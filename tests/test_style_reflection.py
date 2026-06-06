"""风格化反思机制测试"""

from datetime import datetime, timedelta

import pytest

from agents.style_profile import (
    InformationSource,
    InvestmentStyle,
    detect_style_from_guru,
    get_style_profile,
)
from agents.style_reflection_engine import StyleReflectionEngine


class TestStyleProfile:
    def test_get_style_profile_long_term(self):
        profile = get_style_profile(InvestmentStyle.LONG_TERM_VALUE)
        assert profile.style == InvestmentStyle.LONG_TERM_VALUE
        assert profile.cadence.min_interval_days == 252  # 1年
        assert profile.cadence.max_interval_days == 756  # 3年
        assert profile.information.processing_depth == "deep"

    def test_get_style_profile_technical(self):
        profile = get_style_profile(InvestmentStyle.TECHNICAL_TRADING)
        assert profile.cadence.trigger_mode.value == "per_trade"
        assert profile.cadence.per_trade_enabled is True
        assert profile.cadence.min_interval_days == 1
        assert profile.information.processing_depth == "shallow"

    def test_detect_style_buffett(self):
        guru = {
            "typical_holding_period": "very_long",
            "position_style": "concentrated",
            "preferred_factors": {"factor_value": 0.5, "factor_quality": 0.3},
        }
        style = detect_style_from_guru(guru)
        assert style == InvestmentStyle.LONG_TERM_VALUE

    def test_detect_style_soros(self):
        guru = {
            "typical_holding_period": "medium",
            "position_style": "very_concentrated",
            "preferred_factors": {"factor_momentum": 0.7, "factor_value": 0.1},
        }
        style = detect_style_from_guru(guru)
        assert style == InvestmentStyle.MACRO_TREND

    def test_information_priority(self):
        profile = get_style_profile(InvestmentStyle.LONG_TERM_VALUE)
        weights = profile.information.source_weights
        assert weights[InformationSource.ANNUAL_REPORT] > weights[InformationSource.PRICE_VOLUME]
        assert weights[InformationSource.ANNUAL_REPORT] == 0.9

    def test_quant_information_priority(self):
        profile = get_style_profile(InvestmentStyle.QUANTITATIVE)
        weights = profile.information.source_weights
        assert weights[InformationSource.FACTOR_PERFORMANCE] == 0.95
        assert InformationSource.ANNUAL_REPORT not in weights  # 量化不看年报


class TestStyleReflectionEngine:
    def test_engine_init(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)
        assert engine.profile.style == InvestmentStyle.LONG_TERM_VALUE
        assert engine.last_reflection_time is None

    def test_should_reflect_first_run(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)
        should, reason = engine.should_reflect(datetime.now())
        assert should is True
        assert reason == "first_run"

    def test_should_reflect_too_soon(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)
        engine.mark_reflection_completed(datetime(2024, 1, 1))

        should, reason = engine.should_reflect(datetime(2024, 1, 2))
        assert should is False
        assert reason == "too_soon"

    def test_should_reflect_max_interval(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)
        engine.mark_reflection_completed(datetime(2024, 1, 1))

        # 超过3年应触发
        should, reason = engine.should_reflect(datetime(2027, 1, 2))
        assert should is True
        assert reason == "max_interval"

    def test_should_reflect_per_trade(self):
        engine = StyleReflectionEngine(InvestmentStyle.TECHNICAL_TRADING)
        engine.mark_reflection_completed(datetime(2024, 1, 1))

        # 技术交易每笔交易后都应触发
        should, reason = engine.should_reflect(datetime(2024, 1, 1, 10, 0), trade_executed=True)
        assert should is True
        assert reason == "per_trade"

    def test_should_reflect_drawdown(self):
        engine = StyleReflectionEngine(InvestmentStyle.QUANTITATIVE)
        engine.mark_reflection_completed(datetime(2024, 1, 1))

        # 量化回撤5%触发
        should, reason = engine.should_reflect(
            datetime(2024, 1, 10),
            current_drawdown=0.06
        )
        assert should is True
        assert "drawdown" in reason

    def test_should_reflect_event(self):
        engine = StyleReflectionEngine(InvestmentStyle.MACRO_TREND)
        engine.mark_reflection_completed(datetime(2024, 1, 1))

        # 宏观事件触发（超过最小间隔才能触发）
        should, reason = engine.should_reflect(
            datetime(2024, 4, 10),  # 超过63天
            event_type="central_bank_policy"
        )
        assert should is True
        assert "event" in reason

    def test_information_priority(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)
        priority = engine.get_information_priority()

        assert len(priority) > 0
        # 最高优先级应是年报
        assert priority[0][0] == InformationSource.ANNUAL_REPORT
        assert priority[0][1] == 0.9

    def test_information_diet_score_empty(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)
        score = engine.get_information_diet_score()
        assert score["alignment"] == 0.0
        assert score["diversity"] == 0.0

    def test_information_diet_score_aligned(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)

        # 模拟获取符合偏好的信息
        engine.log_information_access(InformationSource.ANNUAL_REPORT, 0.9)
        engine.log_information_access(InformationSource.ANNUAL_REPORT, 0.8)
        engine.log_information_access(InformationSource.INDUSTRY_CHAIN, 0.7)

        score = engine.get_information_diet_score()
        assert score["alignment"] > 0
        assert score["diversity"] > 0
        assert score["total_accesses"] == 3

    def test_evaluate_anchor_moat_score(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)

        result = engine.evaluate_anchor({"moat_score": 0.2})
        assert result["needs_adjustment"] is True
        assert len(result["adjustment_recommendations"]) > 0
        assert result["adjustment_recommendations"][0]["recommended_action"] == "reduce_position"

    def test_evaluate_anchor_roe_stable(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)

        result = engine.evaluate_anchor({"roe_stability": 0.1})
        assert result["needs_adjustment"] is True
        assert result["primary_status"]["roe_stability"]["level"] == "warning"

    def test_evaluate_anchor_win_rate_low(self):
        engine = StyleReflectionEngine(InvestmentStyle.TECHNICAL_TRADING)

        result = engine.evaluate_anchor({"win_rate": 0.3})
        assert result["needs_adjustment"] is True
        assert result["primary_status"]["win_rate"].get("recommendation") == "pause_trading"

    def test_evaluate_anchor_factor_decay(self):
        engine = StyleReflectionEngine(InvestmentStyle.QUANTITATIVE)

        result = engine.evaluate_anchor({"factor_decay_speed": 0.03})
        assert result["needs_adjustment"] is True
        assert result["primary_status"]["factor_decay_speed"].get("recommendation") == "rebalance_factors"

    def test_evaluate_anchor_normal(self):
        engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)

        result = engine.evaluate_anchor({"moat_score": 0.8})
        assert result["needs_adjustment"] is False
        assert result["primary_status"]["moat_score"]["level"] == "normal"

    def test_reflection_summary(self):
        engine = StyleReflectionEngine(InvestmentStyle.MACRO_TREND)
        engine.mark_reflection_completed(datetime(2024, 1, 1))

        summary = engine.get_reflection_summary()
        assert summary["style"] == "macro_trend"
        assert summary["reflection_count"] == 1
        assert summary["last_reflection"] is not None
        assert len(summary["top_information_sources"]) > 0

    def test_from_guru_buffett(self):
        guru = {
            "typical_holding_period": "very_long",
            "position_style": "concentrated",
            "preferred_factors": {"factor_value": 0.5},
        }
        engine = StyleReflectionEngine.from_guru(guru)
        assert engine.profile.style == InvestmentStyle.LONG_TERM_VALUE
        assert engine.cadence.min_interval_days == 252

    def test_from_guru_soros(self):
        guru = {
            "typical_holding_period": "medium",
            "position_style": "very_concentrated",
            "preferred_factors": {"factor_momentum": 0.7},
        }
        engine = StyleReflectionEngine.from_guru(guru)
        assert engine.profile.style == InvestmentStyle.MACRO_TREND
        assert engine.cadence.min_interval_days == 63

    def test_cadence_comparison(self):
        """验证不同风格的反思节奏差异"""
        long_term = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)
        technical = StyleReflectionEngine(InvestmentStyle.TECHNICAL_TRADING)
        quant = StyleReflectionEngine(InvestmentStyle.QUANTITATIVE)

        # 长期价值反思最慢
        assert long_term.cadence.min_interval_days > quant.cadence.min_interval_days
        # 技术交易反思最快
        assert technical.cadence.min_interval_days < quant.cadence.min_interval_days
        # 技术交易每笔交易后反思
        assert technical.cadence.per_trade_enabled is True
        assert long_term.cadence.per_trade_enabled is False

    def test_anchor_comparison(self):
        """验证不同风格的锚定对象差异"""
        long_term = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)
        macro = StyleReflectionEngine(InvestmentStyle.MACRO_TREND)
        technical = StyleReflectionEngine(InvestmentStyle.TECHNICAL_TRADING)

        # 长期价值锚定护城河
        assert "moat_score" in long_term.anchoring.primary_metrics
        # 宏观趋势锚定趋势强度
        assert "trend_strength" in macro.anchoring.primary_metrics
        # 技术交易锚定胜率
        assert "win_rate" in technical.anchoring.primary_metrics
