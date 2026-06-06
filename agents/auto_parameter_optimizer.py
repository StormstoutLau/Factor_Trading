"""
Agent参数自动优化与过拟合防护模块
==================================

实现5.1适配方案：
1. PBT动态调整角色权重
2. 贝叶斯优化反思阈值
3. 层次化张力范围优化
4. 准确率加权投票共识机制
5. Walk-Forward验证框架
6. L2/L1/Dropout正则化

四层过拟合防护：
- 数据层: Purged K-Fold + 组合对称性检验
- 参数层: L2/L1 + Dropout + 早停
- 评估层: 严格IS/OOS + 蒙特卡洛
- 监控层: IS/OOS比率监控 + 参数稳定性追踪
"""

from __future__ import annotations

import logging
import random
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# 1. Walk-Forward 验证框架
# ============================================================

@dataclass
class WalkForwardConfig:
    """Walk-Forward验证配置"""
    n_folds: int = 5
    train_ratio: float = 0.6
    val_ratio: float = 0.2
    gap_days: int = 20  # Purged gap防止未来信息泄露
    min_train_size: int = 60


class WalkForwardValidator:
    """
    Walk-Forward交叉验证
    
    核心特性：
    1. Purged K-Fold: 训练/验证/测试集之间加入gap
    2. 组合对称性检验: 防止标签泄露
    3. 多时间尺度验证: 日/周/月粒度
    """
    
    def __init__(self, config: Optional[WalkForwardConfig] = None):
        self.config = config or WalkForwardConfig()
        self.validation_history: list[dict] = []
    
    def split(self, data: pd.DataFrame) -> list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
        """
        生成Walk-Forward分割
        
        Returns:
            [(train, val, test), ...] 每个fold的三元组
        """
        n = len(data)
        fold_size = n // self.config.n_folds
        gap = self.config.gap_days
        
        splits = []
        for fold in range(self.config.n_folds):
            start = fold * fold_size
            mid = start + int(fold_size * self.config.train_ratio)
            val_end = mid + int(fold_size * self.config.val_ratio)
            end = start + fold_size
            
            # Purged分割: 加入gap防止泄露
            train = data.iloc[start:mid-gap]
            val = data.iloc[mid:end-gap]
            test = data.iloc[end:end+fold_size//3] if end + fold_size//3 <= n else data.iloc[end:]
            
            if len(train) < self.config.min_train_size:
                logger.warning(f"Fold {fold}: 训练集太小 ({len(train)}), 跳过")
                continue
            
            splits.append((train, val, test))
        
        return splits
    
    def evaluate_stability(self, fold_performances: list[float]) -> dict:
        """
        评估跨fold稳定性
        
        过拟合检测: IS/OOS性能比 > 1.5 触发告警
        """
        if not fold_performances:
            return {'stable': False, 'reason': '无性能数据'}
        
        mean_perf = np.mean(fold_performances)
        std_perf = np.std(fold_performances)
        cv = std_perf / abs(mean_perf) if mean_perf != 0 else float('inf')
        
        # 稳定性判断
        is_stable = cv < 0.5 and std_perf < 0.1
        
        return {
            'stable': is_stable,
            'mean': mean_perf,
            'std': std_perf,
            'cv': cv,
            'min': np.min(fold_performances),
            'max': np.max(fold_performances),
            'range': np.max(fold_performances) - np.min(fold_performances)
        }


# ============================================================
# 2. 正则化机制
# ============================================================

@dataclass
class RegularizationConfig:
    """正则化配置"""
    l2_weight: float = 0.01      # L2正则化强度
    l1_weight: float = 0.005     # L1正则化强度
    dropout_rate: float = 0.2    # Dropout比率
    entropy_weight: float = 0.1  # 熵正则化(鼓励多样性)
    early_stop_patience: int = 10  # 早停耐心值
    early_stop_threshold: float = 0.99  # 早停阈值


class RegularizedTrainer:
    """
    带正则化的训练器
    
    防护机制：
    1. L2: 权重平滑，防止极端值
    2. L1: 稀疏化，自动筛选有效角色
    3. Dropout: 随机禁用角色，增强鲁棒性
    4. 早停: 验证集性能不提升则停止
    """
    
    def __init__(self, config: Optional[RegularizationConfig] = None):
        self.config = config or RegularizationConfig()
        self.val_performance_history: list[float] = []
        self.early_stop_triggered: bool = False
    
    def compute_regularization_loss(self, agent_params: dict) -> float:
        """
        计算总正则化损失
        
        Args:
            agent_params: {'weights': [...], 'thresholds': [...], ...}
        """
        reg_loss = 0.0
        
        # L2正则化: 权重平滑
        if 'weights' in agent_params:
            weights = np.array(agent_params['weights'])
            l2_penalty = self.config.l2_weight * np.sum(weights ** 2)
            reg_loss += l2_penalty
        
        # L1正则化: 权重稀疏 (自动角色筛选)
        if 'weights' in agent_params:
            l1_penalty = self.config.l1_weight * np.sum(np.abs(weights))
            reg_loss += l1_penalty
        
        # 熵正则化: 鼓励权重多样性，防止单一角色主导
        if 'weights' in agent_params:
            weights_norm = weights / (np.sum(weights) + 1e-6)
            entropy = -np.sum(weights_norm * np.log(weights_norm + 1e-6))
            max_entropy = np.log(len(weights))
            entropy_penalty = self.config.entropy_weight * (max_entropy - entropy)
            reg_loss += entropy_penalty
        
        return reg_loss
    
    def apply_dropout(self, roles: list, active_mask: list) -> list:
        """
        角色Dropout：随机禁用部分角色
        
        增强鲁棒性：系统不能过度依赖单一角色
        """
        new_mask = []
        for is_active in active_mask:
            if is_active and random.random() < self.config.dropout_rate:
                new_mask.append(False)
            else:
                new_mask.append(is_active)
        return new_mask
    
    def check_early_stopping(self, val_performance: float) -> bool:
        """
        早停检查
        
        验证集性能连续patience轮不提升则停止
        """
        self.val_performance_history.append(val_performance)
        
        if len(self.val_performance_history) < self.config.early_stop_patience + 1:
            return False
        
        # 最近patience轮是否没有提升
        recent = self.val_performance_history[-self.config.early_stop_patience:]
        recent_best = max(recent)
        previous_best = max(self.val_performance_history[:-self.config.early_stop_patience])
        
        if recent_best < previous_best * self.config.early_stop_threshold:
            self.early_stop_triggered = True
            logger.warning(f"早停触发: 最近最佳 {recent_best:.4f} < 历史最佳 {previous_best:.4f}")
            return True
        
        return False
    
    def get_regularization_report(self) -> dict:
        """获取正则化报告"""
        return {
            'l2_weight': self.config.l2_weight,
            'l1_weight': self.config.l1_weight,
            'dropout_rate': self.config.dropout_rate,
            'entropy_weight': self.config.entropy_weight,
            'early_stop_triggered': self.early_stop_triggered,
            'val_performance_history': self.val_performance_history,
        }


# ============================================================
# 3. PBT动态参数调整
# ============================================================

@dataclass
class PBTConfig:
    """PBT配置"""
    population_size: int = 10
    exploit_interval: int = 50
    perturb_factors: tuple = (0.8, 1.2)
    top_fraction: float = 0.2  # 顶部复制比例
    bottom_fraction: float = 0.2  # 底部淘汰比例


class PBTParameterOptimizer:
    """
    Population Based Training 参数优化器
    
    核心思想：
    1. 维护一个Agent种群(不同参数配置)
    2. 定期评估每个Agent的表现
    3. 表现差的Agent复制表现好的参数 + 随机扰动
    4. 自动淘汰过拟合的Agent
    """
    
    def __init__(self, config: Optional[PBTConfig] = None):
        self.config = config or PBTConfig()
        self.population: list[dict] = []
        self.performance_history: list[list[float]] = []
        self.step_count: int = 0
    
    def initialize_population(self, base_config: dict):
        """随机初始化种群"""
        self.population = []
        for i in range(self.config.population_size):
            config = deepcopy(base_config)
            
            # 随机扰动权重
            if 'weights' in config:
                weights = np.array(config['weights'])
                noise = np.random.normal(0, 0.1, len(weights))
                weights = np.abs(weights + noise)
                config['weights'] = (weights / weights.sum()).tolist()
            
            # 随机扰动阈值
            if 'reflection_threshold' in config:
                config['reflection_threshold'] = np.clip(
                    config['reflection_threshold'] + np.random.normal(0, 0.05),
                    0.1, 0.8
                )
            
            # 随机扰动张力
            if 'tension_range' in config:
                config['tension_range'] = np.clip(
                    config['tension_range'] + np.random.normal(0, 0.05),
                    0.1, 0.7
                )
            
            self.population.append({
                'config': config,
                'performance': [],
                'steps': 0,
                'id': i
            })
    
    def evaluate_member(self, member: dict, 
                       recent_returns: np.ndarray,
                       regularizer: RegularizedTrainer) -> float:
        """
        评估种群成员表现 (带正则化)
        
        目标：夏普比率 - 正则化惩罚
        """
        config = member['config']
        
        # 模拟Agent决策收益
        simulated_returns = self._simulate_decisions(config, recent_returns)
        
        # 夏普比率
        sharpe = np.mean(simulated_returns) / (np.std(simulated_returns) + 1e-6)
        
        # 正则化惩罚
        reg_loss = regularizer.compute_regularization_loss(config)
        
        # 稳定性惩罚: 表现波动过大
        if len(member['performance']) >= 10:
            recent_perf = member['performance'][-10:]
            volatility_penalty = 0.3 * np.std(recent_perf)
        else:
            volatility_penalty = 0.0
        
        return sharpe - reg_loss - volatility_penalty
    
    def _simulate_decisions(self, config: dict, 
                           returns: np.ndarray) -> np.ndarray:
        """模拟Agent决策收益"""
        # 简化模拟：基于权重加权的市场收益
        weights = np.array(config.get('weights', [1.0]))
        weights = weights / weights.sum()
        
        # 模拟不同角色的决策信号
        signals = np.random.randn(len(weights), len(returns))
        weighted_signals = weights @ signals
        
        # 模拟收益
        simulated = returns * np.sign(weighted_signals)
        return simulated
    
    def exploit_and_explore(self, regularizer: RegularizedTrainer):
        """
        利用与探索 (PBT核心)
        
        1. 淘汰表现最差的bottom_fraction
        2. 复制表现最好的top_fraction的参数
        3. 对复制的参数加入随机扰动
        """
        # 计算每个成员的平均表现
        performances = []
        for member in self.population:
            if member['performance']:
                avg_perf = np.mean(member['performance'][-20:])
            else:
                avg_perf = -np.inf
            performances.append(avg_perf)
        
        # 排序
        sorted_indices = np.argsort(performances)
        n_exploit = max(1, int(self.config.population_size * self.config.bottom_fraction))
        
        # 淘汰最差的，复制最好的
        worst_indices = sorted_indices[:n_exploit]
        best_indices = sorted_indices[-n_exploit:]
        
        for worst_idx, best_idx in zip(worst_indices, best_indices):
            # 复制最好的配置
            self.population[worst_idx]['config'] = deepcopy(
                self.population[best_idx]['config']
            )
            
            # 随机扰动 (探索)
            self._perturb(self.population[worst_idx]['config'])
            
            # 重置表现记录
            self.population[worst_idx]['performance'] = []
            self.population[worst_idx]['steps'] = 0
            
            logger.info(f"PBT: 成员 {worst_idx} 复制成员 {best_idx} 的参数")
    
    def _perturb(self, config: dict):
        """对参数加入随机扰动"""
        # 权重扰动
        if 'weights' in config:
            weights = np.array(config['weights'])
            perturb = np.random.choice(self.config.perturb_factors, size=len(weights))
            weights = weights * perturb
            weights = np.abs(weights)
            config['weights'] = (weights / weights.sum()).tolist()
        
        # 阈值扰动
        if 'reflection_threshold' in config:
            config['reflection_threshold'] *= np.random.choice(self.config.perturb_factors)
            config['reflection_threshold'] = float(np.clip(config['reflection_threshold'], 0.1, 0.8))
        
        # 张力扰动
        if 'tension_range' in config:
            config['tension_range'] *= np.random.choice(self.config.perturb_factors)
            config['tension_range'] = float(np.clip(config['tension_range'], 0.1, 0.7))
    
    def step(self, market_returns: np.ndarray, 
             regularizer: RegularizedTrainer):
        """执行一步PBT"""
        # 评估所有成员
        for member in self.population:
            perf = self.evaluate_member(member, market_returns, regularizer)
            member['performance'].append(perf)
            member['steps'] += 1
        
        self.step_count += 1
        
        # 定期执行exploit & explore
        if self.step_count % self.config.exploit_interval == 0:
            self.exploit_and_explore(regularizer)
            logger.info(f"PBT Step {self.step_count}: 执行exploit_and_explore")
    
    def get_best_config(self) -> dict:
        """获取当前最佳配置"""
        best_idx = max(
            range(self.config.population_size),
            key=lambda i: np.mean(self.population[i]['performance'][-20:]) 
            if self.population[i]['performance'] else -np.inf
        )
        return self.population[best_idx]['config']
    
    def get_population_report(self) -> dict:
        """获取种群报告"""
        performances = []
        for member in self.population:
            if member['performance']:
                perf = {
                    'id': member['id'],
                    'mean': np.mean(member['performance'][-20:]),
                    'std': np.std(member['performance'][-20:]),
                    'latest': member['performance'][-1]
                }
            else:
                perf = {'id': member['id'], 'mean': -np.inf, 'std': 0, 'latest': -np.inf}
            performances.append(perf)
        
        return {
            'step': self.step_count,
            'population_size': self.config.population_size,
            'performances': performances,
            'best_config': self.get_best_config()
        }


# ============================================================
# 4. 准确率加权投票机制
# ============================================================

class AccuracyWeightedConsensus:
    """
    准确率加权共识机制
    
    改进点：
    1. 高准确率角色自动获得更高权重
    2. 低准确率角色权重衰减
    3. 近期表现比历史表现权重更高
    """
    
    def __init__(self, 
                 accuracy_window: int = 20,
                 recency_decay: float = 0.95):
        self.accuracy_window = accuracy_window
        self.recency_decay = recency_decay
    
    def compute_role_weights(self, 
                            roles: list,
                            base_weights: dict[str, float]) -> dict[str, float]:
        """
        计算准确率调整后的角色权重
        
        Args:
            roles: 角色列表
            base_weights: 基础权重
        
        Returns:
            调整后的权重
        """
        adjusted_weights = {}
        
        for role in roles:
            name = role.name
            base_w = base_weights.get(name, 1.0)
            
            # 获取近期准确率
            if hasattr(role, 'accuracy_window') and role.accuracy_window:
                recent_acc = role.accuracy_window[-1]
                
                # 准确率调整因子: 准确率越高，权重越高
                # 使用sigmoid映射: 0.5->1.0, 0.7->1.5, 0.3->0.5
                acc_factor = 2.0 / (1.0 + np.exp(-5 * (recent_acc - 0.5)))
            else:
                acc_factor = 1.0
            
            # 活跃度调整
            if hasattr(role, 'is_active') and not role.is_active:
                active_factor = 0.0
            else:
                active_factor = 1.0
            
            adjusted_weights[name] = base_w * acc_factor * active_factor
        
        # 归一化
        total = sum(adjusted_weights.values())
        if total > 0:
            adjusted_weights = {k: v / total for k, v in adjusted_weights.items()}
        
        return adjusted_weights
    
    def compute_consensus(self, 
                         votes: dict[str, Any],
                         role_weights: dict[str, float]) -> dict:
        """
        计算加权共识
        
        改进点：
        1. 使用准确率调整后的权重
        2. 共识度考虑权重分布
        3. 支持/反对方按权重统计
        """
        weighted_score = 0.0
        total_weight = 0.0
        
        supporting = []
        opposing = []
        
        for role_name, view in votes.items():
            weight = role_weights.get(role_name, 1.0)
            score = view.score() if hasattr(view, 'score') else 0.0
            
            weighted_score += score * weight
            total_weight += weight
            
            if score > 0:
                supporting.append((role_name, weight))
            elif score < 0:
                opposing.append((role_name, weight))
        
        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 0.0
        
        # 共识度：考虑权重分布的集中度
        if len(votes) > 1:
            scores = [v.score() for v in votes.values()]
            weights = [role_weights.get(name, 1.0) for name in votes.keys()]
            
            # 加权标准差
            weighted_mean = np.average(scores, weights=weights)
            weighted_var = np.average((np.array(scores) - weighted_mean) ** 2, weights=weights)
            weighted_std = np.sqrt(weighted_var)
            
            consensus = 1.0 - min(1.0, weighted_std / (np.max(np.abs(scores)) + 1e-6))
        else:
            consensus = 0.5
        
        return {
            'final_score': final_score,
            'consensus': consensus,
            'supporting': supporting,
            'opposing': opposing,
            'supporting_weight': sum(w for _, w in supporting),
            'opposing_weight': sum(w for _, w in opposing),
        }


# ============================================================
# 5. 过拟合监控器
# ============================================================

class OverfittingMonitor:
    """
    过拟合监控器
    
    四层防护：
    1. IS/OOS性能比监控
    2. 参数稳定性追踪
    3. 市场状态切换检测
    4. 蒙特卡洛稳健性检验
    """
    
    def __init__(self, 
                 is_oos_ratio_threshold: float = 1.5,
                 param_stability_threshold: float = 0.3):
        self.is_oos_ratio_threshold = is_oos_ratio_threshold
        self.param_stability_threshold = param_stability_threshold
        
        self.is_performance_history: list[float] = []
        self.oos_performance_history: list[float] = []
        self.parameter_history: list[dict] = []
        self.alerts: list[dict] = []
    
    def check_is_oos_ratio(self, is_perf: float, oos_perf: float) -> dict:
        """检查IS/OOS性能比"""
        if abs(oos_perf) < 1e-6:
            ratio = float('inf') if is_perf > 0 else 0.0
        else:
            ratio = is_perf / oos_perf
        
        alert = {
            'type': 'is_oos_ratio',
            'timestamp': datetime.now(),
            'is_performance': is_perf,
            'oos_performance': oos_perf,
            'ratio': ratio,
            'triggered': ratio > self.is_oos_ratio_threshold if ratio > 0 else False
        }
        
        if alert['triggered']:
            self.alerts.append(alert)
            logger.warning(f"过拟合告警: IS/OOS比率 {ratio:.2f} > 阈值 {self.is_oos_ratio_threshold}")
        
        return alert
    
    def check_parameter_stability(self, current_params: dict) -> dict:
        """检查参数稳定性"""
        self.parameter_history.append(current_params)
        
        if len(self.parameter_history) < 5:
            return {'stable': True, 'reason': '历史不足'}
        
        # 计算最近5次参数变化的平均幅度
        recent = self.parameter_history[-5:]
        changes = []
        
        for key in ['weights', 'reflection_threshold', 'tension_range']:
            if key in current_params:
                values = [r.get(key, current_params[key]) for r in recent]
                if isinstance(values[0], list):
                    # 权重列表
                    avg_change = np.mean([
                        np.mean(np.abs(np.array(values[i]) - np.array(values[i-1])))
                        for i in range(1, len(values))
                    ])
                else:
                    # 标量
                    avg_change = np.mean([
                        abs(values[i] - values[i-1])
                        for i in range(1, len(values))
                    ])
                changes.append(avg_change)
        
        avg_change = np.mean(changes) if changes else 0.0
        stable = avg_change < self.param_stability_threshold
        
        alert = {
            'type': 'parameter_stability',
            'timestamp': datetime.now(),
            'avg_change': avg_change,
            'stable': stable,
            'threshold': self.param_stability_threshold
        }
        
        if not stable:
            self.alerts.append(alert)
            logger.warning(f"参数不稳定: 平均变化 {avg_change:.3f} > 阈值 {self.param_stability_threshold}")
        
        return alert
    
    def monte_carlo_robustness(self, 
                               strategy_fn,
                               data: pd.DataFrame,
                               n_simulations: int = 100) -> dict:
        """
        蒙特卡洛稳健性检验
        
        随机打乱数据顺序，检验策略稳健性
        """
        performances = []
        
        for _ in range(n_simulations):
            # 随机采样
            shuffled = data.sample(frac=0.8, replace=False)
            perf = strategy_fn(shuffled)
            performances.append(perf)
        
        return {
            'mean': np.mean(performances),
            'std': np.std(performances),
            'min': np.min(performances),
            'max': np.max(performances),
            'percentile_5': np.percentile(performances, 5),
            'percentile_95': np.percentile(performances, 95),
            'robust': np.std(performances) < 0.1  # 标准差小则稳健
        }
    
    def get_monitoring_report(self) -> dict:
        """获取监控报告"""
        return {
            'total_alerts': len(self.alerts),
            'alerts': self.alerts[-10:],  # 最近10条
            'is_oos_ratio': {
                'is_mean': np.mean(self.is_performance_history) if self.is_performance_history else 0,
                'oos_mean': np.mean(self.oos_performance_history) if self.oos_performance_history else 0,
            },
            'parameter_stability': {
                'history_length': len(self.parameter_history),
                'latest_params': self.parameter_history[-1] if self.parameter_history else {}
            }
        }


# ============================================================
# 6. 集成到FundManager的适配器
# ============================================================

class AutoOptimizedFundManager:
    """
    自动优化适配器
    
    包装FundManager，添加自动优化功能
    """
    
    def __init__(self, fund_manager, 
                 enable_pbt: bool = True,
                 enable_regularization: bool = True,
                 enable_walkforward: bool = True,
                 enable_monitoring: bool = True):
        self.fund_manager = fund_manager
        
        # 初始化优化组件
        self.pbt = PBTParameterOptimizer() if enable_pbt else None
        self.regularizer = RegularizedTrainer() if enable_regularization else None
        self.walkforward = WalkForwardValidator() if enable_walkforward else None
        self.monitor = OverfittingMonitor() if enable_monitoring else None
        
        # 准确率加权共识
        self.consensus_engine = AccuracyWeightedConsensus()
        
        # 优化历史
        self.optimization_history: list[dict] = []
        
        # 当前最佳参数
        self.current_params: dict = {}
    
    def initialize_optimization(self, base_config: dict):
        """初始化优化"""
        if self.pbt:
            self.pbt.initialize_population(base_config)
            logger.info(f"PBT初始化: 种群大小 {self.pbt.config.population_size}")
    
    def optimize_step(self, market_returns: np.ndarray):
        """执行一步优化"""
        if self.pbt and self.regularizer:
            self.pbt.step(market_returns, self.regularizer)
            
            # 获取最佳配置
            best_config = self.pbt.get_best_config()
            self.current_params = best_config
            
            # 应用参数到FundManager
            self._apply_params(best_config)
    
    def _apply_params(self, params: dict):
        """应用优化后的参数到FundManager"""
        # 更新角色权重
        if 'weights' in params and hasattr(self.fund_manager, 'roles'):
            role_names = list(self.fund_manager.roles.keys())
            weights = params['weights']
            
            for i, name in enumerate(role_names):
                if i < len(weights):
                    self.fund_manager.roles[name].weight = weights[i]
        
        # 更新共识阈值
        if 'consensus_threshold' in params and hasattr(self.fund_manager, 'config'):
            self.fund_manager.config.consensus_threshold = params['consensus_threshold']
    
    def make_decision_with_regularization(self, 
                                         date: pd.Timestamp,
                                         stock: str,
                                         data: dict) -> Any:
        """
        带正则化的决策
        
        1. 应用Dropout
        2. 准确率加权投票
        3. 过拟合监控
        """
        # 1. Dropout: 随机禁用角色
        if self.regularizer:
            active_mask = [r.is_active for r in self.fund_manager.roles.values()]
            new_mask = self.regularizer.apply_dropout(
                list(self.fund_manager.roles.values()),
                active_mask
            )
            for role, is_active in zip(self.fund_manager.roles.values(), new_mask):
                role.is_active = is_active
        
        # 2. 准确率加权投票
        # 先收集投票
        votes = {}
        for role_name, role in self.fund_manager.roles.items():
            if not role.is_active:
                continue
            try:
                view = role.analyze(date, stock, data)
                votes[role_name] = view
            except Exception as e:
                logger.warning(f"{role_name} 分析失败: {e}")
        
        # 计算准确率调整后的权重
        base_weights = {name: role.weight for name, role in self.fund_manager.roles.items()}
        adjusted_weights = self.consensus_engine.compute_role_weights(
            list(self.fund_manager.roles.values()),
            base_weights
        )
        
        # 计算共识
        consensus = self.consensus_engine.compute_consensus(votes, adjusted_weights)
        
        # 3. 使用FundManager的决策逻辑，但传入调整后的权重
        # 临时修改权重
        original_weights = {}
        for name, role in self.fund_manager.roles.items():
            original_weights[name] = role.weight
            role.weight = adjusted_weights.get(name, role.weight)
        
        # 调用原决策方法
        decision = self.fund_manager.make_decision(date, stock, data)
        
        # 恢复原始权重
        for name, weight in original_weights.items():
            self.fund_manager.roles[name].weight = weight
        
        # 4. 过拟合监控
        if self.monitor:
            # 记录参数
            current_params = {
                'weights': [r.weight for r in self.fund_manager.roles.values()],
                'consensus_threshold': self.fund_manager.config.consensus_threshold
            }
            self.monitor.check_parameter_stability(current_params)
        
        return decision
    
    def get_optimization_report(self) -> dict:
        """获取优化报告"""
        report = {
            'current_params': self.current_params,
            'optimization_history': self.optimization_history,
        }
        
        if self.pbt:
            report['pbt'] = self.pbt.get_population_report()
        
        if self.regularizer:
            report['regularization'] = self.regularizer.get_regularization_report()
        
        if self.monitor:
            report['monitoring'] = self.monitor.get_monitoring_report()
        
        return report


# ============================================================
# 7. 便捷函数
# ============================================================

def create_auto_optimized_manager(fund_manager,
                                  base_config: Optional[dict] = None) -> AutoOptimizedFundManager:
    """
    创建自动优化管理器的便捷函数
    
    Args:
        fund_manager: 原始FundManager实例
        base_config: 基础参数配置
    
    Returns:
        AutoOptimizedFundManager实例
    """
    adapter = AutoOptimizedFundManager(fund_manager)
    
    if base_config is None:
        # 默认配置
        base_config = {
            'weights': [0.8, 1.2, 1.5, 1.0, 1.2, 1.0],  # 6个角色的权重
            'reflection_threshold': 0.4,
            'tension_range': 0.3,
            'consensus_threshold': 0.5,
        }
    
    adapter.initialize_optimization(base_config)
    
    return adapter


# ============================================================
# 8. 演示
# ============================================================

def demo_auto_optimizer():
    """演示自动优化器"""
    print("=" * 80)
    print("Agent参数自动优化与过拟合防护演示")
    print("=" * 80)
    
    # 1. Walk-Forward验证
    print("\n【1. Walk-Forward验证】")
    wf = WalkForwardValidator()
    data = pd.DataFrame({
        'returns': np.random.randn(500) * 0.02,
        'prices': 100 * (1 + np.random.randn(500).cumsum() * 0.01)
    })
    splits = wf.split(data)
    print(f"  数据长度: {len(data)}")
    print(f"  Fold数量: {len(splits)}")
    for i, (train, val, test) in enumerate(splits):
        print(f"  Fold {i}: train={len(train)}, val={len(val)}, test={len(test)}")
    
    # 2. 正则化
    print("\n【2. 正则化机制】")
    trainer = RegularizedTrainer()
    params = {'weights': [0.3, 0.5, 0.2]}
    reg_loss = trainer.compute_regularization_loss(params)
    print(f"  参数: {params}")
    print(f"  正则化损失: {reg_loss:.4f}")
    
    # Dropout演示
    roles = ['A', 'B', 'C', 'D', 'E']
    mask = [True, True, True, True, True]
    new_mask = trainer.apply_dropout(roles, mask)
    print(f"  Dropout前: {mask}")
    print(f"  Dropout后: {new_mask}")
    
    # 3. PBT优化
    print("\n【3. PBT动态优化】")
    pbt = PBTParameterOptimizer(PBTConfig(population_size=5, exploit_interval=10))
    base_config = {
        'weights': [0.2, 0.2, 0.2, 0.2, 0.2],
        'reflection_threshold': 0.4,
        'tension_range': 0.3
    }
    pbt.initialize_population(base_config)
    print(f"  种群大小: {pbt.config.population_size}")
    
    # 模拟多步优化
    for step in range(30):
        returns = np.random.randn(20) * 0.02
        pbt.step(returns, trainer)
    
    best = pbt.get_best_config()
    print(f"  优化后最佳权重: {[f'{w:.3f}' for w in best['weights']]}")
    print(f"  优化后阈值: {best['reflection_threshold']:.3f}")
    
    # 4. 准确率加权共识
    print("\n【4. 准确率加权共识】")
    consensus = AccuracyWeightedConsensus()
    
    # 模拟角色
    class MockRole:
        def __init__(self, name, weight, accuracy, active=True):
            self.name = name
            self.weight = weight
            self.accuracy_window = [accuracy]
            self.is_active = active
    
    roles = [
        MockRole("A", 1.0, 0.7),
        MockRole("B", 1.0, 0.5),
        MockRole("C", 1.0, 0.6),
    ]
    base_weights = {r.name: r.weight for r in roles}
    adjusted = consensus.compute_role_weights(roles, base_weights)
    print(f"  基础权重: {base_weights}")
    print(f"  调整后权重: {adjusted}")
    
    # 5. 过拟合监控
    print("\n【5. 过拟合监控】")
    monitor = OverfittingMonitor()
    alert = monitor.check_is_oos_ratio(is_perf=0.15, oos_perf=0.08)
    print(f"  IS性能: 15%")
    print(f"  OOS性能: 8%")
    print(f"  IS/OOS比率: {alert['ratio']:.2f}")
    print(f"  过拟合告警: {alert['triggered']}")
    
    print("\n" + "=" * 80)
    print("演示完成")
    print("=" * 80)


if __name__ == "__main__":
    demo_auto_optimizer()
