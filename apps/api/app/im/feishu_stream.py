"""飞书 CardKit 流式卡片：先发流式卡片，再流式更新文本（打字机效果）。

流程（参考飞书「流式更新卡片」官方文档）：
1. ``card.create``（卡片 JSON 2.0，``streaming_mode:true``）→ ``card_id``
2. ``im/v1/messages``（``msg_type=interactive``）→ 发卡片到会话
3. ``PUT .../cards/:card_id/elements/:element_id/content``
   （全量文本 + ``sequence`` 递增）→ 打字机效果
4. ``PATCH .../cards/:card_id/settings``（``streaming_mode:false``）→ 关闭流式

前置：应用需开通 ``cardkit:card:write`` 权限。任一步失败由调用方降级为一次性 post 回复，
保证 IM 端必有回复（不破坏现有兜底）。
"""

import json
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.im.feishu import _post_json_with_retry, get_tenant_access_token

# 卡片内 markdown 组件 id（与下方卡片 JSON 一致；流式更新文本按此定位）
_ELEMENT_ID = "md_1"

# 卡片 JSON 2.0：开启流式 + 一个 markdown 组件（初始空，由流式更新填充）
_STREAMING_CARD_JSON = json.dumps(
    {
        "schema": "2.0",
        "config": {
            "streaming_mode": True,
            "streaming_config": {
                "print_frequency_ms": {"default": 50},
                "print_step": {"default": 2},
                "print_strategy": "fast",
            },
        },
        "body": {
            "elements": [
                {"tag": "markdown", "content": "", "element_id": _ELEMENT_ID}
            ]
        },
    },
    ensure_ascii=False,
)


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }


async def _request(
    method: str, url: str, token: str, body: dict[str, Any]
) -> dict[str, Any] | None:
    """通用飞书 CardKit 请求；成功返回 data，失败记日志返回 None（不抛出）。"""
    try:
        async with httpx.AsyncClient(
            timeout=float(settings.IM_DEFAULT_TIMEOUT_SECONDS)
        ) as client:
            resp = await client.request(method, url, json=body, headers=_auth_headers(token))
            data = resp.json()
            if resp.status_code != 200 or data.get("code", 0) != 0:
                logger.bind(module="im", event="feishu_stream").warning(
                    "飞书流式请求失败 {} status={} code={} msg={}",
                    method,
                    resp.status_code,
                    data.get("code"),
                    data.get("msg"),
                )
                return None
            return data
    except Exception as exc:
        logger.bind(module="im", event="feishu_stream").warning(
            "飞书流式请求异常 {}: {}", method, exc
        )
        return None


async def _create_card_and_send(receive_id: str, card_json_str: str) -> str | None:
    """创建 CardKit 卡片实体并发送到会话，返回 card_id；任一步失败返回 None。

    流式（``streaming_mode=True``）与非流式（``streaming_mode=False``）卡片共用此两步逻辑，
    仅 ``card_json_str`` 不同。调用方据此决定是否降级为 post 回复。
    """
    try:
        token = await get_tenant_access_token()
    except RuntimeError:
        return None

    # 1) 创建卡片实体
    create_url = f"{settings.FEISHU_BASE_URL}/cardkit/v1/cards"
    try:
        resp = await _post_json_with_retry(
            create_url,
            json={"type": "card_json", "data": card_json_str},
            headers=_auth_headers(token),
        )
        data = resp.json()
    except Exception as exc:
        logger.bind(module="im", event="feishu_stream").warning("创建卡片异常: {}", exc)
        return None
    if resp.status_code != 200 or data.get("code", 0) != 0:
        logger.bind(module="im", event="feishu_stream").warning(
            "创建卡片失败 status={} code={} msg={}",
            resp.status_code,
            data.get("code"),
            data.get("msg"),
        )
        return None
    card_id = (data.get("data") or {}).get("card_id")
    if not card_id:
        return None

    # 2) 把卡片实体作为 interactive 消息发到会话
    msg_url = f"{settings.FEISHU_BASE_URL}/im/v1/messages?receive_id_type=chat_id"
    msg_body = {
        "receive_id": receive_id,
        "msg_type": "interactive",
        "content": json.dumps(
            {"type": "card", "data": {"card_id": card_id}}, ensure_ascii=False
        ),
    }
    try:
        mresp = await _post_json_with_retry(msg_url, json=msg_body, headers=_auth_headers(token))
        mdata = mresp.json()
        if mresp.status_code != 200 or mdata.get("code", 0) != 0:
            logger.bind(module="im", event="feishu_stream").warning(
                "发送卡片失败 status={} code={} msg={}",
                mresp.status_code,
                mdata.get("code"),
                mdata.get("msg"),
            )
            return None
    except Exception as exc:
        logger.bind(module="im", event="feishu_stream").warning("发送卡片异常: {}", exc)
        return None
    return card_id


async def create_streaming_card(receive_id: str) -> str | None:
    """创建流式卡片并发送到会话（chat_id），返回 card_id；任一步失败返回 None（调用方降级）。"""
    if not receive_id:
        return None
    return await _create_card_and_send(receive_id, _STREAMING_CARD_JSON)


def _build_static_card_json(content: str) -> str:
    """构建非流式 CardKit JSON（schema 2.0，streaming_mode=False，content 预填完整文本）。"""
    return json.dumps(
        {
            "schema": "2.0",
            "config": {"streaming_mode": False},
            "body": {
                "elements": [
                    {"tag": "markdown", "content": content, "element_id": _ELEMENT_ID}
                ]
            },
        },
        ensure_ascii=False,
    )


async def send_static_card(receive_id: str, content: str) -> bool:
    """发送一次性非流式卡片（完整内容直接呈现，无打字机）；失败返回 False（调用方降级 post）。

    与流式路径独立：复用 :func:`_create_card_and_send` 的两步创建+发送，仅卡片 JSON 不同。
    """
    if not receive_id or not content:
        return False
    card_id = await _create_card_and_send(receive_id, _build_static_card_json(content))
    return card_id is not None


async def update_card_text(card_id: str, content: str, sequence: int) -> bool:
    """流式更新卡片 markdown 全量文本（``sequence`` 严格递增）；失败返回 False。"""
    if not card_id:
        return False
    try:
        token = await get_tenant_access_token()
    except RuntimeError:
        return False
    url = (
        f"{settings.FEISHU_BASE_URL}/cardkit/v1/cards/{card_id}/elements/{_ELEMENT_ID}/content"
    )
    data = await _request("PUT", url, token, {"content": content, "sequence": sequence})
    return data is not None


async def close_streaming(card_id: str, sequence: int) -> bool:
    """关闭卡片流式更新模式（best-effort，失败不阻塞；超时 10 分钟也会自动关闭）。

    settings 接口 method 以官方为准（PATCH）；若实际不符，流式仍会自动关闭，不影响主功能。
    """
    if not card_id:
        return False
    try:
        token = await get_tenant_access_token()
    except RuntimeError:
        return False
    url = f"{settings.FEISHU_BASE_URL}/cardkit/v1/cards/{card_id}/settings"
    body = {
        "settings": json.dumps({"config": {"streaming_mode": False}}, ensure_ascii=False),
        "uuid": f"close-{card_id}-{sequence}",
        "sequence": sequence,
    }
    data = await _request("PATCH", url, token, body)
    return data is not None
