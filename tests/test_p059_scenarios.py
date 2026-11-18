"""P-059 场景回归测试（DESIGN §16 T8）。

17 条场景由 ``_scenarios_cases.SCENARIOS`` 单一来源驱动；
``assert_scenario`` 完成全原语组合断言（A4/A5）。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from _scenarios_assert import (
    assert_capability_declared,
    assert_dirty_input_raises,
    assert_reasons_closed,
    assert_scenario,
    assert_trace_shape,
)
from _scenarios_builder import build_scenario
from _scenarios_cases import SCENARIOS
from _scenarios_spec import BUCKET_KEYS, ORDER_STATES, REASONS, ScenarioSpec
from _scenarios_trace import RecordingExecutor, RecordingOptimizer, RecordingTracker

from core.execution import ExecutionSimulator
from core.portfolio import EqualWeightOptimizer
from core.stops import StopBar, StopConfig, StopEngine
from core.tracker import PositionTracker
from filter.limit_rules import build_limit_prices

IDS = list(SCENARIOS)


def _run_stops(spec: ScenarioSpec) -> None:
    case = dict(spec.stop_case)
    engine = StopEngine(StopConfig(**case["config"]))
    state = None
    actual = []
    for index, bar in enumerate(case["bars"]):
        state, decision = engine.update(state, StopBar(date=spec.dates[index], **bar))
        actual.append((decision.action, decision.reason))
    assert actual == [tuple(item) for item in case["expect"]]


def _run_limit_price(spec: ScenarioSpec) -> None:
    prev_close = float(spec.stop_case["prev_close"])
    columns = [spec.codes[0]]
    close = pd.DataFrame([[prev_close], [prev_close]], index=spec.dates, columns=columns)
    adj = pd.DataFrame(1.0, index=spec.dates, columns=columns)
    up, down = build_limit_prices(close, adj, None, spec.dates)
    actual_up = float(up.iloc[1, 0])
    actual_down = float(down.iloc[1, 0])
    assert actual_up == pytest.approx(float(spec.stop_case["expected_up"]), abs=1e-9)
    assert actual_up != round(actual_up, 2), "涨停价不应被舍入到 0.01"
    assert actual_down != round(actual_down, 2), "跌停价不应被舍入到 0.01"


@pytest.mark.parametrize("spec", list(SCENARIOS.values()), ids=IDS)
def test_p059_scenario(spec: ScenarioSpec, tmp_path: Any) -> None:
    """逐场景闭式断言（A2：期望值全部来自声明，未做任何录制）。"""
    if spec.kind == "raises":
        assert_dirty_input_raises(lambda: build_scenario(spec, tmp_path), expect=ValueError)
        return
    if spec.kind == "stops":
        _run_stops(spec)
        return
    if spec.kind == "limit_price":
        _run_limit_price(spec)
        return

    run = build_scenario(spec, tmp_path)
    if spec.ohlc_independent:
        assert run.ohlc_synthetic is False, f"{spec.scenario_id}: 显式 OHLC 场景不应复用 close"
    assert_scenario(spec, run)


def test_registry_contract() -> None:
    """A1：17 条单一来源，id 唯一，7 层全覆盖。"""
    assert len(SCENARIOS) == 17
    assert len(set(IDS)) == 17
    assert {spec.layer for spec in SCENARIOS.values()} == {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}


@pytest.mark.parametrize("spec", list(SCENARIOS.values()), ids=IDS)
def test_each_scenario_declares_closed_form(spec: ScenarioSpec) -> None:
    """A2：每条场景必须有非空闭式期望（backtest 用 ExpectedBlock，其余用 payload）。"""
    if spec.kind == "backtest":
        expected = spec.expected
        has_block = any(
            (
                expected.fills,
                expected.no_fill,
                expected.order_states,
                expected.buyable,
                expected.sellable,
                expected.nav_days,
                expected.final_cash is not None,
                expected.final_nav is not None,
                expected.final_positions is not None,
            )
        )
        assert has_block, f"{spec.scenario_id}: backtest 场景缺少闭式期望"
    elif spec.kind in ("stops", "limit_price"):
        assert spec.stop_case, f"{spec.scenario_id}: {spec.kind} 场景缺少 payload"
    else:
        # raises 场景的闭式期望就是「构建期必抛 ValueError」（见 test_p059_scenario）
        assert (
            spec.expected == type(spec.expected)()
        ), f"{spec.scenario_id}: raises 场景不应声明期望值（脏输入必须在构建期失败）"


def test_bucket_and_reason_contract() -> None:
    """DESIGN §4：桶 10 键 / reason 10 项 / 订单态 3 项。"""
    assert len(BUCKET_KEYS) == 10
    assert len(REASONS) == 10
    assert ORDER_STATES == ("filled", "retry", "dropped")


def test_capability_boundaries_declared() -> None:
    """A10：能力边界 8 键全量声明。"""
    assert_capability_declared()


def test_trace_disabled_keeps_native_components(tmp_path: Any) -> None:
    """I3：``trace_enabled=False`` 时不 attach，引擎保持原生组件（零行为）。"""
    spec = SCENARIOS["S01"]
    run = build_scenario(spec, tmp_path, trace_enabled=False)
    assert not isinstance(run.engine.executor, RecordingExecutor)
    assert not isinstance(run.engine.tracker, RecordingTracker)
    assert not isinstance(run.engine.optimizer, RecordingOptimizer)
    assert isinstance(run.engine.executor, ExecutionSimulator)
    assert isinstance(run.engine.tracker, PositionTracker)
    assert isinstance(run.engine.optimizer, EqualWeightOptimizer)
    assert run.trace.buckets == {}


def test_scenario_trace_is_closed_and_complete(tmp_path: Any) -> None:
    """I13：桶数 == 交易日数，且 reason/state 均在闭集内。"""
    spec = SCENARIOS["S02"]
    run = build_scenario(spec, tmp_path)
    assert_trace_shape(run)
    assert_reasons_closed(run)
    assert list(sorted(run.trace.buckets)) == [
        pd.Timestamp(date).strftime("%Y-%m-%d") for date in run.trade_dates
    ]
