# CHECKLIST：P-026 静默失败治理第二批（因子链路 / 插件 / 传染 / 事件日志 / Walk-Forward）

> **批次**: P-026 · **T1**（`core/` 行为契约 + 新增可观测字段与方法，零 fail-fast）
> **上游**: [IMPL_p026](IMPL_p026_silent_exception_governance.md)（B1-B5 / §4 精确变更实录 / §6 门禁 / §10 Step 6 复审）；[DESIGN_p026](DESIGN_p026_silent_exception_governance.md)（D1-D8 / I1-I7 / V1-V6 / T1-T12）
> **状态**: Step 7 完稿（**45 项**零预填；实测列全部 `[待 Step 9]`）+ **Step 8 一致性 Review pass**（2026-11-13，异构基座 GLM-5.3-Flash；2 P3 修复 + 1 观察，见 §11）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；禁止与正文同一次写入时打勾
> **基线读数（Step 7 实测）**: `pytest --collect-only tests/test_p026_silent_exception_governance.py` **16 tests collected** / 全量 **687 passed**（671 + 16）/ mypy **37 files 0** / black **116 unchanged**

---

## 1. A 组：B1 因子链路（D1 → T1-T6）

> **DoR**: `factor.py` 三接口与两处 except 形态、`diagnostics.py` 的 `STAGES` 与 `classify_day_error` 分支、`engine_v2.py` 注入时点均已在 IMPL §4.1-§4.3 定稿；F-D-P026-2（注入须早于 `_precompute_factors()`）为硬性约束。**DoD**: 每项有 pytest 用例名或可读码行锚点，读数逐字可比。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | T1 参数化 5 例全过：`LinAlgError→("solver", False)`；`ValueError`/`KeyError`/`FileNotFoundError→("data", False)`；`TypeError→("internal", False)` | `pytest tests/test_p026_silent_exception_governance.py -q -k t1` = **5 passed**（5 参数集逐字相等） | D1.3 / T1 / V1 | [待 Step 9] |
| A2 | `STAGES` 含 `"factor"` 且位于 `"rebalance"` 与 `"mark"` 之间（词表契约；无运行时使用） | 读码 `core/diagnostics.py` `STAGES` 元组 11 值；`grep -n "factor" core/diagnostics.py` 命中 L31 注释 + L72 分支 | D1.3 / F-D-P026-3 | [待 Step 9] |
| A3 | `FactorPipeline` 三接口形态：`set_error_sink(sink)`；`neutralize_skip_counts` 属性返回 **dict 拷贝**（`is not` 内部对象）；`_report_error(date, exc)` **无 `reason` 死参数** | 读码 `core/factor.py` L41-L64 三处；断言 `pipeline.neutralize_skip_counts is not pipeline._neutralize_skip_counts` | D1.1 / F-S4-P026-1 | [待 Step 9] |
| A4 | T2 未注入 sink：`process()` 正常返回，双计数保持 `{"degenerate_columns": 0, "regression": 0}` | `pytest -q -k t2` = **1 passed**（字典逐字相等） | D1.1 / T2 / I2 | [待 Step 9] |
| A5 | T3 去常数列失败：认证计数 `degenerate_columns >= 1`，sink 收到 `stage == "factor"`，日志级 **WARNING** 且文案「去常数列失败，跳过中性化」 | `pytest -q -k t3` = **1 passed**（caplog 级 + 文案断言） | D1.2 / T3 / D8 / V5 | [待 Step 9] |
| A6 | T4 回归失败：`regression >= 1`，且该日结果帧与输入**完全相等**（整日跳过语义未变） | `pytest -q -k t4` = **1 passed** | D1.2 / T4 / V5 | [待 Step 9] |
| A7 | T5 端到端：`sink_was_set is True`（注入早于 `_precompute_factors()`）、`counts["factor"] >= 1`、`degraded is True`；正常路径 `counts` **无** `factor` 键 | `pytest -q -k t5` = **1 passed**；读码 `core/engine_v2.py` 注入行位于 `self._precompute_factors()` **之前** | D1.4 / T5 / V5 / F-D-P026-2 | [待 Step 9] |
| A8 | T6 fake pipeline（无 `set_error_sink`）：`setup()` 不抛错（`getattr` 探测生效） | `pytest -q -k t6` = **1 passed** | D1.4 / T6 / I5 | [待 Step 9] |
| A9 | raise 模式语义声明成立：factor 的 `data`/`internal` ∈ `RAISE_CATEGORIES` → `day_error_mode="raise"` 时 setup 期因子异常在首交易日 `raise_if_needed()` 抛出；`off`/`report` 不受影响 | 读码 `RAISE_CATEGORIES` + `engine_v2.py` 唯一 `raise_if_needed` 调用点；`grep -rn "raise_if_needed" core/` 命中数 = 1 调用点 | D1.3 / F-S4-P026-2 / I4 | [待 Step 9] |

---

## 2. B 组：B2 插件层（D2 → T7 / T8）

> **DoR**: `EventLogPlugin._log` 升级与 `get_stats()` 新增、`GuardPlugin` 计数与文案已在 IMPL §4.4 定稿；fail-open 为 P2 级约束。**DoD**: 计数、日志级别、返回元组三面可独立观测。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `EventLogPlugin.get_stats()` **新增**且恰含 `{"enabled", "error_count"}`；无异常时 `error_count == 0`（正常路径零噪声） | 读码 `core/engine_plugins.py` 方法定义；正常路径断言 `error_count == 0` | D2.1 / I3 | [待 Step 9] |
| B2 | T7 `_log` 失败：`error_count == 1`，caplog 记录级为 **WARNING（非 DEBUG）**，文案「EventLog 记录失败」 | `pytest -q -k t7` = **1 passed** | D2.1 / T7 / D8 / V5 | [待 Step 9] |
| B3 | T8 Guard 检查异常：仍返回 `(True, [])`（**fail-open 不变**），`error_count == 1`，`blocked_count` / `warning_count` 均不变，文案含「已放行」 | `pytest -q -k t8` = **1 passed**（四断言） | D2.2 / T8 / DESIGN §10 第 2 条 | [待 Step 9] |
| B4 | `GuardPlugin.get_stats()` 由 4 键扩为 **5 键**（只增不改），既有键访问式断言零破坏 | `pytest tests/test_engine_plugins.py -q` 全绿；读码 `get_stats` 返回字典 5 键 | D2.2 / I3 / R2 | [待 Step 9] |

---

## 3. C 组：B3 传染分析（D3 → T9 / T10）

> **DoR**: `degraded_components` 字段与两兜底标记、Granger 三路径 `failed` 已在 IMPL §4.5 定稿；T9 的 MST patch 目标为 `core.global_contagion.minimum_spanning_tree`（F-S4-P026-4）。**DoD**: 三段降级状态（正常 / 空早退 / 双兜底）逐一可观测。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `ContagionNetwork.degraded_components` 带默认值 → 正常路径 `[]`、空市场早退 `[]`（既有构造点零改动） | `pytest -q -k t9` 覆盖三段；读码 dataclass 字段 `field(default_factory=list)` | D3.1 / T9 / I3 | [待 Step 9] |
| C2 | 双降级：patch `np.linalg.eigh` 与 `core.global_contagion.minimum_spanning_tree` → `degraded_components == ["centrality", "mst"]`，两处 WARNING 文案命中 | `pytest -q -k t9` = **1 passed**；patch 目标为模块内 from-import 绑定 | D3.2 / D3.3 / T9 / F-S4-P026-4 / V5 | [待 Step 9] |
| C3 | T10 Granger 三路径 `failed`：正常 `False` / 样本不足 `False` / 计算异常 `True`（语义严格限定「计算抛异常」） | `pytest -q -k t10` = **1 passed** | D3.4 / T10 / V5 | [待 Step 9] |
| C4 | 早退路径键集合保持 `{"causal", "p_value", "lag", "failed"}`（`strength` 仍缺，按 F-D-P026-4 不补；`failed` 与 `causal` 语义不混用） | 读码早退 `return` 键集合；与 IMPL §4.5 表述逐字对照 | D3.4 / F-D-P026-4 | [待 Step 9] |

---

## 4. D 组：B4 EventLog 与 Walk-Forward（D4 / D5 → T11 / T12）

> **DoR**: `_stats` 三键与 4 自增点、`stats()`、`agent_period_failures` 计数/重置/回填均在 IMPL §4.6-§4.8 定稿。**DoD**: 构造期时序、读写失败、多次 run 重置三面可独立观测。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | `EventLog._stats` 恰 3 键（`read_failures` / `write_failures` / `skipped_lines`），且初始化**早于** `_recover_state()`（构造期坏行不抛 `AttributeError`） | 读码 `core/event_log.py` `__init__` 两处相对顺序；坏行文件构造实例不抛错 | D4.1 / F-S4-P026-6 | [待 Step 9] |
| D2 | T11 写盘失败（`log_path` 指向目录）→ `write_failures >= 1` | `pytest -q -k t11` = **1 passed** | D4.2 / T11 / V5 | [待 Step 9] |
| D3 | T11 坏行（1 有效 + 1 截断 JSON）→ `skipped_lines >= 1`，且 `read()` 返回**有效条目数不变**（I6：返回形态不变） | 同一用例第二段断言 | D4.2 / T11 / I6 | [待 Step 9] |
| D4 | `stats()` 返回 dict 拷贝（外部改写不污染内部）、只读语义；`read`/`query` 返回形状零改动 | 读码 `return dict(self._stats)`；断言 `stats() is not log._stats` | D4.3 / I3 | [待 Step 9] |
| D5 | T12 `agent_period_failures`：抛错 agent → 计数 **1**；无 `set_period` agent → **0**；预置 5 后 `run()`（空窗口）→ **0**（每轮重置） | `pytest -q -k t12` = **1 passed** | D5.1 / D5.2 / T12 / D7 / R7 | [待 Step 9] |

---

## 5. E 组：不变式与保护面（I1-I7）

> **DoR**: 零改动面清单已在 IMPL §1 定稿；golden 7 条已存在。**DoD**: diff 为空或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | I1：正常路径零控制流变更 → golden G1-G7 全过且 `tests/golden/*.json` **零改动** | `pytest tests/test_golden*.py -q` 全绿；`git status --short tests/golden/` = 空 | I1 / V4 / R6 | [待 Step 9] |
| E2 | I2：计数与上报路径**自身不抛错**（`_report_error` try/except，失败仅 debug） | 读码 `factor.py` `_report_error`；T3/T4 反向注入下主流程仍正常返回 | I2 | [待 Step 9] |
| E3 | I3：只增字段 / 只增键 → `get_stats()` Guard 5 键（4+1）、Granger 4 键（3+1）、两 dataclass 新字段带默认值、`read/query` 形状不变 | 读码四处 + 对应测试断言 | I3 | [待 Step 9] |
| E4 | I4：`day_error_mode="off"` 语义不变（采集器首行短路返回 None） | 读码 `record` 首行；T5 的 off 变体或等价断言 | I4 | [待 Step 9] |
| E5 | I5：注入 / fake 对象零破坏 → T6 + 既有解耦引擎测试不回归 | `pytest tests/test_decoupled_engine.py -q` 全绿 | I5 / R3 | [待 Step 9] |
| E6 | I6：无全局可变状态 → 新增计数全部挂在实例上（`FactorPipeline` / 两插件 / `EventLog` / `WalkForwardEngine`） | 读码：新增 `self._*` 字段 5 处，无模块级可变变量 | I6 / R4 | [待 Step 9] |
| E7 | I7：K 类 8 处 + 排除 4 处**零 diff**（`data.py`×3 / `event_log` listener×2 + recovery + 快捷函数 / `walk_forward_engine` 回调 / `config_v2`×3 / `execution` L251） | `git diff <base>..HEAD -- core/data.py core/config_v2.py core/execution.py` = 空；`event_log` / `walk_forward_engine` 对应行未删改 | I7 / V6 / R5 | [待 Step 9] |
| E8 | 零改动面 diff 空：`core/interfaces.py` / `data.py` / `execution.py` / `rebalance.py` / `portfolio.py` / `pending.py` / `factory.py` / `filter/` / `agents/` / `scripts/` / `cli.py` / `engine_v3_vector.py` / `tests/golden/` / `pyproject.toml` / `.github/` | `git diff --name-only <base>..HEAD -- <上述路径>` = 空 | IMPL §1 / V6 | [待 Step 9] |
| E9 | `_stats` **不加锁**（F-S4-P026-3 结论）：全批无新增 `Lock`/`RLock` 使用点，锁语义未被改变 | 读码 `grep -n "Lock" core/event_log.py` = 既有 L61 一处（RLock），无新增 | D4.3 / F-S4-P026-3 / R8 | [待 Step 9] |

---

## 6. F 组：测试与门禁（V1-V6）

> **DoR**: T1-T12 规格已在 IMPL §5 定稿；基线读数已实测（见文档头）。**DoD**: 计数与末行读数逐字一致。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 新测试文件恰含 **12** 个 `test_*` 函数、**16** 个测试实例（T1 参数化 5 例） | `pytest --collect-only -q tests/test_p026_silent_exception_governance.py` 末行 **16 tests collected**；`grep -c "^def test_"` = 12 | V1 / T1-T12 | [待 Step 9] |
| F2 | 新测试 16 项全绿 | `pytest tests/test_p026_silent_exception_governance.py -q` = **16 passed** | V1 | [待 Step 9] |
| F3 | 全量回归 **≥ 687 passed**（671 基线 + 16 新增） | `MPLBACKEND=Agg pytest -q tests` 末行 **687 passed** | V1 / F-I-P026-1 | [待 Step 9] |
| F4 | mypy 门禁：**37 files 0 error** | `python -m mypy --explicit-package-bases --check-untyped-defs core` 末行 `Success: no issues found in 37 source files` | V2 | [待 Step 9] |
| F5 | black 门禁：**116 files unchanged**（115 + 新测试文件 1） | `python -m black --check core tests` 末行读数 | V3 | [待 Step 9] |
| F6 | 受影响面快速回归：`test_engine_plugins.py` / `test_phase2_factor.py` / `test_p025_day_error_diagnostics.py` 三文件改动前后同绿 | `pytest <三文件> -q` = **26 passed** | R2 / B4 | [待 Step 9] |
| F7 | warnings 计数 **173**（172 + statsmodels `FutureWarning`，F-I-P026-6） | 全量末行 `173 warnings` | F-I-P026-6 | [待 Step 9] |
| F8 | 远端 CI 三 job（3.10 / 3.11 / 3.12）success | `gh run view <id> --json conclusion,jobs` | V1 / G6 | [待 Step 9] |

---

## 7. G 组：治理与台账

> **DoR**: 文档落位清单已在 IMPL §2 B5 定稿。**DoD**: 行存在、引用可解析、计数自洽。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| G1 | 四文档齐备且互链：`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_p026_silent_exception_governance.md` 存在，相对链接 0 broken | Step 8 机械校验脚本读数 | B5 | [待 Step 9] |
| G2 | PROGRESS §1.4 P-026 行置 `done`（含 T1 / 四文档链接 / CI run id）+ §3.31 Step 1-10 执行记录完整 | 读回 §1.4 与 §3.31 | B5 | [待 Step 9] |
| G3 | CHANGELOG `[Unreleased]` 记录四项行为变更（因子链路 / 插件层 / 传染分析 / EventLog 与 WF），含门禁读数 | 读回 `CHANGELOG.md` 对应条目 | B5 | [待 Step 9] |
| G4 | README 计数一致：**4 处 687**（L7 badge / L99 / L278 / L427 `79 files`）；`docs/ARCHITECTURE.md` L3 测试数 **687**（核心模块 27 不变） | `Select-String -Pattern '687'` 读数 | B5 | [待 Step 9] |
| G5 | 未决项与回退点登记完整：U-P026-1~6 + F-S6-P026-1 + O-S6-P026-1/2/3 有落点；RB1-RB5 文件级回退可行 | 读回 IMPL §7 / §10 / §8 与 PROGRESS 未决表 | IMPL §8 / §10 | [待 Step 9] |
| G6 | 提交链完整且推送：代码提交 `e79bf06` → 复审回写 `d6fabaa` → Step 7/8/9/10 文档提交；CI run 回收成功 | `git log --oneline` + `gh run list` | B5 / F8 | [待 Step 9] |

---

## 8. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **45**（A 9 + B 4 + C 4 + D 5 + E 9 + F 8 + G 6，机械计数） |
| 实测列 `[待 Step 9]` 数（Step 7 时点） | **45 处** = 45 验收单元格，**零 ✅ 预填** |
| Step 9 回填后剩余 | 待回填（目标 **0 处**） |

> **RULE-2 统计溯源**：上表 45 由 §1-§7 七张表逐行机械计数得出（A1-A9 / B1-B4 / C1-C4 / D1-D5 / E1-E9 / F1-F8 / G1-G6），非估计值。
> **本文件作者基座**: DeepSeek-V4.1-Flash（与 DESIGN / IMPL 作者同源）→ **Step 8 一致性 Review 与 Step 10 ADD 审计须由异构基座执行**（RULE-5）。

---

## 9. Step 7 → Step 8 交接事项

| # | 事项 | 说明 |
|---|------|------|
| 1 | **DESIGN V1 口径订正** | DESIGN §6 V1 写「新增 12 项后 = **683**」；实测 T1 参数化 5 例 → **16 items**，全量为 **687**（F-I-P026-1）；测试**函数**数仍 12 |
| 2 | **DESIGN §4.1 估行偏差** | 估算 +337/−13（代码 +97/−13）；实测 8 core **+100/−10** + 测试 422 行（F-I-P026-3 / F-I-P026-4） |
| 3 | **IMPL §2 B1 删除行已订正** | 「+42/−4」→「+42/−2」（F-S6-P026-1，Step 6 复审回写） |
| 4 | **测试规格表述统一** | DESIGN §4.2 表格「12 项」应统一表述为「12 函数 / 16 实例」 |
| 5 | **V5 红线可观测性映射** | B1→A7 / B2→B2+B3 / B3→C1+C2 / B4→D2+D5；V1→F3、V2→F4、V3→F5、V4→E1、V6→E8 |
| 6 | **未覆盖声明** | O-S6-P026-1（`walk_forward_engine` 回调失败无计量）/ O-S6-P026-2（`event_log` listener 与 recovery 外层无计量）/ F-I-P026-5（`distillation_config` 为 None 无守卫）均**不在本批范围**，登记待第三批裁决 |
| 7 | **审查基座约束** | 本 CHECKLIST 作者 DeepSeek-V4.1-Flash 与 DESIGN / IMPL 同源 → Step 8 / Step 10 须换异构基座（如 GLM-5.3-Flash）方可满足 RULE-5 |

---

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | [RESEARCH §10](RESEARCH_p026_silent_exception_governance.md)（异构 GLM-5.3-Flash；1 P2 回写 + 2 P3 + 3 观察） | 2026-11-13 |
| Step 3-4 设计 + Review | 通过 | [DESIGN §11](DESIGN_p026_silent_exception_governance.md)（异构 GLM-5.3-Flash；4 P3 回写 + 2 观察） | 2026-11-13 |
| Step 5-6 实施规划 + Review | 通过 | [IMPL §10](IMPL_p026_silent_exception_governance.md)（异构 GLM-5.3-Flash；1 P3 回写 + 3 观察） | 2026-11-13 |
| Step 7 验收清单 | 完稿（零预填 45 项） | §1-§8（作者 DeepSeek-V4.1-Flash） | 2026-11-13 |
| Step 8 一致性 Review | **pass**（2 P3 修复 + 1 观察） | §11（异构基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash） | 2026-11-13 |
| Step 9 TDD 实施 | 待回填 | 45/45 目标 | — |
| Step 10 ADD 审计 | 待执行 | 须异构基座 ≠ DeepSeek-V4.1-Flash | — |
| RULE-5 异构复审 | 待执行 | — | — |
| CI 回收 | 待回收 | — | — |

---

## 11. Step 8 一致性 Review 记录（2026-11-13）

> **复审基座**: GLM-5.3-Flash ≠ 四文档作者 DeepSeek-V4.1-Flash（异质性成立）；范围 = RESEARCH ↔ DESIGN ↔ IMPL ↔ CHECKLIST 三对对齐（SPEC_PROCESS Step 8）。

| 维度 | 结果 |
|------|------|
| 链接完整性 | ✅ 四文档全部相对链接（含 `../core/*.py` 代码锚点）**0 broken**（Python 脚本按链接所在目录解析重放） |
| 计数一致性 | ✅ 687 / 671 / 16 items / 12 函数 / 173 warnings / +100/−10 / 37 files / 116 各文档口径一致；RESEARCH 671+172 与 DESIGN 671+172 为 Step 2/4 时点读数（正确）；`+337/−13` 为 DESIGN 估算值（偏差 F-I-P026-3/4 已声明） |
| 编号连续性 | ✅ D1-D8 / I1-I7 / V1-V6 / T1-T12 / F-D-P026-1~4 / F-S4-P026-1~6 / F-I-P026-1~6 / U-P026-1~6 / F-S6-P026-1 / O-S6-P026-1~3 全部连续无断号 |
| 45 项复核 | ✅ 七表行数机械计数 **A9/B4/C4/D5/E9/F8/G6 = 45**，与 §8 声明一致；实测列 45 处全部 `[待 Step 9]`、零 ✅ 预填 |
| 三对对齐 | ✅ RESEARCH↔DESIGN：三处 P2 → D1/D2/D5 覆盖，D4 承接 U-P026-6，依据 §5 编号齐全；DESIGN↔IMPL：D1-D8→B1-B4 批次映射完整，§4 实录 8 文件锚点经 Step 6 diff 重放逐行对码；IMPL↔CHECKLIST：T1-T12 → A/B/C/D 组全覆盖，各组 DoR 引用 IMPL §4.x 均真实存在 |
| 提交链 | ✅ `7c48d50→9c332cc→76f7e6e→bbb55bc→e79bf06→d6fabaa→6532b93` 与各文档状态行一致（`git log --oneline -8` 重放） |

**发现与修复**：

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-S8-P026-1 | P3 | DESIGN §6 V1 判据「新增 12 项后 = 683」与实测 687 不符——IMPL §7 F-I-P026-1 处置声明「CHECKLIST 阶段统一订正」，但 Step 7 仅在交接事项列出、未回改 DESIGN 原文 | **已订正** V1 判据为 **≥687 passed（16 items = 12 函数）**，注明订正链 F-I-P026-1 → Step 8 落地 |
| F-S8-P026-2 | P3 | DESIGN §4.2 标题「测试规格（12 项）」与实测「12 函数 / 16 实例（T1 参数化 5 例）」口径不一（交接事项④） | **已订正**标题；§4.2 表格 T1-T12 行本身无需改动 |
| O-S8-P026-1 | 观察 | DESIGN §11 Step 4 复审历史记录含「V1 671+12=683」算术复核——属当时时点正确结论，历史记录不篡改，保留；读者以订正后 §6 为准 | 保留不改 |

**交接事项 7 条落实情况**（§9）：① **本步修复**（F-S8-P026-1）/ ② 已由 F-I-P026-3/4 声明落实 / ③ 已在 Step 6 落实（F-S6-P026-1）/ ④ **本步修复**（F-S8-P026-2）/ ⑤⑥⑦ 在 §8 / §9 / §10 已落实。

**复审结论**: **pass**（0 P1 / 0 P2 / 2 P3 已修复 / 1 观察）。Step 9 TDD 可启动（45 项按 §1-§7 DoD 证据出口回填）。
