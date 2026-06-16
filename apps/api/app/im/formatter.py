"""IM 回复格式化（引用 Markdown，适配钉钉等 IM 展示）。"""


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
            if r.get("heading_path"):
                loc = r["heading_path"]
            elif r.get("page_number") is not None:
                loc = f"第 {r['page_number']} 页"
            else:
                loc = f"第 {r.get('paragraph_index', '?')} 段"
            lines.append(f"{i}. {r.get('filename', '')}｜{loc}")

    if tool_calls:
        names = "、".join(t.get("name", "") for t in tool_calls)
        lines.append(f"\n（本次调用工具：{names}）")

    return text, "\n".join(lines)
