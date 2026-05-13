"""
扩展过滤器模块

提供基于各种条件的扩展过滤功能，全部向量化实现
"""

from typing import Optional, List, Dict, Any, Union, Callable
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from .base import BaseFilter, FilterConfig

logger = logging.getLogger(__name__)


class ExtendedFilter(BaseFilter):
    """
    扩展过滤器基类
    
    提供通用扩展过滤功能，支持多种过滤条件的向量化组合
    """
    
    def __init__(self, config: Optional[FilterConfig] = None):
        super().__init__(config)
        self.conditions: List[Dict[str, Any]] = []
        
    def add_condition(
        self, 
        field: str, 
        operator: str, 
        value: Any,
        logic: str = 'and'
    ):
        """
        添加过滤条件
        
        Args:
            field: 字段名
            operator: 操作符 ('>', '<', '>=', '<=', '==', '!=', 'in', 'not_in')
            value: 比较值
            logic: 与前一条件的逻辑关系 ('and', 'or')
        """
        self.conditions.append({
            'field': field,
            'operator': operator,
            'value': value,
            'logic': logic
        })
        return self  # 支持链式调用
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        根据条件构建掩码（向量化）
        """
        if not self.conditions:
            # 无条件时返回全True
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 初始化掩码
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        for i, condition in enumerate(self.conditions):
            field = condition['field']
            operator = condition['operator']
            value = condition['value']
            logic = condition['logic']
            
            # 获取字段数据（假设data包含该字段或使用外部数据）
            field_data = self._get_field_data(data, field)
            
            # 向量化条件判断
            if operator == '>':
                cond_mask = field_data > value
            elif operator == '<':
                cond_mask = field_data < value
            elif operator == '>=':
                cond_mask = field_data >= value
            elif operator == '<=':
                cond_mask = field_data <= value
            elif operator == '==':
                cond_mask = field_data == value
            elif operator == '!=':
                cond_mask = field_data != value
            elif operator == 'in':
                cond_mask = field_data.isin(value)
            elif operator == 'not_in':
                cond_mask = ~field_data.isin(value)
            else:
                logger.warning(f"未知操作符: {operator}")
                continue
            
            # 向量化逻辑组合
            if i == 0 or logic == 'and':
                mask &= cond_mask
            else:  # logic == 'or'
                mask |= cond_mask
        
        self._mask = mask
        return mask
    
    def _get_field_data(self, data: pd.DataFrame, field: str) -> pd.DataFrame:
        """
        获取字段数据（子类可重写）
        
        Args:
            data: 输入数据
            field: 字段名
            
        Returns:
            字段数据DataFrame
        """
        if field in data.columns:
            return data[field]
        return pd.DataFrame(np.nan, index=data.index, columns=data.columns)


class DateRangeFilter(BaseFilter):
    """
    日期范围过滤器（向量化）
    """
    
    def __init__(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(config)
        self.start_date = start_date
        self.end_date = end_date
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建日期范围掩码（向量化）"""
        dates = data.index
        
        # 向量化日期判断
        mask = pd.Series(True, index=dates)
        
        if self.start_date is not None:
            mask &= dates >= self.start_date
        if self.end_date is not None:
            mask &= dates <= self.end_date
        
        # 广播到DataFrame形状
        mask_df = pd.DataFrame(
            np.tile(mask.values.reshape(-1, 1), len(data.columns)),
            index=data.index,
            columns=data.columns
        )
        
        self._mask = mask_df
        return mask_df


class StockPoolFilter(BaseFilter):
    """
    股票池过滤器（向量化）
    
    基于预设股票池进行过滤
    """
    
    def __init__(
        self,
        stock_pool: Union[List[str], pd.Index, set],
        config: Optional[FilterConfig] = None
    ):
        super().__init__(config)
        self.stock_pool = set(stock_pool)
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建股票池掩码（向量化）"""
        # 向量化判断股票是否在池中
        valid_cols = [col for col in data.columns if col in self.stock_pool]
        
        # 创建掩码
        mask = pd.DataFrame(False, index=data.index, columns=data.columns)
        mask[valid_cols] = True
        
        self._mask = mask
        return mask
    
    def update_stock_pool(self, stock_pool: Union[List[str], pd.Index, set]):
        """更新股票池"""
        self.stock_pool = set(stock_pool)
        self._mask = None  # 重置缓存


class TurnoverFilter(BaseFilter):
    """
    换手率过滤器（向量化）
    
    基于换手率数据进行过滤
    """
    
    def __init__(
        self,
        min_turnover: Optional[float] = None,
        max_turnover: Optional[float] = None,
        turnover_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(config)
        self.min_turnover = min_turnover
        self.max_turnover = max_turnover
        self.turnover_data = turnover_data
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建换手率掩码（向量化）"""
        if self.turnover_data is None:
            logger.warning("未提供换手率数据，返回全True")
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 对齐数据
        turnover = self.turnover_data.reindex_like(data)
        
        # 向量化条件判断
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        if self.min_turnover is not None:
            mask &= turnover >= self.min_turnover
        if self.max_turnover is not None:
            mask &= turnover <= self.max_turnover
        
        self._mask = mask
        return mask


class VolatilityFilter(BaseFilter):
    """
    波动率过滤器（向量化）
    
    基于历史波动率进行过滤
    """
    
    def __init__(
        self,
        window: int = 20,
        min_volatility: Optional[float] = None,
        max_volatility: Optional[float] = None,
        price_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(config)
        self.window = window
        self.min_volatility = min_volatility
        self.max_volatility = max_volatility
        self.price_data = price_data
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建波动率掩码（向量化）"""
        if self.price_data is None:
            logger.warning("未提供价格数据，返回全True")
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 向量化计算收益率
        returns = self.price_data.pct_change()
        
        # 向量化计算滚动波动率（年化）
        volatility = returns.rolling(window=self.window).std() * np.sqrt(252)
        
        # 对齐数据
        volatility = volatility.reindex_like(data)
        
        # 向量化条件判断
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        if self.min_volatility is not None:
            mask &= volatility >= self.min_volatility
        if self.max_volatility is not None:
            mask &= volatility <= self.max_volatility
        
        self._mask = mask
        return mask


class LiquidityFilter(BaseFilter):
    """
    流动性过滤器（向量化）
    
    基于成交量/成交额进行过滤
    """
    
    def __init__(
        self,
        min_volume: Optional[float] = None,
        min_amount: Optional[float] = None,
        volume_data: Optional[pd.DataFrame] = None,
        amount_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(config)
        self.min_volume = min_volume
        self.min_amount = min_amount
        self.volume_data = volume_data
        self.amount_data = amount_data
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建流动性掩码（向量化）"""
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 成交量过滤
        if self.min_volume is not None and self.volume_data is not None:
            volume = self.volume_data.reindex_like(data)
            mask &= volume >= self.min_volume
        
        # 成交额过滤
        if self.min_amount is not None and self.amount_data is not None:
            amount = self.amount_data.reindex_like(data)
            mask &= amount >= self.min_amount
        
        self._mask = mask
        return mask


# 工厂函数
def create_extended_filter(
    filter_type: str,
    **kwargs
) -> BaseFilter:
    """
    创建扩展过滤器的工厂函数
    
    Args:
        filter_type: 过滤器类型 ('date_range', 'stock_pool', 'turnover', 
                                'volatility', 'liquidity', 'extended')
        **kwargs: 过滤器特定参数
        
    Returns:
        过滤器实例
    """
    filters = {
        'date_range': DateRangeFilter,
        'stock_pool': StockPoolFilter,
        'turnover': TurnoverFilter,
        'volatility': VolatilityFilter,
        'liquidity': LiquidityFilter,
        'extended': ExtendedFilter,
    }
    
    if filter_type not in filters:
        raise ValueError(f"未知过滤器类型: {filter_type}，可用类型: {list(filters.keys())}")
    
    return filters[filter_type](**kwargs)
