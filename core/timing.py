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
    """四掩码信号集合（short 两侧为 P-050 类型位，本批全流程忽略）。

    含 DataFrame 字段 → **禁用 ``==``**（frozen dataclass 逐字段比较触发
    DataFrame 真值歧义 ``ValueError``）；逐字段用 ``assert_frame_equal``。
    """

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
