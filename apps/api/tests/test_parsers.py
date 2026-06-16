"""文档解析与分块测试（不依赖真实 API Key / 数据库）。"""
from pathlib import Path

import pytest

from app.parsers.base import ParsedBlock
from app.parsers.markdown_parser import MarkdownParser
from app.services.indexing_service import chunk_blocks

SAMPLE_DIR = Path(__file__).resolve().parents[3] / "data" / "samples"


@pytest.mark.asyncio
async def test_markdown_parser_keeps_heading_path() -> None:
    """Markdown 解析应保留标题层级到 heading_path。"""
    parser = MarkdownParser()
    blocks = await parser.parse(SAMPLE_DIR / "员工手册.md")
    assert len(blocks) > 0
    # 年假相关块应带 heading_path（含"年假"）
    assert any("年假" in (b.heading_path or "") for b in blocks)


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
