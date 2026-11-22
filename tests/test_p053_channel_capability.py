"""P-053 T 组：通道能力与限额（T1，10 例）。"""

from __future__ import annotations

import pytest

from live.channel import (
    CapabilityError,
    ChannelCapability,
    ChannelRejected,
    ChannelState,
    SubmitAck,
    require_capability,
    resolve_limits,
)
from live.orders import OrderState


def _cap(**overrides) -> ChannelCapability:
    base = dict(
        channel_id="mock",
        venue="mock",
        account_level="cash",
        products=("stock",),
        supports_client_order_id=True,
        supports_cancel=True,
        supports_query_orders=True,
        supports_query_trades=True,
        supports_query_positions=True,
        autonomous=True,
        report_registered=True,
        max_submit_per_sec=50.0,
        max_submit_per_day=100_000,
        max_cancel_per_sec=20.0,
        max_query_per_sec=10.0,
    )
    base.update(overrides)
    return ChannelCapability(**base)


def test_t1_missing_cancel_raises_with_key():
    with pytest.raises(CapabilityError, match="cancel"):
        require_capability(_cap(supports_cancel=False), need=frozenset({"cancel"}))


def test_t1_report_registered_false_rejected():
    with pytest.raises(CapabilityError, match="report_registered"):
        require_capability(_cap(report_registered=False), need=frozenset({"report_registered"}))


def test_t1_product_gate():
    with pytest.raises(CapabilityError, match="future"):
        require_capability(_cap(products=("stock",)), need=frozenset({"future"}))
    require_capability(_cap(products=("stock", "future")), need=frozenset({"future"}))


def test_t1_resolve_limits_internal_lower():
    limits = resolve_limits(_cap(), internal_per_sec=5.0, internal_per_day=1000)
    assert limits.submit_per_sec == 5.0
    assert limits.submit_per_day == 1000


def test_t1_resolve_limits_channel_lower():
    limits = resolve_limits(
        _cap(max_submit_per_sec=8.0, max_submit_per_day=500),
        internal_per_sec=100.0,
        internal_per_day=10_000,
    )
    assert limits.submit_per_sec == 8.0
    assert limits.submit_per_day == 500


def test_t1_resolve_limits_regulator_ceiling():
    limits = resolve_limits(
        _cap(max_submit_per_sec=1000.0, max_submit_per_day=100_000),
        internal_per_sec=1000.0,
        internal_per_day=100_000,
    )
    assert limits.submit_per_sec == 300.0  # 监管秒级兜底
    assert limits.submit_per_day == 20_000  # 监管日级兜底


def test_t1_query_limit_independent_from_submit():
    limits = resolve_limits(
        _cap(max_submit_per_sec=50.0, max_query_per_sec=1.0),
        internal_per_sec=50.0,
        internal_per_day=10_000,
    )
    assert limits.query_per_sec == 1.0
    assert limits.submit_per_sec == 50.0


def test_t1_channel_rejected_keeps_code_and_reason():
    exc = ChannelRejected("E42", "risk limit")
    assert exc.code == "E42"
    assert exc.reason == "risk limit"
    assert "E42" in str(exc)


def test_t1_submit_ack_constructible():
    ack = SubmitAck("co_1", "b_1", OrderState.PENDING_NEW, 1.5)
    assert ack.client_order_id == "co_1"
    assert ack.broker_order_id == "b_1"
    assert ack.state is OrderState.PENDING_NEW
    assert ack.ts == 1.5


def test_t1_channel_state_values_fixed():
    assert [s.value for s in ChannelState] == [
        "disconnected",
        "connecting",
        "connected",
        "degraded",
        "halted",
    ]
