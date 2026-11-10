# IMPL：P-017 P-016 复审 E4 四项 P3 修正

> **批次**: P-017 · T1
> **上游**: [DESIGN_p017_p016_review_fixes.md](DESIGN_p017_p016_review_fixes.md)（D1-D4 / I1-I5 / §4-§6 规格）
> **下游**: [CHECKLIST_p017_p016_review_fixes.md](CHECKLIST_p017_p016_review_fixes.md)
> **状态**: Step 5 完稿 + Step 6 Review 通过（§5）；Step 9 实施记录见 §6

---

## 1. 任务分解（T-1 ~ T-5）

### T-1 PROGRESS 口径注（D1 / F-R5-P016-1）

文件：`docs/PROGRESS.md` §3.17.1 终态行（L517）

| 改动点 | 内容 |
|--------|------|
| 原句 | 逐字保留「29 项断言 0 失败（I1 全零 / I2c 2.0e-10 / …）」 |
| 追加 | 「（**P-017 口径更正**：原计数含 B5 恒真豁免行 1 项；P-016 D1 后口径 = **28 项断言 + 1 项豁免登记**，见 CHECKLIST §9.4）」 |

### T-2 IMPL_p015 §8.5 回填（D2 / F-R5-P016-2）

文件：`docs/IMPL_p015_external_benchmark.md` L140-142

占位句 `（E-2 门禁读数回填区——black / pytest / 主环境 pip list）` → DESIGN §5 的三行读数表 + 「T-4 原始读数未保全」说明。

### T-3 生成物命名空间守卫（D3 / F-R5-P016-3）

文件：`scripts/external_benchmark/verify_p015.py`

| 改动点 | 内容 |
|--------|------|
| 新增常量 | `GENERATED_SUFFIX = ".generated"`（置于 `MANUAL_MARKERS` 旁） |
| `_resolve_report_target` | 在 `not path.exists()` 之后插入 `if path.stem.endswith(GENERATED_SUFFIX): return path` |
| 改名表达式 | `f"{path.stem}.generated{path.suffix}"` → `f"{path.stem}{GENERATED_SUFFIX}{path.suffix}"`（单一来源） |
| docstring | 补四分支说明 + 命名契约（`.generated.*` 归生成器所有） |

### T-4 验收清单更正（D4 / F-R5-P016-4）

文件：`docs/CHECKLIST_p016_p015_review_fixes.md`

| 行 | 改动 |
|----|------|
| E-1 实测列 | 「docs/（6 文件）」→「`4a1cdb4` = scripts 2 + docs 9 + CHANGELOG 1（12 文件）」+ P-017 更正注 |
| B-3 实测列 | 补「分支 1（不存在）覆盖；分支 4（存在且无标记）由 P-017 探针 D 覆盖」 |

### T-5 批次登记

| 文件 | 改动 |
|------|------|
| `docs/PROGRESS.md` §3.19 | P-017 执行记录（立项 → Step 1-10 + 终态读数） |
| `CHANGELOG.md` Fixed | P-017 条目（四项 P3 + 级联守卫） |

---

## 2. 验证项（V1-V6）

| # | 验证项 | 判据 |
|----|--------|------|
| V1 | 级联消除（I2 分支 2） | 以 `.generated.md` 为目标复放 → 写入该文件本身；`*.generated.generated.md` **不存在** |
| V2 | 全链结论不变（I1） | `28 断言（失败 0）+ 豁免 1`，exit 0 |
| V3 | 保护三路径（I2） | 策展版副本 → 改名且 SHA256 不变；不存在路径 → 原地；生成物 → 原地 |
| V4 | 占位扫描（I3） | `docs/` 无真实占位残留（IMPL_p015 §8.5 已回填） |
| V5 | 门禁面 | `pytest tests` 仍 635 passed；`black --check scripts/external_benchmark/` 0 变更；主环境零 vectorbt |
| V6 | 文档一致（I4/I5） | PROGRESS 原句逐字保留 + 注；CHECKLIST_p016 两行含 P-017 标记 |

---

## 3. 风险与回退

| 风险 | 预案 |
|------|------|
| `.generated` 守卫误伤人工策展的 `.generated.md` | DESIGN §4 显式声明命名契约；人工策展须合并回主文件；风险面 = 违反命名契约的使用 |
| 文档改动的行号漂移影响其他文档引用 | 只追加不改行数结构（T-1 同行追加、T-2 同节替换、T-4 同行替换），无跨文档行号引用 |
| 占位扫描误报（RULE-1 合法占位） | 扫描判据区分 `[待 Step 9]` 声明行与真实「回填区」占位 |

---

## 4. 排除的低效操作

- 不为 `_resolve_report_target` 新增 pytest（P7 纪律：校准工具不进 `tests/`）；回归由 CLI 探针承担
- 不重构 `MANUAL_MARKERS` 判据（G-B 已否决，重建议面为零）
- 不改任何恒等式算式与 case 数据（`_spec.py` 零改动）

---

## 5. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本：无新增依赖；vectorbt 版本不变
- [x] stdlib API 下限：仅用 `pathlib.Path` / `str.endswith`，3.12 可用
- [x] API 签名可实现：`_resolve_report_target` 仅内部分支增加，调用方 `write_report` 零改动
- [x] 兼容性：`GENERATED_SUFFIX` 为模块级新增常量，无外部消费者；四分支覆盖不变
- [x] 低效操作已排除（§4）
- [x] 回退点：单文件 `git checkout`（`verify_p015.py`）；文档改动可逐文件回退

**Step 6 Review 结论：通过**。

---

## 6. Step 9 实施记录（2026-11-10 回填）

### 6.1 F5 红→绿（代码改动一组，F-R5-P016-3）

| 组 | 红（改前 @`4a34c49`） | 绿（改后 @本批） |
|----|----------------------|------------------|
| **A（生成物级联）** | `--report …generated.md` → `报告已写入 …generated.generated.md`；产物三文件并存（7767 / 3913 / 3913 B） | 同命令 → `报告已写入 …generated.md`（无 `[保护]` 行）；`CASCADE_EXISTS=False`；`A_EXIT=0,0 -> PASS` |

### 6.2 保护四分支覆盖（探针 @`%TEMP%`，`[未入仓-本批复放]`）

| 探针 | 分支 | 实测读数 |
|------|------|----------|
| A① | 分支 3（策展版 → 改名） | `[保护] APPENDIX_p015_external_calibration.md 含人工章节（§1/§3），改写 …generated.md` |
| A② | 分支 2（生成物 → 原地重写） | `报告已写入 …generated.md`；`*.generated.generated.md` 不存在 |
| C | 分支 3 + 原文件零改动 | `ORIG_UNCHANGED=True`；`APPENDIX_copy.generated.md` 存在；`C_EXIT=0 -> PASS` |
| D | 分支 4（存在且无人工标记 → 原地覆盖） | `OVERWRITTEN=True`；覆盖后内容含「恒等式逐条读数」；`D_EXIT=0 -> PASS` |

> 分支 1（目标不存在 → 原地）由 A① 产生成物时的首次写入与探针 C/D 的新建路径覆盖。
>
> **P-018 更正（F-R5-P017-2）**：上句归因有误——A① 的传入目标是**已存在的策展版主文件**（走分支 3，其解析结果 `.generated.md` 事先并不存在，但被判定的是传入路径而非解析路径）；探针 C 的副本由 `shutil.copyfile` 预置、探针 D 的目标预先 `write_text`，运行前均已存在（分支 3/4）⇒ **分支 1 未被该三探针覆盖**。行为本身正确，缺陷仅在取证归因；真实覆盖见 [P-018 IMPL §6.2](IMPL_p018_p017_review_fixes.md) 探针 ⑥（`FRESH_EXISTS=True`）。

### 6.3 终态读数

| 项 | 读数 |
|----|------|
| 全链断言（I1） | `共 28 项断言（失败 0 项）+ 豁免登记 1 项`（探针 A×2 / C / D 各复放一次） |
| `black --check scripts/external_benchmark/` | `5 files would be left unchanged` |
| `pytest tests` | **635 passed, 152 warnings in 47.26s** |
| 项目解释器 pip list | pandas 2.2.3 / numba 0.65.1；**无 vectorbt** |
| 占位扫描（I3） | `回填区` 命中 **11 行，全部为历史记录引用 / DoD 措辞 / 本批说明**；真实占位残留 **0**（IMPL_p015 §8.5 已回填） |
| 生成物清理 | 取证产物 `.generated.md` 已删除，`git status` 仅含本批预期改动 |

> **环境取证说明**：本终端 `python` 默认解析到 `C:\ProgramData\Anaconda3\python.exe`（3.13.5，其自带 vectorbt 0.28.4）。为与本仓基线一致，全部读数改用项目解释器绝对路径 `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10）复跑；上表读数为项目解释器结果。此现象为环境态，不属本批缺陷。
