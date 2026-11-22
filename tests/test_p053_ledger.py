"""P-053 T 组：双分录账本（T3，14 例）。"""

from __future__ import annotations

import pytest

from live.corporate_actions import ActionType, CorporateAction
from live.ledger import Ledger, LedgerError, PositionLot
from live.orders import FillRecord


def _fill(
    key: str,
    side: str,
    quantity: float,
    price: float,
    *,
    fee: float = 0.0,
    asset: str = "AAA",
    coid: str = "co1",
    ts: float = 1.0,
) -> FillRecord:
    return FillRecord(
        fill_key=key,
        client_order_id=coid,
        asset=asset,
        side=side,
        quantity=quantity,
        price=price,
        fee=fee,
        ts=ts,
    )


def _action(action_type: ActionType, **overrides) -> CorporateAction:
    base = dict(
        action_id="ca1",
        asset="AAA",
        action_type=action_type,
        ex_date="2026-01-05",
    )
    base.update(overrides)
    return CorporateAction(**base)


def _position(ledger: Ledger, asset: str = "AAA") -> PositionLot:
    return {p.asset: p for p in ledger.snapshot().positions}[asset]


def test_t3_buy_weighted_cost():
    ledger = Ledger(initial_cash=10_000.0)
    ledger.apply_fill(_fill("f1", "BUY", 100.0, 10.0))
    lot = _position(ledger)
    assert lot.quantity == 100.0
    assert lot.avg_cost == pytest.approx(10.0)
    assert ledger.cash == pytest.approx(9_000.0)


def test_t3_second_buy_dilutes_avg_cost():
    ledger = Ledger(initial_cash=10_000.0)
    ledger.apply_fill(_fill("f1", "BUY", 100.0, 10.0))
    ledger.apply_fill(_fill("f2", "BUY", 100.0, 20.0, ts=2.0))
    lot = _position(ledger)
    assert lot.quantity == 200.0
    assert lot.avg_cost == pytest.approx(15.0)


def test_t3_sell_realizes_pnl():
    ledger = Ledger(initial_cash=10_000.0)
    ledger.apply_fill(_fill("f1", "BUY", 100.0, 10.0))
    ledger.apply_fill(_fill("f2", "SELL", 40.0, 12.0, ts=2.0))
    lot = _position(ledger)
    assert lot.quantity == 60.0
    assert lot.realized_pnl == pytest.approx(80.0)


def test_t3_full_sell_resets_avg_cost():
    ledger = Ledger(initial_cash=10_000.0)
    ledger.apply_fill(_fill("f1", "BUY", 100.0, 10.0))
    ledger.apply_fill(_fill("f2", "SELL", 100.0, 12.0, ts=2.0))
    lot = _position(ledger)
    assert lot.quantity == 0.0
    assert lot.avg_cost == 0.0
    assert lot.realized_pnl == pytest.approx(200.0)


def test_t3_cash_conservation_with_fees():
    ledger = Ledger(initial_cash=10_000.0)
    ledger.apply_fill(_fill("f1", "BUY", 100.0, 10.0, fee=5.0))
    ledger.apply_fill(_fill("f2", "SELL", 40.0, 12.0, fee=2.0, ts=2.0))
    snap = ledger.snapshot()
    amount = sum(e.amount for e in ledger.entries())
    fees = sum(e.fee for e in ledger.entries())
    assert snap.cash + snap.reserved_cash == pytest.approx(10_000.0 - amount - fees, abs=1e-6)


def test_t3_fee_is_separate_entry():
    ledger = Ledger(initial_cash=10_000.0)
    ledger.apply_fill(_fill("f1", "BUY", 100.0, 10.0, fee=5.0))
    kinds = [e.kind for e in ledger.entries()]
    assert kinds == ["fill", "fee"]
    assert ledger.entries()[1].fee == 5.0


def test_t3_duplicate_entry_returns_false():
    ledger = Ledger(initial_cash=10_000.0)
    fill = _fill("f1", "BUY", 100.0, 10.0)
    assert ledger.apply_fill(fill) is True
    assert ledger.apply_fill(fill) is False
    assert len(ledger.entries()) == 1


def test_t3_reserve_reduces_cash():
    ledger = Ledger(initial_cash=1_000.0)
    ledger.reserve(ref="co1", amount=300.0, ts=1.0)
    assert ledger.cash == pytest.approx(700.0)
    assert ledger.reserved == pytest.approx(300.0)


def test_t3_release_refunds_cash():
    ledger = Ledger(initial_cash=1_000.0)
    ledger.reserve(ref="co1", amount=300.0, ts=1.0)
    ledger.release(ref="co1", ts=2.0)
    assert ledger.cash == pytest.approx(1_000.0)
    assert ledger.reserved == pytest.approx(0.0)


def test_t3_settle_returns_difference():
    ledger = Ledger(initial_cash=1_000.0)
    ledger.reserve(ref="co1", amount=300.0, ts=1.0)
    returned = ledger.settle_reserve(ref="co1", actual=290.0, ts=2.0)
    assert returned == pytest.approx(10.0)
    assert ledger.cash == pytest.approx(710.0)


def test_t3_reserve_over_cash_raises():
    ledger = Ledger(initial_cash=100.0)
    with pytest.raises(LedgerError, match="insufficient cash"):
        ledger.reserve(ref="co1", amount=150.0, ts=1.0)


def test_t3_settle_without_reserve_raises():
    ledger = Ledger(initial_cash=100.0)
    with pytest.raises(LedgerError, match="no reserve"):
        ledger.settle_reserve(ref="co_missing", actual=10.0, ts=1.0)


def test_t3_cash_dividend_updates_cash_and_entry_amount():
    ledger = Ledger(initial_cash=10_000.0)
    ledger.apply_fill(_fill("f1", "BUY", 100.0, 10.0))
    entries = ledger.apply_corporate_action(
        _action(ActionType.CASH_DIVIDEND, cash_per_share=2.0), ts=2.0
    )
    assert ledger.cash == pytest.approx(9_200.0)
    assert entries[0].amount == pytest.approx(-200.0)
    snap = ledger.snapshot()
    total = sum(e.amount for e in ledger.entries())
    assert snap.cash == pytest.approx(10_000.0 - total)


def test_t3_stock_dividend_split_and_replay_equivalence():
    ledger = Ledger(initial_cash=10_000.0)
    ledger.apply_fill(_fill("f1", "BUY", 100.0, 10.0))
    ledger.apply_corporate_action(_action(ActionType.STOCK_DIVIDEND, share_ratio=0.5), ts=2.0)
    ledger.apply_corporate_action(
        _action(ActionType.SPLIT, action_id="ca2", share_ratio=1.0), ts=3.0
    )
    snap = ledger.snapshot()
    replay = Ledger.replay(ledger.entries(), initial_cash=10_000.0)
    assert replay.cash == pytest.approx(snap.cash)
    live_lot = _position(ledger)
    replayed_lot = {p.asset: p for p in replay.positions}["AAA"]
    assert live_lot.quantity == pytest.approx(300.0)
    assert replayed_lot.quantity == pytest.approx(live_lot.quantity)
    assert replayed_lot.avg_cost == pytest.approx(live_lot.avg_cost)
