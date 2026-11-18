"""P-043：事件总线契约与引擎接入（V1-V8）。

红态设计（IMPL §4.3）：核心符号一律函数内导入 → 逐用例失败而非收集期 error；
V3 为「重开续号」非回归护栏（当前 EventLog 即通过）。
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_factor, write_price_fixture

DATES = pd.bdate_range("2024-01-02", periods=5)
CODES = ["000001", "600000"]


def _fixture(root: Path) -> None:
    prices = np.array([[10.0 + 0.1 * i, 20.0 + 0.1 * i] for i in range(len(DATES))])
    write_price_fixture(root, DATES, CODES, prices)
    write_factor(root, "factor_value", np.tile([1.0, 2.0], (len(DATES), 1)), DATES, CODES)


def _make_engine(
    root: Path,
    *,
    event_log_path: Path | None = None,
    event_bus: Any = None,
    trigger: Any = None,
    optimizer: Any = None,
):
    from core.config import (
        BacktestConfig,
        CostConfig,
        FactorConfig,
        OptimizerConfig,
        RebalanceConfig,
        UniverseConfig,
    )
    from core.engine_v2 import BacktestEngineV2

    cfg = BacktestConfig(
        data_dir=root,
        output_dir=root / "out",
        factor_files=["factor_value.pkl"],
        event_log_path=event_log_path,
        cost=CostConfig(
            commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0
        ),
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",
            target_count=2,
            max_weight=1.0,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False
        ),
        initial_capital=10_000_000.0,
        enable_pending_orders=False,
        write_manifest=False,
    )
    return BacktestEngineV2(cfg, event_bus=event_bus, trigger=trigger, optimizer=optimizer)


def test_v1_event_bus_contract(tmp_path):
    """I10 / G3：EventLog 运行时满足 IEventBus；签名与常量逐字。"""
    from core.event_log import EventLog, EventType, IEventBus

    log = EventLog(log_path=tmp_path / "e.jsonl")
    assert isinstance(log, IEventBus)

    append_sig = inspect.signature(log.append)
    assert list(append_sig.parameters) == ["event_type", "payload", "source"]
    assert append_sig.parameters["source"].default == ""
    assert list(inspect.signature(log.read).parameters) == [
        "after_seq",
        "limit",
        "event_type",
    ]
    assert list(inspect.signature(log.subscribe).parameters) == ["listener"]
    assert list(inspect.signature(log.last_seq).parameters) == []

    assert EventType.RUN_STARTED == "engine.run_started"
    assert EventType.REBALANCE == "engine.rebalance"
    assert EventType.DAY_END == "engine.day_end"
    assert EventType.ERROR == "engine.error"
    assert EventType.RUN_FINISHED == "engine.run_finished"


def test_v2_replay(tmp_path):
    """I4 / G4：replay(k) 与 read(after_seq=k) 一致；handler 异常向外传播。"""
    from core.event_log import EventLog

    log = EventLog(log_path=tmp_path / "e.jsonl")
    for i in range(5):
        log.append("t", {"i": i})

    entries = log.replay(2)
    assert [e.seq for e in entries] == [3, 4, 5]
    assert [e.seq for e in entries] == [e.seq for e in log.read(after_seq=2)]

    seen: list[int] = []
    returned = log.replay(2, handler=lambda e: seen.append(e.seq))
    assert [e.seq for e in returned] == [3, 4, 5]
    assert seen == [3, 4, 5]

    def boom(entry):
        raise RuntimeError("handler boom")

    with pytest.raises(RuntimeError, match="handler boom"):
        log.replay(2, handler=boom)


def test_v3_reopen_continues_seq(tmp_path):
    """I7（非回归护栏）：同路径重开 → 首个新 seq = 旧 last_seq + 1。"""
    from core.event_log import EventLog

    path = tmp_path / "e.jsonl"
    first = EventLog(log_path=path)
    for i in range(3):
        first.append("t", {"i": i})

    second = EventLog(log_path=path)
    entry = second.append("t", {"i": 3})
    assert entry.seq == 4
    assert [e.seq for e in second.read()] == [1, 2, 3, 4]


def test_v4_default_closed_zero_behavior(tmp_path):
    """I1 / D6：默认关闭 → 不构造总线、无结果键、无 jsonl。"""
    _fixture(tmp_path)
    engine = _make_engine(tmp_path)
    engine.setup()
    results = engine.run()

    assert engine._event_bus is None
    assert "event_bus" not in results["additional_info"]
    assert list(tmp_path.rglob("*.jsonl")) == []


def test_v5_events_emitted_with_continuous_seq(tmp_path):
    """I2 / I3 / S7：seq 1..N 连续；首尾类型与 payload 键集逐字。"""
    from core.event_log import EventType

    _fixture(tmp_path)
    log_path = tmp_path / "events.jsonl"
    engine = _make_engine(tmp_path, event_log_path=log_path)
    engine.setup()
    results = engine.run()

    bus = engine._event_bus
    entries = bus.read()
    types = [e.type for e in entries]
    assert types[0] == EventType.RUN_STARTED
    assert types[-1] == EventType.RUN_FINISHED
    assert [e.seq for e in entries] == list(range(1, len(entries) + 1))
    assert types.count(EventType.DAY_END) == len(DATES)
    assert entries[0].source == "engine_v2"
    assert set(entries[0].payload) == {"start", "end", "n_dates"}
    assert entries[0].payload["start"] == DATES[0].strftime("%Y-%m-%d")
    assert entries[0].payload["end"] == DATES[-1].strftime("%Y-%m-%d")
    assert entries[0].payload["n_dates"] == len(DATES)
    assert types.count(EventType.REBALANCE) == len(DATES)
    rebalance_entry = next(e for e in entries if e.type == EventType.REBALANCE)
    assert rebalance_entry.payload["n_targets"] == 2
    day_end_entry = next(e for e in entries if e.type == EventType.DAY_END)
    assert set(day_end_entry.payload) == {"date", "total_value"}

    info = results["additional_info"]["event_bus"]
    assert info == {"enabled": True, "last_seq": len(entries), "errors": 0}
    assert entries[-1].seq == info["last_seq"]
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == len(entries)


def test_v6_subscription_matches_disk(tmp_path):
    """I5：订阅 seq 集合 = 磁盘 seq 集合；取消订阅后不再通知。"""
    from core.event_log import EventLog

    _fixture(tmp_path)
    bus = EventLog(log_path=tmp_path / "events.jsonl")
    engine = _make_engine(tmp_path, event_bus=bus)
    collected: list[int] = []
    unsubscribe = bus.subscribe(lambda e: collected.append(e.seq))
    engine.setup()
    engine.run()

    disk = [e.seq for e in bus.read()]
    assert collected == disk

    unsubscribe()
    bus.append("after.unsubscribe", {})
    assert collected == disk


class _BoomBus:
    """append 恒抛的伪总线（V7）；其余方法满足 IEventBus 契约。"""

    def __init__(self) -> None:
        self.calls = 0

    def append(self, event_type, payload, source=""):
        self.calls += 1
        raise RuntimeError("bus down")

    def last_seq(self) -> int:
        return 0

    def read(self, after_seq=0, limit=None, event_type=None):
        return []

    def subscribe(self, listener):
        return lambda: None


def test_v7_bus_failure_does_not_change_backtest(tmp_path):
    """I6 / D4：总线故障零传播；成交与净值不变，errors 显形。"""
    _fixture(tmp_path)
    baseline = _make_engine(tmp_path)
    baseline.setup()
    baseline.run()
    base_trades = baseline.executor.trade_log.get_trades_df()

    boom = _BoomBus()
    engine = _make_engine(tmp_path, event_bus=boom)
    engine.setup()
    results = engine.run()
    trades = engine.executor.trade_log.get_trades_df()

    assert boom.calls > 0
    assert len(trades) == len(base_trades)
    assert float(trades["amount"].sum()) == pytest.approx(float(base_trades["amount"].sum()))
    info = results["additional_info"]["event_bus"]
    assert info["errors"] == boom.calls
    assert info["last_seq"] == 0


class _RaisingTrigger:
    """第 N 次 should_trigger 抛错（V8a）。"""

    def __init__(self, fail_on_call: int = 2) -> None:
        self.calls = 0
        self.fail_on_call = fail_on_call

    def should_trigger(self, date, **kwargs) -> bool:
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("trigger boom")
        return False


class _RaisingOptimizer:
    """optimize 恒抛（V8b）。"""

    def optimize(self, signals, returns_data=None):
        raise RuntimeError("opt boom")


def test_v8_error_events_emitted_without_interruption(tmp_path):
    """I3 / D3：两阶段错误事件不中断（V8a day_loop / V8b rebalance，F-S8-P043-1 合并）。"""
    from core.event_log import EventType

    _fixture(tmp_path)

    # V8a：day_loop 错误（trigger 第 2 次调用抛错 = 交易日 index 1）
    trigger = _RaisingTrigger(fail_on_call=2)
    engine_a = _make_engine(tmp_path, event_log_path=tmp_path / "events_a.jsonl", trigger=trigger)
    engine_a.setup()
    results_a = engine_a.run()

    entries_a = engine_a._event_bus.read()
    errors_a = [e for e in entries_a if e.type == EventType.ERROR]
    assert len(errors_a) == 1
    payload = errors_a[0].payload
    assert set(payload) == {"date", "stage", "error_type", "message"}
    assert payload["date"] == DATES[1].strftime("%Y-%m-%d")
    assert payload["stage"] == "day_loop"
    assert payload["error_type"] == "RuntimeError"

    types_a = [e.type for e in entries_a]
    assert types_a.count(EventType.DAY_END) == len(DATES) - 1
    assert types_a[-1] == EventType.RUN_FINISHED
    diagnostics_a = results_a["additional_info"]["run_diagnostics"]
    assert diagnostics_a["counts"].get("day_loop") == 1

    # V8b：rebalance 错误（独立 events_b.jsonl，防第二引擎重开续号污染 read()）
    engine_b = _make_engine(
        tmp_path,
        event_log_path=tmp_path / "events_b.jsonl",
        optimizer=_RaisingOptimizer(),
    )
    engine_b.setup()
    results_b = engine_b.run()

    entries_b = engine_b._event_bus.read()
    types_b = [e.type for e in entries_b]
    errors_b = [e for e in entries_b if e.type == EventType.ERROR]
    assert len(errors_b) == len(DATES)
    assert all(e.payload["stage"] == "rebalance" for e in errors_b)
    assert types_b.count(EventType.REBALANCE) == 0
    assert types_b.count(EventType.DAY_END) == len(DATES)
    assert types_b[-1] == EventType.RUN_FINISHED
    diagnostics_b = results_b["additional_info"]["run_diagnostics"]
    assert diagnostics_b["counts"].get("rebalance") == len(DATES)
