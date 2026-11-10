# IMPL：P-018 P-017 复审 E4 两项 P3 修正

> **批次**: P-018 · T1
> **上游**: [DESIGN_p018_p017_review_fixes.md](DESIGN_p018_p017_review_fixes.md)（D1-D2 / I1-I4 / §4-§5 规格）
> **下游**: [CHECKLIST_p018_p017_review_fixes.md](CHECKLIST_p018_p017_review_fixes.md)
> **状态**: Step 5 完稿 + Step 6 Review 通过（§5）；Step 9 实施记录见 §6

---

## 1. 任务分解（T-1 ~ T-3）

### T-1 守卫判定（D1 / F-R5-P017-1）

文件：`scripts/external_benchmark/verify_p015.py`

| 行 | 改动 | 行数影响 |
|----|------|----------|
| `:261` docstring 分支 2 | 「（stem 以 `.generated` 结尾）」→「（**name 或 stem** 以 `.generated` 结尾——无扩展名时 stem 会剥离后缀）」 | 1:1，零位移 |
| `:268` 守卫 | `if path.stem.endswith(GENERATED_SUFFIX):` → `if path.name.endswith(GENERATED_SUFFIX) or path.stem.endswith(GENERATED_SUFFIX):` | 1:1，零位移 |

> 零位移是本批的显式约束：P-017 的 CHECKLIST C-1 以 `:254/:268/:272` 行号锚定，位移会连带产生文档不一致。

### T-2 归因更正（D2 / F-R5-P017-2）

| 文件 | 位置 | 改动 |
|------|------|------|
| `docs/IMPL_p017_p016_review_fixes.md` | §6.2 L119 注 | 原句保留 + 追加 P-018 更正注（写明 A①/C/D 实际走分支 3/3/4） |
| `docs/CHECKLIST_p017_p016_review_fixes.md` | C-4 实测列 | 原证据保留 + 追加「分支 1 由 P-018 探针 ⑤ 直接覆盖」 |

### T-3 批次登记

| 文件 | 改动 |
|------|------|
| `docs/PROGRESS.md` §3.20 | P-018 执行记录 |
| `CHANGELOG.md` Fixed | P-018 条目 |

---

## 2. 验证项（V1-V5）

| # | 验证项 | 判据 |
|----|--------|------|
| V1 | 无扩展名不级联（I2） | `X.generated` 连跑两次 → 无 `X.generated.generated`；第二次原地更新 |
| V2 | 四分支不回归（I1） | 普通 `.md` 的分支 1/2/3/4 行为与 P-017 一致（含分支 3 SHA 不变） |
| V3 | 分支 1 真实覆盖（I1/D2） | 目标不存在 → 原地新建；`FRESH_EXISTS=True` |
| V4 | 全链不变（I3） | `28 断言（失败 0）+ 豁免 1`，exit 0 |
| V5 | 纪律面 | `pytest` 635 passed（`MPLBACKEND=Agg`）/ black 5 unchanged / 无 tests/、.github/ 变更 |

---

## 3. 风险与回退

| 风险 | 预案 |
|------|------|
| 守卫放宽后误伤普通文件名（如 `a.generated.bak`） | 判定只要求 name 或 stem 以 `.generated` 结尾；`a.generated.bak` 的 stem 为 `a.generated` ⇒ 命中，属命名契约内（`.generated` 域归生成器） |
| 行号位移破坏 P-017 文档锚点 | 显式约束 1:1 替换；Step 9 复核 `:254/:268/:272` 仍指向同一语义 |
| 归因更正被误读为「P-017 结论作废」 | 注中明确「行为本身正确，仅取证归因需更正」 |

---

## 4. 排除的低效操作

- 不为守卫抽独立函数（G-D 已否决，行号位移代价高于收益）
- 不新增 pytest（P7 纪律：校准工具不进 `tests/`），回归由 CLI 探针承担
- 不改 `_spec.py` / `export_case.py` / `run_vectorbt.py`

---

## 5. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本：无新增依赖
- [x] stdlib API 下限：`pathlib.Path.name/stem/endswith`，3.12 可用
- [x] API 签名可实现：`_resolve_report_target` 仅条件表达式变化，签名与调用方不变
- [x] 兼容性：正常 `.md` 路径判定结果与 P-017 完全一致（命中矩阵 §4 已逐行推导）
- [x] 低效操作已排除（§4）
- [x] 回退点：单文件 `git checkout`；文档改动逐文件可退

**Step 6 Review 结论：通过**。

---

## 6. Step 9 实施记录（2026-11-10 回填）

### 6.1 F5 红→绿（F-R5-P017-1）

| 组 | 红（改前 @`97b71b2`） | 绿（改后 @本批） |
|----|----------------------|------------------|
| **A（无扩展名级联）** | `<tmp>\rep.generated` 连跑两次 → 产物 `rep.generated`（1820B）+ `rep.generated.generated`（1820B）⇒ 级联 | 同命令 → `noext_exists=True cascade=False -> PASS`；第二次原地更新 |

### 6.2 探针读数（8 项全 PASS）

| 探针 | 场景 | 读数 |
|------|------|------|
| ① 全链复放（I3） | 五 case → 策展版主文件 | `28 断言（失败 0）+ 豁免 1`，exit 0；生成物单份（`no_double=True`） |
| ② 无扩展名 ×2（I2） | `rep.generated` 两次 | `cascade=False`，原地更新 |
| ③ `X.generated.md`（P-017 不回归） | 指向生成物复放 | 原地写入、无 `[保护]`、无二次级联 |
| ④ 分支 3（I1） | 策展版副本 | 改名 `.generated.md` + `SHA` 不变 |
| ⑤ 分支 4（I1） | 存在无标记 | 原地覆盖（内容替换为模板） |
| ⑥ **分支 1（F-R5-P017-2 补覆盖）** | 目标不存在（含不存在的父目录） | `FRESH_EXISTS=True`，内容含「恒等式逐条读数」 |
| ⑦ 行号锚点 | `:254/:268/:272` 语义 | PASS（零位移，P-017 C-1 引用仍有效） |

### 6.3 终态读数

| 项 | 读数 |
|----|------|
| 全链断言（I3） | `共 28 项断言（失败 0 项）+ 豁免登记 1 项`，exit 0 |
| `black --check scripts/external_benchmark/` | `5 files would be left unchanged` |
| `pytest tests` | **635 passed, 152 warnings in 64.62s**（`MPLBACKEND=Agg`） |
| 变更面 | `scripts/external_benchmark/verify_p015.py`（2 行 1:1）+ docs；无 tests/、.github/ |
| 取证产物 | 已清理，`git status` 仅含本批预期改动 |
