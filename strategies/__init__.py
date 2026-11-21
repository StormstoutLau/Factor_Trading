"""策略模板库（P-051b）：import 本包即触发 registry 注册。

注册顺序遵循 DESIGN §2.3：grid_atr → trend_breakout → ts_momentum → mean_reversion
（id 唯一，顺序仅影响 ``list_names()`` 输出顺序）。
"""

from strategies.grid import (
    GridATRConfig,
    GridATRStrategy,
    grid_atr_factory,
)
from strategies.trend import (
    TrendBreakoutConfig,
    TrendBreakoutStrategy,
    trend_breakout_factory,
)
from strategies.momentum import (
    TSMomentumConfig,
    TSMomentumStrategy,
    ts_momentum_factory,
)
from strategies.mean_reversion import (
    MeanReversionConfig,
    MeanReversionStrategy,
    mean_reversion_factory,
)

__all__ = [
    "GridATRConfig",
    "GridATRStrategy",
    "MeanReversionConfig",
    "MeanReversionStrategy",
    "TSMomentumConfig",
    "TSMomentumStrategy",
    "TrendBreakoutConfig",
    "TrendBreakoutStrategy",
    "grid_atr_factory",
    "mean_reversion_factory",
    "ts_momentum_factory",
    "trend_breakout_factory",
]
