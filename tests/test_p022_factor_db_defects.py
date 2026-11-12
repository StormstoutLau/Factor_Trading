"""P-022 Factor_DB 四项缺陷回归测试。

覆盖：
- B1 写后重开（缺陷③ str-datetime → 崩溃）
- B2 覆盖守卫（缺陷① 静默覆盖）
- B3 删除彻底（缺陷② csv 孤儿 / 复活）
- B4 单一格式（缺陷④ 双份存储）
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factor_library.database import FactorDatabase

META = {"category": "test", "frequency": "daily", "author": "p022"}


@pytest.fixture
def db_path():
    path = tempfile.mkdtemp(prefix="p022_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_factor():
    dates = pd.date_range("2024-01-01", periods=6, freq="B")
    data = {stock: np.arange(6, dtype=float) for stock in ("000001.SZ", "600000.SH")}
    return pd.DataFrame(data, index=dates)


class TestReopenWrites:
    """B1：重开数据库后的写入路径不得崩溃（缺陷③）。"""

    def test_reopen_then_add_factor(self, db_path, sample_factor):
        db = FactorDatabase(db_path)
        db.add_factor("f1", sample_factor, metadata=META)

        reopened = FactorDatabase(db_path)
        reopened.add_factor("f2", sample_factor, metadata=META)

        assert set(reopened.list_factors()) == {"f1", "f2"}

    def test_reopen_then_update_stats(self, db_path, sample_factor):
        db = FactorDatabase(db_path)
        db.add_factor("f1", sample_factor, metadata=META)

        reopened = FactorDatabase(db_path)
        reopened.update_stats("f1", ir=0.5)

        assert reopened._metadata["f1"].ir == 0.5

    def test_reopen_then_delete_with_two_factors(self, db_path, sample_factor):
        db = FactorDatabase(db_path)
        db.add_factor("f1", sample_factor, metadata=META)
        db.add_factor("f2", sample_factor, metadata=META)

        reopened = FactorDatabase(db_path)
        reopened.delete_factor("f1")

        assert reopened.list_factors() == ["f2"]

    def test_reloaded_datetime_fields(self, db_path, sample_factor):
        db = FactorDatabase(db_path)
        db.add_factor("f1", sample_factor, metadata=META)

        reopened = FactorDatabase(db_path)
        meta = reopened._metadata["f1"]

        assert isinstance(meta.created_at, datetime)
        assert isinstance(meta.updated_at, datetime)
        assert meta.created_at.isoformat()
