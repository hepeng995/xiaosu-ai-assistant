"""文档解析器：统一接口与各格式实现。"""

from pathlib import Path

from app.parsers.base import DocumentParser, ParsedBlock
from app.parsers.docx_parser import DocxParser
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.txt_parser import TxtParser

# 扩展名 → 解析器
_PARSERS: dict[str, type[DocumentParser]] = {
    ".md": MarkdownParser,
    ".markdown": MarkdownParser,
    ".pdf": PdfParser,
    ".docx": DocxParser,
    ".txt": TxtParser,
}

SUPPORTED_EXTENSIONS: set[str] = set(_PARSERS.keys())


def get_parser(file_path: Path) -> DocumentParser:
    """根据文件扩展名返回对应解析器实例；不支持则抛 ValueError。"""
    ext = file_path.suffix.lower()
    parser_cls = _PARSERS.get(ext)
    if parser_cls is None:
        raise ValueError(f"不支持的文件类型: {ext}（支持 {sorted(SUPPORTED_EXTENSIONS)}）")
    return parser_cls()


__all__ = [
    "SUPPORTED_EXTENSIONS",
    "DocumentParser",
    "ParsedBlock",
    "get_parser",
]
