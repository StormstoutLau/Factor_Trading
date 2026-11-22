# REVIEW：P-053 Step 2 异构复审（RESEARCH_p053_trading_gateway）

> **批次**: P-053 · **Step 2 复审** · 日期 2026-11-21
> **复审对象**: [RESEARCH_p053_trading_gateway.md](RESEARCH_p053_trading_gateway.md)（394 行，含 §12 补充调研）
> **复审基座**: **GLM-5.3-Flash** ≠ 作者 **DeepSeek-V4.1-Flash**（异构成立）
> **方法**: E3 代码锚点全量重放 + 外部锚点独立抽检（不经作者检索路径）+ 口径保真核对 + 反向证据检查
> **仓库时点**: 工作区含 RESEARCH 文档 + PROGRESS 更新（未提交）；代码基线 = P-052 关闭态 `2064ae6`

---

## 1. 复审范围

| 维度 | 核对内容 | 结果 |
|------|----------|------|
| 事实性 | 外部锚点（监管/API/行业标准）可回放、无幻觉 | §3 |
| 代码实证 | §2 表 9 行 E3 锚点行号与内容 | §2，**17/17 属实** |
| 边界 | P-052 已关闭契约不被改写；依赖边不越界 | §4 |
| 口径 | D1/D4/Q1/Q10/Q11 引文保真（不得重开已裁决项） | §4 |
| 完整性 | 总纲 F6/L270/L244/L419/O-R2 对 P-053 的全部义务是否被覆盖 | §5（**发现 2 处 P2 缺漏**） |
| 可行性 | §9 估算算术、模块树与门禁预估一致性 | §4 |

---

## 2. 代码锚点重放（E3，17/17 属实）

| # | RESEARCH 声称 | 重放结果 |
|---|---------------|----------|
| 1 | `LiveOrder` status 五值自由串（[live_bridge.py L56](../core/live_bridge.py#L56)） | ✅ `pending/filled/partial/cancelled/rejected` 逐字命中 |
| 2 | ABC 四抽象（L69），`place_intents` L85 / `cancel_orders` L98 | ✅ 全部命中（L84-85/L97-98 装饰器+签名） |
| 3 | `MockLiveBridge` L144，订单号 L171 `mock_{n:06d}` 内部计数器 | ✅ `f"mock_{self._order_counter:06d}"` |
| 4 | `OrderIntent` 字段仅 5 个（[execution_policy.py L71-75](../core/execution_policy.py#L71-L75)），`trade_quantity` L78、`action` property L88 | ✅ 无 `client_order_id`/价格/账户/策略字段 |
| 5 | `Order`(L21)/`filled_qty`(L28)/`TradeExecution`(L38) | ✅ 命中 |
| 6 | TWAP L118 / VWAP L189 / Iceberg L272 | ✅ 三类定义行精确命中 |
| 7 | `append` L153 / `read` L193 / `auto_flush` L116 / JSONL 单行写入 L355（[event_log.py](../core/event_log.py#L153)） | ✅ 命中；确认无 fsync、无唯一约束、无事务 |
| 8 | **8 个审计常量在 L60-67**，含 `audit.order`/`audit.fill`/`audit.reconcile` | ✅ §6.5 所引事件类型真实存在（复审初期疑点排除） |
| 9 | `pre_trade_check(intent, ctx, *, account_id, strategy_id, ts, time_source="local")`（[safety_gate.py L111-120](../live/safety_gate.py#L111-L120)） | ✅ 签名逐字一致 |
| 10 | `cancel_all(bridge: LiveTradingBridge, *, ts) -> int`（L284，D-G7 只对 Bridge） | ✅ L284-286 命中，注释含「D-G7」 |
| 11 | `safety_store` mkstemp+fsync+`os.replace`（L21-27） | ✅ 命中（§12.2 E 行引用属实） |
| 12 | `pyproject.toml` L42 声明 `sqlalchemy>=2.0.0` | ✅ L42-46 依次 sqlalchemy/pymysql/psycopg2/redis/celery |
| 13 | sqlalchemy/redis/celery **全仓 .py 零引用**（「未使用」） | ✅ `Grep sqlalchemy|redis|celery *.py` = 0 文件 |
| 14 | `live/` 恰 3 文件 | ✅ `__init__.py`/`safety_store.py`/`safety_gate.py` |
| 15 | 无 `services/` 目录 | ✅ Glob 0 命中 |
| 16 | 基线读数 pytest 1214 / mypy 128 / black 261 / tests 132 / core 51 | ✅ 与 [CHECKLIST_p052](CHECKLIST_p052_live_safety_gate.md) §8 实测表一致（E1 存档，本复审未重跑） |
| 17 | §9 估算算术 10+14+14+12+8+4 = 62 | ✅ 无误 |

---

## 3. 外部锚点抽检（独立检索，不经作者路径）

| # | 锚点 | 抽检方式 | 结果 |
|---|------|----------|------|
| 1 | xtquant 委托状态 48-55 | WebSearch「迅投知识库」 | ✅ [XtTrader 官方字典](https://dict.thinktrader.net/nativeApi/xttrader.html)：`ORDER_UNREPORTED=48 未报 / WAIT_REPORTING=49 / REPORTED=50 已报 / REPORTED_CANCEL=51`…与 §3.2 表一致 |
| 2 | 华鑫 2026-10-30 关闭 miniQMT | WebSearch | ✅ **华鑫证券官网原文**：《关于关闭迅投 miniQMT 系统功能的公告》——「根据《证券公司交易信息系统接入管理规范（试行）》相关规定…公司将于 2026 年 10 月 30 日收盘后，统一关闭迅投 miniQMT 系统功能」。公告**自引两协会规范**，RESEARCH §3.1 因果链成立；且该一手 URL 此前未入 §10 来源清单 → 已补（F-3 修复） |
| 3 | SimNow 细节（§12.1） | 会话内 WebFetch 官网原文 | ✅ `BrokerID=9999` / 三组前置 + 7×24（40001/40011）/ `APPID=simnow_client_test` + 16 个 0 认证码 / 第二套环境仅 CTP API 开发且不提供结算 / 新注册第三交易日 / 初始 2000 万——逐条与官网一致 |
| 4 | xtquant 版本与平台（O-R2） | WebSearch PyPI + 迅投 | ✅ **新取证**：[PyPI xtquant](https://pypi.org/project/xtquant/)「Windows x64 / Python 3.6-3.13」；[迅投快速开始](http://dict.thinktrader.net/nativeApi/start_now.html) 64 位 Python 3.6-3.13 Windows only；Linux 仅第三方 RPyC 代理（qmt-api）。→ RESEARCH 原文未含此取证（O-R2 义务缺漏）→ 已补（F-3） |
| 5 | §12 案例（Freqtrade/Hummingbot/SQLite WAL/IBKR/FIX/Alpaca/vnpy） | 本会话检索记录回放 | ✅ 9 组案例均有官方 URL 与原文引句，无幻觉 |
| 6 | CTP 契约（OrderRef/SessionID/1 笔每秒/-2/-3） | 作者引用为一手 API 文档（ctpdoc.jedore.top / 东航金融 PDF / vnpy 论坛） | ✅ 抽检链接可达、口径与 §3.2 一致（未逐字重放全文，标注为「链接级抽检」） |
| 7 | SSE 恢复顺序引文 | 上交所 STEP PDF（作者来源） | ✅ 引文与 PDF 口径一致（链接级抽检；全文重放留待 Step 3 设计引用时复核） |

---

## 4. 口径保真核对（不得重开已裁决项）

| 项 | RESEARCH 引文 | 原文 | 判定 |
|----|---------------|------|------|
| D1 | §1.2 L41「多通道预留…默认 BrokerApi+Ctp 完整、Terminal 半自动」 | 总纲 §7.1 L323 + L300 | ✅ 一致（且「先交付 ChannelCapability + Mock 骨架」义务在 §6 有承接） |
| D4 | §1.2 L42「synthetic fixture + golden；禁外部阻断」 | 总纲 §7.1 L326 | ✅ 一致 |
| Q10 | §1.2 L44 | 未决文档 L365 **paper↔live 行逐字一致**（持仓精确/现金 ≤0.01% NAV/权重 L1 ≤1e-4/10bps·30bps/≥95%/连续 2 日降级） | ✅ 无改写。**但**：总纲 L244 的「立项期按账户规模校准并写入验收」义务未被回应 → F-2 |
| Q11 | §1.2 L45 | L389-392 忠实转述；「本批不做净额撮合」为批次裁剪（合法），但净额后置去向未登记 → F-5（P3） |
| Q12 | 仅 L4 头部引用，正文零覆盖 | L412-421 推荐明确落「P-053 验收」 | ❌ 缺漏 → F-1（P2） |
| P-052 契约 | pre_trade_check 必经 / cancel_all 只对 Bridge / 审计 8 常量 | 代码 L111-120/L284/L60-67 | ✅ 只引用未改写；§6.5 `submit()` 顺序与契约兼容 |
| 依赖边 | §6.1「live → core，不 import filter/services」 | P-052 F-D5 | ✅ 一致 |

---

## 5. 发现（0 P1 / 3 P2 / 3 P3）

| ID | 级别 | 发现 | 证据 |
|----|------|------|------|
| **F-1** | **P2** | **Q12 两模块缺漏**：总纲 L270（F6）+ F-R9-P2（L419「F6 增 `live/session_calendar.py`；P-053 验收加时段状态机」）+ Q12 推荐（L421「对总纲影响：§3 F6 `session_calendar`/`corporate_actions`、**P-053 验收**」）三处均把**交易日历/时段状态机**与**公司行为事件表+对账归因**落在 P-053；RESEARCH 正文零覆盖（`session_calendar|corporate_actions|公司行为` 仅 L4 头部 1 次命中），§4 缺口矩阵、§6.1 模块树、§7 未决项均无 | Grep 实测；总纲 L270/L419/L421；未决文档 L412-421 |
| **F-2** | **P2** | **parity 阈值立项期校准义务未回应**：总纲 L244「（回测↔paper↔实盘阈值）在 P-053 立项时**按账户规模校准并写入验收**」+ Q10「待确认：阈值是否按账户规模/标的流动性再校准？」（L374）+ F-R12-P2（L422「P-053 验收引用」）。RESEARCH 只引了 Q10 数值，未把校准义务挂入未决项/验收设计 | 总纲 L244/L422；未决文档 L372-374 |
| **F-3** | **P2** | **O-R2 取证义务未闭环**：总纲 L487 要求「xtquant 支持的 Python 版本范围与 Linux 不可安装性需在 P-053 RESEARCH 阶段用 `pip index versions xtquant`/官方文档取证」。RESEARCH §3.2 无版本/平台证据行。本次复审已代为取证（§3 表 #4），需回填 | 总纲 L487；PyPI/迅投官方页 |
| **F-4** | P3 | §2 表 L53 措辞易误读：`LiveOrder` **实有** `filled_qty`（L57）与 `broker_order_id`（L61）字段，原文「无 filled_qty 事件、无 broker_order_id 关联表」应澄清为「无逐笔 fill 事件记录；`broker_order_id` 仅为回显字段、无 client↔broker 映射表」 | live_bridge.py L57/L61 |
| **F-5** | P3 | Q11「跨策略净额撮合」被本批裁剪（§1.2 L45 括注）但未入 §7 移交清单——净额归属（P-058 模板层或 P-054 之后）无登记 | §1.2 L45 vs §7 L247-252 |
| **F-6** | P3 | §12.1「首个真实协议连通 = CTP（SimNow）」与 §0.5「本批不接真实网络」的时序关系需一句话显式分层，防 Step 3 误读本批接 SimNow | §0.5 vs §12.1 结论 |

**反向证据检查**（§11 第 5 项）：华鑫公告原文自引《接入管理规范（试行）》→「股票端外接被监管关闭」结论维持；XTP 需专业投资者资质+审核、SimNow 属期货仿真，均不构成「股票端零审批完整外接通道」反例。**未发现需推翻 §0 结论的反向证据。**

---

## 6. 修复回执（全部当轮修复）

| ID | 修复位置（RESEARCH 文档） |
|----|---------------------------|
| F-1 | §1.1 表 +2 行（日历/时段、公司行为）；§4 增 **G11**；§6.1 模块树 + `session_calendar.py` + `corporate_actions.py`（最小）；§7 增 **U-P053-11**（synthetic 事件表先行，Q12 推荐 7）；§0 增结论第 8 条 |
| F-2 | §1.2 Q10 行补「立项期校准义务（总纲 L244 + Q10 L374）」；U-P053-5 倾向列扩充（配置化 + 校准 + 写入验收，Step 3 定默认）；§6.2 `ReconcileReport` 行注 parity 引用 |
| F-3 | §3.2 xtquant 行补发行形态证据（Windows x64 / Python 3.6-3.13 / Linux 无官方支持）+ O-R2 闭环注；§10 来源 +3（华鑫官网一手 URL / PyPI xtquant / 迅投字典） |
| F-4 | §2 表 L53 措辞修正 |
| F-5 | §7 移交清单 +1 行（Q11 净额撮合 → P-058 前置复核） |
| F-6 | §12.1 结论句尾补时序澄清 |

---

## 7. 结论

- **0 P1**；3 P2 + 3 P3 **全部当轮修复并回执**（§6）。
- 代码锚点 17/17、外部抽检 3/3 新增 + 3 组链接级、口径 7 项保真——RESEARCH 的事实底座可靠。
- 修复后 RESEARCH 覆盖总纲对 P-053 的全部显性义务（F6 L270 / L244 校准 / L419 时段状态机 / O-R2 取证 / Q10-Q12 引用）。
- **Step 2 复审：PASS**。可进入 Step 3 DESIGN（先裁决 U-P053-1/2/4 = §12 建议口径，或由用户改判）。
