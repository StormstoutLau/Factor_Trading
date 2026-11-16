"""P-029 静默失败治理第四批（agents/ 9 处计量）测试。

对应 docs/IMPL_p029_silent_exception_governance_phase4.md §5（V1-V7）。
全部使用 monkeypatch（禁用 mock 库，DESIGN D7）。
"""

from __future__ import annotations

import logging
import sys
import types

import pandas as pd
import pytest

import agents.agent_framework as agent_framework_module
import agents.research_team_v2 as research_team_module
from agents.agent_framework import ResearchTeamAgent
from agents.multi_strategy_engine import StrategyConfig, StrategyEngine
from core.config import BacktestConfig
from core.pending import OrderSide, PendingOrderQueue, create_pending_order

STOCKS = ["A", "B", "C"]
DATES = pd.bdate_range("2024-01-02", periods=3)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(10.0, index=DATES, columns=STOCKS)


class _Pipe:
    """FactorPipeline 替身（不触真实因子管道）。"""

    def __init__(self, data_manager, factor_config):
        pass

    def process(self, raw):
        return raw


class _Comb:
    """FactorCombiner 替身。"""

    def __init__(self, factor_files, factor_weights):
        pass

    def combine(self, processed):
        return _frame()


class _FakeDM:
    """prepare_factors 所需最小数据面。"""

    def __init__(self, data_dir, raise_price=False):
        self.data_dir = data_dir
        self._raise_price = raise_price

    def load_factor(self, name):
        return _frame()

    def get_adj_price(self, field, adjustment_type):
        if self._raise_price:
            raise RuntimeError("boom")
        return _frame()


# --------------------------------------------------------------- V1
@pytest.mark.parametrize(
    "case,key,attr",
    [
        ("price", "price_cache", "_price_data"),
        ("industry", "industry_cache", "_industry_data"),
        ("mktcap", "mktcap_cache", "_mktcap_data"),
    ],
)
def test_cache_failure_counts(tmp_path, monkeypatch, caplog, case, key, attr):
    """D1 / V1：三缓存各自失败计数 1、缓存保持 None、零 WARNING 日志。"""
    monkeypatch.setattr(agent_framework_module, "FactorPipeline", _Pipe)
    monkeypatch.setattr(agent_framework_module, "FactorCombiner", _Comb)

    if case == "industry":
        (tmp_path / "industry.pkl").write_bytes(b"not a pickle")
    elif case == "mktcap":
        (tmp_path / "mktcap.pkl").write_bytes(b"not a pickle")

    agent = ResearchTeamAgent()
    monkeypatch.setattr(agent, "_init_research_team", lambda dm: None)

    caplog.clear()
    caplog.set_level(logging.WARNING, logger="agents.agent_framework")

    agent.prepare_factors(_FakeDM(tmp_path, raise_price=(case == "price")))

    assert agent.get_failure_stats() == {key: 1}
    assert getattr(agent, attr) is None
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


# --------------------------------------------------------------- V2
def test_rotation_analyzer_skipped(monkeypatch):
    """D2 / V2：数据缺失 → else 分支计 1，分析器保持 None，无 init 失败键。"""
    monkeypatch.setitem(sys.modules, "research_team_v2", research_team_module)

    class _DummyAnalyzer:
        def __init__(self, *args, **kwargs):
            raise AssertionError("数据缺失时不应构造分析器")

    fake_module = types.ModuleType("industry_rotation_v2")
    fake_module.IndustryRotationAnalyzer = _DummyAnalyzer
    monkeypatch.setitem(sys.modules, "industry_rotation_v2", fake_module)

    agent = ResearchTeamAgent()
    agent._research_team_available = True
    agent._price_data = None
    agent._industry_data = None

    agent._init_research_team(None)

    assert agent.rotation_analyzer is None
    assert agent.get_failure_stats() == {"rotation_analyzer_skipped": 1}


# --------------------------------------------------------------- V3
class _BrokenFM:
    def get_team_report(self):
        raise RuntimeError("boom")


def test_team_report_failure():
    """D3 / V3：team_report 缺键计 1，且同调 failure_counts 可见（L1152 下移）。"""
    agent = ResearchTeamAgent()
    agent.fund_manager = _BrokenFM()

    summary = agent.get_performance_summary()

    assert "team_report" not in summary
    assert summary["failure_counts"] == {"performance_summary_team_report": 1}
    assert summary["agent_id"] == agent.agent_id
    assert "style" in summary


# --------------------------------------------------------------- V4 / V5
class _RaisingLoc:
    def __getitem__(self, key):
        raise KeyError("missing price")


class _MissingPriceFrame:
    """columns/index 正常但 .loc 取值必抛 KeyError。"""

    columns = pd.Index(["A"])
    index = pd.DatetimeIndex(DATES)
    loc = _RaisingLoc()


class _EngineDM:
    def __init__(self, n_days: int = 1):
        self.trade_dates = pd.bdate_range("2024-01-02", periods=n_days)
        self.stock_codes = STOCKS
        self.n_stocks = len(STOCKS)
        self.returns = pd.DataFrame(0.0, index=self.trade_dates, columns=STOCKS)

    def get_adj_price(self, field, adjustment_type):
        return pd.DataFrame(10.0, index=self.trade_dates, columns=STOCKS)


def _make_engine() -> StrategyEngine:
    strategy_cfg = StrategyConfig(name="long", direction="long", target_count=2)
    base_cfg = BacktestConfig(enable_pending_orders=False)
    return StrategyEngine(
        strategy_cfg,
        base_cfg,
        _EngineDM(),
        None,
        pd.DataFrame(0.0, index=DATES, columns=STOCKS),
    )


@pytest.mark.parametrize("case", ["legal", "exception"])
def test_order_missing_price(monkeypatch, case):
    """D4 / V4：合法缺列计 0、异常计 1；两例均不产生订单。"""
    engine = _make_engine()

    if case == "legal":
        engine._generate_orders(DATES[0], 0, pd.Series({"ZZZ": 1.0}))
        assert engine.get_failure_stats() == {}
    else:
        monkeypatch.setattr(engine.dm, "get_adj_price", lambda *a, **k: _MissingPriceFrame())
        engine._generate_orders(DATES[0], 0, pd.Series({"A": 1.0}))
        assert engine.get_failure_stats() == {"orders_missing_price": 1}

    assert engine._next_day_orders == []
    assert engine.pending_queue is None


@pytest.mark.parametrize("case,key", [("next_day", "next_day_open_price"), ("pending", "pending_open_price")])
def test_open_price_failures(monkeypatch, caplog, case, key):
    """D4 / V5：S6/S7 各计 1，队列语义不变，零 WARNING 日志。"""
    engine = _make_engine()
    monkeypatch.setattr(engine.dm, "get_adj_price", lambda *a, **k: _MissingPriceFrame())

    caplog.clear()
    caplog.set_level(logging.WARNING, logger="agents.multi_strategy_engine")

    if case == "next_day":
        engine._next_day_orders = [{"order": object(), "create_date": DATES[0]}]
        engine._execute_next_day_orders(DATES[0], 0)
        assert len(engine._next_day_orders) == 1
    else:
        engine.pending_queue = PendingOrderQueue()
        engine.pending_queue.add_order(create_pending_order("A", OrderSide.BUY, 100, DATES[0]))
        before = len(engine.pending_queue.get_pending_orders())
        engine._process_pending_orders(DATES[0], 0)
        assert len(engine.pending_queue.get_pending_orders()) == before

    assert engine.get_failure_stats() == {key: 1}
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
