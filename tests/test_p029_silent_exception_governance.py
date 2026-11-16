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
