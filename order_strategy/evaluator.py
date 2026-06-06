"""
订单策略评估器

对比不同策略的执行成本和表现。
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from dataclasses import dataclass
import numpy as np

from order_strategy.strategies import (
    BaseOrderStrategy,
    MarketOrderStrategy,
    TWAPStrategy,
    VWAPStrategy,
    IcebergStrategy,
    Order,
    TradeExecution,
)

logger = logging.getLogger(__name__)


@dataclass
class StrategyEvaluationResult:
    """策略评估结果"""
    strategy_name: str
    total_qty: int
    avg_price: float
    total_amount: float
    total_impact: float
    impact_ratio: float
    trades: list[TradeExecution]


class OrderStrategyEvaluator:
    """订单策略评估器

    运行各种策略在相同市场条件下的表现。
    """

    def __init__(self, market_data: list[dict], benchmark_price: Optional[float] = None):
        self.market_data = market_data  # 每个时间步的市场数据
        self.benchmark_price = benchmark_price

    def evaluate_strategy(
        self,
        strategy: BaseOrderStrategy,
        symbol: str,
        side: str,
        qty: int,
    ) -> StrategyEvaluationResult:
        """评估单个策略

        Args:
            strategy: 策略实例
            symbol: 标的代码
            side: 方向
            qty: 总数量

        Returns:
            评估结果
        """
        all_trades = []
        total_qty = 0
        total_amount = 0.0
        total_impact = 0.0

        # 逐个时间步执行策略
        for step_idx, market_data in enumerate(self.market_data):
            trades = strategy.execute(
                symbol=symbol,
                side=side,
                qty=qty,
                timestamp=step_idx,
                market_data=market_data,
            )
            for trade in trades:
                all_trades.append(trade)
                total_qty += trade.qty
                total_amount += trade.amount
                total_impact += trade.impact

        # 计算平均价格和统计
        avg_price = total_amount / total_qty if total_qty > 0 else 0.0

        return StrategyEvaluationResult(
            strategy_name=strategy.__class__.__name__,
            total_qty=total_qty,
            avg_price=avg_price,
            total_amount=total_amount,
            total_impact=total_impact,
            impact_ratio=total_impact / total_amount if total_amount > 0 else 0.0,
            trades=all_trades,
        )

    def evaluate_all_strategies(
        self,
        symbol: str,
        side: str,
        qty: int,
    ) -> dict[str, StrategyEvaluationResult]:
        """评估所有策略并返回对比结果

        Args:
            symbol: 标的代码
            side: 方向
            qty: 总数量

        Returns:
            策略名到结果的映射
        """
        strategies = [
            MarketOrderStrategy(),
            TWAPStrategy({"intervals": 10}),
            VWAPStrategy({"volume_profile": np.array([0.08, 0.10, 0.12, 0.10, 0.08, 0.08, 0.10, 0.12, 0.10, 0.12])}),
            IcebergStrategy({"visible_size": 1000}),
        ]

        results = {}
        for strategy in strategies:
            result = self.evaluate_strategy(
                strategy=strategy,
                symbol=symbol,
                side=side,
                qty=qty,
            )
            results[result.strategy_name] = result
            logger.info(
                f"策略 {result.strategy_name} 平均价格: {result.avg_price:.2f}, "
                f"冲击比例: {result.impact_ratio:.4%}"
            )

        return results

