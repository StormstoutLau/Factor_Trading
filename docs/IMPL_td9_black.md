# TD-9（P-003） · black 全量重排 · 实施规划

> **文档编号**: IMPL_td9_black
> **阶段**: Phase 1 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: 完稿；Step 6 Review **通过**（2026-11-09；1 项 P2 已拦截修正 + 2 项 P3 已回写，见 §9）
> **上游**: [DESIGN_td9_black.md](DESIGN_td9_black.md)（Step 4 Review 通过，D1-D7 / V1-**V12**）
> **下游**: [CHECKLIST_td9_black.md](CHECKLIST_td9_black.md)
> **证据时点**: 本仓读数 @ `080f3a3`；解释器 Python 3.12.10
> **档位**: T1（批量 style-only）

---

## 1. 执行总览

### 1.1 任务分解

| ID | 任务 | 依赖 | 产出 | 验证 |
|----|------|------|------|------|
| T-0 | 记录 RED 基线（5 项负向断言 + 门禁读数） | — | §2 表 | 5 项 RED 全部「符合预期未达成」 |
| T-1 | 锁定 black 版本（D2） | T-0 | `pyproject.toml` L64 一行 | 读回 `black~=26.0` |
| T-2 | 全量 black 重排（D1/D6） | T-1 | 126 文件 | `black --check .` exit 0 |
| T-3 | 门禁命令扩展（D3） | T-2 | `spec_runner_adapter.py` L66 | `git diff` 仅该行 |
| T-4 | 全量验证 V1-V11 | T-1~T-3 | 读数 | §4 全绿 |
| T-5 | 四文档 + 台账落档 | T-4 | 5 文件 | 读回 |
| T-6 | 提交 1（重排 + 语义改动 + 文档） | T-5 | 单次 commit | `git show --stat` |
| T-7 | 生成 `.git-blame-ignore-revs`（D4） | T-6 | 新文件含提交 1 hash | 读回 40 位 hash |
| T-8 | 提交 2（blame 元数据） | T-7 | 第二次 commit | `git show --stat` = 1 文件 |
| T-9 | 推送 + 远端 CI + Step 10 审计 | T-8 | run id / 审计表 | 三 job 全绿 |

### 1.2 执行顺序与依赖图

```
T-0 记录 RED
  │
  ▼
T-1 锁定版本 ──► T-2 全量重排 ──► T-3 门禁扩展 ──► T-4 全量验证
                                                      │
                                                      ▼
                                              T-5 文档+台账
                                                      │
                                                      ▼
                                              T-6 提交 1（含 126 文件 + pyproject + adapter + 文档）
                                                      │
                                                      ▼
                                              T-7 .git-blame-ignore-revs（写入 T-6 hash）
                                                      │
                                                      ▼
                                              T-8 提交 2 ──► T-9 推送 + CI + 审计
```

> **关键约束**：T-7 必须在 T-6 之后（需要提交 1 的 hash）；这就是 D4 两笔提交的物理原因。

### 1.3 关键原则

| 原则 | 说明 |
|------|------|
| 纯格式 + 两处语义改动分离可辨 | 126 文件为机械重排；`pyproject.toml` L64 与 `adapter.py` L66 为**语义改动**，须在 commit message 与审计中单独声明（DESIGN F-D2） |
| 不跑 isort | `isort` 会改 import 顺序（语义面），且不在门禁/CI；本批**绝对不执行** |
| 不用 `--preview` / `--unstable` | S1 明文：二者不受稳定性政策约束，会使格式锁失效 |
| 不改 `[tool.black]` 参数 | 调参会改变重排结果，扩大不确定面（DESIGN §8） |
| 精确 `git add` | 逐文件/逐路径，禁止 `git add -A`（防带入 `.venv` 或临时产物） |

---

## 2. T-0 前置：RED 基线记录

> **F5 先失败记录**：本批「先失败」= 格式不合规在当前树成立。以下 5 项必须在 T-1 之前记录。

| ID | 断言 | 命令 | RED 读数（当前） | GREEN 目标 |
|----|------|------|------------------|------------|
| RED-1 | 全仓格式应合规 | `black --check .` | `126 files would be reformatted, 9 files would be left unchanged`（exit 1） | exit 0，`135 files would be left unchanged` |
| RED-2 | 门禁 `black-check` 应 pass | `adapter gate black-check` | **verdict=fail** | **verdict=pass** |
| RED-3 | black 版本应锁定 | 读 pyproject L64 | `"black>=23.0.0"` | `"black~=26.0"` |
| RED-4 | blame 忽略文件应存在 | `Test-Path .git-blame-ignore-revs` | `False` | `True`（含 40 位 hash） |
| RED-5 | 门禁范围应覆盖全仓 | 读 adapter L66 | `black --check core tests 2>&1` | `black --check . 2>&1` |

**对照基线（T-4 复核，不得劣化）**：

| 项 | 基线读数 @ `080f3a3` | T-4 期望 |
|----|----------------------|----------|
| 全量测试 | `507 passed, 82 warnings` | `507 passed`（逐字一致） |
| mypy | `119 errors in 19 files` | `119 errors in 19 files`（不得增加） |
| 测试文件数 | 48 | 48 |
| 收集数 | 507 | 507 |
| `.github/` diff | 空 | 空 |

---

## 3. 逐任务实施文本

### T-1 锁定 black 版本（D2）

**位置**: [pyproject.toml](../pyproject.toml) **L64**（`[project.optional-dependencies] dev` 块内）

```toml
# 旧
    "black>=23.0.0",
# 新
    "black~=26.0",
```

| 项 | 内容 |
|----|------|
| 依据 | S1 Stability Policy：「projects can safely use `black ~=26.0`」 |
| 影响 | `pip install ".[dev]"` 解析到 26.x 最新版；CI 会装但不用（D5） |
| 回退 | 还原该行 |

### T-2 全量 black 重排（D1 / D6）

```powershell
# 在仓库根执行，依赖 pyproject [tool.black] 配置（line-length=100，三 target）
& $PY312 -m black .
```

| 项 | 内容 |
|----|------|
| 期望读数 | `126 files reformatted, 9 files left unchanged` |
| 范围依据 | D6：`black .` 与 14 路径枚举实测等价（126/9 逐字相同）；默认 exclude 已跳过 `.venv`（1174 文件）与 `.git` |
| 禁止 | `--preview` / `--unstable` / 修改 `--line-length` / 同时跑 `isort` |
| 中间态 | 重排后 `tests/test_execution_policy.py:282` 的 `# type: ignore` 须仍在原表达式同行（V5 复核） |
| 回退 | `git checkout -- .`（工作区干净前提下） |

### T-3 门禁命令扩展（D3）

**位置**: [scripts/spec_runner_adapter.py](../scripts/spec_runner_adapter.py) **L66**

```python
# 旧
    "black-check": f"{_PY312} -m black --check core tests 2>&1",
# 新
    "black-check": f"{_PY312} -m black --check . 2>&1",
```

| 项 | 内容 |
|----|------|
| 依据 | `black --check .` 与 14 路径枚举实测等价；自动覆盖未来新增目录 |
| 注意 | 该行是 **GATES 配置区**，属模板允许的「按项目修改」范围（模板 §配置区） |
| 副作用 | 该文件本身也在 126 个重排文件中——T-2 已重排它，T-3 在其之上改字符串 |
| 回退 | 还原该行 |

### T-4 全量验证（V1-V11）

| 验证 | 命令 | 期望 |
|------|------|------|
| V1 | `black .`（重跑） | `135 files left unchanged`（幂等） |
| V2 | `MPLBACKEND=Agg pytest tests -q` | `507 passed` |
| V3 | `black --check .` | exit 0 |
| V4 | `adapter gate black-check --session <sid>` | **verdict=pass** |
| V5 | `mypy --explicit-package-bases core` | `119 errors in 19 files` |
| V6 | `git diff --numstat` + 抽样读码 | 无语义改动 |
| **V12** | **AST 等价性**（机械验证语义零变更） | 对 **125 文件**（排除 `scripts/spec_runner_adapter.py`）比较 `ast.dump(ast.parse(...))`，比较前对**所有 docstring 逐行 `rstrip` 归一化** | **全部逐字相等**（实测方法已验：朴素比较 False → 归一化后 True） |
| V7 | 读回 pyproject L64 | `black~=26.0` |
| V8 | 提交 2 后 `git blame --ignore-revs-file ...` | 跳过重排提交 |
| V9 | `pytest --collect-only -q` | 507 |
| V10 | `git diff --stat -- .github/` | 空 |
| V11 | `git diff --stat -- core/engine_v2.py core/factory.py` + 读回 `[tool.black]`/`[tool.isort]` | 空 / 逐字不变 |

### T-5 文档 + 台账落档

| 文件 | 动作 |
|------|------|
| `docs/RESEARCH_td9_black.md`、`docs/DESIGN_td9_black.md`、`docs/IMPL_td9_black.md`、`docs/CHECKLIST_td9_black.md` | 四文档（本批产出） |
| `docs/PROGRESS.md` | P-003 → done；新增 §3.8 批次记录；§1.4 表更新 |
| `docs/RESEARCH_tech_debt_cleanup.md` | §TD-9 追加执行注记（不改历史结论） |
| `CHANGELOG.md` | `[Unreleased] > Changed` 追加 1 条（style-only） |

### T-6 提交 1

```powershell
# 逐路径精确暂存（禁止 git add -A / git add .）
git add pyproject.toml scripts/spec_runner_adapter.py
git add <126 个 py 文件：按 14 路径逐目录 add>
git add docs/RESEARCH_td9_black.md docs/DESIGN_td9_black.md docs/IMPL_td9_black.md docs/CHECKLIST_td9_black.md
git add docs/PROGRESS.md docs/RESEARCH_tech_debt_cleanup.md CHANGELOG.md
git commit -m "style(TD-9): black 全量重排 126 文件并锁定 black~=26.0（P-003）"
```

**commit message 须显式声明两处语义改动**：`pyproject.toml` 版本锁定（D2）、`adapter.py` 门禁范围扩展（D3）。正文补充 V12 AST 等价性结果。

### T-7 生成 `.git-blame-ignore-revs`（D4）

```powershell
$h = git rev-parse HEAD   # 提交 1 的完整 40 位 hash
```

文件内容（格式同 `fsck.skipList`）：

```
# 格式提交（black 全量重排），git blame 时忽略
# 启用：git config blame.ignoreRevsFile .git-blame-ignore-revs
<提交 1 的 40 位 hash>
```

### T-8 提交 2

```powershell
git add .git-blame-ignore-revs
git commit -m "chore(TD-9): 记录格式提交至 .git-blame-ignore-revs（P-003）"
```

| 校验 | 期望 |
|------|------|
| `git show --stat HEAD` | **仅 1 文件**（`.git-blame-ignore-revs`） |
| `git cat-file -p HEAD` | 存在完整 hash 行 |

### T-9 推送 + 远端 CI + Step 10 审计

```powershell
git push origin master
gh run list --branch master --limit 1 --json databaseId,headSha
gh run watch <id> --exit-status --interval 20
```

期望：三 job（3.10/3.11/3.12）success；每版 `500 passed, 1 skipped`（507 − 7 numba，与 P-001 同一口径）。

---

## 4. 低效/危险操作排除表

| 禁止操作 | 原因 |
|----------|------|
| `black --preview` / `--unstable` | S1：不受稳定性政策约束，重排结果不可复现、格式锁失效 |
| `isort .` | 改 import 顺序 = 语义变更；isort 不在门禁/CI，超出 TD-9 范围 |
| 修改 `[tool.black]` 的 `line-length` / `target-version` | 会改变重排结果，扩大不确定面 |
| `black .` 外加自定义 `--exclude` | 默认 exclude 已够（实测 135 而非 1300+）；加配置属无必要复杂度 |
| `git add -A` / `git add .` | 可能带入 `.venv` 或临时产物；且违反「精确暂存」 |
| 在重排提交中混入 P-007 的 mypy 修复 | 违反 TD-9 独立窗口要求（R-7） |
| 先用 `git commit --amend` 造 blame 文件 | hash 会再次变化，鸡生蛋问题无解；必须两笔提交 |
| 手工编辑 126 个文件 | black 的机械输出不可手写复现，易引入语义差错 |
| 跳过 T-4 直接提交 | 预演虽已证 507 passed，但提交前必须在本树复核（RULE-1 独立取证） |

---

## 5. 红 → 绿执行序（F5）

| 序 | 动作 | 预期状态 |
|----|------|----------|
| 1 | T-0 记录 RED | black-check fail(126)、507 passed、mypy 119 |
| 2 | T-1 锁定版本 | pyproject 变更，测试不受影响（507 passed 仍成立） |
| 3 | T-2 全量重排 | 126 files reformatted |
| 4 | 重排后立即跑 pytest | **507 passed**（GREEN，零回归） |
| 5 | T-3 门禁扩展 | adapter L66 变更 |
| 6 | T-4 验证 V1-V11 | 全绿；black-check **pass** |
| 7 | T-5/T-6 文档 + 提交 1 | commit 1 落地 |
| 8 | T-7/T-8 blame 元数据 + 提交 2 | commit 2 落地，仅 1 文件 |
| 9 | T-9 推送 + CI | 三 job 全绿 |

---

## 6. 回退点

| 断点 | 操作 |
|------|------|
| T-2 后发现问题 | `git checkout -- .` 全部还原（工作区其余改动需先自行保存） |
| 提交 1 后发现问题 | `git revert <commit1>`——因提交 2 只加文件，不影响回退 |
| 提交 2 后发现问题 | `git revert <commit2>`（仅删 blame 文件） |
| 推送后发现严重问题 | 两笔连续 `git revert`，再推送 |

---

## 7. 保护路径

| 路径 | 约束 |
|------|------|
| `.github/workflows/tests.yml` | **零改动**（V10） |
| `[tool.black]` / `[tool.isort]` | **零改动**（V11） |
| `core/engine_v2.py`、`core/factory.py` 等生产逻辑 | 仅格式，零语义（V2 / V6） |
| 测试数与文件数（507 / 48） | 不变（V2 / V9） |

---

## 8. 会话与门禁

- **Spec_Runner session**: `factorv3-p003-td9-black-20261109`
- **门禁预期**：probe pass / unit-tests pass(507) / **black-check pass**（本批目标，区别于历史 fail）/ mypy-check fail(119)（存量，非本批）
- **replay 期望**: 4 rows OK

---

## 9. Step 6 Review（独立 pass）

- **执行时点**: 正文完稿后单独执行，未与正文同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 核对 T-0~T-9 与 DESIGN D1-D7/V1-V12 覆盖 + 逐任务判据机械可检性核查 + 排除表覆盖已知风险 + 红→绿序逻辑断点检查 + **V12 方法可行性实测**

**发现 3 项（1 项 P2 实质缺陷 + 2 项 P3，均已修复）**：

| ID | 级别 | 发现 | 处理 |
|----|------|------|------|
| **F-I1** | **P2** | **V12 的「朴素 AST 等价」前提不成立**：实测 `core/factory.py` 重排后 `ast.dump` 比较为 **False**。根因：black 清理 docstring 行尾空白（`"组件工厂\n    \n    集中..."` → `"组件工厂\n\n    集中..."`），改变 `Constant.value`。若按初稿定义执行，V12 必然失败，且会被误判为「出现了语义变更」 | ① V12 改为 **docstring 逐行 `rstrip` 归一化后比较**（实测归一化后 **True**）；② 范围排除 `spec_runner_adapter.py`（GATES 字符串为有意语义改动，AST 必变）；③ 同步 DESIGN 新增 **R8** 与 **F-D4** |
| **F-I2** | P3 | T-6 暂存命令写 `git add docs/`，范围过宽，可能带入非本批 docs 改动 | 改为**逐文件精确列出**（四文档 + PROGRESS + RESEARCH_tech_debt_cleanup + CHANGELOG） |
| **F-I3** | P3 | 初稿未声明 commit message 需显式区分两处语义改动 | T-6 已补「须显式声明 pyproject 版本锁定与 adapter 门禁扩展」 |

**T ↔ D/V 覆盖核对**：

| 任务 | 覆盖决策 | 对应验证 |
|------|----------|----------|
| T-0 | 全部（RED 基线） | RED-1~RED-5 |
| T-1 | D2 | V7 |
| T-2 | D1 / D6 | V1 / V2 / V3 / V12 |
| T-3 | D3 | V4 |
| T-4 | V1-V12 | 全 |
| T-5 | 文档一致性 | 读回 |
| T-6 | D7 | V6 / V12 |
| T-7 / T-8 | D4 | V8 |
| T-9 | D5（不改 CI） | V10 |

**判据可检性核查**：T-0~T-9 每步均给出可机械执行命令与期望字符串/exit code，无「人工判断」项；RED/GREEN 与基线读数逐字绑定。

**排除表覆盖度**：已覆盖 `--preview`/`--unstable`、isort、`[tool.black]` 参数、自定义 exclude、`git add -A`、混批 P-007、amend 造 blame、手工编辑、跳过验证共 9 类；与 DESIGN R1-R8 无冲突。

**红→绿序断点检查**：T-2 重排后立即跑 pytest（第 4 步）——避免在未验证零回归时继续叠加改动；T-7 严格在 T-6 之后（hash 依赖）成立。

**结论**: **1 项 P2（F-I1）已在规划阶段拦截并修正**，2 项 P3 已回写；无遗留阻断，可进入 Step 7 验收清单。
