"""
前缀过滤器模块

基于股票代码前缀进行过滤，如沪深主板、创业板、科创板等
全部向量化实现
"""

from typing import Optional, Union, List, Set, Dict
import pandas as pd
import numpy as np
import re
import logging

from .base import BaseFilter, FilterConfig

logger = logging.getLogger(__name__)


class PrefixFilter(BaseFilter):
    """
    股票代码前缀过滤器（向量化）
    
    支持按交易所、板块等前缀过滤：
    - 上海主板: 600, 601, 603, 605
    - 深圳主板: 000, 001, 002
    - 创业板: 300, 301
    - 科创板: 688, 689
    - 北交所: 430, 830, 87, 88
    """
    
    # 定义板块前缀映射
    EXCHANGE_PREFIXES = {
        'sh_main': ['600', '601', '603', '605', '609'],  # 上海主板
        'sz_main': ['000', '001', '002', '003'],         # 深圳主板（含中小板）
        'gem': ['300', '301', '302'],                    # 创业板
        'kcb': ['688', '689', '68U'],                    # 科创板
        'bse': ['430', '830', '87', '88', '89', '92'],  # 北交所
        'sh_b': ['900'],                                 # 上海B股
        'sz_b': ['200'],                                 # 深圳B股
    }
    
    def __init__(
        self,
        include_prefixes: Optional[Union[List[str], str]] = None,
        exclude_prefixes: Optional[Union[List[str], str]] = None,
        include_exchanges: Optional[Union[List[str], str]] = None,
        exclude_exchanges: Optional[Union[List[str], str]] = None,
        remove_suffix: bool = True,  # 是否移除.SZ/.SH后缀
        config: Optional[FilterConfig] = None
    ):
        """
        初始化前缀过滤器
        
        Args:
            include_prefixes: 包含的前缀列表或逗号分隔字符串，如 ['600', '601'] 或 '600,601'
            exclude_prefixes: 排除的前缀列表
            include_exchanges: 包含的交易所/板块，如 ['sh_main', 'gem']
            exclude_exchanges: 排除的交易所/板块
            remove_suffix: 是否移除股票代码中的.SZ/.SH后缀
            config: 配置对象
        """
        super().__init__(config)
        
        self.remove_suffix = remove_suffix
        
        # 处理包含前缀
        self.include_prefixes = self._parse_prefixes(include_prefixes)
        
        # 处理排除前缀
        self.exclude_prefixes = self._parse_prefixes(exclude_prefixes)
        
        # 处理交易所/板块
        self.include_exchanges = self._parse_exchanges(include_exchanges)
        self.exclude_exchanges = self._parse_exchanges(exclude_exchanges)
        
        # 从交易所/板块扩展前缀
        self._expand_exchange_prefixes()
    
    def _parse_prefixes(
        self, 
        prefixes: Optional[Union[List[str], str]]
    ) -> Set[str]:
        """解析前缀参数"""
        if prefixes is None:
            return set()
        
        if isinstance(prefixes, str):
            return set(p.strip() for p in prefixes.split(','))
        
        return set(prefixes)
    
    def _parse_exchanges(
        self,
        exchanges: Optional[Union[List[str], str]]
    ) -> Set[str]:
        """解析交易所参数"""
        if exchanges is None:
            return set()
        
        if isinstance(exchanges, str):
            return set(e.strip() for e in exchanges.split(','))
        
        return set(exchanges)
    
    def _expand_exchange_prefixes(self):
        """从交易所/板块定义扩展前缀"""
        # 处理包含的交易所
        for exchange in self.include_exchanges:
            if exchange in self.EXCHANGE_PREFIXES:
                self.include_prefixes.update(self.EXCHANGE_PREFIXES[exchange])
        
        # 处理排除的交易所
        for exchange in self.exclude_exchanges:
            if exchange in self.EXCHANGE_PREFIXES:
                self.exclude_prefixes.update(self.EXCHANGE_PREFIXES[exchange])
    
    def _clean_stock_code(self, code: str) -> str:
        """清理股票代码，移除后缀"""
        if self.remove_suffix:
            # 移除.SZ, .SH, .BJ后缀
            code = re.sub(r'\.(SZ|SH|BJ)$', '', code, flags=re.IGNORECASE)
        return code
    
    def _get_code_prefix(self, code: str) -> str:
        """获取股票代码前缀（前3位或前2位）"""
        code = self._clean_stock_code(code)
        
        # 取前3位，如果不足3位取全部
        prefix = code[:3] if len(code) >= 3 else code
        
        # 对于北交所部分代码（2位前缀）特殊处理
        if len(prefix) == 3 and prefix.startswith(('87', '88', '89', '92')):
            prefix = prefix[:2]
        
        return prefix
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建前缀过滤掩码（向量化）
        
        Args:
            data: 输入数据DataFrame，列名为股票代码
            
        Returns:
            布尔掩码DataFrame
        """
        stocks = data.columns
        
        # 向量化提取所有股票的前缀
        prefixes = pd.Series([self._get_code_prefix(str(code)) for code in stocks], index=stocks)
        
        # 初始化掩码（全True）
        mask = pd.DataFrame(True, index=data.index, columns=stocks)
        
        # 处理包含规则（如果有指定，只保留匹配的前缀）
        if self.include_prefixes:
            # 向量化判断每个股票是否在包含列表中
            valid_by_prefix = prefixes.isin(self.include_prefixes)
            
            # 将结果广播到所有日期
            mask &= pd.DataFrame(
                np.tile(valid_by_prefix.values, (len(data.index), 1)),
                index=data.index,
                columns=stocks
            )
        
        # 处理排除规则
        if self.exclude_prefixes:
            # 向量化判断每个股票是否在排除列表中
            invalid_by_prefix = prefixes.isin(self.exclude_prefixes)
            
            # 排除这些股票
            mask &= ~pd.DataFrame(
                np.tile(invalid_by_prefix.values, (len(data.index), 1)),
                index=data.index,
                columns=stocks
            )
        
        self._mask = mask
        return mask
    
    def get_prefix_stats(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        获取前缀统计信息（向量化）
        
        Args:
            data: 输入数据
            
        Returns:
            前缀统计DataFrame
        """
        stocks = data.columns
        
        # 提取前缀
        prefixes = [self._get_code_prefix(str(code)) for code in stocks]
        
        # 统计每个前缀的数量
        prefix_counts = pd.Series(prefixes).value_counts()
        
        # 分类到交易所
        stats = []
        for prefix, count in prefix_counts.items():
            exchange = self._classify_prefix(prefix)
            stats.append({
                'prefix': prefix,
                'count': count,
                'exchange': exchange
            })
        
        return pd.DataFrame(stats)
    
    def _classify_prefix(self, prefix: str) -> str:
        """将前缀分类到交易所/板块"""
        for exchange, prefixes in self.EXCHANGE_PREFIXES.items():
            if prefix in prefixes:
                return exchange
        return 'unknown'
    
    def get_exchange_distribution(self, data: pd.DataFrame) -> pd.Series:
        """
        获取交易所分布（向量化）
        
        Returns:
            各交易所股票数量
        """
        stats = self.get_prefix_stats(data)
        return stats.groupby('exchange')['count'].sum()


class BoardFilter(PrefixFilter):
    """
    板块过滤器（简化版前缀过滤器）
    
    快速过滤主板/创业板/科创板等
    """
    
    BOARD_DEFINITIONS = {
        'main': {  # 主板（沪深主板）
            'include_exchanges': ['sh_main', 'sz_main']
        },
        'gem': {   # 创业板
            'include_exchanges': ['gem']
        },
        'kcb': {   # 科创板
            'include_exchanges': ['kcb']
        },
        'bse': {   # 北交所
            'include_exchanges': ['bse']
        },
        'a_share': {  # A股（不含B股）
            'include_exchanges': ['sh_main', 'sz_main', 'gem', 'kcb']
        },
        'all_but_bse': {  # 除北交所以外
            'include_exchanges': ['sh_main', 'sz_main', 'gem', 'kcb']
        }
    }
    
    def __init__(
        self,
        board: str = 'a_share',
        config: Optional[FilterConfig] = None
    ):
        """
        初始化板块过滤器
        
        Args:
            board: 板块名称 ('main', 'gem', 'kcb', 'bse', 'a_share', 'all_but_bse')
            config: 配置对象
        """
        if board not in self.BOARD_DEFINITIONS:
            raise ValueError(f"未知板块: {board}，可用: {list(self.BOARD_DEFINITIONS.keys())}")
        
        board_config = self.BOARD_DEFINITIONS[board]
        
        super().__init__(
            include_exchanges=board_config['include_exchanges'],
            config=config
        )
        
        self.board = board


class RegexPrefixFilter(BaseFilter):
    """
    正则表达式前缀过滤器（向量化）
    
    使用正则表达式匹配股票代码
    """
    
    def __init__(
        self,
        pattern: str,
        include: bool = True,  # True=保留匹配，False=排除匹配
        remove_suffix: bool = True,
        config: Optional[FilterConfig] = None
    ):
        """
        初始化正则前缀过滤器
        
        Args:
            pattern: 正则表达式模式
            include: True表示保留匹配项，False表示排除匹配项
            remove_suffix: 是否移除后缀
            config: 配置对象
        """
        super().__init__(config)
        self.pattern = re.compile(pattern)
        self.include = include
        self.remove_suffix = remove_suffix
    
    def _clean_code(self, code: str) -> str:
        """清理股票代码"""
        if self.remove_suffix:
            return re.sub(r'\.(SZ|SH|BJ)$', '', code, flags=re.IGNORECASE)
        return code
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建正则匹配掩码（向量化）"""
        stocks = data.columns
        
        # 向量化匹配
        matches = [bool(self.pattern.match(self._clean_code(str(code)))) for code in stocks]
        matches_series = pd.Series(matches, index=stocks)
        
        # 根据include参数决定保留哪些
        if self.include:
            valid = matches_series
        else:
            valid = ~matches_series
        
        # 广播到DataFrame形状
        mask = pd.DataFrame(
            np.tile(valid.values, (len(data.index), 1)),
            index=data.index,
            columns=stocks
        )
        
        self._mask = mask
        return mask


# 便捷函数
def filter_shanghai_main(data: pd.DataFrame) -> pd.DataFrame:
    """过滤上海主板（向量化便捷函数）"""
    filter_obj = PrefixFilter(include_exchanges='sh_main')
    return filter_obj.apply(data)


def filter_shenzhen_main(data: pd.DataFrame) -> pd.DataFrame:
    """过滤深圳主板（向量化便捷函数）"""
    filter_obj = PrefixFilter(include_exchanges='sz_main')
    return filter_obj.apply(data)


def filter_gem(data: pd.DataFrame) -> pd.DataFrame:
    """过滤创业板（向量化便捷函数）"""
    filter_obj = PrefixFilter(include_exchanges='gem')
    return filter_obj.apply(data)


def filter_kcb(data: pd.DataFrame) -> pd.DataFrame:
    """过滤科创板（向量化便捷函数）"""
    filter_obj = PrefixFilter(include_exchanges='kcb')
    return filter_obj.apply(data)


def filter_a_share(data: pd.DataFrame) -> pd.DataFrame:
    """过滤A股（不含B股和北交所）（向量化便捷函数）"""
    filter_obj = PrefixFilter(
        include_exchanges=['sh_main', 'sz_main', 'gem', 'kcb']
    )
    return filter_obj.apply(data)


# 工厂函数
def create_prefix_filter(
    filter_type: str = 'board',
    **kwargs
) -> PrefixFilter:
    """
    创建前缀过滤器的工厂函数
    
    Args:
        filter_type: 过滤器类型 ('board', 'prefix', 'regex')
        **kwargs: 特定参数
        
    Returns:
        前缀过滤器实例
    """
    if filter_type == 'board':
        return BoardFilter(**kwargs)
    elif filter_type == 'prefix':
        return PrefixFilter(**kwargs)
    elif filter_type == 'regex':
        return RegexPrefixFilter(**kwargs)
    else:
        raise ValueError(f"未知过滤器类型: {filter_type}")
