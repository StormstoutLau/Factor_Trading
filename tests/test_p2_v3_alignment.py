"""
P2.1 TDD: V3 引擎定位对齐测试

验证 V3 引擎 (VectorBacktestEngine) 的定位和限制:
1. 模块文档明确标注"快速因子筛选"定位
2. 引擎暴露 purpose 属性
3. 明确声明不支持的功能列表
4. 运行时对不支持功能给出清晰警告
5. 基本因子筛选功能正常
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest


class TestV3EnginePurpose(unittest.TestCase):
    """V3 引擎定位与文档"""

    def test_module_docstring_mentions_purpose(self):
        """模块文档字符串应包含 '因子筛选' 或 '因子预筛选'"""
        import core.engine_v3_vector as v3

        self.assertIn("因子", v3.__doc__)
        self.assertTrue(
            "筛选" in v3.__doc__ or "预筛选" in v3.__doc__,
            "模块文档应明确标注 V3 的因子筛选定位"
        )

    def test_module_docstring_mentions_limitations(self):
        """模块文档应提及 V3 不支持的功能"""
        import core.engine_v3_vector as v3

        doc = v3.__doc__
        self.assertIn("不支持", doc,
                      "模块文档应明确列出 V3 不支持的功能")

    def test_engine_has_purpose_attribute(self):
        """VectorBacktestEngine 应有 purpose 属性"""
        from core.engine_v3_vector import VectorBacktestEngine

        engine = VectorBacktestEngine()
        self.assertTrue(hasattr(engine, "purpose"),
                        "VectorBacktestEngine 应暴露 purpose 属性")

    def test_purpose_mentions_factor_screening(self):
        """purpose 属性应提及因子筛选"""
        from core.engine_v3_vector import VectorBacktestEngine

        engine = VectorBacktestEngine()
        purpose = engine.purpose
        self.assertIn("因子", purpose)

    def test_engine_has_unsupported_features_list(self):
        """VectorBacktestEngine 应有 unsupported_features 属性"""
        from core.engine_v3_vector import VectorBacktestEngine

        engine = VectorBacktestEngine()
        self.assertTrue(hasattr(engine, "unsupported_features"),
                        "应暴露 unsupported_features 列表")

    def test_unsupported_features_includes_key_items(self):
        """unsupported_features 应包含关键受限功能"""
        from core.engine_v3_vector import VectorBacktestEngine

        engine = VectorBacktestEngine()
        unsupported = engine.unsupported_features

        # 至少应提及 execution_policy, pending_orders, risk_manager
        found = " ".join(unsupported).lower()
        self.assertIn("execution_policy", found,
                      "应说明不支持 execution_policy")
        self.assertIn("pending", found,
                      "应说明不支持 pending_orders")
        self.assertIn("risk", found,
                      "应说明不支持 risk_manager")

    def test_setup_without_data_loader_raises_clear_error(self):
        """未 setup 就 run 应给出清晰错误"""
        from core.engine_v3_vector import VectorBacktestEngine

        engine = VectorBacktestEngine()
        with self.assertRaises(RuntimeError) as ctx:
            engine.run()
        self.assertIn("setup", str(ctx.exception).lower())


class TestV3EngineBasicFunctionality(unittest.TestCase):
    """V3 基本因子筛选功能验证"""

    def setUp(self):
        import numpy as np
        import pandas as pd
        from core.engine_v3_vector import VectorBacktestEngine
        from core.data_v3 import DataLoaderV3

        # 构造模拟数据: 100股 × 252天
        self.n_stocks = 100
        self.n_dates = 252
        rng = np.random.default_rng(42)
        close_arr = np.cumprod(1 + rng.normal(0.001, 0.02, (self.n_dates, self.n_stocks)), axis=0)
        factor_arr = rng.normal(0, 1, (self.n_dates, self.n_stocks))
        stocks = [f"S{i:04d}" for i in range(self.n_stocks)]
        dates = pd.date_range("2024-01-01", periods=self.n_dates, freq="B")
        close = pd.DataFrame(close_arr, index=dates, columns=stocks)
        factor = pd.DataFrame(factor_arr, index=dates, columns=stocks)

        self.data_loader = DataLoaderV3.from_pandas_dataframes(
            close=close,
            factor_dict={"factor": factor},
        )
        self.engine = VectorBacktestEngine(
            config={"initial_capital": 1_000_000.0, "top_n": 20, "rebalance_freq": 20}
        )

    def test_setup_and_run(self):
        """setup + run 应正常返回结果"""
        self.engine.setup(self.data_loader)
        results = self.engine.run()

        self.assertIsInstance(results, dict)
        self.assertIn("total_return", results)
        self.assertIn("sharpe_ratio", results)
        self.assertIn("max_drawdown", results)
        self.assertIn("portfolio_value", results)

    def test_results_have_expected_keys(self):
        """结果字典应包含标准指标"""
        self.engine.setup(self.data_loader)
        results = self.engine.run()

        expected_keys = [
            "total_return", "annual_return", "volatility",
            "sharpe_ratio", "max_drawdown", "final_value",
            "portfolio_value", "returns",
        ]
        for key in expected_keys:
            self.assertIn(key, results, f"结果应包含 '{key}'")

    def test_portfolio_value_has_correct_shape(self):
        """portfolio_value 序列长度应与交易天数一致"""
        self.engine.setup(self.data_loader)
        results = self.engine.run()

        pv = results["portfolio_value"]
        self.assertEqual(len(pv), self.n_dates)

    def test_config_accepts_dict(self):
        """V3 接受 dict 配置（非 BacktestConfig）"""
        from core.engine_v3_vector import VectorBacktestEngine

        engine = VectorBacktestEngine(
            config={"initial_capital": 500_000.0, "top_n": 10}
        )
        self.assertEqual(engine.cfg["initial_capital"], 500_000.0)
        self.assertEqual(engine.cfg["top_n"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)