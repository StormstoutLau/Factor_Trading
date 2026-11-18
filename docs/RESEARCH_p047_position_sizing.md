# RESEARCH：P-047 仓位管理（position sizing）

> **批次**: P-047 · **Step 1 调研** · 日期 2026-11-18
> **判档**: **T1**（新建 `core/sizing.py` 纯函数契约 + `tests/` + golden；U-P031-2 若在本批闭合将触碰 `core/engine_v2.py` 现金路径）
> **上游**: [UPGRADE_MASTER_PLAN.md §F3 L186-191](UPGRADE_MASTER_PLAN.md#L186-L191)（新模块 `core/sizing.py`；分数凯利 / vol-target / 风险预算 / 金字塔加减仓 / max-min size / granularity=100；**前置 U-P031-2**）；[§5 批次表 L263](UPGRADE_MASTER_PLAN.md#L263)（「sizing（F3）+ U-P031-2 裁决 | 前置 P-044 | 验收：现金守恒；分数凯利/vol-target golden」）；[PROGRESS §3.51.10](PROGRESS.md) P-045 批次 done
> **代码证据时点**: HEAD `531795e`（P-045 关闭回填；工作区净）
> **基座**: 正文 DeepSeek-V4.1-Flash；Step 2/4/6/8/10 复审由 GLM-5.3-Flash 执行（RULE-5 异构；U-P047-5 登记至 Step 10 闭合）
> **零预填声明**: 本文只写 ✅+证据 / ❌+证据 / `[待 Step N]`；§13 为 Step 2 预留，**不得**在 Step 2 前填写。

---

## 1. 触发与题干

- **触发**: 用户「启动 P 047」；总纲 §5 P-047：「仓位管理 | sizing（F3）+ U-P031-2 裁决 | 前置 P-044 | 验收：现金守恒；分数凯利/vol-target golden」。
- **题干（本批做什么）**:
  1. **统一 Sizing 层**：`core/sizing.py`——把「目标权重（或目标金额）」经科学仓位方法缩放为**可执行目标权重**；
  2. **四类方法**：分数凯利（1/4~1/2）、波动率目标（`风险预算 / (k·ATR)`）、风险预算（边际风险贡献）、金字塔加减仓（**只浮盈加仓且递减、禁摊亏**）；
  3. **约束落地**：`max_weight`/`min_weight`/`max_size`/`min_size`/`granularity=100`；
  4. **现金守恒**：sizing 输出在「给定现金 + 价格 + 费用缓冲」下**必然可成交**（预算法），并给出 U-P031-2 的裁决方案；
  5. **T+1 持仓龄**：提供持仓龄纯函数（`entry_date` → bar 数，或等价状态）并单测，证明 sizing 不改变「T 日决策、T+1 开盘成交」口径；
  6. **复用而非重写**：`tracker`（现金/持仓）、`guard_pipeline`（仓位限/最低现金语义）、`pending`（订单队列）、`target_positions.build_target_positions`（权重→整手/清仓项唯一出口）。
- **明确不做**:
  - **不做空**（负权重仍 fail-fast → **P-050**）；不做期货保证金/逐日结算（P-050）；
  - **不做优化器扩展**（BL/HRP/约束优化 → **P-046**）；**不重写 `RiskParityOptimizer`**（见 G9/U-P047-2）；
  - **不做止损/择时**（P-045 已交付 `core/stops.py` / `core/timing.py`，本批只消费其权重结果，不修改其契约）；
  - **不做策略模板与生命周期**（P-051）；不做多策略虚拟子账户资金分配（P-051/P-058）；
  - **默认不接线引擎主循环**：除 U-P031-2 裁决要求的**最小 BUY 现金检查**外，`engine_v2.py` 的交易/净值主链路零语义变更；
  - 不做盘中 tick/分钟 bar（日频矩阵；成交仍 T+1 开盘）。
- **职责外（不回答）**: 实盘下单的 size_type/订单类型（P-053）；组合优化器内的换手/行业/跟踪误差约束（P-046）；regime 切换（P-057）。
- **能力边界（回答不了）**: 本批只证明「sizing 纯函数可独立复算 + 现金守恒 + 方法 golden」；**不证明**任何 sizing 方法的样本外 alpha（属 P-051 晋级门与 P-048 风险闭环）。

---

## 2. 代码事实基线（E3 @`531795e`）

### 2.1 现有仓位/现金面盘点

| 对象 | 位置 | 现状 | 与本批关系 |
|------|------|------|-----------|
| **现金扣减** | [tracker.py L200-204](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L200-L204) | `BUY → cash -= net_amount`，**无余额检查、无夹紧** | **G2 根因**：可产生负现金 |
| **现金校验** | [tracker.py L449-462](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L449-L462) | `validate_positions` 仅把负现金写入 `errors` 列表；**全仓调用方 0 处**（grep 仅定义处命中） | 不能作为验收出口 |
| **待执行队列执行** | [engine_v2.py L841-935](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L841-L935) | BUY 仅检查 `buyable_mask` 与价格有效性；**无现金检查** | **U-P031-2 缺口所在（队列路径）** |
| **次日开盘路径** | [engine_v2.py L1204-1282](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1204-L1282) | L1257-1261：`required_cash = qty*open*1.002`，不足则**整单跳过（全有全无）** | 已有「拒绝」语义，但**非夹紧、无部分成交**，且仅此一条路径 |
| **权重→目标数量（引擎）** | [target_positions.py L43-145](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L43-L145) | `weight*total_value*value_buffer(0.985)/price` → `floor(qty/lot)*lot`；含 `is_exit=True` 清仓项 | **sizing 输出的唯一落地出口**（总纲指定） |
| **权重→目标数量（策略层）** | [execution_policy.py L410-466](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L410-L466) | `from_weights`：`target_qty = w*total_value/price`，**无 0.985 缓冲、无整手、浮点数量** | **G4 口径分裂**：与 `build_target_positions` 不一致 |
| **订单整手化** | [execution_policy.py L217-251](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L217-L251) | `T1StockPolicy.create_orders` 仅 `int(abs(tq))` 截断，**无 100 股整手** | G4：`granularity=100` 在 policy 路径不成立 |
| **优化器路径估值** | [engine_v2.py L1139-1148](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1139-L1148) | policy 路径用 `tracker.get_total_value()` 作为 `total_value` | [target_positions.py L148-175](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L148-L175) 明示该值「开盘成交后、日终盯市前不可信」→ **G7** |
| **优化器（风险平价）** | [portfolio.py L326-391](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L326-L391) | 迭代求解等风险贡献（ERC） | **禁止重复实现**；风险预算须界定边界（G9） |
| **整手权重工具** | [portfolio.py L394-423](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L394-L423) | `round_lot_optimize`（向下取整到 100 股后**再归一化权重**） | 与 `build_target_positions` 语义不同（重算权重），**不作为 sizing 出口** |
| **协方差估计器** | [portfolio.py L25-30](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L25-L30) | `sample` / `ledoit_wolf` / `ewma` | 可取对角得单资产波动；**无「目标波动缩放」出口**（G6） |
| **最低现金 Guard** | [guard_pipeline.py L251-278](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L251-L278) | `MinCashGuard(min_cash_ratio=0.05)`：`cash - order_value < pv*ratio` → **拒绝** | 语义是「拒绝整单」，非「夹紧」；且见下行 |
| **Guard 接线状态** | [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py) 全文 grep `guard` | **0 命中**；仅 `core/engine_plugins.py` L176-193 提供可插拔 `GuardPlugin` | **MinCashGuard 默认不生效** → 不能充当现金守恒保障 |
| **待执行订单队列** | [pending.py L270-537](file:///f:/Coding/Factor_Trading_v3.0/core/pending.py#L270-L537) | `max_pending_days_buy=5` / `sell=10`，半衰期过期 | sizing 不改变队列语义，只保证订单金额可支付 |
| **订单生成顺序** | [engine_v2.py L1105-1163](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1105-L1163) + [execution_policy.py L436-438](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L436-L438) | policy 路径由 `set` 并集遍历生成 intents → **先卖后买无保证** | **G10**：现金预算必须保守（只用当前现金，不预支卖出回款） |
| **不变量 I5/I7** | [invariants.py L254-333](file:///f:/Coding/Factor_Trading_v3.0/core/invariants.py#L254-L333) | `check_v3_nav_identity` / `check_v3_cost_identity`（现金流恒等式） | 现金守恒验收可复用其**恒等式形态** |
| **第二消费方** | [multi_strategy_engine.py L326-359](file:///f:/Coding/Factor_Trading_v3.0/agents/multi_strategy_engine.py#L326-L359) | 亦走 `compute_portfolio_value` + `build_target_positions` | sizing 输出可被多策略路径复用（P-051 邻域），本批不接线 |
| **golden 基线** | [tests/_golden_cases.py L36-60](file:///f:/Coding/Factor_Trading_v3.0/tests/_golden_cases.py#L36-L60) + `tests/golden/p045/` | `CASE_IDS` G1-G7（13 实例）+ P-045 隔离 2 实例 = **15** | 既有 15 零重录（I1） |

### 2.2 契约缺失证据

- `core/sizing.py` **不存在**（Glob `core/sizing*.py` → No file；E1 复跑命令见 §10）。
- 全仓 `kelly|vol_target|target_vol|position_size|volatility_target` grep：**3 命中且零实现**——`agents/adaptive_agent.py:578/585`（交易额统计字段 `avg_position_size`）、`agents/style_profile.py:267`（目标标签字符串 `position_size`）。
- 全仓 `\batr\b|average_true_range|true_range` grep：**0 命中**（G5）。
- 无「现金守恒」测试：`tests/test_phase5_business.py:106-140` 的 `test_b3_insufficient_cash` **只在测试内部模拟** `if cash < required` 分支并打印，**未调用引擎**、无断言（G3）。

### 2.3 行为锁（零行为判据来源）

| 锁 | 位置 | 作用 |
|----|------|------|
| golden 15 实例 | `tests/golden/G1-G7.json` + `tests/golden/p045/` | 既有数值基线，**不得重录** |
| P-044 weights 模式 | [engine_v2.py L361-387](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L361-L387) | `set_signal(mode="weights")`：负权重 fail-fast、行和 ≤1 | 
| P-014 停牌账目 | `tests/test_p014_suspension_accounting.py` | 双路径净值一致 |
| P-033/P-034 价格校验 | `tests/test_p033_order_price_validation.py` / `test_p034_price_diff_guard.py` | 成交价合法性 |
| P-045 原语 | `tests/test_p045_timing_stops.py` + `tests/golden/p045/` | 止损/择时语义（本批不改其契约） |

---

## 3. 取证

### 3.1 E1 本地（可重放）

| 读数 | 命令 / 方法 | 结果 |
|------|-------------|------|
| A `core/sizing.py` | `Test-Path core/sizing.py` / Glob | **False**（❌ 契约缺失） |
| B sizing 实现面 | 全仓 `*.py` grep `kelly\|vol_target\|target_vol\|position_size` | **3 命中**（2 统计字段 + 1 标签），**逻辑实现 0** |
| C ATR 原语 | 全仓 `*.py` grep `atr\|true_range` | **0 命中** |
| D 现金扣减 / 现金校验 | Read `tracker.py:192-221`；Grep `validate_positions` 全仓 | L200-204 直接扣减，无检查；`validate_positions` **定义 1 处、调用 0 处** |
| E 队列路径现金检查 | Read `engine_v2.py:841-935` | **无 BUY 现金分支**（仅 buyable/价格） |
| F 次日路径现金检查 | Read `engine_v2.py:1204-1282` | L1257-1261 有 `required_cash` 检查，不足**整单跳过** |
| G Guard 接线 | Grep `guard` in `core/engine_v2.py`；Grep `GuardPlugin` 全仓 | `engine_v2.py` **0 命中**；`GuardPlugin` 仅 `engine_plugins.py`（可插拔，非默认装配） |
| H 权重→数量口径 | Read `target_positions.py:43-145` + `execution_policy.py:410-466` + `:217-251` | 三条路径口径不一致（0.985 缓冲 / 无缓冲；floor 整手 / `int()`） |
| I 风险平价 | Read `portfolio.py:326-391` | ERC 已实现（迭代 + 收敛容差 + 约束） |
| J golden | Read `_golden_cases.py:36-60` + Glob `tests/golden/**` | `CASE_IDS`=7；文件 G1-G7 + p045 2 个 = **15 实例** |
| K 现金守恒测试 | Read `tests/test_phase5_business.py:106-140` | 「模拟」分支，无引擎调用、无断言 |
| L 基线计数 | P-045 Step 10 复跑读数（`PROGRESS.md` §3.51.10） | pytest **821** / golden **15** / black **135·203** / mypy **108** / AST **22** / `tests/*.py` **94** / uv **0** |

> 本批 Step 1 仅只读取证，未运行 pytest/git 写入；L 沿用 P-045 关闭读数，Step 9 必须本批复跑。

### 3.2 E1-EXT 外部锚点

> **证据等级**：T1=论文原文/官方规则/官方文档；T2=维护者文档/机构摘要；T3=社区/镜像。外部锚点只证明**方法学与市场规则**，不证明本仓实现正确性；不引入运行时依赖。

| # | 来源（Layer / 日期 / 版本） | 事实 | 对本项目的含义 | 置信度 |
|---|------------------------------|------|----------------|--------|
| X1 | Thorp, *The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market*, Handbook of Asset and Liability Management vol.1, Elsevier 2006, pp.385-428（T1 书章；原文 PDF 可复核）；MacLean–Thorp–Ziemba, *The Kelly Capital Growth Investment Criterion*, World Scientific 2011（T1 文集） | 半凯利（c=1/2）：增长率 `g = 0.75·g*`，`P(先翻倍后腰斩) = 8/9`；分数凯利 = 在 Kelly 建议下注与现金之间线性混合；Kelly 对参数估计误差敏感，**过度下注会显著提高破产概率** | 默认 `kelly_fraction ∈ [0.25, 0.5]`；凯利输入必须是**可估计的收益/协方差**，不得用因子分数冒充预期收益；需 fail-fast/裁剪 | 高 |
| X2 | Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert, *The Impact of Volatility Targeting*, JPM 45(1):14-33, 2018, DOI `10.3905/jpm.2018.45.1.014`（T1 期刊） | 波动率缩放**降低极端收益/回撤风险**；Sharpe 提升主要见于**股票与信用**等风险资产，债券/商品不显著；股票预期收益**不会**随波动同步上升 | vol-target 是**风险控制**工具而非 alpha 来源；A 股单边做多下应以「目标波动 + 上限 1.0」实现，不得加杠杆 | 高 |
| X3 | Moreira & Muir, *Volatility-Managed Portfolios*, Journal of Finance, 2017（T1 期刊；NBER w22208 同文） | 按近期波动反向缩放风险敞口可提高因子 Sharpe；市场组合 buy-and-hold Sharpe **约 +25%**，alpha ≈ 4.9% | vol-target 的参数（回看期/频率）会显著影响结果 → 必须 golden 锁定口径 | 高（元数据级） |
| X4 | Roncalli, *Introduction to Risk Parity and Budgeting*, 2013（T1 书）；Maillard–Roncalli–Teïletche, *The Properties of Equally Weighted Risk Contribution Portfolios*, JPM 2010（T1 期刊）；arXiv `2302.01196` §2.2（T1 预印本，风险预算定义） | 风险贡献 `RC_i = w_i(Σw)_i / σ_p`，`Σ_i RC_i = σ_p`；风险预算组合满足 `RC_i = b_i·σ_p`（`Σb_i=1`）；等预算 `b_i=1/n` 即 ERC | 风险预算的「诊断」可纯函数实现；**等预算求解已在 `RiskParityOptimizer`**，本批不得重写（G9） | 高 |
| X5 | 上海证券交易所《交易规则（2026 年修订）》3.1.4：投资者买入的证券，交收前不得卖出（回转交易除外）；英文版规则：竞价买入申报数量为 **100 股或其整数倍**（T1 官方规则） | A 股 T+1；买入整手 100 股 | `granularity=100` 的对象是**买入**；卖出允许清仓零股（持有整手时仍为整百） | 高 |
| X6 | Wilder, *New Concepts in Technical Trading Systems*, 1978（T1 书；TR/ATR 定义被 TA 文献一致转述，T2/T3 交叉验证） | `TR = max(H-L, |H-C_prev|, |L-C_prev|)`；ATR 为 TR 的 Wilder 平滑，默认周期 14 | vol-target 的 `k·ATR` 分母需新建 TR/ATR 纯函数（G5） | 高 |
| X7 | *The Original Turtle Trading Rules*（Curtis Faith；镜像 PDF）与 TurtleTrader 规则页（T2/T3，**未回官方原始源**） | 浮盈加仓：价格每有利变动 **0.5N** 加 1 个单位，单一市场最多 **4 个单位**；亏损不加仓 | 金字塔：`add_step = 0.5·ATR`、`max_adds`、只浮盈加仓、禁摊亏；作为**工程启发式**，不作为学术结论 | 中 |

> **边界声明**：X1-X7 只用于锁定语义与默认参数的**合理区间**；任何「收益提升」声明不进入验收（P-051 才评估 alpha）。

### 3.3 追加调研：A2 决策锚点（2026-11-18 用户裁决后）

> 触发：用户裁决 U-P047-1 = **A2**（sizing 预算法 + 队列路径最小 BUY 现金检查）。本节补齐「现金不足时订单语义」的行业/官方锚点与其余缺口的实践证据。

| # | 来源（Layer / 类型） | 事实 | 对本项目的含义 | 置信度 |
|---|----------------------|------|----------------|--------|
| X8 | QuantConnect《Order Errors》官方文档（T2） | `INSUFFICIENT_BUYING_POWER`（错误码 -3）：下单时买入力模型判定不足 → **订单被拒绝**（不是部分成交、不是负现金） | 「整单拒绝」是主流回测/实盘语义 → A2 采用 | 高 |
| X9 | QuantConnect《Order Factory》官方文档（T2） | 提交前可用 `result.IsSufficient` 做**预交易检查**，不足则仅记录原因、不提交 | 支持「执行前检查」而非事后续账 | 高 |
| X10 | Backtrader《Orders》/《Troubleshooting》官方文档（T2） | 订单状态 `Margin` = **not enough cash to execute the order**；且可能发生在「每个新 bar 执行前」，因为现金已被其他订单占用 | **逐单、执行时点检查**是必要设计（同日多单共享现金）→ 直接支撑 A2 的位置选择 | 高 |
| X11 | JoinQuant API 文档 + 撮合说明（T2/T3） | 资金不足 → 订单**被拒绝或调整数量**；买入需同时覆盖**手续费**，仅够股价不够手续费也会失败 | `required_cash` 必须含佣金 → A2 公式 `price*qty*(1+commission_rate)` | 中高 |
| X12 | rqalpha 源码文档（T2） | 资金不足时「use all remaining cash to create order」→ **缩量成交（clamp）** | 备选语义；A2 **不采用**（会产生数量/费用/整手重算与部分成交语义，且与既有次日路径不一致） | 高 |
| X13 | 上交所《交易规则（2026 修订）》3.3.8 / 3.3.9（T1 官方） | 买入申报 **100 股或其整数倍**；卖出时**余额不足 100 股的部分应一次性申报卖出**；单笔申报 ≤ **100 万股** | 细化 I6：BUY 必须整手；SELL 清仓允许零股一次性卖出；`granularity=100` 只约束买入侧 | 高 |
| X14 | Kelly 参数不确定性收缩（T3 量化博客；`t²/(1+t²)` 闭式）+ BSIC 工作论文（T3，噪声项 `1/N`） | 估计噪声越大，最优下注比例越应低于 1；噪声使过度下注的惩罚陡增 | 支撑 `kelly_fraction ∈ [0.25, 0.5]` 默认与「参数不确定 → 分数化」的因果解释 | 中 |
| X15 | 金字塔实践对比：Concretum Group（T3 实务研究，VT vs VP vs VP+P）+ 反例博客（T4，称金字塔在各市场加深回撤、4 单位上限亦不获支持） | 浮盈加仓在少数大趋势中可放大收益，但**风险调整后优势不稳健、回撤更深**；缺乏 T1 学术支持 | 金字塔**默认关闭**；启用时必须「只浮盈、递减、上限」；不作为默认推荐 | 中低（证据冲突，按保守处理） |

**A2 语义对照（决策锚点）**：

| 维度 | 行业语义 A：整单拒绝（X8/X10/X11） | 行业语义 B：缩量成交（X12） | A2 选择 |
|------|-----------------------------------|------------------------------|---------|
| 现金不足时 | 订单不成交 / Margin 状态 | 用剩余现金重建一个更小订单 | **A** |
| 检查时点 | 执行前逐单（X10 明确「每 bar 执行前」） | 下单时 | **执行前逐单** |
| 费用口径 | 含手续费（X11） | 含手续费 | `price*qty*(1+commission_rate)`，与既有次日路径同式 |
| 与既有代码一致性 | 与 `_execute_next_day_orders` L1257-1261「整单跳过」一致 | 需新增部分成交/重算逻辑 | **A**（最小改动） |

### 3.3-补 补充调研：Step 3 前置事项（2026-11-18，Step 2 后）

> 目的：为 DESIGN 待裁决项（F1 费式 / R1 排序 / U-P047-2/3/4）提供可解析决策锚点。证据时点同为 HEAD `531795e`，全部静态读码 + 官方文档，**未执行** pytest/golden。

#### 3.3-补.1 新代码证据（D1-D6）

| # | 事实 | 位置 | 对前置项的意义 |
|---|------|------|----------------|
| D1 | **本仓滑点是「费用行」而非价格调整**：`_calculate_cost` 中 `slippage = amount * slippage_pct; cost += slippage`；BUY 的 `net_amount = amount + cost` | [execution.py L404-405](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L404-L405)、[L335](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L335) | **S11②「exec_price 含滑点」不成立**——滑点不在价格里，而在费用里；`exec_price·qty·(1+commission_rate)` 漏掉 `slippage_pct`（默认 0.1%）→ **F1 升级为必改项** |
| D2 | 默认费率：`commission_rate=0.0003`、`commission_min=5.0`、`stamp_tax_rate=0.001`（仅卖出）、`slippage_pct=0.001` | [config.py L187-190](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L187-L190) | 买入真实成本率 = `max(amount·0.0003, 5)/amount + 0.001`。**最小佣金使小单实际费率高于 0.2%**：`amount < 5,000` 元时含费率 > 0.2%（`5/amount + 0.001 > 0.002`），即 `1.002` 字面常量对小额买单低估；`amount < 16,667` 元起最低佣金开始主导 |
| D3 | `execution_price_type` 默认 `OPEN` | [config.py L384](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L384) | 闸门用 `open_price` 估算与默认成交价口径**一致**；仅在显式改为 close/high/low 时存在偏差（可接受，与既有次日路径同风险） |
| D4 | 待执行队列按**插入顺序**遍历（`list` + `append`），`get_pending_orders` 不做排序/优先级排序 | [pending.py L287-342](file:///f:/Coding/Factor_Trading_v3.0/core/pending.py#L287-L342) | R1：改为「先卖后买」= **改变遍历顺序**，属行为变更，非最小改动 → 建议本批**不做** |
| D5 | `RiskParityOptimizer.optimize(factor_scores, returns, cov_matrix)` **无预算参数**（内部 `weights=1/n` 起步） | [portfolio.py L329-364](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L329-L364) | U-P047-2：**只能解等风险预算**；非等预算需新求解器 → 本批只做诊断，非等预算归 P-046（I10 对拍口径明确） |
| D6 | golden 根目录断言 `glob("*.json") == set(CASE_IDS)`（恰 7）；P-045 用**独立测试模块 + 子目录** `tests/golden/p045/` 装载 | [test_golden_baseline.py L100-105](file:///f:/Coding/Factor_Trading_v3.0/tests/test_golden_baseline.py#L100-L105)、[test_p045_timing_stops.py L17](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p045_timing_stops.py#L17) | U-P047-4：`tests/golden/p047/` 子目录 + 独立模块**不会**污染根断言；计数增量按 `-k golden` 收集数计（F3 口径） |

#### 3.3-补.2 新外部锚点（X16-X18）

| # | 来源（Layer） | 事实 | 对本项目的含义 | 置信度 |
|---|----------------|------|----------------|--------|
| X16 | 财政部/税务总局公告 2023 年第 39 号（T1 官方，2023-08-27；自 2023-08-28 起印花税**减半**） | 证券交易印花税减半征收（0.1% → 0.05%） | 本仓 `stamp_tax_rate=0.001` 是减半前口径 → **成本偏保守**；且印花税只在卖出侧，sizing 买入预算**不应**计入。属既有配置事实，本批**不改**，仅记录口径 | 高 |
| X17 | Harvey et al. 2018（T1，原文）：波动估计用 **20 日半衰期 EWMA**；实践者综述（T3）：短窗口 5-15 日反应快但换手高，**60-120 日更稳** | 回看期是 vol-target 的关键口径参数 | 支撑 `vol_lookback=60`（sample 日收益）默认；`method` 默认 `sample`、`ewma` 作可选；**不引入 20 日半衰期**（避免口径分叉），DESIGN 锁定并在 golden 固化 | 高（T1 方法）/ 中（T3 窗口建议） |
| X18 | QuantConnect 论坛（T3）：清算/退出订单先执行（liquidation orders executed first）；MOO 按收盘价估算成本、开盘滑点致 buying power 不足 | 「先卖后买」是业界常见自然顺序，但**依赖撮合器语义**；滑点会导致预算与实际不符 | R1：本仓无撮合器统一排序语义，改序需自证 golden 零差异 + 引入新不变量 → **不建议本批做**；A2 的「执行前按实际开盘价检查」正好兜住滑点误差（与 D3 一致） | 中 |

#### 3.3-补.3 Step 3 前置项决策建议

| 前置项 | 建议 | 依据 | 残余 |
|--------|------|------|------|
| **F1 费式** | **采用「精确成本式」而非字面 1.002**：`required_cash = amount + max(amount·commission_rate, commission_min) + amount·slippage_pct`（`amount = open_price·qty`），与 [execution.py L384-405](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L384-L405) **逐项同源**；同一纯函数供 sizing 预算（S9）与引擎闸门（S11）共用，消除双口径 | D1+D2 证明 `1.002` 对 `amount<5,000` 元的小单低估；`(1+commission_rate)` 恒低估 0.1% 滑点 | 若 golden 命中「小额+临界现金」用例而产生差异，则**闸门回退字面 `1.002`**（保守），sizing 侧仍用精确式——DESIGN 必须写明该回退条件 |
| **R1 排序** | **不重排**（维持 S11⑤）：保持队列插入顺序，接受「同日先买后卖可能多跳」 | D4 证明重排即行为变更；X18 表明业界先卖后买依赖撮合器语义，本仓无此层 | 登记为 P-048 观察项；以「保守预算（只用当前现金）」缓解 |
| **U-P047-2 风险预算** | 本批**只做诊断** `risk_contributions`（RC 与占比）+ I10 等预算对拍；非等预算求解**归 P-046** | D5：`RiskParityOptimizer` 无预算参数，强行扩展=重写 ERC（G9 禁止） | 非等预算用户诉求由 P-046 承接 |
| **U-P047-3 默认参数** | `kelly_fraction=0.5`、`target_vol=0.15`、`vol_lookback=60`（sample）、`atr_period=14`、`atr_k=2.0`、`cash_buffer=0.985`、`method="none"`、金字塔关闭 | X1（半凯利）/X2（15% 量级）/X17（60 日）/X6（14）/X7（2N）/E3（0.985 同源） | 参数不进 CLI；golden 用固定值锁定 |
| **U-P047-4 golden** | **2 个方法 case**（`kelly` / `vol_target`）+ **1 个现金预算 case**（`cash_budget`）= 3 个，置于 `tests/golden/p047/` + 独立测试模块 | D6：P-045 已验证该装载方式不污染根断言；G3 现金守恒需 golden 以外的恒等式单测，本 case 只锁口径 | 计数链 `-k golden` 由 15 → 18，DESIGN 写入 I8 |

**F4/F5/F6 处置建议（附属项）**：F4 → S9 缩减后**统一 floor 量化 + 断言**（不做二次 ceil）；F5 → 闸门用**严格 `<`**（与既有 L1259 同式，去掉 `1e-9`）；F6 → S5 的 `σ_p=0` 写入 `diagnostics.reason="zero_vol"` 并在 DESIGN 显式告警。

> **本小节不修改 §7 语义正文**：S11② 与 S9 的 `fee_buffer` 表述须由 Step 3 DESIGN 依上表裁决后统一订正（见 §7 S11② 行内批注）。

---

## 4. 缺口清单

| ID | 缺口 | 级别 | 证据 |
|----|------|------|------|
| **G1** | 无统一 sizing 层（四类方法全仓零实现） | P2 | A/B |
| **G2** | **U-P031-2 未闭合**：BUY 侧无现金夹紧——队列路径零检查、tracker 直接扣减、次日路径仅整单跳过 | **P1 → 已裁决 A2** | D/E/F + X8-X12 |
| **G3** | 无现金守恒机械测试（`test_b3_insufficient_cash` 仅本地模拟、无断言） | P2 | K |
| **G4** | 权重→数量三条路径口径不一致（0.985 缓冲 / 无缓冲；floor 整手 / `int()`） | P2 | H |
| **G5** | 无 TR/ATR 原语 → vol-target 的 `k·ATR` 分母不可用 | P2 | C |
| **G6** | 无「单资产波动估计 + 年化 + 目标波动缩放」出口（仅有协方差估计器） | P2 | I |
| **G7** | policy 路径用 `tracker.get_total_value()` 估值（文档明示不可信） | P2 | 2.1 表 · L1139 |
| **G8** | 金字塔状态无载体（`Position` 无 `add_count`/`last_add_price`；P-045 `StopState` 属止损层，不共享） | P3 | D + P-045 契约 |
| **G9** | 风险预算与既有 `RiskParityOptimizer` 职责边界未裁决（重复实现风险） | P2 | I + X4 |
| **G10** | policy 路径订单顺序由 `set` 遍历决定 → 先卖后买无保证 | P2 | 2.1 表 · L1105-1163 |
| **G11** | T+1 持仓龄无载体（`Position` 无 `entry_date`/`bar_count`）→ 「T+1 持仓龄单测」缺输入来源 | P3 | P-045 §2.1 已证；同 G8 |

---

## 5. 方案矩阵

| 方案 | 内容 | 判定 |
|------|------|------|
| **M-A（推荐）** | **纯函数 Sizing 层**：`core/sizing.py` 输入「目标权重/价格/收益/现金/配置」→ 输出「可行目标权重 + 诊断」；数量落地**统一走** `build_target_positions`；引擎默认零改动 | ✅ 纯函数可独立复算 + golden；复用唯一整手/清仓出口；不改交易/净值主链路；A 股 T+1 由「权重 → 次日开盘成交」天然满足 |
| M-B | 引擎内夹紧：改 `_process_pending_orders` + `tracker.execute_trade` 直接夹紧/拒绝 | ⚠️ 触碰主链路；golden 需证明零变化；**但**U-P031-2 的「最小闭合」只能落在引擎侧 → 作为**可选子项 A2**（见 U-P047-1），不作为 sizing 主体 |
| M-C | 强制装配 `MinCashGuard`（默认 5% 现金） | ❌ 改变现有回测行为（默认拒绝部分订单）；Guard 语义是**拒绝**不是**夹紧**；且 `engine_v2` 未接线 Guard |
| M-D | 把 sizing 并入优化器（`portfolio.py`） | ❌ 职责混淆：sizing 是「权重后处理/叠加」，优化器是「权重分配」；与 P-046 边界冲突；会重写 ERC |
| M-E | 引入 riskfolio/ffn 等第三方 | ❌ 违反零新增依赖；与 P-046 的依赖分档裁决冲突 |

**裁决（2026-11-18 用户）**: **M-A（主体）+ A2（U-P031-2 闭合）**。理由：M-A 是唯一同时满足「纯函数可复算 / 不重复优化器 / 默认不接线」的方案；A2 与既有次日路径「整单跳过」同式（X8/X10/X11），改动限于 `_process_pending_orders` 的 BUY 分支，且必须证明 golden 15 零差异。A1 不再作为候选（无法让「现金守恒」端到端机械成立）。

---

## 6. 批次切分（供 DESIGN 采用；以 IMPL 文件对齐为准）

| 批次 | 内容 | 行为 | 验收 |
|------|------|------|------|
| **B1 波动原语** | `core/sizing.py`：`estimate_volatility`（滚动/EWMA，年化）+ `atr`（Wilder TR/ATR） | 零行为（新符号） | 逐值单测（含 NaN/warmup） |
| **B2 方法层** | `kelly_weights` / `vol_target_scale` / `risk_budget_diagnostics` / `pyramid_step` + `SizingConfig` | 零行为（纯函数） | 分数凯利与 vol-target golden；风险预算诊断与 ERC 对拍 |
| **B3 落地层** | `apply_sizing` + `cash_budget_scale` + `SizingState`（JSON 安全）+ 对接 `build_target_positions` | 默认零行为（不接线） | 现金守恒恒等式；granularity=100；清仓项保留 |
| **B4 测试与文档** | `tests/test_p047_position_sizing.py` + golden（隔离 `tests/golden/p047/`）+ 四文档 + U-P031-2 处置 | 若 A2 启用则引擎**局部**变更 | pytest/golden 计数按 DESIGN 更新；既有 15 零重录 |
| **B5 A2 现金闸门** | [engine_v2.py L841-935](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L841-L935) `_process_pending_orders`：BUY 执行前 `required_cash = price*qty*(1+commission_rate)` 不足 → **整单跳过 + logger.warning + 保留队列**（受既有 5 日过期） | 引擎**局部**行为变更（仅现金不足场景） | 现金不变量单测；golden 15 **零差异**；队列长度不变 |

> B2 依赖 B1；B3 依赖 B2；B5 依赖 B4 的现金预算语义；B4/B5 同批提交。B5 的 diff **仅限** `_process_pending_orders` 内的 BUY 现金闸门，不含顺序重排、不含 tracker 改动。

---

## 7. 精确语义（实施规格输入；DESIGN 可细化）

| # | 语义 |
|---|------|
| S1 | `SizingConfig`（frozen）：`method ∈ {"none","kelly","vol_target","risk_budget"}`（默认 `none`=零行为）；`kelly_fraction`（默认 0.5，允许区间 [0.25,0.5]，越界 fail-fast）；`target_vol`（年化，默认 0.15）；`vol_lookback`（默认 60）；`atr_period`（14）/`atr_k`（2.0）；`max_weight`/`min_weight`/`max_size`/`min_size`；`granularity`（100）；`cash_buffer`（0.985，与 `build_target_positions.value_buffer` 同源语义）；`pyramid`: `add_step_atr=0.5` / `max_adds=3` / `decay=0.5` / `only_profitable=True` |
| S2 | `estimate_volatility(returns, *, lookback, method="sample"\|"ewma", annualize=True, periods=252)`：纯函数；样本不足或 NaN → 返回 NaN（调用方必须显式处理，禁止静默 0） |
| S3 | `atr(high, low, close, *, period=14)`：`TR = max(H-L, |H-C_prev|, |L-C_prev|)`；Wilder 平滑；前 `period` 个 bar 为 NaN；首日 `C_prev` 缺失时 `TR=max(H-L)` |
| S4 | `kelly_weights(expected_returns, cov, *, fraction, risk_free=0.0)`：`f = fraction · Σ^{-1}(μ-rf)`；`f < 0 → 0`（不做空）；`Σf > 1 → 按比例缩至 1`（A 股无杠杆）；协方差奇异 → `ValueError`（fail-fast，不静默加 ridge） |
| S5 | `vol_target_scale(weights, cov, *, target_vol)`：`σ_p = sqrt(wᵀΣw)`；`scale = min(target_vol/σ_p, 1.0)`；返回 `scaled_weights = weights*scale` 与 `scale`；`σ_p=0` → scale=1（并记诊断） |
| S6 | `risk_contributions(weights, cov)`：`RC_i = w_i(Σw)_i/σ_p`，返回 `RC` 与 `RC/σ_p`（占比和=1）；**等预算求解复用 `RiskParityOptimizer`**，非等预算求解 `[待 DESIGN/P-046]` |
| S7 | `pyramid_step(state, *, price, atr, config)`：仅当 `price ≥ entry_price`（浮盈）且 `price ≥ last_add_price + add_step_atr·ATR` 且 `add_count < max_adds` 时加仓；加仓规模按 `decay^add_count` 递减；`price < entry_price` **永不加仓**（禁摊亏）；返回新 `SizingState` + 增量权重 |
| S8 | `apply_sizing(weights, *, config, cov=None, vols=None) -> SizingResult`：裁剪到 `[min_weight, max_weight]`；总权重 ≤1（按比例缩放，不重排相对序）；`min_size` 按金额下限过滤（过滤后余额留现金，不再归一） |
| S9 | `cash_budget_scale(weights, *, cash, prices, total_value, granularity, cash_buffer)`：`buy_cost = Σ ceil_lot(qty_i)·price_i·(1+fee_buffer)`；若 `buy_cost > cash·cash_buffer` → **等比缩减买入侧**直至满足；卖出侧不受限（清仓项 `is_exit` 必须保留）；**只使用当前现金**，不预支当日卖出回款（G10）。**⚠️ Step 2 F1 + §3.3-补.1 D1/D2：`fee_buffer` 不得写成 `commission_rate` 单项（漏 0.1% 滑点 + 5 元最低佣金），须用精确成本式或 ≥0.002 的保守常量；缩减后统一 floor 量化并断言（F4）** |
| S10 | 输出契约：`SizingResult`（frozen，JSON 安全）= `weights`（最终目标权重）+ `scale` + `diagnostics`（dropped/skipped 原因）；**不建订单、不读配置、不做 I/O、不写全局态** |
| S11 | **A2 现金闸门**（`_process_pending_orders`，仅 BUY）：①位置 = buyable/价格校验之后、执行器调用之前；②估算 `required_cash = exec_price·quantity·(1+commission_rate)`（`exec_price` 含滑点，费率取引擎同字段，与 [L1257-1261](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1257-L1261) 同式）**⚠️ Step 2 F1 + §3.3-补.1 D1/D2：本仓滑点是费用行（`cost += slippage`），`exec_price` 并不含滑点，且最小佣金 5 元使小单实际费率 > 0.2% → 本式低估；DESIGN 须按 §3.3-补.3 改为「精确成本式」或回退字面 `1.002`**；③`tracker.get_cash() + 1e-9 < required_cash` → **整单跳过**（不成交、不扣款、不改数量）+ `logger.warning`（F5：建议改严格 `<`）；④订单**保留在队列**，由既有 5 日过期机制自然淘汰；⑤**不改变遍历顺序**（最小改动；若同日卖出先执行，其回款自然可用）；⑥不新增配置开关（缺陷修复默认生效，golden 零差异兜底） |

---

## 8. 行为变更与不变式

**默认路径（`method="none"` 或不接入）**：交易/净值/产物逐值不变；golden 既有 **15 零重录**。
**使用 sizing**：纯函数产出权重后，仍走 `set_signal(mode="weights")` → `build_target_positions` → 既有执行链；引擎改动**仅限** S11 的 BUY 现金闸门（A2）。

| ID | 不变式 |
|----|--------|
| I1 | 既有 golden **15 零重录**；`core/engine_v2.py` 的 diff **仅限** `_process_pending_orders` 内的 BUY 现金闸门（S11），且 golden 15 零差异 |
| I2 | `core/sizing.py` 纯函数：无 I/O、无全局写、无随机（AST `open`/`requests` = 0） |
| I3 | **现金守恒**：任意 `SizingResult` 在给定现金下，`Σ买单成本(含费) ≤ cash·cash_buffer`；逐笔模拟账本 `cash_t ≥ -1e-6`；现金流恒等式与 [invariants.py I7](file:///f:/Coding/Factor_Trading_v3.0/core/invariants.py#L305-L333) 同形 |
| I4 | 确定性：同输入两次输出逐值相同；分数凯利/vol-target 各 ≥1 golden 锁定 |
| I5 | 无前视：T 日 sizing 只用 ≤T 的收益/价格；成交仍 T+1 开盘 |
| I6 | `granularity=100`：BUY 数量为 100 整数倍；SELL 清仓允许零股；`is_exit=True` 项不得被 sizing 过滤 |
| I7 | 零新增依赖（不引入 riskfolio/ffn/PyPortfolioOpt 运行时依赖） |
| I8 | 计数链基线：pytest **821** / golden **15** / black **135·203** / mypy **108** / AST **22** / `tests/*.py` **94** / uv **0**；增量（+1 源 `core/sizing.py`、+1 测试文件、+golden 实例）**以 DESIGN 为准**并入五文档 |
| I9 | 状态可序列化：`SizingState` JSON 往返相等；可随策略状态重放 |
| I10 | 风险预算不重复：等预算（`b_i=1/n`）结果与 `RiskParityOptimizer` 对拍一致（容差 ≤1e-6）；非等预算若实现，必须复用同一求解内核 |

---

## 9. 未决项登记（四元块）

- **U-P047-1 U-P031-2 裁决（P1）→ ✅ 已裁决 A2（2026-11-18，用户）**
  - 裁决内容：**A2 = sizing 预算法 + 队列路径最小 BUY 现金检查**；A1（仅预算法）不再作为候选
  - 落地规格：S11（整单跳过 / 执行前逐单 / 含佣金 / 保留队列 / 不改顺序 / 无开关）
  - 证据锚点：X8（QuantConnect 拒单）、X10（Backtrader Margin 逐 bar 检查）、X11（JoinQuant 含手续费）、X12（rqalpha clamp 为备选、已拒）；E3（`tracker.py` L200-204 + `engine_v2.py` L841-935 / L1257-1261）
  - 残留风险：R1 同日「先买后卖」时可能多跳过（不重排顺序的最小改动代价）→ **§3.3-补.3 已裁建议：本批不重排**（D4 队列按插入顺序、X18 先卖后买依赖撮合器语义）；登记 P-048 观察项
  - 证据等级：E1-EXT X8-X12（T2 官方文档为主）+ E3

- **U-P047-2 风险预算边界**
  - 判据：`risk_budget` 是「诊断输出」还是「求解器」；非等预算是否本批实现
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**本批只做风险贡献诊断 + 等预算复用 `RiskParityOptimizer`**；非等预算求解归 P-046（避免重复实现，G9）
  - 证据等级：E3（`portfolio.py` L326-391）+ E1-EXT X4 + **§3.3-补.1 D5（`optimize` 无预算参数，只能解等预算）**

- **U-P047-3 默认参数与启用方式**
  - 判据：`kelly_fraction`（0.25 vs 0.5）、`target_vol`（15% vs 20%）、`atr_k`（2.0）、`vol_lookback`（60）
  - 触发条件：Step 3 DESIGN
  - 当前倾向：默认 `method="none"`（零行为）；文档给推荐值，golden 用固定值锁定；参数不做 CLI 暴露（本批）；**推荐值见 §3.3-补.3**（`0.5 / 0.15 / 60 / 14 / 2.0 / 0.985`）
  - 证据等级：E1-EXT X1/X2/X7 + **X17（回看期 60-120 日更稳）/ X16（费率口径）** + E3（`OptimizerConfig` 默认风格）

- **U-P047-4 golden 新增 case**
  - 判据：新增几个 case、目录与计数
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**2 个方法 case（分数凯利 / vol-target）+ 1 个现金预算 case = 3 个**，隔离到 `tests/golden/p047/` 并配独立测试模块（沿用 P-045 `F-S9-P045-1` 教训：P-013 harness 以 `glob("*.json")` 扫根目录并断言恰为 `CASE_IDS`）；既有 15 零重录；`-k golden` 计数 15 → 18
  - 证据等级：E3（`tests/golden/` 结构 + `_golden_cases.py`）+ **§3.3-补.1 D6（P-045 子目录装载模式已验证）**

- **U-P047-5 异构终审**
  - 判据：Step 2/4/6/8/10 复审基座与作者不同
  - 触发条件：进入 Step 10
  - 当前倾向：作者 DeepSeek-V4.1-Flash；Step 2/4/6/8/10 由 GLM-5.3-Flash 承接
  - 证据等级：E1（会话基座）

---

## 10. 可重放命令

```powershell
$py = 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe'
# E3：契约缺失（只读）
& $py -c "import pathlib; print('sizing.py:', pathlib.Path('core/sizing.py').exists())"
# E3：sizing 实现面（应仅统计字段/标签）
Select-String -Path (Get-ChildItem -Recurse -Filter *.py core,agents,filter,tests).FullName -Pattern 'kelly|vol_target|target_vol|position_size'
# E3：ATR 原语缺失
Select-String -Path (Get-ChildItem -Recurse -Filter *.py core,agents,filter,tests).FullName -Pattern 'average_true_range|true_range|\bATR\b'
# E3：BUY 现金检查分布
Select-String -Path core\engine_v2.py -Pattern 'required_cash|enable_fallback'
# E3：Guard 是否接线引擎
Select-String -Path core\engine_v2.py -Pattern 'guard|Guard'
# E1 基线（Step 9 必跑）
$env:MPLBACKEND='Agg'; & $py -m pytest tests -q -p no:cacheprovider
& $py -m pytest tests -k golden -q -p no:cacheprovider
& $py -m black --check core tests
& $py -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
uv lock --check
```

> Step 1 未执行 pytest/black/mypy/uv（只读取证）；基线沿用 P-045 关闭读数（§3.1-L），Step 9 回填红/绿。

---

## 11. Step 1 自查（RULE-4）

| # | 自查项 | 结论 |
|---|--------|------|
| 1 | 题干是否收窄 | ✅ 做空/优化器扩展/止损/策略模板/盘中 bar/虚拟子账户显式排除（§1） |
| 2 | 事实与推测分离 | ✅ G1-G11 均绑 E1 文件行号（@`531795e`）；外部结论标 Layer/置信度（§3.2） |
| 3 | 是否重做 P-042/P-043/P-044/P-045 | ✅ 复用 `Strategy`/`set_signal`/`StopState` 语义，不改其契约（§2.3） |
| 4 | 是否以「跑通」代替正确性 | ✅ 验收含现金恒等式、granularity、确定性 golden、ERC 对拍（I3-I6/I10） |
| 5 | 方案矩阵是否穷举 | ✅ M-A~M-E；四条拒绝理由（主链路/语义/职责/依赖） |
| 6 | 是否触碰交易/净值语义 | ✅ 默认 `method="none"` 零 diff；A2 仅 `_process_pending_orders` BUY 闸门局部改动，以 golden 15 零差异证明（I1/S11） |
| 7 | 是否新增外部依赖 | ✅ 零新增；外部来源仅作方法学锚点 |
| 8 | 外部引用是否可解析 | ✅ X2 DOI 命中（pm-research）；X5 官方域 `sse.com.cn` 命中；X1/X3/X4/X6 为书/期刊元数据，**Step 2 需逐条解析**（§13 预留） |
| 9 | A2 决策锚点是否充分 | ✅ X8-X12 覆盖「拒单 / 逐单执行前检查 / 含费用 / clamp 备选」四类语义；X13 细化整手/零股；A2 与既有 next-day 路径同式（S11） |
| 10 | 追加调研是否改变题干 | ✅ 仅收窄：金字塔默认关闭（X15 证据冲突）、`granularity` 只约束买入（X13）、A1 移除（§5） |

---

## 12. 判档

**T1**——新建 `core/sizing.py` 契约（判档规则 2 强制）、改动面含 `tests/` 与 golden；且 U-P031-2 若在批内闭合将触及 `core/engine_v2.py`（真值源/主链路）。

---

## 13. Step 2 Review（异构）

> **复审基座**: GLM-5.3-Flash（作者 DeepSeek-V4.1-Flash，RULE-5 异构）· 2026-11-18
> **复审时点**: 工作区代码 = HEAD `531795e`（仅两份文档未提交，代码文件零 diff → E3 锚点有效）
> **取证形态声明**: ①E1 命令重放**未执行**（复审会话只读，pytest/black/mypy/uv 归 Step 9 复跑）；②E2 运行时探针无对象可探（`core/sizing.py` 尚不存在）→ 以 **E3 静态复核**替代；③引用核验：复审**重放 3 组检索**（X8/X12/X13 官方原文），其余按层级抽验；④机械复核：行号锚点、计数算术、编号体系、零预填合规。
> **结论**: **有条件通过**——F1（S11② 费式口径与既有代码不同源）必须在 Step 3 DESIGN 裁决后方可进入 IMPL；F2 建议顺带订正；F3-F6 登记。

### 13.1 E3 机械复核矩阵（复审独立重跑，24 项全 ✅）

| # | 复核项 | 复审读数 | 判定 |
|---|--------|----------|------|
| 1 | `core/sizing.py` 存在性 | Glob → No file | ✅ 与 §2.2 一致 |
| 2 | sizing 方法实现面 | grep `kelly\|vol_target\|target_vol\|position_size` → 恰 3 命中：`style_profile.py:267`、`adaptive_agent.py:578/585` | ✅ 与 §2.2 一致 |
| 3 | ATR 原语 | grep `\batr\b\|average_true_range\|true_range` → 0 命中 | ✅ G5 成立 |
| 4 | 现金扣减 | [tracker.py L200-204](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L200-L204)：`BUY → self._cash -= trade.net_amount`，无检查 | ✅ G2 根因链成立 |
| 5 | 现金校验调用面 | 全仓 grep `validate_positions` → 仅定义（tracker.py:449）+ 2 处文档引用，**调用 0** | ✅ 与 §2.1 一致 |
| 6 | 队列路径现金检查 | [engine_v2.py L841-935](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L841-L935)：BUY 仅 buyable（L873）+ 价格（L900），**无现金分支** | ✅ A2 落点成立 |
| 7 | 次日路径现金检查 | L1257-1261：`required_cash = order.quantity * open_price * 1.002`，不足 → `failed_orders` 整单跳过 | ✅ 语义 A 同式；**但见 F1** |
| 8 | P-044 weights 模式 | L361-387：负权重 fail-fast（L381-382）、行和 ≤1（L383-384）、未知标的 fail-fast（L375-377） | ✅ §2.3 锁成立 |
| 9 | `from_weights` 口径 | L436 `set` 并集遍历、L447 `target_qty = w*total_value/price` 浮点、无缓冲无整手 | ✅ G4/G10 成立 |
| 10 | `create_orders` 整手 | L248 `quantity=int(abs(tq))`，无 100 股整手 | ✅ G4 成立 |
| 11 | `build_target_positions` | L51 `value_buffer=0.985`、L130-132 floor 整手、L101-110 `is_exit` 清仓项 | ✅ sizing 唯一出口成立 |
| 12 | 估值口径警告 | `compute_portfolio_value` L156-158 明示 `tracker.get_total_value()`「开盘成交后、日终盯市前不可信」 | ✅ G7 成立 |
| 13 | policy 路径估值 | engine_v2 L1139 `total_value = tracker.get_total_value()` 直用 | ✅ G7 缺口确认 |
| 14 | 协方差估计器 | [portfolio.py L26-30](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L26-L30) `sample/ledoit_wolf/ewma` | ✅ 与 §2.1 一致 |
| 15 | ERC 已实现 | `RiskParityOptimizer` L326-391（迭代 + `risk_parity_tol` 收敛） | ✅ G9「禁止重写」前提成立 |
| 16 | `round_lot_optimize` | L394-423 floor→再归一化（重算权重语义） | ✅ 「不作为 sizing 出口」判定成立 |
| 17 | `MinCashGuard` | [guard_pipeline.py L251-278](file:///f:/Coding/Factor_Trading_v3.0/core/guard_pipeline.py#L251-L278)：BUY-only、`remaining < pv*ratio` → passed=False（拒绝语义） | ✅ M-C 拒绝理由成立 |
| 18 | Guard 接线 | engine_v2 全文 grep `guard\|Guard` → **0 命中** | ✅ 「默认不生效」成立 |
| 19 | 队列过期参数 | `pending.py:276` `max_pending_days_buy=5/sell=10`；`config.py:377-378` 同值 | ✅ S11④ 前提成立 |
| 20 | 不变量 I5/I7 | `check_v3_nav_identity` L254-278 / `check_v3_cost_identity` L305-333 | ✅ I3 引用 L305-333 **精确命中** |
| 21 | 第二消费方 | [multi_strategy_engine.py L341-358](file:///f:/Coding/Factor_Trading_v3.0/agents/multi_strategy_engine.py#L341-L358)：`compute_portfolio_value` + `build_target_positions` | ✅ 与 §2.1 一致 |
| 22 | golden 文件面 | `tests/golden/G1-G7.json`（7）+ `p045/P045_S1/S2.json`（2）= 9 文件 | ✅ 与 §2.1 一致 |
| 23 | golden 计数口径 | `CASE_IDS` 7 元组；harness `parametrize(case_id)` 7 参数化；P-045 关闭读数 `-k golden` = **15 passed**（见 [test_golden_baseline.py L102](file:///f:/Coding/Factor_Trading_v3.0/tests/test_golden_baseline.py#L102) 根目录 `glob("*.json")` → U-P047-4 前提成立） | ✅ 算术 13+2=15 自洽；**口径备注见 F3** |
| 24 | §10 命令语法 | PowerShell 5.1 语法目测合规（`Select-String`/`Get-ChildItem`/`& $py`） | ✅ 静态审通过（未执行） |

### 13.2 外部引用核验（复审重放/抽验）

| # | 层级 | 验证方式 | 状态 |
|---|------|----------|------|
| X5 | T1 官方 | 复审重放检索：上交所官网 3.1.4「投资者买入的证券，交收前不得卖出」**原文命中** | ✅ |
| X8 | T2 官方 | 复审重放检索：QuantConnect 文档 error code 表「-3 InsufficientBuyingPower - Not enough money to submit order」（负 order-id 拒单）**原文命中** | ✅ |
| X12 | T2 官方 | 复审重放检索：rqalpha 文档「如果资金不足，该API将会使用最大可用资金发单」+ 源码日志 `insufficient cash, use all remaining cash({}) to create order` **原文命中** → clamp 语义确认 | ✅ |
| X13 | T1 官方 | 复审重放检索：《交易规则（2026 修订）》3.3.8「申报数量应当为100股（份）或其整数倍。卖出…余额不足100股…一次性申报卖出」、3.3.9「单笔申报最大数量…不超过100万股」**逐字命中** | ✅ |
| X1/X3/X4/X6 | T1 文献 | 元数据级复核（Thorp 2006 Elsevier 书章 / Moreira & Muir JF 2017 / Roncalli 2013 + Maillard et al. JPM 2010 / Wilder 1978）：均为领域标准文献，元数据一致；**正文数字（8/9、0.75·g*、+25%、RC 定义）未逐页比对**——这些锚点仅锁参数区间，不影响语义决策 | ✅（元数据级） |
| X2 | T1 期刊 | DOI `10.3905/jpm.2018.45.1.014` 作者侧已解析命中；复审未重放 | ✅（沿用） |
| X7 | T2/T3 | 作者已自我声明「未回官方原始源」；仅作工程启发式 | ✅（诚实标注） |
| X9/X10/X11 | T2/T3 | 复审未重放；均为「执行前检查/逐 bar/含费用」方向性支撑，且与 X8/X12/X13 已验证锚点同向 | ✅（方向性） |
| X14/X15 | T3/T4 | 复审未重放；X15 已按「证据冲突 → 默认关闭」保守处理 | ✅（保守处理） |

### 13.3 发现清单

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F1** | **MEDIUM（DESIGN 前置条件）** | **S11② 费式与既有代码不同源**：既有 L1258 是**字面常量** `qty*open*1.002`（非 `cfg.commission_rate` 字段）；且队列路径中 engine 传给 executor 的是 `open_price`（L909-911），滑点在 executor 内部施加——执行前 engine 不知道「含滑点 exec_price」。S11② 写 `exec_price·quantity·(1+commission_rate)` 并自称「与 L1257-1261 同式」，两处偏差（常量 vs 字段；滑点可知性）在边界 cash 场景可能给出不同 skip 决策，而 I1 要求 golden 15 零差异 | **Step 3 DESIGN 必须二选一并写明**：(i) 完全复刻 `1.002` 字面（跨路径一致、最小惊讶——**复审倾向**）；或 (ii) `open_price·qty·(1+cost 打包系数)` 配置驱动（需以 golden 数据证明零差异）。S11② 表述随裁决订正 |
| F2 | LOW（措辞精度） | §2.2/§3.1-K「无断言」过强：`test_b3_insufficient_cash` 实有 1 处 setup assert（`assert required > cash`）+ `if/else return False`；且 pytest 下 `return False` 不计失败——G3 实质（未调引擎、未断言**引擎行为**）成立 | DESIGN 顺带改为「仅 1 处 setup assert，未调用引擎、未断言引擎行为」 |
| F3 | INFO（计数口径） | 「13 实例」= golden 关联测试 `-k golden` 收集数（P-045 关闭读数 15 = 13+2），非 golden 文件数（9）亦非 harness 参数化数（7） | I8 建议备注口径「`-k golden` 收集数」；Step 9 复跑时对齐 |
| F4 | INFO（不动点） | S9 用 `ceil_lot` 估算 `buy_cost` 后等比缩减，缩减后权重再次 `ceil_lot` 量化可能轻微超出预算（量化不动点） | S11 引擎闸门可兜底残余违例；DESIGN 应声明「预估保守（ceil）+ 闸门兜底」双层结构，或改 floor 量化 |
| F5 | INFO（容差） | S11③ `get_cash() + 1e-9 < required_cash` vs 既有 L1259 严格 `<` | 与既有路径同式（严格 `<`）或在 DESIGN 说明容差来源；不阻塞 |
| F6 | INFO（边界语义） | S5 `σ_p=0 → scale=1`：与 `min(target/σ_p, 1)` 公式自洽（inf→1），但「零波动估计→维持满权重」需 diagnostics 显式警示 | DESIGN 在 S5 诊断字段中落实 |

### 13.4 合规检查

- **零预填（RULE-1）**: ✅ §13 原文仅 `[待 Step 2]` 占位，无越权结论；全文未发现「先写结论后找证据」段落。
- **编号体系**: ✅ X1-X15 / G1-G11 / M-A~M-E / B1-B5 / S1-S11 / I1-I10 / U-P047-1..5 / F1-F6 无冲突（外部锚点 X 与语义 S 已分离）。
- **逻辑一致性**: ✅ A1 移除（§5）与 §11 #10、「A2 与次日路径同式」与 X8/X10/X11、G10 保守预算与 S9「只用当前现金」、R1 残留风险与 S11⑤ 相互一致。
- **判档**: ✅ T1 维持——新建契约 + 触及 `engine_v2.py`（真值源）。
- **E1 基线计数**: 沿用 P-045 关闭读数并明示「Step 9 必须复跑」（§3.1-L 注）——诚实，不构成缺陷。

### 13.5 复审结论

**有条件通过**。Step 1 的证据链（E3 24 项 + 外部锚点承重项）复审独立复核全部成立，缺口清单、方案矩阵、批次切分、精确语义可直接作为 DESIGN 输入；唯一实质问题 **F1** 属「规格措辞 vs 既有代码」口径分歧（不影响 A2 裁决本身，X8/X12/X13 已验证「整单拒绝」语义正确），在 Step 3 DESIGN 裁决费式后即可解除。F2-F6 均登记不阻塞。U-P047-2/3/4 按原计划在 DESIGN 裁决；U-P047-5（异构终审）按计划延至 Step 10。
