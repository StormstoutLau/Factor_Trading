# REVIEW：P-051c Step 6 —— IMPL 异构复审

> **复审对象**: [IMPL_p051c_strategy_lifecycle.md](IMPL_p051c_strategy_lifecycle.md)（C-1..C-12 实施口径 / 三新模块逐处代码 / 53 用例映射 / §4 六项 DESIGN 补齐）
> **复审基座**: GLM-5.3-Flash（作者 DeepSeek-V4.1-Flash → **异构成立 ✅**）
> **日期**: 2026-11-21 · **代码证据时点**: HEAD `53db4f7`
> **结论**: **未通过（1 P1 + 4 P2 + 3 P3）**——P1 为 HOLD 记录与迁移校验表矛盾（重放必崩）；P2 四项中两项为**测试设计不可执行**（零窗口空转 / GO 断言必败）

---

## 1. 复审方法

1. 全文精读 IMPL（§1-§5 + C-1..C-12）；
2. 逐条核验其引用的代码事实（实读 `core/engine_v2.py` / `core/strategy.py` / `core/config.py` / `core/walk_forward.py` / `core/metrics.py` / `strategy_evaluation/stats.py` / `tests/test_p051b_end_to_end.py` / `.github/workflows/tests.yml`）；
3. 语义边界审查（evaluate_gate 判定序 / apply-replay 闭环 / I7 守恒 / IC 口径 / 聚合锚点）；
4. **测试可执行性审查**（53 用例在 §3.5 数据构造下能否真实断言）；
5. 依 F-S10 框架分严重度（P1=闭环断裂或照抄必崩 / P2=用例空转或口径漂移 / P3=表述/文档一致性）。

---

## 2. 事实核验（9 项：7 通过 + 2 项暴露缺陷）

| # | IMPL 断言 | 核验 |
|---|-----------|------|
| V1 | setup 守卫可经注入 combiner 绕过：`not factor_files and pipeline is None and combiner is None` → raise（[engine_v2.py L243-L251](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L243-L251)）；注入后 `self.combiner = self._injected_combiner`（L302-303）；`_precompute_factors` 无因子文件仅 warning+return（L589-591）→ `_composite_signal` 保持 None，`set_signal` 后非 None，`run()` 前置满足（L662-666） | ✅ **C-1 装配链成立** |
| V2 | `set_signal` index 强校验（L632-633）；weights 模式跳过优化器直出目标权重（L1338-1347）；列子集经 `reindex(columns=dm.stock_codes)+fillna(0)` 合法（L637-639） | ✅ **C-7 成立** |
| V3 | `run()` 返回 `results["portfolio_value"]` = 快照 `total_value` 序列（L1857-L1865）；空快照 RuntimeError（L1756-L1760） | ✅ **C-3 字段名属实** |
| V4 | `_generate_results` 无条件 `mkdir` + `generate_report` + 写 trades/snapshots CSV（L1763-L1768 / L1839-L1848）；`write_manifest` 默认 True（[config.py L368](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L368)） | ✅ **C-2 临时目录确属必要** |
| V5 | 引擎无初始持仓/现金注入（`__init__` 仅组件注入 L138-L153；tracker 以 `cfg.initial_capital` 起账 L349-L353）；`set_signal` index 全等校验（L632-633） | ✅ **C-4 segmented 否决实证成立** |
| V6 | IC 有效对数口径 | ❌ stats.py `calculate_ic` 先 `f.dropna()`/`r.dropna()` 再交集，`len(common) < 10 → NaN`（[stats.py L66-L72](file:///f:/Coding/Factor_Trading_v3.0/strategy_evaluation/stats.py#L66-L72)）；C-10 用**未 dropna 交集**计数 → **口径差（F-I5）** |
| V7 | O 组默认 splitter 可产窗 | ❌ `split()` 在 `test_end_idx >= n_dates` 时 break（[walk_forward.py](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py) split 循环）；PERIODS=120 < train_size=252 → **零窗口（F-I2）** |
| V8 | mypy 已含 `core`（[tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46)）；black line-length=100（[pyproject.toml L94-L96](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L94-L96)） | ✅ |
| V9 | 末日强平 + `_refresh_last_nav`（L687-L690）→ C-3 末值口径声明属实 | ✅ |

---

## 3. 发现清单

### P1（1 项）

**F-I1 · HOLD 记录与 apply/replay 校验表矛盾——I9 前缀重放必崩**

C-11 裁定「HOLD 落一条 `from_stage == to_stage` 的 `TransitionRecord`（action="hold"）」，但 §3.1 的 `LEGAL` 表**只含 GO / RECYCLE / KILL 条目**，且 `replay` 明文「按 apply 同一张合法表校验 `(from, action)`，非法即抛」。推演：任一含 HOLD 的 history（ evaluate_gate HOLD → apply 落记录）在 `replay` 重放时 `(PAPER, HOLD)` 不在表中 → `LifecycleError` → **I9「任意前缀重放必收敛」被违反**。同时 `apply` 正文虽写「HOLD 原地」，机制分支未定义（HOLD 不查表？target 必须为 None？）——实现者无法唯一执行。

**修法**：`apply` 对 `action == HOLD` 特判：要求 `decision.target is None`，落 `from==to` 记录（不查 LEGAL）；`replay` 对 `r.action == "hold" and r.from_stage == r.to_stage` 特判通过（stage 不变）；LEGAL 表注释声明「HOLD 走特判路径，不入表」。O/R 组各补 1 断言：含 HOLD 记录的 history 可完整 replay。

### P2（4 项）

**F-I2 · O 组零窗口：默认 splitter 对 120 日 fixture 产不出任何窗口**

§3.5 定 PERIODS=120，而 `evaluate_strategy` 默认 `train_size=252/test_size=63`；`split()` 首轮即 `test_end_idx = 252+5+63-1 >= 120` → break → **零窗口** → `aggregate=None / insufficient_warmup`。O 组 11 条中窗口类断言（searchsorted 边界 / 左锚 clamp / 短窗 HOLD / 聚合连乘 / decay / IC）**全部无对象**——用例要么假绿要么崩。

**修法**：O 组全部显式传 `WalkForwardSplitter(dates=dm.trade_dates, train_size=40, test_size=20, purge_gap=2)`（首窗消耗 62 日，末窗 test_end ≈ 102 < 120）；无前视用例利用末窗之后的 ~18 日做「未来 +50%」重写（窗口切分不变，前段指标不变）。

**F-I3 · E 组「四模板 → evaluate_gate == GO」断言必败：等权策略 IC 恒 NaN**

P-051b C-1 实证：四模板输出 `equal_weight(selected)`——当日入选标的**同权**。C-10 的 spearman 对**常数序列**返回 NaN（pandas corr 常数输入 → NaN）→ `ic_series` 恒空 → evaluate_gate 表第 8 行「序列空 → 追加 ic」→ **HOLD，GO 永不可达**。E 组「四模板参数化断言 evaluate_gate == GO」必然失败。

**修法**：GO 全链用例改用**权重差异化** fake Strategy（固定非等权目标，如 `{A: 0.6, B: 0.3}`）+ 小窗口 splitter；四模板端到端断言降级为「`evaluate_strategy` 产出合法 OOSReport + `to_evidence` 可构造 + `evaluate_gate` 返回合法 `GateAction`」。

**F-I4 · C-6 违反 DESIGN D1 明文却「不改 DESIGN」——矛盾推给 Step 8**

DESIGN D1 原文：「三者互不 import（**oos 不 import lifecycle**，lifecycle 只接受 StageEvidence 数据）」。C-6 让 `core/oos.py` `from core.lifecycle import LifecycleError`，处置却写「不改 DESIGN」。C-6 的方向本身正确（oos 抛裸 `ValueError` 会被上层 `except LifecycleError` 漏接），但**文档级矛盾必须当场消解**，否则 Step 8 一致性必报。

**修法（推荐 A）**：
- A：DESIGN D1 加脚注「**例外：异常类型依赖**——`LifecycleError` 定义于 lifecycle，oos 仅 import 该类型，零数据流/零行为耦合；D1 实质约束是无数据耦合」+ IMPL C-6 回执引用该脚注；
- B：oos 自定义 `OOSError(ValueError)`——上层漏接，与 D6.2「`<1e6` → LifecycleError」明文冲突，不推荐。

**F-I5 · IC 有效对数口径与 stats.py 不一致（V6）**

stats.py：先 dropna 再交集、`len < 10 → NaN`（L66-L72）。C-10 用未 dropna 交集计数——next_ret 含 NaN（末日 `shift(-1)`、停牌）时有效对数虚高，边界日 IMPL 算 IC 而对齐口径应记 NaN。U-P051c-14 要求「口径对齐 `calculate_ic`」。

**修法**：corr 前 `paired = pd.concat([sel, next_ret.loc[date]], axis=1).dropna()`；`len(paired) < 10 → 跳过`；对 paired 两列做 spearman。O 组「IC <10 标的」用例补一条：**构造某标的次日收益 NaN（末日），断言该日 IC 与 dropna 口径一致**。

### P3（3 项）

| 编号 | 发现 | 修法 |
|------|------|------|
| F-I6 | evaluate_gate「返回首个决定性结论」与「reasons 累积全部命中项」表述矛盾；KILL/RECYCLE 行未写 reasons 内容 | 定死：KILL/RECYCLE **立即返回**（reasons = 已累积 + 触发判据）；HOLD/GO 评估完整表后返回（reasons = 全部命中） |
| F-I7 | IMPL 给 `StageEvidence` 加 `warmup_days` / `is_oos_decay` / `account_total` 三字段，DESIGN §3 契约未同步——文档-实现漂移留给 Step 7/8 | DESIGN §3 补三字段行（标注「Step 5 补齐」），§4 偏差表引用 |
| F-I8 | ① `ic_series`/`oos_dates` 含 test 段锚点日（purge gap 末日）——无前视但与「OOS 段日期」声明有口径差；② `allocate` 撤资未校验撤后 `cash >= reserved`（锁定资金保护）；③ 双引擎共享 dm 的只读性未兜底 | ① `oos_dates` 定义为「各 test 段**去锚点日**后的并集」或在 oos docstring 声明；② 撤资校验补一行；③ A 组加 1 条「dm 面板前后逐值相等」断言 |

---

## 4. 核验通过项（不修）

- **C-1 引擎装配链**（V1 三段实证闭环）——factor_files=[] + 注入 combiner + set_signal 是对 setup 守卫的最小侵入路径；
- **C-2 I/O 边界澄清**（V4）——临时目录方案不动 engine_v2，I1 脚注提议合理；
- **C-3/C-4**（V3/V5）——字段名与 segmented 否决均实证；
- **C-7 列子集**（V2）——`signals_frame` 列 ⊆ `dm.stock_codes` 经 reindex 合法；
- **C-9 边界推演**——左锚 clamp W / 右端闭区间 / 整窗预热内 → 空段 → skipped，无崩溃路径；
- **C-8 decay 口径**（逐窗 sharpe 均值 + None 语义）与 D6.3 一致；
- **I7 守恒**：allocate/reserve/release/fill 四操作代数推演全部守恒 ✅；
- **C-12 allocate 注资语义**：取「改 total 不动持仓」自洽且保 I8，作为 DESIGN 留白的实现裁决成立（Step 6 裁决认可）；
- §5 实施顺序（lifecycle → virtual_account → oos → E 组 → 门禁）与「冒烟失败回 Step 4 不打补丁」的风险预案合理。

---

## 5. 出口判定与后续

- **「0 P1」未满足** → 须收敛修复：F-I1 必修（P1 闭环断裂）；F-I2/F-I3 必修（P2 用例空转/必败，属 Step 9 门禁前置）；F-I4/F-I5 必修（P2 文档矛盾与口径漂移）；F-I6..F-I8 建议一并修（文字量小）。
- 修复后：**复验**（定点核验 8 项，不做全文重审——主体装配链/守恒/边界已零命中）或按惯例由用户裁决直进 Step 7。

---

## 6. 复核与修复记录（2026-11-21，作者基座 DeepSeek-V4.1-Flash）

### 6.1 复核结论：8 项全部属实

逐项回读原文与代码，无一误报：

| 编号 | 复核证据 |
|------|----------|
| F-I1 | §3.1 `LEGAL` 代码块（原 L247-253）确无 HOLD 条目；`replay` 原文「按 `apply` 同一张合法表校验」→ 含 HOLD 的 history 重放必抛，**属实** |
| F-I2 | `train_size=252 + purge_gap=5 + test_size=63 - 1 = 319 >= 120` → `split()` 首轮 break；`PERIODS=120`（§3.5）→ 零窗口，**属实** |
| F-I3 | `equal_weight` 输出当日入选标的同权（P-051b C-1）→ spearman 对常数序列 NaN → `ic_series` 空 → 判据 8 触发 `ic` → 永 HOLD；E 组原断言 `evaluate_gate == GO`，**属实** |
| F-I4 | DESIGN D1 原文「三者互不 import（`oos` 不 import `lifecycle`）」，IMPL C-6 反向操作且写「不改 DESIGN」，**属实** |
| F-I5 | stats.py L66-L72 先 `f.dropna()/r.dropna()` 再交集、`len<10 → NaN`；C-10 原用未 dropna 交集，**属实** |
| F-I6 | 原句「返回首个决定性结论；`reasons` 累积全部命中项」自相矛盾；序 3/4 未标「立即」，**属实** |
| F-I7 | DESIGN §3 `StageEvidence` 原无 `warmup_days`/`is_oos_decay`/`account_total`，**属实** |
| F-I8 | `oos_dates` 原定义为「test 段日期并集」含锚点日；`allocate` 撤资仅校验 `cash`；无 dm 只读断言，**属实** |

### 6.2 修复落点

| 编号 | 落点（IMPL） | 连带（DESIGN） |
|------|--------------|----------------|
| F-I1 | §3.1 `apply` 增「HOLD 特判」条目；`replay` 增 hold 放行；`LEGAL` 块注释；§3.4 L/R 行补断言（用例数不变） | — |
| F-I2 | §3.5 显式 `train_size=40/test_size=20/purge_gap=2` + 窗口算术（3 窗，末窗 test_end=idx 101） | — |
| F-I3 | §3.4 E 组改为「非等权 fake 断言 GO」+「四模板只断言合法产出」 | — |
| F-I4 | C-6 口径不变，§4 D-3 行标注已回写 | **D1 例外脚注（L146）** |
| F-I5 | C-10 伪码改 `pd.concat(...).dropna()` 后 `len<10`；O 组补停牌/末日 NaN 断言 | — |
| F-I6 | `evaluate_gate` 增返回语义段；序 3/4 标「立即」 | — |
| F-I7 | C-5 不变 | **§3 `StageEvidence` 三字段（L91-L94）** |
| F-I8 | ① `oos_dates` 排除段首锚点日（C-10 末段）；② `allocate` 撤资补 `total + notional >= reserved`；③ 无前视用例补 dm 面板只读断言 | — |
| D-1 连带 | §4 D-1 行标注 | **I1 例外 + D6.2 脚注（L230）** |

### 6.3 定点复验（8/8 通过）

| 编号 | 复验方式 | 结果 |
|------|----------|------|
| F-I1 | 回读 §3.1 三条（apply 特判 / replay hold 放行 / LEGAL 注释），推演「GO → HOLD → RECYCLE → GO」history 的 replay：HOLD 步 now 放行，其余仍在表内 | ✅ 闭环成立，I9 恢复 |
| F-I2 | 手算窗口：`w0` 0-39/42-61、`w1` 20-59/62-81、`w2` 40-79/82-101、`w3` test_end=122≥120 → 3 窗；`W=10` 小于首窗左锚 41 | ✅ 有窗口、断言有对象 |
| F-I3 | 等权 → IC NaN 的机理与 E 组新设计对齐；GO 用例改用 0.6/0.3 差异化权重 → 非退化 spearman 有定义 | ✅ 断言可成立 |
| F-I4 | DESIGN D1 L146 + I1 L316 + D6.2 L230 三处例外表述互不冲突，D1 实质（无数据耦合）保持 | ✅ 文档级矛盾消解 |
| F-I5 | C-10 与 stats.py L66-L72 逐步同序：dropna → 计数 → 阈值 → corr | ✅ 口径一致 |
| F-I6 | 序 0-4 立即返回 + 序 5-12 全表返回，无「既累积又首个」矛盾 | ✅ |
| F-I7 | DESIGN §3 三字段与 IMPL C-5 / §3.1 引用一致（字段名、类型、默认值） | ✅ |
| F-I8 | ① 锚点日排除后 `oos_dates` 与「OOS 起点」语义一致且 IC 少 3 个非起点日；② 撤资保护代数推演：`total' = total + n >= reserved` 保证总额覆盖锁定资金；③ 断言已并入无前视用例 | ✅ |

### 6.4 结论

**8/8 修复到位，0 P1 / 0 P2 / 0 P3 → Step 6 关闭**。用例数仍 53、pytest 目标 1144（新增断言并入既有条目）；D-1..D-6 六项 DESIGN 补齐中 D-1/D-2/D-3/D-5 已回写 DESIGN，D-4/D-6 为 DESIGN 留白由 IMPL 定案（C-12/C-11），不需改 DESIGN。

**残留风险（Step 9 关注）**：`run_engine` 装配链依赖「注入 combiner 绕过 setup 守卫」这一未在既有测试覆盖的路径——O 组的 `initial_capital<1e6` 冒烟与无前视用例会首次实证；若实测不通过，按 §5 风险预案回 Step 4，不在实现里打补丁。

---

## 7. 二轮异构复审（2026-11-21，GLM-5.3-Flash 复核 DeepSeek 修复稿）

**结论：机制层 0 P1；测试设计 1 P2 + 2 P3（已由核验方顺手修正）**。首轮 8 项中 7 项修复到位且复验引用行号全真；F-I3 方向正确但不完整——非等权权重解决了「IC 恒 NaN」，却漏了「IC 门槛 ≥10 标的」与 2 标的 fixture 的结构性冲突。

### 7.1 修复核验（7 项通过 + 1 项不完整）

| 编号 | 核验证据 | 结果 |
|------|----------|------|
| F-I1 | §3.1 三处落盘（apply HOLD 特判 / replay hold 放行 / LEGAL 注释）；**`GateDecision.target` 字段实证存在**（[DESIGN L119](DESIGN_p051c_strategy_lifecycle.md)）；推演「GO→HOLD→RECYCLE→GO」重放：HOLD 步放行、其余在表内 | ✅ |
| F-I2 | 窗口算术独立重算：w0 train 0-39 / test 42-61 → w2 40-79 / 82-101 → w3 test_end=121≥120 break → **3 窗**；W=11 < 首窗锚点 41；末窗后 18 日可作未来数据 | ✅ |
| F-I3 | 机理修正正确（等权 → spearman 常数 → NaN），但见 **O-2-1** | ⚠ 不完整 |
| F-I4 | DESIGN 三处回写（D1 脚注 L146 / I1 L317 / D6.2 脚注 L230）互不冲突，D1 实质（无数据耦合）保持 | ✅ |
| F-I5 | C-10 `concat+dropna` 与 [stats.py L66-L72](file:///f:/Coding/Factor_Trading_v3.0/strategy_evaluation/stats.py#L66-L72) `f.dropna()/r.dropna() → 交集` 数学等价（both-non-NaN 行集相同）；同序计数 | ✅ |
| F-I6 | 返回语义段：序 0-4 立即 / 5-12 全表；序 1 source 门短路优先，reasons 单判据可接受 | ✅ |
| F-I7 | DESIGN §3 三字段（L91-L94）与 IMPL C-5 字段名/类型/默认值逐字一致 | ✅ |
| F-I8 | ① 落盘（见 O-2-2 分支瑕疵）；② `allocate` 撤资保护代数推演：I7 守恒保持 + `total' ≥ reserved` 保证锁定资金覆盖；③ dm 只读断言并入无前视用例 | ✅ |

**连带新事实断言重验**（修复引入的引用）：

| 断言 | 核验 |
|------|------|
| `decision.target is None`（F-I1） | ✅ [DESIGN L119](DESIGN_p051c_strategy_lifecycle.md) `target: Optional[LifecycleStage]` |
| `aggregate.n_periods`（O 组断言） | ✅ [metrics.py L46](file:///f:/Coding/Factor_Trading_v3.0/core/metrics.py#L46) 字段存在（首查未现系截断，扩查确认） |
| `views_from_data(dm, signal, tradable=..., history_window=W)` 步骤 2 | ✅ [strategy.py L279-285](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L279-L285) `returns_window: int = 0` 有默认——不传不 TypeError；四模板仅消费 close/high/low 历史（P-051a O-3：策略层零 returns 消费） |
| `KILL_from_demote` 内部标记与 replay | ✅ 表内条目仅 apply 内部查；记录落四值 `action="kill"`，replay 查 `(PAPER, KILL): RETIRED` 命中，自洽 |
| `apply(RETIRED, HOLD)` 行为 | ✅ 「RETIRED 任何入参 → 抛」含 HOLD，与 evaluate_gate 序 0（仅评估不迁移）一致 |

### 7.2 二轮发现与处置

| 编号 | 严重度 | 发现 | 处置（核验方顺手修正） |
|------|--------|------|------------------------|
| O-2-1 | **P2** | **E 组 GO 用例仍不可达**：判据 8「`ic_series` **空** → 追加 ic → HOLD」为无条件触发；C-10 `len(pair) < 10 → continue` 在 **2 标的 fixture**（CODES2）下恒触发 → `ic_series` 恒空 → GO 永不可达。F-I3 只修了权重差异化（等权→非等权），没修标的数量——**IC 门槛 ≥10 与 2 标的样本的结构性冲突仍在**。影响面单一：仅 E 组 GO 用例（G 组 IC 用例是 fake evidence 不经 evaluate_strategy；O 组两条 IC 用例本就是「不在 index」的负例断言，2 标的下顺带成立） | E 组 ① 改为 **12 标的 fixture**（`write_price_fixture` codes 传 12 列）+ 横截面差异化权重；四模板 ② 沿用 2 标的且不断言 GO |
| O-2-2 | P3 | `oos_dates` 实现 `seg.index[1:] if len(seg)>1 else seg.index`——else 分支在 len==1 时保留锚点日，与「排除锚点日」定义矛盾；但 len<2 段已被 `window_too_short` 拦截，分支实际不可达（防御代码带语义坑） | 删防御分支，定死 `seg.index[1:]` + 注释「len<2 不进入本函数」 |
| O-2-3 | P3 | DESIGN I1 行「自身代码I/O为零」缺空格 | 已改「代码 I/O」 |

### 7.3 结论

- **机制层（lifecycle 状态机 / apply-replay 闭环 / I7 守恒 / IC 口径 / I/O 边界）：0 P1 / 0 P2，首轮 F-I1 修复闭环成立**；
- **测试设计层**：O-2-1（P2）已修正——E 组 GO 用例在 12 标的 fixture 下可达（IC 每日 spearman = ±1 非空、sharpe/decay 合规、backtest 阶段无 paper/capital 判据）；O-2-2/O-2-3 已顺手修正；
- **Step 6 关闭（0 P1）**。用例数仍 53 / pytest 目标 1144；
- Step 9 实证关注项不变：combiner 注入装配链首测 + 12 标的 fixture 的 IC 正例首测。
