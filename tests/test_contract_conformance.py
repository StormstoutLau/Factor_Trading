"""P-012 B6：协议契约符合性（D7 / T-11 / T-12）验收测试。"""

from __future__ import annotations

import inspect
from typing import Any

import pandas as pd

from core.data_provider import DataProvider
from core.config import BacktestConfig, CostConfig, FactorConfig
from core.data import DataManager
from core.execution import ExecutionSimulator
from core.factor import FactorCombiner, FactorPipeline
from core.interfaces import (
    IDataManager,
    IExecutionSimulator,
    IFactorCombiner,
    IFactorPipeline,
    IPositionTracker,
    IUniverseFilter,
)
from core.tracker import PositionTracker
from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig

EXPECTED_MEMBERS: dict[type, set[str]] = {
    IDataManager: {
        "trade_dates",
        "stock_codes",
        "n_stocks",
        "returns",
        "get_adj_price",
        "load_factor",
        "get_data_info",
        "get_asset_info",
    },
    IUniverseFilter: {
        "build_masks",
        "buyable",
        "sellable",
        "tradable",
        "get_mask_summary",
        "get_layer_masks",
    },
    IPositionTracker: {
        "execute_trade",
        "update_market_values",
        "get_position",
        "get_all_positions",
        "get_cash",
        "get_total_value",
        "get_snapshots",
        "get_snapshots_df",
    },
    IFactorPipeline: {"process"},
    IFactorCombiner: {"combine"},
    IExecutionSimulator: {
        "execute_order",
        "execute_pending_order",
        "get_execution_stats",
        "trade_log",
    },
}

IMPLEMENTATIONS: dict[type, type] = {
    IDataManager: DataManager,
    IUniverseFilter: UniverseFilter,
    IPositionTracker: PositionTracker,
    IFactorPipeline: FactorPipeline,
    IFactorCombiner: FactorCombiner,
    IExecutionSimulator: ExecutionSimulator,
}


def _instances() -> dict[type, Any]:
    dm = DataManager(BacktestConfig())
    return {
        IDataManager: dm,
        IUniverseFilter: UniverseFilter(dm, UniverseFilterConfig()),
        IPositionTracker: PositionTracker(1, 1.0),
        IFactorPipeline: FactorPipeline(dm, FactorConfig()),
        IFactorCombiner: FactorCombiner([], {}),
        IExecutionSimulator: ExecutionSimulator(CostConfig()),
    }


def _public_members(obj: Any) -> set[str]:
    return {name for name in dir(obj) if not name.startswith("_")}


def test_protocol_members():
    """6 协议成员集合完整；零消费方成员已收窄（V14 / D7）。"""
    assert not hasattr(IFactorPipeline, "process_single")
    assert not hasattr(IFactorCombiner, "combine_single")

    instances = _instances()
    for protocol, expected in EXPECTED_MEMBERS.items():
        protocol_members = _public_members(protocol)
        assert (
            expected <= protocol_members
        ), f"{protocol.__name__} 缺少 {expected - protocol_members}"

        impl = IMPLEMENTATIONS[protocol]
        missing = expected - _public_members(instances[protocol])
        assert not missing, f"{impl.__name__} 未实现 {protocol.__name__} 的 {missing}"


def test_execute_order_signature():
    """execute_order 形参名/顺序与实现一致，且无 price / **kwargs（F2）。"""
    expected = [
        "self",
        "stock",
        "side",
        "quantity",
        "date",
        "open_price",
        "close_price",
        "high_price",
        "low_price",
        "volume",
    ]
    protocol_params = list(inspect.signature(IExecutionSimulator.execute_order).parameters)
    impl_params = list(inspect.signature(ExecutionSimulator.execute_order).parameters)
    assert protocol_params == expected
    assert impl_params == expected

    for parameter in inspect.signature(IExecutionSimulator.execute_order).parameters.values():
        assert parameter.kind is not inspect.Parameter.VAR_KEYWORD


class MockDataProvider:
    """DataProvider 端口的最小实现（不接线，V15）。"""

    def __init__(self) -> None:
        self.prices: dict[str, pd.DataFrame] = {}

    def load_price(self, kind: str) -> pd.DataFrame:
        return self.prices[kind]

    def load_aux(self, kind: str) -> Any | None:
        return None

    def load_universe(self) -> Any | None:
        return None


def test_mock_data_provider_members():
    """DataProvider 端口 3 成员完整（V14/V15）。"""
    expected = {"load_price", "load_aux", "load_universe"}
    assert expected <= _public_members(DataProvider)
    assert expected <= _public_members(MockDataProvider)


def test_universe_filter_layer_masks_member():
    """B1 新增的 get_layer_masks 已进入协议与实现。"""
    assert "get_layer_masks" in _public_members(IUniverseFilter)
    assert "get_layer_masks" in _public_members(UniverseFilter)
