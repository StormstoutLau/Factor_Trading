"""再平衡触发器模块 - 基于Backtest_Opus_2.0架构

提供多种再平衡触发方式：
- 固定间隔触发（每日、每周、每月、N天）
- 条件触发（信号变化、回撤触发、波动率触发）
- 混合模式（固定间隔+条件触发）
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import RebalanceConfig

logger = logging.getLogger(__name__)


class BaseTrigger:
    """再平衡触发器基类"""
    
    def __init__(self, config: RebalanceConfig):
        """初始化触发器
        
        Args:
            config: 再平衡配置
        """
        self.cfg = config
        logger.info(f"{self.__class__.__name__} 初始化完成")
    
    def should_trigger(self, date: pd.Timestamp, **kwargs) -> bool:
        """判断是否触发再平衡
        
        Args:
            date: 当前日期
            **kwargs: 其他参数
            
        Returns:
            是否触发再平衡
        """
        raise NotImplementedError("子类必须实现should_trigger方法")


class FixedIntervalTrigger(BaseTrigger):
    """固定间隔触发器"""
    
    def __init__(self, config: RebalanceConfig, trade_dates: pd.DatetimeIndex):
        """初始化固定间隔触发器
        
        Args:
            config: 再平衡配置
            trade_dates: 交易日期索引
        """
        super().__init__(config)
        self.trade_dates = trade_dates
        self._rebalance_dates = self._calculate_rebalance_dates()
        logger.info(f"固定间隔触发器计算了{len(self._rebalance_dates)}个再平衡日期")
    
    def _calculate_rebalance_dates(self) -> set[pd.Timestamp]:
        """计算再平衡日期
        
        Returns:
            再平衡日期集合
        """
        rebalance_dates = set()
        
        if self.cfg.frequency == "daily":
            # 每日
            rebalance_dates.update(self.trade_dates)
            
        elif self.cfg.frequency == "weekly":
            # 每周（最后一个交易日）
            for i, date in enumerate(self.trade_dates):
                if i == len(self.trade_dates) - 1:
                    rebalance_dates.add(date)
                elif date.weekday() > self.trade_dates[i + 1].weekday():
                    # 当前日期是本周最后一个交易日
                    rebalance_dates.add(date)
                    
        elif self.cfg.frequency == "monthly":
            # 每月（最后一个交易日）
            for i, date in enumerate(self.trade_dates):
                if i == len(self.trade_dates) - 1:
                    rebalance_dates.add(date)
                elif date.month != self.trade_dates[i + 1].month:
                    # 当前日期是本月最后一个交易日
                    rebalance_dates.add(date)
                    
        elif self.cfg.frequency == "N_days":
            # 每N天
            for i in range(0, len(self.trade_dates), self.cfg.n_days):
                rebalance_dates.add(self.trade_dates[i])
        
        return rebalance_dates
    
    def should_trigger(self, date: pd.Timestamp, **kwargs) -> bool:
        """判断是否触发再平衡
        
        Args:
            date: 当前日期
            **kwargs: 其他参数（未使用）
            
        Returns:
            是否触发再平衡
        """
        return date in self._rebalance_dates


class ConditionalTrigger(BaseTrigger):
    """条件触发器"""
    
    def __init__(self, config: RebalanceConfig):
        """初始化条件触发器
        
        Args:
            config: 再平衡配置
        """
        super().__init__(config)
        self._last_signal: Optional[pd.Series] = None
        self._last_portfolio_value: Optional[float] = None
        self._last_volatility: Optional[float] = None
        self._last_rebalance_date: Optional[pd.Timestamp] = None
    
    def should_trigger(self, date: pd.Timestamp, **kwargs) -> bool:
        """判断是否触发再平衡
        
        Args:
            date: 当前日期
            **kwargs: 包含signal, portfolio_value, volatility等参数
            
        Returns:
            是否触发再平衡
        """
        # 信号变化触发
        if self.cfg.signal_change_threshold is not None:
            signal = kwargs.get('signal')
            if signal is not None and self._last_signal is not None:
                # 计算信号变化
                signal_change = self._calculate_signal_change(signal, self._last_signal)
                if signal_change >= self.cfg.signal_change_threshold:
                    logger.info(f"信号变化触发再平衡: {signal_change:.2%}")
                    self._update_state(date, signal, kwargs.get('portfolio_value'), kwargs.get('volatility'))
                    return True
        
        # 回撤触发
        if self.cfg.drawdown_trigger is not None:
            portfolio_value = kwargs.get('portfolio_value')
            if portfolio_value is not None and self._last_portfolio_value is not None:
                # 计算回撤
                drawdown = (self._last_portfolio_value - portfolio_value) / self._last_portfolio_value
                if drawdown >= self.cfg.drawdown_trigger:
                    logger.info(f"回撤触发再平衡: {drawdown:.2%}")
                    self._update_state(date, kwargs.get('signal'), portfolio_value, kwargs.get('volatility'))
                    return True
        
        # 波动率触发
        if self.cfg.volatility_trigger is not None:
            volatility = kwargs.get('volatility')
            if volatility is not None and volatility >= self.cfg.volatility_trigger:
                logger.info(f"波动率触发再平衡: {volatility:.2%}")
                self._update_state(date, kwargs.get('signal'), kwargs.get('portfolio_value'), volatility)
                return True
        
        # 更新状态
        self._update_state(date, kwargs.get('signal'), kwargs.get('portfolio_value'), kwargs.get('volatility'))
        return False
    
    def _calculate_signal_change(self, current_signal: pd.Series, 
                                 last_signal: pd.Series) -> float:
        """计算信号变化幅度
        
        Args:
            current_signal: 当前信号
            last_signal: 上次信号
            
        Returns:
            信号变化幅度
        """
        # 计算持仓权重变化
        common_stocks = current_signal.index.intersection(last_signal.index)
        if len(common_stocks) == 0:
            return 1.0
        
        current_weights = current_signal.loc[common_stocks]
        last_weights = last_signal.loc[common_stocks]
        
        # 计算权重变化的L2范数
        weight_change = np.linalg.norm(current_weights.values - last_weights.values)
        
        return weight_change
    
    def _update_state(self, date: pd.Timestamp, signal: Optional[pd.Series],
                     portfolio_value: Optional[float], volatility: Optional[float]):
        """更新状态
        
        Args:
            date: 日期
            signal: 信号
            portfolio_value: 组合价值
            volatility: 波动率
        """
        self._last_rebalance_date = date
        if signal is not None:
            self._last_signal = signal.copy()
        if portfolio_value is not None:
            self._last_portfolio_value = portfolio_value
        if volatility is not None:
            self._last_volatility = volatility


class HybridTrigger(BaseTrigger):
    """混合触发器"""
    
    def __init__(self, config: RebalanceConfig, trade_dates: pd.DatetimeIndex):
        """初始化混合触发器
        
        Args:
            config: 再平衡配置
            trade_dates: 交易日期索引
        """
        super().__init__(config)
        self._fixed_trigger = FixedIntervalTrigger(config, trade_dates)
        self._conditional_trigger = ConditionalTrigger(config)
        self._last_rebalance_date: Optional[pd.Timestamp] = None
    
    def should_trigger(self, date: pd.Timestamp, **kwargs) -> bool:
        """判断是否触发再平衡
        
        Args:
            date: 当前日期
            **kwargs: 其他参数
            
        Returns:
            是否触发再平衡
        """
        # 检查是否满足最小间隔
        if self._last_rebalance_date is not None:
            days_since_last = (date - self._last_rebalance_date).days
            if days_since_last < self.cfg.hybrid_min_days:
                return False
        
        # 固定间隔触发
        if self._fixed_trigger.should_trigger(date):
            self._last_rebalance_date = date
            return True
        
        # 条件触发
        if self._conditional_trigger.should_trigger(date, **kwargs):
            self._last_rebalance_date = date
            return True
        
        # 检查是否超过最大间隔
        if self._last_rebalance_date is not None:
            days_since_last = (date - self._last_rebalance_date).days
            if days_since_last >= self.cfg.hybrid_max_days:
                logger.info(f"超过最大间隔触发再平衡: {days_since_last}天")
                self._last_rebalance_date = date
                return True
        
        return False


def build_trigger(config: RebalanceConfig, trade_dates: pd.DatetimeIndex) -> BaseTrigger:
    """构建再平衡触发器
    
    Args:
        config: 再平衡配置
        trade_dates: 交易日期索引
        
    Returns:
        再平衡触发器实例
    """
    if config.method == "fixed":
        return FixedIntervalTrigger(config, trade_dates)
    elif config.method == "conditional":
        return ConditionalTrigger(config)
    elif config.method == "hybrid":
        return HybridTrigger(config, trade_dates)
    else:
        logger.warning(f"未知的触发方法: {config.method}，使用固定间隔触发")
        return FixedIntervalTrigger(config, trade_dates)


class RebalanceCalendar:
    """再平衡日历
    
    预计算所有再平衡日期，提供查询功能。
    """
    
    def __init__(self, trigger: BaseTrigger, trade_dates: pd.DatetimeIndex):
        """初始化再平衡日历
        
        Args:
            trigger: 再平衡触发器
            trade_dates: 交易日期索引
        """
        self.trigger = trigger
        self.trade_dates = trade_dates
        self._rebalance_dates = self._calculate_all_rebalance_dates()
        logger.info(f"再平衡日历计算完成，共{len(self._rebalance_dates)}个再平衡日")
    
    def _calculate_all_rebalance_dates(self) -> list[pd.Timestamp]:
        """计算所有再平衡日期
        
        Returns:
            再平衡日期列表
        """
        rebalance_dates = []
        
        # 模拟触发过程
        for date in self.trade_dates:
            if self.trigger.should_trigger(date):
                rebalance_dates.append(date)
        
        return rebalance_dates
    
    def is_rebalance_date(self, date: pd.Timestamp) -> bool:
        """判断是否为再平衡日期
        
        Args:
            date: 日期
            
        Returns:
            是否为再平衡日期
        """
        return date in self._rebalance_dates
    
    def get_rebalance_dates(self) -> list[pd.Timestamp]:
        """获取所有再平衡日期
        
        Returns:
            再平衡日期列表
        """
        return self._rebalance_dates.copy()
    
    def get_next_rebalance_date(self, current_date: pd.Timestamp) -> Optional[pd.Timestamp]:
        """获取下一个再平衡日期
        
        Args:
            current_date: 当前日期
            
        Returns:
            下一个再平衡日期
        """
        for date in self._rebalance_dates:
            if date > current_date:
                return date
        return None
    
    def get_rebalance_stats(self) -> dict[str, Any]:
        """获取再平衡统计信息
        
        Returns:
            再平衡统计信息
        """
        if not self._rebalance_dates:
            return {
                'total_rebalances': 0,
                'rebalance_frequency': 0,
                'avg_interval_days': 0
            }
        
        # 计算再平衡间隔
        intervals = []
        for i in range(1, len(self._rebalance_dates)):
            interval = (self._rebalance_dates[i] - self._rebalance_dates[i-1]).days
            intervals.append(interval)
        
        # 计算频率（每年再平衡次数）
        total_days = (self._rebalance_dates[-1] - self._rebalance_dates[0]).days
        rebalance_frequency = len(self._rebalance_dates) * 365.25 / total_days if total_days > 0 else 0
        
        return {
            'total_rebalances': len(self._rebalance_dates),
            'rebalance_frequency': rebalance_frequency,
            'avg_interval_days': np.mean(intervals) if intervals else 0,
            'min_interval_days': np.min(intervals) if intervals else 0,
            'max_interval_days': np.max(intervals) if intervals else 0
        }
