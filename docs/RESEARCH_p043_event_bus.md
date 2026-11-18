# RESEARCH：P-043 事件总线（EventLog 接入引擎）

> **批次**: P-043 · **Step 1 调研** · 日期 2026-11-18
> **判档**: **T1**（Layer-1：`core/`、`tests/`；`BacktestEngineV2` 运行时改动 + 新契约）
> **上游**: [UPGRADE_MASTER_PLAN.md §5](UPGRADE_MASTER_PLAN.md) P-043（前置 P-042）；[PROGRESS §1.4](PROGRESS.md) U-P025-1；[PROGRESS §3.48.6](PROGRESS.md) P-042 关闭
> **代码证据时点**: HEAD `1306bf8`（P-042 关闭；工作区净）
> **基座**: DeepSeek-V4.1-Flash（Step 2 Review 同源 → 登记 U-P043-5；终审须异构）

---

## 1. 触发与题干

- **触发**: 用户「进入 P-043 事件总线」；总纲 §5 P-043：「EventLog 接入引擎（U-P025-1）→ 统一事件通道（seq/重放）」，验收「事件 seq 连续；订阅/重放测试」。
- **U-P025-1 触发条件改写（必须显式裁决）**: 原条件为「`run_diagnostics` 已落地**且有第二个消费方**（web/批处理）需要事件流」。E3 实测：`run_diagnostics` 已落地（P-025），但 **web / scripts / batch_backtest 均无 EventLog 读取方**（[web/streamlit_app/pages/01_Overview.py:114](file:///f:/Coding/Factor_Trading_v3.0/web/streamlit_app/pages/01_Overview.py#L114) 仅把 `EventLog` 列为组件名）；第二消费方**尚未出现**。总纲 §5 已把 P-043 排入路线图并以 P-042 为前置，**用户当前指令即立项依据** → 触发条件改写为「路线图批次触发」，裁剪仍保留 U-P025-1 的 P3 边界（不建 Redis / 微服务 / WS）。
- **题干（本批做什么）**:
  1. **总线契约**：在 `core/event_log.py` 增加 `IEventBus` Protocol + `EventType` 常量 + `EventLog.replay()`；
  2. **引擎接入**：`BacktestConfig.event_log_path`（默认 `None`=关闭）+ `BacktestEngineV2(event_bus=...)` 注入；在 5 个生命周期点发射事件（`run_started` / `rebalance` / `day_end` / `error` / `run_finished`）；
  3. **零默认行为**：关闭时零磁盘 I/O、零结果键变化、golden 13 零重录；
  4. **可验证**：seq 连续（含重开续号）、订阅与磁盘一致、`replay(after_seq)` 重放、错误事件不中断回测。
- **明确不做**:
  - 不建 Redis Streams / FastAPI / WebSocket（F7 → P-054）；不建 `live/`（P-053）；
  - 不把 `pending_order_events.csv` 迁入总线（产物兼容，P-053 再议）；
  - 不把 `run_diagnostics` / `invariant_report` / layer dump 迁入总线；
  - 不发射逐订单/逐成交事件（P-053 交易网关再扩，O-P043-2）；
  - 不与 P-042 的 `MarketEvent` / `IStreamingFeed` 合类（前者是**入向行情**，后者是**引擎产出域事件**，语义正交）。
- **职责外（不回答）**: 实时行情接入（P-053）；服务端推送与鉴权（P-054）；Redis 运维。
- **能力边界（回答不了）**: 本批只证明**单进程单写入者**的 seq 连续；多进程/多实例同路径并发写入不在能力内（O-P043-3）。

---

## 2. 代码事实基线（E3）

### 2.1 `core/event_log.py`（400 行，`(Get-Content core/event_log.py).Count`）

| 构件 | 位置 | 现状 |
|------|------|------|
| `EventLogEntry` | L28-36 | `seq:int` / `ts:float` / `type:str` / `payload:dict` / `source:str` |
| `EventLog` | L42-366 | 双写（JSONL + ring buffer）、`threading.RLock`、`buffer_size=500` |
| `append` | L91-129 | 锁内 `seq+=1` → 先写盘 → 入 buffer → 扇出监听器；返回 `EventLogEntry` |
| `read(after_seq, limit, event_type)` | L131-172 | 逐行读盘、`seq > after_seq` 过滤；坏行计入 `skipped_lines` |
| `recent` | L204-225 | 只读内存 buffer |
| `last_seq` | L227-230 | 当前最大 seq |
| `subscribe` / `subscribe_type` | L234-269 | 返回取消订阅闭包；监听器异常**吞掉 + warning**（L286-301） |
| `_append_to_disk` | L273-280 | 写失败 → `write_failures += 1` + `logger.error`，**不抛** |
| `_recover_state` | L303-329 | 启动时读全文件，buffer 取尾部 `buffer_size`，`_seq = entries[-1].seq` |
| `stats` | L282-284 | `read_failures / write_failures / skipped_lines`（P-026） |
| 全局单例 | L371-400 | `get_event_log()` 缺省 `data/events.jsonl`；`log_event()` 首次调用即建文件 |

### 2.2 引擎与插件现状

| 构件 | 位置 | 现状 |
|------|------|------|
| `BacktestEngineV2.__init__` | [engine_v2.py:103-149](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L103-L149) | 12 个可选注入参数；**无 `event_bus`** |
| `run()` | [engine_v2.py:341-386](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L341-L386) | 逐日循环；异常 → `_diagnostics.record(date,"day_loop",e)` 后 `continue`（L365-370） |
| `_process_trading_day` | [engine_v2.py:394-441](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L394-L441) | 再平衡 → 更新市值（L428-429）→ 风控 → dump |
| `_execute_rebalance` | [engine_v2.py:901-995](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L901-L995) | 目标组合在 L977-987 生成；优化失败仅 `diagnostics.record` 后 return |
| `additional_info` | [engine_v2.py:1199-1224](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1199-L1224) | 含 `run_diagnostics` 等；**无事件总线字段** |
| `EventLogPlugin` | [engine_plugins.py:42-173](file:///f:/Coding/Factor_Trading_v3.0/core/engine_plugins.py#L42-L173) | 旁路插件；`enable()` 记 `engine.init`；`log_rebalance/log_trade/log_pending/log_day_end` **仅测试调用** |
| `PluginIntegration` | [engine_plugins.py:405-472](file:///f:/Coding/Factor_Trading_v3.0/core/engine_plugins.py#L405-L472) | `enable_all()` 手动启用三插件；不自动接线 |

### 2.3 其他事件/可观测通道（边界）

| 通道 | 位置 | 与总线的关系 |
|------|------|--------------|
| `PendingOrderQueue._event_log` | [pending.py:291](file:///f:/Coding/Factor_Trading_v3.0/core/pending.py#L291) / `get_event_log` L494-515 | 独立 DataFrame 事件流 → `pending_order_events.csv`（[engine_v2.py:1270-1275](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1270-L1275)）；本批**不迁移** |
| `run_diagnostics` | [diagnostics.py:163-176](file:///f:/Coding/Factor_Trading_v3.0/core/diagnostics.py#L163-L176) | 结果字典载荷；本批仅在 `engine.error` 事件中**引用**同类信息，不替换 |
| `LayerDumper` | `core/change_report.py` | 六层归因 CSV；本批不接入 |
| `MarketEvent` / `IStreamingFeed` | [streaming.py](file:///f:/Coding/Factor_Trading_v3.0/core/streaming.py)（P-042） | **入向行情**契约；与引擎域事件正交，不合类 |
| `LiveTradingBridge` | [live_bridge.py:69-128](file:///f:/Coding/Factor_Trading_v3.0/core/live_bridge.py#L69-L128) | 未来总线消费方（P-053），本批只提供协议 |

### 2.4 配置与产物

- `BacktestConfig` 已有 `dump_layers_dir: Path | None = None`（L343）与 `write_manifest: bool = True`（L347）作为「可选输出」先例；**无事件日志字段**。
- `EventLog` 与 `EventLogPlugin` 的缺省路径均为 `data/events.jsonl`（L52 / engine_plugins L53、L429）；`log_event()` 单例首次调用即建文件（L374-400）——若引擎隐式使用会污染测试与回放。

---

## 3. E1 取证（可重放）

| 读数 | 命令 / 方法 | 结果 |
|------|-------------|------|
| A 引擎是否 import EventLog | `Select-String -Path core/engine_v2.py -Pattern 'EventLog\|event_log'` | `EventLog` 类/模块 **0**；`event_log` 子串 **1** 命中 = [L1271](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1271) `self.pending_queue.get_event_log()`（`PendingOrderQueue` 独立 DataFrame 通道，非 `core.event_log` 总线） |
| B 插件方法是否有生产调用方 | 全仓 `log_rebalance\|log_trade\|log_pending\|log_day_end` 排除 engine_plugins.py | 仅 `tests/test_engine_plugins.py`（L50/L62-64/L73） |
| C EventLog 消费方 | 全仓 `from core.event_log import` | **4 命中**：生产 **1**（`core/engine_plugins.py:32`）+ 测试 **3**（`tests/test_compatibility.py:78` / `tests/test_engine_plugins.py:26` / `tests/test_p026_silent_exception_governance.py:371`） |
| D 协议现状 | `grep "class IEventBus\|replay("` | **0 命中** |
| E 注入面 | Read `engine_v2.py:103-117` | 12 参数，无 `event_bus` |
| F 结果面 | Read `engine_v2.py:1199-1224` | 无 `event_bus` 键 |
| G 第二消费方 | `grep -r "events.jsonl|get_event_log"` web/scripts/batch_backtest | **0**（仅 `pending_queue.get_event_log`，语义不同） |
| H 基线门禁 | P-042 关闭读数 | pytest **795** / golden **13·782** / black **129·196** / mypy **104** / AST **22** / `tests/*.py` **91** / uv **0** |
| I 测试辅助 | `tests/_golden_cases.py` L123-149 / `tests/_synth_fixture.py` | 可复用 `write_price_fixture` / `write_factor` 构造 5 日 × 2 股最小引擎 |

> 本批 Step 1 为只读取证，未运行 pytest/git 写入；H 读数沿用 P-042 关闭基线，Step 9 必须本批复跑。

---

## 4. 缺口清单

| ID | 缺口 | 级别 | 证据 |
|----|------|------|------|
| **G1** | 引擎未接入 `EventLog`——统一事件通道不存在 | P2 | A |
| **G2** | `EventLogPlugin.log_*` 4 方法无生产调用方（名义能力/死 API 风险） | P2 | B |
| **G3** | 无 `IEventBus` 协议——live/services 无法面向契约编程 | P2 | D |
| **G4** | 无 `replay()` 便捷入口（只有 `read(after_seq)`，语义不自证） | P3 | D |
| **G5** | 事件类型为自由字符串，无单一常量表 | P3 | 读码 |
| **G6** | 缺省路径 `data/events.jsonl` + 全局单例有隐式建文件副作用 | P3 | L371-400 |
| **G7** | 两个 `EventLog` 实例指向同一路径会各自从磁盘恢复 seq → 写入冲突 | P3 | `_recover_state` L303-329 |
| **G8** | `pending_order_events.csv` 与总线双通道并存，口径未声明 | P3 | 2.3 |

---

## 5. 方案矩阵

| 方案 | 内容 | 判定 |
|------|------|------|
| **M-A（推荐）** | **契约 + 引擎原生接入**：`IEventBus` + `EventType` + `replay()`；`event_log_path` 默认 `None`；引擎 5 个生命周期点发射；关闭时零 I/O / 零结果键 | ✅ 最小、默认零行为、可独立验证；直接关闭 G1-G5（**D 阶段订正**：G2 不由此方案关闭，见 DESIGN-D8） |
| M-B | 引擎调用 `EventLogPlugin.log_*` | ❌ 插件仍是外部旁路，需同样多的引擎改动，却引入「config 路径」与「plugin 路径」两套入口；插件缺省路径还会隐式建文件 |
| M-C | 全量迁移：订单/成交/诊断/layer 全进总线并替换 CSV | ❌ 破坏 `pending_order_events.csv` / `run_diagnostics` / golden 产物契约，改动面跨 P-053/P-054 |
| M-D | 只加协议与测试，不接引擎 | ❌ 不满足 U-P025-1「接入引擎」 |
| M-E | 直接上 Redis Streams | ❌ 新增服务与依赖，违背「先跑通」；F7 属 P-054 |

**裁决**: **M-A**。理由：唯一同时满足「关闭零行为 / 不破坏既有产物 / 关闭真实缺口 / 为 P-053/P-054 提供契约」的方案。

---

## 6. 批次切分（供 DESIGN 采用）

| 批次 | 内容 | 行为 | 验收 |
|------|------|------|------|
| **B1 契约与重放** | `core/event_log.py`：`IEventBus` Protocol + `EventType` 5 常量 + `EventLog.replay(after_seq, handler=None)` | 零行为（新符号） | 协议 4 方法；`replay(k)` 返回 `seq>k` 升序；重开续号 |
| **B2 引擎接入** | `config.event_log_path: Path \| None = None`；`BacktestEngineV2(event_bus=None)`；`_emit` + 5 发射点；结果键仅在启用时出现 | 默认零行为；启用时旁路写盘 | seq 1..N 连续；run_started 首/run_finished 尾；day_end 数 = 交易日数；error 不中断 |
| **B3 测试与文档** | 新建 `tests/test_p043_event_bus.py`（V1-V8）；四文档 + 台账 | 新增只读面 | pytest **795 → 803**；golden 13 零重录；mypy **104** 不变 / black **129·196 → 130·197**（+1 测试文件，F-D3-P043-1 订正） |

> B2 依赖 B1；B3 与 B2 同批提交即可。三批均不触碰复权/对齐/交易语义。

---

## 7. 精确语义（实施规格输入）

| # | 语义 |
|---|------|
| S1 | `EventType` 常量（5 个，逐字）：`engine.run_started` / `engine.rebalance` / `engine.day_end` / `engine.error` / `engine.run_finished` |
| S2 | `IEventBus` 4 方法：`append(event_type, payload, source="") -> EventLogEntry`；`last_seq() -> int`；`read(after_seq=0, limit=None, event_type=None) -> list[EventLogEntry]`；`subscribe(listener) -> Callable[[], None]` |
| S3 | `EventLog.append` 现有语义不变：单进程内 seq 从 1 起严格 +1；重开后从磁盘最后 seq 续号 |
| S4 | `replay(after_seq=0, handler=None)`：返回 `read(after_seq)` 的升序条目；提供 handler 时逐条调用，**handler 异常向外传播**（与 listener 吞错不同，重放需可失败） |
| S5 | `BacktestConfig.event_log_path: Path \| None = None`；`None` = 关闭（零 I/O、零结果键） |
| S6 | 注入优先级：`BacktestEngineV2(event_bus=...)` > `cfg.event_log_path`；两者同时存在时**不创建第二个实例** |
| S7 | 事件 payload 键集：<br>`run_started {start:str, end:str, n_dates:int}`<br>`rebalance {date:str, n_targets:int}`<br>`day_end {date:str, total_value:float}`<br>`error {date:str, stage:str, error_type:str, message:str}`<br>`run_finished {elapsed_s:float, n_days:int}` |
| S8 | `_emit` 永不抛错：总线异常 → `self._event_bus_errors += 1` + `logger.debug`；不改变回测流程 |
| S9 | 结果键 `additional_info["event_bus"] = {"enabled": True, "last_seq": int, "errors": int}`，**仅启用时出现** |
| S10 | `pending_order_events.csv` / `run_diagnostics` / `invariant_report` / layer dump / manifest 零改动 |

---

## 8. 行为变更与不变式

**默认关闭（`event_log_path=None` 且无注入）**：零磁盘 I/O、零新结果键、交易/净值/产物逐值不变。
**启用时（新增只读面）**：额外写 `events.jsonl`（旁路），新增结果键 `event_bus`。

| ID | 不变式 |
|----|--------|
| I1 | 默认关闭：golden **13 零重录**；`additional_info` 无 `event_bus` 键；无 `events.jsonl` 新建 |
| I2 | 启用：事件 seq 覆盖 `1..N` 连续无洞；`run_started.seq == 1`，`run_finished.seq == N`（DESIGN 阶段细化：限**空路径**；重开续号归 I7） |
| I3 | `day_end` 事件数 = 交易日数；`rebalance` 事件数 = 实际触发再平衡次数 |
| I4 | `replay(k)` 返回 `seq > k` 的升序全集，与 `read(after_seq=k)` 逐条一致 |
| I5 | 订阅回调收到的 seq 集合 = 同次运行磁盘事件的 seq 集合 |
| I6 | 总线异常（注入会抛的 fake bus）不改变回测结果与成交数 |
| I7 | 重开同一路径：首个新事件 seq = 旧 `last_seq + 1`；无重复 seq |
| I8 | 零新增依赖；无 `live/`、无 Redis/WS/FastAPI；`tests/*.py` 91 → 92 |
| I9 | `pending_order_events.csv`、`run_diagnostics`、`invariant_report`、layer dump 零 diff |

---

## 9. 未决项登记（四元块）

- **U-P043-1 协议放置位置**
  - 判据：`IEventBus` 放 `core/event_log.py`（同域，零新文件）还是新建 `core/event_bus.py`（契约与实现分离）
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**`core/event_log.py`**（避免新文件与重复概念；mypy/black 计数不变）
  - 证据等级：E3（架构原则）

- **U-P043-2 订单/成交事件**
  - 判据：本批是否发射逐订单/逐成交事件
  - 触发条件：P-053 交易通道网关立项
  - 当前倾向：**P-053 再扩**；本批仅生命周期 5 类
  - 证据等级：E3（M-C 拒绝理由）

- **U-P043-3 多实例同路径**
  - 判据：是否加文件锁/独占检测
  - 触发条件：出现多进程写同一 `events.jsonl` 的真实场景
  - 当前倾向：**文档声明不支持**（单进程单写入者）；不引入锁
  - 证据等级：E3（G7）

- **U-P043-4 CLI 开关**
  - 判据：是否加 `cli.py run --event-log PATH`
  - 触发条件：P-054 服务层需要外部可配
  - 当前倾向：**本批仅 config 字段**；CLI 后置
  - 证据等级：E3（范围控制）

- **U-P043-5 异构终审**
  - 判据：Step 2/4/6/8/10 复审基座与作者不同
  - 触发条件：进入 Step 10
  - 当前倾向：作者 DeepSeek-V4.1-Flash；终审由 GLM-5.3-Flash 承接
  - 证据等级：E1（会话基座）

---

## 10. 可重放命令

```powershell
$py = 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe'
# E3：引擎/插件/通道（只读）
& $py -c "import pathlib; print('EventLog in engine_v2:', 'EventLog' in pathlib.Path('core/engine_v2.py').read_text(encoding='utf-8'))"
# E1 基线（Step 9 必跑）
$env:MPLBACKEND='Agg'; & $py -m pytest tests -q -p no:cacheprovider
& $py -m pytest tests -k golden -q -p no:cacheprovider
& $py -m black --check core tests
& $py -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
uv lock --check
```

> Step 1 未执行上述命令（只读取证）；基线沿用 P-042 关闭读数，Step 9 回填红/绿。

---

## 11. Step 1 自查（RULE-4）

| # | 自查项 | 结论 |
|---|--------|------|
| 1 | 题干是否收窄 | ✅ 五项收窄见 §1；Redis/WS/live/全量迁移均排除 |
| 2 | 事实与推测分离 | ✅ G1-G8 均有 E3 行号；U-P025-1 触发条件改写显式裁决 |
| 3 | 是否重做 P-042 | ✅ 明确不复用 `MarketEvent`，不改数据层 |
| 4 | 是否以「跑通」代替正确性 | ✅ 验收含 seq 连续/重放/订阅一致/错误不中断 |
| 5 | 方案矩阵是否穷举 | ✅ M-A~M-E；四条拒绝理由 |
| 6 | 是否触碰交易/净值语义 | ✅ 零变更（I1/I6/I9） |
| 7 | 是否新增外部依赖 | ✅ 零新增（仅 stdlib） |

---

## 12. 判档

**T1**——变更面含 `core/engine_v2.py`（V2 主循环）与 `core/event_log.py`（契约），且新增 `IEventBus` **契约变更**（判档规则 2 强制 T1）。

---

## 13. Step 2 Review（同基座独立视角，2026-11-18）

> **基座披露（RULE-4）**: 复审 DeepSeek-V4.1-Flash = 作者**同源**；RULE-5 不成立 → U-P043-5 跟踪；终审须异构。

### 13.1 机械复核

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 引擎 EventLog 接入 | `engine_v2.py` 的 `EventLog` 符号 0；唯一 `event_log` 子串为 L1271 `pending_queue.get_event_log()`（独立通道） | ✅ G1 成立 |
| 2 | 插件方法调用方 | 仅测试 | ✅ G2 成立 |
| 3 | 协议缺失 | `IEventBus`/`replay(` 0 命中 | ✅ G3/G4 成立 |
| 4 | 缺省路径副作用 | `event_log.py` L371-400 首次 `log_event` 建文件 | ✅ G6 成立 |
| 5 | 第二消费方 | web/scripts/batch 0 读取 | ✅ 触发改写出处成立 |
| 6 | 测试夹具可复用 | `_synth_fixture.write_price_fixture/write_factor` | ✅ V4-V7 可落地 |
| 7 | 计数链 | 795+8=803；tests 91+1=92；mypy/black 不变 | ✅ 自洽 |

### 13.2 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S2-P043-1 | P2 | U-P025-1 原触发条件（第二消费方）**未满足**，若照抄会与台账矛盾 | §1 显式裁决「路线图批次触发」，保留 P3 边界；Step 3 回写 PROGRESS U-P025-1 触发说明 |
| F-S2-P043-2 | P3 | `EventLogPlugin` 与 `config.event_log_path` 可能同时启用，两实例同路径 → seq 冲突 | 登记 O-P043-3（文档声明不支持）+ U-P043-3；B2 注入优先级 S6 |
| F-S2-P043-3 | P3 | 缺省路径 `data/events.jsonl` 可能被误认为「默认开启」 | S5 明确 `event_log_path=None` 默认关闭；引擎**不使用** `log_event()` 全局单例 |
| F-S2-P043-4 | P3 | §3 读数 A 用大小写不敏感子串匹配却记「0 命中」（[L1271](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1271) `pending_queue.get_event_log()` 实为独立通道）；读数 C 的 import 清单漏 2 个测试文件 | §3 A/C 按实测订正（生产消费方仍仅 `engine_plugins.py` 1 处，G1/G2 结论不变）；PROGRESS §3.49.1 同步 |

### 13.3 结论

**Step 2 Review pass（1 P2 + 3 P3 当轮处置）**——G1-G8 均有 E3 证据、方案矩阵穷举、U-P025-1 触发改写显式；**准予进入 Step 3 DESIGN**。
**RULE-5**: 同基座 → U-P043-5 pending（终审须 GLM-5.3-Flash）。
