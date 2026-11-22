"""P-053 T 组：三级对账与 parity（T5，12 例）。"""

from __future__ import annotations

from live.ledger import LedgerSnapshot, PositionLot
from live.reconcile import (
    BreakLevel,
    ParityConfig,
    ParityReport,
    ReconcileConfig,
    evaluate_parity,
    overall_level,
    reconcile_cash,
    reconcile_fills,
    reconcile_positions,
    should_degrade,
)

CFG = ReconcileConfig(
    dust_pct=0.001, dust_abs_quantity=100.0, cash_dust_pct_nav=0.0001, cash_dust_abs=1.0
)


def _snap(cash: float, positions: tuple[PositionLot, ...]) -> LedgerSnapshot:
    return LedgerSnapshot(cash=cash, reserved_cash=0.0, positions=positions, as_of=0.0)


def test_t5_position_delta_zero_ok():
    report = reconcile_positions({"AAA": 100.0}, {"AAA": 100.0}, config=CFG)
    assert report.level is BreakLevel.OK
    assert report.breaks == ()
    assert report.checked == 1


def test_t5_position_dust_absolute():
    report = reconcile_positions({"AAA": 1050.0}, {"AAA": 1000.0}, config=CFG)
    assert report.level is BreakLevel.DUST


def test_t5_position_dust_ratio():
    cfg = ReconcileConfig(dust_pct=0.001, dust_abs_quantity=1.0)
    report = reconcile_positions({"AAA": 1_000_500.0}, {"AAA": 1_000_000.0}, config=cfg)
    assert report.level is BreakLevel.DUST


def test_t5_explained_becomes_missed():
    report = reconcile_positions(
        {"AAA": 1500.0},
        {"AAA": 1000.0},
        config=CFG,
        explained=frozenset({"AAA"}),
    )
    assert report.level is BreakLevel.MISSED


def test_t5_unexplained_becomes_unresolved():
    report = reconcile_positions({"AAA": 1500.0}, {"AAA": 1000.0}, config=CFG)
    assert report.level is BreakLevel.UNRESOLVED


def test_t5_cash_dust():
    report = reconcile_cash(10_050.0, 10_000.0, config=CFG, nav=1_000_000.0)
    assert report.level is BreakLevel.DUST
    assert report.breaks[0].kind == "cash"


def test_t5_cash_unresolved():
    report = reconcile_cash(10_500.0, 10_000.0, config=CFG, nav=1_000_000.0)
    assert report.level is BreakLevel.UNRESOLVED


def test_t5_missing_fill_missed():
    report = reconcile_fills(set(), {"f1"})
    assert report.level is BreakLevel.MISSED
    assert report.breaks[0].kind == "missing_fill"


def test_t5_extra_fill_unresolved():
    report = reconcile_fills({"f1"}, set())
    assert report.level is BreakLevel.UNRESOLVED
    assert report.breaks[0].kind == "extra_fill"


def test_t5_overall_level_takes_worst():
    reports = [
        reconcile_positions({"AAA": 100.0}, {"AAA": 100.0}, config=CFG),
        reconcile_cash(10_050.0, 10_000.0, config=CFG, nav=1_000_000.0),
        reconcile_positions(
            {"BBB": 1500.0},
            {"BBB": 1000.0},
            config=CFG,
            explained=frozenset({"BBB"}),
        ),
    ]
    assert overall_level(reports) is BreakLevel.MISSED


def test_t5_evaluate_parity_four_breaches():
    paper = _snap(10_000.0, (PositionLot("AAA", 100.0, 10.0),))
    live = _snap(9_000.0, (PositionLot("BBB", 100.0, 10.0),))
    report = evaluate_parity(
        paper,
        live,
        nav=10_000.0,
        slippage_bps=50.0,
        fill_rate=0.5,
        liquid=True,
        config=ParityConfig(),
    )
    assert set(report.breaches) == {"cash", "weight", "slippage", "fill_rate"}


def test_t5_should_degrade_two_consecutive_days_with_reset():
    bad = ParityReport(0.0, 0.0, 0.0, 1.0, ("cash",))
    ok = ParityReport(0.0, 0.0, 0.0, 1.0, ())
    cfg = ParityConfig(degrade_days=2)
    interrupted = [("2026-01-01", bad), ("2026-01-02", ok), ("2026-01-03", bad)]
    assert should_degrade(interrupted, config=cfg) is False
    consecutive = interrupted + [("2026-01-04", bad)]
    assert should_degrade(consecutive, config=cfg) is True
