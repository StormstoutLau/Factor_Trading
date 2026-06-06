"""
P1-2: 部分成交 (PARTIAL) + 订单类型 (TDD)

测试:
1. OrderType 枚举 (MARKET/LIMIT/STOP)
2. OrderStatus.PARTIAL 状态
3. 部分成交场景
4. 限价单执行逻辑
5. 与现有 PendingOrderQueue 的兼容性
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_order_type_enum():
    """测试: OrderType 枚举"""
    print("\n[Test] OrderType 枚举...")

    from core.pending import OrderSide, OrderType

    # 验证枚举值
    assert OrderType.MARKET.value == "market"
    assert OrderType.LIMIT.value == "limit"
    assert OrderType.STOP.value == "stop"
    print(f"  ✓ OrderType: {[t.value for t in OrderType]}")

    return True


def test_partial_status_in_pending_order():
    """测试: PendingOrder 支持 PARTIAL 状态"""
    print("\n[Test] PendingOrder PARTIAL 状态...")

    from core.pending import PendingOrder, OrderSide, OrderStatus, OrderType

    order = PendingOrder("AAPL", OrderSide.BUY, 100, pd.Timestamp("2024-01-02"))
    assert order.status == OrderStatus.PENDING
    assert order.order_type == OrderType.MARKET  # 默认市价单
    print(f"  ✓ 初始状态: {order.status.name}, 类型: {order.order_type.value}")

    # 创建限价单
    limit_order = PendingOrder(
        "GOOGL", OrderSide.BUY, 100, pd.Timestamp("2024-01-02"),
        order_type=OrderType.LIMIT, limit_price=150.0
    )
    assert limit_order.order_type == OrderType.LIMIT
    assert limit_order.limit_price == 150.0
    print(f"  ✓ 限价单: type={limit_order.order_type.value}, price={limit_order.limit_price}")

    # 部分成交
    limit_order.mark_partial(50, 148.0, pd.Timestamp("2024-01-03"))
    assert limit_order.status == OrderStatus.PARTIAL
    assert limit_order.filled_qty == 50
    assert limit_order.remaining_qty == 50
    print(f"  ✓ 部分成交: filled={limit_order.filled_qty}, remaining={limit_order.remaining_qty}")

    # 剩余部分完全成交
    limit_order.mark_executed_full(pd.Timestamp("2024-01-04"), 152.0)
    assert limit_order.status == OrderStatus.EXECUTED
    assert limit_order.filled_qty == 100
    assert limit_order.remaining_qty == 0
    print(f"  ✓ 完全成交: filled={limit_order.filled_qty}, status={limit_order.status.name}")

    return True


def test_limit_order_price_check():
    """测试: 限价单价格检查"""
    print("\n[Test] 限价单价格检查...")

    from core.pending import PendingOrder, OrderSide, OrderType

    # 买入限价单: 只有当价格 <= limit_price 时才成交
    buy_limit = PendingOrder(
        "AAPL", OrderSide.BUY, 100, pd.Timestamp("2024-01-02"),
        order_type=OrderType.LIMIT, limit_price=150.0
    )

    # 价格高于限价，不应成交
    assert not buy_limit.can_execute_at_price(155.0)
    print(f"  ✓ 买入限价150: 价格155 -> 不成交")

    # 价格低于限价，可以成交
    assert buy_limit.can_execute_at_price(145.0)
    print(f"  ✓ 买入限价150: 价格145 -> 可成交")

    # 市价单总是可以成交
    market_order = PendingOrder("AAPL", OrderSide.BUY, 100, pd.Timestamp("2024-01-02"))
    assert market_order.can_execute_at_price(999.0)
    print(f"  ✓ 市价单: 价格999 -> 可成交")

    # 卖出限价单: 只有当价格 >= limit_price 时才成交
    sell_limit = PendingOrder(
        "AAPL", OrderSide.SELL, 100, pd.Timestamp("2024-01-02"),
        order_type=OrderType.LIMIT, limit_price=150.0
    )
    assert not sell_limit.can_execute_at_price(145.0)
    print(f"  ✓ 卖出限价150: 价格145 -> 不成交")
    assert sell_limit.can_execute_at_price(155.0)
    print(f"  ✓ 卖出限价150: 价格155 -> 可成交")

    return True


def test_stop_order_trigger():
    """测试: 止损单触发条件"""
    print("\n[Test] 止损单触发条件...")

    from core.pending import PendingOrder, OrderSide, OrderType

    # 卖出止损单: 当价格 <= stop_price 时触发
    stop_loss = PendingOrder(
        "AAPL", OrderSide.SELL, 100, pd.Timestamp("2024-01-02"),
        order_type=OrderType.STOP, stop_price=140.0
    )

    assert stop_loss.is_triggered(139.0), "价格低于止损价应触发"
    assert not stop_loss.is_triggered(141.0), "价格高于止损价不触发"
    print(f"  ✓ 卖出止损140: 价格139触发, 价格141不触发")

    return True


def test_pending_order_queue_with_partial():
    """测试: PendingOrderQueue 支持部分成交"""
    print("\n[Test] PendingOrderQueue 部分成交统计...")

    from core.pending import PendingOrderQueue, PendingOrder, OrderSide, OrderType, create_pending_order

    queue = PendingOrderQueue()
    date = pd.Timestamp("2024-01-02")

    # 创建限价单
    order = PendingOrder(
        "AAPL", OrderSide.BUY, 100, date,
        order_type=OrderType.LIMIT, limit_price=150.0
    )
    queue.add_order(order)

    stats = queue.get_order_stats()
    assert stats["total_orders"] == 1
    assert stats["pending_orders"] == 1
    print(f"  ✓ 初始统计: {stats}")

    # 部分成交
    order.mark_partial(30, 148.0, pd.Timestamp("2024-01-03"))
    stats = queue.get_order_stats()
    assert stats["partial_orders"] == 1, f"期望1个部分成交，实际{stats['partial_orders']}"
    print(f"  ✓ 部分成交统计: {stats}")

    # 完全成交剩余
    order.mark_executed_full(pd.Timestamp("2024-01-04"), 152.0)
    stats = queue.get_order_stats()
    assert stats["executed_orders"] == 1
    assert stats["partial_orders"] == 0
    print(f"  ✓ 完全成交后统计: {stats}")

    return True


def test_create_order_with_type():
    """测试: create_pending_order 支持订单类型"""
    print("\n[Test] create_pending_order 支持订单类型...")

    from core.pending import create_pending_order, OrderSide, OrderType

    date = pd.Timestamp("2024-01-02")

    # 默认市价单
    o1 = create_pending_order("AAPL", OrderSide.BUY, 100, date)
    assert o1.order_type == OrderType.MARKET
    print(f"  ✓ 默认市价单: {o1.order_type.value}")

    # 限价单
    o2 = create_pending_order(
        "GOOGL", OrderSide.BUY, 100, date,
        order_type=OrderType.LIMIT, limit_price=200.0
    )
    assert o2.order_type == OrderType.LIMIT
    assert o2.limit_price == 200.0
    print(f"  ✓ 限价单: {o2.order_type.value}, price={o2.limit_price}")

    return True


if __name__ == "__main__":
    results = []
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                results.append((name, True))
            except Exception as e:
                print(f"  ✗ FAILED: {e}")
                import traceback
                traceback.print_exc()
                results.append((name, False))

    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"  Results: {passed}/{total} passed")
    print(f"{'='*50}")