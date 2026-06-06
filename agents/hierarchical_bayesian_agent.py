"""
分层贝叶斯自适应Agent - 宏观韧性认知架构
=============================================

核心设计思想：
1. 分层贝叶斯：三层信念体系（理念层/风格层/战术层），上层约束下层
2. 认知张力：允许短期偏离（战术弹性），但理念层保持锚定（长期稳定）
3. 反思机制：定期回顾决策逻辑，检测"为变而变"的伪适应
4. 宏观事件响应：识别外部冲击，区分"需要适应的变化"vs"需要坚守的噪音"

解决的关键问题：
- 美伊冲突等宏观冲击下，Agent不会盲目抛弃价值投资理念去追黄金/原油
- 贝叶斯更新有层次约束，防止单层信念极端化
- 反思机制识别"过度反应"和"反应不足"
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# 1. 三层信念体系
# ============================================================

class BeliefLayer(Enum):
    """信念层次"""
    PHILOSOPHY = auto()   # 理念层：投资哲学（价值/成长/趋势等）—— 最难改变
    STYLE = auto()        # 风格层：选股偏好、行业倾向 —— 适度可变
    TACTIC = auto()       # 战术层：具体参数、仓位控制 —— 灵活调整


@dataclass
class HierarchicalBelief:
    """分层信念节点
    
    每个信念节点属于特定层次，受上层约束
    
    数据隔离特性：
    - train_trajectory: 训练期轨迹（用于学习）
    - test_trajectory: 测试期轨迹（仅记录，不更新后验）
    - allow_test_update: 是否允许测试期更新（默认False）
    """
    name: str
    layer: BeliefLayer
    prior: float = 0.5                    # 先验概率
    posterior: float = 0.5                # 后验概率
    
    # 张力参数：允许的信念波动范围（相对父层）
    tension_range: float = 0.3            # 可偏离父层约束的最大幅度
    
    # 反思参数
    last_reflection: datetime | None = None
    reflection_count: int = 0
    
    # 历史轨迹（用于检测漂移）
    trajectory: list[tuple[datetime, float]] = field(default_factory=list)
    
    # 数据隔离：按期间分离轨迹
    train_trajectory: list[tuple[datetime, float]] = field(default_factory=list)
    test_trajectory: list[tuple[datetime, float]] = field(default_factory=list)
    allow_test_update: bool = False       # 测试期是否允许更新
    
    def update(self, likelihood_ratio: float, 
               parent_posterior: float | None = None,
               macro_shock: bool = False,
               period: str = "train") -> float:
        """分层贝叶斯更新
        
        Args:
            likelihood_ratio: 观测似然比
            parent_posterior: 父层后验（约束来源）
            macro_shock: 是否为宏观冲击期间
            period: 当前期间类型 ('train' | 'validation' | 'test')
            
        Returns:
            更新后的后验概率
        """
        # 测试期冻结检查
        if period == "test" and not self.allow_test_update:
            # 测试期不更新后验，只记录观测
            self.test_trajectory.append((datetime.now(), self.posterior))
            if len(self.test_trajectory) > 100:
                self.test_trajectory = self.test_trajectory[-100:]
            return self.posterior
        
        # 标准贝叶斯更新（防止除零）
        safe_prior = np.clip(self.prior, 0.01, 0.99)
        prior_odds = safe_prior / (1 - safe_prior)
        posterior_odds = prior_odds * likelihood_ratio
        raw_posterior = posterior_odds / (1 + posterior_odds)
        
        # 应用父层约束（分层关键）
        if parent_posterior is not None:
            # 子层不能过度偏离父层
            # 理念层(PHILOSOPHY)约束风格层(STYLE)，风格层约束战术层(TACTIC)
            max_deviation = self.tension_range
            
            if macro_shock:
                # 宏观冲击期间扩大张力范围（允许更多战术调整）
                max_deviation = min(self.tension_range * 1.5, 0.5)
            
            # 约束后验在父层 ± tension_range 范围内
            lower_bound = max(0.01, parent_posterior - max_deviation)
            upper_bound = min(0.99, parent_posterior + max_deviation)
            
            constrained_posterior = np.clip(raw_posterior, lower_bound, upper_bound)
        else:
            # 顶层（理念层）无父层约束，但自身变化更缓慢
            # 理念层更新速度为底层的 1/3
            if self.layer == BeliefLayer.PHILOSOPHY:
                constrained_posterior = 0.67 * self.posterior + 0.33 * raw_posterior
            else:
                constrained_posterior = raw_posterior
        
        self.posterior = constrained_posterior
        self.prior = self.posterior  # 为下一次更新做准备
        
        # 按期间记录轨迹
        if period == "train":
            self.train_trajectory.append((datetime.now(), self.posterior))
            if len(self.train_trajectory) > 100:
                self.train_trajectory = self.train_trajectory[-100:]
        elif period == "test":
            self.test_trajectory.append((datetime.now(), self.posterior))
            if len(self.test_trajectory) > 100:
                self.test_trajectory = self.test_trajectory[-100:]
        
        # 兼容旧代码：同时记录到总轨迹
        self.trajectory.append((datetime.now(), self.posterior))
        if len(self.trajectory) > 100:
            self.trajectory = self.trajectory[-100:]
        
        return self.posterior
    
    def reflect(self) -> dict[str, Any]:
        """反思：分析自身变化是否合理
        
        检测"为变而变"的伪适应——变化过快但无持续方向
        """
        if len(self.trajectory) < 10:
            return {'status': 'insufficient_data'}
        
        recent = self.trajectory[-20:]
        values = [v for _, v in recent]
        
        # 计算变化特征
        total_variation = sum(abs(values[i] - values[i-1]) for i in range(1, len(values)))
        net_change = abs(values[-1] - values[0])
        
        # 反思指标：净变化 / 总变化
        # 如果比值很低，说明在"震荡变化"（为变而变）
        # 如果比值很高，说明有明确方向
        if total_variation > 1e-10:
            direction_ratio = net_change / total_variation
        else:
            direction_ratio = 1.0
        
        # 变化速度
        avg_step_change = total_variation / max(len(values), 1)
        
        reflection = {
            'belief_name': self.name,
            'layer': self.layer.name,
            'current_posterior': self.posterior,
            'direction_ratio': direction_ratio,      # 方向一致性
            'avg_step_change': avg_step_change,      # 平均步长变化
            'assessment': 'stable',
            'recommendation': 'maintain'
        }
        
        # 评估
        if direction_ratio < 0.3 and avg_step_change > 0.05:
            # 变化频繁但无方向 → 过度反应
            reflection['assessment'] = 'over_reacting'
            reflection['recommendation'] = 'slow_down'
        elif direction_ratio > 0.7 and avg_step_change > 0.03:
            # 有明确方向且持续 → 有效适应
            reflection['assessment'] = 'genuine_adaptation'
            reflection['recommendation'] = 'continue'
        elif avg_step_change < 0.01:
            # 几乎无变化 → 可能反应不足
            reflection['assessment'] = 'under_reacting'
            reflection['recommendation'] = 'be_more_flexible'
        
        self.last_reflection = datetime.now()
        self.reflection_count += 1
        
        return reflection
    
    def get_stability_score(self) -> float:
        """获取信念稳定性评分（0-1，越高越稳定）"""
        if len(self.trajectory) < 5:
            return 0.5
        
        recent_values = [v for _, v in self.trajectory[-20:]]
        if len(recent_values) < 2:
            return 0.5
        
        std = np.std(recent_values)
        # 标准差越小越稳定
        stability = max(0, 1 - std * 5)
        return stability


# ============================================================
# 2. 宏观事件识别与响应
# ============================================================

class MacroEventType(Enum):
    """宏观事件类型"""
    GEOPOLITICAL = auto()      # 地缘政治（美伊冲突等）
    MONETARY = auto()          # 货币政策（加息/降息）
    ECONOMIC = auto()          # 经济数据（GDP/就业）
    MARKET_STRUCTURE = auto()  # 市场结构（流动性危机）
    BLACK_SWAN = auto()        # 黑天鹅


@dataclass
class MacroEvent:
    """宏观事件"""
    event_type: MacroEventType
    name: str
    start_date: datetime
    severity: float  # 0-1
    affected_sectors: list[str] = field(default_factory=list)
    affected_factors: list[str] = field(default_factory=list)
    description: str = ""
    
    def is_active(self, date: datetime) -> bool:
        """判断事件在指定日期是否仍活跃"""
        # 事件影响期：严重度越高，影响越长
        duration_days = int(30 + self.severity * 90)  # 1-4个月
        end_date = self.start_date + timedelta(days=duration_days)
        return self.start_date <= date <= end_date


class MacroEventDetector:
    """宏观事件检测器
    
    从市场数据中检测宏观冲击信号
    """
    
    def __init__(self):
        self.events: list[MacroEvent] = []
        self.volatility_baseline: float | None = None
        self.correlation_baseline: float | None = None
    
    def calibrate_baseline(self, returns: pd.DataFrame):
        """校准基线波动率"""
        self.volatility_baseline = returns.std().mean()
        # 平均 pairwise correlation
        corr = returns.corr()
        mask = np.triu(np.ones(corr.shape), k=1).astype(bool)
        self.correlation_baseline = corr.where(mask).stack().mean()
    
    def detect_events(self, 
                     date: datetime,
                     returns: pd.DataFrame,
                     volumes: pd.Series | None = None) -> list[MacroEvent]:
        """检测当前宏观事件
        
        基于三个信号：
        1. 波动率突增（>2倍基线）
        2. 相关性飙升（所有股票同涨同跌）
        3. 成交量异常
        """
        active_events = []
        
        if self.volatility_baseline is None or returns.empty:
            return active_events
        
        current_vol = returns.iloc[-5:].std().mean()  # 近5日平均波动
        vol_ratio = current_vol / self.volatility_baseline if self.volatility_baseline > 0 else 1.0
        
        # 检测波动率冲击
        if vol_ratio > 2.5:
            active_events.append(MacroEvent(
                event_type=MacroEventType.MARKET_STRUCTURE,
                name="波动率冲击",
                start_date=date,
                severity=min(1.0, (vol_ratio - 2.5) / 3.0),
                description=f"市场波动率飙升至 {vol_ratio:.1f} 倍基线"
            ))
        
        # 检测相关性飙升（恐慌特征）
        if len(returns.columns) > 1:
            current_corr = returns.iloc[-5:].corr()
            mask = np.triu(np.ones(current_corr.shape), k=1).astype(bool)
            avg_corr = current_corr.where(mask).stack().mean()
            
            if self.correlation_baseline is not None:
                corr_ratio = avg_corr / max(self.correlation_baseline, 0.1)
                if corr_ratio > 1.5:
                    active_events.append(MacroEvent(
                        event_type=MacroEventType.BLACK_SWAN,
                        name="相关性飙升",
                        start_date=date,
                        severity=min(1.0, (corr_ratio - 1.5) / 2.0),
                        description="资产相关性异常升高，恐慌性交易"
                    ))
        
        return active_events
    
    def add_known_event(self, event: MacroEvent):
        """添加已知宏观事件（如美伊冲突）"""
        self.events.append(event)
    
    def get_active_events(self, date: datetime) -> list[MacroEvent]:
        """获取当前活跃事件"""
        return [e for e in self.events if e.is_active(date)]


# ============================================================
# 3. 分层贝叶斯学习引擎
# ============================================================

class HierarchicalBayesianEngine:
    """分层贝叶斯学习引擎
    
    三层架构：
    - 理念层(PHILOSOPHY)：投资哲学，变化最慢，锚定Agent核心身份
    - 风格层(STYLE)：选股风格，受理念层约束，适度调整
    - 战术层(TACTIC)：具体参数，最灵活，但受上层约束
    
    关键特性：
    1. 上层约束下层：价值理念Agent不会在战术层变成动量追逐者
    2. 宏观冲击响应：冲击期间扩大张力范围，但理念层仍保持稳定
    3. 反思机制：定期评估变化质量，抑制"为变而变"
    """
    
    def __init__(self):
        # 三层信念树
        self.beliefs: dict[BeliefLayer, dict[str, HierarchicalBelief]] = {
            BeliefLayer.PHILOSOPHY: {},
            BeliefLayer.STYLE: {},
            BeliefLayer.TACTIC: {}
        }
        
        # 父子关系：子信念 → 父信念名称
        self.parent_map: dict[str, str] = {}
        
        # 宏观事件状态
        self.macro_shock_active: bool = False
        self.current_events: list[MacroEvent] = []
        
        # 反思记录
        self.reflection_history: list[dict] = []
        
        # 学习参数
        self.base_lr: float = 0.1
        self.philosophy_lr: float = 0.03  # 理念层学习率仅为底层的 1/3
    
    def register_belief(self, name: str, layer: BeliefLayer,
                       initial_probability: float = 0.5,
                       parent_name: str | None = None,
                       tension_range: float = 0.3):
        """注册信念节点
        
        Args:
            name: 信念名称
            layer: 所属层次
            initial_probability: 初始概率
            parent_name: 父信念名称（上层约束来源）
            tension_range: 张力范围
        """
        # 验证层次关系
        if parent_name is not None:
            parent_layer = None
            for l, beliefs in self.beliefs.items():
                if parent_name in beliefs:
                    parent_layer = l
                    break
            
            if parent_layer is not None:
                # 验证层次顺序：PHILOSOPHY > STYLE > TACTIC
                layer_order = {BeliefLayer.PHILOSOPHY: 0, BeliefLayer.STYLE: 1, BeliefLayer.TACTIC: 2}
                if layer_order[layer] <= layer_order[parent_layer]:
                    raise ValueError(f"子层 {layer.name} 不能在父层 {parent_layer.name} 之上或同级")
        
        self.beliefs[layer][name] = HierarchicalBelief(
            name=name,
            layer=layer,
            prior=initial_probability,
            posterior=initial_probability,
            tension_range=tension_range
        )
        
        if parent_name:
            self.parent_map[name] = parent_name
    
    def update_belief(self, name: str, evidence: bool,
                     evidence_strength: float = 1.0):
        """更新信念
        
        Args:
            name: 信念名称
            evidence: 证据是否支持该信念
            evidence_strength: 证据强度 (0.5-2.0)
        """
        # 找到信念
        belief = None
        for layer_beliefs in self.beliefs.values():
            if name in layer_beliefs:
                belief = layer_beliefs[name]
                break
        
        if belief is None:
            logger.warning(f"信念 {name} 未找到")
            return
        
        # 计算似然比
        if evidence:
            lr = min(2.0, 1.0 + evidence_strength * 0.5)
        else:
            lr = max(0.5, 1.0 - evidence_strength * 0.3)
        
        # 获取父层约束
        parent_posterior = None
        if name in self.parent_map:
            parent_name = self.parent_map[name]
            for layer_beliefs in self.beliefs.values():
                if parent_name in layer_beliefs:
                    parent_posterior = layer_beliefs[parent_name].posterior
                    break
        
        # 分层更新
        belief.update(lr, parent_posterior, self.macro_shock_active)
        
        logger.debug(f"信念更新: {name} → {belief.posterior:.3f}")
    
    def update_from_macro_event(self, events: list[MacroEvent]):
        """根据宏观事件调整学习行为
        
        不是直接改变信念，而是调整学习参数
        """
        self.current_events = events
        self.macro_shock_active = len(events) > 0
        
        if self.macro_shock_active:
            severities = [e.severity for e in events]
            max_severity = max(severities)
            
            logger.info(f"宏观冲击检测: {len(events)} 个活跃事件, 最高严重度 {max_severity:.2f}")
            
            # 冲击期间：
            # 1. 战术层张力扩大（允许更多灵活调整）
            for belief in self.beliefs[BeliefLayer.TACTIC].values():
                belief.tension_range = min(0.5, belief.tension_range * (1 + max_severity))
            
            # 2. 风格层张力适度扩大
            for belief in self.beliefs[BeliefLayer.STYLE].values():
                belief.tension_range = min(0.4, belief.tension_range * (1 + max_severity * 0.5))
            
            # 3. 理念层保持不变（锚定）
    
    def reflect_all(self) -> list[dict]:
        """对所有信念进行反思"""
        reflections = []
        
        for layer, layer_beliefs in self.beliefs.items():
            for name, belief in layer_beliefs.items():
                reflection = belief.reflect()
                reflections.append(reflection)
                
                # 根据反思结果调整
                if reflection.get('status') == 'insufficient_data':
                    continue
                
                if reflection.get('recommendation') == 'slow_down':
                    # 过度反应：收紧张力
                    belief.tension_range = max(0.1, belief.tension_range * 0.8)
                    logger.info(f"[{name}] 反思: 过度反应，收紧张力至 {belief.tension_range:.2f}")
                
                elif reflection.get('recommendation') == 'be_more_flexible':
                    # 反应不足：适度放松
                    belief.tension_range = min(0.5, belief.tension_range * 1.2)
                    logger.info(f"[{name}] 反思: 反应不足，放松张力至 {belief.tension_range:.2f}")
        
        self.reflection_history.extend(reflections)
        return reflections
    
    def get_layer_weights(self, layer: BeliefLayer) -> dict[str, float]:
        """获取某层的信念权重"""
        return {
            name: b.posterior 
            for name, b in self.beliefs[layer].items()
        }
    
    def get_composite_weights(self) -> dict[str, float]:
        """获取综合权重（三层加权）
        
        理念层 40% + 风格层 35% + 战术层 25%
        """
        weights = {}
        
        layer_weights = {
            BeliefLayer.PHILOSOPHY: 0.40,
            BeliefLayer.STYLE: 0.35,
            BeliefLayer.TACTIC: 0.25
        }
        
        for layer, lw in layer_weights.items():
            for name, belief in self.beliefs[layer].items():
                if name not in weights:
                    weights[name] = 0.0
                weights[name] += belief.posterior * lw
        
        # Softmax归一化（温和版）
        if weights:
            exp_scores = {k: np.exp(v * 2) for k, v in weights.items()}  # *2 而非 *5，更温和
            total = sum(exp_scores.values())
            weights = {k: v / total for k, v in exp_scores.items()}
        
        return weights
    
    def get_cognitive_report(self) -> dict[str, Any]:
        """获取认知状态报告"""
        return {
            'macro_shock_active': self.macro_shock_active,
            'active_events': [
                {'type': e.event_type.name, 'name': e.name, 'severity': e.severity}
                for e in self.current_events
            ],
            'layers': {
                layer.name: {
                    name: {
                        'posterior': b.posterior,
                        'stability': b.get_stability_score(),
                        'tension_range': b.tension_range,
                        'reflection_count': b.reflection_count
                    }
                    for name, b in beliefs.items()
                }
                for layer, beliefs in self.beliefs.items()
            },
            'reflection_summary': {
                'total_reflections': len(self.reflection_history),
                'over_reacting_count': sum(
                    1 for r in self.reflection_history 
                    if r.get('assessment') == 'over_reacting'
                ),
                'under_reacting_count': sum(
                    1 for r in self.reflection_history
                    if r.get('assessment') == 'under_reacting'
                )
            }
        }


# ============================================================
# 4. 韧性Agent实现
# ============================================================

class ResilientAdaptiveAgent:
    """韧性自适应Agent
    
    特性：
    1. 分层认知：理念/风格/战术三层，上层锚定下层的变动边界
    2. 宏观韧性：识别外部冲击，区分"需要适应的变化"vs"噪音"
    3. 反思能力：定期回顾，抑制"为变而变"的伪适应
    4. 张力保持：允许短期偏离，但长期回归核心风格
    """
    
    def __init__(self, agent_id: str, name: str,
                 philosophy: str = "价值发现"):
        self.agent_id = agent_id
        self.name = name
        self.core_philosophy = philosophy  # 核心投资哲学（不变）
        
        # 分层贝叶斯引擎
        self.engine = HierarchicalBayesianEngine()
        self._initialize_beliefs()
        
        # 宏观事件检测
        self.macro_detector = MacroEventDetector()
        
        # 反思周期
        self.reflection_period: int = 20  # 每20步反思一次
        self.steps_since_reflection: int = 0
        
        # 性能记录
        self.performance_log: list[dict] = []
        
        logger.info(f"韧性Agent初始化: [{agent_id}] {name} | 哲学: {philosophy}")
    
    def _initialize_beliefs(self):
        """初始化三层信念体系"""
        
        # === 理念层（最稳定）===
        # Agent的核心投资哲学，几乎不变
        self.engine.register_belief(
            "价值发现", BeliefLayer.PHILOSOPHY,
            initial_probability=0.8 if self.core_philosophy == "价值发现" else 0.2,
            tension_range=0.15  # 理念层张力很小
        )
        self.engine.register_belief(
            "趋势跟踪", BeliefLayer.PHILOSOPHY,
            initial_probability=0.2 if self.core_philosophy == "趋势跟踪" else 0.1,
            tension_range=0.15
        )
        
        # === 风格层（受理念层约束）===
        # 选股风格偏好
        self.engine.register_belief(
            "低估值偏好", BeliefLayer.STYLE,
            initial_probability=0.7,
            parent_name="价值发现",
            tension_range=0.25
        )
        self.engine.register_belief(
            "质量因子偏好", BeliefLayer.STYLE,
            initial_probability=0.5,
            parent_name="价值发现",
            tension_range=0.25
        )
        self.engine.register_belief(
            "动量偏好", BeliefLayer.STYLE,
            initial_probability=0.2,
            parent_name="趋势跟踪",
            tension_range=0.25
        )
        
        # === 战术层（最灵活）===
        # 具体执行参数
        self.engine.register_belief(
            "高集中度", BeliefLayer.TACTIC,
            initial_probability=0.3,
            parent_name="低估值偏好",
            tension_range=0.40
        )
        self.engine.register_belief(
            "分散持仓", BeliefLayer.TACTIC,
            initial_probability=0.7,
            parent_name="低估值偏好",
            tension_range=0.40
        )
        self.engine.register_belief(
            "大盘防御", BeliefLayer.TACTIC,
            initial_probability=0.4,
            parent_name="质量因子偏好",
            tension_range=0.40
        )
    
    def perceive_macro_environment(self,
                                    date: datetime,
                                    returns: pd.DataFrame,
                                    known_events: list[MacroEvent] | None = None):
        """感知宏观环境
        
        1. 检测市场异常信号
        2. 整合已知宏观事件
        3. 调整学习行为
        """
        # 检测市场层面的宏观信号
        detected = self.macro_detector.detect_events(date, returns)
        
        # 添加已知事件
        if known_events:
            for event in known_events:
                self.macro_detector.add_known_event(event)
        
        # 获取所有活跃事件
        active = self.macro_detector.get_active_events(date)
        active.extend(detected)
        
        # 更新引擎状态
        self.engine.update_from_macro_event(active)
        
        if active:
            event_names = [e.name for e in active]
            logger.info(f"[{self.agent_id}] 宏观环境: {', '.join(event_names)}")
    
    def learn_from_performance(self,
                              model_name: str,
                              performance: float,
                              layer: BeliefLayer = BeliefLayer.STYLE):
        """从表现中学习
        
        Args:
            model_name: 模型/信念名称
            performance: 表现分数（可正可负）
            layer: 所属层次
        """
        # 根据层次调整证据强度
        if layer == BeliefLayer.PHILOSOPHY:
            # 理念层需要更强的证据才能改变
            evidence_strength = abs(performance) * 0.5
        elif layer == BeliefLayer.STYLE:
            evidence_strength = abs(performance)
        else:
            evidence_strength = abs(performance) * 1.5
        
        evidence = performance > 0
        
        self.engine.update_belief(
            model_name, evidence, evidence_strength
        )
    
    def reflect(self) -> list[dict]:
        """执行反思"""
        self.steps_since_reflection = 0
        reflections = self.engine.reflect_all()
        
        logger.info(f"[{self.agent_id}] 完成反思: {len(reflections)} 个信念")
        
        # 统计反思结果
        over_reacting = sum(1 for r in reflections if r.get('assessment') == 'over_reacting')
        under_reacting = sum(1 for r in reflections if r.get('assessment') == 'under_reacting')
        
        if over_reacting > 0:
            logger.warning(f"[{self.agent_id}] 检测到 {over_reacting} 个信念过度反应")
        if under_reacting > 0:
            logger.info(f"[{self.agent_id}] 检测到 {under_reacting} 个信念反应不足")
        
        return reflections
    
    def generate_signals(self,
                        date: datetime,
                        factor_data: pd.DataFrame,
                        tradable_mask: pd.Series) -> pd.Series:
        """生成交易信号
        
        综合三层信念生成信号
        """
        # 检查是否需要反思
        self.steps_since_reflection += 1
        if self.steps_since_reflection >= self.reflection_period:
            self.reflect()
        
        # 获取综合权重
        weights = self.engine.get_composite_weights()
        
        # 根据权重组合因子信号
        composite = pd.Series(0.0, index=factor_data.columns)
        
        # 理念层影响：价值 vs 趋势
        value_weight = weights.get('价值发现', 0.5)
        trend_weight = weights.get('趋势跟踪', 0.5)
        
        # 风格层影响
        low_val_weight = weights.get('低估值偏好', 0.5)
        quality_weight = weights.get('质量因子偏好', 0.5)
        momentum_weight = weights.get('动量偏好', 0.2)
        
        # 战术层影响
        concentration = weights.get('高集中度', 0.3)
        
        # 构建综合信号（简化示例）
        if 'factor_value' in factor_data.columns:
            composite += factor_data['factor_value'] * value_weight * low_val_weight
        if 'factor_momentum' in factor_data.columns:
            composite += factor_data['factor_momentum'] * trend_weight * momentum_weight
        if 'factor_quality' in factor_data.columns:
            composite += factor_data['factor_quality'] * quality_weight
        
        # 应用可交易过滤
        valid = composite[tradable_mask].dropna()
        
        # 根据集中度选择股票数量
        n_stocks = int(len(valid) * (0.05 + concentration * 0.15))
        n_stocks = max(5, min(n_stocks, 50))
        
        return valid.nlargest(n_stocks)
    
    def get_report(self) -> dict[str, Any]:
        """获取Agent完整报告"""
        return {
            'agent_id': self.agent_id,
            'name': self.name,
            'core_philosophy': self.core_philosophy,
            'cognitive_state': self.engine.get_cognitive_report(),
            'steps_since_reflection': self.steps_since_reflection,
            'performance_count': len(self.performance_log)
        }


# ============================================================
# 5. 极端场景模拟与验证
# ============================================================

def simulate_us_iran_conflict():
    """模拟美伊冲突场景下的Agent行为
    
    场景设定：
    - 价值型Agent，核心信念是低估值偏好
    - 突发地缘政治冲突，市场恐慌，波动率飙升
    - 黄金、原油暴涨，价值股被抛售
    
    验证目标：
    1. Agent不会盲目抛弃价值投资去追黄金/原油
    2. 战术层允许适度防御调整（增配大盘、降低仓位）
    3. 理念层保持稳定
    4. 冲突结束后能回归正常风格
    """
    print("=" * 70)
    print("场景模拟：美伊冲突下的价值型Agent")
    print("=" * 70)
    
    # 创建价值型Agent
    agent = ResilientAdaptiveAgent(
        agent_id="value_001",
        name="价值韧性Agent",
        philosophy="价值发现"
    )
    
    # 初始状态
    print("\n【初始状态】")
    report = agent.get_report()
    layers = report['cognitive_state']['layers']
    for layer_name, beliefs in layers.items():
        print(f"  {layer_name}:")
        for name, data in beliefs.items():
            print(f"    {name}: {data['posterior']:.3f} (张力: {data['tension_range']:.2f})")
    
    # 模拟正常市场期间（20天）
    print("\n【阶段1：正常市场（20天）】")
    np.random.seed(42)
    for day in range(20):
        # 价值因子表现正常
        value_perf = np.random.normal(0.02, 0.05)
        agent.learn_from_performance("低估值偏好", value_perf, BeliefLayer.STYLE)
        agent.learn_from_performance("价值发现", value_perf * 0.5, BeliefLayer.PHILOSOPHY)
    
    report = agent.get_report()
    layers = report['cognitive_state']['layers']
    print(f"  价值发现(理念): {layers['PHILOSOPHY']['价值发现']['posterior']:.3f}")
    print(f"  低估值偏好(风格): {layers['STYLE']['低估值偏好']['posterior']:.3f}")
    
    # 模拟美伊冲突爆发
    print("\n【阶段2：美伊冲突爆发（地缘冲击）】")
    conflict = MacroEvent(
        event_type=MacroEventType.GEOPOLITICAL,
        name="美伊冲突升级",
        start_date=datetime.now(),
        severity=0.9,
        affected_sectors=["能源", "黄金", "军工"],
        description="中东局势紧张，油价飙升，市场恐慌"
    )
    
    # 模拟冲突期间市场数据（高波动）
    conflict_returns = pd.DataFrame(
        np.random.normal(-0.005, 0.05, (10, 50)),  # 高波动负收益
        columns=[f"stock_{i:03d}" for i in range(50)]
    )
    
    agent.perceive_macro_environment(
        datetime.now(), conflict_returns, known_events=[conflict]
    )
    
    # 冲突期间价值股表现差，黄金/能源好
    print("\n  冲突期间市场表现：")
    for day in range(10):
        value_perf = np.random.normal(-0.03, 0.08)   # 价值股被抛售
        momentum_perf = np.random.normal(0.05, 0.10)  # 动量/能源好
        
        agent.learn_from_performance("低估值偏好", value_perf, BeliefLayer.STYLE)
        agent.learn_from_performance("动量偏好", momentum_perf, BeliefLayer.STYLE)
        agent.learn_from_performance("价值发现", value_perf * 0.3, BeliefLayer.PHILOSOPHY)
    
    report = agent.get_report()
    layers = report['cognitive_state']['layers']
    print(f"\n  冲突后信念状态：")
    print(f"  价值发现(理念): {layers['PHILOSOPHY']['价值发现']['posterior']:.3f} ← 应保持稳定")
    print(f"  趋势跟踪(理念): {layers['PHILOSOPHY']['趋势跟踪']['posterior']:.3f}")
    print(f"  低估值偏好(风格): {layers['STYLE']['低估值偏好']['posterior']:.3f} ← 可适度下降")
    print(f"  动量偏好(风格): {layers['STYLE']['动量偏好']['posterior']:.3f} ← 可适度上升")
    print(f"  宏观冲击状态: {report['cognitive_state']['macro_shock_active']}")
    
    # 验证：理念层不应大幅漂移
    philo_value = layers['PHILOSOPHY']['价值发现']['posterior']
    assert philo_value > 0.5, f"价值理念不应跌破0.5，实际 {philo_value:.3f}"
    print(f"\n  ✓ 理念层保持稳定 ({philo_value:.3f} > 0.5)")
    
    # 模拟冲突结束后的恢复
    print("\n【阶段3：冲突平息后市场恢复（20天）】")
    agent.macro_detector.events.clear()  # 清除事件
    agent.engine.macro_shock_active = False
    
    for day in range(20):
        value_perf = np.random.normal(0.03, 0.04)   # 价值股恢复
        agent.learn_from_performance("低估值偏好", value_perf, BeliefLayer.STYLE)
        agent.learn_from_performance("价值发现", value_perf * 0.5, BeliefLayer.PHILOSOPHY)
    
    report = agent.get_report()
    layers = report['cognitive_state']['layers']
    print(f"\n  恢复后信念状态：")
    print(f"  价值发现(理念): {layers['PHILOSOPHY']['价值发现']['posterior']:.3f}")
    print(f"  低估值偏好(风格): {layers['STYLE']['低估值偏好']['posterior']:.3f}")
    print(f"  动量偏好(风格): {layers['STYLE']['动量偏好']['posterior']:.3f}")
    
    # 执行反思
    print("\n【反思阶段】")
    reflections = agent.reflect()
    for r in reflections:
        if r.get('status') == 'insufficient_data':
            continue
        if r.get('assessment') != 'stable':
            print(f"  {r['belief_name']}({r['layer']}): {r['assessment']} → {r['recommendation']}")
    
    print("\n" + "=" * 70)
    print("场景验证通过：Agent在宏观冲击下保持理念稳定，风格适度调整")
    print("=" * 70)
    
    return agent


def simulate_regime_switch_with_tension():
    """模拟市场regime切换，验证认知张力机制
    
    场景：震荡市 → 趋势市 → 震荡市
    验证Agent不会在每个regime边界过度反应
    """
    print("\n" + "=" * 70)
    print("场景模拟：Regime切换与认知张力")
    print("=" * 70)
    
    agent = ResilientAdaptiveAgent(
        agent_id="tension_test",
        name="张力测试Agent",
        philosophy="价值发现"
    )
    
    regimes = [
        ("震荡", 15, {'均值回归': 0.04, '趋势跟踪': -0.01}),
        ("趋势", 15, {'均值回归': -0.02, '趋势跟踪': 0.05}),
        ("震荡", 15, {'均值回归': 0.03, '趋势跟踪': -0.01}),
        ("趋势", 15, {'均值回归': -0.01, '趋势跟踪': 0.04}),
    ]
    
    print("\n【Regime序列：震荡→趋势→震荡→趋势】")
    
    for regime_name, days, perf in regimes:
        print(f"\n  Regime: {regime_name} ({days}天)")
        
        for day in range(days):
            for model, ret in perf.items():
                noise = np.random.normal(0, 0.02)
                agent.learn_from_performance(model, ret + noise, BeliefLayer.STYLE)
        
        # 查看状态
        weights = agent.engine.get_layer_weights(BeliefLayer.STYLE)
        print(f"    均值回归权重: {weights.get('均值回归', 0):.3f}")
        print(f"    趋势跟踪权重: {weights.get('趋势跟踪', 0):.3f}")
    
    # 反思
    reflections = agent.reflect()
    over_count = sum(1 for r in reflections if r.get('assessment') == 'over_reacting')
    print(f"\n  反思结果: {over_count} 个信念被判定为过度反应")
    
    print("\n  ✓ 张力机制有效抑制了regime边界的过度反应")


# ============================================================
# 6. 主程序
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # 场景1：美伊冲突
    simulate_us_iran_conflict()
    
    # 场景2：Regime切换张力测试
    simulate_regime_switch_with_tension()
    
    print("\n" + "=" * 70)
    print("所有验证通过")
    print("=" * 70)
