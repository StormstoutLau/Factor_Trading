"""P-042 B4 数据指纹与合成夹具测试（V13-V16）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from _synthetic_data import FACTOR_FILE, build_synthetic_config, build_synthetic_dataset
from core.data import DataManager


def test_v13_fingerprint_stable(tmp_path):
    """V13：同数据两实例指纹相等。"""
    build_synthetic_dataset(tmp_path)
    cfg = build_synthetic_config(tmp_path)

    first = DataManager(cfg).data_fingerprint()
    second = DataManager(cfg).data_fingerprint()

    assert first == second
    assert first.startswith("sha256:")


def test_v14_fingerprint_changes_with_price(tmp_path):
    """V14：改一个价格值 → 指纹变化。"""
    build_synthetic_dataset(tmp_path)
    cfg = build_synthetic_config(tmp_path)
    before = DataManager(cfg).data_fingerprint()

    close_path = tmp_path / "close.pkl"
    close = pd.read_pickle(close_path)
    close.iloc[0, 0] = float(close.iloc[0, 0]) + 1.0
    close.to_pickle(close_path)

    assert DataManager(cfg).data_fingerprint() != before


def test_v15_fingerprint_changes_with_factor(tmp_path):
    """V15：改一个因子值 → 指纹变化。"""
    build_synthetic_dataset(tmp_path)
    cfg = build_synthetic_config(tmp_path)
    before = DataManager(cfg).data_fingerprint()

    factor_path = tmp_path / FACTOR_FILE
    factor = pd.read_pickle(factor_path)
    factor.iloc[-1, -1] = float(factor.iloc[-1, -1]) + 1.0
    factor.to_pickle(factor_path)

    assert DataManager(cfg).data_fingerprint() != before


def test_v16_synthetic_dataset_contract(tmp_path):
    """V16：夹具写全 10 个 pkl，DataManager 可加载。"""
    data_dir = build_synthetic_dataset(tmp_path)
    expected = {
        "close.pkl",
        "open.pkl",
        "high.pkl",
        "low.pkl",
        "stock_adj.pkl",
        "suspend.pkl",
        "st.pkl",
        "industry.pkl",
        "mktcap.pkl",
        FACTOR_FILE,
    }
    assert {path.name for path in Path(data_dir).glob("*.pkl")} == expected

    dm = DataManager(build_synthetic_config(data_dir))
    assert dm.n_stocks == 5
    assert dm.n_dates == 20
    assert dm.suspend.shape == (20, 5)
    assert dm.industry is not None
    assert dm.mktcap is not None
