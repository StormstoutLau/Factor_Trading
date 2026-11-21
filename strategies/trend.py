"""趋势突破模板（P-051b DESIGN D4.3）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from core.registry import register_strategy
from core.strategy import MarketView, StrategyMeta, StrategyState, TargetWeights, code_hash
from strategies.base import (
    StrategyConfigError,
    build_config,
    equal_weight,
    require_history,
)

__all__ = ["TrendBreakoutConfig", "TrendBreakoutStrategy", "trend_breakout_factory"]


@dataclass(frozen=True)
class TrendBreakoutConfig:
    """突破配置（``atr_period`` 不参与算法，DESIGN R-2）。"""

    entry_n: int = 20
    exit_n: int = 10
    ma_n: int = 60

    def __post_init__(self) -> None:
        for name in ("entry_n", "exit_n", "ma_n"):
            value = getattr(self, name)
            if isinstance(value, bool) or value < 1:
                raise StrategyConfigError(f"trend_breakout: {name} 必须 >= 1: {value!r}")


class TrendBreakoutStrategy:
    """收盘突破 ``entry_n`` 日高点且站上 ``ma_n`` 均线入场；跌破 ``exit_n`` 日低点出场。"""

    def __init__(self, config: TrendBreakoutConfig) -> None:
        self._config = config
        self._meta = StrategyMeta(
            strategy_id="trend_breakout",
            version="1.0.0",
            param_schema=asdict(config),
            code_hash=code_hash(type(self)),
        )

    @property
    def meta(self) -> StrategyMeta:
        return self._meta

    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights:
        cfg = self._config
        history = require_history(
            view,
            max(cfg.ma_n, cfg.entry_n, cfg.exit_n),
            name="trend_breakout",
            keys=("close", "high", "low"),
        )
        upper = history["high"].iloc[-cfg.entry_n :].max(skipna=False)
        lower = history["low"].iloc[-cfg.exit_n :].min(skipna=False)
        ma = history["close"].iloc[-cfg.ma_n :].mean(skipna=False)
        selected: list[str] = []
        for code in (str(item) for item in view.prices.index):
            price = float(view.prices.get(code, np.nan))
            if not np.isfinite(price):
                continue
            holding = float(state.positions.get(code, 0.0)) > 0.0
            if holding:
                floor = float(lower.get(code, np.nan))
                if not np.isfinite(floor) or price >= floor:
                    selected.append(code)
            else:
                top = float(upper.get(code, np.nan))
                average = float(ma.get(code, np.nan))
                if np.isfinite(top) and np.isfinite(average) and price > top and price > average:
                    selected.append(code)
        return equal_weight(selected)


@register_strategy(
    "trend_breakout",
    description="趋势突破（N 日高点 + 均线）",
    config_schema={"entry_n": "int", "exit_n": "int", "ma_n": "int"},
)
def trend_breakout_factory(
    config: Mapping[str, Any] | None = None, **overrides: Any
) -> TrendBreakoutStrategy:
    """趋势突破工厂（DESIGN D6）。"""
    return TrendBreakoutStrategy(build_config(TrendBreakoutConfig, config, overrides))
