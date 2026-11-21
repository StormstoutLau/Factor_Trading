# IMPL：P-051b 策略模板库（`strategies/` 四模板 + registry 接线）

> **批次**: P-051b · **Step 5 实施设计（逐处代码）** · 日期 2026-11-21
> **上游**: [DESIGN_p051b](DESIGN_p051b_strategy_library.md)（D1-D11 / I1-I12 / §0.3 收敛表）；[REVIEW_p051b_step4 §8](REVIEW_p051b_step4_design.md)（**4b 复验 5 项全过，0 P1 / 0 P2，P3-4b-1 已修**）
> **代码证据时点**: HEAD `9c914df`；本文仅新增文档，代码零改动
> **基座**: DeepSeek-V4.1-Flash（Step 6 复审须异构 GLM-5.3-Flash）

---

## 1. 变更总览

| # | 文件 | 变更 | 规模 |
|---|------|------|------|
| 1 | `core/strategy.py` | ① `MarketView` 末位加 `history` 字段；② `views_from_data` 末位加 `history_window` 参数 + 面板加载/切片 | +18 行 |
| 2 | `strategies/base.py` | **新建**：`StrategyConfigError` + `require_keys` / `require_history` / `equal_weight` / `scale_to_one` / `build_config` | 新文件 ≈ 105 行 |
| 3 | `strategies/grid.py` | **新建**：`GridATRConfig` + `GridATRStrategy` + `grid_atr_factory` | ≈ 95 行 |
| 4 | `strategies/trend.py` | 同上（`TrendBreakoutConfig`） | ≈ 85 行 |
| 5 | `strategies/momentum.py` | 同上（`TSMomentumConfig`） | ≈ 80 行 |
| 6 | `strategies/mean_reversion.py` | 同上（`MeanReversionConfig`） | ≈ 80 行 |
| 7 | `strategies/__init__.py` | 集中 import 触发注册 + `__all__` | ≈ 35 行 |
| 8 | `.github/workflows/tests.yml` | mypy 命令追加 `strategies` | +1 处 |
| 9 | `tests/test_p051b_*.py` × 7 | 新建，45 条用例 + C7 参数化 3 | ≈ 620 行 |

**零改动**：`core/sizing.py`、`core/engine_v2.py`、`core/stops.py`、`core/volatility.py`、`core/registry.py`、`tests/_golden_cases.py`、`scripts/record_golden.py`、22 条 golden 基线、`core/strategy.py` 既有 5 字段语义。

---

## 2. IMPL 澄清（伪码 → 可执行语义）

DESIGN D4.2/D4.3 用 `keep / exit / enter` 抽象；IMPL 必须定死它们的**输出数值**。

**C-1 `keep` 与 `enter` 等价于「当日入选」**：模板输出永远是 `equal_weight(selected)`，其中 `selected` = 满足「继续持有」或「新入场」条件的标的集合。`state.positions` **只用于判定是否持仓**（布尔），**不参与权重数值**。

- 理由：DESIGN D5「等权 1/n_selected」+ D9「`state.positions` 只读、不参与数值」；统一等权使 `keep` 无需记忆旧权重，避免「旧权重 + 新 1/n」行和冲突，且与 §18.3 全部闭式数值一致（M1 `{A:.5,B:.5}`、R1 `{A:1.0}`）。
- 可观测效应：持仓标的每日按当日入选数重新等权（等权组合的自然语义）。

**C-2 `exit` = 不计入 `selected`**；若 `selected` 为空 → 返回空 `Series(dtype=float)`（等价清仓，行和 0 ≤ 1）。

**C-3 价格 NaN**：`view.prices[code]` 非有限 → 该标的本日不计入 `selected`（不入场、不维持），**不 fail 全表**。

---

## 3. 逐处代码

### 3.1 `core/strategy.py`（2 处 additive）

**① `MarketView`（L111-120 区域）**

```python
@dataclass(frozen=True)
class MarketView:
    """策略可见的当日只读视图（不回传引擎内部对象）。"""

    date: pd.Timestamp
    signal: pd.Series
    tradable: pd.Series
    prices: pd.Series
    returns: Optional[pd.DataFrame]
    history: Optional[dict[str, pd.DataFrame]] = None
    """截至前一日的 OHLC 历史窗口（P-051b）。

    键为 ``"close"`` / ``"high"`` / ``"low"``；行为 ``[t-W, t-1]``（不含当日），
    列为全量 ``dm.stock_codes``；``history_window<=0`` 时为 ``None``。
    """
```

**② `views_from_data`（L270-310 区域）**

```python
    @staticmethod
    def views_from_data(
        dm: "IDataManager",
        signal: pd.DataFrame,
        tradable: Optional[pd.DataFrame] = None,
        returns_window: int = 0,
        history_window: int = 0,
    ) -> list[MarketView]:
        dates = dm.trade_dates
        aligned = signal.reindex(index=dates, columns=dm.stock_codes)
        prices = dm.get_adj_price("close", "raw")
        returns_matrix = dm.returns

        panels: dict[str, pd.DataFrame] = {}
        if history_window > 0:
            panels = {
                key: dm.get_adj_price(key, "raw").reindex(
                    index=dates, columns=dm.stock_codes
                )
                for key in ("close", "high", "low")
            }

        views: list[MarketView] = []
        for i, date in enumerate(dates):
            row = aligned.iloc[i]
            if tradable is not None and date in tradable.index:
                mask = tradable.loc[date].reindex(dm.stock_codes).fillna(False).astype(bool)
            else:
                mask = row.notna()
            window: Optional[pd.DataFrame] = None
            if returns_window > 0 and i >= returns_window:
                window = returns_matrix.iloc[i - returns_window : i]
            history: Optional[dict[str, pd.DataFrame]] = None
            if history_window > 0 and i >= history_window:
                history = {
                    key: panel.iloc[i - history_window : i]
                    for key, panel in panels.items()
                }
            views.append(
                MarketView(
                    date=date,
                    signal=row,
                    tradable=mask,
                    prices=prices.loc[date],
                    returns=window,
                    history=history,
                )
            )
        return views
```

**不变式**：`history_window=0` 时 `panels` 为空、`history` 恒 `None` → 与改动前逐值等价（I11）；`history[k].index == returns.index`（同 `iloc[i-W:i]`，V6）。

### 3.2 `strategies/base.py`（新建，全文）

```python
"""策略模板公共工具（P-051b）。

契约（DESIGN §3.3 / D10）：
- 无 I/O、无 logging、无全局状态；
- 契约不满足一律 ``StrategyConfigError``（``ValueError`` 子类，fail-fast）；
- 权重非负、行和 ≤ 1；``scale_to_one`` 只在行和 > 1 时缩放（空仓合法）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields
from typing import Any, TypeVar, cast

import pandas as pd

from core.strategy import MarketView

__all__ = [
    "StrategyConfigError",
    "build_config",
    "equal_weight",
    "require_history",
    "require_keys",
    "scale_to_one",
]

T = TypeVar("T")


class StrategyConfigError(ValueError):
    """模板参数或视图契约不满足（fail-fast，不静默降级）。"""


def require_keys(
    history: Mapping[str, pd.DataFrame], keys: Sequence[str], *, name: str
) -> None:
    """校验 ``history`` 键集。"""
    missing = [key for key in keys if key not in history]
    if missing:
        raise StrategyConfigError(f"{name}: history 缺少键 {missing}")


def require_history(
    view: MarketView,
    min_rows: int,
    *,
    name: str,
    keys: Sequence[str] = ("close",),
) -> dict[str, pd.DataFrame]:
    """校验并返回 ``history``（缺失 / 缺键 / 行数不足 → fail-fast）。"""
    history = view.history
    if history is None:
        raise StrategyConfigError(
            f"{name}: history is None（需 views_from_data(history_window>0)）"
        )
    require_keys(history, keys, name=name)
    rows = len(history[keys[0]])
    if rows < min_rows:
        raise StrategyConfigError(
            f"{name}: history 行数 {rows} < 最小窗长 {min_rows}"
        )
    return history


def equal_weight(codes: Sequence[str]) -> pd.Series:
    """等权 ``1/n``；``n=0`` → 空 Series（dtype=float）。"""
    unique = list(dict.fromkeys(str(code) for code in codes))
    if not unique:
        return pd.Series(dtype=float)
    weight = 1.0 / len(unique)
    return pd.Series(weight, index=unique, dtype=float)


def scale_to_one(weights: pd.Series) -> pd.Series:
    """非负校验 + 行和 > 1 时缩放（保证 ≤ 1）。"""
    if weights.empty:
        return pd.Series(dtype=float)
    values = weights.astype(float)
    if bool((values < 0).any()):
        raise StrategyConfigError("权重不得为负")
    total = float(values.sum())
    if total > 1.0:
        values = values * (1.0 / total)
    return values


def build_config(
    cls: type[T],
    config: Mapping[str, Any] | None,
    overrides: Mapping[str, Any],
) -> T:
    """``config`` 展开 + ``overrides`` 覆盖 → dataclass 实例；未知键 fail-fast。"""
    merged: dict[str, Any] = dict(config) if config is not None else {}
    merged.update(dict(overrides))
    known = {item.name for item in fields(cls)}  # type: ignore[arg-type]
    unknown = sorted(set(merged) - known)
    if unknown:
        raise StrategyConfigError(f"{cls.__name__}: 未知配置键 {unknown}")
    return cast(T, cls(**merged))
```

### 3.3 `strategies/grid.py`（新建，全文）

```python
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
            raise StrategyConfigError(
                f"grid_atr: atr_period 必须 >= 2: {self.atr_period!r}"
            )
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
def grid_atr_factory(
    config: Mapping[str, Any] | None = None, **overrides: Any
) -> GridATRStrategy:
    """网格模板工厂（DESIGN D6）。"""
    return GridATRStrategy(build_config(GridATRConfig, config, overrides))
```

### 3.4 `strategies/trend.py`（新建，全文）

```python
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
                raise StrategyConfigError(
                    f"trend_breakout: {name} 必须 >= 1: {value!r}"
                )


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
                if (
                    np.isfinite(top)
                    and np.isfinite(average)
                    and price > top
                    and price > average
                ):
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
```

### 3.5 `strategies/momentum.py`（新建，全文）

```python
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
        history = require_history(
            view, max(lookbacks), name="ts_momentum", keys=("close",)
        )
        close = history["close"]
        latest = close.iloc[-1]
        votes = pd.Series(0, index=close.columns, dtype=int)
        for lookback in lookbacks:
            past = close.iloc[-lookback]
            ratio = latest / past - 1.0
            votes = votes + np.sign(ratio.fillna(0.0)).astype(int)
        selected = [
            str(code)
            for code in close.columns
            if int(votes.get(code, 0)) >= cfg.min_votes
        ]
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
```

> **注**：`ratio.fillna(0.0)` 使价格 NaN → 收益记 0 → 0 票（C-3 的 NaN 政策）；`np.sign(0)=0`（M3）。

### 3.6 `strategies/mean_reversion.py`（新建，全文）

```python
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
            raise StrategyConfigError(
                f"mean_reversion: lookback 必须 >= 2: {self.lookback!r}"
            )
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
        z = z.mask(std == 0, 0.0)            # std==0 → z=0；std=NaN 时保持 NaN（F-I7）
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
```

> **注**：`z.mask(std == 0, 0.0)` —— `std==0` 的标的 z 记 0；`std=NaN`（窗口含 NaN）时保持 NaN → 不入选（F-I7）。按 C-1：未持仓 `0 <= -2.0` 为假 → 不入场；持仓 `0 >= -0.5` 为真 → 出场（与 F-D4 一致）。

### 3.7 `strategies/__init__.py`（新建，全文）

```python
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
```

### 3.8 `.github/workflows/tests.yml`

```yaml
# 原（.github/workflows/tests.yml L46）：
#   python -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
# 后（在 `strategy_evaluation` 之后插入 `strategies`，两个 flag 原样保留）：
#   python -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation strategies cli.py order_strategy web factor_library tools examples
```

> **F-I10 订正**：`strategies` 插入 `strategy_evaluation` 之后（与目录字母序无关，仅保证为独立包名）；**`--explicit-package-bases --check-untyped-defs` 必须原样保留**。

---

## 4. 测试规格

### 4.1 公共夹具

```python
# tests/_p051b_common.py（下划线前缀：不匹配 test_*.py，不被 pytest 收集）
from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy import MarketView, StrategyState

DATES = pd.bdate_range("2024-01-02", periods=140)
CODES = ["000001", "600000", "000002"]


def make_view(
    *,
    closes: np.ndarray,
    prices: dict[str, float] | None = None,
    positions: dict[str, float] | None = None,
    with_history: bool = True,
    codes: list[str] | None = None,
) -> tuple[MarketView, StrategyState]:
    codes = codes or CODES
    frame = pd.DataFrame(closes, index=DATES[: len(closes)], columns=codes)
    history = {
        "close": frame,
        "high": frame * 1.05,
        "low": frame * 0.95,
    } if with_history else None
    date = frame.index[-1]
    price_map = prices if prices is not None else {
        code: float(frame[code].iloc[-1]) for code in codes
    }
    view = MarketView(
        date=date,
        signal=pd.Series(1.0, index=codes),
        tradable=pd.Series(True, index=codes),
        prices=pd.Series(price_map, dtype=float),
        returns=None,
        history=history,
    )
    state = StrategyState(as_of=str(date.date()), positions=positions or {}, extras={})
    return view, state
```

> **注**：`high = close×1.05`、`low = close×0.95` 仅服务 trend 的默认场景；**G 组与 T 组自建显式 `high`/`low`**（§4.6 / §4.5），不复用此默认。

### 4.2 `tests/test_p051b_strategy_contract.py`（C1-C7）

```python
import pytest

import strategies  # noqa: F401  ← 触发注册
from core.registry import get_strategy_registry
from core.strategy import Strategy
from strategies.base import StrategyConfigError

FACTORIES = ["grid_atr", "trend_breakout", "ts_momentum", "mean_reversion"]
GRID_BASE = {"000001": 10.0, "600000": 10.0, "000002": 10.0}


def test_c1_all_registered_implement_protocol():
    registry = get_strategy_registry()
    for name in FACTORIES:
        entry = registry.get(name)
        assert entry is not None
        strategy = entry.factory(base_price=GRID_BASE) if name == "grid_atr" else entry.factory()
        assert isinstance(strategy, Strategy)
        assert strategy.meta.strategy_id == name
        assert len(strategy.meta.code_hash) == 12


def test_c2_factory_forms_equivalent():
    registry = get_strategy_registry()
    entry = registry.get("ts_momentum")
    assert entry is not None
    default = entry.factory()
    via_mapping = entry.factory({"lookbacks": (20, 60), "min_votes": 1})
    via_override = entry.factory(lookbacks=(20, 60), min_votes=1)
    assert default.meta.param_schema["lookbacks"] == (20, 60, 120)
    assert via_mapping.meta.param_schema == via_override.meta.param_schema


def test_c2_grid_requires_base_price():
    entry = get_strategy_registry().get("grid_atr")
    assert entry is not None
    with pytest.raises(StrategyConfigError):
        entry.factory(None)
    with pytest.raises(StrategyConfigError):
        entry.factory({})
    with pytest.raises(StrategyConfigError):
        entry.factory(base_price={})


def test_c3_duplicate_registration_warns(caplog):
    from core.registry import register_strategy

    with caplog.at_level("WARNING"):
        @register_strategy("ts_momentum", description="dup")
        def _dup(config=None, **kwargs):
            return None

    assert "already registered" in caplog.text


def test_c5_param_schema_matches_fields():
    from dataclasses import fields
    from strategies.grid import GridATRConfig

    entry = get_strategy_registry().get("grid_atr")
    assert entry is not None
    strategy = entry.factory(base_price={"A": 1.0})
    assert set(strategy.meta.param_schema) == {item.name for item in fields(GridATRConfig)}


def test_c6_unknown_key_rejected():
    entry = get_strategy_registry().get("ts_momentum")
    assert entry is not None
    with pytest.raises(StrategyConfigError):
        entry.factory(nope=1)


@pytest.mark.parametrize("name", FACTORIES)
def test_c7_history_none_fails(name):
    from _p051b_common import make_view

    entry = get_strategy_registry().get(name)
    assert entry is not None
    strategy = entry.factory(base_price=GRID_BASE) if name == "grid_atr" else entry.factory()
    view, state = make_view(closes=np.full((140, 3), 10.0), with_history=False)
    with pytest.raises(StrategyConfigError):
        strategy.generate_signals(view, state)
```

> C4（`code_hash` 稳定性）并入 C1 的 12-hex 断言 + 复用 P-044 V2 的稳定性用例（不重复实现）。

### 4.3 `tests/test_p051b_views_history.py`（V1-V7）

| ID | 断言 |
|----|------|
| V1 | `MarketView(date, signal, tradable, prices, returns)` 5 位置参数可用；`view.history is None` |
| V2 | `pytest.raises(TypeError): hash(view)`；两个同值实例 `pytest.raises(ValueError): a == b` |
| V3 | `views_from_data(dm, signal, history_window=W)` 后 `set(history) == {"close","high","low"}`、`list(history["close"].columns) == dm.stock_codes` |
| V4 | `history_window=0` → 全部 `history is None`；`returns`/`prices` 形状与 dtype 正常；等价性以「1040 全量不退化」为准（I11，F-I12） |
| V5 | `history_window=60`，`i<60` → `None`，`i>=60` → 非空且 60 行 |
| V6 | `returns_window = history_window = 60` → `history["close"].index.equals(view.returns.index)` |
| V7 | `history["close"].iloc[-1]` == `dm.get_adj_price("close","raw").loc[dates[i-1]]` |

### 4.4 `tests/test_p051b_ts_momentum.py`（M1-M8）

M1 完整用例（W=120 行窗口，锚点 t−120/t−60/t−20）：

```python
def test_m1_votes_sample_from_section_18_3_1():
    from strategies.momentum import TSMomentumConfig, TSMomentumStrategy

    # 120 行窗口（W = max(lookbacks)）；锚点行索引：
    #   iloc[-120]=0 → t−120, iloc[-60]=60 → t−60, iloc[-20]=100 → t−20, iloc[-1]=119 → t−1
    closes = np.full((120, 3), 100.0)          # 中间值任意（只影响数值不影响符号）
    closes[0, :] = [100.0, 50.0, 100.0]        # t−120
    closes[60, :] = [60.0, 60.0, 80.0]         # t−60
    closes[100, :] = [80.0, 70.0, 70.0]        # t−20
    closes[119, :] = [90.0, 80.0, 75.0]        # t−1
    # A: 90/100−1=−0.10(0) 90/60−1=+0.50(1) 90/80−1=+0.125(1) → 2 票
    # B: 80/50−1=+0.60(1)  80/60−1=+0.333(1) 80/70−1=+0.143(1)  → 3 票
    # C: 75/100−1=−0.25(0) 75/80−1=−0.0625(0) 75/70−1=+0.071(1) → 1 票
    strategy = TSMomentumStrategy(TSMomentumConfig())
    view, state = make_view(closes=closes)
    weights = strategy.generate_signals(view, state)
    assert weights.round(12).to_dict() == {"000001": 0.5, "600000": 0.5}
    assert "000002" not in weights.index
```

> 权威数值来自 [RESEARCH §18.3.1 表](RESEARCH_p051b_strategy_templates.md#L1046)，本用例逐点抄录，禁改写。

| ID | 断言 |
|----|------|
| M2 | `min_votes=3` → 仅 B 入选 `{B: 1.0}` |
| M3 | 某标的全部周期收益 == 0 → 0 票 → 不入选（含 `sign(0)=0`） |
| M4 | `view.prices` 为空 Series → 返回空 Series、`dtype == float` |
| M5 | 非负、`sum <= 1 + 1e-9`、`index ⊆ CODES` |
| M6 | 两次调用 `pd.testing.assert_series_equal` 相等 |
| M7 | 改 `history["close"]` 的 `t−1` 值 → 结果变；改 `view.prices` → 结果不变 |
| M8 | `history` 行数 = `max(lookbacks) − 1` → `StrategyConfigError` |

### 4.5 `tests/test_p051b_mean_reversion.py` / `trend_breakout.py`（R1-R7 / T1-T5）

**R 组统一构造条款（F-I3）**：20 行窗口，**前 `20−k` 行 = 10.0（H）、末 `k` 行 = 9.0（L）**，即 `latest = window.iloc[-1] = L`（§18.3.2 闭式推导的前提）。**不可把 L 放头部**——那会让 `latest = H`、z 变正，断言全部反转。

- R1（k=3）：行 0..16=10.0，行 17..19=9.0 → z=−2.3202；
- R2（k=4）：行 0..15=10.0，行 16..19=9.0 → z=−1.9494；
- R3（k=1）：行 0..18=10.0，行 19=9.0 → z=−4.2485（单点偏离不变量）；
- R4/R5（k=16/15）：同条款 + `positions={"A": 0.5}`。

| ID | 断言 |
|----|------|
| R1 | k=3 → z=−2.3202 ≤ −2 → 入场 `{A: 1.0}` |
| R2 | k=4 → z=−1.9494 > −2 → 空 Series |
| R3 | k=1 → z=−4.24853（与偏离幅度无关的不变量） |
| R4 | `positions={"A":0.5}` + k=16 → z=−0.4873 ≥ −0.5 → 空 Series |
| R5 | `positions={"A":0.5}` + k=15 → z=−0.5627 < −0.5 → `{A:1.0}` |
| R6 | 恒定价（std=0）：未持仓 → 空；`positions={"A":0.5}` → 空 |
| R7 | 纯函数 + `index ⊆ CODES` |

| ID | 断言 |
|----|------|
| T1 | 60 行 close=10、high=10、low=9（upper=10）；`prices=11.0` → 11>10 且 11>ma=10 → 入场 `{A:1.0}` |
| T2 | **自建夹具**：60 行 close=10、high=11、low=9（upper=11、ma=10）；`prices=10.5` → 10.5<11 → 空 Series（F-I4） |
| T3 | `positions={"A":0.5}`、low 末 10 行 = 9、`prices=8.5` → 空 Series |
| T4 | `positions={"A":0.5}`、`prices=9.5` → `{A:1.0}` |
| T5 | 纯函数 + `index ⊆ CODES` |

### 4.6 `tests/test_p051b_grid_atr.py`（G1-G7）

G1/G2 专用夹具：15 行 `high=10.5 / low=9.5 / close=10`，`base_price={"A": 10.0}`，`atr_period=14` → ATR=1.0（全 TR 相等，seed=1.0 精确）。

| ID | 断言 |
|----|------|
| G1 | `atr(...).iloc[-1]` ≈ 1.0（第 15 行）；与 `atr_period` 种子无关 |
| G2 | `prices` 取 10/9/8/7/6 → 权重 0 / 1/3 / 2/3 / 1 / 1（单标的，和 ≤1） |
| G3 | A: base=10, price=9（1/3）；B: base=10, price=6（3/3=1）→ 缩放 `{A:0.25, B:0.75}` |
| G4 | `factory(None)` / `factory({})` / `GridATRConfig(base_price={})` → `StrategyConfigError` |
| G5 | `base_price` 缺 B 键 → `{A: ...}`，B 权重 0 |
| G6 | 单标的 `high/low` 全 NaN → 该标的 0，其余正常 |
| G7 | 纯函数 + `index ⊆ CODES` |

### 4.7 `tests/test_p051b_end_to_end.py`（E1-E4）

E1 参数化四模板。**端到端协议（F-I2，三步，E1/E3/E4 通用）**：

```python
PERIODS = 30
WINDOW = 15   # ≥ 四模板最小窗长（grid=atr_period+1=15 / trend=10 / momentum=5 / mean_reversion=5）

def _e_fixture(root: Path) -> pd.DatetimeIndex:
    dates = pd.bdate_range("2024-01-02", periods=PERIODS)
    close = np.array([[10.0 + 0.1 * i, 20.0 + 0.1 * i] for i in range(PERIODS)])
    write_price_fixture(
        root, dates, ["000001", "600000"], close,
        high_prices=close * 1.02, low_prices=close * 0.98,
    )
    write_factor(
        root, "factor_value", np.tile([1.0, 2.0], (PERIODS, 1)),
        dates, ["000001", "600000"],
    )
    return dates

@pytest.mark.parametrize(
    "name,extra",
    [
        ("grid_atr", {"base_price": {"000001": 10.0, "600000": 20.0}}),
        ("trend_breakout", {"entry_n": 5, "exit_n": 3, "ma_n": 10}),
        ("ts_momentum", {"lookbacks": (5,), "min_votes": 1}),
        ("mean_reversion", {"lookback": 5}),
    ],
)
def test_e1_four_templates_end_to_end(tmp_path, name, extra):
    dates = _e_fixture(tmp_path)                 # 30 行（P-044 的 _fixture 只有 5 行，不足）
    engine = _make_engine(tmp_path)              # 引擎 cfg 复用 P-044（不负责写夹具）
    engine.setup()

    entry = get_strategy_registry().get(name)
    assert entry is not None
    adapter = BacktestAdapter(entry.factory(**extra))
    views = adapter.views_from_data(
        engine.dm,
        engine._composite_signal,
        tradable=engine.universe.tradable,
        returns_window=0,
        history_window=WINDOW,
    )
    # ① 前 WINDOW 日 history=None（模板 fail-fast 属预期）→ 只消费有效段
    frame = adapter.signals_frame(views[WINDOW:])
    # ② 头部补零行：满足 set_signal 的 index == dm.trade_dates 全集校验
    head = pd.DataFrame(0.0, index=dates[:WINDOW], columns=frame.columns)
    full = pd.concat([head, frame])
    assert list(full.index) == list(dates)

    engine.set_signal(full, mode="weights")
    assert engine._signal_mode == "weights"
    results = engine.run()
    assert np.isfinite(results["portfolio_value"]).all()
```

> **注**：`write_price_fixture` 的 high/low 关键字名以 `_synth_fixture.py` 实际签名为准（Step 9 核对；若为 `high`/`low` 则按实际改）。协议 ① ② 缺一不可——只做 ① 会被 `set_signal` 的 index 校验拒收，只做 ② 会因首日 `history=None` 抛错。

| ID | 断言 |
|----|------|
| E1 | 四模板端到端不抛（按上协议）、`_signal_mode == "weights"`、净值序列全部有限 |
| E2 | **自建价格路径（F-I6）**：单标的 close `10→10→7.5`（第 3 日 −25%）→ `grid_atr` 持仓 → `apply_stops(frame, ohlc_from_data(dm), StopConfig(stop_loss_pct=0.2))` → 第 3 日起该标的权重 0 |
| E3 | `signals_frame` 每行 `sum <= 1 + 1e-9`（消费 `views[WINDOW:]`，同协议） |
| E4 | 同一 `views[WINDOW:]` 两次 `signals_frame` → `assert_frame_equal` |

**计数**：C 7 + V 7 + M 8 + R 7 + T 5 + G 7 + E 4 = **45**；C7 参数化 4 例额外 +3 → pytest 预估 **+48**（1040 → 1088）。**Step 9 实测 = 1091**（E1 参数化 4 例另 +3）。

---

## 5. 实施顺序（TDD）

| 步 | 动作 | 验证 |
|----|------|------|
| 1 | 改 `core/strategy.py` 2 处 | `pytest -q` → 1040 全绿（I11 零退化） |
| 2 | 写 `tests/test_p051b_views_history.py`（V1-V7）红态 | 全红（`history` 字段不存在） |
| 3 | 新建 `strategies/base.py` + `models` | 单元可导入 |
| 4 | 逐模板「先测后码」：M → R → T → G | 每文件红→绿 |
| 5 | `strategies/__init__.py` + C1-C7 | `registry` 四 id 可取 |
| 6 | E1-E4 端到端 | 四模板 `run()` 通过 |
| 7 | CI mypy 追加 `strategies`；本地 mypy/black | 119 files / 0 error |

---

## 6. 风险与注意

| # | 注意点 |
|---|--------|
| 1 | `warn_return_any = true`：`dm.get_adj_price` 已声明返回 `pd.DataFrame`；`core.volatility.atr` 返回 union → 已在 grid.py 用 `cast(pd.DataFrame, ...)` 收窄（F-I11），无需运行期检查 |
| 2 | `asdict(config)` 对 `base_price: Mapping` 深拷贝为 dict → JSON 安全（C5 只查顶层键） |
| 3 | `atr()` 传入 3 个 DataFrame 返回 DataFrame；`.iloc[-1]` → Series，`.get(code)` 安全 |
| 4 | `math.floor` 对 numpy float 返回 int（G2 的档位为整数，无浮点边界问题；样例均为精确值） |
| 5 | `equal_weight` 用 `dict.fromkeys` 去重保序（M5 `index ⊆ CODES`） |
| 6 | `test_p051b_common.py` 不以 `test_` 开头之外还需**无 `test_` 函数**，避免被收集为用例（保持 +48 计数可控） |
| 7 | 禁录制：全部断言为闭式值或其舍入（`round(10)` / `pytest.approx`），零 golden 新增 |
| 8 | 不动 `core/strategy.py` 既有 5 字段顺序；`history` 必须末位带默认值 |

---

## 7. 自检（Step 6 复审输入）

- [x] 全部代码基于实读事实：`register_strategy` 签名（registry.py L341-359）、`PluginEntry.create`（L40-44）、`get()` 返回 Optional（L101-103）、`write_price_fixture` 支持 high/low（_synth_fixture L38-51）、mypy 配置（pyproject L109-114）
- [x] 设计缺口显式澄清（§2 C-1/C-2/C-3），未静默改变 DESIGN 语义
- [x] 零改动清单明确（§1 末尾）
- [x] 测试计数与 DESIGN §5 一致（45 条 / +48 / 1088）
- [x] 无新增 golden、无重录

---

## 8. 已裁决的实施细节

- **公共夹具命名 `tests/_p051b_common.py`**：下划线前缀不匹配 `test_*.py`，不被 pytest 收集为用例（保证 +48 计数可控）；测试文件以 `from _p051b_common import make_view` 导入（与 `_synth_fixture.py` 同惯例）。

---

## 9. Step 6 复审发现收敛表（3 P1 + 3 P2 + 6 P3）

| ID | 级别 | 复审发现 | 收敛动作 | 落点 |
|----|------|----------|----------|------|
| **F-I1** | **P1** | `base_price: Mapping[str, float]` 无默认值 → `factory(None)` 抛 `TypeError`，进不了 `__post_init__`，C2/G4 必败 | 字段默认 `None`；`__post_init__` 判 `None or 空` → `StrategyConfigError`；局部 `base` 变量供 mypy 收窄 | §3.3 |
| **F-I2** | **P1** | 端到端：头部 `history=None` → fail-fast；切片绕过 → `set_signal` index 校验失败 | 三步协议：`PERIODS=30` + `WINDOW=15` 夹具 → `signals_frame(views[WINDOW:])` → 头部补零行 concat 后 `set_signal` | §4.7 |
| **F-I3** | **P1** | R 组「首位 10.0、其余 9.0」→ `latest=H` 或 k=19，z 符号/幅值全错 | 统一条款：前 `20−k` 行 H、**末 k 行 L**（保证 `latest=L`）；逐条重列 k 与 z 值 | §4.5 |
| F-I4 | P2 | T2 沿用 T1 的 `high=10` → `upper=10`，10.5 会入场 | T2 自建 `high=11`（upper=11），10.5<11 拒绝 | §4.5 |
| F-I5 | P2 | C2_grid 参数化 2 例 → 计数 +49/1089，与 DESIGN 1088 矛盾 | 去参数化，单函数内三个 `pytest.raises` → 回到 +48/1088 | §4.2 |
| F-I6 | P2 | E2 恒定价无 ≥20% 跌幅，止损断言前提不成立 | E2 自建 `10→10→7.5`（第 3 日 −25%） | §4.7 |
| F-I7 | P3 | `where(std>0, 0.0)` 使 std=NaN 也走 0 分支，注释与路径不符 | 改 `mask(std == 0, 0.0)`（std=NaN 保持 NaN） | §3.6 |
| F-I8 | P3 | 注册顺序与 DESIGN §2.3 不一致 | `__init__.py` 改 grid→trend→momentum→mean_reversion | §3.7 |
| F-I9 | P3 | `make_view` 残留「index=-1」垃圾注释 | 删除 | §4.1 |
| F-I10 | P3 | tests.yml「原」行缺 `--explicit-package-bases --check-untyped-defs` | 原文引用补全，映射保留两个 flag | §3.8 |
| F-I11 | P3 | `atr()` union 返回的 `.iloc[-1]` mypy 收窄风险 | `cast(pd.DataFrame, atr(...))` 后再 `.iloc[-1]` | §3.3 |
| F-I12 | P3 | V4「与改动前逐值相同」不可测 | 改「history 恒 None + 形状/dtype 正常；等价性以 1040 不退化」 | §4.3 |

**计数复核（收敛后）**：45 条不变（F-I5 去参数化使 C 组名义 7 条不变）、参数化仅 C7（+3）、pytest 预估 +48 → **1040 → 1088** 与 DESIGN §5/D11 一致。**Step 9 实测 1091**（+3 来自 E1 参数化 4 例，见 CHECKLIST §7）。
