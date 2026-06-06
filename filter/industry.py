"""
行业过滤器模块

基于行业分类数据进行过滤
全部向量化实现
"""

from typing import Optional, Union, List, Set, Dict
import pandas as pd
import numpy as np
import logging

from .base import BaseFilter, FilterConfig

logger = logging.getLogger(__name__)


class IndustryFilter(BaseFilter):
    """
    行业过滤器（向量化）
    
    基于行业分类进行过滤，支持：
    - 包含/排除特定行业
    - 行业数量限制
    - 行业权重限制
    """
    
    # A股常见行业分类（申万/中信）
    COMMON_INDUSTRIES = {
        '银行', '非银金融', '房地产', '医药生物', '电子', '计算机',
        '传媒', '通信', '食品饮料', '家用电器', '汽车', '机械设备',
        '建筑装饰', '建筑材料', '钢铁', '有色金属', '化工', '采掘',
        '公用事业', '交通运输', '商业贸易', '休闲服务', '轻工制造',
        '纺织服装', '农林牧渔', '国防军工', '电气设备', '综合'
    }
    
    def __init__(
        self,
        include_industries: Optional[Union[List[str], str]] = None,
        exclude_industries: Optional[Union[List[str], str]] = None,
        industry_data: Optional[pd.DataFrame] = None,  # 行业分类数据
        max_industries: Optional[int] = None,
        min_industry_weight: Optional[float] = None,
        config: Optional[FilterConfig] = None
    ):
        """
        初始化行业过滤器
        
        Args:
            include_industries: 包含的行业列表或逗号分隔字符串
            exclude_industries: 排除的行业列表
            industry_data: 行业分类DataFrame (日期 x 股票)，值为行业名称
            max_industries: 最多保留几个行业
            min_industry_weight: 最小行业权重（比例）
            config: 配置对象
        """
        super().__init__(config)
        
        self.include_industries = self._parse_industries(include_industries)
        self.exclude_industries = self._parse_industries(exclude_industries)
        self.industry_data = industry_data
        self.max_industries = max_industries
        self.min_industry_weight = min_industry_weight
    
    def _parse_industries(self, industries: Optional[Union[List[str], str]]) -> Set[str]:
        """解析行业参数"""
        if industries is None:
            return set()
        
        if isinstance(industries, str):
            return set(i.strip() for i in industries.split(','))
        
        return set(industries)
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        构建行业过滤掩码（向量化）
        
        Args:
            data: 输入数据（用于对齐索引）
            
        Returns:
            布尔掩码DataFrame
        """
        if self.industry_data is None:
            logger.warning("未提供行业数据，返回全True")
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 对齐行业数据
        industry = self.industry_data.reindex_like(data)
        
        # 初始化掩码
        mask = pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 1. 包含行业过滤（向量化）
        if self.include_industries:
            # 使用isin进行向量化判断
            in_include = industry.isin(self.include_industries)
            mask &= in_include
        
        # 2. 排除行业过滤（向量化）
        if self.exclude_industries:
            in_exclude = industry.isin(self.exclude_industries)
            mask &= ~in_exclude
        
        # 3. 行业数量限制（向量化，逐日计算）
        if self.max_industries is not None:
            # 逐日计算每个行业有多少股票，然后选择前N个行业
            def limit_industries(day_data, day_mask):
                # 只考虑有效股票
                valid_industries = day_data[day_mask]
                
                if valid_industries.empty:
                    return pd.Series(False, index=day_data.index)
                
                # 统计各行业数量
                industry_counts = valid_industries.value_counts()
                
                # 取前N个行业
                top_industries = industry_counts.head(self.max_industries).index
                
                # 返回新的掩码
                return day_data.isin(top_industries) & day_mask
            
            # 应用行业数量限制
            for date in data.index:
                mask.loc[date] = limit_industries(industry.loc[date], mask.loc[date])
        
        self._mask = mask
        return mask
    
    def get_industry_distribution(self, date: Optional[pd.Timestamp] = None) -> pd.Series:
        """
        获取行业分布（向量化）
        
        Args:
            date: 日期，None表示最新日期
            
        Returns:
            各行业股票数量
        """
        if self.industry_data is None:
            return pd.Series()
        
        if date is None:
            date = self.industry_data.index[-1]
        
        if date not in self.industry_data.index:
            return pd.Series()
        
        day_data = self.industry_data.loc[date]
        return day_data.value_counts()
    
    def get_industry_stats(self) -> pd.DataFrame:
        """
        获取行业统计信息
        
        Returns:
            行业统计DataFrame
        """
        if self.industry_data is None:
            return pd.DataFrame()
        
        # 统计每个日期各行业数量
        daily_counts = []
        for date in self.industry_data.index:
            day_dist = self.get_industry_distribution(date)
            day_dist.name = date
            daily_counts.append(day_dist)
        
        # 合并统计
        if daily_counts:
            result = pd.DataFrame(daily_counts).fillna(0).astype(int)
            return result
        
        return pd.DataFrame()


class SectorFilter(IndustryFilter):
    """
    板块过滤器（行业过滤器的简化版）
    
    快速过滤主要板块
    """
    
    SECTOR_DEFINITIONS = {
        'financial': ['银行', '非银金融', '房地产'],  # 金融地产
        'technology': ['电子', '计算机', '传媒', '通信'],  # 科技
        'consumption': ['食品饮料', '家用电器', '汽车', '商业贸易', '休闲服务'],  # 消费
        'healthcare': ['医药生物'],  # 医药
        'manufacturing': ['机械设备', '电气设备', '国防军工'],  # 制造
        'cyclical': ['钢铁', '有色金属', '化工', '采掘', '建筑材料'],  # 周期
        'infrastructure': ['建筑装饰', '公用事业', '交通运输'],  # 基建
        'defensive': ['银行', '医药生物', '食品饮料', '公用事业'],  # 防御性
    }
    
    def __init__(
        self,
        sector: str,
        industry_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        """
        初始化板块过滤器
        
        Args:
            sector: 板块名称
            industry_data: 行业数据
            config: 配置对象
        """
        if sector not in self.SECTOR_DEFINITIONS:
            raise ValueError(f"未知板块: {sector}，可用: {list(self.SECTOR_DEFINITIONS.keys())}")
        
        super().__init__(
            include_industries=self.SECTOR_DEFINITIONS[sector],
            industry_data=industry_data,
            config=config
        )
        
        self.sector = sector


class IndustryExclusionFilter(IndustryFilter):
    """
    行业排除过滤器（向量化简化版）
    
    快速排除特定行业
    """
    
    def __init__(
        self,
        exclude: Union[List[str], str],
        industry_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        super().__init__(
            exclude_industries=exclude,
            industry_data=industry_data,
            config=config
        )


class IndustryRotationFilter(BaseFilter):
    """
    行业轮动过滤器（向量化）
    
    基于行业动量/表现进行轮动选择
    """
    
    def __init__(
        self,
        lookback: int = 20,
        top_n: int = 5,
        industry_data: Optional[pd.DataFrame] = None,
        returns_data: Optional[pd.DataFrame] = None,
        config: Optional[FilterConfig] = None
    ):
        """
        初始化行业轮动过滤器
        
        Args:
            lookback: 回看周期
            top_n: 选择前N个行业
            industry_data: 行业分类数据
            returns_data: 收益率数据
            config: 配置对象
        """
        super().__init__(config)
        self.lookback = lookback
        self.top_n = top_n
        self.industry_data = industry_data
        self.returns_data = returns_data
    
    def build_mask(self, data: pd.DataFrame) -> pd.DataFrame:
        """构建轮动掩码（向量化）"""
        if self.industry_data is None or self.returns_data is None:
            return pd.DataFrame(True, index=data.index, columns=data.columns)
        
        # 对齐数据
        industry = self.industry_data.reindex_like(data)
        returns = self.returns_data.reindex_like(data)
        
        # 初始化掩码
        mask = pd.DataFrame(False, index=data.index, columns=data.columns)
        
        # 向量化计算各行业动量（逐日）
        for i in range(len(data.index)):
            date = data.index[i]
            
            if i < self.lookback:
                # 数据不足，保留所有
                mask.loc[date] = True
                continue
            
            # 计算回看期收益率
            period_returns = returns.iloc[i-self.lookback:i]
            
            # 按行业聚合计算平均收益
            day_industry = industry.loc[date]
            
            # 计算各行业平均收益
            industry_returns = {}
            for ind in day_industry.unique():
                if pd.isna(ind):
                    continue
                stocks_in_ind = day_industry[day_industry == ind].index
                ind_return = period_returns[stocks_in_ind].mean().mean()
                industry_returns[ind] = ind_return
            
            # 选择前N行业
            top_industries = sorted(
                industry_returns.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:self.top_n]
            top_industry_names = [ind for ind, _ in top_industries]
            
            # 设置掩码
            mask.loc[date] = day_industry.isin(top_industry_names)
        
        self._mask = mask
        return mask


# 便捷函数
def filter_by_industry(
    data: pd.DataFrame,
    industry_data: pd.DataFrame,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None
) -> pd.DataFrame:
    """按行业过滤（向量化便捷函数）"""
    filter_obj = IndustryFilter(
        include_industries=include,
        exclude_industries=exclude,
        industry_data=industry_data
    )
    return filter_obj.apply(data)


def exclude_industries(
    data: pd.DataFrame,
    industry_data: pd.DataFrame,
    exclude: Union[List[str], str]
) -> pd.DataFrame:
    """排除行业（向量化便捷函数）"""
    filter_obj = IndustryExclusionFilter(exclude=exclude, industry_data=industry_data)
    return filter_obj.apply(data)


def filter_sector(
    data: pd.DataFrame,
    industry_data: pd.DataFrame,
    sector: str
) -> pd.DataFrame:
    """按板块过滤（向量化便捷函数）"""
    filter_obj = SectorFilter(sector=sector, industry_data=industry_data)
    return filter_obj.apply(data)


# 工厂函数
def create_industry_filter(
    filter_type: str = 'include',
    **kwargs
) -> IndustryFilter:
    """
    创建行业过滤器的工厂函数
    
    Args:
        filter_type: 过滤器类型 ('include', 'exclude', 'sector', 'rotation')
        **kwargs: 特定参数
        
    Returns:
        行业过滤器实例
    """
    filters = {
        'include': IndustryFilter,
        'exclude': IndustryExclusionFilter,
        'sector': SectorFilter,
        'rotation': IndustryRotationFilter,
    }
    
    if filter_type not in filters:
        raise ValueError(f"未知过滤器类型: {filter_type}，可用: {list(filters.keys())}")
    
    return filters[filter_type](**kwargs)
