"""P-044：策略接口契约与权重模式接入（V1-V8）。

红态设计（IMPL §4.3）：核心符号一律函数内导入 → 逐用例失败而非收集期 error；
V4 为零行为护栏（当前代码即通过）。
"""

from __future__ import annotations

import inspect
import json
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


def _make_optimizer(*, select_top: bool = True, target_count: int = 2):
    from core.config import OptimizerConfig
    from core.portfolio import EqualWeightOptimizer

    return EqualWeightOptimizer(
        OptimizerConfig(
            method="equal_weight",
            target_count=target_count,
            max_weight=1.0,
            round_lot=True,
            select_top=select_top,
        )
    )


def _make_engine(root: Path):
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
    return BacktestEngineV2(cfg)


def test_v1_contract_dataclasses_and_protocol():
    """I2 / I10：三 frozen dataclass + Strategy 运行时协议 + meta 四要素。"""
    from dataclasses import FrozenInstanceError

    from core.strategy import (
        FactorSignalStrategy,
        MarketView,
        Strategy,
        StrategyMeta,
        StrategyState,
        TargetWeights,
    )

    assert TargetWeights is pd.Series

    meta = StrategyMeta(
        strategy_id="x", version="1.0.0", param_schema={"a": 1}, code_hash="0123456789ab"
    )
    with pytest.raises(FrozenInstanceError):
        meta.strategy_id = "y"  # type: ignore[misc]

    state = StrategyState(as_of="2024-01-02", positions={"000001": 0.5}, extras={})
    with pytest.raises(FrozenInstanceError):
        state.as_of = "2024-01-03"  # type: ignore[misc]

    view = MarketView(
        date=DATES[0],
        signal=pd.Series({"000001": 1.0}),
        tradable=pd.Series({"000001": True}),
        prices=pd.Series({"000001": 10.0}),
        returns=None,
    )
    with pytest.raises(FrozenInstanceError):
        view.date = DATES[1]  # type: ignore[misc]

    strategy = FactorSignalStrategy(_make_optimizer())
    assert isinstance(strategy, Strategy)
    assert isinstance(strategy.meta, StrategyMeta)
    assert strategy.meta.strategy_id == "factor_signal"
    assert strategy.meta.version == "1.0.0"
    assert strategy.meta.param_schema["select_top"] is True
    assert strategy.meta.param_schema["target_count"] == 2
    assert len(strategy.meta.code_hash) == 12

    sig = inspect.signature(strategy.generate_signals)
    assert list(sig.parameters) == ["view", "state"]


def test_v2_code_hash_stability_and_fallback(tmp_path):
    """I7：同源码稳定 / 12 hex / 参数不入 hash / CRLF≡LF / 动态类 q: 回退。"""
    import importlib.util
    import sys

    from core.strategy import FactorSignalStrategy, code_hash

    h1 = code_hash(FactorSignalStrategy)
    assert h1 == code_hash(FactorSignalStrategy)
    assert len(h1) == 12
    assert all(char in "0123456789abcdef" for char in h1)

    # 参数不同、类源码相同 → 同 hash（参数入 param_schema）
    small = FactorSignalStrategy(_make_optimizer(target_count=2))
    large = FactorSignalStrategy(_make_optimizer(target_count=3))
    assert small.meta.code_hash == large.meta.code_hash
    assert small.meta.param_schema != large.meta.param_schema

    # CRLF 与 LF 源码同 hash（换行归一）
    source = "class Same:\n    def generate_signals(self, view, state):\n        return None\n"
    hashes = []
    for name, newline in (("p044_src_lf", "\n"), ("p044_src_crlf", "\r\n")):
        path = tmp_path / f"{name}.py"
        path.write_bytes(source.replace("\n", newline).encode("utf-8"))
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
            hashes.append(code_hash(module.Same))
        finally:
            sys.modules.pop(name, None)
    assert hashes[0] == hashes[1]

    # exec 动态类：类/方法均取源失败 → q: 前缀回退
    namespace: dict[str, Any] = {}
    exec(
        "class Dyn:\n" "    def generate_signals(self, view, state):\n" "        return None\n",
        namespace,
    )
    dynamic = code_hash(namespace["Dyn"])
    assert dynamic.startswith("q:")
    assert len(dynamic) == 14


def test_v3_state_json_roundtrip():
    """I4：to_dict → json → from_dict 往返相等；值类型归一。"""
    from core.strategy import StrategyState

    state = StrategyState(
        as_of="2024-01-05",
        positions={"000001": 0.5, "600000": 0.25},
        extras={"regime": "bull", "n": 2},
    )
    payload = json.dumps(state.to_dict(), ensure_ascii=False)
    restored = StrategyState.from_dict(json.loads(payload))

    assert restored == state
    assert restored.positions == {"000001": 0.5, "600000": 0.25}
    assert all(isinstance(value, float) for value in restored.positions.values())
    assert restored.extras == {"regime": "bull", "n": 2}


def test_v4_default_mode_zero_behavior(tmp_path):
    """I1 / D8：默认 scores → 两次运行指标/净值/成交完全一致（红态亦 PASS 护栏）。"""
    _fixture(tmp_path)

    first = _make_engine(tmp_path)
    first.setup()
    assert getattr(first, "_signal_mode", "scores") == "scores"
    results_a = first.run()

    second = _make_engine(tmp_path)
    second.setup()
    results_b = second.run()

    assert list(results_a["portfolio_value"]) == list(results_b["portfolio_value"])
    for key in (
        "total_return",
        "annual_return",
        "annual_volatility",
        "max_drawdown",
        "sharpe_ratio",
        "win_rate",
        "trading_days",
    ):
        assert results_a["performance_metrics"][key] == pytest.approx(
            results_b["performance_metrics"][key]
        ), key
    trades_a = first.executor.trade_log.get_trades_df()
    trades_b = second.executor.trade_log.get_trades_df()
    assert len(trades_a) == len(trades_b)
    assert float(trades_a["amount"].sum()) == pytest.approx(float(trades_b["amount"].sum()))


def test_v5_weights_mode_matches_scores_mode(tmp_path):
    """I3 / I9：strategy + weights 通道与默认 scores 路径成交/净值逐值一致。"""
    from core.strategy import BacktestAdapter, FactorSignalStrategy

    _fixture(tmp_path)

    baseline = _make_engine(tmp_path)
    baseline.setup()
    base_results = baseline.run()
    base_trades = baseline.executor.trade_log.get_trades_df()

    engine = _make_engine(tmp_path)
    engine.setup()
    adapter = BacktestAdapter(FactorSignalStrategy(engine.optimizer))
    views = adapter.views_from_data(
        engine.dm,
        engine._composite_signal,
        tradable=engine.universe.tradable,
        returns_window=engine.cfg.optimizer.cov_lookback,
    )
    frame = adapter.signals_frame(views)
    assert list(frame.index) == list(DATES)
    assert len(adapter.state_history) == len(DATES)

    engine.set_signal(frame, mode="weights")
    assert engine._signal_mode == "weights"
    results = engine.run()
    trades = engine.executor.trade_log.get_trades_df()

    assert len(trades) == len(base_trades)
    assert list(trades["stock"]) == list(base_trades["stock"])
    assert list(trades["quantity"]) == list(base_trades["quantity"])
    assert list(results["portfolio_value"].round(6)) == list(
        base_results["portfolio_value"].round(6)
    )
    for key in ("total_return", "annual_return", "max_drawdown", "sharpe_ratio", "trading_days"):
        assert results["performance_metrics"][key] == pytest.approx(
            base_results["performance_metrics"][key]
        ), key


def test_v6_directional_equivalence():
    """I3：三方向与 EqualWeightOptimizer 直出逐值相等；both=long×long_weight。"""
    from core.strategy import DirectionalStrategy, MarketView, StrategyState

    signal = pd.Series({"000001": 1.0, "600000": 2.0, "000002": 0.5})
    view = MarketView(
        date=DATES[0],
        signal=signal,
        tradable=pd.Series(True, index=signal.index),
        prices=pd.Series(10.0, index=signal.index),
        returns=None,
    )
    state = StrategyState(as_of="2024-01-02", positions={}, extras={})

    long_optimizer = _make_optimizer(select_top=True)
    short_optimizer = _make_optimizer(select_top=False)
    long_strategy = DirectionalStrategy(long_optimizer, direction="long", select_top=True)
    short_strategy = DirectionalStrategy(short_optimizer, direction="short", select_top=False)
    both_strategy = DirectionalStrategy(long_optimizer, direction="both", long_weight=0.5)

    long_expected = long_optimizer.optimize(signal, None)
    short_expected = short_optimizer.optimize(signal, None)

    pd.testing.assert_series_equal(long_strategy.generate_signals(view, state), long_expected)
    pd.testing.assert_series_equal(short_strategy.generate_signals(view, state), short_expected)
    both_weights = both_strategy.generate_signals(view, state)
    pd.testing.assert_series_equal(both_weights, long_expected * 0.5)
    assert float(both_weights.sum()) == pytest.approx(0.5)
    assert DirectionalStrategy.short_leg_supported is False
    assert both_strategy.meta.strategy_id == "directional_both"

    with pytest.raises(ValueError, match="未知方向"):
        DirectionalStrategy(long_optimizer, direction="sideways")


def test_v7_set_signal_validation(tmp_path):
    """I6：四类非法输入 fail-fast；scores 允许 NaN；未 setup 抛 RuntimeError。"""
    _fixture(tmp_path)

    engine = _make_engine(tmp_path)
    engine.setup()

    bad_index = pd.DataFrame(0.5, index=DATES[:-1], columns=CODES)
    with pytest.raises(ValueError, match="index"):
        engine.set_signal(bad_index, mode="weights")

    unknown = pd.DataFrame(0.5, index=DATES, columns=["000001", "999999"])
    with pytest.raises(ValueError, match="未知标的"):
        engine.set_signal(unknown, mode="weights")

    negative = pd.DataFrame(0.5, index=DATES, columns=CODES)
    negative.iloc[0, 0] = -0.1
    with pytest.raises(ValueError, match="负权重"):
        engine.set_signal(negative, mode="weights")

    over = pd.DataFrame(0.6, index=DATES, columns=CODES)
    with pytest.raises(ValueError, match="权重和"):
        engine.set_signal(over, mode="weights")

    with pytest.raises(ValueError, match="未知信号模式"):
        engine.set_signal(pd.DataFrame(0.5, index=DATES, columns=CODES), mode="bogus")

    scores = pd.DataFrame(np.nan, index=DATES, columns=CODES)
    scores.iloc[0, 0] = 1.0
    engine.set_signal(scores, mode="scores")
    assert engine._signal_mode == "scores"
    assert engine._composite_signal.shape == (len(DATES), len(CODES))
    assert np.isnan(engine._composite_signal.iloc[0, 1])

    fresh = _make_engine(tmp_path)
    with pytest.raises(RuntimeError, match="setup"):
        fresh.set_signal(scores, mode="scores")


def test_v8_strategy_registry(caplog):
    """I5：registry strategy 类别——单例 / 注册 / 查询 / 创建 / 覆写 warning。"""
    from core.registry import get_strategy_registry, register_strategy

    registry = get_strategy_registry()
    assert registry is get_strategy_registry()
    assert registry.category == "strategy"

    name = "p044_test_strategy"

    def factory(**kwargs: Any):
        return {"kwargs": kwargs}

    try:
        register_strategy(name, description="test")(factory)
        assert registry.has(name)
        entry = registry.get(name)
        assert entry is not None and entry.category == "strategy"
        assert registry.create(name, foo=1) == {"kwargs": {"foo": 1}}

        with caplog.at_level("WARNING"):
            register_strategy(name, description="again")(factory)
        assert any("already registered" in record.message for record in caplog.records)
        assert registry.get(name).description == "again"
    finally:
        registry.unregister(name)
    assert not registry.has(name)
