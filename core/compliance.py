"""合规报告与速率台账（纯计算，I1）。

S4：程序化交易报告 schema（细则第九条 6 类 + 第三十四条 3 项）、异常交易枚举、
速率台账（默认 1 笔/秒、1000 笔/日 = D2 项目内部默认值，非监管要求）。
S6 辅助：``build_audit_payload`` 强制注入 operator/time_source。

本模块**不 import 任何项目内模块**（C-8），审计常量统一在 ``core.event_log``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AbnormalTradeType(str, Enum):
    """异常交易类型（细则第十八条四类 + 科创板补充四类）。"""

    INSTANT_ORDER_RATE = "instant_order_rate"
    FREQUENT_INSTANT_CANCEL = "frequent_instant_cancel"
    FREQUENT_PUSH_PULL = "frequent_push_pull"
    SHORT_TERM_LARGE_TRADE = "short_term_large_trade"
    FALSE_DECLARATION = "false_declaration"
    MAINTAIN_LIMIT_PRICE = "maintain_limit_price"
    SELF_TRADE = "self_trade"
    ABNORMAL_DECLARATION_RATE = "abnormal_declaration_rate"


@dataclass(frozen=True)
class ProgrammaticTradingReport:
    """程序化交易报告（第九条六类 + 第三十四条三项）。"""

    investor_name: str
    account_code: str
    member: str
    product_manager: str = ""
    capital_scale: float = 0.0
    capital_source: str = ""
    leverage_scale: float = 0.0
    leverage_source: str = ""
    leverage_ratio: float = 0.0
    strategy_type: str = ""
    strategy_desc: str = ""
    execution_mode: str = ""
    max_order_rate: int = 0
    max_daily_orders: int = 0
    software_name: str = ""
    software_version: str = ""
    developer: str = ""
    contact: str = ""
    contact_info: str = ""
    server_location: str | None = None
    system_test_report: str | None = None
    emergency_plan: str | None = None

    def missing_required(self) -> tuple[str, ...]:
        """第九条最小必填集为空/纯空白 → 返回字段名（F-D14）。"""
        required = (
            "investor_name",
            "account_code",
            "member",
            "strategy_type",
            "execution_mode",
            "software_name",
        )
        missing: list[str] = []
        for name in required:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                missing.append(name)
        return tuple(missing)


@dataclass(frozen=True)
class RateLimitConfig:
    """速率上限（D2 内部默认值，可配置）。"""

    max_per_second: int = 1
    max_per_day: int = 1000
    max_cancel_ratio: float | None = None
    min_cancel_samples: int = 20


@dataclass(frozen=True)
class RateLedger:
    """速率台账（不可变；由 ``record`` 推进）。"""

    date: str = ""
    per_second: dict[int, int] = field(default_factory=dict)
    daily_orders: int = 0
    daily_cancels: int = 0


def day_key(ts: float) -> str:
    """UTC 日键（不取 now，I1）。"""
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def record(ledger: RateLedger, ts: float, is_cancel: bool) -> RateLedger:
    """记录一次委托申报；跨日重置日累计（C-5）。"""
    day = day_key(ts)
    base = ledger if ledger.date == day else RateLedger(date=day)
    sec = int(ts)
    per_second = {k: v for k, v in base.per_second.items() if k >= sec - 1}
    per_second[sec] = per_second.get(sec, 0) + 1
    return RateLedger(
        date=day,
        per_second=per_second,
        daily_orders=base.daily_orders + (0 if is_cancel else 1),
        daily_cancels=base.daily_cancels + (1 if is_cancel else 0),
    )


def cancel_ratio(ledger: RateLedger) -> float:
    """撤单率 = 撤单数 / 新委托数；分母 0 → 0.0。"""
    if ledger.daily_orders <= 0:
        return 0.0
    return ledger.daily_cancels / ledger.daily_orders


def check_rate(ledger: RateLedger, ts: float, cfg: RateLimitConfig) -> tuple[bool, str]:
    """返回 ``(allowed, reason)``；reason ∈ {"", "per_second", "per_day", "cancel_ratio"}。

    调用方须先 check 后 record（C-6），否则本次委托自阻。
    """
    if cfg.max_per_second > 0:
        sec = int(ts)
        if ledger.per_second.get(sec, 0) >= cfg.max_per_second:  # F-I2：只查当前秒桶
            return False, "per_second"
    if cfg.max_per_day > 0 and ledger.daily_orders >= cfg.max_per_day:
        return False, "per_day"
    if cfg.max_cancel_ratio is not None and ledger.daily_orders >= cfg.min_cancel_samples:
        if cancel_ratio(ledger) > cfg.max_cancel_ratio:
            return False, "cancel_ratio"
    return True, ""


def ledger_to_dict(ledger: RateLedger) -> dict[str, Any]:
    """序列化（键转字符串，JSON 友好；D-3）。"""
    return {
        "date": ledger.date,
        "per_second": {str(k): v for k, v in ledger.per_second.items()},
        "daily_orders": ledger.daily_orders,
        "daily_cancels": ledger.daily_cancels,
    }


def ledger_from_dict(data: dict[str, Any]) -> RateLedger:
    """反序列化；非法值抛 ``ValueError``/``TypeError`` 由调用方容错。"""
    return RateLedger(
        date=str(data.get("date", "")),
        per_second={int(k): int(v) for k, v in dict(data.get("per_second", {})).items()},
        daily_orders=int(data.get("daily_orders", 0)),
        daily_cancels=int(data.get("daily_cancels", 0)),
    )


def build_audit_payload(*, operator: str, time_source: str, **fields: Any) -> dict[str, Any]:
    """强制注入 operator/time_source；重复传入 → ``ValueError``（C-9）。"""
    if "operator" in fields or "time_source" in fields:
        raise ValueError("operator/time_source 由 build_audit_payload 强制注入，不得重复传入")
    payload: dict[str, Any] = {"operator": operator, "time_source": time_source}
    payload.update(fields)
    return payload


AUDIT_RETENTION_YEARS_DEFAULT = 5
AUDIT_RETENTION_YEARS_MAX = 20
