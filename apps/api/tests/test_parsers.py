"""文档解析与分块测试（不依赖真实 API Key / 数据库）。"""

from pathlib import Path

import pytest

from app.parsers.base import ParsedBlock
from app.parsers.docx_parser import DocxParser
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.txt_parser import TxtParser
from app.services.indexing_service import chunk_blocks

SAMPLE_DIR = Path(__file__).resolve().parents[3] / "data" / "samples"


@pytest.mark.asyncio
async def test_markdown_parser_keeps_heading_path() -> None:
    """Markdown 解析应保留标题层级到 heading_path。"""
    parser = MarkdownParser()
    blocks = await parser.parse(SAMPLE_DIR / "员工手册.md")
    assert len(blocks) > 0
    assert any("年假" in (block.heading_path or "") for block in blocks)


@pytest.mark.asyncio
async def test_sample_documents_cover_supported_formats() -> None:
    """样本文档应覆盖 md/docx/txt/pdf，并保留可引用定位信息。"""
    md_blocks = await MarkdownParser().parse(SAMPLE_DIR / "信息安全与账号权限.md")
    assert any("账号开通" in (block.heading_path or "") for block in md_blocks)

    docx_blocks = await DocxParser().parse(SAMPLE_DIR / "报销制度.docx")
    assert any("发票要求" in (block.heading_path or "") for block in docx_blocks)
    assert any("费用明细清单" in block.text for block in docx_blocks)

    txt_blocks = await TxtParser().parse(SAMPLE_DIR / "休假与福利政策.txt")
    assert any("病假" in block.text for block in txt_blocks)
    assert any(block.paragraph_index is not None for block in txt_blocks)

    pdf_blocks = await PdfParser().parse(SAMPLE_DIR / "差旅与报销标准.pdf")
    assert any("餐饮补贴" in block.text for block in pdf_blocks)
    assert any(block.page_number is not None for block in pdf_blocks)


def test_chunk_blocks_splits_long_text() -> None:
    """超过 chunk_size 的文本应被切分，并递增 chunk_index。"""
    blocks = [ParsedBlock(text="A" * 900, paragraph_index=0)]
    chunks = chunk_blocks(blocks, chunk_size=800, overlap=120)
    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


def test_chunk_blocks_keeps_short_text() -> None:
    """短文本应保持单个块。"""
    blocks = [ParsedBlock(text="短文本", paragraph_index=0)]
    chunks = chunk_blocks(blocks, chunk_size=800, overlap=120)
    assert len(chunks) == 1
