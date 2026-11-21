"""时间序列动量模板（P-051b DESIGN D4.1）。"""

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

__all__ = ["TSMomentumConfig", "TSMomentumStrategy", "ts_momentum_factory"]


@dataclass(frozen=True)
class TSMomentumConfig:
    """多周期动量投票配置。"""

    lookbacks: tuple[int, ...] = (20, 60, 120)
    min_votes: int = 2

    def __post_init__(self) -> None:
        lookbacks = tuple(int(lb) for lb in self.lookbacks)
        if not lookbacks:
            raise StrategyConfigError("ts_momentum: lookbacks 不得为空")
        if any(isinstance(lb, bool) or lb < 1 for lb in lookbacks):
            raise StrategyConfigError(f"ts_momentum: lookbacks 必须为正整数: {lookbacks!r}")
        if not 1 <= self.min_votes <= len(lookbacks):
            raise StrategyConfigError(
                f"ts_momentum: min_votes 须在 [1, {len(lookbacks)}]: {self.min_votes!r}"
            )
        object.__setattr__(self, "lookbacks", lookbacks)


class TSMomentumStrategy:
    """``lookbacks`` 各周期收益为正的票数 ≥ ``min_votes`` 即入选。"""

    def __init__(self, config: TSMomentumConfig) -> None:
        self._config = config
        self._meta = StrategyMeta(
            strategy_id="ts_momentum",
            version="1.0.0",
            param_schema=asdict(config),
            code_hash=code_hash(type(self)),
        )

    @property
    def meta(self) -> StrategyMeta:
        return self._meta

    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights:
        cfg = self._config
        lookbacks = cfg.lookbacks
        history = require_history(view, max(lookbacks), name="ts_momentum", keys=("close",))
        close = history["close"]
        latest = close.iloc[-1]
        votes = pd.Series(0, index=close.columns, dtype=int)
        for lookback in lookbacks:
            past = close.iloc[-lookback]
            ratio = latest / past - 1.0
            # 只计「正收益」票：负收益与零收益均记 0（§18.3.1 样例口径）
            votes = votes + (ratio.fillna(0.0) > 0.0).astype(int)
        selected = [str(code) for code in close.columns if int(votes.get(code, 0)) >= cfg.min_votes]
        return equal_weight(selected)


@register_strategy(
    "ts_momentum",
    description="时间序列动量（多周期投票）",
    config_schema={"lookbacks": "tuple[int, ...]", "min_votes": "int"},
)
def ts_momentum_factory(
    config: Mapping[str, Any] | None = None, **overrides: Any
) -> TSMomentumStrategy:
    """动量工厂（DESIGN D6）。"""
    return TSMomentumStrategy(build_config(TSMomentumConfig, config, overrides))
