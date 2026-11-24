"""P-060a 再平衡触发器单元测试（T-A11..A15）。

对应 [IMPL_p060a §4.3](../../docs/IMPL_p060a_implementation.md)：零生产改动；
周/月「最后交易日」用独立分组口径对拍（X19 zipline last-trading-day）。
D-03：条件触发回撤用上期净值（非历史峰值），仅锁定现状。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.config import RebalanceConfig
from core.rebalance import (
    BaseTrigger,
    ConditionalTrigger,
    FixedIntervalTrigger,
    HybridTrigger,
    RebalanceCalendar,
    build_trigger,
)

DATES_20 = pd.bdate_range("2024-01-01", periods=20)
DATES_Q1 = pd.bdate_range("2024-01-01", "2024-03-29")


def last_of_month(dates: pd.DatetimeIndex) -> set[pd.Timestamp]:
    """独立口径：按 (年, 月) 分组取每组最后一根 bar。"""
    series = pd.Series(dates, index=dates)
    return set(series.groupby([dates.year, dates.month]).last())


def last_of_week(dates: pd.DatetimeIndex) -> set[pd.Timestamp]:
    """独立口径：按 ISO (年, 周) 分组取每组最后一根 bar。"""
    iso = dates.isocalendar()
    series = pd.Series(dates, index=dates)
    return set(series.groupby([iso.year.to_numpy(), iso.week.to_numpy()]).last())


# ---------------------------------------------------------------------------
# T-A11 固定间隔四频率
# ---------------------------------------------------------------------------


def test_p060a_a11a_daily_triggers_every_date():
    """T-A11a | oracle=closed-form：daily 全部 20 日触发"""
    trig = FixedIntervalTrigger(RebalanceConfig(frequency="daily"), DATES_20)

    assert all(trig.should_trigger(d) for d in DATES_20)


def test_p060a_a11b_weekly_triggers_last_trading_day():
    """T-A11b | oracle=manual-calendar：每周最后一个交易日（X19 口径）"""
    trig = FixedIntervalTrigger(RebalanceConfig(frequency="weekly"), DATES_20)
    got = {d for d in DATES_20 if trig.should_trigger(d)}

    assert got == last_of_week(DATES_20)
    assert got == {
        pd.Timestamp("2024-01-05"),
        pd.Timestamp("2024-01-12"),
        pd.Timestamp("2024-01-19"),
        pd.Timestamp("2024-01-26"),
    }


def test_p060a_a11c_monthly_triggers_month_end():
    """T-A11c | oracle=manual-calendar：每月最后一个交易日 1/31、2/29、3/29"""
    trig = FixedIntervalTrigger(RebalanceConfig(frequency="monthly"), DATES_Q1)
    got = {d for d in DATES_Q1 if trig.should_trigger(d)}

    assert got == last_of_month(DATES_Q1)
    assert got == {
        pd.Timestamp("2024-01-31"),
        pd.Timestamp("2024-02-29"),
        pd.Timestamp("2024-03-29"),
    }


def test_p060a_a11d_n_days_triggers_stride():
    """T-A11d | oracle=closed-form：N_days=5 → 索引 0/5/10/15"""
    trig = FixedIntervalTrigger(RebalanceConfig(frequency="N_days", n_days=5), DATES_20)
    got = [d for d in DATES_20 if trig.should_trigger(d)]

    assert got == [DATES_20[i] for i in (0, 5, 10, 15)]


def test_p060a_a11e_empty_and_single_date_boundaries():
    """T-A11e | oracle=boundary：空索引 → 无触发；单日 daily → 触发"""
    empty = pd.DatetimeIndex([])
    assert (
        FixedIntervalTrigger(RebalanceConfig(frequency="weekly"), empty)._rebalance_dates == set()
    )

    single = pd.DatetimeIndex([pd.Timestamp("2024-01-02")])
    trig = FixedIntervalTrigger(RebalanceConfig(frequency="daily"), single)
    assert trig.should_trigger(single[0]) is True


# ---------------------------------------------------------------------------
# T-A12 条件触发
# ---------------------------------------------------------------------------


def test_p060a_a12a_signal_change_triggers():
    """T-A12a | oracle=closed-form：L2=√2 ≥ 0.1 → 触发"""
    trig = ConditionalTrigger(RebalanceConfig(signal_change_threshold=0.1))
    day0, day1 = DATES_20[0], DATES_20[1]
    sig0 = pd.Series([1.0, 0.0], index=["A", "B"])

    assert trig.should_trigger(day0, signal=sig0) is False
    assert trig.should_trigger(day1, signal=pd.Series([0.0, 1.0], index=["A", "B"])) is True


def test_p060a_a12b_first_call_updates_state_without_trigger():
    """T-A12b | oracle=state：首次调用不触发，但 last_signal / last_value 被写入"""
    trig = ConditionalTrigger(RebalanceConfig(signal_change_threshold=0.1))
    sig = pd.Series([1.0, 0.0], index=["A", "B"])

    assert trig.should_trigger(DATES_20[0], signal=sig, portfolio_value=100.0) is False
    assert trig._last_signal is not None
    assert trig._last_portfolio_value == pytest.approx(100.0)


def test_p060a_a12c_drawdown_triggers_against_previous_value():
    """T-A12c | oracle=closed-form：100→94（6%）触发；100→96（4%）不触发（D-03 上期净值口径）"""
    cfg = RebalanceConfig(drawdown_trigger=0.05)
    day0, day1 = DATES_20[0], DATES_20[1]

    hit = ConditionalTrigger(cfg)
    hit.should_trigger(day0, portfolio_value=100.0)
    assert hit.should_trigger(day1, portfolio_value=94.0) is True

    miss = ConditionalTrigger(cfg)
    miss.should_trigger(day0, portfolio_value=100.0)
    assert miss.should_trigger(day1, portfolio_value=96.0) is False


def test_p060a_a12d_volatility_triggers_on_first_call():
    """T-A12d | oracle=closed-form：波动率无需前值；0.25≥0.2 触发、0.15 不触发"""
    cfg = RebalanceConfig(volatility_trigger=0.2)
    assert ConditionalTrigger(cfg).should_trigger(DATES_20[0], volatility=0.25) is True
    assert ConditionalTrigger(cfg).should_trigger(DATES_20[0], volatility=0.15) is False


def test_p060a_a12e_signal_branch_is_evaluated_before_others(monkeypatch):
    """T-A12e | oracle=priority：三条件同时满足时先走信号分支（异常可穿出）"""
    cfg = RebalanceConfig(signal_change_threshold=0.0, drawdown_trigger=0.0, volatility_trigger=0.0)
    trig = ConditionalTrigger(cfg)
    sig = pd.Series([1.0, 0.0], index=["A", "B"])
    trig.should_trigger(DATES_20[0], signal=sig, portfolio_value=100.0, volatility=0.0)

    def boom(*args, **kwargs):
        raise RuntimeError("signal path first")

    monkeypatch.setattr(trig, "_calculate_signal_change", boom)
    with pytest.raises(RuntimeError, match="signal path first"):
        trig.should_trigger(
            DATES_20[1],
            signal=pd.Series([0.0, 1.0], index=["A", "B"]),
            portfolio_value=90.0,
            volatility=0.5,
        )


# ---------------------------------------------------------------------------
# T-A13 信号变化幅度
# ---------------------------------------------------------------------------


def test_p060a_a13_signal_change_closed_form():
    """T-A13 | oracle=closed-form：无交集→1.0；相同→0；正交→√2"""
    trig = ConditionalTrigger(RebalanceConfig())

    assert trig._calculate_signal_change(
        pd.Series([1.0], index=["A"]), pd.Series([1.0], index=["B"])
    ) == pytest.approx(1.0)
    same = pd.Series([0.4, 0.6], index=["A", "B"])
    assert trig._calculate_signal_change(same, same) == pytest.approx(0.0)
    assert trig._calculate_signal_change(
        pd.Series([1.0, 0.0], index=["A", "B"]),
        pd.Series([0.0, 1.0], index=["A", "B"]),
    ) == pytest.approx(np.sqrt(2.0))


# ---------------------------------------------------------------------------
# T-A14 混合触发
# ---------------------------------------------------------------------------


def test_p060a_a14a_min_days_suppresses_trigger():
    """T-A14a | oracle=state：距上次 1 天 < min_days=5 → 抑制（即使 fixed 命中）"""
    cfg = RebalanceConfig(method="hybrid", frequency="daily", hybrid_min_days=5)
    trig = HybridTrigger(cfg, DATES_20)

    assert trig.should_trigger(DATES_20[0]) is True
    assert trig.should_trigger(DATES_20[1]) is False
    assert trig.should_trigger(DATES_20[5]) is True


def test_p060a_a14b_fixed_hit_records_last_date():
    """T-A14b | oracle=state：fixed 命中 → True 且记录上次再平衡日"""
    cfg = RebalanceConfig(method="hybrid", frequency="daily")
    trig = HybridTrigger(cfg, DATES_20)

    assert trig.should_trigger(DATES_20[0]) is True
    assert trig._last_rebalance_date == DATES_20[0]


def test_p060a_a14c_no_last_skips_interval_check_and_uses_conditional():
    """T-A14c | oracle=state：last=None 跳过 min_days，条件回撤 10% 触发"""
    cfg = RebalanceConfig(
        method="hybrid", frequency="monthly", drawdown_trigger=0.05, hybrid_min_days=5
    )
    trig = HybridTrigger(cfg, DATES_Q1)
    day0 = pd.Timestamp("2024-01-02")
    day1 = pd.Timestamp("2024-01-03")

    assert trig.should_trigger(day0, portfolio_value=100.0) is False
    assert trig.should_trigger(day1, portfolio_value=90.0) is True


def test_p060a_a14d_max_days_fallback_triggers():
    """T-A14d | oracle=state：31 天 ≥ max_days=30 且 fixed/conditional 均未命中 → 兜底触发"""
    cfg = RebalanceConfig(
        method="hybrid",
        frequency="monthly",
        volatility_trigger=0.2,
        hybrid_min_days=5,
        hybrid_max_days=30,
    )
    trig = HybridTrigger(cfg, DATES_Q1)
    day0 = pd.Timestamp("2024-01-02")
    day1 = pd.Timestamp("2024-02-02")

    assert trig.should_trigger(day0, volatility=0.3) is True
    assert trig.should_trigger(day1, volatility=0.0) is True


# ---------------------------------------------------------------------------
# T-A15 工厂与日历
# ---------------------------------------------------------------------------


def test_p060a_a15_build_trigger_fallback_and_calendar_queries():
    """T-A15 | oracle=boundary：未知 method → FixedInterval；日历 dates/stats/next 正确"""
    trig = build_trigger(RebalanceConfig(method="unknown"), DATES_Q1)
    assert isinstance(trig, FixedIntervalTrigger)

    assert isinstance(
        build_trigger(RebalanceConfig(method="fixed"), DATES_Q1), FixedIntervalTrigger
    )
    assert isinstance(
        build_trigger(RebalanceConfig(method="conditional"), DATES_Q1), ConditionalTrigger
    )
    assert isinstance(build_trigger(RebalanceConfig(method="hybrid"), DATES_Q1), HybridTrigger)

    cal = RebalanceCalendar(
        FixedIntervalTrigger(RebalanceConfig(frequency="monthly"), DATES_Q1), DATES_Q1
    )
    dates = cal.get_rebalance_dates()
    assert len(dates) == 3
    assert cal.is_rebalance_date(dates[0]) is True
    assert cal.get_next_rebalance_date(dates[0]) == dates[1]
    assert cal.get_next_rebalance_date(dates[-1]) is None
    assert cal.get_rebalance_stats()["total_rebalances"] == 3

    empty_cal = RebalanceCalendar(
        FixedIntervalTrigger(RebalanceConfig(frequency="daily"), pd.DatetimeIndex([])),
        pd.DatetimeIndex([]),
    )
    assert empty_cal.get_rebalance_stats() == {
        "total_rebalances": 0,
        "rebalance_frequency": 0,
        "avg_interval_days": 0,
    }

    with pytest.raises(NotImplementedError):
        BaseTrigger(RebalanceConfig()).should_trigger(DATES_Q1[0])


# ---------------------------------------------------------------------------
# T-A11f 与独立日历口径对拍（原 T-A16，避免与 tracker T-A16 重号，见 F-S7-P060a-1）
# ---------------------------------------------------------------------------


def test_p060a_a11f_weekly_monthly_match_independent_calendar():
    """T-A11f | oracle=cross-check：weekly/monthly 与 pandas 独立分组口径逐日相等"""
    weekly = FixedIntervalTrigger(RebalanceConfig(frequency="weekly"), DATES_Q1)
    got_weekly = {d for d in DATES_Q1 if weekly.should_trigger(d)}
    assert got_weekly == last_of_week(DATES_Q1)

    monthly = FixedIntervalTrigger(RebalanceConfig(frequency="monthly"), DATES_Q1)
    got_monthly = {d for d in DATES_Q1 if monthly.should_trigger(d)}
    assert got_monthly == last_of_month(DATES_Q1)
