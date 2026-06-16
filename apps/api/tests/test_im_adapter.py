"""IM Adapter 测试：钉钉 webhook 解析 + 回复格式化（不依赖外部服务）。"""
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


def test_format_reply_with_tool_calls() -> None:
    """有工具调用时 Markdown 应含工具名。"""
    _text, markdown = format_reply("结果", [], [{"name": "get_employee"}])
    assert "get_employee" in markdown


@pytest.mark.asyncio
async def test_dingtalk_verify_sign_dev_mode() -> None:
    """未配置 secret（开发模式）应放行验签。"""
    from app.im.dingtalk import verify_sign

    assert verify_sign("123", "any") is True
