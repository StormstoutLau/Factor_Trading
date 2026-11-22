# CHECKLIST：P-054 服务层（store v2 / 通道流控前置包 / 事件外发 / FastAPI+WS 多 worker / Python 3.11 基线）

> **批次**: P-054 · **Step 7 CHECKLIST / Step 9 回填** · 日期 2026-11-22 · **判档 T1（全量）**
> **上游**: [DESIGN_p054](DESIGN_p054_service_layer.md)（D1-D20 / I1-I17 / §5 阈值 / §7 120 例 / §10 B0-B6）；[IMPL_p054](IMPL_p054_service_layer.md)（26 项变更 / C-1~C-21 / §4 120 例映射 / D-1~D-20 / §6 六批）；[REVIEW_p054_step6](REVIEW_p054_step6_impl.md)（首轮 1 P1/9 P2/5 P3 → §7 修复 → §8 复核回执通过、Step 6 关闭）；[RESEARCH_p054_risk_anchors](RESEARCH_p054_risk_anchors.md)（R1/R2 锚点 S62-S72）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**Step 7 禁预填，Step 9 回填实测**
> **状态**: **Step 9 完成（2026-11-22）——88/88 ✅**；门禁 pytest **1420** / golden **22** / mypy **157·0** / black **309** / `uv lock --check` 通过
> **基线读数（@`7f01b84`，P-053 关闭态）**: pytest **1300** / `-k golden` **22** / mypy **141 files 0** / black `--check .` **283** / `tests/*.py` **141** / `core/*.py` **51** / `live/*.py` **16（含 adapters 递归）** / `services/*.py` **0**
> **目标读数**: pytest **1420**（+120）/ `-k golden` **22**（零重录）/ mypy **157 files 0**（+16：live +3、services +12、scripts +1）/ black **309**（+26）/ `tests/*.py` **151**（+10）/ `core/*.py` **51 不变** / `live/*.py` **19**（+3，递归口径）/ `services/*.py` **12**

---

## 1. M 组：模块与代码（18 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| M1 | **B0 基线**：`pyproject.toml` → `requires-python>=3.11`、classifiers 3.11/3.12、black target py311/py312、mypy python_version 3.11、`pydantic>=2.9.0`、`[services]` extra；`.github/workflows/tests.yml` → CI 矩阵 3.11/3.12、安装 `".[dev,services]"`、mypy 路径含 `services`；`uv.lock` 重生成 | 无 | 读码 + C3 + C5 + C8 | ✅ 读码逐项命中；`uv lock --check` 通过（137 packages）；CI 安装行 `pip install ".[dev,services]"` |
| M2 | `live/events.py`（新建）：`OutboxEventType` **6 类**（无 reconcile，D-16）；`OutboxEvent`；`order_event`/`fill_event`；canonical JSON；`event_id` 模板（accepted 固定 `v1`） | 无 | 读码 + T3 | ✅ `live/events.py` 落盘；T3 10/10 绿（含 C8 六类断言） |
| M3 | `live/flow_control.py`（新建）：`Decision`；`FtdBudget`（6/s、reserve=1、发送即计）；`OrderFlowBudget`（2×internal、reserve_cancel=1、两类型桶）；`CancelResult`；`CancelAllReport` 落 gateway（D-1） | 无 | 读码 + T4 | ✅ 落盘；T4 16/16 绿 |
| M4 | `live/query_scheduler.py`（新建）：`BackoffPolicy`（1.0/×2/5.0/5 次/Full Jitter）；`QueryScheduler`（最小间隔、单在途、启动串行、巡检共用） | 无 | 读码 + T5 | ✅ 落盘；T5 12/12 绿（含单在途并发与巡检共用） |
| M5 | `live/channel.py`：`ChannelCapability` 追加 `max_ftd_per_sec=6.0`、`ftd_reserve=1`、`startup_ftd_instructions=2`；既有字段默认值不变 | 无 | 读码 + T4 + C1 | ✅ 三字段带默认值；P-053 T1 既有断言零改仍绿（C1 1420） |
| M6 | `live/adapters/ctp.py`：能力声明补 FTD 三字段；submit/cancel 注释改为「受 FTD 共享约束」；`-2/-3` 语义不动 | M5 | 读码 + T4 | ✅ 显式注释 + 默认继承；T4 绿 |
| M7 | `live/orders.py`：`OrderRecord.event_version: int = 0`；`transition()` 真实迁移 +1、同态不递增；旧 payload 兼容 | 无 | 读码 + T3 | ✅ T3 C6/C10 绿（status:0:v1、status:2:v2、旧 payload=0） |
| M8 | `live/ledger.py`：`apply_fill(..., outbox_events=())`；`_seen` canonical `fill:{fill_key}`（D-20）；store-first；删除 `_append`；失败内存不变（I17）；`resume`/`replay` 契约不变 | M9 | 读码 + T1 | ✅ T1 A3/A5/A7 绿（两分录同事务、故障注入回滚、resume 重放去重） |
| M9 | `live/ledger_store.py`：schema v2（seq AUTOINCREMENT + event_id UNIQUE + (sent,seq) 索引 + inbox + meta）；迁移三分支；组合写；冲突比对；只读 preflight 四 reason；`snapshot()` 单读事务 | M1 | 读码 + T1 + T2 | ✅ T1 16/16 + T2 12/12 绿（含全新库/v1/v2、只读四 reason、水位） |
| M10 | `live/gateway.py`：预算在 `pre_trade_check` 之后（F-I4/D-18）；`cancel_ex`/`cancel_all`/`cancel_all_ex`；5 处组合写；事件按阶段映射；同态跳过；恢复序走 scheduler；回放 fill 带事件 | M2-M4/M7-M9 | 读码 + T3 + T4 + T10 | ✅ T3/T4/T10 绿；发送即计（拒单不退还）T4 D13 绿 |
| M11 | `services/__init__.py` + `contracts.py` + `config.py`：Protocol/DTO/错误码；`ServiceSettings`（pydantic，extra=forbid，key≥16，TLS 一致性） | M9 | 读码 + T6 + T9 | ✅ T6 F11、T9 HM 绿；contracts 零 redis/fastapi import |
| M12 | `services/bus.py`：`SyncRedisBus`（交易线程）/`AsyncRedisBus`（API/WS）/`InMemoryBus`（FakeBus）；Stream `p054:orders` + Pub/Sub `p054:orders:events`/`p054:market`/`p054:admin` | M11 | 读码 + T8 + T10 | ✅ T8 12/12 + T10 J1 绿；双总线类落盘 |
| M13 | `services/auth.py` + `metrics.py`：compare_digest 三角色；ticket `SET NX EX`+`GETDEL` 双实现；认证限流 10/min/IP；四黄金信号 + 领域指标 + multiproc | M11 | 读码 + T6 + T9 | ✅ T6 F5/F6/F7、T9 HM5/HM6/HM7 绿 |
| M14 | `services/api.py` + `api_worker.py`：11 端点；无下单/撤单/kill 路由；CORS 白名单；`ssl_context_factory`（TLS1.2 下限、AEAD、pickle） | M11-M13 | 读码 + T6 + T9 | ✅ T6 F8/F9/F10/F12 绿（路由清单/ CORS / factory 三断言 / ready） |
| M15 | `services/ws_hub.py` + `market_gateway.py`：有界队列、snapshot+delta、seq 去重、注册-快照-过滤竞态、1013、行情丢旧/合并、心跳；独立/`--embedded` 入口 | M12 | 读码 + T7 + T10 | ✅ T7 16/16 绿（含 G7 竞态、G8/G16 1013、G10/G11 丢旧/合并） |
| M16 | `services/outbox_relay.py` + `trading_worker.py`：relay（批量→XADD→mark_sent、退避、purge）；consumer（inbox→Pub/Sub→XACK/XAUTOCLAIM）；心跳 Redis TTL；三守护线程用 SyncRedisBus | M12 + M9/M10 | 读码 + T8 + T9 | ✅ T8 12/12 绿；`Heartbeat.beat_once` 走 `set_key(...EX)` 不落 SQLite |
| M17 | `scripts/p054_bench_ws.py`：三段延迟采样（append→入队、入队→发送、端到端） | M14-M16 | 运行 + Step 10 报告 | ✅ `sample_segments(20)` 返回三段 p50/p95/p99（T10 J6 绿） |
| M18 | **零改动与分层守卫**：`core/*.py` 51 不变；`live/*` 不 import `services/*`；`contracts` 不 import redis/fastapi；既有测试零改写（仅 v1 outbox 原始 INSERT 随 §8-5 同步）；golden 零改动 | 全组 | grep + C1 + C6 + C7 | ✅ core 51；grep `from services` in live/ = 0；`git status tests/golden` 空；C1 1420 |

---

## 2. T 组：测试（10 文件 / 120 条）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| T1 | `test_p054_ledger_store_atomic.py` **16 条（A1-A16）**：组合写单事务；崩溃探针；fill+fee 同事务；批量幂等；store-first 回滚；resume 重放去重；只读四 reason；snapshot 水位 | M8/M9 | pytest | ✅ 16 passed |
| T2 | `test_p054_outbox_migration.py` **12 条（B1-B12）**：三分支迁移；rowid 顺序；seq 不复用；索引命中；冲突；同 payload 幂等；inbox；meta；purge | M9 | pytest | ✅ 12 passed |
| T3 | `test_p054_event_emission.py` **10 条（C1-C10）**：6 类触发点；accepted v1；event_version；canonical；cancel_rejected；对账仅 audit；旧 payload | M2/M7/M10 | pytest | ✅ 10 passed |
| T4 | `test_p054_flow_control.py` **16 条（D1-D16）**：FTD 6/s；发送即计；order-flow 1+1；reserve_cancel；退还边界；gate 拒绝不耗槽；reason 指标 | M3/M5/M6/M10 | pytest | ✅ 16 passed |
| T5 | `test_p054_query_scheduler.py` **12 条（E1-E12）**：最小间隔；单在途；Full Jitter；封顶/次数；启动 3 查询；-2/-3 退避；fail-closed；positions 降级；巡检共用；fake clock | M4 | pytest | ✅ 12 passed |
| T6 | `test_p054_api_auth.py` **12 条（F1-F12）**：401/403；compare_digest；ticket 单次/过期；429；路由清单；CORS；TLS factory 三项；明文仅 loopback | M11/M13/M14 | pytest | ✅ 12 passed |
| T7 | `test_p054_ws_protocol.py` **16 条（G1-G16）**：snapshot/delta；seq 单调/去重；水位；注册-快照-过滤；1013；行情丢旧/合并；心跳；resume；未就绪；错误码 | M15 + M10 | pytest | ✅ 16 passed |
| T8 | `test_p054_relay_consumer.py` **12 条（H1-H12）**：relay 顺序；mark_sent；重投；inbox；XACK；XAUTOCLAIM；扇出；退避；指标；空批；purge；PEL | M12/M16 | pytest | ✅ 12 passed |
| T9 | `test_p054_health_metrics.py` **8 条（HM1-HM8）**：live/ready；stale 心跳 503；degraded；四信号；领域指标；/metrics 鉴权；JSON 日志 | M13/M16 | pytest | ✅ 8 passed |
| T10 | `test_p054_end_to_end.py` **6 条（J1-J6）** + 合计：FakeBus 全链；快照重放；双 worker；重连；未就绪；延迟采样；合计 120；无 skip/xfail；全量 1420 | T1-T9 | pytest 计数 | ✅ 6 passed；`-k p054` = **120 passed**；全量 **1420 passed**；新文件无 skip/xfail 标记（仅两个测试名含 “skips”） |

---

## 3. C 组：门禁（8 项）

| ID | 门禁 | 命令 | 目标 | 实测 |
|----|------|------|------|------|
| C1 | pytest 全量 | `$env:MPLBACKEND='Agg'; .\.venv\Scripts\python.exe -m pytest -q` | **1420 passed** | ✅ `1420 passed, 279 warnings in 128.93s` |
| C2 | golden | `-m pytest -q -k golden` | **22 passed**（零重录） | ✅ `22 passed, 1398 deselected`（零重录） |
| C3 | mypy | `-m mypy --explicit-package-bases --check-untyped-defs core … live services` | **157 files 0** | ✅ `Success: no issues found in 157 source files` |
| C4 | black | `-m black .` 后 `-m black --check .` | **309 files unchanged** | ✅ 首轮 `15 files reformatted, 294 unchanged`；check `309 files would be left unchanged` |
| C5 | 锁文件 | `uv lock --check` | 通过 | ✅ 退出码 0（`Resolved 137 packages`） |
| C6 | 文件计数 | `tests/*.py`、`core/*.py`、`live/**/*.py`、`services/*.py` | **151 / 51 / 19 / 12** | ✅ 151 / 51 / **19（递归；顶层 14）** / 12 |
| C7 | 无 golden 改动 | `git status --porcelain tests/golden` | 输出为空 | ✅ 输出为空 |
| C8 | 测试卫生 + CI 安装面 | 新 10 文件 grep skip/xfail；`.[dev,services]` | 无 skip/xfail；安装含 services | ✅ 无 `@pytest.mark.skip/xfail`；CI 行 `pip install ".[dev,services]"` |

---

## 4. I 组：不变式（17 项，对应 DESIGN I1-I17）

| ID | 不变式 | 证据出口 | 实测 |
|----|--------|----------|------|
| I1 | 只有交易进程构造 writer store；第二实例 `.lock` 失败 | T1 + 两进程启动测试（沿用 P-053 I8） | ✅ P-053 T4 ⑤ 第二实例 `OSError` 仍绿；writer/reader 分型 |
| I2 | API worker 不写 SQLite、不 append EventLog；store `read_only=True` | T1 preflight + 读码 | ✅ T1 A8-A12 只读四 reason + 写事务拒绝；api worker 仅 `read_only=True` |
| I3 | 业务写 + 事件走组合写 API | grep + T1/T3 | ✅ gateway 5 处 `*_with_events`；T1 A1/A2 绿 |
| I4 | `outbox.seq` 单调不复用；relay 严格 `ORDER BY seq` | T2 + T8 | ✅ T2 B4 新 seq=3；T8 H1 顺序 1→2→3 |
| I5 | 同 `event_id` ⇒ 同 type+payload；否则冲突 | T2 + T3 | ✅ T2 B6 抛 `OutboxEventConflict`；T1 A15 回滚业务写 |
| I6 | at-least-once + inbox/客户端去重；不宣称 exactly-once | T8 + 文档措辞 | ✅ T8 H3/H4/H5 绿；STREAM 字段含 event_id |
| I7 | FTD/order-flow 发送前 reserve；拒绝显式 | T4 | ✅ T4 D11-D16 绿 |
| I8 | 默认路径峰值 3/2；同秒 1 报 + 1 撤；既有 1300 全绿 | T4 + C1 | ✅ T4 D6-D10 绿；C1 1420 |
| I9 | 撤单拒绝写 `AUDIT_CANCEL` + reason；`cancel_ex` 可区分 | T4 + audit | ✅ T3 C4 + T4 审计断言绿 |
| I10 | 查询串行、间隔 ≥1/s；-2/-3 ≤5 次不重复入账 | T5 | ✅ T5 E1/E2/E5/E7 绿 |
| I11 | WS 连接内 seq 严格单调；缺口重连 snapshot | T7 | ✅ T7 G4/G5/G6 绿 |
| I12 | 订单事件不静默丢；行情可丢计数 | T7 + 指标 | ✅ T7 G9 队满不丢既有帧；G10 行情丢旧 |
| I13 | 密钥/ticket 不入日志；compare_digest | grep + T6 | ✅ T6 F5 spy + F1/F2 401；日志无密钥字段 |
| I14 | TLS 仅 1.3/1.2；明文仅 loopback | T6 | ✅ T6 F10/F11 绿 |
| I15 | REST 无下单/撤单/kill；唯一写 broadcast-pause | T6 | ✅ T6 F8 路由清单断言 |
| I16 | `live/*` 不 import `services/*`；contracts 零 redis/fastapi | grep | ✅ 两处 grep 零命中 |
| I17 | Ledger store-first：失败/重复时内存不变 | T1 | ✅ T1 A5 故障注入 + A7 重复 fill 绿 |

---

## 5. D 组：设计决策 D1-D20（20 项）

| ID | 决策 | 落实点 | 实测 |
|----|------|--------|------|
| D1 | 单实例交易/账本进程 + N 无状态 worker | M16 + M14 + I1 | ✅ `trading_worker`/`api_worker` 分入口；I1 绿 |
| D2 | 行情 Pub/Sub；订单 outbox→Streams→consumer→Pub/Sub | M12 + M16 + T8 + T10 | ✅ T8 + J1 全链绿 |
| D3 | `seq = outbox.seq`；快照同读事务 `MAX(seq)` | M9 + T1 + T7 | ✅ T1 A13/A14 + T7 G2 绿 |
| D4 | 显式组合写 API；不引 UoW/ORM | M9 + T1 | ✅ T1 16/16 |
| D5 | 6 类事件；reconcile 仅审计（F-I6） | M2 + T3 | ✅ T3 C1-C9 绿 |
| D6 | event_id 版本化 + 冲突 + inbox；event_version 单调 | M7 + M9 + T2 + T3 | ✅ T2 B6 + T3 C6 绿 |
| D7 | relay 批量 → XADD → mark_sent；7 天保留 | M16 + T8 | ✅ T8 H1/H2/H11 绿 |
| D8 | 查询 1/s、单在途、Full Jitter、巡检共用 | M4 + T5 | ✅ T5 12/12（E11 巡检共用） |
| D9 | FTD 6/s + reserve=1 + 发送即计 | M3 + M5 + M6 + T4 | ✅ T4 D1-D5/D13 绿 |
| D10 | order-flow 2×internal + reserve_cancel | M3 + T4 | ✅ T4 D6-D10 绿 |
| D11 | `cancel_ex` + `cancel` 委托 + `cancel_all` int + `cancel_all_ex` | M10 + T4 + T6 | ✅ T3 C3/C4 + T4 绿；`cancel_all` 保留 bridge 分支 |
| D12 | WS snapshot+delta；seq 单调；不做 delta-only | M15 + T7 | ✅ T7 G1-G7/G13 绿 |
| D13 | 队列满 5s → 1013；行情丢旧/合并 | M15 + T7 | ✅ T7 G8/G9/G10/G11/G16 绿 |
| D14 | API Key compare_digest；ticket NX EX/GETDEL；429 | M11 + M13 + T6 | ✅ T6 F1-F7 绿 |
| D15 | TLS 全启 + loopback 例外 + factory 断言 | M14 + T6 + I14 | ✅ T6 F10/F11 绿 |
| D16 | prometheus 四信号 + 领域指标；/metrics 鉴权 | M13 + T9 | ✅ T9 HM5/HM6/HM7 绿 |
| D17 | 读路径同机 mode=ro；跨机内部 API 只文档化；不建 Redis 读模型 | M9 + T1 | ✅ T1 A8-A12 绿；无 Redis 读模型 |
| D18 | 本地 Docker/CI service/单测 InMemory | M12 + C8 + T8 + T10 | ✅ T8/T10 全用 InMemory；CI service 行在 workflow |
| D19 | REST 只读 + 唯一写 broadcast-pause | M14 + T6 + I15 | ✅ T6 F8 绿 |
| D20 | check_same_thread=False + 双锁 + SyncRedisBus + 三线程 + 心跳 TTL | M8 + M9 + M16 + T8 + T9 | ✅ store 双锁落盘；Heartbeat `set_key(...EX)`；T8 同步线程路径绿 |

---

## 6. F 组：Step 6 复审 15 项回执核对（F-I1~F-I9 + O-I1~O-I5）

> F-I3 含两个独立子问题（fill 事件错挂 / cancel 误标），按 2 项核对 → 1 P1 + 9 P2 + 5 P3 = 15 项。

| ID | 复审发现（P 级） | 核对动作 | 实测 |
|----|------------------|----------|------|
| F1 | **F-I1（P1）** `_seen` 口径不一致 → 重启重复入账 | `grep "_seen.add" live/ledger.py` = canonical；T1 A7 | ✅ `fill:{fill_key}`；A7 重放返回 False 且现金/持仓不变 |
| F2 | **F-I2（P2）** accepted 版本漂移 | T3 C1 断言 `:accepted:v1`；builder `version=1` | ✅ 绿 |
| F3 | **F-I3①（P2）** fill 错挂 `order.status` | T3 C5：fill 仅 `fill.applied` | ✅ 绿（无 order.status） |
| F4 | **F-I3②（P2）** 撤单成功误标 `order.canceled` | T3 C3：`order.status` 且 `:status:6:`，无 canceled | ✅ 绿 |
| F5 | **F-I4（P2）** gate 拒绝泄漏预算 | T4 D11：`pre_trade_check` 后 reserve | ✅ 拒绝后槽位未耗、adapter 零调用 |
| F6 | **F-I5（P2）** 全新库迁移崩溃 | T2 B1/B2/B3 | ✅ 三分支全绿 |
| F7 | **F-I6（P2）** reconcile 跨重启冲突 | T3 C9 + grep `reconcile.completed` | ✅ live/services 零命中；对账仅 audit |
| F8 | **F-I7（P2）** 同步线程 × async bus | `SyncRedisBus` 落盘；T8 | ✅ 类存在且 relay/consumer 线程路径绿 |
| F9 | **F-I8（P2）** CI 缺 `[services]` | C8 grep | ✅ `.[dev,services]` 命中 |
| F10 | **F-I9（P2）** `p054:admin` 链路断裂 | grep 三处 + settings admin_channel | ✅ bus/api/settings 链路齐备 |
| F11 | O-I1（P3）store-first 更新枚举漏 `_seen`/`_reserves` | T1 A5 | ✅ 故障后内存全不变，重试可成功 |
| F12 | O-I2（P3）同态跳过 | T3/T4：同态回报不产事件 | ✅ 绿 |
| F13 | O-I3（P3）恢复序 fill 带事件 | M10 `_run_query` + T3 | ✅ 回放 fill 经 `fill_event` 入库 |
| F14 | O-I4（P3）`cancel_ex` 顺序与事件范围 | 读码 + T3 C4 | ✅ not_found/terminal→rate→FTD→flow→adapter；仅 rate_*/unsupported 发事件 |
| F15 | O-I5（P3）门禁算术 | C1-C6 | ✅ 1420/22/157/309/151/51/19/12 全闭合 |

---

## 7. 出口判定

- **Step 7 判据**：M18 + T10 + C8 + I17 + D20 + F15 = **88 项断言落成**（已满足）。
- **Step 8 判据**：四文档一致性通过（2026-11-22，6 P3 全修）。
- **Step 9 判据**：88 项实测列全部 ✅；门禁命中 1420/22/157/309/151/51/19/12 + `uv lock --check` → **Step 9 通过**。
- **Step 10 判据**：F7 四项验收 + 延迟基准报告 + 异构复审 0 P1。

## 8. 实测读数（Step 9 回填）

| 指标 | 基线 @`7f01b84` | 目标 | 实测 |
|------|------------------|------|------|
| pytest 全量 | 1300 | 1420 | ✅ **1420 passed**（128.93s） |
| `-k golden` | 22 | 22（零重录） | ✅ **22 passed** |
| mypy | 141 files / 0 | 157 files / 0 | ✅ **157 files / 0** |
| black `--check .` | 283 | 309 unchanged | ✅ **309 unchanged** |
| `tests/*.py` | 141 | 151 | ✅ **151** |
| `core/*.py` | 51 | 51 | ✅ **51** |
| `live/*.py` | 16（递归） | 19 | ✅ **19（递归；顶层 14）** |
| `services/*.py` | 0 | 12 | ✅ **12** |
| `uv lock --check` | 通过 | 通过 | ✅ 退出码 0 |

## 9. 备注（含 Step 9 实施偏差）

- **落地顺序**：B0 基线 → B1 store（A+B 28）→ B2 流控（D+E 28）→ B3 事件/store-first（C 10）→ B4 服务骨架（F+HM 20）→ B5 运行时（G+H 28）→ B6 端到端（J 6）；每批红→绿后跑回归。
- **组号别名**：IMPL §4 的 health 组号 I1-I8 在本清单记 **HM1-HM8**，避免与不变式 I1-I17 混淆（8 例不变）。
- **F-I3 拆分**：REVIEW §4 标题「1 P1 / 9 P2 / 5 P3」对应 F-I3 两个子问题（F3/F4 两行）。
- **落点澄清**：`CancelAllReport` → `live/gateway.py`（D-1）；`Decision`/`CancelResult` → `live/flow_control.py`；`OutboxRecord`/`OutboxEventConflict`/`StoreReadOnlyError`/`StoreSnapshot` → `live/ledger_store.py`；`TicketStore` → `services/contracts.py`。
- **Step 9 实施偏差（均不改变对外语义）**：
  1. **P-053 T4 原始 INSERT 同步**：`tests/test_p053_ledger_store.py` 的回滚探针由 5 列 `INSERT INTO outbox VALUES` 改为显式 6 列（schema v2 必需；DESIGN §8-5 已授权「批内同步改测试」）。
  2. **P-024 漂移守卫**：`scripts/spec_runner_adapter.py` 的 `GATES["mypy-check"]` 目标列表追加 `services`（CI/本地口径必须一致；C3 以该命令为准）。
  3. **`httpx`**：`TestClient` 依赖加入 `[dev]` extra 并重生成锁（否则 CI F/HM 20 例会 ImportError）。
  4. **文件计数口径**：`live/*.py` 采用**递归**计数（基线 16 = 11 顶层 + 5 adapters；实测 19 = 14 顶层 + 5 adapters）；非递归为 14。
  5. **mypy 局部忽略**：`services/config.py::from_env` 动态 kwargs 与 `services/bus.py::xreadgroup` 联合返回类型各 1 处 `# type: ignore[...]`（pydantic/redis 存根限制）。
  6. **测试去重 coid**：事件测试用显式 `co_first`/`co_second`，避免确定性 coid 在同参提交时触发 `accepted:v1` 冲突（符合 I5 设计）。
  7. **撤单拒绝版本**：`cancel_rejected` 通过 `event_version+1`（不迁移状态）保证同秒多次拒绝 event_id 唯一；Step 10 复核确认合理（F-A7 登记，O-I4 口径自洽）。
  8. **Step 10 修复回写（F-A1~A4，见 [REVIEW_p054_step10](REVIEW_p054_step10_acceptance.md)）**：① snapshot cash 基准（gateway.start 写 `meta.initial_cash`，api/ws_hub 读基准 + as_of=max ts）；② broadcast-pause 发布 `p054:admin` + hub `set_paused` 短路；③ market_gateway/trading_worker 入口 env 直读（不走 ServiceSettings）；④ trading_worker 补 `assemble()`/`main()`。修复后门禁零回归（1420/22/120/157·0/309/151/51/19/12 全重放）。
- **Risk 相关**：R1 preflight 的 Windows ACL 用例未新增平台 skip（四 reason 用「空库/缺失文件/非 WAL/显式 internal_api」构造，无 ACL 依赖）；R2 TLS factory 含 `pickle.dumps` 断言；`--bus fake` 未用于掩盖 Redis 路径（T8 使用 `InMemoryBus` + `SyncRedisBus` 类型存在性）。
- **本步零提交**：未执行 git commit/push，待 Step 10 验收与用户授权。
