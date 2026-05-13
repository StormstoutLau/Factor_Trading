"""交易执行模块 - 基于Backtest_Opus_2.0架构

提供完整的交易执行模拟功能：
- 支持多种执行价格类型（开盘价/VWAP/收盘价/自定义）
- 完整的交易成本计算
- 交易日志记录
- 失败交易处理
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from config import BacktestConfig, CostConfig, ExecutionPriceType
from pending import OrderSide, PendingOrder

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """交易记录类"""
    date: pd.Timestamp
    stock: str
    side: OrderSide
    quantity: int
    price: float
    amount: float
    cost: float
    net_amount: float
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            'date': self.date,
            'stock': self.stock,
            'side': self.side.name,
            'quantity': self.quantity,
            'price': self.price,
            'amount': self.amount,
            'cost': self.cost,
            'net_amount': self.net_amount
        }


class TradeLog:
    """交易日志管理器"""
    
    def __init__(self):
        """初始化交易日志"""
        self._trades: list[Trade] = []
        logger.info("交易日志初始化完成")
    
    def add_trade(self, trade: Trade):
        """添加交易记录
        
        Args:
            trade: 交易记录
        """
        self._trades.append(trade)
        logger.debug(f"记录交易: {trade.stock} {trade.side.name} {trade.quantity}股 @ {trade.price:.2f}")
    
    def get_trades(self) -> list[Trade]:
        """获取所有交易记录
        
        Returns:
            交易记录列表
        """
        return self._trades.copy()
    
    def get_trades_df(self) -> pd.DataFrame:
        """获取交易记录DataFrame
        
        Returns:
            交易记录DataFrame
        """
        if not self._trades:
            return pd.DataFrame(columns=['date', 'stock', 'side', 'quantity', 'price', 'amount', 'cost', 'net_amount'])
        
        return pd.DataFrame([trade.to_dict() for trade in self._trades])
    
    def get_trades_by_stock(self, stock: str) -> list[Trade]:
        """获取指定股票的交易记录
        
        Args:
            stock: 股票代码
            
        Returns:
            交易记录列表
        """
        return [trade for trade in self._trades if trade.stock == stock]
    
    def get_trades_by_date(self, date: pd.Timestamp) -> list[Trade]:
        """获取指定日期的交易记录
        
        Args:
            date: 日期
            
        Returns:
            交易记录列表
        """
        return [trade for trade in self._trades if trade.date == date]
    
    def get_trade_stats(self) -> dict[str, Any]:
        """获取交易统计信息
        
        Returns:
            交易统计信息
        """
        if not self._trades:
            return {
                'total_trades': 0,
                'total_amount': 0.0,
                'total_cost': 0.0,
                'buy_trades': 0,
                'sell_trades': 0
            }
        
        total_amount = sum(trade.amount for trade in self._trades)
        total_cost = sum(trade.cost for trade in self._trades)
        buy_trades = len([t for t in self._trades if t.side == OrderSide.BUY])
        sell_trades = len([t for t in self._trades if t.side == OrderSide.SELL])
        
        return {
            'total_trades': len(self._trades),
            'total_amount': total_amount,
            'total_cost': total_cost,
            'cost_rate': total_cost / total_amount if total_amount > 0 else 0,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades
        }


class ExecutionSimulator:
    """交易执行模拟器
    
    模拟真实的交易执行过程，支持多种执行价格类型。
    """
    
    def __init__(self, cost_config: CostConfig, 
                 execution_price_type: ExecutionPriceType = ExecutionPriceType.OPEN,
                 custom_price_callback: Optional[Callable] = None):
        """初始化交易执行模拟器
        
        Args:
            cost_config: 交易成本配置
            execution_price_type: 执行价格类型
            custom_price_callback: 自定义价格回调函数 (date, stock, side) -> float
        """
        self.cost_cfg = cost_config
        self.execution_price_type = execution_price_type
        self.custom_price_callback = custom_price_callback
        self.trade_log = TradeLog()
        
        logger.info(f"交易执行模拟器初始化完成，执行价格类型: {execution_price_type.value}")
    
    def _get_execution_price(self, date: pd.Timestamp, stock: str, side: OrderSide,
                            open_price: float, close_price: Optional[float] = None,
                            high_price: Optional[float] = None, 
                            low_price: Optional[float] = None,
                            volume: Optional[float] = None) -> float:
        """
        根据执行价格类型获取执行价格
        
        Args:
            date: 交易日期
            stock: 股票代码
            side: 订单方向
            open_price: 开盘价
            close_price: 收盘价
            high_price: 最高价
            low_price: 最低价
            volume: 成交量
            
        Returns:
            执行价格
        """
        if self.execution_price_type == ExecutionPriceType.OPEN:
            return open_price
        
        elif self.execution_price_type == ExecutionPriceType.CLOSE:
            if close_price is None:
                logger.warning(f"{stock}在{date}收盘价不可用，回退到开盘价")
                return open_price
            return close_price
        
        elif self.execution_price_type == ExecutionPriceType.VWAP:
            # 简化VWAP：使用开盘、收盘、最高、最低价的平均值
            # 实际应用中应该使用逐笔数据的VWAP
            prices = [open_price]
            if close_price is not None:
                prices.append(close_price)
            if high_price is not None:
                prices.append(high_price)
            if low_price is not None:
                prices.append(low_price)
            
            vwap = sum(prices) / len(prices)
            logger.debug(f"{stock}在{date} VWAP: {vwap:.2f} (基于{len(prices)}个价格)")
            return vwap
        
        elif self.execution_price_type == ExecutionPriceType.CUSTOM:
            if self.custom_price_callback is not None:
                try:
                    custom_price = self.custom_price_callback(date, stock, side)
                    if custom_price is not None and custom_price > 0:
                        return custom_price
                    else:
                        logger.warning(f"自定义价格无效，回退到开盘价")
                        return open_price
                except Exception as e:
                    logger.error(f"自定义价格回调失败: {e}，回退到开盘价")
                    return open_price
            else:
                logger.warning("未设置自定义价格回调，回退到开盘价")
                return open_price
        
        else:
            logger.warning(f"未知的执行价格类型: {self.execution_price_type}，回退到开盘价")
            return open_price
    
    def execute_order(self, stock: str, side: OrderSide, quantity: int,
                     date: pd.Timestamp, open_price: float, 
                     close_price: Optional[float] = None,
                     high_price: Optional[float] = None,
                     low_price: Optional[float] = None,
                     volume: Optional[float] = None) -> tuple[bool, Optional[Trade]]:
        """执行订单
        
        Args:
            stock: 股票代码
            side: 订单方向
            quantity: 数量
            date: 交易日期
            open_price: 开盘价
            close_price: 收盘价（可选）
            high_price: 最高价（可选，用于VWAP）
            low_price: 最低价（可选，用于VWAP）
            volume: 成交量（可选，用于VWAP）
            
        Returns:
            (是否成功, 交易记录)
        """
        try:
            # 根据执行价格类型确定执行价格
            execution_price = self._get_execution_price(
                date, stock, side, open_price, close_price, 
                high_price, low_price, volume
            )
            
            # 价格合理性检查
            if close_price is not None:
                price_diff_ratio = abs(execution_price - close_price) / close_price
                if price_diff_ratio > 0.1:  # 10%阈值
                    logger.warning(
                        f"{stock}在{date}执行价格与收盘价差异过大: "
                        f"执行价={execution_price:.2f}, 收盘价={close_price:.2f}, "
                        f"差异={price_diff_ratio:.2%}"
                    )
            
            # 计算交易金额
            amount = quantity * execution_price
            
            # 计算交易成本
            cost = self._calculate_cost(amount, side)
            
            # 【修复E16】净金额统一为扣除成本后的实际收支
            # 买入：支付金额 + 成本（总支出）
            # 卖出：收到金额 - 成本（净收入）
            net_amount = amount + cost if side == OrderSide.BUY else amount - cost
            
            # 创建交易记录
            trade = Trade(
                date=date,
                stock=stock,
                side=side,
                quantity=quantity,
                price=execution_price,
                amount=amount,
                cost=cost,
                net_amount=net_amount
            )
            
            # 记录交易
            self.trade_log.add_trade(trade)
            
            logger.info(
                f"交易执行成功: {stock} {side.name} {quantity}股 "
                f"@ {execution_price:.2f} ({self.execution_price_type.value}), 成本: {cost:.2f}"
            )
            
            return True, trade
            
        except Exception as e:
            logger.error(f"交易执行失败: {stock} {side.name} {quantity}股, 错误: {e}")
            return False, None
    
    def _calculate_cost(self, amount: float, side: OrderSide) -> float:
        """计算交易成本
        
        Args:
            amount: 交易金额
            side: 订单方向
            
        Returns:
            交易成本
        """
        cost = 0.0
        
        # 佣金
        commission = amount * self.cost_cfg.commission_rate
        commission = max(commission, self.cost_cfg.commission_min)
        cost += commission
        
        # 印花税（卖出单边）
        if side == OrderSide.SELL:
            stamp_tax = amount * self.cost_cfg.stamp_tax_rate
            cost += stamp_tax
        
        # 滑点
        slippage = amount * self.cost_cfg.slippage_pct
        cost += slippage
        
        return cost
    
    def execute_pending_order(self, order: PendingOrder, date: pd.Timestamp,
                            open_price: float, close_price: Optional[float] = None) -> tuple[bool, Optional[Trade]]:
        """执行待执行订单
        
        Args:
            order: 待执行订单
            date: 交易日期
            open_price: 开盘价
            close_price: 收盘价（可选）
            
        Returns:
            (是否成功, 交易记录)
        """
        return self.execute_order(
            stock=order.stock,
            side=order.side,
            quantity=order.quantity,
            date=date,
            open_price=open_price,
            close_price=close_price
        )
    
    def calculate_liquidation_value(self, stock: str, quantity: int, 
                                   date: pd.Timestamp, close_price: float) -> float:
        """计算清算价值
        
        Args:
            stock: 股票代码
            quantity: 数量
            date: 日期
            close_price: 收盘价
            
        Returns:
            清算价值（扣除成本）
        """
        # 计算交易金额
        amount = quantity * close_price
        
        # 计算卖出成本
        cost = self._calculate_cost(amount, OrderSide.SELL)
        
        # 【修复E10】卖出清算应扣除成本，而非加上
        net_amount = amount - cost
        
        return net_amount
    
    def get_execution_stats(self) -> dict[str, Any]:
        """获取执行统计信息
        
        Returns:
            执行统计信息
        """
        trade_stats = self.trade_log.get_trade_stats()
        
        # 添加成本配置信息
        trade_stats.update({
            'commission_rate': self.cost_cfg.commission_rate,
            'commission_min': self.cost_cfg.commission_min,
            'stamp_tax_rate': self.cost_cfg.stamp_tax_rate,
            'slippage_pct': self.cost_cfg.slippage_pct
        })
        
        return trade_stats
    
    def validate_execution_price(self, stock: str, date: pd.Timestamp,
                                execution_price: float, 
                                reference_price: float) -> bool:
        """验证执行价格的合理性
        
        Args:
            stock: 股票代码
            date: 日期
            execution_price: 执行价格
            reference_price: 参考价格（如收盘价）
            
        Returns:
            价格是否合理
        """
        if reference_price <= 0:
            return False
        
        # 计算价格偏差
        price_deviation = abs(execution_price - reference_price) / reference_price
        
        # 价格偏差不应超过20%
        if price_deviation > 0.2:
            logger.warning(f"{stock}在{date}执行价格偏差过大: {price_deviation:.2%}")
            return False
        
        return True
    
    def simulate_market_impact(self, stock: str, quantity: int, 
                             avg_daily_volume: float, price: float) -> float:
        """模拟市场冲击成本
        
        Args:
            stock: 股票代码
            quantity: 交易数量
            avg_daily_volume: 平均日成交量
            price: 当前价格
            
        Returns:
            市场冲击成本（比例）
        """
        if avg_daily_volume <= 0:
            return 0.0
        
        # 计算交易量占比
        volume_ratio = quantity / avg_daily_volume
        
        # 简单的线性市场冲击模型
        # 交易量占比越大，冲击成本越高
        impact_cost = min(volume_ratio * 0.01, 0.05)  # 最大5%的冲击成本
        
        return impact_cost
