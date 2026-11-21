# REVIEW：P-051c Step 2 异构复审（调研文档）

> **批次**: P-051c · **Step 2 异构复审** · 日期 2026-11-21
> **对象**: [RESEARCH_p051c_strategy_lifecycle.md](RESEARCH_p051c_strategy_lifecycle.md)（含 §11 外部锚点）
> **作者基座**: DeepSeek-V4.1-Flash · **复审基座**: GLM-5.3-Flash（RULE-5 异构 ✅）
> **方法**: ① 对 E1-E14 逐条实读核验（作者部分读取结果已被上下文清理，转录风险高）；② 对照总纲 L197-L276 原文；③ 复核 §11 外部锚点的标注纪律；④ 审查缺口清单/方案矩阵/不变式的完整性。
> **结论**: **未通过**（**4 P1 + 3 P2 + 2 P3**）——最大问题是 **E3 失实：`WalkForwardEngine` 是空壳，晋级门的 OOS 绩效产出链路根本不存在**，缺口清单低估了 G2 的深度。

---

## 0. 结论速览

| 严重度 | 数量 | 编号 |
|--------|------|------|
| P1（影响 DESIGN 走向，必须先裁决） | 4 | F-R1 / F-R2 / F-R3 / F-R4 |
| P2（影响设计质量，Step 3 前应修） | 3 | F-R5 / F-R6 / F-R7 |
| P3（转录修正） | 2 | F-R8 / F-R9 |

**核验通过项**：E1 / E2 / E4 / E5 / E7 / E8 / E9 / E11 / E12 / E13 / E14 行号与事实全部命中；总纲 L204-210 / L268 引用准确；§11 十三条外部锚点的 ✅/⚠️ 标注与实际可得材料相符，无幻觉引用。

---

## 1. P1 发现

### F-R1 【E3 失实 · 晋级门数据链路断层】

**证据**（本轮实读）：

- [walk_forward_engine.py L134](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward_engine.py#L134-L140)：`# 注意：这里简化处理，实际应该运行完整的训练流程`——`train_result` 是只含 `period/start_date/end_date/n_days` 的**占位 dict**，未跑任何回测；
- [walk_forward_engine.py L163-L171](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward_engine.py#L163-L171)：`test_result` 的 `total_return: 0.0  # 占位`、`sharpe_ratio: 0.0  # 占位`；
- `test_config`（L160 创建）**创建后从未消费**；
- [_aggregate_results L221-L238](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward_engine.py#L221-L238) 只聚合上述占位值。

**问题**：RESEARCH E3 写「`WalkForwardEngine` … 在多个时间窗口上运行回测」「训练期允许 Agent 在线学习，测试期冻结」——**失实**。实际只做：切窗（真）→ `agent.set_period()` 改模式标记（不学习）→ 占位指标（恒 0）→ 回调。RESEARCH §1 结论 1「三块能力（walk-forward / 分配器 / 假设监控）已存在，缺的是判据与状态」**错一半**：切窗器存在，但 **walk-forward 的「跑」不存在**；G2 的真实深度是「判据缺失 + **绩效产出器缺失**」双层。

**建议**：Step 3 方案矩阵必须新增「OOS 绩效产出器」一节，候选：
- **A（倾向）**：`WalkForwardSplitter`（纯切窗，已验证）+ `BacktestAdapter.signals_frame`（P-051b 端到端已验证）+ 新建轻量逐窗绩效计算（夏普/回撤/换手），**不改 `WalkForwardEngine`**；
- B：补全 `WalkForwardEngine`（改它跑真实回测）——但它是 agents 体系专用（`base_engine_class` 期望 `StrategyEngine`，四模板走的是 `BacktestAdapter` 路径），兼容性改造面大；
- C：只用单段 OOS 切分——不符合总纲 L207「walk-forward 回测」语义。

### F-R2 【退役语义与总纲 L207 偏差 + IC 判据缺失】

**证据**：总纲 [L207](UPGRADE_MASTER_PLAN.md#L207) 原文：「退役（**IC 持续低于阈值/回撤超限→降paper→归档可复现）**」——退役路径是**先降回 paper 再归档**；同段监控清单明示「**滚动IC衰减**」。RESEARCH §5.1 状态图中 `retired` 是从 `backtest/paper/gray` **直入**的终态（未经过降级）；§5.2 判据表**无任何 IC 字段**。

**问题**：① 退役前置语义不符；② 监控/退役判据漏掉总纲点名的 IC 衰减。IC 设施须在 Step 3 核实仓库内位置（总纲 L208 复用清单未含 IC 计算模块；`attribution.py` 是否承载待查）。

**建议**：① §5.1 状态图修正：`retire` 的合法入边 = 仅 `paper`（各阶段先 `demote` 到 paper，paper 阶段 IC 持续低于阈值才 `retire`→归档）；② §5.2 增加判据 `ic_min`（滚动 IC 阈值）与 `ic_lookback`，并新增未决项「IC 计算设施来源」。

### F-R3 【月度归因未裁决】

**证据**：总纲 [L207](UPGRADE_MASTER_PLAN.md#L207)：「月度归因（alpha/beta/行业/成本/择时，**复用 `attribution.py`**）」属于 F5 生命周期流水线。RESEARCH §1 的「做 / 不做」清单**两者皆未提**。

**问题**：范围定义不完整——既可能被解读为本批交付，也可能被静默丢弃。

**建议**：新增未决项 **U-P051c-12**：月度归因纳入 or 外置。倾向外置（`attribution.py` 已存在，生命周期侧只需触发编排，价值密度低），但须显式裁决并写明理由。

### F-R4 【`core/strategy_registry.py` 指名与指纹方案的偏差未对照】

**证据**：总纲 [L205](UPGRADE_MASTER_PLAN.md#L205) 新模块清单指名 `core/strategy_registry.py`（**版本化注册**）；P-051b 实际落地复用 `core/registry.py`（无版本化字段）；RESEARCH G6 方案 =「不改 registry，lifecycle 侧维护 `StrategyFingerprint`」——**未引用 L205 的指名，偏差未声明**。

**问题**：两条路线（lifecycle 侧指纹 vs 新建版本化注册表）未裁决；若 Step 3 沿用指纹方案，DESIGN 必须写明「与总纲 L205 指名的偏差及理由」，否则审计断链。

**建议**：新增未决项 **U-P051c-13**。倾向指纹方案（避免平行注册表；`StrategyMeta` 已含 `version/param_schema/code_hash` 四件套，L75-L82 实证），但需在 DESIGN 声明偏差。

---

## 2. P2 发现

### F-R5 【「任意时点可重放」未升为不变式】

总纲 [L210](UPGRADE_MASTER_PLAN.md#L210)：「策略状态可序列化→**任意时点可重放复算**」。RESEARCH I6 只覆盖退役快照的 JSON 往返；§7 DoD 提了「重放一致」但 I1-I8 无对应不变式条目——DoD 与不变式脱节。**建议**：新增 I9「迁移记录序列重放不变式：任意 `TransitionRecord` 前缀重放必达同一 `(stage, account_states)`」。

### F-R6 【`paper_trades>=50` 的 A股语境与证据等级】

§11.2 的 50 笔锚点全部为加密/外汇/美股 bot 供应商（全部 ⚠️）。A股 T+1 + 涨跌停 + 日频调仓下，单标的策略 20 交易日远达不到 50 笔；P-051b 四模板为多标的日频尚可达，但该默认值**语境错配风险**未讨论。**建议**：DESIGN 中 ① 明示证据等级「社区经验值，非学术结论」；② 默认值改为按策略类型配置（如 `paper_trades_per_year` 比例式），或至少在文档声明 50 笔对低频策略需放宽。

### F-R7 【VirtualAccount 与共享现金/先卖后买的对账边界未声明】

P-044 订单层语义（总纲 L197）：「先卖后买 call_seq + **共享现金账户**」——真实引擎现金流是共享的；`VirtualAccount` 是 per-策略 sleeve。RESEARCH §5.3 未声明「sleeve 现金流 ↔ 共享账户实际现金流的对账属于 P-053 接线」。若不显式声明，P-053 会面临 sleeve 账与总账对不上的语义陷阱。**建议**：§5.3 增加边界声明条目。

---

## 3. P3 发现（转录修正）

### F-R8 【三处代码证据转录错误】

| 项 | RESEARCH 原文 | 实测 |
|----|---------------|------|
| E3 便捷入口 | 「模块级 `run_walk_forward(engine_class, ...)`」 | 实名 **`run_walk_forward_backtest`**（[L241](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward_engine.py#L241)） |
| E10 监控器计数 | 「四监控器」 | 实为五类：另有 **`UniversalMonitor`**（[L679](file:///f:/Coding/Factor_Trading_v3.0/agents/assumption_monitor.py#L679)，`check` L701）；且 `AssumptionMonitorLayer.fallback_strategy` 默认 `"equal_weight"`、支持 `"risk_parity"`（L788/L817-L819） |
| E6 registry 行号 | 「`get(name)` L110」 | `get()` 实为 **L101-L104**（L110 起为 `create`）；L81 覆盖、L92 `unregister` 正确 |

### F-R9 【补记与草案厘清】

① `WalkForwardResult` dataclass 在 [core/walk_forward.py L220](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L220)（E1/E2 未列，且字段为 `window_results + agent_period_failures`，无绩效字段——佐证 F-R1）；② §5.3 `allocate(weight, total)`（分配额度）与 `try_reserve(notional)`（订单锁定）语义重叠，DESIGN 须厘清两者关系，避免双记账。

---

## 4. 核验通过项（供 Step 3 直接引用）

| # | 项 | 核验结果 |
|---|----|----------|
| 1 | E1/E2 `WalkForwardWindow` L45 / `WalkForwardSplitter` L84 / `split` L153 / `get_n_splits` L207 / `get_window` L211 | ✅ 行号精确 |
| 2 | E4 `StrategyMeta` L76 / `StrategyState` L86（to_dict L93 / from_dict L102）/ `Strategy` Protocol L129 | ✅ 精确 |
| 3 | E5 `BacktestAdapter` L228 / `signals_frame` L240 | ✅ 精确 |
| 4 | E7 `MultiStrategyEngine` L560 / run_sequential L665 / run_parallel L693 / run_vectorized L728 / run_with_dynamic_allocation L861 | ✅ 精确 |
| 5 | E8 docstring「不实际转移资金」L872 / 硬编码策略名 L892 | ✅ 精确 |
| 6 | E9 allocator 五实现 L354/L374/L419/L495/L536/L582 + MetaPolicy L661（detect_regime L682 / adapt_parameters L710）+ Manager L745（update L806 / get_weights L841 / get_report L845） | ✅ 精确 |
| 7 | E11 `data.py suspend()` L158；全仓无 promote/retire/deactivate/paper_trading | ✅ |
| 8 | E12 pyproject 无 import-linter 段 | ✅ |
| 9 | E13 test_walk_forward.py **6** / test_walk_forward_engine.py **6** | ✅（本轮 shell 重数确认） |
| 10 | E14 PROGRESS 承接项措辞（U-P051b-15 / O-P051a-1 / O-P051a-2 / U-P044-3） | ✅ |
| 11 | 总纲引用 L204-210 / L205 / L207 / L209 / L210 / L268 | ✅ 行号与内容均符 |
| 12 | §11 外部锚点 R1-R13 标注纪律 | ✅ 无幻觉；⚠️ 标注诚实（其中 R7 社区实践的证据等级问题见 F-R6） |

---

## 5. 出口判定与后续

- **出口条件「0 P1」未满足** → RESEARCH 须收敛修复（F-R1..F-R4 必修，F-R5..F-R9 建议一并修）后，由用户决定是否**二轮复审**或**带修复说明直进 Step 3**（F-R1 的绩效产出器方案、F-R2 的状态图、U-P051c-12/13 将在 Step 3 作为新裁决项）。
- 新增未决项汇总：U-P051c-12（月度归因内/外）、U-P051c-13（strategy_registry 指名 vs 指纹方案）、U-P051c-14（IC 计算设施来源）、U-P051c-15（OOS 绩效产出器方案 A/B/C，倾向 A）。

---

## 6. 二轮复审（2026-11-21，GLM-5.3-Flash）

> **对象**: RESEARCH §10.1 所列 9 项修复的落盘质量 + 修复引入的新问题。
> **方法**: 全文重读（L1-L375）逐项对照修复要求；新增 3 项代码事实核查（`core/attribution.py` / `core/metrics.py` / 全仓 IC 命名函数）。

### 6.1 修复核验结果：9/9 落盘 ✅

| 项 | 核验 |
|----|------|
| F-R1 | E1（`WalkForwardResult` L220 无绩效字段）/ E3（空壳全细节 + `run_walk_forward_backtest` L241）/ G2 双层 / §4.0 方案矩阵 / G9 / U-P051c-15 / §7 同步——**全部落盘且与实读一致** ✅ |
| F-R2 | §5.1 文字「退役唯一入边 = paper」+ §5.2 `ic_min`/`ic_lookback` + U-P051c-14 ✅；**但状态图缺边、I3 未同步**（见 6.2）⚠️ |
| F-R3 | §1 不做清单 L29 + U-P051c-12 ✅ |
| F-R4 | §4.5 G6 偏差警示 + U-P051c-13 ✅ |
| F-R5 | I9 ✅ |
| F-R6 | §5.2 L168 标注 + §11.2 净影响同步 ✅ |
| F-R7 | §5.3 对账边界段 ✅ |
| F-R8 | E3 改名 / E10 五类监控器 / E6 L101-L104 ✅（无「四监控器」「run_walk_forward(」残留） |
| F-R9 | E1 补记 / §5.3 语义厘清 / I10 ✅ |

### 6.2 二轮发现：0 P1 + 2 P2 + 2 P3

**出口判定：通过（0 P1）**——2 P2 为 Step 3 定稿范畴的设计语义问题，全部转为 Step 3 输入，不阻塞进 Step 3。

| 编号 | 严重度 | 发现 | 建议 |
|------|--------|------|------|
| **F-R2b-1** | P2 | **I3 与「退役唯一入边 = paper」矛盾**（RESEARCH L203 vs L154）：I3 仍写「任一 kill criteria 命中则**优先** `retire`」——但按 §5.1 新规则，gray/live 命中 kill 须先 `demote`→`paper`→`retire`，不可直达。F-R2 修复未同步 I3 | I3 改为「kill 命中 →（若非 paper 先 demote）→ retire」，或定义 kill 为 demote 加速路径；Step 3 定稿 |
| **F-R2b-2** | P2 | **backtest 失败路径语义未闭合 + 图缺边**：文字（L154）称「backtest / gray / live 均须先 demote 到 paper」，但状态图（L144-148）只有 gray/live 的 demote 边；且 backtest（历史回放）→paper（前向模拟）的「降级」语义存疑——更合理是 `reject → draft`（判据不达标打回）或废弃 | 状态图补边或改文字；backtest 失败路径（reject→draft vs 废弃 vs demote）作为 **U-P051c-16** 进 Step 3 裁决 |
| **F-R2b-3** | P3 | §4.2 倾向段（L111）残留**单条件** `paper_days>=20`，未同步 §5.2 / U-P051c-2 的双条件 `paper_days>=20 && paper_trades>=50` | 文字同步（可随 Step 3 或下轮修复） |
| **F-R2b-4** | P3 | §9 步骤表 Step 3 出口条件写「**10 项**未决收敛」→ 实际未决已 15 项（U-P051c-1..15） | 数字更新 |

### 6.3 二轮增值证据（非缺陷，供 Step 3 直接引用）

| # | 事实 | 影响 |
|---|------|------|
| V1 | `core/metrics.py` **存在** | §4.0 A 案「`core/metrics.py`（若存在）」升级为「已确认存在，轻量绩效计算**优先复用**它，勿另写」 |
| V2 | `core/attribution.py` **存在** | U-P051c-12 引用非幻觉 ✅ |
| V3 | **IC 计算设施已存在**：[strategy_evaluation/stats.py L54](file:///f:/Coding/Factor_Trading_v3.0/strategy_evaluation/stats.py#L54) `calculate_ic(method="spearman"\|"pearson") -> pd.Series`、L86 `calculate_ic_stats`、L114 `calculate_half_life`；`core/attribution.py` 与全仓 core 层**无** rolling IC 命名函数 | **U-P051c-14 的 A 案有实锚**：复用对象是 `strategy_evaluation/stats.py`（非 attribution.py）；Step 3 须核实其依赖方向（`strategy_evaluation` 是否可被 `core/` 消费——若不可，按 I1 纯函数纪律把 IC 计算放绩效产出器内并注明来源口径） |
