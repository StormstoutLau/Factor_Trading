"""
多维度风控监控模块 (Risk Monitor)

基于用户提供的五维风控框架实现：
- 基本面 (Fundamental)
- 行业 (Industry)
- 宏观 (Macro)
- 资金 (Capital Flow)
- 情绪 (Sentiment)

支持三级预警分级：
- 🟢 三级预警 (低风险): 维持关注
- 🟡 二级预警 (中风险): 调低仓位/暂停买入
- 🔴 一级预警 (高风险): 不计成本清仓

架构设计：
- 松耦合：各维度监控器独立运行，通过 RiskSignal 统一输出
- 可扩展：新增监控维度只需实现 BaseRiskMonitor 接口
- 可配置：各维度权重、阈值、启用状态均可配置
- LLM Ready：预留 LLM 智能体集成接口
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

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================


class RiskLevel(Enum):
    """风险等级"""
    SAFE = 0      # 安全
    LOW = 1       # 🟢 三级预警
    MEDIUM = 2    # 🟡 二级预警
    HIGH = 3      # 🔴 一级预警


@dataclass
class RiskSignal:
    """风险信号"""
    dimension: str           # 维度名称: fundamental/industry/macro/capital/sentiment/composite
    level: RiskLevel         # 风险等级
    score: float             # 风险分数 0-1
    symbol: Optional[str] = None  # 相关股票代码（None表示组合级信号）
    message: str = ""        # 信号描述
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)  # 扩展数据

    def __post_init__(self):
        # 确保score在0-1范围内
        self.score = max(0.0, min(1.0, float(self.score)))

    @property
    def emoji(self) -> str:
        """风险等级表情"""
        return {
            RiskLevel.SAFE: "🟢",
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🔴",
        }.get(self.level, "⚪")

    @property
    def level_name(self) -> str:
        """风险等级名称"""
        return {
            RiskLevel.SAFE: "安全",
            RiskLevel.LOW: "三级预警",
            RiskLevel.MEDIUM: "二级预警",
            RiskLevel.HIGH: "一级预警",
        }.get(self.level, "未知")


@dataclass
class RiskAction:
    """风控动作"""
    action_type: str   # 'hold' | 'reduce' | 'clear' | 'hedge' | 'pause_buy'
    target_symbol: Optional[str] = None  # None表示组合级动作
    params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


# ==================== 监控器基类 ====================


class BaseRiskMonitor(ABC):
    """风险监控器基类"""

    def __init__(self, name: str, enabled: bool = True, weight: float = 1.0):
        self.name = name
        self.enabled = enabled
        self.weight = weight  # 在综合评分中的权重
        self._history: list[RiskSignal] = []

    @abstractmethod
    def monitor(self, symbol: Optional[str] = None, **kwargs) -> RiskSignal:
        """执行监控，返回风险信号"""
        pass

    def get_history(self, n: int = 10) -> list[RiskSignal]:
        """获取最近n条历史信号"""
        return self._history[-n:]

    def _record(self, signal: RiskSignal) -> RiskSignal:
        """记录信号到历史"""
        self._history.append(signal)
        return signal


# ==================== 五维监控器实现 ====================


class FundamentalMonitor(BaseRiskMonitor):
    """
    基本面监控器

    监控指标：
    - 财报异常：营收/利润增速骤降、现金流恶化
    - 风险事件：对外担保、诉讼、关联交易、高管减持
    - 财务健康度：资产负债率、流动比率等
    """

    def __init__(self, enabled: bool = True, weight: float = 1.0):
        super().__init__("fundamental", enabled, weight)
        self.threshold_low = 0.3    # 三级预警阈值
        self.threshold_medium = 0.6  # 二级预警阈值
        self.threshold_high = 0.85   # 一级预警阈值

    def monitor(self, symbol: Optional[str] = None, **kwargs) -> RiskSignal:
        """
        执行基本面监控

        Args:
            symbol: 股票代码
            kwargs:
                - financial_data: dict, 财务数据
                - events: list, 风险事件列表
                - earnings_miss: bool, 业绩miss
                - management_change: bool, 管理层变动
        """
        if not self.enabled:
            return RiskSignal(
                dimension=self.name,
                level=RiskLevel.SAFE,
                score=0.0,
                symbol=symbol,
                message="基本面监控已禁用"
            )

        score = 0.0
        reasons = []

        # 1. 业绩miss检查
        if kwargs.get('earnings_miss', False):
            score += 0.4
            reasons.append("业绩miss")

        # 2. 管理层变动
        if kwargs.get('management_change', False):
            score += 0.3
            reasons.append("管理层变动")

        # 3. 风险事件
        events = kwargs.get('events', [])
        event_scores = {
            'lawsuit': 0.35,
            'guarantee': 0.2,
            'related_party': 0.25,
            'insider_selling': 0.3,
            'audit_opinion': 0.4,
        }
        for event in events:
            event_score = event_scores.get(event, 0.15)
            score += event_score
            reasons.append(f"风险事件: {event}")

        # 4. 财务数据异常
        financial = kwargs.get('financial_data', {})
        if financial:
            # 资产负债率过高 (>80%)
            debt_ratio = financial.get('debt_ratio', 0)
            if debt_ratio > 0.8:
                score += 0.25
                reasons.append(f"资产负债率过高: {debt_ratio:.1%}")

            # 现金流恶化
            cashflow = financial.get('operating_cashflow', 0)
            if cashflow < 0:
                score += 0.2
                reasons.append("经营现金流为负")

            # 营收增速骤降
            revenue_growth = financial.get('revenue_growth', 0)
            if revenue_growth < -0.3:
                score += 0.3
                reasons.append(f"营收增速骤降: {revenue_growth:.1%}")

        # 归一化分数
        score = min(1.0, score)

        # 确定风险等级
        level = self._score_to_level(score)

        message = "; ".join(reasons) if reasons else "基本面正常"

        signal = RiskSignal(
            dimension=self.name,
            level=level,
            score=score,
            symbol=symbol,
            message=message,
            metadata={
                'events': events,
                'financial': financial,
            }
        )

        return self._record(signal)

    def _score_to_level(self, score: float) -> RiskLevel:
        """分数转风险等级"""
        if score >= self.threshold_high:
            return RiskLevel.HIGH
        elif score >= self.threshold_medium:
            return RiskLevel.MEDIUM
        elif score >= self.threshold_low:
            return RiskLevel.LOW
        return RiskLevel.SAFE


class IndustryMonitor(BaseRiskMonitor):
    """
    行业监控器

    监控指标：
    - 行业政策变化
    - 供需变化
    - 技术颠覆风险
    - 行业负面舆情
    """

    def __init__(self, enabled: bool = True, weight: float = 0.8):
        super().__init__("industry", enabled, weight)
        self.threshold_low = 0.35
        self.threshold_medium = 0.65
        self.threshold_high = 0.85

    def monitor(self, symbol: Optional[str] = None, **kwargs) -> RiskSignal:
        """
        执行行业监控

        Args:
            symbol: 股票代码
            kwargs:
                - industry: str, 行业名称
                - policy_changes: list, 政策变化列表
                - supply_demand: str, 供需状况 ('tight'|'balanced'|'oversupply')
                - tech_disruption: bool, 技术颠覆风险
                - negative_news: list, 负面新闻列表
        """
        if not self.enabled:
            return RiskSignal(
                dimension=self.name,
                level=RiskLevel.SAFE,
                score=0.0,
                symbol=symbol,
                message="行业监控已禁用"
            )

        score = 0.0
        reasons = []

        # 1. 政策变化
        policies = kwargs.get('policy_changes', [])
        policy_scores = {
            'restrictive': 0.5,      # 限制性政策
            'investigation': 0.4,    # 行业调查
            'tax_increase': 0.3,     # 加税
            'license_revoke': 0.6,   # 吊销牌照
        }
        for policy in policies:
            ps = policy_scores.get(policy, 0.2)
            score += ps
            reasons.append(f"政策变化: {policy}")

        # 2. 供需状况
        sd = kwargs.get('supply_demand', 'balanced')
        if sd == 'oversupply':
            score += 0.25
            reasons.append("行业产能过剩")
        elif sd == 'tight':
            score -= 0.1  # 供不应求是利好

        # 3. 技术颠覆
        if kwargs.get('tech_disruption', False):
            score += 0.45
            reasons.append("技术颠覆风险")

        # 4. 负面舆情
        negative_news = kwargs.get('negative_news', [])
        score += min(0.3, len(negative_news) * 0.1)
        if negative_news:
            reasons.append(f"行业负面舆情: {len(negative_news)}条")

        score = max(0.0, min(1.0, score))
        level = self._score_to_level(score)

        message = "; ".join(reasons) if reasons else "行业状况正常"

        return self._record(RiskSignal(
            dimension=self.name,
            level=level,
            score=score,
            symbol=symbol,
            message=message,
            metadata={
                'industry': kwargs.get('industry'),
                'policies': policies,
            }
        ))

    def _score_to_level(self, score: float) -> RiskLevel:
        if score >= self.threshold_high:
            return RiskLevel.HIGH
        elif score >= self.threshold_medium:
            return RiskLevel.MEDIUM
        elif score >= self.threshold_low:
            return RiskLevel.LOW
        return RiskLevel.SAFE


class MacroMonitor(BaseRiskMonitor):
    """
    宏观监控器

    监控指标：
    - 利率变化
    - PMI走势
    - 地缘政治/贸易政策
    - 系统性风险
    """

    def __init__(self, enabled: bool = True, weight: float = 0.9):
        super().__init__("macro", enabled, weight)
        self.threshold_low = 0.3
        self.threshold_medium = 0.6
        self.threshold_high = 0.8

    def monitor(self, symbol: Optional[str] = None, **kwargs) -> RiskSignal:
        """
        执行宏观监控

        Args:
            symbol: 股票代码（宏观监控通常忽略）
            kwargs:
                - interest_rate_change: float, 利率变化(bp)
                - pmi: float, PMI指数
                - pmi_trend: str, PMI趋势 ('up'|'down'|'stable')
                - geopolitical_events: list, 地缘事件
                - trade_policy: list, 贸易政策变化
                - market_stress: float, 市场压力指数 0-1
        """
        if not self.enabled:
            return RiskSignal(
                dimension=self.name,
                level=RiskLevel.SAFE,
                score=0.0,
                symbol=symbol,
                message="宏观监控已禁用"
            )

        score = 0.0
        reasons = []

        # 1. 利率变化（加息利空股市）
        rate_change = kwargs.get('interest_rate_change', 0)
        if rate_change >= 50:  # 加息50bp以上
            score += 0.3
            reasons.append(f"大幅加息: +{rate_change}bp")
        elif rate_change >= 25:
            score += 0.15
            reasons.append(f"加息: +{rate_change}bp")

        # 2. PMI走势
        pmi = kwargs.get('pmi', 50)
        pmi_trend = kwargs.get('pmi_trend', 'stable')
        if pmi < 45:
            score += 0.3
            reasons.append(f"PMI深度萎缩: {pmi}")
        elif pmi < 50:
            score += 0.15
            reasons.append(f"PMI低于荣枯线: {pmi}")

        if pmi_trend == 'down' and pmi < 50:
            score += 0.15
            reasons.append("PMI下行趋势")

        # 3. 地缘政治
        geo_events = kwargs.get('geopolitical_events', [])
        geo_scores = {
            'war': 0.5,
            'sanctions': 0.4,
            'trade_war': 0.35,
            'election_uncertainty': 0.25,
        }
        for event in geo_events:
            es = geo_scores.get(event, 0.2)
            score += es
            reasons.append(f"地缘事件: {event}")

        # 4. 市场压力
        market_stress = kwargs.get('market_stress', 0)
        score += market_stress * 0.4
        if market_stress > 0.5:
            reasons.append(f"市场压力指数高: {market_stress:.2f}")

        score = min(1.0, score)
        level = self._score_to_level(score)

        message = "; ".join(reasons) if reasons else "宏观环境正常"

        return self._record(RiskSignal(
            dimension=self.name,
            level=level,
            score=score,
            symbol=symbol,
            message=message,
            metadata={
                'pmi': pmi,
                'rate_change': rate_change,
                'market_stress': market_stress,
            }
        ))

    def _score_to_level(self, score: float) -> RiskLevel:
        if score >= self.threshold_high:
            return RiskLevel.HIGH
        elif score >= self.threshold_medium:
            return RiskLevel.MEDIUM
        elif score >= self.threshold_low:
            return RiskLevel.LOW
        return RiskLevel.SAFE


class CapitalFlowMonitor(BaseRiskMonitor):
    """
    资金监控器

    监控指标：
    - 主力净流入/出
    - 北向资金增减持
    - 龙虎榜席位异常
    - 大宗交易折价
    """

    def __init__(self, enabled: bool = True, weight: float = 0.7):
        super().__init__("capital_flow", enabled, weight)
        self.threshold_low = 0.35
        self.threshold_medium = 0.65
        self.threshold_high = 0.85

    def monitor(self, symbol: Optional[str] = None, **kwargs) -> RiskSignal:
        """
        执行资金监控

        Args:
            symbol: 股票代码
            kwargs:
                - main_force_net_inflow: float, 主力净流入(万元)
                - northbound_change: float, 北向资金变化(万股)
                - dragon_tiger: list, 龙虎榜席位
                - block_trade_discount: float, 大宗交易折价率
                - turnover_rate: float, 换手率
                - turnover_rate_20d_avg: float, 20日平均换手率
        """
        if not self.enabled:
            return RiskSignal(
                dimension=self.name,
                level=RiskLevel.SAFE,
                score=0.0,
                symbol=symbol,
                message="资金监控已禁用"
            )

        score = 0.0
        reasons = []

        # 1. 主力资金大幅流出
        main_force = kwargs.get('main_force_net_inflow', 0)
        if main_force < -5000:  # 流出5000万以上
            score += 0.35
            reasons.append(f"主力资金大幅流出: {main_force/10000:.0f}万")
        elif main_force < -1000:
            score += 0.15
            reasons.append(f"主力资金流出: {main_force/10000:.0f}万")

        # 2. 北向资金减持
        northbound = kwargs.get('northbound_change', 0)
        if northbound < -100:  # 减持100万股以上
            score += 0.25
            reasons.append(f"北向资金大幅减持: {northbound:.0f}万股")

        # 3. 龙虎榜异常
        dragon_tiger = kwargs.get('dragon_tiger', [])
        if dragon_tiger:
            # 机构席位大量卖出
            institutional_sell = sum(1 for d in dragon_tiger if d.get('type') == 'institutional_sell')
            if institutional_sell >= 2:
                score += 0.3
                reasons.append(f"机构席位卖出: {institutional_sell}家")

        # 4. 大宗交易大幅折价
        discount = kwargs.get('block_trade_discount', 0)
        if discount > 0.1:  # 折价超过10%
            score += 0.25
            reasons.append(f"大宗交易折价: {discount:.1%}")

        # 5. 换手率异常（放量下跌）
        turnover = kwargs.get('turnover_rate', 0)
        turnover_avg = kwargs.get('turnover_rate_20d_avg', turnover)
        if turnover_avg > 0 and turnover > turnover_avg * 3:
            score += 0.2
            reasons.append(f"换手率异常: {turnover:.1%} (20日均值: {turnover_avg:.1%})")

        score = min(1.0, score)
        level = self._score_to_level(score)

        message = "; ".join(reasons) if reasons else "资金流向正常"

        return self._record(RiskSignal(
            dimension=self.name,
            level=level,
            score=score,
            symbol=symbol,
            message=message,
            metadata={
                'main_force': main_force,
                'northbound': northbound,
                'turnover': turnover,
            }
        ))

    def _score_to_level(self, score: float) -> RiskLevel:
        if score >= self.threshold_high:
            return RiskLevel.HIGH
        elif score >= self.threshold_medium:
            return RiskLevel.MEDIUM
        elif score >= self.threshold_low:
            return RiskLevel.LOW
        return RiskLevel.SAFE


class SentimentMonitor(BaseRiskMonitor):
    """
    情绪监控器

    监控指标：
    - 换手率/波动率
    - 融资融券余额变化
    - 社交媒体情绪
    - 股价异动（跳空、长上影线等）
    """

    def __init__(self, enabled: bool = True, weight: float = 0.6):
        super().__init__("sentiment", enabled, weight)
        self.threshold_low = 0.3
        self.threshold_medium = 0.6
        self.threshold_high = 0.85

    def monitor(self, symbol: Optional[str] = None, **kwargs) -> RiskSignal:
        """
        执行情绪监控

        Args:
            symbol: 股票代码
            kwargs:
                - volatility: float, 波动率
                - volatility_20d_avg: float, 20日平均波动率
                - margin_balance_change: float, 融资余额变化率
                - social_sentiment: float, 社交媒体情绪分数 -1~1
                - price_gap: float, 跳空幅度
                - upper_shadow_ratio: float, 上影线比例
                - limit_down: bool, 是否跌停
        """
        if not self.enabled:
            return RiskSignal(
                dimension=self.name,
                level=RiskLevel.SAFE,
                score=0.0,
                symbol=symbol,
                message="情绪监控已禁用"
            )

        score = 0.0
        reasons = []

        # 1. 波动率异常
        vol = kwargs.get('volatility', 0)
        vol_avg = kwargs.get('volatility_20d_avg', vol)
        if vol_avg > 0 and vol > vol_avg * 2.5:
            score += 0.25
            reasons.append(f"波动率异常: {vol:.1%} (20日均值: {vol_avg:.1%})")

        # 2. 融资余额快速下降（杠杆资金撤离）
        margin_change = kwargs.get('margin_balance_change', 0)
        if margin_change < -0.15:  # 下降超过15%
            score += 0.3
            reasons.append(f"融资余额快速下降: {margin_change:.1%}")

        # 3. 社交媒体情绪极度负面
        sentiment = kwargs.get('social_sentiment', 0)
        if sentiment < -0.7:
            score += 0.2
            reasons.append(f"社交媒体情绪极度负面: {sentiment:.2f}")

        # 4. 向下跳空
        price_gap = kwargs.get('price_gap', 0)
        if price_gap < -0.05:  # 向下跳空5%
            score += 0.25
            reasons.append(f"向下跳空: {price_gap:.1%}")

        # 5. 长上影线（冲高回落）
        upper_shadow = kwargs.get('upper_shadow_ratio', 0)
        if upper_shadow > 0.05:  # 上影线超过5%
            score += 0.15
            reasons.append(f"长上影线: {upper_shadow:.1%}")

        # 6. 跌停
        if kwargs.get('limit_down', False):
            score += 0.4
            reasons.append("跌停")

        score = min(1.0, score)
        level = self._score_to_level(score)

        message = "; ".join(reasons) if reasons else "市场情绪正常"

        return self._record(RiskSignal(
            dimension=self.name,
            level=level,
            score=score,
            symbol=symbol,
            message=message,
            metadata={
                'volatility': vol,
                'sentiment': sentiment,
                'margin_change': margin_change,
            }
        ))

    def _score_to_level(self, score: float) -> RiskLevel:
        if score >= self.threshold_high:
            return RiskLevel.HIGH
        elif score >= self.threshold_medium:
            return RiskLevel.MEDIUM
        elif score >= self.threshold_low:
            return RiskLevel.LOW
        return RiskLevel.SAFE


# ==================== 综合风控引擎 ====================


class CompositeRiskEngine:
    """
    综合风控引擎

    整合五维监控器，计算综合风险评分，生成分级风控动作
    """

    def __init__(self, monitors: Optional[list[BaseRiskMonitor]] = None):
        self.monitors = monitors or [
            FundamentalMonitor(),
            IndustryMonitor(),
            MacroMonitor(),
            CapitalFlowMonitor(),
            SentimentMonitor(),
        ]
        self._signal_history: list[RiskSignal] = []
        self._action_history: list[RiskAction] = []

    def add_monitor(self, monitor: BaseRiskMonitor) -> None:
        """添加监控器"""
        self.monitors.append(monitor)

    def remove_monitor(self, monitor_name: str) -> None:
        """移除监控器"""
        self.monitors = [m for m in self.monitors if m.name != monitor_name]
        self._signal_history: list[RiskSignal] = []
        self._action_history: list[RiskAction] = []

    def evaluate(self, symbol: Optional[str] = None, **kwargs) -> tuple[RiskSignal, list[RiskAction]]:
        """
        执行综合风险评估

        Args:
            symbol: 股票代码（None表示组合级评估）
            kwargs: 各维度监控参数
                - fundamental: dict, 基本面参数
                - industry: dict, 行业参数
                - macro: dict, 宏观参数
                - capital: dict, 资金参数
                - sentiment: dict, 情绪参数

        Returns:
            (综合风险信号, 风控动作列表)
        """
        signals = []
        dimension_params = {
            'fundamental': kwargs.get('fundamental', {}),
            'industry': kwargs.get('industry', {}),
            'macro': kwargs.get('macro', {}),
            'capital': kwargs.get('capital', {}),
            'sentiment': kwargs.get('sentiment', {}),
            'global_contagion': kwargs.get('global_contagion', {}),
        }

        # 收集各维度信号
        for monitor in self.monitors:
            params = dimension_params.get(monitor.name, {})
            signal = monitor.monitor(symbol=symbol, **params)
            signals.append(signal)
            logger.debug(f"{monitor.name}: {signal.level_name} (score={signal.score:.2f})")

        # 计算加权综合分数
        total_weight = sum(m.weight for m in self.monitors if m.enabled)
        if total_weight == 0:
            composite_score = 0.0
        else:
            composite_score = sum(
                s.score * m.weight
                for s, m in zip(signals, self.monitors)
                if m.enabled
            ) / total_weight

        # 确定综合风险等级（取最高等级）
        max_level = max((s.level for s in signals), key=lambda x: x.value, default=RiskLevel.SAFE)

        # 如果综合分数超过阈值，提升风险等级
        if composite_score >= 0.8:
            max_level = RiskLevel.HIGH
        elif composite_score >= 0.6:
            max_level = max([max_level, RiskLevel.MEDIUM], key=lambda x: x.value)

        composite_signal = RiskSignal(
            dimension="composite",
            level=max_level,
            score=composite_score,
            symbol=symbol,
            message=f"综合评分: {composite_score:.2f}, 最高维度: {max_level.name}",
            metadata={
                'dimension_signals': [
                    {'dimension': s.dimension, 'level': s.level.name, 'score': s.score}
                    for s in signals
                ]
            }
        )

        self._signal_history.append(composite_signal)

        # 生成风控动作
        actions = self._generate_actions(composite_signal, signals, symbol)
        self._action_history.extend(actions)

        return composite_signal, actions

    def _generate_actions(
        self,
        composite: RiskSignal,
        signals: list[RiskSignal],
        symbol: Optional[str]
    ) -> list[RiskAction]:
        """根据风险等级生成风控动作"""
        actions = []

        if composite.level == RiskLevel.HIGH:
            # 🔴 一级预警：不计成本清仓
            actions.append(RiskAction(
                action_type='clear',
                target_symbol=symbol,
                params={'urgency': 'immediate'},
                reason=f"{composite.emoji} 一级预警: {composite.message}"
            ))
            # 如果是组合级信号，暂停所有买入
            if symbol is None:
                actions.append(RiskAction(
                    action_type='pause_buy',
                    reason="组合级一级预警，暂停新买入"
                ))

        elif composite.level == RiskLevel.MEDIUM:
            # 🟡 二级预警：调低仓位，暂停买入
            actions.append(RiskAction(
                action_type='reduce',
                target_symbol=symbol,
                params={'target_ratio': 0.5},  # 减仓至50%
                reason=f"{composite.emoji} 二级预警: {composite.message}"
            ))
            if symbol is None:
                actions.append(RiskAction(
                    action_type='pause_buy',
                    reason="组合级二级预警，暂停新买入"
                ))

        elif composite.level == RiskLevel.LOW:
            # 🟢 三级预警：维持关注，小幅降低目标仓位
            actions.append(RiskAction(
                action_type='hold',
                target_symbol=symbol,
                params={'reduce_target_weight': 0.1},  # 目标权重降低10%
                reason=f"{composite.emoji} 三级预警: {composite.message}"
            ))

        return actions

    def get_summary(self, n: int = 5) -> dict[str, Any]:
        """获取风控摘要"""
        recent_signals = self._signal_history[-n:]

        if not recent_signals:
            return {"status": "无风险信号记录"}

        latest = recent_signals[-1]

        return {
            "latest_level": latest.level_name,
            "latest_score": latest.score,
            "latest_emoji": latest.emoji,
            "signal_count": len(self._signal_history),
            "high_risk_count": sum(1 for s in self._signal_history if s.level == RiskLevel.HIGH),
            "medium_risk_count": sum(1 for s in self._signal_history if s.level == RiskLevel.MEDIUM),
            "recent_signals": [
                {
                    "time": s.timestamp.strftime("%H:%M:%S"),
                    "dimension": s.dimension,
                    "level": s.level_name,
                    "score": s.score,
                    "symbol": s.symbol,
                }
                for s in recent_signals
            ],
        }


# ==================== LLM 智能体集成接口 ====================


class LLMRiskAgent:
    """
    LLM 风险智能体接口

    预留LLM集成能力：
    - 非结构化数据解析（财报、公告、新闻）
    - 风险事件语义理解
    - 多智能体协作决策

    当前为基于关键词的模拟实现，可替换为真实LLM调用。
    替换方式：继承此类并重写 analyze_text 和 generate_report 方法。
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._call_count = 0

    def analyze_text(self, text: str, context: dict[str, Any]) -> RiskSignal:
        """
        分析非结构化文本，提取风险信号

        Args:
            text: 待分析的文本（财报、公告、新闻等）
            context: 上下文信息

        Returns:
            RiskSignal
        """
        if not self.enabled:
            return RiskSignal(
                dimension="llm",
                level=RiskLevel.SAFE,
                score=0.0,
                message="LLM智能体已禁用"
            )

        self._call_count += 1

        # 模拟分析：基于关键词的风险评分
        # 实际部署时应替换为LLM API调用，例如：
        #   response = openai.ChatCompletion.create(...)
        #   score = parse_risk_score(response)
        risk_keywords = {
            '亏损': 0.3,
            '下降': 0.2,
            '诉讼': 0.4,
            '调查': 0.5,
            '违约': 0.6,
            '退市': 0.9,
            '造假': 0.9,
            '破产': 0.95,
        }

        score = 0.0
        found_keywords = []
        for keyword, kw_score in risk_keywords.items():
            if keyword in text:
                score += kw_score
                found_keywords.append(keyword)

        score = min(1.0, score)

        if score >= 0.7:
            level = RiskLevel.HIGH
        elif score >= 0.4:
            level = RiskLevel.MEDIUM
        elif score >= 0.2:
            level = RiskLevel.LOW
        else:
            level = RiskLevel.SAFE

        return RiskSignal(
            dimension="llm",
            level=level,
            score=score,
            message=f"LLM分析发现风险关键词: {', '.join(found_keywords)}" if found_keywords else "LLM分析无显著风险",
            metadata={
                'keywords': found_keywords,
                'text_length': len(text),
            }
        )

    def generate_report(self, signals: list[RiskSignal]) -> str:
        """
        生成综合风险报告

        Args:
            signals: 风险信号列表

        Returns:
            风险报告文本
        """
        if not self.enabled:
            return "LLM智能体已禁用，无法生成报告"

        # 模拟报告生成：结构化文本输出
        # 实际部署时可替换为LLM生成自然语言报告，例如：
        #   prompt = build_report_prompt(signals)
        #   report = llm.generate(prompt)
        lines = ["# 风险监控报告", ""]

        for signal in signals:
            lines.append(f"## {signal.dimension} - {signal.emoji} {signal.level_name}")
            lines.append(f"- 风险分数: {signal.score:.2f}")
            lines.append(f"- 信号描述: {signal.message}")
            lines.append("")

        return "\n".join(lines)


# ==================== 与现有 GuardPipeline 集成 ====================


class RiskGuardAdapter:
    """
    将 RiskMonitor 集成到现有 GuardPipeline 的适配器

    将 RiskEngine 的输出转换为 GuardResult，实现无缝集成
    """

    def __init__(self, risk_engine: CompositeRiskEngine):
        self.risk_engine = risk_engine

    def check(self, ctx) -> Any:
        """
        适配 GuardPipeline 接口

        从 GuardContext 中提取信息，执行风险评估
        """
        symbol = getattr(ctx, 'symbol', None)

        # 执行风险评估
        signal, actions = self.risk_engine.evaluate(symbol=symbol)

        # 根据风险等级决定是否阻断
        if signal.level == RiskLevel.HIGH:
            return GuardResult(
                passed=False,
                guard_name="RiskMonitor",
                message=f"🔴 一级预警: {signal.message}",
                severity="error"
            )
        elif signal.level == RiskLevel.MEDIUM:
            return GuardResult(
                passed=False,
                guard_name="RiskMonitor",
                message=f"🟡 二级预警: {signal.message}",
                severity="warning"
            )
        elif signal.level == RiskLevel.LOW:
            return GuardResult(
                passed=True,
                guard_name="RiskMonitor",
                message=f"🟢 三级预警: {signal.message}",
                severity="warning"
            )

        return GuardResult(
            passed=True,
            guard_name="RiskMonitor",
            message="风险监控通过"
        )


# 延迟导入避免循环依赖
from core.guard_pipeline import GuardResult
