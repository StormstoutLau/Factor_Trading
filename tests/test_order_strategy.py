"""
订单策略测试

验证 TWAP/VWAP/Iceberg 策略的正确性。
"""

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from order_strategy.strategies import (
    MarketOrderStrategy,
    TWAPStrategy,
    VWAPStrategy,
    IcebergStrategy,
    MarketImpactModel,
)
from order_strategy.evaluator import OrderStrategyEvaluator


class TestMarketImpactModel(unittest.TestCase):
    """测试市场冲击模型"""

    def test_calculate_impact(self):
        model = MarketImpactModel()
        impact = model.calculate_impact(10000, {"volume": 1000000})
        self.assertGreater(impact, 0)
        self.assertLess(impact, 0.1)

    def test_impact_scales_with_qty(self):
        model = MarketImpactModel()
        impact_small = model.calculate_impact(1000, {"volume": 1000000})
        impact_large = model.calculate_impact(100000, {"volume": 1000000})
        self.assertLess(impact_small, impact_large)


class TestOrderStrategies(unittest.TestCase):
    """测试各种订单策略"""

    def setUp(self):
        """测试准备"""
        self.market_data = []
        base_price = 100.0
        for i in range(20):
            price = base_price * (1 + np.random.randn() * 0.01)
            self.market_data.append({
                "price": price,
                "close": price,
                "volume": 1000000,
            })
            base_price = price

    def test_market_order(self):
        """测试市价单策略"""
        strategy = MarketOrderStrategy()
        trades = strategy.execute(
            symbol="TEST",
            side="BUY",
            qty=10000,
            timestamp=0,
            market_data={"price": 100.0},
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].qty, 10000)

    def test_twap_execution(self):
        """测试 TWAP 策略执行"""
        strategy = TWAPStrategy({"intervals": 10})
        total_trades = []

        for i in range(15):
            trades = strategy.execute(
                symbol="TEST",
                side="BUY",
                qty=10000,
                timestamp=i,
                market_data=self.market_data[i],
            )
            total_trades.extend(trades)

        total_qty = sum(t.qty for t in total_trades)
        self.assertEqual(total_qty, 10000)
        self.assertEqual(len(total_trades), 10)  # 分10次执行

    def test_vwap_execution(self):
        """测试 VWAP 策略"""
        strategy = VWAPStrategy()
        total_trades = []

        for i in range(15):
            trades = strategy.execute(
                symbol="TEST",
                side="BUY",
                qty=10000,
                timestamp=i,
                market_data=self.market_data[i],
            )
            total_trades.extend(trades)

        total_qty = sum(t.qty for t in total_trades)
        self.assertEqual(total_qty, 10000)

    def test_iceberg_execution(self):
        """测试冰山策略"""
        strategy = IcebergStrategy({"visible_size": 1000})
        total_trades = []

        for i in range(20):
            trades = strategy.execute(
                symbol="TEST",
                side="BUY",
                qty=10000,
                timestamp=i,
                market_data=self.market_data[i],
            )
            total_trades.extend(trades)

        total_qty = sum(t.qty for t in total_trades)
        self.assertEqual(total_qty, 10000)
        # 每笔成交应该小于等于可见数量
        for t in total_trades:
            self.assertLessEqual(t.qty, 1000)


class TestStrategyEvaluator(unittest.TestCase):
    """测试策略评估器"""

    def test_evaluate_strategy(self):
        """测试策略评估"""
        market_data = [{"price": 100.0 + i * 0.5, "volume": 1000000} for i in range(20)]
        evaluator = OrderStrategyEvaluator(market_data)

        strategy = TWAPStrategy({"intervals": 10})
        result = evaluator.evaluate_strategy(strategy, "TEST", "BUY", 10000)

        self.assertEqual(result.total_qty, 10000)
        self.assertGreater(result.avg_price, 0)

    def test_compare_strategies(self):
        """测试多策略对比"""
        market_data = [{"price": 100.0 + i * 0.5, "volume": 1000000} for i in range(20)]
        evaluator = OrderStrategyEvaluator(market_data)

        results = evaluator.evaluate_all_strategies("TEST", "BUY", 10000)

        self.assertIn("MarketOrderStrategy", results)
        self.assertIn("TWAPStrategy", results)
        self.assertIn("VWAPStrategy", results)
        self.assertIn("IcebergStrategy", results)


if __name__ == "__main__":
    unittest.main()

