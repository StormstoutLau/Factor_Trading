"""真实A股数据回测验证测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")


class TestRealAshareBacktest(unittest.TestCase):
    """真实A股数据回测验证"""

    @classmethod
    def setUpClass(cls):
        """准备测试数据"""
        from core.config import BacktestConfig, CostConfig, UniverseConfig
        from core.config import FactorConfig, OptimizerConfig, RebalanceConfig
        from core.data import DataManager

        cls.cfg = BacktestConfig(
            data_dir=Path("data/test_ashare"),
            initial_capital=1_000_000.0,
            start_date="2024-01-02",
            end_date="2024-06-04",
            cost=CostConfig(
                commission_rate=0.0003,
                commission_min=5.0,
                stamp_tax_rate=0.001,
                slippage_pct=0.001,
            ),
            universe=UniverseConfig(
                exclude_suspended=True,
                exclude_limit_up=True,
                exclude_st=False,
            ),
            factor=FactorConfig(
                neutralize=False,
                standardize_method="zscore",
                winsorize_method="percentile",
                winsorize_pct=(0.01, 0.99),
            ),
            optimizer=OptimizerConfig(
                method="equal_weight",
                target_count=10,
                max_weight=0.15,
            ),
            rebalance=RebalanceConfig(
                method="fixed",
                frequency="N_days",
                n_days=20,
            ),
            enable_pending_orders=True,
            output_dir=Path("data/test_ashare/output"),
        )

        cls.dm = DataManager(cls.cfg)

    def test_01_data_manager_loads(self):
        """数据管理器加载真实数据"""
        self.dm.preload_data()
        self.assertGreater(self.dm.n_stocks, 0)
        self.assertGreater(self.dm.n_dates, 0)
        print(f"\n  ✓ 加载 {self.dm.n_stocks} 只股票, {self.dm.n_dates} 个交易日")

    def test_02_price_data_valid(self):
        """价格数据有效性"""
        close = self.dm.close
        self.assertFalse(close.isna().all().any(), "某列全部为NaN")
        # stack+dropna: 过滤掉未上市的NaN，只检查有效价格
        valid_values = close.stack().dropna()
        self.assertTrue((valid_values >= 0).all(), "存在负价格")
        val_min = valid_values.min()
        val_max = valid_values.max()
        print(f"  ✓ 收盘价范围: {val_min:.2f} ~ {val_max:.2f}")

    def test_03_returns_data_valid(self):
        """收益率数据有效性"""
        returns = self.dm.returns
        self.assertFalse(returns.isna().all().all())
        print(f"  ✓ 日收益率范围: {returns.min().min():.4f} ~ {returns.max().max():.4f}")

    def test_04_universe_filter(self):
        """股票池过滤"""
        from filter.universe_filter_clean import UniverseFilter

        unf = UniverseFilter(self.dm, self.cfg.universe)
        unf.build_masks()
        self.assertTrue(hasattr(unf, "buyable"))
        self.assertTrue(hasattr(unf, "sellable"))
        print(f"  ✓ 可买股票数: {unf.buyable.sum(axis=1).mean():.0f}")

    def test_05_factor_pipeline(self):
        """因子处理管道"""
        from core.factor import FactorPipeline

        # 使用收益率作为简单因子
        factor_df = self.dm.returns.copy()
        factor_df.columns = self.dm.stock_codes

        pipeline = FactorPipeline(self.dm, self.cfg.factor)
        processed = pipeline.process(factor_df)
        self.assertFalse(processed.isna().all().all())
        print(f"  ✓ 因子处理后形状: {processed.shape}")

    def test_06_engine_v2_setup(self):
        """引擎V2 setup"""
        from core.engine_v2 import BacktestEngineV2
        from core.factor import FactorPipeline, FactorCombiner

        pipeline = FactorPipeline(self.dm, self.cfg.factor)
        combiner = FactorCombiner([], {})
        engine = BacktestEngineV2(
            self.cfg,
            factor_pipeline=pipeline,
            factor_combiner=combiner,
        )
        engine.setup()
        self.assertIsNotNone(engine.dm)
        print(f"  ✓ 引擎V2 setup完成")

    def test_07_engine_v2_run(self):
        """引擎V2 完整回测"""
        from core.engine_v2 import BacktestEngineV2
        from core.factor import FactorPipeline, FactorCombiner

        pipeline = FactorPipeline(self.dm, self.cfg.factor)
        combiner = FactorCombiner([], {})
        engine = BacktestEngineV2(
            self.cfg,
            factor_pipeline=pipeline,
            factor_combiner=combiner,
        )
        engine.setup()

        # 注入信号（收益率作为因子）
        signal = self.dm.returns.copy()
        signal.columns = self.dm.stock_codes
        engine._composite_signal = pipeline.process(signal).fillna(0)

        results = engine.run()

        self.assertIsInstance(results, dict)
        self.assertIn("portfolio_value", results)
        self.assertIn("performance_metrics", results)

        pv = results["portfolio_value"]
        metrics = results["performance_metrics"]

        self.assertGreater(len(pv), 0)
        print(f"  ✓ 回测完成: {len(pv)} 天")
        print(f"  ✓ 总收益率: {metrics.get('total_return', 'N/A')}")
        print(f"  ✓ 夏普比率: {metrics.get('sharpe_ratio', 'N/A')}")
        print(f"  ✓ 最大回撤: {metrics.get('max_drawdown', 'N/A')}")
        print(f"  ✓ 年化收益: {metrics.get('annual_return', 'N/A')}")

    def test_08_portfolio_value_positive(self):
        """组合价值为正"""
        from core.engine_v2 import BacktestEngineV2
        from core.factor import FactorPipeline, FactorCombiner

        pipeline = FactorPipeline(self.dm, self.cfg.factor)
        combiner = FactorCombiner([], {})
        engine = BacktestEngineV2(
            self.cfg,
            factor_pipeline=pipeline,
            factor_combiner=combiner,
        )
        engine.setup()

        signal = self.dm.returns.copy()
        signal.columns = self.dm.stock_codes
        engine._composite_signal = pipeline.process(signal).fillna(0)

        results = engine.run()

        pv = results["portfolio_value"]
        self.assertGreater(pv.iloc[-1], 0)
        print(f"  ✓ 最终组合价值: {pv.iloc[-1]:.2f}")

    def test_09_trades_generated(self):
        """产生实际交易"""
        from core.engine_v2 import BacktestEngineV2
        from core.factor import FactorPipeline, FactorCombiner

        pipeline = FactorPipeline(self.dm, self.cfg.factor)
        combiner = FactorCombiner([], {})
        engine = BacktestEngineV2(
            self.cfg,
            factor_pipeline=pipeline,
            factor_combiner=combiner,
        )
        engine.setup()

        signal = self.dm.returns.copy()
        signal.columns = self.dm.stock_codes
        engine._composite_signal = pipeline.process(signal).fillna(0)

        results = engine.run()

        # 检查交易记录
        if hasattr(engine, 'executor') and engine.executor:
            stats = engine.executor.get_execution_stats()
            print(f"  ✓ 交易统计: {stats}")

        add_info = results.get("additional_info", {})
        exec_stats = add_info.get("execution_stats", {})
        if exec_stats:
            print(f"  ✓ 执行统计: {exec_stats}")


if __name__ == "__main__":
    unittest.main(verbosity=2)