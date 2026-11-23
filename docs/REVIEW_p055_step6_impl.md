# REVIEW：P-055 Step 6 IMPL 异构复审

> **批次**: P-055 · **Step 6 实施文档复审** · 日期 2026-11-23 · **基线 commit**: `e67ebbe`
> **对象**: [IMPL_p055_microservices](IMPL_p055_microservices.md)（作者 DeepSeek-V4.1-Flash）
> **复审方**: GLM-5.3-Flash（**≠ 作者，RULE-5 异构成立**）
> **输入**: [DESIGN_p055_microservices](DESIGN_p055_microservices.md)（Step 4 PASS，P2×6 已回写）· [RESEARCH_p055_microservices](RESEARCH_p055_microservices.md)（G1-G19）· 外部锚点逐条联网复检
> **口径**: 只审文档、不改代码/门禁/依赖；对 IMPL 的事实性错误**当场回写**（先例：Step 4 P2×6 回写）；未获授权不提交。

---

## 1. 引用核验（V1-V16，E1 重放）

| ID | IMPL 声明 | 复核证据 | 结论 |
|----|-----------|----------|------|
| V1 | 版本锚：uvicorn 0.54.0 / fastapi 0.165.0 / starlette 1.10.0 / redis 8.0.0 / anyio 4.16.0；import-linter 未装 | `.venv/Lib/site-packages/*.dist-info` 五个目录名逐一命中；无 `import_linter*.dist-info` | ✅ 精确 |
| V2 | `next_frame()` 先 orders 后 market（#L22-30）→ 双 Hub 依据 | ws_hub.py#L22-30 确认顺序 | ✅ |
| V3 | `register()`/`unregister()`（#L56-61） | ws_hub.py#L56-61 命中 | ✅ |
| V4 | `snapshot_and_stream` 为 keyword-only `*, limit=200, resume_last_seq=0`（#L155-157，D-9 修正方向） | ws_hub.py#L155-157：`def snapshot_and_stream(self, store, conn, *, limit: int = 200, resume_last_seq: int = 0)` | ✅ D-9 成立 |
| V5 | `heartbeat(conn)` 返回 `"idle"`/`"ping"`/`"close"`；`ensure_ready` 抛 ServiceError | ws_hub.py#L170-178 三返回值 + #L183-187 `ServiceError(ErrorCode.NOT_READY)` | ✅ |
| V6 | `create_app` 5 参数（#L69-76）；`app.state.tickets`（#L80，D-10）；`health_ready` 未传 heartbeats（#L166-169） | api.py 全部命中；`app.state.settings` 亦存在（#L78） | ✅ D-10 成立 |
| V7 | `tls_context_factory()` 零参（api_worker.py#L33-41）；`uvicorn.run(..., factory=True)`（#L44-62） | api_worker.py#L33/L44 命中 | ✅ |
| V8 | `ConsumerLoop` 无 `run()`；`run_once(count: int = 10)`（#L99）；属性 `self._bus`（#L92）/`self._consumer`（#L94）；**无 `self.batch`** | outbox_relay.py 逐一命中 | ✅（暴露 F-S6-P055-3） |
| V9 | `RelayLoop.run` 条件 `while not self.stop`（#L67-68） | outbox_relay.py#L67-68 命中 | ✅ |
| V10 | market 发布形状 `{"type":"market","tick_seq":N,"ticks":[...]}`（#L62-66）；`main()` 只 `run_once`（#L71-87） | market_gateway.py 命中 | ✅ |
| V11 | `run_embedded` stub 已存在（#L90-91，只调 `main()` 忽略 stop_event） | market_gateway.py#L90-91：`def run_embedded(stop_event=None) -> None: main()` | ⚠️ IMPL 原文写「新增」→ F-S6-P055-4 |
| V12 | `Heartbeat.beat_once(value="ok")`（#L117）/`run`（#L120）/`stop`（#L124）——F-D5 前提 | trading_worker.py#L110-125 命中 | ✅ |
| V13 | `_PY312`（#L62）+ `GATES`（#L63-68）；mypy gate 已含 `services` | spec_runner_adapter.py#L62-68，L67 mypy 命令含 `services` | ✅（读数 4 的 +2 files 成立） |
| V14 | outbox `created_ts REAL NOT NULL`（#L38）/`sent_ts REAL`（#L40）；`is_read_only` 是 property（#L225） | ledger_store.py 命中（`@property`+`def is_read_only`） | ✅（I1 断言用属性访问成立） |
| V15 | `TradingGateway.__init__(scheduler=...)`（#L81）；`poll()`（#L329）；`reconcile(*, ts, nav=0.0)`（#L555） | gateway.py#L81/L329/L555 命中；`scheduler` 参数在 #L100 | ✅（V4 级微差：参数行超锚点范围 8 行，无实质影响） |
| V16 | `SyncRedisBus`（#L99）/`AsyncRedisBus`（#L147）/`stream_pending`（#L197）；**`AsyncRedisBus.close()` 已存在**（#L163-164，内部 `await self._client.aclose()`） | bus.py 逐一命中 | ⚠️ D-4 前提「无 aclose」不完整 → F-S6-P055-2 |

### 1.1 外部锚点复检（A1-A12）

| ID | 复检方式 | 结论 |
|----|----------|------|
| A1/A2 uvicorn | 本仓实装 config.py#L246 签名 `Callable[[Config, Callable[[], ssl.SSLContext]], ssl.SSLContext]`、#L477 `self.ssl_context_factory(self, default_factory)` 双参调用——与部署文档描述一致；app 实例 vs `workers` 互斥为官方文档原文 | ✅ |
| A3 Starlette accept 前 close→403 | 官方文档「If you call `websocket.close()` before `websocket.accept()` then the server will automatically send a HTTP 403」 | ✅ C-9 顺序成立 |
| A4/A5 FastAPI | WS 端点支持 `Query`；lifespan 官方推荐 | ✅ |
| A6 redis-py | `pubsub()` 上下文 + `listen()` + `aclose()`（8.0 文档） | ✅ |
| A7 import-linter | forbidden 语义（默认含后代与间接导入）；layers「列表从高到低 + 层必须存在」；`root_packages`/`.importlinter` 发现 | ✅ |
| A8 SQLite WAL | 官方「will not work on a network filesystem」 | ✅ |
| A9/A10/A11 | compose `service_healthy`；NSSM Control-C 优先；Python `SIGBREAK` 仅 Windows | ✅ |
| A12 anyio `run_sync` | **实装签名 `run_sync(func, *args, abandon_on_cancel=False, limiter=None)`——不转发 kwargs**（anyio/to_thread.py#L27-31） | ⚠️ IMPL 用法错误 → **F-S6-P055-1（P1）** |

### 1.2 契约可达性（IMPL §8 第 6 项）

- 四个 root `__init__.py`（core/live/strategies/services）全部存在 ✅（layers「层必须存在」满足）。
- services/ 下上层导入仅两处：`api.py#L28` `from live.ledger_store import SqliteLedgerStore`（**不在** C3 forbidden 列表：live.gateway/orders/channel/ledger）与 `trading_worker.py#L57-98`（I8 组合根例外，**不在** C3 source_modules）→ **C3 对现状代码天然绿**，Step 9 第 4 步预期红（无依赖）→ 绿（装依赖+契约）成立。
- C1 layers：services 当前零直接上层导入（延迟导入仅上述两处）→ 无向上违规 ✅。

### 1.3 测试与引用细节

- `TestClient.websocket_connect` 实装 testclient.py#L534 ✅（C-17 行号精确）。
- `test_p054_api_auth.py#L166` `assert pickle.dumps(tls_context_factory)` ✅（C-7 引用精确）。
- `pyproject`：`[services]`（L75-79）= fastapi/uvicorn/prometheus-client；**redis>=4.5.0 在主 dependencies（L44）** → F-S6-P055-5（文字级）；`pip install ".[services]"` 含主依赖，结论不变。
- Dockerfile：builder（#L14-28）/runtime（#L31-52）、root 运行、`COPY . .`（#L43）✅ 与锚点一致。

---

## 2. 发现（F-S6-P055-1..6）

### F-S6-P055-1（P1）——`run_sync` 调用 keyword-only 函数的两种写法均 TypeError

- **证据**：实装 `snapshot_and_stream(self, store, conn, *, limit=200, resume_last_seq=0)`（ws_hub.py#L155-157）为 keyword-only；`anyio.to_thread.run_sync(func, *args, abandon_on_cancel=False, limiter=None)`（anyio/to_thread.py#L27-31）**无 `**kwargs`**。
- **IMPL 错误**：C-10 写 `run_sync(hub.snapshot_and_stream, store, conn, resume_last_seq, limit)`（位置传参 → 关键字参数前置 TypeError）；§3.5 写 `run_sync(..., limit=..., resume_last_seq=...)`（kwargs 传给 run_sync 自身 → TypeError）。
- **修复（已回写）**：`from functools import partial` → `await anyio.to_thread.run_sync(partial(hub.snapshot_and_stream, store, conn, limit=..., resume_last_seq=...))`；§3.5 代码 imports 补 `partial`。
- **级别理由**：照抄必炸且为 B1 关键路径（WS 快照），未修复则 Step 9 TDD 无法推进 → P1。

### F-S6-P055-2（P2）——D-4/R-IMPL-1 前提不完整：`AsyncRedisBus.close()` 已存在

- **证据**：bus.py#L163-164 `async def close() → await self._client.aclose()`。
- **IMPL 错误**：lifespan 伪码 `await bus.aclose()`（AttributeError）；D-4/R-IMPL-1 计划「bus.py 补 3 行」为多余改动。
- **修复（已回写）**：§3.6/C-11 改 `await bus.close()`；D-4 改判「bus.py 零改动」；R-IMPL-1 撤销。

### F-S6-P055-3（P2）——C-5 伪码属性名错误：`self.batch` / `self.consumer`

- **证据**：`ConsumerLoop` 无 `batch` 字段（`run_once(count: int = 10)` 为参数默认）；实装属性为 `self._consumer`（#L94）。原文 `self.run_once(count=self.batch, ...)` 与 `self._bus.stream_pending(self.consumer)` 均 AttributeError。
- **修复（已回写）**：`run(..., *, count=100, ...)` 关键字参数承载批量（默认 100 = `P054_OUTBOX_BATCH_SIZE`），`run_once(count=count)`；`self._consumer`。R-IMPL-2 相应部分结案。

### F-S6-P055-4（P3）——`run_embedded` 是改写现有 stub 而非新增

- **证据**：market_gateway.py#L90-91 已有 `def run_embedded(stop_event=None): main()`（忽略 stop_event）。
- **修复（已回写）**：§3.3 改「改写现有 stub」并注明现状行为。

### F-S6-P055-5（P3）——redis 依赖位置文字不准

- **证据**：redis>=4.5.0 在主 dependencies（pyproject#L44），不在 `[services]`（L75-79）。
- **修复（已回写）**：§1.3 更正表述；结论（镜像可得 redis）不受影响。

### F-S6-P055-6（P3）——锚点与残留对码项

- `gateway.py#L80-92` 锚点内 `scheduler` 参数实际在 #L100（超范围 8 行，无实质影响）；`QueryScheduler()` 构造签名未核，与「现状 main() 不传 scheduler、gateway 内部 `if self._scheduler is not None` 守卫（#L424/#L561）」一并留 Step 9 对码。
- **修复（已回写）**：R-IMPL-2 更新为「部分结案 + 残留」。

---

## 3. 回写记录（IMPL 6 处）

| # | 位置 | 修正 |
|---|------|------|
| 1 | C-10 快照段 + §3.5 ws_orders + §3.5 imports | `run_sync` → `functools.partial` 方案（F-S6-P055-1，P1） |
| 2 | C-11 关闭段 + §3.6 lifespan + D-4 + R-IMPL-1 | `bus.aclose()` → `bus.close()`；bus.py 零改动（F-S6-P055-2） |
| 3 | C-5 代码块 + 注记 | `count` 参数 + `self._consumer`（F-S6-P055-3） |
| 4 | §3.3 第 3 点 | 「新增」→「改写现有 stub」（F-S6-P055-4） |
| 5 | §1.3 零变更表 | redis 依赖位置更正（F-S6-P055-5） |
| 6 | §9 R-IMPL-2 | 部分结案 + QueryScheduler 残留（F-S6-P055-6） |

---

## 4. 一致性检查

| 维度 | 结论 |
|------|------|
| IMPL ↔ DESIGN | B0-B3 任务、§2.3 文件清单、§15 阶段划分逐项对应；F-D1/F-D5/F-D6 落点（C-13/C-3/C-4）与 Step 4 结论一致 ✅ |
| IMPL ↔ RESEARCH | G17/G18/G19 承接、S1-S23 引用链完整 ✅ |
| 外部锚点 ↔ 实装 | A1/A3/A6/A12 与 `.venv` 实装行为一致；A12 暴露的用法错误已修 ✅ |
| 门禁基线 | 读数 15 项与 DESIGN §11 数字一致（1420/22/157 files/309/services 12→13）✅ |
| RULE-5 | reviewer（GLM-5.3-Flash）≠ author（DeepSeek-V4.1-Flash）✅ |
| 零代码 | 本步仅 docs 变更；`git status` 应仅含 docs ✅ |

---

## 5. 判定

**PASS（有条件）**——P1×1 当场回写修复后文档级 **0 P1**；P2×2 / P3×3 全部回写。

- 条件：Step 9 TDD 以**修正后**的 IMPL 为准（`partial` 快照、`bus.close()`、`count` 参数、改写 stub）。
- P3 残留（QueryScheduler 构造签名）不阻断，已挂 R-IMPL-2。
- 外部锚点 A1-A12 全部可解析、与实装版本一致；无编造链接。

---

## 6. 状态链

| 阶段 | 结论 | 证据 |
|------|------|------|
| Step 1-5 | 完成 | RESEARCH / REVIEW_step2 / DESIGN / REVIEW_step4 / IMPL |
| **Step 6 IMPL 复审** | **本文档**：V1-V16 对码 + A1-A12 复检，P1×1/P2×2/P3×3 回写，判定 PASS（有条件） | 本文档 §1-§5 |
| Step 7 CHECKLIST | 待执行（下一步） | — |
| Step 8 一致性 → Step 9 TDD → Step 10 验收 | 待执行；提交需用户授权 | — |
