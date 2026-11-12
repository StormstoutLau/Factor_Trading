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


class TestOverwriteGuard:
    """B2：overwrite 守卫必须覆盖已持久化因子（缺陷①）。"""

    def test_reopen_rejects_duplicate_without_overwrite(self, db_path, sample_factor):
        db = FactorDatabase(db_path)
        db.add_factor("f1", sample_factor, metadata=META)

        reopened = FactorDatabase(db_path)
        with pytest.raises(ValueError, match="已存在"):
            reopened.add_factor("f1", sample_factor, metadata=META)

    def test_overwrite_persisted_factor(self, db_path, sample_factor):
        db = FactorDatabase(db_path)
        db.add_factor("f1", sample_factor, metadata=META)
        updated = sample_factor * 2.0

        reopened = FactorDatabase(db_path)
        reopened.add_factor("f1", updated, metadata=META, overwrite=True)

        pd.testing.assert_frame_equal(reopened.get_factor("f1"), updated)

    def test_orphan_csv_requires_overwrite(self, db_path, sample_factor):
        sample_factor.to_csv(Path(db_path) / "orphan.csv")

        db = FactorDatabase(db_path)
        with pytest.raises(ValueError, match="已存在"):
            db.add_factor("orphan", sample_factor, metadata=META)


def _raise_import_error(self, *args, **kwargs):
    raise ImportError("no parquet engine")


class TestDeleteBothFormats:
    """B3：删除必须同时清理 parquet 与 csv（缺陷②）。"""

    def test_delete_removes_csv_fallback(self, db_path, sample_factor, monkeypatch):
        db = FactorDatabase(db_path)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise_import_error)
        db.add_factor("csv_only", sample_factor, metadata=META)
        csv_path = Path(db_path) / "csv_only.csv"
        assert csv_path.exists()

        db.delete_factor("csv_only")

        assert not csv_path.exists()

    def test_deleted_factor_cannot_resurrect(self, db_path, sample_factor, monkeypatch):
        db = FactorDatabase(db_path)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise_import_error)
        db.add_factor("csv_only", sample_factor, metadata=META)
        db.delete_factor("csv_only")

        assert not (Path(db_path) / "csv_only.parquet").exists()
        with pytest.raises(KeyError):
            db.get_factor("csv_only")


class TestSingleFormat:
    """B4：写入成功后只保留一种格式（缺陷④）。"""

    def test_parquet_write_removes_stale_csv(self, db_path, sample_factor):
        stale_csv = Path(db_path) / "both.csv"
        sample_factor.to_csv(stale_csv)

        db = FactorDatabase(db_path)
        db.add_factor("both", sample_factor, metadata=META, overwrite=True)

        assert (Path(db_path) / "both.parquet").exists()
        assert not stale_csv.exists()
        pd.testing.assert_frame_equal(db.get_factor("both"), sample_factor)

    def test_csv_fallback_removes_stale_parquet(self, db_path, sample_factor, monkeypatch):
        seed = FactorDatabase(db_path)
        seed.add_factor("swap", sample_factor, metadata=META)
        stale_parquet = Path(db_path) / "swap.parquet"
        assert stale_parquet.exists()

        monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise_import_error)
        updated = sample_factor * 3.0
        db = FactorDatabase(db_path)
        db.add_factor("swap", updated, metadata=META, overwrite=True)

        assert not stale_parquet.exists()
        assert (Path(db_path) / "swap.csv").exists()

        monkeypatch.undo()
        reloaded = FactorDatabase(db_path).get_factor("swap")
        pd.testing.assert_frame_equal(reloaded, updated, check_freq=False)
