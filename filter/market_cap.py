"""
市值过滤器模块

基于市值数据进行过滤，支持流通市值、总市值等多种指标
全部向量化实现
"""

from typing import Optional, Union, Literal, Dict, Any
import pandas as pd
import numpy as np
from datetime import datetime
import logging

from .base import BaseFilter, FilterConfig

logger = logging.getLogger(__name__)


class MarketCapFilter(BaseFilter):
    """
    市值过滤器（向量化）
    
    基于市值数据进行过滤，支持：
    - 流通市值过滤
    - 总市值过滤
    - 市值分位数过滤
    - 市值排名过滤
    """
    
    def __init__(
        self,
        min_cap: Optional[float] = None,
        max_cap: Optional[float] = None,
        percentile_range: Optional[tuple] = None,  # (min_percentile, max_percentile)
        rank_range: Optional[tuple] = None,  # (min_rank, max_rank)
        cap_type: Literal['float', 'total'] = 'float',  # 流通市值或总市值
        market_cap_data: Optional[pd.DataFrame] = None,
        ascending: bool = False,  # 排名时是否升序（小市值在前）
        config: Optional[FilterConfig] = None
    ):
        """
        初始化市值过滤器
        
        Args:
            min_cap: 最小市值（万元或元，根据数据单位）
            max_cap: 最大市值
            percentile_range: 市值分位数范围 (0-1)，如 (0.8, 1.0)表示大盘股
            rank_range: 市值排名范围，如 (1, 100)表示前100名
            cap_type: 市值类型 'float'(流通市值) 或 'total'(总市值)
            market_cap_data: 市值数据DataFrame (日期 x 股票)
            ascending: 排名时是否升序
            config: 配置对象
        """
        super().__init__(config)
        self.min_cap = min_cap
        self.max_cap = max_cap
        self.percentile_range = percentile_range
        self.rank_range = rank_range
        self.cap_type = cap_type
        self.market_cap_data = market_cap_data
        self.ascending = ascending
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建市值过滤掩码（向量化）
        
        Args:
            data: 输入数据（用于对齐索引）
            
        Returns:
            布尔掩码DataFrame
        """
        if self.market_cap_data is None:
            logger.warning("未提供市值数据，返回全True")
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 对齐市值数据到输入数据的形状
        cap_data = self.market_cap_data.reindex_like(data)
        
        # 初始化掩码
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 1. 数值范围过滤（向量化）
        if self.min_cap is not None:
            mask &= cap_data >= self.min_cap
        if self.max_cap is not None:
            mask &= cap_data <= self.max_cap
        
        # 2. 分位数过滤（向量化，逐日计算）
        if self.percentile_range is not None:
            min_p, max_p = self.percentile_range
            
            # 向量化计算每日分位数
            # 使用apply逐日计算，但内部使用向量化操作
            def calc_percentile_mask(day_data):
                if day_data.isna().all():
                    return pd.Series(False, index=day_data.index)
                
                # 计算分位数阈值
                lower_thresh = day_data.quantile(min_p) if not day_data.isna().all() else np.nan
                upper_thresh = day_data.quantile(max_p) if not day_data.isna().all() else np.nan
                
                if pd.isna(lower_thresh) or pd.isna(upper_thresh):
                    return pd.Series(False, index=day_data.index)
                
                return (day_data >= lower_thresh) & (day_data <= upper_thresh)
            
            # 应用分位数过滤
            percentile_mask = cap_data.apply(calc_percentile_mask, axis=1)
            mask &= percentile_mask
        
        # 3. 排名过滤（向量化，逐日计算）
        if self.rank_range is not None:
            min_rank, max_rank = self.rank_range
            
            # 向量化排名计算
            # rank(axis=1) 对每行（每日）进行排名
            daily_ranks = cap_data.rank(
                axis=1, 
                ascending=self.ascending,
                method='min'  # 相同值取最小排名
            )
            
            # 向量化排名过滤
            rank_mask = (daily_ranks >= min_rank) & (daily_ranks <= max_rank)
            mask &= rank_mask
        
        self._mask = mask
        return mask
    
    def get_cap_stats(self) -> Optional[pd.DataFrame]:
        """
        获取市值统计信息
        
        Returns:
            市值统计DataFrame
        """
        if self.market_cap_data is None:
            return None
        
        return pd.DataFrame({
            'min': self.market_cap_data.min(axis=1),
            'max': self.market_cap_data.max(axis=1),
            'mean': self.market_cap_data.mean(axis=1),
            'median': self.market_cap_data.median(axis=1),
            'std': self.market_cap_data.std(axis=1),
            'q05': self.market_cap_data.quantile(0.05, axis=1),
            'q25': self.market_cap_data.quantile(0.25, axis=1),
            'q50': self.market_cap_data.quantile(0.50, axis=1),
            'q75': self.market_cap_data.quantile(0.75, axis=1),
            'q95': self.market_cap_data.quantile(0.95, axis=1),
        })
    
    def get_top_n(self, n: int = 100, date: Optional[datetime] = None) -> pd.Series:
        """
        获取指定日期的前N大市值股票（向量化）
        
        Args:
            n: 前N名
            date: 日期，None表示最新日期
            
        Returns:
            前N股票及其市值
        """
        if self.market_cap_data is None:
            return pd.Series()
        
        if date is None:
            date = self.market_cap_data.index[-1]
        
        if date not in self.market_cap_data.index:
            return pd.Series()
        
        # 向量化获取前N
        day_data = self.market_cap_data.loc[date]
        return day_data.nlargest(n)


class LargeCapFilter(MarketCapFilter):
    """
    大盘股过滤器（向量化简化版）
    
    过滤市值最大的股票（如前100名）
    """
    
    def __init__(
        self,
        top_n: int = 100,
        market_cap_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(
            rank_range=(1, top_n),
            market_cap_data=market_cap_data,
            ascending=False,  # 大市值在前
            config=config
        )
        self.top_n = top_n


class SmallCapFilter(MarketCapFilter):
    """
    小盘股过滤器（向量化简化版）
    
    过滤市值最小的股票（如最后100名）
    """
    
    def __init__(
        self,
        bottom_n: int = 100,
        market_cap_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(
            rank_range=(1, bottom_n),
            market_cap_data=market_cap_data,
            ascending=True,  # 小市值在前
            config=config
        )
        self.bottom_n = bottom_n


class MidCapFilter(MarketCapFilter):
    """
    中盘股过滤器（向量化简化版）
    
    过滤市值中等的股票
    """
    
    def __init__(
        self,
        min_percentile: float = 0.3,
        max_percentile: float = 0.7,
        market_cap_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(
            percentile_range=(min_percentile, max_percentile),
            market_cap_data=market_cap_data,
            config=config
        )


class MarketCapRatioFilter(BaseFilter):
    """
    市值比例过滤器（向量化）
    
    基于市值占比进行过滤
    """
    
    def __init__(
        self,
        min_ratio: float = 0.0001,  # 最小占比 0.01%
        max_ratio: Optional[float] = None,
        market_cap_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(config)
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio
        self.market_cap_data = market_cap_data
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建市值比例掩码（向量化）"""
        if self.market_cap_data is None:
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 对齐数据
        cap_data = self.market_cap_data.reindex_like(data)
        
        # 向量化计算每日总市值
        total_cap_per_day = cap_data.sum(axis=1)
        
        # 向量化计算占比
        # 使用div进行广播除法
        ratio = cap_data.div(total_cap_per_day, axis=0)
        
        # 向量化条件判断
        mask = ratio >= self.min_ratio
        if self.max_ratio is not None:
            mask &= ratio <= self.max_ratio
        
        self._mask = mask
        return mask


class MarketCapMomentumFilter(BaseFilter):
    """
    市值动量过滤器（向量化）
    
    基于市值变化趋势进行过滤
    """
    
    def __init__(
        self,
        window: int = 20,
        min_growth: Optional[float] = None,
        max_growth: Optional[float] = None,
        market_cap_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(config)
        self.window = window
        self.min_growth = min_growth
        self.max_growth = max_growth
        self.market_cap_data = market_cap_data
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建市值动量掩码（向量化）"""
        if self.market_cap_data is None:
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 对齐数据
        cap_data = self.market_cap_data.reindex_like(data)
        
        # 向量化计算滚动增长
        # 使用pct_change计算增长率
        growth = cap_data.pct_change(periods=self.window)
        
        # 向量化条件判断
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        if self.min_growth is not None:
            mask &= growth >= self.min_growth
        if self.max_growth is not None:
            mask &= growth <= self.max_growth
        
        self._mask = mask
        return mask


# 便捷函数
def filter_large_cap(
    data: pd.DataFrame,
    market_cap_data: pd.DataFrame,
    top_n: int = 100
) -> pd.DataFrame:
    """过滤大盘股（向量化便捷函数）"""
    filter_obj = LargeCapFilter(top_n=top_n, market_cap_data=market_cap_data)
    return filter_obj.apply(data)


def filter_small_cap(
    data: pd.DataFrame,
    market_cap_data: pd.DataFrame,
    bottom_n: int = 100
) -> pd.DataFrame:
    """过滤小盘股（向量化便捷函数）"""
    filter_obj = SmallCapFilter(bottom_n=bottom_n, market_cap_data=market_cap_data)
    return filter_obj.apply(data)


def filter_cap_range(
    data: pd.DataFrame,
    market_cap_data: pd.DataFrame,
    min_cap: float,
    max_cap: float
) -> pd.DataFrame:
    """过滤市值范围（向量化便捷函数）"""
    filter_obj = MarketCapFilter(
        min_cap=min_cap,
        max_cap=max_cap,
        market_cap_data=market_cap_data
    )
    return filter_obj.apply(data)


# 工厂函数
def create_market_cap_filter(
    filter_type: str = 'range',
    **kwargs
) -> MarketCapFilter:
    """
    创建市值过滤器的工厂函数
    
    Args:
        filter_type: 过滤器类型 ('range', 'large', 'small', 'mid', 'ratio', 'momentum')
        **kwargs: 特定参数
        
    Returns:
        市值过滤器实例
    """
    filters = {
        'range': MarketCapFilter,
        'large': LargeCapFilter,
        'small': SmallCapFilter,
        'mid': MidCapFilter,
        'ratio': MarketCapRatioFilter,
        'momentum': MarketCapMomentumFilter,
    }
    
    if filter_type not in filters:
        raise ValueError(f"未知过滤器类型: {filter_type}，可用: {list(filters.keys())}")
    
    return filters[filter_type](**kwargs)
