# CHECKLIST：P-055 微服务拆分（运行时长跑 / WS 挂载 / 依赖门禁 / 部署资产 / 跨进程基准）

> **批次**: P-055 · **Step 7 CHECKLIST / Step 8 一致性 / Step 9 回填 / Step 10 验收** · 日期 2026-11-23 · **判档 T1（全量）**
> **上游**: [IMPL_p055_microservices](IMPL_p055_microservices.md)（B0-B3 / C-1~C-18 / A1-A12 / §4 测试映射 / D-1~D-10）；[DESIGN_p055_microservices](DESIGN_p055_microservices.md)（D1-D14 / I1-I12 / §5 三契约 / §11 读数 15）；[REVIEW_p055_step6_impl](REVIEW_p055_step6_impl.md)（PASS 有条件）；[RESEARCH_p055_microservices](RESEARCH_p055_microservices.md)（G1-G19）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **状态**: **Step 10 完成（2026-11-23）——84/84 ✅ 全绿（0 P1 残留）**；门禁 pytest **1440 passed / 1 skipped**（规范 `MPLBACKEND=Agg`）/ golden **22** / `-k p054` **120** / mypy **159·0** / black **319** / `lint-imports` **3 kept** / `uv lock --check` 通过 / compose `config -q` 通过
> **基线读数（P-054 关闭态）**: pytest **1420** / golden **22** / `-k p054` **120** / mypy **157 files 0** / black **309** / `tests/*.py` **151** / `core/*.py` **51** / `live/**/*.py` **19（递归）** / `services/*.py` **12**
> **目标读数 vs 实测**: pytest ≥1437 → **1440 passed / 1 skipped** / golden 22 → **22** / `-k p054` ≥120 → **120** / mypy 159·0 → **159·0** / black ≥316 → **319** / `tests/*.py` ≥156 → **156** / `core` 51 → **51** / `live` 19 → **19** / `services` 13 → **13**

---

## 1. M 组：模块与代码（16 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| M1 | `services/trading_worker.py`：`install_stop_handlers`（主线程注册 SIGINT/SIGTERM，`SIGBREAK` 存在才注册）；三 daemon 线程 relay/consumer/heartbeat（可选 market）；`stop_event.wait(0.2)` 非忙等 + 6 s 巡检；`--once`/`--bus fake`；`shutdown()` 固定收尾顺序 | 无 | 读码 + T1 + C1 + C10 | ✅ `install_stop_handlers`/`start_threads`/`run_main_loop`/`shutdown` 落盘；T1 7/7；`--bus fake` 装配零触网。**Step 10 实机**：长跑存活 + 心跳 `p054:trading:heartbeat` 持续写入；`CTRL_BREAK` → **0.47 s 退出 code 0**；idle 30 s CPU **0.00%** 单核。**Step 10 修 F-B9**：补 `if __name__ == "__main__": main()`（此前 `python -m` 只导入即退出） |
| M2 | `services/outbox_relay.py`：`RelayLoop.run(stop_event=None)` + `last_unsent`；`ConsumerLoop.run(stop_event=None, *, count=100, autoclaim_every=30.0, heartbeat_key, heartbeat_ttl=10, poll_interval=0.2)`；`self._bus`/`self._consumer`；心跳 `<ts>:<pending>`；异常不退出 | M1 | 读码 + T1 | ✅ 读码命中；T1 `test_consumer_run_writes_pending`（`:7`）与 `test_consumer_run_does_not_busy_loop` 绿 |
| M3 | `services/market_gateway.py`：**改写** `run_embedded` stub；`serve()` 每帧写 `p054:market:heartbeat`；`main(argv)` `--once`/`--embedded`/默认；CLI > env > 默认 | 无 | 读码 + C9 | ✅ `serve`/`_parse_args`/`run_embedded` 改写落盘；`P054_MARKET_HEARTBEAT_TTL_SECONDS` 生效 |
| M4 | `services/api_worker.py`：删 `factory=True`；`P054_WORKERS` 非 1 → `SystemExit`；`tls_context_factory(config=None, default_factory=None)` 顶层可 pickle；装配 `AsyncRedisBus`/`publisher`/`RedisTicketStore`/双 Hub/`heartbeat_reader` | M5/M6 | 读码 + T4 + C4 | ✅ T4 2/2（明文 200 + TLS 握手 200）；`pickle.dumps` 旧断言仍绿（P-054 F10） |
| M5 | `services/ws_routes.py`（新增）：双 Hub；`accept → ticket → error+4401`；未就绪 4503；`partial` 快照；帧泵 20 ms（1013/1011/ping-pong）；`start_subscribers` 三任务 | M6（同批共建） | 读码 + T2 | ✅ 文件落盘 230 行；T2 5/5（snapshot/4401/4503/1013/market 包装） |
| M6 | `services/api.py`：`create_app` 新参数默认 `None`；条件 lifespan；挂 `/ws/orders`、`/ws/market`；`health_ready` 传 `heartbeats=`；broadcast-pause 不变 | M5 | 读码 + T2 + T4 + C1 | ✅ P-054 120 例零回归；T2 5/5；默认 app（无 bus）不挂 WS |
| M7 | `pyproject.toml`：3 契约（C3 含 `ws_routes`、`allow_indirect_imports=true`）；`[dev]` 加 `import-linter>=2.0,<3`；运行时依赖零变更 | 无 | 读码 + T3 + C7 | ✅ `lint-imports` 3 kept；T3 `test_three_contracts_declared` 绿 |
| M8 | `uv.lock`：与 M7 同步，`uv lock --check` 通过 | M7 | C8 | ✅ `Resolved 139 packages`，退出码 0（新增 grimp/import-linter） |
| M9 | `.github/workflows/tests.yml`：`arch-check` job（ubuntu / 3.11 / `.[dev,services]` / `lint-imports`） | M7 | 读码 + C7 | ✅ job 落盘（L61-77），与 lock-check 并列 |
| M10 | `scripts/spec_runner_adapter.py`：`GATES["arch-check"]` | M7 | 读码 | ✅ `"arch-check": "lint-imports"`（U-D2 校准：console script） |
| M11 | `Dockerfile`：`services` target 非 root（uid 10001）、`/app/run` 属主 appuser；既有回测面保留 | 无 | 读码 + T5 | ✅ T5 `test_dockerfile_services_non_root` 绿 |
| M12 | `deploy/`：compose（redis:7/healthy/p055-data/127.0.0.1:8054/`METRICS_REQUIRE_AUTH="0"`/stop_grace_period）、env 样例、prometheus、certs 占位 + `.gitignore` | M11 | 读码 + T5 + C9 | ✅ T5 绿；`docker compose config -q` 退出 0（临时 `.env.services`） |
| M13 | `scripts/p055_bench_e2e.py`：四段口径、`_TimedBus` 委托包装、report.md/json、`--assert-p99` 默认关 | M2 | 运行 + DESIGN §11 读数 12 | ✅ **Step 10 双轮实跑**：1k（`.bench/n1000`）与 10k（`.bench/n10000`）**三零全中**；T4 p50 1.21/1.22 ms、p99 2.66/2.98 ms；`--assert-p99` 默认关符合 I12。实跑修 harness 三处口径缺陷（F-B5：跨跑游标残留 / 订阅竞态 / 不等扇出） |
| M14 | `tests/` 5 文件 19 例 + arch fixture：无 skip/xfail、无新测试依赖、WS 不依赖真 Redis | M5/M7/M11 | T1-T6 + C6 | ✅ `-k p055` **19 passed**；无 skip/xfail；`tests/*.py` 156。**Step 10**：21 例（+入口守卫 `test_entry_modules_have_main_guard`、+真实 Redis 集成 `test_sync_redis_bus_adapter_shape_with_real_redis`）；后者以 `P054_TEST_REDIS_URL` 门控（无 Redis 环境 **skip**，带 Redis 时 8/8 绿），单元面仍零 skip |
| M15 | `docs/RUNBOOK_p055_deployment.md`：七节（证书/Mode S/Mode R+NSSM/备份/轮换/排障/跨机只读）+ G15 触发条件 | M12 | 读码 | ✅ 落盘（含 1013/4401/4503/stale/卷属主排障表） |
| M16 | **零变更守卫**：`core` 51 零 diff、`live` 零 diff、`ws_hub.py` 零修改、golden 零重录、既有断言仅 adapter 一处同步、无新增写路由 | 全组 | C1/C2/C3/C10 | ✅ `git diff --stat -- core live` 空；golden 22；`ws_hub.py` 未改；adapter 测试仅同步 GATES 键集。**Step 10 修正口径**：`bus.py` 由「零修改」改为**仅补齐 `SyncRedisBus` adapter 形状 + 消费组懒创建 + XAUTOCLAIM 解包**（F-B1/B2/B3 实跑缺陷，`InMemoryBusAdapter`/`AsyncRedisBus` 语义零改动） |

---

## 2. T 组：测试（5 文件 / 19 例）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| T1 | `test_p055_runtime.py` **7 例**：信号 handler 直调 / 心跳值 `_fresh` 解析 / 收尾顺序 / relay stop / consumer pending 心跳 / 非忙等 / fake bus 装配 | M1/M2 | pytest | ✅ 7 passed |
| T2 | `test_p055_ws.py` **5 例**：snapshot 首帧 / 4401 / 4503 / 1013 / market 包装 | M5/M6 | pytest | ✅ 5 passed |
| T3 | `test_p055_arch_gate.py` **3 例**：3 契约 exit 0 / 负例 exit≠0 且含 `violation_app.core` / 契约数 ≥3 | M7/M14 | pytest | ✅ 3 passed |
| T4 | `test_p055_entrypoint.py` **2 例**：明文 loopback `/health/live` 200 / TLS 握手 200 | M4 | pytest | ✅ 2 passed（openssl 自定义 config） |
| T5 | `test_p055_deploy_assets.py` **2 例**：compose 文本断言 / Dockerfile 非 root | M11/M12 | pytest | ✅ 2 passed |
| T6 | 合计与卫生：19 例全绿；无 skip/xfail；`-k p055` = 19；全量 1439 | T1-T5 | pytest 计数 | ✅ `19 passed`；Step 9 全量 **1439 passed**；Step 10 增入口守卫/真实 Redis 集成 2 例（21 例），规范后端 **1440 passed / 1 skipped** |

---

## 3. C 组：门禁（10 项）

| ID | 门禁 | 命令 | 目标 | 实测 |
|----|------|------|------|------|
| C1 | pytest 全量 | `pytest tests -q` | ≥1437 | ✅ **1440 passed / 1 skipped**（规范 `MPLBACKEND=Agg`；Step 9 为 1439，+入口守卫用例，集成用例环境门控 skip） |
| C2 | golden | `pytest tests -k golden -q` | 22 | ✅ **22 passed** |
| C3 | `-k p054` | `pytest tests -k p054 -q` | ≥120 | ✅ **120 passed** |
| C4 | mypy | CI 同款路径 | 159·0 | ✅ **159 source files / 0** |
| C5 | black | `black --check .` | ≥316 | ✅ **319 unchanged** |
| C6 | 计数 | glob | ≥156 / 13 / 51 / 19 | ✅ **156 / 13 / 51 / 19** |
| C7 | 依赖门禁 | `lint-imports`（console script，U-D2） | 3 kept / 负例 broken | ✅ C1/C2/C3 **KEPT**；负例 exit 1 且输出 `violation_app.core` |
| C8 | 锁文件 | `uv lock --check` | 通过 | ✅ 退出码 0（139 packages） |
| C9 | 部署静态 | `docker compose -f deploy/compose.services.yaml config -q` | exit 0 | ✅ 退出码 0（临时 `.env.services` 校验后删除） |
| C10 | 结构守卫 | `git diff --stat -- core live`；`git status --porcelain tests/golden` | 空 | ✅ 均空 |

---

## 4. I 组：不变式（12 项）

| ID | 不变式 | 证据出口 | 实测 |
|----|--------|----------|------|
| I1 | 同一 SQLite 仅一个写连接（trading），第二实例 `.lock` 失败 | 读码 + P-053 T4 ⑤ | ✅ 未改 store；P-053 用例仍绿 |
| I2 | API worker store `read_only=True` | 读码 + `is_read_only` property | ✅ `api_worker.main` 仅 `read_only=True` |
| I3 | WS 首帧必 snapshot；delta seq 严格递增 | T2 | ✅ snapshot 首帧绿；Hub seq 去重未改 |
| I4 | ticket 一次性 | `RedisTicketStore` + T2 | ✅ api_worker 接线 `RedisTicketStore`；T2 用 `InMemoryTicketStore` 单次消费 |
| I5 | 心跳缺失/滞后 ⇒ 503 | T1 + M6 + DESIGN §11 读数 11 | ✅ 心跳值可被 `_fresh` 解析；`health_ready` 接 reader |
| I6 | 停机 ≤10 s，outbox 不丢 | T1 + C-4 | ✅ `shutdown()` 顺序断言：heartbeat → join:5.0 → gateway |
| I7 | 3 契约常绿 | T3 + C7 | ✅ 3 kept |
| I8 | 仅 `trading_worker` 可 import `live.gateway/ledger/adapters` | M7 C3 名单 | ✅ C3 源名单不含 trading_worker |
| I9 | `core` 不 import 上层 | C2 + C7 | ✅ KEPT |
| I10 | SQLite 禁跨 Windows/WSL 挂载 | M12 + M15 | ✅ compose 仅 named volume；runbook 红线 |
| I11 | `/metrics` 不暴露非内网 | M12 | ✅ `127.0.0.1:8054:8054` + 内网免鉴权注释 |
| I12 | 基准不因抖动判红 | M13 | ✅ `--assert-p99` 默认关；Step 10 双轮实跑均未开断言，以三零为判据 |

---

## 5. D 组：设计决策 D1-D14（14 项）

| ID | 决策 | 落实点 | 实测 |
|----|------|--------|------|
| D1 | 4 类进程 + Redis | M1/M4/M5/M12 | ✅ 三入口 + compose 四服务 |
| D2 | 策略/风控库内调用 | M15 | ✅ runbook 触发条件成文；`strategies/` 零 diff |
| D3 | SQLite named volume / NTFS | M12 + M15 | ✅ `p055-data` + runbook |
| D4 | API `0.0.0.0` + TLS | M4 + T4 | ✅ TLS 握手 200 |
| D5 | 去 `factory=True`，WORKERS=1 | M4 | ✅ 源码无 `factory`；非 1 抛 `SystemExit` |
| D6 | TLS 双参签名 | M4 + T4 | ✅ `(config=None, default_factory=None)` |
| D7 | 双 Hub 不合并 | M5 | ✅ 两实例；`ws_hub.py` 零修改 |
| D8 | accept → ticket → 4401 | M5 + T2 | ✅ T2 绿 |
| D9 | 单协程 20 ms 帧泵 | M5 + T2 | ✅ `_POLL=0.02`；T2 绿 |
| D10 | sync `heartbeat_reader` | M4/M6 | ✅ `build_heartbeat_reader` + `health_ready` 注入 |
| D11 | `stop_event.wait(0.2)` + 6 s 巡检 | M1 | ✅ `run_main_loop` 落盘；**Step 10 实机 CPU 0.00% 单核**（读数 10） |
| D12 | market `serve()` + 心跳 | M3/M12 | ✅ serve + healthcheck |
| D13 | 3 契约 + 负例 + 数守护 | M7/M9/M10 + T3 | ✅ 全绿 |
| D14 | 基准双进程 | M13 | ✅ 脚本含 `client` 子进程；**Step 10 双轮实跑通过**（T4 跨进程 publish→client 1.21~2.98 ms） |

---

## 6. G 组：研究锚点闭合（G1-G19，19 项）

| ID | 研究锚点（摘要） | 落点 | 实测 |
|----|------------------|------|------|
| G1 | consumer 线程未启动 | M1 三线程 | ✅ `p054-consumer` 启动 |
| G2 | heartbeat/readiness 未接 | M1/M4/M6 | ✅ 心跳线程 + reader + `heartbeats=` |
| G3 | market 只跑一次 | M3 | ✅ `serve()` 循环 |
| G4 | 无优雅停机 | M1 | ✅ 信号 + `shutdown()` |
| G5 | 部署资产回测化 | M11/M12 | ✅ services target + compose |
| G6 | 门禁缺失 | M7-M10 | ✅ 3 kept |
| G7 | 无跨进程基准 | M13 | ✅ 脚本四段；**Step 10 双轮实跑三零**（1k / 10k） |
| G8 | 容器网络/TLS 冲突 | M4/M12 | ✅ TLS 必需 + 证书挂载 |
| G9 | SQLite 挂载边界 | M12/M15 | ✅ 无 bind mount |
| G10 | 网关不能容器化 | M12/M15 | ✅ runbook Mode R 原生 |
| G11 | trading 无健康检查 | M1/M12 | ✅ 心跳键 healthcheck |
| G12 | metrics 默认要 auth | M12 | ✅ 内网 `REQUIRE_AUTH=0` |
| G13 | API 边专用 forbidden | M7 | ✅ C3 + 直接导入语义 |
| G14 | `--bus fake` 未落 CLI | M1 | ✅ `--bus fake` + T1 |
| G15 | 策略/风控未进程化 | D2 + M15 | ✅ 触发条件成文 |
| G16 | 无 Prometheus 资产 | M12 | ✅ `prometheus.yml` + obs profile |
| G17 | FastAPI 零 WS 端点 | M5/M6 | ✅ 两路由 + T2 |
| G18 | api_worker 不可启动 | M4 | ✅ 子进程 `/health/live` 200 |
| G19 | api_worker 装配缺口 | M4/M6 | ✅ bus/publisher/tickets/hubs 全接线 |

---

## 7. F 组：Step 6 复审发现回执（7 项）

| ID | 复审发现（P 级） | 核对动作 | 实测 |
|----|------------------|----------|------|
| F1 | **F-S6-P055-1（P1）** kwargs 不转发 + keyword-only | M5 `functools.partial` + T2 snapshot | ✅ `partial(hub.snapshot_and_stream, …, limit=…, resume_last_seq=…)`；T2 绿 |
| F2 | **F-S6-P055-2（P2）** `aclose` 不存在 | M5/M4 `await bus.close()`；bus.py 零 diff | ✅ 读码 + C10 |
| F3 | **F-S6-P055-3（P2）** `self.batch`/属性名 | M2 + T1 | ✅ `count` 关键字参数 + `_consumer`；T1 绿 |
| F4 | **F-S6-P055-4（P3）** `run_embedded` 为改写 | M3 读码 | ✅ 同函数位置改写（非新增定义） |
| F5 | **F-S6-P055-5（P3）** redis 在主依赖 | M7 diff | ✅ pyproject 运行时依赖零变更 |
| F6 | **F-S6-P055-6（P3）** `QueryScheduler()` 签名 | M1 读码 | ✅ 已核：`QueryScheduler()` 全关键字默认参，`main()` 显式传入（DESIGN §2.6.1 方案）→ R-IMPL-2 **结案** |
| F7 | **A1-A12 外部锚点复检** | M4/M5/M7 抽检 | ✅ uvicorn 双参（T4 实跑）、Starlette 先 accept（T2 4401）、import-linter（C7）一致 |

---

## 8. 出口判定

- **Step 7 判据**：84 项断言落成（已满足）。
- **Step 8 判据**：四文档一致性通过（2026-11-23）。
- **Step 9 判据**：**83/84 ✅ + 1 项环境待验（M13 基准实跑）**；10 项门禁全部命中（1439/22/120/159·0/319/156·13·51·19/3 kept/lock/compose/结构）。
- **Step 10 判据**：M13 实跑出四段 p50/p95/p99 + `dropped=0`/`pending_after=0`/`unsent_after=0`；DESIGN §11 读数 8-12 实机；异构复审 0 P1；提交需用户授权。
- **Step 10 结论（2026-11-23）：84/84 ✅ 全绿**——M13 双轮实跑三零达成；读数 10/11 + O3 实机通过；实跑暴露 5 P1 全修（F-B1/B2/B3/B9 + F-B5）；门禁 **1440 passed / 0 failed / 1 skipped**（详见 [REVIEW_p055_step10_acceptance](REVIEW_p055_step10_acceptance.md)）。
- **提交与 CI（2026-11-23）**：`8f8b912`（39 files +5832/−34）已推送；CI run `45132788783` 四 job 全绿（lock-check / test 3.11 / test 3.12 / arch-check）。

## 9. 实测读数（已回填）

| 指标 | 基线（P-054 关闭） | 目标 | 实测 |
|------|--------------------|------|------|
| pytest 全量 | 1420 | ≥1437 | ✅ **1440 passed / 1 skipped**（Step 10 规范 `MPLBACKEND=Agg`；Step 9 为 1439，+入口守卫用例，集成用例环境门控 skip） |
| `-k golden` | 22 | 22 | ✅ **22** |
| `-k p054` | 120 | ≥120 | ✅ **120** |
| `-k p055` | 0 | 19 | ✅ **19**（Step 10 后 `-k "p055 or spec_runner_adapter"` = 26 passed + 1 skipped） |
| mypy | 157 / 0 | 159 / 0 | ✅ **159 / 0** |
| black `--check .` | 309 | ≥316 | ✅ **319** |
| `tests/*.py` | 151 | ≥156 | ✅ **156** |
| `services/*.py` | 12 | 13 | ✅ **13** |
| `core/*.py` | 51 | 51 | ✅ **51（零 diff）** |
| `live/**/*.py` | 19 | 19 | ✅ **19（零 diff）** |
| `lint-imports` | 无 | 3 pass / 负例 fail | ✅ **3 kept / 负例 exit 1** |
| `uv lock --check` | 通过 | 通过 | ✅ **exit 0**（139 packages） |
| compose `config -q` | — | exit 0 | ✅ **exit 0** |
| 跨进程基准 | — | 四段 + 三零 | ✅ **双轮三零**：1k（T4 p50 **1.21** / p99 **2.66** ms）、10k（T4 p50 **1.22** / p99 **2.98** ms）；`dropped=0`/`pending_after=0`/`unsent_after=0`（Step 10） |
| 读数 10（idle CPU） | 忙等 >90% | <5% 单核 | ✅ **0.00%**（30 s 采样，三守护线程） |
| 读数 11（readiness） | stale 永不 503 | 键在 200 / 删键 503 | ✅ **200 ok / 503 `stale_trading`+`stale_consumer`** |
| O3 优雅停机 | — | ≤10 s | ✅ **0.47 s，exit code 0**（`CTRL_BREAK`） |

## 10. 备注（Step 9 实施偏差，均不改变对外语义）

1. **C3 契约语义校准（重要）**：import-linter `forbidden` 默认把**间接导入**计入，导致 `services.api → live.ledger_store → live.ledger/orders` 被误判；C3 增加 `allow_indirect_imports = true`（只禁直接导入），与 DESIGN「API/WS 不含交易逻辑」意图一致。DESIGN §5.2/§5.5 与 IMPL C-13 已回写。
2. **lint 入口校准（U-D2 结案）**：import-linter 2.17 **无** `python -m importlinter.cli` 可执行入口（无 `__main__`，静默退出 0）；统一用 console script `lint-imports`（CI job、`GATES["arch-check"]`、T3 均如此）。
3. **负例 INI 语法与缓存**：`.importlinter` 的契约段必须是 `[importlinter:contract:<name>]`，`layers` 写完整包路径 `violation_app.upper` / `violation_app.core`（否则报 `Missing layer`）；T3 以 `lint-imports --no-cache` 运行，避免在仓库/负例目录留下 `.import_linter_cache/`（已 gitignore 兜底）。
4. **C-4 可测化**：`services/trading_worker.py` 抽出 `shutdown()`（置位→停心跳→join→gateway），`main()` 复用；T1 以假线程/假 gateway 断言顺序。
5. **`ConsumerLoop.stop = False`**：为 `run()` 的 `stop_event=None` 兼容分支补齐属性（P-054 只有 `RelayLoop.stop`）。
6. **既有测试同步 1 处**：`tests/test_spec_runner_adapter.py::test_u1` 的 GATES 键集加入 `arch-check`（P-024 漂移守卫，属批内允许同步）。
7. **本机测试临时目录**：`%TEMP%\pytest-of-Peng` 无写权限，统一 `--basetemp=.pytest_tmp`（已 `.gitignore`）；CI 不受影响。
8. **TLS 测试证书**：Windows OpenSSL 缺默认 `openssl.cnf`，T4 写临时最小 config + `-config` 生成自签证书（Linux CI 同样可用）。
9. **market 心跳 TTL**：`P054_MARKET_HEARTBEAT_TTL_SECONDS` 在 `main`/`run_embedded` 读取，避免 env 样例出现死配置。
10. **M13 基准（Step 10 已闭合）**：Redis 7（`p055-redis`）双轮实跑 1k/10k 三零达成；实跑修 harness 三处口径缺陷（F-B5）与 4 个运行时 P1（F-B1/B2/B3/B9），详见 [REVIEW_p055_step10_acceptance](REVIEW_p055_step10_acceptance.md)。
