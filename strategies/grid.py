"""网格模板（ATR 间距，P-051b DESIGN D4.4）。"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast

import numpy as np
import pandas as pd

from core.registry import register_strategy
from core.strategy import MarketView, StrategyMeta, StrategyState, TargetWeights, code_hash
from core.volatility import atr
from strategies.base import (
    StrategyConfigError,
    build_config,
    require_history,
    scale_to_one,
)

__all__ = ["GridATRConfig", "GridATRStrategy", "grid_atr_factory"]


@dataclass(frozen=True)
class GridATRConfig:
    """网格配置。``base_price`` 必填（DESIGN R-1 终版；``None`` → fail-fast）。"""

    base_price: Mapping[str, float] | None = None
    grid_k: float = 1.0
    levels: int = 3
    atr_period: int = 14

    def __post_init__(self) -> None:
        base = self.base_price
        if base is None or not base:
            raise StrategyConfigError("grid_atr: base_price 必填且不得为空")
        if self.grid_k <= 0:
            raise StrategyConfigError(f"grid_atr: grid_k 必须 > 0: {self.grid_k!r}")
        if isinstance(self.levels, bool) or self.levels < 1:
            raise StrategyConfigError(f"grid_atr: levels 必须 >= 1: {self.levels!r}")
        if isinstance(self.atr_period, bool) or self.atr_period < 2:
            raise StrategyConfigError(f"grid_atr: atr_period 必须 >= 2: {self.atr_period!r}")
        object.__setattr__(
            self,
            "base_price",
            {str(code): float(price) for code, price in base.items()},
        )


class GridATRStrategy:
    """``base_price`` 锚定的等间距加仓网格。"""

    def __init__(self, config: GridATRConfig) -> None:
        self._config = config
        self._meta = StrategyMeta(
            strategy_id="grid_atr",
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
            view, cfg.atr_period + 1, name="grid_atr", keys=("close", "high", "low")
        )
        atr_frame = cast(
            pd.DataFrame,
            atr(
                history["high"],
                history["low"],
                history["close"],
                period=cfg.atr_period,
            ),
        )
        atr_last = atr_frame.iloc[-1]
        base_prices = cfg.base_price or {}
        weights: dict[str, float] = {}
        for code in (str(item) for item in view.prices.index):
            base = base_prices.get(code)
            price = float(view.prices.get(code, np.nan))
            span = float(atr_last.get(code, np.nan))
            if base is None or not np.isfinite(price) or not np.isfinite(span):
                weights[code] = 0.0
                continue
            step = cfg.grid_k * span
            if step <= 0:
                weights[code] = 0.0
                continue
            level = math.floor((float(base) - price) / step)
            weights[code] = min(max(level, 0), cfg.levels) / cfg.levels
        return scale_to_one(pd.Series(weights, dtype=float))


@register_strategy(
    "grid_atr",
    description="网格（ATR 间距）",
    config_schema={
        "base_price": "dict (required)",
        "grid_k": "float",
        "levels": "int",
        "atr_period": "int",
    },
)
def grid_atr_factory(config: Mapping[str, Any] | None = None, **overrides: Any) -> GridATRStrategy:
    """网格模板工厂（DESIGN D6）。"""
    return GridATRStrategy(build_config(GridATRConfig, config, overrides))
