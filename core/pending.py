"""待执行订单管理系统 - 基于Backtest_Opus_2.0架构

提供完整的待执行订单管理功能：
- 失败交易自动重试
- 买入失败时的备选替补
- 订单过期机制
- 详细的事件日志记录
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import BacktestConfig

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = auto()     # 待执行
    EXECUTED = auto()    # 已执行
    EXPIRED = auto()     # 已过期
    CANCELLED = auto()   # 已取消


class OrderSide(Enum):
    """订单方向枚举"""
    BUY = auto()         # 买入
    SELL = auto()        # 卖出


class PendingOrder:
    """待执行订单类"""
    
    def __init__(self, stock: str, side: OrderSide, quantity: int,
                 create_date: pd.Timestamp, target_price: Optional[float] = None):
        """初始化待执行订单
        
        Args:
            stock: 股票代码
            side: 订单方向
            quantity: 数量
            create_date: 创建日期
            target_price: 目标价格（可选）
        """
        self.stock = stock
        self.side = side
        self.quantity = quantity
        self.create_date = create_date
        self.target_price = target_price
        self.status = OrderStatus.PENDING
        self.execute_date: Optional[pd.Timestamp] = None
        self.execute_price: Optional[float] = None
        self.retry_count = 0
        self.fallback_stock: Optional[str] = None  # 备选替补股票
        
    def mark_executed(self, execute_date: pd.Timestamp, execute_price: float):
        """标记订单已执行
        
        Args:
            execute_date: 执行日期
            execute_price: 执行价格
        """
        self.status = OrderStatus.EXECUTED
        self.execute_date = execute_date
        self.execute_price = execute_price
        
    def mark_expired(self, expire_date: pd.Timestamp):
        """标记订单已过期
        
        Args:
            expire_date: 过期日期
        """
        self.status = OrderStatus.EXPIRED
        self.execute_date = expire_date
        
    def mark_cancelled(self, cancel_date: pd.Timestamp):
        """标记订单已取消
        
        Args:
            cancel_date: 取消日期
        """
        self.status = OrderStatus.CANCELLED
        self.execute_date = cancel_date
        
    def is_expired(self, current_date: pd.Timestamp, max_pending_days: int, half_life: int = 3) -> bool:
        """检查订单是否过期（半衰期机制）
        
        Args:
            current_date: 当前日期
            max_pending_days: 最大待执行天数
            half_life: 半衰期天数（默认3天）
            
        Returns:
            是否过期
        """
        days_pending = (current_date - self.create_date).days
        
        # 【修复B1】半衰期机制：订单优先级随时间递减
        # 超过max_pending_days直接过期
        if days_pending >= max_pending_days:
            return True
        
        # 半衰期检查：订单"活力"随时间指数衰减
        # 活力 = 0.5^(days_pending/half_life)
        # 当活力 < 0.125 (约3个半衰期) 时，订单过期
        vitality = 0.5 ** (days_pending / half_life) if half_life > 0 else 0
        if vitality < 0.125:
            return True
        
        return False
    
    def get_priority(self, current_date: pd.Timestamp, half_life: int = 3) -> float:
        """获取订单优先级（半衰期衰减）
        
        Args:
            current_date: 当前日期
            half_life: 半衰期天数
            
        Returns:
            优先级分数（0-1，越高越优先）
        """
        days_pending = (current_date - self.create_date).days
        vitality = 0.5 ** (days_pending / half_life) if half_life > 0 else 0
        return vitality
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式
        
        Returns:
            订单信息字典
        """
        return {
            'stock': self.stock,
            'side': self.side.name,
            'quantity': self.quantity,
            'create_date': self.create_date,
            'target_price': self.target_price,
            'status': self.status.name,
            'execute_date': self.execute_date,
            'execute_price': self.execute_price,
            'retry_count': self.retry_count,
            'fallback_stock': self.fallback_stock
        }


class PendingOrderQueue:
    """待执行订单队列
    
    管理所有待执行订单，支持按日期查询和状态管理。
    """
    
    def __init__(self, max_pending_days_buy: int = 5, max_pending_days_sell: int = 10):
        """初始化待执行订单队列
        
        Args:
            max_pending_days_buy: 买入订单最大待执行天数
            max_pending_days_sell: 卖出订单最大待执行天数
        """
        self.max_pending_days_buy = max_pending_days_buy
        self.max_pending_days_sell = max_pending_days_sell
        
        # 订单存储
        self._orders: list[PendingOrder] = []
        self._order_index: dict[str, list[int]] = {}  # {stock: [order_indices]}
        
        # 事件日志
        self._event_log: list[dict[str, Any]] = []
        
        logger.info("待执行订单队列初始化完成")
    
    def add_order(self, order: PendingOrder):
        """添加待执行订单
        
        Args:
            order: 待执行订单
        """
        self._orders.append(order)
        order_index = len(self._orders) - 1
        
        # 更新股票索引
        if order.stock not in self._order_index:
            self._order_index[order.stock] = []
        self._order_index[order.stock].append(order_index)
        
        # 记录事件
        self._log_event(order.create_date, 'ORDER_ADDED', order.stock, 
                       f"{order.side.name} {order.quantity}股")
        
        logger.debug(f"添加待执行订单: {order.stock} {order.side.name} {order.quantity}")
    
    def get_pending_orders(self, stock: Optional[str] = None, 
                          side: Optional[OrderSide] = None) -> list[PendingOrder]:
        """获取待执行订单
        
        Args:
            stock: 股票代码（可选）
            side: 订单方向（可选）
            
        Returns:
            待执行订单列表
        """
        pending_orders = []
        
        for order in self._orders:
            if order.status != OrderStatus.PENDING:
                continue
            
            if stock and order.stock != stock:
                continue
                
            if side and order.side != side:
                continue
                
            pending_orders.append(order)
        
        return pending_orders
    
    def get_orders_by_date(self, date: pd.Timestamp) -> list[PendingOrder]:
        """获取指定日期的订单
        
        Args:
            date: 日期
            
        Returns:
            订单列表
        """
        return [order for order in self._orders if order.create_date == date]
    
    def mark_executed(self, order: PendingOrder, execute_date: pd.Timestamp, 
                     execute_price: float):
        """标记订单已执行
        
        Args:
            order: 订单
            execute_date: 执行日期
            execute_price: 执行价格
        """
        order.mark_executed(execute_date, execute_price)
        order.retry_count += 1
        
        # 记录事件
        self._log_event(execute_date, 'ORDER_EXECUTED', order.stock,
                       f"{order.side.name} {order.quantity}股 @ {execute_price:.2f}")
        
        logger.info(f"订单执行成功: {order.stock} {order.side.name} {order.quantity}股 @ {execute_price:.2f}")
    
    def mark_expired(self, current_date: pd.Timestamp):
        """标记过期订单
        
        Args:
            current_date: 当前日期
        """
        expired_orders = []
        
        for order in self._orders:
            if order.status != OrderStatus.PENDING:
                continue
            
            max_days = (self.max_pending_days_buy if order.side == OrderSide.BUY 
                       else self.max_pending_days_sell)
            
            if order.is_expired(current_date, max_days):
                order.mark_expired(current_date)
                expired_orders.append(order)
                
                # 记录事件
                self._log_event(current_date, 'ORDER_EXPIRED', order.stock,
                               f"{order.side.name} {order.quantity}股")
        
        if expired_orders:
            logger.info(f"标记{len(expired_orders)}个订单为过期")
    
    def cancel_orders(self, stock: str, cancel_date: pd.Timestamp):
        """取消指定股票的所有待执行订单
        
        Args:
            stock: 股票代码
            cancel_date: 取消日期
        """
        if stock not in self._order_index:
            return
        
        cancelled_orders = []
        
        for order_index in self._order_index[stock]:
            order = self._orders[order_index]
            if order.status == OrderStatus.PENDING:
                order.mark_cancelled(cancel_date)
                cancelled_orders.append(order)
                
                # 记录事件
                self._log_event(cancel_date, 'ORDER_CANCELLED', order.stock,
                               f"{order.side.name} {order.quantity}股")
        
        if cancelled_orders:
            logger.info(f"取消{stock}的{len(cancelled_orders)}个待执行订单")
    
    def get_order_stats(self) -> dict[str, Any]:
        """获取订单统计信息
        
        Returns:
            订单统计信息
        """
        stats = {
            'total_orders': len(self._orders),
            'pending_orders': len([o for o in self._orders if o.status == OrderStatus.PENDING]),
            'executed_orders': len([o for o in self._orders if o.status == OrderStatus.EXECUTED]),
            'expired_orders': len([o for o in self._orders if o.status == OrderStatus.EXPIRED]),
            'cancelled_orders': len([o for o in self._orders if o.status == OrderStatus.CANCELLED]),
        }
        
        # 按方向统计
        stats['buy_orders'] = len([o for o in self._orders if o.side == OrderSide.BUY])
        stats['sell_orders'] = len([o for o in self._orders if o.side == OrderSide.SELL])
        
        # 平均重试次数
        executed_orders = [o for o in self._orders if o.status == OrderStatus.EXECUTED]
        if executed_orders:
            stats['avg_retry_count'] = np.mean([o.retry_count for o in executed_orders])
        else:
            stats['avg_retry_count'] = 0
        
        return stats
    
    def get_event_log(self) -> pd.DataFrame:
        """获取事件日志
        
        Returns:
            事件日志DataFrame
        """
        if not self._event_log:
            return pd.DataFrame(columns=['date', 'event_type', 'stock', 'description'])
        
        return pd.DataFrame(self._event_log)
    
    def _log_event(self, date: pd.Timestamp, event_type: str, stock: str, description: str):
        """记录事件日志
        
        Args:
            date: 事件日期
            event_type: 事件类型
            stock: 股票代码
            description: 事件描述
        """
        event = {
            'date': date,
            'event_type': event_type,
            'stock': stock,
            'description': description
        }
        self._event_log.append(event)
    
    def clear_executed_orders(self):
        """清理已执行的订单"""
        original_count = len(self._orders)
        self._orders = [o for o in self._orders if o.status != OrderStatus.EXECUTED]
        
        # 重建索引
        self._rebuild_index()
        
        cleared_count = original_count - len(self._orders)
        if cleared_count > 0:
            logger.info(f"清理{cleared_count}个已执行订单")
    
    def _rebuild_index(self):
        """重建股票索引"""
        self._order_index.clear()
        
        for i, order in enumerate(self._orders):
            if order.stock not in self._order_index:
                self._order_index[order.stock] = []
            self._order_index[order.stock].append(i)


def select_fallback_stocks(factor_scores: pd.Series, excluded_stocks: list[str],
                          depth: int = 10) -> list[str]:
    """选择备选替补股票
    
    Args:
        factor_scores: 因子得分
        excluded_stocks: 已排除的股票列表
        depth: 搜索深度
        
    Returns:
        备选股票列表
    """
    # 过滤已排除的股票
    available_stocks = factor_scores.index.difference(excluded_stocks)
    
    if len(available_stocks) == 0:
        return []
    
    # 按因子得分排序
    available_scores = factor_scores.loc[available_stocks]
    
    # 选择得分最高的股票作为备选
    fallback_stocks = available_scores.nlargest(depth).index.tolist()
    
    return fallback_stocks


def create_pending_order(stock: str, side: OrderSide, quantity: int,
                        create_date: pd.Timestamp, 
                        target_price: Optional[float] = None) -> PendingOrder:
    """创建待执行订单
    
    Args:
        stock: 股票代码
        side: 订单方向
        quantity: 数量
        create_date: 创建日期
        target_price: 目标价格
        
    Returns:
        待执行订单
    """
    return PendingOrder(stock, side, quantity, create_date, target_price)
