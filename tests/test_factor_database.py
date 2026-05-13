"""FactorDatabase 模块测试"""

import shutil
import tempfile

import numpy as np
import pandas as pd
import pytest

from factor_library.database import FactorDatabase, FactorMetadata


@pytest.fixture
def temp_db():
    tmpdir = tempfile.mkdtemp()
    db = FactorDatabase(tmpdir)
    yield db
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_factor():
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    stocks = ["000001.SZ", "000002.SZ", "600000.SH"]
    data = {s: np.random.randn(10) for s in stocks}
    return pd.DataFrame(data, index=dates)


class TestFactorDatabase:
    def test_add_and_get_factor(self, temp_db, sample_factor):
        temp_db.add_factor(
            "roe_ttm",
            sample_factor,
            metadata={
                "category": "fundamental",
                "frequency": "quarterly",
                "description": "ROE TTM",
                "author": "test",
            },
        )
        retrieved = temp_db.get_factor("roe_ttm")
        assert retrieved is not None
        assert retrieved.shape == sample_factor.shape
        pd.testing.assert_frame_equal(retrieved, sample_factor)

    def test_get_nonexistent_factor(self, temp_db, sample_factor):
        temp_db.add_factor("f1", sample_factor, metadata={"category": "test", "frequency": "daily", "author": "a"})
        with pytest.raises(KeyError):
            temp_db.get_factor("not_exist")

    def test_list_factors(self, temp_db, sample_factor):
        temp_db.add_factor("f1", sample_factor, metadata={"category": "value", "frequency": "daily", "author": "a"})
        temp_db.add_factor("f2", sample_factor, metadata={"category": "momentum", "frequency": "daily", "author": "a"})
        factors = temp_db.list_factors()
        assert len(factors) == 2
        assert set(factors) == {"f1", "f2"}

    def test_query_by_category(self, temp_db, sample_factor):
        temp_db.add_factor("v1", sample_factor, metadata={"category": "value", "frequency": "daily", "author": "a"})
        temp_db.add_factor("m1", sample_factor, metadata={"category": "momentum", "frequency": "daily", "author": "a"})
        value_factors = temp_db.query(category="value")
        assert len(value_factors) == 1
        assert value_factors[0] == "v1"

    def test_delete_factor(self, temp_db, sample_factor):
        temp_db.add_factor("del_me", sample_factor, metadata={"category": "test", "frequency": "daily", "author": "a"})
        assert "del_me" in temp_db.list_factors()
        temp_db.delete_factor("del_me")
        assert "del_me" not in temp_db.list_factors()

    def test_update_stats(self, temp_db, sample_factor):
        temp_db.add_factor("stats_test", sample_factor, metadata={"category": "test", "frequency": "daily", "author": "a"})
        temp_db.update_stats("stats_test", ir=0.8)
        meta_list = temp_db.query()
        matched = [m for m in meta_list if temp_db._metadata.get(m) and temp_db._metadata[m].ir == 0.8]
        assert temp_db._metadata["stats_test"].ir == 0.8

    def test_persistence(self, temp_db, sample_factor):
        temp_db.add_factor("persist", sample_factor, metadata={"category": "test", "frequency": "daily", "author": "a"})
        db2 = FactorDatabase(temp_db.db_path)
        retrieved = db2.get_factor("persist")
        assert retrieved is not None
        pd.testing.assert_frame_equal(retrieved, sample_factor, check_freq=False)
