"""P-047 仓位管理（sizing）单测：V1-V12 + golden（规格锁定，非行为录制）。

设计依据：``docs/DESIGN_p047_position_sizing.md`` §5 测试规格 / §6 不变式 / D6 golden。
取证口径：全部为解析式期望（闭式推导），不使用实现输出自证。

golden 期望值由 D3/D4 闭式推导：
- ``P047_S1``：分数凯利逐标的缩放；
- ``P047_S2``：波动率目标组合缩放（含协方差非对角项）；
- ``P047_S3``：现金预算 floor 整手 + 最低佣金 + 3 次等比收缩。

文件置于 ``tests/golden/p047/`` 子目录，不进入根目录
``test_golden_baseline`` 的 ``glob("*.json") == set(CASE_IDS)`` 断言。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.config import BacktestConfig, CostConfig, OptimizerConfig
from core.engine_v2 import BacktestEngineV2
from core.execution import ExecutionSimulator
from core.pending import OrderSide, PendingOrder, PendingOrderQueue
from core.portfolio import RiskParityOptimizer
from core.sizing import (
    SizingConfig,
    SizingState,
    apply_sizing,
    cash_budget_scale,
    estimate_buy_cash,
    holding_age,
    kelly_fraction_scale,
    pyramid_step,
    risk_contributions,
    vol_target_scale,
)
from core.tracker import PositionTracker

# ---------------------------------------------------------------------------
# V1 method="none" 幂等
# ---------------------------------------------------------------------------


def test_v1_none_is_identity():
    cfg = SizingConfig()
    weights = {"A": 0.3, "B": 0.2}
    result = apply_sizing(weights, config=cfg)
    assert dict(result.weights) == weights
    assert result.weights is not weights  # 返回副本
    assert result.scale == 1.0
    assert dict(result.diagnostics.reasons) == {}
    assert result.diagnostics.dropped == ()
    assert result.diagnostics.clipped == ()


# ---------------------------------------------------------------------------
# V2 凯利闭式
# ---------------------------------------------------------------------------


def test_v2_kelly_closed_form():
    # f* = μ/σ² = 0.01/0.04 = 0.25；半凯利 → 0.125
    scale, reason = kelly_fraction_scale(0.01, 0.04, fraction=0.5)
    assert scale == pytest.approx(0.125)
    assert reason == ""

    codes = ["A", "B"]
    cov = np.diag([0.04, 0.09])
    expected = {"A": 0.01, "B": 0.03}
    result = apply_sizing(
        {"A": 0.5, "B": 0.5},
        config=SizingConfig(method="kelly", kelly_fraction=0.5),
        cov=cov,
        codes=codes,
        expected_returns=expected,
    )
    # A: 0.5*0.01/0.04=0.125 → 0.5*0.125=0.0625
    # B: 0.5*0.03/0.09=0.1666667 → 0.5*0.1666667=0.0833333
    assert result.weights["A"] == pytest.approx(0.0625)
    assert result.weights["B"] == pytest.approx(0.0833333333)
    assert result.scale == pytest.approx((0.0625 + 0.0833333333) / 1.0)


# ---------------------------------------------------------------------------
# V3 凯利边界
# ---------------------------------------------------------------------------


def test_v3_kelly_boundaries():
    assert kelly_fraction_scale(0.0, 0.04) == (0.0, "non_positive_edge")
    assert kelly_fraction_scale(-0.01, 0.04) == (0.0, "non_positive_edge")
    assert kelly_fraction_scale(0.01, 0.0) == (0.0, "zero_var")
    # 0.5 * 2.5 = 1.25 → clip 到 1.0
    assert kelly_fraction_scale(2.5, 1.0, fraction=0.5) == (1.0, "clipped_max")
    with pytest.raises(ValueError):
        kelly_fraction_scale(0.01, 0.04, fraction=0.0)
    with pytest.raises(ValueError):
        kelly_fraction_scale(0.01, 0.04, fraction=1.1)


# ---------------------------------------------------------------------------
# V4 vol-target 闭式
# ---------------------------------------------------------------------------


def test_v4_vol_target_closed_form():
    codes = ["A", "B"]
    cov = np.diag([0.04, 0.09])
    weights = {"A": 0.5, "B": 0.5}
    # σ_p = sqrt(0.25*0.04 + 0.25*0.09) = sqrt(0.0325)
    sigma_p = math.sqrt(0.0325)
    expected_scale = 0.15 / sigma_p
    scaled, scale, reason = vol_target_scale(weights, cov, codes=codes, target_vol=0.15)
    assert reason == ""
    assert scale == pytest.approx(expected_scale)
    assert scaled["A"] == pytest.approx(0.5 * expected_scale)
    assert scaled["B"] == pytest.approx(0.5 * expected_scale)
    # 目标波动高于实际 → 不放大（scale 上限 1.0）
    _, scale_low, _ = vol_target_scale(weights, cov, codes=codes, target_vol=1.0)
    assert scale_low == 1.0


# ---------------------------------------------------------------------------
# V5 σ_p = 0
# ---------------------------------------------------------------------------


def test_v5_zero_vol():
    codes = ["A", "B"]
    cov = np.diag([0.04, 0.09])
    weights = {"A": 0.0, "B": 0.0}
    scaled, scale, reason = vol_target_scale(weights, cov, codes=codes)
    assert reason == "zero_vol"
    assert scale == 1.0
    assert dict(scaled) == weights


# ---------------------------------------------------------------------------
# V6 风险贡献 / I10 等预算对拍
# ---------------------------------------------------------------------------


def test_v6_risk_contributions():
    codes = ["A", "B"]
    cov = np.diag([0.04, 0.04])
    weights = {"A": 0.5, "B": 0.5}
    rc = risk_contributions(weights, cov, codes=codes)
    sigma_p = math.sqrt(0.5**2 * 0.04 + 0.5**2 * 0.04)
    assert sum(rc.rc.values()) == pytest.approx(sigma_p)
    assert sum(rc.pct.values()) == pytest.approx(1.0)
    # 等权 + 等波动 + 不相关 → 等风险贡献
    assert rc.pct["A"] == pytest.approx(0.5)
    assert rc.pct["B"] == pytest.approx(0.5)


def test_v6_risk_parity_equal_budget_crosscheck():
    """I10：与 RiskParityOptimizer 对拍（显式 max_weight=1.0，F-S4-P047-1）。"""
    codes = ["A", "B", "C"]
    cov = pd.DataFrame(
        [[0.04, 0.008, 0.006], [0.008, 0.09, 0.012], [0.006, 0.012, 0.16]],
        index=codes,
        columns=codes,
    )
    scores = pd.Series([3.0, 2.0, 1.0], index=codes)
    optimizer = RiskParityOptimizer(
        OptimizerConfig(target_count=3, select_top=True, max_weight=1.0)
    )
    weights = optimizer.optimize(scores, cov_matrix=cov)
    rc = risk_contributions({code: float(weights[code]) for code in codes}, cov.values, codes=codes)
    for code in codes:
        assert rc.pct[code] == pytest.approx(1.0 / 3.0, abs=1e-3)


# ---------------------------------------------------------------------------
# V7 权重 / 金额裁剪
# ---------------------------------------------------------------------------


def test_v7_weight_clip_and_size_filter():
    cfg = SizingConfig(method="none", max_weight=0.4)
    result = apply_sizing({"A": 0.7, "B": 0.3}, config=cfg)
    assert result.weights["A"] == pytest.approx(0.4)
    assert result.weights["B"] == pytest.approx(0.3)
    assert "A" in result.diagnostics.clipped

    cfg_size = SizingConfig(method="none", min_size=10_000.0, max_size=30_000.0)
    result_size = apply_sizing(
        {"A": 0.05, "B": 0.25, "C": 0.6},
        config=cfg_size,
        total_value=100_000.0,
        prices={"A": 10.0, "B": 10.0, "C": 10.0},
    )
    # A: 5,000 < min_size → 剔除，余额留现金（不归一化）
    assert result_size.weights["A"] == 0.0
    assert "A" in result_size.diagnostics.dropped
    # B: 25,000 ∈ [min_size, max_size] → 原样保留
    assert result_size.weights["B"] == pytest.approx(0.25)
    # C: 60,000 > max_size → 0.3；总权重 0.25+0.3=0.55 ≤ 1
    assert result_size.weights["C"] == pytest.approx(0.3)
    assert "C" in result_size.diagnostics.clipped
    assert sum(result_size.weights.values()) <= 1.0 + 1e-12


def test_v7_total_weight_never_exceeds_one():
    result = apply_sizing({"A": 0.8, "B": 0.8}, config=SizingConfig(method="none"))
    assert sum(result.weights.values()) == pytest.approx(1.0)
    assert result.scale == pytest.approx(0.625)


# ---------------------------------------------------------------------------
# V8 现金预算
# ---------------------------------------------------------------------------


def test_v8_cash_budget_floor_and_min_commission():
    cfg = SizingConfig()
    result = cash_budget_scale(
        {"A": 0.5, "B": 0.5},
        cash=100_000.0,
        prices={"A": 10.0, "B": 25.0},
        total_value=100_000.0,
        config=cfg,
    )
    # A: 0.5*0.985*100000/10 = 4925 → floor 4900 股 → 49,000 元
    # B: 0.5*0.985*100000/25 = 1970 → floor 1900 股 → 47,500 元
    assert result.scale == 1.0
    assert result.budget == pytest.approx(98_500.0)
    assert result.weights["A"] == pytest.approx(0.49)
    assert result.weights["B"] == pytest.approx(0.475)
    expected_cost = (49_000 + max(49_000 * 0.0003, 5.0) + 49.0) + (
        47_500 + max(47_500 * 0.0003, 5.0) + 47.5
    )
    assert result.buy_cost == pytest.approx(expected_cost)
    assert result.buy_cost <= result.budget


def test_v8_cash_budget_shrinks_when_over_budget():
    cfg = SizingConfig()
    result = cash_budget_scale(
        {"A": 1.0}, cash=1_000.0, prices={"A": 10.0}, total_value=100_000.0, config=cfg
    )
    assert result.buy_cost <= result.budget
    # 预算 985 元 < 1 手 1,000 元 → 无法成交任何整手
    assert result.weights["A"] == 0.0
    assert result.buy_cost == 0.0


def test_v8_zero_quantity_costs_nothing():
    """F-S4-P047-2：qty=0 的空单不计最低佣金。"""
    assert (
        estimate_buy_cash(0.0, commission_rate=0.0003, commission_min=5.0, slippage_pct=0.001)
        == 0.0
    )
    result = cash_budget_scale(
        {"A": 1.0}, cash=100.0, prices={"A": 1_000.0}, total_value=100.0, config=SizingConfig()
    )
    assert result.weights["A"] == 0.0
    assert result.buy_cost == 0.0


# ---------------------------------------------------------------------------
# V9 成本同源（与 ExecutionSimulator._calculate_cost 净现金式对拍）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("amount", [1_000.0, 5_000.0, 100_000.0])
def test_v9_cost_same_source(amount: float):
    cost_cfg = CostConfig()
    simulator = ExecutionSimulator(cost_cfg)
    exact = estimate_buy_cash(
        amount,
        commission_rate=cost_cfg.commission_rate,
        commission_min=cost_cfg.commission_min,
        slippage_pct=cost_cfg.slippage_pct,
    )
    net_cash = amount + simulator._calculate_cost(amount, OrderSide.BUY)
    assert exact == pytest.approx(net_cash)


# ---------------------------------------------------------------------------
# V10 金字塔加减仓
# ---------------------------------------------------------------------------


def test_v10_pyramid_adds_only_on_profit_and_decays():
    cfg = SizingConfig(
        pyramid_enabled=True, pyramid_max_adds=3, pyramid_decay=0.5, pyramid_step_atr=1.0
    )
    state = SizingState(entry_price=100.0, last_add_price=100.0, add_count=0)

    # 未达 1×ATR（2 元）阈值 → 不加
    same_state, increment = pyramid_step(state, price=101.0, atr=2.0, config=cfg)
    assert increment == 0.0
    assert same_state == state

    # 浮亏 → 禁摊亏（I6）
    _, increment_loss = pyramid_step(state, price=99.0, atr=2.0, config=cfg)
    assert increment_loss == 0.0

    # 达到阈值 → 首次加仓幅度 = 1.0，并推进水位
    new_state, increment_1 = pyramid_step(state, price=102.0, atr=2.0, config=cfg)
    assert increment_1 == pytest.approx(1.0)
    assert new_state.add_count == 1
    assert new_state.last_add_price == pytest.approx(102.0)
    assert new_state.entry_price == pytest.approx(100.0)

    # 自新水位再涨 1×ATR → 递减（0.5）
    _, increment_2 = pyramid_step(new_state, price=104.0, atr=2.0, config=cfg)
    assert increment_2 == pytest.approx(0.5)


def test_v10_pyramid_respects_max_adds_and_switch():
    cfg = SizingConfig(pyramid_enabled=True, pyramid_max_adds=1)
    state = SizingState(entry_price=100.0, last_add_price=100.0, add_count=1)
    _, increment = pyramid_step(state, price=200.0, atr=2.0, config=cfg)
    assert increment == 0.0

    disabled = SizingConfig(pyramid_enabled=False)
    _, increment_off = pyramid_step(
        SizingState(entry_price=100.0, last_add_price=100.0),
        price=200.0,
        atr=2.0,
        config=disabled,
    )
    assert increment_off == 0.0


# ---------------------------------------------------------------------------
# V11 持仓龄
# ---------------------------------------------------------------------------


def test_v11_holding_age_counts_trading_bars():
    dates = pd.bdate_range("2024-01-02", periods=5)
    assert holding_age(dates[0], dates[0], dates) == 1  # 建仓日 = 1
    assert holding_age(dates[0], dates[1], dates) == 2
    assert holding_age(dates[0], dates[4], dates) == 5
    assert holding_age(dates[1], dates[3], dates) == 3
    with pytest.raises(ValueError):
        holding_age(dates[2], dates[1], dates)


# ---------------------------------------------------------------------------
# V12 引擎队列路径最小 BUY 现金闸门（A2）
# ---------------------------------------------------------------------------


class _FakeDataManager:
    """最小数据管理器：仅提供 open 价矩阵与空 returns。"""

    def __init__(self, date: pd.Timestamp, prices: dict[str, float]):
        self.returns = pd.Series(dtype=float)
        self._prices = pd.DataFrame({code: [price] for code, price in prices.items()}, index=[date])

    def get_adj_price(self, kind: str, mode: str = "raw") -> pd.DataFrame:
        return self._prices


class _FakeUniverse:
    def __init__(self, date: pd.Timestamp, codes: tuple[str, ...] = ("AAA",)):
        self.buyable = pd.DataFrame({code: [True] for code in codes}, index=[date])
        self.sellable = pd.DataFrame({code: [True] for code in codes}, index=[date])


def _make_engine(cash: float, open_price: float = 10.0):
    date = pd.Timestamp("2024-01-02")
    cfg = BacktestConfig()
    tracker = PositionTracker(n_stocks=1, initial_capital=cash)
    queue = PendingOrderQueue()
    engine = BacktestEngineV2(
        cfg,
        executor=ExecutionSimulator(cfg.cost),
        tracker=tracker,
        pending_queue=queue,
    )
    engine.dm = _FakeDataManager(date, {"AAA": open_price})  # type: ignore[assignment]
    engine.universe = _FakeUniverse(date)  # type: ignore[assignment]
    engine.executor = engine._injected_executor  # type: ignore[assignment]
    engine.tracker = tracker  # type: ignore[assignment]
    engine.pending_queue = queue  # type: ignore[assignment]
    return engine, queue, tracker, date


def test_v12_gate_skips_buy_when_cash_insufficient():
    engine, queue, tracker, date = _make_engine(cash=1_000.0)
    order = PendingOrder(stock="AAA", side=OrderSide.BUY, quantity=1_000, create_date=date)
    queue.add_order(order)

    engine._process_pending_orders(date, date_index=0)

    # 需要 10,000 + 5.0… > 1,000 → 整单跳过；现金不动、持仓为空、订单保留
    assert tracker.get_cash() == pytest.approx(1_000.0)
    assert tracker.get_position("AAA") is None
    assert queue.get_pending_orders() == [order]


def test_v12_gate_allows_buy_when_cash_sufficient():
    engine, queue, tracker, date = _make_engine(cash=20_000.0)
    order = PendingOrder(stock="AAA", side=OrderSide.BUY, quantity=1_000, create_date=date)
    queue.add_order(order)

    engine._process_pending_orders(date, date_index=0)

    position = tracker.get_position("AAA")
    assert position is not None
    assert position.quantity == 1_000
    required = estimate_buy_cash(
        10_000.0,
        commission_rate=engine.cfg.cost.commission_rate,
        commission_min=engine.cfg.cost.commission_min,
        slippage_pct=engine.cfg.cost.slippage_pct,
    )
    assert tracker.get_cash() == pytest.approx(20_000.0 - required)
    assert queue.get_pending_orders() == []


def test_v12_gate_continues_to_later_orders_after_skip():
    """闸门语义 = ``continue`` 而非 ``break``：被拒 BUY 之后的小额 BUY 仍处理（§5 V12）。"""
    date = pd.Timestamp("2024-01-02")
    cfg = BacktestConfig()
    tracker = PositionTracker(n_stocks=2, initial_capital=3_000.0)
    queue = PendingOrderQueue()
    engine = BacktestEngineV2(
        cfg,
        executor=ExecutionSimulator(cfg.cost),
        tracker=tracker,
        pending_queue=queue,
    )
    engine.dm = _FakeDataManager(date, {"AAA": 10.0, "BBB": 5.0})  # type: ignore[assignment]
    engine.universe = _FakeUniverse(date, ("AAA", "BBB"))  # type: ignore[assignment]
    engine.executor = engine._injected_executor  # type: ignore[assignment]
    engine.tracker = tracker  # type: ignore[assignment]
    engine.pending_queue = queue  # type: ignore[assignment]

    big = PendingOrder(stock="AAA", side=OrderSide.BUY, quantity=1_000, create_date=date)
    small = PendingOrder(stock="BBB", side=OrderSide.BUY, quantity=100, create_date=date)
    queue.add_order(big)
    queue.add_order(small)

    engine._process_pending_orders(date, date_index=0)

    # 需 10,000+费 > 3,000 → 整单跳过且保留；后续小额单继续处理
    assert tracker.get_position("AAA") is None
    assert tracker.get_position("BBB") is not None
    required_small = estimate_buy_cash(
        500.0,
        commission_rate=engine.cfg.cost.commission_rate,
        commission_min=engine.cfg.cost.commission_min,
        slippage_pct=engine.cfg.cost.slippage_pct,
    )
    assert tracker.get_cash() == pytest.approx(3_000.0 - required_small)
    assert queue.get_pending_orders() == [big]


# ---------------------------------------------------------------------------
# golden（D6：3 例规格锁定，独立子目录）
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).parent / "golden" / "p047"
CASE_IDS = ("P047_S1", "P047_S2", "P047_S3")


def _load_case(case_id: str) -> dict:
    return json.loads((GOLDEN_DIR / f"{case_id}.json").read_text(encoding="utf-8"))


def test_p047_case_files_isolated_from_root_baseline():
    """3 个 case 文件仅存在于 p047 子目录，不污染根目录基线断言。"""
    assert {path.stem for path in GOLDEN_DIR.glob("*.json")} == set(CASE_IDS)
    root_cases = {path.stem for path in GOLDEN_DIR.parent.glob("*.json")}
    assert not (set(CASE_IDS) & root_cases)


def test_p047_golden_kelly():
    payload = _load_case("P047_S1")
    inputs = payload["inputs"]
    result = apply_sizing(
        inputs["weights"],
        config=SizingConfig(**payload["config"]),
        cov=np.array(inputs["cov"], dtype=float),
        codes=inputs["codes"],
        expected_returns=inputs["expected_returns"],
    )
    expected = payload["expected"]
    tolerance = payload["tolerance"]
    for code, weight in expected["weights"].items():
        assert result.weights[code] == pytest.approx(
            weight, rel=tolerance["rtol"], abs=tolerance["atol"]
        )
    assert result.scale == pytest.approx(
        expected["scale"], rel=tolerance["rtol"], abs=tolerance["atol"]
    )
    assert dict(result.diagnostics.reasons) == expected["reasons"]


def test_p047_golden_vol_target():
    payload = _load_case("P047_S2")
    inputs = payload["inputs"]
    result = apply_sizing(
        inputs["weights"],
        config=SizingConfig(**payload["config"]),
        cov=np.array(inputs["cov"], dtype=float),
        codes=inputs["codes"],
    )
    expected = payload["expected"]
    tolerance = payload["tolerance"]
    for code, weight in expected["weights"].items():
        assert result.weights[code] == pytest.approx(
            weight, rel=tolerance["rtol"], abs=tolerance["atol"]
        )
    assert result.scale == pytest.approx(
        expected["scale"], rel=tolerance["rtol"], abs=tolerance["atol"]
    )
    assert dict(result.diagnostics.reasons) == expected["reasons"]


def test_p047_golden_cash_budget():
    payload = _load_case("P047_S3")
    inputs = payload["inputs"]
    expected = payload["expected"]
    tolerance = payload["tolerance"]
    result = cash_budget_scale(
        inputs["weights"],
        cash=inputs["cash"],
        prices=inputs["prices"],
        total_value=inputs["total_value"],
        config=SizingConfig(**payload["config"]),
    )
    for code, weight in expected["weights"].items():
        assert result.weights[code] == pytest.approx(
            weight, rel=tolerance["rtol"], abs=tolerance["atol"]
        )
        # floor 整手锁定：由权重反推的数量必须是整手
        qty = round(result.weights[code] * inputs["total_value"] / inputs["prices"][code])
        assert qty == expected["qty"][code]
        assert qty % payload["config"]["granularity"] == 0
    assert result.buy_cost == pytest.approx(
        expected["buy_cost"], rel=tolerance["rtol"], abs=tolerance["atol"]
    )
    assert result.budget == pytest.approx(
        expected["budget"], rel=tolerance["rtol"], abs=tolerance["atol"]
    )
    assert result.buy_cost <= result.budget
    assert result.scale == pytest.approx(
        expected["scale"], rel=tolerance["rtol"], abs=tolerance["atol"]
    )
    assert (result.scale < 1.0) is expected["scale_lt_one"]
