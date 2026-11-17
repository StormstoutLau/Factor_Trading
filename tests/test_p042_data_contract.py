"""P-042 B1/B2 数据契约测试（V1-V7）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import agents.agent_framework as agent_framework_module
from agents.agent_framework import ResearchTeamAgent
from core.config import BacktestConfig
from core.data import DataManager
from core.data_provider import PklDataProvider
from core.interfaces import IDataManager


def test_v1_pkl_provider_load_factor_roundtrip(tmp_path):
    """V1：端口读取因子逐值相等。"""
    frame = pd.DataFrame({"A": [1.0, 2.0]}, index=pd.date_range("2024-01-02", periods=2))
    frame.to_pickle(tmp_path / "f.pkl")

    loaded = PklDataProvider(tmp_path).load_factor("f.pkl")

    pd.testing.assert_frame_equal(loaded, frame)


def test_v2_pkl_provider_load_factor_missing(tmp_path):
    """V2：缺失文件抛 FileNotFoundError，文案含路径。"""
    with pytest.raises(FileNotFoundError, match="因子文件不存在:"):
        PklDataProvider(tmp_path).load_factor("missing.pkl")


class _SpyProvider:
    def __init__(self, close: pd.DataFrame, factor: pd.DataFrame) -> None:
        self._close = close
        self._factor = factor
        self.factor_calls: list[str] = []

    def load_price(self, kind):
        return self._close

    def load_aux(self, kind):
        return None

    def load_universe(self):
        return None

    def load_factor(self, name):
        self.factor_calls.append(name)
        return self._factor


def test_v3_load_factor_goes_through_provider():
    """V3：DataManager.load_factor 经端口读取。"""
    dates = pd.bdate_range("2024-01-02", periods=3)
    close = pd.DataFrame({"A": [1.0, 1.1, 1.2]}, index=dates)
    factor = pd.DataFrame({"A": [0.1, 0.2]}, index=dates[:2])
    provider = _SpyProvider(close, factor)
    dm = DataManager(BacktestConfig(factor_files=["f.pkl"]), provider=provider)

    _ = dm.trade_dates
    result = dm.load_factor("f.pkl")

    assert provider.factor_calls == ["f.pkl"]
    assert list(result.index) == list(dates)
    assert result["A"].iloc[2] == 0.2


def test_v4_load_factor_alignment_semantics(tmp_path):
    """V4：asof 对齐 / 首因子日前 NaN / 缺列填 0 零变更（非回归护栏）。"""
    dates = pd.bdate_range("2024-01-02", periods=6)
    pd.DataFrame({"A": [1.0] * 6, "B": [1.0] * 6}, index=dates).to_pickle(tmp_path / "close.pkl")
    pd.DataFrame({"A": [1.0, 2.0]}, index=pd.DatetimeIndex([dates[2], dates[4]])).to_pickle(
        tmp_path / "f.pkl"
    )

    dm = DataManager(BacktestConfig(data_dir=tmp_path, factor_files=["f.pkl"]))
    _ = dm.trade_dates
    aligned = dm.load_factor("f.pkl")

    assert list(aligned.columns) == ["A", "B"]
    assert aligned["B"].eq(0).all()
    assert aligned["A"].iloc[:2].isna().all()
    assert list(aligned["A"].iloc[2:4]) == [1.0, 1.0]
    assert list(aligned["A"].iloc[4:]) == [2.0, 2.0]


class _Pipe:
    def __init__(self, data_manager, factor_config):
        pass

    def process(self, raw):
        return raw


class _Comb:
    def __init__(self, factor_files, factor_weights):
        pass

    def combine(self, processed):
        return next(iter(processed.values()))


class _AuxDM:
    def __init__(self, industry=None, mktcap=None, fail_industry=False):
        self.data_dir = Path("./__missing__")
        self._industry = industry
        self._mktcap = mktcap
        self._fail_industry = fail_industry

    def load_factor(self, name):
        return pd.DataFrame({"A": [1.0]}, index=pd.DatetimeIndex(["2024-01-02"]))

    def get_adj_price(self, price_type, adjustment_type):
        return pd.DataFrame({"A": [1.0]}, index=pd.DatetimeIndex(["2024-01-02"]))

    def load_aux_raw(self, kind):
        if kind == "industry":
            if self._fail_industry:
                raise RuntimeError("boom")
            return self._industry
        return self._mktcap


def _agent(monkeypatch):
    monkeypatch.setattr(agent_framework_module, "FactorPipeline", _Pipe)
    monkeypatch.setattr(agent_framework_module, "FactorCombiner", _Comb)
    agent = ResearchTeamAgent()
    monkeypatch.setattr(agent, "_init_research_team", lambda dm: None)
    return agent


def test_v5_agent_framework_caches_industry_via_facade(monkeypatch):
    """V5：agents 经门面读行业/市值，成功路径零失败计数。"""
    index = pd.DatetimeIndex(["2024-01-02"])
    industry = pd.DataFrame({"A": [1]}, index=index)
    mktcap = pd.DataFrame({"A": [1e9]}, index=index)

    agent = _agent(monkeypatch)
    agent.prepare_factors(_AuxDM(industry=industry, mktcap=mktcap))

    assert agent._industry_data is industry
    assert agent._mktcap_data is mktcap
    assert agent.get_failure_stats() == {}


def test_v6_agent_framework_cache_failure_still_counted(monkeypatch):
    """V6：行业读取抛错仍计 1，缓存保持 None。"""
    agent = _agent(monkeypatch)
    agent.prepare_factors(_AuxDM(fail_industry=True))

    assert agent._industry_data is None
    assert agent._mktcap_data is None
    assert agent.get_failure_stats() == {"industry_cache": 1}


_CONSUMERS = {
    "trade_dates",
    "stock_codes",
    "close",
    "open",
    "high",
    "low",
    "adj_factor",
    "suspend",
    "st",
    "industry",
    "mktcap",
    "universe",
}


def test_v7_idatamanager_covers_data_layer_consumers():
    """V7：filter/factor 实际消费集合 ⊆ 协议 ⊆ 实现；两个具体方法不入协议。"""
    protocol_members = {name for name in dir(IDataManager) if not name.startswith("_")}
    assert _CONSUMERS <= protocol_members
    assert "load_aux_raw" not in protocol_members
    assert "data_fingerprint" not in protocol_members

    dm = DataManager(BacktestConfig())
    impl_members = {name for name in dir(dm) if not name.startswith("_")}
    assert _CONSUMERS <= impl_members
