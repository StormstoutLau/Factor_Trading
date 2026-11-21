# REVIEW：P-052 Step 2 异构复审（RESEARCH 实盘安全闸门）

> **批次**: P-052 · **Step 2 异构复审** · 日期 2026-11-21
> **复审对象**: [RESEARCH_p052_live_safety_gate.md](RESEARCH_p052_live_safety_gate.md)（Step 1 落盘版）
> **作者基座**: DeepSeek-V4.1-Flash · **复审基座**: GLM-5.3-Flash（**异构 ✅**，符合 RULE-5）
> **证据时点**: HEAD `1f950c6`（工作区：RESEARCH_p052 + PROGRESS 两处未提交修改，与复审对象一致）
> **方法**: ① 外部条文号对照上交所细则**全文**（WebFetch 原文 261 行）逐条核验；② 代码锚点 E1-E17 逐条 grep/read 重放；③ 词表命中声明复跑；④ 内部文档引用（D2/Q9/总纲/ARCHITECTURE/PROGRESS）逐个行号核对。

---

## 1. 核验矩阵（全验通过项）

| # | 核验对象 | 方法 | 结果 |
|---|----------|------|------|
| V1 | §4.2 条文号 8 处（第九/十/十八/二十一/二十七/三十三/三十四/三十七条） | 对照上交所细则全文（上证发〔2025〕52 号，c_20250612_10781696 页面附件全文）逐条核对 | **8/8 属实**：第九条 6 类报告字段（(一)~(六)）✅；第十条 8 类重大变更 ✅；第十八条 4+1 类异常交易（瞬时申报速率/频繁瞬时撤单/频繁拉抬打压/短时间大额成交）✅；第二十一条 6 类会员拒绝委托情形 ✅；第二十七条(二)验资验券/权限控制/阈值管理/异常监测/错误处理、(三)快速撤销申报/暂停申报/系统隔离 ✅；第三十三条 ≥300 笔/秒 或 ≥20000 笔/日 ✅；第三十四条高频额外报告 3+1 项 ✅；第三十七条差异化收费（流量费+撤单费）✅ |
| V2 | 代码锚点 E1-E17 | 逐条 grep/read 重放 | **17/17 属实**：E1 GuardContext L29-50/管道 L284 ✅；E2 六 Guard L85/117/154/190/216/251 与 check 行号逐一吻合 ✅；E3 GuardPlugin L179 + mode L190 + check_trade L213 + fail-open L244-247（「异常时允许执行，避免阻断正常交易」原文在 L247）✅；E4 LiveOrder L46-47/ABC 四方法 L85/98/110/119/Mock L144/164 ✅；E5 EventLogEntry L37-44/append L129/replay L212/_recover_state L357 ✅；E6 五维+RiskLevel L51-57+RiskGuardAdapter L1000 ✅；E7 RiskAction L46-52 ✅；E8 _ACTION_VALUES L44/GateAction L61-65/KILL 迁移 L378-400（paper→target、gray\|live→PAPER→RETIRED 两段式）✅/resolve_monitor_action L495 ✅；E9 StopConfig L20-21/StopEngine L116 ✅；E10 LimitRule L31-32/RULES L53/resolve_limit L106/build_limit_prices L132 ✅；E11 BacktestConfig L353-354/MarginConfig L505-506 ✅；E12 OrderIntent L57 ✅；E13 OrderStatus L24-31/OrderSide L34 ✅；E14 web/server.py L1-11（SimpleHTTPRequestHandler/127.0.0.1:9000/无鉴权）✅；E15 cli.py L1-14（5 子命令）✅；E16 RiskOverlayConfig L48 ✅；E17 PortfolioSnapshot L222/PositionTracker L247 ✅ |
| V3 | 词表命中声明 | 复跑 grep（`*.py`） | **4/4 属实**：kill switch/急停/一键撤单 = 0 ✅；鉴权/auth/jwt/api key/CORS/TLS = 0 ✅；fastapi/uvicorn/websocket = 0 ✅；合规类 6 词正则命中 **5 行、位于 2 个文件**（`tools/distillation_audit.py` + `tests/test_decoupled_engine.py`）✅（但 §1 表述见 F-2）；限速唯一实现 = sentiment_framework rate_limiter L737/_check L775/_update L787 ✅ |
| V4 | 内部文档引用 | 逐个行号核对 | D2（总纲 L324「自用工具 + 完成程序化报备」+ 速率默认值）✅；Q9（upgrade_open_questions：推荐 1 L337 / 推荐 3 L339 / 推荐 4 L340）✅——**Q9 标题实为 L323，RESEARCH 写 L324，差 1 行（F-3）**；总纲 L114 依赖方向/L155-167 §3.0/L269 P-052 行/L270 P-053/L271 P-054/L277 关键路径/L332 宜粗不宜细/L58 EventLog/L286 import-linter/L163 S5/L160 S2/L164 S6/L165 S7 ✅；ARCHITECTURE L109「⚠️ 骨架」✅；PROGRESS P-052 行 L202 ✅ |

---

## 2. 发现清单

> 分级：P1 = 幻觉/断言错误/阻断；P2 = 表述矛盾/关键证据漏引/应修；P3 = 行号差 1/细节不精确/可顺手修。

| ID | 级别 | 发现 | 证据 |
|----|------|------|------|
| **F-1** | **P2（增值漏引）** | **细则第十五条第二款漏引**：「会员及使用交易单元的其他机构应当妥善保存客户和自身的报告信息和交易相关资料，**保存期限不得少于二十年**」——这是 S6 审计保留期**最贴近平台场景的一手依据**（比《证券法》137 条的券商义务更直接），§4.2 与 §8.1 S6 保留期行均未引用 | 细则全文 L123 |
| **F-2** | **P2（表述矛盾）** | §1 词表「合规 \| 程序化交易 \| … → **0**（5 处命中全在 tools/distillation_audit.py / tests/test_decoupled_engine.py）」——「0」与「5 处命中」自相矛盾；实测为**命中 5 行、位于 2 个无关文件**，语义应为「无相关实现，命中均为注释/审计工具文案」 | grep files_with_matches 实测 2 files |
| **F-3** | P3（行号差 1） | §8.1 U-P052-4/5 引用「Q9 L324」——Q9 标题实为 **L323**（L324 为 Q9 框架现状段）；L337/L339/L340 正确 | grep `^### Q9` → L323 |
| **F-4** | P3（锚点不精确） | E7 引用「L46-L52 / L83-L117」但 `RiskActionItem`（L56）/`requires_immediate_action`（L72）落在两段引用之外 | grep risk_manager L56/L72 |
| **F-5** | P3（状态陈旧） | §5.6/§8.1 以「U-P025-1（统一事件总线方向）」支持审计事件落 EventLog——该待办**已由 P-043 关闭**（`IEventBus` + `EventType` + `replay` + 引擎 6 发射点，PROGRESS L182/L2014），引用应更新为「已落地」，论据更强 | PROGRESS L182/L2014 |
| **F-6** | P3（增值观察） | 第三十四条**第二款拆单豁免**（公募基金管理人及其子公司/从事资产管理业务的会员/QFII 按设定拆单算法交易且已履行第九条报告的，不适用高频额外报告）未记录——自用账户**不适用**豁免，对 S4 报告字段设计是必要边界说明 | 细则全文 L247 |
| **F-7** | P3（细节可补） | §4.2 第十八条(四)漏「**上证综合指数或科创 50 指数**」限定词；(一)漏「1 秒钟内申报、撤单笔数达到一定标准」的申报+撤单合计口径已写但可更精确 | 细则全文 L133/L139 |

**P1：0 项**。外部数字（≥300/秒、≥20000/日、20 年、6+3 报告字段、4 类异常）全部与原文一致，无幻觉。

---

## 3. 用户裁决登记（2026-11-21）

用户指令「按这三项直接推进 Step 2 异构复审」= 对 §8.1 三项 ★ 未决确认采纳**方案 A**：

| ID | 裁决 | 生效 |
|----|------|------|
| **U-P052-1** | ✅ 方案 A：安全判定纯函数放 `core/`（`safety.py`/`circuit_breaker.py`），持久化/撤单/告警适配器放 `live/` | Step 3 直接采用 |
| **U-P052-2** | ✅ 方案 A：本批新建最小 `live/`（仅 S1/S3 状态持久化与执行适配器；真实交易通道仍留 P-053） | Step 3 直接采用 |
| **U-P052-4** | ✅ 方案 A：S5 本批只交付 `AuthConfig` 契约 + 401/403 用例骨架，实现归 P-054 | Step 3 直接采用 |

连同 D2 已落定的 U-P052-5/9，**10 项未决全部有主**；余 5 项（U-P052-3/6/7/8/10）为工程口径，Step 3 一次性确认。

---

## 4. 修复回执（全部当轮修复）

| ID | 修复动作 | 落点 |
|----|----------|------|
| F-1 | §4.2 新增「第十五条第二款」行；§8.1「S6 保留期」行补细则 20 年一手依据（列于《证券法》137 条之前） | RESEARCH §4.2 / §8.1 |
| F-2 | §1 词表行改为「6 词正则命中 5 行、位于 2 个无关文件（均为注释/工具文案），无任何实现」 | RESEARCH §1 |
| F-3 | §8.1 两处「Q9 …L324」→「L323」 | RESEARCH §8.1 |
| F-4 | E7 锚点扩为「L46-L72 / L83-L117」 | RESEARCH §2 E7 |
| F-5 | §5.6 B 行与 §8.1 U-P052-7 行改为「U-P025-1 已由 P-043 落地（IEventBus+replay+6 发射点）」 | RESEARCH §5.6 / §8.1 |
| F-6 | §4.2 第三十四条行补第二款拆单豁免边界说明（自用账户不适用） | RESEARCH §4.2 |
| F-7 | §4.2 第十八条(四)补指数限定词 | RESEARCH §4.2 |

---

## 5. 结论

- **0 P1**；2 P2 + 5 P3，全部当轮修复并回写；
- 外部取证部分经全文对照**无幻觉**，条文号 8/8、数字 4/4 全验；
- 代码锚点 17/17 全验，E1-E17 可直接作为 Step 3 DESIGN 输入；
- 用户三项裁决已登记（§3），10 项未决全部闭环；
- **Step 2 通过** → 可进入 Step 3 DESIGN。
