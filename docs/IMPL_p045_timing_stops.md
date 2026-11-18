# IMPL：P-045 择时原语与止损状态机（timing + stops）

> **批次**: P-045 · **Step 5 实施规划** · 日期 2026-11-18
> **判档**: **T1**（新建 `core/timing.py` + `core/stops.py` + `tests/` + 2 golden case）
> **上游**: [DESIGN_p045](DESIGN_p045_timing_stops.md)（D1-D9 / §2.0 上游裁决 / §10 Step 4 pass：8 P3 当轮处置）
> **代码时点**: HEAD `0482881`（P-044 关闭；行号为该时点）
> **基座**: DeepSeek-V4.1-Flash（Step 6 Review 须异构 GLM-5.3-Flash；U-P045-5 于 Step 10 终审闭合）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 落地批次 | B1 `core/timing.py` → B2 `core/stops.py` → B3 测试 + golden + 文档 |
| 行为变更 | **零**（纯新增模块；不接线引擎、不改 `config`/`engineering`/`agents`） |
| 新增能力 | ① 信号原语（交叉/仲裁/持仓状态机/权重/gate）；② 止损止盈状态机 + 矩阵级叠加（OHLC 显式载体） |
| 不触碰 | `core/engine_v2.py` / `core/strategy.py` / `core/risk_manager.py` / `core/config.py` / `core/target_positions.py` / `core/execution_policy.py` / `filter/` / `agents/` / `tests/golden/G*.json` / `tests/_golden_cases.py` / `tests/test_golden_baseline.py` |
| 零预填 | §9（Step 6）与 §10（Step 9）为占位，实测后回填 |

---

## 2. 任务拆解

| 批 | 文件 | 改动 |
|----|------|------|
| **B1** | `core/timing.py`（新建） | `crossed_above` / `crossed_below` / `SignalSet` / `resolve_conflicts` / `holdings_from_signals` / `weights_from_holdings` / `apply_timing` |
| **B2** | `core/stops.py`（新建） | `StopConfig` / `StopBar` / `StopState` / `StopDecision` / `StopTrigger` / `StopResult` / `StopEngine` / `ohlc_from_data` / `apply_stops` |
| **B3** | `tests/test_p045_timing_stops.py`（新建） | V1-V8（8 函数）+ `test_golden_p045_s1` / `test_golden_p045_s2`（2 函数） |
| **B3** | `tests/golden/p045/P045_S1.json` / `P045_S2.json`（新建） | 规格锁定期望（手工推导，见 §4.4）；**子目录隔离**（F-S9-P045-1） |
| **B3** | `scripts/external_benchmark/verify_p045.py`（新建） | vectorbt 对拍（隔离 venv）：触发判定序列逐值比对 + 豁免登记 + 差异闭式声明（**F-S6-P045-1 增补**，见 §4.6） |

依赖：B2 无 B1 依赖（`stops` 不 import `timing`）；B3 依赖 B1/B2。三批可独立 revert。

---

## 3. 接口签名与实现规格

### 3.1 B1：`core/timing.py`（新建，完整代码）

```python
"""择时信号原语（P-045）：交叉检测 / 冲突仲裁 / 持仓状态机 / 权重生成 / 目标 gate。

纯函数模块（无 I/O、无全局状态）；**不 import ``core.strategy``**（避免与 P-044 循环）。
边界（DESIGN §4）：不重归一 / short 侧仅类型位（P-050） / 行和 <1 合法。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


def crossed_above(series: pd.Series, level: float) -> pd.Series:
    """上穿检测：当前 > level 且前值 <= level。

    首行（前值缺失）与任一 NaN 参与比较时恒 False（DESIGN D3）。
    """
    prev = series.shift(1)
    return (series > level) & (prev <= level)


def crossed_below(series: pd.Series, level: float) -> pd.Series:
    """下穿检测：当前 < level 且前值 >= level（NaN 语义同 ``crossed_above``）。"""
    prev = series.shift(1)
    return (series < level) & (prev >= level)


@dataclass(frozen=True)
class SignalSet:
    """四掩码信号集合（short 两侧为 P-050 类型位，本批全流程忽略）。"""

    entries_long: pd.DataFrame
    exits_long: pd.DataFrame
    entries_short: Optional[pd.DataFrame] = None
    exits_short: Optional[pd.DataFrame] = None

    def __post_init__(self) -> None:
        if not self.entries_long.index.equals(self.exits_long.index):
            raise ValueError("entries_long 与 exits_long 的 index 必须完全一致")
        if not self.entries_long.columns.equals(self.exits_long.columns):
            raise ValueError("entries_long 与 exits_long 的 columns 必须完全一致")


def _as_bool(frame: pd.DataFrame) -> pd.DataFrame:
    """NaN → False 的布尔归一（不修改入参）。"""
    return frame.fillna(False).astype(bool)


def resolve_conflicts(signals: SignalSet) -> SignalSet:
    """冲突仲裁：同日同时 entry+exit → **exit 优先**（entry 被抵消）。"""
    entries = _as_bool(signals.entries_long)
    exits = _as_bool(signals.exits_long)
    return SignalSet(
        entries_long=entries & ~exits,
        exits_long=exits,
        entries_short=signals.entries_short,
        exits_short=signals.exits_short,
    )


def holdings_from_signals(signals: SignalSet) -> pd.DataFrame:
    """持仓状态机（向量化）：entry 置 1、exit 置 0、其余 ffill；同日冲突 exit 优先。"""
    entries = _as_bool(signals.entries_long)
    exits = _as_bool(signals.exits_long)
    raw = pd.DataFrame(np.nan, index=entries.index, columns=entries.columns)
    raw = raw.mask(exits, 0.0)
    raw = raw.mask(entries & ~exits, 1.0)
    return raw.ffill().fillna(0.0).astype(bool)


def weights_from_holdings(holdings: pd.DataFrame, *, mode: str = "equal") -> pd.DataFrame:
    """持仓 → 等权目标权重（空持仓行全 0；**不重归一**，行和 ∈ {0, 1}）。"""
    if mode != "equal":
        raise ValueError(f"未知权重模式: {mode}（当前仅支持 equal）")
    held = _as_bool(holdings)
    counts = held.sum(axis=1).astype(float)
    weights = held.astype(float).div(counts.replace(0.0, np.nan), axis=0)
    return weights.fillna(0.0)


def apply_timing(targets: pd.DataFrame, holdings: pd.DataFrame) -> pd.DataFrame:
    """择时 gate：``holdings=False`` 处目标权重归 0，其余逐值保留（不重归一）。

    注意 ``DataFrame.reindex`` 只接受 1-2 个位置参数，必须用 keyword 形式
    （DESIGN §10 F-S4-P045-1 实测订正）。
    """
    aligned = _as_bool(holdings.reindex(index=targets.index, columns=targets.columns))
    return targets.where(aligned, 0.0)
```

### 3.2 B2：`core/stops.py`（新建，完整代码）

```python
"""止损止盈状态机（P-045）：逐持仓 bar 判定 + 矩阵级叠加。

纯函数模块（无 I/O、无全局状态）；OHLC 由调用方显式提供（**P-044 ``MarketView`` 零改动**）。
触发 ≠ 成交：触发日只把次日目标权重归 0，成交仍由既有链路 T+1 开盘完成（无前视）。
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

    stop_loss_pct: Optional[float] = None          # 0.10 = 相对入场价 -10%
    trailing_stop_pct: Optional[float] = None      # 0.08 = 自峰值回撤 8%
    take_profit_pct: Optional[float] = None        # 0.20 = 相对入场价 +20%
    time_stop_days: Optional[int] = None           # 持仓 bar 数上限（建仓日 = 1）
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

    action: str          # "hold" | "exit"
    reason: str = ""     # "" | "stop_loss" | "trailing_stop" | "take_profit" | "time_stop"
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

    def update(
        self, state: Optional[StopState], bar: StopBar
    ) -> tuple[StopState, StopDecision]:
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
    下一可交易日重新判定。
    """
    for key in _BAR_KEYS:
        if key not in bars:
            raise ValueError(f"bars 缺少键: {key}（必须含 {list(_BAR_KEYS)}）")
    frames = {
        key: bars[key].reindex(index=targets.index, columns=targets.columns)
        for key in _BAR_KEYS
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
                    allowed = (
                        True if tradable_mask is None else bool(tradable_mask.at[date, code])
                    )
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
```

**实现要点**

- `StopResult` 与 `SignalSet` 含 DataFrame → **禁用 `==`**（DESIGN §10 F-S4-P045-2 实测）；测试用 `assert_frame_equal` / 逐字段。
- `weights.at[date, code] = 0.0` 为标量写；因状态机顺序依赖（同一日先判退出、再建仓），不做全矩阵向量化。
- `apply_stops` 的单日单标的循环 = `D × N` 次 `update`；生产规模（1460 × 数十持仓）约万级调用。

---

## 4. 测试规格（`tests/test_p045_timing_stops.py`，V1-V8 + G1/G2）

### 4.1 文件头与夹具

```python
"""P-045：择时原语与止损状态机（V1-V8 + G1/G2）。

红态设计：核心符号一律函数内导入 → 逐用例失败而非收集期 error。
G1/G2 为**规格锁定** golden（期望值由 DESIGN/IMPL 手工推导，非实现录制）。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DATES = pd.bdate_range("2024-01-02", periods=5)
GOLDEN_DIR = Path(__file__).parent / "golden" / "p045"  # F-S9-P045-1：隔离子目录，P-013 harness 零 diff
```

### 4.2 V1-V8 完整代码

```python
def test_v1_crossed_above_below():
    """S2 / D3：交叉检测与 NaN 语义。"""
    from core.timing import crossed_above, crossed_below

    series = pd.Series([np.nan, 1.0, 0.5, 2.0, np.nan, 3.0])
    assert crossed_above(series, 1.0).tolist() == [False, False, False, True, False, False]
    assert crossed_below(series, 1.0).tolist() == [False, False, True, False, False, False]

    flat = pd.Series([1.0, 1.0, 1.0])
    assert not crossed_above(flat, 1.0).any()
    assert not crossed_below(flat, 1.0).any()


def test_v2_conflicts_and_holdings():
    """S3 / D4：同日冲突 exit 优先；持仓状态机 ffill 与重建。"""
    from core.timing import SignalSet, holdings_from_signals, resolve_conflicts

    codes = ["A", "B"]
    entries = pd.DataFrame(False, index=DATES, columns=codes)
    exits = pd.DataFrame(False, index=DATES, columns=codes)
    entries.iloc[0, 0] = True      # A: d1 entry
    exits.iloc[3, 0] = True        # A: d4 exit
    entries.iloc[4, 0] = True      # A: d5 re-entry
    entries.iloc[1, 1] = True      # B: d2 entry
    exits.iloc[1, 1] = True        # B: 同日 entry+exit

    resolved = resolve_conflicts(SignalSet(entries_long=entries, exits_long=exits))
    assert not resolved.entries_long.iloc[1, 1]

    holdings = holdings_from_signals(SignalSet(entries_long=entries, exits_long=exits))
    assert holdings["A"].tolist() == [True, True, True, False, True]
    assert holdings["B"].tolist() == [False, False, False, False, False]

    with pytest.raises(ValueError, match="index"):
        SignalSet(entries_long=entries, exits_long=exits.iloc[:-1])


def test_v3_weights_from_holdings():
    """S4 / D4：等权、空持仓全 0、行和 ∈ {0,1}、非法 mode。"""
    from core.timing import weights_from_holdings

    holdings = pd.DataFrame(
        [[True, True, False], [False, False, False], [True, False, False]],
        index=DATES[:3],
        columns=["A", "B", "C"],
    )
    weights = weights_from_holdings(holdings)
    assert weights.iloc[0].tolist() == [0.5, 0.5, 0.0]
    assert weights.iloc[1].tolist() == [0.0, 0.0, 0.0]
    assert weights.iloc[2].tolist() == [1.0, 0.0, 0.0]
    assert set(weights.sum(axis=1).round(12)) <= {0.0, 1.0}

    with pytest.raises(ValueError, match="未知权重模式"):
        weights_from_holdings(holdings, mode="risk_parity")


def test_v4_apply_timing_gate():
    """S4 / D4：gate 归零且**不重归一**（F-S4-P045-1 reindex keyword）。"""
    from core.timing import apply_timing

    targets = pd.DataFrame([[0.5, 0.5], [0.6, 0.0]], index=DATES[:2], columns=["A", "B"])
    holdings = pd.DataFrame(True, index=DATES[:2], columns=["A", "B"])
    holdings.iloc[1, 1] = False

    gated = apply_timing(targets, holdings)
    assert gated.sum(axis=1).tolist() == [1.0, 0.6]
    assert gated.iloc[1, 0] == 0.6


def test_v5_fixed_stop_loss():
    """S5-S8 / D6：建仓 state、gap 触发、盘中触发、未触发。"""
    from core.stops import StopBar, StopConfig, StopEngine, StopState

    engine = StopEngine(StopConfig(stop_loss_pct=0.10))
    state, decision = engine.update(None, StopBar(DATES[0], 100.0, 101.0, 99.0, 100.0))
    assert decision.action == "hold"
    assert state == StopState(
        entry_price=100.0, peak_price=101.0, bar_count=1, entry_date="2024-01-02"
    )

    _, gap = engine.update(state, StopBar(DATES[1], 89.0, 90.0, 88.0, 89.0))
    assert (gap.action, gap.reason) == ("exit", "stop_loss")

    _, intraday = engine.update(state, StopBar(DATES[1], 95.0, 96.0, 89.0, 90.0))
    assert (intraday.action, intraday.reason) == ("exit", "stop_loss")

    updated, hold = engine.update(state, StopBar(DATES[1], 99.0, 100.0, 95.0, 96.0))
    assert hold.action == "hold"
    assert updated.bar_count == 2 and updated.peak_price == 101.0


def test_v6_trailing_and_take_profit_priority():
    """S5-S8 / D6：移动止损激活即触发、未激活不触发、SL 优先于 TP。"""
    from core.stops import StopBar, StopConfig, StopEngine

    engine = StopEngine(StopConfig(trailing_stop_pct=0.08, trailing_activate_pct=0.05))
    state, _ = engine.update(None, StopBar(DATES[0], 50.0, 50.5, 49.5, 50.0))
    state, hold1 = engine.update(state, StopBar(DATES[1], 51.0, 53.0, 50.8, 52.0))
    assert hold1.action == "hold"
    state, hold2 = engine.update(state, StopBar(DATES[2], 52.0, 52.5, 49.0, 49.5))
    assert hold2.action == "hold"
    _, trailing = engine.update(state, StopBar(DATES[3], 49.5, 50.0, 47.0, 48.0))
    assert (trailing.action, trailing.reason) == ("exit", "trailing_stop")

    engine2 = StopEngine(StopConfig(trailing_stop_pct=0.08, trailing_activate_pct=0.5))
    state2, _ = engine2.update(None, StopBar(DATES[0], 50.0, 50.5, 49.5, 50.0))
    _, hold3 = engine2.update(state2, StopBar(DATES[1], 51.0, 53.0, 47.0, 52.0))
    assert hold3.action == "hold"

    engine3 = StopEngine(StopConfig(stop_loss_pct=0.10, take_profit_pct=0.20))
    state3, _ = engine3.update(None, StopBar(DATES[0], 100.0, 101.0, 99.0, 100.0))
    _, both = engine3.update(state3, StopBar(DATES[1], 102.0, 122.0, 88.0, 100.0))
    assert (both.action, both.reason) == ("exit", "stop_loss")

    engine4 = StopEngine(StopConfig(stop_loss_pct=0.10, take_profit_pct=0.20))
    state4, _ = engine4.update(None, StopBar(DATES[0], 100.0, 101.0, 99.0, 100.0))
    _, tp = engine4.update(state4, StopBar(DATES[1], 105.0, 125.0, 99.0, 120.0))
    assert (tp.action, tp.reason) == ("exit", "take_profit")


def test_v7_time_stop_and_deferred_exit():
    """S9 / D6-D7：时间止损、不可交易日延迟、deferred 计数。"""
    from core.stops import StopConfig, apply_stops

    dates = DATES[:4]
    codes = ["X", "Y"]
    targets = pd.DataFrame(0.5, index=dates, columns=codes)
    flat = pd.DataFrame(100.0, index=dates, columns=codes)
    bars = {
        "open": flat.copy(),
        "high": flat + 1.0,
        "low": flat - 1.0,
        "close": flat.copy(),
    }
    tradable = pd.DataFrame(True, index=dates, columns=codes)
    tradable.loc[dates[1], "Y"] = False

    result = apply_stops(targets, bars, StopConfig(time_stop_days=2), tradable=tradable)

    assert result.weights["X"].tolist() == [0.5, 0.0, 0.5, 0.0]
    assert result.weights["Y"].tolist() == [0.5, 0.5, 0.0, 0.5]
    assert result.deferred == 1
    assert [t.reason for t in result.triggers] == ["time_stop"] * 3


def test_v8_apply_stops_end_to_end():
    """D7 / I8-I9：多标的端到端、状态往返、行和只减不增、三类 fail-fast。"""
    from core.stops import StopConfig, StopState, apply_stops

    codes = ["A", "B"]
    targets = pd.DataFrame(0.5, index=DATES, columns=codes)
    close = pd.DataFrame(
        [[100.0, 50.0], [96.0, 51.0], [90.0, 50.0], [89.0, 49.0], [89.0, 48.0]],
        index=DATES,
        columns=codes,
    )
    open_ = close.shift(1).fillna(close.iloc[0])
    high = close + 1.0
    low = close - 1.0
    bars = {"open": open_, "high": high, "low": low, "close": close}

    result = apply_stops(targets, bars, StopConfig(stop_loss_pct=0.10))
    assert len(result.triggers) == 1
    trigger = result.triggers[0]
    assert (trigger.code, trigger.reason) == ("A", "stop_loss")
    assert trigger.entry_date == "2024-01-02"
    assert trigger.entry_price == pytest.approx(100.0)
    assert trigger.exit_price_ref == pytest.approx(90.0)
    assert result.weights.loc[DATES[2], "A"] == 0.0
    assert result.weights.loc[DATES[3], "A"] == 0.5

    for payload in result.states.values():
        assert StopState.from_dict(payload).to_dict() == payload
    assert (result.weights.sum(axis=1) <= targets.sum(axis=1) + 1e-12).all()

    with pytest.raises(ValueError, match="缺少键"):
        apply_stops(targets, {"open": bars["open"]}, StopConfig(stop_loss_pct=0.10))
    broken = {key: value.copy() for key, value in bars.items()}
    broken["close"].iloc[0, 0] = np.nan
    with pytest.raises(ValueError, match="缺失值"):
        apply_stops(targets, broken, StopConfig(stop_loss_pct=0.10))
    bad_targets = targets.copy()
    bad_targets.iloc[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        apply_stops(bad_targets, bars, StopConfig(stop_loss_pct=0.10))

    with pytest.raises(ValueError, match="正数"):
        StopConfig(stop_loss_pct=0.0)
    with pytest.raises(ValueError, match="time_stop_days"):
        StopConfig(time_stop_days=0)
```

### 4.3 G1/G2 golden 测试函数

```python
def _run_golden(name: str):
    from core.stops import StopConfig, apply_stops

    payload = json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))
    dates = pd.DatetimeIndex(payload["targets"]["dates"])
    codes = payload["targets"]["codes"]
    targets = pd.DataFrame(payload["targets"]["values"], index=dates, columns=codes)
    bars = {
        key: pd.DataFrame(payload["bars"][key], index=dates, columns=codes)
        for key in ("open", "high", "low", "close")
    }
    tradable = None
    if payload["tradable"] is not None:
        tradable = pd.DataFrame(payload["tradable"], index=dates, columns=codes).astype(bool)

    result = apply_stops(targets, bars, StopConfig(**payload["config"]), tradable=tradable)
    expected = payload["expected"]

    pd.testing.assert_frame_equal(
        result.weights,
        pd.DataFrame(expected["weights"], index=dates, columns=codes),
        check_dtype=False,
    )
    got_triggers = [
        {
            "date": trigger.date.strftime("%Y-%m-%d"),
            "code": trigger.code,
            "reason": trigger.reason,
            "entry_date": trigger.entry_date,
            "entry_price": trigger.entry_price,
            "exit_price_ref": trigger.exit_price_ref,
        }
        for trigger in result.triggers
    ]
    assert got_triggers == expected["triggers"]
    assert result.deferred == expected["deferred"]
    assert result.states == expected["states"]


def test_golden_p045_s1():
    """G1：固定止损 + 移动止损 + 止盈优先级（规格锁定）。"""
    _run_golden("P045_S1")


def test_golden_p045_s2():
    """G2：时间止损 + 跌停延迟退出（规格锁定）。"""
    _run_golden("P045_S2")
```

### 4.4 golden 期望值（手工推导，§4.4 为准）

**`P045_S1`（固定 + 移动 + 止盈优先级）**

- 日期：`2024-01-02..01-08`（5 日）；标的 `A/B/C`；目标权重 `0.5/0.3/0.2` 每日恒定
- `config`：`stop_loss_pct=0.10`、`trailing_stop_pct=0.08`、`take_profit_pct=0.20`、`trailing_activate_pct=0.05`

| 日期 | A O/H/L/C | B O/H/L/C | C O/H/L/C |
|------|-----------|-----------|-----------|
| 01-02 | 100/101/99/100 | 50/50.5/49.5/50 | 100/101/99/100 |
| 01-03 | 99/100/95/96 | 51/53/50.8/52 | 102/122/88/100 |
| 01-04 | 95/96/89/90 | 52/52.5/49/49.5 | 100/101/99/100 |
| 01-05 | 90/91/88/89 | 49.5/50/47/48 | 100/101/99/100 |
| 01-08 | 89/90/88/89 | 48/49/47/48 | 100/101/99/100 |

推导：
- **A**：01-02 建仓 `entry=100/peak=101`；01-03 未触发（peak 101 < 105 激活线，low 95 > 90）；**01-04 low 89 ≤ 90 → stop_loss**（`exit_price_ref=90`）；01-05 权重 >0 → 重建 `entry=89/peak=91`；01-08 未触发。
- **B**：01-02 建仓 `entry=50/peak=50.5`；01-03 peak 53 ≥ 52.5 **激活**但 low 50.8 > 48.76；01-04 low 49 > 48.76；**01-05 low 47 ≤ 48.76 → trailing_stop**（ref=48）；01-08 重建 `entry=48/peak=49`。
- **C**：01-02 建仓 `entry=100/peak=101`；**01-03 low 88 ≤ 90 且 high 122 ≥ 120 → stop_loss 优先**（ref=100，验证 F-S4-P045-4 优先级链）；01-04 重建 `entry=100/peak=101`；01-05/01-08 未触发。

期望 `weights`：

| 日期 | A | B | C |
|------|---|---|---|
| 01-02 | 0.5 | 0.3 | 0.2 |
| 01-03 | 0.5 | 0.3 | **0.0** |
| 01-04 | **0.0** | 0.3 | 0.2 |
| 01-05 | 0.5 | **0.0** | 0.2 |
| 01-08 | 0.5 | 0.3 | 0.2 |

期望 `triggers`（按 (date, code) 排序）：

```json
[
  {"date": "2024-01-03", "code": "C", "reason": "stop_loss",
   "entry_date": "2024-01-02", "entry_price": 100.0, "exit_price_ref": 100.0},
  {"date": "2024-01-04", "code": "A", "reason": "stop_loss",
   "entry_date": "2024-01-02", "entry_price": 100.0, "exit_price_ref": 90.0},
  {"date": "2024-01-05", "code": "B", "reason": "trailing_stop",
   "entry_date": "2024-01-02", "entry_price": 50.0, "exit_price_ref": 48.0}
]
```

期望 `states`（末日）：

```json
{
  "A": {"entry_price": 89.0, "peak_price": 91.0, "bar_count": 2, "entry_date": "2024-01-05"},
  "B": {"entry_price": 48.0, "peak_price": 49.0, "bar_count": 1, "entry_date": "2024-01-08"},
  "C": {"entry_price": 100.0, "peak_price": 101.0, "bar_count": 3, "entry_date": "2024-01-04"}
}
```

`deferred = 0`；`tradable = null`。

**`P045_S2`（时间止损 + 跌停延迟）**

- 日期/标的：同上；目标权重 `X=0.6 / Y=0.4` 每日恒定
- `config`：`time_stop_days=2`（其余字段 null）
- 价格：全部 `O=100 / H=101 / L=99 / C=100`
- `tradable`：仅 `2024-01-03` 的 `Y` 为 `false`（跌停不可卖）

推导：X 在 01-02 建仓（count1）→ 01-03 count2 **触发**；01-04 重建 → 01-05 count2 **触发**；01-08 重建。Y 在 01-02 建仓 → 01-03 count2 触发但**不可交易 → 保持 + deferred=1** → 01-04 count3 触发并退出；01-05 重建 → 01-08 count2 **触发**。

期望 `weights`：

| 日期 | X | Y |
|------|---|---|
| 01-02 | 0.6 | 0.4 |
| 01-03 | **0.0** | 0.4 |
| 01-04 | 0.6 | **0.0** |
| 01-05 | **0.0** | 0.4 |
| 01-08 | 0.6 | **0.0** |

期望 `triggers`：

```json
[
  {"date": "2024-01-03", "code": "X", "reason": "time_stop",
   "entry_date": "2024-01-02", "entry_price": 100.0, "exit_price_ref": 100.0},
  {"date": "2024-01-04", "code": "Y", "reason": "time_stop",
   "entry_date": "2024-01-02", "entry_price": 100.0, "exit_price_ref": 100.0},
  {"date": "2024-01-05", "code": "X", "reason": "time_stop",
   "entry_date": "2024-01-04", "entry_price": 100.0, "exit_price_ref": 100.0},
  {"date": "2024-01-08", "code": "Y", "reason": "time_stop",
   "entry_date": "2024-01-05", "entry_price": 100.0, "exit_price_ref": 100.0}
]
```

期望 `states`：`{"X": {"entry_price": 100.0, "peak_price": 101.0, "bar_count": 1, "entry_date": "2024-01-08"}}`；`deferred = 1`。

**JSON schema**（两份同构）：

```json
{
  "schema_version": "1.0",
  "case_id": "P045_S1",
  "git_commit": "<落码时填充（非空即可）>",
  "kind": "stops",
  "config": {"stop_loss_pct": 0.10, "trailing_stop_pct": 0.08,
             "take_profit_pct": 0.20, "trailing_activate_pct": 0.05,
             "time_stop_days": null},
  "targets": {"dates": [...], "codes": ["A","B","C"], "values": [[...]]},
  "bars": {"open": [[...]], "high": [[...]], "low": [[...]], "close": [[...]]},
  "tradable": null,
  "expected": {"weights": [[...]], "triggers": [...], "deferred": 0, "states": {...}},
  "tolerance": {"rtol": 1e-12, "atol": 1e-12}
}
```

### 4.5 红态预期（Step 9 首跑）

| 结果 | 用例 | 原因 |
|------|------|------|
| FAIL | V1-V8 | `ModuleNotFoundError: No module named 'core.timing'` / `'core.stops'` |
| FAIL | G1/G2 | 同上（`_run_golden` 内导入） |

**聚合预测**：**`10 failed`**（0 passed）。**实测 `10 failed in 0.75s`**（全 `ModuleNotFoundError`，§10）。

### 4.6 vectorbt 对拍（F-S6-P045-1 增补，I3 执行载体）

**任务**：新增 `scripts/external_benchmark/verify_p045.py`（沿用 P-015 三态词表 pass/fail/waiver），在隔离 venv（`.venv-vbt`，`vectorbt==1.2.0`）运行：

1. **共同输入** = `P045_S1` 的价格路径（同一 OHLC 矩阵 + 阈值 `sl_stop=0.10`/`tp_stop=0.20`/`sl_trail=True`）；
2. **本仓端**：`apply_stops(targets, bars, StopConfig(stop_loss_pct=0.10, take_profit_pct=0.20, trailing_stop_pct=0.08))` → 触发序列（date, code, reason）；
3. **vbt 端**：`Portfolio.from_signals(entries, exits, price=close, open/open/high/low 可用时传入, sl_stop=0.10, sl_trail=True, tp_stop=0.20, fees=0)` → `trades` 的止损类退出记录（exit_reason → reason 映射：StopLoss→stop_loss / TakeProfit→take_profit / TrailStop→trailing_stop）；
4. **断言**：双方**触发判定序列**（date, code, reason）逐值一致（I3 收窄口径，F-S2-P045-1）；
5. **豁免登记（waiver）**：激活阈值（免费版无 `tsl_th` 对应，F-D3-P045-4）、成交价/NAV 差异（vbt 同 bar 成交 vs 本仓 T+1 开盘）→ 按 P-015 恒等式方法论在输出中**闭式声明**；
6. **输出**：对拍读数（E2）写入 `docs/APPENDIX_p045_external_calibration.md` 新增 §（或独立附录段落），验收出口 = 脚本 exit 0 + 附录记录。

> 实施细节（vbt `from_signals` 的 OHLC 参数支持面）以 Step 9 实测为准：免费版不支持处一律 `waiver` 登记，不得静默缩窄断言。

---

## 5. 低效排除表

| # | 低效操作 | 排除方式 | 判据 |
|---|----------|----------|------|
| 1 | 状态机向量化 | 逐日逐标的顺序依赖（同日先退出再建仓），`D×N` 约万级 `update`（<10µs/次）；不引入 numba（CI numpy 三口径类型桩风险，P-036 教训） | 5 日 × 3 标的单测 <50ms |
| 2 | `bars` 反复 reindex | 每次 `apply_stops` 仅 4 次整表 reindex（入口一次），不在逐日循环内 | 循环体内无 reindex |
| 3 | 全矩阵掩码写权重 | 触发为稀疏事件，`weights.at` 标量写 O(1)；全矩阵掩码需额外状态机向量化，收益 < 复杂度 | 触发次数 = `len(triggers)` |
| 4 | golden 录制脚本 | 不新建 `scripts/record_golden_p045.py`（规格锁定 JSON 手工推导，避免「实现输出自证」） | 无新增 script |
| 5 | 测试重复构造 DataFrame | 单文件内联小矩阵（5×2/5×3），不引入 session 夹具 | 10 用例合计 <3s |

---

## 6. 兼容性与版本

| 项 | 结论 |
|----|------|
| Python | `>=3.10`（`dataclass` / `typing.Optional` / `Mapping` 均 stdlib） |
| 新增依赖 | **0**（仅 `pandas` / `numpy`，已在依赖内） |
| `core/timing.py` / `core/stops.py` | 纯新增；无 I/O、无全局单例、无 import 副作用 |
| 既有模块 | `engine_v2` / `strategy` / `risk_manager` / `config` / `target_positions` / `execution_policy` / `filter` / `agents` **零 diff** |
| 既有 golden | `G1..G7.json` / `_golden_cases.py` / `test_golden_baseline.py` **零 diff**（跨 schema 隔离） |
| 产物 | 无新增运行产物；golden JSON 为测试资产 |

---

## 7. 门禁终态（Step 9 目标）

| 门禁 | 现值 | 目标 | 说明 |
|------|------|------|------|
| pytest | 811 | **821** | +10（V1-V8 + G1/G2） |
| golden | 13 | **15** | +2；既有 13 零重录 |
| black（`core tests` / 全仓） | 132·199 | **135·203** | +2 源 +1 测试 +1 对拍脚本（F-D3-P045-2 / **F-S9-P045-5**） |
| mypy | 105 | **108** | +2 模块 +1 对拍脚本（命令含 `scripts/`；F-S10-P045-1 订正） |
| AST `except Exception` | 22 | **22** | 新模块无 try/except |
| `tests/*.py` | 93 | **94** | +1 测试文件 |
| 对拍 | —（新建） | **verify_p045 exit 0** | 隔离 venv；触发序列逐值 + 豁免显式（I3，F-S6-P045-1） |
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
| B1 | 删除 `core/timing.py` | 无（纯新增） |
| B2 | 删除 `core/stops.py` | 无（纯新增） |
| B3 | 删除测试文件 + 2 个 golden JSON | 无 |

三批互不依赖既有文件，无数据迁移与产物兼容问题。

---

## 9. Step 6 实施 Review

- **执行时点**: IMPL §1-§8 完稿后单独执行；本节占位后回填，未与正文同一次写入（零预填）。
- **审查者**: GLM-5.3-Flash（异构基座，≠ 作者 DeepSeek-V4.1-Flash，**RULE-5 异构成立**）；U-P045-5 异构链维持至 Step 10 终审。
- **审查方式**: 本步零代码执行（落码属 Step 9）——E3 静态读码（逐节对拍 DESIGN D1-D9 与 §3 签名）+ golden 期望手工独立重推（不读 §4.4 结论先行）+ 计数链机械复核 + 红态推演。

### 9.1 复核读数

| 复核项 | 读数 | 结果 |
|--------|------|------|
| S1 golden 期望独立重推 | A：01-04 low 89 ≤ 90 → stop_loss（01-05 重建）；B：01-03 peak 53 ≥ 52.5 激活 → 01-05 low 47 ≤ 48.76 → trailing_stop（01-08 重建）；C：01-03 low 88 ≤ 90 且 high 122 ≥ 120 → SL 优先于 TP（01-04 重建） | 与 §4.4 逐值一致 |
| S1 weights/triggers/states 重推 | 五日权重矩阵（3 次置 0 + 3 次重建）；triggers 3 条（C 01-03 / A 01-04 / B 01-05，`exit_price_ref` = 退出日收盘）；states 末日 entry/peak/bar_count/entry_date | 与 §4.4 逐值一致 |
| S2 golden 期望独立重推 | X：01-03 count2 触发 → 01-04 重建 → 01-05 count2 触发 → 01-08 重建；Y：01-03 count2 触发但 `tradable=false` → 保持 + deferred=1 → 01-04 count3 退出 → 01-05 重建 → 01-08 count2 触发；states 仅 X（Y 末日已退出） | 与 §4.4 逐值一致 |
| 签名对拍（DESIGN §3） | `apply_timing` reindex keyword 形式（F-S4-P045-1 订正已落实）/ `SignalSet` 构造期形状校验（`==` 禁用注）/ `StopConfig.__post_init__` 正数校验 / `apply_stops` 三类 fail-fast + exit 分支禁同日重建 | 全部落实 |
| 计数链复核 | pytest 811→821（+10：V1-V8 + G1/G2）/ golden 13→15 / black 135·202（Step 6 时点；Step 9 实测 203 见 §10）/ mypy 105→107（Step 6 时点；Step 10 复跑订正 108，F-S10-P045-1）/ AST 22 / tests 93→94 / uv 0 | 与 DESIGN §6 自洽 |
| 红态推演 | V1-V8 + G1/G2 均因 `core.timing`/`core.stops` 不存在而失败 → **10 failed / 0 passed** | 与 §4.5 一致 |
| 既有面零触碰 | B1/B2/B3 纯新增（`core/timing.py`、`core/stops.py`、测试文件 + 2 golden JSON）；P-044 契约 / engine_v2 / 既有测试与 golden 零改动 | §8 回退点成立 |

### 9.2 发现与处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S6-P045-1 | **P2** | 总纲 §5 P-045 验收「与 vectorbt 对拍」在 IMPL 无落点（§2 任务表与 §7 门禁均无对拍项，仅 RESEARCH I3 有口径收窄描述）→ 对拍若不落 IMPL 即无执行载体，验收悬空 | **当轮处置**：§2 增补对拍任务行；新增 §4.6 对拍规格（`scripts/external_benchmark/verify_p045.py` 隔离 venv + 触发判定序列逐值比对 + waiver 豁免登记 + 附录出口）；§7 门禁表增补「verify_p045 exit 0」行 |
| F-S6-P045-2 | P3 | D7「止损退出日禁止同日重建」在 DESIGN 无显式依据，仅由 golden G1 隐含锁定：若允许同日重建，C 将以 01-03 当日 high=122 为 peak，01-04 low 99 ≤ 122×0.92=112.24 → trailing_stop 再退出，与期望 triggers（C 仅 1 条）冲突 | **当轮处置**：DESIGN D7 补注（反证推导 + G1 锁定）；IMPL §3.2 exit 分支 `continue` 注释同步 |
| F-S6-P045-3 | P3 | P045 golden JSON 的装饰字段（`schema_version`/`git_commit`/`tolerance`）无校验测试（§4.2-§4.3 仅断言 `expected` 内容，装饰字段不落断言） | **登记观察**：装饰字段不承载断言语义，不阻断；Step 9 落码时可选增一条 schema 自检（非门禁项） |

### 9.3 结论

- **判档**: 1 P2 + 2 P3，P2 当轮处置、P3 一处置一登记，无 P1。
- **结论**: **pass** —— 准予进入 Step 7 CHECKLIST。

---

## 10. Step 9 实施记录

- **落码顺序（TDD）**: ① 先落 `tests/test_p045_timing_stops.py`（V1-V8 + G1/G2）与 2 份 golden JSON → ② 红态实测 → ③ 落 `core/timing.py` + `core/stops.py` → ④ 绿态 → ⑤ 八门禁 → ⑥ 对拍脚本。
- **红态（实测）**: **`10 failed in 0.75s`**（0 passed）；10 项均 `ModuleNotFoundError: No module named 'core.timing' / 'core.stops'`——与 §4.5 预测逐字一致。
- **绿态（实测）**: **`10 passed in 0.58s`**（black 格式化后复跑仍 10 passed）。
- **门禁终态（实测）**: pytest **821 passed**（57.55s）/ golden **`15 passed, 806 deselected`** / black `core tests` **135**、全仓 **203** / mypy **`Success: no issues found in 107 source files`**（Step 9 时点，verify_p045 落盘前；Step 10 终态复跑 **108**，F-S10-P045-1）/ AST `except Exception` **22** / `tests/*.py` **94** / `uv lock --check` exit **0**（Resolved 148 packages）/ 新增 `# type: ignore` **0** / 对拍 `verify_p045` exit **0**。
- **既有回归（实测）**: `test_golden_baseline.py` + `test_p044_strategy_interface.py` + `test_engine_plugins.py` + `test_manifest.py` = **32 passed**（零订正）。
- **零 diff 面（实测）**: `git status` 对 `core/engine_v2.py` / `core/engine_v3_vector.py` / `core/strategy.py` / `core/risk_manager.py` / `core/config.py` / `core/target_positions.py` / `core/execution_policy.py` / `agents/` / `filter/` / `tests/_golden_cases.py` / `tests/test_golden_baseline.py` / `tests/golden/G1..G7.json` / `pyproject.toml` / `uv.lock` **全部空输出**。

### 10.1 实施期发现与处置（4 项，全部当轮处置）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P045-1 | **P2** | P-013 `test_all_cases_present` 以 `GOLDEN_DIR.glob("*.json")` 扫描**整个** golden 目录并与 `CASE_IDS`（G1-G7）全等断言；按 §4.3 落 `tests/golden/P045_S*.json` 后该断言失败（实测 `1 failed, 820 passed`）→ 与 B14/C10「P-013 harness 零 diff」硬冲突 | **golden 隔离到子目录** `tests/golden/p045/`（`GOLDEN_DIR = .../golden/p045`）；P-013 harness 零 diff 保持，实测 `15 passed, 806 deselected` 且 `git status tests/golden/` 仅 `?? tests/golden/p045/` |
| F-S9-P045-2 | P3 | `core/stops.py` 与测试文件按 §3.2/§4 逐字落码后 black 判 2 文件待格式化（注释列对齐 / 单行签名） | `black` style-only 重排（语义零变更），复跑 10 passed；门禁 135·203 达标（F-S9-P045-5） |
| F-S9-P045-3 | P3 | `verify_p045` 首跑 C3 fail：本仓触发按 `(date, code)` 时间序、vbt 侧按 code 循环序 → 列表顺序不同但**内容集合相同**（3/3 命中） | C3 断言两侧均按 `(date, code)` 规范化排序后比较（「触发判定序列」语义 = 日期×标的集合，不含遍历顺序）；复跑 PASS |
| F-S9-P045-4 | P3 | vbt 1.2.0 免费版 `trades.records` / `orders.records` **均无止损类型字段**（实测列 `id/col/size/entry_idx/entry_price/...`）→ `reason` 无法逐值对拍 | 登记 waiver W1（非断言），reason 正确性由 V5/V6 + G1/G2 锁定；同批实测 A/C 的 vbt 退出价为 SL 触发价 **90.0**（非 TP 120），可**间接**断言 SL 优先于 TP（C4/C5 PASS） |
| F-S9-P045-5 | P3 | black **全仓**计数链漏算对拍脚本：F-S6-P045-1 增补 `verify_p045.py` 时只加了门禁行，§7/DESIGN §6/CHECKLIST 仍记 **202**（+2 源 +1 测试）；实测 **203**（199 + 4） | 五文档统一订正为 **135 · 203**（DESIGN §6/§10.3、IMPL §7/§10、CHECKLIST 头部/D3/§5/§6-2、PROGRESS §3.51.9、CHANGELOG）；`core tests` 口径 **135** 不变（scripts 不在该范围） |

### 10.2 对拍读数（E2，`verify_p045` exit 0）

| ID | 断言 | 读数 |
|----|------|------|
| C1 | 本仓触发序列 == 规格锁定 | `[(01-03,C,stop_loss),(01-04,A,stop_loss),(01-05,B,trailing_stop)]` ✅ |
| C2.A/B/C | vbt 各恰一笔平仓 | A `01-04 @90.0` / B `01-05 @47.7` / C `01-03 @90.0` ✅ |
| C3 | 触发序列（date, code）逐值 | 两侧排序后全等 ✅ |
| C4 | C 退出价 = SL 90（非 TP 120）→ SL 优先级一致 | ✅ |
| C5 | A 退出价 = SL 90 | ✅ |
| W1-W4 | reason / 成交价-Nav / trailing 幅度 / 激活阈值 | 豁免登记（非断言） |

报告：[APPENDIX_p045_external_calibration.md](APPENDIX_p045_external_calibration.md)（7 断言 + 4 豁免，exit 0）。
