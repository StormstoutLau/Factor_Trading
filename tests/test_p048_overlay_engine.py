"""P-048 overlay 引擎接线测试（IMPL §7.2 + B9 external_max_weight）。

接线口径（F-S6-P048-4）：vol 腿用例必须把 ``cov_lookback`` 设小并证明
``scale_vol < 1.0``——夹具用**单调上涨**价格使 DD≡0（``scale_dd==1``），
此时 enabled 与 disabled 两跑的权重若不同，只可能来自 vol 腿。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_factor, write_price_fixture

DATES = pd.bdate_range("2024-01-02", periods=5)
CODE = "000001"
RISING = np.array([[10.0], [10.5], [10.6], [11.2], [11.3]])
FALLING = np.array([[10.0], [10.0], [10.0], [9.2], [9.2]])


def _fixture(root, prices: np.ndarray) -> None:
    write_price_fixture(root, DATES, [CODE], prices)
    write_factor(root, "factor_value", np.ones((len(DATES), 1)), DATES, [CODE])


def _make_engine(root, *, risk_overlay=None, cov_lookback: int = 2):
    from core.config import (
        BacktestConfig,
        CostConfig,
        FactorConfig,
        OptimizerConfig,
        RebalanceConfig,
        UniverseConfig,
    )
    from core.engine_v2 import BacktestEngineV2

    cfg = BacktestConfig(
        data_dir=root,
        output_dir=root / "out",
        factor_files=["factor_value.pkl"],
        cost=CostConfig(
            commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0
        ),
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",
            target_count=1,
            max_weight=1.0,
            round_lot=True,
            select_top=True,
            cov_lookback=cov_lookback,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False,
            exclude_suspended=False,
            exclude_limit_up=False,
            exclude_limit_down=False,
        ),
        initial_capital=100_000.0,
        enable_pending_orders=False,
        write_manifest=False,
        day_error_mode="raise",
        risk_overlay=risk_overlay,
    )
    return BacktestEngineV2(cfg)


def _run(tmp_path, prices: np.ndarray, *, suffix: str, risk_overlay=None) -> dict:
    root = tmp_path / suffix
    root.mkdir()
    _fixture(root, prices)
    engine = _make_engine(root, risk_overlay=risk_overlay)
    engine.setup()
    engine.run()
    return {
        "nav": float(engine.tracker.get_total_value()),
        "nav_history": list(engine._nav_history),
        "last_target_weight": float(engine._last_targets[CODE].weight),
        "positions": {
            code: int(position.quantity)
            for code, position in engine.tracker.get_all_positions().items()
            if int(position.quantity) > 0
        },
    }


def test_default_none_keeps_baseline(tmp_path):
    """risk_overlay=None 与「enabled 但恒等配置」逐值一致（I4 引擎级）。

    命名避开 ``golden`` 关键词，避免污染 ``-k golden`` 的 18 条基线门禁读数。
    """
    from core.risk_overlay import RiskOverlayConfig

    baseline = _run(tmp_path, FALLING, suffix="none", risk_overlay=None)
    identity = _run(
        tmp_path,
        FALLING,
        suffix="identity",
        risk_overlay=RiskOverlayConfig(enabled=True, defensive_policy="none"),
    )
    assert baseline["nav"] == pytest.approx(identity["nav"])
    assert baseline["last_target_weight"] == pytest.approx(identity["last_target_weight"])
    assert baseline["positions"] == identity["positions"]
    assert baseline["nav_history"] == []


def test_enabled_false_equals_none(tmp_path):
    """enabled=False 与 None 输出逐值相等；且不维护 NAV 序列。"""
    from core.risk_overlay import RiskOverlayConfig

    baseline = _run(tmp_path, FALLING, suffix="none", risk_overlay=None)
    disabled = _run(
        tmp_path,
        FALLING,
        suffix="disabled",
        risk_overlay=RiskOverlayConfig(enabled=False, defensive_policy="cash_scaling"),
    )
    assert disabled["nav"] == pytest.approx(baseline["nav"])
    assert disabled["last_target_weight"] == pytest.approx(baseline["last_target_weight"])
    assert disabled["positions"] == baseline["positions"]
    assert disabled["nav_history"] == []


def test_enabled_scales_weights(tmp_path):
    """vol 腿生效：上涨夹具下 DD≡0 → 权重缩小只能来自 scale_vol < 1。"""
    from core.risk_overlay import RiskOverlayConfig

    disabled = _run(tmp_path, RISING, suffix="off")
    enabled = _run(
        tmp_path,
        RISING,
        suffix="on",
        risk_overlay=RiskOverlayConfig(enabled=True, target_vol=0.01, defensive_policy="none"),
    )

    # 接线：启用后逐日维护 NAV（5 个交易日 → 5 个点）
    assert len(enabled["nav_history"]) == len(DATES)
    # 上涨夹具无回撤 → DD 腿恒等，权重缩小只可能由 vol 腿造成
    assert all(
        later >= earlier
        for earlier, later in zip(enabled["nav_history"], enabled["nav_history"][1:])
    )
    assert disabled["last_target_weight"] == pytest.approx(1.0)
    assert enabled["last_target_weight"] < 1.0
    # O-P051a-2：vol 腿若被 clip 到 1 则等于 disabled → 必须显著小于 1
    assert enabled["last_target_weight"] < 0.1

    # vol 腿闭式：σ_A 由最近两日收益（close[2]/close[1]、close[3]/close[2]）经
    # LedoitWolf 估计（P-046a 起 overlay 复用引擎单一 Σ 入口，单资产时 LW 退化为
    # sklearn 的有偏样本协方差，即 ddof=0）
    from sklearn.covariance import LedoitWolf

    from core.volatility import TRADING_DAYS

    returns = np.array([10.6 / 10.5 - 1.0, 11.2 / 10.6 - 1.0]).reshape(-1, 1)
    sigma_daily = float(np.sqrt(LedoitWolf().fit(returns).covariance_[0, 0]))
    assert sigma_daily > 0.01  # 保证 scale < 1（非零波动）
    # O-P051a-2：引擎 overlay 侧 Σ 已年化 → target_vol（年化）除以 σ_annual
    sigma_annual = sigma_daily * np.sqrt(TRADING_DAYS)
    expected = min(1.0, 0.01 / sigma_annual)
    assert enabled["last_target_weight"] == pytest.approx(expected, rel=1e-6)


def test_nav_history_not_accumulated_when_disabled(tmp_path):
    """未启用（None / enabled=False）时 _nav_history 恒为空。"""
    from core.risk_overlay import RiskOverlayConfig

    assert _run(tmp_path, FALLING, suffix="a")["nav_history"] == []
    assert (
        _run(
            tmp_path,
            FALLING,
            suffix="b",
            risk_overlay=RiskOverlayConfig(enabled=False),
        )["nav_history"]
        == []
    )


# ---------------------------------------------------------------------------
# B9：T4 set_signal(external_max_weight)（F-S7-P048-1 补登）
# ---------------------------------------------------------------------------
def _engine_for_signal(tmp_path):
    _fixture(tmp_path, FALLING)
    engine = _make_engine(tmp_path)
    engine.setup()
    return engine


def test_external_max_weight_rejects_breach(tmp_path):
    engine = _engine_for_signal(tmp_path)
    frame = pd.DataFrame({"000001": 0.8}, index=DATES)
    with pytest.raises(ValueError, match="单票超限"):
        engine.set_signal(frame, mode="weights", external_max_weight=0.5)


def test_external_max_weight_allows_within_limit(tmp_path):
    engine = _engine_for_signal(tmp_path)
    frame = pd.DataFrame({"000001": 0.4}, index=DATES)
    engine.set_signal(frame, mode="weights", external_max_weight=0.5)
    assert engine._signal_mode == "weights"
    assert float(engine._composite_signal.iloc[0, 0]) == pytest.approx(0.4)


def test_external_max_weight_default_none_unchanged(tmp_path):
    """默认 None：既有 weights 合法用例（0.8 单票）逐字通过。"""
    engine = _engine_for_signal(tmp_path)
    frame = pd.DataFrame({"000001": 0.8}, index=DATES)
    engine.set_signal(frame, mode="weights")
    assert float(engine._composite_signal.iloc[0, 0]) == pytest.approx(0.8)

    with pytest.raises(ValueError, match="权重和"):
        engine.set_signal(pd.DataFrame({"000001": 1.2}, index=DATES), mode="weights")
    with pytest.raises(ValueError, match="负权重"):
        engine.set_signal(pd.DataFrame({"000001": -0.1}, index=DATES), mode="weights")
