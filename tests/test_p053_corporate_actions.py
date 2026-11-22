"""P-053 T 组：公司行为与先归因（T8，8 例）。"""

from __future__ import annotations

import pytest

from live.corporate_actions import (
    ActionType,
    CorporateAction,
    actions_for,
    adjust_position,
    attribute_break,
    load_actions,
)
from live.ledger import PositionLot
from live.reconcile import Break, BreakLevel


def _lot(quantity: float = 100.0, avg_cost: float = 10.0) -> PositionLot:
    return PositionLot("AAA", quantity, avg_cost)


def _action(action_type: ActionType, **overrides) -> CorporateAction:
    base = dict(action_id="ca1", asset="AAA", action_type=action_type, ex_date="2026-01-05")
    base.update(overrides)
    return CorporateAction(**base)


def test_t8_cash_dividend():
    lot, cash = adjust_position(_lot(), _action(ActionType.CASH_DIVIDEND, cash_per_share=0.5))
    assert cash == pytest.approx(50.0)
    assert lot.quantity == 100.0


def test_t8_stock_dividend():
    lot, cash = adjust_position(_lot(), _action(ActionType.STOCK_DIVIDEND, share_ratio=0.5))
    assert cash == 0.0
    assert lot.quantity == pytest.approx(150.0)
    assert lot.avg_cost == pytest.approx(10.0 / 1.5)


def test_t8_split():
    lot, cash = adjust_position(_lot(), _action(ActionType.SPLIT, share_ratio=1.0))
    assert cash == 0.0
    assert lot.quantity == pytest.approx(200.0)
    assert lot.avg_cost == pytest.approx(5.0)


def test_t8_rights_issue_no_cash_deduction():
    lot, cash = adjust_position(
        _lot(), _action(ActionType.RIGHTS_ISSUE, share_ratio=0.3, price=5.0)
    )
    assert cash == 0.0
    assert lot.quantity == pytest.approx(130.0)


def test_t8_load_actions_missing_column_raises():
    with pytest.raises(ValueError, match="missing columns"):
        load_actions([{"action_id": "ca1"}])


def test_t8_actions_for_filters_by_date():
    rows = [
        {"action_id": "ca1", "asset": "AAA", "action_type": "split", "ex_date": "2026-01-05"},
        {"action_id": "ca2", "asset": "AAA", "action_type": "split", "ex_date": "2026-01-06"},
    ]
    actions = load_actions(
        [
            {**rows[0], "cash_per_share": "0", "share_ratio": "1", "price": "0", "note": ""},
            {**rows[1], "cash_per_share": "0", "share_ratio": "1", "price": "0", "note": ""},
        ]
    )
    selected = actions_for(actions, asset="AAA", ex_date="2026-01-05")
    assert [a.action_id for a in selected] == ["ca1"]


def test_t8_attribute_break_cash_to_missed():
    brk = Break("cash", "AAA", 1000.0, 800.0, 200.0, BreakLevel.UNRESOLVED)
    action = _action(ActionType.CASH_DIVIDEND, cash_per_share=0.2)
    attributed = attribute_break(brk, actions=(action,))
    assert attributed.level is BreakLevel.MISSED
    assert attributed.note == "ca1"


def test_t8_attribute_break_unknown_asset_unchanged():
    brk = Break("position", "BBB", 200.0, 100.0, 100.0, BreakLevel.UNRESOLVED)
    action = _action(ActionType.SPLIT, share_ratio=1.0)
    assert attribute_break(brk, actions=(action,)) == brk
