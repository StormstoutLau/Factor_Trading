# RESEARCH：P-052 实盘安全闸门（kill switch / 网关事前风控 / 账户熔断 / 合规报告 / 鉴权 / 审计 / 故障处置）

> **批次**: P-052 · **Step 1 调研** · 日期 2026-11-21
> **上游**: [UPGRADE_MASTER_PLAN §3.0](UPGRADE_MASTER_PLAN.md)（S1-S7 硬约束，L153-L167）；[UPGRADE_MASTER_PLAN §5](UPGRADE_MASTER_PLAN.md)（L269 P-052 行）；[关键路径 L277](UPGRADE_MASTER_PLAN.md)（…→051→**052**→053→054→055）；[PROGRESS §1.4](PROGRESS.md)（P-052 行 L202）
> **代码证据时点**: HEAD `1f950c6`（工作区干净；`git rev-parse HEAD` / `git status --short` 实测）
> **基线读数**: pytest **1144** / `-k golden` **22** / mypy **122 files 0** / black **247**（P-051c 关闭时实测 2026-11-21；**本批未重跑**，Step 9 以当时实测为准）
> **基座**: DeepSeek-V4.1-Flash（Step 2 复审须异构）
> **Step 2 复审**: [REVIEW_p052_step2](REVIEW_p052_step2_research.md)（GLM-5.3-Flash 异构 ✅）→ **0 P1**，2 P2 + 5 P3 全部当轮修复；外部条文号 8/8 对照全文核验、代码锚点 17/17 重放属实；用户裁决 U-P052-1/2/4 = 方案 A（2026-11-21）

---

## 1. 范围与前置

**做**（候选，Step 3 收敛）：

1. **S1 平台级 kill switch**：全局 / 账户 / 策略三级急停；停止新开仓、可选一键撤单与平仓；状态持久化，重启后保持；
2. **S2 网关事前风控**：每笔订单发柜台前校验——单笔金额上限、价格带（复用 `filter/limit_rules.py`）、单票/行业暴露、日下单笔数与撤单率上限、自成交拦截；
3. **S3 账户级熔断**：日亏损 / 回撤 / 连续拒单超阈值 → 自动降级（只平不开）+ 告警；
4. **S4 合规报告**：程序化交易报告字段清单 + 台账 + 速率上限（默认值待裁决，见 §4.5）+ 异常交易监控指标；
5. **S5 鉴权与传输安全**：REST/WS 鉴权、TLS、最小权限、CORS 白名单、密钥注入（**范围与 P-054 重叠，见 U-P052-4**）；
6. **S6 审计留痕**：意图 / 风控决策 / 下单 / 回报 / 撤单 / 对账全链路 append-only，含操作者与时间源；
7. **S7 故障处置**：断线 / 拒单 / 部分成交 / 柜台重启的处置策略与人工接管 runbook；
8. 四文档 + 台账。

**不做**（明确外置）：

- 真实交易通道（QMT/CTP/券商 API 具体子类）→ **P-053 交易通道网关**（总纲 L270）；
- FastAPI + WebSocket 服务层 → **P-054**（总纲 L271；鉴权/TLS 的**载体**也在 P-054，见 U-P052-4）；
- 微服务拆分 / Redis Streams → **P-055**；
- CTP 期货/月差 → **P-056**；
- regime 自适应 → **P-057**；
- 截面多空/月差模板 → **P-058**。

**前置事实**：

- `live/` 目录**不存在**（`Glob live/**/*.py` 无命中）——总纲 §2.1 规划的 LIVE 层尚未落盘；
- **安全词表全仓零命中**（源码，`*.py`）：
  - `kill switch | kill_switch | 急停 | 一键撤单` → **0**；
  - `鉴权 | authenticat | authorization | jwt | api key | CORS | TLS` → **0**；
  - `合规 | 程序化交易 | 高频交易 | 异常交易 | 报备 | 交易所细则` → **命中 5 行、位于 2 个无关文件**（`tools/distillation_audit.py` / `tests/test_decoupled_engine.py`，均为注释/工具文案），**无任何合规实现**；
  - `fastapi | uvicorn | websocket` → **0**；
- 唯一「限速」实现是 **LLM 告警节流**：`agents/sentiment_framework.py` L737-790（`rate_limiter` 按 severity 节流告警，与订单速率无关）；
- 可复用底座**真实存在**：Guard 管道（6 类检查）、EventLog（append-only JSONL + seq 恢复 + 重放）、涨跌停规则表、止损状态机、生命周期 `KILL` 动作、五维风控、主动盯市（见 §2）。

---

## 2. 代码证据（逐条实读）

| # | 锚点 | 事实 |
|---|------|------|
| E1 | [guard_pipeline.py](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L29-L52) L29-L52 / L284-L362 | `GuardContext` 字段：`action/symbol/quantity/price/order_value/current_positions/current_weights/portfolio_value/cash/trade_history/equity_curve/config`；**无行业、无价格带、无对手方/挂单簿**；`GuardPipeline` 串联 guard，`default/conservative/aggressive` 三预设 |
| E2 | [guard_pipeline.py](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L85-L278) L85-L278 | 现有 **6 类 Guard**：`MaxPositionGuard`（单票权重上限，按 `current_weight*portfolio_value+order_value` 算新权重，L96-L114）/ `CooldownGuard`（同标的冷却天数，L128-L151）/ `DrawdownGuard`（组合回撤 > 阈值禁 BUY，L165-L187）/ `SymbolWhitelistGuard`（白名单，默认禁用，L201-L213）/ `TurnoverGuard`（**日成交额**换手率上限，`sum(value)`，L227-L248）/ `MinCashGuard`（最低现金比例，L262-L278）。**均为金额/权重口径，无笔数、无撤单率、无单笔金额上限、无价格带、无自成交** |
| E3 | [engine_plugins.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_plugins.py#L179-L247) L179-L247 | `GuardPlugin`：`mode ∈ {block, warn}`；`check_trade` L213-247 调 `create_guard_context_from_engine` + `get_blocking_reasons`；**异常 fail-open**（L244-L247 `except → return True, []`，注释「避免阻断正常交易」）——对实盘安全是风险点 |
| E4 | [live_bridge.py](file:///f:/Coding/Factor_Trading_v3.0/core/live_bridge.py#L46-L137) L46-L137 / L144-L242 | `LiveOrder`（order_id/asset/side/quantity/price/status/filled_qty/broker_order_id）；`LiveTradingBridge` ABC 四方法：`place_intents` / `cancel_orders` / `sync_positions` / `query_order_status`；`MockLiveBridge` 仅记录订单。**`place_intents` 内无任何事前风控、无审计写入、无 kill switch 检查**（L164-L189） |
| E5 | [event_log.py](file:///f:/Coding/Factor_Trading_v3.0/core/event_log.py#L37-L57) L37-L57 / L129-L226 / L357-L383 | `EventLogEntry(seq/ts/type/payload/source)`；`EventType` 仅 5 个引擎生命周期事件（`run_started/rebalance/day_end/error/run_finished`）；`append` 双写（磁盘 JSONL 先写 + 内存环形缓冲）L129-L167；`replay` handler 异常**向外传播** L212-L226；`_recover_state` 重启后恢复 `seq` 与缓冲区 L357-L383。**是 S6 的直接复用底座，但无审计事件类型、无操作者字段（仅 `source`）、无显式时间源** |
| E6 | [risk_monitor.py](file:///f:/Coding/Factor_Trading_v3.0/core/risk_monitor.py#L2-L31) L2-L31 / L51-L70 / L1000-L1014 | 五维风控（基本面/行业/宏观/资金流/情绪）→ `RiskLevel(SAFE/LOW/MEDIUM/HIGH)` + `RiskSignal(dimension/level/score/symbol/message/timestamp/metadata)`；`RiskGuardAdapter`（L1000）适配器接入 GuardPipeline。**是组合级预警，不是账户级「只平不开」熔断状态机** |
| E7 | [risk_manager.py](file:///f:/Coding/Factor_Trading_v3.0/core/risk_manager.py#L46-L72) L46-L72 / L83-L117 | `RiskAction(NONE/STOP_LOSS/MARGIN_CALL/FORCE_CLOSE)` + `RiskActionItem(requires_immediate_action)`；`StopLossConfig`（负号阈值）+ `check_stop_loss`。**持仓级盯市，不是账户级熔断** |
| E8 | [lifecycle.py](file:///f:/Coding/Factor_Trading_v3.0/core/lifecycle.py#L44-L65) L44-L65 / L377-L400 / L495-L511 | `GateAction` 四值 `go/hold/recycle/kill`；`KILL` 把 `paper→retired`、`gray|live→paper→retired`（**策略生命周期退役**）；`resolve_monitor_action` 把 red → KILL。**语义是「策略退役」，不阻止下单、不撤单、不平仓、无急停状态持久化**——与 S1 的「运行期急停控制」是不同对象 |
| E9 | [stops.py](file:///f:/Coding/Factor_Trading_v3.0/core/stops.py#L20-L44) L20-L44 / L116+ | `StopConfig(stop_loss_pct/trailing_stop_pct/take_profit_pct/time_stop_days/trailing_activate_pct)` 全正数；`StopEngine.update` 纯函数逐 bar 判定。**持仓级止损止盈，不是账户级** |
| E10 | [limit_rules.py](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L31-L177) L31-L177 | `LimitRule(board/is_st/effective_from/effective_to/up/down)`；`RULES` 覆盖 main/gem/star/bse × ST/非 ST × 时段；`resolve_limit` 唯一命中否则 `LimitRuleError`；`build_limit_prices(close, adj_factor, st, dates)` 产出 raw 口径涨跌停价。**S2 价格带可直接复用，但当前 Guard 管道未消费** |
| E11 | [config.py](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L353-L440) L353-L440 / L505-L538 | `BacktestConfig` 全字段中**无** kill switch / 限速 / 鉴权 / 合规报告相关项；`MarginConfig`（初始 10% / 维持 8% / 强平 5%）为期货保证金，非账户熔断 |
| E12 | [execution_policy.py](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L57-L73) L57-L73 | `OrderIntent(asset/asset_type/target_quantity)`——**无价格带校验、无笔数统计、无自成交标识**；S2 的输入对象 |
| E13 | [pending.py](file:///f:/Coding/Factor_Trading_v3.0/core/pending.py#L24-L40) L24-L40 | `OrderStatus(PENDING/EXECUTED/PARTIAL/EXPIRED/CANCELLED)` + `OrderSide(BUY/SELL/SELL_SHORT/BUY_TO_COVER)`——S7「部分成交 / 拒单」已有状态枚举可复用 |
| E14 | [web/server.py](file:///f:/Coding/Factor_Trading_v3.0/web/server.py#L1-L11) L1-L11 | 仅 `SimpleHTTPRequestHandler` 静态服务（`127.0.0.1:9000`），**无鉴权、无 TLS、无 CORS 控制** |
| E15 | [cli.py](file:///f:/Coding/Factor_Trading_v3.0/cli.py#L1-L14) L1-L14 | 5 子命令 `run/test/analyze/info/dashboard`，**无 live / kill / report 入口** |
| E16 | [risk_overlay.py](file:///f:/Coding/Factor_Trading_v3.0/core/risk_overlay.py#L48-L70) L48-L70 | `RiskOverlayConfig(dd_soft=0.08, dd_hard=0.12, scale_floor, b_min, ...)` —— 回撤 → **权重缩放**（非熔断降级）；S3 可参考其阈值分层，但语义不同（缩放 ≠ 只平不开） |
| E17 | [tracker.py](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L222-L247) L222-L247 | `PortfolioSnapshot`（含 `cash`/`positions`）+ `PositionTracker`——S1「状态持久化 / 账户级」所需账户快照来源 |

---

## 3. 缺口清单（对齐总纲 §3.0 S1-S7）

| ID | 约束 | 现状 | 缺口 | 严重度 |
|----|------|------|------|--------|
| **G1** | S1 kill switch（全局/账户/策略三级） | 仅有策略生命周期 `KILL`（E8，退役语义），无运行期急停 | 无三级急停状态机、无「停止新开仓 / 一键撤单 / 平仓」控制、无状态持久化与崩溃恢复 | 核心 |
| **G2** | S2 网关事前风控 | Guard 6 类（E2）+ GuardPlugin（E3） | 缺**单笔金额上限**、缺**价格带**（E10 未接入）、缺**行业暴露**（E2 无行业）、缺**日下单笔数/撤单率**（TurnoverGuard 是金额换手率）、缺**自成交拦截**；且 `place_intents`（E4）未挂任何检查 | 核心 |
| **G3** | S3 账户级熔断 | DrawdownGuard（每笔回撤阻断，E2）+ risk_overlay 缩放（E16） | 无账户级状态机：日亏损 / 连续拒单计数 / 只平不开降级 / 告警送达均缺 | 核心 |
| **G4** | S4 合规报告 | **0**（词表零命中） | 无报告字段清单、无台账、无速率上限、无异常交易监控指标 | 核心 |
| **G5** | S5 鉴权与传输安全 | **0**（E14 静态服务无鉴权） | 无 API Key/JWT、无 TLS、无 CORS、无密钥注入 | 高（**载体疑属 P-054**，见 U-P052-4） |
| **G6** | S6 审计留痕 | EventLog 底座（E5） | 无「意图/风控决策/下单/回报/撤单/对账」事件类型；无操作者字段（仅 `source`）；无显式时间源 | 高 |
| **G7** | S7 故障处置 runbook | `OrderStatus` 枚举（E13）+ `sync_positions`（E4） | 无断线/拒单/部分成交/柜台重启处置策略，无人工接管流程，无故障注入演练记录 | 高 |

**补充缺口（调研发现）**：

| ID | 缺口 | 证据 |
|----|------|------|
| **G8** | 实盘路径 fail-open：`GuardPlugin` 异常时放行 | E3 L244-L247 |
| **G9** | 合规量化阈值**无一手出处**：总纲 S4「默认 ≤1 笔/秒、≤1000 笔/日」在交易所细则中查无出处（见 §4.5） | §4 外部取证；U-P052-5 |

---

## 4. 外部合规证据（一手来源）

> **核实状态图例**：✅ = 已读官方原文片段；⚠️ = 仅读到官方摘要/问答；❌ = 未取得原文。
> **纪律**：所有数字必须能回溯到官方链接；取不到原文的数值一律标 ❌ 并进入未决项，禁用于正确性断言。

### 4.1 证监会《证券市场程序化交易管理规定（试行）》

| 项 | 内容 | 出处 | 状态 |
|----|------|------|------|
| 文号/日期 | 证监会公告〔2024〕8 号，**2024-05-11 发文**（新闻稿 2024-05-15），**自 2024-10-08 施行** | [中国政府网公报](https://www.gov.cn/gongbao/2024/issue_11426/202406/content_6959680.html)；[证监会发布页](https://www.csrc.gov.cn/csrc/c100028/c7480577/content.shtml) | ✅ |
| 报告管理 | 第二章：报告信息含「账户基本信息 / 账户资金信息（含杠杆资金与杠杆率）/ 交易信息（策略类型及主要内容、指令执行方式、最高申报速率、单日最高申报笔数）/ 交易软件信息」 | [规定 PDF](http://www.csrc.gov.cn/csrc/c101954/c7480579/7480579/files/%E9%99%84%E4%BB%B61%EF%BC%9A%E8%AF%81%E5%88%B8%E5%B8%82%E5%9C%BA%E7%A8%8B%E5%BA%8F%E5%8C%96%E4%BA%A4%E6%98%93%E7%AE%A1%E7%90%86%E8%A7%84%E5%AE%9A%EF%BC%88%E8%AF%95%E8%A1%8C%EF%BC%89.pdf) | ✅ |
| 高频定义 | 第五章 高频交易特别规定 第二十一条：短时间内申报/撤单笔数频率较高、日内申报/撤单笔数较高、交易所认定的其他特征；**具体认定标准由交易所明确并适时完善** | 同上 | ✅ |
| 执法依据 | 第三十二条：本规定自 2024 年 10 月 8 日起施行 | 同上 | ✅ |

### 4.2 沪深北交易所《程序化交易管理实施细则》（核心量化来源）

| 项 | 内容 | 出处 | 状态 |
|----|------|------|------|
| 文号/日期 | 上交所 **上证发〔2025〕52 号，2025-04-03 发布，2025-07-07 施行**；深交所同日发布同日起施行 | [上交所细则全文](http://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250612_10781696.shtml)；[新华网](https://app.xinhuanet.com/news/article.html?articleId=436d5da0dd11f131c43e262536097ed0) | ✅ |
| **报告字段（第九条）** | （一）账户基本信息（投资者名称、证券账户代码、指定会员、产品管理人）；（二）账户资金信息（资金规模及来源、杠杆资金规模及来源、杠杆率）；（三）账户交易信息（策略类型及主要内容、指令执行方式、最高申报速率、单日最高申报笔数）；（四）交易软件信息（名称及版本号、开发主体）；（五）联络信息；（六）交易所要求的其他 | 上交所细则 第九条 | ✅ |
| **重大变更（第十条）** | 8 类，含「账户最高申报速率或单日最高申报笔数变更」「主要交易策略变更」「交易软件信息变更」「停止程序化交易」 | 上交所细则 第十条 | ✅ |
| **四类异常交易（第十八条）** | （一）**瞬时申报速率异常**（1 秒内申报/撤单笔数达一定标准）；（二）**频繁瞬时撤单**（全日多次 1 秒内申报又撤单 + 全日撤单比例达标准）；（三）**频繁拉抬打压**（全日多次个股 1 分钟内涨跌幅与成交占比达标准）；（四）**短时间大额成交**（**上证综合指数或科创 50 指数** 1 分钟内涨跌幅 + 主动买卖金额占比达标准）；（五）兜底 | 上交所细则 第十八条 | ✅ |
| **会员处置权（第二十一条）** | 6 类情形会员应拒绝委托、撤销申报（含「技术系统重大故障或委托重大异常」「可能影响交易系统安全或正常秩序」） | 上交所细则 第二十一条 | ✅ |
| **技术系统要求（第二十七条）** | （二）具备**验资验券、权限控制、阈值管理、异常监测和错误处理**等风控功能；（三）具备**快速撤销申报、暂停申报、系统隔离**等人工干预功能 | 上交所细则 第二十七条 | ✅ |
| **高频认定（第三十三条）** | 单个账户**每秒申报、撤单最高笔数 ≥ 300 笔**，或**单日申报、撤单最高笔数 ≥ 20000 笔**，或交易所认定的其他情形 | 上交所细则 第三十三条；[上交所答记者问](https://www.sse.com.cn/aboutus/mediacenter//hotandd/c/c_20250403_10776805.shtml) | ✅ |
| **高频额外报告（第三十四条）** | （一）高频交易系统服务器所在地；（二）系统测试报告；（三）故障应急方案；（四）其他；**第二款拆单豁免**（公募基金管理人及其子公司/从事资产管理业务的会员/QFII 按设定拆单算法交易且已履行第九条报告者不适用）——**自用账户不适用豁免** | 上交所细则 第三十四条 | ✅ |
| **差异化收费（第三十七条）** | 按申报、撤单笔数与频率设收费标准，加收**流量费与撤单费** | 上交所细则 第三十七条 | ✅ |
| **记录保存（第十五条第二款）** | 会员及使用交易单元的其他机构应当妥善保存报告信息和交易相关资料，**保存期限不得少于二十年**——S6 审计保留期最直接的一手依据 | 上交所细则 第十五条 | ✅ |
| 深交所四类异常交易 | 与上交所口径一致：瞬时申报速率异常 / 频繁瞬时撤单 / 频繁拉抬打压 / 短时间大额成交 | [深交所新闻发布会](http://www.szse.cn/www/aboutus/trends/conference/t20250403_612773.html) | ✅ |
| 异常交易类型补充 | 科创板实时监控细则：虚假申报 / 拉抬打压股价 / 维持涨跌幅限制价格 / **自买自卖或互为对手方交易** / 严重异常波动股票申报速率异常 | [科创板异常交易实时监控细则](http://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20250519_10779400.shtml) | ✅ |

### 4.3 期货市场（P-052 边界外，仅登记）

| 项 | 内容 | 出处 | 状态 |
|----|------|------|------|
| 期货规定 | 证监会公告〔2025〕12 号《期货市场程序化交易管理规定（试行）》，高频特征同构、**具体标准由期货交易所制定** | [国务院公报](https://www.gov.cn/gongbao/2025/issue_12226/202508/content_7036966.html) | ✅ |
| 上期所办法 | 《上海期货交易所程序化交易管理办法》第十条：报告信息（账户基本信息 / 交易和软件信息 / 其他）；高频交易者另报 | [上期所](https://www.shfe.com.cn/regulation/exchangerules/otherrules/202508/t20250814_828665.html) | ✅ |

### 4.4 境外锚点（用于方案设计方向，不用于中国阈值断言）

| 锚点 | 关键内容 | 出处 | 状态 |
|------|----------|------|------|
| **SEC Rule 15c3-5**（Market Access Rule，2010 采纳） | 有市场准入的券商须建立、记录、维护**金融与监管风险管理控制**（事前风控），系统性限制金融敞口并确保合规 | [SEC FAQ](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions/divisionsmarketregfaq-0)；[FINRA](https://www.finra.org/rules-guidance/key-topics/market-access) | ✅ |
| **MiFID II RTS 6**（Commission Delegated Regulation (EU) 2017/584）Article 12 | **kill functionality**：紧急状态下立即撤下任一或全部交易场所的全部未成交订单 | [ESMA Q&A 1612](https://www.esma.europa.eu/publications-data/questions-answers/1612) | ✅ |
| RTS 6 Article 15 / 20 | **事前风控**：price collars（价格带，逐单及区间）、maximum order values（单笔金额上限）、maximum order volumes（单笔数量上限）、maximum message limits（消息/报单频率上限），并要求 hard block | [EUR-Lex 2017/584](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A32017R0589)；[FCA Handbook](https://www.handbook.fca.org.uk/techstandards/MIFID-MIFIR/2017/reg_del_2017_584_oj/?view=chapter) | ✅ |

### 4.5 关键发现：总纲 S4「≤1 笔/秒、≤1000 笔/日」无一手出处

- 检索「程序化交易 每秒不超过1笔 每日不超过1000笔 券商 限制」等组合，**未在证监会规定、沪深北实施细则、上期所办法中找到任何「≤1 笔/秒 / ≤1000 笔/日」的默认速率上限**（❌ 未取得一手原文）；
- 交易所细则中的量化门槛是：**高频认定 ≥300 笔/秒 或 ≥20000 笔/日**（§4.2 第三十三条），以及**四类异常交易的「一定标准」**（细则未公开具体数值，由交易所另行掌握）；
- 因此总纲 S4 的「≤1 笔/秒、≤1000 笔/日」**只能作为项目内部保守默认值**，不得写成监管要求；该数值实为 **D2 用户裁决（2026-11-17）的项目内部默认值**，Step 3 只需确认其「可配置 + 远低于高频阈值」的实现（见 U-P052-5 / §8.1）。

### 4.6 接入合规与数据保存（补充一手来源）

| 项 | 内容 | 出处 | 状态 |
|----|------|------|------|
| **券商外接新规** | 《证券公司交易信息系统接入管理规范（试行）》，中国证券业协会 + 中国证券投资基金业协会 **2026-08-28 发布并施行**，共五章三十三条；第二十六条：券商首次开展交易信息系统接入业务前应向证券业协会**备案**；规范强调**验资验券、阈值管理、异常监测、非法接入阻断、穿透管理**、取消通道特权 | [中证协原文](https://www.sac.net.cn/zlgl/zlgz/202609/t20260901_82233.html)；[央广网报道](http://finance.cnr.cn/jjgd/20260831/t20260831_527799747.shtml) | ✅ |
| **交易记录保存** | 《证券法》第一百三十七条（2019 修订；旧法第一百四十七条）：开户资料 / 委托记录 / 交易记录等保存期限**不得少于二十年** | [全国人大英文本](http://en.npc.gov.cn.cdurl.cn/2019-12/28/c_674672_3.htm)；[证监会法规库](https://neris.csrc.gov.cn/falvfagui/rdqsHeader/mainbody?navbarId=1&secFutrsLawId=0fc431a2a10b47909beef058f6ac3335) | ✅ |
| **反洗钱保存** | 《金融机构客户尽职调查和客户身份资料及交易记录保存管理办法》（〔2025〕第 11 号）：交易记录自交易结束后**至少保存 10 年** | [国务院公报](https://www.gov.cn/gongbao/2026/issue_12506/202601/content_7055197.html) | ✅ |

> 对 S6 的含义：平台侧审计留痕**建议 ≥5 年**（Q9 推荐 5），但若未来承担券商级记录义务，法定下限为《证券法》**20 年**；当前自用定位只需满足「可追溯 + 可重放」，保留期限做成可配置。

---

## 5. 方案矩阵（Step 3 裁决对象）

### 5.1 S1 kill switch 的归属与形态

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | **纯状态机（core）+ 持久化/执行适配器（live）**：`core/safety.py` 定义 `KillLevel(GLOBAL/ACCOUNT/STRATEGY)` + `KillState` + 迁移函数（纯函数、可重放）；`live/` 侧做状态落盘（复用 EventLog/JSONL）、调用 `cancel_orders`、阻断 `place_intents` | 与项目「core 纯计算 / live I/O」纪律一致；状态机可单测、可重放复算；不侵入回测 |
| B | 全部放 `live/`（含判定） | 判定不可独立复算、只能集成测试；与既有 risk/lifecycle 纯函数风格不一致 |
| C | 复用 `core/lifecycle.py` 的 `KILL` | 语义错配：lifecycle 是「策略退役」，S1 要的是「运行期急停 + 撤单 + 停止新开仓」；强行复用会污染生命周期语义 |

**倾向 A**；策略级急停与 `LifecycleStage` 的 `kill` 必须**显式区分**（一个是运行期熔断开关，一个是生命周期终态）。

### 5.2 S2 网关事前风控的落点

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | **扩展 `GuardPipeline`**：新增 `MaxOrderValueGuard`（单笔金额上限）、`PriceBandGuard`（复用 `filter/limit_rules.py` 的 `resolve_limit` / `build_limit_prices`）、`IndustryExposureGuard`（`GuardContext` 增 `industry_exposure` 与 `industry_limits`）、`OrderRateGuard`（日笔数 + 撤单率，`GuardContext` 增 `daily_order_count` / `daily_cancel_count`）、`SelfTradeGuard`（自成交拦截，输入对手方/本方挂单）；`GuardContext` 扩展字段 | 复用已存在的 6-Guard 架构与 `block/warn` 模式；纯函数可测；与 S3 共享上下文 |
| B | 新建独立 `live/gateway_risk.py` | 与既有 Guard 架构平行，重复实现；上下文重复构建 |
| C | 推迟到 P-053 网关实现 | 违反总纲 L269「S1-S7 每项有机械验证出口」；P-052 应交付可被 P-053 调用的校验层 |

**倾向 A**；但须先修 **G8 fail-open**（S2 安全语境下 guard 异常应 **fail-closed** 或至少显式可配）。

### 5.3 S3 账户级熔断

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | 新建 `core/circuit_breaker.py`：`AccountCircuitBreaker`（日亏损 / 回撤 / 连续拒单三阈值 + 状态 `NORMAL/DERISK_ONLY/HALTED`），输出「只平不开」决策 + 告警事件；阈值可配置 | 与 risk_overlay（缩放）语义分离；纯函数可测；可被 S1/S2 消费 |
| B | 扩展 `DrawdownGuard` | 它只做「每笔回撤阻断 BUY」，无状态、无连续拒单、无告警，扩它会混淆「无状态 guard」定位 |
| C | 扩展 `RiskOverlayConfig` | overlay 输出是权重缩放，不是「只平不开」；语义不同 |

**倾向 A**。

### 5.4 S4 合规报告

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | 新建 `core/compliance.py`：① `ProgrammaticTradingReport` 字段 schema（严格对齐 §4.2 第九条 6 类 + 第三十四条额外 3 项）；② `RateLedger`（日笔数/峰值秒速率统计，供报告与限速共用）；③ 异常交易监控指标枚举（§4.2 第十八条四类 + 科创板 5 类）；④ 速率上限默认值**作为可配置项**（默认值待裁决） | 报告字段是一次性 schema，纯数据结构；台账纯函数；不接真实报备通道（外置） |
| B | 只写文档、不落代码 | 不满足总纲 L269「机械验证出口」 |
| C | 本批直接对接券商报备 API | 无 P-053 通道，且报备主体依赖 §7.9 裁决 |

**倾向 A**；报备推送属 P-053/§7.9。

### 5.5 S5 鉴权与传输安全（范围裁决）

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | 本批只交付**接口/契约声明 + 配置项占位**（如 `AuthConfig` / 密钥经环境注入的约定），**实现归 P-054**（总纲 L271 明确 `services/` 含鉴权/TLS/观测） | 避免与 P-054 重复；且当前无 FastAPI/WS 载体，本批无落点 |
| B | 本批实现 API Key/JWT + TLS + CORS | 无服务层载体，会造出「无宿主的鉴权模块」；且与 P-054 冲突 |
| C | 本批完全不做、也不声明 | 违反 §3.0 S5 的「合入前须有」原则 |

**倾向 A**，并作为 **U-P052-4** 提交用户裁决。

### 5.6 S6 审计留痕

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | **扩展 `EventLog` 事件类型**：新增 `audit.intent / audit.risk_decision / audit.order / audit.fill / audit.cancel / audit.reconcile`；`EventLogEntry` 增加可选 `operator` 与 `time_source` 字段（保持向后兼容）；全链路 append-only 复用 `replay` 校验 | 复用已验证的 JSONL + seq + replay；最小侵入 |
| B | 新建独立审计日志 | 与 EventLog 双轨，违反统一事件总线方向（**U-P025-1 已由 P-043 落地**：`IEventBus`+`replay`+引擎 6 发射点） |

**倾向 A**。

### 5.7 S7 故障处置

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | 交付 **runbook 文档 + 故障注入测试骨架**（断线/拒单/部分成交/柜台重启四场景，复用 `OrderStatus` 与 `MockLiveBridge`），处置动作抽象为纯函数决策（`FaultAction`），执行归 P-053 | 满足「故障注入演练记录」且不依赖真实通道 |
| B | 只写文档 | 无机械验证出口 |
| C | 本批实现断线重连 | 属 P-053 网关职责 |

**倾向 A**。

---

## 6. 不变式（草案）

| ID | 不变式 |
|----|--------|
| I1 | 安全判定（kill switch / 事前风控 / 熔断 / 限速）为**纯函数**：同输入必同输出，无 I/O / 无 `datetime.now`（时间由调用方传入） |
| I2 | 任一 `live/place_intents` 路径必须先过 S2 校验；校验未通过**不得发单**（fail-closed，不得静默放行） |
| I3 | 三级 kill switch 中，**更高层级**（global > account > strategy）生效时低层级不得解除 |
| I4 | kill 状态持久化后，重启必须恢复（`EventLog` seq 恢复语义对齐，E5） |
| I5 | 账户熔断进入 `HALTED/DERISK_ONLY` 后，仅允许**减仓方向**订单（只平不开） |
| I6 | 审计事件 append-only 且 `seq` 单调；同一 `seq` 重放结果一致（E5 `replay`） |
| I7 | 合规报告字段**逐项对齐** §4.2 第九条 / 第三十四条，不得缺项或改义 |
| I8 | 本批对 `core/engine_v2.py` / `core/engine_v3_vector.py` / `core/sizing.py` / `core/stops.py` 主路径**零 diff**（如破例须 DESIGN 逐行列出） |
| I9 | 既有 golden 22 条**零重录** |
| I10 | 所有速率/金额阈值**可配置**，禁止硬编码在判定函数体；默认值须标注出处或「项目内部默认」 |

---

## 7. DoD 与读数目标（待 Step 3 / Step 5 定稿）

| 项 | 目标 |
|----|------|
| 新模块 | `core/safety.py`（kill switch 纯状态机）/ `core/circuit_breaker.py`（账户熔断）/ `core/compliance.py`（报告 schema + 速率台账）；`GuardPipeline` 扩展（S2 5 类新 Guard）；`EventLog` 扩展（S6 事件类型 + 字段）；`live/` 适配器（S1/S3 持久化与执行，若 Step 3 判定本批建 `live/`） |
| 用例 | 覆盖 **G1-G9**，每缺口 ≥ 2 例；预计 **+45~65**（Step 3 精确化） |
| pytest | 基线 **1144** → 目标 **≥1180**（Step 3 定稿后精确化） |
| golden | 22 条零重录 |
| mypy | 目标目录不变，新增文件 0 error |
| black | `black --check .` 保持 unchanged（当前 247 + 新增文件数） |
| 合规 | 报告字段清单可逐条回溯 §4.2；速率上限单测；异常交易指标枚举与 §4.2 第十八条一致 |
| 可复现 | kill 状态 / 熔断状态 `to_dict/from_dict` 往返 + EventLog 重放一致 |

---

## 8. 未决项（Step 2 复审后全部闭环：U-P052-1/2/4 经用户裁决 2026-11-21 = 方案 A；U-P052-5/9 由 D2 落定；余 5 项为工程口径，Step 3 一次性确认）

| ID | 未决 | 备选 | 倾向 |
|----|------|------|------|
| **U-P052-1 ✅** | 安全判定归属（core 纯函数 vs live） | A 纯状态机 core + I/O 适配器 live / B 全 live / C 复用 lifecycle.KILL | **A（用户裁决 2026-11-21）** |
| **U-P052-2 ✅** | 本批是否新建 `live/` 目录 | A 建最小 `live/`（仅安全适配器，交易通道仍留 P-053）/ B 全部塞 `core/` / C 推迟到 P-053 | **A（用户裁决 2026-11-21；总纲 §2.1 LIVE 层已规划，S1/S3 持久化需要宿主）** |
| **U-P052-3** | S2 是否扩展 `GuardPipeline` 而非新建 | A 扩展（5 类新 Guard）/ B 新建 gateway_risk / C 推迟 | **A** |
| **U-P052-4 ✅** | S5 鉴权范围（与 P-054 重叠） | A 本批只声明契约/配置，实现归 P-054 / B 本批全做 / C 不做 | **A（用户裁决 2026-11-21；D2/Q9 已定「仅本机/内网 + API Key/JWT + TLS」；载体属 P-054）** |
| **U-P052-5** | S4「≤1 笔/秒、≤1000 笔/日」的定位 | A 标注为「D2 已裁决的项目内部默认值」并做成可配置 / B 作为监管要求写死 / C 移除 | **A**（§4.5：交易所无此默认值；D2 已裁决该值，见 §8.1） |
| **U-P052-6** | GuardPlugin fail-open（G8）处理 | A S2 语境改 fail-closed（可配）/ B 仅记录告警保持放行 / C 不改 | **A**（安全语境；RTS 6 要求 hard block） |
| **U-P052-7** | S6 审计事件类型落 `EventLog` vs 独立日志 | A 扩 `EventLog` / B 独立审计文件 | **A**（U-P025-1 已由 P-043 落地，统一事件总线已成事实） |
| **U-P052-8** | S7 runbook 是否含代码骨架 | A 文档 + 故障注入测试骨架 / B 纯文档 / C 本批实现重连 | **A** |
| **U-P052-9** | 合规报备主体（自用 vs 对外服务） | 待用户按 §7.9 裁决 | **已裁决（D2：自用工具 + 完成程序化报备）**，S4/S5 按自用深度设计 |
| **U-P052-10** | 默认阈值（日亏损/回撤/连续拒单）来源 | A 经验默认 + 可配置 / B 校准后再定 | **A**（阈值不进正确性断言，只进状态迁移测试） |

### 8.1 决策锚点（2026-11-21 补充调研）

> 目的：为 §8 的待裁决项寻找**内部文档裁决 + 架构约束 + 外部一手规则**三类锚点，把「主观倾向」升级为「可引用证据」。

| 未决 | 决策锚点（证据） | 结论 |
|------|------------------|------|
| **U-P052-1** | ① 依赖边禁止 `core→live/services/strategies`，允许 `live→core`（[UPGRADE_MASTER_PLAN §2.1](UPGRADE_MASTER_PLAN.md) L114）；② `core/live_bridge.py` 已在 `core` 放 ABC 骨架、`MockLiveBridge` 亦在 core（ARCHITECTURE L109 标「骨架」）——**协议在 core、实现下沉 `live/`** 是既有先例；③ 外部 MiFID II RTS 6 Art.12 / SEC 15c3-5 只约束「必须具备 kill / 事前控制」，**不约束代码落点** | **方案 A**：判定纯函数放 `core`，持久化/撤单/告警适配器放 `live/`；有内部先例+架构约束双重支撑 |
| **U-P052-2** | ① 总纲 §2.1 已规划 LIVE 层职责含「交易网关/账本/对账/流式适配器」（L114）；② `live/` 当前不存在，P-053 才建真实通道（L270）；③ 总纲 §7.2「宜粗不宜细：先落接口/契约/骨架」（L332）；④ `core/live_bridge.py` 证明「接口可先在 core」 | **倾向 A（建最小 `live/`）**：仅承载 S1/S3 状态持久化与执行适配器；若 Step 3 判定 P-053 前不需要落盘，可退回「接口在 core 骨架、P-053 再搬」——两案均不违反依赖规则 |
| **U-P052-4** | ① **D2 已裁决**：自用工具 + 完成程序化报备（[RESEARCH_upgrade_open_questions Q9/D2](RESEARCH_upgrade_open_questions.md) L323/L337）；② Q9 推荐 4：API/WS 仅绑定 `127.0.0.1`/内网、API Key/JWT + TLS、禁止公网暴露（L340）；③ §3.0 S5 要求 401/403（UPGRADE_MASTER_PLAN L163）；④ P-054 是 `services/` 载体（L271）；⑤ **用户裁决 2026-11-21 = 方案 A** | **方案 A**：本批交付 `AuthConfig` 契约 + 401/403 用例骨架，实现随 P-054；因「仅本机/内网」，鉴权强度可简化但不可省略 |
| **U-P052-5** | ① **D2 已裁决**：默认速率上限 **≤1 笔/秒、≤1000 笔/日**（[Q9](RESEARCH_upgrade_open_questions.md) L323/L339）；② 交易所高频阈值 **≥300 笔/秒 或 ≥20000 笔/日**（§4.2 第三十三条）；③ Q9 明示该默认值「远低于高频阈值」（L339） | **已裁决，非待定**：做成可配置，默认 1/s、1000/日；**禁止写成监管要求**；与 300/20000 保持 ≥2 个数量级余量 |
| **U-P052-6** | ① MiFID II RTS 6 Art.15 要求 **hard block** 强制性、soft block 建议（§4.4 Cms/ESMA）；② SEC 15c3-5 要求「reasonably designed」的有效控制；③ 总纲 §3.0 S2 要求「拒绝路径有单测」（L160） | **方案 A**：安全语境默认 fail-closed，异常放行须显式配置并留审计 |
| **U-P052-7** | ① 总纲 §1.3：EventLog「升级为统一事件总线」（UPGRADE_MASTER_PLAN L58）；② U-P025-1 **已由 P-043 落地**（`IEventBus`+`replay`+引擎 6 发射点）；③ §3.0 S6（L164） | **方案 A**：扩 `EventLog`，不另立日志 |
| **U-P052-8** | ① §3.0 S7 要求「故障注入演练记录」（UPGRADE_MASTER_PLAN L165）；② RTS 6 业务连续性要求 | **方案 A**：runbook + 故障注入骨架（断线/拒单/部分成交/柜台重启） |
| **U-P052-9** | **D2 已裁决**：定位自用工具 + 完成程序化报备；Q9 推荐 1「不对外提供服务；对外另做持牌/等保评估」（[Q9](RESEARCH_upgrade_open_questions.md) L337） | **已解**：S4/S5 按自用深度设计，**不做**等保、多租户、公网鉴权体系 |
| **U-P052-10** | ① `risk_overlay` 已有内部阈值先例 `dd_soft=0.08` / `dd_hard=0.12`（E16）；② 无外部强制阈值（§4） | **方案 A**：经验默认 + 可配置；阈值只进状态迁移测试，不作正确性断言 |
| **S6 保留期** | 上交所细则**第十五条第二款**：报告信息和交易相关资料保存**≥20 年**（§4.2）；《证券法》第一百三十七条：交易记录保存**≥20 年**（§4.6）；反洗钱办法：**≥10 年**；Q9 推荐平台侧 **≥5 年** | 自用定位按 **≥5 年可配置**；若承担券商级记录义务则对齐 **20 年** |

> **锚点小结**：10 项全部闭环——**U-P052-5/9 由 D2 落定；U-P052-1/2/4 经用户裁决 = 方案 A（2026-11-21）**；其余 5 项（U-P052-3/6/7/8/10）为工程口径，可在 Step 3 一次性确认。

---

## 9. 步骤表

| 步 | 动作 | 出口条件 |
|----|------|----------|
| 1 | 调研（本文） | 本文落盘 |
| 2 | 异构复审 | 0 P1（✅ 2026-11-21，[REVIEW §5](REVIEW_p052_step2_research.md)：2 P2 + 5 P3 全修） |
| 3 | DESIGN | 裁决 U-P052-1..10（U-P052-5 / U-P052-9 已由 D2 落定，见 §8.1）；逐模块设计 + 用例映射 |
| 4 | 异构复审 + 收敛 | 0 P1 |
| 5 | IMPL（逐处代码） | 每文件伪码可执行 |
| 6 | 异构复审 + 收敛 | 0 P1 |
| 7 | CHECKLIST | 断言可核对（RULE-1 禁预填） |
| 8 | 一致性检查 | 四文档一致 |
| 9 | TDD + 门禁 | pytest / golden / mypy / black 全绿 |
| 10 | 提交 + CI | 四 job 全绿，批次关闭 |

---

## 10. 结论

1. **P-052 的本质不是「新建一套风控」，而是把已有 6 类 Guard、EventLog、涨跌停规则表、止损状态机、生命周期 KILL 组织成「实盘发单前最后一道闸门」**；核心缺口集中在**运行期急停（G1）、账户级熔断（G3）、合规报告（G4）与审计事件化（G6）**；
2. **合规量化口径已锁定**：沪深北实施细则一手原文（高频 ≥300 笔/秒 或 ≥20000 笔/日；四类异常交易；报告 6 类字段 + 高频额外 3 项）+ 券商外接新规（2026-08-28 备案制）+ 《证券法》20 年记录保存；总纲 S4 的「≤1 笔/秒、≤1000 笔/日」经补充调研确认是 **D2 用户裁决的项目内部默认值**（非交易所规则），实现为可配置且远低于高频阈值（U-P052-5，见 §4.5/§8.1）；
3. **S5（鉴权/TLS）与 P-054 明显重叠**：D2/Q9 已定「仅本机/内网 + API Key/JWT + TLS」，本批只声明契约、实现随 `services/` 落地（U-P052-4，见 §8.1）；
4. **安全语境必须收紧 fail-open**：`GuardPlugin` 当前异常放行（E3），MiFID II RTS 6 要求 hard block、SEC 15c3-5 要求有效控制 → 实盘发单前应改为 fail-closed 或显式可配（U-P052-6）；
5. **10 项未决全部闭环**（§8.1）：U-P052-5/9 由 D2 落定，U-P052-1/2/4 经用户裁决 = 方案 A（2026-11-21），余 5 项工程口径 Step 3 一次性确认；复审增值发现「细则第十五条第二款 20 年记录保存」已补入 §4.2；
6. **本批为零代码变更的文档批次**，未提交、未改门禁；Step 2 已通过（0 P1，[REVIEW](REVIEW_p052_step2_research.md)），下一步为 Step 3 DESIGN。
