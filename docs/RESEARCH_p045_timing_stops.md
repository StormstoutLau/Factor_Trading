# RESEARCH：P-045 择时原语与止损状态机（timing + stops）

> **批次**: P-045 · **Step 1 调研** · 日期 2026-11-18
> **判档**: **T1**（新建 `core/timing.py` + `core/stops.py` 纯函数契约 + 组合器 + `tests/`）
> **上游**: [UPGRADE_MASTER_PLAN.md §5](UPGRADE_MASTER_PLAN.md) P-045（「timing + stops（F4），复用 `target_positions`/`limit_rules`」，验收「与 vectorbt 对拍；止损状态机 golden」）；[§1.2 F4](UPGRADE_MASTER_PLAN.md)；[PROGRESS §3.50.10](PROGRESS.md) P-044 批次关闭
> **代码证据时点**: HEAD `0482881`（P-044 关闭；工作区净）
> **基座**: 正文 DeepSeek-V4.1-Flash；Step 2 Review 由 GLM-5.3-Flash 执行（**异构提前成立**——作者预设「Step 2 同源」被实际执行推翻，见 §13；U-P045-5 维持登记至 Step 10 终审闭合）

---

## 1. 触发与题干

- **触发**: 用户「请开始 P-045 的 Step 1」；总纲 §5 P-045：「择时原语 | timing + stops（F4），复用 `target_positions`/`limit_rules` | 前置 P-044 | 验收：与 vectorbt 对拍；止损状态机 golden」。
- **题干（本批做什么）**:
  1. **信号层原语**：`core/timing.py`——long/short entry/exit 四掩码、`crossed_above`/`crossed_below` 交叉检测、冲突仲裁、信号 → 目标权重；
  2. **止损层状态机**：`core/stops.py`——逐持仓 `entry_price`/`peak_price`/`bar_count` 状态、固定止损、移动止损（trailing）、止盈、时间止损、bar 内触发顺序、分批退出；
  3. **与 P-044 契约的组合**：`TimingStrategy` / `StopsStrategy` 以 `Strategy` wrapper 形式叠加在既有策略之上（`StrategyState.extras` 携带状态机状态，P-044 DESIGN §8 已预留该接口约定）；
  4. **验证**：止损状态机 golden + 与 vectorbt 隔离 venv 对拍（P-015 方法论）。
- **明确不做**:
  - **不做空**（`short` 侧信号保留类型位但行为不落地 → **P-050**）；负权重仍 fail-fast（P-044 `set_signal`）；
  - **不做仓位 sizing**（分数凯利/vol-target/目标百分比 → **P-047**）；不做金字塔加仓/部分减仓的比例分配（P-047）；
  - **不做订单层 size_type / 先卖后买 call_seq / 共享现金账户**（F4 第 2 项，属 P-047/P-053 邻域）；
  - **不接线引擎主循环**（逐 bar 止损检查会触碰交易/净值主链路 → M-B 被拒）；不做风险 overlay 决策闭环（**P-048**）；
  - 不做盘中 tick/分钟 bar（本仓为日频矩阵；止损触发用日 OHLC，成交价次日开盘）；
  - 不重构 `MarkToMarketPolicy`（既有固定止损检查保留原状，不执行语义不变）。
- **职责外（不回答）**: 实盘止损单类型（StopMarket/StopLimit 柜台语义 → P-053）；策略模板（网格/趋势 → P-051）；regime 切换（P-057）。
- **能力边界（回答不了）**: 本批只证明「原语 + 状态机 + 与既有执行链组合后零行为副作用」；不证明择时策略的样本外 alpha（P-051 才做模板与晋级门）。

---

## 2. 代码事实基线（E3 @`0482881`）

### 2.1 现有择时/止损面盘点

| 对象 | 位置 | 现状 | 与本批关系 |
|------|------|------|-----------|
| **`Position`** | [tracker.py L26-115](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L26-L115) | 仅 `quantity/avg_cost/market_value/unrealized_pnl`；**无 `peak_price`（最高水位）、无 `entry_date`（持仓龄）** | G4/G5 缺口来源 |
| **固定止损** | [risk_manager.py L80-119](file:///f:/Coding/Factor_Trading_v3.0/core/risk_manager.py#L80-L119) `StopLossConfig` | `stop_loss_pct=-0.10`；`check_stop_loss` 基于 `unrealized_pnl / cost_basis` | 可复用语义，不复用实现（无水位/无龄） |
| **移动止损** | [risk_manager.py L90](file:///f:/Coding/Factor_Trading_v3.0/core/risk_manager.py#L90) `trailing_stop_pct=-0.05` | **字段声明但无任何逻辑读取**（全仓 grep 仅声明处 + 默认值断言测试） | G3：死配置 |
| **风险动作闭环** | [engine_v2.py L520-526](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L520-L526) | `check_portfolio` 产出的 `RiskActionItem` **仅 `logger.warning`**，注释「自动执行在后续版本中实现」 | G6：动作不落单 |
| **vbt 风格信号翻译** | [execution_policy.py L469-](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L469) `SignalTranslator.from_signals` | 四信号（buy/sell/short/short_exit）→ `OrderIntent`；**仅测试引用，无引擎接线** | 可复用但本批不依赖（见 M-A） |
| **V3 向量内核** | [engine_v3_vector.py L78-155](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v3_vector.py#L78-L155) | 信号 → top_n 等权目标仓位（`@njit`）；**无交叉检测/无冲突仲裁/无止损** | 非择时原语（总纲 §1.2 第 4 行判「部分」） |
| **目标权重 → 数量** | `target_positions.build_target_positions` L43 | 整手/清仓项/`value_buffer=0.985` | **复用**（F4 指定） |
| **涨跌停价带** | `filter/limit_rules.build_limit_prices` L132 | 按 board/ST/日期制度期解析限价 | **复用**（A 股可成交性） |
| **执行时序枚举** | `execution_policy.ExecutionTiming` L35-51 | `NEXT_OPEN`（A 股 T+1 默认） | **复用**（止损成交价口径） |
| **策略契约** | `core/strategy.py`（P-044） | `Strategy` Protocol + `MarketView` + `StrategyState.extras` | **组合载体**（P-044 DESIGN §8 已预留「P-045 可在内部叠加状态机，`extras` 携带状态」） |
| **对拍基础设施** | `scripts/external_benchmark/` + `.venv-vbt`（存在） | `verify_p015.py` 三态断言；`requirements-vectorbt.txt` 钉版 `vectorbt==1.2.0` / `pandas==3.1.1` / `numba==0.68.1`；`audit_signatures.py` 可读 `from_signals` 签名 | **复用**（P-015 方法论） |
| **golden** | `tests/_golden_cases.py` L36 `CASE_IDS` G1-G7 / L52-59 `CASES` | 7 case → 13 实例（V2/V3 × baseline/cost/mask/delisting/suspend） | 新增止损 case 的落点 |

### 2.2 契约缺失证据

- `core/timing.py` **不存在**（`Test-Path` = False）；
- `core/stops.py` **不存在**（`Test-Path` = False）；
- 全仓无 `entry_mask` / `exit_mask` / `crossed_above` / `stop_state` 等符号（仅 `SignalTranslator.from_signals` 形似，见 2.1）；
- `trailing_stop_pct` **零消费方**（grep 全仓：声明 + 默认值断言 = 2 处）。

### 2.3 行为锁（零行为判据来源）

| 锁 | 位置 | 作用 |
|----|------|------|
| golden 13 实例 | `tests/golden/` + `tests/_golden_cases.py` | 既有 V2/V3 数值基线，**不得重录** |
| P-043 事件 | `tests/test_p043_event_bus.py` | 引擎发射语义 |
| P-044 策略契约 | `tests/test_p044_strategy_interface.py` | `Strategy`/`BacktestAdapter`/`set_signal` 语义 |
| P-033/P-034 执行价格 | `tests/test_p033_order_price_validation.py` / `test_p034_price_diff_guard.py` | 成交价合法性 |
| P-014 停牌账目 | `tests/test_p014_suspension_accounting.py` | 双路径净值一致 |

---

## 3. 取证

### 3.1 E1 本地（可重放）

| 读数 | 命令 / 方法 | 结果 |
|------|-------------|------|
| A `core/timing.py` | `Test-Path core/timing.py` | **False** |
| B `core/stops.py` | `Test-Path core/stops.py` | **False** |
| C `trailing_stop_pct` 消费方 | 全仓 `*.py` grep | **3**（`risk_manager.py` L85 docstring / L90 声明 / `test_phase3_risk_monitor.py` L84 默认值断言；**（S2 订正，F-S2-P045-6）**初稿计 2 漏 docstring）→ **零逻辑读取**（结论不变） |
| D `Position` 字段 | Read `tracker.py:26-115` | 无 peak / 无 entry_date / 无 bar_count |
| E 风险动作接线 | Read `engine_v2.py:520-526` | 仅 `logger.warning` + 注释「自动执行在后续版本中实现」 |
| F `from_signals` 接线 | 全仓 grep | 定义 1 + 测试 11 处；**引擎 0** |
| G 对拍环境 | `Test-Path .venv-vbt` / `requirements-vectorbt.txt` | **True**；`vectorbt==1.2.0`（L65）/ `pandas==3.1.1`（L37）/ `numba==0.68.1`（L34） |
| H 基线门禁 | P-044 关闭读数 | pytest **811** / golden **13·798** / black **132·199** / mypy **105** / AST **22** / `tests/*.py` **93** / uv **0** |
| I golden 结构 | Read `_golden_cases.py` | `CASE_IDS` 7 / `CASES` 7 条；golden 13 实例 |

> 本批 Step 1 为只读取证，未运行 pytest/git 写入；H 沿用 P-044 关闭基线，Step 9 必须本批复跑。

### 3.2 E1-EXT 外部锚点（vectorbt 止损语义）

> **证据等级 E1-EXT**：官方文档 URL 可复核；只证明「对拍对象的参数语义」，不证明本项目正确性。

| 锚点 | 事实 | 对本项目的含义 |
|------|------|----------------|
| vectorbt PRO「Four stop types are built in」 | `sl_stop`（止损）/ `tsl_stop`（**trailing stop，跟随入场后最优价**）/ `tp_stop`（止盈）/ `tsl_th`（**trailing 激活阈值**） | S5 参数集须覆盖四类：固定/移动/止盈/激活阈值 |
| vectorbt.dev `from_signals` 参数 | `sl_stop`（>=0）/ `sl_trail`（启用移动）/ `tp_stop`（>=0）/ `reverse`（空头用） | 对拍参数名与符号约定（**正数=跌幅/涨幅阈值**，与本仓 `stop_loss_pct=-0.10` 负号约定相反）——S5 需显式符号裁决 |
| vectorbt 枚举 `StopPrice` | `StopMarket`：**触发后用下一 bar 开盘价成交**；`StopLimit` 同理但按限价 | 与总纲「止损按次日开盘/VWAP 成交而非触发价」一致 → S8 |
| 「Realistic backtests」 | 「**Stops are checked against each later bar**」；`order_type=limit` + `price=close` 从下一 bar 起检查 | 防前视：T 日决策只用 ≤T 数据，成交在 T+1 → I5 |
| `nb` stop 数组语义 | `stop=None/NaN` 表示禁用；可按 frame/column/row/element 配置 | 状态机应支持「逐标的覆盖配置」而非全局单一参数（S5 可选扩展，DESIGN 裁决） |

**边界声明**：本仓运行环境无 vectorbt（`.venv-vbt` 为隔离环境，主环境零污染，P-015 已立先例）；对拍在隔离 venv 内执行并写入验收记录，**不引入运行时依赖**。

> **（S2 升级，F-S2-P045-6）上表 PRO 专有参数与免费版参数须区分——隔离 venv 实测（E2，2026-11-18）**：`vectorbt==1.2.0` 导入成功，`Portfolio.from_signals` stop 相关参数实测 = `['sl_stop', 'sl_trail', 'tp_stop', 'stop_entry_price', 'stop_exit_price', 'upon_stop_exit', 'upon_stop_update', 'use_stops']`。**对拍对象为免费版 1.2.0**：`tsl_stop`/`tsl_th` 为 vectorbt PRO 专有**不在对拍范围**；trailing/激活阈值语义由 `sl_trail`（布尔开关）承载——与 U-P045-4 倾向（`sl_stop`+`sl_trail`+`tp_stop` 三项）一致。E1-EXT 锚点升级为 E2 本地可重放证据。

---

## 4. 缺口清单

| ID | 缺口 | 级别 | 证据 |
|----|------|------|------|
| **G1** | 无信号原语模块（entry/exit 四掩码 + 交叉检测） | P2 | A/C |
| **G2** | 无冲突仲裁（同日同时入场/离场、long/short 冲突无裁决规则） | P3 | A |
| **G3** | 无移动止损实现（`trailing_stop_pct` 死配置） | P2 | C |
| **G4** | 无入场价/最高水位追踪（`Position` 无字段） | P2 | D |
| **G5** | 无时间止损/持仓龄（无 `entry_date`/`bar_count`） | P3 | D |
| **G6** | 止损决策不落单（引擎仅 warning，动作与订单脱节） | P2 | E |
| **G7** | 无 bar 内触发顺序与 A 股成交价口径（触发价 vs 次日开盘） | P2 | 总纲 F4 §3 / 3.2 锚点 |
| **G8** | 无止损 golden 与 vectorbt 对拍（验收硬要求） | P3 | I / 总纲 P-045 验收 |
| **G9** | 止损触发判定需 OHLC（gap open / intraday high-low），但 P-044 `MarketView` 仅 `prices`（close）——**状态机输入载体缺口** | P2 | D + S8（**Step 2 复审新增，F-S2-P045-2**） |

---

## 5. 方案矩阵

| 方案 | 内容 | 判定 |
|------|------|------|
| **M-A（推荐）** | **纯函数原语 + Strategy 组合器**：`core/timing.py`（掩码/交叉/仲裁/信号→权重）+ `core/stops.py`（`StopConfig`/`StopState`/`StopEngine.update` 纯函数状态机）+ `TimingStrategy`/`StopsStrategy` wrapper（状态存 `StrategyState.extras`）；不接线引擎主循环 | ✅ 纯函数可独立对拍 + golden；复用 P-044 契约；引擎零改动；A 股 T+1 口径由「wrapper 产权重 → `set_signal(mode="weights")` → 次日开盘成交」天然满足 |
| M-B | 引擎主循环逐 bar 检查止损并直接下卖单 | ❌ 触碰交易/净值主链路（`_execute_rebalance`/`_process_pending_orders`），等价性无法单批证明；与 P-048 风险 overlay 职责重叠 |
| M-C | 只做 timing 不做 stops | ❌ 不满足验收「止损状态机 golden」 |
| M-D | 运行时依赖 vectorbt（停止自研） | ❌ 违反零新增依赖 + 主环境 pandas 2.2.3 与 vbt 需求 pandas 3.1.1 冲突（P-015 已实证） |
| M-E | 改造 `MarkToMarketPolicy` 并接线引擎执行 | ❌ 无水位/无龄 → 仍缺 G3/G4；且动作→订单链路需改 `_process_trading_day`，等同 M-B |

**裁决**: **M-A**。理由：唯一同时满足「纯函数可对拍 / 不改主链路零行为 / 复用既有复用面 / 关闭 G1-G8」；引擎接线与风险 overlay 决策闭环留 **P-048**（`RiskActionItem` → 目标权重调整是 P-048 题干）。

> **（S8 注，F-S8-P045-1）**M-A 描述中的「`TimingStrategy`/`StopsStrategy` wrapper」成分已被 [DESIGN_p045 D1](DESIGN_p045_timing_stops.md) 裁决**推翻**：因 G9 OHLC 载体缺口（F-D3-P045-1）改交付**矩阵级叠加**（`apply_timing`/`apply_stops`）；纯函数原语与「不接线引擎」维持。

---

## 6. 批次切分（供 DESIGN 采用；以 IMPL 文件对齐为准）

| 批次 | 内容 | 行为 | 验收 |
|------|------|------|------|
| **B1 信号原语** | `core/timing.py`：`SignalSet` / `crossed_above` / `crossed_below` / `resolve_conflicts` / `signals_to_weights` | 零行为（新符号） | 交叉检测逐值；冲突仲裁规则表化 |
| **B2 止损状态机** | `core/stops.py`：`StopConfig` / `StopState` / `StopDecision` / `StopEngine.update(view, state)` | 零行为（纯函数） | 固定/移动/止盈/时间四类触发；bar 内顺序；golden |
| **B3 组合器** | `TimingStrategy` / `StopsStrategy`（`Strategy` wrapper；状态入 `extras`；输出 `TargetWeights`） | 零行为（不接线则无副作用） | 与 P-044 `BacktestAdapter` 端到端一致 |
| **B4 测试与文档** | `tests/test_p045_timing_stops.py`（V1-V8）+ golden case + 对拍记录 + 四文档 | 新增只读面 | pytest **811 → 819**；golden 既有 13 零重录 |

> B2 依赖 B1；B3 依赖 B2；B4 与 B3 同批提交。四批均不触碰 `agents/` 与引擎主链路。
> **（S4 订正，F-S4-P045-6）**本节为 Step 1 提案：① B3「组合器」已被 [DESIGN_p045 D1](DESIGN_p045_timing_stops.md) 裁决为**矩阵级叠加**（`apply_timing`/`apply_stops`，不提供 `Strategy` wrapper，F-D3-P045-1/G9）；② 计数链以 DESIGN §6 为准——pytest **811 → 821**（+10：V1-V8 + 2 golden）、black **135·202**（+2 源 +1 测试）、golden **13→15**；③ §8 I8 同口径订正。

---

## 7. 精确语义（实施规格输入；DESIGN 可细化）

| # | 语义 |
|---|------|
| S1 | `SignalSet`（frozen）：`entries_long` / `entries_short` / `exits_long` / `exits_short` 四个 `pd.Series`（逐日真值）或 `pd.DataFrame`（逐日 × 标的）；`short` 侧本批仅保留类型位（P-050） |
| S2 | `crossed_above(series, level) -> pd.Series[bool]`：`s > level & s.shift(1) <= level`；首行为 False；**（S2 注，F-S2-P045-3）**NaN 参与比较恒 False（当前值或前值为 NaN 均不触发）；`crossed_below` 为对偶 |
| S3 | `resolve_conflicts(signals, *, exit_priority=True) -> SignalSet`：同日同时 entry+exit → **exit 优先**（A 股 T+1 保守）；显式规则表（不靠隐式覆盖） |
| S4 | `signals_to_weights(signals, *, mode="equal") -> pd.Series`：holding = entry 且未 exit；等权或全仓；不含负权重；**（S2 注，F-S2-P045-4）**exit 后剩余持仓权重**保持**（行和 <1 合法，现金冗余由 `build_target_positions` 承接）；再归一归 P-047 sizing（DESIGN 确认） |
| S5 | `StopConfig`（frozen）：`stop_loss_pct`（正数=跌幅阈值，**符号与 vbt `sl_stop` 对齐**；既有 `StopLossConfig` 负号约定不复用）/ `trailing_stop_pct` / `take_profit_pct` / `time_stop_days` / `trailing_activate_pct`（对应 PRO `tsl_th`；**（S2 订正，F-S2-P045-6）**免费版 1.2.0 无该参数（实测参数表见 §3.2 升级注），激活阈值**不在对拍范围**、仅本仓实现） |
| S6 | `StopState`（frozen，JSON 安全）：`entry_price` / `peak_price` / `bar_count` / `entry_date`（`YYYY-MM-DD`）；`to_dict`/`from_dict` 与 `StrategyState.extras` 兼容 |
| S7 | `StopDecision`：`action ∈ {"hold","exit"}` + `reason ∈ {"stop_loss","trailing_stop","take_profit","time_stop"}` + `severity: float` |
| S8 | bar 内触发顺序：先 gap（`open` 相对入场价/峰值）→ 再盘中（`high`/`low`）；同段 **SL 优先于 TP**；**成交价口径 = 次日开盘**（禁止用触发价成交，I5）；**（S2 注，F-S2-P045-2）**触发判定需 OHLC——P-044 `MarketView` 仅含 close（**G9**），载体由 DESIGN 裁决（倾向 `StopEngine.update` 显式接收 open/high/low 参数，零 P-044 契约变更） |
| S9 | 状态更新：`peak_price = max(peak_price, high)`；`bar_count += 1`；exit 后状态清除（下次入场重建） |
| S10 | 组合器：`StopsStrategy(base: Strategy, config)` 在 `base.generate_signals` 后对**当前持仓 ∩ 触发**输出 0 权重；`TimingStrategy(base, signals)` 用 `SignalSet` gate 基础策略输出；二者可串联（顺序由 DESIGN 裁决）（**S8 注，F-S8-P045-1**：S10 已被 D1 裁决为矩阵级叠加，wrapper 不交付——终态见 [DESIGN_p045 §4](DESIGN_p045_timing_stops.md)） |

---

## 8. 行为变更与不变式

**默认路径（不使用新原语）**：交易/净值/产物逐值不变；golden 既有 13 零重录。
**使用新原语**：信号/止损为纯函数，产出 `TargetWeights` 后仍走既有 `set_signal(mode="weights")` → `build_target_positions` → `ExecutionSimulator`，引擎主链路零改动。

| ID | 不变式 |
|----|--------|
| I1 | 既有 golden **13 零重录**；`agents/` / `core/engine_v2.py` / `core/engine_v3_vector.py` 零 diff |
| I2 | `core/timing.py` / `core/stops.py` 纯函数：无 I/O、无全局写、无随机（AST `open`/`requests` = 0） |
| I3 | **触发判定序列**（信号交叉与止损触发）与 vectorbt（`.venv-vbt`，`vectorbt==1.2.0`）**逐值一致**；成交价与 NAV 层面差异（vbt 免费版同 bar 触发+成交模型 vs 本仓 T 日判触发、T+1 开盘成交）按 P-015 恒等式方法论**闭式声明**（对拍记录入附录）——**（S2 收窄，F-S2-P045-1）****（S8 注，F-S8-P045-2）**对拍可操作对象为**止损触发判定序列**（IMPL §4.6）——vbt 免费版无交叉原语可比，交叉检测由 S2 语义 + V1 单测锁定 |
| I4 | 止损状态机确定性：同输入两次输出逐值相同；golden 锁定 |
| I5 | **无前视**：T 日决策只用 ≤T 数据；成交价取 T+1 开盘（`StopMarket` 语义），禁止触发价成交 |
| I6 | A 股可成交性：涨停禁买 / 跌停禁卖 / 停牌不可成交（复用 `universe.tradable` 与 `build_limit_prices`） |
| I7 | 零新增依赖（`vectorbt` 仅隔离 venv 对拍） |
| I8 | 计数链：pytest **811 → 819**；`tests/*.py` **93 → 94**；mypy **105 → 107**（+2 模块）；black **132·199 → 134·201**；AST **22 不变**；golden 新增实例的 pytest 增量 **+N_g** 由 U-P045-3 裁决后并入五文档计数链（**（S2 注，F-S2-P045-5）**golden 为参数化实例，新增 case 必增 pytest 计数）——**（S4 订正，F-D3-P045-2/F-S4-P045-6）**终值以 [DESIGN_p045 §6](DESIGN_p045_timing_stops.md) 为准：pytest **821**（819+2 golden）/ black **135·202**（+1 测试文件） |
| I9 | 状态可序列化：`StopState` JSON 往返相等；`extras` 可随 `StrategyState` 重放 |

---

## 9. 未决项登记（四元块）

- **U-P045-1 信号层 short 侧范围**
  - 判据：`entries_short`/`exits_short` 是否本批只留类型位、零行为
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**只留类型位**（字段存在、`signals_to_weights` 忽略；负权重仍 fail-fast）→ P-050
  - 证据等级：E3（P-044 `set_signal` 负权重 fail-fast + P-050 题干）

- **U-P045-2 止损接入点**
  - 判据：`Strategy` wrapper（M-A）vs 引擎 `risk_manager` 接线 vs `SignalTranslator.from_signals` 接线
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**`Strategy` wrapper**（组合器）；引擎接线与动作闭环归 P-048
  - 证据等级：E3（G6 / P-044 DESIGN §8 接口约定）

- **U-P045-3 golden 新增 case**
  - 判据：新增几个 case、是否改变既有 13 实例计数
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**新增 1-2 个 case（止损状态机：固定+移动 / 时间止损）**，既有 13 零重录；golden 总数随之增加并在五文档同步
  - 证据等级：E3（`_golden_cases.py` CASE_IDS/CASES）

- **U-P045-4 对拍范围与符号约定**
  - 判据：对拍 `sl_stop`/`sl_trail`/`tp_stop` 哪些参数；阈值符号（vbt 正数 vs 既有负号）
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**`sl_stop` + `sl_trail` + `tp_stop` 三项**；本项目 `StopConfig` 统一**正数阈值**并在文档声明与既有 `StopLossConfig`（负号）的差异
  - 证据等级：E1-EXT（3.2 四条锚点）

- **U-P045-5 异构终审**
  - 判据：Step 2/4/6/8/10 复审基座与作者不同
  - 触发条件：进入 Step 10
  - 当前倾向：作者 DeepSeek-V4.1-Flash；终审由 GLM-5.3-Flash 承接
  - 证据等级：E1（会话基座）——**（S2 订正，F-S2-P045-6）**Step 2 已异构成立（GLM ≠ 作者，见 §13）；本项维持登记至 Step 10 终审承接闭合（P-044 先例）

---

## 10. 可重放命令

```powershell
$py = 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe'
# E3：契约缺失（只读）
& $py -c "import pathlib; print('timing.py:', pathlib.Path('core/timing.py').exists()); print('stops.py:', pathlib.Path('core/stops.py').exists())"
# E3：trailing 死配置
Select-String -Path (Get-ChildItem -Recurse -Filter *.py core,agents,filter,tests).FullName -Pattern 'trailing_stop_pct'
# E1 基线（Step 9 必跑）
$env:MPLBACKEND='Agg'; & $py -m pytest tests -q -p no:cacheprovider
& $py -m pytest tests -k golden -q -p no:cacheprovider
& $py -m black --check core tests
& $py -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
uv lock --check
# 对拍（隔离 venv，仅验收记录；S8 注 F-S8-P045-3：本批对拍载体已裁决为 scripts/external_benchmark/verify_p045.py（F-S6-P045-1），下行 audit_signatures.py 为 P-015 命令存档）
.\.venv-vbt\Scripts\python.exe scripts\external_benchmark\audit_signatures.py
```

> Step 1 未执行上述命令（只读取证）；基线沿用 P-044 关闭读数，Step 9 回填红/绿。

---

## 11. Step 1 自查（RULE-4）

| # | 自查项 | 结论 |
|---|--------|------|
| 1 | 题干是否收窄 | ✅ 做空/sizing/订单层 size_type/盘中 bar/引擎接线/风险 overlay 全部显式排除 |
| 2 | 事实与推测分离 | ✅ G1-G8 均有 E3 行号或 E1-EXT 锚点；`trailing` 死配置经全仓 grep 实证 |
| 3 | 是否重做 P-042/P-043/P-044 | ✅ 复用 `Strategy` 契约与 `set_signal`；不触碰事件总线/数据契约 |
| 4 | 是否以「跑通」代替正确性 | ✅ 验收含逐值对拍 + 状态机 golden + 无前视声明 |
| 5 | 方案矩阵是否穷举 | ✅ M-A~M-E；四条拒绝理由（主链路/验收缺口/依赖冲突/职责重叠） |
| 6 | 是否触碰交易/净值语义 | ✅ 不变式 I1 显式要求引擎文件零 diff |
| 7 | 是否新增外部依赖 | ✅ 零新增；vectorbt 仅隔离 venv 对拍 |

---

## 12. 判档

**T1**——新建 `core/timing.py` / `core/stops.py` 契约（判档规则 2 强制）且改动面含 `tests/` 与 golden case。

---

## 13. Step 2 Review（异构 GLM-5.3-Flash，2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 复审 **GLM-5.3-Flash** ≠ 作者 DeepSeek-V4.1-Flash → **异构成立**（作者头部预设「Step 2 同源」被实际执行推翻——异构增益提前获得）；U-P045-5 维持登记至 Step 10 终审闭合（P-044 先例）。
> **取证方式**: E1 命令独立重放 + E2 探针（`StopLossConfig` 默认值 / **隔离 venv `vectorbt==1.2.0` 导入 + `from_signals` 参数实测**）+ 机械复核（锚点抽检 / 计数链算术 / G 证据链）。**零预填，本节为评审后回填。**

### 13.1 复核读数

| # | 项 | 复核方法 / 读数 | 判定 |
|---|----|----------------|------|
| 1 | E1-A/B 重放 | `Test-Path core/timing.py` / `core/stops.py` 均 **False** | ✅ G1 前提成立 |
| 2 | E1-C 重放 | trailing grep 实测 **3**（L85 docstring / L90 声明 / 测试 L84）——初稿计 2 漏 docstring（F-S2-P045-6 订正）；**「零逻辑读取」结论不变** | ✅（订正后） |
| 3 | E2 符号探针 | `StopLossConfig()` 实测 `stop_loss_pct=-0.1 / trailing_stop_pct=-0.05 / enabled=True` → 负号约定实证，支撑 U-P045-4「新 `StopConfig` 统一正数」裁决 | ✅ |
| 4 | **E2 隔离 venv 探针** | `.venv-vbt\Scripts\python.exe` 导入 `vectorbt==1.2.0` **成功**；`Portfolio.from_signals` stop 参数实测 8 个（`sl_stop/sl_trail/tp_stop/stop_entry_price/stop_exit_price/upon_stop_exit/upon_stop_update/use_stops`）→ **G8 对拍可行性证实**；E1-EXT 锚点升级为 E2 本地可重放证据；`tsl_stop`/`tsl_th` 为 PRO 专有不在免费版（F-S2-P045-6 订正 §3.2/§7-S5） | ✅ |
| 5 | E1-I 重放 | `CASE_IDS` = 7（G1-G7）/ `CASES` = 7 ✓ | ✅ |
| 6 | 锚点抽检 | `engine_v2` L520-526（warning 不落单）/ `risk_manager` L80-119 / `tracker` L26-115 / `execution_policy` L469 / `_golden_cases` L36·L52-59 / `limit_rules` L132 全命中 | ✅ |
| 7 | 计数链算术 | 811+8=819 / 93+1=94 / 105+2=107 / 132+2·199+2=134·201 / AST 22（纯函数不增）✓；**I8 未含 U-P045-3 golden 新增实例增量**（F-S2-P045-5 补 +N_g 注） | ✅（订正后） |
| 8 | G1-G8 证据链 | 逐行复核成立；**新增 G9（OHLC 载体缺口，F-S2-P045-2）** | ✅（+G9） |
| 9 | M-A 裁决独立复核 | M-B 触碰交易/净值主链路（G6 证据）、M-D 依赖冲突（pandas 2.2.3 vs vbt 需 3.1.1）——维持 M-A | ✅ |

### 13.2 发现与当轮处置（2 P2 + 4 P3，全部当轮回写）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S2-P045-1 | **P2** | I3「与 vectorbt 逐值一致」范围过宽：vbt 免费版止损为**同 bar 触发+成交**模型（`StopMarket` 触发后下一 bar 开盘，bar 内 high/low 即可成交），本仓 **T 日 OHLC 判触发、T+1 开盘成交**（总纲 F4 / S8 / I5）→ **成交价与 NAV 层面不可逐值对拍**；若不收窄，DESIGN/IMPL 将朝不可达的 NAV 对拍推进或静默缩水 | I3 收窄为「**触发判定序列**逐值一致；成交/NAV 差异按 P-015 恒等式方法论**闭式声明**」（已回写）；对拍口径作为 DESIGN 强制输入 |
| F-S2-P045-2 | **P2** | S8 触发判定需 OHLC（gap open / intraday high-low），但 P-044 `MarketView` 仅 `prices`（close）→ **状态机输入载体缺口**（新增 **G9**）；`StopEngine.update(view, state)` 提案签名不可实现 | §4 新增 G9 行；S8 补载体裁决注（倾向 `StopEngine.update` 显式接收 open/high/low 参数，**零 P-044 契约变更**）；DESIGN 必答 |
| F-S2-P045-3 | P3 | S2 交叉检测未规格化 NaN 语义（前值或当前值 NaN 时行为未定义） | S2 补注「NaN 参与比较恒 False（不触发）」 |
| F-S2-P045-4 | P3 | S4 exit 后剩余持仓权重语义未裁决（保持 vs 再归一）——P-044 weights 模式允许行和 <1，两语义均可行但结果不同 | S4 补倾向注「exit 后权重保持（现金冗余由 `build_target_positions` 承接）；再归一归 P-047」；DESIGN 确认 |
| F-S2-P045-5 | P3 | §8 I8 计数链 819 未含 U-P045-3 golden 新增实例的 pytest 增量（golden 为参数化实例，新增 case 必增计数） | I8 补 **+N_g** 注（U-P045-3 裁决后并入五文档计数链） |
| F-S2-P045-6 | P3 | 三处订正：① 头部「Step 2 同源」预设被实际执行推翻（本轮即异构 GLM）；② §3.1 row C trailing 计数 2→3（漏 docstring L85，「零逻辑读取」结论不变）；③ §3.2/§7-S5 PRO 专有参数（`tsl_stop`/`tsl_th`）与免费版 1.2.0 实测参数（`sl_stop`/`sl_trail`/`tp_stop`）须区分——对拍范围以免费版为准，激活阈值不在对拍范围（与 U-P045-4 倾向一致） | 三处已回写（头部基座行 / §3.1 / §3.2 升级注 + S5 订正）；U-P045-5 登记理由订正（异构提前成立，维持登记至 Step 10） |

### 13.3 结论

**Step 2 Review pass（2 P2 + 4 P3，全部当轮回写）**——G1-G8 证据链独立重放成立并新增 G9；M-A 裁决经独立复核维持；对拍可行性经隔离 venv 实测证实（`vectorbt==1.2.0` + stop 参数清单）；I3 对拍口径收窄与 OHLC 载体裁决（G9）为 **DESIGN 强制输入**。**准予进入 Step 3 DESIGN**（输入：U-P045-1/2/3/4 + F-S2-P045-1/2）。
