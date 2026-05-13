"""
过滤器基类模块

提供所有过滤器的抽象基类和通用向量化操作接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union
import pandas as pd
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FilterConfig:
    """过滤器配置基类"""
    
    def __init__(self, **kwargs):
        """初始化配置"""
        self.config = kwargs
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """支持字典式访问"""
        return self.config[key]
    
    def __contains__(self, key: str) -> bool:
        """支持in操作符"""
        return key in self.config


class BaseFilter(ABC):
    """
    过滤器抽象基类
    
    所有具体过滤器必须继承此类，实现向量化过滤逻辑
    """
    
    def __init__(self, config: Optional[FilterConfig] = None):
        """
        初始化过滤器
        
        Args:
            config: 过滤器配置对象
        """
        self.config = config or FilterConfig()
        self._mask: Optional[pd.DataFrame] = None  # 缓存的布尔掩码
        self._data_manager = None
        
    @abstractmethod
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建过滤掩码（向量化实现）
        
        Args:
            data: 输入数据 DataFrame (日期 x 股票)
            
        Returns:
            布尔掩码 DataFrame，True表示保留该股票
        """
        pass
    
    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        应用过滤器（向量化）
        
        Args:
            data: 输入数据 DataFrame
            
        Returns:
            过滤后的数据，被过滤的位置为NaN
        """
        mask = self.build_mask(data)
        # 使用where方法进行向量化过滤
        return data.where(mask, other=np.nan)
    
    def get_valid_stocks(self, date: datetime) -> pd.Index:
        """
        获取指定日期的有效股票列表
        
        Args:
            date: 查询日期
            
        Returns:
            有效股票代码索引
        """
        if self._mask is None:
            raise ValueError("掩码未构建，请先调用build_mask或apply")
        
        if date not in self._mask.index:
            return pd.Index([])
        
        # 向量化获取当日有效股票
        day_mask = self._mask.loc[date]
        return day_mask[day_mask].index
    
    def filter_stocks_vectorized(
        self, 
        stock_codes: pd.Index, 
        date: datetime
    ) -> pd.Index:
        """
        向量化过滤股票代码
        
        Args:
            stock_codes: 待过滤的股票代码索引
            date: 过滤日期
            
        Returns:
            过滤后的股票代码索引
        """
        valid_stocks = self.get_valid_stocks(date)
        # 使用向量化交集操作
        return stock_codes.intersection(valid_stocks)
    
    def reset(self):
        """重置过滤器状态"""
        self._mask = None
        
    @property
    def mask(self) -> Optional[pd.DataFrame]:
        """获取当前掩码"""
        return self._mask
    
    def get_coverage_stats(self) -> Dict[str, float]:
        """
        获取覆盖率统计（向量化计算）
        
        Returns:
            统计信息字典
        """
        if self._mask is None:
            return {'coverage': 0.0, 'total_cells': 0, 'valid_cells': 0}
        
        # 向量化计算统计
        total_cells = self._mask.size
        valid_cells = self._mask.sum().sum()
        coverage = valid_cells / total_cells if total_cells > 0 else 0.0
        
        return {
            'coverage': coverage,
            'total_cells': total_cells,
            'valid_cells': int(valid_cells),
            'avg_daily_stocks': self._mask.sum(axis=1).mean(),
            'dates': len(self._mask.index),
            'stocks': len(self._mask.columns)
        }


class CompositeFilter(BaseFilter):
    """
    组合过滤器
    
    将多个过滤器组合成一个，支持AND/OR逻辑
    """
    
    def __init__(
        self, 
        filters: List[BaseFilter],
        logic: str = 'and',
        config: Optional[FilterConfig] = None
    ):
        """
        初始化组合过滤器
        
        Args:
            filters: 过滤器列表
            logic: 组合逻辑，'and' 或 'or'
            config: 配置对象
        """
        super().__init__(config)
        self.filters = filters
        self.logic = logic.lower()
        
        if self.logic not in ('and', 'or'):
            raise ValueError("logic必须是 'and' 或 'or'")
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建组合掩码（向量化）
        
        Args:
            data: 输入数据
            
        Returns:
            组合后的布尔掩码
        """
        if not self.filters:
            # 没有过滤器时返回全True
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 获取所有过滤器的掩码
        masks = [f.build_mask(data) for f in self.filters]
        
        # 向量化组合
        if self.logic == 'and':
            # 使用all方法进行AND组合
            combined_mask = pd.concat(masks, axis=0).groupby(level=0).all()
        else:  # 'or'
            # 使用any方法进行OR组合
            combined_mask = pd.concat(masks, axis=0).groupby(level=0).any()
        
        # 确保形状一致
        combined_mask = combined_mask.reindex(index=data.index, columns=data.columns)
        
        self._mask = combined_mask
        return combined_mask
    
    def add_filter(self, filter_obj: BaseFilter):
        """添加过滤器"""
        self.filters.append(filter_obj)
        self._mask = None  # 重置缓存
    
    def remove_filter(self, index: int):
        """移除指定位置的过滤器"""
        if 0 <= index < len(self.filters):
            del self.filters[index]
            self._mask = None


class FilterChain:
    """
    过滤器链
    
    按顺序应用多个过滤器，每个过滤器的输出作为下一个的输入
    """
    
    def __init__(self, filters: Optional[List[BaseFilter]] = None):
        """
        初始化过滤器链
        
        Args:
            filters: 过滤器列表
        """
        self.filters = filters or []
        self._intermediate_results: List[pd.DataFrame] = []
    
    def add(self, filter_obj: BaseFilter):
        """添加过滤器到链尾"""
        self.filters.append(filter_obj)
        return self  # 支持链式调用
    
    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        顺序应用所有过滤器（向量化）
        
        Args:
            data: 初始数据
            
        Returns:
            最终过滤结果
        """
        result = data.copy()
        self._intermediate_results = [result.copy()]
        
        for i, filter_obj in enumerate(self.filters):
            logger.debug(f"应用过滤器 {i+1}/{len(self.filters)}: {type(filter_obj).__name__}")
            result = filter_obj.apply(result)
            self._intermediate_results.append(result.copy())
        
        return result
    
    def get_intermediate_results(self) -> List[pd.DataFrame]:
        """获取中间结果"""
        return self._intermediate_results


# 向量化工具函数
def build_boolean_mask(
    dates: pd.DatetimeIndex,
    stocks: pd.Index,
    condition: Union[pd.Series, pd.DataFrame, np.ndarray],
    default: bool = True
) -> pd.DataFrame:
    """
    构建布尔掩码（向量化）
    
    Args:
        dates: 日期索引
        stocks: 股票代码索引
        condition: 过滤条件
        default: 默认填充值
        
    Returns:
        布尔掩码DataFrame
    """
    # 创建全True/False的掩码
    mask = pd.DataFrame(default, index=dates, columns=stocks)
    
    # 应用条件（向量化）
    if isinstance(condition, pd.DataFrame):
        # 对齐索引后更新
        mask = mask.reindex_like(condition)
        mask = condition.fillna(default)
    elif isinstance(condition, pd.Series):
        # 广播Series到DataFrame
        if condition.index.equals(dates):
            # 按日期广播
            mask = mask.apply(lambda x: condition, axis=0)
        elif condition.index.equals(stocks):
            # 按股票广播
            mask = mask.apply(lambda x: condition, axis=1)
    elif isinstance(condition, np.ndarray):
        if condition.shape == mask.shape:
            mask = pd.DataFrame(condition, index=dates, columns=stocks)
    
    return mask.astype(bool)


def vectorized_filter_by_list(
    data: pd.DataFrame,
    valid_items: Union[List, pd.Index, set],
    axis: int = 1
) -> pd.DataFrame:
    """
    向量化列表过滤
    
    Args:
        data: 输入数据
        valid_items: 有效项目列表
        axis: 过滤轴，0=按日期，1=按股票
        
    Returns:
        过滤后的数据
    """
    valid_set = set(valid_items)
    
    if axis == 1:
        # 按股票过滤（列）
        valid_cols = [col for col in data.columns if col in valid_set]
        return data[valid_cols]
    else:
        # 按日期过滤（行）
        valid_rows = [idx for idx in data.index if idx in valid_set]
        return data.loc[valid_rows]


def fast_date_range_filter(
    data: pd.DataFrame,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> pd.DataFrame:
    """
    快速日期范围过滤（向量化）
    
    Args:
        data: 输入数据
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        过滤后的数据
    """
    mask = pd.Series(True, index=data.index)
    
    if start_date is not None:
        mask &= data.index >= start_date
    if end_date is not None:
        mask &= data.index <= end_date
    
    return data.loc[mask]
