"""Word(.docx) 解析器：按标题样式与段落切分。"""

from pathlib import Path

from docx import Document as DocxDocument

from app.parsers.base import DocumentParser, ParsedBlock


class DocxParser(DocumentParser):
    """依据段落样式识别标题（构建 heading_path）与正文段落。"""

    async def parse(self, file_path: Path) -> list[ParsedBlock]:
        doc = DocxDocument(str(file_path))
        blocks: list[ParsedBlock] = []
        heading_stack: list[str] = []
        para_idx = 0
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style = para.style.name if para.style else ""
            if style.startswith("Heading"):
                try:
                    level = int(style.split()[-1])
                except ValueError:
                    level = 1
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(text)
            else:
                blocks.append(
                    ParsedBlock(
                        text=text,
                        heading_path=" > ".join(heading_stack) or None,
                        paragraph_index=para_idx,
                    )
                )
                para_idx += 1
        return blocks
