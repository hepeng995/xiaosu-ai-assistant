"""纯问候语识别 + 小苏角色化打招呼。

属于开发规范 10.1 明确允许的「基础安全前置」（与空问题拒绝、超长截断、敏感词过滤同类），
**不参与工具选择**——仅拦截「纯问候短消息」，跳过 Agent 直接回复，省 token、IM/Web 即时响应。

含实质内容（如「你好，报销流程？」「早期项目」「早晨几点上班」）一律放行，
由 Agent 按 Tool Schema 自主决定工具/RAG，确保核心能力不受影响。
"""

import random
import re
from datetime import datetime

# 纯问候词：整串匹配使用，避免误伤含实质内容的消息。
# 排在前的长词优先匹配（alternation 按出现顺序），「早安/早上好」不会被「早」吃掉。
_GREETING_WORDS: tuple[str, ...] = (
    "你们好",
    "大家早上好",
    "早上好",
    "早安",
    "上午好",
    "中午好",
    "午安",
    "下午好",
    "晚上好",
    "晚安",
    "你好",
    "您好",
    "哈喽",
    "哈罗",
    "在不在",
    "有人在吗",
    "有人吗",
    "在吗",
    "在么",
    "嗨",
    "嘿",
    "hello",
    "hey",
    "hi",
)

# 允许的语气/标点尾缀：你好啊 / 早呀 / 嗨～ / 在吗？
_TAIL = r"[啊呀哟呐哒哈哇哦嗯~！!。.，,～?？\s]*"

_GREETING_PATTERN = re.compile(
    r"^\s*(?:" + "|".join(_GREETING_WORDS) + r")" + _TAIL + r"$",
    re.IGNORECASE,
)

# 纯问候长度上限：超过此长度几乎必然带实质内容，直接放行给 Agent。
_MAX_GREETING_LEN = 12

# 时段 → 小苏式招呼模板池。语气遵循 SYSTEM_PROMPT：亲切 + 干练，自称「小苏」，克制 emoji。
_GREETING_TEMPLATES: dict[str, tuple[str, ...]] = {
    "morning": (
        "早上好呀～我是小苏，今天有什么可以帮你？",
        "早安～小苏在的，工作上的事尽管问我。",
        "早上好！新的一天，小苏随时待命。",
    ),
    "noon": (
        "中午好～午休一下，下午继续。需要查什么可以问小苏。",
        "午安～我是小苏，有事随时叫我。",
    ),
    "afternoon": (
        "下午好～我是小苏，有什么可以帮你？",
        "嗨～小苏在的，工作问题尽管问。",
        "你好呀～我是小苏，随时为你服务。",
    ),
    "evening": (
        "晚上好～我是小苏，加完班别太累，有事可以问我。",
        "晚上好呀～小苏在的，有什么需要帮忙的？",
    ),
    "late_night": (
        "这么晚了还在忙？小苏陪你～有事可以问，但别熬太晚哦。",
        "夜深了～小苏还在，工作的事可以问，记得早点休息。",
    ),
}


def is_greeting(message: str) -> bool:
    """判定是否为纯问候语。

    保守原则：长度超过 ``_MAX_GREETING_LEN`` 直接返回 False；仅匹配「问候词 + 语气/标点」整串。
    """
    if not message or len(message) > _MAX_GREETING_LEN:
        return False
    return bool(_GREETING_PATTERN.match(message.strip()))


def _period(hour: int) -> str:
    """0-23 小时 → 时段 key（基于服务器本地时间）。"""
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 14:
        return "noon"
    if 14 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 23:
        return "evening"
    return "late_night"


def build_greeting_reply(now: datetime | None = None) -> str:
    """根据时段随机挑选一条小苏式问候（测试可注入 ``now`` 固定时段）。"""
    hour = (now or datetime.now()).hour
    return random.choice(_GREETING_TEMPLATES[_period(hour)])
