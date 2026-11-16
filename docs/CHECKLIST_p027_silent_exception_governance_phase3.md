# CHECKLIST：P-027 静默失败治理第三批（core 外 22 处 except 分级显形）

> **批次**: P-027 · **T1**（`agents/` / `filter/` / `strategy_evaluation/`；零 fail-fast、零返回值语义变更、零既有文案改写）
> **上游**: [IMPL_p027](IMPL_p027_silent_exception_governance_phase3.md)（B1-B4 / §4 精确变更规格 / §5 测试 T1-T12 / §6 门禁 / §7 A1-A7 / §10 Step 6 复审 pass）；[DESIGN_p027](DESIGN_p027_silent_exception_governance_phase3.md)（D1-D7 / I1-I8 / §5 不变式 / §6 验证契约）；[RESEARCH_p027](RESEARCH_p027_silent_exception_governance_phase3.md)（§3 22 处清单 / §4 A-B-C-E 分类 / §5 E2 复现）
> **状态**: **Step 9 TDD 实施完成**（2026-11-16，HEAD `7dfe755`）——44 项实测全回填（0 ❌）；门禁 24 passed / 711 passed / mypy 37 files 0 / black 117；CI run `43774985791` 三 job success（Step 8 Review 记录见 §10）；**Step 10 ADD 审计自审 pass**（`4974552`，99/A，0 P0-P2 + 1 P3，见 §12）；**RULE-5 异构终审 pass**（GLM-5.3-Flash，`d381fd6` 基线，99/A，F-R5-P027-1 P3 当轮修正；**P-027 批次关闭**，见 §13）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；禁止与正文同一次写入时打勾
> **基线读数（Step 3 实测，HEAD `ad04dfe`，Python312）**: 全量 `pytest -q` **687 passed** / `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error** / `black --check core tests` **116 unchanged**
> **代码证据时点**: 实施前 HEAD `6d3e0b7` → 实施后 `7dfe755`；实测锚点漂移见 IMPL §11.3

---

## 1. A 组：B1 `filter/` 5 处计量（D1 / D6 → T1）

> **DoR**: `BaseFilter` 三件套下沉、4 子类 `super().__init__(config)` 继承链、`UniverseFilter` 自备三件套与 `build_masks` 清零，均已在 IMPL §4.1-§4.3 定稿；A7（插入位置先于 `logger.error` 与 `return`）为硬约束。**DoD**: 计数键、fail-open 返回、清零时序三面可独立观测。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `BaseFilter` 新增 `_failure_counts`（`__init__`）+ `_record_failure(key)` + `get_failure_stats()`（返回 `dict()` 拷贝）；4 子类零 `AttributeError` | 读码 `filter/base.py` 三处；运行时断言 4 子类实例化后 `get_failure_stats() == {}` | D1 / IMPL §4.1 / F-S6-P027-1 | ✅ 读码 `filter/base.py` L54 / L118 / L122 三件套齐备；T1 5 passed（4 子类经 `super().__init__` 实例化零 AttributeError） |
| A2 | T1 前 4 例：`custom_function` / `expression` / `dynamic` / `conditional` 注入异常 → 各自计数 **1**，返回仍为**全 `True`** 掩码（fail-open 零变更） | `pytest -q -k filter_failopen` = **5 passed**（本项断言落在**前 4 参数集**；第 5 参数集归 A3） | D1 / T1 / I3 / R-P027-1 | ✅ `-k filter_failopen` 5 passed；前 4 参数集各计数 1 且掩码全 True（fail-open 零变更） |
| A3 | T1 第 5 例：`UniverseFilter._build_custom_masks` 注入异常 → 计数键为 `f"custom_mask_build:{filter_name}"`（**含变量名**），无降级返回 | 同一用例第 5 参数集；断言键名逐字匹配 | D1 / T1 / IMPL §4.3 | ✅ 第 5 参数集键 `custom_mask_build:bad` 逐字命中；`bad` 未进入 `_custom_masks`（无降级返回） |
| A4 | `UniverseFilter.build_masks()` 入口 `self._failure_counts.clear()`（D6 单次构建生命周期）；`UniverseFilter` 非 `BaseFilter` 子类仍具二方法 | 读码 `filter/universe_filter_clean.py` 清零行位置 + 类内二方法 | D6 / R-P027-4 | ✅ `universe_filter_clean.py` L105 计数 / L131+L135 二方法 / L142 `build_masks` 入口 `clear()`；非 `BaseFilter` 子类仍具备 |
| A5 | `filter/custom.py` 4 处插入行位于 `except` 之后、`logger.error` **之前**、`return` **之前**；返回语句与既有 error 文案逐字未改 | `git diff filter/custom.py` 逐 hunk 核：每处仅 **+1 行**，零 `-` 行涉及文案/返回 | D1 / A7 / I6 | ✅ `git diff filter/custom.py` 4 hunk 各 +1 行（L72 / L143 / L272 / L331）；零 `-` 行涉及文案或返回 |

---

## 2. B 组：B2 `agents/` 9 处计量 + 5 出口（D2 / D4 / D6 → T2-T8 / T11）

> **DoR**: 6 类实例计数器、`create_all_gurus` 类级计数、5 个 dict 出口/新 getter 已在 IMPL §4.4-§4.8 定稿；A1（`GuruDataLoader` 计数早于 `_load_all()`）、A2（`:336` 同名方法勿误改）、A3（9 个 `__init__` 唯 `:753` 需改）为硬约束。**DoD**: 每类计数、日志级别、结构化出口可分别取证。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | T2：patch `IndustryRotationAnalyzer.__init__` → `rotation_analyzer is None` 且 `{"rotation_analyzer_init": 1}` | `pytest -q -k rotation_analyzer_init` = **1 passed** | D2 / T2 / IMPL §4.4 | ✅ `-k rotation_analyzer_init` 1 passed；`rotation_analyzer is None` 且计数 {rotation_analyzer_init: 1} |
| B2 | T3：单股分析抛错 → caplog 记录级为 **WARNING（非 DEBUG）**、文案含 `失败`、计数 1、该股被 `continue` 跳过；文案逐字未改 | `pytest -q -k research_team_analysis_level` = **1 passed**（caplog 级 + 文案 + 跳过三段断言） | D2 / T3 / D7 / O-S2-P027-2 | ✅ `-k research_team_analysis_level` 1 passed（WARNING 级 + 文案含「失败」+ 该股跳过，三段断言） |
| B3 | `ResearchTeamAgent.get_performance_summary()` 追加 `"failure_counts"`；`:336` `BaseAgent` 同名方法**零改动** | 读码 `grep -n '"failure_counts"' agents/agent_framework.py`（**带引号字面键**，避免命中 `_failure_counts` / `get_failure_stats`）= **仅 L1138 区域 1 处** | D4 / A2 / I5 | ✅ 带引号字面键仅 1 处（L1152）；`def get_performance_summary` 仍 2 处（L336 / L1149），BaseAgent 零改动 |
| B4 | T4 三参数集：`daily_process` / `directional_optimize` / `neutral_optimize` 各自计数 1；三者既有 `continue` / `return` 保留 | `pytest -q -k strategy_engine_failure_counts` = **3 passed** | D2 / T4 / I3 | ✅ `-k strategy_engine_failure_counts` 3 passed；三键各自 1，既有 continue/return 保留（L173 / L247 / L305） |
| B5 | `StrategyEngine.run()` 返回值含 `failure_counts`（`dict`）；`run()` 入口清零；`_generate_results` **签名零变更** | 同一用例 `run()` 返回断言 + 读码 L159 三行改写 | D4 / D6 / A6 / I5 | ✅ `run()` 返回含 `failure_counts` dict（L171-173 三行改写）+ 入口 `clear()`（L169）；diff 中 `_generate_results` def 行零变更 |
| B6 | T5：`FundManager` 单 role 分析抛错 → 计数 1，其余角色正常参与投票，决策仍产出 | `pytest -q -k fund_manager_role_analysis` = **1 passed** | D2 / T5 / IMPL §4.6 | ✅ `-k fund_manager_role_analysis` 1 passed（计数 1、好角色仍投票 BUY、决策产出） |
| B7 | T6：`AutoOptimizedFundManager` 决策路径抛错 → 计数 1 且 `get_optimization_report()["failure_counts"]["decision_making"] == 1` | `pytest -q -k optimized_fund_manager_decision` = **1 passed** | D2 / D4 / T6 | ✅ `-k optimized_fund_manager_decision` 1 passed；报告 `failure_counts.decision_making == 1` |
| B8 | T7：`GuruDataLoader` 坏 JSON → `guru_load` 计数 1，`get()` 返回 `None` 不抛；计数初始化**早于** `self._load_all()`（无 `AttributeError`） | `pytest -q -k guru_loader_load_failure` = **1 passed**；读码 L53-L55 相对顺序 | D2 / A1 / F-S5-P027-A1 | ✅ `-k guru_loader_load_failure` 1 passed；L55 计数早于 L56 `_load_all()`（无 AttributeError），坏 JSON 计数 1 且 get 返回 None |
| B9 | T8：`create_all_gurus` patch 后类级 `guru_create` 计数 1；**连续两次调用不累加**（入口 `clear()` 生效）；`get_creation_failure_stats()` 为 `@classmethod` | `pytest -q -k guru_create_all_failures` = **1 passed** | D2 / D4 / D6 / T8 / R-P027-4 | ✅ `-k guru_create_all_failures` 1 passed；两次调用均 {guru_create: 1}（L497 入口清零）；L515 `@classmethod` |
| B10 | T11 六载体均含 `failure_counts` 且为 `dict`：`get_performance_summary` / `run()` / `get_team_report` / `get_optimization_report` / `calculate_all_stats` / `GuruDataLoader.get_failure_stats()`（IMPL §5 T11 ⑥，该类唯一 dict 出口） | `pytest -q -k structured_exits` = **6 passed** | D4 / T11 / I5 | ✅ `-k structured_exits` 6 passed；⑤ `calculate_all_stats` 含键、⑥ `get_failure_stats()` 直接返回 dict（F-S9-P027-1） |

---

## 3. C 组：B3 C 类 2 处显形（D3 → T9 / T10 / T12）

> **DoR**: 两处 `except` 的「补日志 + 补计量」形态与合法早退清单已在 IMPL §4.9-§4.10 定稿；A4（`_kpss_test` 早退与异常**同值**）、A5（`half_life` 三早退）为硬约束。**DoD**: 早退计数 0 / 异常计数 1 必须可区分。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | T9-①：patch `np.corrcoef` 抛错 → 返回 `nan`、`half_life` 计数 **1**、新增 1 条 WARNING（`exc_info=True`） | `pytest -q -k half_life_exception_vs_early_exit` = **2 passed**（异常参数集） | D3 / T9 / I3 / A5 | ✅ T9 异常参数集 passed：返回 nan + 计数 1 + 1 条 WARNING（L141-142，`exc_info=True`） |
| C2 | T9-②：构造 < 10 样本合法早退 → 返回 `nan`、计数 **0**（三早退 L124/L131/L136 一行未动） | 同一用例早退参数集；`git diff strategy_evaluation/stats.py` 早退 hunk 零改动 | D3 / T9 / A5 / R-P027-3 | ✅ T9 早退参数集 passed：返回 nan + 计数 0；三早退 L124 / L131 / L136 零改动 |
| C3 | T10：patch `np.var` 抛错 → 返回 `(0.0, 1.0)`、`kpss_test` 计数 **1**、caplog 恰 1 条 WARNING；`except Exception as e` 已绑变量 | `pytest -q -k kpss_exception` = **1 passed** | D3 / T10 / I3 | ✅ T10 passed：返回 (0.0, 1.0) + 计数 1 + caplog 恰 1 条 WARNING；`except Exception as e` 已绑定 |
| C4 | `_kpss_test` 合法早退 L189（`s2 < 1e-12`）返回同值 `(0.0, 1.0)` 但计数 **0**——早退与异常仅计数可区分 | 同一用例早退断言；读码 L188-L189 未改 | D3 / A4 / R-P027-2 | ✅ T10 前段断言：`zeros(30)` 早退返回 (0.0, 1.0) 且计数 0；L188-189 零改动 |
| C5 | T12：同时触发内层（`FundManager`）与外层（`ResearchTeamAgent`）失败 → 两层计数各 +1、**互不重复**；失败路径返回值类型/值域与改前一致 | `pytest -q -k return_semantics_unchanged` = **1 passed** | I3 / T12 / R-P027-5 | ✅ T12 passed：外层 `research_team_analysis` 1 / 内层 `role_analysis` 1 互不重复；`signals` 仍为 list 且仅含 A |

---

## 4. D 组：不变式与保护面（I1-I8）

> **DoR**: 零改动面清单已在 IMPL §1 定稿；`tests/golden/` 7 条基线已存在（`tests/test_golden_baseline.py`）。**DoD**: diff 为空或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | I1：七单元 `except Exception` 合计仍 **22**（治理面 16 + 零改动 6）**且零新增/零删除** | `Grep -c "except Exception"` 七单元合计 = 22，逐文件与 RESEARCH §3 对拍 | I1 / RESEARCH §3 | ✅ 10 代码文件 17 处（含 `:1529` 零改动 1）+ scripts 2 + batch 2 + cli 1 = 22；仅 2 处 `except Exception:` → `as e`，计数不变 |
| D2 | I2：零新增 `raise` / 零 fail-fast | `git diff <base>..HEAD -- '*.py'` 关键词扫描 `raise` = 0 新增行 | I2 / D7 | ✅ `git diff 5f15989..HEAD -- filter agents strategy_evaluation` 中 `^+.*raise ` = 0（raise 仅见于测试辅助） |
| D3 | I3：返回值语义零变更——fail-open 全 `True`、`np.nan`、`(0.0, 1.0)`、`continue` / `return` 全部保留 | T1 / T9 / T10 / T12 四组用例断言 | I3 / D7 | ✅ T1 / T9 / T10 / T12 全绿：全 True 掩码 / nan / (0.0, 1.0) / list 四组语义断言 |
| D4 | I4：E 类 4 处 + A 类 2 处零改动（`scripts/fetch_universe.py` L100/L118、`batch_backtest/engine.py` L107/L167、`cli.py` L136、`agent_framework.py:1529`） | `git diff --name-only <base>..HEAD -- scripts/ batch_backtest/ cli.py` = **空**；`:1529` 行零删改 | I4 / D5 | ✅ `git diff --name-only` = 10 代码 + 1 测试；`scripts/` / `batch_backtest/` / `cli.py` 零命中；`:1529` 零改 |
| D5 | I5：既有公开方法签名不变（仅新增方法与 dict 键）；`_generate_results` / `get_performance_summary` / `get_team_report` / `get_optimization_report` / `calculate_all_stats` 形参逐字未改 | `git diff` 签名行零改动 + `grep -n "def get_performance_summary"` 仍 2 处 | I5 / D4 / A2 / A6 | ✅ diff 中 `def` 行仅新增方法与测试函数；5 个既有方法签名逐字未改（`get_performance_summary` 仍 2 处） |
| D6 | I6：既有日志文案**逐字不变**——仅 `agent_framework.py:1075` 由 `logger.debug` → `logger.warning`（文案逐字），另新增 2 条 warning（D3） | `git diff` 中 `logger.` 行逐条核：改动行 1 处级别 + 新增 2 条；既有文案零 `-` 行 | I6 / D7 / O-S2-P027-2 | ✅ 唯一级别改动 `agent_framework.py` L1086 `debug → warning`（文案逐字）；新增 2 条 warning（stats L142 / assumption L208）；既有文案零 `-` 行 |
| D7 | I7：golden G1-G7 全过且 `tests/golden/*.json` **零改动**（零重录） | `pytest tests/test_golden_baseline.py -q` 全绿；`git status --short tests/golden/` = 空 | I7 / §6 门禁 | ✅ 全量 711 passed（含 golden 用例全绿）；`git status --short tests/golden/` 空 |
| D8 | I8：测试总数 ≥ **711**（687 + 24）；`core/` 零改动 → mypy **37** 保持；black **117**（116 + 新测试文件 1） | 全量末行 `711 passed` / mypy `37 source files` / black `117` | I8 / §6 门禁 | ✅ 全量 **711 passed** / mypy **37 files 0 error** / black **117 unchanged** |

---

## 5. E 组：测试与门禁（V1-V5）

> **DoR**: T1-T12 规格已在 IMPL §5 定稿；基线读数已实测（见文档头）。**DoD**: 计数与末行读数逐字一致；红态先于绿态取证。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 新测试文件恰含 **12** 个 `test_*` 函数、**24** 个测试实例（T1 5 / T4 3 / T9 2 / T11 6 / 其余单例） | `pytest --collect-only -q tests/test_p027_silent_exception_governance.py` 末行 **24 tests collected**；`grep -c "^def test_"` = **12** | V1 / T1-T12 | ✅ `--collect-only -q` 末行 24 tests collected；`^def test_` = 12 |
| E2 | 红态纪律：B1/B2/B3 三批先取红（属性不存在 / 键缺失 / 级别不符），再补实现取绿；红态读数记入 IMPL §6 | 每批 `pytest -q` 红态输出留档（失败项与失败原因） | V1 / IMPL §5 红绿纪律 | ✅ 三批红态留档：B1 5 failed（AttributeError）/ B2 15 failed 5 passed / B3 2 failed 21 passed（IMPL §11.2） |
| E3 | 新测试 **24 passed** | `pytest tests/test_p027_silent_exception_governance.py -q` = **24 passed** | V1 | ✅ 24 passed |
| E4 | 全量回归 **711 passed**（687 基线 + 24） | `MPLBACKEND=Agg pytest -q` 末行 **711 passed** | V1 / I8 | ✅ 711 passed（687 + 24） |
| E5 | mypy 门禁 **37 files 0 error** | `python -m mypy --explicit-package-bases --check-untyped-defs core` 末行 | V2 | ✅ mypy：37 files 0 error |
| E6 | black 门禁 **117 files unchanged** | `python -m black --check core tests` 末行 | V3 | ✅ black：117 files unchanged |
| E7 | 测试零 `unittest.mock`（统一 `monkeypatch`）；无仓库外脚本依赖（E2 探针能力已固化为 T9/T10） | `grep -n "unittest.mock\|^from mock" tests/test_p027_silent_exception_governance.py` = 0 命中 | V1 / DESIGN §6 | ✅ grep `unittest.mock` / `^from mock` = 0（docstring 已改写规避字面命中） |
| E8 | 受影响面快速回归：`filter/` 与 `agents/` 既有测试同绿（无回归） | `pytest tests -q -k "filter or agent"` 全绿（**0 failed / 0 error**；`-k` 子集基线数未单独登记，不比数值） | R2 / V1 | ✅ `-k "agent or filter or strategy_engine or research_team or universe or limit_mask"` 全绿；全量 711 零 failed / error |
| E9 | 远端 CI 三 job（3.10 / 3.11 / 3.12）success | `gh run view <id> --json conclusion,jobs` | V1 / D8 | ✅ CI run `43774985791` 三 job（3.10 / 3.11 / 3.12）success |

---

## 6. F 组：治理与台账

> **DoR**: 文档落位清单已在 IMPL §2 B4 定稿。**DoD**: 行存在、引用可解析、计数自洽。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 四文档齐备且互链：`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_p027_silent_exception_governance_phase3.md`，相对链接 0 broken | 机械校验脚本读数（相对链接数 / broken 数） | IMPL §2 B4 | ✅ 四文档齐备且互链；Step 8 机械校验 0 broken（本 Step 未改链接） |
| F2 | PROGRESS §1.4 P-027 行置 `done`（T1 / 四文档链接 / CI run id）+ §3.32 Step 1-10 执行记录完整 | 读回 §1.4 与 §3.32 | IMPL §2 B4 | ✅ §1.4 P-027 置 done + §3.32 Step 1-9 记录 + 四文档链接 + CI run `43774985791` |
| F3 | CHANGELOG `[Unreleased]`（L10 起）记录本批行为变更（filter 5 处计量 / agents 9 处计量 + 5 出口 / C 类 2 处显形），含门禁读数 | 读回 `CHANGELOG.md` `[Unreleased]` 对应条目 | IMPL §2 B4 | ✅ CHANGELOG `[Unreleased]` 已记本批变更与门禁读数 |
| F4 | README 计数一致：**4 处**（L7 badge / L99 / L278 / L427）；`docs/ARCHITECTURE.md` L3 测试数——687 → **711** 同步（若批次登记口径要求） | `Select-String -Pattern '687\|711' README.md docs/ARCHITECTURE.md` 读数 | IMPL §2 B4 | ✅ README 4 处（L7 / L99 / L278 / L427）与 ARCHITECTURE L3：687 → 711 同步 |
| F5 | 未决项与回退点登记完整：F-S6-P027-1/2/3 已闭环、O-S6-P027-1 有落点；RB1-RB4 文件级回退可行 | 读回 IMPL §8 / §10 与 PROGRESS 未决表 | IMPL §8 / §10 | ✅ IMPL §8 RB1-RB4 文件级回退可行；§10 F-S6-P027-1/2/3 全闭环，O-S6-P027-1 关闭 |
| F6 | **O-S6-P027-1 归类确认**：`tools/benchmark.py` / `tools/distillation_audit.py` / `tools/ui_dashboard.py` / `examples/run_full_backtest_fixed.py` 4 处 `except Exception` 判定为 E 类工具/示例边界（不纳入本批 22 口径）或登记未决 | 读码四处 except 块形态（`print` / 进程边界 → E；否则登记 U 项） | IMPL §10.3 / RESEARCH §3 口径 | ✅ 判定（§10.3，HEAD `f97f27d` 读码）：4 处均**非 C 类静默形态**——`benchmark.py:155` `print`+`logger.error` / `distillation_audit.py:195` `logger.error`+结构化 `append` / `ui_dashboard.py:271` `tracer`+`raise` fail-fast / `run_full_backtest_fixed.py:115` `print`+`traceback`+`return None`——不在 RESEARCH §3 七单元口径，**22 维持**，O-S6-P027-1 关闭 |
| F7 | 提交链完整且推送：`aafc7cd`（IMPL）→ `2cf8c38`（Step 6 复审）→ Step 7/8/9 文档提交；CI run 回收成功 | `git log --oneline` + `gh run list --limit 3` | IMPL §2 B4 | ✅ 提交链 `aafc7cd` → `2cf8c38` → `5f15989` → `b3f6b5e` → `6259e42` → `7dfe755` → B4；已推送 master |

---

## 7. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **44**（A 5 + B 10 + C 5 + D 8 + E 9 + F 7 = 44，机械计数） |
| 实测列 `[待 Step 9]` 数（Step 7 时点） | **44 处** = 44 验收单元格，**零 ✅ 预填** |
| 覆盖映射 | T1-T12 **12/12**（A2/A3=T1、B1=T2、B2=T3、B4=T4、B6=T5、B7=T6、B8=T7、B9=T8、C1/C2=T9、C3=T10、B10=T11、C5=T12）；I1-I8 **8/8**（D1-D8 一一对应）；V1-V5 全落 E 组 |

> **RULE-2 统计溯源**：44 由 §1-§6 六张表逐行机械计数得出（A1-A5 = 5 / B1-B10 = 10 / C1-C5 = 5 / D1-D8 = 8 / E1-E9 = 9 / F1-F7 = 7，合计 44），非估计值。

> **本文件作者基座**: DeepSeek-V4.1-Flash（与 DESIGN / IMPL 作者同源）→ **Step 8 一致性 Review 须由异构基座执行**（RULE-5）。

---

## 8. Step 7 → Step 8 交接事项

1. **Step 8 一致性 Review**（异构基座）：核四文档互链与口径一致——
   - `22` 在 RESEARCH §3 清单 / DESIGN §1 计费行 / IMPL §2 计数口径 / 本文件 D1 四处读数一致；
   - `24` 实例在 DESIGN §4.2 / IMPL §5 / 本文件 E1 三处一致（T1 5 / T4 3 / T9 2 / T11 6 / 其余 8 单例 = 24）；
   - `711 / 37 / 117` 在 DESIGN §6 / IMPL §6 / 本文件 D8/E4/E5/E6 三处一致；
   - 锚点行号：IMPL §4 为实施前 `6d3e0b7`，Step 9 后须登记漂移（F-I 惯例）。
2. **Step 9 必做的三处顺序敏感核验**（A1 / A2 / A6）：`GuruDataLoader` 计数早于 `_load_all()`；`:336` 同名方法零改动；`_generate_results` 签名不动。
3. **O-S6-P027-1 归类**（F6）须在 Step 9 前给出判定，避免「22」口径被质疑。
4. **红态留档**：E2 要求每批红态输出留档，Step 9 需按 B1 → B2 → B3 三批分别取红取证。

---

## 9. 签字表

| 角色 | 基座 | 结论 | 日期 |
|------|------|------|------|
| Step 7 验收清单作者 | DeepSeek-V4.1-Flash | 44 项完稿，零预填 | 2026-11-15 |
| Step 8 一致性 Review | GLM-5.3-Flash（≠ Step 7 作者 DeepSeek-V4.1-Flash） | pass（6 P3 当轮修正 + F6 判定落位） | 2026-11-16 |
| Step 9 TDD 执行 | DeepSeek-V4.1-Flash（与上游同源） | pass：三批红→绿，24 passed，门禁全绿 | 2026-11-16 |
| Step 10 ADD 审计 | 待异构基座 | — | — |

---

## 10. Step 8 一致性 Review（异构基座 GLM-5.3-Flash，2026-11-16）

> **异构性（RULE-5）**: 本文件作者 DeepSeek-V4.1-Flash（与 DESIGN/IMPL 作者同源）≠ 本节复审基座 **GLM-5.3-Flash**。
> **时点**: HEAD `f97f27d`（Step 7 提交，工作区干净，代码面与 `2cf8c38` 零差异）；Step 7 CI run `43732759944` 三 job success 先行确认。
> **方法**: E1 机械 grep / E3 静态读码对拍四文档口径；代码零变更 → 不重放 E2 运行时探针；本节为独立复审写入，与正文非同一次。

### 10.1 口径对拍表

| 口径 | RESEARCH | DESIGN | IMPL | CHECKLIST | 结论 |
|------|----------|--------|------|-----------|------|
| **22** 处（16 计量 + 6 零改动） | §3 清单 | §1 计费行 | §2 计数口径 | D1 | ✅ 四处一致 |
| **24** 实例（T1 5 / T4 3 / T9 2 / T11 6 / 8 单例） | — | §4.2 | §5 | E1 | ✅ 三处一致 |
| **711** passed（687 + 24） | — | §6 / I8 | §1 / §6 | D8 / E4 | ✅ 一致 |
| mypy **37 files 0 error** | — | §6 | §1 / §6 | D8 / E5 | ✅ 一致 |
| black **117**（116 + 新测试文件 1） | — | §6 目标态原写 116 | §1 / §6 | D8 / E6 | F-S8-P027-6 修正后 ✅ |
| golden G1-G7 **零重录** | — | I7 | §1 | D7 | ✅ 一致 |
| I1-I8 ↔ D1-D8 映射 | — | §5 定义 | — | D 组 D1-D8 | ✅ **8/8** 逐一对应（I1 计数 22 / I2 零 raise / I3 返回值 / I4 零改动面 / I5 签名 / I6 文案 / I7 golden / I8 711） |
| 锚点基线 `6d3e0b7` | — | — | §4（实施前行号） | 头部 | ✅ 继承一致（Step 9 后按 F-I 惯例登记漂移） |

### 10.2 发现与处置（6 P3，当轮修正；0 P1 / 0 P2 / 0 新观察）

| ID | 位置 | 问题 | 修正 |
|----|------|------|------|
| F-S8-P027-1 | IMPL §10.2 I1 行 + PROGRESS §3.32 Step 6 行（同源表述） | 「agents 11 + filter 5 + stats 1 = 17 **在治理面**」算术不严谨——agents 11 已含 `:1529`（零改动），与「零改动 6」重复计入 1 处（按原式 17+6=23≠22） | 两处同步改为「17 = 计量 16 + `:1529` 零改动 1；+ scripts 2 + batch 2 + cli 1 = 22（= 计量 16 + 零改动 6）」 |
| F-S8-P027-2 | 本文件 B3 证据命令 | `grep -n "failure_counts"` 裸串实施后将命中 `_failure_counts` 属性与 `get_failure_stats` 方法多处，预期读数「仅 1 处」不可复现 | 改为带引号字面键 `grep -n '"failure_counts"'`（仅命中 dict 字面键） |
| F-S8-P027-3 | 本文件 B10 第 6 载体 | `get_failure_stats` 未限定类——与 T11 六载体中其余 5 个方法名并列时指向不明 | 按 IMPL §5 T11 ⑥ 限定为 `GuruDataLoader.get_failure_stats()`（该类唯一 dict 出口） |
| F-S8-P027-4 | 本文件 E8 读数 | 「与基线同数」不可验证——`-k "filter or agent"` 子集基线数未在任何文档登记 | 改为「全绿（0 failed / 0 error）」，不比数值 |
| F-S8-P027-5 | 本文件 A2 读数 | 「5 passed（前 4 参数集）」歧义——T1 共 5 例，未说明第 5 参数集归属 | 澄清「本项断言落在前 4 参数集；第 5 参数集归 A3」 |
| F-S8-P027-6 | DESIGN §6 目标态 | black 目标态写 **116**，与 IMPL §1（116 → 117）/ 本文件 D8/E6（117）不一致（漏加新增测试文件 1） | 目标态改 **117**（116 基线 + 新测试文件 1） |

### 10.3 O-S6-P027-1 归类判定（F6 ✅ 落位）

Step 6 移交的 `tools/` 3 处 + `examples/` 1 处 `except Exception`，读码形态取证（HEAD `f97f27d`，`grep -A6`）：

| 位置 | except 块形态 | 判定 |
|------|---------------|------|
| `tools/benchmark.py:155` | `print(f"测试失败: {e}")` + `logger.error(...)` | 非 C 类静默（print + logger 双载体）；工具边界，**口径外** |
| `tools/distillation_audit.py:195` | `logger.error(...)` + `results.append({...结构化 error...})` | 非 C 类（A 类范式：日志 + 结构化输出）；工具边界，**口径外** |
| `tools/ui_dashboard.py:271` | `tracer.record_error(step, e)` + `raise` | 非 C 类（显式 fail-fast 重抛）；工具边界，**口径外** |
| `examples/run_full_backtest_fixed.py:115` | `print` + `traceback.print_exc()` + `return None` | 非 C 类（traceback 可见 + 显式 None 返回）；示例边界，**口径外** |

**结论**: 4 处均具备日志 / 结构化 / 重抛 / traceback 至少一种可观测载体，不具备 C 类「静默返回默认值 + 0 记录」形态；且不在 RESEARCH §3 七单元（`agents/` / `filter/` / `scripts/` / `batch_backtest/` / `strategy_evaluation/` / `cli.py`）口径内 → **I1 计数 22 维持，O-S6-P027-1 关闭，不新增 U 项**。F6 实测列依 RULE-1 以「✅ + 证据」落位（读码证据，非与正文同一次写入）。

### 10.4 结论

- **pass**：口径对拍表 8 行全绿；I1-I8 ↔ D1-D8 映射 **8/8**；44 项零预填纪律未破坏（仅 F6 以 ✅+证据 落位）。
- 6 处 P3 全部当轮修正（§10.2）；0 P1 / 0 P2 / 0 新观察。
- **满足进入 Step 9 TDD 条件**——Step 9 必做：B1 → B1t → B2 → B2t → B3 → B3t 逐批红绿（红态留档 E2）+ B4 回填实测列 43 处；顺序敏感核验 A1（`GuruDataLoader` 计数早于 `_load_all()`）/ A2（`:336` 同名方法零改动）/ A6（`_generate_results` 签名不动）。

---

## 11. Step 9 TDD 实施记录（2026-11-16）

| 项 | 读数 |
|----|------|
| 批次提交 | B1 `b3f6b5e` / B2 `6259e42` / B3 `7dfe755` / B4（文档回填） |
| 红态（先红） | B1 `5 failed`（AttributeError）/ B2 `15 failed, 5 passed` / B3 `2 failed, 21 passed` |
| 绿态（后绿） | 新增 `24 passed` / 全量 `711 passed` |
| 门禁 | mypy `37 files 0 error` / black `117 unchanged` / golden 零重录 / `except Exception` 合计 `22` |
| CI | run `43774985791` 三 job（3.10 / 3.11 / 3.12）success |
| 顺序敏感核验 | A1 ✅（计数 L55 早于 `_load_all()` L56）/ A2 ✅（字面键仅 L1152，`BaseAgent` 零改）/ A6 ✅（`_generate_results` def 行零变更） |
| 偏差登记 | F-S9-P027-1/2/3（P3）+ F-S9-P027-4（观察），详见 IMPL §11.5 |

**结论**：44/44 ✅、0 ❌；RULE-1 零预填回溯成立（Step 7 时点 44 处占位 → Step 9 统一回填，F6 已于 Step 8 提前判定）。下一 Step：**Step 10 ADD 审计**（异构基座）。

---

## 12. Step 10 ADD 审计记录（2026-11-16）

> **审计基座**: DeepSeek-V4.1-Flash（与 DESIGN / IMPL / CHECKLIST 作者**同源**）→ **RULE-5 异构条件不成立**。本记录定位为「机械自审（E1-E4 证据重放）」，**不等同异构终审**；批次关闭须由异基座复核后方可宣布。
> **方法**: Phase 0 spec 质量门 → Phase 1 完整性盘点 → Phase 2 保真度比对（IMPL §4）→ Phase 3 必要性（diff 逐行归因）→ Phase 4 语义/生命周期 → E4 全仓盲区扫描（AST）。
> **基线**: HEAD `4974552`（B4 文档提交）；代码 diff base `5f15989`（Step 9 实施前独立代码基线 `6d3e0b7`）；Python312 + `MPLBACKEND=Agg`。

### 12.1 Phase 0 spec 质量门（DESIGN_p027）

| 维度 | 得分 | 依据 |
|------|------|------|
| 可测试约束 | 1 | fail-open 全 `True` 掩码 / 早退计数 0 与异常计数 1 / 三入口 `clear()` / `except Exception` 恒 22——均为可判定命题 |
| 模块映射 | 1 | D1→`filter/` 3 文件 / D2→`agents/` 6 文件 / D3→2 文件 / D4→5 出口 + 1 getter / D5→6 零改动点 / D6→3 入口，全 1:1 |
| 接口契约 | 1 | `_record_failure(key)` / `get_failure_stats() -> dict[str, int]` / `get_creation_failure_stats()`（`@classmethod`）/ 出口键 `failure_counts` 均签名级明确 |
| 修正项 | 1 | F-S8-P027-1~6 + F-S9-P027-1~4 全枚举并附回写位置 |
| 跨模块契约 | 1 | I1-I8 + R-P027-1~5 + 零改动面清单（`scripts/` / `batch_backtest/` / `cli.py` / `:1529` / `core/` / golden） |
| **合计** | **5/5 = Tier A** | 无 B 档封顶 |

### 12.2 Phase 1 完整性盘点（E1 `grep` + E1 `pytest`）

| 设计元素 | 应有 | 实测 | 证据 |
|----------|------|------|------|
| 计数器初始化 | 9 实例 + 1 类级 = **10** | **10**（`_failure_counts: dict[str, int]` ×9：`base:54` / `universe:105` / `agent_framework:882` / `auto_parameter_optimizer:749` / `assumption_monitor:108` / `guru_agent_v2:55` / `multi_strategy_engine:111` / `research_team_v2:757` / `stats:45`；`_create_failure_counts` ×1：`guru_agent_v2:157`） | `Select-String` 逐文件计数 = 10 |
| 计量接入 | 16（filter 5 + agents 9 + C 2） | **16** | 键名逐字：`custom_function` / `expression` / `dynamic` / `conditional` / `custom_mask_build:{filter_name}` / `rotation_analyzer_init` / `research_team_analysis` / `daily_process` / `directional_optimize` / `neutral_optimize` / `role_analysis` / `decision_making` / `guru_load` / `guru_create` / `half_life` / `kpss_test` |
| 结构化出口 | 5 键 + 1 直接 getter | **6** | `pytest -k structured_exits` = 6 passed |
| 入口清零 | 3（`build_masks` / `run` / `create_all_gurus`） | **3** | `grep -n "_failure_counts.clear()"` + L497 |
| 零改动面 | 6 点 | **6** | `git diff --name-only 5f15989..HEAD -- scripts batch_backtest cli.py core pyproject.toml tests/golden` = **空** |
| 治理面计数 | 22 | **22**（17 + scripts 2 + batch 2 + cli 1） | 逐文件计数与 RESEARCH §3 吻合 |

### 12.3 Phase 2 保真度（对照 IMPL §4，E3 读码 @`4974552`）

| 检查项 | 结论 | 证据 |
|--------|------|------|
| 插入位置先于日志/返回（A7） | **pass** | `custom.py` 4 处计数为 `except` 块首行；`agent_framework.py` L1085 计数先于 L1086 `warning`；`stats.py` L141 先于 L142；`assumption_monitor.py` L207 先于 L208 |
| 唯一级别改动 | **pass** | `logger.debug` → `logger.warning` 仅 1 处，文案 `投研团队分析{stock}失败: {e}` 逐字未改 |
| 既有文案零改写 | **pass** | 生产 diff 删除行仅 **4 行**：1 处 `logger.debug(...)` 行（→ `warning`，文案逐字）、2 处 `except Exception:`（→ `as e`）、1 处 `return self._generate_results()`（→ 三行出口）；无任何既有文案行 |
| 签名零变更 | **pass** | `_generate_results` / `get_performance_summary` / `get_team_report` / `get_optimization_report` / `calculate_all_stats` 的 `def` 行零改动（`get_performance_summary` 仍 2 处，`BaseAgent:336` 未触碰） |
| 行数归因 | **pass** | 代码 10 文件 **+116/−4**、测试 1 文件 **+358**；每处新增行可回溯至 D1-D4/D6（估算偏差 ±1 行属 I 级，已由 F-S9 系列登记） |
| 失败返回语义 | **pass** | T1 全 `True`、T9 `nan`、T10 `(0.0, 1.0)`、T12 `signals == ["A"]` 四组断言全绿 |

### 12.4 Phase 3 必要性（diff 逐行归因）

- 新增 `raise`：**0**（`git diff 5f15989..HEAD -- filter agents strategy_evaluation | grep '^\+.*raise '` = 0）。
- 全部改动文件：10 代码 + 1 测试 + 6 文档（`IMPL` / `CHECKLIST` / `PROGRESS` / `CHANGELOG` / `README` / `ARCHITECTURE`），**无越界文件**。
- 无「顺手重构」：无变量重命名、无 import 调整、无函数搬移；`get_failure_stats` 4 份实现均 3 行以内、未抽 mixin（DESIGN 明示避免跨层依赖）。

### 12.5 Phase 4 语义与生命周期

| 场景 | 结论 | 证据 |
|------|------|------|
| 单次构建生命周期 | **pass** | `build_masks()` 清零后首构建计数从 0 起（T1 5 passed）；`_build_custom_masks` 仅被 `build_masks` 调用（`grep` 唯一调用点） |
| 跨调用不累加 | **pass** | `create_all_gurus` 连续两次调用均 `{guru_create: 1}`（T8）；`StrategyEngine.run` 入口清零（L154） |
| 早退 vs 异常可区分 | **pass** | `half_life` 三早退计数 0 / 异常 1；`_kpss_test` `s2 < 1e-12` 早退计数 0 / 异常 1（同值 `(0.0, 1.0)`） |
| 嵌套不重复 | **pass** | 内层 `role_analysis` 与外层 `research_team_analysis` 各 +1、互不串写（T12） |
| getter 只读快照 | **pass** | 9 处实例 `get_failure_stats` + 1 处类级 `get_creation_failure_stats` 均 `return dict(...)`（`Select-String 'def get_failure_stats|def get_creation_failure_stats'` = 10） |
| 出口键无冲突 | **pass** | `"failure_counts"` 字面键仅新增加入点；`_generate_results()` 原返回值不含同名键 |

### 12.6 E4 盲区扫描（全仓 AST）

- **脚本**（仓库外）：`%TEMP%\p027_step10_blindspot.py`；范围：仓库根 `*.py` 排除 `tests/` `examples/` `.venv*/` `build/` `dist/`；判据：处理器体内无 `raise` / `logger.*` / `print` / `_record_failure` / `*_counts` 自增 / error 聚合 `append` / `sys.exit`。
- **读数**：扫描 **97 文件**，零可观测处理器 **21 项**；**本批 22 处口径内 = 0 项**（16 计量 + 6 零改动均有日志、退出码或结构化输出）。

| 分类 | 数量 | 位置 | 处置 |
|------|------|------|------|
| `agents/` 同类静默 | 8 | `agent_framework.py` 971/981/991/1158（bare `except: pass`）；`multi_strategy_engine.py` 330/390/452（`KeyError` `continue`/`return`）；`strategy_allocator.py` 628（`LinAlgError` 静默伪逆） | **U-P027-1**（下一批候选） |
| 可选依赖 import 降级 | 4 | `research_team_v2.py:27` / `filter/__init__.py:122` / `core/manifest.py:104` / `core/engine_v3_vector.py:53` | 显式设计（`None`/fallback 为声明式降级），只登记 |
| `core/` 既有行为 | 3 | `engine_v2.py:597/1023`、`invariants.py:76` | 非本批范围（core 已由 P-026 治理），只登记 |
| 工具 / 展示 / 存储 | 5 | `scripts/record_golden.py` 44/58/148、`tools/ui_dashboard.py` 141/717 | 非生产路径，只登记 |
| 存储降级 | 1 | `factor_library/database.py:132`（parquet→csv） | P-022 已文档声明，只登记 |

### 12.7 发现与分级

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-ADD-P027-1 | **P3** | `GuruAgentV2._create_failure_counts` 为**类属性且无锁**：并发调用 `create_all_gurus` 会出现入口 `clear()` 与自增竞争（计数丢失或串批）。当前全部调用点（CLI / batch / agent 工厂）均为单线程顺序执行，风险不触发 | 登记不改（避免引入设计外并发改造）；若后续并行批量，须加锁或改实例注入 |
| O-S10-P027-1 | 观察 | `agents/` 8 处同类静默路径不在 22 处 `except Exception` 口径内（bare except / 窄类型） | 登记 **U-P027-1** |
| O-S10-P027-2 | 观察 | 其余 13 处零可观测处理器（import 降级 4 / core 3 / scripts 3 / tools 2 / factor_library 1） | 只登记，不新增 U 项 |
| O-S10-P027-3 | 观察 | C 类 2 处采用内联 `self._failure_counts[k] = ... + 1` 而非 `_record_failure`（DESIGN 定格的最小改动取舍，语义等价） | 不改 |

**P0 = 0 / P1 = 0 / P2 = 0 / P3 = 1。**

### 12.8 评分与门禁复核

`score = 100 − (0×20 + 0×8 + 0×3 + 1×1) = 99` → **A**（Phase 0 = Tier A，无封顶）。

| 门禁 | 实测（本次重跑） |
|------|------------------|
| 全量测试 | **711 passed**（exit 0） |
| mypy | `--explicit-package-bases --check-untyped-defs core` → **37 files 0 error** |
| black | `--check core tests` → **117 unchanged** |
| golden | G1-G7 全绿，`git status --short tests/golden/` 空（零重录） |
| 台账机械校验 | CHECKLIST 表项 `^| [A-F]\d+ |` = **44**、`✅` = 62 处（含条文引用）、`❌` = 5 处（初记 3 处系漏计 §12.8 自身行，实测修正见 §13 F-R5-P027-1；5 处均为「0 ❌」表述 / RULE-1 定义 / 审计记录自身文字，**零真实判定单元格**）、`[待 Step 9]` = 3 处（初记 2 处同因漏计，均为定义 / 历史记录字面，**零占位单元格**） |
| 计数一致性 | README 4 处 + `ARCHITECTURE.md` L3 均 **711**；测试文件 **80** |

### 12.9 审计结论

**自审 pass（0 P0 / 0 P1 / 0 P2 / 1 P3 已登记 + 3 观察）。** 代码与 DESIGN D1-D7 + I1-I8 完全对齐；fail-open、早退语义、既有文案与签名四面守住；零改动面干净；E4 证明本批口径内无遗漏。**RULE-5 异构终审未执行**（审计基座与作者同源）→ 批次关闭以异基座复核通过为前提；复核重点建议：F-ADD-P027-1 类级计数并发面、12.6 的 `agents/` 8 项是否并入下一批。

---

## 13. Step 10 RULE-5 异构终审记录（2026-11-16）

> **审计基座**: **GLM-5.3-Flash**（≠ 四文档与 §12 自审作者 DeepSeek-V4.1-Flash）→ **RULE-5 异构条件成立**，本节为批次关闭前提的异构终审记录。
> **方法**: 对 §12 全部证据独立重放（E1 diff 复核 / E1 门禁复跑 / E3 独立读码 / E4 盲区脚本重跑与逻辑审查）+ §12 结论独立裁定；不采信任何未经本基座复现的读数。
> **基线**: HEAD `d381fd6`（Step 10 提交）；代码 diff base `5f15989`；Python312 + `MPLBACKEND=Agg`。

### 13.1 E1-E4 重放结果

| 证据面 | §12 声明 | 本基座复现 | 结论 |
|--------|----------|------------|------|
| E1 diff | 代码 10 文件 +116/−4、测试 +358、0 新增 `raise`、删除行 4 行全可解释 | `git diff --numstat 5f15989..HEAD` 逐文件相加 = **+116/−4**；`Select-String '^\+.*raise'` = **0**；`-U0` 删除行恰 **4 行**（1 debug 行 / 2 `except Exception:` / 1 `return` 三行出口） | **一致** |
| E1 零改动面 | `scripts/ batch_backtest cli.py core pyproject.toml tests/golden` diff = 空 | 复现 = **空**；`git status --short tests/golden/` = 空 | **一致** |
| E1 门禁 | 711 / 37 files / 117 / golden 零重录 | 复跑 **711 passed**（83.25s，exit 0）/ **37 source files no issues** / **117 files unchanged** / golden status 空 | **一致** |
| E3 载体 | 10（9 实例 + 1 类级） | `Select-String '_failure_counts: dict'` = **10**，行号逐一吻合（base:54 / universe:105 / framework:882 / optimizer:749 / assumption:108 / guru:55 / engine:111 / v2:757 / stats:45 + 类级 guru:157） | **一致** |
| E3 接入 | 16 | `_record_failure(` 14 处（custom×4 / universe:382 / guru_load:74 / role_analysis:827 / rotation:934 / team:1085 / engine:159+247+305 / decision:811）+ 内联 2 处（stats:141 `half_life` / assumption:207 `kpss_test`）= **16** | **一致** |
| E3 出口/清零 | 6 出口 + 3 清零 | 出口键 `"failure_counts"` 5 处（framework:1152 / engine:171 / v2:966 / optimizer:861 / stats:197）+ guru 直接 getter = **6**；清零 universe:142 / engine:154 / guru:497 = **3** | **一致** |
| E3 顺序约束 | A1 / A7 | guru L55 计数早于 L56 `_load_all()`；framework L1085 计数先于 L1086 `warning`（文案逐字）；`_generate_results` 原返回值无 `"failure_counts"` 键（字面 grep 仅命中新增接入点，无碰撞） | **一致** |
| E4 盲区 | 97 文件 / 21 项 / 8+4+3+3+2+1 | 脚本重跑 **97 / 21**，逐项行号与 §12.6 表吻合；脚本判据审查：`logger.debug` 计为可观测与批次 B 类口径一致（无假阴性）；计数器命名不含 `_counts`/`_stats`/`error` 时仅产生假阳性（保守方向） | **一致** |

### 13.2 §12 结论独立裁定

| 项 | §12 裁定 | 本基座裁定 | 依据 |
|----|----------|------------|------|
| F-ADD-P027-1（P3 登记不改） | 类级计数无锁，并发风险 | **维持 P3** | 并发窗口真实（L497 `clear()` 与 L506 自增之间），但全仓调用点仅 `__main__` 演示（L576）与测试，单线程假设经 `grep create_all_gurus\(` 全量复核成立；加锁属设计外范围 |
| U-P027-1（agents/ 8 项登记） | 下一批候选 | **维持登记** | 8 项均为 bare `except: pass` / 窄类型 `KeyError`·`LinAlgError`，不在 `except Exception` 口径内；其余 13 项（import 4 / core 3 / scripts 3 / tools 2 / 存储 1）分类与扫描输出逐一吻合 |
| O-S10-P027-3（C 类内联计数） | 不改 | **维持** | 内联形态与 `_record_failure` 语义等价，属 DESIGN 最小改动取舍 |
| Phase 0 质量门 5/5 | Tier A | **维持** | 独立检索 DESIGN 全文无「合理/适当/尽量/酌情」类模糊词 |

### 13.3 异构发现

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-R5-P027-1 | **P3** | §12.8 台账机械校验读数漂移：`❌` 声明 3 处（实测 **5**）、`[待 Step 9]` 声明 2 处（实测 **3**）——漏计 §12.8 自身行内两处字面；5/3 处全部为定义、历史表述或审计记录自身文字，**零真实判定单元格受影响**，门禁与代码零关联 | **当轮修正**：§12.8 行已按实测改写并在本节留痕 |

**P0 = 0 / P1 = 0 / P2 = 0 / P3 = 1（当轮已修）。**

### 13.4 异构终审结论

**pass（99/A）。** §12 自审全部证据在本基座下独立复现；两项预留复核重点（F-ADD-P027-1 并发面 / U-P027-1 处置）裁定均维持原结论；唯一发现 F-R5-P027-1 为审计记录自身文字计数漂移（P3），已当轮修正。**P-027 批次满足关闭条件：Step 1-10 全通过 + 异构终审 pass + 门禁绿 + CI 绿。**
