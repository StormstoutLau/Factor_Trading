# TD-9（P-003） · black 全量重排 · 调研文档

> **文档编号**: RESEARCH_td9_black
> **阶段**: Phase 1 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: Step 1 完稿；Step 2 Review **通过**（2026-11-09；0 项阻断，2 项 P3 已回写，见 §6.1）；Step 6 Review 追加 **P17/P18** 事实（docstring 行尾空白清理）
> **上游**: `docs/PROGRESS.md` §1.4 P-003；[RESEARCH_tech_debt_cleanup.md](RESEARCH_tech_debt_cleanup.md) §TD-9 / §4.4
> **下游**: [DESIGN_td9_black.md](DESIGN_td9_black.md) → [IMPL_td9_black.md](IMPL_td9_black.md) → [CHECKLIST_td9_black.md](CHECKLIST_td9_black.md)
> **档位**: T1（改动覆盖 `core/`、`tests/` 等 Layer-1 路径，虽 style-only 但属批量重写）
> **证据时点**: 本仓读数 @ `080f3a3`；外部来源读取日 2026-11-09
> **规范版本**: `F:\Spec_Workflow\SPEC_PROCESS.md` **v1.7.2**

---

## 1. 问题定义

TD-9 的目标是消除代码格式基线不合规：`black --check` 在 `core tests` 上报告 **72 files would be reformatted**，导致 `black-check` 门禁长期 fail，且后续任何批次的 diff 都混有格式噪音。

### 1.1 TD-9 原文与实测偏差（本轮核心输入）

| 断言行 | TD-9 原文（[RESEARCH_tech_debt_cleanup §TD-9](RESEARCH_tech_debt_cleanup.md)） | 实测 @ `080f3a3` | 判定 |
|--------|-------------------------------------------------------------------|------------------|------|
| 文件数 | 「75/79 文件」 | **门禁范围 core+tests = 77 文件**（72 需改 + 5 合规）；**全仓 14 路径 = 135 文件**（126 需改 + 9 合规） | **口径修正**：原文 79 无对应实测值 |
| 改动行数 | 「约 7,872 行」 | core+tests 范围 **+4853 / −4316 = 9169 改动行**（19777 diff 行含上下文） | **数值修正**（F-R1） |
| black 版本 | 「先锁定 black 版本」 | dev 依赖 `black>=23.0.0`（**未锁定**）；本地实跑 26.5.0 | 原文要求**未落实**，本批须解决 |
| 执行方式 | 「独立 style-only 提交」 | — | 本批遵守（不混功能 diff） |

### 1.2 范围候选（须在 DESIGN 裁决）

| 方案 | 范围 | 文件数 | 门禁影响 | 风险 |
|------|------|--------|----------|------|
| **A 最小** | `core` + `tests` | 72 需改 / 77 | `black --check core tests` 转绿 | 低；但 `examples/`、`agents/`、`web/` 等 54 个文件仍不合规 |
| **B 全量** | 14 个路径（根 2 + core 29 + tests 48 + examples 7 + scripts 3 + agents 14 + filter 9 + factor_library 2 + web 9 + batch_backtest 2 + order_strategy 3 + strategy_evaluation 3 + tools 4） | 126 需改 / 135 | 须扩展门禁命令范围 | 中低；diff 面更大但一次性收口 |

> **倾向 B**：TD-9 原文措辞为「全量 black 重排」；且方案 A 会在未来某个时点再触发一次同样成本的独占窗口。最终由 DESIGN 决策。

### 1.3 目录与文件实测分布（E1）

| 路径 | py 文件数 | 需重排 | 合规 |
|------|-----------|--------|------|
| `core/` | 29 | **27** | **2** |
| `tests/` | 48 | **45** | **3** |
| `examples/` | 7 | 7 | 0 |
| `scripts/` | 3 | 2 | 1 |
| `agents/` | 14 | 13 | 1 |
| `filter/` | 9 | 9 | 0 |
| `factor_library/` | 2 | 2 | 0 |
| `web/` | 9 | 8 | 1 |
| 根目录 `cli.py` | 1 | 1 | 0 |
| 根目录 `__init__.py` | 1 | 0 | 1 |
| `batch_backtest/` | 2 | 2 | 0 |
| `order_strategy/` | 3 | 3 | 0 |
| `strategy_evaluation/` | 3 | 3 | 0 |
| `tools/` | 4 | 4 | 0 |
| **合计** | **135** | **126** | **9** |
| `.venv/`（**必须排除**） | 1174 | — | — |

> 口径说明（Step 2 Review 修正，F-R2）：门禁范围 `core tests` 的分项实测为 **core 27/2 + tests 45/3 = 72/5**，与合计一致；初稿曾误写 core 26/3 + tests 46/2（总数巧合相同、构成错误），已按逐路径实测订正。

### 1.4 可行性预演（本批关键证据，E1）

> 预演在真实工作区执行，完成后立即 `git checkout -- .` 还原；执行前后 `git status --short` 均为空，HEAD 保持 `080f3a3`。

| 步骤 | 命令 | 读数 |
|------|------|------|
| 1 重排 | `black <14 路径>` | **`126 files reformatted, 9 files left unchanged`** |
| 2 回归 | `MPLBACKEND=Agg pytest tests -q` | **`507 passed, 82 warnings in 25.20s`**（与基线逐字一致，零回归） |
| 3 复核 | `black --check <14 路径>` | **`135 files would be left unchanged`**（幂等，全绿） |
| 4 类型 | `mypy --explicit-package-bases core` | **`119 errors in 19 files`**（与基线逐字一致，重排不影响类型检查） |

结论：**重排对运行时行为与类型检查均为零影响**，方案可行性已实证。

---

## 2. 外部来源调研（Step 1，F1/F2/F3 字段齐备）

| ID | 来源 | 等级 | F1 日期 | F2 版本 | 关键事实 | 可解析 ID |
|----|------|------|---------|---------|----------|-----------|
| S1 | black 官方文档《The Black Code Style》— Stability Policy | **T1** | 读取 2026-11-09 | stable docs（对应 26.x） | ①「If code has been formatted with Black, it will remain unchanged when formatted with the same options using any other release **in the same calendar year**」；②「projects can safely use `black ~=26.0` without worrying about formatting changes disrupting their project in 2026」；③「The first release in a new calendar year *may* contain formatting changes」；④ `--preview` / `--unstable` **不受该政策约束** | https://black.readthedocs.io/en/stable/the_black_code_style/index.html |
| S2 | black 官方文档《Using Black with other tools》 | **T1** | 读取 2026-11-09 | stable docs | ① isort 官方推荐 `profile = "black"`；② flake8 与 black 冲突须 `extend-ignore = E203,E701`，且 `max-line-length` 应与 black 的 `line-length` 一致（默认示例 88） | https://black.readthedocs.io/en/stable/guides/using_black_with_other_tools.html |
| S3 | Git 官方文档《git-blame》 | **T1** | 读取 2026-11-09；页面 last updated in **2.56.0** | Git ≥ 2.23 | `--ignore-revs-file <file>`「Ignore revisions listed in `<file>`, which must be in the same format as an `fsck.skipList`. This option may be repeated, and these files will be processed after any files specified with the `blame.ignoreRevsFile` config option」 | https://git-scm.com/docs/git-blame |

**F3 降级链**：**无降级**——S1/S2/S3 均由 `WebFetch` 直读官方文档原文命中，未发生通道失败或搜索摘要替代。

### 2.1 来源适用边界

| 关系 | 说明 |
|------|------|
| S1 → 版本锁定形式 | 官方明确「同年内同选项结果不变」，故锁定 **`black~=26.0`** 优于 `==26.5.0`（保留 26.x 补丁/次版本升级能力，同时阻止 27.x 跨年格式变更）。TD-9 原文「先锁定 black 版本」据此得出可执行形式 |
| S1 → 跨年风险 | 政策显式允许「新年首个 release 可能有格式变更」。故锁定范围须在后续年度评审时手动放宽，**不能依赖自动升级**；此为已知的长期维护成本，须在 DESIGN 记录 |
| S2 → isort 已就位 | 本仓 `pyproject.toml` 已有 `[tool.isort] profile = "black"`（P2 事实），与 S2 官方推荐一致，无需改动 |
| S2 → flake8 未运行 | 本仓**无 flake8 配置文件**，flake8 不在门禁链、不在 CI step（P6/P7）。故 `E203/E701` 与 `max-line-length` 冲突**当前不发生**；本批不引入 flake8 配置（避免范围蔓延），仅在 DESIGN 记录该潜在不一致 |
| S3 → blame 可追溯性 | 重排会让 126 个文件的历史行归属全部指向格式提交。`--ignore-revs-file` 是官方提供的标准解法；本仓 Git 2.53.0 支持该选项（P13） |
| **不外推** | S1/S2 仅约束 black 自身行为，**不**为「重排后测试必然通过」提供任何保证；该结论仅由本仓预演（§1.4）支撑。S3 仅提供机制，不保证本仓配置即生效，须在 Step 9 实测验证 |

---

## 3. 本仓事实（E1/E3，@ `080f3a3`）

| ID | 断言 | 证据 |
|----|------|------|
| P1 | black **26.5.0**（compiled）；配置 `line-length = 100`、`target-version = ["py310","py311","py312"]` | E1 `black --version`；E3 [pyproject.toml](../pyproject.toml) L91-93 |
| P2 | 门禁范围 `core tests` = **77** 文件 → **72 reformatted / 5 unchanged** | E1 |
| P3 | 全仓 14 路径 = **135** 文件 → **126 reformatted / 9 unchanged**；`.venv` 内 1174 个 py 文件须排除 | E1 |
| P4 | dev 依赖声明为 `black>=23.0.0`，**未锁定** | E3 [pyproject.toml](../pyproject.toml) L64 |
| P5 | `.git-blame-ignore-revs` **不存在**；`blame.ignoreRevsFile` 配置**未设置** | E1 `Test-Path` → `False` |
| P6 | CI [tests.yml](../.github/workflows/tests.yml) L45-46：**无 black step**；mypy step 命令为 `mypy core/ --ignore-missing-imports --no-error-summary \|\| true`（**软检查，永不影响 job 结论**） | E3 |
| P7 | 无 `flake8` / `setup.cfg` / `tox.ini` / `.editorconfig` / `pre-commit-config` 配置文件；仅 pyproject 的 `[tool.black]` 与 `[tool.isort]` | E1 文件枚举 |
| P8 | 全仓无生成代码标记（`@generated` / `autogenerated` / `DO NOT EDIT` / `自动生成` 在 `*.py` 中 0 命中） | E1 |
| P9 | 无测试读取源码文本（`read_text(` / `open(__file__` / `inspect.getsource` / `getsource(` 在 `tests/*.py` 中 0 命中） | E1 |
| P10 | 全仓 `type: ignore` / `# noqa` 仅 **1 处**：`tests/test_execution_policy.py:282`（`ExecutionPolicy()  # type: ignore`） | E1 Grep count + 精确定位 |
| P11 | 可行性预演：重排 126 文件 → `507 passed in 25.20s`；`black --check` 135 全绿；mypy `119 errors` 不变；工作区已还原 | E1（§1.4） |
| P12 | core+tests 范围 diff 体量：**+4853 / −4316**（72 文件，19777 diff 行）；全量 126 文件口径见 [DESIGN_td9_black.md](DESIGN_td9_black.md) §3（**+11145 / −10054**） | E1 `black --diff` 统计 |
| P13 | `git version 2.53.0.windows.2`（≥2.23，支持 `--ignore-revs-file` / `blame.ignoreRevsFile`） | E1 |
| P14 | 目录分布见 §1.3（合计 135 与全仓 py 计数一致） | E1 |
| P15 | 当前基线：全量 `507 passed`；门禁 `black-check` fail(72) / `mypy-check` fail(119)；测试文件 48 | E1 |
| P16 | 历史记录类文档（`DEVLOG.md`、`docs/archive/` 等）不在本批改动面 | E3（依 D5 活/历史分离惯例） |
| **P17** | **black 重排会清理 docstring 行尾空白**，导致字符串常量值改变：实测 `core/factory.py` 类 docstring `"组件工厂\n    \n    集中..."` → `"组件工厂\n\n    集中..."`；朴素 `ast.dump` 比较为 **False**，docstring 逐行 `rstrip` 归一化后为 **True** | E1（Step 6 Review 实测，2026-11-09） |
| **P18** | 全仓 `__doc__` 依赖 **5 处**（`tests/test_p2_v3_alignment.py` L29/L31/L39、`tests/test_p2_risk_naming.py` L56/L65），**全部为子串包含断言**（`assertIn` / `in`），非精确相等 → 行尾空格清理不影响判定 | E1 Grep + 读码（Step 6 Review 补充） |

---

## 4. 影响范围汇总

| 范围 | 内容 |
|------|------|
| 代码（方案 B） | 126 个 py 文件纯格式重排；**零语义变更** |
| 配置 | `pyproject.toml` dev 依赖 `black>=23.0.0` → 锁定（形式待 DESIGN 定） |
| 配套 | 新增 `.git-blame-ignore-revs`（记录重排提交 hash）；`blame.ignoreRevsFile` 配置说明 |
| 门禁 | `black-check` 由 fail(72) 转 pass；门禁命令范围是否扩展待 DESIGN |
| CI | **本批不改**（不加 black step）——避免 scope creep；须在 DESIGN 显式声明为「已知未覆盖」 |
| 文档 | 台账 P-003 → done；另需评估 README/ARCHITECTURE 是否含格式相关表述 |
| 生产逻辑 | **零算法变更**（预演已证 507 passed 逐字一致、mypy 读数不变） |

---

## 5. 未决点（移交 DESIGN）

| ID | 未决点 | 候选 | 判定依据 |
|----|--------|------|----------|
| Q1 | 重排范围 | A 最小（72）/ B 全量（126） | TD-9 原文「全量」；避免二次独占窗口 |
| Q2 | black 版本锁定形式 | `~=26.0` / `==26.5.0` / 不锁 | S1 Stability Policy 明确推荐 `~=26.0` |
| Q3 | 门禁命令是否扩范围 | `core tests` 不变 / 扩到 14 路径 | 与 Q1 联动：若选 B，门禁须同步扩展否则无法守护成果 |
| Q4 | blame 方案 | `.git-blame-ignore-revs` + 配置 / 不做 | S3 机制；不做则永久丧失历史可追溯性 |
| Q5 | CI 是否加 black step | 加 / 不加 | 加则本批范围扩大到 workflows（Layer-1）并可能立即影响后续提交；不加则格式合规仅靠本地门禁 |
| Q6 | `.venv` 等排除策略 | 显式目录列表 / `--exclude` 正则 | 本仓 `.venv` 有 1174 个 py 文件，误扫会极慢且有污染风险 |

---

## 6. 取证与 Review

### 6.1 Step 2 Review（独立 pass）

- **执行时点**: 正文完稿后单独执行，未与正文同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座
- **审查方式**: 逐路径重跑 E1 计数 + 二次直读 S1/S2/S3 + 精确定位 P10 + 文件枚举验证 P5/P7

**发现 2 项（均 P3，均已修复）**：

| ID | 发现 | 处理 |
|----|------|------|
| F-R1 | §1.1 未如实记录 TD-9 原文数值与实测的偏差（原文「79 文件 / 约 7,872 行」，实测门禁范围 77 文件、全仓 135 文件；核心改动行 9169） | 已在 §1.1 表格逐行登记「口径修正 / 数值修正」 |
| F-R2 | §1.3 分目录构成初稿错误：core 写 26 需改/3 合规、tests 写 46/2；逐路径实测为 **core 27/2、tests 45/3**（合计 72/5 巧合相同，构成错误） | 已按逐路径实测订正，并加口径说明留痕 |

**复核结果**：

| 断言 | 复核方式 | 结果 |
|------|----------|------|
| 门禁范围 72/5 | `black --check core`（27/2）+ `black --check tests`（45/3） | 27+45=72、2+3=5，与合计数一致 |
| 全仓 126/9 | 14 条路径逐条 `black --check` 累加 | 1+0+27+45+7+2+13+9+2+8+2+3+3+4 = **126**；0+1+2+3+0+1+1+0+0+1+0+0+0+0 = **9** |
| `.venv` 规模 | `Get-ChildItem .venv -Filter *.py -Recurse` | 1174（必须排除，P3 成立） |
| P5 无 blame 文件 | `Test-Path .git-blame-ignore-revs`；Glob 枚举 | `False`；Glob 无命中 |
| P7 无 lint 配置文件 | Glob `{.flake8,.isort.cfg,setup.cfg,tox.ini,.editorconfig,.pre-commit-config.yaml}` | **无命中**；确认仅 pyproject 内含 `[tool.black]` L91-93 / `[tool.isort]` L95-97 |
| P10 单处 type: ignore | Grep + Read 精确定位 | `tests/test_execution_policy.py:282`，内容 `ExecutionPolicy()  # type: ignore` |
| P1 black 配置 | Read pyproject L91-93 | `line-length = 100`、`target-version = ["py310","py311","py312"]` |
| S1 稳定性政策 | 二次直读原文 | 逐字命中「remain unchanged … in the same calendar year」与「`black ~=26.0`」 |
| S2 isort 推荐 | 二次直读原文 | 命中 `[tool.isort] profile = "black"` |
| S3 git-blame 选项 | 二次直读原文 | 命中 `--ignore-revs-file <file>` 与 `blame.ignoreRevsFile` |
| 预演可复现性 | 工作区还原后复核 `git status --short` | 空输出；HEAD = `080f3a3`（预演未污染仓库） |

**F3 降级链复核**：S1/S2/S3 三次调用均直读成功，无降级、无搜索摘要替代。

**结论**: 0 项阻断（P1/P2 = 0）；2 项 P3 已回写；数据可重放，可进入 Step 3 设计。

---

## 7. 结论

TD-9 的债务性质为**纯格式基线不合规**，无运行时风险，但会持续污染评审 diff 并封锁 `black-check` 门禁。

本轮调研的关键实证是 §1.4 的可行性预演：**126 文件重排后全量测试 507 passed 逐字一致、mypy 读数不变、black 复核幂等全绿**——这为「重排零语义风险」提供了直接证据，而非仅靠「格式化工具理应无害」的推断。

六个未决点（Q1-Q6）已移交 DESIGN；其中 Q2（版本锁定）与 Q4（blame）有明确的外部权威依据（S1/S3），Q1/Q3/Q5 需在 DESIGN 结合本仓约束裁决。
