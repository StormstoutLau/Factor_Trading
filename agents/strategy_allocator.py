"""
多策略动态资金分配模块 (Strategy Allocator)

实现用户提出的混合架构：
- 底层（策略评估层）：贝叶斯动态线性模型估计策略时变收益和相关性
- 上层（分配层）：在线凸优化（FTRL with entropy regularization）动态调整权重
- 元策略层：预留RL接口，用于调整超参数

参考论文框架：
- MAB: ε-greedy, UCB, Thompson Sampling
- Online Learning: Hedge, FTRL
- Bayesian: DLM + Kalman Filter
- RL: PPO/A3C (预留接口)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ============================================================
# 1. 数据模型
# ============================================================

@dataclass
class StrategyPerformance:
    """策略绩效快照"""
    strategy_id: str
    date: datetime
    daily_return: float
    cumulative_return: float
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    
    # 扩展指标
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0


@dataclass  
class AllocationState:
    """分配状态"""
    weights: np.ndarray           # 当前权重 (K,)
    strategy_returns: np.ndarray  # 最近收益矩阵 (T, K)
    dates: list[datetime]         # 日期列表
    
    def sharpe_ratios(self, risk_free_rate: float = 0.0) -> np.ndarray:
        """计算各策略的夏普比率"""
        if len(self.strategy_returns) == 0:
            return np.zeros(len(self.weights))
        
        excess_returns = self.strategy_returns - risk_free_rate
        means = np.mean(excess_returns, axis=0)
        stds = np.std(excess_returns, axis=0)
        stds = np.where(stds == 0, 1e-8, stds)
        return means / stds
    
    def covariance(self) -> np.ndarray:
        """计算收益协方差矩阵"""
        if len(self.strategy_returns) < 2:
            return np.eye(len(self.weights)) * 1e-6
        return np.cov(self.strategy_returns.T)


# ============================================================
# 2. 策略评估层：贝叶斯动态线性模型 (DLM)
# ============================================================

class BayesianDLM:
    """
    贝叶斯动态线性模型
    
    对每个策略的收益建模为时变参数过程：
        r_t = β_t + ε_t,  ε_t ~ N(0, σ²)
        β_t = β_{t-1} + η_t,  η_t ~ N(0, q²)
    
    使用卡尔曼滤波在线更新后验分布。
    """
    
    def __init__(self, 
                 observation_variance: float = 0.01,
                 state_variance: float = 0.001,
                 prior_mean: float = 0.0,
                 prior_variance: float = 0.1):
        """
        Args:
            observation_variance: 观测噪声方差 σ²
            state_variance: 状态转移方差 q² (控制适应速度)
            prior_mean: 先验均值
            prior_variance: 先验方差
        """
        self.sigma2 = observation_variance
        self.q2 = state_variance
        
        # 当前后验分布参数
        self.mu = prior_mean      # 后验均值
        self.sigma2_post = prior_variance  # 后验方差
        
        # 历史轨迹
        self.trajectory: list[tuple[datetime, float, float]] = []  # (date, mu, sigma)
        
        # 性能统计
        self.prediction_errors: list[float] = []
        self.n_observations = 0
    
    def update(self, 
               return_t: float, 
               date: Optional[datetime] = None) -> dict[str, float]:
        """
        卡尔曼滤波更新
        
        预测步骤：
            μ_{t|t-1} = μ_{t-1}
            σ²_{t|t-1} = σ²_{t-1} + q²
        
        更新步骤：
            K_t = σ²_{t|t-1} / (σ²_{t|t-1} + σ²)
            μ_t = μ_{t|t-1} + K_t * (r_t - μ_{t|t-1})
            σ²_t = (1 - K_t) * σ²_{t|t-1}
        
        Args:
            return_t: 时刻t的观测收益
            date: 日期标记
            
        Returns:
            更新后的状态字典
        """
        # 预测步骤
        mu_pred = self.mu
        sigma2_pred = self.sigma2_post + self.q2
        
        # 卡尔曼增益
        K = sigma2_pred / (sigma2_pred + self.sigma2)
        
        # 更新步骤
        prediction_error = return_t - mu_pred
        self.mu = mu_pred + K * prediction_error
        self.sigma2_post = (1 - K) * sigma2_pred
        
        # 记录
        self.n_observations += 1
        self.prediction_errors.append(prediction_error)
        
        if date is not None:
            self.trajectory.append((date, self.mu, np.sqrt(self.sigma2_post)))
        
        return {
            'mu': self.mu,
            'sigma': np.sqrt(self.sigma2_post),
            'K': K,
            'prediction_error': prediction_error
        }
    
    def predict(self, n_steps: int = 1) -> tuple[float, float]:
        """
        预测未来收益
        
        Returns:
            (预测均值, 预测标准差)
        """
        # n步预测：均值不变，方差累积
        mu_pred = self.mu
        sigma2_pred = self.sigma2_post + n_steps * self.q2
        return mu_pred, np.sqrt(sigma2_pred)
    
    def get_confidence_interval(self, alpha: float = 0.95) -> tuple[float, float]:
        """
        获取置信区间
        
        Args:
            alpha: 置信水平
            
        Returns:
            (下限, 上限)
        """
        z = stats.norm.ppf((1 + alpha) / 2)
        margin = z * np.sqrt(self.sigma2_post)
        return self.mu - margin, self.mu + margin
    
    def get_performance_metrics(self) -> dict[str, float]:
        """获取性能指标"""
        if len(self.prediction_errors) < 2:
            return {'rmse': 0.0, 'mae': 0.0}
        
        errors = np.array(self.prediction_errors)
        return {
            'rmse': np.sqrt(np.mean(errors**2)),
            'mae': np.mean(np.abs(errors)),
            'n_obs': self.n_observations,
            'current_mu': self.mu,
            'current_sigma': np.sqrt(self.sigma2_post)
        }


class StrategyEvaluator:
    """
    策略评估器
    
    为每个策略维护一个贝叶斯DLM，估计时变收益和相关性。
    """
    
    def __init__(self, 
                 n_strategies: int,
                 strategy_names: Optional[list[str]] = None,
                 state_variance: float = 0.001,
                 lookback_window: int = 60):
        """
        Args:
            n_strategies: 策略数量
            strategy_names: 策略名称列表
            state_variance: DLM状态方差
            lookback_window: 收益历史窗口
        """
        self.n = n_strategies
        self.names = strategy_names or [f"strategy_{i}" for i in range(n_strategies)]
        self.lookback = lookback_window
        
        # 每个策略一个DLM
        self.dlms: list[BayesianDLM] = [
            BayesianDLM(state_variance=state_variance)
            for _ in range(n_strategies)
        ]
        
        # 收益历史
        self.returns_history: list[np.ndarray] = []
        self.dates: list[datetime] = []
        
        # 相关性矩阵（滚动估计）
        self.correlation_matrix: np.ndarray = np.eye(n_strategies)
    
    def update(self, 
               returns: np.ndarray, 
               date: Optional[datetime] = None) -> dict[str, Any]:
        """
        更新所有策略的DLM
        
        Args:
            returns: 各策略当日收益 (K,)
            date: 日期
            
        Returns:
            更新结果摘要
        """
        assert len(returns) == self.n, f"收益维度不匹配: {len(returns)} != {self.n}"
        
        results = {}
        for i, (dlm, ret) in enumerate(zip(self.dlms, returns)):
            result = dlm.update(ret, date)
            results[self.names[i]] = result
        
        # 记录历史
        self.returns_history.append(returns.copy())
        if date is not None:
            self.dates.append(date)
        
        # 更新相关性矩阵
        if len(self.returns_history) >= 10:
            recent_returns = np.array(self.returns_history[-self.lookback:])
            # 检查每列标准差，避免常数列导致corrcoef产生NaN
            stds = np.std(recent_returns, axis=0)
            valid_cols = stds > 1e-12
            if np.all(valid_cols):
                self.correlation_matrix = np.corrcoef(recent_returns.T)
            else:
                # 对有变化的列计算相关，常数列设为0相关
                self.correlation_matrix = np.eye(self.n)
                valid_indices = np.where(valid_cols)[0]
                if len(valid_indices) >= 2:
                    sub_corr = np.corrcoef(recent_returns[:, valid_indices].T)
                    for i, vi in enumerate(valid_indices):
                        for j, vj in enumerate(valid_indices):
                            self.correlation_matrix[vi, vj] = sub_corr[i, j]
            # 处理NaN和对称化
            self.correlation_matrix = np.nan_to_num(self.correlation_matrix, nan=0.0)
            self.correlation_matrix = (self.correlation_matrix + self.correlation_matrix.T) / 2
            np.fill_diagonal(self.correlation_matrix, 1.0)
        
        return results
    
    def get_expected_returns(self) -> np.ndarray:
        """获取各策略的期望收益"""
        return np.array([dlm.mu for dlm in self.dlms])
    
    def get_expected_variances(self) -> np.ndarray:
        """获取各策略的期望方差"""
        return np.array([dlm.sigma2_post for dlm in self.dlms])
    
    def get_uncertainty(self) -> np.ndarray:
        """获取各策略的不确定性（后验标准差）"""
        return np.array([np.sqrt(dlm.sigma2_post) for dlm in self.dlms])
    
    def get_sharpe_estimates(self, risk_free_rate: float = 0.0) -> np.ndarray:
        """获取夏普比率估计"""
        expected = self.get_expected_returns() - risk_free_rate
        uncertainty = self.get_uncertainty()
        uncertainty = np.where(uncertainty < 1e-8, 1e-8, uncertainty)
        return expected / uncertainty
    
    def get_report(self) -> dict[str, Any]:
        """生成评估报告"""
        report = {
            'strategies': {},
            'correlation_matrix': self.correlation_matrix.tolist(),
            'summary': {}
        }
        
        for i, name in enumerate(self.names):
            dlm = self.dlms[i]
            report['strategies'][name] = {
                'expected_return': dlm.mu,
                'uncertainty': np.sqrt(dlm.sigma2_post),
                'confidence_interval_95': dlm.get_confidence_interval(0.95),
                'n_observations': dlm.n_observations,
                'metrics': dlm.get_performance_metrics()
            }
        
        # 汇总统计
        sharpe_estimates = self.get_sharpe_estimates()
        report['summary'] = {
            'best_strategy': self.names[np.argmax(sharpe_estimates)],
            'worst_strategy': self.names[np.argmin(sharpe_estimates)],
            'avg_correlation': np.mean(np.abs(self.correlation_matrix[np.triu_indices_from(self.correlation_matrix, k=1)])),
            'max_correlation': np.max(np.abs(self.correlation_matrix[np.triu_indices_from(self.correlation_matrix, k=1)]))
        }
        
        return report


# ============================================================
# 3. 分配层：在线凸优化 (FTRL + Hedge)
# ============================================================

class BaseAllocator(ABC):
    """分配器基类"""
    
    @abstractmethod
    def allocate(self, 
                 evaluator: StrategyEvaluator,
                 current_weights: Optional[np.ndarray] = None) -> np.ndarray:
        """
        计算资金分配权重
        
        Args:
            evaluator: 策略评估器
            current_weights: 当前权重（用于计算换手惩罚）
            
        Returns:
            新权重 (K,)，满足 sum=1, w_i >= 0
        """
        pass


class HedgeAllocator(BaseAllocator):
    """
    Hedge算法（指数加权平均）
    
    在线学习经典算法，每期根据收益更新权重：
        w_{i,t+1} ∝ w_{i,t} * exp(η * r_{i,t})
    
    有理论保证：对抗性环境下的遗憾界 O(sqrt(T * ln(K)))
    """
    
    def __init__(self, 
                 learning_rate: float = 0.1,
                 forget_factor: float = 1.0):
        """
        Args:
            learning_rate: 学习率 η
            forget_factor: 遗忘因子 γ (0<γ<=1)，用于非平稳环境
        """
        self.eta = learning_rate
        self.gamma = forget_factor
        self.cumulative_losses: Optional[np.ndarray] = None
    
    def allocate(self, 
                 evaluator: StrategyEvaluator,
                 current_weights: Optional[np.ndarray] = None) -> np.ndarray:
        """Hedge分配"""
        n = evaluator.n
        
        # 初始化累积损失
        if self.cumulative_losses is None:
            self.cumulative_losses = np.zeros(n)
        
        # 获取最新收益（作为负损失）
        expected_returns = evaluator.get_expected_returns()
        
        # 更新累积损失（带遗忘因子）
        self.cumulative_losses = self.gamma * self.cumulative_losses - expected_returns
        
        # 计算权重：w_i ∝ exp(-η * L_i)
        weights = np.exp(-self.eta * self.cumulative_losses)
        
        # 归一化
        weights = weights / np.sum(weights)
        
        return weights


class FTRLAllocator(BaseAllocator):
    """
    Follow The Regularized Leader (FTRL)
    
    每期求解：
        w_{t+1} = argmin_{w∈Δ} (sum_{s=1}^t w·r_s + ψ(w))
    
    使用熵正则化：ψ(w) = (1/η) * sum_i w_i * ln(w_i)
    
    等价于带学习率的Hedge，但更适合处理约束。
    """
    
    def __init__(self,
                 learning_rate: float = 0.1,
                 forget_factor: float = 1.0,
                 turnover_penalty: float = 0.0,
                 min_weight: float = 0.0,
                 max_weight: float = 1.0):
        """
        Args:
            learning_rate: 学习率 η
            forget_factor: 遗忘因子
            turnover_penalty: 换手率惩罚系数 λ
            min_weight: 最小权重
            max_weight: 最大权重
        """
        self.eta = learning_rate
        self.gamma = forget_factor
        self.lambda_turnover = turnover_penalty
        self.min_w = min_weight
        self.max_w = max_weight
        
        self.cumulative_rewards: Optional[np.ndarray] = None
    
    def allocate(self, 
                 evaluator: StrategyEvaluator,
                 current_weights: Optional[np.ndarray] = None) -> np.ndarray:
        """FTRL分配"""
        n = evaluator.n
        
        # 初始化累积奖励
        if self.cumulative_rewards is None:
            self.cumulative_rewards = np.zeros(n)
        
        # 获取期望收益
        expected_returns = evaluator.get_expected_returns()
        
        # 更新累积奖励（带遗忘因子）
        self.cumulative_rewards = self.gamma * self.cumulative_rewards + expected_returns
        
        # 如果存在换手率惩罚，调整累积奖励
        if current_weights is not None and self.lambda_turnover > 0:
            # 惩罚与当前权重的偏离
            turnover_cost = self.lambda_turnover * np.abs(current_weights - np.ones(n) / n)
            self.cumulative_rewards -= turnover_cost
        
        # 求解FTRL：带熵正则化的权重
        # 解析解：w_i ∝ exp(η * cumulative_reward_i)
        logits = self.eta * self.cumulative_rewards
        
        # 数值稳定性处理
        logits = logits - np.max(logits)
        weights = np.exp(logits)
        
        # 归一化
        weights = weights / np.sum(weights)
        
        # 应用权重约束
        weights = np.clip(weights, self.min_w, self.max_w)
        weights = weights / np.sum(weights)
        
        return weights


class UCBAllocator(BaseAllocator):
    """
    Upper Confidence Bound (UCB) 分配器
    
    基于贝叶斯DLM的不确定性估计：
        UCB_i = μ_i + c * σ_i
    
    其中c为探索系数，σ_i为后验标准差。
    """
    
    def __init__(self, 
                 exploration_coeff: float = 2.0,
                 min_weight: float = 0.0):
        """
        Args:
            exploration_coeff: 探索系数 c
            min_weight: 最小权重
        """
        self.c = exploration_coeff
        self.min_w = min_weight
    
    def allocate(self, 
                 evaluator: StrategyEvaluator,
                 current_weights: Optional[np.ndarray] = None) -> np.ndarray:
        """UCB分配"""
        expected = evaluator.get_expected_returns()
        uncertainty = evaluator.get_uncertainty()
        
        # UCB得分
        ucb_scores = expected + self.c * uncertainty
        
        # 转换为权重（softmax）
        ucb_scores = ucb_scores - np.max(ucb_scores)
        weights = np.exp(ucb_scores)
        weights = weights / np.sum(weights)
        
        # 应用约束
        weights = np.clip(weights, self.min_w, 1.0)
        weights = weights / np.sum(weights)
        
        return weights


class ThompsonSamplingAllocator(BaseAllocator):
    """
    Thompson Sampling (贝叶斯老虎机)
    
    从每个策略的后验分布采样一个收益值，选择采样值最高的策略。
    可扩展为分配比例：使用采样的softmax。
    """
    
    def __init__(self,
                 temperature: float = 1.0,
                 min_weight: float = 0.0,
                 use_correlation: bool = False):
        """
        Args:
            temperature: softmax温度参数
            min_weight: 最小权重
            use_correlation: 是否考虑策略间相关性
        """
        self.temperature = temperature
        self.min_w = min_weight
        self.use_correlation = use_correlation
    
    def allocate(self, 
                 evaluator: StrategyEvaluator,
                 current_weights: Optional[np.ndarray] = None) -> np.ndarray:
        """Thompson Sampling分配"""
        n = evaluator.n
        
        # 从后验采样
        samples = np.zeros(n)
        for i, dlm in enumerate(evaluator.dlms):
            mu, sigma = dlm.predict(1)
            samples[i] = np.random.normal(mu, sigma)
        
        # 使用softmax转换为权重
        samples = samples / self.temperature
        samples = samples - np.max(samples)
        weights = np.exp(samples)
        weights = weights / np.sum(weights)
        
        # 应用约束
        weights = np.clip(weights, self.min_w, 1.0)
        weights = weights / np.sum(weights)
        
        return weights


class MeanVarianceAllocator(BaseAllocator):
    """
    在线均值-方差优化
    
    基于贝叶斯DLM的期望收益和相关性估计，
    求解Markowitz优化问题。
    """
    
    def __init__(self,
                 risk_aversion: float = 1.0,
                 turnover_penalty: float = 0.0,
                 min_weight: float = 0.0,
                 max_weight: float = 1.0):
        """
        Args:
            risk_aversion: 风险厌恶系数 λ
            turnover_penalty: 换手率惩罚
            min_weight: 最小权重
            max_weight: 最大权重
        """
        self.lambda_risk = risk_aversion
        self.lambda_turnover = turnover_penalty
        self.min_w = min_weight
        self.max_w = max_weight
    
    def allocate(self, 
                 evaluator: StrategyEvaluator,
                 current_weights: Optional[np.ndarray] = None) -> np.ndarray:
        """均值-方差优化分配"""
        n = evaluator.n
        
        # 期望收益和协方差
        mu = evaluator.get_expected_returns()
        Sigma = evaluator.correlation_matrix * np.outer(
            evaluator.get_expected_variances(),
            evaluator.get_expected_variances()
        )
        
        # 确保正定性
        Sigma = Sigma + np.eye(n) * 1e-6
        
        # 解析解（无约束）：w ∝ Σ^{-1} * μ
        try:
            Sigma_inv = np.linalg.inv(Sigma)
            raw_weights = Sigma_inv @ mu
        except np.linalg.LinAlgError:
            # 如果奇异，使用伪逆
            raw_weights = np.linalg.pinv(Sigma) @ mu
        
        # 归一化到概率单纯形
        raw_weights = np.maximum(raw_weights, 0)  # 非负
        if np.sum(raw_weights) > 0:
            weights = raw_weights / np.sum(raw_weights)
        else:
            weights = np.ones(n) / n
        
        # 应用约束
        weights = np.clip(weights, self.min_w, self.max_w)
        weights = weights / np.sum(weights)
        
        return weights


# ============================================================
# 4. 元策略层：预留RL接口
# ============================================================

class MetaPolicy:
    """
    元策略：调整分配器的超参数
    
    预留RL接口，未来可用PPO/A3C训练元策略。
    当前使用简单的规则基方法。
    """
    
    def __init__(self,
                 base_allocator: BaseAllocator,
                 adaptation_rate: float = 0.1):
        """
        Args:
            base_allocator: 基础分配器
            adaptation_rate: 超参数调整速度
        """
        self.base = base_allocator
        self.adaptation_rate = adaptation_rate
        
        # 状态
        self.market_regime: str = "normal"  # normal | volatile | trending
        self.performance_history: list[float] = []
    
    def detect_regime(self,
                      evaluator: StrategyEvaluator) -> str:
        """
        检测市场状态

        基于策略收益分布特征判断市场状态：
        - volatile: 收益波动大，策略分化严重
        - trending: 多数策略同向收益且波动适中
        - normal: 其他情况
        """
        expected = evaluator.get_expected_returns()
        uncertainty = evaluator.get_uncertainty()

        # 波动率指标
        avg_uncertainty = np.mean(uncertainty)

        # 同向性指标
        sign_consensus = abs(np.sum(np.sign(expected))) / len(expected)

        # 趋势强度：期望收益的绝对值之和
        trend_strength = np.sum(np.abs(expected))

        if avg_uncertainty > 0.05 and sign_consensus < 0.7:
            return "volatile"
        elif sign_consensus > 0.7 and trend_strength > 0.005:
            return "trending"
        else:
            return "normal"
    
    def adapt_parameters(self, 
                        evaluator: StrategyEvaluator) -> BaseAllocator:
        """
        根据市场状态调整分配器参数
        
        Returns:
            调整后的分配器
        """
        regime = self.detect_regime(evaluator)
        
        if regime == "volatile":
            # 高波动：增加探索，降低集中度
            if isinstance(self.base, FTRLAllocator):
                self.base.eta = min(0.3, self.base.eta * (1 + self.adaptation_rate))
                self.base.lambda_turnover = min(0.1, self.base.lambda_turnover + 0.01)
            elif isinstance(self.base, UCBAllocator):
                self.base.c = min(5.0, self.base.c * (1 + self.adaptation_rate))
        
        elif regime == "trending":
            # 趋势市：减少探索，增加集中度
            if isinstance(self.base, FTRLAllocator):
                self.base.eta = max(0.01, self.base.eta * (1 - self.adaptation_rate))
                self.base.lambda_turnover = max(0.0, self.base.lambda_turnover - 0.005)
            elif isinstance(self.base, UCBAllocator):
                self.base.c = max(0.5, self.base.c * (1 - self.adaptation_rate))
        
        # normal: 保持当前参数
        
        return self.base


# ============================================================
# 5. 主控制器：策略分配管理器
# ============================================================

class StrategyAllocationManager:
    """
    策略分配管理器
    
    整合评估层和分配层，提供统一的策略权重管理接口。
    """
    
    def __init__(self,
                 strategy_names: list[str],
                 allocator_type: str = "ftrl",
                 dlm_state_variance: float = 0.001,
                 **allocator_kwargs):
        """
        Args:
            strategy_names: 策略名称列表
            allocator_type: 分配器类型
                - 'hedge': Hedge算法
                - 'ftrl': FTRL (默认)
                - 'ucb': UCB
                - 'thompson': Thompson Sampling
                - 'mean_variance': 均值-方差优化
            dlm_state_variance: DLM状态方差
            **allocator_kwargs: 分配器额外参数
        """
        self.names = strategy_names
        self.n = len(strategy_names)
        
        # 评估层
        self.evaluator = StrategyEvaluator(
            n_strategies=self.n,
            strategy_names=self.names,
            state_variance=dlm_state_variance
        )
        
        # 分配层
        allocators = {
            'hedge': HedgeAllocator,
            'ftrl': FTRLAllocator,
            'ucb': UCBAllocator,
            'thompson': ThompsonSamplingAllocator,
            'mean_variance': MeanVarianceAllocator,
        }

        allocator_cls = allocators.get(allocator_type, FTRLAllocator)

        # 过滤 allocator_kwargs，只保留该分配器支持的参数
        import inspect
        sig = inspect.signature(allocator_cls.__init__)
        valid_params = set(sig.parameters.keys()) - {'self'}
        filtered_kwargs = {k: v for k, v in allocator_kwargs.items() if k in valid_params}
        self.allocator = allocator_cls(**filtered_kwargs)
        
        # 元策略
        self.meta_policy = MetaPolicy(self.allocator)
        
        # 状态
        self.current_weights: np.ndarray = np.ones(self.n) / self.n
        self.weight_history: list[tuple[datetime, np.ndarray]] = []
        self.portfolio_returns: list[float] = []
    
    def update(self, 
               strategy_returns: np.ndarray,
               date: Optional[datetime] = None,
               adapt_meta: bool = True) -> np.ndarray:
        """
        更新策略权重
        
        Args:
            strategy_returns: 各策略当日收益 (K,)
            date: 日期
            adapt_meta: 是否启用元策略调整
            
        Returns:
            新权重 (K,)
        """
        # 1. 更新评估层
        self.evaluator.update(strategy_returns, date)
        
        # 2. 计算组合收益
        portfolio_return = np.dot(self.current_weights, strategy_returns)
        self.portfolio_returns.append(portfolio_return)
        
        # 3. 元策略调整（可选）
        if adapt_meta:
            self.meta_policy.adapt_parameters(self.evaluator)
        
        # 4. 分配层计算新权重
        new_weights = self.allocator.allocate(
            self.evaluator,
            current_weights=self.current_weights
        )
        
        # 5. 记录
        self.current_weights = new_weights
        if date is not None:
            self.weight_history.append((date, new_weights.copy()))
        
        return new_weights
    
    def get_weights(self) -> dict[str, float]:
        """获取当前权重字典"""
        return {name: float(w) for name, w in zip(self.names, self.current_weights)}
    
    def get_report(self) -> dict[str, Any]:
        """生成完整报告"""
        report = {
            'current_weights': self.get_weights(),
            'evaluator_report': self.evaluator.get_report(),
            'portfolio_cumulative_return': float(np.sum(self.portfolio_returns)),
            'n_updates': len(self.portfolio_returns),
        }
        
        if len(self.portfolio_returns) > 0:
            report['portfolio_sharpe'] = float(np.mean(self.portfolio_returns) / (np.std(self.portfolio_returns) + 1e-8))
        
        return report
