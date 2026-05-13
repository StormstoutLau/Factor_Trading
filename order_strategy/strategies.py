"""下单策略实现

提供多种订单执行策略，包括市价单、TWAP、VWAP、冰山订单等。
所有策略均基于统一的 BaseOrderStrategy 接口，支持插拔式接入回测引擎。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Literal

import numpy as np
import pandas as pd


@dataclass
class OrderSlice:
    """订单切片"""
    timestamp: datetime
    size: float
    price: float | None = None
    is_market: bool = False


@dataclass
class SliceResult:
    """切片执行结果"""
    slices: list[OrderSlice]
    expected_impact_bps: float = 0.0
    expected_slippage_bps: float = 0.0
    estimated_duration_min: float = 0.0


class BaseOrderStrategy(ABC):
    """订单策略基类

    所有具体策略必须实现 split_order 方法，将总订单拆分为时间序列上的切片。
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def split_order(
        self,
        symbol: str,
        total_size: float,
        side: Literal["buy", "sell"],
        start_time: datetime,
        market_data: pd.DataFrame | None = None,
        **kwargs,
    ) -> SliceResult:
        """将订单拆分为执行切片

        Args:
            symbol: 标的代码
            total_size: 总订单数量（股数）
            side: 买卖方向
            start_time: 开始执行时间
            market_data: 市场数据（可选，用于自适应策略）
            **kwargs: 策略特定参数

        Returns:
            SliceResult: 拆分结果
        """
        ...

    def estimate_cost(
        self,
        symbol: str,
        total_size: float,
        side: Literal["buy", "sell"],
        market_data: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        """估算执行成本（默认实现，子类可覆盖）"""
        return {
            "impact_bps": 0.0,
            "slippage_bps": 0.0,
            "total_cost_bps": 0.0,
        }


class MarketOrderStrategy(BaseOrderStrategy):
    """市价单策略：立即以当前最优价全部成交"""

    def __init__(self):
        super().__init__("MarketOrder")

    def split_order(
        self,
        symbol: str,
        total_size: float,
        side: Literal["buy", "sell"],
        start_time: datetime,
        market_data: pd.DataFrame | None = None,
        **kwargs,
    ) -> SliceResult:
        return SliceResult(
            slices=[OrderSlice(timestamp=start_time, size=total_size, is_market=True)],
            expected_impact_bps=5.0,
            expected_slippage_bps=2.0,
            estimated_duration_min=0.0,
        )

    def estimate_cost(
        self,
        symbol: str,
        total_size: float,
        side: Literal["buy", "sell"],
        market_data: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        return {
            "impact_bps": 5.0,
            "slippage_bps": 2.0,
            "total_cost_bps": 7.0,
        }


class TWAPStrategy(BaseOrderStrategy):
    """时间加权平均价格策略

    将订单均匀分配到指定时间窗口内的多个切片中。
    """

    def __init__(
        self,
        num_slices: int = 10,
        duration_min: float = 30.0,
        randomize: bool = False,
    ):
        super().__init__("TWAP")
        self.num_slices = num_slices
        self.duration_min = duration_min
        self.randomize = randomize

    def split_order(
        self,
        symbol: str,
        total_size: float,
        side: Literal["buy", "sell"],
        start_time: datetime,
        market_data: pd.DataFrame | None = None,
        **kwargs,
    ) -> SliceResult:
        num_slices = kwargs.get("num_slices", self.num_slices)
        duration_min = kwargs.get("duration_min", self.duration_min)
        randomize = kwargs.get("randomize", self.randomize)

        base_size = total_size / num_slices
        slices: list[OrderSlice] = []
        interval = timedelta(minutes=duration_min / num_slices)

        for i in range(num_slices):
            size = base_size
            if randomize and i == num_slices - 1:
                size = total_size - sum(s.size for s in slices)
            slices.append(
                OrderSlice(
                    timestamp=start_time + interval * i,
                    size=size,
                    is_market=False,
                )
            )

        return SliceResult(
            slices=slices,
            expected_impact_bps=2.0,
            expected_slippage_bps=1.5,
            estimated_duration_min=duration_min,
        )


class VWAPStrategy(BaseOrderStrategy):
    """成交量加权平均价格策略

    根据历史成交量分布预测，将订单切片按预测成交量比例分配。
    """

    def __init__(
        self,
        num_slices: int = 12,
        duration_min: float = 60.0,
        volume_profile: pd.Series | None = None,
    ):
        super().__init__("VWAP")
        self.num_slices = num_slices
        self.duration_min = duration_min
        self.volume_profile = volume_profile

    def split_order(
        self,
        symbol: str,
        total_size: float,
        side: Literal["buy", "sell"],
        start_time: datetime,
        market_data: pd.DataFrame | None = None,
        **kwargs,
    ) -> SliceResult:
        num_slices = kwargs.get("num_slices", self.num_slices)
        duration_min = kwargs.get("duration_min", self.duration_min)
        volume_profile = kwargs.get("volume_profile", self.volume_profile)

        if volume_profile is not None and len(volume_profile) == num_slices:
            weights = volume_profile.values / volume_profile.sum()
        else:
            weights = np.ones(num_slices) / num_slices

        interval = timedelta(minutes=duration_min / num_slices)
        slices: list[OrderSlice] = []
        for i, w in enumerate(weights):
            slices.append(
                OrderSlice(
                    timestamp=start_time + interval * i,
                    size=total_size * w,
                    is_market=False,
                )
            )

        return SliceResult(
            slices=slices,
            expected_impact_bps=1.5,
            expected_slippage_bps=1.0,
            estimated_duration_min=duration_min,
        )


class IcebergStrategy(BaseOrderStrategy):
    """冰山订单策略

    将大单拆分为多个小单（显示量），每完成一个显示量后再释放下一个，
    隐藏真实订单总量。
    """

    def __init__(
        self,
        display_size: float = 1000.0,
        interval_sec: float = 60.0,
        variance_ratio: float = 0.2,
    ):
        super().__init__("Iceberg")
        self.display_size = display_size
        self.interval_sec = interval_sec
        self.variance_ratio = variance_ratio

    def split_order(
        self,
        symbol: str,
        total_size: float,
        side: Literal["buy", "sell"],
        start_time: datetime,
        market_data: pd.DataFrame | None = None,
        **kwargs,
    ) -> SliceResult:
        display_size = kwargs.get("display_size", self.display_size)
        interval_sec = kwargs.get("interval_sec", self.interval_sec)
        variance_ratio = kwargs.get("variance_ratio", self.variance_ratio)

        slices: list[OrderSlice] = []
        remaining = total_size
        current_time = start_time
        idx = 0

        while remaining > 0:
            size = min(display_size, remaining)
            if variance_ratio > 0:
                noise = np.random.uniform(-variance_ratio, variance_ratio)
                size = max(1.0, size * (1 + noise))
                size = min(size, remaining)

            slices.append(
                OrderSlice(
                    timestamp=current_time,
                    size=size,
                    is_market=False,
                )
            )
            remaining -= size
            current_time += timedelta(seconds=interval_sec)
            idx += 1
            if idx > 10000:
                raise RuntimeError("Iceberg slice overflow")

        duration_min = (len(slices) * interval_sec) / 60.0
        return SliceResult(
            slices=slices,
            expected_impact_bps=0.5,
            expected_slippage_bps=0.8,
            estimated_duration_min=duration_min,
        )


class MarketImpactModel:
    """市场冲击成本模型

    基于 Almgren-Chriss 框架的简化实现，用于预估大单执行对价格的影响。
    """

    def __init__(
        self,
        eta: float = 0.142,
        gamma: float = 0.314,
        sigma: float | None = None,
    ):
        self.eta = eta
        self.gamma = gamma
        self.sigma = sigma

    def permanent_impact(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float,
    ) -> float:
        """永久冲击（bps）"""
        if daily_volume <= 0:
            return 0.0
        x = order_size / daily_volume
        return self.gamma * volatility * math.sqrt(x) * 10000

    def temporary_impact(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float,
        participation_rate: float = 0.1,
    ) -> float:
        """临时冲击（bps）"""
        if daily_volume <= 0 or participation_rate <= 0:
            return 0.0
        x = order_size / daily_volume
        return self.eta * volatility * x / participation_rate * 10000

    def total_cost(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float,
        participation_rate: float = 0.1,
    ) -> dict[str, float]:
        """总冲击成本"""
        perm = self.permanent_impact(order_size, daily_volume, volatility)
        temp = self.temporary_impact(order_size, daily_volume, volatility, participation_rate)
        return {
            "permanent_bps": perm,
            "temporary_bps": temp,
            "total_bps": perm + temp,
        }

    def optimal_participation_rate(
        self,
        risk_aversion: float,
        order_size: float,
        daily_volume: float,
        volatility: float,
    ) -> float:
        """最优参与率（Almgren-Chriss 闭式解）"""
        if daily_volume <= 0 or volatility <= 0 or risk_aversion <= 0:
            return 0.1
        x = order_size / daily_volume
        return (self.eta * volatility * x / (risk_aversion * volatility**2)) ** (1 / 3)
