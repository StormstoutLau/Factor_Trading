"""P-061 B1 报告层验收（T-C01..C08）。

覆盖两级产物（F-18）：核心 ``trace_*.csv`` / ``alignment.json`` 缺失 → exit 1；
辅助 ``manifest.json`` / ``snapshots`` / ``trades`` / ``pending_events`` / L1-L6 缺失
→ ``missing[]`` + exit 0（不可算残差分项标 ``degraded``）。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pandas as pd

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "trace_report.py"
_SPEC = importlib.util.spec_from_file_location("p061_trace_report", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
trace_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(trace_report)

CORE_FILES = trace_report.CORE_FILES
main = trace_report.main

DAY_COLUMNS = [
    "date",
    "stock",
    "trace_id",
    "signal",
    "target_weight",
    "target_qty",
    "current_qty",
    "is_exit",
    "tradable",
    "buyable",
    "sellable",
    "position_qty",
    "position_value",
    "close_reason",
    "nav",
]
ORDER_COLUMNS = [
    "order_ref",
    "trace_id",
    "date",
    "stock",
    "side",
    "qty",
    "filled_qty",
    "status",
    "reject_reason",
    "retry_count",
    "create_date",
    "execute_date",
    "execute_price",
    "fallback_stock",
]
FILL_COLUMNS = [
    "fill_ref",
    "order_ref",
    "replaces_order_ref",
    "date",
    "stock",
    "side",
    "qty",
    "price",
    "amount",
    "cost",
    "net_amount",
    "multiplier",
]

ORDER_REF = "2024-01-02|000001|BUY|00001"


def _day_rows() -> list[dict[str, Any]]:
    return [
        {
            "date": "2024-01-02",
            "stock": "000001",
            "trace_id": "2024-01-02|000001",
            "signal": "1.5",
            "target_weight": "1.0",
            "target_qty": "100",
            "current_qty": "0",
            "is_exit": "False",
            "tradable": "True",
            "buyable": "True",
            "sellable": "True",
            "position_qty": "100",
            "position_value": "1000",
            "close_reason": "",
            "nav": "1004",
        },
        {
            "date": "2024-01-03",
            "stock": "000001",
            "trace_id": "2024-01-03|000001",
            "signal": "1.2",
            "target_weight": "0.0",
            "target_qty": "0",
            "current_qty": "100",
            "is_exit": "True",
            "tradable": "True",
            "buyable": "True",
            "sellable": "True",
            "position_qty": "0",
            "position_value": "0",
            "close_reason": "final_liquidation",
            "nav": "1004",
        },
    ]


def _order_rows() -> list[dict[str, Any]]:
    return [
        {
            "order_ref": ORDER_REF,
            "trace_id": "2024-01-02|000001",
            "date": "2024-01-02",
            "stock": "000001",
            "side": "BUY",
            "qty": "100",
            "filled_qty": "100",
            "status": "filled",
            "reject_reason": "",
            "retry_count": "0",
            "create_date": "2024-01-02",
            "execute_date": "2024-01-02",
            "execute_price": "10.0",
            "fallback_stock": "",
        }
    ]


def _fill_rows(amount: float = 1000.0) -> list[dict[str, Any]]:
    return [
        {
            "fill_ref": f"{ORDER_REF}|1",
            "order_ref": ORDER_REF,
            "replaces_order_ref": "",
            "date": "2024-01-02",
            "stock": "000001",
            "side": "BUY",
            "qty": "100",
            "price": "10.0",
            "amount": f"{amount}",
            "cost": "6.0",
            "net_amount": "-1006.0",
            "multiplier": "1.0",
        }
    ]


def _alignment(amount: float = 1000.0) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "manifest": {"run_id": None, "input_fingerprint": None},
        "counts": {"orders": 1, "fills": 1, "direct_fills": 0},
        "reconcile": {
            "qty_by_side": {"BUY": 100, "SELL": 0, "SELL_SHORT": 0, "BUY_TO_COVER": 0},
            "amount_sum": amount,
            "cost_sum": 6.0,
            "trades_csv_amount_sum": amount,
            "snapshots_final_nav": 1004.0,
            "residual": 0.0,
        },
        "gates": {"golden": "not_run", "p059": "not_run"},
        "missing": [],
    }


def _write_dir(
    root: Path,
    *,
    fill_amount: float = 1000.0,
    alignment_amount: float = 1000.0,
    day_columns: list[str] | None = None,
    with_manifest: bool = True,
    with_layers: bool = False,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    day_df = pd.DataFrame(_day_rows())[day_columns or DAY_COLUMNS]
    day_df.to_csv(root / "trace_day.csv", index=False)
    pd.DataFrame(_order_rows(), columns=ORDER_COLUMNS).to_csv(root / "trace_order.csv", index=False)
    pd.DataFrame(_fill_rows(fill_amount), columns=FILL_COLUMNS).to_csv(
        root / "trace_fill.csv", index=False
    )
    (root / "alignment.json").write_text(
        json.dumps(_alignment(alignment_amount), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if with_manifest:
        (root / "manifest.json").write_text(
            json.dumps({"schema_version": "1.0", "run_id": "run-1"}, ensure_ascii=False),
            encoding="utf-8",
        )
    pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "stock": "000001",
                "side": "BUY",
                "quantity": 100,
                "price": 10.0,
                "amount": fill_amount,
                "cost": 6.0,
                "net_amount": -float(fill_amount) - 6.0,
            }
        ]
    ).to_csv(root / "trades.csv", index=False)
    pd.DataFrame([{"date": "2024-01-03", "total_value": 1004.0}]).to_csv(
        root / "portfolio_snapshots.csv", index=False
    )
    pd.DataFrame(
        [{"date": "2024-01-02", "event_type": "ORDER_ADDED", "stock": "000001", "description": ""}]
    ).to_csv(root / "pending_order_events.csv", index=False)
    if with_layers:
        pd.DataFrame(
            [{"date": "2024-01-02", "stock": "000001", "can_buy": False, "can_sell": True}]
        ).to_csv(root / "L1_limit_mask.csv", index=False)
        pd.DataFrame(
            [{"date": "2024-01-02", "stock": "000001", "buyable": False, "sellable": True}]
        ).to_csv(root / "L2_tradable.csv", index=False)
        (root / "L3_target_positions.json").write_text(
            json.dumps({"2024-01-02": ["000001"]}), encoding="utf-8"
        )
        (root / "L4_orders.json").write_text(
            json.dumps(
                {
                    "2024-01-02": [
                        {"stock": "000001", "side": "BUY", "qty": 100, "reason": "rebalance"}
                    ]
                }
            ),
            encoding="utf-8",
        )
        (root / "L5_fills.json").write_text(
            json.dumps(
                {"2024-01-02": [{"stock": "000001", "side": "BUY", "qty": 100, "price": 10.0}]}
            ),
            encoding="utf-8",
        )
        pd.DataFrame(
            [{"date": "2024-01-02", "cash": 4.0, "market_value": 1000.0, "total_value": 1004.0}]
        ).to_csv(root / "L6_nav.csv", index=False)
    return root


def _payload(root: Path) -> dict[str, Any]:
    return json.loads((root / "missing.json").read_text(encoding="utf-8"))


def test_t_c01_aligned_dir_exits_zero_and_writes_outputs(tmp_path: Path) -> None:
    """T-C01 | oracle=contract：对齐目录 → exit 0 + trace.html + missing.json。"""
    root = _write_dir(tmp_path / "run")
    assert main(["--run-dir", str(root)]) == 0
    assert (root / "trace.html").is_file()
    assert (root / "missing.json").is_file()
    payload = _payload(root)
    assert payload["core_ok"] is True
    assert payload["residual"] == 0.0
    assert payload["counts"]["orders"] == 1
    assert payload["counts"]["fills"] == 1


def test_t_c02_tampered_amount_exits_one(tmp_path: Path, capsys: Any) -> None:
    """T-C02 | oracle=contract：篡改 1 行金额 → exit 1；stderr 含 residual。"""
    root = _write_dir(tmp_path / "run", fill_amount=1001.0)
    assert main(["--run-dir", str(root)]) == 1
    captured = capsys.readouterr()
    assert "residual" in captured.err
    payload = _payload(root)
    assert payload["residual"] > 1e-8
    assert payload["exit_code"] == 1


def test_t_c03_missing_manifest_is_auxiliary_but_core_is_fatal(tmp_path: Path) -> None:
    """T-C03 | oracle=boundary：辅助缺失 → exit 0 + missing[]；核心缺失 → exit 1。"""
    aux_root = _write_dir(tmp_path / "auxdir", with_manifest=False)
    assert main(["--run-dir", str(aux_root)]) == 0
    payload = _payload(aux_root)
    assert "manifest.json" in payload["missing"]
    assert "run_identity" in payload["degraded"]
    assert payload["core_ok"] is True

    core_root = _write_dir(tmp_path / "core")
    (core_root / "trace_day.csv").unlink()
    assert main(["--run-dir", str(core_root)]) == 1
    core_payload = _payload(core_root)
    assert core_payload["core_ok"] is False
    assert "trace_day.csv" in core_payload["missing"]


def test_t_c04_html_is_offline_single_file(tmp_path: Path) -> None:
    """T-C04 | oracle=contract：无 http(s) 外链、无脚本 src、单文件可开。"""
    root = _write_dir(tmp_path / "run")
    assert main(["--run-dir", str(root)]) == 0
    text = (root / "trace.html").read_text(encoding="utf-8")
    assert "http://" not in text
    assert "https://" not in text
    assert "<script" not in text
    assert "<svg" in text
    assert "<html" in text


def test_t_c05_day_view_has_four_sections_and_tolerates_missing_columns(
    tmp_path: Path,
) -> None:
    """T-C05 | oracle=contract：目标/订单/成交/平仓四段；缺列标 — 不抛异常。"""
    reduced = [column for column in DAY_COLUMNS if column != "close_reason"]
    root = _write_dir(tmp_path / "run", day_columns=reduced)
    assert main(["--run-dir", str(root)]) == 0
    text = (root / "trace.html").read_text(encoding="utf-8")
    assert "3. 日视图" in text
    for label in ("目标", "订单", "成交", "平仓"):
        assert label in text
    assert "—" in text
    assert "数据来源" in text


def test_t_c06_cross_check_with_layers_or_skipped(tmp_path: Path) -> None:
    """T-C06 | oracle=contract：有 L1-L6 交叉校验；无则 cross_check=skipped。"""
    with_layers = _write_dir(tmp_path / "layers", with_layers=True)
    assert main(["--run-dir", str(with_layers)]) == 0
    payload = _payload(with_layers)
    assert payload["cross_check"]["status"] == "ok"
    assert payload["cross_check"]["l4_orders"] == 1
    assert payload["cross_check"]["l5_fills"] == 1

    without_layers = _write_dir(tmp_path / "plain")
    assert main(["--run-dir", str(without_layers)]) == 0
    assert _payload(without_layers)["cross_check"] == "skipped"


def test_t_c07_check_mode_writes_no_html(tmp_path: Path, capsys: Any) -> None:
    """T-C07 | oracle=contract：--check 不写 HTML，只输出 JSON/退出码。"""
    root = _write_dir(tmp_path / "run")
    assert main(["--run-dir", str(root), "--check"]) == 0
    assert not (root / "trace.html").exists()
    assert not (root / "missing.json").exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["core_ok"] is True


def test_t_c08_html_bytes_are_deterministic(tmp_path: Path) -> None:
    """T-C08 | oracle=invariant：同输入两次生成 HTML/JSON 字节相同（无时间戳）。"""
    root = _write_dir(tmp_path / "run")
    assert main(["--run-dir", str(root)]) == 0
    first_html = (root / "trace.html").read_bytes()
    first_json = (root / "missing.json").read_bytes()
    assert main(["--run-dir", str(root)]) == 0
    assert (root / "trace.html").read_bytes() == first_html
    assert (root / "missing.json").read_bytes() == first_json
    assert all(name in {item.name for item in root.iterdir()} for name in CORE_FILES)
