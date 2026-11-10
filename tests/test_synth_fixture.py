"""P-013 B1：合成夹具能力扩展的单测（独立 OHLC / 矩阵 suspend·st / universe）。

覆盖 DESIGN §5（D5.1/D5.2）与 IMPL §3 B1 的 6 项 RED 用例；同时锁定
「不传新参数时行为与 P-011 完全一致」的向后兼容契约。
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_price_fixture, write_universe
from core.universe_data import load_universe_snapshot

DATES = pd.bdate_range("2024-01-02", periods=4)
CODES = ["000001", "600000"]
BASE = np.array([[10.0, 25.0]] * 4)


def _read(root, name: str) -> pd.DataFrame:
    return pd.read_pickle(root / f"{name}.pkl")


def test_independent_open_written(tmp_path):
    """``open_prices`` 独立写入，且不影响 close。"""
    open_matrix = np.array([[11.0, 26.0]] * 4)
    write_price_fixture(tmp_path, DATES, CODES, BASE, open_prices=open_matrix)

    assert np.array_equal(_read(tmp_path, "open").to_numpy(), open_matrix)
    assert np.array_equal(_read(tmp_path, "close").to_numpy(), BASE)


@pytest.mark.parametrize(
    ("field", "values"),
    [("high_prices", np.array([[12.0, 27.0]] * 4)), ("low_prices", np.array([[9.0, 24.0]] * 4))],
)
def test_high_and_low_independent(tmp_path, field, values):
    """``high_prices`` / ``low_prices`` 独立写入。"""
    write_price_fixture(tmp_path, DATES, CODES, BASE, **{field: values})
    name = field.replace("_prices", "")
    assert np.array_equal(_read(tmp_path, name).to_numpy(), values)


def test_backward_compatible_ohlc(tmp_path):
    """不传 OHLC 覆盖参数 → open/high/low 与 close 逐值相等（旧行为）。"""
    write_price_fixture(tmp_path, DATES, CODES, BASE)
    for name in ("open", "high", "low"):
        assert np.array_equal(_read(tmp_path, name).to_numpy(), BASE)


def test_backward_compatible_suspend_scalar(tmp_path):
    """``suspend``/``st`` 传标量 → 全 0 矩阵（旧行为）。"""
    write_price_fixture(tmp_path, DATES, CODES, BASE, suspend=0, st=0)
    for name in ("suspend", "st"):
        assert _read(tmp_path, name).to_numpy().sum() == 0


@pytest.mark.parametrize("name", ["suspend", "st"])
def test_matrix_flags_supported(tmp_path, name):
    """``suspend`` / ``st`` 支持 2D 矩阵逐值写入。"""
    matrix = np.zeros((4, 2), dtype=int)
    matrix[2, 0] = 1
    matrix[3, 1] = 1
    write_price_fixture(tmp_path, DATES, CODES, BASE, **{name: matrix})

    written = _read(tmp_path, name).to_numpy()
    assert np.array_equal(written, matrix)
    assert written.dtype.kind in ("i", "u")


def test_write_universe_format(tmp_path):
    """``write_universe`` 三文件格式正确，且 ``load_universe_snapshot`` 读回 corrected。"""
    list_rows = [{"stock": "000001", "list_date": "2020-01-01"}]
    delist_rows = [{"stock": "600000", "delist_date": "2024-01-04", "delist_return": -0.1}]
    write_universe(tmp_path, list_rows, delist_rows)

    universe_dir = tmp_path / "universe"
    assert list(pd.read_csv(universe_dir / "list_date.csv").columns) == ["stock", "list_date"]
    assert list(pd.read_csv(universe_dir / "delist.csv").columns) == [
        "stock",
        "delist_date",
        "delist_return",
    ]
    payload = json.loads((universe_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["rows"] == 2

    snap = load_universe_snapshot(tmp_path)
    assert snap.status == "corrected"


def test_write_universe_manifest_optional(tmp_path):
    """``manifest=False`` 时不写 manifest.json，但 CSV 仍齐备。"""
    write_universe(tmp_path, [], [], manifest=False)
    universe_dir = tmp_path / "universe"
    assert (universe_dir / "list_date.csv").exists()
    assert (universe_dir / "delist.csv").exists()
    assert not (universe_dir / "manifest.json").exists()
