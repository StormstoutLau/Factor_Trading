"""A 股涨跌停规则表（P-012 D3 / T-3）。

- 规则不可变（``LimitRule`` frozen），``(board, is_st, date)`` 必须**恰好 1 条**命中；
  0 条或多条一律抛 ``LimitRuleError``，禁止回落默认值（DESIGN I3）。
- 板块由代码前缀推断：300/301→gem；688/689→star；8/4 开头→bse；其余→main。
- ST 状态由调用方按**当日**传入（不做 shift）。
- 本模块只依赖 pandas/numpy，不 import ``core``（避免循环依赖）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd

RULESET_VERSION = "cn_a_2026_07"


class LimitRuleError(ValueError):
    """规则表命中 0 条或多条。"""


@dataclass(frozen=True)
class LimitRule:
    """单条日期段涨跌停规则。"""

    board: str
    is_st: bool
    effective_from: pd.Timestamp
    effective_to: Optional[pd.Timestamp]
    up: float
    down: float

    def matches(self, board: str, is_st: bool, date: pd.Timestamp) -> bool:
        if self.board != board or self.is_st != is_st:
            return False
        if date < self.effective_from:
            return False
        if self.effective_to is not None and date >= self.effective_to:
            return False
        return True


# 规则表（RESEARCH §11.4 / §12.3.3；U-D3：bse 保留 is_st=True 闭合行）
RULES: tuple[LimitRule, ...] = (
    # 沪深主板：普通 10%
    LimitRule("main", False, pd.Timestamp("1996-12-16"), None, 0.10, -0.10),
    # 沪深主板 ST：5%（1998-04-28 起）→ 10%（2026-07-06 起）
    LimitRule("main", True, pd.Timestamp("1998-04-28"), pd.Timestamp("2026-07-06"), 0.05, -0.05),
    LimitRule("main", True, pd.Timestamp("2026-07-06"), None, 0.10, -0.10),
    # 创业板：10% / ST 5%（2009-10-30 开市）→ 20% / ST 20%（2020-08-24 注册制）
    LimitRule("gem", False, pd.Timestamp("2009-10-30"), pd.Timestamp("2020-08-24"), 0.10, -0.10),
    LimitRule("gem", False, pd.Timestamp("2020-08-24"), None, 0.20, -0.20),
    LimitRule("gem", True, pd.Timestamp("2009-10-30"), pd.Timestamp("2020-08-24"), 0.05, -0.05),
    LimitRule("gem", True, pd.Timestamp("2020-08-24"), None, 0.20, -0.20),
    # 科创板：20%（含 ST）
    LimitRule("star", False, pd.Timestamp("2019-07-22"), None, 0.20, -0.20),
    LimitRule("star", True, pd.Timestamp("2019-07-22"), None, 0.20, -0.20),
    # 北交所：30%（U-D3：ST 闭合行同 30%）
    LimitRule("bse", False, pd.Timestamp("2021-11-15"), None, 0.30, -0.30),
    LimitRule("bse", True, pd.Timestamp("2021-11-15"), None, 0.30, -0.30),
)

_RULE_INDEX: dict[tuple[str, bool], tuple[LimitRule, ...]] = {}
for _rule in RULES:
    _RULE_INDEX.setdefault((_rule.board, _rule.is_st), ())
    _RULE_INDEX[(_rule.board, _rule.is_st)] += (_rule,)


def infer_board(code: str) -> str:
    """按代码前缀推断板块。"""
    prefix = str(code).split(".")[0]
    if prefix.startswith(("300", "301")):
        return "gem"
    if prefix.startswith(("688", "689")):
        return "star"
    if prefix.startswith(("8", "4")):
        return "bse"
    return "main"


def resolve_limit(
    board: str,
    is_st: bool,
    date: pd.Timestamp,
    rules: Optional[Sequence[LimitRule]] = None,
) -> LimitRule:
    """按 ``(board, is_st, date)`` 查唯一规则。

    Raises:
        LimitRuleError: 命中 0 条（缺口/未知板块）或多条（区间重叠）。
    """
    date = pd.Timestamp(date)
    table = RULES if rules is None else tuple(rules)
    hits = [rule for rule in table if rule.matches(board, is_st, date)]
    if len(hits) != 1:
        if not hits:
            raise LimitRuleError(
                f"无匹配涨跌停规则: board={board}, is_st={is_st}, date={date.date()}"
            )
        raise LimitRuleError(
            f"涨跌停规则区间重叠: board={board}, is_st={is_st}, date={date.date()}, "
            f"命中 {len(hits)} 条"
        )
    return hits[0]


def build_limit_prices(
    close: pd.DataFrame,
    adj_factor: pd.DataFrame,
    st: Optional[pd.DataFrame],
    dates: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回 ``(limit_up_price, limit_down_price)``，均为 raw 价格口径。

    ``ref_price(t) = close(t-1) * adj(t-1) / adj(t)``（除权参考价）；
    ``limit = ref_price * (1 ± ratio)``；首行无 prev_close → NaN（不限制）。
    """
    up = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    down = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    if close.empty:
        return up, down

    adj = adj_factor.reindex(index=close.index, columns=close.columns)
    safe_adj = adj.replace(0, np.nan)
    ref = close.shift(1) * adj.shift(1) / safe_adj
    ref = ref.fillna(close.shift(1))

    board_columns: dict[str, list[str]] = {}
    for code in close.columns:
        board_columns.setdefault(infer_board(str(code)), []).append(code)

    st_frame = st.reindex(index=dates, columns=close.columns) if st is not None else None

    for date in dates:
        if date not in ref.index:
            continue
        ref_row = ref.loc[date]
        for board, columns in board_columns.items():
            normal = resolve_limit(board, False, date)
            st_rule = resolve_limit(board, True, date)
            if st_frame is not None and date in st_frame.index:
                st_mask = st_frame.loc[date, columns].to_numpy() == 1
            else:
                st_mask = np.zeros(len(columns), dtype=bool)
            ref_values = ref_row[columns].to_numpy(dtype=float)
            up.loc[date, columns] = np.where(
                st_mask, ref_values * (1 + st_rule.up), ref_values * (1 + normal.up)
            )
            down.loc[date, columns] = np.where(
                st_mask, ref_values * (1 + st_rule.down), ref_values * (1 + normal.down)
            )
    return up, down


def special_no_limit_mask(dates: pd.DatetimeIndex, codes: pd.Index, snap: object) -> pd.DataFrame:
    """True = 当日不适用涨跌停限制。

    - IPO 前 5 个交易日（``list_date <= t < list_date + 5 交易日``）；
    - 退市整理期首日依赖 ``delist_start_date``；字段缺失时该部分全 False，
      由调用方在报告标注 ``delist_period_handled=false``（U-D2）。
    """
    mask = pd.DataFrame(False, index=dates, columns=codes, dtype=bool)
    list_date = getattr(snap, "list_date", None)
    if list_date is None or len(list_date) == 0:
        return mask

    for code in codes:
        if code not in list_date.index:
            continue
        start = pd.Timestamp(list_date.loc[code])
        positions = np.flatnonzero(np.asarray(dates >= start))
        if positions.size == 0:
            continue
        begin = int(positions[0])
        end = min(begin + 5, len(dates))
        mask.iloc[begin:end, mask.columns.get_loc(code)] = True
    return mask
