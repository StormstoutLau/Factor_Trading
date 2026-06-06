"""
元策略假设检验与监控层 (Assumption Monitor)

实现用户提出的"假设检验层"：监控元策略（MAB/在线学习/RL/贝叶斯）的隐含数学假设是否成立，
当检测到假设被违反时，自动退化到更简单的基准策略（等权或风险平价）。

监控维度：
1. 收益分布突变 (CUSUM / 滑动t检验 / KPSS)
2. 策略间相关结构变化 (滚动协方差特征值)
3. 换手率异常 (权重变化率分位数)
4. 后验预测检验 (贝叶斯模型适配度)
5. 通用指标 (有效数量、熵、遗憾)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

class AlertLevel(Enum):
    """预警级别"""
    GREEN = "green"    # 正常
    YELLOW = "yellow"  # 警告
    RED = "red"        # 严重


@dataclass
class AssumptionCheck:
    """假设检验结果"""
    name: str
    level: AlertLevel
    statistic: float
    threshold: float
    p_value: Optional[float] = None
    description: str = ""
    recommended_action: str = ""


@dataclass
class MonitorState:
    """监控层整体状态"""
    checks: list[AssumptionCheck] = field(default_factory=list)
    overall_level: AlertLevel = AlertLevel.GREEN
    should_fallback: bool = False
    fallback_weights: Optional[np.ndarray] = None

    def add_check(self, check: AssumptionCheck):
        self.checks.append(check)
        if check.level == AlertLevel.RED:
            self.overall_level = AlertLevel.RED
            self.should_fallback = True
        elif check.level == AlertLevel.YELLOW and self.overall_level == AlertLevel.GREEN:
            self.overall_level = AlertLevel.YELLOW


# ============================================================
# 1. 收益分布突变检测
# ============================================================

class ReturnDistributionMonitor:
    """
    监控策略收益分布是否发生突变

    检测方法:
    - CUSUM: 累积和控制图，检测均值偏移
    - 滑动t检验: 比较两个窗口的均值差异
    - KPSS: 检验序列是否平稳
    """

    def __init__(self,
                 cusum_threshold: float = 2.0,
                 window_size: int = 30,
                 t_test_threshold: float = 2.5,
                 kpss_threshold: float = 0.05):
        """
        Args:
            cusum_threshold: CUSUM控制限
            window_size: 滑动窗口大小
            t_test_threshold: t检验统计量阈值
            kpss_threshold: KPSS检验p值阈值
        """
        self.cusum_threshold = cusum_threshold
        self.window_size = window_size
        self.t_test_threshold = t_test_threshold
        self.kpss_threshold = kpss_threshold

        # CUSUM状态
        self.cusum_pos: dict[int, float] = {}  # 正向累积和
        self.cusum_neg: dict[int, float] = {}  # 负向累积和
        self.cusum_baseline: dict[int, float] = {}  # 基准均值

    def _cusum_update(self, strategy_idx: int, ret: float) -> tuple[float, float]:
        """更新CUSUM统计量

        使用固定baseline（历史均值），检测相对于历史均值的偏移。
        当累积和超过阈值时触发警报，然后重置。

        Returns:
            (pos_cusum, neg_cusum)
        """
        if strategy_idx not in self.cusum_baseline:
            self.cusum_baseline[strategy_idx] = ret
            self.cusum_pos[strategy_idx] = 0.0
            self.cusum_neg[strategy_idx] = 0.0
            return 0.0, 0.0

        baseline = self.cusum_baseline[strategy_idx]
        diff = ret - baseline

        # 正向累积和
        self.cusum_pos[strategy_idx] = max(0, self.cusum_pos.get(strategy_idx, 0) + diff)
        # 负向累积和
        self.cusum_neg[strategy_idx] = min(0, self.cusum_neg.get(strategy_idx, 0) + diff)

        return self.cusum_pos[strategy_idx], self.cusum_neg[strategy_idx]

    def update_baseline(self, strategy_idx: int, returns_history: list[np.ndarray]):
        """更新CUSUM baseline（定期调用以适应当前环境）"""
        if len(returns_history) >= 10:
            returns_matrix = np.array(returns_history)
            self.cusum_baseline[strategy_idx] = np.mean(returns_matrix[:, strategy_idx])
            # 重置累积和
            self.cusum_pos[strategy_idx] = 0.0
            self.cusum_neg[strategy_idx] = 0.0

    def _rolling_t_test(self, returns: np.ndarray) -> tuple[float, float]:
        """滑动窗口t检验

        Args:
            returns: 收益序列 (T,)

        Returns:
            (t_statistic, p_value)
        """
        if len(returns) < 2 * self.window_size:
            return 0.0, 1.0

        recent = returns[-self.window_size:]
        previous = returns[-2 * self.window_size:-self.window_size]

        t_stat, p_val = stats.ttest_ind(recent, previous, equal_var=False)
        if np.isnan(t_stat):
            return 0.0, 1.0

        return abs(t_stat), p_val

    def _kpss_test(self, returns: np.ndarray) -> tuple[float, float]:
        """KPSS平稳性检验

        Args:
            returns: 收益序列

        Returns:
            (kpss_statistic, p_value)
        """
        if len(returns) < 20:
            return 0.0, 1.0

        try:
            # 简化的KPSS检验实现
            # H0: 序列平稳
            n = len(returns)
            cumsum = np.cumsum(returns - np.mean(returns))
            eta = np.sum(cumsum ** 2) / (n ** 2)
            s2 = np.var(returns, ddof=1)
            if s2 < 1e-12:
                return 0.0, 1.0
            kpss_stat = eta / s2

            # 临界值 (1%, 5%, 10%)
            critical_values = {0.01: 0.739, 0.05: 0.463, 0.10: 0.347}
            p_value = 0.10
            for alpha, crit in sorted(critical_values.items()):
                if kpss_stat > crit:
                    p_value = alpha
                    break

            return kpss_stat, p_value
        except Exception:
            return 0.0, 1.0

    def check(self, returns_history: list[np.ndarray]) -> list[AssumptionCheck]:
        """执行所有收益分布突变检测

        Args:
            returns_history: 历史收益列表，每个元素是 (K,) 的当日收益

        Returns:
            检验结果列表
        """
        checks = []
        if len(returns_history) < self.window_size:
            return checks

        returns_matrix = np.array(returns_history)  # (T, K)
        n_strategies = returns_matrix.shape[1]

        for i in range(n_strategies):
            strategy_returns = returns_matrix[:, i]

            # 1. CUSUM检测
            latest_return = strategy_returns[-1]
            pos_cusum, neg_cusum = self._cusum_update(i, latest_return)
            cusum_max = max(abs(pos_cusum), abs(neg_cusum))

            if cusum_max > self.cusum_threshold:
                level = AlertLevel.RED if cusum_max > 2 * self.cusum_threshold else AlertLevel.YELLOW
                checks.append(AssumptionCheck(
                    name=f"CUSUM_策略{i}",
                    level=level,
                    statistic=cusum_max,
                    threshold=self.cusum_threshold,
                    description=f"策略{i}收益CUSUM统计量{cusum_max:.4f}超过阈值",
                    recommended_action="收益分布可能发生突变，考虑重置该策略评估"
                ))

            # 2. 滑动t检验
            t_stat, p_val = self._rolling_t_test(strategy_returns)
            if t_stat > self.t_test_threshold:
                level = AlertLevel.RED if t_stat > 3.5 else AlertLevel.YELLOW
                checks.append(AssumptionCheck(
                    name=f"滑动t检验_策略{i}",
                    level=level,
                    statistic=t_stat,
                    threshold=self.t_test_threshold,
                    p_value=p_val,
                    description=f"策略{i}近期收益均值显著变化 (t={t_stat:.2f})",
                    recommended_action="策略表现可能发生结构性变化"
                ))

            # 3. KPSS检验
            kpss_stat, kpss_p = self._kpss_test(strategy_returns)
            if kpss_p < self.kpss_threshold:
                level = AlertLevel.RED if kpss_p < 0.01 else AlertLevel.YELLOW
                checks.append(AssumptionCheck(
                    name=f"KPSS_策略{i}",
                    level=level,
                    statistic=kpss_stat,
                    threshold=self.kpss_threshold,
                    p_value=kpss_p,
                    description=f"策略{i}收益序列非平稳 (KPSS p={kpss_p:.4f})",
                    recommended_action="收益分布非平稳，MAB假设被违反"
                ))

        return checks


# ============================================================
# 2. 策略间相关结构变化监控
# ============================================================

class CorrelationStructureMonitor:
    """
    监控策略间相关性结构是否发生显著变化

    检测方法:
    - 滚动协方差矩阵特征值分解
    - 最大特征值占比变化
    - 条件数监控
    """

    def __init__(self,
                 window_size: int = 60,
                 eigenvalue_change_threshold: float = 2.0,
                 condition_number_threshold: float = 100.0):
        """
        Args:
            window_size: 滚动窗口
            eigenvalue_change_threshold: 最大特征值占比变化阈值（标准差倍数）
            condition_number_threshold: 条件数阈值
        """
        self.window_size = window_size
        self.eigenvalue_change_threshold = eigenvalue_change_threshold
        self.condition_number_threshold = condition_number_threshold

        self.eigenvalue_history: list[tuple[float, float]] = []  # (max_eigen_ratio, condition_num)

    def check(self, returns_history: list[np.ndarray]) -> list[AssumptionCheck]:
        """检测相关结构变化

        Args:
            returns_history: 历史收益列表

        Returns:
            检验结果列表
        """
        checks = []
        if len(returns_history) < self.window_size + 10:
            return checks

        returns_matrix = np.array(returns_history)
        recent_returns = returns_matrix[-self.window_size:]

        # 计算协方差矩阵
        cov_matrix = np.cov(recent_returns.T)
        cov_matrix = cov_matrix + np.eye(cov_matrix.shape[0]) * 1e-8  # 正则化

        # 特征值分解
        eigenvalues = np.linalg.eigvalsh(cov_matrix)
        eigenvalues = np.maximum(eigenvalues, 1e-10)

        # 最大特征值占比
        max_eigen_ratio = np.max(eigenvalues) / np.sum(eigenvalues)

        # 条件数
        condition_number = np.max(eigenvalues) / np.min(eigenvalues)

        self.eigenvalue_history.append((max_eigen_ratio, condition_number))

        # 检测最大特征值占比的突变
        if len(self.eigenvalue_history) >= 20:
            ratios = [r for r, _ in self.eigenvalue_history[-20:]]
            mean_ratio = np.mean(ratios[:-1])
            std_ratio = np.std(ratios[:-1]) + 1e-8
            z_score = abs(ratios[-1] - mean_ratio) / std_ratio

            if z_score > self.eigenvalue_change_threshold:
                level = AlertLevel.RED if z_score > 3.0 else AlertLevel.YELLOW
                checks.append(AssumptionCheck(
                    name="特征值结构变化",
                    level=level,
                    statistic=z_score,
                    threshold=self.eigenvalue_change_threshold,
                    description=f"最大特征值占比突变 (z={z_score:.2f})，策略间相关性结构可能改变",
                    recommended_action="切换到风险平价或等权分配"
                ))

        # 检测条件数异常
        if condition_number > self.condition_number_threshold:
            level = AlertLevel.RED if condition_number > 2 * self.condition_number_threshold else AlertLevel.YELLOW
            checks.append(AssumptionCheck(
                name="协方差条件数异常",
                level=level,
                statistic=condition_number,
                threshold=self.condition_number_threshold,
                description=f"协方差矩阵条件数{condition_number:.1f}过高，策略间高度共线",
                recommended_action="增加分散化，避免均值-方差优化"
            ))

        return checks


# ============================================================
# 3. 换手率异常与过拟合检测
# ============================================================

class TurnoverMonitor:
    """
    监控权重换手率是否异常

    检测方法:
    - 权重变化率超过历史95分位数
    - 有效数量骤降
    - 权重熵的突变
    """

    def __init__(self,
                 turnover_percentile: float = 95.0,
                 entropy_drop_threshold: float = 0.3,
                 min_effective_count: float = 2.0):
        """
        Args:
            turnover_percentile: 换手率分位数阈值
            entropy_drop_threshold: 熵下降比例阈值
            min_effective_count: 最小有效策略数
        """
        self.turnover_percentile = turnover_percentile
        self.entropy_drop_threshold = entropy_drop_threshold
        self.min_effective_count = min_effective_count

        self.turnover_history: list[float] = []
        self.entropy_history: list[float] = []

    def _calculate_turnover(self, w_old: np.ndarray, w_new: np.ndarray) -> float:
        """计算换手率"""
        return np.sum(np.abs(w_new - w_old)) / 2

    def _calculate_entropy(self, weights: np.ndarray) -> float:
        """计算权重熵"""
        w = weights[weights > 1e-10]
        if len(w) == 0:
            return 0.0
        return -np.sum(w * np.log(w))

    def _effective_count(self, weights: np.ndarray) -> float:
        """计算有效策略数"""
        entropy = self._calculate_entropy(weights)
        return np.exp(entropy)

    def check(self,
              current_weights: np.ndarray,
              previous_weights: Optional[np.ndarray] = None) -> list[AssumptionCheck]:
        """检测换手率异常

        Args:
            current_weights: 当前权重
            previous_weights: 上一期权重

        Returns:
            检验结果列表
        """
        checks = []

        # 1. 换手率检测
        if previous_weights is not None:
            turnover = self._calculate_turnover(previous_weights, current_weights)
            self.turnover_history.append(turnover)

            if len(self.turnover_history) >= 20:
                threshold = np.percentile(self.turnover_history[:-1], self.turnover_percentile)
                if turnover > threshold:
                    level = AlertLevel.RED if turnover > 1.5 * threshold else AlertLevel.YELLOW
                    checks.append(AssumptionCheck(
                        name="换手率异常",
                        level=level,
                        statistic=turnover,
                        threshold=threshold,
                        description=f"权重换手率{turnover:.4f}超过历史{self.turnover_percentile:.0f}分位数",
                        recommended_action="增加交易成本惩罚系数"
                    ))

        # 2. 有效数量检测
        eff_count = self._effective_count(current_weights)
        if eff_count < self.min_effective_count:
            checks.append(AssumptionCheck(
                name="有效策略数过低",
                level=AlertLevel.RED,
                statistic=eff_count,
                threshold=self.min_effective_count,
                description=f"有效策略数{eff_count:.2f}低于阈值，权重过度集中",
                recommended_action="强制分散化，设置最小权重约束"
            ))

        # 3. 熵突变检测
        entropy = self._calculate_entropy(current_weights)
        self.entropy_history.append(entropy)

        if len(self.entropy_history) >= 10:
            prev_entropy = self.entropy_history[-2]
            if prev_entropy > 1e-10:
                entropy_drop = (prev_entropy - entropy) / prev_entropy
                if entropy_drop > self.entropy_drop_threshold:
                    checks.append(AssumptionCheck(
                        name="权重熵骤降",
                        level=AlertLevel.YELLOW,
                        statistic=entropy_drop,
                        threshold=self.entropy_drop_threshold,
                        description=f"权重熵骤降{entropy_drop:.1%}，可能过拟合近期表现",
                        recommended_action="增加正则化，降低学习率"
                    ))

        return checks


# ============================================================
# 4. 后验预测检验与模型证据监控
# ============================================================

class BayesianModelMonitor:
    """
    监控贝叶斯模型的适配度

    检测方法:
    - 后验预测检验 (PPC): 实际观测在预测分布中的位置
    - 累积对数似然监控
    - Kalman创新序列白噪声检验
    """

    def __init__(self,
                 ppc_outlier_threshold: float = 0.05,
                 loglikelihood_drop_threshold: float = 2.0,
                 innovation_ljung_box_threshold: float = 0.05):
        """
        Args:
            ppc_outlier_threshold: 后验预测异常值比例阈值
            loglikelihood_drop_threshold: 对数似然下降阈值
            innovation_ljung_box_threshold: Ljung-Box检验p值阈值
        """
        self.ppc_outlier_threshold = ppc_outlier_threshold
        self.loglikelihood_drop_threshold = loglikelihood_drop_threshold
        self.innovation_ljung_box_threshold = innovation_ljung_box_threshold

        self.loglikelihood_history: list[float] = []
        self.innovation_history: dict[int, list[float]] = {}
        self.ppc_violations: dict[int, int] = {}
        self.ppc_total: dict[int, int] = {}

    def _gaussian_loglikelihood(self, obs: float, mean: float, std: float) -> float:
        """计算高斯对数似然"""
        if std < 1e-10:
            return -np.inf
        return -0.5 * np.log(2 * np.pi * std ** 2) - 0.5 * ((obs - mean) / std) ** 2

    def _ljung_box(self, residuals: list[float], lags: int = 5) -> tuple[float, float]:
        """简化的Ljung-Box检验"""
        if len(residuals) < lags + 5:
            return 0.0, 1.0

        n = len(residuals)
        r = np.array(residuals)
        r_mean = np.mean(r)
        r_centered = r - r_mean

        autocorrs = []
        for lag in range(1, lags + 1):
            c_lag = np.sum(r_centered[:-lag] * r_centered[lag:]) / n
            c_0 = np.sum(r_centered ** 2) / n
            if c_0 > 1e-10:
                autocorrs.append(c_lag / c_0)
            else:
                autocorrs.append(0.0)

        lb_stat = n * (n + 2) * sum(a ** 2 / (n - i) for i, a in enumerate(autocorrs, 1))
        p_value = 1 - stats.chi2.cdf(lb_stat, lags)

        return lb_stat, p_value

    def check(self,
              returns_history: list[np.ndarray],
              predicted_means: np.ndarray,
              predicted_stds: np.ndarray,
              innovations: Optional[dict[int, list[float]]] = None) -> list[AssumptionCheck]:
        """执行贝叶斯模型监控

        Args:
            returns_history: 历史收益
            predicted_means: 预测均值 (K,)
            predicted_stds: 预测标准差 (K,)
            innovations: Kalman创新序列 {strategy_idx: [innovations]}

        Returns:
            检验结果列表
        """
        checks = []
        if len(returns_history) < 10:
            return checks

        latest_returns = returns_history[-1]
        n_strategies = len(latest_returns)

        # 1. 后验预测检验
        outlier_count = 0
        for i in range(n_strategies):
            z_score = abs(latest_returns[i] - predicted_means[i]) / (predicted_stds[i] + 1e-10)
            is_outlier = z_score > 2.0  # 95%置信区间外

            self.ppc_violations[i] = self.ppc_violations.get(i, 0) + int(is_outlier)
            self.ppc_total[i] = self.ppc_total.get(i, 0) + 1

            if self.ppc_total[i] >= 20:
                outlier_ratio = self.ppc_violations[i] / self.ppc_total[i]
                if outlier_ratio > self.ppc_outlier_threshold:
                    checks.append(AssumptionCheck(
                        name=f"PPC_策略{i}",
                        level=AlertLevel.RED,
                        statistic=outlier_ratio,
                        threshold=self.ppc_outlier_threshold,
                        description=f"策略{i}后验预测异常比例{outlier_ratio:.1%}，模型可能misspecified",
                        recommended_action="检查先验和似然函数设定"
                    ))

            # 2. 累积对数似然
            loglik = self._gaussian_loglikelihood(
                latest_returns[i], predicted_means[i], predicted_stds[i]
            )
            self.loglikelihood_history.append(loglik)

        if len(self.loglikelihood_history) >= 20:
            recent_ll = np.mean(self.loglikelihood_history[-10:])
            previous_ll = np.mean(self.loglikelihood_history[-20:-10])
            ll_drop = previous_ll - recent_ll

            if ll_drop > self.loglikelihood_drop_threshold:
                checks.append(AssumptionCheck(
                    name="对数似然下降",
                    level=AlertLevel.YELLOW,
                    statistic=ll_drop,
                    threshold=self.loglikelihood_drop_threshold,
                    description=f"近期对数似然均值下降{ll_drop:.4f}，模型拟合能力退化",
                    recommended_action="考虑更换模型或增加正则化"
                ))

        # 3. 创新序列白噪声检验
        if innovations:
            for i, innov_list in innovations.items():
                if len(innov_list) >= 20:
                    lb_stat, lb_p = self._ljung_box(innov_list)
                    if lb_p < self.innovation_ljung_box_threshold:
                        checks.append(AssumptionCheck(
                            name=f"创新序列自相关_策略{i}",
                            level=AlertLevel.YELLOW,
                            statistic=lb_stat,
                            threshold=self.innovation_ljung_box_threshold,
                            p_value=lb_p,
                            description=f"策略{i}Kalman创新序列存在自相关，DLM假设被违反",
                            recommended_action="增加状态方差或检查模型设定"
                        ))

        return checks


# ============================================================
# 5. 通用指标监控
# ============================================================

class UniversalMonitor:
    """
    跨框架通用监控指标

    - 累计遗憾
    - 权重向量熵
    - 瞬时遗憾
    """

    def __init__(self,
                 regret_window: int = 30,
                 max_regret_growth_rate: float = 0.001):
        """
        Args:
            regret_window: 遗憾计算窗口
            max_regret_growth_rate: 最大遗憾增长率
        """
        self.regret_window = regret_window
        self.max_regret_growth_rate = max_regret_growth_rate

        self.cumulative_regret: float = 0.0
        self.regret_history: list[float] = []
        self.best_fixed_return: float = 0.0

    def check(self,
              returns_history: list[np.ndarray],
              weights_history: list[np.ndarray]) -> list[AssumptionCheck]:
        """通用指标检测

        Args:
            returns_history: 历史收益
            weights_history: 历史权重

        Returns:
            检验结果列表
        """
        checks = []
        if len(returns_history) < 2 or len(weights_history) < 2:
            return checks

        returns_matrix = np.array(returns_history)
        weights_matrix = np.array(weights_history)

        # 1. 累计遗憾
        portfolio_returns = np.sum(weights_matrix * returns_matrix, axis=1)

        # 最优固定策略（事后最优）
        cumulative_returns = np.cumsum(returns_matrix, axis=0)
        best_strategy_cumret = np.max(cumulative_returns[-1])
        actual_cumret = np.sum(portfolio_returns)
        self.cumulative_regret = best_strategy_cumret - actual_cumret
        self.regret_history.append(self.cumulative_regret)

        if len(self.regret_history) >= self.regret_window:
            recent_regret_growth = (
                self.regret_history[-1] - self.regret_history[-self.regret_window]
            ) / self.regret_window

            if recent_regret_growth > self.max_regret_growth_rate:
                checks.append(AssumptionCheck(
                    name="累计遗憾增长",
                    level=AlertLevel.YELLOW,
                    statistic=recent_regret_growth,
                    threshold=self.max_regret_growth_rate,
                    description=f"最近{self.regret_window}期遗憾增长率{recent_regret_growth:.6f}",
                    recommended_action="元策略可能失效，考虑回退到等权"
                ))

        # 2. 瞬时遗憾
        if len(portfolio_returns) > 0:
            latest_portfolio_ret = portfolio_returns[-1]
            latest_best_ret = np.max(returns_matrix[-1])
            instantaneous_regret = latest_best_ret - latest_portfolio_ret

            if instantaneous_regret > 0.02:  # 单日落后2%
                checks.append(AssumptionCheck(
                    name="瞬时遗憾过大",
                    level=AlertLevel.YELLOW,
                    statistic=instantaneous_regret,
                    threshold=0.02,
                    description=f"单日遗憾{instantaneous_regret:.4f}，组合大幅落后最佳策略",
                    recommended_action="检查是否存在异常权重配置"
                ))

        return checks


# ============================================================
# 6. 假设检验层主控制器
# ============================================================

class AssumptionMonitorLayer:
    """
    假设检验层主控制器

    整合所有监控模块，当检测到假设被违反时自动触发退化机制。
    """

    def __init__(self,
                 n_strategies: int,
                 enable_return_monitor: bool = True,
                 enable_correlation_monitor: bool = True,
                 enable_turnover_monitor: bool = True,
                 enable_bayesian_monitor: bool = True,
                 enable_universal_monitor: bool = True,
                 fallback_strategy: str = "equal_weight"):
        """
        Args:
            n_strategies: 策略数量
            enable_return_monitor: 启用收益分布监控
            enable_correlation_monitor: 启用相关结构监控
            enable_turnover_monitor: 启用换手率监控
            enable_bayesian_monitor: 启用贝叶斯模型监控
            enable_universal_monitor: 启用通用指标监控
            fallback_strategy: 退化策略 ('equal_weight' | 'risk_parity')
        """
        self.n = n_strategies
        self.fallback_strategy = fallback_strategy

        self.return_monitor = ReturnDistributionMonitor() if enable_return_monitor else None
        self.correlation_monitor = CorrelationStructureMonitor() if enable_correlation_monitor else None
        self.turnover_monitor = TurnoverMonitor() if enable_turnover_monitor else None
        self.bayesian_monitor = BayesianModelMonitor() if enable_bayesian_monitor else None
        self.universal_monitor = UniversalMonitor() if enable_universal_monitor else None

        self.returns_history: list[np.ndarray] = []
        self.weights_history: list[np.ndarray] = []
        self.check_history: list[MonitorState] = []

    def _get_fallback_weights(self) -> np.ndarray:
        """获取退化权重"""
        if self.fallback_strategy == "equal_weight":
            return np.ones(self.n) / self.n
        elif self.fallback_strategy == "risk_parity":
            # 简化的风险平价：使用历史波动率倒数加权
            if len(self.returns_history) >= 10:
                returns_matrix = np.array(self.returns_history[-60:])
                vols = np.std(returns_matrix, axis=0) + 1e-10
                inv_vols = 1.0 / vols
                return inv_vols / np.sum(inv_vols)
            return np.ones(self.n) / self.n
        else:
            return np.ones(self.n) / self.n

    def monitor(self,
                current_weights: np.ndarray,
                strategy_returns: np.ndarray,
                predicted_means: Optional[np.ndarray] = None,
                predicted_stds: Optional[np.ndarray] = None,
                innovations: Optional[dict[int, list[float]]] = None) -> MonitorState:
        """执行全面监控

        Args:
            current_weights: 当前权重
            strategy_returns: 当日策略收益
            predicted_means: 预测均值（贝叶斯监控需要）
            predicted_stds: 预测标准差（贝叶斯监控需要）
            innovations: Kalman创新序列

        Returns:
            监控状态
        """
        self.returns_history.append(strategy_returns.copy())
        self.weights_history.append(current_weights.copy())

        state = MonitorState()
        state.fallback_weights = self._get_fallback_weights()

        # 1. 收益分布监控
        if self.return_monitor and len(self.returns_history) >= self.return_monitor.window_size:
            checks = self.return_monitor.check(self.returns_history)
            for check in checks:
                state.add_check(check)

        # 2. 相关结构监控
        if self.correlation_monitor:
            checks = self.correlation_monitor.check(self.returns_history)
            for check in checks:
                state.add_check(check)

        # 3. 换手率监控
        if self.turnover_monitor:
            prev_weights = self.weights_history[-2] if len(self.weights_history) >= 2 else None
            checks = self.turnover_monitor.check(current_weights, prev_weights)
            for check in checks:
                state.add_check(check)

        # 4. 贝叶斯模型监控
        if self.bayesian_monitor and predicted_means is not None and predicted_stds is not None:
            checks = self.bayesian_monitor.check(
                self.returns_history, predicted_means, predicted_stds, innovations
            )
            for check in checks:
                state.add_check(check)

        # 5. 通用指标监控
        if self.universal_monitor:
            checks = self.universal_monitor.check(self.returns_history, self.weights_history)
            for check in checks:
                state.add_check(check)

        self.check_history.append(state)

        # 记录日志
        if state.should_fallback:
            logger.warning(
                f"[假设检验层] 检测到假设违反！级别: {state.overall_level.value}，"
                f"触发退化到 {self.fallback_strategy}"
            )
            for check in state.checks:
                if check.level in (AlertLevel.YELLOW, AlertLevel.RED):
                    logger.warning(f"  - {check.name}: {check.description}")
        elif state.overall_level == AlertLevel.YELLOW:
            logger.info(f"[假设检验层] 警告级别检测，共{len(state.checks)}项异常")

        return state

    def get_summary(self) -> dict[str, Any]:
        """获取监控摘要"""
        if not self.check_history:
            return {}

        red_count = sum(
            1 for s in self.check_history if s.overall_level == AlertLevel.RED
        )
        yellow_count = sum(
            1 for s in self.check_history if s.overall_level == AlertLevel.YELLOW
        )
        fallback_count = sum(1 for s in self.check_history if s.should_fallback)

        return {
            'total_checks': len(self.check_history),
            'red_alerts': red_count,
            'yellow_alerts': yellow_count,
            'fallback_triggered': fallback_count,
            'fallback_ratio': fallback_count / len(self.check_history),
            'latest_level': self.check_history[-1].overall_level.value,
        }
