# IMPL：P-019 报告写入父目录缺失修正

> **批次**: P-019 · T1
> **上游**: [DESIGN_p019_report_parent_dir.md](DESIGN_p019_report_parent_dir.md)（D1-D2 / I1-I4 / §4 实现规格）
> **下游**: [CHECKLIST_p019_report_parent_dir.md](CHECKLIST_p019_report_parent_dir.md)
> **状态**: Step 5 完稿 + Step 6 Review 通过（§5）；Step 9 实施记录见 §6

---

## 1. 任务分解（T-1 ~ T-3）

### T-1 父目录自动创建（D1 / F-R5-P018-1）

文件：`scripts/external_benchmark/verify_p015.py`

| 位置 | 改动 | 行数影响 |
|------|------|----------|
| `write_report` 内 `write_text` 前（`:322`/`:323` 之间） | 插入 `target.parent.mkdir(parents=True, exist_ok=True)` + 同行注释 | +1 行；位于 `:272` 之后 ⇒ `:254/:268/:272` 锚点零位移 |

### T-2 归因更正（D2）

| 文件 | 位置 | 改动 |
|------|------|------|
| `docs/IMPL_p018_p017_review_fixes.md` | §6.2 探针 ⑥ 行（L101） | 原句保留 + 追加 P-019 更正注（说明该形态在 P-018 会崩溃、父目录由探针预建；P-019 已修复并补真探针） |
| `docs/CHECKLIST_p018_p017_review_fixes.md` | B-3 实测列 | 追加 P-019 注（同上，指向本批 §6.2 读数） |

### T-3 批次登记

| 文件 | 改动 |
|------|------|
| `docs/PROGRESS.md` §3.21 | P-019 执行记录 |
| `CHANGELOG.md` Fixed | P-019 条目 |

---

## 2. 验证项（V1-V5）

| # | 验证项 | 判据 |
|----|--------|------|
| V1 | 父目录缺失可写（I2） | `--report <tmp>\nodir\fresh.md` → exit 0、文件存在、内容含「恒等式逐条读数」 |
| V2 | 多级父目录（I2） | `--report <tmp>\a\b\c\r.md` → exit 0、路径全建成 |
| V3 | 父目录存在不回归（I1） | 四分支 + 无扩展名守卫读数与 P-018 一致 |
| V4 | 全链不变（I3） | `28 断言（失败 0）+ 豁免 1`，exit 0 |
| V5 | 锚点零位移（I4）与门禁 | `:254/:268/:272` 语义不变；black 5 unchanged；pytest 635 passed（Agg） |

---

## 3. 风险与回退

| 风险 | 预案 |
|------|------|
| mkdir 掩盖路径拼写错误（如误写 `report/2026/x.md` 生成幽灵目录） | 属预期行为：`--report` 显式指定路径，自动建目录是常见 CLI 语义（同 `git init` 行为） |
| 无写权限时仍崩溃 | 本批边界：只处理「不存在」，`PermissionError` 照常抛出（不吞异常） |
| 插入行使后续行号漂移 | 仅影响 `:323+`；已确认文档只引用 `:254/:268/:272` 与 L252-273 区间 |

---

## 4. 排除的低效操作

- 不新增 pytest（P7 纪律），回归由 CLI 探针承担
- 不在 `_resolve_report_target` 内做 I/O（M-C 已否决）
- 不引入 `try/except` 包装（M-B 已否决）

---

## 5. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本：无新增依赖；`pathlib.Path.mkdir` 为 stdlib
- [x] stdlib API 下限：`mkdir(parents=, exist_ok=)` 自 3.5 可用，3.12 无虞
- [x] API 签名可实现：`write_report` 签名不变
- [x] 兼容性：父目录已存在时 `exist_ok=True` 为 no-op，四分支不受影响
- [x] 低效操作已排除（§4）
- [x] 回退点：单行删除即可回退

**Step 6 Review 结论：通过**。

---

## 6. Step 9 实施记录（2026-11-10 回填）

### 6.1 F5 红→绿（F-R5-P018-1）

| 组 | 红（改前 @`6149cc6`） | 绿（改后 @本批） |
|----|----------------------|------------------|
| **A（父目录缺失）** | `--report <tmp>\p019_red\nodir\fresh.md` → `FileNotFoundError: [Errno 2] …` traceback，**exit 1** | 同形态 → `EXIT=0 EXISTS=True`，内容含「恒等式逐条读数」 |

### 6.2 探针读数（8 项全 PASS）

| 探针 | 场景 | 读数 |
|------|------|------|
| ① 父目录不存在（V1） | `<tmp>\nodir\fresh.md`（五 case） | `EXIT=0 EXISTS=True`，报告内容完整 |
| ② 多级父目录（V2） | `<tmp>\a\b\c\r.md` | `EXIT=0`，`a/b/c` 全建成 |
| ③ 父目录已存在（V3） | 普通 `.md`（无标记） | 原地覆盖，内容为报告 |
| ④ 全链（V4） | 五 case → 策展版主文件 | `28 断言（失败 0）+ 豁免 1`，exit 0；生成物单份 |
| ⑤ 分支 3 副本（V3） | 策展版副本 | 改名 + 原文件 SHA 不变 |
| ⑥ 无扩展名 ×2（P-018 不回归） | `rep.generated` 两次 | `EXIT=0`，无 `rep.generated.generated` |
| ⑦ 锚点零位移（I4） | `:254/:268/:272` 语义 | PASS |

> 探针首轮曾误判：①②⑥ 仅传 B1（I5 跨 case 阴性对照未齐 → exit 1），文件实际已建成；改传五 case 后均为 exit 0。**该 exit 1 属 I5 语义，不是父目录缺陷**。

### 6.3 终态读数

| 项 | 读数 |
|----|------|
| 全链断言（I3） | `共 28 项断言（失败 0 项）+ 豁免登记 1 项`，exit 0 |
| `black --check scripts/external_benchmark/` | `5 files would be left unchanged` |
| `pytest tests` | **635 passed, 152 warnings in 64.29s**（`MPLBACKEND=Agg`） |
| 变更面 | `verify_p015.py`（+1 行 mkdir）+ docs；无 tests/、.github/ |
| 取证产物 | 已清理，`git status` 仅含本批预期改动 |
