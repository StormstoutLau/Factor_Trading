# CHECKLIST：P-018 P-017 复审 E4 两项 P3 修正

> **批次**: P-018 · T1
> **上游**: [IMPL_p018_p017_review_fixes.md](IMPL_p018_p017_review_fixes.md)（T-1~T-3 / V1-V5）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **状态**: Step 7 完稿（零预填）

---

## 1. 验收项

### A 组：守卫判定（F-R5-P017-1）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| A-1 | 守卫并判 name 与 stem（I2 前置） | 静态读码：`:268` 含 `path.name.endswith` **且** `path.stem.endswith` | ✅ E3：[verify_p015.py](../scripts/external_benchmark/verify_p015.py#L268) `if path.name.endswith(GENERATED_SUFFIX) or path.stem.endswith(GENERATED_SUFFIX):` |
| A-2 | 无扩展名不级联（I2，V1） | `X.generated` 连跑两次 → 无 `X.generated.generated` | ✅ E1：探针 ② → `noext_exists=True cascade=False -> PASS`（红读数：改前两文件并存 1820B×2） |
| A-3 | `X.generated.md` 仍不级联（P-017 不回归） | 指向 `…generated.md` 复放 → 原地、无二次级联 | ✅ E1：探针 ③ → 原地写入、无 `[保护]`、无 `…generated.generated.md` |
| A-4 | 行号零位移 | `:254` 常量 / `:268` 守卫 / `:272` 改名仍指向同一语义 | ✅ E1：探针 ⑦ `:254/268/272 语义 -> PASS`（`splitlines()` 逐行断言） |

### B 组：归因更正（F-R5-P017-2）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| B-1 | 原句逐字保留（I4） | IMPL_p017 §6.2 仍含「由 A① 产生成物时的首次写入与探针 C/D 的新建路径覆盖」 | ✅ E1：[IMPL_p017 §6.2](IMPL_p017_p016_review_fixes.md#L119) 原句逐字保留，更正注为追加段 |
| B-2 | 追加 P-018 更正注 | IMPL_p017 §6.2 与 CHECKLIST_p017 C-4 均含「P-018 更正」 | ✅ E1：两处均含「P-018 更正」（IMPL L121 / CHECKLIST L33） |
| B-3 | 分支 1 真实覆盖（V3） | 目标不存在 → 原地新建、`FRESH_EXISTS=True` 读数入档 | ✅ E1：探针 ⑥（含不存在的父目录）→ `FRESH_EXISTS=True`，内容含「恒等式逐条读数」，读数已入 [IMPL_p018 §6.2](IMPL_p018_p017_review_fixes.md#L101) —— **P-019 更正**：该探针实际预建了父目录；「父目录不存在」形态在 P-018 时点会抛 `FileNotFoundError`（F-R5-P018-1），P-019 已修复并补真探针（见 [P-019 §6.2](IMPL_p019_report_parent_dir.md)） |

### C 组：纪律面与回归

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| C-1 | 四分支不回归（I1，V2） | 普通 `.md` 分支 2/3/4 读数与 P-017 一致（分支 3 SHA 不变） | ✅ E1：探针 ③④⑤ 全 PASS（分支 3 `SHA` 不变 + 改名存在；分支 4 原地覆盖） |
| C-2 | 全链结论不变（I3，V4） | `28 断言（失败 0）+ 豁免 1`，exit 0 | ✅ E1：探针 ① → `28 断言（失败 0）+ 豁免 1`，exit 0，生成物单份 |
| C-3 | 门禁与纪律（V5） | `pytest` 635 passed（Agg）/ black 5 unchanged / 无 tests/、.github/ 变更 | ✅ E1：`635 passed, 152 warnings in 64.62s`；`5 files would be left unchanged`；`git status` 无 tests/、.github/ |

---

## 2. 统计

- 总数：**10 项**（A4 / B3 / C3）
- 状态：**10/10 ✅**（逐项绑证据，RULE-2 逐项核对）
- 发现：**P1 = 0 / P2 = 0 / P3 = 0**

---

## 3. 后续章节

Step 8 一致性 Review（§8）、Step 10 ADD 审计（§9）、签字表（§10）在对应步骤完成后追加。

---

## 8. Step 8 一致性 Review

**执行时点**：四文档完稿后的独立 pass（RULE-1）；**[RULE-4] 自查（单视角）**。

### 8.1 机械校验读数（2026-11-10）

| 校验项 | 读数 |
|--------|------|
| 链接存在性 | 8/8 OK（RESEARCH 2 / DESIGN 3 / IMPL 2 / CHECKLIST 1），0 broken |
| 预填检查（RULE-1） | `✅` 命中 **1 处 = L5 规则声明行本身**（合法）；10 项实测列全 `[待 Step 9]` |
| ID 引用闭环 | F-R5-P017-1(9) / -2(7)、I1(6)/I2(4)/I3(3)/I4(4)、D1(6)/D2(7)、T-1(3)/T-3(3)、V1(6)/V5(4) —— 全部 ≥3 且跨文档 |

### 8.2 对齐矩阵

| 上游 → 下游 | 结果 |
|-------------|------|
| RESEARCH §5 两方案 → DESIGN D1-D2 | 一一对应（G-A→D1 / N-A→D2） |
| DESIGN I1-I4 → IMPL V1-V5 → CHECKLIST A/B/C 组 | 全覆盖（I1→V2/C-1；I2→V1/A-2；I3→V4/C-2；I4→B-1） |
| IMPL T-1~T-3 → CHECKLIST A/B/C 组 | 逐项有验收（T-1→A；T-2→B；T-3 由 §9/§10 与批次登记承接） |

### 8.3 一致性发现

| ID | 发现 | 处置 |
|----|------|------|
| （无） | 四文档无矛盾；行号引用（`:254/:268/:272`、`:261`）与本批约束（零位移）自洽 | — |

**Step 8 结论：通过**。

---

## 9. Step 10 ADD 审计

### 9.1 四阶段

| 阶段 | 结果 |
|------|------|
| Phase 0 规格质量 | ✅ 两项决策均可证伪（无扩展名级联产物不存在 / 归因注存在且原句保留） |
| Phase 1 完整性 | ✅ D1→守卫单行替换（含 docstring 同步）；D2→两处更正注 + 探针 ⑥ |
| Phase 2 忠实度 | ✅ 实现与 DESIGN §4/§5 逐字一致；`_spec.py`/`export_case.py`/`run_vectorbt.py` 零改动 |
| Phase 3 必要性 | ✅ 无未登记派生行为；未新增函数/常量/依赖 |
| Phase 4 语义 | ✅ 意图 = 消除「守卫边界失效 / 取证归因失实」，两者均有红→绿与实读证实 |

### 9.2 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| 无扩展名探针 ×2（E1） | A-2 / I2 | ✅ `cascade=False` |
| `X.generated.md` 探针（E1） | A-3 / I1 | ✅ 原地、无二次级联 |
| 四分支探针 ③④⑤（E1） | C-1 / I1 | ✅ 全 PASS（含分支 3 SHA） |
| 分支 1 探针 ⑥（E1） | B-3 | ✅ `FRESH_EXISTS=True` |
| 全链复放（E1） | C-2 / I3 | ✅ 28 断言 + 1 豁免，exit 0 |
| 行号锚点断言（E1/E3） | A-4 | ✅ `:254/:268/:272` 语义不变 |
| `pytest` / `black`（E1） | C-3 | ✅ 635 passed / 5 unchanged |
| 静态读码（E3 @本批提交） | A-1 / B-1 / B-2 | ✅ 三处实现与注锚点 |
| 盲区扫描（E4，范围：守卫判定四种路径形态 × 归因表述 × 行号引用） | A/B/C 全组 | **发现 1 项**：`a.generated.bak` 形态的 stem 为 `a.generated` ⇒ 判为生成物并原地覆盖——属命名契约内的后果（`.generated` 域归生成器），已在 DESIGN §3 风险表登记，不单列 ID |
| E5 推测 | — | 无 |

### 9.3 审计结论

**P1 = 0 / P2 = 0 / P3 = 0**；E4 发现 1 项（契约内后果，不阻断）。ADD 通过。

---

## 9.4 RULE-5 异构复审（用户指派 2026-11-10；P-017 §9.4 先例）

**复审基座声明**：复审方 GLM-5.3-Flash ≠ 本批作者基座 DeepSeek-V4.1-Flash（异构性成立）。复审权限单向：只标记问题，不改判作者结论。复审对象 = P-018 四文档 + `verify_p015.py` 守卫改动 @`ba24312`（HEAD = origin/master，工作区干净）。

### E1 独立重放（8 项）

| # | 项 | 读数 |
|---|----|------|
| 1 | git 状态 | HEAD = origin/master = `ba24312`，工作区干净 |
| 2 | CI | `42837224919`（@`0410505`）success；`42838015633`（@`ba24312` 回填提交）success（独立重查） |
| 3 | 变更面 | `0410505` = scripts 1 + docs 7 + CHANGELOG 1（9 文件）；无 tests/、.github/（与 IMPL §6.3 声明一致） |
| 4 | 项目解释器 | Python 3.12.10；pandas 2.2.3 / numba 0.65.1 / **无 vectorbt** |
| 5 | black | `5 files would be left unchanged` |
| 6 | pytest（Agg） | **`635 passed, 152 warnings in 69.93s`**（与作者 64.62s 计数一致、时长漂移正常） |
| 7 | 占位扫描（沿用建议） | 目标形态模板占位命中 **3 行，全部为历史记录引用**（CHECKLIST_p016:186 / IMPL_p017:25 / RESEARCH_p017:27——均在描述已修复的占位）；真实占位残留 **0** |
| 8 | 代码零位移 | `:254` 常量 / `:268` 守卫 / `:272` 改名——与 P-017 C-1、P-018 A-4 行号引用完全一致 |

### E2 运行时取证（11 项读数，全部 PASS）

| 探针 | 场景 | 读数 |
|------|------|------|
| ① 全链复放（I3） | 五 case → 策展版主文件 | `28 断言（失败 0）+ 豁免 1`，exit 0；生成物单份 |
| ② 无扩展名 ×2（I2，本批修复对象） | `rep.generated` 两次 | `cascade=False`，原地更新 |
| ③ `X.generated.md`（P-017 不回归） | 指向生成物复放 | 原地、无 `[保护]`、无二次级联 |
| ④ 分支 3（I1） | 策展版副本 | 改名 + 原文件 SHA 不变 |
| ⑤ 分支 4（I1） | 存在无标记 | 原地覆盖 |
| ⑥ 分支 1（I1） | 目标不存在（父目录预建） | 原地新建 |
| ⑦ **幂等形态（命中矩阵第 4 行）** | `X.generated.generated` ×2 | 无 `X.generated.generated.generated` 膨胀 |
| ⑧ B5 单跑（I3） | 负路径 | `WAIVER(非断言)` + `4 断言（失败 1）+ 豁免 1`，exit 1 |
| ⑨ P-016 守卫 | rate>0 / rate=0 | `NotImplementedError` / 正常返回 |
| ⑩ **红读数重放 @`97b71b2`** | 旧代码（stem-only 判定）无扩展名 ×2 | **`rep.generated.generated` 产生（True）**——与 IMPL §6.1 红 A 复现，与新代码 ② 红绿对照成立 |
| ⑪ **父目录不存在** | `--report <tmp>\nodir\fresh.md` | **`FileNotFoundError` traceback，exit 1（未捕获）**——见 E4 F-R5-P018-1 |

### E3 静态锚点（@`ba24312`，逐字核对）

| 锚点 | 实现 | 规格 |
|------|------|------|
| 守卫判定 | `:268` `path.name.endswith(...) or path.stem.endswith(...)` | DESIGN §4 判定规格逐字一致 |
| docstring | `:261` 「**name 或 stem**…无扩展名时 stem 会剥离后缀」 | 同步落位 |
| 零位移 | `:254/:272` 与 P-017 时点逐字一致 | IMPL §1 T-1 约束达成；P-017 复审的行号漂移观察项**未复发** |
| 归因更正 | IMPL_p017 §6.2 L119 原句保留 + L121 P-018 注；CHECKLIST_p017 C-4 L33 注 | D2/I4 落位 |
| 命中矩阵 | 四形态（`X.md` / `X.generated.md` / `X.generated` / `X.generated.generated`） | DESIGN §4 矩阵逐行经 E2 ③②⑦ 实证 |

### E4 盲区扫描（1 项 P3 + 1 观察，均不阻断）

| ID | 级别 | 发现 | 处置建议 |
|----|------|------|----------|
| F-R5-P018-1 | P3 | **分支 1「父目录不存在」形态未被覆盖且声明失实**：`--report <tmp>\nodir\fresh.md` 实测 `FileNotFoundError` traceback、exit 1（`write_text` 无父目录容错，E2 ⑪）；IMPL §6.2 探针 ⑥ 声称「目标不存在（**含不存在的父目录**）」——若真传该形态会崩溃而非 `FRESH_EXISTS=True`，作者探针必然预建了父目录。**F-R5-P017-2 的归因失实模式复发** | 后续批次二选一：① `write_report` 增 `target.parent.mkdir(parents=True, exist_ok=True)` 并补真探针；② 更正 IMPL §6.2 归因表述（删「含不存在的父目录」） |
| （观察） | — | `endswith` 大小写敏感：Windows 不区分大小写文件系统上 `X.GENERATED.md` 不命中守卫（生成器自身不产出大写形态，无现实触发面） | 登记备查 |

> 复核确认：作者 §9.2 已登记的 `a.generated.bak`（stem 命中 → 原地覆盖）属命名契约内后果，本批无新发现。

### 复审结论

**pass（0 P1 / 0 P2 / 1 P3 登记 + 1 观察）**。两项决策（D1/D2）实现与规格逐字一致；命中矩阵四形态 + 幂等形态全部独立证实；F5 红读数经 worktree 旧代码重放复现，修复真实性成立；行号零位移达成（P-017 观察项未复发）；两处归因更正落位。E4 一项 P3 为守卫边界的覆盖声明问题，不阻断验收。

---

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | RESEARCH §7（RULE-4 自查·单视角） | 2026-11-10 |
| Step 3-4 设计 + Review | 通过 | DESIGN §6（RULE-4 自查·单视角） | 2026-11-10 |
| Step 5-6 实施规划 + Review | 通过 | IMPL §5（RULE-4 自查·单视角） | 2026-11-10 |
| Step 7-8 验收清单 + 一致性 | 通过 | §8（RULE-4 自查·单视角；0 发现） | 2026-11-10 |
| Step 9 TDD 实施 | 完成 | IMPL §6（F5 红→绿 + 8 探针） | 2026-11-10 |
| Step 10 ADD 审计 | 通过 | §9（Phase 0-4 + 取证矩阵） | 2026-11-10 |
| RULE-5 异构复审 | pass | §9.4（复审基座 GLM-5.3-Flash ≠ 作者基座；0 P1/P2，1 P3 登记） | 2026-11-10 |
