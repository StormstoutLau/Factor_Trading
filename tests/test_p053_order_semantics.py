"""P-053 T 组：订单状态语义（T2，14 例）。"""

from __future__ import annotations

import pytest

from live.orders import (
    OrderRecord,
    OrderRequest,
    OrderState,
    OrderTransitionError,
    from_request,
    make_client_order_id,
    transition,
)


def _coid_kwargs(**overrides):
    base = dict(
        strategy_id="S1",
        account_id="ACC",
        asset="AAA",
        side="BUY",
        quantity=100.0,
        price=10.0,
        signal_ts=1_700_000_000.0,
    )
    base.update(overrides)
    return base


def _request(**overrides) -> OrderRequest:
    base = dict(
        asset="AAA",
        side="BUY",
        quantity=100.0,
        asset_type="stock",
        price=10.0,
        order_type="limit",
        client_order_id="co_test",
        account_id="ACC",
        strategy_id="S1",
        signal_ts=1_700_000_000.0,
    )
    base.update(overrides)
    return OrderRequest(**base)


def _record(state: OrderState = OrderState.PENDING_NEW, *, filled: float = 0.0) -> OrderRecord:
    return OrderRecord(
        client_order_id="co_test",
        broker_order_id="",
        asset="AAA",
        side="BUY",
        quantity=100.0,
        filled_quantity=filled,
        avg_price=0.0,
        state=state,
        created_ts=1.0,
        updated_ts=1.0,
    )


def test_t2_client_order_id_deterministic():
    a = make_client_order_id(**_coid_kwargs())
    b = make_client_order_id(**_coid_kwargs())
    assert a == b


def test_t2_client_order_id_differs_on_input():
    a = make_client_order_id(**_coid_kwargs())
    b = make_client_order_id(**_coid_kwargs(quantity=200.0))
    assert a != b


def test_t2_client_order_id_prefix_and_length():
    cid = make_client_order_id(**_coid_kwargs())
    assert cid.startswith("co_")
    assert len(cid) == 19  # "co_" + 16 hex


def test_t2_from_request_pending_new():
    rec = from_request(_request(), ts=42.0)
    assert rec.state is OrderState.PENDING_NEW
    assert rec.client_order_id == "co_test"
    assert rec.filled_quantity == 0.0
    assert rec.avg_price == 0.0
    assert rec.created_ts == 42.0


def test_t2_pending_new_to_new():
    rec = transition(_record(), state=OrderState.NEW, ts=2.0)
    assert rec.state is OrderState.NEW


def test_t2_pending_new_to_instant_fill_and_ack_backfill():
    direct = transition(_record(), state=OrderState.FILLED, ts=2.0, filled_quantity=100.0)
    assert direct.state is OrderState.FILLED  # F-R5-7：A→2 直接秒成交（非经 PF 中转）
    part = transition(_record(), state=OrderState.PARTIALLY_FILLED, ts=2.0, filled_quantity=40.0)
    assert part.state is OrderState.PARTIALLY_FILLED
    filled = transition(part, state=OrderState.FILLED, ts=3.0, filled_quantity=100.0)
    assert filled.state is OrderState.FILLED
    # 同态 ack 回填：只补 broker_order_id（F-I5）
    acked = transition(_record(), state=OrderState.PENDING_NEW, ts=5.0, broker_order_id="b1")
    assert acked.broker_order_id == "b1"
    assert acked.state is OrderState.PENDING_NEW


def test_t2_pending_new_to_rejected():
    rec = transition(
        _record(),
        state=OrderState.REJECTED,
        ts=2.0,
        reject_code="E1",
        reject_reason="bad",
    )
    assert rec.state is OrderState.REJECTED
    assert rec.reject_code == "E1"
    assert rec.reject_reason == "bad"


def test_t2_new_to_canceled():
    rec = transition(_record(OrderState.NEW), state=OrderState.CANCELED, ts=2.0)
    assert rec.state is OrderState.CANCELED


def test_t2_partial_self_loop_then_filled():
    part = _record(OrderState.PARTIALLY_FILLED, filled=40.0)
    more = transition(part, state=OrderState.PARTIALLY_FILLED, ts=2.0, filled_quantity=70.0)
    assert more.filled_quantity == 70.0
    filled = transition(more, state=OrderState.FILLED, ts=3.0, filled_quantity=100.0)
    assert filled.state is OrderState.FILLED


def test_t2_pending_cancel_self_loop_then_canceled():
    pc = _record(OrderState.PENDING_CANCEL)
    again = transition(pc, state=OrderState.PENDING_CANCEL, ts=2.0)
    assert again.state is OrderState.PENDING_CANCEL
    done = transition(again, state=OrderState.CANCELED, ts=3.0)
    assert done.state is OrderState.CANCELED


def test_t2_unknown_can_resolve_to_new():
    rec = transition(_record(OrderState.UNKNOWN), state=OrderState.NEW, ts=2.0)
    assert rec.state is OrderState.NEW


def test_t2_terminal_states_irreversible():
    for terminal in (
        OrderState.FILLED,
        OrderState.CANCELED,
        OrderState.REJECTED,
        OrderState.EXPIRED,
    ):
        with pytest.raises(OrderTransitionError, match="terminal"):
            transition(_record(terminal), state=OrderState.PENDING_CANCEL, ts=2.0)


def test_t2_filled_quantity_regression_raises():
    rec = _record(OrderState.NEW, filled=50.0)
    with pytest.raises(OrderTransitionError, match="regressed"):
        transition(rec, state=OrderState.PARTIALLY_FILLED, ts=2.0, filled_quantity=40.0)


def test_t2_filled_quantity_exceeds_quantity_raises():
    with pytest.raises(OrderTransitionError, match="> quantity"):
        transition(
            _record(OrderState.NEW),
            state=OrderState.PARTIALLY_FILLED,
            ts=2.0,
            filled_quantity=150.0,
        )
