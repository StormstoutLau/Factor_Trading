"""P-007 层 A：三处真实缺陷的 smoke 测试（RED 于修复前，GREEN 于修复后）"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import RebalanceConfig
from core.engine_plugins import RegistryPlugin
from core.global_contagion import analyze_market_contagion
from core.rebalance import FixedIntervalTrigger
from core.risk_monitor import CompositeRiskEngine


def test_remove_monitor_does_not_raise():
    """A-1：remove_monitor 曾引用未定义的 RiskAction，调用即 NameError"""
    engine = CompositeRiskEngine()
    monitor_count = len(engine.monitors)

    engine.remove_monitor("nonexistent")

    assert len(engine.monitors) == monitor_count


def test_analyze_market_contagion_returns_dict():
    """A-2：analyze_market_contagion 曾调用不存在的 evaluate，调用即 AttributeError"""
    rng = np.random.default_rng(20261109)
    market_returns = {
        "SPX": pd.Series(rng.normal(0, 0.01, 60)),
        "SH": pd.Series(rng.normal(0, 0.015, 60)),
    }

    result = analyze_market_contagion(market_returns)

    assert isinstance(result, dict)
    assert {"signal", "summary"} <= set(result.keys())


def test_create_trigger_via_registry():
    """A-3：create_trigger 曾以 3 个位置参数调用只接受 2 个的 create，调用即 TypeError"""
    plugin = RegistryPlugin()
    plugin.enable()
    config = RebalanceConfig(method="fixed", frequency="monthly")
    trade_dates = pd.date_range("2024-01-01", "2024-12-31", freq="B")

    trigger = plugin.create_trigger(config, trade_dates)

    assert isinstance(trigger, FixedIntervalTrigger)
