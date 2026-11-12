# RESEARCH：P-024 CI 门禁对齐（mypy 假门禁 + README uv extras）

> **批次**: P-024 · **T1**（`.github/workflows/` Layer-1 + 门禁口径收紧，判档规则 1 + 规则 2「门禁/真值源」强制升级）
> **上游**: [PROGRESS §2](PROGRESS.md) **U-006**（`mypy-check` 口径收紧，Q4=B 挂起待重评）；[RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md) **U-P023-2**（`--check-untyped-defs` 是否入门禁）与 **U-P023-4**（v3 信号路径取证）；[PROGRESS §1.4](PROGRESS.md) P-021 锁纪律
> **下游**: [DESIGN_p024_ci_gate_alignment.md](DESIGN_p024_ci_gate_alignment.md) → [IMPL_p024_ci_gate_alignment.md](IMPL_p024_ci_gate_alignment.md) → [CHECKLIST_p024_ci_gate_alignment.md](CHECKLIST_p024_ci_gate_alignment.md)
> **代码证据时点**: HEAD `6ed74d0`（2026-11-12，`git status --short` 空输出）
> **状态**: Step 1 调研完稿

---

## 1. 背景与目标

**立项链条**：P-007 层 B 收口时用户裁决 **Q4=B**——`mypy-check` 门禁虽机械转绿，但「收紧 `mypy-check` 命令口径（如 `--check-untyped-defs`）」留待下一批次评估，故 **U-006 不关闭**（[PROGRESS §2 L119](PROGRESS.md)）。P-023 已把该口径下的残差从 4 errors 清零到 0，并把「是否纳入门禁」登记为 **U-P023-2**（当前倾向「不纳入」）。本批由用户裁决承接：**去 `|| true`、对齐本地 mypy 口径、README 补 extras**，同时关闭 U-P023-2 与 U-006。

- **F1（假门禁，P1）**：CI 的 mypy 步骤为 `mypy core/ --ignore-missing-imports --no-error-summary || true`（[tests.yml](../.github/workflows/tests.yml) L45-L46）。`|| true` 使该步骤**退出码恒为 0**，无论 mypy 报多少错误——CI badge 绿不能证明类型检查通过。E2 探针实测：同一失败命令加 `|| true` 后内部读数由 `exit=2` 变 `exit=0`（§5 读数 C/D）。
- **F2（双口径，P2）**：本地真实门禁是 `mypy --explicit-package-bases core`（[spec_runner_adapter.py](../scripts/spec_runner_adapter.py) L67），CI 口径与之**无一处相同**（缺 `--explicit-package-bases`、多两个冗余旗标、且被 `|| true` 抹平）。更关键的是 CI 的那串参数在本地**根本跑不起来**：exit 2（§5 读数 C）。
- **F3（README 与锁纪律矛盾，P3）**：README `### uv` 段只有 `uv sync`（[README.md](../README.md) L217-L221），而 [ARCHITECTURE.md](ARCHITECTURE.md) L332 明写「`uv sync` 默认不同步 extras，需 `--extra web` 或 `--all-extras`」；照 README 执行得到的环境**缺 pytest/mypy/black**，紧接着的 Quick Start 第 5 步 `python cli.py test` 必然失败。
- **F4（台账缺口，P3）**：P-023 在 §3.27 与 RESEARCH §6 宣布新增 U-P023-1~4，但 §1.4 [PROGRESS.md](PROGRESS.md) L66-L82 表格**没有任何一行**对应这四个 ID（只有 §2 之外的文字提及）——违反「未决项单来源」纪律。

**目标**：① CI mypy 步骤恢复为**真实阻塞**；② CI 与本地门禁**同一命令形状**（消除双口径）；③ 门禁纳入 `--check-untyped-defs`（U-006/U-P023-2 判据达成）；④ README uv 段与锁纪律一致；⑤ 台账补登 U-P023-1~4 并关闭 U-006 / U-P023-2 / U-P023-4。

**出界（不回答）**：`mypy` 版本钉上限（U-P024-2）；CI 增加 `uv lock --check`（U-P021-1）；把 mypy 检查面从 `core` 扩到 `cli.py`/`agents`/`web`/`scripts`；`--check-untyped-defs` 扩展后新出现的**新增代码**治理（本批只对齐口径，不新增类型修复需求）。

---

## 2. 本仓事实（P1-P13）

| # | 事实 | 证据 |
|---|------|------|
| **P1** | **CI mypy 步骤原文**（L45-L46）：`- name: Type check (mypy)` / `run: mypy core/ --ignore-missing-imports --no-error-summary \|\| true`；同 job 其余步骤（pytest / fixture）无 `\|\| true`，故只有类型检查这一步是不可失败的 | E3 [tests.yml](../.github/workflows/tests.yml) L45-L46 @`6ed74d0` |
| **P2** | **`\|\| true` 自初版即存在**，非某次改造引入：该文件全历史仅 3 次提交（`c7a0f29` 2026-06-07 初版 / `06e9e11` P-008 / `33872c3` P-009），`git show c7a0f29:.github/workflows/tests.yml` 已含同文本 | E1 `git log -- .github/workflows/tests.yml` + `git show c7a0f29:...` |
| **P3** | **本地门禁原文**：`GATES["mypy-check"] = f"{_PY312} -m mypy --explicit-package-bases core"`；`verdict` 为命令 exit code 的机械映射 → 本地**真实阻塞** | E3 [spec_runner_adapter.py](../scripts/spec_runner_adapter.py) L61 / L67 |
| **P4** | **双口径不可互换（关键）**：CI 参数 `mypy core/ --ignore-missing-imports --no-error-summary` 在本地执行 → **exit 2**，输出 `Factor_Trading_v3.0 contains __init__.py but is not a valid Python package name`；本地参数 `--explicit-package-bases core` → 0 errors / 36 files。根因：本地目录名含点号属非法包标识符，CI checkout 目录名为 `Factor_Trading`（合法）故不触发 | E1 四组命令（§5 读数 B/C） |
| **P5** | **`--ignore-missing-imports` 在 CI 冗余**：`[tool.mypy]` 已全局设 `ignore_missing_imports = true`（[pyproject.toml](../pyproject.toml) L105-L110），且 mypy 自动发现 `pyproject.toml` 的 `[tool.mypy]`（外部锚点 E2）；该选项「may only be set in the global section」→ CLI 再加一次不改变行为 | E3 pyproject L105-L110 + 外部 E2 |
| **P6** | **`--check-untyped-defs` 当前残差为 0**：`mypy --explicit-package-bases --check-untyped-defs core` → `Success: no issues found in 36 source files`（P-023 已把 4 errors 清零）→ 现在纳入门禁**零成本**，不会引入新红 | E1（§5 读数 D） |
| **P7** | **版本面**：dev extras `mypy>=1.5.0`（pyproject L65）**无上限**；CI 矩阵 `["3.10","3.11","3.12"]`（tests.yml L15-L16），pip 按解释器各自回溯解析 → 三条 leg 可能装到不同 mypy 版本；但 `[tool.mypy] python_version = "3.10"`（pyproject L106）使三腿的**语义目标一致**（差异仅来自 mypy 自身版本） | E3 [tests.yml](../.github/workflows/tests.yml) L15-L16 + [pyproject.toml](../pyproject.toml) L65 / L106 |
| **P8** | **README uv 段与锁纪律冲突**：README L217-L221 只有 `uv sync`；ARCHITECTURE L332「`uv sync` 默认不同步 extras，需 `--extra web` 或 `--all-extras`」；`uv sync --help` 原文 `--extra <EXTRA> Include optional dependencies from the specified extra name` / `--all-extras Include all optional dependencies` | E3 [README.md](../README.md) L217-L221 + ARCHITECTURE L332；E1 `uv sync --help`（uv 0.11.14） |
| **P9** | **extras 真值**：`[project.optional-dependencies]` 含 `web = ["streamlit>=1.28.0"]` 与 `dev = [pytest, pytest-cov, black~=26.0, flake8, mypy, isort]`；P-021 已把 `uv.lock` 的 `provides-extras` 修为 `["dev","web"]` | E3 pyproject L59-L70；E1 `uv lock --check`（P-021 收口已 0） |
| **P10** | **终态基线（本批起点）**：`651 passed`（Agg，3.12.10，42.21s）；`black --check .` → `179 files would be left unchanged`；mypy 门禁口径 0 / 36 files；盲区口径（含 `--check-untyped-defs`）0 / 36 files | E1（§5 读数 A/B/D/F） |
| **P11** | **台账缺口**：§1.4 表格无 U-P023-1~4 独立行（L66 起直接是 U-D1/P-013/…）；§2 U-006 行（L119）仍停在 P-007 层 B 的 Q4=B 注记，未反映 P-023 清零后状态 | E3 [PROGRESS.md](PROGRESS.md) §1.4 L66-L88 / §2 L119 |
| **P12** | **U-P023-4 取证完成（可关闭）**：`EngineV3Vector._precompute_signals()` 在无因子时用收盘价动量填充 `factor = np.zeros_like(close)` 后赋值 `self._signals`（非 `None`）；`run()` L293-L295 有 `dl is None` fail-fast → **不存在**「信号 `None` → 静默空回测」同形缺陷 | E3 [engine_v3_vector.py](../core/engine_v3_vector.py) L265-L295 @`6ed74d0` |
| **P13** | **`\|\| true` 语义实证**：Git bash 下 `sh -c "exit 3"` → 内部 `exit=3`；加 `\|\| true` → `exit=0`；`mypy -p <不存在模块>` → `exit=2`，加 `\|\| true` → `exit=0` | E2 `%TEMP%\p024_gate_probe.py`（§5 读数 G） |

**严重度**：F1 = **P1**（门禁语义反转：CI 绿 → 类型检查必然「通过」，与 P-023 刚建立的盲区零残差形成反差——口径再严也无处生效）；F2 = **P2**（双口径不可互换，任何一方改动都无法被另一方验证）；F3 = **P3**（文档误导，可自愈成本低）；F4 = **P3**（台账完整性）。U-P023-4 由「待取证」转 **已取证可关闭**（P12）。

---

## 3. 外部锚点（F1/F2/F4 + F3 降级链）

### 3.1 降级链（F3）

| 目标 | 结果 | 处置 |
|------|------|------|
| `docs.astral.sh/uv/reference/cli/#uv-sync` | **返回空**（local crawler empty content） | 降级为**本地 E1**：`uv sync --help`（uv 0.11.14）原文命中 `--extra` / `--all-extras` 两条（P8） |
| `docs.github.com/.../workflow-syntax#jobsjob_idstepscontinue-on-error` | 页面**截断于目录区**（27.4 KB 仅到 `jobs.<job_id>.strategy`），`continue-on-error` 正文未到达 | 不作为判据；`|| true` 语义改用**本地 E1 探针**（P13，比文档更强） |
| `docs.python.org/3/library/typing.html#typing.cast` | 同 P-023：截断未含 cast 节 | 沿用 P-023 的 mypy *Type narrowing* 替代（本批未新引 `cast` 判据） |

### 3.2 锚点清单与验证表

| ID | 来源 | 发布/版本 | 读取日 | 验证 | 命中要点 |
|----|------|-----------|--------|------|----------|
| **E1** | mypy docs *The mypy command line* — `--explicit-package-bases` | stable（2026-11 快照） | 2026-11-12 | ✅ 正文 | 「tells mypy that top-level packages will be based in either the current directory, or a member of the MYPYPATH… only useful in the absence of `__init__.py`」→ 解释 P4 的目录名敏感性 |
| **E2** | mypy docs *The mypy configuration file* — `ignore_missing_imports` | stable（2026-11 快照） | 2026-11-12 | ✅ 正文 | 「Suppresses error messages about imports that cannot be resolved.」+ 「This option may only be set in the global section」+ 自动发现 `pyproject.toml` 的 `[tool.mypy]` → 支撑 P5 冗余判定 |
| **E3** | mypy docs *The mypy command line* — `--check-untyped-defs` | stable（2026-11 快照） | 2026-11-12 | ✅ 正文 | 「type checks the body of every function, regardless of whether it has type annotations」→ 本批纳入门禁的定义依据 |
| **E4** | mypy docs *The mypy command line* — `--ignore-missing-imports` | stable（2026-11 快照） | 2026-11-12 | ✅ 正文 | 「makes mypy ignore all missing imports. It is equivalent to adding `# type: ignore` comments to all unresolved imports」 |
| **E5** | PEP 20 *The Zen of Python* | Active（Created 2004-08-19） | 2026-11-12 | ✅ 正文 | 「Errors should never pass silently. / Unless explicitly silenced.」——`|| true` 属**未显式声明**的静默（workflow 里没有任何注释说明这是有意豁免） |

> **F4**：有效外部引用 **5 条**（E1-E5，均命中正文）≥3，已建表。**F1/F2**：每条带版本与读取日。**F5**：Step 1 已取 8 组读数（§5），Step 9 以同命令 + 探针转绿/转红双向回填。

---

## 4. 方案矩阵（7 维）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 数据风险 | 短期 | 长期 |
|------|------|------|------|------|------|----------|------|------|
| **M-A 单源命令 + 真实阻塞（推荐）** | CI 与 adapter 统一为 `python -m mypy --explicit-package-bases --check-untyped-defs core`；CI 去 `\|\| true`、去 `--ignore-missing-imports`（配置已有）、去 `--no-error-summary`（保留汇总行） | 低（2 文件各 1 行 + README 1 行） | 高：门禁语义恢复；双口径合一；U-006/U-P023-2 判据达成 | 低（单一命令形状，改一处即两处同步的**文档化约定**） | 高（代码零改动；`core` 当前 0 errors） | 无 | 1 批 | 口径稳定 |
| M-B 最小改动：仅去 `\|\| true` | 保留 `--ignore-missing-imports --no-error-summary`，不加 `--check-untyped-defs` | 极低 | 中：门禁恢复阻塞，但双口径仍不一致（本地带 `--explicit-package-bases`、CI 不带） | 中（两处命令仍不同源） | 高 | 无 | 1 批 | U-006/U-P023-2 无法关闭 |
| M-C 去 `\|\| true` + 加 `--check-untyped-defs`，其余不变 | 不动 `--explicit-package-bases` | 低 | 中：U-P023-2 可关，但 P4 的目录名风险留存——仓库若改名回 `*_v3.0` 类目录，CI 立刻 exit 2 | 中 | 中 | 无 | 1 批 | 隐患留存 |
| M-D 保留 `\|\| true` 但拆独立 job + 文档声明「非阻塞」 | 诚实化但不阻塞 | 中（新增 job） | 低：类型错误仍不进 CI 红 | 中 | 高 | 无 | 1 批 | U-006 永远无法关闭 |

**判定**：
- **M-A 采用**：① E5 支撑「不得静默」；② P4 证明 `--explicit-package-bases` 是**跨环境唯一稳压器**（本地必需、CI 无害），统一带上即消除目录名敏感；③ P5 证明 `--ignore-missing-imports` 冗余，去掉不减能力；④ P6 证明 `--check-untyped-defs` 当前 0 残差，纳入零成本——三者叠加后两侧命令**逐字相同**，满足「同一形状」目标。
- **M-B 否决**：门禁虽恢复，但两侧命令仍不同源；且 U-006 的判据原文是「收紧 `mypy-check` 命令口径（如 `--check-untyped-defs`）」，不加旗标则 U-006 无判据可依。
- **M-C 否决**：P4 已实证目录名敏感性，去掉 `--explicit-package-bases` 等于把 CI 的可用性押在仓库名不含点号上；这与「对齐本地口径」的目标直接冲突。
- **M-D 否决**：与用户裁决「去 `|| true`」相反；且新增 job 属过度设计（本仓 CI 单 job 已有清晰结构）。

**README 处置**：`uv sync` → `uv sync --all-extras`（覆盖 dev + web，与 Quick Start 后续 `python cli.py test` / `python cli.py dashboard` 两步都自洽）；不加第二行 `--extra web` 变体（避免同义选项并列增加认知负担）。依据：P8 的 CLI 原文 + P9 的 extras 真值。

---

## 5. 取证读数（Step 1，HEAD `6ed74d0`）

| # | 命令/探针 | 读数 |
|---|-----------|------|
| A | `pytest -q`（Agg，3.12.10） | **651 passed, 152 warnings in 42.21s** |
| B | `mypy --explicit-package-bases core`（本地门禁口径） | `Success: no issues found in 36 source files`；另有 3 条 `annotation-unchecked` note（`execution.py:57` / `live_bridge.py:158-159`） |
| C | `mypy core/ --ignore-missing-imports --no-error-summary`（CI 口径，本地复现） | **exit 2**：`Factor_Trading_v3.0 contains __init__.py but is not a valid Python package name` |
| D | `mypy --explicit-package-bases --check-untyped-defs core`（拟采用口径） | `Success: no issues found in 36 source files`（0 errors） |
| E | `mypy --explicit-package-bases --no-error-summary core` | 无汇总行输出，exit 0 → `--no-error-summary` 只影响输出，不影响判定 |
| F | `black --check .` | `179 files would be left unchanged` |
| G | `p024_gate_probe.py`（Git bash） | A: `exit=3` / B: `exit=0` / C(myPy 失败，无 `\|\| true`): `exit=2` / D(同 C + `\|\| true`): `exit=0` |
| H | `uv sync --help`（uv 0.11.14） | `--extra <EXTRA>`「Include optional dependencies from the specified extra name」；`--all-extras`「Include all optional dependencies」 |

> 注：读数 B 的 3 条 note 是 mypy 对「无注解函数体默认不检查」的提示，**不是 error**；读数 D 纳入 `--check-untyped-defs` 后该提示消失且仍 0 errors。

**Step 9 追加读数（版本漂移现实化）**：`uv run --no-project --with mypy==2.4.1 python -m mypy --explicit-package-bases --check-untyped-defs core` → **24 errors / 8 files**（`core/config_v2.py` 3 / `filter/custom.py` 2 / `filter/industry.py` 1 / `filter/market_cap.py` 1 / `filter/prefix.py` 1 / `filter/na_factor.py` 2 / `filter/extended.py` 1 / `filter/universe_filter_clean.py` 13）；同命令 `mypy==2.1.0` → **0 errors / 36 files**。CI run `43193963200` 的 3.10 leg 读数为 **21 errors / 7 files**（Linux 侧少 3 条 `config_v2` 命中，平台差异）。→ 直接导致 U-P024-1 触发与 D6 修订。

---

## 6. 未决项登记（四元块）

- **U-P024-1 mypy 版本上限**
  - 判据：dev extras 中 `mypy` 是否加版本上限
  - 触发条件：CI 三条 leg 出现因 mypy 版本差异导致的**不一致结论**，或某 leg 装到的 mypy 不再支持该 Python
  - **状态：已触发并结案（P-024 Step 9）**——CI 首跑 run `43193963200` 的 3.10 leg 装到 **mypy 2.4.1**（本地 2.1.0），同一命令报 **24 errors / 8 files**（`core/config_v2.py` 3 + `filter/*` 21）：`filter` 由 `engine_v2` L61-62 / `factory` L31 导入而被 follow，`core/config_v2.py` 的 3 条为 2.4.x 新增检查命中冻结模块。处置：**钉 `mypy~=2.1.0`**（pyproject + `uv.lock` 各 1 行），三腿与本地同引擎
  - 证据等级：E1（本地 `uv run --with mypy==2.4.1` 复现 24 errors；2.1.0 为 0）

- **U-P024-4 mypy 升级到 2.4.x 前的清零**
  - 判据：`mypy~=2.4` 下 `core`（含 follow 到的 `filter/*`）0 errors
  - 触发条件：需要 2.4.x 的新检查能力，或 `filter/` 纳入检查面（U-P024-3）
  - 当前倾向：维持 `~=2.1.0`；待 `core/config_v2.py`（冻结模块，3 条 `no-any-return`）与 `filter/*`（21 条，`universe_filter_clean.py` 独占 13）清零后再放宽
  - 证据等级：E1（run `43193963200` 3.10 leg 日志 + 本地 2.4.1 复现）

- **U-P024-2 CI 增加 `uv lock --check`**
  - 判据：`tests.yml` 出现锁校验步骤
  - 触发条件：锁再次漂移，或 CI 改用 uv 安装路径
  - 当前倾向：不做（U-P021-1 已登记同源事项，本批不重复承接）
  - 证据等级：E3（tests.yml 当前仅 pip 安装）

- **U-P024-3 mypy 检查面扩展（`cli.py`/`agents`/`web`/`scripts`）**
  - 判据：门禁命令的 target 从 `core` 扩展为多包，且 exit 0
  - 触发条件：`core` 之外出现类型相关生产事故，或用户要求全仓类型治理
  - 当前倾向：不扩（本批只对齐口径；扩展会引入未知量级的新错误面）
  - 证据等级：E1（读数 B/D 的 target 为 `core`）

---

## 7. 批次切分

| 批次 | 内容 | 变更面 |
|------|------|--------|
| **B1** | CI mypy 步骤：去 `\|\| true`；改 `python -m mypy`；加 `--explicit-package-bases` / `--check-untyped-defs`；去 `--ignore-missing-imports` / `--no-error-summary` | [tests.yml](../.github/workflows/tests.yml) L45-L46 |
| **B2** | 本地门禁同步：`mypy-check` 加 `--check-untyped-defs` | [spec_runner_adapter.py](../scripts/spec_runner_adapter.py) L67 |
| **B3** | README uv 段：`uv sync` → `uv sync --all-extras` | [README.md](../README.md) L217-L221 |
| **B4** | 台账：§1.4 补登 **U-P023-1~4** 四行 + **U-P024-1~3** 三行；§2 U-006 行补 P-024 注记 + 追加关闭注；§3.28 执行记录；CHANGELOG | [PROGRESS.md](PROGRESS.md)、[CHANGELOG.md](../CHANGELOG.md) |
| **B5** | 四文档回填 + 推送 + CI run 回收 + 复审（RULE-5 另立会话） | 本批四文档 |

---

## 8. Step 2 Review（独立 pass）

| # | 审查项 | 结论 |
|---|--------|------|
| R1 | **事实完整性**：F1-F4 是否都有 P 编号承载 | ✅ F1→P1/P2/P13；F2→P3/P4；F3→P8/P9；F4→P11；U-P023-4→P12 |
| R2 | **证据等级合规**：结论是否只依赖 E1/E2/E3 | ✅ 全部结论有 E1-E3 支撑；表格中无 E5 推测 |
| R3 | **外部引用门槛（F4）** | ✅ 5 条有效外部锚点（E1-E5），全部命中正文，已建表 |
| R4 | **降级链（F3）** | ✅ 3 处降级均已登记并给出替代证据（uv 页空 → CLI help；GH Actions 截断 → 本地探针；typing 页截断 → 沿用 P-023） |
| R5 | **方案矩阵维度** | ✅ 7 维齐（成本/收益/维护/兼容/数据风险/短期/长期），4 方案 + 逐条否决理由 |
| R6 | **出界声明** | ✅ 四项出界明确（版本上限 / uv lock 门禁 / 检查面扩展 / 新增类型治理） |
| R7 | **零预填** | ✅ 全文无实测读数占位；§5 全部为 Step 1 实读 |
| R8 | **与上游一致性**：是否重复承接 U-P021-1 | ✅ §6 U-P024-2 明确「不重复承接」 |
| R9 | **判档合规** | ✅ 路径 `.github/workflows/` → Layer-1；门禁口径 → 规则 2 升级 → T1 |
| R10 | **术语一致**：门禁 / 口径 / 盲区 三词是否与 P-007/P-023 同义 | ✅ 门禁 = Gate exit code 机械映射；口径 = 命令字符串；盲区 = 无注解函数体检查 |

**Step 2 输出**：**0 个 P1/P2**；1 个 P3（**F-S2-P024-1**：P7 初稿把 CI 矩阵位置误记为 `pyproject.toml` L15-L16，实为 [tests.yml](../.github/workflows/tests.yml) L15-L16，`pyproject` 侧只有 L65 的 `mypy>=1.5.0` 与 L106 的 `python_version`——已在 P7 订正为双来源分列）。**结论：可进入 Step 3 DESIGN。**
