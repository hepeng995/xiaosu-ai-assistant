"""文档解析器统一抽象与公共工具。"""

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel


class ParsedBlock(BaseModel):
    """解析后的文本块（含定位信息，用于分块与引用溯源）。"""

    text: str
    heading_path: str | None = None
    page_number: int | None = None
    paragraph_index: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


class DocumentParser:
    """文档解析器基类（子类实现 parse）。

    统一接口：``async parse(file_path) -> list[ParsedBlock]``。
    解析为 CPU 密集型同步操作，在小文档场景下直接在 async 内执行。
    """

    async def parse(self, file_path: Path) -> list[ParsedBlock]:
        raise NotImplementedError


def split_paragraphs(text: str) -> list[str]:
    """按连续空行切分段落，丢弃空白段。"""
    paragraphs: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line.rstrip())
        elif current:
            paragraphs.append("\n".join(current).strip())
            current = []
    if current:
        paragraphs.append("\n".join(current).strip())
    return paragraphs


# 解析器工厂：按文件扩展名返回对应解析器实例
ParserFactory = Callable[[], DocumentParser]
