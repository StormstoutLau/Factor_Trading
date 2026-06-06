"""
数据层 V3 - Qlib 风格向量化数据加载器
为高性能向量回测提供 NumPy 数组存储
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Optional, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataLoaderV3:
    """Qlib 风格向量化数据加载器

    设计目标：
        1. 预加载所有必要数据到内存中
        2. 统一对齐到同一交易日历
        3. NumPy 数组化存储，避免 pandas 开销
        4. 日期位置映射 {date_str: idx}
        5. 向后兼容 DataManager 接口
    """

    def __init__(self, data_dir: Optional[Path] = None, from_hdf5: bool = False):
        """初始化数据加载器

        Args:
            data_dir: 数据目录（可选，用于文件加载）
            from_hdf5: 是否从 HDF5 格式加载（预留）
        """
        self.data_dir = data_dir
        self._from_hdf5 = from_hdf5

        # 核心数据结构 - NumPy 数组 (n_dates, n_stocks)
        self.price_data: Dict[str, np.ndarray] = {}  # 'open' / 'close' / 'high' / 'low' / 'volume'
        self.factor_data: Dict[str, np.ndarray] = {}  # 因子数据
        self.mask_data: Dict[str, np.ndarray] = {}  # 可交易掩码

        # 元数据
        self.dates: Optional[np.ndarray] = None  # shape (n_dates,) - datetime64 或字符串
        self.stocks: Optional[np.ndarray] = None  # shape (n_stocks,)
        self.date_map: Dict[str, int] = {}  # 日期名 -> 索引
        self.stock_map: Dict[str, int] = {}  # 股票名 -> 索引
        self.n_dates: int = 0
        self.n_stocks: int = 0

        # 资产信息 (P3.2)
        self._asset_info: dict = {}

        logger.info("DataLoaderV3 初始化完成")

    @classmethod
    def from_data_manager(cls, dm) -> "DataLoaderV3":
        """从现有 DataManager 创建 DataLoaderV3（兼容性构造器）

        Args:
            dm: DataManager 实例

        Returns:
            DataLoaderV3 实例
        """
        dl = cls()
        dl._load_from_data_manager(dm)
        return dl

    @classmethod
    def from_pandas_dataframes(
        cls,
        close: pd.DataFrame,
        open: Optional[pd.DataFrame] = None,
        high: Optional[pd.DataFrame] = None,
        low: Optional[pd.DataFrame] = None,
        volume: Optional[pd.DataFrame] = None,
        factor_dict: Optional[Dict[str, pd.DataFrame]] = None,
        buyable: Optional[pd.DataFrame] = None,
        sellable: Optional[pd.DataFrame] = None,
    ) -> "DataLoaderV3":
        """从 pandas DataFrame 构造

        Args:
            close: 收盘价 DataFrame (dates x stocks)
            open: 开盘价
            high: 最高价
            low: 最低价
            volume: 成交量
            factor_dict: 因子字典 {factor_name: factor_df}
            buyable: 可买入掩码
            sellable: 可卖出掩码

        Returns:
            DataLoaderV3 实例
        """
        dl = cls()
        dl._load_from_pandas(close, open, high, low, volume, factor_dict, buyable, sellable)
        return dl

    def _load_from_data_manager(self, dm) -> None:
        """从 DataManager 加载数据（内部方法）"""
        logger.info("从 DataManager 加载数据...")

        # 加载价格数据
        for price_type in ["close", "open", "high", "low"]:
            df = dm.get_adj_price(price_type, "forward")
            self.price_data[price_type] = df.values
            logger.debug(f"加载 {price_type} 数据: {self.price_data[price_type].shape}")

        # 元数据
        self.dates = df.index.values.astype(str)
        self.stocks = df.columns.values.astype(str)
        self.n_dates, self.n_stocks = self.price_data["close"].shape

        # 构建索引映射
        self._build_maps()

        # 加载可交易掩码
        if hasattr(dm, "universe"):
            if hasattr(dm.universe, "buyable"):
                self.mask_data["buyable"] = dm.universe.buyable.values
            if hasattr(dm.universe, "sellable"):
                self.mask_data["sellable"] = dm.universe.sellable.values

        logger.info(f"DataLoaderV3 加载完成: {self.n_dates} 天 × {self.n_stocks} 股票")

    def _load_from_pandas(
        self,
        close: pd.DataFrame,
        open: Optional[pd.DataFrame],
        high: Optional[pd.DataFrame],
        low: Optional[pd.DataFrame],
        volume: Optional[pd.DataFrame],
        factor_dict: Optional[Dict[str, pd.DataFrame]],
        buyable: Optional[pd.DataFrame],
        sellable: Optional[pd.DataFrame],
    ) -> None:
        """从 pandas DataFrame 加载（内部方法）"""
        logger.info("从 pandas DataFrame 加载数据...")

        self.price_data["close"] = close.values
        if open is not None:
            self.price_data["open"] = open.values
        if high is not None:
            self.price_data["high"] = high.values
        if low is not None:
            self.price_data["low"] = low.values
        if volume is not None:
            self.price_data["volume"] = volume.values

        self.dates = close.index.values.astype(str)
        self.stocks = close.columns.values.astype(str)
        self.n_dates, self.n_stocks = self.price_data["close"].shape

        self._build_maps()

        if buyable is not None:
            self.mask_data["buyable"] = buyable.values
        if sellable is not None:
            self.mask_data["sellable"] = sellable.values

        if factor_dict:
            for name, df in factor_dict.items():
                self.factor_data[name] = df.values

        logger.info(f"DataLoaderV3 加载完成: {self.n_dates} 天 × {self.n_stocks} 股票")

    def _build_maps(self):
        """构建日期/股票到索引的映射"""
        self.date_map = {date_str: i for i, date_str in enumerate(self.dates)}
        self.stock_map = {stock_code: i for i, stock_code in enumerate(self.stocks)}

    def get_slice(self, start: int, end: int) -> dict[str, np.ndarray]:
        """获取日期切片

        Args:
            start: 起始索引（包含）
            end: 结束索引（不包含）

        Returns:
            价格数据字典
        """
        return {k: v[start:end] for k, v in self.price_data.items()}

    def get_date_index(self, date: str) -> Optional[int]:
        """获取日期对应的索引

        Args:
            date: 日期字符串

        Returns:
            索引或 None
        """
        return self.date_map.get(date)

    def get_stock_index(self, stock: str) -> Optional[int]:
        """获取股票对应的索引

        Args:
            stock: 股票代码

        Returns:
            索引或 None
        """
        return self.stock_map.get(stock)

    def to_data_manager_compatible(self) -> dict:
        """转换为 DataManager 兼容格式（用于兼容性）

        Returns:
            兼容字典
        """
        return {
            "dates": self.dates,
            "stocks": self.stocks,
            "close": pd.DataFrame(self.price_data["close"], index=self.dates, columns=self.stocks),
            "n_dates": self.n_dates,
            "n_stocks": self.n_stocks,
        }

    def save(self, path: Path) -> None:
        """保存到二进制文件

        Args:
            path: 保存路径
        """
        save_dict = {
            "price_data": self.price_data,
            "factor_data": self.factor_data,
            "mask_data": self.mask_data,
            "dates": self.dates,
            "stocks": self.stocks,
        }
        with open(path, "wb") as f:
            pickle.dump(save_dict, f)
        logger.info(f"DataLoaderV3 已保存到: {path}")

    @classmethod
    def load(cls, path: Path) -> "DataLoaderV3":
        """从二进制文件加载

        Args:
            path: 文件路径

        Returns:
            DataLoaderV3 实例
        """
        with open(path, "rb") as f:
            save_dict = pickle.load(f)

        dl = cls()
        dl.price_data = save_dict["price_data"]
        dl.factor_data = save_dict["factor_data"]
        dl.mask_data = save_dict["mask_data"]
        dl.dates = save_dict["dates"]
        dl.stocks = save_dict["stocks"]
        dl.n_dates = len(dl.dates)
        dl.n_stocks = len(dl.stocks)
        dl._build_maps()

        logger.info(f"DataLoaderV3 已从 {path} 加载")
        return dl

    def __repr__(self) -> str:
        return f"DataLoaderV3(n_dates={self.n_dates}, n_stocks={self.n_stocks})"

    # ── P3.2: 多资产信息 ──────────────────────────────────────

    def get_asset_info(self, symbol: str):
        """获取资产基本信息

        Args:
            symbol: 资产代码

        Returns:
            AssetInfo 实例，未知代码返回默认股票配置
        """
        from core.config import AssetInfo, AssetType

        if symbol in self._asset_info:
            return self._asset_info[symbol]
        return AssetInfo(asset_type=AssetType.STOCK)

    def configure_asset(self, symbol: str, info) -> None:
        """配置单个资产信息

        Args:
            symbol: 资产代码
            info: AssetInfo 实例
        """
        self._asset_info[symbol] = info

