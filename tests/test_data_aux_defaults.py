"""P-010：DataManager 辅助数据缺失处理（默认值 / 幂等 / 告警）"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pytest

from core.config import BacktestConfig
from core.data import DataManager

N_DAYS = 100
N_STOCKS = 50


def _write_close(tmp_path) -> None:
    """写入最小基础数据 close.pkl"""
    rng = np.random.default_rng(20261109)
    dates = pd.bdate_range("2024-01-02", periods=N_DAYS)
    codes = [f"{i:06d}" for i in range(1, N_STOCKS + 1)]
    close = pd.DataFrame(rng.uniform(8.0, 60.0, (N_DAYS, N_STOCKS)), index=dates, columns=codes)
    close.to_pickle(tmp_path / "close.pkl")


def _write_suspend(tmp_path, value: int = 0) -> None:
    """写入停牌数据（默认全 0 = 正常）"""
    dates = pd.bdate_range("2024-01-02", periods=N_DAYS)
    codes = [f"{i:06d}" for i in range(1, N_STOCKS + 1)]
    suspend = pd.DataFrame(value, index=dates, columns=codes)
    suspend.to_pickle(tmp_path / "suspend.pkl")


def test_suspend_st_default_zero_frames(tmp_path):
    """停牌/ST 缺失时按 0=正常 提供默认值；行业/市值保持 None"""
    _write_close(tmp_path)
    dm = DataManager(BacktestConfig(data_dir=tmp_path))

    assert isinstance(dm.suspend, pd.DataFrame)
    assert dm.suspend.shape == (N_DAYS, N_STOCKS)
    assert (dm.suspend == 0).all().all()

    assert isinstance(dm.st, pd.DataFrame)
    assert dm.st.shape == (N_DAYS, N_STOCKS)
    assert (dm.st == 0).all().all()

    assert dm.industry is None
    assert dm.mktcap is None


def test_auxiliary_load_is_idempotent(tmp_path, monkeypatch):
    """可选文件缺失（industry）时重复访问不得反复读盘"""
    _write_close(tmp_path)
    _write_suspend(tmp_path)
    dm = DataManager(BacktestConfig(data_dir=tmp_path))

    calls = {"n": 0}
    original = dm._load_and_align_data

    def counted(path):
        calls["n"] += 1
        return original(path)

    monkeypatch.setattr(dm, "_load_and_align_data", counted)

    for _ in range(3):
        assert dm.industry is None

    assert calls["n"] == 1


def test_existing_suspend_not_overwritten(tmp_path):
    """已存在的停牌数据不得被默认值覆盖"""
    _write_close(tmp_path)
    _write_suspend(tmp_path, value=0)
    suspend = pd.read_pickle(tmp_path / "suspend.pkl")
    suspend.iloc[0, 0] = 1
    suspend.to_pickle(tmp_path / "suspend.pkl")

    dm = DataManager(BacktestConfig(data_dir=tmp_path))

    assert dm.suspend.iloc[0, 0] == 1
    assert int(dm.suspend.to_numpy().sum()) == 1


def test_missing_aux_logs_warning(tmp_path, caplog):
    """停牌/ST 缺失时必须有数据层 warning"""
    _write_close(tmp_path)
    dm = DataManager(BacktestConfig(data_dir=tmp_path))

    with caplog.at_level(logging.WARNING, logger="core.data"):
        _ = dm.suspend
        _ = dm.st

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "停牌数据文件不存在" in messages
    assert "ST数据文件不存在" in messages
