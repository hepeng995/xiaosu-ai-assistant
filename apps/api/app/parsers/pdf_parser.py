"""PDF 解析器：按页提取，保留 page_number。"""

from pathlib import Path

from pypdf import PdfReader

from app.parsers.base import DocumentParser, ParsedBlock, split_paragraphs


class PdfParser(DocumentParser):
    """逐页提取文本，按段落切分并标注页码。"""

    async def parse(self, file_path: Path) -> list[ParsedBlock]:
        reader = PdfReader(str(file_path))
        blocks: list[ParsedBlock] = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for para_idx, para in enumerate(split_paragraphs(text)):
                blocks.append(ParsedBlock(text=para, page_number=page_no, paragraph_index=para_idx))
        return blocks
