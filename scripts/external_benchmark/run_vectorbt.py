"""P-015 run_vectorbt：读 case 目录 → vectorbt 对拍 → 写 vbt_results/vbt_orders（venv 内运行）。

用法:
    .venv-vbt/Scripts/python.exe scripts/external_benchmark/run_vectorbt.py --case-dir .tmp_p015_cases/B1

依赖隔离 venv（vectorbt 1.2.0 自带 pandas 3.x；主环境 pandas 2.2.3 与之冲突，
故走 CSV 文件交换 —— RESEARCH F2 / DESIGN D3）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import vectorbt as vbt

from _spec import INIT_CASH, load_meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True, type=Path)
    args = parser.parse_args()
    case_dir = args.case_dir

    spec, meta = load_meta(case_dir)
    close = pd.read_csv(case_dir / "close.csv", index_col=0)
    close.index = pd.to_datetime(close.index)

    # U-P015-2 跨 pandas 往返自检：读回值与导出侧 checksum 对账（checksum 由 export 打印、
    # verify 复算对账；此处再验 shape/NaN/正值）
    assert close.shape == (meta["t"], meta["n_stocks"]), f"close shape {close.shape}"
    assert not close.isna().any().any(), "close 含 NaN"
    assert float((close.values > 0).all()), "close 含非正值"
    print(
        f"[run_vectorbt:{spec.case}] 读回自检 shape ok，checksum = {float(np.sum(close.values)):.17g}"
    )

    codes = list(close.columns)
    fees = spec.cost_rate + spec.fees_perturb

    if spec.entry_mode == "v3_only":
        # F-S9-P015-5：B5 阴性对照仅在 V3 侧（cost_rate 扰动 0.001→0.002），
        # vbt 不参与；本脚本对 v3_only case 无操作
        print(f"[run_vectorbt:{spec.case}] entry_mode=v3_only，跳过 vbt 侧")
        return 0

    if spec.entry_mode == "orders":
        size = pd.read_csv(case_dir / "spec_orders.csv", index_col=0)
        size.index = pd.to_datetime(size.index)
        size = size.reindex(index=close.index, columns=codes)
        pf = vbt.Portfolio.from_orders(
            close=close,
            size=size,
            size_type="amount",
            price=close,
            fees=fees,
            init_cash=INIT_CASH,
            cash_sharing=True,
            group_by=True,
            call_seq="auto",
        )
    elif spec.entry_mode == "targetpercent":
        # F-S9-P015-1：1.2.0 免费版 from_signals 不支持 TargetPercent
        # （nb.py:1771 "Only Amount/Value/Percent supported"）→ 改 from_orders 路径
        size = pd.DataFrame(np.nan, index=close.index, columns=codes)
        for i in meta["reb_days"]:
            size.iloc[i] = 1.0 / meta["n_stocks"]
        pf = vbt.Portfolio.from_orders(
            close=close,
            size=size,
            size_type="targetpercent",
            price=close,
            fees=fees,
            init_cash=INIT_CASH,
            cash_sharing=True,
            group_by=True,
            call_seq="auto",
        )
    else:  # pragma: no cover — meta 校验兜底
        raise ValueError(f"entry_mode 非法: {spec.entry_mode}")

    # 提取逐日会计量：value / cash / qty
    pv = np.asarray(pf.value(), dtype=float)
    cash_df = pf.cash()
    cash = (
        np.asarray(cash_df.iloc[:, 0], dtype=float)
        if isinstance(cash_df, pd.DataFrame)
        else np.asarray(cash_df, dtype=float)
    )
    qty_df = pf.asset_flow()  # 1.2.0 无 asset_qty：逐日订单量，累计即持仓
    qty = (
        np.asarray(qty_df, dtype=float)
        if isinstance(qty_df, pd.DataFrame)
        else np.asarray(qty_df, dtype=float)
    )
    qty = np.atleast_2d(qty)
    if qty.shape != close.shape:  # 单列时 vbt 可能返回 1D
        qty = np.broadcast_to(qty.reshape(-1, 1), close.shape).copy()
    qty = np.cumsum(qty, axis=0)

    res = pd.DataFrame({"cash": cash, "pv": pv}, index=close.index)
    for j, code in enumerate(codes):
        res[f"qty_{code}"] = qty[:, j]
    res.to_csv(case_dir / "vbt_results.csv")

    orders = pf.orders.records_readable
    keep = [
        c
        for c in ("Order Id", "Timestamp", "Column", "Size", "Price", "Fees", "Status")
        if c in orders.columns
    ]
    orders[keep].to_csv(case_dir / "vbt_orders.csv", index=False)
    n_rejected = (
        int((orders["Status"].astype(str) != "Filled").sum()) if "Status" in orders.columns else 0
    )
    print(
        f"[run_vectorbt:{spec.case}] orders={len(orders)} rejected={n_rejected} "
        f"pv_last={float(pv[-1]):.6f} qty_last={qty[-1].tolist()}"
    )
    if n_rejected:
        print(f"[run_vectorbt:{spec.case}] [警告] 存在非 Filled 订单，恒等式预期破裂")
    return 0


if __name__ == "__main__":
    sys.exit(main())
