#!/usr/bin/env python3
"""
股票池过滤器 - 清理版本
整合了所有过滤功能，采用向量化操作，代码结构清晰
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class UniverseFilterConfig:
    """股票池过滤配置"""
    
    # 基础过滤
    exclude_suspended: bool = True
    exclude_limit_up: bool = True
    exclude_limit_down: bool = True
    exclude_st: bool = True
    check_next_day_tradable: bool = True
    
    # 涨跌停阈值
    limit_up_threshold: float = 0.095
    limit_down_threshold: float = -0.095
    st_limit_up_threshold: float = 0.048
    st_limit_down_threshold: float = -0.048
    
    # 扩展过滤
    exclude_na_factors: bool = False
    na_factor_names: List[str] = field(default_factory=lambda: ['factor_value'])
    na_threshold: float = 0.3
    
    exclude_stock_prefixes: bool = False
    excluded_prefixes: List[str] = field(default_factory=lambda: ['300', '688'])
    
    exclude_by_market_cap: bool = False
    min_market_cap: float = 1e9
    max_market_cap: float = 5e11
    
    exclude_industries: bool = False
    excluded_industries: List[str] = field(default_factory=list)
    
    enable_custom_filters: bool = False
    custom_filter_configs: Dict[str, Any] = field(default_factory=dict)

class UniverseFilter:
    """股票池过滤器 - 清理版本"""
    
    def __init__(self, data_manager, config: UniverseFilterConfig):
        """初始化过滤器
        
        Args:
            data_manager: 数据管理器
            config: 过滤配置
        """
        self.dm = data_manager
        self.cfg = config
        
        # 预计算信息
        self._prefix_info = {}
        
        # 过滤掩码
        self._suspend_mask: Optional[pd.DataFrame] = None
        self._limit_up_mask: Optional[pd.DataFrame] = None
        self._limit_down_mask: Optional[pd.DataFrame] = None
        self._st_mask: Optional[pd.DataFrame] = None
        self._next_day_tradable_mask: Optional[pd.DataFrame] = None
        self._na_factor_mask: Optional[pd.DataFrame] = None
        self._stock_prefix_mask: Optional[pd.DataFrame] = None
        self._market_cap_mask: Optional[pd.DataFrame] = None
        self._industry_mask: Optional[pd.DataFrame] = None
        self._custom_masks: Dict[str, pd.DataFrame] = {}
        
        # 最终掩码
        self._buyable_mask: Optional[pd.DataFrame] = None
        self._sellable_mask: Optional[pd.DataFrame] = None
        self._tradable_mask: Optional[pd.DataFrame] = None
        
        logger.info("股票池过滤器初始化完成")
    
    def build_masks(self):
        """构建所有过滤掩码"""
        logger.info("开始构建股票池过滤掩码...")
        
        # 预计算基础信息
        self._precompute_basic_info()
        
        # 构建基础掩码
        self._build_suspend_mask()
        self._build_limit_masks()
        self._build_st_mask()
        
        # 构建扩展掩码
        if self.cfg.check_next_day_tradable:
            self._build_next_day_tradable_mask()
        
        if self.cfg.exclude_na_factors:
            self._build_na_factor_mask()
        
        if self.cfg.exclude_stock_prefixes:
            self._build_stock_prefix_mask()
        
        if self.cfg.exclude_by_market_cap:
            self._build_market_cap_mask()
        
        if self.cfg.exclude_industries:
            self._build_industry_mask()
        
        if self.cfg.enable_custom_filters:
            self._build_custom_masks()
        
        # 构建最终掩码
        self._build_final_masks()
        
        logger.info("股票池过滤掩码构建完成")
    
    def _precompute_basic_info(self):
        """预计算基础信息"""
        if self.cfg.exclude_stock_prefixes:
            self._prefix_info = {}
            for stock_code in self.dm.stock_codes:
                self._prefix_info[stock_code] = any(
                    stock_code.startswith(prefix) for prefix in self.cfg.excluded_prefixes
                )
    
    def _build_suspend_mask(self):
        """构建停牌掩码"""
        if self.dm.suspend is not None:
            self._suspend_mask = (self.dm.suspend == 0)
        else:
            self._suspend_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
            logger.warning("未找到停牌数据，假设所有股票都可交易")
    
    def _build_limit_masks(self):
        """构建涨跌停掩码"""
        if self.dm.returns is None:
            logger.warning("未找到收益率数据，跳过涨跌停过滤")
            self._limit_up_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
            self._limit_down_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
            return
        
        # 向量化计算
        returns = self.dm.returns
        returns_shifted = returns.shift(1)
        
        # 获取ST状态
        st_data = self.dm.st if self.dm.st is not None else pd.DataFrame(
            0, index=returns.index, columns=returns.columns
        )
        st_shifted = st_data.shift(1)
        
        # 向量化计算阈值
        up_thresholds = np.where(
            st_shifted == 1,
            self.cfg.st_limit_up_threshold,
            self.cfg.limit_up_threshold
        )
        down_thresholds = np.where(
            st_shifted == 1,
            self.cfg.st_limit_down_threshold,
            self.cfg.limit_down_threshold
        )
        
        # 创建阈值DataFrame
        up_threshold_df = pd.DataFrame(
            up_thresholds,
            index=returns.index,
            columns=returns.columns
        )
        down_threshold_df = pd.DataFrame(
            down_thresholds,
            index=returns.index,
            columns=returns.columns
        )
        
        # 向量化判断涨跌停
        self._limit_up_mask = ~(returns >= up_threshold_df)
        self._limit_down_mask = ~(returns <= down_threshold_df)
        
        # 第一天设为True
        if len(returns) > 0:
            self._limit_up_mask.iloc[0] = True
            self._limit_down_mask.iloc[0] = True
    
    def _build_st_mask(self):
        """构建ST股票掩码"""
        if self.dm.st is not None:
            if self.cfg.exclude_st:
                self._st_mask = (self.dm.st == 0)
            else:
                self._st_mask = pd.DataFrame(
                    True, 
                    index=self.dm.trade_dates, 
                    columns=self.dm.stock_codes,
                    dtype=bool
                )
        else:
            self._st_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
    
    def _build_next_day_tradable_mask(self):
        """构建下一交易日可交易性掩码"""
        if self.dm.suspend is not None:
            suspend_shifted = self.dm.suspend.shift(-1)
            self._next_day_tradable_mask = (suspend_shifted == 0)
            
            # 最后一天设为False
            if len(self._next_day_tradable_mask) > 0:
                self._next_day_tradable_mask.iloc[-1] = False
        else:
            self._next_day_tradable_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
    
    def _build_na_factor_mask(self):
        """构建因子NA过滤掩码"""
        na_mask = pd.DataFrame(
            True, 
            index=self.dm.trade_dates, 
            columns=self.dm.stock_codes,
            dtype=bool
        )
        
        for factor_name in self.cfg.na_factor_names:
            if hasattr(self.dm, factor_name):
                factor_data = getattr(self.dm, factor_name)
                
                # 向量化计算NA比例
                na_ratios = factor_data.isna().mean(axis=1)
                high_na_dates = na_ratios > self.cfg.na_threshold
                
                # 设置掩码
                na_mask.loc[high_na_dates] = False
                
                logger.debug(f"因子 {factor_name} NA过滤: {high_na_dates.sum()} 个日期被过滤")
        
        self._na_factor_mask = na_mask
    
    def _build_stock_prefix_mask(self):
        """构建股票代码前缀过滤掩码"""
        if hasattr(self, '_prefix_info'):
            # 使用预计算信息
            prefix_data = [not self._prefix_info.get(stock, False) for stock in self.dm.stock_codes]
            prefix_array = np.tile(prefix_data, (len(self.dm.trade_dates), 1))
            self._stock_prefix_mask = pd.DataFrame(
                prefix_array,
                index=self.dm.trade_dates,
                columns=self.dm.stock_codes,
                dtype=bool
            )
        else:
            # 备选方案
            self._stock_prefix_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
            
            for prefix in self.cfg.excluded_prefixes:
                excluded_stocks = [stock for stock in self.dm.stock_codes if stock.startswith(prefix)]
                if excluded_stocks:
                    self._stock_prefix_mask[excluded_stocks] = False
    
    def _build_market_cap_mask(self):
        """构建市值过滤掩码"""
        if self.dm.mktcap is not None:
            self._market_cap_mask = (
                (self.dm.mktcap >= self.cfg.min_market_cap) & 
                (self.dm.mktcap <= self.cfg.max_market_cap)
            )
        else:
            logger.warning("未找到市值数据，跳过市值过滤")
            self._market_cap_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
    
    def _build_industry_mask(self):
        """构建行业过滤掩码"""
        if self.dm.industry is not None:
            industry_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
            
            for industry in self.cfg.excluded_industries:
                industry_mask &= (self.dm.industry != industry)
            
            self._industry_mask = industry_mask
        else:
            logger.warning("未找到行业数据，跳过行业过滤")
            self._industry_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
    
    def _build_custom_masks(self):
        """构建自定义过滤掩码"""
        for filter_name, filter_config in self.cfg.custom_filter_configs.items():
            try:
                mask = self._apply_custom_filter(filter_name, filter_config)
                self._custom_masks[filter_name] = mask
                logger.info(f"自定义过滤 {filter_name} 构建完成")
            except Exception as e:
                logger.error(f"构建自定义过滤 {filter_name} 失败: {e}")
    
    def _apply_custom_filter(self, filter_name: str, filter_config: Dict[str, Any]) -> pd.DataFrame:
        """应用自定义过滤条件"""
        filter_type = filter_config.get('type', 'simple')
        
        if filter_type == 'simple':
            data_source = filter_config['data_source']
            condition = filter_config['condition']
            
            if hasattr(self.dm, data_source):
                data = getattr(self.dm, data_source)
                return eval(f"data {condition}")
        
        elif filter_type == 'function':
            func = filter_config['function']
            return func(self.dm)
        
        # 默认返回全True
        return pd.DataFrame(
            True, 
            index=self.dm.trade_dates, 
            columns=self.dm.stock_codes,
            dtype=bool
        )
    
    def _build_final_masks(self):
        """构建最终的可交易掩码"""
        # 收集买入掩码
        buyable_masks = []
        
        if self.cfg.exclude_suspended and self._suspend_mask is not None:
            buyable_masks.append(self._suspend_mask)
        
        if self.cfg.exclude_limit_up and self._limit_up_mask is not None:
            buyable_masks.append(self._limit_up_mask)
        
        if self.cfg.exclude_st and self._st_mask is not None:
            buyable_masks.append(self._st_mask)
        
        if self.cfg.exclude_na_factors and self._na_factor_mask is not None:
            buyable_masks.append(self._na_factor_mask)
        
        if self.cfg.exclude_stock_prefixes and self._stock_prefix_mask is not None:
            buyable_masks.append(self._stock_prefix_mask)
        
        if self.cfg.exclude_by_market_cap and self._market_cap_mask is not None:
            buyable_masks.append(self._market_cap_mask)
        
        if self.cfg.exclude_industries and self._industry_mask is not None:
            buyable_masks.append(self._industry_mask)
        
        # 添加自定义掩码
        for mask in self._custom_masks.values():
            buyable_masks.append(mask)
        
        # 构建买入掩码
        if buyable_masks:
            self._buyable_mask = buyable_masks[0].copy()
            for mask in buyable_masks[1:]:
                self._buyable_mask &= mask
        else:
            self._buyable_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
        
        # 构建卖出掩码
        sellable_masks = []
        
        if self.cfg.exclude_suspended and self._suspend_mask is not None:
            sellable_masks.append(self._suspend_mask)
        
        if self.cfg.exclude_limit_down and self._limit_down_mask is not None:
            sellable_masks.append(self._limit_down_mask)
        
        if self.cfg.exclude_st and self._st_mask is not None:
            sellable_masks.append(self._st_mask)
        
        if self.cfg.exclude_na_factors and self._na_factor_mask is not None:
            sellable_masks.append(self._na_factor_mask)
        
        if self.cfg.exclude_stock_prefixes and self._stock_prefix_mask is not None:
            sellable_masks.append(self._stock_prefix_mask)
        
        if self.cfg.exclude_by_market_cap and self._market_cap_mask is not None:
            sellable_masks.append(self._market_cap_mask)
        
        if self.cfg.exclude_industries and self._industry_mask is not None:
            sellable_masks.append(self._industry_mask)
        
        # 添加自定义掩码
        for mask in self._custom_masks.values():
            sellable_masks.append(mask)
        
        # 构建卖出掩码
        if sellable_masks:
            self._sellable_mask = sellable_masks[0].copy()
            for mask in sellable_masks[1:]:
                self._sellable_mask &= mask
        else:
            self._sellable_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes,
                dtype=bool
            )
        
        # 构建可交易掩码
        self._tradable_mask = self._buyable_mask & self._sellable_mask
        
        # 下一交易日可交易性检查
        if self.cfg.check_next_day_tradable and self._next_day_tradable_mask is not None:
            self._buyable_mask &= self._next_day_tradable_mask
            self._tradable_mask = self._buyable_mask & self._sellable_mask
    
    def filter_stocks(self, date: str, stocks: List[str], filter_type: str = 'tradable') -> List[str]:
        """过滤股票列表
        
        Args:
            date: 日期
            stocks: 股票列表
            filter_type: 过滤类型 ('buyable', 'sellable', 'tradable')
            
        Returns:
            过滤后的股票列表
        """
        if self._tradable_mask is None:
            self.build_masks()
        
        mask_map = {
            'buyable': self._buyable_mask,
            'sellable': self._sellable_mask,
            'tradable': self._tradable_mask
        }
        
        mask = mask_map.get(filter_type, self._tradable_mask)
        
        if date not in mask.index:
            logger.warning(f"日期 {date} 不在掩码索引中")
            return stocks
        
        date_mask = mask.loc[date]
        filtered_stocks = [stock for stock in stocks if stock in date_mask.index and date_mask[stock]]
        
        return filtered_stocks
    
    def get_universe_stats(self, date: str) -> Dict[str, Any]:
        """获取股票池统计信息
        
        Args:
            date: 日期
            
        Returns:
            统计信息字典
        """
        if self._tradable_mask is None:
            self.build_masks()
        
        if date not in self._tradable_mask.index:
            return {}
        
        stats = {
            'total_stocks': len(self.dm.stock_codes),
            'buyable': self._buyable_mask.loc[date].sum(),
            'sellable': self._sellable_mask.loc[date].sum(),
            'tradable': self._tradable_mask.loc[date].sum()
        }
        
        stats['buyable_ratio'] = stats['buyable'] / stats['total_stocks']
        stats['sellable_ratio'] = stats['sellable'] / stats['total_stocks']
        stats['tradable_ratio'] = stats['tradable'] / stats['total_stocks']
        
        return stats
    
    def get_mask_summary(self) -> Dict[str, Any]:
        """获取掩码汇总信息"""
        if self._tradable_mask is None:
            self.build_masks()
        
        summary = {
            'buyable_coverage': self._buyable_mask.mean().mean(),
            'sellable_coverage': self._sellable_mask.mean().mean(),
            'tradable_coverage': self._tradable_mask.mean().mean(),
            'memory_usage_mb': {
                'buyable': self._buyable_mask.memory_usage(deep=True).sum() / 1024 / 1024,
                'sellable': self._sellable_mask.memory_usage(deep=True).sum() / 1024 / 1024,
                'tradable': self._tradable_mask.memory_usage(deep=True).sum() / 1024 / 1024
            }
        }
        
        return summary
    
    @property
    def buyable(self) -> pd.DataFrame:
        """可开仓掩码（可买入）"""
        if self._buyable_mask is None:
            self.build_masks()
        return self._buyable_mask
    
    @property
    def sellable(self) -> pd.DataFrame:
        """可平仓掩码（可卖出）"""
        if self._sellable_mask is None:
            self.build_masks()
        return self._sellable_mask
    
    @property
    def tradable(self) -> pd.DataFrame:
        """可交易掩码（可买入和卖出）"""
        if self._tradable_mask is None:
            self.build_masks()
        return self._tradable_mask

# 便捷函数
def create_universe_filter(data_manager, **kwargs) -> UniverseFilter:
    """创建股票池过滤器的便捷函数
    
    Args:
        data_manager: 数据管理器
        **kwargs: 配置参数
        
    Returns:
        股票池过滤器实例
    """
    config = UniverseFilterConfig(**kwargs)
    return UniverseFilter(data_manager, config)

# 预定义配置
def get_conservative_config() -> UniverseFilterConfig:
    """获取保守配置（严格过滤）"""
    return UniverseFilterConfig(
        exclude_suspended=True,
        exclude_limit_up=True,
        exclude_limit_down=True,
        exclude_st=True,
        check_next_day_tradable=True,
        
        exclude_na_factors=True,
        na_threshold=0.2,
        
        exclude_stock_prefixes=True,
        excluded_prefixes=['300', '688'],
        
        exclude_by_market_cap=True,
        min_market_cap=5e9,
        max_market_cap=1e11,
        
        exclude_industries=True,
        excluded_industries=['房地产', '钢铁', '煤炭']
    )

def get_aggressive_config() -> UniverseFilterConfig:
    """获取激进配置（宽松过滤）"""
    return UniverseFilterConfig(
        exclude_suspended=True,
        exclude_limit_up=False,
        exclude_limit_down=False,
        exclude_st=False,
        check_next_day_tradable=False,
        
        exclude_na_factors=False,
        
        exclude_stock_prefixes=False,
        
        exclude_by_market_cap=False,
        
        exclude_industries=False
    )

def get_balanced_config() -> UniverseFilterConfig:
    """获取平衡配置（适中过滤）"""
    return UniverseFilterConfig(
        exclude_suspended=True,
        exclude_limit_up=True,
        exclude_limit_down=True,
        exclude_st=True,
        check_next_day_tradable=True,
        
        exclude_na_factors=True,
        na_threshold=0.3,
        
        exclude_stock_prefixes=False,
        
        exclude_by_market_cap=True,
        min_market_cap=1e9,
        max_market_cap=5e11,
        
        exclude_industries=False
    )
