"""目标持仓计算单元测试（T1 / RED）

对应设计文档 DESIGN_critical_rebalance_fix.md §9.1 的 U1–U7。

在 core/target_positions.py 实现之前，本文件预期以 ImportError 失败——
这是 TDD 的 RED 阶段信号。
"""

from __future__ import annotations

import sys
import tempfile
import warnings
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

import pandas as pd

from core.config import (
    BacktestConfig,
    CostConfig,
    OptimizerConfig,
    RebalanceConfig,
)
from core.engine import BacktestEngine
from core.engine_v2 import BacktestEngineV2
from core.pending import OrderSide
from core.target_positions import build_target_positions, compute_portfolio_value

TOTAL_VALUE = 1_000_000.0


class TestBuildTargetPositions(unittest.TestCase):
    """build_target_positions 的行为契约（DESIGN §4.3）"""

    def test_u1_exited_positions_are_liquidated(self):
        """U1 调出清仓：不在目标权重中的持仓必须生成 target=0 的清仓项"""
        weights = pd.Series({"C": 0.5, "D": 0.5})
        current = {"A": 1000, "B": 1000}
        prices = pd.Series({"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0})

        targets = build_target_positions(weights, current, prices, TOTAL_VALUE)

        for stock in ("A", "B"):
            self.assertIn(stock, targets, f"{stock} 应作为清仓项出现在结果中")
            self.assertTrue(targets[stock].is_exit, f"{stock} 应标记为 is_exit")
            self.assertEqual(targets[stock].target_quantity, 0)
            self.assertEqual(targets[stock].current_quantity, 1000)

        for stock in ("C", "D"):
            self.assertIn(stock, targets)
            self.assertFalse(targets[stock].is_exit)
            self.assertGreater(targets[stock].target_quantity, 0)

    def test_u2_partial_reduction(self):
        """U2 部分减仓：目标数量应为正且小于当前持仓，不标记 is_exit"""
        weights = pd.Series({"A": 0.1})
        current = {"A": 20000}
        prices = pd.Series({"A": 10.0})

        target = build_target_positions(weights, current, prices, TOTAL_VALUE)["A"]

        self.assertFalse(target.is_exit)
        self.assertGreater(target.target_quantity, 0)
        self.assertLess(target.target_quantity, 20000)
        # 0.1 * 1e6 * 0.985 / 10 = 9850 → 整手取整 9800
        self.assertEqual(target.target_quantity, 9800)

    def test_u3_new_entry_rounds_to_lot(self):
        """U3 新进建仓：目标数量按整手取整，且应用 0.985 现金缓冲"""
        weights = pd.Series({"A": 0.5})
        current: dict[str, int] = {}
        prices = pd.Series({"A": 33.3})

        target = build_target_positions(weights, current, prices, TOTAL_VALUE)["A"]

        self.assertFalse(target.is_exit)
        self.assertEqual(target.target_quantity % 100, 0)
        # 0.5 * 1e6 * 0.985 / 33.3 = 14789.79 → 147 手 → 14700 股
        self.assertEqual(target.target_quantity, 14700)

    def test_u4_exit_without_price_still_liquidates(self):
        """U4 清仓标的无价格：仍应生成清仓项（数量由持仓决定，价格次日开盘取得）"""
        weights = pd.Series(dtype=float)
        current = {"A": 500}
        prices = pd.Series(dtype=float)

        targets = build_target_positions(weights, current, prices, TOTAL_VALUE)

        self.assertIn("A", targets)
        self.assertTrue(targets["A"].is_exit)
        self.assertEqual(targets["A"].target_quantity, 0)
        self.assertIsNone(targets["A"].price)

    def test_u5_held_without_price_and_still_targeted(self):
        """U5 在场但价格缺失且仍在目标中：维持现状，不产生交易"""
        weights = pd.Series({"A": 0.5})
        current = {"A": 500}
        prices = pd.Series(dtype=float)

        targets = build_target_positions(weights, current, prices, TOTAL_VALUE)

        self.assertIn("A", targets)
        self.assertEqual(targets["A"].target_quantity, 500)
        self.assertEqual(targets["A"].current_quantity, 500)
        self.assertFalse(targets["A"].is_exit)

    def test_u6_invalid_inputs_raise(self):
        """U6 非法输入：total_value<=0 与负权重均应抛 ValueError"""
        prices = pd.Series({"A": 10.0})

        with self.assertRaises(ValueError):
            build_target_positions(pd.Series({"A": 0.5}), {}, prices, 0.0)

        with self.assertRaises(ValueError):
            build_target_positions(pd.Series({"A": -0.1}), {}, prices, TOTAL_VALUE)

    def test_u7_new_entry_without_price_is_omitted(self):
        """U7 空仓且无法定价：无法计算下单数量，不应出现在结果中"""
        weights = pd.Series({"A": 0.5})
        current: dict[str, int] = {}
        prices = pd.Series(dtype=float)

        targets = build_target_positions(weights, current, prices, TOTAL_VALUE)

        self.assertNotIn("A", targets)

    def test_u9_portfolio_value_prefers_prices_then_falls_back(self):
        """U9 组合价值重算：优先用价格，价格缺失时回退到已记录市值"""
        prices = pd.Series({"A": 10.0})
        self.assertAlmostEqual(compute_portfolio_value(1000.0, {"A": 70}, prices), 1700.0)

        missing_prices = pd.Series(dtype=float)
        self.assertAlmostEqual(
            compute_portfolio_value(1000.0, {"A": 70}, missing_prices, {"A": 650.0}),
            1650.0,
        )
        self.assertAlmostEqual(compute_portfolio_value(1000.0, {"A": 70}, missing_prices), 1000.0)


# ============================================================
# 黄金集成测试的确定性场景（DESIGN §9.2）
# ============================================================

DATES = pd.date_range("2024-01-02", periods=4, freq="B")
STOCKS = ["A", "B", "C", "D"]
PRICES = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0}


def _factor_frame() -> pd.DataFrame:
    """d0/d1 由 A、B 领先；d2/d3 切换为 C、D 领先"""
    return pd.DataFrame(
        {
            "A": [4.0, 4.0, 1.0, 1.0],
            "B": [3.0, 3.0, 2.0, 2.0],
            "C": [1.0, 1.0, 4.0, 4.0],
            "D": [2.0, 2.0, 3.0, 3.0],
        },
        index=DATES,
    )


class _FakeDataManager:
    """最小鸭子类型数据管理器：无文件 I/O，价格恒定"""

    def __init__(self):
        self.trade_dates = DATES
        self.stock_codes = list(STOCKS)
        self.n_stocks = len(STOCKS)
        self.returns = pd.DataFrame(0.0, index=DATES, columns=STOCKS)
        self._prices = pd.DataFrame(
            {stock: [price] * len(DATES) for stock, price in PRICES.items()},
            index=DATES,
        )
        self._factors = _factor_frame()

    def get_adj_price(self, price_type: str, adjustment_type: str) -> pd.DataFrame:
        return self._prices

    def load_factor(self, factor_file: str) -> pd.DataFrame:
        return self._factors

    def get_data_info(self) -> dict:
        return {"source": "fake"}


class _FakeUniverse:
    """可交易股票池；blocked_sell_stocks 用于模拟跌停/停牌导致卖不掉"""

    def __init__(self, blocked_sell_stocks=()):
        self._all = pd.DataFrame(True, index=DATES, columns=STOCKS)
        self._sellable = self._all.copy()
        for stock in blocked_sell_stocks:
            self._sellable[stock] = False

    def build_masks(self) -> None:
        return None

    @property
    def buyable(self) -> pd.DataFrame:
        return self._all

    @property
    def sellable(self) -> pd.DataFrame:
        return self._sellable

    @property
    def tradable(self) -> pd.DataFrame:
        return self._all

    def get_mask_summary(self) -> dict:
        return {"source": "fake"}


class _FakePipeline:
    """原样返回，使 V1/V2 的因子输入完全一致"""

    def process(self, raw: pd.DataFrame) -> pd.DataFrame:
        return raw


class _FakeCombiner:
    def __init__(self, *args, **kwargs):
        pass


class _Top2Optimizer:
    """确定性优化器：取因子最高的 2 只等权（模拟 nlargest 语义）"""

    def optimize(self, factor_scores, returns=None, cov_matrix=None) -> pd.Series:
        scores = factor_scores.dropna()
        scores = scores[scores != 0]
        if scores.empty:
            return pd.Series(dtype=float)
        top = scores.nlargest(2)
        return pd.Series(1.0 / len(top), index=top.index)


class _AlwaysTrigger:
    def should_trigger(self, date, **kwargs) -> bool:
        return True


def _build_config(tmpdir: str) -> BacktestConfig:
    """零成本配置：把成本模型噪声从本组断言中隔离"""
    zero_cost = CostConfig(
        commission_rate=0.0,
        commission_min=0.0,
        stamp_tax_rate=0.0,
        slippage_pct=0.0,
    )
    return BacktestConfig(
        data_dir=Path(tmpdir),
        output_dir=Path(tmpdir) / "output",
        factor_files=["dummy.pkl"],
        factor_weights={},
        cost=zero_cost,
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        optimizer=OptimizerConfig(target_count=2, round_lot=True),
        enable_pending_orders=True,
        enable_fallback=False,
        initial_capital=TOTAL_VALUE,
    )


def _run_engine_v2(tmpdir: str, blocked_sell_stocks=()):
    """通过官方依赖注入装配 V2（无文件 I/O）"""
    cfg = _build_config(tmpdir)
    engine = BacktestEngineV2(
        cfg,
        data_manager=_FakeDataManager(),
        universe_filter=_FakeUniverse(blocked_sell_stocks),
        factor_pipeline=_FakePipeline(),
        optimizer=_Top2Optimizer(),
        trigger=_AlwaysTrigger(),
    )
    engine.setup()
    # 保留末态持仓用于断言（强平会清空一切，不在本组测试范围）
    engine._force_liquidation = lambda *args, **kwargs: None
    with patch(
        "core.engine_v2.generate_report",
        return_value={"metrics": {}, "charts": {}, "reports": {}},
    ):
        results = engine.run()
    return engine, results


def _run_engine_v1(tmpdir: str):
    """V1 的 setup() 直接构造组件，故用 patch 注入等价 fake"""
    cfg = _build_config(tmpdir)
    with ExitStack() as stack:
        stack.enter_context(patch("core.engine.DataManager", return_value=_FakeDataManager()))
        stack.enter_context(patch("core.engine.UniverseFilter", return_value=_FakeUniverse()))
        stack.enter_context(patch("core.engine.FactorPipeline", return_value=_FakePipeline()))
        stack.enter_context(patch("core.engine.FactorCombiner", return_value=_FakeCombiner()))
        stack.enter_context(patch("core.engine.build_optimizer", return_value=_Top2Optimizer()))
        stack.enter_context(patch("core.engine.build_trigger", return_value=_AlwaysTrigger()))
        stack.enter_context(
            patch(
                "core.engine.generate_report",
                return_value={"metrics": {}, "charts": {}, "reports": {}},
            )
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            engine = BacktestEngine(cfg)
        engine.setup()
        engine._force_liquidation = lambda *args, **kwargs: None
        results = engine.run()
    return engine, results


def _quantity(engine, stock: str) -> int:
    position = engine.tracker.get_position(stock)
    return int(position.quantity) if position is not None else 0


class TestGoldenRebalanceIntegration(unittest.TestCase):
    """G1–G5：调出组合的持仓必须被卖出（DESIGN §9.2）"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_g1_engine_v2_liquidates_exited_positions(self):
        """G1 第 3 日调仓成交后：A/B 清零，C/D 建仓"""
        engine, _ = _run_engine_v2(self.tmpdir)

        self.assertEqual(_quantity(engine, "A"), 0, "调出的 A 必须被卖出")
        self.assertEqual(_quantity(engine, "B"), 0, "调出的 B 必须被卖出")
        self.assertGreater(_quantity(engine, "C"), 0)
        self.assertGreater(_quantity(engine, "D"), 0)

    def test_g2_engine_v1_liquidates_exited_positions(self):
        """G2 V1（CLI 路径）行为与 V2 一致"""
        engine, _ = _run_engine_v1(self.tmpdir)

        self.assertEqual(_quantity(engine, "A"), 0, "调出的 A 必须被卖出")
        self.assertEqual(_quantity(engine, "B"), 0, "调出的 B 必须被卖出")
        self.assertGreater(_quantity(engine, "C"), 0)
        self.assertGreater(_quantity(engine, "D"), 0)

    def test_g3_engines_share_identical_targets(self):
        """G3 两引擎最近一次目标持仓逐项相等"""
        engine_v1, _ = _run_engine_v1(self.tmpdir)
        engine_v2, _ = _run_engine_v2(self.tmpdir)

        self.assertTrue(hasattr(engine_v1, "_last_targets"), "V1 应记录最近一次目标持仓")
        self.assertTrue(hasattr(engine_v2, "_last_targets"), "V2 应记录最近一次目标持仓")
        self.assertEqual(engine_v1._last_targets, engine_v2._last_targets)

    def test_g4_no_hidden_leverage(self):
        """G4 全程现金不为负（缺陷版本会买入远超可用现金的仓位）"""
        engine, _ = _run_engine_v2(self.tmpdir)

        cash_values = [snapshot.cash for snapshot in engine.tracker.get_snapshots()]
        self.assertTrue(cash_values, "应产生持仓快照")
        self.assertGreaterEqual(min(cash_values), -1e-6)

    def test_g5_sells_precede_buys(self):
        """G5 同一成交日内卖出记录必须早于买入记录"""
        engine, _ = _run_engine_v2(self.tmpdir)
        trades = engine.executor.trade_log.get_trades()

        by_date = defaultdict(list)
        for index, trade in enumerate(trades):
            by_date[trade.date].append((index, trade.side))

        mixed = {
            date: records
            for date, records in by_date.items()
            if any(side == OrderSide.SELL for _, side in records)
            and any(side == OrderSide.BUY for _, side in records)
        }
        self.assertTrue(mixed, "应存在同时含卖出与买入的调仓成交日")

        for date, records in mixed.items():
            sides = [side for _, side in records]
            last_sell = len(sides) - 1 - sides[::-1].index(OrderSide.SELL)
            first_buy = sides.index(OrderSide.BUY)
            self.assertLess(last_sell, first_buy, f"{date} 卖出未先于买入")

    def test_u8_unclosed_positions_reported_when_sell_blocked(self):
        """U8 卖不掉的调出持仓必须出现在 results['unclosed_positions'] 中"""
        _, results = _run_engine_v2(self.tmpdir, blocked_sell_stocks=("A",))

        self.assertIn("unclosed_positions", results)
        self.assertIn("A", results["unclosed_positions"])
        self.assertGreater(results["unclosed_positions"]["A"], 0)
        self.assertNotIn("B", results["unclosed_positions"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
