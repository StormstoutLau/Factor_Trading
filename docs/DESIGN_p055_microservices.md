# DESIGN：P-055 微服务拆分（部署化模块化单体 + 进程边界 + 依赖门禁 + 跨进程基准）

> **批次**: P-055 · **Step 3 设计（DESIGN）** · 日期 2026-11-23 · **基线 commit**: `e67ebbe`
> **上游**: [UPGRADE_MASTER_PLAN](UPGRADE_MASTER_PLAN.md) L272 / F6 L217-221 / §6 L286、L293 / §7 Q13；[PROGRESS](PROGRESS.md) §3.76-3.77
> **输入**: [RESEARCH_p055_microservices](RESEARCH_p055_microservices.md)（G1-G19）· [RESEARCH_p055_decision_anchors](RESEARCH_p055_decision_anchors.md)（U-P055-1/2/4/6 五维评分）· [REVIEW_p055_step2_research](REVIEW_p055_step2_research.md)（G17/G18 P1 承接）
> **口径**: 只写设计，不改代码/门禁/依赖/部署资产；**不提交**。Q8/Q9/Q17/Q18/Q19/Q20 与 U-P055-1/2/4/6 已裁决不重开。
> **模板**: Spec Workflow v1.7.1 DESIGN_TEMPLATE（§2A 方案矩阵 / §2 架构 / §3 接口 / §4 不变量 / §5 错误与降级 / **决策表 + 拒绝方案** / 未决项四元块 / ADR-0010 三问）。

---

## 0. 裁决记录与设计边界

### 0.1 继承裁决（不重开）

| 裁决 | 内容 | 本文档的落法 |
|------|------|--------------|
| U-P055-1 = **A** | 双部署模式：Mode S 全容器 / Mode R 应用全 Windows 原生 + 仅 Redis 容器 | §2.1 / §2.2 / §4 |
| U-P055-2 = **A** | 不拆策略引擎/风控为网络服务，保留库内调用；文档化未来拆分触发条件 | §2.1 / §3.5 |
| U-P055-4 = **A** | 跨进程基准报告制；CI 不设 SLO；`--assert-p99` 仅手动作业 | §6.3 |
| U-P055-6 = **A** | SQLite 用 named volume（Mode S）/ 原生 NTFS 盘（Mode R）；禁止 Windows→WSL bind mount | §4.2 / §10 I10 |
| Q18 | 单写者 + N 无状态 API/WS worker，无 leader election | §2.1 / §10 I1-I2 |
| Q19 | 同机只读 SQLite；跨机回退只做内部 API 文档化 | §9 / §13 U-D4 |
| Q20 | `redis:7`（不用 8.x 特性）；CI Ubuntu `services: redis` | §4.2 / §5.3 |
| Q17 | `prometheus-client` + 四黄金信号 + JSON 日志，不上 Grafana | §4.5 |

### 0.2 本步定稿（Step 3 必须收敛的四项）

| 编号 | 定稿 | 依据 |
|------|------|------|
| **U-P055-3 = A** | `import-linter` **3 契约 + 1 负例**：layers（services>live>strategies>core）、core-no-upward（forbidden）、api-no-trading（forbidden）+ fixture 负例；`[dev]` 增依赖、CI 增 `arch-check` job、本地 gate 增项 | §5 |
| **U-P055-5 = A** | 最小观测栈：JSON 日志（stdout）+ API `/metrics`（prometheus-client）+ Redis 心跳键（携带 `ts:pending`）+ 可选 prometheus profile；**不新增 trading 指标端口、不上 Grafana/OTEL/agent** | §4.5 |
| **U-P055-7 = A** | `/metrics` 仅内网可达，免鉴权（`P054_METRICS_REQUIRE_AUTH=0`）；端口不发布到 0.0.0.0 | §4.5 |
| **U-P055-8 = A** | Mode R 用 **NSSM** 注册三个 Windows 服务（Ctrl+C 语义 → SIGINT → 优雅停机）；任务计划为文档化回退 | §4.4 |

### 0.3 设计边界（不做什么）

- 不新增 REST 下单/撤单/kill-switch（P-054 D19 延续）；不新增公网暴露、多租户、鉴权体系改造。
- 不引入 Kubernetes/NATS/gRPC/服务网格/leader election。
- 不改 `core/*`、`live/*` 的既有语义；不触碰 golden 基线。
- 不把策略引擎/风控进程化（U-P055-2）；只写未来拆分触发条件（§3.5）。
- 不把 P-054 的 WS 协议字段改名或语义变更；只补齐「谁把 Hub 挂到 ASGI」这一缺口。

### 0.4 证据分级

| 级 | 含义 | 本文档用法 |
|----|------|-----------|
| E0 | 设计推理 / 未验证假设 | 必须进 §13 未决项或 §12 风险 |
| E1 | 静态对码（file:line） | 现状与接口约束 |
| E2 | 单次脚本/探针实测 | Step 9 实施后回填 |
| E3 | 门禁与基线读数 | §11 验收读数基线 |
| E4 | 外部权威（RESEARCH S1-S23） | 方案取舍依据 |

---

## 1. 目标与非目标

### 1.1 目标（可判定）

| # | 目标 | 判定方式 |
|---|------|----------|
| O1 | 三个进程入口**真能长跑**：trading writer / API+WS worker / market gateway | 进程存活 ≥ 10 min，无忙等（§11 读数 9） |
| O2 | WS 在**真实 HTTP 升级**下可用：`/ws/orders`、`/ws/market`，ticket 一次性鉴权 | 握手探针（§11 读数 8） |
| O3 | 停机可控：SIGINT/SIGTERM → 10 s 内退出，outbox 不丢 | 停机探针（§11 读数 10） |
| O4 | 部署可复现：Mode S 一条 `docker compose ... up`；Mode R 三条 NSSM 命令 | `compose config` + runbook 演练 |
| O5 | 依赖方向**被机器守住**：3 契约常绿 + 负例可证伪 | `lint-imports` 0 / 负例非 0（§11 读数 6） |
| O6 | 跨进程端到端延迟**有报告**：1k/10k 两轮，0 丢失、pending 0 | bench 报告（§11 读数 11） |

### 1.2 非目标

真实 QMT/CTP 联调（P-056）、跨机部署与分布式锁、跨机 SQLite、浏览器前端、告警通道（只保留最小栈）。

---

## 2. 架构设计

### 2.1 进程拓扑

**Mode S（synthetic / 开发 / CI）——全容器**

```
                     ┌──────────────────────────────┐
                     │        docker network        │
  host 127.0.0.1:8054│                              │
        ┌────────────▼──────────┐                   │
        │  api  (N 容器, 1 worker/容器)               │
        │  uvicorn + REST + WS  ◄──────┐            │
        └───────┬───────────▲──┘       │ Pub/Sub    │
                │ read-only │          │            │
                │ SQLite    │          │            │
        ┌───────▼───────────┴──┐   ┌───┴─────────┐  │
        │ trading (单实例)      │   │   redis:7   │  │
        │ gateway+relay+       │──►│ Streams     │  │
        │ consumer+heartbeat   │   │ Pub/Sub     │  │
        └───────┬──────────────┘   │ TTL keys    │  │
                │ rw               └───▲─────────┘  │
        ┌───────▼──────────┐           │            │
        │ p055-data (named │   ┌───────┴────────┐   │
        │ volume, WAL)     │   │ market gateway │───┘
        └──────────────────┘   └────────────────┘
```

**Mode R（真实 QMT/CTP）——应用全 Windows 原生，仅 Redis 容器**

```
Windows 原生（NSSM 服务）                      Docker Desktop (WSL2)
┌──────────────┐ ┌──────────────┐ ┌──────────┐  ┌──────────────┐
│ P055Trading  │ │  P055Api     │ │ P055Market│  │ redis:7      │
│ 单写者+账本   │ │ uvicorn+WS   │ │ 行情网关  │  │ 仅 127.0.0.1 │
└──────┬───────┘ └──────┬───────┘ └────┬─────┘  │ :6379        │
       │  NTFS 本地盘  └───────────────┴────────►└──────────────┘
       │  F:\...\live_ledger.db（**绝不跨 WSL 挂载**）
```

**关键约束**（E1 + E4/S20）：SQLite WAL 要求所有连接同机本地文件系统；Windows 与 WSL2 跨挂载会破坏文件锁语义。Mode S 因此用 **named volume**（镜像内目录初始化属主），Mode R 因此用 **NTFS 原生路径**。策略引擎/风控保持**库内调用**：它们由 trading 进程持有（`gateway` 内部调用 `SafetyGate` / `GuardPipeline`），否则会引入同步网络 RPC 与超时语义（U-P055-2 拒绝理由）。

### 2.2 Mode S vs Mode R 差异表

| 维度 | Mode S | Mode R |
|------|--------|--------|
| 应用进程 | 容器（`deploy/compose.services.yaml`） | Windows 原生（NSSM 服务） |
| Redis | `redis:7` 容器 + named volume | `redis:7` 容器（Docker Desktop/WSL2），只绑 127.0.0.1 |
| SQLite 路径 | `/app/run/live_ledger.db`（named volume） | `F:\...\live_ledger.db`（NTFS 本地盘） |
| API 绑定 | 容器内 `0.0.0.0:8054` → 宿主 `127.0.0.1:8054` | `127.0.0.1:8054` |
| TLS | 自签开发证书（`deploy/certs/`，挂载只读） | 自签/内部 CA（同机制，证书放本机目录） |
| 进程管理 | `restart: unless-stopped` + `init: true` + `stop_grace_period` | NSSM（`AppStopMethodConsole`） |
| 停止信号 | Docker `SIGTERM`（grace 10 s）→ `SIGKILL` | NSSM `CTRL_C_EVENT` → SIGINT |
| 行情源 | `SyntheticSource` | `SyntheticSource`（真实源在 P-056，留 `MarketDataSource` 端口） |
| 观测 | `/metrics` + JSON 日志（`docker logs`） | `/metrics` + JSON 日志（NSSM `AppStdout`） |
| 适用 | CI、开发、联调、演示 | 真实柜台（QMT 仅 Windows） |

### 2.3 模块与文件变更清单

| 文件 | 动作 | 设计内容 | 归属 |
|------|------|----------|------|
| [services/trading_worker.py](../services/trading_worker.py) | 修改 | signal handler、三线程启动、主循环 sleep+巡检、`--bus`/`--with-market`/`--once` | B0 运行时 |
| [services/outbox_relay.py](../services/outbox_relay.py) | 修改 | `RelayLoop.run(stop_event)`、`ConsumerLoop.run(stop_event)` + consumer 心跳 | B0 运行时 |
| [services/market_gateway.py](../services/market_gateway.py) | 修改 | `serve()` hz 循环 + 心跳键 + argparse + signal | B0 运行时 |
| [services/api.py](../services/api.py) | 修改 | `create_app` 增 `orders_hub/market_hub/bus/heartbeat_reader`；`health_ready` 接心跳；lifespan 订阅任务 | G17/G19 |
| [services/ws_routes.py](../services/ws_routes.py) | **新增** | `/ws/orders`、`/ws/market`、订阅任务、帧泵 | G17 |
| [services/api_worker.py](../services/api_worker.py) | 修改 | 去 `factory=True`、TLS factory 双参、装配 tickets/hubs/bus/心跳读取器 | G18/G19 |
| `deploy/compose.services.yaml` | **新增** | Redis + 三服务 + healthcheck/depends_on/restart/volume/profile | 部署 |
| `deploy/certs/`（gitignore） | **新增** | 开发自签证书落点 + 生成命令（runbook） | 部署 |
| `deploy/prometheus.yml` | **新增** | 可选 `obs` profile 抓取 API `/metrics` | 观测 |
| `.env.services.example` | **新增** | `P054_*` 全量 env 矩阵（§3.7） | 部署 |
| [Dockerfile](../Dockerfile) | 修改 | 新增 `services` target（`.[services]`、非 root、`/app/run` 属主） | 部署 |
| [pyproject.toml](../pyproject.toml) | 修改 | `[dev]` 加 `import-linter`；新增 `[tool.importlinter]` 3 契约 | 门禁 |
| [.github/workflows/tests.yml](../.github/workflows/tests.yml) | 修改 | 新增 `arch-check` job（Linux，不依赖 Windows） | 门禁 |
| [scripts/spec_runner_adapter.py](../scripts/spec_runner_adapter.py) | 修改 | `GATES["arch-check"] = "python -m importlinter.cli lint-imports"`（精确形态见 U-D2） | 门禁 |
| `scripts/p055_bench_e2e.py` | **新增** | 四段基准（harness + client 双进程） | 基准 |
| `tests/test_p055_runtime.py` | **新增** | 信号/循环/心跳/readiness 单测（Fake 时钟与 FakeBus） | 测试 |
| `tests/test_p055_ws.py` | **新增** | Starlette TestClient WS 握手/鉴权/快照/1013 | 测试 |
| `tests/test_p055_arch_gate.py` | **新增** | 3 契约 exit 0 + 负例非 0 + 契约数守护 | 测试 |
| `tests/test_p055_deploy_assets.py` | **新增** | compose 结构/健康检查/卷/非 root 静态断言 | 测试 |
| `tests/fixtures/arch_violation/` | **新增** | 负例包（core→upper 违规） | 测试 |
| `docs/RUNBOOK_p055_deployment.md` | **新增（Step 9）** | 启停/重启/备份/健康检查/故障排查/跨机回退 | 运维 |

> `deploy/compose.services.yaml` 不替换根 [docker-compose.yml](../docker-compose.yml)：根文件服务**回测/测试**，新文件服务**运行态**，避免互踩 `profiles` 与 `CMD`。

### 2.4 数据流与控制流

| 流 | 路径 | 语义 | 本轮新增 |
|----|------|------|----------|
| 订单事件 | gateway → outbox(SQLite) → relay `XADD p054:orders` → consumer `XREADGROUP` → `PUBLISH p054:orders:events` → API worker 订阅 → WS delta | at-least-once（Stream）+ at-most-once（Pub/Sub） | consumer 线程真正启动（G1） |
| 行情 | market poll → `PUBLISH p054:market` → API worker 订阅 → WS market | 可丢/可合并 | hz 循环（G3） |
| 控制 | API `broadcast-pause` → `PUBLISH p054:admin` → 各 worker `market_hub.set_paused` | at-most-once | 订阅任务接线（G19） |
| 心跳 | trading/consumer/market 每 N 秒 `SET p054:*:heartbeat "<ts>:<pending>" EX ttl` | TTL 过期即判死 | Heartbeat 线程 + consumer 自写（G2） |
| 就绪 | API `/health/ready` → `evaluate_readiness(store, heartbeats=reader())` | 503 = 明确原因列表 | `heartbeat_reader`（G2） |
| 观测 | API `/metrics` → Prometheus（可选） | 内网免鉴权 | §4.5 |

### 2.5 方案矩阵收敛（Type-1 出口）

四个高影响决策已在 [decision_anchors §10](RESEARCH_p055_decision_anchors.md) 完成五维评分并裁决 **A/A/A/A**（部署形态 / 服务边界 / SQLite 卷 / 基准门禁）。四项均为 Type-1（高影响、难逆转：涉及部署形态与验收口径），矩阵与拒绝方案不重复粘贴，**收敛出口**：

| 决策 | 选定 | 关键被拒替代（见 anchors §7） | 一句理由 | 代价 |
|------|------|------------------------------|----------|------|
| 部署形态 | 部署化模块化单体 | 六网络服务全拆 / 保持单进程 | 3 s/笔 + 单团队 + WAL 同机 | 无自动扩缩容；靠容器数扩 worker |
| 服务边界 | 策略/风控留库内 | 独立风控 RPC 服务 | 同步闸门引入网络超时与故障放大 | 未来拆分需改调用点 |
| SQLite 卷 | named volume / 原生盘 | Windows→WSL bind mount | WAL 文件锁跨挂载不可靠 | 跨机读需内部 API（只文档化） |
| 基准门禁 | 报告制 | CI 硬 SLO | 共享 CI 抖动 → 假红 | 回归靠人工比对报告 |

U-P055-3/5/7/8 属 **Type-2**（局部、可逆）：加 dev 依赖/CI job、加可选抓取、关一个布尔、换进程管理器均可在单批内回退 → 不展开七维矩阵，但**必须**在 §7 写「被拒替代 + 理由 + 代价」。

### 2.6 运行时补齐设计

#### 2.6.1 trading writer：三线程 + 主循环 + 信号 + 巡检

现状（E1）：`start_threads()` 只启 relay（[trading_worker.py#L45-L51](../services/trading_worker.py#L45-L51)）；`main()` 无信号、`while True: gateway.poll()` 无 sleep（[trading_worker.py#L85-L89](../services/trading_worker.py#L85-L89)）；`gateway.poll()` 无内部等待（[gateway.py#L329-L347](../live/gateway.py#L329-L347)）→ 100% CPU 空转。

目标形态：

```python
def main(argv: Sequence[str] | None = None) -> None:      # pragma: no cover
    args = _parse_args(argv)                              # --bus {redis,fake} / --with-market / --once
    stop_event = threading.Event()
    install_stop_handlers(stop_event)                     # SIGINT/SIGTERM → stop_event.set()
    ...                                                   # store/gateway 装配（不变）
    heartbeat = Heartbeat(bus, interval=_env_f("P054_HEARTBEAT_INTERVAL_SECONDS", 1.0),
                          ttl=_env_i("P054_HEARTBEAT_TTL_SECONDS", 10))
    components = assemble(gateway=gateway, store=store, bus=bus)
    threads = start_threads(components, stop_event=stop_event, heartbeat=heartbeat)
    if args.with_market:
        threads.append(_start_market_thread(stop_event, bus))   # 复用 market serve()
    next_patrol = time.monotonic() + _env_f("P054_PATROL_SECONDS", 6.0)
    try:
        while not stop_event.is_set():
            gateway.poll()
            if time.monotonic() >= next_patrol:
                _safe_patrol(gateway)                     # try/except + JSON 日志，不中断主循环
                next_patrol = time.monotonic() + _env_f("P054_PATROL_SECONDS", 6.0)
            stop_event.wait(_env_f("P054_POLL_SECONDS", 0.2))   # 可被信号立即唤醒（替代 sleep）
    finally:
        stop_event.set()
        heartbeat.stop()                          # Step4 F-D6：Heartbeat 自持独立 stop Event，必须显式停
        for t in threads:
            t.join(timeout=5.0)
        gateway.shutdown()
```

设计要点：

1. **信号只置位**，不做阻塞清理；清理统一在 `finally`（IMPL C-20 语义）。Windows 上 Python 支持 `SIGINT`/`SIGTERM`/`SIGBREAK`；`SIGBREAK` 也注册为停止信号（`CTRL_BREAK_EVENT`）。
2. **忙等修复**：`stop_event.wait(0.2)` 同时给出 0.2 s 轮询与即时唤醒；不新增 `time.sleep`。
3. **巡检**：每 `P054_PATROL_SECONDS`（默认 6 s）调 `gateway.reconcile(ts=time.time(), nav=0.0)`；异常吞掉并打 JSON 日志（`event="patrol_failed"`），**不得**杀进程。含义：巡检与启动恢复共用 `QueryScheduler`（P-054 Q7/D8），`main()` 需显式构造并传入 `TradingGateway(scheduler=...)`（`live/query_scheduler` 已存在，不改 live 代码）。
4. **三线程**：relay（已有）+ consumer（新增）+ heartbeat（新增）。全部 daemon；收尾序列 = `stop_event.set()` → **`heartbeat.stop()`**（Step4 F-D6：`Heartbeat.run` 自持独立 stop Event，不显式停则停机瞬间仍可能再刷 TTL 键）→ join → `gateway.shutdown()`。trading 心跳值必须写 `f"{ts}:{outbox_pending}"`（Step4 F-D5：现 `Heartbeat.run` 默认 `value="ok"`，`_fresh` 解析失败恒 True → staleness 失效）。
5. **`--bus fake`**：本地无 Redis 时用 `InMemoryBusAdapter(InMemoryBus())`（G14 收敛）；此时 heartbeat/readiness 无跨进程意义，仅开发用途，runbook 标注。
6. **`--with-market`**：在 trading 进程内以 daemon 线程跑 §2.6.2 的 `serve()`（IMPL §3.19 的 embedded 语义），省一个进程；默认关闭（Mode S/R 均独立进程，便于单独重启）。

#### 2.6.2 market gateway：hz 循环 + 心跳 + 信号

现状（E1）：`main()` 只 `run_once()` 一次，无循环、无 `--embedded`、无心跳（[market_gateway.py#L71-L91](../services/market_gateway.py#L71-L91)）。

```python
def serve(stop_event: threading.Event, *, gateway: MarketGateway, hz: float,
          bus=None, heartbeat_key: str = "p054:market:heartbeat", heartbeat_ttl: int = 10) -> None:
    interval = 1.0 / hz if hz > 0 else 1.0
    while not stop_event.is_set():
        gateway.run_once()
        if bus is not None:
            bus.set_key(heartbeat_key, f"{time.time():.3f}", heartbeat_ttl)
        stop_event.wait(interval)

def main(argv=None) -> None:   # argparse: --once/--embedded/--hz/--symbols/--redis-url
def run_embedded(stop_event: threading.Event | None = None) -> None   # serve(...) 薄包装
```

`--once` 保留单帧行为（测试/探针）；`run_once()` 语义与签名不变（零回归）。

#### 2.6.3 readiness 心跳接线

现状（E1）：`health_ready` 调 `evaluate_readiness(app.state.store)`，`heartbeats=None` 导致两项检查被跳过（[api.py#L165-L170](../services/api.py#L165-L170)）。

```python
status, body = evaluate_readiness(
    app.state.store,
    heartbeats=app.state.heartbeat_reader() if app.state.heartbeat_reader is not None else None,
)
```

`heartbeat_reader: Callable[[], dict[str, bool]]` 由 `api_worker.main()` 注入（§3.6）。`evaluate_readiness` 本体**不改**（已支持 `heartbeats`）。

### 2.7 WS 挂载设计（G17）

现状（E1）：`services/` 全目录 **0** 处 websocket 路由；`ConnectionHub` 为纯组件（[ws_hub.py#L33-L59](../services/ws_hub.py#L33-L59)）；`snapshot_and_stream` 已实现但无调用方（[ws_hub.py#L155-L166](../services/ws_hub.py#L155-L166)）。

**结构决策**：**两个 Hub 实例**（`orders_hub` / `market_hub`），而不是一个 Hub 挂两个端点。原因：`ConnectionState.next_frame()` 先弹 `orders_q` 再弹 `market_q`（[ws_hub.py#L22-L30](../services/ws_hub.py#L22-L30)），单 Hub 会让行情帧串到订单连接；而 `broadcast_market` 受 `paused` 控制（[ws_hub.py#L95-L99](../services/ws_hub.py#L95-L99)），语义只属于行情。两个实例**零修改**既有 `ws_hub.py`，测试全部保持。

```
FastAPI app
├── REST（P-054 11 端点，不变）
├── lifespan
│   ├── orders_subscriber(orders_hub, bus, settings.orders_channel)
│   ├── market_subscriber(market_hub, bus, settings.market_channel)
│   └── admin_subscriber(market_hub, bus, settings.admin_channel)
├── /ws/orders  ── ticket 鉴权 → ensure_ready → snapshot+pending → 帧泵（orders_hub）
└── /ws/market  ── ticket 鉴权 → 帧泵（market_hub，行情 tick）
```

**挂载条件**：`create_app(..., orders_hub=..., market_hub=..., bus=...)` 全部非空才挂 WS 与订阅任务；否则行为与 P-054 **完全一致**（现有 120 例外零影响）。

**鉴权顺序（重要）**：ASGI 在 `accept()` 之前 `close()` 只能得到 HTTP 403，**拿不到自定义关闭码**。因此设计为「先 accept → 验 ticket → 失败发 `{"type":"error","code":"auth_failed"}` → `close(4401)`」。已接受连接在鉴权前**不注册 Hub、不读 DB、不发任何数据**。

**关闭码字典**：

| 码 | 含义 | 触发 |
|----|------|------|
| 4401 | ticket 缺失/过期/已消费 | `tickets.consume()` 假 |
| 4503 | 未就绪 | `hub.ensure_ready(store)` 抛 `ServiceError(NOT_READY)` |
| 1011 | 心跳超时 | `hub.heartbeat()` 返回 `"close"`（>30 s 无 pong） |
| 1013 | 慢消费者 | Hub 队满超 `slow_seconds` 后 `next_frame()` 返回 close 帧 |

**帧泵（每连接一个协程）**：

```python
_POLL = 0.02   # 发送轮询粒度（≤20 ms 附加延迟，低于 P-054 5-50 ms 预算上限的 40%）

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
    except ValueError:
        continue
    if msg.get("type") == "pong":
        hub.pong(conn)
```

`_wrap(kind, frame)`：订单帧已是 `{"type":"delta","seq":N,"events":[...]}`（[ws_hub.py#L89](../services/ws_hub.py#L89)）原样发；行情帧是裸 tick dict → 包成 `{"type":"market","tick":{...}}`。

**并发模型**：Hub 的 `list/deque` 只在事件循环线程访问（订阅任务、WS 协程、心跳都在同一 loop），**不加锁**；SQLite 快照调用用 `await anyio.to_thread.run_sync(...)` 下沉到线程池（store 已 `check_same_thread=False` + `RLock`）。

**订阅任务**（Redis Pub/Sub 断线重连）：

```python
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
        except Exception as exc:                       # 断线/解析失败 → 退避重连，不杀 worker
            log_json("ws_orders_subscriber_error", error=repr(exc))
            await asyncio.sleep(1.0)
        finally:
            await pubsub.aclose()
```

`market_subscriber` 对 `payload["ticks"]` 逐 tick 调 `hub.broadcast_market(tick)`；`admin_subscriber` 调 `hub.set_paused(bool(payload["paused"]))`。

### 2.8 api_worker 入口修复（G18）

现状（E1）：`uvicorn.run(app 实例, factory=True)` → uvicorn 0.54 对实例做**无参调用** → TypeError → `sys.exit(3)`；`tls_context_factory()` 零参 vs uvicorn 双参协议 → TLS 启动即崩（[api_worker.py#L33-L62](../services/api_worker.py#L33-L62)）。

修复（**选 A，最小改动**）：

1. **删除 `"factory": True`**：直接 `uvicorn.run(app, host=..., port=..., ssl_context_factory=...)`。uvicorn 对「实例调用失败且非 factory」静默保持实例（0.54 `config.py` L513-518：except TypeError 分支中 `if self.factory:` 为假 → 不 `sys.exit`、`loaded_app` 保持原实例；L519-523 的 else 仅在**调用成功**时告警——Step 4 复审 F-D2 修正行号引用）。
2. **`P054_WORKERS` 强制为 1**：实例直跑无法满足 uvicorn 多 worker 的 import-string 要求。`P054_WORKERS>1` → `SystemExit("P054_WORKERS must be 1; scale containers instead")`。多实例 = 多容器（Q18：N 个无状态 worker）。
3. **TLS factory 改双参签名**：

```python
def tls_context_factory(config=None, default_factory=None) -> ssl.SSLContext:
    """uvicorn 协议：Callable[[Config, Callable[[], SSLContext]], SSLContext]；仍为 top-level 可 pickle。"""
    return build_ssl_context(
        os.environ.get("P054_TLS_CERTFILE"),
        os.environ.get("P054_TLS_KEYFILE"),
        ciphers=os.environ.get("P054_TLS_CIPHERS", DEFAULT_CIPHERS),
        ca_certs=os.environ.get("P054_TLS_CA_CERTS"),
        require_client_cert=os.environ.get("P054_TLS_REQUIRE_CLIENT_CERT") == "1",
    )
```

沿用 env 作为唯一输入源（与 settings 同源），忽略 `config/default_factory` 仅做协议适配。既有 `test_p054_api_auth` 的 `pickle.dumps` 断言仍成立（顶层函数）。

4. **启动探针**（Step 9）：`tests/test_p055_entrypoint.py` 以真实 `uvicorn.Server(Config(app=...))` 在空闲端口起子进程，轮询 `/health/live` 200；TLS 分支用 `ssl._create_unverified_context` 验证握手。这是 P-054「仅 pickle 断言」的补洞。

---

## 3. 接口定义

> 签名即契约；参数默认值不得改变 P-054 既有行为。

### 3.1 trading_worker

```python
def start_threads(
    components: WorkerComponents,
    *,
    stop_event: threading.Event,
    heartbeat: Heartbeat | None = None,
) -> list[threading.Thread]: ...
# 线程: p054-relay / p054-consumer / p054-heartbeat（heartbeat 非空时）

def install_stop_handlers(stop_event: threading.Event) -> None: ...
# signal.signal 注册 SIGINT/SIGTERM/SIGBREAK（存在才注册）→ stop_event.set()

def main(argv: Sequence[str] | None = None) -> None: ...   # 参数: --bus {redis,fake} / --with-market / --once
```

`WorkerComponents` 字段不变；`assemble()` 语义不变（`gateway.start()` 仍由调用方先执行）。

### 3.2 outbox_relay

```python
class RelayLoop:
    def run(self, stop_event: threading.Event | None = None) -> None:
        # while not (stop_event.is_set() if stop_event is not None else self.stop)

class ConsumerLoop:
    def run(
        self,
        stop_event: threading.Event | None = None,
        *,
        autoclaim_every: float = 30.0,
        heartbeat_key: str = "p054:consumer:heartbeat",
        heartbeat_ttl: int = 10,
    ) -> None: ...
```

`ConsumerLoop.run` 行为：

1. 循环 `run_once(count=batch)`；每 `autoclaim_every` 秒以 `autoclaim=True` 跑一次（回收 PEL）。
2. 每轮结束（含 0 条）刷新心跳键：`f"{int(time.time())}:{pending}"`，`pending = bus.stream_pending(consumer)`（`InMemoryBusAdapter` 已有该法）。
3. 异常：`PublisherFailure` 之外一律捕获 + JSON 日志 + `sleep(1.0)`，**不退出**（消费者死掉会导致订单事件永久不扇出）。
4. `stop_event` 置位后最多阻塞 `block_ms=1000` 退出。

`RelayLoop.run` 仅新增可选 `stop_event`，不改重试/背退避逻辑。

### 3.3 market_gateway

```python
def serve(stop_event, *, gateway: MarketGateway, hz: float, bus=None,
          heartbeat_key: str = "p054:market:heartbeat", heartbeat_ttl: int = 10) -> None: ...
def main(argv: Sequence[str] | None = None) -> None: ...      # --once / --embedded / --hz / --symbols / --redis-url
def run_embedded(stop_event: threading.Event | None = None) -> None: ...
```

优先级：CLI > env > 默认（`P054_MARKET_TICK_HZ=2.0`、`P054_MARKET_SYMBOLS=600000.SH`、`P054_REDIS_URL`）。

### 3.4 api_worker

```python
def tls_context_factory(config=None, default_factory=None) -> ssl.SSLContext: ...
def build_heartbeat_reader(settings: ServiceSettings) -> Callable[[], dict[str, bool]]: ...
def main() -> None: ...   # 装配见 §2.8 + §3.6
```

`main()` 装配清单（收敛 G19）：

| 依赖 | 实例 | 用途 |
|------|------|------|
| store | `SqliteLedgerStore(settings.sqlite_path, read_only=True)` | REST/WS 只读 |
| tickets | `RedisTicketStore(redis.Redis.from_url(settings.redis_url))` | 多 worker 共享 ticket |
| publisher | `SyncRedisBus(settings.redis_url)` | `broadcast-pause` 同步发布 |
| heartbeat_reader | `build_heartbeat_reader(settings)`（复用同一个 SyncRedisBus） | `/health/ready` |
| orders_hub / market_hub | `ConnectionHub(orders_max=..., market_max=..., slow_seconds=...)` | WS |
| bus | `AsyncRedisBus(settings.redis_url)` | WS 订阅任务 |

`api_worker` 内同时存在 **sync**（publisher/心跳）与 **async**（订阅）两个 Redis 客户端：前者在 REST `def` 线程池执行，后者在事件循环，职责不混。资源占用可忽略（Q9：自用规模）。

### 3.5 create_app 扩展与 WS 协议

```python
def create_app(
    *,
    settings: ServiceSettings | None = None,
    store=None,
    ticket_store=None,
    metrics: Metrics | None = None,
    publisher=None,
    orders_hub=None,        # ConnectionHub | None
    market_hub=None,        # ConnectionHub | None
    bus=None,               # AsyncRedisBus | None
    heartbeat_reader=None,  # Callable[[], dict[str, bool]] | None
) -> FastAPI: ...
```

全部新增参数默认 `None` → 与本批之前行为等价（零回归硬约束）。

**WS 路由**（新模块 `services/ws_routes.py`）：

```python
@app.websocket("/ws/orders")
async def ws_orders(ws: WebSocket, ticket: str = Query(default=""),
                    resume_last_seq: int = Query(default=0)) -> None
@app.websocket("/ws/market")
async def ws_market(ws: WebSocket, ticket: str = Query(default="")) -> None

def mount_ws(app: FastAPI) -> None
def start_subscribers(app: FastAPI) -> list[asyncio.Task]
async def orders_subscriber(hub, bus, channel) -> None
async def market_subscriber(hub, bus, channel) -> None
async def admin_subscriber(hub, bus, channel) -> None
```

**协议帧**（不改 P-054 语义，仅新增 `market` 包装与 `error` 复用）：

| 方向 | 帧 | 说明 |
|------|----|------|
| S→C | `{"type":"snapshot","seq":N,"recovery_state":"...","degraded":bool,"orders":[...],"positions":[...],"account":{...},"market":{},"resumed_from":N}` | 首帧，必发（`/ws/orders`） |
| S→C | `{"type":"delta","seq":N,"events":[event]}` | 订单增量（Hub 原样） |
| S→C | `{"type":"market","tick":{"symbol","last","ts"}}` | 行情（Hub 裸 tick 包装） |
| S→C | `{"type":"ping"}` / `{"type":"error","code":"slow_consumer",...}` / `{"type":"close","code":N}` | 心跳/背压/关闭 |
| C→S | `{"type":"pong"}` | 心跳应答 |
| C→S | `{"type":"resume","last_seq":N}` | 仅记录（快照始终全量；用于自检日志） |

**未知帧**：忽略并记 debug 日志，不断连（前向兼容）。

**未来拆分触发条件**（U-P055-2 文档化，不实施）：满足任一即重评风控/策略进程化——① 风控需要独立部署/独立扩缩；② 风控与交易需不同语言/运行时；③ 单笔决策 P99 需要跨机隔离；④ 出现第二个消费方（如独立回测服务）需要同步闸门语义。

### 3.6 心跳读取器

```python
def build_heartbeat_reader(settings: ServiceSettings) -> Callable[[], dict[str, bool]]:
    bus = SyncRedisBus(settings.redis_url)

    def _fresh(raw: str | None) -> bool:
        if raw is None:
            return False
        head = raw.split(":", 1)[0]
        try:
            ts = float(head)
        except ValueError:
            return True                      # 非时间戳负载（如 "ok"）→ 以 TTL 存在为准
        return (time.time() - ts) <= settings.ready_staleness_seconds

    def read() -> dict[str, bool]:
        return {
            "trading": _fresh(bus.get_key("p054:trading:heartbeat")),
            "consumer": _fresh(bus.get_key("p054:consumer:heartbeat")),
        }
    return read
```

心跳值格式统一为 `"<unix_ts>:<int>"`（trading 的 `<int>` = outbox 未发送条数；consumer = PEL pending；market 只写 `<unix_ts>`）。`ready_staleness_seconds`（默认 3 s）因此**真正生效**：即使 TTL 10 s 未过期，滞后 >3 s 也判 stale。**实施约束（Step 4 F-D5）**：现 `Heartbeat.run()`（trading_worker.py L120-122）以默认 `value="ok"` 写键 → `_fresh` 解析失败恒 True → staleness 静默失效退化为 TTL 语义；Step 5 B0 必须让 trading 心跳写 `<ts>:<outbox_pending>`（value provider 或调用点传值），并以测试断言键值可被 `_fresh` 解析。

### 3.7 env 矩阵（新增/变更；`ServiceSettings` 之外由入口直读的标注 †）

| 变量 | 默认 | 读方 | 说明 |
|------|------|------|------|
| `P054_REDIS_URL` | `redis://127.0.0.1:6379/0` | 全部 | 必需 |
| `P054_SQLITE_PATH` | `live_ledger.db` | trading/API | Mode S `/app/run/live_ledger.db` |
| `P054_API_KEY` | —（≥16） | API | 必需 |
| `P054_OPERATOR_API_KEY` / `P054_ADMIN_API_KEY` | — | API | 可选 |
| `P054_API_HOST` / `P054_API_PORT` | `127.0.0.1` / `8054` | API | 容器内 `0.0.0.0` |
| `P054_TLS_CERTFILE` / `P054_TLS_KEYFILE` | — | API | 成对；容器/原生均需 |
| `P054_ALLOW_PLAINTEXT_LOOPBACK` | `0` | API | 仅 127.0.0.1 + 明文调试 |
| `P054_WORKERS` † | `1` | API | **必须为 1**（§2.8） |
| `P054_METRICS_REQUIRE_AUTH` | `1` | API | 内网部署设 `0`（U-P055-7） |
| `P054_WS_TICKET_TTL_SECONDS` | `30` | API | ticket 生命周期（model 已有） |
| `P054_WS_ORDERS_QUEUE_MAX` / `P054_WS_MARKET_QUEUE_MAX` | `1000` / `200` | API | Hub 背压（model 已有） |
| `P054_WS_SLOW_CONSUMER_SECONDS` | `5.0` | API | 1013 阈值（model 已有） |
| `P054_WS_SNAPSHOT_ORDERS_LIMIT` | `200` | API | 快照条数（model 已有） |
| `P054_READY_STALENESS_SECONDS` | `3.0` | API | 心跳滞后判 stale（model 已有） |
| `P054_HEARTBEAT_INTERVAL_SECONDS` / `P054_HEARTBEAT_TTL_SECONDS` | `1.0` / `10` | trading（直读）/ API（model） | 心跳节奏；**trading 无 `ServiceSettings`，直读同名 env** |
| `P054_OUTBOX_POLL_INTERVAL_SECONDS` / `P054_OUTBOX_BATCH_SIZE` | `0.2` / `100` | trading | relay/consumer 节奏（model 已有） |
| `P054_CONSUMER_NAME` / `P054_CONSUMER_GROUP` / `P054_AUTOCLAIM_IDLE_MS` | `trading-1` / `p054-relay` / `60000` | trading | 消费者身份（model 已有） |
| `P054_ORDERS_STREAM_KEY` / `P054_ORDERS_CHANNEL` / `P054_MARKET_CHANNEL` / `P054_ADMIN_CHANNEL` | `p054:orders` / `p054:orders:events` / `p054:market` / `p054:admin` | 全部 | 键名（model 已有） |
| `P054_MARKET_SOURCE` / `P054_MARKET_TICK_HZ` / `P054_MARKET_SYMBOLS` | `synthetic` / `2.0` / 空 | market | 行情（model 已有；`--symbols`/`--hz` CLI 覆盖） |
| `P054_MARKET_HEARTBEAT_TTL_SECONDS` † | `10` | market | **新增**（入口直读，不进 model） |
| `P054_POLL_SECONDS` † | `0.2` | trading | **新增**主循环粒度（入口直读） |
| `P054_PATROL_SECONDS` † | `6.0` | trading | **新增**巡检节奏（入口直读） |
| `P054_ORDER_CSV` † | `orders.csv` | trading | 半自动通道（P-054 已有） |

> `ServiceSettings` 是 `extra="forbid"` 且按 `model_fields` 读 env（[config.py#L74-L86](../services/config.py#L74-L86)），**新增字段必须同时改 model**（本批仅 `ws_*`/`heartbeat_*`/`ready_*` 等**已存在**，无需扩字段；标 † 的多为新增、由入口直读，不进 model——沿用 P-054 F-A3「无 api_key 依赖」约定）。`P054_TLS_CIPHERS`/`P054_TLS_CA_CERTS`/`P054_TLS_REQUIRE_CLIENT_CERT` 在 model 中已有，但 `tls_context_factory` 按 uvicorn 协议直读 env（与 settings 同源，值必须一致）。

---

## 4. 部署编排

### 4.1 资产清单

`deploy/compose.services.yaml`（运行态）· `deploy/certs/`（自签，gitignore）· `deploy/prometheus.yml`（可选）· `.env.services.example` · `Dockerfile#services` · `docs/RUNBOOK_p055_deployment.md`。

### 4.2 compose 服务矩阵（设计稿）

```yaml
name: p055
x-runtime: &runtime
  build: {context: .., dockerfile: Dockerfile, target: services}
  image: factor-trading-services:p055
  restart: unless-stopped
  init: true
  stop_grace_period: 10s
  env_file: [../.env.services]
  depends_on:
    redis: {condition: service_healthy}

services:
  redis:
    image: redis:7
    command: ["redis-server", "--appendonly", "yes"]
    volumes: ["redis-data:/data"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    # 不发布端口；宿主需调试时临时 -p 127.0.0.1:6379:6379

  trading:
    <<: *runtime
    command: ["python", "-m", "services.trading_worker"]
    volumes: ["p055-data:/app/run"]
    environment:
      P054_SQLITE_PATH: /app/run/live_ledger.db
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import os,redis,sys;sys.exit(0 if redis.Redis.from_url(os.environ['P054_REDIS_URL']).get('p054:trading:heartbeat') else 1)\""]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 20s

  market:
    <<: *runtime
    command: ["python", "-m", "services.market_gateway"]
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import os,redis,sys;sys.exit(0 if redis.Redis.from_url(os.environ['P054_REDIS_URL']).get('p054:market:heartbeat') else 1)\""]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 20s

  api:
    <<: *runtime
    command: ["python", "-m", "services.api_worker"]
    depends_on:
      redis: {condition: service_healthy}
      trading: {condition: service_healthy}
    volumes:
      - "p055-data:/app/run"          # 读写挂载；应用层 read_only=True + mode=ro/query_only
      - "../deploy/certs:/certs:ro"
    ports: ["127.0.0.1:8054:8054"]    # 仅本机暴露
    environment:
      P054_SQLITE_PATH: /app/run/live_ledger.db
      P054_API_HOST: 0.0.0.0
      P054_TLS_CERTFILE: /certs/cert.pem
      P054_TLS_KEYFILE: /certs/key.pem
      P054_METRICS_REQUIRE_AUTH: "0"  # U-P055-7
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import ssl,urllib.request,sys;ctx=ssl._create_unverified_context();sys.exit(0 if urllib.request.urlopen('https://127.0.0.1:8054/health/live',context=ctx,timeout=3).status==200 else 1)\""]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 20s

  prometheus:                         # 可选：--profile obs
    image: prom/prometheus:latest
    profiles: ["obs"]
    volumes: ["../deploy/prometheus.yml:/etc/prometheus/prometheus.yml:ro"]
    ports: ["127.0.0.1:9090:9090"]

volumes:
  p055-data:
  redis-data:
```

设计取舍：

1. **TLS 是 Mode S 默认**：容器内必须绑 `0.0.0.0`，而 `allow_plaintext_loopback` 校验强制明文仅限 `127.0.0.1`（[config.py#L66-L72](../services/config.py#L66-L72)）。Docker Desktop(Windows) 的 port publish 落到容器 eth0，容器内绑 loopback 宿主不可达 → 只能 TLS（自签证书 + 健康检查忽略校验）。
2. **`depends_on: service_healthy`**：避免 API 在 trading 未写 `recovery_state` 时把 503 当故障刷屏。
3. **`init: true`**：容器内 PID 1 正确转发 SIGTERM 给 Python（若直接 `python -m` 则 PID 1 即 Python，Python 自注册 handler 已足够；`init` 用于兜底僵尸回收）。
4. **named volume**：`p055-data` 由镜像内 `/app/run` 初始化属主（§4.3），非 root（uid 10001）可写；`redis-data` 存 AOF。
5. **api 与 trading 共享同一卷**：只读约束由应用层保证（`read_only=True` + `mode=ro` + `query_only=ON`，[ledger_store.py#L191-L201](../live/ledger_store.py#L191-L201)），**不是**靠容器 `:ro` 挂载（容器级只读会让 WAL 的 `-shm` 映射失败）。

### 4.3 Dockerfile `services` target

```dockerfile
FROM python:3.11-slim AS services
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
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

- 只装 `.[services]`（不含 `[dev]`），镜像不携带 pytest。
- 非 root（uid 10001）运行；`/app/run` 属主正确 → named volume 首次初始化可写。
- 不 `EXPOSE`（端口由 compose 决定）。
- 既有回测/测试 stage 不动。

### 4.4 Mode R 进程管理（U-P055-8）

**主选 NSSM**（能发 `CTRL_C_EVENT` → Python `SIGINT` → `stop_event`）：

```bat
nssm install P055Trading "F:\Coding\Factor_Trading_v3.0\.venv\Scripts\python.exe" "-m services.trading_worker"
nssm set P055Trading AppDirectory "F:\Coding\Factor_Trading_v3.0"
nssm set P055Trading AppEnvironmentExtra P054_SQLITE_PATH=F:\Coding\Factor_Trading_v3.0\live_ledger.db P054_REDIS_URL=redis://127.0.0.1:6379/0
nssm set P055Trading AppStdout "F:\Coding\Factor_Trading_v3.0\logs\trading.out.log"
nssm set P055Trading AppStderr "F:\Coding\Factor_Trading_v3.0\logs\trading.err.log"
nssm set P055Trading AppStopMethodConsole 15000
nssm set P055Trading AppRotateFiles 1
nssm start P055Trading
```

`P055Api` / `P055Market` 同构（command 与 env 不同）。Redis：

```bat
docker run -d --name p055-redis -p 127.0.0.1:6379:6379 -v p055-redis:/data redis:7 redis-server --appendonly yes
```

**回退（任务计划）**——文档化，不作默认：

```powershell
$action  = New-ScheduledTaskAction -Execute "F:\...\.venv\Scripts\python.exe" `
           -Argument "-m services.trading_worker" -WorkingDirectory "F:\Coding\Factor_Trading_v3.0"
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName P055Trading -Action $action -Trigger $trigger -RunLevel Highest
```

差异：任务计划停止时通常直接 `TerminateProcess`（等价 SIGKILL），**不保证** `finally` 清理 → 仅作降级；runbook 写明「停机前先手动 `stop_event` 探针或用 `Stop-Process` 前的 `CTRL_BREAK`」。

### 4.5 观测最小栈（U-P055-5 / U-P055-7）

| 组件 | 落点 | 备注 |
|------|------|------|
| 结构化日志 | 三进程 stdout（JSON 行，`json_log`） | `docker logs` / NSSM `AppStdout`；不打轮转由宿主负责 |
| Prometheus 指标 | API `/metrics`（现有 13 个指标族：HTTP/WS/订单/outbox/PEL/就绪/延迟/行情丢弃，[metrics.py#L36-L58](../services/metrics.py#L36-L58)，Step 4 F-D3 更正计数） | `P054_METRICS_REQUIRE_AUTH=0`；端口仅 127.0.0.1 |
| 进程存活 | Redis 心跳键（`p054:trading:heartbeat`、`p054:consumer:heartbeat`、`p054:market:heartbeat`） | compose healthcheck / 外部脚本读取 |
| 可选抓取 | `deploy/prometheus.yml` + `--profile obs` | `scheme: https` + `tls_config: {insecure_skip_verify: true}` |
| 不引入 | Grafana / OTEL / node_exporter / trading 指标端口 | 理由：Q9 自用规模；新增端口=新增鉴权面 |

**代价**：trading/consumer 的 `outbox_pending`/`PEL pending` 不能直接抓取，只能从心跳值（`ts:pending`）与基准报告读取；若未来需要趋势图，再评估给 trading 加只读 `/metrics` 端口（登记为 §13 U-D5 触发条件）。

### 4.6 备份与恢复（写入 runbook）

- 备份：`sqlite3 live_ledger.db ".backup 'backups/ledger-YYYYmmdd.db'"`（在线备份，WAL 安全）；每日一次 + 变更前一次。
- 恢复：先停 `P055Trading`（或 compose `stop trading api`）→ 替换 DB → 启动；启动恢复走 `gateway.start()`（`recovery_state`）。
- 卷备份：named volume 需 `docker run --rm -v p055-data:/d -v ${PWD}:/b alpine tar czf /b/p055-data.tgz -C /d .`，必须停 trading。

---

## 5. 依赖方向门禁（U-P055-3）

### 5.1 三契约定义

| # | 契约类型 | 允许/禁止 | 对应总纲 |
|---|----------|-----------|----------|
| C1 | `layers` | 上层可依赖下层：`services > live > strategies > core` | §6 L286 允许边 |
| C2 | `forbidden` | `core` **不得** import `live` / `services` / `strategies` | §6 L286 禁止 `core→*` |
| C3 | `forbidden` | `services.api` / `services.api_worker` / `services.ws_hub` / `services.market_gateway` **不得** import `live.gateway` / `live.orders` / `live.channel` / `live.ledger` | §6「services 禁含交易逻辑」 |
| C4 | 负例 fixture | 故意 `core→upper` 违规，断言 `lint-imports` 非 0 | 门禁可证伪 |

**组合根例外**：`services.trading_worker` **不在** C3 的 `source_modules` 中——它必须装配 `live.gateway/ledger/adapters`（[trading_worker.py#L56-L61](../services/trading_worker.py#L56-L61)）。这是显式、单点的例外，写入 §10 I8。

### 5.2 配置落点（`pyproject.toml`）

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
allow_indirect_imports = true     # Step 9 校准：只禁直接导入（读路径经 live.ledger_store 属数据层）
source_modules = ["services.api", "services.api_worker", "services.ws_routes", "services.ws_hub", "services.market_gateway"]
forbidden_modules = ["live.gateway", "live.orders", "live.channel", "live.ledger"]
```

依赖新增：`[project.optional-dependencies].dev` 加 `import-linter`（2.x），并 `uv lock` 同步 [uv.lock](../uv.lock)（CI `lock-check` 会校验）。

### 5.3 CI `arch-check`（Linux，不依赖 Windows）

```yaml
  arch-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install ".[dev,services]"
      - run: lint-imports          # 精确入口见 U-D2
```

本地 gate（[spec_runner_adapter.py#L63-L68](../scripts/spec_runner_adapter.py#L63-L68)）追加：

```python
"arch-check": f"{_PY312} -m importlinter.cli lint-imports",
```

（精确命令形态 Step 9 以 `--help` 校准，见 §13 U-D2；未校准前不写死到文档读数。）

### 5.4 负例 fixture

```
tests/fixtures/arch_violation/
├── .importlinter            # root_packages = ["violation_app"]; layers = ["upper","core"]
└── violation_app/
    ├── __init__.py
    ├── core.py              # from violation_app.upper import helper   ← 违规
    └── upper.py
```

`tests/test_p055_arch_gate.py`：

1. `test_repo_contracts_pass` → 在仓库根跑 `lint-imports`，断言 exit 0。
2. `test_negative_fixture_fails` → `cwd=tests/fixtures/arch_violation`，断言 exit ≠ 0，且 stdout 含 `violation_app.core`。
3. `test_three_contracts_declared` → 解析 `pyproject.toml`，断言 `tool.importlinter.contracts` 长度 ≥3 且名字含 C1/C2/C3 关键词（防止「删契约保绿」）。

`shutil.which("lint-imports")` 为 `None` 时**直接失败**（依赖缺失即环境错误），不 skip（RULE-3：禁止环境条件 skip）。

### 5.5 盲区与护栏

| 盲区 | 影响 | 护栏 |
|------|------|------|
| 字符串动态导入（`importlib`） | 静态分析看不到 | §5.2 `include_external_packages=false` + 代码评审清单标注「动态导入必须写注释说明归属层」 |
| 函数内延迟导入 | import-linter 2.x 默认**计入** | 已知 C3 会看到 `api._load_store → live.ledger_store`（合法，不在 forbidden 列表）；**Step 9 校准**：`forbidden` 默认连间接导入一并禁止（`api→ledger_store→ledger/orders` 会误红），故 C3 设 `allow_indirect_imports = true` 只约束直接导入 |
| `TYPE_CHECKING` 导入 | 可能被算作依赖 | 暂不豁免；若误报再开 `exclude_type_checking_imports`（U-D2 一并校准） |
| 测试目录不在契约内 | `tests/` 可自由 import | 不作为门禁对象（测试本就要跨层造场景） |

---

## 6. 跨进程基准（`scripts/p055_bench_e2e.py`）

### 6.1 四段口径与进程边界

| 段 | 起 | 止 | 测量进程 | 数据来源 |
|----|----|----|----------|----------|
| T1 submit→commit | `gateway.submit()` 进入 | outbox 行 `created_ts` | harness（writer 进程） | harness 内存 `submit_ts` + `created_ts` |
| T2 commit→stream | `created_ts` | `sent_ts`（`mark_sent` 在 XADD 返回后写） | harness | SQLite `outbox.created_ts/sent_ts`（[ledger_store.py#L31-L42](../live/ledger_store.py#L31-L42)） |
| T3 stream→fanout | `sent_ts` | consumer `PUBLISH` 返回前打点 | harness | consumer 侧 publish 前 `time.time()` 写 `--publish-log` |
| T4 fanout→client | publish 打点 | client 收到同 seq | **独立 client 进程** | client 写 `--recv-log`，离线按 seq join |

**进程边界**：harness = 生产同构的 writer 进程（gateway+relay+consumer 三线程）；client 是**另一个进程**，通过真实 Redis Pub/Sub（或可选 WS）接收。T1-T3 与生产同代码路径、同真实 Redis/SQLite；T4 跨真实进程边界（含序列化/网络/调度）。3 进程全编排（含真实 `api_worker` 与 WS 握手）列为可选 `--with-api`，**默认不做**（U-D1）。

**零改动约束**：不为基准修改 `services/*`；publish 打点只在脚本的 consumer 子类或脚本自带 relay/consumer 实例外记录（脚本内构造 `ConsumerLoop` 并在其前后打点即可，无需改类）。

### 6.2 脚本接口

```bash
# 端到端（自动拉起 client 子进程并汇总）
python scripts/p055_bench_e2e.py run \
  --n 1000 --redis-url redis://127.0.0.1:6379/0 \
  --sqlite-path .bench/bench.db --out .bench/report.md --json .bench/report.json

# 两轮口径（1k / 10k）
python scripts/p055_bench_e2e.py run --n 10000 ...

# 可选：全链路（API worker + WS）
python scripts/p055_bench_e2e.py run --n 1000 --mode ws --with-api

# 可选阈值（默认不启用）
python scripts/p055_bench_e2e.py run --n 1000 --assert-p99 200
```

输出（`report.md` + `report.json`）：

```json
{
  "env": {"os": "...", "cpu": "...", "python": "3.11.x", "redis": "7.x"},
  "rounds": [{"n": 1000, "segments": {"T1": {"p50":0, "p95":0, "p99":0},
                                       "T2": {}, "T3": {}, "T4": {}},
              "dropped": 0, "pending_after": 0, "unsent_after": 0,
              "ws_seq_continuous": true}]
}
```

`--sqlite-path` 必须指向**临时目录**（`.bench/`，gitignore），跑完不污染 `live_ledger.db`。

### 6.3 判读与 CI 策略（U-P055-4 已裁）

| 规则 | 内容 |
|------|------|
| 报告制 | 结论文档记录：环境、两轮 p50/p95/p99、`dropped=0`、`pending_after=0`、`unsent_after=0` |
| CI | **不跑** bench（CI 无稳定 Redis/时钟），不设 SLO；`--assert-p99` 仅本地/发布前手动作业 |
| 判读 | ① T4 p99 与 P-054 进程内基准同量级（不得劣化一个数量级）；② 任何 `dropped>0` 或 `pending_after>0` 判失败；③ WS 模式下 seq 必须连续单调 |
| 周期 | 每批发布前手跑 1k+10k；nightly 可选非阻塞（U-D1） |

---

## 7. 关键决策表（决策 + 被拒替代 + 理由 + 代价）

> Step 3 硬约束：每个关键决策必须有「被拒替代 / 拒绝理由 / 代价或回退点」；证据出口即本表 + §2.5。

| # | 决策 | 选定 | 被拒替代 | 拒绝理由 | 代价 / 回退点 |
|---|------|------|----------|----------|---------------|
| D1 | 部署形态 | 4 类进程 + Redis（Mode S/R） | 六网络服务全拆 | 单团队/3 s 每笔/WAL 同机；网络化只增 RPC 失败面 | 无自动扩缩容；回退点 = 减容器 |
| D2 | 策略/风控位置 | 库内调用（交易进程内） | 独立风控 RPC | 同步闸门遇网络超时即放大为交易停顿 | 拆分需改调用点（§3.5 触发条件） |
| D3 | SQLite 卷 | named volume（S）/ NTFS（R） | Windows→WSL bind mount | WAL 跨挂载文件锁不可靠（E4/S20） | 跨机读走内部 API（仅文档） |
| D4 | API 容器绑定 | `0.0.0.0` + TLS 自签 | 明文 0.0.0.0 / 宿主网络 | validator 禁止明文非 loopback；宿主网络在 Docker Desktop 不可靠 | 证书 30 天轮换（runbook） |
| D5 | 入口修复（G18） | 去 `factory=True`，`WORKERS=1` | import string + 零参 `create_app_from_env` | 需重新装配 store/tickets/hubs，重复装配逻辑且默认 key 不安全 | 多实例靠容器数；回退点 = 改 import string |
| D6 | TLS 适配 | 双参签名（忽略入参，读 env） | 用 `default_factory()` 返回值 | 默认 factory 不加载业务证书，等于放弃 TLS 配置 | 单函数改动，易回退 |
| D7 | WS 结构 | **两个** `ConnectionHub`（orders/market） | 单 Hub 双端点 | `next_frame` orders 优先 → 行情帧串订单连接；`paused` 只属行情 | 内存翻倍（可忽略）；回退点 = 合并需改 `next_frame` |
| D8 | WS 鉴权顺序 | 先 accept → 验 ticket → error 帧 + close 4401 | accept 前 close 传自定义码 | ASGI 只能回 HTTP 403，拿不到 4401 | 握手后 1 帧即断；客户端需按 4401 处理 |
| D9 | WS 发送模型 | 单协程帧泵 + 20 ms 轮询 + `receive_json` 超时 | 每连接双任务（sender/receiver） | 双任务需跨任务唤醒/取消配对，复杂且易漏清理 | ≤20 ms 附加延迟；回退点 = 加 Hub 通知事件 |
| D10 | readiness | 注入 `heartbeat_reader`（sync Redis） | 在 API 内用 async 客户端读 | `def` 端点不能 await；async 读取会让 11 个 REST 端点都变 async | API worker 多一个 sync 连接；回退点 = 合并为 async 全栈 |
| D11 | trading 主循环 | `stop_event.wait(0.2)` + 6 s 巡检 | `time.sleep(0.2)` / 保持忙等 | sleep 不可即时唤醒；忙等 100% CPU（G4） | 轮询粒度 0.2 s（P-054 IMPL 0.5 s 的更紧版本） |
| D12 | market 循环 | `serve()` + 心跳键 + signal | 仅 `run_once` 重试 | 无心跳则 healthcheck 无依据 | 多一个 TTL 键 |
| D13 | 门禁形态 | 3 契约 + 负例 + 契约数守护 | 只写 1 个 layers 契约 | 单契约漏掉「api 含交易逻辑」与方向反转 | 新增 dev 依赖；回退点 = 删 job |
| D14 | 基准进程边界 | harness（writer）+ client 双进程 | 单进程 FakeBus / 三进程全编排 | FakeBus 不测真实 Redis；三进程编排成本高且易脆 | T1-T3 同进程（生产同构）；全链路灯 U-D1 |

---

## 8. 数据结构

| 结构 | 定义 | 落点 |
|------|------|------|
| 心跳值 | `"<unix_ts>:<int>"`（trading=outbox 未发送；consumer=PEL pending）；market=`"<unix_ts>"` | Redis TTL 键 |
| WS 快照帧 | `hub.snapshot()` 现有 dict（含 `market:{}`） | 未改 |
| WS 增量帧 | `{"type":"delta","seq":N,"events":[event]}` | 未改（Hub 产出） |
| WS 行情帧 | `{"type":"market","tick":{"symbol","last","ts"}}` | ws_routes 包装 |
| 错误帧 | `{"type":"error","code":str,"message":str}` | 现有 `ErrorCode` |
| 基准 publish 打点 | `{"seq":N,"ts":float}` JSONL | `--publish-log` |
| 基准 recv 打点 | `{"seq":N,"ts":float}` JSONL | `--recv-log` |
| 负例契约配置 | `.importlinter`（fixture 内） | `tests/fixtures/arch_violation/` |

---

## 9. 错误处理与降级链

| 场景 | 检测 | 行为 | 降级链 |
|------|------|------|--------|
| Redis 不可用（trading） | relay `PublisherFailure` / heartbeat 写入异常 | 背退避重试；主循环不退出；heartbeat 键过期 → API 503 | L1 重试 → L2 503 摘流 → L3 runbook 重启 |
| Redis 不可用（API 订阅） | 订阅任务异常 | 退避 1 s 重连；REST 仍可读；WS 无增量 | L1 重连 → L2 客户端重连拿快照 |
| SQLite 写失败（trading） | `SqliteLedgerStore` 抛错 | 进程退出（单写者不可降级）；容器/服务重启 | L1 重启 → L2 恢复 `recovery_state` |
| SQLite 只读打开失败（API） | `_open_read_only` 抛 `ServiceError` | `/health/ready` 503 `db_uninitialized` | L1 等 trading 建库 → L2 runbook |
| recovery 未完成 | `meta.recovery_state` | 503 `recovery_incomplete` | trading `gateway.start()` 完成后自动放行 |
| 心跳滞后 | `ready_staleness_seconds` | 503 `stale_trading`/`stale_consumer` | L1 等心跳恢复 → L2 查进程 |
| ticket 过期/重复 | `consume()` 假 | WS error 帧 + close 4401 | 客户端重新 `POST /api/ws-ticket` |
| 慢消费者 | Hub 队满超 5 s | close 1013（先发 error 帧） | 客户端重连拿全量快照 |
| pong 超时 | `hub.heartbeat` >30 s | close 1011 | 客户端重连 |
| WS 未知帧 | 解析成功但 type 未知 | debug 日志，忽略 | 无 |
| 巡检异常 | `gateway.reconcile` 抛错 | JSON 日志 `patrol_failed`，下轮重试 | 不降级（对账失败不阻断交易） |
| 容器 SIGTERM 超时 | compose `stop_grace_period` 10 s | Docker SIGKILL | runbook 检查 join 卡点 |

---

## 10. 不变式

| ID | 不变式 | 守护方式 |
|----|--------|----------|
| I1 | 同一 SQLite 文件**只有一个写连接**（trading 进程） | `SqliteLedgerStore` `.lock` + 代码评审 + 部署拓扑 |
| I2 | API worker 的 store `read_only=True`（`mode=ro` + `query_only=ON`） | `test_p055_runtime` 断言 `store.is_read_only()` |
| I3 | WS 首帧必为 snapshot；delta 的 seq 严格递增 | `test_p055_ws` 握手用例 |
| I4 | ticket 一次性（consume 后不可复用） | `RedisTicketStore` + 用例 |
| I5 | 心跳缺失/滞后 ⇒ `/health/ready` 503，绝不 200 | `evaluate_readiness` 用例 |
| I6 | SIGTERM/SIGINT 后 ≤10 s 退出，outbox 无未发送丢失 | 停机探针：先停 relay 再 shutdown |
| I7 | 3 个 import-linter 契约常绿 | CI `arch-check` |
| I8 | 仅 `services.trading_worker` 可 import `live.gateway/ledger/adapters`（组合根单点例外） | C3 契约 + 评审清单 |
| I9 | `core` 不 import 任何上层 | C2 契约 |
| I10 | SQLite 不得跨 Windows/WSL 挂载 | compose 无 bind mount + runbook 红线 |
| I11 | `/metrics` 不暴露到非内网地址 | 端口 `127.0.0.1` 发布 + `P054_METRICS_REQUIRE_AUTH=0` 仅内网 |
| I12 | 基准不因环境抖动判红（除非显式 `--assert-p99`） | §6.3 |

---

## 11. 验收读数（Step 9/10 回填）

| # | 读数 | 基线（P-054 关闭） | P-055 目标 |
|---|------|-------------------|-----------|
| 1 | pytest | 1420 passed | ≥1420 + 新增用例，**零回归** |
| 2 | golden | 22 零重录 | 22 零重录 |
| 3 | `-k p054` | 120 | ≥120（不改既有断言） |
| 4 | mypy | 157 files · 0 | 157 + 新增（`services/ws_routes.py`、`scripts/p055_bench_e2e.py`）· 0 → **实测 159 · 0** |
| 5 | black | 309 unchanged | 309 + 新增文件已格式化 → **实测 319** |
| 6 | 计数 | tests 151 / core 51 / live 19 / services 12 | tests **≥156**（151+5 新文件，Step 8 与 IMPL/CHECKLIST 统一） / core 51 / live 19 / services **13** |
| 7 | `lint-imports` | 无 | 3 契约 exit **0**；负例 exit **≠0** |
| 8 | api_worker 真实启动 | 未验证（仅 pickle） | 子进程 uvicorn → `/health/live` **200**；TLS 握手成功 |
| 9 | WS 握手 | 0 端点 | `/ws/orders` 有效 ticket → snapshot seq 单调；无 ticket → **4401**；未就绪 → **4503** |
| 10 | 主循环 CPU | 忙等（>90% 单核） | idle 30 s 平均 **<5%** 单核 → **实测 0.00%**（Step 10，`GetProcessTimes` 采样真实进程含三守护线程） |
| 11 | 心跳/readiness | stale 永不 503 | 键存在 → 200；删键 → **503 `stale_*`** → **实测 200 `{"status":"ok","degraded":false}` / 503 `["stale_trading","stale_consumer"]`**（Step 10，停 writer 后删键） |
| 12 | 跨进程基准 | 仅进程内 | 1k/10k 四段 p50/p95/p99；`dropped=0`、`pending_after=0`、`unsent_after=0` → **实测双轮三零**（真实 Redis + 双进程：1k T4 p50 1.21/p95 2.17/p99 2.66 ms；10k T4 p50 1.22/p95 2.23/p99 2.98 ms；Step 10） |
| 13 | 部署静态校验 | compose 仅回测 | `docker compose -f deploy/compose.services.yaml config -q` 通过 |
| 14 | `uv lock --check` | 通过 | 通过（`import-linter` 已入 lock） |
| 15 | 结构守卫 | — | `core/*` 51 零 diff；`live/*` 零 diff（与 §15 结构守卫统一表述，Step 4 F-D4 修正） |

---

## 12. 风险与缓解

| # | 风险 | 概率/影响 | 缓解 |
|---|------|-----------|------|
| R1 | named volume 属主错误 → trading 写失败 | 中/高 | Dockerfile 显式 `chown /app/run`；compose 首启探针断言可写 |
| R2 | 自签证书 30 天过期 → API 健康检查全红 | 高/中 | runbook 轮换命令 + `start_period`；错误信息写清证书路径 |
| R3 | 20 ms 帧泵在连接数多时 CPU 上升 | 低/中 | Q9 自用规模（≤10 连接）；触发条件：>50 连接再改事件通知 |
| R4 | import-linter 对延迟导入误报 | 中/中 | `ignore_imports` 精确豁免 + 注释；U-D2 校准 |
| R5 | api_worker 双 Redis 客户端连接数翻倍 | 低/低 | 每 worker 2 连接；Redis `maxclients` 默认 10000 |
| R6 | Windows 信号语义差异（任务计划直接 kill） | 中/中 | NSSM 主选；runbook 写明 `AppStopMethodConsole` |
| R7 | 多容器共享 SQLite 但 API 误写 | 低/高 | I2 用例 + `query_only=ON`（SQLite 级拒写） |
| R8 | benchmark 受机器负载影响波动 | 高/低 | 报告环境与两轮读数；不设 CI SLO（U-P055-4） |

---

## 13. 未决项（四元块）

| ID | 判据（何时必须定） | 触发 | 当前倾向 | 证据 |
|----|-------------------|------|----------|------|
| **U-D1** | 需要「API+WS 真实进程全链路」读数时 | 发布前人工 / nightly | 本轮不做；保留 `--with-api` 升降级开关 | E0（脚本站位）+ E2（Step 9 实测） |
| **U-D2** | `lint-imports` 精确入口/`--config` 支持性 | Step 9 首次运行 | 优先 `python -m importlinter.cli lint-imports`；不支持则回落 `lint-imports` 可执行文件；fixture 用 `.importlinter` INI | E1（uvicorn/依赖实测）+ E2 |
| **U-D3** | 证书是否需无人值守轮换 | 证书 ≥2 次过期或需 CI 部署 | 暂用 runbook 手动 openssl；不引入 mkcert/step-ca | E0 |
| **U-D4** | 跨机只读回退是否需要实现 | 出现第二台机器读账本 | 仅文档化（Q19）；不建 Redis 读模型 | E4（Q19 裁决） |
| **U-D5** | trading 是否需要可抓取指标端口 | 需要 pending 趋势图/告警 | 暂不新增端口；心跳值携带 pending 兜底 | E0 |

---

## 14. ADR-0010 三问（新增面）

> 三问：① 是否真被用到（激活条件）？② 放哪层（Layer-0 文档 / Layer-1 代码 / Layer-2 基础设施）？③ 未激活时副作用是否为 0？

| 新增面 | ① 激活条件 | ② 层级 | ③ 未激活副作用 |
|--------|-----------|--------|----------------|
| `services/ws_routes.py` + WS 路由 | `create_app` 传入 `orders_hub/market_hub`（仅 `api_worker.main`） | Layer-1 代码 | 0：参数为 None 时不挂路由/不启任务 |
| 订阅任务（orders/market/admin） | `bus` 非 None | Layer-1 代码 | 0：不创建 asyncio task |
| `heartbeat_reader` | `api_worker` 注入 | Layer-1 代码 | 0：None 时行为与 P-054 一致 |
| market 心跳键 | `serve()` 心跳参数非 None | Layer-1 代码 | 0：`run_once`/测试不写键 |
| consumer 心跳 + `ConsumerLoop.run` | `start_threads(heartbeat=...)` | Layer-1 代码 | 0：既有 `run_once` 测试不变 |
| `--bus fake` / `--with-market` / `--once` | 显式 CLI 参数 | Layer-1 代码 | 0：默认值 = 生产路径 |
| `deploy/` 全部资产 | `docker compose -f ... up` | Layer-2 基础设施 | 0：不参与 pytest/mypy |
| `import-linter` 依赖 + 配置 + job | CI 或本地 `arch-check` | Layer-1（依赖）/ Layer-0（配置） | 0：运行时零 import |
| `scripts/p055_bench_e2e.py` | 手动执行 | Layer-1 脚本（不进生产镜像） | 0：不被任何生产模块 import |
| `tests/fixtures/arch_violation/` | 仅在负例用例 cwd 下被扫描 | Layer-1 测试资产 | 0：不在 `root_packages` 内 |

---

## 15. 对 Step 5（实施）的输入

**建议顺序（B0 → B3）**：

| 阶段 | 任务 | 文件 |
|------|------|------|
| **B0 运行时** | trading：signal + 三线程 + 主循环 + 巡检；relay/consumer `run`；market：`serve` + 心跳 + argparse | `services/trading_worker.py`、`services/outbox_relay.py`、`services/market_gateway.py` |
| **B0 入口** | G18：去 factory、TLS 双参、`WORKERS=1` 校验、装配 tickets/hubs/bus/reader | `services/api_worker.py` |
| **B1 WS** | `ws_routes.py`；`create_app` 扩展 + lifespan；`health_ready` 接心跳 | `services/ws_routes.py`、`services/api.py` |
| **B2 门禁** | `[tool.importlinter]` + dev 依赖 + `uv lock` + CI job + gate 表 + 负例与用例 | `pyproject.toml`、`uv.lock`、`tests.yml`、`spec_runner_adapter.py`、`tests/fixtures/arch_violation/`、`tests/test_p055_arch_gate.py` |
| **B2 部署** | `services` target、compose、env 样例、prometheus profile、静态断言用例 | `Dockerfile`、`deploy/*`、`.env.services.example`、`tests/test_p055_deploy_assets.py` |
| **B3 基准** | `p055_bench_e2e.py`（run/client/report）+ 两轮读数 | `scripts/p055_bench_e2e.py` |
| **B3 运维** | runbook（启停/备份/证书/排查/跨机回退） | `docs/RUNBOOK_p055_deployment.md` |

**测试清单**（新增，均不依赖环境条件 skip）：

- `test_p055_runtime.py`：信号置位后线程退出 ≤5 s；consumer 心跳键含 `ts:pending`；`stop_event.wait` 路径不 busy-loop（以 Fake 时钟计数）；`--bus fake` 装配；**trading 心跳键值可被 `_fresh` 解析（Step4 F-D5）**；**停机收尾调用 `heartbeat.stop()`（Step4 F-D6）**。
- `test_p055_ws.py`：TestClient `websocket_connect` → snapshot 首帧；无 ticket → 4401；store 未就绪 → 4503；慢消费者 → 1013（注入小 `orders_max` + `slow_seconds`）；行情帧包装。
- `test_p055_arch_gate.py`：§5.4 三例。
- `test_p055_entrypoint.py`：真实 uvicorn 子进程 `/health/live` 200（TLS 与明文 loopback 两分支）。
- `test_p055_deploy_assets.py`：compose 含 `redis/trading/api/market`、`service_healthy`、`p055-data`、`USER` 非 root（读 Dockerfile 文本）、`P054_METRICS_REQUIRE_AUTH: "0"`。

**结构守卫**：`core/*` 零 diff；`live/*` 零 diff；只改 `services/*` + `scripts/*` + `tests/*` + `docs/*` + 部署/配置。

---

## 16. 状态链

- **2026-11-23**：Step 3 DESIGN 落盘。继承 A/A/A/A 与 Q17-Q20；定稿 U-P055-3（3 契约 + 负例）/ U-P055-5（最小观测栈）/ U-P055-7（内网免鉴权）/ U-P055-8（NSSM）；形成 D1-D14 决策表（含被拒替代与代价）、I1-I12 不变式、U-D1..D5 未决项四元块、ADR-0010 三问。
- **2026-11-23**：**Step 4 异构复审 PASS**（[REVIEW_p055_step4_design](REVIEW_p055_step4_design.md)，GLM-5.3-Flash ≠ 作者）：29 项引用对码 0 幻觉（uvicorn 0.54.0 实装 / 双 Hub 参数 / 三通道发布形状 / env 矩阵 / compose 合并语义全实证）；**P2×6 已回写本文档**——F-D1 C3 契约补 `services.ws_routes`（§5.2）、F-D2 uvicorn 行号引用修正（§2.8，回退路径在 L513-518 except 分支）、F-D3 metrics 13 个指标族（§4.5）、F-D4 读数 15 统一「live/* 零 diff」（§11）、F-D5 心跳值 `<ts>:<pending>` 实施约束（§2.6.1/§3.6/§15）、F-D6 收尾补 `heartbeat.stop()`（§2.6.1/§15）；F-D7 `--once` 补列（§2.3）；F-D8 复审自纠撤回。**文档级 0 P1**。
- **零代码变更 / 未提交**：本步仅文档。
- **下一步**：Step 5 实施（B0 运行时+入口 → B1 WS → B2 门禁+部署 → B3 基准+运维，§15）；**B0 前置：F-D5/F-D6；B2 前置：F-D1**。
- **2026-11-23**：**Step 5 IMPL 完成**（[IMPL_p055_microservices](IMPL_p055_microservices.md)：B0-B3 逐处代码 + C-1..C-18 + 外部锚点 A1-A12 + 5 测试文件映射 + 读数 15 命令化）。
- **2026-11-23**：**Step 6 IMPL 异构复审 PASS（有条件）**（[REVIEW_p055_step6_impl](REVIEW_p055_step6_impl.md)，GLM ≠ 作者）：P1×1（anyio `run_sync` 不转发 kwargs + `snapshot_and_stream` keyword-only → `functools.partial`）+ P2×2（`AsyncRedisBus.close()` 已实装 → bus.py 零改动；`ConsumerLoop` 属性名）+ P3×3，6 处当场回写 IMPL；本文档 D-9 所述 `orders_limit` 表述经 grep 复核**无残留**。
- **2026-11-23**：**Step 7 CHECKLIST 完成**（[CHECKLIST_p055_microservices](CHECKLIST_p055_microservices.md)：M16+T6+C10+I12+D14+G19+F7 = 84 项断言，实测列全部 `[待 Step 9]`）。
- **2026-11-23**：**Step 8 四文档一致性通过**——IMPL §3.2/§3.4 两处 F-S6 修正残留清理（`self.batch`→`count` 参数；「需补 aclose」→`await bus.close()` 零改动）+ IMPL §6 步 1 market 用例口径澄清 + 本文 §11.6 tests 目标统一 **≥156**；D5「巡检共用 QueryScheduler 显式传入」与 R-IMPL-2 残留的收敛口径 = Step 9 对码后择一。**下一步 Step 9 TDD（红绿序 = IMPL §6）。零代码变更 / 未提交。**
- **2026-11-23**：**Step 9 TDD + 门禁完成**——B0（`trading_worker` 信号/三线程/非忙等/巡检/`--bus fake`、`outbox_relay` 双 `run`、`market_gateway` serve/argparse/改写 stub）、B1（`ws_routes.py` 新增 + `api.py` lifespan/挂载/readiness + `api_worker` 双参 factory/全装配）、B2（3 契约/负例/CI arch-check/adapter/Dockerfile services/deploy 资产）、B3（bench 脚本 + runbook）全部落码；19 例新测试全绿，门禁 **1439 / 22 / 120 / 159·0 / 319 / 156·13·51·19 / lint 3 kept / lock / compose / 结构零 diff**。**Step 9 校准（已回写）**：C3 `allow_indirect_imports = true`（默认连间接导入会误红 api→ledger_store→ledger）；lint 入口为 console script `lint-imports`（2.17 无 `__main__`）。**唯一环境待验**：bench 实跑缺 Redis（Docker daemon 未运行）→ Step 10 读数 12。
- **2026-11-23**：**Step 10 验收 PASS（0 P1 残留）**——M13 双轮实跑（1k / 10k）**三零全中**，T4 p50 1.21/1.22 ms、p99 2.66/2.98 ms；§11 读数 10 **0.00% 单核**、读数 11 **200 / 503 `stale_*`**、O3 **0.47 s exit 0**；实跑暴露并修复 **F-B1/B2/B3/B9 四个 P1 + F-B5 harness 三缺陷**（`SyncRedisBus` adapter 形状补齐、消费组懒创建、`XAUTOCLAIM` 三元素解包、入口 `__main__` 守卫、bench 跨跑复位/订阅延迟/扇出等待）；门禁 **1440 passed / 1 skipped** + 22/120/159·0/319/156·13·51·19 + lint 3 kept + lock + compose + 结构零 diff。详见 [REVIEW_p055_step10_acceptance](REVIEW_p055_step10_acceptance.md)。**未提交，待用户授权。**
