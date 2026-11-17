"""数据端口（P-012 D7 / T-12 / P-042 B1）。

- ``DataProvider``：价格 / 辅助数据 / 股票池快照 / 因子的读取端口；
- ``PklDataProvider``：pkl 目录适配器（只读）；
- ``DataManager`` 经本端口读取（P-004 B1），业务装配不直接依赖存储实现。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

import pandas as pd

from core.universe_data import UniverseSnapshot, load_universe_snapshot


class DataProvider(Protocol):
    """数据读取端口（不绑定存储实现）。"""

    def load_price(self, kind: str) -> pd.DataFrame:
        """读取价格矩阵（open/high/low/close/adj_factor）。"""
        ...

    def load_aux(self, kind: str) -> Optional[pd.DataFrame]:
        """读取辅助数据（suspend/st/industry/mktcap）；缺失返回 None。"""
        ...

    def load_universe(self) -> Optional[UniverseSnapshot]:
        """读取股票池快照；缺失返回降级快照。"""
        ...

    def load_factor(self, name: str) -> pd.DataFrame:
        """读取因子矩阵（data_dir 下的文件名）。"""
        ...


class PklDataProvider:
    """pkl 目录适配器（只读）。"""

    def __init__(
        self,
        data_dir: Path,
        file_map: Optional[dict[str, str]] = None,
        universe_dir: Optional[Path] = None,
        aux_files: Optional[dict[str, str]] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.file_map = file_map or {
            "open": "open.pkl",
            "high": "high.pkl",
            "low": "low.pkl",
            "close": "close.pkl",
            "adj_factor": "stock_adj.pkl",
        }
        self.aux_files = aux_files or {
            "suspend": "suspend.pkl",
            "st": "st.pkl",
            "industry": "industry.pkl",
            "mktcap": "mktcap.pkl",
        }
        self.universe_dir = Path(universe_dir) if universe_dir is not None else None

    def load_price(self, kind: str) -> pd.DataFrame:
        filename = self.file_map.get(kind)
        if filename is None:
            raise ValueError(f"未知价格类型: {kind}")
        return pd.read_pickle(self.data_dir / filename)

    def load_aux(self, kind: str) -> Optional[pd.DataFrame]:
        filename = self.aux_files.get(kind)
        if filename is None:
            raise ValueError(f"未知辅助数据类型: {kind}")
        path = self.data_dir / filename
        if not path.exists():
            return None
        return pd.read_pickle(path)

    def load_universe(self) -> Optional[UniverseSnapshot]:
        return load_universe_snapshot(self.data_dir, self.universe_dir)

    def load_factor(self, name: str) -> pd.DataFrame:
        path = self.data_dir / name
        if not path.exists():
            raise FileNotFoundError(f"因子文件不存在: {path}")
        return pd.read_pickle(path)
