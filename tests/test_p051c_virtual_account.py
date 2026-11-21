"""P-051c A 组：虚拟子账户与预算校验（10 条）。"""

from __future__ import annotations

import pytest

from core.virtual_account import (
    BudgetCheck,
    VirtualAccount,
    check_allocation,
    check_book,
)


def _account() -> VirtualAccount:
    return VirtualAccount(
        strategy_id="s1",
        cash=1000.0,
        reserved=200.0,
        positions={"000001": 300.0},
        total=1500.0,
    )


def _booked(account: VirtualAccount) -> float:
    return account.cash + account.reserved + sum(account.positions.values())


def test_a1_conservation_enforced():
    account = _account()
    assert _booked(account) == pytest.approx(account.total)
    with pytest.raises(ValueError, match="不守恒"):
        VirtualAccount(
            strategy_id="s1", cash=1000.0, reserved=200.0, positions={"000001": 300.0}, total=1600.0
        )
    with pytest.raises(ValueError, match="cash"):
        VirtualAccount(strategy_id="s1", cash=-1.0, reserved=0.0, positions={}, total=-1.0)


def test_a2_try_reserve_success():
    updated, ok = _account().try_reserve(100.0)
    assert ok is True
    assert updated.cash == pytest.approx(900.0)
    assert updated.reserved == pytest.approx(300.0)
    assert updated.total == pytest.approx(1500.0)
    assert _booked(updated) == pytest.approx(updated.total)


def test_a3_try_reserve_insufficient_returns_self():
    account = _account()
    same, ok = account.try_reserve(1001.0)
    assert ok is False
    assert same is account


def test_a4_release_moves_reserved_to_cash():
    released = _account().release(50.0)
    assert released.cash == pytest.approx(1050.0)
    assert released.reserved == pytest.approx(150.0)
    assert released.total == pytest.approx(1500.0)
    with pytest.raises(ValueError, match="reserved"):
        _account().release(201.0)


def test_a5_fill_moves_reserved_to_positions():
    filled = _account().fill("600000", 100.0)
    assert filled.reserved == pytest.approx(100.0)
    assert filled.positions["600000"] == pytest.approx(100.0)
    assert filled.positions["000001"] == pytest.approx(300.0)
    assert filled.cash == pytest.approx(1000.0)
    assert _booked(filled) == pytest.approx(filled.total)


def test_a6_partial_fill_then_release_conserves():
    reserved, ok = _account().try_reserve(200.0)
    assert ok is True
    partial = reserved.fill("600000", 150.0)
    remainder = partial.release(250.0)
    assert remainder.cash == pytest.approx(1050.0)
    assert remainder.reserved == pytest.approx(0.0)
    assert remainder.positions["600000"] == pytest.approx(150.0)
    assert _booked(remainder) == pytest.approx(remainder.total)


def test_a7_fill_over_reserved_raises():
    with pytest.raises(ValueError, match="reserved"):
        _account().fill("600000", 300.0)
    with pytest.raises(ValueError):
        _account().fill("600000", 0.0)


def test_a8_allocate_leaves_positions_and_reserved():
    account = _account()
    funded = account.allocate(500.0)
    assert funded.cash == pytest.approx(1500.0)
    assert funded.total == pytest.approx(2000.0)
    assert funded.reserved == account.reserved
    assert dict(funded.positions) == dict(account.positions)
    withdrawn = funded.allocate(-500.0)
    assert withdrawn.cash == pytest.approx(account.cash)
    assert withdrawn.total == pytest.approx(account.total)
    with pytest.raises(ValueError, match="cash"):
        account.allocate(-1001.0)
    with pytest.raises(ValueError, match="不得为零"):
        account.allocate(0.0)


def test_a9_allocation_violations():
    result = check_allocation({"A": -0.1, "B": 0.8, "C": 0.5}, 1_000_000.0, max_weight=0.6)
    assert result.ok is False
    assert "negative:A" in result.violations
    assert "max_weight:B" in result.violations
    assert "sum" in result.violations
    assert check_allocation({"A": 0.5, "B": 0.5}, 1_000_000.0).ok is True


def test_a10_book_check_and_chain_conservation():
    first = VirtualAccount("s1", cash=600.0, reserved=0.0, positions={"X": 400.0}, total=1000.0)
    second = VirtualAccount("s2", cash=500.0, reserved=0.0, positions={}, total=500.0)
    book = {"s1": first, "s2": second}
    assert check_book(book, 1500.0) == BudgetCheck(ok=True, violations=())
    over = check_book(book, 1400.0)
    assert over.ok is False
    assert "over_allocated" in over.violations

    account = first
    account, ok = account.try_reserve(50.0)
    assert ok is True
    assert _booked(account) == pytest.approx(account.total)
    account = account.fill("Y", 40.0)
    assert _booked(account) == pytest.approx(account.total)
    account = account.release(10.0)
    assert _booked(account) == pytest.approx(account.total)
    assert account.positions["Y"] == pytest.approx(40.0)
    assert account.total == pytest.approx(1000.0)
