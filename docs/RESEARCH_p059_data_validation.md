# RESEARCH：P-059 模拟数据验证体系（data validation harness）

> **批次**: P-059 · **Step 1 调研** · 日期 2026-11-18
> **执行序**: **P-048 之前**（用户 2026-11-18 指定立项：「在 P-048 之前单独立项」）；编号为**追加式分配**，不重排既有 P-042..P-058
> **判档**: **T1**（新增测试侧基础设施 + **仅 G4** 一处生产修复；G5 经复核撤回，见 §2.3）
> **上游**: 用户诉求「当前框架缺少模拟数据验证：验证模块计算准确性、涨跌停调仓买卖等边界情况处理准确；后续任何模块开发也需执行数据验证、方便排查每一个步骤问题；先调研历史批次是否有类似机制，有则扩展」；[UPGRADE_MASTER_PLAN.md §3.4 L236-248](UPGRADE_MASTER_PLAN.md#L236-L248)（golden/invariants/manifest/change_report/外部对拍横切基建）；[RESEARCH_golden_baseline.md](RESEARCH_golden_baseline.md)；[RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md)；[RESEARCH_p014_suspension_accounting.md](RESEARCH_p014_suspension_accounting.md)
> **代码证据时点**: HEAD `5f85363`（P-047 关闭；工作区净）
> **基座**: 正文 DeepSeek-V4.1-Flash；Step 2/4/6/8/10 复审由 GLM-5.3-Flash 执行（RULE-5；U-P059-6 于 Step 10 闭合）
> **零预填声明**: 本文只写 ✅+证据 / ❌+证据 / `[待 Step N]`；§11 起为后续步骤预留，**不得**提前填写。

---

## 1. 触发与题干

- **触发**: 用户 2026-11-18 指示——「当前框架缺少模拟数据验证，验证模块计算准确性、涨跌停调仓买卖处理等边界情况处理准确；同时对后续任何模块功能开发也需要执行数据验证，能够方便排查每一个步骤问题；请开展调研，之前调研批次是否有类似机制，如果有则需要扩展。」
- **题干（本批做什么）**:
  1. **场景库**：把「涨跌停、停牌、ST、退市、除权、新股、T+1」等边界情形做成**可复用的确定性场景定义**，而非各测试手搓 fixture；
  2. **逐步骤可观测**：任意一天/任意一步的中间态（目标权重、买卖掩码、订单、成交、现金、持仓）可 dump、可 diff、可单点复跑，用于定位「为什么这天没成交」；
  3. **断言原语**：把分散的边界断言（现金守恒、成交价合法、掩码语义、订单去向）沉淀为可组合的验证原语；
  4. **统一验证入口**：新增模块（如 P-048 risk_overlay）能一行命令挂载场景验证，不再手写整套样板；
  5. **覆盖面补强**：补齐现有测试未覆盖的边界（见 §4 G1-G21）。
- **明确不做**:
  - 不做实盘/paper 数据接入（P-053+）；不做实时流式数据（`live/`）；
  - 不做 `data/` 真实数据依赖（CI 忽略 `data/`，场景必须 100% 代码构造）；
  - 不改既有 golden 15 + P-045 2 + P-047 3 = **18** 的任何期望值；
  - 不引入随机性（属性测试 Hypothesis 见 U-P059-4，默认不做）；
  - 不做性能基准（另属 TD/性能批次）。
- **职责外（不回答）**: 某策略的收益能力；实盘成交滑点标定（P-053）；数据源质量（P-042 已交付契约）。

---

## 2. 代码事实基线（E3 @`5f85363`）

### 2.1 现有验证资产盘点（**结论：机制已有，缺统一与逐日**）

| # | 机制 | 位置 | 已解决 | **未解决（本批缺口来源）** |
|---|------|------|--------|---------------------------|
| 1 | golden 基线（18 实例） | `tests/golden/`（G1-G7 + p045/ + p047/）、[_golden_cases.py L33-60](file:///f:/Coding/Factor_Trading_v3.0/tests/_golden_cases.py#L33-L60)、[record_golden.py](file:///f:/Coding/Factor_Trading_v3.0/scripts/record_golden.py) | 端到端**末值**回归（`metrics` / `nav` 摘要 `length/first/last/min/max` / `trades` 汇总）；容差 `rtol=1e-9, atol=1e-12, money_atol=1e-6` | **只有末值与摘要**，无逐日轨迹；场景靠手写 case（G1-G7 硬编码于 `_golden_cases.py`）；新增场景 = 改公共文件 |
| 2 | 合成夹具 | [_synth_fixture.py L38-139](file:///f:/Coding/Factor_Trading_v3.0/tests/_synth_fixture.py#L38-L139) | 可写 `close/open/high/low`、`stock_adj`、`suspend/st`（支持 2D 逐值）、`industry`、`universe`（`list_date`/`delist`）、manifest | `open/high/low` **缺省复用 `close`**（[test_synth_fixture.py L47-71](file:///f:/Coding/Factor_Trading_v3.0/tests/test_synth_fixture.py#L47-L71) 断言此法向后兼容）→ **无天然日内**；无涨跌停价生成器 |
| 3 | 测试数据生成器 | [prepare_test_fixture.py L71-114](file:///f:/Coding/Factor_Trading_v3.0/scripts/prepare_test_fixture.py#L71-L114)（baseline）、[L117-208](file:///f:/Coding/Factor_Trading_v3.0/scripts/prepare_test_fixture.py#L117-L208)（biased） | baseline/based 两套 pkl（含涨停开盘 `open = close*1.10`、ST、停牌、除权）；[test_fixture_profile.py L27-69](file:///f:/Coding/Factor_Trading_v3.0/tests/test_fixture_profile.py#L27-L69) 断言文件集合与逐字节稳定 | 粗粒度 GBM 数据，**非场景化**；`high/low` 由 `open/close` 推导；无「场景 → 期望行为」绑定 |
| 4 | 参考实现差分 | `tests/_reference_impl.py` + [test_reference_diff.py](file:///f:/Coding/Factor_Trading_v3.0/tests/test_reference_diff.py)（**9 用例**） | 指标/成本层与独立参考解对拍 | 只覆盖**指标层**，不覆盖调仓/成交/掩码边界 |
| 5 | 不变量 | `core/invariants.py`（I1-I7）+ [test_invariants.py](file:///f:/Coding/Factor_Trading_v3.0/tests/test_invariants.py)（**11 用例**） | 事后账目恒等（NAV 恒等式、成本恒等、负持仓等） | 只验「账目自洽」，**不验「是否按规则处理」**（如跌停卖单去了哪里） |
| 6 | 涨跌停规则 | [limit_rules.py L52-73](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L52-L73)（规则表）、[L106-129](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L106-L129)（`resolve_limit` 唯一命中，0/多条即 `LimitRuleError`）、[L132-177](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L132-L177)（`build_limit_prices`）、[L180-202](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L180-L202)（IPO 前 5 日无限制） | 板别/ST 比例唯一真值源；不回落默认值 | **无舍入边界用例**（如 10.005）；无「连续一字板」场景 |
| 7 | 掩码合成 | [universe_filter_clean.py L188-233](file:///f:/Coding/Factor_Trading_v3.0/filter/universe_filter_clean.py#L188-L233)（`_build_limit_masks`：`open >= limit_up - EPS` 不可买、`open <= limit_down + EPS` 不可卖）、[L406-496](file:///f:/Coding/Factor_Trading_v3.0/filter/universe_filter_clean.py#L406-L496)（`buyable/sellable/tradable`） | 掩码口径唯一 | 掩码正确 ≠ 订单处置正确（见 §2.3） |
| 8 | 队列路径执行 | [engine_v2.py L842-951](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L842-L951) | 不可买/不可卖 → **跳过并保留队列**；P-047 现金闸门同语义（`continue`） | 与次日路径**现金口径**不统一（G4） |
| 9 | 次日开盘路径 | [engine_v2.py L1220-1301](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1220-L1301) | 不可买/不可卖 → `failed_orders` → 次日重试（L1298 保留）；**先过期再执行**（[L1233](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1233) `_expire_next_day_orders`，P-014 D7，含半衰期） | 现金口径仍是字面 `qty*open*1.002`（L1274）≠ `estimate_buy_cash`（**G4，真实缺口**）；过期按自然日计数为**设计口径**且有测试（[test_p014 L247-266](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p014_suspension_accounting.py#L247-L266)）→ **G5 撤回** |
| 10 | manifest / change_report | `core/manifest.py`、`core/change_report.py`（+`docs/dev-log/p012/*.json`） | 可复现指纹 + 六层归因 | 不生成场景、不做逐日 diff |

### 2.2 边界测试覆盖实测（E1 计数，`def test_` 含类内缩进；**Step 2 回写订正**：顶格 `^def test_` = 42，`test_rebalance_exits.py` 12 例为类方法）

| 文件 | 用例数 | 覆盖场景 |
|------|--------|----------|
| `test_limit_rules.py` | **7** | 板别/ST 比例表、唯一命中、涨停跌停价 |
| `test_limit_mask_timing.py` | **3** | 开盘价触及涨停不可买 / 未触及可买；跌停下 `sellable` |
| `test_p040_bse_limit_rule_gap.py` | **6** | 北交所 30% 规则缺口 |
| `test_p014_suspension_accounting.py` | **7** | 停牌期间两路径不负持仓、不重复成交 |
| `test_universe_delisting.py` | **6** | 退市动态池移除 |
| `test_p033_order_price_validation.py` | **8** | 订单价合法性 |
| `test_p034_price_diff_guard.py` | **5** | 价格跳变守卫 |
| `test_rebalance_exits.py` | **12** | 调出清仓 / SELL 优先 |
| **合计** | **54** | — |

### 2.3 关键缺口实证

**G4（两路径现金口径分裂）**: 队列路径在 P-047 后使用精确式 `estimate_buy_cash`（含最低佣金 5 元和滑点），次日路径 [L1274](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1274) 仍为 `order.quantity * open_price * 1.002`。→ **同一笔小额买入在两条路径可成交性判定不同**（精确式可能需 5 元最低佣金，`1.002` 在金额 <2500 元时给出更宽松/更严格的相反结论）。

**G5（撤回：初判「次日路径无过期 / 零测试」均不成立）**: [L1233](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1233) 在执行前调用 `_expire_next_day_orders(date)`（P-014 D7，[L809-840](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L809-L840)），读 `cfg.max_pending_days_buy=5` / `max_pending_days_sell=10`（[config.py L377-378](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L377-L378)），调 `PendingOrder.is_expired`（[pending.py L202-229](file:///f:/Coding/Factor_Trading_v3.0/core/pending.py#L202-L229)）；**且已有测试锁定**：[test_p014_suspension_accounting.py L247-266](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p014_suspension_accounting.py#L247-L266)（`test_expire_next_day_orders`，docstring 明示「买 5 / 卖 10 **自然日**」，构造 3 单断言 2 过期 1 保留）。→ **G5 不是缺陷**：实现、测试、口径声明三者齐备；自然日计数是**显式设计选择**（[pending.py L215](file:///f:/Coding/Factor_Trading_v3.0/core/pending.py#L215)），非遗漏。本批**零生产改动**，仅在 S13 能力边界清单中转述该口径。

**更正记录（RULE-1 零预填）**: §2.1-9、§3.1-E、§3.3-BZ8、§4-G5、§6-B7、§9.1-D2、§9.2-U-P059-1/7 已同步撤回或收窄；**「次日路径无过期」「次日过期零测试」两个表述不得再出现在本批任何文档**。

**G3（OHLC 非独立）**: `_synth_fixture.write_price_fixture` 的 `open/high/low` 缺省复用 `close`，现有涨停场景靠**显式传 `open`** 绕过（G3 case、`prepare_test_fixture` 的 `open = close*1.10`）。→ 无法自然表达「盘中从跌停拉到涨停」或「一字板封死」的差异，场景表达能力受限。

**G6（舍入边界未测）**: `build_limit_prices` 无 `10.005 → ?` 级别用例；A 股涨停价按「参考价×(1+比例) 四舍五入到分」，边界值易出偏差。

**G7（目标偏离未量化）**: 现有断言止于「掩码为 False」，无「连续 N 日不可买 → 目标权重偏离度 / 现金闲置率」的量化断言。

**G8（新增模块验证成本高）**: P-047 加 3 个 golden 需改 4 处（`_golden_cases.py` 的 `CASES`/构造/`CASE_IDS` + 独立目录 + 装载测试）。→ 与「后续任何模块开发都能方便挂载验证」直接冲突。

---

## 3. 取证

### 3.1 E1 本地（可重放）

| 读数 | 命令 | 结果 |
|------|------|------|
| A 基线门禁 | `pytest -q`（`MPLBACKEND=Agg`） | **846 passed**（@`5f85363`） |
| B golden 实例 | `pytest -q -k golden` | **18 passed**（15 + p045 2 + p047 3） |
| C 边界测试规模 | 8 文件 `def test_`（含类内缩进）计数 | **54**（§2.2；**Step 2 回写**：顶格 `^def test_` = 42，`test_rebalance_exits.py` 12 例为类方法） |
| D 两路径现金式 | Read `engine_v2.py` L1274 vs `core/sizing.py` L133-149 | 字面 `1.002` vs 精确式 → ❌ 不一致 |
| E 次日队列过期 | Read `engine_v2.py` L1233/L809-840 + `pending.py` L202-229 + `test_p014` L247-266 | ✅ 有过期 + ✅ 有测试 + ✅ 自然日口径已文档化 → **G5 撤回**（初判不成立） |
| F 夹具 OHLC | Read `_synth_fixture.py` L38-85 + `test_synth_fixture.py` L47-71 | 缺省复用 `close` → ❌ 非独立 |
| G 逐日 trace | 全仓 grep `dump|trace|snapshot` 于 `core/` | 仅 `tracker.get_snapshots()`（日终净值），无调仓中间态 |
| H 测试文件数 | `tests/*.py` | **95** |

### 3.2 E1-EXT 外部锚点

> 只证明**方法学**与**市场规则**，不引入运行时依赖。

| # | 来源 | 事实 | 对本批含义 | 置信度 |
|---|------|------|-----------|--------|
| X1 | 上交所《交易规则》/ 深交所《交易规则》（2023 修订）关于「价格笼子」「涨跌幅限制」条款（T1 官方规则） | 主板 ±10%、创业板/科创板 ±20%、北交所 ±30%、ST ±5%；涨跌停价按「前收盘价×(1±比例)」四舍五入至 0.01 元 | 舍入边界必须有用例（G6）；比例表已由 `limit_rules.py` 承载 | 高 |
| X2 | 上交所/深交所《交易规则》关于「一字板」与「集合竞价」条款（T1） | 开盘集合竞价即封涨停 → 全天无成交可能；跌停同理 | 「一字板」与「盘中触及」必须区分（G3） | 高 |
| X3 | 中国结算《证券登记结算业务规则》/ 交易所 T+1 规定（T1） | 当日买入不可当日卖出 | 场景库需 `T+1` 约束场景（现有 `_clamp_sell_quantity` 已实现，缺场景验证） | 高 |
| X4 | pytest 官方文档：`fixture` 作用域 / `parametrize` / `--lf` / `-x`（T1 官方文档） | 参数化与失败重跑是排查效率的标准手段 | 场景库应以 `parametrize` 驱动，兼容 `--lf` 单点复跑（S5） | 高 |
| X5 | Fowler, *Parallel Change* / *Strangler Fig*（T2 工程实践） | 扩展现有机制优于另起炉灶 | 裁决 M-A：在 golden/synth 之上扩展，不新建平行体系 | 中高 |
| X6 | Referential Labs, *Metamorphic Relations for Backtests: Testing the Engine, Not the Strategy*（T2 工程实践）：https://referentiallabs.com/blog/metamorphic-relations-backtests/ | 回测引擎的 oracle 问题（无「正确答案」可比）可用**变质关系**破解：不问「输出对不对」，而问「输入变换后输出是否按预期变化」；针对**引擎**而非策略 | 断言原语库（B4）须内建变质关系：缩放价格→收益不变；增删零权重标的→结果不变；日期平移→结果平移（S11/I9-I11） | 高 |
| X7 | S. Potter, *Property-Based Testing Meets Financial Data: Turning Market Invariants into Executable Specifications*（T2 工程博客）：https://www.susanpotter.net/quant/property-based-testing-statistical-validation/ | 把市场不变量写成可执行规格，优于逐例期望；Hypothesis 可生成大量输入 | **方法学采纳、依赖不采纳**：以不变式驱动断言（I1-I12），但不引入 Hypothesis（U-P059-4） | 中高 |
| X8 | M. Feathers, *Working Effectively with Legacy Code*（T1 书）；golden master / characterization testing 社区综述（T2） | Characterization test 断言「代码现在做什么」而非「应该做什么」；golden master 是其间最钝但最彻底的工具 | 本仓既有 golden 属**行为锁定**；P-047 起新增 golden 属**规格锁定**（闭式推导）。本批须在文档中区分二者，禁止用行为锁定替代正确性论证 | 高 |
| X9 | Bailey & López de Prado, *The Deflated Sharpe Ratio* / *PBO*（T1 论文，经 X-RAY 审计综述转引：https://arxiv.org/html/2611.18934v1） | 回测绩效的假阳性来自多重检验与选择偏差，与引擎正确性正交 | **能力边界**：本体系只证明「引擎按规则计算与成交」，不证明策略 alpha；验证报告中必须显式声明 | 高 |
| X10 | 上海证券交易所《交易规则（2026 年修订）》6.6 条（T1 官方原文）：https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml | 科创板 ±20%；**不设涨跌幅**的情形：IPO 上市后前 5 个交易日、**退市整理期首个交易日**、**退市后重新上市首个交易日** | `special_no_limit_mask` 现状仅覆盖 IPO 前 5 日且退市整理期依赖外部数据（缺失时全 False）→ 盲区 BZ11 / 缺口 G12 | 高 |
| X11 | 上海证券交易所《股票上市规则（2026 年 4 月修订）》9.6 条（T1 官方原文）：https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/mainipo/c/c_20260424_10816589.shtml | 退市整理期 **15 个交易日**；全天停牌不计入，累计停牌 **≤5 个交易日** | 场景库需「退市整理期 + 停牌累计」场景；日频引擎需明确是否建模时长计数 | 高 |
| X12 | 深圳证券交易所《交易规则》4.5.6 条解读（T1 官方问答）：https://investor.szse.cn/knowledge/stock/deal/t20210203_584642.html | 退市整理首个交易日不设涨跌幅，但设**盘中临时停牌**（较开盘价 ±30% / ±60%） | 日频回测**不建模盘中临停** → 必须写入「能力边界声明」（S13/G20），禁止静默忽略 | 高 |
| X13 | EvoMarket（arXiv 2604.18046，T2 论文）；Simudyne *PulseCheck*（T3 工业博客） | 市场模拟器的验证须覆盖「价格路径以外的统计量」（机制保真 + 微观结构保真），单一 NAV 对比不足以证明保真 | 断言原语须覆盖：成交率、拒单原因分布、现金利用率、目标偏离度（B4/G7） | 中高 |
| X14 | A 股回测适配社区实践（T3 社区：腾讯云开发者社区 / 华为云社区 / ZVT 数据避坑）：https://developer.cloud.tencent.cn/article/2673629 、https://bbs.huaweicloud.com/blogs/517427 、https://easyclaw.ijinshan.com/skills/zvt/a-share-data-traps.html | 「能算出价格 ≠ 能成交」；不复权数据会造成假日跳空并被策略误判为暴跌；六件事=复权/T+1/涨跌停/停牌/成本/字段 | 场景库必含：除权跳空（不得触发止损/信号误判）、跌停卖不出、涨停买不到、停牌复牌；与 G3/G6/G10 对应 | 中 |

---

### 3.3 E4 盲区扫描（全链路 7 层，`@5f85363`）

> **口径**: 「已读码」= 本轮 Explore 逐文件读到的分支；「候选」= 由既有设计文档/代码结构推断，**Step 2 必须复核后再定性**（禁止在 Step 2 前当作结论）。不局限于用户举例的涨跌停/停牌。

| ID | 层 | 盲区 | 证据 | 触发条件 | 严重度 | 建议场景 |
|----|----|------|------|----------|--------|----------|
| **BZ1** | L1 数据 | 数据层**零入参校验**：NaN / 负价 / 零成交 / 重复或乱序索引无守卫 | 已读码：[data_v3.py L99-126](file:///f:/Coding/Factor_Trading_v3.0/core/data_v3.py#L99-L126) 直接 `.values` 入 NumPy | 脏数据输入 | **P2** | 脏数据注入 → 断言显式失败而非静默 NaN 传播 |
| **BZ2** | L1 数据 | 复权因子为 0 仅 `limit_rules` 局部兜底，数据层无校验 | 已读码：[limit_rules.py L132-177](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L132-L177) `replace(0, np.nan)` | `adj_factor=0` | P3 | 零复权因子场景 |
| **BZ3** | L2 因子 | 截面**全相同值 / 全 NaN** 时排序退化，选股行为未定义；**（Step 2 回写）** 标准化层已有部分守卫（[factor.py L436-442](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py#L436-L442) masked rank + `stds.replace(0, nan)`），残余 = optimizer `select_top` 并列排名稳定性 | 复审重放：factor.py L436-442 | 因子退化 | P2 | 常量因子 / 全 NaN 因子 |
| **BZ4** | L2 因子 | 停牌股是否参与排序、复牌次日的因子可用性 | 候选 | 停牌期间因子 | P3 | 停牌×因子缺失 |
| **BZ5** | L3 权重 | 权重和 **>1 仅 warning**，不归一、不报错 | 已读码：[target_positions.py L76-145](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L76-L145) | 权重和 1.2 | **P2** | 权重和 >1 场景 + 现金守恒断言 |
| **BZ6** | L3 权重 | **（Step 2 回写，P2→P3，部分锁定）** 空目标/零权重→清仓与空 dict 同一代码路径，已由 `test_u1_exited_positions_are_liquidated` / `test_u6` / `test_g4_no_hidden_leverage` 锁定；残余 = 空 dict 端到端场景 | 复审重放：`test_rebalance_exits.py` 用例名 | 空信号 | P3 | 空目标 → 全清仓端到端 |
| **BZ7** | L4 执行 | 两路径现金口径分裂（精确式 vs `1.002`） | 已读码：[engine_v2.py L1274](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1274) | 小额单（<2500 元） | **P1** | 同一订单两路径对拍（G4） |
| ~~**BZ8**~~ | L4 执行 | **撤回**：次日队列过期已实现（L1233，P-014 D7）且已测试，自然日计数为显式设计口径 | 已读码：[engine_v2.py L1233](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1233)、[test_p014 L247-266](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p014_suspension_accounting.py#L247-L266) | — | **撤回** | 仅在 S13 声明口径 |
| **BZ9** | L4 执行 | 同日**先买后卖**导致现金不足误拒；**（Step 2 回写）** SELL 优先已由 `test_g5_sells_precede_buys` 锁定，残余 =「同日卖款可用于当日买入」现金充分性场景 | 已读码：P-047 R1（队列插入顺序）+ 复审重放 | 同日双向调仓 | P2 | 同日买卖混合场景 |
| **BZ10** | L4 执行 | 零手（<100 股）与「最低佣金吞噬」（小额单佣金占比 >100%） | 已读码：`_clamp_sell_quantity` / P-047 `estimate_buy_cash` | 极小仓位 | P2 | 微额订单场景 |
| **BZ11** | L4 执行 | **无涨跌幅限制窗口**未覆盖：退市整理期首日、重新上市首日（X10） | 已读码：[limit_rules.py L180-202](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L180-L202) 仅 IPO 前 5 日，退市整理期「缺失时全 False」 | 退市整理期首日 | **P2** | 无限制窗口场景（含外部数据缺失） |
| **BZ12** | L5 账目 | **（Step 2 回写改写，P1→P2）** 复权默认 **hfq**（[data.py L490](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L490)）→ 后复权序列无除权跳空，持仓股数设计上无需调整；真实残余盲区 =「复权因子变更日 NAV 连续性」与「hfq 非整分价格 vs `limit_rules` 前收盘口径一致性」无场景锁定 | 复审重放：grep `stock_adj`/`adj` + [data.py L483-490](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L483-L490) | 复权因子变更日 | **P2** | 复权变更日 NAV 连续性场景（原「除权跳空误判」前提不成立） |
| **BZ13** | L5 账目 | **（Step 2 回写，P2→P3）** 退市清算价口径**已有实现+测试锁定**（P-012 D5 + `test_delist_settlement_uses_delist_return` / `…_without_return_uses_last_close`）；残余 =「回测末日未平仓持仓净值口径」 | 复审重放：`test_universe_delisting.py` 用例名 | 回测末日持仓 | P3 | 末日未平仓净值场景 |
| **BZ14** | L5 账目 | **（Step 2 回写，P2→P3，部分覆盖）** 停牌账目主体已由 P-014 7 用例 + golden G7 锁定；残余 =「长期停牌 mark-to-market 用最后成交价」显式断言场景 | 复审重放：`test_p014` 用例 + G7 | 长期停牌 | P3 | 停牌净值口径显式断言 |
| **BZ15** | L6 风控 | SL 与 TP **同 bar 同时触发**的优先级；跳空穿越止损价的成交价口径 | 已读码：P-045 DESIGN D6 定义 SL→trailing→TP→time，gap 归 `stop_loss` | 大幅跳空 | **P2** | 同 bar 双触发 / 跳空穿价场景锁定 |
| **BZ16** | L7 策略 | 策略抛异常、warmup 不足、信号全空 | 候选 | 异常策略 | P3 | 异常与冷启动场景 |
| **BZ17** | L7 调度 | 多策略资金分配溢出（子账户求和 > 总资金） | 候选（P-051/P-058 邻域） | 多策略 | P3 | 本批仅登记，不覆盖 |
| **BZ18** | L1/L4 | 长假日 / 日期不连续（跨春节）时的 T+1 与持仓龄计算 | 候选 | 长假 | P3 | 日期跳空场景 |

> **盲区统计（RULE-2，Step 2 回写重算）**: 登记 18 项 = **有效 17 + 撤回 1（BZ8）**。有效项严重度（Step 2 重分级）：P1 **1**（BZ7）+ P2 **8**（BZ1/BZ3/BZ5/BZ9/BZ10/BZ11/BZ12/BZ15）+ P3 **8**（BZ2/BZ4/BZ6/BZ13/BZ14/BZ16/BZ17/BZ18），**1+8+8=17 ✓**。层分布（含撤回项）：L1 3 / L2 2 / L3 2 / L4 5 / L5 3 / L6 1 / L7 2 = **18 ✓**；有效项 L4 为 **4**（BZ8 撤回后）。
> **证据完备度（Step 2 更新）**: 「已读码」**9** + 「候选」**9**；Step 2 已复核候选 **5** 项（BZ3/BZ6/BZ12/BZ13/BZ14 → 部分守卫/降级/改写，见 §11.2），**剩余候选 4** 项（BZ4/BZ16/BZ17/BZ18）维持候选定性，Step 3 设计场景时须先复核。

---

## 4. 缺口清单（G1-G21）

| ID | 缺口 | 证据 | 影响 |
|----|------|------|------|
| **G1** | 无统一**场景库**：边界场景散落在 8 个测试文件的手搓 fixture 中（54 用例） | §2.2 | 新场景无法复用；同类场景重复实现易漂移 |
| **G2** | 无**逐日中间态 trace**：只有末值 golden + 日志 | §3.1-G | 「为什么这天没成交」需改代码加 print；不满足用户「排查每一个步骤」 |
| **G3** | 夹具 **OHLC 非独立**：`open/high/low` 缺省复用 `close` | §2.1-2、§3.1-F | 无法自然构造一字板 / 盘中触板 |
| **G4** | 两执行路径**现金口径分裂**：`estimate_buy_cash` vs `1.002` | §2.3-G4、§3.1-D | 同一订单两条路径判定不同 |
| ~~**G5**~~ | **撤回**：初判「次日路径订单无过期 / 零测试」不成立——实现（L1233）、测试（`test_p014` L247-266）、口径声明（docstring「自然日」）三者齐备 | §2.3-G5、§3.1-E | 无缺口；仅在 S13 能力边界中陈述自然日口径 |
| **G6** | **涨跌停价舍入边界**无用例 | §3.2-X1 | 边界价可能错判 ±1 分 |
| **G7** | **目标偏离/现金闲置**无量化断言 | §2.3-G7 | 连续不可买时无回归保护 |
| **G8** | 新增模块**验证挂载成本高**（P-047 需改 4 处） | §2.3-G8 | 与用户「任何模块都要验证」冲突 |
| **G9** | **属性/组合覆盖**缺失：边界组合靠人工枚举 | §2.2 | 停牌×跌停×ST 等交叉场景无覆盖 |

> 以下 **G10-G21** 由 §3.3 盲区扫描（BZ1-BZ18）与外锚（X6-X14）映射而来；**BZ7→G4、BZ8 撤回、其余 16 项 → G10-G19**。

| ID | 缺口 | 证据 | 影响 |
|----|------|------|------|
| **G10** | **数据层零入参校验**：NaN / 负价 / 零成交 / 乱序索引 / 零复权因子无守卫 | BZ1、BZ2；[data_v3.py L99-126](file:///f:/Coding/Factor_Trading_v3.0/core/data_v3.py#L99-L126)、[limit_rules.py L132-177](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L132-L177) | 脏数据静默传播为 NaN 净值，排查成本极高 |
| **G11** | **因子截面退化**：全相同值 / 全 NaN / 停牌股参与排序，选股行为未定义（标准化层已有部分守卫，见 BZ3 回写） | BZ3（部分守卫）、BZ4（候选，Step 3 先复核） | 退化输入产生不可解释换手 |
| **G12** | **权重和 >1 仅 warning**，不归一不报错；空目标 / 全零权重的清仓语义未锁定 | BZ5、BZ6；[target_positions.py L76-145](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L76-L145) | 超配与清仓口径不可回归 |
| **G13** | **同日先买后卖**导致现金误拒；**微额订单**（零手 / 最低佣金吞噬）无场景 | BZ9、BZ10；P-047 `estimate_buy_cash` | 现金闸门误拒与佣金占比异常无保护 |
| **G14** | **无涨跌幅限制窗口**仅覆盖 IPO 前 5 日；**退市整理期首日 / 退市后重新上市首日**缺失 | BZ11、X10；[limit_rules.py L180-202](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L180-L202) | 应不设限的日期被误判为涨停 → 买不进 |
| **G15** | **（Step 2 回写改写）** 复权默认 hfq → 持仓无需除权调整（设计使然）；**残余未锁定**：复权因子变更日 NAV 连续性 + hfq 非整分价格与 `limit_rules` 前收盘口径一致性 | BZ12（改写）、X14；[data.py L483-490](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L483-L490) | 原担心的「除权跳空误判」前提不成立；真实风险在口径一致性 |
| **G16** | **（Step 2 回写收窄）** 退市清算价口径**已锁定**（P-012 D5 + `test_delist_settlement_*` 2 用例）；残余 =「回测末日未平仓净值」与「长期停牌 mark-to-market 最后成交价」显式断言 | BZ13/BZ14（降级后） | 主体已有保护；残余口径仍无场景锁 |
| **G17** | **止损止盈同 bar 双触发**与**跳空穿价**成交价口径无场景锁 | BZ15；P-045 DESIGN D6（SL→trailing→TP→time） | 极端行情下退出价不可复现 |
| **G18** | **策略异常 / warmup 不足 / 信号全空 / 多策略资金溢出** | BZ16、BZ17（P-051/P-058 邻域） | 异常路径静默产出空回测 |
| **G19** | **长假日 / 日期不连续**下 T+1 与持仓龄；**退市整理期 15 日 + 停牌累计 ≤5 日**未建模 | BZ18、X11、X12 | 日历口径偏差导致持仓龄与订单过期判定错位 |
| **G20** | **无变质关系测试形态**：只能逐例给期望，无法验证「输入变换 → 输出应按规律变换」 | X6、X7 | 引擎级口径回归只能靠人工枚举场景 |
| **G21** | **无能力边界声明机制**：分钟 / tick / 盘中临停 / 集合竞价撮合不做，但无机器可读声明 | X9、X12 | 读者误以为回测覆盖盘中约束 |

> **计数（RULE-2）**: 登记 **21 项 = G1-G9（9）+ G10-G21（12）**，**9+12=21 ✓**；其中 **G5 撤回** → **有效 20 项**。盲区映射：**有效 17/18 项全覆盖**（BZ7→G4；BZ8 撤回；其余 16 项 → G10-G19）。
> **处置归属（Step 3 定案）**: 生产修复 **1**（G4，D2）；验证设施 **17**；能力边界声明 **1**（G21）；方法学形态 **1**（G20）——G20/G21 与设施项交叠，按**主归属**计；**20 = 1+17+1+1 ✓**。

---

## 5. 方案对比与建议

| 方案 | 内容 | 优点 | 缺点 | 裁决 |
|------|------|------|------|------|
| **M-A 扩展现有基建**（推荐） | `tests/scenarios/`（场景注册表 + 构造器）+ 统一 `dump` 中间态 + 断言原语库 + `scripts/verify_scenario.py` 入口；复用 `_synth_fixture` / `limit_rules` / `invariants` | 与 §3.2-X5 一致；零新依赖；CI 口径不变 | 需设计稳定的场景 schema，避免二次重构 | **采纳** |
| M-B 只扩 golden | 多录 N 个 case | 改动最小 | 不解决 G2/G8；golden 越加越慢 | 拒（作为 M-A 的子能力） |
| M-C 引入 Hypothesis 属性测试 | 随机生成边界组合 | 覆盖 G9 | 不确定性 vs 可复现冲突；新增依赖 | 拒（U-P059-4 保留评估） |
| M-D 引入第三方回测框架做对拍 | 如 backtrader | 独立参考 | 依赖重、口径不可控；已有 `external_benchmark` 隔离 venv 先例但仅指标层 | 拒（指标层已用外派对拍） |

**建议**: **M-A**。核心是「场景可声明、中间态可观测、断言可组合、入口统一」，全部落在测试侧。

**M-A 增强（B4 断言原语的理论基础）**: 回测引擎**没有外部 oracle**（不存在「正确答案」可比），断言不能只靠逐例给期望。本批在 B4 内建**变质关系**（X6）：不问「输出对不对」，而问「输入变换后输出是否按预期变换」。采纳三条（S11 / I9-I11）：

| 关系 | 变换 | 应保持不变 |
|------|------|-----------|
| R1 价格缩放 | 全部价格与初始资金同乘 k（k≥1，整手与最低佣金可比） | 收益率 / 持仓股数 / 成交笔数 |
| R2 惰性标的 | 增删从不入目标集且从不成交的代码 | NAV / 成交 / 现金逐日一致 |
| R3 日期平移 | 交易日整体平移（数量与顺序不变） | trace 结构平移、末值相对指标不变 |

此为**方法学采纳、依赖不采纳**（X7）：不引入 Hypothesis（D5），仍走显式参数化。**与 G4 的关系**：U-P059-1 已由用户裁决取 (b)，**G4 本批修复**（D2；G5 经复核撤回，非缺陷）——场景库是「先修后锁」，不是「给缺陷录基线」。

---

## 6. 拆分（B1-B7）

| 块 | 内容 | 交付物 | 依赖 |
|----|------|--------|------|
| **B1** | 场景库地基：`ScenarioSpec`（日期/代码/OHLC/掩码/因子/初始持仓/事件）+ 注册表 + 构造器复用 `_synth_fixture` | `tests/scenarios/__init__.py`、`tests/scenarios/_spec.py` | 无 |
| **B2** | 边界场景集（≥10 例）：涨停买失败、跌停卖失败、一字板连续 3 日、停牌复牌、ST 5%、退市移除、除权、新股无限制、T+1 禁卖、跨板 20%/30% | `tests/scenarios/boundary.py` | B1 |
| **B3** | 逐日 trace：`TraceRecorder`（日级：目标权重/掩码/订单/成交/现金/持仓；默认关闭，零行为） | `tests/scenarios/_trace.py`（或 `core/trace.py`，见 U-P059-2） | B1 |
| **B4** | 断言原语：`assert_cash_non_negative` / `assert_mask_semantics` / `assert_order_disposition` / `assert_target_deviation` / `assert_price_legal` | `tests/scenarios/_asserts.py` | B1 |
| **B5** | 统一入口：`python scripts/verify_scenario.py --scenario <id> [--dump] [--day N]`；失败自动打印该日中间态 | `scripts/verify_scenario.py` | B1-B4 |
| **B6** | 接入规范 + 回归：新增模块「如何挂验证」三行模板；全量门禁复跑 | `docs/*` + 测试 | B1-B5 |
| **B7** | **G4 生产修复**：次日路径现金改 `estimate_buy_cash`（1 处）；G5 撤回（非缺陷），仅在 S13 陈述自然日过期口径 | `core/engine_v2.py`（1 处）+ 红绿测试 | 独立（B1 前即可做） |

> **已纳入（仅 G4）**: D2、U-P059-1 用户裁决取 (b)。[L1274](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1274) 改用 `estimate_buy_cash`（与队列路径 L907 同源），消除小额单判定分裂。**G5 已撤回**（见 §2.3）：过期实现（L1233）+ 测试（`test_p014` L247-266）+ 自然日口径声明三者齐备，本批对次日路径**零生产改动**。

---

## 7. 规格（S1-S14，Step 3 细化）

| ID | 规格 | 边界 |
|----|------|------|
| S1 | 场景必须**确定性**：无 `random`、无当前时间、无网络；价格/掩码全部显式 | 违反 → 场景不可注册 |
| S2 | 场景**自校验**：每个场景声明 `expected`（闭式推导的成交/持仓/现金），不允许「先跑后录」 | 与 golden 的「规格锁定」一致（P-047 D6 先例） |
| S3 | `open/high/low` **独立可写**，缺省值行为保持向后兼容（复用 `close`） | 不破坏 `test_synth_fixture.py` 既有断言 |
| S4 | 涨跌停价必须由 `limit_rules.build_limit_prices` 计算，场景不得硬编码限价 | 单一真值源 |
| S5 | 场景按 `parametrize` 驱动，支持 `--lf`/`-x` 单点复跑 | 排查效率 |
| S6 | trace 默认 **off**；开启时零行为影响（只读观测） | 违反 → 拒绝合并 |
| S7 | trace 字段固定集合：`date/target_weight/mask(buy,sell)/orders/submitted/filled/rejected/reason/cash/positions/nav` | 缺失 → 验证不完整 |
| S8 | 订单去向三态唯一：`filled` / `retry(保留)` / `dropped(丢弃)`；每单必须可归因到三态之一 | 与 P-047 「跳过≠失败」口径一致 |
| S9 | 面板/断言容差：金额 `1e-6`、权重 `1e-9`、价格 `1e-9`（沿用 `_golden_cases.TOLERANCE`） | 不新造容差 |
| S10 | 既有 18 golden **零重录**；场景库不进入 `tests/golden/` 根目录断言范围 | 与 `CASE_IDS` glob 断言兼容 |
| S11 | 每个场景须声明**至少 1 条变质关系**（R1 价格缩放 / R2 惰性标的 / R3 日期平移），由 B4 原语自动执行 | 无关系声明 → 场景视为不完整（对应 G20） |
| S12 | 变换须**保持可成交性前提**：缩放价格会改变最低佣金占比的场景，禁止对现金类断言套用 R1；每条变换须显式声明影响域 | 防止变质关系产生假阳性 |
| S13 | 验证报告必须含**机器可读能力边界清单**：不含分钟 / tick、不含盘中临停、不含集合竞价撮合、不证明策略 alpha | 对应 G21；X9、X12 |
| S14 | **脏数据守卫只在验证侧**：场景库对 NaN / 负价 / 零成交 / 乱序索引须显式失败；生产数据层校验另立项 | 不扩本批生产面（G10、D9） |

---

## 8. 不变式（I1-I12）

| ID | 不变式 | 验证出口 |
|----|--------|----------|
| I1 | 确定性：同场景同配置重复运行，trace 逐字节一致 | `test_scenario_determinism` |
| I2 | 零行为：本批不接线生产路径时，既有 846 全绿 | 全量 pytest |
| I3 | trace 关闭时零观测开销与零输出 | `test_trace_off_noop` |
| I4 | 订单三态完备：任一订单在任一日必属 `filled/retry/dropped` 之一，且总数守恒 | `assert_order_disposition` |
| I5 | 掩码一致：`buyable=False` 当日绝不产生 BUY 成交；`sellable=False` 当日绝不产生 SELL 成交 | `assert_mask_semantics` |
| I6 | 现金非负：所有场景全程 `cash >= 0` | `assert_cash_non_negative` |
| I7 | 价格合法：成交价落在 `[limit_down, limit_up]` 且为整手 | `assert_price_legal` |
| I8 | 既有 golden 18 零重录 | `pytest -k golden` |
| I9 | **变质-价格缩放（R1）**：全部价格与初始资金同乘 k≥1（保持整手与最低佣金可比）后，收益率 / 持仓股数 / 成交笔数不变 | `assert_metamorphic_scale` |
| I10 | **变质-惰性标的（R2）**：增删从不入目标集且从不成交的代码后，NAV / 成交 / 现金逐日一致 | `assert_metamorphic_inert` |
| I11 | **变质-日期平移（R3）**：交易日整体平移（数量与顺序不变）后，trace 结构平移、末值相对指标不变 | `assert_metamorphic_shift` |
| I12 | **脏数据显式失败**：NaN / 负价 / 零成交 / 乱序索引输入必须抛出明确异常，禁止静默传播为 NaN 净值 | `assert_dirty_input_raises` |

---

## 9. 决策锚点与未决

### 9.1 决策锚点（D1-D11，**已裁决**，直接作为 Step 3 输入）

| ID | 决策 | 依据 / 锚 | 裁决来源 |
|----|------|-----------|----------|
| **D1** | 方案取 **M-A**：在既有 golden / synth / invariants / `limit_rules` 之上**扩展**，不新建平行体系 | X5、§2.1 | 用户 2026-11-18「按照建议执行」 |
| **D2** | **G4 本批修复**（次日路径改用 `estimate_buy_cash`）；**G5 撤回**——初判「无过期 / 零测试」不成立（实现 L1233 + 测试 `test_p014` L247-266 + docstring 自然日口径齐备），非缺陷 | U-P059-1 (b) + §2.3 **更正** | 用户 2026-11-18；G5 因初判被推翻而撤回 |
| **D3** | trace 落**测试侧** `tests/scenarios/_trace.py`，生产 `core/` 零改动 | U-P059-2、S6 | 同上 |
| **D4** | 批次编号 **P-059**（追加式，不重排 P-042..P-058） | U-P059-3 | 同上 |
| **D5** | **不引入 Hypothesis**；采纳变质关系 + 不变式驱动的方法学 | X6、X7、U-P059-4 | 同上 |
| **D6** | 边界场景 **≥10 例**，且覆盖 **≥6 层**（L1-L7 中） | U-P059-5、§3.3 | 同上 |
| **D7** | 验证报告必须**显式能力边界**：不证明策略 alpha，不证明统计显著性 | X9 | 同上 |
| **D8** | 口径锁定**日频**：不建模分钟 / tick / 盘中临停 / 集合竞价撮合；深交所退市整理首日 ±30% / ±60% 临停写入声明 | X12、S13 | 同上 |
| **D9** | **脏数据守卫仅验证侧**；生产数据层入参校验（G10 / BZ1）另立项，不扩本批生产面 | BZ1、S14 | 同上 |
| **D10** | 既有 **18 golden 零重录**；场景库不进 `tests/golden/` 根 glob 断言范围 | S10、I8 | 同上 |
| **D11** | **不引入第三方回测框架做全链路对拍**（指标层已有 `external_benchmark` 隔离 venv 先例） | §5 方案 M-D | 同上 |

### 9.2 未决索引

| ID | 未决 | 选项 | 建议 / 状态 |
|----|------|------|-------------|
| **U-P059-1** | 是否修复 G4/G5 | (a) 仅记录期望 / (b) 一并修复 | **已闭合** → 取 (b) 落 **D2**；实际范围仅 **G4**（G5 撤回） |
| **U-P059-2** | trace 实现位置 | (a) `core/trace.py` / (b) 测试侧 | 由 **D3** 落定 (b)；若 Step 9 验收要求「日常排查也用」再评估升级 |
| **U-P059-3** | 批次编号 | (a) P-059 / (b) 无编号专项 | 由 **D4** 闭合 (a) |
| **U-P059-4** | 是否引入 Hypothesis | 是 / 否 | 由 **D5** 闭合「否」 |
| **U-P059-5** | 场景必做清单规模 | 10 / 15 | 由 **D6** 收窄为「≥10 且 ≥6 层」，最终清单 Step 3 定 |
| **U-P059-6** | Step 10 异构终审基座 | GLM-5.3-Flash | 沿用 RULE-5，待 Step 10 |
| ~~**U-P059-7**~~ | ~~次日过期口径自然日 → 交易日是否变更~~ | — | **已闭合（不变更）**：自然日为 [test_p014 L248](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p014_suspension_accounting.py#L247-L266) docstring 明示的**设计口径**，非缺陷；若未来要变更，另立项 |

---

## 10. 可重放命令（E1）

```powershell
# 门禁基线（@5f85363）
$env:MPLBACKEND="Agg"; python -m pytest -q
python -m pytest -q -k golden
# 边界测试规模
Select-String -Path tests/test_limit_rules.py,tests/test_limit_mask_timing.py,` 
  tests/test_p040_bse_limit_rule_gap.py,tests/test_p014_suspension_accounting.py,`
  tests/test_universe_delisting.py,tests/test_p033_order_price_validation.py,`
  tests/test_p034_price_diff_guard.py,tests/test_rebalance_exits.py -Pattern '^def test_' | Measure-Object
# 两路径现金口径
git grep -n "1.002" -- core/engine_v2.py
git grep -n "def estimate_buy_cash" -- core/sizing.py
# 盲区证据复核（对应 §3.3，逐条可重放）
git grep -n "estimate_buy_cash" -- core/engine_v2.py            # BZ7/G4：队列 L907 精确式 vs 次日 L1274 字面式
git grep -n "_expire_next_day_orders" -- core/engine_v2.py      # BZ8 撤回：L1233 调用点存在
Select-String -Path tests/test_p014_suspension_accounting.py -Pattern 'test_expire_next_day_orders'  # BZ8 撤回：测试存在
git grep -n "special_no_limit_mask" -- filter/                  # BZ11/G14：无限制窗口唯一实现点
git grep -n "adj_factor" -- core/ filter/                       # BZ2/G15：复权因子消费点
git grep -n "weight_sum\|权重和" -- core/target_positions.py      # BZ5/G12：>1 仅 warning
git grep -n "def is_expired" -- core/pending.py                 # G5 口径：自然日计数（L215）
```

> **注**: 本节命令在 Step 2 复审时须由复审者**独立重放**并比对读数；结论与本文不一致时以重放为准（RULE-6）。

---

## 11. Step 2 异构复审（GLM-5.3-Flash，2026-11-19）

> **复审者**: GLM-5.3-Flash（≠ 作者 DeepSeek-V4.1-Flash，RULE-5）；**重放环境**: PowerShell 5.1 / Python 3.12 / HEAD `5f853637d6dc`（与页首声明一致）。

### 11.1 E1-E4 独立重放（全部复现）

| 读数 | 重放方式 | 结果 | 与正文一致 |
|------|----------|------|-----------|
| HEAD | `git rev-parse HEAD` | `5f853637d6dc…` | ✅ |
| A 全量门禁 | `pytest -q`（MPLBACKEND=Agg） | **846 passed**（62.67s） | ✅ |
| B golden | `pytest -q -k golden` | **18 passed** | ✅ |
| D G4 两路径 | grep `1\.002` + `estimate_buy_cash` | [L1274](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1274) 字面 `1.002` vs L907 精确式 | ✅ 分裂成立 |
| E G5 撤回 | Read `pending.py` L202-229 + `test_p014` L247-266 | L215 自然日计数 + `test_expire_next_day_orders`（3 单 → 2 过期 1 保留） | ✅ **撤回成立** |
| C 边界计数 | 8 文件逐文件计数 | 顶格 `^def test_` = **42**；无锚定 `def test_` = **54**（`test_rebalance_exits.py` 类内缩进 0/12） | ⚠️ 数值 54 对、方法学标签错（F-S2-P059-1） |
| 9/11 用例 | 计数 `test_reference_diff.py` / `test_invariants.py` | 9 / 11 | ✅ |
| H 测试文件数 | `Get-ChildItem tests\*.py` | 95 | ✅ |
| BZ1 | Read `data_v3.py` L99-126 | 直接 `.values`，零校验 | ✅ |
| BZ5 | Read `target_positions.py` L76-145 | L90-91 仅 warning，不归一不报错 | ✅ |
| BZ11 | Read `limit_rules.py` L180-202 + grep `delist_start_date` | 仅 IPO 前 5 日；该字段**全仓零功能消费** | ✅（证据加强） |
| BZ2 | Read `limit_rules.py` L132-177 | `replace(0, np.nan)` 局部兜底 | ✅ |

### 11.2 发现（F-S2-P059-1..8，0 P1 / 3 P2 / 5 P3）

| ID | 严重度 | 发现 | 处置 |
|----|--------|------|------|
| **F-S2-P059-1** | P3 | §2.2/§3.1-C 声明「`^def test_` 行数」与结果 54 不符（顶格计数 = 42；54 来自 `test_rebalance_exits.py` 类内缩进用例） | **已回写**：方法学标签订正为「`def test_`（含类内缩进）」 |
| **F-S2-P059-2** | P2 | **BZ13 过度悲观**：退市清算价口径已有实现（P-012 D5 `_delist_return_source`）+ 2 专项测试锁定（`test_delist_settlement_uses_delist_return` / `…_without_return_uses_last_close`）；[data.py L236](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L236) 显式上报 `delist_period_handled=False` | **已回写**：BZ13 降 P2→P3，残余改写为「回测末日未平仓持仓净值口径」 |
| **F-S2-P059-3** | P2 | **BZ14 部分覆盖**：P-014 7 用例（停牌不负持仓/不重复成交）+ golden G7（停牌账目自洽 I2）已锁定主体；残余仅「长期停牌 mark-to-market 用最后成交价」的显式断言场景 | **已回写**：BZ14 降 P2→P3 并标注部分覆盖 |
| **F-S2-P059-4** | P2 | **BZ12 原表述不成立**：复权默认 **hfq**（[data.py L490](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L490) `price_modes.returns … else "hfq"`）→ 后复权序列无除权跳空，持仓股数**设计上无需调整**（X14 担忧的前提不存在）。真实残余盲区 =「复权因子变更日 NAV 连续性」与「hfq 非整分价格 vs `limit_rules` 前收盘口径一致性」无场景锁定 | **已回写**：BZ12 降 **P1→P2** 并改写；G15 同步改写 |
| **F-S2-P059-5** | P3 | **BZ6 部分锁定**：零权重→清仓与空 dict 走同一代码路径（`weight_map.get(stock, 0.0)` → exit），已由 `test_u1_exited_positions_are_liquidated` / `test_u6_invalid_inputs_raise` / `test_g4_no_hidden_leverage` 锁定 | **已回写**：BZ6 降 P2→P3，残余仅「空 dict 端到端场景」 |
| **F-S2-P059-6** | P3 | **BZ9 部分锁定**：`test_g5_sells_precede_buys` 已锁 SELL 优先；残余 =「同日卖款可用于当日买入」的现金充分性场景未验证 | **已回写**：标注部分覆盖 |
| **F-S2-P059-7** | P3 | **docstring 与实现不符**：`special_no_limit_mask` docstring 声称退市整理期「依赖 delist_start_date」，但该字段全仓零功能消费（仅 [data.py L235](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L235) 注释 U-D2 + 上报 `delist_period_handled=False`）→ G14 证据加强 | **登记，Step 3 处置**（docstring 订正纳入 G14） |
| **F-S2-P059-8** | P3 | **BZ3 部分守卫**：[factor.py L436-442](file:///f:/Coding/Factor_Trading_v3.0/core/factor.py#L436-L442) masked rank（NaN 不参与）+ `stds.replace(0, nan)`（常量截面 → NaN → `exclude_na_factors` 排除）；残余 = optimizer `select_top` 并列排名稳定性未锁定 | **已回写**：标注部分守卫 |

### 11.3 复审结论

- **PASS**（0 P1 / 3 P2 / 5 P3）：核心结论——G4 成立、G5 撤回正确、M-A 方向、盲区框架——全部经独立重放确认；
- 3 项 P2 均为「盲区严重度/定性」修正，不推翻批次方向；**P1 计数 2 → 1（仅 BZ7/G4）**；
- 全部修正已按「Step 2 回写」标注落盘；G 计数不变（21 登记 / 20 有效）；
- 待 Step 3 消化：F-S2-P059-7（docstring 订正）、BZ12 改写后的场景定义、BZ13/BZ14 残余口径的场景化。

## 12. Step 3 DESIGN / Step 4 Review（预留）

[待 Step 3] / [待 Step 4]

## 13. Step 9/10 验收与终审（预留）

[待 Step 9] / [待 Step 10]
