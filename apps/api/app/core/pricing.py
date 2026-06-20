"""LLM 成本估算：按每百万 token 单价估算美元成本（未配置单价时返回 0）。

降级语义：单价为 0（未在 .env 配置）时返回 Decimal(0)，保证「未配置即不估算」，
不破坏 mock/无单价流程。Message.estimated_cost 落库精度与 Numeric(10,6) 对齐。
"""

from decimal import Decimal

from app.core.config import settings

_PER_M = Decimal("1000000")
_QUANTIZE = Decimal("0.000001")


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> Decimal:
    """按 input/output 单价估算单次对话成本（美元）。

    Args:
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。

    Returns:
        估算成本（Decimal，6 位精度）；单价为 0 时返回 Decimal("0.000000")。
    """
    prompt_tokens = max(int(prompt_tokens or 0), 0)
    completion_tokens = max(int(completion_tokens or 0), 0)
    cost = (
        Decimal(prompt_tokens) * Decimal(str(settings.LLM_PRICE_INPUT_PER_M))
        + Decimal(completion_tokens) * Decimal(str(settings.LLM_PRICE_OUTPUT_PER_M))
    ) / _PER_M
    return cost.quantize(_QUANTIZE)
