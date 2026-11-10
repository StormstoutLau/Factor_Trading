"""P-015 verify_p015：读两侧结果 → 断言恒等式 I1-I5 → 写报告（主环境运行）。

用法:
    python scripts/external_benchmark/verify_p015.py --case-dir <dir1> [dir2 ...] --report docs/APPENDIX_p015_external_calibration.md

断言组（DESIGN §3）:
- G1（全 case）: V3 == V3 规格（I1 / I2a / I3 前半 / I4）
- G2 orders 模式: vectorbt == V3 规格（I1 / I4）；费用闭式（I3）；B5 阴性对照（I5）
- G2 targetpercent 模式（B2）: vectorbt == current-NAV 规格（I2b）；I2c 闭式差异
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from _spec import (
    INIT_CASH,
    MONEY_ATOL,
    RTOL,
    i2c_closed_form,
    load_meta,
    simulate_v3_spec,
    simulate_vbt_spec,
)

_STATUS_LABEL = {"pass": "PASS", "fail": "FAIL", "waiver": "WAIVER(非断言)"}


class Checks:
    """检查记录器：三态 ``pass / fail / waiver``（P-016 D1 / F-R5-P015-2）。

    ``waiver`` 是**豁免登记**而非断言——不计入断言数、不计入失败数，
    报告渲染为「— 豁免（非断言）」。这样既保留登记可见性，又不在形式上
    制造「恒真即通过」。
    """

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, cid: str, case: str, desc: str, ok: bool, detail: str) -> None:
        self._push(cid, case, desc, "pass" if ok else "fail", detail)

    def waive(self, cid: str, case: str, desc: str, detail: str) -> None:
        """登记豁免（非断言）：保留可见性，不参与通过/失败判定。"""
        self._push(cid, case, desc, "waiver", detail)

    def _push(self, cid: str, case: str, desc: str, status: str, detail: str) -> None:
        self.rows.append(
            {"id": cid, "case": case, "desc": desc, "status": status, "detail": detail}
        )
        print(f"[verify] {cid} [{case}] {_STATUS_LABEL[status]} — {desc} | {detail}")

    def finalize(self) -> int:
        n_assert = sum(1 for r in self.rows if r["status"] != "waiver")
        n_fail = sum(1 for r in self.rows if r["status"] == "fail")
        n_waive = sum(1 for r in self.rows if r["status"] == "waiver")
        print(f"[verify] 共 {n_assert} 项断言（失败 {n_fail} 项）+ 豁免登记 {n_waive} 项")
        return 0 if n_fail == 0 else 1


def _maxdiff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))))


def _close(a: np.ndarray, b: np.ndarray, rtol: float, atol: float) -> bool:
    return bool(np.allclose(a, b, rtol=rtol, atol=atol))


def verify_case(case_dir: Path, checks: Checks) -> None:
    spec, meta = load_meta(case_dir)
    case = spec.case
    close = pd.read_csv(case_dir / "close.csv", index_col=0).values
    factor = pd.read_csv(case_dir / "factor.csv", index_col=0).values
    v3 = pd.read_csv(case_dir / "v3_results.csv", index_col=0)
    qty_v3 = v3[[c for c in v3.columns if c.startswith("qty_")]].values
    cash_v3, pv_v3 = v3["cash"].values, v3["pv"].values

    spec_v3 = simulate_v3_spec(close, factor, spec)

    # ---- G1: V3 == V3 规格（逐日全矩阵）----
    ok_q = _close(qty_v3, spec_v3["qty"], RTOL, 0.0)
    checks.add(
        "G1.qty",
        case,
        "V3 逐日持仓 == 规格（rtol=1e-12）",
        ok_q,
        f"max|Δ|={_maxdiff(qty_v3, spec_v3['qty']):.3e}",
    )
    ok_c = _close(cash_v3, spec_v3["cash"], 0.0, MONEY_ATOL)
    checks.add(
        "G1.cash",
        case,
        "V3 逐日现金 == 规格（money_atol=1e-6）",
        ok_c,
        f"max|Δ|={_maxdiff(cash_v3, spec_v3['cash']):.3e}",
    )
    ok_p = _close(pv_v3, spec_v3["pv"], 0.0, MONEY_ATOL)
    checks.add(
        "G1.pv", case, "V3 逐日净值 == 规格", ok_p, f"max|Δ|={_maxdiff(pv_v3, spec_v3['pv']):.3e}"
    )

    vbt_res_path = case_dir / "vbt_results.csv"
    if spec.entry_mode == "v3_only":
        checks.waive(
            "G2",
            case,
            "vectorbt 侧按 meta 豁免（v3_only：F-S9-P015-5 现金约束语义差）",
            "I5 阴性对照移至 V3 侧（跨 case 断言）",
        )
        return pv_v3
    if not vbt_res_path.exists():
        checks.add(
            "G2", case, "vectorbt 侧结果存在", False, "vbt_results.csv 缺失（venv 侧未运行）"
        )
        return

    vbt = pd.read_csv(vbt_res_path, index_col=0)
    qty_vbt = vbt[[c for c in vbt.columns if c.startswith("qty_")]].values
    cash_vbt, pv_vbt = vbt["cash"].values, vbt["pv"].values

    if spec.entry_mode == "orders":
        if spec.cost_rate == 0.0:
            # ---- G2: vectorbt == V3 规格（零费用：orders 记账全等，B1/B4）----
            ok_q2 = _close(qty_vbt, spec_v3["qty"], RTOL, 0.0)
            checks.add(
                "G2.qty",
                case,
                "vectorbt 逐日持仓 == 规格",
                ok_q2,
                f"max|Δ|={_maxdiff(qty_vbt, spec_v3['qty']):.3e}",
            )
            ok_c2 = _close(cash_vbt, spec_v3["cash"], 0.0, MONEY_ATOL)
            checks.add(
                "G2.cash",
                case,
                "vectorbt 逐日现金 == 规格",
                ok_c2,
                f"max|Δ|={_maxdiff(cash_vbt, spec_v3['cash']):.3e}",
            )
            ok_p2 = _close(pv_vbt, spec_v3["pv"], 0.0, MONEY_ATOL)
            checks.add(
                "G2.pv",
                case,
                "vectorbt 逐日净值 == 规格",
                ok_p2,
                f"max|Δ|={_maxdiff(pv_vbt, spec_v3['pv']):.3e}",
            )
        # ---- I3-1: vectorbt 费用模型一致性（对已执行订单；rate>0 时 vbt↔spec 全等
        # 因现金约束结构性不可达 → F-S9-P015-2/5，改验费用记账闭式）----
        if (
            case_dir.joinpath("vbt_orders.csv").exists()
            and (spec.cost_rate + spec.fees_perturb) > 0
        ):
            orders = pd.read_csv(case_dir / "vbt_orders.csv")
            fees_vbt = float(orders["Fees"].sum())
            executed_value = float((orders["Size"].abs() * orders["Price"]).sum())
            fees_rate = spec.cost_rate + spec.fees_perturb
            ok_f = abs(executed_value * fees_rate - fees_vbt) <= MONEY_ATOL
            checks.add(
                "I3.fees",
                case,
                "vectorbt 费用 == Σ|executed|×P×rate（费用模型一致性）",
                ok_f,
                f"executed_value={executed_value:.4f} fees_vbt={fees_vbt:.6f}",
            )
            # 缺口登记（非断言）：请求 vs 执行的价值差 = V3 费用透支现金的不可复现部分
            request_value = float(np.sum(np.abs(spec_v3["trades"]) * close))
            print(
                f"[verify] [缺口登记] {case}: request_value={request_value:.4f} "
                f"executed_value={executed_value:.4f} gap={request_value - executed_value:.4f}"
            )
        elif case_dir.joinpath("vbt_orders.csv").exists():
            orders = pd.read_csv(case_dir / "vbt_orders.csv")
            fees_vbt = float(orders["Fees"].sum())
            checks.add(
                "I3.fees",
                case,
                "零费用 case 费用合计 == 0",
                abs(fees_vbt) <= MONEY_ATOL,
                f"fees={fees_vbt:.6f}",
            )
    else:
        # ---- I2b: vectorbt == current-NAV 规格 ----
        spec_vbt = simulate_vbt_spec(close, factor, spec)
        ok_q2 = _close(qty_vbt, spec_vbt["qty"], RTOL, 0.0)
        checks.add(
            "I2b.qty",
            case,
            "vectorbt 逐日持仓 == current-NAV 规格",
            ok_q2,
            f"max|Δ|={_maxdiff(qty_vbt, spec_vbt['qty']):.3e}",
        )
        ok_p2 = _close(pv_vbt, spec_vbt["pv"], 0.0, MONEY_ATOL)
        checks.add(
            "I2b.pv",
            case,
            "vectorbt 逐日净值 == current-NAV 规格",
            ok_p2,
            f"max|Δ|={_maxdiff(pv_vbt, spec_vbt['pv']):.3e}",
        )

        # ---- I2c: 声明差异闭式（一般式，F-S9-P015-4）----
        n_sel = meta["n_stocks"]
        closed = i2c_closed_form(close, spec_v3, spec_vbt, n_sel)
        diff = qty_vbt - qty_v3
        ok_i2c = _close(diff, closed, RTOL, 0.0)
        checks.add(
            "I2c.diff",
            case,
            "qty_vbt − qty_v3 == 声明闭式（last_pv vs current-NAV 规模差）",
            ok_i2c,
            f"max|Δ|={_maxdiff(diff, closed):.3e}",
        )
    return pv_v3


def cross_case_checks(checks: Checks, pv_by_case: dict[str, np.ndarray]) -> None:
    """跨 case 断言：I5 阴性对照（V3 侧费用扰动，F-S9-P015-5）。

    B5 与 B3 同数据；B5 有效费率 0.002 = B3 0.001 + 扰动 0.001。
    常量价单笔建仓下 pv[1] = init×(1−rate) → 差 = −init×0.001 精确成立。
    """
    if "B3" not in pv_by_case or "B5" not in pv_by_case:
        checks.add("I5.negctl", "B3×B5", "V3 侧费用扰动偏移", False, "B3/B5 case 未齐")
        return
    offset = float(pv_by_case["B5"][1] - pv_by_case["B3"][1])
    expected = -INIT_CASH * 0.001
    ok_n = abs(offset - expected) <= MONEY_ATOL
    checks.add(
        "I5.negctl",
        "B3×B5",
        "V3 费用扰动偏移 == −init_cash×perturb（灵敏度自证）",
        ok_n,
        f"offset={offset:.6f} expected={expected:.6f}",
    )


_REPORT_MARK = {"pass": "✅ PASS", "fail": "❌ FAIL", "waiver": "— 豁免（非断言）"}

# 人工回填章节标记（P-016 D2 / F-S9-P016-1）：命中即视为「策展报告」，生成器改名写入
MANUAL_MARKERS = ("## 1. vectorbt 权威签名核验", "## 3. 口径映射实测结论")

# 生成物命名空间（P-017 D3 / F-R5-P016-3）：``<stem>.generated<suffix>`` 归生成器独占，
# 该路径内容随时可被原地重写；人工策展须合并回主文件，不得直接编辑生成物。
GENERATED_SUFFIX = ".generated"


def _resolve_report_target(path: Path) -> Path:
    """解析报告写入目标（四分支）。

    1. 目标不存在 → 原地写入；
    2. 目标本身是生成物（**name 或 stem** 以 ``.generated`` 结尾——无扩展名时 stem 会剥离后缀）→ **原地重写**，不再级联改名
       （P-017 / F-R5-P016-3：旧行为会产出 ``.generated.generated.md``）；
    3. 目标含人工章节标记（策展版）→ 改名 ``<stem>.generated<suffix>``，原文件不动；
    4. 存在但无人工标记的外部文件 → 原地覆盖。
    """
    if not path.exists():
        return path
    if path.name.endswith(GENERATED_SUFFIX) or path.stem.endswith(GENERATED_SUFFIX):
        return path
    text = path.read_text(encoding="utf-8")
    if any(marker in text for marker in MANUAL_MARKERS):
        return path.with_name(f"{path.stem}{GENERATED_SUFFIX}{path.suffix}")
    return path


def write_report(path: Path, checks: Checks) -> None:
    lines = [
        "# APPENDIX：P-015 外部对拍校准报告（VectorBT 1.2.0 ↔ V3）",
        "",
        "> 生成物：`verify_p015.py` 自动产出（P-015 · T-4）。复放命令见 §4。",
        "> 「— 豁免（非断言）」行是豁免登记，不计入断言数（P-016 D1）。",
        "",
        "## 1. vectorbt 权威签名核验（U-P015-3）",
        "",
        "```",
        "（T-1.4 读数回填区：inspect.signature 读数，venv 建成后立即执行）",
        "```",
        "",
        "## 2. 恒等式逐条读数",
        "",
        "| ID | case | 断言 | 结果 | 读数 |",
        "|----|------|------|------|------|",
    ]
    for r in checks.rows:
        lines.append(
            f"| {r['id']} | {r['case']} | {r['desc']} | {_REPORT_MARK[r['status']]} | {r['detail']} |"
        )
    lines += [
        "",
        "## 3. 口径映射实测结论",
        "",
        "（T-4 回填区：I2c 语义差异 → BACKTEST_CALIBER_MAPPING §2.2 实测列）",
        "",
        "## 4. 复放命令",
        "",
        "```bash",
        "# venv 重建（一次性）",
        "python -m venv .venv-vbt",
        ".venv-vbt/Scripts/python.exe -m pip install -r scripts/external_benchmark/requirements-vectorbt.txt",
        "# case 全链复放",
        "# python scripts/external_benchmark/export_case.py --case B1 --out-dir .tmp_p015_cases/B1  （逐 case）",
        "# .venv-vbt/Scripts/python.exe scripts/external_benchmark/run_vectorbt.py --case-dir .tmp_p015_cases/B1",
        "# python scripts/external_benchmark/verify_p015.py --case-dir .tmp_p015_cases/B1 ...",
        "```",
        "",
    ]
    target = _resolve_report_target(path)
    if target != path:
        print(
            f"[verify] [保护] {path.name} 含人工章节（§1/§3），改写 {target.name}；"
            "请人工比对 §2 读数后再合并"
        )
    # 父目录缺失时自动创建（P-019 D1 / F-R5-P018-1）；权限类失败仍照常抛出
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"[verify] 报告已写入 {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True, nargs="+", type=Path)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    checks = Checks()
    pv_by_case: dict[str, np.ndarray] = {}
    for case_dir in args.case_dir:
        pv = verify_case(case_dir, checks)
        if pv is not None:
            meta = load_meta(case_dir)[0]
            pv_by_case[meta.case] = pv
    cross_case_checks(checks, pv_by_case)
    if args.report is not None:
        write_report(args.report, checks)
    return checks.finalize()


if __name__ == "__main__":
    sys.exit(main())
