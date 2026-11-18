# IMPL：P-044 策略接口抽象（Strategy Protocol + BacktestAdapter）

> **批次**: P-044 · **Step 5 实施规划** · 日期 2026-11-18
> **判档**: **T1**（新建 `core/strategy.py` 契约 + `core/registry.py` 扩展 + `core/engine_v2.py` 信号模式分支 + `tests/`）
> **上游**: [DESIGN_p044_strategy_interface.md](DESIGN_p044_strategy_interface.md)（D1-D8 / §5 V1-V8 / §6 I1-I10 / §10 Step 4 Review pass：0 P1/P2 + 5 P3 当轮处置 + 2 项补记）
> **代码时点**: HEAD `96384f6`（P-043 关闭；行号为该时点，插入后位移，以锚点文字为准）
> **基座**: DeepSeek-V4.1-Flash（Step 6 Review 须异构 GLM-5.3-Flash；本轮不预填评审结论）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 落地批次 | B1 契约（新建 `core/strategy.py`）→ B2 注册表（`core/registry.py`）→ B3 引擎信号模式（`core/engine_v2.py`）→ B4 测试（`tests/test_p044_strategy_interface.py`） |
| 行为变更 | **默认零变更**（`_signal_mode="scores"`；不调用 `set_signal` 时既有优化器路径逐字执行） |
| 新增能力 | ① `Strategy` 契约与三数据模型；② `BacktestAdapter` 批量物化目标权重；③ `engine.set_signal(df, mode="weights")` 显式权重通道 |
| 不触碰 | `agents/multi_strategy_engine.py`（零 diff）/ `core/config.py`（零新字段）/ `core/interfaces.py` / `core/portfolio.py` / `core/rebalance.py` / `core/target_positions.py` / `SignalTranslator` / golden 夹具 |
| 零预填 | §9（Step 6）与 §10（Step 9）为占位，实测后回填 |

---

## 2. 任务拆解

| 批 | 文件 | 改动 |
|----|------|------|
| **B1** | `core/strategy.py`（新建） | `canonical_json` / `code_hash` / `StrategyMeta` / `StrategyState` / `MarketView` / `TargetWeights` / `StrategyFactory` / `Strategy`（Protocol）/ `FactorSignalStrategy` / `DirectionalStrategy` / `BacktestAdapter` |
| **B2** | `core/registry.py` | 模块 docstring +1 行；`_strategy_registry`（L180 后）；`get_strategy_registry()`（L220 后）；`register_strategy()`（L327 后） |
| **B3** | `core/engine_v2.py` | typing +`Literal`（L13）；`__init__` +1 属性（L181 后）；`set_signal` 新方法（L356/L358 之间）；`_execute_rebalance` +1 分支（原 try/except 整体缩进进 `else`） |
| **B4** | `tests/test_p044_strategy_interface.py`（新建） | V1-V8（8 用例） |

依赖：B3 无 B1 依赖（`set_signal` 只处理 DataFrame）；B4 依赖 B1/B2/B3。四批可独立 revert。

---

## 3. 接口签名与实现规格

### 3.1 B1：`core/strategy.py`（新建，完整代码）

```python
"""策略接口抽象（P-044）：Strategy 契约 / 状态模型 / 回测适配器。

设计约束（DESIGN §2 D1-D4）：
- 策略只产权重（与 qlib ``WeightStrategyBase`` 同构），不接触订单/执行/账目；
- ``MarketView`` 只读引用，不快照大矩阵；
- ``StrategyState`` 仅含 JSON 安全类型，支持往返与重放；
- ``code_hash`` 绑定类源码（dedent + 换行归一 + sha256 前 12 hex），源不可得时
  回退 ``q:`` 前缀（不静默）。
"""

from __future__ import annotations

import hashlib
import inspect
import json
import textwrap
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    Optional,
    Protocol,
    TypeAlias,
    runtime_checkable,
)

import pandas as pd

if TYPE_CHECKING:
    from core.interfaces import IDataManager, IOptimizer

TargetWeights: TypeAlias = pd.Series
"""目标权重类型别名：index=标的，value=非负权重（负权重/空头属 P-050）。"""

StrategyFactory = Callable[..., "Strategy"]


def canonical_json(value: Any) -> str:
    """确定性 JSON 序列化（排序键、紧凑分隔符、不转义非 ASCII）。"""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def code_hash(target: Any) -> str:
    """策略代码指纹：类源码归一化后 sha256 前 12 hex；源不可得时回退 ``q:`` 前缀。

    回退链：``getsource(类)`` → ``getsource(generate_signals)`` → ``q:`` 前缀种子。
    类取源对动态类抛 ``TypeError``（``__module__='builtins'``）、方法取源抛
    ``OSError``（Step 4 探针 D1/D2），故两处均捕获 ``(OSError, TypeError)``。
    """
    source = ""
    try:
        source = inspect.getsource(target)
    except (OSError, TypeError):
        method = getattr(target, "generate_signals", None)
        if method is not None:
            try:
                source = inspect.getsource(method)
            except (OSError, TypeError):
                source = ""
    if not source:
        seed = "|".join(
            [
                str(getattr(target, "__qualname__", type(target).__qualname__)),
                str(getattr(target, "version", "")),
                canonical_json(getattr(target, "param_schema", {})),
            ]
        )
        return "q:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    normalized = textwrap.dedent(source).replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class StrategyMeta:
    """策略元数据（§6 可追溯门禁：id + 版本 + 参数 schema + 代码 hash）。"""

    strategy_id: str
    version: str
    param_schema: dict[str, Any]
    code_hash: str


@dataclass(frozen=True)
class StrategyState:
    """策略状态快照（JSON 安全）：上一日目标权重 + 扩展位。"""

    as_of: str
    positions: dict[str, float]
    extras: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """导出 JSON 安全字典（positions 值归一到 float）。"""
        return {
            "as_of": self.as_of,
            "positions": {str(code): float(weight) for code, weight in self.positions.items()},
            "extras": dict(self.extras),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyState":
        """从字典恢复状态（仅接受含三键的 dict；positions 值强制 float）。"""
        return cls(
            as_of=str(data["as_of"]),
            positions={str(code): float(weight) for code, weight in data["positions"].items()},
            extras=dict(data["extras"]),
        )


@dataclass(frozen=True)
class MarketView:
    """策略可见的当日只读视图（不回传引擎内部对象）。"""

    date: pd.Timestamp
    signal: pd.Series
    tradable: pd.Series
    prices: pd.Series
    returns: Optional[pd.DataFrame]


@runtime_checkable
class Strategy(Protocol):
    """策略最小契约（D2）：只产权重，不接触订单/执行。"""

    @property
    def meta(self) -> StrategyMeta: ...

    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights: ...


class FactorSignalStrategy:
    """等价迁移：默认因子信号路径（引擎 ``_execute_rebalance`` 优化器分支）。

    与引擎逐字同构：``optimizer.optimize(view.signal[view.tradable].dropna(),
    view.returns)``；等价性由「同一优化器实例」保证（D6）。
    """

    def __init__(
        self,
        optimizer: "IOptimizer",
        *,
        strategy_id: str = "factor_signal",
        version: str = "1.0.0",
    ) -> None:
        self._optimizer = optimizer
        cfg = getattr(optimizer, "cfg", None)
        self._meta = StrategyMeta(
            strategy_id=strategy_id,
            version=version,
            param_schema={
                "optimizer": type(optimizer).__name__,
                "select_top": bool(getattr(cfg, "select_top", True)),
                "target_count": int(getattr(cfg, "target_count", 0)),
            },
            code_hash=code_hash(type(self)),
        )

    @property
    def meta(self) -> StrategyMeta:
        return self._meta

    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights:
        scores = view.signal[view.tradable].dropna()
        if scores.empty:
            return TargetWeights(dtype=float)
        return self._optimizer.optimize(scores, view.returns)


class DirectionalStrategy:
    """等价迁移：三方向策略（P-031 D2 语义逐字，见 ``agents/multi_strategy_engine``）。

    - ``direction="long"``（``select_top=True``）：买入因子得分最高的股票；
    - ``direction="short"``（``select_top=False``）：买入得分最低的股票（账目模型仅做多）；
    - ``direction="both"``：多头腿（``select_top=True``）× ``long_weight``，空头腿禁用。
    """

    short_leg_supported = False  # P-031 D2：账目模型无负持仓结算

    def __init__(
        self,
        optimizer: "IOptimizer",
        *,
        direction: str = "long",
        select_top: bool = True,
        long_weight: float = 1.0,
        strategy_id: Optional[str] = None,
        version: str = "1.0.0",
    ) -> None:
        if direction not in ("long", "short", "both"):
            raise ValueError(f"未知方向: {direction}（应为 long | short | both）")
        self.direction = direction
        self.select_top = select_top
        self.long_weight = long_weight
        self._optimizer = optimizer
        self._meta = StrategyMeta(
            strategy_id=strategy_id or f"directional_{direction}",
            version=version,
            param_schema={
                "direction": direction,
                "select_top": bool(select_top),
                "long_weight": float(long_weight),
                "optimizer": type(optimizer).__name__,
            },
            code_hash=code_hash(type(self)),
        )

    @property
    def meta(self) -> StrategyMeta:
        return self._meta

    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights:
        scores = view.signal[view.tradable].dropna()
        if scores.empty:
            return TargetWeights(dtype=float)
        weights = self._optimizer.optimize(scores, view.returns)
        if self.direction == "both":
            weights = weights * self.long_weight
        return weights


class BacktestAdapter:
    """回测适配器（D4）：策略逐日驱动 → 目标权重矩阵；状态演进留档。"""

    def __init__(self, strategy: Strategy) -> None:
        self._strategy = strategy
        self._state_history: list[StrategyState] = []

    @property
    def state_history(self) -> list[StrategyState]:
        """已推进的状态快照（只读副本，按驱动顺序）。"""
        return list(self._state_history)

    def signals_frame(
        self,
        views: Iterable[MarketView],
        initial_state: Optional[StrategyState] = None,
    ) -> pd.DataFrame:
        """逐日调用策略，物化目标权重矩阵（index=dates，columns=标的并集）。

        未出现的标的当日权重记 0（目标权重语义：当日不在目标组合即清仓）。
        """
        view_list = list(views)
        state = (
            initial_state
            if initial_state is not None
            else StrategyState(as_of="", positions={}, extras={})
        )
        rows: list[TargetWeights] = []
        for view in view_list:
            weights = self._strategy.generate_signals(view, state)
            weights = weights[weights != 0]
            rows.append(weights)
            state = StrategyState(
                as_of=view.date.strftime("%Y-%m-%d"),
                positions={str(code): float(weight) for code, weight in weights.items()},
                extras=dict(state.extras),
            )
            self._state_history.append(state)

        columns = sorted({str(code) for row in rows for code in row.index})
        frame = pd.DataFrame(
            0.0,
            index=pd.DatetimeIndex([view.date for view in view_list]),
            columns=columns,
        )
        for view, row in zip(view_list, rows):
            if len(row) > 0:
                frame.loc[view.date, [str(code) for code in row.index]] = row.to_numpy(dtype=float)
        return frame

    @staticmethod
    def views_from_data(
        dm: "IDataManager",
        signal: pd.DataFrame,
        tradable: Optional[pd.DataFrame] = None,
        returns_window: int = 0,
    ) -> list[MarketView]:
        """组装逐日 ``MarketView``（§4 数据流）。

        - ``signal`` 先按 ``(dm.trade_dates, dm.stock_codes)`` 重排，保证视图日期全集；
        - ``tradable`` 缺省为当日 ``signal.notna()``；
        - ``prices`` 取 ``dm.get_adj_price("close", "raw")``（与引擎成交口径一致）；
        - ``returns_window > 0`` 时给「截至前一日」窗口；历史不足记 ``None``
          （镜像引擎 ``date_index >= cov_lookback`` 的逐日语义）。
        """
        dates = dm.trade_dates
        aligned = signal.reindex(index=dates, columns=dm.stock_codes)
        prices = dm.get_adj_price("close", "raw")
        returns_matrix = dm.returns
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
            views.append(
                MarketView(
                    date=date,
                    signal=row,
                    tradable=mask,
                    prices=prices.loc[date],
                    returns=window,
                )
            )
        return views
```

**实现说明**

- `meta` 为 property（D2）：`isinstance(impl, Strategy)` 对 property 与注解成员均成立（Step 4 探针 A1/B1/C1/C2）；**不可**用 `issubclass`（property 同属非可调用成员，探针 A2/A3）。
- `code_hash(type(self))` 在构造期计算一次（类级粒度）；参数值入 `param_schema` 不入 hash（D3）。
- `signals_frame` 不复制全量收益矩阵：`views_from_data` 的 `returns` 为逐日窗口切片（内存口径见 DESIGN D4）。
- `views_from_data` 的 `mask` 显式 `reindex(dm.stock_codes)` 后再取布尔，避免 pandas 布尔索引对不齐抛 `IndexingError`。
- `signals_frame` **必须先求列并集再构造 DataFrame**：若以空列构造、依赖 `.loc` 首次赋值建列，未写入标的会呈 NaN 而非 0（本机 pandas 实测），违反「未出现标的记 0」契约。
- **`q:` 回退种子退化声明（S6 审）**：对**类目标**，类上无 `version`/`param_schema` 属性（二者仅存于实例 `meta`，构造期反向读取会循环依赖）→ 种子实际为 `qualname|version|{}`，同名无版本动态类会同种子碰撞；属 D3 已接受的回退语义，审计以 `q:` 前缀判别（不静默）。

### 3.2 B2：`core/registry.py`

**① 模块 docstring（L9-14「适用于:」列表末行）**：

```python
- Strategy (策略)
```

**② 全局注册表（`_agent_registry` L180 之后）**：

```python
_strategy_registry: Optional[PluginRegistry[Any]] = None
```

**③ 访问器（`get_agent_registry()` L215-220 之后）**：

```python
def get_strategy_registry() -> PluginRegistry[Any]:
    """获取 Strategy 注册中心"""
    global _strategy_registry
    if _strategy_registry is None:
        _strategy_registry = PluginRegistry("strategy")
    return _strategy_registry
```

**④ 注册装饰器（`register_agent` L310-327 之后，文件末尾）**：

```python
def register_strategy(
    name: str,
    description: str = "",
    config_schema: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    """Strategy 注册装饰器"""

    def decorator(factory: Callable[..., Any]) -> Callable[..., Any]:
        get_strategy_registry().register(
            name=name,
            factory=factory,
            description=description,
            config_schema=config_schema,
            metadata=metadata,
        )
        return factory

    return decorator
```

与既有 5 类别逐字同构；重复注册走 `PluginRegistry.register` L77-79（`logger.warning` + 覆写）→ V8 覆盖。

### 3.3 B3：`core/engine_v2.py`

**① typing import（L13）**：

```python
from typing import Any, Literal, Optional
```

**② `__init__` 信号模式属性（`_returns_matrix` L182 之后）**：

```python
        # 信号模式（P-044 D5）：默认 scores 零行为；weights=策略直出目标权重
        self._signal_mode: Literal["scores", "weights"] = "scores"
```

**③ `set_signal`（`_precompute_factors` 结束 L356 与 `run()` L358 之间）**：

```python
    def set_signal(
        self, signal: pd.DataFrame, *, mode: Literal["scores", "weights"] = "scores"
    ) -> None:
        """显式注入信号矩阵（P-044 D5）：``scores``=因子分（默认原行为）；``weights``=目标权重。

        ``weights`` 模式要求每行权重和 ≤ 1 且不得为负（空头属 P-050）；
        缺列按 0 补齐（目标权重语义），未知标的与 index 不一致 fail-fast。
        """
        if self.dm is None:
            raise RuntimeError("请先调用setup()方法")
        if mode not in ("scores", "weights"):
            raise ValueError(f"未知信号模式: {mode}")
        if not signal.index.equals(self.dm.trade_dates):
            raise ValueError("signal.index 必须与 dm.trade_dates 完全一致")
        unknown = set(signal.columns) - set(self.dm.stock_codes)
        if unknown:
            raise ValueError(f"signal 含未知标的: {sorted(unknown)[:5]}")
        aligned = signal.reindex(columns=self.dm.stock_codes)
        if mode == "weights":
            values = aligned.fillna(0.0)
            if (values.to_numpy() < 0).any():
                raise ValueError("weights 模式不接受负权重（空头属 P-050）")
            if (values.sum(axis=1) > 1.0 + 1e-9).any():
                raise ValueError("weights 模式要求每行权重和 ≤ 1")
            aligned = values
        self._composite_signal = aligned
        self._signal_mode = mode
```

**④ `_execute_rebalance` 组合优化段（L993-1023 整块替换）**：

```python
        # 组合优化（P-044 D5）：weights 模式策略直出，跳过优化器（权重不得二次优化）
        if self._signal_mode == "weights":
            target_weights = daily_signal.clip(lower=0.0)
        else:
            try:
                if date_index >= self.cfg.optimizer.cov_lookback:
                    assert returns_matrix is not None
                    start_idx = date_index - self.cfg.optimizer.cov_lookback
                    end_idx = date_index
                    returns_data = pd.DataFrame(
                        returns_matrix[start_idx:end_idx],
                        index=dm.trade_dates[start_idx:end_idx],
                        columns=dm.stock_codes,
                    )
                else:
                    returns_data = None

                target_weights = optimizer.optimize(tradable_stocks, returns_data)

                logger.debug(f"优化得到{len(target_weights)}只股票的目标权重")

            except Exception as e:
                self._diagnostics.record(date, "rebalance", e)
                self._emit(
                    EventType.ERROR,
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "stage": "rebalance",
                        "error_type": type(e).__name__,
                        "message": str(e)[: self._diagnostics.MAX_MESSAGE],
                    },
                )
                logger.error(f"组合优化失败: {e}")
                return
```

原 try/except 体**逐字不动**，仅整体缩进进 `else`（I1 零行为）。

### 3.4 边界语义（实施期显式声明）

| # | 边界 | 语义 |
|---|------|------|
| 1 | weights 行全 0 | **= 目标组合为空（清仓）**；与 scores 模式「当日无可交易标的 → 早退跳过」不同。策略欲「保持」须回填 `state.positions`（契约已提供），U-P044-2 语义边界 |
| 2 | tradable | weights 模式**不强制** tradable（策略经 `MarketView.tradable` 自主决策）；`_execute_rebalance` 的空可交易早退（L989-991）仍共用 |
| 3 | 缺列 | `set_signal` 按 `dm.stock_codes` 补齐为 0（weights）/ 保持 NaN（scores） |
| 4 | `factor_files` | `setup()` 预检（L197-205）要求非空；纯策略运行需占位因子文件，`set_signal` 整体替换信号（F-S4-P044-4） |
| 5 | 触发器 | weights 模式**禁配** `conditional`/`hybrid`（直接/间接消费 signal，Step 4 读码 L138-177/L265）；`fixed`/`daily` 零影响 |
| 6 | 负权重 | fail-fast（P-050 前不支持空头） |

---

## 4. 测试规格（`tests/test_p044_strategy_interface.py`，V1-V8）

### 4.1 文件头与夹具（完整）

```python
"""P-044：策略接口契约与权重模式接入（V1-V8）。

红态设计（IMPL §4.3）：核心符号一律函数内导入 → 逐用例失败而非收集期 error；
V4 为零行为护栏（当前代码即通过）。
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_factor, write_price_fixture

DATES = pd.bdate_range("2024-01-02", periods=5)
CODES = ["000001", "600000"]


def _fixture(root: Path) -> None:
    prices = np.array([[10.0 + 0.1 * i, 20.0 + 0.1 * i] for i in range(len(DATES))])
    write_price_fixture(root, DATES, CODES, prices)
    write_factor(root, "factor_value", np.tile([1.0, 2.0], (len(DATES), 1)), DATES, CODES)


def _make_optimizer(*, select_top: bool = True, target_count: int = 2):
    from core.config import OptimizerConfig
    from core.portfolio import EqualWeightOptimizer

    return EqualWeightOptimizer(
        OptimizerConfig(
            method="equal_weight",
            target_count=target_count,
            max_weight=1.0,
            round_lot=True,
            select_top=select_top,
        )
    )


def _make_engine(root: Path):
    from core.config import (
        BacktestConfig,
        CostConfig,
        FactorConfig,
        OptimizerConfig,
        RebalanceConfig,
        UniverseConfig,
    )
    from core.engine_v2 import BacktestEngineV2

    cfg = BacktestConfig(
        data_dir=root,
        output_dir=root / "out",
        factor_files=["factor_value.pkl"],
        cost=CostConfig(
            commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0
        ),
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",
            target_count=2,
            max_weight=1.0,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False
        ),
        initial_capital=10_000_000.0,
        enable_pending_orders=False,
        write_manifest=False,
    )
    return BacktestEngineV2(cfg)
```

### 4.2 V1-V8 完整代码

```python
def test_v1_contract_dataclasses_and_protocol():
    """I2 / I10：三 frozen dataclass + Strategy 运行时协议 + meta 四要素。"""
    from dataclasses import FrozenInstanceError

    from core.strategy import (
        FactorSignalStrategy,
        MarketView,
        Strategy,
        StrategyMeta,
        StrategyState,
        TargetWeights,
    )

    assert TargetWeights is pd.Series

    meta = StrategyMeta(
        strategy_id="x", version="1.0.0", param_schema={"a": 1}, code_hash="0123456789ab"
    )
    with pytest.raises(FrozenInstanceError):
        meta.strategy_id = "y"  # type: ignore[misc]

    state = StrategyState(as_of="2024-01-02", positions={"000001": 0.5}, extras={})
    with pytest.raises(FrozenInstanceError):
        state.as_of = "2024-01-03"  # type: ignore[misc]

    view = MarketView(
        date=DATES[0],
        signal=pd.Series({"000001": 1.0}),
        tradable=pd.Series({"000001": True}),
        prices=pd.Series({"000001": 10.0}),
        returns=None,
    )
    with pytest.raises(FrozenInstanceError):
        view.date = DATES[1]  # type: ignore[misc]

    strategy = FactorSignalStrategy(_make_optimizer())
    assert isinstance(strategy, Strategy)
    assert isinstance(strategy.meta, StrategyMeta)
    assert strategy.meta.strategy_id == "factor_signal"
    assert strategy.meta.version == "1.0.0"
    assert strategy.meta.param_schema["select_top"] is True
    assert strategy.meta.param_schema["target_count"] == 2
    assert len(strategy.meta.code_hash) == 12

    sig = inspect.signature(strategy.generate_signals)
    assert list(sig.parameters) == ["view", "state"]


def test_v2_code_hash_stability_and_fallback(tmp_path):
    """I7：同源码稳定 / 12 hex / 参数不入 hash / CRLF≡LF / 动态类 q: 回退。"""
    import importlib.util
    import sys

    from core.strategy import FactorSignalStrategy, code_hash

    h1 = code_hash(FactorSignalStrategy)
    assert h1 == code_hash(FactorSignalStrategy)
    assert len(h1) == 12
    assert all(char in "0123456789abcdef" for char in h1)

    # 参数不同、类源码相同 → 同 hash（参数入 param_schema）
    small = FactorSignalStrategy(_make_optimizer(target_count=2))
    large = FactorSignalStrategy(_make_optimizer(target_count=3))
    assert small.meta.code_hash == large.meta.code_hash
    assert small.meta.param_schema != large.meta.param_schema

    # CRLF 与 LF 源码同 hash（换行归一）
    source = "class Same:\n    def generate_signals(self, view, state):\n        return None\n"
    hashes = []
    for name, newline in (("p044_src_lf", "\n"), ("p044_src_crlf", "\r\n")):
        path = tmp_path / f"{name}.py"
        path.write_bytes(source.replace("\n", newline).encode("utf-8"))
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
            hashes.append(code_hash(module.Same))
        finally:
            sys.modules.pop(name, None)
    assert hashes[0] == hashes[1]

    # exec 动态类：类/方法均取源失败 → q: 前缀回退
    namespace: dict[str, Any] = {}
    exec(
        "class Dyn:\n"
        "    def generate_signals(self, view, state):\n"
        "        return None\n",
        namespace,
    )
    dynamic = code_hash(namespace["Dyn"])
    assert dynamic.startswith("q:")
    assert len(dynamic) == 14


def test_v3_state_json_roundtrip():
    """I4：to_dict → json → from_dict 往返相等；值类型归一。"""
    from core.strategy import StrategyState

    state = StrategyState(
        as_of="2024-01-05",
        positions={"000001": 0.5, "600000": 0.25},
        extras={"regime": "bull", "n": 2},
    )
    payload = json.dumps(state.to_dict(), ensure_ascii=False)
    restored = StrategyState.from_dict(json.loads(payload))

    assert restored == state
    assert restored.positions == {"000001": 0.5, "600000": 0.25}
    assert all(isinstance(value, float) for value in restored.positions.values())
    assert restored.extras == {"regime": "bull", "n": 2}


def test_v4_default_mode_zero_behavior(tmp_path):
    """I1 / D8：默认 scores → 两次运行指标/净值/成交完全一致（红态亦 PASS 护栏）。"""
    _fixture(tmp_path)

    first = _make_engine(tmp_path)
    first.setup()
    assert getattr(first, "_signal_mode", "scores") == "scores"
    results_a = first.run()

    second = _make_engine(tmp_path)
    second.setup()
    results_b = second.run()

    assert list(results_a["portfolio_value"]) == list(results_b["portfolio_value"])
    for key in (
        "total_return",
        "annual_return",
        "annual_volatility",
        "max_drawdown",
        "sharpe_ratio",
        "win_rate",
        "trading_days",
    ):
        assert results_a["performance_metrics"][key] == pytest.approx(
            results_b["performance_metrics"][key]
        ), key
    trades_a = first.executor.trade_log.get_trades_df()
    trades_b = second.executor.trade_log.get_trades_df()
    assert len(trades_a) == len(trades_b)
    assert float(trades_a["amount"].sum()) == pytest.approx(float(trades_b["amount"].sum()))


def test_v5_weights_mode_matches_scores_mode(tmp_path):
    """I3 / I9：strategy + weights 通道与默认 scores 路径成交/净值逐值一致。"""
    from core.strategy import BacktestAdapter, FactorSignalStrategy

    _fixture(tmp_path)

    baseline = _make_engine(tmp_path)
    baseline.setup()
    base_results = baseline.run()
    base_trades = baseline.executor.trade_log.get_trades_df()

    engine = _make_engine(tmp_path)
    engine.setup()
    adapter = BacktestAdapter(FactorSignalStrategy(engine.optimizer))
    views = adapter.views_from_data(
        engine.dm,
        engine._composite_signal,
        tradable=engine.universe.tradable,
        returns_window=engine.cfg.optimizer.cov_lookback,
    )
    frame = adapter.signals_frame(views)
    assert list(frame.index) == list(DATES)
    assert len(adapter.state_history) == len(DATES)

    engine.set_signal(frame, mode="weights")
    assert engine._signal_mode == "weights"
    results = engine.run()
    trades = engine.executor.trade_log.get_trades_df()

    assert len(trades) == len(base_trades)
    assert list(trades["stock"]) == list(base_trades["stock"])
    assert list(trades["quantity"]) == list(base_trades["quantity"])
    assert list(results["portfolio_value"].round(6)) == list(
        base_results["portfolio_value"].round(6)
    )
    for key in ("total_return", "annual_return", "max_drawdown", "sharpe_ratio", "trading_days"):
        assert results["performance_metrics"][key] == pytest.approx(
            base_results["performance_metrics"][key]
        ), key


def test_v6_directional_equivalence():
    """I3：三方向与 EqualWeightOptimizer 直出逐值相等；both=long×long_weight。"""
    from core.strategy import DirectionalStrategy, MarketView, StrategyState

    signal = pd.Series({"000001": 1.0, "600000": 2.0, "000002": 0.5})
    view = MarketView(
        date=DATES[0],
        signal=signal,
        tradable=pd.Series(True, index=signal.index),
        prices=pd.Series(10.0, index=signal.index),
        returns=None,
    )
    state = StrategyState(as_of="2024-01-02", positions={}, extras={})

    long_optimizer = _make_optimizer(select_top=True)
    short_optimizer = _make_optimizer(select_top=False)
    long_strategy = DirectionalStrategy(long_optimizer, direction="long", select_top=True)
    short_strategy = DirectionalStrategy(short_optimizer, direction="short", select_top=False)
    both_strategy = DirectionalStrategy(long_optimizer, direction="both", long_weight=0.5)

    long_expected = long_optimizer.optimize(signal, None)
    short_expected = short_optimizer.optimize(signal, None)

    pd.testing.assert_series_equal(long_strategy.generate_signals(view, state), long_expected)
    pd.testing.assert_series_equal(short_strategy.generate_signals(view, state), short_expected)
    both_weights = both_strategy.generate_signals(view, state)
    pd.testing.assert_series_equal(both_weights, long_expected * 0.5)
    assert float(both_weights.sum()) == pytest.approx(0.5)
    assert DirectionalStrategy.short_leg_supported is False
    assert both_strategy.meta.strategy_id == "directional_both"

    with pytest.raises(ValueError, match="未知方向"):
        DirectionalStrategy(long_optimizer, direction="sideways")


def test_v7_set_signal_validation(tmp_path):
    """I6：四类非法输入 fail-fast；scores 允许 NaN；未 setup 抛 RuntimeError。"""
    _fixture(tmp_path)

    engine = _make_engine(tmp_path)
    engine.setup()

    bad_index = pd.DataFrame(0.5, index=DATES[:-1], columns=CODES)
    with pytest.raises(ValueError, match="index"):
        engine.set_signal(bad_index, mode="weights")

    unknown = pd.DataFrame(0.5, index=DATES, columns=["000001", "999999"])
    with pytest.raises(ValueError, match="未知标的"):
        engine.set_signal(unknown, mode="weights")

    negative = pd.DataFrame(0.5, index=DATES, columns=CODES)
    negative.iloc[0, 0] = -0.1
    with pytest.raises(ValueError, match="负权重"):
        engine.set_signal(negative, mode="weights")

    over = pd.DataFrame(0.6, index=DATES, columns=CODES)
    with pytest.raises(ValueError, match="权重和"):
        engine.set_signal(over, mode="weights")

    with pytest.raises(ValueError, match="未知信号模式"):
        engine.set_signal(pd.DataFrame(0.5, index=DATES, columns=CODES), mode="bogus")

    scores = pd.DataFrame(np.nan, index=DATES, columns=CODES)
    scores.iloc[0, 0] = 1.0
    engine.set_signal(scores, mode="scores")
    assert engine._signal_mode == "scores"
    assert engine._composite_signal.shape == (len(DATES), len(CODES))
    assert np.isnan(engine._composite_signal.iloc[0, 1])

    fresh = _make_engine(tmp_path)
    with pytest.raises(RuntimeError, match="setup"):
        fresh.set_signal(scores, mode="scores")


def test_v8_strategy_registry(caplog):
    """I5：registry strategy 类别——单例 / 注册 / 查询 / 创建 / 覆写 warning。"""
    from core.registry import get_strategy_registry, register_strategy

    registry = get_strategy_registry()
    assert registry is get_strategy_registry()
    assert registry.category == "strategy"

    name = "p044_test_strategy"

    def factory(**kwargs: Any):
        return {"kwargs": kwargs}

    try:
        register_strategy(name, description="test")(factory)
        assert registry.has(name)
        entry = registry.get(name)
        assert entry is not None and entry.category == "strategy"
        assert registry.create(name, foo=1) == {"kwargs": {"foo": 1}}

        with caplog.at_level("WARNING"):
            register_strategy(name, description="again")(factory)
        assert any("already registered" in record.message for record in caplog.records)
        assert registry.get(name).description == "again"
    finally:
        registry.unregister(name)
    assert not registry.has(name)
```

### 4.3 红态预期（Step 9 首跑）

**确定性说明**：`performance_metrics` 含 `cumulative_return_series`（数组），整字典相等会因数组布尔歧义抛 `ValueError`——V4/V5 只断言标量键（`pytest.approx`），NAV 用 `portfolio_value` 逐值。

| 结果 | 用例 | 原因 |
|------|------|------|
| FAIL | V1/V2/V3/V5/V6 | `core.strategy` 不存在（`ModuleNotFoundError`） |
| FAIL | V7 | `BacktestEngineV2` 无 `set_signal`（`AttributeError`） |
| FAIL | V8 | `core.registry.get_strategy_registry` 不存在（`ImportError`） |
| PASS | V4 | 零行为护栏（`getattr(..., "_signal_mode", "scores")` 兜底） |

**聚合预测**：`7 failed, 1 passed`。与 P-043 教训一致：**以 Step 9 实测为准回填**。

---

## 5. 低效排除表

| # | 低效操作 | 排除方式 | 判据 |
|---|----------|----------|------|
| 1 | 适配器向量化批处理 | 策略契约为**逐日纯函数**（qlib/freqtrade 同构），不做批量包装；1460 日 × 单策略 = 1460 次调用，Python 开销可忽略 | `signals_frame` 单层循环，无嵌套重算 |
| 2 | `returns` 全矩阵快照 | `views_from_data` 只切「前一日回看窗口」（`returns_matrix.iloc[i-w:i]`），不复制全量 | 与引擎 `_execute_rebalance` 逐日构造同量级 |
| 3 | `set_signal` 重复全矩阵校验 | 一次 O(D×N) 扫描（1460×5688≈8.3M 单元，约 10-30ms），仅在注入时执行一次，不在日内循环 | 校验在方法内单次，无逐日复检 |
| 4 | `code_hash` 反复取源 | 构造期一次 `getsource` + sha256，缓存进 `meta` | `meta` 属性只读缓冲 |
| 5 | 测试重复起引擎 | 5 日 × 2 股单次 <1s；不引入 session 级夹具（隔离性优先） | 8 用例合计目标 <8s |

---

## 6. 兼容性与版本

| 项 | 结论 |
|----|------|
| Python | `>=3.10`；`Protocol` / `runtime_checkable` / `Literal` 均 stdlib |
| 新增依赖 | **0**（`hashlib`/`inspect`/`json`/`textwrap`/`dataclasses`） |
| `core/strategy.py` | 纯新增模块；无 I/O、无全局写（I8） |
| `core/registry.py` | 纯追加（+1 全局 +2 函数 +1 docstring 行）；既有 5 类别零改动 |
| `BacktestConfig` | **零新字段**（D8） |
| `BacktestEngineV2` | 新方法 `set_signal` + 私有属性 `_signal_mode`（默认 `"scores"`）；构造签名与既有 13 个注入参数零改动 |
| `agents/` | **零 diff**（M-A 裁决；`StrategyEngine` 内部重构归 P-051/U-P044-3） |
| golden | 13 零重录（默认 scores 路径逐字执行） |
| 产物 | 无新增文件/键；`trades.csv` / snapshots / manifest 结构不变 |

---

## 7. 门禁终态（Step 9 目标）

| 门禁 | 现值 | 目标 | 说明 |
|------|------|------|------|
| pytest | 803 | **811** | +8（V1-V8） |
| golden | 13·790 | **13·790** | 零重录 |
| black（`core tests` / 全仓） | 130·197 | **132·199** | **+2 文件**（`core/strategy.py` + `tests/test_p044...`；DESIGN §6 原记 +1 漏算测试文件，见 F-S5-P044-1） |
| mypy | 104 | **105** | +1（`core/strategy.py`） |
| AST `except Exception` | 22 | **22** | 门禁口径 = core 外十文件；`set_signal` 用 `ValueError`，新文件零该模式（F-S9-P043-1 口径） |
| `tests/*.py` | 92 | **93** | +1 测试文件 |
| uv lock | 0 | **0** | 零依赖 |

命令：

```powershell
$py = 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe'
$env:MPLBACKEND='Agg'; & $py -m pytest tests -q -p no:cacheprovider
& $py -m pytest tests -k golden -q -p no:cacheprovider
& $py -m black --check core tests
& $py -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
uv lock --check
```

---

## 8. 回退点

| 批 | revert 方式 | 残留 |
|----|-------------|------|
| B1 | 删除 `core/strategy.py` | 无（纯新增） |
| B2 | 还原 `core/registry.py` 4 处新增 | 无（无注册即无消费方） |
| B3 | 还原 `engine_v2.py` 4 处（typing / 属性 / `set_signal` / 分支）；原 try 体回退缩进 | 无（默认 `scores` 零行为） |
| B4 | 删除 `tests/test_p044_strategy_interface.py` | 无 |

四批均无数据迁移、无产物兼容问题；`agents/` 全程零 diff。

---

## 9. Step 6 实施 Review（异构 GLM-5.3-Flash，2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 复审 **GLM-5.3-Flash** ≠ 作者 DeepSeek-V4.1-Flash → **本轮异构成立**（Step 4/6 连续两轮异构）。评审对象：本文 §2-§8；取证方式 = 读码（E3）+ 本机探针（E2）+ 机械复核，零预填、回填于完稿后。

### 9.1 复核读数

| # | 项 | 复核方法 / 读数 | 判定 |
|---|----|----------------|------|
| 1 | B3 引擎四处锚点 | typing L13（`Any, Optional` → +`Literal`）；属性位 L181-182（`_composite_signal`/`_returns_matrix` 之后、L184 注释之前）；`set_signal` 插于 `_precompute_factors` 末行 L356 与 `run()` L358 之间；`_execute_rebalance` L993-1023 与 §3.3 ④ 替换文本**逐字比对一致**（含空行与 `logger.debug`） | ✅ |
| 2 | B2 registry 三处锚点 | `_agent_registry` L180 后 / `get_agent_registry()` L215-220 后 / `register_agent` L310-327 后（文件末尾）；docstring「适用于:」列表末行 L14；新增符号与既有 5 类别逐字同构；重复注册走 `PluginRegistry.register` L77-79 warning+覆写 | ✅ |
| 3 | **零权重 ≡ 缺席（关键语义）** | [target_positions.py](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py) L82-84 `weight_map.get(stock, 0.0)` → L100-111 `weight <= 0.0` 有持仓即 `is_exit=True` 清仓：strategy 路径传全 universe Series（含 0）与 baseline 传优化器输出（仅入选）**走同一分支** → V5 等价性与 §3.4 边界 1（全 0 = 清仓）从文档声明**升级为 E3 读码证实**；L79-80 负权重 ValueError / L90-91 行和 >1 warning 与 `set_signal` fail-fast 双重防御一致 | ✅ |
| 4 | 数据列序对齐 | `dm.returns` = `close_data.pct_change()`（data.py L494），close_data 已 `reindex(columns=self._stock_codes)`（L476）→ 适配器 `returns_matrix.iloc[i-w:i]` ≡ 引擎 `returns_matrix[start:end]` 显式构造；`universe.tradable` = buyable&sellable（filter L491），掩码源自 dm 矩阵重索引 → `tradable.loc[date].reindex(stock_codes)` 恒等 | ✅ |
| 5 | §3.4 六条边界 | 早退共用（engine L989-991）/ factor_files 预检（L197-205）/ conditional·hybrid 禁配（Step 4 读码）/ 负权重 fail-fast / 缺列填 0 / tradable 不强制——与实现逐一对应，无遗漏 | ✅ |
| 6 | V1-V8 确定性 | V1 property 协议 isinstance（Step 4 探针 A1）；V2 双文件 hash（getsource 走 `__file__`）+ exec 动态类 TypeError→OSError→`q:`（探针 D1/D2）+ `len==14`；V4 标量键 `pytest.approx` 避开 `cumulative_return_series` 数组布尔歧义（metrics 字典键 L125-151 全部存在）；V5 两引擎同 `tmp_path/out` 写盘互不干扰（断言读内存 trade log）；V8 `caplog` handler 格式化后 `record.message` 可用 | ✅ |
| 7 | 红态逐用例 | V1/V2/V3/V5/V6 `ModuleNotFoundError: core.strategy`；V7 `AttributeError: ... has no attribute 'set_signal'`；V8 `ImportError: get_strategy_registry`；V4 `getattr` 兜底 PASS → **7F/1P 成立** | ✅ |
| 8 | mypy 风险排除 | `ignore_missing_imports=true`（pyproject L114）+ pandas-stubs **未安装**（本机 find_spec 实测 False）→ pandas 调用 Any 化，`frame.loc[date, list] = ndarray` 无风险；`TYPE_CHECKING` 导入 + `from __future__ import annotations` 前向引用成立；`Literal` 注解兼容 py310 目标 | ✅ |
| 9 | 计数链自洽 | pytest 803+8=**811**；black 130·197+2 文件=**132·199**（P-043 同口径先例 +1 测试文件=+1）；mypy 104→**105**（mypy 命令不含 `tests/`，测试文件不计）；AST **22 不变**（`except (OSError, TypeError)` 非 `except Exception`；新文件在 `core/` 内本就不计门禁）；`tests/*.py` 92→**93** | ✅ |
| 10 | 批次依赖与回退 | B3 零 `strategy.py` 依赖（`set_signal`/分支仅涉 pd 与既有符号）→ 声明准确；四批 revert 残留均为零；`agents/` 零 diff 与 M-A 一致 | ✅ |

### 9.2 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S6-P044-1 | P3 | V6 缺 `DirectionalStrategy` 契约输入校验覆盖：非法 `direction` 的 `ValueError`（§3.1 实现 L「未知方向」）无测试 | V6 增补 `pytest.raises(ValueError, match="未知方向")` 一例（§4.2 已落） |
| F-S6-P044-2 | P3 | `code_hash` `q:` 种子对类目标退化为 `qualname\|version\|{}`：类上无 `version`/`param_schema` 属性（仅实例 `meta` 有），同名无版本动态类会同种子碰撞；IMPL 未声明 | §3.1 实现说明补声明行（不改码——实例侧读 `meta` 会循环依赖；`q:` 前缀保障审计可判别，属 D3 已接受语义） |

### 9.3 结论

**Step 6 Review pass（0 P1 / 0 P2 / 2 P3，全部当轮处置）**——IMPL 与 DESIGN D1-D8 及 §10 处置逐项对齐；引擎/注册表锚点经 @`96384f6` 读码核实；关键等价性语义（零权重 ≡ 缺席）由 target_positions.py 读码证实；红态 7F/1P 逐用例成立；mypy/black/AST 计数链经环境实测排除风险。**准予进入 Step 7 CHECKLIST**。

---

## 10. Step 9 实施记录（2026-11-18）

### 10.1 落码

| 文件 | 内容 |
|------|------|
| `core/strategy.py`（新建） | `canonical_json`（L42-44）/ `code_hash`（L47-77，双异常回退）/ `StrategyMeta`（L80-87）/ `StrategyState`（L90-115）/ `MarketView`（L118-125）/ `TargetWeights: TypeAlias`（L34）/ `StrategyFactory`（L37）/ `Strategy` Protocol（L128-135）/ `FactorSignalStrategy`（L138-166）/ `DirectionalStrategy`（L169-219）/ `BacktestAdapter`（L222-275 `state_history`+`signals_frame`）/ `views_from_data`（L277-322） |
| `core/registry.py` | docstring +`Strategy (策略)`（L15）；`_strategy_registry`（L182）；`get_strategy_registry`（L225-230）；`register_strategy`（L341-359） |
| `core/engine_v2.py` | typing +`Literal`（L13）；`_signal_mode` 属性（L184-185）；`set_signal`（L361-387）；`_execute_rebalance` 单分支（L1024-1057，原 try 体逐字缩进进 `else`） |
| `tests/test_p044_strategy_interface.py`（新建） | V1-V8 共 8 函数 |

### 10.2 红 → 绿

- **红**（测试先落）：`7 failed, 1 passed in 8.61s`——与 IMPL §4.3 预测**逐项一致**：V1/V2/V3/V5/V6 `ModuleNotFoundError: No module named 'core.strategy'`、V7 `AttributeError: 'BacktestEngineV2' object has no attribute 'set_signal'`、V8 `ImportError: cannot import name 'get_strategy_registry'`；**V4 护栏 PASS**。
- **绿**（B1→B2→B3 落码后）：`8 passed, 5 warnings in 5.49s`。
- **既有测试零订正**：新文件 + `test_engine_plugins + test_manifest + test_p026 + test_compatibility` → **45 passed**（新 8 + 既有 37）。

### 10.3 门禁（E1）

| 门禁 | 实测 | 判定 |
|------|------|------|
| pytest | **`811 passed, 184 warnings in 52.81s`** | ✅ 803+8 |
| golden | **`13 passed, 798 deselected`** | ✅ 零重录 |
| black | `core tests` **132** / 全仓 **199**（首跑 1 文件待格式化，见 F-S9-P044-2） | ✅ |
| mypy | **`Success: no issues found in 105 source files`** | ✅ |
| AST `except Exception` | 门禁口径 **22**（agents 11 / filter 5 / scripts 2 / batch 2 / strategy 1 / cli 1） | ✅ |
| `tests/*.py` | **93** | ✅ |
| `uv lock --check` | exit **0**（Resolved 148 packages） | ✅ |

### 10.4 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P044-1 | P3 | IMPL §3.1 原写 `TargetWeights = pd.Series` 作注解类型 → mypy **12 errors**（`Variable ... is not valid as a type`；pandas 无 stubs 时裸赋值不被认作别名，连带 `TargetWeights?` 无属性）。**补充事实订正**：IMPL §9.1-8「pandas-stubs 未安装 → 调用 Any 化」结论不完整——`Any` 化确实消除 pandas 属性检查，但**类型别名本身**仍受 `valid-type` 校验 | 改为 `TargetWeights: TypeAlias = pd.Series`（+`TypeAlias` 导入）；运行时 `TargetWeights is pd.Series` 断言不变（V1）；IMPL §3.1 / DESIGN D2 同步订正 |
| F-S9-P044-2 | P3 | black 首跑 `core tests` **1 file would be reformatted**（`tests/test_p044_strategy_interface.py`），计数 131/198 | `black core/strategy.py tests/test_p044_strategy_interface.py` 格式化后复跑 **132·199 unchanged**；复跑新测试 8 passed + 全量 811 passed 确认零语义变化 |
| F-S9-P044-3 | P3（观察） | `core/engine_v2.py` diff 显示 **+96/−31**：其中约 27 行为 `_execute_rebalance` 原 try 体缩进位移（`git diff -w` 语义等价），属设计预期而非逻辑变更 | 声明：C11 以「原 try 体逐字 + 仅缩进」判定；Step 10 用 `git diff -w` 复核 |

### 10.5 结论

**Step 9 TDD pass**——红态 `7 failed, 1 passed` 与预测逐项一致；绿态 8 passed；七门禁全命中目标（811 / 13·798 / 132·199 / 105 / 22 / 93 / uv 0）；`agents/` 与 `SignalTranslator`/`portfolio`/`target_positions`/`rebalance` 零 diff。剩 Step 10 ADD 审计、异构终审与提交（需用户授权）。
