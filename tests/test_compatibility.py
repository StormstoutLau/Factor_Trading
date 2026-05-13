"""
兼容性测试

验证:
1. 旧导入路径仍然有效
2. 新模块可以正常工作
3. EventLog 功能正常
4. GuardPipeline 功能正常
5. PluginRegistry 功能正常
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_old_import_paths():
    """测试旧导入路径仍然有效"""
    print("\n[Test] 旧导入路径兼容性...")

    # 旧路径导入
    from config import BacktestConfig, CostConfig, UniverseConfig
    from data import DataManager
    from engine import BacktestEngine
    from factor import FactorPipeline
    from portfolio import BaseOptimizer
    from execution import ExecutionSimulator
    from tracker import PositionTracker
    from rebalance import BaseTrigger
    from pending import PendingOrderQueue
    from analytics import generate_report

    print("  ✓ 所有旧导入路径正常")
    return True


def test_new_import_paths():
    """测试新导入路径有效"""
    print("\n[Test] 新导入路径...")

    from core.config import BacktestConfig
    from core.data import DataManager
    from core.engine import BacktestEngine
    from core.factor import FactorPipeline
    from core.portfolio import BaseOptimizer
    from core.execution import ExecutionSimulator
    from core.tracker import PositionTracker
    from core.rebalance import BaseTrigger
    from core.pending import PendingOrderQueue
    from core.analytics import generate_report

    print("  ✓ 所有新导入路径正常")
    return True


def test_event_log():
    """测试 EventLog 功能"""
    print("\n[Test] EventLog...")

    from core.event_log import EventLog, EventLogEntry

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_events.jsonl"
        el = EventLog(log_path=log_path, buffer_size=10)

        # Test append
        entry1 = el.append("factor.calc", {"factor": "value", "stocks": 100}, source="test")
        assert entry1.seq == 1
        assert entry1.type == "factor.calc"
        print(f"  ✓ Append: seq={entry1.seq}")

        # Test read
        entries = el.read()
        assert len(entries) == 1
        assert entries[0].payload["factor"] == "value"
        print(f"  ✓ Read: {len(entries)} entries")

        # Test subscription
        received = []

        def listener(e):
            received.append(e)

        unsub = el.subscribe(listener)
        el.append("trade.execute", {"symbol": "AAPL", "qty": 100})
        assert len(received) == 1
        assert received[0].type == "trade.execute"
        print(f"  ✓ Subscription: received {received[0].type}")

        unsub()

        # Test type subscription
        type_received = []

        def type_listener(e):
            type_received.append(e)

        unsub_type = el.subscribe_type("agent.decision", type_listener)
        el.append("agent.decision", {"agent": "value"})
        el.append("trade.execute", {"symbol": "TSLA"})  # Should not trigger
        assert len(type_received) == 1
        print(f"  ✓ Type subscription: received {len(type_received)} events")

        unsub_type()

        # Test recovery
        el2 = EventLog(log_path=log_path, buffer_size=10)
        # Note: recovery reads from disk, seq should be preserved
        assert el2.last_seq() >= 2, f"Expected >= 2, got {el2.last_seq()}"
        print(f"  ✓ Recovery: seq={el2.last_seq()}")

        el.reset()

    print("  ✓ EventLog 所有测试通过")
    return True


def test_guard_pipeline():
    """测试 GuardPipeline 功能"""
    print("\n[Test] GuardPipeline...")

    from core.guard_pipeline import (
        GuardContext,
        GuardPipeline,
        MaxPositionGuard,
        DrawdownGuard,
        MinCashGuard,
    )

    ctx = GuardContext(
        action="BUY",
        symbol="AAPL",
        quantity=10,
        price=150.0,
        order_value=1500.0,
        current_positions={},
        current_weights={},
        portfolio_value=100000.0,
        cash=50000.0,
    )

    # Test default pipeline
    pipeline = GuardPipeline.default()
    results = pipeline.check(ctx)
    assert all(r.passed for r in results), f"Some guards failed: {[r.message for r in results if not r.passed]}"
    print(f"  ✓ Default pipeline: all passed ({len(results)} guards)")

    # Test blocking scenario
    ctx2 = GuardContext(
        action="BUY",
        symbol="AAPL",
        quantity=10000,
        price=150.0,
        order_value=1_500_000.0,
        current_positions={},
        current_weights={},
        portfolio_value=100000.0,
        cash=50000.0,
    )
    reasons = pipeline.get_blocking_reasons(ctx2)
    assert len(reasons) > 0
    print(f"  ✓ Blocking: {len(reasons)} reasons")

    # Test conservative pipeline
    conservative = GuardPipeline.conservative()
    results = conservative.check(ctx)
    print(f"  ✓ Conservative pipeline: {len(results)} guards")

    # Test aggressive pipeline
    aggressive = GuardPipeline.aggressive()
    results = aggressive.check(ctx)
    print(f"  ✓ Aggressive pipeline: {len(results)} guards")

    print("  ✓ GuardPipeline 所有测试通过")
    return True


def test_plugin_registry():
    """测试 PluginRegistry 功能"""
    print("\n[Test] PluginRegistry...")

    from core.registry import PluginRegistry, get_optimizer_registry

    # Test basic registry
    reg = PluginRegistry("test")

    def factory(config):
        return {"type": "test", "config": config}

    reg.register("test_plugin", factory, description="Test plugin")
    assert reg.has("test_plugin")
    print("  ✓ Register: test_plugin")

    # Test create
    instance = reg.create("test_plugin", config={"param": 1})
    assert instance["type"] == "test"
    print("  ✓ Create: instance created")

    # Test inventory
    inventory = reg.get_inventory()
    assert len(inventory) == 1
    assert inventory[0]["name"] == "test_plugin"
    print(f"  ✓ Inventory: {len(inventory)} plugins")

    # Test global registry
    opt_reg = get_optimizer_registry()
    assert opt_reg.category == "optimizer"
    print("  ✓ Global registry: optimizer")

    print("  ✓ PluginRegistry 所有测试通过")
    return True


def test_config_creation():
    """测试配置创建"""
    print("\n[Test] Config 兼容性...")

    from config import BacktestConfig, CostConfig, UniverseConfig
    from core.config import BacktestConfig as NewBacktestConfig

    # Old path
    config1 = BacktestConfig(
        data_dir=Path("./data"),
        factor_files=["factor_value.pkl"],
    )

    # New path
    config2 = NewBacktestConfig(
        data_dir=Path("./data"),
        factor_files=["factor_value.pkl"],
    )

    assert type(config1) == type(config2)
    print("  ✓ Config: old and new paths return same type")

    print("  ✓ Config 兼容性测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Factor Trading v3.0 - 兼容性测试")
    print("=" * 60)

    tests = [
        ("旧导入路径", test_old_import_paths),
        ("新导入路径", test_new_import_paths),
        ("EventLog", test_event_log),
        ("GuardPipeline", test_guard_pipeline),
        ("PluginRegistry", test_plugin_registry),
        ("Config兼容性", test_config_creation),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {name} 失败: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
