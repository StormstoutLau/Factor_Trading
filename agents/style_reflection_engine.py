"""风格化反思引擎

将 StyleProfile 与现有反思机制集成，实现：
1. 风格感知的反思触发
2. 风格化的锚定对象评估
3. 差异化的信息获取优先级
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from agents.style_profile import (
    AnchoringTarget,
    InformationPreference,
    InformationSource,
    InvestmentStyle,
    ReflectionCadence,
    ReflectionTrigger,
    StyleProfile,
    detect_style_from_guru,
    get_style_profile,
)

logger = logging.getLogger(__name__)


class StyleReflectionEngine:
    """风格化反思引擎

    为每个Agent根据其投资风格定制反思行为：
    - 何时反思（触发机制）
    - 反思什么（锚定对象）
    - 用什么信息（信息偏好）
    """

    def __init__(self, profile: StyleProfile | InvestmentStyle | str | None = None):
        if profile is None:
            profile = get_style_profile(InvestmentStyle.BALANCED)
        elif isinstance(profile, str):
            profile = get_style_profile(profile)
        elif isinstance(profile, InvestmentStyle):
            profile = get_style_profile(profile)

        self.profile = profile
        self.cadence: ReflectionCadence = profile.cadence
        self.information: InformationPreference = profile.information
        self.anchoring: AnchoringTarget = profile.anchoring

        # 状态追踪
        self.last_reflection_time: datetime | None = None
        self.reflection_count: int = 0
        self.trade_count_since_reflection: int = 0
        self.performance_since_reflection: float = 0.0

        # 信息获取记录
        self.information_access_log: list[tuple[datetime, InformationSource, float]] = []

    @classmethod
    def from_guru(cls, guru_data: dict) -> "StyleReflectionEngine":
        """从Guru配置创建风格化反思引擎"""
        style = detect_style_from_guru(guru_data)
        return cls(style)

    def should_reflect(
        self,
        current_time: datetime,
        trade_executed: bool = False,
        current_drawdown: float = 0.0,
        event_type: str | None = None,
    ) -> tuple[bool, str]:
        """判断是否应该触发反思

        Returns:
            (should_reflect, trigger_reason)
        """
        # 1. 每笔交易后触发
        if self.cadence.per_trade_enabled and trade_executed:
            self.trade_count_since_reflection += 1
            return True, "per_trade"

        # 2. 首次运行
        if self.last_reflection_time is None:
            return True, "first_run"

        elapsed_days = (current_time - self.last_reflection_time).days

        # 3. 最小间隔检查
        if elapsed_days < self.cadence.min_interval_days:
            return False, "too_soon"

        # 4. 最大间隔强制触发
        if elapsed_days >= self.cadence.max_interval_days:
            return True, "max_interval"

        # 5. 绩效阈值触发
        if self.cadence.performance_threshold is not None:
            if current_drawdown >= self.cadence.performance_threshold:
                return True, f"drawdown_{current_drawdown:.2%}"

        # 6. 事件触发
        if event_type and event_type in self.cadence.event_types:
            return True, f"event_{event_type}"

        # 7. 定期触发（达到最小间隔）
        if self.cadence.trigger_mode in (ReflectionTrigger.SCHEDULED, ReflectionTrigger.HYBRID):
            if elapsed_days >= self.cadence.min_interval_days:
                return True, "scheduled"

        return False, "no_trigger"

    def get_information_priority(self, available_sources: list[InformationSource] | None = None) -> list[tuple[InformationSource, float]]:
        """获取信息源优先级排序

        Args:
            available_sources: 可用的信息源列表，None则返回所有配置中的源

        Returns:
            [(信息源, 权重), ...] 按权重降序排列
        """
        weights = self.information.source_weights

        if available_sources is None:
            sources = list(weights.keys())
        else:
            sources = [s for s in available_sources if s in weights]

        # 过滤噪声
        filtered = [(s, w) for s, w in weights.items() if s in sources and w >= self.information.noise_threshold]

        # 按权重降序
        return sorted(filtered, key=lambda x: x[1], reverse=True)

    def log_information_access(self, source: InformationSource, relevance_score: float, timestamp: datetime | None = None) -> None:
        """记录信息获取"""
        if timestamp is None:
            timestamp = datetime.now()
        self.information_access_log.append((timestamp, source, relevance_score))

    def get_information_diet_score(self) -> dict[str, float]:
        """获取信息饮食结构评分

        分析Agent实际获取的信息是否符合其风格偏好
        """
        if not self.information_access_log:
            return {"alignment": 0.0, "diversity": 0.0}

        # 统计实际获取的信息源分布
        source_counts: dict[InformationSource, int] = {}
        for _, source, _ in self.information_access_log:
            source_counts[source] = source_counts.get(source, 0) + 1

        total = sum(source_counts.values())
        if total == 0:
            return {"alignment": 0.0, "diversity": 0.0}

        # 计算与偏好的对齐度
        alignment = 0.0
        for source, count in source_counts.items():
            actual_ratio = count / total
            preferred_ratio = self.information.source_weights.get(source, 0)
            alignment += min(actual_ratio, preferred_ratio)

        # 计算多样性（实际使用的信息源数量 / 偏好的信息源数量）
        preferred_sources = sum(1 for w in self.information.source_weights.values() if w >= self.information.noise_threshold)
        actual_sources = len(source_counts)
        diversity = min(actual_sources / max(preferred_sources, 1), 1.0)

        return {
            "alignment": alignment,
            "diversity": diversity,
            "total_accesses": total,
        }

    def evaluate_anchor(self, metric_values: dict[str, float]) -> dict[str, Any]:
        """评估锚定对象

        Args:
            metric_values: {指标名: 当前值}

        Returns:
            评估结果，包含是否需要调整及调整建议
        """
        primary = self.anchoring.primary_metrics
        secondary = self.anchoring.secondary_metrics

        result = {
            "style": self.profile.style.value,
            "primary_status": {},
            "secondary_status": {},
            "needs_adjustment": False,
            "adjustment_recommendations": [],
        }

        # 评估核心指标
        for metric in primary:
            value = metric_values.get(metric)
            if value is None:
                continue

            status = self._evaluate_metric(metric, value)
            result["primary_status"][metric] = status

            if status.get("alert", False):
                result["needs_adjustment"] = True
                result["adjustment_recommendations"].append({
                    "target": metric,
                    "current_value": value,
                    "recommended_action": status.get("recommendation", "review"),
                })

        # 评估辅助指标
        for metric in secondary:
            value = metric_values.get(metric)
            if value is None:
                continue
            result["secondary_status"][metric] = self._evaluate_metric(metric, value)

        return result

    def _evaluate_metric(self, metric: str, value: float) -> dict[str, Any]:
        """评估单个指标"""
        # 根据风格类型和指标名进行差异化评估
        style = self.profile.style

        # 长期价值型：护城河评分
        if style == InvestmentStyle.LONG_TERM_VALUE and metric == "moat_score":
            threshold = self.profile.custom_params.get("moat_decay_threshold", 0.3)
            if value < threshold:
                return {"alert": True, "level": "critical", "recommendation": "reduce_position", "message": f"护城河评分({value:.2f})低于阈值({threshold})"}
            return {"alert": False, "level": "normal"}

        # 长期价值型：ROE稳定性
        if style == InvestmentStyle.LONG_TERM_VALUE and metric == "roe_stability":
            min_roe = self.profile.custom_params.get("roe_min_sustainable", 0.15)
            if value < min_roe:
                return {"alert": True, "level": "warning", "recommendation": "review_holdings", "message": f"ROE({value:.2%})低于可持续水平({min_roe:.0%})"}
            return {"alert": False, "level": "normal"}

        # 宏观趋势型：趋势强度
        if style == InvestmentStyle.MACRO_TREND and metric == "trend_strength":
            if value < 0.2:
                return {"alert": True, "level": "warning", "recommendation": "reduce_exposure", "message": f"趋势强度({value:.2f})显著减弱"}
            return {"alert": False, "level": "normal"}

        # 技术交易型：胜率
        if style == InvestmentStyle.TECHNICAL_TRADING and metric == "win_rate":
            min_wr = self.profile.custom_params.get("min_win_rate", 0.45)
            if value < min_wr:
                return {"alert": True, "level": "critical", "recommendation": "pause_trading", "message": f"胜率({value:.1%})低于最低要求({min_wr:.0%})"}
            return {"alert": False, "level": "normal"}

        # 量化型：因子衰减
        if style == InvestmentStyle.QUANTITATIVE and metric == "factor_decay_speed":
            threshold = self.profile.custom_params.get("ic_decay_threshold", 0.02)
            if value > threshold:
                return {"alert": True, "level": "warning", "recommendation": "rebalance_factors", "message": f"因子衰减速度({value:.4f})超过阈值({threshold})"}
            return {"alert": False, "level": "normal"}

        # 通用评估
        if value < 0:
            return {"alert": True, "level": "warning", "recommendation": "review", "message": f"{metric}为负值({value:.4f})"}

        return {"alert": False, "level": "normal"}

    def get_reflection_summary(self) -> dict[str, Any]:
        """获取反思引擎状态摘要"""
        info_diet = self.get_information_diet_score()

        return {
            "style": self.profile.style.value,
            "style_name": self.profile.name,
            "reflection_count": self.reflection_count,
            "last_reflection": self.last_reflection_time.isoformat() if self.last_reflection_time else None,
            "cadence": {
                "trigger_mode": self.cadence.trigger_mode.value,
                "min_interval_days": self.cadence.min_interval_days,
                "max_interval_days": self.cadence.max_interval_days,
            },
            "information_diet": info_diet,
            "top_information_sources": [
                {"source": s.value, "weight": w}
                for s, w in self.get_information_priority()[:3]
            ],
            "primary_anchors": self.anchoring.primary_metrics,
            "adjustment_targets": self.anchoring.adjustment_targets,
        }

    def mark_reflection_completed(self, timestamp: datetime | None = None) -> None:
        """标记反思完成"""
        if timestamp is None:
            timestamp = datetime.now()
        self.last_reflection_time = timestamp
        self.reflection_count += 1
        self.trade_count_since_reflection = 0
        self.performance_since_reflection = 0.0
