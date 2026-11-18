"""P-045 verify_p045：本仓 ``apply_stops`` 与 vectorbt 1.2.0 触发判定序列对拍。

用法（隔离 venv ``.venv-vbt``，含 ``vectorbt==1.2.0``）::

    .\\.venv-vbt\\Scripts\\python.exe scripts\\external_benchmark\\verify_p045.py

口径（DESIGN I3 / F-S2-P045-1 / F-S6-P045-1）:

- **断言**：``P045_S1`` 的**触发判定序列**（date, code）逐值一致；SL 优先于 TP 由
  vbt 退出价间接断言（C 若判 TP 则退出价为 120，实测 90）。
- **豁免（waiver，非断言）**：``reason`` 字段（免费版 trades/orders 无该列）、
  成交价与 NAV（vbt 以触发价成交 vs 本仓触发日归零 + T+1 开盘成交）、
  trailing 幅度（vbt ``sl_trail=True`` 复用 ``sl_stop=0.10``；本仓 ``trailing_stop_pct=0.08``）、
  激活阈值（免费版无 ``tsl_th``，本仓 ``trailing_activate_pct=0.05``）。

本脚本在**隔离 venv** 内运行，不能 ``import core.stops``（会触发 ``core/__init__``
的第三方重依赖）；改用 importlib 按文件路径加载。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

import pandas as pd

GOLDEN = REPO_ROOT / "tests" / "golden" / "p045" / "P045_S1.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "APPENDIX_p045_external_calibration.md"
_BAR_KEYS = ("open", "high", "low", "close")
_STATUS_LABEL = {"pass": "PASS", "fail": "FAIL", "waiver": "WAIVER(非断言)"}


class Checks:
    """检查记录器：三态 ``pass / fail / waiver``（沿用 P-015 D1 / F-R5-P015-2）。"""

    def __init__(self) -> None:
        self.rows: list[dict[str, str]] = []

    def add(self, cid: str, desc: str, ok: bool, detail: str) -> None:
        self._push(cid, desc, "pass" if ok else "fail", detail)

    def waive(self, cid: str, desc: str, detail: str) -> None:
        """登记豁免（非断言）：保留可见性，不参与通过/失败判定。"""
        self._push(cid, desc, "waiver", detail)

    def _push(self, cid: str, desc: str, status: str, detail: str) -> None:
        self.rows.append({"id": cid, "desc": desc, "status": status, "detail": detail})
        print(f"[verify] {cid} {_STATUS_LABEL[status]} — {desc} | {detail}")

    def finalize(self) -> int:
        n_assert = sum(1 for r in self.rows if r["status"] != "waiver")
        n_fail = sum(1 for r in self.rows if r["status"] == "fail")
        n_waive = sum(1 for r in self.rows if r["status"] == "waiver")
        print(f"[verify] 共 {n_assert} 项断言（失败 {n_fail} 项）+ 豁免登记 {n_waive} 项")
        return 0 if n_fail == 0 else 1


def _load_repo_stops() -> ModuleType:
    """按文件路径加载 ``core/stops.py``（绕过 ``core/__init__`` 重依赖）。"""
    path = REPO_ROOT / "core" / "stops.py"
    spec = importlib.util.spec_from_file_location("p045_stops_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses 内部依赖 sys.modules[cls.__module__]，必须先注册再 exec
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _side_frames(
    payload: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DatetimeIndex, list[str], dict[str, pd.DataFrame]]:
    dates = pd.DatetimeIndex(payload["targets"]["dates"])
    codes = list(payload["targets"]["codes"])
    targets = pd.DataFrame(payload["targets"]["values"], index=dates, columns=codes)
    bars = {
        key: pd.DataFrame(payload["bars"][key], index=dates, columns=codes) for key in _BAR_KEYS
    }
    return targets, dates, codes, bars


def _repo_triggers(payload: dict[str, Any], stops: ModuleType) -> list[tuple[str, str, str]]:
    targets, dates, codes, bars = _side_frames(payload)
    tradable = None
    if payload["tradable"] is not None:
        tradable = pd.DataFrame(payload["tradable"], index=dates, columns=codes).astype(bool)
    result = stops.apply_stops(
        targets, bars, stops.StopConfig(**payload["config"]), tradable=tradable
    )
    return [(t.date.strftime("%Y-%m-%d"), t.code, t.reason) for t in result.triggers]


def _vbt_exits(
    payload: dict[str, Any], dates: pd.DatetimeIndex, code: str, j: int
) -> tuple[str, float, str]:
    import vectorbt as vbt

    bars = {
        key: pd.Series([row[j] for row in payload["bars"][key]], index=dates, dtype=float)
        for key in _BAR_KEYS
    }
    entries = pd.Series(False, index=dates)
    entries.iloc[0] = True
    exits = pd.Series(False, index=dates)
    config = payload["config"]
    portfolio = vbt.Portfolio.from_signals(
        bars["close"],
        entries,
        exits,
        open=bars["open"],
        high=bars["high"],
        low=bars["low"],
        sl_stop=config["stop_loss_pct"],
        tp_stop=config["take_profit_pct"],
        sl_trail=True,
        fees=0.0,
        init_cash=100000.0,
        freq="1D",
    )
    records = portfolio.trades.records
    if len(records) != 1:
        return "MULTI_OR_NONE", float("nan"), str(len(records))
    exit_idx = int(records["exit_idx"].iloc[0])
    exit_price = float(records["exit_price"].iloc[0])
    return dates[exit_idx].strftime("%Y-%m-%d"), exit_price, "ok"


def _render(
    checks: Checks, repo: list[tuple[str, str, str]], vbt_rows: list[tuple[str, str, float]]
) -> str:
    lines = [
        "# 附录：P-045 外部对拍校准（vectorbt 1.2.0）",
        "",
        "> **批次**: P-045（timing + stops）· **执行载体**: `scripts/external_benchmark/verify_p045.py`",
        "> **环境**: 隔离 venv `.venv-vbt`（`vectorbt==1.2.0` / `pandas==3.1.1`）· **输入**: `tests/golden/p045/P045_S1.json`",
        "> **口径**: 触发判定序列逐值（DESIGN I3，F-S2-P045-1 收窄；F-S6-P045-1 落点）；成交/NAV 差异闭式声明（P-015 恒等式方法论）",
        "",
        "## 1. 读数",
        "",
        "| 侧 | (date, code, reason/price) |",
        "|----|----------------------------|",
    ]
    for date, code, reason in repo:
        lines.append(f"| 本仓 `apply_stops` | `{date}` / `{code}` / `{reason}` |")
    for date, code, price in vbt_rows:
        lines.append(
            f"| vbt `from_signals` | `{date}` / `{code}` / exit_price `{price}`（无 reason 列） |"
        )
    lines += [
        "",
        "## 2. 断言与豁免",
        "",
        "| ID | 项 | 状态 | 读数 |",
        "|----|----|------|------|",
    ]
    marks = {"pass": "✅ PASS", "fail": "❌ FAIL", "waiver": "— 豁免（非断言）"}
    for row in checks.rows:
        lines.append(f"| {row['id']} | {row['desc']} | {marks[row['status']]} | {row['detail']} |")
    n_assert = sum(1 for r in checks.rows if r["status"] != "waiver")
    n_fail = sum(1 for r in checks.rows if r["status"] == "fail")
    n_waive = sum(1 for r in checks.rows if r["status"] == "waiver")
    lines += [
        "",
        f"**汇总**: {n_assert} 项断言（失败 {n_fail}）+ {n_waive} 项豁免登记；"
        f"退出码 **{0 if n_fail == 0 else 1}**。",
        "",
        "## 3. 差异闭式声明（waiver 展开）",
        "",
        "| # | 差异 | 闭式说明 |",
        "|---|------|----------|",
        "| 1 | `reason` 不可比 | vbt 1.2.0 免费版 `trades` / `orders` 记录均无止损类型字段（实测列：`id/col/size/entry_idx/...`）；"
        "本仓 reason 由 V5/V6 单测与 G1/G2 golden 锁定 |",
        "| 2 | 成交价模型 | vbt 在触发 bar 以**触发价**成交（C 实测 90.0，而非当日 close 100.0）；"
        "本仓 `exit_price_ref` 记触发日 close 仅作审计，真实成交由既有链 T+1 开盘完成（无前视，I5） |",
        "| 3 | trailing 幅度 | vbt `sl_trail=True` 将 `sl_stop=0.10` 复用为跟踪幅度（B 实测退出价 47.7 = 53×0.9）；"
        "本仓 `trailing_stop_pct=0.08`（阈值 48.76）。本 case 两侧触发日相同（01-05） |",
        "| 4 | 激活阈值 | 免费版无 `tsl_th`（PRO 专有），`trailing_activate_pct=0.05` 不参与对拍（F-D3-P045-4）；"
        "本 case 未产生触发日差异 |",
        "| 5 | 重建行为 | vbt 单次 entry 信号 → 止损后不再重建；本仓 `targets>0` 次日重建（S1 期望 weights 反映）。"
        "本对拍只取**首次触发**（各标的 1 次），重建语义由 G1/G2 锁定 |",
        "",
        "## 4. 命令",
        "",
        "```powershell",
        r".\.venv-vbt\Scripts\python.exe scripts\external_benchmark\verify_p045.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P-045 vectorbt external calibration")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--golden", type=Path, default=GOLDEN)
    args = parser.parse_args(argv)

    payload = json.loads(args.golden.read_text(encoding="utf-8"))
    _, dates, codes, _ = _side_frames(payload)
    stops = _load_repo_stops()
    checks = Checks()

    repo = _repo_triggers(payload, stops)
    expected = [
        (row["date"], row["code"], row["reason"]) for row in payload["expected"]["triggers"]
    ]
    checks.add(
        "C1",
        "本仓触发序列 == 规格锁定期望（输入自校验）",
        repo == expected,
        f"repo={repo}",
    )

    vbt_rows: list[tuple[str, str, float]] = []
    for j, code in enumerate(codes):
        exit_date, exit_price, status = _vbt_exits(payload, dates, code, j)
        vbt_rows.append((exit_date, code, exit_price))
        checks.add(
            f"C2.{code}",
            f"vbt 恰一笔平仓（{code}）",
            status == "ok",
            f"exit_date={exit_date} exit_price={exit_price:.4f} rows={status}",
        )

    checks.add(
        "C3",
        "触发判定序列（date, code）逐值一致（按 date, code 规范化排序）",
        sorted((d, c) for d, c, _ in repo) == sorted((d, c) for d, c, _ in vbt_rows),
        f"repo={sorted((d, c) for d, c, _ in repo)} vbt={sorted((d, c) for d, c, _ in vbt_rows)}",
    )

    price_by_code = {code: price for _, code, price in vbt_rows}
    checks.add(
        "C4",
        "C 的 vbt 退出价 = SL 触发价 90（非 TP 120）→ SL 优先于 TP 与 vbt 一致",
        abs(price_by_code.get("C", float("nan")) - 90.0) < 1e-9,
        f"C exit_price={price_by_code.get('C')}",
    )
    checks.add(
        "C5",
        "A 的 vbt 退出价 = SL 触发价 90",
        abs(price_by_code.get("A", float("nan")) - 90.0) < 1e-9,
        f"A exit_price={price_by_code.get('A')}",
    )

    checks.waive("W1", "reason 字段对拍", "vbt 免费版 trades/orders 无止损类型列（实测）")
    checks.waive(
        "W2", "成交价 / NAV 对拍", "vbt 触发价成交 vs 本仓 T+1 开盘（I3 收窄，F-S2-P045-1）"
    )
    checks.waive(
        "W3", "trailing 幅度 0.08 vs 0.10", "vbt sl_trail 复用 sl_stop；本 case 触发日同（B 01-05）"
    )
    checks.waive(
        "W4", "trailing 激活阈值 0.05", "免费版无 tsl_th（F-D3-P045-4）；本 case 无触发日差异"
    )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(_render(checks, repo, vbt_rows), encoding="utf-8")
    print(f"[verify] 报告写入 {args.report}")
    return checks.finalize()


if __name__ == "__main__":
    sys.exit(main())
