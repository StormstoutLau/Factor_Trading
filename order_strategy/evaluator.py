"""下单策略评估器

评估不同订单执行策略的绩效，支持多维度对比分析。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from order_strategy.strategies import BaseOrderStrategy, MarketImpactModel, SliceResult


@dataclass
class ExecutionRecord:
    """单次执行记录"""
    strategy_name: str
    symbol: str
    side: Literal["buy", "sell"]
    total_size: float
    benchmark_price: float
    avg_executed_price: float
    total_cost: float
    duration_min: float
    num_slices: int
    timestamp: pd.Timestamp

    @property
    def slippage_bps(self) -> float:
        """滑点（bps）"""
        if self.benchmark_price == 0:
            return 0.0
        sign = 1 if self.side == "buy" else -1
        return sign * (self.avg_executed_price - self.benchmark_price) / self.benchmark_price * 10000

    @property
    def market_impact_bps(self) -> float:
        """市场冲击（bps）"""
        return abs(self.slippage_bps)


@dataclass
class StrategyEvaluationMetrics:
    """策略评估指标"""
    strategy_name: str
    avg_slippage_bps: float = 0.0
    slippage_std: float = 0.0
    avg_duration_min: float = 0.0
    avg_slices: float = 0.0
    total_orders: int = 0
    win_rate: float = 0.0
    cost_score: float = 0.0
    speed_score: float = 0.0
    composite_score: float = 0.0
    records: list[ExecutionRecord] = field(default_factory=list)


class OrderStrategyEvaluator:
    """订单策略评估器

    支持多策略对比、冲击成本分析、最优策略推荐。
    """

    def __init__(self, impact_model: MarketImpactModel | None = None):
        self.impact_model = impact_model or MarketImpactModel()
        self.records: list[ExecutionRecord] = []
        self._strategies: dict[str, BaseOrderStrategy] = {}

    def register_strategy(self, strategy: BaseOrderStrategy) -> None:
        """注册策略"""
        self._strategies[strategy.name] = strategy

    def simulate_execution(
        self,
        strategy: BaseOrderStrategy,
        symbol: str,
        total_size: float,
        side: Literal["buy", "sell"],
        benchmark_price: float,
        daily_volume: float,
        volatility: float,
        start_time: pd.Timestamp,
        market_data: pd.DataFrame | None = None,
    ) -> ExecutionRecord:
        """模拟单次执行

        使用市场冲击模型估算实际成交均价，生成执行记录。
        """
        slice_result = strategy.split_order(
            symbol=symbol,
            total_size=total_size,
            side=side,
            start_time=start_time,
            market_data=market_data,
        )

        cost_info = self.impact_model.total_cost(
            order_size=total_size,
            daily_volume=daily_volume,
            volatility=volatility,
            participation_rate=total_size / daily_volume if daily_volume > 0 else 0.1,
        )

        total_impact_bps = cost_info["total_bps"]
        slippage_bps = slice_result.expected_slippage_bps
        total_cost_bps = total_impact_bps + slippage_bps

        sign = 1 if side == "buy" else -1
        avg_price = benchmark_price * (1 + sign * total_cost_bps / 10000)
        total_cost = total_size * abs(avg_price - benchmark_price)

        record = ExecutionRecord(
            strategy_name=strategy.name,
            symbol=symbol,
            side=side,
            total_size=total_size,
            benchmark_price=benchmark_price,
            avg_executed_price=avg_price,
            total_cost=total_cost,
            duration_min=slice_result.estimated_duration_min,
            num_slices=len(slice_result.slices),
            timestamp=start_time,
        )
        self.records.append(record)
        return record

    def evaluate_strategy(
        self,
        strategy_name: str,
        weight_slippage: float = 0.5,
        weight_speed: float = 0.3,
        weight_slices: float = 0.2,
    ) -> StrategyEvaluationMetrics:
        """评估单个策略"""
        records = [r for r in self.records if r.strategy_name == strategy_name]
        if not records:
            return StrategyEvaluationMetrics(strategy_name=strategy_name)

        slippages = [r.slippage_bps for r in records]
        durations = [r.duration_min for r in records]
        slices = [r.num_slices for r in records]

        avg_slippage = float(np.mean(slippages))
        slippage_std = float(np.std(slippages))
        avg_duration = float(np.mean(durations))
        avg_slices = float(np.mean(slices))

        win_rate = sum(1 for s in slippages if s <= 0) / len(slippages)

        cost_score = max(0, 100 - abs(avg_slippage))
        speed_score = max(0, 100 - avg_duration * 2)
        slice_score = max(0, 100 - avg_slices)
        composite = (
            weight_slippage * cost_score
            + weight_speed * speed_score
            + weight_slices * slice_score
        )

        return StrategyEvaluationMetrics(
            strategy_name=strategy_name,
            avg_slippage_bps=avg_slippage,
            slippage_std=slippage_std,
            avg_duration_min=avg_duration,
            avg_slices=avg_slices,
            total_orders=len(records),
            win_rate=win_rate,
            cost_score=cost_score,
            speed_score=speed_score,
            composite_score=composite,
            records=records,
        )

    def compare_strategies(
        self,
        strategy_names: list[str] | None = None,
    ) -> pd.DataFrame:
        """多策略对比"""
        if strategy_names is None:
            strategy_names = list(self._strategies.keys())
            if not strategy_names:
                strategy_names = list({r.strategy_name for r in self.records})

        results = []
        for name in strategy_names:
            metrics = self.evaluate_strategy(name)
            results.append({
                "策略": metrics.strategy_name,
                "平均滑点(bps)": round(metrics.avg_slippage_bps, 2),
                "滑点标准差": round(metrics.slippage_std, 2),
                "平均耗时(分)": round(metrics.avg_duration_min, 1),
                "平均切片数": round(metrics.avg_slices, 1),
                "订单数": metrics.total_orders,
                "胜率": round(metrics.win_rate, 2),
                "成本得分": round(metrics.cost_score, 1),
                "速度得分": round(metrics.speed_score, 1),
                "综合得分": round(metrics.composite_score, 1),
            })

        return pd.DataFrame(results)

    def recommend_strategy(
        self,
        urgency: Literal["high", "medium", "low"] = "medium",
        size_relative_to_adv: float = 0.05,
    ) -> str:
        """根据场景推荐策略

        Args:
            urgency: 紧急程度
            size_relative_to_adv: 订单量占日均成交量的比例

        Returns:
            推荐策略名称
        """
        if urgency == "high" or size_relative_to_adv < 0.01:
            return "MarketOrder"
        elif size_relative_to_adv > 0.3:
            return "Iceberg"
        elif urgency == "low":
            return "VWAP"
        else:
            return "TWAP"

    def get_summary(self) -> dict:
        """获取评估摘要"""
        if not self.records:
            return {"status": "no_data"}

        df = self.compare_strategies()
        best = df.loc[df["综合得分"].idxmax(), "策略"] if not df.empty else None

        return {
            "status": "ok",
            "total_records": len(self.records),
            "strategies_evaluated": df["策略"].tolist() if not df.empty else [],
            "best_strategy": best,
            "comparison_table": df.to_dict("records") if not df.empty else [],
        }

    def clear(self) -> None:
        """清空记录"""
        self.records.clear()
