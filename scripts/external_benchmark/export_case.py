"""P-015 export_case：构造对拍 case → 跑 V3 → 导出 case 目录（主环境运行）。

用法:
    python scripts/external_benchmark/export_case.py --case B1 --out-dir .tmp_p015_cases/B1

导出五件套: meta.json / close.csv / factor.csv / spec_orders.csv / v3_results.csv
- spec_orders.csv: 规格增量订单（NaN = 无订单），供 venv 侧 from_orders
- v3_results.csv:  V3 公共 API 端到端输出（cash / pv / qty_*）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from _spec import INIT_CASH, get_case, build_data, simulate_v3_spec, write_meta

from core.data_v3 import DataLoaderV3
from core.engine_v3_vector import VectorBacktestEngine


def export(case: str, out_dir: Path) -> None:
    spec = get_case(case)
    close_df, factor_df, reb_days = build_data(spec)
    codes = list(close_df.columns)
    t = len(close_df)
    out_dir.mkdir(parents=True, exist_ok=True)

    loader = DataLoaderV3.from_pandas_dataframes(
        close=close_df,
        open=close_df,
        high=close_df,
        low=close_df,
        factor_dict={"factor": factor_df},
    )
    engine = VectorBacktestEngine(
        {
            "initial_capital": INIT_CASH,
            "top_n": spec.top_n,
            "rebalance_freq": spec.reb_freq,
            "cost_rate": spec.cost_rate,
        }
    )
    engine.setup(loader)
    engine.run()

    qty = np.asarray(engine.get_positions(), dtype=float)
    cash = np.asarray(getattr(engine, "_cash"), dtype=float)
    pv = np.asarray(engine.get_portfolio_value(), dtype=float)

    # 自检：现金派生式 vs 私有字段（校准脚本专用访问，口径见 IMPL T-2.1）
    cash_derived = pv - np.sum(qty * close_df.values, axis=1)
    cash_gap = float(np.max(np.abs(cash - cash_derived)))
    print(f"[export:{case}] 现金派生自检 max|Δcash| = {cash_gap:.3e}")
    if cash_gap > 1e-6:
        raise AssertionError(f"V3 现金派生不一致: {cash_gap}")

    v3_df = pd.DataFrame({"cash": cash, "pv": pv}, index=close_df.index)
    for j, code in enumerate(codes):
        v3_df[f"qty_{code}"] = qty[:, j]

    spec_res = simulate_v3_spec(close_df.values, factor_df.values, spec)
    # 规格增量订单：0 → NaN（from_orders 跳过 NaN）
    orders_df = pd.DataFrame(spec_res["trades"], index=close_df.index, columns=codes)
    orders_df = orders_df.mask(orders_df == 0.0)

    write_meta(out_dir, spec, codes, t, reb_days)
    close_df.to_csv(out_dir / "close.csv")
    factor_df.to_csv(out_dir / "factor.csv")
    orders_df.to_csv(out_dir / "spec_orders.csv")
    v3_df.to_csv(out_dir / "v3_results.csv")
    print(
        f"[export:{case}] 五件套落盘 {out_dir}（close checksum = {float(np.sum(close_df.values)):.17g}）"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=["B1", "B2", "B3", "B4", "B5"])
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    export(args.case, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
