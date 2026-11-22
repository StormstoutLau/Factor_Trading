# REVIEW：P-054 Step 4 设计异构复审（DESIGN_p054_service_layer）

> **批次**: P-054 · **Step 4 设计复审** · 日期 2026-11-22
> **复审对象**: [DESIGN_p054_service_layer.md](DESIGN_p054_service_layer.md)（D1-D20 / I1-I17 / §3 数据契约 / §7 120 例 / §8 十项偏差 / §10.2 B0-B6）+ 关联 [RESEARCH_p054_risk_anchors](RESEARCH_p054_risk_anchors.md)
> **复审基座**: **GLM-5.3-Flash** ≠ 作者 **DeepSeek-V4.1-Flash**（异构成立，RULE-5）
> **方法**: E3 代码锚点逐条重放 + 外部锚点独立抽检（本会话直取）+ 口径保真核对 + 内部一致性/算术扫描 + 可实施性推演（以「Step 5 拿到即可落码」为准绳）+ 反向证据检查
> **仓库时点**: 工作区含 RESEARCH/DESIGN/risk_anchors/PROGRESS（未提交）；代码基线 = P-053 关闭态 `7f01b84` 系
> **结论**: **0 P1 / 4 P2 / 6 P3 —— 有条件通过；F-D1~F-D4 修复前不得进入 Step 5**（门禁 b）
> **修复与关闭（§8）**: F-D1~F-D4 复核属实并已修复；F-D5~F-D10 已顺手修正/登记 → Step 4 关闭
> **二轮复审（§9）**: 修复落点 10/10 重放属实；新引入 P3 ×5 顺手修正、观察 ×2 登记（0 P1/P2）→ **Step 4 维持关闭（2026-11-22）**

---

## 1. 复审范围

| 维度 | 核对内容 | 结果 |
|------|----------|------|
| 事实性 | 外部锚点（S62-S72）可回放、无幻觉 | §3 |
| 代码实证 | §0.3 契约、§2.2 改造点、§3.3 Protocol 变更、D9-D11、I 系可测性的 file:line 重放 | §2 |
| 边界 | Q8-Q20 用户裁决不改写；P-053 已关闭契约（cancel/cancel_all/Protocol/EventType）；D16 边界转移 | §4 |
| 一致性 | D/I/Q 编号链、测试计数（120 例/10 文件）、门禁算术（1420/156/309/151/19/12）、DESIGN↔RESEARCH↔PROGRESS 同步 | §5 |
| 可实施性 | 进程并发模型、SQLite 访问模型、组合写调用链、迁移可逆性、WS 水位竞态 | §2/§5 |

---

## 2. 代码锚点重放（E3）

| # | DESIGN 声称 | 重放结果 |
|---|-------------|----------|
| 1 | `LedgerStore` Protocol 现有 8 方法 + `transaction()`（§0.3「8 方法签名保留」） | ✅ [ledger_store.py#L31-L40](../live/ledger_store.py#L31-L40)：append_entry/entries/upsert_order/load_orders/append_outbox/pending_outbox/mark_sent/close 8 + transaction（与 RESEARCH §2-1 口径一致） |
| 2 | `append_outbox(event_id, event_type, payload, ts)` 旧签名、`pending_outbox()` 返回 4 元组、`mark_sent(event_id)` | ✅ [L121-L136](../live/ledger_store.py#L121-L136) 逐字命中 → §3.3「替换签名」成立 |
| 3 | `pending_outbox` 现为 `ORDER BY created_ts`（无稳定序，Q11 动机） | ✅ [L128-L132](../live/ledger_store.py#L128-L132) 命中 |
| 4 | `TradingGateway.cancel() -> bool` / `cancel_all() -> int`（§0.3/D11 涉及） | ✅ [gateway.py#L381](../live/gateway.py#L381) `-> bool`；[L402-L410](../live/gateway.py#L402-L410) `-> int`（逐单累加；bridge 分支 [L403-L405](../live/gateway.py#L403-L405) 委托 `gate.cancel_all(bridge) -> int`）→ **D11 变更返回类型但未登记，见 F-D3** |
| 5 | `Ledger._append` 逐条 `store.append_entry`（组合写改造点） | ✅ [ledger.py#L260-L263](../live/ledger.py#L260-L263)：先 store 后 `self._entries.append`，**store 返回值被忽略** → 内存/持久化分叉已在 P-053 潜伏，组合写必须一并处理 → **F-D4** |
| 6 | `apply_fill` 的 fill/fee 两分录跨两事务（U-P053-17） | ✅ RESEARCH §4.1-3 已证；本轮复核 `_append` 路径一致 |
| 7 | CTP 能力声明 `max_submit_per_sec=10.0` / `max_cancel_per_sec=10.0` / `max_query_per_sec=1.0`（§2.2 ctp.py 改造点） | ✅ [ctp.py#L58-L61](../live/adapters/ctp.py#L58-L61) 逐字命中（另有 `max_submit_per_day=20000`，DESIGN 未提及日上限与 FTD 的关系 → 并入 F-D6 观察不单列） |
| 8 | `start()` 恢复序 3 查询 + `_throttle_query` 直接 raise（U-P053-18） | ✅ [gateway.py#L146-L153](../live/gateway.py#L146-L153) + [L355-L361](../live/gateway.py#L355-L361)；QueryScheduler 替换路径成立 |
| 9 | writer 连接 `check_same_thread=True` / `isolation_level=None` / WAL / `synchronous=FULL` | ✅ [ledger_store.py#L52-L56](../live/ledger_store.py#L52-L56) → **API worker 与交易进程的线程模型均未在 DESIGN 中处理，见 F-D1/F-D2** |
| 10 | `EventLog` buffer 500 / `RLock` 仅进程内（R9、G17 承接） | ✅ [event_log.py#L115](../core/event_log.py#L115)/[L123](../core/event_log.py#L123) |
| 11 | pyproject：`requires-python>=3.10`（L10）、`pydantic>=2.0.0`（L35）、`redis>=4.5.0`（L45）；fastapi/uvicorn 未声明 | ✅ 与 RESEARCH §19.1 一致；B0 变更面成立 |
| 12 | `OrderRecord` 现无 `event_version` 字段；`transition()` 位于 [orders.py#L160-L168](../live/orders.py#L160-L168) | ✅ §3.2 追加字段 + 递增点可行；frozen dataclass 返回新记录，旧 payload `dataclass(**data)` 兼容默认值 0（§8-6）成立 |
| 13 | CI mypy 命令含 `scripts`（门禁算术核对） | ✅ [tests.yml](../.github/workflows/tests.yml) mypy 步骤含 `scripts` → 新增 `scripts/p054_bench_ws.py` 计入 mypy 文件数 → **F-D5** |

**13/13 属实**（其中 #4/#5/#9/#13 同时构成发现证据）。

---

## 3. 外部锚点抽检（S62-S72，本会话独立直取）

| # | 锚点 | 方式 | 结果 |
|---|------|------|------|
| 1 | S62 WAL 只读三条件 + 「所有读者必须同机 / 不支持网络文件系统」（§2.2） | 检索命中官方正文 + 全文直取（18.7KB 存档） | ✅ 三条件逐字命中；同机约束命中 |
| 2 | S63 `immutable=1` 语义与「错误结果/损坏」警告 | 官方 URI 页 | ✅ 逐字命中（含 Caution） |
| 3 | S65 `sqlite3.connect("file:...?mode=ro", uri=True)` 与 `attempt to write a readonly database` | Python 3.11 文档 | ✅ 命中 |
| 4 | S68 uvicorn **0.54.0** `config.py`：`create_ssl_context`（L104-L124 不设 `minimum_version`）、`ssl_context_factory` 参数（L218）、`ssl_ciphers`（L217） | tag 直取源码（15.6KB 存档） | ✅ 行号精确命中 |
| 5 | S69/S70 settings + deployment 文档：factory 官方入口、「bumping `minimum_version`」示例、每 worker 调用、**必须可 pickle** | raw main 直取 | ✅ 示例与 pickle 约束逐字命中 |
| 6 | S71/S72 `SSLContext.minimum_version`（3.7+）/ `PROTOCOL_TLS_SERVER` 默认 TLS1.2 / Python 3.10 What's New | 官方文档 | ✅ 命中 |
| 7 | S42-S61（RESEARCH 主体） | 复用二轮复审（REVIEW_p054_step2 §8.2）结论，不重复抽检 | ✅ 既往 pass |
| 8 | S66/S67（T3 旁证） | 定位核对：仅用于失败现象旁证，未进入结论链 | ✅ 降级合规 |

**无幻觉**；S62-S72 全部 T1 且本会话可重放。

---

## 4. 口径保真（不重开已裁决项）

- **Q8/Q9/Q10/Q11/Q12/Q13/Q14/Q15-Q20**：§0.1 表 13 项与 RESEARCH §15/§16.6/§19.3/§20.6/§22 逐条一致 ✅；复审未发现重开或改写。
- **Q5 数值**（1.0s/×2/封顶 5.0s/5 次/Full Jitter）：与 RESEARCH §12.4-B5 建议一致，属「留 Step 3 定数值」的授权范围 ✅。
- **Q6/Q7**：trades/orders fail-closed + positions 降级、巡检共用调度器（6s）——RESEARCH §5.4/§12.2-B6 授权范围内定案 ✅。
- **D16（outbox 只写不读）失效**：以「批次边界转移」显式登记（§0.3-5），未伪装成 P-053 契约 ✅。
- **I8 默认路径不变**（FTD 峰值 3、order-flow 峰值 2、1报+1撤允许）：与 §15.5-2/§17.4 (a-修订) 一致 ✅。
- **WS seq = outbox.seq**：依赖组合写原子性（业务行与事件同事务）→ 水位一致性成立 ✅；「订阅→快照→过滤 seq>S→live」的窗口分析：S 即快照 MAX(seq)，`seq>S` 过滤恰好无重无漏 ✅（推演通过）。
- **R1/R2 补充调研**：S62 禁 immutable、preflight、factory 方案与 DESIGN §8-10/§9 回写一致 ✅。

---

## 5. 发现（0 P1 / 4 P2 / 6 P3）

| ID | 级别 | 发现 | 证据 |
|----|------|------|------|
| **F-D1** | **P2** | **API worker 只读 SQLite 的访问模型未定**：现 writer 连接 `check_same_thread=True`（[ledger_store.py#L52-L54](../live/ledger_store.py#L52-L54)）；FastAPI sync 端点跑在线程池（默认 40 线程），单连接跨线程必炸 `ProgrammingError`；DESIGN §3.3 只写了 `read_only=True`，未定「连接生命周期」（每请求连接 / 连接池 / check_same_thread=False+串行 / aiosqlite）——Step 5 无法落码 | §3.3/§3.7 vs ledger_store.py#L52-L54 |
| **F-D2** | **P2** | **交易进程并发模型未定**：relay（0.2s 轮询）、Streams 消费者（XREADGROUP 阻塞）、heartbeat（1s `set_meta`）、QueryScheduler、gateway 同住单实例，但线程/asyncio 结构未设计；writer 连接 `check_same_thread=True` 禁跨线程，若多线程共享须 `check_same_thread=False` + 串行化（或单写线程队列）；且 `synchronous=FULL` 下每秒 heartbeat = 每秒一次 fsync，与订单写同连接串行——代价与放置（同连接 or 独立只读连接读回）需定案 | §2.1/§3.1 meta 表/D7/D8 vs ledger_store.py#L52-L56 |
| **F-D3** | **P2** | **D11 `cancel_all` 返回 `{requested, submitted, deferred, rejected}` 与 §0.3/I8 矛盾且未登记**：现状 `cancel_all() -> int`（[gateway.py#L402-L410](../live/gateway.py#L402-L410)，bridge 分支亦返回 int）；§0.3 只保护 `cancel() -> bool`，§8 十项偏差无 cancel_all 条目；返回类型变更必然改动 P-053 既有测试 → 与 I8「既有 1300 测试全绿」冲突。二选一：① 保留 int，deferred 经 audit/日志表达；② 显式登记 §8-11 + 修正 I8 为「既有测试更新后全绿」并复核门禁算术 | D11/§0.3/§8/I8 vs gateway.py#L402-L410 |
| **F-D4** | **P2** | **Ledger 侧组合写路径未设计**：组合写契约在 store（§3.3），但调用链未定——`apply_fill` 产生 fill+fee 两分录 + `fill.applied` 事件，谁组装 `append_entries_with_events`？`Ledger._append` 现状「store 先写、内存后 append、返回值忽略」（[ledger.py#L260-L263](../live/ledger.py#L260-L263)）；组合写下若 store 事务失败，内存 positions/entries 是否已脏？需定案：Ledger API 是否接收 events、写入失败时内存回滚策略、`apply_fill -> bool` 返回值语义是否保持 | §3.3/B3 vs ledger.py#L260-L263、ledger.py#L96-L145 |
| F-D5 | P3 | **门禁算术：mypy 156 少计 1**——CI mypy 命令含 `scripts`，`scripts/p054_bench_ws.py` +1 → 应为 **157**（141+3+12+1）；black 的 +26 已计入该脚本（3+12+10+1=26），仅 mypy 漏。连带：§0.2 表实为 **11 行**（Q1/Q2/Q5/Q6/Q7/WS 序号源/WS 重连/ticket/outbox 保留/REST 写端点/实施批次），PROGRESS §3.63 写「10 项工程定案」——建议按「10 项定案 + 1 项排期」口径对齐 | §7 门禁表/§0.2 vs tests.yml mypy 步骤、PROGRESS §3.63 |
| F-D6 | P3 | **market_gateway 进程归属未定案**：§2.1 画独立进程「可 1 个」，B5 将其列为模块但未说明由谁启动（独立入口 vs trading_worker 内嵌可选）；影响启动脚本、故障隔离面与 D18 的 `--bus fake` 开发模式 | §2.1/§2.2/§10.2-B5 |
| F-D7 | P3 | **ticket 存储抽象缺失**：`services/auth.py` 依赖 redis（§2.2），ticket 用 Redis `SET NX EX`+`GETDEL`；但 D18 要求单测 FakeBus（I16 只约束 contracts.py 不 import redis）→ `test_p054_api_auth` 的 ticket 用例（单次使用/过期）需要 **TicketStore Protocol + InMemory 实现**，DESIGN 未定义 | §3.5/§2.2/D18 vs §7 api_auth 行 |
| F-D8 | P3 | **`/api/orders?status=&limit=&offset=` 无对应只读查询方法**：Protocol v2 仅保留 `load_orders()`（全量），worker 只能内存过滤；自用规模可接受，但 Step 5 应明确（内存过滤 vs 增加 `orders_where(...)`），且 404 语义依赖全量比对 | §3.7 vs §3.3 |
| F-D9 | P3 | **preflight 错误分类不全**：[risk_anchors §2.5](RESEARCH_p054_risk_anchors.md) 只写「三条修复路径」（同用户/目录授权/内部 API）；fresh DB（交易进程未启动，无 `outbox` 表）时 `MAX(seq)` 报 `no such table`，属第四种根因，错误消息规格应区分「权限失败」vs「库未初始化」 | risk_anchors §2.5 vs §3.1 迁移时序 |
| F-D10 | P3 | **S 编号空间分裂**：S62-S72 定义于 risk_anchors §5，主 RESEARCH §8 表无条目，而 RESEARCH §22.3 直接引用「S62/S63」——后续批次若继续编号 S62 会撞号。建议：主表追加 11 行（标注「来自 risk_anchors」）或 risk_anchors 改用独立前缀（A1-A11） | RESEARCH §8 vs §22.3 vs risk_anchors §5 |

---

## 6. 反向证据检查

- **未发现推翻架构裁决的反例**：单写者拆分（Q18）、Pub/Sub 扇出（F-R2-1 修复口径）、FTD/order-flow 双层预算（Q8/Q9）、seq=AUTOINCREMENT（Q11）在重放中均与代码事实自洽。
- **WS 水位竞态推演通过**：订阅→快照→`seq>S` 过滤→live 的顺序在「快照 MAX(seq)=S」定义下无重无漏；`stale_snapshot` 关闭路径自洽。
- **F-D1/F-D2 属规格缺口而非设计错误**：现有代码事实（check_same_thread、单连接）与 Full 拓扑不矛盾，但缺并发/访问模型则 Step 5 必然各写各的——判 P2 而非 P1。
- **Q14=Full 的代价（G16/G17）已由 D1/D18 承接** ✅。

---

## 7. 出口判定与门禁

- (a) FALSIFIED 断言：**0**（S62-S72 重放全真；代码锚点 13/13 属实）。
- (b) CONFLICT：**1 处未仲裁 = F-D3**（D11 vs §0.3/I8 的 cancel_all 返回类型矛盾）；另有 **3 项规格缺口 = F-D1/F-D2/F-D4**（不冲突但阻断 Step 5 落码）。**F-D1~F-D4 修复前不得进入 Step 5**。
- (c) 阻断性断言双源：seq 单调性（SQLite AUTOINCREMENT S33 + 组合写 E3）、at-least-once（S1 + Streams S44）、TLS1.2（S70 factory + S72 默认）、WAL 只读三条件（S62）✅。
- (d) 假设显式携带：R1 部署前提、R6 保留期、R8 基准口径均已标注 ✅。
- **判定：有条件通过**——F-D1~F-D4（P2）修复 + F-D5~F-D10（P3，顺手）登记后，Step 4 关闭，进入 Step 5 IMPL。

> **复审者权限声明（RULE-5 单向）**：本复审仅标记问题，未改写 DESIGN/RESEARCH/risk_anchors 正文；F-D3 的两个修复方向（保留 int vs 登记变更）属作者定案事项，复审者不代行。

---

## 8. 作者修复核验（回执，2026-11-22）

> 执行方：作者基座 DeepSeek-V4.1-Flash（≠ 复审基座 GLM-5.3-Flash）。10 项发现（4 P2 + 6 P3）复核结论均为**属实**；本节为修复落点与自检方式，§5 原始发现保留不改写（RULE-5 单向）。

| ID | 复核 | 修复落点 | 核验方式 |
|----|------|----------|----------|
| **F-D1**（P2） | 属实：只读连接生命周期未定，`check_same_thread=True` + FastAPI 线程池不可行 | [DESIGN §2.4](DESIGN_p054_service_layer.md) 新增「API/WS worker」模型：每 worker 一个只读连接、`check_same_thread=False` + `_read_lock`、`def` 端点走线程池、WS 快照 `anyio.to_thread` | 与 §3.3 preflight 衔接；连接在 lifespan 打开/关闭，无跨 worker 共享 |
| **F-D2**（P2） | 属实：relay/consumer/heartbeat 线程结构与 writer 线程亲和未定 | §2.4 交易进程表（主线程 + relay/consumer/heartbeat 三守护线程）+ writer `check_same_thread=False` + `_write_lock`；心跳改 **Redis TTL**（§3.1/§3.5），避免每秒 fsync；新增 **D20** | 启动/退出顺序、`join(5s)`、心跳键 TTL 均已写明；`meta` 只留 schema_version/recovery_state |
| **F-D3**（P2） | 属实：`cancel_all` 返回类型变更与 §0.3/I8 冲突且未登记 | 采纳「保留 int」方向：D11 改为 `cancel_all() -> int` 不变 + 新增 `cancel_all_ex() -> CancelAllReport`（§3.2）；**不新增 §8 偏差，I8 原样成立** | `CancelAllReport` 四字段与 Q12「requested/submitted/deferred」对齐；P-053 既有测试无需改签名 |
| **F-D4**（P2） | 属实：Ledger 侧组合写调用链与失败回滚未定义 | §3.3 新增「Ledger 侧写入契约」：store-first/memory-second 四步；`apply_fill(..., outbox_events=...)`；`apply_corporate_action`/`cash_adjust` 同路径；新增 **I17** | 与 `_append` 现状（ledger.py L260-L263）逐条对应；重复预检用 `_seen`，事件由 gateway 组装 |
| F-D5 | 属实：mypy 漏计 scripts +1；§0.2 实为 11 行 | §7/§10.1 改 **mypy 157**（+16）；PROGRESS §3.63 改「10 项定案 + 实施排期（11 行）」 | 141+3+12+1=157；black 309 不变（脚本已计入 +26） |
| F-D6 | 属实：market_gateway 进程归属未定 | §2.2 行内定案：**独立入口 `python -m services.market_gateway`（推荐）**，`--embedded` 由 trading_worker 内嵌；§10.2 B5 同步 | 与 D18「`--bus fake` 仅开发/测试」不冲突 |
| F-D7 | 属实：ticket 用例在 FakeBus/单测下无实现 | §2.2 auth 行改为 **`TicketStore` Protocol + Redis/InMemory 两实现** | `test_p054_api_auth` 的「单次使用/过期」可用 InMemory 版本测试，不依赖 Redis |
| F-D8 | 属实：`/api/orders` 过滤无 store 方法 | §3.7 明确 **`load_orders()` 内存过滤**（自用规模），并注明 >1 万单再引入 SQL 过滤；404 依赖全量比对 | 不新增 Protocol 方法，保持 §3.3 精简 |
| F-D9 | 属实：preflight 缺「库未初始化」分类 | risk_anchors §2.5 改为 `StoreReadOnlyError.reason` 四分类（permission/uninitialized/not_wal/internal_api_required）+ 错误消息映射；DESIGN §3.3 同步 | 与 §3.1 迁移时序一致（fresh DB 先由 trading_worker 初始化） |
| F-D10 | 属实：S62-S72 编号空间分裂 | risk_anchors §5 声明「该段唯一定义在本表，后续从 S73 起」；RESEARCH §8 注同步 | 主 RESEARCH 不再新增 S62-S72 条目 |

**出口判定更新**：门禁 (b) 的唯一 CONFLICT（F-D3）已消除；F-D1/F-D2/F-D4 规格缺口已补齐；F-D5~F-D10 已修正/登记；门禁 (a)/(c)/(d) 维持 §7 结论 → **Step 4 关闭**，进入 Step 5 IMPL。

> 复核范围声明：本节只核对「发现属实 + 修复落点到位」，不代替第二轮异构复审；若 Step 5 落码时发现并发模型/组合写在真实代码上不可行，按门禁 (b) 回退 DESIGN 修订。

---

## 9. 二轮异构复审（修复核验，2026-11-22）

> **触发**：用户指令「执行第二轮异构复审」（对象 = §8 回执与 10 项修复落盘）。**复审基座 GLM-5.3-Flash ≠ 修复执行基座 DeepSeek-V4.1-Flash** → 异构成立。方法：修复位点逐点重放 + `reserve/settle_reserve` 等关联面读码 + 残留扫描（grep）+ 回执准确性核对。复审方仅标记问题、顺手修正无歧义 P3 措辞，不改写 §8 回执正文与裁决内容。

### 9.1 十项修复落盘重放（10/10 与回执一致）

| ID | 重放结果 |
|----|----------|
| F-D1 | ✅ §2.4「API/WS worker」：每 worker 一个只读连接、`check_same_thread=False` + `_read_lock`、lifespan 开关、REST `def` 线程池、WS 快照 `anyio.to_thread`；无跨 worker 共享连接 |
| F-D2 | ✅ §2.4 交易进程表（主线程 + relay/consumer/heartbeat 三守护线程）+ writer `_write_lock`；心跳改 Redis TTL（§3.1 meta 移除心跳键、§3.5 两心跳键、拓扑图同步、D20、`heartbeat_ttl_seconds` 配置）；启动/退出顺序完整 |
| F-D3 | ✅ D11 保留 `cancel_all() -> int` + 新增 `cancel_all_ex() -> CancelAllReport`；§0.3/I8 原样；§8 十项偏差未新增（正确——保留 int 不构成偏差） |
| F-D4 | ✅ §3.3「Ledger 侧写入契约」store-first/memory-second 四步 + `apply_fill(..., outbox_events=())` + I17 + atomic 16 例纳入；**关联面读码补充核验**：`reserve/release/settle_reserve` 只改内存、不触 store（[ledger.py#L63-L84](../live/ledger.py#L63-L84)），无需纳入 store-first 契约 → 范围自洽 |
| F-D5 | ✅ DESIGN §7/§10.1 mypy **157**（+16 含 scripts）；DESIGN 全文无 156 残留（仅 PROGRESS 历史记录保留订正注） |
| F-D6 | ✅ §2.2 market_gateway 行「独立入口（推荐）/ `--embedded`」+ §10.2 B5 同步 |
| F-D7 | ✅ §2.2 auth 行 `TicketStore` Protocol + Redis/InMemory；§10.2 B4 同步 |
| F-D8 | ✅ §3.7 `/api/orders` 行明确 `load_orders()` 内存过滤 + 升级阈值（>1 万单） |
| F-D9 | ✅ DESIGN §3.3 preflight 四分类 + risk_anchors §2.5 代码改 `StoreReadOnlyError(reason=...)` + 分类说明 |
| F-D10 | ✅ risk_anchors §5 编号约定（S62-S72 唯一定义、后续从 S73 起）+ RESEARCH §8 注同步；RESEARCH 全文 S62-S72 引用仅 §8 注与 §22.3 两处，均有指向 |

### 9.2 残留扫描与新发现（0 P1 / 0 P2 / 5 顺手修正 + 2 登记）

**残留扫描**：`heartbeat_ts`/`consumer_heartbeat_ts`/`consumer_pending`（meta 旧键）0 残留；`SELECT 1`（旧 preflight）0 残留；DESIGN 内 `mypy 156` 0 残留；「cancel_all 返回 {requested…}」旧口径 0 残留。

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| O-R2-1 | P3 | **心跳写方归属前后不一**：§2.4 说 heartbeat 线程写两个心跳，§3.5 却写「交易进程主循环（每 1s）」与「consumer 线程（每 2s）」 | **顺手修正**：§3.5 两行写方统一为 heartbeat 线程（consumer 心跳注明 pending 数来自 consumer 线程内存） |
| O-R2-2 | P3 | **meta 键数口径不一**：§2.4「meta 只保留 schema_version / recovery_state」漏 §3.1 的 `recovery_ts` | **顺手修正**：§2.4 改「低频键（schema_version / recovery_state / recovery_ts）」 |
| O-R2-3 | P3 | risk_anchors §2.6 探针行仍写「消息含三条修复路径」、DESIGN §9-R1 处置列同——与四分类口径未对齐（permission 场景确为三条，但表述易误读为全局仍三条） | **顺手修正**：两处改「按 `reason` 给出对应修复路径」（permission 注明三条） |
| O-R2-4 | P3 | **§3.2 标题范围与代码块内容不符**：标题只列 events.py/flow_control.py，但块内含 `StoreReadOnlyError`/`OutboxEventConflict`（ledger_store.py）与 `CancelAllReport`（gateway 域）——Step 5 可能落错文件 | **顺手修正**：代码块后加「落点归属」注，逐类型标明所属模块 |
| O-R2-5 | P3 | **主线程内联调度等待会阻塞 poll**：§2.4 主线程行含 QueryScheduler；运行期巡检每次查询最多阻塞 ~1s（退避时更久），成交回报 poll 相应延迟。自用 + A股 3s 快照下可接受，但属已知代价 | **登记**：留 Step 5 落码确认；若实测不可接受，巡检移独立线程（不改本轮验收） |
| O-R2-6 | P3 | `StoreReadOnlyError.reason="internal_api_required"` 为 Plan B 预留，但本批 §3.8 无内部 API 配置入口（D17「只文档化」） | **登记**：本批不实现；Step 5 不引入该配置，reason 枚举仅占位 |
| O-R2-7 | — | 复审方核对回执本身：§8 表 10 行与 §5 发现一一对应、头/尾计数（4 P2 + 6 P3）一致、无改写 §5 原文 | ✅ 回执准确 |

### 9.3 出口判定（二轮）

- 10/10 修复落盘与回执一致；门禁 (a) FALSIFIED = 0、(b) CONFLICT = 0（F-D3 采用「保留 int」后无矛盾）、(c) 双源与 (d) 假设携带维持 §7 结论。
- 新发现 0 P1 / 0 P2；P3 ×5 已顺手修正、×2 登记 → **Step 4 维持关闭（2026-11-22）**，进入 Step 5 IMPL。
- 本节为修复核验（定点），非全量三轮复审；Step 5 落码后由 Step 6 IMPL 复审继续把关。

> 复审方顺手修正清单：DESIGN §3.5 两行（O-R2-1）、§2.4 一行（O-R2-2）、§9-R1 处置列（O-R2-3）、§3.2 落点归属注（O-R2-4）；risk_anchors §2.6 一行（O-R2-3）。
