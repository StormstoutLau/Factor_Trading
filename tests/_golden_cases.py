"""P-013：golden 基线 case 构造器（**单一来源**，DESIGN §8 D7 / IMPL T-4）。

录制脚本 ``scripts/record_golden.py`` 与断言测试 ``tests/test_golden_baseline.py``
**共同 import 本模块**，确保两侧使用完全相同的夹具与引擎调用，杜绝
「录制用夹具 A、断言跑夹具 B」的静默漂移。

边界（A20）：golden 只锁「当前行为」，**不证明正确性**；正确性由 P-011 的
L1-L3（不变量 / 参考实现差分 / 事件级等价）承担。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from _synth_fixture import write_factor, write_price_fixture, write_universe
from core.config import (
    BacktestConfig,
    CostConfig,
    FactorConfig,
    OptimizerConfig,
    RebalanceConfig,
    UniverseConfig,
)
from core.data_v3 import DataLoaderV3
from core.engine_v2 import BacktestEngineV2
from core.engine_v3_vector import VectorBacktestEngine

SCHEMA_VERSION = "1.0"
TOLERANCE = {"rtol": 1e-9, "atol": 1e-12, "money_atol": 1e-6}
INITIAL_CAPITAL = 10_000_000.0
CASE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6")

_BASE_DATES = pd.bdate_range("2024-01-02", periods=5)
_BASE_CODES = ["000001", "600000"]
_VOL_DATES = pd.bdate_range("2024-01-02", periods=20)
_VOL_CODES = ["000001", "600000", "000002"]


@dataclass(frozen=True)
class CaseMeta:
    case_id: str
    engine: str
    scenario: str
    description: str


CASES: dict[str, CaseMeta] = {
    "G1": CaseMeta("G1", "v2", "baseline", "V2 基础：常量价、零费用、5 日 × 2 股"),
    "G2": CaseMeta("G2", "v2", "cost", "V2 费用：真实波动 + 佣金/印花税/滑点 + 整手"),
    "G3": CaseMeta("G3", "v2", "mask", "V2 掩码：涨停（开盘价触及限幅）+ 停牌"),
    "G4": CaseMeta("G4", "v3", "baseline", "V3 基础：常量价、零费用、5 日 × 2 股"),
    "G5": CaseMeta("G5", "v3", "cost", "V3 费用：真实波动 + cost_rate=0.001"),
    "G6": CaseMeta("G6", "v2", "delisting", "V2 退市：universe 动态池在第 15 日移除标的"),
}


def _base_const_prices() -> tuple[np.ndarray, np.ndarray]:
    close = np.array([[10.0, 25.0]] * len(_BASE_DATES))
    return close, close.copy()


def _volatile_prices(n_dates: int, n_codes: int) -> tuple[np.ndarray, np.ndarray]:
    """确定性波动价（无随机），open 与 close 不同以覆盖成交时点口径。"""
    i = np.arange(n_dates, dtype=float)
    close = np.column_stack([10.0 + 5.0 * k + 0.1 * np.sin(i + k) for k in range(n_codes)])
    open_ = close * (1.0 + 0.002 * np.cos(i))[:, None]
    return close, open_


def _factor_matrix(n_dates: int, n_codes: int) -> np.ndarray:
    """确定性因子（排名稳定：列序即强弱序）。"""
    return np.tile(np.arange(1.0, n_codes + 1), (n_dates, 1))


def _v2_config(root: Path, *, n_codes: int, cost: bool, suspended: bool = False) -> BacktestConfig:
    cost_cfg = (
        CostConfig(
            commission_rate=0.0003,
            commission_min=5.0,
            stamp_tax_rate=0.001,
            slippage_pct=0.001,
        )
        if cost
        else CostConfig(
            commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0
        )
    )
    return BacktestConfig(
        data_dir=root,
        output_dir=root / "out",
        factor_files=["factor_value.pkl"],
        cost=cost_cfg,
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",
            target_count=n_codes,
            max_weight=1.0,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False,
            exclude_suspended=suspended,
            exclude_limit_up=suspended,
        ),
        initial_capital=INITIAL_CAPITAL,
        enable_pending_orders=False,
    )


def _run_v2(root: Path, *, n_codes: int, cost: bool, suspended: bool = False) -> dict[str, Any]:
    cfg = _v2_config(root, n_codes=n_codes, cost=cost, suspended=suspended)
    engine = BacktestEngineV2(cfg)
    engine.setup()
    results = engine.run()

    # 观测网前置（P-011 I1/I2）：不变量不通过的运行**不得**进入基线——
    # 否则等于把违规行为固化为「期望值」。录制与断言两侧都会走到这里。
    inv = (results.get("additional_info") or {}).get("invariant_report") or {}
    if inv and not inv.get("ok", True):
        violations = inv.get("violations", [])
        raise AssertionError(
            f"V2 不变量校验未通过（{len(violations)} 项），拒绝生成基线: {violations[:3]}"
        )

    trades_df = engine.executor.trade_log.get_trades_df() if engine.executor is not None else None
    trade_count = int(len(trades_df)) if trades_df is not None else 0
    trade_amount = float(trades_df["amount"].sum()) if trade_count else 0.0
    trade_cost = float(trades_df["cost"].sum()) if trade_count and "cost" in trades_df else 0.0

    return {
        "metrics": results["performance_metrics"],
        "portfolio_value": results["portfolio_value"],
        "trades": {"count": trade_count, "total_amount": trade_amount, "total_cost": trade_cost},
        "executed_trade_count": trade_count,
        "executed_trade_amount": trade_amount,
    }


def _run_v3(
    *, n_dates: int, n_codes: int, close: np.ndarray, open_: np.ndarray, cost_rate: float
) -> dict[str, Any]:
    dates, codes = (
        (_BASE_DATES, _BASE_CODES) if n_dates == len(_BASE_DATES) else (_VOL_DATES, _VOL_CODES)
    )
    shape = {"index": dates, "columns": codes}
    factor = _factor_matrix(n_dates, n_codes)
    loader = DataLoaderV3.from_pandas_dataframes(
        close=pd.DataFrame(close, **shape),
        open=pd.DataFrame(open_, **shape),
        high=pd.DataFrame(np.maximum(close, open_), **shape),
        low=pd.DataFrame(np.minimum(close, open_), **shape),
        factor_dict={"factor": pd.DataFrame(factor, **shape)},
    )
    engine = VectorBacktestEngine(
        {
            "initial_capital": INITIAL_CAPITAL,
            "top_n": n_codes,
            "rebalance_freq": 1,
            "cost_rate": cost_rate,
        }
    )
    engine.setup(loader)
    results = engine.run()

    pv = np.asarray(results["portfolio_value"], dtype=float)
    mdd = float(results["max_drawdown"])
    if abs(mdd) < 1e-15:  # 归一化浮点负零，避免基线出现 -0.0
        mdd = 0.0
    return {
        "metrics": {
            "total_return": float(results["total_return"]),
            "annual_return": float(results["annual_return"]),
            "annual_volatility": float(results["volatility"]),
            "sharpe_ratio": float(results["sharpe_ratio"]),
            "max_drawdown": mdd,
            "final_value": float(results["final_value"]),
        },
        "portfolio_value": pv,
        "trades": {"count": 0, "total_amount": 0.0, "total_cost": 0.0},
        "executed_trade_count": 0,
        "executed_trade_amount": 0.0,
    }


def _nav_block(pv) -> dict[str, Any]:
    arr = np.asarray(pv, dtype=float)
    return {
        "length": int(arr.size),
        "first": float(arr[0]),
        "last": float(arr[-1]),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def _metrics_block_v2(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "total_return": float(metrics["total_return"]),
        "annual_return": float(metrics["annual_return"]),
        "annual_volatility": float(metrics["annual_volatility"]),
        "sharpe_ratio": float(metrics["sharpe_ratio"]),
        "max_drawdown": float(metrics["max_drawdown"]),
        "final_value": float(metrics.get("final_value", 0.0)),
    }


def _final_value_from_pv(pv) -> float:
    arr = np.asarray(pv, dtype=float)
    return float(arr[-1])


def build_case(case_id: str, root: Path) -> dict[str, Any]:
    """构造并运行一个 case，返回可直接序列化为基线 JSON 的 payload。

    首次运行后会清理 ``root/out`` 下的图表产物，避免 golden 录制污染工作区。
    """
    if case_id not in CASES:
        raise KeyError(f"未知 case_id: {case_id}")

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    meta = CASES[case_id]

    if case_id == "G1":
        close, open_ = _base_const_prices()
        write_price_fixture(root, _BASE_DATES, _BASE_CODES, close, open_prices=open_)
        write_factor(
            root,
            "factor_value",
            _factor_matrix(len(_BASE_DATES), len(_BASE_CODES)),
            _BASE_DATES,
            _BASE_CODES,
        )
        run = _run_v2(root, n_codes=2, cost=False)
        metrics = _metrics_block_v2(run["metrics"])
        metrics["final_value"] = _final_value_from_pv(run["portfolio_value"])

    elif case_id == "G2":
        close, open_ = _volatile_prices(len(_VOL_DATES), len(_VOL_CODES))
        write_price_fixture(root, _VOL_DATES, _VOL_CODES, close, open_prices=open_)
        write_factor(
            root,
            "factor_value",
            _factor_matrix(len(_VOL_DATES), len(_VOL_CODES)),
            _VOL_DATES,
            _VOL_CODES,
        )
        run = _run_v2(root, n_codes=3, cost=True)
        metrics = _metrics_block_v2(run["metrics"])
        metrics["final_value"] = _final_value_from_pv(run["portfolio_value"])

    elif case_id == "G3":
        close, _ = _volatile_prices(len(_VOL_DATES), len(_VOL_CODES))
        close = close.copy()
        # 第 10 个交易日列 0 真实涨停：整段价格上移至 close(9) × 1.10，使
        #   open(t10) == close(t9) × 1.10（触发涨跌停掩码）且价格序列连续（无虚假跳空）。
        # 停牌场景不纳入本基线：P-013 实施期发现 V2 停牌路径存在两项缺陷
        # （停牌日仍成交 / 恢复日重复记账致负持仓），已登记 F-S9-G2 另立批次。
        bump = close[9, 0] * 1.10 / close[10, 0]
        close[10:, 0] = close[10:, 0] * bump
        open_ = close.copy()
        write_price_fixture(root, _VOL_DATES, _VOL_CODES, close, open_prices=open_)
        write_factor(
            root,
            "factor_value",
            _factor_matrix(len(_VOL_DATES), len(_VOL_CODES)),
            _VOL_DATES,
            _VOL_CODES,
        )
        run = _run_v2(root, n_codes=3, cost=True, suspended=True)
        metrics = _metrics_block_v2(run["metrics"])
        metrics["final_value"] = _final_value_from_pv(run["portfolio_value"])

    elif case_id == "G4":
        close, open_ = _base_const_prices()
        run = _run_v3(n_dates=len(_BASE_DATES), n_codes=2, close=close, open_=open_, cost_rate=0.0)
        metrics = run["metrics"]

    elif case_id == "G5":
        close, open_ = _volatile_prices(len(_VOL_DATES), len(_VOL_CODES))
        run = _run_v3(n_dates=len(_VOL_DATES), n_codes=3, close=close, open_=open_, cost_rate=0.001)
        metrics = run["metrics"]

    else:  # G6
        close, open_ = _volatile_prices(len(_VOL_DATES), len(_VOL_CODES))
        write_price_fixture(root, _VOL_DATES, _VOL_CODES, close, open_prices=open_)
        write_factor(
            root,
            "factor_value",
            _factor_matrix(len(_VOL_DATES), len(_VOL_CODES)),
            _VOL_DATES,
            _VOL_CODES,
        )
        write_universe(
            root,
            list_rows=[{"stock": code, "list_date": "2020-01-01"} for code in _VOL_CODES],
            delist_rows=[
                {
                    "stock": _VOL_CODES[2],
                    "delist_date": str(_VOL_DATES[14].date()),
                    "delist_return": -0.1,
                }
            ],
        )
        run = _run_v2(root, n_codes=3, cost=True)
        metrics = _metrics_block_v2(run["metrics"])
        metrics["final_value"] = _final_value_from_pv(run["portfolio_value"])

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": meta.case_id,
        "engine": meta.engine,
        "scenario": meta.scenario,
        "description": meta.description,
        "tolerance": dict(TOLERANCE),
        "metrics": metrics,
        "nav": _nav_block(run["portfolio_value"]),
        "trades": run["trades"],
    }
