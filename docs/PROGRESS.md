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
| HEAD | `1058cbbb283f307fe4783f885800765f2c4e8118` | `git rev-parse HEAD`（E1） |
| 分支同步 | `master` 与本地记录的 `origin/master` 指向同一提交；未执行 `fetch` | `git branch -vv`（E1） |
| 工作区（落档前） | 干净（无已跟踪修改、无未跟踪文件） | `git status --short` 空输出（E1） |

### 1.2 测试状态

| 场景 | 结果 | 证据 |
|------|------|------|
| 默认 matplotlib 后端 | `1 failed, 502 passed, 82 warnings`；失败项 `tests/test_real_ashare_backtest.py::TestRealAshareBacktest::test_09_trades_generated`，根因 `_tkinter.TclError`：本机 Tk 缺少 `ttk/xpTheme.tcl` | 日志 `C:\Users\Peng\AppData\Local\Temp\pytest_progress_check.log` 第 99、545、573 行（E1） |
| `MPLBACKEND=Agg` | `503 passed, 82 warnings in 18.72s` | 日志 `C:\Users\Peng\AppData\Local\Temp\pytest_agg_progress_20261104.log`，SHA256 `34DC8EBD382509ED28E732A094CD4661A6048024A442B12E28BD9C61185A669B`（E1） |

结论：默认后端失败由本机 Tk 安装不完整引起，非代码回归；无头后端下全量通过。

> **解释器口径（2026-11-04 复核）**: 上述基线使用 `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`。当前 shell 的 `python` 解析到 `C:\ProgramData\Anaconda3\python.exe`（3.13.5，缺 `cvxpy`），直接复跑会出现 `collected 483 / 2 errors`；以 Python312 复跑恢复 `503 passed`（日志 `%TEMP%\pytest_agg_devlog003_20261104.log`，SHA256 `71F014D4…`）。见 U-005。

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

### 1.4 未完成事项

| ID | 事项 | 依据（含档位） | 状态 | 优先级 |
|----|------|----------------|------|--------|
| P-001 | TD-3 Stage 3：移除 `core/engine.py` | `docs/RESEARCH_tech_debt_cleanup.md` TD-3；实测 10 个实际导入文件（6 examples + 4 tests），`core/__init__.py` 仅注释提及；**T1**（Layer-1：删除 `core/engine.py` 并迁移 `tests/`、`examples/`） | pending | P2 |
| P-002 | TD-2：`core/config_v2.py` 冻结标注 | `docs/RESEARCH_tech_debt_cleanup.md` TD-2；当前文件无 `冻结/frozen/TD-2` 标注；**T3**（docstring-only，零运行时行为；路径不落在 scripts/tests/tools/workflows） | pending | P2 |
| P-003 | TD-9：black 全量重排 | `docs/RESEARCH_tech_debt_cleanup.md` TD-9；实测 `75 files would be reformatted, 4 unchanged`（black 26.5.0）；**T1**（改动覆盖 `core/` 与 `tests/`，虽 style-only 但属批量重写） | pending | P3 |
| P-004 | TD-1：数据层统一（DataManager → DataLoaderV3 / Provider） | `docs/RESEARCH_tech_debt_cleanup.md` TD-1；两套实现仍并存；**T1**（数据层接口与生产消费方变更） | pending | P3 |
| P-005 | TD-4：Factor_DB 存储迁移 / 文档对齐（DuckDB 为规划方向） | `docs/RESEARCH_tech_debt_cleanup.md` TD-4；全仓仍无 `import duckdb`；**T1**（存储层接口变更） | pending | P3 |
| P-006 | ADR-016 补录或引用修正 | `__init__.py:3@1058cbb`、`core/__init__.py:3@1058cbb`、`pyproject.toml:79@1058cbb` 引用 ADR-016；`docs/DECISIONS.md` 当前仅 ADR-001~013；**T3**（纯文档一致性，零代码） | pending | P3 |

> 状态说明：上表仅有决策态 `pending`（未开工）。开工后执行态由工作记录派生，不在本表手写。

### 1.5 本批新增（2026-11-04，未提交）

| 项目 | 文件 | 档位 | 状态 |
|------|------|------|------|
| Spec 搜索锚点规则增补 | `docs/SPEC_STANDARD.md` §十一；`docs/dev-log/DEV-LOG-002-search-anchor-rules-20261104.md` | T3（Layer-0，纯文档） | done（自查·单视角） |
| 方案对比 7 维矩阵规则增补 | `docs/SPEC_STANDARD.md` §11.8；`docs/dev-log/DEV-LOG-003-comparison-matrix-anchors-20261104.md` | T3（Layer-0，纯文档） | done（自查·单视角） |

---

## 2. 未决项登记（四元块）

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| U-001 | 默认 matplotlib 后端下 `pytest tests/` 全绿 | 每次本地或 CI 测试（未设置 `MPLBACKEND` 时） | 本地与 CI 统一设置 `MPLBACKEND=Agg`；或修复 Python312 的 Tk 组件 | E1 |
| U-002 | `docs/DECISIONS.md` 出现 ADR-016，或三处代码引用改为已登记 ADR | 下次文档一致性更新 / P-006 开工 | 补录 ADR-016（TD-1.2 轻量子包化决策），保留代码引用 | E1 |
| U-003 | TD-3 Stage 3 的调研清单更新为实测值（6 examples + 4 tests，无 `core/__init__.py` re-export） | P-001 Step 1 调研启动 | 在新 RESEARCH 中更新清单后，再进入设计 | E1 |
| U-004 | `docs/SPEC_STANDARD.md` 明确外部权威源，或完成同步 | 本批（2026-11-04） | 保留项目内简版为快速参考，标注 `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1 为冲突时的权威源 | E1 |
| U-005 | 测试命令固定解释器，或各解释器依赖一致（`cvxpy` 可导入） | 每次本地或 CI 测试 | 命令中显式使用 Python312 路径；不默许 `python` 解析到 Anaconda 3.13.5 | E1 |

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
| black 基线 | `python -m black --check core tests` | `75 files would be reformatted, 4 unchanged` |

**结论**: 无 P1/P2 阻断项；台账可进入使用状态。残余风险见 §2 U-001~U-004。

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
