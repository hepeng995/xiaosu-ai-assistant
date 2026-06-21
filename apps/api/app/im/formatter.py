"""IM 回复格式化：引用 Markdown / 飞书 post 富文本，按 IM 能力选择展示形式。"""

from app.core.config import settings
from app.im.base import IMMention


def _reference_location(r: dict) -> str:
    """推导单条引用的定位描述（钉钉 Markdown 与飞书 post 共用，避免重复）。"""
    if r.get("heading_path"):
        return str(r["heading_path"])
    if r.get("page_number") is not None:
        return f"第 {r['page_number']} 页"
    return f"第 {r.get('paragraph_index', '?')} 段"


def _reference_url(r: dict) -> str | None:
    """生成 Web 后台 chunk 定位链接；缺少字段时降级为纯文本引用。"""
    document_id = r.get("document_id")
    chunk_id = r.get("chunk_id")
    if not (settings.WEB_BASE_URL and document_id and chunk_id):
        return None
    base = settings.WEB_BASE_URL.rstrip("/")
    return f"{base}/admin/documents/{document_id}?chunk={chunk_id}"


def format_reply(
    answer: str,
    references: list[dict] | None = None,
    tool_calls: list[dict] | None = None,
) -> tuple[str, str]:
    """生成 (纯文本, Markdown) 双形式回复。

    Markdown 追加参考来源与工具调用，IM 端按能力选择展示形式。
    """
    text = answer
    lines: list[str] = [answer]

    if references:
        lines.append("\n---\n参考来源：")
        for i, r in enumerate(references, 1):
            label = f"{r.get('filename', '')}｜{_reference_location(r)}"
            url = _reference_url(r)
            lines.append(f"{i}. [{label}]({url})" if url else f"{i}. {label}")

    if tool_calls:
        names = "、".join(t.get("name", "") for t in tool_calls)
        lines.append(f"\n（本次调用工具：{names}）")

    return text, "\n".join(lines)


def format_feishu_post(
    answer: str,
    references: list[dict] | None = None,
    tool_calls: list[dict] | None = None,
    mentions: list[IMMention] | None = None,
) -> dict:
    """生成飞书 post 富文本结构（``{"zh_cn": {"content": [[...]]}}``）。

    由 ``im/feishu.reply_message`` 以 ``msg_type=post`` 发送，复用 ``_reference_location``。
    不带 title，避免每条消息正文开头都出现"小苏"前缀。
    """
    first_row: list[dict] = [{"tag": "text", "text": answer}]
    if mentions:
        first_row.append({"tag": "text", "text": "\n"})
        for mention in mentions:
            first_row.append(
                {
                    "tag": "at",
                    "user_id": mention.open_id or mention.user_id,
                    "user_name": mention.name or "成员",
                }
            )
            first_row.append({"tag": "text", "text": " "})
    content: list[list[dict]] = [first_row]

    if references:
        content.append([{"tag": "text", "text": "参考来源："}])
        for i, r in enumerate(references, 1):
            line = f"{i}. {r.get('filename', '')}｜{_reference_location(r)}"
            url = _reference_url(r)
            content.append(
                [{"tag": "a", "text": line, "href": url}]
                if url
                else [{"tag": "text", "text": line}]
            )

    if tool_calls:
        names = "、".join(t.get("name", "") for t in tool_calls)
        content.append([{"tag": "text", "text": f"（本次调用工具：{names}）"}])

    return {"zh_cn": {"content": content}}


def format_feishu_card_markdown(
    answer: str,
    references: list[dict] | None = None,
    tool_calls: list[dict] | None = None,
    mentions: list[IMMention] | None = None,
) -> str:
    """生成飞书卡片 markdown 文本（供 ``send_static_card`` 一次性投递）。

    与 :func:`format_feishu_post` 字段一一对应，确保卡片化后功能不丢失：
    - 正文原样；
    - 参考来源用 ``---`` 分隔 + ``[text](url)``，无 url 降级纯文本（复用 ``_reference_url``）；
    - @ 提及用飞书卡片 markdown 专用语法 ``<at user_id="ou_xxx">name</at>``，触发真通知
      （补齐流式路径只拼 ``@name`` 纯文本而丢失的通知能力）。
    """
    parts: list[str] = []
    if answer:
        parts.append(answer)

    if mentions:
        at_line = " ".join(
            f'<at user_id="{m.open_id or m.user_id}">{m.name or "成员"}</at>'
            for m in mentions
            if (m.open_id or m.user_id)
        )
        if at_line:
            parts.append(at_line)

    if references:
        parts.append("---")
        parts.append("**参考来源：**")
        for i, r in enumerate(references, 1):
            label = f"{i}. {r.get('filename', '')}｜{_reference_location(r)}"
            url = _reference_url(r)
            parts.append(f"[{label}]({url})" if url else label)

    if tool_calls:
        names = "、".join(t.get("name", "") for t in tool_calls)
        parts.append(f"（本次调用工具：{names}）")

    return "\n".join(parts).strip()
