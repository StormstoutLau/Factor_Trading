# REVIEW：P-054 Step 2 异构复审（RESEARCH_p054_service_layer）

> **批次**: P-054 · **Step 2 复审** · 日期 2026-11-22
> **复审对象**: [RESEARCH_p054_service_layer.md](RESEARCH_p054_service_layer.md)（一轮：§0-§16 约 725 行；**二轮：§19-§22 全量 Step 1 与全部裁决，见 §8**）
> **复审基座**: **GLM-5.3-Flash** ≠ 作者 **DeepSeek-V4.1-Flash**（异构成立，RULE-5；两轮均异构）
> **方法**: E3 代码锚点全量重放 + 外部锚点独立抽检（新路径直取全文，不经作者检索路径）+ 口径保真核对 + 内部一致性扫描 + 反向证据检查
> **仓库时点**: 工作区含 RESEARCH + PROGRESS 更新（未提交）；代码基线 = P-053 关闭态 `a67a26b`
> **一轮结论**: **0 P1 / 1 P2 / 6 P3** —— 有条件通过；F-1（裁决内部矛盾）修复前不得进入 Step 3（门禁 b）
> **二轮结论（§8）**: **0 P1 / 2 P2 / 5 P3** —— 有条件通过；F-R2-1/F-R2-2 修复前不得进入 Step 3
> **修复与关闭（§8.7 回执 / §9 定点复验）**: F-R2-1~F-R2-7 复核 7/7 属实并已修复；§9 异构定点复验通过（0 P1/P2，2 P3：1 顺手修正 + 1 登记）→ **Step 2 关闭（2026-11-22）**

---

## 1. 复审范围

| 维度 | 核对内容 | 结果 |
|------|----------|------|
| 事实性 | 外部锚点可回放、无幻觉（S1-S36 抽检） | §3 |
| 代码实证 | §2 表 21 行 + G1-G14 + §15.7 计数的 file:line 重放 | §2，**21/21 属实** |
| 边界 | P-053 已关闭契约不改写；D14 零依赖；D2/D4/D16 引文保真 | §4 |
| 一致性 | 编号（G/Q/S/§）、计数、跨节引用、RESEARCH↔PROGRESS 同步 | §5 |
| 可行性 | §13.2 暴露矩阵算术、§16 迁移方案、§15 边界自洽 | §2/§5 |

---

## 2. 代码锚点重放（E3，21/21 属实）

| # | RESEARCH 声称 | 重放结果 |
|---|---------------|----------|
| 1 | `LedgerStore` Protocol 8 方法 + `transaction()`（[ledger_store.py L31-40](../live/ledger_store.py#L31-L40)） | ✅ 逐字命中 |
| 2 | `transaction()` = `BEGIN IMMEDIATE`/COMMIT/ROLLBACK（L140-148） | ✅ 命中 |
| 3-6 | `append_entry`/`upsert_order`/`append_outbox` 各自 `with self.transaction()`；`append_outbox` 用 `INSERT OR IGNORE`；`pending_outbox`/`mark_sent` 已实现 | ✅ 四行全命中（L63-82/L93-108/L121-126/L128-136） |
| 7 | `apply_fill` 写 fill+fee 两条分录（[ledger.py L96](../live/ledger.py#L96)、`_seen.add` L116） | ✅ 命中 |
| 8 | `_append` 逐条 `store.append_entry`（L260-262） | ✅ 命中 |
| 9 | submit ⑧ `upsert_order`→`_audit`→`append_outbox`（L266-274），`event_id=uuid.uuid4().hex` L270 | ✅ 逐行命中（G6 行号精确） |
| 10-13 | `_apply_order_report`（L339-353）/`cancel`（L397-399）/`confirm`（L453-456）均 `upsert_order`+`_audit` **无 outbox**；poll 成交 L286-288 无 outbox | ✅ 四处重放，确认零 `append_outbox` 调用 |
| 14 | `start()` 恢复序 L145-153：2 次 `_throttle_query` + reconcile 第 3 次 | ✅ 命中 |
| 15 | `_throttle_query` check 失败直接 raise（L355-361） | ✅ 命中 |
| 16 | `_query_config.max_per_second = int(max(1, round(query_per_sec)))`（L120-123） | ✅ 命中 |
| 17 | CTP `max_query_per_sec=1.0`（L61）；能力 `10.0/20000/10.0/1.0`（L58-61） | ✅ 精确命中 |
| 18 | `-2/-3` → `ChannelUnavailable`（L82/L97） | ✅ 命中 |
| 19 | mock `max_query_per_sec=10.0`（L61） | ✅ 命中 |
| 20-21 | `check_rate` 只查当前秒桶 / `record` 保留近 2 秒桶（[compliance.py](../core/compliance.py#L101-L137)） | ✅ 命中 |
| 补 | §15.7「check_rate 4 处调用点 / 2 模块」（gateway L199/L358/L385 + safety_gate L170）；「6 测试文件 / 38 处引用」 | ✅ Grep 实测一致 |
| 补 | §13.2 暴露矩阵算术（internal 1/2/3/4/6/10 → 3/5/7/9/13/21 FTD/s） | ✅ 算术无误 |
| 补 | 基线读数 pytest 1300 / mypy 141 / black 283 等 | E1 存档（CHECKLIST 口径），本复审未重跑（工作区脚本不执行） |

---

## 3. 外部锚点独立抽检（不经作者检索路径）

| # | 锚点 | 抽检方式 | 结果 |
|---|------|----------|------|
| 1 | **S1** microservices.io Transactional Outbox | 复审会话 WebFetch 直取全文 | ✅ 「Messages are guaranteed to be sent **if and only if** the database transaction commits」「consumer must be **idempotent**, perhaps by tracking the IDs」逐句命中。**增益发现**：原文同时要求「Messages must be sent **in the order** they were sent by the service…preserved across multiple service instances that update the same aggregate」→ 该顺序义务在 S1 内**本就存在**，§16 引 Debezium 作顺序锚点之外可加引 S1（强化，非缺陷） |
| 2 | **S2** SQLite Transaction | 复审会话 WebFetch 直取全文 | ✅ 「Transactions created using BEGIN...COMMIT **do not nest**…An attempt to invoke the BEGIN command within a transaction **will fail with an error**」+「only one simultaneous write transaction」逐句命中；页面更新日 2026-02-18 与 S8 表一致。G1（P1）双源成立（S2 + 仓内代码） |
| 3 | **S33/S34** SQLite AUTOINCREMENT/VACUUM | 会话内 fetch 正文比对 | ✅ 「ROWIDs from previously deleted rows **might be reused**」「**monotonically increasing**」「VACUUM **may change the ROWIDs** of entries in any tables that do not have an explicit INTEGER PRIMARY KEY」逐句命中（引文与 fetch 原文一致） |
| 4 | **S30** CTP ReqOrderAction 返回码 | 检索快照回放（ctpdoc 6.5.1 镜像） | ✅ 「-2，表示未处理请求超过许可数；-3，表示每秒发送请求数超过许可数」——支撑 §13.4-2 更正（`-2/-3` 为 API 通用码） |
| 5 | **S35/S36** Debezium / Stripe | 会话内 fetch 正文比对 | ✅ Debezium「important for maintaining correct order」；Stripe「**errors if they're not the same**」逐句命中 |
| 6 | S21/S15/S16/S22（CTP 流控） | 链接级抽检 + 快照回放 | ✅ 口径一致（FTD 全接口、6/s 常见默认、查询 1/s、报单+撤单合并）；全文重放留待 Step 3 引用时复核 |
| 7 | S24-S29（上游源码） | 会话内 raw 直取正文比对 | ✅ §14.6 行号（L199-207/L209-212/L402-415）与 fetch 正文精确一致；§14.4 tenacity 公式与 L173-191/L210-213 一致（±1 行，不算偏差） |

**无幻觉**：抽检的 7 组锚点全部可回放，引句与原文一致。

---

## 4. 口径保真核对（不得重开已裁决项）

| 项 | RESEARCH 引文 | 判定 |
|----|---------------|------|
| D2 | §1.3「自用工具 + 程序化报备；默认 ≤1 笔/秒、≤1000 笔/日；API/WS 仅本机/内网」 | ✅ 一致；§15.2-2「不改默认 max_per_second=1」未重开 |
| D4 | §1.3「synthetic fixture + golden；禁外部阻断」 | ✅ 一致；§15.5 测试矩阵全 fake clock，符合 |
| D16 | §1.3「outbox 本批只写不读，送达循环归 P-054」 | ✅ 一致；relay 归 P-054 未越界 |
| D14 | §12.4-5 / §14.4「零新依赖，自实现等价逻辑」 | ✅ 全文无引入 fastapi/redis/tenacity/pyrate-limiter 的主张 |
| P-053 契约 | §15.3-2「不合并两个 RateLedger，保留 cancel_ratio 口径」；§15.2-1「不改统计层语义」 | ✅ 未改写 P-053 已关闭实现；G13 的「预算层（发送前）/统计层（成功后）」两层切分是**新增层**而非改写 |
| 总纲 F7 | §1.1 表「覆盖/不覆盖」逐项标注 | ✅ 无越权覆盖；Redis 取舍显式留全量 Step 1（§7.2） |
| 裁决回写 | Q8/Q9/Q10（§15）/Q11（§16.6）均标「已裁决」并注明 2026-11-22 用户确认 | ✅ 与本会话用户指令一致 |

---

## 5. 发现（0 P1 / 1 P2 / 6 P3）

| ID | 级别 | 发现 | 证据 |
|----|------|------|------|
| **F-1** | **P2** | **§15 内部矛盾：order-flow 默认值 vs 默认路径回归声明**。§15.3-1 规定 order-flow 共享预算「默认 = 内部 `max_per_second`（1/s）」且 submit/cancel 都先 reserve → 同秒 1 报 + 1 撤的第 2 笔必被 `rate_order_flow` 拒绝；但 §15.5-2 声称「默认 1/s 下 FTD 与 order-flow **均不改变**现有 `SubmitResult`/`cancel()` 结果」，且 §15.5-1 探针自己就预期「同秒 1 submit + 1 cancel → 第 2 笔 `rate_order_flow`」——探针与回归声明互斥。PROGRESS §3.61 同句「默认路径行为不变…order-flow 均不拒绝」同样失真。二选一待裁决：(a) order-flow 默认 = **2×internal**（1 报+1 撤），保留现状，D2「≤1 笔/秒」重释为「报单 ≤1/s」；(b) 默认 = internal（1/s），承认**有意行为变更**并修订 §15.5-2。另：order-flow 预算是否设日上限未定义（现 cancel 桶无日上限） | [RESEARCH §15.3-1 vs §15.5-1/2](RESEARCH_p054_service_layer.md)；PROGRESS §3.61 |
| F-2 | P3 | **计数失同步（RESEARCH↔PROGRESS）**：PROGRESS §3.61 交付行仍写「§0 十条结论」（实为 11 条）、「§2 代码现状 17 条 E3 实证」（实表 **21 行**）、「§8 来源 S1-S29」（实为 S1-S36）；§7.1「必须由 P-054 承接的两项改造」在 §15/§16 裁决后实为**四项**（+通道流控前置包、+outbox seq/inbox 迁移），§0 第 7 条「两条硬输入」同理 | PROGRESS §3.61；RESEARCH §2/§7.1/§0-7 |
| F-3 | P3 | **G14/G6 处置建议未随 §16 更新**：§3 G14 行仍写「`ORDER BY created_ts, rowid` + `(sent, created_ts)` 索引」，而 §14.8 已降级其为「零迁移退路」、§16.4 已裁决 `seq AUTOINCREMENT` + `(sent, seq)`；G6 行「`order:{coid}:accepted`」缺 §16.5 的 `:v{n}` 版本化（兼容但欠精确） | §3 vs §14.8/§16 |
| F-4 | P3 | **「五处/六处源码」口径不一**：§0-10 与 §11 写「五处上游源码」，§14.10 写「六处源码」——S24-S29 为 **5 库 6 文件**（PyrateLimiter 贡献 2 文件）。建议统一为「5 库 6 文件」 | §0-10/§11 vs §14.10 |
| F-5 | P3 | **§8 多源校验注未纳入后补强锚点**：仍写「CTP 流控（S8+S6+S7）」，未含 S21（官方镜像）/S30（返回码更正）/S31-S32（监管 T1）；该注是「≥2 独立 + ≥1 T1」的正式声明，应更新 | §8 末注 |
| F-6 | P3 | **Q2 登记滞后**：§10 Q2 仍标「P-054 Step 3 设计」，但 §16.5 已给出完整 event_id 规则（格式/冲突语义/inbox）且 Q11 裁决（用户确认）明确覆盖「event_id 版本化规则」。Q2 应改为「格式与冲突语义已由 §16.5 裁决；payload 细节归 Step 3」 | §10 vs §16.5 |
| F-7 | P3 | **Q3 被隐含裁决但未登记**：§16.6「与 U-P053-17 的 store 改造**同一次迁移**完成」预设了 Q3（组合写入口落点）= P-054 批内，但 §10 Q3 仍标「用户/Step 3 裁决」。建议显式登记「Q3 随 Q11 裁决默认 P-054 批内，待用户追认」或保持 open 并注明依赖关系 | §10 vs §16.6 |

**正向增益（不构成缺陷）**：S1 原文即含「同 aggregate 顺序保持」义务，可补强 §16 的顺序锚点（§3 表 #1）。

---

## 6. 反向证据检查

- **G13（计量口径）反向检验**：submit 的 `record` 在 `adapter.submit` 成功后（L261），`ChannelRejected`/`ChannelUnavailable` 分支均提前 return 不记（L247-257）——「成功才 record」属实，无反例。
- **Q9 合并额度反向检验**：中金所 S31「1 秒钟内 10 笔（含）以上**报撤单**」为交易所官方对**报撤单合并计量**的直接表述；未发现「撤单不计入每秒额度」的任何来源。
- **Q11 seq 方案反向检验**：S33 明示 `AUTOINCREMENT` 有额外开销「should be avoided if not strictly needed」——本场景 relay 排序**正是** S33 所说 "strictly needed" 的性质（never-used + monotonic），引用不失衡。SQLite `WITHOUT ROWID` 不适用（表需 AUTOINCREMENT，S33 明示禁止）——方案 A 未误用。
- **未发现需推翻 §0 十一条结论的反向证据。**

---

## 7. 出口判定与门禁（SPEC_PROCESS Step 2）

- (a) FALSIFIED 断言：**0**（S30 更正属作者自查修正，已入 §13.4-2/§15.7）。
- (b) CONFLICT：**1 处未仲裁 = F-1**（§15 内部矛盾）→ **修复前禁止进入 Step 3**。
- (c) 阻断性断言双源：✅ G1（S2+代码）、G2/G5（代码+DESIGN/官方）、G10/G11（S21+S15/S22+S31/S32）、Q11（S33/S34+S35/S36）。
- (d) 假设区：Q5 退避参数、Q6 降级语义等均以「待 Step 3 定稿」显式携带，✅。
- **判定：有条件通过**——F-1 由用户二选一裁决后，连同 F-2~F-7（P3 顺手修）一次修订；随后进入全量 Step 1（F7：FastAPI/WS/鉴权/TLS/可观测性/Redis 取舍）。

> **复审者权限声明（RULE-5 单向）**：本复审仅标记问题，未改写 RESEARCH 正文；F-1 的两个修复方向均需用户裁决，不属于复审者可代行事项。

---

## 8. 二轮复审：§19-§22 全量 Step 1 与全部裁决（2026-11-22）

> 触发：RESEARCH 新增 §19（F7 选型）/ §20（Q14 专项）/ §21（Full 架构约束）/ §22（剩余缺口裁决）。复审基座 GLM-5.3-Flash ≠ §19-§22 作者 DeepSeek-V4.1-Flash（异构成立）。**Q13（全局升 3.11）/ Q14（Full 多 worker）为用户裁决**——复审只核对证据与文档一致性，不重开裁决本身。

### 8.1 代码锚点重放（E3，8/8 属实）

| # | RESEARCH 声称 | 重放结果 |
|---|---------------|----------|
| 1 | pyproject L10 `>=3.10` / L35 `pydantic>=2.0.0` / L42 `sqlalchemy>=2.0.0` / L45 `redis>=4.5.0` | ✅ 四处行号精确命中 |
| 2 | tests.yml L16 `["3.10", "3.11", "3.12"]` | ✅ 命中 |
| 3 | ledger_store L49-51 `O_CREAT\|O_EXCL` 抢 `.lock`（G16 核心） | ✅ 逐字命中 |
| 4 | event_log L123 `threading.RLock` / L115 `buffer_size=500` | ✅ 命中 |
| 5 | gateway L407-409 `cancel_all` 逐单调 `cancel()` | ✅ 命中 |
| 6 | 总纲 F7 L223-232 六项能力行号（uvloop/Redis/背压/安全/可观测/验收） | ✅ 命中 |
| 7 | event_log L153-193 `read` / L236-252 `replay`（§19.5 seq 源复用主张） | ✅ 命中 |
| 8 | 总纲 L312/L324 D2 原文（§17 已引，本轮复核） | ✅ 一致 |

### 8.2 外部锚点抽检（S42-S61）

| # | 锚点 | 方式 | 结果 |
|---|------|------|------|
| 1 | S42 FastAPI master pyproject `requires-python>=3.11`、依赖 `pydantic>=2.9.0`/`opentelemetry-api>=1.44.0` | 会话内直取 | ✅ 逐字命中 |
| 2 | S42「0.139.2 仍 >=3.10」 | 搜索快照（PyPI 0.139.2 页） | ✅ 一致 |
| 3 | S42「发布说明含 Drop support for Python 3.10」 | 搜索摘要；直取 release notes grep **未命中**（页面截断） | ⚠️ 引句成立但**无版本号**→ F-R2-3 |
| 4 | S43 uvicorn 0.54.0 / `>=3.10` /「not compatible with Windows or PyPy」/ ws-ping 20s/20s / ws-max-queue 仅入站 | 直取正文 | ✅ 逐字命中 |
| 5 | S44/XACK v5.0.0、XAUTOCLAIM v6.2.0；S45「at-most-once…forever lost」 | 直取正文 | ✅ 逐字命中 |
| 6 | S46 prometheus-client 0.26.0（2026-07-25，>=3.9） | 直取正文 | ✅ 命中 |
| 7 | S50 Python 3.10 EOL 2026-10-01 | 直取正文 | ✅ 命中 |
| 8 | S51「not officially supported on Windows」 | 直取正文 | ✅ 命中 |
| 9 | S56 service containers 必须 Ubuntu runner | 直取正文 | ✅ 命中 |
| 10 | S57 API Keys 四条要求；S58 RFC 8725 章节；S59「Use TLS For All Pages」+RFC 8996 | 直取正文 | ✅ 命中 |
| 11 | S60 Instrumentation | 直取正文 | ✅ 命中 |
| 12 | S61 四黄金信号 | 检索摘要（直取失败，**doc 已如实标注**） | ✅ 降级合规 |

### 8.3 口径保真

- **Q13/Q14 用户裁决**：§19.3/§20.6/§21 记录忠实，裁决与证据倾向的分野（§20.4 vs §20.6）表述清晰 ✅。
- **D14 修正**：「P-053 批内规则」与 [DESIGN_p053#L550](DESIGN_p053_trading_gateway.md)/[IMPL_p053#L28](IMPL_p053_trading_gateway.md) 一致 ✅。
- **F7 对齐**：§21.5「Full 对齐 F7、新增的是落地约束」定位准确 ✅。

### 8.4 发现（0 P1 / 2 P2 / 5 P3）

| ID | 级别 | 发现 | 证据 |
|----|------|------|------|
| **F-R2-1** | **P2** | **§21.1 拓扑图订单事件路径与 §19.9「易错点」自相矛盾**：图中「`Redis Streams ──> 订单事件（消费组，单消费者）`」从交易进程指向 API/WS worker；而消费组是**负载均衡**（每条消息只到一个消费者）——这正是 §19.9 自己更正过的坑。按图实现，连在其它 worker 上的客户端**收不到订单/成交事件**，§21.4「跨 worker 广播一致性」验收不可达。必须二选一并改图：① 交易进程经单一消费组处理后，由 relay/交易进程以 **Pub/Sub** 把订单事件广播给全部 worker（§19.9 原方案）；② 每 worker 一个独立 group（明确 N 倍成本与 XADD 写放大） | §21.1 vs §19.9/§21.4；S44 |
| **F-R2-2** | **P2** | **Q14=Full 后两处旧口径未更新**：① [RESEARCH §7.2](RESEARCH_p054_service_layer.md) 第二条仍写「前置建议：P-054 **首发**可用『进程内 asyncio.Queue + outbox 轮询 relay + 单 worker』」——与 Q14 裁决矛盾；② §10 **Q4 行**（relay 载体：进程内轮询 vs Redis Streams）仍标「P-054 全量 Step 1」，实际已由 Q14 隐含裁决（交易进程内 relay → Redis Streams/PubSub）。两者会误导 Step 3 | §7.2/§10 vs §19.9/§20.6 |
| F-R2-3 | P3 | §19.3 选项 B「`fastapi>=0.139.2,<0.140`（已验证 3.10）」中 **`<0.140` 上界未取证**（0.139.2 支持 3.10 已验证，但 0.140.0 起是否要求 >=3.11 未验证；本轮 PyPI 0.140.0 直取失败）；「Drop support for Python 3.10」引句无版本号（release notes 直取 grep 未命中，仅搜索摘要）。Q13 已选 A 使 B 失效，仍应订正表述或补取证 | §19.3；§8.2 表 #3 |
| F-R2-4 | P3 | 叙述残留：① §19.9「结论先行」句仍是 Phase-0 式设问（「真正的问题是**何时**把进程内扇出升级为跨进程扇出」），与同节末尾「直接 Full」裁决语气不一致；② §21.1 图注「REST 读路径：只读 SQLite（WAL）**或内部 API / Redis 快照**」——Q19 已裁决**不建 Redis 读模型**，图注应删「Redis 快照」 | §19.9/§21.1 vs §20.6/§22.3 |
| F-R2-5 | P3 | PROGRESS §3.61 交付行计数失同步：§0「十一条」（实 **12** 条）、§3「G1-G15」（实 **G1-G17**）、「S1-S41」（实 **S1-S61**）、「Q1-Q12」（实 **Q1-Q20**） | PROGRESS 2908 |
| F-R2-6 | P3 | §19.1 引注「前文 **§12**/G9」不准确——「pyproject 无 redis」的原始出处是 **§3 G9** 与 **§7.2**，§12 无此表述 | §19.1 vs §3/§7.2 |
| F-R2-7 | P3 | ① §22.3「`mode=ro` 跳过 `.lock`」未提 WAL 只读连接对 `-shm`/`-wal` 文件的访问条件（本轮 S53 直取正文截断，Read-Only Databases 节未取到）→ Step 3 需补取证或按「同机同用户」前提显式声明；② **pydantic 实际被使用**（[config_v2.py#L29](../core/config_v2.py#L29) `from pydantic import BaseModel, Field, ...`）——Q13 把 pydantic 升到 `>=2.9.0` 的回归范围必须含 `core/config_v2` 相关测试，§19.3 影响清单未列此项 | §22.3/§19.3；grep 实测 |

### 8.5 反向证据检查

- 未发现推翻 §19-§22 裁决的反例；S53「readers do not block writers」直接支撑 Q19 只读路径。
- **Q14=Full 为用户裁决**，调研证据曾指向 Phase 0（§20.4）——复审不重开裁决，但确认 §20.6/§21 已如实记录代价（G16/G17）与前置条件 ✅。
- §22 各裁决均 ≥1 T1 锚点（S53-S61 全部官方/学术/行业标准）✅；多源校验注已含 §18/S37-S41 ✅。

### 8.6 出口判定（二轮）

- (a) FALSIFIED 断言：0。
- (b) CONFLICT：**2 处未仲裁 = F-R2-1（拓扑图矛盾）、F-R2-2（旧口径未更新）**→ 修复前不得进入 Step 3。
- (c) 双源：§19-§22 核心结论均 ≥1 T1 + 代码实证 ✅（FastAPI 3.11 要求 = S42 master pyproject + S50 3.10 EOL 佐证；单写者 = S2+S53+E3）。
- (d) 假设显式携带：Q5-Q7 数值留 Step 3、S61 检索摘要、S53 Read-Only 节未取证（F-R2-7）均已标注 ✅。
- **判定：有条件通过**——F-R2-1/F-R2-2（P2）与 F-R2-3~F-R2-7（P3，顺手）修复后，Step 2 关闭，进入 Step 3 DESIGN。

> **复审者权限声明（RULE-5 单向）**：二轮仅标记问题，未改写 RESEARCH 正文；Q13/Q14 为用户裁决不受复审影响。

### 8.7 修复核验（复核回执，2026-11-22）

> 执行方：作者基座 DeepSeek-V4.1-Flash（≠ 复审基座 GLM-5.3-Flash）。逐项复核发现属实后修复，本节为回执与落点；§8.4 保留原始发现不改写（RULE-5 单向）。

| ID | 复核 | 修复落点 | 核验方式 |
|----|------|----------|----------|
| **F-R2-1**（P2） | 属实：原图「Streams → 订单事件（消费组，单消费者）」直连 worker，与 §19.9 自相矛盾 | [RESEARCH §21.1](RESEARCH_p054_service_layer.md) 拓扑图重绘为「relay XADD → Streams → **唯一消费者**处理后 PUBLISH → Pub/Sub → N worker」，并加「扇出路径唯一化」注解 | 图内订单/行情两条路径均收敛到 Pub/Sub；与 §19.9「消费组=负载均衡」、§21.4「跨 worker 广播一致性」一致 |
| **F-R2-2**（P2） | 属实：§7.2 第二条仍「首发单 worker」；§10 Q4 仍标「全量 Step 1」 | §7.2 标题与正文改 Q14=Full 口径；§10 Q4 行改「已裁决（随 Q14）」；连带同步 §12.1 S12 / A3 / §12.4 Q4 三处旧引用 | grep「首发」/「单 worker」：除 §7.2 的否定句（「不采用…」）与 §19.10/§20.4 的被拒方案历史记录外，无有效口径残留 |
| F-R2-3 | 属实：`<0.140` 无取证；「Drop 3.10」无版本号 | §19.3 选项 B 标注上界未取证；S42 在 §8 与 §19.12 两处表内加「无版本号」注；§19.1 同步 | 三处措辞一致，未把搜索摘要升格为一手断言 |
| F-R2-4 | 属实：§19.9 结论先行仍 Phase-0 式设问；图注含「Redis 快照」 | §19.9 结论先行改为 Full 已裁决口径；§21.1 图注改为「只读 SQLite（WAL，mode=ro/query_only）；跨机走内部 API」 | 与 Q14（§20.6）、Q19（§22.3）一致；「Redis 快照」仅存于 §22.3 的被拒方案说明 |
| F-R2-5 | 属实：PROGRESS §3.61 计数过时 | PROGRESS L2908 改「§0 十二条 / G1-G17 / S1-S61 / Q1-Q20」并补 §19-§22 指向 §3.62 | 与 RESEARCH 实际章节数、S 表末条 S61、Q 表末条 Q20 逐一对齐 |
| F-R2-6 | 属实：§19.1 引注「§12/G9」错误 | 改为「§3 G9 与 §7.2」，并补 `redis` 零引用 / `pydantic` 仍被 `config_v2` 使用的准确表述 | 与 §3 G9、§7.1 原文对应 |
| F-R2-7 | 属实：① §22.3 未提 `-shm`/`-wal`；② pydantic 确被 `core/config_v2.py` L29 使用 | §22.3 第 1 条加「未取证前提」+ 退回内部 API 条件；§19.3 实施影响 ③ 补 pydantic 实际使用与 config 回归范围 | 读码 `core/config_v2.py` L29 确认；WAL 前提已显式标未取证，未升格为结论 |

**出口判定更新**：门禁 (b) CONFLICT 的 2 处（F-R2-1/F-R2-2）已消除；F-R2-3~F-R2-7 为 P3 且已顺手修复；其余门禁 (a)/(c)/(d) 维持 §8.5-§8.6 结论 → **Step 2 关闭**，可进入 Step 3 DESIGN。

> 复核范围声明：本节只核对「发现是否属实 + 修复落点是否到位」，不代替第三轮异构复审；若 Step 3 DESIGN 阶段发现本次修复引入新的口径冲突，按门禁 (b) 回退处理。

---

## 9. 二轮修复定点复验（异构第三轮，2026-11-22）

> **触发**：用户指令「执行第二轮复审」（对象 = §8.7 回执与其 7 项修复落盘）。**复验基座 GLM-5.3-Flash ≠ 修复执行基座 DeepSeek-V4.1-Flash**（§8.7 自述）→ 异构成立。方法：修复位点逐点重放 + 全文口径残留扫描（grep）+ 关键代码锚点独立重放 + 回执准确性核对。复验方仅标记问题、顺手修正无歧义 P3 措辞，不改写 §8.7 回执正文与任何裁决内容。

### 9.1 七项修复落盘重放（7/7 与回执一致）

| ID | 回执声称落点 | 重放结果 |
|----|--------------|----------|
| F-R2-1 | §21.1 拓扑重绘 + 扇出注解 | ✅ 订单路径 = relay XADD → Streams（**唯一消费者**）→ PUBLISH → Pub/Sub → N worker；订单/行情均收敛到 Pub/Sub；注解引 §19.9（消费组=负载均衡）与 §21.4（跨 worker 一致性）准确 |
| F-R2-2 | §7.2 / §10 Q4 / §12 三处 | ✅ §7.2 标题「已裁决：Q14 = Full」+ 正文为否定句；§10 Q4 =「已裁决（随 Q14）」；§12.1 S12（L367）/ A3（L375）/ §12.4 Q4 行（L415）同步 |
| F-R2-3 | §19.3 选项 B + S42 三处 | ✅ 选项 B 含「`<0.140` 上界未取证」；「无版本号」恰 3 处（§8 S42 L275 / §19.1 L864 / §19.12 L977），措辞一致 |
| F-R2-4 | §19.9 结论先行 + §21.1 图注 | ✅ 结论先行（L935）=「Q14 已裁决 Full」口径；图注（L1072）=「只读 SQLite（WAL，mode=ro/query_only）；跨机走交易进程内部 API」；「Redis 快照」仅存 4 处合法位置（§10 Q19 选项枚举 / §11 复审引述 / §21.3 裁决点选项 / §22.3 被拒说明） |
| F-R2-5 | PROGRESS L2908 | ✅ 「§0 十二条 / G1-G17 / S1-S61 / Q1-Q20 + §19-§22 见 §3.62」；交叉核对：§0 第 12 条在位（L26）、**G16/G17 确在 §3 发现表（L109/L110）**、S60/S61 在位（L293/L294）、Q20 在位（L333） |
| F-R2-6 | §19.1 引注 | ✅ 「§3 G9 与 §7.2」；全文「§12/G9」0 命中 |
| F-R2-7 | §22.3 + §19.3 | ✅ §22.3 第 1 条含「未取证前提」与退回内部 API 条件；§19.3 ③ 含 pydantic 实际使用与 config 回归范围；`config_v2.py` L29 `from pydantic import BaseModel, Field, field_validator, model_validator` 独立重放确认 |

### 9.2 残留扫描与新发现（0 P1 / 0 P2 / 2 P3）

**残留扫描**：grep「首发」仅 3 处（L54 D1「首发真实连通」不同语义 / L219 §7.2 否定句 / L353 §11 复审记录引述）；grep「单 worker」13 处全部为否定句（L219/L946）、被拒方案（§19.10 L959）、uvicorn 产品事实（L891）、§20 专项历史分析（L998-L1051，已标「推翻」）与 §11 状态链记录（L350/L353）——**无有效旧口径残留** ✅。

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-R3-1** | P3 | **「入账」术语误用 ×2**：§21.1 图「Streams 消费组（**入账**/分发…）」与 §10 Q4「Streams **入账**」——按 §16/U-P053-17 裁决设计，订单/成交**入账发生在交易进程 SQLite 组合写事务**（业务行 + outbox 同提交）；Streams 消费侧职责是 **at-least-once 投递桥接**（消费 → PUBLISH → XACK，XAUTOCLAIM 重投）。「入账」在本文档语境特指账本记账，保留会误导 Step 3 的 relay 职责划分 | **复验方顺手修正**：两处改「可靠投递/分发」/「Streams 可靠投递」 |
| **F-R3-2** | P3 | **§8.7 回执 F-R2-2 核验枚举不全**：回执称残留「仅剩 §19.10/§20.4」，实际还包括 §11 状态链（L350/L353）、§19.4 L891（uvicorn 产品事实）与 §20 专项整节（L998-L1051）——均为已标「推翻/未采纳」的历史记录或产品事实，回执结论「无有效口径残留」仍成立，仅枚举不全 | **登记不改写**（§8.7 为修复执行方章节，RULE-5 单向）；本节扫描即完整枚举 |

### 9.3 出口判定（第三轮）

- 7/7 修复落盘与回执一致；门禁 (a) FALSIFIED = 0、(b) CONFLICT 维持清零、(c) 双源与 (d) 假设携带维持 §8.5-§8.6 结论。
- 新发现 0 P1 / 0 P2 / 2 P3：F-R3-1 已顺手修正、F-R3-2 已登记 → **Step 2 维持关闭（2026-11-22）**，进入 Step 3 DESIGN。
- 本节为**定点复验**（修复落盘 + 残留扫描），非全量第三轮复审；若 Step 3 前需要全量复审可另行触发。

> PROGRESS §3.62 已由复验方补登本节记录行。
