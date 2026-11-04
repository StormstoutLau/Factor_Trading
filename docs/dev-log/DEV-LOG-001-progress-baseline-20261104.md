# DEV-LOG-001: 进度基线落档（2026-11-04）

> **日期**: 2026-11-04
> **类型**: T3 轻批（Layer-0：纯文档；零代码 / 零门禁 / 零真值源变更）
> **涉及**: `docs/PROGRESS.md`（新建）、`docs/dev-log/DEV-LOG-001-progress-baseline-20261104.md`（新建）、`docs/DEVLOG.md`、`CHANGELOG.md`、`docs/SPEC_STANDARD.md`
> **状态**: done（独立复核 pass 已完成，见文末“审查”）
> **规范依据**: `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1
> **源指针**: [PROGRESS](../PROGRESS.md)、`F:\Spec_Workflow\SPEC_PROCESS.md`、[RESEARCH_tech_debt_cleanup](../RESEARCH_tech_debt_cleanup.md)

## 做了什么（时序）

1. **状态采集**：复核 HEAD、分支同步、工作区、V1 引擎引用、`config_v2` 冻结标注、DuckDB 引用、black 基线与测试状态；全部断言附 E1 命令。
2. **落档进度分析**：新建 [PROGRESS.md](../PROGRESS.md)，写入仓库快照、已完成提交、未完成事项（P-001~P-006）、未决项四元块与下一批次启动规则。
3. **登记档位**：按 SPEC_PROCESS v1.7.1 判档——TD-3 Stage 3 / TD-9 / TD-1 / TD-4 为 T1，config_v2 冻结标注与 ADR-016 补录为 T3；本批为 T3。
4. **同步视图**：`docs/DEVLOG.md` 增加本批条目；`CHANGELOG.md` 的 Docs 段增加台账条目；`docs/SPEC_STANDARD.md` 标注外部权威源。
5. **独立复核 pass**：正文完稿后单独执行，核对台账中的 commit、grep、测试日志与文件存在性（结果回写 PROGRESS §4）。

## 决策依据

### ① 为何本批判 T3

改动路径全部为文档（`docs/` 与 `CHANGELOG.md`），不触碰 `scripts/`、`tests/`、`tools/`、`.pre-commit-config.yaml`、`.github/workflows/`；不改变运行时、公开接口、真值源或门禁。符合 T3 定义与裁剪理由要求。

### ② 为何不复制 `SPEC_PROCESS.md` 全文

Spec_Workflow README 的迁移步骤建议复制流程宪法；本仓以外部路径为权威源，避免完整副本与上游版本漂移。代价是路径依赖本机环境，已在 `docs/SPEC_STANDARD.md` 与 `PROGRESS.md` 显式声明。若后续需要脱离本机使用，再按 README 迁移步骤复制。

### ③ 为何不启动 P-001 实现

P-001 判为 T1，须先完成 Step 1-8 四文档与门禁；本批只登记，不进入调研或代码修改。

## 遇到的问题

- **Tk 环境缺陷**：默认 matplotlib 后端调用 Tk 失败（缺 `ttk/xpTheme.tcl`）；`MPLBACKEND=Agg` 下 503 passed。已登记 U-001，倾向统一无头后端或修复 Tk。
- **ADR-016 引用悬空**：三处代码注释引用 ADR-016，但 `docs/DECISIONS.md` 仅 ADR-001~013。已登记 U-002 / P-006。
- **TD-3 Stage 3 清单过期**：调研文档写“5 examples + 3 tests + re-export”，实测 6 examples + 4 tests、无 re-export。已登记 U-003，P-001 Step 1 必须先行更新。
- **项目内规范与外部权威源版本差**：`docs/SPEC_STANDARD.md` v1.0 vs SPEC_PROCESS v1.7.1。已登记 U-004，本批标注外部权威源。

## 下一步

- P-001（TD-3 Stage 3，T1）从 Step 1 调研开始；先更新引用清单与迁移边界，再进入 Step 2 Review。
- P-002（TD-2 冻结标注，T3）可在 P-001 之外独立执行。
- U-001（Tk/MPLBACKEND）优先在 CI 与本地测试命令中固化。

## 证据

| 断言 | 证据 | 等级 |
|------|------|------|
| HEAD = `1058cbbb283f307fe4783f885800765f2c4e8118` | `git rev-parse HEAD` | E1 |
| 工作区干净、分支与本地 `origin/master` 同步 | `git status --short` 空输出、`git branch -vv` | E1 |
| `MPLBACKEND=Agg` 下 503 passed | 日志 `%TEMP%\pytest_agg_progress_20261104.log`，SHA256 `34DC8EBD…` | E1 |
| 默认后端失败为 Tk `xpTheme.tcl` 缺失 | 日志 `%TEMP%\pytest_progress_check.log` 第 99/545/573 行 | E1 |
| V1 实际引用为 10 个文件（6 examples + 4 tests） | `git grep -l "from core\.engine import" -- "*.py"` | E1 |
| `config_v2` 无冻结标注 | `git grep -n "冻结\|frozen\|TD-2" -- core/config_v2.py` 空输出 | E1 |
| 全仓无 `import duckdb` | `git grep -n "import duckdb" -- "*.py"` 空输出 | E1 |
| black 75/79 需重排 | `python -m black --check core tests` | E1 |
| ADR-016 仅在 3 处代码注释出现 | `git grep -n "ADR-016"` | E1；`docs/DECISIONS.md` 标题检索 ADR-001~013 |

## 审查

- **时点**：2026-11-04，正文与视图文件完稿后单独执行（非与正文同一次写入，RULE-1）。
- **审查者**：单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座。
- **发现 4 项并修复**：工作区状态缺时点限定；P-001 删除对象表述不精确；P-006 行号证据未绑 commit；源指针绝对路径链接易断。
- **E1 复跑**：HEAD/分支、V1 引用清单、ADR-016、config_v2 冻结标注、DuckDB、两份 pytest 日志与哈希、black 基线，均与台账一致。
- **结论**：无 P1/P2 阻断项；本批 done。
