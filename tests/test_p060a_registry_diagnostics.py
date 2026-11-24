"""P-060a 插件注册表 / 日级诊断 / 事件日志单元测试（T-A20..A23）。

对应 [IMPL_p060a §4.5](../../docs/IMPL_p060a_implementation.md)：零生产改动。
外部对照：X28 pluggy（重名报错）、X29 stevedore（重名覆盖）——本仓 register 取 X29 语义。
"""

from __future__ import annotations

import pandas as pd
import pytest

from core import registry as reg_mod
from core.diagnostics import DayErrorCollector
from core.event_log import EventLog
from core.registry import PluginRegistry

DAY = pd.Timestamp("2024-01-02")


# ---------------------------------------------------------------------------
# T-A20 注册表核心操作
# ---------------------------------------------------------------------------


def test_p060a_a20_registry_crud_and_error_paths():
    """T-A20 | oracle=contract：重名覆盖、注销缺失 False、未注册 KeyError、工厂异常透传"""
    reg: PluginRegistry[int] = PluginRegistry("test")
    reg.register("a", lambda config=None, **kw: 1, description="A")

    assert reg.has("a") is True
    assert reg.list_names() == ["a"]
    entry = reg.get("a")
    assert entry is not None and entry.description == "A"

    reg.register("a", lambda config=None, **kw: 2)  # 重名覆盖（X29 语义）
    assert reg.create("a") == 2

    assert reg.unregister("a") is True
    assert reg.unregister("a") is False
    assert reg.get("missing") is None

    with pytest.raises(KeyError, match="not found"):
        reg.create("missing")

    def boom(config=None, **kw):
        raise RuntimeError("factory boom")

    reg.register("boom", boom)
    with pytest.raises(RuntimeError, match="factory boom"):
        reg.create("boom")


# ---------------------------------------------------------------------------
# T-A21 create_or_default
# ---------------------------------------------------------------------------


def test_p060a_a21_create_or_default_falls_back_with_config():
    """T-A21 | oracle=contract：未注册走默认；config/kwargs 透传；双缺失抛 KeyError"""
    reg: PluginRegistry[tuple] = PluginRegistry("test")
    reg.register("base", lambda config=None, **kw: (config, kw.get("x")))

    assert reg.create_or_default("missing", "base", config=7, x=9) == (7, 9)
    assert reg.create_or_default("base", "missing", config=7, x=9) == (7, 9)

    with pytest.raises(KeyError):
        reg.create_or_default("missing", "missing")


# ---------------------------------------------------------------------------
# T-A22 六类注册装饰器 + inventory
# ---------------------------------------------------------------------------


def test_p060a_a22_decorators_register_and_inventory():
    """T-A22 | oracle=contract：六类装饰器返回原工厂、登记可见、可注销"""
    cases = [
        (reg_mod.register_optimizer, reg_mod.get_optimizer_registry, "p060a_opt"),
        (reg_mod.register_trigger, reg_mod.get_trigger_registry, "p060a_trigger"),
        (reg_mod.register_filter, reg_mod.get_filter_registry, "p060a_filter"),
        (reg_mod.register_guard, reg_mod.get_guard_registry, "p060a_guard"),
        (reg_mod.register_agent, reg_mod.get_agent_registry, "p060a_agent"),
        (reg_mod.register_strategy, reg_mod.get_strategy_registry, "p060a_strategy"),
    ]

    for decorate, getter, name in cases:

        @decorate(name, description="p060a")
        def factory(config=None, **kwargs):
            return "ok"

        assert callable(factory)
        registry = getter()
        assert registry.has(name) is True
        inventory = {row["name"]: row for row in registry.get_inventory()}
        assert inventory[name]["description"] == "p060a"
        assert inventory[name]["category"]
        assert registry.unregister(name) is True


# ---------------------------------------------------------------------------
# T-A23 日级诊断 / 事件日志
# ---------------------------------------------------------------------------


def test_p060a_a23_diagnostics_and_event_log(tmp_path):
    """T-A23 | oracle=contract：分类/去重/降级/raise/off；事件日志双写/过滤/订阅/重置"""
    collector = DayErrorCollector("report")
    first = collector.record(DAY, "execution", ValueError("order rejected"))
    assert first is not None
    assert first.category == "execution" and first.retryable is True

    collector.record(DAY, "execution", ValueError("order rejected"))  # 去重：计数 +1，样本不重复
    summary = collector.summary()
    assert summary["counts"] == {"execution": 2}
    assert len(summary["samples"]) == 1
    assert summary["degraded"] is False

    collector.record(DAY, "day_loop", KeyError("missing col"))  # data → degraded
    assert collector.summary()["degraded"] is True

    strict = DayErrorCollector("raise")
    strict.record(DAY, "day_loop", KeyError("missing col"))
    with pytest.raises(ExceptionGroup, match="日级异常"):
        strict.raise_if_needed()

    off = DayErrorCollector("off")
    assert off.record(DAY, "execution", ValueError("x")) is None
    assert off.summary() == {"mode": "off"}

    log = EventLog(tmp_path / "events.jsonl", buffer_size=2)
    seen: list[object] = []
    unsub_all = log.subscribe(lambda e: seen.append(e.seq))
    unsub_type = log.subscribe_type("trade.execute", lambda e: seen.append(("t", e.seq)))

    e1 = log.append("trade.execute", {"qty": 1}, source="test")
    e2 = log.append("factor.calc", {"f": 2})
    e3 = log.append("trade.execute", {"qty": 3})

    assert [e1.seq, e2.seq, e3.seq] == [1, 2, 3]
    assert log.last_seq() == 3
    assert [e.seq for e in log.recent()] == [2, 3]  # ring buffer 只留最近 2 条
    assert [e.seq for e in log.recent(event_type="trade.execute")] == [3]
    assert [e.seq for e in log.read()] == [1, 2, 3]
    assert [e.seq for e in log.read(after_seq=1, limit=1)] == [2]
    assert set(log.stats()) >= {"read_failures", "write_failures", "skipped_lines"}
    assert seen == [1, ("t", 1), 2, 3, ("t", 3)]

    unsub_all()
    unsub_type()
    log.append("trade.execute", {"qty": 4})
    assert seen == [1, ("t", 1), 2, 3, ("t", 3)]

    log.close()
    log.reset()
    assert log.last_seq() == 0
    assert not (tmp_path / "events.jsonl").exists()
