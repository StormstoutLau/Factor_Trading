# RESEARCH：P-055 微服务拆分（部署化模块化单体 + 进程边界 + 依赖门禁 + 跨进程基准）

> **批次**: P-055 · **Step 1 调研** · 日期 2026-11-23 · **基线 commit**: `e67ebbe`（P-054 关闭后）
> **上游**: [UPGRADE_MASTER_PLAN](UPGRADE_MASTER_PLAN.md) L272（P-055 行）/ F6 L217-221（六服务边界）/ §6 L286、L293（import-linter 门禁）/ §7 Q13（观测栈）；[PROGRESS](PROGRESS.md) §3.75（P-054 关闭）
> **口径**: Q8/Q9/Q17/Q18/Q19/Q20 已裁决不重开；本文件只做 Step 1 调研与决策点收敛，不写代码、不改门禁
> **判档**: T1（全量）——涉及进程拓扑、部署、依赖门禁与验收基准

---

## 0. 结论摘要（TL;DR）

1. **P-055 的实质不是「把单体拆成六个网络微服务」**，而是把 P-054 已定的进程模型补齐为**可部署、可观测、可门禁、可基准**的运行拓扑。理由：Q18 已裁决单写者 + N 无状态 worker；SQLite WAL 要求所有进程同机本地文件系统；行情源 3s/笔；自用/单团队；总纲 §6 的验收硬项是「依赖方向门禁 + 端到端延迟基准」，不是服务数量。
2. **代码现状暴露 4 个 P1 运行缺口**（P-054 设计/IMPL 均有要求，Step 9 落码漏接，测试只覆盖 `run_once` 未覆盖 `main()`）：
   - `ConsumerLoop` 装配了但**从未启动**（[trading_worker.py#L45-L51](../services/trading_worker.py#L45-L51) 仅启动 relay）→ 真实进程中 **Streams → Pub/Sub 链路断开**；
   - `Heartbeat` 类定义但**从未实例化/启动**；`/health/ready` 调 `evaluate_readiness(store)` **未传 heartbeats** → stale 永不 503（[api.py#L165-L170](../services/api.py#L165-L170)）；
   - `market_gateway.main()` 只 `run_once()` **一次即退出**，无按 `hz` 循环（[market_gateway.py#L71-L87](../services/market_gateway.py#L71-L87)）；
   - 无 `SIGTERM/SIGINT` handler（IMPL C-20 明确要求），容器 `stop` 默认 SIGTERM → 不执行 `finally` 清理。
3. **部署资产为空**：根 [docker-compose.yml](../docker-compose.yml#L11-L43) / [Dockerfile](../Dockerfile#L28-L52) 仅服务回测（`.[dev]` + 默认 `pytest`），**无 redis、无 trading/api/market 服务、无 healthcheck/depends_on/restart/volume 规划**。
4. **依赖方向门禁未落地**：全仓无 `import-linter` 依赖/配置/CI job（总纲 §6 L286/L293 的硬要求）→ 本批验收硬项。
5. **跨进程端到端延迟基准未做**：P-054 J6 是 `InMemoryBus` 进程内分段计时（[test_p054_end_to_end.py](../tests/test_p054_end_to_end.py)），不是「真实 Redis + 进程边界」→ 本批验收硬项。
6. **推荐方案 A：部署化模块化单体（4 类进程 + Redis）**——交易 writer（单实例）/ N 个 API+WS worker / 行情网关 / Redis（Streams + Pub/Sub + TTL 键）。**不新增策略引擎/风控网络服务**（保持库内调用，文档化未来拆分触发条件）。
7. **推荐双部署模式**（关键裁决）：
   - **Mode S（synthetic/开发/CI）**：全容器（redis + trading + api + market），SQLite 用 **named volume**（不进 Windows bind mount）；
   - **Mode R（真实 QMT/CTP）**：**应用进程全部 Windows 原生**（QMT 仅 Windows 本机或 Windows 云主机；F6 L219），只有 Redis 走 Docker Desktop/WSL2；SQLite 留 NTFS 本地盘，**绝不跨 Windows/WSL 挂载**。
8. **需用户裁决 8 项**（U-P055-1..8）。其中 4 项高影响决策已补外部案例与多维评分（[RESEARCH_p055_decision_anchors](RESEARCH_p055_decision_anchors.md)），推荐组合 **A/A/A/A**（双模式 / 不拆策略风控 / named volume 或原生盘 / 基准报告制），置信度为高或中高。

---

## 1. 题干与范围

### 1.1 总纲口径

| 来源 | 原文/约束 | 对 P-055 的含义 |
|------|-----------|-----------------|
| 总纲 L272 | 「P-055 微服务拆分｜进程边界 + Redis Streams + 部署｜前置 P-054｜验收：依赖方向门禁；端到端延迟基准」 | 四个交付面：进程边界、Redis 拓扑、部署、两项验收 |
| 总纲 F6 L217 | 「行情服务 / 策略引擎（只产信号）/ 风控服务（事前同步闸门）/ 交易网关（唯一对接柜台、每账户单写者）/ 持仓账户服务（成交驱动账本+对账）/ API+WS（只读扇出）」 | 六服务边界；P-054 已覆盖其中 4 个（行情/交易网关/账本/API+WS），策略与风控仍是库 |
| 总纲 §6 L286 | 允许边 `services→live/strategies/core`、`live→strategies/core`、`strategies→core`；禁止 `core→live/services/strategies`、`strategies→live/services`、`live→services`；`services` 禁含交易逻辑 | import-linter 契约的精确边集 |
| 总纲 §6 L293 | 新增 CI job 跑 `import-linter`；`[dev]` 加 `import-linter`；新 job 不依赖 Windows | CI/依赖落点 |
| 总纲 §7 Q13 | 观测栈决定 P-055 部署复杂度 | 已由 P-054 Q17 收敛为「prometheus-client + JSON 日志，不上 Grafana」 |

### 1.2 前置批次已交付（P-054，commit `d7a0c8a`）

| 能力 | 落点 | 状态 |
|------|------|------|
| 单写者 + N worker 进程模型 | `services/trading_worker.py` / `services/api_worker.py` | 入口存在，运行时装配不完整（G1-G4） |
| store v2 + outbox/inbox/meta | `live/ledger_store.py` | 完成（P-054 Step 10 PASS） |
| outbox relay + 单消费者 + Pub/Sub 扇出 | `services/outbox_relay.py` | 类完成；进程入口未启动 consumer |
| WS snapshot+delta / seq / 背压 | `services/ws_hub.py` | 完成 |
| API Key + ticket + TLS + metrics | `services/{auth,api,api_worker,metrics}.py` | 完成 |
| 行情 synthetic → Pub/Sub | `services/market_gateway.py` | 完成单次 poll；无循环 |
| Python 3.11 基线 + `[services]` extra | `pyproject.toml` / `tests.yml` | 完成 |
| 延迟基准（进程内） | `scripts/p054_bench_ws.py` | 完成，但非跨进程 |

### 1.3 本批做什么 / 不做什么

**做（建议验收面）**：

1. **运行时补齐**：consumer 线程、heartbeat 线程、market 循环、SIGTERM/SIGINT 优雅退出、readiness 接心跳。
2. **部署编排**：服务化 compose（redis + trading + api + market，healthcheck/depends_on/restart/volume/profiles）+ 非 root 运行镜像 target + env 样例。
3. **依赖方向门禁**：`import-linter` 契约 + `[dev]` 依赖 + CI `arch-check` job + 本地门禁入口 + 负例（证明门禁真能拦住）。
4. **跨进程端到端延迟基准**：真实 Redis + 进程边界，分段 p50/p95/p99 报告，0 订单事件丢失、pending 归零。
5. **运维契约**：`RUNBOOK_p055_deployment.md`（启动/停止/重启/备份/健康检查/故障排查/跨机回退）。
6. **文档与台账**：RESEARCH/DESIGN/IMPL/CHECKLIST/REVIEW + PROGRESS。

**不做（外置或明确拒绝）**：

- 策略引擎 / 风控服务拆成独立网络进程（推荐不拆，§4.1/§6 U-P055-2）；
- 真实行情源、真实 QMT/CTP 联调（P-056 / U-P053-1）；
- Kubernetes / NATS / gRPC / leader election / 服务网格；
- REST 下单/撤单/kill-switch（P-054 D19 已明确不含）；
- 跨机 SQLite（Q19 已裁：同机只读；跨机只做内部 API 文档化回退）；
- Grafana 全栈（Q17 最小栈）。

### 1.4 已裁决不重开

| 裁决 | 内容 | 对 P-055 的约束 |
|------|------|-----------------|
| Q18 | 单实例交易/账本进程 + N 个无状态 API/WS worker，无 leader election | 不得引入多写者或分布式锁 |
| Q19 | 同机只读 SQLite（`mode=ro`/`query_only`）；跨机回退到内部 API；不建 Redis 读模型 | 部署必须同机；跨机只写文档 |
| Q20 | 本地 Docker Desktop(WSL2) + `redis:7`；CI Ubuntu `services: redis`；单测 FakeBus | redis 版本锁定 7（不得用 8.6 幂等特性） |
| Q17 | `prometheus-client` + 四黄金信号 + JSON 日志；不上 Grafana | 观测最小化 |
| Q9 | 自用工具；API 仅本机/内网；速率 ≤1 笔/秒、≤1000 笔/日 | 不做公网暴露/多租户 |

---

## 2. 代码现状（E3，基线 `e67ebbe`）

### 2.1 进程入口清单

| 进程 | 入口 | 职责 | 线程/循环 | 现状 |
|------|------|------|-----------|------|
| 交易/账本 writer | `python -m services.trading_worker`（`main()` L54） | store + gateway + relay + consumer + heartbeat | 主线程 `gateway.poll()`；`start_threads` 仅启动 relay | **不完整**（G1/G2/G4） |
| API/WS worker（N 个） | `python -m services.api_worker`（`main()` L44） | uvicorn `--factory` + TLS + workers 透传 | uvicorn 管理 | **REST 可跑；WS 未挂载（G17）+ 入口两处启动缺陷（G18）+ 装配缺省（G19）**（Step 2 复审发现） |
| 行情网关 | `python -m services.market_gateway`（`main()` L71） | synthetic → PUBLISH `p054:market` | **仅 `run_once()` 一次** | **不能长跑**（G3） |
| Redis | 外部依赖 | Stream `p054:orders` / Pub/Sub / TTL 键 | — | 无部署资产（G5） |

### 2.2 运行时缺口（对照 P-054 DESIGN/IMPL）

| 设计要求 | 出处 | 落码现状 | 缺口 |
|----------|------|----------|------|
| relay/consumer/heartbeat **三线程**均用 `SyncRedisBus` | IMPL §3.21 L438 | `assemble()` 创建 consumer（L41），`start_threads()` 只启动 relay（L45-L51） | **consumer 从未运行** |
| heartbeat 线程每 1s/2s 写 TTL 键 | DESIGN §3.5 L377-L378；IMPL §3.21 L440 | `Heartbeat` 类定义（L110-L125），`main()` 未实例化 | **心跳键从不写入** |
| API ready 读心跳 | DESIGN §3.7；`evaluate_readiness` L33-L40 | `health_ready` 调 `evaluate_readiness(store)`，`heartbeats=None` → 两检查被跳过 | **stale 永不 503** |
| `signal.signal(SIGINT/SIGTERM)` → `stop_event` → `join(5)` | IMPL C-20 L277 | 无任何 signal handler；`finally` 仅在异常/KeyboardInterrupt 时执行 | **容器 SIGTERM 不走清理**（G4）；主循环 `while True: gateway.poll()` 无 sleep 且 poll 无内部等待（[gateway.py#L329-L347](../live/gateway.py#L329-L347)）→ **忙等 CPU 空转**（G4 扩展，Step 2 复审实证） |
| market 独立入口 + `--embedded` | DESIGN §2.1/§3.19；IMPL §3.19 L427 | `main()` 只 `run_once()`；无 `--embedded` 参数解析 | **行情只发一帧**（G3） |
| **WS 端点挂载** | F7 L231「WS Hub 扇出」；DESIGN §3.6 | **services/ 全目录 0 处 websocket 路由**（复审 grep 实证）；`ws_hub.ConnectionHub` 为纯组件，无任何 ASGI 挂载点；api.py 11 端点全 REST | **部署态 API worker 零 WS 端点**（G17，Step 2 复审新增 P1） |
| **api_worker 入口可启动性** | IMPL §3.20（uvicorn 入口） | `uvicorn.run(app 实例, factory=True)` → uvicorn 0.54 将实例无参调用 → TypeError → `sys.exit(3)`（config.py L513-518）；`tls_context_factory()` 零参 vs uvicorn 双参协议（config.py L246/L477）→ TLS 模式启动即崩 | **入口不可启动**（G18，Step 2 复审新增 P1；测试仅 pickle 断言未覆盖） |
| `gateway.poll()` 0.5s + 巡检 6s | IMPL §3.21 L438 | `main()` 有 `while True: gateway.poll()`；无巡检调度 | 巡检未接（P2） |

### 2.3 部署资产现状

| 资产 | 现状 | 缺口 |
|------|------|------|
| `Dockerfile` | 多阶段；builder 装 `.[dev]`（L28）；runtime `CMD pytest`（L52） | 无 `[services]` target；默认跑测试不是服务 |
| `docker-compose.yml` | 单容器 `factor-trading` + `test/backtest/shell` profiles（L11-L43） | 无 redis/trading/api/market；无 healthcheck/depends_on/restart |
| `.env` 样例 | 未见服务级样例 | 缺 `P054_*` 全量 env 矩阵 |
| Prometheus 抓取配置 | 无 | 指标端点存在但未接抓取 |
| Runbook | P-052 有故障处理 runbook；P-054 无部署 runbook | 缺启动/停止/备份/回退 |

### 2.4 门禁现状

| 门禁 | 现状 | 与总纲 §6 的差距 |
|------|------|------------------|
| pytest | 1420（P-054 后） | 需新增 P-055 用例并保零回归 |
| golden | 22 零重录 | 本批不应触碰 |
| mypy | 157 files 0；靶含 `services` | 已满足 |
| black | 309 unchanged | 已满足 |
| `uv lock --check` | CI `lock-check` job | 新增依赖需同步 `uv.lock` |
| **import-linter** | **全仓 0 处依赖/配置/CI job** | **P-055 验收硬项** |
| AST 纯函数核扫描 | 无 | 总纲 §6 有要求，但非 P-055 验收项（观察） |

### 2.5 依赖边实测（E3）

| 方向 | 实测 | 结论 |
|------|------|------|
| `live/*` → `services/*` | 0 处 | 合法（禁止边未出现） |
| `core/*` → `live/services/strategies` | 0 处 | 合法 |
| `strategies/*` → `live/services` | 0 处 | 合法 |
| `services/*` → `live/core/strategies` | 存在**函数内延迟导入**：`api._load_store` → `live.ledger_store`（[api.py#L25-L30](../services/api.py#L25-L30)）；`trading_worker.main` → `live.gateway/ledger/ledger_store/adapters.terminal`（[trading_worker.py#L56-L61](../services/trading_worker.py#L56-L61)）；`market_gateway.main` → `services.bus` | 合法边；但 import-linter 必须能识别延迟导入（见 §4.4） |
| `services.api` → `live.gateway/orders/channel` | 0 处 | 「REST 禁交易逻辑」当前成立，可用 forbidden 契约固化 |

### 2.6 通信与存储边界

| 通道 | 用途 | 语义 | 现有实现 |
|------|------|------|----------|
| Redis Stream `p054:orders` | 订单/成交事件（不可丢） | at-least-once；consumer group + PEL + XACK | relay `XADD`；consumer `XREADGROUP`/`XACK` |
| Redis Pub/Sub `p054:orders:events` | 事件扇出到全部 API/WS worker | at-most-once，可丢（重连发 snapshot） | consumer publish；ws_hub subscribe |
| Redis Pub/Sub `p054:market` | 行情 tick | at-most-once，可丢/可合并 | market_gateway publish；ws_hub subscribe |
| Redis Pub/Sub `p054:admin` | 跨 worker 暂停/恢复行情 | at-most-once | API 发布；ws_hub 订阅 |
| Redis TTL 键 | trading/consumer 心跳 | TTL 过期即判死 | `Heartbeat` 类（未启动） |
| SQLite（WAL） | 账本/订单/outbox/inbox/meta | 单写者 + N 只读 reader | writer `SqliteLedgerStore`；reader `read_only=True` |

---

## 3. 发现表

| ID | 级别 | 结论 | 证据（E） | 处置建议 |
|----|------|------|-----------|----------|
| **G1** | **P1** | **consumer 线程未启动**：`assemble()` 创建了 `ConsumerLoop`，但 `start_threads()` 只启动 `RelayLoop`；真实进程中订单事件进 Stream 后无人消费、无人扇出 | E3: [trading_worker.py#L41](../services/trading_worker.py#L41) + [#L45-L51](../services/trading_worker.py#L45-L51) + [outbox_relay.py#L77-L121](../services/outbox_relay.py#L77-L121) | P-055 补齐三线程 + `stop_event`；加进程级冒烟探针（relay→stream→consumer→pubsub） |
| **G2** | **P1** | **heartbeat 未启动且 readiness 未接**：`Heartbeat` 类无实例；`health_ready` 不传 heartbeats → `evaluate_readiness` 直接跳过 trading/consumer 检查，stale 永不 503 | E3: [trading_worker.py#L110-L125](../services/trading_worker.py#L110-L125) + [api.py#L165-L170](../services/api.py#L165-L170) + [#L33-L40](../services/api.py#L33-L40) | heartbeat 线程写 `p054:trading:heartbeat`/`p054:consumer:heartbeat`；API 从 Redis 读并传 `heartbeats=`；加「杀心跳 → 3s 内 503」探针 |
| **G3** | **P1** | **行情网关只跑一次**：`main()` 调 `run_once()` 后返回；无 `hz` 循环、无 `--embedded` 参数、无停止条件 | E3: [market_gateway.py#L71-L91](../services/market_gateway.py#L71-L91)；DESIGN §3.19；IMPL §3.19 L427 | 改 `while not stop: run_once(); sleep(1/hz)`；接 SIGTERM；补 `--embedded` |
| **G4** | **P2** | **无优雅停机**：无 `signal.signal(SIGINT/SIGTERM)`；容器 `stop` 的 SIGTERM 默认终止，`finally` 不执行 → store 未 close、线程未 join | E3: [trading_worker.py#L85-L89](../services/trading_worker.py#L85-L89)；IMPL C-20 L277；S21 | 主线程注册信号 → `stop_event`；relay/consumer/heartbeat/market 检查 stop；`join(5)`；compose `stop_grace_period` |
| **G5** | **P1** | **部署资产仍是回测容器**：compose 无 redis/服务定义；Dockerfile 装 `.[dev]` 且默认 `pytest` | E3: [docker-compose.yml#L11-L43](../docker-compose.yml#L11-L43) + [Dockerfile#L28](../Dockerfile#L28) + [#L52](../Dockerfile#L52) | 新增服务化 compose + `services` 镜像 target；保留回测 compose 不动 |
| **G6** | **P1** | **依赖方向门禁缺失**：无 `import-linter` 依赖/配置/CI job，总纲 §6 未落地 | E3: [pyproject.toml#L58-L79](../pyproject.toml#L58-L79) + [tests.yml#L9-L59](../.github/workflows/tests.yml#L9-L59)；S1/S19 | 加 `[dev] import-linter>=2.15` + `[tool.importlinter]` + CI `arch-check` + 负例测试 |
| **G7** | **P1** | **无跨进程端到端延迟基准**：P-054 J6 是进程内 `InMemoryBus` 分段，不覆盖 Redis/进程边界/WS；CI 也无 `services: redis` job（Q20 只预留口径） | E3: [test_p054_end_to_end.py](../tests/test_p054_end_to_end.py)；[tests.yml#L48-L59](../.github/workflows/tests.yml#L48-L59)；[REVIEW_p054_step10 §2](REVIEW_p054_step10_acceptance.md) | 新增 `scripts/p055_bench_e2e.py`：真实 Redis + 进程边界，1k/10k，四段 p50/p95/p99；CI 是否加 integration job 由 U-P055-4/6 裁决 |
| **G8** | **P2** | **容器网络与 TLS 校验冲突**：`allow_plaintext_loopback` 仅允许 `api_host=127.0.0.1`；容器内需绑 `0.0.0.0` 才可达 → 必须 TLS 或 host network | E3: [config.py#L66-L72](../services/config.py#L66-L72) + [api_worker.py#L58-L61](../services/api_worker.py#L58-L61) | Mode S 挂载证书并设 `P054_TLS_*`；或明确只在本机 host 网络明文；二选一写入设计 |
| **G9** | **P2** | **SQLite 不能跨 OS/挂载边界**：WAL 要求所有进程同机本地文件系统；`-shm/-wal` 需存在或可创建；长读事务会阻塞 checkpoint | E3: S6 L59/L65/L95-L99；S7 L98/L110/L126 | Mode S 用 named volume；Mode R 全部 Windows 原生 + NTFS；**禁止** Windows→WSL bind mount 共享 SQLite；reader 用 rw 挂载 + 应用层 `mode=ro`/`query_only` |
| **G10** | **P2** | **真实网关不能容器化**：QMT 仅 Windows（本机或 Windows 云主机）；`xtquant` 为 Windows-only；P-053 已定 Windows venv | E3: S1 L219；P-053/P-054 文档；决策专项 S9/S11 | Mode R 明确「应用原生、仅 Redis 容器」；compose 只服务 Mode S 与 CI |
| **G11** | **P2** | **trading 无 HTTP 健康检查**：compose `depends_on service_healthy` 需要一个探针；当前只能查 SQLite 文件/心跳键 | E3: [trading_worker.py#L110-L125](../services/trading_worker.py#L110-L125)（心跳未写）；S9 | healthcheck 用 `redis-cli GET p054:trading:heartbeat` 或 Python `redis` 探针；心跳补齐后成立 |
| **G12** | **P3** | **metrics 默认要 auth**：`metrics_require_auth=True`，Prometheus 抓取需带 reader key 或关闭 | E3: [config.py#L21](../services/config.py#L21) + [api.py#L245-L254](../services/api.py#L245-L254) | Mode S 内网抓取设 `P054_METRICS_REQUIRE_AUTH=0`（仅 loopback/内网）或 scrape 带 key；写入 runbook |
| **G13** | **P3** | **「services 禁含交易逻辑」不能只靠分层表达**：`services.trading_worker` 作为组合根必须 import `live.gateway`；API/WS 边才应禁止 | E3: [trading_worker.py#L56-L61](../services/trading_worker.py#L56-L61) + [api.py#L25-L30](../services/api.py#L25-L30) | layers 契约 + **API 边专用 forbidden**（`services.api/api_worker/ws_hub/market_gateway` 禁 `live.gateway/orders/channel/ledger`）+ 评审项 |
| **G14** | **P3** | **`--bus fake` 未落 CLI**（P-054 F-A6 已登记）：FakeBus 仅测试可注入，入口无开关 | E3: [trading_worker.py#L54-L89](../services/trading_worker.py#L54-L89) | 本批可顺手加 `--bus fake`（仅开发）；或 runbook 明确不支持 |
| **G15** | **P3** | **六服务边界中策略/风控未进程化**：`strategies/` 与风控均为库；无独立入口 | E3: `strategies/*.py`；`core/guard_pipeline.py`；总纲 F6 L217 | 推荐**不拆**，文档化触发条件（§4.1）；若用户要求拆，另立批次 |
| **G16** | **观察** | 无 Prometheus 抓取/Grafana 资产；Q17 已定最小栈 | E3: 全仓无 `prometheus.yml` | Mode S 加 optional profile；不做 Grafana |
| **G17** | **P1（Step 2 复审新增）** | **FastAPI 进程零 WS 端点**：services/ 全目录 0 处 websocket 路由；`ws_hub.ConnectionHub` 纯组件无 ASGI 挂载点；api.py 11 端点全 REST → 部署态 WS seq/snapshot+delta/慢消费者 1013 全部不可达（P-054 探针走 Hub 直连掩盖缺口） | E3: services/ grep `websocket` 0 命中；[ws_hub.py](../services/ws_hub.py) 无路由代码；P-054 IMPL §3.17/§3.18 均未定义挂载职责 | P-055 承接：设计 `app.websocket("/ws/orders"|"/ws/market")` 挂载 + hub 接线（AsyncRedisBus 订阅）+ 真实握手探针（HTTP 升级级，非 Hub 直连） |
| **G18** | **P1（Step 2 复审新增）** | **api_worker 入口不可启动**：① `uvicorn.run(app 实例, factory=True)` → uvicorn 0.54 `Config.load()` 无参调用实例 → TypeError → `sys.exit(3)`（config.py L513-518 + importer.py L10-11 实证）；② `tls_context_factory()` 零参 vs uvicorn 双参协议 `Callable[[Config, Callable], SSLContext]`（config.py L246/L477）→ TLS 模式在 app 加载前即 TypeError。测试仅 `pickle.dumps` 断言（[test_p054_api_auth.py#L166](../tests/test_p054_api_auth.py#L166)） | E3: [api_worker.py#L33-L62](../services/api_worker.py#L33-L62) + .venv uvicorn 0.54.0 源码 | ① 移除 `factory: True`（实例直跑，倾向）或 import string；② 签名改 `(config, default_factory)` 双参转发；Step 9 加真实 uvicorn 启动探针（子进程 boot + `/health/live` 200） |
| **G19** | **P2（Step 2 复审新增）** | **api_worker 装配缺口**：`create_app(settings=)` 缺 publisher/bus/hub → broadcast-pause 跨 worker 语义静默丢失（api.py L240 有 None 防护，不崩但失效，F-I9 残留）；`ticket_store` 默认 InMemoryTicketStore，RedisTicketStore 已实现（auth.py L97）未接线 → 多 worker ticket 不共享 | E3: [api_worker.py#L50-L51](../services/api_worker.py#L50-L51) + [api.py#L240](../services/api.py#L240) + [auth.py#L77/L97](../services/auth.py#L77) | 与 P-054 F-A4 同型：api_worker 补 AsyncRedisBus/publisher=bus/RedisTicketStore（settings.redis_url）/hub 装配（依赖 G17 设计） |

---

## 4. 关键论证

### 4.1 为什么不拆成六个网络微服务

**结论：维持「模块化单体 + 必要的进程边界」，不把策略/风控拆成网络服务。**

外部案例佐证（详见 [决策专项 §3](RESEARCH_p055_decision_anchors.md)）：Segment 从 100+ 微服务回到单体（运维复杂度/重复 bug）；Prime Video VQA 迁回单体后基础设施成本降 90%+；Shopify 选择「模块化单体 + 强制边界」支撑千人级代码库；arXiv 综述归纳回退五因（成本/复杂度/可扩展性/性能/组织）。

证据链：

1. **MonolithFirst**：Fowler 明确「几乎所有成功的微服务故事都始于一个变得过大的单体；从零构建微服务系统的案例多数陷入麻烦」，并给出「先粗粒度服务、边界稳定后再拆」的路径（S16）。本仓正处在这一路径：P-054 刚建立 writer/worker 边界，策略/风控边界尚未被真实负载检验。
2. **MicroservicePremium**：微服务引入自动部署、监控、故障处理、最终一致性等额外成本；「除非系统复杂到单体难以管理，否则不要考虑微服务」（S17）。本仓是自用单机/内网、单团队、3s/笔行情（S1 §7 Q2），没有团队规模/独立伸缩/多租户驱动。
3. **数据边界硬约束**：SQLite WAL 要求所有进程同机且本地文件系统（S6 L59），同一时刻只有一个 writer（S6 L95；S7 L110/L126）；跨机只能走内部 API（Q19 已裁）。把账本拆成网络服务不会消除这个约束，只会增加一次网络往返与一致性窗口。
4. **同步事前风控的路径要求**：总纲 F6 L217 要求「风控服务（事前同步闸门）；下单路径尽量短」。若拆成网络调用，submit 路径增加一次 RPC + 超时/重试/降级语义；当前 `pre_trade_check` 是纯内存函数（P-052），拆分收益为负。
5. **验收口径**：总纲 L272 的验收是「依赖方向门禁 + 端到端延迟基准」，不是「服务数量」。本批应把这 4 类进程部署好、把边界用工具锁死，而不是制造分布式单体。

**未来拆分触发条件（写入设计，不在本批实现）**：

- 策略数量/回测吞吐导致交易进程 CPU 饱和，且策略可独立伸缩；
- 风控需要独立合规审计进程或多账户共享；
- 需要跨机部署（届时账本仍留单机，API 走内部 API）；
- 团队规模导致独立发布节奏。

### 4.2 SQLite WAL 的硬约束（决定部署拓扑）

| 事实 | 来源 | 对部署的含义 |
|------|------|--------------|
| WAL 下「readers do not block writers and a writer does not block readers」 | S6 L51 | API reader 可与 writer 并发，不必停写 |
| 「All processes using a database must be on the same host computer; WAL does not work over a network filesystem」 | S6 L59 | **所有进程必须同机本地盘**；跨机 SQLite 直接排除 |
| 「there can only be one writer at a time」 | S6 L95 | 交易进程单实例；多 writer 会 `SQLITE_BUSY`/锁冲突 |
| 只读 WAL 数据库可打开的条件：`-shm`/`-wal` 已存在或可创建（或 immutable） | S6 L65 | 容器 reader 若 ro 挂载目录，需保证 `-shm/-wal` 存在且可访问；**建议 rw 挂载 + 应用层只读** |
| 长读事务会阻止 checkpoint 推进 | S6 L97-L99 | API 查询应短事务；避免长游标/大结果集持锁 |
| SQLite 单写者、写事务通常毫秒级；不适合多机直接共享 | S7 L110/L126 | 与 Q18 单写者裁决一致 |

独立学术佐证：Gaffney et al., *SQLite: Past, Present, and Future*, PVLDB 15(12), 2022（S8）指出 SQLite 是 in-process、面向 OLTP 的设计；另一篇 PVLDB 2022 论文亦指出 SQLite 使用粗粒度文件锁、同一时刻仅一个线程可获排他锁（S8b）。这从实现层面解释了为何「多 writer + 网络共享」不可行。

### 4.3 Redis Streams 语义与现有实现对照

| 语义 | 官方事实 | 现有实现 | 结论 |
|------|----------|----------|------|
| Stream = append-only log + consumer groups | S4 L135-L137 | `XADD`/`XREADGROUP` | 匹配 |
| 消费后进入 PEL，需 `XACK` 才移出 | S4/S5；`XACK` 返回成功数 | `ConsumerLoop` publish 后 `mark_inbox` + `ack` | at-least-once 正确；重复投递由 inbox 幂等 |
| 崩溃消费者的 pending 可被接管 | `XAUTOCLAIM`（v6.2+）按 `min-idle-time` 转移 | `stream_autoclaim`/`autoclaim`；`ConsumerLoop.run_once(autoclaim=True)` | 具备；但进程入口未启动 consumer（G1） |
| Redis 8.6 起支持 XADD 幂等（IDMP） | S4 L147 | 目标 `redis:7`（Q20） | **不得依赖**；继续用应用层 inbox 去重 |
| Pub/Sub 不持久化 | Redis Pub/Sub 语义 | 行情/事件扇出；重连发 snapshot | 与 P-054 D12 一致；订单事件可靠性由 Stream+inbox 保证 |

### 4.4 依赖方向门禁设计

**工具**：`import-linter` 2.15（PyPI 2026-09-04，Requires-Python >=3.10，Classifier 含 Windows；S19）。其 `layers`/`forbidden` 契约可表达总纲 §6 的边集；UI 文档明确图模型包含 **lazy imports**（S20 检索摘要），因此函数内延迟导入（本仓 `api._load_store`、`trading_worker.main`）会被计入。

**契约草案（Step 3 定稿）**：

```ini
[importlinter]
root_packages =
    core
    live
    strategies
    services

[importlinter:contract:layers]
name = services > live > strategies > core
type = layers
layers =
    services
    live
    strategies
    core
```

> 配置语法以 Step 3 本地 `lint-imports` 实测为准（`root_packages` 复数形式与 `exclude_type_checking_imports` 选项版本相关；S19/S20）。

```ini
[importlinter:contract:core-no-upward]
name = core must not import upper layers
type = forbidden
source_modules =
    core
forbidden_modules =
    live
    services
    strategies

[importlinter:contract:api-no-trading]
name = API/WS edges must not import trading internals
type = forbidden
source_modules =
    services.api
    services.api_worker
    services.ws_hub
    services.market_gateway
forbidden_modules =
    live.gateway
    live.orders
    live.channel
    live.ledger
```

**要点**：

- `layers` 已隐含「下层不得上行」，但保留显式 `core-no-upward` 以获得清晰错误信息；
- `services.trading_worker` 是**组合根**，允许 import `live.gateway`，因此不能把整个 `services` 包都设为禁止源；
- `exclude_type_checking_imports` 需在 Step 3 决定（避免 `TYPE_CHECKING` 误报）；
- **负例证明门禁有效**：在 `tests/fixtures/arch_violation/` 放一个故意反向 import 的微型包 + 独立配置，测试用 `subprocess` 跑 `lint-imports` 断言退出码非 0；否则「0 violations」可能只是没配到模块；
- 落点：`[dev]` 加 `import-linter>=2.15` → `uv lock` → CI 新 job `arch-check`（Ubuntu，不依赖 Windows）→ `scripts/spec_runner_adapter.py` 加本地门禁。

### 4.5 部署编排设计（建议，Step 3 定稿）

**Mode S（synthetic/开发/CI，全容器）**：

| 服务 | 镜像/命令 | 依赖 | 健康检查 | 卷 |
|------|-----------|------|----------|----|
| `redis` | `redis:7` | — | `redis-cli ping` | named volume（可选 AOF） |
| `trading` | 服务镜像 `python -m services.trading_worker` | redis healthy | `redis-cli GET p054:trading:heartbeat` 或 Python 探针 | `p055-data:/app/run`（SQLite 全目录） |
| `api` | `python -m services.api_worker`（可 N 副本） | redis healthy + trading healthy | `GET /health/live` | 只读挂载 `p055-data`（rw 更稳妥，见 G9） |
| `market` | `python -m services.market_gateway` | redis healthy | 进程存活（`restart: unless-stopped`） | — |
| `prometheus`（profile `obs`） | `prom/prometheus` | api | — | `deploy/prometheus.yml` |

**Mode R（真实 QMT/CTP，Windows 原生）**：

- `trading` / `api` / `market` 全部 Windows 原生进程（`python -m ...`）；SQLite 在 NTFS 本地目录；
- 仅 `redis` 通过 Docker Desktop/WSL2 暴露 `127.0.0.1:6379`（或原生 Redis 兼容服务）；
- **禁止**把 SQLite 目录 bind mount 到 WSL 容器给 API 读（跨文件系统边界，WAL 共享内存/锁语义不可靠，S6 L59）；
- 用 NSSM/任务计划或 runbook 管理进程；`stop` 用 `taskkill /PID` 前先发 CTRL_BREAK 或由 runbook 走优雅退出接口（若实现）。

**通用**：

- `restart: unless-stopped`；`init: true`（回收僵尸）；`stop_grace_period: 10s`；
- 镜像非 root 用户；`PYTHONUNBUFFERED=1`；`P054_*` env 全量样例；
- api 容器绑 `0.0.0.0` 时必须挂 TLS 证书（G8），或使用 host network（Windows Docker Desktop 支持有限，需实测）；
- 不修改现有回测 `docker-compose.yml`，新增 `deploy/compose.services.yaml`（Compose 支持 `-f` 多文件/独立文件，S10）。

### 4.6 端到端延迟基准口径

P-054 已有进程内三段（`scripts/p054_bench_ws.py`）。P-055 需补「跨进程 + 真实 Redis」：

| 段 | 起点 | 终点 | 测什么 |
|----|------|------|--------|
| T1 提交 | `submit()` 进入 | outbox 事务 commit 返回 | SQLite 写 + 事件构造 |
| T2 relay | `pending_outbox` 读出 | `XADD` 返回 + `mark_sent` | 轮询 + Redis 写 |
| T3 consume | `XREADGROUP` 返回 | Pub/Sub `PUBLISH` 返回 + inbox/ack | 反序列化 + 去重 + 扇出 |
| T4 扇出/API | `PUBLISH` 返回 | WS 客户端收到 / `GET /api/snapshot` 返回 | 进程边界 + 序列化 + 网络栈 |

口径：

- 1k/10k 两档；p50/p95/p99 + max；JSON + Markdown；
- 断言：订单事件 **0 丢失**（收端计数 = 发端）、consumer pending 归零、进程 RSS/队列无持续增长；
- **报告不设 CI SLO**（跨进程/容器调度抖动大）；SLO 由 runbook 给出参考区间（P-054 已澄清 5-50ms 是浏览器端到端现实上限，S1 §7 Q2）；
- 与 P-054 进程内基线并列展示，避免口径混淆。

### 4.7 运行时补齐设计（Step 3 细化）

```
main()
  settings/env → store(writer) → gateway → gateway.start()
  stop_event = threading.Event()
  signal.signal(SIGINT/SIGTERM, -> stop_event.set())
  threads = [relay.run(stop_event), consumer.run(stop_event), heartbeat.run(stop_event)]
  while not stop_event.is_set():
      gateway.poll()
      每 6s 巡检（scheduler.run_patrol）
  stop_event.set(); join(5); gateway.shutdown(); store.close()
```

- `ConsumerLoop.run` 需要新增循环方法（当前只有 `run_once`）；每 2s `autoclaim`；每轮写 consumer heartbeat（值 `"<ts>:<pending>"`）；
- `Heartbeat.run` 已存在（L120-L122），补 instantiate + stop_event；
- `market_gateway.main`：argparse `--embedded/--hz/--symbols`；`while not stop: run_once(); sleep(1/hz)`；
- API `health_ready`：从 Redis 读 `p054:trading:heartbeat`/`p054:consumer:heartbeat`，TTL 不存在即 False；跨 worker 共享。

### 4.8 跨机回退路径（Q19 文档化，不在本批实现）

- **触发条件**：API/WS 需要跑在另一台机器（例如 Windows 交易机 + Linux 观察机）；
- **方案**：trading 机暴露内部只读 API（带 mTLS/API Key），观察机 API worker 通过内部 API 取 snapshot/orders/positions；SQLite 不共享；Redis 可跨机（但 Streams 延迟与分区需评估）；
- **本批交付**：runbook 写清「不支持的做法（SQLite 网络共享）→ 支持的回退（内部 API）→ 安全要求」；
- **不实现**：内部 API 的代码路径（Q19 明确 P-054 只要求文档化）。

---

## 5. 候选方案与拒绝理由

| 方案 | 做法 | 优点 | 代价/风险 | 结论 |
|------|------|------|-----------|------|
| **A（推荐）部署化模块化单体** | 4 类进程 + Redis；补齐运行时；compose 双模式；import-linter；跨进程基准 | 满足总纲验收；风险最低；不引入分布式一致性；可从 P-054 平滑增量 | 需补 4 个运行时缺口；部署文档/测试工作量 | **采纳** |
| B 六服务全网络拆分 | 策略/风控独立进程；gRPC/NATS；服务发现 | 边界清晰、可独立伸缩 | 分布式事务/超时/重试/观测成本；SQLite 仍同机；submit 延迟增加；违背 MonolithFirst/MicroservicePremium | 拒绝（触发条件见 §4.1） |
| C 仅脚本 + runbook，不做 compose | 手工启动 4 个进程 | 改动最小 | 「部署」验收不成立；环境不可复现；健康检查/重启无保障 | 拒绝（可作为 Mode R 的补充） |
| D 仅 redis 容器 + 应用原生 | Mode R 的形态 | 规避 SQLite 跨挂载；贴近真实 QMT | 开发环境可复现性弱于全容器 | **作为 Mode R 采纳**（与 A 组合） |
| E 跨机 SQLite | 网络盘/共享卷 | 看似省事 | 官方明确 WAL 不支持网络文件系统；锁/共享内存不可靠 | 拒绝 |
| F 现在拆策略/风控 | 独立进程 + 同步风控 RPC | 未来扩展 | 当前无规模驱动；增加 submit 路径失败模式 | 拒绝（文档化触发条件） |

---

## 6. 决策点（需用户裁决，Step 2/3 前）

> 外部锚点、兼容/维护/短期/长期/升级潜力五维评分，以及「非推荐组合的代价」见 [RESEARCH_p055_decision_anchors](RESEARCH_p055_decision_anchors.md)。本节推荐已按该评估收敛；推荐组合 **A/A/A/A**。

| ID | 问题 | 选项 | 推荐 | 影响 |
|----|------|------|------|------|
| **U-P055-1** | 部署形态 | A 全容器（Mode S）+ 真实模式原生（Mode R）；B 仅全容器；C 仅原生 | **A（双模式）✅ 已裁决（2026-11-23）** | 决定 compose/镜像/runbook 范围 |
| **U-P055-2** | 是否拆策略引擎/风控为独立进程 | A 不拆（库内调用）；B 拆策略；C 拆风控；D 都拆 | **A ✅ 已裁决（2026-11-23）** | 决定是否引入 gRPC/NATS/分布式一致性 |
| **U-P055-3** | 依赖门禁严格度 | A layers + core-no-upward + api-no-trading + 负例；B 仅 layers；C 仅 forbidden | **A（Step 3 定稿）** | 决定契约数量/CI 时长 |
| **U-P055-4** | 延迟基准是否进门禁 | A 报告制（本地跑，CI 不设阈值）；B CI 设 SLO；C 仅进程内 | **A ✅ 已裁决（2026-11-23）** | 决定 CI 稳定性与基准脚本复杂度 |
| **U-P055-5** | 观测范围 | A 最小（Prometheus 可选 profile + JSON 日志 + healthcheck）；B 全栈 Grafana；C 不做 | **A（Step 3 定稿）** | 决定部署复杂度（Q13） |
| **U-P055-6** | SQLite 卷策略 | A 容器 named volume / 原生本地盘；B reader ro 挂载；C 共享 Windows 目录 | **A ✅ 已裁决（2026-11-23）** | 决定 WAL 可用性与权限风险 |
| **U-P055-7** | metrics 抓取鉴权 | A 内网 loopback 关闭 auth；B scrape 带 reader key；C 不抓 | **A**（仅内网；Step 3 定稿） | 决定 runbook/安全口径 |
| **U-P055-8** | 真实模式进程管理 | A NSSM/任务计划 + runbook；B 手工；C 仅容器 | **A（Step 3 定稿）** | 决定 Windows 运维复杂度 |

> U-P055-1/2/4/6 已由用户裁决 **A/A/A/A**（2026-11-23，依据决策专项五维评估）；其余 Step 3 定稿。

---

## 7. 验收读数建议（供 Step 7 CHECKLIST 挂载）

| 验收面 | 读数 | 证据出口 |
|--------|------|----------|
| 依赖方向门禁 | `lint-imports` 退出码 0；契约数 ≥3；负例 fixture 退出码 ≠0 | CI `arch-check` + 本地脚本 + 测试 |
| 部署编排 | `docker compose -f deploy/compose.services.yaml config` 退出码 0；服务数 = 4（+可选 obs）；healthcheck/restart/volume 存在 | CI 或本地 `docker compose config`（无 daemon 亦可） |
| 运行时：consumer | 发 100 事件 → 收端 100；pending=0；重复投递不重复扇出 | 进程级冒烟测试/探针 |
| 运行时：heartbeat | 停止心跳 → `/health/ready` 在 3s 内 503；恢复 → 200 | FastAPI TestClient + FakeBus/Redis |
| 运行时：market | 运行 10s → tick 数 ≥ 2×hz；`tick_seq` 单调 | 进程级探针 |
| 运行时：优雅退出 | SIGTERM → 10s 内退出码 0；store 已 close；线程 join | 子进程测试 |
| **api_worker 启动（G18）** | 真实 uvicorn 子进程 boot → `/health/live` 200；TLS 模式 boot 成功 | 子进程探针（修复 G18 后） |
| **WS 挂载（G17）** | `ws://…/ws/orders` 真实握手 → 收 snapshot；seq 连续 | HTTP 升级级探针（非 Hub 直连） |
| **主循环占用（G4）** | trading 运行 10s，CPU 占用 ≤ 1 核 ×10%（sleep 后） | 进程级读数 |
| 端到端延迟 | 1k/10k 四段 p50/p95/p99；0 订单丢失；pending 0 | `scripts/p055_bench_e2e.py` 报告 |
| 零回归 | pytest 1420 + 新增；golden 22 零重录；mypy 157+N 0；black；计数 | 门禁重放 |
| 结构守卫 | `core/*` 零 diff；`live/*` 仅运行时接线；P-054 契约不改 | `git diff --stat` |

---

## 8. 来源清单（Layer / 日期 / 版本）

> 决策专项的外部案例来源（Prime Video / Segment / Shopify / Windows 容器 / WSL2 / SQLite 论坛 / CI 基准）见 [RESEARCH_p055_decision_anchors §8](RESEARCH_p055_decision_anchors.md)，本表不重复。

| # | 来源 | Layer | 发布/更新日 | 读取日 | 版本 | 用途 |
|---|------|-------|-------------|--------|------|------|
| S1 | [UPGRADE_MASTER_PLAN](UPGRADE_MASTER_PLAN.md)（L272 / F6 L217-221 / §6 L286、L293 / §7 Q13 / L219） | **T1**（仓内总纲） | 2026-11-17 | 2026-11-23 | 仓内文档 | P-055 题干、六服务边界、门禁边集、QMT 约束 |
| S2 | [PROGRESS](PROGRESS.md) §3.75 + P-054 五文档 | **T1**（仓内验收台账） | 2026-11-22 | 2026-11-23 | commit `e67ebbe` | P-054 已交付/未交付事实 |
| S3 | 仓内源码 `services/*.py`、`live/*.py`、`tests/test_p054_*.py`、`pyproject.toml`、`tests.yml`、`docker-compose.yml`、`Dockerfile` | **T1**（仓内源码） | 2026-11-22 | 2026-11-23 | commit `e67ebbe` | 全部 G1-G16 的 file:line 证据 |
| S4 | [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) | **T1**（官方文档） | 未标注（latest） | 2026-11-23 | 文档页；命令版本见下 | Stream/consumer group/event sourcing；8.6 幂等特性 |
| S5 | [XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/) | **T1**（官方命令文档） | 未标注（latest） | 2026-11-23 | v6.2.0 起 | PEL 接管语义 |
| S6 | [SQLite: Write-Ahead Logging](https://www.sqlite.org/wal.html) | **T1**（官方文档） | 未标注（页面） | 2026-11-23 | SQLite 文档页 | 单写者/同机/只读 WAL/checkpoint 约束 |
| S7 | [SQLite: Appropriate Uses](https://www.sqlite.org/whentouse.html) | **T1**（官方文档） | 未标注（页面） | 2026-11-23 | SQLite 文档页 | 单写者、网络共享禁忌 |
| S8 | [Gaffney et al., *SQLite: Past, Present, and Future*, PVLDB 15(12), 2022](https://dl.acm.org/doi/abs/10.14778/3554821.3554842) | **T1**（学术论文，独立于厂商） | 2022 | 2026-11-23（摘要/NSF 记录） | PVLDB Vol 15 No 12 | in-process/OLTP 设计定位 |
| S8b | [Nam et al., PVLDB 15(10), 2022（In-Page Shadowing…）](https://www.vldb.org/pvldb/vol15/p2402-nam.pdf) | **T1**（学术论文） | 2022 | 2026-11-23（摘要） | PVLDB Vol 15 | SQLite 粗粒度文件锁、单排他锁的实现佐证 |
| S9 | [Docker Compose: Control startup order](https://docs.docker.com/compose/how-tos/startup-order/) | **T1**（官方文档） | 未标注（latest） | 2026-11-23 | 文档页 | `depends_on` + `condition: service_healthy` |
| S10 | [Docker Compose: Use Compose in production](https://docs.docker.com/compose/how-tos/production/) | **T1**（官方文档） | 未标注（latest） | 2026-11-23 | 文档页 | 单机部署、`restart: always`、多 compose 文件 |
| S11 | [The Compose Specification](https://compose-spec.github.io/compose-spec/spec.html) | **T1**（开放规范） | 未标注 | 2026-11-23（部分） | spec | 服务模型/`depends_on` |
| S12 | [Uvicorn: Deployment](https://www.uvicorn.org/deployment/) | **T1**（官方文档） | 未标注（latest） | 2026-11-23 | 文档页（本地 uvicorn 0.54.0） | `--workers`、进程管理、`--timeout-graceful-shutdown`、proxy headers |
| S13 | [The Twelve-Factor App: Processes](https://12factor.net/processes) | **T1**（方法论标准） | 2017（最后更新） | 2026-11-23 | 12-factor | 无状态/共享-nothing；状态进 backing service |
| S14 | [The Twelve-Factor App: Admin processes](https://12factor.net/admin-processes) | **T1**（方法论标准） | 2017（最后更新） | 2026-11-23 | 12-factor | 一次性管理任务与长驻进程同环境 |
| S15 | [Fowler & Lewis, *Microservices*, 2014-03-25](https://martinfowler.com/articles/microservices.html) | **T1**（领域奠基文章） | 2014-03-25 | 2026-11-23 | 页面 | 服务边界/「How big is a microservice」/design for failure |
| S16 | [Fowler, *MonolithFirst*, 2015-06-03](https://martinfowler.com/bliki/MonolithFirst.html) | **T1**（领域权威） | 2015-06-03 | 2026-11-23 | 页面 | 先单体、边界稳定后再拆；粗粒度服务路径 |
| S17 | [Fowler, *MicroservicePremium*, 2015-05-13](https://martinfowler.com/bliki/MicroservicePremium.html) | **T1**（领域权威） | 2015-05-13 | 2026-11-23 | 页面 | 无复杂度驱动不要上微服务；额外部署/监控/一致性成本 |
| S18 | [Fowler, *Presentation Domain Data Layering*, 2015-08-26](https://martinfowler.com/bliki/PresentationDomainDataLayering.html) | **T1**（领域权威） | 2015-08-26 | 2026-11-23 | 页面 | 分层降低认知范围；依赖方向约束的理论依据 |
| S19 | [import-linter 2.15 — PyPI](https://pypi.org/project/import-linter/) | **T1**（包官方元数据） | 2026-09-04（2.15 发布） | 2026-11-23 | 2.15；Requires-Python >=3.10 | 版本/平台支持/依赖引入依据 |
| S20 | [import-linter 文档](https://import-linter.readthedocs.io/)（直取被 bot 校验拦截；检索摘要：contracts、lazy imports） | **T1**（官方文档，部分取证） | 未标注 | 2026-11-23 | v2.12/latest | `layers`/`forbidden`、lazy imports 入图、`exclude_type_checking_imports` |
| S21 | [Python: signal — Set handlers for asynchronous events](https://docs.python.org/3/library/signal.html) | **T1**（官方文档） | 未标注（3.x docs） | 2026-11-23 | Python 3.x | SIGTERM 是终止信号；`signal.signal` 注册处理器 |
| S22 | [Docker: Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/) | **T1**（官方文档，部分取证） | 未标注 | 2026-11-23 | 文档页 | bind mount 主机目录进容器；G9 的边界风险背景 |

---

## 9. 降级链记录

| 目标 | 首选 | 降级 | 结果 |
|------|------|------|------|
| import-linter 用法/契约 | readthedocs 全文 | **被 bot 校验拦截（403/验证页）** → PyPI 元数据 + 搜索结果摘要 + 已知契约类型 | 版本/平台/契约类型已取；精确配置语法留 Step 3 以 `lint-imports --help`/本地安装验证 |
| import-linter 延迟导入是否入图 | 官方文档 | 搜索结果「UI: Lazy imports」摘要 | 判定「会入图」；Step 9 负例测试再实证 |
| SQLite 只读 WAL 细节 | WAL 全文 | 抓取截断（仅前 144 行） | 采用 Overview 第 4 条（S6 L65）的权威表述；容器 ro 挂载留待 Step 9 实测 |
| Docker Desktop/WSL bind mount 细节 | 官方 bind mounts | 抓取文件缺失（路径/缓存） | 仅采用「bind mount 主机目录」通用语义；跨 OS 边界风险以 SQLite 官方同机约束为依据，标为「待实测」 |
| Redis 8.6 幂等 | 官方 Streams | 目标 `redis:7`（Q20） | 不使用 8.6 特性；继续 inbox 去重 |
| uvicorn 版本 | 官方 docs latest | 本地安装 0.54.0 | 以本地版本为准；文档用于行为语义 |

---

## 10. 未决问题（移交 Step 2/3）

> 下列 1/2/4/6 项已由用户裁决 **A/A/A/A**（2026-11-23）；3/5/7/8 留 Step 3 定稿。

1. **U-P055-1 双模式部署**：✅ 已裁决 A（2026-11-23）。
2. **U-P055-2 不拆策略/风控**：✅ 已裁决 A；拆分触发条件写入 DESIGN §未来演进。
3. **U-P055-3** import-linter 契约是否采用「layers + core-no-upward + api-no-trading + 负例」四件套？（Step 3）
4. **U-P055-4 延迟基准报告制**：✅ 已裁决 A（不设 CI SLO）。
5. **U-P055-5/7** 观测最小栈与 metrics 抓取鉴权口径？（Step 3）
6. **U-P055-6 SQLite 卷策略**：✅ 已裁决 A（named volume/原生盘；禁止 Windows→WSL bind mount）。
7. **U-P055-8** Mode R 进程管理用 NSSM/任务计划还是手工 runbook？（Step 3）
8. **服务命名/端口**：`P054_*` env 是否沿用（推荐沿用，避免破坏 P-054）；新 compose 文件名 `deploy/compose.services.yaml` 是否接受？
9. **是否顺手修 G14（`--bus fake`）**，还是登记为运维项？
10. **P-055 用例规模**：建议 +35~45 例（运行时 12 / 部署 8 / 门禁 8 / 基准 6 / 回归 5），门禁目标 `1420 + N`；是否接受？（G17/G18 修复与真实握手探针建议纳入用例）

---

## 11. 状态链

- **Step 1 调研完成（2026-11-23）**：本文件落盘；代码基线 `e67ebbe`；发现 G1-G16；决策点 U-P055-1..8 + 未决 10 项。
- **决策专项（2026-11-23）**：[RESEARCH_p055_decision_anchors](RESEARCH_p055_decision_anchors.md) 落盘——4 项高影响决策外部锚点 + 五维评分，推荐 A/A/A/A。
- **用户裁决（2026-11-23）**：**U-P055-1/2/4/6 = A/A/A/A 定案**（回写 §6/§10）。
- **Step 2 复审通过（2026-11-23，GLM-5.3-Flash 异构 ✅）**：[REVIEW_p055_step2](REVIEW_p055_step2_research.md)——G1-G16 **16/16 对码属实（0 幻觉）**、引用链合规、评分算术复算一致 → 文档级 0 P1；复审独立扫描新增 **G17（P1：FastAPI 零 WS 端点）/ G18（P1：api_worker 入口 factory+TLS 不可启动）/ G19（P2：api_worker 装配缺省）** 及 G4 扩展（主循环忙等），已并入本文件 §2.2/§3 并补 §7 三项验收读数（修正 R-1~R-6）→ **Step 2 关闭**。
- **Step 3 DESIGN 完成（2026-11-23）**：[DESIGN_p055_microservices](DESIGN_p055_microservices.md) 落盘——Mode S/R 拓扑与差异表、运行时补齐（三线程/主循环/信号/巡检/行情循环/readiness 接线）、**G17 WS 挂载设计**（双 Hub + `/ws/orders`、`/ws/market` + ticket 鉴权 + lifespan 订阅）、**G18 入口修复**（去 `factory=True`、TLS 双参、`WORKERS=1` + 真实 uvicorn 启动探针）、部署编排（compose/healthcheck/卷/非 root/两模式）、import-linter 3 契约 + 负例 + CI `arch-check`、`p055_bench_e2e.py` 四段口径、D1-D14 决策表（含被拒替代与代价）、I1-I12 不变式、U-D1..D5 四元块；**U-P055-3/5/7/8 定稿 A**。
- **Step 4 设计复审 PASS（2026-11-23）**：[REVIEW_p055_step4_design](REVIEW_p055_step4_design.md)（GLM-5.3-Flash ≠ 作者）——29 项引用对码 0 幻觉（uvicorn 0.54.0 实装、双 Hub 参数、三通道发布形状、env 矩阵全实证）；P2×6 已回写 DESIGN（C3 补 `services.ws_routes` / uvicorn 行号引用修正 / metrics 13 个指标族 / 读数 15 统一 / 心跳值 `<ts>:<pending>` 约束 / 收尾补 `heartbeat.stop()`）；文档级 **0 P1**。
- **Step 5 IMPL 完成（2026-11-23）**：[IMPL_p055_microservices](IMPL_p055_microservices.md) 落盘——B0-B3 逐处代码（`trading_worker`/`outbox_relay`/`market_gateway`/`api_worker`/`ws_routes` 新增/`api`）、C-1..C-18 实施澄清、**外部锚点 A1-A12**（uvicorn `ssl_context_factory` 双参与 worker 内可 pickle、app 实例与 `workers>1` 互斥、Starlette accept 前 close→403、FastAPI `Query`+lifespan、redis-py asyncio Pub/Sub/`aclose`、import-linter forbidden/layers 语义与 `.importlinter` 发现、SQLite WAL 禁网络文件系统、compose `service_healthy`、NSSM Control-C 优先、Python `SIGBREAK`、anyio `run_sync`）、社区实践采用/拒绝对照、5 个新测试文件映射、读数 15 项命令化、F-D1/F-D5/F-D6 显式落点。
- **Step 6 IMPL 异构复审 PASS（2026-11-23，reviewer GLM-5.3-Flash ≠ 作者）**：[REVIEW_p055_step6_impl](REVIEW_p055_step6_impl.md)——V1-V16 对码全过（版本锚 5/5 命中、ws_hub/api/api_worker/trading_worker/outbox_relay/market_gateway/ledger_store/gateway/bus/Dockerfile/TestClient/pickle 断言行号逐一核实）、外部锚点 A1-A12 复检通过；发现 **P1×1**（anyio `run_sync` 不转发 kwargs + `snapshot_and_stream` keyword-only，两种调用写法均 TypeError → 改 `functools.partial`）+ **P2×2**（`AsyncRedisBus.close()` 已存在 bus.py#L163-164，D-4/R-IMPL-1 撤销 bus.py 零改动；`ConsumerLoop` 属性名 `_consumer`/无 `batch`）+ **P3×3**（`run_embedded` 为改写 stub；redis 在主依赖非 `[services]`；QueryScheduler 构造签名留 Step 9）——**6 处当场回写 IMPL**，修复后文档级 0 P1。
- **Step 7 CHECKLIST 完成（2026-11-23）**：[CHECKLIST_p055_microservices](CHECKLIST_p055_microservices.md)——**M16 + T6 + C10 + I12 + D14 + G19 + F7 = 84 项断言落成**；分组覆盖 M（模块与代码）/ T（5 文件 19 例）/ C（门禁 10）/ I（I1-I12）/ D（D1-D14）/ G（G1-G19 研究锚点闭合）/ F（Step 6 六项发现 + A1-A12 复检回执）；实测列全部 `[待 Step 9]`（RULE-1 禁预填）；基线 1420/22/120/157·0/309/151/51/19/12 → 目标 ≥1437/22/≥120/159·0/≥316/≥156/51/19/13。
- **Step 8 四文档一致性通过（2026-11-23）**：RESEARCH / DESIGN / IMPL / CHECKLIST 交叉核对——**修正 9 处（均 P3）**：① IMPL §3.2 `self.batch` 残留改 `count` 关键字参数（F-S6-P055-3 漏改点）；② IMPL §3.4 「Step 9 需补 aclose」残留改 `await bus.close()` 零改动（F-S6-P055-2 漏改点）；③ IMPL §6 步 1 红列「新增 1-2 failed」澄清为 0 新增用例（market 不设独立用例，§3.13 即全集）；④ IMPL §10 状态链补齐 Step 6/7/8；⑤ DESIGN §16 状态链补齐 Step 5-8；⑥ DESIGN §11.6 tests 目标 ≥151 统一为 **≥156**（151+5 新文件）；⑦ CHECKLIST M7 版本口径统一 `import-linter>=2.0,<3`（IMPL §3.7 为准，替代 `>=2.15`）+ DoR 修正（M7「无」、M4「M5/M6」、M5「M6 同批共建」消除互指）；⑧ CHECKLIST 裸「读数 N」全部加「DESIGN §11」前缀（9 处）；⑨ CHECKLIST F6 收敛口径 = Step 9 对码后择一（显式传入需核签名 / 不传由守卫保证可运行）；另核 DESIGN `orders_limit` 无残留（D-9 闭合）、端口 8054 / 心跳值格式 / D1-D14 / I1-I12 / G1-G19 / C-1..C-18 / A1-A12 / 用例 19 例 / 门禁目标四文档一致。
- **Step 9 TDD + 门禁完成（2026-11-23）**：B0-B3 全部落码——`services/{trading_worker,outbox_relay,market_gateway,api_worker,api}.py` 改造 + `services/ws_routes.py` 新增 + `pyproject/uv.lock/tests.yml/spec_runner_adapter/Dockerfile/.env.services.example/deploy/*` + `scripts/p055_bench_e2e.py` + `docs/RUNBOOK_p055_deployment.md` + 5 测试文件（19 例）+ arch 负例 fixture。门禁实测 **1439 passed / golden 22 / `-k p054` 120 / mypy 159·0 / black 319 / tests 156·services 13·core 51·live 19 / `lint-imports` 3 kept（负例 exit 1）/ `uv lock --check` 0 / compose `config -q` 0 / core+live 零 diff**。两处校准回写：**C3 `allow_indirect_imports = true`**（默认含间接导入会误红 `api→ledger_store→ledger/orders`）；**lint 入口 = console script `lint-imports`**（2.17 无 `__main__`，U-D2 结案）。**唯一环境待验**：bench 实跑（Docker daemon 未运行、本机 6379 无 Redis）→ Step 10 读数 12。
- **Step 10 验收 PASS（2026-11-23）**：[REVIEW_p055_step10_acceptance](REVIEW_p055_step10_acceptance.md)——真实 Redis 7 双轮实跑（1k / 10k）**三零全中**（`dropped=0`/`pending_after=0`/`unsent_after=0`），T4 p50 1.21/1.22 ms、p99 2.66/2.98 ms；DESIGN §11 读数 10 **0.00% 单核**、读数 11 **200 / 503 `stale_*`**、O3 **0.47 s exit 0**；实跑暴露并修复 **F-B1/B2/B3/B9 四个 P1 + F-B5 harness 三缺陷**（`SyncRedisBus` adapter 形状、消费组懒创建、`XAUTOCLAIM` 三元素解包、入口 `__main__` 守卫、bench 跨跑复位/订阅延迟/扇出等待）；门禁 **1440 passed / 1 skipped** + 22/120/159·0/319/156·13·51·19 + lint 3 kept + lock + compose + 结构零 diff；CHECKLIST **84/84 ✅**。
- **下一步**：**待用户授权提交**（`feat(P-055): microservice decomposition …`）；P-055 十步全部完成。
- **代码变更**：Step 9-10 为落码步（B0-B3 + 实跑修复 F-B1/B2/B3/B9/F-B5）；Step 1-8 零代码。**未提交（未获授权）。**
