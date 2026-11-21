"""P-052 C 组：合规报告与速率台账（C1-C10）。"""

from __future__ import annotations

from core.compliance import (
    AUDIT_RETENTION_YEARS_DEFAULT,
    AUDIT_RETENTION_YEARS_MAX,
    ProgrammaticTradingReport,
    RateLedger,
    RateLimitConfig,
    cancel_ratio,
    check_rate,
    day_key,
    record,
)

DAY1 = 1_700_000_000.0  # 2023-11-14 UTC
DAY2 = DAY1 + 86_400.0


def _report(**overrides) -> ProgrammaticTradingReport:
    base = dict(
        investor_name="张三",
        account_code="A123",
        member="某券商",
        strategy_type="趋势",
        execution_mode="自动",
        software_name="ft-v3",
    )
    base.update(overrides)
    return ProgrammaticTradingReport(**base)


def test_c1_missing_required_all():
    """C1：必填全缺 → 6 项。"""
    report = ProgrammaticTradingReport(investor_name="", account_code="", member="")
    missing = report.missing_required()
    assert len(missing) == 6
    assert set(missing) == {
        "investor_name",
        "account_code",
        "member",
        "strategy_type",
        "execution_mode",
        "software_name",
    }


def test_c2_missing_required_complete():
    """C2：必填齐全 → 空。"""
    assert _report().missing_required() == ()


def test_c3_whitespace_counts_as_missing():
    """C3：纯空白视为缺失。"""
    missing = _report(investor_name="   ", software_name="\t").missing_required()
    assert missing == ("investor_name", "software_name")


def test_c4_same_second_blocked():
    """C4（F-I2）：同秒第二笔被阻断。"""
    cfg = RateLimitConfig(max_per_second=1, max_per_day=0)
    ledger = record(RateLedger(), DAY1, is_cancel=False)
    allowed, reason = check_rate(ledger, DAY1, cfg)
    assert allowed is False
    assert reason == "per_second"


def test_c5_next_second_allowed():
    """C5：跨秒放行（无 {sec-1,sec} 滑窗互斥）。"""
    cfg = RateLimitConfig(max_per_second=1, max_per_day=0)
    ledger = record(RateLedger(), DAY1, is_cancel=False)
    allowed, reason = check_rate(ledger, DAY1 + 1.0, cfg)
    assert allowed is True
    assert reason == ""


def test_c6_daily_limit():
    """C6：日累计达上限阻断。"""
    cfg = RateLimitConfig(max_per_second=0, max_per_day=2)
    ledger = RateLedger()
    ledger = record(ledger, DAY1, is_cancel=False)
    ledger = record(ledger, DAY1 + 10.0, is_cancel=False)
    allowed, reason = check_rate(ledger, DAY1 + 20.0, cfg)
    assert allowed is False
    assert reason == "per_day"
    assert ledger.daily_orders == 2


def test_c7_cross_day_reset():
    """C7（F-D10）：跨日重置日累计。"""
    ledger = record(RateLedger(), DAY1, is_cancel=False)
    assert ledger.daily_orders == 1
    ledger = record(ledger, DAY2, is_cancel=False)
    assert ledger.date == day_key(DAY2)
    assert ledger.daily_orders == 1


def test_c8_cancel_ratio_insufficient_samples():
    """C8：样本不足不判撤单率。"""
    cfg = RateLimitConfig(max_per_second=0, max_per_day=0, max_cancel_ratio=0.5)
    ledger = RateLedger()
    for i in range(5):
        ledger = record(ledger, DAY1 + i, is_cancel=False)
    for i in range(10):
        ledger = record(ledger, DAY1 + 100 + i, is_cancel=True)
    assert cancel_ratio(ledger) == 2.0
    allowed, reason = check_rate(ledger, DAY1 + 500.0, cfg)
    assert allowed is True
    assert reason == ""


def test_c9_cancel_ratio_exceeded():
    """C9：样本充足且撤单率超限 → 阻断。"""
    cfg = RateLimitConfig(
        max_per_second=0, max_per_day=0, max_cancel_ratio=0.5, min_cancel_samples=20
    )
    ledger = RateLedger()
    for i in range(20):
        ledger = record(ledger, DAY1 + i, is_cancel=False)
    for i in range(15):
        ledger = record(ledger, DAY1 + 100 + i, is_cancel=True)
    allowed, reason = check_rate(ledger, DAY1 + 500.0, cfg)
    assert allowed is False
    assert reason == "cancel_ratio"


def test_c10_retention_constants():
    """C10：保留期常量 5 / 20。"""
    assert AUDIT_RETENTION_YEARS_DEFAULT == 5
    assert AUDIT_RETENTION_YEARS_MAX == 20
