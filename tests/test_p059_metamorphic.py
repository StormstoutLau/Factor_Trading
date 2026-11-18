"""P-059 变质关系测试（DESIGN §7 / Step 5 T8）。

三条关系（逐场景声明 ≥1 条）：
- R1 ``scale(k)``：价格 × k **且** ``initial_capital × k`` → 成交笔数 / 持仓股数不变，
  金额类指标按 k 等比缩放（A2：不作为新的闭式值来源，只做关系比较）。
- R2 ``inert(code)``：追加一只永不入目标、永不成交的惰性标的（因子 NaN、信号 0）
  → 现金 / NAV / 成交逐日完全一致。
- R3 ``shift(days)``：交易日整体平移 → 桶数一致、逐日金额与持仓一致（日期随之平移）。

两条硬前提（DESIGN §7.1）：
- R1 不用于现金类阈值会翻转的场景（S09 走 R2）；
- ``scale`` 的 k 必须远离整手 floor 边界（本文件只使用声明中的 k，不再自选）。
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
import pandas as pd
import pytest

from _scenarios_builder import DEFAULT_CAPITAL, build_scenario
from _scenarios_cases import SCENARIOS
from _scenarios_spec import Metamorphic, ScenarioSpec

MONEY_RTOL = 1e-9
MONEY_ATOL = 1e-6


# ---------------------------------------------------------------------------
# 变换
# ---------------------------------------------------------------------------
def _scale_matrix(matrix: Any, k: float) -> Any:
    return None if matrix is None else np.asarray(matrix, dtype=float) * k


def _scale_spec(spec: ScenarioSpec, k: float) -> ScenarioSpec:
    """R1：价格四键 × k，初始资金 × k（复权因子是相对量，不缩放）。"""
    config = dict(spec.config)
    config["initial_capital"] = float(config.get("initial_capital", DEFAULT_CAPITAL)) * k
    return dataclasses.replace(
        spec,
        close=_scale_matrix(spec.close, k),
        open=_scale_matrix(spec.open, k),
        high=_scale_matrix(spec.high, k),
        low=_scale_matrix(spec.low, k),
        config=config,
        metamorphic=(),
    )


def _append_column(matrix: Any, column: np.ndarray) -> Any:
    if matrix is None:
        return None
    return np.column_stack([np.asarray(matrix, dtype=float), column])


def _inert_spec(spec: ScenarioSpec, code: str) -> ScenarioSpec:
    """R2：追加惰性标的（价格常量 10、因子 NaN、信号 0、不 ST 不停牌）。"""
    n = len(spec.dates)
    assert code not in spec.codes, f"{spec.scenario_id}: 惰性标的 {code} 已在 codes 中"
    price_col = np.full((n, 1), 10.0)
    nan_col = np.full((n, 1), np.nan)
    zero_col = np.zeros((n, 1), dtype=int)
    return dataclasses.replace(
        spec,
        codes=spec.codes + (code,),
        close=_append_column(spec.close, price_col),
        open=_append_column(spec.open, price_col),
        high=_append_column(spec.high, price_col),
        low=_append_column(spec.low, price_col),
        adj=_append_column(spec.adj, np.ones((n, 1))),
        suspend=_append_column(spec.suspend, zero_col),
        st=_append_column(spec.st, zero_col),
        factors={
            name: np.column_stack([np.asarray(values, dtype=float), nan_col[:, 0]])
            for name, values in spec.factors.items()
        },
        signal=_append_column(spec.signal, np.zeros((n, 1))),
        metamorphic=(),
    )


def _shift_dates(rows: Any, offset: pd.Timedelta) -> Any:
    shifted = []
    for row in rows:
        item = dict(row)
        for key in ("list_date", "delist_date"):
            if key in item:
                item[key] = (pd.Timestamp(item[key]) + offset).strftime("%Y-%m-%d")
        shifted.append(item)
    return shifted


def _shift_spec(spec: ScenarioSpec, days: int) -> ScenarioSpec:
    """R3：交易日整体平移（上市/退市日期同步平移，避免跨状态边界）。"""
    offset = pd.Timedelta(days=days)
    extra = {}
    for key, rows in spec.universe_extra.items():
        extra[key] = _shift_dates(rows, offset) if isinstance(rows, (list, tuple)) else rows
    return dataclasses.replace(
        spec,
        dates=pd.DatetimeIndex(spec.dates) + offset,
        universe_extra=extra,
        metamorphic=(),
    )


# ---------------------------------------------------------------------------
# 比较原语（失败时汇报首个分歧桶 + 字段）
# ---------------------------------------------------------------------------
def _close(expected: float, actual: float) -> bool:
    return math.isclose(actual, expected, rel_tol=MONEY_RTOL, abs_tol=MONEY_ATOL)


def _fail(spec: ScenarioSpec, relation: Metamorphic, where: str, field: str, want: Any, got: Any):
    raise AssertionError(
        f"{spec.scenario_id}/{relation.kind}: {where} 字段 {field} 期望 {want!r} 实际 {got!r}"
    )


def _compare_buckets(
    spec: ScenarioSpec, relation: Metamorphic, base_run: Any, variant_run: Any, scale: float
) -> None:
    base_dates = sorted(base_run.trace.buckets)
    variant_dates = sorted(variant_run.trace.buckets)
    if len(base_dates) != len(variant_dates):
        _fail(spec, relation, "buckets", "count", len(base_dates), len(variant_dates))

    offset = pd.Timedelta(days=relation.days) if relation.kind == "shift" else None

    for base_key, variant_key in zip(base_dates, variant_dates):
        if offset is not None:
            want_key = (pd.Timestamp(base_key) + offset).strftime("%Y-%m-%d")
            if want_key != variant_key:
                _fail(spec, relation, base_key, "date", want_key, variant_key)
        elif base_key != variant_key:
            _fail(spec, relation, base_key, "date", base_key, variant_key)

        base = base_run.trace.buckets[base_key]
        variant = variant_run.trace.buckets[variant_key]

        for field in ("cash", "nav"):
            if not _close(base[field] * scale, variant[field]):
                _fail(spec, relation, base_key, field, base[field] * scale, variant[field])
        if base["positions"] != variant["positions"]:
            _fail(spec, relation, base_key, "positions", base["positions"], variant["positions"])

        base_fills, variant_fills = base["filled"], variant["filled"]
        if len(base_fills) != len(variant_fills):
            _fail(spec, relation, base_key, "filled.count", len(base_fills), len(variant_fills))
        for left, right in zip(base_fills, variant_fills):
            for field in ("code", "side", "quantity"):
                if left[field] != right[field]:
                    _fail(spec, relation, base_key, f"filled.{field}", left[field], right[field])
            if not _close(left["price"] * scale, right["price"]):
                _fail(
                    spec, relation, base_key, "filled.price", left["price"] * scale, right["price"]
                )


def _compare_fills(
    spec: ScenarioSpec, relation: Metamorphic, base_run: Any, variant_run: Any, scale: float
) -> None:
    base_fills = list(base_run.trace.fills)
    variant_fills = list(variant_run.trace.fills)
    if len(base_fills) != len(variant_fills):
        _fail(spec, relation, "<fills>", "count", len(base_fills), len(variant_fills))

    offset = pd.Timedelta(days=relation.days) if relation.kind == "shift" else None
    for left, right in zip(base_fills, variant_fills):
        for field in ("code", "side", "quantity"):
            if left[field] != right[field]:
                _fail(spec, relation, left["date"], f"fill.{field}", left[field], right[field])
        want_date = (
            (pd.Timestamp(left["date"]) + offset).strftime("%Y-%m-%d")
            if offset is not None
            else left["date"]
        )
        if want_date != right["date"]:
            _fail(spec, relation, left["date"], "fill.date", want_date, right["date"])
        for field in ("price", "amount", "cost"):
            if not _close(left[field] * scale, right[field]):
                _fail(
                    spec, relation, left["date"], f"fill.{field}", left[field] * scale, right[field]
                )


def _assert_relation(spec: ScenarioSpec, relation: Metamorphic, tmp_path: Any) -> None:
    base = build_scenario(spec, tmp_path / "base")

    if relation.kind == "scale":
        variant = build_scenario(
            _scale_spec(spec, relation.k), tmp_path / "variant", trace_enabled=True
        )
        scale = relation.k
    elif relation.kind == "inert":
        variant = build_scenario(_inert_spec(spec, relation.code), tmp_path / "variant")
        scale = 1.0
    elif relation.kind == "shift":
        variant = build_scenario(_shift_spec(spec, relation.days), tmp_path / "variant")
        scale = 1.0
    else:  # pragma: no cover - 声明侧已受限
        raise AssertionError(f"未知变质关系 {relation.kind}")

    _compare_fills(spec, relation, base, variant, scale)
    _compare_buckets(spec, relation, base, variant, scale)


# ---------------------------------------------------------------------------
# 注册契约 + 参数化
# ---------------------------------------------------------------------------
RELATIONS = [(spec, relation) for spec in SCENARIOS.values() for relation in spec.metamorphic]
RELATION_IDS = [f"{spec.scenario_id}-{relation.kind}" for spec, relation in RELATIONS]


def test_every_backtest_scenario_declares_relation() -> None:
    """DESIGN §7.1：每条 backtest 场景至少声明 1 条变质关系，且三条关系全覆盖。"""
    missing = [
        spec.scenario_id
        for spec in SCENARIOS.values()
        if spec.kind == "backtest" and not spec.metamorphic
    ]
    assert not missing, f"缺少变质关系声明：{missing}"

    kinds = {relation.kind for _, relation in RELATIONS}
    assert kinds == {"scale", "inert", "shift"}, f"关系覆盖不全：{sorted(kinds)}"
    for spec, relation in RELATIONS:
        assert relation.kind in {"scale", "inert", "shift"}, f"{spec.scenario_id}: 未知关系"
        if relation.kind == "scale":
            assert relation.k > 0, f"{spec.scenario_id}: scale 的 k 必须为正"
        if relation.kind == "inert":
            assert (
                relation.code and relation.code not in spec.codes
            ), f"{spec.scenario_id}: 惰性标的 {relation.code!r} 必须是非既有代码"
        if relation.kind == "shift":
            assert relation.days != 0, f"{spec.scenario_id}: shift 天数不得为 0"


@pytest.mark.parametrize(("spec", "relation"), RELATIONS, ids=RELATION_IDS)
def test_p059_metamorphic(spec: ScenarioSpec, relation: Metamorphic, tmp_path: Any) -> None:
    """R1/R2/R3：base 与变换体各跑一次，比较相对量与逐日轨迹（I9-I11）。"""
    _assert_relation(spec, relation, tmp_path)
