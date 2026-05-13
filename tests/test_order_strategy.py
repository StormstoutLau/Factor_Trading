"""OrderStrategy 模块测试"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from order_strategy.strategies import (
    IcebergStrategy,
    MarketOrderStrategy,
    MarketImpactModel,
    TWAPStrategy,
    VWAPStrategy,
)
from order_strategy.evaluator import OrderStrategyEvaluator


class TestMarketOrderStrategy:
    def test_split_order(self):
        strategy = MarketOrderStrategy()
        result = strategy.split_order(
            symbol="000001.SZ",
            total_size=10000,
            side="buy",
            start_time=datetime(2024, 1, 1, 9, 30),
        )
        assert len(result.slices) == 1
        assert result.slices[0].size == 10000
        assert result.slices[0].is_market is True
        assert result.estimated_duration_min == 0.0

    def test_estimate_cost(self):
        strategy = MarketOrderStrategy()
        cost = strategy.estimate_cost("000001.SZ", 10000, "buy")
        assert cost["total_cost_bps"] == 7.0


class TestTWAPStrategy:
    def test_split_order(self):
        strategy = TWAPStrategy(num_slices=5, duration_min=50)
        result = strategy.split_order(
            symbol="000001.SZ",
            total_size=10000,
            side="buy",
            start_time=datetime(2024, 1, 1, 9, 30),
        )
        assert len(result.slices) == 5
        assert sum(s.size for s in result.slices) == pytest.approx(10000, rel=1e-9)
        assert result.estimated_duration_min == 50.0

    def test_randomize(self):
        strategy = TWAPStrategy(num_slices=4, duration_min=40, randomize=True)
        result = strategy.split_order(
            symbol="000001.SZ",
            total_size=10000,
            side="buy",
            start_time=datetime(2024, 1, 1, 9, 30),
        )
        assert len(result.slices) == 4
        assert sum(s.size for s in result.slices) == pytest.approx(10000, rel=1e-9)


class TestVWAPStrategy:
    def test_split_order_uniform(self):
        strategy = VWAPStrategy(num_slices=4, duration_min=40)
        result = strategy.split_order(
            symbol="000001.SZ",
            total_size=10000,
            side="buy",
            start_time=datetime(2024, 1, 1, 9, 30),
        )
        assert len(result.slices) == 4
        assert sum(s.size for s in result.slices) == pytest.approx(10000, rel=1e-9)

    def test_split_order_with_profile(self):
        profile = pd.Series([0.1, 0.2, 0.3, 0.4])
        strategy = VWAPStrategy(num_slices=4, duration_min=40, volume_profile=profile)
        result = strategy.split_order(
            symbol="000001.SZ",
            total_size=10000,
            side="buy",
            start_time=datetime(2024, 1, 1, 9, 30),
        )
        assert len(result.slices) == 4
        assert result.slices[0].size == pytest.approx(1000, rel=1e-9)
        assert result.slices[3].size == pytest.approx(4000, rel=1e-9)


class TestIcebergStrategy:
    def test_split_order(self):
        strategy = IcebergStrategy(display_size=1000, interval_sec=60)
        result = strategy.split_order(
            symbol="000001.SZ",
            total_size=5500,
            side="buy",
            start_time=datetime(2024, 1, 1, 9, 30),
            variance_ratio=0.0,
        )
        assert len(result.slices) == 6
        assert sum(s.size for s in result.slices) == pytest.approx(5500, rel=1e-9)

    def test_overflow_protection(self):
        strategy = IcebergStrategy(display_size=1, interval_sec=0.001)
        with pytest.raises(RuntimeError, match="overflow"):
            strategy.split_order(
                symbol="000001.SZ",
                total_size=100000,
                side="buy",
                start_time=datetime(2024, 1, 1, 9, 30),
            )


class TestMarketImpactModel:
    def test_permanent_impact(self):
        model = MarketImpactModel()
        impact = model.permanent_impact(
            order_size=10000,
            daily_volume=1000000,
            volatility=0.02,
        )
        assert impact > 0
        assert isinstance(impact, float)

    def test_temporary_impact(self):
        model = MarketImpactModel()
        impact = model.temporary_impact(
            order_size=10000,
            daily_volume=1000000,
            volatility=0.02,
            participation_rate=0.1,
        )
        assert impact > 0

    def test_total_cost(self):
        model = MarketImpactModel()
        cost = model.total_cost(
            order_size=10000,
            daily_volume=1000000,
            volatility=0.02,
        )
        assert "permanent_bps" in cost
        assert "temporary_bps" in cost
        assert cost["total_bps"] == cost["permanent_bps"] + cost["temporary_bps"]

    def test_zero_volume(self):
        model = MarketImpactModel()
        impact = model.permanent_impact(10000, 0, 0.02)
        assert impact == 0.0

    def test_optimal_participation_rate(self):
        model = MarketImpactModel()
        rate = model.optimal_participation_rate(
            risk_aversion=1e-6,
            order_size=100000,
            daily_volume=10000000,
            volatility=0.02,
        )
        assert rate > 0


class TestOrderStrategyEvaluator:
    def test_simulate_execution(self):
        evaluator = OrderStrategyEvaluator()
        strategy = MarketOrderStrategy()
        record = evaluator.simulate_execution(
            strategy=strategy,
            symbol="000001.SZ",
            total_size=10000,
            side="buy",
            benchmark_price=10.0,
            daily_volume=1000000,
            volatility=0.02,
            start_time=pd.Timestamp("2024-01-01 09:30"),
        )
        assert record.strategy_name == "MarketOrder"
        assert record.total_size == 10000
        assert record.slippage_bps >= 0

    def test_evaluate_strategy(self):
        evaluator = OrderStrategyEvaluator()
        strategy = TWAPStrategy()
        for _ in range(5):
            evaluator.simulate_execution(
                strategy=strategy,
                symbol="000001.SZ",
                total_size=10000,
                side="buy",
                benchmark_price=10.0,
                daily_volume=1000000,
                volatility=0.02,
                start_time=pd.Timestamp("2024-01-01 09:30"),
            )
        metrics = evaluator.evaluate_strategy("TWAP")
        assert metrics.total_orders == 5
        assert metrics.avg_slippage_bps != 0

    def test_compare_strategies(self):
        evaluator = OrderStrategyEvaluator()
        for strategy in [MarketOrderStrategy(), TWAPStrategy()]:
            evaluator.simulate_execution(
                strategy=strategy,
                symbol="000001.SZ",
                total_size=10000,
                side="buy",
                benchmark_price=10.0,
                daily_volume=1000000,
                volatility=0.02,
                start_time=pd.Timestamp("2024-01-01 09:30"),
            )
        df = evaluator.compare_strategies()
        assert len(df) == 2
        assert "综合得分" in df.columns

    def test_recommend_strategy(self):
        evaluator = OrderStrategyEvaluator()
        assert evaluator.recommend_strategy("high", 0.005) == "MarketOrder"
        assert evaluator.recommend_strategy("low", 0.05) == "VWAP"
        assert evaluator.recommend_strategy("medium", 0.5) == "Iceberg"

    def test_get_summary_empty(self):
        evaluator = OrderStrategyEvaluator()
        summary = evaluator.get_summary()
        assert summary["status"] == "no_data"

    def test_clear(self):
        evaluator = OrderStrategyEvaluator()
        evaluator.simulate_execution(
            strategy=MarketOrderStrategy(),
            symbol="000001.SZ",
            total_size=10000,
            side="buy",
            benchmark_price=10.0,
            daily_volume=1000000,
            volatility=0.02,
            start_time=pd.Timestamp("2024-01-01 09:30"),
        )
        assert len(evaluator.records) == 1
        evaluator.clear()
        assert len(evaluator.records) == 0
