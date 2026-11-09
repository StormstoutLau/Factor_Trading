# TD-9（P-003） · black 全量重排 · 设计文档

> **文档编号**: DESIGN_td9_black
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: 完稿；Step 4 Review **通过**（2026-11-09；0 项阻断，3 项 P3 已回写，见 §9）
> **上游**: [RESEARCH_td9_black.md](RESEARCH_td9_black.md)（Step 2 Review 通过，含 S1-S3 / P1-**P18** / Q1-Q6）
> **下游**: [IMPL_td9_black.md](IMPL_td9_black.md) → [CHECKLIST_td9_black.md](CHECKLIST_td9_black.md)
> **证据时点**: 本仓读数 @ `080f3a3`；解释器 Python 3.12.10
> **档位**: T1（批量 style-only 重写，覆盖 Layer-1 路径）

---

## 1. 决策总览

| ID | 决策项 | 决定 | 对应 RESEARCH |
|----|--------|------|---------------|
| **D1** | 重排范围 | **全量 126 文件**（`black .` 等效范围，含 core/tests/examples/agents/filter/web 等 14 路径） | Q1 |
| **D2** | black 版本锁定 | **`black~=26.0`** 写入 `[project.optional-dependencies] dev` | Q2 / S1 |
| **D3** | 门禁命令范围 | **`black --check .`**（替代现 `black --check core tests`） | Q3 / Q6 |
| **D4** | blame 可追溯性 | 新增 `.git-blame-ignore-revs` 并记录重排提交 hash（两笔提交） | Q4 / S3 |
| **D5** | CI black step | **本批不加**（记录为已知未覆盖） | Q5 |
| **D6** | 目录排除策略 | 依赖 black 默认 exclude（`.venv` 已在默认列表），不自定义正则 | Q6 |
| **D7** | 提交策略 | 重排提交 + 元数据提交，**两笔**，均 style/chore 前缀 | TD-9 原文 / R-7 |

---

## 2. 逐项决策与依据

### D1 重排范围：全量 126 文件

**依据**

1. TD-9 原文措辞为「**全量** black 重排」；方案 A（仅 `core tests` 72 文件）会遗留 54 个不合规文件（examples 7 / scripts 2 / agents 13 / filter 9 / factor_library 2 / web 8 / 根 cli.py 1 / batch_backtest 2 / order_strategy 3 / strategy_evaluation 3 / tools 4），未来须再开一次同等成本的独占窗口。
2. 预演已证零风险：126 文件重排后 `507 passed` 逐字一致、mypy `119 errors` 不变（RESEARCH §1.4 / P11）。
3. 改动行数 9169（+4853/−4316），与方案 A 的 9169 中约 75% 重叠——增量成本有限，收益是一次性收口。

**被拒方案与代价**

| 方案 | 代价 |
|------|------|
| A 最小（core+tests 72） | 门禁虽可转绿，但 `examples/`、`agents/`、`web/` 等 54 文件长期漂移；下次合入这些目录的新代码时格式不一致，未来必再开一次独占窗口 |
| C 逐目录分批（core 一批、tests 一批） | 每批都要独立验证与独占窗口，总成本更高，且中间态门禁仍 fail |

### D2 版本锁定：`black~=26.0`

**依据（S1 逐字）**：「If code has been formatted with *Black*, it will remain unchanged when formatted with the same options using any other release **in the same calendar year**」+「projects can safely use `black ~=26.0` without worrying about formatting changes disrupting their project in 2026」。

即：`~=26.0` 保证 26.x 全系列格式一致（含未来补丁/次版本），同时把 27.x 跨年变更挡在门外——这正是 TD-9「先锁定 black 版本」的可执行形式。

**被拒方案与代价**

| 方案 | 代价 |
|------|------|
| `black==26.5.0` | 过严：无法接收 26.x 的 bug 修复（如崩溃修复），而 S1 明确同系列不改格式，pin 到补丁版无额外收益 |
| 不锁（保持 `>=23.0.0`） | 27.x 首版可能改格式（S1 明文允许），届时 126 文件重排成果全部失效，需重做整个窗口 |
| `black>=26.0` 无上界 | 等价于不锁，跨年风险同上 |

**长期维护义务（须登记）**：每年评审一次是否放宽到次年主版本；不可依赖自动升级。

### D3 门禁命令：`black --check .`

**依据（实测）**：`black --check .` 输出 **`126 files would be reformatted, 9 files would be left unchanged`**，与 14 路径显式枚举**逐字相同**；`docs/` 下 py 文件数 = **0**，无常驻干扰。

**收益**：命令简洁、自动覆盖未来新增目录、避免枚举遗漏。

**被拒方案与代价**

| 方案 | 代价 |
|------|------|
| 保持 `black --check core tests` | 无法守护本批新增的 54 个合规文件，格式会再次漂移 |
| 枚举 14 条路径 | 冗长、易漏；新增目录需人工追加 |

### D4 blame：`.git-blame-ignore-revs` + 两笔提交

**依据（S3 逐字）**：`--ignore-revs-file <file>`「Ignore revisions listed in *<file>*, which must be in the same format as an `fsck.skipList`」；另有 `blame.ignoreRevsFile` 配置项。本仓 Git 2.53.0 满足版本要求（P13）。

**鸡生蛋问题的解法（两笔提交）**

| 序 | 提交 | 内容 |
|----|------|------|
| 1 | `style(TD-9): black 全量重排（P-003）` | 126 文件格式重排 |
| 2 | `chore(TD-9): 记录格式提交至 .git-blame-ignore-revs` | 新建 `.git-blame-ignore-revs`，内容为提交 1 的完整 40 位 hash + 注释行 |

**文件格式**（同 `fsck.skipList`）：每行一个完整 hash；`#` 开头为注释。

**本地启用说明**：仓库提供文件后，开发者需执行 `git config blame.ignoreRevsFile .git-blame-ignore-revs`（该配置不随仓库分发）；GitHub Web blame 会自动识别该文件名。

**被拒方案与代价**

| 方案 | 代价 |
|------|------|
| 不做 | 126 文件的历史行归属永久指向格式提交，`git blame` / `git log -L` 追溯失效，违反 TD-9 自身「保护评审可读性」的初衷 |
| 单笔提交（重排 + 文件同时） | 无法写入自身 hash（提交前未知）；用 amend 改写则 hash 再次变化，仍不成立 |
| 用 `git blame -w`（忽略空白） | 仅缓解空白类改动；black 还会改变换行、括号与调用展开，覆盖不全；且不能用于 `git log -L` |

### D5 CI 不加 black step

**依据**：CI [tests.yml](../.github/workflows/tests.yml) 当前无 black 依赖安装、无 black step（P6）。加入需同时处理：`[dev]` 依赖解析、三版本矩阵验证、失败时的阻断策略。这属独立变更面（Layer-1 `.github/`），与「style-only 重排」混批会违反 TD-9 的独立窗口要求。

**验收口径影响（如实声明）**：本批完成后 **CI 仍不校验格式**；`black-check` 仅在本地 Spec_Runner 门禁链转绿。该未覆盖项在 CHECKLIST 中标 `[未在 CI 覆盖]`，**不得写成 CI 已验证**。

### D6 排除策略：依赖默认 exclude

**依据（实测）**：`black .` 结果 126/9 与显式枚举一致，说明默认 exclude 已正确跳过 `.venv`（1174 个 py 文件）、`.git` 等；且 `docs/` 无 py 文件。

**被拒方案**：自定义 `extend-exclude` / `--exclude` 正则——无实际需要，增加配置面与维护成本。

### D7 提交策略：两笔，均不含功能改动

- 提交 1：126 文件，纯格式；`git diff --numstat` 应只体现空白/换行/括号重排。
- 提交 2：1 文件元数据。
- **禁止**：本批混入 `pyproject.toml` 版本锁定？→ **不禁止，但须谨慎**：D2 的 `black~=26.0` 属配置语义变更（非格式），建议纳入提交 1（同属 TD-9 范围，且必须在同一提交内才能保证新装环境使用同版本）。若审阅认为应以独立提交表达，可拆为提交 1a（pyproject）+ 1b（重排）。

> **本设计采用**：提交 1 含 `pyproject.toml`（D2 锁定）+ 126 文件重排；提交 2 为 `.git-blame-ignore-revs`。理由：版本锁定与重排必须原子生效，否则中间态「锁定版本但未重排」或「已重排但版本未锁」都无意义。

---

## 3. 精确变更面

| 文件/路径 | 变更 | 行数（实测 E1） |
|-----------|------|-----------------|
| 126 个 `*.py`（`black .` 范围） | black 机械重排（纯格式） | **+11145 / −10054**（21199 改动行；43205 diff 行） |
| [scripts/spec_runner_adapter.py](../scripts/spec_runner_adapter.py) **L66** | `black-check` 门禁命令：`black --check core tests 2>&1` → `black --check . 2>&1`（D3，**语义改动**） | ±1 行 |
| [pyproject.toml](../pyproject.toml) **L64** | `"black>=23.0.0"` → `"black~=26.0"`（D2，**语义改动**） | ±1 行 |
| `.git-blame-ignore-revs`（新增） | 重排提交 hash + 注释 | 新增 2-3 行 |
| `docs/PROGRESS.md` | P-003 → done；§3.8 批次记录 | 追加 |
| `docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_td9_black.md` | 四文档 | 新增 |

> **口径修正（Step 4 Review，F-D1）**：初稿引用 RESEARCH P12 的 `+4853/−4316` 为 **core+tests 口径（72 文件）**，与 D1「全量 126 文件」不自洽。上表已改为全量实测；两口径差值即其余 54 文件贡献（+6292/−5738）。
>
> **遗漏修正（Step 4 Review，F-D2）**：初稿 §3 未单列 `spec_runner_adapter.py` 的门禁命令变更。该文件虽包含在 126 个重排文件中，但 **GATES 字符串替换属语义改动**，须单独受审，不得被「纯格式」掩盖。

**不变项**：`[tool.black]` 配置（line-length 100、target-version 三值）不改；`[tool.isort]` 不改；测试文件数（48）与测试数（507）不变；`core/engine_v2.py` 等生产逻辑零语义变更。

---

## 4. 锚点表（实施定位）

| 锚点 | 位置 | 用途 |
|------|------|------|
| `dev` 依赖块 | [pyproject.toml](../pyproject.toml) L60-68，black 在 **L64** | D2 唯一编辑点 |
| `[tool.black]` | [pyproject.toml](../pyproject.toml) L91-93 | 只读，不修改 |
| GATES 门禁表 | [scripts/spec_runner_adapter.py](../scripts/spec_runner_adapter.py) L63-68，`black-check` 在 **L66** | D3 编辑点 |
| CI 工作流 | [.github/workflows/tests.yml](../.github/workflows/tests.yml) L45-46 | 只读，本批不改（D5） |
| `type: ignore` 单点 | [tests/test_execution_policy.py](../tests/test_execution_policy.py) L282 | 重排后须复核该注释仍附着于原表达式 |

---

## 5. 验证契约

| ID | 断言 | 命令 | 期望 |
|----|------|------|------|
| V1 | 重排完成 | `black <14 路径>` | `126 files reformatted, 9 files left unchanged` |
| V2 | 全量回归 | `MPLBACKEND=Agg pytest tests -q` | `507 passed`（与基线逐字一致） |
| V3 | 格式幂等 | `black --check .` | exit 0，`135 files would be left unchanged` |
| V4 | 门禁转绿 | `adapter gate black-check` | **verdict=pass**（区别于基线 fail） |
| V5 | 类型不劣化 | `mypy --explicit-package-bases core` | `119 errors in 19 files`（与基线逐字一致，不得增加） |
| V6 | 语义零变更 | `git diff --numstat` + 抽样读码 | 无标识符/字符串/逻辑改动 |
| V7 | 版本锁定生效 | `pip install ".[dev]"` 解析 + 读回 pyproject | `black~=26.0` |
| V8 | blame 可追溯（**尽力回退**） | `git blame --ignore-revs-file .git-blame-ignore-revs <抽样文件>`，对照不加参数的同文件 | 部分行回退至原提交；black 结构性换行导致的行保留格式提交归属并被 git 标为 unblamable（`*`）——见 **F-9-2**，属 git 机制固有行为 |
| V9 | 单测计数不变 | `pytest --collect-only -q` | `507` 收集（tests 48 文件） |
| V10 | CI 范围零改动（D5） | `git diff --stat -- .github/` | **输出空** |
| V11 | 保护路径核查 | `.github/` diff 为空 + 读回 `[tool.black]`/`[tool.isort]` 逐字不变 + `git diff --name-only -- core/engine_v2.py core/factory.py`（**允许格式 diff**） | `.github/` 空、两配置块不变；engine_v2/factory 的语义等价由 **V12** 保证，**不要求零 diff** |
| **V12** | **语义零变更（机械验证）** | 对 125 文件（**排除** `scripts/spec_runner_adapter.py`，其 GATES 字符串为有意语义改动）比较 `ast.dump(ast.parse(...))`，比较前对**所有 docstring 逐行 `rstrip` 归一化** | **全部逐字相等** |

---

## 6. 风险登记

| ID | 风险 | 等级 | 缓解 |
|----|------|------|------|
| R1 | black 重排改变字符串字面量拼接方式，影响某处精确文本断言 | 低 | V2 全量回归；P9 已证无测试读源码 |
| R2 | `# type: ignore`（L282 单处）因换行移位失效 | 低 | V5 要求 mypy 读数不增；单点人工复核 |
| R3 | 跨年 black 主版本变更导致格式再次漂移 | 中 | D2 `~=26.0` 锁定；年度评审义务 |
| R4 | CI 无格式校验，格式可能再次漂移 | 中 | D5 如实声明；本地门禁 `black --check .` 守护（D3） |
| R5 | `git blame` 历史归属丢失 | 中 | D4 `.git-blame-ignore-revs` + 两笔提交 |
| R6 | `.venv` 被误扫导致极慢或污染 | 低 | D6 默认 exclude；V3 实测 135 文件（非 1300+） |
| R7 | 重排 diff 过大导致评审无法逐行审阅 | 中 | 预演已证语义零变更；评审以 V2/V5 读数为主要依据，抽样读码为辅 |
| **R8** | **black 会清理 docstring 行尾空白，导致 `__doc__` 字符串值改变**（Step 6 Review 实测：朴素 AST 比较 **不等价**；归一化后等价） | 低 | V12 采用 docstring `rstrip` 归一化比较；已核实 5 处 `__doc__` 依赖均为**子串断言**（非精确相等），空格清理不影响；V2 全量 507 passed 为最终证据 |

---

## 7. 回退点

| 场景 | 操作 |
|------|------|
| 重排提交后发现问题 | `git revert <重排提交>`——单笔回退即恢复全部格式原状；因无其他改动混入，回退干净 |
| 版本锁定引发环境问题 | 单独回退 `pyproject.toml` L64 一行 |
| blame 文件有误 | 回退第二笔提交，或修正 hash 行后重新提交 |

---

## 8. 范围外（明确不做）

| 项 | 理由 |
|----|------|
| CI 增加 black step | D5；属独立批次 |
| flake8 / isort 实际执行 | 本仓无 flake8 配置且不在门禁（RESEARCH P7 / S2 边界）；isort 已配 `profile="black"` 但未接入门禁，不属 TD-9 |
| mypy 119 errors 修复 | 属 P-007，独立批次 |
| `[tool.black]` 参数调整（line-length 等） | 无需求；调参会改变重排结果，扩大不确定面 |
| `.venv` 清理 | 与本批无关 |

---

## 9. Step 4 Review（独立 pass）

- **执行时点**: 正文完稿后单独执行，未与正文同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 重跑全量 diff 实测 + 核对 D1-D7 与 RESEARCH Q1-Q6 一一对应 + 逐条检查被拒代价 + 保护路径清单核查

**发现 3 项（均 P3，均已修复）**：

| ID | 发现 | 处理 |
|----|------|------|
| **F-D1** | §3 变更行数引用 RESEARCH P12 的 core+tests 口径（+4853/−4316），与 D1「全量 126 文件」不自洽 | 已改为全量实测 **+11145/−10054**（21199 改动行），并标注两口径差值来源 |
| **F-D2** | §3 精确变更面**遗漏** `scripts/spec_runner_adapter.py` L66 的 GATES 命令替换——该文件虽在重排范围内，但命令字符串替换属**语义改动**，若被「纯格式」掩盖则审计盲区 | 已在 §3 单列该行并标注「语义改动」，加留痕说明 |
| **F-D3** | §5 验证契约缺 D5（CI 不改）与保护路径的对应断言，导致「本批不改 CI」无证据出口 | 新增 **V10**（`.github/` diff 为空）与 **V11**（保护路径 + `[tool.black]`/`[tool.isort]` 逐字不变） |
| **F-D4（Step 6 Review 追加）** | **「AST 等价 = 零语义变更」的假设不成立**：实测 `core/factory.py` 重排后朴素 `ast.dump` 比较为 **False**，根因是 black 清理 docstring 行尾空白，改变 `Constant` 字符串值 | ① V12 定义改为「docstring 逐行 `rstrip` 归一化后比较」（实测归一化后 **True**）；② V12 范围排除 `spec_runner_adapter.py`；③ 新增风险 **R8** 并核实 5 处 `__doc__` 依赖均为子串断言 |

**对应性核对（D ↔ Q）**：

| 决策 | 来源问题 | 覆盖验证 |
|------|----------|----------|
| D1 全量范围 | Q1 | V1 / V3 / V9 |
| D2 版本锁定 `~=26.0` | Q2（S1） | V7 |
| D3 门禁 `black --check .` | Q3 | V4 |
| D4 blame 两笔提交 | Q4（S3） | V8 |
| D5 CI 不加 | Q5 | V10（新增） |
| D6 默认 exclude | Q6 | V3（135 而非 1300+） |
| D7 提交策略 | TD-9 原文 / R-7 | 流程约束（V6 语义零变更辅助） |

**保护路径核查**：

| 路径 | 本批是否改动 | 证据 |
|------|--------------|------|
| `.github/workflows/tests.yml` | **不改** | V10 |
| `[tool.black]`（L91-93）/ `[tool.isort]`（L95-97） | **不改** | V11 读回逐字 |
| `core/engine_v2.py` 等生产逻辑 | 仅格式，零语义 | V2 / V6 |
| 测试数与文件数（507 / 48） | 不变 | V2 / V9 |

**被拒代价完整性**：D1/D2/D3/D4 均给出被拒方案与具体代价；D5/D6 的被拒项已在 §8 范围外与 D6 表中声明。

**结论**: 0 项阻断（P1/P2 = 0）；**4 项 P3** 已回写（F-D1~F-D4，其中 F-D4 于 Step 6 Review 阶段追加）；D1-D7 与 Q1-Q6 全覆盖、验证契约 V1-V12 无悬空，可进入 Step 5 实施规划。
