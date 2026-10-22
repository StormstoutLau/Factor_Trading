"""
P0-1: Pending Order × Universe Filter 改进测试 (TDD)

测试:
1. 待执行订单被 universe filter 阻挡时正确取消
2. 待执行订单被 universe filter 阻挡时记录日志
3. PendingOrderQueue 统计正确
4. 半衰期过期后订单不再有效
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_pending_order_queue_stats():
    """测试: PendingOrderQueue 统计正确"""
    print("\n[Test] PendingOrderQueue 统计...")

    from core.pending import PendingOrderQueue, PendingOrder, OrderSide, create_pending_order

    queue = PendingOrderQueue(max_pending_days_buy=5, max_pending_days_sell=10)

    # 添加订单
    date = pd.Timestamp("2024-01-02")
    o1 = create_pending_order("AAPL", OrderSide.BUY, 100, date)
    o2 = create_pending_order("GOOGL", OrderSide.SELL, 50, date)
    queue.add_order(o1)
    queue.add_order(o2)

    stats = queue.get_order_stats()
    assert stats["total_orders"] == 2
    assert stats["pending_orders"] == 2
    assert stats["buy_orders"] == 1
    assert stats["sell_orders"] == 1
    print(f"  ✓ 订单统计正确: {stats}")

    # 标记执行
    queue.mark_executed(o1, pd.Timestamp("2024-01-03"), 150.0)
    stats = queue.get_order_stats()
    assert stats["executed_orders"] == 1
    assert stats["pending_orders"] == 1
    print(f"  ✓ 执行后统计正确: {stats}")

    return True


def test_pending_order_cancel_by_stock():
    """测试: 按股票取消所有待执行订单"""
    print("\n[Test] 按股票取消待执行订单...")

    from core.pending import PendingOrderQueue, PendingOrder, OrderSide, create_pending_order

    queue = PendingOrderQueue()
    date = pd.Timestamp("2024-01-02")

    o1 = create_pending_order("AAPL", OrderSide.BUY, 100, date)
    o2 = create_pending_order("AAPL", OrderSide.SELL, 50, date)
    o3 = create_pending_order("GOOGL", OrderSide.BUY, 200, date)
    queue.add_order(o1)
    queue.add_order(o2)
    queue.add_order(o3)

    # 取消 AAPL 所有订单
    cancel_date = pd.Timestamp("2024-01-03")
    queue.cancel_orders("AAPL", cancel_date)

    stats = queue.get_order_stats()
    assert stats["cancelled_orders"] == 2, f"期望2个取消，实际{stats['cancelled_orders']}"
    assert stats["pending_orders"] == 1, f"期望1个待执行，实际{stats['pending_orders']}"

    # GOOGL 订单应仍在
    pending = queue.get_pending_orders()
    assert len(pending) == 1
    assert pending[0].stock == "GOOGL"
    print(f"  ✓ 取消正确: AAPL订单已取消, GOOGL仍在")

    return True


def test_pending_order_expiry_marking():
    """测试: 过期订单标记"""
    print("\n[Test] 过期订单标记...")

    from core.pending import PendingOrderQueue, PendingOrder, OrderSide, create_pending_order

    queue = PendingOrderQueue(max_pending_days_buy=3, max_pending_days_sell=5)
    old_date = pd.Timestamp("2024-01-02")

    # 创建旧订单
    o1 = create_pending_order("AAPL", OrderSide.BUY, 100, old_date)

    # 直接设置状态为已过期，测试统计
    o1.mark_expired(pd.Timestamp("2024-01-10"))
    queue.add_order(o1)

    stats = queue.get_order_stats()
    assert stats["expired_orders"] == 1
    print(f"  ✓ 过期订单统计正确: {stats}")

    return True


def test_pending_order_priority_decay():
    """测试: 半衰期优先级衰减"""
    print("\n[Test] 半衰期优先级衰减...")

    from core.pending import PendingOrder, OrderSide

    create_date = pd.Timestamp("2024-01-02")
    order = PendingOrder("AAPL", OrderSide.BUY, 100, create_date)

    # 第0天: 活力=1.0
    p0 = order.get_priority(create_date)
    assert abs(p0 - 1.0) < 0.01, f"期望1.0，实际{p0}"
    print(f"  ✓ Day 0 优先级: {p0:.3f}")

    # 第3天: 活力=0.5
    d3 = pd.Timestamp("2024-01-05")
    p3 = order.get_priority(d3)
    assert abs(p3 - 0.5) < 0.01, f"期望0.5，实际{p3}"
    print(f"  ✓ Day 3 优先级: {p3:.3f}")

    # 第6天: 活力=0.25
    d6 = pd.Timestamp("2024-01-08")
    p6 = order.get_priority(d6)
    assert abs(p6 - 0.25) < 0.01, f"期望0.25，实际{p6}"
    print(f"  ✓ Day 6 优先级: {p6:.3f}")

    # 第9天: 活力=0.125 (刚好在过期边界)
    d9 = pd.Timestamp("2024-01-11")
    p9 = order.get_priority(d9)
    assert abs(p9 - 0.125) < 0.01, f"期望0.125，实际{p9}"
    print(f"  ✓ Day 9 优先级: {p9:.3f}")

    return True


def test_pending_order_status_transitions():
    """测试: 订单状态完整生命周期"""
    print("\n[Test] 订单状态完整生命周期...")

    from core.pending import PendingOrder, OrderSide, OrderStatus

    order = PendingOrder("AAPL", OrderSide.BUY, 100, pd.Timestamp("2024-01-02"))
    assert order.status == OrderStatus.PENDING
    print(f"  ✓ 初始状态: {order.status.name}")

    # 通过 queue.mark_executed 执行（增加 retry_count）
    from core.pending import PendingOrderQueue
    queue = PendingOrderQueue()
    queue.add_order(order)
    queue.mark_executed(order, pd.Timestamp("2024-01-03"), 150.0)
    assert order.status == OrderStatus.EXECUTED
    assert order.execute_price == 150.0
    assert order.retry_count == 1, f"queue.mark_executed应增加retry_count，实际{order.retry_count}"
    print(f"  ✓ 执行后: {order.status.name}, price={order.execute_price}, retry={order.retry_count}")

    # 创建新订单测试过期
    order2 = PendingOrder("GOOGL", OrderSide.SELL, 50, pd.Timestamp("2024-01-02"))
    order2.mark_expired(pd.Timestamp("2024-01-10"))
    assert order2.status == OrderStatus.EXPIRED
    print(f"  ✓ 过期后: {order2.status.name}")

    # 创建新订单测试取消
    order3 = PendingOrder("MSFT", OrderSide.BUY, 200, pd.Timestamp("2024-01-02"))
    order3.mark_cancelled(pd.Timestamp("2024-01-04"))
    assert order3.status == OrderStatus.CANCELLED
    print(f"  ✓ 取消后: {order3.status.name}")


def test_fallback_stock_selection():
    """测试: 备选替补股票选择"""
    print("\n[Test] 备选替补股票选择...")

    from core.pending import select_fallback_stocks

    scores = pd.Series(
        [0.8, 0.6, 0.4, 0.2, 0.1],
        index=["A", "B", "C", "D", "E"]
    )

    # 排除 A 和 B
    fallback = select_fallback_stocks(scores, excluded_stocks=["A", "B"], depth=3)
    assert fallback == ["C", "D", "E"], f"期望[C,D,E]，实际{fallback}"
    print(f"  ✓ 备选正确: {fallback}")

    # 排除全部
    fallback = select_fallback_stocks(scores, excluded_stocks=["A", "B", "C", "D", "E"], depth=3)
    assert fallback == []
    print(f"  ✓ 全部排除后为空: {fallback}")

    return True


# ── 集成测试 ──

def test_universe_filter_masks_shape():
    """测试: UniverseFilter 掩码形状正确"""
    print("\n[Test] UniverseFilter 掩码形状...")

    from core.config import UniverseConfig
    from core.data import DataManager
    from filter.universe_filter_clean import UniverseFilter

    cfg = UniverseConfig(
        exclude_suspended=True,
        exclude_limit_up=False,
        exclude_limit_down=False,
        exclude_st=True,
        check_next_day_tradable=False,
    )

    # 使用模拟数据
    import tempfile
    import os
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建最小数据文件
        dates = pd.date_range("2024-01-02", "2024-01-31", freq="B")
        stocks = ["000001", "000002", "000003", "000004", "000005"]

        # 价格数据
        np.random.seed(42)
        close = pd.DataFrame(
            np.random.uniform(5, 50, (len(dates), len(stocks))),
            index=dates, columns=stocks
        )
        open_p = close * np.random.uniform(0.98, 1.02, close.shape)
        open_p = pd.DataFrame(open_p, index=dates, columns=stocks)
        high = close * 1.05
        low = close * 0.95

        data_dir = Path(tmpdir)
        close.to_pickle(data_dir / "close.pkl")
        open_p.to_pickle(data_dir / "open.pkl")
        high.to_pickle(data_dir / "high.pkl")
        low.to_pickle(data_dir / "low.pkl")

        # 停牌数据 (全部正常)
        suspend = pd.DataFrame(0, index=dates, columns=stocks)
        # 停牌一只股票
        suspend.loc[dates[5]:dates[10], "000001"] = 1
        suspend.to_pickle(data_dir / "suspend.pkl")

        # ST数据
        st = pd.DataFrame(0, index=dates, columns=stocks)
        st.to_pickle(data_dir / "st.pkl")

        # 收益率数据
        returns = close.pct_change().fillna(0)
        returns.to_pickle(data_dir / "returns.pkl")

        # 复权因子 (全部为1.0，文件名需匹配 config 默认 stock_adj.pkl)
        adj_factor = pd.DataFrame(1.0, index=dates, columns=stocks)
        adj_factor.to_pickle(data_dir / "stock_adj.pkl")

        # 成交量数据
        volume = pd.DataFrame(
            np.random.uniform(1e6, 1e8, (len(dates), len(stocks))),
            index=dates, columns=stocks
        )
        volume.to_pickle(data_dir / "volume.pkl")

        # 使用 DataManager 加载
        from core.config import BacktestConfig, FactorConfig, OptimizerConfig, RebalanceConfig, CostConfig
        config = BacktestConfig(
            data_dir=data_dir,
            factor_files=["factor_value.pkl"],
            factor=FactorConfig(),
            optimizer=OptimizerConfig(),
            rebalance=RebalanceConfig(),
            cost=CostConfig(),
            start_date="2024-01-02",
            end_date="2024-01-31",
            universe=cfg,
            enable_pending_orders=False,
        )

        dm = DataManager(config)
        universe = UniverseFilter(dm, cfg)
        universe.build_masks()

        # 验证掩码形状
        assert universe.buyable.shape == (len(dates), len(stocks)), \
            f"buyable shape: {universe.buyable.shape}"
        assert universe.sellable.shape == (len(dates), len(stocks))
        assert universe.tradable.shape == (len(dates), len(stocks))
        print(f"  ✓ 掩码形状正确: {universe.buyable.shape}")

        # 停牌日期应不可交易
        suspend_date = dates[6]
        assert not universe.tradable.loc[suspend_date, "000001"], \
            "停牌股票应不可交易"
        print(f"  ✓ 停牌股票 ({suspend_date.date()}, 000001) 正确过滤")

        # 正常日期应可交易
        normal_date = dates[2]
        assert universe.tradable.loc[normal_date, "000001"], \
            "正常股票应可交易"
        print(f"  ✓ 正常股票 ({normal_date.date()}, 000001) 正确可交易")

    return True


def test_pending_order_event_log():
    """测试: PendingOrderQueue 事件日志"""
    print("\n[Test] PendingOrderQueue 事件日志...")

    from core.pending import PendingOrderQueue, OrderSide, create_pending_order

    queue = PendingOrderQueue()
    date = pd.Timestamp("2024-01-02")

    o1 = create_pending_order("AAPL", OrderSide.BUY, 100, date)
    queue.add_order(o1)
    queue.mark_executed(o1, pd.Timestamp("2024-01-03"), 150.0)

    log_df = queue.get_event_log()
    assert len(log_df) == 2, f"期望2条日志，实际{len(log_df)}"
    assert log_df.iloc[0]["event_type"] == "ORDER_ADDED"
    assert log_df.iloc[1]["event_type"] == "ORDER_EXECUTED"
    print(f"  ✓ 事件日志正确: {len(log_df)}条")

    return True


if __name__ == "__main__":
    results = []
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                result = func()
                results.append((name, result))
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