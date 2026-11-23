# IMPL：P-055 微服务拆分（实施文档）

> **批次**: P-055 · **Step 5 实施（IMPL）** · 日期 2026-11-23 · **基线 commit**: `e67ebbe`
> **上游**: [DESIGN_p055_microservices](DESIGN_p055_microservices.md)（D1-D14 / I1-I12 / §15 B0-B3 / F-D1/F-D5/F-D6）· [REVIEW_p055_step4_design](REVIEW_p055_step4_design.md)（PASS，0 P1）· [RESEARCH_p055_microservices](RESEARCH_p055_microservices.md)（G1-G19）
> **模板**: `F:\Spec_Workflow\spec\templates\IMPLEMENTATION_TEMPLATE.md` + [IMPL_p054_service_layer](IMPL_p054_service_layer.md) 章节骨架
> **口径**: 只写实施；不改代码/门禁/依赖/部署资产；**不提交**。本步作者 DeepSeek-V4.1-Flash，Step 6 复审必须异构（RULE-5）。
> **版本锚（E1，2026-11-23 实测 `.venv`）**: uvicorn **0.54.0** / fastapi **0.165.0** / starlette **1.10.0** / redis-py **8.0.0** / anyio **4.16.0**；服务端 `redis:7`（Q20）；Python 3.11 / 3.12。

---

## 0. 外部锚点与实施证据（外部社区案例 / 算法 / 源码级）

> 本节是 Step 5 的**新增取证面**：每条外部事实必须可解析、版本可核对、结论只用于「支持某个实现选择或拒绝某个替代」。凡外部资料与本仓实装冲突，**以实装为准**。

### 0.1 外部锚点总表 A1-A12

| ID | 主题 | 来源（可解析 URL） | 取用结论（原文语义） | 本仓落点 | 级别 |
|----|------|--------------------|----------------------|----------|------|
| **A1** | uvicorn `ssl_context_factory` 协议 | [uvicorn 部署文档（GitHub raw）](https://raw.githubusercontent.com/encode/uvicorn/master/docs/deployment/index.md) | factory 接收 `Config` 实例与 `default_ssl_context_factory` 可调用；`ssl_*` 设置只被默认 factory 消费；factory 在**每个 worker 进程内**运行，`reload`/`workers` 下必须**可 pickle**（顶层函数） | C-7 / §3.4：`tls_context_factory(config=None, default_factory=None)` 顶层函数，忽略入参只读 env | E4 + E1（实装 0.54.0） |
| **A2** | uvicorn「app 实例 vs 多 worker」 | 同上 A1 | `uvicorn.run(app_instance)` **只在**不使用 `workers=NUM` 或 `reload` 时成立；多进程须用 import string | C-1 / C-7：`P054_WORKERS` 强制 1，多实例靠多容器（Q18） | E4 |
| **A3** | Starlette WS：accept 前 close | [Starlette WebSockets](https://www.starlette.io/websockets/) | 在 `accept()` 之前调用 `close()` → 服务器回 **HTTP 403**；要自定义拒绝响应用 `send_denial_response`（需 ASGI 扩展）；`close(code=1000)` 支持自定义码；`receive_json` 可能抛 `WebSocketDisconnect` | C-9：先 accept 再验 ticket，失败发 error 帧后 `close(4401)`——**拒绝**「accept 前 close」方案 | E4 |
| **A4** | FastAPI WebSocket 端点参数 | [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) | WS 端点与普通端点一致地支持 `Query`/`Depends` | §3.5：`ticket: str = Query(default="")`、`resume_last_seq: int = Query(default=0)` | E4 |
| **A5** | FastAPI lifespan | [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) | 推荐 `@asynccontextmanager` 的 `lifespan` 管理启动/关闭资源；旧 `on_event` 为降级路径 | C-11 / §3.6：订阅任务在 lifespan 启动、取消后 gather | E4 |
| **A6** | redis-py asyncio Pub/Sub | [redis-py Asyncio Examples（8.0.0）](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html) | `r.pubsub()` 作异步上下文；`await pubsub.subscribe(...)`；`get_message`/`listen` 消费；`await client.aclose()` 显式断连（无 asyncio 析构魔法）；8.0 起默认 RESP3 但保留 RESP2 响应形状 | C-11：`AsyncRedisBus.subscribe` + `async for ... in pubsub.listen()` + `finally: await pubsub.aclose()` | E4 + E1（实装 8.0.0） |
| **A7** | import-linter 契约语义 | [Forbidden](https://import-linter.readthedocs.io/en/stable/contract_types/forbidden/) · [Layers](https://import-linter.readthedocs.io/en/stable/contract_types/layers/) · [Configure](https://import-linter.readthedocs.io/en/stable/get_started/configure/) | Forbidden：`source_modules` 不得 import `forbidden_modules`，默认 `as_packages=True`（含后代与间接导入）；Layers：列表**从高到低**，且「列出的层必须存在，否则契约失败」；配置从 cwd 的 `.importlinter`(INI)/`pyproject.toml`(TOML) 发现；顶层用 `root_package` 或 `root_packages` | C-13 / §3.7：3 契约 TOML；负例 fixture 用 `.importlinter` INI + `cwd=` 切换 | E4 |
| **A8** | SQLite WAL 与文件系统 | [SQLite Write-Ahead Logging](https://www.sqlite.org/wal.html) | WAL **不能在网络文件系统上工作**；所有进程必须同主机（需共享内存） | C-16 / I10：Mode S named volume、Mode R NTFS 原生盘；拒绝 Windows→WSL bind mount | E4 |
| **A9** | Compose 启动顺序 | [Control startup and shutdown order](https://docs.docker.com/compose/how-tos/startup-order/) | `depends_on.condition: service_healthy` 依赖被依赖服务的 `healthcheck` | §3.11：redis 健康 → trading → api；健康检查用心跳键 | E4 |
| **A10** | NSSM 停机语义 | [NSSM Usage](https://nssm.cc/usage/) | 停机第一步向应用控制台发 **Control-C 事件**（可被控制台程序捕获优雅退出）；`AppStopMethodConsole` 配超时（毫秒）；最后才 `TerminateProcess` | C-16 / U-P055-8：NSSM 主选 → Python `SIGINT` → `stop_event` | E4 |
| **A11** | Windows 信号 | [Python signal](https://docs.python.org/3/library/signal.html) | `SIGBREAK` = Ctrl+Break，**仅 Windows**；`CTRL_C_EVENT`/`CTRL_BREAK_EVENT` 只能配合 `os.kill()` 使用 | C-2：注册 `SIGINT`/`SIGTERM`，存在时再注册 `SIGBREAK` | E4 |
| **A12** | 线程池卸载只读快照 | `.venv/Lib/site-packages/anyio/to_thread.py#L27-L31`（E1） | `run_sync(func, *args, abandon_on_cancel=False, limiter=None)` | C-10：`await anyio.to_thread.run_sync(hub.snapshot_and_stream, store, conn, ...)` | E1 |

### 0.2 社区实践对照（采用 / 拒绝）

| 社区实践 | 出处 | 本仓裁决 |
|----------|------|----------|
| Gunicorn + `UvicornWorker` 跑多进程 uvicorn | A1 文档明示的生产建议 | **拒绝**：Windows 原生（Mode R）无 gunicorn 语义；本仓用「1 worker/容器 + N 容器」实现水平扩展（A2 约束、Q18） |
| `on_event("startup")` 启后台任务 | FastAPI 旧文档/大量社区代码 | **不采用**：用 `lifespan` 上下文（A5），确保异常路径也会取消订阅任务 |
| accept 前 close 做鉴权拒绝 | 常见 WS 示例 | **拒绝**：只能回 HTTP 403，丢失 4401 语义（A3） |
| Redis Pub/Sub 断线自动重订阅 | redis-py 连接层 `on_connect` 会重放订阅（源码 `redis/asyncio/client.py`） | **部分采用**：仍在外层 `while True` 重建 `pubsub` + 指数退避，避免「连接存活但订阅丢失」静默 |
| compose 用 `network_mode`/bind mount 共享 SQLite | 社区常见「省事」写法 | **拒绝**：WAL 网络文件系统不可用（A8）+ 容器级 `:ro` 会破坏 `-shm` 映射；改用 named volume + 应用层只读 |
| 任务计划做 Windows 服务 | 常见运维贴 | **降级**：任务计划停止通常 `TerminateProcess`（等价 SIGKILL），无 `finally`；仅作 NSSM 回退（A10） |

### 0.3 本仓源码锚点（E1，Step 5 逐处改动的「起点行」）

| 锚点 | 现状事实 | 使用节 |
|------|----------|--------|
| [trading_worker.py#L45-L51](../services/trading_worker.py#L45-L51) | `start_threads()` 只启 `p054-relay` | §3.1 |
| [trading_worker.py#L54-L89](../services/trading_worker.py#L54-L89) | `main()` 无信号；`while True: gateway.poll()` 无等待（忙等） | §3.1 |
| [trading_worker.py#L110-L125](../services/trading_worker.py#L110-L125) | `Heartbeat.beat_once(value="ok")`；`run()` 不带值 | §3.1（F-D5/F-D6） |
| [outbox_relay.py#L67-L76](../services/outbox_relay.py#L67-L76) | `RelayLoop.run()` 读 `self.stop`，无 `stop_event` | §3.2 |
| [outbox_relay.py#L99-L112](../services/outbox_relay.py#L99-L112) | `ConsumerLoop` **只有** `run_once()`，无 `run()`；publish 形状 `{"seq","event"}` | §3.2 |
| [market_gateway.py#L57-L68](../services/market_gateway.py#L57-L68) | 行情发布 `{"type":"market","tick_seq":N,"ticks":[...]}` | §3.3 / §3.5 |
| [market_gateway.py#L71-L90](../services/market_gateway.py#L71-L90) | `main()` 只 `run_once()` 一次，无循环/心跳 | §3.3 |
| [api_worker.py#L33-L41](../services/api_worker.py#L33-L41) | `tls_context_factory()` **零参** → uvicorn 双参调用即 TypeError | §3.4 |
| [api_worker.py#L44-L62](../services/api_worker.py#L44-L62) | `uvicorn.run(app 实例, factory=True)`；未装配 hubs/bus/reader | §3.4 |
| [api.py#L69-L76](../services/api.py#L69-L76) | `create_app(*, settings, store, ticket_store, metrics, publisher)` | §3.6 |
| [api.py#L165-L170](../services/api.py#L165-L170) | `health_ready` 未传 `heartbeats` → 心跳检查被跳过 | §3.6 |
| [ws_hub.py#L22-L30](../services/ws_hub.py#L22-L30) | `next_frame()` **先 orders 后 market** → 单 Hub 会串流 | C-8 |
| [ws_hub.py#L56-L61](../services/ws_hub.py#L56-L61) | `register() -> ConnectionState` / `unregister(conn)` | §3.5 |
| [ws_hub.py#L155-L166](../services/ws_hub.py#L155-L166) | `snapshot_and_stream(store, conn, *, limit=200, resume_last_seq=0)` 已实现**但无调用方**（DESIGN 写作 `orders_limit`，实装为 `limit`） | §3.5 |
| [ws_hub.py#L170-L183](../services/ws_hub.py#L170-L183) | `heartbeat(conn)` 返回 `"idle"` / `"ping"` / `"close"`；`pong(conn)`、`ensure_ready(store)` | §3.5 |
| [ledger_store.py#L31-L42](../live/ledger_store.py#L31-L42) | outbox `created_ts REAL NOT NULL` / `sent_ts REAL` | §3.12 |
| [ledger_store.py#L224-L226](../live/ledger_store.py#L224-L226) | `is_read_only` 是 **property**（非方法） | §3.13 测试断言 |
| [gateway.py#L80-L92](../live/gateway.py#L80-L92) | `TradingGateway.__init__(..., scheduler=...)` | §3.1 |
| [gateway.py#L329-L347](../live/gateway.py#L329-L347) | `poll()` 无内部等待 | §3.1 |
| [gateway.py#L555-L570](../live/gateway.py#L555-L570) | `reconcile(*, ts, nav=0.0)` | §3.1 |
| [bus.py#L99-L164](../services/bus.py#L99-L164) | `SyncRedisBus`（set/get/publish/subscribe）与 `AsyncRedisBus`（async publish/subscribe） | §3.4 / §3.5 |
| [bus.py#L197](../services/bus.py#L197) | `InMemoryBusAdapter.stream_pending(consumer)` | §3.2 |
| [spec_runner_adapter.py#L62-L68](../scripts/spec_runner_adapter.py#L62-L68) | `GATES` 字典 + `_PY312` | §3.9 |
| [Dockerfile#L14-L52](../Dockerfile#L14-L52) | 现有 builder/runtime 两 stage，root 运行 | §3.10 |

### 0.4 采用纪律

1. 外部资料只引「文档/源码明确陈述」，社区二手文章仅作旁证（不进 §7 验收）。
2. 版本以 `.venv` 实装为准；外部文档跨版本行为差异（如 `aclose` vs `close`）写进对应 C 节。
3. **不新增运行时依赖**；`import-linter` 仅进 `[dev]`（A7）。
4. 外部链接在 Step 6 复审时逐条可解析性检查（列入 §8 清单）。

---

## 1. 变更总览

### 1.1 批次边界（B0 → B3，单批可回退）

| 阶段 | 目标（可判定） | 文件 | 回退方式 |
|------|----------------|------|----------|
| **B0 运行时** | 三个入口「真能长跑」：信号、三线程、非忙等、心跳、巡检、hz 循环 | `services/trading_worker.py`、`services/outbox_relay.py`、`services/market_gateway.py`、`services/api_worker.py` | 仅 `services/*` 改动，`git revert` 单提交 |
| **B1 WS 挂载** | `/ws/orders`、`/ws/market` 在真实 HTTP 升级下可用；订阅任务接线；readiness 接心跳 | `services/ws_routes.py`（新）、`services/api.py`、`tests/test_p055_ws.py` | 参数默认 `None` → 行为回 P-054 |
| **B2 门禁与部署** | 3 契约 + 负例 + CI job；compose/Dockerfile/env/证书占位；部署静态断言 | `pyproject.toml`、`uv.lock`、`.github/workflows/tests.yml`、`scripts/spec_runner_adapter.py`、`Dockerfile`、`deploy/*`、`.env.services.example`、`tests/fixtures/arch_violation/`、`tests/test_p055_arch_gate.py`、`tests/test_p055_deploy_assets.py` | 删契约/删 job；删 `deploy/`（不参与 pytest） |
| **B3 基准与运维** | 四段跨进程报告；runbook | `scripts/p055_bench_e2e.py`（新）、`docs/RUNBOOK_p055_deployment.md`（新） | 纯新增，删除即回退 |

### 1.2 文件变更清单（含规模估算）

| 文件 | 动作 | 估算行数 | 承载任务 |
|------|------|----------|----------|
| `services/trading_worker.py` | 修改 | +95 / −8 | C-2/C-3/C-4/C-5、§3.1 |
| `services/outbox_relay.py` | 修改 | +55 / −6 | C-3/C-5、§3.2 |
| `services/market_gateway.py` | 修改 | +70 / −12 | §3.3 |
| `services/api_worker.py` | 修改 | +45 / −10 | C-1/C-7/C-12、§3.4 |
| `services/ws_routes.py` | **新增** | ~180 | C-8/C-9/C-10/C-11、§3.5 |
| `services/api.py` | 修改 | +35 / −4 | §3.6 |
| `pyproject.toml` | 修改 | +30 | §3.7 |
| `uv.lock` | 修改 | 自动 | §3.7 |
| `.github/workflows/tests.yml` | 修改 | +12 | §3.8 |
| `scripts/spec_runner_adapter.py` | 修改 | +2 | §3.9 |
| `Dockerfile` | 修改 | +18 | §3.10 |
| `deploy/compose.services.yaml` | **新增** | ~85 | §3.11 |
| `.env.services.example` | **新增** | ~30 | §3.11 |
| `deploy/prometheus.yml` | **新增** | ~12 | §3.11 |
| `deploy/certs/.gitkeep` + `.gitignore` 条目 | **新增** | ~4 | §3.11 |
| `scripts/p055_bench_e2e.py` | **新增** | ~260 | §3.12 |
| `tests/test_p055_runtime.py` | **新增** | ~150 | §3.13 |
| `tests/test_p055_ws.py` | **新增** | ~140 | §3.13 |
| `tests/test_p055_arch_gate.py` | **新增** | ~70 | §3.13 |
| `tests/test_p055_entrypoint.py` | **新增** | ~90 | §3.13 |
| `tests/test_p055_deploy_assets.py` | **新增** | ~55 | §3.13 |
| `tests/fixtures/arch_violation/*` | **新增** | ~15 | §3.13 |
| `docs/RUNBOOK_p055_deployment.md` | **新增（Step 9）** | ~180 | §3.14 |

### 1.3 零变更声明（硬约束）

| 约束 | 检查 |
|------|------|
| `core/*` 零 diff | 读数 15（DESIGN §11） |
| `live/*` 零 diff | 同上；只读 / 心跳语义都放 `services/*` |
| golden 22 条零重录 | 读数 2 |
| 既有 1420 用例零回归、断言不改 | 读数 1/3 |
| 运行时依赖不变（fastapi/uvicorn/prometheus-client 在 `[services]` L75-79，**redis>=4.5.0 在主 dependencies L44**——F-S6-P055-5 修正：`pip install ".[services]"` 含主依赖，redis 可得） | `pyproject` diff 仅 `[dev]`/`[tool.importlinter]` |
| 不新增 REST 下单/撤单/kill-switch | 设计边界 §0.3 |

---

## 2. IMPL 澄清（伪码 → 可执行语义）

### C-1 进程与线程模型

- 1 个容器 = 1 个 uvicorn worker（A2）；`P054_WORKERS` 仅接受 `1`，其余 `SystemExit`。
- trading：主线程跑 `gateway.poll()` 循环；daemon 线程 `p054-relay` / `p054-consumer` / `p054-heartbeat`（可选 `p054-market`）。
- market：单进程单循环；API：1 worker 内 1 事件循环 + anyio 线程池（只读快照）。

### C-2 信号安装（仅主线程）

```python
def install_stop_handlers(stop_event: threading.Event) -> None:
    import signal

    def _handle(signum, frame):  # noqa: ANN001
        stop_event.set()

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, _handle)
    sigbreak = getattr(signal, "SIGBREAK", None)   # A11：仅 Windows 存在
    if sigbreak is not None:
        signal.signal(sigbreak, _handle)
```

约定：handler **只置位**；清理统一在 `finally`。`main()` 只允许主线程调用（`signal.signal` 限制），故 main 内不另起装配线程。

### C-3 心跳值协议（F-D5）

统一 `"<unix_ts>:<int>"`：

| 键 | 写方 | 值 | ttl |
|----|------|----|-----|
| `p054:trading:heartbeat` | `Heartbeat` 线程（trading） | `f"{int(time.time())}:{relay.last_unsent}"` | `P054_HEARTBEAT_TTL_SECONDS`（10） |
| `p054:consumer:heartbeat` | `ConsumerLoop.run` 每轮 | `f"{int(time.time())}:{bus.stream_pending(consumer)}"` | 10 |
| `p054:market:heartbeat` | `serve()` 每帧 | `f"{time.time():.3f}"` | `P054_MARKET_HEARTBEAT_TTL_SECONDS`（10） |

`Heartbeat` 改造（保留 `run()` 外形，新增可选 provider）：

```python
class Heartbeat:
    def __init__(self, bus, *, interval=1.0, ttl=10, value_provider=None):
        ...
        self._value_provider = value_provider

    def beat_once(self, *, key="p054:trading:heartbeat", value: str | None = None) -> None:
        if value is None:
            value = self._value_provider() if self._value_provider else f"{int(time.time())}:0"
        self._bus.set_key(key, value, self._ttl)

    def run(self) -> None:              # 循环不变
        while not self._stop.wait(self._interval):
            self.beat_once()
```

> 这是 F-D5 的闭合点：`build_heartbeat_reader._fresh()`（DESIGN §3.6）解析 `":"` 前的 float，滞后 > `ready_staleness_seconds` 判 stale。旧默认 `"ok"` 会走 `ValueError → True` 分支，staleness 恒不生效。

### C-4 停机收尾（F-D6）

`finally` 顺序**固定**：`stop_event.set()` → `heartbeat.stop()` → 各线程 `join(5.0)` → `gateway.shutdown()`。`Heartbeat` 自持独立 `threading.Event`，不调 `stop()` 会在停机瞬间再刷一次 TTL（`run` 的 `wait` 已返回、下一轮判断前被硬杀）。

### C-5 relay / consumer 循环语义

- `RelayLoop.run(stop_event=None)`：条件改为 `while not (stop_event.is_set() if stop_event is not None else self.stop)`；每轮后更新 `self.last_unsent = len(records)`（0..batch，供 C-3）。重试/退避逻辑不动。
- `ConsumerLoop.run(...)`（新增，**不复用** `run_once` 的返回值语义之外的行为）：

```python
def run(self, stop_event=None, *, count=100, autoclaim_every=30.0,
        heartbeat_key="p054:consumer:heartbeat", heartbeat_ttl=10,
        poll_interval=0.2) -> None:
    last_autoclaim = time.monotonic()
    while not (stop_event.is_set() if stop_event is not None else self.stop):
        due = (time.monotonic() - last_autoclaim) >= autoclaim_every
        try:
            published = self.run_once(count=count, autoclaim=due)
        except Exception as exc:          # 不退出：消费者死掉 = 永久不扇出
            _log("consumer_loop_error", error=repr(exc))
            time.sleep(1.0)
            continue
        if due:
            last_autoclaim = time.monotonic()
        if self._bus is not None:
            pending = self._bus.stream_pending(self._consumer)
            self._bus.set_key(heartbeat_key, f"{int(time.time())}:{pending}", heartbeat_ttl)
        if published == 0:
            (stop_event.wait(poll_interval) if stop_event is not None else time.sleep(poll_interval))
```

> 属性名按实装（Step 6 对码）：`self._bus`（outbox_relay.py#L92）、`self._consumer`（#L94）；`ConsumerLoop` **无** `self.batch` 字段——count 作为 `run` 的关键字参数（默认 100 = `P054_OUTBOX_BATCH_SIZE`），`run_once(count=count)` 的实装默认 `count: int = 10`（#L99）保持不动。

> `poll_interval` 是 IMPL 补充（见 §5 D-3）：`InMemoryBusAdapter.read` 非阻塞，缺节流会空转；真实 Redis 的 `read(block_ms=1000)` 已阻塞，`published==0` 后额外 0.2 s 可忽略。

### C-6 market `serve()`

```python
def serve(stop_event, *, gateway, hz, bus=None,
          heartbeat_key="p054:market:heartbeat", heartbeat_ttl=10) -> None:
    interval = 1.0 / hz if hz > 0 else 1.0
    while not stop_event.is_set():
        gateway.run_once()
        if bus is not None:
            bus.set_key(heartbeat_key, f"{time.time():.3f}", heartbeat_ttl)
        stop_event.wait(interval)
```

`main(argv)`：`--once`（单帧，保留旧行为）/ `--embedded`（daemon 线程 + 信号，给 trading `--with-market`）/ 默认独立进程（信号 + `serve`）。优先级 CLI > env > 默认（`P054_MARKET_TICK_HZ`、`P054_MARKET_SYMBOLS`、`P054_REDIS_URL`）。

### C-7 G18 入口修复

1. 删 `"factory": True`；`uvicorn.run(app, host=..., port=..., ssl_context_factory=...)`（A1/A2：实例 + `workers=1`）。
2. `P054_WORKERS`：`int(os.environ.get("P054_WORKERS", "1"))`，非 1 → `SystemExit("P054_WORKERS must be 1; scale containers instead")`。
3. `tls_context_factory(config=None, default_factory=None)` 双参；仍为顶层函数（既有 `test_p054_api_auth.py#L166` 的 `pickle.dumps` 断言继续成立）。
4. TLS 分支不变：`_tls_enabled()` 为真则传 `ssl_context_factory=tls_context_factory`，否则传 `None`（uvicorn 默认）。明文 loopback 校验仍在 `build_ssl_context` 之外（沿用 P-054）。

### C-8 双 Hub（不合并）

- `orders_hub` / `market_hub` 各一个 `ConnectionHub(orders_max=..., market_max=..., slow_seconds=...)`。
- 原因（E1，A 无替代）：`next_frame()` 先弹 `orders_q` 后弹 `market_q`（[ws_hub.py#L22-L30](../services/ws_hub.py#L22-L30)）；单 Hub 会让订单连接收到行情、行情连接收到订单。
- `ws_hub.py` **零修改**（既有测试全保留）；两个实例只是装配差异。

### C-9 鉴权顺序与关闭码

```
accept() → tickets.consume(ticket) 失败 → send {"type":"error","code":"auth_failed"} → close(4401)
        → hub.ensure_ready(store) 失败 → send error(not_ready) → close(4503)
        → hub.register() → snapshot → pending → 帧泵
```

- 先 `accept()` 的唯一理由是 A3（accept 前 close 只能 403，无法携带 4401）。
- accept 后、鉴权前：**不注册 Hub、不读 DB、不发任何帧**。
- 关闭码：4401（ticket）/ 4503（未就绪）/ 1011（心跳超时）/ 1013（慢消费者，由 Hub close 帧给出）。

### C-10 帧泵（单协程 + 20 ms 轮询）

```python
_POLL = 0.02
while True:
    frame = conn.next_frame()
    if frame is not None:
        if frame.get("type") == "close":
            await ws.close(code=int(frame["code"])); break
        await ws.send_json(_wrap(kind, frame)); continue
    action = hub.heartbeat(conn)
    if action == "close":
        await ws.close(code=1011); break
    if action == "ping":
        await ws.send_json({"type": "ping"})
    try:
        msg = await asyncio.wait_for(ws.receive_json(), timeout=_POLL)
    except asyncio.TimeoutError:
        continue
    except WebSocketDisconnect:
        break
    except ValueError:          # 非 JSON 帧
        continue
    if isinstance(msg, dict) and msg.get("type") == "pong":
        hub.pong(conn)
```

- 并发：Hub 的 `list/deque/paused` 只在事件循环线程访问 → 不加锁；订阅任务/WS 协程/心跳同 loop。
- 快照（**F-S6-P055-1 修正**）：`snapshot_and_stream` 为 keyword-only（ws_hub.py#L155-157 `*, limit=200, resume_last_seq=0`），且 `anyio.to_thread.run_sync` **不转发 kwargs**（anyio/to_thread.py#L27-31 签名仅 `*args`）——必须用 `functools.partial`：

```python
from functools import partial
snapshot, pending = await anyio.to_thread.run_sync(
    partial(hub.snapshot_and_stream, store, conn,
            limit=app.state.settings.ws_snapshot_orders_limit,
            resume_last_seq=resume_last_seq),
)
```

`store` 已 `check_same_thread=False` + `RLock`。
- 已知代价：≤20 ms 附加延迟、连接数多时 CPU 上升（R3）；>50 连接再改事件通知（U-D 观察，不预解）。

### C-11 订阅任务与重连

- `start_subscribers(app)` 返回 `[orders, market, admin]` 三个 `asyncio.Task`；仅当 `bus` 非 None。
- 每个任务：`while True: pubsub = await bus.subscribe(channel)` → `async for message in pubsub.listen()` → 处理；`except asyncio.CancelledError: raise`；`except Exception: log + await asyncio.sleep(1.0)`；`finally: await pubsub.aclose()`。
- 负载形状（E1）：orders `{"seq","event"}`；market `{"ticks":[{...}]}`；admin `{"paused": bool}`。
- 关闭：lifespan `finally` 中 `task.cancel()` + `await asyncio.gather(*tasks, return_exceptions=True)`；连接释放调 `await bus.close()`（**实装已有**：`AsyncRedisBus.close()`，bus.py#L163-164，内部 `await self._client.aclose()`——**F-S6-P055-2 修正**：原文写 `bus.aclose()` 会 AttributeError）。

### C-12 `heartbeat_reader`

- `build_heartbeat_reader(settings)` 内部建一个 `SyncRedisBus(settings.redis_url)`；`read()` 读 `p054:trading:heartbeat` / `p054:consumer:heartbeat`，用 DESIGN §3.6 的 `_fresh` 规则。
- `health_ready` 是同步 `def`（FastAPI 线程池执行）→ 使用 sync 客户端合理（与 async 订阅客户端职责分离）。
- market 心跳不进 readiness（行情可丢，不阻塞交易就绪）。

### C-13 import-linter 契约（F-D1）

- C1 layers：`["services", "live", "strategies", "core"]`（A7：高→低；四层均存在）。
- C2 forbidden：`source_modules=["core"]`，`forbidden_modules=["live","services","strategies"]`。
- C3 forbidden：`source_modules=["services.api","services.api_worker","services.ws_routes","services.ws_hub","services.market_gateway"]`（**F-D1 已补 `ws_routes`**），`forbidden_modules=["live.gateway","live.orders","live.channel","live.ledger"]`；**Step 9 校准**：`allow_indirect_imports = true`——`forbidden` 默认连间接导入一并禁止，会把 `services.api → live.ledger_store → live.ledger/orders` 误判为违规（读路径属数据层，不是「API 含交易逻辑」）。
- `services.trading_worker` 是唯一组合根例外（I8），**不**进 C3。
- 负例：`tests/fixtures/arch_violation/.importlinter`，`cwd` 切到该目录运行，exit ≠ 0 且 stdout 含 `violation_app.core`。

### C-14 就绪判定复用

`evaluate_readiness(store, heartbeats=...)` 本体不改；`health_ready` 只在 reader 非 None 时传参。`http_ready` 的 503 body 由既有实现给出 `stale_*` 原因列表，不改结构。

### C-15 基准打点（零改 `services/*`）

- T1：harness 记录 `submit_ts`，SQLite 查 `outbox.created_ts`。
- T2：`created_ts → sent_ts`（同一行）。
- T3：`_TimedBus` **委托包装**（实现 `publish/read/ack/autoclaim/stream_pending`），在 `publish()` 进入前打 `(seq, ts)` 写 `--publish-log`；`ConsumerLoop` 拿到的是包装实例 → 不改类。
- T4：独立 client 子进程订阅 `p054:orders:events`，写 `(seq, ts)` 到 `--recv-log`；父进程按 seq join。
- 全部时间戳 `time.time()`；报告输出 `report.md` + `report.json`；`--assert-p99` 默认关闭（U-P055-4）。

### C-16 部署资产边界

- `deploy/compose.services.yaml` 独立于根 `docker-compose.yml`（根文件服务回测/测试）。
- 镜像：新增 `services` target，**非 root**（uid 10001），`/app/run` 属主为 appuser（named volume 首启 copy-up 保留属主）。
- SQLite：Mode S `p055-data` named volume；Mode R NTFS 原生路径；**禁止** Windows→WSL bind mount（A8）。
- 证书：`deploy/certs/` 仅占位 + `.gitignore`；真实证书由 runbook `openssl` 生成。
- 观测：`P054_METRICS_REQUIRE_AUTH=0` + 端口仅 `127.0.0.1`；prometheus 走 `--profile obs`。

### C-17 测试基建

- 不新增测试依赖：`pytest`、`starlette.testclient`（`websocket_connect` 实装 L534）、`anyio`（fastapi 依赖）。
- **禁止** `pytest.skip` 环境分支（RULE-3）；缺依赖/缺工具直接失败。
- 需要真 Redis 的用例（entrypoint TLS、arch 契约）不依赖 Redis：契约不需要 Redis；entrypoint 用明文 loopback 分支 + TLS 分支。
- 子进程一律用 `sys.executable`（与 `.venv` 一致），超时 20 s，端口用「绑定 0 取空闲端口」策略。

### C-18 日志与退出码

- 结构化：复用 `services.log_json`（不存在时在 `ws_routes` 内 `import json; print(json.dumps(...), flush=True)` —— 以 Step 9 对码为准，**不新建日志模块**）。
- 退出码：`0` 正常停机；`1` 装配失败；`SystemExit` 文本用于 `P054_WORKERS` 误配；WS 关闭码见 C-9。

---

## 3. 逐处代码

### 3.1 `services/trading_worker.py`

现状锚点：L45-51（仅 relay）、L54-89（忙等主循环）、L110-125（Heartbeat）。

改动点（6 处）：

1. 顶部 `import signal`、`import time`、`from typing import Callable, Sequence`（按需）。
2. 新增 `install_stop_handlers(stop_event)`（C-2 代码）。
3. `Heartbeat`：增 `value_provider` 与 `beat_once(value=None)`（C-3 代码）；`run/stop` 不变。
4. `start_threads(components, *, stop_event, heartbeat=None)`：线程表 = relay + consumer +（heartbeat 非空时）heartbeat；全部 `daemon=True`。

```python
def start_threads(components, *, stop_event, heartbeat=None):
    threads = [
        threading.Thread(target=components.relay.run, args=(stop_event,),
                         name="p054-relay", daemon=True),
        threading.Thread(target=components.consumer.run, args=(stop_event,),
                         kwargs=_consumer_kwargs(), name="p054-consumer", daemon=True),
    ]
    if heartbeat is not None:
        threads.append(threading.Thread(target=heartbeat.run,
                                        name="p054-heartbeat", daemon=True))
    for t in threads:
        t.start()
    return threads
```

5. `main(argv=None)`：

```python
def main(argv=None) -> None:
    args = _parse_args(argv)                       # --bus {redis,fake} / --with-market / --once
    stop_event = threading.Event()
    install_stop_handlers(stop_event)
    ...
    gateway = TradingGateway(..., scheduler=QueryScheduler())   # 巡检与启动恢复共用
    gateway.start()
    bus = _make_bus(args.bus)                      # fake → InMemoryBusAdapter(InMemoryBus())
    components = assemble(gateway=gateway, store=store, bus=bus,
                          batch=_env_i("P054_OUTBOX_BATCH_SIZE", 100),
                          poll_interval=_env_f("P054_OUTBOX_POLL_INTERVAL_SECONDS", 0.2))
    if args.once:
        gateway.poll(); components.relay.run_once(); components.consumer.run_once()
        write_heartbeat(bus, "p054:trading:heartbeat", f"{int(time.time())}:{components.relay.last_unsent}", _env_i("P054_HEARTBEAT_TTL_SECONDS", 10))
        gateway.shutdown(); return
    heartbeat = Heartbeat(bus, interval=_env_f("P054_HEARTBEAT_INTERVAL_SECONDS", 1.0),
                          ttl=_env_i("P054_HEARTBEAT_TTL_SECONDS", 10),
                          value_provider=lambda: f"{int(time.time())}:{components.relay.last_unsent}")
    threads = start_threads(components, stop_event=stop_event, heartbeat=heartbeat)
    if args.with_market:
        threads.append(_start_market_thread(stop_event, bus))
    next_patrol = time.monotonic() + _env_f("P054_PATROL_SECONDS", 6.0)
    try:
        while not stop_event.is_set():
            gateway.poll()
            if time.monotonic() >= next_patrol:
                _safe_patrol(gateway, event_log)          # try/except + 日志，不杀进程
                next_patrol = time.monotonic() + _env_f("P054_PATROL_SECONDS", 6.0)
            stop_event.wait(_env_f("P054_POLL_SECONDS", 0.2))
    finally:
        stop_event.set()
        heartbeat.stop()                              # F-D6
        for t in threads[1:]:
            t.join(timeout=5.0)
        gateway.shutdown()
```

6. `_safe_patrol(gateway, event_log)`：`gateway.reconcile(ts=time.time(), nav=0.0)`；异常 → `event_log`/JSON 日志 `{"event":"patrol_failed"}`，不重抛。`_start_market_thread` 复用 `services.market_gateway.serve`：

```python
def _start_market_thread(stop_event, bus):
    from services.market_gateway import MarketGateway, SyntheticSource, serve
    gw = MarketGateway(SyntheticSource(_symbols(), hz=_env_f("P054_MARKET_TICK_HZ", 2.0)), bus)
    t = threading.Thread(target=serve, args=(stop_event,), kwargs={"gateway": gw, "hz": _env_f("P054_MARKET_TICK_HZ", 2.0), "bus": bus},
                         name="p054-market", daemon=True)
    t.start(); return t
```

> 辅助函数：`_env_i/_env_f(name, default)`（3 行 `int/float(os.environ.get(...))`）、`_parse_args(argv=None)`（argparse：`--bus {redis,fake}` 默认 `redis`、`--with-market`、`--once`）、`_symbols()`（`P054_MARKET_SYMBOLS` 逗号切分）。均为同文件私有函数，不新增模块。
>
> `--once` 语义：单轮 poll/relay/consumer + 一次心跳写键后退出，供 compose 冒烟与测试（不启动线程）。

### 3.2 `services/outbox_relay.py`

1. `RelayLoop.__init__` 增 `self.last_unsent = 0`；`run(stop_event=None)` 用 C-5 条件；`run_once` 末尾 `self.last_unsent = len(records)`。
2. 新增 `ConsumerLoop.run(...)`（C-5 完整代码），参数默认即生产值；count 作为 `run` 的关键字参数（默认 100）——**F-S6-P055-3 修正**（Step 8 残留清理）：实装**无** `self.batch` 字段，循环用 `self._bus`/`self._consumer`。
3. **不改** `run_once` 的 publish 形状与异常类型（`PublisherFailure` 继续上抛给 `run` 内层 `except` 统一处理）。

### 3.3 `services/market_gateway.py`

1. 新增 `serve(...)`（C-6）。
2. `main(argv=None)`：argparse；`--once` → `run_once()`；`--embedded` → `run_embedded()`；默认：建 bus（`SyncRedisBus`）+ 信号 + `serve`。
3. `run_embedded(stop_event=None)`：**改写现有 stub**（实装 market_gateway.py#L90-91 已有 `def run_embedded(stop_event=None): main()`，忽略 stop_event——**F-S6-P055-4 修正**：原文写「新增」）。新语义：外部给 event 则直接 `serve`；否则自建 event + 安装信号 + serve（供 trading `--with-market` 与独立线程）。
4. 行情发布负载**不变**（`{"type":"market","tick_seq":N,"ticks":[...]}`），订阅侧只读 `ticks`。

### 3.4 `services/api_worker.py`

```python
def tls_context_factory(config=None, default_factory=None) -> ssl.SSLContext:
    """uvicorn 协议 Callable[[Config, Callable[[], SSLContext]], SSLContext]；顶层可 pickle。"""
    return build_ssl_context(
        os.environ.get("P054_TLS_CERTFILE"),
        os.environ.get("P054_TLS_KEYFILE"),
        ciphers=os.environ.get("P054_TLS_CIPHERS", DEFAULT_CIPHERS),
        ca_certs=os.environ.get("P054_TLS_CA_CERTS"),
        require_client_cert=os.environ.get("P054_TLS_REQUIRE_CLIENT_CERT") == "1",
    )

def build_heartbeat_reader(settings) -> Callable[[], dict[str, bool]]: ...   # DESIGN §3.6 原样

def main() -> None:
    workers = int(os.environ.get("P054_WORKERS", "1"))
    if workers != 1:
        raise SystemExit("P054_WORKERS must be 1; scale containers instead")
    settings = ServiceSettings.from_env()
    store = SqliteLedgerStore(settings.sqlite_path, read_only=True)
    publisher = SyncRedisBus(settings.redis_url)
    tickets = RedisTicketStore(redis.Redis.from_url(settings.redis_url, decode_responses=True))
    heartbeat_reader = build_heartbeat_reader(settings)
    hubs = dict(orders_hub=ConnectionHub(...), market_hub=ConnectionHub(...))
    bus = AsyncRedisBus(settings.redis_url)
    app = create_app(settings=settings, store=store, ticket_store=tickets,
                     publisher=publisher, heartbeat_reader=heartbeat_reader, bus=bus, **hubs)
    kwargs = dict(host=settings.api_host, port=settings.api_port, workers=1)
    if _tls_enabled(settings):
        kwargs["ssl_context_factory"] = tls_context_factory
    uvicorn.run(app, **kwargs)
```

要点：**删** `factory=True`；`kwargs` 不再含 `factory`；`RedisTicketStore` 需要 sync 客户端（`redis.Redis.from_url`，`decode_responses=True` 保持 P-054 现状）；hub 容量/慢阈值取 `settings.ws_*`。`AsyncRedisBus` 连接释放由 lifespan 调 `await bus.close()`——**F-S6-P055-2 修正**（Step 8 残留清理）：`close()` 已实装（bus.py#L163-164，内部 `self._client.aclose()`），**`services/bus.py` 零改动**（见 §5 D-4）。

### 3.5 `services/ws_routes.py`（新增）

```python
"""WS 挂载：/ws/orders、/ws/market + Redis Pub/Sub 订阅任务（G17）。"""
from __future__ import annotations

import asyncio
import json
from functools import partial

import anyio.to_thread
from fastapi import FastAPI, Query, WebSocket
from starlette.websockets import WebSocketDisconnect

from services.contracts import ErrorCode, ServiceError

_POLL = 0.02


def mount_ws(app: FastAPI) -> None:
    @app.websocket("/ws/orders")
    async def ws_orders(ws: WebSocket, ticket: str = Query(default=""),
                        resume_last_seq: int = Query(default=0)) -> None:
        hub, store, tickets = app.state.orders_hub, app.state.store, app.state.tickets
        await ws.accept()                                  # C-9：先 accept 才能给 4401
        if not ticket or not tickets.consume(ticket):
            await ws.send_json({"type": "error", "code": ErrorCode.AUTH_FAILED})
            await ws.close(code=4401)
            return
        try:
            hub.ensure_ready(store)
        except ServiceError:
            await ws.send_json({"type": "error", "code": ErrorCode.NOT_READY})
            await ws.close(code=4503)
            return
        conn = hub.register()
        try:
            snapshot, pending = await anyio.to_thread.run_sync(
                partial(hub.snapshot_and_stream, store, conn,
                        limit=app.state.settings.ws_snapshot_orders_limit,
                        resume_last_seq=resume_last_seq),
            )
            await ws.send_json(snapshot)
            while pending:
                await ws.send_json(pending.pop(0))
            await _pump(ws, hub, conn, kind="orders")
        finally:
            hub.unregister(conn)

    @app.websocket("/ws/market")
    async def ws_market(ws: WebSocket, ticket: str = Query(default="")) -> None:
        hub, tickets = app.state.market_hub, app.state.tickets
        await ws.accept()
        if not ticket or not tickets.consume(ticket):
            await ws.send_json({"type": "error", "code": ErrorCode.AUTH_FAILED})
            await ws.close(code=4401)
            return
        conn = hub.register()
        try:
            await _pump(ws, hub, conn, kind="market")
        finally:
            hub.unregister(conn)


def _wrap(kind: str, frame: dict) -> dict:
    if kind == "market":
        return {"type": "market", "tick": frame}
    return frame


async def _pump(ws, hub, conn, *, kind: str) -> None:
    while True:
        frame = conn.next_frame()
        if frame is not None:
            if frame.get("type") == "close":
                await ws.close(code=int(frame["code"])); return
            await ws.send_json(_wrap(kind, frame)); continue
        action = hub.heartbeat(conn)
        if action == "close":
            await ws.close(code=1011); return
        if action == "ping":
            await ws.send_json({"type": "ping"})
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=_POLL)
        except asyncio.TimeoutError:
            continue
        except WebSocketDisconnect:
            return
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("type") == "pong":
            hub.pong(conn)
```

订阅任务（放同文件，避免再拆模块）：

```python
def start_subscribers(app: FastAPI) -> list[asyncio.Task]:
    if app.state.bus is None:
        return []
    cfg = (app.state.orders_hub, app.state.market_hub, app.state.bus, app.state.settings)
    return [
        asyncio.create_task(orders_subscriber(*cfg[:3], cfg[3].orders_channel)),
        asyncio.create_task(market_subscriber(*cfg[:3], cfg[3].market_channel)),
        asyncio.create_task(admin_subscriber(cfg[0], cfg[1], cfg[2], cfg[3].admin_channel)),
    ]


async def orders_subscriber(hub, bus, channel) -> None:
    while True:
        pubsub = await bus.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                payload = json.loads(message["data"])
                hub.broadcast_orders(int(payload["seq"]), payload["event"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:                        # 断线/坏帧 → 退避重连
            await asyncio.sleep(1.0)
        finally:
            await pubsub.aclose()


async def market_subscriber(hub, bus, channel) -> None:
    while True:
        pubsub = await bus.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                for tick in json.loads(message["data"]).get("ticks", []):
                    hub.broadcast_market(tick)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(1.0)
        finally:
            await pubsub.aclose()


async def admin_subscriber(orders_hub, market_hub, bus, channel) -> None:
    while True:
        pubsub = await bus.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                market_hub.set_paused(bool(json.loads(message["data"])["paused"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(1.0)
        finally:
            await pubsub.aclose()
```

> `orders_subscriber` 的 `hub` 必须是 `orders_hub`，`market_subscriber` 是 `market_hub`；`admin` 只改 `market_hub`（行情暂停语义）。`start_subscribers` 里用位置参数组合时须保证顺序正确——Step 9 落码建议显式解包为三个变量，避免 `cfg[:3]` 顺序错误（本段仅为骨架）。

### 3.6 `services/api.py`

1. `create_app` 签名追加 `orders_hub=None, market_hub=None, bus=None, heartbeat_reader=None`；`app.state` 记录。
2. **条件** lifespan（不改变 P-054 默认行为）：

```python
if bus is not None:
    @asynccontextmanager
    async def _lifespan(app):
        tasks = start_subscribers(app)
        try:
            yield
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await bus.close()   # AsyncRedisBus.close() 已存在（bus.py#L163-164）
    app = FastAPI(title=..., lifespan=_lifespan)
else:
    app = FastAPI(title=...)
```

3. 挂路由：`if orders_hub is not None and market_hub is not None and bus is not None: mount_ws(app)`（局部 import 防循环依赖）。
4. `health_ready`：

```python
reader = app.state.heartbeat_reader
status, body = evaluate_readiness(
    app.state.store, heartbeats=reader() if reader is not None else None
)
```

5. `app.state.paused` / broadcast-pause 端点不变（`publisher` 可能为 None 的既有分支保留）。

### 3.7 `pyproject.toml` + `uv.lock`

- `[project.optional-dependencies].dev` 追加 `"import-linter>=2.0,<3"`（A7；精确版本由 `uv lock` 解析后回填读数，不预写小版本）。
- 新增：

```toml
[tool.importlinter]
root_packages = ["core", "live", "strategies", "services"]
include_external_packages = false

[[tool.importlinter.contracts]]
name = "C1 分层：services > live > strategies > core"
type = "layers"
layers = ["services", "live", "strategies", "core"]

[[tool.importlinter.contracts]]
name = "C2 core 不得依赖上层"
type = "forbidden"
source_modules = ["core"]
forbidden_modules = ["live", "services", "strategies"]

[[tool.importlinter.contracts]]
name = "C3 API/WS 不得含交易逻辑"
type = "forbidden"
source_modules = ["services.api", "services.api_worker", "services.ws_routes", "services.ws_hub", "services.market_gateway"]
forbidden_modules = ["live.gateway", "live.orders", "live.channel", "live.ledger"]
```

- `uv lock` 后 `uv lock --check` 必须 0（读数 14）。
- 若 Step 9 首跑出现合法的延迟导入误报（如 `api._load_store → live.ledger_store` 不在 forbidden 列表，不应报），先用 `ignore_imports` 精确豁免并写注释（A7 支持）；不关契约。

### 3.8 `.github/workflows/tests.yml`

新增独立 job（Linux，不依赖 Windows 运行时）：

```yaml
  arch-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: |
          python -m pip install --upgrade pip
          pip install ".[dev,services]"
      - run: python -m importlinter.cli lint-imports
```

> 命令入口是 U-D2：优先 `python -m importlinter.cli lint-imports`；若该模块路径不存在，回落 `lint-imports`（两者都在 Step 9 首跑校准后写死，Step 6 只审「有 job、装 dev、跑契约」）。

### 3.9 `scripts/spec_runner_adapter.py`

`GATES`（L62-68）追加一项：

```python
"arch-check": f"{_PY312} -m importlinter.cli lint-imports",
```

`_PY312` 已在文件内定义（E1）；不新增 gate 依赖安装逻辑（本地环境由 `pip install -e ".[dev]"` 提供）。

### 3.10 `Dockerfile`

在现有 runtime stage 之后**追加**（不改 builder/runtime 的既有用途）：

```dockerfile
# ──────────────────────────── Services Stage ────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS services
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY core ./core
COPY live ./live
COPY strategies ./strategies
COPY services ./services
RUN pip install --no-cache-dir ".[services]"
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /app/run /app/logs \
 && chown -R appuser:appuser /app
USER appuser
CMD ["python", "-m", "services.api_worker"]
```

风险：`pip install ".[services]"` 需 setuptools 在本仓能发现包（仅复制四个包目录）；若打包配置依赖其他顶层目录（如 `web/`），Step 9 首建失败 → 改为 `COPY . .`（唯一可接受的补救，记录到 §5 D-7）。

### 3.11 `deploy/` + `.env.services.example`

`deploy/compose.services.yaml`：完全采用 DESIGN §4.2 设计稿（YAML 原文照搬，不加不减），要点：

- `x-runtime` 锚点：`target: services`、`restart: unless-stopped`、`init: true`、`stop_grace_period: 10s`、`env_file: [../.env.services]`、`depends_on.redis.condition: service_healthy`（A9）。
- `redis:7` + `--appendonly yes` + `redis-cli ping` 健康检查 + **不发布端口**。
- `trading` 挂 `p055-data:/app/run`，健康检查读 `p054:trading:heartbeat`。
- `api` 挂同一卷（读写）+ `../deploy/certs:/certs:ro`，`ports: ["127.0.0.1:8054:8054"]`，TLS 环境变量齐全，健康检查 `https://127.0.0.1:8054/health/live` 且忽略自签校验证。
- `prometheus` 走 `profiles: ["obs"]`。
- `volumes: p055-data / redis-data`。

`.env.services.example` 键集（与 DESIGN §3.7 一一对应，**不含真实密钥**）：

```
P054_REDIS_URL=redis://redis:6379/0
P054_SQLITE_PATH=/app/run/live_ledger.db
P054_API_KEY=change-me-16chars-min
P054_API_HOST=0.0.0.0
P054_API_PORT=8054
P054_WORKERS=1
P054_TLS_CERTFILE=/certs/cert.pem
P054_TLS_KEYFILE=/certs/key.pem
P054_ALLOW_PLAINTEXT_LOOPBACK=0
P054_METRICS_REQUIRE_AUTH=0
P054_MARKET_TICK_HZ=2.0
P054_MARKET_SYMBOLS=600000.SH
P054_MARKET_HEARTBEAT_TTL_SECONDS=10
P054_PATROL_SECONDS=6.0
P054_POLL_SECONDS=0.2
```

`deploy/prometheus.yml`：

```yaml
scrape_configs:
  - job_name: p055-api
    scheme: https
    tls_config:
      insecure_skip_verify: true
    static_configs:
      - targets: ["api:8054"]
```

`deploy/certs/.gitkeep` + `.gitignore` 追加 `deploy/certs/*.pem`、`.bench/`、`.env.services`。

### 3.12 `scripts/p055_bench_e2e.py`（新增）

子命令：`run`（默认）与 `client`（子进程内部用）。

```python
# 结构骨架（非全文）
def main(argv=None):
    args = _parse(argv)
    if args.cmd == "client":
        _run_client(args)          # redis pubsub → --recv-log
        return
    os.makedirs(os.path.dirname(args.sqlite_path), exist_ok=True)
    store = SqliteLedgerStore(args.sqlite_path)
    gateway, event_log = _build_writer(store)          # 生产同构装配（复用 _build_gate/TerminalChannelAdapter/Ledger）
    gateway.start()
    bus = _TimedBus(SyncRedisBus(args.redis_url), args.publish_log)
    relay = RelayLoop(store, bus, batch=100, poll_interval=0.0)
    consumer = ConsumerLoop(store, bus)
    stop = threading.Event()
    threads = [threading.Thread(target=relay.run, args=(stop,), daemon=True),
               threading.Thread(target=consumer.run, args=(stop,), daemon=True)]
    ...
    submit_ts = {}
    for i in range(args.n):
        submit_ts[i] = time.time()
        gateway.submit(_intent(i), _ctx())             # 与 tests/test_p053_end_to_end.py 的构造同源
    ...
    rows = _read_outbox_rows(args.sqlite_path)         # created_ts / sent_ts
    _spawn_client(args)                                # T4
    report = _aggregate(args, submit_ts, rows)
    _write_report(report, args.out, args.json)
    if args.assert_p99 and _p99(report) > args.assert_p99:
        raise SystemExit(1)
```

- `_TimedBus`：委托全部方法；`publish(channel, message)` 前 `if isinstance(message, dict) and "seq" in message: log(seq, time.time())`，再 `inner.publish`。
- `_read_outbox_rows`：用标准库 `sqlite3` 只读连接读 `outbox(seq, created_ts, sent_ts)`（不依赖 `live` 私有 API）。
- `--assert-p99` 默认 `None`；`--n`、`--redis-url`、`--sqlite-path`、`--out`、`--json` 必填/默认如 DESIGN §6.2。
- 不 import `services.api*`（保持「不进生产镜像」的隔离）；`--mode ws --with-api` 为 U-D1 升降级开关，默认不实现。

### 3.13 `tests/`（5 个新文件 + fixture）

| 文件 | 用例（名） | 断言要点 | 对应 |
|------|-----------|----------|------|
| `test_p055_runtime.py` | `test_install_stop_handlers_sets_event` | 取出注册的 handler 直接调用 → event set（不 `os.kill`） | C-2 |
| | `test_heartbeat_value_parseable_by_reader` | provider 写 `"1700000000:3"`；用假 bus 复算 `_fresh` → True，滞后 5 s → False | F-D5 |
| | `test_shutdown_calls_heartbeat_stop` | monkeypatch `Heartbeat.stop`，跑 `main--once` 之外的最小收尾路径 | F-D6 |
| | `test_relay_loop_respects_stop_event` | 置位后 ≤5 s 退出 | C-5 |
| | `test_consumer_run_writes_pending` | FakeBus `stream_pending=7` → 键值后缀 `:7` | C-3 |
| | `test_consumer_run_does_not_busy_loop` | Fake 时钟计数 `wait/sleep` 次数 > 0 | C-5 |
| | `test_fake_bus_assembly` | `--bus fake` 不触网，`assemble` 可用 | G14 |
| `test_p055_ws.py` | `test_snapshot_first_frame` | TestClient `websocket_connect("/ws/orders?ticket=...")` → 首帧 `type=snapshot` | I3 |
| | `test_missing_ticket_4401` | 无 ticket → 收 error 帧后关闭码 4401 | C-9 |
| | `test_not_ready_4503` | store 未写 `recovery_state` → 4503 | C-9 |
| | `test_slow_consumer_1013` | 小 `orders_max=1` + `slow_seconds=0` 灌帧 → close 1013 | C-9 |
| | `test_market_frame_wrapped` | `broadcast_market(tick)` → `{"type":"market","tick":{...}}` | C-10 |
| `test_p055_arch_gate.py` | `test_repo_contracts_pass` | `lint-imports` exit 0 | I7 |
| | `test_negative_fixture_fails` | cwd=fixture → exit ≠0 且输出含 `violation_app.core` | C-13 |
| | `test_three_contracts_declared` | `tomllib` 读 pyproject，契约数 ≥3 且名字含 C1/C2/C3 | C-13 |
| `test_p055_entrypoint.py` | `test_plaintext_loopback_health_live` | 子进程 uvicorn（`ALLOW_PLAINTEXT_LOOPBACK=1` + `127.0.0.1`）→ `/health/live` 200 | 读数 8 |
| | `test_tls_handshake` | 临时自签证书 → `ssl._create_unverified_context` 握手 200 | 读数 8 |
| `test_p055_deploy_assets.py` | `test_compose_services_and_health` | 文本断言：`redis:7`、`service_healthy`、`p055-data`、`127.0.0.1:8054:8054`、`P054_METRICS_REQUIRE_AUTH: "0"` | 读数 13 |
| | `test_dockerfile_services_non_root` | 文本断言：`AS services`、`useradd`、`USER appuser` | C-16 |
| `tests/fixtures/arch_violation/` | `.importlinter` / `violation_app/{__init__,core,upper}.py` | `core.py` 内 `from violation_app.upper import helper` | A7 负例 |

> `test_p055_ws.py` 使用 `FakeAsyncBus`（`subscribe` 返回带 `listen()`/`aclose()` 的假对象）注入 `create_app(bus=...)`，**不依赖真 Redis**；`TestClient` 的 lifespan 会启订阅任务，假对象需保证 `listen()` 立刻结束或阻塞在可取消点。

### 3.14 `docs/RUNBOOK_p055_deployment.md`（Step 9 产物，Step 5 定大纲）

1. 前置：Docker Desktop/Redis、证书生成（`openssl req -x509 -newkey rsa:2048 -nodes -days 30`）。
2. Mode S：`cp .env.services.example .env.services` → 改 `P054_API_KEY` → `docker compose -f deploy/compose.services.yaml up -d` → 健康检查 → 日志。
3. Mode R：Redis 容器 + 三条 `nssm install/set/start`；`AppStopMethodConsole 15000`。
4. 备份：`sqlite3 live_ledger.db ".backup ..."`（在线备份）+ outbox 未被消费时的恢复顺序。
5. 证书轮换；6. 故障排查表（503 stale、4401、4503、1013、卷属主）；7. 跨机只读回退（Q19：仅文档化，不建读模型）。

---

## 4. 测试映射（设计 → 用例）

| 设计条目 | 用例/读数 | 文件 |
|----------|-----------|------|
| O1 长跑 + 非忙等 | `test_consumer_run_does_not_busy_loop` + 读数 10 | runtime |
| O2 WS 可用 | 4 条 WS 用例 + 读数 9 | ws |
| O3 停机 ≤10 s | `test_relay_loop_respects_stop_event` + 停机探针 | runtime |
| O4 部署可复现 | `test_compose_*` + `docker compose config -q`（读数 13） | deploy_assets |
| O5 依赖方向 | 3 条 arch 用例 + 读数 7 | arch_gate |
| O6 跨进程延迟 | 读数 12（bench 报告） | bench |
| I1-I2 | `store.is_read_only` property 断言（**属性不是方法**） | runtime |
| I3-I5 | WS 三用例 | ws |
| I6 | 停机探针 | runtime |
| I7-I9 | arch | arch_gate |
| I10-I12 | compose 静态断言 + runbook | deploy_assets |

---

## 5. 与 DESIGN 的偏差与补齐（Step 6 逐条核）

| ID | 偏差/补齐 | 理由 | 影响 |
|----|-----------|------|------|
| **D-1** | `Heartbeat` 增 `value_provider`（DESIGN 只说「value provider 或调用点传值」） | 收敛为单一实现点，避免两处拼字符串 | 无（默认行为改为 `"<ts>:0"`，正是 F-D5 要求） |
| **D-2** | trading 心跳 `<int>` 取 `relay.last_unsent`（0..batch）而非全表精确计数 | `pending_outbox(limit)` 精确计数需全表/大 limit 扫描，心跳 1 Hz 不划算 | 语义为「最近一轮未发送」；精确 PEL 在 consumer 心跳；DESIGN §3.6 的 `_fresh` 只用 ts 前段 |
| **D-3** | `ConsumerLoop.run` 增 `poll_interval=0.2` | `InMemoryBusAdapter.read` 非阻塞，`--bus fake`/测试会空转 | 生产路径 `published>0` 时不受影响 |
| **D-4** | lifespan 关闭调 `await bus.close()`（**F-S6-P055-2 修正**：`AsyncRedisBus.close()` 实装已有，bus.py#L163-164，内部调 `self._client.aclose()`） | redis-py 8 无 asyncio 析构（A6） | **`services/bus.py` 零改动**（原文「需补 aclose 3 行」撤销） |
| **D-5** | lifespan 仅在 `bus is not None` 时注入 | 保证 P-054 默认 app 完全等价（零回归硬约束） | 无 |
| **D-6** | `--once` 明确定义为「单轮 poll/relay/consumer + 一次心跳」 | DESIGN 只列参数未定义语义 | 仅 CLI，不影响生产 |
| **D-7** | `services` stage 若 `pip install ".[services]"` 失败，退回 `COPY . .` | 打包发现面不确定（E0） | 镜像变大，非功能风险 |
| **D-8** | `test_p055_ws` 用 FakeAsyncBus 而非真 Redis | CI 无外部服务下限也需可跑（RULE-3） | 无（真 Redis 由 bench/entrypoint 覆盖） |
| **D-9** | 快照调用参数名按实装 `limit` / `resume_last_seq`（DESIGN §3.5 写作 `orders_limit`） | 实装签名 `snapshot_and_stream(store, conn, *, limit=200, resume_last_seq=0)`（ws_hub.py#L155-156），`ws_hub` 不改 | 仅 IMPL 正确性；DESIGN 文字待 Step 6 复核（也可由 Step 9 顺手改 DESIGN 一处） |
| **D-10** | WS 路由取票据用 `app.state.tickets`（DESIGN 未规定 state 键名；P-054 实装即 `tickets`） | 与 `create_app` 既有赋值一致 | 无 |

---

## 6. 实施顺序（红绿）

| 步 | 动作 | 红 | 绿 |
|----|------|----|----|
| 0 | 先写 `test_p055_runtime.py`（C-2/C-3/C-5/F-D5/F-D6） | 5-7 failed | 改 `trading_worker`/`outbox_relay` 后全绿 |
| 1 | market `serve` + 信号 + argparse | 0 新增用例（**Step 8 口径澄清**：market 不设独立 pytest 用例，§3.13 明细即全集；验证出口 = T5 + C9 compose 静态 + Step 10 实机） | `market_gateway` 完成 |
| 2 | `ws_routes.py` + `api.py` 扩展（先写 `test_p055_ws.py`） | 5 failed | B1 全绿 |
| 3 | `api_worker` G18 + `test_p055_entrypoint.py` | 2 failed（现状必红：factory/零参） | 2 passed |
| 4 | 契约 + 负例 + `test_p055_arch_gate.py` + CI job + gate | 1 failed（无契约/无依赖） | 3 passed |
| 5 | Dockerfile + deploy + `test_p055_deploy_assets.py` | 1-2 failed | 全绿 |
| 6 | bench 脚本（不计门禁）+ 两轮手跑 | — | 报告落 `.bench/` |
| 7 | runbook | — | — |
| 8 | 全量：`pytest` / `black --check .` / `mypy ...` / `uv lock --check` / `lint-imports` | — | 读数 1-7/14 |

---

## 7. 门禁与验收读数映射

| # | 读数 | 命令 | 期望 |
|---|------|------|------|
| 1 | pytest | `python -m pytest tests/ -q` | ≥1420 + 新增（预计 +17~19） |
| 2 | golden | `python -m pytest tests/ -k golden -q` | 22 passed，零重录 |
| 3 | `-k p054` | `python -m pytest tests/ -k p054 -q` | ≥120，断言未改 |
| 4 | mypy | CI 同款 `mypy ... core ... live services` | 157+2 files（`ws_routes.py`、`p055_bench_e2e.py`）· 0 |
| 5 | black | `black --check .` | 309+7 unchanged |
| 6 | 计数 | `glob` | services **13**；tests ≥156 |
| 7 | 契约 | `lint-imports`（**Step 9 校准**：import-linter 2.17 无 `python -m importlinter.cli` 入口，改用 console script） | exit 0；负例 ≠0 |
| 8 | 入口 | `test_p055_entrypoint.py` | `/health/live` 200 + TLS 握手 |
| 9 | WS | `test_p055_ws.py` | snapshot/4401/4503/1013/包装 |
| 10 | CPU | `Get-Process` 采样 30 s（或 `psutil` 手测） | <5% 单核 |
| 11 | readiness | 删键 → `curl /health/ready` | 200 → 503 `stale_*` |
| 12 | 基准 | `python scripts/p055_bench_e2e.py run --n 1000/10000` | 报告：`dropped=0`、`pending_after=0`、`unsent_after=0` |
| 13 | compose | `docker compose -f deploy/compose.services.yaml config -q` | exit 0 |
| 14 | lock | `uv lock --check` | exit 0 |
| 15 | 结构 | `git diff --stat -- core live` | 空 |

---

## 8. Step 6 复审输入（可证伪清单）

1. **外部锚点可解析**：A1-A11 逐条打开；A1 中「factory 双参 + worker 内 + 可 pickle」、A3「accept 前 close → 403」、A7「层必须存在」、A10「Control-C 优先」是否被正确引用（§0.1）。
2. **实装版本**：`uvicorn 0.54.0` / `fastapi 0.165.0` / `redis 8.0.0` / `anyio 4.16.0` 与 §3 代码假设一致；`import-linter` 不在 `.venv`（Step 9 安装）。
3. **F-D1/F-D5/F-D6 落点**：C-13 的 `source_modules` 含 `ws_routes`；C-3 值格式；C-4 `finally` 顺序。
4. **零回归**：`create_app` 新参数默认 None；`api_worker` 删 `factory=True` 的唯一行为差异是「原为崩溃 → 现可启动」；`live/*` 零 diff（`is_read_only` 是 property）。
5. **接口签名**：`start_threads(*, stop_event, heartbeat=None)`、`RelayLoop.run(stop_event=None)`、`ConsumerLoop.run(stop_event=None, *, autoclaim_every=30.0, heartbeat_key=..., heartbeat_ttl=10, poll_interval=0.2)`、`serve(stop_event, *, gateway, hz, bus=None, ...)`、`tls_context_factory(config=None, default_factory=None)`、`build_heartbeat_reader(settings)`、`snapshot_and_stream(store, conn, *, limit=200, resume_last_seq=0)`（D-9：DESIGN 写 `orders_limit`）。
6. **契约可达性**：四个 root package 都有 `__init__.py`（E1 已核）；C3 不含 `trading_worker`；`include_external_packages=false` 不会掩盖内部依赖。
7. **测试可跑性**：无 `skip`；无新依赖；`TestClient` 依赖 starlette 1.10 的 `websocket_connect`（实装存在）。
8. **读数一致性**：§7 与 DESIGN §11 数字一一对应（157+2 / 309+7 / services 13 / tests ≥156 为 Step 5 估算，Step 9 回填真值）。

---

## 9. 风险与交回

| # | 风险 | 处置 |
|---|------|------|
| R-IMPL-1 | ~~`AsyncRedisBus` 无 `aclose`（D-4）~~ **撤销（F-S6-P055-2）**：`close()` 已存在（bus.py#L163-164） | lifespan 直接 `await bus.close()`；测试断言退出后无 pending task |
| R-IMPL-2 | ~~属性名/构造顺序未逐一核~~ **部分结案（F-S6-P055-3/6）**：`self._bus`/`self._consumer` 已按实装修正（C-5）；`MarketGateway(source, publisher, *, channel)`（market_gateway.py#L52）与 `SyntheticSource(symbols, *, hz, seed)`（#L25-27）顺序已核正确。**残留**：`QueryScheduler()` 构造签名与 `scheduler=QueryScheduler()` 显式传入（现状 main() 不传，gateway 内部 `if self._scheduler is not None` 守卫）留 Step 9 对码 | Step 9：`QueryScheduler` 若需参数按实装调整；不传 scheduler 亦可运行（守卫在 gateway.py#L424/L561） |
| R-IMPL-3 | market 心跳值（纯 `ts`，无 pending）在 `--bus fake` 下无跨进程意义 | runbook 标注；测试只断言字符串可解析 |
| R-IMPL-4 | `pip install ".[services]"` 打包发现失败 | D-7 回退 `COPY . .` |
| R-IMPL-5 | Starlette 1.10 的 `receive_json` 取消语义 | 20 ms `wait_for` 取消已在 C-10；若实测取消导致丢帧，改 Hub 事件通知（U-D 观察，不入本批） |
| R-IMPL-6 | Windows `signal.signal` 在非主线程报错 | `main()` 主线程安装；`--with-market` 线程不装信号 |
| 交回 | U-D1（`--with-api`）/U-D2（lint 入口）/U-D3（证书轮换）/U-D4（跨机回退）/U-D5（trading 指标端口） | **不预解**，按 DESIGN §13 触发条件 |

---

## 10. 状态链

| 阶段 | 结论 | 证据 |
|------|------|------|
| Step 1 RESEARCH | 完成（G1-G19） | [RESEARCH_p055_microservices](RESEARCH_p055_microservices.md) |
| Step 2 异构复审 | PASS（16/16 + 新增 3） | [REVIEW_p055_step2_research](REVIEW_p055_step2_research.md) |
| Step 3 DESIGN | 完成（D1-D14 / I1-I12 / U-D1..D5） | [DESIGN_p055_microservices](DESIGN_p055_microservices.md) |
| Step 4 异构复审 | PASS（0 P1，P2×6 回写） | [REVIEW_p055_step4_design](REVIEW_p055_step4_design.md) |
| **Step 5 IMPL** | **完成（本文档）**：B0-B3 逐处代码 + 外部锚点 A1-A12 + 测试映射 | 本文档 |
| Step 6 IMPL 复审 | **PASS（有条件）**：P1×1 + P2×2 + P3×3，6 处当场回写本文档（C-10 partial 快照 / C-5 `count` 参数与 `_consumer` / §3.6 `bus.close()` / §3.3 改写 stub / §1.3 redis 主依赖 / D-4 与 R-IMPL-1 撤销） | [REVIEW_p055_step6_impl](REVIEW_p055_step6_impl.md) |
| Step 7 CHECKLIST | 完成：M16+T6+C10+I12+D14+G19+F7 = **84 项断言**，实测列全部 `[待 Step 9]` | [CHECKLIST_p055_microservices](CHECKLIST_p055_microservices.md) |
| Step 8 一致性 | **通过（2026-11-23）**：四文档交叉核对；本文档 §3.2/§3.4 两处 F-S6 修正残留清理 + §6 步 1 用例口径澄清 + 本状态链更新 | [PROGRESS](PROGRESS.md) §3.83 |
| **Step 9 TDD** | **完成（2026-11-23）**：B0-B3 落码；19 例新测试全绿；门禁 1439/22/120/159·0/319/156·13·51·19 + lint 3 kept + lock + compose + 结构零 diff；C3 `allow_indirect_imports=true` 与 `lint-imports` 入口两处校准已回写 | [CHECKLIST_p055](CHECKLIST_p055_microservices.md) |
| **Step 10 验收** | **PASS（2026-11-23，0 P1 残留）**：M13 双轮实跑三零（1k / 10k）；读数 10/11 + O3 实机；实跑修 F-B1/B2/B3/B9 四个 P1 + F-B5 harness 三缺陷；门禁 **1440 passed / 1 skipped** + 22/120/159·0/319/156·13·51·19 + lint 3 kept + lock + compose + 结构零 diff；**提交待用户授权** | [REVIEW_p055_step10_acceptance](REVIEW_p055_step10_acceptance.md) |
