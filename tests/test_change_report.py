"""P-012 B1：六层归因与 change_report（D6 / T-2）验收测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from core.change_report import LayerDumper, MissingLayerError, compare_runs


def _write_run(
    root: Path,
    *,
    l1_rows: list[list],
    l5_fills: dict,
    l6_rows: list[list],
    l2_rows: list[list] | None = None,
    l3: dict | None = None,
    l4: dict | None = None,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(l1_rows, columns=["date", "stock", "can_buy", "can_sell"]).to_csv(
        root / "L1_limit_mask.csv", index=False
    )
    pd.DataFrame(l2_rows or [], columns=["date", "stock", "buyable", "sellable"]).to_csv(
        root / "L2_tradable.csv", index=False
    )
    (root / "L3_target_positions.json").write_text(json.dumps(l3 or {}), encoding="utf-8")
    (root / "L4_orders.json").write_text(json.dumps(l4 or {}), encoding="utf-8")
    (root / "L5_fills.json").write_text(json.dumps(l5_fills), encoding="utf-8")
    pd.DataFrame(l6_rows, columns=["date", "cash", "market_value", "total_value"]).to_csv(
        root / "L6_nav.csv", index=False
    )


def test_residual_requires_layers(tmp_path):
    run = tmp_path / "a"
    _write_run(
        run,
        l1_rows=[],
        l5_fills={},
        l6_rows=[["2024-01-02", 1000.0, 0.0, 1000.0]],
    )
    (run / "L5_fills.json").unlink()
    with pytest.raises(MissingLayerError):
        compare_runs(run, run)


def test_attribution_gap_detected(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    _write_run(
        before,
        l1_rows=[],
        l5_fills={},
        l6_rows=[["2024-01-02", 1000.0, 0.0, 1000.0]],
    )
    _write_run(
        after,
        l1_rows=[],
        l5_fills={},
        l6_rows=[["2024-01-02", 900.0, 0.0, 900.0]],
    )

    report = compare_runs(before, after)

    assert report.attribution_complete is False
    assert report.nav.after == pytest.approx(900.0)
    assert report.nav_recomputed == pytest.approx(900.0)
    assert report.residual == pytest.approx(0.0)


def test_dump_disabled_zero_io(tmp_path):
    disabled = LayerDumper(None)
    assert disabled.enabled is False
    disabled.setup()
    disabled.record_targets(pd.Timestamp("2024-01-02"), ["000001"])
    disabled.dump_day(
        pd.Timestamp("2024-01-02"),
        None,
        None,
        None,
        None,
        {"cash": 1.0, "market_value": 0.0, "total_value": 1.0},
    )
    disabled.finalize()
    assert list(tmp_path.iterdir()) == []

    layers = tmp_path / "layers"
    enabled = LayerDumper(layers)
    assert enabled.enabled is True
    enabled.setup()
    enabled.record_targets(pd.Timestamp("2024-01-02"), ["000001"])
    enabled.dump_day(
        pd.Timestamp("2024-01-02"),
        pd.Series({"000001": True, "000002": False}),
        pd.Series({"000001": True, "000002": False}),
        pd.Series({"000001": True, "000002": True}),
        pd.Series({"000001": True, "000002": True}),
        {"cash": 1000.0, "market_value": 0.0, "total_value": 1000.0},
    )
    enabled.finalize()

    assert (layers / "L6_nav.csv").exists()
    assert (layers / "L1_limit_mask.csv").exists()
    assert (layers / "L2_tradable.csv").exists()
