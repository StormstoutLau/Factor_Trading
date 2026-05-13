"""策略评估模块

提供因子统计量计算和策略绩效评估。
"""

from strategy_evaluation.stats import FactorStatsCalculator
from strategy_evaluation.evaluator import StrategyEvaluator

__all__ = ['FactorStatsCalculator', 'StrategyEvaluator']
