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


def test_feishu_parse_event_preserves_non_bot_mentions() -> None:
    """解析群聊文本时应剥离机器人占位，同时保留其他被 @ 成员用于富消息回复。"""
    from app.im.feishu import parse_event

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_1"}},
            "message": {
                "message_id": "om_mention",
                "chat_id": "oc_mention",
                "chat_type": "group",
                "message_type": "text",
                "content": json.dumps({"text": "@_user_1 帮 @_user_2 查一下年假"}),
                "mentions": [
                    {"key": "@_user_1", "id": {"open_id": "ou_bot"}, "name": "小苏"},
                    {"key": "@_user_2", "id": {"open_id": "ou_2"}, "name": "李四"},
                ],
            },
        },
    }
    msg = parse_event(payload)

    assert msg.text == "帮 查一下年假"
    assert [m.open_id for m in msg.mentions] == ["ou_2"]
    assert msg.mentions[0].name == "李四"


def test_feishu_parse_file_event_as_attachment() -> None:
    """飞书文件消息应转换为 IMAttachment，供路由层下载并索引。"""
    from app.im.feishu import parse_event

    payload = {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_1"}},
            "message": {
                "message_id": "om_file",
                "chat_id": "oc_file",
                "chat_type": "p2p",
                "message_type": "file",
                "content": json.dumps(
                    {"file_key": "file_v2_x", "file_name": "制度.md", "file_size": 128}
                ),
            },
        },
    }
    msg = parse_event(payload)

    assert msg.text == ""
    assert len(msg.attachments) == 1
    assert msg.attachments[0].file_key == "file_v2_x"
    assert msg.attachments[0].filename == "制度.md"
    assert msg.attachments[0].file_type == "md"


def test_format_feishu_post_with_mentions() -> None:
    """飞书 post 回复应能用 at 富文本元素展示被 @ 群成员。"""
    from app.im.base import IMMention
    from app.im.formatter import format_feishu_post

    post = format_feishu_post(
        "已为你查询。",
        [],
        [],
        mentions=[IMMention(open_id="ou_2", name="李四")],
    )
    segments = [seg for row in post["zh_cn"]["content"] for seg in row]

    assert {"tag": "at", "user_id": "ou_2", "user_name": "李四"} in segments


def test_im_verify_rejects_missing_secret_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """生产环境缺少 IM 密钥时必须拒绝验签，不能沿用开发放行。"""
    from app.im import dingtalk, feishu

    monkeypatch.setattr(dingtalk.settings, "APP_ENV", "production")
    monkeypatch.setattr(dingtalk.settings, "DINGTALK_APP_SECRET", "replace_me")
    monkeypatch.setattr(dingtalk.settings, "DINGTALK_CALLBACK_TOKEN", "replace_me")
    monkeypatch.setattr(feishu.settings, "APP_ENV", "production")
    monkeypatch.setattr(feishu.settings, "FEISHU_VERIFICATION_TOKEN", "replace_me")
    monkeypatch.setattr(feishu.settings, "FEISHU_ENCRYPT_KEY", "replace_me")

    assert dingtalk.verify_sign("123", "any") is False
    assert dingtalk.verify_event_signature("1", "n", "e", "sig") is False
    assert feishu.verify_token("any") is False
    assert feishu.verify_signature("1", "n", "body", "sig") is False


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


# ---------- 飞书 CardKit 流式卡片 ----------


@pytest.mark.asyncio
async def test_feishu_stream_create_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """创建流式卡片：card.create + message create 均成功 → 返回 card_id。"""
    from app.im import feishu_stream

    class FakeResp:
        status_code = 200

        def json(self) -> dict:
            return {"code": 0, "msg": "ok", "data": {"card_id": "CARD_001"}}

    async def fake_post(url: str, **_kwargs: object) -> FakeResp:
        return FakeResp()

    async def fake_token() -> str:
        return "tenant_token"

    monkeypatch.setattr(feishu_stream, "_post_json_with_retry", fake_post)
    monkeypatch.setattr(feishu_stream, "get_tenant_access_token", fake_token)

    assert await feishu_stream.create_streaming_card("chat_1") == "CARD_001"


@pytest.mark.asyncio
async def test_feishu_stream_create_no_permission_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """card.create 失败（如缺 cardkit:card:write 权限）→ 返回 None（调用方降级）。"""
    from app.im import feishu_stream

    class FakeResp:
        status_code = 200

        def json(self) -> dict:
            return {"code": 99991000, "msg": "permission denied"}

    async def fake_post(url: str, **_kwargs: object) -> FakeResp:
        return FakeResp()

    async def fake_token() -> str:
        return "tenant_token"

    monkeypatch.setattr(feishu_stream, "_post_json_with_retry", fake_post)
    monkeypatch.setattr(feishu_stream, "get_tenant_access_token", fake_token)

    assert await feishu_stream.create_streaming_card("chat_1") is None


@pytest.mark.asyncio
async def test_feishu_stream_reply_batches_and_appends_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_feishu_stream_reply 攒批更新卡片，最终追加引用并关闭流式。"""
    import time as _time

    from loguru import logger

    from app.api import routes_im
    from app.im.base import IMMessage

    updates: list[tuple[int, str]] = []
    closes: list[int] = []

    async def fake_stream_chat(*_args: object, **_kwargs: object):
        for piece in ("你", "好", "！"):
            yield {"event": "token", "data": {"content": piece}}
        yield {"event": "references", "data": {"references": [{"filename": "员工手册.md"}]}}

    async def fake_update(card_id: str, content: str, sequence: int) -> bool:
        updates.append((sequence, content))
        return True

    async def fake_close(card_id: str, sequence: int) -> bool:
        closes.append(sequence)
        return True

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    # 让 time.monotonic 每次调用递增，确保每个 token 都触发攒批 flush
    counter = [0]
    orig_monotonic = _time.monotonic

    def fake_monotonic() -> float:
        counter[0] += 1
        return orig_monotonic() + counter[0]

    monkeypatch.setattr(routes_im.chat_service, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(routes_im.feishu_stream, "update_card_text", fake_update)
    monkeypatch.setattr(routes_im.feishu_stream, "close_streaming", fake_close)
    monkeypatch.setattr(routes_im, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(routes_im.time, "monotonic", fake_monotonic)

    im_msg = IMMessage(
        platform="feishu",
        message_id="m1",
        conversation_id="c1",
        conversation_type="private",
        user_id="u1",
        user_name=None,
        text="你好",
        raw={},
    )
    await routes_im._feishu_stream_reply(im_msg, "CARD_1", logger.bind())

    # 每个 token flush 一次 + 最终全文(含引用)1 次
    assert len(updates) >= 2
    assert updates[-1][1].startswith("你好！")
    assert "参考来源" in updates[-1][1]
    assert "员工手册.md" in updates[-1][1]
    assert len(closes) == 1


@pytest.mark.asyncio
async def test_handle_feishu_file_upload_indexes_supported_attachment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """飞书文件消息应下载、复用文档服务上传并同步索引，然后回复成功文案。"""
    from loguru import logger

    from app.api import routes_im
    from app.im.base import IMAttachment, IMMessage

    uploaded: list[tuple[str, bytes]] = []
    indexed: list[object] = []
    replies: list[tuple[str, dict, str]] = []
    doc = type("Doc", (), {"id": "doc-1", "original_filename": "制度.md"})()

    async def fake_download(_message_id: str, _attachment: IMAttachment) -> bytes:
        return b"# new policy"

    async def fake_upload(file: object, _session: object) -> object:
        uploaded.append((file.filename, await file.read()))
        return doc

    async def fake_index(document_id: object) -> None:
        indexed.append(document_id)

    async def fake_reply(receive_id: str, content: dict, msg_type: str = "text") -> bool:
        replies.append((receive_id, content, msg_type))
        return True

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

        async def refresh(self, _obj: object) -> None:
            return None

    monkeypatch.setattr(routes_im, "download_feishu_file", fake_download)
    monkeypatch.setattr(routes_im.document_service, "upload_document", fake_upload)
    monkeypatch.setattr(routes_im, "index_document", fake_index)
    monkeypatch.setattr(routes_im, "reply_message", fake_reply)
    monkeypatch.setattr(routes_im, "AsyncSessionLocal", lambda: FakeSession())

    im_msg = IMMessage(
        platform="feishu",
        message_id="om_file",
        conversation_id="oc_file",
        conversation_type="private",
        user_id="ou_1",
        text="",
        raw={},
        attachments=[
            IMAttachment(file_key="file_v2_x", filename="制度.md", file_size=12, file_type="md")
        ],
    )

    assert await routes_im._handle_feishu_file_message(im_msg, logger.bind()) is True
    assert uploaded == [("制度.md", b"# new policy")]
    assert indexed == ["doc-1"]
    assert replies[0][0] == "oc_file"
    assert replies[0][2] == "post"
    texts = [seg["text"] for row in replies[0][1]["zh_cn"]["content"] for seg in row]
    assert any("已加入知识库" in text for text in texts)


@pytest.mark.asyncio
async def test_handle_feishu_file_upload_rejects_unsupported_attachment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """飞书文件问答只允许知识库白名单格式，非法格式应友好回复且不下载。"""
    from loguru import logger

    from app.api import routes_im
    from app.im.base import IMAttachment, IMMessage

    replies: list[dict] = []

    async def fake_download(*_args: object) -> bytes:
        raise AssertionError("非法格式不应下载文件")

    async def fake_reply(_receive_id: str, content: dict, msg_type: str = "text") -> bool:
        replies.append(content)
        return True

    monkeypatch.setattr(routes_im, "download_feishu_file", fake_download)
    monkeypatch.setattr(routes_im, "reply_message", fake_reply)

    im_msg = IMMessage(
        platform="feishu",
        message_id="om_file",
        conversation_id="oc_file",
        conversation_type="private",
        user_id="ou_1",
        text="",
        raw={},
        attachments=[
            IMAttachment(file_key="file_v2_x", filename="合同.xlsx", file_size=12, file_type="xlsx")
        ],
    )

    assert await routes_im._handle_feishu_file_message(im_msg, logger.bind()) is True
    texts = [seg["text"] for row in replies[0]["zh_cn"]["content"] for seg in row]
    assert any("仅支持" in text for text in texts)


@pytest.mark.asyncio
async def test_feishu_stream_reply_renders_status_as_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_feishu_stream_reply 应把 status 文案渲染为 markdown 引用块，终态清空进度只留答案。"""
    import time as _time

    from loguru import logger

    from app.api import routes_im
    from app.im.base import IMMessage

    updates: list[str] = []

    async def fake_stream_chat(*_args: object, **_kwargs: object):
        yield {
            "event": "status",
            "data": {
                "stage": "tool_call",
                "tool_name": "search_knowledge_base",
                "label": "正在检索知识库...",
            },
        }
        yield {"event": "token", "data": {"content": "答案"}}
        yield {"event": "references", "data": {"references": []}}

    async def fake_update(_card_id: str, content: str, _sequence: int) -> bool:
        updates.append(content)
        return True

    async def fake_close(_card_id: str, _sequence: int) -> bool:
        return True

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    counter = [0]
    orig_monotonic = _time.monotonic

    def fake_monotonic() -> float:
        counter[0] += 1
        return orig_monotonic() + counter[0]

    monkeypatch.setattr(routes_im.chat_service, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(routes_im.feishu_stream, "update_card_text", fake_update)
    monkeypatch.setattr(routes_im.feishu_stream, "close_streaming", fake_close)
    monkeypatch.setattr(routes_im, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(routes_im.time, "monotonic", fake_monotonic)

    im_msg = IMMessage(
        platform="feishu",
        message_id="m1",
        conversation_id="c1",
        conversation_type="private",
        user_id="u1",
        user_name=None,
        text="查",
        raw={},
    )
    await routes_im._feishu_stream_reply(im_msg, "CARD_1", logger.bind())

    # 过程态：进度文案以 markdown 引用块（>）出现
    assert any("> 正在检索知识库..." in u for u in updates)
    # 终态：清空进度文案，只保留答案
    assert updates[-1] == "答案"


@pytest.mark.asyncio
async def test_dingtalk_handle_message_placeholder_then_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_handle_dingtalk_message 应先发占位消息（纯文本），再发最终答案（双消息方案）。"""
    from loguru import logger

    from app.api import routes_im
    from app.core.config import settings
    from app.im.base import IMMessage

    replies: list[tuple[str, str | None]] = []
    chat_called = [False]

    async def fake_chat(*_args: object, **_kwargs: object) -> dict:
        chat_called[0] = True
        return {"answer": "最终答案", "references": [], "tool_calls": [], "refused": False}

    async def fake_reply(_webhook: str, text: str, markdown: str | None = None) -> bool:
        replies.append((text, markdown))
        return True

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(routes_im.chat_service, "chat", fake_chat)
    monkeypatch.setattr(routes_im, "reply_via_webhook", fake_reply)
    monkeypatch.setattr(routes_im, "AsyncSessionLocal", lambda: FakeSession())

    im_msg = IMMessage(
        platform="dingtalk",
        message_id="m1",
        conversation_id="c1",
        conversation_type="private",
        user_id="u1",
        user_name=None,
        text="你好",
        raw={},
    )
    await routes_im._handle_dingtalk_message(im_msg, "https://wh.example", logger.bind())

    # 占位先发（纯文本 markdown=None），最终答案后发
    assert len(replies) == 2
    assert replies[0] == (settings.DINGTALK_PLACEHOLDER_TEXT, None)
    assert replies[1][0] == "最终答案"
    assert chat_called[0] is True


@pytest.mark.asyncio
async def test_send_feishu_card_or_fallback_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """静态卡片发送成功时不走 post 兜底。"""
    from loguru import logger

    from app.api import routes_im

    card_called = [False]
    post_called = [False]

    async def fake_card(_rid: str, _content: str) -> bool:
        card_called[0] = True
        return True

    async def fake_reply(*_a: object, **_kw: object) -> bool:
        post_called[0] = True
        return True

    monkeypatch.setattr(routes_im.feishu_stream, "send_static_card", fake_card)
    monkeypatch.setattr(routes_im, "reply_message", fake_reply)

    await routes_im._send_feishu_card_or_fallback("oc_x", "hi", [], [], None, logger.bind())
    assert card_called[0] is True
    assert post_called[0] is False


@pytest.mark.asyncio
async def test_send_feishu_card_or_fallback_post_on_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """静态卡片失败时降级 post 富文本（IM 端必有回复）。"""
    from loguru import logger

    from app.api import routes_im

    post_calls: list[tuple] = []

    async def fake_card(_rid: str, _content: str) -> bool:
        return False

    async def fake_reply(receive_id: str, content: dict, msg_type: str = "text") -> bool:
        post_calls.append((receive_id, content, msg_type))
        return True

    monkeypatch.setattr(routes_im.feishu_stream, "send_static_card", fake_card)
    monkeypatch.setattr(routes_im, "reply_message", fake_reply)

    await routes_im._send_feishu_card_or_fallback("oc_x", "hi", [], [], None, logger.bind())
    assert len(post_calls) == 1
    assert post_calls[0][0] == "oc_x"
    assert post_calls[0][2] == "post"
    assert "zh_cn" in post_calls[0][1]


def test_format_feishu_card_markdown_at_syntax() -> None:
    """@ 提及用飞书卡片 <at user_id> 语法（触发真通知，补齐流式路径丢失的能力）。"""
    from app.im.base import IMMention
    from app.im.formatter import format_feishu_card_markdown

    md = format_feishu_card_markdown("hi", [], [], [IMMention(open_id="ou_abc", name="张三")])
    assert '<at user_id="ou_abc">张三</at>' in md


def test_format_feishu_card_markdown_skips_empty_mention() -> None:
    """空 open_id/user_id 的 mention 被跳过，不生成无效 <at>。"""
    from app.im.base import IMMention
    from app.im.formatter import format_feishu_card_markdown

    md = format_feishu_card_markdown(
        "hi", [], [], [IMMention(open_id="", user_id="", name="x")]
    )
    assert "<at" not in md


def test_format_feishu_card_markdown_reference_url() -> None:
    """参考来源有 url 用 [text](url)，缺字段降级纯文本。"""
    from app.im.formatter import format_feishu_card_markdown

    md_with_url = format_feishu_card_markdown(
        "hi",
        [{"filename": "员工手册.md", "document_id": "d1", "chunk_id": "c1", "paragraph_index": 1}],
        [], [],
    )
    assert "[1. 员工手册.md" in md_with_url

    md_no_url = format_feishu_card_markdown(
        "hi", [{"filename": "无链接.md", "paragraph_index": 1}], [], []
    )
    assert "[" not in md_no_url
    assert "无链接.md" in md_no_url


def test_build_static_card_json_not_streaming() -> None:
    """静态卡片 JSON 的 streaming_mode=False，content 预填，复用 md_1 元素 id。"""
    import json

    from app.im.feishu_stream import _build_static_card_json

    card = json.loads(_build_static_card_json("hello"))
    assert card["config"]["streaming_mode"] is False
    assert card["body"]["elements"][0]["content"] == "hello"
    assert card["body"]["elements"][0]["element_id"] == "md_1"


@pytest.mark.asyncio
async def test_send_static_card_empty_receive_id_short_circuits() -> None:
    """空 receive_id 或空 content 短路返回 False（不调底层 API）。"""
    from app.im.feishu_stream import send_static_card

    assert await send_static_card("", "hi") is False
    assert await send_static_card("oc_x", "") is False


@pytest.mark.asyncio
async def test_feishu_post_reply_streams_tokens_and_posts_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_feishu_post_reply 应消费 stream_chat 累积 token，最后 post 一次性回复。"""
    from loguru import logger

    from app.api import routes_im
    from app.im.base import IMMessage

    posts: list[tuple] = []

    async def fake_stream_chat(*_args: object, **_kwargs: object):
        yield {"event": "token", "data": {"content": "你"}}
        yield {"event": "token", "data": {"content": "好"}}
        yield {
            "event": "references",
            "data": {"references": [{"filename": "员工手册.md"}]},
        }

    async def fake_reply(receive_id: str, content: dict, msg_type: str = "text") -> bool:
        posts.append((receive_id, content, msg_type))
        return True

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(routes_im.chat_service, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(routes_im, "reply_message", fake_reply)
    monkeypatch.setattr(routes_im, "AsyncSessionLocal", lambda: FakeSession())

    im_msg = IMMessage(
        platform="feishu",
        message_id="m1",
        conversation_id="c1",
        conversation_type="private",
        user_id="u1",
        user_name=None,
        text="你好",
        raw={},
    )
    await routes_im._feishu_post_reply(im_msg, logger.bind())

    # 只 post 一次，msg_type=post
    assert len(posts) == 1
    assert posts[0][0] == "c1"
    assert posts[0][2] == "post"
    # post 富文本首行含累积的完整答案「你好」
    first_row = posts[0][1]["zh_cn"]["content"][0]
    assert any("你好" in node.get("text", "") for node in first_row if isinstance(node, dict))
