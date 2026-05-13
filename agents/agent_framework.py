"""
多Agent投研框架 - 回测引擎设计
================================

核心场景:
- 多个Agent，每个Agent有独立的投资风格、调仓频率、因子选择
- Agent之间可能产生冲突（同一股票不同方向）
- 需要统一的资金管理、风险控制、绩效归因

设计原则:
1. Agent自治: 每个Agent独立决策，不感知其他Agent
2. 中央调度: 回测引擎负责协调、冲突解决、资金分配
3. 数据共享: 所有Agent共享底层数据，避免重复加载
4. 事件驱动: Agent通过事件机制与回测引擎交互
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from config import BacktestConfig, CostConfig, ExecutionPriceType, FactorConfig, OptimizerConfig, RebalanceConfig, UniverseConfig
from data import DataManager
from execution import ExecutionSimulator, Trade
from factor import FactorCombiner, FactorPipeline
from filter.universe_filter_clean import UniverseFilter
from pending import OrderSide, PendingOrderQueue, create_pending_order
from portfolio import BaseOptimizer, build_optimizer
from rebalance import BaseTrigger, build_trigger
from tracker import PositionTracker

logger = logging.getLogger(__name__)


# ============================================================
# 1. Agent 抽象基类与接口定义
# ============================================================

class AgentStyle(Enum):
    """Agent投资风格"""
    VALUE = auto()           # 价值型
    GROWTH = auto()          # 成长型
    MOMENTUM = auto()        # 动量型
    QUALITY = auto()         # 质量型
    CONTRARIAN = auto()      # 逆向型
    TREND_FOLLOWING = auto() # 趋势跟踪型
    MULTI_FACTOR = auto()    # 多因子型
    CUSTOM = auto()          # 自定义


class SignalDirection(Enum):
    """信号方向"""
    LONG = 1.0      # 做多
    SHORT = -1.0    # 做空
    NEUTRAL = 0.0   # 中性/观望


@dataclass
class AgentSignal:
    """Agent产生的交易信号
    
    每个Agent在每个调仓日产生一组信号
    """
    agent_id: str                           # Agent唯一标识
    date: pd.Timestamp                      # 信号日期
    stock: str                              # 股票代码
    direction: SignalDirection              # 信号方向
    score: float                            # 信号强度/置信度 (-1 ~ 1)
    target_weight: float                    # 目标权重 (0 ~ 1)
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外信息


@dataclass
class AgentConfig:
    """Agent配置
    
    定义Agent的核心参数
    """
    agent_id: str = "agent_001"
    name: str = "Value Agent"
    style: AgentStyle = AgentStyle.VALUE
    
    # 因子配置（每个Agent可以选不同的因子）
    factor_files: list[str] = field(default_factory=list)
    factor_weights: dict[str, float] = field(default_factory=dict)
    factor_config: FactorConfig = field(default_factory=FactorConfig)
    
    # 调仓配置
    rebalance_frequency: str = "monthly"     # daily | weekly | monthly
    rebalance_day: int = 1                   # 每月第几天调仓（1=月初）
    
    # 组合配置
    optimizer_config: OptimizerConfig = field(default_factory=OptimizerConfig)
    target_count: int = 20                   # 目标持股数
    max_weight: float = 0.10                 # 单股最大权重
    
    # 风险控制
    stop_loss: float | None = None           # 止损比例
    take_profit: float | None = None         # 止盈比例
    max_drawdown_limit: float | None = None  # 最大回撤限制
    
    # 资金配置
    initial_capital: float = 10_000_000.0    # 初始资金
    capital_weight: float = 1.0              # 资金分配权重（相对于总资金）


class BaseAgent(ABC):
    """Agent抽象基类
    
    每个Agent代表一个独立的投资策略/投资经理。
    Agent只负责产生信号，不直接执行交易。
    
    v2更新：所有Agent内置分层贝叶斯认知引擎
    - 理念层(PHILOSOPHY)：投资哲学，最难改变
    - 风格层(STYLE)：选股偏好，适度可变  
    - 战术层(TACTIC)：具体参数，灵活调整
    
    每个Agent都有反思能力和张力控制
    """
    
    def __init__(self, config: AgentConfig):
        self.cfg = config
        self.agent_id = config.agent_id
        self.name = config.name
        self.style = config.style
        
        # 状态
        self.is_active: bool = True
        self.signals_history: list[AgentSignal] = []
        
        # 分层贝叶斯认知引擎（所有Agent统一具备）
        self._init_bayesian_engine()
        
        # 学习记录
        self.prediction_history: list[tuple[bool, float]] = []
        self.accuracy_window: list[float] = []
        
        # 反思周期
        self.reflection_period: int = 20
        self.steps_since_reflection: int = 0
        
        logger.info(f"Agent初始化: [{self.agent_id}] {self.name} (风格: {self.style.name})")
    
    def _init_bayesian_engine(self):
        """初始化分层贝叶斯引擎 - 子类可覆盖"""
        try:
            from hierarchical_bayesian_agent import HierarchicalBayesianEngine, BeliefLayer
            self.belief_engine = HierarchicalBayesianEngine()
            self._setup_default_beliefs()
        except ImportError:
            logger.warning(f"[{self.agent_id}] 分层贝叶斯引擎不可用")
            self.belief_engine = None
    
    def _setup_default_beliefs(self):
        """设置默认信念体系 - 子类应覆盖"""
        from hierarchical_bayesian_agent import BeliefLayer
        
        if self.belief_engine is None:
            return
        
        # 理念层：核心投资哲学
        self.belief_engine.register_belief(
            "价值发现", BeliefLayer.PHILOSOPHY, 0.5, tension_range=0.15
        )
        self.belief_engine.register_belief(
            "趋势跟踪", BeliefLayer.PHILOSOPHY, 0.5, tension_range=0.15
        )
        
        # 风格层：选股偏好
        self.belief_engine.register_belief(
            "低估值偏好", BeliefLayer.STYLE, 0.5, 
            parent_name="价值发现", tension_range=0.25
        )
        self.belief_engine.register_belief(
            "动量偏好", BeliefLayer.STYLE, 0.5,
            parent_name="趋势跟踪", tension_range=0.25
        )
        
        # 战术层：执行参数
        self.belief_engine.register_belief(
            "高集中度", BeliefLayer.TACTIC, 0.3,
            parent_name="低估值偏好", tension_range=0.40
        )
        self.belief_engine.register_belief(
            "分散持仓", BeliefLayer.TACTIC, 0.7,
            parent_name="低估值偏好", tension_range=0.40
        )
    
    def learn_from_outcome(self, prediction_correct: bool, 
                          outcome_score: float = 0.0):
        """从预测结果学习
        
        所有Agent统一的学习接口
        """
        self.prediction_history.append((prediction_correct, outcome_score))
        
        # 更新准确率窗口
        window_size = 20
        recent = self.prediction_history[-window_size:]
        accuracy = sum(1 for p, _ in recent if p) / len(recent) if recent else 0.5
        self.accuracy_window.append(accuracy)
        
        # 贝叶斯更新
        if self.belief_engine is not None:
            # 更新"我的分析能力"信念
            for layer_beliefs in self.belief_engine.beliefs.values():
                for belief in layer_beliefs.values():
                    lr = 1.5 if prediction_correct else 0.67
                    belief.update(lr)
        
        logger.debug(f"[{self.agent_id}] 学习: 正确={prediction_correct}, "
                    f"得分={outcome_score:.3f}, 最近准确率={accuracy:.1%}")
    
    def reflect(self) -> dict[str, Any]:
        """执行反思
        
        所有Agent统一的反思接口
        """
        self.steps_since_reflection = 0
        
        if self.belief_engine is None:
            return {'status': 'no_engine'}
        
        reflections = self.belief_engine.reflect_all()
        
        over_reacting = sum(1 for r in reflections 
                          if r.get('assessment') == 'over_reacting')
        under_reacting = sum(1 for r in reflections
                           if r.get('assessment') == 'under_reacting')
        
        if over_reacting > 0:
            logger.info(f"[{self.agent_id}] 反思: {over_reacting} 个信念过度反应")
        if under_reacting > 0:
            logger.info(f"[{self.agent_id}] 反思: {under_reacting} 个信念反应不足")
        
        return {
            'agent_id': self.agent_id,
            'reflections': reflections,
            'over_reacting_count': over_reacting,
            'under_reacting_count': under_reacting,
            'recent_accuracy': self.accuracy_window[-1] if self.accuracy_window else 0.5,
        }
    
    def get_belief_report(self) -> dict[str, Any]:
        """获取信念状态报告"""
        if self.belief_engine is None:
            return {'status': 'no_engine'}
        
        return {
            'agent_id': self.agent_id,
            'cognitive_state': self.belief_engine.get_cognitive_report(),
            'recent_accuracy': self.accuracy_window[-1] if self.accuracy_window else 0.5,
            'prediction_count': len(self.prediction_history),
        }
    
    @abstractmethod
    def prepare_factors(self, data_manager: DataManager) -> pd.DataFrame:
        """准备因子数据
        
        每个Agent可以加载不同的因子文件，使用不同的因子处理方式
        
        Args:
            data_manager: 数据管理器
            
        Returns:
            处理后的复合因子信号 DataFrame (index=dates, columns=stocks)
        """
        pass
    
    @abstractmethod
    def generate_signals(self, 
                        date: pd.Timestamp,
                        composite_signal: pd.Series,
                        tradable_mask: pd.Series,
                        current_portfolio: dict[str, Any]) -> list[AgentSignal]:
        """生成交易信号
        
        Agent的核心决策逻辑。根据因子信号、当前持仓、市场环境等产生交易信号。
        
        Args:
            date: 当前日期
            composite_signal: 当日复合因子信号
            tradable_mask: 可交易股票掩码
            current_portfolio: 当前持仓信息
            
        Returns:
            交易信号列表
        """
        pass
    
    @abstractmethod
    def should_rebalance(self, date: pd.Timestamp, 
                        current_portfolio: dict[str, Any]) -> bool:
        """判断是否调仓
        
        每个Agent可以有自己的调仓频率和触发条件
        
        Args:
            date: 当前日期
            current_portfolio: 当前持仓
            
        Returns:
            是否触发调仓
        """
        pass
    
    def on_market_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """响应市场事件
        
        Agent可以响应市场事件（如停牌、ST、分红等）调整策略
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
        """
        pass
    
    def get_performance_summary(self) -> dict[str, Any]:
        """获取Agent绩效摘要"""
        return {
            'agent_id': self.agent_id,
            'name': self.name,
            'style': self.style.name,
            'is_active': self.is_active,
            'signal_count': len(self.signals_history)
        }


# ============================================================
# 2. 具体Agent实现示例
# ============================================================

class ValueAgent(BaseAgent):
    """价值型Agent
    
    投资风格：低估值、高股息、安全边际
    因子选择：使用现有的 value 因子（模拟PE/PB/股息率合成）
    调仓频率：月度
    """
    
    def __init__(self, agent_id: str = "value_001", 
                 initial_capital: float = 10_000_000.0):
        config = AgentConfig(
            agent_id=agent_id,
            name="价值型Agent",
            style=AgentStyle.VALUE,
            factor_files=['factor_value.pkl'],  # 使用现有的value因子
            factor_weights={'factor_value': 1.0},
            factor_config=FactorConfig(
                winsorize_method='mad',
                winsorize_n=5.0,
                fill_method='median',
                standardize_method='zscore',
                reverse_factor=True  # 低PE=高价值，需要反转
            ),
            rebalance_frequency='monthly',
            rebalance_day=1,
            optimizer_config=OptimizerConfig(
                method='equal_weight',
                target_count=20,
                max_weight=0.08,
                select_top=True
            ),
            initial_capital=initial_capital,
            stop_loss=0.10,
            max_drawdown_limit=0.15
        )
        super().__init__(config)
    
    def prepare_factors(self, data_manager: DataManager) -> pd.DataFrame:
        """准备价值因子"""
        pipeline = FactorPipeline(data_manager, self.cfg.factor_config)
        combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)
        
        processed_factors = {}
        for fname in self.cfg.factor_files:
            raw = data_manager.load_factor(fname)
            key = fname.replace('.pkl', '')
            processed = pipeline.process(raw)
            processed_factors[key] = processed
        
        return combiner.combine(processed_factors)
    
    def generate_signals(self, date: pd.Timestamp,
                        composite_signal: pd.Series,
                        tradable_mask: pd.Series,
                        current_portfolio: dict[str, Any]) -> list[AgentSignal]:
        """生成价值型信号"""
        signals = []
        
        # 只选可交易股票
        valid_signal = composite_signal[tradable_mask].dropna()
        
        # 选择Top N（价值最高 = 得分最高，因为已经反转）
        selected = valid_signal.nlargest(self.cfg.target_count)
        
        for stock, score in selected.items():
            signals.append(AgentSignal(
                agent_id=self.agent_id,
                date=date,
                stock=stock,
                direction=SignalDirection.LONG,
                score=float(score),
                target_weight=1.0 / len(selected),
                metadata={'style': 'value', 'score': float(score)}
            ))
        
        self.signals_history.extend(signals)
        return signals
    
    def should_rebalance(self, date: pd.Timestamp,
                        current_portfolio: dict[str, Any]) -> bool:
        """月度调仓"""
        return date.day == self.cfg.rebalance_day


class MomentumAgent(BaseAgent):
    """动量型Agent
    
    投资风格：趋势跟踪、追涨杀跌
    因子选择：使用现有的 momentum 因子
    调仓频率：月度
    """
    
    def __init__(self, agent_id: str = "momentum_001",
                 initial_capital: float = 10_000_000.0):
        config = AgentConfig(
            agent_id=agent_id,
            name="动量型Agent",
            style=AgentStyle.MOMENTUM,
            factor_files=['factor_momentum.pkl'],
            factor_weights={'factor_momentum': 1.0},
            factor_config=FactorConfig(
                winsorize_method='mad',
                winsorize_n=5.0,
                fill_method='median',
                standardize_method='zscore',
                reverse_factor=False
            ),
            rebalance_frequency='monthly',
            rebalance_day=1,
            optimizer_config=OptimizerConfig(
                method='equal_weight',
                target_count=15,
                max_weight=0.10,
                select_top=True
            ),
            initial_capital=initial_capital,
            stop_loss=0.08,
            max_drawdown_limit=0.20
        )
        super().__init__(config)
    
    def prepare_factors(self, data_manager: DataManager) -> pd.DataFrame:
        """准备动量因子"""
        pipeline = FactorPipeline(data_manager, self.cfg.factor_config)
        combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)
        
        processed_factors = {}
        for fname in self.cfg.factor_files:
            raw = data_manager.load_factor(fname)
            key = fname.replace('.pkl', '')
            processed = pipeline.process(raw)
            processed_factors[key] = processed
        
        return combiner.combine(processed_factors)
    
    def generate_signals(self, date: pd.Timestamp,
                        composite_signal: pd.Series,
                        tradable_mask: pd.Series,
                        current_portfolio: dict[str, Any]) -> list[AgentSignal]:
        """生成动量型信号"""
        signals = []
        
        valid_signal = composite_signal[tradable_mask].dropna()
        selected = valid_signal.nlargest(self.cfg.target_count)
        
        for stock, score in selected.items():
            signals.append(AgentSignal(
                agent_id=self.agent_id,
                date=date,
                stock=stock,
                direction=SignalDirection.LONG,
                score=float(score),
                target_weight=1.0 / len(selected),
                metadata={'style': 'momentum', 'score': float(score)}
            ))
        
        self.signals_history.extend(signals)
        return signals
    
    def should_rebalance(self, date: pd.Timestamp,
                        current_portfolio: dict[str, Any]) -> bool:
        """月度调仓"""
        return date.day == self.cfg.rebalance_day


class ContrarianAgent(BaseAgent):
    """逆向型Agent
    
    投资风格：均值回归、超跌反弹
    因子选择：使用反转因子（负的momentum）
    调仓频率：双月
    """
    
    def __init__(self, agent_id: str = "contrarian_001",
                 initial_capital: float = 10_000_000.0):
        config = AgentConfig(
            agent_id=agent_id,
            name="逆向型Agent",
            style=AgentStyle.CONTRARIAN,
            factor_files=['factor_momentum.pkl'],
            factor_weights={'factor_momentum': 1.0},
            factor_config=FactorConfig(
                winsorize_method='mad',
                winsorize_n=5.0,
                fill_method='median',
                standardize_method='zscore',
                reverse_factor=True  # 反转：选动量最低的股票
            ),
            rebalance_frequency='monthly',
            rebalance_day=1,
            optimizer_config=OptimizerConfig(
                method='equal_weight',
                target_count=20,
                max_weight=0.08,
                select_top=True
            ),
            initial_capital=initial_capital,
            stop_loss=0.15,
            max_drawdown_limit=0.20
        )
        super().__init__(config)
    
    def prepare_factors(self, data_manager: DataManager) -> pd.DataFrame:
        """准备逆向因子（反转的动量）"""
        pipeline = FactorPipeline(data_manager, self.cfg.factor_config)
        combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)
        
        processed_factors = {}
        for fname in self.cfg.factor_files:
            raw = data_manager.load_factor(fname)
            key = fname.replace('.pkl', '')
            processed = pipeline.process(raw)
            processed_factors[key] = processed
        
        return combiner.combine(processed_factors)
    
    def generate_signals(self, date: pd.Timestamp,
                        composite_signal: pd.Series,
                        tradable_mask: pd.Series,
                        current_portfolio: dict[str, Any]) -> list[AgentSignal]:
        """生成逆向型信号"""
        signals = []
        
        valid_signal = composite_signal[tradable_mask].dropna()
        # 选得分最低的（反转后最低 = 原始动量最高，但我们反转了，所以选最低）
        selected = valid_signal.nsmallest(self.cfg.target_count)
        
        for stock, score in selected.items():
            signals.append(AgentSignal(
                agent_id=self.agent_id,
                date=date,
                stock=stock,
                direction=SignalDirection.LONG,
                score=float(score),
                target_weight=1.0 / len(selected),
                metadata={'style': 'contrarian', 'score': float(score)}
            ))
        
        self.signals_history.extend(signals)
        return signals
    
    def should_rebalance(self, date: pd.Timestamp,
                        current_portfolio: dict[str, Any]) -> bool:
        """双月调仓"""
        return date.day == self.cfg.rebalance_day and date.month % 2 == 1


# ============================================================
# 3. 信号聚合器
# ============================================================

class SignalAggregator:
    """信号聚合器
    
    将多个Agent的信号聚合成统一的调仓指令
    """
    
    def __init__(self, aggregation_method: str = "weighted_vote"):
        """
        Args:
            aggregation_method: 聚合方法
                - weighted_vote: 加权投票（默认）
                - majority_vote: 多数投票
                - confidence_weighted: 按置信度加权
                - best_agent: 选表现最好的Agent的信号
        """
        self.aggregation_method = aggregation_method
        self.agent_weights: dict[str, float] = {}  # Agent权重（用于加权投票）
    
    def set_agent_weights(self, weights: dict[str, float]):
        """设置Agent权重"""
        self.agent_weights = weights
    
    def aggregate_signals(self, signals: list[AgentSignal],
                         date: pd.Timestamp) -> pd.DataFrame:
        """聚合信号
        
        Args:
            signals: 所有Agent的信号列表
            date: 当前日期
            
        Returns:
            聚合后的信号 DataFrame (index=stock, columns=[direction, score, weight, ...])
        """
        if not signals:
            return pd.DataFrame()
        
        # 按股票分组
        stock_signals: dict[str, list[AgentSignal]] = {}
        for signal in signals:
            if signal.stock not in stock_signals:
                stock_signals[signal.stock] = []
            stock_signals[signal.stock].append(signal)
        
        # 聚合每只股票的方向和权重
        aggregated = []
        
        for stock, agent_signals in stock_signals.items():
            result = self._aggregate_stock_signals(stock, agent_signals, date)
            if result:
                aggregated.append(result)
        
        if not aggregated:
            return pd.DataFrame()
        
        return pd.DataFrame(aggregated).set_index('stock')
    
    def _aggregate_stock_signals(self, stock: str,
                                  signals: list[AgentSignal],
                                  date: pd.Timestamp) -> dict[str, Any] | None:
        """聚合单只股票的信号"""
        
        if self.aggregation_method == "weighted_vote":
            return self._weighted_vote(stock, signals)
        elif self.aggregation_method == "majority_vote":
            return self._majority_vote(stock, signals)
        elif self.aggregation_method == "confidence_weighted":
            return self._confidence_weighted(stock, signals)
        elif self.aggregation_method == "best_agent":
            return self._best_agent(stock, signals)
        else:
            return self._weighted_vote(stock, signals)
    
    def _weighted_vote(self, stock: str, signals: list[AgentSignal]) -> dict[str, Any]:
        """加权投票"""
        long_score = 0.0
        short_score = 0.0
        total_weight = 0.0
        
        for signal in signals:
            agent_weight = self.agent_weights.get(signal.agent_id, 1.0)
            
            if signal.direction == SignalDirection.LONG:
                long_score += signal.score * agent_weight
            elif signal.direction == SignalDirection.SHORT:
                short_score += abs(signal.score) * agent_weight
            
            total_weight += agent_weight
        
        if total_weight == 0:
            return None
        
        # 净方向
        net_score = (long_score - short_score) / total_weight
        
        if net_score > 0.1:
            direction = SignalDirection.LONG
        elif net_score < -0.1:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL
        
        return {
            'stock': stock,
            'direction': direction,
            'score': net_score,
            'weight': min(abs(net_score), 0.2),  # 最大权重限制
            'long_votes': sum(1 for s in signals if s.direction == SignalDirection.LONG),
            'short_votes': sum(1 for s in signals if s.direction == SignalDirection.SHORT)
        }
    
    def _majority_vote(self, stock: str, signals: list[AgentSignal]) -> dict[str, Any]:
        """多数投票"""
        long_count = sum(1 for s in signals if s.direction == SignalDirection.LONG)
        short_count = sum(1 for s in signals if s.direction == SignalDirection.SHORT)
        
        if long_count > short_count:
            direction = SignalDirection.LONG
            score = long_count / len(signals)
        elif short_count > long_count:
            direction = SignalDirection.SHORT
            score = -short_count / len(signals)
        else:
            direction = SignalDirection.NEUTRAL
            score = 0.0
        
        return {
            'stock': stock,
            'direction': direction,
            'score': score,
            'weight': min(abs(score), 0.2),
            'long_votes': long_count,
            'short_votes': short_count
        }
    
    def _confidence_weighted(self, stock: str, signals: list[AgentSignal]) -> dict[str, Any]:
        """按置信度加权"""
        long_score = 0.0
        short_score = 0.0
        total_confidence = 0.0
        
        for signal in signals:
            confidence = abs(signal.score)
            
            if signal.direction == SignalDirection.LONG:
                long_score += signal.score * confidence
            elif signal.direction == SignalDirection.SHORT:
                short_score += signal.score * confidence
            
            total_confidence += confidence
        
        if total_confidence == 0:
            return None
        
        net_score = (long_score + short_score) / total_confidence
        
        if net_score > 0.1:
            direction = SignalDirection.LONG
        elif net_score < -0.1:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL
        
        return {
            'stock': stock,
            'direction': direction,
            'score': net_score,
            'weight': min(abs(net_score), 0.2),
            'long_votes': sum(1 for s in signals if s.direction == SignalDirection.LONG),
            'short_votes': sum(1 for s in signals if s.direction == SignalDirection.SHORT)
        }
    
    def _best_agent(self, stock: str, signals: list[AgentSignal]) -> dict[str, Any]:
        """选表现最好的Agent的信号"""
        # 简化实现：选得分最高的信号
        best_signal = max(signals, key=lambda s: abs(s.score))
        
        return {
            'stock': stock,
            'direction': best_signal.direction,
            'score': best_signal.score,
            'weight': min(abs(best_signal.score), 0.2),
            'long_votes': sum(1 for s in signals if s.direction == SignalDirection.LONG),
            'short_votes': sum(1 for s in signals if s.direction == SignalDirection.SHORT)
        }


# ============================================================
# 4. 投研团队Agent（新增）
# ============================================================

class ResearchTeamAgent(BaseAgent):
    """投研团队Agent
    
    将research_team_v2中的FundManager包装为BaseAgent子类，
    使其可以无缝接入MultiAgentBacktestEngine。
    
    内部包含7个角色：主观交易员、财务分析师、行业分析师、
    宏观经济学家、量化研究员、风险分析师、基金经理。
    """
    
    def __init__(self, 
                 agent_id: str = "research_team_001",
                 name: str = "投研团队Agent",
                 style: AgentStyle = AgentStyle.MULTI_FACTOR,
                 manager_style: str = "moderate",
                 initial_capital: float = 10_000_000.0,
                 rebalance_frequency: str = "monthly",
                 rebalance_day: int = 1,
                 target_count: int = 20,
                 max_weight: float = 0.10):
        """
        Args:
            agent_id: Agent标识
            name: Agent名称
            style: Agent风格（默认MULTI_FACTOR）
            manager_style: 基金经理风格 ('aggressive' | 'moderate' | 'conservative')
            initial_capital: 初始资金
            rebalance_frequency: 调仓频率
            rebalance_day: 调仓日
            target_count: 目标持股数
            max_weight: 单股最大权重
        """
        # 导入投研团队模块
        try:
            from research_team_v2 import (
                FundManager, ManagerStyle,
                DiscretionaryTrader, FinancialAnalyst, IndustryAnalyst,
                MacroEconomist, QuantResearcher, RiskAnalyst
            )
            from industry_rotation_v2 import IndustryRotationAnalyzer
            self._research_team_available = True
        except ImportError as e:
            logger.warning(f"投研团队模块未完全可用: {e}")
            self._research_team_available = False
        
        # 创建配置
        config = AgentConfig(
            agent_id=agent_id,
            name=name,
            style=style,
            factor_files=['factor_value.pkl', 'factor_momentum.pkl'],
            factor_weights={'factor_value': 0.5, 'factor_momentum': 0.5},
            factor_config=FactorConfig(
                winsorize_method='mad',
                winsorize_n=5.0,
                fill_method='median',
                standardize_method='zscore',
                reverse_factor=False
            ),
            rebalance_frequency=rebalance_frequency,
            rebalance_day=rebalance_day,
            optimizer_config=OptimizerConfig(
                method='equal_weight',
                target_count=target_count,
                max_weight=max_weight,
                select_top=True
            ),
            initial_capital=initial_capital,
            stop_loss=0.10,
            max_drawdown_limit=0.15
        )
        super().__init__(config)
        
        # 基金经理风格
        self.manager_style_str = manager_style.lower()
        
        # 投研团队组件（延迟初始化）
        self.fund_manager: Any = None
        self.industry_analyzer: Any = None
        self.rotation_analyzer: Any = None
        
        # 数据缓存
        self._price_data: pd.DataFrame | None = None
        self._industry_data: pd.DataFrame | None = None
        self._mktcap_data: pd.DataFrame | None = None
        
        logger.info(f"投研团队Agent初始化: [{agent_id}] 基金经理风格={manager_style}")
    
    def _init_research_team(self, data_manager: DataManager):
        """初始化投研团队"""
        if not self._research_team_available:
            return
        
        from research_team_v2 import (
            FundManager, ManagerStyle,
            DiscretionaryTrader, FinancialAnalyst, IndustryAnalyst,
            MacroEconomist, QuantResearcher, RiskAnalyst
        )
        from industry_rotation_v2 import IndustryRotationAnalyzer
        
        # 映射风格字符串
        style_map = {
            'aggressive': ManagerStyle.AGGRESSIVE,
            'moderate': ManagerStyle.MODERATE,
            'conservative': ManagerStyle.CONSERVATIVE
        }
        manager_style = style_map.get(self.manager_style_str, ManagerStyle.MODERATE)
        
        # 创建基金经理
        self.fund_manager = FundManager(style=manager_style)
        
        # 创建行业轮动分析器
        if self._industry_data is not None and self._price_data is not None:
            try:
                self.rotation_analyzer = IndustryRotationAnalyzer(
                    self._industry_data,
                    self._price_data,
                    self._mktcap_data
                )
            except Exception as e:
                logger.warning(f"行业轮动分析器初始化失败: {e}")
                self.rotation_analyzer = None
        
        # 创建团队成员
        self.fund_manager.add_role(DiscretionaryTrader())
        self.fund_manager.add_role(FinancialAnalyst())
        self.fund_manager.add_role(MacroEconomist())
        self.fund_manager.add_role(QuantResearcher())
        self.fund_manager.add_role(RiskAnalyst())
        
        if self.rotation_analyzer is not None:
            self.fund_manager.add_role(IndustryAnalyst(self.rotation_analyzer))
        
        logger.info(f"投研团队初始化完成: {len(self.fund_manager.roles)}个角色")
    
    def prepare_factors(self, data_manager: DataManager) -> pd.DataFrame:
        """准备因子数据
        
        同时缓存价格、行业、市值数据供投研团队使用
        """
        # 准备复合因子（用于回测引擎的标准接口）
        pipeline = FactorPipeline(data_manager, self.cfg.factor_config)
        combiner = FactorCombiner(self.cfg.factor_files, self.cfg.factor_weights)
        
        processed_factors = {}
        for fname in self.cfg.factor_files:
            raw = data_manager.load_factor(fname)
            key = fname.replace('.pkl', '')
            processed = pipeline.process(raw)
            processed_factors[key] = processed
        
        composite = combiner.combine(processed_factors)
        
        # 缓存投研团队需要的数据
        try:
            self._price_data = data_manager.get_adj_price('close', 'forward')
        except:
            pass
        
        try:
            import pickle
            industry_path = data_manager.data_dir / 'industry.pkl'
            if industry_path.exists():
                with open(industry_path, 'rb') as f:
                    self._industry_data = pickle.load(f)
        except:
            pass
        
        try:
            import pickle
            mktcap_path = data_manager.data_dir / 'mktcap.pkl'
            if mktcap_path.exists():
                with open(mktcap_path, 'rb') as f:
                    self._mktcap_data = pickle.load(f)
        except:
            pass
        
        # 初始化投研团队
        self._init_research_team(data_manager)
        
        return composite
    
    def generate_signals(self,
                        date: pd.Timestamp,
                        composite_signal: pd.Series,
                        tradable_mask: pd.Series,
                        current_portfolio: dict[str, Any]) -> list[AgentSignal]:
        """生成交易信号
        
        使用投研团队决策机制生成信号
        """
        signals = []
        
        if not self._research_team_available or self.fund_manager is None:
            # 回退到简单因子选股
            return self._fallback_signals(date, composite_signal, tradable_mask)
        
        # 准备市场数据
        valid_stocks = composite_signal[tradable_mask].dropna().index
        
        # 获取历史价格数据
        prices = pd.Series()
        volumes = pd.Series()
        returns = pd.Series()
        factor_momentum = pd.Series()
        factor_value = pd.Series()
        
        if self._price_data is not None and date in self._price_data.index:
            prices = self._price_data.loc[:date, valid_stocks].iloc[-60:]
            returns = prices.pct_change().fillna(0)
        
        # 对每个股票进行团队决策
        for stock in valid_stocks[:self.cfg.target_count * 2]:  # 分析更多股票，再精选
            try:
                # 准备该股票的数据
                stock_data = {
                    'prices': prices[stock] if stock in prices.columns else pd.Series(),
                    'volumes': volumes,
                    'returns': returns[stock] if stock in returns.columns else pd.Series(),
                    'market_returns': returns.mean(axis=1) if not returns.empty else pd.Series(),
                    'factor_momentum': composite_signal if 'momentum' in str(self.cfg.factor_files) else pd.Series(),
                    'factor_value': composite_signal if 'value' in str(self.cfg.factor_files) else pd.Series(),
                    'industry': self._get_stock_industry(date, stock),
                }
                
                # 投研团队决策
                decision = self.fund_manager.make_decision(date, stock, stock_data)
                
                # 转换为AgentSignal
                if decision.final_direction.value > 0 and decision.suggested_weight > 0:
                    direction = SignalDirection.LONG
                    score = decision.final_score
                    weight = decision.suggested_weight
                elif decision.final_direction.value < 0:
                    direction = SignalDirection.SHORT
                    score = decision.final_score
                    weight = abs(decision.suggested_weight)
                else:
                    continue
                
                signals.append(AgentSignal(
                    agent_id=self.agent_id,
                    date=date,
                    stock=stock,
                    direction=direction,
                    score=float(score),
                    target_weight=float(weight),
                    metadata={
                        'style': 'research_team',
                        'manager_style': self.manager_style_str,
                        'consensus': decision.consensus_level,
                        'supporting': decision.supporting_roles,
                        'opposing': decision.opposing_roles,
                        'risk_flags': decision.risk_flags,
                    }
                ))
                
            except Exception as e:
                logger.debug(f"投研团队分析{stock}失败: {e}")
                continue
        
        # 按权重排序，取Top N
        signals.sort(key=lambda s: abs(s.score), reverse=True)
        signals = signals[:self.cfg.target_count]
        
        # 归一化权重
        if signals:
            total_weight = sum(s.target_weight for s in signals)
            if total_weight > 0:
                for s in signals:
                    s.target_weight = s.target_weight / total_weight * self.cfg.max_weight
        
        self.signals_history.extend(signals)
        
        # 记录团队报告
        if signals:
            report = self.fund_manager.get_team_report()
            logger.info(f"[{date.strftime('%Y-%m-%d')}] 投研团队: "
                       f"分析{len(valid_stocks)}只股票, 选出{len(signals)}只, "
                       f"风格={self.manager_style_str}")
        
        return signals
    
    def _fallback_signals(self, date: pd.Timestamp,
                         composite_signal: pd.Series,
                         tradable_mask: pd.Series) -> list[AgentSignal]:
        """回退信号生成（当投研团队不可用时）"""
        signals = []
        valid_signal = composite_signal[tradable_mask].dropna()
        selected = valid_signal.nlargest(self.cfg.target_count)
        
        for stock, score in selected.items():
            signals.append(AgentSignal(
                agent_id=self.agent_id,
                date=date,
                stock=stock,
                direction=SignalDirection.LONG,
                score=float(score),
                target_weight=1.0 / len(selected),
                metadata={'style': 'fallback', 'reason': 'research_team_unavailable'}
            ))
        
        self.signals_history.extend(signals)
        return signals
    
    def _get_stock_industry(self, date: pd.Timestamp, stock: str) -> str:
        """获取股票行业"""
        if self._industry_data is not None and date in self._industry_data.index:
            day_industry = self._industry_data.loc[date]
            if stock in day_industry.index:
                return day_industry[stock]
        return ""
    
    def should_rebalance(self, date: pd.Timestamp,
                        current_portfolio: dict[str, Any]) -> bool:
        """判断是否调仓"""
        return date.day == self.cfg.rebalance_day
    
    def get_performance_summary(self) -> dict[str, Any]:
        """获取绩效摘要（扩展）"""
        summary = super().get_performance_summary()
        
        if self.fund_manager is not None:
            try:
                team_report = self.fund_manager.get_team_report()
                summary['team_report'] = team_report
            except:
                pass
        
        return summary


# ============================================================
# 5. 多Agent回测引擎
# ============================================================

class MultiAgentBacktestEngine:
    """多Agent回测引擎
    
    核心职责：
    1. 管理共享数据层（DataManager）
    2. 协调多个Agent的调仓节奏
    3. 聚合各Agent的信号
    4. 执行交易并跟踪组合
    5. 生成综合绩效报告
    """
    
    def __init__(self, base_config: BacktestConfig):
        """
        Args:
            base_config: 基础回测配置（共享）
        """
        self.cfg = base_config
        
        # Agent管理
        self.agents: dict[str, BaseAgent] = {}
        self.agent_signals: dict[str, pd.DataFrame] = {}  # Agent预计算的因子信号
        
        # 信号聚合
        self.signal_aggregator = SignalAggregator(aggregation_method="weighted_vote")
        
        # 交易执行 - 使用配置的执行价格类型
        self.executor = ExecutionSimulator(
            base_config.cost,
            execution_price_type=base_config.execution_price_type,
            custom_price_callback=base_config.execution_price_custom_callback
        )
        self.tracker = PositionTracker(0, base_config.initial_capital)  # n_stocks稍后设置
        
        # 绩效跟踪（每个Agent独立）
        self.agent_trackers: dict[str, PositionTracker] = {}
        
        # 数据管理器（延迟初始化）
        self.dm: DataManager | None = None
        self.universe: UniverseFilter | None = None
        
        logger.info("多Agent回测引擎初始化完成")
    
    def register_agent(self, agent: BaseAgent) -> None:
        """注册Agent
        
        Args:
            agent: Agent实例
        """
        self.agents[agent.agent_id] = agent
        
        # 为每个Agent创建独立的持仓跟踪器
        self.agent_trackers[agent.agent_id] = PositionTracker(
            0, agent.cfg.initial_capital
        )
        
        logger.info(f"注册Agent: [{agent.agent_id}] {agent.name}")
    
    def setup(self) -> None:
        """设置回测引擎"""
        logger.info("=" * 70)
        logger.info("【多Agent引擎】设置共享数据层")
        logger.info("=" * 70)
        
        # 1. 数据管理器
        self.dm = DataManager(self.cfg)
        self.tracker.n_stocks = len(self.dm.stock_codes)
        for tracker in self.agent_trackers.values():
            tracker.n_stocks = len(self.dm.stock_codes)
        
        # 2. 股票池过滤器
        self.universe = UniverseFilter(self.dm, self.cfg.universe)
        self.universe.build_masks()
        
        # 3. 每个Agent准备自己的因子
        logger.info("\n【多Agent引擎】各Agent准备因子...")
        for agent_id, agent in self.agents.items():
            logger.info(f"  → [{agent_id}] {agent.name}")
            self.agent_signals[agent_id] = agent.prepare_factors(self.dm)
        
        logger.info("  ✓ 设置完成")
    
    def run(self) -> dict[str, Any]:
        """运行多Agent回测
        
        Returns:
            回测结果
        """
        if self.dm is None:
            raise RuntimeError("请先调用setup()")
        
        logger.info("\n" + "=" * 70)
        logger.info("【多Agent引擎】开始回测")
        logger.info("=" * 70)
        
        for i, date in enumerate(self.dm.trade_dates):
            self._process_trading_day(date, i)
        
        return self._generate_results()
    
    def _process_trading_day(self, date: pd.Timestamp, date_index: int):
        """处理交易日"""
        # 1. 收集需要调仓的Agent
        rebalance_agents = []
        
        for agent_id, agent in self.agents.items():
            if not agent.is_active:
                continue
            
            current_portfolio = self._get_agent_portfolio(agent_id)
            
            if agent.should_rebalance(date, current_portfolio):
                rebalance_agents.append(agent)
        
        if not rebalance_agents:
            # 没有Agent调仓，只更新市值
            self._update_all_portfolios(date)
            return
        
        # 2. 收集所有Agent的信号
        all_signals: list[AgentSignal] = []
        
        for agent in rebalance_agents:
            composite_signal = self.agent_signals[agent.agent_id].loc[date]
            tradable_mask = self.universe.tradable.loc[date]
            current_portfolio = self._get_agent_portfolio(agent.agent_id)
            
            signals = agent.generate_signals(date, composite_signal, 
                                            tradable_mask, current_portfolio)
            all_signals.extend(signals)
        
        # 3. 聚合信号
        aggregated = self.signal_aggregator.aggregate_signals(all_signals, date)
        
        if not aggregated.empty:
            logger.info(f"[{date.strftime('%Y-%m-%d')}] 聚合信号: {len(aggregated)}只股票, "
                       f"做多{sum(aggregated['direction'] == SignalDirection.LONG)}只, "
                       f"做空{sum(aggregated['direction'] == SignalDirection.SHORT)}只")
            
            # 4. 执行交易
            self._execute_aggregated_signals(date, date_index, aggregated)
        
        # 5. 更新所有Agent的持仓市值
        self._update_all_portfolios(date)
    
    def _get_agent_portfolio(self, agent_id: str) -> dict[str, Any]:
        """获取Agent当前持仓"""
        tracker = self.agent_trackers.get(agent_id)
        if tracker is None:
            return {}
        
        positions = tracker.get_all_positions()
        return {
            'cash': tracker.get_cash(),
            'total_value': tracker.get_total_value(),
            'positions': {stock: pos.to_dict() for stock, pos in positions.items()}
        }
    
    def _execute_aggregated_signals(self, date: pd.Timestamp, date_index: int,
                                    aggregated: pd.DataFrame):
        """执行聚合后的信号 - 修复数据窥探：使用执行价格类型确定的价格"""
        # 获取各种价格数据
        adj_open = self.dm.get_adj_price('open', self.cfg.adjustment_type)
        adj_close = self.dm.get_adj_price('close', self.cfg.adjustment_type)
        adj_high = self.dm.get_adj_price('high', self.cfg.adjustment_type)
        adj_low = self.dm.get_adj_price('low', self.cfg.adjustment_type)
        
        for stock, row in aggregated.iterrows():
            if stock not in adj_open.columns or date not in adj_open.index:
                continue
            
            # 获取当日各种价格
            open_price = adj_open.loc[date, stock]
            close_price = adj_close.loc[date, stock] if stock in adj_close.columns else None
            high_price = adj_high.loc[date, stock] if stock in adj_high.columns else None
            low_price = adj_low.loc[date, stock] if stock in adj_low.columns else None
            
            if pd.isna(open_price) or open_price <= 0:
                continue
            
            direction = row['direction']
            target_weight = row['weight']
            
            # 【修复数据窥探】使用执行价格类型确定的价格计算目标仓位
            # 对于OPEN/VWAP，使用开盘价估算；对于CLOSE，使用收盘价（仅测试）
            if self.cfg.execution_price_type == ExecutionPriceType.CLOSE and close_price is not None:
                estimation_price = close_price
            else:
                estimation_price = open_price
            
            # 计算目标持仓
            total_value = self.tracker.get_total_value()
            target_value = target_weight * total_value
            target_qty = int(target_value / estimation_price / 100) * 100
            
            if target_qty <= 0:
                continue
            
            # 获取当前持仓
            current_position = self.tracker.get_position(stock)
            current_qty = current_position.quantity if current_position else 0
            
            # 确定交易方向
            if direction == SignalDirection.LONG:
                # 做多：买入
                if target_qty > current_qty:
                    trade_qty = target_qty - current_qty
                    self._execute_trade(date, stock, OrderSide.BUY, trade_qty, 
                                       open_price, close_price, high_price, low_price)
            
            elif direction == SignalDirection.SHORT:
                # 做空：卖出（如果当前有持仓）
                if current_qty > 0:
                    trade_qty = min(current_qty, target_qty)
                    self._execute_trade(date, stock, OrderSide.SELL, trade_qty,
                                       open_price, close_price, high_price, low_price)
    
    def _execute_trade(self, date: pd.Timestamp, stock: str, side: OrderSide,
                      quantity: int, open_price: float, 
                      close_price: Optional[float] = None,
                      high_price: Optional[float] = None,
                      low_price: Optional[float] = None):
        """执行单笔交易 - 支持多种执行价格类型"""
        success, trade = self.executor.execute_order(
            stock, side, quantity, date, open_price, close_price, high_price, low_price
        )
        
        if success and trade:
            self.tracker.execute_trade(trade)
            
            # 同时更新各Agent的跟踪器（用于归因分析）
            for agent_id, agent_tracker in self.agent_trackers.items():
                # 这里简化处理，实际应该根据Agent的持仓比例分配
                agent_tracker.execute_trade(trade)
    
    def _update_all_portfolios(self, date: pd.Timestamp):
        """更新所有组合的市值"""
        close_prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date]
        
        # 更新总组合
        self.tracker.update_market_values(date, close_prices)
        
        # 更新各Agent组合
        for agent_tracker in self.agent_trackers.values():
            agent_tracker.update_market_values(date, close_prices)
    
    def _generate_results(self) -> dict[str, Any]:
        """生成回测结果"""
        from analytics import PerformanceAnalyzer
        
        results = {
            'total_portfolio': {},
            'agent_portfolios': {}
        }
        
        # 总组合绩效
        total_analyzer = PerformanceAnalyzer()
        total_analyzer.set_data(self.tracker.get_snapshots(), 
                               self.executor.trade_log.get_trades_df())
        results['total_portfolio']['metrics'] = total_analyzer.calculate_performance_metrics()
        
        # 各Agent绩效
        for agent_id, agent_tracker in self.agent_trackers.items():
            agent = self.agents.get(agent_id)
            if agent is None:
                continue
            
            analyzer = PerformanceAnalyzer()
            analyzer.set_data(agent_tracker.get_snapshots(),
                            self.executor.trade_log.get_trades_df())
            
            results['agent_portfolios'][agent_id] = {
                'name': agent.name,
                'style': agent.style.name,
                'metrics': analyzer.calculate_performance_metrics(),
                'signal_count': len(agent.signals_history)
            }
        
        return results


# ============================================================
# 6. 演示与测试
# ============================================================

def demo_multi_agent_backtest():
    """演示多Agent回测"""
    print("=" * 70)
    print("多Agent回测引擎演示")
    print("=" * 70)
    
    from config import BacktestConfig
    
    # 创建基础配置
    config = BacktestConfig()
    config.initial_capital = 50_000_000.0
    
    # 创建回测引擎
    engine = MultiAgentBacktestEngine(config)
    
    # 注册多个Agent
    engine.register_agent(ValueAgent("value_001", 20_000_000))
    engine.register_agent(MomentumAgent("momentum_001", 15_000_000))
    engine.register_agent(ContrarianAgent("contrarian_001", 15_000_000))
    
    # 注册投研团队Agent
    engine.register_agent(ResearchTeamAgent(
        agent_id="research_team_001",
        name="投研团队-稳健",
        manager_style="moderate",
        initial_capital=20_000_000
    ))
    
    print(f"\n已注册 {len(engine.agents)} 个Agent:")
    for agent_id, agent in engine.agents.items():
        print(f"  [{agent_id}] {agent.name} (风格: {agent.style.name})")
    
    # 设置并运行
    try:
        engine.setup()
        results = engine.run()
        
        print("\n" + "=" * 70)
        print("回测结果")
        print("=" * 70)
        
        # 总组合
        total_metrics = results['total_portfolio']['metrics']
        print(f"\n总组合:")
        print(f"  年化收益: {total_metrics.get('annual_return', 0):.2%}")
        print(f"  年化波动: {total_metrics.get('annual_volatility', 0):.2%}")
        print(f"  夏普比率: {total_metrics.get('sharpe_ratio', 0):.2f}")
        print(f"  最大回撤: {total_metrics.get('max_drawdown', 0):.2%}")
        
        # 各Agent
        print(f"\n各Agent绩效:")
        for agent_id, agent_result in results['agent_portfolios'].items():
            metrics = agent_result['metrics']
            print(f"\n  [{agent_id}] {agent_result['name']}")
            print(f"    信号数: {agent_result['signal_count']}")
            print(f"    年化收益: {metrics.get('annual_return', 0):.2%}")
            print(f"    夏普比率: {metrics.get('sharpe_ratio', 0):.2f}")
            print(f"    最大回撤: {metrics.get('max_drawdown', 0):.2%}")
    
    except Exception as e:
        print(f"\n回测执行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    demo_multi_agent_backtest()
