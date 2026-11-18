# DESIGN：P-043 事件总线（EventLog 接入引擎）

> **批次**: P-043 · **Step 3 设计** · 日期 2026-11-18
> **判档**: **T1**（`core/event_log.py` 契约新增 + `core/engine_v2.py` 运行时接入 + `core/config.py` 字段）
> **上游**: [RESEARCH_p043_event_bus.md](RESEARCH_p043_event_bus.md)（§7 S1-S10 / §8 I1-I9 / §13 Step 2 Review pass）
> **代码证据时点**: HEAD `1306bf8`（DESIGN 中行号为该时点；插入后行号会位移，以符号为准）
> **基座**: DeepSeek-V4.1-Flash（Step 4 Review 同源 → U-P043-5；终审须 GLM-5.3-Flash）

---

## 1. 范围与前置

**做**（B1 → B2 → B3）：
1. `core/event_log.py`：`EventType`（5 常量）+ `IEventBus`（Protocol，4 方法）+ `EventLog.replay(after_seq, handler)`；
2. `BacktestConfig.event_log_path: Path | None = None` + `BacktestEngineV2(event_bus=None)`；`setup()` 解析；`run()`/`_process_trading_day`/`_execute_rebalance` 共 **6 处发射点**（5 类事件，`error` 两处）；
3. 默认关闭：零磁盘 I/O、零新结果键、golden 13 零重录；
4. `tests/test_p043_event_bus.py` 8 用例（V1-V8）。

**不做**：Redis/WS/FastAPI（P-054）；`live/`（P-053）；`pending_order_events.csv` 迁移；`run_diagnostics`/layer dump 迁入；逐订单/逐成交事件；与 `MarketEvent` 合类；`EventLogPlugin` 改造。

**前置**（E3 @`1306bf8`）：`EventLog` 已被 `engine_plugins.py` 与 3 个测试模块导入；`core/manifest.py::_jsonable` 已支持 `Path`/`None`（L33-56）→ 新增 config 字段不会使 manifest 序列化失败。

---

## 2. 设计决策

### D1 协议放置：`core/event_log.py`（U-P043-1 裁决）

`EventType` + `IEventBus` 与 `EventLog` 同文件。理由：
- 与 P-042 D5（`IStreamingFeed` 与 `InMemoryStreamingFeed` 同置 `core/streaming.py`）同构，契约与实现同域；
- 零新文件 → mypy `104` 不变；`interfaces.py` 不必反向依赖 `event_log`（抽象层不应依赖具体事件模块）。

| 被拒 | 代价 |
|------|------|
| `core/interfaces.py` | 需 `from core.event_log import EventLogEntry`（TYPE_CHECKING 反向依赖）；`interfaces` 被全层依赖，方向倒置 |
| 新建 `core/event_bus.py` | 新增概念文件，mypy/black 计数 +1，且契约与唯一实现分居两处 |

### D2 引擎接入形态：config 字段 + 构造注入；`setup()` 解析

- `BacktestConfig.event_log_path: Path | None = None`（放在 `dump_layers_dir` / `write_manifest` 同组，`core/config.py` L343-L347 区段）。
- `BacktestEngineV2(..., event_bus: Optional[IEventBus] = None)` 追加在参数表**末尾**（不移动既有 12 个位置参数）。
- `setup()` 末尾「14. 事件总线」解析：

```python
if self._injected_event_bus is not None:
    self._event_bus = self._injected_event_bus      # 注入优先
elif self.cfg.event_log_path is not None:
    self._event_bus = EventLog(log_path=self.cfg.event_log_path)  # 仅此时构造（会 mkdir）
else:
    self._event_bus = None                          # 默认关闭：不构造、零 I/O
```

| 被拒 | 代价 |
|------|------|
| 引擎调 `get_event_log()` 全局单例 | 隐式建 `data/events.jsonl`（G6）、跨测试污染、无法关闭 |
| 引擎调 `EventLogPlugin.log_*` | 需同样多的引擎改动，却保留 config/plugin 双入口；插件缺省路径同样隐式建文件（RESEARCH M-B） |
| 两实例同时创建（注入 + 配置） | 同路径双实例 seq 冲突（F-S2-P043-2 → U-P043-3） |

**注入优先分支补显形（F-S4-P043-4）**：注入与 `cfg.event_log_path` 同时设置时，注入优先、config 路径被忽略——此时 `logger.info` 注明被忽略的路径（P-026 显形纪律，不静默）。

### D3 发射点：5 类 6 处（位置逐字）

| 事件 | 位置（设计时点） | 触发语义 |
|------|------------------|----------|
| `engine.run_started` | `run()` L351-L353 之后、日循环 L356 之前 | 每次 `run()` 一次 |
| `engine.rebalance` | `_execute_rebalance` L984-L989（`_last_target_stocks` 赋值后、订单生成前） | **成功产出目标组合**才发；无票/优化失败/缺价返回不发 |
| `engine.day_end` | `_process_trading_day` L428-L429（`update_market_values` 之后） | 每个**成功完成**的交易日一次 |
| `engine.error` | `run()` except L365-L370（`stage="day_loop"`）；`_execute_rebalance` except L953-L956（`stage="rebalance"`） | 与 `_diagnostics.record` 两站点一一对应 |
| `engine.run_finished` | `run()` L383-L386（`elapsed` 计算后、`_generate_results()` 前） | 日循环结束即发（不含结果生成本身） |

- `day_end` **不放** `_process_trading_day` 末尾：`_dump_layers` 抛错会漏发当日净值。
- `error` **不覆盖** setup 期 factor sink（无 bus 生命周期，且 setup 失败即终止）。
- `run_finished` 先于 `_generate_results()`：保证结果键 `last_seq` 已含 `run_finished.seq`；若结果生成随后抛错，事件仍如实记录「回测已跑完」。

| 被拒 | 代价 |
|------|------|
| 在 `run()` 循环统一发 `day_end` | 需跨方法传净值；异常日语义与 tracker 快照不对齐 |
| 把 `run_diagnostics` 全量镜像为事件 | 重复通道，违反 S10 |

### D4 `_emit` 永不抛错（总线故障隔离）

```python
def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
    bus = self._event_bus
    if bus is None:
        return
    try:
        bus.append(event_type, payload, source="engine_v2")
    except Exception as exc:              # noqa: BLE001 — 总线路由不得改变回测流程
        self._event_bus_errors += 1
        logger.debug("事件总线写入失败（不影响回测）: %s", exc)
```

**门禁影响（F-S9-P043-1 实测订正）**：`_emit` 新增 1 处 `except Exception`，但门禁口径为 **core 外十文件**（P-029 单行命令：agents/filter/scripts/batch/strategy/cli）→ **门禁读数仍 22**；`core/` 内计数 28 → 29 属非门禁口径，仅声明。理由不变：S8 要求总线异常零传播；计数 + 日志 + 结果键 `errors` 三重显形，符合 P-026 治理口径（非静默）。不用 `contextlib.suppress` 规避计数（属指标规避）。

**边界**：`_emit` 只保护 `append`。`additional_info["event_bus"]` 中 `last_seq()` 为只读契约调用，不包裹（伪总线在该调用抛错属违反 `IEventBus` 契约）。

### D5 `replay()` 语义：`read` 薄封装 + handler 异常向外传播

```python
def replay(self, after_seq: int = 0, handler: Optional[EventListener] = None) -> list[EventLogEntry]:
    entries = self.read(after_seq=after_seq)
    if handler is not None:
        for entry in entries:
            handler(entry)
    return entries
```

- 返回 `seq > after_seq` 的**磁盘**全集（升序，非 ring buffer）；
- handler 异常**向外传播**——与 listener 吞错（`_notify_listeners` L286-301）语义分离：重放消费方需要可失败。

| 被拒 | 代价 |
|------|------|
| handler 吞错 | 重放静默丢事件，与订阅容错混淆 |
| 新增独立 `Replayer` 类 | 本批只有一个消费方（测试），过度抽象 |

### D6 默认关闭：`None` 即关闭，且不构造 `EventLog`

`EventLog.__init__` 会 `log_path.parent.mkdir(...)`（L81）→ 关闭路径**绝不实例化**。golden 13、`tests/test_manifest.py` 等既有用例均不设 `event_log_path`，行为逐值不变。

### D7 结果键：仅启用时出现

```python
if self._event_bus is not None:
    additional_info["event_bus"] = {
        "enabled": True,
        "last_seq": int(self._event_bus.last_seq()),
        "errors": int(self._event_bus_errors),
    }
```

放置于 `metrics_method`（L1254-1257）之后、产物写盘（L1259）之前。默认关闭 → 键不存在（I1）。

| 被拒 | 代价 |
|------|------|
| 恒输出 `{"enabled": False}` | 改变既有结果键集，下游/golden 需适配 |

### D8 缺口关闭映射（含 G2 重分类）

| 缺口 | 处置 |
|------|------|
| G1 引擎未接入 | **关闭**（B2） |
| G2 插件 `log_*` 死 API | **不关闭，重分类 O-P043-1**：该插件是外部旁路 API，非引擎生命周期通道；去留由 P-053/P-054 决定。RESEARCH §5「M-A 关闭 G1-G5」表述过宽，此处以 DESIGN 为准（F-D3-P043-2） |
| G3 无协议 / G4 无 replay / G5 无常量 | **关闭**（B1） |
| G6 缺省路径副作用 | **关闭**（D6：引擎不用全局单例；`log_event()` 既有行为不动） |
| G7 双实例同路径 | **文档声明不支持**（U-P043-3）：单进程单写入者 |
| G8 pending CSV 双通道 | **边界声明**（S10）：`pending_order_events.csv` 本批零改动，P-053 再议 |

---

## 3. 精确签名

### 3.1 `core/event_log.py`（新增，置于 `EventListener` L39 之后）

```python
class EventType:
    """引擎生命周期事件类型（单一来源；禁止在引擎侧写裸字符串）"""
    RUN_STARTED = "engine.run_started"
    REBALANCE = "engine.rebalance"
    DAY_END = "engine.day_end"
    ERROR = "engine.error"
    RUN_FINISHED = "engine.run_finished"


@runtime_checkable
class IEventBus(Protocol):
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

导入增补：`from typing import Protocol, runtime_checkable`（保留既有 `Any/Callable/Generic/Optional/TypeVar` 不动）。
`EventLog.replay` 置于 `read()` 之后（语义相邻）。

### 3.2 `core/config.py`

```python
event_log_path: Path | None = None  # 事件总线输出路径（P-043）；None=关闭（零 I/O）
```

位置：`dump_layers_dir`（L343）之后。`manifest._jsonable` 已支持 `Path|None`。

### 3.3 `core/engine_v2.py`

| 项 | 规格 |
|----|------|
| import | `from core.event_log import EventLog, EventType, IEventBus` |
| `__init__` | 末尾追加 `event_bus: Optional[IEventBus] = None`；文档字符串 +1 行；存储 `self._injected_event_bus = event_bus`、`self._event_bus: Optional[IEventBus] = None`、`self._event_bus_errors: int = 0` |
| `setup()` | 追加「14. 事件总线」（D2 代码块），置于协方差预检之后、`elapsed` 日志之前 |
| `_emit` | 见 D4；置于 `_process_trading_day` 之前 |
| `run()` | 3 处：started（L353 后）、error（L366 后）、finished（L383 后） |
| `_process_trading_day` | 1 处：`update_market_values` 后 |
| `_execute_rebalance` | 2 处：rebalance（**`_last_target_stocks` 赋值后**、订单生成分支前；设计时点 L987-989，锚点钉死见 F-S4-P043-5）、error（L954 后） |
| `_generate_results` | 1 处：结果键（D7） |

---

## 4. 事件 payload 逐字规格

所有事件 `source="engine_v2"`；日期统一 `Timestamp.strftime("%Y-%m-%d")`。

| 事件 | payload | 备注 |
|------|---------|------|
| `engine.run_started` | `{"start": str, "end": str, "n_dates": int}` | `start/end` 取 `dm.trade_dates[0] / [-1]`；`n_dates = len(dm.trade_dates)` |
| `engine.rebalance` | `{"date": str, "n_targets": int}` | `n_targets = len(self._last_target_stocks)`（目标持仓 > 0 的标的数） |
| `engine.day_end` | `{"date": str, "total_value": float}` | 取 `tracker.get_total_value()`，`float()` |
| `engine.error` | `{"date": str, "stage": str, "error_type": str, "message": str}` | `stage ∈ {"day_loop","rebalance"}`；`error_type=type(e).__name__`；`message=str(e)` **截断至 `DayErrorCollector.MAX_MESSAGE`(200)**（F-S6-P043-1，对齐 P-025 纪律） |
| `engine.run_finished` | `{"elapsed_s": float, "n_days": int}` | `elapsed_s` = 日循环耗时（L383 同源）；`n_days = len(dm.trade_dates)` |

**空交易日边界（F-S4-P043-3 措辞订正）**：启用 pending 时 `run()` 既有实现 L374 已假设 `trade_dates` 非空（空序列 IndexError）；无 pending 时既有失败形态为 `_generate_results` 的 RuntimeError（快照缺失）。启用总线后 `run_started` 在循环前构造，两种配置下空序列均**提前**以 IndexError 失败——失败时点与异常类型变化、但均不静默成功；不新增兜底。

**两条事件语义边界（F-S4-P043-2 补声明）**：
1. `day_error_mode="raise"` 中断时 `run_finished` **不发射**——`run_finished` 存在即「日循环干净完成」的可判别标志；`engine.error` 在 `raise_if_needed()` 之前发射，raise 模式下错误事件仍已落盘；
2. 末日 `day_end.total_value` 反映当日 `update_market_values` 之后、`_force_liquidation` **之前**的净值（发射点在 `_process_trading_day` 内，强平在其后的 `run()` 分支）。

---

## 5. 测试规格（`tests/test_p043_event_bus.py`，V1-V8）

夹具：复用 [tests/_synth_fixture.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_synth_fixture.py)（`write_price_fixture` / `write_factor`；5 日 × 2 股、常量价、零费用、daily 再平衡、`enable_pending_orders=False`、`write_manifest=False`）。导入一律**函数内局部导入**，保证红态为逐用例失败而非收集期 error。预计红态：**`7 failed, 1 passed`**（V3 为非回归护栏，见下）。

| # | 用例 | 断言 |
|---|------|------|
| V1 | 契约 | `isinstance(EventLog(tmp), IEventBus)`；`inspect.signature` 四方法参数名逐字；`EventType` 5 常量值逐字 |
| V2 | replay | 追加 5 条 → `replay(2)` 返回 seq `[3,4,5]` 且与 `read(after_seq=2)` 逐条一致；handler 收集 3 条；`handler` 抛 `RuntimeError` 时 `pytest.raises` 向外传播 |
| V3 | 续号（**护栏**） | 新实例同路径：先 3 条 → 重开 → 追加 1 条 seq=4；磁盘 seq `[1,2,3,4]`（当前代码即通过，红态 PASS） |
| V4 | 默认关闭 | `event_log_path=None` → `engine._event_bus is None`；`"event_bus" not in results["additional_info"]`；`root.rglob("*.jsonl")` 为空 |
| V5 | 启用发射 | tmp 路径运行 → `types[0]==RUN_STARTED`、`types[-1]==RUN_FINISHED`；`seqs == list(range(1, N+1))`；`day_end` 数 == 5；`run_finished.seq == last_seq == N`；`additional_info["event_bus"] == {"enabled":True,"last_seq":N,"errors":0}` |
| V6 | 订阅一致 | 订阅（run 前）→ 收集 seq 集合 == `read()` seq 集合 == `1..N`；取消订阅后追加 1 条不再通知 |
| V7 | 总线故障隔离 | 注入 `_BoomBus`（`append` 抛 `RuntimeError`，其余返回空/0）→ `run()` 正常返回；成交数与无总线基线一致；`errors > 0` 且 `last_seq == 0` |
| V8 | 错误事件不中断（两阶段，F-S4-P043-1 扩展） | **V8a** 注入第 2 个交易日抛 `RuntimeError` 的 fake trigger → `engine.error` 恰 1 条（`stage="day_loop"`、date 匹配、`error_type="RuntimeError"`）；`day_end` 数 == 4；`run_finished` 存在；`run_diagnostics` 同步 1 条。**V8b** 注入恒抛 `RuntimeError` 的 fake optimizer → `engine.error` 恰 5 条且 `stage=="rebalance"` 逐条成立；`rebalance` 事件 **0** 条（成功产出才发，I3 反向）；`day_end` 数 == 5；`run_finished` 存在 |

**映射**：V1↔I4/G3；V2↔I4/G4；V3↔I7；V4↔I1；V5↔I2/I3/I9；V6↔I5；V7↔I6；V8↔I3（正反两向）/错误语义两阶段。

---

## 6. 不变式与门禁口径

| ID | 不变式 |
|----|--------|
| I1 | 默认关闭：golden **13 零重录**；`additional_info` 无 `event_bus` 键；无 `*.jsonl` 新建 |
| I2 | 启用且**空路径**：seq `1..N` 连续；`run_started.seq==1`；`run_finished.seq==N==last_seq`（重开路径见 I7） |
| I3 | `day_end` 数 = 成功完成的交易日数（无异常时 = 交易日数）；`rebalance` 数 = 成功产出目标组合次数 |
| I4 | `replay(k)` 与 `read(after_seq=k)` 逐条一致、升序 |
| I5 | 订阅 seq 集合 = 同次运行磁盘 seq 集合 |
| I6 | 伪总线 `append` 抛错不改变成交数与净值；`errors>0` 显形 |
| I7 | 重开同路径：首个新 seq = 旧 `last_seq+1`，无重复 |
| I8 | 零新增依赖；`tests/*.py` **91 → 92**；pytest **795 → 803** |
| I9 | `pending_order_events.csv` / `run_diagnostics` / `invariant_report` / layer dump **零 diff**；manifest 顶层键集不变，`config` 块新增 `"event_log_path": null` → `input_fingerprint` 随配置 schema 变化（**无固定指纹断言**，`tests/test_manifest.py:118-126` 只断言同输入两次相等） |
| I10 | 契约测试：`EventLog` 运行时满足 `IEventBus`；`EventType` 为唯一事件类型来源 |

**计数链（本批声明，Step 9 实测回填）**

| 门禁 | 现值 | 预期 | 说明 |
|------|------|------|------|
| pytest | 795 | **803** | +8（V1-V8） |
| golden | 13·782 | **13·782** | 默认关闭，零重录 |
| black | 129·196 | **130·197** | 新增 1 个测试文件（F-D3-P043-1：RESEARCH §6 B3「black 不变」表述订正） |
| mypy | 104 files 0 | **104** | 无新源文件；`EventLog` 仍需满足 `IEventBus` |
| AST `except Exception` | 22 | **22（不变）** | 门禁口径 = core 外（P-029 十文件命令）；`core/` 内 28→29 非门禁（F-S9-P043-1） |
| `tests/*.py` | 91 | **92** | 1 个新测试文件 |
| uv lock | exit 0 | **0** | 零依赖变更 |

---

## 7. 兼容、迁移与风险

| ID | 风险 | 处置 / 验证 |
|----|------|-------------|
| R1 | dataclass 字段插入改变位置参数顺序 | 全仓 `BacktestConfig(` 均为关键字构造（E3 抽查 cli/examples/tests）；Step 9 grep 复核 |
| R2 | `EventLog` 构造即 `mkdir` | 仅 `event_log_path != None` 时构造（D6） |
| R3 | 同路径双实例 seq 冲突 | 文档声明单写入者（U-P043-3）；不使用全局单例 |
| R4 | `_emit` 吞错掩盖真实故障 | `errors` 计数进结果键 + `logger.debug`；总线自身 `write_failures` 已计量（P-026） |
| R5 | manifest 指纹变化 | 仅配置 schema 变化导致，预期内；无固定指纹断言（I9） |
| R6 | 事件写入放大磁盘 I/O | 仅启用时；每交易日 2-3 条，5 年约 4k 条 |
| R7 | `IEventBus` 与实际 `EventLog` 签名漂移 | V1 签名逐字断言；mypy 对 `EventLog()` 赋给 `IEventBus` 做静态检查（core 侧由 setup 赋值保证） |
| R8 | 事件导致交易/净值变化 | 5 类事件全部在既有流程之外；V7 成交数对照 + golden 零重录 |

**回退点**：B1（`event_log.py` 新增符号）零行为可单独 revert；B2（config/engine）revert 后默认路径无任何残留（默认 None，无产物）；B3 测试文件可独立删除。三批均为「新增只读面」，无数据迁移。

---

## 8. 与 P-042 的边界（防重做）

| 维度 | P-042 | P-043 |
|------|-------|-------|
| 方向 | 入向行情（`MarketEvent` / `IStreamingFeed`） | 引擎产出域事件（生命周期） |
| 类型 | `core/streaming.py` | `core/event_log.py` |
| 同化 | **不合类**；`MarketEvent` 不带 `seq`，`EventLogEntry` 不带 OHLCV | — |

---

## 9. 设计期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-D3-P043-1 | P3 | RESEARCH §6 B3 写「black 129·196 不变」，但 B3 含新增测试文件 → 应为 **130·197** | §6 计数链按 130·197 声明；RESEARCH 该行加订正注 |
| F-D3-P043-2 | P3 | RESEARCH §5 称 M-A「关闭 G1-G5」，实际 M-A 不触 `EventLogPlugin`，G2 不关闭 | D8 重分类 G2 → O-P043-1；以 DESIGN 为准 |
| F-D3-P043-3 | P3 | 新增 config 字段会改变 manifest `input_fingerprint`（`_jsonable` 遍历全字段） | I9 显式声明；确认无固定指纹断言（`tests/test_manifest.py` 仅同输入对比） |

---

## 10. Step 4 Design Review（2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 复审 **GLM-5.3-Flash** ≠ 作者 DeepSeek-V4.1-Flash → **本轮异构成立**（P-042 五轮同源复审的惯例在本轮被打破）；U-P043-5 维持——Step 6/8 若回到同基座，Step 10 终审仍须异构。

### 10.1 机械复核

| # | 项 | 复核方法 / 读数 | 判定 |
|---|----|----------------|------|
| 1 | 发射点行号 | 读码 @`1306bf8`：`run()` L351-386 / `_process_trading_day` L428-429 / `_execute_rebalance` L953-956·L984-989 | ✅ 与 D3 一致 |
| 2 | config 字段先例与 manifest 兼容 | [config.py](file:///f:/Coding/Factor_Trading_v3.0/core/config.py) L343 `dump_layers_dir` 先例；[manifest.py](file:///f:/Coding/Factor_Trading_v3.0/core/manifest.py) `_jsonable` L33-56 已支持 `Path|None` | ✅ |
| 3 | D6「构造即 mkdir」 | [event_log.py](file:///f:/Coding/Factor_Trading_v3.0/core/event_log.py) L81 `log_path.parent.mkdir(..., exist_ok=True)` | ✅ 关闭路径必须不实例化 |
| 4 | V3 护栏（重开续号） | `_recover_state` L303-329 由末条恢复 `_seq` | ✅ 当前代码即过 |
| 5 | D5 薄封装可行性 | `read` L131-172 磁盘升序、`seq > after_seq` 过滤 | ✅ |
| 6 | **AST 计数是否测试硬编码** | `tests/`、`scripts/` 无 `ExceptHandler`/计数断言（Grep 复核）；[CHECKLIST_p042](CHECKLIST_p042_data_contract.md) D2 表明口径为「P-029 单行命令」测量 | ✅ `_emit` 22→23 无需改既有测试，预登记充分 |
| 7 | black 双口径 | `black core tests` **129** / 全仓 **196**（CHECKLIST_p042 基线注） | ✅ +1 测试文件 → 130·197 |
| 8 | 结果键无既有断言冲突 | 全仓无 `additional_info` 键集断言；[test_manifest.py:118-126](file:///f:/Coding/Factor_Trading_v3.0/tests/test_manifest.py#L118-L126) 仅同输入指纹对比 | ✅ D7/I9 成立 |
| 9 | mypy 可行性 | `EventLog` 4 方法与 `IEventBus` 逐参同型（结构化满足）；mypy 门禁命令不含 `tests/` | ✅ V7/V8 fake 无类型风险 |
| 10 | 红态形态 | V1-V8 局部导入（吸取 P-042 streaming 收集期 error 教训）；仅 V3 依赖既有符号 | ✅ 预测 7F/1P 合理，Step 9 实测为准 |
| 11 | 计数链自洽 | 795+8=803；tests 91+1=92；AST 门禁 **22 不变**（core 外口径）；mypy 104 不变；golden 13·782 不变 | ✅（F-S9-P043-1 订正 23→22） |

### 10.2 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S4-P043-1 | P3 | **rebalance 阶段 error 事件无测试载体**——D3 规格含两处 error 发射，V8 仅覆盖 `day_loop` | §5 V8 扩展为两段：V8a（原）+ V8b 注入恒抛 fake optimizer → error×5 且 `stage=="rebalance"`、`rebalance` 事件 0 条（I3 反向）；计数链 803 不变 |
| F-S4-P043-2 | P3 | 两条事件语义边界未声明：① `day_error_mode="raise"` 中断时 `run_finished` 不发射；② 末日 `day_end.total_value` 为强平前净值 | §4 补两条边界；`error` 在 `raise_if_needed()` 前发射（raise 模式错误事件仍落盘）随 ① 写明 |
| F-S4-P043-3 | P3 | §4「空交易日同一失败语义」不准：无 pending 时既有失败为 `_generate_results` RuntimeError，启用总线后提前 IndexError | §4 措辞订正（失败时点/类型变化、均不静默成功、不新增兜底） |
| F-S4-P043-4 | P3 | 注入与 `cfg.event_log_path` 同时设置时 config 被静默忽略（S6 只禁双实例） | D2 补：注入优先分支 `logger.info` 注明被忽略路径（P-026 显形纪律） |
| F-S4-P043-5 | P3 | D3 表「L984-989」与 §3.3「L987 后」不一致（L988-989 为 layer dump）；实质等价 | §3.3 锚点钉死为「`_last_target_stocks` 赋值后、订单生成分支前」 |

### 10.3 结论

**Step 4 Review pass（0 P1 / 0 P2 / 5 P3，全部当轮处置）**——D1-D8 论证成立、payload 与 RESEARCH S1-S10 逐字对齐、计数链自洽、AST/black 口径经工具复核无隐性测试耦合、V1-V8 载体齐备（含本轮补齐的 V8b）。**准予进入 Step 5 IMPL**。
