# CHECKLIST：P-027 静默失败治理第三批（core 外 22 处 except 分级显形）

> **批次**: P-027 · **T1**（`agents/` / `filter/` / `strategy_evaluation/`；零 fail-fast、零返回值语义变更、零既有文案改写）
> **上游**: [IMPL_p027](IMPL_p027_silent_exception_governance_phase3.md)（B1-B4 / §4 精确变更规格 / §5 测试 T1-T12 / §6 门禁 / §7 A1-A7 / §10 Step 6 复审 pass）；[DESIGN_p027](DESIGN_p027_silent_exception_governance_phase3.md)（D1-D7 / I1-I8 / §5 不变式 / §6 验证契约）；[RESEARCH_p027](RESEARCH_p027_silent_exception_governance_phase3.md)（§3 22 处清单 / §4 A-B-C-E 分类 / §5 E2 复现）
> **状态**: **Step 8 一致性 Review pass**（GLM-5.3-Flash 异构复审，见 §10；6 P3 当轮修正，O-S6-P027-1 判定落位）——实测列 43 处 `[待 Step 9]`（F6 已于 Step 8 判定 ✅），待 Step 9 TDD 回填
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；禁止与正文同一次写入时打勾
> **基线读数（Step 3 实测，HEAD `ad04dfe`，Python312）**: 全量 `pytest -q` **687 passed** / `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error** / `black --check core tests` **116 unchanged**
> **代码证据时点**: HEAD `f97f27d`（Step 7 后，代码面与 `2cf8c38` 零差异）；锚点行号均继承 IMPL §4（实施前 `6d3e0b7`），实施后漂移属预期

---

## 1. A 组：B1 `filter/` 5 处计量（D1 / D6 → T1）

> **DoR**: `BaseFilter` 三件套下沉、4 子类 `super().__init__(config)` 继承链、`UniverseFilter` 自备三件套与 `build_masks` 清零，均已在 IMPL §4.1-§4.3 定稿；A7（插入位置先于 `logger.error` 与 `return`）为硬约束。**DoD**: 计数键、fail-open 返回、清零时序三面可独立观测。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `BaseFilter` 新增 `_failure_counts`（`__init__`）+ `_record_failure(key)` + `get_failure_stats()`（返回 `dict()` 拷贝）；4 子类零 `AttributeError` | 读码 `filter/base.py` 三处；运行时断言 4 子类实例化后 `get_failure_stats() == {}` | D1 / IMPL §4.1 / F-S6-P027-1 | [待 Step 9] |
| A2 | T1 前 4 例：`custom_function` / `expression` / `dynamic` / `conditional` 注入异常 → 各自计数 **1**，返回仍为**全 `True`** 掩码（fail-open 零变更） | `pytest -q -k filter_failopen` = **5 passed**（本项断言落在**前 4 参数集**；第 5 参数集归 A3） | D1 / T1 / I3 / R-P027-1 | [待 Step 9] |
| A3 | T1 第 5 例：`UniverseFilter._build_custom_masks` 注入异常 → 计数键为 `f"custom_mask_build:{filter_name}"`（**含变量名**），无降级返回 | 同一用例第 5 参数集；断言键名逐字匹配 | D1 / T1 / IMPL §4.3 | [待 Step 9] |
| A4 | `UniverseFilter.build_masks()` 入口 `self._failure_counts.clear()`（D6 单次构建生命周期）；`UniverseFilter` 非 `BaseFilter` 子类仍具二方法 | 读码 `filter/universe_filter_clean.py` 清零行位置 + 类内二方法 | D6 / R-P027-4 | [待 Step 9] |
| A5 | `filter/custom.py` 4 处插入行位于 `except` 之后、`logger.error` **之前**、`return` **之前**；返回语句与既有 error 文案逐字未改 | `git diff filter/custom.py` 逐 hunk 核：每处仅 **+1 行**，零 `-` 行涉及文案/返回 | D1 / A7 / I6 | [待 Step 9] |

---

## 2. B 组：B2 `agents/` 9 处计量 + 5 出口（D2 / D4 / D6 → T2-T8 / T11）

> **DoR**: 6 类实例计数器、`create_all_gurus` 类级计数、5 个 dict 出口/新 getter 已在 IMPL §4.4-§4.8 定稿；A1（`GuruDataLoader` 计数早于 `_load_all()`）、A2（`:336` 同名方法勿误改）、A3（9 个 `__init__` 唯 `:753` 需改）为硬约束。**DoD**: 每类计数、日志级别、结构化出口可分别取证。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | T2：patch `IndustryRotationAnalyzer.__init__` → `rotation_analyzer is None` 且 `{"rotation_analyzer_init": 1}` | `pytest -q -k rotation_analyzer_init` = **1 passed** | D2 / T2 / IMPL §4.4 | [待 Step 9] |
| B2 | T3：单股分析抛错 → caplog 记录级为 **WARNING（非 DEBUG）**、文案含 `失败`、计数 1、该股被 `continue` 跳过；文案逐字未改 | `pytest -q -k research_team_analysis_level` = **1 passed**（caplog 级 + 文案 + 跳过三段断言） | D2 / T3 / D7 / O-S2-P027-2 | [待 Step 9] |
| B3 | `ResearchTeamAgent.get_performance_summary()` 追加 `"failure_counts"`；`:336` `BaseAgent` 同名方法**零改动** | 读码 `grep -n '"failure_counts"' agents/agent_framework.py`（**带引号字面键**，避免命中 `_failure_counts` / `get_failure_stats`）= **仅 L1138 区域 1 处** | D4 / A2 / I5 | [待 Step 9] |
| B4 | T4 三参数集：`daily_process` / `directional_optimize` / `neutral_optimize` 各自计数 1；三者既有 `continue` / `return` 保留 | `pytest -q -k strategy_engine_failure_counts` = **3 passed** | D2 / T4 / I3 | [待 Step 9] |
| B5 | `StrategyEngine.run()` 返回值含 `failure_counts`（`dict`）；`run()` 入口清零；`_generate_results` **签名零变更** | 同一用例 `run()` 返回断言 + 读码 L159 三行改写 | D4 / D6 / A6 / I5 | [待 Step 9] |
| B6 | T5：`FundManager` 单 role 分析抛错 → 计数 1，其余角色正常参与投票，决策仍产出 | `pytest -q -k fund_manager_role_analysis` = **1 passed** | D2 / T5 / IMPL §4.6 | [待 Step 9] |
| B7 | T6：`AutoOptimizedFundManager` 决策路径抛错 → 计数 1 且 `get_optimization_report()["failure_counts"]["decision_making"] == 1` | `pytest -q -k optimized_fund_manager_decision` = **1 passed** | D2 / D4 / T6 | [待 Step 9] |
| B8 | T7：`GuruDataLoader` 坏 JSON → `guru_load` 计数 1，`get()` 返回 `None` 不抛；计数初始化**早于** `self._load_all()`（无 `AttributeError`） | `pytest -q -k guru_loader_load_failure` = **1 passed**；读码 L53-L55 相对顺序 | D2 / A1 / F-S5-P027-A1 | [待 Step 9] |
| B9 | T8：`create_all_gurus` patch 后类级 `guru_create` 计数 1；**连续两次调用不累加**（入口 `clear()` 生效）；`get_creation_failure_stats()` 为 `@classmethod` | `pytest -q -k guru_create_all_failures` = **1 passed** | D2 / D4 / D6 / T8 / R-P027-4 | [待 Step 9] |
| B10 | T11 六载体均含 `failure_counts` 且为 `dict`：`get_performance_summary` / `run()` / `get_team_report` / `get_optimization_report` / `calculate_all_stats` / `GuruDataLoader.get_failure_stats()`（IMPL §5 T11 ⑥，该类唯一 dict 出口） | `pytest -q -k structured_exits` = **6 passed** | D4 / T11 / I5 | [待 Step 9] |

---

## 3. C 组：B3 C 类 2 处显形（D3 → T9 / T10 / T12）

> **DoR**: 两处 `except` 的「补日志 + 补计量」形态与合法早退清单已在 IMPL §4.9-§4.10 定稿；A4（`_kpss_test` 早退与异常**同值**）、A5（`half_life` 三早退）为硬约束。**DoD**: 早退计数 0 / 异常计数 1 必须可区分。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | T9-①：patch `np.corrcoef` 抛错 → 返回 `nan`、`half_life` 计数 **1**、新增 1 条 WARNING（`exc_info=True`） | `pytest -q -k half_life_exception_vs_early_exit` = **2 passed**（异常参数集） | D3 / T9 / I3 / A5 | [待 Step 9] |
| C2 | T9-②：构造 < 10 样本合法早退 → 返回 `nan`、计数 **0**（三早退 L124/L131/L136 一行未动） | 同一用例早退参数集；`git diff strategy_evaluation/stats.py` 早退 hunk 零改动 | D3 / T9 / A5 / R-P027-3 | [待 Step 9] |
| C3 | T10：patch `np.var` 抛错 → 返回 `(0.0, 1.0)`、`kpss_test` 计数 **1**、caplog 恰 1 条 WARNING；`except Exception as e` 已绑变量 | `pytest -q -k kpss_exception` = **1 passed** | D3 / T10 / I3 | [待 Step 9] |
| C4 | `_kpss_test` 合法早退 L189（`s2 < 1e-12`）返回同值 `(0.0, 1.0)` 但计数 **0**——早退与异常仅计数可区分 | 同一用例早退断言；读码 L188-L189 未改 | D3 / A4 / R-P027-2 | [待 Step 9] |
| C5 | T12：同时触发内层（`FundManager`）与外层（`ResearchTeamAgent`）失败 → 两层计数各 +1、**互不重复**；失败路径返回值类型/值域与改前一致 | `pytest -q -k return_semantics_unchanged` = **1 passed** | I3 / T12 / R-P027-5 | [待 Step 9] |

---

## 4. D 组：不变式与保护面（I1-I8）

> **DoR**: 零改动面清单已在 IMPL §1 定稿；`tests/golden/` 7 条基线已存在（`tests/test_golden_baseline.py`）。**DoD**: diff 为空或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | I1：七单元 `except Exception` 合计仍 **22**（治理面 16 + 零改动 6）**且零新增/零删除** | `Grep -c "except Exception"` 七单元合计 = 22，逐文件与 RESEARCH §3 对拍 | I1 / RESEARCH §3 | [待 Step 9] |
| D2 | I2：零新增 `raise` / 零 fail-fast | `git diff <base>..HEAD -- '*.py'` 关键词扫描 `raise` = 0 新增行 | I2 / D7 | [待 Step 9] |
| D3 | I3：返回值语义零变更——fail-open 全 `True`、`np.nan`、`(0.0, 1.0)`、`continue` / `return` 全部保留 | T1 / T9 / T10 / T12 四组用例断言 | I3 / D7 | [待 Step 9] |
| D4 | I4：E 类 4 处 + A 类 2 处零改动（`scripts/fetch_universe.py` L100/L118、`batch_backtest/engine.py` L107/L167、`cli.py` L136、`agent_framework.py:1529`） | `git diff --name-only <base>..HEAD -- scripts/ batch_backtest/ cli.py` = **空**；`:1529` 行零删改 | I4 / D5 | [待 Step 9] |
| D5 | I5：既有公开方法签名不变（仅新增方法与 dict 键）；`_generate_results` / `get_performance_summary` / `get_team_report` / `get_optimization_report` / `calculate_all_stats` 形参逐字未改 | `git diff` 签名行零改动 + `grep -n "def get_performance_summary"` 仍 2 处 | I5 / D4 / A2 / A6 | [待 Step 9] |
| D6 | I6：既有日志文案**逐字不变**——仅 `agent_framework.py:1075` 由 `logger.debug` → `logger.warning`（文案逐字），另新增 2 条 warning（D3） | `git diff` 中 `logger.` 行逐条核：改动行 1 处级别 + 新增 2 条；既有文案零 `-` 行 | I6 / D7 / O-S2-P027-2 | [待 Step 9] |
| D7 | I7：golden G1-G7 全过且 `tests/golden/*.json` **零改动**（零重录） | `pytest tests/test_golden_baseline.py -q` 全绿；`git status --short tests/golden/` = 空 | I7 / §6 门禁 | [待 Step 9] |
| D8 | I8：测试总数 ≥ **711**（687 + 24）；`core/` 零改动 → mypy **37** 保持；black **117**（116 + 新测试文件 1） | 全量末行 `711 passed` / mypy `37 source files` / black `117` | I8 / §6 门禁 | [待 Step 9] |

---

## 5. E 组：测试与门禁（V1-V5）

> **DoR**: T1-T12 规格已在 IMPL §5 定稿；基线读数已实测（见文档头）。**DoD**: 计数与末行读数逐字一致；红态先于绿态取证。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 新测试文件恰含 **12** 个 `test_*` 函数、**24** 个测试实例（T1 5 / T4 3 / T9 2 / T11 6 / 其余单例） | `pytest --collect-only -q tests/test_p027_silent_exception_governance.py` 末行 **24 tests collected**；`grep -c "^def test_"` = **12** | V1 / T1-T12 | [待 Step 9] |
| E2 | 红态纪律：B1/B2/B3 三批先取红（属性不存在 / 键缺失 / 级别不符），再补实现取绿；红态读数记入 IMPL §6 | 每批 `pytest -q` 红态输出留档（失败项与失败原因） | V1 / IMPL §5 红绿纪律 | [待 Step 9] |
| E3 | 新测试 **24 passed** | `pytest tests/test_p027_silent_exception_governance.py -q` = **24 passed** | V1 | [待 Step 9] |
| E4 | 全量回归 **711 passed**（687 基线 + 24） | `MPLBACKEND=Agg pytest -q` 末行 **711 passed** | V1 / I8 | [待 Step 9] |
| E5 | mypy 门禁 **37 files 0 error** | `python -m mypy --explicit-package-bases --check-untyped-defs core` 末行 | V2 | [待 Step 9] |
| E6 | black 门禁 **117 files unchanged** | `python -m black --check core tests` 末行 | V3 | [待 Step 9] |
| E7 | 测试零 `unittest.mock`（统一 `monkeypatch`）；无仓库外脚本依赖（E2 探针能力已固化为 T9/T10） | `grep -n "unittest.mock\|^from mock" tests/test_p027_silent_exception_governance.py` = 0 命中 | V1 / DESIGN §6 | [待 Step 9] |
| E8 | 受影响面快速回归：`filter/` 与 `agents/` 既有测试同绿（无回归） | `pytest tests -q -k "filter or agent"` 全绿（**0 failed / 0 error**；`-k` 子集基线数未单独登记，不比数值） | R2 / V1 | [待 Step 9] |
| E9 | 远端 CI 三 job（3.10 / 3.11 / 3.12）success | `gh run view <id> --json conclusion,jobs` | V1 / D8 | [待 Step 9] |

---

## 6. F 组：治理与台账

> **DoR**: 文档落位清单已在 IMPL §2 B4 定稿。**DoD**: 行存在、引用可解析、计数自洽。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 四文档齐备且互链：`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_p027_silent_exception_governance_phase3.md`，相对链接 0 broken | 机械校验脚本读数（相对链接数 / broken 数） | IMPL §2 B4 | [待 Step 9] |
| F2 | PROGRESS §1.4 P-027 行置 `done`（T1 / 四文档链接 / CI run id）+ §3.32 Step 1-10 执行记录完整 | 读回 §1.4 与 §3.32 | IMPL §2 B4 | [待 Step 9] |
| F3 | CHANGELOG `[Unreleased]`（L10 起）记录本批行为变更（filter 5 处计量 / agents 9 处计量 + 5 出口 / C 类 2 处显形），含门禁读数 | 读回 `CHANGELOG.md` `[Unreleased]` 对应条目 | IMPL §2 B4 | [待 Step 9] |
| F4 | README 计数一致：**4 处**（L7 badge / L99 / L278 / L427）；`docs/ARCHITECTURE.md` L3 测试数——687 → **711** 同步（若批次登记口径要求） | `Select-String -Pattern '687\|711' README.md docs/ARCHITECTURE.md` 读数 | IMPL §2 B4 | [待 Step 9] |
| F5 | 未决项与回退点登记完整：F-S6-P027-1/2/3 已闭环、O-S6-P027-1 有落点；RB1-RB4 文件级回退可行 | 读回 IMPL §8 / §10 与 PROGRESS 未决表 | IMPL §8 / §10 | [待 Step 9] |
| F6 | **O-S6-P027-1 归类确认**：`tools/benchmark.py` / `tools/distillation_audit.py` / `tools/ui_dashboard.py` / `examples/run_full_backtest_fixed.py` 4 处 `except Exception` 判定为 E 类工具/示例边界（不纳入本批 22 口径）或登记未决 | 读码四处 except 块形态（`print` / 进程边界 → E；否则登记 U 项） | IMPL §10.3 / RESEARCH §3 口径 | ✅ 判定（§10.3，HEAD `f97f27d` 读码）：4 处均**非 C 类静默形态**——`benchmark.py:155` `print`+`logger.error` / `distillation_audit.py:195` `logger.error`+结构化 `append` / `ui_dashboard.py:271` `tracer`+`raise` fail-fast / `run_full_backtest_fixed.py:115` `print`+`traceback`+`return None`——不在 RESEARCH §3 七单元口径，**22 维持**，O-S6-P027-1 关闭 |
| F7 | 提交链完整且推送：`aafc7cd`（IMPL）→ `2cf8c38`（Step 6 复审）→ Step 7/8/9 文档提交；CI run 回收成功 | `git log --oneline` + `gh run list --limit 3` | IMPL §2 B4 | [待 Step 9] |

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
| Step 9 TDD 执行 | 待填 | — | — |
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
