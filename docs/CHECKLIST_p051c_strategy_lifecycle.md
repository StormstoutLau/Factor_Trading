# CHECKLIST：P-051c 策略生命周期（lifecycle / oos / virtual_account）

> **批次**: P-051c · **Step 7** · 日期 2026-11-21 · **判档 T1**
> **上游**: [IMPL_p051c](IMPL_p051c_strategy_lifecycle.md)（C-1..C-12 / 三模块逐处代码 / 53 用例映射 / §4 六项补齐 + 8 项修复回执）；[DESIGN_p051c](DESIGN_p051c_strategy_lifecycle.md)（D1-D12 / I1-I11 / 20 项裁决）；[REVIEW_p051c_step6_impl](REVIEW_p051c_step6_impl.md)（首轮 1 P1+4 P2+3 P3 → 8/8 修复 → 二轮 0 P1，O-2-1/O-2-2/O-2-3 已修）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；**禁止预填**
> **状态**: Step 9 执行完成（2026-11-21），M10 + T7 + C6 + I11 + D12 = **46 项全部 ✅**，`[待 Step 9]` 清零
> **基线读数（@`53db4f7`，P-051b 关闭态）**: pytest **1091** / `-k golden` **22** / mypy **119 files 0** / black `--check .` **240** / `tests/*.py` **120** / `core/*.py` **45**
> **实测读数**: pytest **1144**（+53）/ `-k golden` **22** / mypy **122 files 0** / black `--check .` **247** / `tests/*.py` **124** / `core/*.py` **48**

---

## 1. M 组：模块与代码（10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| M1 | `core/lifecycle.py` 新建：`LifecycleError(ValueError)` + `LifecycleStage`/`GateAction` 两枚举 + 7 契约（`StrategyFingerprint`/`StageEvidence`/`ReadinessCriteria`/`ValueCriteria`/`GateCriteria`/`GateDecision`/`TransitionRecord`/`LifecycleRecord`）+ 6 函数（`initial_record`/`evaluate_gate`/`apply`/`archive`/`replay`/`resolve_monitor_action`）；`__all__` 与 §3.1 一致；**`StageEvidence` 含 `warmup_days`/`is_oos_decay`/`account_total` 三字段**（DESIGN §3 L91-L94） | 无 | 读码 + M2-M7 | ✅ `core/lifecycle.py` L48 异常 / L52-L65 两枚举 / L86-L203 七契约（StageEvidence L102-L116 三字段齐） / L205/L231/L333/L428/L468/L495 六函数；`__all__` L24-L45 |
| M2 | `_GO_TARGET` 四段链 + `LEGAL` 表（GO×4 / RECYCLE×1 / KILL×3 + 内部 demote）；（LIVE, GO）→ `LifecycleError("live 为最高阶段")`；RETIRED 任何入参 → 抛 | M1 | 读码 + L1-L5/L14 | ✅ `core/lifecycle.py` L68-L84 两表（GO×4/RECYCLE×1/KILL×3）；L359 (LIVE,GO) 抛；L347 RETIRED 抛；L1-L7 全绿 |
| M3 | **HOLD 特判**：`decision.target is None` 校验 + 落 `from==to` 记录 + **不查 LEGAL**；`replay` 对 `(hold, from==to)` 放行（REVIEW F-I1） | M2 | 读码 + L6/L14-R4 | ✅ `core/lifecycle.py` L350-L356 HOLD 特判（target 校验 L352、from==to、不查 LEGAL）；L468-L486 replay hold 放行；L3/L14/R4 绿 |
| M4 | KILL：paper 一步落 1 条、gray/live 两步（demote→paper 再 retire）落 2 条；RECYCLE：`new_version` 须区别于 history 全部 version + 当前 version，成功后 `replace(fingerprint, version=...)`（F-D7） | M2 | 读码 + L7-L8/L11-L13 | ✅ `core/lifecycle.py` L379-L385 KILL paper 1 条；L386-L395 gray/live 两步（L386 `kill_trigger`）；L322-L331 版本唯一性；L4-L6/L9-L11 绿 |
| M5 | `evaluate_gate` 12 序判定与 DESIGN D4/D5 逐条对应；返回语义：序 0-4 **立即**、序 5-12 全表后返回；序 1 `source != "paper_record"` 在 PAPER 段短路（I6） | M1 | 读码 + G1-G10 | ✅ `core/lifecycle.py` L231-L296 全序；L239-L262 序 0-4 立即返回；L240-L241 source 短路；G1-G10 绿 |
| M6 | `archive` → `{"schema_version":1, "fingerprint", "final_stage", "history", "account", "unresolved"}`；递归校验 float 有限，含 NaN/Inf → `LifecycleError`（I10） | M1 | 读码 + R1-R3 | ✅ `core/lifecycle.py` L428-L458 六键齐；L408-L426 递归有限校验（L421 抛 NaN/Inf）；R1-R3 绿 |
| M7 | `replay` 校验 `from_stage` 链 + 动作查表（hold 例外），返回 `tuple(to_stage)`；链断/非法动作 → `LifecycleError`（I9） | M3 | 读码 + R4-R5 | ✅ `core/lifecycle.py` L468-L492 链校验 + 查表；R4/R5 绿 |
| M8 | `core/virtual_account.py` 新建：`VirtualAccount`（`cash`/`reserved`/`positions`/`total` + `__post_init__` I7 守恒 1e-9）+ `allocate`/`try_reserve`/`release`/`fill`（全部返回新实例）+ `BudgetCheck` + `check_allocation` + `check_book`；**不 import lifecycle** | 无 | 读码 + A1-A10 | ✅ `core/virtual_account.py` L25-L103 账户（L53 守恒 1e-9）；L59/L71/L81/L91 四变更加；L105-L136 `BudgetCheck`/`check_allocation`/`check_book`；全文件零 core import |
| M9 | `core/oos.py` 新建：`OOSReport`/`WindowOutcome`/`run_engine`/`evaluate_strategy`/`to_evidence`；`run_engine` = `factor_files=[]` + 注入 `_NullCombiner` + `setup()` + `set_signal(mode="weights")` + `TemporaryDirectory` 承接引擎写盘 + `write_manifest=False` + `<1e6` 抛 `LifecycleError`（C-1/C-2/C-3）；`evaluate_strategy` 签名含必填 `min_history`（U-P051c-20） | M1/M5 | 读码 + O1-O11 | ✅ `core/oos.py` L42/L53 两契约；L67 `_NullCombiner`；L82-L119 `run_engine`（L106 `write_manifest=False`、L110 临时目录、L114 weights 注入）；L166-L272 `evaluate_strategy`（L178 min_history 守卫）；L275-L294 `to_evidence`；O1-O11 绿 |
| M10 | **零改动**：`core/engine_v2.py`、`core/strategy.py`、`core/walk_forward.py`、`core/metrics.py`、`core/config.py`、`core/registry.py`、`core/sizing.py`、`core/stops.py`、`strategies/*`、`tests/_golden_cases.py`、`core/__init__.py` | 无 | `git diff --stat` | ✅ `git diff --stat` 对 11 文件 + `.github/workflows/tests.yml` 输出为空（2026-11-21 实测） |

---

## 2. T 组：测试（4 文件 / 53 条）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| T1 | `tests/test_p051c_lifecycle.py` **L1-L14** 全绿：四段 GO 链 / (LIVE,GO) 抛 / HOLD 原地落记录（含 `target is None` 校验）/ RECYCLE 新版本 / 版本重复抛 / 非法迁移 / RETIRED 终态 / KILL paper 一步 / KILL gray 两步 / KILL live 两步 / I5 确定性 | M2-M4 | pytest | ✅ `pytest tests/test_p051c_lifecycle.py -q` → **29 passed**（L14+G10+R5）；L1-L14 覆盖全部列项 |
| T2 | 同文件 **G1-G10** 全绿：sharpe<0 → KILL/RECYCLE 分阶段 / sharpe 不足 → backtest RECYCLE / drawdown 超阈 → HOLD / >2× → KILL / decay 超限 → HOLD / decay None → `insufficient_signal` / IC 不足 → HOLD / paper_days+paper_trades 双条件 → HOLD / source 门 → HOLD / capital 门 → HOLD；**断言语义与 M5 返回语义一致（0-4 立即）** | M5 | pytest | ✅ 同一命令 29 passed 中 G1-G10 全绿（G1 同时断言 RECYCLE/KILL 分阶段） |
| T3 | 同文件 **R1-R5** 全绿：archive 结构含 `schema_version` / JSON 往返相等 / 含 NaN → 抛 / replay 前缀收敛（**含 HOLD 记录放行、不查 LEGAL**）/ from_stage 链断 → 抛 | M6/M7 | pytest | ✅ 同一命令 29 passed 中 R1-R5 全绿 |
| T4 | `tests/test_p051c_oos.py` **O1-O11** 全绿：searchsorted 非交易日端点 / 左锚 clamp W / short-window → `window_too_short` 且 Gate HOLD / 聚合段首归一 / decay None / IC 全零日 / IC <10（含末日/停牌 NaN 的 dropna 有效对数，F-I5）/ min_history<1 抛 / initial_capital<1e6 抛 / 预热段排除（`aggregate.n_periods`）/ 无前视（未来 +50% 不改过去段指标 + dm 面板只读，F-I8③） | M9 | pytest | ✅ `pytest tests/test_p051c_oos.py -q` → **11 passed**（O1-O11 逐条对应） |
| T5 | `tests/test_p051c_virtual_account.py` **A1-A10** 全绿：I7 守恒 / reserve 成功/不足 / release / fill 入账 / fill 差额两步守恒 / fill 超 reserved 抛 / allocate 不动 positions（I8）/ check_allocation 三类 violation / check_book Σ 超限 / 全链路守恒 | M8 | pytest | ✅ `pytest tests/test_p051c_virtual_account.py -q` → **10 passed** |
| T6 | `tests/test_p051c_end_to_end.py` **E1-E3** 全绿：①GO 全链 = 非等权 fake + **12 标的 fixture**（O-2-1）→ `evaluate_gate == GO`；②四模板参数化（4 例计 1 条）仅断言合法 `OOSReport` + 可构造 evidence + 合法 `GateAction`（**不断言 GO**）；③golden 22 条零重录 | M9 + A/B/C | pytest | ✅ `pytest tests/test_p051c_end_to_end.py -q` → **3 passed**（E2 内部单函数循环 4 模板计 1 条）；E1 实测 `GO → PAPER`（sharpe 7.04 / dd 0.065 / decay 0.022 / IC 尾部均值 1.0）；E3 锁 16 个 golden JSON 清单 |
| T7 | 用例数 **53**（14+10+5+11+10+3）；总 pytest = 1091+53 = **1144**；无 `@pytest.mark.skip` / `xfail` 新增 | T1-T6 | pytest 计数 | ✅ 收集 29（lifecycle）+24（oos 11 / virtual 10 / e2e 3）= **53**；全量 **1144 passed**；四新文件无 skip/xfail |

---

## 3. C 组：门禁（6 项）

| ID | 门禁 | 命令 | 目标 | 实测 |
|----|------|------|------|------|
| C1 | pytest 全量 | `.\.venv\Scripts\python.exe -m pytest -q`（`$env:MPLBACKEND='Agg'`） | **1144 passed** | ✅ `1144 passed in 129.07s`（2026-11-21 复验，+53） |
| C2 | golden | `.\.venv\Scripts\python.exe -m pytest -q -k golden` | **22 passed**（零重录） | ✅ `22 passed, 1122 deselected`（零重录） |
| C3 | mypy | `-m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation strategies cli.py order_strategy web factor_library tools examples` | **122 files, 0 error** | ✅ `Success: no issues found in 122 source files` |
| C4 | black | `-m black --check .` | **247 files unchanged** | ✅ `247 files would be left unchanged` |
| C5 | 无新增 golden 目录 | `git status --porcelain tests/golden` | 输出为空 | ✅ 输出为空（无新增/改动 golden 文件） |
| C6 | 零新依赖 | `git diff --stat requirements*.txt pyproject.toml` | 空（仅用 pandas/numpy/tempfile 标准库） | ✅ `git status --porcelain -- pyproject.toml requirements*.txt` 输出为空 |

---

## 4. I 组：不变式（11 项，对应 DESIGN I1-I11）

| ID | 不变式 | 证据出口 | 实测 |
|----|--------|----------|------|
| I1 | 三模块自身零 I/O、零 logging、无全局状态；**唯一受控例外** = `run_engine` 经引擎写临时目录并返回前销毁（DESIGN I1 例外 + D6.2 脚注） | grep `open(\|to_csv\|requests\.\|logging` 三文件 + O10 | ✅ grep 仅命中 docstring（`core/lifecycle.py` L3-L4）；`core/oos.py` L110 唯一 `TemporaryDirectory` 且 `with` 返回前销毁、L106 `write_manifest=False`；三文件无模块级可变全局 |
| I2 | 状态机迁移闭包：任意 `(stage, action)` 要么在 `LEGAL`/HOLD 特判内成功，要么抛 `LifecycleError`，无第三态 | L1-L14 | ✅ `tests/test_p051c_lifecycle.py` 29 passed；`test_l7_illegal_transitions_raise`（3 组非法组合全抛）+ L1-L14 全绿 |
| I3 | 退役唯一入边 = paper：gray/live 的 KILL 必落两条记录、paper 自身一步 | L11-L13 | ✅ `test_l9_kill_from_paper_one_record` / `test_l10_kill_from_gray_two_records` / `test_l11_kill_from_live_two_records` 全绿；实现 `core/lifecycle.py` L379-L395 |
| I4 | 时间只由调用方传入（`at` 字符串），模块内无 `datetime.now`/`time.time` | grep + R1 | ✅ grep `datetime.now\|time.time` 三文件仅命中 docstring（`core/lifecycle.py` L4/L171）；`test_l12_at_validation` 校验非法 `at` 抛 |
| I5 | 确定性：同输入两次结果全等；无 set 迭代序依赖（reasons 保序） | L14 / G* | ✅ `test_l14_deterministic` 全等断言通过；`reasons` 由有序元组拼接（`core/lifecycle.py` L231-L296） |
| I6 | 证据来源门：PAPER 段 `source != "paper_record"` → 不晋级（HOLD） | G10 | ✅ `test_g9_source_gate_holds`（source 门）+ `test_g10_capital_gate_holds`（capital 门）全绿；实现短路 `core/lifecycle.py` L240-L241 |
| I7 | 账本守恒：任一操作后 `cash + reserved + Σpositions == total`（1e-9），且三项非负 | A1-A10（逐操作） | ✅ `tests/test_p051c_virtual_account.py` 10 passed；A1 守恒校验 + A2-A10 每步断言；实现 `core/virtual_account.py` L34-L57（L53 1e-9 守卫） |
| I8 | `allocate` 与 `try_reserve` 分属两层、不重复记账（allocate 不动 positions/reserved） | A7 | ✅ `test_a8_allocate_leaves_positions_and_reserved`（allocate 不动 positions/reserved）；另 `test_a7_fill_over_reserved_raises` 锁超 reserved 抛；实现 L59-L68 |
| I9 | 任意前缀重放收敛：`replay(history[:k]) == stage_k`；HOLD 记录可重放 | R4 | ✅ `test_r4_replay_prefix_converges_with_hold` 全绿；实现 `core/lifecycle.py` L468-L492 |
| I10 | 归档 JSON 往返稳定、不含 NaN/Inf | R2/R3 | ✅ `test_r2_archive_json_roundtrip` / `test_r3_archive_rejects_nan` 全绿；实现 L408-L426（L421 NaN/Inf 抛） |
| I11 | 既有 1091 用例零回归 + 引擎/策略/指标/窗口/配置零 diff | M10 + C1 | ✅ C1 `1144 passed`（=1091+53，零回归）；M10 `git diff --stat` 11 文件 + workflow 输出为空 |

---

## 5. D 组：裁决与设计决策落实（12 项；§0 全 20 项在 Step 8 逐条交叉核对）

| ID | 决策 | 落实点（可核对位置） | 实测 |
|----|------|----------------------|------|
| D1 | 三模块划分、互不 import（唯一例外 `LifecycleError` 类型） | `core/{lifecycle,oos,virtual_account}.py` docstring + grep import | ✅ `core/lifecycle.py` L10-L21 仅 import `core.metrics.MetricsResult`；`core/virtual_account.py` L6-L10 **零 core import**；`core/oos.py` L28 仅 import `LifecycleError, StageEvidence`（C-6 例外，契约类型） |
| D2 | 状态机与退役唯一入边 + HOLD 特例 | M2/M3/M4 + L1-L14 | ✅ `core/lifecycle.py` L68-L84 两表 / L350-L356 HOLD 特判 / L347 RETIRED 抛 / L379-L395 KILL 分支；L1-L14 全绿 |
| D3 | 判据顺序（oos_sharpe → drawdown → decay → ic → paper_* → capital） | M5 + G1-G10 | ✅ `core/lifecycle.py` L231-L296 十二序（序 0-4 立即返回 L239-L262，序 5-12 全表后返回）；G1-G10 全绿 |
| D4 | 四决策 Go/Kill/Hold/Recycle 语义 | M2/M5 + L*/G* | ✅ `GateAction` L61-L65 四值；`evaluate_gate` 返回四决策；L1-L14 / G1-G10 全绿 |
| D5 | paper 阶段证据注入（`StageEvidence.source`） | M1/M5 + G10 | ✅ `StageEvidence` L102-L116 含 `source`；L240-L241 source 门；`test_g9_source_gate_holds` 绿 |
| D6 | OOS 产出器（D6.1-D6.4 四段规格） | M9 + O1-O11 | ✅ `core/oos.py` L82-L119 `run_engine` / L122-L126 `_segment` / L129-L153 `_cross_sectional_ic` / L156-L164 `_chain_segments` / L166-L272 `evaluate_strategy` / L275-L294 `to_evidence`；O1-O11 全绿 |
| D7 | 虚拟子账户纯账本（4 变更 + 2 校验） | M8 + A1-A10 | ✅ `core/virtual_account.py` L59/L71/L81/L91 四变更 + L112/L133 两校验；A1-A10 全绿 |
| D8 | 指纹与版本（RECYCLE 新版本唯一性） | M4 + L7/L8 | ✅ `core/lifecycle.py` L322-L331 `_recycle_version` 唯一性校验；`test_l4`/`test_l5`/`test_l6` 全绿 |
| D9 | 归档快照（JSON 稳定） | M6 + R1-R3 | ✅ `core/lifecycle.py` L428-L458 六键快照；R1-R3 全绿 |
| D10 | 监控级别 → 动作映射（字符串入参，不 import agents） | M1 `resolve_monitor_action` + G 组 | ✅ `core/lifecycle.py` L495-L511 纯字符串入参、零 agents import；断言并入 `test_l8_retired_is_terminal` 尾段 |
| D11 | 重放审计（I9） | M7 + R4/R5 | ✅ `core/lifecycle.py` L468-L492；R4/R5 全绿 |
| D12 | 月度归因外置（本批不实现） | grep 无 Brinson/Menchero 实现 | ✅ 三新模块 grep `Brinson\|Menchero` **零命中**；既有 `core/attribution.py` 未改动（`git diff --stat` 空） |

**本批有代码落点的 20 项裁决索引**：U-P051c-1（纯函数核，M1）· 2（证据注入式 paper，M5）· 3（纯账本，M8）· 4（不接引擎，M10）· 12（归因外置，D12）· 13（指纹，M4）· 16（四决策，M2/M5）· 17（continuous 切段，M9）· 18（segmented 不做，M9）· 19（预热排除 + `warmup_days`，M1/M9）· 20（`min_history` 显式参数，M9）。其余 9 项为设计/边界裁决，无独立代码落点，Step 8 交叉核对。

---

## 6. 出口判定

- **Step 9 判据**：M/T/C/I/D 五组 **46 项全部 ✅**（`[待 Step 9]` 清零）；
- **任一 ❌** → 记录证据并回 Step 5/6（不打补丁式修复）；
- **实测读数**回填 §7，再进 Step 8 一致性检查。

## 7. 实测读数（Step 9 回填）

| 指标 | 基线 @`53db4f7` | 目标 | 实测 |
|------|------------------|------|------|
| pytest 全量 | 1091 | 1144 | ✅ **1144 passed** in 129.07s |
| `-k golden` | 22 | 22（零重录） | ✅ **22 passed**, 1122 deselected |
| mypy | 119 files / 0 | 122 files / 0 | ✅ **122 source files, 0 error** |
| black `--check .` | 240 | 247 unchanged | ✅ **247 files would be left unchanged** |
| `tests/*.py` | 120 | 124 | ✅ **124** |
| `core/*.py` | 45 | 48 | ✅ **48** |
