#!/usr/bin/env python3
"""全周期追溯报告 CLI（P-061 B1）：trace_*.csv + alignment.json → 单文件 HTML。

用法：
    python scripts/trace_report.py --run-dir output/ [--out DIR] [--check]

两级产物（F-18）：
- **核心**：``trace_day.csv`` / ``trace_order.csv`` / ``trace_fill.csv`` / ``alignment.json``
  —— 任一缺失即 ``exit 1``；
- **辅助**：``manifest.json`` / ``portfolio_snapshots.csv`` / ``trades.csv`` /
  ``pending_order_events.csv`` / L1-L6 —— 缺失只记入 ``missing.json`` 的 ``missing[]``，
  ``exit 0``；不可计算的残差分项标 ``degraded``。

硬约束：只读渲染、无网络（无 ``http(s)://``、无 ``<script src>``）、无时间戳（可复现）。

注：B1 阶段 ``core/trace.py`` 尚未交付，列名常量临时自带；S5-2 后统一收敛为
``from core.trace import ...``（F-S8-P061-1）。
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.change_report import LAYER_FILES, RESIDUAL_TOL  # noqa: E402
from core.trace import (  # noqa: E402
    TRACE_DAY_COLUMNS,
    TRACE_FILL_COLUMNS,
    TRACE_FILES,
    TRACE_ORDER_COLUMNS,
    TRACE_SCHEMA_VERSION,
)

SCHEMA_VERSION = TRACE_SCHEMA_VERSION
CORE_FILES = TRACE_FILES

AUX_FILES = (
    "manifest.json",
    "portfolio_snapshots.csv",
    "trades.csv",
    "pending_order_events.csv",
)

EMPTY = "—"


def _read_csv(path: Path) -> pd.DataFrame:
    """全字段按字符串读取（空值保留空串，渲染侧统一显示 ``—``）。"""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip()
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def _missing_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "core_ok": True,
        "missing": [],
        "degraded": [],
        "residual": 0.0,
        "tolerance": RESIDUAL_TOL,
        "checks": {},
        "counts": {},
        "cross_check": "skipped",
        "exit_code": 0,
    }


def _scan_aux(run_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """辅助产物扫描：缺失记 ``missing[]``，残差不可算项记 ``degraded``。"""
    aux: dict[str, Any] = {}
    for name in AUX_FILES:
        path = run_dir / name
        if path.is_file():
            aux[name] = path
        else:
            payload["missing"].append(name)
            if name == "trades.csv":
                payload["degraded"].append("trades_amount_sum")
            elif name == "portfolio_snapshots.csv":
                payload["degraded"].append("snapshot_final_nav")
            elif name == "manifest.json":
                payload["degraded"].append("run_identity")
    return aux


def _cross_check(
    run_dir: Path, order_df: pd.DataFrame, fill_df: pd.DataFrame
) -> dict[str, Any] | str:
    """与既有 L1-L6 六层快照交叉校验（无则返回字符串 ``"skipped"``）。"""
    present = [name for name in LAYER_FILES if (run_dir / name).is_file()]
    if not present:
        return "skipped"
    result: dict[str, Any] = {"status": "ok", "layers_present": present}
    l4_path = run_dir / "L4_orders.json"
    if l4_path.is_file():
        try:
            l4 = json.loads(l4_path.read_text(encoding="utf-8"))
            n_l4 = sum(len(rows) for rows in l4.values() if isinstance(rows, list))
            result["l4_orders"] = n_l4
            result["trace_orders"] = int(len(order_df))
            if n_l4 != len(order_df):
                result["status"] = "mismatch"
        except (OSError, json.JSONDecodeError, AttributeError):
            result["status"] = "mismatch"
            result["l4_orders"] = None
    l5_path = run_dir / "L5_fills.json"
    if l5_path.is_file():
        try:
            l5 = json.loads(l5_path.read_text(encoding="utf-8"))
            n_l5 = sum(len(rows) for rows in l5.values() if isinstance(rows, list))
            result["l5_fills"] = n_l5
            result["trace_fills"] = int(len(fill_df))
            if n_l5 != len(fill_df):
                result["status"] = "mismatch"
        except (OSError, json.JSONDecodeError, AttributeError):
            result["status"] = "mismatch"
            result["l5_fills"] = None
    return result


def analyze(run_dir: Path) -> tuple[dict[str, Any], dict[str, pd.DataFrame], bool]:
    """读取并校验 trace 产物。

    Returns:
        ``(payload, frames, core_ok)``；``core_ok=False`` 表示核心产物缺失/损坏（exit 1）。
    """
    payload = _missing_payload()
    frames: dict[str, pd.DataFrame] = {}
    missing_core = [name for name in CORE_FILES if not (run_dir / name).is_file()]
    if missing_core:
        payload["core_ok"] = False
        payload["missing"] = missing_core
        payload["exit_code"] = 1
        return payload, frames, False

    try:
        alignment = json.loads((run_dir / "alignment.json").read_text(encoding="utf-8"))
        day_df = _read_csv(run_dir / "trace_day.csv")
        order_df = _read_csv(run_dir / "trace_order.csv")
        fill_df = _read_csv(run_dir / "trace_fill.csv")
    except (OSError, json.JSONDecodeError, pd.errors.ParserError):
        payload["core_ok"] = False
        payload["missing"] = ["alignment.json"]
        payload["exit_code"] = 1
        return payload, frames, False

    frames = {"day": day_df, "order": order_df, "fill": fill_df}
    counts = alignment.get("counts") or {}
    reconcile = alignment.get("reconcile") or {}

    csv_amount = sum(_to_float(value) for value in fill_df.get("amount", []))
    declared_amount = _to_float(reconcile.get("amount_sum"))
    declared_residual = _to_float(reconcile.get("residual"))
    residual_terms = [abs(csv_amount - declared_amount), declared_residual]

    aux = _scan_aux(run_dir, payload)
    trades_path = aux.get("trades.csv")
    if trades_path is not None:
        try:
            trades_df = _read_csv(trades_path)
            trades_amount = sum(_to_float(value) for value in trades_df.get("amount", []))
            residual_terms.append(abs(csv_amount - trades_amount))
            payload["checks"]["trades_amount"] = float(trades_amount)
        except (OSError, pd.errors.ParserError, KeyError):
            payload["degraded"].append("trades_amount_sum")

    snap_path = aux.get("portfolio_snapshots.csv")
    if snap_path is not None:
        try:
            snap_df = _read_csv(snap_path)
            if "total_value" in snap_df.columns and len(snap_df) > 0:
                snap_nav = _to_float(snap_df["total_value"].iloc[-1])
                residual_terms.append(
                    abs(_to_float(reconcile.get("snapshots_final_nav")) - snap_nav)
                )
                payload["checks"]["snapshot_final_nav"] = float(snap_nav)
            else:
                payload["degraded"].append("snapshot_final_nav")
        except (OSError, pd.errors.ParserError):
            payload["degraded"].append("snapshot_final_nav")

    counts_ok = int(counts.get("orders", len(order_df))) == len(order_df) and int(
        counts.get("fills", len(fill_df))
    ) == len(fill_df)
    residual = max(residual_terms) if residual_terms else 0.0
    ok = bool(counts_ok and residual <= RESIDUAL_TOL)

    payload.update(
        {
            "residual": float(residual),
            "checks": {
                **payload["checks"],
                "amount_matches_alignment": bool(abs(csv_amount - declared_amount) <= RESIDUAL_TOL),
                "counts_match": bool(counts_ok),
            },
            "counts": {
                "orders": int(len(order_df)),
                "fills": int(len(fill_df)),
                "direct_fills": (
                    int((fill_df.get("order_ref") == "direct").sum())
                    if "order_ref" in fill_df.columns
                    else 0
                ),
                "declared_orders": int(counts.get("orders", 0)),
                "declared_fills": int(counts.get("fills", 0)),
            },
            "cross_check": _cross_check(run_dir, order_df, fill_df),
            "exit_code": 0 if ok else 1,
        }
    )
    return payload, frames, ok


def _fmt(value: Any) -> str:
    text = str(value).strip()
    return html.escape(text) if text else EMPTY


def _heat_color(value: float, maximum: float) -> str:
    if maximum <= 0:
        return "#ffffff"
    ratio = max(0.0, min(value / maximum, 1.0))
    red = int(255 - 150 * ratio)
    green = int(255 - 70 * ratio)
    blue = int(255 - 150 * ratio)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _section_summary(payload: dict[str, Any]) -> str:
    counts = payload.get("counts", {})
    residual = float(payload.get("residual", 0.0))
    status = "通过" if residual <= RESIDUAL_TOL else "残差超限"
    color = "#1b5e20" if residual <= RESIDUAL_TOL else "#b71c1c"
    missing = "、".join(payload.get("missing", [])) or EMPTY
    degraded = "、".join(payload.get("degraded", [])) or EMPTY
    return (
        "<section><h2>1. 对齐摘要</h2>"
        '<table class="kv">'
        f"<tr><th>orders / fills / direct_fills</th><td>{counts.get('orders', 0)} / "
        f"{counts.get('fills', 0)} / {counts.get('direct_fills', 0)}</td></tr>"
        f'<tr><th>residual</th><td style="color:{color};font-weight:700">'
        f"{residual:.12g}（容差 {RESIDUAL_TOL:g}，{status}）</td></tr>"
        f"<tr><th>missing[]</th><td>{html.escape(missing)}</td></tr>"
        f"<tr><th>degraded</th><td>{html.escape(degraded)}</td></tr>"
        "</table></section>"
    )


def _section_heatmap(frames: dict[str, pd.DataFrame]) -> str:
    day_df = frames["day"]
    fill_df = frames["fill"]
    order_df = frames["order"]
    dates = sorted(
        set(day_df.get("date", [])) | set(fill_df.get("date", [])) | set(order_df.get("date", []))
    )
    if not dates:
        return "<section><h2>2. 日历热力</h2><p>（无数据）</p></section>"

    rows = []
    amounts: dict[str, float] = {}
    fill_counts: dict[str, int] = {}
    reject_counts: dict[str, int] = {}
    for date in dates:
        amounts[date] = 0.0
        fill_counts[date] = 0
        reject_counts[date] = 0
    for record in fill_df.to_dict("records"):
        date = str(record.get("date", ""))
        if date not in amounts:
            continue
        amounts[date] += _to_float(record.get("amount"))
        fill_counts[date] += 1
    for record in order_df.to_dict("records"):
        date = str(record.get("date", ""))
        if date not in amounts:
            continue
        if str(record.get("reject_reason", "")).strip():
            reject_counts[date] += 1
    max_amount = max(amounts.values()) if amounts else 0.0

    for date in dates:
        color = _heat_color(amounts[date], max_amount)
        rows.append(
            f'<tr style="background:{color}"><td><a href="#d-{html.escape(date)}">'
            f"{html.escape(date)}</a></td>"
            f"<td>{amounts[date]:.2f}</td><td>{fill_counts[date]}</td>"
            f"<td>{reject_counts[date]}</td></tr>"
        )
    return (
        '<section><h2>2. 日历热力</h2><table class="grid">'
        "<tr><th>日期</th><th>成交额</th><th>成交笔数</th><th>拒单数</th></tr>"
        + "".join(rows)
        + "</table></section>"
    )


def _section_day(frames: dict[str, pd.DataFrame]) -> str:
    day_df = frames["day"]
    blocks = []
    if day_df.empty or "date" not in day_df.columns:
        return "<section><h2>3. 日视图</h2><p>（无数据）</p></section>"
    for date in sorted(set(day_df["date"])):
        sub = day_df[day_df["date"] == date]
        head = "".join(f"<th>{html.escape(col)}</th>" for col in TRACE_DAY_COLUMNS)
        body = []
        for _, row in sub.iterrows():
            cells = "".join(f"<td>{_fmt(row.get(col, ''))}</td>" for col in TRACE_DAY_COLUMNS)
            body.append(f"<tr>{cells}</tr>")
        blocks.append(
            f'<h3 id="d-{html.escape(date)}">{html.escape(date)}</h3>'
            f'<table class="grid"><tr>{head}</tr>{"".join(body)}</table>'
        )
    return "<section><h2>3. 日视图</h2>" + "".join(blocks) + "</section>"


def _section_timeline(frames: dict[str, pd.DataFrame]) -> str:
    day_df = frames["day"]
    order_df = frames["order"]
    fill_df = frames["fill"]
    stocks = sorted(
        set(day_df.get("stock", []))
        | set(order_df.get("stock", []))
        | set(fill_df.get("stock", []))
    )
    if not stocks:
        return "<section><h2>4. 单票时间轴</h2><p>（无数据）</p></section>"

    details = []
    for stock in stocks:
        day_rows = (
            day_df[day_df["stock"] == stock] if "stock" in day_df.columns else day_df.iloc[0:0]
        )
        order_rows = (
            order_df[order_df["stock"] == stock]
            if "stock" in order_df.columns
            else order_df.iloc[0:0]
        )
        fill_rows = (
            fill_df[fill_df["stock"] == stock] if "stock" in fill_df.columns else fill_df.iloc[0:0]
        )
        dates = sorted(
            set(day_rows.get("date", []))
            | set(order_rows.get("date", []))
            | set(fill_rows.get("date", []))
        )
        svg = _render_svg(stock, dates, day_rows, order_rows, fill_rows)
        details.append(f"<details open><summary>{html.escape(stock)}</summary>{svg}</details>")
    return "<section><h2>4. 单票时间轴</h2>" + "".join(details) + "</section>"


def _render_svg(
    stock: str,
    dates: list[str],
    day_rows: pd.DataFrame,
    order_rows: pd.DataFrame,
    fill_rows: pd.DataFrame,
) -> str:
    lanes = (("target", "目标"), ("order", "订单"), ("fill", "成交"), ("close", "平仓"))
    left = 80
    width = 960
    lane_height = 40
    top = 30
    height = top + lane_height * len(lanes) + 10
    span = max(len(dates) - 1, 1)
    step = (width - left - 20) / span

    parts = [
        f'<svg width="{width}" height="{height}" role="img" aria-label="{html.escape(stock)}">'
    ]
    for index, date in enumerate(dates):
        x = left + index * step
        parts.append(
            f'<text x="{x:.1f}" y="16" font-size="10" text-anchor="middle" '
            f'fill="#555">{html.escape(date[5:])}</text>'
        )
    for lane_index, (_, label) in enumerate(lanes):
        y = top + lane_index * lane_height
        parts.append(
            f'<text x="8" y="{y + 4}" font-size="12" fill="#333">{label}</text>'
            f'<line x1="{left}" y1="{y}" x2="{width - 20}" y2="{y}" stroke="#dddddd"/>'
        )

    def x_of(date: str) -> float:
        return left + dates.index(date) * step

    marks = []
    for _, row in day_rows.iterrows():
        date = str(row.get("date", ""))
        if date not in dates:
            continue
        text = f"目标 {row.get('target_qty', EMPTY)} 权重 {row.get('target_weight', EMPTY)}"
        marks.append((date, 0, text))
    for _, row in order_rows.iterrows():
        date = str(row.get("date", ""))
        if date not in dates:
            continue
        text = f"{row.get('side', '')} {row.get('qty', '')} {row.get('status', '')}"
        marks.append((date, 1, text))
    for _, row in fill_rows.iterrows():
        date = str(row.get("date", ""))
        if date not in dates:
            continue
        text = f"{row.get('side', '')} {row.get('qty', '')}@{row.get('price', '')}"
        marks.append((date, 2, text))
    for _, row in day_rows.iterrows():
        date = str(row.get("date", ""))
        reason = str(row.get("close_reason", "")).strip()
        if date not in dates or not reason:
            continue
        marks.append((date, 3, reason))

    for date, lane_index, text in marks:
        x = x_of(date)
        y = top + lane_index * lane_height
        parts.append(f'<circle cx="{x:.1f}" cy="{y}" r="4" fill="#1565c0"/>')
        parts.append(
            f'<text x="{x + 7:.1f}" y="{y + 4}" font-size="10" fill="#222">'
            f"{html.escape(text)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def render_html(payload: dict[str, Any], frames: dict[str, pd.DataFrame]) -> str:
    """渲染单文件离线 HTML（四块：摘要 / 热力 / 日视图 / 单票时间轴）。"""
    body = (
        _section_summary(payload)
        + _section_heatmap(frames)
        + _section_day(frames)
        + _section_timeline(frames)
    )
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        "<title>P-061 全周期追溯报告</title><style>"
        "body{font-family:-apple-system,'Segoe UI',sans-serif;margin:24px;color:#222}"
        "h1{font-size:20px} h2{font-size:16px;margin-top:28px;border-left:4px solid #1565c0;"
        "padding-left:8px} h3{font-size:13px;margin:16px 0 6px}"
        "table{border-collapse:collapse;margin:6px 0 14px;font-size:12px}"
        "th,td{border:1px solid #d0d0d0;padding:3px 6px;text-align:left}"
        "table.grid th{background:#f5f5f5;position:sticky;top:0}"
        "table.kv th{background:#f5f5f5;width:220px}"
        "source{display:block}"
        "p.source{color:#666;font-size:12px}"
        "details{margin:6px 0 14px} summary{cursor:pointer;font-weight:600;font-size:13px}"
        "</style></head><body>"
        "<h1>P-061 全周期追溯报告</h1>"
        '<p class="source">数据来源：trace_day.csv / trace_order.csv / trace_fill.csv / '
        "alignment.json / manifest.json（只读渲染，不重算指标）</p>" + body + "</body></html>"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P-061 全周期追溯报告（只读，单文件 HTML）")
    parser.add_argument("--run-dir", required=True, help="含 trace_*.csv / alignment.json 的目录")
    parser.add_argument("--out", default=None, help="输出目录（默认与 run-dir 相同）")
    parser.add_argument("--check", action="store_true", help="只做对齐校验，不写 HTML")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    out_dir = Path(args.out) if args.out else run_dir
    payload, frames, alignment_ok = analyze(run_dir)
    core_ok = bool(payload["core_ok"])

    if args.check:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        if not core_ok:
            print(f"error: 核心产物缺失 {payload['missing']}", file=sys.stderr)
        elif not alignment_ok:
            print(
                f"error: residual={payload['residual']:.3e} > {RESIDUAL_TOL:g} "
                f"或 counts 不一致",
                file=sys.stderr,
            )
        return int(payload["exit_code"])

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "missing.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not core_ok:
        print(f"error: 核心产物缺失 {payload['missing']}", file=sys.stderr)
        return 1

    (out_dir / "trace.html").write_text(render_html(payload, frames), encoding="utf-8")
    if not alignment_ok:
        print(
            f"error: residual={payload['residual']:.3e} > {RESIDUAL_TOL:g} 或 counts 不一致",
            file=sys.stderr,
        )
    print(f"trace.html / missing.json written to {out_dir}")
    return int(payload["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
