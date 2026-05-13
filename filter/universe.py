"""股票池过滤模块 - 基于Backtest_Opus_2.0架构

提供完整的市场约束过滤功能：
- 停牌股票过滤
- 涨跌停股票过滤
- ST股票特殊处理
- 下一交易日可交易性检查
- 预计算掩码优化
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config import UniverseConfig
from data import DataManager

logger = logging.getLogger(__name__)


class UniverseFilter:
    """股票池过滤器
    
    根据市场约束条件过滤股票池，生成可交易股票掩码。
    支持预计算掩码以提高性能。
    """
    
    def __init__(self, data_manager: DataManager, config: UniverseConfig):
        """初始化股票池过滤器
        
        Args:
            data_manager: 数据管理器
            config: 股票池配置
        """
        self.dm = data_manager
        self.cfg = config
        
        # 预计算的掩码
        self._suspend_mask: Optional[pd.DataFrame] = None
        self._limit_up_mask: Optional[pd.DataFrame] = None
        self._limit_down_mask: Optional[pd.DataFrame] = None
        self._st_mask: Optional[pd.DataFrame] = None
        self._next_day_tradable_mask: Optional[pd.DataFrame] = None
        
        # 合并掩码
        self._buyable_mask: Optional[pd.DataFrame] = None
        self._sellable_mask: Optional[pd.DataFrame] = None
        self._tradable_mask: Optional[pd.DataFrame] = None
        
        logger.info("股票池过滤器初始化完成")
    
    def build_masks(self):
        """构建所有过滤掩码"""
        logger.info("开始构建股票池过滤掩码...")
        
        # 构建基础掩码
        self._build_suspend_mask()
        self._build_limit_masks()
        self._build_st_mask()
        
        # 构建下一交易日可交易性掩码
        if self.cfg.check_next_day_tradable:
            self._build_next_day_tradable_mask()
        
        # 构建最终掩码
        self._build_final_masks()
        
        logger.info("股票池过滤掩码构建完成")
    
    def _build_suspend_mask(self):
        """构建停牌掩码"""
        if self.dm.suspend is not None:
            # 停牌数据: 1=停牌, 0=正常
            self._suspend_mask = (self.dm.suspend == 0)
            logger.debug("停牌掩码构建完成")
        else:
            # 如果没有停牌数据，假设所有股票都可交易
            self._suspend_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes
            )
            logger.warning("未找到停牌数据，假设所有股票都可交易")
    
    def _build_limit_masks(self):
        """构建涨跌停掩码"""
        # 计算收益率
        returns = self.dm.returns
        
        # 获取ST状态用于判断涨跌停阈值
        st_data = self.dm.st
        
        # 构建涨跌停掩码
        limit_up_mask = pd.DataFrame(
            True, 
            index=self.dm.trade_dates, 
            columns=self.dm.stock_codes
        )
        limit_down_mask = pd.DataFrame(
            True, 
            index=self.dm.trade_dates, 
            columns=self.dm.stock_codes
        )
        
        for date in returns.index:
            if date == returns.index[0]:  # 第一天没有收益率数据
                continue
            
            daily_return = returns.loc[date]
            prev_date = returns.index[returns.index.get_loc(date) - 1]
            
            for stock in daily_return.index:
                ret = daily_return[stock]
                if pd.isna(ret):
                    continue
                
                # 判断是否为ST股票
                is_st = False
                if st_data is not None:
                    is_st = st_data.loc[prev_date, stock] == 1
                
                # 选择涨跌停阈值
                if is_st:
                    up_threshold = self.cfg.st_limit_up_threshold
                    down_threshold = self.cfg.st_limit_down_threshold
                else:
                    up_threshold = self.cfg.limit_up_threshold
                    down_threshold = self.cfg.limit_down_threshold
                
                # 判断涨跌停
                if ret >= up_threshold:
                    limit_up_mask.loc[date, stock] = False  # 涨停无法买入
                if ret <= down_threshold:
                    limit_down_mask.loc[date, stock] = False  # 跌停无法卖出
        
        self._limit_up_mask = limit_up_mask
        self._limit_down_mask = limit_down_mask
        logger.debug("涨跌停掩码构建完成")
    
    def _build_st_mask(self):
        """构建ST股票掩码"""
        if self.dm.st is not None:
            # ST数据: 1=ST, 0=正常
            # 根据配置决定是否排除ST股票
            if hasattr(self.cfg, 'exclude_st') and self.cfg.exclude_st:
                self._st_mask = (self.dm.st == 0)
                logger.debug("ST股票掩码构建完成（排除ST）")
            else:
                self._st_mask = pd.DataFrame(
                    True, 
                    index=self.dm.trade_dates, 
                    columns=self.dm.stock_codes
                )
                logger.debug("ST股票掩码构建完成（包含ST）")
        else:
            # 如果没有ST数据，假设所有股票都非ST
            self._st_mask = pd.DataFrame(
                True, 
                index=self.dm.trade_dates, 
                columns=self.dm.stock_codes
            )
    
    def _build_next_day_tradable_mask(self):
        """构建下一交易日可交易性掩码"""
        # 检查下一交易日是否仍在交易
        next_day_tradable = pd.DataFrame(
            True, 
            index=self.dm.trade_dates, 
            columns=self.dm.stock_codes
        )
        
        for i, date in enumerate(self.dm.trade_dates):
            if i >= len(self.dm.trade_dates) - 1:  # 最后一天没有下一交易日
                next_day_tradable.loc[date] = False
                continue
            
            next_date = self.dm.trade_dates[i + 1]
            
            # 检查下一日是否停牌
            if self.dm.suspend is not None:
                suspend_next_day = self.dm.suspend.loc[next_date]
                next_day_tradable.loc[date] = (suspend_next_day == 0)
        
        self._next_day_tradable_mask = next_day_tradable
        logger.debug("下一交易日可交易性掩码构建完成")
    
    def _build_final_masks(self):
        """构建最终的可交易掩码"""
        # 可开仓掩码（买入）
        self._buyable_mask = pd.DataFrame(
            True, 
            index=self.dm.trade_dates, 
            columns=self.dm.stock_codes
        )
        
        if self.cfg.exclude_suspended:
            self._buyable_mask &= self._suspend_mask
        
        if self.cfg.exclude_limit_up:
            self._buyable_mask &= self._limit_up_mask
        
        if hasattr(self.cfg, 'exclude_st') and self.cfg.exclude_st:
            self._buyable_mask &= self._st_mask
        
        # 可平仓掩码（卖出）
        self._sellable_mask = pd.DataFrame(
            True, 
            index=self.dm.trade_dates, 
            columns=self.dm.stock_codes
        )
        
        if self.cfg.exclude_suspended:
            self._sellable_mask &= self._suspend_mask
        
        if self.cfg.exclude_limit_down:
            self._sellable_mask &= self._limit_down_mask
        
        if hasattr(self.cfg, 'exclude_st') and self.cfg.exclude_st:
            self._sellable_mask &= self._st_mask
        
        # 可交易掩码（买入和卖出的交集）
        self._tradable_mask = self._buyable_mask & self._sellable_mask
        
        # 如果需要检查下一交易日可交易性
        if self.cfg.check_next_day_tradable:
            self._buyable_mask &= self._next_day_tradable_mask
            self._tradable_mask = self._buyable_mask & self._sellable_mask
        
        logger.info("最终可交易掩码构建完成")
    
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
    
    def filter_stocks(self, date: str | pd.Timestamp, 
                     stocks: list[str] | pd.Index,
                     filter_type: str = "tradable") -> list[str]:
        """过滤指定日期的股票列表
        
        Args:
            date: 交易日期
            stocks: 股票列表
            filter_type: 过滤类型 ('buyable', 'sellable', 'tradable')
            
        Returns:
            过滤后的股票列表
        """
        date = pd.to_datetime(date)
        
        if filter_type == "buyable":
            mask = self.buyable.loc[date]
        elif filter_type == "sellable":
            mask = self.sellable.loc[date]
        elif filter_type == "tradable":
            mask = self.tradable.loc[date]
        else:
            raise ValueError(f"未知的过滤类型: {filter_type}")
        
        # 过滤股票
        filtered_stocks = [stock for stock in stocks if mask.get(stock, False)]
        
        return filtered_stocks
    
    def get_universe_stats(self, date: str | pd.Timestamp) -> dict[str, int]:
        """获取指定日期的股票池统计信息
        
        Args:
            date: 交易日期
            
        Returns:
            股票池统计信息
        """
        date = pd.to_datetime(date)
        
        stats = {
            'total_stocks': len(self.dm.stock_codes),
            'buyable': self.buyable.loc[date].sum(),
            'sellable': self.sellable.loc[date].sum(),
            'tradable': self.tradable.loc[date].sum()
        }
        
        # 添加各约束的影响
        if self.cfg.exclude_suspended and self._suspend_mask is not None:
            stats['suspended'] = (~self._suspend_mask.loc[date]).sum()
        
        if self.cfg.exclude_limit_up and self._limit_up_mask is not None:
            stats['limit_up'] = (~self._limit_up_mask.loc[date]).sum()
        
        if self.cfg.exclude_limit_down and self._limit_down_mask is not None:
            stats['limit_down'] = (~self._limit_down_mask.loc[date]).sum()
        
        if hasattr(self.cfg, 'exclude_st') and self.cfg.exclude_st and self._st_mask is not None:
            stats['st_stocks'] = (~self._st_mask.loc[date]).sum()
        
        return stats
    
    def get_mask_summary(self) -> dict[str, Any]:
        """获取掩码摘要信息
        
        Returns:
            掩码摘要信息
        """
        if self._tradable_mask is None:
            self.build_masks()
        
        summary = {
            'config': {
                'exclude_suspended': self.cfg.exclude_suspended,
                'exclude_limit_up': self.cfg.exclude_limit_up,
                'exclude_limit_down': self.cfg.exclude_limit_down,
                'check_next_day_tradable': self.cfg.check_next_day_tradable
            },
            'mask_shapes': {
                'buyable': self._buyable_mask.shape,
                'sellable': self._sellable_mask.shape,
                'tradable': self._tradable_mask.shape
            },
            'average_tradable_ratio': self._tradable_mask.mean().mean(),
            'average_buyable_ratio': self._buyable_mask.mean().mean(),
            'average_sellable_ratio': self._sellable_mask.mean().mean()
        }
        
        return summary
