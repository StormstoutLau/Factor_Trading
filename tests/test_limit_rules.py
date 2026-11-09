"""P-012 B2：涨跌停规则表（D3 / T-3）验收测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from filter.limit_rules import (
    RULESET_VERSION,
    LimitRule,
    LimitRuleError,
    infer_board,
    resolve_limit,
    special_no_limit_mask,
)


def test_st_main_2026_07_06_switch():
    assert resolve_limit("main", True, pd.Timestamp("2026-07-05")).up == 0.05
    assert resolve_limit("main", True, pd.Timestamp("2026-07-06")).up == 0.10
    assert resolve_limit("main", False, pd.Timestamp("2026-07-06")).up == 0.10


def test_gem_2020_08_24_switch():
    assert resolve_limit("gem", False, pd.Timestamp("2020-08-21")).up == 0.10
    assert resolve_limit("gem", False, pd.Timestamp("2020-08-24")).up == 0.20
    assert resolve_limit("gem", True, pd.Timestamp("2020-08-21")).up == 0.05
    assert resolve_limit("gem", True, pd.Timestamp("2020-08-24")).up == 0.20


def test_bse_limit_30_and_ipo_mask():
    assert resolve_limit("bse", False, pd.Timestamp("2022-01-04")).up == 0.30
    assert resolve_limit("bse", True, pd.Timestamp("2022-01-04")).up == 0.30

    dates = pd.bdate_range("2024-01-02", periods=10)
    snap = SimpleNamespace(
        list_date=pd.Series({"430001": dates[2]}),
        delist=None,
        status="corrected",
    )
    mask = special_no_limit_mask(dates, pd.Index(["430001", "600001"]), snap)
    assert mask.loc[dates[2] : dates[6], "430001"].all()
    assert not mask.loc[dates[7], "430001"]
    assert not mask["600001"].any()


def test_infer_board_prefixes():
    cases = {
        "300001": "gem",
        "301001": "gem",
        "688001": "star",
        "689001": "star",
        "830001": "bse",
        "430001": "bse",
        "000001": "main",
        "600001": "main",
        "700001": "main",  # 无法识别前缀归 main（DESIGN §7）
    }
    for code, board in cases.items():
        assert infer_board(code) == board


def test_rule_lookup_gap_raises():
    with pytest.raises(LimitRuleError):
        resolve_limit("main", True, pd.Timestamp("1990-01-02"))


def test_rule_overlap_raises():
    rules = (
        LimitRule("main", False, pd.Timestamp("2020-01-01"), None, 0.10, -0.10),
        LimitRule("main", False, pd.Timestamp("2021-01-01"), None, 0.20, -0.20),
    )
    with pytest.raises(LimitRuleError):
        resolve_limit("main", False, pd.Timestamp("2022-01-04"), rules=rules)


def test_ruleset_version_nonempty():
    assert isinstance(RULESET_VERSION, str)
    assert RULESET_VERSION
