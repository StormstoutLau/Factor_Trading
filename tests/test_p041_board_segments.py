"""P-041 infer_board 号段表补齐回归测试（U-P040-2）。

覆盖：920→bse / 302→gem / 既有前缀非回归 / 920 跨制度期价格 /
302 跨注册制边界 / 版本与未识别计数 / 带后缀代码。
"""

from __future__ import annotations

import pandas as pd
import pytest

from filter.limit_rules import (
    RULESET_VERSION,
    build_limit_prices,
    infer_board,
    unknown_board_count,
)


def test_v1_920_maps_to_bse():
    """V1：北交所 920 号段 → bse。"""
    for code in ("920000", "920493", "920931"):
        assert infer_board(code) == "bse"


def test_v2_302_maps_to_gem():
    """V2：创业板 302 号段 → gem。"""
    assert infer_board("302132") == "gem"


def test_v3_existing_prefixes_unchanged():
    """V3：既有前缀映射零变更（含未知前缀回落 main）。"""
    cases = {
        "300001": "gem",
        "301001": "gem",
        "688001": "star",
        "689001": "star",
        "830001": "bse",
        "430001": "bse",
        "000001": "main",
        "001001": "main",
        "002001": "main",
        "003001": "main",
        "600001": "main",
        "601001": "main",
        "603001": "main",
        "605001": "main",
        "700001": "main",
    }
    for code, board in cases.items():
        assert infer_board(code) == board


def test_v4_920_limit_prices_across_regimes():
    """V4：920 在集合竞价段 20/5、精选层段 13/7（flat 10、adj=1）。"""
    dates = pd.DatetimeIndex(["2020-07-22", "2020-07-23", "2020-07-24", "2020-07-27", "2020-07-28"])
    close = pd.DataFrame({"920493": [10.0] * 5}, index=dates)
    adj = pd.DataFrame({"920493": [1.0] * 5}, index=dates)

    up, down = build_limit_prices(close, adj, None, dates)

    for d in (dates[1], dates[2]):
        assert up.loc[d, "920493"] == pytest.approx(20.0)
        assert down.loc[d, "920493"] == pytest.approx(5.0)
    for d in (dates[3], dates[4]):
        assert up.loc[d, "920493"] == pytest.approx(13.0)
        assert down.loc[d, "920493"] == pytest.approx(7.0)


def test_v5_302_limit_prices_across_gem_regime():
    """V5：302 在 2020-08-24 前后分别为 10% / 20%（flat 10、adj=1）。"""
    dates = pd.DatetimeIndex(["2020-08-20", "2020-08-21", "2020-08-24"])
    close = pd.DataFrame({"302132": [10.0] * 3}, index=dates)
    adj = pd.DataFrame({"302132": [1.0] * 3}, index=dates)

    up, down = build_limit_prices(close, adj, None, dates)

    assert up.loc[dates[1], "302132"] == pytest.approx(11.0)
    assert down.loc[dates[1], "302132"] == pytest.approx(9.0)
    assert up.loc[dates[2], "302132"] == pytest.approx(12.0)
    assert down.loc[dates[2], "302132"] == pytest.approx(8.0)


def test_v6_version_and_unknown_counting():
    """V6：版本口径 cn_a_2026_11b；920/302 不再计入未识别前缀。"""
    assert RULESET_VERSION == "cn_a_2026_11b"
    before = unknown_board_count()
    assert infer_board("920493") == "bse"
    assert infer_board("302132") == "gem"
    assert unknown_board_count() == before


def test_v7_suffixed_codes():
    """V7：带交易所后缀的代码按点号前主干判定。"""
    assert infer_board("920493.BJ") == "bse"
    assert infer_board("302132.SZ") == "gem"
