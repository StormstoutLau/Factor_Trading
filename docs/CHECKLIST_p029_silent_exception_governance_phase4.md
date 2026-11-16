# CHECKLIST：P-029 静默失败治理第四批（`agents/` 9 处计量）

> **批次**: P-029 · **T1**（`agents/` 3 文件；零 fail-fast、零返回值语义变更、零既有文案改写、**零新增日志**）
> **上游**: [IMPL_p029](IMPL_p029_silent_exception_governance_phase4.md)（B1-B4 / §4 精确变更规格 / §5 V1-V7 / §6 门禁 / §7 A1-A7 / §10 Step 6 复审 pass）；[DESIGN_p029](DESIGN_p029_silent_exception_governance_phase4.md)（D1-D7 / I1-I8 / §5 不变式 / §6 验证契约 + F-S6-P029-4 注记）；[RESEARCH_p029](RESEARCH_p029_silent_exception_governance_phase4.md)（§3 八处清单 / §4 分类 / §5 E2 / §11 Step 2 复审）
> **状态**: **Step 8 一致性 Review pass**（2026-11-16，复核基座 GLM-5.3-Flash ≠ Step 7 作者 DeepSeek-V4.1-Flash；机械五项全过 + 对齐矩阵无遗留 + 1 P3 当轮修正 + 1 观察，见 §10）｜Step 7 完稿（作者 DeepSeek-V4.1-Flash）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**禁止与正文同一次写入时打勾**
> **基线读数（Step 4 实测 @HEAD `23132cb`，Python312）**: 全量 `pytest -q` **711 passed** / `tests/` .py **80**（77 `test_*.py` + 3 `_` 辅助）/ `black --check core tests` **117 unchanged** / `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error** / I1 `except Exception` **22**
> **目标读数（Step 9）**: **722 passed** / 测试文件 **81** / black **118** / mypy **37 files 0** / I1 恒 **22**
> **代码证据时点**: 实施前 HEAD `23132cb`（§4 锚点为实施前行号）；Step 9 后按 F-I 惯例登记漂移

---

## 1. A 组：B1 `agent_framework.py` 5 计量（D1 / D2 / D3 → 测试 V1-V3）

> **DoR**: 载体三件套已存在（L882/L891-893/L895-897，P-027 落地）；S1-S3 三处 bare except 的 `pass` 替换、S3b `else` 挂 `if`、S4 计量 + L1152 下移均已在 IMPL §4.1 定稿。**DoD**: 5 个键各自可独立触发、缓存/缺键语义零变更、零新增日志。**ID 空间注记（F-S8-P029-1）**：本表验收项 A1-A6 与 IMPL §7 注意项 A1-A7 为两套 ID；本文件锚点列引用 IMPL 注意项时一律带 `IMPL§7-` 前缀。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | S1：`prepare_factors` L971 bare except → 计数键 `price_cache` 1；`self._price_data` 仍为 `None`；`prepare_factors` 期间 WARNING+ **零记录** | `pytest -q -k cache_failure_counts` 含 price 参数集通过；caplog 断言（构造后 `caplog.clear()`） | D1 / V1 / IMPL §4.1 S1 | [待 Step 9] |
| A2 | S2：L981 bare except → `industry_cache` 1；`self._industry_data` 仍 `None`；**损坏 pkl per-case**（本参数集仅写 `industry.pkl`） | 同一用例 industry 参数集；`{key: 1}` 精确断言（不含 `mktcap_cache`） | D1 / V1 / F-S6-P029-1 | [待 Step 9] |
| A3 | S3：L991 bare except → `mktcap_cache` 1；`self._mktcap_data` 仍 `None`；本参数集仅写 `mktcap.pkl` | 同一用例 mktcap 参数集；`{key: 1}` 精确断言 | D1 / V1 / F-S6-P029-1 | [待 Step 9] |
| A4 | S3b：`_init_research_team` 新增 `else` 分支，**挂 L928 的 `if`**（AST 校验 `orelse` 归属 `If` 而非 `Try`）→ `rotation_analyzer_skipped` 1；`rotation_analyzer is None`；无 `rotation_analyzer_init` 键；**零新增 warning** | `pytest -q -k rotation_analyzer_skipped` = 1 passed；AST 脚本打印归属节点类型 | D2 / V2 / IMPL§7-A1 / R-P029-4 | [待 Step 9] |
| A5 | S4：bare except → `performance_summary_team_report` 1；`team_report` **不在** summary；`failure_counts` **同调含该键**（L1152 下移生效）；`agent_id` / `style` 等既有键仍在 | `pytest -q -k team_report_failure` = 1 passed（同调断言） | D3 / V3 / F-S4-P029-1 | [待 Step 9] |
| A6 | bare except **零改写**：4 处 `except:` 行（L971/L981/L991/L1158）在 diff 中零变更；零新增 `logger.*`；`pass` 全部被计量行替换 | `git diff -U0 agents/agent_framework.py`：`except:` 行零增删；`^\+.*logger\.` = 0；4 处 `pass` 行零残留 | D7 / I1 / I6 / A3 | [待 Step 9] |

---

## 2. B 组：B2 `multi_strategy_engine.py` 3 计量（D4 → 测试 V4-V5）

> **DoR**: 载体与出口均为 P-027 既有（L111/L115-117/L119-121、清零 L154、出口 L171），B2 **零载体改动**；S5 合法分支不计数（IMPL§7-A4）。**DoD**: 三键各自可触发；`continue`/`return` 与队列语义逐字保留。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | S5：L330 `except (KeyError, IndexError)` → `orders_missing_price` 1；**合法分支**（列/日期缺失走 L328-329 `continue`）计数 **0**；两例均不产生订单 | `pytest -q -k order_missing_price` = 2 passed（双参数集） | D4 / V4 / IMPL§7-A4 | [待 Step 9] |
| B2 | S6：L390 `except KeyError` → `next_day_open_price` 1；`return` 后 `_next_day_orders` **长度不变**；WARNING+ 零记录 | `pytest -q -k open_price_failures` 含 next_day 参数集通过 | D4 / V5 / U-P029-2 | [待 Step 9] |
| B3 | S7：L452 `except KeyError` → `pending_open_price` 1；`return` 后 `pending_queue` **长度不变**；WARNING+ 零记录 | 同一用例 pending 参数集通过 | D4 / V5 / U-P029-2 | [待 Step 9] |
| B4 | 三处插入均为 `except` 块**首行 +1 行**，其后语句零 `-` 行；`run()` 出口 `failure_counts` 零改动仍存在 | `git diff multi_strategy_engine.py` 三 hunk 各 +1 / −0；读码 L171 出口未动 | D4 / D6 / IMPL §4.2 | [待 Step 9] |

---

## 3. C 组：B3 `strategy_allocator.py` 三件套 + 1 计量（D5 / D6 → 测试 V6-V7）

> **DoR**: M-A 决策（仅 `MeanVarianceAllocator` 自备，不下沉 `BaseAllocator`）已由 Step 4 E4 实证（5 子类均有自有 `__init__`）。**DoD**: pinv 路径可计数、getter 为拷贝、正常路径零计数、`BaseAllocator` 零改动。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `MeanVarianceAllocator.__init__` 追加 `_failure_counts: dict[str, int] = {}`，**形参逐字零变更**；新增 `_record_failure` / `get_failure_stats`（含 docstring） | 读码 L604-608 与新增二方法；`git diff` 中 `def __init__(self, risk_aversion...` 行零变更 | D5 / D6 / I5 / M-A | [待 Step 9] |
| C2 | S8：patch `np.linalg.inv` 抛 `LinAlgError` → `pinv_fallback` 1；权重仍归一（`sum ≈ 1.0`）；注释「如果奇异，使用伪逆」逐字保留 | `pytest -q -k pinv_fallback` = 1 passed；`git diff` 注释行零变更 | D5 / V6 / IMPL §4.3 | [待 Step 9] |
| C3 | `get_failure_stats()` 返回 **拷贝**：外部改写返回值不影响内部计数 | 同一用例断言（`stats["pinv_fallback"] = 999` 后内部仍 1） | D5 / V6 / IMPL §4.3 | [待 Step 9] |
| C4 | 正常路径零计数：正常求逆 → `get_failure_stats() == {}`；engine 侧 no-op 日处理后 `run()["failure_counts"] == {}` | `pytest -q -k normal_path_zero_counts` = 1 passed | D5 / V7 / IMPL§7-A7 | [待 Step 9] |
| C5 | **M-A 边界**：`BaseAllocator`（L354-371）与其余 4 个子类（Hedge/FTRL/UCB/Thompson）**零改动** | `git diff strategy_allocator.py`：变更 hunk 全落在 `MeanVarianceAllocator` 区间（L582 起） | D5 / M-A / R-P029-5 | [待 Step 9] |

---

## 4. D 组：不变式与保护面（I1-I8）

> **DoR**: 九面零改动清单已在 IMPL §1 定稿；`tests/golden/` 7 条基线已存在。**DoD**: diff 为空或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | I1：十文件 AST 扫描 `except Exception` 合计仍 **22**（本批 9 处均为 bare / 窄类型） | IMPL §6 AST 单行命令（独立复跑）= `22` | I1 / IMPL §6 | [待 Step 9] |
| D2 | I2：零新增 `raise` / 零 fail-fast | `git diff -- '*.py'` 中 `^+.*raise ` = 0（测试辅助可豁免，须登记） | I2 / D7 | [待 Step 9] |
| D3 | I3：返回值语义零变更——缓存 `None` / 缺 `team_report` 键 / `continue` / `return` / pinv 权重域 | A1-A5 / B1-B3 / C2-C4 断言组合 | I3 / V1-V7 | [待 Step 9] |
| D4 | I4：九面零改动（`filter/` / `core/` / `strategy_evaluation/` / `scripts/` / `batch_backtest/` / `cli.py` / `pyproject.toml` / `.github/` / `tests/golden/*.json`） | `git diff --name-only` 仅 3 代码 + 1 测试；九面零命中 | I4 / IMPL §1 | [待 Step 9] |
| D5 | I5：既有签名不变——`prepare_factors` / `get_performance_summary` / `_generate_orders` / `_execute_next_day_orders` / `_process_pending_orders` / `allocate` / `MeanVarianceAllocator.__init__` 形参逐字；`get_performance_summary` 仍 **2 处**（L336 BaseAgent 勿动） | `git diff` 中 7 个 `def` 行零变更；`grep -n "def get_performance_summary"` 仍 2 处 | I5 / A2(IMPL) | [待 Step 9] |
| D6 | I6：**零新增日志 + 既有文案逐字**——`git diff` 中 `logger.` 行 **0 增 0 删**；「如果奇异，使用伪逆」等既有注释零改写 | `git diff -U0 \| Select-String "logger\."` = 0；IMPL §4.3 注释行零变更 | I6 / D7 | [待 Step 9] |
| D7 | I7：golden G1-G7 全过且 `tests/golden/*.json` **零改动**（零重录） | `pytest tests -q -k golden` 全绿；`git status --short tests/golden/` = 空 | I7 / IMPL §6 | [待 Step 9] |
| D8 | I8：测试 **711 → 722**（+11）；测试文件 **80 → 81**；black **117 → 118**；mypy **37 files 0**（不变） | 全量末行 `722 passed`；文件计数 81；black `118 unchanged`；mypy `37 source files` | I8 / IMPL §6 | [待 Step 9] |

---

## 5. E 组：测试与门禁（V1-V7 覆盖 + 门禁）

> **DoR**: V1-V7 规格与 §5.1 注入实证已定稿（改前代码 7 组全通）。**DoD**: 计数与末行读数逐字一致；红态先于绿态取证。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 新测试文件恰含 **7** 个 `test_*` 函数、**11** 个测试实例（V1 3 / V4 2 / V5 2 / V2/V3/V6/V7 各 1） | `pytest --collect-only -q tests/test_p029_silent_exception_governance.py` 末行 **11 tests collected**；`grep -c "^def test_"` = **7** | V1-V7 / IMPL §5 | [待 Step 9] |
| E2 | 红态纪律：B1/B2/B3 三批先取红再取绿；红态读数记入 IMPL §11；**V4 合法参数与 V7 engine 侧在红态即通过属预期**（须在留档中标注，防误判为「红态不完整」） | 三批红态输出留档；IMPL §11 记录 | IMPL §5 红态纪律 | [待 Step 9] |
| E3 | 新测试 **11 passed** | `pytest tests/test_p029_silent_exception_governance.py -q` = **11 passed** | V1-V7 | [待 Step 9] |
| E4 | 全量回归 **722 passed**（711 基线 + 11） | `MPLBACKEND=Agg pytest -q` 末行 **722 passed** | I8 / §6 | [待 Step 9] |
| E5 | mypy 门禁 **37 files 0 error**（`agents/` 不在门禁路径） | `python -m mypy --explicit-package-bases --check-untyped-defs core` 末行 | §6 | [待 Step 9] |
| E6 | black 门禁 **118 files unchanged**（117 + 新测试文件 1） | `python -m black --check core tests` 末行 | §6 | [待 Step 9] |
| E7 | 测试零 `unittest.mock`（统一 `monkeypatch`）；无仓库外脚本依赖（§5.1 探针能力已固化为 V1-V7） | `grep -n "unittest.mock\|^from mock" tests/test_p029_silent_exception_governance.py` = 0 命中 | DESIGN D7 / §5 | [待 Step 9] |
| E8 | 受影响面快速回归：`agents/` / `core/` 相关既有测试同绿（**0 failed / 0 error**），P-027 套件（24 passed）与 P-026 套件不回归 | `pytest tests -q -k "agent or strategy_engine or strategy_alloc or portfolio or pending or p027 or p026"` 全绿（子集基线未单独登记，不比数值） | V1-V7 / 回归面 | [待 Step 9] |
| E9 | 远端 CI 三 job（3.10 / 3.11 / 3.12）success | `gh run view <id> --json conclusion,jobs` | §6 | [待 Step 9] |

---

## 6. F 组：治理与台账

> **DoR**: 文档落位清单已在 IMPL §2 B4 定稿（含 F-S6-P029-5 的目标更正：Step 9 记录落 IMPL §11）。**DoD**: 行存在、引用可解析、计数自洽。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 四文档齐备且互链：`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_p029_silent_exception_governance_phase4.md`，相对链接 0 broken | 机械校验脚本读数（相对链接数 / broken 数） | IMPL §2 B4 | [待 Step 9] |
| F2 | PROGRESS §1.4 P-029 行置 `done`（T1 / 四文档链接 / CI run id）；§3.34 系列补齐 Step 7-10 记录（Step 9 记录落 **IMPL §11**） | 读回 §1.4 与 §3.34.x | IMPL §2 B4 / F-S6-P029-5 | [待 Step 9] |
| F3 | CHANGELOG `[Unreleased]` 记录本批行为变更（`agents/` 9 计量 / 零新增日志 / 零 fail-fast），含门禁读数 | 读回 `CHANGELOG.md` `[Unreleased]` 对应条目 | IMPL §2 B4 | [待 Step 9] |
| F4 | README 计数一致：**4 处**（L7 badge / L99 / L278 / L427 含「80 files」）与 `docs/ARCHITECTURE.md` L3——711 → **722**、80 → **81** files 同步 | `Select-String -Pattern '711\|722\|80 files\|81 files' README.md docs/ARCHITECTURE.md` 读数 | IMPL §2 B4 | [待 Step 9] |
| F5 | 未决项与回退点登记完整：U-P029-2（S6/S7 重试语义）维持 pending；R-P029-4/5/6/7 有落点；O-S4-P029-1（非异常等权回退）/ O-S4-P029-2（文件数口径）/ F-I-P029-1（行数估算）/ O-I-P029-1 已登记；B1-B3 文件级回退可行 | 读回 IMPL §7 / §8 与 PROGRESS 未决表 | IMPL §7 / §8 | [待 Step 9] |
| F6 | 提交链完整且推送：`e6daa05`（IMPL）→ `9614ba4`（Step 6 复审）→ `285d952`（回填）→ Step 7 文档提交 → Step 9 三批 + B4；CI run 逐次回收成功 | `git log --oneline` + `gh run list --limit 5` | IMPL §2 B4 | [待 Step 9] |

---

## 7. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **38**（A 6 + B 4 + C 5 + D 8 + E 9 + F 6 = 38，机械计数；ID 去重 38/38） |
| 实测列 `[待 Step 9]` 数（Step 7 时点） | **38 处** = 38 验收单元格，**零 ✅ 预填**（全文机械计数 **40** 处 = 38 验收 + **2 合法字面引用**：本文档头「实测列规则」行 + 本行；与 P-027 §7 同口径） |
| 覆盖映射（测试用例） | V1 **3/3**（A1/A2/A3）；V2 1/1（A4）；V3 1/1（A5）；V4 2/2（B1 双参数集）；V5 2/2（B2/B3）；V6 1/1（C2 + C3）；V7 1/1（C4）→ **11/11 实例全覆盖** |
| 覆盖映射（不变式） | I1-I8 **8/8**（D1-D8 一一对应） |
| 覆盖映射（设计决策） | D1→A1-A3 / D2→A4 / D3→A5 / D4→B1-B4 / D5→C1-C5 / D6→A5+B4+C1+C4 / D7→A6+D2+D6 全落点 |

> **RULE-2 统计溯源**：38 由 §1-§6 六张表逐行机械计数得出（A1-A6 = 6 / B1-B4 = 4 / C1-C5 = 5 / D1-D8 = 8 / E1-E9 = 9 / F1-F6 = 6，合计 38），非估计值。

> **本文件作者基座**: DeepSeek-V4.1-Flash（与 RESEARCH / DESIGN / IMPL 作者同源）→ **Step 8 一致性 Review 须由异构基座执行**（RULE-5）。

---

## 8. Step 7 → Step 8 交接事项

1. **Step 8 一致性 Review**（异构基座）：核四文档互链与口径一致——
   - `9` 计量在 RESEARCH §1/§4 分类 / DESIGN §1 计费行 / IMPL §2 计数口径 / 本文件 A(5)+B(3)+C(1) 四处一致；
   - `11` 实例在 DESIGN §4.2 / IMPL §5 / 本文件 E1 三处一致（V1 3 + V4 2 + V5 2 + 其余 4 单例 = 11）；
   - `722 / 81 / 118 / 37` 在 DESIGN §5 I8 / IMPL §6 / 本文件 D8+E4-E6 三处一致；
   - 「零改动 1 处」（`research_team_v2.py:25-28` import 降级）在 DESIGN §1 / IMPL §2 两处一致（F-S4-P029-3）。
2. **F-S6-P029-4 映射确认**：DESIGN §6 契约 V1-V5 与测试用例 V1-V7 为两套 ID，本文件 A5/B1-B3/C4 已按**测试用例**编号落位（Step 8 须复核无混用）。
3. **Step 9 必做的三处顺序敏感核验**（IMPL§7-A1/A2/A3）：`else` 挂 `if`（AST 归属）、V2 先置 `_research_team_available=True`、bare except 零改写。
4. **红态留档**：E2 要求三批红态输出留档，且须标注 V4 合法参数 / V7 engine 侧「红态即通过」的预期豁免。
5. **行号漂移**：Step 9 实施后按 F-I 惯例登记（IMPL §4 锚点为实施前 `23132cb`；参考 P-027 IMPL §11.3 形态）。

---

## 9. 签字表

| 角色 | 基座 | 结论 | 日期 |
|------|------|------|------|
| Step 7 验收清单作者 | DeepSeek-V4.1-Flash | 38 项完稿，零预填 | 2026-11-16 |
| Step 8 一致性 Review | GLM-5.3-Flash（≠ Step 7 作者 DeepSeek-V4.1-Flash） | pass（机械五项全过 + 对齐矩阵无遗留；1 P3 当轮修正 F-S8-P029-1 + 1 观察，见 §10） | 2026-11-16 |
| Step 9 TDD 执行 | 待定 | — | — |
| Step 10 ADD 审计 + RULE-5 异构终审 | 待异构基座 | — | — |

---

## 10. Step 8 一致性 Review（异构基座 GLM-5.3-Flash，2026-11-16）

> **异构性（RULE-5）**: 本文件作者 DeepSeek-V4.1-Flash（与 RESEARCH/DESIGN/IMPL 同源）≠ 本节复审基座 **GLM-5.3-Flash**。
> **复审对象**: 本文件提交 `b2014aa` 版本（Step 7 收口）
> **方法**: 机械校验脚本（`%TEMP%\p029_step8_check.py`，独立编写）五项 + 四处口径人工对拍 + F-S6-P029-4 映射复核 + 对齐矩阵
> **结论**: **pass**（0 P1 / 0 P2 / 1 P3 当轮修正 / 1 观察）——满足进入 Step 9 TDD 条件

### 10.1 机械校验五项（全过）

| # | 校验项 | 读数 | 判定 |
|---|--------|------|------|
| 1 | 四文档存在性 + 相对链接 | RESEARCH 4 / DESIGN 1 / IMPL 1 / CHECKLIST 3 = **9 条，0 broken** | ✅ |
| 2 | ID 闭环 | A 6 + B 4 + C 5 + D 8 + E 9 + F 6 = **38**，unique 38/38，六组序列全连续（无跳号） | ✅ |
| 3 | 计数一致 | §7 声称 38 = 机械计数 38 | ✅ |
| 4 | 零预填（RULE-1） | 行内 ✅ = **0**；`[待 Step 9]` 计数：Step 7 时点 **40** = 38 验收 + 2 合法字面引用；本 Review 记录新增 1 处字面引用（本行）→ 现全文 **41** = 38 + **3** | ✅ |
| 5 | 角色引用 | 四文档基座引用链完整（RESEARCH DeepSeek+GLM / DESIGN DeepSeek+GLM / IMPL DeepSeek+GLM / CHECKLIST DeepSeek→Step 8 补 GLM，签字表已更新） | ✅ |

### 10.2 四处口径对拍（全一致）

| 口径 | RESEARCH | DESIGN | IMPL | CHECKLIST | 判定 |
|------|----------|--------|------|-----------|------|
| **9 计量 / 3 文件** | §11 L237 定稿口径（§1/§4 为「B 7 + 待裁决 1 + 观察 1」8+1 分类，推导兼容） | §1 计费行 ×4 处 | §2 计数口径 ×5 处 | 标题 + A(5)+B(3)+C(1) | ✅ |
| **11 实例**（V1 3 + V4 2 + V5 2 + 4 单例） | —（Step 1 无测试规格，正常） | §4.2 ×4 | §5 ×4 | E1 + §7 ×3 | ✅ |
| **722 / 81 / 118 / 37** | —（正常） | I8 | §6 门禁表 | 头部目标 + D8 + E4/E5/E6 | ✅ |
| **零改动 1 处**（`research_team_v2.py` import 降级） | §11 E4 复扫「9 零可观测 = 8 + 1」（表述异形） | §1 ×2（F-S4-P029-3 回写） | §2 ×1 | §8.1 ×1 | ✅ |
| **I1 = 22** | §11 | ×3 | ×4 | D1 + 头部 ×3 | ✅ |

粒度注记：`research_team_v2.py` 站点在 RESEARCH 引作 `:27`（except 行）、DESIGN/IMPL 引作 `:25-28`（块区间）——同一站点两种粒度，不冲突。

### 10.3 F-S6-P029-4 两套 V ID 映射复核（无混用）

- 本文件锚点列的 V 编号**全部为测试用例编号**：A1/A2/A3→V1、A4→V2、A5→V3、B1→V4、B2/B3→V5、C2/C3→V6、C4→V7，§7 覆盖映射同口径。
- DESIGN §6 契约 V1-V5「对应」列 T1-T7 与测试 V1-V7 按序一一对应；契约→测试映射（契约V1→V1、契约V2→V2/V3、契约V3→V4/V5、契约V4→V6/V7、契约V5→V3/V5）覆盖完整。
- **无契约编号误入测试落位、亦无反向混用** ✅。

### 10.4 对齐矩阵（RESEARCH → DESIGN → IMPL → CHECKLIST，无遗留）

| RESEARCH 站点 | DESIGN | IMPL | CHECKLIST |
|---------------|--------|------|-----------|
| S1/S2/S3（bare×3） | D1 | §4.1 S1-S3 | A1/A2/A3 |
| S3b（else 缺失） | D2 | §4.1 S3b | A4 |
| S4（bare + L1152 滞后） | D3 | §4.1 S4 | A5 |
| S5/S6/S7（窄类型×3） | D4 | §4.2 | B1/B2/B3 + B4（插入形态） |
| S8（LinAlgError→pinv） | D5 | §4.3 | C1/C2 + C5（M-A 边界） |
| D6 出口（2 复用 + 1 getter） | D6 | §4.3 getter / 复用既有 | C3/C4 + B4 |
| D7 约定（零日志/零 raise/零捕获变更） | D7 | §1 五前提 | A6 + D2/D6 |
| R-P029-4~7 / U-P029-2 / O-S4/F-I 项 | §7 | §7/§8 | B2/B3 + F5 |

不变式 I1-I8 → D1-D8 一一对应；测试 V1-V7 → A/B/C 组 11/11 实例；**零遗留落点** ✅。

### 10.5 E8 可执行性抽查

`pytest --collect-only -q -k "agent or strategy_engine or strategy_alloc or portfolio or pending or p027 or p026" tests` 实测 **83/711 collected**（628 deselected）——E8 七个关键词全部有效命中，Step 9 复跑只需验证 0 failed（不比数值）。

### 10.6 发现与处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P029-1 | P3 | **A ID 双套**：本文件验收项 A1-A6 与 IMPL §7 注意项 A1-A7 同名异义；行内锚点（A4 行引 IMPL§7-A1、B1 行引 IMPL§7-A4、C4 行引 IMPL§7-A7、B 组 DoR 引 IMPL§7-A4）原本裸写「A1/A4/A7」，Step 9 执行者存在误读为本文件 A 组验收项的风险（§8.3 虽有「IMPL §7」限定但行内未带） | **已当轮修正**：4 处行内锚点 + B 组 DoR 统一加 `IMPL§7-` 前缀；A 组 DoR 补 ID 空间注记；§8.3 统一为 `IMPL§7-A1/A2/A3` |
| O-S8-P029-1 | 观察 | RESEARCH 的「9 计量」口径实际落在 §11 L237（Step 2 定稿），§1/§4 为「B 7 + 待裁决 1 + 观察 1」的 8+1 分类口径——§8.1 第一条引用写「RESEARCH §1/§4 分类」是推导链起点，语义成立但读者需经 §11 才见 9 字样；另 `research_team_v2.py` 粒度引用 `:27`（RESEARCH）vs `:25-28`（DESIGN/IMPL）并存 | 登记：不改文档（两处表述各自忠实）；Step 9 收口时若引 RESEARCH 口径以 §11 为准 |

### 10.7 复审结论

- **Step 8 一致性 Review pass**：机械五项全过、四处口径一致、F-S6-P029-4 映射无混用、对齐矩阵零遗留、E8 可执行性实证（83/711）。
- 1 P3（F-S8-P029-1）当轮修正；1 观察登记。
- **下一 Step：Step 9 TDD**——按 B1→B1t→B2→B2t→B3→B3t 逐批红绿（先核 IMPL§7-A1/A2/A3 三处顺序敏感项），最后 B4 回填本文件 38 项实测列 + IMPL §6/§11 + PROGRESS + CHANGELOG + README/ARCH 计数。
