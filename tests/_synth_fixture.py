"""合成夹具辅助（tmp_path 写入，供多处测试复用）。

只生成 V2/V3 测试所需的最小 pkl 集合；不读 ``data/`` 下任何本地数据。

P-013 扩展（向后兼容）：
- ``write_price_fixture`` 支持独立 ``open_prices``/``high_prices``/``low_prices``；
- ``suspend``/``st`` 支持标量或 2D 矩阵；
- 新增 ``write_universe``（``list_date.csv``/``delist.csv``/``manifest.json``）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


def _as_matrix(
    values: float | Sequence[float] | np.ndarray, n_dates: int, n_codes: int
) -> np.ndarray:
    if np.isscalar(values):
        return np.full((n_dates, n_codes), float(values))
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        return np.full((n_dates, n_codes), float(arr))
    if arr.ndim == 1:
        if len(arr) != n_codes:
            raise ValueError(f"一维价格长度应为 {n_codes}，实际 {len(arr)}")
        return np.tile(arr, (n_dates, 1))
    if arr.shape != (n_dates, n_codes):
        raise ValueError(f"价格矩阵形状应为 {(n_dates, n_codes)}，实际 {arr.shape}")
    return arr


def write_price_fixture(
    out_dir: Path,
    dates: Sequence[str] | pd.DatetimeIndex,
    codes: Sequence[str],
    prices: float | Sequence[float] | np.ndarray,
    *,
    open_prices: float | Sequence[float] | np.ndarray | None = None,
    high_prices: float | Sequence[float] | np.ndarray | None = None,
    low_prices: float | Sequence[float] | np.ndarray | None = None,
    adj: float = 1.0,
    suspend: float | Sequence[int] | np.ndarray = 0,
    st: float | Sequence[int] | np.ndarray = 0,
    with_industry: bool = True,
) -> Path:
    """写入 close/open/high/low/stock_adj/suspend/st（可选 industry）。

    ``open_prices``/``high_prices``/``low_prices`` 缺省为 ``None`` → 复用 ``prices``
    （与 P-011 行为完全一致）。``suspend``/``st`` 支持标量或矩阵。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    columns = [str(code) for code in codes]
    matrix = _as_matrix(prices, len(index), len(columns))

    for name, override in (
        ("close", None),
        ("open", open_prices),
        ("high", high_prices),
        ("low", low_prices),
    ):
        arr = matrix if override is None else _as_matrix(override, len(index), len(columns))
        pd.DataFrame(arr.copy(), index=index, columns=columns).to_pickle(out_dir / f"{name}.pkl")

    pd.DataFrame(
        np.full((len(index), len(columns)), float(adj)), index=index, columns=columns
    ).to_pickle(out_dir / "stock_adj.pkl")

    for name, value in (("suspend", suspend), ("st", st)):
        arr = _as_matrix(value, len(index), len(columns)).astype(int)
        pd.DataFrame(arr, index=index, columns=columns).to_pickle(out_dir / f"{name}.pkl")

    if with_industry:
        pd.DataFrame(
            np.ones((len(index), len(columns)), dtype=int), index=index, columns=columns
        ).to_pickle(out_dir / "industry.pkl")
    return out_dir


def write_universe(
    out_dir: Path,
    list_rows: Sequence[dict],
    delist_rows: Sequence[dict],
    *,
    manifest: bool = True,
) -> Path:
    """写入股票池快照（``universe/``，格式对齐 ``core.universe_data``）。

    ``list_rows``: ``[{"stock": "000001", "list_date": "2020-01-01"}, ...]``
    ``delist_rows``: ``[{"stock": "...", "delist_date": "...", "delist_return": 0.0}, ...]``
    """
    universe_dir = Path(out_dir) / "universe"
    universe_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(list(list_rows), columns=["stock", "list_date"]).to_csv(
        universe_dir / "list_date.csv", index=False
    )
    pd.DataFrame(list(delist_rows), columns=["stock", "delist_date", "delist_return"]).to_csv(
        universe_dir / "delist.csv", index=False
    )

    if manifest:
        payload = {
            "source": "fixture",
            "fetched_at": "2026-11-10T00:00:00",
            "rows": len(list(list_rows)) + len(list(delist_rows)),
            "sha256": "fixture",
            "schema_version": "1.0",
        }
        (universe_dir / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    return universe_dir


def write_factor(
    out_dir: Path,
    name: str,
    values: float | Sequence[float] | np.ndarray,
    dates: Sequence[str] | pd.DatetimeIndex,
    codes: Sequence[str],
) -> Path:
    """写入因子 pkl（形状 dates × codes）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    columns = [str(code) for code in codes]
    matrix = _as_matrix(values, len(index), len(columns))
    path = out_dir / f"{name}.pkl"
    pd.DataFrame(matrix.copy(), index=index, columns=columns).to_pickle(path)
    return path
