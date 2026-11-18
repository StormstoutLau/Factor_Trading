"""P-059 场景构建器（DESIGN §3 DD3 / Step 5 T1）。

单一执行入口：``build_scenario(spec, root)`` → 写夹具 → 构建配置 → setup →
（可选注入）→ attach trace → run。pytest 与 CLI 均调用本函数。

DD1：复用 ``tests/_synth_fixture.py``（不改其签名）与 ``core`` 既有能力。
DD4：注入仅发生在 ``setup()`` 之后、``run()`` 之前，生产代码零感知。
"""

from __future__ import annotations

import dataclasses
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import numpy as np
import pandas as pd

from _synth_fixture import write_factor, write_price_fixture, write_universe

from core.config import (
    BacktestConfig,
    CostConfig,
    FactorConfig,
    OptimizerConfig,
    RebalanceConfig,
    UniverseConfig,
)
from core.engine_v2 import BacktestEngineV2
from core.pending import OrderSide, create_pending_order
from filter.limit_rules import build_limit_prices, special_no_limit_mask

from _scenarios_spec import ScenarioSpec
from _scenarios_trace import TraceRecorder

# spec.config 保留键：不当作 BacktestConfig 字段处理。
RESERVED_KEYS = frozenset(
    {
        "no_rebalance",
        "inject_weights",
        "inject_orders",
        "expect_build_error",
    }
)

DEFAULT_CAPITAL = 100_000.0


@dataclass
class ScenarioRun:
    """一次场景执行的完整产物。"""

    spec: ScenarioSpec
    root: Path
    engine: Any
    results: dict[str, Any]
    trace: TraceRecorder
    masks: dict[str, Any]
    trade_dates: pd.DatetimeIndex
    ohlc_synthetic: bool

    @property
    def last_bucket(self) -> dict[str, Any]:
        key = max(self.trace.buckets)
        return self.trace.buckets[key]

    @property
    def final_cash(self) -> float:
        return float(self.last_bucket["cash"])

    @property
    def final_nav(self) -> float:
        return float(self.last_bucket["nav"])

    @property
    def final_positions(self) -> dict[str, int]:
        return dict(self.last_bucket["positions"])


def _apply_overrides(target: Any, overrides: Mapping[str, Any], *, prefix: str = "") -> None:
    for key, value in overrides.items():
        if not hasattr(target, key):
            raise ValueError(f"未知配置项: {prefix}{key}")
        current = getattr(target, key)
        if isinstance(value, Mapping) and dataclasses.is_dataclass(current):
            _apply_overrides(current, value, prefix=f"{prefix}{key}.")
        else:
            setattr(target, key, value)


def build_config(spec: ScenarioSpec, root: Path) -> BacktestConfig:
    """由场景声明构建 ``BacktestConfig``（默认值保证确定性）。"""
    first_factor = next(iter(spec.factors))
    cfg = BacktestConfig(
        data_dir=Path(root),
        output_dir=Path(root) / "out",
        factor_files=[f"{first_factor}.pkl"],
        cost=CostConfig(),
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",
            target_count=len(spec.codes),
            max_weight=1.0,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="N_days", n_days=len(spec.dates)),
        universe=UniverseConfig(),
        initial_capital=DEFAULT_CAPITAL,
        enable_pending_orders=True,
        enable_fallback=False,
        enable_parallel=False,
        enable_cache=False,
        write_manifest=False,
        day_error_mode="raise",
        invariant_mode="report",
    )
    overrides = {k: v for k, v in spec.config.items() if k not in RESERVED_KEYS}
    _apply_overrides(cfg, overrides)
    return cfg


def _write_fixtures(spec: ScenarioSpec, root: Path) -> None:
    write_price_fixture(
        root,
        spec.dates,
        spec.codes,
        spec.close,
        open_prices=spec.open,
        high_prices=spec.high,
        low_prices=spec.low,
        suspend=spec.suspend if spec.suspend is not None else 0,
        st=spec.st if spec.st is not None else 0,
    )
    if spec.adj is not None:
        pd.DataFrame(
            np.asarray(spec.adj, dtype=float), index=spec.dates, columns=list(spec.codes)
        ).to_pickle(Path(root) / "stock_adj.pkl")
    for name, values in spec.factors.items():
        write_factor(root, name, values, spec.dates, spec.codes)

    extra = spec.universe_extra
    if not extra:
        # 不写 universe 快照：``special_no_limit_mask`` 会把窗口内前 5 个交易日
        # 全部判为无涨跌幅（list_date 侧效应），与涨跌停场景冲突。
        return
    write_universe(
        root,
        [dict(row) for row in extra.get("list_rows", [])],
        [dict(row) for row in extra.get("delist_rows", [])],
    )


class _NeverTrigger:
    """永不触发的再平衡触发器（仅注入场景使用，避免 cancel_orders 干扰）。"""

    def should_trigger(self, date: Any, *args: Any, **kwargs: Any) -> bool:
        return False


class _FixedWeightOptimizer:
    """返回固定权重的优化器（S10 权重和 > 1 场景注入）。"""

    def __init__(self, weights: Mapping[str, float]) -> None:
        self._weights = dict(weights)

    def optimize(self, factor_scores: Any, *args: Any, **kwargs: Any) -> pd.Series:
        index = list(factor_scores.index) if hasattr(factor_scores, "index") else []
        values = [float(self._weights.get(str(code), 0.0)) for code in index]
        return pd.Series(values, index=index, dtype=float)


def _inject_orders(engine: BacktestEngineV2, spec: ScenarioSpec) -> None:
    items = spec.config.get("inject_orders", ())
    for item in items:
        order = create_pending_order(
            str(item["code"]),
            OrderSide[str(item["side"])],
            int(item["quantity"]),
            spec.dates[0],
        )
        if item.get("path", "queue") == "queue":
            if engine.pending_queue is None:
                raise ValueError("inject_orders 指定 queue 路径但 cfg.enable_pending_orders=False")
            engine.pending_queue.add_order(order)
        else:
            if not hasattr(engine, "_next_day_orders"):
                engine._next_day_orders = []
            engine._next_day_orders.append(
                {"order": order, "create_date": spec.dates[0], "create_date_index": 0}
            )


def build_scenario(
    spec: ScenarioSpec,
    root: Optional[Path] = None,
    *,
    trace_enabled: bool = True,
) -> ScenarioRun:
    """执行单个场景并返回 trace / 掩码 / 终值。"""
    _validate_spec(spec)
    base = Path(root) if root is not None else Path(tempfile.mkdtemp(prefix="p059_"))
    _write_fixtures(spec, base)

    cfg = build_config(spec, base)
    engine = BacktestEngineV2(cfg)
    engine.setup()

    if spec.signal is not None:
        signal = pd.DataFrame(
            np.asarray(spec.signal, dtype=float),
            index=spec.dates,
            columns=list(spec.codes),
        )
        engine.set_signal(signal, mode=spec.signal_mode)
    if spec.config.get("no_rebalance"):
        engine.trigger = _NeverTrigger()
    if "inject_weights" in spec.config:
        engine.optimizer = _FixedWeightOptimizer(spec.config["inject_weights"])
    _inject_orders(engine, spec)

    trace = TraceRecorder(enabled=trace_enabled)
    trace.attach(engine)
    results = engine.run()
    trace.finalize()

    trade_dates = engine.dm.trade_dates
    limit_up, limit_down = build_limit_prices(
        engine.dm.close, engine.dm.adj_factor, engine.dm.st, trade_dates
    )
    masks = {
        "buyable": engine.universe.buyable,
        "sellable": engine.universe.sellable,
        "tradable": engine.universe.tradable,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "no_limit": special_no_limit_mask(trade_dates, engine.dm.stock_codes, engine.dm.universe),
    }
    return ScenarioRun(
        spec=spec,
        root=base,
        engine=engine,
        results=results,
        trace=trace,
        masks=masks,
        trade_dates=trade_dates,
        ohlc_synthetic=not spec.ohlc_independent,
    )


def _validate_spec(spec: ScenarioSpec) -> None:
    """脏输入守卫（S11）：形状/日期/价格/因子任一非法即 ``ValueError``。"""
    dates = pd.DatetimeIndex(spec.dates)
    if len(dates) == 0:
        raise ValueError(f"{spec.scenario_id}: dates 为空")
    if len(dates) != len(dates.unique()):
        raise ValueError(f"{spec.scenario_id}: dates 存在重复")
    if not dates.is_monotonic_increasing:
        raise ValueError(f"{spec.scenario_id}: dates 必须严格递增")
    if len(spec.codes) == 0:
        raise ValueError(f"{spec.scenario_id}: codes 为空")
    if len(set(spec.codes)) != len(spec.codes):
        raise ValueError(f"{spec.scenario_id}: codes 存在重复")
    if not spec.factors:
        raise ValueError(f"{spec.scenario_id}: factors 为空")
    if spec.kind not in ("backtest", "raises", "stops", "limit_price"):
        raise ValueError(f"{spec.scenario_id}: 未知 kind={spec.kind}")
    if spec.layer not in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        raise ValueError(f"{spec.scenario_id}: 未知 layer={spec.layer}")

    shape = (len(dates), len(spec.codes))
    for name, matrix in (
        ("close", spec.close),
        ("open", spec.open),
        ("high", spec.high),
        ("low", spec.low),
        ("adj", spec.adj),
        ("suspend", spec.suspend),
        ("st", spec.st),
        ("signal", spec.signal),
    ):
        if matrix is None:
            continue
        arr = np.asarray(matrix, dtype=float)
        if arr.shape != shape:
            raise ValueError(f"{spec.scenario_id}: {name} 形状应为 {shape}，实际 {arr.shape}")
        if name in ("close", "open", "high", "low", "adj"):
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"{spec.scenario_id}: {name} 含 NaN/Inf")
            if np.any(arr <= 0):
                raise ValueError(f"{spec.scenario_id}: {name} 存在非正价格")

    for name, matrix in spec.factors.items():
        arr = np.asarray(matrix, dtype=float)
        if arr.shape != shape:
            raise ValueError(
                f"{spec.scenario_id}: factor[{name}] 形状应为 {shape}，实际 {arr.shape}"
            )
