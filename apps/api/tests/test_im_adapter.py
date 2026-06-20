"""IM Adapter 测试：钉钉 webhook 解析 + 回复格式化（不依赖外部服务）。"""
import json

import pytest

from app.im.dingtalk import parse_webhook
from app.im.formatter import format_reply


def test_parse_webhook_group_message() -> None:
    """群聊消息（conversationType=2）→ conversation_type=group，文本去空白。"""
    payload = {
        "msgId": "m1",
        "conversationId": "c1",
        "conversationType": "2",
        "senderStaffId": "u1",
        "senderNick": "张三",
        "text": {"content": " 员工每年有几天年假？"},
    }
    msg = parse_webhook(payload)
    assert msg.platform == "dingtalk"
    assert msg.conversation_type == "group"
    assert msg.user_id == "u1"
    assert msg.text == "员工每年有几天年假？"


def test_parse_webhook_private_message() -> None:
    """私聊（conversationType=1）→ conversation_type=private。"""
    msg = parse_webhook({"conversationType": "1", "text": {"content": "你好"}})
    assert msg.conversation_type == "private"


def test_format_reply_with_references() -> None:
    """有引用时 Markdown 应含参考来源与文件名。"""
    text, markdown = format_reply(
        "正式员工每年 5 天年假。",
        [{"filename": "员工手册.md", "heading_path": "年假规则"}],
        [],
    )
    assert text == "正式员工每年 5 天年假。"
    assert "参考来源" in markdown
    assert "员工手册.md" in markdown


def test_format_reply_with_reference_link(monkeypatch: pytest.MonkeyPatch) -> None:
    """配置 WEB_BASE_URL 后，Markdown 引用应包含可点击 chunk 定位链接。"""
    from app.im import formatter

    monkeypatch.setattr(formatter.settings, "WEB_BASE_URL", "http://localhost:3001")
    _text, markdown = format_reply(
        "正式员工每年 5 天年假。",
        [
            {
                "filename": "员工手册.md",
                "heading_path": "年假规则",
                "document_id": "doc1",
                "chunk_id": "chunk1",
            }
        ],
        [],
    )

    assert "[员工手册.md｜年假规则]" in markdown
    assert "http://localhost:3001/admin/documents/doc1?chunk=chunk1" in markdown


def test_format_reply_with_tool_calls() -> None:
    """有工具调用时 Markdown 应含工具名。"""
    _text, markdown = format_reply("结果", [], [{"name": "get_employee"}])
    assert "get_employee" in markdown


@pytest.mark.asyncio
async def test_dingtalk_verify_sign_dev_mode() -> None:
    """未配置 secret（开发模式）应放行验签。"""
    from app.im.dingtalk import verify_sign

    assert verify_sign("123", "any") is True


# ============ 飞书 IM 适配器测试 ============


def test_feishu_parse_event_p2p() -> None:
    """单聊事件（chat_type=p2p）→ conversation_type=private，提取 text。"""
    from app.im.feishu import parse_event

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1", "token": "t"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_1"}},
            "message": {
                "message_id": "om_1",
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "员工年假几天"}),
            },
        },
    }
    msg = parse_event(payload)
    assert msg.platform == "feishu"
    assert msg.conversation_type == "private"
    assert msg.user_id == "ou_1"
    assert msg.text == "员工年假几天"


def test_feishu_parse_event_group_strip_mention() -> None:
    """群聊事件（chat_type=group）→ conversation_type=group，剥离 @机器人 占位。"""
    from app.im.feishu import parse_event

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_1"}},
            "message": {
                "message_id": "om_2",
                "chat_id": "oc_2",
                "chat_type": "group",
                "message_type": "text",
                "content": json.dumps({"text": "@_user_1 员工年假几天"}),
                "mentions": [{"key": "@_user_1", "id": {"open_id": "ou_bot", "name": "小苏"}}],
            },
        },
    }
    msg = parse_event(payload)
    assert msg.conversation_type == "group"
    assert msg.text == "员工年假几天"


def test_feishu_verify_dev_mode() -> None:
    """未配置 ENCRYPT_KEY/VERIFICATION_TOKEN（开发模式）应放行验签与 token 校验。"""
    from app.im.feishu import verify_signature, verify_token

    assert verify_signature("t", "n", "body", "sig") is True
    assert verify_token("any") is True


def test_feishu_decrypt_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """AES-256-CBC 加密后由 decrypt_payload 解密，应还原原始事件。"""
    import base64
    import hashlib

    from cryptography.hazmat.primitives import padding as sym_padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    from app.im import feishu

    key_str = "test_encrypt_key_123"
    monkeypatch.setattr(feishu.settings, "FEISHU_ENCRYPT_KEY", key_str)

    original = {"schema": "2.0", "event": {"message": {"chat_id": "oc_x"}}}
    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(json.dumps(original).encode("utf-8")) + padder.finalize()
    key = hashlib.sha256(key_str.encode("utf-8")).digest()
    iv = b"0123456789abcdef"
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    combined = iv + encryptor.update(padded) + encryptor.finalize()

    assert feishu.decrypt_payload(base64.b64encode(combined).decode()) == original


def test_feishu_event_type_detection() -> None:
    """握手请求与非消息事件应被正确识别。"""
    from app.im.feishu import is_message_receive_event, is_url_verification

    assert is_url_verification({"type": "url_verification", "challenge": "abc"}) is True
    assert is_url_verification({"schema": "2.0"}) is False
    assert is_message_receive_event({"header": {"event_type": "im.message.receive_v1"}}) is True
    assert is_message_receive_event({"header": {"event_type": "other.event"}}) is False


def test_format_feishu_post_with_references() -> None:
    """飞书 post 富文本应含正文、引用文件名与工具调用。"""
    from app.im.formatter import format_feishu_post

    post = format_feishu_post(
        "正式员工每年 5 天年假。",
        [{"filename": "员工手册.md", "heading_path": "年假规则"}],
        [{"name": "get_employee"}],
    )
    assert "title" not in post["zh_cn"]  # 不再在消息开头加"小苏"标题
    texts = [seg["text"] for row in post["zh_cn"]["content"] for seg in row]
    assert "正式员工每年 5 天年假。" in texts
    assert any("员工手册.md" in t for t in texts)
    assert any("get_employee" in t for t in texts)


def test_format_feishu_post_with_reference_link(monkeypatch: pytest.MonkeyPatch) -> None:
    """飞书 post 引用在配置 WEB_BASE_URL 后应使用 a 标签。"""
    from app.im import formatter
    from app.im.formatter import format_feishu_post

    monkeypatch.setattr(formatter.settings, "WEB_BASE_URL", "http://localhost:3001")
    post = format_feishu_post(
        "正式员工每年 5 天年假。",
        [
            {
                "filename": "员工手册.md",
                "heading_path": "年假规则",
                "document_id": "doc1",
                "chunk_id": "chunk1",
            }
        ],
        [],
    )
    links = [seg for row in post["zh_cn"]["content"] for seg in row if seg["tag"] == "a"]

    assert links[0]["href"] == "http://localhost:3001/admin/documents/doc1?chunk=chunk1"


@pytest.mark.asyncio
async def test_dingtalk_reply_retries_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """钉钉回复遇到 5xx 应重试一次。"""
    from app.im import dingtalk

    class FakeResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    class FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.responses = [FakeResponse(500), FakeResponse(200)]
            self.calls = 0

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            self.calls += 1
            return self.responses.pop(0)

    fake_client = FakeClient()
    monkeypatch.setattr(dingtalk.httpx, "AsyncClient", lambda **_kwargs: fake_client)

    assert await dingtalk.reply_via_webhook("http://webhook.test", "hi") is True
    assert fake_client.calls == 2


@pytest.mark.asyncio
async def test_feishu_reply_retries_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """飞书回复发送消息遇到 5xx 应重试一次。"""
    import time

    from app.im import feishu

    class FakeResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError("server error")

        def json(self) -> dict:
            return {}

    class FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.responses = [FakeResponse(500), FakeResponse(200)]
            self.calls = 0

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            self.calls += 1
            return self.responses.pop(0)

    fake_client = FakeClient()
    feishu._token_cache.update(token="token", expire_at=time.time() + 3600)
    monkeypatch.setattr(feishu.httpx, "AsyncClient", lambda **_kwargs: fake_client)

    assert await feishu.reply_message("chat", {"text": "hi"}) is True
    assert fake_client.calls == 2
