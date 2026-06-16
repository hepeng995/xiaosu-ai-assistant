"""Markdown 解析器：保留标题层级（heading_path）。"""

import re
from pathlib import Path

from app.parsers.base import DocumentParser, ParsedBlock

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


class MarkdownParser(DocumentParser):
    """按 Markdown 标题层级切分，每个标题下内容成一个块。"""

    async def parse(self, file_path: Path) -> list[ParsedBlock]:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        blocks: list[ParsedBlock] = []
        heading_stack: list[str] = []
        current_lines: list[str] = []
        para_idx = 0

        def flush() -> None:
            nonlocal para_idx
            if not current_lines:
                return
            content = "\n".join(current_lines).strip()
            if content:
                blocks.append(
                    ParsedBlock(
                        text=content,
                        heading_path=" > ".join(heading_stack) if heading_stack else None,
                        paragraph_index=para_idx,
                    )
                )
                para_idx += 1
            current_lines.clear()

        for line in text.splitlines():
            m = _HEADING_RE.match(line)
            if m:
                flush()
                level = len(m.group(1))
                title = m.group(2).strip()
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(title)
            else:
                current_lines.append(line)
        flush()
        return blocks
