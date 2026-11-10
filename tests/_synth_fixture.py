"""P-011 合成夹具辅助（tmp_path 写入，供 3 处测试复用）。

只生成 V2/V3 测试所需的最小 pkl 集合；不读 ``data/`` 下任何本地数据。
"""

from __future__ import annotations

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
    adj: float = 1.0,
    suspend: int = 0,
    st: int = 0,
    with_industry: bool = True,
) -> Path:
    """写入 close/open/high/low/stock_adj/suspend/st（可选 industry）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    columns = [str(code) for code in codes]
    matrix = _as_matrix(prices, len(index), len(columns))

    for name in ("close", "open", "high", "low"):
        pd.DataFrame(matrix.copy(), index=index, columns=columns).to_pickle(out_dir / f"{name}.pkl")
    pd.DataFrame(
        np.full((len(index), len(columns)), float(adj)), index=index, columns=columns
    ).to_pickle(out_dir / "stock_adj.pkl")
    pd.DataFrame(
        np.full((len(index), len(columns)), int(suspend), dtype=int), index=index, columns=columns
    ).to_pickle(out_dir / "suspend.pkl")
    pd.DataFrame(
        np.full((len(index), len(columns)), int(st), dtype=int), index=index, columns=columns
    ).to_pickle(out_dir / "st.pkl")
    if with_industry:
        pd.DataFrame(
            np.ones((len(index), len(columns)), dtype=int), index=index, columns=columns
        ).to_pickle(out_dir / "industry.pkl")
    return out_dir


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
