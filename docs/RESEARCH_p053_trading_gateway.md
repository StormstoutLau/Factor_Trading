# RESEARCH：P-053 交易通道网关（通道可行性门 / 三桥 / ledger / reconcile）

> **批次**: P-053 · **Step 1 调研** · 日期 2026-11-21 · **判档 P2**（预计 T1：新增契约 + `live/` 多模块）
> **上游口径**: [UPGRADE_MASTER_PLAN](UPGRADE_MASTER_PLAN.md) §3 F6（L212-221）/ §5 P-053（L270）/ §7.1 D1·D4 裁决；[RESEARCH_upgrade_open_questions](RESEARCH_upgrade_open_questions.md) Q1（通道拓扑）/ Q10（parity 阈值）/ Q11（多策略共享账户）/ Q12（公司行为）
> **前置**: P-043（`IEventBus` 契约）/ P-044（Strategy 契约）/ P-050（保证金/空头账目）/ **P-052（SafetyGate，已关闭 `2064ae6`）**
> **方法**: E1 官方文档/监管原文 → E2 工程实践（开源实现 + 行业文章）→ E3 本仓代码实证 → E4 接口/数据实测（本批不联网实测，仅取文档契约）
> **基线读数 @`2064ae6`**: pytest **1214** / golden **22** / mypy **128 files 0** / black **261** / `tests/*.py` **132** / `core/*.py` **51** / `live/*.py` **3**
> **状态**: Step 2 复审 PASS（[REVIEW_p053_step2](REVIEW_p053_step2_research.md)，0 P1 / 3 P2 / 3 P3 全修复）→ Step 3 DESIGN 完成（[DESIGN_p053](DESIGN_p053_trading_gateway.md)：13 模块 / 86 例；U-P053-1..11 全部定案）→ **Step 4 复审 PASS**（[REVIEW_p053_step4](REVIEW_p053_step4_design.md)，3 P1 + 5 P2 + 6 P3 全修复）→ **Step 5 IMPL 完成**（[IMPL_p053](IMPL_p053_trading_gateway.md)：13 文件逐处代码 / C-1..C-12 / 86 例映射）→ **Step 6 复审 PASS**（[REVIEW_p053_step6](REVIEW_p053_step6_impl.md)：5 P1 + 8 P2 + 4 P3 全修复并回写 IMPL/DESIGN，§4 六项复审输入逐条作答）→ **Step 7 CHECKLIST 完成**（[CHECKLIST_p053](CHECKLIST_p053_trading_gateway.md)：M13+T10+C7+I12+D16+F17 = 75 项，全 `[待 Step 9]`）→ **Step 8 四文档一致性通过**（2026-11-22，GLM-5.3-Flash 异构；86 例映射 / 门禁目标 / 编号链 / 契约签名四方核对，1 处 P3 残留修复）→ **Step 9 TDD 落码 + 门禁完成**（2026-11-22：13 实现文件 + 9 测试文件 86 例；pytest **1300** / golden **22** / mypy **141·0** / black **283** / `tests/*.py` **141** / `core/*.py` **51** / `live/*.py` **16** 全绿，CHECKLIST 75/75 ✅）→ **Step 10 验收与异构复审完成（2026-11-22）**（[REVIEW_p053_step10](REVIEW_p053_step10_acceptance.md)：GLM-5.3-Flash 异构 ✅；ADD Tier A 判档，三路 subagent 审计 22 发现（1 P1 + 7 P2 + 14 P3）→ **7 修复 + 4 订正 + 6 登记（U-P053-15..20）**，0 P1 残留；修复后门禁重放 **1300 passed（138.34s）** / 22 / 141·0 / 283 / 141·51·16 全绿零回归，总评 **A+（修复后）**；未提交）
> **补充调研（2026-11-21）**: U-P053-1/2/4 已补外部案例锚点，结论与残余发现见 **§12**

---

## 0. 结论摘要（TL;DR）

1. **股票端的「本地 xtquant 常驻网关」路线已被监管关闭**：miniQMT 属「外接」形态（本地进程生成指令、客户端仅转发，策略不在券商可穿透环境内），受 2026-08-28《证券公司交易信息系统接入管理规范（试行）》约束；华鑫证券已公告 **2026-10-30 收盘后关闭 miniQMT**，多家券商 2026-07 起停止新申请。**P-053 不能把 QMT 当主通道。**
2. **可完整自动化的通道只剩两类**：`BrokerApiBridge`（券商机构 API，如中泰 XTP / 宽睿 OES，需机构户与审批）与 `CtpBridge`（期货/期权，公开 API、可完整集成）。`TerminalBridge`（QMT 标准版 / PTrade / 人工客户端）只能做**半自动**：平台出订单清单 + 人工确认回填。
3. **P-053 的第一交付物是「通道可行性门」（`ChannelCapability`）而不是任何具体连接**：账户层级、可用 API、品种、速率上限、合规报备状态、是否支持客户端订单号/撤单/查询——不满足即拒绝启用该通道。
4. **订单链路的正确性不靠通道，靠本地四件套**：`client_order_id` 幂等、归一化订单状态机、账本（双重记账 + 唯一约束）、对账（逐笔 + 余额）。外部四大权威锚点一致支持：FIX 订单状态机、上交所 STEP「重连先恢复执行报告，再处理已报未确认」、CTP「OrderRef 唯一 + 断线重连需重新认证登录」、JR/T 0300—2023 对账数据接口。
5. **本批建议仍不接真实网络**：用 `FakeTransport` + 录制帧（QMT/CTP/XTP 状态码）做确定性测试；真实连通、压测、灰度归上线演练（P-053 之后或同批后半）。这与项目「先 synthetic 后接数据」的既定粒度一致。
6. 预计新增 6 个模块 + 6 个测试文件 **约 62 例**，pytest 1214 → **≈1276**；`live/` 文件数 3 → **9**。
7. **U-P053-1/2/4 已补外部案例锚点（§12）**：首发真实连通 = CTP/SimNow（零审批、官方、第二套环境不提供结算）；账本 = SQLite（stdlib + WAL + 单写者，零新依赖）；「已报未确认」= 只查询 + 宽限期 + 人工确认，不自动重发。
8. **Step 2 复审后修订（F-1..F-6，见 §11 第 7 条回执）**：补 Q12 两模块（`session_calendar`/`corporate_actions` → G11 + U-P053-11）；补 parity 立项期校准义务（总纲 L244 → U-P053-5）；闭环 O-R2 取证（xtquant = Windows x64 / Python 3.6-3.13 / Linux 无官方支持）；§2 两处字段措辞澄清；Q11 净额撮合移交登记。

---

## 1. 题干与总纲口径

### 1.1 总纲 F6（L212-221）已明确的能力面

| 能力 | 总纲要求 | 本批落点 |
|------|----------|----------|
| 通道可行性门 | `ChannelCapability`：账户层级/API/品种/速率/报备 | §6.1、G7 |
| 三桥 | qmt（半自动）/broker_api（完整）/ctp（完整） | §5 方案、§6.2 |
| 统一订单语义 | 复用 `OrderIntent`，补客户端订单号与状态机 | G2/G3 |
| 账本 | 持仓/资金/加权成本/已实现盈亏，唯一约束 | G5 |
| 对账 | 逐笔 + 余额，差异分级与停机 | G6 |
| 合规 | 报备字段与速率上限（P-052 已建报告 schema） | §3.6 |
| 安全 | 凭据不落配置、每账户单写者 | G9 |
| 交易日历/交易时段 | `live/session_calendar.py` 时段状态机（F-R9-P2：P-053 验收加时段状态机；Q12 推荐 5） | G11 |
| 公司行为归因 | 除权除息/送转/配股事件表 + 对账先归因再判异常（Q12 推荐 1/4；synthetic 事件表先行） | G11 |

### 1.2 已裁决口径（不得在本批重开）

- **D1（通道）**：不做单一 QMT 绑定；P-053 = 交易通道网关 + 可行性门；默认 `BrokerApiBridge` + `CtpBridge` 完整集成，`TerminalBridge` 半自动。（Q1 §推荐）
- **D4（粒度）**：每批必须有 synthetic fixture + golden；禁止因外部数据/权限缺失阻断开发。
- **P-052 契约**：所有发单必须经 `SafetyGate.pre_trade_check`（`live/safety_gate.py`），`cancel_all` 只对 `LiveTradingBridge` 调用（D-G7）。本批不得绕过。
- **Q10（parity 阈值）**：paper↔live 持仓精确、现金 ≤0.01% NAV、权重 L1 ≤1e-4、成交均价 ≤10bps（流动）/30bps（小盘）、成交率 ≥95%；连续 2 日超阈值自动降级。**附立项期校准义务**：总纲 L244「阈值在 P-053 立项时按账户规模校准并写入验收」+ Q10 待确认（L374）→ U-P053-5。
- **Q11（多策略共享账户）**：每策略虚拟子账户 + 下单前预留 + 跨策略净额（本批只做账本侧最小实现，不做净额撮合）。

---

## 2. 代码现状（E3 实证）

| 位置 | 事实 | 影响 |
|------|------|------|
| [live_bridge.py](../core/live_bridge.py#L46-L57) | `LiveOrder` 仅 `status: str` 五值自由串（`pending/filled/partial/cancelled/rejected`）；无 `client_order_id`、无逐笔成交（fill）事件记录；`broker_order_id`（L61）仅为回显字符串字段、无 client↔broker 映射表 | 状态机与幂等底座缺失 |
| [live_bridge.py](../core/live_bridge.py#L69) | `LiveTradingBridge` ABC 四抽象：`place_intents` L85 / `cancel_orders` L98 / `sync_positions` / `query_order_status` | 可复用为通道接口，但缺 `query_orders`/`query_trades`/`connect` |
| [live_bridge.py](../core/live_bridge.py#L144) | `MockLiveBridge` 订单号由内部计数器生成（L171 `mock_{n:06d}`），调用方无法指定 | 幂等键缺失的直接证据 |
| [execution_policy.py](../core/execution_policy.py#L57) | `OrderIntent` 字段仅 `asset/asset_type/target_quantity/current_quantity/urgency`（L71-75），`action` 为 property（L88），`trade_quantity` L78 | 无 `client_order_id`/价格（价格在 `GuardContext`）/账户/策略 |
| [strategies.py](../order_strategy/strategies.py#L21) | `Order`(L21)/`TradeExecution`(L38) + TWAP(L118)/VWAP(L189)/Iceberg(L272) 均为**模拟切片**，`filled_qty`(L28) 本地累加 | 无回报驱动，切片与真实成交不同步 |
| [event_log.py](../core/event_log.py#L153) | `append`/`read` JSONL（L355 单行写入），`auto_flush` L116；**无 fsync、无唯一约束、无事务** | 事件流不能充当账本 |
| [safety_gate.py](../live/safety_gate.py) | P-052 闸门：`pre_trade_check` 方向分流 + fail-closed + 落盘 | 本批须在其**放行后**才发单，且发单结果回写 `on_order_result` |
| [safety_store.py](../live/safety_store.py) | mkstemp+fsync+`os.replace` 原子 JSON | 可作为账本最小持久化范式 |
| 目录 | **无 `services/`**；无 DB 层；`pyproject` 有 sqlalchemy/redis/celery 但**未使用** | 账本存储选型待裁决（U-P053-2） |

**关键结论**：P-053 不是「补一个连接类」，而是**补订单语义层**（幂等 + 状态机 + 账本 + 对账）；通道只是最后一段 I/O。

---

## 3. 外部证据

### 3.1 通道可用性变局（2026，最强约束）

| # | 事实 | 来源 |
|---|------|------|
| E1-1 | 中证协 + 中基协 **2026-08-28** 联合发布《证券公司交易信息系统接入管理规范（试行）》：全程管理、穿透管理、公平对待系统接入客户，不得为特定客户提供技术/速度便利 | [上海证券报](https://paper.cnstock.com/html/2026-08/29/content_2262321.htm) |
| E1-2 | 华鑫证券公告：依据该规范，**2026-10-30 收盘后统一关闭迅投 miniQMT** | [华鑫证券](https://www.cfsc.com.cn/www/html/132/2026-10-21/5E517A3E129F23CAE06329F7BC0AA46A.html) |
| E1-3 | miniQMT 属「外接」形态：本地独立 Python 进程生成指令、QMT 仅本地转发，策略不在 QMT 内置环境，**无法被券商穿透监管**，故受新规约束 | [财联社（转载）](http://m.toutiao.com/group/7690807397509497385/) |
| E1-4 | 2026-07-06 起部分券商新开 QMT 权限**不再包含 miniQMT**；存量「后续专项通知」逐步关闭 | [WTSolutions 事实核查](https://invest.wtsolutions.cn/posts/miniqmt-termination/) / [miniqmt.com](https://miniqmt.com/index.html) |
| E1-5 | 交易所行情/交易接入由局域网改广域网（2025-07 起），速度竞赛被拉平 | [央视网](http://big5.cctv.com/gate/big5/finance.cctv.com/2026/08/12/ARTIdjCoZYZSEZTDHRFc8Doc260812.shtml) |

**推论**：`qmt` 在本批只能是 `TerminalBridge`（半自动、人工确认、订单清单），且必须在 `ChannelCapability` 里声明「不可无人值守」。

### 3.2 四类通道的技术契约

| 通道 | 契约要点 | 自动化程度 | 来源 |
|------|----------|-----------|------|
| **miniQMT / xtquant** | 委托状态枚举：48 未报 / 49 待报 / 50 已报 / 51 已报待撤 / 52 部成待撤 / 53 部撤 / 54 已撤 / 55 部成（56/57 未取证）；撤单 `cancel_order_stock_async(account, order_id)`；撤单失败回调 `on_cancel_error`；同一 `session_id` 两次 connect 需间隔 >3 秒；**发行形态（O-R2 取证，Step 2 补）**：pip 包 **Windows x64 / Python 3.6–3.13**（[PyPI 官方](https://pypi.org/project/xtquant/)），**Linux 无官方支持**（仅第三方 RPyC 代理如 qmt-api） | 完整但**合规关闭** | [迅投 委托状态](http://docs.thinktrader.net/pages/198696/) / [XtTrader 字典](https://dict.thinktrader.net/nativeApi/xttrader.html) / [接口说明](http://docs.thinktrader.net/pages/ee0e9b/) / [快速开始·运行环境](http://dict.thinktrader.net/nativeApi/start_now.html) |
| **CTP** | `OnRtnOrder` 为私有流回报；`OrderRef` 每笔唯一（客户端不赋值则由服务端赋值）；`ReqUserLogout` 重建连接后 `SessionID` 重置、`MaxOrderRef` 可能从 0 计数；断线重连需**重新认证 + 信息上报 + 登录**（`ReqAuthenticate`→`OnRspAuthenticate`→`ReqUserLogin`）；查询流控默认 **1 笔/秒**（在途查询 1 笔），报单/撤单不受查询流控；请求返回 `-2` 未处理请求超许可、`-3` 每秒请求超许可 | 完整 | [OnRtnOrder](https://ctpdoc.jedore.top/3.7.3/JYJK/CTHOSTFTDCTRADERAPI/ONRTNORDER/) / [客户端开发指南](https://www.eastmoneyfutures.com/software/9809db08-c8cb-4cc4-b631-8a16f0c2dfb9/0f757a06-10a5-48c2-817e-362b42202b51/f3ec4355-a448-45d7-bd51-3124d046092a/CTPcdg_ch.pdf) / [看穿式认证参考代码](https://www.dzqh.com.cn/orient/file/jianguan/%E7%9C%8B%E7%A9%BF%E5%BC%8F%E7%9B%91%E7%AE%A1%E8%AE%A4%E8%AF%81%E5%8F%82%E8%80%83%E4%BB%A3%E7%A0%81.pdf) / [查询流控实践](https://www.vnpy.com/forum/topic/7680-bao-dan-liu-kong-cha-xun-liu-kong-he-hui-hua-shu-kong-zhi) |
| **券商机构 API（XTP/OES）** | 交易/行情/资金划拨全覆盖，提供委托回报与成交回报回调、分页查询；需机构户 + 审批 | 完整 | [XTP API](https://xtp.zts.com.cn/docs/xtp-api) / [XTP-Pro](https://xtp.zts.com.cn/docs/xtppro-api) |
| **QMT 标准版 / PTrade** | 策略运行在券商内置环境（Python 3.6.x 沙箱/云容器），文件与外网受限 | 半自动/不可外接 | Q1 §E2（既有调研）+ E1-3 |

> **证据等级说明**：E1-1..E1-4 为一手公告/监管转载；xtquant 枚举与 CTP 接口为一手 API 文档；「结算确认」仅见于券商客户端手册（[汇点手册](https://www.xinhu.cn/attachments/1801/15/da3467b68491e6f.pdf)），列为**弱证据**，本批不据此设计硬流程，只作为 runbook 提示。

### 3.3 订单状态机与崩溃恢复

| 锚点 | 内容 | 用途 |
|------|------|------|
| **FIX 4.4 Order State Changes**（官方 PDF） | `OrdStatus` 值域与优先级：`A` PendingNew / `0` New / `1` PartiallyFilled / `2` Filled / `4` Canceled / `8` Rejected / `C` Expired；终态优先级高于中间态 | 归一化状态机直接采用该值域（G3） |
| **上交所 STEP 接口规格（官方）** | OMS 与 TDGW 重连后：「应对上下行两个方向的消息进行恢复。建议 OMS **先对执行报告进行恢复**，以尽可能更新断连前申报订单的状态。OMS 可在恢复一段时间后，对仍然处于『已报但未确认』状态的订单**进行重新申报**」 | 崩溃恢复的**标准顺序**：先成交/执行报告 → 再处理未确认（G4） |
| 工程实践 | 用 `client_order_id` 在重启后查询「这笔到底成没成」；状态机 `pending→routed→acked→partial→filled/canceled/rejected` | 恢复必须依赖幂等键（G2/G4） |

来源：[FIX Order State Changes](https://www.fixtrading.org/wp-content/uploads/download-manager-files/Order-State-Changes.pdf) / [FIX 生命周期解读](https://fixparser.zagtrader.com/guides/fix-order-lifecycle) / [上交所 STEP 规格（债券平台）](https://www.sse.com.cn/services/tradingtech/data/c/10800115/files/d4ed0a7c66e34ac5af68709e10b29568.pdf) / [上交所 STEP 规格（期权平台）](http://www.sse.com.cn/services/tradingtech/development/c/10822595/files/d5757f624e474a2a986c1aad0353f52e.pdf) / [崩溃恢复实践](https://tierzero.dev/blog/trading-bot-order-state-machine-idempotency-crash-recovery)

### 3.4 幂等与账本

| 锚点 | 内容 | 用途 |
|------|------|------|
| client order id | 在**首次提交前生成一次**（UUID 或 `strategy+signal_ts` 确定性哈希），所有重试复用；**绝不在重试循环内重新生成** | G2 |
| 成交去重 | 交易所 `fill_id` 唯一约束；重复投递只入账一次 | G5 |
| 事务性 outbox | 业务表与 outbox 同库同事务提交 → relay 发布；保证 **at-least-once**，消费端按事件唯一 ID 去重（inbox）→ effectively-once | G5（账本写入与事件发布不可分裂） |

来源：[Idempotency & Duplicate-Order Prevention](https://www.getswoopr.com/trading-technology/apis-bots-webhooks-strategy-automation/idempotency-and-duplicate-order-prevention/) / [Trading Bot Order State Machines](https://tierzero.dev/blog/trading-bot-order-state-machine-idempotency-crash-recovery) / [Transactional Outbox](https://www.alekseialeinikov.com/en/blog/topics/architecture/transactional-outbox-pattern) / [Outbox+Inbox](https://zylos.ai/research/2026-06-05-transactional-outbox-pattern-microservices/)

### 3.5 对账

| 锚点 | 内容 | 用途 |
|------|------|------|
| **JR/T 0300—2023**（行业标准） | 《证券公司与资产管理产品管理人及服务机构间对账数据接口》：统一对账数据接口与释义，含 `scrBal` 证券余额等字段 | 对账字段命名与分类（G6） |
| 行业实践 | 日内多次对账；差异三级：**dust**（<0.1% 且 <固定下限）静默对齐并记录 / **missed event**（可在成交流水找到的漏记）回放并标记已对账 / **unresolved** 告警并暂停该账户 | 差异分级与停机策略（G6） |

来源：[JR/T 0300—2023（上交所转发）](https://www.sse.com.cn/lawandrules/regulations/csrcannoun/c/10751838/files/38d0a2f3c4b643879286c7c26ad2e520.pdf) / [Intraday Position Reconciliation](https://www.getswoopr.com/trading-technology/oms-ems-reconciliation/intraday-position-reconciliation/) / [Position Reconciliation 分级](https://blockcircle.com/blog/position-reconciliation-bot-exchange-state)

### 3.6 流控与监管阈值

| 锚点 | 内容 | 用途 |
|------|------|------|
| 程序化交易实施细则（2025-07-07 施行） | 单账户每秒申报/撤单 **≥300 笔** 或 单日 **≥20000 笔** 认定为高频交易，差异化监管 | 通道级速率上限的**外部红线**（区别于 P-052 内部默认 1 笔/秒、1000 笔/日） |
| 上交所通知 | 重点监控「最高申报速率 ≥300 笔/秒，或单日最高申报笔数 ≥20000 笔」 | 同上 |
| CTP 查询流控 | 默认 1 笔/秒；`-2`/`-3` 错误码 | 查询必须令牌桶 + 退避（G8） |

来源：[上交所通知](http://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250612_10781707.shtml) / [央视网细则解读](http://big5.cctv.com/gate/big5/finance.cctv.com/2026/08/12/ARTIdjCoZYZSEZTDHRFc8Doc260812.shtml) / [CTP 请求返回码](https://documentation.help/CTP-API-cn/REQQRYSECAGENTTRADEINFO.html)

### 3.7 开源架构参照

| 锚点 | 内容 | 用途 |
|------|------|------|
| VeighNa (vnpy) | `BaseGateway` 抽象（connect/subscribe/send_order/cancel_order/query_*）+ `on_order/on_trade/on_position` 事件推送 + `MainEngine`/`OmsEngine` 聚合 + `RPC` 网关支持跨进程 | 通道插件化与事件驱动 OMS 的成熟范式（G1/G4） |

来源：[vnpy 功能介绍](https://www.vnpy.com/docs/cn/community/info/introduction.html) / [委托与成交状态回传源码分析](https://www.vnpy.com/forum/topic/60-vnpy-jiao-yi-suo-fan-hui-wei-tuo-he-jiao-yi-zhuang-tai-dao-ce-lue-de-yuan-dai-ma-fen-xi)

---

## 4. 缺口矩阵 G1-G10

| ID | 缺口 | 现状证据 | 优先级 | 对应锚点 |
|----|------|----------|--------|----------|
| G1 | 无真实通道适配（仅 ABC + Mock） | `live_bridge.py` L69/L144 | P1 | §3.2/§3.7 |
| G2 | 无客户端订单号/幂等（订单号由 Mock 内部生成） | L171 | P1 | §3.4 |
| G3 | 无归一化订单状态机（5 个自由字符串） | L56 | P1 | §3.3 FIX |
| G4 | 无回报驱动、无崩溃恢复（无 `query_orders`/`query_trades`、无未确认重发） | ABC 仅 4 方法 | P1 | §3.3 SSE |
| G5 | 无账本（持仓/现金/加权成本/已实现盈亏、唯一约束） | 无模块 | P1 | §3.4 |
| G6 | 无对账（逐笔/余额、差异分级、停机） | 无模块 | P2 | §3.5 |
| G7 | 无通道能力门（账户层级/API/品种/速率/报备） | 无 | P1 | §1.1 |
| G8 | 无流控/查询限频（CTP 1 次/秒；300/20000 红线） | 无 | P2 | §3.6 |
| G9 | 无凭据注入/每账户单写者约束 | 无 | P2 | Q1 §推荐 |
| G10 | 与 P-052 闸门无原子衔接（放行→发单→回报回写） | `safety_gate.py` 独立 | P1 | P-052 契约 |
| G11 | 交易日历/交易时段状态机缺失（F-R9-P2：P-053 验收加时段状态机）；公司行为事件表与对账归因缺失（除权除息/送转/配股须先归因再判异常） | 无任何实现 | P2 | 总纲 L270 + Q12 L421 + F-R9-P2 L419 |

---

## 5. 方案选项与取舍

| 选项 | 内容 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **A. 语义层优先 + 适配器后置** | 先建 `ChannelCapability` + 订单语义层（id/状态机/账本/对账）+ `MockChannel`，适配器只做协议翻译 | 可测试、不被通道可用性阻塞、符合 D4 | 暂不能真实下单 | **推荐** |
| B. 直接接 QMT/xtquant | 复用旧路线 | 上手快 | 合规已关闭（E1-2/E1-3）、Windows 绑定 | 拒 |
| C. 直接接 CTP 全量 | 期货优先落地 | 真自动化 | 股票缺口未解、需 CTP 环境与仿真账号 | 降级为后续连通演练 |
| D. 引入 vnpy 作为通道层 | 直接复用其 gateway/OMS | 生态成熟 | 重依赖、与现有 `OrderIntent`/`SafetyGate` 双栈、契约冲突 | 拒（只借鉴架构） |
| E. 只做半自动清单 | 平台出单、人工执行 | 零对接风险 | 不满足 F6「完整集成」验收 | 仅作 TerminalBridge 子集 |
| F. 先建 DB 账本（SQLite） | 账本落 SQLite 事务 | 唯一约束/事务天然 | 新增依赖与迁移成本 | 待裁（U-P053-2） |

---

## 6. 推荐方案（供 Step 3 DESIGN 展开）

### 6.1 模块分层（依赖方向 `live → core`，不 import `filter`/`services`）

```
live/
  channel.py      ChannelCapability / ChannelError / ChannelAdapter(ABC) / ChannelState
  orders.py       OrderState(FIX 值域) / OrderRecord / FillRecord / ClientOrderId
  ledger.py       Ledger / PositionBook / CashBook / LedgerSnapshot（双重记账 + 唯一约束）
  reconcile.py    ReconcileReport / Break / reconcile_positions / reconcile_cash / reconcile_fills
  session_calendar.py TradingSession / session_state(ts)（时段状态机；synthetic 日历先行）
  corporate_actions.py CorporateAction 事件表 + 对账归因（除权除息/送转/配股；数据源粒度 → U-P053-11）
  adapters/
    mock.py       MockChannel（FakeTransport + 录制帧回放）
    ctp.py        CtpChannel（协议翻译；本批不连真实前置）
    broker_api.py BrokerApiChannel（XTP/OES 语义占位）
    terminal.py   TerminalChannel（订单清单 + 人工确认回填）
```

### 6.2 核心契约（草案）

| 契约 | 关键字段 |
|------|----------|
| `ChannelCapability` | `channel_id` / `account_level`（institutional/retail）/ `products` / `max_per_sec` / `max_per_day` / `supports_client_order_id` / `supports_cancel` / `supports_query` / `autonomous`（bool）/ `filing_status` |
| `ClientOrderId` | 确定性生成：`hash(strategy_id, account_id, symbol, side, target_qty, signal_ts)`；重试复用 |
| `OrderState` | `PENDING_NEW/NEW/PARTIALLY_FILLED/FILLED/CANCELED/REJECTED/EXPIRED/PENDING_CANCEL/UNKNOWN`（FIX 对齐 + 未知态） |
| `OrderRecord` | `client_order_id` / `broker_order_id` / `state` / `filled_qty` / `avg_price` / `last_update_ts` / `revision` |
| `FillRecord` | `client_order_id` + `fill_seq`（唯一）/ `qty` / `price` / `fee` / `ts` |
| `LedgerSnapshot` | `cash` / `reserved` / `positions{symbol: qty, cost}` / `realized_pnl` / `version` |
| `ReconcileReport` | `as_of` / `breaks[]{kind, symbol, local, remote, delta, level}` / `level∈{ok,dust,missed,unresolved}`；阈值引用 parity（总纲 L244 立项校准 + Q10 paper↔live 行） |

### 6.3 状态机（FIX 对齐）

```
PENDING_NEW ──ack──> NEW ──fill──> PARTIALLY_FILLED ──fill──> FILLED
     │                 │                  │
     ├──reject──> REJECTED                └──cancel──> CANCELED
     └──timeout──> UNKNOWN ──query──> (任一确定态)
NEW/PARTIALLY_FILLED ──cancel_req──> PENDING_CANCEL ──ack──> CANCELED
                                                    └──reject──> 回原态
```
不变式：终态不可逆；`FILLED`/`CANCELED` 后 `filled_qty` 不再变化；`UNKNOWN` 必须由查询收敛，不得凭猜测推进。

### 6.4 崩溃恢复顺序（SSE 锚点直译）

1. 启动 → `ChannelCapability` 自检（不满足则通道置 `DISABLED`，不接单）。
2. `query_trades`（先成交）→ 回放补账 → 标记 `missed/duplicate`。
3. `query_orders` → 更新进行中订单状态（覆盖本地 `UNKNOWN`/`PENDING_*`）。
4. 仍处 `NEW` 且本地无确认、超宽限期 → **只查询不重发**（默认）；重发须显式开关（U-P053-4）。
5. 对账 → 生成 `ReconcileReport` → `unresolved` 则账户停机（复用 P-052 kill）。

### 6.5 与 P-052 的衔接（G10）

`submit(intent, ctx, ts)`：`SafetyGate.pre_trade_check` → 放行才 `channel.place` → 回报 `on_order_result(rejected=...)` 与 `ledger.apply(fill)` → 全部写审计（`audit.order`/`audit.fill`/`audit.reconcile`）。闸门未放行时**不得**产生任何通道调用。

### 6.6 流控（G8）

- 通道侧令牌桶：`max_per_sec`/`max_per_day` 取 `min(通道声明, 监管红线, P-052 内部默认)`；
- 查询与报单分桶（CTP 查询 1/s 独立）；
- `-2`/`-3` 类错误按指数退避，连续失败触发 P-052 `DISCONNECT` 策略。

---

## 7. 未决项（Step 2 复审 + 用户裁决）

| ID | 问题 | 选项 | 倾向 |
|----|------|------|------|
| U-P053-1 | 首发「完整通道」选谁 | CTP 仿真 / 券商机构 API / 两者仅语义层 | **语义层先行；首个真实协议连通 = CTP（SimNow 第二套环境，零审批）；券商机构 API 作第二目标（测试账号需审核）**——见 §12.1 |
| U-P053-2 | 账本存储 | JSON 原子写（复用 safety_store）/ SQLite / Postgres | **SQLite（stdlib `sqlite3` + WAL + 单写者进程）；JSON 原子写只留给 P-052 安全状态**——见 §12.2（零新依赖） |
| U-P053-3 | 状态机值域 | FIX 全量 / 精简 7 态 | FIX 全量（映射成本低、可对表） |
| U-P053-4 | `已报未确认` 是否自动重发 | 只查询 / 宽限期后重发 / 人工确认 | **只查询 + 宽限期 + 人工确认**（IBKR / vnpy / FIX / CTP 四锚点同向）——见 §12.3 |
| U-P053-5 | 对账阈值 | 沿用 Q10 / 按流动性分档 | 沿用 Q10，配置化；**须按账户规模校准并写入验收**（总纲 L244 + Q10 L374 待确认），Step 3 定默认 |
| U-P053-6 | 每账户单写者形态 | 进程内单例 / 独立进程 + socket / Redis 锁 | 进程内单例 + 文件锁（最小） |
| U-P053-7 | 半自动通道留痕 | 订单清单 CSV / JSON / 审计事件 | CSV + `audit.order` 双写 |
| U-P053-8 | 是否新增第三方依赖 | 零依赖 / SQLite / FIX 引擎 | **零新依赖优先**（与 P-051c/P-052 一致） |
| U-P053-9 | TerminalBridge 是否本批实现 | 是 / 仅能力门占位 | 占位 + 清单生成（U-P053-1 联动） |
| U-P053-10 | 与 P-056（CTP 期货月差）边界 | 通道 vs 策略 | P-053 只做通道语义，不碰月差逻辑 |
| U-P053-11 | corporate_actions / session_calendar 数据源与粒度 | synthetic 事件表先行 / AKShare 兜底 / 柜台源 | **synthetic 先行**（Q12 推荐 7）；AKShare 兜底、柜台源实盘时再接（Step 2 增补，G11） |

**跨批次移交（不得遗忘）**

- O-P043-2：订单/成交事件类型（P-053 承接）；
- O-P043-1：`EventLogPlugin.log_*` 死 API 去留（P-053/P-054 复核）；
- U-P045-1：`entry_price` 收盘近似精化（P-053 成交回填后可用真实均价）；
- P-052 D-G7：`cancel_all` 只对 Bridge；本批 `ChannelAdapter.cancel_all()` 需保持同语义。
- Q11 净额撮合：本批只做账本侧预留（§1.2），跨策略净额撮合后置——P-058（多空/月差模板）立项时复核（Step 2 增补）。

---

## 8. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 通道权限不可得（机构户审批） | 无法真实下单 | 语义层 + Mock 先行；连通作为独立验收项（D4） |
| 回报乱序/重复/丢失 | 账实不符 | FIX 状态机 + `fill_seq` 唯一约束 + 启动先回放成交 |
| 断线期间「已报未确认」 | 重复下单 | 幂等键 + 先查询 + 宽限期 + 默认不自动重发 |
| 查询流控（CTP 1/s） | 恢复慢、被拒 | 独立令牌桶 + 退避 + 批量分页 |
| 事件日志非事务 | 账本漂移 | 账本独立持久化；事件仅审计，不作账 |
| 多进程双写 | 重复发单 | 每账户单写者 + 文件锁 |
| 监管口径变化 | 合规风险 | `ChannelCapability.filing_status` + runbook 定期复核 |

---

## 9. 用例与门禁估算（供 Step 7 校准）

| 组 | 内容 | 估算 |
|----|------|------|
| G（能力门） | 自动/半自动判定、品种、速率取最小值、报备缺失拒绝 | 10 |
| O（订单语义） | client_order_id 确定性、重试不变、状态机合法/非法迁移、终态不可逆 | 14 |
| L（账本） | 双重记账守恒、fill 去重、加权成本、已实现盈亏、快照往返 | 14 |
| R（对账） | 逐笔/余额、dust/missed/unresolved 分级、停机触发 | 12 |
| F（流控/恢复） | 令牌桶、查询分桶、退避、先成交后订单的恢复顺序 | 8 |
| E（端到端） | 闸门→通道→回报→账本→对账 全链；kill 后零调用 | 4 |
| **合计** | 6 文件 | **≈62** |

**门禁预估**：pytest **1214 → ≈1276** / golden **22 不变** / mypy **128 → ≈134**（新增 6 模块，`live` 已纳入）/ black **261 → ≈267**（+6）/ `tests/*.py` **132 → 138** / `live/*.py` **3 → 9**。（若 U-P053-2 采 SQLite 仓储，再 +1 模块 → mypy **≈135** / `live/*.py` **10**，用例数不变；见 §12.2）

---

## 10. 外部来源清单

**监管/官方**
- [《证券公司交易信息系统接入管理规范（试行）》发布（上海证券报）](https://paper.cnstock.com/html/2026-08/29/content_2262321.htm)
- [华鑫证券：关闭 miniQMT 公告](https://www.cfsc.com.cn/www/html/132/2026-10-21/5E517A3E129F23CAE06329F7BC0AA46A.html)
- [上交所：关于加强程序化交易管理有关事项的通知](http://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250612_10781707.shtml)
- [上交所 STEP 接口规格（债券平台）](https://www.sse.com.cn/services/tradingtech/data/c/10800115/files/d4ed0a7c66e34ac5af68709e10b29568.pdf)
- [上交所 STEP 接口规格（期权平台）](http://www.sse.com.cn/services/tradingtech/development/c/10822595/files/d5757f624e474a2a986c1aad0353f52e.pdf)
- [JR/T 0300—2023 对账数据接口](https://www.sse.com.cn/lawandrules/regulations/csrcannoun/c/10751838/files/38d0a2f3c4b643879286c7c26ad2e520.pdf)
- [JR/T 0016—2014 期货交易数据交换协议](http://www.csrc.gov.cn/csrc/c101902/c1039226/1039226/files/%E9%99%84%E4%BB%B6%EF%BC%9A%E3%80%8A%E6%9C%9F%E8%B4%A7%E4%BA%A4%E6%98%93%E6%95%B0%E6%8D%AE%E4%BA%A4%E6%8D%A2%E5%8D%8F%E8%AE%AE%E3%80%8B.pdf)
- [FIX Order State Changes（FIX Trading Community）](https://www.fixtrading.org/wp-content/uploads/download-manager-files/Order-State-Changes.pdf)

**通道 API**
- [迅投：委托状态枚举](http://docs.thinktrader.net/pages/198696/) / [XtQuant.Xttrade](https://knowledge.thinktrader.net/docs/xtquant/xttrader.html) / [接口说明](http://docs.thinktrader.net/pages/ee0e9b/)
- [CTP：OnRtnOrder](https://ctpdoc.jedore.top/3.7.3/JYJK/CTHOSTFTDCTRADERAPI/ONRTNORDER/) / [CTP 客户端开发指南](https://www.eastmoneyfutures.com/software/9809db08-c8cb-4cc4-b631-8a16f0c2dfb9/0f757a06-10a5-48c2-817e-362b42202b51/f3ec4355-a448-45d7-bd51-3124d046092a/CTPcdg_ch.pdf) / [看穿式监管认证参考代码](https://www.dzqh.com.cn/orient/file/jianguan/%E7%9C%8B%E7%A9%BF%E5%BC%8F%E7%9B%91%E7%AE%A1%E8%AE%A4%E8%AF%81%E5%8F%82%E8%80%83%E4%BB%A3%E7%A0%81.pdf)
- [中泰 XTP API](https://xtp.zts.com.cn/docs/xtp-api) / [XTP-Pro](https://xtp.zts.com.cn/docs/xtppro-api)

**工程实践**
- [vnpy 功能介绍](https://www.vnpy.com/docs/cn/community/info/introduction.html) / [委托与成交状态回传源码分析](https://www.vnpy.com/forum/topic/60-vnpy-jiao-yi-suo-fan-hui-wei-tuo-he-jiao-yi-zhuang-tai-dao-ce-lue-de-yuan-dai-ma-fen-xi) / [报单/查询流控](https://www.vnpy.com/forum/topic/7680-bao-dan-liu-kong-cha-xun-liu-kong-he-hui-hua-shu-kong-zhi)
- [Idempotency & Duplicate-Order Prevention](https://www.getswoopr.com/trading-technology/apis-bots-webhooks-strategy-automation/idempotency-and-duplicate-order-prevention/) / [订单状态机与崩溃恢复](https://tierzero.dev/blog/trading-bot-order-state-machine-idempotency-crash-recovery)
- [Transactional Outbox](https://www.alekseialeinikov.com/en/blog/topics/architecture/transactional-outbox-pattern) / [Outbox+Inbox 端到端可靠性](https://zylos.ai/research/2026-06-05-transactional-outbox-pattern-microservices/)
- [Intraday Position Reconciliation](https://www.getswoopr.com/trading-technology/oms-ems-reconciliation/intraday-position-reconciliation/) / [Position Reconciliation 分级](https://blockcircle.com/blog/position-reconciliation-bot-exchange-state)
- [FIX Order Lifecycle 解读](https://fixparser.zagtrader.com/guides/fix-order-lifecycle)

**补充案例（2026-11-21，U-P053-1/2/4 锚点）**
- [SimNow 产品与服务（上期技术官方）](https://www.simnow.com.cn/product.action) / [SimNow 常见问题](https://www.simnow.com.cn/static/SimNowFAQ.action) / [SimNow 简介](https://www.simnow.com.cn/static/contactus.action)
- [中泰 XTP FAQ（非 API 类，含测试账号申请）](https://xtp.zts.com.cn/basic?id=120006&key=FAQ%28other%29&name=FAQ%EF%BC%88%E9%9D%9EAPI%E7%B1%BB%EF%BC%89) / [XTP 机构服务平台](https://inst.zts.com.cn/index) / [XTP 资方赋能](https://xtp.zts.com.cn/basic?id=150003&key=Investor-Empowerment&name=%E8%B5%84%E6%96%B9%E8%B5%8B%E8%83%BD) / [SmartX 开发者指南（测试账号流程）](https://smarttest.ztqft.com/sdkDoc/introduction/1.0.0/guide/howTo_develop.html)
- [IBKR：Order States and Partial Fills（重启用 reqOpenOrders 重建视图）](https://www.interactivebrokers.com/campus/ibkr-quant-news/order-states-and-partial-fills-on-the-ibkr-api-keeping-your-systems-view-of-each-order-in-step-with-the-account/) / [IBKR：API client's orders](https://www.interactivebrokers.com/docs/tws-api/doc/order-management/requesting-currently-active-orders/api-clients-orders) / [IBKR：Keeping an IBKR API System Running Unattended](https://www.interactivebrokers.com/campus/ibkr-quant-news/keeping-an-ibkr-api-system-running-unattended/)
- [Freqtrade：Advanced Post-installation（默认 SQLite）](https://docs.freqtrade.io/en/2025.9/advanced-setup/) / [Hummingbot：Connect External Database（默认本地 SQLite）](https://hummingbot.org/client/global-configs/external-db/) / [Hummingbot：hbot CLI（`.sqlite` 为 trades DB）](https://hummingbot.org/client/hbot-cli/)
- [SQLite：Write-Ahead Logging（官方）](https://www.sqlite.org/wal.html) / [SQLite on Linux：Transactions 与 ACID（官方 LPC-2019）](https://www.sqlite.org/lpc2019/doc/6c0c739994/briefing.md)
- [Alpaca：Placing Orders（client_order_id 去重）](https://docs.alpaca.markets/us/docs/orders-at-alpaca) / [Alpaca：Trading CLI idempotent orders](https://docs.alpaca.markets/us/docs/alpacas-cli)
- [vnpy：交易接口（连接后立即查询账号/持仓/委托/成交）](https://www.vnpy.com/docs/cn/community/info/gateway.html) / [vnpy 社区：断线后持仓维护（CTP 6 秒推送）](https://www.vnpy.com/forum/topic/5700-jiao-yi-zhong-vnpybu-xiao-xin-tui-chu-huo-duan-wang-chi-cang-shu-ju-zen-yao-wei-hu)
- [FIX.4.2 字段表（PossDupFlag 语义）](https://fiximate.fixtrading.org/legacy/en/FIX.4.2/fields_sorted_by_tagnum.html) / [FIX ExecutionReport](https://fiximate.fixtrading.org/legacy/en/FIX.5.0SP2/body_5756.html)
- [华鑫证券官网：《关于关闭迅投 miniQMT 系统功能的公告》一手原文（自引《接入管理规范（试行）》）](https://www.cfsc.com.cn/www/html/132/2026-10-21/5E517A3E129F23CAE06329F7BC0AA46A.html)（Step 2 复审补）
- [PyPI：xtquant（Windows x64 / Python 3.6-3.13，O-R2 取证）](https://pypi.org/project/xtquant/) / [迅投：XtTrader 委托状态字典](https://dict.thinktrader.net/nativeApi/xttrader.html) / [迅投：快速开始·运行依赖环境](http://dict.thinktrader.net/nativeApi/start_now.html)（Step 2 复审补）

---

## 11. Step 2 复审输入（待核清单）

1. **事实核对**：E1-1..E1-4 是否均在检索结果中有直接原文（不得二次推断）；xtquant 48-55 枚举是否逐值可核；CTP「查询 1 笔/秒」是否为接口内置而非券商配置差异。
2. **边界核对**：本批是否**未**触碰 P-052 已关闭契约（`pre_trade_check` 签名、`cancel_all` 语义、审计事件 8 常量）；是否**未**引入 `filter`/`services` 依赖边。
3. **可行性核对**：G1-G10 是否与仓库实际一致（行号、模块存在性）；§9 估算是否与既有 `live/` 规模自洽。
4. **口径核对**：Q10/Q11/Q1 的既有裁决是否被本文件**改写**（只允许引用，不允许重开）。
5. **反向证据**：是否存在「股票端仍有合规完整外接通道」的证据被遗漏（若有，U-P053-1 需改）。
6. **补充调研核对（§12）**：SimNow「零审批 + 第二套环境不提供结算」、SQLite「零新依赖 + 单写者」、IBKR/FIX/vnpy/CTP「只查询不重发」三条锚点是否成立；N-1..N-6 是否有遗漏或误读（尤其 N-2 第三交易日、N-6 行情配额原文待复核）。
7. **复审回执**：[REVIEW_p053_step2_research.md](REVIEW_p053_step2_research.md)——GLM-5.3-Flash 异构复审 **0 P1 / 3 P2 / 3 P3 全部当轮修复**（Q12 两模块 G11/U-P053-11、parity 校准义务 U-P053-5、O-R2 取证回填、§2 措辞、Q11 净额移交、§12.1 时序澄清）。

---

## 12. 未决项补充调研：U-P053-1 / 2 / 4 外部案例锚点（2026-11-21）

> **目的**：把 §7 三项「策略性选择」从工程口味升级为**有外部案例支撑**的方案锚点。
> **证据等级**：官方文档 / 开源项目官方文档 = E1-E2；行业文章 = E2；原文表述存疑处显式标注「待复核」，不用于硬设计。

### 12.1 U-P053-1：首发「完整通道」选谁

| # | 案例（官方） | 事实（原文口径） | 对选型的含义 |
|---|--------------|------------------|--------------|
| A | **SimNow（上期技术，上期所全资子公司）** | 免费注册即可用；`BrokerID=9999`；三组交易/行情前置（30001/30011、30002/30012、30003/30013）+ **7×24 环境**（40001/40011）；支持六所期货与期权；初始资金 2000 万；**注册后默认 `APPID=simnow_client_test`、认证码 `0000000000000000`（16 个 0），默认开启终端认证，程序化用户可选择不开终端认证接入**；第二套环境**仅服务 CTP API 开发需求、不提供结算等其它服务**，且**新注册用户需等到第三个交易日**才能使用 | 期货端存在**零审批、官方、可编程**的 CTP 协议环境，是唯一"当天可拿到真实协议"的完整通道 |
| B | **中泰 XTP** | FAQ：接入需**专业投资者资质认定**（中泰齐富通 APP 认证）、程序化接入须符合合规要求；**测试账号由官网申请、公司审核后邮件发放**；XTP-Pro 行情有订阅配额（单市场 100 只；全市场订阅上限原文表述**待复核**） | 券商机构 API **有官方测试环境但非即时**，审核周期不在我方控制内 |
| C | **中泰尚元机构服务平台** | 面向**私募、公募、证券、银行、信托、保险、期货等机构客户**提供一体化服务 | 机构 API 的商业门槛在"客户资质"，不在技术 |
| D | **QMT（§3.1）** | 华鑫 2026-10-30 收盘关闭 miniQMT；miniQMT 属外接形态受 2026-08-28 新规约束 | 股票端零审批路径已消失，不能作为首发通道 |

**结论（建议裁决）**：**U-P053-1 = 语义层先行；首个"真实协议连通"目标定为 CTP（SimNow 第二套环境），券商机构 API（XTP/OES）列为第二目标，以"测试账号审核通过 + 专业投资者资质"为前置**。

- 理由：SimNow 零审批 + 官方 + 与 §3.2/§3.3 的 CTP 契约同源（`OrderRef`/`OnRtnOrder`/查询 1 笔/秒 全部可验）；XTP 审核不可控，不得进关键路径（D4）。
- 边界：CTP 是期货/期权 → 本批只做**通道语义**，月差/期货账目归 P-056（§7 U-P053-10 不变）。
- 时序（Step 2 澄清，F-6）：连通演练**非本批**——语义层验收通过后单列演练前置项（§0.5「本批不接真实网络」不变；N-2 提示若排演练须提前注册 SimNow）。

### 12.2 U-P053-2：账本存储

| # | 案例（官方） | 事实（原文口径） | 对选型的含义 |
|---|--------------|------------------|--------------|
| A | **Freqtrade**（开源实盘机器人） | 实盘默认 `sqlite:///tradesv3.sqlite`，dry-run 默认 `tradesv3.dryrun.sqlite`；可用 SQLAlchemy `db_url` 切服务端库 | 单机单写 SQLite 是实盘机器人**主流默认** |
| B | **Hummingbot**（开源做市机器人） | 成交**默认存本地 SQLite**（`data/hummingbot_trades.sqlite`，跨重启持久）；官方明确"默认 SQLite 可能不够用，可通过 SQLAlchemy 换外部 RDBMS" | 与 A 同一范式：**SQLAlchemy 抽象 + SQLite 默认 + 需要时升服务端库** |
| C | **本仓依赖现况** | `pyproject.toml` L42 已声明 `sqlalchemy>=2.0.0`（当前未使用）；`sqlite3` 为 Python 标准库 | 选 SQLite **不新增任何依赖**，满足 U-P053-8 |
| D | **SQLite 官方（WAL / ACID）** | WAL 下**读不阻塞写、写不阻塞读**，但**同一时刻只有一个写者**；崩溃/断电后仍 ACID（rollback journal / WAL / 原子写三路径）；无共享内存时用 `locking_mode=EXCLUSIVE` 保证单进程独占 | 契约可写成：**单写者进程 + WAL + 事务包裹 outbox** |
| E | 对照：现有 `live/safety_store.py` | mkstemp + `fsync` + `os.replace` 原子 JSON | 适合**单文档小状态**（kill/熔断基准），不适合**追加型流水**（fill 唯一约束、按 `client_order_id` 检索、聚合对账） |

**结论（建议裁决）**：**U-P053-2 = SQLite（stdlib `sqlite3`，WAL，单写者进程）承载账本流水 + 保留 JSON 原子写仅用于 P-052 安全状态**；`Ledger` 经 `LedgerStore` Protocol 隔离，SQLAlchemy/Postgres 留作后续。

- 理由：零新依赖（`sqlite3` 标准库；SQLAlchemy 已在依赖内）、天然唯一约束与事务、可测（`tmp_path` / `:memory:`）。
- 约束：**账本与 outbox 必须同库同事务**（WAL 下多库事务非原子，见 §12.4 N-4）。
- 估算影响：新增 `live/ledger_store.py`（仓储）→ `live/*.py` 3 → **10**、mypy **≈135**；账本 14 例覆盖仓储往返与唯一约束，**用例总数不变**（§9）。

### 12.3 U-P053-4：「已报未确认」是否自动重发

| # | 案例（官方） | 事实（原文口径） | 对选型的含义 |
|---|--------------|------------------|--------------|
| A | **IBKR：Order States and Partial Fills** | 重启后**先重建视图再发新单**：用**同一 client ID** 重连 → `reqOpenOrders` 拉活动委托（逐条 `openOrder`+`orderStatus`，`openOrderEnd` 结束，**列表永不含已完成订单**）→ 再拉已完成订单与 executions | 权威范式 = **查询重建**，不是重发 |
| B | **IBKR：Unattended 运行** | TWS/IB Gateway **每日按设计重启**，每周还需人工 2FA 登录；系统须把重启当正常事件、留静默期 | **计划内断连是常态** → 恢复流程必须可重复执行且幂等 |
| C | **vnpy 官方（交易接口）** | 连接接口后"**立刻进行查询工作**：查询账号信息、查询持仓、查询委托信息、查询成交信息" | 行业通行顺序：**连接即查询**，与 §6.4 SSE 顺序一致 |
| D | **FIX 语义** | `PossDupFlag`＝"该序号消息可能为重传"；`Resend Request`/`GapFill` 是**会话层**消息恢复；`ExecutionReport`（`OrdStatus`）才是订单状态真相源 | 重发是**会话层补消息**，不是"重新下一笔业务单"；交易所不保证对重复业务单去重 |
| E | **Alpaca（现代券商 API）** | `client_order_id` 客户端指定（≤128 字符）；**提供时 API 拒绝相同 id 的重复提交**，防重试造成重复下单；订单可凭该 id 查状态 | 幂等键既是**防重**手段，也是**"先查询"的检索键** |
| F | **CTP（§3.2）** | `OrderRef` 每笔唯一；登出重连后 `SessionID` 重置、`MaxOrderRef` 可能从 0 计数 | 本地计数器**不能**作为"是否已发"的证据，只能靠柜台查询 |

**结论（建议裁决）**：**U-P053-4 = 只查询 + 宽限期 + 人工确认，不自动重发**，并固定"重连三查询"顺序：`query_trades`（先成交）→ `query_orders`（再状态）→（可选）`query_positions` 后对账；`UNKNOWN` 只能由查询收敛。

- 自动重发的**升级前提（四条件缺一不可）**：柜台确认该 `client_order_id` 不存在 + 超宽限期 + 显式开关 + 审计留痕。记为 U-P053-4 的可选升级路径，不进本批。

### 12.4 本次补充调研的残余发现（新登记）

| ID | 发现 | 影响 / 处置 |
|----|------|-------------|
| N-1 | SimNow 第二套环境**不提供结算服务** | 对账全链**不能**靠 SimNow 验证；仍用 FakeTransport + 录制帧（§0.5 不变） |
| N-2 | SimNow 新注册需**第三个交易日**才能用 API 环境 | 若排连通演练，须**提前注册**（时间前置，不阻塞语义层） |
| N-3 | XTP 测试账号需**审核 + 专业投资者资质** | 外部不可控 → 不得进关键路径；Step 3 只留 `BrokerApiChannel` 语义占位 |
| N-4 | SQLite WAL 下**多库事务非原子** | 账本与 outbox 同库同事务；禁止跨库分摊 |
| N-5 | IBKR 每日重启说明"**计划内断连是常态**" | 通道接口需区分"计划内重启"与"异常断线"，恢复流程幂等可重入 |
| N-6 | XTP-Pro 行情订阅配额（单市场 100 只，全市场上限**待复核**） | 仅影响后续行情侧；本批不设计行情通道 |

**综合结论**：U-P053-1 / 2 / 4 三项**均可收敛为非阻塞决策**（上表"结论（建议裁决）"），Step 3 DESIGN 可直接采用；其余 U-P053-3/5/6/7/8/9/10 属工程口径，由 Step 3 定案。
