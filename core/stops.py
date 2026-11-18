"""止损止盈状态机（P-045）：逐持仓 bar 判定 + 矩阵级叠加。

纯函数模块（无 I/O、无全局状态）；OHLC 由调用方显式提供（**P-044 ``MarketView`` 零改动**）。
触发 ≠ 成交：触发日只把当日目标权重归 0（该行目标经 T+1 执行链成交，无前视）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Optional

import pandas as pd

if TYPE_CHECKING:
    from core.interfaces import IDataManager

_BAR_KEYS = ("open", "high", "low", "close")


@dataclass(frozen=True)
class StopConfig:
    """止损配置（**全部正数阈值**；与 vbt ``sl_stop``/``tp_stop`` 同号约定）。

    既有 ``core.risk_manager.StopLossConfig``（负号）不复用、不修改。
    """

    stop_loss_pct: Optional[float] = None  # 0.10 = 相对入场价 -10%
    trailing_stop_pct: Optional[float] = None  # 0.08 = 自峰值回撤 8%
    take_profit_pct: Optional[float] = None  # 0.20 = 相对入场价 +20%
    time_stop_days: Optional[int] = None  # 持仓 bar 数上限（建仓日 = 1）
    trailing_activate_pct: Optional[float] = None  # 移动止损激活阈值（PRO tsl_th 对应）

    def __post_init__(self) -> None:
        for name in (
            "stop_loss_pct",
            "trailing_stop_pct",
            "take_profit_pct",
            "trailing_activate_pct",
        ):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} 必须为正数（当前 {value!r}）")
        if self.time_stop_days is not None and self.time_stop_days < 1:
            raise ValueError(f"time_stop_days 必须 >= 1（当前 {self.time_stop_days!r}）")


@dataclass(frozen=True)
class StopBar:
    """单标的单 bar 的 OHLC。"""

    date: pd.Timestamp
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class StopState:
    """持仓止损状态（JSON 安全，可随 ``StrategyState.extras`` 重放）。"""

    entry_price: float
    peak_price: float
    bar_count: int
    entry_date: str  # YYYY-MM-DD

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_price": float(self.entry_price),
            "peak_price": float(self.peak_price),
            "bar_count": int(self.bar_count),
            "entry_date": self.entry_date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StopState":
        return cls(
            entry_price=float(data["entry_price"]),
            peak_price=float(data["peak_price"]),
            bar_count=int(data["bar_count"]),
            entry_date=str(data["entry_date"]),
        )


@dataclass(frozen=True)
class StopDecision:
    """单 bar 判定结果。"""

    action: str  # "hold" | "exit"
    reason: str = ""  # "" | "stop_loss" | "trailing_stop" | "take_profit" | "time_stop"
    severity: float = 1.0


@dataclass(frozen=True)
class StopTrigger:
    """一次触发记录（审计/归因）。"""

    date: pd.Timestamp
    code: str
    reason: str
    entry_date: str
    entry_price: float
    exit_price_ref: float  # 触发日收盘（成交在次日开盘，仅参考）


@dataclass(frozen=True)
class StopResult:
    """矩阵级叠加产物（**禁用 ``==``**：含 DataFrame/tuple/dict，逐字段断言）。"""

    weights: pd.DataFrame
    triggers: tuple[StopTrigger, ...]
    states: dict[str, dict[str, Any]]
    deferred: int


class StopEngine:
    """无状态止损状态机：``update`` 为纯函数，可并发复用。"""

    def __init__(self, config: StopConfig) -> None:
        self.config = config

    def update(self, state: Optional[StopState], bar: StopBar) -> tuple[StopState, StopDecision]:
        """推进一个 bar。

        ``state is None`` → 建仓（不判触发）；否则按 **SL → trailing → TP → time**
        优先级判定（DESIGN D6）。bar 内 gap/盘中均归入 ``stop_loss``；
        移动止损用**更新后峰值**（同 bar 可「激活即触发」）。
        """
        cfg = self.config
        if state is None:
            new_state = StopState(
                entry_price=float(bar.close),
                peak_price=float(max(bar.high, bar.close)),
                bar_count=1,
                entry_date=bar.date.strftime("%Y-%m-%d"),
            )
            return new_state, StopDecision(action="hold")

        peak = max(state.peak_price, bar.high)
        count = state.bar_count + 1
        entry = state.entry_price
        updated = StopState(
            entry_price=entry,
            peak_price=peak,
            bar_count=count,
            entry_date=state.entry_date,
        )

        if cfg.stop_loss_pct is not None:
            threshold = entry * (1.0 - cfg.stop_loss_pct)
            if bar.open <= threshold or bar.low <= threshold:
                return updated, StopDecision(action="exit", reason="stop_loss")

        if cfg.trailing_stop_pct is not None:
            activated = cfg.trailing_activate_pct is None or peak >= entry * (
                1.0 + cfg.trailing_activate_pct
            )
            if activated and bar.low <= peak * (1.0 - cfg.trailing_stop_pct):
                return updated, StopDecision(action="exit", reason="trailing_stop")

        if cfg.take_profit_pct is not None:
            if bar.high >= entry * (1.0 + cfg.take_profit_pct):
                return updated, StopDecision(action="exit", reason="take_profit")

        if cfg.time_stop_days is not None and count >= cfg.time_stop_days:
            return updated, StopDecision(action="exit", reason="time_stop")

        return updated, StopDecision(action="hold")


def ohlc_from_data(dm: "IDataManager") -> dict[str, pd.DataFrame]:
    """从数据管理器组装四键 OHLC（``raw`` 口径，与引擎成交价一致）。"""
    return {key: dm.get_adj_price(key, "raw") for key in _BAR_KEYS}


def apply_stops(
    targets: pd.DataFrame,
    bars: Mapping[str, pd.DataFrame],
    config: StopConfig,
    *,
    tradable: Optional[pd.DataFrame] = None,
) -> StopResult:
    """矩阵级止损叠加：触发日把目标权重归 0（只减不增、不重归一）。

    严格校验（DESIGN D7）：四键缺失 / bars 在 targets 网格上有缺失值 /
    targets 含 NaN → ``ValueError``。不可交易日的退出延迟（``deferred``），
    下一可交易日重新判定。退出日**禁止同日重建**（``continue``，DESIGN D7 注）。
    """
    for key in _BAR_KEYS:
        if key not in bars:
            raise ValueError(f"bars 缺少键: {key}（必须含 {list(_BAR_KEYS)}）")
    frames = {
        key: bars[key].reindex(index=targets.index, columns=targets.columns) for key in _BAR_KEYS
    }
    for key, frame in frames.items():
        if bool(frame.isna().to_numpy().any()):
            raise ValueError(f"bars[{key!r}] 在 targets 网格上存在缺失值")
    if bool(targets.isna().to_numpy().any()):
        raise ValueError("targets 不允许含 NaN")

    tradable_mask: Optional[pd.DataFrame] = None
    if tradable is not None:
        tradable_mask = (
            tradable.reindex(index=targets.index, columns=targets.columns)
            .fillna(False)
            .astype(bool)
        )

    engine = StopEngine(config)
    open_m, high_m, low_m, close_m = (frames[key] for key in _BAR_KEYS)
    weights = targets.astype(float).copy()
    states: dict[str, StopState] = {}
    triggers: list[StopTrigger] = []
    deferred = 0

    for date in targets.index:
        for code in targets.columns:
            weight = float(targets.at[date, code])
            bar = StopBar(
                date=date,
                open=float(open_m.at[date, code]),
                high=float(high_m.at[date, code]),
                low=float(low_m.at[date, code]),
                close=float(close_m.at[date, code]),
            )
            state = states.get(code)

            if state is not None:
                new_state, decision = engine.update(state, bar)
                if decision.action == "exit":
                    allowed = True if tradable_mask is None else bool(tradable_mask.at[date, code])
                    if allowed:
                        weights.at[date, code] = 0.0
                        triggers.append(
                            StopTrigger(
                                date=date,
                                code=str(code),
                                reason=decision.reason,
                                entry_date=state.entry_date,
                                entry_price=state.entry_price,
                                exit_price_ref=bar.close,
                            )
                        )
                        del states[code]
                        continue
                    deferred += 1
                    states[code] = new_state
                    continue
                if weight <= 0.0:
                    del states[code]
                else:
                    states[code] = new_state
                continue

            if weight > 0.0:
                states[code] = engine.update(None, bar)[0]

    return StopResult(
        weights=weights,
        triggers=tuple(triggers),
        states={code: state.to_dict() for code, state in states.items()},
        deferred=deferred,
    )
