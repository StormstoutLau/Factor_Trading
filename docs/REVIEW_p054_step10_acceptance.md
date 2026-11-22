# REVIEW：P-054 Step 10 验收（F7 四项验收 + 延迟基准 + RULE-5 异构复审）

> **批次**: P-054 · **Step 10 验收** · 日期 2026-11-22 · **复审基座 GLM-5.3-Flash（≠ 落码基座 DeepSeek-V4.1-Flash → 异构成立）**
> **上游**: [CHECKLIST_p054](CHECKLIST_p054_service_layer.md)（88 项 Step 9 全 ✅，门禁 1420/22/157/309/151/51/19/12）；[IMPL_p054](IMPL_p054_service_layer.md)（D-1~D-20）；[DESIGN_p054](DESIGN_p054_service_layer.md)（D1-D20/I1-I17/§10 B0-B6）；[RESEARCH_p054](RESEARCH_p054_service_layer.md)（§19.11 F7 验收映射）；总纲 F7 [L223-232](../docs/UPGRADE_MASTER_PLAN.md#L223-L232)
> **复审方法**：F7 验收探针（一次性运行，运行后即弃）+ 源码级定向扫描（七面：事件/预算/快照/暂停链路/入口/装配/零改动守卫）+ 门禁零回归全量重放
> **范围声明（RULE-5 单向）**：复审者标记问题并执行 P2/P3 修复（用户已授权 Step 10 流程）；复审不改写 Step 9 交付文档的原始记录

---

## 1. F7 验收（总纲 L232 五项 + RESEARCH §19.11 映射）

| F7 验收项 | 探针/用例 | 结果 |
|-----------|-----------|------|
| **WS seq 连续性**（注入 100 条无跳变无重复） | 验收探针 `probe_seq_continuity(100)` | ✅ `count=100, monotonic=true, no_duplicate=true, first=1, last=100`（连接内去重 G5/G6 联合覆盖） |
| **snapshot+delta 重放一致**（断开重连 = 全量） | 探针 `probe_snapshot_replay` + T7 G7/G13 + T10 J2/J4 | ✅ `full_seq == snapshot_seq == watermark == 1`；`pending_after_snapshot=[]`；accepted coid 在快照；重连取 snapshot（D12，不做 delta-only） |
| **401/403 三角色**（无 key/错 key/低权限） | T6 F1（无 key 401）/F2（错 key 401）/F3（低权限 403）/F4（admin 200） | ✅ 4 例绿；`compare_digest` spy（F5）+ 429 限流（F7）绿 |
| **REST 路由审计**（无下单/撤单/kill；唯一写 broadcast-pause） | T6 F8 路由清单断言 | ✅ 无 POST /orders、无 cancel、无 kill；`/api/admin/broadcast-pause` 存在 |
| **延迟基准报告**（1k/10k p50/p95/p99 + 慢客户端丢弃计数） | 探针 `probe_benchmark`（§2） | ✅ 见 §2；**报告口径标注（R8）**：探针段计时为进程内零 I/O 演示口径，机内总线亚毫秒~几ms、浏览器端到端典型 5-50ms（总纲 L228 已向用户澄清；A股 L1 快照 3s/笔，「毫秒级」只优化内部新鲜度） |

## 2. 延迟基准报告（`scripts/p054_bench_ws.py` 三段口径 + 探针 1k/10k）

| 段 | 1k msgs | 10k msgs | 说明 |
|----|---------|----------|------|
| append→入队 p99 | 0.0001 ms | 0.0001 ms | 段计时演示口径（零 I/O） |
| 入队→发送 p99 | 0.001 ms | 0.0001 ms | 同上 |
| 端到端 p50 / p95 / p99 | 0.0001 / 0.0002 / 0.001 ms | 0.0001 / 0.0002 / 0.0002 ms | 机内总线（无 Redis 网络） |
| 慢消费者 | 行情 100 tick 全部经队列投递、0 条未投递（旧 tick 按 symbol 丢旧替换，可丢语义）；订单队满 `delivered=0` 且既有帧零丢失（不丢只延后，5s 超时 → 1013） | 同左 | I12：订单不丢 / 行情可丢 ✅ |

> **基准结论**：内部推送路径远低于「亚毫秒~几ms」机内总线预算；总纲 L228 的 5-50ms 浏览器端到端与 3s/笔行情源频率约束不受本批影响（已向用户澄清口径）。

## 3. 异构复审发现（源码级定向扫描）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-A1** | **P2** | **快照现金口径失真**：`api._snapshot` 与 `ws_hub.snapshot` 的 `cash = −Σ(amount+fee)` 缺 `initial_cash` 基准（`initial_cash` 是 Ledger 构造参数不入库）→ reader 侧把 10 万本金显示为负数/零基准；连带 `as_of` 硬编码 0.0 | **已修复**：`gateway.start()` 写 `meta.initial_cash`（writer 唯一写者）；两处 snapshot 改 `cash = initial − Σ` 且 `as_of = max(entry.ts)`；J4 内嵌断言（cash=100000，reserve 不入 entries） |
| **F-A2** | **P2** | **broadcast-pause 链路落码缺口（F-I9 残留）**：api 端点只改本进程 flag，未发布 `p054:admin`；`ConnectionHub` 无 paused 状态/订阅语义 → D19「跨 worker 暂停」静默失效（Step 6 复审 F-I9 的落码层回归） | **已修复**：`create_app(publisher=...)` 端点发布 `{"paused":bool}` 至 `admin_channel`；hub `set_paused` + `broadcast_market` paused 短路（只停行情，订单不受影响）；F4 内嵌 publisher 断言、G10 内嵌 paused 断言 |
| **F-A3** | **P2** | **独立入口不可运行**：`market_gateway.main` 与 `trading_worker` 若走 `ServiceSettings.from_env` 则强制 `api_key`（ValidationError）——行情/交易进程无 REST 鉴权需求 | **已修复**：`market_gateway.main` 直读 `P054_REDIS_URL/_MARKET_SYMBOLS/_MARKET_TICK_HZ/_MARKET_CHANNEL`；`trading_worker.main` 直读 `P054_SQLITE_PATH/_ORDER_CSV/_REDIS_URL`（env 直读，不依赖 api_key） |
| **F-A4** | **P2** | **trading_worker 装配缺口（IMPL §3.21）**：仅有 `Heartbeat`/`start_threads` 骨架，缺 `assemble()`（relay+consumer 装配）与 `main()`（gateway.start → 三线程 → poll 循环 → 信号退出） | **已修复**：`assemble(*, gateway, store, bus=None, metrics=...)` 可测装配函数（InMemoryBus 兜底）+ `main()` 薄壳（Terminal 适配器 + `_build_gate` 复用 P-052 SafetyGate 构造） |
| F-A5 | P3 观察 | `positions` DTO 只有 `quantity` 无 `avg_cost`（DESIGN §3.6 未定义字段） | **登记**：自用工具可接受；补 avg_cost 归后续（需加权成本重放） |
| F-A6 | P3 观察 | `apply_fill` 的 `inserted != len(entries)` 理论上存在「fill 新 + fee 旧」部分插入窗口 | **登记**：不可达——`fill:{fill_key}`/`fee:{fill_key}` 同 key 同源生成，要么都在要么都不在（T1 A3 同事务断言覆盖） |
| F-A7 | P3 观察 | `cancel_rejected` 用 `event_version+1` 不迁移状态（Step 9 偏差⑦）——与「真实迁移才 +1」的 D6 字面口径不同 | **登记并确认合理**：拒绝不改状态是 O-I4 口径（not_found/terminal 静默、rate_* 显式事件）；版本 +1 仅保同秒多次拒绝 event_id 唯一（I5）；CHECKLIST §9 偏差⑦维持登记 |

## 4. 修复后验证（零回归重放）

| 门禁 | 修复前（Step 9） | 修复后（Step 10） | 判定 |
|------|------------------|-------------------|------|
| pytest 全量 | 1420 | **1420 passed**（144.61s） | ✅ 零回归 |
| `-k golden` | 22 | **22 passed**（零重录） | ✅ |
| `-k p054` | 120 | **120 passed** | ✅（用例函数数不变：F4/G10/J4 内嵌断言） |
| mypy | 157·0 | **157 files 0** | ✅ |
| black | 309 | **309 unchanged** | ✅ |
| 文件计数 | 151/51/19/12 | **151 / 51 / 19 / 12** | ✅ |
| golden | 零改动 | `git status --porcelain tests/golden` 为空 | ✅ |
| `uv lock --check` | 通过 | 通过（未再改锁） | ✅ |

**core/* 零改动守卫**：修复全部落在 `live/{gateway}.py` 与 `services/{api,ws_hub,market_gateway,trading_worker}.py`，`core/*.py` 保持 51 文件零 diff。

## 5. 出口判定

- **F7 五项验收**：全部通过（§1）。
- **延迟基准报告**：已产出（§2，三段口径 + 慢消费者计数 + R8 口径澄清）。
- **异构复审**：0 P1 / 3 P2 全修（F-A1/A2/A3/A4）+ 3 P3 登记（F-A5/A6/A7）；修复后门禁零回归（§4）。
- **判定：Step 10 验收 PASS（0 P1 残留）**；P-054 十步全部完成，待用户授权提交。
- **Step 11 移交**：无新增未决；既有移交（P-055 微服务拆分前置 P-054）不变。

## 6. 遗留与后续

| 项 | 说明 | 归属 |
|----|------|------|
| F-A5 avg_cost | 快照 positions 无成本口径 | 后续批（P-055 或运维批） |
| `--bus fake` 开关 | D18 提及的开发/演示开关未落 CLI 参数（InMemoryBus 已可注入） | 登记为后续运维项 |
| Windows ACL preflight 用例 | R1 的 ACL 场景无法在单测构造（四 reason 用空库/缺文件/非 WAL/显式 internal_api 覆盖） | 登记为部署前人工检查项 |
| 真实 CTP 联调 | P-054 交付语义层 + mock/terminal；CTP 真机接入沿用 P-053 D1（SimNow 首连） | U-P053-1 / P-056 |

> 提交与 CI 触发未执行（未获授权）。建议提交信息：`feat(P-054): FastAPI+WS service layer, store v2, flow-control, 6-class events（Python 3.11 baseline）`。
