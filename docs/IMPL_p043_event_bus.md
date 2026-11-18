# IMPL：P-043 事件总线（EventLog 接入引擎）

> **批次**: P-043 · **Step 5 实施规划** · 日期 2026-11-18
> **判档**: **T1**（`core/event_log.py` 契约 + `core/engine_v2.py` 运行时 + `core/config.py` 字段 + `tests/`）
> **上游**: [DESIGN_p043_event_bus.md](DESIGN_p043_event_bus.md)（D1-D8 / §10 Step 4 Review pass：0 P1/P2 + 5 P3 当轮处置）
> **代码时点**: HEAD `1306bf8`（行号为该时点；插入后位移，以锚点文字为准）
> **基座**: DeepSeek-V4.1-Flash（Step 6 Review 同源；终审须 GLM-5.3-Flash，U-P043-5）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 落地批次 | B1 契约（`event_log.py`）→ B2 引擎接入（`config.py` + `engine_v2.py`）→ B3 测试（`test_p043_event_bus.py`） |
| 行为变更 | **默认零变更**（`event_log_path=None` 且无注入）；启用时新增旁路 `*.jsonl` 与结果键 `additional_info["event_bus"]` |
| 不触碰 | 复权/对齐/掩膜/交易/净值/`pending_order_events.csv`/`run_diagnostics`/layer dump/manifest 结构/`EventLogPlugin` |
| 零预填 | 本文件 §9（Step 6）与 §10（Step 9）为占位，实测后回填 |

---

## 2. 任务拆解

| 批 | 文件 | 改动 |
|----|------|------|
| **B1** | `core/event_log.py` | typing import +2；`EventType`（5 常量）+ `IEventBus`（4 方法 Protocol，`@runtime_checkable`）+ `EventLog.replay`（+3 符号） |
| **B2** | `core/config.py` | `event_log_path: Path \| None = None`（+1 字段） |
| **B2** | `core/engine_v2.py` | import +1；`__init__` +1 参数 / +3 属性；`setup()` +步骤 14；`_emit` 新方法；**6 处发射**；结果键 +1 |
| **B3** | `tests/test_p043_event_bus.py` | 新建，V1-V8（8 用例） |

依赖：B2 依赖 B1；B3 与 B2 同批提交。三批可独立 revert。

---

## 3. 接口签名与实现规格

### 3.1 B1：`core/event_log.py`

**① typing import（L21）**：

```python
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)
```

**② 新增符号（`EventListener` L39 之后、`class EventLog` L42 之前）**：

```python
class EventType:
    """引擎生命周期事件类型（单一来源；引擎侧禁止写裸字符串）"""

    RUN_STARTED = "engine.run_started"
    REBALANCE = "engine.rebalance"
    DAY_END = "engine.day_end"
    ERROR = "engine.error"
    RUN_FINISHED = "engine.run_finished"


@runtime_checkable
class IEventBus(Protocol):
    """事件总线最小契约（P-043 D1）：append 写入 / last_seq 读游标 / read 回放读 / subscribe 订阅"""

    def append(
        self, event_type: str, payload: dict[str, Any], source: str = ""
    ) -> EventLogEntry: ...

    def last_seq(self) -> int: ...

    def read(
        self,
        after_seq: int = 0,
        limit: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> list[EventLogEntry]: ...

    def subscribe(self, listener: EventListener) -> Callable[[], None]: ...
```

**③ `EventLog.replay`（`read` L172 之后、`query` L174 之前）**：

```python
    def replay(
        self,
        after_seq: int = 0,
        handler: Optional[EventListener] = None,
    ) -> list[EventLogEntry]:
        """重放磁盘事件：``seq > after_seq`` 升序全集。

        与订阅监听器不同，``handler`` 异常**向外传播**（P-043 D5）——
        重放消费方必须可失败，不得静默丢事件。
        """
        entries = self.read(after_seq=after_seq)
        if handler is not None:
            for entry in entries:
                handler(entry)
        return entries
```

**零行为**：既有 `append` / `read` / `subscribe` / `_recover_state` 逐字不动。

### 3.2 B2：`core/config.py`

`dump_layers_dir`（L343）之后插入：

```python
    event_log_path: Path | None = None  # 事件总线输出路径（P-043）；None=关闭（零 I/O）
```

`Path` 已在 L12 导入（F-S6-P043-2 订正）；`manifest._jsonable` 已支持 `Path|None`（L33-56）→ manifest 序列化安全。

### 3.3 B2：`core/engine_v2.py`

**① import（`from core.data import DataManager` 之后）**：

```python
from core.event_log import EventLog, EventType, IEventBus
```

**② `__init__` 参数表（`risk_manager` 之后追加）**：

```python
        event_bus: Optional[IEventBus] = None,
```

文档字符串追加一行：

```python
            event_bus: 事件总线（可选，默认None=关闭；优先于 cfg.event_log_path）
```

**③ 属性（三处）**：

```python
        # 注入的组件（或None，由setup创建）
        self._injected_pending_queue = pending_queue
        self._injected_event_bus = event_bus          # ← 新增
```

```python
        # 实际使用的组件（setup后填充）
        ...
        self.pending_queue: Optional[IPendingOrderQueue] = None
        self._event_bus: Optional[IEventBus] = None   # ← 新增
        self._event_bus_errors: int = 0               # ← 新增
```

**④ `setup()` 步骤 14（协方差预检 L297-308 之后、`elapsed` L310 之前）**：

```python
        # 14. 事件总线（P-043 D2）：默认关闭零 I/O；注入优先，且不创建第二实例
        if self._injected_event_bus is not None:
            self._event_bus = self._injected_event_bus
            if self.cfg.event_log_path is not None:
                logger.info(
                    "已注入事件总线，忽略 cfg.event_log_path=%s", self.cfg.event_log_path
                )
        elif self.cfg.event_log_path is not None:
            self._event_bus = EventLog(log_path=self.cfg.event_log_path)
            logger.info("事件总线已启用: %s", self.cfg.event_log_path)
        else:
            self._event_bus = None
```

**⑤ `_emit`（`_process_trading_day` L394 之前）**：

```python
    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """发射引擎域事件（P-043 D4）：总线故障永不改变回测流程。"""
        bus = self._event_bus
        if bus is None:
            return
        try:
            bus.append(event_type, payload, source="engine_v2")
        except Exception as exc:  # noqa: BLE001 — 总线路由不得改变回测流程
            self._event_bus_errors += 1
            logger.debug("事件总线写入失败（不影响回测）: %s", exc)
```

**⑥ `run()` 三处（L351-L356 整块替换）**：

```python
        t0 = time.perf_counter()
        self._run_started_at = datetime.now()
        logger.info("开始回测...")

        trade_dates = self.dm.trade_dates
        self._emit(
            EventType.RUN_STARTED,
            {
                "start": trade_dates[0].strftime("%Y-%m-%d"),
                "end": trade_dates[-1].strftime("%Y-%m-%d"),
                "n_dates": int(len(trade_dates)),
            },
        )

        last_date_index = len(trade_dates) - 1
        for i, date in enumerate(trade_dates):
```

`except` 块（`_diagnostics.record` 之后、`logger.error` 之前）：

```python
            except Exception as e:
                self._diagnostics.record(date, "day_loop", e)
                self._emit(
                    EventType.ERROR,
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "stage": "day_loop",
                        "error_type": type(e).__name__,
                        "message": str(e)[: self._diagnostics.MAX_MESSAGE],
                    },
                )
                logger.error(f"处理交易日 {date} 时发生错误: {e}")
```

`elapsed` 之后、`logger.info(f"回测完成...")` 之前：

```python
        elapsed = time.perf_counter() - t0
        self._emit(
            EventType.RUN_FINISHED,
            {"elapsed_s": float(elapsed), "n_days": int(len(self.dm.trade_dates))},
        )
        logger.info(f"回测完成，总耗时: {elapsed:.2f}秒")
```

**⑦ `_process_trading_day`（`update_market_values` L429 之后）**：

```python
        close_prices = self._exec_price(dm, "close").loc[date]
        tracker.update_market_values(date, close_prices)
        self._emit(
            EventType.DAY_END,
            {
                "date": date.strftime("%Y-%m-%d"),
                "total_value": float(tracker.get_total_value()),
            },
        )
```

**⑧ `_execute_rebalance` 两处**

优化失败 `except`（`_diagnostics.record` 之后、`logger.error` 之前）：

```python
        except Exception as e:
            self._diagnostics.record(date, "rebalance", e)
            self._emit(
                EventType.ERROR,
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "stage": "rebalance",
                    "error_type": type(e).__name__,
                    "message": str(e)[: self._diagnostics.MAX_MESSAGE],
                },
            )
            logger.error(f"组合优化失败: {e}")
            return
```

目标组合产出（`_last_target_stocks` 赋值块 L985-987 之后、`if self._layer_dumper.enabled` L988 之前）：

```python
        self._last_target_stocks = {
            stock for stock, target in targets.items() if target.target_quantity > 0
        }
        self._emit(
            EventType.REBALANCE,
            {
                "date": date.strftime("%Y-%m-%d"),
                "n_targets": len(self._last_target_stocks),
            },
        )
```

**⑨ `_generate_results`（`metrics_method` L1254-1257 之后、产物写盘 L1259 之前）**：

```python
        # 事件总线（P-043 D7）：仅启用时出现；last_seq 已含 run_finished
        if self._event_bus is not None:
            additional_info["event_bus"] = {
                "enabled": True,
                "last_seq": int(self._event_bus.last_seq()),
                "errors": int(self._event_bus_errors),
            }
```

---

## 4. 测试规格（`tests/test_p043_event_bus.py`，V1-V8）

### 4.1 文件头与夹具（完整）

```python
"""P-043：事件总线契约与引擎接入（V1-V8）。

红态设计（IMPL §4.3）：核心符号一律函数内导入 → 逐用例失败而非收集期 error；
V3 为「重开续号」非回归护栏（当前 EventLog 即通过）。
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_factor, write_price_fixture

DATES = pd.bdate_range("2024-01-02", periods=5)
CODES = ["000001", "600000"]


def _fixture(root: Path) -> None:
    prices = np.array([[10.0 + 0.1 * i, 20.0 + 0.1 * i] for i in range(len(DATES))])
    write_price_fixture(root, DATES, CODES, prices)
    write_factor(
        root, "factor_value", np.tile([1.0, 2.0], (len(DATES), 1)), DATES, CODES
    )


def _make_engine(
    root: Path,
    *,
    event_log_path: Path | None = None,
    event_bus: Any = None,
    trigger: Any = None,
    optimizer: Any = None,
):
    from core.config import (
        BacktestConfig,
        CostConfig,
        FactorConfig,
        OptimizerConfig,
        RebalanceConfig,
        UniverseConfig,
    )
    from core.engine_v2 import BacktestEngineV2

    cfg = BacktestConfig(
        data_dir=root,
        output_dir=root / "out",
        factor_files=["factor_value.pkl"],
        event_log_path=event_log_path,
        cost=CostConfig(
            commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0
        ),
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight",
            target_count=2,
            max_weight=1.0,
            round_lot=True,
            select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False
        ),
        initial_capital=10_000_000.0,
        enable_pending_orders=False,
        write_manifest=False,
    )
    return BacktestEngineV2(
        cfg, event_bus=event_bus, trigger=trigger, optimizer=optimizer
    )
```

### 4.2 V1-V8 完整代码

```python
def test_v1_event_bus_contract(tmp_path):
    """I10 / G3：EventLog 运行时满足 IEventBus；签名与常量逐字。"""
    from core.event_log import EventLog, EventType, IEventBus

    log = EventLog(log_path=tmp_path / "e.jsonl")
    assert isinstance(log, IEventBus)

    append_sig = inspect.signature(log.append)
    assert list(append_sig.parameters) == ["event_type", "payload", "source"]
    assert append_sig.parameters["source"].default == ""
    assert list(inspect.signature(log.read).parameters) == [
        "after_seq",
        "limit",
        "event_type",
    ]
    assert list(inspect.signature(log.subscribe).parameters) == ["listener"]
    assert list(inspect.signature(log.last_seq).parameters) == []

    assert EventType.RUN_STARTED == "engine.run_started"
    assert EventType.REBALANCE == "engine.rebalance"
    assert EventType.DAY_END == "engine.day_end"
    assert EventType.ERROR == "engine.error"
    assert EventType.RUN_FINISHED == "engine.run_finished"


def test_v2_replay(tmp_path):
    """I4 / G4：replay(k) 与 read(after_seq=k) 一致；handler 异常向外传播。"""
    from core.event_log import EventLog

    log = EventLog(log_path=tmp_path / "e.jsonl")
    for i in range(5):
        log.append("t", {"i": i})

    entries = log.replay(2)
    assert [e.seq for e in entries] == [3, 4, 5]
    assert [e.seq for e in entries] == [e.seq for e in log.read(after_seq=2)]

    seen: list[int] = []
    returned = log.replay(2, handler=lambda e: seen.append(e.seq))
    assert [e.seq for e in returned] == [3, 4, 5]
    assert seen == [3, 4, 5]

    def boom(entry):
        raise RuntimeError("handler boom")

    with pytest.raises(RuntimeError, match="handler boom"):
        log.replay(2, handler=boom)


def test_v3_reopen_continues_seq(tmp_path):
    """I7（非回归护栏）：同路径重开 → 首个新 seq = 旧 last_seq + 1。"""
    from core.event_log import EventLog

    path = tmp_path / "e.jsonl"
    first = EventLog(log_path=path)
    for i in range(3):
        first.append("t", {"i": i})

    second = EventLog(log_path=path)
    entry = second.append("t", {"i": 3})
    assert entry.seq == 4
    assert [e.seq for e in second.read()] == [1, 2, 3, 4]


def test_v4_default_closed_zero_behavior(tmp_path):
    """I1 / D6：默认关闭 → 不构造总线、无结果键、无 jsonl。"""
    _fixture(tmp_path)
    engine = _make_engine(tmp_path)
    engine.setup()
    results = engine.run()

    assert engine._event_bus is None
    assert "event_bus" not in results["additional_info"]
    assert list(tmp_path.rglob("*.jsonl")) == []


def test_v5_events_emitted_with_continuous_seq(tmp_path):
    """I2 / I3 / S7：seq 1..N 连续；首尾类型与 payload 键集逐字。"""
    from core.event_log import EventType

    _fixture(tmp_path)
    log_path = tmp_path / "events.jsonl"
    engine = _make_engine(tmp_path, event_log_path=log_path)
    engine.setup()
    results = engine.run()

    bus = engine._event_bus
    entries = bus.read()
    types = [e.type for e in entries]
    assert types[0] == EventType.RUN_STARTED
    assert types[-1] == EventType.RUN_FINISHED
    assert [e.seq for e in entries] == list(range(1, len(entries) + 1))
    assert types.count(EventType.DAY_END) == len(DATES)
    assert entries[0].source == "engine_v2"
    assert set(entries[0].payload) == {"start", "end", "n_dates"}
    assert entries[0].payload["start"] == DATES[0].strftime("%Y-%m-%d")
    assert entries[0].payload["end"] == DATES[-1].strftime("%Y-%m-%d")
    assert entries[0].payload["n_dates"] == len(DATES)
    assert types.count(EventType.REBALANCE) == len(DATES)
    rebalance_entry = next(e for e in entries if e.type == EventType.REBALANCE)
    assert rebalance_entry.payload["n_targets"] == 2
    day_end_entry = next(e for e in entries if e.type == EventType.DAY_END)
    assert set(day_end_entry.payload) == {"date", "total_value"}

    info = results["additional_info"]["event_bus"]
    assert info == {"enabled": True, "last_seq": len(entries), "errors": 0}
    assert entries[-1].seq == info["last_seq"]
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == len(
        entries
    )


def test_v6_subscription_matches_disk(tmp_path):
    """I5：订阅 seq 集合 = 磁盘 seq 集合；取消订阅后不再通知。"""
    from core.event_log import EventLog

    _fixture(tmp_path)
    bus = EventLog(log_path=tmp_path / "events.jsonl")
    engine = _make_engine(tmp_path, event_bus=bus)
    collected: list[int] = []
    unsubscribe = bus.subscribe(lambda e: collected.append(e.seq))
    engine.setup()
    engine.run()

    disk = [e.seq for e in bus.read()]
    assert collected == disk

    unsubscribe()
    bus.append("after.unsubscribe", {})
    assert collected == disk


class _BoomBus:
    """append 恒抛的伪总线（V7）；其余方法满足 IEventBus 契约。"""

    def __init__(self) -> None:
        self.calls = 0

    def append(self, event_type, payload, source=""):
        self.calls += 1
        raise RuntimeError("bus down")

    def last_seq(self) -> int:
        return 0

    def read(self, after_seq=0, limit=None, event_type=None):
        return []

    def subscribe(self, listener):
        return lambda: None


def test_v7_bus_failure_does_not_change_backtest(tmp_path):
    """I6 / D4：总线故障零传播；成交与净值不变，errors 显形。"""
    _fixture(tmp_path)
    baseline = _make_engine(tmp_path)
    baseline.setup()
    baseline.run()
    base_trades = baseline.executor.trade_log.get_trades_df()

    boom = _BoomBus()
    engine = _make_engine(tmp_path, event_bus=boom)
    engine.setup()
    results = engine.run()
    trades = engine.executor.trade_log.get_trades_df()

    assert boom.calls > 0
    assert len(trades) == len(base_trades)
    assert float(trades["amount"].sum()) == pytest.approx(
        float(base_trades["amount"].sum())
    )
    info = results["additional_info"]["event_bus"]
    assert info["errors"] == boom.calls
    assert info["last_seq"] == 0


class _RaisingTrigger:
    """第 N 次 should_trigger 抛错（V8a）。"""

    def __init__(self, fail_on_call: int = 2) -> None:
        self.calls = 0
        self.fail_on_call = fail_on_call

    def should_trigger(self, date, **kwargs) -> bool:
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("trigger boom")
        return False


class _RaisingOptimizer:
    """optimize 恒抛（V8b）。"""

    def optimize(self, signals, returns_data=None):
        raise RuntimeError("opt boom")


def test_v8_error_events_emitted_without_interruption(tmp_path):
    """I3 / D3：两阶段错误事件不中断（V8a day_loop / V8b rebalance，F-S8-P043-1 合并）。"""
    from core.event_log import EventType

    _fixture(tmp_path)

    # V8a：day_loop 错误（trigger 第 2 次调用抛错 = 交易日 index 1）
    trigger = _RaisingTrigger(fail_on_call=2)
    engine_a = _make_engine(
        tmp_path, event_log_path=tmp_path / "events_a.jsonl", trigger=trigger
    )
    engine_a.setup()
    results_a = engine_a.run()

    entries_a = engine_a._event_bus.read()
    errors_a = [e for e in entries_a if e.type == EventType.ERROR]
    assert len(errors_a) == 1
    payload = errors_a[0].payload
    assert set(payload) == {"date", "stage", "error_type", "message"}
    assert payload["date"] == DATES[1].strftime("%Y-%m-%d")
    assert payload["stage"] == "day_loop"
    assert payload["error_type"] == "RuntimeError"

    types_a = [e.type for e in entries_a]
    assert types_a.count(EventType.DAY_END) == len(DATES) - 1
    assert types_a[-1] == EventType.RUN_FINISHED
    diagnostics_a = results_a["additional_info"]["run_diagnostics"]
    assert diagnostics_a["counts"].get("day_loop") == 1

    # V8b：rebalance 错误（独立 events_b.jsonl，防第二引擎重开续号污染 read()）
    engine_b = _make_engine(
        tmp_path,
        event_log_path=tmp_path / "events_b.jsonl",
        optimizer=_RaisingOptimizer(),
    )
    engine_b.setup()
    results_b = engine_b.run()

    entries_b = engine_b._event_bus.read()
    types_b = [e.type for e in entries_b]
    errors_b = [e for e in entries_b if e.type == EventType.ERROR]
    assert len(errors_b) == len(DATES)
    assert all(e.payload["stage"] == "rebalance" for e in errors_b)
    assert types_b.count(EventType.REBALANCE) == 0
    assert types_b.count(EventType.DAY_END) == len(DATES)
    assert types_b[-1] == EventType.RUN_FINISHED
    diagnostics_b = results_b["additional_info"]["run_diagnostics"]
    assert diagnostics_b["counts"].get("rebalance") == len(DATES)
```

### 4.3 红态预期（Step 9 首跑）

| 结果 | 用例 | 原因 |
|------|------|------|
| FAIL | V1 | `IEventBus` / `EventType` 不存在（ImportError） |
| FAIL | V2 | `EventLog.replay` 不存在（AttributeError） |
| PASS | V3 | 非回归护栏（`_recover_state` 现状即续号） |
| FAIL | V4/V5/V6 | `BacktestConfig(event_log_path=...)` / `BacktestEngineV2(event_bus=...)` 不存在（TypeError） |
| FAIL | V7/V8 | 同上（`event_bus` 参数缺失） |

**聚合预测**：`7 failed, 1 passed`（V3 PASS）。与 P-042 教训一致：**以 Step 9 实测为准回填**。

---

## 5. 低效排除表

| # | 低效操作 | 排除方式 | 判据 |
|---|----------|----------|------|
| 1 | 逐事件 `open/close` 写盘（既有 `_append_to_disk`） | 不新增缓冲层/批量刷新——单进程每交易日仅 2-3 条，缓冲引入的是复杂度而非收益 | 5 日运行 12 条；`write_failures` 已计量（P-026） |
| 2 | 关闭时仍构造 payload dict | 保留调用点字面量（每交易日 1-2 个小 dict，<1µs）；不引入惰性工厂 | `_emit` 首行 `bus is None` 短路，零 I/O / 零序列化 |
| 3 | 订阅轮询线程 | 复用既有 listener 扇出，无新线程/队列 | 全文件无 `threading.Thread` 新增 |
| 4 | 测试重复起引擎（V4-V8） | 5 日 × 2 股单次 <0.5s；不引入 session 级夹具（隔离性优先） | 8 用例合计目标 <5s |
| 5 | 结果键读取触发读盘 | `last_seq()` 只读内存 `_seq`（L227-230） | 无 `read` 调用 |

---

## 6. 兼容性与版本

| 项 | 结论 |
|----|------|
| Python | `>=3.10`；`Protocol` / `runtime_checkable` 均 stdlib |
| 新增依赖 | **0** |
| `EventLog` 既有 API | 零改动（仅新增 `replay` 与两符号）；`EventLogPlugin` 零改动 |
| `BacktestConfig` | 新增末位同组默认字段 `None` → 关键字构造零影响；manifest `config` 块 +1 键 → `input_fingerprint` 随 schema 变化（I9 声明，无固定断言） |
| `BacktestEngineV2` | 新参数追加在签名末尾，既有 12 个注入参数位置不变 |
| golden | 13 零重录（默认 `None`） |
| 产物 | 新增 `events.jsonl` 仅在启用时；`pending_order_events.csv` / `trades.csv` / snapshots / manifest 结构不变 |

---

## 7. 门禁终态（Step 9 目标）

| 门禁 | 现值 | 目标 |
|------|------|------|
| pytest | 795 | **803** |
| golden | 13·782 | **13·782**（零重录） |
| black（`core tests` / 全仓） | 129·196 | **130·197** |
| mypy | 104 files 0 | **104 files 0** |
| AST `except Exception` | 22 | **22（不变）**；`core/` 内 28→29 非门禁（F-S9-P043-1） |
| `tests/*.py` | 91 | **92** |
| `uv lock --check` | exit 0 | **exit 0** |

命令：

```powershell
$py = 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe'
$env:MPLBACKEND='Agg'; & $py -m pytest tests -q -p no:cacheprovider
& $py -m pytest tests -k golden -q -p no:cacheprovider
& $py -m black --check core tests
& $py -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
uv lock --check
```

---

## 8. 回退点

| 批 | revert 方式 | 残留 |
|----|-------------|------|
| B1 | 还原 `core/event_log.py` 4 处新增 | 无（仅新符号） |
| B2 | 还原 `config.py` 1 字段 + `engine_v2.py` 9 处 | 无（默认 `None`，不产生文件/键） |
| B3 | 删除 `tests/test_p043_event_bus.py` | 无 |

三批均无数据迁移与产物兼容问题。

---

## 9. Step 6 实施 Review（异构 GLM-5.3-Flash，2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 复审 **GLM-5.3-Flash** ≠ 作者 DeepSeek-V4.1-Flash → **本轮异构成立**（Step 4/6 连续两轮异构；U-P043-5 终审维持）。

### 9.1 复核读数

| # | 项 | 复核方法 / 读数 | 判定 |
|---|----|----------------|------|
| 1 | B1 符号与既有 API 兼容 | `IEventBus` 4 方法与 `EventLog.append/last_seq/read/subscribe`（L91/L227/L131/L234）逐参同型；`replay` 插入点 L172/L174 之间无冲突 | ✅ |
| 2 | ① import | 既有 L21 `from typing import Any, Callable, Generic, Optional, TypeVar` → 增补 `Protocol`/`runtime_checkable`；既有名保留 | ✅ |
| 3 | ② config | `Path` 实际在 [config.py L12](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L12)（IMPL 误写 L5，F-S6-P043-2 订正）；`dump_layers_dir` L343 锚点成立 | ✅（订正后） |
| 4 | ③-⑨ 引擎锚点 | `__init__` 属性位 L145/L172、setup 步骤 14 位于协方差预检（L297-308）后、`_emit` 位于 `_exec_price` 与 `_process_trading_day` 之间、6 处发射行与 `_generate_results`（L1254-1257/L1259）全部与 @`1306bf8` 读码一致 | ✅ |
| 5 | DESIGN §10 五项处置落地 | V8b（F-S4-P043-1）/ `logger.info`（F-S4-P043-4）/ 锚点钉死（F-S4-P043-5）/ V8 两段 / 文档边界 → IMPL 全部承接 | ✅ |
| 6 | 红态逐用例失败模式 | V1 ImportError（`EventType`/`IEventBus`）/ V2 AttributeError（`replay`）/ V3 PASS / V4 AttributeError（`_event_bus`）/ V5-V8 TypeError（`event_log_path`·`event_bus` kwargs） | ✅ 7F/1P 预测成立 |
| 7 | 测试确定性 | V5 `info == {...,"errors":0}` 相等断言隐含全日程零异常；V8a trigger 第 2 次调用 = 交易日 index 1；V8b `diagnostics["counts"]["rebalance"]==5` 与 error×5 对齐；夹具参数与 `_golden_cases._v2_config` 同源核对（CostConfig/OptimizerConfig/UniverseConfig/RebalanceConfig 字段全部存在） | ✅ |
| 8 | mypy | `EventLog` 结构化满足 `IEventBus`；结果键 `last_seq()` 在 `is not None` 窄化内；`self._diagnostics.MAX_MESSAGE` 类属性可访问；mypy 门禁不含 `tests/` | ✅ |
| 9 | 计数链自洽 | 795+8=803；tests 91+1=92；AST 门禁 **22 不变**（口径 = core 外十文件，F-S9-P043-1 实测订正）；black 130·197 | ✅ |
| 10 | 既有测试零触碰 | `test_engine_plugins` / `test_compatibility` / `test_p026` 均不涉及新符号与新参数；`BacktestEngineV2` 新参数追加签名末尾 | ✅ |

### 9.2 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S6-P043-1 | P3 | error payload `message=str(e)` **无截断**——与 P-025 既有纪律不一致（`DayErrorCollector.MAX_MESSAGE = 200`，[diagnostics.py L89/L113/L145](file:///f:/Coding/Factor_Trading_v3.0/core/diagnostics.py#L89)）；pandas/cvxpy 异常消息可达数 KB，事件 JSONL 无界增长 | §3.3 ⑥⑧ 改为 `str(e)[: self._diagnostics.MAX_MESSAGE]`（复用常量、零魔数；`DayErrorCollector` 已在 engine_v2 L57 导入）；DESIGN §4 payload 行同步补注；V8a/V8b 断言不含 message 全文，测试零影响 |
| F-S6-P043-2 | P3 | §3.2 锚点注释「`Path` 已在 L5 导入」实测 **L12** | 当轮订正注释 |
| F-S6-P043-3 | P3 | V5 覆盖不足：I3 正向（rebalance 事件数）与 S7 payload **值**（start/end/n_dates、n_targets）均可确定性断言而未断言 | V5 增补 5 条断言（rebalance count==5、payload 三值、n_targets==2） |

### 9.3 结论

**Step 6 Review pass（0 P1 / 0 P2 / 3 P3，全部当轮处置）**——IMPL 与 DESIGN D1-D8 及 §10 处置逐项对齐、9 处引擎锚点经读码核实、红态逐用例失败模式成立、测试夹具与 `_golden_cases` 同源参数核对无误。**准予进入 Step 7 CHECKLIST**。

---

## 10. Step 9 实施记录（2026-11-18）

### 10.1 落码

| 文件 | 内容 |
|------|------|
| `core/event_log.py` | typing import 增补 `Protocol`/`runtime_checkable`（L21-29）；`EventType` 5 常量 + `IEventBus` 4 方法 `@runtime_checkable`（L50-77）；`EventLog.replay`（L212-226） |
| `core/config.py` | `event_log_path: Path \| None = None`（L344，`dump_layers_dir` 后） |
| `core/engine_v2.py` | import（L23）；`__init__` 参数（L118）+ 文档（L135）+ 属性（L149/L177-178）；`setup()` 步骤 14（L316-327）；`_emit`（L413-422）；`run()` 三处（L375/L396/L422）；`day_end`（L483）；`rebalance`/`error`（L1015/L1057）；结果键（L1335-1341） |
| `tests/test_p043_event_bus.py` | 新建，8 函数（V1-V7 + V8 单函数 a/b 两段） |

### 10.2 红 → 绿

- **红**（测试先落）：`7 failed, 1 passed in 2.46s`——与 IMPL §4.3 预测**逐项一致**：V1/V5/V8 `ImportError: cannot import name 'EventType'`、V2 `AttributeError: 'EventLog' object has no attribute 'replay'`、V4/V6/V7 `TypeError: BacktestConfig.__init__() got an unexpected keyword argument 'event_log_path'`；**V3 护栏 PASS**。
- **绿**（B1→B2 落码后）：`8 passed, 7 warnings in 8.51s`。
- **既有测试零订正**：`test_engine_plugins + test_manifest + test_p026 + test_compatibility` → **37 passed**。

### 10.3 门禁（E1）

| 门禁 | 实测 | 判定 |
|------|------|------|
| pytest | **`803 passed, 179 warnings in 53.65s`** | ✅ 795+8 |
| golden | **`13 passed, 790 deselected`**（`tests/golden/` 无改动） | ✅ 零重录 |
| black | `core tests` **130** / 全仓 **197**（首跑 2 文件待格式化，见 F-S9-P043-2） | ✅ |
| mypy | **`Success: no issues found in 104 source files`** | ✅ |
| AST `except Exception` | 门禁口径（core 外十文件）**22 不变**；`core/` 内 28→29（非门禁） | ✅ F-S9-P043-1 |
| `tests/*.py` | **92** | ✅ |
| `uv lock --check` | exit **0**；`pyproject.toml`/`uv.lock` 零 diff | ✅ |

### 10.4 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P043-1 | P3 | **AST 门禁口径误判**：DESIGN D4 / IMPL §7 / CHECKLIST D5 预登记「22 → 23」，实测门禁命令仅覆盖 **core 外十文件**（agents 11 + filter 5 + scripts 2 + batch 2 + strategy 1 + cli 1 = 22，P-029 口径），`core/engine_v2.py` 新增 1 处不计入 → 门禁读数仍 **22**；`core/` 内由 28→29（非门禁，仅声明） | DESIGN §2-D4/§6/§10.1、IMPL §7/§9.1、CHECKLIST 头部/D5/§6 全部订正为「22 不变 + core 内 28→29 声明」 |
| F-S9-P043-2 | P3 | IMPL §3 预格式化未覆盖两处：`logger.info(...)` 三行被 black 折叠为一行、测试文件 2 处需要重排；首跑 black 为 128·195 | `black core/engine_v2.py tests/test_p043_event_bus.py` 格式化后复跑 **130·197 unchanged**；仅格式差异，重跑新测试 8 passed + 全量 803 passed 确认零语义变化 |
