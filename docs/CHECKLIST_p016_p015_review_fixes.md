# CHECKLIST：P-016 P-015 复审 P3 修正

> **批次**: P-016 · T1
> **上游**: [IMPL_p016_p015_review_fixes.md](IMPL_p016_p015_review_fixes.md)（T-1~T-5 / V1-V8）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **状态**: Step 9-10 完稿（2026-11-10）

---

## 1. 验收项

### A 组：三态改造（F-R5-P015-2）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| A-1 | `Checks.waive` 存在且与 `add` 同形 | 静态读码 + 运行时出现 `WAIVER(非断言)` | ✅ E1+E3：`verify_p015.py:53` `waive()`；B5 单跑 stdout `G2 [B5] WAIVER(非断言)` |
| A-2 | 豁免行不计入断言数 | 全链汇总 `断言 28（失败 0）+ 豁免 1` | ✅ E1：`共 28 项断言（失败 0 项）+ 豁免登记 1 项`（全链）、`共 4 项断言（失败 1 项）+ 豁免登记 1 项`（B5 单跑） |
| A-3 | 报告渲染为「— 豁免（非断言）」 | APPENDIX §2 对应行文本 | ✅ E1：[APPENDIX §2](APPENDIX_p015_external_calibration.md) B5 行 = `— 豁免（非断言）`（逐行 diff 唯一差异） |
| A-4 | 退出码语义不变（I3） | 全链 exit 0；B5 单跑 exit 1 | ✅ E1：全链 `VERIFY_EXIT=0`；B5 单跑 exit 1（I5 仍 FAIL） |

### B 组：报告人工章节保护（F-S9-P016-1）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| B-1 | 含人工标记的目标 → 改名写入 | 对副本执行 `--report`，生成 `<stem>.generated.md` | ✅ E1：`[保护] APPENDIX.md 含人工章节（§1/§3），改写 APPENDIX.generated.md`；文件存在 |
| B-2 | 原文件零改动（I5） | 执行前后 SHA256 相同 | ✅ E1：`ORIG_UNCHANGED=True`（副本场景）；真实路径复放同样只写 `.generated.md` |
| B-3 | 无标记目标 → 原路径写入 | 临时空路径执行后文件存在 | ✅ E1：`.tmp_p015_report/*.md`（无标记）按原路径写入（红 C 场景） |

### C 组：current-NAV 规格 fail-fast（F-R5-P015-3）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| C-1 | `cost_rate>0` 抛 `NotImplementedError` | 探针 B 复跑得异常 + 文案含 case/rate | ✅ E1：`GUARD_OK: simulate_vbt_spec 的费用语义未定义（F-R5-P015-3 / U-P016-1）：case=B2 c…` |
| C-2 | `cost_rate=0` 行为不变（I6） | B2 全链仍绿，I2b/I2c 读数与改前一致 | ✅ E1：B2 `I2b.qty=1.164e-10` / `I2c.diff=2.021e-10`（与改前逐位一致） |

### D 组：文档回写（F-R5-P015-1 + 口径同步）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| D-1 | CHECKLIST_p015 C-2 写明 I2a ↔ G1 映射 | 该行含「I2a = G1 组三行」 | ✅ E1：C-2 判据列已含「I2a（= G1 组三行 `G1.qty/cash/pv`，verify 无独立命名行——P-016 D4）」 |
| D-2 | APPENDIX 口径与重生成结果一致 | §2 头注 + 数值逐行一致（I4） | ✅ E1：`§2 完全一致: True`；29 行中仅 1 行差异（豁免渲染） |
| D-3 | RESEARCH_p015 U-P015-1 补费率前置 | 四元块含 U-P016-1 指针 | ✅ E1：U-P015-1 增「附加前置（P-016 / U-P016-1）」行 |
| D-4 | DESIGN_p015 §3.2 补 I2a 命名映射 | 该节含 G1.qty 交叉引用 | ✅ E1：§3.2 代码块后增「命名映射（P-016 D4 / F-R5-P015-1）」注 |

### E 组：纪律面

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| E-1 | 不进 tests/、不进 CI | `git status` 无 `tests/`、`.github/` 变更 | ✅ E1：变更面 = `scripts/external_benchmark/`（2 文件）+ `docs/`（6 文件） |
| E-2 | 主环境回归不劣化 | `pytest tests` 仍 635 passed | ✅ E1：`635 passed, 152 warnings in 76.89s` |
| E-3 | 新脚本格式 | `black --check scripts/external_benchmark/` 0 变更 | ✅ E1：`5 files would be left unchanged` |

### F 组：可重放

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| F-1 | F5 红→绿两读数 | IMPL §6 含红（A/B/C 三探针）与绿（同命令修复后读数） | ✅ E1：[IMPL §6.1](IMPL_p016_p015_review_fixes.md) 三组红→绿对照表 |
| F-2 | 全链复放命令仍有效 | 五 case 导出→venv→verify 复放 exit 0 | ✅ E1：`VERIFY_EXIT=0`，五 case 导出 checksum 逐 case 复现 |

---

## 2. 统计

- 总数：**18 项**（A4 / B3 / C2 / D4 / E3 / F2）
- 状态：**18/18 ✅**（逐项绑证据，RULE-2 逐项核对）
- 发现：**P1 = 0 / P2 = 1（F-S9-P016-1，已修并重新回填）/ P3 = 1（F-S9-P016-2，登记）**

---

## 8. Step 8 一致性 Review

**执行时点**：四文档完稿后的独立 pass（RULE-1）；**[RULE-4] 自查（单视角）**。

### 8.1 机械校验读数（2026-11-10）

| 校验项 | 读数 |
|--------|------|
| 链接存在性 | 10/10 OK（四文档 + P-015 四件 + 两脚本），0 broken |
| 预填检查（RULE-1） | 仅 L5 规则声明行命中 `✅`；18 项实测列全 `[待 Step 9]` |
| ID 引用闭环 | F-R5-P015-1(6)/-2(4)/-3(5)、F-S9-P016-1(6)、U-P016-1(10)、I1(3)/I6(5)、D1(6)/D4(5)、T-1(4)/T-5(3)、V1(4)/V8(3) —— 全部 ≥3 且跨文档 |

### 8.2 一致性发现与修复

| ID | 发现 | 处置 |
|----|------|------|
| F-S8-P016-1 | RESEARCH §2 P6 原写「会覆盖」为**风险表述**，与 `git show` 证实的**既成事实**不符 | P6 与 IMPL F-S9-P016-1 均改为「已真实发生」，级别由 P3 升 **P2** |
| F-S8-P016-2 | 本批范围原仅含 3 项复审发现，实施前取证新增 F-S9-P016-1 未在 DESIGN D 表中 | DESIGN 增 D2 覆盖（本就含报告保护），并在 §2 D2 的「代价」列补「复放命令需知道保护会改名」 |

### 8.3 对齐矩阵

| 上游 → 下游 | 结果 |
|-------------|------|
| RESEARCH §5 四方案 → DESIGN D1-D4 | 一一对应（N-A→D4 / W-A→D1 / X-A→D3 / R-A→D2） |
| DESIGN I1-I6 → IMPL V1-V8 → CHECKLIST A/B/C 组 | 全覆盖，无孤立条 |
| IMPL T-5 → CHECKLIST D-1~D-4 | 逐项有验收 |

**Step 8 结论：通过**（P1=P2=0；P3×2 当场回写）。

---

## 9. Step 10 ADD 审计

### 9.1 四阶段

| 阶段 | 结果 |
|------|------|
| Phase 0 规格质量 | ✅ 四项决策均可证伪（三态计数、保护触发、守卫异常、文档映射） |
| Phase 1 完整性 | ✅ D1→`Checks` 三态；D2→`_resolve_report_target`；D3→守卫；D4→三处文档注 |
| Phase 2 忠实度 | ✅ 实现与 DESIGN §4-§6 规格逐条一致；无静默偏离（`_spec` 仅加守卫，`export/run` 零改动） |
| Phase 3 必要性 | ✅ 无未登记派生行为；新增 `MANUAL_MARKERS`/`_REPORT_MARK` 均在 DESIGN §4/§5 声明 |
| Phase 4 语义 | ✅ 本批意图 = 消除「形式恒真 / 静默未定义 / 静默覆盖」，三者均由红→绿实证消失；并修复了已发生的覆盖事件（§1/§3/§4 重新回填） |

### 9.2 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| `verify_p015` 全链（E1） | A-2/A-4/F-2/C-2 | ✅ 28 断言 + 1 豁免，exit 0 |
| `verify_p015` B5 单跑（E1） | A-1/A-4 | ✅ WAIVER 渲染 + exit 1 |
| 报告 §2 逐行 diff（E1） | A-3/D-2 | ✅ 29 行仅 1 行差异 |
| SHA256 前后比对（E1） | B-2 | ✅ `ORIG_UNCHANGED=True` |
| `_spec` 探针（E1） | C-1 | ✅ NotImplementedError |
| `git show HEAD:APPENDIX`（E1） | F-S9-P016-1 既成事实 | ✅ §1/§3/§4 为占位 |
| `pytest tests`（E1） | E-2 | ✅ 635 passed |
| `black --check`（E1） | E-3 | ✅ 5 files unchanged |
| `git status`（E1） | E-1 | ✅ 无 tests/、无 .github/ |
| 静态读码（E3 @本批提交） | A-1/B-1/B-3 | ✅ 三处实现锚点 |
| 盲区扫描（E4，范围：三态词表全分支 × 保护判定四象限 × 守卫正负路径） | A/B/C 全组 | **发现 1 项**：`_resolve_report_target` 只判「含标记」不判「是否为生成态」——若人工误删标记，保护失效；风险低（标记在 §1/§3 标题内，删除需显式编辑），登记于本表不单列 ID |
| E5 推测 | — | 无 |

### 9.3 审计结论

**P1 = 0 / P2 = 1（F-S9-P016-1，已修）/ P3 = 1（F-S9-P016-2，登记）**；E4 发现 1 项（低风险，不阻断）。ADD 通过。

---

## 9.4 RULE-5 异构复审（用户指派 2026-11-10；P-015 §9.4 先例）

**复审基座声明**：复审方 GLM-5.3-Flash ≠ 本批作者基座 DeepSeek-V4.1-Flash（异构性成立）。复审权限单向：只标记问题，不改判作者结论。复审对象 = 四文档 + 两脚本 @`bd50b54`（HEAD = origin/master，工作区干净）。

### E1 独立重放（10 项）

| # | 项 | 读数 |
|---|----|------|
| 1 | git 状态 | HEAD = origin/master = `bd50b54`，工作区干净 |
| 2 | black | `5 files would be left unchanged` |
| 3 | 主环境 pip | pandas 2.2.3 / numba 0.65.1，无 vectorbt（零污染） |
| 4 | .gitignore | `.venv-vbt/`、`.tmp_p015_cases/` 两目录忽略生效 |
| 5 | pytest | `635 passed, 152 warnings in 56.88s` |
| 6 | CI | `42815329691`（@`4a1cdb4`）success；`42815809194`（@`bd50b54`）success |
| 7 | 变更面 | `4a1cdb4` = scripts 2 + docs 9 + CHANGELOG 1（12 文件）；无 tests/、.github/ |
| 8 | venv 签名读数 | `audit_signatures.py` 独立重跑，与 APPENDIX §1 记录一致 |
| 9 | **生成物占位残留扫描**（采纳 F-S9-P016-2 建议） | docs/ 全域扫描命中 35 行 → 34 行为 RULE-1 合法占位（Step 7 时点声明）或历史记录引用；**唯一真实残留 = IMPL_p015 §8.5**（见 E4 F-R5-P016-2） |
| 10 | 报告保护正路径（真实入库路径） | `[保护] …改写 …generated.md`；原文件 git 零改动；`.generated.md` 存在（取证后已清理） |

### E2 运行时取证（新代码 3 探针 + worktree 旧代码红读数重放 3 组）

| 探针 | 场景 | 读数 |
|------|------|------|
| ① 全链复放 | 五 case export→run→verify | `28 断言（失败 0）+ 豁免 1`，exit 0；§2 读数与入库 APPENDIX 逐行一致（I1/I2/I4） |
| ② B5 单跑（负路径） | `--case-dir B5` | `G2 [B5] WAIVER(非断言)` + `共 4 项断言（失败 1 项）+ 豁免登记 1 项`，exit 1（I3 语义不变） |
| ③ 守卫正负双路径 | rate=0 / rate>0 | rate=0 正常返回；rate>0 `NotImplementedError`（文案含 case/rate/U-P016-1）（I6） |
| ④ 红读数 A 重放（@`90eb879` 旧代码） | 旧 verify B5 单跑 | `G2 [B5] PASS` + `共 5 项断言，失败 1 项` + exit 1——**与 IMPL §6.1 红读数逐字一致**（恒真豁免计为断言） |
| ⑤ 红读数 B 重放（同上） | 旧 `simulate_vbt_spec(cost_rate=0.001)` | 静默返回 `pv_last=9843199.479897`——**与 IMPL §6.1 记录逐位一致**（未验证语义静默产出） |
| ⑥ 红读数 C 重放（同上） | 旧 verify 全链 `--report` 指向入库报告副本 | `共 29 项断言，失败 0 项`（旧计数）+ 副本 L8/L47 变 `（T-1.4 读数回填区…）`/`（T-4 回填区…）`——**与 IMPL §6.1 记录一致（含行号）** |

> 重放技术注：旧 `--case-dir` 为 `nargs="+"` 单 flag；复审首跑误用多 flag 形态（argparse last-wins → 只处理 B5），改用正确形态后全链 29 断言复现。三组红→绿对照（旧 5 断言 / 静默产出 / 覆盖 ↔ 新 4+豁免 / 异常 / 改名）全部独立证实，F5 真实性成立。

### E3 静态锚点（@`bd50b54`，逐字核对）

| 锚点 | 实现 | 规格 |
|------|------|------|
| 三态词表 | `verify_p015.py:35`（`_STATUS_LABEL`）、`:49/:52/:56/:62`（`add/waive/_push/finalize`）、`:247`（`_REPORT_MARK`） | DESIGN §4 词表 + 汇总行格式（运行时读数逐字命中） |
| v3_only 豁免分支 | `:113-118` `checks.waive(...)` + `return pv_v3` | IMPL T-2（不变式保持） |
| 报告保护 | `:250` `MANUAL_MARKERS`、`:253-260` `_resolve_report_target`、`:304-309` 保护提示 | DESIGN §5 逐字一致 |
| fail-fast 守卫 | `_spec.py:159-165` | DESIGN §6 代码块逐字一致（含文案） |
| D-1/D-4 文档映射 | CHECKLIST_p015:34（C-2 I2a=G1 组三行）、DESIGN_p015 §3.2 命名映射注 | 互相指认成立 |
| D-3 费率前置 | RESEARCH_p015 U-P015-1「附加前置（P-016 / U-P016-1）」 | 指向成立 |
| B-4 口径更正 | CHECKLIST_p015:27「28 项断言 0 失败 + 1 项豁免登记（P-016 D1 更正计数口径）」 | 落位 |
| APPENDIX 回填 | §1/§3/§4 与 `audit_signatures` 现场读数 / M1-M5 / 实跑命令一致 | F-S9-P016-1 修复有效 |

### E4 盲区扫描（4 项 P3，均不阻断）

| ID | 级别 | 发现 | 处置建议 |
|----|------|------|----------|
| F-R5-P016-1 | P3 | PROGRESS §3.17.1 终态行「29 项断言 0 失败」为冻结历史读数，未加 P-016 口径更正注（对照 CHECKLIST_p015 B-4 已注） | 后续批次补「（P-016 更正口径：28 断言 + 1 豁免）」注 |
| F-R5-P016-2 | P3 | IMPL_p015 §8.5「门禁实测（T-4 时点）」为未回填占位（`（E-2 门禁读数回填区——…）`）——占位扫描唯一真实残留；门禁读数实际存在于 CHECKLIST/PROGRESS，非数据丢失 | 后续批次回填或删除该占位小节 |
| F-R5-P016-3 | P3 | `MANUAL_MARKERS` 子串匹配自指：生成模板自身含标记文本（`verify_p015.py:270/:287` 标题）→ `.generated.md` 再被 `--report` 指向会级联改名；CHECKLIST B-3「无标记 → 原路径写入」对生成器自身产物不可达（仅外部文件可达） | 行为无害（改名写入不丢数据）；如需精确，可改用「生成态指纹」区分 |
| F-R5-P016-4 | P3 | 本清单 E-1 实测列「docs/（6 文件）」与提交实际不符（docs/ 9 + CHANGELOG 1）；E-1 核心判定（无 tests/、.github/）不受影响 | 后续批次更正计数 |

### 复审结论

**pass（0 P1 / 0 P2 / 4 P3 登记）**。四项决策（D1-D4）实现与规格逐字一致；I1-I6 不变量全部独立证实；三组红→绿读数经 worktree 旧代码独立重放全部复现（含逐位一致），F5 真实性成立；F-S9-P016-1 的重新回填（§1/§3/§4）与现场读数一致。本复审同时验证 F-S9-P016-2 建议的扫描形态有效（命中 1 处真实残留）。

---

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | RESEARCH §7（RULE-4 自查·单视角） | 2026-11-10 |
| Step 3-4 设计 + Review | 通过 | DESIGN §7（RULE-4 自查·单视角） | 2026-11-10 |
| Step 5-6 实施规划 + Review | 通过 | IMPL §5（RULE-4 自查·单视角） | 2026-11-10 |
| Step 7-8 验收清单 + 一致性 | 通过 | §8（RULE-4 自查·单视角；P3×2 回写） | 2026-11-10 |
| Step 9 TDD 实施 | 完成 | IMPL §6.1 三组红→绿 | 2026-11-10 |
| Step 10 ADD 审计 | 通过 | §9（Phase 0-4 + 取证矩阵） | 2026-11-10 |
| RULE-5 异构复审 | pass | §9.4（复审基座 GLM-5.3-Flash ≠ 作者基座；0 P1/P2，4 P3 登记） | 2026-11-10 |
