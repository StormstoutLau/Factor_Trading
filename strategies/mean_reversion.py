"""均值回归模板（P-051b DESIGN D4.2）。"""

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

__all__ = ["MeanReversionConfig", "MeanReversionStrategy", "mean_reversion_factory"]


@dataclass(frozen=True)
class MeanReversionConfig:
    """z-score 均值回归配置（时间止损交 ``core.stops``，DESIGN R-3）。"""

    lookback: int = 20
    z_entry: float = 2.0
    z_exit: float = 0.5

    def __post_init__(self) -> None:
        if isinstance(self.lookback, bool) or self.lookback < 2:
            raise StrategyConfigError(f"mean_reversion: lookback 必须 >= 2: {self.lookback!r}")
        if self.z_entry <= 0:
            raise StrategyConfigError(f"mean_reversion: z_entry 必须 > 0: {self.z_entry!r}")
        if self.z_exit < 0:
            raise StrategyConfigError(f"mean_reversion: z_exit 必须 >= 0: {self.z_exit!r}")


class MeanReversionStrategy:
    """z ≤ ``-z_entry`` 入场；持仓中 z ≥ ``-z_exit`` 出场。"""

    def __init__(self, config: MeanReversionConfig) -> None:
        self._config = config
        self._meta = StrategyMeta(
            strategy_id="mean_reversion",
            version="1.0.0",
            param_schema=asdict(config),
            code_hash=code_hash(type(self)),
        )

    @property
    def meta(self) -> StrategyMeta:
        return self._meta

    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights:
        cfg = self._config
        history = require_history(view, cfg.lookback, name="mean_reversion", keys=("close",))
        window = history["close"].iloc[-cfg.lookback :]
        mean = window.mean()
        std = window.std(ddof=1)
        latest = window.iloc[-1]
        z = (latest - mean) / std
        z = z.mask(std == 0, 0.0)  # std==0 → z=0；std=NaN 时保持 NaN（F-I7）
        z = z.where(np.isfinite(z), np.nan)  # 价格 NaN → z=NaN → 不入选
        selected: list[str] = []
        for code in (str(item) for item in view.prices.index):
            value = float(z.get(code, np.nan))
            if not np.isfinite(value):
                continue
            holding = float(state.positions.get(code, 0.0)) > 0.0
            if holding:
                if value >= -cfg.z_exit:
                    continue
                selected.append(code)
            elif value <= -cfg.z_entry:
                selected.append(code)
        return equal_weight(selected)


@register_strategy(
    "mean_reversion",
    description="均值回归（z-score）",
    config_schema={"lookback": "int", "z_entry": "float", "z_exit": "float"},
)
def mean_reversion_factory(
    config: Mapping[str, Any] | None = None, **overrides: Any
) -> MeanReversionStrategy:
    """均值回归工厂（DESIGN D6）。"""
    return MeanReversionStrategy(build_config(MeanReversionConfig, config, overrides))
