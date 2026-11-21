# RESEARCH：P-051c 策略生命周期（晋级门 + 监控/退役 + 多策略虚拟子账户）

> **批次**: P-051c · **Step 1 调研** · 日期 2026-11-21
> **上游**: [UPGRADE_MASTER_PLAN F5](UPGRADE_MASTER_PLAN.md)（L205 新模块 `core/lifecycle.py`；L207 生命周期流水线；L209 多策略资金分配；L210 验证审计）；[PROGRESS §1.4](PROGRESS.md)（P-051c 行）；[P-051a 已关闭](PROGRESS.md)（`core/volatility.py` + sizing 接线）；[P-051b 已关闭](PROGRESS.md)（`strategies/` 四模板 + registry 接线）
> **代码证据时点**: HEAD `53db4f7`（工作区干净）
> **基线读数**: pytest **1091** / `-k golden` **22** / mypy **119 files 0** / black **240**（P-051b 关闭时实测；**本批未重跑**，Step 9 以当时实测为准）
> **基座**: DeepSeek-V4.1-Flash（Step 2 复审须异构）
> **Step 2 复审**: [REVIEW_p051c_step2](REVIEW_p051c_step2_research.md)（GLM-5.3-Flash 异构 ✅）→ 首轮 4 P1 + 3 P2 + 2 P3，已按 §10.1 全部修复；**二轮复审通过（0 P1，2 P2 + 2 P3 转 Step 3 输入；增值证据 V1-V3 见 REVIEW §6.3）**

---

## 1. 范围与前置

**做**（候选，Step 3 收敛）：

1. 新建生命周期状态机（总纲指名 `core/lifecycle.py`）：阶段枚举 + 迁移规则 + 迁移审计记录；
2. **晋级门**：以 walk-forward 结果为输入，机械化判定「准入 / 退出 / kill」，产出可复核的 `GateDecision`；**前置必须补建 OOS 绩效产出链路**（E3 为空壳，方案见 §4.0）；
3. **监控/退役**：在线指标（滚动 IC 衰减、滑点偏离、回撤超限）→ 降级/退役判定，退役后归档快照；
4. **多策略虚拟子账户**：虚拟现金/持仓、按 allocator 权重预留资金、下单前资金占用校验、冲突仲裁；
5. 端到端测试：四模板（P-051b）经 walk-forward → 晋级门 → 虚拟子账户，全链路可复现；
6. 四文档 + 台账。

**不做**（明确外置）：

- **regime 识别（HMM 2-4 态 / BIC 选态 / 按态切换参数集）→ P-057**（总纲 L274 已单列批次）；本批只留「按态切换」的**接口位**与未决项；
- 真实实盘通道、paper 账户、QMT/CTP 对接 → P-053（本批 paper/灰度阶段只接受**注入证据**，不接真实账户）；
- 截面多空/月差模板 → P-058；
- LLM 策略生成（U-P051b-7 已裁决另立批次）；
- **月度归因**（总纲 L207「复用 `attribution.py`」）：是否纳入本批**待裁决 U-P051c-12**（倾向外置，生命周期侧只留触发位）；
- 改 `core/engine_v2.py` / `core/sizing.py` / `core/stops.py` 主路径（如无必要，零 diff；任何改动须在 DESIGN 逐行列出）；
- `import-linter` 门禁落地（总纲 §6，当前 pyproject 无配置，见 E10）。

**前置事实**：

- **`WalkForwardEngine` 是空壳**（E3，Step 2 复核实锤）：`WalkForwardSplitter` 的切窗逻辑真实可用，但 `run()` 的训练期/测试期**均未跑回测**——`test_result` 的 `total_return` / `sharpe_ratio` 是写死的 `0.0` 占位，`test_config` 创建后从未消费；且 `base_engine_class` 期望 agents 体系 `StrategyEngine`，**四模板的 `BacktestAdapter` 路径进不去**。→ 晋级门所需的 OOS 绩效**没有任何代码能产出**（G2 因此是「判据缺失 + 绩效产出器缺失」双层缺口）；
- 多策略资金分配与假设监控已存在（E6-E8），但**无生命周期语义、无虚拟子账户、无退役**（E9）；
- `strategies/` 四模板已注册并通过端到端（P-051b），生命周期对象可直接以 `strategy_id` 对齐；
- P-053 未交付 → 「paper/灰度/全量」在当前仓库**没有真实载体**，只能以证据注入方式机械化（见 §4.2）。

---

## 2. 代码证据（逐条实读）

| # | 锚点 | 事实 |
|---|------|------|
| E1 | [walk_forward.py](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L45-L220) L45-L84 / L220 | `WalkForwardWindow` + `WalkForwardSplitter`：`train_size` / `test_size` / `purge_gap` / `method`（固定/扩展）/ `step_size`，窗口含 train/test 日期区间与期间判定；`WalkForwardResult`（L220）字段仅 `window_results + agent_period_failures`，**无任何绩效字段** |
| E2 | [walk_forward.py](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L153-L216) L153-L216 | `split()` 生成窗口（含 purge gap、越界停止）；`get_n_splits()` / `get_window()` |
| E3 | [walk_forward_engine.py](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward_engine.py#L31-L70) L31-L70 / L118-L174 / L241 | **⚠ 空壳（Step 2 复核订正）**：`WalkForwardEngine(base_engine_class, splitter, config, window_callbacks)`、`run(agents=None) -> WalkForwardResult`；实际只做「切窗 → `agent.set_period()` 模式标记 → 回调 → 聚合」：`_run_train_period` L134 注释自认「简化处理，实际应该运行完整的训练流程」，`train_result` 为占位 dict；`_run_test_period` L163-L171 `total_return: 0.0 # 占位`、`sharpe_ratio: 0.0 # 占位`，`test_config`（L160）**创建后从未消费**；`_aggregate_results` L221-L238 仅聚合占位值。**不跑任何回测**；`base_engine_class` 期望 agents `StrategyEngine`，与 `BacktestAdapter` 路径不兼容；便捷入口实名 `run_walk_forward_backtest`（L241） |
| E4 | [strategy.py](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L75-L137) L75-L137 | `StrategyMeta`（`strategy_id` / `version` / `param_schema` / `code_hash`）；`StrategyState`（`to_dict` L93 / `from_dict` L102）；`Strategy` Protocol（`meta` + `generate_signals`） |
| E5 | [strategy.py](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L228-L276) L228-L276 | `BacktestAdapter.signals_frame(views, initial_state)` 逐日驱动 → 目标权重矩阵；**本批是否增加状态回写通道见 U-P051c-5** |
| E6 | [registry.py](file:///f:/Coding/Factor_Trading_v3.0/core/registry.py#L81-L115) L81 / L92 / L101-L104 | `register` 遇同名**覆盖并 warning**；`unregister(name)`；`get(name) -> Optional[PluginEntry]`（L101-L104；L110 起为 `create`）；`PluginEntry` 无 `code_hash` / 参数快照字段 |
| E7 | [multi_strategy_engine.py](file:///f:/Coding/Factor_Trading_v3.0/agents/multi_strategy_engine.py#L560-L1016) L560 / L665 / L693 / L728 / L861 | `MultiStrategyEngine`：`run_sequential` / `run_parallel` / `run_vectorized` / `run_with_dynamic_allocation(allocator_type="ftrl", warm_up_days=30)` |
| E8 | [multi_strategy_engine.py](file:///f:/Coding/Factor_Trading_v3.0/agents/multi_strategy_engine.py#L861-L895) L872 / L892 | docstring 明示「权重变化通过调整目标持仓市值实现（**不实际转移资金**）」；分配器策略名**硬编码** `["多头策略","空头策略","中性策略"]` |
| E9 | [strategy_allocator.py](file:///f:/Coding/Factor_Trading_v3.0/agents/strategy_allocator.py#L354-L857) L354 / L374 / L419 / L495 / L536 / L582 / L661 / L745 | `BaseAllocator` + 5 实现（Hedge / FTRL / UCB / Thompson / MeanVariance）；`MetaPolicy.detect_regime`（L682）/ `adapt_parameters`（L710）；`StrategyAllocationManager`（`update` L806 / `get_weights` L841 / `get_report` L845） |
| E10 | [assumption_monitor.py](file:///f:/Coding/Factor_Trading_v3.0/agents/assumption_monitor.py#L36-L788) L36 / L45 / L58 / L80 / L290 / L396 / L520 / L679 / L773 | `AlertLevel` / `AssumptionCheck` / `MonitorState`；**五类监控器**：收益分布（L80）/ 相关性结构（L290）/ 换手（L396）/ 贝叶斯（L520）/ **`UniversalMonitor`（L679，`check` L701）**；`AssumptionMonitorLayer`（L773，`fallback_strategy` 默认 `"equal_weight"`，支持 `"risk_parity"`，L788/L817-L819） |
| E11 | 全仓 grep（`*.py`，排除 docs） | **无 `promote` / `demote` / `retire` / `deactivate` / `paper_trading` 任何生命周期语义**；唯一同名项为 [data.py](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L158) `suspend()`（停牌数据） |
| E12 | [pyproject.toml](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml) | **无 `import-linter` 段**（总纲 §6 的依赖方向门禁尚未落地） |
| E13 | 既有测试 | `test_walk_forward.py` **6** 例、`test_walk_forward_engine.py` **6** 例；`test_strategy_allocator.py` / `test_strategy_allocation_visual.py` / `test_assumption_monitor.py` / `test_integration_full_stack.py`（后者的 `AssumptionMonitorLayer` + `StrategyAllocationManager` 组合是现成的集成范式） |
| E14 | [PROGRESS §1.4](PROGRESS.md) + [DESIGN_p051b §10](DESIGN_p051b_strategy_library.md) | 承接项：**U-P051b-15**（`BacktestAdapter` 状态回写，触发条件 = 「P-051c 多策略虚拟子账户立项」→ **本批已触发**）；**O-P051a-1**（`SizingState` 持久化，若 P-051c 需持久化则升级 `to_dict/from_dict`）；**O-P051a-2**（overlay vol 腿单位口径，仍 pending）；**U-P044-3**（引擎内循环重构，触发条件改为「同账户 N 策略并行且需共享现金/保证金」→ 本批若做虚拟子账户则**再次触发**，须裁决） |

---

## 3. 缺口清单

| ID | 缺口 | 证据 | 严重度 |
|----|------|------|--------|
| **G1** | 无生命周期状态机：无阶段枚举、无迁移规则、无迁移审计 | E11 | 核心 |
| **G2** | 晋级门判据未机械化，且**绩效产出器缺失（双层）**：① `WalkForwardEngine` 不跑回测——`train_result` 为占位 dict、`test_result` 的 `total_return/sharpe_ratio` 写死 `0.0`、`test_config` 创建后未消费（E3）；② 无准入/退出阈值、无 IS-OOS 衰减度量 | E3 / E1（`WalkForwardResult` 无绩效字段） | 核心 |
| **G3** | paper/灰度/全量阶段无载体：P-053 未交付，仓库内无 paper 账户 | §1 前置事实 | 核心 |
| **G4** | 无虚拟子账户：`run_with_dynamic_allocation` 明确「不实际转移资金」；无虚拟现金/持仓、无资金占用校验、无冲突仲裁 | E7 / E8 | 核心 |
| **G5** | 无退役与归档：无退役判据、无归档快照（可复现） | E11 | 高 |
| **G6** | 注册表不可追溯：`PluginEntry` 无 `code_hash` / 参数快照；同名注册会**静默覆盖**（仅 warning） | E6 | 高 |
| **G7** | `BacktestAdapter` 无状态回写：多策略/持仓级状态无法回传（U-P051b-15 已触发） | E5 / E14 | 中 |
| **G8** | 监控未接生命周期：五类 Monitor（含 `UniversalMonitor`）与 `AssumptionMonitorLayer` 存在，但 `AlertLevel` 与「降级/退役」之间无映射 | E10 | 中 |
| **G9** | **IC 计算设施未确认**：总纲 L207 要求「滚动 IC 衰减」判据，但 `attribution.py` 是否提供滚动 IC 未核实（U-P051c-14） | 总纲 L207；§2 未覆盖 | 高 |

---

## 4. 方案矩阵（Step 3 裁决对象）

### 4.0 G2 前置：OOS 绩效产出器（Step 2 复审 F-R1 新增）

**事实**：`WalkForwardEngine` 不跑回测（E3），`WalkForwardResult` 也无绩效字段（E1）——因此「walk-forward → 晋级门」之间缺一个**绩效产出环节**。

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | `WalkForwardSplitter`（纯切窗，已可用）+ `BacktestAdapter.signals_frame`（P-051b 端到端已验证）+ 新建**轻量逐窗绩效计算**（夏普/最大回撤/换手/IC），输出 `StageEvidence` | 三段均为已验证组件；不改 `WalkForwardEngine`；纯函数可测；与 `core/engine_v2` 的成交/成本口径一致性须在 DESIGN 说明 |
| B | 补全 `WalkForwardEngine`（让它跑真实回测） | 它面向 `agents.StrategyEngine`（`base_engine_class`），与 `BacktestAdapter` 路径不兼容；改造面大、回归风险高 |
| C | 只做单段 OOS 切分 | 不满足总纲 L207「walk-forward 回测」语义 |

**倾向 A**；`core/metrics.py` **已确认存在**（二轮复审 V1），轻量绩效计算**优先复用**它，勿另写；IC 计算复用 `strategy_evaluation/stats.py` 的 `calculate_ic`（二轮复审 V3，依赖方向 Step 3 核实）。

### 4.1 G1/G2：生命周期状态机的归属与形态

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | `core/lifecycle.py` 纯函数核：`LifecycleStage` 枚举 + `GateCriteria` + `StageEvidence` + `evaluate_gate()` / `transition()`（无 I/O、无 logging、无全局态） | 与总纲 L205 一致；依赖方向天然合规（`core` 不依赖 `agents`）；可单测、可序列化 |
| B | 放 `agents/lifecycle.py` 并复用 `AssumptionMonitorLayer` | 违反总纲指名的 `core/lifecycle.py`；`core→agents` 会被 §6 依赖门禁禁止（虽然门禁未落地） |
| C | 扩展现有 `MultiStrategyEngine` | 把判定逻辑塞进回测循环，不可单测、不可复用于 live |

**倾向 A**；`agents/` 侧只做**适配器**（把 `AssumptionMonitorLayer` 的 `AlertLevel` 翻译成 `StageEvidence`），不承载判定。

### 4.2 G3：无实盘通道时 paper/灰度如何机械化

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | 阶段推进只消费**注入的证据对象**（`StageEvidence`），证据来源可为：walk-forward OOS 结果 / 手工回放的 paper 记录 / 未来 P-053 的真实账户 | 本批零依赖实盘；判据本身完全可测；P-053 交付后只需换证据来源 |
| B | 本批不实现 paper/灰度，只做 backtest → live | 与总纲 L207 的「paper≥1月→小资金灰度→全量」冲突 |
| C | 用 `BacktestEngineV2` 重跑一段区间冒充 paper | 语义造假（回测≠paper），禁止 |

**倾向 A**，并在 DESIGN 明确 `StageEvidence.source` 字段（`"walk_forward"` / `"paper_record"` / `"live_account"`），paper 阶段要求 `source=="paper_record"` 且 `paper_days>=20 && paper_trades>=50`（双条件，F-R2b-3 同步）。

### 4.3 G4：多策略虚拟子账户的范围

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | `core/lifecycle.py` 内或同级新增**纯账本** `VirtualAccount`：`cash` / `positions` / `reserved`；`allocate(weights)`、`try_reserve(notional) -> bool`、`release()`、`snapshot()`；冲突仲裁 = 优先级 + 公平队列（FIFO 同级） | 纯函数可测；不侵入引擎下单路径；与总纲 L209 对齐 |
| B | 直接改造 `MultiStrategyEngine` 的资金分配循环 | 改动面大、回归风险高；且它基于 `agents.StrategyEngine` 自研循环，与 `core.engine_v2` 双路径并存（已知技术债） |
| C | 只做分配权重，不做资金占用校验 | 不满足总纲 L209「下单前校验资金占用」 |

**倾向 A**；**明确不接 `core/engine_v2.py` 下单路径**（本批），只交付可被 P-053 调用的账本与校验函数。

### 4.4 G5/G8：退役与监控映射

| 方案 | 做法 | 评价 |
|------|------|------|
| **A（推荐）** | `evaluate_gate()` 统一处理「晋级」与「降级/退役」：输入 `StageEvidence`，输出 `GateDecision(action, reasons)`；`action ∈ {promote, hold, demote, retire}`；kill criteria 优先级最高 | 单一判据入口，避免两套阈值 |
| B | 晋级与退役各自独立模块 | 阈值重复、易漂移 |

### 4.5 G6/G7：追溯与状态回写

| 项 | 方案 | 评价 |
|----|------|------|
| G6 | **不修改** `core/registry.py`；在 `lifecycle` 侧维护 `StrategyFingerprint(strategy_id, version, param_snapshot, code_hash)`，从 `StrategyMeta` 取值 | 零回归；registry 的覆盖语义保留（P-051b C3 已锁定）。**⚠ 与总纲 L205 指名 `core/strategy_registry.py`（版本化注册）存在偏差，须在 DESIGN 显式声明（U-P051c-13）** |
| G7 | U-P051b-15：**本批不改 `BacktestAdapter`**，虚拟子账户所需持仓状态由 `LifecycleManager` 自行维护（`StrategyState.positions` 只读已够） | 避免动 P-044 契约；如 Step 3 判定必须回写，再走独立小批 |

---

## 5. 规格草案（Step 3 定稿）

### 5.1 阶段与迁移

```
draft ──submit──> backtest ──promote──> paper ──promote──> gray ──promote──> live
                                          ▲                │                 │
                                          └──── demote ────┴──── demote ─────┘
                                          │
              paper ── IC 持续低于阈值 / 回撤超限 ──> retired（归档，终态）

paper → gray 前置：paper_days >= 20 且 paper_trades >= 50
```

- 迁移函数纯函数：`transition(current, decision, evidence) -> (next, TransitionRecord)`；
- **退役唯一入边 = `paper`**：总纲 L207 原文为「退役（IC 持续低于阈值/回撤超限→**降paper**→归档可复现）」——`backtest` / `gray` / `live` 均须**先 `demote` 到 `paper`**，再在 paper 阶段判定 `retire`；禁止任何阶段直跳 `retired`（F-R2 订正）；
- 非法迁移（如 `draft → live`、`live → retired` 直跳）→ `LifecycleError`（fail-fast）；
- `retired` 为终态，只允许 `archive()`（导出快照），不允许回到任何阶段。

### 5.2 判据（初稿，Step 3 定稿）

| 判据 | 字段 | 初值 | 说明 |
|------|------|------|------|
| 最小 OOS 样本 | `oos_days` | ≥ 60 | 低于则 `hold`（样本不足） |
| 晋级最低夏普 | `sharpe_oos` | ≥ 1.0 | 与 `sharpe_is` 联合看 |
| IS-OOS 衰减 | `sharpe_oos / sharpe_is` | ≥ 0.5 | 防过拟合（P-051b §13.2 的离线准则） |
| 最大回撤 | `max_drawdown` | ≤ 0.20 | 触发 kill |
| 换手 | `turnover` | ≤ 0.30/日 | 触发 hold |
| paper 时长 | `paper_days` | ≥ 20 | 交易日（总纲 L207「≥1月」） |
| paper 成交笔数 | `paper_trades` | ≥ 50 | 与时长**并列**（§11.2）。**F-R6**：50 笔为社区经验值且语境偏高频；A股日频低频策略可改比例式 `paper_trades_per_year`，Step 3 定 |
| 滚动 IC | `ic_min`（+ `ic_lookback`） | Step 3 定 | 总纲 L207「**IC 持续低于阈值**」→ 退役判据；计算设施来源见 U-P051c-14 |
| 资金门槛 | `capital` | 灰度 → 全量 ≥ 阈值 | Step 3 定 |

**所有权重与阈值必须可配置**（`GateCriteria` dataclass），并且**禁止硬编码在判定函数体**。

### 5.3 虚拟子账户（草案）

```python
@dataclass(frozen=True)
class VirtualAccount:
    strategy_id: str
    cash: float
    positions: dict[str, float]      # code -> 市值
    reserved: float                  # 已预留未成交

    def allocate(self, weight: float, total: float) -> "VirtualAccount": ...
    def try_reserve(self, notional: float) -> tuple["VirtualAccount", bool]: ...
    def snapshot(self) -> dict[str, Any]: ...
```

不变式：`cash + sum(positions) + reserved == total`（浮点容差 1e-9）；`reserved >= 0`；退役时 `snapshot()` 落盘后账户置零。

**语义厘清（F-R9）**：`allocate()` 是**额度层**（调整 sleeve 目标资金），`try_reserve()` 是**订单层**（锁定待成交资金，只能从 `cash` 划出并计入 `reserved`），两者**不重复记账**。

**对账边界（F-R7）**：本批 `VirtualAccount` 是 per-策略 sleeve 账本；与引擎侧**共享现金账户**（总纲 L197「先卖后买 call_seq + 共享现金账户」）的实际现金流对账，属 **P-053 接线范围**，本批不假设 sleeve 与总账实时一致，也不实现跨 sleeve 资金调拨。

---

## 6. 不变式（草案）

| ID | 不变式 |
|----|--------|
| I1 | 生命周期判定为**纯函数**：同输入必同输出，无 I/O / 无 logging / 无全局态 |
| I2 | 阶段只能沿 §5.1 有向图迁移；`retired` 为终态 |
| I3 | 晋级必须同时满足全部 `GateCriteria`；任一 kill criteria 命中则**优先** `retire` |
| I4 | `GateDecision` 必须携带 `reasons: tuple[str, ...]`（可审计，禁止只给布尔） |
| I5 | 虚拟子账户资金守恒：`cash + Σpositions + reserved == total` |
| I6 | 退役后账户清零且快照可 JSON 往返（对齐 U-P051b 的序列化纪律） |
| I7 | 本批对 `core/engine_v2.py` / `core/sizing.py` / `core/stops.py` **零 diff**（如破例须 DESIGN 逐行列出并说明理由） |
| I8 | 既有 golden 22 条**零重录** |
| I9 | **迁移重放**：任意 `TransitionRecord` 前缀重放，必达同一 `(stage, account_states)`（总纲 L210「任意时点可重放复算」；F-R5 新增） |
| I10 | `reserved` 只能从 `cash` 划出；`allocate` 与 `try_reserve` 不重复记账（F-R9 新增） |

---

## 7. DoD 与读数目标（待 Step 3 / Step 5 定稿）

| 项 | 目标 |
|----|------|
| 新模块 | `core/lifecycle.py`（+ 可选 `core/virtual_account.py`，Step 3 定）；**+ OOS 绩效产出器**（§4.0 A 案，归属 Step 3 定） |
| 用例 | 覆盖 **G1-G9** 全部缺口，每缺口 ≥ 2 例；预计 **+40~60** 例（含绩效产出器用例，Step 3 精确化） |
| pytest | 基线 **1091** → 目标 ≥ **1131**（Step 3 定稿后精确化；含 §4.0 绩效产出器用例） |
| golden | 22 条零重录 |
| mypy | 目标目录不变（`core` 等），新增文件 0 error |
| black | `black --check .` 保持 unchanged（当前 240 + 新增文件数） |
| 可复现 | 生命周期状态机 `to_dict/from_dict` 往返 + 重放一致 |

---

## 8. 未决项（Step 2 复审 → Step 3 裁决；标 ★ 者需用户裁决）

| ID | 未决 | 备选 | 倾向 |
|----|------|------|------|
| **U-P051c-1 ★** | 生命周期状态机归属 | A `core/lifecycle.py`（总纲指名）/ B `agents/` | **A** |
| **U-P051c-2 ★** | 无实盘通道时 paper/灰度如何机械化 | A 证据注入 / B 本批不做 paper / C 回测冒充 | **A**（`source` 区分来源；**按 §11.2 修订**：paper 判据改双条件 `paper_days>=20 && paper_trades>=50`，且 DESIGN 须标注「工程选择，非行业最佳实践」） |
| **U-P051c-3 ★** | 多策略虚拟子账户是否本批做 | A 纯账本 + 校验（不接引擎）/ B 改造 `MultiStrategyEngine` / C 不做 | **A** |
| **U-P051c-4 ★** | 是否顺带解 U-P044-3（引擎内循环重构） | A 不做（维持 P-051b 裁决）/ B 本批最小化下沉 | **A**（虚拟子账户不接引擎即可，无需重构；**锚点 R18 一手**：Parnas 信息隐藏准则支持「新增独立模块」而非改主循环；见 §11.8.1） |
| **U-P051c-5** | `BacktestAdapter` 状态回写（U-P051b-15） | A 本批不改 / B 加 `take_extras()` 钩子 | **A** |
| **U-P051c-6** | `SizingState` 持久化（O-P051a-1） | A 本批需要 → 升级 `to_dict/from_dict` / B 仍不需要 | Step 3 按实际调用判定 |
| **U-P051c-7** | 退役归档落盘位置 | A 工作区外（不入仓）/ B 仓库内 `reports/lifecycle/`（gitignore） | **A**（与既有 golden/报告纪律一致） |
| **U-P051c-8** | regime 接口预留程度 | A 仅留 `regime: str | None` 字段 + 注释 / B 实现 HMM | **A**（HMM 归 P-057） |
| U-P051c-9 | 判据阈值来源 | A 初值 + 可配置 / B 校准后再定 | **A**（阈值不进入正确性断言，只进入迁移规则测试） |
| **U-P051c-10** | DSR/PBO 是否本批实现 | A 只留 `GateCriteria` 预留字段（**不写空实现**）/ B 本批实现 DSR+PBO | **A**（§11.2 R4/R5：裸夏普偏乐观，但 DSR/PBO 需多重试验记录，属增强项） |
| **U-P051c-11** | `GateCriteria` 的 readiness/value 分组命名 | A 复用 `AssumptionCheck` 的既有语义（字段待 Step 3 核对）/ B 独立命名 | Step 3 定（§11.2 R3） |
| **U-P051c-12** | 月度归因是否纳入本批（总纲 L207） | A 外置（仅留触发位）/ B 本批交付 | **A**（`attribution.py` 已存在；**锚点 R20/R21 一手**：Brinson 为**单期**模型、Menchero 证明多期链接是独立工作量 → 外置成本论；见 §11.8.2） |
| **U-P051c-13** | 版本化注册：总纲 L205 指名 `core/strategy_registry.py` vs lifecycle 侧指纹 | A 指纹（不改 registry）/ B 新建版本化注册表 | **A** + DESIGN 声明偏差。**锚点强化（R14）**：MLflow 官方已**弃用 Model Stages**（改用 tags/aliases），即「把生命周期阶段嵌进注册表」是业界已退场的路线；其版本最佳实践为**单调 build ID + git commit + artifact digest**，与 A 案指纹字段同构 |
| **U-P051c-14** | 滚动 IC 计算设施来源（退役判据依赖） | A 复用 `strategy_evaluation/stats.py::calculate_ic` / B 绩效产出器内新写 | **A**（二轮 V3 实锚；依赖方向 Step 3 核实） |
| **U-P051c-15** | OOS 绩效产出器方案（§4.0） | A Splitter + BacktestAdapter + 轻量逐窗绩效 / B 补全 `WalkForwardEngine` / C 单段 OOS | **A** |
| **U-P051c-16** | Gate 决策枚举与失败路径（二轮 F-R2b-1/2） | A **Go/Kill/Hold/Recycle 四值**（对齐 Stage-Gate 官方），`kill` 仅在 `paper` 及其后生效、且先 `snapshot()`；`recycle → draft`（版本号递增，不复用旧指纹）/ B 三值 `promote/hold/kill` | **A**（R15 官方四决策；`recycle` 正是「打回重做」，可同时解 I3 矛盾与 backtest 失败路径） |

---

## 9. 步骤表

| 步 | 动作 | 出口条件 |
|----|------|----------|
| 1 | 调研（本文） | 本文落盘 |
| 2 | 异构复审 | 0 P1 |
| 3 | DESIGN | ✅ 完成（2026-11-21）：[DESIGN_p051c](DESIGN_p051c_strategy_lifecycle.md)（D1-D12 / I1-I11 / 20 项裁决定案 + 新增 U-P051c-17/18/19/20 / ≈53 用例、pytest ≈1144）；**Step 4 首轮 1 P1+2 P2+4 P3 → 7 项已修复 → 二轮 3 P1+1 P3（N-4 重估）→ 已全部修复 → **三轮定点核验通过（2026-11-21，GLM：4 项回执落盘一致 + 行号重验 4 组全真 + 2 P3 同步残留已修正），Step 4 关闭，待 Step 5 IMPL** |
| 4 | 异构复审 + 收敛 | 0 P1 |
| 5 | IMPL（逐处代码） | ✅ 完成（2026-11-21）：[IMPL_p051c](IMPL_p051c_strategy_lifecycle.md)（三新模块逐处代码 + C-1..C-12 实施口径 + 53 用例映射 + 6 项 DESIGN 补齐，**Step 6 已全部复核并修复**）；出口：每文件伪码可执行 |
| 6 | 异构复审 + 收敛 | ✅ 完成（2026-11-21）：首轮 GLM 复核 DeepSeek IMPL **1 P1+4 P2+3 P3**（F-I1 HOLD/LEGAL、F-I2 零窗口、F-I3 GO 必败、F-I4 D1 矛盾、F-I5 IC 口径 + P3×3）→ 复核 8/8 属实 → 8/8 修复（含 DESIGN 回写：D1 例外脚注 / I1 例外 / D6.2 临时目录脚注 / §3 三字段）→ **二轮异构复审（GLM）：机制层 0 P1（F-I1 闭环成立、窗口算术重算吻合、三处回写无冲突、IC 口径等价 + 连带新断言 5 项全验）+ 测试设计 1 P2+2 P3（O-2-1 E 组 GO 仍不可达：IC 门槛 ≥10 vs 2 标的 fixture 结构性冲突 → 已修 12 标的；O-2-2 else 分支语义坑；O-2-3 笔误，均顺手修正）→ Step 6 关闭**；用例仍 53、pytest 1144；详见 [REVIEW §6-§7](REVIEW_p051c_step6_impl.md) |
| 7 | CHECKLIST | ✅ 完成（2026-11-21）：[CHECKLIST_p051c](CHECKLIST_p051c_strategy_lifecycle.md)——**M10 + T7 + C6 + I11 + D12 = 46 项**，全部 `[待 Step 9]`（RULE-1 禁预填）；基线 @`53db4f7` pytest 1091 / golden 22 / mypy 119·0 / black 240；目标 1144 / 122 files / 247 |
| 8 | 一致性检查 | ✅ 通过（2026-11-21，GLM）：**20 项裁决 §0 齐全（L14-L33）/ §7 O11·≈53·≈1144 / 组数 L14+G10+R5+O11+A10+E3=53 四文档一致 / StageEvidence 三字段 D§3↔IMPL C-5↔CHECKLIST M1 一致 / run_engine+evaluate_strategy 签名一致 / D6.2 段公式与 IMPL _segment 等价 / CHECKLIST M-T-C-I-D 与 DESIGN D/I 组对齐 / mypy 122·black 247 口径一致**；4 项 P3 修正：R-1 E② 定死循环断言（1 收集项，保 53/1144，禁 @parametrize 漂移至 1147）/ R-2 删 lifecycle 侧死常量 EPS_SHARPE（oos 侧消费，lifecycle 不用）/ R-3 DESIGN 头部状态链更新 + D10 补注 draft red→HOLD（IMPL §3.1 定案回写）/ R-4 RESEARCH Step 5 行滞后清理。四文档状态同步完成，待 Step 9 |
| 9 | TDD + 门禁 | ✅ 完成（2026-11-21）：三新模块 `core/{lifecycle,oos,virtual_account}.py` + 四测试文件落盘，**53 用例全绿**（lifecycle 29 / oos 11 / virtual_account 10 / end_to_end 3）；门禁实测 **pytest 1144 / `-k golden` 22 零重录 / mypy 122 files 0 / black 247 unchanged / tests 124 / core 48**；[CHECKLIST](CHECKLIST_p051c_strategy_lifecycle.md) 46 项全部 ✅（`[待 Step 9]` 清零）；M10 零改动清单 `git diff --stat` 空。**未提交，待 Step 10 授权** |
| 10 | 提交 + CI | ✅ 完成（2026-11-21）：提交 `45e133b`（feat(P-051c)：15 files +4184/−1，`53db4f7..45e133b` 已推送）→ CI run `44895295314` **四 job 全绿**（lock-check + test 3.10/3.11/3.12）。**批次关闭** |

---

## 10. 结论

1. **P-051c 的核心不是「再写一个回测」，而是把已有三块能力用一条可审计的状态机串起来**——但 Step 2 复核实锤：**切窗器（`WalkForwardSplitter`）与分配器真实可用，`WalkForwardEngine` 的「跑」是空壳**（`test_result` 写死 0.0）。因此缺的不只是判据与状态，还缺 **OOS 绩效产出器**（§4.0）；
2. **最大风险在 G3（无实盘载体）**：若强行在本批实现 paper/灰度，会造出「回测冒充 paper」的语义假象；采用**证据注入**是唯一既能机械化又不失真的路径；
3. **第二大风险在 G4（虚拟子账户）**：`MultiStrategyEngine` 的双路径结构使「改造它」代价很高，本批应交付**纯账本**，把接线留给 P-053；
4. **U-P044-3 不必在本批解**：虚拟子账户不进入引擎主循环即可满足总纲 L209 的「下单前校验」语义（校验函数由调用方在 P-053 使用）；
5. **Step 2 二轮复审已通过（0 P1）**：首轮 9 项修复全部核验落盘；7 项待裁决的锚点充足度见 **§11.7**（其中 U-P051c-13 与 16 获官方级锚点并已细化推荐）。

---

## 10.1 Step 2 复审修复记录（F-R1..F-R9）

| 复审项 | 严重度 | 修复动作 | 落点 |
|--------|--------|----------|------|
| F-R1 E3 空壳 / 晋级门链路断层 | P1 | E1/E3 按实读重写；G2 改为双层缺口；新增 **§4.0 绩效产出器** 方案矩阵（A/B/C）；新增 **G9**、**U-P051c-15**；§7 DoD 同步 | §1 前置事实、§2 E1/E3、§3、§4.0、§7、§8 |
| F-R2 退役语义 + IC 判据缺失 | P1 | §5.1 状态图重画：**退役唯一入边 = paper**，任何阶段先 demote 到 paper；§5.2 增 `ic_min` / `ic_lookback`；新增 **U-P051c-14** | §5.1、§5.2、§8 |
| F-R3 月度归因未裁决 | P1 | §1「不做」清单显式列出；新增 **U-P051c-12** | §1、§8 |
| F-R4 `strategy_registry.py` 指名未对照 | P1 | §4.5 G6 行加偏差警示；新增 **U-P051c-13**（要求 DESIGN 显式声明偏差） | §4.5、§8 |
| F-R5 重放未升为不变式 | P2 | 新增 **I9** 迁移前缀重放不变式 | §6 |
| F-R6 `paper_trades>=50` 语境错配 | P2 | §5.2 标注「社区经验值、偏高频」，给出比例式候选；§11.2 净影响同步 | §5.2、§11.2 |
| F-R7 sleeve 与共享现金对账边界 | P2 | §5.3 新增「对账边界」段（对账归 P-053，本批不假设实时一致） | §5.3 |
| F-R8 三处转录错误 | P3 | E3 改名 `run_walk_forward_backtest`；E10 改「五类监控器 + `UniversalMonitor` L679」；E6 `get()` 改 L101-L104 | §2 |
| F-R9 补记与语义厘清 | P3 | E1 补 `WalkForwardResult` L220（无绩效字段）；§5.3 厘清 `allocate`（额度层）与 `try_reserve`（订单层）不重复记账；新增 **I10** | §2、§5.3、§6 |

**修复后未决项**：U-P051c-1..15（其中 ★4 项待用户裁决；新增 12/13/14/15 中 12/13 亦建议用户确认）。

---

## 11. 四项裁决的外部锚点（2026-11-21 补充调研）

> **核实状态图例**：✅ = 已读官方文档/原文片段，结论可直接支撑；⚠️ = 仅读到摘要/二手转述，结论方向可信但**细节未逐字核实**；❌ = 未取得原文（本文未使用）。
> **纪律**：社区博客与商业供应商内容一律标 ⚠️，不得作为「标准」引用；学术结论只用于**判据设计方向**，不用于断言具体数值阈值。

### 11.1 U-P051c-1：状态机归属（`core` 纯函数核 vs `agents`）

| 锚点 | 内容 | 状态 | 对本项的含义 |
|------|------|------|--------------|
| **Functional Core / Imperative Shell**（Gary Bernhardt, *Boundaries*, SCNA 2012） | 业务判定放在纯函数核（无 I/O、无需 mock、可确定性测试），I/O 与副作用收敛到薄外壳 | ⚠️ 二手（多个工程博客一致转述，未取得原演讲文本） | 生命周期判定（阶段迁移/判据/仲裁）应全部落在纯函数核；`assumption_monitor` 的 `AlertLevel → StageEvidence` 翻译属外壳 |
| **QuantConnect LEAN Algorithm Framework**（官方文档 v2） | 官方把算法框架拆为 **Universe → Alpha → PortfolioConstruction → Execution** 四层；Engine 统一管理组合与数据 | ✅ 官方文档（overview / portfolio-construction / algorithm-engine 页） | 生命周期属于「PortfolioConstruction 之上的治理层」，既不属于 Alpha（信号）也不属于 Execution（下单）→ 独立纯函数模块合理 |
| **LEAN `IPortfolioConstructionModel` 系列**（类参考） | 组合构建模型接收 Insight、输出 PortfolioTarget，可插拔（如 `AccumulativeInsightPortfolioConstructionModel`） | ✅ 官方类参考 | 佐证「治理/分配逻辑应与信号生成解耦，并以可替换组件形式存在」 |

**净影响**：维持原推荐 A（`core/lifecycle.py` 纯函数核），并明确 `agents/` 只做适配器，不做判定。

### 11.2 U-P051c-2：paper/灰度阶段的机械化与判据

| 锚点 | 内容 | 状态 | 对本项的含义 |
|------|------|------|--------------|
| **Stage-Gate® 模型**（Cooper；stage-gate.com 官方概览 + PDMA 2026 官方版） | 阶段末尾设 **Gate = go/kill + 资源配置决策点**；判据分两类：**readiness（就绪度）** 与 **business value（价值）** | ✅ 官方概览 + ⚠️ 2026 版博客 | 晋级门不是「自动通过」而是**显式决策点**；`GateCriteria` 应分「就绪度」（样本量、paper 天数、成交笔数）与「价值」（OOS 夏普、回撤、衰减）两组 |
| **The Deflated Sharpe Ratio**（Bailey & López de Prado, JPM 2014；SSRN 2460551） | 对多重试验与收益非正态做修正，给出真实 SR 超过阈值的概率 | ✅ SSRN/Crossref 元数据 + 原文 PDF 片段 | 裸 `sharpe_oos` 阈值天然乐观；本批**先接可插拔判据接口**，DSR 作为增强项（U-P051c-10），不阻塞本批 |
| **The Probability of Backtest Overfitting（CSCV）**（Bailey, Borwein, López de Prado, Zhu） | 用组合对称交叉验证估计「样本内最优在样本外排名下滑」的概率 | ⚠️ 摘要/PDF 片段 | 与 IS-OOS 衰减同源；本批用**轻量衰减比** `sharpe_oos/sharpe_is`，PBO 全量计算留增强项 |
| **Backtesting**（Harvey & Liu, JPM 2015-10-31） | 行业惯例是「回测 Sharpe 砍半」；论文给出多重检验下的 haircut 与显著性门槛 | ✅ 期刊页元数据 + CFA Digest 摘要 | `ρ_min = 0.5`（OOS/IS ≥ 0.5）有**行业惯例级**支撑，但属经验值，必须在 DESIGN 标为「可配置默认值」而非定理 |
| **paper trading 时长社区实践**（x3algo；TradingBotExperts；Arthalab；Backtrex） | 最低 2 周~30 天；较好 60-90 天；并普遍要求 **30-100 笔成交**才具统计意义 | ⚠️ 全部为商业博客/供应商内容，**无权威统一标准** | 总纲 L207「paper≥1月」位于社区区间下沿、可接受；但**单一时长不足**，应改为**双条件**（见下） |

**净影响（对原推荐的修订）**：
1. paper 阶段判据由单一 `paper_days >= 20` 改为 **`paper_days >= 20` 且 `trades >= 50`**（双条件，均可配置）——外部实践一致强调「成交笔数」；但 R7 全部为**商业博客**且语境偏高频，**A股日频低频策略须改用比例式**（F-R6）；
2. `GateCriteria` 拆为 `readiness` / `value` 两组（对齐 Stage-Gate 的 readiness vs business value）；
3. **证据注入**（`StageEvidence.source`）**没有直接外部锚点**——主流平台都有真实 paper 账户（LEAN/IB 等）。因此必须在 DESIGN 中明确标注：「这是本仓库在 P-053 未交付约束下的**工程选择**，不是行业最佳实践」，并在 P-053 交付后把 `source="paper_record"` 切到真实账户；
4. 新增 **U-P051c-10**：DSR/PBO 可插拔判据——本批**只保留 `GateCriteria` 中的预留字段与文档承诺，不写空实现、不写 `NotImplemented` 路径**，避免"假装支持"。

### 11.3 U-P051c-3：多策略虚拟子账户（纯账本 + 校验）

| 锚点 | 内容 | 状态 | 对本项的含义 |
|------|------|------|--------------|
| **基金 sleeve 结构**（SEC 备案 N-1A/497K：Columbia Funds、Janus 等） | 基金资产按「sleeve」分配给不同 subadviser，各自独立管理一部分资产 | ✅ 监管备案文件片段 | 「虚拟子账户 = sleeve」是行业标准记账结构；每 sleeve 独立核算、合计守恒 |
| **Interactive Brokers Model Portfolios**（官方） | 顾问设定**目标百分比分配**，把客户资金投入一个或多个模型；另有「按股数/百分比/比率」的批量分配 | ✅ 官方产品页 | 与「allocator 权重 → 子账户资金」映射一致；分配与记账应分离（模型给权重，账本记资金） |
| **Online Learning of Portfolio Ensembles with Sector Exposure Regularization**（Uziel & El-Yaniv, arXiv:1604.03266, 2016） | 用在线凸优化控制**对底层算法的资金分配**，对 best-in-hindsight 集成有 **log regret** | ✅ arXiv 元数据 + 摘要 | 仓库既有 `StrategyAllocationManager`（FTRL/UCB 等）有学术对应物；但「分配权重」**不等于**「资金账本」，两者须解耦 |
| `MultiStrategyEngine.run_with_dynamic_allocation`（本地 E8） | docstring 自认「不实际转移资金，仅调整目标持仓市值」 | ✅ 本地代码 | 证明「改造它来承载账本」是错位：它本就不是账本 |

**净影响**：维持推荐 A（纯账本 + `try_reserve` 校验），并明确三条语义：**sleeve 独立核算 / 合计守恒 / 与 allocator 权重解耦**。不改造 `MultiStrategyEngine`。

### 11.4 U-P051c-4：是否顺带解 U-P044-3（引擎内循环重构）

| 锚点 | 内容 | 状态 | 对本项的含义 |
|------|------|------|--------------|
| **Intelligent Trading Architecture**（Wiley, *Concurrency and Computation*, 2016） | 明确把交易问题分解为 **signal generation / trading / operation** 三个子问题 | ⚠️ 摘要级 | 「信号生成」与「资金/执行」分离是主流架构；共享现金属于 trading/operation 层，可独立演进 |
| **`py-backtesting-lib` 管线** | `Strategy → Signal → Money Manager → Order → Broker` 同步事件循环 | ⚠️ 第三方库文档 | Money Manager（资金管理）是**独立管线环节**，不要求与信号层同循环重构 |
| **Backtest–live parity / shared core 模式**（社区工程实践） | 抽出共享策略核心，回测与实盘只替换外围（数据源、下单通道） | ⚠️ 社区博客 | 支持「核心可复用、外围可替换」，而非「重写主循环」 |
| **The 10 Reasons Most Machine Learning Funds Fail**（López de Prado, GARP 白皮书） | 研究流程治理类错误（Sisyphus 范式等）是主要失败来源 | ⚠️ 白皮书 PDF 片段 | 仅作**间接**支持：治理与流程（本项目即生命周期层）比「重写引擎」优先级更高；**不**作为虚拟子账户的直接依据 |

**净影响**：维持推荐 A（本批不解 U-P044-3）。虚拟子账户以纯账本形式交付，校验函数由 P-053 在真实下单路径调用；引擎内循环保持零 diff。

### 11.5 引用清单（可复核）

| # | 文献/文档 | 类型 | 状态 | 支撑 |
|---|-----------|------|------|------|
| R1 | Bernhardt, *Boundaries*（SCNA 2012） | 会议演讲（二手转述） | ⚠️ | U-P051c-1 |
| R2 | QuantConnect LEAN Algorithm Framework 官方文档 v2 | 官方文档 | ✅ | U-P051c-1 |
| R3 | Cooper, Stage-Gate® 官方概览 + PDMA 2026 版 | 方法论官方 | ✅/⚠️ | U-P051c-2 |
| R4 | Bailey & López de Prado, *The Deflated Sharpe Ratio*, JPM 2014（SSRN 2460551） | 期刊论文 | ✅ 元数据 + PDF 片段 | U-P051c-2 |
| R5 | Bailey, Borwein, López de Prado, Zhu, *The Probability of Backtest Overfitting*（CSCV） | 论文 | ⚠️ 摘要 | U-P051c-2 |
| R6 | Harvey & Liu, *Backtesting*, JPM 2015-10-31 | 期刊论文 | ✅ 元数据 + Digest 摘要 | U-P051c-2 |
| R7 | 社区 paper trading 时长实践（x3algo / TradingBotExperts / Arthalab / Backtrex） | 商业博客 | ⚠️ | U-P051c-2 |
| R8 | SEC 备案 N-1A/497K（Columbia / Janus，sleeve 结构） | 监管文件 | ✅ 片段 | U-P051c-3 |
| R9 | Interactive Brokers Model Portfolios 官方页 | 官方产品文档 | ✅ | U-P051c-3 |
| R10 | Uziel & El-Yaniv, *Online Learning of Portfolio Ensembles…*, arXiv:1604.03266 | 预印本 | ✅ 元数据 + 摘要 | U-P051c-3 |
| R11 | *Intelligent Trading Architecture*, Wiley CCPE 2016 | 期刊论文 | ⚠️ 摘要 | U-P051c-4 |
| R12 | `py-backtesting-lib` / backtest-live parity 工程实践 | 第三方文档/博客 | ⚠️ | U-P051c-4 |
| R13 | López de Prado, *The 10 Reasons Most ML Funds Fail*, GARP 白皮书 | 白皮书 | ⚠️ 片段 | U-P051c-4（间接） |
| R14 | MLflow Model Registry 官方文档（*Model Stages* 已标 **Deprecated**；版本最佳实践为单调 build ID + git commit + artifact digest） | 官方文档 | ✅ 片段 | U-P051c-13 |
| R15 | Stage-Gate 官方：Gate 输出为 **Go / Kill / Hold / Recycle** 四决策（同 R3 页面） | 方法论官方 | ✅ | U-P051c-16、I3 |
| R16 | Brinson, Hood & Beebower (1986)；多期归因需 Carino/Menchero/GRAP 链接（Ortect/QuanterLab 转述） | 期刊论文（二手转述） | ⚠️ | U-P051c-12 |
| R17 | Gentleman & Temple Lang (2007)「research compendium」（数据+代码+计算环境可复现分发，R Journal 转述） | 期刊论文（二手转述） | ⚠️ | U-P051c-13、G5 归档 |
| R18 | Parnas, *On the Criteria To Be Used in Decomposing Systems into Modules*, CACM 15(12), 1972，DOI 10.1145/361598.361623——**信息隐藏**：模块应按「隐藏的设计决策」分解，而非按流程步骤 | CACM 论文 | ✅ **一手**（ACM DL 原文片段） | U-P051c-4 |
| R19 | Arnott, Harvey & Markowitz, *A Backtesting Protocol in the Era of Machine Learning*, 2019，DOI 10.2139/ssrn.3275654——研究协议：分阶段验证、避免在最终测试集反复试错 | 期刊/SSRN 论文 | ✅ **一手**（摘要全文） | U-P051c-4（间接）、12 |
| R20 | Brinson, Hood & Beebower, *Determinants of Portfolio Performance*, FAJ 42(4), 1986，DOI 10.2469/faj.v42.n4.39（+ 1995 FAJ 51(1) 复检，DOI 10.2469/faj.v51.n1.1869）——归因分解的**原始单期模型** | FAJ 论文 | ✅ **一手**（Crossref 元数据） | U-P051c-12 |
| R21 | Menchero, *Optimized Geometric Attribution*, FAJ 61(4), 2005，DOI 10.2469/faj.v61.n4.2743——多期归因**链接**是独立研究课题（另见 Carino/Menchero 系列） | FAJ 论文 | ✅ **一手**（Crossref 元数据） | U-P051c-12 |

### 11.6 复核对本批的净结论

1. **U-P051c-1 维持 A**：`core/lifecycle.py` 纯函数核 + `agents/` 适配器（R1/R2）；
2. **U-P051c-2 维持 A 但修订判据**：paper 阶段改**双条件** `paper_days>=20 && trades>=50`；`GateCriteria` 拆 readiness/value 两组；证据注入须在 DESIGN 明确标注为**工程选择**（R3/R7）；DSR/PBO 留接口位（R4/R5/R6）；
3. **U-P051c-3 维持 A**：纯账本 + 校验，sleeve 语义（独立核算/合计守恒/与权重解耦）（R8/R9/R10）；
4. **U-P051c-4 维持 A**：不解 U-P044-3，引擎零 diff（R11/R12/R13）。
5. 新增未决：**U-P051c-10**（DSR/PBO 可插拔判据，本批只留字段与文档承诺，不实现）；**U-P051c-11**（`GateCriteria` 的 readiness/value 分组命名是否与既有 `AssumptionCheck` 对齐）。

### 11.7 七项待裁决的锚点充足度（2026-11-21 补检）

| 裁决项 | 外部锚点 | 最高证据层级 | 充足度 | 结论是否变化 |
|--------|----------|--------------|--------|--------------|
| **U-P051c-1** 归属 `core/lifecycle.py` | R1（⚠️）+ R2（✅ 官方四层） | 官方文档 | **充足** | 不变（A） |
| **U-P051c-2** 证据注入式 paper | R3（✅ Gate 机制）+ R4/R5/R6（✅/⚠️ 判据修正）+ R7（⚠️ 时长） | 官方方法论 + 期刊 | **判据充足；「证据注入」本身无先例** | 不变（A），但须在 DESIGN 承认「机制为本仓库工程选择」 |
| **U-P051c-3** 纯账本虚拟子账户 | R8（✅ 监管文件）+ R9（✅ 官方）+ R10（✅ 摘要） | 监管文件 | **充足** | 不变（A） |
| **U-P051c-4** 不解 U-P044-3 | R11/R12/R13（⚠️）+ **R18 ✅ + R19 ✅（补充调研）** | **一手 CACM 论文** | **中等偏强** | 不变（A）：R18「按隐藏的设计决策分解模块」支持**新增独立模块**（lifecycle / 虚拟账本）而非重构引擎主循环；R19 支持「分阶段交付、不在同一批混入重构」 |
| **U-P051c-12** 月度归因外置 | **R20 ✅ + R21 ✅（一手 FAJ；R16 为其二手转述）** | **一手 FAJ 论文** | **充足（方向）** | 强化 A（外置）：R20 是**单期**模型，R21 表明「多期链接」本身是独立研究课题 → 本批实现成本与出错面远高于预期 |
| **U-P051c-13** 指纹方案 + 声明偏差 | R14（✅ **MLflow 官方弃用 Model Stages**）+ R17（⚠️ compendium） | 官方文档 | **强** | **强化 A**：把阶段嵌进注册表已被业界退场；指纹字段照「单调版本 + git commit + digest」设计 |
| **U-P051c-16** Gate 决策枚举 | R15（✅ **Go/Kill/Hold/Recycle**） | 方法论官方 | **强** | **细化 A**：四值枚举；`recycle → draft` 且版本递增（同时解 I3 矛盾与 backtest 失败路径） |

**判定**：7 项中 **4 项有官方/监管级锚点**（1/2/3/16 的机制面），**1 项强**（13），原 2 项二手（4/12）**已通过 §11.8 补齐一手文献**。因此——

- 可直接裁决：1、2、3、13、16（证据充分）；
- 建议裁决但仍属「方向性判断」：12（外置成本论）；
- **证据最弱的是 U-P051c-4**：经补充调研（R18/R19）已升至**中等偏强**；其本质是「不做某重构」的保守选择，风险不对称（不做 = 零回归风险），故不要求更强锚点。
- **补充调研后（2026-11-21，§11.8）**：原 2 项仅二手证据均已补齐一手文献——U-P051c-4（Parnas 1972 + Arnott/Harvey/Markowitz 2019）、U-P051c-12（Brinson et al. 1986 + Menchero 2005）。**7 项现在全部具备一手或官方级锚点**。

**诚实边界**：外部锚点只能证明「方向与业界一致」，**不能证明本仓库的具体阈值/枚举正确**（如 `50` 笔、`ρ_min=0.5`、四值决策的 kill 生效阶段）。这些必须在 DESIGN 标为经验默认值，并由单元测试锁定**迁移规则**而非数值。

### 11.8 两项二手证据项的补充调研（2026-11-21）

#### 11.8.1 U-P051c-4：不解 U-P044-3

| 锚点 | 等级 | 提供了什么 | 局限 |
|------|------|------------|------|
| **R18** Parnas, CACM 1972（DOI 10.1145/361598.361623） | ✅ **一手**（ACM DL 原文片段确认 information hiding 与「模块按其隐藏的设计决策划分」） | 架构原则：**新增独立模块**（lifecycle / 虚拟账本）优于把新逻辑塞进既有主循环；模块边界应随「可能变化的设计决策」划 | 1972 年通用软件工程文献，不涉及量化交易领域 |
| **R19** Arnott, Harvey & Markowitz 2019（DOI 10.2139/ssrn.3275654） | ✅ **一手**（摘要全文） | 研究协议强调**分阶段验证**、避免在最终测试集上反复试错 | 讨论对象是研究流程而非代码架构，对「重构是否顺带」只能**间接**支持 |

**结论**：维持 A（不解 U-P044-3）。

**诚实标注**：**「回测引擎主循环是否应当重构」不存在专门的一手学术命题**——它是工程判断。R18 提供的是「如何划分模块」的原则，不是本仓库该不该重构的结论；本项裁决的真实依据是**风险不对称**（不做 = 零回归风险）+ 范围纪律。

#### 11.8.2 U-P051c-12：月度归因外置

| 锚点 | 等级 | 提供了什么 |
|------|------|------------|
| **R20** Brinson, Hood & Beebower, *Determinants of Portfolio Performance*, FAJ 42(4) 1986（DOI 10.2469/faj.v42.n4.39；1995 年 FAJ 51(1) 复检版 DOI 10.2469/faj.v51.n1.1869） | ✅ **一手**（Crossref 元数据：FAJ 卷期页、59 次引用） | 归因分解的**原始单期**模型（配置 / 选择 / 交互效应） |
| **R21** Menchero, *Optimized Geometric Attribution*, FAJ 61(4) 2005（DOI 10.2469/faj.v61.n4.2743） | ✅ **一手**（Crossref 元数据） | 多期归因**链接**需要专门方法（几何 / 算术链接、Carino/Menchero/GRAP 系列），本身是独立研究课题 |

**结论**：由「中等偏弱」升为「**充足（方向）**」。外置理由从「价值密度低」升级为一条可验证的成本论证：**月度报告必然跨期 → 必须做多期链接 → 单期模型（R20）不足 → 需引入一个新算法族（R21 系列）及其校准测试**，这超出「生命周期状态机」主线的收益边界。

**残余局限**：一手文献证明「归因有实现成本」，**不证明**「必须外置到哪个批次」——批次归属仍是范围裁决（U-P051c-12 的 A/B），只是成本侧已无争议。
