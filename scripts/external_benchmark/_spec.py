"""P-015 对拍规格层：案例定义 + 声明式规格模拟器。

规格 = [DESIGN_p015_external_benchmark.md](../../docs/DESIGN_p015_external_benchmark.md)
§3 / §8 对 V3 内核语义的逐字翻译（E3 @`607f1c3`）。两侧引擎各自对规格断言；
规格之间的差异写成恒等式（DESIGN D3，不互比两侧输出）。

案例数据全部确定性构造（无随机数），保证可重放（E1）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

INIT_CASH = 10_000_000.0
SPEC_VERSION = "1.0"
RTOL = 1e-12
MONEY_ATOL = 1e-6

_CASES_2 = ["000001", "600000"]
_CASES_4 = ["000001", "600000", "000002", "300059"]


@dataclass(frozen=True)
class CaseSpec:
    case: str  # B1..B5
    layer: str  # L0 / L1 / L2 / L3 / NegCtl
    entry_mode: str  # "orders" | "targetpercent"
    cost_rate: float
    fees_perturb: float = 0.0  # 仅 B5：vbt 侧在 cost_rate 之上追加
    reb_freq: int = 1
    top_n: int = 2


def get_case(case: str) -> CaseSpec:
    if case == "B1":
        return CaseSpec(case="B1", layer="L0", entry_mode="orders", cost_rate=0.0)
    if case == "B2":
        return CaseSpec(case="B2", layer="L1", entry_mode="targetpercent", cost_rate=0.0)
    if case == "B3":
        return CaseSpec(case="B3", layer="L2", entry_mode="orders", cost_rate=0.001)
    if case == "B4":
        return CaseSpec(case="B4", layer="L3", entry_mode="orders", cost_rate=0.0, top_n=2)
    if case == "B5":
        # B1 数据；V3 侧阴性对照：基线 0.001 + 扰动 0.001 → 有效 0.002（F-S9-P015-5：
        # vbt 现金约束下 fees>0 的 vbt↔spec 全等结构性不可达，阴性对照移至 V3 侧）
        return CaseSpec(
            case="B5", layer="NegCtl", entry_mode="v3_only", cost_rate=0.002, fees_perturb=0.001
        )
    raise ValueError(f"未知 case: {case}（合法值 B1-B5）")


def _sin_close(base: list[float], t: int, phases: list[float]) -> np.ndarray:
    """确定性波动价：base × (1 + 0.01 × sin(0.7·i + phase))，恒正。"""
    i = np.arange(t, dtype=float)
    cols = [b * (1.0 + 0.01 * np.sin(0.7 * i + p)) for b, p in zip(base, phases)]
    return np.column_stack(cols)


def build_data(spec: CaseSpec) -> tuple[pd.DataFrame, pd.DataFrame, list[int]]:
    """返回 (close_df, factor_df, reb_days)。日期用 ISO 字符串索引（跨 pandas 版本安全）。"""
    if spec.case in ("B1", "B5"):
        t, codes = 5, _CASES_2
        close = np.full((t, 2), np.nan)
        close[:, 0], close[:, 1] = 10.0, 25.0
        factor = np.tile(np.array([1.0, 2.0]), (t, 1))
    elif spec.case == "B2":
        t, codes = 6, _CASES_2
        close = _sin_close([10.0, 25.0], t, [0.0, 1.1])
        factor = np.tile(np.array([1.0, 2.0]), (t, 1))
    elif spec.case == "B3":
        t, codes = 4, _CASES_2
        close = _sin_close([10.0, 25.0], t, [0.0, 1.1])
        factor = np.tile(np.array([1.0, 2.0]), (t, 1))
    elif spec.case == "B4":
        t, codes = 6, _CASES_4
        # 常量价：规避 V3「无现金约束」（last_pv 定规模 + 持仓升值 → 超现金补仓）
        # 与 vectorbt「现金不足拒单」的语义冲突（F-S9-P015-2，DESIGN §5 预案②）
        close = np.tile(np.array([8.0, 12.0, 18.0, 26.0]), (t, 1))
        # 翻转日 i=3：变序不变值域（互异 → 无 abs>=threshold 并列超选）
        factor = np.empty((t, 4))
        factor[:3] = np.array([1.0, 2.0, 3.0, 4.0])
        factor[3:] = np.array([4.0, 3.0, 2.0, 1.0])
    else:  # pragma: no cover — get_case 已拦截
        raise ValueError(spec.case)
    dates = pd.date_range("2024-01-02", periods=t, freq="B").strftime("%Y-%m-%d")
    close_df = pd.DataFrame(close, index=dates, columns=codes)
    factor_df = pd.DataFrame(factor, index=dates, columns=codes)
    reb_days = [i for i in range(1, t) if i % spec.reb_freq == 0]
    return close_df, factor_df, reb_days


def select_top(signal_row: np.ndarray, top_n: int) -> np.ndarray:
    """V3 选股规则规格（engine_v3_vector.py:112-118 逐字翻译）。"""
    s = np.nan_to_num(signal_row, nan=0.0)
    if len(s) <= top_n:
        return s > 0
    abs_s = np.abs(s)
    threshold = abs_s[np.argpartition(abs_s, -top_n)[-top_n]]
    return abs_s >= threshold


def _simulate(close: np.ndarray, factor: np.ndarray, spec: CaseSpec, size_on: str) -> dict:
    """规格模拟器。

    size_on="last_pv"     → V3 内核语义：目标值 = 前一日组合价值 / n_sel（:128）
    size_on="current_nav" → vectorbt targetpercent 语义：目标值 = 当日盯市值 / n_sel
    """
    t, n = close.shape
    qty = np.zeros((t, n))
    cash = np.full(t, INIT_CASH, dtype=float)
    pv = np.zeros(t)
    trades = np.zeros((t, n))
    costs = np.zeros(t)
    pv[0] = cash[0]
    for i in range(1, t):
        qty[i] = qty[i - 1]
        cash[i] = cash[i - 1]
        if i % spec.reb_freq == 0:
            mask = select_top(factor[i], spec.top_n)
            n_sel = int(mask.sum())
            if n_sel == 0:
                pv[i] = cash[i] + float(np.sum(qty[i] * close[i]))
                continue
            if size_on == "last_pv":
                sizing_value = pv[i - 1]
            else:  # current_nav：现金不变，持仓按当日收盘盯市
                sizing_value = cash[i - 1] + float(np.sum(qty[i - 1] * close[i]))
            target = np.zeros(n)
            for j in range(n):
                if mask[j] and close[i, j] > 0:
                    target[j] = sizing_value * (1.0 / n_sel) / close[i, j]
            trade = target - qty[i - 1]
            cost = float(np.sum(np.abs(trade) * close[i]) * spec.cost_rate)
            cash[i] = cash[i - 1] - float(np.sum(trade * close[i])) - cost
            qty[i] = target
            trades[i] = trade
            costs[i] = cost
        pv[i] = cash[i] + float(np.sum(qty[i] * close[i]))
    return {"qty": qty, "cash": cash, "pv": pv, "trades": trades, "costs": costs}


def simulate_v3_spec(close: np.ndarray, factor: np.ndarray, spec: CaseSpec) -> dict:
    """V3 侧声明规格（G1 / I2a 断言对象）。"""
    return _simulate(close, factor, spec, size_on="last_pv")


def simulate_vbt_spec(close: np.ndarray, factor: np.ndarray, spec: CaseSpec) -> dict:
    """vectorbt targetpercent 侧声明规格（I2b 断言对象，仅 B2 使用）。"""
    return _simulate(close, factor, spec, size_on="current_nav")


def i2c_closed_form(
    close: np.ndarray, spec_v3_res: dict, spec_vbt_res: dict, n_sel: int
) -> np.ndarray:
    """I2c 声明差异闭式·一般式（F-S9-P015-4 修正，DESIGN §3.2）：

        Δ_j[i] = (V_cur_vbt[i] − pv_v3[i-1]) / (n_sel × P[i,j])
        V_cur_vbt[i]  = cash_vbt[i-1] + Σ_k qty_vbt[i-1,k]·P[i,k]   （current-NAV 规格）
        pv_v3[i-1]    = cash_v3[i-1] + Σ_k qty_v3[i-1,k]·P[i-1,k]   （last_pv 规格）

    原简单式（Σ_k qty[i-1,k]·ΔP[i,k]）仅在两侧路径重合的首个分叉日精确；
    路径分叉后两侧各自的现金/持仓路径进入闭式输入。
    """
    t, n = close.shape
    out = np.zeros((t, n))
    for i in range(1, t):
        v_cur_vbt = spec_vbt_res["cash"][i - 1] + float(
            np.sum(spec_vbt_res["qty"][i - 1] * close[i])
        )
        d_value = v_cur_vbt - spec_v3_res["pv"][i - 1]
        for j in range(n):
            out[i, j] = d_value / (n_sel * close[i, j])
    return out


def write_meta(
    case_dir: Path, spec: CaseSpec, codes: list[str], t: int, reb_days: list[int]
) -> None:
    meta = {
        "case": spec.case,
        "layer": spec.layer,
        "entry_mode": spec.entry_mode,
        "cost_rate": spec.cost_rate,
        "fees_perturb": spec.fees_perturb,
        "reb_freq": spec.reb_freq,
        "top_n": spec.top_n,
        "n_stocks": len(codes),
        "t": t,
        "codes": codes,
        "reb_days": reb_days,
        "init_cash": INIT_CASH,
        "spec_version": SPEC_VERSION,
        "rtol": RTOL,
        "money_atol": MONEY_ATOL,
    }
    (case_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_meta(case_dir: Path) -> tuple[CaseSpec, dict]:
    raw = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    if raw.get("spec_version") != SPEC_VERSION:
        raise ValueError(f"spec_version 不匹配: {raw.get('spec_version')} != {SPEC_VERSION}")
    spec = CaseSpec(
        case=raw["case"],
        layer=raw["layer"],
        entry_mode=raw["entry_mode"],
        cost_rate=raw["cost_rate"],
        fees_perturb=raw.get("fees_perturb", 0.0),
        reb_freq=raw["reb_freq"],
        top_n=raw["top_n"],
    )
    return spec, raw
