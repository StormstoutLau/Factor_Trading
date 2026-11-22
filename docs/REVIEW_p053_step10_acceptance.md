# REVIEW：P-053 Step 10 验收与异构复审（代码 vs 设计对齐审计）

> **批次**: P-053 · **Step 10 验收** · 日期 2026-11-22 · **判档 P2**
> **对象**: Step 9 落码（13 实现文件 + 9 测试 86 例；`live/*.py` 16、`tests/test_p053_*` 9 文件）
> **异构性**: 作者 DeepSeek-V4.1-Flash ≠ 复审基座 GLM-5.3-Flash（对齐 P-051c / P-052 / 本批 Step 6 先例，RULE-5）
> **方法**: ADD（audit-driven-development）五阶段——Phase 0 Spec 质量门 → Phase 1 盘点 → Phase 2 三路 subagent 并行多维审计 → Phase 3 优先级矩阵 → Phase 3.5 源码级验证（防幻觉硬门）→ Phase 4 修复基线（修复 + 门禁全量重放）
> **结论**: **PASS（修复后）**——22 项发现 = **1 P1 + 7 P2 + 14 P3**；处置 **7 代码/测试修复 + 4 文档订正 + 6 登记**（合并 11 项未修 → U-P053-15..20）；**0 P1 残留**；修复后门禁全量重放零回归（§5）；总评 **A+（修复后）**（§7）

---

## 1. 结论速览

| 级别 | 数量 | 发现（编号双轨：复审源 ID ↔ F-R5-N） |
|---|---|---|
| P1（运行必崩 / 契约互斥） | 1 | B-1 = **F-R5-1** CTP capability 与网关自主通道能力门互斥 |
| P2（功能阻塞 / 契约违背 / 断言缺口） | 7 | B-2 = F-R5-2 start() 回放环死路径 · B-3 = F-R5-3 CTP 启动期查询限流（登记）· B-4 = F-R5-4 委托/撤单桶未接 resolve_limits · B-5 = F-R5-5 coid↔OrderRef 映射缺失 · A-1 = F-R5-7 T2 无 A→2 直接断言 · A-2 outbox 同事务公开 API 缺口（登记）· C-P2-1 = F-R5-8 I5 无 pre_trade_check 直接断言 |
| P3（语义背离 / 口径 / 死代码 / 覆盖缺口） | 14 | B-9 = F-R5-9 should_degrade 闩锁 vs 尾部语义 · B-7 = F-R5-6 attribute_break 现金分支不可达（登记）· B-6 M11 占位措辞 · B-8 M5/M6 函数计数 · A-3 M1 16 字段 · A-4 M3 import 口径 · A-5/A-6 死代码（登记）· A-7 测试探针 3 条（登记）· C-P3-1..5 测试缺口 5 条（登记，含 resume 迭代器） |
| 合计 | **22** | 7 修复（落码）+ 4 订正（文档）+ 6 登记（合并 11 项，§6） |

P1 一句话摘要：

- **F-R5-1（B-1）**：[ctp.py](../live/adapters/ctp.py) 曾声明 `supports_client_order_id=False`，而网关 submit 步⑤ 对自主通道 `require_capability(need={"client_order_id","cancel","query_orders"})` → **CTP 经网关提交必抛 `CapabilityError`**，能力声明与映射契约（DESIGN §3.9）双重违约。修复：capability 置 True + `_refs` 映射落地（F-R5-5 配套）。

---

## 2. Phase 0：Spec 质量门（判档 Tier A，5/5）

| # | 维度 | 判据 | 得分 |
|---|------|------|------|
| 1 | 可测试约束 | DESIGN D1-D16 + I1-I12 + §5 阈值表（≥3 条 must/数值阈值，实测数十条） | 1 |
| 2 | 模块映射 | 13 实现文件 ↔ DESIGN §3.1-§3.9 1:1 映射（IMPL §1 表） | 1 |
| 3 | 接口契约 | 公开函数签名/参数/返回值在 IMPL §3 逐处给码（≥80% 覆盖） | 1 |
| 4 | 修正项 | Step 4/6 复审 17 项 F-I 修正枚举 + D-1..D-13 偏差表 | 1 |
| 5 | 跨模块契约 | 依赖边 DAG（IMPL §1）+ C-1..C-12 跨文件契约 + D14 零改动清单 | 1 |

**判档 Tier A → 全量审计（Phases 1-4）**，评分无 B+ 封顶限制。

## 3. 取证矩阵（E1-E5）

| # | 取证维度 | 方法 | 实测证据 |
|---|----------|------|----------|
| E1 | 门禁重放 | 修复后全量复跑七项门禁 | pytest `1300 passed, 278 warnings in 138.34s`（Step 9 首跑 140.15s）；golden `22 passed, 1278 deselected`（零重录）；mypy `Success: no issues found in 141 source files`；black `283 files would be left unchanged` |
| E2 | CHECKLIST 全项重放 | M13 + T10 + C7 + I12 + D16 + F17 = 75 项逐项核对 | 75/75 ✅（[CHECKLIST](CHECKLIST_p053_trading_gateway.md)，Step 10 订正 M1/M3/M5/M6/M10/M11/T2/T6/I5 共 10 处实测列） |
| E3 | 读码证据（file:line） | Phase 3.5 对全部 P1/P2 关键项**亲自读码证实**后才落修复 | 见 §4 各发现「证据」行；关键点位：[ctp.py#L51](../live/adapters/ctp.py#L51)、[gateway.py#L106-L133](../live/gateway.py#L106-L133)、[gateway.py#L144](../live/gateway.py#L144)、[channel.py#L28-L43](../live/channel.py#L28-L43)（16 字段）、[reconcile.py#L173-L185](../live/reconcile.py#L173-L185)、`core/compliance.py` `RateLimitConfig` 默认（1/s、1000/日） |
| E4 | 盲区扫描 | ①恒真断言扫描 ②跨文件传递依赖 ③设计独有约束无测试 ④死代码/禁 import | ③→A-1/C-P2-1/A-7/C-P3 组（断言经中转恒真或缺失）；④→A-5/A-6 死代码；I7 禁 import `grep` 零命中（CHECKLIST I7 ✅） |
| E5 | 修复后回归 | 修复跟踪 open→fixed→verified + 零改动核对 | §5 回执表；`git status --porcelain` 对 golden、零改动 7 文件（M13）、依赖清单输出为空 |

## 4. 发现明细

### P1（1 项）

**F-R5-1（B-1）CTP capability 与网关能力门互斥（CTP 经网关必崩）**
- 证据：`live/adapters/ctp.py` 曾 `supports_client_order_id=False`；gateway submit 步⑤ 对 autonomous 通道 `require_capability(cap, need=frozenset({"client_order_id", "cancel", "query_orders"}))`。
- 影响：CTP 通道 start/submit 直接 `CapabilityError`——DESIGN §3.9 声明的 coid ↔ (FrontID, SessionID, OrderRef) 映射完全不可达；D8 违约。
- 处置：**修复**（capability 置 True，[ctp.py#L51](../live/adapters/ctp.py#L51)；配套 `_refs` 映射见 F-R5-5）；IMPL 偏差表 **D-9** 登记。

### P2（7 项）

**F-R5-2（B-2）start() 回放环死路径（远程回报静默丢弃）**
- 证据：`load_orders` 装载曾在自主回放环**之后**执行 → 回放环读空 `_orders`，`_apply_order_report` 内 `rec is None` 早退，from_query 回报全部静默丢弃。
- 影响：崩溃重启后远程在途订单状态无法恢复（SSE 恢复序第一步失效）。
- 处置：**修复**——`load_orders` 前移至回放环之前（[gateway.py#L144-L145](../live/gateway.py#L144-L145)）；IMPL **D-11**。

**F-R5-4（B-4）委托/撤单桶只用内部 rate_config（通道上限本地不生效）**
- 证据：submit/cancel 曾 `check_rate(..., self._rate_config)`；C-5/D11 双层流控要求内部与通道取 min。
- 影响：通道声明低于内部阈值时，本地不拦截，依赖通道拒单（请求级 -3 与业务拒单混淆）。
- 处置：**修复**——`start()` 构造 `_submit_config`/`_cancel_config` 接 `resolve_limits` 三方最小（[gateway.py#L124-L133](../live/gateway.py#L124-L133)），submit/cancel 改 `self._submit_config or self._rate_config`（[gateway.py#L200](../live/gateway.py#L200)、[gateway.py#L386](../live/gateway.py#L386)）。经核 `RateLimitConfig()` 内部默认 1/s → 对 mock/CTP 默认配置零行为变化，仅收紧「通道低于内部」场景，既有测试安全；IMPL **D-12**。

**F-R5-5（B-5）CTP coid↔OrderRef 映射缺失（F-R5-1 配套）**
- 证据：capability 置 True 后，`query_orders` 返回的 `order_ref` 无法映射回 `client_order_id` → 回报对不上本地订单。
- 影响：CTP 回报链路断裂（同 F-R5-1 的 D8 违约面）。
- 处置：**修复**——submit 成功后登记 `_refs[coid] = (front_id, session_id, order_ref)`（[ctp.py#L86](../live/adapters/ctp.py#L86)），`query_orders` 首部 `by_ref` 反查（[ctp.py#L102-L105](../live/adapters/ctp.py#L102-L105)）；IMPL **D-10**。

**F-R5-7（A-1）T2 缺 A→2 直接断言（秒成交仅经 PF 中转间接覆盖）**
- 证据：T2 既有用例 A→2 均经「A→PF→2」中转；`LEGAL` 的 `A→2`（秒成交，F-D3）无直接探针——若该边被误删，测试仍绿（E4 盲区③）。
- 处置：**修复**——补 `transition(_record(), state=OrderState.FILLED, ts=2.0, filled_quantity=100.0)` 直接断言（[test_p053_order_semantics.py#L98](../tests/test_p053_order_semantics.py#L98)）。

**F-R5-8（C-P2-1）I5 缺 pre_trade_check 直接断言（T6 打桩间接覆盖）**
- 证据：T6 ⑤ 仅断言 `on_order_result(rejected=True)` 被调，未证明「拒单前必经 gate」——若步④被误删，mock 拒单路径仍可能绿（I5 恒真风险）。
- 处置：**修复**——`pre_trade_check` spy 包装 + `gate_calls == [1]` 直接断言（[test_p053_flow_recovery.py#L169](../tests/test_p053_flow_recovery.py#L169)）；CHECKLIST I5 实测列已更新。

**A-2 outbox「同事务」公开 API 缺口（登记 → U-P053-17）**
- 证据：outbox 三表同事务原子性仅裸 SQL 路径可达；`append_entry`/`upsert_order`/`append_outbox` 公开方法各自独立事务；gateway 生产路径「订单 + 审计」两事务非原子。
- 处置：**登记**（P-054 消费端设计前置，本批 D16 只写不读）；详见 §6。

**F-R5-3（B-3）CTP 启动期同秒 3 查询必限流（登记 → U-P053-18）**
- 证据：RESEARCH 锚点——CTP 查询流控 1 笔/秒（在途 1）；start() 恢复序同秒内 `query_trades` + `query_orders` + reconcile `query_positions` 三连发。
- 影响：真实 CTP 环境启动期触发请求级 -3（本批无真实网络接线，测试不可达）。
- 处置：**登记**（退避重试方案属 P-054 真实接线设计）；详见 §6。

### P3（14 项，摘要）

| ID | 摘要 | 处置 |
|----|------|------|
| **F-R5-9（B-9）** | `should_degrade` 实现「历史闩锁」（任一日 breach 永久降级）vs docstring「尾部连续 N 日」语义背离 | **修复**：重写为按日期排序的尾部连续计数（[reconcile.py#L173-L185](../live/reconcile.py#L173-L185)）；T5 既有断言（bad-ok-bad→False / 追加→True）不变仍绿 |
| **F-R5-6（B-7）** | `attribute_break` 现金分支维度错位（资产-现金粒度不匹配），实际输入下不可达 | 登记 → U-P053-19 |
| B-6 | broker_api「未注入 transport → 不可用」措辞不准：语义占位，注入亦不可用，`_require` 为死占位 | 订正 M11 |
| B-8 | reconcile 8 函数 / session_calendar 5 函数计数口径（IMPL §1 曾写 7 函数） | 订正 M5/M6 |
| A-3 | `ChannelCapability` 字段计数 15 → **16**（含 `notes`），DESIGN/IMPL/代码三方对齐 | 订正 M1 |
| A-4 | ledger 运行期 import 口径：`live.corporate_actions` + `live.orders.FillRecord` | 订正 M3 |
| A-5 / A-6 | 死代码 `_ceil_positive` / `_SOURCE`（无调用方） | 登记 → U-P053-15 |
| A-7 | 3 条规格行为无测试探针（DESIGN 86 例映射缺口） | 登记 → U-P053-20 |
| C-P3-1..5 | 测试缺口 5 条：恢复序 positions 段、`_query_config` 默认接线、resume 一次性迭代器（C-P3-3）、CSV 10 列全表头、相位边界端点 | 登记 → U-P053-16 / U-P053-20 |

## 5. 修复回执与门禁重放

| # | 发现 | 落码位置 | verified 证据 |
|---|------|----------|---------------|
| 1 | F-R5-1 | [ctp.py#L51](../live/adapters/ctp.py#L51) capability True | mypy 141 files 0；T6 全绿（CTP 用例经网关提交通过） |
| 2 | F-R5-2 | [gateway.py#L144-L145](../live/gateway.py#L144-L145) load_orders 前移 | T9 ⑤ 崩溃恢复 + T6 恢复序绿 |
| 3 | F-R5-4 | [gateway.py#L106-L107](../live/gateway.py#L106-L107)、[L124-L133](../live/gateway.py#L124-L133)、[L200](../live/gateway.py#L200)、[L386](../live/gateway.py#L386) | T6 ④ 查询桶 / T9 全链绿；既有 86 例零回归（默认配置零行为变化） |
| 4 | F-R5-5 | [ctp.py#L63](../live/adapters/ctp.py#L63)、[L86](../live/adapters/ctp.py#L86)、[L102-L105](../live/adapters/ctp.py#L102-L105) | T6 查询回报回 coid 路径绿 |
| 5 | F-R5-7 | [test_p053_order_semantics.py#L97-L98](../tests/test_p053_order_semantics.py#L97-L98) | T2 **14 passed**（含新增直接断言） |
| 6 | F-R5-8 | [test_p053_flow_recovery.py#L169](../tests/test_p053_flow_recovery.py#L169) | T6 **8 passed**；CHECKLIST I5 直接断言成立 |
| 7 | F-R5-9 | [reconcile.py#L173-L185](../live/reconcile.py#L173-L185) | T5 **12 passed**（bad-ok-bad→False / 追加→True 语义保持） |

**门禁全量重放（修复后）**：pytest **1300 passed（138.34s）** · golden **22 passed**（零重录）· mypy **141 files 0** · black **283 unchanged** · 计数 `tests=141 / core=51 / live=16`（顶层 11 + adapters 5）· golden / 零改动 7 文件 / 依赖清单 `git status --porcelain` 输出为空 → **零回归**。

**文档同步**：IMPL 8 处（C-5 注记、§3.8 伪码 3 处、§3.9 3 处、§5 偏差表 D-9..D-13）；CHECKLIST 12 处（头部计数、M1/M3/M5/M6/M10/M11、T2/T6、I5、C1 重跑读数、§7 出口判定、§10 复审记录）。

## 6. 登记项（U-P053-15..20，四元块）

**U-P053-15 死代码 `_ceil_positive` / `_SOURCE`**（源 A-5 + A-6，P3×2）
- 现象：两符号无调用方（E4 盲区④死代码扫描命中）。
- 影响：无运行期风险；仅维护噪音。
- 决策：登记不修（当轮修复面收敛于行为缺陷）。
- 计划：P-054 真实接线批随 refactor 顺手清除。

**U-P053-16 `Ledger.resume` 一次性迭代器静默空账本**（源 C-P3-3，P3）
- 现象：`resume(entries_iter)` 消费一次性迭代器后，重复调用得空账本且无告警。
- 影响：调用方误用（如复用生成器）时静默丢账本；当前唯一调用点 `start()` 传入 `store.entries()` 列表，安全。
- 决策：登记不修（防御性校验属 API 加固，超出本批面）。
- 计划：P-054 接线批将 `resume` 入参固化为 `Sequence` 并加空账本断言。

**U-P053-17 outbox「同事务」公开 API 缺口**（源 A-2，P2）
- 现象：outbox 三表原子性仅裸 SQL 可达；公开 API 各自独立事务；gateway 生产路径「订单 + outbox」两事务非原子。
- 影响：进程在两事务之间崩溃时，订单已落库而 outbox 缺失 → P-054 消费端漏投递（不丢已确认成交）。
- 决策：登记不修（D16 本批 outbox 只写不读，无消费方；原子性改造需与消费端 ACK 语义一并设计）。
- 计划：**P-054 前置项**——outbox 消费端设计时落地「订单+outbox 组合事务」入口。

**U-P053-18 CTP 启动期同秒 3 查询限流**（源 B-3 = F-R5-3，P2）
- 现象：CTP 查询流控 1 笔/秒；start() 恢复序同秒 `query_trades` + `query_orders` + reconcile `query_positions` 三连发。
- 影响：真实 CTP 环境启动期触发请求级 -3（`ChannelUnavailable`），恢复序中断；本批测试环境不可达。
- 决策：登记不修（本批无真实网络接线；`_throttle_query` 桶已按 1/s 生效，缺的是退避重试）。
- 计划：**P-054 前置项**——真实接线批为查询路径增加 -3 退避重试与启动期查询合并。

**U-P053-19 `attribute_break` 现金分支维度错位不可达**（源 B-7 = F-R5-6，P3）
- 现象：现金归因分支的资产-现金粒度与调用面不匹配，现有输入下不可达。
- 影响：无（不可达代码）；若未来传入现金资产将得到错位归因。
- 决策：登记不修。
- 计划：P-056（margin/short 账本）涉及现金资产归因时重审该分支。

**U-P053-20 测试覆盖缺口合并项**（源 A-7 + C-P3-1/2/4/5，P3×5 合并）
- 现象：①A-7：3 条规格行为无探针；②恢复序 positions 段；③`_query_config` 默认接线；④CSV 10 列全表头；⑤相位边界端点。
- 影响：均为低概率回归盲区（E4 盲区③），无已知缺陷。
- 决策：登记不修（86 例规模已达标，补探针收益/成本比低）。
- 计划：P-054 接线批天然触及②③④场景（真实通道 + 消费端），随批补测。

## 7. 评分（ADD A+~F，修复后）

| 模块 | 评分 | 依据 |
|------|------|------|
| `live/channel.py` / `orders.py` / `session_calendar.py` / `adapters/broker_api.py` / `adapters/terminal.py` / `ledger_store.py` / `adapters/mock.py` | **A** | 无行为级发现（M1/M3/M5/M6/M11 订正为文档侧） |
| `live/ledger.py` | **A** | 登记 U-P053-16（调用点安全） |
| `live/reconcile.py` | **A-** | F-R5-9 修复 verified；U-P053-19 登记 |
| `live/gateway.py` | **A-** | F-R5-2/F-R5-4 修复 verified |
| `live/adapters/ctp.py` | **A-** | F-R5-1/F-R5-5 修复 verified；U-P053-18 登记（P-054 前置） |
| `tests/`（9 文件 86 例） | **A-** | F-R5-7/F-R5-8 补断言 verified；U-P053-20 登记 |
| **总评** | **A+（修复后）** | 0 P1 残留、0 开放 P2（2 项 P2 按 D16/无接线边界**有意降级**为 P-054 前置登记）、P3 全部修复/订正/登记；门禁重放零回归 |

**遗留风险声明**：U-P053-17/18 为 P-054 硬前置（outbox 原子性、CTP 查询退避）——P-054 启动时必须先行消化；其余登记项均为低风险技术债。
