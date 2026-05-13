"""
NA因子过滤器模块

处理因子数据中的缺失值（NA/NaN），提供多种填充和过滤策略
全部向量化实现，避免循环
"""

from typing import Optional, Union, Literal
import pandas as pd
import numpy as np
from datetime import datetime
import logging

from .base import BaseFilter, FilterConfig

logger = logging.getLogger(__name__)


class NAFactorFilter(BaseFilter):
    """
    NA因子过滤器（向量化）
    
    处理因子数据中的缺失值，支持多种策略：
    - drop: 删除含NA的股票
    - fill: 填充NA值
    - forward_fill: 前向填充
    - backward_fill: 后向填充
    - interpolate: 线性插值
    """
    
    def __init__(
        self,
        strategy: Literal['drop', 'fill', 'forward_fill', 'backward_fill', 'interpolate'] = 'drop',
        fill_value: Optional[float] = 0.0,
        threshold: float = 0.0,  # NA比例阈值，超过则删除
        min_valid_days: int = 1,  # 最少有效天数
        config: Optional[FilterConfig] = None
    ):
        """
        初始化NA过滤器
        
        Args:
            strategy: 处理策略
            fill_value: 填充值（用于fill策略）
            threshold: NA比例阈值（0-1），超过此比例的股票被删除
            min_valid_days: 最少需要有多少天非NA数据
            config: 配置对象
        """
        super().__init__(config)
        self.strategy = strategy
        self.fill_value = fill_value
        self.threshold = threshold
        self.min_valid_days = min_valid_days
        self._processed_data: Optional[pd.DataFrame] = None
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建NA处理掩码（向量化）
        
        Args:
            data: 输入数据（可能包含NA）
            
        Returns:
            处理后的布尔掩码
        """
        # 向量化计算每只股票的有效数据比例
        valid_ratio = data.notna().mean(axis=0)
        valid_count = data.notna().sum(axis=0)
        
        # 根据阈值筛选股票（向量化）
        valid_stocks = (valid_ratio >= (1 - self.threshold)) & (valid_count >= self.min_valid_days)
        
        # 创建基础掩码
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 删除不符合条件的股票列
        invalid_stocks = ~valid_stocks
        if invalid_stocks.any():
            mask.loc[:, invalid_stocks] = False
            logger.debug(f"删除 {invalid_stocks.sum()} 只股票（NA比例过高或有效天数不足）")
        
        # 根据策略处理剩余数据
        if self.strategy == 'drop':
            # 删除策略：NA位置设为False
            mask &= data.notna()
            
        elif self.strategy == 'fill':
            # 填充策略：NA位置保留True，但记录需要填充
            self._processed_data = data.fillna(self.fill_value)
            
        elif self.strategy == 'forward_fill':
            # 前向填充（向量化）
            self._processed_data = data.ffill()
            # 如果开头有NA，用fill_value填充
            self._processed_data = self._processed_data.fillna(self.fill_value)
            
        elif self.strategy == 'backward_fill':
            # 后向填充（向量化）
            self._processed_data = data.bfill()
            # 如果末尾有NA，用fill_value填充
            self._processed_data = self._processed_data.fillna(self.fill_value)
            
        elif self.strategy == 'interpolate':
            # 线性插值（向量化）
            self._processed_data = data.interpolate(method='linear', axis=0)
            # 边界NA用前向/后向填充
            self._processed_data = self._processed_data.ffill().bfill()
            # 仍有NA则使用fill_value
            self._processed_data = self._processed_data.fillna(self.fill_value)
        
        self._mask = mask
        return mask
    
    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        应用过滤器并返回处理后的数据
        
        重写基类方法以支持数据填充
        """
        mask = self.build_mask(data)
        
        # 使用处理后的数据（如果有）
        if self._processed_data is not None:
            result = self._processed_data.where(mask, other=np.nan)
        else:
            result = data.where(mask, other=np.nan)
        
        return result
    
    def get_na_stats(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        获取NA统计信息（向量化）
        
        Args:
            data: 输入数据
            
        Returns:
            每只股票NA统计信息
        """
        na_count = data.isna().sum(axis=0)
        na_ratio = data.isna().mean(axis=0)
        valid_count = data.notna().sum(axis=0)
        
        stats = pd.DataFrame({
            'na_count': na_count,
            'na_ratio': na_ratio,
            'valid_count': valid_count,
            'total_count': len(data.index)
        })
        
        return stats
    
    def get_na_summary(self, data: pd.DataFrame) -> dict:
        """
        获取NA摘要信息
        
        Returns:
            摘要字典
        """
        total_cells = data.size
        na_cells = data.isna().sum().sum()
        
        return {
            'total_cells': total_cells,
            'na_cells': na_cells,
            'na_ratio': na_cells / total_cells if total_cells > 0 else 0,
            'na_stocks': data.isna().any(axis=0).sum(),
            'na_dates': data.isna().any(axis=1).sum(),
            'full_na_stocks': data.isna().all(axis=0).sum(),
            'full_na_dates': data.isna().all(axis=1).sum()
        }


class NAFactorDropFilter(NAFactorFilter):
    """
    NA删除过滤器（向量化简化版）
    
    简单删除所有含NA的数据
    """
    
    def __init__(self, threshold: float = 0.0, config: Optional[FilterConfig] = None):
        super().__init__(
            strategy='drop',
            threshold=threshold,
            config=config
        )


class NAFactorFillFilter(NAFactorFilter):
    """
    NA填充过滤器（向量化简化版）
    
    用指定值填充所有NA
    """
    
    def __init__(self, fill_value: float = 0.0, config: Optional[FilterConfig] = None):
        super().__init__(
            strategy='fill',
            fill_value=fill_value,
            threshold=1.0,  # 允许所有NA
            config=config
        )


class NAFactorForwardFillFilter(NAFactorFilter):
    """
    NA前向填充过滤器（向量化简化版）
    
    用前一个有效值填充NA
    """
    
    def __init__(
        self, 
        fill_value: float = 0.0,
        limit: Optional[int] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(
            strategy='forward_fill',
            fill_value=fill_value,
            threshold=1.0,
            config=config
        )
        self.limit = limit


class CrossSectionalNAFilter(BaseFilter):
    """
    横截面NA过滤器（向量化）
    
    基于横截面（每个日期）的NA情况进行过滤
    例如：某日期如果超过一半股票NA，则删除该日期
    """
    
    def __init__(
        self,
        max_na_ratio_per_date: float = 0.5,
        max_na_ratio_per_stock: float = 0.5,
        config: Optional[FilterConfig] = None
    ):
        """
        初始化横截面NA过滤器
        
        Args:
            max_na_ratio_per_date: 每个日期允许的最大NA比例
            max_na_ratio_per_stock: 每只股票允许的最大NA比例
            config: 配置对象
        """
        super().__init__(config)
        self.max_na_ratio_per_date = max_na_ratio_per_date
        self.max_na_ratio_per_stock = max_na_ratio_per_stock
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建横截面NA掩码（向量化）
        """
        # 计算每行（日期）的NA比例
        na_ratio_per_date = data.isna().mean(axis=1)
        
        # 计算每列（股票）的NA比例
        na_ratio_per_stock = data.isna().mean(axis=0)
        
        # 筛选有效日期（NA比例低于阈值）
        valid_dates = na_ratio_per_date <= self.max_na_ratio_per_date
        
        # 筛选有效股票（NA比例低于阈值）
        valid_stocks = na_ratio_per_stock <= self.max_na_ratio_per_stock
        
        # 向量化创建掩码
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 删除NA比例过高的日期
        invalid_dates = ~valid_dates
        if invalid_dates.any():
            mask.loc[invalid_dates, :] = False
            logger.debug(f"删除 {invalid_dates.sum()} 个日期（NA比例过高）")
        
        # 删除NA比例过高的股票
        invalid_stocks = ~valid_stocks
        if invalid_stocks.any():
            mask.loc[:, invalid_stocks] = False
            logger.debug(f"删除 {invalid_stocks.sum()} 只股票（NA比例过高）")
        
        # 剩余NA位置设为False
        mask &= data.notna()
        
        self._mask = mask
        return mask


# 工具函数
def fill_na_vectorized(
    data: pd.DataFrame,
    method: str = 'constant',
    value: Optional[float] = None,
    limit: Optional[int] = None
) -> pd.DataFrame:
    """
    向量化填充NA
    
    Args:
        data: 输入数据
        method: 填充方法 ('constant', 'ffill', 'bfill', 'interpolate')
        value: 常量填充值
        limit: 最大连续填充次数
        
    Returns:
        填充后的数据
    """
    if method == 'constant':
        return data.fillna(value, limit=limit)
    elif method == 'ffill':
        return data.ffill(limit=limit)
    elif method == 'bfill':
        return data.bfill(limit=limit)
    elif method == 'interpolate':
        return data.interpolate(method='linear', limit=limit)
    else:
        raise ValueError(f"未知填充方法: {method}")


def drop_na_vectorized(
    data: pd.DataFrame,
    axis: int = 1,
    thresh: Optional[int] = None
) -> pd.DataFrame:
    """
    向量化删除NA
    
    Args:
        data: 输入数据
        axis: 删除轴，0=删除行，1=删除列
        thresh: 至少需要多少非NA值
        
    Returns:
        删除NA后的数据
    """
    return data.dropna(axis=axis, thresh=thresh)


# 工厂函数
def create_na_filter(
    strategy: str = 'drop',
    **kwargs
) -> NAFactorFilter:
    """
    创建NA过滤器的工厂函数
    
    Args:
        strategy: 处理策略
        **kwargs: 其他参数
        
    Returns:
        NA过滤器实例
    """
    strategies = {
        'drop': NAFactorDropFilter,
        'fill': NAFactorFillFilter,
        'forward_fill': NAFactorForwardFillFilter,
        'cross_sectional': CrossSectionalNAFilter,
    }
    
    if strategy not in strategies:
        # 默认使用通用NAFactorFilter
        return NAFactorFilter(strategy=strategy, **kwargs)
    
    return strategies[strategy](**kwargs)
