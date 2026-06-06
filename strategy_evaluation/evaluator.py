"""策略评估器

综合评估策略/因子的绩效表现。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class StrategyEvaluator:
    """策略评估器
    
    综合评估策略/因子的绩效表现。
    
    Example:
        evaluator = StrategyEvaluator(backtest_results)
        
        # 策略排名
        ranking = evaluator.rank_strategies()
        print(ranking)
        
        # 生成评估报告
        report = evaluator.generate_evaluation_report()
    """
    
    def __init__(self, backtest_results: dict[str, Any]):
        """初始化
        
        Args:
            backtest_results: 回测结果字典 {name: result}
        """
        self.results = backtest_results
    
    def rank_strategies(
        self,
        metrics: list[str] = ["sharpe_ratio", "total_return", "max_drawdown"],
        weights: Optional[list[float]] = None
    ) -> pd.DataFrame:
        """策略排名
        
        Args:
            metrics: 评估指标列表
            weights: 指标权重（默认等权）
            
        Returns:
            排名DataFrame
        """
        if weights is None:
            weights = [1.0 / len(metrics)] * len(metrics)
        
        data = []
        for name, result in self.results.items():
            if "error" in result:
                continue
            
            perf = result.get('performance_metrics', {})
            row = {'name': name}
            
            score = 0
            for metric, weight in zip(metrics, weights):
                value = perf.get(metric, 0)
                # 对回撤进行反向处理
                if 'drawdown' in metric:
                    value = -value
                row[metric] = value
                score += value * weight
            
            row['score'] = score
            data.append(row)
        
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('score', ascending=False)
        
        return df
    
    def generate_evaluation_report(self) -> dict[str, Any]:
        """生成评估报告"""
        ranking = self.rank_strategies()
        
        return {
            'ranking': ranking,
            'best_strategy': ranking.iloc[0]['name'] if not ranking.empty else None,
            'total_strategies': len(self.results),
            'successful_strategies': len([r for r in self.results.values() if 'error' not in r]),
        }
