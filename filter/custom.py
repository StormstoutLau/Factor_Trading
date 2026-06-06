"""
自定义过滤器模块

提供灵活自定义过滤逻辑的接口，支持：
- 函数式过滤器（传入自定义函数）
- 表达式过滤器（字符串表达式）
- 组合自定义条件
全部向量化实现
"""

from typing import Optional, Callable, Union, Dict, Any, List
import pandas as pd
import numpy as np
from datetime import datetime
import logging

from .base import BaseFilter, FilterConfig

logger = logging.getLogger(__name__)


class CustomFunctionFilter(BaseFilter):
    """
    自定义函数过滤器（向量化）
    
    允许用户传入自定义过滤函数
    """
    
    def __init__(
        self,
        filter_func: Callable[[pd.DataFrame], pd.DataFrame],
        config: Optional[FilterConfig] = None,
        **kwargs
    ):
        """
        初始化自定义函数过滤器
        
        Args:
            filter_func: 过滤函数，接收DataFrame返回布尔掩码DataFrame
            config: 配置对象
            **kwargs: 传递给过滤函数的额外参数
        """
        super().__init__(config)
        self.filter_func = filter_func
        self.func_kwargs = kwargs
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        使用自定义函数构建掩码
        
        Args:
            data: 输入数据
            
        Returns:
            布尔掩码DataFrame
        """
        try:
            # 调用自定义函数
            mask = self.filter_func(data, **self.func_kwargs)
            
            # 确保返回布尔DataFrame
            if not isinstance(mask, pd.DataFrame):
                raise ValueError("过滤函数必须返回DataFrame")
            
            # 对齐索引
            mask = mask.reindex_like(data).fillna(False).astype(bool)
            
            self._mask = mask
            return mask
            
        except Exception as e:
            logger.error(f"自定义过滤函数执行失败: {e}")
            # 返回全True，避免中断流程
            return pd.DataFrame(True, index=data.index, columns=data.columns)


class ExpressionFilter(BaseFilter):
    """
    表达式过滤器（向量化）
    
    使用字符串表达式定义过滤条件
    支持pandas eval语法
    """
    
    def __init__(
        self,
        expression: str,
        local_dict: Optional[Dict[str, Any]] = None,
        config: Optional[FilterConfig] = None
    ):
        """
        初始化表达式过滤器
        
        Args:
            expression: 过滤表达式，如 "close > ma20 & volume > 1000000"
            local_dict: 额外变量字典
            config: 配置对象
        """
        super().__init__(config)
        self.expression = expression
        self.local_dict = local_dict or {}
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        使用表达式构建掩码（向量化）
        
        Args:
            data: 输入数据
            
        Returns:
            布尔掩码DataFrame
        """
        try:
            # 准备环境
            env = {
                'pd': pd,
                'np': np,
                'data': data,
            }
            env.update(self.local_dict)
            
            # 执行表达式
            result = eval(self.expression, {"__builtins__": {}}, env)
            
            # 确保返回布尔DataFrame
            if isinstance(result, pd.DataFrame):
                mask = result.fillna(False).astype(bool)
            elif isinstance(result, pd.Series):
                # 广播到DataFrame
                mask = pd.DataFrame(
                    np.tile(result.values.reshape(-1, 1), len(data.columns)),
                    index=data.index,
                    columns=data.columns
                )
            else:
                raise ValueError("表达式必须返回DataFrame或Series")
            
            self._mask = mask
            return mask
            
        except Exception as e:
            logger.error(f"表达式执行失败: {e}")
            return pd.DataFrame(True, index=data.index, columns=data.columns)


class MultiConditionFilter(BaseFilter):
    """
    多条件组合过滤器（向量化）
    
    支持复杂的AND/OR/NOT条件组合
    """
    
    def __init__(
        self,
        conditions: List[Dict[str, Any]],
        config: Optional[FilterConfig] = None
    ):
        """
        初始化多条件过滤器
        
        Args:
            conditions: 条件列表，每个条件是字典：
                {
                    'type': 'filter'|'expression'|'function',
                    'value': 过滤器实例|表达式字符串|函数,
                    'logic': 'and'|'or'|'not',
                    'params': 额外参数
                }
            config: 配置对象
        """
        super().__init__(config)
        self.conditions = conditions
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建多条件组合掩码（向量化）
        """
        if not self.conditions:
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 初始化结果
        result = None
        
        for i, condition in enumerate(self.conditions):
            cond_type = condition.get('type', 'filter')
            cond_value = condition['value']
            logic = condition.get('logic', 'and')
            params = condition.get('params', {})
            
            # 获取当前条件的掩码
            if cond_type == 'filter':
                mask = cond_value.build_mask(data)
            elif cond_type == 'expression':
                filter_obj = ExpressionFilter(cond_value, params)
                mask = filter_obj.build_mask(data)
            elif cond_type == 'function':
                filter_obj = CustomFunctionFilter(cond_value, params)
                mask = filter_obj.build_mask(data)
            else:
                logger.warning(f"未知条件类型: {cond_type}")
                continue
            
            # 处理NOT逻辑
            if logic == 'not':
                mask = ~mask
                logic = 'and'  # NOT后转为AND
            
            # 组合条件
            if result is None:
                result = mask
            elif logic == 'and':
                result &= mask
            elif logic == 'or':
                result |= mask
        
        if result is None:
            result = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        self._mask = result
        return result


class DynamicFilter(BaseFilter):
    """
    动态过滤器（向量化）
    
    根据动态条件（如日期、市场状态）调整过滤逻辑
    """
    
    def __init__(
        self,
        filter_rules: Dict[Any, BaseFilter],
        selector: Callable[[pd.DataFrame], Any],
        default_filter: Optional[BaseFilter] = None,
        config: Optional[FilterConfig] = None
    ):
        """
        初始化动态过滤器
        
        Args:
            filter_rules: 过滤规则字典，key是选择器返回值，value是对应过滤器
            selector: 选择器函数，接收data返回key
            default_filter: 默认过滤器（无匹配规则时使用）
            config: 配置对象
        """
        super().__init__(config)
        self.filter_rules = filter_rules
        self.selector = selector
        self.default_filter = default_filter
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        动态构建掩码
        """
        try:
            # 获取当前选择器值
            key = self.selector(data)
            
            # 查找对应过滤器
            if key in self.filter_rules:
                filter_obj = self.filter_rules[key]
            elif self.default_filter is not None:
                filter_obj = self.default_filter
            else:
                # 无匹配规则，返回全True
                return pd.DataFrame(True, index=data.index, columns=data.columns)
            
            # 执行过滤
            mask = filter_obj.build_mask(data)
            self._mask = mask
            return mask
            
        except Exception as e:
            logger.error(f"动态过滤失败: {e}")
            return pd.DataFrame(True, index=data.index, columns=data.columns)


class ConditionalFilter(BaseFilter):
    """
    条件过滤器（向量化）
    
    基于条件选择不同过滤策略
    """
    
    def __init__(
        self,
        condition: Callable[[pd.DataFrame], pd.Series],
        true_filter: BaseFilter,
        false_filter: BaseFilter,
        config: Optional[FilterConfig] = None
    ):
        """
        初始化条件过滤器
        
        Args:
            condition: 条件函数，返回布尔Series（按日期）
            true_filter: 条件为True时使用的过滤器
            false_filter: 条件为False时使用的过滤器
            config: 配置对象
        """
        super().__init__(config)
        self.condition = condition
        self.true_filter = true_filter
        self.false_filter = false_filter
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建条件掩码（向量化）
        """
        try:
            # 评估条件
            cond_result = self.condition(data)
            
            # 获取两种情况的掩码
            true_mask = self.true_filter.build_mask(data)
            false_mask = self.false_filter.build_mask(data)
            
            # 根据条件组合（向量化）
            cond_broadcast = pd.DataFrame(
                np.tile(cond_result.values.reshape(-1, 1), len(data.columns)),
                index=data.index,
                columns=data.columns
            )
            
            mask = np.where(cond_broadcast, true_mask, false_mask)
            mask = pd.DataFrame(mask, index=data.index, columns=data.columns)
            
            self._mask = mask
            return mask
            
        except Exception as e:
            logger.error(f"条件过滤失败: {e}")
            return pd.DataFrame(True, index=data.index, columns=data.columns)


# 便捷函数
def create_filter_from_func(
    func: Callable[[pd.DataFrame], pd.DataFrame],
    **kwargs
) -> CustomFunctionFilter:
    """
    从函数快速创建过滤器
    
    Args:
        func: 过滤函数
        **kwargs: 额外参数
        
    Returns:
        自定义函数过滤器
    """
    return CustomFunctionFilter(func, **kwargs)


def create_filter_from_expr(
    expression: str,
    **kwargs
) -> ExpressionFilter:
    """
    从表达式快速创建过滤器
    
    Args:
        expression: 过滤表达式
        **kwargs: 额外参数
        
    Returns:
        表达式过滤器
    """
    return ExpressionFilter(expression, **kwargs)


# 预定义的一些常用自定义过滤器

def create_threshold_filter(
    column: str,
    threshold: float,
    operator: str = '>'
) -> ExpressionFilter:
    """
    创建阈值过滤器
    
    Args:
        column: 列名
        threshold: 阈值
        operator: 比较操作符 '>', '<', '>=', '<=', '=='
        
    Returns:
        表达式过滤器
    """
    expression = f"data['{column}'] {operator} {threshold}"
    return ExpressionFilter(expression)


def create_range_filter(
    column: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> MultiConditionFilter:
    """
    创建范围过滤器
    
    Args:
        column: 列名
        min_val: 最小值
        max_val: 最大值
        
    Returns:
        多条件过滤器
    """
    conditions = []
    
    if min_val is not None:
        conditions.append({
            'type': 'expression',
            'value': f"data['{column}'] >= {min_val}",
            'logic': 'and'
        })
    
    if max_val is not None:
        conditions.append({
            'type': 'expression',
            'value': f"data['{column}'] <= {max_val}",
            'logic': 'and'
        })
    
    return MultiConditionFilter(conditions)


# 工厂函数
def create_custom_filter(
    filter_type: str = 'function',
    **kwargs
) -> BaseFilter:
    """
    创建自定义过滤器的工厂函数
    
    Args:
        filter_type: 过滤器类型 ('function', 'expression', 'multi', 'dynamic', 'conditional')
        **kwargs: 特定参数
        
    Returns:
        自定义过滤器实例
    """
    filters = {
        'function': CustomFunctionFilter,
        'expression': ExpressionFilter,
        'multi': MultiConditionFilter,
        'dynamic': DynamicFilter,
        'conditional': ConditionalFilter,
    }
    
    if filter_type not in filters:
        raise ValueError(f"未知过滤器类型: {filter_type}，可用: {list(filters.keys())}")
    
    return filters[filter_type](**kwargs)
