# RESEARCH：P-051b 策略模板库（`strategies/` + registry）

> **批次**: P-051b · **Step 1 调研** · 日期 2026-11-21
> **上游**: [UPGRADE_MASTER_PLAN F5](UPGRADE_MASTER_PLAN.md)（L205-206 新模块与模板清单；L207-210 生命周期/多策略资金分配 → **P-051c**）；[PROGRESS §1.4](PROGRESS.md#L200)（P-051b 行）；[P-044 已关闭](CHECKLIST_p044_strategy_interface.md)（Strategy Protocol / BacktestAdapter / registry 已交付）；[P-051a 已关闭](../docs/PROGRESS.md#L2860)（`core/volatility.py` + sizing 接线）
> **代码证据时点**: HEAD `9c914df`（工作区干净）
> **基线读数**（实测，关闭 P-051a 时）：pytest **1040** / `-k golden` **22** / mypy **113 files 0** / black `core tests` **157** / `tests/*.py` **112** / `core/*.py` **45** / `strategies/` **不存在**

---

## 1. 范围与前置

**做**（候选，Step 3 收敛）：
1. 新建 `strategies/` 包：4 类模板——**网格（ATR 间距）** / **趋势跟踪（N 日突破 + 均线符号）** / **时序动量（多周期收益符号）** / **均值回归（z-score 进出 + 时间止损）**；
2. 每模板实现 `core.strategy.Strategy` Protocol（`meta` + `generate_signals`），并带 `@register_strategy` 注册；
3. 模板参数 schema / 版本 / `code_hash` 走 `StrategyMeta`（P-044 既有）；
4. 端到端驱动测试：`BacktestAdapter.views_from_data` → `signals_frame` → `engine.set_signal(mode="weights")` → 回测；
5. 四文档 + 台账。

**不做**：生命周期（晋级门/监控/退役/多策略虚拟子账户）→ **P-051c**；截面多空 + 股指期货对冲（依赖 U-P031-1）；月差套利（依赖期货连续合约数据，当前 `get_adj_price` 无近远月）；实盘；参数自动寻优（`batch_backtest` 已有 `run_param_grid`，不重复造）；**agent 策略生成（L0-L3）→ 另立批次，见 §11 / §12 与 U-P051b-7..9**。

**前置事实**：
- `core/strategy.py` 已交付 Protocol 与适配器，但**仓库无任何策略模板实现**（`strategies/` 目录不存在）；
- 引擎 `set_signal(mode="weights")` 已支持外部权重直供（P-044 D5），是模板接入引擎的现成通道；
- 波动原语（`estimate_volatility` / `atr`）与 sizing 接线已于 P-051a 交付；**`MarketView` 仍只有当日横截面**。

---

## 2. 代码证据（逐条实读）

| # | 锚点 | 事实 |
|---|------|------|
| E1 | [strategy.py L122-130](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L122-L130) | `Strategy` 为 `@runtime_checkable` Protocol：`meta` property + `generate_signals(view, state) -> TargetWeights`；只产权重、不接触订单 |
| E2 | [strategy.py L111-120](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L111-L120) | `MarketView` 五字段：`date / signal / tradable / prices / returns`；**无 `high/low/volume`、无时序价格窗口** |
| E3 | [strategy.py L222-270](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L222-L270) | `BacktestAdapter.signals_frame`：逐日调用策略→物化权重矩阵；未出现标的记 0；`state_history` 按日追加 |
| E4 | [strategy.py L272-310](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L272-L310) | `views_from_data`：`signal` 按 `(trade_dates, stock_codes)` 重排；`prices=get_adj_price("close","raw")`；`returns_window>0` 且 `i>=window` 时给**截至前一日**窗口（`returns_matrix.iloc[i-window:i]`） |
| E5 | [engine_v2.py L614-656](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L614-L656) | `set_signal(mode="weights")`：index 必须等于 `dm.trade_dates`；未知标的 fail-fast；**非负**；行和 `≤1+1e-9`；缺列补 0；可选 `external_max_weight` |
| E6 | [registry.py L60-90](file:///f:/Coding/Factor_Trading_v3.0/core/registry.py#L60-L90) | `PluginRegistry.register(name, factory, description, config_schema, metadata)`；重复名 `logger.warning` + 覆写；工厂约定签名 `(config, **kwargs) -> T` |
| E7 | [registry.py L225-230 / L341-359](file:///f:/Coding/Factor_Trading_v3.0/core/registry.py#L341-L359) | `get_strategy_registry()` + `register_strategy` 装饰器已交付；注册依赖「模块被 import」这一副作用 |
| E8 | [strategy.py L132-167 / L170-219](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L132-L219) | 既有两实现均为「因子分 → optimizer → 权重」，模板层无先例 |
| E9 | [agent_framework.py L436-510](file:///f:/Coding/Factor_Trading_v3.0/agents/agent_framework.py#L436-L510) | 动量型 Agent 先例：`factor_momentum` + zscore + `select_top`，但输出的是**信号/因子分**，不是权重 |
| E10 | [volatility.py](file:///f:/Coding/Factor_Trading_v3.0/core/volatility.py) | `estimate_volatility`（窗口**含当日**，`TRADING_DAYS=252`）/ `atr`（标准 Wilder）；O-P051a-3 已登记口径差 |
| E11 | 全仓 grep `mean_reversion|breakout|ts_momentum|grid`（`*.py`） | **无策略实现命中**：仅 `batch_backtest.engine.run_param_grid`（参数网格）与 matplotlib `.grid()`；模板为全新 |

---

## 3. 缺口清单

| ID | 缺口 | 影响 | 证据 |
|----|------|------|------|
| **G1** | `MarketView` 无**时序价格历史**（仅当日 `prices` + 可选 `returns` 窗口） | 阻断 均线/突破/ATR/`high-low` 类模板（网格与趋势的核心输入） | E2/E4 |
| **G2** | 引擎无「直接消费 `Strategy`」的入口，只能经 `BacktestAdapter` 外部驱动 + `set_signal` | 可用但链路在引擎外；P-051c 多策略虚拟子账户需要引擎内循环 | E3/E5 |
| **G3** | registry 工厂约定 `(config, **kwargs)`，但 `Strategy` 构造需注入 `optimizer`/阈值 等依赖 | 若不统一约定，注册后无法实例化 | E6 |
| **G4** | 模板输出权重未归一/未约束（行和 ≤1、非负） | `set_signal` 会 fail-fast；权重设计须在模板内闭合 | E5 |
| **G5** | 引擎层已有 vol-target（P-051a）；模板层再做组合波动目标 → **双层缩放** | 与 P-051a F-R5 同类问题（乘积杠杆），需明确职责边界 | E10 / P-051a DESIGN |
| **G6** | 策略层若用 `estimate_volatility`（窗口含当日）判入场 | **前视风险**（当日收益已知） | O-P051a-3 |
| **G7** | 无任何策略模板测试/golden 基线 | 需新建测试面；不得改既有 golden | 基线读数 |
| **G8** | U-P044-3（`StrategyEngine` 内部重构）触发条件已满足（策略模板库出现），但范围未定 | 范围过大会拖垮批次 | PROGRESS §3.58 |

---

## 4. 方案矩阵（Step 3 裁决对象）

### 4.1 G1：历史数据如何进入策略

| 方案 | 做法 | 优点 | 缺点 | 判定 |
|------|------|------|------|------|
| **A1 扩展 `MarketView`** | 增可选字段 `history: Optional[dict[str, pd.DataFrame]]`（`close/high/low/volume` 截至 **t−1**） | 真相单一、可重放、可测；additive 默认 `None` 零破坏 | 需改 P-044 契约（向后兼容） | **推荐** |
| A2 策略内部累积 | 每次调用把当日价 append 到 deque，存 `state.extras` | 零契约变更 | 中途加载无法重放；`state` 语义被污染；易混入当日值 | 备选 |
| A3 注入 fetcher 回调 | 构造时传 `Callable[[date], DataFrame]` | 灵活 | 破坏可测性/可序列化；模板难做纯函数测试 | 否 |
| A4 仅用 `returns` 窗口 | 用累计收益代理价格 | 零改动 | **拿不到 high/low/volume**，网格/突破不可实现 | 否（仅时序动量可用） |

> **A1 关键约束**：`history` 必须**截断到 t−1**（`views_from_data` 内显式切片），与 E4 的 `returns_window` 同源同窗；`history is None` 时模板须 fail-fast（`ValueError`）而非静默降级。

### 4.2 G5：vol-target 职责归属

| 方案 | 判定 |
|------|------|
| 引擎层（`config.sizing.method="vol_target"`）+ 模板不出波动目标 | **推荐**：单一缩放点，复用 P-051a 已验收链路 |
| 模板层自带目标波动 | 否：与引擎层叠乘，重复 P-051a F-R5 问题 |
| 模板层 ATR 仓位（`atr_k` 风险单位） | 可选：属**风险单位**而非组合波动目标，与引擎 vol-target 不冲突（Step 3 定默认关闭） |

### 4.3 G8：U-P044-3 范围

| 方案 | 判定 |
|------|------|
| 本批最小化：只新增 `strategies/` + 复用 `BacktestAdapter`/`set_signal` | **推荐**：P-051b 是「模板可用」，引擎内多策略循环由 P-051c 的虚拟子账户需求驱动 |
| 本批顺带重构 `StrategyEngine` | 否：无消费方（P-051c 未立项），过早抽象 |

**机械判据**：若 P-051c 的需求里出现「同一账户 N 个策略并行」→ 引擎内循环；仅「单策略回测/实盘」→ `BacktestAdapter` 足够。

---

## 5. 四模板规格草案

| 模板 | 参数（schema 草案） | 入场 | 出场 | 依赖输入 |
|------|---------------------|------|------|----------|
| `grid_atr` | `grid_k`(ATR 间距倍数, 默认 1.0) / `levels`(档数) / `atr_period`(14) | 价格相对基准网格下穿一档 → 加一档权重 | 上穿对应档 → 减一档；`stop_loss_pct` 兜底 | `high/low/close` 历史窗 |
| `trend_breakout` | `entry_n`(20) / `exit_n`(10) / `ma_n`(60) / `atr_period`(14) | `close > max(high[t-entry_n:t])` 且 `close > MA(ma_n)` | `close < min(low[t-exit_n:t])` | `high/low/close` |
| `ts_momentum` | `lookbacks`(20,60,120) / `min_votes`(2) | 多周期收益符号多数为正 → 等权持有 | 多数转负 | `close` 历史窗（或 `returns` 窗口） |
| `mean_reversion` | `z_entry`(2.0) / `z_exit`(0.5) / `lookback`(20) / `max_hold_days`(10) | `z <= -z_entry`（超跌） | `z >= -z_exit` 或持仓达 `max_hold_days` | `close` 历史窗 |

**共同约束**：输出 `pd.Series`（index=标的，非负）；选中标的等权（`1/n_selected`，`n` 为当日入选数）；行和 ≤1；不产出空头；不使用 ≥t 的数据（`history` 已截断 + 模板内禁止 `iloc[-1]` 直接取当日）。

> **DESIGN 订正（R-2 / R-3，见 [DESIGN_p051b §0.1](DESIGN_p051b_strategy_library.md)）**：`trend_breakout` **删除** `atr_period`（算法不用，避免死参数违反 I4）；`mean_reversion.max_hold_days` 与 `grid_atr.stop_loss_pct` **移出模板参数**，改由 `core.stops.apply_stops`（P-045）在矩阵层承担，避免双层止损叠加（同 P-051a F-R5）。

---

## 6. 不变式（草案）

| ID | 不变式 |
|----|--------|
| I1 | 模板输出：非负、行和 ≤1、index ⊆ `dm.stock_codes`（`set_signal` 不抛错） |
| I2 | 无前视：`generate_signals` 仅消费 `history`（≤t−1）/`returns`（≤t−1）/`signal`（当日，若显式允许） |
| I3 | 纯函数性：同一 `(view, state)` 两次调用结果逐值相同（时间/随机/全局态零依赖） |
| I4 | `meta`：`strategy_id` 唯一、`version` 语义化、`param_schema` 与构造参数一一对应、`code_hash` 非空 |
| I5 | 注册幂等：同 id 重复注册 → warning + 覆写（沿用 E6 语义），不抛错 |
| I6 | 未注册模板不得被 `get_strategy_registry().get(name)` 取到（无隐式自动发现之外的路径） |
| I7 | 与引擎组合：`signals_frame` → `set_signal` → 回测全链路不抛异常；`sizing=None` 时行为与只给同一权重矩阵完全一致 |
| I8 | 不新增 golden；既有 22 条零重录 |
| I9 | 模板层不做组合 vol-target（G5 裁决），不调用 `apply_sizing` |
| I10 | `history=None` 且模板需要历史 → `ValueError`（fail-fast，不静默返回空权重） |

---

## 7. DoD 与读数目标（待 Step 3 定稿）

- **代码**：`strategies/__init__.py`（集中 import 触发注册）、`strategies/grid.py`、`trend.py`、`momentum.py`、`mean_reversion.py`、`strategies/base.py`（公共工具：权重归一、`history` 校验）；
- **契约变更（若采 A1）**：`core/strategy.py` `MarketView` +`history` 可选字段；`views_from_data` +`history_window` 参数（默认 0 关闭，零行为变更）；
- **测试**：预计 +30~40（每模板 6-8：闭式入场/出场/无前视/参数校验/注册/端到端），目标 pytest **1040 → ~1075**（Step 3 定死）；
- **门禁**：golden **22 零重录** / mypy **113**（新增文件后为 113+N） / black 全绿 / `core/sizing.py`、`core/engine_v2.py` 尽量零 diff（若改 `MarketView` 则限 `core/strategy.py`）。

---

## 8. 未决项（Step 2 复审 → Step 3 裁决）

| ID | 未决 | 备选 | 推荐 |
|----|------|------|------|
| **U-P051b-1** | 历史数据注入（G1） | A1 扩 `MarketView` / A2 内部累积 / A4 仅 returns | **A1** |
| **U-P051b-2** | 模板范围 | 4 类 / 5 类（含月差套利） | **4 类**（月差需期货数据，另立批次） |
| **U-P051b-3** | 权重归一 | 等权 `1/n` / 按信号强度加权 / 外部 optimizer | **等权**（简单可验证；强度加权归 P-046/optimizer） |
| **U-P051b-4** | registry 工厂约定（G3） | `(config: dict) -> Strategy` / `(**params) -> Strategy` | **`(config: Mapping[str, Any] \| None = None, **overrides)`**，与既有工厂约定兼容 |
| **U-P051b-5** | U-P044-3 范围（G8） | 本批最小化 / 顺带重构 | **最小化**，引擎内循环归 P-051c |
| **U-P051b-6** | 网格模板基准价 | 首日收盘 / 滚动均值 / ATR 带中心 | ~~首建仓日收盘~~ → **DESIGN R-1 终版**：`base_price` **必填**（缺省/空 → `StrategyConfigError`）。`BacktestAdapter` 无 extras 回写通道 → 原方案不可实现；缺省滚动锚被 Step 4 F-D2 否决（恰为原裁决要避免的语义） |
| **U-P051b-7** | 本批是否预留「生成器可注入」的最小钩子（见 §11） | 完全不预留 / 仅冻结参数 schema 与工厂签名 / 预留 `generator` 字段 | **已裁决（2026-11-21 用户）：仅冻结 schema + 工厂签名**（零代码，靠契约约束；生成功能另立批次） |
| **U-P051b-8** | trial 登记（`n_trials`）归属 | 本批 / P-051c / 独立批次 | **独立批次**（`core/validation.py` L17 现自报 `MULTIPLE_TESTING_SUPPORTED=False`，本批改不动） |
| **U-P051b-9** | `agents/` 新增生成层时的命名 | 复用 `StrategyEngine` / 新建 `StrategyGenerator` | **新建**（`agents.multi_strategy_engine.StrategyEngine` 已占用该名，且与 U-P044-3 同名冲突） |
| **U-P051b-10** | 评估协议声明是否写入本批 DESIGN（§13） | 不写 / 写「声明式四问」/ 写并实现 `n_trials` | **写「声明式四问」**（纯文档零代码：试验数 N / 是否预注册 / 是否报告全部候选 / 是否做多重检验校正） |
| **U-P051b-11** | 选择偏差机制（§14 M1-M8）的落地批次 | 本批 / P-051c / 独立批次 | **独立批次**（需 ledger + 负对照，属「生成」而非「模板」范围） |
| **U-P051b-12** | Fin_Agent Guru JSON 的接入归属（§15） | P-051b / `agents/` 独立批次 / P-051c | **`agents/` 独立批次**（A 路径零代码，需契约测试；与模板库无关） |
| **U-P051b-13** | 研报/KOL → 策略（§15 C 路径）是否立项 | 不立项 / 仅事件因子 / 全文本因子 | **仅事件因子**（评级变动/目标价调整可 PIT、可复现） |
| **U-P051b-14** | 预测市场赔率是否纳入事件表（§16） | 不纳入 / 仅作展示 / 作 `P(event)` 外生输入 | **仅作外生输入**（PIT 快照 + 域内校准 + 不用于筛选策略） |

---

## 9. 步骤表

| Step | 动作 | 出口 |
|------|------|------|
| 2 | RULE-5 异构独立复审（排除建议幻觉；重点 A1 契约变更是否破坏 P-044 既有用例） | **0 P1 已达成**（2026-11-21，复审方 GLM-5.3-Flash，报告见 [REVIEW_p051b_step2_research.md](REVIEW_p051b_step2_research.md)；4 条 P3 备注移交 Step 3） |
| 3 | DESIGN：定 U-P051b-1..6 + `MarketView.history` 精确语义 + 四模板闭式 + 测试规格 | **DESIGN 已落盘**（2026-11-21，见 [DESIGN_p051b_strategy_library.md](DESIGN_p051b_strategy_library.md)；含 R-1..R-3 对本文订正，R-4 已撤销；4b 复验已通过） |
| 4 | 异构复审（重点：前视、归一、注册、回归） | **0 P1 已达成**（2026-11-21：首轮 2 P1 → 按修复 b/c 收敛 → 4b 复验 5 项全过；P3-4b-1 已当场修复）。报告见 [REVIEW_p051b_step4_design.md](REVIEW_p051b_step4_design.md)，收敛表见 [DESIGN §0.3](DESIGN_p051b_strategy_library.md) |
| 5 | IMPL：逐处代码 + 测试规格 | **IMPL 已落盘**（2026-11-21，见 [IMPL_p051b_strategy_library.md](IMPL_p051b_strategy_library.md)：9 文件变更 / 6 新文件全文 / C-1..C-3 语义澄清 / 45 条用例；Step 6 已通过） |
| 6 | 异构复审 | **0 P1 已达成**（2026-11-21：首轮 3 P1 → 按 3 P1 + 3 P2 + 6 P3 收敛 → 6b 复验 5 项全过）。报告见 [REVIEW_p051b_step6_impl.md](REVIEW_p051b_step6_impl.md)，收敛表见 [IMPL §9](IMPL_p051b_strategy_library.md) |
| 7 | CHECKLIST（A/B/C/I 四组） | **已落盘并执行完毕**（2026-11-21，见 [CHECKLIST_p051b_strategy_library.md](CHECKLIST_p051b_strategy_library.md)：A10 + B7 + C5 + I12 = 34 项全 ✅；实测 pytest **1091** / golden **22 零重录** / mypy **119** / black **240** / tests **120**；见其 §7 实测与偏差记录） |
| 8 | 一致性检查（四文档 ↔ 锚点 ↔ 读数） | **通过（2026-11-21，复审方 GLM-5.3-Flash）**：①计数链 45/+48/1088 与 22/119/170 四文档全一致（Step 9 实测订正为 **1091 / 240**，差额已解释）；②参数默认值、注册顺序、`iloc[-lb]`、U 编号链跨文档一致；③代码锚点实测相符（`MarketView` L111-119 / registry `get` L101-103 / `set_signal` L614）；④修正 2 处过时表述 |
| 9 | TDD 实施 + 门禁 | **通过（2026-11-21）**：`core/strategy.py` 两处 additive 后先跑 1040 零退化闸门 ✅；新建 `strategies/` 6 文件 + 7 个测试文件；门禁 pytest **1091 passed** / golden **22 passed**（零重录）/ mypy **119 files 0 error** / black **240 unchanged** / A10 零 diff / golden 目录无新增。实施中修复 6 项 IMPL 转录缺陷（S9-1..S9-6，见 CHECKLIST §7） |
| 10 | PROGRESS 回填 + 用户授权提交 + CI | 四 job 全绿 |

---

## 10. 结论

P-051b 的技术底座（Protocol / 适配器 / 引擎 weights 通道 / registry / 波动原语）**已全部就绪**，唯一硬缺口是 **G1：`MarketView` 无时序历史**——它决定网格与趋势模板能否实现，也是本批唯一的跨批次契约变更点。建议采 **A1（可选 `history` 字段，默认 `None` 零破坏）**，并把「引擎内多策略循环（U-P044-3 的完整形态）」明确留给 P-051c。模板层**一律不做组合 vol-target**，避免与 P-051a 已接线的 sizing 形成双层缩放。

---

## 11. 补充分析：`agents/` 能否增加「策略生成」并与模板库接线

> 本节回答一个独立于 P-051b 交付范围的问题：**agent 模块加策略生成能力，可行性 / 接线形态 / 成本 / 收益 / 风险**。结论先给，证据后置；**学术与社区条目见 §11.6，均标注本轮核实方式**。

### 11.0 结论先行

| 判断 | 内容 |
|------|------|
| **能不能做** | 能。四个接缝（工厂 / 权重 / 分配 / 参数搜索）都已存在，缺的**不是 LLM，而是候选表达 + trial 登记** |
| **本批做不做** | **不做**。P-051b 只交付模板库；但它恰好是生成能力的**必要前置**（生成必须有受限的落点） |
| **先做什么** | 分级 **L0（参数生成）** 优先于 **L1（受限 DSL）**；**L2（自由代码）/L3（全闭环）建议不立项**，除非 §11.5 的四项门禁先落地 |
| **硬前置** | trial 登记 + DSR/PBO 门禁。当前 [validation.py L17](file:///f:/Coding/Factor_Trading_v3.0/core/validation.py#L16-L27) **自报** `MULTIPLE_TESTING_SUPPORTED = False`，并明写「未做多重检验校正（无 trials 登记）」——生成式搜索会直接放大这个已知缺口 |
| **命名红线** | 不得再引入第三个 `StrategyEngine`（`agents.multi_strategy_engine.StrategyEngine` 已占用，且与 U-P044-3 同名） |

### 11.1 现状盘点（本轮实读，E12-E20）

| # | 锚点 | 事实 |
|---|------|------|
| E12 | `agents/` 15 文件 / **11,102 行** | 已有**参数搜索层**：[auto_parameter_optimizer.py L51](file:///f:/Coding/Factor_Trading_v3.0/agents/auto_parameter_optimizer.py#L41-L60) `WalkForwardConfig`（`gap_days=20` purge）、L255 `PBTParameterOptimizer`、L575 `OverfittingMonitor`（IS/OOS 比、参数稳定性） |
| E13 | [strategy_allocator.py L745](file:///f:/Coding/Factor_Trading_v3.0/agents/strategy_allocator.py#L745-L805) | `StrategyAllocationManager`：5 种分配器（Hedge/FTRL/UCB/Thompson/MV）+ `MetaPolicy`；**消费的是策略收益序列**（L806 `update(strategy_returns)`），不消费策略定义 |
| E14 | [sentiment_framework.py L303-416](file:///f:/Coding/Factor_Trading_v3.0/agents/sentiment_framework.py#L303-L416) | **全仓唯一的 LLM 触点**，且为占位：`use_llm = False`（L308）、`analyze_with_llm` 全注释（L409-415），实际回落规则词典 |
| E15 | [pyproject.toml L28-L71](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L28-L71) | `dependencies` 与 `optional-dependencies` **均无** openai / anthropic / langchain / transformers |
| E16 | [multi_strategy_engine.py L67 / L560](file:///f:/Coding/Factor_Trading_v3.0/agents/multi_strategy_engine.py#L67-L90) | `StrategyEngine` 是**单策略回测引擎**（吃 `composite_signal: pd.DataFrame`）；`MultiStrategyEngine` 固定 long/short/neutral 三方向，**不接受外部策略对象** |
| E17 | [agent_framework.py L1162-1241](file:///f:/Coding/Factor_Trading_v3.0/agents/agent_framework.py#L1162-L1241) | `MultiAgentBacktestEngine`：agent → `prepare_factors(dm)` → `agent_signals` DataFrame → `SignalAggregator` → 回测。**这是本仓已存在的「agent 产出 → 回测」骨架**，但产物是因子分而非策略对象 |
| E18 | [validation.py L16-L27](file:///f:/Coding/Factor_Trading_v3.0/core/validation.py#L16-L27) | `PIT_SUPPORTED=False` / `MULTIPLE_TESTING_SUPPORTED=False` / `BENCHMARK_SUPPORTED=False`；`KNOWN_LIMITATIONS` 首条即「未做多重检验校正（无 trials 登记）」 |
| E19 | [research_team_v2.py L526-L575](file:///f:/Coding/Factor_Trading_v3.0/agents/research_team_v2.py#L526-L575) | `QuantResearcher` 输出 `ResearchView`（方向 + 置信度 + 说明），**不是权重、不是代码、不可回测** |
| E20 | [walk_forward.py L1-L14](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L1-L14) | 已实现 rolling/expanding 分割 + purge gap；全仓 grep `deflated|dsr|pbo|combinatorial|CSCV` **零实现符号**（仅 `auto_parameter_optimizer.py` L14/L57 两处注释提到「组合对称性检验」，无对应函数） |

**推论**：本仓「生成」链条的实际缺口是三项，LLM 只影响第一项的选择：
1. **候选表达**——模板参数 schema（P-051b 补）或受限 DSL（未建）；
2. **trial 登记**——无（E18/E20）；
3. **生成物 → `Strategy` Protocol 的适配器**——无，但因 Protocol 极窄（`meta` + `generate_signals`），成本很低。

### 11.2 四个接缝与分级方案

**接缝**（全部为既有接口，本轮无需改核心）：

| 接缝 | 接口 | 生成的产物形态 |
|------|------|----------------|
| **S1 工厂** | `get_strategy_registry().create(name, config)`（[registry.py L225-230](file:///f:/Coding/Factor_Trading_v3.0/core/registry.py#L225-L230) / L341-359） | 参数 dict → `Strategy` 实例 |
| **S2 权重** | `engine.set_signal(mode="weights")`（[engine_v2.py L614-656](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L614-L656)） | 权重矩阵（可绕过 Protocol） |
| **S3 分配** | `StrategyAllocationManager.update(strategy_returns)`（E13） | 多候选 → 资金权重（**不做晋级/退役**，那是 P-051c） |
| **S4 参数搜索** | `WalkForwardValidator` / `PBTParameterOptimizer` / `OverfittingMonitor`（E12） | 已有、且**不依赖 LLM** |

**分级**（按「生成物可信度」排序，不是按效果排序）：

| 级 | 生成物 | 需要新建 | 与模板库的关系 |
|----|--------|----------|----------------|
| **L0 参数生成** | 模板参数 JSON（如 `{"entry_n":25,"ma_n":60}`） | schema 校验器 + 生成器 + trial 计数（~250-350 行） | **直接复用 S1**：模板库就是生成空间。P-051b 的 `param_schema` 是 L0 的硬前置 |
| **L1 受限 DSL** | 入场/出场布尔表达式 | lexer/parser/AST 白名单/求值器（~700-1000 行） | 求值器**只吃** `MarketView.history`（截断 t−1）→ 前视在结构上不可表达 |
| **L2 自由代码** | Python `Strategy` 源码 | 进程沙箱（无网/只读 FS/超时/内存）+ AST 审查 + CI 隔离 | 生成代码成为不可重放输入，**破坏本仓「纯函数 + golden」原则** |
| **L3 全闭环** | N 个候选 + 自动淘汰 | trial ledger + DSR + PBO/CSCV（~700-900 行，E20 现为零） | 可复用 S3 做资金分配，但**晋级门仍属 P-051c** |

L0 接线示意（不改核心，只在 `strategies/` 之上加一层）：

```python
# 生成 → 校验 → 走既有工厂；模板 id 不变，只有参数变
raw = generator.propose(template_id="trend_breakout", n_candidates=16)   # list[dict]
params = validate_against_schema("trend_breakout", raw)                  # 拒绝未知键/越界
strategy = get_strategy_registry().create("trend_breakout", params)      # S1
ledger.record(template_id=..., params=params, source="llm")              # trial 计数
```

L1 的关键不在于「能不能解析」，而在于**求值器的输入域**：若 `DslEvaluator.evaluate(window)` 的 `window` 参数类型上只能接受 `MarketView.history`，则前视在结构上不可表达——这与 [2608.27734](https://arxiv.org/abs/2608.27734) 的做法一致（"agent can only act through registry-validated tools whose feature space excludes look-ahead by construction"），该文同时给出一个反直觉结论：**统计校正不能替代结构约束**——一个故意前视的 oracle 拿到 Sharpe 35，仍能通过 DSR 与 PBO 检验。

### 11.3 成本（工程点口径，非日历工期）

基线：pytest **1040** / mypy **113** / black **157** / `tests/*.py` **112**（P-051a 关闭读数）。

| 级 | 新增代码 | 新增测试 | 新依赖 | 对门禁的影响 | 主要工程难点 |
|----|----------|----------|--------|--------------|--------------|
| L0 | ~250-350 行（`agents/strategy_generator.py` 或 `strategies/generator.py`） | ~12-15 | **0**（HTTP/注入式 client，不引 SDK） | mypy +1~2 文件；不触 `core/` | 生成确定性（需固定 seed/温度 0 + 响应缓存）；重复候选去重 |
| L1 | ~700-1000 行（`strategies/dsl/`） | ~35-45 | 0（手写 parser 或 Python `ast` 子集） | mypy +3~5 文件 | AST 逃逸面（属性访问/`shift(-n)`/闭包）；求值性能（逐日 × 逐标的） |
| L2 | ~400-600 行沙箱 + CI 改造 | ~40（含逃逸/超时/OOM 用例） | **1**（沙箱运行时 / Docker；Windows 主环境需 Job Object 或 WSL） | 新增独立 CI job；与本仓现有信任模型冲突 | 目标机器是 Windows → 跨平台沙箱成本显著 |
| L3 | ~700-900 行（ledger + DSR + PBO/CSCV） | ~30-40（统计量需闭式/仿真双验证） | 0（scipy 已在 L31） | 需改 `MULTIPLE_TESTING_SUPPORTED`（E18）→ 牵连报告与 golden | DSR 的「有效独立试验数」估计；CSCV 的 S 分块与计算量 |

**共同前置成本**（无论哪级都要付）：`core/validation.py` 的 `multiple_testing.n_trials` 目前恒为 `None`（L51），生成式搜索一旦启用，所有报告都会**自报未校正**——这条不是代码问题，是口径问题，须先有 ledger 才能改常量。

### 11.4 收益

| 收益 | 说明 | 强度 |
|------|------|------|
| **搜索空间从「网格」变「语义」** | 现有 `run_param_grid` 只能枚举预定义轴；L0 可在同一 schema 内提出非均匀组合（如「高波动 regime 用更宽的 `entry_n`」） | 中 |
| **与既有反馈层天然衔接** | 候选 → 回测 → 收益序列 → `StrategyAllocationManager`（S3）→ 权重，**闭环后半段已存在**，不需要 P-051c 就能做离线实验 | 强 |
| **可审计性优于自由代码** | L0/L1 的产物是参数与表达式，可 diff、可版本化、可写进 manifest；L2 的源码产物不具备这一性质 | 强 |
| **与「策略模板库」互补而非替代** | 模板定义**结构**，生成定义**参数/组合**；没有模板，生成器只能生成自由代码（即 L2） | 强 |
| 收益不包含「替代研究员」 | §11.6 三条负向证据（2608.27734 / 2605.16895 / 2510.07920）均指向：LLM 发现的策略在样本外与知识截止后显著衰减 | — |

### 11.5 风险（按证据强度排序）

| # | 风险 | 证据 | 强度 | 缓解 |
|---|------|------|------|------|
| R1 | **搜索强度未校正**（生成 N 个候选只报最好） | 本仓 E18 自报无 trial 登记；[2608.27734](https://arxiv.org/abs/2608.27734) 显示该缺陷是 LLM 策略发现文献的通病 | **强（本地+文献双证）** | 先做 trial ledger + DSR；DSR 参数里的试验数必须来自 ledger 而非事后估计 |
| R2 | **前视 / 知识泄漏** | [2510.07920](https://arxiv.org/abs/2510.07920)（Profit Mirage：LLM 代理在训练截止后收益蒸发，趋势题 90.23% 准确率来自记忆）；[2602.14233](https://arxiv.org/abs/2602.14233)（164 篇综述：仅 26.8% 论文承认前视偏差，生存偏差 1.2%） | **强（多源一致）** | 结构约束优先（L1 求值器只吃 t−1 窗口）；LLM 不得接触价格数值，只接触 schema |
| R3 | **样本外衰减 / alpha 衰减** | [2502.16789](https://arxiv.org/abs/2502.16789) AlphaAgent 用 AST 去重 + 复杂度上限对抗衰减；[2605.16895](https://arxiv.org/abs/2605.16895) 主张 LLM 交易代理报告的 alpha 不应作为部署证据（六项最小证据协议） | **中-强** | 候选相似度去重（AST/参数距离）、复杂度上限、walk-forward 而非单段回测 |
| R4 | **代码执行安全**（仅 L2） | 本仓无沙箱基建；Windows 主环境 | **强（工程事实）** | 不做 L2；若要做，先补 OCI/Job Object 沙箱与独立 CI |
| R5 | **LLM 非确定性 → 不可复现** | 生成物不可重放，与本仓「纯函数 + golden + manifest」原则冲突 | **强（原则冲突）** | 落盘生成物（参数/表达式 + prompt + 模型版本 + 采样参数）；回测只吃落盘物 |
| R6 | **合规** | A 股程序化交易对策略来源无量化要求，但「自动生成并自动下单」属高风险链路 | **弱-中（未核实监管细则）** | 生成物一律**离线**，人审后才能进 registry；不与实盘直连 |
| R7 | **重复造轮子** | E12 已有 PBT + walk-forward + IS/OOS 监控 | **强（本地）** | 生成层只做「候选提出」，搜索/评估复用 E12，不新建优化器 |

### 11.6 学术与社区证据表

> **核实方式**：本轮（2026-11-21）以标题+摘要检索命中为准，**未逐篇精读全文**；标「仅摘要片段」者只见到检索摘要。社区星数为第三方站点读数，非实时。

| 类型 | 条目 | 与本议题的关系 |
|------|------|----------------|
| 正向 | **RD-Agent(Q)**，arXiv [2505.15155](https://arxiv.org/abs/2505.15155)（微软） | 最接近的完整形态：Research（假设生成）→ Development（代码实现）→ 回测反馈，bandit 调度器在固定算力下迭代。社区仓库 `microsoft/RD-Agent`（Qlib 底座），第三方 star 追踪读数 ~15.4k（2026-11 附近） |
| 正向 | **Alpha-GPT**，arXiv [2308.00016](https://arxiv.org/abs/2308.00016) | 「人机交互 alpha 挖掘」：人给想法 → LLM 译成公式化 alpha → 遗传规划增强 + 回测。对应本仓的 **L1** 形态 |
| 正向 | **AlphaAgent**，arXiv [2502.16789](https://arxiv.org/abs/2502.16789)（ACM DL 10.1145/3711896.3736838） | AST 相似度去重（原创性约束）+ 假设-因子语义对齐 + AST 结构复杂度上限，直接对应 R3 的缓解手段 |
| 中性 | **QuantAgent**（arXiv 2402.03755） | 检索到标题级信息，本轮未取得摘要，**不做结论引用** |
| 中性 | **TradingAgents**，arXiv [2412.20138](https://arxiv.org/abs/2412.20138) | 多角色（基本面/情绪/技术/多空研究员/风控）辩论式决策。**是决策框架，不是策略生成**；与本仓 `agents/research_team_v2.py` 定位同源 |
| **负向** | **What survives honest evaluation?**，arXiv [2608.27734](https://arxiv.org/abs/2608.27734) | ①特征空间在结构上排除前视，且**该约束不可被统计校正替代**（故意前视 oracle SR=35 仍通过 DSR + PBO）；②记录每次搜索评估并按 trial 数对全部报告做 deflate。→ 本仓若做 L3，这两条是硬要求 |
| **负向** | **The Alpha Illusion**，arXiv [2605.16895](https://arxiv.org/abs/2605.16895) | 立场文：端到端 LLM 交易代理报告的 alpha **不应**作为部署证据；提出时间完整性/交易摩擦/反事实稳健/预测校准/数值执行/多代理拆解六项协议 |
| **负向** | **Profit Mirage**，arXiv [2510.07920](https://arxiv.org/abs/2510.07920) | 「利润海市蜃楼」：模型知识窗口结束后的收益蒸发；提出 FinLake-Bench 与 FactFin 反事实框架 |
| **负向** | **Evaluating LLMs in Finance Requires Explicit Bias Consideration**，arXiv [2602.14233](https://arxiv.org/abs/2602.14233) | 164 篇（2023-2025）综述，归纳「五宗罪」：前视/生存/叙事/目标/成本；单项偏差的处理率最高不过 28% |
| 方法 | Deflated Sharpe Ratio — Bailey & López de Prado, *JPM* 40(5), 2014 | 多重检验 + 非正态下的 Sharpe 校正；本仓缺口 E18 |
| 方法 | Probability of Backtest Overfitting (CSCV) — Bailey, Borwein, López de Prado, Zhu, *J. Computational Finance* 20(4), 2017（DOI 10.21314/JCF.2016.322） | 过拟合概率估计；本仓仅有 docstring 提及、无实现（E20） |
| 方法 | Purged K-Fold / CPCV — López de Prado, *Advances in Financial Machine Learning*, 2018, Ch.7 | 本仓已部分实现（E12/E20：walk-forward + purge gap），CPCV 未实现 |
| 社区 | `microsoft/RD-Agent` | 活跃，Qlib 底座，与本仓架构（engine + registry + 回测）最接近的可借鉴对象 |
| 社区 | `virattt/ai-hedge-fund`、`AI4Finance/FinRL` | 均为教学/研究定位；**本轮未核实细节，不作论据** |

### 11.7 建议路线与门槛

1. **P-051b 只做模板库**，但同时**冻结两样契约**（U-P051b-7）：`param_schema` 字段集 + 工厂签名 `(config, **overrides)`。这两样就是未来 L0 的全部前置，零额外代码。
2. **L0 单独立项**（建议编号 P-05x），验收门槛：
   - 生成物 100% 落盘（参数 + prompt + 模型 + 采样参数），回测只吃落盘物；
   - trial ledger 先行——`n_trials` 从 ledger 取，且能答「本次报告背后搜了多少次」；
   - 生成层不接触价格序列，只接触 schema；
   - 复用 E12 的 walk-forward 与 IS/OOS 监控，不新建优化器。
3. **L1 在 L0 之后**，验收门槛：求值器签名只接受 `MarketView.history`（类型层面杜绝前视）+ AST 白名单 + 参数距离去重。
4. **L2/L3 不立项**，除非 R1 与 R4 同时具备：trial ledger + DSR/PBO 已实现（改 `MULTIPLE_TESTING_SUPPORTED`），且沙箱与独立 CI 就绪。
5. **命名**：新增层用 `StrategyGenerator`，不复用 `StrategyEngine`（U-P051b-9）。

### 11.8 本节新增未决项

见 §8 **U-P051b-7 / U-P051b-8 / U-P051b-9**（已并入 Step 2 复审议程）。三者的共同推荐均为「本批零代码、只冻结契约」，使 P-051b 的交付范围不变。

### 11.9 用户裁决（2026-11-21）：范围确认

| 项 | 裁决 |
|----|------|
| 分析归档位置 | 本文 §11（与 P-051b 同文档，Step 2 复审可连带核查；不另建独立文档，避免双份真相） |
| P-051b 交付范围 | **只做模板库**：`strategies/` 4 类模板 + `@register_strategy` + `BacktestAdapter`/`set_signal` 端到端；**不含**任何生成、DSL、沙箱、trial ledger |
| 「保留扩展能力」的落地方式 | **零代码，只冻结契约**：①`param_schema` 字段集在 DESIGN 定稿并写入 `meta.param_schema`；②工厂签名统一 `(config: Mapping[str, Any] \| None = None, **overrides)`；③四接缝 S1/S2/S3/S4 在 DESIGN §外部锚点 登记，供后续批次引用 |
| 明确不做 | L0 生成器 / L1 受限 DSL / L2 代码沙箱 / L3 闭环 / 修改 `MULTIPLE_TESTING_SUPPORTED` |

**「扩展能力保留」的机械判据**（供 Step 8 一致性检查）：对任一模板，手工把参数 dict 换成另一个**合法** dict 后，`get_strategy_registry().create(name, dict)` 能直接产出可用实例并跑通 `BacktestAdapter` → 说明 L0 前置成立，无需改任何代码。

---

## 12. 八项缺口的外部锚点补充调研（G1-G8）

> **目的**：为 Step 3 设计提供可复核的外部依据，避免「凭直觉定契约」。
> **核实口径**（检索时点 2026-11-21）：`官方已核` = 读到官方页面/PDF 正文；`摘要级` = 仅检索摘要或第三方转述；`未取得` = 未找到可靠来源，不作论据。
> **原则**：锚点只用于**支持或反驳已有建议**，不引入新范围。

### 12.1 G1：策略如何拿到时序历史

| 来源 | 精确锚点 | 要点 | 核实 |
|------|----------|------|------|
| zipline-reloaded | `data.history(asset, 'price', bar_count=100, frequency='1d')` | 窗口由**引擎**按当前 bar 向前截取，策略不自己累积 | 官方已核 |
| QuantConnect LEAN | `History(symbol, 253, Resolution.DAILY)`（trailing data samples） | 以「最近 N 根 bar」而非日期区间取数，返回只含已发生样本 | 官方已核 |
| backtrader | `self.data.close[0]` / `self.data.close[-1]` | `0` = 当前 bar，`-1` = 上一 bar；**正向索引不存在**，未来取不到 | 官方已核 |

**→ 对本轮实现的约束**：三家一致把窗口责任放在**引擎/数据层**。这直接支持 §4.1 的 **A1**、否决 A2（策略内部累积 deque）：A2 等于让策略自己当引擎，既无法从中途加载重放，也把「截断到 t−1」的正确性责任从一处变成 N 处。`history=None` 时 fail-fast（I10）与 backtrader「越界即异常」的语义同源。

### 12.2 G2：引擎是否应直接消费策略对象

| 来源 | 精确锚点 | 要点 | 核实 |
|------|----------|------|------|
| Qlib | `qlib.backtest.backtest(executor=..., strategy=...)`，策略实现 `generate_trade_decision` | 引擎持有策略对象，逐 bar 调用；无需外部物化权重矩阵 | 官方已核 |
| backtrader | `cerebro.addstrategy(MyStrategy, **params)` | 策略实例注册进主循环，构造参数随注册注入 | 官方已核 |
| LEAN | Algorithm Framework：`add_alpha(...)` + `set_portfolio_construction(...)` | 框架直接持有并串联 Alpha/组合/风控/执行四类模型对象 | 官方已核 |

**→ 对本轮实现的约束**：G2 是**真实缺口**（主流框架都是「引擎持有策略」），但不构成本批阻塞——我们已有 `BacktestAdapter` 这一外部驱动路径，且当前**没有消费方**（P-051c 未立项）。故 G2 在本批只登记为 P-051c 的设计锚点，不触发重构（与 §4.3 一致）。

### 12.3 G3：工厂签名与实例化约定

| 来源 | 精确锚点 | 要点 | 核实 |
|------|----------|------|------|
| Qlib | `init_instance_by_config({"class":..., "module_path":..., "kwargs":{...}})` | **单 dict 入参**统一实例化，`kwargs` 即依赖注入位 | 官方已核 |
| Hydra / OmegaConf | `instantiate(cfg)` + `cfg._target_` | `_target_` 指定类，其余键为构造参数；可递归嵌套 | 官方已核 |
| Python 标准库 | `importlib.metadata.entry_points(**select_params)` | 按 group 发现插件，替代自建注册表 | 官方已核 |

**→ 对本轮实现的约束**：`(config: Mapping[str, Any] | None = None, **overrides)` 与 Hydra `instantiate` **同构**（单 config + 展开 kwargs），说明 U-P051b-4 的推荐不是自创约定。Qlib 的 `module_path` 另给一条提示：注册名 → 模块路径应是**显式数据**，而本仓 `register_strategy` 依赖 import 副作用（E7）——两者可共存（装饰器管同进程、entry points 管跨包发现），但**跨包发现本批不做**，仅在 §8 U-P051b-7 已冻结的工厂签名中留出兼容位。

### 12.4 G4：权重的语义边界

| 来源 | 精确锚点 | 要点 | 核实 |
|------|----------|------|------|
| vectorbt | `vbt.portfolio.enums.SizeType.TargetPercent` | 语义为「占**总价值**的目标比例」，内部折算为 TargetValue | 官方已核 |
| LEAN | `SetHoldings(symbol, weight)` | 权重是**未加杠杆**的比例；要加杠杆须显式设置，100% 权重在 2x 杠杆下只用一半保证金 | 官方已核 |
| Qlib | `WeightStrategyBase.generate_target_weight_position` | 输出为占总资产目标比例，**现金不计入权重** | 官方已核 |

**→ 对本轮实现的约束**：三家把「权重」统一定义为**占总资产比例、不含现金、未加杠杆**——即本仓 `set_signal` 的「非负 + 行和 ≤1」不是特例，而是行业主流口径（E5）。同时说明为何**不允许空头/负权**在本批是合理简化：LEAN/Qlib 的负权需额外的融资与保证金账目，本仓账目模型无此能力（与 P-051a B10 的发现一致）。等权 `1/n`（U-P051b-3）与 LEAN 等权目标语义一致。

### 12.5 G5：vol-target 的归属与「只缩放一次」

| 来源 | 精确锚点 | 要点 | 核实 |
|------|----------|------|------|
| 学术 | Moreira & Muir (2017), *Journal of Finance* 72(4), doi:10.1111/jofi.12513 | 波动率管理作用于所管理的**收益序列**本身，改变其风险暴露 | 摘要级 |
| 学术 | Harvey et al. (2018), *Journal of Portfolio Management* 45(1):14-33, doi:10.3905/jpm.2018.45.1.014 | 系统评估波动率目标化对收益分布的影响；缩放因子作用于一条收益序列 | PDF 已核 |

**→ 对本轮实现的约束**：缩放是**对一条收益序列做一次乘法**。若模板层与引擎层各做一次，两个缩放因子相乘，实际波动不再是任一层的 `σ_target`——这是 §4.2「引擎层单点」裁决的直接依据，也支撑 I9（模板层不调用 `apply_sizing`）。ATR 风险单位（`atr_k`）属**头寸风险预算**而非组合波动目标，两者不构成同一维度，可并存。

### 12.6 G6：波动率估计的前视面

| 来源 | 精确锚点 | 要点 | 核实 |
|------|----------|------|------|
| pandas | `rolling(window)` 窗口**右端闭合** | 官方定义窗口「由当前观测向前回看」，含当日 → 判入场须显式 `shift(1)` | 官方已核 |
| Qlib | 表达式 `Ref(feature, N)`：`N>0` 为 N 期前，**`N<0` 为未来数据** | 用「负号 = 未来」显式编码前视，策略只允许 `N≥0` | 摘要级 |
| zipline-reloaded | stream-based 逐 bar 推进设计 | `handle_data` 只见当前 bar + `history`，前视在架构层被排除 | 官方已核 |

**→ 对本轮实现的约束**：`estimate_volatility` 的窗口含当日（O-P051a-3）在**策略层不可直接消费**，否则 `rolling` 的右端闭合会变成系统性前视。落为三条硬规则：①模板只消费 `history`（已截断 t−1）；②若必须自算滚动量，入口一律 `shift(1)`；③模板层增加「禁止负数 shift / 禁止正向索引」的静态检查位（Step 3 定为注释级或 lint 级，不进 CI 脚本）。

### 12.7 G7：纯函数策略的测试范式

| 来源 | 精确锚点 | 要点 | 核实 |
|------|----------|------|------|
| Hypothesis | `hypothesis.extra.numpy.arrays(...)` | 对「任意窗口 → 权重」生成输入，断言不变量而非逐值 | 官方已核 |
| ApprovalTests | Golden Master / characterization test | 对结果取快照并确认未变，即本仓 `tests/golden/` 的做法 | 官方已核 |

**→ 对本轮实现的约束**：三层测试分工——①**闭式样例**（手工可算的入场/出场，沿用 P-051a B 组风格，禁录制）；②**属性断言**（非负 / 行和 ≤1 / `index ⊆ dm.stock_codes` / 同一 `(view, state)` 两次调用逐值相同），正好覆盖 I1-I3；③**既有 22 条 golden 零重录**（I8）。Hypothesis 属新增 dev 依赖，**本批不引入**，用 `pytest.mark.parametrize` 手写等价用例，避免为测试范式付出依赖成本。

### 12.8 G8：何时把策略对象下沉进引擎主循环

| 来源 | 精确锚点 | 要点 | 核实 |
|------|----------|------|------|
| Qlib | `BaseStrategy.generate_trade_decision` 与 executor 频率解耦 | 策略只产决策，调用频率由 executor 决定——分层是为了**频率解耦** | 官方已核 |
| LEAN | Algorithm Framework 文档「Framework vs Classic Design」 | 明确「简单算法用 Classic 写法」，分层只在模块需复用/隔离时才划算 | 官方已核 |
| 社区 | Martin Fowler, "Yagni"（2015-05-26） | 未来才需要的能力现在不建 | 官方已核 |

**→ 对本轮实现的约束**：LEAN 官方的「Classic vs Framework」正是本批的判据来源——**单一策略回测用 Classic（外部适配器）即可**。故 U-P044-3 维持 pending，触发条件写死为「同一账户 N 个策略并行且需共享现金/保证金」（P-051c），而不是「策略模板库出现」这一较弱信号。

### 12.9 汇总：锚点如何改变（或不改变）本批裁决

| 缺口 | 外部锚点结论 | 对本批裁决的影响 |
|------|--------------|------------------|
| G1 | 窗口责任在引擎（zipline/LEAN/backtrader 三家一致） | **强化 A1**，否决 A2 |
| G2 | 主流框架引擎持有策略，但我们无消费方 | **维持最小化**，登记为 P-051c 锚点 |
| G3 | `init_instance_by_config` / `_target_` 与本仓工厂同构 | **支持 U-P051b-4**，跨包发现不做 |
| G4 | 「权重 = 总资产比例、不含现金、不加杠杆」是主流口径 | **支撑 I1**，非负 + 行和 ≤1 合理 |
| G5 | 缩放是对一条收益序列的一次乘法 | **强化引擎层单点**（I9） |
| G6 | `rolling` 含当日 = 前视；Qlib 以负号编码未来 | **强化 I2**，并新增「禁负 shift」规则 |
| G7 | golden + 属性断言是成熟组合 | **支撑 I3/I8**，不引入 Hypothesis |
| G8 | LEAN「简单算法用 Classic」+ YAGNI | **强化 U-P051b-5**，P-051c 再下沉 |

### 12.10 引用清单（可复核）

- zipline-reloaded 教程（`data.history`、stream-based）：https://zipline.ml4trading.io/beginner-tutorial
- LEAN 历史数据（trailing samples）：https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/history-requests
- LEAN 仓位规模（`SetHoldings`）：https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/position-sizing
- LEAN Algorithm Framework（Classic vs Framework）：https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview
- backtrader 概念（`close[0]/[-1]`）：https://backtrader.com/docu/concepts/ ；Cerebro：https://backtrader.com/docu/cerebro/
- Qlib 策略与回测（`generate_trade_decision`、`WeightStrategyBase`）：https://qlib.readthedocs.io/en/stable/component/strategy.html
- Qlib 工作流（`init_instance_by_config`）：https://qlib.readthedocs.io/en/latest/component/workflow.html
- Qlib API（`Ref` 语义）：https://qlib.readthedocs.io/en/latest/reference/api.html
- vectorbt 枚举（`SizeType.TargetPercent`）：https://vectorbt.dev/api/portfolio/enums/
- pandas 窗口文档（右端闭合）：https://pandas.pydata.org/docs/user_guide/window.html
- Hydra instantiate / `_target_`：https://hydra.cc/docs/advanced/instantiate_objects/overview/
- Python `importlib.metadata.entry_points`：https://docs.python.org/3/library/importlib.metadata.html
- Hypothesis NumPy 策略：https://hypothesis.readthedocs.io/en/latest/numpy.html
- ApprovalTests（Golden Master）：https://approvaltests.com/
- Martin Fowler, Yagni：https://martinfowler.com/bliki/Yagni.html
- Moreira & Muir (2017)：https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.12513
- Harvey et al. (2018)：https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf

**未取得 / 不作论据**：zipline 日频「当日收盘可见」的官方明文（改用 stream-based 表述）；Moreira & Muir 全文（仅摘要级）；Qlib `Ref` 负号语义的独立条目页（仅摘要级）。

---

## 13. 补充调研：不接 LLM 时，统计学习 / 在线学习能否处理选择偏差与前视

> **问题**：若模板库暂不接 LLM，改用统计学习或在线学习，能否**避免**多重检验选择偏差与前视偏差？或至少提供**统计准则 / 后悔界**？
> **核实口径**同 §12.0。

### 13.0 三条结论

1. **「不接 LLM」不改变问题**。选择偏差的驱动量是**试验次数 N 与试次间相关性**，不是生成器类型。手工枚举 4 模板 × 20 组参数 = 80 次试验，与 LLM 生成 80 个候选在统计上同构。换生成器不能免疫，只能减少 N。
2. **前视偏差不能被统计方法「修正」**。它是**信息集**问题（t 时刻可见什么），只能靠结构与审计；统计方法只能**检测**（扰动测试）与**隔离**（purged CV、PIT 数据）。
3. **三类保证不可互相替代**：

| 手段 | 保证的对象 | 不保证什么 |
|------|------------|------------|
| 离线多重检验校正（DSR/PBO/SPA/StepM/MCS/FDR） | 在 N 次试验下控制误报概率（FWE / FDR 或等价惩罚） | 不能提高真实 alpha；只报告冠军时**事后无法补救** |
| 序贯 / anytime-valid（e-process、online FDR） | 任意停止时刻下误差仍受控 | 不解决「候选集合本身是搜索出来的」 |
| 在线学习（regret bound） | 相对**事后最优臂**的累计遗憾 | **不保证**被选臂的收益估计无偏；不替代报告有效性 |

**因此**：能拿到的是「**量化惩罚 + 停止规则 + 声明义务**」，不是「免疫」。唯一真正「避免」的路径是**减少搜索**（预注册 + 一次性检验 + 数据隔离）。

### 13.1 两类偏差的性质差异

| 维度 | 多重检验 / 选择偏差 | 前视偏差 |
|------|---------------------|----------|
| 成因 | 从 N 个候选中挑最大 | t 时刻用了 t 之后的信息 |
| 是否随能力增强而恶化 | **是**（搜索越强越严重） | 否（与搜索强度无关） |
| 统计方法能否消除 | 不能，只能控制误报率 | **完全不能** |
| 有效对策 | 降低 N（预注册）/ 记录 N 并惩罚 / 不选而合 | 结构约束（信息集）+ 扰动检测 + PIT |
| 本仓现状 | 无 trial 登记（§11 E18） | `history` 尚未存在（G1）；`PIT_SUPPORTED=False` |

### 13.2 离线统计准则（「从 N 个回测里挑最好」的正式化）

| 准则 | 回答的问题 | 输入要求 | 本仓可行性 |
|------|------------|----------|------------|
| **DSR**（Bailey & López de Prado 2014） | 给定 N 次试验，最大 Sharpe 是否仍显著 | N + 收益偏度/峰度 | 需 ledger 提供 N |
| **PBO / CSCV**（2017） | 样本内冠军在样本外排名落后于中位的概率 | N×T 收益矩阵 | 需全候选收益 |
| **Reality Check**（White 2000, *Econometrica*） | `max_i` 统计量是否显著超过基准（bootstrap，控 FWE） | 全候选相对基准的损失序列 | 需 ledger |
| **SPA**（Hansen 2005, *JBES*） | 同上，但对「明显劣质候选」的加入更稳健（studentized + 剔除） | 同上 | 需 ledger |
| **StepM**（Romano & Wolf 2005, *Econometrica*） | 「**哪些**候选真的优于基准」（逐步剔除，控 FWE，功效高于 RC） | 同上 | 需 ledger |
| **MCS**（Hansen, Lunde & Nason 2011, *Econometrica*） | 输出**存活集合**而非单一冠军 | 同上 | 需 ledger |
| **t > 3.0 门槛**（Harvey, Liu & Zhu 2016, *RFS* 29(1)） | 新因子的经验显著性门槛 | 单个 t 值 | 可直接写进评估协议 |
| **Haircut Sharpe**（Harvey & Liu 2015） | 按 N 折减报告 Sharpe | N | 需 ledger |
| **MinBTL**（Bailey et al. 2014） | 给定 N，回测至少要多少年才可信 | N | 需 ledger |

**关键工程结论**：RC / SPA / StepM / MCS 都需要**全部候选的收益序列**。一旦只保留冠军的净值曲线，这些准则**事后无法计算**——所以 ledger 必须**在搜索时**记录，不能事后重建。这比算法选择更决定成败。

**统计学习理论的边界**（判断，非文献结论）：VC / Rademacher 类泛化界在金融时序上因有效样本小、分布非平稳而极松，实务中不构成可用准则；能落地的仍是上表的经验型多重检验方法。

### 13.3 序贯 / 在线监控准则（上线后持续观察）

| 准则 | 适用 | 要点 |
|------|------|------|
| **Group sequential / alpha-spending**（Pocock、O'Brien-Fleming） | 预设最大观察次数，期中可看 | 每次「偷看」都消耗 alpha 预算 |
| **Anytime-valid / e-process**（Ramdas et al. 2023, *Statistical Science*；arXiv 2210.01948） | **不预设**停止时间，随时可看 | 用 test martingale 的「财富」代替 p 值；任意停止时间下仍有效 |
| **Online FDR：LORD / SAFFRON**（Javanmard & Montanari 2018；Ramdas et al. 2018） | 策略库持续新增、逐个上线 | 按「alpha 财富」分配检验预算，控 FDR 而非 FWE |
| **CUSUM / e-detector**（Page 1954；Shin et al. 2024） | 检测 alpha 衰减 / regime 切换 | 控制误报率的同时给出最快检测延迟 |

**对本仓的价值**：P-051c 的「监控 / 退役」若用固定窗口 Sharpe + 阈值，会重复「反复偷看」问题；e-process 是这一场景的现成答案（无需预设观察期）。

### 13.4 在线学习：后悔界能给什么、不能给什么

**定义**：`R_T = max_i Σ_t r_{i,t} − Σ_t r_{a_t,t}`（事后最优臂 vs 实际选择）。

| 算法 | 典型遗憾量级 | 参考 |
|------|--------------|------|
| Hedge / 指数权重 | `O(√(T ln N))` | Freund & Schapire 1997 |
| EXP3（对抗性、无分布假设） | `O(√(T N ln N))` | Auer et al. 2002 |
| UCB1（随机、有界奖励） | `O(√(N T ln N))` | Auer, Cesa-Bianchi & Fischer 2002 |
| Thompson Sampling | 贝叶斯遗憾同阶 | Russo & Van Roy 2016 |
| 下界 | `Ω(√(N T))` | 无免费午餐的定量形式 |

**不能给的**：
- 遗憾界**不**保证被选臂的样本均值无偏——它约束的是**累计实现收益**，不是**估计量**；
- 最优臂是**事后**定义的，因此遗憾界本身不消除「选择性报告」；
- 低信噪比 + 非平稳下，`√T` 的界是 worst-case，可能远大于真实 alpha；非平稳需换滑动窗口 / 折扣 / EXP3，界的形式随之改变；
- 分配器的超参（学习率、窗口长度）本身又是新的选择维度。

**能给的（结构价值）**：
- **「不选而合」**：把「选出最好」换成「按权重分配」，报告的是**组合实现收益**而非「N 个里的样本内最大值」——选择偏差被结构性绕过；
- 本仓 `agents/strategy_allocator.py` 已有 FTRL / Hedge / UCB / Thompson / MV（§11 E13），**零新代码**即可做离线实验；
- 遗憾框架强制显式信息集（t 时刻只用 ≤t−1），是**纪律**而非校正。

### 13.5 前视：可自动化的检测判据

| 判据 | 做法 | 强度 |
|------|------|------|
| **未来扰动测试**（future-shift falsification） | 随机置换 / 加噪 t 之后的收益（及价格），重算 t 时刻信号；**信号变化即泄漏** | 强，可写成单测 |
| **Purged K-Fold + embargo** | 训练/验证之间留 gap（本仓 `WalkForwardConfig.gap_days=20`） | 中，评估期用 |
| **CPCV** | 多路径组合分割，给分布而非单点 | 中，评估期用 |
| **非预期性（non-anticipativity）** | `generate_signals(view)` 的 `view` 只含 ≤t−1；类型层面强制 | 强，结构级 |
| **PIT 数据** | 财报类因子需版本轴（本仓 `PIT_SUPPORTED=False`） | 对价量模板不构成约束 |

**关键判断**：4 类价量模板的前视风险**集中在滚动窗口端点**，不在数据源本身（日频 OHLCV 天然 PIT）。因此「`history` 截断 t−1 + `shift(1)` + 一个扰动测试」已覆盖绝大部分风险，不需要完整的 PIT 基建。

### 13.6 对 P-051b 的直接结论：最小准则集（零代码）

1. **本批试验数 = 4，不是 4×N**：4 个模板各跑**默认参数**一组，且**全部报告**（不挑最好）→ 选择偏差 ≈ 0，无需 DSR/PBO。
2. **禁止在 P-051b 内做参数网格**：一旦枚举参数，N 从 4 抬到几十，立刻落入 §13.2 的适用范围，而本仓尚无 ledger（§11 E18）。
3. **若只报告最优一个**：N=4，DSR 惩罚极小但仍须在报告中声明「从 4 个候选中选出 1 个」——声明是零成本的。
4. **前视**：`history` 截断 t−1 + 模板内禁负 shift + **一个扰动测试用例**（建议纳入 I2 的机械验证），成本约 1 个测试。
5. **写进 DESIGN 的「评估协议」章节**（声明式，不写代码）：每次报告必须声明 ①试验数 N ②是否预注册 ③是否报告全部候选 ④是否做多重检验校正。这正是 `core/validation.py` 现有 `multiple_testing` 字段的语义延伸。

### 13.7 引用清单（可复核）

- White, *A Reality Check for Data Snooping*, Econometrica 68(5), 2000：https://doi.org/10.1111/1468-0262.00152
- Hansen, *A Test for Superior Predictive Ability*, JBES 23(4), 2005
- Romano & Wolf, *Stepwise Multiple Testing as Formalized Data Snooping*, Econometrica 73(4), 2005：https://www.econ.uzh.ch/dam/jcr:ffffffff-935a-b0d6-ffff-ffffa286d4d1/etca.pdf
- Hansen, Lunde & Nason, *The Model Confidence Set*, Econometrica 79(2), 2011：https://www.atlantafed.org/-/media/documents/research/publications/wp/2005/wp0507a.pdf
- Harvey, Liu & Zhu, *…and the Cross-Section of Expected Returns*, RFS 29(1), 2016（t > 3.0）
- Ramdas et al., *Game-Theoretic Statistics and Safe Anytime-Valid Inference*, Statistical Science 38(4), 2023：https://arxiv.org/abs/2210.01948
- Javanmard & Montanari, *Online Rules for Control of False Discovery Rate and False Discovery Exceedance*, Annals of Statistics 46(2), 2018；SAFFRON：https://arxiv.org/abs/1802.09098
- 综述：*Online Multiple Hypothesis Testing*, Statistical Science 38(4), 2023：https://projecteuclid.org/journals/statistical-science/volume-38/issue-4/Online-Multiple-Hypothesis-Testing/10.1214/23-STS901.pdf
- 教材：Lattimore & Szepesvári, *Bandit Algorithms*, Cambridge, 2020（遗憾界与下界）
- 教材：Cesa-Bianchi & Lugosi, *Prediction, Learning, and Games*, Cambridge, 2006（Hedge / EXP3）

**摘要级 / 未取得**：Hansen (2005)、Harvey & Liu (2015)、Russo & Van Roy (2016)、Shin et al. (2024) 仅检索到标题或转述，未取得正文——引用时只取「存在该准则」这一定性结论。

### 13.8 新增未决项

| ID | 未决 | 备选 | 推荐 |
|----|------|------|------|
| **U-P051b-10** | 评估协议声明是否写入本批 DESIGN | 不写 / 写「声明式四问」/ 写并实现 `n_trials` | **写「声明式四问」**（纯文档，零代码；`n_trials` 实现归独立批次） |

---

## 14. 补充调研：接入 LLM 生成策略时，如何**设计机制**避免选择偏差

> **前置**：§13 已论证「事后校正不能免疫」。本节回答**机制设计**——如果真要接 LLM，应怎样把偏差挡在结构里，而不是靠事后折扣。

### 14.0 结论：四层强度阶梯（越靠前越强）

| 强度 | 机制 | 报告的量 | 是否需要多重检验校正 |
|------|------|----------|----------------------|
| **① 不搜索** | 预注册单一假设 + 确认集一次性使用 | 一次检验的结果 | 不需要（N=1） |
| **② 不选** | 报告全集 / MCS 存活集 / no-regret 集成实现收益 | 集合或组合，不是 max | 不需要（未取 max） |
| **③ 选但校正** | 固定 N + ledger + DSR/SPA/StepM | max，附带校正后显著性 | 需要 |
| **④ 自适应搜索** | anytime-valid（e-process）+ 分轮 alpha 预算 / online FDR | 任意停止时刻有效 | 需要，且**不能**用固定 N 公式 |

**关键判断**：LLM 闭环（看到回测结果再改提案）属于 ④，**N 是随机变量**——此时 §13.2 的固定 N 公式（DSR/PBO/SPA）**全部失效**。这是最容易被忽略、也最致命的一个设计错误。

### 14.1 为什么 LLM 会让问题变严重

| 因素 | 无 LLM（人工枚举） | 有 LLM（闭环） |
|------|--------------------|----------------|
| N | 事先可数 | **事后才知道**（且每次重跑都不同） |
| 候选相关性 | 高（同一模板的邻域） | 可能低（跨模板跳跃）→ `N_eff` 更高 |
| 搜索是否自适应 | 否 | **是**（看到反馈再改） |
| 可复现性 | 高 | 低（温度/模型版本漂移） |
| 失败候选是否被记录 | 通常否 | 通常否 → 更严重 |

后两行说明：**LLM 不是「多了一个生成器」，而是「多了一个不可复现的自适应搜索过程」**。机制设计必须针对这一点。

### 14.2 八条机制（M1-M8）

| # | 机制 | 作用点 | 做法 | 代价 |
|---|------|--------|------|------|
| **M1** | **有界假设类** | 源头减少 N | LLM 只能在 `param_schema` 的离散域内提议；模板集合、参数上下界、轮数全部预声明 | 表达力下降（但换来 N 可枚举） |
| **M2** | **预注册 + 确认集保管** | 结构消除 | 搜索前把「假设类 + N 预算 + 指标 + 确认集区间」写 manifest 并哈希；确认集**只在最后用一次**，且 LLM 不可见（只给 schema，不给价格） | 可用数据减少；需访问控制 + 审计日志 |
| **M3** | **试验账本** | 使校正可行 | append-only 记录每个候选：`config / code_hash / data_slice / metric / timestamp / model_version / prompt_hash / temperature`；**非确定性重跑记为新试验** | ~200 行；但无它则 ③④ 层全部不可用 |
| **M4** | **有效试验数 `N_eff`** | 校正精度 | 候选收益相关性聚类 / 参与率 `(Σλ)²/Σλ²`；`N_eff ≤ N`，DSR 用 `N_eff` | 需全候选收益矩阵 |
| **M5** | **不取最大** | 绕过选择 | 三选一：①报 MCS 存活集（不选冠军）；②报 no-regret 集成实现收益；③必须选冠军时用 DSR + SPA/StepM + winner's curse 解析修正（`E[max] ≈ σ√(2 ln N)`） | ①放弃单一策略；②放弃「最好」叙事 |
| **M6** | **自适应搜索的 anytime-valid** | ④ 层必需 | 分轮 alpha 预算（每轮固定 B 个候选）或 e-process 按轮累积证据；候选流式到达时用 online FDR（LORD/SAFFRON） | 需放弃「边搜边看直到满意」 |
| **M7** | **负对照 / 泄漏审计** | 证明机制有效 | ①**泄漏 oracle**：故意注入前视候选，门禁必须拒绝；②**安慰剂搜索**：在打乱标签/GBM 合成数据上重跑同一流程，若「发现 alpha」则流程有偏；③未来扰动测试 | ~100 行 + 一个 CI job |
| **M8** | **组织门禁** | 防退化 | 提议者 ≠ 评估者；LLM 产物人审后才进 registry；模型版本与 prompt 钉死并落盘 | 流程成本 |

**M6 的二元选择**（本节的硬结论）：**要么冻结 N（固定轮数 + 固定每轮候选数），要么采用 anytime-valid**。不存在「先搜着看，事后数 N」的第三条路——因为事后数出的 N 已经包含「停在哪」这个信息，属于可选停止，固定样本公式不成立。

**M5 的工程取舍**：本仓已有 `agents/strategy_allocator.py`（FTRL/UCB/TS/Hedge），路线②**零新算法**；路线①需实现 MCS（§13.2）；路线③需 DSR + SPA。建议先②后①，路线③只在「必须交付单一策略」时启用。

### 14.3 机制 × 偏差覆盖矩阵

| 机制 | 选择偏差 | 前视偏差 | 知识泄漏（LLM 记忆） | 不可复现 |
|------|----------|----------|----------------------|----------|
| M1 有界假设类 | 部分（降 N） | — | — | — |
| M2 预注册 + 确认集 | **强（归零）** | 部分 | 部分（确认集隔离） | — |
| M3 ledger | 强（使校正可行） | — | — | **强**（版本/prompt 落盘） |
| M4 `N_eff` | 中（校正精度） | — | — | — |
| M5 不取最大 | **强** | — | — | — |
| M6 anytime-valid | **强（自适应场景唯一正确解）** | — | — | — |
| M7 负对照 | 中（检测机制失效） | **强（检测）** | 中（合成数据可测记忆外的真实预测力） | — |
| M8 组织门禁 | 中 | 中 | 中 | 强 |

**注意**：没有任何机制能处理「LLM 参数化记忆了历史行情」——这正是 [2510.07920](https://arxiv.org/abs/2510.07920) 的结论（知识截止后收益蒸发）。M2 的「LLM 不见价格」只阻断**上下文泄漏**，阻断不了**权重记忆**。唯一可靠的验证是**确认集时间区间晚于模型知识截止**，或改用合成/扰动数据（M7②）。

### 14.4 反模式清单（看起来在防偏，实际无效）

1. **用样本外回测当「确认」**——只要看过多次就不再是样本外；除非一次性且此前从未接触。
2. **用 walk-forward 代替多重检验**——walk-forward 只解决时间顺序，不解决 N（本仓已有 `WalkForwardValidator`，别误用）。
3. **「数据够多就能稀释选择偏差」**——偏差来自取 max，样本量增大不消除。
4. **只报 Sharpe 不报 N**——第三方无法复核；等价于自报「未校正」。
5. **让 LLM 自评「是否过拟合」**——用 LLM 验证 LLM，属 §11.6 的循环论证。
6. **设「最少交易次数」门槛**——降低噪声，不解决多重性。
7. **在 CV 上调参后又用同一 CV 报告**——经典泄漏。
8. **事后估算 trial count**——必须在搜索时记录；事后估算必然低估（幸存者偏差）。

### 14.5 本仓落点与成本

| 组件 | 建议位置 | 规模 | 依赖 |
|------|----------|------|------|
| Trial ledger（append-only + 派生 N） | `core/selection.py`（新） | ~200 行 | 0 |
| `N_eff`（相关性聚类 / 参与率） | 同上 | ~80 行 | numpy |
| DSR | 同上 | ~150 行 | scipy.stats |
| SPA / StepM（bootstrap） | 同上 | ~250 行 | numpy |
| MCS | 同上 | ~200 行 | numpy |
| e-process / online FDR | 同上 | ~150 行 | 0 |
| 负对照 harness（oracle + 安慰剂） | `tests/` 或 `core/audit.py` | ~100 行 | 0 |
| 合计 | — | **~1130 行 + 60-80 测试** | 0 新增 |

门禁影响：`mypy` +1~2 文件；需改 `MULTIPLE_TESTING_SUPPORTED`（§11 E18）→ 牵连 `validation.py` 报告与相关 golden，属**跨批次变更**。

### 14.6 推荐路线：先做「固定 N」最小集（M1+M2+M3+M7）

理由：这四条把 N 变成**已知常数**，使 ③ 层公式可用；成本最低且不依赖统计实现。

| 顺序 | 机制 | 交付物 | 验收 |
|------|------|--------|------|
| 1 | M1 | `param_schema` 离散域 + 轮数/候选数上限写进 manifest | 给定 manifest 能**枚举出全部候选**（N 可复算） |
| 2 | M3 | ledger 落盘 | 任一次搜索能回答「N 是多少、有哪些候选」 |
| 3 | M7 | 泄漏 oracle + 安慰剂搜索两个用例 | oracle 被拒；合成数据上假阳性率 ≈ 名义 α |
| 4 | M2 | 确认集一次性 + 哈希 | 确认集被二次访问时**报错** |

M4/M5/M6 在「必须选冠军」或「改为自适应搜索」时再补。

### 14.7 引用与核实状态

| 条目 | 用途 | 核实 |
|------|------|------|
| arXiv [2608.27734](https://arxiv.org/abs/2608.27734) | 泄漏 oracle（SR=35 仍通过 DSR/PBO）+ 按 trial 数 deflate | 摘要已核（§11.6） |
| arXiv [2502.16789](https://arxiv.org/abs/2502.16789) | AST 原创性 + 复杂度上限 → M1 | 摘要已核（§11.6） |
| Kaufman, Rosset, Perlich, Stitelman, *Leakage in Data Mining*, ACM TKDD 6(4), 2012 | 泄漏分类学（M7） | 官方已核（DOI 10.1145/2382577.2382579） |
| Kapoor & Narayanan, *Leakage and the reproducibility crisis in ML-based science*, Patterns, 2023 | 21 问 model info sheet → M2/M8 的声明模板 | 官方已核（PMC10499856） |
| Berk, Brown, Buja, Zhang, Zhao, *Valid Post-Selection Inference*, Annals of Statistics 41(2), 2013 | 选择性推断（M5 路线③的理论依据；假设强，金融慎用） | 官方已核（arXiv 1306.1059） |
| Cover, *Universal Portfolios*, Mathematical Finance 1(1), 1991 | 「不选而合」的经典保证（M5 路线②） | 官方已核（PDF） |
| Hansen, Lunde & Nason, *The Model Confidence Set*, 2011 | M5 路线① | 官方已核（§13） |
| Ramdas et al., *SAVI*, 2023；Javanmard & Montanari, 2018 | M6 | 官方已核（§13） |
| Nosek et al., *The preregistration revolution*, PNAS, 2018 | M2 | **未本轮核实**（经典文献，仅作概念引用） |
| López de Prado & Lewis, *Detection of false investment strategies using unsupervised learning*, 2019 | `N_eff` 的 ONC 方法 | **未本轮核实**（仅作方法名引用） |

### 14.8 三条硬结论

1. **机制的强度顺序不可颠倒**：不搜索 > 不选 > 选但校正 > 自适应不校正。设计时应先问「能不能不选」，再问「怎么校正」。
2. **LLM 闭环必须先解决 N 的定义**：冻结轮数与每轮候选数（固定 N），或直接上 anytime-valid。二者必选其一，否则所有后续统计都是装饰。
3. **没有负对照就没有证据**：M7 是唯一能证明「机制真的生效」的手段（而不是「机制看起来存在」）。这也与本仓「可单独验证审计」的架构原则一致。

---

## 15. 补充调研：F 盘 `Fin_Agent`（博主观点蒸馏）能否接入，研报/KOL 生成策略是否可行

> **对象**：`F:\Fin_Agent\blogger_distillation`（财经博主知识蒸馏框架，L1→L4 五层，自述 2640 测试）。
> **方法**：实读代码与 README；外部证据见 §15.8，均标注核实方式。

### 15.0 结论先行

| 判断 | 内容 |
|------|------|
| **能不能接** | **能，而且接口已经存在**——但它接的是 `agents/guru_agent_v2`，**不是** `strategies/` 模板库 |
| **接在哪个缝** | `guru_exporter.py` 产出 Guru JSON → 本仓 `GuruDataLoader` 扫描 `gurus/*.json` → `GuruAgentV2` → `MultiAgentBacktestEngine`（§11 E17） |
| **P-051b 能否直接用** | **不能**。Guru JSON 是「人物画像 + 因子偏好权重」，没有权重时间序列、没有策略参数；4 类价量模板也不需要文本输入 |
| **KOL 观点生成策略** | **作为弱信号源可行，作为「策略作者」不可行**——Finfluencers 证据显示 56% 为 antiskill，且 antiskill 粉丝更多 |
| **研报解读生成策略** | 技术可行（中文研报情绪对收益/波动有预测力），但**发布时点（PIT）与选择偏差**是硬约束 |
| **本仓既有立场** | 已把「Agent 博主蒸馏」登记为 🔴 严重风险（[LLM_PREDICTION_AS_TRUTH_RISK.md L179](file:///f:/Coding/Factor_Trading_v3.0/docs/LLM_PREDICTION_AS_TRUTH_RISK.md#L179)），并配了审计工具与隔离测试 |

### 15.1 Fin_Agent 现状（实读，E21-E28）

| # | 锚点 | 事实 |
|---|------|------|
| E21 | [README.md L11-33](file:///F:/Fin_Agent/blogger_distillation/README.md#L11-L33) | 五层：L1 采集（yt-dlp/Whisper/网页）→ L2 蒸馏（LLM 观点提取、Δ立场、CoT/框架提取）→ L2.5 评估（事实核查、断言追踪、Granger、校准、观点量化、分层贝叶斯）→ L3 存储（Chroma/知识图谱/事件库）→ L4 应用（检索/模拟/对比/桥接/Guru 导出） |
| E22 | [guru_exporter.py L133-152](file:///F:/Fin_Agent/blogger_distillation/l4_application/guru_exporter.py#L133-L152) | 导出字段：`blogger_id / agent_id / name / core_philosophy / mental_models / heuristics / expression_dna / anti_patterns / blind_spots / preferred_factors / distillation_config / calibration / n_opinions / n_calibrated_opinions / confidence_level` |
| E23 | [guru_exporter.py L45-64](file:///F:/Fin_Agent/blogger_distillation/l4_application/guru_exporter.py#L45-L64) | `preferred_factors` 由关键词映射产生：低估值→`factor_value`、动量→`factor_momentum`、质量→`factor_quality`、分红→`factor_dividend`、市值→`factor_size`、换手→`factor_turnover`、波动→`factor_volatility`、低波→`factor_low_volatility` |
| E24 | [guru_agent_v2.py L46-107 / L278-295](file:///f:/Coding/Factor_Trading_v3.0/agents/guru_agent_v2.py#L278-L295) | 本仓 `GuruDataLoader` glob `gurus/*.json`（文件名 stem = `guru_id`）；`_build_factor_config` 直接把 `preferred_factors` 转成 `factor_*.pkl` + 权重；缺省回落 value+momentum 各 0.5 |
| E25 | [core/config.py L37-54](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L37-L54) | 本仓已定义 `DistillationSource` / `LearningMode` / `AgentDistillationConfig`；现有 `gurus/buffett.json` L71-74 使用 `source="manual"`，而 Fin_Agent 导出 `source="trained"` |
| E26 | [distillation_audit.py L26-50](file:///f:/Coding/Factor_Trading_v3.0/tools/distillation_audit.py#L26-L50) | 本仓已有「可疑权重」审计（1/3、2/3、1/4、1/5 倍数等），用于检测蒸馏产物的数据窥探痕迹 |
| E27 | [README.md L212](file:///F:/Fin_Agent/blogger_distillation/README.md#L212) | 自带时间约束检索（ChromaDB `$lte` 过滤）以「防止前瞻偏差」，并有 [time_semantics.py](file:///F:/Fin_Agent/blogger_distillation/time_semantics.py) |
| E28 | [README.md L106-107 / L318](file:///F:/Fin_Agent/blogger_distillation/README.md#L106-L107) | **成熟度警示**：视频路径（yt-dlp+Whisper）待修复；「真实 LLM 端到端测试」因 LM Studio 不可达**跳过**——即 LLM 抽取链路尚未在真实模型上端到端验证 |

### 15.2 三条接线路径

| 路径 | 链路 | 改动量 | 适用 |
|------|------|--------|------|
| **A. Guru 路径（已存在）** | Fin_Agent `GuruExporter.write_json` → `gurus/*.json` → `GuruDataLoader` → `GuruAgentV2` → `MultiAgentBacktestEngine` | **≈0 行**（仅字段对齐） | 人物画像 → 因子偏好 → 多 Agent 回测 |
| **B. 画像 → 模板参数** | `preferred_factors` / `heuristics.threshold` → 4 模板参数（如 `trend_breakout.ma_n`） | ~150-250 行适配器 | 想用 `strategies/` 统一回测口径时 |
| **C. 观点 → 事件因子** | 按「发布日 × 标的」聚合情绪分 → `set_signal(mode="scores")` 或新因子 pkl | ~600-900 行（实体链接/PIT/去重） | 真正把 KOL/研报做成 alpha 源 |

**A 路径的三个具体对齐点**（实读差异）：
1. `GuruDataLoader` 以**文件名**为 key，Fin_Agent 以 `agent_id = blogger_id + "_distilled"`；两者不一致时 `GuruAgentV2(guru_id=...)` 会找不到 → 约定「文件名 = agent_id」。
2. 本仓 `get_guru_info` 读取 `english_name` / `position_style`，Fin_Agent 不产出 → 走 `.get()` 默认值，不报错但信息缺失。
3. `distillation_config` 是**两套独立定义**（本仓在 `core/config.py`，Fin_Agent 在 `l4_application/distillation_config.py`），靠字段名约定对齐，**枚举值漂移不会报错**——建议加一个契约测试。

### 15.3 与 P-051b 的边界（明确不做）

- 4 类模板的输入是 `MarketView`（价量 + 可选 history），**没有文本字段**；接 KOL 需扩 `MarketView`，会把「价量模板」变成「混合信号模板」，超范围。
- 因此：**P-051b 不接 Fin_Agent**；A 路径归 `agents/`，B/C 路径另立批次（与 §11 的 L0/L1 分级对齐）。

### 15.4 KOL 观点：作为信号源可行，作为策略作者不可行

| 证据 | 结论 | 核实 |
|------|------|------|
| Chen, De, Hu & Hwang, *Wisdom of Crowds*, RFS 27(5):1367-1403, 2014 | Seeking Alpha 文章与评论的文本观点**能预测**未来收益与盈余惊喜 | 官方已核 |
| NBER 工作论文 *Finfluencers*（f204198） | 财经网红中 **56% 为 antiskill**（月均 −2.3% 异常收益）、28% skilled（+2.6%）、16% unskilled；**antiskill 的粉丝更多** | 论文 PDF 已核 |
| UNSW BusinessThink 报道 | 跟随网红组合一年**跑输 S&P 500 约 43 个百分点**，且事前无法用粉丝数/播放量/认证等识别可靠者 | 第三方转述 |

**推论**：KOL 观点可以进「横截面弱信号」（路径 C），但**不能**把「博主说了什么」直接当作策略逻辑；更不能以「粉丝多 = 准」做筛选——证据恰好相反。

### 15.5 研报解读生成策略：可行性与硬约束

| 层 | 可行性 | 关键约束 |
|----|--------|----------|
| 研报情绪 → 横截面打分 | **可行**：中文研报 BERT 情绪对波动率、超额收益、成交额有预测力（[arXiv 2411.08726](https://arxiv.org/abs/2411.08726)；A 股研报情绪网络 ESAN，[arXiv 2112.11444](https://arxiv.org/abs/2112.11444)） | 必须用**发布日**而非研报内数据日；同一研报多平台转载需去重 |
| 新闻 + 多因子 → 收益/风险报告 | **可行**：[FinReport](https://arxiv.org/abs/2403.02647) 用 SRL + 语义依存 + 多因子做可解释预测 | 其「可解释」不等于「可交易」，仍需交易成本与容量约束 |
| 研报 → 策略代码（LLM 直出） | **不建议**：等价于 §14 的 L2 自由代码 + §13 的选择偏差 | 需沙箱 + ledger + 负对照，本仓均无 |
| 目标价 / 评级当预测值 | **高危**：卖方评级与目标价有系统性乐观偏差 | 只能做相对变化（上调/下调），不能当绝对收益预期 |

**判据**：研报路径的价值在「**事件**（评级变动、目标价调整、盈利预测修正）」而非「**文本风格**」；前者可 PIT、可复现，后者难。

### 15.6 风险清单（与 §11/§13/§14 打通）

| # | 风险 | 证据/现状 | 缓解 |
|---|------|-----------|------|
| R1 | **幸存者偏差**（只蒸馏「现在还有名」的博主） | Finfluencers：antiskill 粉丝更多 → 名气与能力负相关 | 博主池按**事前**规则固定（粉丝数/更新频率），不按业绩筛选 |
| R2 | **前视**：观点发布日期 vs 内容提及日期 vs 数据可得日 | Fin_Agent 已有 `$lte` 过滤（E27），但仅覆盖检索层 | 入库时强制记录 `published_at` 与 `ingested_at`，回测只用前者 |
| R3 | **LLM 抽取偏差累积** | 本仓已登记 🔴（[LLM_PREDICTION_AS_TRUTH_RISK.md L179](file:///f:/Coding/Factor_Trading_v3.0/docs/LLM_PREDICTION_AS_TRUTH_RISK.md#L179)） | PPI/IPW 校正 + 小样本人工标注（该文档已给方案） |
| R4 | **不可复现** | Fin_Agent 真实 LLM 端到端未验证（E28）；模型版本漂移 | 落盘 `model_version / prompt_hash / temperature`（§14 M3） |
| R5 | **数据窥探** | `tools/distillation_audit.py` 仅启发式检测整数值权重（E26） | 升级为 §14 的 ledger + N 登记 |
| R6 | **版权/合规** | 博主内容与研报均受版权约束 | 仅内部研究；不落库分发；商用需授权 |

### 15.7 建议路线

1. **先做 A 路径验证（零代码）**：取 1 个 Fin_Agent 导出的样例 JSON，跑通 `GuruDataLoader → GuruAgentV2 → MultiAgentBacktestEngine`，并补 1 个契约测试（枚举值 + 必需字段）。
2. **B 路径按需**：只在「必须用 `strategies/` 统一口径」时做；参数必须来自画像（`preferred_factors` / `heuristics.threshold`），**不得**用回测结果反调，否则立刻产生 §13 的选择偏差。
3. **C 路径单独立项**，前置三件：①PIT 字段（`published_at`）②实体链接准确率评估（观点 → 股票代码）③trial ledger。
4. **研报优先做「事件」不做「风格」**：评级变动 / 目标价调整 / 盈利预测修正，可 PIT、可复现。

### 15.8 引用与核实状态

| 条目 | 用途 | 核实 |
|------|------|------|
| [FinGPT, arXiv 2306.06031](https://arxiv.org/abs/2306.06031) | 开源金融 LLM 的数据工程范式 | 摘要已核 |
| [FinRobot, arXiv 2405.14767](https://arxiv.org/abs/2405.14767) | 金融 Agent 平台四层架构 | 摘要已核 |
| [FinReport, arXiv 2403.02647](https://arxiv.org/abs/2403.02647) | 新闻 + 多因子 → 可解释收益预测 | 摘要已核 |
| [Analyst Reports and Stock Performance: Evidence from the Chinese Market, arXiv 2411.08726](https://arxiv.org/abs/2411.08726) | 中文研报情绪对波动/超额收益/成交额的预测力 | 摘要已核 |
| [ESAN, arXiv 2112.11444](https://arxiv.org/abs/2112.11444) | A 股研报情绪因子网络 | 摘要已核 |
| Chen, De, Hu & Hwang, RFS 27(5), 2014 | 社交平台文本观点可预测收益 | 官方已核 |
| NBER *Finfluencers*（f204198） | 56% antiskill、28% skilled；antiskill 粉丝更多 | PDF 已核 |
| Tetlock, *Giving Content to Investor Sentiment*, JF 2007 | 媒体情绪与市场 | **未本轮核实**（经典文献，仅作概念引用） |
| UNSW BusinessThink 报道 | 跟随网红组合一年跑输 43pp | 第三方转述 |

### 15.9 新增未决项

| ID | 未决 | 备选 | 推荐 |
|----|------|------|------|
| **U-P051b-12** | Fin_Agent Guru JSON 的接入归属 | P-051b / `agents/` 独立批次 / P-051c | **`agents/` 独立批次**（A 路径零代码，但需契约测试；与模板库无关） |
| **U-P051b-13** | 研报/KOL → 策略（C 路径）是否立项 | 不立项 / 仅事件因子 / 全文本因子 | **仅事件因子**（评级变动/目标价调整可 PIT、可复现；文本风格因子先不做） |

---

## 16. 案例补充：英伟达/黄仁勋事件——研报提取的价值与预测市场是否更准

> **案例**：2026 年 5 月 13 日 Culper Research 发布 NVDA 空头报告，指出「中国问题」及 CEO 与 Alice Huang 的关系；当日股价 $225.83，**次日反而创收盘新高**；11 月事件公开化后，股价较 5/13 下跌约 25%。
> **问题**：既然风险提示早已存在，研报/观点提取的价值到底是什么？Polymarket 这类预测市场的赔率是不是更准的指示器？

### 16.0 结论先行

| 问题 | 回答 |
|------|------|
| 研报的价值是「预测涨跌」吗 | **不是**。价值在**风险暴露识别 + 触发条件 + 催化剂日历 + 共识拥挤度 + 事后校准标签** |
| 为什么提示了还涨 | 报告能给「脆弱性」，给不了「触发时点」；市场定价的是共识现金流，不是风险是否存在 |
| 预测市场更准吗 | **对离散可结算事件：通常是**；**对股价路径/时点/幅度：基本无用** |
| 两者关系 | **互补，不可替代**：研报给机制与暴露，预测市场给事件概率；可交易形式是 `P(event) × E[return \| event]` |
| 正确用法 | 把赔率当**外生条件概率**做情景加权，不当 alpha 信号；必须 PIT + 流动性过滤 |

### 16.1 案例时间线（媒体报道，非一手核实）

| 时点 | 事件 | 股价/反应 |
|------|------|-----------|
| 2026-05-13 | Culper Research 发布 *NVIDIA (NVDA): The China Problem*，称「不是押注 AI 失败，而是公司有重大中国问题」，并披露 CEO 与 Alice Huang（Megaspeed）的关系时间线 | $225.83 |
| 2026-05-14 | 市场无视报告，**创收盘新高** | 「所有人都在嘲笑我们」 |
| 2026-05 至 11 | 五个月「安静的窗口」，报告未被定价 | — |
| 2026-11 | 事件公开化（董事会调查/丑闻），股价重挫 | 较 5/13 约 **−25%**；市值蒸发规模被媒体形容为超过 Meta 整体市值 |
| 2026-11 | Burry 评论：短期是「绝佳交易」，但长期仍看空、不会买入持有 | — |

**这个案例的统计结构**：方向判断正确（−25%），但**时点误差 6 个月**，且中间先经历一次新高。对做空者而言，6 个月的借券成本 + 浮亏 + 逼空风险，足以让「正确的判断」变成「亏损的交易」。

### 16.2 为什么「提前提示风险」常常无效：三个结构性原因

| # | 原因 | 说明 |
|---|------|------|
| 1 | **时点不可知** | 报告能识别脆弱性（暴露、治理、供应链），不能给出触发时点；催化剂出现前，价格可以继续上涨 |
| 2 | **概率 ≠ 赔率** | 即使 `P(下跌)=70%`，若做空成本高、尾部有逼空，期望值仍可能为负 |
| 3 | **叙事与定价分离** | 市场定价的是共识现金流预期；风险要进入价格，需要**催化剂**（调查、听证、财报、监管动作） |

**推论**：评价研报不应问「它说对了吗」，而应问「它把哪一个**未被定价的暴露**变成了**可观测的条件命题**」。这是可提取、可检验、可入库的东西。

### 16.3 研报/观点提取的价值：五个可量化维度

| 维度 | 提取物 | 可量化形式 | 与本仓的关系 |
|------|--------|------------|--------------|
| **V1 暴露识别** | 「中国收入占比 / 关键人依赖 / 单一客户」 | 暴露向量（industry / supplier / customer / geography） | 可映射到因子暴露或风险预算 |
| **V2 触发条件** | 「若 X 被调查，则 Y 重估」 | 条件命题：`event → direction/horizon` | 可写成事件研究假设，非交易信号 |
| **V3 催化剂日历** | 听证、财报、出口管制窗口 | 日期集合（PIT） | 用于**择时对冲**而非方向 |
| **V4 共识/拥挤度** | 「所有人都在嘲笑」 | 观点极性分布 / 覆盖率变化 | 反向指标，可做 positioning 代理 |
| **V5 事后校准标签** | 报告最终对/错/未验证 | 准确率、Brier、校准曲线 | 正是 Fin_Agent `calibration` 在做的事（§15 E22） |

**价值上限（必须同时声明）**：①正确但过早 ≈ 交易上错误；②单事件 n=1，无法验证概率能力；③只公开成功报告 → 幸存者偏差；④做空可行性受借券与逼空约束。

### 16.4 预测市场：对什么更准、对什么不准

| 对象 | 是否更准 | 依据 |
|------|----------|------|
| **离散、可结算、有明确到期日的事件**（选举、是否加息、是否被调查） | **通常是** | Wolfers & Zitzewitz (2004, *JEP* 18(2):107-126)：价格良好校准、优于民调；NBER 2004 摘要：平均绝对误差约 1.5pp vs 盖洛普 2.1pp |
| **同域内的相对概率排序** | 通常可用 | 但存在**域间校准差异**（arXiv 2602.19520：不同领域校准动态不同，且两家交易所均为美国平台） |
| **股价路径 / 时点 / 幅度** | **基本无用** | 预测市场合约是二元/离散的，不承载连续收益分布 |
| **多阶段条件事件**（「若被调查，则 CEO 是否辞职」） | 弱 | 合约设计难以覆盖条件链 |
| **尾部/极端事件** | 弱 | **favorite-longshot bias**：热门被高估、冷门被低估（该偏差自 Griffith 1949 起有记录，本轮未核实原文） |
| **流动性差的合约** | 不可用 | 价格噪声大、操纵成本低；Polymarket v1 数据仅链上结算、**无订单簿快照**（arXiv 2606.04217 自述局限） |

**结论**：预测市场是**事件概率**的指示器，不是**资产价格**的指示器。它替代不了研报，因为研报提供的是「事件如何映射到暴露」；它也替代不了回测，因为概率正确 ≠ 赔率有利。

### 16.5 正确用法：`P(event) × E[return | event]`

```
研报/观点提取        →  事件定义 + 暴露映射 + 触发条件
预测市场赔率(快照)   →  P(event) 的外生估计
回测/事件研究        →  E[return | event]（按暴露分组）
------------------------------------------------------
条件期望 = Σ_i P(event_i) × E[return | event_i, exposure]
```

三条纪律：
1. **快照必须 PIT**：记录 `snapshot_ts / bid-ask / volume / resolution_rule`；用结算后价格回填等于前视。
2. **赔率只做加权，不做筛选**：一旦用赔率挑选「值得研究的策略」，就重新引入 §13 的选择偏差。
3. **校准分离**：按域（政治/监管/科技/宏观）分别算 Brier 与可靠性曲线，不合并成单一分数。

### 16.6 与本仓接线的约束

| 约束 | 说明 |
|------|------|
| 数据形态 | 事件表（`event_id / publish_ts / symbol / exposure / P_event / horizon`），不是因子矩阵 |
| 消费端 | 优先 `set_signal(mode="scores")` 或事件窗口分析；**不进** `strategies/` 4 模板（模板是价量驱动） |
| 新增试验数 | 预测市场快照本身不增加 N；但「按赔率筛事件再回测」会增加 N → 必须登记（§14 M3） |
| 与 Fin_Agent 的衔接 | Fin_Agent 已有 `events_db`、`claim_tracker`、`calibration`（§15 E21），事件表可直接落在 L3；本仓只做只读消费 |

### 16.7 引用与核实状态

| 条目 | 用途 | 核实 |
|------|------|------|
| Culper Research, *NVIDIA (NVDA): The China Problem*, 2026-05-13（PDF） | 案例一手报告 | 官方 PDF 摘要级已核（仅读到首页要点） |
| CBS News, *Nvidia short-seller warned in May…* | $225.83 → 约 −25%、「所有人都在嘲笑我们」 | 媒体报道已核 |
| Fortune, 2026-11-15 | 「六个月前就做空，理由是中国问题」 | 媒体报道已核 |
| Morningstar/MarketWatch, 2026-11-09 | 「发布时股价接近历史高位，次日创新高」 | 媒体报道已核 |
| 新浪财经，2026-11-12 | 事件公开化、Burry 评论 | 媒体报道已核 |
| Wolfers & Zitzewitz, *Prediction Markets*, JEP 18(2), 2004 | 预测市场校准与优于民调 | 官方已核（经 NBER 引文与摘要） |
| NBER Digest, 2004-11 | 1.5pp vs 2.1pp 的误差对比 | 官方已核 |
| arXiv 2602.19520, *Decomposing Crowd Wisdom* | 域间校准差异；两家交易所均为美国平台 | 摘要已核 |
| arXiv 2606.04217, *Polymarket-v1 Database* | 数据局限：仅链上结算、无订单簿快照、版本外推不确定 | 摘要已核 |
| Griffith (1949) favorite-longshot bias | 赔率偏差的经典来源 | **未本轮核实**（仅作概念引用） |

### 16.8 新增未决项

| ID | 未决 | 备选 | 推荐 |
|----|------|------|------|
| **U-P051b-14** | 预测市场赔率是否纳入事件表 | 不纳入 / 仅作展示 / 作 `P(event)` 外生输入 | **仅作外生输入**（PIT 快照 + 域内校准 + 不用于筛选策略） |

---

## 17. 调研证据充分性评估（Step 1 出口判定）

> **文档现状**：§1-§16 共 905 行 / 424 个表格行 / 45 个外部链接（本节不计入）；§1-§10 为原始调研，§11-§16 为六轮补充（生成能力、外部锚点、统计准则、机制设计、Fin_Agent、案例）。
> **判定对象**：P-051b 是否具备进入 Step 2（异构复审）与 Step 3（设计）的证据条件。

### 17.0 结论

**可以进入 Step 2；尚不足以直接进入 Step 3。**

- **达标**：范围、代码锚点、外部锚点、方案矩阵、未决项推荐、基线读数、证据边界标注——7 项出口标准全部满足。
- **未达标**：三项**设计粒度**证据（A1 的 additive 实测、`history` 语义定稿、四模板闭式数值）——它们本属 Step 2/3 的产物，不计为 Step 1 缺陷，但构成「Step 2 不得跳步」的硬约束。

### 17.1 评估标准与结果

| # | 标准 | 要求 | 现状 | 判定 |
|---|------|------|------|------|
| E1 | 范围明确 | 做/不做逐条列出 | §1 五条「做」+ 六条「不做」（含 agent 生成） | ✅ |
| E2 | 本地代码锚点 | 每条缺口有 `file:line` | 8/8 缺口有锚点（E1-E20），另加 E21-E28 | ✅ |
| E3 | 外部锚点 | 每个关键裁决 ≥2 个可复核来源 | G1-G8 各 2-3 条（§12.1-12.8）；另有 §11.6 / §13.2 / §14.7 / §15.8 / §16.7 | ✅ |
| E4 | 方案矩阵 | ≥2 备选 + 推荐 + 机械判据 | §4.1（4 案）/ §4.2（3 案）/ §4.3（2 案） | ✅ |
| E5 | 未决项 | 全部有推荐值 | 14 项（U-P051b-1..14），14/14 有推荐；U-P051b-7 已由用户裁决 | ✅ |
| E6 | 基线可复现 | 读数 + 提交时点 | pytest 1040 / golden 22 / mypy 113 / black 157 / tests 112 / core 45 / `strategies/` 不存在，时点 HEAD `9c914df` | ✅ |
| E7 | 证据边界 | 标注核实状态 | 45 个链接全部带「官方已核 / 摘要级 / 未取得」；未核实项单列，不作论据 | ✅ |

### 17.2 G1-G8 证据闭合矩阵

| 缺口 | 本地证据 | 外部锚点 | 调研层 | 遗留（设计层） |
|------|----------|----------|--------|----------------|
| G1 时序历史 | E2/E4 | §12.1（zipline/LEAN/backtrader 三家） | **闭合**（A1） | `history` 字段形态与窗口默认值 |
| G2 引擎消费策略 | E3/E5 | §12.2（Qlib/backtrader/LEAN） | **闭合**（本批不做） | 无 |
| G3 工厂签名 | E6/E7 | §12.3（Qlib/Hydra/entry points） | **闭合**（U-P051b-4） | 与 P-044 既有工厂的兼容实测 |
| G4 权重约束 | E5 | §12.4（vbt/LEAN/Qlib） | **闭合**（I1） | 浮点容差（已有 1e-9） |
| G5 vol-target 归属 | E10 / §4.2 | §12.5（Moreira-Muir / Harvey） | **闭合**（引擎单点） | 无 |
| G6 前视 | O-P051a-3 | §12.6（pandas/Qlib/zipline） | **闭合**（截断 t−1 + 禁负 shift） | lint 级 or 注释级 |
| G7 测试范式 | 基线读数 | §12.7（Hypothesis/ApprovalTests） | **闭合**（三层测试） | 用例清单与计数 |
| G8 重构时机 | E3/E5 | §12.8（Qlib/LEAN/Fowler） | **闭合**（最小化） | 无 |

**结论**：8/8 在**调研层**闭合，遗留项全部属于 Step 3 的设计输出，不构成 Step 1 缺口。

### 17.3 仍不足的三项（阻断 Step 3，不阻断 Step 2）

| # | 缺口 | 为什么必须补 | 归属 |
|---|------|--------------|------|
| 1 | **A1 的 additive 实测** | 若 `MarketView` 存在**位置参数构造**或依赖 `__eq__`/序列化的用例，加字段会破坏 P-044 回归 | Step 2（复审时实测 grep + 跑用例） |
| 2 | **`history` 语义未定稿** | 字段名与形态（`dict[str, DataFrame]` vs 三个独立字段）、窗口长度默认、索引对齐、是否含 volume——四种选择会导出不同测试面 | Step 3（DESIGN 定稿） |
| 3 | **四模板闭式数值未手算** | 如 `trend_breakout` 在 25 日样例上「哪些标的入选、权重多少」未手算，无法写禁录制的断言 | Step 3（DESIGN 必做） |

**两项次要**：①测试目标 1040→~1075 是按每模板 6-8 条估算，未按用例清单加总；②`strategies/__init__.py` 的 import 触发注册顺序、以及对 mypy 文件计数的实际影响未实测。

**→ 上述三项已于 §18 补全**（additive 实测、`history` 语义定稿、四模板闭式数值）。

### 17.4 Step 2 复审输入清单（控制阅读量）

**最小必读**（约 250 行）：§1 范围 / §3 缺口 / §4 方案矩阵 / §5 模板规格 / §6 不变式 / §8 未决项 / §10 结论 / §12.9 汇总 / §13.6 最小准则 / §14.6 固定 N 路线 / 本节。

**背景可选**：§2（代码证据细节）、§11（生成能力）、§15（Fin_Agent）、§16（案例）——与模板库实现无直接关系，仅为跨批次决策留痕。

**建议复审方重点质疑 5 条**：
1. A1 是否真 additive（位置参数、默认值、`__eq__`、序列化、`runtime_checkable` 协议）。
2. `history` 截断 t−1 是否与 E4 的 `returns_window` **同窗**（否则两个窗口口径不一致）。
3. 等权 `1/n` 与 `set_signal` 行和校验 `≤1+1e-9` 是否在所有 n 下相容（浮点求和顺序）。
4. 四个模板是否都只需 OHLC（网格与趋势需 high/low；若 `history` 只给 close 则两个模板不可实现）。
5. 是否引入新 golden（I8 要求零新增、22 条零重录）。

### 17.5 判定

| 项 | 结论 |
|----|------|
| Step 1 是否可关闭 | **可以**（7/7 出口标准达标） |
| 是否可启动 Step 2 | **可以** |
| Step 2 是否可跳过直接做 Step 3 | **不可以**——§17.3 的第 1、2 项必须在 Step 2 完成 |
| 是否需要继续补充调研 | **不需要**。后续若再遇未决，按增量追加，不重写 §1-§10 |
| 文档体量风险 | 905 行 / 45 链接，复审成本偏高 → 按 §17.4 的最小清单阅读 |

---

## 18. 三项缺口补充调研（§17.3 闭环）

> 三项均为**代码/设计验证**，非文献检索：①A1 是否真 additive；②`history` 契约定稿；③四模板闭式数值。

### 18.0 结论

| 缺口 | 结论 | 依据 |
|------|------|------|
| 1 A1 additive 实测 | **成立**：加第 6 个带默认值的可选字段不破坏任何既有构造/比较/哈希语义 | §18.1（探针 + grep） |
| 2 `history` 语义 | **定稿**：`dict[str, DataFrame]`，键 `close/high/low`，行严格 `[t−W, t−1]`，与 `returns_window` 同窗 | §18.2 |
| 3 四模板闭式 | **已手算**：4 组可复现的数值样例 + 1 条通用不变量 | §18.3 |

### 18.1 缺口 1：A1 的 additive 实测

| # | 检查项 | 方法 | 结果 |
|---|--------|------|------|
| A1 | 构造方式是否为位置参数 | 读 [test_p044_strategy_interface.py L112-118 / L277-283](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p044_strategy_interface.py#L112-L118) | 2/2 处均用**关键字**参数 |
| A2 | 生产构造点 | 读 [strategy.py L302-308](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L302-L308) | `views_from_data` 全部关键字 |
| A3 | 是否有 `hash(view)` / `asdict(view)` / `view == other` | 全仓 grep `hash(.*view\|asdict(view\|== view\|view ==\|set(.*views` | **0 命中** |
| A4 | 子类追加字段后 5 位置参数是否可用 | 临时探针（工作区外，运行后已删除）：`@dataclass(frozen=True) class V2(MarketView): history: dict\|None=None` | `pos5_ok = 2024-01-02`；`fields_v2` 为 5 项 + `history` |
| A5 | 哈希语义是否变化 | 探针 `hash(view)` | 加字段**前后均** `TypeError`（`pd.Series.__hash__ is None`） |
| A6 | 相等语义是否变化 | 探针：不同实例 `view == other` | 加字段前已 `ValueError`（Series 比较歧义），**不变化** |

**结论**：A1 为真 additive。唯一可观测差异是 `dataclasses.fields(MarketView)` 由 5 项变 6 项，而全仓无该 API 的消费方。

**两个实施注意点**（不构成阻断）：
1. 新字段必须放在**末尾且带默认值**（`= None`），否则既有 5 参数调用会 `TypeError`。
2. `frozen=True` + dict 字段 → `hash(view)` 仍不可用；因 A5 已证明原本就不可用，故不算回归。若未来需要哈希视图，应显式实现 `__hash__`（本批不做）。

### 18.2 缺口 2：`history` 契约定稿

| 项 | 定稿 | 依据 |
|----|------|------|
| 字段 | `history: Optional[dict[str, pd.DataFrame]] = None`（第 6 位，带默认） | §18.1 A4 |
| 键 | `"close"` / `"high"` / `"low"`（**不含** `volume` / `open`） | 四模板只读这三个（§18.3） |
| 行 | 严格 `[t−W, t−1]`，共 W 行；**不含当日 t** | 与 E4 的 `returns_window` 同窗（`iloc[i-W:i]`，L299-300） |
| 列 | 全量 `dm.stock_codes`（不裁剪） | 与 `signal.reindex(columns=dm.stock_codes)` 一致（L288） |
| 索引 | `DatetimeIndex`，取自 `dm.trade_dates` 连续切片 | 同 `returns_matrix` |
| 取价口径 | `dm.get_adj_price(field, "raw")` | 与 `prices` 同源（L289） |
| 最小窗长 | `W ≥ max(ma_n, entry_n, exit_n, max(lookbacks), atr_period + 1)` | 各模板需求见 §18.3；**R-4 已撤销**（Step 4 F-D1 修复 b：`iloc[-lb]` 口径下 `max(lookbacks)` 行恰好够用，`iloc[-lb]` 在 `W=max` 时恰为 `t−lb`） |
| 缺省行为 | `history_window=0` → 不构造（零行为变更）；模板需要历史却拿到 `None` 或行数不足 → `ValueError` | I10 / A1 |
| 扩展性 | 新增键（如 `volume`）不改签名 | dict 结构天然可加键 |

**为什么用 dict 而不是三个独立字段**：独立字段会让 dataclass 变成 8 个参数，且未来加 `volume` 还要再改签名；dict 让契约保持「一个可选字段 + 可扩展键集」，与 §11.9「冻结契约、零代码扩展」一致。

**为什么不用 `HistoryWindow` 类**：新增类型的收益仅是属性访问更顺手，成本是 mypy 文件数 +1、序列化/比较语义再定义一次；当前 4 模板用 `history["close"]` 已足够。

**代价（实测口径）**：每字段每日 1 次 `.iloc[i-W:i]` 切片；3 字段 × 2500 交易日 = 7,500 次切片对象，不复制列。`history_window=0` 时成本为 0。

**与 `prices` 的分工**：`prices` 是**当日收盘**（用于「今日收盘 vs 昨日区间」类判定，如突破入场）；`history` 只到 t−1。二者配合足以表达四模板，且成交仍在次日开盘（`execution_timing="next_open"`，E5），不构成前视。

### 18.3 缺口 3：四模板闭式数值

**通用设定**：决策日 `t`；`history` 为 `[t−W, t−1]`；`prices` 为当日收盘。等权 `1/n_selected`；不入选 → 空 Series（权重 0）。

#### 18.3.1 `ts_momentum`（lookbacks=20/60/120，min_votes=2）

构造三个标的的锚点收盘价（中间值任意，只影响数值不影响符号）：

| 标的 | P(t−120) | P(t−60) | P(t−20) | P(t−1) | 120d 收益 | 60d 收益 | 20d 收益 | 票数 | 入选 |
|------|----------|---------|---------|--------|-----------|----------|----------|------|------|
| A | 100 | 60 | 80 | 90 | −0.10（0） | +0.50（1） | +0.125（1） | **2** | 是 |
| B | 50 | 60 | 70 | 80 | +0.60（1） | +0.3333（1） | +0.1429（1） | **3** | 是 |
| C | 100 | 80 | 70 | 75 | −0.25（0） | −0.0625（0） | +0.0714（1） | 1 | 否 |

**输出**：`{A: 0.5, B: 0.5}`，C 记 0。
**边界约定**：`sign(0) → 0 票`（不含持平）。A 的 120d 收益恰为负，用于检验「长周期反对票不阻断短周期多数」。

#### 18.3.2 `mean_reversion`（lookback=20，z_entry=2.0，z_exit=0.5）

设窗口内 `k` 个值为 `L`、`n−k` 个为 `H`（`d=H−L`，`n=20`，`std` 用 ddof=1）。可手推：

```
var = d² · k(n−k) / [n(n−1)]
z_low = −√( (n−k)(n−1) / (n·k) )
```

| k | 计算式 | z_low | 判定（entry 2.0 / exit 0.5） |
|---|--------|-------|------------------------------|
| 1 | −√(19·19/20) | **−4.2485** | 入场 |
| 2 | −√(18·19/40) | **−2.9240** | 入场 |
| 3 | −√(17·19/60) | **−2.3202** | 入场 |
| 4 | −√(16·19/80) | **−1.9494** | 不入场 |
| 15 | −√(5·19/300) | **−0.5627** | 持仓（未达出场） |
| 16 | −√(4·19/320) | **−0.4873** | 出场 |

**通用不变量**：单点偏离（k=1）时 `z = −(n−1)/√n`，与偏离幅度无关；n=20 → 恒为 **−4.24853**。可直接写成一个断言，无需构造精确数值。
**输出示例**：A（k=3，z=−2.3202）入选、B（k=4，z=−1.9494）不入选 → `{A: 1.0}`。

#### 18.3.3 `trend_breakout`（entry_n=20，exit_n=10，ma_n=60）

| 场景 | 历史构造 | 当日 `prices` | 判定 | 结果 |
|------|----------|---------------|------|------|
| 入场 | 60 日 `close=10`、`high=10`、`low=9` | 11.0 | `11 > max(high[-20:])=10` 且 `11 > MA60=10` | 入选 |
| 拒绝 | 同上，但最近 20 日 `high=11` | 10.5 | `10.5 > MA60=10` 成立，但 `10.5 < 11` | 不入选 |
| 出场 | 持仓中；最近 10 日 `low=9` | 8.5 | `8.5 < min(low[-10:])=9` | 清仓 |

**输出**：入场景单标的 → `{A: 1.0}`；「拒绝」用例专门验证**两个条件必须同时满足**（防止只测 MA 的伪通过）。

#### 18.3.4 `grid_atr`（grid_k=1.0，levels=3，atr_period=14，`base_price` 必填）

历史 15 日 `high=10.5 / low=9.5 / close=10` → 每日 `TR = max(1.0, 0.5, 0.5) = 1.0`；Wilder ATR14 = **1.0**（全部 TR 相等，**与种子无关**，可闭式）。
基准 `B = 10`（**显式传 `base_price={"A": 10.0}`**；DESIGN R-1 终版：必填，无隐式默认），间距 `s = k·ATR = 1.0`；`j = floor((B − P)/s)`，权重 `= min(j, levels)/levels`。

| 当日价 P | j | 权重 |
|----------|---|------|
| 10.0 | 0 | 0 |
| 9.0 | 1 | 1/3 ≈ 0.333333 |
| 8.0 | 2 | 2/3 ≈ 0.666667 |
| 7.0 | 3 | 1.0 |
| 6.0 | 4 | 1.0（封顶） |

**多标的归一**：A(j=1)=1/3、B(j=3)=1.0 → 原始和 4/3 > 1 → 缩放 3/4 → `{A: 0.25, B: 0.75}`。
**止损兜底（DESIGN R-3 订正）**：`stop_loss_pct=0.20` **不在模板内实现**，由 `core.stops.apply_stops` 在矩阵层施加（B=10 → 触发价 8.0）；`apply_stops` 的「触发日归 0 + 退出日禁止同日重建」保证止损优先于网格加仓。

#### 18.3.5 四模板共同可测断言

1. 空输入 → 空 `Series`，`dtype=float`；
2. 权重非负；行和 `≤ 1 + 1e-9`；
3. `index ⊆ dm.stock_codes`；
4. 同一 `(view, state)` 两次调用逐值相等；
5. `history` 缺失或行数 < 所需窗长 → `ValueError`；
6. 把 `history` 最后一行的价格改成任意值（仍是 t−1），结果按新值变化；把 **t 当日**价格放进 `prices` 不改变动量/均值回归结果（证明不偷看当日）。

### 18.4 对 §17.3 的更新

| 原缺口 | 状态 |
|--------|------|
| 1 A1 additive | **已闭合**（§18.1，6 项检查全通过） |
| 2 `history` 语义 | **已闭合**（§18.2，9 项契约条款） |
| 3 四模板闭式 | **已闭合**（§18.3，4 组样例 + 1 条不变量） |

### 18.5 仍开放的两项次要问题

> **（2026-11-21 Step 9 标注）两项均已闭合且实测**：①用例清单定稿 45 条，**实测 pytest 1091**（= 1040 + 45 名义 + C7 参数化 3 + E1 参数化 3）；②mypy 实测 **119 files 0 error**、black 实测 **240 unchanged**（真实门禁 `black --check .`）。

1. ~~测试目标 1040→~1075 仍为估算，需在 Step 3 按用例清单逐条加总。~~（已闭合 → 实测 **1091**）
2. `strategies/__init__.py` 的 import 顺序与 mypy 文件计数未实测，留 Step 9 门禁时确认。（顺序已定 grid→trend→momentum→mean_reversion；计数推演 119 已入 CHECKLIST）

### 18.6 Step 2 复审质疑点更新

§17.4 的 5 条中，**第 1、2、4 条已由本节回答**；剩余需复审方确认：
- 第 3 条：等权 `1/n` 与 `≤1+1e-9` 的浮点相容（如 n=3 时 `3×(1/3)` 的求和顺序）。
- 第 5 条：是否新增 golden（I8 要求零新增）。
