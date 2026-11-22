# RESEARCH：P-054 服务层 · 前置登记项专项（U-P053-17 / U-P053-18）

> **批次**: P-054 · **Step 1 调研（前置专项）** · 日期 2026-11-22 · **判档 P2**（后续全量 T1）
> **上游口径**: [UPGRADE_MASTER_PLAN](UPGRADE_MASTER_PLAN.md) §3 **F7**（L223-232）/ §5 **L271**（P-054）/ §7 第 9 条 + **§7.1 D2**（自用工具 + 完成程序化报备 + API 仅本机/内网）
> **前置**: P-053 ✅ 已关闭（`7f01b84` feat + `a67a26b` docs 关闭，CI run `44987704764` 四 job 全绿）/ P-052 ✅ / P-043 ✅
> **范围**: 仅 **U-P053-17 / U-P053-18** 两项「P-054 硬前置」+ U-P053-15/16/19/20 低风险项处置建议；**不含 F7 全量调研**（FastAPI/WS/Redis/鉴权/TLS/可观测性留后续完整 Step 1）
> **方法**: E3 本仓读码（`a67a26b`）→ E1 一手规范/官方文档 → E2 工程实践（反例与陷阱）
> **基线读数 @`a67a26b`**: pytest **1300** / golden **22** / mypy **141 files 0** / black **283** / `tests/*.py` **141** / `core/*.py` **51** / `live/*.py` **16**
> **状态**: 前置专项调研完成（**未改代码、未提交**）→ 待 Step 2 异构复审 → 待全量 Step 1 合并

---

## 0. 结论摘要（TL;DR）

1. **U-P053-17 比登记描述更严重**：不仅是「订单 + outbox 两事务」，而是 **`LedgerStore` 的公开写方法全部各自开事务且不可组合**（SQLite `BEGIN...COMMIT` 不可嵌套，T1），因此**当前没有任何公开入口**能把「业务写 + outbox 写」放进同一事务。
2. **成交链路与设计声明不符**：DESIGN §3.3 写「`apply_fill` 写 entry + 写 outbox 在一个 `transaction()` 内（N-4）」，实测 `apply_fill` **既不写 outbox，且 `fill` / `fee` 两条分录分属两个事务**（[ledger.py](../live/ledger.py#L117-L143) → [L260-L263](../live/ledger.py#L260-L263)）。崩溃点落在两条分录之间会造成现金与手续费口径不一致。
3. **outbox 目前只含「委托受理」一种事件**（payload 仅 `coid`）：成交 / 状态迁移 / 撤单 / 对账均**不入 outbox**（[gateway.py](../live/gateway.py#L267-L274) vs [L339-L353](../live/gateway.py#L339-L353) / [L398-L399](../live/gateway.py#L398-L399) / [L453-L456](../live/gateway.py#L453-L456)）。P-054 若要做「订单/成交可靠外发」，必须先补齐事件覆盖面。
4. **outbox 消费端为零**：`pending_outbox()` 仅测试读取，`mark_sent()` 全仓无调用方（T1 读码）——符合 P-053 D16「只写不读」，但意味着 P-054 必须自建 relay + ACK + 幂等。
5. **U-P053-18 是确定性启动失败（真机口径）**：`start()` 在同一次启动里连续发起 3 次查询，`_throttle_query` 只 check 不等待，CTP `max_query_per_sec=1`，`check_rate` 只查当前秒桶 → **第 2 次查询同一秒内即抛 `ChannelUnavailable`**，`start()` 中断。测试不可达是因为 mock 通道 `max_query_per_sec=10.0`。
6. **外部一手锚点齐备**：事务性 outbox（微服务模式目录，T1）+ SQLite 事务不可嵌套/单写者（T1 官方，2026-02-18 更新）+ 退避与抖动（Amazon Builders' Library，T1 官方）；「at-least-once ⇒ 消费端必须幂等」是 outbox 模式的**强约束而非可选项**。
7. **对 P-054 的四项硬输入**：① 新增「一次事务内组合写」的仓储 API（订单/分录/outbox 同提交），事件 `event_id` 改**业务键派生**以支撑消费端去重；② 新增**查询调度器**（最小间隔 + `-2/-3` 指数退避 + 全抖动 + 启动期串行合并），并把 P-054 的 `/health/ready` 与 WS 首帧 snapshot 挂在恢复序完成之后；③ **通道流控前置包**（Q8 FTD 共享预算 + Q9 order-flow 合并预算 = 2×internal，§15/§17/§18）；④ **outbox `seq`/inbox 迁移**（Q11 已裁决，§16）。
8. **社区案例（§12）独立印证方案 A**：同栈 Python+SQLite 的 outbox+inbox 可复现案例（S11）、vnpy 的「双队列 + 退避」实践（S15）与「1/s + 单在途」双源锚点（S16/S17）均支持推荐方案；并**新增裁决点 Q8**——CTP 查询会占用报单的共享 FTD 6/s 额度，P-053 三桶独立可能高估可报单量。
9. **Q8 专项（§13）结论**：FTD 是**每 Session 全接口共享**额度（登录/查询/报单/撤单/报价），超限由前置**缓存到下一秒且不返回错误**（S21/S16），故失败模式是**延迟而非拒单**；社区常见默认 6/s 但券商可配（S15/S22/S23）。按当前代码公式，内部速率 1/s 时同秒最坏 3 笔（安全），**≥3/s 即越界**（7+ 笔），而 CTP 能力声明 `10/10` 与 FTD 6 不一致。另发现 **G11/Q9**：柜台报单流控是报单+撤单**合并**额度，本仓 submit/cancel 独立台账在内部 1/s 下仍可同秒 2 笔。
10. **算法源码取证（§14）**：本仓 `check_rate` 属**整数秒固定窗口**，与 `limits.FixedWindowRateLimiter` / PyrateLimiter `FixedWindow` 同类；上游源码明示固定窗口**跨边界可达 2×limit**（G12）。更关键的是计量口径：前置 FTD **发送即计**，本仓**成功才 record**（[gateway.py#L261](../live/gateway.py#L261) / [L396](../live/gateway.py#L396)），台账系统性低估消耗（G13）；且 `check_rate`+`record` 是 check-then-act，多 worker 必须合并为 `try_acquire()->Decision`。退避直接照 tenacity 源码公式：`high=min(multiplier*2**(n-1), max)`、`sleep=uniform(min, high)`（Full Jitter）。vnpy_ctp 源码用**定时器串行轮询**（每两 tick 只发一个查询）规避启动期同秒多查询，是 U-P053-18 的工程同构解。
11. **Q11 专项（§16）结论**：outbox 的稳定顺序不能依赖默认 `rowid`——SQLite 官方明确「删除最大行后 rowid 可能复用」「VACUUM 会改变无 `INTEGER PRIMARY KEY` 表的 rowid」（S33/S34）；应改为显式 `seq INTEGER PRIMARY KEY AUTOINCREMENT`（保证从未使用且单调递增，S33）+ `(sent, seq)` 索引。`event_id` 需**版本化业务键**（`order:{coid}:{event}:v{n}`），同 key 不同 payload 必须**报错而非静默忽略**（Stripe 幂等语义，S36）；消费端配 inbox 去重（S1/S35）。**Q11 已裁决纳入 P-054 批内**（§16.6）。
12. **全量 Step 1（§19）结论**：FastAPI 上游已要求 Python **>=3.11**，与本仓 3.10 基线冲突 → **已裁决（Q13）：全局升到 3.11**（3.10 已于 2026-10-01 EOL，S50）；F7 的 **uvloop 在 Windows 不可用**（uvicorn 原文）→ Windows=asyncio；WS **出站背压必须自建**（uvicorn `--ws-max-queue` 只管入站）；鉴权用 API Key + `hmac.compare_digest`，浏览器 WS 用**短时 ticket/子协议**；内网强制 TLS；指标用官方 `prometheus-client`；**已裁决（Q14）：直接 F7 全量多 worker**（行情 Pub/Sub + 订单 Streams）——但必须先解决 **G16**（SQLite 单写者 → 拆「单实例交易/账本进程 + N 无状态 API/WS worker」）与 **G17**（Windows Redis/CI），见 §21。**§22 已把剩余 Q12/Q15-Q20 全部裁决**（单写者拆分、Redis/CI、读路径、鉴权、TLS、可观测性、kill-switch）。

---

## 1. 题干与范围

### 1.1 P-054 总纲口径（F7，L223-232）

| 能力 | 总纲要求 | 本专项是否覆盖 |
|------|----------|----------------|
| 新模块 | `services/api.py`（FastAPI）/ `services/ws_hub.py` / `services/market_gateway.py` | 否（全量 Step 1） |
| 拓扑 | 行情网关 → Redis Streams → 快照聚合 → FastAPI+uvicorn(uvloop) 多 worker WS 扇出 | 否；**§7.2 给降低复杂度的前置判断** |
| 背压 | 每连接 bounded asyncio.Queue；行情可丢、**订单不可丢**；订单/成交走 Streams 消费组 + ack | **是**（U-P053-17 是「订单不可丢」的落库前提） |
| 重连 | snapshot + delta，消息带 seq；心跳 + 客户端指数退避 | 部分（退避原则 §5） |
| 安全 | REST/WS 鉴权（API Key/JWT）+ TLS + CORS 白名单；密钥不入库 | 否（全量 Step 1；D2 已定「仅本机/内网」） |
| 可观测性 | Prometheus + 结构化日志 + 告警 + **延迟基准报告** | 否；**§7.3 给启动期可测口径** |
| 验收 | WS seq 连续；snapshot+delta 重放一致；401/403；REST 管理面可写但不含下单/撤单交易逻辑 | 否（全量 Step 1） |

### 1.2 两项硬前置的登记原文（[REVIEW_p053_step10 §6](REVIEW_p053_step10_acceptance.md)）

- **U-P053-17 outbox「同事务」公开 API 缺口（P2）**：outbox 三表原子性仅裸 SQL 可达；`append_entry`/`upsert_order`/`append_outbox` 公开方法各自独立事务；gateway 生产路径「订单 + outbox」两事务非原子。计划：**P-054 前置项**——outbox 消费端设计时落地「订单 + outbox 组合事务」入口。
- **U-P053-18 CTP 启动期同秒 3 查询限流（P2）**：CTP 查询流控 1 笔/秒；`start()` 恢复序同秒 `query_trades` + `query_orders` + reconcile `query_positions` 三连发。计划：**P-054 前置项**——真实接线批为查询路径增加 `-3` 退避重试与启动期查询合并。

### 1.3 已裁决口径（本专项不得重开）

- **D2（合规定位）**：自用工具 + 完成程序化报备；默认速率 ≤1 笔/秒、≤1000 笔/日；**API/WS 仅本机/内网**（决定鉴权与 TLS 强度，D2 已裁）。
- **D4（粒度）**：每批须有 synthetic fixture + golden；禁止因外部数据/权限缺失阻断开发。
- **D16（P-053）**：outbox 本批只写不读，送达循环归 P-054。
- **D1（P-053）**：多通道预留，首发真实连通 = CTP/SimNow；P-054 的真实接线对象按此口径。

### 1.4 本轮明确不做

不改任何代码；不提交；不做 F7 全量调研（FastAPI 版本/WS 协议/Redis 引入与否/鉴权方案）；不重开 P-053 已关闭项。

---

## 2. 代码现状（E3，`a67a26b`）

| 位置 | 事实 | 对本专项的影响 |
|------|------|----------------|
| [ledger_store.py#L31-L40](../live/ledger_store.py#L31-L40) | `LedgerStore` Protocol 暴露 8 个方法 + `transaction()` | 有事务原语，但无「组合写」方法 |
| [ledger_store.py#L140-L148](../live/ledger_store.py#L140-L148) | `transaction()` = `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` | 每次 `with` 都开新事务；**在事务内再调用 `append_*` 会触发嵌套 BEGIN** |
| [ledger_store.py#L63-L82](../live/ledger_store.py#L63-L82) | `append_entry` 自开事务 | 不可与 outbox 同事务组合 |
| [ledger_store.py#L93-L108](../live/ledger_store.py#L93-L108) | `upsert_order` 自开事务 | 同上 |
| [ledger_store.py#L121-L126](../live/ledger_store.py#L121-L126) | `append_outbox` 自开事务，`INSERT OR IGNORE` | 同上；`event_id` 冲突即静默丢弃 |
| [ledger_store.py#L128-L136](../live/ledger_store.py#L128-L136) | `pending_outbox` / `mark_sent` 已实现 | 供 P-054 relay 消费 |
| [ledger.py#L96-L145](../live/ledger.py#L96-L145) | `apply_fill` 可能写 `fill` + `fee` **两条分录** | 两条分录跨两个事务（见 G2） |
| [ledger.py#L260-L263](../live/ledger.py#L260-L263) | `_append` 逐条调用 `store.append_entry` | 无批量、无 outbox |
| [gateway.py#L267-L274](../live/gateway.py#L267-L274) | submit ⑧：`upsert_order`（事务 A）→ `_audit`（JSONL）→ `append_outbox`（事务 B） | 订单与 outbox 非原子（U-P053-17 核心） |
| [gateway.py#L339-L353](../live/gateway.py#L339-L353) | `_apply_order_report`：`upsert_order` + `_audit`，**无 outbox** | 状态迁移事件外部不可达 |
| [gateway.py#L398-L399](../live/gateway.py#L398-L399) | `cancel`：`upsert_order` + `_audit`，**无 outbox** | 撤单事件外部不可达 |
| [gateway.py#L453-L456](../live/gateway.py#L453-L456) | `confirm`：`upsert_order` + `_audit`，**无 outbox** | 人工确认事件外部不可达 |
| [gateway.py#L286-L294](../live/gateway.py#L286-L294) | poll 成交路径：`apply_fill` + `_audit(AUDIT_FILL)`，**无 outbox** | 成交事件外部不可达 |
| [gateway.py#L111-L153](../live/gateway.py#L111-L153) | `start()` 恢复序：2 次 `_throttle_query` + `reconcile()` 内第 3 次 | U-P053-18 现场 |
| [gateway.py#L355-L361](../live/gateway.py#L355-L361) | `_throttle_query`：check 失败**直接 raise**，无等待/无重试 | 无退避（U-P053-18 根因之一） |
| [gateway.py#L120-L123](../live/gateway.py#L120-L123) | `_query_config.max_per_second = max(1, round(query_per_sec))` | CTP → 1 |
| [ctp.py#L61](../live/adapters/ctp.py#L61) | `max_query_per_sec=1.0` | 与上项合并 → 同秒第 2 次必拒 |
| [ctp.py#L79-L84](../live/adapters/ctp.py#L79-L84) | `-2/-3` → `ChannelUnavailable`（可重试，不计柜台拒单） | 退避重试的语义基础 |
| [mock.py#L61](../live/adapters/mock.py#L61) | `max_query_per_sec=10.0` | 解释「测试环境不可达」 |
| [compliance.py#L123-L137](../core/compliance.py#L123-L137) | `check_rate` 只查 `int(ts)` 当前秒桶 | 同秒第 2 次必然 `per_second` 拒绝 |
| [compliance.py#L101-L113](../core/compliance.py#L101-L113) | `record` 保留 `sec-1` 与 `sec` 两秒桶 | 仅保留近 2 秒，符合「当前秒桶」判定 |

---

## 3. 发现表

| ID | 级别 | 结论 | 证据（E） | 处置建议 |
|----|------|------|-----------|----------|
| **G1** | **P1** | 无公开入口可原子提交「业务写 + outbox」：每个写方法自开事务，且 SQLite 事务不可嵌套 | E3: [ledger_store.py#L63-L148](../live/ledger_store.py#L63-L148)；E1: SQLite 官方「BEGIN…COMMIT 不可嵌套」 | 新增组合写 API（§4.3 方案 A） |
| **G2** | **P1** | `apply_fill` 的 `fill`/`fee` 两条分录跨两事务，且不写 outbox；与 DESIGN §3.3 N-4 声明不符 | E3: [ledger.py#L117-L143](../live/ledger.py#L117-L143) + [L260-L263](../live/ledger.py#L260-L263)；[DESIGN_p053#L353](DESIGN_p053_trading_gateway.md) | 批量分录 + outbox 同事务；订正 DESIGN |
| **G3** | P2 | outbox 只覆盖「委托受理」；成交/迁移/撤单/对账不入 outbox | E3: [gateway.py#L267-L274](../live/gateway.py#L267-L274) vs [L339-L456](../live/gateway.py#L339-L456) | P-054 先定「外发事件集合」再补写点 |
| **G4** | P2 | outbox 消费端为空（`mark_sent` 无调用方） | E3: 全仓 grep；仅 `tests/test_p053_*` 读 `pending_outbox` | P-054 实现 relay + ACK + 幂等 |
| **G5** | **P1（真机）** | CTP 启动期 3 查询同秒 → 第 2 次 `check_rate` 拒绝 → `start()` 抛 `ChannelUnavailable` | E3: [gateway.py#L147-L153](../live/gateway.py#L147-L153) + [L355-L361](../live/gateway.py#L355-L361) + [ctp.py#L61](../live/adapters/ctp.py#L61) + [compliance.py#L128-L131](../core/compliance.py#L128-L131) | 查询调度器 + 退避（§5.3 方案 A） |
| G6 | P3 | `event_id = uuid4()` 非确定性，不利消费端重放去重 | E3: [gateway.py#L270](../live/gateway.py#L270) | 改业务键派生（§16.5 已细化：`<type>:<coid>:<event>:v<n>` 版本化） |
| G7 | P3 | `Ledger.resume` 一次性迭代器静默空账本（U-P053-16） | E3: [gateway.py#L138-L140](../live/gateway.py#L138-L140) 传 list，当前安全 | P-054 接线时固化 `Sequence` + 空账本断言 |
| G8 | P3 | 死代码 `_ceil_positive` / `_SOURCE`（U-P053-15） | E3: [channel.py#L184](../live/channel.py#L184)、[orders.py#L91](../live/orders.py#L91) 无调用方 | P-054 refactor 顺手清除 |
| G9 | 观察 | F7 的 Redis Streams 拓扑与本仓「自用/内网」口径张力；**更正**：`pyproject` **已声明 `redis>=4.5.0`**（[L45](../pyproject.toml#L45)）与 `pydantic>=2.0.0`（L35），仅 fastapi/uvicorn 未声明；D14 零依赖是 P-053 批内规则（§19.1） | E1: [UPGRADE_MASTER_PLAN#L225](UPGRADE_MASTER_PLAN.md)；E3: [pyproject.toml#L45](../pyproject.toml#L45) | 全量 Step 1 裁决（§19） |
| **G10** | **P2** | 未建模 CTP 共享 FTD 6/s 预算：submit/cancel/query 三独立桶，内部速率≥3 时同秒最坏 7+ 笔 FTD；能力声明 10/10 与 FTD 6 不一致 | E3: [gateway.py#L102-L133](../live/gateway.py#L102-L133) + [ctp.py#L58-L61](../live/adapters/ctp.py#L58-L61)；文献: S21/S15/S22 | Q8 专项（§13） |
| **G11** | **P2** | 柜台「报单流控」是报单+撤单**合并**每秒额度，而本仓 submit/cancel 各用独立台账：内部 1/s 下可同秒 1 报 + 1 撤 = 2 笔，可能超柜台配置且与 D2「≤1 笔/秒」口径不符 | E3: [gateway.py#L102-L104](../live/gateway.py#L102-L104) + [L199-L200](../live/gateway.py#L199-L200) + [L385-L386](../live/gateway.py#L385-L386)；文献: S21 | Q9 专项（§13.6） |
| **G12** | P3 | 本仓限流是**整数秒固定窗口**：`check_rate` 只看当前秒桶，跨秒边界任意滚动 1s 内可达 2×limit；与 CTP 前置「自然秒」同构，故对前置无害，但对外承诺「严格 N/s」不成立 | E3: [compliance.py#L101-L113](../core/compliance.py#L101-L113) + [L123-L137](../core/compliance.py#L123-L137)；源码: S24（`FixedWindow` 原文 "up to 2 * limit across a window boundary"）/ S26 | §14.3；P-054 对外限流改用滑动日志/GCRA |
| **G13** | **P2** | 计量口径不一致：前置 FTD/报单流控**发送即计**，本仓仅**成功才 record**（拒单、`ChannelUnavailable` 均不记）→ 内部台账低估真实 FTD 消耗，Q8 方案 A 若沿用会超发 | E3: [gateway.py#L261](../live/gateway.py#L261) + [L392-L396](../live/gateway.py#L392-L396) + [L355-L361](../live/gateway.py#L355-L361)；文献: S21/S16 | §14.3/§14.9：`FtdBudget.reserve` 必须在**发送前**扣减 |
| **G14** | P3 | outbox relay 两个源码级隐患：`pending_outbox` 仅 `ORDER BY created_ts`（同秒并列无稳定序）；`INSERT OR IGNORE` 对同 `event_id` 不同 payload **静默丢弃** | E3: [ledger_store.py#L121-L136](../live/ledger_store.py#L121-L136) | §16：`seq AUTOINCREMENT` + `(sent, seq)` 索引 + `event_id` 版本化（已裁决） |
| **G15** | **P2** | **撤单被拒静默失败**：`cancel()` 在预算拒绝时 `return False`、无 audit、无原因（[gateway.py#L385-L389](../live/gateway.py#L385-L389)），与「订单不存在/已终态」的 `False` 不可区分；`cancel_all`（急停路径，[L407-L409](../live/gateway.py#L407-L409)）逐单调 `cancel()` → 同秒第 2 笔起撤单被静默丢弃，**风险削减动作静默失效** | E3: 上述行号；总纲 S1「可选一键撤单」（[UPGRADE_MASTER_PLAN#L159](UPGRADE_MASTER_PLAN.md)）；P-052 §4.4 RTS 6 Art.12「kill = 立即撤下全部」 | §17.3；P-054 批内：撤单拒绝必须 audit + 显式原因；kill-switch 预算语义另裁（Q12） |
| **G16** | **P1（Full 拓扑）** | **F7 多 worker 与 SQLite 单写者直接冲突**：`SqliteLedgerStore.__init__` 用 `O_CREAT\|O_EXCL` 抢 `.lock`（[ledger_store.py#L49-L51](../live/ledger_store.py#L49-L51)），第二个进程启动即失败；`EventLog` 的 `RLock` 仅进程内（[event_log.py#L123](../core/event_log.py#L123)），多 worker 共写同一 JSONL 不安全。**直接 `--workers N` 会让第 2 个 worker 起不来** | E3: 上述行号；F7 L231「禁止依赖进程内状态」 | **§22.1 已裁决：单实例交易/账本进程 + N 无状态 worker（P1 已缓解）** |
| **G17** | **P2（Full 运维）** | **Windows 无官方 Redis**：官方原文「not officially supported on Windows」，需 WSL2/Docker（S51）；CI 需 Redis service 或 FakeBus，否则 Full 在开发机不可跑、门禁不可复现 | S51；[tests.yml#L10-L16](../.github/workflows/tests.yml#L10-L16) | **§22.2 已裁决：Docker Desktop(WSL2) + CI `services: redis` + FakeBus（P2 已缓解）** |

---

## 4. U-P053-17：outbox 同事务缺口

### 4.1 事实链

1. **事务原语存在但不可组合**：`transaction()` 是 `BEGIN IMMEDIATE`；SQLite 官方明确「用 `BEGIN…COMMIT` 创建的事务不可嵌套；在事务内再执行 `BEGIN` 会报错」（T1）。因此调用方即使写 `with store.transaction(): store.upsert_order(...); store.append_outbox(...)`，也会在第二个 `with` 处触发嵌套 BEGIN 而失败。
2. **业务写与 outbox 分属两次提交**：submit 成功路径先 `upsert_order`（事务 A），再 `append_outbox`（事务 B）。进程在 A 与 B 之间崩溃 → **订单已持久化、事件永久缺失**；崩溃在 B 之后 → 正常。这正是事务性 outbox 模式要消除的「双写不一致」。
3. **成交链路更脆弱**：`apply_fill` 先写 `fill` 分录、再写 `fee` 分录（两条独立 `append_entry`）。崩溃在两者之间 → 现金已按成交额扣减、但手续费未扣；`snapshot()` 重放会得到与运行态不一致的现金（DESIGN I4 现金守恒在**持久化层**被打破，虽然单进程内存态不会）。并且两条分录都不进 outbox。
4. **outbox 覆盖面不足**：reflect「订单/成交走可靠通道」的 F7 背压口径，当前 outbox 只有 `AUDIT_ORDER/accepted`，payload 只有 `coid`，没有成交金额/数量/状态等外发所需字段。

### 4.2 崩溃点后果矩阵（submit 成功路径）

| 崩溃点 | 订单记录 | outbox | 外部可见后果 |
|--------|----------|--------|--------------|
| `upsert_order` 之后、`append_outbox` 之前 | ✅ 已落库 | ❌ 缺失 | 订单已受理但外部永远收不到通知 → 对账/前端静默漏单 |
| `append_outbox` 之后、返回前 | ✅ | ✅ | 一致 |
| `apply_fill` 的 `fill` 与 `fee` 之间 | 分录只落一半 | 无关（本就不写） | 重启后现金/手续费口径不一致 |

### 4.3 候选方案

| 方案 | 做法 | 优点 | 代价 / 风险 |
|------|------|------|-------------|
| **A（推荐）显式组合写方法** | 在 store 内加私有非事务 `_insert_*`，对外暴露原子方法：`append_entries(entries)`、`upsert_order_with_events(record, events)`、`append_entries_with_events(entries, events)`；每次内部只用一个 `transaction()` | 语义清晰、可单测、无嵌套问题、mypy 友好、改动面可控 | Protocol 方法数增加；需成对维护单写/组合写两条路径 |
| B 事务内传入连接 | 公开方法加 `conn: sqlite3.Connection \| None = None`，`None` 时自开事务 | 复用现有方法 | Protocol 泄露 sqlite 类型；可测性/可移植性差；调用方易误用 |
| C SAVEPOINT 可重入 | 用 SAVEPOINT 让公开方法可重入，调用方包一层 | 保持现有方法签名 | 嵌套层级判定复杂、错误语义难控，收益低 |

> **推荐 A**：一次性把「业务写 + outbox」收敛到 store 的显式组合方法，ledger/gateway 只调用组合方法；单写方法保留供只读/测试场景。

### 4.4 裁决点

- **Q1 外发事件集合**：P-054 需要外发哪些事件？建议最小集 = 委托受理 / 委托状态迁移（含拒绝、撤单）/ 成交（fill）/ 对账结果；由 P-054 设计定稿。
- **Q2 `event_id` 生成**：改为业务键派生（`order:{coid}:accepted`、`fill:{fill_key}`）以支撑消费端按 ID 去重与重放；需与 `INSERT OR IGNORE` 的幂等语义配合。
- **Q3 改造落点**：P-054 批内改 `live/`（推荐，消费端同批可联调）vs 单开 P-053b 补丁批（隔离但多一轮流程）。
- **Q4 消费载体**：relay 以轮询 `pending_outbox()` 实现（零依赖），还是引入 Redis Streams（总纲 F7）——见 §7.2。

### 4.5 对 P-054 设计的影响

- P-054 的「订单不可丢」不能只靠 WS 层 bounded queue，**必须先有原子 outbox**；否则服务层再可靠也补不回未写入的事件。
- relay 契约（草案）：`pending_outbox()` 批次取 → 投递（WS broadcast / HTTP webhook）→ 成功后 `mark_sent(event_id)`；失败保留 `sent=0` 下轮重试（at-least-once）；消费端按 `event_id` 幂等。
- `mark_sent` 与「投递成功」之间的崩溃会重复投递——这正是 at-least-once 的必然，需在 P-054 验收里显式接受并测试重复帧去重。

---

## 5. U-P053-18：CTP 启动期查询限流

### 5.1 事实链

1. `start()` 恢复序（SSE）：`_throttle_query(now)` → `query_trades` → `_throttle_query(now)` → `query_orders` → `reconcile(ts=now)` → 内部 `_throttle_query(ts)` → `query_positions`。
2. `_query_config.max_per_second` 由 `resolve_limits` 得 CTP `query_per_sec=1` → `max_per_second=1`。
3. `check_rate` 只查 `int(ts)` 当前秒桶；`record` 使当前秒计数 +1。首次 0<1 放行；第二次 1≥1 拒绝。
4. `_throttle_query` 拒绝时直接 `raise ChannelUnavailable`——**没有等待、没有重试**。
5. 结论：真实 CTP 环境 `start()` 第 2 次查询即中断；mock 通道 `query_per_sec=10` 使测试通过（测试不可达）。
6. 幂等性前提已具备：`apply_fill` 用 `fill_key` 去重（`_seen`），`query_orders` 回报经 `transition` 合法迁移 + 非法迁移 audit 忽略 → **重试不会重复入账**，可安全退避重试。

### 5.2 后果

- 崩溃重启后无法完成「先成交、再订单、再持仓」恢复序 → 本地账本与远程状态不一致，P-054 的 `/health/ready` 与 WS 首帧 snapshot 都可能建立在错误基线上。
- 若简单地「提高 query_per_sec」，会直接触发交易所/柜台流控（`-2/-3`），且违反 CTP 查询 1 笔/秒的通道事实。

### 5.3 候选方案

| 方案 | 做法 | 优点 | 代价 / 风险 |
|------|------|------|-------------|
| **A（推荐）查询调度器 + 退避** | 新增 `live/query_scheduler.py`（注入 clock/sleep，纯逻辑可测）：① 保证相邻查询间隔 ≥ `1/query_per_sec`；② 捕获 `ChannelUnavailable`(`-2/-3`) 做**指数退避 + 全抖动**，封顶且限次；③ 启动期把 3 次查询收束为**单一串行恢复例程**（trades → orders → positions） | 真机可跑；可测；对 P-054 无侵入；幂等前提已具备 | 启动期阻塞数秒；需改 `gateway.start()`（跨 P-053/P-054 边界） |
| B 仅 start() 内手写 sleep | 在恢复序三次查询之间 `sleep(1/query_per_sec)` | 改动最小 | 不处理 `-2/-3` 抖动；不可复用；并发/异常路径仍会破 |
| C 提高 query_per_sec | 配置绕开 | 零代码 | **错误**：违反 CTP 1 笔/秒，真机触发 `-2/-3` |

> **推荐 A**，并保留 B 作为 A 落地前的临时兜底（仅启动序，不打补丁到通用路径）。

### 5.4 裁决点

- **Q5 退避参数**：初始间隔、倍率、封顶、最大尝试次数（建议全抖动、封顶 5s、最多 5 次；需在 P-054 设计中定稿并在 CHECKLIST 写数值）。
- **Q6 失败降级语义**：3 次查询中某次最终失败时，`start()` 整体失败 vs 标记「恢复不完整」并继续（建议：`query_trades`/`query_orders` 失败即 fail-closed；`query_positions` 失败则标记 reconcile 不可用、网关进入降级态，不阻断启动）——由 P-054 设计裁决。
- **Q7 改造落点**：`live/` 内新增调度器 + 改 `start()`，属 P-054 的真实接线改造（与 U-P053-17 同批）。

### 5.5 对 P-054 设计的影响

- `/health/ready` 的语义应定义为「启动恢复序完成且账本可用」，而非「进程起来了」。
- WS 首帧 snapshot 必须等恢复序完成后再生成，否则会把「恢复中」的中间态推给客户端。
- 查询调度器是服务层与通道层之间的**唯一查询入口**，P-054 的任何后台巡检（对账/持仓刷新）都应走同一调度器，避免再次出现同秒多查询。

---

## 6. 其余登记项处置建议（U-P053-15/16/19/20）

| 项 | 结论 | 依据 | 建议 |
|----|------|------|------|
| **U-P053-15** 死代码 | 确认 `_ceil_positive`（[channel.py#L184](../live/channel.py#L184)）与 `_SOURCE`（[orders.py#L91](../live/orders.py#L91)）无调用方 | E3 全仓 grep | P-054 refactor 顺手删除；不单开批次 |
| **U-P053-16** `resume` 一次性迭代器 | 当前唯一调用点传 list，安全 | E3 [gateway.py#L140](../live/gateway.py#L140) | P-054 接线时把入参固化为 `Sequence` 并加空账本断言 |
| **U-P053-19** `attribute_break` 现金分支 | 不可达；属 P-056 现金/保证金账本面 | [REVIEW §6](REVIEW_p053_step10_acceptance.md) | **保持登记**，随 P-056 重审，P-054 不处理 |
| **U-P053-20** 测试缺口 | 5 条低概率回归盲区 | 同上 | 其中「恢复序 positions 段」「`_query_config` 默认接线」「resume 迭代器」与 P-054 直接相关 → 并入 P-054 测试计划；其余（CSV 表头、相位边界）保持登记 |

---

## 7. 对 P-054 设计/验收的输入

### 7.1 必须由 P-054 承接的四项改造

1. **原子仓储入口**（U-P053-17）：订单/分录/outbox 一次提交；事件 `event_id` 业务键派生（§4.3/§4.4）。
2. **查询调度器**（U-P053-18）：最小间隔 + `-2/-3` 退避 + 启动期串行合并 + 失败降级语义（§5.3/§5.4）。
3. **通道流控前置包**（Q8/Q9 已裁决，§15）：`FtdBudget` + order-flow 合并预算（默认 2×internal，§17/§18）+ CTP 能力声明修正（G10）。
4. **outbox `seq`/inbox 迁移**（Q11 已裁决，§16）：表重建 + relay 按 `seq` 排序 + `OutboxEventConflict` + 消费端 inbox。

### 7.2 Redis 引入与否（已裁决：Q14 = Full，§19.9/§20.6）

- 总纲 F7 要求 Redis Streams 多 worker 扇出；`redis` 依赖**已在 pyproject 声明**（[L45](../pyproject.toml#L45)），fastapi/uvicorn 未声明但总纲 §6 明确允许进 `[services]` extra；D2 已定「自用工具 + API 仅本机/内网」。
- **已裁决（Q14，2026-11-22 用户确认）：直接按 F7 全量多 worker 落地**——不采用「首发单 worker、Redis 后置增量」的过渡路径。落地前提见 §21：交易/账本进程单实例（SQLite 单写者）+ N 个无状态 API/WS worker；行情与订单/成交事件经 Redis Pub/Sub 广播，订单/成交另走 Streams 单一消费组保证 at-least-once。被拒方案（Phase 0 单 worker）的收益/代价见 §19.10/§20.4，Phase 0 仅保留为 FakeBus 测试替身。

### 7.3 验收读数（供后续 CHECKLIST 挂载）

- outbox 原子性：构造「业务写后崩溃」探针，断言 outbox 与业务行**同生同灭**（要么都在，要么都不在）。
- at-least-once：重复投递同一 `event_id` 时消费端只生效一次。
- 启动恢复序：CTP `query_per_sec=1` 下 `start()` 完成 3 次查询且无 `ChannelUnavailable`；注入 `-3` 后按退避重试成功。
- 幂等重试：同一 `fill_key` 重复回放不重复入账（复用既有 `_seen`）。

---

## 8. 来源清单（Layer / 日期 / 版本）

| # | 来源 | Layer | 发布/更新日 | 读取日 | 版本 | 用途 |
|---|------|-------|-------------|--------|------|------|
| S1 | [Transactional outbox — microservices.io](https://microservices.io/patterns/data/transactional-outbox.html) | **T1**（模式目录/一手定义） | 未标注 | 2026-11-22 | 页面无版本号 | outbox 定义、at-least-once、消费端必须幂等 |
| S2 | [SQLite: Transaction](https://www.sqlite.org/lang_transaction.html) | **T1**（官方文档） | 2026-02-18 更新 | 2026-11-22 | SQLite 文档页 | `BEGIN…COMMIT` 不可嵌套、单写者 |
| S3 | [Amazon Builders' Library: Timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) | **T1**（官方工程指南） | 未标注 | 2026-11-22 | 页面无版本号 | 超时/重试/退避/抖动 |
| S4 | [AWS Architecture Blog: Exponential Backoff and Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) | T2（官方博客） | 2015-03-04（2023-05 更新） | 2026-11-22 | 博客 | Full/Equal/Decorrelated Jitter 取舍 |
| S5 | [Azure Architecture Center: Transactional Outbox pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/transactional-outbox) | T1（官方文档） | 未取证 | 2026-11-22（直取失败） | — | **未取证**（降级见 §9） |
| S6 | [quantceo：交易所未处理请求超过许可数](https://www.quantceo.com/?p=861) | T3（社区/工程博客） | 未标注 | 2026-11-22 | 页面无版本号 | CTP `StatusMsg` 流控文案（反例/陷阱） |
| S7 | [金字塔 BBS：自动换月提示交易所每秒发送请求数超过许可](https://www.weistock.com/BBS/forum.php?mod=viewthread&tid=21208) | T3（论坛日志） | 2024-08-16 日志 | 2026-11-22 | 无版本 | CTP 流控真机日志佐证 |
| S8 | [RESEARCH_p053 §3.6 / §12.2](RESEARCH_p053_trading_gateway.md) | T1（仓内文件） | 2026-11-21 | 2026-11-22 | P-053 文档 | CTP 查询 1 笔/秒、`-2/-3` 语义、SQLite WAL（内含上游官方来源） |
| S9 | 仓内源码 `live/{gateway,ledger,ledger_store}.py`、`core/compliance.py`、`live/adapters/{ctp,mock}.py` | T1（仓内源码） | `a67a26b` | 2026-11-22 | commit `a67a26b` | 全部 G1-G8 的 file:line 证据 |
| S10 | [UPGRADE_MASTER_PLAN](UPGRADE_MASTER_PLAN.md) F7 / L271 / §7.1 D2 | T1（仓内文件） | 2026-11-17 裁决 | 2026-11-22 | 仓内文档 | P-054 能力面与已裁决口径 |
| S11 | [订单提交了，消息却没发出：用 Python SQLite 拆解事务型 Outbox](https://bbs.huaweicloud.com/blogs/524769) | T3（社区技术博客，同栈可复现） | 2026-11-10 | 2026-11-22 | Python 3.12.14 / SQLite 3.53.1 | 同事务 outbox + inbox、稳定 event_id、三段事务边界 |
| S12 | [ballast.py（PyPI）](https://pypi.org/project/ballast.py/) | T3（个人开源库） | 2026-07-08（0.1.1） | 2026-11-22 | 0.1.1 / Apache-2.0 | 单 SQLite 文件 + 零依赖 + outbox 的可行性参照 |
| S13 | [Implement the Transactional Outbox Pattern by Using Azure Cosmos DB](https://learn.microsoft.com/ga-ie/azure/architecture/databases/guide/transactional-out-box-cosmos) | T1（官方文档） | 未标注 | 2026-11-22（检索摘要，未直取全文） | — | 「业务对象 + 事件同事务；独立 worker 发布并标记」 |
| S14 | [Unit of Work（Martin Fowler, P of EAA）](https://martinfowler.com/eaaCatalog/unitOfWork.html) | T1（模式原始定义） | 2002（书籍） | 2026-11-22 | 目录页 | UoW 定义：集中跟踪变更、结束时统一写库 |
| S15 | [分享一个符合 CTP 流控的 ctp_gateway（vnpy 论坛）](https://www.vnpy.com/forum/topic/29510-fen-xiang-yi-ge-fu-he-ctpliu-kong-de-ctp-gateway) | T3（社区高赞实践帖） | 2021-11-25（2022-03-26 编辑） | 2026-11-22 | — | -1/-2/-3 语义、双队列调度、共享 FTD 预算 |
| S16 | [报单流控、查询流控和会话数控制（vnpy 论坛）](https://www.vnpy.com/forum/topic/7680-bao-dan-liu-kong-cha-xun-liu-kong-he-hui-hua-shu-kong-zhi) | T3（社区科普） | 未标注 | 2026-11-22 | — | 前置 `QryFreq` 配置、API 内置在途查询 1 笔 |
| S17 | [ctp-common（crates.io 文档转录）](https://crates.io/crates/ctp-common/code) | T3（第三方文档转录） | 未标注 | 2026-11-22 | — | 「每秒最多 1 次查询；在途最多 1 个」原文 |
| S18 | [策略获取持仓问题（vnpy 论坛）](https://www.vnpy.com/forum/topic/7766-ce-lue-huo-qu-chi-cang-wen-ti) | T3（社区问答） | 未标注 | 2026-11-22 | — | CTP 不推持仓、社区每 6 秒查询一次 |
| S19 | [PyrateLimiter 文档](https://pyratelimiter.readthedocs.io/en/stable/) | T1（库官方文档） | 未标注 | 2026-11-22 | v4（Python 3.10+） | 阻塞等待许可（可选 timeout）、多速率、token bucket/GCRA |
| S20 | [Tenacity 文档](https://tenacity.readthedocs.io/en/latest/) | T1（库官方文档） | 未标注 | 2026-11-22 | 最新文档 | `wait_random_exponential` + stop 条件 + 协程重试 |
| S21 | [报单流控、查询流控和会话数控制（CTP 接口文档 6.7.10）](https://ctpdoc.jedore.top/6.7.10/QTYWGZ/LK/) | T2（官方文档镜像） | 未标注（文档版本 6.7.10） | 2026-11-22 | 6.7.10 | FTD `FTDMaxCommFlux`、`QryFreq`、报单流控、交易所流控原文 |
| S22 | [ctp流控问题（豆丁文档分享）](https://www.docin.com/touch_new/preview_new.do?id=2108667936) | T3（文档分享） | 未标注 | 2026-11-22 | — | 「报单/撤单/查询每客户每连接 6 笔/秒，超出排队」 |
| S23 | [ReqOrderInsert FAQ（CTP 接口文档 6.7.10）](https://ctpdoc.jedore.top/6.7.10/JYJK/CTHOSTFTDCTRADERAPI/REQORDERINSERT/) | T2（官方文档镜像） | 未标注（文档版本 6.7.10） | 2026-11-22 | 6.7.10 | 前置流控由期货公司配置；`-2/-3` 归因 |
| S24 | [PyrateLimiter `abstracts/algorithm.py`](https://github.com/vutran1710/PyrateLimiter/blob/master/pyrate_limiter/abstracts/algorithm.py) | **T1**（库源码） | 读取当日 HEAD | 2026-11-22 | master（未锁 commit） | `SlidingWindowLog`/`FixedWindow`/`GCRA`/`TokenBucket` 状态模型；`Decision.retry_after_ms` 一次加锁同时出判定与等待 |
| S25 | [PyrateLimiter `abstracts/bucket.py`](https://github.com/vutran1710/PyrateLimiter/blob/master/pyrate_limiter/abstracts/bucket.py) | **T1**（库源码） | 读取当日 HEAD | 2026-11-22 | master（未锁 commit） | `put`/`waiting`/`Leaker` 后台泄漏线程/任务；bucket 内 `Lock` |
| S26 | [limits `limits/strategies.py`](https://github.com/alisaifee/limits/blob/master/limits/strategies.py) | **T1**（库源码） | 读取当日 HEAD | 2026-11-22 | master（未锁 commit） | 固定窗口 `hit = storage.incr(...) <= amount`；移动窗口按条目 `acquire_entry`；滑动计数加权 |
| S27 | [aiolimiter `leakybucket.py`](https://github.com/mjpieters/aiolimiter/blob/master/src/aiolimiter/leakybucket.py) | **T1**（库源码） | 读取当日 HEAD | 2026-11-22 | master（未锁 commit） | asyncio 漏桶：`_level` 按 `elapsed*rate` 泄漏；`acquire` 用 heapq 排队 + `call_at` 唤醒；**只建模容量，不建模并发** |
| S28 | [tenacity `tenacity/wait.py`](https://github.com/jd/tenacity/blob/master/tenacity/wait.py) | **T1**（库源码） | 读取当日 HEAD | 2026-11-22 | master（未锁 commit） | `wait_random_exponential` = 指数上界 + `uniform(min, high)`（Full Jitter）精确公式 |
| S29 | [vnpy_ctp `gateway/ctp_gateway.py`](https://github.com/vnpy/vnpy_ctp/blob/master/vnpy_ctp/gateway/ctp_gateway.py) | **T1**（上游网关源码） | 读取当日 HEAD | 2026-11-22 | master（未锁 commit） | `init_query` 仅注册 account/position；`process_timer_event` 每两 tick 发**一个**查询；登录→结算确认后才查询；未处理 `-2/-3` |
| S30 | [ReqOrderAction（CTP 接口文档 6.5.1 镜像）](https://ctpdoc.jedore.top/6.5.1/JYJK/CTHOSTFTDCTRADERSPI/REQORDERACTION/) | T2（官方文档镜像） | 未标注（文档版本 6.5.1） | 2026-11-22 | 6.5.1 | 返回码原文 `-2` = 未处理请求超过许可数、`-3` = 每秒发送请求数超过许可数；**报单/撤单同样适用**（更正 §13.4-2） |
| S31 | [中金所：关于程序化交易有关事项的通知](http://www.cffex.com.cn/cn/jystz/20250808/44660.html) | **T1**（交易所官方） | 2025-08-08 | 2026-11-22 | — | 「1 秒钟内 10 笔（含）以上**报撤单**」→ 报单与撤单**合并计量** |
| S32 | [证监会《期货市场程序化交易管理规定（试行）》](http://www.csrc.gov.cn/csrc/c101954/c7564346/7564346/files/%E9%99%84%E4%BB%B61%EF%BC%9A%E3%80%8A%E6%9C%9F%E8%B4%A7%E5%B8%82%E5%9C%BA%E7%A8%8B%E5%BA%8F%E5%8C%96%E4%BA%A4%E6%98%93%E7%AE%A1%E7%90%86%E8%A7%84%E5%AE%9A%EF%BC%88%E8%AF%95%E8%A1%8C%EF%BC%89%E3%80%8B.pdf) | **T1**（监管规定） | 2025 年第 12 号公告 | 2026-11-22 | — | 高频特征「短时间内**报单、撤单**的笔数、频率较高」；报撤单并列观察 |
| S33 | [SQLite: AUTOINCREMENT](https://www.sqlite.org/autoinc.html) | **T1**（官方文档） | 2024-02-22 更新 | 2026-11-22 | SQLite 文档页 | 默认 rowid 删最大行后**可能复用**、非严格递增；`AUTOINCREMENT` 保证**从未使用 + 单调递增**（允许空洞） |
| S34 | [SQLite: VACUUM](https://www.sqlite.org/lang_vacuum.html) | **T1**（官方文档） | 2025-07-12 更新 | 2026-11-22 | SQLite 文档页 | 「VACUUM **may change the ROWIDs** of entries in any tables that do not have an explicit INTEGER PRIMARY KEY」 |
| S35 | [Debezium: Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html) | **T1**（官方文档） | 未标注 | 2026-11-22 | stable | outbox 列 `id`（事件唯一 ID，供消费端去重）+ `aggregatetype`/`aggregateid`/`type`/`payload`；`aggregateid` 作消息 key，「important for maintaining correct order in Kafka partitions」 |
| S36 | [Stripe: Idempotent requests](https://docs.stripe.com/api/idempotent_requests) | T2（行业权威 API 文档） | 未标注 | 2026-11-22 | — | 幂等层「compares incoming parameters ... **errors if they're not the same**」；key 有保留期（v1 为 24h），过期重用会新建请求 |
| S37 | [CME iLink Messaging Controls](https://www.cmegroup.com/confluence/display/EPICSANDBOX/Messaging+Controls) | **T1**（交易所官方文档） | 未标注 | 2026-11-22 | — | 报单等 application messages 共用 **500 MPS（3s 窗）/ logout 750 MPS**；Mass Quote/Quote Cancel 另桶 350 MPS；超限 = Session Level Reject（**显式拒绝**） |
| S38 | [CME 清算所财务安全保障（断线删单 COD）](https://www.cmegroup.com/cn-s/education/files/financial-safeguards-sc.pdf) | **T1**（交易所官方，中文） | 未标注 | 2026-11-22 | — | COD：断线时交易所**替用户撤全部单**，保护持仓不受变动（撤单可靠性的服务端保障） |
| S39 | [台湾期货公会：自动化交易风险控管最佳实务](https://www.sfi.org.tw/files/4388/%E7%BE%8E%E5%9C%8B%E6%9C%9F%E8%B2%A8%E5%B8%82%E5%A0%B4%E8%87%AA%E5%8B%95%E5%8C%96%E4%BA%A4%E6%98%93%E9%A2%A8%E9%9A%AA%E6%8E%A7%E7%AE%A1%E8%88%87%E7%B3%BB%E7%B5%B1%E5%AE%89%E5%85%A8%E4%BF%9D%E9%9A%9C%E6%9C%80%E4%BD%B3%E5%AF%A6%E5%8B%99%E4%BD%9C%E6%B3%95%E4%B9%8B%E5%8F%83%E8%80%83.pdf) | T2（行业文件） | 未标注 | 2026-11-22 | — | COD 列为「交易前风险控管措施」标准项 |
| S40 | [IB TWS API: Third Party Platforms / Message Codes](https://interactivebrokers.github.io/tws-api/third_party.html) | **T1**（经纪商官方文档） | v9.72+ | 2026-11-22 | — | 「order rate limitation of **50 orders per second**」；>50 msg/s → 警告并可能断开（code 100，显式） |
| S41 | [vnpy 精英版事前交易风控 OrderFlowRule](https://www.vnpy.com/docs/cn/elite/strategy/elite_riskmanager.html) | T2（官方文档） | 未标注 | 2026-11-22 | — | 内部风控「委托流量限制」= 窗口内**委托笔数** + 日内总委托上限，**不含撤单**（内部风控口径 = 报单） |
| S42 | [FastAPI PyPI 0.165.0](https://pypi.org/project/fastapi/) / [0.139.2](https://pypi.org/project/fastapi/0.139.2/) / [release notes](https://fastapi.tiangolo.com/release-notes/) | **T1**（官方） | 0.165.0；0.139.2（>=3.10）；「Drop support for Python 3.10」（**无版本号**：release notes 直取 grep 未命中，仅搜索摘要） | 2026-11-22 | — | FastAPI 最新要求 >=3.11；0.139.2 仍支持 3.10 |
| S43 | [uvicorn PyPI 0.54.0](https://pypi.org/project/uvicorn/) / [settings](https://www.uvicorn.org/settings/) | **T1**（官方） | 0.54.0（>=3.10） | 2026-11-22 | — | uvloop 不支持 Windows；TLS/WS/并发参数 |
| S44 | [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) | **T1**（官方） | XADD/XACK v5.0、XAUTOCLAIM v6.2 | 2026-11-22 | — | 消费组/PEL/at-least-once |
| S45 | [Redis Pub/Sub](https://redis.io/docs/latest/develop/interact/pubsub/) | **T1**（官方） | at-most-once 原文 | 2026-11-22 | — | 行情可丢扇出 |
| S46 | [prometheus-client 0.26.0](https://pypi.org/project/prometheus-client/) | **T1**（官方客户端） | 0.26.0（2026-07-25，>=3.9） | 2026-11-22 | — | 指标 |
| S47 | [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) | **T1**（官方） | — | 2026-11-22 | — | apiKey/bearer 方案 |
| S48 | [Starlette WebSockets](https://www.starlette.io/websockets/) | **T1**（官方） | — | 2026-11-22 | — | subprotocol 鉴权、close/disconnect、denial response |
| S49 | [redis-py PyPI 8.1.0](https://pypi.org/project/redis/) | **T1**（官方客户端） | 8.1.0（>=3.10） | 2026-11-22 | — | async 连接、客户端能力 |
| S50 | [Python: Status of Python versions](https://devguide.python.org/versions/) | **T1**（官方） | 页面更新 2026-05-27 | 2026-11-22 | — | **Python 3.10 于 2026-10-01 EOL**；3.11/3.12 为 security 支持 |
| S51 | [Redis: Install on Windows](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/install-redis-on-windows/) | **T1**（官方） | — | 2026-11-22 | — | 「Redis is **not officially supported on Windows**」；需 WSL2 |
| S52 | [WebSocket.org: WebSocket with FastAPI](https://websocket.org/guides/frameworks/fastapi/) | T2（行业指南） | — | 2026-11-22 | — | uvicorn worker 是独立进程、内存隔离；跨 worker 广播需 Redis pub/sub，约 **+1ms** |
| S53 | [SQLite: Write-Ahead Logging](https://www.sqlite.org/wal.html) | **T1**（官方） | — | 2026-11-22 | — | WAL：「readers do not block writers and a writer does not block readers」；另有 Read-Only Databases 节 |
| S54 | [Helland: Life Beyond Distributed Transactions](https://www.ics.uci.edu/~cs223/papers/cidr07p15.pdf) | **T1**（学术，CIDR 2007） | 2007 | 2026-11-22 | — | 实体「lives on a single machine at a time」；「Atomic Transactions Cannot Span Entities」 |
| S55 | [Fowler: CQRS](https://martinfowler.com/bliki/CQRS.html) | **T1**（模式原始定义） | 2011-07-14 | 2026-11-22 | — | 读写模型可分离；可共享同一数据库；**警告 CQRS 增加复杂风险，只用于局部** |
| S56 | [GitHub Actions: About service containers](https://docs.github.com/en/actions/using-containerized-services/about-service-containers) | **T1**（官方） | — | 2026-11-22 | — | `services:` 起 Redis 容器；**必须 Linux/Ubuntu runner**；示例映射 6379 |
| S57 | [OWASP REST Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html) | **T1**（行业标准） | — | 2026-11-22 | — | API Key：每个受保护请求都要、429、可撤销；**不得仅依赖 API Key 保护高价值资源** |
| S58 | [RFC 8725: JWT Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725) | **T1**（IETF BCP） | 2020-02 | 2026-11-22 | — | 算法验证、issuer/audience 校验、不信任收到的 claims |
| S59 | [OWASP TLS Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html) | **T1**（行业标准） | — | 2026-11-22 | — | 「Use TLS For All Pages」；TLS 1.3 默认、1.2 兼容、**1.0/1.1 必须禁用** |
| S60 | [Prometheus: Instrumentation](https://prometheus.io/docs/practices/instrumentation/) | **T1**（官方） | — | 2026-11-22 | — | online-serving 关键指标 = 请求数/错误/延迟 + in-progress；统一计数口径 |
| S61 | [Google SRE Book: Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) | **T1**（学术/工程经典） | 2016 | 2026-11-22（检索摘要） | — | 四黄金信号：latency / traffic / errors / saturation |

> **多源校验**：核心结论均 ≥2 独立来源且 ≥1 T1——outbox 原子性（S1+S2+S9）、at-least-once⇒幂等（S1+S9 `fill_key` 去重）、CTP 流控（S21/S30 官方镜像 + S8 + S15/S22/S31/S32 + 反例 S6/S7）、退避抖动（S3+S4）、order-flow 默认值行业实践（§18：B1-B7 = CME/IB/vnpy/Binance 四系统，S37-S41）。
> **补充调研来源（S62-S72）**：WAL 只读（S62-S67）与 TLS 最低版本（S68-S72）两项风险锚点见 [RESEARCH_p054_risk_anchors](RESEARCH_p054_risk_anchors.md) §5；**该编号段唯一定义在 risk_anchors，本表不复用，后续新来源从 S73 起**。

---

## 9. 降级链记录

| 通道 | 失败形态 | 降级走了哪一跳 | 已读到的事实 / 未取证 |
|------|----------|----------------|------------------------|
| Azure Transactional Outbox 页面 | WebFetch 返回 cookie 横幅、正文为空 | 目标页 → 无备用镜像（未使用第三方代理）→ 仓内 S1/S2/S9 | 结论不依赖 Azure 页面；标 **S5 未取证** |
| CTP 官方错误码页（ctpdoc.jedore.top） | WebFetch 返回 Material for MkDocs 空壳（内容由 JS 渲染） | 官方页 → WebSearch 精确短语 + 站点限定 → 命中 T3 社区/论坛 | `-2/-3` 语义沿用 S8 既有取证（其上游为 CTP 开发指南/官方文档）；本轮**未新增一手错误码页** |
| 首次中文 CTP 关键词检索 | 返回大量无关 PDF/招标页 | 精确短语 `"每秒发送请求数超过许可数"` + 站点限定 | 命中 S6/S7（T3），仅作反例与日志佐证 |

---

## 10. 未决问题（移交后续 Step）

| ID | 问题 | 归属 |
|----|------|------|
| Q1 | P-054 外发事件集合（哪些业务事件进 outbox） | P-054 Step 3 设计 |
| Q2 | `event_id` 业务键派生规则 | **格式与冲突语义已由 §16.5 裁决**（随 Q11）；payload 细节归 Step 3 |
| Q3 | 原子入口改造落点（P-054 批内 vs P-053b 补丁批） | **随 Q11 裁决默认 P-054 批内**（§16.6 前提）；单开 P-053b 须显式推翻 |
| Q4 | relay 载体（进程内轮询 vs Redis Streams） | **已裁决（随 Q14）**：交易进程内 SQLite outbox 轮询 relay → Redis 发布（Streams 可靠投递 / Pub/Sub 广播 worker，§19.9/§21.1） |
| Q5 | 退避参数（初始/倍率/封顶/次数） | P-054 Step 3 设计 |
| Q6 | 启动恢复序部分失败的降级语义 | P-054 Step 3 设计 |
| Q7 | 查询调度器是否同时覆盖后台巡检 | P-054 Step 3 设计 |
| Q8 | CTP 共享 FTD 预算如何建模（§13：能力字段/默认值/预留/耗尽策略） | **已裁决：P-054 批内**（§15） |
| Q9 | 柜台报单流控为报单+撤单合并额度，是否合并 submit/cancel 台账（§13.6，新增 P2） | **已裁决：P-054 批内**（§15） |
| Q10 | 限流原语是否升级为 `try_acquire(ts) -> Decision{allowed, retry_after_ms}`（并决定固定窗口→GCRA/滑动日志）（§14.3/§14.9） | **已裁决：本轮不改造**（§15） |
| Q11 | outbox relay 排序/索引与 `event_id` 版本化规则（§14.8） | **已裁决：P-054 批内**（§16，2026-11-22 用户确认） |
| Q12 | kill-switch/`cancel_all` 的预算语义：预留槽位 vs bypass+audit（G15 衍生；RTS 6 kill 精神） | **已裁决：撤单优先通道 + 显式 deferred**（§22.7） |
| Q13 | Python 下限：全局升 3.11 / 锁旧 FastAPI / 服务层独立 3.11+ | **已裁决：全局升 3.11**（§19.3，2026-11-22 用户确认） |
| Q14 | Phase 0 单 worker vs 直接 F7 全量多 worker | **已裁决：直接 F7 全量多 worker**（§20.6/§21） |
| Q15 | 鉴权：API Key / JWT / 两者 | **已裁决：API Key 优先，JWT 预留**（§22.4） |
| Q16 | TLS 范围：loopback 是否强制 | **已裁决：TLS 全启用（含 loopback），1.3/1.2**（§22.5） |
| Q17 | 可观测性：prometheus-client vs 手写 `/metrics` | **已裁决：prometheus-client + 四黄金信号**（§22.6） |
| Q18 | 交易/账本进程与 API worker 的拆分方式（独立进程 vs leader worker） | **已裁决：独立交易/账本进程 + N 无状态 worker**（§22.1） |
| Q19 | REST 管理面读路径（只读 SQLite / 内部 API / Redis 快照） | **已裁决：同机只读 SQLite；跨机内部 API**（§22.3） |
| Q20 | Windows Redis 运行方式（Docker/WSL2/Memurai）与 CI 方案（Redis service / FakeBus） | **已裁决：Docker/WSL2 + CI Redis service + FakeBus**（§22.2） |

---

## 11. 状态链

**Step 1 前置专项调研完成（2026-11-22）**：产出本文档；两项硬前置（U-P053-17/18）均给出事实链、崩溃矩阵、候选方案 A/B(/C)、裁决点与对 P-054 的影响；四项低风险 U 项给出处置建议；未改代码、未提交 →
**补充调研（§12）完成（2026-11-22）**：针对推荐方案 A 补社区案例与决策锚点，新增 §12 与 S11-S20；**新增裁决点 Q8（CTP 共享 FTD 预算）** →
**Q8 专项（§13）完成（2026-11-22）**：分层澄清 FTD/报单/查询/交易所四层流控，建立当前实现暴露矩阵（内部 1/s 安全、≥3/s 越界），新增 G10/G11 与 Q9，给出共享预算方案 A/C；补 S21/S22/S23 → 待 Step 2 异构复审（复审基座 ≠ 作者，RULE-5）→ 待全量 Step 1（F7：FastAPI/WS/鉴权/TLS/可观测性/Redis 取舍）合并为本批完整 RESEARCH →
**算法源码级取证（§14）完成（2026-11-22）**：取 PyrateLimiter / limits / aiolimiter / tenacity / vnpy_ctp **五个上游库的六份源码文件**（S24-S29），确认算法归属（固定秒窗）、计量口径差异（G13）、退避精确公式、查询「速率+在途」双原语、vnpy 串行轮询同构解；新增 G12/G13/G14、S24-S29、Q10/Q11 → 仍待 Step 2 异构复审 →
**Q8/Q9/Q10 裁决（§15，2026-11-22）**：Q8/Q9 **纳入 P-054 批内**（与 U-P053-18 同一「通道流控前置包」）；Q10 **本轮不改造**，登记为并发化触发项 →
**依据强度审计（§15.7）完成**：Q8 强（多源+源码+代码实证）；Q9 中强（核心事实同源，补 S31/S32 两条 T1 监管锚点，柜台细则留待真机确认）；Q10 中（范围/成本裁决，非外部调研，原「1300 测试」已更正为 4 调用点/2 模块/6 文件 38 处）；另经 S30 更正 `-2/-3` 为 API 通用流控码 →
**Q11 专项（§16）完成（2026-11-22）**：以 SQLite AUTOINCREMENT/VACUUM（S33/S34 T1）、Debezium Outbox（S35 T1）、Stripe 幂等（S36）为锚，确定 `seq INTEGER PRIMARY KEY AUTOINCREMENT` + `(sent, seq)` 索引 + 版本化 `event_id` + 冲突报错 + inbox 去重；**已裁决纳入 P-054 批内**（2026-11-22 用户确认，与 U-P053-17 同一次 store 改造/迁移完成）→
**Step 2 异构复审完成（[REVIEW_p054_step2_research.md](REVIEW_p054_step2_research.md)，2026-11-22，基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash）**：E3 锚点 **21/21 属实**、外部锚点 7 组抽检无幻觉、口径保真 ✅；**0 P1 / 1 P2 / 6 P3** —— P2 = **F-1**（§15.3-1 order-flow 默认 1/s 与 §15.5-2「默认路径不变」互斥，需用户二选一：(a) 默认 2×internal 保留现状 / (b) 默认 internal 承认行为变更）；P3 = F-2~F-7（计数失同步、G14/G6 处置过时、「五处/六处」口径、§8 多源注未更新、Q2/Q3 登记滞后）。**有条件通过：F-1 修复前禁止进入 Step 3**（门禁 b）→
**F-1 决策依据专项（§17）+ 外部案例专项（§18）完成（2026-11-22）**：根源 = D2「笔」未定义（R1 已关闭实现 vs R2 §15 新引入）；8 锚点 A1-A8 + 行业案例 B1-B7（CME 500 MPS 合并且显式 reject / COD 断线删单 / IB 50 orders/s / vnpy 精英版内部风控**只数委托** / Binance 409 显式 + 批量撤单）→ **F-1 证据锚定裁决 = (a-修订)**（order-flow 默认 2×internal + G15 显式化 + Q12 三选项）；F-2~F-7 已同步修订 → **Step 2 门禁 (b) 解除** →
**全量 Step 1（§19）完成（2026-11-22）**：FastAPI/uvicorn/redis/prometheus-client 版本与 Python 兼容矩阵；发现 **FastAPI 上游要求 >=3.11 与本仓 3.10 冲突**（Q13）、**uvloop 不支持 Windows**、**WS 出站背压须自建**；鉴权 API Key + 短时 ticket/子协议；TLS 内网强制；指标官方 client；Redis 取舍先建议 Phase 0 → Phase 1，**随后 Q14 裁决改为直接 Full**（见下），新增 Q13-Q17、S42-S49 → 待 Step 2 复审全量 Step 1 →
**Q13 裁决（2026-11-22 用户确认）**：**全局升到 Python >=3.11**（3.10 已于 2026-10-01 EOL，S50；FastAPI 最新要求 >=3.11，S42）；实施影响见 §19.3（pyproject/CI/black/mypy/依赖/基线重跑），需单列小任务 →
**Q14 专项（§20）完成**：外部锚点 S51（Redis 不支持 Windows，需 WSL2）、S52（uvicorn worker 内存隔离，跨 worker 广播必须 Redis pub/sub，+≈1ms）、F7 L228（A股 L1 3s，总线延迟非瓶颈）+ 仓内硬约束（SQLite 单写者 `.lock`、EventLog `RLock` 仅进程内）→ **证据指向 Phase 0 单 worker**；**用户裁决（2026-11-22）：直接 F7 全量多 worker**（§20.6），推翻上述倾向 →
**§21 架构约束（Q14 裁决后）**：新增 **G16（P1）**——F7 多 worker 与 SQLite `.lock` 单写者冲突，直接 `--workers N` 会让第 2 个 worker 启动失败，必须拆「单实例交易/账本进程 + N 个无状态 API/WS worker」（或 store 只读模式）；新增 **G17**——Windows 无官方 Redis（需 WSL2/Docker）+ EventLog 不得多进程共写；新增 **Q18-Q20**（进程拆分方式 / REST 读路径 / Redis 运行与 CI）→
**§22 剩余缺口裁决（2026-11-22）**：以学术/官方锚点逐项裁决——**Q18/G16** = 单实例交易/账本进程 + N 无状态 worker（Helland 单实体所有者 S54 + SQLite 单写者/WAL S53/S2，不用 leader election）；**Q20/G17** = Docker Desktop(WSL2) + `redis:7`、CI Ubuntu `services: redis`、单测 FakeBus（S51/S56）；**Q19** = 同机只读 SQLite（`mode=ro`/`query_only`）/跨机内部 API，不建 Redis 读模型（S53/S55）；**Q15** = API Key + `hmac.compare_digest`、JWT 预留（RFC 8725）、WS 短时 ticket（S57/S58）；**Q16** = TLS 全启用（含 loopback）、TLS1.3/1.2、1.0/1.1 禁用（S59）；**Q17** = prometheus-client + 四黄金信号 + 领域指标、JSON 日志（S60/S61）；**Q12** = 撤单优先通道 + 保留槽位 + 显式 deferred，不绕过 CTP 物理限额（RTS 6/CME COD/Binance + S21）；**Q5-Q7** 依据已足、数值留 Step 3。新增 S53-S61 →
**Step 2 二轮复审完成（[REVIEW_p054_step2_research.md §8](REVIEW_p054_step2_research.md)，2026-11-22，GLM-5.3-Flash ≠ DeepSeek-V4.1-Flash）**：E3 锚点 8/8 属实、S42-S61 抽检（S42-S51/S56-S60 直取 ✅、S42 引句与 S61 降级已标注）；口径保真 ✅；**0 P1 / 2 P2 / 5 P3，有条件通过**——P2 = **F-R2-1**（§21.1 拓扑图订单路径用消费组直连 worker，与 §19.9「消费组=负载均衡非广播」自相矛盾，跨 worker 广播一致性验收不可达，须改图二选一）+ **F-R2-2**（§7.2「首发单 worker」与 §10 Q4 行未随 Q14=Full 更新）；P3 = F-R2-3~F-R2-7（`<0.140` 上界未取证、§19.9/§21.1 叙述残留、PROGRESS 计数、§19.1 引注、WAL 只读 -shm 条件未取证 + pydantic 实际被 config_v2.py 使用须纳入 Q13 回归范围）。**F-R2-1/F-R2-2 修复前不得进入 Step 3**。
**Step 2 二轮复审修复完成（2026-11-22）**：F-R2-1 → §21.1 拓扑图改为「Streams 单一消费者处理后经 Pub/Sub 扇出全 worker」并加扇出路径注解；F-R2-2 → §7.2 与 §10 Q4 更新为 Q14=Full 口径（含 §12 三处交叉引用同步）；F-R2-3~F-R2-7 → `<0.140` 上界与「Drop 3.10」版本号标注未取证、§19.9 结论先行改 Full、§21.1 图注删「Redis 快照」、§19.1 引注改「§3 G9 与 §7.2」、§22.3 补 WAL `-shm`/`-wal` 前提、§19.3 影响清单补 pydantic 实际使用与回归范围；PROGRESS §3.61 计数同步 → **Step 2 关闭**，进入 Step 3 DESIGN。

---

## 12. 补充调研：推荐方案社区案例与决策锚点（2026-11-22）

> 目的：为 §4.3 方案 A（原子组合写）与 §5.3 方案 A（查询调度器）补足社区实证，把「设计上合理」升级为「有可复现案例与成熟实现语义支撑」。
> 检索口径：优先同栈（Python + SQLite）与同域（CTP/vnpy）；每条给出「可借用」与「不可照搬」。

### 12.1 U-P053-17 方案 A 的社区案例

| 案例 | 栈 / 版本 | 与本方案的对应 | 可借用 | 不可照搬 / 教训 |
|------|-----------|----------------|--------|------------------|
| **S11 华为云社区：用 Python SQLite 拆解事务型 Outbox** | Python 3.12.14 / SQLite 3.53.1，标准库，退出码 0（2026-11-10） | 与本仓**同栈**：`BEGIN IMMEDIATE` → `orders`+`outbox` 同事务 → relay `SELECT sent=0` → 消费 → `UPDATE sent=1`；消费端 `inbox` 与业务效果同事务 | 三段事务边界表（§12.1 下方 A2）；**「真实系统需给不同事件分配稳定唯一标识，重试复用编号，不能每次重新生成」**（原文） | 用两个独立 SQLite 文件 + 直接函数调用模拟投递，**未覆盖外部副作用不可回滚**；作者自述「不代表生产已实现分布式 exactly-once」 |
| **S12 ballast.py（PyPI）** | 0.1.1 / Apache-2.0 / 2026-07-08 / **0 star** | 「单 SQLite 文件 + 零依赖」提供 transactional outbox、exactly-once jobs、forward-only migrations | 证明**单机单库零依赖**跑通 outbox 在工程上可行（仅可行性参照，不构成 P-054 选型依据；Q14 已裁决 Full，见 §19.9/§20.6） | 个人项目、成熟度极低；**只作可行性参照，不引入依赖**（D14 零新依赖 + 基线锁定） |
| **S13 Azure Cosmos DB Outbox（官方）** | T1 官方文档 | 「在同一数据库事务中保存业务对象与其事件；独立服务/worker 查询未处理条目、发布、标记」 | 与「组合写方法 + relay + `mark_sent`」一一对应，属**跨栈同构**佐证 | Cosmos 用 TransactionalBatch/change feed；SQLite 无 change feed，需轮询（本仓已定 `pending_outbox`） |
| **S14 Unit of Work（Fowler）** | T1 模式原始定义（P of EAA, 2002） | UoW = 集中跟踪一次业务事务内的变更，结束时统一写库 | 说明「组合写方法」就是 UoW 的**最小子集**：无需引入 ORM/完整 UoW 框架 | 完整 UoW 面向对象变更跟踪；本仓是显式函数式写入，**不要过度工程化** |

**决策锚点（U-P053-17）**

- **A1 `event_id` 必须稳定、可复用**：S11 明文 + S13/S1 的「按事件 ID 去重」共同指向 → **Q2 方向确定：业务键派生**（`order:{coid}:accepted`、`fill:{fill_key}`），`uuid4` 仅可作兜底。
- **A2 同事务只覆盖本地库，外部投递天然 at-least-once**：S11 三段边界 + S1 → relay 成功后 `mark_sent`，两步之间崩溃必然重复投递；**消费端必须有 inbox/幂等**，对外不得宣称 exactly-once。
- **A3 单机单库零依赖路线成立（仅限单进程）**：S12 + 仓内 SQLite WAL（S9/S2）→ 单进程内「组合写 + 轮询 relay」可行；P-054 已裁决 Full（Q14），relay 需写入 Redis 作为跨进程载体（§19.9/§21.1），S12 只支撑单库路线、不支撑最终拓扑。
- **A4 组合写不需要完整 UoW 框架**：S14 + 仓内 Protocol → 方案 A 的 3 个显式方法（`append_entries` / `upsert_order_with_events` / `append_entries_with_events`）足够，避免引入 ORM。

### 12.2 U-P053-18 方案 A 的社区案例

| 案例 | 来源性质 | 关键事实 | 对本方案的作用 |
|------|----------|----------|----------------|
| **S15 vnpy《分享一个符合 CTP 流控的 ctp_gateway》（hxxjava，2021-11-25 / 2022-03-26 编辑）** | T3 社区高赞实践帖 | ① `-1` 网络失败 / `-2` 未处理请求超许可 / `-3` 每秒请求超许可；② **`-2/-3` 可用「等待、重试、队列」**；③ 「网关应有**两个统一队列**（报单 + 查询）来调度，而不是把流控留给上层 APP」；④ 默认 FTD **6 次/秒**，查询 **1 次/秒**，**当前秒已用 1 次查询则报单只剩 5 次**；⑤ 实现：查询队列每 **1s**、报单队列每 **1/6s** 检查一次 | 直接支撑 §5.5「调度器是通道层唯一入口」；支撑「等待/排队」而非立即失败；**引出新增裁决点 Q8（共享 FTD 预算）** |
| **S16 vnpy《报单流控、查询流控和会话数控制》** | T3 社区科普 | 查询流控配置在交易前置 `QryFreq`；**API 内置在途查询流控 1 笔** | 调度器必须**串行 + 单在途**，不可并发查询 |
| **S17 ctp-common（crates.io 文档转录）** | T3 第三方转录 | 原文：「每秒钟最多只能进行一次查询操作；在途的查询操作最多只能有一个」 | 与 S16 互证，构成「1/s + 单在途」的双源锚点（另一源为 S8 仓内取证） |
| **S18 vnpy《策略获取持仓问题》** | T3 社区问答 | CTP 不推送持仓；社区按**每 6 秒**查询一次刷新 | 后台巡检间隔锚点 → 支撑 Q7「巡检共用调度器」，避免与启动查询争抢同一秒额度 |
| **S19 PyrateLimiter（官方文档）** | T1 库文档 | 支持 **blocking acquire（可选 timeout）**、多速率（如 5/s 且 1000/h）、token bucket/GCRA、SQLite 后端、sync/async 同 API | 证明「阻塞等待许可 / 多速率」是成熟库的既有语义 → 方案 A 的「最小间隔等待 + 日限」建模正确；D14 下**只借鉴语义不引依赖** |
| **S20 Tenacity（官方文档）** | T1 库文档 | `wait_random_exponential`、stop 条件、协程重试 | 退避 + 抖动 + 限次的成熟语义 → 为 Q5 参数提供实现参照（不引依赖，自实现等价逻辑） |

**决策锚点（U-P053-18）**

- **B1 调度器必须下沉到通道层**：S15 明确指出「不能把流控留给上层 APP」→ 与 §5.5 一致；P-054 服务层不得直接调用 CTP 查询，必须经调度器。
- **B2 编排语义是「排队延后」而非「立即失败」**：S15（队列）+ S19（blocking acquire）→ 方案 A 的「等待到下一窗」正确；若查询量上升，可平滑升级为**有界查询队列**（超出则拒绝并暴露指标），不影响现有接口。
- **B3（新增，P2）查询与报单共享 FTD 预算**：S15 给出「6/s 总额，查询占 1 则报单剩 5」。当前 P-053 D11 是 `submit` / `cancel` / `query` **三独立桶**（[gateway.py#L124-L133](../live/gateway.py#L124-L133)），**可能高估可报单量**。→ **新增裁决点 Q8**：是否在 P-054 调度器层叠加「共享 FTD 6/s」外层预算（不改 P-053 已关闭实现），避免真机报单被 `-3` 拒绝。
- **B4 查询必须串行、单在途**：S16 + S17 → 调度器内部只允许一个查询在途；并发查询会直接触发 `-2`。
- **B5 退避需限次 + 封顶 + 抖动**：S20 + S3/S4 → Q5 建议：初始 1s、倍率 2、封顶 5s、最多 5 次、full jitter。
- **B6 后台巡检共用同一查询桶**：S18 → 持仓刷新（约 6s/次）也消耗查询额度；Q7 建议「是」，否则启动恢复序与巡检会在同一秒互斥失败。

### 12.3 补充调研对前文结论的影响

1. **G5/G6 获独立复现，置信度提升，方案不变**：S11 同栈复现「双写丢事件」，S15 复现「`-2/-3` 未处理即静默失败」。
2. **新增裁决点 Q8（P2）**：P-053 三桶独立 vs CTP 共享 FTD 预算。建议 P-054 设计评估「共享外层 + 各桶内层」双层模型；**不在本轮改 P-053 实现**。
3. **方案 A 的边界更清晰**：outbox 只保证「本地库内事件与业务同生同灭」，**不保证外部 exactly-once**；relay 必须配套消费端幂等——作为 P-054 验收硬项（§7.3）。
4. **未发现与推荐方案冲突的社区反例**；vnpy 的教训恰好是「不做队列/不管流控 → 静默失败」，反向支持方案 A。
5. **D14 兼容性确认**：S12/S19/S20 均为「可借鉴的成熟实现」，但**不引入新依赖**，全部自实现等价最小逻辑（与 P-053 零新依赖一致）。

### 12.4 决策点更新汇总

| 裁决点 | 状态 | 结论方向 |
|--------|------|----------|
| Q2 `event_id` 生成 | **方向明确** | 业务键派生（A1） |
| Q5 退避参数 | **有参照** | 1s 起、×2、封顶 5s、≤5 次、full jitter（B5） |
| Q7 巡检共用调度器 | **建议确定** | 是（B6） |
| **Q8 共享 FTD 预算** | **已专项分析（§13）** | 共享 6/s 外层 + 各桶内层；默认 6 可配 + 预留 1（方案 A） |
| Q1/Q3/Q6 | 保持 | 仍由 P-054 Step 3 设计裁决 |
| **Q4 relay 载体** | **已裁决（随 Q14）** | 交易进程内 SQLite outbox 轮询 relay → Redis 发布（§19.9/§21.1） |

---

## 13. Q8 专项：CTP 共享 FTD 预算与当前实现暴露（2026-11-22）

### 13.1 CTP 的四层流控（先分清层级）

据 CTP 接口文档 6.7.10（S21，官方文档镜像）与 vnpy 对官方 CHM 的转录（S16），CTP 至少有四层独立流控：

| 层 | 覆盖范围 | 配置位置 | 超限表现 |
|----|----------|----------|----------|
| **FTD 报文流控** | 当前 **Session 的所有 API 指令**：登录、查询、报单、撤单、报价等 | 前置 `FTDMaxCommFlux` | **超出部分被前置缓存到下一秒发出；不返回任何错误** |
| **报单流控** | `ReqOrderInsert` + `ReqOrderAction`（报单与撤单） | 柜台【程序化交易频繁报撤单管理】 | `OnRspOrderAction`：「CTP:下单频率限制」 |
| **查询流控** | 当前 Session 的查询请求 | 前置 `QryFreq` + API 内置在途 1 笔 | 超前置：`OnRspError`「CTP：查询未就绪，请稍后重试」；超在途：返回值 `-2`（`-2` 为 API 级「未处理请求超过许可数」，查询在途 1 是特例，S30） |
| **交易所 API 流控** | 经交易所 API 的报单等 | 交易所端 | `OnRtnOrder`：「CTP：交易所每秒发送请求数超过许可数」/「未处理请求超过许可数」 |

**Q8 = 第 1 层（FTD）未建模；G11/Q9 = 第 2 层（报单+撤单合并）未建模。** `-2/-3` 不是 FTD 的错误（FTD 不报错），而是 **API 在途/速率层**的表现（`-2` = 未处理请求超过许可数、`-3` = 每秒发送请求数超过许可数，S30）——这一点决定了 Q8 的定级。

### 13.2 当前实现与暴露矩阵

当前是三份**独立台账 + 三份独立配置**（[gateway.py#L102-L107](../live/gateway.py#L102-L107)、[L120-L133](../live/gateway.py#L120-L133)）：

- `submit`：`max(1, round(min(internal, cap=10.0, regulator=300)))`
- `cancel`：`max(1, min(internal, round(min(cap_cancel=10.0, cap_submit=10.0))))`
- `query`：`int(max(1, round(min(cap_query=1.0, cap_submit=10.0)))) = 1`

按上述公式展开（`internal = self._rate_config.max_per_second`，默认 1）：

| `internal` | submit | cancel | query | 同秒最坏 FTD（三类型打满） | 对 6/s 的差 | 真机表现 |
|-----------|--------|--------|-------|---------------------------|-------------|----------|
| **1（默认）** | 1 | 1 | 1 | **3** | −3 | 安全，但只用了 FTD 一半 |
| 2 | 2 | 2 | 1 | **5** | −1 | 接近上限 |
| **3** | 3 | 3 | 1 | **7** | **+1** | 前置缓存 1 笔 → 约 1s 延迟 |
| 4 | 4 | 4 | 1 | **9** | **+3** | 队列开始累积 |
| 6 | 6 | 6 | 1 | **13** | **+7** | 多秒延迟，盘中可能明显滑点 |
| 10（能力声明） | 10 | 10 | 1 | **21** | **+15** | 严重排队；且与能力声明矛盾 |

补充事实：

- 启动期还有**登录 / 结算确认**等 FTD 指令，实际可用额度再少 1–2 笔。
- CTP 适配器声明 `max_submit_per_sec=10.0`、`max_cancel_per_sec=10.0`（[ctp.py#L58-L60](../live/adapters/ctp.py#L58-L60)），而 FTD 常见配置为 6/s（S15/S22）——**能力声明本身与共享额度不一致**（G10）。
- 最坏值是「同秒三类型同时打满」的构造上界；真实触发形态是**撤单风暴**、**启动恢复 + 登录/确认同秒**、或**内部速率被调高**。默认 1/s 下不会触发，所以该问题在 P-053 测试中不可见。

### 13.3 外部锚点

| 锚点 | 层级/日期 | 关键事实 | 支撑的判断 |
|------|-----------|----------|------------|
| **S21** CTP 接口文档 6.7.10《报单流控、查询流控和会话数控制》 | T2 官方文档镜像 / 6.7.10 | FTD `FTDMaxCommFlux` 覆盖「登录、查询、报单、撤单和报价等**所有请求**」；超出**缓存到前置，不返回错误**；报单流控覆盖 `ReqOrderInsert`+`ReqOrderAction`；查询 `QryFreq` + 在途 1 + `-2`；交易所流控 → `-3` | **Q8 的主锚点**：共享范围、缓冲语义、四层分层 |
| **S16** vnpy《报单流控、查询流控和会话数控制》 | T3（官方 CHM 转录）/ 2021-09-22 | 与 S21 文本一致；FTD 示例配置为 6；「登录、查询、报单、撤单和报价都受 FTD 限制」 | 与 S21 互证（同源不同通道），降低单点转述风险 |
| **S15** vnpy《分享一个符合 CTP 流控的 ctp_gateway》 | T3 / 2021-11-25 | 「默认 FTD 如果是每秒 6 次……当前秒已有 1 次查询，报单只剩 5 次」；建议网关建报单/查询两个统一队列 | 量化「查询挤占报单」；支撑通道层统一调度 |
| **S22** 豆丁《ctp 流控问题》 | T3 / 未标注 | 「指令（报单/撤单/查询）：每客户每连接 6 笔/秒，超过部分将排队」 | 独立第三方给出「6 笔/秒 + 排队」；与 S15/S21 一致 |
| **S23** CTP 接口文档 6.7.10 `ReqOrderInsert` FAQ | T2 官方文档镜像 / 6.7.10 | 报单频率太快触发**前置流控**；「投资者可询问期货公司具体的流控设置」 | 6/s 非保证值，**必须可配置** |
| **S17** ctp-common 文档转录 | T3 | 查询每秒最多 1 次、在途最多 1 个 | 查询层的独立约束，不能与 FTD 混同 |
| **S30** [ReqOrderAction（CTP 接口文档 6.5.1 镜像）](https://ctpdoc.jedore.top/6.5.1/JYJK/CTHOSTFTDCTRADERSPI/REQORDERACTION/) | T2（官方文档镜像）/ 6.5.1 | 返回码原文：`-2` = 未处理请求超过许可数；`-3` = 每秒发送请求数超过许可数 | **更正**：`-2/-3` 是 API 通用流控码（报单/撤单同样适用），不是查询专属（§13.4-2） |
| **S31** [中金所：关于程序化交易有关事项的通知](http://www.cffex.com.cn/cn/jystz/20250808/44660.html) | **T1**（交易所官方）/ 2025-08-08 | 报告义务触发条件：「1 个交易日内出现 10 次（含）以上 **1 秒钟内 10 笔（含）以上报撤单**」 | **报撤单合并计量**的独立监管锚点（支撑 Q9 的「合并额度」语义） |
| **S32** [证监会《期货市场程序化交易管理规定（试行）》](http://www.csrc.gov.cn/csrc/c101954/c7564346/7564346/files/%E9%99%84%E4%BB%B61%EF%BC%9A%E3%80%8A%E6%9C%9F%E8%B4%A7%E5%B8%82%E5%9C%BA%E7%A8%8B%E5%BA%8F%E5%8C%96%E4%BA%A4%E6%98%93%E7%AE%A1%E7%90%86%E8%A7%84%E5%AE%9A%EF%BC%88%E8%AF%95%E8%A1%8C%EF%BC%89%E3%80%8B.pdf) | **T1**（监管规定）/ 2025 年第 12 号公告 | 高频交易特征：「短时间内**报单、撤单**的笔数、频率较高」 | 监管口径将报单与撤单**并列合并**观察（Q9 的间接独立锚点） |

> **来源缺口**：CTP 官方 API 说明 `.chm` 为 T1 一手，但不可直接抓取；S21 为官方文档镜像（6.7.10）、S16 为官方 CHM 转录，二者文本一致，另有两篇独立社区实践（S15/S22）互证。结论置信度高，但按 F3 记录该降级。

### 13.4 语义澄清（决定 Q8 的定级与处置）

1. **FTD 超限不是拒单，而是延迟**：超出部分由前置缓存到下一秒，**没有错误返回**（S21/S16）。因此 Q8 的主要危害是**盘中延迟与队列累积**，不是 `-3` 拒单 → 定级 **P2**，不是 P1。
2. **`-2` / `-3` 不属于 FTD 层**：`-2` 是 **API 级「未处理请求超过许可数」**（S30 对 `ReqOrderAction` 原文如此；查询在途 1 笔只是其特例，S21/S17）；`-3` 是 **API 级「每秒发送请求数超过许可数」**（S30 原文；交易所侧同文案见 S6/S7）。S30 表明报单/撤单同样会收到 `-2/-3` → 二者是 **API 通用流控返回码**，不是查询专属。把它们归因到 FTD 会误导处置。
3. **报单流控是另一层且报单+撤单合并**（S21）→ Q9（§13.6），不能只靠 FTD 预算解决。
4. **FTD 是 per Session**（S21）：本仓单适配器、单 Session，单一预算正确；若未来多账户/多前置并行，需按 Session 拆分预算。
5. **6/s 是常见默认/示例，不是保证值**（S15/S21/S22/S23）→ 必须做成 `ChannelCapability` 可配置项；未配置时取 6 作**保守假设**（宁可少发，不可超发）。
6. **一处源歧义需保留**：S21 写「所有 ReqQuery 开头查询函数不受流控限制（走交易核心，不走查询核心）」。若该句成立，本仓 3 个 `ReqQry*` 启动查询不受 `QryFreq`，但仍受**在途 1 笔**与 FTD 约束。**建议暂不据此放宽**，保持 1/s + 在途 1，待 SimNow 探针验证（Q8c）——放宽的收益只是启动快几秒，代价是可能触发真机流控。

### 13.5 候选方案（Q8）

| 方案 | 做法 | 优点 | 代价 / 风险 |
|------|------|------|-------------|
| **A（推荐）通道层共享 FTD 预算** | 新增 `ChannelCapability.max_ftd_per_sec`（CTP 默认 6.0，可配）+ `ftd_reserve`（默认 1）；`FtdBudget` 可注入 clock；每次请求顺序 = **FTD 预算 → 类型桶（submit/cancel/query）→ 发送 → record** | 与真机语义同构；保留现有三桶；可测；无需改 P-053 台账语义 | 需改 `gateway` 请求入口；耗尽策略需裁决（Q8b） |
| B 静态下调各桶 | 把 submit/cancel 上限压到 `floor((FTD - query - reserve)/2)` | 改动最小 | 过于保守（浪费 FTD）；无法适应「某一类型突发」；仍不能防三类型叠加 |
| C 统一请求队列 | 所有 FTD 请求进单一 6/s 桶 + 各类型队列（S15 两队列的推广） | 最接近前置语义；天然削峰 | 改动最大；需处理优先级与 deadline；可作为 A 的演进 |
| D 不做，依赖前置缓存 | 继续三桶独立 | 零改动 | 延迟不可观测、不可控；与 P-054「订单不可丢 + 可观测」冲突；能力声明 10/10 仍误导 |

> **推荐 A**，并预留向 C 演进（当查询/巡检请求增多或需要优先级时）。A 的耗尽策略建议分类型：**查询/巡检 → 等待到下一窗**（契合前置缓存）；**报单/撤单 → 有界队列 + deadline 或 fail-fast `rate_ftd`**（不得静默延迟，否则盘中不可控）。

### 13.6 邻近问题 Q9（G11）：柜台报单流控是报单+撤单合并额度

- S21 明确报单流控覆盖 `ReqOrderInsert` **与** `ReqOrderAction`，是柜台端每客户每秒的**合并**额度；监管口径同样按「报撤单」合并计量（中金所 1 秒 10 笔以上报撤单触发报告义务，S31；证监会将报单、撤单并列列为高频特征，S32）。
- 本仓 `_submit_ledger` 与 `_cancel_ledger` 完全独立（[gateway.py#L102-L103](../live/gateway.py#L102-L103)），内部 1/s 下同秒可 **1 报 + 1 撤 = 2 笔**：可能超过柜台配置，也与 D2「≤1 笔/秒」口径不符。
- 建议：新增**报单流控预算**（submit+cancel 共享），与 FTD 预算分开；或合并为单一 `_order_ledger`。查询仍独立。
- 这是 P-054 设计需一并裁决的 Q9；**不在本轮改 P-053 实现**。

### 13.7 对 P-054 的影响与验收

- P-054 查询调度器必须同时接 **FTD 预算**与**查询类型桶**（1/s + 在途 1）；启动恢复 3 查询 + 登录/确认必须落在同一预算内。按 1/s 查询节奏，每秒 FTD 占用 ≤ 3（1 查询 + 登录/确认），与 6/s 兼容——**Q8 不改变 U-P053-18 的 1/s 结论**。
- `/health/ready` 暴露 `ftd_remaining`、`last_ftd_wait_s`；指标：`ftd_tokens_remaining`、`ftd_wait_seconds_total`、`rate_denied_total{reason}`（reason 含 `per_second` / `ftd` / `order_flow`）。
- 验收探针：注入 fake clock，构造「同一秒 6 笔 FTD 后第 7 笔」，断言按策略等待或拒绝；构造「submit+cancel+query 同秒打满」，断言不超 FTD；构造「启动 3 查询 + 登录/确认」，断言不超预算；`-2/-3` 重试不重复入账（复用 `fill_key` 幂等）。
- **本轮不改 P-053 代码**；`max_ftd_per_sec` / `ftd_reserve` / 耗尽策略由 P-054 Step 3 设计定案。

---

## 14. 算法源码级取证（2026-11-22）

> 目的：把 §5/§13 的推荐方案从「文档级主张」下沉到「可照抄实现的源码事实」。本轮全部取**上游库/上游网关真实源码**（S24-S29），不引用二手转述；版本均为读取当日 `master` HEAD，**未锁 commit**（降级见 §14.10）。

### 14.1 取证清单

| # | 源码 | 取到的关键代码事实 |
|---|------|--------------------|
| S24 | PyrateLimiter `abstracts/algorithm.py` | 默认算法 `SlidingWindowLog`；`FixedWindow` docstring 明示跨边界 2×；`GCRA` 每 rate 一个整数 TAT；`TokenBucket` 即 GCRA 别名；`Decision.retry_after_ms` 与判定同一次加锁产出 |
| S25 | PyrateLimiter `abstracts/bucket.py` | `put()` 返回 bool、`put_decision()` 返回 `Decision`；`waiting()` 计算可再消费时间；`Leaker` 用守护线程/asyncio Task 周期泄漏 |
| S26 | limits `limits/strategies.py` | `FixedWindowRateLimiter.hit = storage.incr(key) <= amount`；`MovingWindowRateLimiter.hit = acquire_entry(...)`；滑动计数为两桶加权 |
| S27 | aiolimiter `leakybucket.py` | `AsyncLimiter` 单一 `_level` + `_leak()`（`elapsed * rate_per_sec` 递减）+ `acquire()` heapq 等待队列；**只有容量上限，无并发上限** |
| S28 | tenacity `wait.py` | `wait_random_exponential` = `random.uniform(min, high)`，`high = max(min, min(multiplier * exp_base**(n-1), max))` |
| S29 | vnpy_ctp `gateway/ctp_gateway.py` | `init_query` 只注册 2 个查询；`process_timer_event` 每两 tick 只 `pop` 并执行**一个**查询后 `append`；`onRspUserLogin` → `reqSettlementInfoConfirm` 后才进入查询 |

### 14.2 四种限流状态模型对照

| 算法 | 上游实现 | 状态量 | 边界行为 | 能否表达「单在途」 |
|------|----------|--------|----------|--------------------|
| **固定窗口** | limits `FixedWindowRateLimiter`（S26）；PyrateLimiter `FixedWindow`（S24） | 每窗一个计数 | **跨窗边界可达 2×limit**（S24 原文："up to `2 * limit` can pass across a window boundary"） | 否 |
| **滑动日志** | PyrateLimiter 默认 `SlidingWindowLog.admit`（S24） | 每消费单位一条记录 | 精确，无边界突发 | 否 |
| **滑动计数** | limits `SlidingWindowCounterRateLimiter`（S26） | 相邻两窗计数 + 权重 | 近似（误差 ≤ 1 窗） | 否 |
| **令牌桶 / GCRA** | PyrateLimiter `GCRA`；`TokenBucket` 仅是别名（S24） | 每个 rate 一个整数 TAT（微秒） | 可持续 `limit/interval`，按 `burst` 容忍突发 | 否（burst 是速率突发，不是并发） |
| **异步漏桶** | aiolimiter `AsyncLimiter`（S27） | 单个浮点 `_level` + 等待堆 | `level` 随时间泄漏；`acquire` 阻塞至可用 | 否（容量 ≠ 并发） |

**结论：主流限流库都不建模「在途/并发」。** CTP 的 `-2`（API 级未处理请求超限，查询在途 1 是其特例）只能用**信号量/在途计数**表达，不能靠限流器表达（§14.5）。这也解释了为什么本仓 `RateLedger` 天然无法覆盖 `-2`。

### 14.3 本仓 `check_rate` 的算法归属与源码级差异

1. **归属 = 整数秒固定窗口**：`record` 只保留 `sec-1` / `sec` 两桶（[compliance.py#L101-L113](../core/compliance.py#L101-L113)），`check_rate` 只查 `int(ts)` 当前桶（[L123-L137](../core/compliance.py#L123-L137)）——与 S26 `FixedWindowRateLimiter` 同构（计数 + 窗内比较），不是滑动窗口。
2. **差异 1（G12，P3）边界双倍突发**：t=0.999 与 t=1.001 各 1 笔，任意滚动 1s 内为 2 笔。CTP 前置 FTD 按自然秒计（S21），故「本仓→CTP」同构、不额外放大；但 P-054 若对**客户端**承诺「每客户端严格 N/s」，固定窗口不成立，需 `SlidingWindowLog`（每请求一条记录）或 `GCRA`（单 TAT）。
3. **差异 2（G13，P2）计量口径不一致**：本仓是「**成功才记**」——submit 的 `record` 在 ack 之后（[gateway.py#L261](../live/gateway.py#L261)），cancel 在撤单成功之后（[L396](../live/gateway.py#L396)），拒单与 `ChannelUnavailable` **都不记**；而前置 FTD/报单流控是「**发送即计**」（S21/S16，超限才缓存/报错，但请求已计入）。→ 内部台账**系统性低估**真实消耗；Q8 方案 A 的 `FtdBudget` 必须在**发送前 reserve**，否则高拒单率时照样打满前置。
4. **差异 3（P3）check-then-act 非原子**：`check_rate` 与 `record` 是两次调用（[L199-L205](../live/gateway.py#L199-L205) 与 [L261](../live/gateway.py#L261)），单线程网关下安全；P-054 多 worker/多线程时同秒并发会同时通过 check。上游做法是单次加锁内完成「判定 + 扣减 + 计算 retry-after」并返回 `Decision`（S24 `put_decision`、S25 bucket `Lock`）→ P-054 应改为 `try_acquire(ts) -> Decision{allowed, retry_after_ms}`（Q10）。
5. **命名观察**：查询台账复用 `record(..., is_cancel=False)`（[L361](../live/gateway.py#L361)），使 `RateLedger.daily_orders` 实际承载「当日查询数」；单看指标名会误读，P-054 指标需另起字段。

### 14.4 退避 + 全抖动：源码精确公式（可直接内联，零新依赖）

S28 `tenacity/wait.py` L174-191 + L210-213 的真实逻辑：

```python
exponent = attempt_number - 1
high = max(min, min(multiplier * exp_base ** exponent, max))  # 含溢出短路
sleep = random.uniform(min, high)                             # Full Jitter
```

要点（源码级，非二手）：

- `wait_random_exponential` **不是** Equal Jitter；它把整个 `[min, high]` 当均匀采样区间，docstring 明示对应 AWS **Full Jitter**。
- 上界计算带 `math.log` 提前短路与 `OverflowError` 兜底 → 大 retry 次数不会溢出。
- 内联到本仓约 10 行、只用 `random`，符合 **D14 零新依赖**；建议 `multiplier=0.5, max=8, min=0`，并叠加**总截止时间**（U-P053-18 的启动恢复不应无限重试）。
- 语义提醒（S28 docstring 原文）：`wait_random_exponential` 适用于「等资源恢复」，`wait_exponential`（固定间隔）适用于「争用共享资源」；本仓 `-3`/`-2` 属前者 → 用 full jitter 正确。

### 14.5 查询流控 = 速率 + 在途，必须是两个原语

CTP 查询层同时约束两件事（S21/S17）：`QryFreq`（前置，常见 1/s）与 **API 在途 1 笔**（超出返回 `-2`；`-2` 是 API 级未处理请求上限，S30）。二者不可用一个限流器表达：

| 约束 | 正确原语 | 上游源码证据 |
|------|----------|--------------|
| 每秒 ≤ 1 次 | GCRA / 最小间隔（TAT） | S24 `GCRA`：`TAT += weight * emission_interval`，单状态精确 |
| 同时在途 ≤ 1 | `Semaphore(1)`（asyncio/threading） | **无限流库提供**；S27 也明确只有 `_level` 容量，无并发计数 |

推荐组合：`QueryGate = FtdBudget.reserve("query") + GCRA(1/s) + Semaphore(1)`；`-2` → 等在途释放后重试（不盲退避），`-3` → full jitter 退避并计重试次数。重试不重复入账的前提已在仓内具备（`fill_key` 去重 + 合法迁移守卫，§5.3）。

### 14.6 vnpy_ctp 的工程同构解（源码级）

S29 `ctp_gateway.py`：

- `init_query()` 只挂两个查询函数：`[self.query_account, self.query_position]`（L209-212）。
- `process_timer_event()`：`count += 1; if count < 2: return`，否则 `func = query_functions.pop(0); func(); query_functions.append(func)`（L199-207）→ **每两个 timer tick 只发一个查询**，两类查询轮转。
- `onRspUserLogin` 成功后立即 `reqSettlementInfoConfirm`（L402-415），确认完成后才进入查询轮询。

即：上游成熟网关用**定时器驱动的串行轮询**替代「启动期批量查询」，与 U-P053-18 的「同秒 3 连发」正好相反。这是方案 A「启动期串行合并 + 最小间隔」的直接工程锚点。

反向证据（必须注意）：该文件**未处理 `-2/-3`**（仅 `write_error` 记录 ErrorID/ErrorMsg，L193-198；grep 无 `-2`/`-3` 分支）→ **不可照抄**，P-054 必须自行补退避与在途门（§14.5）。

### 14.7 FTD 的可见性边界（为什么只能做成配置项）

- S16 原文：FTD 报文流控**配置在交易前置组件**上，配置项为 `FTDMaxCommFlux`。
- 本仓 `ChannelCapability`（[channel.py](../live/channel.py)）与 CTP 适配层（[ctp.py#L46-L62](../live/adapters/ctp.py#L46-L62)）均**无**该字段；公开 API 文档（S21/S23）也未给出读取该配置的请求。
- → 运行时**不可能探测**该值，只能由券商/运维告知后写入 `ChannelCapability.max_ftd_per_sec`；未配置取 6 是唯一可行默认（呼应 §13.4-5）。这也从源头解释了 §13.2「能力声明 10/10 与 FTD 6 矛盾」：适配层把「报单能力」误当成了「共享报文能力」。

### 14.8 outbox relay 的源码级语义与两处改进

- **生产端幂等但不防冲突**：`append_outbox` 用 `INSERT OR IGNORE`（[ledger_store.py#L121-L126](../live/ledger_store.py#L121-L126)）——同 `event_id` 重复写安全，但**同 `event_id` 不同 payload 会被静默丢弃**。因此 `event_id` 必须带状态/版本（如 `order:{coid}:accepted:v1`），否则状态迁移事件会「以为写进去了、其实被忽略」（Q2/Q11）。
- **消费顺序不稳定**：`pending_outbox` 只 `ORDER BY created_ts`（[L128-L132](../live/ledger_store.py#L128-L132)）——同秒多事件并列时 SQLite 不保证顺序，relay 可能先发「成交」后发「受理」。`ORDER BY created_ts, rowid` 只是**零迁移退路**；稳健方案见 §16：显式 `seq INTEGER PRIMARY KEY AUTOINCREMENT`（SQLite 官方：默认 rowid 删除最大行后可能复用、VACUUM 可重排；AUTOINCREMENT 保证从未使用且单调递增，S33/S34），索引 `(sent, seq)`。
- **at-least-once 是结构性的**：`mark_sent` 在 publish 之后单独开事务（[L134-L136](../live/ledger_store.py#L134-L136)）；publish 成功、mark 前崩溃 → 重投。这不是缺陷，而是 outbox 的定义（S1/S13）；消费端必须按业务 `event_id` 去重（S1/S11）。
- **组合写必须绕开现有方法**：`transaction()` 是裸 `BEGIN IMMEDIATE`（[L140-L148](../live/ledger_store.py#L140-L148)），而 `append_entry`/`upsert_order`/`append_outbox` 各自 `with self.transaction()` → 在事务内调用会触发嵌套 `BEGIN`（SQLite 直接报错，S2）。方案 A 的 `append_entries_with_events(...)` 必须在**同一个 `with transaction()` 内直接 execute**，不能复用现有公开方法。

### 14.9 对推荐方案 A 的修订（经源码校准）

1. `FtdBudget.reserve(kind) -> Decision`：**发送前**扣减（G13）；只有「本地未发出」才退还，拒单/超时/`-3` 不退还（匹配前置「发送即计」）。
2. 两级桶顺序：**FTD 共享桶（6/s，`ftd_reserve=1`）→ 类型桶**（submit+cancel 合并为 `order_flow`；query 独立 1/s）→ 发送 → 记账。
3. 并发安全：单 `Lock`（同步网关）或 `asyncio.Lock`（服务层）内完成「FTD 扣减 + 类型桶扣减 + 记账」，消灭 check-then-act（§14.3-4）。
4. 查询走「GCRA + `Semaphore(1)` + full jitter」；启动 3 查询**串行化**（§14.6），`/health/ready` 挂在恢复序之后。
5. 可观测：`Decision.retry_after_ms` 直接暴露为 `ftd_wait_ms` / `rate_retry_after_ms`——与 S24 一致（判定与等待同一次加锁产出，避免二次读状态漂移）。

### 14.10 来源与降级

- 六处源码均通过 `raw.githubusercontent.com` 直取**文件正文**并落盘（S24-S29），不是文档页转述；均在读取当日 `master` HEAD，**未锁 commit** → 若后续需要可复现性，应在 P-054 设计文档中锁 tag/commit。
- **未取证项**：CTP 头文件 `ThostFtdcUserApiStruct.h`/`ThostFtdcTraderApi.h` 中是否存在 `FTDMaxCommFlux` 字段——公开镜像可检索性差，本轮两次精确检索均未命中。不影响结论：S16 已明确它是**前置组件配置项**，客户端 API 无读取入口。
- 版本风险：`limits`/`PyrateLimiter` 的类名与文件路径随大版本变化（PyrateLimiter v5 将 `algorithm` 提升为公开扩展点），引用时以**行为**（固定窗口/滑动日志/TAT/Full Jitter）为准，不以符号名为准。

---

## 15. 裁决记录：Q8 / Q9 / Q10 是否纳入改造（2026-11-22）

> 判据（按优先级）：① 是否 P-054 验收所必需或已登记为 P-054 前置；② 是否改变 P-053 已关闭批次的**默认路径行为**（可回归性）；③ 改动半径与回归成本；④ 是否引入新依赖（D14）。

### 15.1 裁决结论

| ID | 裁决 | 落点 | 一句话理由 |
|----|------|------|------------|
| **Q8** 共享 FTD 预算 | **纳入 P-054 批内** | 与 U-P053-18 合并为**同一「通道流控前置包」**（`live/channel.py` + `live/gateway.py` + `live/adapters/ctp.py` + 测试） | §13.7 已明确「查询调度器必须同时接 FTD 预算」；两者改同一请求入口，拆批会二次改 `gateway.py` |
| **Q9** 报单+撤单合并额度 | **纳入 P-054 批内** | 同上工作包（新增 order-flow 预算，不动 `RateLedger` 统计） | 与 Q8 同属「发送前预算层」，共用一套 fake clock 测试夹具 |
| **Q10** 限流原语升级（`try_acquire()->Decision`、固定窗口→GCRA/滑动日志） | **本轮不改造** | 登记为**并发化触发项**；P-054 设计只保留接口演进方向 | P-054 验收明确 REST 管理面**不含下单/撤单**，本批无并发订单路径；改造波及 `check_rate` 的 **4 处调用点 / 2 个模块**（gateway 3 + safety_gate 1）与 **6 个测试文件 / 38 处引用**（详见 §15.7），收益不在本批验收内 |

### 15.2 Q8 纳入的边界（做什么 / 不做什么）

**做**：

1. `ChannelCapability` 新增 `max_ftd_per_sec: float = 6.0`（S21/S16/S22 的保守默认，券商可配）与 `ftd_reserve: int = 1`。
2. 新增 `FtdBudget`：可注入 clock、单锁、`reserve(kind) -> Decision{allowed, retry_after_ms}`；**发送前扣减**（G13），仅「本地未发出」退还。
3. 顺序固定为：**FTD 预算 → 类型预算（order_flow / query）→ 发送 → 既有 `RateLedger` 统计记录**。
4. CTP 适配器修正能力声明：`max_submit_per_sec=10.0` / `max_cancel_per_sec=10.0` 不得被读作「可报单 10 次/秒」——在 `ChannelCapability` 中明确 FTD 6/s 是**共享硬约束**（或把声明下调到不高于 FTD），消除 §13.2 的能力声明矛盾。
5. 指标/健康：`ftd_remaining`、`ftd_wait_seconds_total`、`rate_denied_total{reason="ftd"}`。

**不做**：

- 不改 `RateLedger` 的数据结构、不把「成功才 record」改成「发送即 record」（避免动 P-053 统计语义；计量差异由新增预算层吸收）。
- 不改默认 `max_per_second=1`（D2）；默认路径下 FTD 上限 3/s，**永不拒绝**。
- 不做方案 C 统一队列、不引入 Redis/新依赖（D14）。

### 15.3 Q9 纳入的边界（做什么 / 不做什么）

**做**：

1. 新增 **order-flow 共享预算**（submit + cancel 合并），默认 = **2 × 内部 `max_per_second`**（每类型桶保留各 1/s；**不设日上限**，daily 口径保持现状：报单 1000/日 + 撤单不设日限，与已关闭实现一致）。依据：§17.2 A1-A8 + §18 行业案例 B1-B7（证据锚定裁决 2026-11-22）。`submit` 与 `cancel` 都先向它 reserve。
2. 两个既有 `RateLedger` 保留：`_submit_ledger` 继续维护 `daily_orders` 与撤单率统计，`_cancel_ledger` 继续维护 `daily_cancels`。
3. 拒绝理由新增 `rate_order_flow`（与 `rate_ftd`、`rate_per_second` 并列）。

**不做**：

- 不把两个 `RateLedger` 合并成一个（会破坏 `cancel_ratio` 分母/分子的口径与既有测试）。
- 不改 `cancel()` 的返回值语义与状态迁移。

### 15.4 Q10 不纳入的理由与触发条件

**理由**：

1. P-054 验收（§1.1）写明 REST 管理面「可写但**不含下单/撤单交易逻辑**」→ 本批不存在并发 `submit` 路径，check-then-act 的竞态无实际暴露面。
2. 改造需改 `check_rate`/`record` 的调用契约（[compliance.py#L123-L137](../core/compliance.py#L123-L137)）并同步 gateway 全部调用点与相关测试；对 P-054 验收**零贡献**。
3. 固定窗口的边界双倍突发（G12）与 CTP 前置「自然秒」同构，真机侧不放大；对外严格限流是 P-054 之外的需求。

**触发条件（满足任一即升级为改造）**：

- 出现**并发** `submit`/`cancel`：多 worker 共享 gateway、异步执行器、或对外多客户端下单 API；
- P-054 若把 WS/REST 扩展为可交易（超出当前验收口径）；
- 需要对客户端承诺「严格滑动 N/s」（届时一并决定固定窗口→`SlidingWindowLog`/`GCRA`）。

**过渡保护**：Q8 的 `FtdBudget` 内部用单锁完成「判定 + 扣减 + retry_after」，不新增竞态；Q10 的接口形状（`Decision{allowed, retry_after_ms}`）在 `FtdBudget` 上先落地，后续替换 `RateLedger` 时无需再改调用方。

### 15.5 对 P-054 Step 3 设计与验收的硬要求

1. **测试矩阵**（全部 fake clock，不依赖真机）：
   - 同秒 6 笔 FTD 后第 7 笔 → 按类型策略等待或 `rate_ftd`；
   - 同秒 1 submit + 1 cancel → **允许**（order-flow 默认 2/s）；同秒第 3 笔（再报或再撤）→ `rate_order_flow`；**撤单被拒必须 audit + 显式原因**（G15）；
   - 启动 3 查询 + 登录/结算确认 → 不超 FTD；同秒第 2 查询 → 等待/串行，不抛 `ChannelUnavailable`；
   - **拒单也消耗 FTD**（G13）：连续 6 笔拒单后第 7 笔仍受限（不能因「未成功」而不计）；
   - `-2`/`-3` 重试不重复入账（`fill_key` 幂等）。
2. **默认路径回归**：既有 1300 测试全绿；默认（FTD 6 + order-flow 2 + 各类 1/s）下同秒 1报+1撤 **允许**，行为与 P-053 一致；kill-switch/`cancel_all` 的预算语义按 Q12 单独裁决（预留槽位 / bypass+audit / 批量撤单单请求，§18-B7）。
3. **文档同步**：DESIGN 增补「预算层」一节，明确「预算层=发送前、统计层=成功后」两层语义，避免再次出现 DESIGN §3.3 N-4 式声明与实现不符。

### 15.6 影响

- Q8/Q9 使 P-054 的工作量增加一个「通道流控前置包」，但**减少一次对 `gateway.py` 的二次改动**，且让 §13.7 的查询调度器有正确的预算底座。
- Q10 暂缓不产生技术债：`RateLedger` 保持现状，`FtdBudget` 以 `Decision` 形状先行隔离；触发条件明确、可随时升级。

### 15.7 依据强度审计（2026-11-22，回应「裁决是否有充分调研依据」）

| 裁决 | 支撑证据 | 强度 | 缺口 / 残余不确定性 | 处置 |
|------|----------|------|----------------------|------|
| **Q8 纳入** | S21（官方镜像）+ S16（官方 CHM 转录，同源）+ **S15/S22（独立第三方：查询挤占报单、6 笔/秒超限排队）** + S23（券商可配）+ S29（vnpy 串行轮询实现）+ 仓内暴露矩阵（§13.2）+ S24/S27（算法源码） | **强**：≥2 独立来源 + ≥1 T1/T2 + 源码 + 仓内代码实证 | ① 6/s 是常见默认非保证（已用「默认 6 + 可配 + reserve 1」缓解）；② 「FTD 发送即计」由「超限缓存不报错」推定，无直接计费字段 | 可进入设计；SimNow 探针作为最终验证（Q8c） |
| **Q9 纳入** | S21/S16（`ReqOrderInsert`+`ReqOrderAction` 并列，**核心事实同源**）+ 本轮新增 **S31（中金所：报撤单合并计量，T1）** + **S32（证监会：报单、撤单并列，T1）** + 仓内三台账独立（G11） | **中强**：核心事实单源，但已补两条独立官方/监管锚点 | 柜台【程序化交易频繁报撤单管理】的**具体计数细则**无公开逐条文档；撤单是否单独占额度需券商确认 | 裁决维持（与监管「报撤单合并」口径一致且更保守）；SimNow/券商确认为最终验证 |
| **Q10 暂缓** | F7 验收「REST 管理面不含下单/撤单」（T1 仓内）+ 调用面实测 **4 处 / 2 模块**（gateway 3 + safety_gate 1）+ 测试面实测 **6 文件 / 38 处** + 固定窗口与 CTP 自然秒同构（S21/S24/S26） | **中**：属「范围 + 成本」裁决，不是外部事实裁决 | 原表述「波及 1300 测试」**不准确**（1300 为全量基线，非受影响数），已更正 | 结论不变；触发条件与 `Decision` 过渡形状见 §15.4 |
| **Q8+Q9 同包** | 两者共用 `gateway` 请求入口与 fake clock 夹具；§13.7 要求查询调度器接 FTD 预算 | **强**：代码结构 + 设计依赖 | 工作量未估（不影响裁决） | 合并为「通道流控前置包」 |

**审计结论**：

- **Q8：依据充分**（多源 + 源码 + 代码矩阵），可进入设计。
- **Q9：直接证据同源**（S21/S16），本轮补 S31/S32 两条独立监管锚点后达到「可裁决」；柜台细则仍需真机/券商确认，属**已知残余不确定性**，不阻塞设计。
- **Q10：依据成立但类型不同**——它是范围/成本裁决，不是外部调研结论；原「1300 测试」为夸大表述，已按实测更正为 4 处调用点 / 2 模块 / 6 文件 38 处引用。
- **顺带更正（本轮审计发现）**：S30 显示 `-2/-3` 是 **API 通用返回码**（`ReqOrderAction` 同样返回），原 §13.4「`-2` = 查询在途」表述过窄，已改为「API 级未处理请求超限，查询在途 1 是特例」。该更正不改变 Q8/Q9 裁决，但影响 P-054 的错误分类指标（`rate_denied_total{reason}` 不应把 `-2` 归入查询专属）。

---

## 16. Q11 专项：outbox relay 排序/索引与 event_id 版本化（2026-11-22）

> Q11 来自 §14.8：① `pending_outbox` 仅 `ORDER BY created_ts`，同秒并列无稳定序；② `INSERT OR IGNORE` 对同 `event_id` 不同 payload 静默丢弃。本节只回答三件事：**需要什么级别的顺序保证、`event_id` 怎么构造、索引与保留怎么定**。

### 16.1 问题拆解

| 子问题 | 现状 | 必须回答 |
|--------|------|----------|
| **Q11a 顺序** | `pending_outbox` = `WHERE sent=0 ORDER BY created_ts`（[ledger_store.py#L128-L132](../live/ledger_store.py#L128-L132)） | 需要全局有序还是仅聚合内有序？排序键在删除/VACUUM 后是否仍稳定？ |
| **Q11b 标识** | `event_id = uuid4()`（G6），写入 `INSERT OR IGNORE`（[L121-L126](../live/ledger_store.py#L121-L126)） | 同 key 重复与「同 key 不同 payload」分别怎么处理？消费端凭什么去重？ |
| **Q11c 性能/保留** | 无 `sent` 索引、无删除策略 | relay 扫描成本？删除 sent 行后排序是否失效？ |

### 16.2 外部锚点

| 锚点 | 层级/日期 | 关键原文/事实 | 支撑的判断 |
|------|-----------|----------------|------------|
| **S33** SQLite AUTOINCREMENT | **T1** 官方 / 2024-02-22 | 默认算法：删除最大 ROWID 行后「ROWIDs from previously deleted rows **might be reused**」且「might not be in strictly ascending order」；`AUTOINCREMENT` 保证「**never been used before**」且「**monotonically increasing**」（允许空洞） | 排序键不能依赖默认 rowid；显式 `seq` 才稳定 |
| **S34** SQLite VACUUM | **T1** 官方 / 2025-07-12 | 「VACUUM **may change the ROWIDs** of entries in any tables that do not have an explicit INTEGER PRIMARY KEY」 | 即使不删行，维护动作也可能打乱 rowid 序 → `ORDER BY rowid` 不是契约 |
| **S35** Debezium Outbox Event Router | **T1** 官方 / stable | outbox 表列：`id`（事件唯一 ID，**用于消费端去除重复消息**）、`aggregatetype`、`aggregateid`、`type`、`payload`；`aggregateid` 作为消息 key，「important for **maintaining correct order** in Kafka partitions」 | 顺序保证的正确粒度是**聚合内**（同 key 同分区），不是无差别全局序 |
| **S36** Stripe Idempotent requests | T2 行业权威 / — | 「The idempotency layer **compares incoming parameters** to those of the original request and **errors if they're not the same** to prevent accidental misuse」；key 有保留期（v1 为 24h），过期重用会新建请求 | 同 key 不同 payload 必须**显式报错**，不能静默忽略；去重窗口是显式设计项 |
| S1 microservices.io / S11 华为云 | T1 / T3 | outbox 为 at-least-once，消费端必须按事件 ID 幂等（§4/§12 已证） | 去重责任在消费端，需 inbox 表 |

### 16.3 由锚点直接推出的事实

1. **`ORDER BY created_ts, rowid` 只是零迁移退路，不是稳健契约**：SQLite 官方同时给出「rowid 可能复用」（S33）与「VACUUM 可能重排」（S34）两条反例；本仓又是 `journal_mode=WAL` 的长期运行库，未来任何清理/维护都可能破坏顺序。
2. **`AUTOINCREMENT` 才提供 relay 需要的两个性质**：从未使用 + 单调递增（S33）。注意它**不保证连续**——插入失败会留空洞，所以 relay 不能假设 `seq+1` 存在，只能做 `seq > cursor` 的范围扫描。
3. **顺序保证应定在「聚合内」**：Debezium 的工程解是把 `aggregateid` 作消息 key 以保同聚合有序（S35）；本仓 `coid` 即聚合 ID。单 relay 时天然获得全局序；多 relay 时必须按 `coid` 分区，否则只能保证聚合内序。
4. **同 key 冲突必须报错**：Stripe 的幂等层会比较参数并在不一致时报错（S36）。本仓 `INSERT OR IGNORE` 的静默丢弃与之相反，属于**数据丢失型静默失败**。

### 16.4 候选方案

| 方案 | 做法 | 优点 | 代价 / 风险 |
|------|------|------|-------------|
| **A（推荐）显式 seq** | 重建 outbox：`seq INTEGER PRIMARY KEY AUTOINCREMENT`、`event_id TEXT NOT NULL UNIQUE`；relay `WHERE sent=0 ORDER BY seq LIMIT N`；索引 `(sent, seq)`；单 relay → 全局有序 | 顺序稳定（S33）；删除/维护/VACUUM 不影响；relay 可做游标分页 | 一次性表重建迁移；`pending_outbox` 返回结构增加 `seq` |
| B 零迁移 | 保留 `event_id` 主键，改 `ORDER BY created_ts, rowid` + `(sent, created_ts)` 索引 | 零迁移 | rowid 可复用、VACUUM 可重排（S33/S34）；同秒依赖物理序，不是契约 |
| C 独立游标表 | 新增 `outbox_cursor(max_seq)` 单行表，插入时在事务内自增 | 不重建 outbox | 多一张表 + 每次写多一次 UPDATE；收益与 A 相同，复杂度更高 |

> **推荐 A**。迁移方式（在 `SqliteLedgerStore.__init__` 内先探测 `PRAGMA table_info(outbox)` 是否含 `seq`）：`RENAME → CREATE 新表 → INSERT ... SELECT ... ORDER BY rowid → DROP → RENAME`，整体包在一个 `BEGIN IMMEDIATE` 内；旧库按原 rowid 序映射为 seq，保持历史顺序。

### 16.5 event_id 规则与冲突语义（建议裁决）

1. **格式**：`<aggregate_type>:<aggregate_id>:<event_type>:v<n>`，例如 `order:{coid}:accepted:v1` / `order:{coid}:filled:v2`。
   - `n` 为聚合内事件序号（或状态机版本）；**payload 任何变化都必须递增 n**，保证「同 key ⇒ 同 payload」。
   - 禁止随机 UUID 作为唯一事件标识（G6）：重放/重试时无法稳定复用，消费端无法去重。
2. **写入**：保留 `INSERT ... ON CONFLICT(event_id) DO NOTHING` 以支持重试幂等；但随后必须**读取既有行并比对 `event_type` + `payload`**，不一致则抛 `OutboxEventConflict`（对齐 S36 的「不同参数即报错」）。该异常不得被吞掉。
3. **消费端**：`processed_event(event_id TEXT PRIMARY KEY, processed_ts REAL)`，与业务效果**同事务**提交；去重记录保留期 ≥ relay 最大重投窗口（Stripe 的 24h 仅作参照，本仓按自身保留策略定）。
4. **契约测试**：断言「同 key 同 payload 重写 → 静默通过；同 key 不同 payload → 抛错」，防止未来有人把校验删掉。

### 16.6 裁决（2026-11-22 已确认）

- **Q11 纳入 P-054 批内**（用户 2026-11-22 确认，与 U-P053-17 的 store 改造**同一次迁移**完成），采用 **方案 A + §16.5 规则**；状态从「建议」转为**已裁决**，进入 P-054 Step 3 设计与实施排期。
- 理由：P-054 必须新增 relay，排序与去重是 relay 的正确性前提；迁移只做一次，避免 P-054 上线后再改表；无新依赖（D14）。
- 成本：一次 outbox 表重建 + `pending_outbox` 返回 `seq` + 1 个冲突异常 + 1 张 inbox 表；均在本批 store 改造范围内。
- 残余不确定性：**无外部事实缺口**（全部为本地 SQL 语义）；唯一取舍是「全局有序 vs 多 relay 并行」——本仓自用、单 relay → 全局有序；若未来多 relay，按 `coid` 分区（S35 同构）。

### 16.7 验收探针（fake clock + 临时 SQLite 文件）

1. 同秒插入 3 条 → relay 返回顺序 = 插入顺序（`seq` 单调）。
2. 删除最大 `seq` 行后再插入 → `seq` **不复用**（AUTOINCREMENT，S33）。
3. 同 `event_id` 不同 payload → 抛 `OutboxEventConflict`，**不得静默**。
4. `publish` 成功、`mark_sent` 前崩溃 → 重启重投；消费端 inbox 去重 → 业务效果恰好一次。
5. `EXPLAIN QUERY PLAN` 断言 `WHERE sent=0 ORDER BY seq` 命中 `(sent, seq)` 索引。
6. 迁移测试：旧表（无 `seq`）插入 3 条 → 迁移后 `seq` 顺序与原插入顺序一致。

### 16.8 来源与降级

- S33/S34/S35 为 T1 官方文档，S36 为 T2 行业权威；S1/S11 复用既有 outbox/幂等结论。
- **未取证**：Eventuate Tram 的 `MESSAGE` 表 DDL 与 relay 排序实现（检索仅得目录页，未直取正文），故**不作锚点**；不影响结论——排序维度由 SQLite 官方覆盖，去重维度由 Debezium/Stripe 覆盖。
- 版本：Debezium 为 `stable`（页面未标版本号）、Stripe 文档未标版本；SQLite 两页有明确更新日期（2024-02-22 / 2025-07-12）。

---

## 17. F-1 决策依据专项：order-flow 预算默认值（2026-11-22）

> 复审 F-1 的根源不是「两个方案哪个好」，而是 **D2「≤1 笔/秒」的「笔」从未被定义**。本节只做三件事：定位根源、列出可核锚点、给出与锚点自洽的建议。

### 17.1 根源定位

- D2 两处原文均未定义「笔」的归属：调研推荐（[UPGRADE_MASTER_PLAN#L312](UPGRADE_MASTER_PLAN.md)）「速率 ≤1 笔/秒、≤1000 笔/日——见调研 Q9」；裁决（[L324](UPGRADE_MASTER_PLAN.md)）「默认速率上限 ≤1 笔/秒、≤1000 笔/日」。
- **P-052 RESEARCH §4.5（L138-142）已考证**：该值在证监会规定、沪深北实施细则、上期所办法中**查无出处**，是「D2 用户裁决（2026-11-17）的项目内部默认值」，约束只有两条：**可配置 + 远低于高频阈值**（U-P052-5：「与 300/20000 保持 ≥2 个数量级余量」）。
- 两种解释自此分叉：**R1 = 按类型各 ≤1/s**（报单 1/s + 撤单 1/s，daily 只计报单）——**P-052/P-053 已关闭实现取此解**（[compliance.py#L77-L83](../core/compliance.py#L77-L83) + gateway 三桶 + `record(is_cancel)` 不入 `daily_orders`）；**R2 = 报撤单合并 ≤1/s**——§15.3-1 引入的新解释（G11「与 D2 口径不符」采用 R2 措辞）。**F-1 的矛盾 = §15.3-1 取 R2 而 §15.5-2 的回归声明按 R1 写。**

### 17.2 锚点（每条注明指向）

| # | 锚点 | 层级/出处 | 关键事实 | 指向 |
|---|------|-----------|----------|------|
| A1 | D2 数值无监管出处 | T1 仓内（P-052 RESEARCH §4.5） | 1/s 是内部保守默认；唯一硬约束 = 可配置 + 远低于高频阈值 | 1/s 非底线，合并 2/s 不违反 D2 的原始约束 |
| A2 | 已关闭实现取 R1 | T1 仓内（P-052/P-053 关闭态代码） | submit/cancel 各 1/s 独立桶；daily 只计报单 | (b) 将**改写已关闭解释**；(a) 保持。复审口径「已关闭契约不改写」 |
| A3 | 量化余量 | T1/T2 监管（沪深北细则 300 笔/s 报撤单合并，[RESEARCH_p053#L128](RESEARCH_p053_trading_gateway.md)；中金所报告义务 10 笔/s 报撤单，S31） | (a) 峰值 2/s：vs 300 = **150×**（≥2 个数量级 ✓）；vs 报告义务 10 笔/s = 5×，且报告义务需「日内 10 次达 10 笔/s」→ 2/s 永不触发；日均报撤 ≤2000 vs 高频日阈 20000 = 10×（两案相同，由 daily 1000 决定，与秒级预算选择无关） | (a) 满足 U-P052-5 的原始量化意图 |
| A4 | 柜台报单流控量级 | S15 原文（本轮补精确引文） | 「**报单流控最大是每秒 6 次**，假如当前秒已有 1 次查询，报单流控只剩 5 次」（vnpy 假设值；柜台可配，S21/S23） | 2/s < 柜台典型 6/s；(a) 无真机超限风险 |
| A5 | **失败不对称** | T1 仓内（[gateway.py#L385-L389](../live/gateway.py#L385-L389)） | cancel 被拒 → `return False` 无 audit 无原因，与「订单不存在」同值；订单继续存活。submit 被拒无风险；**撤单被拒 = 风险削减动作静默失效** | 预算默认值不应挤压撤单主路径 → **反对 (b)** |
| A6 | kill switch 语义 | 总纲 S1（[UPGRADE_MASTER_PLAN#L159](UPGRADE_MASTER_PLAN.md)）+ [gateway.py#L407-L409](../live/gateway.py#L407-L409) + P-052 §4.4 RTS 6 Art.12 | S1 急停「可选一键撤单」；`cancel_all` 逐单调 `cancel()` → 同秒急停撤单在 (b) 下被拒；RTS 6 kill 要求**立即撤下全部** | (b) 与急停语义冲突；(a) 允许同秒首个撤单 |
| A7 | 监管合并计量 | S31/S32/S30（T1/T2） | 监管按「报撤单」合并计量，但阈值 10/300 笔/s | 合并**机制**正确（Q9 已裁）；1/s 的**数值**无监管依据 |
| A8 | 社区实践 | S15（T3） | vnpy 流控网关：报单队列（含撤单）按 1/6s 调度 = 合并 6/s | 合并机制 + 6/s 量级是社区通行解 |

### 17.3 新发现 G15（由 A5 直接得出）

撤单被拒静默失败（P2）已登记入 §3：无论 F-1 取 (a) 还是 (b)，P-054 都必须让撤单拒绝**显式化**（audit 事件 + 原因返回）；kill-switch 的预算语义（预留槽位 vs bypass+audit）另立 **Q12** 交 Step 3。另注：全仓测试 `grep '\.cancel\('` = 0 命中——撤单限流路径**零测试覆盖**，P-054 测试矩阵须补（两个方案下都要）。

### 17.4 方案对比与裁决（2026-11-22 证据锚定）

| 方案 | order-flow 默认 | 同秒 1报+1撤 | 与锚点的关系 |
|------|------------------|--------------|--------------|
| **(a-修订) 2×internal + 每类各 1/s** | 合并 ≤2/s，类型桶保留 | 允许 | A1/A2/A3/A4/A6/A8 全部指向此案；不触碰已关闭解释；急停同秒撤单可用 |
| (b) internal（合并 ≤1/s） | 合并 ≤1/s | **拒绝** | 仅 R2 字面解释支持；与 A2（改写已关闭实现）、A5/A6（撤单静默失败/急停被拒）冲突 |
| (c) 合并 ≤1/s 但撤单豁免 | submit 受 1/s，撤单只受自身桶 | 允许 | 语义 ≈ (a) 但**不建模柜台合并额度**——Q9 的建模目标落空；放弃 |

> **裁决（证据锚定，2026-11-22）：采用 (a-修订)**——`order_flow_per_sec = 2 × internal_per_second`（每类型桶仍各 1/s 保留），order-flow **不设日上限**（daily 口径保持现状）；配套 **G15 修复**（撤单拒绝显式化）与 **Q12**（kill-switch 预算语义，§18-B7 扩为三选项）。外部案例佐证见 §18（CME/IB/vnpy/Binance 四系统，无一例「报+撤合计 1 笔/s」、无一例静默拒绝）。推翻本裁决须同时推翻 A2（已关闭实现）与 §18-B5（vnpy 内部风控同构），并另行缓解 G15 与 Q12。

### 17.5 修订清单（已于 2026-11-22 全部应用）

1. §15.3-1 已改「默认 = 2×internal（每类型桶保留各 1/s）+ 不设日上限」；§15.5-1 探针已改「同秒 1 报+1 撤 → **允许**；同秒第 3 笔 → `rate_order_flow`」；§15.5-2 已补 G15 显式化要求与 Q12。
2. F-2~F-7 已修订：§0-7「四项硬输入」/ §7.1「四项改造」（F-2）；G6/G14 处置随 §16 更新（F-3）；§11「五个上游库六份源码」（F-4）；§8 多源注纳入 S21/S30-S41（F-5）；Q2 标「格式已由 §16.5 裁决」（F-6）；Q3 标「随 Q11 默认 P-054 批内」（F-7）；PROGRESS §3.61 计数同步（十一条结论 / §2 21 行 / S1-S41）。
3. G15 行、Q12 行已登记；§18 新增 S37-S41。

---

## 18. F-1 外部案例专项：报单/撤单限流的行业实践（2026-11-22）

> 回应「先充分调研寻找外部案例、结合问题实际」：取**交易所 / 经纪商 API / 成熟网关**四类真实系统，看它们如何处理「报单与撤单共享额度」与「撤单失败可靠性」，对照本仓 F-1。

### 18.1 案例表

| # | 系统 | 层级/来源 | 关键事实 | 对本仓的含义 |
|---|------|-----------|----------|--------------|
| **B1** | CME Globex iLink Messaging Controls | **T1** 交易所官方（S37） | 报单等 application messages 共用 **500 MPS（3 秒窗）/ logout 750 MPS** 阈值（Mass Quote/Quote Cancel 另设 350 MPS 桶）；超限 = **Session Level Reject（显式拒绝）** | ① 交易所层「报单+撤单合并计量」是通行机制（Q9 全证）；② 阈值量级 ≫ 业务速率；③ 超限**显式拒绝**，从不静默 |
| **B2** | CME 断线删单（COD） | **T1** 交易所官方中文（S38） | 「断线时删单 (COD) 功能将为该用户取消所有当日剩余交易时段的期货和期权交易单，以保护市场参与者在**无法监控交易执行状况**的情况下保持持仓不受任何变动」 | 撤单可靠性是行业级课题 → 交易所提供**服务端撤单保障**；客户端逐单撤单不应被限流挤死（A5/A6 的交易所级外证） |
| B3 | 台湾期货公会《自动化交易风险控管最佳实务》 | T2 行业文件（S39） | COD 列为「交易前风险控管措施」标准项 | 撤单保障是最佳实践组件（Q12 行业依据） |
| **B4** | IB TWS API | **T1** 经纪商官方（S40） | 「order rate limitation of **50 orders per second**」；>50 msg/s → 警告并**可能断开**（message code 100，显式） | 限额 50/s ≫ 业务速率；超限显式化 |
| **B5** | vnpy 精英版 OrderFlowRule | T2 官方文档（S41） | 内部风控「委托流量限制」= 窗口内**委托笔数** + 日内总委托上限——**不含撤单** | **内部风控层（对应 D2 层）的行业口径 = 报单（R1）**；柜台合并额度由柜台同构的预算层建模 → 支撑本仓「统计层（内部）/预算层（柜台）」两层结构 |
| **B6** | vnpy S15 流控网关 | S15 原文 | 「如遇违反流控，让 CTP 网关**缓冲**报单请求和查询请求，延后执行；构造报单请求队列」 | 耗尽行为 = 缓冲延后（可观测），容量对齐柜台 6/s；非静默拒绝 |
| **B7** | Binance Spot API | **T1** 官方文档 | ① cancelReplace 失败 = **HTTP 409 显式部分成功语义**；② 提供「Cancel All Open Orders on a Symbol」**单请求批量撤单** | ① 撤单失败显式化是 API 设计标配（G15 外证）；② 急停 = 批量撤单单请求 → **Q12 新增选项 (iii)** |

### 18.2 综合结论（裁决 F-1）

1. **合并计量是交易所/柜台层的通行机制**（B1/B5/S21/S31）——Q9 的建模方向获行业全证。
2. **限额默认值全部远高于业务速率**：500/s（CME）/ 50/s（IB）/ 6/s（CTP 柜台典型）——**没有任何已知系统把「报单+撤单合计」压到 1 笔/秒**；(b) 无行业先例。
3. **超限行为全部显式**：Session Level Reject / logout / 警告断开 / HTTP 409 / 缓冲队列——**无一例静默返回**；本仓 `cancel() -> False` 静默失败（G15）与全行业相反。
4. **撤单可靠性有专门机制**（COD / 批量撤单 / kill，B2/B3/B7）——不在逐单限流里解决。
5. **内部风控层只数委托**（B5）：R1（D2 = 报单口径）与 vnpy 精英版同构；柜台合并额度交给柜台同构的预算层——本仓「统计层（内部）/预算层（柜台）」的两层切分因此获得行业同构佐证。

→ **证据裁决（2026-11-22）：F-1 = (a-修订)**——`order_flow_per_sec = 2 × internal_per_second`（每类型桶保留各 1/s、不设日上限）+ G15 显式化 + Q12 扩为三选项（**预留槽位 / bypass+audit / 批量撤单单请求**）。唯一保留调整通道：若券商实际配置 < 2 笔/s（罕见），经 `ChannelCapability` 下调——「可配置」正是 D2 的硬约束（A1）。

### 18.3 来源

S37/S38/S39/S40/S41 新登记入 §8；S15/S21/S23/S31/S32 复用既有条目。**未取证**：Binance ORDERS 限额是否计入撤单（docs 已迁移未直取）——不影响结论（B7 只引 409 语义与批量撤单端点，均为已直取正文的事实）。

---

## 19. 全量 Step 1：F7 服务层选型（FastAPI / WS / 鉴权 / TLS / 可观测性 / Redis，2026-11-22）

> 本节补齐 §1.1 中标注「否（全量 Step 1）」的六项能力；只做**选型与依据**，不写实现、不改代码。

### 19.1 三条基线更正（影响后续全部结论）

1. **D14「零新依赖」不是全局规则**：它是 P-053 批内设计决策（[DESIGN_p053#L550](DESIGN_p053_trading_gateway.md) / [IMPL_p053#L28](IMPL_p053_trading_gateway.md)），约束对象是 `live/`。总纲 §6 门禁明确写「**FastAPI/uvicorn 视部署进 `[services]`**」并列出 extra 分档 + `uv lock`——P-054 新增依赖是**总纲预设路径**，不构成对 D14 的违反。
2. **`redis` 已在 pyproject 声明**：[pyproject.toml#L45](../pyproject.toml#L45) `redis>=4.5.0`、[L35](../pyproject.toml#L35) `pydantic>=2.0.0`、[L42](../pyproject.toml#L42) `sqlalchemy>=2.0.0`。前文 **§3 G9 与 §7.2** 的「pyproject 无 redis」**错误**，更正为：**fastapi/uvicorn/websocket 未声明；redis/pydantic 已声明**（`redis` 当前无 .py 引用；`pydantic` 仍被 `core/config_v2.py` 使用，见 §19.3）。
3. **Python 基线是 3.10**：[pyproject.toml#L10](../pyproject.toml#L10) `requires-python = ">=3.10"`；CI 矩阵 3.10/3.11/3.12（[tests.yml#L16](../.github/workflows/tests.yml#L16)）。**FastAPI 上游当前要求 Python >=3.11**（master `requires-python=">=3.11"`；发布说明含「Drop support for Python 3.10」，该引句**无版本号**，见 S42 注），而 **0.139.2 仍要求 >=3.10**（PyPI）→ 本批第一个硬冲突（§19.3）。

### 19.2 依赖版本与兼容矩阵（2026-11-22 读取）

| 包 | 最新版本 | requires-python | 本批角色 | 建议 |
|----|----------|-----------------|----------|------|
| **fastapi** | 0.165.0 | 上游 master **>=3.11**；0.139.2 **>=3.10** | REST + WS 框架 | 见 §19.3 三选一 |
| **uvicorn** | 0.54.0 | **>=3.10** | ASGI server | `>=0.54.0`；**Windows 不可用 uvloop**（§19.4） |
| **redis**（redis-py） | 8.1.0 | **>=3.10** | Streams/PubSub 客户端 | 沿用已声明 `>=4.5.0`；asyncio 连接可用 |
| **prometheus-client** | 0.26.0（2026-07-25） | **>=3.9** | `/metrics` | `>=0.26.0`（官方客户端） |
| **pydantic** | 2.x（已声明 >=2.0.0） | >=3.9 | FastAPI 依赖 | 若采用新 FastAPI，需 `>=2.9.0`（上游 master 依赖） |
| **websockets** | uvicorn 可选依赖 | — | WS 协议实现 | 显式声明 `websockets>=12`，避免 `[standard]` 隐式解析 |

> 备注：FastAPI 上游 master 依赖还含 `opentelemetry-api>=1.44.0`——若采用最新版，会额外拉入 OTel API（即使不用 OTel）。这是 §19.3 选项 C 的隐性成本。

### 19.3 Python 3.10 冲突：三个选项（Q13）

| 选项 | 做法 | 优点 | 代价 |
|------|------|------|------|
| **A（已裁决）全局升 3.11** | 改 `requires-python=">=3.11"`，CI 去 3.10 | 依赖统一、可用最新 FastAPI；3.10 已 EOL（2026-10-01，S50） | 影响全部用户与既有基线；需全批回归，改动面最大 |
| B 锁旧 FastAPI | `[services]` 固定 `fastapi>=0.139.2,<0.140`（0.139.2 支持 3.10 已验证；**`<0.140` 上界未取证**——0.140.0 起是否要求 >=3.11 未验证，本轮 PyPI 直取失败） | 核心保持 3.10 | 锁旧版、失去后续修复；且 3.10 已 EOL，延长无收益 |
| C 服务层 3.11+ | `[services]` 声明 `fastapi>=0.165.0`，核心仍 3.10；CI services job 仅 3.11/3.12 | 核心不动 | 维护两套 Python 下限；3.10 EOL 后仍要迁 |

> **裁决（2026-11-22 用户确认）：A——全局升到 Python >=3.11**。依据：Python 3.10 已于 **2026-10-01 EOL**（S50）；FastAPI 上游要求 >=3.11（S42）；3.11 仍处 security 支持期（至 2027-10）。**实施影响（需单列一个小任务，不得在 Step 3 静默改）**：① `pyproject.toml` `requires-python=">=3.11"`、classifiers 去 3.10（可加 3.13）、`[tool.black] target-version` 去 py310、`[tool.mypy] python_version="3.11"`；② CI 矩阵 3.10/3.11/3.12 → **3.11/3.12**（可加 3.13）；③ 依赖 `fastapi>=0.165.0`、`pydantic>=2.9.0`——**pydantic 已被 [config_v2.py#L29](../core/config_v2.py#L29) 实际使用**（`BaseModel/Field/field_validator/model_validator`），升版回归范围必须包含 `core/config_v2` 相关测试；④ 既有 1300 测试在 3.11/3.12 重跑并更新基线文档；⑤ QMT `[qmt]` 独立 venv（可能 3.6/3.8）不受影响（D4 已隔离）。

### 19.4 FastAPI / uvicorn 运行模型

- ASGI + lifespan；**单 worker 是默认**，`--workers N` 是多进程、每进程独立内存（[uvicorn settings](https://www.uvicorn.org/settings/)）。
- **Windows/ uvloop**：uvicorn 原文「uvloop ... **not compatible with Windows or PyPy**」；`uvicorn[standard]` 是「install and use **if possible**」→ Windows 自动回退 asyncio。**F7 写的「uvicorn(uvloop)」在 Windows 开发机不可达**，必须写成「Windows=asyncio，Linux=uvloop（可选）」。
- 与本批相关的参数：`--limit-concurrency`（过载 503）、`--timeout-keep-alive`、`--ws-max-size`（默认 16MB）、`--ws-max-queue`（默认 32，**仅入站**）、`--ws-ping-interval/--ws-ping-timeout`（默认 20s/20s）、`--ssl-*`。
- **关键结论**：`--ws-max-queue` 只限制**入站**消息；**出站背压必须自建**（§19.5）。

### 19.5 WS 协议：snapshot + delta / seq / 心跳 / 背压

- **帧约定（建议）**：`{"type":"snapshot","seq":S,"data":{...}}` → `{"type":"delta","seq":S+n,"events":[...]}`；客户端重连带 `{"type":"resume","last_seq":S}`；服务端 `{"type":"error","code":"..."}`。
- **复用已有资产**：`EventLog` 已具备单调 `seq`、`read/replay/subscribe`、JSONL 持久化（[event_log.py#L112-L133](../core/event_log.py#L112-L133)、[L153-L193](../core/event_log.py#L153-L193)、[L236-L252](../core/event_log.py#L236-L252)）→ **snapshot+delta 的 seq 源不必新造**。
- **已知边界**：`EventLog._lock` 是 `threading.RLock`（[L123](../core/event_log.py#L123)），**仅进程内线程安全**；多进程同时写同一 JSONL 不安全 → 只有交易/账本进程可 append `EventLog`，API/WS worker 不写、只从 Redis 取事件（§21.2）。
- **重连语义**：`last_seq` 仍在可回放窗口 → 只补 delta；已滚出窗口 → 发新 snapshot（并标记 gap）。ring buffer 默认 500（[L115](../core/event_log.py#L115)），超出从磁盘 `read` 补。
- **心跳**：uvicorn 协议层 ping/pong（20s/20s）+ 应用层 `ping/pong`（客户端指数退避）。
- **背压**：每连接 `asyncio.Queue(maxsize=N)`；行情 delta 满 → 丢旧/合并（可丢）；订单/成交 → **不可丢**：阻塞等待或超时后断开慢客户端并计 `ws_dropped_orders`（绝不静默丢）。
- **慢客户端**：队列持续满 > T 秒 → `close(code=1013)` + 指标；重连走 snapshot。

### 19.6 鉴权（REST + WS）

- D2 已定「仅本机/内网」→ **API Key 优先**，JWT 预留（多用户/过期/轮换时再上）。
- REST：`APIKeyHeader(name="X-API-Key")`（FastAPI `fastapi.security`，[Security 文档](https://fastapi.tiangolo.com/tutorial/security/)）；比较用 `hmac.compare_digest`（stdlib，常数时间）；密钥从环境变量/密钥库注入，**禁止入库**；无 key→401，权限不足→403；CORS 仅白名单（本机默认关闭）。
- **WS 的浏览器约束**：浏览器 `WebSocket` 构造函数**不能自定义 Authorization header**（Starlette 只暴露 headers/query/subprotocols）。三选一：
  1. **一次性短时 ticket**（推荐）：REST 用 API Key 换 30s 有效 ticket，WS 用 `?ticket=`；
  2. `Sec-WebSocket-Protocol` 子协议携带（Starlette 官方示例即用 `subprotocols` 鉴权）；
  3. query 直接放长期 key（**不推荐**：进访问日志/代理日志）。
- 拒绝时机：在 `accept()` 前拒绝 → Starlette 默认 HTTP 403；需要 401 时用 `send_denial_response`/`HTTPException`（[Starlette WebSockets](https://www.starlette.io/websockets/)）。
- 握手失败限流独立于交易 FTD/order-flow 预算，避免认证攻击挤占交易额度。

### 19.7 TLS

- uvicorn 内置 SSL：`--ssl-keyfile` / `--ssl-certfile` / `--ssl-keyfile-password` / `--ssl-ca-certs` / `--ssl-cert-reqs` / `--ssl-ciphers`（默认 `PROTOCOL_TLS_SERVER`）。
- **本机 loopback**：TLS 可选（D2），但建议统一 `https/wss` 以免前端混用；**内网 LAN：必须 TLS**。
- 证书：内网自签或内部 CA；文件放仓库外、最小权限；轮换 = 重启 worker；密钥不落库（与总纲 S5 一致）。
- mTLS 可选：`--ssl-cert-reqs 2` + `--ssl-ca-certs`，适合多机内网。
- 反向代理（若未来加）：`--proxy-headers` + `--forwarded-allow-ips` 限定可信代理。

### 19.8 可观测性

- **指标**：`prometheus-client` 0.26.0（官方，[PyPI](https://pypi.org/project/prometheus-client/)）；`/metrics` 仅绑 loopback 或加鉴权。
- 最小指标集：`ws_connections`、`ws_queue_depth`、`ws_dropped_ticks_total`、`ws_dropped_orders_total`、`ws_send_latency_seconds`（histogram）、`outbox_pending`、`outbox_publish_failures_total`、`ftd_remaining`、`rate_denied_total{reason}`。
- **结构化日志**：stdlib `logging` + JSON formatter（零依赖）；字段 `ts/level/event/conn_id/seq/latency_ms`；禁止记录 key/token/证书口令。
- **延迟基准**：`time.perf_counter` 采样 p50/p95/p99，分三段：EventLog append→入队、入队→WS 发送、端到端（含客户端）。F7 的「5–50ms」是目标区间，不是保证（受 GIL/A股 3s 快照约束）。
- **告警**：队列深度、发送 p99、outbox 积压、FTD 耗尽 → 日志/IM；**不做 Grafana/Loki/Tempo 全栈**（总纲 §7.2 明确不做）。

### 19.9 Redis 取舍（F7 的核心裁决）

**结论先行（Q14 已裁决 Full）**：Redis 依赖已在 `pyproject`，拓扑已定为「单实例交易/账本进程 + N 个无状态 API/WS worker」，因此 Redis 不是可选项，而是**跨进程扇出的既定载体**：行情走 Pub/Sub、订单/成交走 Streams 单一消费组（处理后经 Pub/Sub 广播，§21.1）。本节价值在于固定两类消息的语义边界，避免把消费组当广播用。

两类消息必须分开（这与 F7「行情可丢、订单不可丢」同构）：

| 消息 | 语义 | Redis 原语 | 依据 |
|------|------|-----------|------|
| 行情 tick | 可丢、可合并 | **Pub/Sub** | 官方原文：Pub/Sub 是 **at-most-once**，「a message will be delivered once **if at all** ... forever lost」（[Redis Pub/Sub](https://redis.io/docs/latest/develop/interact/pubsub/)） |
| 订单/成交 | 不可丢 | **Streams 消费组 + XACK + XAUTOCLAIM** | at-least-once；PEL 支持重投；`XADD/XACK v5.0`、`XAUTOCLAIM v6.2`（[Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/)） |

**一个易错点**：消费组是**负载均衡**（同一消息只给一个消费者），不是广播；F7 要求「每个 worker 独立订阅」→ 行情用 Pub/Sub 广播；订单处理用**单一消费组**（只处理一次），处理完再 Pub/Sub 通知各 worker 推送。若用 Streams 做广播，需要每个 worker 一个独立 group（成本高、易漏）。

**裁决（2026-11-22 用户确认）：直接按 F7 全量多 worker 落地**（不做 Phase 0 单 worker 过渡）。因此以下架构约束成为 P-054 的**前置设计条件**（详见 §21）：

- 交易/账本进程必须**单实例**（SQLite `.lock` 单写者，G16）；
- API/WS worker **无状态**，不得各自创建 EventLog 写同一 JSONL（G17）；
- 行情走 Pub/Sub、订单/成交走 Streams 消费组；
- Redis 运行环境（Windows WSL2/Docker，S51）与 CI service/FakeBus 需先就绪。

Phase 0 仅作为**测试替身**（FakeBus + 单进程）保留，不作为交付拓扑；D-P054-1 改为「Full 拓扑 + 单写者进程拆分」。

### 19.10 方案对比

| 方案 | 组成 | 满足 F7 验收 | 风险 / 代价 |
|------|------|--------------|-------------|
| A Phase 0 单 worker（未采纳） | FastAPI+uvicorn 单进程；EventLog seq；SQLite outbox relay；Redis 接口预留 | ✅ seq / snapshot+delta / 401/403 / 延迟报告 | 被 Q14 裁决否决，仅保留为测试替身 |
| **B（已裁决）直接 F7 全量** | Redis Pub/Sub + Streams + N workers + 单实例交易/账本进程 | ✅ 且可扩展 | 需先解决 G16（单写者拆分）、G17（Windows Redis/CI）；运维与调试复杂度最高 |
| C stdlib-only（http.server） | 无 ASGI / 无 WS | ❌ 无 WebSocket | 直接否决 |

### 19.11 验收映射（F7 L232）

| F7 验收项 | 验收探针（Full 拓扑；Phase 0 仅 FakeBus 单测替身） |
|-----------|--------------|
| WS seq 连续 | 注入 100 条事件，断言客户端收到的 seq 无跳变、无重复（多 worker 下连不同 worker 交叉验证，§21.4） |
| snapshot+delta 重放一致 | 断开 → 带 `last_seq` 重连 → 重放后状态 = 全量重放状态 |
| 401 / 403 | 无 key / 错 key / 低权限三角色各一例 |
| REST 管理面可写但不含下单/撤单 | 路由清单审计 + 禁止 `submit/cancel` 依赖边 |
| 延迟基准报告 | 1k/10k 消息的 p50/p95/p99 + 慢客户端丢弃计数 |

### 19.12 新增来源（S42-S49）

| # | 来源 | Layer | 日期/版本 | 用途 |
|---|------|-------|-----------|------|
| S42 | [FastAPI PyPI 0.165.0](https://pypi.org/project/fastapi/) / [0.139.2](https://pypi.org/project/fastapi/0.139.2/) / [release notes](https://fastapi.tiangolo.com/release-notes/) | **T1** 官方 | 0.165.0；0.139.2（>=3.10）；「Drop support for Python 3.10」（**无版本号**，见 §8 S42 注） | Python 下限冲突（§19.3） |
| S43 | [uvicorn PyPI 0.54.0](https://pypi.org/project/uvicorn/) / [settings](https://www.uvicorn.org/settings/) | **T1** 官方 | 0.54.0（>=3.10） | uvloop 不支持 Windows；TLS/WS/并发参数 |
| S44 | [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) | **T1** 官方 | XADD/XACK v5.0、XAUTOCLAIM v6.2 | 订单可靠通道（消费组/PEL） |
| S45 | [Redis Pub/Sub](https://redis.io/docs/latest/develop/interact/pubsub/) | **T1** 官方 | at-most-once 原文 | 行情可丢扇出 |
| S46 | [prometheus-client 0.26.0](https://pypi.org/project/prometheus-client/) | **T1** 官方客户端 | 0.26.0（2026-07-25，>=3.9） | 指标 |
| S47 | [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) | **T1** 官方 | — | OpenAPI apiKey/bearer 方案 |
| S48 | [Starlette WebSockets](https://www.starlette.io/websockets/) | **T1** 官方 | — | subprotocol 鉴权、close/disconnect、denial response |
| S49 | [redis-py PyPI 8.1.0](https://pypi.org/project/redis/) | **T1** 官方客户端 | 8.1.0（>=3.10，含 async 连接） | 客户端能力/版本 |

### 19.13 新增裁决点（Q13-Q17）

| ID | 决策 | 建议 |
|----|------|------|
| Q13 | Python 下限：全局 3.11 / 锁旧 FastAPI / 服务层 3.11+ | **已裁决：全局升 3.11**（§19.3） |
| Q14 | Phase 0 单 worker vs 直接 F7 全量多 worker | **已裁决：直接 F7 全量多 worker**（§20.6/§21，2026-11-22 用户确认） |
| Q15 | 鉴权：API Key / JWT / 两者 | **已裁决：API Key 优先，JWT 预留**（§22.4） |
| Q16 | TLS 范围：loopback 是否强制 | **已裁决：TLS 全启用（含 loopback）**（§22.5） |
| Q17 | 可观测性：prometheus-client vs 手写 `/metrics` | **已裁决：prometheus-client + 四黄金信号**（§22.6） |

---

## 20. Q14 专项：Phase 0 单 worker vs F7 全量多 worker（2026-11-22）

> 回应「调研一下，补充裁决依据」。只比较两条**拓扑**，不重复 §19 的选型细节。

### 20.1 两条路线

- **Phase 0（单 worker）**：1 个 uvicorn 进程；`EventLog` 提供 seq/snapshot/delta；每连接有界 `asyncio.Queue`；订单/成交走 SQLite outbox relay；**运行时不需要 Redis 服务**。
- **F7 Full（多 worker）**：N 个 uvicorn worker；行情走 Redis **Pub/Sub** 广播；订单走 Redis **Streams 消费组 + XACK/XAUTOCLAIM**；连接/订阅状态入 Redis。

### 20.2 外部锚点

| # | 锚点 | 关键事实 | 对本问题的指向 |
|---|------|----------|----------------|
| **S51** Redis on Windows | 官方原文：「Redis is **not officially supported on Windows**」；需 WSL2 才能装 | 本机是 Windows：Phase 1 会把「装 Redis」变成 WSL2/Docker 的运维前置 |
| **S52** WebSocket.org FastAPI 指南 | 「Uvicorn workers are **separate OS processes with isolated memory**」；内存 `ConnectionManager` 只知道本 worker 的连接；跨 worker 广播必须加 **Redis pub/sub**，约 **+1ms** | Full 的 Redis 不是可选优化，而是多 worker 广播的**必要组件**；但只增加约 1ms |
| **S43** uvicorn settings | `--workers N` 是多进程；默认 1 | Full 的进程模型与 Phase 0 不同 |
| **F7 L228**（仓内） | 「GIL 下事件循环只做解析+入队」；「A股 Level-1 快照本身 **3s 一笔**」 | 端到端新鲜度由数据源决定；Redis 的 +1ms 不是瓶颈 → **Redis 不能显著改善延迟** |
| **ledger_store.py L49-51**（仓内） | 单写者 `.lock` 用 `O_CREAT\|O_EXCL`；第二实例直接失败 | N 个 worker **不能各自持有账本**；Full 必须拆出「单一交易/账本进程」+ N 个只读 WS worker，架构改动更大 |
| **event_log.py L123**（仓内） | `threading.RLock`，仅进程内线程安全；JSONL 追加无跨进程锁 | Phase 0 单 worker；Full 不能让多进程共写同一 JSONL |

### 20.3 对比矩阵

| 维度 | Phase 0 单 worker | F7 Full 多 worker |
|------|-------------------|-------------------|
| 部署依赖 | 无额外服务（Windows 直接跑） | Redis 服务（Windows 需 WSL2/Docker，S51） |
| 端到端延迟 | 无总线跳数 | +≈1ms（S52），相对 A股 3s 快照可忽略（F7 L228） |
| 故障模式 | 单进程重启，客户端重连走 snapshot | Redis 故障 = 广播中断；需额外健康检查/重连 |
| 水平扩展 | 仅纵向（单进程） | N worker 横向扩展 |
| 与现有 SQLite 单写者 | **天然兼容**（单写者） | **不兼容**：需拆出独立交易/账本进程 |
| 实现成本 | 复用 EventLog/outbox；新增 WS 层即可 | 新增总线抽象、消费组、PEL/claim、Redis 运维与测试 |
| F7 验收覆盖 | ✅ seq / snapshot+delta / 401/403 / 延迟报告 | ✅ 同上，另需多 worker 一致性测试 |
| 与 D2（自用/本机） | 高度一致 | 有张力（多一个常驻服务） |

### 20.4 证据结论

1. **Full 的唯一独占收益是「横向扩展/多机」**；F7 验收项与 D2 自用定位都**不要求**它。
2. **Full 的代价不只是 +1ms**：Windows 需要 WSL2/Docker（S51）、需要拆出单写者进程（ledger `.lock`）、需要消费组/PEL 运维与测试。
3. **Phase 0 不牺牲延迟**：A股 L1 本身 3s（F7 L228），单进程事件循环足够做「解析+入队+扇出」。
4. **Phase 0 的主要风险是单点故障**，但自用工具可接受：进程重启 + 客户端 snapshot 重连即可恢复；这是可测试、可观测的已知风险，而非隐性缺陷。
5. **升级路径可控**：只要在 Phase 0 就定义 `EventPublisher`/`MarketBus` 接口（进程内实现），Phase 1 换成 Redis 实现是机械替换。

> **初始建议（证据指向）：Q14 = Phase 0 单 worker**（**已被 §20.6 用户裁决推翻：改为 Full**）；Phase 1 触发条件 = ① 单进程 CPU 饱和/需要 `--workers>1`；② 行情网关独立进程；③ 跨机/多用户；④ 需要 HA；⑤ 运行环境已有 Redis（WSL2/Docker/Linux）。若你明确近期就要多机/多用户，则可直接选 Full——但需同时接受「拆单写者进程 + Redis 运维」的额外范围。

### 20.5 Q14 状态

**调研时结论：证据指向 Phase 0；用户最终裁决见 §20.6 = Full。** Phase 0 仅保留为 FakeBus 测试替身；Step 3 DESIGN 按 §21 的 Full 架构约束编写（单实例交易/账本进程 + N 无状态 API/WS worker、EventLog 写入唯一化、Redis 运行与 CI）。

### 20.6 用户裁决（2026-11-22）：Full

尽管 §20.4 的证据指向 Phase 0，用户选择**直接 F7 全量多 worker**。该选择与 F7 原文一致，但推翻本节倾向，并**引入三个必须先解决的硬约束**：

1. **SQLite 单写者**（G16，P1）：第 2 个 worker 在 `.lock` 处启动失败 → 必须拆「单实例交易/账本进程 + N 个无状态 API/WS worker」，或让 store 支持只读模式（跳过 `.lock`）。
2. **EventLog 多进程**（G17）：不得让多个 worker 各自写同一 JSONL → 事件写入只能由单实例完成，worker 只读 Redis/快照。
3. **Windows Redis**（G17）：官方不支持 Windows，需 WSL2/Docker；CI 需 Redis service 或 FakeBus。

Q14 状态改为「已裁决：Full」；D-P054-1 改为「Full 拓扑 + 单写者进程拆分」；Phase 0 仅保留 FakeBus 测试替身。

---

## 21. Q14 裁决后的架构约束（Full 多 worker，2026-11-22）

### 21.1 目标拓扑

```
[trading/ledger process 单实例]
  ├── SQLite（唯一写者，.lock）
  ├── EventLog append（唯一写入者）
  ├── outbox relay（唯一实例）
  │     └── XADD 订单/成交事件 → Redis Streams（at-least-once，PEL 可重投）
  ├── Streams 消费组：**唯一消费者**（可靠投递/分发；XACK / XAUTOCLAIM）
  │     └── 处理完成后 PUBLISH 订单/成交事件 → Redis Pub/Sub
  └── 行情 tick：PUBLISH → Redis Pub/Sub
              │
              └──> [API/WS worker × N]（无状态：只订阅 Pub/Sub + 只读 SQLite）──> 浏览器
REST 管理面读路径：同机只读 SQLite（WAL，mode=ro/query_only）；跨机走交易进程内部 API
```

> **扇出路径唯一化（F-R2-1 修复）**：Streams 消费组只负责「恰好一个消费者处理一次」，**不承担广播**；订单/成交事件与行情一样，最终都经 **Pub/Sub** 扇出到全部 worker。若让消费组直连 worker，连在其它 worker 的客户端将收不到订单事件，§21.4 跨 worker 广播一致性验收不可达（消费组=负载均衡，§19.9）。

### 21.2 三个硬约束（设计前置）

1. **G16 单写者拆分（P1）**：`SqliteLedgerStore` 的 `.lock` 用 `O_EXCL`（[L49-L51](../live/ledger_store.py#L49-L51)），只能一个进程写；`--workers N` **不能**让每个 worker 都 new store。必须：① 单实例交易/账本进程持有写连接；② 或给 store 增加 `read_only=True`（跳过 `.lock`，WAL 多读者）；③ API worker 不得实例化 writer。
2. **G17 事件写入唯一化**：`EventLog._lock` 仅线程级（[L123](../core/event_log.py#L123)），JSONL 无跨进程锁；只有交易进程可 append，worker 通过 Redis Pub/Sub 与只读 SQLite 获取事件，不写 EventLog。
3. **G17 Redis 运行环境**：Windows 需 WSL2/Docker（S51）；CI 需 `services: redis`（Ubuntu）或 FakeBus 单测；本地启动脚本必须显式检查 Redis 可用性并在 `/health/ready` 反映。

### 21.3 裁决点（已于 §22 裁决）

| ID | 决策 | 说明 |
|----|------|------|
| Q18 | 交易/账本进程与 API worker 的拆分方式 | 独立进程（推荐，静态角色） vs leader worker（Redis 锁选举） |
| Q19 | REST 管理面读路径 | 只读 SQLite（WAL） vs 内部 API 代理 vs Redis 快照（最终一致） |
| Q20 | Windows Redis 运行方式与 CI 方案 | Docker Desktop / WSL2 / Memurai；CI 用 Redis service 或 FakeBus |

> **§22 已裁决**：Q18 = 独立交易/账本进程 + N 无状态 worker；Q19 = 同机只读 SQLite / 跨机内部 API；Q20 = Docker Desktop(WSL2) + CI `services: redis` + FakeBus。依据 S51/S53/S54/S55/S56。

### 21.4 验收影响

- **多 worker 启动测试**：第 2+ worker 不得触碰 writer / EventLog 写路径（启动即断言）。
- **跨 worker 广播一致性**：客户端连不同 worker，收到同一 seq 序列（无重复/无跳变）。
- **Redis 故障降级**：Pub/Sub 断线重连、Streams pending 重投、`/health/ready` 反映。
- **CI**：Ubuntu 加 Redis service 或 FakeBus 单测；Windows 本地用 Docker/WSL2 并在文档写明。
- F7 原验收项不变，测试矩阵扩大。

### 21.5 与 F7 的关系

F7 原文要求多 worker + Redis，本裁决**完全对齐**；新增的是 F7 未展开的「单写者拆分」与「Windows Redis」两项工程约束——这不是对 F7 的偏离，而是把 F7 落到本仓代码事实上的必要条件。

---

## 22. 剩余裁决缺口：外部/学术证据与裁决（2026-11-22）

> 覆盖 G16/G17、Q18/Q19/Q20、Q15/Q16/Q17、Q12；Q5/Q6/Q7 仅确认「依据已足」，数值留 Step 3。

### 22.1 G16 / Q18：单写者与进程拆分

**外部/学术锚点**：

- **S54（Helland, CIDR 2007）**：「An entity lives on a **single machine at a time** and the application can only manipulate one entity at a time」「**Atomic Transactions Cannot Span Entities**」→ 订单/账本作为实体，天然应**单一所有者**。
- **S53（SQLite WAL）**：「readers do not block writers and a writer does not block readers」→ 允许「单写者 + 多读者」；但仍是**一个写事务**（S2）。
- **S55（Fowler CQRS）**：读写模型可以分离，且「may share the same database」→ 读侧不必复制一套 Redis 模型。

**裁决 Q18 = 独立交易/账本进程（静态角色）+ N 个无状态 API/WS worker**：

1. 交易/账本进程唯一持有 `SqliteLedgerStore` 写连接、唯一运行 outbox relay、唯一 append `EventLog`。
2. API/WS worker 只读：REST 走只读 SQLite（§22.3），WS 只订阅 Redis。
3. **不用 leader election/Redlock**：自用、静态部署，进程角色由启动参数决定即可；引入分布式锁只增加故障面（Helland 的实体所有权也不需要租约）。
4. G16 处置：P1 → **已缓解**（不是让多 worker 抢锁，而是从架构上只允许一个写者）。

### 22.2 G17 / Q20：Windows Redis 与 CI

**外部锚点**：

- **S51**：Redis「not officially supported on Windows」，需 WSL2。
- **S56**：GitHub Actions `services:` 可起 Redis 容器，但**必须 Linux/Ubuntu runner**；示例 `redis` + `6379:6379`。

**裁决 Q20 = 本地 Docker Desktop（WSL2 backend）+ `redis:7`；CI 用 Ubuntu `services: redis:7`；单测用 FakeBus**：

1. 本地：Docker Desktop 的 WSL2 backend 跑 `redis:7`（不引入 Memurai 等第三方分支，避免行为差异）。
2. CI：在 Ubuntu job 加 `services.redis`（S56），集成测试连 `localhost:6379`。
3. 单测：定义 `EventPublisher`/`MarketBus` Protocol，默认 `FakeBus`（进程内），Redis 实现仅在 `@pytest.mark.redis` 集成测试使用——满足 D4「无外部依赖也能跑」。
4. G17 处置：P2 → **已缓解**（运行方式与 CI 方案确定；Windows 本地前置写入 README/runbook）。

### 22.3 Q19：REST 管理面读路径

**外部锚点**：

- S53 WAL：读不阻塞写、写不阻塞读 → 同一 SQLite 上「单写者 + 多只读连接」可行。
- S55 CQRS：可共享同一数据库；但**警告** CQRS 对多数系统增加风险与复杂度，只应用于局部。

**裁决 Q19 = 同机优先「只读 SQLite」，跨机用内部 API；不建 Redis 读模型**：

1. API worker 以 `mode=ro` 打开同一 SQLite（`PRAGMA query_only=ON`），**跳过 `.lock`**；读到的是一致的 WAL 快照。**前提已取证（S62/S63）**：WAL 只读需满足「`-shm`/`-wal` 已存在且可读」或「数据库目录可写（可创建 `-shm`/`-wal`）」或「数据库 immutable」三者之一；本仓交易进程持续写入 → **禁用 `immutable=1`**（官方警告错误结果/损坏），按「同机、同用户、目录可写」前提部署并做启动 preflight；前提不成立则退回本条 2 的「内部只读 API」。另：WAL wal-index 在共享内存，官方明确「所有读者必须同机」「不支持网络文件系统」（S62 §2.2），故跨机一律内部 API。详见 [RESEARCH_p054_risk_anchors §2](RESEARCH_p054_risk_anchors.md)。
2. 若未来 API worker 跨机：由交易进程暴露**内部只读 API**（鉴权 + 限流），不让远端直接挂 SQLite 文件。
3. 不采用「Redis 快照作为管理面真相源」：会引入最终一致性与双写；CQRS 的复杂度警告（S55）不支持为自用管理面这样做。
4. 验收：读接口返回的 `seq` 必须 ≥ 请求前已提交的 seq（read-your-writes 由同一 WAL 保证）。

### 22.4 Q15：鉴权

**外部锚点**：

- S57：API Key 要**每个受保护请求**都带；过量返回 **429**；可撤销；**不得仅依赖 API Key 保护高价值资源**。
- S58：若启用 JWT，必须做算法验证、issuer/audience 校验、不信任未验证 claims。

**裁决 Q15 = API Key 优先（`X-API-Key` + `hmac.compare_digest`），JWT 预留**：

1. REST：`APIKeyHeader`；key 从环境/密钥库注入，禁止入库；失败 401/403；认证失败 429 限流。
2. WS：**短时一次性 ticket**（REST 换取，30s，单次使用）或 `Sec-WebSocket-Protocol`；禁止把长期 key 放 query。
3. JWT 仅在「多用户/需要过期与细粒度 scope」时启用，启用即按 RFC 8725 全量校验（alg allowlist、iss/aud、exp）。
4. 自用本机/内网 + TLS + API Key 满足 S57 的「不单独依赖 API Key」精神（叠加了网络边界与 TLS）；若暴露到更大网络，必须加 mTLS 或 JWT。

### 22.5 Q16：TLS

**外部锚点**：

- S59：「Use TLS For All Pages」；TLS 1.3 默认、TLS 1.2 兼容；**TLS 1.0/1.1 必须禁用**；证书与私钥强保护。

**裁决 Q16 = 默认全启用 TLS（含 loopback），TLS 1.3 优先/1.2 兼容**：

1. LAN 必须 TLS；loopback 也默认 TLS（自签/本地 CA），避免前端出现 `http`/`https` 两套路径。
2. 仅允许显式配置 `--allow-plaintext-loopback`（且必须绑定 `127.0.0.1`）作为开发便利；该配置写入启动日志与 `/health`，视为风险接受。
3. 禁用 TLS 1.0/1.1；私钥文件仓库外、最小权限；轮换 = 重启；mTLS 可选（`--ssl-cert-reqs 2`）。
4. 与 S57 的组合：TLS + API Key + 本机/内网边界，三者叠加而非单点。

### 22.6 Q17：可观测性

**外部锚点**：

- S61：四黄金信号 = **latency / traffic / errors / saturation**。
- S60：online-serving 关键指标 = 请求数、错误、延迟 + in-progress；计数口径统一（建议按结束计）。

**裁决 Q17 = prometheus-client + 四黄金信号 + 领域指标；JSON 结构化日志；不上 Grafana 栈**：

1. 黄金信号映射：HTTP/WS 请求数（traffic）、错误码（errors）、发送/处理延迟 histogram（latency）、队列深度/连接数（saturation）。
2. 领域指标：`outbox_pending`、`ftd_remaining`、`rate_denied_total{reason}`、`ws_dropped_ticks_total`、`ws_dropped_orders_total`。
3. 日志：stdlib `logging` + JSON；禁止记录 key/token/证书口令。
4. 延迟基准：p50/p95/p99 分段（append→入队、入队→发送、端到端）；F7 的 5–50ms 为目标区间，不是保证。

### 22.7 Q12：kill-switch 预算语义

**外部锚点**（复用既有）：

- RTS 6 Art.12：kill 要求**立即撤下全部**未成交订单（P-052 §4.4）。
- S38 CME COD：断线时交易所**替用户撤全部单**。
- B7 Binance：提供「Cancel All Open Orders」**单请求批量撤单**；撤单失败显式 409。
- S21/S30：CTP 撤单仍受柜台报单流控/FTD **物理限额**，无法真正 bypass。

**裁决 Q12 = 「撤单优先通道 + 显式失败」，不绕过物理限额**：

1. order-flow 预算内为撤单保留**至少 1 个槽位/秒**（`reserve_cancel=1`）；kill-switch 的撤单优先于新报单。
2. kill-switch 逐单 `ReqOrderAction`；预算耗尽时**排队并记录 deferred**，绝不静默丢弃（G15 必须修复：audit + 原因）。
3. 不宣称「立即全部撤完」——物理上受 CTP 流控；对外报告 `requested/submitted/deferred` 三个数。
4. 若未来 CTP 提供批量撤单，再升级为单请求（对齐 B7）。

### 22.8 Q5 / Q6 / Q7：依据已足，留 Step 3 数值

| 项 | 已有依据 | 状态 |
|----|----------|------|
| Q5 退避参数 | S3/S4（Full Jitter）+ S28（tenacity 精确公式） | 依据足；数值（初始/倍率/封顶/次数）Step 3 定 |
| Q6 部分失败降级 | 订单/成交 fail-closed；positions → 降级态（§5.4） | 语义已定；错误码/健康态映射 Step 3 定 |
| Q7 巡检共用调度器 | S18（持仓 6s 轮询）+ S16/S17（1/s + 单在途） | 结论已定：共用；间隔 Step 3 定 |

### 22.9 裁决汇总

| 项 | 裁决 |
|----|------|
| G16 / Q18 | 单实例交易/账本进程 + N 无状态 API/WS worker；不用 leader election |
| G17 / Q20 | 本地 Docker Desktop(WSL2) + `redis:7`；CI Ubuntu `services: redis`；单测 FakeBus |
| Q19 | 同机只读 SQLite（`mode=ro`/`query_only`）；跨机内部 API；不建 Redis 读模型 |
| Q15 | API Key + `hmac.compare_digest`；JWT 预留（RFC 8725）；WS 短时 ticket/子协议 |
| Q16 | TLS 全启用（含 loopback），TLS1.3/1.2；明文仅显式 loopback 风险接受 |
| Q17 | prometheus-client + 四黄金信号 + 领域指标；JSON 日志；不上 Grafana |
| Q12 | 撤单优先通道 + 保留槽位 + 显式 deferred；不绕过 CTP 物理限额 |
| Q5/Q6/Q7 | 依据已足，数值/映射留 Step 3 |
