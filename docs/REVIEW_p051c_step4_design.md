# REVIEW：P-051c Step 4 —— DESIGN 异构复审

> **复审对象**: [DESIGN_p051c_strategy_lifecycle.md](DESIGN_p051c_strategy_lifecycle.md)（D1-D12 / I1-I11 / 17 项裁决 / §5-§9）
> **复审基座**: GLM-5.3-Flash（作者 DeepSeek-V4.1-Flash → **异构成立 ✅**）
> **日期**: 2026-11-21 · **代码证据时点**: HEAD `53db4f7`
> **结论**: **未通过（1 P1 + 2 P2 + 4 P3）**——P1 为 D6 视图构造规格缺口（IMPL 无法唯一执行）；P2 两项为 OOS 度量的数学边界缺陷

---

## 1. 复审方法

1. 全文精读 DESIGN（§0-§10）；
2. 逐条核验其引用的 8 处代码事实（实读 `core/strategy.py` / `core/metrics.py` / `strategy_evaluation/stats.py` / `tests/test_p051b_end_to_end.py` / `agents/assumption_monitor.py`）；
3. 数学边界审查（decay 公式 / 聚合拼接 / IC 口径）；
4. 依 F-S10 复审框架分严重度（P1=实施无法唯一执行或语义错误 / P2=度量缺陷或规格模糊致歧义 / P3=表述/一致性）。

---

## 2. 事实核验（8/8 通过 + 2 项发现缺口）

| # | DESIGN 断言 | 核验 |
|---|-------------|------|
| F1 | `StrategyMeta` 四件套（strategy_id/version/param_schema/code_hash） | ✅ [core/strategy.py L76-L82](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L76-L82)，`code_hash` = 类源码 sha256 前 12 hex（L7/L45） |
| F2 | `signals_frame` 过滤 0 权重 | ✅ L258 `weights[weights != 0]`——DESIGN R4 风险成立 |
| F3 | `views_from_data(dm, signal, tradable, returns_window, history_window)` | ✅ 签名存在；**但 D6 对 signal/tradable/预热段的使用约定缺失**（→ F-D1） |
| F4 | `compute_metrics(portfolio_value, *, risk_free_rate, periods)`、`len>=2` 否则 ValueError | ✅ [core/metrics.py L57-L71](file:///f:/Coding/Factor_Trading_v3.0/core/metrics.py#L57-L71)；**D6 未处理窗口最短长度**（→ F-D3） |
| F5 | `calculate_ic(method="spearman")`、共同标的 <10 → NaN | ✅ [strategy_evaluation/stats.py L69-L72](file:///f:/Coding/Factor_Trading_v3.0/strategy_evaluation/stats.py#L69-L72)——DESIGN R3 断言准确 |
| F6 | `WalkForwardSplitter.split(dates)` | ✅ E1 已实证（Step 2） |
| F7 | `AlertLevel` 三值 green/yellow/red + `MonitorState.overall_level` | ✅ [assumption_monitor.py L37-L72](file:///f:/Coding/Factor_Trading_v3.0/agents/assumption_monitor.py#L37-L72)——D10 入参字符串映射的事实基础成立 |
| F8 | `engine_v2.set_signal(mode="weights")` + index == dm.trade_dates | ✅（P-044/P-051b 两轮实证） |

**核验通过但暴露缺口**：P-051b E2 的实际用法（[test_p051b_end_to_end.py L77-L92](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p051b_end_to_end.py#L77-L92)）揭示 D6 缺三处工程约定——signal 占位（E2 借 `engine._composite_signal`）、`tradable=engine.universe.tradable` 传递、`views[WINDOW:]` 跳预热 + 头部补零。DESIGN 全部未提 → **F-D1**。

---

## 3. 发现清单

### P1（1 项）

**F-D1 · D6 视图构造规格不完整，IMPL 无法唯一执行**

`oos.evaluate_strategy` 的步骤 1-2 有一个**先有鸡还是先有蛋**的缺口：`views_from_data` 需要 `signal` DataFrame 提供「日期全集」（E2 借用了 `engine._composite_signal`——但 lifecycle 评估独立策略，不存在引擎复合信号），且 `tradable` 是否传递未定。同时「全区间跑一次」掩盖了 E2 已实证的三段式语义：

1. 前 `W` 个 views 的 `history=None`（`i < W`），模板会抛 `StrategyConfigError`——必须跳过（E2 用 `views[WINDOW:]`）；
2. 跳过段的权重须**头部补零**拼回 `full`，否则 `set_signal` 的 index ≠ `dm.trade_dates` 直接 ValueError；
3. **预热段是否计入绩效**：若把补零段计入 `compute_metrics`，等于把强制空仓段算进夏普/回撤——DESIGN 必须显式裁决（计入 or 排除，建议排除并记录 `warmup_days`）。

**要求**：D6 重写为「视图构造约定」小节，逐项写死 signal 占位构造（如全 True 布尔框）、tradable 来源（None 或调用方传入）、预热段三段式处理、`warmup_days` 是否进 `StageEvidence`。

### P2（2 项）

**F-D2 · decay 公式在 |IS sharpe| ≈ 0 时爆炸，产生误判**

D6 步骤 6：`(mean(IS) − mean(OOS)) / |mean(IS)|`，仅处理 `IS == 0`（返回 0.0）。当 IS sharpe = 0.001（近零噪声）时，decay 数值可达数百 → 必触发 `is_oos_decay_max=0.5` → 误 RECYCLE/KILL 一个「IS 无信号」的策略。**IS 无信号 ≠ 衰减**。

**要求**：定义 `|mean(IS)| < ε`（如 0.1）时返回 `NaN`，并明确 NaN → 该判据记 `insufficient_signal` → `HOLD`（不是 GO 也不是 KILL）。

**F-D3 · 聚合拼接的段语义未定义**

D6 步骤 5「各 test 段净值连乘拼接（段间以 1.0 锚点对齐）」存在两处歧义：

1. **段收益起止日**：test 段 `[a, b]` 的收益是 `pv[b]/pv[a-1]` 还是 `pv[b]/pv[a]`？continuous 模式下段首继承前序持仓，段首日收益归属（train 侧还是 test 侧）直接改变 OOS 指标；
2. **窗口最短长度**：`compute_metrics` 要求 `len >= 2`，窗口过短（如 test_size=2 且段首被扣除）会 ValueError——DESIGN 未定义最短窗口校验与失败行为（建议：不足时该窗口记 NaN + `HOLD`）。

**要求**：D6 写死段收益公式（建议 `pv[b] / pv[a-1]`，即「段首继承持仓、段首日收益归 test」并在文档注明这是 continuous 语义的自然推论）+ 最短窗口规则。

### P3（4 项）

| 编号 | 发现 | 要求 |
|------|------|------|
| F-D4 | D2 图注「两步：demote→paper 再 retire」对 **paper 自身的 KILL** 不适用（paper→retired 是一步）；图文微不一致 | 图注改为「gray/live 两步；paper 一步」 |
| F-D5 | IC 的「次日收益」口径未定义（raw close-to-close？T+1 对齐？）；当日无持仓（全零权重）时该日 IC 如何处理未定义 | D6 步骤 7 补两句：收益口径 = `dm.get_adj_price("close","raw")` 的次日 close/close；全零日记 NaN |
| F-D6 | D7 `fill(code, notional)` 的成交额 ≠ 预留额时差额处理未定义（滑点下 `reserved` 残额是否自动 release、差额计入 cash 还是 positions） | D7 补一句：`fill` 以实际成交额计，`reserved` 与成交额的差额自动 `release` 回 `cash` |
| F-D7 | D2「版本号 +1」与 D8「调用方传入新 version」表述不一致——lifecycle 机制上只能校验「≠ 旧版本」，`+1` 是约定不是可执行校验 | D8 统一为「必须与历史所有 version 不同」，`+1` 仅为推荐约定 |

---

## 4. 核验通过项（不修）

- 17 项裁决定案齐备且与 §11.7-11.8 证据一致；
- 三模块划分 + 依赖纪律（D1，Parnas R18）成立；D10 字符串映射避免 import agents，好设计；
- D2 退役唯一入边 + KILL 两步消解了二轮 F-R2b-1/2（机制本身正确，仅图注瑕疵 F-D4）；
- I1-I11 与 D7/D9/D11 对应完整；§8 偏差表 5 条诚实；U-P051c-17 continuous 语义声明充分；
- 测试数算术正确（14+10+8+10+5+3=50，≈1141 在 RESEARCH 区间内）；
- R3/R4 风险与代码事实一致（F5/F2 实证）。

---

## 5. 出口判定与后续

- **「0 P1」未满足** → 须收敛修复：F-D1 必修（P1），F-D2/F-D3 必修（P2 数学边界），F-D4..F-D7 建议一并修（文字量小）。
- 修复后由用户决定：**二轮复审** 或 **带修复说明直进 Step 5 IMPL**（与 P-051b Step 4 惯例一致）。

---

## 6. 修复记录（2026-11-21，作者基座 DeepSeek-V4.1-Flash）

| 编号 | 严重度 | 修复落点（DESIGN） |
|------|--------|--------------------|
| F-D1 | P1 | **D6.1 视图构造约定**：signal 全 `True` 占位 + `tradable` 可选 + `views[W:]` + 头部补零 + 样本不足抛错；**新增 U-P051c-19**（预热段排除，`warmup_days` 入证据） |
| F-D2 | P2 | **D6.3**：`|mean(IS)| < EPS_SHARPE(0.1)` → `NaN` → `insufficient_signal` → `HOLD`（非 GO 非 KILL） |
| F-D3 | P2 | **D6.2**：段公式 `pv[max(a-1, W) : b+1]`（段首日归本段）、`len(seg)<2` → `window_too_short` → HOLD、聚合按段首归一化连乘 |
| F-D4 | P3 | **D2**：图注改为「gray/live 两步；paper 一步」 |
| F-D5 | P3 | **D6.4**：`raw` close 的 `pct_change().shift(-1)`；全零权重日 / <10 标的 → NaN |
| F-D6 | P3 | **D7**：`fill` 以实际成交额计；差额须先 `release` 再 `fill`；`reserved < 0` 抛 `ValueError` |
| F-D7 | P3 | **D2 / D8**：统一为「新 version 与历史所有记录均不同」，`+1` 仅推荐 |

同步：§7 测试 O 组 8 → **9**，合计 → **51**，pytest 目标 → **≈1142**（仍在 ≥1131 区间内）。

**待二轮复审确认**（重点：D6.1 的 `W` 推导是否可唯一实现、D6.2 段公式与 `Splitter` 索引口径是否一致）。

---

## 7. 二轮复审（2026-11-21，GLM-5.3-Flash → 复审 DeepSeek 修复稿）

**结论：未通过（2 P1 + 0 P2 + 2 P3）**。一轮 7 项中 5 项修复到位（F-D2/D3 的数学语义、F-D5/D6/D7 契约），但自标的两个核验点双双失守，且其中一处连带暴露一轮复审的自身失误。

### N-1（P1）· `strategy_min_history(strategy)` 在插件架构下不可实现

D6.1 伪码 `W = strategy_min_history(strategy) + 1` 未定义实现机制。实读四模板的 `require_history` 调用点：

| 模板 | min_rows | 来源 |
|------|----------|------|
| grid | `cfg.atr_period + 1` | [grid.py L70](file:///f:/Coding/Factor_Trading_v3.0/strategies/grid.py#L70) |
| trend | `max(ma_n, entry_n, exit_n)` | [trend.py L57-62](file:///f:/Coding/Factor_Trading_v3.0/strategies/trend.py#L57-L62) |
| momentum | `max(lookbacks)` | [momentum.py L63](file:///f:/Coding/Factor_Trading_v3.0/strategies/momentum.py#L63) |
| mean_reversion | `cfg.lookback` | [mean_reversion.py L59](file:///f:/Coding/Factor_Trading_v3.0/strategies/mean_reversion.py#L59) |

全部是**实例配置的函数**，且 `Strategy` Protocol 无 `min_history` 属性。若 `core/oos.py` 按「类名 → 模板参数」硬编码，则：① 形成 core 对 strategies 的语义耦合（即使不 import）；② **直接违背 P-051b 插件架构**——lifecycle 的对象是 registry 中任意注册策略，per-template 知识使第三批/用户自注册策略永远无法被评估。

**修复要求**（二选一，作者定）：
- **A（推荐）**：`evaluate_strategy(..., min_history: int)` 显式参数，由调用方传入——最小历史本来就是策略作者/调用方的知识，零契约改动、插件友好；
- **B**：`Strategy` Protocol 增加可选属性 `min_history: int = 0`（additive 契约扩展，四模板实现）。

### N-2（P1）· D6.2 伪码与 `WalkForwardSplitter` 实际 API 完全不匹配

实读 [walk_forward.py](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py)：

1. **签名**：`def split(self) -> Iterator[WalkForwardWindow]`（L153）——**不接收 dates 参数**（dates 在构造器传入）；D6.2 的 `splitter.split(dm.trade_dates)` 照抄必 TypeError；
2. **返回类型**：`WalkForwardWindow`（L44-55，四 Timestamp：train_start/train_end/test_start/test_end），不是 `(train_idx, test_idx)` 二元组——`test_idx[0]`/`test_idx[1]` 无意义；
3. **日期重建陷阱**：`train_dates`/`test_dates` property 用 `pd.date_range(freq="B")` **重建日期**（L57-65）——工作日历 ≠ 实际交易日（不含中国节假日语义），直接拿 `win.test_dates` 切 `pv` 会错位或漏日。必须用 `win.test_start/test_end` 在 `pv.index` 上做**标签切片**，段锚点用 `pv.index.searchsorted(win.test_start) - 1` 定位前一真实交易日。

**连带订正**：一轮 §2 F6 断言「`WalkForwardSplitter.split(dates)`」**不准确**（方法存在但签名错误）——一轮复审自身失误，在此更正；E1 的窗口切分功能成立，仅签名口径错。

**修复要求**：D6.2 重写为实 API 口径：`spl = WalkForwardSplitter(dates=..., ...)` → `for win in spl.split()` → `seg = pv.loc[win.test_start : win.test_end]`，锚点 = `test_start` 前一真实交易日；声明窗口端点为非交易日时，切片自动取真实交易日子集（pandas 标签切片语义），`len(seg) < 2` 规则不变。

### N-3（P3）· F-D4 修复不完整

D2 的 bullet 已改（「paper 自身的 KILL 只落一条」），但 ASCII 图内注释 `↓ 两步：demote→paper 再 retire` **未同步**——paper 读者仍会被误导。改图注为「gray/live 两步；paper 一步」。

### N-4（P3 → **严重度重估为 P1，见 §8.3**）· `run_engine` helper 无规格 + `initial_capital=1.0` 触发静默失效

D6.2 引入 `run_engine(dm, full, initial_capital)` 但未定义：cfg 从哪来（P-044 既有默认？）、`initial_capital` 参数与 `cfg.initial_capital` 的关系（E2 用 10_000_000，签名默认 1.0）、返回的 pv 是什么字段。补三行规格即可。

### 二轮核验通过项

- F-D2 的 `EPS_SHARPE=0.1` + `insufficient_signal→HOLD` 语义闭环 ✅；
- F-D3 的段公式/短窗规则数学上成立（但实现载体须按 N-2 重写）✅；
- F-D5 的 `pct_change().shift(-1)` + 双 NaN 规则 ✅；F-D6 两步差额守恒 ✅；F-D7「与历史所有 version 均不同」✅；
- U-P051c-19 预热段排除 + `warmup_days` 入证据 ✅。

### 出口

**0 P1 仍未满足** → 修复 N-1/N-2（N-3/N-4 顺带）后三轮复审或按惯例带修复说明直进 Step 5，由用户裁决。

---

## 8. 复审结果分析（作者基座 DeepSeek-V4.1-Flash，2026-11-21）

### 8.1 总体判断

| 维度 | 判断 |
|------|------|
| 严重度 | 两轮均未达 0 P1，但 **P1 的性质在两轮间发生了变化**（见 8.2） |
| 收敛性 | 数量收敛（7 → 4），但**不是同一缺陷收敛**——二轮 P1 是**修复过程新引入**的，属「修复型回归」 |
| 影响面 | 4 项全部落在 **D6（OOS 产出器）**，DESIGN 主体（19 项裁决 / 状态机 / I1-I11 / D7-D12）**零改动、两轮零命中** |
| 复审有效性 | **异构复审两轮均命中真缺陷**（N-2 若照抄必运行时 TypeError），未被浪费 |

### 8.2 逐项性质分析

| 编号 | 原判 | 性质 | 分析 |
|------|------|------|------|
| N-1 | P1 | **架构一致性缺口** | 不是功能错误——实现者手工传参也能跑通；之所以 P1，是因为文档**无法唯一执行**且**违背 P-051b 插件架构**（per-template 知识使第三方策略永久不可评估）。维持 P1 |
| N-2 | P1 | **硬性事实错误** | `split(dates)` 必 TypeError、`(train_idx, test_idx)` 解包必错、`test_dates` 的 `freq="B"` 会丢中国节假日 → 指标直接错。这是**照抄即崩**，P1 无争议 |
| N-3 | P3 | 文字残留 | 成立，量级正确 |
| **N-4** | P3 | **实为 P1（严重度重估）** | 见 8.3 |

### 8.3 N-4 严重度重估（本轮新增发现）

复审只写了「`run_engine` 无规格」，但 `initial_capital=1.0` 并非中性默认值：

- 实证：[config.py L194](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L194) `commission_min = 5.0`；[engine_v2.py L1206](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1206) 将该值接入成交成本；
- 推演：资金 1.0 元、单笔最低佣金 5.0 元 → P-047 的 `cash_budget_scale` 会把可买数量压到 0（`qty=0` 不计最低佣金）→ **全程空仓** → 净值恒定 → OOS 夏普 0、回撤 0、IC 全 NaN；
- 后果：`oos_sharpe < 0` 判据不触发（0 不小于 0）→ 所有策略一律走 `HOLD`/`RECYCLE` → **晋级门对所有策略永久失效且不报错**。这是**静默失效**，比抛异常更危险。

**结论：N-4 升为 P1**；修复要求补「`initial_capital` 默认 **1e7**（与 P-044 既有回测口径一致）、且与 `cfg.initial_capital` 的关系写死；< 最小佣金量级时抛 `LifecycleError`」——由静默失效改为显式失败。

### 8.4 根因

1. **抽象层级反复**：一轮 D6 是「7 步流程」（过抽象，缺工程约定）→ 二轮改成「伪码」（过具体，但具体内容是凭记忆写的）→ 伪码制造了「已确定」的假象，反而跳过了 API 实读。
2. **修复未执行核验纪律**：N-1 的 `strategy_min_history` 与 N-2 的 `split(dates)` 都是**修复时新写的符号**，未按「新写入即需实证」处理。
3. **D6 是唯一的跨模块集成面**：状态机/账户/归档都是本批新造、自洽；D6 消费 `Splitter`/`BacktestAdapter`/`engine_v2` 三个既有模块，外部事实最密集——两轮 P1 全部命中于此，非偶然。

### 8.5 处置建议

- **修复顺序**：N-2（先实读 API）→ N-1（方案 A）→ N-4（默认值与显式失败）→ N-3；
- **N-1 选 A**：`min_history` 作为 `evaluate_strategy` 显式参数。B 案虽更优雅，但会给 Protocol 增加可选成员、需回改 P-051b 四模板与测试，收益不抵成本；
- **三轮复审改为定点核验**：只核 D6.1-D6.3 四段 + N-1..N-4 回执，不做全文重审（主体已两轮零命中，全量复审边际收益低）；
- **修复纪律（本批强制）**：凡修复中引入的新符号/新调用，必须在文档内标注「实证：文件:行号」，否则视为未完成。

---

## 9. 二轮修复记录（2026-11-21）

| 编号 | 修复落点（DESIGN） | 实证 |
|------|--------------------|------|
| N-1（P1） | **D6.1**：`W = min_history + 1`，`min_history` 为 `evaluate_strategy` 必填参数；新增 **U-P051c-20（方案 A）** | 四模板 min_rows 行号（grid L70 / trend L57-62 / momentum L63 / MR L59）已逐条内联 |
| N-2（P1） | **D6.2** 按实 API 重写：`split()` 无参、`WalkForwardWindow` 四 Timestamp、**禁用 `win.test_dates`**（`freq="B"` 重建）、`searchsorted` 定位真实交易日 | L111-L120（构造器）/ L153（`split`）/ L51-L55（窗口字段）/ L58-L65（日期重建陷阱）均已内联 |
| N-4（P1，重估） | **D6.2** 补 `run_engine` 规格：`initial_capital` 默认 **1e7**、覆盖 `cfg.initial_capital`、**`< 1e6` 抛 `LifecycleError`**（消除静默失效） | config.py L194（`commission_min=5.0`）/ L408（`initial_capital=1e7`） |
| N-3（P3） | **D2** ASCII 图注改为「gray/live 两步；paper 一步」 | — |

同步：§0 补入遗漏的 **U-P051c-18** 行（此前仅存在于 §13 风险表，属文档不一致）；裁决总数 **20 项**。

**待三轮定点核验**：仅核 D6.1-D6.3 四段 + 本节 4 项回执，不做全文重审（§8.5 建议）。

---

## 10. 三轮定点核验（2026-11-21，GLM-5.3-Flash 复核 DeepSeek 修复稿）

**范围**（§8.5 定案）：D6.1-D6.3 四段 + §9 四项回执 + **回执引用行号真实性重验**（「新符号必实证」纪律的回执面）——不做全文重审。

### 10.1 行号重验（4 组全真）

| # | 回执引用 | 重验方式 | 结果 |
|---|----------|----------|------|
| V1 | config.py L408 `initial_capital: float = 10_000_000.0` | grep 全文 | ✅ 唯一命中 |
| V2 | 四模板 require_history 行号（grid L70 / trend L57 / momentum L63 / mean_reversion L59；base L42 定义处） | grep `require_history` | ✅ 5 行全中 |
| V3 | walk_forward.py L51-55（窗口五字段）/ L58-65（`freq="B"` 重建）/ L111-120（构造器）/ L153（`split()` 无参） | 实读全文 | ✅ 全中 |
| V4 | config.py L194 `commission_min: float = 5.0`（§8.3 静默失效链条引用） | grep | ✅ |

二轮修复时系统已清除当时的 grep/read 证据（行号存在记忆臆写风险）——本轮重验**全部为真**，风险解除。

### 10.2 回执 × 落盘对照（4/4 一致）

| 回执 | 声明落点 | DESIGN 实际 | 判定 |
|------|----------|-------------|------|
| N-1 | D6.1 `min_history` 必填 + U-P051c-20 方案 A | D6.1 伪码注释「调用方显式传入」/ min_history 必填段（四模板行号内联 + `<1` 抛错）/ §0 表第 20 行 | ✅ |
| N-2 | D6.2 实 API 重写 + 禁用 `test_dates` | D6.2 伪码（`split()` 无参 / `searchsorted` 左锚 `max(·, W)` / 右端 `side="right"`）/ 窗口 API 实证段 / 禁用条目 | ✅ |
| N-4 | `run_engine` 规格：默认 1e7、覆盖 `cfg.initial_capital`、`<1e6` 抛 `LifecycleError` | D6.2 run_engine 规格段三要素齐备（含显式失败文案「最低佣金 5 元将主导成本结构」） | ✅ |
| N-3 | D2 图注「gray/live 两步；paper 一步」 | D2 图内注释 + bullet 双处到位 | ✅ |

### 10.3 D6 语义自洽推演（非缺陷观察）

- `searchsorted` 边界：左锚落入预热段时被 `max(·, W)` 截断（与 U-P051c-19 一致）；右端 `side="right"` 为闭区间；窗口端点为非交易日时自动落到相邻真实交易日——与 pandas 定位语义一致；
- 整窗落在预热段内 → `len(seg) < 2` → `window_too_short` → HOLD，无崩溃路径；
- **观察（不阻断）**：聚合连乘中各段锚点日归一化为 1.0，在 `agg_pv` 中呈「冻结值」平坦日（数量 = 窗口数，约 2-5 日），对夏普/波动有极轻微稀释——属 F-D3 已批准语义的自然推论，Step 5 按 D6.2 原文实现即可。

### 10.4 残留发现（2 P3，均为修复同步遗漏，已由核验方顺手修正）

| 编号 | 位置 | 问题 | 处置 |
|------|------|------|------|
| T-1 | D6 流程总览 | 签名残留 `initial_capital=1.0`（与 D6.2 规格 1e7 + `<1e6` 抛错**自相矛盾**——默认调用即抛错），且缺必填参数 `min_history` | 已同步：`min_history: int` 必填 + `initial_capital=10_000_000.0`（值源 config.py L408 已实证；**无新符号引入**，不触发 §8.5 实证纪律） |
| T-2 | DESIGN §10 出口条件 | 「19 项裁决」——§0 实为 20 项（U-P051c-19/20 已补入，§9 亦声明 20 项） | 已改为「20 项裁决」 |

### 10.5 结论

**通过（0 P1 / 0 P2 / 2 P3 已修正）→ Step 4 关闭**。三轮累计：一轮 7 项 → 二轮 4 项（N-4 重估 P1）→ 三轮定点核验 0 项未决；D6（唯一跨模块集成面）规格现与 `walk_forward` / `config` 实证 API 完全对齐。下一步 **Step 5 IMPL**（随实施进行：U-P051c-18 segmented 模式依 `engine_v2` 能力裁决、`run_engine` 返回字段名核对 engine_v2）。
