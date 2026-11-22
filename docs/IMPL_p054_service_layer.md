# IMPL：P-054 服务层（store v2 / 通道流控前置包 / 事件外发 / FastAPI+WS 多 worker / Python 3.11 基线）

> **批次**: P-054 · **Step 5 实施方案** · 日期 2026-11-22 · **判档 T1（全量）**
> **上游**: [DESIGN_p054](DESIGN_p054_service_layer.md)（D1-D20 / I1-I17 / §3 契约 / §7 120 例 / B0-B6）；[REVIEW_p054_step4](REVIEW_p054_step4_design.md)（首轮 0 P1/4 P2/6 P3 → §8 修复 → §9 二轮 10/10 通过）；[RESEARCH_p054_risk_anchors](RESEARCH_p054_risk_anchors.md)（R1/R2 锚点 S62-S72）
> **口径**: Q8/Q9/Q11/Q12/Q13/Q14/Q15-Q20 为用户裁决；本文件只做「落到文件与函数」的实施映射，不重开设计
> **零代码/零门禁变更**：Step 5 交付实施方案；Step 9 才落码（B0-B6 按 §6 顺序）

---

## 1. 变更总览

| # | 文件 | 类型 | 批次 | 关键内容 | 关联 D / I |
|---|------|------|------|----------|-----------|
| 1 | `pyproject.toml` | 改造 | B0 | `requires-python>=3.11`、classifiers、black target、mypy 版本、`pydantic>=2.9.0`、`[services]` extra | Q13 |
| 2 | `.github/workflows/tests.yml` | 改造 | B0 | CI 矩阵 3.11/3.12、mypy 路径加 `services` | Q13、I16 |
| 3 | `uv.lock` | 重生成 | B0 | `uv lock`；`uv lock --check` 通过 | Q13 |
| 4 | `live/events.py` | **新建** | B3 | **6 类**事件常量、`OutboxEvent` 构造器、canonical JSON、`event_version` 规则 | D5/D6、I5 |
| 5 | `live/flow_control.py` | **新建** | B2 | `Decision`、`FtdBudget`、`OrderFlowBudget`、`CancelResult`/`CancelAllReport` | D9/D10/D11、I7/I9 |
| 6 | `live/query_scheduler.py` | **新建** | B2 | `BackoffPolicy`、`QueryScheduler`（最小间隔/单在途/全抖动/巡检） | D8、I10 |
| 7 | `live/channel.py` | 改造 | B2 | `ChannelCapability` 追加 `max_ftd_per_sec=6.0`、`ftd_reserve=1`、`startup_ftd_instructions=2` | D9、C-11 |
| 8 | `live/adapters/ctp.py` | 改造 | B2 | 能力声明补 FTD 三字段；`max_submit/cancel_per_sec` 注释改为「受 FTD 共享约束」 | D9 |
| 9 | `live/orders.py` | 改造 | B3 | `OrderRecord.event_version: int = 0`；`transition()` 递增 | D6、I5 |
| 10 | `live/ledger.py` | 改造 | B3 | `apply_fill(..., outbox_events=())`、`apply_corporate_action`/`cash_adjust` 改 store-first、删除 `_append` 直写 | D4、I3/I17 |
| 11 | `live/ledger_store.py` | 改造 | B1 | schema v2 + 迁移、组合写 8 组方法、inbox/meta、只读 preflight、双锁 | D3/D4/D5/D6/D7、I2-I5/I17 |
| 12 | `live/gateway.py` | 改造 | B2/B3 | 预算接线、`cancel_ex`/`cancel_all_ex`、事件发射、恢复序走 scheduler | D8-D11、G15 |
| 13 | `services/__init__.py` | **新建** | B4 | 包标记 | — |
| 14 | `services/contracts.py` | **新建** | B4 | `EventPublisher`/`OrderStream`/`TicketStore` Protocol、`StreamMessage`、DTO、错误码 | D14、I16 |
| 15 | `services/config.py` | **新建** | B4 | `ServiceSettings` + `from_env` + validators | D14/D15 |
| 16 | `services/bus.py` | **新建** | B4 | `RedisBus`（Pub/Sub+Streams）、`InMemoryBus`（FakeBus） | D2/D18、I6 |
| 17 | `services/auth.py` | **新建** | B4 | API Key（constant-time）、角色、Redis/InMemory ticket、认证限流 | D14、I13 |
| 18 | `services/metrics.py` | **新建** | B4 | registry、指标、多 worker 聚合 | D16、C-19 |
| 19 | `services/api.py` | **新建** | B4 | app factory：11 端点、依赖、异常映射、CORS、ready | D19、I2/I15 |
| 20 | `services/api_worker.py` | **新建** | B4 | uvicorn 入口、TLS factory、workers | D15、I14 |
| 21 | `services/ws_hub.py` | **新建** | B5 | hub、每连接队列、snapshot+delta、心跳/慢客户端 | D12/D13、I11/I12 |
| 22 | `services/market_gateway.py` | **新建** | B5 | `MarketDataSource` + synthetic + 独立/内嵌入口（§3.19） | D2 |
| 23 | `services/outbox_relay.py` | **新建** | B5 | relay 循环、退避、purge | D7、I4/I6 |
| 24 | `services/trading_worker.py` | **新建** | B5 | 装配、consumer、heartbeat、信号退出 | D1/D20、I1/I2 |
| 25 | `scripts/p054_bench_ws.py` | **新建** | B6 | 三段延迟基准 | F7 验收 |
| 26 | `tests/test_p054_*.py` | **新建 10 文件** | B1-B6 | 120 例（§4） | I1-I17 |

**文件计数目标**：`live/*.py` 16→**19**、`services/*.py` 0→**12**、`tests/*.py` 141→**151**、`core/*.py` 51 不变。

---

## 2. IMPL 澄清（伪码 → 可执行语义，Step 6 逐条复核）

### C-1 Python 3.11 与 `[services]` extra

- `pyproject.toml`：`requires-python = ">=3.11"`；classifiers 删 `3.10`（保留 3.11/3.12，可加 3.13）；`[tool.black] target-version = ["py311","py312"]`；mypy 若显式 `python_version` 则设 `3.11`（当前无该键，新增）。
- `pydantic>=2.0.0` → `pydantic>=2.9.0`（FastAPI 0.165 上游要求；`core/config_v2.py` 已实际使用，回归含 config 测试）。
- 新增 extra：
  ```toml
  services = [
      "fastapi>=0.165.0,<1.0",
      "uvicorn>=0.54.0",
      "websockets>=12",
      "prometheus-client>=0.26.0",
  ]
  ```
- `tests.yml`：矩阵 `["3.11","3.12"]`；安装改 `pip install ".[dev,services]"`（**F-I8**：否则 services 测试与 mypy 缺依赖）；mypy 命令末尾追加 `services`；新增 `PROMETHEUS_MULTIPROC_DIR` 仅用于 services 测试（可选，见 C-19）。
- B0 退出前必须 `uv lock` 重生成并 `uv lock --check`；全量 1300 测试在 3.11/3.12 各跑一次。

### C-2 outbox v2 迁移（幂等、单事务、顺序保持）

```python
def _migrate(self) -> None:
    tables = {r[0] for r in self._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "outbox" not in tables:                     # ① 全新库
        self._conn.executescript(_SCHEMA_V2)
        self._conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','2')")
        return
    cols = {row[1] for row in self._conn.execute("PRAGMA table_info(outbox)")}
    version = self._get_meta_raw("schema_version")  # ② v1 库 meta 表可能不存在 → 返回 None
    if "seq" in cols and version == "2":            # ③ 已迁移
        return
    with self.transaction():  # BEGIN IMMEDIATE
        self._conn.execute("ALTER TABLE outbox RENAME TO outbox_v1")
        self._conn.executescript(_SCHEMA_V2)  # outbox/inbox/meta + 索引（IF NOT EXISTS）
        self._conn.execute(
            "INSERT INTO outbox(event_id,aggregate_type,aggregate_id,event_type,"
            "payload,created_ts,sent,sent_ts) "
            "SELECT event_id,'legacy',event_id,event_type,payload,created_ts,sent,NULL "
            "FROM outbox_v1 ORDER BY rowid"
        )
        self._conn.execute("DROP TABLE outbox_v1")
        self._conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','2')")
```

- **三分支（F-I5 修复）**：① 无 `outbox` 表（全新库）→ 直接建 v2；② v1 库（有表无 `seq` / 版本≠2）→ 迁移；③ 已是 v2 → 跳过。`_get_meta_raw` 在 ② 前先判 `meta` 表是否存在，不存在返回 `None`。
- 迁移在 `__init__` 中、`.lock` 之后、任何读写之前；只读模式**不迁移**（缺表 → `uninitialized`）。
- 幂等：重复 `__init__` 不重复迁移。

### C-3 组合写在事务内的顺序与冲突回滚

- `upsert_order_with_events(record, events)`：`BEGIN` → upsert 订单 → 逐条 `INSERT ... ON CONFLICT(event_id) DO NOTHING` → 对每条**读回**既有行比对 `event_type` + `payload`；不一致 → 抛 `OutboxEventConflict`（事务回滚，业务行也不落）。
- `append_entries_with_events(entries, events)`：同一事务；先写分录、再写事件；冲突同样整体回滚。
- `append_entries(entries)`：仅分录（用于无事件的 `apply_corporate_action` 等）。
- `append_outbox(events)`：单事务，仅事件；冲突比对同上。
- **调用方契约**：`OutboxEventConflict` 视为程序错误（同 `event_id` 必同 payload），不捕获、不降级；`IntegrityError`（分录重复）由组合方法转成返回计数/`False`，不抛。

### C-4 `mark_sent` / inbox 幂等与 at-least-once 窗口

- `mark_sent(seq, ts)`：`UPDATE outbox SET sent=1, sent_ts=? WHERE seq=? AND sent=0`；重复调用无副作用。
- consumer 顺序：`XREADGROUP` → `inbox_has(event_id)`? 跳过并 XACK : `PUBLISH` → `mark_inbox` → `XACK`。
- 窗口：PUBLISH 成功、`mark_inbox` 前崩溃 → 重投后重复 PUBLISH（客户端按 `event_id` 去重，接受）；`mark_inbox` 后、XACK 前崩溃 → 重投后 `inbox_has=true` → 直接 XACK（不重发）。
- `inbox` 只增不删；保留期与 outbox 一致（7 天 purge 时同步清 `processed_ts < before_ts`，**可选**，默认不清以保幂等）。

### C-5 锁模型与连接参数

| 角色 | 连接参数 | 锁 |
|------|----------|-----|
| writer（交易进程） | `check_same_thread=False`、`isolation_level=None`、WAL、`synchronous=FULL`、`timeout=5.0` | `threading.RLock`（`_write_lock`）包住 `transaction()` |
| reader（API worker） | URI `file:...?mode=ro`、`check_same_thread=False`、`PRAGMA query_only=ON` | `threading.RLock`（`_read_lock`）包住所有读方法 |

- `transaction()` 外层加 `with self._write_lock:`；`snapshot()`/`entries()`/`load_orders()`/`outbox_after()` 等读方法在 reader 上加 `_read_lock`。
- 单写者 `.lock` 行为不变（writer 才抢锁）。

### C-6 只读 preflight 与 reason 分类

```python
def assert_readonly_ready(store) -> None:
    try:
        mode = store.conn.execute("PRAGMA journal_mode").fetchone()[0]
    except sqlite3.OperationalError as e:
        raise StoreReadOnlyError(classify(e), str(e)) from e
    if str(mode).lower() != "wal":
        raise StoreReadOnlyError("not_wal", f"journal_mode={mode!r}")
    try:
        store.conn.execute("SELECT COALESCE(MAX(seq),0) FROM outbox").fetchone()
    except sqlite3.OperationalError as e:
        raise StoreReadOnlyError("uninitialized", str(e)) from e
```

`classify`：`"unable to open database file"` → `permission`；`"no such table"` → `uninitialized`；其余 → `permission`（保守）。`internal_api_required` 仅由显式配置产生（本批不实现，占位）。

### C-7 FTD 预算（整秒窗 + 保留）

```python
class FtdBudget:
    def __init__(self, max_per_sec: float = 6.0, reserve: int = 1, clock=time.monotonic)
    def reserve(self, kind: str) -> Decision   # kind: "submit"|"cancel"|"query"|"startup"
    def release(self, kind: str) -> None       # 仅本地未发出时调用
    def remaining(self) -> int
```

- 窗口键 `int(clock())`（与 CTP 自然秒同构，Q10 不升级）。
- `capacity = max(1, int(max_per_sec))`；`reserve` 槽位仅 `kind == "cancel"` 可用；`submit/query/startup` 可用上限 `capacity - reserve`。
- 拒绝 → `Decision(False, retry_after_ms=至下一整秒, reason="ftd")`；`ftd_remaining` 指标与 ready 暴露。
- **发送即计**：adapter 调用前 reserve；调用后无论成功/拒单/超时都不退还（G13）。

### C-8 order-flow 预算

- `capacity = max(1, floor(2 × internal_per_second))`（默认 2）；`reserve_cancel = 1`。
- `submit` 可用 `capacity - reserve_cancel`；`cancel` 可用 `capacity`（仍受自身类型桶 1/s）。
- 拒绝 → `Decision(False, retry_after_ms=至下一整秒, reason="order_flow")`。
- 不设日上限；`_submit_ledger`/`_cancel_ledger` 保留（统计口径不变）。

### C-9 发送前 reserve 与「本地未发出」退还边界

- **预算位置（F-I4 修复）**：`ftd.reserve` / `order_flow.reserve` 放在**全部本地校验之后、`adapter.submit` 之前**（即 `pre_trade_check` 之后）——仍满足 D9「发送前 reserve」，且本地拒绝（含风控拒绝）不再空耗当秒槽位。
- **不退还**（已发给适配器）：`ChannelRejected`、`ChannelUnavailable`、超时、返回未知。
- **退还**（确定未发出）：`reserve` 之后、`adapter.submit` 之前抛出的异常（如请求构造失败）；`CapabilityError`/参数校验/`require_capability`/`pre_trade_check` 拒绝均发生在 reserve 之前，**不涉及退还**。

### C-10 QueryScheduler

```python
@dataclass(frozen=True)
class BackoffPolicy:
    initial: float = 1.0; multiplier: float = 2.0; cap: float = 5.0; max_attempts: int = 5
    def delay(self, attempt: int, rng: random.Random) -> float:
        high = min(self.initial * self.multiplier ** (attempt - 1), self.cap)
        return rng.uniform(0.0, high)  # Full Jitter

class QueryScheduler:
    def __init__(self, min_interval: float, *, clock=time.monotonic, sleep=time.sleep,
                 rng=random.Random(0), backoff=BackoffPolicy())
    def run(self, fn: Callable[[], T]) -> T
```

- `run`：`_lock` 串行（单在途）→ 等到 `last + min_interval` → `fn()`；捕 `ChannelUnavailable` → 按 `backoff.delay` sleep 重试；`max_attempts` 后原样抛出。
- 首次尝试计 `attempt=1`；`attempt` 只影响延迟，不改变 `fn` 语义。
- 巡检入口 `run_patrol(fn)` 同 `run`（同一 `last`，共用 1/s 桶），默认 6s 调度由 `trading_worker` 主循环控制。

### C-11 启动恢复与 FTD 外部占用

- `gateway.start()`：`connect()` 内登录/结算确认由适配器发送，**不经 gateway 预算**；`ChannelCapability.startup_ftd_instructions=2` 表示已知占用，`start()` 首秒调用 `ftd.reserve("startup")` × N（best-effort，记录后不退还）。
- 恢复序：`scheduler.run(lambda: self._adapter.query_trades(day))` → `scheduler.run(query_orders)` → `reconcile()` 内部 `scheduler.run(query_positions)`。
- `recovery_state`：trades/orders 失败 → `failed` 并抛；positions 失败 → `degraded_positions` 并继续。
- `_throttle_query` 保留（查询类型桶 1/s），由 `scheduler.run` 内部调用：`run(lambda: (self._throttle_query(now), adapter.query_xxx())[1])`。

### C-12 事件构造与 `event_version` 递增点

- `live/events.py` 提供：
  ```python
def order_event(rec: OrderRecord, event: str, *, ts: float,
                version: int | None = None, **extra) -> OutboxEvent
def fill_event(fill: FillRecord, *, entry_ids: Sequence[str], ts: float, coid: str) -> OutboxEvent
```
- `event_id`：`order:{coid}:{event}:v{n}`；`fill:{fill_key}:v1`。
- **accepted 固定 v1（F-I2 修复）**：`order_event(rec, "accepted", version=1)` 由 builder **显式传版本**，不使用 `rec.event_version`；其余事件用 `rec.event_version`（随真实迁移递增；事件名不同，与固定 v1 无冲突）。`from_request` 保持默认 0，不再做 `replace(event_version=1)`。
- `transition()` 只在**真实状态迁移**时 `event_version + 1`；同态幂等分支返回原对象（版本不变），且 gateway **不写库、不发事件**（O-I2）。
- **移除 `reconcile.completed` 出 outbox（F-I6 修复）**：对账结果只写 `AUDIT_RECONCILE` 审计，不入 outbox——避免「attempt 进程内计数重启归零 → 同 event_id 不同 payload → `OutboxEventConflict`」；F7 验收只要求订单/成交事件。§3.4 事件集由 7 类降为 **6 类**。

### C-13 Ledger store-first 改造

- 删除 `_append`，新增 `_commit(entries, events, mutate: Callable[[], None]) -> bool`：
  1. 重复预检在方法入口：**统一用 canonical entry_id**——`fill:{fill_key}` / `fee:{fill_key}` / `ca:{action_id}:{asset}`（**F-I1 修复**：不再使用裸 `fill_key`；`resume` 的 `_seen` 本就存 entry_id，重启后回放同一成交必然命中 → 返回 False，现金/持仓不变）；
  2. 计算局部新状态（不改 `self`）；
  3. `store.append_entries_with_events(...)`（或 `append_entries`）；
  4. 成功后执行 `mutate()` 更新 **`_entries` / `_positions` / `_cash` / `_reserves` / `_seen`**（O-I1：`_seen` 必须在提交成功后加；否则失败重试会被误判重复而丢成交）；
  5. 失败内存不变、异常上抛。
- `apply_fill(fill, *, ts=None, outbox_events=())`：保留 `-> bool`；重复返回 False。
- `resume()` **不改**（`_seen = {entry_id}` 已是 canonical）；回归用例：`resume(entries)` 后重放同一 `fill_key` → `False` 且 `cash/positions` 不变（F-I1）。
- `apply_corporate_action` / `cash_adjust`：改 `append_entries`（可带事件）；返回类型不变。
- `reserve/release/settle_reserve` 只改内存、不触 store（二轮复审已核验），**不改**。
- `Ledger.attach_store` 仍允许 `None`（测试内存模式）。

### C-14 Gateway 组合写替换点（共 5 处）

| 位置 | 现状 | 改为 |
|------|------|------|
| `submit` 成功 ⑧ | `upsert_order` + `append_outbox(uuid)` | `upsert_order_with_events(rec, [order_event(rec,"accepted",version=1)])` |
| `_apply_order_report` | `upsert_order`（无事件） | `upsert_order_with_events(rec, [event_by_state])`；`event_by_state`：REJECTED→`order.rejected`、CANCELED→`order.canceled`、其余→`order.status`；**同态分支（updated is rec）不写库不发事件**（O-I2） |
| `poll` 成交 | `apply_fill`（无事件） | `apply_fill(..., outbox_events=[fill.applied])`——**只发 fill 事件**：poll 不更新订单记录，不得声称订单状态（F-I3） |
| `ingest_fills` | 同上 | 同上 |
| `cancel` 成功 | `upsert_order` + audit | `upsert_order_with_events(rec, [order.status(status=PENDING_CANCEL)])`；**不是 `order.canceled`**（F-I3，CANCELED 只在回报迁移时发） |
| `cancel` 拒绝 | 静默 `False` | `cancel_ex`：audit + `append_outbox([order.cancel_rejected])`（仅 `rate_*`/`unsupported`；not_found/terminal 只返回 `CancelResult`） |
| `confirm` | `upsert_order` + audit | `upsert_order_with_events(rec, [order.status])` |
| `reconcile` | audit | **仅 `AUDIT_RECONCILE`，不入 outbox**（F-I6；事件集 6 类） |

### C-15 WS 注册-快照-过滤竞态

- 连接：`register(conn)`（队列开始收）→ `snapshot = await to_thread(store.snapshot)` → `send(snapshot)` → `drain queue` 过滤 `seq > snapshot.seq` 并按 seq 排序去重 → live。
- `queue` 容量：orders 1000、market 200；溢出 → orders 走慢消费者路径（5s → error+1013），market 丢最旧。
- `seq` 只来自 outbox；`snapshot.seq = store.snapshot().seq`（同一读事务 `MAX(seq)`）。

### C-16 ticket / 鉴权 / 拒绝时机

- `POST /api/ws-ticket`：校验 reader key → `token = secrets.token_urlsafe(32)` → `ticket_store.put(token, ttl=30)`（Redis `SET NX EX`）→ 返回。
- WS 握手：`ticket` 查询参数 → `ticket_store.pop(token)`（Redis `GETDEL`）→ 失败 `send_denial_response(403)`；成功 `accept()`。
- API Key：`hmac.compare_digest(expected.encode(), provided.encode())`；长度不等先返回 False（避免异常）。
- 认证失败限流：进程内 `dict[ip, deque[ts]]`，10 次/分钟；超限 429（不占 FTD）。
- 日志脱敏：过滤 `X-API-Key`/`ticket`/`Authorization`。

### C-17 TLS factory

```python
def build_ssl_context(config, default_factory):
    ctx = default_factory()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
    ctx.set_ciphers(config.tls_ciphers)
    ctx.options |= ssl.OP_NO_COMPRESSION
    return ctx
```

- 模块级函数（`--workers>1` 需可 pickle）；`uvicorn.run(..., ssl_context_factory=build_ssl_context, workers=N)`。
- 启动断言：`minimum_version == TLSv1_2`、`get_ciphers()` 的 `protocol ∈ {"TLSv1.2","TLSv1.3"}`、`pickle.dumps(build_ssl_context)` 成功。
- 明文：仅 `allow_plaintext_loopback=True` 且 host `127.0.0.1`；否则缺证书/私钥启动失败。

### C-18 readiness 与心跳键

- 写入：heartbeat 线程 `SET p054:trading:heartbeat "<ts>" EX 10`（1s）、`SET p054:consumer:heartbeat "<ts>:<pending>" EX 10`（2s）。
- 读取：`GET` 两键，缺失/`ts` 超过 `ready_staleness_seconds` → `reasons` 加 `stale_trading`/`stale_consumer`；Redis 异常 → `redis_down`；recovery ∈ {failed,incomplete} → 503；store preflight 失败 → `db_uninitialized`。
- `/health/live` 恒 200；`/health/ready` 只在全部通过时 200。

### C-19 metrics 多 worker 聚合

- `api_worker` 在启动子进程前设置 `PROMETHEUS_MULTIPROC_DIR`（临时目录）。
- `services/metrics.py`：若环境变量存在 → `CollectorRegistry()` + `MultiProcessCollector(registry)`；否则默认 `REGISTRY`。
- Gauge 使用 `multiprocess_mode="livesum"`（连接数/队列深度/outbox_pending）；Counter/Histogram 默认。
- 单测不设该环境变量，走默认 registry；`/metrics` 断言仅检查指标名存在。

### C-20 日志 / 脱敏 / 进程退出

- JSON formatter：`{"ts","level","service","role","event",...,"latency_ms","conn_id","seq"}`；`RedactFilter` 替换敏感字段。
- 交易进程：`signal.signal(SIGINT/SIGTERM, handler)` → `stop_event.set()`；主循环与三线程检查 `stop_event`；`join(5)`；`store.close()`。
- API worker：uvicorn lifespan 关闭 store/订阅任务。

### C-21 测试基建（fake clock / FakeBus / 临时库）

- `tests/` 复用既有 `conftest` 风格；新增 `tests/_p054_helpers.py`（辅助文件，不计入 `tests/*.py` 的测试文件数？——**注意**：`tests/*.py` 计数会把辅助文件算入；因此**不新建辅助文件**，helper 内联或放 `tests/conftest.py` 追加 fixture）。
- FakeBus：`InMemoryBus` 提供 `publish`/`subscribe`/`xadd`/`xreadgroup`/`xack`/`xautoclaim` 的 asyncio 版本；单测用 `asyncio.run` 或 pytest-asyncio（**不新增依赖** → 用 `asyncio.run` 包装同步测试）。
- 临时库：`tmp_path` + `SqliteLedgerStore`；迁移测试手工建 v1 表。

---

## 3. 逐处代码

> 只列「改哪里、改成什么」；完整代码在 Step 9 落盘。行号基于当前工作区（P-053 关闭态）。

### 3.1 `pyproject.toml` / `tests.yml`（B0）

- L10 `requires-python = ">=3.11"`；L22 删 `3.10` classifier；L35 `pydantic>=2.9.0`；L59-74 `[project.optional-dependencies]` 增 `services`；L94-96 `target-version = ["py311","py312"]`。
- `tests.yml` L16 矩阵改 `["3.11","3.12"]`；mypy 步骤末尾加 `services`。

### 3.2 `live/events.py`（新建，约 90 行）

- `class OutboxEventType`（**6 常量**，DESIGN §3.4；无 reconcile）。
- `CANONICAL = dict(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`。
- `def canonical(payload: Mapping) -> str`。
- `def order_event(..., version: int | None = None)` / `fill_event(...)`：组装 `payload` dict → `canonical` → `OutboxEvent`；无 `reconcile_event`（F-I6）。
- `def next_version(rec: OrderRecord) -> int`（返回 `rec.event_version`，由 `transition` 已递增）。

### 3.3 `live/flow_control.py`（新建，约 150 行）

- `Decision`、`CancelResult`、`CancelAllReport`（DESIGN §3.2）。
- `class _WindowBudget`：`dict[int,int]` 计数、`clock`、`capacity`、`reserve_slots`；`reserve(kind)`/`release(kind)`/`remaining()`；清理 `sec-1` 之前桶。
- `class FtdBudget(_WindowBudget)`：`capacity=max(1,int(max_ftd_per_sec))`、`reserve_slots=ftd_reserve`（仅 cancel）。
- `class OrderFlowBudget(_WindowBudget)`：`capacity=max(1,int(2*internal))`、`reserve_slots=reserve_cancel`（submit 不可用）；`submit`/`cancel` 两个 kind 共享同一窗口计数，类型桶由 `RateLedger` 另管。
- 拒绝统一 `Decision(False, retry_after_ms, reason)`。

### 3.4 `live/query_scheduler.py`（新建，约 110 行）

- `BackoffPolicy.delay`（C-10 公式）。
- `QueryScheduler.run(fn)`：`with self._lock:` 串行；`wait = max(0, last + interval - clock())` → `sleep(wait)`；循环 attempt 1..N；成功后 `last = clock()`；捕 `ChannelUnavailable` → `sleep(delay)`；第 N 次失败 `raise`。
- `reset()` 供测试。

### 3.5 `live/channel.py`（改造）

- `ChannelCapability` **末尾（`notes` 之后）** 追加（全部带默认值，保持既有位置参数顺序不变）：
  ```python
  max_ftd_per_sec: float = 6.0
  ftd_reserve: int = 1
  startup_ftd_instructions: int = 2
  ```
  **注意**：`notes` 已有默认值且位于末尾；新字段必须追加在 `notes` **之后**，避免把既有第 16 个位置参数（`notes`）错映射为 `max_ftd_per_sec`。
- `resolve_limits` 不变（类型桶仍取三方最小）。

### 3.6 `live/adapters/ctp.py`（改造）

- `capability` 增 `max_ftd_per_sec=6.0, ftd_reserve=1, startup_ftd_instructions=2`。
- `max_submit_per_sec=10.0`/`max_cancel_per_sec=10.0` 保留（类型桶），注释改为「受 `max_ftd_per_sec` 共享约束，不得读作独立上限」。

### 3.7 `live/orders.py`（改造）

- `OrderRecord` 末尾追加 `event_version: int = 0`（在 `reject_reason` 之后）。
- `transition()` 的 `replace(...)` 增 `event_version=record.event_version + 1`；**同态幂等分支**（L171-175）返回原对象或仅补 broker id，版本不变。

### 3.8 `live/ledger.py`（改造）

- `apply_fill(..., outbox_events: Sequence[OutboxEvent] = ())`：按 C-13 重构；保留签名兼容（新增关键字有默认）；去重用 `fill:{fill_key}`（canonical，F-I1）。
- `apply_corporate_action` / `cash_adjust`：`_append` → `_commit`。
- `_append` 删除；`_update_position` 保留（在 `mutate` 内调用）。
- 现金/持仓的局部计算：买入分支的 `settle_reserve` 目前会改内存（L107）——重构时改为**纯计算**返回 `(new_cash, new_reserves)`，成功提交后再写回。

### 3.9 `live/ledger_store.py`（改造，约 420 行）

- 模块级：`_SCHEMA_V2`、`OutboxEvent`/`OutboxRecord`/`OutboxEventConflict`/`StoreReadOnlyError`/`StoreSnapshot`。
- `__init__(path, read_only=False)`：lock → connect（writer/reader 参数不同）→（writer）`_migrate()`；（reader）`_preflight()`。
- 组合写：`append_entries`、`append_entries_with_events`、`upsert_order_with_events`、`append_outbox(events)`。
- 读：`pending_outbox(limit)`、`outbox_after`、`max_outbox_seq`、`snapshot`。
- 状态：`mark_sent(seq, ts)`、`purge_outbox(before_ts)`、`inbox_has`/`mark_inbox`、`get_meta`/`set_meta`。
- 锁：`_write_lock`/`_read_lock`；`transaction()` 加锁。
- 只读属性：`is_read_only`。

### 3.10 `live/gateway.py`（改造）

- `__init__` 追加关键字参数（均有默认）：`ftd_budget=None`、`order_flow_budget=None`、`query_scheduler=None`、`backoff=None`、`event_version_start=1`。
- `start()`：构造预算（用 `self._limits` 与 capability）→ `startup` 占用 → 恢复序改 scheduler（C-11）。
- `submit`：`check_rate` → `pre_trade_check` → **`ftd.reserve("submit")` → `order_flow.reserve("submit")` → `adapter.submit`**（F-I4：预算在全部本地校验之后）；拒绝 → `SubmitResult(False, ..., reasons=("rate_ftd"/"rate_order_flow",))`；成功路径改组合写（C-14）。
- `_apply_order_report`：组合写 + 按状态映射事件；同态（`updated is rec`）直接返回（O-I2）。
- `poll` / `ingest_fills`：`apply_fill(..., outbox_events=[fill_event])`（只发 fill；O-I3：恢复序回放同样传入 fill 事件，已入库的由 F-I1 去重跳过）。
- `cancel_ex` 顺序（O-I4）：`not_found/terminal` → `CancelResult`（不发事件）→ `check_rate` → `ftd.reserve("cancel")` → `order_flow.reserve("cancel")` → `adapter.cancel` → 成功组合写 + `order.status(PENDING_CANCEL)`；预算拒绝 → audit + `order.cancel_rejected` + `CancelResult(False, reason, retry_after_ms)`；`cancel` 委托 `.accepted`。
- `cancel_all`：保持 `-> int`；`cancel_all_ex`：遍历 → `cancel_ex` → 统计 `CancelAllReport`；bridge 分支返回 `requested=submitted=gate 返回值, deferred=(), rejected=()`（D-8 偏差登记）。
- `confirm`：组合写 + `order.status`。
- `reconcile`：`scheduler.run`；**只写 `AUDIT_RECONCILE`，不入 outbox**（F-I6）。

### 3.11 `services/contracts.py`（新建，约 120 行）

- `EventPublisher`：`async publish(channel, message)`、`async ping()`。
- `OrderStream`：`async add(key, fields)`、`ensure_group`、`read`、`ack`、`autoclaim`。
- `TicketStore`：`put(token, ttl)`、`pop(token) -> bool`。
- `StreamMessage(id, fields)`；`ErrorCode` 常量（`not_ready/auth_failed/slow_consumer/queue_overflow/internal`）。
- 零 redis/fastapi import。

### 3.12 `services/config.py`（新建，约 140 行）

- `ServiceSettings`（DESIGN §3.8 全字段 + `heartbeat_ttl_seconds`）。
- `@classmethod from_env(cls, env: Mapping[str,str])`：`P054_` 前缀；tuple 字段按逗号拆分；`SecretStr`。
- validators（DESIGN §3.8 四条）。

### 3.13 `services/bus.py`（新建，约 300 行）

- `AsyncRedisBus(redis_url)`：`redis.asyncio.Redis`；`publish`/`ping`/`add`/`ensure_group`/`read`/`ack`/`autoclaim`；subscribe 由 ws_hub 直接使用 `client.pubsub()`。
- **`SyncRedisBus(redis_url)`**（F-I7 修复）：`redis.Redis` 同步客户端，供交易进程的 relay/consumer/heartbeat 线程使用；同方法名但同步返回；`XREADGROUP BLOCK 1000` 在此线程内阻塞。
- `InMemoryBus`：线程安全 `deque` + `dict[group, cursor]`；**同时提供 sync 与 async 包装**（trading_worker 测试走 sync、api/ws 测试走 async）。
- 工厂 `create_bus(settings, fake=False, mode="async"|"sync")`。
- 理由：交易进程是同步 SQLite + 线程模型，用同步 Redis 客户端可避免「无事件循环线程调协程」的 `RuntimeError`（REVIEW F-I7），不引入线程-事件循环桥。

### 3.14 `services/auth.py`（新建，约 130 行）

- `verify_api_key(provided, expected)`（length check + compare_digest）。
- `RedisTicketStore(bus)`：`SET NX EX` / `GETDEL`；`InMemoryTicketStore`：`dict` + 过期时间。
- `AuthFailureLimiter(limit=10, window=60)`。

### 3.15 `services/metrics.py`（新建，约 110 行）

- 指标名（DESIGN §19.8 + 领域）：`p054_ws_connections`、`p054_ws_queue_depth`、`p054_ws_dropped_ticks_total`、`p054_ws_slow_consumer_total`、`p054_ws_send_latency_seconds`、`p054_ws_resync_total`、`p054_outbox_pending`、`p054_outbox_publish_failures_total`、`p054_outbox_lag_seconds`、`p054_ftd_remaining`、`p054_rate_denied_total{reason}`、`p054_query_backoff_total`、`p054_http_requests_total{route,status}`、`p054_http_request_duration_seconds`、`p054_auth_failures_total{kind}`。
- `render()`：multiprocess 分支（C-19）。

### 3.16 `services/api.py`（新建，约 260 行）

- `create_app(settings=None) -> FastAPI`：lifespan 打开只读 store、启动订阅任务（ws_hub）、关闭清理。
- 依赖：`reader_dep`/`admin_dep`；异常处理器：`StoreReadOnlyError` → 503 `db_uninitialized`；`HTTPException` 统一 DTO。
- 端点 11 个（DESIGN §3.7）；`/api/orders` 内存过滤（D-12）；`/api/admin/broadcast-pause` 发布 `p054:admin` 消息 `{"paused":bool}`（F-I9：跨 worker 生效），同时更新本进程 flag。
- CORS：`CORSMiddleware` 仅在 `cors_origins` 非空时添加。

### 3.17 `services/api_worker.py`（新建，约 110 行）

- `build_ssl_context`（C-17，模块级）。
- `main()`：解析 env → 断言明文/证书 → `uvicorn.run("services.api:create_app", factory=True, workers=N, host, port, ssl_*, ssl_context_factory=...)`。
- `PROMETHEUS_MULTIPROC_DIR` 在 `main()` 设置（C-19）。

### 3.18 `services/ws_hub.py`（新建，约 280 行）

- `ConnectionState`：`orders_q`/`market_q`/`last_seq`/`slow_since`。
- `ConnectionHub`：`register`/`unregister`/`broadcast_orders`/`broadcast_market`/`snapshot_and_stream(ws)`。
- 订阅任务：`bus.subscribe([orders_channel, market_channel, admin_channel])`（F-I9：`p054:admin` → 更新 `paused` 标志）→ 分派到各连接（orders 带 seq）。
- 发送协程：orders 优先；market 合并；慢消费者 5s → error + `close(1013)`。
- 心跳：服务端 15s ping、30s 无 pong 关闭。

### 3.19 `services/market_gateway.py`（新建，约 130 行）

- `MarketDataSource` Protocol `poll() -> list[Tick]`。
- `SyntheticSource(symbols, hz, seed=7)`：几何随机游走；`tick_seq` 单调；`session_id`。
- `main()`：独立进程入口；`--embedded` 时由 `trading_worker` 调用 `run_embedded(stop_event)`。
- 发布 `p054:market`；无订阅者时 PUBLISH 自然丢弃（可接受）。

### 3.20 `services/outbox_relay.py`（新建，约 150 行）

- `RelayLoop(store, sync_stream, settings)`（F-I7：用 `SyncRedisBus`）：`while not stop:` → `pending_outbox(batch)` → 逐条 `add` → `mark_sent(seq, now)`；异常 → 退避（1/2/4/8/16/30）；空批 → `sleep(poll_interval)`。
- `purge_once()`：每日一次 `purge_outbox(now - retention_days*86400)`。
- 指标：`outbox_pending`、`publish_failures_total`、`outbox_lag_seconds`。

### 3.21 `services/trading_worker.py`（新建，约 230 行）

- 主线程：`ServiceSettings.from_env` → writer store → `Ledger.resume(store.entries())` → gateway（注入预算/scheduler/events）→ `gateway.start()`（recovery_state）→ 启动 relay/consumer/heartbeat **线程（均用 `SyncRedisBus`，F-I7）** → 主循环 `gateway.poll()`（0.5s）+ 巡检（6s）→ 信号退出。
- consumer 线程：`ensure_group` → `read(block=1000)` → 逐条 inbox 判定 → `publish` → `mark_inbox` → `ack`；每 2s `autoclaim(idle=60s)`；`consumer_heartbeat` 写 pending 数（同步 `SET EX`）。
- 心跳线程：C-18。
- `--bus fake`：单进程开发模式（relay/consumer 用 InMemoryBus，不连 Redis）。

### 3.22 `scripts/p054_bench_ws.py`（新建，约 140 行）

- 参数：`--messages 1000 --workers 1`；三段：append→enqueue、enqueue→send、端到端；输出 p50/p95/p99 JSON + Markdown 表。
- 不引入新依赖（`time.perf_counter` + `statistics`）。

### 3.23 测试文件（10 个，§4）

- 全部使用 `tmp_path`、`InMemoryBus`、fake clock；不依赖真机/Redis（除 `@pytest.mark.redis` 可选项，本批不强制）。

---

## 4. 测试映射（120 例 / 10 文件）

| 文件 | 例数 | 分组 | 关键断言 | I/D |
|------|------|------|----------|-----|
| `tests/test_p054_ledger_store_atomic.py` | 16 | A1-A16 | 组合写单事务；崩溃探针（业务写后 outbox 同生同灭）；fill+fee 同事务；批量幂等；Ledger store-first 回滚；**resume 后重放同 fill_key → False 且现金/持仓不变（F-I1）**；只读 preflight 四 reason；snapshot 水位 | I3/I4/I17、D4/D5 |
| `tests/test_p054_outbox_migration.py` | 12 | B1-B12 | v1→v2 顺序；seq 不复用；索引命中；冲突报错；同 payload 幂等；inbox；meta；purge | I4/I5、D6/D7 |
| `tests/test_p054_event_emission.py` | 10 | C1-C10 | **6 类**触发点（含 `cancel_rejected`）；event_id 模板（accepted 固定 v1）；event_version 递增；canonical；旧 payload 反序列化；对账仅 audit | I5、D5/D6 |
| `tests/test_p054_flow_control.py` | 16 | D1-D16 | FTD 6/s 第 7 笔；发送即计；order-flow 1报+1撤允许/第 3 笔拒绝；reserve_cancel；退还边界；reason 指标 | I7/I8/I9、D9/D10 |
| `tests/test_p054_query_scheduler.py` | 12 | E1-E12 | 最小间隔；单在途；Full Jitter 边界；封顶/次数；启动 3 查询；-2/-3 退避；fail-closed/degraded；巡检 | I10、D8 |
| `tests/test_p054_api_auth.py` | 12 | F1-F12 | 401/403；compare_digest；ticket 单次/过期；429；路由清单；CORS；TLS factory 三项断言；明文仅 loopback | I13-I15、D14/D15 |
| `tests/test_p054_ws_protocol.py` | 16 | G1-G16 | snapshot/delta；seq 单调/去重；水位；注册-快照-过滤；慢消费者 1013；行情丢旧；心跳；resume；未就绪；错误码 | I11/I12、D12/D13 |
| `tests/test_p054_relay_consumer.py` | 12 | H1-H12 | relay 顺序；XADD 成功才 mark_sent；重投；inbox 幂等；XACK/XAUTOCLAIM；扇出；Redis 故障退避 | I4/I6、D7 |
| `tests/test_p054_health_metrics.py` | 8 | I1-I8 | live/ready 分支；Redis 心跳 TTL；consumer 心跳；recovery；黄金信号；领域指标；/metrics 鉴权；JSON 日志 | I2、D16 |
| `tests/test_p054_end_to_end.py` | 6 | J1-J6 | FakeBus 全链；快照+delta 重放等价；双 worker 一致；断线重连；未就绪；延迟采样 | 全部 |

**门禁目标**：pytest **1420** / golden **22** / mypy **157** / black **309** / `tests/*.py` **151** / `live/*.py` **19** / `services/*.py` **12** / `core/*.py` **51**。

---

## 5. 与 DESIGN 的偏差与补齐（Step 6 复核清单）

| # | 项 | 说明 | 处置 |
|---|----|------|------|
| **D-1** | `CancelAllReport` 落点 | DESIGN §3.2 块内；IMPL 定在 `live/gateway.py`（依赖 `CancelResult`） | Step 6 确认分层（flow_control 不 import gateway） |
| **D-2** | `StoreReadOnlyError` 落点 | `live/ledger_store.py`；risk_anchors 伪码未标模块 | 已在 DESIGN §3.2 落点注登记 |
| **D-3** | `apply_fill` 新关键字 | `outbox_events=()` 有默认，旧调用兼容；P-053 测试不需改 | Step 6 核对无位置参数误用 |
| **D-4** | `_append` 删除 | 私有方法；`grep _append` 确认仅本文件使用 | Step 6 核对无外部引用 |
| **D-5** | `TradingGateway.__init__` 新参数 | 全部关键字 + 默认 `None`，既有构造不变 | Step 6 核对 |
| **D-6** | `_throttle_query` 保留 | 由 scheduler 内部调用；签名不变 | 与 Q10「不改造 check_rate」一致 |
| **D-7** | 恢复序包装 | `scheduler.run(lambda: ...)` 返回适配器结果；`_throttle_query` 先执行 | Step 6 核对异常传播 |
| **D-8** | bridge 分支 `cancel_all_ex` | `gate.cancel_all` 只返回 int → `deferred=(), rejected=()` | 文档写明能力边界 |
| **D-9** | FTD startup 占用 | `startup_ftd_instructions=2` 为 best-effort 预扣 | Step 6 核对不阻塞启动 |
| **D-10** | metrics 多 worker | 采用 `PROMETHEUS_MULTIPROC_DIR` + MultiProcessCollector | Step 6 核对 gauge `livesum` |
| **D-11** | `TicketStore` Protocol 落点 | `services/contracts.py`（纯协议），实现 `services/auth.py` | 与 I16 一致 |
| **D-12** | `/api/orders` 内存过滤 | `load_orders()` 全量 → 过滤/分页；>1 万单再引 SQL | DESIGN §3.7 已定 |
| **D-13** | `broadcast-pause` 跨 worker | 用 Redis Pub/Sub `p054:admin` 广播 flag；Redis 不可用时仅本 worker 生效 | Step 6 确认可接受 |
| **D-14** | 测试辅助不放新文件 | 避免 `tests/*.py` 计数漂移；fixture 追加到 `tests/conftest.py` | 若必须新建则同步门禁目标 |
| **D-15** | `PROMETHEUS_MULTIPROC_DIR` 仅 api_worker 设置 | 单测走默认 registry，避免全局污染 | Step 6 核对测试隔离 |
| **D-16** | **`reconcile.completed` 移出 outbox** | 对账只写 `AUDIT_RECONCILE`；事件集 6 类；避免重启 attempt 归零导致 `OutboxEventConflict` | F-I6 修复；DESIGN §3.4/D5 同步 |
| **D-17** | **交易进程用同步 Redis 客户端** | `SyncRedisBus`（线程）vs API 侧 `AsyncRedisBus`；避免线程内 `asyncio.run` 桥 | F-I7 修复；DESIGN §2.4/D20 同步 |
| **D-18** | **预算移到 `pre_trade_check` 之后** | 仍满足「发送前 reserve」；本地拒绝不再空耗槽位 | F-I4 修复；C-9 同步 |
| **D-19** | **accepted 事件固定 v1** | builder 显式版本参数；其余事件用 `record.event_version` | F-I2 修复；C-12 同步 |
| **D-20** | **`_seen` canonical 化** | `apply_fill` 用 `fill:{fill_key}` 去重/登记，与 `resume` 的 entry_id 对齐 | F-I1 修复；C-13 同步 |

---

## 6. 实施顺序（Step 5 执行序 → Step 9 落码按此分六批）

| 批次 | 内容 | 依赖 | 退出条件（红→绿） |
|------|------|------|-------------------|
| **B0** | pyproject/tests.yml/uv.lock：Python 3.11、`[services]`、pydantic 2.9 | 无 | 1300 测试在 3.11/3.12 全绿；`uv lock --check`；`PROTOCOL_TLS_SERVER` 默认 TLS1.2 |
| **B1** | store v2（迁移/组合写/inbox/meta/只读 preflight/双锁） | B0 | A 组 16 + B 组 12 绿；I3/I4/I5/I17 |
| **B2** | flow_control + query_scheduler + channel/ctp/gateway 接线 | B0 | D 组 16 + E 组 12 绿；I7-I10；既有 1300 回归 |
| **B3** | events + orders.event_version + ledger store-first + gateway 5 处组合写 | B1 | C 组 10 绿；I3/I5/I17；崩溃探针 |
| **B4** | contracts/config/bus/auth/metrics/api/api_worker + FakeBus | B1、B3 | F 组 12 + I 组 8 绿；I2/I13-I16 |
| **B5** | ws_hub + market_gateway + outbox_relay + trading_worker | B4 | G 组 16 + H 组 12 绿；I6/I11/I12；D20 |
| **B6** | 端到端 + 基准脚本 + 四文档 + 台账 | B5 | J 组 6 绿；pytest 1420；golden 22；mypy 157；black 309 |

**每批铁律**：先写红测试 → 实现 → 绿 → 跑全量回归；B0 之外不得改 `pyproject` 依赖；`live/*` 不 import `services/*`。

---

## 7. Step 6 复审输入

1. **本次实施计划 vs DESIGN**：D-1~D-15 逐条核对；C-1~C-21 是否把伪码落成可执行语义（尤其 C-3 冲突回滚、C-9 退还边界、C-11 恢复序、C-13 store-first）。
2. **代码事实一致性**：§3 的行号锚点（ledger_store L16-40/L121-136/L140-148、ledger L96-145/L260-263、gateway L199-205/L261-275/L299-353/L381-410/L414-439、orders L159-196、channel L26-43、ctp L53-62）在本轮是否仍精确。
3. **测试映射**：120 例/10 文件与 DESIGN §7 完全一致；门禁 1420/22/157/309/151/19/12 算术闭合。
4. **风险**：R1 preflight 的 Windows ACL 测试可跳过策略；R2 TLS factory 的 pickle 断言；metrics 多 worker 的测试隔离；`--bus fake` 不掩盖 Redis 路径。
5. **零代码检查**：本文件不应伴随任何 `.py` 变更（Step 5 只交付方案）。
6. **Step 6 首轮修复（2026-11-22）**：F-I1~F-I9 已回写 C-2/C-9/C-12/C-13/C-14/§3.8/§3.10/§3.13/§3.16/§3.18/§3.20/§3.21，新增 D-16~D-20；O-I1~O-I5 已顺手；待复审复核后 Step 6 关闭。
