"""数据管理模块 - 基于Backtest_Opus_2.0架构

提供高效的数据加载、缓存和预处理功能，支持：
- 懒加载和智能缓存
- 自动索引对齐
- 派生字段计算（复权价格、收益率）
- 日期范围过滤
- 内存优化管理
"""

from __future__ import annotations

import logging
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import BacktestConfig

logger = logging.getLogger(__name__)


class DataManager:
    """数据管理器
    
    负责所有市场数据和因子数据的加载、缓存和预处理。
    采用懒加载策略，只在需要时加载数据，并提供智能缓存机制。
    """
    
    def __init__(self, config: BacktestConfig):
        """初始化数据管理器
        
        Args:
            config: 回测配置
        """
        self.cfg = config
        self.data_dir = config.data_dir
        
        # 数据缓存
        self._cache: dict[str, Any] = {}
        self._cache_enabled = config.enable_cache
        
        # 基础数据
        self._prices: dict[str, pd.DataFrame] = {}
        self._factor_data: dict[str, pd.DataFrame] = {}
        self._suspend_data: Optional[pd.DataFrame] = None
        self._industry_data: Optional[pd.DataFrame] = None
        self._st_data: Optional[pd.DataFrame] = None
        self._mktcap_data: Optional[pd.DataFrame] = None
        
        # 派生数据
        self._returns: Optional[pd.DataFrame] = None
        self._adj_prices: dict[str, pd.DataFrame] = {}
        
        # 元数据
        self._trade_dates: Optional[pd.DatetimeIndex] = None
        self._stock_codes: Optional[pd.Index] = None
        self._n_stocks: int = 0
        self._n_dates: int = 0
        
        logger.info("数据管理器初始化完成")
    
    @property
    def trade_dates(self) -> pd.DatetimeIndex:
        """获取交易日期索引"""
        if self._trade_dates is None:
            self._load_basic_data()
        return self._trade_dates
    
    @property
    def stock_codes(self) -> pd.Index:
        """获取股票代码索引"""
        if self._stock_codes is None:
            self._load_basic_data()
        return self._stock_codes
    
    @property
    def n_stocks(self) -> int:
        """获取股票数量"""
        if self._n_stocks == 0:
            self._load_basic_data()
        return self._n_stocks
    
    @property
    def n_dates(self) -> int:
        """获取交易日期数量"""
        if self._n_dates == 0:
            self._load_basic_data()
        return self._n_dates
    
    @property
    def close(self) -> pd.DataFrame:
        """获取收盘价数据"""
        return self._load_price_data('close')
    
    @property
    def open(self) -> pd.DataFrame:
        """获取开盘价数据"""
        return self._load_price_data('open')
    
    @property
    def high(self) -> pd.DataFrame:
        """获取最高价数据"""
        return self._load_price_data('high')
    
    @property
    def low(self) -> pd.DataFrame:
        """获取最低价数据"""
        return self._load_price_data('low')
    
    @property
    def adj_factor(self) -> pd.DataFrame:
        """获取复权因子数据"""
        return self._load_price_data('adj_factor')
    
    @property
    def suspend(self) -> pd.DataFrame:
        """获取停牌数据"""
        if self._suspend_data is None:
            self._load_auxiliary_data()
        return self._suspend_data
    
    @property
    def industry(self) -> pd.DataFrame:
        """获取行业数据"""
        if self._industry_data is None:
            self._load_auxiliary_data()
        return self._industry_data
    
    @property
    def st(self) -> Optional[pd.DataFrame]:
        """获取ST数据"""
        if self._st_data is None and self.cfg.st_file:
            self._load_auxiliary_data()
        return self._st_data
    
    @property
    def mktcap(self) -> Optional[pd.DataFrame]:
        """获取市值数据"""
        if self._mktcap_data is None and self.cfg.mktcap_file:
            self._load_auxiliary_data()
        return self._mktcap_data
    
    @property
    def returns(self) -> pd.DataFrame:
        """获取收益率数据"""
        if self._returns is None:
            self._calculate_returns()
        return self._returns
    
    def _load_basic_data(self):
        """加载基础数据以获取元数据"""
        try:
            # 加载收盘价获取基础索引
            close_path = self.data_dir / self.cfg.close_file
            if not close_path.exists():
                raise FileNotFoundError(f"收盘价文件不存在: {close_path}")
            
            close_data = pd.read_pickle(close_path)
            
            # 设置元数据
            self._trade_dates = pd.to_datetime(close_data.index)
            self._stock_codes = close_data.columns
            self._n_stocks = len(self._stock_codes)
            self._n_dates = len(self._trade_dates)
            
            # 应用日期过滤
            if self.cfg.start_date or self.cfg.end_date:
                self._apply_date_filter()
            
            logger.info(f"基础数据加载完成: {self._n_stocks}只股票, {self._n_dates}个交易日")
            
        except Exception as e:
            logger.error(f"基础数据加载失败: {e}")
            raise
    
    def _load_auxiliary_data(self):
        """加载辅助数据

        辅助数据缺失时使用安全默认值，不影响回测执行。
        但会记录警告日志提醒用户数据不完整。
        """
        # 加载停牌数据（关键数据，缺失时默认全部可交易）
        suspend_path = self.data_dir / self.cfg.suspend_file
        if suspend_path.exists():
            self._suspend_data = self._load_and_align_data(suspend_path)
        else:
            logger.warning(f"停牌数据文件不存在: {suspend_path}，默认全部可交易")
            self._suspend_data = pd.DataFrame(True, index=self._trade_dates, columns=self._stock_codes)

        # 加载行业数据（可选数据，缺失时默认同一行业）
        industry_path = self.data_dir / self.cfg.industry_file
        if industry_path.exists():
            self._industry_data = self._load_and_align_data(industry_path)
        else:
            logger.warning(f"行业数据文件不存在: {industry_path}，默认同一行业")
            self._industry_data = pd.DataFrame(1, index=self._trade_dates, columns=self._stock_codes)

        # 加载ST数据（可选数据，缺失时默认无ST）
        if self.cfg.st_file:
            st_path = self.data_dir / self.cfg.st_file
            if st_path.exists():
                self._st_data = self._load_and_align_data(st_path)
            else:
                logger.warning(f"ST数据文件不存在: {st_path}，默认无ST股票")
                self._st_data = pd.DataFrame(False, index=self._trade_dates, columns=self._stock_codes)

        # 加载市值数据（可选数据，缺失时默认10亿）
        if self.cfg.mktcap_file:
            mktcap_path = self.data_dir / self.cfg.mktcap_file
            if mktcap_path.exists():
                self._mktcap_data = self._load_and_align_data(mktcap_path)
            else:
                logger.warning(f"市值数据文件不存在: {mktcap_path}，默认市值10亿")
                self._mktcap_data = pd.DataFrame(1e9, index=self._trade_dates, columns=self._stock_codes)
    
    def _apply_date_filter(self):
        """应用日期范围过滤"""
        if self._trade_dates is None:
            return
        
        start_date = pd.to_datetime(self.cfg.start_date) if self.cfg.start_date else None
        end_date = pd.to_datetime(self.cfg.end_date) if self.cfg.end_date else None
        
        date_mask = pd.Series(True, index=self._trade_dates)
        
        if start_date:
            date_mask &= (self._trade_dates >= start_date)
        if end_date:
            date_mask &= (self._trade_dates <= end_date)
        
        if not date_mask.all():
            self._trade_dates = self._trade_dates[date_mask]
            self._n_dates = len(self._trade_dates)
            logger.info(f"日期过滤后: {self._n_dates}个交易日")
    
    def _load_price_data(self, price_type: str) -> pd.DataFrame:
        """加载价格数据
        
        Args:
            price_type: 价格类型 ('close', 'open', 'high', 'low', 'adj_factor')
            
        Returns:
            价格数据DataFrame
        """
        cache_key = f"price_{price_type}"
        
        if self._cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]
        
        # 确定文件名
        file_map = {
            'close': self.cfg.close_file,
            'open': self.cfg.open_file,
            'high': self.cfg.high_file,
            'low': self.cfg.low_file,
            'adj_factor': self.cfg.adj_factor_file
        }
        
        filename = file_map.get(price_type)
        if not filename:
            raise ValueError(f"未知的价格类型: {price_type}")
        
        file_path = self.data_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"价格文件不存在: {file_path}")
        
        # 加载数据
        try:
            data = pd.read_pickle(file_path)
            
            # 确保索引为日期格式
            if not isinstance(data.index, pd.DatetimeIndex):
                data.index = pd.to_datetime(data.index)
            
            # 应用日期过滤
            if self._trade_dates is not None:
                data = data.loc[self._trade_dates]
            
            # 确保列顺序一致
            if self._stock_codes is not None:
                data = data[self._stock_codes]
            
            # 缓存数据
            if self._cache_enabled:
                self._cache[cache_key] = data
            
            self._prices[price_type] = data
            logger.debug(f"加载{price_type}数据: {data.shape}")
            
            return data
            
        except Exception as e:
            logger.error(f"加载{price_type}数据失败: {e}")
            raise
    
    def _load_auxiliary_data(self):
        """加载辅助数据（停牌、行业、ST、市值）"""
        # 确保基础数据已加载
        if self._trade_dates is None or self._stock_codes is None:
            self._load_basic_data()
        
        # 停牌数据
        if self.cfg.suspend_file:
            suspend_path = self.data_dir / self.cfg.suspend_file
            if suspend_path.exists():
                self._suspend_data = self._load_and_align_data(suspend_path)
        
        # 行业数据
        industry_path = self.data_dir / self.cfg.industry_file
        if industry_path.exists():
            self._industry_data = self._load_and_align_data(industry_path)
        
        # ST数据
        if self.cfg.st_file:
            st_path = self.data_dir / self.cfg.st_file
            if st_path.exists():
                self._st_data = self._load_and_align_data(st_path)
        
        # 市值数据
        if self.cfg.mktcap_file:
            mktcap_path = self.data_dir / self.cfg.mktcap_file
            if mktcap_path.exists():
                self._mktcap_data = self._load_and_align_data(mktcap_path)
    
    def _load_and_align_data(self, file_path: Path) -> pd.DataFrame:
        """加载并对齐数据到标准索引
        
        Args:
            file_path: 数据文件路径
            
        Returns:
            对齐后的DataFrame
        """
        data = pd.read_pickle(file_path)
        
        # 处理dict类型数据（如industry_mapping.pkl, stock_suspended.pkl）
        if isinstance(data, dict):
            # 检查值的类型（停牌数据值通常是Series）
            sample_value = next(iter(data.values()))
            if isinstance(sample_value, pd.Series):
                # 停牌数据: {stock_code: pd.Series(index=dates, values=suspend_status)}
                # 创建一个DataFrame，行是日期，列是股票代码
                all_dates = None
                for stock_code, series in data.items():
                    if all_dates is None:
                        all_dates = series.index
                    else:
                        all_dates = all_dates.union(series.index)
                
                # 创建结果DataFrame
                result = pd.DataFrame(0, index=all_dates, columns=list(data.keys()))
                
                # 填充数据
                for stock_code, series in data.items():
                    result.loc[series.index, stock_code] = series.values
                
                data = result
            else:
                # 行业映射数据: {stock_code: industry_code}
                # 转换为DataFrame，创建全0的DataFrame并与现有数据对齐
                result = pd.DataFrame(0, index=self._trade_dates, columns=self._stock_codes)
                # 将dict中的值填充到对应的股票代码
                for stock_code, value in data.items():
                    if stock_code in result.columns:
                        result[stock_code] = value
                data = result
        
        # 确保索引为日期格式
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index)
        
        # 应用日期过滤 - 使用reindex更安全，避免KeyError
        if self._trade_dates is not None:
            # 只保留同时存在于数据和交易日历中的日期
            common_dates = data.index.intersection(self._trade_dates)
            if len(common_dates) == 0:
                logger.warning(f"警告: {file_path} 中的日期与交易日历无交集")
                # 创建空DataFrame并返回
                data = pd.DataFrame(0, index=self._trade_dates, columns=self._stock_codes)
                return data
            # 使用reindex而不是loc，避免KeyError
            # 价格数据用0填充，因子数据保持NaN以区分缺失
            is_factor = 'factor' in str(file_path).lower()
            data = data.reindex(self._trade_dates) if is_factor else data.reindex(self._trade_dates, fill_value=0)
        
        # 确保列顺序一致
        if self._stock_codes is not None:
            # 使用reindex处理列不匹配的情况，缺失列填充为0
            data = data.reindex(columns=self._stock_codes, fill_value=0)
        
        return data
    
    def _calculate_returns(self):
        """计算收益率数据

        使用与交易配置一致的复权价格计算收益率，
        确保收益计算与回测执行价格完全匹配。
        """
        # 使用配置的复权类型获取收盘价
        adj_type = getattr(self.cfg, 'adjustment_type', 'forward')
        close_data = self.get_adj_price('close', adjustment_type=adj_type)

        # 计算简单收益率
        self._returns = close_data.pct_change()

        # 第一天设为NaN
        self._returns.iloc[0] = np.nan

        logger.debug(f"收益率计算完成 (复权类型: {adj_type})")
    
    def get_adj_price(self, price_type: str = 'close', adjustment_type: str = 'forward') -> pd.DataFrame:
        """获取复权价格数据

        Args:
            price_type: 价格类型 ('close', 'open', 'high', 'low')
            adjustment_type: 复权类型 ('forward'=前复权, 'backward'=后复权, 'none'=不复权)

        Returns:
            复权价格数据
        """
        cache_key = f"adj_{price_type}_{adjustment_type}"

        if self._cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]

        # 加载原始价格
        price_data = self._load_price_data(price_type)

        # 不复权：直接返回原始价格
        if adjustment_type == 'none':
            if self._cache_enabled:
                self._cache[cache_key] = price_data
            return price_data

        # 加载复权因子
        adj_factor = self.adj_factor

        # 计算复权价格
        if adjustment_type == 'backward':
            # 后复权：以最新日期为基准归一化
            # 获取每个股票最新的复权因子
            latest_factors = adj_factor.iloc[-1]
            # 安全处理：避免除零
            safe_factors = latest_factors.replace(0, np.nan)
            # 后复权价格 = 原始价格 * 复权因子 / 最新复权因子
            adj_price = price_data.mul(adj_factor).div(safe_factors, axis=1)
            # 除零时用原始价格填充
            adj_price = adj_price.fillna(price_data)
        else:
            # 前复权（默认）：价格 * 复权因子
            adj_price = price_data * adj_factor

        # 缓存结果
        if self._cache_enabled:
            self._cache[cache_key] = adj_price

        self._adj_prices[price_type] = adj_price
        return adj_price
    
    def load_factor(self, factor_file: str) -> pd.DataFrame:
        """加载因子数据
        
        Args:
            factor_file: 因子文件名
            
        Returns:
            因子数据DataFrame
        """
        cache_key = f"factor_{factor_file}"
        
        if self._cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]
        
        file_path = self.data_dir / factor_file
        if not file_path.exists():
            raise FileNotFoundError(f"因子文件不存在: {file_path}")
        
        try:
            factor_data = pd.read_pickle(file_path)
            
            # 确保索引为日期格式
            if not isinstance(factor_data.index, pd.DatetimeIndex):
                factor_data.index = pd.to_datetime(factor_data.index)
            
            # 应用日期过滤 - 使用向前填充策略对齐到交易日
            if self._trade_dates is not None:
                # 【修复】统一使用向前填充策略对齐月度因子到交易日
                # 对于每个交易日，找到最近的一个因子日期（<= 该交易日）
                aligned_data = []
                for trade_date in self._trade_dates:
                    # 找到小于等于交易日的最近因子日期
                    valid_dates = factor_data.index[factor_data.index <= trade_date]
                    if len(valid_dates) > 0:
                        nearest_date = valid_dates[-1]  # 最近的过去日期
                        aligned_data.append(factor_data.loc[nearest_date])
                    else:
                        # 【修复】如果该交易日前没有因子数据，使用NaN而不是最早数据
                        # 避免未来信息泄露：回测早期不应使用后期的因子数据
                        aligned_data.append(pd.Series(np.nan, index=factor_data.columns))
                
                factor_data = pd.DataFrame(aligned_data, index=self._trade_dates, columns=factor_data.columns)
                
                # 记录对齐信息
                common_dates = factor_data.index.intersection(self._trade_dates)
                if len(common_dates) == 0:
                    logger.warning(f"警告: 因子文件 {factor_file} 对齐后与交易日历无交集")
                else:
                    logger.debug(f"因子 {factor_file} 对齐完成: {len(common_dates)} 个共同日期")
            
            # 确保列顺序一致
            if self._stock_codes is not None:
                # 使用reindex处理列不匹配的情况，缺失列填充为0
                factor_data = factor_data.reindex(columns=self._stock_codes, fill_value=0)
            
            # 缓存数据
            if self._cache_enabled:
                self._cache[cache_key] = factor_data
            
            self._factor_data[factor_file] = factor_data
            logger.debug(f"加载因子数据 {factor_file}: {factor_data.shape}")
            
            return factor_data
            
        except Exception as e:
            logger.error(f"加载因子数据 {factor_file} 失败: {e}")
            raise
    
    def get_data_info(self) -> dict[str, Any]:
        """获取数据信息摘要
        
        Returns:
            数据信息字典
        """
        info = {
            'n_stocks': self.n_stocks,
            'n_dates': self.n_dates,
            'date_range': {
                'start': self.trade_dates[0].strftime('%Y-%m-%d') if self.n_dates > 0 else None,
                'end': self.trade_dates[-1].strftime('%Y-%m-%d') if self.n_dates > 0 else None
            },
            'price_data_loaded': list(self._prices.keys()),
            'factor_data_loaded': list(self._factor_data.keys()),
            'cache_enabled': self._cache_enabled,
            'cache_size': len(self._cache) if self._cache_enabled else 0
        }
        
        return info
    
    def clear_cache(self):
        """清空数据缓存"""
        self._cache.clear()
        logger.info("数据缓存已清空")
    
    def preload_data(self):
        """预加载所有数据"""
        logger.info("开始预加载数据...")
        
        # 加载价格数据
        for price_type in ['close', 'open', 'high', 'low', 'adj_factor']:
            self._load_price_data(price_type)
        
        # 加载辅助数据
        self._load_auxiliary_data()
        
        # 计算收益率
        self._calculate_returns()
        
        # 加载因子数据
        for factor_file in self.cfg.factor_files:
            self.load_factor(factor_file)
        
        logger.info("数据预加载完成")
