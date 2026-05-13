"""持仓跟踪模块 - 基于Backtest_Opus_2.0架构

提供完整的持仓跟踪功能：
- 实时持仓数量跟踪
- 组合总价值计算
- 每日收益计算
- 持仓快照记录
- 风险暴露监控
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from execution import Trade

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """持仓信息类"""
    stock: str
    quantity: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    
    def update_market_value(self, current_price: float):
        """更新市值和未实现盈亏
        
        Args:
            current_price: 当前价格
        """
        self.market_value = self.quantity * current_price
        self.unrealized_pnl = self.market_value - self.quantity * self.avg_cost
    
    def execute_trade(self, trade: Trade):
        """执行交易，更新持仓
        
        Args:
            trade: 交易记录
        """
        if trade.side.name == 'BUY':
            # 买入：更新平均成本
            total_cost = self.quantity * self.avg_cost + trade.amount
            total_quantity = self.quantity + trade.quantity
            self.avg_cost = total_cost / total_quantity if total_quantity > 0 else 0
            self.quantity = total_quantity
            
        elif trade.side.name == 'SELL':
            # 卖出：计算已实现盈亏
            if self.quantity > 0:
                sell_proceeds = trade.quantity * self.avg_cost
                realized_pnl = trade.amount - sell_proceeds - trade.cost
                self.realized_pnl += realized_pnl
                self.quantity -= trade.quantity
                
                # 如果全部卖出，重置平均成本和市值
                if self.quantity == 0:
                    self.avg_cost = 0
                    self.market_value = 0.0  # 【修复】清空市值
                    self.unrealized_pnl = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            'stock': self.stock,
            'quantity': self.quantity,
            'avg_cost': self.avg_cost,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': self.unrealized_pnl + self.realized_pnl
        }


@dataclass
class PortfolioSnapshot:
    """组合快照类"""
    date: pd.Timestamp
    cash: float
    total_value: float
    positions: dict[str, Position]
    daily_return: float
    cumulative_return: float
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            'date': self.date,
            'cash': self.cash,
            'total_value': self.total_value,
            'position_count': len([p for p in self.positions.values() if p.quantity > 0]),
            'daily_return': self.daily_return,
            'cumulative_return': self.cumulative_return,
            'positions': {stock: pos.to_dict() for stock, pos in self.positions.items() if pos.quantity > 0}
        }


class PositionTracker:
    """持仓跟踪器
    
    负责跟踪持仓变化、计算组合价值和收益。
    """
    
    def __init__(self, n_stocks: int, initial_capital: float):
        """初始化持仓跟踪器
        
        Args:
            n_stocks: 股票总数
            initial_capital: 初始资金
        """
        self.n_stocks = n_stocks
        self.initial_capital = initial_capital
        
        # 当前持仓
        self._positions: dict[str, Position] = {}
        
        # 现金
        self._cash = initial_capital
        
        # 组合快照历史
        self._snapshots: list[PortfolioSnapshot] = []
        
        # 前一日总价值（用于计算日收益）
        self._prev_total_value = initial_capital
        
        # 累计收益
        self._cumulative_return = 0.0
        
        logger.info("持仓跟踪器初始化完成")
    
    def execute_trade(self, trade: Trade):
        """执行交易，更新持仓
        
        Args:
            trade: 交易记录
        """
        stock = trade.stock
        
        # 更新现金
        if trade.side.name == 'BUY':
            self._cash -= trade.net_amount
        elif trade.side.name == 'SELL':
            self._cash += trade.net_amount
        
        # 更新持仓
        if stock not in self._positions:
            self._positions[stock] = Position(
                stock=stock,
                quantity=0,
                avg_cost=0.0,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0
            )
        
        self._positions[stock].execute_trade(trade)
        
        logger.debug(f"执行交易: {trade.stock} {trade.side.name} {trade.quantity}股, 现金: {self._cash:.2f}")
    
    def update_market_values(self, date: pd.Timestamp, prices: pd.Series):
        """更新持仓市值
        
        Args:
            date: 日期
            prices: 价格数据
        """
        for stock, position in self._positions.items():
            if position.quantity > 0 and stock in prices:
                price = prices[stock]
                # 【修复】跳过NaN或无效价格，保持上次市值不变
                if pd.notna(price) and price > 0:
                    position.update_market_value(price)
                # 如果价格无效，保持原有市值（不进行更新）
        
        # 记录组合快照
        self._take_snapshot(date)
    
    def _take_snapshot(self, date: pd.Timestamp):
        """记录组合快照
        
        Args:
            date: 日期
        """
        total_value = self.get_total_value()
        
        # 计算日收益
        daily_return = (total_value - self._prev_total_value) / self._prev_total_value
        
        # 计算累计收益
        self._cumulative_return = (total_value - self.initial_capital) / self.initial_capital
        
        # 创建快照
        snapshot = PortfolioSnapshot(
            date=date,
            cash=self._cash,
            total_value=total_value,
            positions=self._positions.copy(),
            daily_return=daily_return,
            cumulative_return=self._cumulative_return
        )
        
        self._snapshots.append(snapshot)
        self._prev_total_value = total_value
        
        logger.debug(f"记录组合快照: {date}, 总价值: {total_value:.2f}, 日收益: {daily_return:.2%}")
    
    def get_position(self, stock: str) -> Optional[Position]:
        """获取指定股票的持仓
        
        Args:
            stock: 股票代码
            
        Returns:
            持仓信息
        """
        return self._positions.get(stock)
    
    def get_all_positions(self) -> dict[str, Position]:
        """获取所有持仓
        
        Returns:
            所有持仓信息
        """
        return {stock: pos for stock, pos in self._positions.items() if pos.quantity > 0}
    
    def get_total_value(self) -> float:
        """获取组合总价值
        
        Returns:
            现金 + 持仓市值
        """
        position_value = sum(pos.market_value for pos in self._positions.values())
        return self._cash + position_value
    
    def get_cash(self) -> float:
        """获取现金余额
        
        Returns:
            现金余额
        """
        return self._cash
    
    def get_position_weights(self, prices: pd.Series) -> pd.Series:
        """获取持仓权重
        
        Args:
            prices: 价格数据
            
        Returns:
            持仓权重序列
        """
        total_value = self.get_total_value()
        if total_value <= 0:
            return pd.Series()
        
        weights = {}
        for stock, position in self._positions.items():
            if position.quantity > 0:
                weights[stock] = position.market_value / total_value
        
        return pd.Series(weights)
    
    def get_sector_exposure(self, industry_data: pd.Series) -> dict[str, float]:
        """获取行业暴露
        
        Args:
            industry_data: 行业数据
            
        Returns:
            行业暴露字典
        """
        sector_exposure = {}
        total_value = self.get_total_value()
        
        if total_value <= 0:
            return sector_exposure
        
        for stock, position in self._positions.items():
            if position.quantity > 0 and stock in industry_data:
                sector = industry_data[stock]
                if sector not in sector_exposure:
                    sector_exposure[sector] = 0.0
                sector_exposure[sector] += position.market_value / total_value
        
        return sector_exposure
    
    def get_snapshots(self) -> list[PortfolioSnapshot]:
        """获取所有组合快照
        
        Returns:
            组合快照列表
        """
        return self._snapshots.copy()
    
    def get_snapshots_df(self) -> pd.DataFrame:
        """获取组合快照DataFrame
        
        Returns:
            组合快照DataFrame
        """
        if not self._snapshots:
            return pd.DataFrame(columns=['date', 'cash', 'total_value', 'position_count', 
                                       'daily_return', 'cumulative_return'])
        
        data = []
        for snapshot in self._snapshots:
            data.append({
                'date': snapshot.date,
                'cash': snapshot.cash,
                'total_value': snapshot.total_value,
                'position_count': len([p for p in snapshot.positions.values() if p.quantity > 0]),
                'daily_return': snapshot.daily_return,
                'cumulative_return': snapshot.cumulative_return
            })
        
        return pd.DataFrame(data)
    
    def get_performance_metrics(self) -> dict[str, Any]:
        """获取性能指标
        
        Returns:
            性能指标字典
        """
        if not self._snapshots:
            return {}
        
        # 提取收益率序列
        daily_returns = [s.daily_return for s in self._snapshots if not pd.isna(s.daily_return)]
        cumulative_returns = [s.cumulative_return for s in self._snapshots]
        
        if not daily_returns:
            return {}
        
        # 计算性能指标
        total_return = cumulative_returns[-1] if cumulative_returns else 0
        
        # 年化收益率（假设252个交易日）
        n_days = len(daily_returns)
        annual_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0
        
        # 年化波动率
        annual_volatility = np.std(daily_returns) * np.sqrt(252) if daily_returns else 0
        
        # 夏普比率（假设无风险利率为0）
        sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0
        
        # 最大回撤
        cumulative_values = [1 + r for r in cumulative_returns]
        peak = np.maximum.accumulate(cumulative_values)
        drawdown = (peak - cumulative_values) / peak
        max_drawdown = np.max(drawdown) if drawdown.size > 0 else 0
        
        # 当前持仓统计
        current_positions = self.get_all_positions()
        position_count = len(current_positions)
        
        # 总盈亏
        total_pnl = sum(pos.unrealized_pnl + pos.realized_pnl for pos in current_positions.values())
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'current_value': self.get_total_value(),
            'current_cash': self._cash,
            'position_count': position_count,
            'total_pnl': total_pnl,
            'trading_days': n_days
        }
    
    def validate_positions(self, prices: pd.Series) -> list[str]:
        """验证持仓数据的一致性
        
        Args:
            prices: 价格数据
            
        Returns:
            验证错误列表
        """
        errors = []
        
        # 检查现金是否为负
        if self._cash < 0:
            errors.append(f"现金余额为负: {self._cash:.2f}")
        
        # 检查持仓数量是否合理
        for stock, position in self._positions.items():
            if position.quantity < 0:
                errors.append(f"{stock}持仓数量为负: {position.quantity}")
            
            if position.avg_cost <= 0 and position.quantity > 0:
                errors.append(f"{stock}平均成本异常: {position.avg_cost}")
            
            if stock in prices and position.quantity > 0:
                expected_market_value = position.quantity * prices[stock]
                if abs(position.market_value - expected_market_value) > 0.01:
                    errors.append(f"{stock}市值计算错误: {position.market_value} vs {expected_market_value}")
        
        return errors
    
    def reset(self, initial_capital: float):
        """重置持仓跟踪器
        
        Args:
            initial_capital: 初始资金
        """
        self._positions.clear()
        self._cash = initial_capital
        self._snapshots.clear()
        self._prev_total_value = initial_capital
        self._cumulative_return = 0.0
        
        logger.info("持仓跟踪器已重置")
