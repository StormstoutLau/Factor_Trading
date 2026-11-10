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
| B-3 | 分支 1 真实覆盖（V3） | 目标不存在 → 原地新建、`FRESH_EXISTS=True` 读数入档 | ✅ E1：探针 ⑥（含不存在的父目录）→ `FRESH_EXISTS=True`，内容含「恒等式逐条读数」，读数已入 [IMPL_p018 §6.2](IMPL_p018_p017_review_fixes.md#L101) |

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

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | RESEARCH §7（RULE-4 自查·单视角） | 2026-11-10 |
| Step 3-4 设计 + Review | 通过 | DESIGN §6（RULE-4 自查·单视角） | 2026-11-10 |
| Step 5-6 实施规划 + Review | 通过 | IMPL §5（RULE-4 自查·单视角） | 2026-11-10 |
| Step 7-8 验收清单 + 一致性 | 通过 | §8（RULE-4 自查·单视角；0 发现） | 2026-11-10 |
| Step 9 TDD 实施 | 完成 | IMPL §6（F5 红→绿 + 8 探针） | 2026-11-10 |
| Step 10 ADD 审计 | 通过 | §9（Phase 0-4 + 取证矩阵） | 2026-11-10 |
| RULE-5 异构复审 | 未执行 | P3 小修批；如需按 P-017 先例单独发起 | — |
