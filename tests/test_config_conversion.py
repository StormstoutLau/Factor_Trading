"""P-012 B6：UniverseConfig → UniverseFilterConfig 转换（D11 / T-12）验收测试。"""

from __future__ import annotations

from core.config import UniverseConfig
from filter.universe_filter_clean import UniverseFilterConfig


def test_all_fields_mapped():
    """21 个源字段逐一显式映射，无遗漏（F5）。"""
    source = UniverseConfig(
        exclude_suspended=False,
        exclude_limit_up=False,
        exclude_limit_down=False,
        exclude_st=False,
        check_next_day_tradable=True,
        limit_up_threshold=0.11,
        limit_down_threshold=-0.11,
        st_limit_up_threshold=0.06,
        st_limit_down_threshold=-0.06,
        exclude_na_factors=False,
        na_factor_names=["factor_a"],
        na_threshold=0.4,
        exclude_stock_prefixes=["300", "688"],
        excluded_prefixes=["300", "688", "8"],
        exclude_by_market_cap=True,
        min_market_cap=2e9,
        max_market_cap=4e11,
        exclude_industries=True,
        excluded_industries=["房地产"],
        enable_custom_filters=True,
        custom_filter_configs={"demo": {"threshold": 1}},
    )

    target = UniverseFilterConfig.from_universe_config(source)

    assert target.exclude_suspended is False
    assert target.exclude_limit_up is False
    assert target.exclude_limit_down is False
    assert target.exclude_st is False
    assert target.check_next_day_tradable is True
    assert target.limit_up_threshold == 0.11
    assert target.limit_down_threshold == -0.11
    assert target.st_limit_up_threshold == 0.06
    assert target.st_limit_down_threshold == -0.06
    assert target.exclude_na_factors is False
    assert target.na_factor_names == ["factor_a"]
    assert target.na_threshold == 0.4
    assert target.exclude_stock_prefixes is True  # list[str] → bool（F-I5）
    assert target.excluded_prefixes == ["300", "688", "8"]
    assert target.exclude_by_market_cap is True
    assert target.min_market_cap == 2e9
    assert target.max_market_cap == 4e11
    assert target.exclude_industries is True
    assert target.excluded_industries == ["房地产"]
    assert target.enable_custom_filters is True
    assert target.custom_filter_configs == {"demo": {"threshold": 1}}


def test_default_drift_explicitly_overridden():
    """两处默认值漂移被显式覆盖，不落回 filter 侧默认（D11）。"""
    source = UniverseConfig()
    target = UniverseFilterConfig.from_universe_config(source)

    # 漂移 1：exclude_na_factors 源 True / 目标默认 False
    assert target.exclude_na_factors is True
    # 漂移 2：na_factor_names 源 [] / 目标默认 ["factor_value"]
    assert target.na_factor_names == []
    # 源 exclude_stock_prefixes 为 list（默认 []）→ bool False
    assert target.exclude_stock_prefixes is False
    # excluded_prefixes 源 [] / 目标默认 ["300", "688"]
    assert target.excluded_prefixes == []
    # 新字段不由旧配置派生，保持默认
    assert target.next_day_tradable_mode == "ignored"
    assert target.limit_check_price == "open"


def test_unknown_fields_do_not_break():
    """源对象携带未知字段时转换不丢失已映射字段（D11）。"""
    source = UniverseConfig(excluded_prefixes=["9"])
    source.future_option = {"unexpected": True}

    target = UniverseFilterConfig.from_universe_config(source)

    assert target.excluded_prefixes == ["9"]
    assert target.exclude_stock_prefixes is False
    assert not hasattr(target, "future_option")
