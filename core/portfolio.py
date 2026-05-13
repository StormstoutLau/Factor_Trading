"""组合优化模块 - 基于Backtest_Opus_2.0架构

提供多种组合优化策略：
- 等权重优化
- 最小方差优化
- 均值方差优化（马科维茨）
- 风险平价优化
- 整手数优化
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import cvxpy as cp
import numpy as np
import pandas as pd
from scipy import linalg, stats

from config import OptimizerConfig

logger = logging.getLogger(__name__)

# 协方差估计器
COV_ESTIMATORS = {
    'sample': lambda returns: returns.cov(),
    'ledoit_wolf': lambda returns: _ledoit_wolf_shrinkage(returns),
    'ewma': lambda returns: _ewma_covariance(returns)
}


def _ledoit_wolf_shrinkage(returns: pd.DataFrame) -> pd.DataFrame:
    """Ledoit-Wolf压缩估计器
    
    Args:
        returns: 收益率数据
        
    Returns:
        压缩估计的协方差矩阵
    """
    # 计算样本协方差
    sample_cov = returns.cov()
    
    # 计算Ledoit-Wolf压缩参数
    n_assets = sample_cov.shape[0]
    n_obs = returns.shape[0]
    
    # 计算因子模型协方差
    mu = returns.mean()
    factor_cov = np.outer(mu, mu)
    
    # 计算压缩参数
    pi = np.sum(np.var(returns, ddof=1) ** 2)
    rho = np.sum(sample_cov.values ** 2)
    gamma = np.linalg.norm(sample_cov.values - factor_cov, 'fro') ** 2
    
    kappa = (pi - rho) / gamma
    shrinkage = max(0.0, min(1.0, kappa / n_obs))
    
    # 压缩估计
    cov_matrix = shrinkage * factor_cov + (1 - shrinkage) * sample_cov.values
    
    return pd.DataFrame(cov_matrix, index=sample_cov.index, columns=sample_cov.columns)


def _ewma_covariance(returns: pd.DataFrame, lambda_param: float = 0.94) -> pd.DataFrame:
    """指数加权移动平均协方差
    
    Args:
        returns: 收益率数据
        lambda_param: 衰减参数
        
    Returns:
        EWMA协方差矩阵
    """
    returns_array = returns.values
    n_periods, n_assets = returns_array.shape
    
    # 初始化权重
    weights = np.array([(1 - lambda_param) * lambda_param ** (n_periods - 1 - i) 
                       for i in range(n_periods)])
    weights = weights / weights.sum()
    
    # 计算加权均值
    weighted_mean = np.sum(returns_array * weights[:, None], axis=0)
    
    # 计算加权协方差
    cov_matrix = np.zeros((n_assets, n_assets))
    for i in range(n_periods):
        diff = returns_array[i] - weighted_mean
        cov_matrix += weights[i] * np.outer(diff, diff)
    
    return pd.DataFrame(cov_matrix, index=returns.columns, columns=returns.columns)


class BaseOptimizer:
    """组合优化器基类"""
    
    def __init__(self, config: OptimizerConfig):
        """初始化优化器
        
        Args:
            config: 优化器配置
        """
        self.cfg = config
        logger.info(f"{self.__class__.__name__} 初始化完成")
    
    def optimize(self, factor_scores: pd.Series, 
                 returns: Optional[pd.DataFrame] = None,
                 cov_matrix: Optional[pd.DataFrame] = None) -> pd.Series:
        """执行组合优化
        
        Args:
            factor_scores: 因子得分
            returns: 收益率数据（用于风险模型）
            cov_matrix: 协方差矩阵（可选）
            
        Returns:
            优化权重
        """
        raise NotImplementedError("子类必须实现optimize方法")
    
    def _apply_constraints(self, weights: pd.Series) -> pd.Series:
        """应用权重约束
        
        Args:
            weights: 原始权重
            
        Returns:
            约束后的权重
        """
        # 应用最大权重约束
        weights = weights.clip(upper=self.cfg.max_weight)
        
        # 应用最小权重约束
        weights = weights.clip(lower=self.cfg.min_weight)
        
        # 归一化
        weights = weights / weights.sum()
        
        return weights


class EqualWeightOptimizer(BaseOptimizer):
    """等权重优化器"""
    
    def optimize(self, factor_scores: pd.Series, 
                 returns: Optional[pd.DataFrame] = None,
                 cov_matrix: Optional[pd.DataFrame] = None) -> pd.Series:
        """等权重分配
        
        Args:
            factor_scores: 因子得分
            returns: 收益率数据（未使用）
            cov_matrix: 协方差矩阵（未使用）
            
        Returns:
            等权重组合
        """
        # 过滤掉NA和0值
        valid_scores = factor_scores.dropna()
        valid_scores = valid_scores[valid_scores != 0]
        
        if len(valid_scores) == 0:
            logger.warning("没有有效的因子得分，返回空权重")
            return pd.Series(dtype=float)
        
        # 选择目标数量的股票
        target_count = min(self.cfg.target_count, len(valid_scores))
        if self.cfg.select_top:
            selected_stocks = valid_scores.nlargest(target_count).index
        else:
            selected_stocks = valid_scores.nsmallest(target_count).index
        
        # 等权重分配
        weights = pd.Series(1.0 / len(selected_stocks), index=selected_stocks)
        
        # 应用约束
        weights = self._apply_constraints(weights)
        
        return weights


class MinVarianceOptimizer(BaseOptimizer):
    """最小方差优化器"""
    
    def optimize(self, factor_scores: pd.Series, 
                 returns: Optional[pd.DataFrame] = None,
                 cov_matrix: Optional[pd.DataFrame] = None) -> pd.Series:
        """最小方差优化
        
        Args:
            factor_scores: 因子得分
            returns: 收益率数据
            cov_matrix: 协方差矩阵
            
        Returns:
            最小方差组合权重
        """
        if returns is None and cov_matrix is None:
            raise ValueError("最小方差优化需要收益率数据或协方差矩阵")
        
        # 选择目标数量的股票
        if self.cfg.select_top:
            selected_stocks = factor_scores.nlargest(self.cfg.target_count).index
        else:
            selected_stocks = factor_scores.nsmallest(self.cfg.target_count).index
        
        # 获取协方差矩阵
        if cov_matrix is None:
            cov_estimator = COV_ESTIMATORS.get(self.cfg.cov_method, COV_ESTIMATORS['sample'])
            cov_matrix = cov_estimator(returns[selected_stocks])
        else:
            cov_matrix = cov_matrix.loc[selected_stocks, selected_stocks]
        
        # 最小方差优化
        n = len(selected_stocks)
        w = cp.Variable(n)
        
        # 目标函数：最小化组合方差
        portfolio_variance = cp.quad_form(w, cov_matrix.values)
        objective = cp.Minimize(portfolio_variance)
        
        # 约束条件
        constraints = [
            cp.sum(w) == 1,  # 权重和为1
            w >= self.cfg.min_weight,  # 最小权重
            w <= self.cfg.max_weight   # 最大权重
        ]
        
        # 求解
        problem = cp.Problem(objective, constraints)
        problem.solve()
        
        if problem.status != cp.OPTIMAL:
            logger.warning("最小方差优化未找到最优解，使用等权重")
            return EqualWeightOptimizer(self.cfg).optimize(factor_scores, returns, cov_matrix)
        
        # 构建权重序列
        weights = pd.Series(w.value, index=selected_stocks)
        
        return weights


class MeanVarianceOptimizer(BaseOptimizer):
    """均值方差优化器（马科维茨）"""
    
    def optimize(self, factor_scores: pd.Series, 
                 returns: Optional[pd.DataFrame] = None,
                 cov_matrix: Optional[pd.DataFrame] = None) -> pd.Series:
        """均值方差优化
        
        Args:
            factor_scores: 因子得分
            returns: 收益率数据
            cov_matrix: 协方差矩阵
            
        Returns:
            均值方差优化权重
        """
        if returns is None and cov_matrix is None:
            raise ValueError("均值方差优化需要收益率数据或协方差矩阵")
        
        # 选择目标数量的股票
        if self.cfg.select_top:
            selected_stocks = factor_scores.nlargest(self.cfg.target_count).index
        else:
            selected_stocks = factor_scores.nsmallest(self.cfg.target_count).index
        
        # 获取预期收益率和协方差矩阵
        if returns is not None:
            expected_returns = returns[selected_stocks].mean()
            cov_estimator = COV_ESTIMATORS.get(self.cfg.cov_method, COV_ESTIMATORS['sample'])
            cov_matrix = cov_estimator(returns[selected_stocks])
        else:
            expected_returns = pd.Series(0, index=selected_stocks)  # 如果没有收益率数据，假设预期收益为0
        
        # 均值方差优化
        n = len(selected_stocks)
        w = cp.Variable(n)
        
        # 目标函数：最大化效用 = 预期收益 - 风险厌恶系数 * 方差
        portfolio_return = expected_returns.values @ w
        portfolio_variance = cp.quad_form(w, cov_matrix.values)
        objective = cp.Maximize(portfolio_return - self.cfg.risk_aversion * portfolio_variance)
        
        # 约束条件
        constraints = [
            cp.sum(w) == 1,  # 权重和为1
            w >= self.cfg.min_weight,  # 最小权重
            w <= self.cfg.max_weight   # 最大权重
        ]
        
        # 求解
        problem = cp.Problem(objective, constraints)
        problem.solve()
        
        if problem.status != cp.OPTIMAL:
            logger.warning("均值方差优化未找到最优解，使用等权重")
            return EqualWeightOptimizer(self.cfg).optimize(factor_scores, returns, cov_matrix)
        
        # 构建权重序列
        weights = pd.Series(w.value, index=selected_stocks)
        
        return weights


class RiskParityOptimizer(BaseOptimizer):
    """风险平价优化器"""
    
    def optimize(self, factor_scores: pd.Series, 
                 returns: Optional[pd.DataFrame] = None,
                 cov_matrix: Optional[pd.DataFrame] = None) -> pd.Series:
        """风险平价优化
        
        Args:
            factor_scores: 因子得分
            returns: 收益率数据
            cov_matrix: 协方差矩阵
            
        Returns:
            风险平价权重
        """
        if returns is None and cov_matrix is None:
            raise ValueError("风险平价优化需要收益率数据或协方差矩阵")
        
        # 选择目标数量的股票
        if self.cfg.select_top:
            selected_stocks = factor_scores.nlargest(self.cfg.target_count).index
        else:
            selected_stocks = factor_scores.nsmallest(self.cfg.target_count).index
        
        # 获取协方差矩阵
        if cov_matrix is None:
            cov_estimator = COV_ESTIMATORS.get(self.cfg.cov_method, COV_ESTIMATORS['sample'])
            cov_matrix = cov_estimator(returns[selected_stocks])
        else:
            cov_matrix = cov_matrix.loc[selected_stocks, selected_stocks]
        
        # 风险平价优化（使用迭代算法）
        n = len(selected_stocks)
        weights = np.ones(n) / n  # 初始等权重
        
        for iteration in range(self.cfg.risk_parity_max_iter):
            # 计算每个资产的风险贡献
            portfolio_vol = np.sqrt(weights @ cov_matrix.values @ weights)
            marginal_contrib = cov_matrix.values @ weights / portfolio_vol
            risk_contrib = weights * marginal_contrib
            
            # 计算目标风险贡献
            target_risk_contrib = risk_contrib.mean()
            
            # 更新权重
            weights_new = weights * target_risk_contrib / risk_contrib
            
            # 检查收敛
            if np.max(np.abs(weights_new - weights)) < self.cfg.risk_parity_tol:
                break
            
            weights = weights_new
        
        # 归一化权重
        weights = weights / weights.sum()
        
        # 应用约束
        weights_series = pd.Series(weights, index=selected_stocks)
        weights_series = self._apply_constraints(weights_series)
        
        return weights_series


def round_lot_optimize(weights: pd.Series, prices: pd.Series, 
                      total_value: float, lot_size: int = 100) -> pd.Series:
    """整手数优化
    
    Args:
        weights: 目标权重
        prices: 股票价格
        total_value: 总资金
        lot_size: 整手数大小（A股为100）
        
    Returns:
        整手数优化后的权重
    """
    # 计算每只股票的目标投资金额
    target_values = weights * total_value
    
    # 计算每只股票的目标股数
    target_shares = target_values / prices
    
    # 调整为整手数（向下取整到最近的100股整数倍）
    rounded_shares = np.floor(target_shares / lot_size) * lot_size
    
    # 计算实际投资金额
    actual_values = rounded_shares * prices
    
    # 重新计算权重
    actual_weights = actual_values / actual_values.sum()
    
    return actual_weights


def build_optimizer(config: OptimizerConfig) -> BaseOptimizer:
    """构建优化器
    
    Args:
        config: 优化器配置
        
    Returns:
        优化器实例
    """
    optimizer_map = {
        'equal_weight': EqualWeightOptimizer,
        'min_variance': MinVarianceOptimizer,
        'mvo': MeanVarianceOptimizer,
        'risk_parity': RiskParityOptimizer
    }
    
    optimizer_class = optimizer_map.get(config.method, EqualWeightOptimizer)
    return optimizer_class(config)
