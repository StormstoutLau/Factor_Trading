# PROGRESS 待办登记与进度分析

> **规范依据**: `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1（10 步 Spec 流程 + RULE-1~6 + E1-E5 取证分级 + T1/T3 批次档位）
> **登记日期**: 2026-11-04
> **状态词表**: `pending / in-progress / blocked / done`（DC2.1；执行态与决策态同一位点单来源）
> **证据分级**: E1 可重放命令 / E2 运行时脚本 / E3 静态读码（须绑定 commit hash）/ E4 盲区扫描 / E5 推测（禁止用于结论）
> **编号口径**: 本仓 P 编号为独立命名空间，不与 `Spec_Workflow` 的 P 编号复用

---

## 1. 当前进度快照（2026-11-04）

### 1.1 仓库状态

| 项 | 值 | 证据 |
|----|----|------|
| HEAD | `df652f9e3595dbbb2b1dfc1d7dccc016851c84c5` | `git rev-parse HEAD`（E1，2026-11-04 更新） |
| 分支同步 | `master` 与 `origin/master` 指向同一提交（`df652f9`）；远端已切换 SSH | `git rev-parse HEAD origin/master`（E1） |
| 工作区（本批开始前） | 干净（无已跟踪修改、无未跟踪文件） | `git status --short` 空输出（E1） |

### 1.2 测试状态

| 场景 | 结果 | 证据 |
|------|------|------|
| 默认 matplotlib 后端 | `1 failed, 505 passed, 3 errors, 82 warnings in 19.19s`；失败项 `test_real_ashare_backtest.py::TestRealAshareBacktest::test_08_portfolio_value_positive`；3 个 error 为 `test_real_ashare_strict_validation.py` 的 setup（test_12/13/14）；根因均为 `_tkinter.TclError`（本机 Tk 缺 `tk.tcl`） | 日志 `%TEMP%\pytest_default_backend_p0_20261104.log` 第 59、134、206、320、766、794-887 行（E1） |
| `MPLBACKEND=Agg` | `509 passed, 82 warnings in 20.02s` | 日志 `%TEMP%\pytest_agg_sr_integration_final_20261104.log`，SHA256 `D262199F55DC7D2E2AD85D5D1868CB1221F0FFFE96B3E8A57B8369311DC57707`（E1） |

结论：默认后端失败/错误由本机 Tk 安装不完整引起，非代码回归；无头后端下 509 全通过（= 503 基线 + 6 项 adapter 测试）。

> **解释器口径（2026-11-04 复核）**: 上述基线使用 `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`。当前 shell 的 `python` 解析到 `C:\ProgramData\Anaconda3\python.exe`（3.13.5，缺 `cvxpy`），直接复跑会出现 `collected 483 / 2 errors`；以 Python312 复跑恢复 `509 passed`（见上表）。见 U-005。

### 1.3 已完成事项（近期提交）

| 项目 | 提交 | 状态 |
|------|------|------|
| CRITICAL 再平衡修复（双引擎目标持仓、调出清仓、SELL 优先、`unclosed_positions`） | `c0d34e2` | done |
| TD-5 移除旧版过滤器 `filter/universe.py` | `699063f` | done |
| TD-3 Stage 2：CLI 切换至 V2 默认引擎（R-1 受控对比一致） | `3f87576` | done |
| P0：H-1/H-2/H-3 文档幻觉修正 | `f4c13c3` | done |
| TD-6 memory 停止跟踪；TD-7 conversation 归档 | `65d750f`、`f4c13c3` | done |
| demo_data `stock_adj.pkl` 与 README/CODE_WIKI 对齐 | `84e9d4c` | done |
| 2026-10-23 差异报告 | `5b64cce` | done |
| TD-1.2 轻量子包化；历史文档存档标注；LLM 风险文档扩充；Web 主题统一；DECISIONS/SPEC_STANDARD 入库 | `2848331`、`c14cab6`、`1321a8e`、`8607c82`、`1058cbb` | done |
| 进度台账 + Spec 搜索锚点/方案对比矩阵规则 | `400394e` | done |
| Spec_Runner 接入（adapter + 4 门禁 + 四文档） | `df652f9` | done |

### 1.4 未完成事项

| ID | 事项 | 依据（含档位） | 状态 | 优先级 |
|----|------|----------------|------|--------|
| P-001 | TD-3 Stage 3：移除 `core/engine.py` | `docs/RESEARCH_tech_debt_cleanup.md` TD-3；实测 10 个实际导入文件（6 examples + 4 tests），`core/__init__.py` 仅注释提及；**T1**（Layer-1：删除 `core/engine.py` 并迁移 `tests/`、`examples/`） | pending | P2 |
| P-002 | TD-2：`core/config_v2.py` 冻结标注 | `docs/RESEARCH_tech_debt_cleanup.md` TD-2；当前文件无 `冻结/frozen/TD-2` 标注；**T3**（docstring-only，零运行时行为；路径不落在 scripts/tests/tools/workflows） | pending | P2 |
| P-003 | TD-9：black 全量重排 | `docs/RESEARCH_tech_debt_cleanup.md` TD-9；实测 `75 files would be reformatted, 5 unchanged`（black 26.5.0；2026-11-04 复核，新增测试已格式化）；**T1**（改动覆盖 `core/` 与 `tests/`，虽 style-only 但属批量重写） | pending | P3 |
| P-004 | TD-1：数据层统一（DataManager → DataLoaderV3 / Provider） | `docs/RESEARCH_tech_debt_cleanup.md` TD-1；两套实现仍并存；**T1**（数据层接口与生产消费方变更） | pending | P3 |
| P-005 | TD-4：Factor_DB 存储迁移 / 文档对齐（DuckDB 为规划方向） | `docs/RESEARCH_tech_debt_cleanup.md` TD-4；全仓仍无 `import duckdb`；**T1**（存储层接口变更） | pending | P3 |
| P-006 | ADR-016 补录或引用修正 | `__init__.py:3@1058cbb`、`core/__init__.py:3@1058cbb`、`pyproject.toml:79@1058cbb` 引用 ADR-016；`docs/DECISIONS.md` 当前仅 ADR-001~013；**T3**（纯文档一致性，零代码） | pending | P3 |
| P-007 | mypy 基线清理（`core` 168 errors / 20 files） | `python312 -m mypy --explicit-package-bases core`（E1，2026-11-04）；`mypy-check` 门禁当前预期 fail | pending | P3 |

> 状态说明：上表仅有决策态 `pending`（未开工）。开工后执行态由工作记录派生，不在本表手写。

### 1.5 本批新增（2026-11-04）

| 项目 | 文件 | 档位 | 状态 |
|------|------|------|------|
| Spec 搜索锚点规则增补 | `docs/SPEC_STANDARD.md` §十一；`docs/dev-log/DEV-LOG-002-search-anchor-rules-20261104.md` | T3（Layer-0，纯文档） | done（自查·单视角；`400394e`） |
| 方案对比 7 维矩阵规则增补 | `docs/SPEC_STANDARD.md` §11.8；`docs/dev-log/DEV-LOG-003-comparison-matrix-anchors-20261104.md` | T3（Layer-0，纯文档） | done（自查·单视角；`400394e`） |
| Spec_Runner 接入 | `scripts/spec_runner_adapter.py`、`tests/test_spec_runner_adapter.py`、`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_spec_runner_integration.md` | T1（Layer-1：scripts/ + tests/） | done（四文档 + 8 道 Review；`df652f9`） |
| P0 台账校正 | `docs/PROGRESS.md`、`docs/CHECKLIST_spec_runner_integration.md` | T3（Layer-0，纯文档） | done（session `factorv3-p0-ledger-fix-20261104`，5 行 replay OK） |

---

## 2. 未决项登记（四元块）

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| U-001 | 默认 matplotlib 后端下 `pytest tests/` 全绿 | 每次本地或 CI 测试（未设置 `MPLBACKEND` 时） | 本地与 CI 统一设置 `MPLBACKEND=Agg`；或修复 Python312 的 Tk 组件 | E1 |
| U-002 | `docs/DECISIONS.md` 出现 ADR-016，或三处代码引用改为已登记 ADR | 下次文档一致性更新 / P-006 开工 | 补录 ADR-016（TD-1.2 轻量子包化决策），保留代码引用 | E1 |
| U-003 | TD-3 Stage 3 的调研清单更新为实测值（6 examples + 4 tests，无 `core/__init__.py` re-export） | P-001 Step 1 调研启动 | 在新 RESEARCH 中更新清单后，再进入设计 | E1 |
| U-005 | 测试命令固定解释器，或各解释器依赖一致（`cvxpy` 可导入） | 每次本地或 CI 测试 | 命令中显式使用 Python312 路径；不默许 `python` 解析到 Anaconda 3.13.5 | E1 |
| U-006 | `mypy-check` 门禁转绿（`core` 0 errors） | mypy 清理批次启动 / 每次门禁链验收 | 先清理 P-007（168 errors），再收紧；门禁保持如实 fail | E1 |

> **已关闭（2026-11-04）**: U-004 —— [SPEC_STANDARD.md](SPEC_STANDARD.md) 头部已声明 `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1 为冲突时的权威源（@`400394e`），判据达成。
> **映射说明**: U-002 由 P-006 关闭；U-003 作为 P-001 Step 1 的输入，不单独占工作流。

---

## 3. 下一批次启动规则

### 3.1 P-001（TD-3 Stage 3）执行序

判定为 **T1 完整管线**，顺序固定：

1. Step 1：调研（更新 TD-3 Stage 3 引用清单、迁移路径、V1 黄金测试去留）
2. Step 2：Review（幻觉排除门禁）→ 形成 `RESEARCH.md`
3. Step 3：设计（迁移方案、删除边界、兼容性）→ Step 4 Review → `DESIGN.md`
4. Step 5：实施规划 → Step 6 Review → `IMPLEMENTATION.md`
5. Step 7：验收清单 → Step 8 文档一致性 Review → `CHECKLIST.md`
6. Step 9：TDD 实现（先写测试）
7. Step 10：ADD 审计 + 取证矩阵 + 更新本台账与开发日志

未通过 Step 8 门禁前，不得修改实现代码。

### 3.2 本批（进度落档 + 搜索锚点规则 + 方案对比矩阵）档位

判定为 **T3 轻批**：

- 改动范围：`docs/PROGRESS.md`、`docs/dev-log/`（DEV-LOG-001/002/003）、`docs/DEVLOG.md`、`CHANGELOG.md`、`docs/SPEC_STANDARD.md`（含 §十一 与 §11.8 规则增补）
- 裁剪理由：Layer-0 纯文档；零代码、零门禁、零真值源变更
- 回退点：删除新增文档并还原上述既有文档即可
- 证据出口：本文件 + 三份开发日志 + `git diff`（E1）+ 测试日志（E1）

### 3.3 本批（Spec_Runner 接入）档位

判定为 **T1 完整管线**（路径含 `scripts/` 与 `tests/`，按 `SPEC_PROCESS.md` L561 属 Layer-1）：

- 必需工件：RESEARCH → DESIGN → IMPL → CHECKLIST 四文档 + Step 2/4/6/8 四道文档 Review
- 证据出口：四文档 + Step 9 TDD 红/绿 + 4 条 `factorv3-*` session + `replay` + 509 passed
- 门禁链：`probe` pass、`unit-tests` pass、`black-check` fail（基线 75）、`mypy-check` fail（基线 168）
- 回退点：删除 `scripts/spec_runner_adapter.py` 与 `tests/test_spec_runner_adapter.py`，还原本批文档
- 外部状态：`F:\Spec_Runner` 的 `sessions/` 与自动 commit 为框架设计内行为（源码 L106-L114），不改其源码

### 3.4 本批（P0 台账校正）档位

判定为 **T3 轻批**（Layer-0：仅 `docs/PROGRESS.md` 与 `docs/CHECKLIST_spec_runner_integration.md`；零代码 / 零门禁 / 零真值源）：

- 5 步决策流 session：`factorv3-p0-ledger-fix-20261104`（step-research → step-design → step-implement → step-verify → step-finalize）
- 改动：刷新 HEAD / 测试数 / black 基线；关闭 U-004；CHECKLIST §8 的 E2 升级为 E3 @`df652f9`
- 证据出口：session + `pytest`（509 passed）+ `git rev-parse`（E1）
- 工具替代：本仓无 `Spec_Workflow` 三校验器 / `console_gen`；以 `pytest` + Spec_Runner 5 步 gate 作为等价证据出口
- 回退点：将两文件还原至 `df652f9` 版本

---

## 4. 审查记录

### 4.1 独立 pass（2026-11-04）

- **执行时点**: 正文、`docs/DEVLOG.md`、`CHANGELOG.md`、`docs/SPEC_STANDARD.md` 完稿后单独执行；未与正文同一次写入
- **审查者**: 单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座
- **审查方式**: 重新运行台账中的 E1 命令 + 读回文件核对，不依赖正文自报

**发现 4 项（均已修复）**:

1. §1.1 工作区状态未注明时点，落档后工作区已因本批文档产生修改；已改为“工作区（落档前）”。
2. P-001 将 `core/engine.py` 表述为“公共模块”，删除对象与迁移范围不够精确；已改为“删除 `core/engine.py` 并迁移 `tests/`、`examples/`”。
3. P-006 的 E3 行号证据未绑定 commit hash，不满足 RULE-6 对 E3 的约束；已补 `@1058cbb`。
4. 开发日志源指针使用绝对 Windows 路径的 Markdown 链接，存在断链风险；已改为行内代码。

**复核结果**:

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| HEAD 与分支状态 | `git rev-parse HEAD`、`git branch -vv` | 与 §1.1 一致 |
| V1 引用清单 | `git grep -l "from core\.engine import" -- "*.py"` | 11 个文件命中，其中 `core/__init__.py` 为注释；实际导入 10 个（6 examples + 4 tests） |
| ADR-016 悬空 | `git grep -n "ADR-016"`；`Select-String docs/DECISIONS.md '^## ADR-01[3-6]'` | 代码 3 处引用；DECISIONS 仅 ADR-013 及以前 |
| config_v2 无冻结标注 | `git grep -n "冻结\|frozen\|TD-2" -- core/config_v2.py` | 空输出 |
| 无 DuckDB 依赖 | `git grep -n "import duckdb" -- "*.py"` | 空输出 |
| 测试证据 | 读回两份 pytest 日志并复核 SHA256 | 默认后端 `1 failed, 502 passed`；Agg `503 passed`，哈希一致 |
| black 基线 | `python -m black --check core tests` | `75 files would be reformatted, 4 unchanged`（当时读数；本批复核为 `75/5`，见 §4.4） |

**结论**: 无 P1/P2 阻断项；台账可进入使用状态。残余风险见 §2 U-001~U-003、U-005~U-006（U-004 已于本批关闭）。

### 4.2 独立 pass：搜索锚点 + 方案对比矩阵（2026-11-04）

- **执行时点**: §十一 与 §11.8 正文、阶段模板与 Review 行、三份开发日志完稿后单独执行；未与正文同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 逐条对照外部 `DECISION_MATRIX_TEMPLATE.md` v1.0 L18-L42、L52-L73 与 `SPEC_PROCESS.md` L431-L467（均 @ `bf83e48`），并重新运行 E1 命令

**发现并修复**:

| 批 | 发现 | 修复 |
|----|------|------|
| 搜索锚点（DEV-LOG-002） | 4 项：issue 等级分类、Step 5 工具数量、Step 9 锚点等级、“不懂不要乱写”释义 | 均已回写 §11.3 / §11.4 / §11.5 / §11.7 |
| 方案对比（DEV-LOG-003） | 6 项：维度命名、时间口径缺失、Type-1/2 判定未落规则、证据等级取值域、收敛出口空态、悬空引用 | 均已回写 §11.8.2 / §11.8.3 / §11.8.4，并创建 DEV-LOG-003 |

**复核结果**:

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| 七维与外部模板逐行同构 | 读回模板 L34-L42 与 §11.8.2 | 七行一一对应 |
| 启用判据 / 收敛出口 / 反模式同构 | 模板 L18-L26、L52-L64、L75-L78 | 结构一致；本仓另有增补（时间口径、被拒代价） |
| 阶段接入 | `Grep "11\.8" docs/SPEC_STANDARD.md` | Phase 0 §3、Phase 0/1 Review、Design §2A 四处命中 |
| 外部仓只读 | `git -C F:\Spec_Workflow status --short` | 空输出 |
| 全量回归 | `MPLBACKEND=Agg` + Python312 `pytest tests` | `503 passed`，日志 SHA256 `71F014D4…` |
| 解释器漂移 | `Get-Command python` + pytest 收集日志 | 默认 `python` = Anaconda 3.13.5 缺 `cvxpy`（interrupted 2 errors）；已登记 U-005 |

**结论**: 无 P1/P2 阻断项；本批 done。残余风险见 §2 U-001~U-005。

### 4.3 独立 pass：Spec_Runner 接入（T1，2026-11-04）

- **执行时点**: 四文档、实现、门禁链与回写完成后单独执行；未与实现同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 重跑 E1 命令 + 读回四文档 + 对照官方模板 diff

**8 道 Review 证据点**：

| # | 门 | 证据 |
|---|----|------|
| 1 | Step 2 调研 Review | RESEARCH §6 来源验证表（5 个 T1 + 8 条 E1） |
| 2 | Step 3 设计决策表自检 | DESIGN §8 四项决策 + 被拒代价 |
| 3 | Step 4 设计 Review | DESIGN §9 六项检查 + 2 项修复 |
| 4 | Step 5 实施规划自检 | IMPL §1 任务分解 + §2.5 测试策略 |
| 5 | Step 6 实施 Review | IMPL §3 六项检查 + 2 项修复 |
| 6 | Step 7 验收清单 DoR/DoD | CHECKLIST §1-§7 全项 |
| 7 | Step 8 一致性 Review | CHECKLIST §9 四对文档核对 |
| 8 | Step 9 TDD + Step 10 ADD | CHECKLIST §10 红→绿 + §7 四阶段 |

**发现并修复**：

| ID | 级别 | 发现 | 处理 |
|----|------|------|------|
| F-1 | P3 | black 报告写 stderr，runner 只捕获 stdout，首轮 `stdout_tail` 为空 | 门禁命令追加 `2>&1`；重跑 seq 2 捕获基线 |
| F-2 | P3 | 项目 black 会重排上游模板编排代码，与“配置区以外逐行一致”冲突 | adapter 保持模板原格式；仅新增测试文件 black；偏离记录于 CHECKLIST §6 |
| F-3 | P3 | `mypy core` 在含点目录名下属无效包名 | 使用 `--explicit-package-bases`；基线 168 errors 登记 P-007/U-006 |

**复核结果**：

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| 配置区以外零改动 | `git diff --no-index <模板> scripts\spec_runner_adapter.py` | 仅 `PREFIX` 与 `GATES`（含 `_PY312`）差异 |
| 四门禁 verdict | 4 次 `adapter gate` | pass / pass / fail(1) / fail(1) |
| 事件流可重放 | `adapter replay --session factorv3-probe-20261104`、`...black-check...` | 1 行 OK；2 行 OK |
| 全量回归 | `MPLBACKEND=Agg` + Python312 `pytest tests` | `509 passed, 82 warnings in 20.02s`；日志 SHA256 `D262199F…` |
| 新增文件质量 | `py_compile`、`black --check tests/...` | exit 0；`1 file would be left unchanged` |
| 无残留标记 | `Select-String "TODO\|FIXME"` 两个新文件 | 空输出 |
| 外部执行器状态 | `git -C F:\Spec_Runner log --oneline -6` | 5 条 `factorv3` gate 自动提交（设计内行为）；工作区干净 |

**结论**: 0 个 P1/P2；3 个 P3 已处理；本批 done。残余技术债见 §2 U-006 与 §1.4 P-007。

### 4.4 独立 pass：P0 台账校正（T3，2026-11-04）

- **执行时点**: 文档与视图完稿后单独执行（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 重跑 E1 命令 + 读回 `PROGRESS.md` / `CHECKLIST_spec_runner_integration.md`

**发现并修复（3 项，均已回写）**：

| ID | 发现 | 处理 |
|----|------|------|
| P0-1 | 默认后端不止 1 个 fail，另有 3 个 Tk setup error（strict_validation test_12/13/14） | §1.2 如实记录 `1 failed + 3 errors`，U-001 仍按 Tk 根因 |
| P0-2 | 解释器口径备注仍写“恢复 503 passed” | 改为 509，并指向当前测试表 |
| P0-3 | §1.5 标题仍写“未提交”，与实际 `400394e`/`df652f9` 不符 | 改为“本批新增（2026-11-04）”，逐行补 commit |

**复核结果**：

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| HEAD / origin/master | `git rev-parse HEAD origin/master` | 均为 `df652f9e3595…` |
| Agg 全量回归 | T3 session `step-verify` | `509 passed, 82 warnings in 19.88s` |
| 默认后端读数 | `%TEMP%\pytest_default_backend_p0_20261104.log` | `1 failed, 505 passed, 3 errors`，均 Tk |
| black 基线 | 门禁 session `factorv3-black-check-20261104` seq 2 | `75 files would be reformatted, 5 unchanged` |
| U-004 关闭 | 读回 §2 关闭说明 + `SPEC_STANDARD.md` 头部 | 判据达成 |
| CHECKLIST E3 | `CHECKLIST_spec_runner_integration.md` §8 | `E3 @df652f9` 已落 |
| 5 步 session | `replay --session factorv3-p0-ledger-fix-20261104` | `5 rows OK`，5 个 gate 全 pass |
| 改动范围 | `git status --short` | 仅 4 个文档（PROGRESS/CHECKLIST/DEVLOG/CHANGELOG） |

**结论**: 0 个 P1/P2；T3 证据链完整；本批 done。
