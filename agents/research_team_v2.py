"""
模拟投研团队多Agent决策框架 v2
=================================

新增功能：
1. 贝叶斯学习：每个角色独立学习进化
2. 元控制层：不同角色使用不同反思机制
3. 基金经理风格：激进/稳健/保守
4. 向量化优化：减少for循环
5. 行业轮动接入：IndustryRotationAnalyzer集成
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

try:
    from industry_rotation_v2 import IndustryRotationAnalyzer
except ImportError:
    IndustryRotationAnalyzer = None
from hierarchical_bayesian_agent import HierarchicalBelief, BeliefLayer, HierarchicalBayesianEngine

logger = logging.getLogger(__name__)


# ============================================================
# 1. 元控制层：反思机制工厂
# ============================================================

class ReflectionType(Enum):
    """反思机制类型"""
    CONSERVATIVE = auto()   # 保守型：变化慢，重视稳定性
    AGGRESSIVE = auto()     # 激进型：变化快，追求适应
    BALANCED = auto()       # 平衡型：折中
    TECHNICAL = auto()      # 技术型：基于统计指标
    FUNDAMENTAL = auto()    # 基本面型：基于逻辑一致性


class MetaReflectionController:
    """元控制层
    
    为不同角色配置不同的反思机制
    """
    
    def __init__(self):
        self.reflection_configs: dict[ReflectionType, dict] = {
            ReflectionType.CONSERVATIVE: {
                'direction_ratio_threshold': 0.5,    # 更高阈值才判定为有效适应
                'over_react_threshold': 0.03,        # 更敏感检测过度反应
                'tension_adjust_factor': 0.7,        # 张力调整更保守
                'reflection_period': 30,             # 反思周期更长
            },
            ReflectionType.AGGRESSIVE: {
                'direction_ratio_threshold': 0.2,
                'over_react_threshold': 0.08,
                'tension_adjust_factor': 1.3,
                'reflection_period': 10,
            },
            ReflectionType.BALANCED: {
                'direction_ratio_threshold': 0.3,
                'over_react_threshold': 0.05,
                'tension_adjust_factor': 1.0,
                'reflection_period': 20,
            },
            ReflectionType.TECHNICAL: {
                'direction_ratio_threshold': 0.35,
                'over_react_threshold': 0.04,
                'tension_adjust_factor': 0.9,
                'reflection_period': 15,
                'use_statistical_test': True,        # 使用统计检验
            },
            ReflectionType.FUNDAMENTAL: {
                'direction_ratio_threshold': 0.25,
                'over_react_threshold': 0.06,
                'tension_adjust_factor': 1.1,
                'reflection_period': 25,
                'check_logical_consistency': True,   # 检查逻辑一致性
            }
        }
    
    def get_config(self, reflection_type: ReflectionType) -> dict:
        """获取反思配置"""
        return self.reflection_configs.get(reflection_type, 
                                           self.reflection_configs[ReflectionType.BALANCED])
    
    def create_reflection_function(self, 
                                   reflection_type: ReflectionType) -> Callable:
        """创建反思函数"""
        config = self.get_config(reflection_type)
        
        def reflect(trajectory: list[tuple[datetime, float]]) -> dict:
            """执行反思"""
            if len(trajectory) < 10:
                return {'status': 'insufficient_data'}
            
            recent = trajectory[-20:]
            values = [v for _, v in recent]
            
            total_variation = sum(abs(values[i] - values[i-1]) for i in range(1, len(values)))
            net_change = abs(values[-1] - values[0])
            
            direction_ratio = net_change / total_variation if total_variation > 0 else 1.0
            avg_step_change = total_variation / len(values)
            
            # 使用配置参数判断
            threshold = config['direction_ratio_threshold']
            over_threshold = config['over_react_threshold']
            
            if direction_ratio < threshold and avg_step_change > over_threshold:
                assessment = 'over_reacting'
                recommendation = 'slow_down'
            elif direction_ratio > 0.7 and avg_step_change > over_threshold * 0.6:
                assessment = 'genuine_adaptation'
                recommendation = 'continue'
            elif avg_step_change < over_threshold * 0.3:
                assessment = 'under_reacting'
                recommendation = 'be_more_flexible'
            else:
                assessment = 'stable'
                recommendation = 'maintain'
            
            result = {
                'direction_ratio': direction_ratio,
                'avg_step_change': avg_step_change,
                'assessment': assessment,
                'recommendation': recommendation,
                'config_type': reflection_type.name,
            }
            
            # 额外检查
            if config.get('use_statistical_test') and len(values) >= 10:
                # 简单的趋势检验
                from scipy import stats
                slope, _, pvalue, _, _ = stats.linregress(range(len(values)), values)
                result['trend_pvalue'] = pvalue
                result['trend_significant'] = pvalue < 0.05
            
            return result
        
        return reflect


# ============================================================
# 2. 贝叶斯学习角色基类
# ============================================================

class BayesianResearchRole(ABC):
    """带贝叶斯学习的投研角色基类
    
    数据隔离特性：
    - learning_mode: 学习模式 (online/frozen/reset)
    - train_prediction_history: 训练期预测记录
    - test_prediction_history: 测试期预测记录（仅记录，不用于学习）
    """
    
    def __init__(self, 
                 name: str, 
                 weight: float = 1.0,
                 reflection_type: ReflectionType = ReflectionType.BALANCED,
                 learning_mode: str = "online"):
        self.name = name
        self.weight = weight
        self.views: list[ResearchView] = []
        self.is_active: bool = True
        
        # 学习模式
        self.learning_mode = learning_mode
        
        # 贝叶斯学习引擎
        self.belief_engine = HierarchicalBayesianEngine()
        self._setup_beliefs()
        
        # 元控制层
        self.meta_controller = MetaReflectionController()
        self.reflection_type = reflection_type
        self.reflect_fn = self.meta_controller.create_reflection_function(reflection_type)
        
        # 反思周期
        config = self.meta_controller.get_config(reflection_type)
        self.reflection_period = config['reflection_period']
        self.steps_since_reflection = 0
        
        # 学习记录（按期间隔离）
        self.prediction_history: list[tuple[bool, float]] = []  # (是否正确, 得分)
        self.accuracy_window: list[float] = []  # 最近准确率
        self.train_prediction_history: list[tuple[bool, float]] = []  # 训练期记录
        self.test_prediction_history: list[tuple[bool, float]] = []   # 测试期记录
    
    def _setup_beliefs(self):
        """设置信念体系 - 子类可覆盖"""
        pass
    
    @abstractmethod
    def analyze(self,
               date: pd.Timestamp,
               stock: str,
               data: dict[str, Any]) -> 'ResearchView':
        """分析并生成观点"""
        pass
    
    def learn_from_outcome(self, prediction_correct: bool, 
                          outcome_score: float = 0.0,
                          period: str = "train"):
        """从预测结果学习
        
        Args:
            prediction_correct: 预测是否正确
            outcome_score: 结果得分（收益等）
            period: 当前期间类型 ('train' | 'test')
        """
        # 测试期处理
        if period == "test":
            self.test_prediction_history.append((prediction_correct, outcome_score))
            
            if self.learning_mode == "frozen":
                # 冻结模式：不学习，只记录
                return
            elif self.learning_mode == "reset":
                # 重置模式：清空训练记录，只保留测试期记录
                self.prediction_history = [(prediction_correct, outcome_score)]
                self.accuracy_window = []
                return
            # online模式：继续执行下面的学习逻辑
        
        # 训练期或online模式的测试期
        self.prediction_history.append((prediction_correct, outcome_score))
        if period == "train":
            self.train_prediction_history.append((prediction_correct, outcome_score))
        
        # 更新准确率窗口
        window_size = 20
        recent = self.prediction_history[-window_size:]
        accuracy = sum(1 for p, _ in recent if p) / len(recent) if recent else 0.5
        self.accuracy_window.append(accuracy)
        
        # 贝叶斯更新（传递period）
        if hasattr(self, 'capability_belief'):
            lr = 1.5 if prediction_correct else 0.67
            self.capability_belief.update(lr, period=period)
        
        # 更新各因子信念（传递period）
        for factor_name in self.belief_engine.beliefs.get(BeliefLayer.TACTIC, {}):
            evidence_strength = abs(outcome_score) * 2
            self.belief_engine.update_belief(
                factor_name, 
                outcome_score > 0,
                evidence_strength,
                period=period
            )
        
        logger.debug(f"[{self.name}] 学习: 正确={prediction_correct}, 得分={outcome_score:.3f}, "
                    f"最近准确率={accuracy:.1%}, 期间={period}")
    
    def reflect(self) -> dict:
        """执行反思"""
        self.steps_since_reflection = 0
        
        # 收集所有信念的轨迹
        reflections = []
        
        for layer, layer_beliefs in self.belief_engine.beliefs.items():
            for name, belief in layer_beliefs.items():
                if len(belief.trajectory) >= 10:
                    result = self.reflect_fn(belief.trajectory)
                    result['belief_name'] = name
                    result['layer'] = layer.name
                    reflections.append(result)
                    
                    # 根据反思结果调整
                    if result['recommendation'] == 'slow_down':
                        config = self.meta_controller.get_config(self.reflection_type)
                        belief.tension_range *= config['tension_adjust_factor']
                        belief.tension_range = max(0.1, belief.tension_range)
                    elif result['recommendation'] == 'be_more_flexible':
                        config = self.meta_controller.get_config(self.reflection_type)
                        belief.tension_range /= config['tension_adjust_factor']
                        belief.tension_range = min(0.5, belief.tension_range)
        
        return {
            'role': self.name,
            'reflection_type': self.reflection_type.name,
            'reflections': reflections,
            'recent_accuracy': self.accuracy_window[-1] if self.accuracy_window else 0.5,
        }
    
    def get_views_summary(self) -> dict[str, Any]:
        """获取观点摘要"""
        if not self.views:
            return {
                'role': self.name, 
                'view_count': 0,
                'reflection_type': self.reflection_type.name,
                'recent_accuracy': 0.5
            }
        
        latest = self.views[-1]
        return {
            'role': self.name,
            'latest_view': latest.direction.name,
            'confidence': latest.confidence,
            'view_count': len(self.views),
            'avg_score': np.mean([v.score() for v in self.views]) if self.views else 0,
            'reflection_type': self.reflection_type.name,
            'recent_accuracy': self.accuracy_window[-1] if self.accuracy_window else 0.5,
        }


# ============================================================
# 3. 角色实现（带贝叶斯学习）
# ============================================================

class ViewDirection(Enum):
    """观点方向"""
    STRONG_BUY = 2.0
    BUY = 1.0
    HOLD = 0.0
    SELL = -1.0
    STRONG_SELL = -2.0


@dataclass
class ResearchView:
    """投研观点"""
    role: str
    stock: str
    direction: ViewDirection
    confidence: float = 0.5
    reasoning: str = ""
    key_factors: list[str] = field(default_factory=list)
    horizon: str = "medium"
    risks: list[str] = field(default_factory=list)
    
    def score(self) -> float:
        return self.direction.value * self.confidence


class DiscretionaryTrader(BayesianResearchRole):
    """主观交易员 - 激进反思"""
    
    def __init__(self):
        super().__init__("主观交易员", weight=0.8, 
                        reflection_type=ReflectionType.AGGRESSIVE)
    
    def _setup_beliefs(self):
        """设置技术指标信念"""
        self.belief_engine.register_belief("均线突破", BeliefLayer.TACTIC, 0.5, tension_range=0.4)
        self.belief_engine.register_belief("成交量确认", BeliefLayer.TACTIC, 0.5, tension_range=0.4)
        self.belief_engine.register_belief("形态识别", BeliefLayer.TACTIC, 0.3, tension_range=0.5)
    
    def analyze(self, date, stock, data) -> ResearchView:
        """技术分析"""
        self.steps_since_reflection += 1
        if self.steps_since_reflection >= self.reflection_period:
            self.reflect()
        
        prices = data.get('prices', pd.Series())
        volumes = data.get('volumes', pd.Series())
        
        if len(prices) < 20:
            return ResearchView(self.name, stock, ViewDirection.HOLD, 0.3, "数据不足")
        
        ma5 = prices.rolling(5).mean().iloc[-1]
        ma20 = prices.rolling(20).mean().iloc[-1]
        current = prices.iloc[-1]
        
        score = 0.0
        reasoning = []
        
        if current > ma5 > ma20:
            score += 1.0
            reasoning.append("多头排列")
            self.belief_engine.update_belief("均线突破", True, 0.8)
        elif current < ma5 < ma20:
            score -= 1.0
            reasoning.append("空头排列")
            self.belief_engine.update_belief("均线突破", False, 0.8)
        
        if len(volumes) > 0:
            vol_ma = volumes.rolling(20).mean().iloc[-1]
            vol_current = volumes.iloc[-1]
            if vol_ma > 0 and vol_current / vol_ma > 1.5:
                score += 0.3 if score > 0 else -0.3
                reasoning.append("放量")
                self.belief_engine.update_belief("成交量确认", True, 0.6)
        
        direction = ViewDirection.BUY if score > 1.0 else ViewDirection.SELL if score < -1.0 else ViewDirection.HOLD
        confidence = min(0.9, abs(score) / 2.0)
        
        view = ResearchView(self.name, stock, direction, confidence, "; ".join(reasoning), horizon="short")
        self.views.append(view)
        return view


class FinancialAnalyst(BayesianResearchRole):
    """财务分析师 - 保守反思"""
    
    def __init__(self):
        super().__init__("财务分析师", weight=1.2,
                        reflection_type=ReflectionType.CONSERVATIVE)
    
    def _setup_beliefs(self):
        """设置基本面信念"""
        self.belief_engine.register_belief("低估值", BeliefLayer.STYLE, 0.7, tension_range=0.2)
        self.belief_engine.register_belief("高盈利质量", BeliefLayer.STYLE, 0.6, tension_range=0.2)
        self.belief_engine.register_belief("盈利增长", BeliefLayer.TACTIC, 0.5, tension_range=0.25)
    
    def analyze(self, date, stock, data) -> ResearchView:
        """基本面分析"""
        self.steps_since_reflection += 1
        if self.steps_since_reflection >= self.reflection_period:
            self.reflect()
        
        factor_value = data.get('factor_value', pd.Series())
        
        if factor_value.empty:
            return ResearchView(self.name, stock, ViewDirection.HOLD, 0.3, "无财务数据")
        
        latest_score = factor_value.iloc[-1]
        percentile = (factor_value < latest_score).mean()
        
        if percentile < 0.2:
            direction = ViewDirection.BUY
            reasoning = f"估值处于历史低位({percentile:.1%}分位)"
            self.belief_engine.update_belief("低估值", True, 1.0)
        elif percentile > 0.8:
            direction = ViewDirection.SELL
            reasoning = f"估值处于历史高位({percentile:.1%}分位)"
            self.belief_engine.update_belief("低估值", False, 1.0)
        else:
            direction = ViewDirection.HOLD
            reasoning = f"估值处于历史中位({percentile:.1%}分位)"
        
        confidence = abs(0.5 - percentile) * 2
        
        view = ResearchView(self.name, stock, direction, confidence, reasoning, 
                          horizon="long", key_factors=['PE', 'PB', 'ROE'])
        self.views.append(view)
        return view


class MacroEconomist(BayesianResearchRole):
    """宏观经济学家 - 基本面反思"""
    
    def __init__(self):
        super().__init__("宏观经济学家", weight=1.5,
                        reflection_type=ReflectionType.FUNDAMENTAL)
        self.market_regime = "neutral"
    
    def _setup_beliefs(self):
        self.belief_engine.register_belief("牛市判断", BeliefLayer.PHILOSOPHY, 0.3, tension_range=0.15)
        self.belief_engine.register_belief("熊市判断", BeliefLayer.PHILOSOPHY, 0.3, tension_range=0.15)
    
    def analyze(self, date, stock, data) -> ResearchView:
        """宏观分析"""
        self.steps_since_reflection += 1
        if self.steps_since_reflection >= self.reflection_period:
            self.reflect()
        
        returns = data.get('market_returns', pd.Series())
        
        if len(returns) < 60:
            return ResearchView(self.name, stock, ViewDirection.HOLD, 0.3, "数据不足")
        
        vol = returns.iloc[-20:].std() * np.sqrt(252)
        trend = returns.iloc[-60:].sum()
        
        if trend > 0.1 and vol < 0.25:
            self.market_regime = "bull"
            direction = ViewDirection.BUY
            reasoning = "牛市环境，趋势向上"
            self.belief_engine.update_belief("牛市判断", True, 0.9)
        elif trend < -0.1 or vol > 0.35:
            self.market_regime = "bear"
            direction = ViewDirection.SELL
            reasoning = "熊市/高波动环境，降低仓位"
            self.belief_engine.update_belief("熊市判断", True, 0.9)
        else:
            self.market_regime = "neutral"
            direction = ViewDirection.HOLD
            reasoning = "震荡市，观望"
        
        confidence = min(0.9, abs(trend) * 5)
        
        view = ResearchView(self.name, stock, direction, confidence, reasoning,
                          horizon="long", key_factors=['market_regime', 'volatility'])
        self.views.append(view)
        return view


class QuantResearcher(BayesianResearchRole):
    """量化研究员 - 技术反思（统计检验）"""
    
    def __init__(self):
        super().__init__("量化研究员", weight=1.0,
                        reflection_type=ReflectionType.TECHNICAL)
    
    def _setup_beliefs(self):
        self.belief_engine.register_belief("动量因子", BeliefLayer.TACTIC, 0.5, tension_range=0.35)
        self.belief_engine.register_belief("价值因子", BeliefLayer.TACTIC, 0.5, tension_range=0.35)
    
    def analyze(self, date, stock, data) -> ResearchView:
        """量化分析"""
        self.steps_since_reflection += 1
        if self.steps_since_reflection >= self.reflection_period:
            self.reflect()
        
        factor_momentum = data.get('factor_momentum', pd.Series())
        factor_value = data.get('factor_value', pd.Series())
        
        if factor_momentum.empty:
            return ResearchView(self.name, stock, ViewDirection.HOLD, 0.3, "无量化数据")
        
        mom_score = factor_momentum.iloc[-1] if not factor_momentum.empty else 0
        val_score = factor_value.iloc[-1] if not factor_value.empty else 0
        
        composite = 0.5 * mom_score + 0.5 * val_score
        
        if composite > 0.5:
            direction = ViewDirection.BUY
        elif composite < -0.5:
            direction = ViewDirection.SELL
        else:
            direction = ViewDirection.HOLD
        
        confidence = min(0.9, abs(composite))
        
        self.belief_engine.update_belief("动量因子", mom_score > 0, abs(mom_score))
        self.belief_engine.update_belief("价值因子", val_score > 0, abs(val_score))
        
        view = ResearchView(self.name, stock, direction, confidence,
                          f"多因子综合得分: {composite:.3f}",
                          horizon="medium", key_factors=['momentum', 'value'])
        self.views.append(view)
        return view


class RiskAnalyst(BayesianResearchRole):
    """风险分析师 - 保守反思"""
    
    def __init__(self):
        super().__init__("风险分析师", weight=1.2,
                        reflection_type=ReflectionType.CONSERVATIVE)
        self.risk_level = "normal"
    
    def _setup_beliefs(self):
        self.belief_engine.register_belief("VaR预警", BeliefLayer.TACTIC, 0.5, tension_range=0.25)
        self.belief_engine.register_belief("回撤预警", BeliefLayer.TACTIC, 0.5, tension_range=0.25)
    
    def analyze(self, date, stock, data) -> ResearchView:
        """风险分析"""
        self.steps_since_reflection += 1
        if self.steps_since_reflection >= self.reflection_period:
            self.reflect()
        
        returns = data.get('returns', pd.Series())
        
        if len(returns) < 20:
            return ResearchView(self.name, stock, ViewDirection.HOLD, 0.3, "数据不足")
        
        var_95 = np.percentile(returns.iloc[-60:], 5)
        max_dd = (returns.iloc[-60:].cumsum() - returns.iloc[-60:].cumsum().cummax()).min()
        vol = returns.iloc[-20:].std() * np.sqrt(252)
        
        reasoning = []
        risk_flags = []
        score = 0.0
        
        if var_95 < -0.03:
            score -= 1.0
            reasoning.append(f"VaR过高({var_95:.2%})")
            risk_flags.append("high_var")
            self.belief_engine.update_belief("VaR预警", True, 0.9)
        
        if max_dd < -0.15:
            score -= 1.0
            reasoning.append(f"近期回撤大({max_dd:.2%})")
            risk_flags.append("large_drawdown")
            self.belief_engine.update_belief("回撤预警", True, 0.9)
        
        if vol > 0.40:
            score -= 0.5
            reasoning.append(f"高波动({vol:.1%})")
            risk_flags.append("high_volatility")
        
        if score < -1.5:
            direction = ViewDirection.STRONG_SELL
            self.risk_level = "high"
        elif score < -0.5:
            direction = ViewDirection.SELL
            self.risk_level = "elevated"
        else:
            direction = ViewDirection.HOLD
            self.risk_level = "normal"
            reasoning.append("风险可控")
        
        confidence = min(0.9, abs(score) / 2.5)
        
        view = ResearchView(self.name, stock, direction, confidence,
                          "; ".join(reasoning) if reasoning else "风险正常",
                          horizon="short", risks=risk_flags)
        self.views.append(view)
        return view


class IndustryAnalyst(BayesianResearchRole):
    """行业分析师 - 平衡反思"""
    
    def __init__(self, rotation_analyzer: Optional[IndustryRotationAnalyzer] = None):
        super().__init__("行业分析师", weight=1.0,
                        reflection_type=ReflectionType.BALANCED)
        self.rotation_analyzer = rotation_analyzer
    
    def _setup_beliefs(self):
        self.belief_engine.register_belief("行业动量", BeliefLayer.STYLE, 0.5, tension_range=0.3)
        self.belief_engine.register_belief("政策利好", BeliefLayer.TACTIC, 0.3, tension_range=0.4)
    
    def analyze(self, date, stock, data) -> ResearchView:
        """行业分析"""
        self.steps_since_reflection += 1
        if self.steps_since_reflection >= self.reflection_period:
            self.reflect()
        
        industry = data.get('industry', '')
        
        if not industry or self.rotation_analyzer is None:
            return ResearchView(self.name, stock, ViewDirection.HOLD, 0.3, "无行业数据")
        
        rotation = self.rotation_analyzer.get_rotation_signal(date, top_n=10)
        
        if industry in rotation.index:
            rank = rotation.index.get_loc(industry) + 1
            score = rotation[industry]
            
            if rank <= 3:
                direction = ViewDirection.BUY
                reasoning = f"行业处于轮动前3名(第{rank}位)"
            elif rank <= 6:
                direction = ViewDirection.HOLD
                reasoning = f"行业处于轮动中游(第{rank}位)"
            else:
                direction = ViewDirection.SELL
                reasoning = f"行业处于轮动后段(第{rank}位)"
            
            confidence = min(0.9, abs(score) * 2)
            self.belief_engine.update_belief("行业动量", rank <= 5, confidence)
        else:
            direction = ViewDirection.HOLD
            reasoning = "行业不在轮动范围内"
            confidence = 0.3
        
        view = ResearchView(self.name, stock, direction, confidence, reasoning,
                          horizon="medium", key_factors=['industry_momentum'])
        self.views.append(view)
        return view


# ============================================================
# 4. 基金经理风格配置
# ============================================================

class ManagerStyle(Enum):
    """基金经理风格"""
    AGGRESSIVE = "激进"    # 高仓位、高集中度、容忍高波动
    MODERATE = "稳健"      # 平衡配置、中等集中度
    CONSERVATIVE = "保守"  # 低仓位、分散、严格风控


@dataclass
class StyleConfig:
    """风格配置参数"""
    # 仓位参数
    base_position: float = 0.8           # 基础仓位
    max_position: float = 0.10           # 单股最大仓位
    min_position: float = 0.0            # 单股最小仓位
    
    # 集中度参数
    max_concentration: float = 0.30      # 最大行业集中度
    target_stock_count: int = 20         # 目标持股数
    
    # 风控参数
    var_limit: float = -0.03             # VaR限制
    max_drawdown_limit: float = -0.15    # 最大回撤限制
    
    # 决策参数
    consensus_threshold: float = 0.5     # 共识度阈值
    confidence_threshold: float = 0.5    # 最低置信度
    
    # 学习参数
    learning_rate: float = 0.1           # 学习率
    exploration_rate: float = 0.2        # 探索率


class FundManager:
    """基金经理 - 支持风格配置"""
    
    def __init__(self, style: ManagerStyle = ManagerStyle.MODERATE):
        self.name = "基金经理"
        self.roles: dict[str, BayesianResearchRole] = {}
        self.decisions: list['TeamDecision'] = []
        
        # 风格配置
        self.style = style
        self.config = self._get_style_config(style)
        
        logger.info(f"基金经理初始化: {style.value}风格")
    
    def _get_style_config(self, style: ManagerStyle) -> StyleConfig:
        """获取风格配置"""
        configs = {
            ManagerStyle.AGGRESSIVE: StyleConfig(
                base_position=0.95,
                max_position=0.15,
                max_concentration=0.40,
                target_stock_count=15,
                var_limit=-0.05,
                max_drawdown_limit=-0.25,
                consensus_threshold=0.4,
                confidence_threshold=0.4,
                learning_rate=0.15,
                exploration_rate=0.3,
            ),
            ManagerStyle.MODERATE: StyleConfig(
                base_position=0.80,
                max_position=0.10,
                max_concentration=0.30,
                target_stock_count=20,
                var_limit=-0.03,
                max_drawdown_limit=-0.15,
                consensus_threshold=0.5,
                confidence_threshold=0.5,
                learning_rate=0.10,
                exploration_rate=0.2,
            ),
            ManagerStyle.CONSERVATIVE: StyleConfig(
                base_position=0.60,
                max_position=0.08,
                max_concentration=0.20,
                target_stock_count=30,
                var_limit=-0.02,
                max_drawdown_limit=-0.10,
                consensus_threshold=0.7,
                confidence_threshold=0.6,
                learning_rate=0.05,
                exploration_rate=0.1,
            ),
        }
        return configs.get(style, configs[ManagerStyle.MODERATE])
    
    def add_role(self, role: BayesianResearchRole):
        """添加团队成员"""
        self.roles[role.name] = role
        logger.info(f"添加团队成员: {role.name} (权重: {role.weight}, "
                   f"反思: {role.reflection_type.name})")
    
    def make_decision(self,
                     date: pd.Timestamp,
                     stock: str,
                     data: dict[str, Any]) -> 'TeamDecision':
        """做出投资决策"""
        # 1. 收集各角色观点
        votes: dict[str, ResearchView] = {}
        
        for role_name, role in self.roles.items():
            if not role.is_active:
                continue
            try:
                view = role.analyze(date, stock, data)
                votes[role_name] = view
            except Exception as e:
                logger.warning(f"{role_name} 分析失败: {e}")
        
        # 2. 加权汇总（考虑风格）
        weighted_score = 0.0
        total_weight = 0.0
        
        supporting = []
        opposing = []
        risk_flags = []
        
        for role_name, view in votes.items():
            role = self.roles[role_name]
            
            # 根据风格调整权重
            effective_weight = role.weight * view.confidence
            
            # 激进风格：更重视动量和趋势
            if self.style == ManagerStyle.AGGRESSIVE:
                if role_name in ["主观交易员", "量化研究员"]:
                    effective_weight *= 1.2
            
            # 保守风格：更重视基本面和风险
            elif self.style == ManagerStyle.CONSERVATIVE:
                if role_name in ["财务分析师", "风险分析师"]:
                    effective_weight *= 1.3
                if role_name == "宏观经济学家":
                    effective_weight *= 1.2
            
            weighted_score += view.score() * effective_weight
            total_weight += effective_weight
            
            if view.score() > 0:
                supporting.append(role_name)
            elif view.score() < 0:
                opposing.append(role_name)
            
            if view.risks:
                risk_flags.extend(view.risks)
        
        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 0.0
        
        # 3. 共识度
        if len(votes) > 1:
            scores = [v.score() for v in votes.values()]
            consensus = 1.0 - (np.std(scores) / (np.max(np.abs(scores)) + 1e-6))
            consensus = np.clip(consensus, 0, 1)
        else:
            consensus = 0.5
        
        # 4. 映射到方向（考虑风格阈值）
        threshold = self.config.confidence_threshold
        
        if final_score > 1.0:
            direction = ViewDirection.STRONG_BUY
        elif final_score > threshold:
            direction = ViewDirection.BUY
        elif final_score < -1.0:
            direction = ViewDirection.STRONG_SELL
        elif final_score < -threshold:
            direction = ViewDirection.SELL
        else:
            direction = ViewDirection.HOLD
        
        # 5. 仓位建议（考虑风格）
        if direction in [ViewDirection.STRONG_BUY, ViewDirection.BUY]:
            suggested_weight = min(
                self.config.max_position,
                abs(final_score) * self.config.base_position * consensus
            )
        else:
            suggested_weight = 0.0
        
        # 风险调整
        if risk_flags:
            suggested_weight *= 0.7
        
        # 保守风格额外减仓
        if self.style == ManagerStyle.CONSERVATIVE and risk_flags:
            suggested_weight *= 0.7
        
        decision = TeamDecision(
            stock=stock,
            final_direction=direction,
            final_score=final_score,
            consensus_level=consensus,
            votes=votes,
            supporting_roles=supporting,
            opposing_roles=opposing,
            risk_flags=list(set(risk_flags)),
            suggested_weight=suggested_weight,
            max_weight=self.config.max_position
        )
        
        self.decisions.append(decision)
        return decision
    
    def update_role_performance(self, stock: str, actual_return: float):
        """更新角色表现并触发学习"""
        for role_name, role in self.roles.items():
            # 找到该股票最近的观点
            role_views = [v for v in role.views if v.stock == stock]
            if not role_views:
                continue
            
            latest_view = role_views[-1]
            
            # 判断预测是否正确
            prediction_correct = (
                (latest_view.direction.value > 0 and actual_return > 0) or
                (latest_view.direction.value < 0 and actual_return < 0) or
                (latest_view.direction.value == 0 and abs(actual_return) < 0.01)
            )
            
            # 触发学习
            role.learn_from_outcome(prediction_correct, actual_return)
    
    def get_team_report(self) -> dict[str, Any]:
        """获取团队报告"""
        return {
            'manager_style': self.style.value,
            'config': {
                'base_position': self.config.base_position,
                'max_position': self.config.max_position,
                'target_stock_count': self.config.target_stock_count,
            },
            'team_size': len(self.roles),
            'roles': [r.get_views_summary() for r in self.roles.values()],
            'total_decisions': len(self.decisions),
        }


@dataclass
class TeamDecision:
    """团队决策结果"""
    stock: str
    final_direction: ViewDirection
    final_score: float
    consensus_level: float
    votes: dict[str, ResearchView] = field(default_factory=dict)
    supporting_roles: list[str] = field(default_factory=list)
    opposing_roles: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    suggested_weight: float = 0.0
    max_weight: float = 0.1


# ============================================================
# 5. 演示
# ============================================================

def demo_research_team_v2():
    """演示投研团队v2"""
    print("=" * 80)
    print("模拟投研团队 v2 - 贝叶斯学习 + 元控制 + 风格配置")
    print("=" * 80)
    
    # 创建不同风格的基金经理
    for style in [ManagerStyle.AGGRESSIVE, ManagerStyle.MODERATE, ManagerStyle.CONSERVATIVE]:
        print(f"\n{'='*60}")
        print(f"【{style.value}风格基金经理】")
        print(f"{'='*60}")
        
        manager = FundManager(style=style)
        
        # 创建团队成员（带不同反思机制）
        trader = DiscretionaryTrader()
        financial = FinancialAnalyst()
        macro = MacroEconomist()
        quant = QuantResearcher()
        risk = RiskAnalyst()
        
        manager.add_role(trader)
        manager.add_role(financial)
        manager.add_role(macro)
        manager.add_role(quant)
        manager.add_role(risk)
        
        print(f"\n团队配置:")
        for name, role in manager.roles.items():
            print(f"  {name:<15} 反思: {role.reflection_type.name:<12} 权重: {role.weight}")
        
        print(f"\n风格参数:")
        print(f"  基础仓位: {manager.config.base_position:.0%}")
        print(f"  单股上限: {manager.config.max_position:.0%}")
        print(f"  目标持股: {manager.config.target_stock_count}")
        print(f"  共识阈值: {manager.config.consensus_threshold}")
        
        # 模拟数据
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='B')
        prices = pd.Series(100 * (1 + np.random.randn(100).cumsum() * 0.01), index=dates)
        volumes = pd.Series(np.random.randint(1000000, 10000000, 100), index=dates)
        returns = prices.pct_change().fillna(0)
        
        factor_momentum = pd.Series(np.random.randn(100) * 0.5, index=dates)
        factor_value = pd.Series(np.random.randn(100) * 0.3, index=dates)
        
        # 模拟决策
        stock = "000001.SZ"
        date = dates[-1]
        
        data = {
            'prices': prices,
            'volumes': volumes,
            'returns': returns,
            'market_returns': returns,
            'factor_momentum': factor_momentum,
            'factor_value': factor_value,
        }
        
        decision = manager.make_decision(date, stock, data)
        
        print(f"\n决策结果:")
        print(f"  方向: {decision.final_direction.name}")
        print(f"  得分: {decision.final_score:.3f}")
        print(f"  共识: {decision.consensus_level:.1%}")
        print(f"  仓位: {decision.suggested_weight:.2%}")
        
        # 模拟实际收益并触发学习
        actual_return = 0.05  # 假设实际收益5%
        manager.update_role_performance(stock, actual_return)
        
        print(f"\n学习后角色准确率:")
        for name, role in manager.roles.items():
            acc = role.accuracy_window[-1] if role.accuracy_window else 0.5
            print(f"  {name:<15} 准确率: {acc:.1%}")


if __name__ == "__main__":
    demo_research_team_v2()
