"""BatchBacktestEngine 模块测试"""

import shutil
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from batch_backtest.engine import BatchBacktestEngine
from factor_library.database import FactorDatabase


@pytest.fixture
def temp_db():
    tmpdir = tempfile.mkdtemp()
    db = FactorDatabase(tmpdir)

    dates = pd.date_range("2024-01-01", periods=20, freq="B")
    stocks = ["000001.SZ", "000002.SZ"]
    for name in ["f1", "f2"]:
        data = {s: np.random.randn(20) for s in stocks}
        db.add_factor(name, pd.DataFrame(data, index=dates), metadata={"category": "test", "frequency": "daily", "author": "a"})

    yield db
    shutil.rmtree(tmpdir)


@pytest.fixture
def mock_config():
    """创建最小可用的 mock config"""
    from core.config import BacktestConfig
    from dataclasses import dataclass

    @dataclass
    class MockOptimizer:
        lookback: int = 20
        top_n: int = 10

    @dataclass
    class MockRebalance:
        freq: str = "monthly"

    config = MagicMock(spec=BacktestConfig)
    config.optimizer = MockOptimizer()
    config.rebalance = MockRebalance()
    config.output_dir = MagicMock()
    config.output_dir.__truediv__ = MagicMock(return_value=MagicMock())
    config.output_dir.mkdir = MagicMock()
    return config


class TestBatchBacktestEngine:
    def test_init(self, temp_db, mock_config):
        batch = BatchBacktestEngine(mock_config, factor_db=temp_db)
        assert batch.factor_db is temp_db
        assert batch.max_workers == 4

    def test_run_all_factors_no_db(self, mock_config):
        batch = BatchBacktestEngine(mock_config)
        with pytest.raises(ValueError, match="未提供因子数据库"):
            batch.run_all_factors()

    def test_compare_results_empty(self, mock_config):
        batch = BatchBacktestEngine(mock_config)
        df = batch.compare_results({})
        assert len(df) == 0
        assert isinstance(df, pd.DataFrame)

    def test_get_best_factor_empty(self, mock_config):
        batch = BatchBacktestEngine(mock_config)
        best, val = batch.get_best_factor()
        assert best == ""
        assert val == 0.0

    def test_get_best_factor_with_data(self, mock_config):
        batch = BatchBacktestEngine(mock_config)
        mock_results = {
            "s1": {"performance_metrics": {"sharpe_ratio": 1.5, "total_return": 0.1}},
            "s2": {"performance_metrics": {"sharpe_ratio": 2.0, "total_return": 0.15}},
        }
        best, val = batch.get_best_factor(results=mock_results)
        assert best == "s2"
        assert val == 2.0

    def test_compare_results_with_data(self, mock_config):
        batch = BatchBacktestEngine(mock_config)
        mock_results = {
            "s1": {"performance_metrics": {"sharpe_ratio": 1.5, "total_return": 0.1, "max_drawdown": -0.05}},
            "s2": {"error": "failed"},
        }
        df = batch.compare_results(mock_results)
        assert len(df) == 1
        assert df.iloc[0]["name"] == "s1"
