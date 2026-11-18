"""P-045：择时原语与止损状态机（V1-V8 + G1/G2）。

红态设计：核心符号一律函数内导入 → 逐用例失败而非收集期 error。
G1/G2 为**规格锁定** golden（期望值由 DESIGN/IMPL 手工推导，非实现录制）。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DATES = pd.bdate_range("2024-01-02", periods=5)
GOLDEN_DIR = Path(__file__).parent / "golden" / "p045"


def test_v1_crossed_above_below():
    """S2 / D3：交叉检测与 NaN 语义。"""
    from core.timing import crossed_above, crossed_below

    series = pd.Series([np.nan, 1.0, 0.5, 2.0, np.nan, 3.0])
    assert crossed_above(series, 1.0).tolist() == [False, False, False, True, False, False]
    assert crossed_below(series, 1.0).tolist() == [False, False, True, False, False, False]

    flat = pd.Series([1.0, 1.0, 1.0])
    assert not crossed_above(flat, 1.0).any()
    assert not crossed_below(flat, 1.0).any()


def test_v2_conflicts_and_holdings():
    """S3 / D4：同日冲突 exit 优先；持仓状态机 ffill 与重建。"""
    from core.timing import SignalSet, holdings_from_signals, resolve_conflicts

    codes = ["A", "B"]
    entries = pd.DataFrame(False, index=DATES, columns=codes)
    exits = pd.DataFrame(False, index=DATES, columns=codes)
    entries.iloc[0, 0] = True  # A: d1 entry
    exits.iloc[3, 0] = True  # A: d4 exit
    entries.iloc[4, 0] = True  # A: d5 re-entry
    entries.iloc[1, 1] = True  # B: d2 entry
    exits.iloc[1, 1] = True  # B: 同日 entry+exit

    resolved = resolve_conflicts(SignalSet(entries_long=entries, exits_long=exits))
    assert not resolved.entries_long.iloc[1, 1]

    holdings = holdings_from_signals(SignalSet(entries_long=entries, exits_long=exits))
    assert holdings["A"].tolist() == [True, True, True, False, True]
    assert holdings["B"].tolist() == [False, False, False, False, False]

    with pytest.raises(ValueError, match="index"):
        SignalSet(entries_long=entries, exits_long=exits.iloc[:-1])


def test_v3_weights_from_holdings():
    """S4 / D4：等权、空持仓全 0、行和 ∈ {0,1}、非法 mode。"""
    from core.timing import weights_from_holdings

    holdings = pd.DataFrame(
        [[True, True, False], [False, False, False], [True, False, False]],
        index=DATES[:3],
        columns=["A", "B", "C"],
    )
    weights = weights_from_holdings(holdings)
    assert weights.iloc[0].tolist() == [0.5, 0.5, 0.0]
    assert weights.iloc[1].tolist() == [0.0, 0.0, 0.0]
    assert weights.iloc[2].tolist() == [1.0, 0.0, 0.0]
    assert set(weights.sum(axis=1).round(12)) <= {0.0, 1.0}

    with pytest.raises(ValueError, match="未知权重模式"):
        weights_from_holdings(holdings, mode="risk_parity")


def test_v4_apply_timing_gate():
    """S4 / D4：gate 归零且**不重归一**（F-S4-P045-1 reindex keyword）。"""
    from core.timing import apply_timing

    targets = pd.DataFrame([[0.5, 0.5], [0.6, 0.0]], index=DATES[:2], columns=["A", "B"])
    holdings = pd.DataFrame(True, index=DATES[:2], columns=["A", "B"])
    holdings.iloc[1, 1] = False

    gated = apply_timing(targets, holdings)
    assert gated.sum(axis=1).tolist() == [1.0, 0.6]
    assert gated.iloc[1, 0] == 0.6


def test_v5_fixed_stop_loss():
    """S5-S8 / D6：建仓 state、gap 触发、盘中触发、未触发。"""
    from core.stops import StopBar, StopConfig, StopEngine, StopState

    engine = StopEngine(StopConfig(stop_loss_pct=0.10))
    state, decision = engine.update(None, StopBar(DATES[0], 100.0, 101.0, 99.0, 100.0))
    assert decision.action == "hold"
    assert state == StopState(
        entry_price=100.0, peak_price=101.0, bar_count=1, entry_date="2024-01-02"
    )

    _, gap = engine.update(state, StopBar(DATES[1], 89.0, 90.0, 88.0, 89.0))
    assert (gap.action, gap.reason) == ("exit", "stop_loss")

    _, intraday = engine.update(state, StopBar(DATES[1], 95.0, 96.0, 89.0, 90.0))
    assert (intraday.action, intraday.reason) == ("exit", "stop_loss")

    updated, hold = engine.update(state, StopBar(DATES[1], 99.0, 100.0, 95.0, 96.0))
    assert hold.action == "hold"
    assert updated.bar_count == 2 and updated.peak_price == 101.0


def test_v6_trailing_and_take_profit_priority():
    """S5-S8 / D6：移动止损激活即触发、未激活不触发、SL 优先于 TP。"""
    from core.stops import StopBar, StopConfig, StopEngine

    engine = StopEngine(StopConfig(trailing_stop_pct=0.08, trailing_activate_pct=0.05))
    state, _ = engine.update(None, StopBar(DATES[0], 50.0, 50.5, 49.5, 50.0))
    state, hold1 = engine.update(state, StopBar(DATES[1], 51.0, 53.0, 50.8, 52.0))
    assert hold1.action == "hold"
    state, hold2 = engine.update(state, StopBar(DATES[2], 52.0, 52.5, 49.0, 49.5))
    assert hold2.action == "hold"
    _, trailing = engine.update(state, StopBar(DATES[3], 49.5, 50.0, 47.0, 48.0))
    assert (trailing.action, trailing.reason) == ("exit", "trailing_stop")

    engine2 = StopEngine(StopConfig(trailing_stop_pct=0.08, trailing_activate_pct=0.5))
    state2, _ = engine2.update(None, StopBar(DATES[0], 50.0, 50.5, 49.5, 50.0))
    _, hold3 = engine2.update(state2, StopBar(DATES[1], 51.0, 53.0, 47.0, 52.0))
    assert hold3.action == "hold"

    engine3 = StopEngine(StopConfig(stop_loss_pct=0.10, take_profit_pct=0.20))
    state3, _ = engine3.update(None, StopBar(DATES[0], 100.0, 101.0, 99.0, 100.0))
    _, both = engine3.update(state3, StopBar(DATES[1], 102.0, 122.0, 88.0, 100.0))
    assert (both.action, both.reason) == ("exit", "stop_loss")

    engine4 = StopEngine(StopConfig(stop_loss_pct=0.10, take_profit_pct=0.20))
    state4, _ = engine4.update(None, StopBar(DATES[0], 100.0, 101.0, 99.0, 100.0))
    _, tp = engine4.update(state4, StopBar(DATES[1], 105.0, 125.0, 99.0, 120.0))
    assert (tp.action, tp.reason) == ("exit", "take_profit")


def test_v7_time_stop_and_deferred_exit():
    """S9 / D6-D7：时间止损、不可交易日延迟、deferred 计数。"""
    from core.stops import StopConfig, apply_stops

    dates = DATES[:4]
    codes = ["X", "Y"]
    targets = pd.DataFrame(0.5, index=dates, columns=codes)
    flat = pd.DataFrame(100.0, index=dates, columns=codes)
    bars = {
        "open": flat.copy(),
        "high": flat + 1.0,
        "low": flat - 1.0,
        "close": flat.copy(),
    }
    tradable = pd.DataFrame(True, index=dates, columns=codes)
    tradable.loc[dates[1], "Y"] = False

    result = apply_stops(targets, bars, StopConfig(time_stop_days=2), tradable=tradable)

    assert result.weights["X"].tolist() == [0.5, 0.0, 0.5, 0.0]
    assert result.weights["Y"].tolist() == [0.5, 0.5, 0.0, 0.5]
    assert result.deferred == 1
    assert [t.reason for t in result.triggers] == ["time_stop"] * 3


def test_v8_apply_stops_end_to_end():
    """D7 / I8-I9：多标的端到端、状态往返、行和只减不增、三类 fail-fast。"""
    from core.stops import StopConfig, StopState, apply_stops

    codes = ["A", "B"]
    targets = pd.DataFrame(0.5, index=DATES, columns=codes)
    close = pd.DataFrame(
        [[100.0, 50.0], [96.0, 51.0], [90.0, 50.0], [89.0, 49.0], [89.0, 48.0]],
        index=DATES,
        columns=codes,
    )
    open_ = close.shift(1).fillna(close.iloc[0])
    high = close + 1.0
    low = close - 1.0
    bars = {"open": open_, "high": high, "low": low, "close": close}

    result = apply_stops(targets, bars, StopConfig(stop_loss_pct=0.10))
    assert len(result.triggers) == 1
    trigger = result.triggers[0]
    assert (trigger.code, trigger.reason) == ("A", "stop_loss")
    assert trigger.entry_date == "2024-01-02"
    assert trigger.entry_price == pytest.approx(100.0)
    assert trigger.exit_price_ref == pytest.approx(90.0)
    assert result.weights.loc[DATES[2], "A"] == 0.0
    assert result.weights.loc[DATES[3], "A"] == 0.5

    for payload in result.states.values():
        assert StopState.from_dict(payload).to_dict() == payload
    assert (result.weights.sum(axis=1) <= targets.sum(axis=1) + 1e-12).all()

    with pytest.raises(ValueError, match="缺少键"):
        apply_stops(targets, {"open": bars["open"]}, StopConfig(stop_loss_pct=0.10))
    broken = {key: value.copy() for key, value in bars.items()}
    broken["close"].iloc[0, 0] = np.nan
    with pytest.raises(ValueError, match="缺失值"):
        apply_stops(targets, broken, StopConfig(stop_loss_pct=0.10))
    bad_targets = targets.copy()
    bad_targets.iloc[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        apply_stops(bad_targets, bars, StopConfig(stop_loss_pct=0.10))

    with pytest.raises(ValueError, match="正数"):
        StopConfig(stop_loss_pct=0.0)
    with pytest.raises(ValueError, match="time_stop_days"):
        StopConfig(time_stop_days=0)


def _run_golden(name: str):
    from core.stops import StopConfig, apply_stops

    payload = json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))
    dates = pd.DatetimeIndex(payload["targets"]["dates"])
    codes = payload["targets"]["codes"]
    targets = pd.DataFrame(payload["targets"]["values"], index=dates, columns=codes)
    bars = {
        key: pd.DataFrame(payload["bars"][key], index=dates, columns=codes)
        for key in ("open", "high", "low", "close")
    }
    tradable = None
    if payload["tradable"] is not None:
        tradable = pd.DataFrame(payload["tradable"], index=dates, columns=codes).astype(bool)

    result = apply_stops(targets, bars, StopConfig(**payload["config"]), tradable=tradable)
    expected = payload["expected"]

    pd.testing.assert_frame_equal(
        result.weights,
        pd.DataFrame(expected["weights"], index=dates, columns=codes),
        check_dtype=False,
    )
    got_triggers = [
        {
            "date": trigger.date.strftime("%Y-%m-%d"),
            "code": trigger.code,
            "reason": trigger.reason,
            "entry_date": trigger.entry_date,
            "entry_price": trigger.entry_price,
            "exit_price_ref": trigger.exit_price_ref,
        }
        for trigger in result.triggers
    ]
    assert got_triggers == expected["triggers"]
    assert result.deferred == expected["deferred"]
    assert result.states == expected["states"]


def test_golden_p045_s1():
    """G1：固定止损 + 移动止损 + 止盈优先级（规格锁定）。"""
    _run_golden("P045_S1")


def test_golden_p045_s2():
    """G2：时间止损 + 跌停延迟退出（规格锁定）。"""
    _run_golden("P045_S2")
