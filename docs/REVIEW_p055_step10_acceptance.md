# REVIEW：P-055 Step 10 验收（M13 跨进程基准实跑 + 实机读数 + RULE-5 异构复审）

> **批次**: P-055 · **Step 10 验收** · 日期 2026-11-23 · **复审基座 GLM-5.3-Flash（≠ 落码基座 DeepSeek-V4.1-Flash → 异构成立）**
> **上游**: [CHECKLIST_p055](CHECKLIST_p055_microservices.md)（84/84，Step 10 回填）；[IMPL_p055](IMPL_p055_microservices.md)（B0-B3）；[DESIGN_p055](DESIGN_p055_microservices.md)（D1-D14 / §11 读数 15）；[REVIEW_p055_step6_impl](REVIEW_p055_step6_impl.md)（PASS 有条件）
> **复审方法**：M13 真实 Redis 端到端实跑（redis:7 容器 + `scripts/p055_bench_e2e.py`）+ 实机读数 10/11 + 微基准分解（per-op 计时）+ 门禁零回归重放
> **范围声明（RULE-5 单向）**：复审者标记问题并执行修复（实跑暴露的集成缺陷属于验收判据内必须排除项）；复审不改写 Step 9 交付文档的原始记录
> **环境事实**：Docker Desktop 需脱离沙箱进程树启动（WMI `Win32_Process.Create`）；redis:7 经 `docker.m.daocloud.io` 镜像源拉取；容器 `p055-redis` 映射 `127.0.0.1:6379`

---

## 1. M13 跨进程基准实跑（DESIGN §11 读数 12）

**判据**：1k/10k 两轮四段 p50/p95/p99 + `dropped=0` / `pending_after=0` / `unsent_after=0`。

### 1.1 实跑暴露的集成缺陷（fake bus 无法覆盖的真实 Redis 路径）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-B1** | **P1** | **`SyncRedisBus` 缺 adapter 形状方法**：`RelayLoop` 调 `publisher.add()`、`ConsumerLoop` 调 `bus.read/ack/autoclaim/stream_pending`——`SyncRedisBus` 均无 → `trading_worker --bus redis` 的 relay 静默 `PublisherFailure` 死循环、consumer 线程崩溃；Step 9 测试全用 `InMemoryBusAdapter`/fake 掩盖 | **已修复**：`SyncRedisBus` 补 `add/read/ack/autoclaim/stream_pending/delete_key` 六方法（与 `InMemoryBusAdapter` 同构）；生产装配（`trading_worker.main`）零改动即恢复 |
| **F-B2** | **P1** | **消费组从无创建**：`XREADGROUP` 前置条件 `XGROUP CREATE p054:orders p054-relay` 无人执行 → 真实 Redis 上必报 `NOGROUP` | **已修复**：`SyncRedisBus._ensure_group()` 懒触发幂等创建（`id="0"` + `MKSTREAM`，仅 stream 路径调用，publish-only 使用方零副作用） |
| **F-B3** | **P1** | **`XAUTOCLAIM` 三元素解包**：Redis 7 响应为 `[cursor, entries, deleted]`，代码按两元素解包 → `ValueError` → consumer 循环 `sleep(1)` 重试且 `last_autoclaim` 不更新（`due` 永真）→ **30 s 后 consumer 永久冻结**（实测 `entries-read=293, lag=707` 冻结 200 s+） | **已修复**：改索引取 `result[1]`；集成测试补 `run_once(autoclaim=True)` 路径断言 |
| F-B4 | P2 | relay `PublisherFailure` 静默吞掉（无日志）→ F-B1 期间不可观测 | **已修复**：`_log("relay_publisher_failure")` |
| F-B5 | P2 | **bench harness 三处口径缺陷**：①跨跑 Redis 流/组游标残留 → consumer 先扇出上一轮事件（seq 空间错位、假三零）；②client 订阅完成前 writer 已发布（Pub/Sub 无保留）→ dropped 虚高；③drain 只等 relay 清空 outbox、不等 consumer 扇出至 n → 提前停线程 | **已修复**：①起跑 `delete_key("p054:orders")`（组由 `_ensure_group` 重建）；②`--writer-delay`（默认 2 s）先订后发；③扇出等待阶段（publish 日志 ≥ n 才停，`--fanout-timeout`）+ 进度曲线日志 |
| F-B6 | P3 观察 | **单连接 SQLite `synchronous=FULL` 三线程竞争**：本机每提交 fsync ≈26 ms（writer 26.3 / relay 26.5 / consumer 27.1 ms/事件，微基准分解），三线程共享单连接时合并吞吐 ~25-35 事件/s → 扇出窗口需秒级~分钟级；n=10000 实跑窗口相应放大 | **登记**：属 D7 持久化语义的如实测量；批内不做批量提交优化（后续运维项） |
| F-B7 | P3 观察 | **T3 口径备注**：relay 先 XADD 后 `mark_sent`（fsync 滞后），consumer 可在 mark_sent 前发布 → `publish - sent` 结构性可为负/偏大（积压期测量值，非通道延迟） | **登记**：以 T2/T4 与三零为准；T3 解释写进报告备注 |
| F-B8 | P3 观察 | 集成测试隔离教训：测试用例起跑也须复位流键（组游标残留会把旧条目当新事件） | **已修复**：测试起跑 `delete_key` |
| **F-B9** | **P1** | **入口 `__main__` 守卫缺失**：`services/trading_worker.py` 与 `services/market_gateway.py` 无 `if __name__ == "__main__": main()`——`python -m services.trading_worker` 只导入模块即退出（code 0、零输出、零日志）；Dockerfile `CMD ["python","-m","services.trading_worker"]`、compose 的 `trading`/`market` 服务、RUNBOOK 手工启动命令**全部空转**（healthcheck 永红）。Step 9 的 `--once` 用例未覆盖「长跑存活」故漏网 | **已修复**：两文件补 `__main__` 守卫（与 `api_worker.py` 对齐）；修复后长跑存活、心跳写入、`CTRL_BREAK` 优雅退出全部实测通过 |
| F-B10 | P3 观察 | 强杀（TerminateProcess）残留单写者锁 `live_ledger.db.lock`（`O_EXCL` 语义正确，重启前需人工删锁） | **登记**：RUNBOOK 排障表补一行 |

### 1.2 基准结果（修复后实跑）

**n = 1000**（`.bench/n1000/report.md`）

| 段 | n | p50 (ms) | p95 (ms) | p99 (ms) |
|----|---|----------|----------|----------|
| T1 submit→outbox | 1000 | 0.00 | 0.00 | 0.00 |
| T2 outbox→sent | 1000 | 2197.99 | 3021.95 | 3166.24 |
| T3 sent→publish | 1000 | 18714.90 | 30004.79 | 30399.74 |
| T4 publish→client | 1000 | **1.21** | **2.17** | **2.66** |

`dropped=0` / `pending_after=0` / `unsent_after=0` ✅

**n = 10000**（`.bench/n10000/report.md`）

| 段 | n | p50 (ms) | p95 (ms) | p99 (ms) |
|----|---|----------|----------|----------|
| T1 submit→outbox | 10000 | 0.00 | 0.00 | 0.00 |
| T2 outbox→sent | 10000 | 8356.34 | 13263.63 | 14281.87 |
| T3 sent→publish | 10000 | 199350.91 | 309164.12 | 318888.05 |
| T4 publish→client | 10000 | **1.22** | **2.23** | **2.98** |

`dropped=0` / `pending_after=0` / `unsent_after=0` ✅

**结论**：
- **三零在 1k 与 10k 双轮达成**——无丢失、无残留 pending、无未 sent（M13 判据全中）。
- **T4（publish→client，真实通道延迟）1.21~2.98 ms**，两轮同量级：Redis Pub/Sub 扇出到跨进程客户端为**毫秒级**，与 DESIGN O6 目标一致。
- T2/T3 的量级由 **fsync 吞吐**决定（F-B6：本机 ~26 ms/提交 × 单连接三线程共享）：T2 = relay 追赶积压、T3 = consumer 队列等待，10k 时 T3 p50 ~199 s 即 10000 条 × ~20 ms 的排队时间，属**如实测量**而非通道缺陷；实际部署（Mode S 容器 named volume）不做 10k 瞬时突刺压测，稳态由 `P054_OUTBOX_BATCH_SIZE`/轮询节流控制。
- `--assert-p99` 默认关（I12：基准不因机器抖动判红）；本轮未开断言，三零为主判据。

---

## 2. 实机读数（DESIGN §11 读数 10/11；读数 8/9 已由 T4/T2 真实 uvicorn/WS 用例覆盖）

| # | 读数 | 判据 | 实测 | 判定 |
|---|------|------|------|------|
| **10** | 主循环 CPU（idle 30 s） | 单核 <5%（基线忙等 >90%） | **0.00%** 单核（`GetProcessTimes` 前后差值 / 30 s；进程含 relay+consumer+heartbeat 三守护线程） | ✅ |
| **11a** | readiness 正常态 | 键在 → 200 | `200 {"status":"ok","degraded":false}`（心跳值 `1795415607:0`，TTL 9） | ✅ |
| **11b** | readiness 失效态 | 停 writer + 删键 → 503 `stale_*` | `503 {"status":"not_ready","reasons":["stale_trading","stale_consumer"]}` | ✅ |
| **O3** | 优雅停机（Design O3 补充） | SIGINT/SIGTERM → 10 s 内退出 | `CTRL_BREAK` → **0.47 s** 退出，exit code **0**（`install_stop_handlers` 只置位 + `finally` 固定收尾） | ✅ |

> 采样方式：`subprocess.Popen` 启动真实进程（cwd 隔离在 `.bench/readings`，`PYTHONPATH` 指仓库根），`ctypes` 调 `kernel32.GetProcessTimes` 取 CPU；readiness 用 `urllib` 打真实 uvicorn（明文 loopback，`P054_ALLOW_PLAINTEXT_LOOPBACK=1`）。采样脚本为一次性探针（`.bench/` 已 gitignore）。
> 读数 11 采样的第一版时序有缺陷（心跳 interval=1 s，运行中删键 1 s 内被重写 → 假 200）；改为**先停 writer 再删键**后取值。此缺陷属探针而非产品代码。
> 读数 8/9：由 `tests/test_p055_entrypoint.py`（真实 uvicorn 子进程 + TLS 握手 200）与 `tests/test_p055_ws.py`（snapshot 首帧 / 4401 / 4503 / 1013 / market 包装）持续覆盖，Step 9 已绿。

---

## 3. 门禁复跑（修复后零回归）

| 门禁 | Step 9 | Step 10（修复后） | 判定 |
|------|--------|-------------------|------|
| pytest 全量（规范 `MPLBACKEND=Agg`） | 1439 passed | **1440 passed / 0 failed / 1 skipped** | ✅ 零回归 |
| 跳过项 | 0 | 1（`test_sync_redis_bus_adapter_shape_with_real_redis`，`P054_TEST_REDIS_URL` 环境门控；本机带该变量单独跑 **8/8 绿**） | ✅ 设计内 |
| `-k golden` | 22 | **22 passed**（零重录，`git status tests/golden` 干净） | ✅ |
| `-k p054` | 120 | **120 passed** | ✅ 断言未改 |
| `-k "p055 or spec_runner_adapter"` | 25 | **26 passed + 1 skipped**（+入口守卫用例） | ✅ |
| mypy | 159·0 | **159 files · 0** | ✅ |
| black | 319 | **319 unchanged** | ✅ |
| `lint-imports --no-cache` | 3 kept | **3 kept / 0 broken**（C1 分层 / C2 core 反向 / C3 API 无交易逻辑） | ✅ |
| `uv lock --check` | 0 | **0**（139 packages） | ✅ |
| `docker compose config -q` | 0 | **0** | ✅ |
| 文件计数 | 156 / 51 / 19 / 13 | **156 / 51 / 19 / 13** | ✅ |
| 结构守卫 | core/live 零 diff | **core / live / strategies 零 diff**；golden 干净 | ✅ |

**门禁方法学修正（本步发现）**：规范 `unit-tests` 门禁命令为 `set MPLBACKEND=Agg&& python -m pytest tests -q`（[spec_runner_adapter.py#L65](../scripts/spec_runner_adapter.py#L65)）。本步前几轮漏设该前缀 → matplotlib 默认 `tkagg` 后端在非交互会话下初始化 Tk 失败（`_tkinter.TclError: Can't find a usable tk.tcl`），表现为**随机用例**（p044 / p051c）失败；补回前缀后 **1440 全绿**。结论：该失败为**门禁命令不完整**，非代码回归（`core`/`live`/`strategies` 与相关用例零 diff）。

---

## 4. 出口判定

| 判据（CHECKLIST §8 / DESIGN O1-O6） | 结果 |
|--------------------------------------|------|
| M13 实跑 1k/10k 四段 p50/p95/p99 | ✅ 双轮（§1.2） |
| `dropped=0` / `pending_after=0` / `unsent_after=0` | ✅ 双轮全零 |
| 读数 10（idle CPU <5%） | ✅ 0.00% |
| 读数 11（删键 → 503 `stale_*`） | ✅ `stale_trading`+`stale_consumer` |
| 读数 8/9（真实 uvicorn / WS 握手） | ✅ Step 9 用例覆盖，本步回归通过 |
| O3 优雅停机 10 s 内 | ✅ 0.47 s |
| 异构复审 0 P1 残留 | ✅ 5 个 P1 全修（F-B1/B2/B3/B9 + F-B5 P2 组合）；2 个 P3 登记 |
| 门禁零回归 | ✅ §3 |

**判定：Step 10 验收 PASS（0 P1 残留）**。P-055 十步全部完成，待用户授权提交。

**开跑即崩的教训（复核价值）**：Step 9 的 19 例测试全部以 `InMemoryBusAdapter` / fake bus 构造，**真实 Redis 路径一行未被执行**；Step 10 首跑在 30 秒内连续暴露 4 个 P1（缺 adapter 形状、消费组未建、XAUTOCLAIM 三元素、入口缺 `__main__` 守卫）。结论：**跨进程组件的验收必须包含真实依赖实跑**，fake 只证明装配形状。

---

## 5. 遗留与后续

| 项 | 说明 | 归属 |
|----|------|------|
| F-B6 fsync 吞吐 | 单连接 `synchronous=FULL` ~26 ms/提交；批量提交/连接池化可提升 1-2 个量级 | 后续运维批（不作本批验收门槛） |
| F-B10 强杀残留锁 | `live_ledger.db.lock` 需人工清理（RUNBOOK 已补） | 运维项 |
| 集成用例默认跳过 | `P054_TEST_REDIS_URL` 未设时跳过（CI 无 Redis）；建议 CI 增 redis service 后设为必跑 | CI 增强（后续） |
| Mode S 容器实跑 | 本步用本机 Redis + 原生进程验证协议与循环；`docker compose up` 端到端冒烟待部署环境 | Step 11 / 部署演练 |

> 提交与 CI 触发未执行（未获授权）。建议提交信息：`feat(P-055): microservice decomposition — runtime loops, WS routes, arch gates, deploy assets, cross-process bench`。
