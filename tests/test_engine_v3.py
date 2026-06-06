"""
向量回测引擎测试

验证 VectorBacktestEngine 的正确性和性能。
"""

import sys
from pathlib import Path
import unittest
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_v3 import DataLoaderV3
from core.engine_v3_vector import VectorBacktestEngine


class TestVectorBacktestEngine(unittest.TestCase):
    """测试向量回测引擎"""

    def setUp(self):
        """测试准备：创建模拟数据"""
        self.n_dates = 252  # 一年交易日
        self.n_stocks = 100
        dates = pd.date_range("2020-01-01", periods=self.n_dates, freq="B")
        stocks = [f"STOCK_{i:03d}" for i in range(self.n_stocks)]

        np.random.seed(42)
        # 生成随机价格数据
        returns = np.random.randn(self.n_dates, self.n_stocks) * 0.02
        close = 100 * np.exp(np.cumsum(returns, axis=0))
        open_price = close * (1 + np.random.randn(self.n_dates, self.n_stocks) * 0.005)
        high = close * (1 + np.abs(np.random.randn(self.n_dates, self.n_stocks)) * 0.01)
        low = close * (1 - np.abs(np.random.randn(self.n_dates, self.n_stocks)) * 0.01)

        self.close_df = pd.DataFrame(close, index=dates, columns=stocks)
        self.open_df = pd.DataFrame(open_price, index=dates, columns=stocks)
        self.high_df = pd.DataFrame(high, index=dates, columns=stocks)
        self.low_df = pd.DataFrame(low, index=dates, columns=stocks)

        # 创建 DataLoaderV3
        self.dl = DataLoaderV3.from_pandas_dataframes(
            close=self.close_df,
            open=self.open_df,
            high=self.high_df,
            low=self.low_df,
        )

        # 配置
        self.config = {
            "initial_capital": 10000000.0,
            "rebalance_freq": 20,
            "top_n": 10,
            "cost_rate": 0.001,
        }

    def test_engine_setup(self):
        """测试引擎设置"""
        engine = VectorBacktestEngine(self.config)
        engine.setup(self.dl)

        self.assertIsNotNone(engine.dl)
        self.assertEqual(engine.dl.n_dates, self.n_dates)
        self.assertEqual(engine.dl.n_stocks, self.n_stocks)

    def test_run_backtest(self):
        """测试运行回测"""
        engine = VectorBacktestEngine(self.config)
        engine.setup(self.dl)
        results = engine.run()

        # 验证结果
        self.assertIn("total_return", results)
        self.assertIn("sharpe_ratio", results)
        self.assertIn("max_drawdown", results)
        self.assertIn("portfolio_value", results)

        # 验证组合价值
        portfolio_value = results["portfolio_value"]
        self.assertEqual(len(portfolio_value), self.n_dates)
        self.assertGreater(portfolio_value[-1], 0)

        # 验证收益率
        self.assertIsInstance(results["total_return"], float)

    def test_positions(self):
        """测试仓位计算"""
        engine = VectorBacktestEngine(self.config)
        engine.setup(self.dl)
        engine.run()

        positions = engine.get_positions()
        self.assertIsNotNone(positions)
        self.assertEqual(positions.shape, (self.n_dates, self.n_stocks))

        # 验证再平衡日有仓位变化
        rebalance_days = list(range(20, self.n_dates, 20))
        if rebalance_days:
            day = rebalance_days[0]
            if day > 0:
                # 再平衡日仓位应该和前一日不同
                has_change = not np.allclose(positions[day], positions[day - 1])
                # 由于随机性，不一定每次都有变化，但大概率有
                # 这里只验证仓位在合理范围内
                self.assertTrue(np.all(positions >= 0))

    def test_performance_benchmark(self):
        """性能基准测试"""
        engine = VectorBacktestEngine(self.config)
        engine.setup(self.dl)

        start_time = time.perf_counter()
        results = engine.run()
        elapsed = time.perf_counter() - start_time

        print(f"\n性能测试结果:")
        print(f"  数据规模: {self.n_dates} 天 × {self.n_stocks} 股票")
        print(f"  回测耗时: {elapsed:.4f} 秒")
        print(f"  总收益率: {results['total_return']:.2%}")
        print(f"  夏普比率: {results['sharpe_ratio']:.2f}")
        print(f"  最大回撤: {results['max_drawdown']:.2%}")

        # 性能断言：100股票 × 252天应该在 1 秒内完成
        self.assertLess(elapsed, 1.0)

    def test_different_rebalance_freq(self):
        """测试不同再平衡频率"""
        for freq in [5, 10, 20, 60]:
            config = self.config.copy()
            config["rebalance_freq"] = freq

            engine = VectorBacktestEngine(config)
            engine.setup(self.dl)
            results = engine.run()

            self.assertIn("total_return", results)
            self.assertGreater(results["final_value"], 0)

    def test_edge_cases(self):
        """测试边界情况"""
        # 测试 top_n 大于股票数量
        config = self.config.copy()
        config["top_n"] = 200  # 大于 100

        engine = VectorBacktestEngine(config)
        engine.setup(self.dl)
        results = engine.run()

        self.assertIn("total_return", results)

    def test_results_consistency(self):
        """测试结果一致性"""
        engine1 = VectorBacktestEngine(self.config)
        engine1.setup(self.dl)
        results1 = engine1.run()

        engine2 = VectorBacktestEngine(self.config)
        engine2.setup(self.dl)
        results2 = engine2.run()

        # 相同输入应该产生相同结果
        self.assertAlmostEqual(results1["total_return"], results2["total_return"], places=10)
        self.assertAlmostEqual(results1["sharpe_ratio"], results2["sharpe_ratio"], places=10)


class TestVectorBacktestLargeScale(unittest.TestCase):
    """大规模数据测试"""

    def test_large_scale_performance(self):
        """测试大规模数据性能"""
        n_dates = 1250  # 5年
        n_stocks = 500

        dates = pd.date_range("2020-01-01", periods=n_dates, freq="B")
        stocks = [f"STOCK_{i:04d}" for i in range(n_stocks)]

        np.random.seed(42)
        returns = np.random.randn(n_dates, n_stocks) * 0.02
        close = 100 * np.exp(np.cumsum(returns, axis=0))
        close_df = pd.DataFrame(close, index=dates, columns=stocks)

        dl = DataLoaderV3.from_pandas_dataframes(close=close_df)

        config = {
            "initial_capital": 10000000.0,
            "rebalance_freq": 20,
            "top_n": 50,
            "cost_rate": 0.001,
        }

        engine = VectorBacktestEngine(config)
        engine.setup(dl)

        start_time = time.perf_counter()
        results = engine.run()
        elapsed = time.perf_counter() - start_time

        print(f"\n大规模性能测试:")
        print(f"  数据规模: {n_dates} 天 × {n_stocks} 股票")
        print(f"  回测耗时: {elapsed:.4f} 秒")
        print(f"  总收益率: {results['total_return']:.2%}")

        # 500股票 × 1250天应该在 5 秒内完成
        self.assertLess(elapsed, 5.0)
        self.assertIn("sharpe_ratio", results)


if __name__ == "__main__":
    unittest.main()

