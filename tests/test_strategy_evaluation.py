"""StrategyEvaluation 模块测试"""

import numpy as np
import pandas as pd
import pytest

from strategy_evaluation.stats import FactorStatsCalculator
from strategy_evaluation.evaluator import StrategyEvaluator


class TestFactorStatsCalculator:
    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=50, freq="B")
        stocks = ["A", "B", "C"]

        factor = pd.DataFrame(
            {s: np.random.randn(50) for s in stocks},
            index=dates,
        )
        returns = pd.DataFrame(
            {s: np.random.randn(50) * 0.02 for s in stocks},
            index=dates,
        )
        return factor, returns

    def test_calculate_ic(self, sample_data):
        factor, returns = sample_data
        calc = FactorStatsCalculator(factor, returns)
        ic = calc.calculate_ic(method="spearman")

        assert isinstance(ic, pd.Series)
        assert len(ic) == len(factor)
        assert ic.index.equals(factor.index)

    def test_calculate_ic_stats(self, sample_data):
        factor, returns = sample_data
        calc = FactorStatsCalculator(factor, returns)
        ic_series = calc.calculate_ic()
        stats = calc.calculate_ic_stats(ic_series)

        assert "ic_mean" in stats
        assert "ic_std" in stats
        assert "ir" in stats
        assert "ic_tstat" in stats
        assert isinstance(stats["ir"], (int, float))

    def test_calculate_half_life(self, sample_data):
        factor, returns = sample_data
        calc = FactorStatsCalculator(factor, returns)
        ic_series = calc.calculate_ic()
        hl = calc.calculate_half_life(ic_series)

        assert isinstance(hl, float)

    def test_calculate_turnover(self, sample_data):
        factor, _ = sample_data
        calc = FactorStatsCalculator(factor, factor)
        turnover = calc.calculate_turnover()

        assert isinstance(turnover, pd.Series)
        assert len(turnover) == len(factor) - 1
        assert (turnover >= 0).all()

    def test_calculate_all_stats(self, sample_data):
        factor, returns = sample_data
        calc = FactorStatsCalculator(factor, returns)
        all_stats = calc.calculate_all_stats()

        assert "ic_mean" in all_stats
        assert "half_life" in all_stats
        assert "turnover_mean" in all_stats
        assert "ic_series" in all_stats


class TestStrategyEvaluator:
    def test_rank_strategies(self):
        results = {
            "s1": {"performance_metrics": {"sharpe_ratio": 1.5, "total_return": 0.2, "max_drawdown": -0.1}},
            "s2": {"performance_metrics": {"sharpe_ratio": 1.0, "total_return": 0.15, "max_drawdown": -0.05}},
            "s3": {"performance_metrics": {"sharpe_ratio": 2.0, "total_return": 0.1, "max_drawdown": -0.2}},
        }
        evaluator = StrategyEvaluator(results)
        ranked = evaluator.rank_strategies()

        assert isinstance(ranked, pd.DataFrame)
        assert len(ranked) == 3
        assert "score" in ranked.columns
        assert ranked.iloc[0]["score"] >= ranked.iloc[-1]["score"]

    def test_rank_with_custom_weights(self):
        results = {
            "s1": {"performance_metrics": {"sharpe_ratio": 1.5, "total_return": 0.2}},
            "s2": {"performance_metrics": {"sharpe_ratio": 1.0, "total_return": 0.5}},
        }
        evaluator = StrategyEvaluator(results)
        ranked = evaluator.rank_strategies(
            metrics=["sharpe_ratio", "total_return"],
            weights=[0.2, 0.8],
        )
        assert ranked.iloc[0]["name"] == "s2"

    def test_generate_evaluation_report(self):
        results = {
            "s1": {"performance_metrics": {"sharpe_ratio": 1.5, "total_return": 0.2, "max_drawdown": -0.1}},
        }
        evaluator = StrategyEvaluator(results)
        report = evaluator.generate_evaluation_report()

        assert "ranking" in report
        assert "best_strategy" in report
        assert report["total_strategies"] == 1

    def test_empty_strategies(self):
        evaluator = StrategyEvaluator({})
        ranked = evaluator.rank_strategies()
        assert len(ranked) == 0

    def test_error_handling(self):
        results = {
            "s1": {"error": "failed"},
            "s2": {"performance_metrics": {"sharpe_ratio": 1.0}},
        }
        evaluator = StrategyEvaluator(results)
        ranked = evaluator.rank_strategies()
        assert len(ranked) == 1
        assert ranked.iloc[0]["name"] == "s2"
