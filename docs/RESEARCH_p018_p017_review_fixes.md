# RESEARCH：P-018 P-017 复审 E4 两项 P3 修正

> **批次**: P-018 · **T1**（改动落 `scripts/external_benchmark/verify_p015.py`，Layer-1；SPEC_PROCESS v1.7.2 §判档规则 1）
> **上游**: [CHECKLIST_p017_p016_review_fixes.md](CHECKLIST_p017_p016_review_fixes.md) §9.4 E4（F-R5-P017-1 / F-R5-P017-2）；PROGRESS §3.19
> **代码证据时点**: HEAD `97b71b2`（工作区干净，E1 2026-11-10）
> **状态**: Step 1 完稿 + Step 2 Review 通过（§7）；待进 Step 3

---

## 1. 背景与目标

P-017 的 RULE-5 异构复审（GLM-5.3-Flash，[§9.4](CHECKLIST_p017_p016_review_fixes.md)）输出 2 项 P3：

- **F-R5-P017-1**：生成物守卫在**无扩展名目标**下失效（`Path("X.generated").stem == "X"`，后缀被剥离）→ 二次运行仍级联改名。
- **F-R5-P017-2**：分支 1（目标不存在）的**覆盖归因失实**——作者探针 A①/C/D 的目标在运行前均已存在，未真正覆盖该分支。

**目标**：让守卫判定覆盖「无扩展名」形态；更正分支 1 的取证归因并补真实覆盖。不改恒等式结论、不改断言语义、不改命名契约。

**职责外（不回答）**：`MANUAL_MARKERS` 判据的生成态指纹化重构；U-P015-1 / U-P016-1。

**能力边界（回答不了）**：本地默认 TkAgg 后端全量 pytest 的间歇 `TclError`——属环境态，不在本批修复范围（复审观察项）。

---

## 2. 本仓事实（P1-P4）

| # | 事实 | 证据 |
|---|------|------|
| P1 | **F-R5-P017-1**：守卫为 `path.stem.endswith(GENERATED_SUFFIX)`；`Path("rep.generated").stem == "rep"`、`suffix == ".generated"` ⇒ 判定 False，落入分支 3 → 改名 `rep.generated.generated` | E3 @`97b71b2` [verify_p015.py](../scripts/external_benchmark/verify_p015.py) L268、L272；E1 红读数 A（§4） |
| P2 | **F-R5-P017-2**：IMPL §6.2 注与 CHECKLIST C-4 称分支 1「由 A① 产生成物时的首次写入与探针 C/D 的新建路径覆盖」；实际 A① 传入目标是**已存在的策展版主文件**（分支 3）、C 的副本与 D 的目标在运行前均已存在（分支 3/4） | E3 @`97b71b2` [IMPL_p017](IMPL_p017_p016_review_fixes.md) L119；[CHECKLIST_p017](CHECKLIST_p017_p016_review_fixes.md) L33 |
| P3 | 正常 `.md` 形态的四分支行为为绿：全链 `28 断言 + 豁免 1` exit 0；分支 2 原地、分支 3 改名 + 原文件不变、分支 4 原地覆盖 | E1 复审 §9.4 E2 ①-④；本批复核（§4 读数 B） |
| P4 | 本地全量 `pytest` 需 `MPLBACKEND=Agg`：默认 TkAgg 间歇 `TclError: not enough free memory for image buffer`（环境态，CI 干净环境双 run success） | E1 复审 §9.4 E1 #6；本批沿用该形态取证 |

> P1 与 P2 相互独立：前者是**代码判定**缺陷（行为面），后者是**文档归因**缺陷（证据面）；二者不可合并为单因。

---

## 3. 外部来源

**无外部来源**。两项发现均来自本仓 RULE-5 复审记录。
按 SPEC_PROCESS v1.7.2 §契约取证字段形态：**F1 / F2 / F3 = N/A（无外部来源，不涉检索通道）**；**F4 = N/A（外部引用 0 条 <3）**。仓内证据以 E3 的 commit + 行号区间替代版本号。

---

## 4. 本轮 E1 取证（2026-11-10 @`97b71b2`）

| 读数 | 命令 | 结果 |
|------|------|------|
| **A（F-R5-P017-1 缺陷实证）** | `verify_p015.py --case-dir B1 --report <tmp>\rep.generated` 连跑两次 | 两次均退出；产物 `rep.generated`（1820B）+ `rep.generated.generated`（1820B）⇒ **级联发生** |
| **B（正常形态绿态）** | 五 case 全链 → 策展版主文件 | `28 断言（失败 0）+ 豁免 1`；生成物 `APPENDIX…generated.md` 单份（无二次级联） |
| **C（归因复核）** | 逐条重读 P-017 探针 A①/C/D 的目标路径 | A① 目标 = 已存在的 `docs/APPENDIX….md`；C 副本由 `shutil.copyfile` 预置；D 目标预先 `write_text` ⇒ **分支 1 未被覆盖**（P2 成立） |

> 取证产物（`%TEMP%\p018_red\`）不入仓；`docs/` 未产生生成物。

---

## 5. 方案矩阵

### 5.1 F-R5-P017-1（无扩展名目标的守卫）

| 方案 | 内容 | 判定 |
|------|------|------|
| **G-A 并判 name 与 stem** | `path.name.endswith(GENERATED_SUFFIX) or path.stem.endswith(GENERATED_SUFFIX)`：前者覆盖「无扩展名」（`X.generated`），后者覆盖「有扩展名」（`X.generated.md`） | **推荐**——单行 1:1 替换，零行号位移；两种形态都命中 |
| G-B `name.endswith(GENERATED_SUFFIX + suffix)` | 用后缀拼接判定 | 否决——无扩展名时 `suffix == ".generated"` ⇒ 实际判 `.generated.generated`，**仍失效** |
| G-C 只判 name | `path.name.endswith(GENERATED_SUFFIX)` | 否决——漏掉 `X.generated.md`（name 以 `.md` 结尾），会回归 F-R5-P016-3 的原始缺陷 |
| G-D 抽出 `_is_generated_target()` 辅助函数 | 提为独立函数便于单测 | 否决——P-017 的 CHECKLIST C-1 以行号锚定 `:254/:268/:272`，新增函数会造成行号位移并连带改文档；本批以「零位移」为约束 |

### 5.2 F-R5-P017-2（分支 1 覆盖归因）

| 方案 | 内容 | 判定 |
|------|------|------|
| **N-A 追加更正注 + 补真实覆盖探针** | 保留 IMPL §6.2 原句，追加 P-018 更正（说明分支 1 未被 A①/C/D 覆盖）；Step 9 新增「目标不存在」探针取得真实读数 | **推荐**——冻结记录不改写，缺口可见且被实际补上 |
| N-B 静默改写原句 | 直接把归因改成正确表述 | 否决——抹掉「曾误判」的痕迹，后续复审无法据此评估取证质量 |
| N-C 只改文档不补探针 | 仅更正表述 | 否决——分支 1 仍无直接证据，属「改了话术没改证据」 |

---

## 6. 未决项登记

**（无）**。本批关闭 2 个既有发现（F-R5-P017-1/-2），不新开未决项。

---

## 7. Step 2 Review（调研文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明：与正文同会话，无第二视角；RULE-5 复审按惯例留待用户指派（若要求）。

- [x] 引用可解析：全部为仓内文件 + commit 绑定 + 行号（四文档 + 脚本 + PROGRESS）
- [x] 无未标注推测：P1 有 E1 红读数 A（两次运行产物）+ E3 代码行；P2 有 E1 读数 C（逐条复核探针目标）
- [x] 门禁 (a) FALSIFIED：**无**（复审 2 项均被本轮复核为真）
- [x] 门禁 (b) CONFLICT / STEP_GAP_OPEN：**无**（两项均为 P3，不推翻 P-017 的 pass）
- [x] 门禁 (c) 阻断性断言双源：缺陷 1 **双证**（E1 红 A + E3 `Path.stem` 语义）；缺陷 2 **双证**（E1 读数 C + E3 三处探针目标路径）
- [x] 门禁 (d) 假设区：无新假设（G-B 失效已在 §5.1 给出机制）

**Step 2 Review 结论：通过**。可进入 Step 3 DESIGN。
