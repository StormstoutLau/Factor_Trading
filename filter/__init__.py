"""
Filter模块 - 股票过滤器集合

提供完整的股票筛选和过滤功能，全部向量化实现，避免循环。

主要组件:
- base: 过滤器基类和通用接口
- extended: 扩展过滤器（日期、换手率、波动率等）
- na_factor: NA/NaN值处理过滤器
- prefix: 股票代码前缀/板块过滤器
- market_cap: 市值相关过滤器
- industry: 行业分类过滤器
- custom: 自定义过滤器

使用方法:
    # 方式1: 从模块导入特定过滤器
    from filter import UniverseFilter, MarketCapFilter
    from filter.prefix import filter_a_share
    from filter.market_cap import filter_large_cap
    
    # 方式2: 使用工厂函数创建过滤器
    from filter import create_filter
    filter_obj = create_filter('market_cap', min_cap=1000000)
    
    # 方式3: 使用便捷函数
    from filter.prefix import filter_gem, filter_kcb
    from filter.market_cap import filter_large_cap, filter_small_cap
"""

# ==================== 基类和配置 ====================
from .base import (
    BaseFilter,
    FilterConfig,
    CompositeFilter,
    FilterChain,
    build_boolean_mask,
    vectorized_filter_by_list,
    fast_date_range_filter,
)

# ==================== 扩展过滤器 ====================
from .extended import (
    ExtendedFilter,
    DateRangeFilter,
    StockPoolFilter,
    TurnoverFilter,
    VolatilityFilter,
    LiquidityFilter,
    create_extended_filter,
)

# ==================== NA因子过滤器 ====================
from .na_factor import (
    NAFactorFilter,
    NAFactorDropFilter,
    NAFactorFillFilter,
    NAFactorForwardFillFilter,
    CrossSectionalNAFilter,
    fill_na_vectorized,
    drop_na_vectorized,
    create_na_filter,
)

# ==================== 前缀过滤器 ====================
from .prefix import (
    PrefixFilter,
    BoardFilter,
    RegexPrefixFilter,
    filter_shanghai_main,
    filter_shenzhen_main,
    filter_gem,
    filter_kcb,
    filter_a_share,
    create_prefix_filter,
)

# ==================== 市值过滤器 ====================
from .market_cap import (
    MarketCapFilter,
    LargeCapFilter,
    SmallCapFilter,
    MidCapFilter,
    MarketCapRatioFilter,
    MarketCapMomentumFilter,
    filter_large_cap,
    filter_small_cap,
    filter_cap_range,
    create_market_cap_filter,
)

# ==================== 行业过滤器 ====================
from .industry import (
    IndustryFilter,
    SectorFilter,
    IndustryExclusionFilter,
    IndustryRotationFilter,
    filter_by_industry,
    exclude_industries,
    filter_sector,
    create_industry_filter,
)

# ==================== 自定义过滤器 ====================
from .custom import (
    CustomFunctionFilter,
    ExpressionFilter,
    MultiConditionFilter,
    DynamicFilter,
    ConditionalFilter,
    create_filter_from_func,
    create_filter_from_expr,
    create_threshold_filter,
    create_range_filter,
    create_custom_filter,
)

# ==================== 原有Universe过滤器 ====================
try:
    from .predictive_listing_filter import PredictiveListDateFilter
    PredictiveListingFilter = PredictiveListDateFilter
except ImportError:
    PredictiveListDateFilter = None
    PredictiveListingFilter = None

from .universe_filter_clean import UniverseFilter


# ==================== 统一工厂函数 ====================
def create_filter(filter_type: str, **kwargs):
    """
    统一的过滤器创建工厂函数
    
    Args:
        filter_type: 过滤器类型，支持:
            - 'universe': 基础宇宙过滤器
            - 'date_range': 日期范围过滤器
            - 'stock_pool': 股票池过滤器
            - 'turnover': 换手率过滤器
            - 'volatility': 波动率过滤器
            - 'liquidity': 流动性过滤器
            - 'na_drop': NA删除过滤器
            - 'na_fill': NA填充过滤器
            - 'prefix': 前缀过滤器
            - 'board': 板块过滤器
            - 'market_cap': 市值过滤器
            - 'large_cap': 大盘股过滤器
            - 'small_cap': 小盘股过滤器
            - 'industry': 行业过滤器
            - 'sector': 板块过滤器
            - 'custom': 自定义过滤器
            - 'expression': 表达式过滤器
        **kwargs: 过滤器特定参数
        
    Returns:
        过滤器实例
        
    Examples:
        >>> from filter import create_filter
        >>> 
        >>> # 创建大盘股过滤器
        >>> filter_obj = create_filter('large_cap', top_n=100, market_cap_data=cap_data)
        >>> 
        >>> # 创建创业板过滤器
        >>> filter_obj = create_filter('board', board='gem')
        >>> 
        >>> # 创建NA删除过滤器
        >>> filter_obj = create_filter('na_drop', threshold=0.1)
    """
    type_mapping = {
        # 基础过滤器
        'universe': UniverseFilter,
        
        # 扩展过滤器
        'date_range': DateRangeFilter,
        'stock_pool': StockPoolFilter,
        'turnover': TurnoverFilter,
        'volatility': VolatilityFilter,
        'liquidity': LiquidityFilter,
        
        # NA过滤器
        'na_drop': NAFactorDropFilter,
        'na_fill': NAFactorFillFilter,
        'na_forward_fill': NAFactorForwardFillFilter,
        
        # 前缀过滤器
        'prefix': PrefixFilter,
        'board': BoardFilter,
        
        # 市值过滤器
        'market_cap': MarketCapFilter,
        'large_cap': LargeCapFilter,
        'small_cap': SmallCapFilter,
        'mid_cap': MidCapFilter,
        
        # 行业过滤器
        'industry': IndustryFilter,
        'sector': SectorFilter,
        
        # 自定义过滤器
        'custom': CustomFunctionFilter,
        'expression': ExpressionFilter,
    }
    
    if filter_type not in type_mapping:
        raise ValueError(
            f"未知过滤器类型: {filter_type}\n"
            f"可用类型: {list(type_mapping.keys())}"
        )
    
    return type_mapping[filter_type](**kwargs)


# ==================== 导出列表 ====================
__all__ = [
    # 基类
    'BaseFilter',
    'FilterConfig',
    'CompositeFilter',
    'FilterChain',
    
    # 扩展过滤器
    'ExtendedFilter',
    'DateRangeFilter',
    'StockPoolFilter',
    'TurnoverFilter',
    'VolatilityFilter',
    'LiquidityFilter',
    
    # NA过滤器
    'NAFactorFilter',
    'NAFactorDropFilter',
    'NAFactorFillFilter',
    'NAFactorForwardFillFilter',
    'CrossSectionalNAFilter',
    
    # 前缀过滤器
    'PrefixFilter',
    'BoardFilter',
    'RegexPrefixFilter',
    
    # 市值过滤器
    'MarketCapFilter',
    'LargeCapFilter',
    'SmallCapFilter',
    'MidCapFilter',
    'MarketCapRatioFilter',
    'MarketCapMomentumFilter',
    
    # 行业过滤器
    'IndustryFilter',
    'SectorFilter',
    'IndustryExclusionFilter',
    'IndustryRotationFilter',
    
    # 自定义过滤器
    'CustomFunctionFilter',
    'ExpressionFilter',
    'MultiConditionFilter',
    'DynamicFilter',
    'ConditionalFilter',
    
    # 原有过滤器
    'UniverseFilter',
    'PredictiveListingFilter',
    
    # 工厂函数
    'create_filter',
    'create_extended_filter',
    'create_na_filter',
    'create_prefix_filter',
    'create_market_cap_filter',
    'create_industry_filter',
    'create_custom_filter',
    
    # 工具函数
    'build_boolean_mask',
    'vectorized_filter_by_list',
    'fast_date_range_filter',
    'fill_na_vectorized',
    'drop_na_vectorized',
    
    # 便捷函数
    'filter_shanghai_main',
    'filter_shenzhen_main',
    'filter_gem',
    'filter_kcb',
    'filter_a_share',
    'filter_large_cap',
    'filter_small_cap',
    'filter_cap_range',
    'filter_by_industry',
    'exclude_industries',
    'filter_sector',
    'create_filter_from_func',
    'create_filter_from_expr',
    'create_threshold_filter',
    'create_range_filter',
]
