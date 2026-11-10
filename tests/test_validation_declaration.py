"""P-011 B4：偏差声明（`core/validation.py` + 引擎接线）。

DESIGN §4.3 要求声明字段全部来自运行时状态或能力常量，禁止把未实现的能力写成 True。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from _synth_fixture import write_factor, write_price_fixture
from core.config import BacktestConfig, OptimizerConfig, RebalanceConfig
from core.engine_v2 import BacktestEngineV2
from core.validation import build_validation_declaration

DATES = pd.bdate_range("2024-01-02", periods=8)
CODES = [f"00000{i}" for i in range(1, 5)]


def _run(tmp_path, *, risk_free_rate: float = 0.03, benchmark: str | None = None):
    rng = np.random.default_rng(20261110)
    prices = 10.0 * np.cumprod(1.0 + rng.normal(0.0, 0.01, (len(DATES), len(CODES))), axis=0)
    write_price_fixture(tmp_path, DATES, CODES, prices)
    write_factor(tmp_path, "factor_value", prices.tolist(), DATES, CODES)

    cfg = BacktestConfig(
        data_dir=tmp_path,
        output_dir=tmp_path / "out",
        factor_files=["factor_value.pkl"],
        optimizer=OptimizerConfig(method="equal_weight", target_count=2, max_weight=1.0),
        rebalance=RebalanceConfig(method="fixed", frequency="N_days", n_days=3),
        initial_capital=1_000_000.0,
        risk_free_rate=risk_free_rate,
        benchmark=benchmark,
    )
    engine = BacktestEngineV2(cfg)
    engine.setup()
    return engine.run()


def test_declaration_present(tmp_path):
    """引擎结果必须携带 validation_declaration，且键集与 DESIGN §4.3 一致。"""
    results = _run(tmp_path)
    declaration = results["additional_info"]["validation_declaration"]

    assert set(declaration) == {
        "schema_version",
        "multiple_testing",
        "survivorship",
        "pit_data",
        "benchmark",
        "out_of_sample",
        "risk_free_rate",
        "sharpe_method",
        "execution_timing",
        "known_limitations",
    }
    assert declaration["schema_version"] == "1.0"
    assert len(declaration["known_limitations"]) == 5

    # 指标口径声明（P-011 D5 / DESIGN §5.4）与声明同挂 additional_info
    method = results["additional_info"]["metrics_method"]
    assert set(method) == {
        "annualization_days",
        "risk_free_rate",
        "annual_return",
        "annual_volatility",
        "sharpe_ratio",
        "max_drawdown",
    }
    assert method["annualization_days"] == 252
    assert method["risk_free_rate"] == 0.03


def test_capability_flags_are_false(tmp_path):
    """未实现的能力一律 false；walk_forward 仅声明可用、不代表本次使用。"""
    declaration = _run(tmp_path)["additional_info"]["validation_declaration"]

    assert declaration["pit_data"] is False
    assert declaration["multiple_testing"] == {"corrected": False, "n_trials": None}
    assert declaration["benchmark"]["comparable"] is False
    assert declaration["out_of_sample"]["walk_forward_available"] is True
    assert declaration["out_of_sample"]["used_in_this_run"] is False
    assert declaration["sharpe_method"] == "annual_return_minus_rf_over_annual_vol"


def test_survivorship_derived_from_universe_report():
    """survivorship.corrected 由 universe_report 派生，不写死。"""
    corrected = build_validation_declaration(
        risk_free_rate=0.03,
        universe_report={"survivorship": "corrected"},
        execution_timing="next_open",
    )
    assert corrected["survivorship"] == {"corrected": True, "source": "corrected"}

    uncorrected = build_validation_declaration(
        risk_free_rate=0.03,
        universe_report={"survivorship": "uncorrected"},
        execution_timing="next_open",
    )
    assert uncorrected["survivorship"] == {"corrected": False, "source": "uncorrected"}

    missing = build_validation_declaration(
        risk_free_rate=0.03, universe_report={}, execution_timing="next_open"
    )
    assert missing["survivorship"] == {"corrected": False, "source": "unknown"}


def test_rf_and_benchmark_passed_through(tmp_path):
    """rf 与 benchmark 配置透传：rf=0.05 生效，配置基准只登记 configured。"""
    declaration = _run(tmp_path, risk_free_rate=0.05, benchmark="000300.SH")["additional_info"][
        "validation_declaration"
    ]

    assert declaration["risk_free_rate"] == 0.05
    assert declaration["benchmark"] == {"configured": True, "comparable": False}
    assert declaration["execution_timing"] == "next_open"
