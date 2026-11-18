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
