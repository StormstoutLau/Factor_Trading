"""P-027 静默失败治理第三批（core 外 22 处 except 分级显形）测试。

对应 docs/IMPL_p027_silent_exception_governance_phase3.md §5（T1-T12）。
全部使用 monkeypatch（禁 unittest.mock，DESIGN §6 / E7）。
"""

from __future__ import annotations

import json
import logging
import sys
import types

import numpy as np
import pandas as pd
import pytest

import agents.research_team_v2 as research_team_module
from agents.agent_framework import ResearchTeamAgent
from agents.assumption_monitor import ReturnDistributionMonitor
from agents.auto_parameter_optimizer import AutoOptimizedFundManager
from agents.guru_agent_v2 import GuruAgentV2, GuruDataLoader
from agents.multi_strategy_engine import StrategyConfig, StrategyEngine
from agents.research_team_v2 import FundManager, ResearchView, ViewDirection
from core.config import BacktestConfig
from core.portfolio import EqualWeightOptimizer
from filter.custom import ConditionalFilter, CustomFunctionFilter, DynamicFilter, ExpressionFilter
from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig
from strategy_evaluation.stats import FactorStatsCalculator

STOCKS = ["A", "B", "C"]
DATES = pd.bdate_range("2024-01-02", periods=3)


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame(rng.normal(size=(len(DATES), len(STOCKS))), index=DATES, columns=STOCKS)


def _boom(*args, **kwargs):
    raise RuntimeError("boom")


def _all_true(data: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(True, index=data.index, columns=data.columns)


class _BrokenRole:
    """分析即抛错的角色（内层 handler 注入点）。"""

    name = "坏角色"
    weight = 1.0
    is_active = True

    def analyze(self, date, stock, data):
        raise RuntimeError("boom")

    def get_views_summary(self):
        return {"role": self.name, "weight": self.weight, "views": 0}


class _GoodRole:
    """正常返回观点的角色。"""

    name = "好角色"
    weight = 1.0
    is_active = True

    def analyze(self, date, stock, data):
        return ResearchView(
            role=self.name, stock=stock, direction=ViewDirection.BUY, confidence=0.8
        )

    def get_views_summary(self):
        return {"role": self.name, "weight": self.weight, "views": 1}


class _FakeDM:
    """仅提供 StrategyEngine 构造与日处理所需的最小数据面。"""

    def __init__(self, n_days: int = 1):
        self.trade_dates = pd.bdate_range("2024-01-02", periods=n_days)
        self.stock_codes = STOCKS
        self.n_stocks = len(STOCKS)
        self.returns = pd.DataFrame(0.0, index=self.trade_dates, columns=STOCKS)

    def get_adj_price(self, field: str, adjustment_type: str) -> pd.DataFrame:
        return pd.DataFrame(10.0, index=self.trade_dates, columns=STOCKS)


def _make_engine(signal: pd.DataFrame | None = None) -> StrategyEngine:
    strategy_cfg = StrategyConfig(name="long", direction="long", target_count=2)
    base_cfg = BacktestConfig(enable_pending_orders=False)
    return StrategyEngine(
        strategy_cfg, base_cfg, _FakeDM(), None, _frame() if signal is None else signal
    )


# --------------------------------------------------------------- T1
@pytest.mark.parametrize(
    "factory,key,universe",
    [
        (lambda: CustomFunctionFilter(_boom), "custom_function", False),
        (lambda: ExpressionFilter("1/0"), "expression", False),
        (lambda: DynamicFilter({}, _boom), "dynamic", False),
        (
            lambda: ConditionalFilter(
                _boom, CustomFunctionFilter(_all_true), CustomFunctionFilter(_all_true)
            ),
            "conditional",
            False,
        ),
        (
            lambda: UniverseFilter(
                object(),
                UniverseFilterConfig(
                    enable_custom_filters=True,
                    custom_filter_configs={"bad": {"type": "function", "function": _boom}},
                ),
            ),
            "custom_mask_build:bad",
            True,
        ),
    ],
)
def test_filter_failopen_counts(factory, key, universe):
    """D1：5 处 filter 降级路径计数 +1，fail-open 返回不变。"""
    filt = factory()
    if universe:
        filt._build_custom_masks()
        assert filt.get_failure_stats() == {key: 1}
        assert "bad" not in filt._custom_masks
    else:
        mask = filt.build_mask(_frame())
        assert mask.to_numpy().all()
        assert filt.get_failure_stats() == {key: 1}


# --------------------------------------------------------------- T2
def test_rotation_analyzer_init_failure(monkeypatch):
    """D2：行业轮动分析器初始化失败 → None + 计数 1（不中断）。"""
    monkeypatch.setitem(sys.modules, "research_team_v2", research_team_module)

    class _BoomAnalyzer:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("boom")

    fake_module = types.ModuleType("industry_rotation_v2")
    fake_module.IndustryRotationAnalyzer = _BoomAnalyzer
    monkeypatch.setitem(sys.modules, "industry_rotation_v2", fake_module)

    agent = ResearchTeamAgent()
    agent._research_team_available = True
    agent._price_data = _frame()
    agent._industry_data = pd.DataFrame("银行", index=DATES, columns=STOCKS)
    agent._init_research_team(None)

    assert agent.rotation_analyzer is None
    assert agent.get_failure_stats() == {"rotation_analyzer_init": 1}


# --------------------------------------------------------------- T3
def test_research_team_analysis_level(monkeypatch, caplog):
    """D2 / D7：单股分析失败 → WARNING（非 DEBUG）+ 文案逐字 + 计数 1 + 跳过。"""
    agent = ResearchTeamAgent()
    agent._research_team_available = True
    agent._price_data = pd.DataFrame(10.0, index=DATES, columns=STOCKS)
    fund_manager = FundManager()
    monkeypatch.setattr(fund_manager, "make_decision", _boom)
    agent.fund_manager = fund_manager

    composite = pd.Series({"A": 1.0})
    tradable_mask = pd.Series(True, index=["A"])

    caplog.set_level(logging.DEBUG, logger="agents.agent_framework")
    signals = agent.generate_signals(DATES[0], composite, tradable_mask, {})

    assert signals == []
    assert agent.get_failure_stats() == {"research_team_analysis": 1}
    records = [r for r in caplog.records if "投研团队分析" in r.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert "失败" in records[0].getMessage()


# --------------------------------------------------------------- T4
@pytest.mark.parametrize("case", ["daily_process", "directional_optimize", "neutral_optimize"])
def test_strategy_engine_failure_counts(monkeypatch, case):
    """D2 / D6：日处理与两类再平衡失败各自计数 1；run() 出口含 failure_counts。"""
    engine = _make_engine()
    stocks = pd.Series({"A": 1.0, "B": 0.5})

    if case == "daily_process":
        monkeypatch.setattr(engine, "_process_trading_day", _boom)
        result = engine.run()
        assert isinstance(result["failure_counts"], dict)
        assert result["failure_counts"] == {"daily_process": 1}
    elif case == "directional_optimize":
        monkeypatch.setattr(engine.optimizer, "optimize", _boom)
        engine._execute_directional_rebalance(DATES[0], 0, stocks)
        assert engine.get_failure_stats() == {"directional_optimize": 1}
    else:
        monkeypatch.setattr(EqualWeightOptimizer, "optimize", _boom)
        engine._execute_neutral_rebalance(DATES[0], 0, stocks)
        assert engine.get_failure_stats() == {"neutral_optimize": 1}


# --------------------------------------------------------------- T5
def test_fund_manager_role_analysis():
    """D2：单角色分析失败 → 计数 1，其余角色正常投票，决策仍产出。"""
    fund_manager = FundManager()
    fund_manager.roles["坏角色"] = _BrokenRole()
    fund_manager.roles["好角色"] = _GoodRole()

    decision = fund_manager.make_decision(DATES[0], "A", {})

    assert fund_manager.get_failure_stats() == {"role_analysis": 1}
    assert decision.stock == "A"
    assert decision.final_direction == ViewDirection.BUY
    assert list(decision.votes) == ["好角色"]


# --------------------------------------------------------------- T6
def test_optimized_fund_manager_decision():
    """D2 / D4：优化适配器决策路径失败 → 计数 1 且报告出口可见。"""
    fund_manager = FundManager()
    fund_manager.roles["坏角色"] = _BrokenRole()
    fund_manager.roles["好角色"] = _GoodRole()
    manager = AutoOptimizedFundManager(
        fund_manager,
        enable_pbt=False,
        enable_regularization=False,
        enable_walkforward=False,
        enable_monitoring=False,
    )

    decision = manager.make_decision_with_regularization(DATES[0], "A", {})
    report = manager.get_optimization_report()

    assert decision.stock == "A"
    assert report["failure_counts"] == {"decision_making": 1}


# --------------------------------------------------------------- T7
def test_guru_loader_load_failure(tmp_path):
    """D2 / A1：坏 JSON → 计数 1，加载器仍可用（get 返回 None，不抛）。"""
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")

    loader = GuruDataLoader(tmp_path)

    assert loader.get("bad") is None
    assert loader.get_failure_stats() == {"guru_load": 1}


# --------------------------------------------------------------- T8
def test_guru_create_all_failures(tmp_path, monkeypatch):
    """D2 / D6：工厂创建失败 → 类级计数 1；重复调用不累加（入口清零）。"""
    (tmp_path / "one.json").write_text(json.dumps({"name": "one"}), encoding="utf-8")
    monkeypatch.setattr(GuruAgentV2, "__init__", _boom)

    assert GuruAgentV2.create_all_gurus(tmp_path) == []
    assert GuruAgentV2.get_creation_failure_stats() == {"guru_create": 1}

    assert GuruAgentV2.create_all_gurus(tmp_path) == []
    assert GuruAgentV2.get_creation_failure_stats() == {"guru_create": 1}


# --------------------------------------------------------------- T11
@pytest.mark.parametrize(
    "factory,nested",
    [
        (lambda: ResearchTeamAgent().get_performance_summary(), True),
        (lambda: _make_engine(signal=pd.DataFrame()).run(), True),
        (lambda: FundManager().get_team_report(), True),
        (
            lambda: AutoOptimizedFundManager(
                FundManager(),
                enable_pbt=False,
                enable_regularization=False,
                enable_walkforward=False,
                enable_monitoring=False,
            ).get_optimization_report(),
            True,
        ),
        (lambda: FactorStatsCalculator(_frame(), _frame()).calculate_all_stats(), True),
        (lambda: GuruDataLoader("__p027_no_such_dir__").get_failure_stats(), False),
    ],
)
def test_structured_exits(factory, nested):
    """D4 / I5：6 个结构化出口均含 failure_counts 且为 dict。"""
    payload = factory()
    stats = payload["failure_counts"] if nested else payload
    assert isinstance(stats, dict)


# --------------------------------------------------------------- T12
def test_return_semantics_unchanged(monkeypatch):
    """I3 / R-P027-5：内层与外层计数互不重复，失败路径返回值语义不变。"""
    agent = ResearchTeamAgent()
    agent._research_team_available = True
    agent._price_data = pd.DataFrame(10.0, index=DATES, columns=STOCKS)

    fund_manager = FundManager()
    fund_manager.roles["坏角色"] = _BrokenRole()
    fund_manager.roles["好角色"] = _GoodRole()

    original_make_decision = FundManager.make_decision

    def flaky_make_decision(self, date, stock, data):
        if stock == "B":
            raise RuntimeError("outer boom")
        return original_make_decision(self, date, stock, data)

    monkeypatch.setattr(FundManager, "make_decision", flaky_make_decision)
    agent.fund_manager = fund_manager

    composite = pd.Series({"A": 1.0, "B": 1.0})
    tradable_mask = pd.Series(True, index=["A", "B"])
    signals = agent.generate_signals(DATES[0], composite, tradable_mask, {})

    assert isinstance(signals, list)
    assert [s.stock for s in signals] == ["A"]
    # 外层（agent）仅 1 次，内层（FundManager）仅 1 次：互不重复计数
    assert agent.get_failure_stats() == {"research_team_analysis": 1}
    assert fund_manager.get_failure_stats() == {"role_analysis": 1}


# --------------------------------------------------------------- T9
@pytest.mark.parametrize("mode", ["exception", "early_exit"])
def test_half_life_exception_vs_early_exit(monkeypatch, mode):
    """D3 / A5：异常路径计数 1、合法早退计数 0，两者返回值同为 nan。"""
    calculator = FactorStatsCalculator(_frame(), _frame())
    rng = np.random.default_rng(11)
    ic_series = pd.Series(rng.normal(size=20), index=pd.bdate_range("2024-01-02", periods=20))

    if mode == "exception":
        monkeypatch.setattr(np, "corrcoef", _boom)
        assert np.isnan(calculator.calculate_half_life(ic_series))
        assert calculator.get_failure_stats() == {"half_life": 1}
    else:
        assert np.isnan(calculator.calculate_half_life(ic_series.iloc[:5]))
        assert calculator.get_failure_stats() == {}


# --------------------------------------------------------------- T10
def test_kpss_exception(monkeypatch, caplog):
    """D3 / A4：异常计数 1 且新增 1 条 WARNING；合法早退同值但计数 0。"""
    monitor = ReturnDistributionMonitor()
    assert monitor._kpss_test(np.zeros(30)) == (0.0, 1.0)
    assert monitor.get_failure_stats() == {}

    caplog.set_level(logging.DEBUG, logger="agents.assumption_monitor")
    monkeypatch.setattr(np, "var", _boom)
    result = monitor._kpss_test(np.random.default_rng(3).normal(size=30))

    assert result == (0.0, 1.0)
    assert monitor.get_failure_stats() == {"kpss_test": 1}
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1
