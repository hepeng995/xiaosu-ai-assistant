"""纯文本解析器：按段落切分（无标题层级）。"""

from pathlib import Path

from app.parsers.base import DocumentParser, ParsedBlock, split_paragraphs


class TxtParser(DocumentParser):
    """按空行切分段落，paragraph_index 递增。"""

    async def parse(self, file_path: Path) -> list[ParsedBlock]:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return [
            ParsedBlock(text=para, paragraph_index=idx)
            for idx, para in enumerate(split_paragraphs(text))
        ]
