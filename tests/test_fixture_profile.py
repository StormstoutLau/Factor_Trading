"""P-012 B1：夹具双 profile（D8 / T-1）验收测试。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from scripts.prepare_test_fixture import main

BASELINE_FILES = (
    "close.pkl",
    "open.pkl",
    "high.pkl",
    "low.pkl",
    "stock_adj.pkl",
    "suspend.pkl",
    "industry.pkl",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_biased_profile_has_required_files(tmp_path):
    out = tmp_path / "biased"
    assert main(["--profile", "biased", "--out-dir", str(out)]) == 0

    for name in BASELINE_FILES + ("st.pkl",):
        assert (out / name).exists(), name
    for name in ("list_date.csv", "delist.csv", "manifest.json"):
        assert (out / "universe" / name).exists(), name

    close = pd.read_pickle(out / "close.pkl")
    assert close.shape == (60, 6)
    assert list(close.columns) == ["000001", "300001", "688001", "830001", "430001", "600001"]

    adj = pd.read_pickle(out / "stock_adj.pkl")
    assert adj.loc[:, "300001"].iloc[29] == 1.0
    assert adj.loc[:, "300001"].iloc[30] == 2.0

    st = pd.read_pickle(out / "st.pkl")
    assert st.loc[:, "600001"].iloc[20:41].eq(1).all()
    assert st.loc[:, "600001"].iloc[19] == 0

    suspend = pd.read_pickle(out / "suspend.pkl")
    assert suspend.loc[:, "830001"].iloc[10:13].eq(1).all()

    delist = pd.read_csv(out / "universe" / "delist.csv", dtype={"stock": str})
    assert "000001" in set(delist["stock"])
    assert float(delist.loc[delist["stock"] == "000001", "delist_return"].iloc[0]) == -0.10

    list_date = pd.read_csv(out / "universe" / "list_date.csv", dtype={"stock": str})
    assert "430001" in set(list_date["stock"])


def test_baseline_profile_bytes_stable(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    common = ["--profile", "baseline", "--n-stocks", "31", "--n-days", "51"]
    assert main([*common, "--out-dir", str(a)]) == 0
    assert main([*common, "--out-dir", str(b)]) == 0

    for name in BASELINE_FILES:
        assert _sha256(a / name) == _sha256(b / name), name
    assert not (a / "universe").exists()
    assert not (a / "st.pkl").exists()
