"""P-040 bse 规则表日期维度补齐回归测试（U-P039-4）。

覆盖：新三板集合竞价段 / 精选层边界 / 北交所期不变 / pre-2018 fail-fast /
全窗口可解析 / build_limit_prices 复牌首日不限制。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from filter.limit_rules import (
    RULESET_VERSION,
    LimitRuleError,
    build_limit_prices,
    resolve_limit,
)

PRE_END = pd.Timestamp("2020-07-26")
SEG_START = pd.Timestamp("2020-07-27")
BSE_START = pd.Timestamp("2021-11-15")


def test_v1_neeq_auction_limits():
    """V1：新三板创新层/基础层集合竞价段 +100% / −50%。"""
    for is_st in (False, True):
        rule = resolve_limit("bse", is_st, PRE_END)
        assert (rule.up, rule.down) == (1.00, -0.50)


def test_v2_selection_layer_boundary():
    """V2：2020-07-27 起进入精选层 ±30%（半开区间边界）。"""
    for is_st in (False, True):
        rule = resolve_limit("bse", is_st, SEG_START)
        assert (rule.up, rule.down) == (0.30, -0.30)


def test_v3_bse_unchanged_and_version():
    """V3：北交所期维持 30%；C2 版本口径为 cn_a_2026_11。"""
    assert RULESET_VERSION == "cn_a_2026_11"
    for d in (BSE_START, pd.Timestamp("2023-06-01")):
        for is_st in (False, True):
            rule = resolve_limit("bse", is_st, d)
            assert (rule.up, rule.down) == (0.30, -0.30)


def test_v4_pre_2018_fail_fast():
    """V4：2018-01-15 之前仍无规则 → fail-fast（不回落默认值）。"""
    with pytest.raises(LimitRuleError, match="无匹配涨跌停规则"):
        resolve_limit("bse", False, pd.Timestamp("2018-01-12"))


def test_v5_window_fully_resolvable():
    """V5：真实数据窗口 2020-01-23..2021-11-12 逐日 × 两态均可解析（436 日缺口 → 0）。"""
    dates = pd.bdate_range("2020-01-23", "2021-11-12")
    for d in dates:
        for is_st in (False, True):
            assert resolve_limit("bse", is_st, d) is not None


def test_v6_build_limit_prices_no_raise_and_resume_day_unlimited():
    """V6：不抛错；前收 NaN（停牌复牌首日）不限制；集合竞价段 10 → 20 / 5。"""
    dates = pd.DatetimeIndex(["2020-07-22", "2020-07-23", "2020-07-27"])
    close = pd.DataFrame({"832317": [10.0, np.nan, 13.35]}, index=dates)
    adj = pd.DataFrame({"832317": [1.0, 1.0, 1.0]}, index=dates)

    up, down = build_limit_prices(close, adj, None, dates)

    assert up.shape == (3, 1) and down.shape == (3, 1)
    # 2020-07-23：前收 10，集合竞价段 +100% / −50%
    assert up.loc[dates[1], "832317"] == pytest.approx(20.0)
    assert down.loc[dates[1], "832317"] == pytest.approx(5.0)
    # 2020-07-27：前收 NaN（停牌）→ 不限制
    assert np.isnan(up.loc[dates[2], "832317"])
    assert np.isnan(down.loc[dates[2], "832317"])
