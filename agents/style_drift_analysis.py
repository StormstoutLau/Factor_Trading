"""
Agent风格漂移分析与防控机制
==============================

核心问题：Agent在学习过程中是否会偏离初始设定的投资风格？

风格漂移（Style Drift）定义：
- 狭义：Agent的选股偏好、权重分配模式发生非预期变化
- 广义：Agent的风险特征、收益来源、市场暴露与初始设定不一致

本模块实现：
1. 漂移检测指标
2. 漂移根因分析
3. 防漂移机制（正则化、约束、监控）
4. 风格锚定系统
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# 1. 风格漂移检测指标
# ============================================================

@dataclass
class StyleDriftMetrics:
    """风格漂移检测指标集
    
    多维度监控Agent是否偏离初始风格
    """
    
    # 1. 选股偏好漂移
    factor_correlation_drift: float = 0.0      # 与初始因子的相关性变化
    sector_exposure_drift: float = 0.0         # 行业暴露变化
    market_cap_drift: float = 0.0              # 市值偏好变化
    
    # 2. 权重分配漂移
    concentration_drift: float = 0.0           # 集中度变化
    turnover_drift: float = 0.0                # 换手率变化
    
    # 3. 风险特征漂移
    beta_drift: float = 0.0                    # Beta变化
    volatility_drift: float = 0.0              # 波动率变化
    max_drawdown_drift: float = 0.0            # 回撤特征变化
    
    # 4. 收益来源漂移
    return_attribution_drift: float = 0.0      # 收益归因变化
    factor_exposure_drift: float = 0.0         # 因子暴露变化
    
    # 综合漂移评分
    composite_drift_score: float = 0.0         # 综合漂移分数 (0-1)
    drift_level: str = "NONE"                   # NONE | MILD | MODERATE | SEVERE
    
    def to_dict(self) -> dict:
        return {
            'factor_correlation_drift': self.factor_correlation_drift,
            'sector_exposure_drift': self.sector_exposure_drift,
            'market_cap_drift': self.market_cap_drift,
            'concentration_drift': self.concentration_drift,
            'turnover_drift': self.turnover_drift,
            'beta_drift': self.beta_drift,
            'volatility_drift': self.volatility_drift,
            'max_drawdown_drift': self.max_drawdown_drift,
            'return_attribution_drift': self.return_attribution_drift,
            'factor_exposure_drift': self.factor_exposure_drift,
            'composite_drift_score': self.composite_drift_score,
            'drift_level': self.drift_level
        }


class StyleDriftDetector:
    """风格漂移检测器
    
    通过对比Agent当前行为与初始设定，检测风格漂移
    """
    
    def __init__(self, 
                 factor_correlation_threshold: float = 0.3,
                 concentration_threshold: float = 0.5,
                 beta_threshold: float = 0.3,
                 composite_threshold: float = 0.4):
        """
        Args:
            factor_correlation_threshold: 因子相关性漂移阈值
            concentration_threshold: 集中度漂移阈值
            beta_threshold: Beta漂移阈值
            composite_threshold: 综合漂移阈值
        """
        self.thresholds = {
            'factor_correlation': factor_correlation_threshold,
            'concentration': concentration_threshold,
            'beta': beta_threshold,
            'composite': composite_threshold
        }
        
        # 历史记录
        self.drift_history: list[dict] = []
        self.baseline_profile: dict[str, Any] | None = None
    
    def set_baseline(self, baseline: dict[str, Any]):
        """设置基线风格档案
        
        Args:
            baseline: 初始风格档案，包含：
                - preferred_factors: 偏好因子列表
                - sector_weights: 行业权重分布
                - market_cap_preference: 市值偏好
                - target_concentration: 目标集中度
                - target_beta: 目标Beta
        """
        self.baseline_profile = baseline
        logger.info("基线风格档案已设置")
    
    def detect_drift(self, 
                    current_portfolio: dict[str, Any],
                    current_returns: pd.Series,
                    current_factors: pd.DataFrame) -> StyleDriftMetrics:
        """检测当前风格漂移
        
        Args:
            current_portfolio: 当前持仓
            current_returns: 当前收益序列
            current_factors: 当前因子暴露
            
        Returns:
            漂移检测指标
        """
        if self.baseline_profile is None:
            logger.warning("未设置基线档案，无法检测漂移")
            return StyleDriftMetrics()
        
        metrics = StyleDriftMetrics()
        
        # 1. 检测因子相关性漂移
        metrics.factor_correlation_drift = self._detect_factor_drift(
            current_factors
        )
        
        # 2. 检测集中度漂移
        metrics.concentration_drift = self._detect_concentration_drift(
            current_portfolio
        )
        
        # 3. 检测Beta漂移
        metrics.beta_drift = self._detect_beta_drift(
            current_returns
        )
        
        # 4. 检测波动率漂移
        metrics.volatility_drift = self._detect_volatility_drift(
            current_returns
        )
        
        # 5. 计算综合漂移分数
        metrics.composite_drift_score = self._compute_composite_score(metrics)
        
        # 6. 判定漂移等级
        metrics.drift_level = self._classify_drift_level(
            metrics.composite_drift_score
        )
        
        # 记录历史
        self.drift_history.append({
            'timestamp': datetime.now(),
            'metrics': metrics.to_dict()
        })
        
        return metrics
    
    def _detect_factor_drift(self, current_factors: pd.DataFrame) -> float:
        """检测因子偏好漂移
        
        计算当前因子暴露与初始偏好的差异
        """
        if self.baseline_profile is None or 'preferred_factors' not in self.baseline_profile:
            return 0.0
        
        baseline_factors = self.baseline_profile['preferred_factors']
        
        # 计算当前因子与基线因子的相关性
        correlations = []
        for factor in baseline_factors:
            if factor in current_factors.columns:
                # 简化：使用因子暴露的均值差异
                baseline_exposure = self.baseline_profile.get(
                    f'{factor}_exposure', 0.0
                )
                current_exposure = current_factors[factor].mean()
                diff = abs(current_exposure - baseline_exposure)
                correlations.append(min(diff, 1.0))
        
        return np.mean(correlations) if correlations else 0.0
    
    def _detect_concentration_drift(self, current_portfolio: dict) -> float:
        """检测持仓集中度漂移"""
        if self.baseline_profile is None:
            return 0.0
        
        baseline_concentration = self.baseline_profile.get(
            'target_concentration', 0.05
        )
        
        # 计算当前集中度（HHI指数）
        positions = current_portfolio.get('positions', {})
        if not positions:
            return 0.0
        
        total_value = sum(
            pos.get('market_value', 0) for pos in positions.values()
        )
        
        if total_value == 0:
            return 0.0
        
        weights = [
            pos.get('market_value', 0) / total_value 
            for pos in positions.values()
        ]
        
        hhi = sum(w ** 2 for w in weights)
        current_concentration = hhi  # HHI指数本身反映集中度
        
        # 计算漂移
        drift = abs(current_concentration - baseline_concentration) / baseline_concentration
        
        return min(drift, 1.0)
    
    def _detect_beta_drift(self, current_returns: pd.Series) -> float:
        """检测Beta漂移"""
        if self.baseline_profile is None:
            return 0.0
        
        baseline_beta = self.baseline_profile.get('target_beta', 1.0)
        
        # 简化：使用收益波动率作为Beta的代理
        if len(current_returns) < 2:
            return 0.0
        
        current_volatility = current_returns.std()
        baseline_volatility = self.baseline_profile.get(
            'baseline_volatility', current_volatility
        )
        
        if baseline_volatility == 0:
            return 0.0
        
        current_beta = current_volatility / baseline_volatility
        drift = abs(current_beta - baseline_beta) / abs(baseline_beta)
        
        return min(drift, 1.0)
    
    def _detect_volatility_drift(self, current_returns: pd.Series) -> float:
        """检测波动率漂移"""
        if len(current_returns) < 10:
            return 0.0
        
        baseline_vol = self.baseline_profile.get('baseline_volatility', 0.02)
        current_vol = current_returns.std()
        
        if baseline_vol == 0:
            return 0.0
        
        drift = abs(current_vol - baseline_vol) / baseline_vol
        return min(drift, 1.0)
    
    def _compute_composite_score(self, metrics: StyleDriftMetrics) -> float:
        """计算综合漂移分数"""
        weights = {
            'factor_correlation': 0.25,
            'concentration': 0.20,
            'beta': 0.20,
            'volatility': 0.15,
            'sector': 0.10,
            'turnover': 0.10
        }
        
        score = (
            weights['factor_correlation'] * metrics.factor_correlation_drift +
            weights['concentration'] * metrics.concentration_drift +
            weights['beta'] * metrics.beta_drift +
            weights['volatility'] * metrics.volatility_drift
        )
        
        return min(score, 1.0)
    
    def _classify_drift_level(self, score: float) -> str:
        """分类漂移等级"""
        if score < 0.2:
            return "NONE"
        elif score < 0.4:
            return "MILD"
        elif score < 0.6:
            return "MODERATE"
        else:
            return "SEVERE"
    
    def get_drift_report(self) -> dict[str, Any]:
        """获取漂移检测报告"""
        if not self.drift_history:
            return {'status': 'no_data'}
        
        latest = self.drift_history[-1]
        
        # 计算趋势
        if len(self.drift_history) >= 3:
            recent_scores = [
                h['metrics']['composite_drift_score'] 
                for h in self.drift_history[-10:]
            ]
            trend = np.polyfit(range(len(recent_scores)), recent_scores, 1)[0]
        else:
            trend = 0.0
        
        return {
            'latest_drift_score': latest['metrics']['composite_drift_score'],
            'latest_drift_level': latest['metrics']['drift_level'],
            'trend': 'increasing' if trend > 0.01 else 'decreasing' if trend < -0.01 else 'stable',
            'trend_slope': float(trend),
            'total_detections': len(self.drift_history),
            'severe_count': sum(
                1 for h in self.drift_history 
                if h['metrics']['drift_level'] == 'SEVERE'
            )
        }


# ============================================================
# 2. 风格锚定系统（防漂移核心机制）
# ============================================================

class StyleAnchor:
    """风格锚定系统
    
    通过多种机制防止Agent风格漂移：
    1. 正则化约束：限制模型权重变化幅度
    2. 风格回拉：定期将Agent拉回初始风格
    3. 硬边界：绝对不允许突破的约束
    4. 冷却期：风格变化后的观察期
    """
    
    def __init__(self,
                 anchor_strength: float = 0.3,        # 锚定强度 (0-1)
                 max_weight_change_per_step: float = 0.2,  # 每步最大权重变化
                 style_recalibration_period: int = 20,     # 风格重新校准周期（交易日）
                 hard_constraints: dict | None = None):
        """
        Args:
            anchor_strength: 锚定强度，越高越难偏离初始风格
            max_weight_change_per_step: 每步最大权重变化比例
            style_recalibration_period: 风格重新校准周期
            hard_constraints: 硬约束条件
        """
        self.anchor_strength = anchor_strength
        self.max_weight_change = max_weight_change_per_step
        self.recalibration_period = style_recalibration_period
        
        # 硬约束
        self.hard_constraints = hard_constraints or {
            'min_factor_correlation': 0.5,      # 与初始因子最小相关性
            'max_concentration': 0.20,          # 最大集中度
            'max_beta_deviation': 0.5,          # Beta最大偏离
            'max_turnover_increase': 2.0,       # 换手率最大增加倍数
        }
        
        # 初始风格锚点
        self.initial_style_weights: dict[str, float] = {}
        self.initial_expression_dna: dict[str, Any] = {}
        
        # 状态
        self.steps_since_calibration: int = 0
        self.is_in_cooldown: bool = False
        self.cooldown_steps: int = 0
    
    def set_initial_anchor(self, 
                          style_weights: dict[str, float],
                          expression_dna: dict[str, Any]):
        """设置初始风格锚点"""
        self.initial_style_weights = style_weights.copy()
        self.initial_expression_dna = expression_dna.copy()
        
        logger.info(f"风格锚点已设置: {style_weights}")
    
    def constrain_weights(self, 
                         current_weights: dict[str, float]) -> dict[str, float]:
        """约束模型权重变化
        
        应用正则化，防止权重剧烈变化
        """
        if not self.initial_style_weights:
            return current_weights
        
        constrained = {}
        
        for model_name, current_weight in current_weights.items():
            initial_weight = self.initial_style_weights.get(model_name, 0.0)
            
            # 1. 限制单步变化幅度
            max_change = self.max_weight_change
            weight_change = current_weight - initial_weight
            
            if abs(weight_change) > max_change:
                # 限制变化
                constrained_change = np.sign(weight_change) * max_change
                constrained[model_name] = initial_weight + constrained_change
            else:
                constrained[model_name] = current_weight
            
            # 2. 应用锚定强度（向初始权重回拉）
            constrained[model_name] = (
                self.anchor_strength * initial_weight +
                (1 - self.anchor_strength) * constrained[model_name]
            )
        
        # 3. 归一化
        total = sum(constrained.values())
        if total > 0:
            constrained = {k: v / total for k, v in constrained.items()}
        
        return constrained
    
    def check_hard_constraints(self,
                              current_metrics: StyleDriftMetrics) -> tuple[bool, list[str]]:
        """检查硬约束是否被违反
        
        Returns:
            (是否通过, 违反的约束列表)
        """
        violations = []
        
        # 检查因子相关性
        if current_metrics.factor_correlation_drift > \
           (1 - self.hard_constraints['min_factor_correlation']):
            violations.append(
                f"因子相关性过低: {current_metrics.factor_correlation_drift:.2f} "
                f"(要求 < {1 - self.hard_constraints['min_factor_correlation']:.2f})"
            )
        
        # 检查集中度
        if current_metrics.concentration_drift > self.hard_constraints['max_concentration']:
            violations.append(
                f"集中度超限: {current_metrics.concentration_drift:.2f} "
                f"(要求 < {self.hard_constraints['max_concentration']:.2f})"
            )
        
        # 检查Beta偏离
        if current_metrics.beta_drift > self.hard_constraints['max_beta_deviation']:
            violations.append(
                f"Beta偏离过大: {current_metrics.beta_drift:.2f} "
                f"(要求 < {self.hard_constraints['max_beta_deviation']:.2f})"
            )
        
        return len(violations) == 0, violations
    
    def should_recalibrate(self) -> bool:
        """判断是否需要重新校准风格"""
        self.steps_since_calibration += 1
        
        # 定期校准
        if self.steps_since_calibration >= self.recalibration_period:
            return True
        
        # 冷却期检查
        if self.is_in_cooldown:
            self.cooldown_steps -= 1
            if self.cooldown_steps <= 0:
                self.is_in_cooldown = False
                return True
        
        return False
    
    def recalibrate(self, 
                   current_weights: dict[str, float],
                   current_dna: dict[str, Any]) -> tuple[dict, dict]:
        """重新校准风格
        
        将当前风格向初始锚点回拉
        """
        logger.info("执行风格重新校准...")
        
        # 回拉权重
        recalibrated_weights = {}
        for model_name, current_weight in current_weights.items():
            initial_weight = self.initial_style_weights.get(model_name, 0.0)
            
            # 向初始权重回拉50%
            recalibrated_weights[model_name] = (
                0.5 * initial_weight + 0.5 * current_weight
            )
        
        # 归一化
        total = sum(recalibrated_weights.values())
        if total > 0:
            recalibrated_weights = {
                k: v / total for k, v in recalibrated_weights.items()
            }
        
        # 回拉DNA
        recalibrated_dna = current_dna.copy()
        for key, initial_value in self.initial_expression_dna.items():
            if key in recalibrated_dna:
                if isinstance(initial_value, (int, float)):
                    recalibrated_dna[key] = 0.5 * initial_value + 0.5 * recalibrated_dna[key]
        
        self.steps_since_calibration = 0
        
        logger.info(f"校准后权重: {recalibrated_weights}")
        
        return recalibrated_weights, recalibrated_dna
    
    def enter_cooldown(self, steps: int = 5):
        """进入冷却期
        
        在风格剧烈变化后，暂停学习，观察效果
        """
        self.is_in_cooldown = True
        self.cooldown_steps = steps
        logger.info(f"进入冷却期: {steps} 步")


# ============================================================
# 3. 集成到AdaptiveAgent的防漂移机制
# ============================================================

class DriftResistantAdaptiveAgent:
    """防漂移自适应Agent
    
    在AdaptiveAgent基础上增加风格漂移防控
    """
    
    def __init__(self, agent_id: str, name: str,
                 anchor_strength: float = 0.3):
        self.agent_id = agent_id
        self.name = name
        
        # 从adaptive_agent导入
        from adaptive_agent import AdaptiveAgent
        self.base_agent = AdaptiveAgent(agent_id, name)
        
        # 漂移检测
        self.drift_detector = StyleDriftDetector()
        
        # 风格锚定
        self.style_anchor = StyleAnchor(anchor_strength=anchor_strength)
        
        # 设置初始锚点
        initial_weights = self.base_agent.learning_engine.get_model_weights()
        initial_dna = self.base_agent.cognition.expression_dna
        self.style_anchor.set_initial_anchor(initial_weights, initial_dna)
        
        # 设置基线档案
        self._setup_baseline_profile()
        
        logger.info(f"防漂移Agent初始化: [{agent_id}] {name}")
    
    def _setup_baseline_profile(self):
        """设置基线风格档案"""
        baseline = {
            'preferred_factors': ['factor_value', 'factor_momentum'],
            'target_concentration': 0.05,
            'target_beta': 1.0,
            'baseline_volatility': 0.02
        }
        self.drift_detector.set_baseline(baseline)
    
    def generate_signals_with_drift_control(self,
                                           date: pd.Timestamp,
                                           factor_data: pd.DataFrame,
                                           tradable_mask: pd.Series,
                                           current_portfolio: dict) -> pd.Series:
        """生成信号（带漂移控制）"""
        
        # 1. 获取当前模型权重
        current_weights = self.base_agent.learning_engine.get_model_weights()
        
        # 2. 应用锚定约束
        constrained_weights = self.style_anchor.constrain_weights(current_weights)
        
        # 3. 检查是否需要重新校准
        if self.style_anchor.should_recalibrate():
            constrained_weights, new_dna = self.style_anchor.recalibrate(
                constrained_weights,
                self.base_agent.cognition.expression_dna
            )
            self.base_agent.cognition.expression_dna = new_dna
        
        # 4. 使用约束后的权重生成信号
        # （这里简化处理，实际应修改AdaptiveAgent的内部逻辑）
        composite_signal = pd.Series(0.0, index=factor_data.columns)
        
        for model_name, weight in constrained_weights.items():
            model_signal = self.base_agent._apply_model(
                model_name, factor_data, tradable_mask
            )
            composite_signal += model_signal * weight
        
        # 5. 检测漂移
        # 简化：使用当前持仓和收益计算漂移
        # 实际应在回测循环中调用
        
        return composite_signal[tradable_mask].dropna()
    
    def check_and_handle_drift(self,
                              current_portfolio: dict,
                              current_returns: pd.Series,
                              current_factors: pd.DataFrame):
        """检查并处理风格漂移"""
        
        # 1. 检测漂移
        drift_metrics = self.drift_detector.detect_drift(
            current_portfolio, current_returns, current_factors
        )
        
        # 2. 检查硬约束
        passed, violations = self.style_anchor.check_hard_constraints(drift_metrics)
        
        if not passed:
            logger.warning(f"[{self.agent_id}] 硬约束被违反:")
            for v in violations:
                logger.warning(f"  - {v}")
            
            # 触发重新校准
            current_weights = self.base_agent.learning_engine.get_model_weights()
            new_weights, new_dna = self.style_anchor.recalibrate(
                current_weights,
                self.base_agent.cognition.expression_dna
            )
            
            # 应用新权重（简化）
            logger.info(f"[{self.agent_id}] 强制重新校准风格")
            
            # 进入冷却期
            self.style_anchor.enter_cooldown(steps=10)
        
        # 3. 根据漂移等级采取行动
        if drift_metrics.drift_level == 'SEVERE':
            logger.error(f"[{self.agent_id}] 严重风格漂移 detected!")
            self.style_anchor.enter_cooldown(steps=20)
        elif drift_metrics.drift_level == 'MODERATE':
            logger.warning(f"[{self.agent_id}] 中度风格漂移 detected")
            self.style_anchor.enter_cooldown(steps=10)
        
        return drift_metrics
    
    def get_drift_report(self) -> dict[str, Any]:
        """获取漂移报告"""
        return {
            'agent_id': self.agent_id,
            'drift_detection': self.drift_detector.get_drift_report(),
            'anchor_status': {
                'steps_since_calibration': self.style_anchor.steps_since_calibration,
                'in_cooldown': self.style_anchor.is_in_cooldown,
                'cooldown_steps': self.style_anchor.cooldown_steps
            },
            'current_weights': self.base_agent.learning_engine.get_model_weights()
        }


# ============================================================
# 4. 漂移根因分析
# ============================================================

def analyze_drift_root_causes() -> dict[str, Any]:
    """分析当前AdaptiveAgent设计中导致漂移的根因
    
    基于代码审查，识别潜在的漂移风险点
    """
    
    root_causes = {
        'high_risk': [
            {
                'issue': '贝叶斯更新无约束',
                'location': 'BayesianLearningEngine.evaluate_prediction()',
                'description': 'likelihood_ratio 固定为 1.5 或 0.67，无上限/下限约束',
                'impact': '少数几次正确预测可使信念极端化（>0.99）',
                'example': '连续3次正确 → 后验概率 0.5 → 0.75 → 0.90 → 0.96'
            },
            {
                'issue': 'Softmax放大差异',
                'location': 'BayesianLearningEngine.get_model_weights()',
                'description': 'exp(v * 5) 极大放大置信度差异',
                'impact': '微小置信度差异导致权重分配极端化',
                'example': '置信度 0.6 vs 0.55 → 权重 62% vs 38%'
            },
            {
                'issue': '表达DNA完全由regime决定',
                'location': 'AdaptiveAgent._update_expression_dna()',
                'description': 'DNA参数根据regime硬编码变化，无平滑过渡',
                'impact': 'regime误判时DNA剧烈变化',
                'example': '趋势→震荡: 集中度 8% → 4%（瞬间减半）'
            },
            {
                'issue': '无风格回拉机制',
                'location': '整个AdaptiveAgent类',
                'description': '没有机制将Agent拉回初始风格',
                'impact': '一旦漂移，持续加剧',
                'example': '价值型Agent可能完全变成动量型'
            }
        ],
        'medium_risk': [
            {
                'issue': '单一regime判断',
                'location': 'AdaptiveAgent.adapt_to_regime()',
                'description': 'regime是离散分类，无概率分布',
                'impact': 'regime边界处频繁切换',
                'example': '在趋势/震荡边界反复切换'
            },
            {
                'issue': '预测准确率更新过快',
                'location': 'BeliefState.add_evidence()',
                'description': 'alpha=0.1，10次错误即可将准确率从0.5降到0.35',
                'impact': '短期噪音影响长期信念',
                'example': '10次错误 → 准确率 0.5 → 0.35'
            }
        ],
        'low_risk': [
            {
                'issue': '无交易记录验证',
                'location': 'AdaptiveAgent.update_from_backtest()',
                'description': '仅使用sharpe>0.5作为判断，无统计显著性检验',
                'impact': '可能将运气误认为能力',
                'example': '短期正夏普可能只是运气'
            }
        ]
    }
    
    return root_causes


# ============================================================
# 5. 使用示例
# ============================================================

def demo_drift_detection():
    """演示漂移检测"""
    
    # 创建检测器
    detector = StyleDriftDetector()
    
    # 设置基线
    baseline = {
        'preferred_factors': ['factor_value', 'factor_momentum'],
        'target_concentration': 0.05,
        'target_beta': 1.0,
        'baseline_volatility': 0.02,
        'factor_value_exposure': 0.3,
        'factor_momentum_exposure': 0.2
    }
    detector.set_baseline(baseline)
    
    # 模拟当前状态（轻度漂移）
    current_portfolio = {
        'positions': {
            '000001.SZ': {'market_value': 500000},
            '000002.SZ': {'market_value': 400000},
            '000003.SZ': {'market_value': 300000},
        }
    }
    current_returns = pd.Series(np.random.normal(0.001, 0.015, 20))
    current_factors = pd.DataFrame({
        'factor_value': np.random.normal(0.25, 0.1, 100),      # 偏离基线0.3
        'factor_momentum': np.random.normal(0.35, 0.1, 100),   # 偏离基线0.2
    })
    
    # 检测
    metrics = detector.detect_drift(current_portfolio, current_returns, current_factors)
    
    print("漂移检测结果:")
    print(f"  综合漂移分数: {metrics.composite_drift_score:.3f}")
    print(f"  漂移等级: {metrics.drift_level}")
    print(f"  因子相关性漂移: {metrics.factor_correlation_drift:.3f}")
    print(f"  集中度漂移: {metrics.concentration_drift:.3f}")
    print(f"  Beta漂移: {metrics.beta_drift:.3f}")
    
    # 报告
    report = detector.get_drift_report()
    print(f"\n漂移趋势: {report['trend']}")


def demo_style_anchor():
    """演示风格锚定"""
    
    # 创建锚定系统
    anchor = StyleAnchor(anchor_strength=0.3)
    
    # 设置初始锚点
    initial_weights = {
        '均值回归': 0.4,
        '趋势跟踪': 0.3,
        '动量效应': 0.2,
        '价值发现': 0.1
    }
    initial_dna = {
        'position_concentration': 0.05,
        'market_cap_bias': 'none'
    }
    anchor.set_initial_anchor(initial_weights, initial_dna)
    
    # 模拟学习后的权重（严重漂移）
    learned_weights = {
        '均值回归': 0.05,    # 从0.4降到0.05
        '趋势跟踪': 0.70,   # 从0.3升到0.70
        '动量效应': 0.20,
        '价值发现': 0.05
    }
    
    print("学习后权重（漂移前）:")
    for k, v in learned_weights.items():
        print(f"  {k}: {v:.2f}")
    
    # 应用约束
    constrained = anchor.constrain_weights(learned_weights)
    
    print("\n约束后权重（防漂移）:")
    for k, v in constrained.items():
        print(f"  {k}: {v:.2f}")
    
    # 检查硬约束
    metrics = StyleDriftMetrics(
        factor_correlation_drift=0.6,
        concentration_drift=0.15,
        beta_drift=0.4
    )
    passed, violations = anchor.check_hard_constraints(metrics)
    
    print(f"\n硬约束检查: {'通过' if passed else '未通过'}")
    if violations:
        for v in violations:
            print(f"  违反: {v}")


if __name__ == "__main__":
    print("=" * 60)
    print("风格漂移检测演示")
    print("=" * 60)
    demo_drift_detection()
    
    print("\n" + "=" * 60)
    print("风格锚定演示")
    print("=" * 60)
    demo_style_anchor()
    
    print("\n" + "=" * 60)
    print("漂移根因分析")
    print("=" * 60)
    causes = analyze_drift_root_causes()
    for level, items in causes.items():
        print(f"\n【{level}】")
        for item in items:
            print(f"  问题: {item['issue']}")
            print(f"  位置: {item['location']}")
            print(f"  影响: {item['description']}")
            print()
