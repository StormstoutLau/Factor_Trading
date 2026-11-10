# RESEARCH：P-019 报告写入父目录缺失修正

> **批次**: P-019 · **T1**（改动落 `scripts/external_benchmark/verify_p015.py`，Layer-1；SPEC_PROCESS v1.7.2 §判档规则 1）
> **上游**: [CHECKLIST_p018_p017_review_fixes.md](CHECKLIST_p018_p017_review_fixes.md) §9.4 E4（F-R5-P018-1）；PROGRESS §3.20
> **代码证据时点**: HEAD `6149cc6`（工作区干净，E1 2026-11-10）
> **状态**: Step 1 完稿 + Step 2 Review 通过（§7）；待进 Step 3

---

## 1. 背景与目标

P-018 的 RULE-5 复审输出 F-R5-P018-1：`verify_p015.py --report <路径>` 在**父目录不存在**时直接抛出未捕获的 `FileNotFoundError`（traceback + exit 1），且 P-018 的探针 ⑥ 声称覆盖了「含不存在的父目录」形态——声明与行为不符。

**目标**：① 让 `--report` 在父目录缺失时自动创建并正常写入；② 更正探针 ⑥ 的覆盖声明并补真实读数。

**职责外（不回答）**：`MANUAL_MARKERS` 判据重构；`endswith` 大小写敏感观察项；U-P015-1 / U-P016-1。

**能力边界（回答不了）**：无写权限路径（如系统目录）的 `PermissionError`——本批只处理「父目录不存在」，权限类失败仍按原样抛出（不吞异常）。

---

## 2. 本仓事实（P1-P4）

| # | 事实 | 证据 |
|---|------|------|
| P1 | **F-R5-P018-1**：`write_report` 末尾直接 `target.write_text(...)`（`:323`），无父目录创建；父目录缺失时抛 `FileNotFoundError` 且未捕获 | E3 @`6149cc6` [verify_p015.py](../scripts/external_benchmark/verify_p015.py) L317-324；E1 红读数 A（§4） |
| P2 | 同一函数的写入点唯一：`_resolve_report_target` 只解析（无副作用），`write_text` 仅此一处 | E3 @`6149cc6` L257-273、L323 |
| P3 | P-018 探针 ⑥ 的记录为「目标不存在（**含不存在的父目录**）」→ `FRESH_EXISTS=True`；但该形态真传会崩溃，作者探针必然预建了父目录 | E3 @`6149cc6` [IMPL_p018](IMPL_p018_p017_review_fixes.md) L101；E1 红读数 A |
| P4 | 现行四分支与无扩展名守卫（P-017/P-018）在父目录存在时行为为绿：全链 `28 断言 + 豁免 1` exit 0 | E1 复审 §9.4 E2 ①-⑦；本批复核（§4 读数 B） |

---

## 3. 外部来源

**无外部来源**。发现来自本仓 RULE-5 复审记录。
按 SPEC_PROCESS v1.7.2 §契约取证字段形态：**F1 / F2 / F3 = N/A（无外部来源）**；**F4 = N/A（外部引用 0 条 <3）**。仓内证据以 E3 commit + 行号替代版本号。

---

## 4. 本轮 E1 取证（2026-11-10 @`6149cc6`）

| 读数 | 命令 | 结果 |
|------|------|------|
| **A（缺陷实证）** | `verify_p015.py --case-dir B1 --report <tmp>\p019_red\nodir\fresh.md`（父目录 `nodir` 不存在） | `FileNotFoundError: [Errno 2] No such file or directory: '…\nodir\fresh.md'`；**exit 1** |
| **B（绿态基线）** | 五 case 全链 → `docs/APPENDIX_p015_external_calibration.md` | `28 断言（失败 0）+ 豁免 1`，exit 0 |
| **C（写入点唯一性）** | `Grep 'write_text' verify_p015.py` | 命中 2 处：`:270`（读文本）、`:323`（写报告）——写入点唯一（P2 成立） |

> 取证产物在 `%TEMP%`，`docs/` 未产生生成物。

---

## 5. 方案矩阵

| 方案 | 内容 | 判定 |
|------|------|------|
| **M-A 写入前 `mkdir(parents=True, exist_ok=True)`** | 在 `:323` 之前插入 `target.parent.mkdir(parents=True, exist_ok=True)`（1 行） | **推荐**——与 `write_text` 同点、幂等、多级父目录一次到位；`:254/:268/:272` 锚点零位移 |
| M-B 捕获异常并给友好提示 | `try/except FileNotFoundError` → 打印「请先创建目录」 | 否决——把可自动完成的事推给用户；仍是失败路径 |
| M-C 在 `_resolve_report_target` 内 mkdir | 解析阶段创建目录 | 否决——解析函数本应无副作用（当前四分支纯判定），混入 I/O 破坏可测性 |
| M-D 仅更正文档 | 删掉「含不存在的父目录」表述 | 否决——行为缺陷仍在；复审的建议是「二选一」，本批取「修复 + 更正」 |

---

## 6. 未决项登记

**（无）**。本批关闭 1 个既有发现（F-R5-P018-1），不新开未决项。

---

## 7. Step 2 Review（调研文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明：与正文同会话，无第二视角；RULE-5 复审按惯例留待用户指派（若要求）。

- [x] 引用可解析：仓内文件 + commit 绑定 + 行号（`L317-324`、`L257-273`、`L101`）
- [x] 无未标注推测：P1/P3 有 E1 红读数 A（崩溃原文）；P2 有 E1 读数 C（写入点唯一）
- [x] 门禁 (a) FALSIFIED：**无**（复审发现被本轮复核为真）
- [x] 门禁 (b) CONFLICT / STEP_GAP_OPEN：**无**（P3 级，不推翻 P-018 的 pass）
- [x] 门禁 (c) 阻断性断言双源：缺陷 **双证**（E1 红读数 A + E3 `:323` 无 mkdir）
- [x] 门禁 (d) 假设区：无新假设（M-A 的幂等性由 `exist_ok=True` 语义保证，Step 9 实测）

**Step 2 Review 结论：通过**。可进入 Step 3 DESIGN。
