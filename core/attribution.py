"""Brinson多期归因分析模块

实现经典的Brinson归因模型：
- 单期Brinson模型 (BF, 1985)
- 多期Brinson模型 (Menchero, 2000)
- 行业配置效应 + 个股选择效应 + 交互效应
- 支持多因子归因扩展
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AttributionPeriod:
    """单期归因数据"""
    period_date: pd.Timestamp
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    
    # 组合权重和收益 (按行业/板块)
    portfolio_weights: dict[str, float] = field(default_factory=dict)
    portfolio_returns: dict[str, float] = field(default_factory=dict)
    
    # 基准权重和收益
    benchmark_weights: dict[str, float] = field(default_factory=dict)
    benchmark_returns: dict[str, float] = field(default_factory=dict)
    
    # 组合内个股数据 {sector: {stock: (weight, return)}}
    portfolio_stocks: dict[str, dict[str, tuple[float, float]]] = field(default_factory=dict)
    benchmark_stocks: dict[str, dict[str, tuple[float, float]]] = field(default_factory=dict)


@dataclass
class BrinsonAttributionResult:
    """Brinson归因结果"""
    # 单期结果
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0
    total_excess_return: float = 0.0
    
    # 行业层面分解
    sector_allocation: dict[str, float] = field(default_factory=dict)
    sector_selection: dict[str, float] = field(default_factory=dict)
    sector_interaction: dict[str, float] = field(default_factory=dict)
    
    # 个股层面分解 (在行业内)
    stock_selection: dict[str, dict[str, float]] = field(default_factory=dict)
    
    # 多期累计
    cumulative_portfolio_return: float = 0.0
    cumulative_benchmark_return: float = 0.0
    cumulative_allocation: float = 0.0
    cumulative_selection: float = 0.0
    cumulative_interaction: float = 0.0


class BrinsonAttributionAnalyzer:
    """Brinson归因分析器
    
    实现经典Brinson多期归因模型：
    - 配置效应 (Allocation Effect): 行业配置能力
    - 选择效应 (Selection Effect): 个股选择能力  
    - 交互效应 (Interaction Effect): 配置与选择的交互
    
    参考:
    - Brinson & Fachler (1985): "Measuring Non-U.S. Equity Portfolio Performance"
    - Menchero (2000): "An Optimized Approach to Linking Attribution Results Over Time"
    """
    
    def __init__(self, linking_method: str = "geometric"):
        """初始化归因分析器
        
        Args:
            linking_method: 多期连接方法 ("geometric" | "arithmetic" | "optimized")
        """
        self.linking_method = linking_method
        self.periods: list[AttributionPeriod] = []
        self.results: list[BrinsonAttributionResult] = []
        
        logger.info(f"Brinson归因分析器初始化完成 (连接方法: {linking_method})")
    
    def add_period(self, period: AttributionPeriod):
        """添加单期数据"""
        self.periods.append(period)
    
    def calculate_single_period(self, period: AttributionPeriod) -> BrinsonAttributionResult:
        """计算单期Brinson归因
        
        公式:
        - 配置效应 = Σ(Wp_i - Wb_i) * Rb_i
        - 选择效应 = ΣWb_i * (Rp_i - Rb_i)
        - 交互效应 = Σ(Wp_i - Wb_i) * (Rp_i - Rb_i)
        - 超额收益 = Rp - Rb = 配置 + 选择 + 交互
        
        Args:
            period: 单期数据
            
        Returns:
            归因结果
        """
        result = BrinsonAttributionResult()
        result.total_excess_return = period.portfolio_return - period.benchmark_return
        
        sectors = set(period.portfolio_weights.keys()) | set(period.benchmark_weights.keys())
        
        for sector in sectors:
            wp = period.portfolio_weights.get(sector, 0.0)
            wb = period.benchmark_weights.get(sector, 0.0)
            rp = period.portfolio_returns.get(sector, 0.0)
            rb = period.benchmark_returns.get(sector, 0.0)
            
            # 配置效应 (行业配置能力)
            alloc = (wp - wb) * rb
            result.sector_allocation[sector] = alloc
            result.allocation_effect += alloc
            
            # 选择效应 (行业内选股能力)
            select = wb * (rp - rb)
            result.sector_selection[sector] = select
            result.selection_effect += select
            
            # 交互效应
            inter = (wp - wb) * (rp - rb)
            result.sector_interaction[sector] = inter
            result.interaction_effect += inter
            
            # 个股层面分解
            if sector in period.portfolio_stocks and sector in period.benchmark_stocks:
                result.stock_selection[sector] = self._calculate_stock_selection(
                    period.portfolio_stocks[sector],
                    period.benchmark_stocks[sector],
                    rb
                )
        
        # 验证
        expected = result.allocation_effect + result.selection_effect + result.interaction_effect
        if abs(expected - result.total_excess_return) > 1e-10:
            logger.warning(f"归因分解不匹配: {expected:.6f} vs {result.total_excess_return:.6f}")
        
        return result
    
    def _calculate_stock_selection(
        self,
        portfolio_stocks: dict[str, tuple[float, float]],
        benchmark_stocks: dict[str, tuple[float, float]],
        sector_benchmark_return: float
    ) -> dict[str, float]:
        """计算行业内个股选择贡献
        
        Args:
            portfolio_stocks: {股票: (权重, 收益)}
            benchmark_stocks: {股票: (权重, 收益)}
            sector_benchmark_return: 行业基准收益
            
        Returns:
            个股选择贡献
        """
        stock_contrib = {}
        all_stocks = set(portfolio_stocks.keys()) | set(benchmark_stocks.keys())
        
        for stock in all_stocks:
            wp, rp = portfolio_stocks.get(stock, (0.0, 0.0))
            wb, rb = benchmark_stocks.get(stock, (0.0, 0.0))
            
            # 个股选择效应 = wb * (rp - rb)
            stock_contrib[stock] = wb * (rp - rb)
        
        return stock_contrib
    
    def calculate_multi_period(self) -> BrinsonAttributionResult:
        """计算多期累计归因
        
        使用几何连接法:
        - 累计组合收益 = Π(1 + Rp_t) - 1
        - 累计基准收益 = Π(1 + Rb_t) - 1
        - 累计超额收益 = (1 + Rp) / (1 + Rb) - 1
        
        归因连接 (Menchero, 2000):
        - 每期贡献按比例缩放以匹配累计超额收益
        
        Returns:
            累计归因结果
        """
        if not self.periods:
            return BrinsonAttributionResult()
        
        # 计算单期结果
        self.results = [self.calculate_single_period(p) for p in self.periods]
        
        # 计算累计收益
        cum_portfolio = 1.0
        cum_benchmark = 1.0
        
        for period, result in zip(self.periods, self.results):
            cum_portfolio *= (1 + period.portfolio_return)
            cum_benchmark *= (1 + period.benchmark_return)
        
        cum_portfolio -= 1
        cum_benchmark -= 1
        cum_excess = (1 + cum_portfolio) / (1 + cum_benchmark) - 1
        
        # 归因连接
        if self.linking_method == "geometric":
            return self._geometric_linking(cum_portfolio, cum_benchmark, cum_excess)
        elif self.linking_method == "arithmetic":
            return self._arithmetic_linking(cum_portfolio, cum_benchmark, cum_excess)
        else:
            return self._optimized_linking(cum_portfolio, cum_benchmark, cum_excess)
    
    def _geometric_linking(
        self,
        cum_portfolio: float,
        cum_benchmark: float,
        cum_excess: float
    ) -> BrinsonAttributionResult:
        """几何连接法"""
        result = BrinsonAttributionResult()
        result.cumulative_portfolio_return = cum_portfolio
        result.cumulative_benchmark_return = cum_benchmark
        result.total_excess_return = cum_excess
        
        # 单期归因和
        total_alloc = sum(r.allocation_effect for r in self.results)
        total_select = sum(r.selection_effect for r in self.results)
        total_inter = sum(r.interaction_effect for r in self.results)
        total_single = total_alloc + total_select + total_inter
        
        if abs(total_single) < 1e-10:
            return result
        
        # 按比例缩放
        scale = cum_excess / total_single if total_single != 0 else 1.0
        result.cumulative_allocation = total_alloc * scale
        result.cumulative_selection = total_select * scale
        result.cumulative_interaction = total_inter * scale
        
        return result
    
    def _arithmetic_linking(
        self,
        cum_portfolio: float,
        cum_benchmark: float,
        cum_excess: float
    ) -> BrinsonAttributionResult:
        """算术连接法"""
        result = BrinsonAttributionResult()
        result.cumulative_portfolio_return = cum_portfolio
        result.cumulative_benchmark_return = cum_benchmark
        result.total_excess_return = cum_excess
        
        # 简单求和
        result.cumulative_allocation = sum(r.allocation_effect for r in self.results)
        result.cumulative_selection = sum(r.selection_effect for r in self.results)
        result.cumulative_interaction = sum(r.interaction_effect for r in self.results)
        
        return result
    
    def _optimized_linking(
        self,
        cum_portfolio: float,
        cum_benchmark: float,
        cum_excess: float
    ) -> BrinsonAttributionResult:
        """Menchero优化连接法
        
        最小化连接误差的平方和
        """
        result = BrinsonAttributionResult()
        result.cumulative_portfolio_return = cum_portfolio
        result.cumulative_benchmark_return = cum_benchmark
        result.total_excess_return = cum_excess
        
        # 计算调整因子
        total_single = sum(
            r.allocation_effect + r.selection_effect + r.interaction_effect
            for r in self.results
        )
        
        if abs(total_single) < 1e-10:
            return result
        
        # Menchero调整
        adjustment = (cum_excess - total_single) / len(self.results)
        
        result.cumulative_allocation = sum(r.allocation_effect for r in self.results)
        result.cumulative_selection = sum(r.selection_effect for r in self.results)
        result.cumulative_interaction = sum(r.interaction_effect for r in self.results)
        
        # 将调整分配到各效应
        result.cumulative_allocation += adjustment * 0.4
        result.cumulative_selection += adjustment * 0.4
        result.cumulative_interaction += adjustment * 0.2
        
        return result
    
    def generate_report(self) -> dict[str, Any]:
        """生成归因分析报告"""
        if not self.results:
            self.calculate_multi_period()
        
        cum_result = self.calculate_multi_period()
        
        report = {
            'summary': {
                'cumulative_portfolio_return': cum_result.cumulative_portfolio_return,
                'cumulative_benchmark_return': cum_result.cumulative_benchmark_return,
                'total_excess_return': cum_result.total_excess_return,
                'allocation_effect': cum_result.cumulative_allocation,
                'selection_effect': cum_result.cumulative_selection,
                'interaction_effect': cum_result.cumulative_interaction,
            },
            'period_results': [
                {
                    'date': str(p.period_date),
                    'portfolio_return': p.portfolio_return,
                    'benchmark_return': p.benchmark_return,
                    'excess_return': r.total_excess_return,
                    'allocation': r.allocation_effect,
                    'selection': r.selection_effect,
                    'interaction': r.interaction_effect,
                }
                for p, r in zip(self.periods, self.results)
            ],
            'sector_breakdown': self._get_sector_breakdown(),
        }
        
        return report
    
    def _get_sector_breakdown(self) -> dict[str, dict[str, float]]:
        """获取行业层面分解"""
        if not self.results:
            return {}
        
        sectors = set()
        for r in self.results:
            sectors.update(r.sector_allocation.keys())
        
        breakdown = {}
        for sector in sectors:
            breakdown[sector] = {
                'allocation': sum(r.sector_allocation.get(sector, 0.0) for r in self.results),
                'selection': sum(r.sector_selection.get(sector, 0.0) for r in self.results),
                'interaction': sum(r.sector_interaction.get(sector, 0.0) for r in self.results),
            }
        
        return breakdown


class FactorAttributionAnalyzer:
    """多因子归因分析器
    
    扩展Brinson模型到多因子场景：
    - 风格因子归因 (Size, Value, Momentum, etc.)
    - 行业因子归因
    - 纯因子收益分解
    """
    
    def __init__(self, factor_names: list[str]):
        """初始化
        
        Args:
            factor_names: 因子名称列表
        """
        self.factor_names = factor_names
        self.periods: list[dict[str, Any]] = []
        
        logger.info(f"多因子归因分析器初始化完成 (因子数: {len(factor_names)})")
    
    def add_period(
        self,
        date: pd.Timestamp,
        portfolio_exposure: dict[str, float],
        benchmark_exposure: dict[str, float],
        factor_returns: dict[str, float],
        specific_return: float
    ):
        """添加单期因子暴露数据"""
        self.periods.append({
            'date': date,
            'portfolio_exposure': portfolio_exposure,
            'benchmark_exposure': benchmark_exposure,
            'factor_returns': factor_returns,
            'specific_return': specific_return,
        })
    
    def calculate_attribution(self) -> dict[str, Any]:
        """计算多因子归因
        
        公式:
        - 因子贡献 = (组合暴露 - 基准暴露) * 因子收益
        - 特质收益 = 组合收益 - 因子贡献和
        
        Returns:
            归因结果
        """
        factor_contrib = {name: 0.0 for name in self.factor_names}
        specific_contrib = 0.0
        
        for period in self.periods:
            for factor in self.factor_names:
                wp = period['portfolio_exposure'].get(factor, 0.0)
                wb = period['benchmark_exposure'].get(factor, 0.0)
                fr = period['factor_returns'].get(factor, 0.0)
                factor_contrib[factor] += (wp - wb) * fr
            
            specific_contrib += period['specific_return']
        
        return {
            'factor_contributions': factor_contrib,
            'specific_contribution': specific_contrib,
            'total_excess': sum(factor_contrib.values()) + specific_contrib,
        }


def create_benchmark_from_universe(
    universe_returns: pd.DataFrame,
    weights: Optional[dict[str, float]] = None
) -> pd.Series:
    """从股票池创建基准收益序列
    
    Args:
        universe_returns: 股票收益矩阵 (dates x stocks)
        weights: 自定义权重 {stock: weight}，None则等权
        
    Returns:
        基准日收益序列
    """
    if weights is None:
        # 等权基准
        return universe_returns.mean(axis=1)
    
    # 加权基准
    weight_series = pd.Series(weights)
    aligned = universe_returns[weight_series.index]
    return (aligned * weight_series).sum(axis=1)


def calculate_sector_returns(
    stock_returns: pd.DataFrame,
    sector_mapping: dict[str, str],
    weights: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """计算行业收益
    
    Args:
        stock_returns: 股票收益矩阵 (dates x stocks)
        sector_mapping: 股票到行业的映射 {stock: sector}
        weights: 权重矩阵 (dates x stocks)，None则等权
        
    Returns:
        行业收益矩阵 (dates x sectors)
    """
    sectors = sorted(set(sector_mapping.values()))
    sector_returns = pd.DataFrame(index=stock_returns.index, columns=sectors, dtype=float)
    
    for sector in sectors:
        sector_stocks = [s for s, sec in sector_mapping.items() if sec == sector]
        sector_data = stock_returns[sector_stocks]
        
        if weights is not None:
            sector_weights = weights[sector_stocks]
            sector_weights = sector_weights.div(sector_weights.sum(axis=1), axis=0)
            sector_returns[sector] = (sector_data * sector_weights).sum(axis=1)
        else:
            sector_returns[sector] = sector_data.mean(axis=1)
    
    return sector_returns
