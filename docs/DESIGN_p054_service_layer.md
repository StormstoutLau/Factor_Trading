# DESIGN：P-054 服务层（单写者交易进程 + FastAPI/WS 多 worker + 可靠事件外发 + 通道流控前置包 + Python 3.11 基线）

> **批次**: P-054 · **Step 3 设计** · 日期 2026-11-22 · **判档 T1（全量）**
> **上游**: [RESEARCH_p054](RESEARCH_p054_service_layer.md)（§19-§22 全量 Step 1 + Q1-Q20 裁决）；[REVIEW_p054_step2](REVIEW_p054_step2_research.md)（两轮 0 P1 + §9 定点复验通过，Step 2 关闭）
> **总纲**: F7 L223-232 / L271；§6 依赖分档（`[services]`）；§7.1 D2（自用工具 + 仅本机/内网）
> **口径**: Q8/Q9/Q11/Q12/Q13/Q14/Q15-Q20 为用户已裁决（RESEARCH §15-§22）；本文件只做工程定案（§0.2），不重开裁决
> **零代码/零门禁变更**：本批交付设计文档；Step 5 才落码；B0（Python 3.11 基线）单列为前置小任务

---

## 0. 裁决记录

### 0.1 继承裁决（RESEARCH 已定，本文件不改写）

| 项 | 裁决 | 出处 |
|----|------|------|
| **Q8** | 共享 FTD 预算纳入 P-054：`FtdBudget`，默认 6/s 可配 + `ftd_reserve=1`，**发送前 reserve** | §13/§15.2 |
| **Q9** | 报单+撤单合并 order-flow 预算，默认 `2 × internal_per_second`，两类型桶各 1/s 保留 | §15.3/§17.4 |
| **Q10** | 限流原语本轮**不改造**（保留 `check_rate`/`RateLedger`），仅让 `FtdBudget` 先产出 `Decision` 形状 | §15.4 |
| **Q11** | outbox 重建 `seq INTEGER PRIMARY KEY AUTOINCREMENT` + 版本化 `event_id` + 冲突报错 + inbox，**与 U-P053-17 同一次迁移** | §16.6 |
| **Q12** | kill-switch：撤单优先通道 + `reserve_cancel=1` + 显式 deferred，不绕过 CTP 物理限额 | §22.7 |
| **Q13** | **全局升 Python >= 3.11**（单列小任务 B0） | §19.3 |
| **Q14** | 不做 Phase 0，直接 F7 全量多 worker | §20.6 |
| **Q3** | 组合写改造落点 = **P-054 批内**（随 Q11 用户裁决「同一次迁移完成」，不开 P-053b 补丁批） | §10 L317 |
| **Q4** | relay 载体 = **交易进程内 outbox 轮询 relay → Redis 发布**（Streams 可靠投递 / Pub/Sub 广播 worker，随 Q14 裁决） | §10 L318 |
| **Q15** | API Key + `hmac.compare_digest`；JWT 预留；WS 短时一次性 ticket | §22.4 |
| **Q16** | TLS 全启用（含 loopback），TLS 1.3/1.2，禁用 1.0/1.1 | §22.5 |
| **Q17** | `prometheus-client` + 四黄金信号 + 领域指标；JSON 日志；不上 Grafana 栈 | §22.6 |
| **Q18** | 单实例交易/账本进程 + N 个无状态 API/WS worker，不用 leader election | §22.1 |
| **Q19** | 同机只读 SQLite（`mode=ro`/`query_only`）；跨机内部 API；不建 Redis 读模型 | §22.3 |
| **Q20** | 本地 Docker Desktop(WSL2) + `redis:7`；CI Ubuntu `services: redis`；单测 FakeBus | §22.2 |

### 0.2 Step 3 工程定案（本文件新增）

| 项 | 定案 | 落点 |
|----|------|------|
| **Q1 外发事件集合** | **6 类**：`order.accepted` / `order.rejected` / `order.canceled` / `order.cancel_rejected` / `order.status` / `fill.applied`（**对账不入 outbox**：仅 `AUDIT_RECONCILE`，F-I6） | §3.4 / D5 |
| **Q2 event_id** | `<agg_type>:<agg_id>:<event>:v<n>`；`n` 取 `OrderRecord.event_version`（新增字段，随状态变更单调 +1）或 `fill_key`；同 `event_id` 不同 payload 抛 `OutboxEventConflict` | §3.4 / D6 |
| **Q5 退避数值** | 初始 **1.0s**、倍率 **2.0**、封顶 **5.0s**、最多 **5 次**、**Full Jitter**（`uniform(0, min(1×2^(n-1), 5))`） | §5 / D8 |
| **Q6 降级语义** | `query_trades`/`query_orders` 最终失败 → `start()` **fail-closed**；`query_positions` 失败 → `recovery_state="degraded_positions"`，网关可用、对账不可用、ready=200 `degraded=true` | §4.3 / D8 |
| **Q7 巡检覆盖** | 是：持仓巡检与启动恢复共用**同一个** `QueryScheduler`（同一 1/s 查询桶 + 单在途），默认巡检间隔 6s | §4.3 / D8 |
| **WS 序号源** | 订单通道 `seq = outbox.seq`（快照水位 = 同一读事务内 `MAX(seq)`）；行情通道 `tick_seq` 独立、允许缺口 | §3.6 / D12 |
| **WS 重连** | **一律重发 snapshot**（不以 delta 续传）；`resume.last_seq` 仅用于客户端自检与 `missed` 标记 | §3.6 / D12（偏差见 §8-4） |
| **ticket 存储** | Redis `SET p054:ticket:<token> 1 NX EX 30` + `GETDEL` 单次使用（多 worker 可共享） | §3.5 / D14 |
| **outbox 保留** | 已发送行保留 **7 天**（供 `/api/events` 排查）；超期由交易进程每日 purge（永不删最大 seq） | §5 / D7 |
| **REST 唯一写端点** | `POST /api/admin/broadcast-pause`（暂停/恢复行情推送，admin key）；**不含任何下单/撤单逻辑** | §3.7 / D19 |
| **实施批次** | B0 基线 → B1 store → B2 流控 → B3 事件 → B4 服务层 → B5 运行时 → B6 验收 | §10.2 |

### 0.3 不改写的既有契约（只引用 / 仅做加法）

- **P-053 `LedgerStore` Protocol**：现有 8 方法签名保留；新增方法全部为**追加**（§3.3 标注「新增/替换」）。
- **`TradingGateway.cancel() -> bool`**：签名与返回值语义保留；G15 通过新方法 `cancel_ex() -> CancelResult` + 强制 audit 实现，`cancel()` 委托 `cancel_ex().accepted`。
- **`EventType` 8 个 `audit.*` 常量**：不新增、不改名；`order.cancel_rejected` 走 **outbox**（业务事件），审计仍用 `AUDIT_CANCEL`。
- **`EventLog` / `IEventBus`**：API 不变；仍只由交易进程写。
- **D16（P-053「outbox 只写不读」）**：P-054 起**失效**（本批新增 relay/消费者），属批次边界转移，不是对 P-053 契约的改写。

---

## 1. 目标与非目标

**做**（本批验收面）：

1. **存储原子化**（U-P053-17）：新增「业务写 + outbox」组合写 API，消除双写不一致与 `apply_fill` 两事务。
2. **outbox v2 迁移**（Q11）：`seq AUTOINCREMENT` + `(sent, seq)` 索引 + 版本化 `event_id` + `OutboxEventConflict` + `inbox` + `meta`。
3. **通道流控前置包**（Q8/Q9/Q12/G15）：`FtdBudget` + `OrderFlowBudget` + 撤单显式拒绝 + 撤单优先槽位。
4. **查询调度器**（U-P053-18 + Q5-Q7）：最小间隔、单在途、`-2/-3` 全抖动退避、启动串行恢复、巡检共用。
5. **事件外发**：outbox relay → Redis Streams → 单消费者 → Redis Pub/Sub 扇出全 worker（at-least-once）。
6. **服务层**：`services/api.py`（REST 只读管理面 + 鉴权 + TLS + 指标）、`services/ws_hub.py`（snapshot+delta/seq/心跳/背压）、`services/market_gateway.py`（行情源 → Pub/Sub）。
7. **进程拆分**（Q18）：单实例交易/账本进程 + N 个无状态 API/WS worker；同机只读 SQLite。
8. **Python 3.11 基线**（Q13/B0）：`requires-python`、CI 矩阵、black/mypy 目标、`pydantic>=2.9.0`。
9. **验收**：WS seq 连续、snapshot+delta 重放一致、401/403、REST 不含下单/撤单、延迟基准报告。
10. 四文档 + 台账（Step 4/5/7/9/10）。

**不做**（外置）：

- 微服务化 / 跨机部署编排（P-055）；跨机只读 API 的**实现**（Q19 只要求文档化回退路径）。
- 真实行情接入（本批 synthetic 源 + `MarketDataSource` 端口）；真实 CTP 联调（沿用 P-053 语义层）。
- REST/WS 下单、撤单、kill-switch 的 HTTP 暴露（REST 管理面明确不含交易逻辑）。
- JWT / 多用户 / RBAC（Q15 预留）；mTLS 强制（可选参数，不默认开）。
- Q10 的 `try_acquire` 全局替换、GCRA/滑动日志。
- Grafana/Loki/Tempo 全栈；分布式追踪。
- 多 relay 并行 / 按 `coid` 分区（单 relay 全局有序，Q11 残留不确定性已记录）。

---

## 2. 模块拓扑与依赖

### 2.1 进程拓扑

```
[market_gateway 进程]（可 1 个，无状态）
    └── PUBLISH p054:market ─────────────────────────────┐
                                                         │
[trading/ledger 进程 单实例]                              │
  ├── SQLite（唯一写者，.lock，WAL）                       │
  ├── TradingGateway（P-053）+ Ledger                      │
  ├── QueryScheduler + FtdBudget + OrderFlowBudget        │
  ├── outbox relay：pending_outbox → XADD p054:orders      │
  ├── Streams 消费者（单消费者）：XREADGROUP → PUBLISH      │
  │      └── p054:orders:events ─────────────────────────┤
  ├── EventLog append（唯一写入者）                        │
  └── Redis heartbeat：trading（1s）/ consumer（2s）（EX 10）    │
                                                         │
                                    ┌────────────────────┴───────────┐
                                    │ Redis                          │
                                    │  · p054:market (Pub/Sub)       │
                                    │  · p054:orders (Stream)        │
                                    │  · p054:orders:events (Pub/Sub)│
                                    │  · p054:ticket:<token> (TTL 30)│
                                    │  · p054:trading:heartbeat (10s)│
                                    │  · p054:consumer:heartbeat (10s)│
                                    └────────────────┬───────────────┘
                                                     │ 订阅
                    [API/WS worker × N]（无状态，uvicorn --workers N）
                      ├── REST：只读 SQLite（mode=ro/query_only）
                      ├── WS：snapshot + delta（seq=outbox.seq）
                      ├── /health/live|ready、/metrics
                      └── 不实例化 writer、不 append EventLog
```

### 2.2 模块清单

| 模块 | 类型 | 职责 | 依赖 |
|------|------|------|------|
| `live/events.py` | 新增 | outbox 事件类型常量、`OrderRecord.event_version` 递增规则、payload 规范化与构造器 | `live/orders.py` |
| `live/flow_control.py` | 新增 | `Decision`、`FtdBudget`、`OrderFlowBudget`（单锁、发送前 reserve、退还仅限本地未发出） | stdlib |
| `live/query_scheduler.py` | 新增 | `QueryScheduler`：最小间隔 + 单在途 + Full Jitter 退避 + 启动串行恢复 + 巡检入口 | `live/flow_control.py`、`live/channel.py` |
| `live/ledger_store.py` | 改造 | 组合写 API、outbox v2 迁移、inbox、meta、只读模式 | `live/events.py` |
| `live/gateway.py` | 改造 | 预算接线、事件发射、`cancel_ex`、启动恢复改走调度器、能力声明修正 | 上述 |
| `live/adapters/ctp.py` | 改造 | `max_ftd_per_sec=6.0` / `ftd_reserve=1` 声明；`max_submit/cancel_per_sec` 不再被读作独立上限 | `live/channel.py` |
| `services/contracts.py` | 新增 | `EventPublisher`/`OrderStream` Protocol、`StreamMessage`、DTO 与错误码 | stdlib |
| `services/bus.py` | 新增 | `RedisBus`（Pub/Sub + Streams）与 `InMemoryBus`（FakeBus，单测/单进程） | redis |
| `services/config.py` | 新增 | `ServiceSettings`（pydantic，env 前缀 `P054_`，`extra="forbid"`） | pydantic |
| `services/auth.py` | 新增 | API Key 校验（常数时间）、角色、**`TicketStore` Protocol + Redis/InMemory 两实现**、认证失败限流 | redis/pydantic |
| `services/metrics.py` | 新增 | Prometheus registry、指标定义、`/metrics` 输出 | prometheus-client |
| `services/api.py` | 新增 | FastAPI app factory：REST 只读、health、ticket、metrics、CORS、异常映射 | fastapi |
| `services/ws_hub.py` | 新增 | WS 连接管理、worker 级 Pub/Sub 订阅、每连接有界队列、snapshot+delta、心跳/慢客户端 | fastapi/starlette |
| `services/market_gateway.py` | 新增 | `MarketDataSource` 端口 + synthetic 源 → `p054:market`；**独立入口 `python -m services.market_gateway`（推荐），`--embedded` 由 trading_worker 内嵌（单机开发）** | `services/bus.py` |
| `services/outbox_relay.py` | 新增 | relay 循环（批量、XADD、`mark_sent(seq)`、退避、保留期 purge） | store/bus |
| `services/trading_worker.py` | 新增 | 交易进程装配：store/gateway/scheduler/relay/consumer/heartbeat/优雅退出 | 全部 |
| `services/api_worker.py` | 新增 | uvicorn 入口（`--factory`、TLS、workers 透传） | uvicorn |
| `services/__init__.py` | 新增 | 包标记 | — |
| `scripts/p054_bench_ws.py` | 新增 | 延迟基准（三段采样 p50/p95/p99） | services |

### 2.3 分层规则

1. `live/*` **不得** import `services/*`（I16）；`services/*` 可 import `live/*`、`core/*`。
2. API worker **只允许**构造 `SqliteLedgerStore(read_only=True)`；启动断言 `store.is_read_only`。
3. 只有 `trading_worker` 能构造 writer store、append `EventLog`、运行 relay/consumer。
4. `services/contracts.py` 不 import redis/fastapi（纯协议 + DTO），保证 `InMemoryBus` 与单测零外部依赖（D4）。

### 2.4 进程内并发与连接模型（F-D1/F-D2 修复）

**交易/账本进程（单实例、单写者）**

| 执行单元 | 职责 | SQLite 访问 |
|----------|------|-------------|
| 主线程 | `gateway.poll()` 循环（P-053 同步）+ QueryScheduler + 组合写 | writer 连接（唯一） |
| `relay` 线程 | `pending_outbox(100)` → XADD → `mark_sent(seq)`；失败退避 | writer 连接（经 `_write_lock`） |
| `consumer` 线程 | `XREADGROUP`（block 1s）→ PUBLISH → inbox → XACK；周期 `XAUTOCLAIM` | writer 连接（经 `_write_lock`） |
| heartbeat 线程 | Redis `SET p054:trading:heartbeat <ts> EX 10`（1s）+ consumer 心跳（2s） | **不写 SQLite** |

- **writer 连接**：`sqlite3.connect(..., check_same_thread=False)` + 进程内 `threading.RLock`（`_write_lock`）包住每个 `transaction()`；跨进程仍由 `.lock` + WAL 单写者保证。锁的目的只是避免自有线程在 `BEGIN IMMEDIATE` 上互等 5s 超时。
- **Redis 客户端**：relay/consumer/heartbeat 线程使用**同步** `SyncRedisBus`（redis-py `Redis`），不在无事件循环的线程里调协程；API/WS 侧使用 `AsyncRedisBus`（F-I7）。
- **心跳不落 SQLite**：避免 `synchronous=FULL` 下每秒一次 fsync 与订单写抢同一把写锁；`meta` 只保留低频键（`schema_version` / `recovery_state` / `recovery_ts`，见 §3.1）。
- **启动顺序**：打开 writer → 迁移 → 恢复（QueryScheduler 串行）→ 写 `recovery_state` → 启动 relay/consumer/heartbeat → 写首个心跳。
- **退出**：SIGINT/SIGTERM → `stop_event.set()` → `join(timeout=5s)` → `store.close()`（先关连接再删 `.lock`）。

**API/WS worker（N 个无状态进程）**

- **每 worker 一个只读连接**：`SqliteLedgerStore(read_only=True)`，`check_same_thread=False` + 进程内 `_read_lock`（RLock）；lifespan 启动时打开，退出时关闭。
- **REST 端点用 `def`**（FastAPI 线程池执行）；所有 store 读经 `_read_lock` 串行（WAL 读为毫秒级，自用规模足够）。
- **WS 端点用 `async def`**：连接读快照走 `anyio.to_thread.run_sync(store.snapshot)`（同样受 `_read_lock` 保护）；订阅/发送全在事件循环内，不触碰 SQLite writer。
- **不共享连接**：worker 之间不共享 sqlite3 连接；跨进程并发由 WAL + 只读 URI 承担（前提见 §9-R1）。
- **端点的线程数**：SQLite 读串行是唯一约束；HTTP/WS 并发本身不受限（等待锁期间不阻塞事件循环，因为 `def` 端点在线程池）。

---

## 3. 数据契约

### 3.1 SQLite schema v2（`live/ledger_store.py`）

```sql
-- 既有表保持不变
CREATE TABLE IF NOT EXISTS ledger_entry (
  entry_id TEXT PRIMARY KEY, kind TEXT NOT NULL, ts REAL NOT NULL, asset TEXT NOT NULL,
  quantity REAL NOT NULL, price REAL NOT NULL, amount REAL NOT NULL, fee REAL NOT NULL,
  ref TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_entry_ref ON ledger_entry(ref);

CREATE TABLE IF NOT EXISTS order_record (
  client_order_id TEXT PRIMARY KEY, broker_order_id TEXT NOT NULL, state TEXT NOT NULL,
  payload TEXT NOT NULL, updated_ts REAL NOT NULL);

-- v2：outbox 重建
CREATE TABLE IF NOT EXISTS outbox (
  seq            INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id       TEXT NOT NULL UNIQUE,
  aggregate_type TEXT NOT NULL,
  aggregate_id   TEXT NOT NULL,
  event_type     TEXT NOT NULL,
  payload        TEXT NOT NULL,
  created_ts     REAL NOT NULL,
  sent           INTEGER NOT NULL DEFAULT 0,
  sent_ts        REAL
);
CREATE INDEX IF NOT EXISTS ix_outbox_unsent ON outbox(sent, seq);

-- 消费端去重
CREATE TABLE IF NOT EXISTS inbox (
  event_id     TEXT PRIMARY KEY,
  processed_ts REAL NOT NULL
);

-- 进程间状态（API worker 只读）
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

**迁移（`__init__` 内，幂等）**：

1. 读 `meta.schema_version`（表不存在视为 `1`）与 `PRAGMA table_info(outbox)`。
2. 若 `schema_version >= 2` 且 outbox 含 `seq` → 跳过。
3. 否则在**单个 `BEGIN IMMEDIATE`** 内：`ALTER TABLE outbox RENAME TO outbox_v1` → 建新表 → `INSERT INTO outbox(event_id,aggregate_type,aggregate_id,event_type,payload,created_ts,sent,sent_ts) SELECT event_id,'legacy',event_id,event_type,payload,created_ts,sent,NULL FROM outbox_v1 ORDER BY rowid` → `DROP TABLE outbox_v1` → 建 inbox/meta → `INSERT OR REPLACE INTO meta VALUES('schema_version','2')`。
4. 旧库按原 `rowid` 序映射为 `seq`，保持历史顺序；`legacy` 聚合仅用于迁移行，不参与新事件分区。

**meta 键**：

| key | 写入方 | 语义 |
|-----|--------|------|
| `schema_version` | 交易进程 | `"2"` |
| `recovery_state` | 交易进程 | `incomplete` / `complete` / `degraded_positions` / `failed` |
| `recovery_ts` | 交易进程 | 最近一次恢复完成时间（epoch 秒） |

> **心跳不在此表**（F-D2）：交易/消费者心跳改为 Redis TTL 键（§3.5），避免 `synchronous=FULL` 下每秒 fsync 与订单写争锁。

### 3.2 Python 契约（`live/events.py`、`live/flow_control.py`）

```python
class OutboxEventType:
    ORDER_ACCEPTED = "order.accepted"
    ORDER_REJECTED = "order.rejected"
    ORDER_CANCELED = "order.canceled"
    ORDER_CANCEL_REJECTED = "order.cancel_rejected"
    ORDER_STATUS = "order.status"
    FILL_APPLIED = "fill.applied"

@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    aggregate_type: str      # "order" | "fill"（reconcile 不入 outbox，F-I6）
    aggregate_id: str        # coid | fill_key
    event_type: str
    payload: str             # canonical JSON
    created_ts: float

@dataclass(frozen=True)
class OutboxRecord:
    seq: int
    event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: str
    created_ts: float
    sent_ts: float | None

class OutboxEventConflict(RuntimeError): ...

@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after_ms: int = 0
    reason: str = ""         # "ftd" | "order_flow" | "per_second" | "daily" | ""

@dataclass(frozen=True)
class CancelResult:
    accepted: bool
    reason: str = ""         # "" | "not_found" | "terminal" | "rate_order_flow" | "rate_ftd" | "unsupported"
    retry_after_ms: int = 0

@dataclass(frozen=True)
class CancelAllReport:
    requested: int           # 遍历到的非终态订单数
    submitted: int           # 实际发出撤单请求
    deferred: tuple[str, ...]  # 因预算耗尽排队/延后的 coid（显式，不静默丢）
    rejected: tuple[tuple[str, str], ...]  # (coid, reason)

class StoreReadOnlyError(RuntimeError):
    reason: str              # "permission" | "uninitialized" | "not_wal" | "internal_api_required"
```

> **落点归属（二轮复审注）**：`OutboxEventType` / `OutboxEvent` → `live/events.py`；`Decision` / `CancelResult` → `live/flow_control.py`；`CancelAllReport` → `live/gateway.py`；`OutboxRecord` / `OutboxEventConflict` / `StoreReadOnlyError` → `live/ledger_store.py`（§3.2 标题仅列两个主要模块，落点以本注为准）。

**`OrderRecord` 追加字段**（`live/orders.py`，默认值保证旧 payload 可反序列化）：

```python
event_version: int = 0   # 每次状态/关键字段变更 +1；作为 event_id 的 v<n>
```

`transition()` 在返回新记录时执行 `event_version = record.event_version + 1`。

### 3.3 `LedgerStore` Protocol v2（新增/替换标注）

| 方法 | 状态 | 说明 |
|------|------|------|
| `append_entry(entry) -> bool` | 保留 | 单分录；不得再与 outbox 分两次调用 |
| `append_entries(entries) -> int` | **新增** | 单事务批量分录；返回插入条数 |
| `append_entries_with_events(entries, events) -> int` | **新增** | 批量分录 + outbox **同一事务** |
| `upsert_order(record) -> None` | 保留 | 单写；仅供只读/测试场景 |
| `upsert_order_with_events(record, events) -> None` | **新增** | 订单 + outbox 同一事务 |
| `append_outbox(events: Sequence[OutboxEvent]) -> None` | **替换签名** | 仅用于「无业务写」的事件（如 `order.cancel_rejected`）；内部逐条比对冲突 |
| `pending_outbox(limit: int = 100) -> list[OutboxRecord]` | **替换返回** | `WHERE sent=0 ORDER BY seq LIMIT ?` |
| `mark_sent(seq: int, ts: float) -> None` | **替换签名** | 按 `seq` 标记 |
| `outbox_after(after_seq: int, limit: int) -> list[OutboxRecord]` | **新增** | `/api/events` 与排查用 |
| `max_outbox_seq() -> int` | **新增** | 快照水位 |
| `purge_outbox(before_ts: float) -> int` | **新增** | 仅删 `sent=1 AND created_ts < before_ts` |
| `inbox_has(event_id) -> bool` / `mark_inbox(event_id, ts)` | **新增** | 消费端去重 |
| `get_meta(key) -> str | None` / `set_meta(key, value)` | **新增** | 进程间状态 |
| `snapshot() -> StoreSnapshot` | **新增** | 单读事务：`MAX(seq)` + orders + ledger 分录 |
| `entries()` / `load_orders()` / `transaction()` / `close()` | 保留 | 语义不变 |

**只读模式与 preflight**（F-D1/F-D9）：

- `SqliteLedgerStore(path, read_only=True)` → 跳过 `.lock`；URI `file:<path>?mode=ro` + `PRAGMA query_only=ON`；不建表；连接 `check_same_thread=False` + 进程内 `_read_lock`（§2.4）。
- 启动 preflight 按根因分类抛 `StoreReadOnlyError.reason`：
  - `"uninitialized"`：库/`outbox` 表不存在（`no such table`）→ 提示「先启动 trading_worker」；
  - `"permission"`：`unable to open database file` → 提示同用户/目录授权/内部 API 三条路径；
  - `"not_wal"`：`journal_mode != 'wal'` → 提示先由交易进程初始化 WAL；
  - `"internal_api_required"`：显式配置走 Plan B。
- worker 启动失败（不进入 ready）；错误消息必须包含上述修复路径。

**Ledger 侧写入契约（F-D4）**：

- `Ledger` 不再逐条 `_append` 直写；改为 **store-first，memory-second**：
  1. 预检重复（`_seen` / `entry_id`）→ 重复直接返回 `False`，不触库；
  2. 在局部变量中计算新现金/持仓与分录（不修改 `self`）；
  3. 调用 `store.append_entries_with_events(entries, events)`（或 `append_entries`）；
  4. **事务成功后才**更新 `_entries` / `_positions` / `_cash` / `_reserved`；失败则内存完全不变并向上抛。
- `apply_fill(fill, *, ts=None, outbox_events: Sequence[OutboxEvent] = ()) -> bool`：fill/fee 两分录 + 事件一次提交；`fill.applied` 与 `order.status` 由 **gateway** 组装后传入（Ledger 不构造 payload，保持分层）。
- `apply_corporate_action` / `cash_adjust` 同样走 `append_entries`（可带事件）；`Ledger.resume` / `replay` 不变。
- 旧 `Ledger._append` 的「store 返回值被忽略」分叉（[ledger.py#L260-L263](../live/ledger.py#L260-L263)）在本批消除（I17）。

### 3.4 事件目录、`event_id` 与 payload

| event_type | event_id 模板 | 触发点 | payload 关键字段 |
|------------|---------------|--------|------------------|
| `order.accepted` | `order:{coid}:accepted:v1` | `submit()` 受理成功 | `coid, asset, side, quantity, price, order_type` |
| `order.rejected` | `order:{coid}:rejected:v{n}` | 本地校验/风控/柜台拒绝 | `coid, reject_code, reject_reason` |
| `order.canceled` | `order:{coid}:canceled:v{n}` | 撤单成功 | `coid, filled_quantity` |
| `order.cancel_rejected` | `order:{coid}:cancel_rejected:v{n}` | 撤单被预算/能力拒绝（G15） | `coid, reason, retry_after_ms` |
| `order.status` | `order:{coid}:status:{state}:v{n}` | 其余状态迁移 | `coid, status, filled_quantity, avg_price` |
| `fill.applied` | `fill:{fill_key}:v1` | `apply_fill` 入账 | `fill_key, coid, quantity, price, fee, entry_ids` |

**payload 规范**：

```json
{"schema":1,"event_id":"order:co_ab12:status:FILLED:v3","type":"order.status",
 "ts":1763712000.123,"coid":"co_ab12","broker_order_id":"...","asset":"600000.SH",
 "side":"BUY","status":"FILLED","filled_quantity":100.0,"avg_price":10.5,"reason":""}
```

- 序列化统一 `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`。
- `event_version` 递增保证「同 `event_id` ⇒ 同 payload」；`fill.applied` 用唯一 `fill_key`。
- 写入：`INSERT ... ON CONFLICT(event_id) DO NOTHING`，随后**读取既有行比对** `event_type` + `payload`；不一致抛 `OutboxEventConflict`（不得吞掉）。

### 3.5 Redis 键与 Stream 字段

| 键 | 类型 | 写入方 | 消费方 | 说明 |
|----|------|--------|--------|------|
| `p054:orders` | Stream | relay | 交易进程单消费者 | 订单/成交事件，`MAXLEN ~ 200000` |
| `p054:orders:events` | Pub/Sub | 交易进程消费者 | 全部 API/WS worker | 扇出帧 `{"seq":n,"event":{...}}` |
| `p054:market` | Pub/Sub | market_gateway | 全部 API/WS worker | tick 帧（可丢） |
| `p054:ticket:<token>` | String | API worker | 任意 worker | `EX 30`，`GETDEL` 单次 |
| `p054:trading:heartbeat` | String | heartbeat 线程（每 1s） | API worker（ready 检查） | `SET ... EX 10`；TTL 过期即判死 |
| `p054:consumer:heartbeat` | String | heartbeat 线程（每 2s，读 consumer 线程内存中的 PEL pending 数） | API worker（ready 检查） | `SET ... EX 10`；含 PEL pending 数（值 `"<ts>:<pending>"`） |
| `p054:admin` | Pub/Sub | 任一 API worker（admin 端点） | 全部 API/WS worker | `{"paused":bool}`：跨 worker 暂停/恢复行情推送（F-I9） |

Stream 条目字段：`event_id` / `seq` / `kind`（event_type）/ `payload`（canonical JSON） / `ts`。
消费组：`p054-relay`；消费者：`trading-1`；`XAUTOCLAIM` 空闲阈值 **60s**，每次最多 **50** 条。

### 3.6 WS 协议

**连接**：`GET /ws?ticket=<one-time>`（TLS 下 `wss`）。握手前校验 ticket；失败 → `403`（无 ticket / 已用）或 `401`（无效）。`accept()` 后立即开始。

**客户端 → 服务端**：

```json
{"type":"resume","last_seq":123}
{"type":"ping","ts":1763712000.0}
```

**服务端 → 客户端**：

```json
{"type":"snapshot","seq":123,"server_ts":...,"recovery_state":"complete","degraded":false,
 "orders":[...],"positions":[...],"account":{"cash":...,"reserved_cash":...,"equity_estimate":...,"as_of":...},
 "market":{"600000.SH":{"last":10.5,"ts":...,"tick_seq":88}}}
{"type":"delta","seq":124,"events":[{"seq":124,"type":"order.status","payload":{...}}]}
{"type":"market","tick_seq":89,"ticks":[{"symbol":"600000.SH","last":10.6,"ts":...}]}
{"type":"pong","ts":...}
{"type":"error","code":"not_ready|auth_failed|slow_consumer|queue_overflow|internal","message":"..."}
```

**语义**：

- `snapshot.seq` = 该快照**已包含**的最后事件序号（单读事务内 `MAX(outbox.seq)`），与 orders 状态严格一致。
- 连接建立顺序：**先注册连接（开始收 Pub/Sub）→ 再读快照 → 发 snapshot → 过滤队列中 `seq > S` 的 delta（按 seq 排序去重）→ 转 live**，消除快照与订阅之间的丢帧窗口。
- 每次连接**必发 snapshot**；`resume.last_seq` 仅回显为 `resumed_from`，若 `last_seq > snapshot.seq` 发 `error:stale_snapshot` 后关闭（客户端状态来自旧库/未来库）。
- 订单 delta 的 `seq` 严格单调递增；同一连接内重复 seq 由服务端去重；客户端发现缺口 → 主动重连取 snapshot。
- 行情帧 `tick_seq` 独立；允许缺口；客户端以最新值为准。
- 心跳：uvicorn 协议层 ping/pong（20s/20s）+ 应用层 `ping/pong`（服务端 15s 主动 ping，30s 无 pong 关闭）。
- 关闭码：`1013`（慢消费者/过载）、`1008`（鉴权/协议违规）、`1011`（内部错误）。

### 3.7 REST 端点（只读管理面 + 一个非交易写端点）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/health/live` | 无 | 进程存活，恒 200 |
| GET | `/health/ready` | 无 | Redis PING + `p054:trading:heartbeat` / `p054:consumer:heartbeat` 未过期 + `recovery_state ∈ {complete, degraded_positions}` + SQLite 可读；否则 503 + `reasons[]`（含 `db_uninitialized` / `stale_trading` / `stale_consumer` / `redis_down`） |
| GET | `/api/snapshot` | reader | 与 WS snapshot 同 DTO（HTTP 轮询回退） |
| GET | `/api/orders?status=&limit=&offset=` | reader | 只读；`load_orders()` 内存过滤（自用规模；>1 万单再引入 SQL 过滤），默认 `limit=100`，上限 500 |
| GET | `/api/orders/{coid}` | reader | 404 语义明确 |
| GET | `/api/positions` | reader | 来自 `LedgerSnapshot.positions` |
| GET | `/api/account` | reader | `cash/reserved_cash/equity_estimate/as_of`（成本口径，非市值） |
| GET | `/api/events?after_seq=&limit=` | reader | `outbox_after`，默认 100、上限 500 |
| POST | `/api/ws-ticket` | reader | 返回 `{"ticket":"...","expires_in":30}`；Redis `SET NX EX` |
| POST | `/api/admin/broadcast-pause` | **admin** | `{"paused":true|false}`；只影响行情推送，不触碰订单路径 |
| GET | `/metrics` | reader（可配关闭鉴权） | Prometheus 文本格式 |

**明确不存在**：`POST /orders`、`POST /orders/{id}/cancel`、`POST /kill`（I15）。
**错误映射**：401（缺失/错误 key）、403（角色不足）、404（资源不存在）、409（冲突）、422（参数）、429（认证失败限流）、503（未就绪）。

### 3.8 `ServiceSettings`（`services/config.py`）

```python
class ServiceSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    redis_url: str = "redis://127.0.0.1:6379/0"
    sqlite_path: Path
    api_key: SecretStr
    admin_api_key: SecretStr | None = None
    cors_origins: tuple[str, ...] = ()
    metrics_require_auth: bool = True

    ws_ticket_ttl_seconds: int = 30
    ws_orders_queue_max: int = 1000
    ws_market_queue_max: int = 200
    ws_slow_consumer_seconds: float = 5.0
    ws_snapshot_orders_limit: int = 200

    heartbeat_interval_seconds: float = 1.0
    heartbeat_ttl_seconds: int = 10
    ready_staleness_seconds: float = 3.0

    outbox_batch_size: int = 100
    outbox_poll_interval_seconds: float = 0.2
    outbox_retention_days: int = 7
    outbox_publish_timeout_seconds: float = 2.0

    orders_stream_key: str = "p054:orders"
    orders_channel: str = "p054:orders:events"
    market_channel: str = "p054:market"
    consumer_group: str = "p054-relay"
    consumer_name: str = "trading-1"
    autoclaim_idle_ms: int = 60_000

    market_source: Literal["synthetic", "none"] = "synthetic"
    market_tick_hz: float = 2.0
    market_symbols: tuple[str, ...] = ()

    tls_ciphers: str = "ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!RC4:!3DES"
    tls_certfile: Path | None = None
    tls_keyfile: Path | None = None
    tls_ca_certs: Path | None = None
    tls_require_client_cert: bool = False
    allow_plaintext_loopback: bool = False
```

**校验**（`model_validator`）：

1. `tls_certfile`/`tls_keyfile` 必须成对；未提供且 `allow_plaintext_loopback=False` → 报错（Q16）。
2. `allow_plaintext_loopback=True` 时绑定地址必须 `127.0.0.1`（由 `api_worker` 断言）。
3. `api_key` 长度 ≥16；`admin_api_key` 不得等于 `api_key`。
4. `ws_orders_queue_max >= 100`；`outbox_retention_days >= 1`。

---

## 4. 关键决策 D1-D19

| ID | 决策 | 依据 |
|----|------|------|
| **D1** | 拓扑 = **单实例交易/账本进程 + N 个无状态 API/WS worker**；进程角色由入口决定，不用 leader election | Q18 / §22.1（Helland 实体单所有者 + SQLite 单写者） |
| **D2** | 行情走 **Pub/Sub**（可丢）；订单/成交走 **outbox → Streams → 单消费者 → Pub/Sub**（不可丢） | §19.9 / F7 L223-232 |
| **D3** | 订单通道 `seq = outbox.seq`；快照水位与业务数据在**同一读事务**取 `MAX(seq)` | §16 + 组合写原子性（U-P053-17） |
| **D4** | store 采用**显式组合写 API**（方案 A），不引入 UoW/ORM；单写方法保留 | §4.3 |
| **D5** | 外发事件 **6 类**（§3.4）；`order.cancel_rejected` 用于 G15 可视化；对账只审计不入 outbox（F-I6） | Q1 / §17.3 |
| **D6** | `event_id` 版本化 + 冲突报错 + inbox 去重；`OrderRecord.event_version` 单调递增 | Q2/Q11 / §16.5 |
| **D7** | relay：批量 `pending_outbox(100)` → `XADD` → `mark_sent(seq)`；失败保留 `sent=0` 退避重试；已发送保留 7 天 | §4.5 / §16.6 |
| **D8** | 查询调度器：1/s 最小间隔、单在途、Full Jitter（1/2/5/5 次）、启动串行、巡检共用；降级语义按 Q6 | U-P053-18 / Q5-Q7 |
| **D9** | FTD 预算：`max_ftd_per_sec=6.0`、`ftd_reserve=1`（保留给 **cancel**）；顺序 FTD → 类型预算 → 发送 → `RateLedger.record`；**发送即计**（G13） | Q8 / §15.2 |
| **D10** | order-flow 预算：容量 `2 × internal`（默认 2/s），`reserve_cancel=1`（submit 不能用保留槽）；两类型桶各 1/s 保留；不设日上限 | Q9 / §17.4 |
| **D11** | `cancel_ex() -> CancelResult`；`cancel()` 委托保持 bool；所有撤单拒绝写 `AUDIT_CANCEL` + `order.cancel_rejected`；**`cancel_all() -> int` 保持 P-053 契约**，新增 `cancel_all_ex() -> CancelAllReport`（requested/submitted/deferred/rejected） | G15 / Q12；F-D3 修复 |
| **D12** | WS：每次连接发 snapshot + 之后 live delta；`seq` 严格单调、连接内去重；不做 delta-only 续传（偏差 §8-4） | §19.5 / F7 验收 |
| **D13** | 背压：订单队列满 → 等待 ≤5s → `error:slow_consumer` + `close(1013)`（绝不静默丢）；行情队列满 → 丢旧/按 symbol 合并 | §19.5 |
| **D14** | 鉴权：`X-API-Key` + `hmac.compare_digest`；WS 一次性 ticket（Redis `SET NX EX` + `GETDEL`）；认证失败 429 独立限流（不占用 FTD） | Q15 / §22.4 |
| **D15** | TLS 全启用；`allow_plaintext_loopback` 仅显式开启且绑 `127.0.0.1`；用 uvicorn `ssl_context_factory`（top-level、可 pickle）显式设 `minimum_version=TLSv1_2` + `maximum_version=MAXIMUM_SUPPORTED` + AEAD-only cipher，并做启动断言 | Q16 / §22.5；锚点见 [补充调研 §3](RESEARCH_p054_risk_anchors.md)（S68-S72） |
| **D16** | 可观测性：`prometheus-client` + 四黄金信号 + 领域指标；stdlib JSON 日志；`/metrics` 默认要求 reader key | Q17 / §22.6 |
| **D17** | 读路径：同机 `mode=ro` 只读 SQLite；跨机内部 API（本批只文档化）；**不建 Redis 读模型** | Q19 / §22.3 |
| **D18** | Redis：本地 Docker Desktop(WSL2) `redis:7`；CI Ubuntu `services: redis`；单测 `InMemoryBus`。Windows 本地无 Redis 时 `--bus fake` 仅用于开发/测试 | Q20 / §22.2 |
| **D19** | REST 管理面：只读端点 + 唯一写端点 `broadcast-pause`（admin）；不含下单/撤单/kill HTTP 路径 | F7 L232 / Q12 |
| **D20** | 进程内并发与连接模型：writer/reader 连接均 `check_same_thread=False` + 各自 RLock；交易进程用**同步** Redis 客户端、心跳走 Redis TTL 不落 SQLite；交易进程 = 主线程（gateway/poll/写）+ relay/consumer/heartbeat 三个守护线程 | F-D1/F-D2/F-I7 修复；§2.4 |

---

## 5. 阈值与默认值表

| 项 | 默认 | 来源 | 可配 |
|----|------|------|------|
| `internal_per_sec` / `internal_per_day` | 1 / 1000 | P-052 D2 | ✅ |
| `max_ftd_per_sec`（CTP） | 6.0 | S21/S16/S22 | ✅ |
| `ftd_reserve` | 1（保留给 cancel） | Q8/Q12 | ✅ |
| `order_flow_per_sec` | `2 × internal`（默认 2） | Q9/§17.4 | ✅ |
| `reserve_cancel`（order-flow） | 1 | Q12 | ✅ |
| 查询最小间隔 | `1 / query_per_sec`（CTP=1.0s） | S16/S17 | ✅ |
| 查询在途 | 1 | S16/S17 | ❌ |
| 退避 | 1.0s / ×2 / 封顶 5.0s / 5 次 / Full Jitter | Q5/§14.4 | ✅ |
| 巡检间隔 | 6s | S18 | ✅ |
| outbox 批量 / 轮询 | 100 / 0.2s | 工程默认 | ✅ |
| outbox 保留 | 7 天 | Q11 残留取舍 | ✅ |
| XAUTOCLAIM 空闲 / 批量 | 60s / 50 | 工程默认 | ✅ |
| WS 订单队列 / 行情队列 | 1000 / 200 | §19.5 | ✅ |
| 慢消费者阈值 | 5s | §19.5 | ✅ |
| 心跳 / ready 过期 | 1s 写 / Redis TTL 10s / ready 3s | 工程默认；F-D2 起不落 SQLite | ✅ |
| ticket TTL | 30s | Q15/§22.4 | ✅ |
| snapshot orders 上限 | 200（open + 最近终态） | 工程默认 | ✅ |
| API Key 最小长度 | 16 | 安全下限 | ✅ |
| 认证失败限流 | 10 次/分钟/IP（进程内） | 工程默认 | ✅ |
| TLS 最低/最高版本 | TLS1.2 / MAXIMUM_SUPPORTED（1.3 优先、1.2 兼容） | Q16/S59 + S68-S72 | ❌（策略常量） |
| TLS cipher 串 | `ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!RC4:!3DES`（纵深防御；协议级强制由 `minimum_version` 承担） | S70 | ✅ `tls_ciphers` |
| 事件 payload schema | 1 | 本设计 | ✅（升版需评审） |

---

## 6. 不变式 I1-I16

| ID | 不变式 | 验证方式 |
|----|--------|----------|
| I1 | 只有交易进程构造 writer store；第二实例在 `.lock` 处失败 | 两进程启动测试（沿用 P-053 I8） |
| I2 | API worker 不写 SQLite、不 append EventLog；store 为 `read_only=True` | 启动断言 + grep 守卫 |
| I3 | 所有「业务写 + 事件」必须走组合写 API；禁止 `upsert_order` 后再 `append_outbox` | grep 调用点 + 崩溃探针 |
| I4 | `outbox.seq` 单调递增、永不复用；relay 严格 `ORDER BY seq` | 迁移/重投/`EXPLAIN QUERY PLAN` 测试 |
| I5 | 同 `event_id` ⇒ 同 `event_type` + 同 payload；否则 `OutboxEventConflict` | 契约测试（同/异 payload 两例） |
| I6 | 投递语义为 at-least-once；不得对外宣称 exactly-once；消费端 inbox + 客户端按 `event_id` 去重 | 重投测试 + 文档措辞 |
| I7 | FTD/order-flow 均在**发送前** reserve；拒绝必须显式（异常/`CancelResult`/审计） | 打桩计数 + audit 断言 |
| I8 | 默认路径行为不变：默认 1/s 下 FTD 峰值 3、order-flow 峰值 2；同秒 1 报 + 1 撤允许 | 既有 1300 测试全绿 + 新边界用例 |
| I9 | 撤单拒绝必写 `AUDIT_CANCEL` 且带原因；`cancel_ex` 可区分 not_found/terminal/限流 | 单测 + audit 读取 |
| I10 | 查询串行（单在途）、相邻间隔 ≥ `1/query_per_sec`；`-2/-3` 重试 ≤5 次且不重复入账 | fake clock/注入适配器 |
| I11 | 同一 WS 连接内订单 `seq` 严格单调；缺口由客户端重连取 snapshot；服务端不得发乱序帧 | 协议测试 |
| I12 | 订单事件永不静默丢弃；行情 tick 可丢（指标计数） | 慢客户端测试 + 指标断言 |
| I13 | 密钥/口令/ticket 不进入日志与错误响应；比较用 `hmac.compare_digest` | grep + 日志采样 |
| I14 | TLS 仅 1.3/1.2；明文仅 `allow_plaintext_loopback` 且 `127.0.0.1` | factory 断言 `minimum_version==TLSv1_2` + `get_ciphers()` 协议集合 ⊆ {TLSv1.2, TLSv1.3} + `pickle.dumps(factory)` + 可选 TLS1.1 拒绝握手 |
| I15 | REST 无下单/撤单/kill 路由；唯一写端点为 `broadcast-pause` | 路由清单测试 |
| I16 | `live/*` 不 import `services/*`；`services/contracts.py` 不 import redis/fastapi | grep 守卫 |
| I17 | Ledger 写入 store-first：store 事务失败或重复时，内存 `entries/positions/cash/reserved` 不变 | 故障注入 + 重复 fill 测试 |

---

## 7. 测试策略与用例映射（120 例 / 10 文件）

| 文件 | 例数 | 覆盖 |
|------|------|------|
| `tests/test_p054_ledger_store_atomic.py` | 16 | 组合写单事务、崩溃点探针（业务写后崩溃 outbox 同生同灭）、`apply_fill` 两分录同事务 + **Ledger store-first 回滚**、批量分录幂等、只读模式跳过 `.lock` + **只读 preflight（`journal_mode=='wal'`/四类 reason）**、`snapshot` 水位一致 |
| `tests/test_p054_outbox_migration.py` | 12 | 旧表→v2 迁移顺序保持、`seq` 不复用、`(sent,seq)` 索引命中、冲突报错、同 payload 静默幂等、inbox 去重、`meta` 读写、purge 不删最大 seq |
| `tests/test_p054_event_emission.py` | 10 | **6 类**事件触发点齐全、`event_id` 模板（accepted 固定 v1）、`event_version` 递增、payload canonical、拒绝/撤单事件、对账仅 audit、`OrderRecord` 旧 payload 反序列化 |
| `tests/test_p054_flow_control.py` | 16 | FTD 6/s 第 7 笔、发送即计（拒单也消耗）、order-flow 同秒 1报+1撤允许、第 3 笔拒绝、`reserve_cancel` 槽位、退还仅本地未发出、`rate_denied_total` 原因、能力声明一致 |
| `tests/test_p054_query_scheduler.py` | 12 | 最小间隔、单在途串行、Full Jitter 边界（0..high）、封顶 5s、5 次上限、启动 3 查询不抛、`-2/-3` 退避、trades/orders fail-closed、positions 降级、巡检共用、fake clock |
| `tests/test_p054_api_auth.py` | 12 | 401/403 三角色、`hmac.compare_digest` 调用、ticket 单次使用/过期、429 认证限流、路由清单无下单/撤单、CORS 白名单、**TLS factory（`minimum_version`/`get_ciphers()`/pickle）**、明文仅 loopback |
| `tests/test_p054_ws_protocol.py` | 16 | snapshot/delta 帧、seq 单调/去重、snapshot 水位一致、注册-快照-队列过滤无丢帧、慢消费者 1013、行情丢旧/合并、心跳、resume 语义、未就绪拒绝、错误码 |
| `tests/test_p054_relay_consumer.py` | 12 | relay 顺序、XADD 成功才 `mark_sent`、崩溃重投、消费幂等（inbox）、XACK/XAUTOCLAIM、Pub/Sub 扇出全 worker、Redis 故障退避、`outbox_pending` 指标 |
| `tests/test_p054_health_metrics.py` | 8 | live/ready 分支、**Redis 心跳 TTL 过期 503**、consumer 心跳、recovery 状态、四黄金信号存在、领域指标、`/metrics` 鉴权、JSON 日志字段 |
| `tests/test_p054_end_to_end.py` | 6 | FakeBus 单进程全链（submit→outbox→stream→pubsub→WS）、快照+delta 重放等价、双 worker 广播一致、断线重连、未就绪路径、延迟分段采样 |

**门禁目标**（Step 9 实测写入 CHECKLIST，不预填）：

| 指标 | 基线 | 目标 |
|------|------|------|
| pytest | 1300 | **1420**（+120） |
| `-k golden` | 22 | **22 不变**（零重录） |
| mypy | 141 files 0 | **157**（+16：`live` +3、`services` +12、`scripts` +1） |
| black | 283 | **309**（+26：3 live + 12 services + 10 tests + 1 script） |
| `tests/*.py` | 141 | **151**（+10） |
| `core/*.py` | 51 | **51 不变** |
| `live/*.py` | 16 | **19**（+3） |
| `services/*.py` | 0 | **12** |

---

## 8. 与总纲 / RESEARCH 的偏差

| # | 偏差 | 说明 | 处理 |
|---|------|------|------|
| 1 | 总纲 F7「行情网关 → **Redis Streams** → 快照聚合」改为行情走 **Pub/Sub** | 行情可丢、可合并；Pub/Sub at-most-once 与语义匹配，Streams 用于不可丢的订单/成交（RESEARCH §19.9 已论证并裁决） | 登记；F7 验收项不依赖行情持久化 |
| 2 | F7「uvicorn(uvloop)」在 Windows 不可达 | uvloop 不支持 Windows/PyPy → Windows=asyncio，Linux 可选 uvloop | 登记（§19.4） |
| 3 | F7「REST 管理面**可写**」收窄为唯一写端点 `broadcast-pause` | F7 同时要求「不含下单/撤单交易逻辑」；kill-switch 属撤单语义，不经 HTTP 暴露 | 登记（D19/I15） |
| 4 | RESEARCH §19.5「重连可只补 delta」改为**一律 snapshot** | 账本存在非事件化变更（分红/送转/现金调整），delta-only 续传可能漏状态；一律 snapshot 正确性优先 | 登记（D12）；`/api/events` 仍提供排查用回放 |
| 5 | `pending_outbox`/`mark_sent`/`append_outbox` 签名变更 | Q11 要求 `seq`；旧签名无法表达顺序 | 批内同步改 gateway/测试；Protocol 其余方法只增不改 |
| 6 | `OrderRecord` 追加 `event_version` 字段 | 提供稳定 `v<n>`，避免时间戳/随机 UUID 作版本 | 默认值 0，旧 payload 兼容；`transition()` 递增 |
| 7 | `cancel()` 保持 bool 但新增 `cancel_ex()` | 兼顾 P-053 已关闭契约与 G15 显式化 | D11 |
| 8 | Q10 未改造 `check_rate` | 用户裁决；`FtdBudget` 先落地 `Decision` 形状 | 触发条件见 RESEARCH §15.4 |
| 9 | Python 3.11 为**前置批次 B0**，不混入功能批 | Q13 要求「单列小任务，不得在 Step 3 静默改」 | §10.2 |
| 10 | `mode=ro` 读 WAL 需 `-shm`/`-wal` 可访问 | **已取证**：S62 只读三条件 + §2.2 同机约束；S63 `immutable` 禁令（[补充调研 §2](RESEARCH_p054_risk_anchors.md)） | 部署前提 + 启动 preflight；失败走 Plan B 内部 API |

---

## 9. 风险与未决

| ID | 风险 / 未决 | 影响 | 处置 |
|----|-------------|------|------|
| R1 | 只读 WAL 连接需 `-shm`/`-wal` 可访问（同机、同用户、目录可写） | 不同用户/只读挂载下 API worker 无法打开只读库 | **已缓解**：S62 三条件已取证；启动 preflight（`journal_mode=='wal'` + 一次 `MAX(seq)` 读）按 `StoreReadOnlyError.reason` 四分类给出修复路径；失败走 Plan B 内部 API（[补充调研 §2](RESEARCH_p054_risk_anchors.md)） |
| R2 | ~~uvicorn 不暴露 `ssl.minimum_version`~~ → **已关闭** | 无（不再依赖 cipher 间接排除） | uvicorn 0.54.0 `ssl_context_factory`（S68）+ 显式 `minimum_version=TLSv1_2`（S70）+ 启动断言；Python 3.11 默认 TLS1.2 为第二层（S72）（[补充调研 §3](RESEARCH_p054_risk_anchors.md)） |
| R3 | FastAPI 0.165 传递依赖含 `opentelemetry-api` | 安装面增大 | 接受（§19.2 已记录）；不启用 OTel |
| R4 | Windows 本地无官方 Redis | 开发/演示不可跑 | Docker Desktop(WSL2) `redis:7`；`InMemoryBus` 仅测试/单进程开发 |
| R5 | 交易进程是单点：重启期间 API 503、WS 断开 | 可用性 | `/health/ready` 反映；客户端重连；自用工具可接受（§20.4） |
| R6 | outbox 保留 7 天，超期无法增量排查 | 仅影响 `/api/events` | 文档写明；WS 不依赖该回放 |
| R7 | 多 worker 下 ticket/心跳依赖 Redis | Redis 故障时 WS 全断 | 显式降级（ready 503）；不做本地兜底冒充 |
| R8 | 延迟基准含客户端时钟 | 绝对值可能偏差 | 三段分段测量（append→入队、入队→发送、端到端），报告标注口径 |
| R9 | `EventLog` JSONL 随运行增长 | 磁盘 | 沿用既有 buffer 500 + 磁盘；P-054 不新增轮转（登记为后续运维项） |

---

## 10. 出口条件

### 10.1 Step 4/5/7/9/10 对齐

- **Step 4（设计复审）**：0 P1；P2/P3 全部修复或登记后回写本文件。
- **Step 5（IMPL）**：本文件 D1-D20 / I1-I17 / §3 契约逐条映射到文件与函数；B0-B6 顺序与依赖明确。
- **Step 7（CHECKLIST）**：§7 的 120 例 + §5 阈值 + I1-I17 全部落成可核对断言；门禁目标不预填实测值。
- **Step 9（落码）**：pytest 1420 / golden 22 零重录 / mypy 157·0 / black 309 / 文件计数 151·51·19·12；`uv lock --check` 通过。
- **Step 10（验收）**：F7 四项验收 + 延迟基准报告 + 异构复审 0 P1。

### 10.2 实施批次（Step 5 排期）

| 批次 | 内容 | 依赖 | 退出条件 |
|------|------|------|----------|
| **B0** | Python 3.11 基线：`requires-python`、classifiers、black/mypy 目标、CI 3.11/3.12、`pydantic>=2.9.0`、`[services]` extra | 无 | 1300 测试在 3.11/3.12 全绿；`uv lock --check` 通过；确认 `PROTOCOL_TLS_SERVER` 默认最低 TLS1.2（S72） |
| **B1** | store v2：组合写、outbox 迁移、inbox、meta、只读模式 + **preflight** | B0 | I3/I4/I5 + 28 例（atomic 16 + migration 12） |
| **B2** | 流控前置包：`flow_control`、`query_scheduler`、gateway 接线、`cancel_ex`、CTP 能力声明 | B0 | I7-I10 + 28 例（flow 16 + scheduler 12） |
| **B3** | 事件发射：`live/events.py`、**6 类**事件、`event_version`、gateway 全面改组合写、**Ledger store-first（I17）** | B1 | I3/I5/I17 + 10 例（I17 故障注入在 atomic 16 内） |
| **B4** | 服务层骨架：contracts/bus/config/auth/metrics/api（REST/health/ticket/**TLS factory**）+ TicketStore + FakeBus | B1、B3 | I2/I13-I16 + 20 例（api 12 + health 8） |
| **B5** | 运行时：ws_hub、market_gateway（独立入口/`--embedded`）、relay、consumer、trading_worker、api_worker、**D20 并发/心跳** | B4 | I6/I11/I12 + D20 + 28 例（ws 16 + relay 12） |
| **B6** | 端到端 + 延迟基准 + 文档/台账（含可选 TLS1.1 拒绝握手、只读 preflight 集成复核） | B5 | 6 例 + 基准报告 + 四文档一致 |

---

## 11. 状态链

**Step 3 DESIGN 完成（2026-11-22）**：本文档产出（D1-D19 / I1-I16 / §3 数据契约 / §5 阈值 / §7 120 例映射 / §8 十项偏差 / §10 B0-B6）→ 待 Step 4 异构复审（reviewer ≠ author）→ Step 5 IMPL。

**R1/R2 补充调研完成（2026-11-22）**：[RESEARCH_p054_risk_anchors.md](RESEARCH_p054_risk_anchors.md)——R1 以 SQLite 官方 WAL 只读三条件（S62）+ `immutable` 禁令（S63）+ 同机共享内存约束（S62 §2.2）定案「前提 + preflight + Plan B」；R2 以 uvicorn **0.54.0** `ssl_context_factory`（S68）+ 官方 `minimum_version` 示例（S70）+ Python 3.10+ 默认 TLS1.2（S72）定案「factory + 显式 TLS1.2 + 启动断言」，**R2 关闭**；回写 §3.8/§4 D15/§5/§6 I14/§8 #10/§9 R1-R2/§10.2，测试仍 120 例（preflight 与 TLS factory 计入既有 `ledger_store_atomic`/`api_auth` 覆盖项）。

**Step 4 设计复审修复完成（2026-11-22）**：F-D1/F-D2 → 新增 §2.4 进程内并发与连接模型（writer/reader `check_same_thread=False` + 各自 RLock；心跳改 Redis TTL 不落 SQLite；交易进程 = 主线程 + relay/consumer/heartbeat 三守护线程）+ **D20**；F-D3 → D11 保留 `cancel_all() -> int`、新增 `cancel_all_ex() -> CancelAllReport`（§0.3/I8 不变，无新增偏差）；F-D4 → §3.3 新增「Ledger 侧写入契约」（store-first/memory-second、`apply_fill(..., outbox_events=...)`）+ **I17**；F-D5 → mypy 目标 157（含 scripts）、§10.1 与 §7 同步；F-D6 → market_gateway 独立入口/`--embedded`；F-D7 → `TicketStore` Protocol + InMemory 实现；F-D8 → `/api/orders` 内存过滤口径；F-D9 → `StoreReadOnlyError.reason` 四分类；F-D10 → S62-S72 编号唯一归属 risk_anchors §5。→ **Step 4 关闭**，进入 Step 5 IMPL。

**Step 6 IMPL 复审修复回写（2026-11-22）**：F-I1 → `_seen` canonical 化（`fill:{fill_key}`，与 resume 的 entry_id 对齐，IMPL C-13）；F-I2 → accepted 事件固定 v1（builder 显式版本，C-12）；F-I3 → 事件类型按阶段映射（fill 只发 `fill.applied`；撤单成功 `order.status(PENDING_CANCEL)`，CANCELED 仅在回报，C-14）；F-I4 → 预算移到 `pre_trade_check` 之后（C-9）；F-I5 → 迁移三分支（全新库/v1/v2，C-2）；F-I6 → **`reconcile.completed` 移出 outbox（事件集 6 类，Q1/D5/§3.4 同步）**；F-I7 → 交易进程改用 `SyncRedisBus`（§2.4/D20）；F-I8 → CI 安装 `.[dev,services]`；F-I9 → 新增 `p054:admin` 频道（§3.5/§3.16/§3.18）；O-I1~O-I5 已顺手。→ 待 Step 6 复核关闭。
