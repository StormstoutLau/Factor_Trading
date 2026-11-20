"""P-051a：波动原语 + sizing 引擎接线（B1-B16）。

设计依据：docs/IMPL_p051a_sizing_wiring.md §3 / §9.2（F-I1..F-I5 钉死值）。
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_factor, write_price_fixture

DATES = pd.bdate_range("2024-01-02", periods=6)
CODES = ["000001", "600000"]


def _fixture(root: Path) -> None:
    prices = np.array([[10.0 + 0.1 * i, 20.0 + 0.1 * i] for i in range(len(DATES))])
    write_price_fixture(root, DATES, CODES, prices)
    write_factor(root, "factor_value", np.tile([1.0, 2.0], (len(DATES), 1)), DATES, CODES)


def _make_engine(root: Path, *, sizing=None, **cfg_kwargs):
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
            target_count=2,
            max_weight=1.0,
            round_lot=True,
            select_top=True,
            cov_method="sample",
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False
        ),
        initial_capital=10_000_000.0,
        enable_pending_orders=False,
        write_manifest=False,
        sizing=sizing,
        **cfg_kwargs,
    )
    return BacktestEngineV2(cfg)


def _quantities(engine) -> dict[str, int]:
    targets = engine._last_targets or {}
    return {code: target.target_quantity for code, target in targets.items()}


def _run(engine, index: int) -> dict[str, int]:
    engine._execute_rebalance(DATES[index], index)
    return _quantities(engine)


# ---------------------------------------------------------------------------
# B1-B4：波动原语
# ---------------------------------------------------------------------------


def test_b1_volatility_closed_form():
    from core.volatility import estimate_volatility

    assert estimate_volatility(pd.Series([0.01, -0.01]), lookback=2).iloc[1] == pytest.approx(
        0.2244994, abs=1e-6
    )
    four = estimate_volatility(pd.Series([0.01, -0.01, 0.02, -0.02]), lookback=4)
    assert four.iloc[3] == pytest.approx(0.2898275, abs=1e-6)


def test_b2_volatility_nan_and_unannualized():
    from core.volatility import estimate_volatility

    series = pd.Series([0.01, -0.01, 0.03, 0.01])
    annual = estimate_volatility(series, lookback=2)
    assert math.isnan(annual.iloc[0])
    assert annual.iloc[1] == pytest.approx(0.2244994432, abs=1e-9)
    assert annual.iloc[2] == pytest.approx(0.4489988864, abs=1e-9)
    assert annual.iloc[3] == pytest.approx(0.2244994432, abs=1e-9)

    daily = estimate_volatility(series, lookback=2, annualize=False)
    assert daily.iloc[1] == pytest.approx(0.0141421356, abs=1e-9)
    assert daily.iloc[2] == pytest.approx(0.0282842712, abs=1e-9)
    assert daily.iloc[3] == pytest.approx(0.0141421356, abs=1e-9)

    with_nan = estimate_volatility(pd.Series([0.01, np.nan, 0.02, 0.01]), lookback=2)
    assert math.isnan(with_nan.iloc[1])
    assert math.isnan(with_nan.iloc[2])
    assert with_nan.iloc[3] == pytest.approx(0.1122497216, abs=1e-9)


def test_b3_atr_standard_wilder():
    from core.volatility import atr

    high = pd.Series([10.5, 11.0, 11.2, 11.5, 11.8])
    low = pd.Series([9.5, 10.0, 10.5, 10.8, 11.0])
    close = pd.Series([10.0, 10.8, 11.0, 11.3, 11.6])
    out = atr(high, low, close, period=3)
    assert math.isnan(out.iloc[0]) and math.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(0.9, abs=1e-7)
    assert out.iloc[3] == pytest.approx(0.8333333, abs=1e-7)
    assert out.iloc[4] == pytest.approx(0.8222222, abs=1e-7)


def test_b4_atr_invalid_inputs():
    from core.volatility import atr

    with pytest.raises(ValueError):
        atr(pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0, 3.0]), pd.Series([1.0, 2.0]))
    with pytest.raises(ValueError):
        atr(pd.Series([1.0]), pd.Series([0.5]), pd.Series([0.8]), period=0)
    with pytest.raises(ValueError):
        atr(pd.Series([1.0]), pd.Series([0.5]), pd.DataFrame({"c": [0.8]}))

    single = atr(pd.Series([10.5, 11.0]), pd.Series([9.5, 10.0]), pd.Series([10.0, 10.8]), period=1)
    assert single.iloc[0] == pytest.approx(1.0)
    assert single.iloc[1] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# B5-B16：引擎接线
# ---------------------------------------------------------------------------


def test_b5_sizing_none_is_zero_behavior(tmp_path, caplog):
    from core.sizing import SizingConfig

    caplog.set_level(logging.WARNING)
    base = _make_engine(tmp_path / "base", sizing=None)
    none_cfg = _make_engine(tmp_path / "none", sizing=SizingConfig(method="none"))
    for engine in (base, none_cfg):
        _fixture(engine.cfg.data_dir)
        engine.setup()

    for index in range(4):
        assert _run(base, index) == _run(none_cfg, index)
    sizing_logs = [
        record
        for record in caplog.records
        if record.name == "core.engine_v2" and "sizing" in record.getMessage()
    ]
    assert sizing_logs == []


def test_b6_none_method_applies_constraints(tmp_path):
    from core.sizing import SizingConfig

    base = _make_engine(tmp_path / "base")
    _fixture(base.cfg.data_dir)
    base.setup()
    capped = _make_engine(tmp_path / "capped", sizing=SizingConfig(method="none", max_weight=0.2))
    _fixture(capped.cfg.data_dir)
    capped.setup()

    baseline = _run(base, 2)
    sized = _run(capped, 2)
    for code in CODES:
        ratio = sized[code] / baseline[code]
        assert 0.39 < ratio < 0.41
        price = 10.2 if code == CODES[0] else 20.2
        assert sized[code] * price / 10_000_000.0 <= 0.2 + 1e-9


def test_b7_vol_target_annualized_scale(tmp_path):
    from core.sizing import SizingConfig

    base = _make_engine(tmp_path / "base")
    _fixture(base.cfg.data_dir)
    base.setup()
    sized_engine = _make_engine(
        tmp_path / "sized", sizing=SizingConfig(method="vol_target", vol_lookback=2)
    )
    _fixture(sized_engine.cfg.data_dir)
    sized_engine.setup()

    known = np.array([[0.01, 0.02], [-0.01, -0.02]] + [[0.0, 0.0]] * 4)
    sized_engine._returns_matrix = known

    baseline = _run(base, 2)
    sized = _run(sized_engine, 2)
    from core.portfolio import estimate_cov

    rets = pd.DataFrame(known[:2], columns=CODES)
    cov_daily = estimate_cov(rets, method="sample").to_numpy()
    weights = np.full(len(CODES), 0.5)
    sigma_annual = math.sqrt(float(weights @ (cov_daily * 252) @ weights))
    scale = min(0.15 / sigma_annual, 1.0)
    assert 0.4 < scale < 0.7  # 漏 ×252 或漏 Σ 时 scale 会被夹到 1.0
    for code in CODES:
        assert sized[code] / baseline[code] == pytest.approx(scale, rel=2e-3)


def test_b8_insufficient_history_skips(tmp_path, caplog):
    from core.sizing import SizingConfig

    caplog.set_level(logging.WARNING)
    base = _make_engine(tmp_path / "base")
    _fixture(base.cfg.data_dir)
    base.setup()
    short = _make_engine(tmp_path / "short", sizing=SizingConfig(method="vol_target"))
    _fixture(short.cfg.data_dir)
    short.setup()

    baseline = _run(base, 2)
    assert _run(short, 2) == baseline
    assert "insufficient_history" in caplog.text


def test_b9_zero_vol_keeps_weights(tmp_path, caplog):
    from core.sizing import SizingConfig

    caplog.set_level(logging.WARNING)
    base = _make_engine(tmp_path / "base")
    _fixture(base.cfg.data_dir)
    base.setup()
    flat = _make_engine(tmp_path / "flat", sizing=SizingConfig(method="vol_target", vol_lookback=2))
    _fixture(flat.cfg.data_dir)
    flat.setup()
    flat._returns_matrix = np.zeros((len(DATES), len(CODES)))

    baseline = _run(base, 2)
    assert _run(flat, 2) == baseline
    assert "zero_vol" in caplog.text


def test_b10_short_path_skips_sizing(tmp_path):
    """短仓路径：sizing 零作用（max_weight=0.2 也不生效）。"""
    from core.sizing import SizingConfig

    base = _make_engine(tmp_path / "base")
    _fixture(base.cfg.data_dir)
    base.setup()
    short = _make_engine(
        tmp_path / "short",
        sizing=SizingConfig(method="none", max_weight=0.2),
        allow_negative_stock_positions=True,
    )
    _fixture(short.cfg.data_dir)
    short.setup()

    assert _run(short, 2) == _run(base, 2)


def test_b11_method_subset_fail_fast(tmp_path):
    from core.sizing import SizingConfig

    for method in ("kelly", "risk_parity"):
        engine = _make_engine(tmp_path / method, sizing=SizingConfig(method=method))
        with pytest.raises(ValueError, match="P-051a"):
            engine.setup()


def test_b12_sizing_state_json_roundtrip():
    from core.sizing import SizingState

    state = SizingState(entry_price=100.0, last_add_price=100.0, add_count=1)
    restored = SizingState(**json.loads(json.dumps(dataclasses.asdict(state))))
    assert restored == state


def test_b13_nan_price_skips_sizing(tmp_path, caplog, monkeypatch):
    from core.sizing import SizingConfig

    caplog.set_level(logging.WARNING)
    engine = _make_engine(tmp_path / "nan", sizing=SizingConfig(method="none"))
    _fixture(engine.cfg.data_dir)
    engine.setup()

    panel = engine._exec_price(engine.dm, "close").copy()
    panel.loc[DATES[2], CODES[0]] = np.nan
    monkeypatch.setattr(engine, "_exec_price", lambda dm, price_type: panel)

    engine._execute_rebalance(DATES[2], 2)
    assert "sizing_skipped_bad_price" in caplog.text


def test_b14_dual_vol_warning_once(tmp_path, caplog):
    from core.risk_overlay import RiskOverlayConfig
    from core.sizing import SizingConfig

    caplog.set_level(logging.WARNING)
    engine = _make_engine(
        tmp_path / "dual",
        sizing=SizingConfig(method="vol_target"),
        risk_overlay=RiskOverlayConfig(enabled=True, target_vol=0.2),
    )
    _fixture(engine.cfg.data_dir)
    engine.setup()
    hits = [record for record in caplog.records if "两腿独立缩放" in record.getMessage()]
    assert len(hits) == 1


def test_b15_no_new_reference_dir():
    golden_dir = Path(__file__).parent / "golden"
    assert not (golden_dir / "p051a").exists()


def test_b16_min_weight_fail_fast(tmp_path):
    from core.sizing import SizingConfig

    engine = _make_engine(tmp_path / "minw", sizing=SizingConfig(method="none", min_weight=0.1))
    with pytest.raises(ValueError, match="F-D1"):
        engine.setup()
