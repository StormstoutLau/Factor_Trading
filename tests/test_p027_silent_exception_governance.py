"""P-027 静默失败治理第三批（core 外 22 处 except 分级显形）测试。

对应 docs/IMPL_p027_silent_exception_governance_phase3.md §5（T1-T12）。
全部使用 monkeypatch（禁 unittest.mock，DESIGN §6 / E7）。
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
import pytest

from agents.assumption_monitor import ReturnDistributionMonitor
from agents.auto_parameter_optimizer import AutoOptimizedFundManager
from agents.guru_agent_v2 import GuruAgentV2, GuruDataLoader
from agents.research_team_v2 import FundManager, ResearchView, ViewDirection
from filter.custom import ConditionalFilter, CustomFunctionFilter, DynamicFilter, ExpressionFilter
from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig
from strategy_evaluation.stats import FactorStatsCalculator

STOCKS = ["A", "B", "C"]
DATES = pd.bdate_range("2024-01-02", periods=3)


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        rng.normal(size=(len(DATES), len(STOCKS))), index=DATES, columns=STOCKS
    )


def _boom(*args, **kwargs):
    raise RuntimeError("boom")


def _all_true(data: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(True, index=data.index, columns=data.columns)


# --------------------------------------------------------------- T1
@pytest.mark.parametrize(
    "factory,key,universe",
    [
        (lambda: CustomFunctionFilter(_boom), "custom_function", False),
        (lambda: ExpressionFilter("1/0"), "expression", False),
        (lambda: DynamicFilter({}, _boom), "dynamic", False),
        (
            lambda: ConditionalFilter(_boom, CustomFunctionFilter(_all_true), CustomFunctionFilter(_all_true)),
            "conditional",
            False,
        ),
        (
            lambda: UniverseFilter(
                object(),
                UniverseFilterConfig(
                    enable_custom_filters=True,
                    custom_filter_configs={"bad": {"type": "function", "function": _boom}},
                ),
            ),
            "custom_mask_build:bad",
            True,
        ),
    ],
)
def test_filter_failopen_counts(factory, key, universe):
    """D1：5 处 filter 降级路径计数 +1，fail-open 返回不变。"""
    filt = factory()
    if universe:
        filt._build_custom_masks()
        assert filt.get_failure_stats() == {key: 1}
        assert "bad" not in filt._custom_masks
    else:
        mask = filt.build_mask(_frame())
        assert mask.to_numpy().all()
        assert filt.get_failure_stats() == {key: 1}
