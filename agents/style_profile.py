"""Agent风格画像与差异化反思机制

为不同投资风格的Agent配置差异化的：
1. 反思节奏 (Reflection Cadence)
2. 信息偏好 (Information Preference)
3. 锚定对象 (Anchoring Target)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd


class InvestmentStyle(str, Enum):
    """投资风格"""
    LONG_TERM_VALUE = "long_term_value"      # 长期价值：巴菲特型
    MACRO_TREND = "macro_trend"              # 宏观趋势：索罗斯型
    FUNDAMENTAL = "fundamental"              # 基本面：财务分析师型
    TECHNICAL_TRADING = "technical_trading"  # 技术交易：日内/波段
    QUANTITATIVE = "quantitative"            # 量化：统计套利/因子
    BALANCED = "balanced"                    # 平衡型


class ReflectionTrigger(str, Enum):
    """反思触发机制"""
    SCHEDULED = "scheduled"          # 定期触发
    PER_TRADE = "per_trade"          # 每笔交易后
    EVENT_DRIVEN = "event_driven"    # 事件驱动
    PERFORMANCE = "performance"      # 绩效阈值
    HYBRID = "hybrid"                # 混合


class InformationSource(str, Enum):
    """信息源类型"""
    ANNUAL_REPORT = "annual_report"          # 年报
    QUARTERLY_EARNINGS = "quarterly_earnings"  # 季报
    MACRO_DATA = "macro_data"                # 宏观数据
    PRICE_VOLUME = "price_volume"            # 价量数据
    FACTOR_PERFORMANCE = "factor_performance"  # 因子绩效
    NEWS_SENTIMENT = "news_sentiment"        # 新闻情绪
    INDUSTRY_CHAIN = "industry_chain"        # 产业链
    POLICY_REGULATION = "policy_regulation"  # 政策法规


@dataclass
class ReflectionCadence:
    """反思节奏配置"""
    trigger_mode: ReflectionTrigger = ReflectionTrigger.SCHEDULED
    min_interval_days: int = 20          # 最小反思间隔（日）
    max_interval_days: int = 60          # 最大反思间隔（日）
    per_trade_enabled: bool = False      # 是否每笔交易后反思
    event_types: list[str] = field(default_factory=list)  # 触发反思的事件类型
    performance_threshold: float | None = None  # 绩效阈值触发（如回撤>5%）


@dataclass
class InformationPreference:
    """信息偏好配置"""
    # 信息源优先级 (0-1, 越高越优先)
    source_weights: dict[InformationSource, float] = field(default_factory=dict)
    # 信息处理深度 (shallow/medium/deep)
    processing_depth: Literal["shallow", "medium", "deep"] = "medium"
    # 信息时效性要求 (days)
    information_freshness_days: int = 7
    # 噪声过滤阈值 (忽略低于此权重的信息)
    noise_threshold: float = 0.1


@dataclass
class AnchoringTarget:
    """反思锚定对象配置"""
    # 核心锚定指标
    primary_metrics: list[str] = field(default_factory=list)
    # 辅助锚定指标
    secondary_metrics: list[str] = field(default_factory=list)
    # 锚定计算窗口 (days)
    anchoring_window_days: int = 60
    # 锚定评估函数
    evaluation_fn: str = "default"
    # 调整目标参数
    adjustment_targets: list[str] = field(default_factory=list)


@dataclass
class StyleProfile:
    """Agent风格画像"""
    style: InvestmentStyle
    name: str
    description: str
    # 反思节奏
    cadence: ReflectionCadence
    # 信息偏好
    information: InformationPreference
    # 锚定对象
    anchoring: AnchoringTarget
    # 风格特有参数
    custom_params: dict[str, Any] = field(default_factory=dict)


# ============================================================
# 预定义风格画像
# ============================================================

STYLE_PROFILES: dict[InvestmentStyle, StyleProfile] = {
    InvestmentStyle.LONG_TERM_VALUE: StyleProfile(
        style=InvestmentStyle.LONG_TERM_VALUE,
        name="长期价值投资",
        description="以合理价格买入具有持久竞争优势的伟大企业，长期持有",
        cadence=ReflectionCadence(
            trigger_mode=ReflectionTrigger.HYBRID,
            min_interval_days=252,      # 至少1年
            max_interval_days=756,      # 最多3年
            event_types=["annual_report", "management_change", "industry_disruption"],
            performance_threshold=0.20,  # 回撤20%才触发
        ),
        information=InformationPreference(
            source_weights={
                InformationSource.ANNUAL_REPORT: 0.9,
                InformationSource.INDUSTRY_CHAIN: 0.7,
                InformationSource.POLICY_REGULATION: 0.5,
                InformationSource.QUARTERLY_EARNINGS: 0.6,
                InformationSource.PRICE_VOLUME: 0.1,
                InformationSource.NEWS_SENTIMENT: 0.05,
            },
            processing_depth="deep",
            information_freshness_days=90,
            noise_threshold=0.2,
        ),
        anchoring=AnchoringTarget(
            primary_metrics=["moat_score", "roe_stability", "valuation_deviation"],
            secondary_metrics=["market_share_trend", "management_quality"],
            anchoring_window_days=756,   # 3年窗口
            evaluation_fn="moat_based",
            adjustment_targets=["belief_strength", "position_max_weight"],
        ),
        custom_params={
            "moat_decay_threshold": 0.3,    # 护城河评分下降30%触发深度反思
            "roe_min_sustainable": 0.15,    # ROE持续低于15%触发反思
            "holding_period_years": 10,     # 预期持有10年
        },
    ),

    InvestmentStyle.MACRO_TREND: StyleProfile(
        style=InvestmentStyle.MACRO_TREND,
        name="宏观趋势交易",
        description="基于宏观经济趋势进行大额方向性押注，利用反身性在趋势中获利",
        cadence=ReflectionCadence(
            trigger_mode=ReflectionTrigger.HYBRID,
            min_interval_days=63,       # 1季度
            max_interval_days=252,      # 1年
            event_types=["central_bank_policy", "geopolitical_event", "currency_crisis"],
            performance_threshold=0.10,  # 回撤10%触发
        ),
        information=InformationPreference(
            source_weights={
                InformationSource.MACRO_DATA: 0.95,
                InformationSource.POLICY_REGULATION: 0.8,
                InformationSource.INDUSTRY_CHAIN: 0.4,
                InformationSource.NEWS_SENTIMENT: 0.5,
                InformationSource.PRICE_VOLUME: 0.3,
                InformationSource.QUARTERLY_EARNINGS: 0.2,
            },
            processing_depth="deep",
            information_freshness_days=7,
            noise_threshold=0.15,
        ),
        anchoring=AnchoringTarget(
            primary_metrics=["macro_assumption_validity", "trend_strength", "reflexivity_feedback"],
            secondary_metrics=["position_flow", "sentiment_extreme"],
            anchoring_window_days=126,   # 半年窗口
            evaluation_fn="macro_based",
            adjustment_targets=["position_direction", "leverage_level", "hedge_ratio"],
        ),
        custom_params={
            "assumption_falsification_threshold": 0.4,
            "trend_reversal_confirmation": 2,  # 需要2个独立信号确认趋势反转
            "max_position_concentration": 0.5,  # 单方向最大50%
        },
    ),

    InvestmentStyle.FUNDAMENTAL: StyleProfile(
        style=InvestmentStyle.FUNDAMENTAL,
        name="基本面分析",
        description="基于财务数据和行业研究，通过DCF估值寻找安全边际",
        cadence=ReflectionCadence(
            trigger_mode=ReflectionTrigger.HYBRID,
            min_interval_days=63,       # 1季度
            max_interval_days=126,      # 半年
            event_types=["earnings_release", "industry_data", "guidance_change"],
            performance_threshold=0.15,
        ),
        information=InformationPreference(
            source_weights={
                InformationSource.QUARTERLY_EARNINGS: 0.9,
                InformationSource.INDUSTRY_CHAIN: 0.8,
                InformationSource.ANNUAL_REPORT: 0.7,
                InformationSource.POLICY_REGULATION: 0.4,
                InformationSource.PRICE_VOLUME: 0.2,
                InformationSource.NEWS_SENTIMENT: 0.15,
            },
            processing_depth="deep",
            information_freshness_days=30,
            noise_threshold=0.15,
        ),
        anchoring=AnchoringTarget(
            primary_metrics=["earnings_forecast_accuracy", "valuation_model_error", "margin_of_safety"],
            secondary_metrics=["consensus_deviation", "earnings_surprise"],
            anchoring_window_days=252,
            evaluation_fn="fundamental_based",
            adjustment_targets=["forecast_model_params", "margin_of_safety_threshold"],
        ),
        custom_params={
            "forecast_horizon_quarters": 8,
            "dcf_discount_rate_range": (0.08, 0.12),
            "margin_of_safety_min": 0.3,
        },
    ),

    InvestmentStyle.TECHNICAL_TRADING: StyleProfile(
        style=InvestmentStyle.TECHNICAL_TRADING,
        name="技术交易",
        description="基于价格形态、动量和成交量进行短期交易",
        cadence=ReflectionCadence(
            trigger_mode=ReflectionTrigger.PER_TRADE,
            min_interval_days=1,
            max_interval_days=5,
            per_trade_enabled=True,
            event_types=["stop_loss_triggered", "breakout_failure", "volume_spike"],
            performance_threshold=0.03,  # 3%回撤即触发
        ),
        information=InformationPreference(
            source_weights={
                InformationSource.PRICE_VOLUME: 0.95,
                InformationSource.NEWS_SENTIMENT: 0.3,
                InformationSource.MACRO_DATA: 0.1,
                InformationSource.QUARTERLY_EARNINGS: 0.05,
                InformationSource.ANNUAL_REPORT: 0.0,
            },
            processing_depth="shallow",
            information_freshness_days=1,
            noise_threshold=0.05,
        ),
        anchoring=AnchoringTarget(
            primary_metrics=["win_rate", "profit_loss_ratio", "max_consecutive_losses", "slippage_cost"],
            secondary_metrics=["avg_holding_period", "time_in_market"],
            anchoring_window_days=20,
            evaluation_fn="technical_based",
            adjustment_targets=["stop_loss_level", "position_size", "entry_timing"],
        ),
        custom_params={
            "min_win_rate": 0.45,
            "min_profit_loss_ratio": 1.5,
            "max_consecutive_losses": 3,
            "slippage_tolerance_bps": 10,
        },
    ),

    InvestmentStyle.QUANTITATIVE: StyleProfile(
        style=InvestmentStyle.QUANTITATIVE,
        name="量化策略",
        description="基于统计模型和因子进行系统化交易",
        cadence=ReflectionCadence(
            trigger_mode=ReflectionTrigger.HYBRID,
            min_interval_days=5,        # 1周
            max_interval_days=21,       # 1月
            event_types=["factor_ic_decay", "regime_change", "drawdown_limit"],
            performance_threshold=0.05,  # 5%回撤触发
        ),
        information=InformationPreference(
            source_weights={
                InformationSource.FACTOR_PERFORMANCE: 0.95,
                InformationSource.PRICE_VOLUME: 0.4,
                InformationSource.MACRO_DATA: 0.3,
                InformationSource.QUARTERLY_EARNINGS: 0.2,
                InformationSource.NEWS_SENTIMENT: 0.1,
            },
            processing_depth="medium",
            information_freshness_days=3,
            noise_threshold=0.08,
        ),
        anchoring=AnchoringTarget(
            primary_metrics=["factor_decay_speed", "overfitting_indicator", "out_of_sample_ic"],
            secondary_metrics=["turnover_cost", "capacity_utilization"],
            anchoring_window_days=63,
            evaluation_fn="quant_based",
            adjustment_targets=["factor_weights", "universe_constraints", "rebalance_freq"],
        ),
        custom_params={
            "ic_decay_threshold": 0.02,
            "max_overfitting_ratio": 2.0,
            "min_oos_ic": 0.03,
            "turnover_limit": 0.3,
        },
    ),

    InvestmentStyle.BALANCED: StyleProfile(
        style=InvestmentStyle.BALANCED,
        name="平衡型",
        description="兼顾长期价值与短期机会，多维度信息融合",
        cadence=ReflectionCadence(
            trigger_mode=ReflectionTrigger.SCHEDULED,
            min_interval_days=21,
            max_interval_days=63,
            event_types=["significant_drawdown", "major_event"],
            performance_threshold=0.10,
        ),
        information=InformationPreference(
            source_weights={
                InformationSource.QUARTERLY_EARNINGS: 0.6,
                InformationSource.PRICE_VOLUME: 0.5,
                InformationSource.MACRO_DATA: 0.5,
                InformationSource.INDUSTRY_CHAIN: 0.5,
                InformationSource.NEWS_SENTIMENT: 0.3,
            },
            processing_depth="medium",
            information_freshness_days=14,
            noise_threshold=0.12,
        ),
        anchoring=AnchoringTarget(
            primary_metrics=["composite_score", "risk_adjusted_return", "style_consistency"],
            secondary_metrics=["information_ratio", "tracking_error"],
            anchoring_window_days=126,
            evaluation_fn="balanced_based",
            adjustment_targets=["style_tilt", "risk_budget"],
        ),
        custom_params={
            "rebalance_threshold": 0.05,
            "style_drift_limit": 0.2,
        },
    ),
}


def get_style_profile(style: InvestmentStyle | str) -> StyleProfile:
    """获取风格画像"""
    if isinstance(style, str):
        style = InvestmentStyle(style)
    return STYLE_PROFILES.get(style, STYLE_PROFILES[InvestmentStyle.BALANCED])


def detect_style_from_guru(guru_data: dict) -> InvestmentStyle:
    """从Guru配置自动检测投资风格"""
    holding_period = guru_data.get("typical_holding_period", "medium")
    position_style = guru_data.get("position_style", "moderate")
    preferred_factors = guru_data.get("preferred_factors", {})

    # 根据持有期判断
    if holding_period in ["very_long", "long"]:
        return InvestmentStyle.LONG_TERM_VALUE

    # 根据因子偏好判断
    momentum_weight = preferred_factors.get("factor_momentum", 0)
    value_weight = preferred_factors.get("factor_value", 0)

    if momentum_weight > 0.5 and position_style in ["very_concentrated", "concentrated"]:
        return InvestmentStyle.MACRO_TREND

    if value_weight > 0.4:
        return InvestmentStyle.FUNDAMENTAL

    return InvestmentStyle.BALANCED
