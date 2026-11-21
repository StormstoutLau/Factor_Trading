import numpy as np
import pytest

import strategies  # noqa: F401  ← 触发注册
from core.registry import get_strategy_registry
from core.strategy import Strategy
from strategies.base import StrategyConfigError

FACTORIES = ["grid_atr", "trend_breakout", "ts_momentum", "mean_reversion"]
GRID_BASE = {"000001": 10.0, "600000": 10.0, "000002": 10.0}


def test_c1_all_registered_implement_protocol():
    registry = get_strategy_registry()
    for name in FACTORIES:
        entry = registry.get(name)
        assert entry is not None
        strategy = entry.factory(base_price=GRID_BASE) if name == "grid_atr" else entry.factory()
        assert isinstance(strategy, Strategy)
        assert strategy.meta.strategy_id == name
        assert len(strategy.meta.code_hash) == 12


def test_c2_factory_forms_equivalent():
    registry = get_strategy_registry()
    entry = registry.get("ts_momentum")
    assert entry is not None
    default = entry.factory()
    via_mapping = entry.factory({"lookbacks": (20, 60), "min_votes": 1})
    via_override = entry.factory(lookbacks=(20, 60), min_votes=1)
    assert default.meta.param_schema["lookbacks"] == (20, 60, 120)
    assert via_mapping.meta.param_schema == via_override.meta.param_schema


def test_c2_grid_requires_base_price():
    entry = get_strategy_registry().get("grid_atr")
    assert entry is not None
    with pytest.raises(StrategyConfigError):
        entry.factory(None)
    with pytest.raises(StrategyConfigError):
        entry.factory({})
    with pytest.raises(StrategyConfigError):
        entry.factory(base_price={})


def test_c3_duplicate_registration_warns(caplog):
    """重复注册告警。用独立探针 id（**不得**复用真实 id：registry 重复注册会覆盖）。"""
    from core.registry import register_strategy

    probe = "_p051b_dup_probe"
    with caplog.at_level("WARNING"):

        @register_strategy(probe, description="first")
        def _first(config=None, **kwargs):
            return None

        @register_strategy(probe, description="second")
        def _second(config=None, **kwargs):
            return None

    assert "already registered" in caplog.text
    get_strategy_registry().unregister(probe)


def test_c5_param_schema_matches_fields():
    from dataclasses import fields

    from strategies.grid import GridATRConfig

    entry = get_strategy_registry().get("grid_atr")
    assert entry is not None
    strategy = entry.factory(base_price={"A": 1.0})
    assert set(strategy.meta.param_schema) == {item.name for item in fields(GridATRConfig)}


def test_c6_unknown_key_rejected():
    entry = get_strategy_registry().get("ts_momentum")
    assert entry is not None
    with pytest.raises(StrategyConfigError):
        entry.factory(nope=1)


@pytest.mark.parametrize("name", FACTORIES)
def test_c7_history_none_fails(name):
    from _p051b_common import make_view

    entry = get_strategy_registry().get(name)
    assert entry is not None
    strategy = entry.factory(base_price=GRID_BASE) if name == "grid_atr" else entry.factory()
    view, state = make_view(closes=np.full((140, 3), 10.0), with_history=False)
    with pytest.raises(StrategyConfigError):
        strategy.generate_signals(view, state)
