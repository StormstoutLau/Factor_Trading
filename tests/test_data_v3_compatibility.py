"""
测试 DataLoaderV3 与现有代码兼容性
"""

import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_v3 import DataLoaderV3


class TestDataLoaderV3Compatibility(unittest.TestCase):
    """测试 DataLoaderV3 兼容性"""

    def setUp(self):
        """测试准备：创建模拟数据"""
        self.n_dates = 100
        self.n_stocks = 50
        dates = pd.date_range("2020-01-01", periods=self.n_dates, freq="D")
        stocks = [f"STOCK_{i:03d}" for i in range(self.n_stocks)]

        # 创建随机 DataFrame
        np.random.seed(42)
        self.close_df = pd.DataFrame(
            100 * np.exp(np.random.randn(self.n_dates, self.n_stocks).cumsum(axis=0)),
            index=dates,
            columns=stocks,
        )
        self.open_df = self.close_df * (1 + 0.01 * np.random.randn(self.n_dates, self.n_stocks))
        self.high_df = self.close_df * (1 + 0.02 * np.random.rand(self.n_dates, self.n_stocks))
        self.low_df = self.close_df * (1 - 0.02 * np.random.rand(self.n_dates, self.n_stocks))

    def test_creation_from_pandas(self):
        """测试从 pandas 创建"""
        dl = DataLoaderV3.from_pandas_dataframes(
            close=self.close_df, open=self.open_df, high=self.high_df, low=self.low_df
        )

        # 验证形状
        self.assertEqual(dl.n_dates, self.n_dates)
        self.assertEqual(dl.n_stocks, self.n_stocks)
        self.assertEqual(dl.price_data["close"].shape, (self.n_dates, self.n_stocks))
        self.assertEqual(dl.price_data["open"].shape, (self.n_dates, self.n_stocks))

        # 验证数据一致性
        np.testing.assert_allclose(dl.price_data["close"], self.close_df.values)
        np.testing.assert_allclose(dl.price_data["open"], self.open_df.values)

    def test_index_mappings(self):
        """测试索引映射"""
        dl = DataLoaderV3.from_pandas_dataframes(close=self.close_df)

        # 测试日期索引
        date0 = dl.dates[0]
        idx0 = dl.get_date_index(date0)
        self.assertEqual(idx0, 0)

        # 测试股票索引
        stock0 = dl.stocks[0]
        sidx0 = dl.get_stock_index(stock0)
        self.assertEqual(sidx0, 0)

    def test_get_slice(self):
        """测试日期切片"""
        dl = DataLoaderV3.from_pandas_dataframes(close=self.close_df, open=self.open_df)

        start, end = 10, 30
        slice_data = dl.get_slice(start, end)

        self.assertEqual(slice_data["close"].shape, (20, self.n_stocks))
        np.testing.assert_allclose(slice_data["close"], self.close_df.values[10:30])

    def test_to_data_manager_compatible(self):
        """测试转换为 DataManager 兼容格式"""
        dl = DataLoaderV3.from_pandas_dataframes(close=self.close_df)
        compat = dl.to_data_manager_compatible()

        self.assertTrue(isinstance(compat["close"], pd.DataFrame))
        self.assertEqual(compat["close"].shape, (self.n_dates, self.n_stocks))
        np.testing.assert_allclose(compat["close"].values, self.close_df.values)

    def test_save_load(self):
        """测试保存和加载"""
        import tempfile

        dl = DataLoaderV3.from_pandas_dataframes(
            close=self.close_df, open=self.open_df, high=self.high_df, low=self.low_df
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_data_v3.pkl"
            dl.save(save_path)
            self.assertTrue(save_path.exists())

            dl2 = DataLoaderV3.load(save_path)
            self.assertEqual(dl2.n_dates, dl.n_dates)
            self.assertEqual(dl2.n_stocks, dl.n_stocks)
            np.testing.assert_allclose(dl2.price_data["close"], dl.price_data["close"])

    def test_factor_data(self):
        """测试因子数据加载"""
        factor1 = self.close_df.pct_change()
        factor2 = self.close_df.rolling(window=20).mean()

        dl = DataLoaderV3.from_pandas_dataframes(
            close=self.close_df, factor_dict={"factor1": factor1, "factor2": factor2}
        )

        self.assertIn("factor1", dl.factor_data)
        self.assertIn("factor2", dl.factor_data)
        self.assertEqual(dl.factor_data["factor1"].shape, (self.n_dates, self.n_stocks))
        self.assertEqual(dl.factor_data["factor2"].shape, (self.n_dates, self.n_stocks))


if __name__ == "__main__":
    unittest.main()

