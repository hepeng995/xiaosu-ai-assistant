"""Mock LLM 工具调用测试（不依赖真实 API Key / 数据库）。

验证：无 key 时走 mock，且工具选择逻辑（模拟 LLM）能正确选工具 + 工具 Schema 合法。
真实模式下工具选择由 LLM 按 Tool Schema 自主决定（function calling）。
"""
import pytest

from app.agents.prompts import SENSITIVE_KEYWORDS
from app.core.config import settings
from app.llm.openai_compatible import llm_service
from app.tools.attendance_tool import AttendanceTool
from app.tools.employee_tool import EmployeeTool
from app.tools.orders_tool import OrdersTool
from app.tools.time_tool import CurrentTimeTool


def test_rag_score_threshold_default_matches_spec() -> None:
    """默认 RAG 阈值应与笔试题/开发规范一致。"""
    assert settings.RAG_SCORE_THRESHOLD == 0.72


def test_llm_uses_mock_without_key() -> None:
    """key=replace_me 时应启用 mock 模式（不调真实 API）。"""
    assert llm_service.use_mock is True


def test_mock_plan_selects_employee_tool() -> None:
    """问员工部门 → mock 选 get_employee。"""
    calls = llm_service._mock_plan("员工 001 是哪个部门的？")
    names = [c["function"]["name"] for c in calls]
    assert "get_employee" in names


def test_mock_plan_selects_orders_tool() -> None:
    """问订单 → mock 选 get_orders。"""
    calls = llm_service._mock_plan("上周一共多少订单？")
    names = [c["function"]["name"] for c in calls]
    assert "get_orders" in names


def test_mock_plan_sales_target_uses_knowledge_base() -> None:
    """问未来销售目标 → mock 应检索知识库，不能误走订单工具。"""
    calls = llm_service._mock_plan("2030 年的销售目标是多少？")
    names = [c["function"]["name"] for c in calls]
    assert names == ["search_knowledge_base"]


def test_salary_detail_keywords_are_sensitive() -> None:
    """工资明细类问题应走隐私拒答前置。"""
    assert "工资明细" in SENSITIVE_KEYWORDS
    assert "薪资明细" in SENSITIVE_KEYWORDS
    assert "所有员工工资" in SENSITIVE_KEYWORDS


def test_mock_plan_selects_time_tool() -> None:
    """问时间 → mock 选 get_current_time。"""
    calls = llm_service._mock_plan("现在几点？")
    names = [c["function"]["name"] for c in calls]
    assert "get_current_time" in names


def test_tool_schemas_are_valid() -> None:
    """工具 Schema 应符合 OpenAI function-calling 格式。"""
    for tool in (EmployeeTool(), AttendanceTool(), OrdersTool(), CurrentTimeTool()):
        schema = tool.schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == tool.name
        assert "parameters" in schema["function"]


@pytest.mark.asyncio
async def test_time_tool_runs() -> None:
    """当前时间工具应返回有效时间数据（不依赖外部 API）。"""
    result = await CurrentTimeTool().run({"timezone": "Asia/Shanghai"})
    assert result.success
    assert isinstance(result.data, dict)
    assert "datetime" in result.data
