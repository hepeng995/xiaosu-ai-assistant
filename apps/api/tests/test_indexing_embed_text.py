"""indexing_service embedding 文本构建测试。

验证 embedding 文本纳入 heading_path，让 FAQ 类 chunk（heading=问题，content=答案）
更易被语义命中——修复"2030 销售目标"无法命中"公司未来销售目标是多少？"FAQ 的问题。
"""

from app.services.indexing_service import _ChunkData, _embed_text


def test_embed_text_includes_heading() -> None:
    """有 heading 时 embedding 文本应 = heading + content（heading 前置）。"""
    chunk = _ChunkData(
        content="涉及未公开的经营规划，不在知识库披露。",
        heading_path="常见问题 FAQ > 合规与其他类 > 公司未来销售目标是多少？",
        page_number=None,
        paragraph_index=55,
        chunk_index=0,
    )
    text = _embed_text(chunk)
    assert "公司未来销售目标是多少" in text
    assert "涉及未公开的经营规划" in text
    # heading 语义信号前置（与 query 相似度更高的部分排在前面）
    assert text.index("公司未来销售目标") < text.index("涉及未公开")


def test_embed_text_without_heading() -> None:
    """无 heading 时 embedding 文本应 = content（兼容无标题 chunk）。"""
    chunk = _ChunkData(
        content="正文内容",
        heading_path=None,
        page_number=None,
        paragraph_index=None,
        chunk_index=0,
    )
    assert _embed_text(chunk) == "正文内容"


def test_embed_text_empty_heading() -> None:
    """heading 为空字符串时应回退到 content（防御空标题）。"""
    chunk = _ChunkData(
        content="正文",
        heading_path="",
        page_number=None,
        paragraph_index=None,
        chunk_index=0,
    )
    assert _embed_text(chunk) == "正文"
