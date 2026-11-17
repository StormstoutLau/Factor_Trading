# PROGRESS 待办登记与进度分析

> **规范依据**: `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1（10 步 Spec 流程 + RULE-1~6 + E1-E5 取证分级 + T1/T3 批次档位）
> **登记日期**: 2026-11-04（**2026-11-10 终态盘点更新**：P-011/P-012 收口后重排待办优先级，见 §1.4 / §3.14⑥）
> **状态词表**: `pending / in-progress / blocked / done`（DC2.1；执行态与决策态同一位点单来源）
> **证据分级**: E1 可重放命令 / E2 运行时脚本 / E3 静态读码（须绑定 commit hash）/ E4 盲区扫描 / E5 推测（禁止用于结论）
> **编号口径**: 本仓 P 编号为独立命名空间，不与 `Spec_Workflow` 的 P 编号复用

---

## 1. 当前进度快照（2026-11-10 终态盘点）

### 1.1 仓库状态

| 项 | 值 | 证据 |
|----|----|------|
| HEAD（代码+基线终态） | `6ad7678`（P-014 基线元数据重录；后续为纯文档提交） | `git rev-parse HEAD`（E1，2026-11-10 更新） |
| 分支同步 | `master` 与 `origin/master` 指向同一提交（`6ad7678`）；远端 SSH；CI run `42791704254` 三 job success | `git rev-parse HEAD origin/master`（E1） |
| 工作区（本批开始前） | 干净（无已跟踪修改、无未跟踪文件） | `git status --short` 空输出（E1） |

### 1.2 测试状态

> **2026-11-10 终态基线（P-014 收口实测）**: `635 passed` / black 172 unchanged / mypy 0（36 files）/ 盲区 4 errors 2 files / **71 测试文件**（`tests/*.py` 74 = 71 测试 + 3 辅助）/ **golden 7 条** / 远端 CI run `42791704254` 三版本（3.10/3.11/3.12）各 `628 passed, 1 skipped`（= 本地 635 − 7 项 numba `importorskip`）；P-013 收口时为 `626 passed` / 70 文件 / CI `619 passed, 1 skipped`；P-011 收口时为 `609 passed` / 68 文件。U-001/U-005 已由 P-008/P-009 关闭，下表为 P-0 时代历史快照存档。

| 场景 | 结果 | 证据 |
|------|------|------|
| 默认 matplotlib 后端 | `1 failed, 505 passed, 3 errors, 82 warnings in 19.19s`；失败项 `test_real_ashare_backtest.py::TestRealAshareBacktest::test_08_portfolio_value_positive`；3 个 error 为 `test_real_ashare_strict_validation.py` 的 setup（test_12/13/14）；根因均为 `_tkinter.TclError: Can't find a usable tk.tcl`（Tcl 报错原文；相关 `.tcl` 文件实际存在，根因未完全定位，见 [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md) §1.1） | 日志 `%TEMP%\pytest_default_backend_p0_20261104.log` 第 59、134、206、320、766、794-887 行（E1） |
| `MPLBACKEND=Agg` | `509 passed, 82 warnings in 20.02s` | 日志 `%TEMP%\pytest_agg_sr_integration_final_20261104.log`，SHA256 `D262199F55DC7D2E2AD85D5D1868CB1221F0FFFE96B3E8A57B8369311DC57707`（E1） |

结论：默认后端失败/错误由 matplotlib 自动选择 TkAgg 初始化失败触发（触发链见 [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md) §1.1），非代码回归；无头后端下 509 全通过（= 503 基线 + 6 项 adapter 测试）。

> **U-001 复测（2026-11-04，P-008 调研）**: 默认后端 `1 failed, 508 passed, 0 errors`（失败项漂移，单独运行通过）；触发链已定位到 `analytics.generate_report → plt.figure → _backend_tk → tk.Tk`，但根因未完全定位；详见 [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md) §1.1。

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
| P-012 偏差防护与接口锁定（观测网/ST 规则表/复权三口径/掩码/退市动态池/接口治理，七批实施） | `a5ae5cc..a17ebce`（15 提交） | done（2026-11-10） |
| P-011 回测准确性验证（不变量/参考差分/口径统一/偏差声明/manifest/trace，六批实施 + 审计 + RULE-5 异构复审） | `cd6d619..6f583fc`（17 提交） | done（2026-11-10） |

### 1.4 未完成事项

| ID | 事项 | 依据（含档位） | 状态 | 优先级 |
|----|------|----------------|------|--------|
| P-001 | TD-3 Stage 3：移除 `core/engine.py` | `docs/RESEARCH_tech_debt_cleanup.md` TD-3；实测 10 个实际导入文件（6 examples + 4 tests），`core/__init__.py` 仅注释提及；**T1**（Layer-1：删除 `core/engine.py` 并迁移 `tests/`、`examples/`） | done（2026-11-09，Step 1-10 全通过；本地 `507 passed`、black 72 / mypy 119 新基线；`ccd0c98`；远端 CI run `42598775895` 三版本 `500 passed, 1 skipped`） | P2 |
| P-002 | TD-2：`core/config_v2.py` 冻结标注 | `docs/RESEARCH_tech_debt_cleanup.md` TD-2；当前文件无 `冻结/frozen/TD-2` 标注；**T3**（docstring-only，零运行时行为；路径不落在 scripts/tests/tools/workflows） | done（2026-11-09，T3 轻批：module docstring 落地 ⚠️ FROZEN/TD-2 冻结声明 + 冻结期间约束 + 再激活条件，口径对齐 ARCHITECTURE「⚠️ 冻结（零生产引用）」；`py_compile` exit 0，全量 507 passed，零代码行变更） | P2 |
| P-003 | TD-9：black 全量重排 | `docs/RESEARCH_tech_debt_cleanup.md` TD-9；实测 `75 files would be reformatted, 5 unchanged`（black 26.5.0；2026-11-04 复核，新增测试已格式化）；**T1**（改动覆盖 `core/` 与 `tests/`，虽 style-only 但属批量重写） | done（2026-11-09，Step 1-10 全通过；**126 文件重排**、`black~=26.0` 锁定、门禁扩展 `black --check .` 并首转绿、`.git-blame-ignore-revs` 落地；全量 `507 passed`、AST 125/125 等价、mypy 119 无劣化；提交 `4098629` + `17fc69d`；远端 CI run `42609336249` 三版本 `500 passed, 1 skipped`） | P3 |
| P-004 | TD-1：数据层统一（DataManager → DataLoaderV3 / Provider；消费方迁移 + 旧实现删除，边界见 P-012 U-9 B-A） | `docs/RESEARCH_tech_debt_cleanup.md` TD-1；两套实现仍并存；**硬前置已满足**——P-012 B6 已落地 `DataProvider` 端口 + `PklDataProvider` + 契约测试（零接线），Protocol 先定型约束解除；数据层自 P-010（安全默认值）/P-012（复权三口径、掩码时点、退市动态池）连续叠加变更，双轨维护面扩大；**T1**（数据层接口与生产消费方变更） | **done（2026-11-11，Step 1-10 全通过）**：B1 端口注入 `3ddc895` / B2 死 API 删除 `8b72145` / B3 协议对齐 `bb50009` + 回写 `4d1a47b`；终态 **`636 passed`**（B1 635 持平 / B2 634 / B3 636，F5 红绿三批入档）/ black 110 / mypy 36 files 0 / 死 API grep 0 命中 / V8 外部对拍 28 断言 + 1 豁免 exit 0 / golden G1-G7 数值不变；复审两轮 pass（调研 0 P2 / 设计 1 P2 cfg-falsy 守卫已修）；Step 8 一致性 2 P3 + Step 9 P3 计数更正 + ADD E4 2 观察均登记；CI run `43001831287` / `43005785446` / `43006124986` 三 job success；四文档 [RESEARCH](RESEARCH_p004_data_layer_unification.md) / [DESIGN](DESIGN_p004_data_layer_unification.md) / [IMPL](IMPL_p004_data_layer_unification.md) / [CHECKLIST](CHECKLIST_p004_data_layer_unification.md) | **P2** |
| P-005 | TD-4：Factor_DB 存储迁移 / 文档对齐（DuckDB 为规划方向） | `docs/RESEARCH_tech_debt_cleanup.md` TD-4；2026-11-10 复核代码仍零 `import duckdb`（仅 docs 提及）；**宜排 P-004 之后**——接口未统一前迁移会波及两套实现；无外部触发 | **done（2026-11-11，Step 1-10 全通过）**：B1 文档对齐 `938f413`（README 架构图 3 token + Factor_DB 章节整节重写 + Requirements；web Overview；ARCHITECTURE 依赖表删行补注）/ B2 依赖与 CLI `fb94280`（`pyproject` 去 `duckdb>=0.10.0`、`cli info` 去 duckdb）/ B3 `uv.lock` −44（Step 10 P2 补丁）；四表面 `Grep -i duckdb` **6 → 0**、`info` 无 duckdb、deps **26 → 25**；终态 **`636 passed`** / black 111 / mypy 36 files 0；Step 8 1 P3 + Step 9 3 P3 + Step 10 P2×1/P3×1/E4 3 观察均登记；CI run `43012172205` 三 job success；不迁移决策登记 U-P005-1（新增 U-P005-5 锁漂移）；四文档 [RESEARCH](RESEARCH_p005_factor_db_alignment.md) / [DESIGN](DESIGN_p005_factor_db_alignment.md) / [IMPL](IMPL_p005_factor_db_alignment.md) / [CHECKLIST](CHECKLIST_p005_factor_db_alignment.md) | P3 |
| **P-020** | **文档一致性收尾（P-005 复审残留 + 计数漂移）** | P-005 RULE-5 §9.5 **F-R5-P005-2**（`ARCHITECTURE.md` L66-68 `Price数据/Macro/News/Alternative` 与 `database.py` 能力不符）+ E4 观察 1/2（README 4 处 `507`、ARCHITECTURE L3 `489` vs 实测 636；README L196 裸 ID）；**T3**（Layer-0 纯文档订正，零代码 / 零门禁） | **done（2026-11-11，T3 轻批）**：ARCHITECTURE 三 token → `Metadata/Lineage/Stats`（列宽 14 不变）+ L3/L269 测试数 → 636；README badge / L98 / L263 / L412 → 636（71 files）+ L196 补 U-P005-1 链接 + L441 移除不存在的 `CONTRIBUTING.md` 链接；PROGRESS 补登 U-P005-1/2/4/5；`636 passed` / black 111 / mypy 0 / 链接 0 broken；CI run `43019737462` 三 job success；执行记录 §3.24 | P3 |
| **P-021** | **依赖与锁维护（U-P005-4 / U-P005-5）** | P-005 RULE-5 E4 观察 2（`uv lock --check` 失败——锁根包 `provides-extras` 缺 `web`）+ U-P005-5；U-P005-4（`pyarrow`/`fastparquet` 是否显式声明）；**T1**（`uv.lock` 真值面，判档规则 2 保守升级） | **done（2026-11-12，Step 1-10 全通过）**：B1 `2245962`（plain `uv lock` `+1207/−2`：extras `["dev","web"]`、新增 19 包、既有 pin changed 0 / duckdb 0、修正旧锁 black specifier `>=23.0.0→~=26.0`）/ B2 `6c4adb5`（`ARCHITECTURE` §9.2 三行真值 + 三条锁纪律）/ B3 docs；`uv lock --check` **1 → 0**、`uv export --frozen` exit 0（325 行）；**636 passed** / black 111 / mypy 36 files 0；`pyproject.toml` 零改动；U-P005-4 结案（不显式声明，文档写明前提 + CSV 回退）/ U-P005-5 结案（实测 `+1207/−2`，原估 −46 偏差已注）；**RULE-5 异构复审 pass**（GLM-5.3-Flash ≠ 作者，E1-E4 重放全复现；0 P1/P2，4 P3 回写 + 2 观察）；CI run `43167039277` + 回填 `43167328785` 三 job success；四文档 [RESEARCH](RESEARCH_p021_dependency_lock_maintenance.md) / [DESIGN](DESIGN_p021_dependency_lock_maintenance.md) / [IMPL](IMPL_p021_dependency_lock_maintenance.md) / [CHECKLIST](CHECKLIST_p021_dependency_lock_maintenance.md) | P3 |
| **P-022** | **Factor_DB 四项实现缺陷（U-P005-2）** | P-005 P7 静态读码四项；本批 Step 1 探针全部复现，且**缺陷③升级为确定性崩溃（P1）**：重开数据库后 `add_factor`/`update_stats`/双因子 `delete_factor` 均 `AttributeError`；缺陷①静默覆盖、②删除复活为数据完整性（P2）；④双份存储（P3）；**T1**（`factor_library/` 行为变更 + 4 组红绿测试） | **done（2026-11-12，Step 1-10 全通过）**：B1 `9c50bcd`（加载期 datetime 解析）/ B2 `ec21dc5`（覆盖守卫 = metadata ∪ 内存 ∪ 两种文件）/ B3 `9ffbfde`（删除同时清 parquet+csv）/ B4 `1550e63`（写入后单一格式）/ B4b `59e1273`（black）；逐批红 4/2/2/2 → 绿 11；**647 passed**（636+11，44.46s）/ black 112 unchanged / mypy 36 files 0；7 个公开方法与 `FactorMetadata` 字段 AST **完全相等**；`batch_backtest`/`pyproject` 零改动；ADD P3×1 已记录 + U-P022-4 登记；CI run `43176076114` 三 job success + 回填 run `43176435214` success；RULE-5 **pass**（GLM-5.3-Flash 异构复审，E1-E4 重放 + F-R5-P022-1 回写）；四文档 [RESEARCH](RESEARCH_p022_factor_db_defects.md) / [DESIGN](DESIGN_p022_factor_db_defects.md) / [IMPL](IMPL_p022_factor_db_defects.md) / [CHECKLIST](CHECKLIST_p022_factor_db_defects.md) | **P1** |
| **P-023** | **质量护栏（F-A1 静默空回测 + U-006-R mypy 盲区）** | U-006-R（`mypy --check-untyped-defs core` 残差 4 errors 2 files）+ F-A1（注入式工作流未注入信号 → 静默空回测，权威源 [P-007 CHECKLIST §9.3](CHECKLIST_p007_mypy_layerb.md)）；**T1**（`core/` 行为变更 + 盲区清零） | **done（2026-11-12，Step 1-10 全通过）**：B1 `run()` 信号未就绪 fail-fast（`RuntimeError`）/ B2 `_generate_results()` 零快照 fail-fast / B3 U-006-R 四项窄化（`data_v3._build_maps` 别名+assert、`engine_v2` L224 `cast(DataManager, ...)`、L293 别名+assert）；提交 `a5b95bb`（3 文件 +222/−5）；逐批红 **1 failed 1 passed** → 绿 2 passed、红 **1 failed 3 passed** → 绿 4 passed、盲区 **4 errors → 0**；**651 passed**（647+4）/ black 113 unchanged / mypy 门禁 36 files 0 / 注入式 27 passed；探针复跑 A/C/E 三场景全部由「静默 OK」转抛 `RuntimeError`；CI run `43187514724` 三 job success；四文档 [RESEARCH](RESEARCH_p023_quality_guardrails.md) / [DESIGN](DESIGN_p023_quality_guardrails.md) / [IMPL](IMPL_p023_quality_guardrails.md) / [CHECKLIST](CHECKLIST_p023_quality_guardrails.md) | **P1** |
| **P-024** | **CI 门禁对齐（mypy 假门禁 + README uv extras）** | U-006（口径收紧待重评，Q4=B）+ U-P023-2（`--check-untyped-defs` 是否入门禁）+ U-P023-4（v3 信号路径取证）；Step 1 取证：`tests.yml` L46 的 `\|\| true` 自初版 `c7a0f29` 即存在 → **恒吞退出码（假门禁，P1）**；CI 参数在本地 exit 2（目录名含点号，**双口径不可互换**，P2）；README `uv sync` 缺 extras（P3）；**T1**（Layer-1：`.github/workflows/` + 门禁口径，判档规则 1 + 2） | **done（2026-11-12，Step 1-10 全通过）**：B1 `tests.yml` L46 → `python -m mypy --explicit-package-bases --check-untyped-defs core`（去 `\|\| true` / 去冗余旗标）+ adapter L67 同步 + 守卫测试 3 断言 / B2 README `uv sync --all-extras` / B3 台账七行补登 + §3.28；F5 先红 **exit 1**（`Incompatible types in assignment`）→ `\|\| true` 对照 **exit 0** → 后绿 exit 0；**654 passed**（651+3）/ black 180 / mypy 双口径 36 files 0 / `uv lock --check` exit 0 / `mypy.*\|\| true` grep **0**；**Step 9 追加**：CI 首跑 run `43193963200` 报 `filter/*` **21 errors / 7 files**（根因 **pandas 3.1.1 类型桩**，非 mypy 版本；首轮「版本漂移」判定已证伪撤回）→ `[[tool.mypy.overrides]] filter.* ignore_errors` 声明越界（+8 行，`mypy>=1.5.0` 维持）；CI run [`43196177149`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43196177149) 三 job success；**U-006 / U-P023-2 / U-P023-4 关闭**；**RULE-5 异构复审 pass**（GLM-5.3-Flash ≠ 作者，E1 九项重放 / E2 六组红绿归因 / E3 独立脚本 49 链接 0 broken / E4 盲区扫描；**F-R5-P024-1（P3，测试计数漂移 README 4 + ARCHITECTURE 2 处 636/71 → 654/74）已回写修复** + 2 观察；详见 [CHECKLIST_p024 §11](CHECKLIST_p024_ci_gate_alignment.md)）；四文档 [RESEARCH](RESEARCH_p024_ci_gate_alignment.md) / [DESIGN](DESIGN_p024_ci_gate_alignment.md) / [IMPL](IMPL_p024_ci_gate_alignment.md) / [CHECKLIST](CHECKLIST_p024_ci_gate_alignment.md) | **P1** |
| **P-025** | **日循环异常分类与 retry 语义（U-P023-1）** | U-P023-1；Step 1 取证将触发条件由「事故驱动」改判为**已成立**：`min_variance` + `cov_lookback=60`（20 交易日）→ **0 成交 / `sharpe=0.0` / 零诊断字段**（探针 B2，零代码缺陷、纯配置），与 P-023 F-A1 同级假成功；**T1**（`core/engine_v2.py` + `core/execution.py` 行为契约 + 结果字典新增键） | **done（2026-11-13，Step 1-10 完成；ADD 审计通过（P1/P2=0，P3×3：2 修 1 登记 + 3 观察）；**RULE-5 异构复审 pass**（GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash，E1 9/9 + E2 红绿闭环 + E3 锚点全命中 + E4 2 P3 已修 + 3 观察，详见 [CHECKLIST_p025 §13](CHECKLIST_p025_daily_loop_exception_semantics.md)）**：七探针 A/A2/A3/B/B2/C/D 取证——日循环吞没（A2：20 条快照仅 19 个不同日期 + 末日重复）、优化失败双重静默（B）、执行异常隐式重试无计量（C）、`additional_info` 10 键零诊断位（D）；负向发现 P14（`load_factor` PIT 对齐已排除「因子缺日」路径）；方案矩阵 5 案选 **M-A**（`day_error_mode: off\|report\|raise` + 统一采集器 + `run_diagnostics`）；锚点 PEP 654 / AWS Builders retries / SRE golden signals；未决 U-P025-1~5；四批切分 B1-B4；**Step 2 Review pass**（异构 GLM-5.3-Flash vs 作者 DeepSeek-V4.1-Flash：四探针独立重跑全复现 / 门禁四项全过 / 0 P1/P2，**2 P3 回写**（F-S2-P025-1 retry_count 第三处自增 + F-S2-P025-2 锚点维度映射）+ 2 观察（末日重复快照为既有行为不得顺带修复 / setup 期预检候选），详见 [RESEARCH_p025 §10](RESEARCH_p025_daily_loop_exception_semantics.md)）；**Step 3 DESIGN 完稿**（D1-D7 / I1-I7 / V1-V12 / 10 项测试规格 / 四批切分；**B3 新增 F-D3-P025-1（P2）**：`build_optimizer` 用 `mvo` 而 CLI 提供 `mean_variance` → 静默降级等权，探针实测与 `equal_weight` 读数完全相同（64 笔 / sharpe −1.4611），已纳入 D6 别名 + fail-closed；D7 裁决 O1 末日重复快照不动、O2 纳入 setup 预检；新增 U-P025-6），详见 [DESIGN_p025](DESIGN_p025_daily_loop_exception_semantics.md)；**Step 4 独立 Review pass**（异构 GLM-5.3-Flash vs 作者 DeepSeek-V4.1-Flash：探针 d1 独立复现 F-D3-P025-1 读数逐字一致 / 13 项机械复核全过（含双表对照、D6 测试破坏面、4 处链接复检）/ 门禁四项全过 / 0 P1/P2，**7 P3 回写**——F-S4-P025-1 I7 快照数 22→21、F-S4-P025-2 stage 枚举补 day_loop/execution、F-S4-P025-3 D2 success=False 缩范围裁决、F-S4-P025-4 R5 计数口径（ARCHITECTURE 28 vs 实查 36）、F-S4-P025-5 factory L167 第二调用点、F-S4-P025-6 raise 语义裁决「首错即抛」、F-S4-P025-7 I5 措辞；4 观察（2 回写 / 2 登记：mvo 双表残余、D7-O2 必要非充分）），详见 [DESIGN_p025 §10](DESIGN_p025_daily_loop_exception_semantics.md)；**Step 5 IMPL 完稿**（T-1..T-6 六任务对应 B1-B4 四批 / 接口签名与回退点 12 项 / 低效排除表 9 项（正常路径零新增指令）/ fixture 表 7 项（独立复制不改 `test_rebalance_exits`）/ 10 项测试规格落位 V1-V12 映射；**IMPL 期裁决 5 项**：F-S5-P025-1 `data` 判定须纳入 `day_loop`（settle/pending/next_day/mark 本批不插桩）、F-S5-P025-2 `record_failure` 实现但不接线、F-S5-P025-3 `run_diagnostics` 键恒存在（off 时 `{"mode":"off"}`，保 I1/V8 成立）、F-S5-P025-4 `interfaces.py` 不加 sink 抽象方法（走 `hasattr`，否则全 fake 执行器 TypeError）、F-S5-P025-5 `ExceptionGroup` 经 `getattr(builtins,…)` 规避 mypy `python_version=3.10` name-defined；另自查修正 T5-T7 单日注入（每日全抛会撞 P-023 空快照守卫）），详见 [IMPL_p025](IMPL_p025_daily_loop_exception_semantics.md)；**Step 6 Review 通过**（实施文档幻觉抑制：11 项检查表全过（任务-设计映射 / I1-I7 落点 / 零新增依赖 / stdlib 3.10 下限 / 签名可实现 / 红态可观测 / 11 组行号引用实查命中）；**1 P2 + 3 P3 回写**——F-S6-P025-1（P2）sink 注解 `Callable[...,None]` 与 record 返回值 mypy 不兼容 + hasattr 直调 Protocol 属性 → 注解 object 化 + getattr 探测（V10/CI 门禁必红项，已闭环）、F-S6-P025-2 raise/degraded 判定基于截断后 samples → `_category_counts` 计数器、F-S6-P025-3 DESIGN D4 代码形态补回 logger.error（回写 DESIGN）、F-S6-P025-4 T7 在 3.10 收集期 NameError → 版本分支断言；3 观察（T8 fixture 非全零收益 / record_failure 无测试维持裁决 / 导入行零改动）；IMPL §10 开放点 3 项全关），详见 [IMPL_p025 §11](IMPL_p025_daily_loop_exception_semantics.md)；**Step 7 CHECKLIST 完稿**（六组 **42 项**零预填（A 采集器 7 / B 引擎主线 6 / C 内层接线+D6/D7 6 / D 不变式 8 / E 测试门禁 9 / F 治理 6），每项 DoR/DoD + 证据出口，实测列 42 处全为 `[待 Step 9]`（RULE-1 零 ✅ 预填）；**Step 7 实测门禁基线**：pytest **654** / mypy **36 files 0** / `black --check core tests cli.py` **114** / `black --check .` **180** → 目标 664 / 37 / 116 / 182；登记 Step 8 待办 2 项（IMPL §1「black +1」实为 **+2**、`black --check core tests cli.py` 基线 113→**114**；IMPL §8 V10「不变」应为 182）），详见 [CHECKLIST_p025](CHECKLIST_p025_daily_loop_exception_semantics.md)；**Step 8 一致性 Review 通过**（机械脚本五项：链接 0 broken（2 处代码块伪命中人工判定）/ ID 闭环 **17 组**全连续 / 计数 42 与声称一致 / 零预填合规（46 处 `[待 Step 9]` = 42 验收 + 4 合法字面引用）/ 角色引用终端文档标准形态；对齐矩阵 9 行全一致（RESEARCH→DESIGN / V/I/R 三表 → CHECKLIST 全落点无遗留）；**2 P3 回写 IMPL**——F-S8-P025-1 `black --check` 文件数「+1」实为 **+2**（基线 114/180 → 目标 116/182）、F-S8-P025-2 IMPL §8 V10 补目标读数 182；3 观察），详见 [CHECKLIST_p025 §10](CHECKLIST_p025_daily_loop_exception_semantics.md)；**Step 9 TDD 实施完成**（五批红绿逐批取证：B1 `ModuleNotFoundError` → 4 函数绿 / B2 `2×KeyError: run_diagnostics` + `DID NOT RAISE` → 绿 / B3a `degraded False` → 绿 / B3b `mean_variance→EqualWeightOptimizer`（F-D3-P025-1 复现）→ 绿 / B3c `DID NOT RAISE` → 绿；**代码变更**：`core/diagnostics.py` 新增（≈200 行，含 `_category_counts` 对截断免疫）+ config 1 行 + engine_v2 4 处（采集器/run catch/优化 catch/setup sink+预检）+ execution 3 处 + portfolio D6；**门禁终态**：pytest **671 passed**（654+17）/ mypy **37 files 0** / black **116 + 182** unchanged / golden **13 passed 零重录**；**探针复跑**：A2 20 快照·19 去重日·day_loop=1（与 HEAD 逐字一致）/ B2 setup 抛「必然失败」/ C execution=6·恢复后成交 4 笔 / A3 21 快照·20 去重日（I7 未顺带修复）；**AST 校验**：`execute_order` 与 `__init__` 签名一致；**零改动面 diff 空**；**I1** report/off 双跑键差均 `{run_diagnostics}` 共 11 键；**CI run [`43260476319`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43260476319) 三 job success**（3.10 / 3.11 / 3.12——3.10 leg 覆盖 `ExceptionGroup` 缺失分支）），详见 [CHECKLIST_p025 §11](CHECKLIST_p025_daily_loop_exception_semantics.md)；**Step 10 ADD 审计通过**（基线 `43cfa36..e199acc` 13 文件 **+903/−23**；**Phase 0-4**：D1-D7 全可机械核验 / 7/7 落地（锚点行号逐一命中）/ 忠实度无静默偏离（唯一偏离 T9 合并已登记）/ +903 行归属清晰 0 行无依据 / 语义达成「假成功→明确失败」且未换成另一静默；**取证矩阵 E1-E5**：pytest 671+17+13+12、mypy 37 files 0、black 116+182、保护面空与 golden 零重录、探针 A2/B2/C/A3 逐字一致、AST 签名一致、盲区扫描 **3 P3（F-S10-P025-1 测试夹具死参数 `n_days` 已删 / F-S10-P025-2 F3 项数 3→4 与 CHANGELOG 对齐 / F-S10-P025-3 `STAGES` 词表常量登记）+ 3 观察**（run 二次调用累积 / execution L239 except 未接入属正确 / 探针脚本在 %TEMP%）），详见 [CHECKLIST_p025 §12](CHECKLIST_p025_daily_loop_exception_semantics.md) | **P1** |
| **P-026** | **静默失败治理第二批（U-P025-3 承接）** | U-P025-3 触发条件实证成立（Step 1 读码：22 处待评估 `except Exception` 中三处 P2 静默面——factor 去常数列零日志 / Guard fail-open 零计量 / WF `set_period` 仅 warning）；**T1**（`core/` 行为契约 + 新增可观测字段与方法，零 fail-fast） | **done（2026-11-13，Step 1-10 全通过）**：M-A 案四批实施（B1-B4t：8 core **+100/−10** + 新测试 422 行 16 items）；45/45 验收回填（红态 **14F/2P** → 绿态 **16P**；全量 **687 passed, 172 warnings** / mypy **37 files 0** / black **116** / golden 9 零重录）；Step 9 修复 **F-S9-P026-1（P2）** statsmodels 0.15 `verbose` 兼容（+1/−1，CI run `43386673276` / `43387091175` 三 job success）；**Step 10 ADD 审计 A+**（0 P0/P1/P2 + 2 观察，[CHECKLIST §13](CHECKLIST_p026_silent_exception_governance.md)）；四文档 [RESEARCH](RESEARCH_p026_silent_exception_governance.md) / [DESIGN](DESIGN_p026_silent_exception_governance.md) / [IMPL](IMPL_p026_silent_exception_governance.md) / [CHECKLIST](CHECKLIST_p026_silent_exception_governance.md) | **P2** |
| **P-027** | **静默失败治理第三批（core 外 22 处 · U-P026-3 承接）** | U-P026-3；**Step 1 取证触发成立**：22 处分类 **A 2 / B 14 / C 2 / E 4**，其中 C 类（`agents/assumption_monitor.py:201` 静默 `(0.0, 1.0)`、`strategy_evaluation/stats.py:139` 静默 `nan`）经 E2 探针复现（注入异常 → 返回默认值 + **0 条日志**）；**U-P024-4 撤销合并**（环境 pandas 2.2.3，`mypy --explicit-package-bases filter` = 10 files 0 error，触发条件不成立）；**Step 2 Review pass**（异构 GLM-5.3-Flash：E1/E2/E4 全复现 + 16 处分类全量读码零错误，0 P1-P3 + 2 观察 O-S2-P027-1/2）；**Step 3 DESIGN 完成**（[DESIGN_p027](DESIGN_p027_silent_exception_governance_phase3.md)：16 处计量 + 6 处零改动 = 22；D1 `BaseFilter` 载体下行 / D2 agents 实例计数 + `:1074` debug→warning / D3 C 类补日志+计量 / D4 5 出口追加 `failure_counts` + 5 新只读方法 / D5 E+A 零改动 / D6 三个批量入口清零 / D7 文案与异常约定）；**T1**（`agents/` / `filter/` / `scripts/` / `batch_backtest/` / `strategy_evaluation/` / `cli.py`，零 fail-fast、零返回值语义变更） | **done（2026-11-16，Step 1-10 完成 + RULE-5 异构终审 pass，批次关闭）**：[RESEARCH_p027](RESEARCH_p027_silent_exception_governance_phase3.md)（§10 复审记录）+ [DESIGN_p027](DESIGN_p027_silent_exception_governance_phase3.md)（§11 复审记录）+ [IMPL_p027](IMPL_p027_silent_exception_governance_phase3.md)（§4 精确变更规格 + §10 复审记录 + §11 Step 9 实施记录）+ [CHECKLIST_p027](CHECKLIST_p027_silent_exception_governance_phase3.md)（**44 项全 ✅**，§10 一致性 Review pass + §11 Step 9 记录）；**Step 9 TDD 三批**：B1 `b3f6b5e` / B2 `6259e42` / B3 `7dfe755`（红态 5F → 15F+5P → 2F，绿态 **24 passed**）；门禁 **711 passed** / mypy **37 files 0 error** / black **117 unchanged** / golden 零重录 / `except Exception` 合计 **22**；CI run `43774985791` 三 job success；**Step 10 ADD 自审 pass**（0 P0/P1/P2 + 1 P3 + 3 观察，[CHECKLIST §12](CHECKLIST_p027_silent_exception_governance_phase3.md)）；**RULE-5 异构终审 pass**（GLM-5.3-Flash 异构基座，E1-E4 全量重放一致 + 两项预留复核维持原裁定 + 1 P3 当轮修正，[CHECKLIST §13](CHECKLIST_p027_silent_exception_governance_phase3.md)）——**批次关闭** | **P2** |
| **P-028** | **台账去重（U-P021-1 → U-P024-2 / U-P024-1 实测注记）** | 2026-11-16 待办分析：U-P021-1 与 U-P024-2 为同一事项（CI 增加 `uv lock --check` 门禁），U-P024-2 原已注明「与 U-P021-1 同源」——双跟踪源会在触发时导致重复立项；**T3**（纯文档，零代码 / 零测试 / 零门禁变更） | **done（2026-11-16，T3 轻批）**：① U-P021-1 → 「已合并」指针（保留历史与 RESEARCH_p021 锚点，不删行）；② U-P024-2 升为**单一跟踪源**，触发条件并入「引入 uv 安装路径」；③ U-P024-1 追加实测注记（mypy **2.1.0** / pandas **2.2.3** / numba 已装未声明）；④ RESEARCH_p021 §6 + RESEARCH_p024 §6 各补 1 行交叉引用；门禁持平 **711 passed** / mypy **37 files 0** / black **117 unchanged**（详见 §3.33） | P3 |
| **P-029** | **静默失败治理第四批（`agents/` 9 处 · U-P027-1 承接）** | U-P027-1（[CHECKLIST_p027 §12.6](CHECKLIST_p027_silent_exception_governance_phase3.md) E4 扫描 8 项：`agent_framework.py` S1-S4 / `multi_strategy_engine.py` S5-S7 / `strategy_allocator.py` S8）；**Step 1 取证**：8 处 E2 全部复现（0 日志 + 0 计量 + 不抛出），分类 **B 7 + 待裁决 1（S8）+ 观察 1（S3b）**；**T1**（`agents/` 3 文件；零 fail-fast、零返回值语义变更、零既有文案改写） | **done（2026-11-16，Step 1-10 完成 + RULE-5 异构终审 pass，批次关闭）**：[RESEARCH_p029](RESEARCH_p029_silent_exception_governance_phase4.md)（§3 八处 + §11 Step 2 复审）+ [DESIGN_p029](DESIGN_p029_silent_exception_governance_phase4.md)（D1-D7 / I1-I8 / §11 Step 4 复审）+ [IMPL_p029](IMPL_p029_silent_exception_governance_phase4.md)（§4 逐锚点规格 / §5 测试 / §10 Step 6 复审 / §11 Step 9 记录）+ [CHECKLIST_p029](CHECKLIST_p029_silent_exception_governance_phase4.md)（**38 项全 ✅**，§10 Step 8 一致性 Review + §11 Step 10 审计）；**Step 9 TDD 三批**：B1 `e86b09d` / B2 `7cf6718` / B3 `58954bd`（红态 5F → 3F+6P → 2F+9P，绿态 **11 passed**）；**口径**：9 计量 / 3 文件 / 0 新增日志 / 0 新增 raise / 0 捕获类型变更；**门禁**：**722 passed** / 测试文件 **81** / black **118** / mypy **37 files 0** / golden **13 零重录** / `except Exception` 恒 **22** / I2=0 / I5 零删改 / I6=0；变更面 3 代码 + 1 测试（+7/−5、+3/−0、+10/−0）；CI run `43824569283` + B4 文档 `43825106609` 三 job success；**Step 10 ADD 审计 + RULE-5 异构终审 pass**（GLM-5.3-Flash ≠ 四文档作者 DeepSeek-V4.1-Flash，审计与终审合并一轮；Phase 0 质量门 5/5 Tier A + E1-E5 门禁独立复跑全绿 + 盲区扫描 silent **9 → 1** + **0 P0-P2 + 1 P3 当轮修正 F-R5-P029-1** + 2 观察，见 [CHECKLIST_p029 §11](CHECKLIST_p029_silent_exception_governance_phase4.md)）——**批次关闭**；U-P029-2（S6/S7 队列重试语义）**2026-11-16 转入 P-031** | **P3** |
| **P-030** | **台账收口（P-029 关闭后遗留两项）** | P-029 收口后发现：① U-P027-1 仍标 `in-progress`（实际已由 P-029 完成）；② U-P029-2 未在 §1.4 建行、只散落在正文，会漏跟踪；**T3**（纯文档，零代码 / 零测试 / 零门禁） | **done（2026-11-16，T3 轻批）**：① U-P027-1 → **done**（P-029 承接：9 计量 / silent 9→1 / 终审 99/A）；② 新增 **U-P029-2** 行（pending P3，`StrategyEngine` 次日订单簿时序语义）；③ §3.34.9 补总结报告 `83a27aa` → CI `43832206129`；④ CHANGELOG 追加本批条目；门禁持平 **722 passed** / mypy **37 files 0** / black **118 unchanged**（详见 §3.35） | P3 |
| **P-031** | **`StrategyEngine` 订单簿与估值时序（U-P029-2 承接）** | U-P029-2；P-030 待办分析核出 `_next_day_orders` 无过期/无撤销，且 P-014 三层防线未下沉 `agents/`；**Step 1 探针四项实证**：R2 目标外持仓不生成卖出单（**P1**，默认 `equal_weight` 触发）/ R4 超卖成交入账致现金虚增（**P1**）/ R1 再平衡 NAV 漏计当日成交致自激换手（**P2**，`daily`）/ R3 失败单重复累积（**P2**）；**T1**（`agents/multi_strategy_engine.py` 单文件 + 新测试） | **done（2026-11-16，Step 1-10 全通过 + RULE-5 异构终审 pass，批次关闭）**：[RESEARCH_p031](RESEARCH_p031_strategy_engine_order_accounting.md)（§3 四项缺陷 / §11 Step 2 复审）+ [DESIGN_p031](DESIGN_p031_strategy_engine_order_accounting.md)（D1-D7 / I1-I8 / V1-V6）；**Step 2 异构 Review pass**（GLM-5.3-Flash：E1 十锚点 + E2 六组读数全复现；E3 两项新证——中性空头腿幻影现金 8 日 cash 10M→90M / `build_target_positions` 拒绝负权重；**2 P2 当轮回写**）；**Step 3 DESIGN 完成**（四项必答裁决：D2 中性空头腿**显式禁用**而非 fail-fast / D3 执行侧夹紧且 `core/tracker.py` 零改动 / `value_buffer=0.985` 采纳 / O1 与 short 语义不并入；B1-B5 切分）；**Step 4 异构 Review pass**（GLM-5.3-Flash ≠ DESIGN 作者 DeepSeek-V4.1-Flash：E1 五锚点 + E2 两探针——Q1 实证默认主路径 `_process_pending_orders` 无夹紧、queue 3 张 SELL 全成交 cash 虚增 2,000；**3 P2 + 1 P3 当轮回写**——F-S4-P031-1 D3/D4 改双路径夹紧+双载体撤销 / F-S4-P031-2 D1 补 nav 守卫（第 6 计数键 `rebalance_nav_invalid`）/ F-S4-P031-4 D2 补资金部署子裁决（维持半仓+披露，登记 U-P031-4）/ F-S4-P031-3（P3）`orders_missing_price` 触发面注记；B1→B2 顺序裁决「成立且加强」（多策略循环 L751/L882 无 try），详见 [DESIGN_p031 §12](DESIGN_p031_strategy_engine_order_accounting.md)，CI run `43853333069` 三 job success）；**Step 5 IMPL 完稿**（[IMPL_p031](IMPL_p031_strategy_engine_order_accounting.md)：B1-B5 五批 + 9 测试实例 / 逐函数锚点规格 / 6 项 fixture / 7 项低效排除 / 接口回退点 9 项 / 7 项实施期发现（F-I-P031-1 过期过滤移至切片后保 P-029 V5 / F-I-P031-2 queue 路径直调 execute_order / F-I-P031-7 V2 零成本口径修正）；V2b 覆盖补充 nav 守卫），CI run `43854958855` 三 job success）；**Step 6 实施 Review pass**（异构 GLM-5.3-Flash ≠ IMPL 作者 DeepSeek-V4.1-Flash：E1 十二锚点全命中 + E2 门禁基线独立复测四项一致（pytest 722 / black 118 / mypy 37 files 0 / tests .py 81）+ E3 探针（nav 守卫 nan/±inf/0/负值全拦截；is_expired 阈值实证）；**1 P3 当轮回写**——F-S6-P031-1 V4② 过期用例显式 BUY 单（SELL 6 日不过期：vitality 0.25 > 0.125）+ 3 观察（重建 vs 直调语义等价 / 次日丢弃无状态迁移 / queue 价格无校验为既有缺口），详见 [IMPL_p031 §13](IMPL_p031_strategy_engine_order_accounting.md)，CI run `43858051695` 三 job success）；**Step 7 CHECKLIST 完稿**（[CHECKLIST_p031](CHECKLIST_p031_strategy_engine_order_accounting.md)：六组 **46 项**零预填（A 中性 6 / B 估值 8 / C 夹紧 6 / D 撤销 6 / E 不变式 8 / F 门禁治理 12），基线实测 722 passed / 81 文件 / 78 test_*.py / golden 7 json / black 118 / mypy 37 files 0；目标 731/82/119/37 + golden 13 零重录；红态豁免（V6）与三处合法字面引用已披露），CI run `43859690027` 三 job success）；**Step 8 一致性 Review pass**（异构 GLM-5.3-Flash ≠ Step 7 作者 DeepSeek-V4.1-Flash：机械五项全过（链接 0 broken / 46 行 ID 闭环 / 计数自洽 / 49=46+3 零预填 / 角色引用）+ 对齐矩阵七项全过（9 实例三处 / 4 修 1 降级四处 / 6 键三文档 / 731 链三处 / V-ID 契约↔用例 1:1 / 顺序敏感五项 / 基线-目标链）；**2 P3 当轮回写 IMPL**——F-S8-P031-1 V5 补半仓断言 / F-S8-P031-2 IMPL §11 补 I1 AST 计数行；**1 P3 当轮修正**——F-S8-P031-3 B4 锚点改 DESIGN-V2 前缀；3 观察，详见 [CHECKLIST_p031 §10](CHECKLIST_p031_strategy_engine_order_accounting.md)，CI run `43861365698` 三 job success）；**Step 9 TDD 实施完成**（B1-B4 四批红→绿逐批取证：B1 V5 红 `1 failed` → 绿 `1 passed` / B2 V1+V2+V2b 红 `3 failed`（V2 红态 **9 笔**，与 RESEARCH R1 逐字一致）→ 绿 `4 passed` / B3 V3×2 红 `2 failed`（两路径各 3 笔成交，cash 虚增 2,000）→ 绿 `6 passed` / B4 V4×2+V6 红 `2 failed`（**V6 红态即通过**，回归保护显式标注不伪造红态）→ 绿 **`9 passed`**；**代码变更** `agents/multi_strategy_engine.py` **+133/−83**（D1 `compute_portfolio_value` + `build_target_positions` + nav 守卫 / D2 构造期 WARNING + 中性腿禁用 / D3 `_clamp_sell_quantity` 双路径 / D4 双载体撤销 + 过期过滤置于开盘价切片后 / `_generate_results` 增 `neutral_short_leg`）；**新测试** `tests/test_p031_strategy_engine_accounting.py`（≈270 行，8 个 `def test_`，V3 参数化 → 9 实例）；**门禁终态** pytest **731 passed**（722+9）/ tests .py **82** / black **119 unchanged** / mypy **37 files 0** / golden+p027+p029 **48 passed**（13+24+11）**golden 零重录** / AST `except Exception` 恒 **22** / `core`+`tests/golden` 零改动 / 公开签名零变更；**实施期发现 3 P3**（F-S9-P031-1 `mark_expired` 实为 2 调用 + 1 注释，原「仅 1 处」失实已修正 / F-S9-P031-2 新测试 black 首轮重排 / F-S9-P031-3 V6 红态即通过），详见 [IMPL_p031 §11](IMPL_p031_strategy_engine_order_accounting.md)；提交 `750674e` → CI run `43864133531` 三 job success）；**Step 10 ADD 审计 + RULE-5 异构终审 pass**（GLM-5.3-Flash ≠ 四文档作者 DeepSeek-V4.1-Flash，审计与终审合并一轮，审计区间 `6a7771e..780197c`；Phase 0 spec 质量门 **5/5 Tier A** + Phase 1-4 全过（完整性 8 文件 +714/−98 / 保真度九函数独立读码 pass / 必要性 11 hunk 零游离行 / 语义生命周期五面裁决）+ E1-E5 门禁独立复跑全绿（**731 passed** / black **119** / mypy **37 files 0** / golden 回归面 **48** / I1 **22**）+ 盲区扫描零新增静默；**0 P0-P2 + 1 P3 当轮修正 F-R5-P031-1**（IMPL §11.2 测试行数 +270 → 提交后实测 **+272**）+ 2 观察，详见 [CHECKLIST_p031 §11](CHECKLIST_p031_strategy_engine_order_accounting.md)）——**批次关闭**；U-P031-1~4 与 O-P031-1~3 随批次归档，触发条件不变 | **P1** |
| U-P031-1 | 中性策略负持仓账目模型（保证金 / 借券 / 负市值盯市） | [DESIGN_p031 §7](DESIGN_p031_strategy_engine_order_accounting.md) D2 裁决；P-031 按显式降级处理（半仓多头 + 三重披露）；实现完整做空需改 `core/tracker.py` / `core/execution.py` 并波及 V2/V3/golden | pending（条件触发：需要真正市场中性策略） | P2 |
| U-P031-2 | BUY 侧现金夹紧 | [DESIGN_p031 §7](DESIGN_p031_strategy_engine_order_accounting.md)；与 U-P014-3 同列；D3 仅修 SELL 侧（超卖幻影现金），BUY 侧现金不足时行为未定义 | pending（条件触发：BUY 侧透支出现实证事故）；**2026-11-17 注记（P-034 台账收口）**：U-P014-3 与 U-P033-2 同源已并入本行，本行为**单一跟踪源** | P3 |
| U-P031-3 | `direction="short"` 语义（买低分 vs 真做空） | [DESIGN_p031 §7](DESIGN_p031_strategy_engine_order_accounting.md) D5；`select_top=False` 产正权重买低分股，模块 docstring 两义；产品定义未定 | pending（条件触发：产品侧裁决 short 策略语义） | P3 |
| U-P031-4 | 中性策略资金部署产品化（重归一化满仓单边 vs 半仓+现金） | [DESIGN_p031 §7](DESIGN_p031_strategy_engine_order_accounting.md) F-S4-P031-4；现裁决维持 `long_weight` 缩放（半仓 + 双重披露），满仓需求应显式改用 `direction="long"` | pending（条件触发：用户要求中性策略满仓单边部署） | P3 |
| **P-032** | **台账收口 + 文档幻觉修正（P-031 关闭后遗留，T3 轻批）** | P-031 关闭后发现：① §1.4 U-P029-2 仍标 `in-progress`（实际已由 P-031 完成关闭）；② U-P031-1~4 未在 §1.4 建行（P-030 教训：散落正文会漏跟踪）；③ O-P031-3 实测仍成立——README L314-315 调用 `MultiStrategyEngine.register_agent`，该方法仅存在于 `MultiAgentBacktestEngine`（agent_framework L1213），且 `MultiStrategyEngine` 无 `run()`（仅 `run_sequential` / `run_parallel` / `run_vectorized`）——示例双重幻觉 | **done（2026-11-16，T3 轻批）**：① U-P029-2 → **done**；② 新增 U-P031-1~4 四行（pending，触发条件各自独立）；③ README Multi-Agent 示例改 `MultiAgentBacktestEngine`（`register_agent` / `setup` / `run` 真实链）+ 补 `MultiStrategyEngine` 真实 API 注记（O-P031-3 **关闭**）；④ CHANGELOG 追加本批条目；门禁持平 **731 passed** / mypy **37 files 0** / black **119 unchanged**；同基座独立复审 pass（0 缺陷 + 2 观察，异构终审预留 U-P032-1），详见 §3.37 | P3 |
| U-P032-1 | P-032 的 RULE-5 异构终审预留 | RULE-5：P-032 作者与同基座复审者均为 GLM-5.3-Flash（本会话），异构条件不成立；同基座独立复审已全过（E1 API 实证 / E2 结构 / E3 落位 / E4 diff 面 / E5 门禁 731/119/37，0 缺陷 + 2 观察，PROGRESS §3.37） | **done（2026-11-16，由 DeepSeek-V4.1-Flash 承接）**：异构终审五项全过（E1 introspection / E2 结构 / E3 落位 / E4 diff / E5 门禁 731/119/37），**0 缺陷 + 1 观察**，见 §3.37 | P3 |
| **P-033** | **待执行订单价格有效性（queue 路径 NaN / 非正价透传，O-S6-P031-3 承接）** | O-S6-P031-3（P-031 Step 6 观察）；**Step 1 十场景探针实证**：queue 路径（`agents` 与 `core/engine_v2` **同构**）仅做成员检查 → **R1** 开盘价 `NaN`/`±inf` → 成交入账后 **cash 永久 NaN**（NAV 全 NaN、P-031 nav 守卫逐日计数、组合冻结，**P1**）/ **R2** 开盘价 `0` → **免费持仓**（零成本 100 股；默认成本仅付 5 元佣金）、`-5` → **现金 +500**（**P2**）/ **R3** `close=0` 除零返回 `inf` 仅告警（P3）；**次日路径两引擎均已完整防护**（对照组零成交、订单保留，负向发现 N1）→ 缺陷严格限于 queue 路径；非 P-031 回归（N5）；全仓 37 处 `execute_order` 调用零非正价入参（测试破坏面 0）；**T1**（`core/execution.py` + `core/engine_v2.py` + `agents/multi_strategy_engine.py`） | **done（2026-11-17，Step 1-10 全通过，批次关闭）**：四文档 [RESEARCH_p033](RESEARCH_p033_pending_order_price_validation.md)（R1 P1 / R2 P2 / R3 P3 + M-A 方案）/ [DESIGN_p033](DESIGN_p033_pending_order_price_validation.md)（D1-D6 / I1-I7 / V1-V8）/ [IMPL_p033](IMPL_p033_pending_order_price_validation.md)（B1-B4 / §4 锚点 / §11 实施记录）/ [CHECKLIST_p033](CHECKLIST_p033_pending_order_price_validation.md)（39 项 39/39 / §9 Step 8 / §10 Step 10）；**修复**：`is_valid_price` 单点守卫（execution L153-161 + 解析后守卫 L308-315，覆盖 OPEN/CLOSE/VWAP/CUSTOM 五分支）+ 双引擎 queue 前置过滤（agents L511-514 新键 `pending_invalid_price` / V2 L810-813 复用 `skipped_price`）——NaN/±inf/≤0 开盘价由「静默成交污染账目」改为「拒绝 + 计量 + 保留重试」；新增 `tests/test_p033_order_price_validation.py` **17 实例**（三批红→绿 6F/1P → 6F/1P → 2F/1P，全批 14F/3P）；golden **13 零重录**、公开签名零变更、`except Exception` 恒 **22**；门禁 **731 → 748 passed** / 测试文件 82 → **83** / black 119 → **120** / mypy 37 files 0；**Step 2/4/6/8 异构 Review 四轮 pass（GLM-5.3-Flash）**：Step 2（十场景逐字一致 + 2 P3）→ Step 4（C1/C2 实锤解析后守卫必要性 + 2 P3）→ Step 6（E3 红态探针 F-S6-P033-1 当轮回写）→ Step 8（机械五项 + 对齐矩阵七项，F-S8-P033-2 红态批次口径更正 + 6 P3 当轮修正）；**Step 9 TDD**（DeepSeek-V4.1-Flash，2 项实施期发现）；**Step 10 ADD 审计 + RULE-5 终审 pass**（GLM-5.3-Flash：Phase 0 5/5 Tier A + 7 hunk 零游离 + 门禁独立复跑全绿 + 盲区零新增静默；F-R5-P033-1 当轮修正 + 1 观察）；未决 U-P033-1~3 随批归档，详见 §3.38.1~§3.38.9 | **P1** |
| **P-034** | **台账收口 · 价格差异校验守卫 · CI 锁门禁（三件合批）** | ① U-P033-1（R3 `close=0` 告警文案）；② U-P024-2（CI 增加 `uv lock --check` 门禁，单一跟踪源）；③ PROGRESS §1.4 台账三缺口（P-030/P-032 同型第三次）；**Step 1 探针实证 R3 三形态**：R1 `close=0.0`（Python float）→ `ZeroDivisionError` 被 except 捕获 → 合法价订单 `success=False`（诊断吞单，P3 结构性隐患 / 三引擎生产不可达）/ R2 `np.float64(0)` → `inf%` 告警噪声（P3）/ R3 `close` NaN·负 → 校验静默失效（P3）；`uv 0.11.14` + `uv lock --check` 本地 exit 0 而 CI 零 uv 步骤；**T1**（**强制升级**：任务 C 新增 CI 门禁，SPEC_PROCESS 判档规则 2） | **done（2026-11-17，Step 1-10 全通过，批次关闭）**：四文档 [RESEARCH_p034](RESEARCH_p034_ledger_diff_guard_and_lock_gate.md) / [DESIGN_p034](DESIGN_p034_ledger_diff_guard_and_lock_gate.md) / [IMPL_p034](IMPL_p034_ledger_diff_guard_and_lock_gate.md) / [CHECKLIST_p034](CHECKLIST_p034_ledger_diff_guard_and_lock_gate.md)（37 项 37/37）；**修复**：`if close_price is not None and is_valid_price(close_price):`（1 定义 **4** 调用）+ 新增独立 `lock-check` job（`setup-uv@v10.3.3` + `uv lock --check`，禁 `\|\| true`）；新增 `tests/test_p034_price_diff_guard.py` **12 实例**（红 **3F/9P** → 绿 12 passed）；门禁 **748 → 760** / 84 / 121 / 37 / golden 13 零重录 / AST 22 / `uv lock --check` exit 0；**Step 2/4/6/8/10 五轮同基座独立复审（RULE-5 不成立 → 异构终审记 U-P034-3）**：Step 2（C1-C4 四项新证 + 1 P3）→ Step 4（mypy 正反例 + `setup-uv@v6` 过时 → v10.3.3，1 **P2** 当轮）→ Step 6（红态预览 3F/9P 逐项吻合 + 1 P3）→ Step 8（机械五项 + A-G，1 P3）→ Step 10（Phase 0 5/5 Tier A + 2 hunk 零游离 + 1 P3 `O-P034-3` 引用幻觉）；台账 8 处收口（U-P033-1 done / U-P033-3 不采纳 / U-P033-2·U-P014-3 → U-P031-2 / U-008 → U-P021-2 / 三项建行）；**U-P034-3 异构终审 pass（2026-11-17，GLM-5.3-Flash 补做：E1-E5 五项全过 + 运行期复验 7/7 + 2 P3 当轮修正 F-U3-P034-1/-2）**；详见 §3.39.1~§3.39.10 | **P3** |
| U-P033-1 | R3 `close=0` 差异告警文案（`inf%`） | [DESIGN_p033 §7](DESIGN_p033_pending_order_price_validation.md) D6；无账目污染，仅告警噪声 | **done（2026-11-17 由 P-034 承接）**：D1 close 有效性守卫——无效 close 静默跳过（同时消除 `ZeroDivisionError` 吞单与 NaN 静默），见 §3.39 | P3 |
| U-P033-2 | BUY 侧现金夹紧 | [DESIGN_p033 §7](DESIGN_p033_pending_order_price_validation.md)；与 U-P031-2 / U-P014-3 同源 | **已合并（2026-11-17，P-034 台账收口）**：统一由 **U-P031-2** 单一跟踪 | P3 |
| U-P033-3 | 账目层（`tracker.execute_trade`）价格守卫 | [DESIGN_p033 §7](DESIGN_p033_pending_order_price_validation.md)；账目层堵漏会掩盖上游数据错误且 V3 共用该层 | **已裁决不采纳**（同 O-P031-1 口径），2026-11-17 P-034 建行归档 | P3 |
| U-P014-1 | 停牌 / 涨跌停掩码语义变更 | [DESIGN_p014 §1](DESIGN_p014_suspension_accounting.md)（非目标）；P-014 不改变掩码语义 | pending（条件触发：需要变更停牌/涨跌停判定口径） | P3 |
| U-P014-3 | 队列路径买侧现金校验 | [DESIGN_p014 §1](DESIGN_p014_suspension_accounting.md)（非目标）；P-031 D3 仅修 SELL 侧 | **已合并（2026-11-17，P-034 台账收口）**：统一由 **U-P031-2** 单一跟踪 | P3 |
| U-P015-1 | Backtrader ↔ V2 第二例对拍 | [RESEARCH_p015 §6](RESEARCH_p015_external_benchmark.md) 四元块；判据 = 首例方法论闭环报告落档；附加前置 = U-P016-1 费用语义 | pending（条件触发：需要第二框架对照） | P3 |
| U-P016-1 | current-NAV 规格的费用语义（`cost_rate>0`） | [RESEARCH_p016 §6](RESEARCH_p016_p015_review_fixes.md) 四元块；现 `simulate_vbt_spec` 对 `rate>0` fail-fast | pending（触发：U-P015-1 立项时一并定义） | P3 |
| U-P034-1 | `setup-uv` action 长期维护 vs `pip install uv` 降级链 | [DESIGN_p034 §5](DESIGN_p034_ledger_diff_guard_and_lock_gate.md) 未决表；`@v10.3.3` 精确钉，v10 `enable-cache` 语义 = `'auto'`（省略） | pending（条件触发：action 主版本升级 / 不可用时重验降级链） | P3 |
| U-P034-2 | 外部调用方同时传 Python float 的 R1 面 | [DESIGN_p034 §5](DESIGN_p034_ledger_diff_guard_and_lock_gate.md) 未决表；现 8 生产调用点全为 `np.float64` 取值写法（R1 不可达），`to_dict`/`items` 写法会产生 Python `float` 使 R1 形态可达 | pending（条件触发：真实外部调用报告） | P3 |
| U-P034-3 | P-034 的 RULE-5 异构终审预留 | RULE-5：作者与五轮复审者（Step 2/4/6/8/10）均为 DeepSeek-V4.1-Flash，异构不成立；同基座终审已全过（Phase 0 5/5 Tier A + 2 hunk 零游离 + 门禁独立复跑全绿，见 §3.39.9） | **done（2026-11-17，由 GLM-5.3-Flash 承接）**：异构终审五项全过（E1 锚点 / E2 diff 面 12 提交 / E3 门禁 760·121·37·86·12·uv exit 0 / E4 运行期复验 7/7 / E5 F-R5-P034-1 修正到位）+ 2 P3 当轮修正（F-U3-P034-1 审计区间口径 / F-U3-P034-2 台账建行缺口），见 §3.39.10 | P3 |
| **P-035** | **台账同步（U-P024-2 关闭 + D5 纪律扩展，T3 轻批）** | 2026-11-17 待办分析发现：U-P024-2（CI 增加 `uv lock --check` 门禁）已由 P-034 任务 B 完整落地（`lock-check` job 上线并持续全绿），但 §1.4 仍标 `pending`——P-034 的 D3 八处收口清单只含「新增 / 合并 / 不采纳」项，未含「本批实现的既有项」；同型缺口第 5 次（P-030 / P-032 / P-034 / F-U3-P034-2 / 本次）；**T3**（纯文档，零代码 / 零测试 / 零门禁变更） | **done（2026-11-17，T3 轻批）**：① U-P024-2 → **done**（P-034 承接，`lock-check` job 实证）；② U-P021-1 追加关闭指针注；③ **D5 派生纪律扩展**——批次关闭动作清单由「本批新增 U-\*/O-\* 是否建行」扩为「新增建行 **+ 本批实现/承接的既有项转 done / 已合并**」（[DESIGN_p034](DESIGN_p034_ledger_diff_guard_and_lock_gate.md) D3 附则 + 本节）；④ [CHANGELOG](../CHANGELOG.md) 追加本批条目；门禁持平 **760 passed** / black **121 unchanged** / mypy **37 files 0**（详见 §3.40） | P3 |
| **P-036** | **mypy 检查面扩展（U-P024-3 取证批）** | U-P024-3 + U-P024-4 + U-P024-1 三条关联项；**Step 1 取证（CI 等价口径复刻 venv）**：当前门禁 target 仅 `core`（37 files），`agents/` / `filter/` / `scripts/` / `batch_backtest/` / `strategy_evaluation/` / `cli.py` 零覆盖；实测 **129 errors / 25 files**（保留 `filter.*` 豁免则 **108**），按目录 `agents` 94 / `filter` 21 / `scripts` 5 / `cli.py` 3 / `strategy_evaluation` 3 / `order_strategy` 2 / `batch_backtest` 1，`core`·`web`·`factor_library` **0**；错误码 `union-attr` **50**（潜在 AttributeError，A 级）/ `no-any-return` 34 / `var-annotated` 11 / 其余 34；**R1 机制实锤**：根因是 **mypy 版本行为差异**（2.1.0 下 `core` = 0，2.4.1 同配置 = 21），**非 pandas 类型桩**（2.2.3 与 3.1.1 均无 `py.typed`）→ **P-024 归因失实、U-P024-4 前提需重写**；**T1**（判档规则 2：扩面 = 变更 CI 门禁判据） | **in-progress（Step 1-8 完成，待 Step 9 TDD 三批实施）**：[RESEARCH_p036](RESEARCH_p036_mypy_check_surface_expansion.md)（§3 环境矩阵 + 保真校验 0/37 与 CI 逐字一致 / §4 两方案读数 / §5 R1'~~R1~~ + R2' + R3-R5 + N1-N3 / §6 A-B-C 三级分类 50+30+46 / §7 M-A~M-D 方案矩阵推荐 M-B 两级分批 + 七项低效排除 / §8 U-P036-1~4 四元块 / §9 可重放命令 / §11 B0 裁决与实施 / **§12 Step 2 异构复审：1 P2（F-S2-P036-2 R1 归因证伪→R1'）+ 3 P3 当轮回写 + 4 观察，pass**）/ [DESIGN_p036](DESIGN_p036_mypy_check_surface_expansion.md)（D1 双口径固定 + D2 三批边界 + D3 修复四层策略 + D4 行为变更裁决 + D5 override 移除绑定 + D6/D7 不扩做 / I1-I7 / V1-V6 含红态实测 / **F-D3-P036-1（P2）读数对 pandas 敏感 2 条（Step 4 已改判 numpy，见 §3.41.5）**；**§9 Step 4 异构复审 pass（GLM）**：2 P2 + 2 P3 当轮回写——F-S4-P036-4 129/131 差异变量改判 **numpy 桩版本**（真 CI 口径 = 131 = 本地，双口径收敛）/ F-S4-P036-3 **D4 改写**（guru_data 实为 U-a 构造期已 `raise`；裁决原则改「现网崩溃 → 保持 fail-fast，禁止默认值降级」，对齐 P-025 F-D3-P025-1 先例）/ F-S4-P036-1（P3）D2 表「本地 98」笔误 / F-S4-P036-2（P3）根因计数 37（guru_data 25 + mask 12））/ [IMPL_p036](IMPL_p036_mypy_check_surface_expansion.md)（**Step 5**：B1 14 条逐条 + B2 96 条按 11 文件簇 + B3 21 条逐条规格（§4）；行为变更清单 C1-C4；I2 返回注解口径澄清；§5 三批红态实测 14/96/21；**不新增 pytest（X=0）**；**§11 Step 6 异构复审 pass：2 P2（F-S6-P036-1 filter_stocks 分组更正 / F-S6-P036-2 三个 filter 工厂返回注解补录，I2 清单 5→8 处）+ 4 P3 当轮回写，F-I-P036-3/4 闭合**）/ [CHECKLIST_p036](CHECKLIST_p036_mypy_check_surface_expansion.md)（**Step 7**：六组 **65 项零预填**——A B1 12 / B B2 14 / C B3 11 / D 行为变更 C1-C4 8 / E 不变式 10 / F 门禁治理 10；基线 760·84·121·37·13·22·uv 0；**§9 Step 8 异构一致性 Review pass：机械五项全过 + 对齐矩阵 5/6 逐字一致 + 1 P3（F-S8-P036-1 「8 处 def 行」口径精化为 7 处 def 行 + 1 处参数注解行）当轮精化**）；**Step 9 完成（2026-11-17）**：三批红→绿 14/96/21 → 0（8→9→10 面；终态 92 files 三口径 0）、C1-C4 探针留证、gate 双载体同步、删 pyproject override；5 提交 `e2dafff`/`e781b75`/`eb3ae55`/`43ed468`/`f1fdab4`，CI run `44029888652` 四 job 全绿；CHECKLIST **65/65**；F-S9-P036-1~7（2 P2 + 5 P3）闭合，见 §3.41.10-§3.41.13 | P3 |
| U-D1(P-011) | golden 全局基线固化（L4 判据） | P-011 U-D1 设计裁决挂起；**硬约束「先改口径、后固 golden」已满足**——复权三口径/掩码/退市均已随 P-012 落地且 RULE-5 复审确认无未归因行为；**T1**（基线固化 + manifest 绑定） | **done（2026-11-10 由 P-013 承接**，见下） | **P2** |
| P-013 | Golden 基线固化（L4 判据落地） | P-011 U-D1 升格；6 条基线（V2/V3 × baseline·cost·mask·delisting）× 分字段容差 × CI 三版本；**T1** | done（2026-11-10，Step 1-10 全通过：四文档 + B1/B2 两批；**626 passed**（609+17）/ black 171 / mypy 0 / 盲区不劣化 / 6 份基线**逐字节可重现**；`tests/golden/*.json` + `scripts/record_golden.py` + `tests/_golden_cases.py` 单一构造器；实施期发现 **F-S9-G1（P1 停牌账目缺陷）** + F-S9-G2~G7） | P2 |
| **P-014** | **V2 停牌路径账目缺陷（P-013 实施期发现）** | 次日开盘路径（`enable_pending_orders=False`）在停牌期重复生成清仓单，恢复日一次性成交 → 负持仓 + 5 项 I2 违规；E2 复现见 [RESEARCH_p014 §4](RESEARCH_p014_suspension_accounting.md)；**症状订正**：原登记「停牌日仍成交」未复现（掩码生效），详见该文 §4.3；**T1** | **done（2026-11-10，Step 1-10）**：三层防线（执行侧持仓夹紧 / 再平衡刷新订单簿 / 次日订单过期）+ 8 项性质测试 + golden **G7**；**635 passed** / black 172 / mypy 0（36）/ 盲区不劣化；G1/G2/G4/G5/G6 基线**数值不变**，G3 行为变更重录（56→55 笔，NAV rel 1.11e-6，理由见 [IMPL §9.3](IMPL_p014_suspension_accounting.md)）；四文档 [RESEARCH](RESEARCH_p014_suspension_accounting.md) / [DESIGN](DESIGN_p014_suspension_accounting.md) / [IMPL](IMPL_p014_suspension_accounting.md) / [CHECKLIST](CHECKLIST_p014_suspension_accounting.md) | **P1** |
| **P-015** | **外部框架对拍校准（U-4 触发 · 单框架打通）** | U-4 触发条件「用户/评审要求第三方框架对照时」由用户 2026-11-10 说明构成——目的=**准确性基准**（验证「准确计算 + 回测机制设计意图落地」），非对外声明一致；用户裁决：① 正式立项 ② 先一个框架打通；**VectorBT↔V3 首例 + 隔离 venv**（vectorbt 1.2.0 依赖 pandas>=3.0.3 / numba>=0.66，与主环境冲突，清华镜像安装）；Backtrader↔V2、Qlib 登记后续（U-P015-1）；**T1**（Layer-1：`scripts/external_benchmark/`） | **done（2026-11-10，Step 1-10）**：四文档 + 规格层/三脚本 + **隔离 venv**（.gitignore 豁免）+ [校准报告](APPENDIX_p015_external_calibration.md)；**29 项恒等式断言 0 失败**（**P-017 口径更正**：含 B5 恒真豁免 1 项 → 28 断言 + 1 豁免登记）（I1 全零残差 / I2c 闭式一般式 2.0e-10 / I3 费用模型一致性 + 缺口 38658.94 登记 / I4 翻转全等 5.8e-11 / I5 阴性对照 −10000.000000 精确命中）；**两处结构性语义差异实锤**（V3 last_pv 规模参考值 vs vbt current-NAV；V3 费用透支现金 vs vbt 部分成交——已写恒等式/缺口）；**635 passed / black 0 / 主环境零污染**；mapping §2.2 获首个实测列；执行序 §3.17；四文档 [RESEARCH](RESEARCH_p015_external_benchmark.md) / [DESIGN](DESIGN_p015_external_benchmark.md) / [IMPL](IMPL_p015_external_benchmark.md) / [CHECKLIST](CHECKLIST_p015_external_benchmark.md) | P2 |
| **P-016** | **P-015 复审 P3 修正（F-R5-P015-1~3 + F-S9-P016-1）** | RULE-5 复审 §9.4 输出 3 项 P3；改动落 `scripts/external_benchmark/`（Layer-1）→ **T1**（判档规则 1 + 规则 3 fail-closed；本仓无 T2 本地先例）；实施前取证新发现 F-S9-P016-1（报告覆盖**已真实发生**，P2） | **done（2026-11-10，Step 1-10）**：三态词表（pass/fail/waiver，豁免不计断言）/ 报告人工章节保护（命中即改写 `.generated.md`）/ `simulate_vbt_spec` rate>0 fail-fast / I2a↔G1 命名映射三处文档注；**重新回填** APPENDIX §1/§3/§4（P-015 会话内已被覆盖为占位）；**18/18**；**28 断言 + 1 豁免，exit 0**；`635 passed` / black 0 / 主环境零污染；发现 P2×1 + P3×1（F-S9-P016-2 复审漏检项，登记）；四文档 [RESEARCH](RESEARCH_p016_p015_review_fixes.md) / [DESIGN](DESIGN_p016_p015_review_fixes.md) / [IMPL](IMPL_p016_p015_review_fixes.md) / [CHECKLIST](CHECKLIST_p016_p015_review_fixes.md) | **P3** |
| **P-017** | **P-016 复审 E4 四项 P3 修正** | P-016 RULE-5 复审 §9.4 E4 输出 4 项 P3（F-R5-P016-1~4）；改动落 `scripts/external_benchmark/verify_p015.py`（Layer-1）→ **T1**（判档规则 1；无 T2 本地先例） | **done（2026-11-10，Step 1-10）**：① PROGRESS §3.17.1 + §1.4 两处「29 项断言」补 P-017 口径注（原句保留，不改冻结读数）；② IMPL_p015 §8.5 占位回填为读数表 + 「T-4 原始读数未保全」声明；③ `_resolve_report_target` 增 `GENERATED_SUFFIX` 命名空间守卫（生成物原地重写，消除 `.generated.generated.md` 级联）；④ CHECKLIST_p016 E-1 计数更正为 12 文件 + B-3 分支精确化。**13/13 ✅**；四分支探针全 PASS；**28 断言 + 1 豁免，exit 0**；`635 passed` / black 0；占位真实残留 0；四文档 [RESEARCH](RESEARCH_p017_p016_review_fixes.md) / [DESIGN](DESIGN_p017_p016_review_fixes.md) / [IMPL](IMPL_p017_p016_review_fixes.md) / [CHECKLIST](CHECKLIST_p017_p016_review_fixes.md) | **P3** |
| **P-018** | **P-017 复审 E4 两项 P3 修正** | P-017 RULE-5 复审 §9.4 E4 输出 F-R5-P017-1（无扩展名目标守卫失效）/ -2（分支 1 覆盖归因失实）；改动落 `scripts/external_benchmark/verify_p015.py`（Layer-1）→ **T1** | **done（2026-11-10，Step 1-10）**：① 守卫改为并判 `path.name` 与 `path.stem`（单行 1:1，零行号位移）——`X.generated` 二次运行不再级联；② IMPL_p017 §6.2 + CHECKLIST_p017 C-4 追加 P-018 更正注（原句保留）+ 探针 ⑥ 真实覆盖分支 1。**10/10 ✅**；8 探针全 PASS；**28 断言 + 1 豁免，exit 0**；`635 passed`（Agg）/ black 5 unchanged；四文档 [RESEARCH](RESEARCH_p018_p017_review_fixes.md) / [DESIGN](DESIGN_p018_p017_review_fixes.md) / [IMPL](IMPL_p018_p017_review_fixes.md) / [CHECKLIST](CHECKLIST_p018_p017_review_fixes.md) | **P3** |
| **P-019** | **报告写入父目录缺失修正（F-R5-P018-1）** | P-018 RULE-5 复审 §9.4 E4 发现：`--report` 父目录不存在时抛未捕获 `FileNotFoundError`（exit 1），且 P-018 探针 ⑥ 声称覆盖该形态（失实）；改动落 `scripts/external_benchmark/verify_p015.py`（Layer-1）→ **T1** | **done（2026-11-10，Step 1-10）**：① `write_report` 增 `target.parent.mkdir(parents=True, exist_ok=True)`（+1 行，`:254/:268/:272` 锚点零位移）——父目录缺失/多级父目录均可写；② IMPL_p018 §6.2 + CHECKLIST_p018 B-3 追加 P-019 更正注（原句保留）+ 真探针。**10/10 ✅**；7 探针全 PASS；**28 断言 + 1 豁免，exit 0**；`635 passed`（Agg）/ black 5 unchanged；四文档 [RESEARCH](RESEARCH_p019_report_parent_dir.md) / [DESIGN](DESIGN_p019_report_parent_dir.md) / [IMPL](IMPL_p019_report_parent_dir.md) / [CHECKLIST](CHECKLIST_p019_report_parent_dir.md) | **P3** |
| U-D2(P-011) | V2 同日收盘模式（跨引擎逐日净值一致） | P-011 U-D2 挂起（倾向不做）；触发=第三方要求 V2/V3 逐日净值一致 | pending（倾向不做） | P3 |
| U-D3(P-011) | trace 采样/保留策略 | P-011 U-D3 挂起；触发=长区间/全市场 trace（体积 > 500 MB） | pending（条件触发） | P3 |
| U-2(P-011) | DSR/PBO 多重检验校正 | P-011 RESEARCH U-2 裁决：S-B 方案挂起至对外发布需求——无 trials log 则 DSR/PBO 无数据可算；触发=对外发布因子结论或建立 trials 记录 | pending（条件触发） | P3 |
| U-P005-1 | Factor_DB DuckDB 存储迁移（条件触发） | [RESEARCH_p005 §5](RESEARCH_p005_factor_db_alignment.md) 四元块；触发 = 首个生产因子库数据集，或单次 `query()` 内存过滤 >1s（可机械测量）；届时优先 DuckDB 直读 Parquet（零导入） | pending（条件触发） | P3 |
| U-P005-2 | Factor_DB 四项实现缺陷（静默覆盖 / csv 孤儿 / str-datetime / 双份存储） | [RESEARCH_p005 P7](RESEARCH_p005_factor_db_alignment.md)；HEAD 复核四项仍在（`database.py` L77-84 / L101-112 / L198-210）；零数据 → 风险未现实化；修复含 4 组红绿测试，`add_factor` 语义变严 | **done（2026-11-12 由 P-022 承接）**：四项全修；缺陷③由「类型漂移」重估为「写后重开崩溃（P1）」；新增 11 项回归测试；**647 passed** | P3 |
| U-P022-1 | `_save_metadata` 原子写（tmp + os.replace） | [RESEARCH_p022 §6](RESEARCH_p022_factor_db_defects.md)；当前为非原子 `open(..., "w")` | pending（条件触发：并发写 / 写中断事故） | P3 |
| U-P022-2 | `get_factor` 返回副本（防调用方污染缓存） | [RESEARCH_p022 P10](RESEARCH_p022_factor_db_defects.md)；当前命中缓存时返回内部 DataFrame | pending（条件触发：缓存污染事故 / 新增写消费方） | P3 |
| U-P022-3 | 非 `ImportError` 写入失败的清理 | [RESEARCH_p022 §6](RESEARCH_p022_factor_db_defects.md)；`ArrowInvalid` 等异常会留下半成品文件 | pending（条件触发：真实引擎异常样本） | P3 |
| U-P022-4 | `overwrite=True` 保留 `created_at` | [RESEARCH_p022 §6](RESEARCH_p022_factor_db_defects.md)；探针证实覆盖会重置创建时间（血缘/审计丢失） | pending（条件触发：按创建时间排序 / 审计需求） | P3 |
| U-P005-4 | Parquet 可选引擎声明（`pyarrow`/`fastparquet`） | [RESEARCH_p005 §5](RESEARCH_p005_factor_db_alignment.md)；当前不声明，README 写明前提 + CSV 回退 | **done（2026-11-12 由 P-021 承接）**：决定**不显式声明**（保持核心依赖最小面）；`ARCHITECTURE §9.2` 写明「未声明；缺失时降级 CSV」；锁内 `pyarrow` 仅经 streamlit（`[web]` extra）传递出现 | P3 |
| U-P005-5 | `uv.lock` 既有漂移（`uv lock --check` 失败） | [RESEARCH_p005 §5](RESEARCH_p005_factor_db_alignment.md)；锁内根包 `metadata.provides-extras` 缺 `web` extra；原估完整重锁 `+1207/−46` 行 | **done（2026-11-12 由 P-021 承接）**：plain `uv lock` 实测 **`+1207/−2`**（既有 pin 全部保留，仅 2 行元数据更新：extras + black specifier）；`--check` exit 1 → 0；120 → 148 包（新增 19） | P3 |
| U-P021-1 | CI 增加 `uv lock --check` 门禁 | [RESEARCH_p021 §6](RESEARCH_p021_dependency_lock_maintenance.md)；CI 当前 `pip install ".[dev]"`，锁不参与安装；本地 `--check` 已归零但不约束提交 | **已合并（2026-11-16，P-028 台账去重）**：与 U-P024-2 同源，统一由后者**单一跟踪**；本行保留历史记录与 RESEARCH_p021 §6 锚点，不再单独触发；**U-P024-2 已于 2026-11-17 由 P-034 落地并关闭（本项随之关闭，见 §3.40）** | P3 |
| U-P021-2 | `numba` 依赖声明 | [RESEARCH_p021 §6](RESEARCH_p021_dependency_lock_maintenance.md)；未声明；缺失时降级 `py_func`；CI 无 JIT 覆盖（与 U-008 同源） | pending（条件触发：CI 需覆盖 JIT 或出现性能回归） | P3 |
| U-P021-3 | 锁升级节奏 | [RESEARCH_p021 §6](RESEARCH_p021_dependency_lock_maintenance.md)；本批只补缺不升级（plain `uv lock`），既有 pin 保持 2026 年旧值 | pending（条件触发：安全通告 / 显式升级需求） | P3 |
| U-P023-1 | `run()` 逐日 `except Exception: continue` 的 retry 语义 | [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)；P-007 RESEARCH A26 已登记 `Catch Generic` 反模式 | **done（2026-11-13 由 P-025 承接并完成）**：触发条件经 P-025 Step 1 取证改判为**已成立**（探针 B2：`min_variance` + `cov_lookback=60` → 0 成交 / sharpe 0.0 / 零诊断）；P-025 落地三处统一采集 + `run_diagnostics` + `day_error_mode` 三态 + D7-O2 setup 预检，探针 B2 现由 setup 直接拦截，详见 [CHECKLIST_p025](CHECKLIST_p025_daily_loop_exception_semantics.md) | P3 |
| U-P025-1 | `EventLog` 接入引擎作为统一事件通道 | `run_diagnostics` 已落地且有第二个消费方（web/批处理）需要事件流 | pending（条件触发，本批不接入） | P3 |
| U-P025-2 | `EngineV3Vector` 是否需要同形诊断 | V3 出现「静默空结果」实例 | pending（条件触发；V3 单次向量求值无日循环） | P3 |
| U-P025-3 | 其余 22 处 `except Exception` 治理 | 其中任一处产生可复现的静默错误 | **done（2026-11-13，P-025 + P-026 两批收口）**：22 处逐点裁决 D10 显形 / K8 保留（有理由零改动）/ 排除 4（非静默），见 [RESEARCH_p026 §5](RESEARCH_p026_silent_exception_governance.md)；ADD 审计 A+ | P3 |
| U-P025-4 | 优化失败时退化为等权（而非跳过调仓） | — | **已裁决不做**：静默降级会掩盖配置错误（正是 F-D3-P025-1 的成因） | P3 |
| U-P025-5 | `ExceptionGroup`（raise 模式）与 3.10 分支实现 | DESIGN 阶段确认最低版本 3.10 | **done**：3.11+ `getattr(builtins,"ExceptionGroup")` / 3.10 `RuntimeError`；T7 版本分支断言 + CI 3.10 job 覆盖 | P3 |
| U-P025-6 | 末日重复快照治理（`_force_liquidation` 末日二次 `update_market_values`） | 需要精确交易日数统计 / golden 有意重录 | pending（本批不动；A3 复跑 21 快照 / 20 去重日，golden 依赖该形态） | P3 |
| U-P026-1 | `EventLog` 写盘失败是否 fail-fast 或重试 | [RESEARCH_p026 §7](RESEARCH_p026_silent_exception_governance.md)；触发：审计完整性成为合规要求，或出现写盘断裂真实案例 | pending（倾向不 fail-fast 保可用性；P-026 已落地 `write_failures` 计量） | P3 |
| U-P026-2 | `global_contagion` 是否需独立 `degraded` 字段（而非日志 + `degraded_components`） | [RESEARCH_p026 §7](RESEARCH_p026_silent_exception_governance.md)；触发：消费方（web 面板 / 报告）需区分「计算失败」与「结果为空」 | pending（P-026 已加 `degraded_components`，字段粒度待消费方需求） | P3 |
| U-P026-3 | core 外 22 处静默捕获后续分批 | [RESEARCH_p026 §7](RESEARCH_p026_silent_exception_governance.md)；触发：任一模块出现可复现静默错误实例；HEAD `e6caafd` 复核构成吻合（`agents/` 11 / `filter/` 5 / `scripts/` 2 / `batch_backtest/` 2 / `strategy_evaluation/` 1 / `cli.py` 1） | **done（2026-11-15 转入 P-027）**：Step 1 取证触发成立（C 类 2 处 E2 复现）；U-P024-4 **不可合并**（pandas 2.2.3，`mypy filter` 0 error） | P3 |
| U-P026-4 | listener 类隔离容错是否需限流 / 告警 | [RESEARCH_p026 §7](RESEARCH_p026_silent_exception_governance.md)；触发：listener 频繁抛错导致日志刷屏 | pending（倾向不做，K 类保持） | P3 |
| U-P026-5 | 是否引入跨模块统一采集器（替代 sink 注入） | [RESEARCH_p026 §7](RESEARCH_p026_silent_exception_governance.md)；触发：出现第三个需要 sink 注入的模块 | pending（本批沿用 sink 注入，不建全局） | P3 |
| U-P026-6 | `EventLog.read()` 内层窄类型跳坏行是否纳入计量 | [RESEARCH_p026 §7](RESEARCH_p026_silent_exception_governance.md)；不在 `except Exception` 口径内 | **done（2026-11-13 由 P-026 顺带收口）**：`stats().skipped_lines` 已计量，CHECKLIST D1（构造期坏行 = 1）/ D3（read 1 有效 + 1 截断 ≥ 1）实测 | P3 |
| U-P027-1 | `agents/` 8 处同类静默路径（bare `except: pass` ×4 / 窄类型 `KeyError` `continue`·`return` ×3 / `LinAlgError` 静默伪逆 ×1） | [CHECKLIST_p027 §12.6](CHECKLIST_p027_silent_exception_governance_phase3.md)（Step 10 E4 AST 扫描，97 文件 21 项中 8 项落 `agents/`，不在 22 处 `except Exception` 口径内）；触发：任一处在实际运行中被复现为可观测错误，或发起「静默失败治理第四批」 | **done（2026-11-16 由 P-029 承接并完成）**：Step 1 E2 **8/8 复现**；Step 9 三批落地 **9 计量**（8 站点 + S3b `else`）；Step 10 异构终审 **99/A**；盲区扫描 `agents/` silent **9 → 1**（唯一残留 `research_team_v2.py:27` 显式 import 降级）；门禁 **722 passed**，批次关闭——见 [CHECKLIST_p029 §11](CHECKLIST_p029_silent_exception_governance_phase4.md) | P3 |
| U-P029-2 | `StrategyEngine` 次日订单簿的时序语义（`_next_day_orders` 无过期 / 无再平衡撤销 / 无卖量夹紧） | [IMPL_p029 §7](IMPL_p029_silent_exception_governance_phase4.md)；P-029 仅补计量（S6/S7），按「`return` 语义零变更」纪律未改重试与陈旧单行为；对照 `core/engine_v2.py` 的 P-014 三层防线（`_clamp_sell_quantity` L671 / `_cancel_next_day_orders` L690 / `is_expired`）**均未下沉**至 `agents/` | **done（2026-11-16 由 P-031 承接并关闭）**：四项缺陷全部修复（R2/R4 **P1** + R1/R3 **P2**）+ 中性空头腿显式降级；P-014 三层防线下沉 `agents/`；**722 → 731 passed** / golden 13 零重录；批次归档见 [SUMMARY_p031](SUMMARY_p031_strategy_engine_order_accounting.md) | P3 |
| U-P023-2 | `--check-untyped-defs` 是否纳入门禁 | [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)；原倾向「不纳入」 | **done（2026-11-12 由 P-024 承接）**：CI 与 adapter 双侧统一纳入，残差 0 | P3 |
| U-P023-3 | 零交易日回测的合法形态 | [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)；`_generate_results` 空快照守卫已统一 fail-fast（不区分原因） | pending（条件触发：真实数据出现空交易日集） | P3 |
| U-P023-4 | `EngineV3Vector` 信号路径 | [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)；P-024 取证：无因子时 `_precompute_signals` 用收盘价动量回填（非 `None`）+ `run()` 有 `dl is None` 守卫 → 无同形缺陷 | **done（2026-11-12 由 P-024 承接）**：[RESEARCH_p024 P12](RESEARCH_p024_ci_gate_alignment.md) | P3 |
| U-P024-1 | mypy 版本上限（`mypy>=1.5.0` 无上限） | [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)；CI 三版本各自回溯解析 | **done（2026-11-17 由 P-036 B0 承接）**：`mypy>=1.5.0` → **`mypy~=2.4.1`**（`>=2.4.1,<2.5`，patch 系列）；`uv lock` mypy 2.1.0 → **2.4.1**（+`ast-serialize`/`librt` 传递升级，+240/−163）；本地主环境同步 2.4.1；`uv lock --check` **exit 0**；门禁 `mypy core` **0 errors / 37 files**（`mypy filter` 直检 **21** 证明 override 仍是绿的唯一原因）；black 121 / pytest 760 持平。历史：**2026-11-12 注记（P-024）**：Step 9 一度判为「已触发」并提交 `745e2b7` 钉 `~=2.1.0`，经 X1-X4 隔离实验证伪——差异实为 **pandas 3.1.1 类型桩**；钉版已撤回，本项维持 pending。**2026-11-16 注记（P-028 台账去重）**：P-027 收口环境实测 **mypy 2.1.0**（`>=1.5.0` 无上限仍成立）、pandas **2.2.3**、numba 已安装但 `pyproject` 未声明（U-P021-2 维持）；门禁绿，维持「不钉」；**2026-11-17 注记（P-036 Step 1）**：CI 实际装 **mypy 2.4.1**，与 2.1.0 在同一配置下对 `core` 读数不同（**21 vs 0**），实证「不钉版本 → 门禁读数随 CI 解析漂移」；倾向由「不钉」改判为**钉上界**（U-P036-1），待 P-036 DESIGN 裁决。**2026-11-17 注记（P-036 Step 2 异构复审 F-S2-P036-2）**：上述「21 vs 0」对照混杂环境闭包变量——控变量实验（r1/r2 四象限）证实**干净缓存下 2.1.0 与 2.4.1 均渗入 filter 21 条**，版本非渗入变量；主环境「0」为未归因站点现象（O-P036-5）；钉版决策保留、理由改写（见上 done 记录） | P3 |
| U-P024-2 | CI 增加 `uv lock --check` 门禁（**承接 U-P021-1，单一跟踪源**） | [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)；U-P021-1 同源事项已于 2026-11-16（P-028）并入本行 | **done（2026-11-17 由 P-034 承接）**：独立 `lock-check` job（`astral-sh/setup-uv@v10.3.3` + `version: "0.11.14"` + `uv lock --check`，独立 step、禁 `\|\| true`、无 `continue-on-error`）；C4 实证门禁可红（临时改 numpy 约束 → exit 1）；自首跑 `43923154391` 起每个 CI run 的该 job 全部 success（P-034 阶梯 14 run + SUMMARY_p034 2 run）；`ARCHITECTURE §9.2` 同步订正 | P3 |
| U-P024-3 | mypy 检查面扩展（`cli.py`/`agents`/`web`/`scripts`） | [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)；本批只对齐口径，target 仍为 `core` | **done（2026-11-17 由 P-036 承接并关闭，Step 1 取证 → Step 9 落地）**：CI 等价口径实测 **129 errors / 25 files**（filter 豁免则 108；`agents` 94 占 73%）——见 [RESEARCH_p036](RESEARCH_p036_mypy_check_surface_expansion.md) 与 §3.41.1。**2026-11-17 更正（P-036 Step 4 异构复审 F-S4-P036-4）**：上述 129 为复刻 venv numpy 漂移到 2.5.5 的假口径——钉 `numpy==2.4.6` 重放 = **131 errors / 25 files**，真 CI 口径 = 本地 = 131（双口径收敛）；三批边界 B1 14 / B2 96 / B3 21，见 §3.41.5。**2026-11-17 关闭（P-036 Step 9）**：mypy target `core` → **10 面**（`core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`），CI + adapter 双载体同步，三版本 leg 0 error（run `44029888652`）；见 §3.41.10-§3.41.13 | **done** | P3 |
| U-P024-4 | `filter/` 在 pandas 3.x 下的 21 errors | [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)；CI 依赖集（pandas 3.1.1）实测 21 errors / 7 files（`universe_filter_clean.py` 13）；本批以 `filter.* ignore_errors` 声明越界 | **done（2026-11-17 由 P-036 Step 9 B3 承接并关闭）**：**2026-11-17 前提更正（P-036 Step 1）**：21 errors **与 pandas 版本无关**——pandas 2.2.3 与 3.1.1 均无 `py.typed`（`dev` extras 无 `pandas-stubs`），`mypy filter` 在本地 2.1.0 下同为 21 errors / 7 files；真实成因是 filter 自身的 21 条代码级类型错误（非类型桩）。**2026-11-17 注记（P-036 Step 2 强化）**：三环境直检（2.1.0/2.4.1 × pandas 2.2.3/3.1.1）**恒 21 errors / 7 files**——与 mypy 版本、pandas 版本、环境闭包全部无关；且干净缓存下 2.1.0 与 2.4.1 的 `core` 构建**均渗入**该 21 条（Step 1 原「2.4.x follow 行为」表述更正），见 [RESEARCH_p036](RESEARCH_p036_mypy_check_surface_expansion.md) R1'/R2'。**2026-11-17 关闭（P-036 Step 9 B3）**：21 条全部按代码级修复（13 mask/var-annotated + 返回注解 ×4 + 工厂 dict ×4 + 其余），`mypy filter`（无 override ini）`Success: no issues found in 10 source files`，`pyproject.toml` override 块整块删除且 `mypy core` 仍 0（run `44029888652` 三版本 leg 全绿） | **done** | P3 |
| U-P036-5 | 主环境 `core` 构建（filter 被 follow）恒 0 错误 vs 同环境 `filter` 直检恒 21——机制未归因 | [RESEARCH_p036 §5 R1'](RESEARCH_p036_mypy_check_surface_expansion.md) O-P036-5；site-packages 劫持 / 缓存复用 / MYPY_CACHE_DIR 已排除（verbose 证实解析本地文件）；该现象使「本地 0 / CI 渗入 21」假象维持自 P-024 以来全部时间，是两次误诊（pandas 桩、mypy 版本）的共同土壤 | pending（条件触发：mypy 版本升级 / 需要本地无 override 取证口径时深入排查；门禁语义不受影响——CI 走仓库 config 且无缓存残留） | P3 |
| U-P036-1 | mypy 版本上界（围堵门禁读数随 CI 解析漂移） | [RESEARCH_p036 §8](RESEARCH_p036_mypy_check_surface_expansion.md) 四元块；~~R1 实证 2.1.0 下 `core` = 0、2.4.1 下 = 21~~（**Step 2 更正**：该对照混杂环境闭包变量，见 R1'——干净缓存下两版本均渗入 21 条） | **done（2026-11-17，P-036 B0）**：`mypy>=1.5.0` → **`mypy~=2.4.1`**；锁与本地同步 2.4.1；`uv lock --check` exit 0；门禁 0 errors 持平，见 [RESEARCH_p036 §11](RESEARCH_p036_mypy_check_surface_expansion.md)；**理由经 Step 2 改写**为「锁 / CI / 本地三方一致 + 可复现性」（F-S2-P036-2） | P3 |
| U-P036-2 | `filter.* ignore_errors` 是否移除（21 条真实类型错误） | [RESEARCH_p036 §8](RESEARCH_p036_mypy_check_surface_expansion.md)；B0 已更正 override 注释归因 | pending（条件触发：B3 批修复 filter 21 条 → 0 后移除） | **done（2026-11-17，P-036 Step 9 B3）**：三条件顺序执行——无 override ini `mypy filter` = 0 → 删 `pyproject.toml` L116-123 整块 → `mypy core` 仍 0（37 files）；`Grep "filter\.\*"` = 0；见 §3.41.12 | P3 |
| U-P036-3 | 50 条 `union-attr` 是否全部真修（而非 `assert`/`cast` 掩盖） | [RESEARCH_p036 §8](RESEARCH_p036_mypy_check_surface_expansion.md)；样本含 `agent_framework.py` 6 处 `DataManager \| None → .get_adj_price` | pending（条件触发：B2 批 Step 3 逐条读码定性） | **done（2026-11-17，P-036 Step 9 B2）**：96 条按文件簇逐条定性并修复——45 条 union-attr 中仅 U-a 型（构造期已赋值 / setup 后赋值）用 `assert` 收窄（cli.py 1 / agent_framework 6 / style_drift 1 / multi_strategy 1 / strategies 3），其余均为根因收窄（guru_data 25 条一处消）或真缺陷修复（**C2** `tracker.cash` 静默影子属性 → `_cash`，F-S9-P036-4）；`agent_framework` / `multi_strategy_engine` 的 `DataManager | None` 6 处 assert 均能指出现有运行期前提（U-a）；见 §3.41.11 | P3 |
| U-P036-4 | `tools/` / `examples/` / `demo/` / `memory/` 是否纳入类型门禁 | [RESEARCH_p036 §8](RESEARCH_p036_mypy_check_surface_expansion.md)；本批未测（显式未覆盖项） | pending（条件触发：任一目录出现生产调用） | P3 |
| F-R5-P005-2 | ARCHITECTURE 图表幻觉残留（`Price数据/Macro/News/Alternative`） | P-005 RULE-5 §9.5；`Grep -i duckdb` 词元法对不含该词元的幻觉不可见 | **done（2026-11-11 由 P-020 承接）** | P3 |
| P-006 | ADR-016 补录或引用修正 | `__init__.py:3@1058cbb`、`core/__init__.py:3@1058cbb`、`pyproject.toml:79@1058cbb` 引用 ADR-016；`docs/DECISIONS.md` 当前仅 ADR-001~013；**T3**（纯文档一致性，零代码） | done（2026-11-09，T3 轻批：DECISIONS.md 补录 ADR-016（TD-1.2 轻量子包化，实施提交 `2848331`；ADR-014/015 编号跳空已注明）；三处代码引用保留；U-002 关闭） | P3 |
| P-007 | mypy 基线清理（`core` 168 errors / 20 files） | `python312 -m mypy --explicit-package-bases core`（E1，2026-11-04）；`mypy-check` 门禁当前预期 fail | done（2026-11-09 **层 A**：16 个非引擎文件 **26 → 0**；mypy **119 → 93**；修复 **4 处真实缺陷**（A-1 `remove_monitor` NameError / A-2 `analyze_market_contagion` AttributeError / A-3 `create_trigger` TypeError / A-4 `_load_auxiliary_data` 重复定义）+ 4 处 B 类防御；新增 3 项 smoke（507 → 510 passed）；`e0247ce`）。**2026-11-10 层 B 完成**：引擎三件套 `93 → 0`（engine_v2 54 / engine_v3_vector 26 / factory 13）+ 盲区口径 **102 → 8**（engine_v2 6 / data_v3 2，Q3=A 未打开）；协议真实化（`get_snapshots -> list[PortfolioSnapshot]`、`ITradeLog` 最小协议 + `trade_log` 只读 property）；2 项行为变更（空因子 fail-fast、`_generate_results` 未 setup 守卫）；新增 2 项 smoke（**514 → 516 passed**）；`mypy-check` 门禁 verdict=pass(0)，**U-006 按 Q4=B 保持挂起**，下一批次重评；主提交 `05af52f`，远端 CI run `42666962752` 三 job `509 passed, 1 skipped`） | P3 |
| P-008 | P0 环境规范化：U-001 + U-005 | 默认后端全量 `1 failed, 508 passed`，栈 `engine_v2 → analytics.generate_report → plt.figure → _backend_tk → tk.Tk`；默认 `python`=Anaconda 3.13.5 缺 `cvxpy`；CI 已存在 `.github/workflows/tests.yml`（未设 `MPLBACKEND`）；**T1**（Layer-1：`.github/workflows/` + README） | done（2026-11-05，Step 1-10 全通过；`06e9e11`；本地 U-001 达成、远端红为既有环境缺失见 P-009） | P1 |
| P-009 | CI 测试环境依赖缺失（远端红基线根因） | run `41970636863` @ `06e9e11`：3.10 `14 failed, 477 passed, 18 errors`。① `data/test_ashare/close.pkl` 被 `.gitignore:62`（`data/`）忽略 → **9 failed + 18 errors**（27 项数据测试）；② `tests/test_distillation_isolation.py:255-327` 硬编码 `F:\Coding\Factor_Trading_v3.0\gurus`（E3 @`06e9e11`）→ 4 failed；③ `numba` 不在 `pyproject.toml`（E1 `Select-String` 0 命中）→ 1 failed。历史 `df652f9` / `116426e` 两次运行同样 failure；**T1**（Layer-1：`tests/`） | done（2026-11-08 远端复核通过：run `42030484187` @ `33872c3` 三版本 `502 passed, 1 skipped`，U-007/U-001 关闭；Step 1-10 全记录见 §3.6） | P1 |
| P-010 | `DataManager` 辅助数据缺失时无安全默认值（行为缺口） | P-007 层 A D1 实证：`core/data.py` L184 死版本曾对停牌/行业/ST/市值数据提供安全默认值（全可交易 / 同行业 / 无 ST / 10 亿），唯一生效版本（原 L312）直接跳过加载，缺失文件时相应数据保持 `None`；**T1**（数据层行为变更，需构造缺失场景测试） | done（2026-11-09，T1 全流程：**幂等 guard**（`.industry` 3 次访问 3→1 次读盘）+ **停牌/ST 缺失按 `0=正常` 给默认值**（旧版 `True` 语义相反，已拒绝）+ 行业/市值保持 `None` 且 `industry` 注解改 `Optional`；新增 4 项测试 **510 → 514 passed**；mypy 93 / black 137 unchanged；**行为变更**：缺失停牌数据时 next-day 掩码末日为 False（已披露）；消费方零改动） | P2 |
| P-011 | 回测准确性验证、学术规范与基准比较（调研批） | 用户四问：如何判断回测准确性 / 如何验证建模·求解·程序·数据正确且符合学术规范 / 是否具备断点排查与模型·程序·数据 bug 诊断 / 是否需要 Qlib·Backtrader·VectorBT 基准比较。本仓取证：51 测试文件 516 用例、101 处数值断言、**无 golden 回归**、**无固化跨引擎差分**（V3 当日 close 成交 vs V2 次日开盘）、**无 PIT/数据 checksum**、Sharpe 双口径、无多重检验；断点排查「事后可查、过程不可查」；**T1**（若实施将触及 `tests/`、`core/`、`scripts/`、可能 CI） | done（2026-11-10，**Step 1-10 全通过**——Step 1 + Step 2 Review + §11 补充调研完稿：[RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md)（A1-A30 共 30 外部锚点 + 18 本仓事实 + 四层判据 + 方案矩阵；**U-1~U-4 与合并判定已按 §11.8 裁决通过**）；**Step 3 DESIGN 完稿**：[DESIGN_backtest_validation.md](DESIGN_backtest_validation.md)（D1-D9 / I1-I10 / B1-B6 六批；6 项设计期读码发现 F-D1~F-D6，其中 F-D1 收窄「全历史跨引擎对拍」为事件级等价、F-D5 收窄 trace 为复用 CSV）；**Step 4 Review 通过**（§13：P1×1 F-R1 + P2×1 + P3×2 全部回写；E2 探针证伪「年化分母不一致」并实证 V3 回撤缺锚点低估；异构基座 GLM vs DeepSeek）；**Step 5 IMPL 完稿**：[IMPL_backtest_validation.md](IMPL_backtest_validation.md)（T-0~T-14 / B1-B6 六批 / V1-V16 / 52 项新增用例 → 预期 602）；**Step 6 Review 通过**（IMPL §8：P2×3 F-I1~I3 + P3×2 全部回写；E2 证实 numba 0.65.1 默认参数可编译；DESIGN §4.1 签名回写 F-I5；异构基座 GLM vs DeepSeek）；**Step 7 CHECKLIST 完稿**：[CHECKLIST_backtest_validation.md](CHECKLIST_backtest_validation.md)（A/B/C/D/E/F/G/INV/RL/DOC 共 **76 项**，实测列全 `[待 Step 9]` 零预填；目标末态 602 passed / black 167 / 68 测试文件）；**Step 8 一致性 Review 通过**（CHECKLIST §8：13 链接 0 broken / 76 ID 连续 / 0 预填 / 断言链无未闭合标记 / 术语 7 组贯通 / V↔G 16 项全有归宿；P3×3 F-S8-1~3 已回写；异构基座 GLM vs DeepSeek）；**Step 9 实施完成**（B1-B6 六批提交 `cd6d619`/`26929c6`/`9ec9f7d`/`e59dee2`/`beaa3a1`/`b6bcee3` + 补丁 `d270511`；**609 passed**（550+59）/ black 167 unchanged / mypy 0（36 files）/ 盲区 4 errors 2 files / 68 测试文件；B3 Δ 表 + `change_report` `residual 0.0` 双证；实施期发现 **F-S9-1（P1，快照共享 Position）** + F-S9-2~F-S9-7；IMPL §9 已回填；远端 CI run `42768525717` 三 job 全绿，首跑 `42768109104` 的 1 失败已由 `7bcdd57` 修复）；**Step 10 ADD 审计通过**（CHECKLIST §9：Phase 0-4 全过、P1=0 / **P2=1 F-A1 metrics_method 未落地已修复 `a754a2d`** / P3=2 F-A2/F-A3 已回写；门禁 4 pass + `replay: 10 rows OK`；Iron Law 反例实证；RULE-5 异构复审留待独立会话；远端 CI run `42771058634`（@`955f06a`，含 F-A1 修复远端首跑）三 job success）；**RULE-5 异构复审完成并 pass**（2026-11-10，CHECKLIST §9.6：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash，E1-E5 独立重放 7/7 命中，0 P1/P2，2 项 P3 文档修正 F-R5-1/F-R5-2） | P2 |
| P-012 | 偏差防护与接口锁定（专项调研批） | 用户五问：幸存者偏差 / 前视偏差 / 复权 / ST·停牌 / 接口锁定。本仓取证：**无退市字段与动态股票池**（P1/P2）、**涨跌停掩码用当日收益却在次日开盘执行**（P5）、**`next_day_tradable` 用 `suspend.shift(-1)`**（P6）、**复权 forward/backward 疑似颠倒**（P7）、**成交价使用复权价**（P8）、**ST 阈值 4.8% 对 2026-07-06 主板 ST 10% 新规失效**（P11）、**14 Protocol + 7 ABC 双轨 + `UniverseConfig`/`UniverseFilterConfig` 双定义**（P14/P15）；**T1**（若实施触及 `core/data.py`、`filter/`、`core/interfaces.py`、`tests/`） | done（2026-11-10，Step 1-10 全通过：Step 1-8 见 §3.13；**Step 9 实施**——七批次 `a5ae5cc`/`4e2ab0b`/`ad40490`/`79c4dea`/`3717246`/`94018f2`/`6e5eeba` + 取证修正 6 提交，`550 passed` / black 153 / mypy 0，四份 `change_report.json` 双门通过，V1-V20 全过（V7 legacy `rtol=0`、V20 逆序回退 9/9）；**Step 10**——推送 + 远端 CI run `42694945888`（3 job `543 passed, 1 skipped`）+ **ADD 审计全过**（CHECKLIST §9：Phase 0-4 全过、P1/P2=0、P3×2 F-A1/F-A2 已修正；取证矩阵 E1-E5；RULE-5 异构复审留待独立会话）；CHECKLIST **74/74**；docs `5e866b9`/`a17ebce`） | P1 |

> 状态说明：上表仅有决策态 `pending`（未开工）。开工后执行态由工作记录派生，不在本表手写。

### 1.5 本批新增（2026-11-04 / 2026-11-05）

| 项目 | 文件 | 档位 | 状态 |
|------|------|------|------|
| Spec 搜索锚点规则增补 | `docs/SPEC_STANDARD.md` §十一；`docs/dev-log/DEV-LOG-002-search-anchor-rules-20261104.md` | T3（Layer-0，纯文档） | done（自查·单视角；`400394e`） |
| 方案对比 7 维矩阵规则增补 | `docs/SPEC_STANDARD.md` §11.8；`docs/dev-log/DEV-LOG-003-comparison-matrix-anchors-20261104.md` | T3（Layer-0，纯文档） | done（自查·单视角；`400394e`） |
| Spec_Runner 接入 | `scripts/spec_runner_adapter.py`、`tests/test_spec_runner_adapter.py`、`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_spec_runner_integration.md` | T1（Layer-1：scripts/ + tests/） | done（四文档 + 8 道 Review；`df652f9`） |
| P0 台账校正 | `docs/PROGRESS.md`、`docs/CHECKLIST_spec_runner_integration.md` | T3（Layer-0，纯文档） | done（session `factorv3-p0-ledger-fix-20261104`，5 行 replay OK） |
| P-008 环境规范化（U-001 + U-005） | `.github/workflows/tests.yml`、`README.md`、`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_env_normalization.md`、`docs/PROGRESS.md` | T1（Layer-1：workflows/；零生产代码） | done（2026-11-05，Step 1-10；session `factorv3-p008-env-norm-20261105` 12 rows replay OK；`step-review` fail 为 findstr 中文陷阱，seq 2 起 pass） |

---

## 2. 未决项登记（四元块）

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| U-001 | 默认 matplotlib 后端下 `pytest tests/` 全绿 | 每次本地或 CI 测试（未设置 `MPLBACKEND` 时） | 本地与 CI 统一设置 `MPLBACKEND=Agg`；或修复 Python312 的 Tk 组件 | E1 |
| U-002 | `docs/DECISIONS.md` 出现 ADR-016，或三处代码引用改为已登记 ADR | 下次文档一致性更新 / P-006 开工 | 补录 ADR-016（TD-1.2 轻量子包化决策），保留代码引用 | E1 |
| U-003 | TD-3 Stage 3 的调研清单更新为实测值（6 examples + 4 tests，无 `core/__init__.py` re-export） | P-001 Step 1 调研启动 | 在新 RESEARCH 中更新清单后，再进入设计 | E1 |
| U-005 | 测试命令固定解释器，或各解释器依赖一致（`cvxpy` 可导入） | 每次本地或 CI 测试 | 命令中显式使用 Python312 路径；不默许 `python` 解析到 Anaconda 3.13.5 | E1 |
| U-006 | `mypy-check` 门禁转绿（`core` 0 errors） | mypy 清理批次启动 / 每次门禁链验收 | 先清理 P-007（168 errors），再收紧；门禁保持如实 fail。**2026-11-10 注记（P-007 层 B 收口）**：P-007 层 A+B 完成，`mypy --explicit-package-bases core` = 0、门禁 verdict 已机械转 **pass**；但按用户裁决 **Q4=B（2026-11-09）本项不关闭**——收紧 `mypy-check` 命令口径（如 `--check-untyped-defs`）另行评估（残差 8），下一批次重评。**2026-11-12 注记（P-024）**：口径已收紧为 `--check-untyped-defs`，且 CI（去 `|| true`）与本地 adapter 双侧同形，判据达成——本项关闭（见下方关闭注） | E1 |
| U-007 | CI `Run tests` 三版本全绿（U-001 远端判据） | P-009 修复后 / 每次远端验收 | 先修 P-009（数据夹具策略 + 路径相对化 + 可选依赖声明），再重跑；不得用 skip 掩盖缺失（RULE-3） | E1（run `41970636863`） |
| U-008 | numba JIT 路径在 CI 有覆盖 | CI 出现 numba 相关回归却无法拦截 | 暂不新增 optional job；以 C1（`importorskip`）保留本地执行，后续按需评估。**2026-11-17 注记（P-034）**：与 §1.4 U-P021-2 同源，统一由后者**单一跟踪**，本行不再单独触发 | E1（`pyproject.toml` 无 numba） |

> **已关闭（2026-11-04）**: U-004 —— [SPEC_STANDARD.md](SPEC_STANDARD.md) 头部已声明 `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1 为冲突时的权威源（@`400394e`），判据达成。
> **已关闭（2026-11-05，P-008）**: U-005 —— 收敛口径按 [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md) §5.3 落定并达成：「README 写明测试解释器选择方式」。README `## 🧪 Testing` 节落地（`py -0p` / `py -3.12` / 临时 `MPLBACKEND=Agg`），V2 断言 PASS（E2）；CI 矩阵显式 3.10-3.12（S4）。原倾向「命令固定 Python312 路径」仅适用于本机门禁（`unit-tests` gate 已固定）。
> **本地达成，远端未达成（2026-11-05，P-008）**: U-001 —— `MPLBACKEND=Agg` 全量 `509 passed`（E1 × 3：30.18s / 32.23s / 31.99s）；CI 侧 job 级 `env` 已落地（`.github/workflows/tests.yml` @`06e9e11`），**但远端 run `41970636863` = failure**：根因是数据夹具被 `.gitignore` 忽略（**9 failed + 18 errors**）、[`tests/test_distillation_isolation.py`](tests/test_distillation_isolation.py) 硬编码 Windows 路径（4 failed）、缺 `numba`（1 failed），与本批改动无关（历史 `df652f9`/`116426e` 同样 failure）。U-001 **不关闭**，转 U-007 跟踪；Tk 根因仍不在范围（[RESEARCH](RESEARCH_env_normalization.md) §1.1）。
> **已关闭（2026-11-08，P-009）**: U-007 —— run [`42030484187`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42030484187) @ `33872c3` 三 job success，每版 `502 passed, 1 skipped`（3.10 17.46s / 3.11 17.22s / 3.12 19.55s），与 C-1 推演（477−6+27+4=502，模块级 skip 计 1）逐字一致；27 项数据测试计入 passed、零 skip（RULE-3 达成）；`Prepare test fixture` 每版成功（`0.005s`，296051/296436 B）。
> **已关闭（2026-11-08，P-009）**: U-001 —— 本地 Agg `509 passed`（E1×3）+ 远端三版本全绿（run `42030484187`），判据「固定 Agg 下全绿（本地 + CI）」达成；Tk 组件本身仍未修复（不在判据内，见 [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md) §1.1）。
> **映射说明**: U-002 由 P-006 关闭；U-003 作为 P-001 Step 1 的输入，不单独占工作流。
> **已关闭（2026-11-09，P-006）**: U-002 —— [DECISIONS.md](DECISIONS.md) 出现 ADR-016（§决策状态说明前，TD-1.2 轻量子包化）；三处代码引用保留（E1 `git grep -n "ADR-016"` = 代码 3 处 + DECISIONS 条目）。
> **已关闭（2026-11-12，P-021）**: U-P005-4 / U-P005-5 —— `uv.lock` plain 重建（`--check` exit 1 → 0，`+1207/−2`）且 Parquet 引擎维持「不显式声明」；实测与决策详见 §3.25。
> **已关闭（2026-11-12，P-022）**: U-P005-2 —— Factor_DB 四项缺陷全部修复（B1-B4），重开写入崩溃 / 静默覆盖 / 删除复活 / 双份存储均转绿；详见 §3.26。
>
> **已关闭（2026-11-12，P-023）**: **U-006-R**（mypy 盲区 4 errors 2 files → 0，四项窄化）与 **F-A1**（注入式工作流静默空回测 → `run()`/`_generate_results()` 双 `RuntimeError` 守卫）；**F-A1 来源订正**：原登记「P-012 CHECKLIST §11」失准——P-012 的 `F-A1` 是同名另一发现（`limit_check_price` 文档列名，§9.2 L306），静默空回测的权威来源为 **P-007 CHECKLIST §9.3 L210**（编号撞车，F-S2-P023-1/F-S8-P023-1 记录）；详见 §3.27。
> **已关闭（2026-11-12，P-024）**: **U-006**（`mypy-check` 口径收紧为 `--explicit-package-bases --check-untyped-defs core`，且 CI 与本地 adapter 同形）、**U-P023-2**（`--check-untyped-defs` 纳入双侧门禁，残差 0）、**U-P023-4**（`EngineV3Vector` 无「信号 None → 静默空回测」同形缺陷，取证见 [RESEARCH_p024 P12](RESEARCH_p024_ci_gate_alignment.md)）；同时修复 CI 假门禁（`|| true` 自初版 `c7a0f29` 存在，`tests.yml` L46 现真实阻塞）；详见 §3.28。

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

**执行进度（2026-11-09）**：

- **立项（2026-11-09）**: P-001 启动；U-003 作为 Step 1 输入
- **Step 1 调研（已完成 2026-11-09）**: [RESEARCH_td3_stage3.md](RESEARCH_td3_stage3.md) 形成；3 个 T1 外部来源（S1 PEP 594 / S2 Python `warnings` / S3 PEP 387，均直读原文）+ 16 条本仓事实（P1-P16）；**U-003 关闭**——实测「6 examples + 4 tests = 10 个活跃 import + `core/__init__.py` 1 处注释」，`cli.py` 零 `core.engine` 引用（Stage 2 已完成）；发现 g2/g3 两项 golden 测试依赖 V1、两个 visual_trace 脚本 0 收集；初步倾向：移除 A（直接删除）/ examples A（迁移 `create_default_engine`）/ tests A1（删 g2/g3 + 删死脚本）/ 文档 A（只改活文档）；连带影响 测试 `509→507`、文件 `50→48`
- **Step 2 Review（已完成 2026-11-09）**: 独立复核 pass（RESEARCH §6.1）；E1 15 项重跑 + S1/S2/S3 二次直读逐字命中（F3 无降级）；**5 项 P3 修正**（F-R1 README 计数为 4 行含 509；F-R2 §3.3 A1 算式 505→507；F-R3 `_run_engine_v1` 为 7 个 patch；F-R4 ARCH 6→3 / DECISIONS 2→1 精确口径；F-R5 回放须固定 Python 3.12.10 解释器）；**0 项 P1/P2 阻断**
- **Step 3 设计（已完成 2026-11-09）**: [DESIGN_td3_stage3.md](DESIGN_td3_stage3.md) 完稿（D1-D6 决策 + 被拒方案与代价、删除边界精确到行、6 examples 分两类迁移契约、tests 清理契约、活文档同步、回退点）；量化基线实测：black `75→72`、mypy `168→119`（`core/engine.py` 占 49）；发现并修正手动装配脚本 `build_trigger` 形参错误；改动面 = 1 个生产文件删除（724 行）+ 2 个 0 收集脚本删除 + 6 examples + 2 tests + 4 处注释/docstring + 7 份文档
- **Step 4 设计 Review（已完成 2026-11-09）**: 独立复核 pass 通过（DESIGN §9）；**1 项 P2 + 5 项 P3** 发现已处置——F-D4（P2）手动装配脚本 L92-96 五个顶层导入包/模块均不存在（脚本今天就 ImportError，先存缺陷）→ 新增派生决策 **D7** 迁移时一并修复 5 行导入为 `core.*` 权威路径 + R11 登记回归风险；F-D1 属性计数 10→11、F-D2 V3 命令通配符不展开改逐文件、F-D3 CODE_WIKI 禁盲改改分级处理、F-D5 `_run_engine_v1` 范围 L294-316、F-D6 A4′ 状态修正；12 项 E-Review 复核 9 命中，0 项阻断
- **Step 5 实施规划（已完成 2026-11-09）**: [IMPL_td3_stage3.md](IMPL_td3_stage3.md) 完稿——T-0~T-9 任务分解（依赖图 + 单提交原则）；**F5 先失败记录**：RED 5 项（V1 存在 / import 10 / 收集 20 / 文件 50 / README 509）+ R6 删除后 2 collection errors；GREEN 9 项（507 passed / 48 files / 18 collected / black 72 / mypy 119）；逐任务给出前后文本（6 examples 含 D7 的 5 行导入与 `build_trigger` 形参修正、2 tests、4 处注释、5 份文档）；8 条低效/危险操作排除表；回退点按任务列明
- **Step 6 实施 Review（已完成 2026-11-09）**: 独立复核 pass 通过（IMPL §9）；**6 项 P3** 发现已回写——F-I1 CODE_WIKI 覆盖不全（`BacktestEngine` 类名 10 处 + L23 目录锚点，编辑点 15→25）、F-I2 迁移文本缩进契约、F-I3 `build_trigger` 签名前缀、F-I4 空行契约、F-I5 删除前工作区干净检查、F-I6 T-8 时序拆分；关键验证：T-3.5 的 `dm.trade_dates` 作用域成立（dm 与 engine 同函数）、`cli.py --help` 轻量可行、R6「2 errors」推断成立；0 项阻断
- **Step 7 验收清单（已完成 2026-11-09）**: [CHECKLIST_td3_stage3.md](CHECKLIST_td3_stage3.md) 完稿——**43 项**（A 功能 10 / B 测试 9 / C 性能 4 / D 文档 8 / E 兼容安全 6 / F 质量 6），逐项 DoR/DoD + 证据出口 + 锚点；实测列全部 `[待 Step 9]`（D7 待 Step 8、D8/F6 待 Step 10），**零预填**（RULE-1）；§7 门禁链预期（probe/unit-tests pass，black 72 / mypy 119 预期 fail）；§8 取证矩阵、§9-§12 空态
- **Step 8 一致性 Review（已完成 2026-11-09）**: 机械校验 pass（CHECKLIST §9）——四文档互引 **14 条链接全可解析**；键值计数矩阵（`507 passed` 五文档全命中 / `48 files` / 门禁基线 `119`+`168` / `75→72`+`168→119` DESIGN↔IMPL 无冲突）；CHECKLIST 零预填合规（`[待 Step` 57 处，✅ 5 处全为规则文本）；旧值 `509 passed` 逐行角色判定（基线/旧→新/历史，无当前预期值残留）；断言延续链七组贯通；**1 项 P3 已回写**（F-S1 A3 补 py_compile 判据）+ 1 项 P3 判定角色分工（F-S2 IMPL 不直接链 RESEARCH）；0 项阻断
- **Step 9 TDD 实施（已完成 2026-11-09）**: 先 RED 后删除再迁移——T-0 RED 6 项（engine 存在 `True` / V1 import 11 行（10 活跃 + `core/__init__.py` 注释）/ 收集 `20` / 文件 `50` / README `509` 4 行 / R6）；T-1~T-2 删除 3 文件（`core/engine.py` 747 行 diff、`test_visual_trace.py` 255、`test_visual_trace_v2.py` 192）；**R6 实测修正（F-9-1）**：1 个 collection error（`test_rebalance_exits`，模块级 import）+ 1 个 runtime failure（`test_compatibility::test_new_import_paths`，import 在函数体内），非 IMPL 预测的「2 errors」；T-3 六个 examples 迁移（5 个 `create_default_engine` 5 文件 6 调用 + 手动装配 `BacktestEngineV2` 含 D7 修复）；T-4/T-5 tests 清理（7 个模式 0 命中、`patch` 保留、compat 改 `engine_v2` 仍 6 项）；T-6 注释 5 行/3 文件（`agents/multi_strategy_engine.py:64` 历史表述保留）；T-7 活文档 ARCH 3 / WIKI 25 编辑点（残存仅 2 处「已移除」注记）/ DECISIONS 1 / README 5 行（D4 4 行 + F-9-2 目录树残行）/ CHANGELOG 1 条；T-8 台账与 TD-3 Stage 3 注记；**T-9 GREEN**：V1 `False`、V2 `0`、V3 `py_compile exit 0`、V4 **`507 passed, 82 warnings in 20.32s`**、V5 `48`、V6 `18 collected`、V7 black **`72`** / mypy **`119`**（预期 fail）、V8 `demo.py exit 0`（5.4s）+ `cli.py --help exit 0`、E3 `ModuleNotFoundError: No module named 'core.engine'`（exit 1）；门禁 4 条 `verdict`：probe pass / unit-tests pass / black-check fail(72) / mypy-check fail(119)，`replay` **9 rows OK**；净删除 **1245** 行（新增 25 / 删除 1270，core+tests+examples numstat）
- **Step 10 ADD 审计（已完成 2026-11-09）**: CHECKLIST §11 四阶段 + 盲区扫描——**Phase 0** DESIGN/IMPL 不可审计措辞 **0**；**Phase 1** D1-D7 与 §3.3 逐条落到 A1-A9/E2（`core/engine.py` 不存在、5+1 examples、3 删除、5 注释行、7 份文档、无 shim、D7 五行导入）；**Phase 2** 代码 diff 11 文件 **新增 25 行逐字吻合** IMPL §3、文档 hunk 计数 = 25/4/5/1/1/1/1 与 DESIGN 精确动作一致、numstat 对账（代码 25/1270、文档 64/111）；**Phase 3** 新增行全部可归属 T-3~T-8，盲区扫描 **1 项设计外改动**（README L359 目录树残行 → F-9-2 已修），保护路径 12 项 diff 空；**Phase 4** 语义核对：V1 不可达（E3）+ 无 shim + 目标未降级（不是「测试绿」而是删除生效 + 迁移完整）+ expected-fail 未伪装（black 72 / mypy 119 仍记 fail）+ demo 数值变化已入 CHANGELOG；审计时点复跑不变式 `507 passed in 29.52s`、V1 import 边界化计数 **0**（`import core.engine_v2` 等 5 处为假阳性）；**P1/P2 = 0，P3 = 5 项（F-9-1~F-9-5）全部处置**；CHECKLIST **43/43 达成**（41 项 Step 9 回填 + D8/F6 Step 10 回填）；门禁 4 条 + `replay: 9 rows OK`；**P-001 → done（`ccd0c98`）**
- **远端 CI 复核（已完成 2026-11-09）**: `ccd0c98` + `35427f0` 已推送 `origin/master`；run [`42598775895`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42598775895) @ `35427f0` **三 job success**，3.10 `500 passed, 1 skipped`（12.44s）/ 3.11 同（17.93s）/ 3.12 同（18.80s），与「507 − 7 numba」推演逐字一致
- **RULE-5 异构第二会话复审（已完成 2026-11-09）**: GLM-5.3-Flash（异构基座，与前序 DeepSeek 实现会话不同模型家族）按 RULE-5 指引独立重跑不变式/全量/门禁 + `git show` 行号回溯 + 盲区重扫（CHECKLIST §11.3）——抽查 7 项全命中、无静默降级、无盲区漏报；**3 项 P3 文档残留修正**（F-5-1/F-5-2 CHECKLIST 过期限定表述、F-5-3 RESEARCH §6.1 补 RULE-4 标注）；复审 pass，0 P1/P2
- **范围约束**: 删除 `core/engine.py`（724 行 / 29910 B）；迁移 6 个 examples；tests 处置 g2/g3 + 2 个 0 收集脚本；活文档 ARCHITECTURE / CODE_WIKI / DECISIONS / README 计数 + 本台账；历史条目不改（CHANGELOG 仅追加 `[Unreleased]` 新条目）
- **验收口径（推演，Step 3 定稿）**: 本地全量 `507 passed`（A1 口径）；`tests/test_*.py = 48`；活文档无未标注的 V1 路径；远端 CI 3.10/3.11/3.12 `500 passed, 1 skipped`（507 − 7 numba）
- **回退点**: 单提交整体 `git revert`；`core/engine.py` tracked（P15），可完整恢复

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

### 3.5 P-008（P0 环境规范化）执行序与进度

判定为 **T1 完整管线**（`.github/workflows/tests.yml` 属 Layer-1）：

- **Step 1-2（已完成 2026-11-04）**: [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md) 形成，7 个外部来源 + 8 条 E1 事实通过来源验证
- **Step 2 Review（已完成 2026-11-05）**: 独立复核 pass 通过（RESEARCH §6.1）；2 项发现已修复（E3 绑定、Tk 根因表述与 P4/P5 矛盾）
- **Step 3 设计（已完成 2026-11-05）**: [DESIGN_env_normalization.md](DESIGN_env_normalization.md) 完稿（D1-D5 决策 + 被拒方案与代价、锚点表、精确变更面、回退点）
- **Step 4 设计 Review（已完成 2026-11-05）**: 独立复核 pass 通过（DESIGN §11）；2 项 P3 发现已修复（F-D1 假设 A1-A3 显式携带、F-D2 README 分隔约定说明）
- **Step 5 实施规划（已完成 2026-11-05）**: [IMPL_env_normalization.md](IMPL_env_normalization.md) 完稿（T-0~T-5 任务分解、配置契约、README 节全文、低效排除表、V1-V4 验证与红→绿序）
- **Step 6 实施 Review（已完成 2026-11-05）**: 独立复核 pass 通过（IMPL §5）；3 项 P3 发现已修复（F-I1 提醒注释精确化、F-I2 后端解析时机与触发链对齐并回写 DESIGN、F-I3 回退措辞）
- **Step 7 验收清单（已完成 2026-11-05）**: [CHECKLIST_env_normalization.md](CHECKLIST_env_normalization.md) 完稿（A1-A9 / B1-B6 / C1-C4 / D1-D6 / E1-E5 / F1-F5，逐项 DoR/DoD + 证据出口 + 锚点；Step 8-10 空态）
- **Step 8 一致性 Review（已完成 2026-11-05）**: 机械校验贴读数（互引链接 17 条全 True、键值计数矩阵、断言延续）；无 P1/P2 矛盾，1 项 P3 已修复（F-S1：D1 措辞与机械读数对齐）；4 项派生需求登记（D-R1~D-R4）
- **Step 9 实施（已完成 2026-11-05）**: `tests.yml` 加 job 级 `MPLBACKEND: Agg` + 命令改 `python -m pytest`（+3/-1）；README 新增 Testing 小节 + 3 处计数（+40/-3）；红→绿 RED 3 → GREEN 0（反例 5/5 拦截）；全量 `509 passed`；`gate unit-tests` pass（seq 9，32.23s）；2 项 P3（F-9-1 行数偏差、F-9-2 F1 自引用）已处理
- **Step 10 ADD 审计（已完成 2026-11-05）**: 四阶段全过（Phase 0-4，盲区扫描 0 项设计外改动）；取证矩阵 9 类手段回填（CHECKLIST §8）；门禁链复跑——probe pass / unit-tests pass（seq 9）/ black-check fail 基线 75 无漂移（seq 11）/ mypy-check fail 基线 168 无漂移（seq 12）；`replay: 12 rows OK`；U-005 关闭、U-001 本地达成；30 项验收 29 ✅ + 1 `[未入仓-不可重放]`（C4）
- **提交推送与远端复核（已完成 2026-11-05）**: `06e9e11` 已推送；远端 run `41970636863` **failure**（3.10 `14 failed, 477 passed, 18 errors`，3.11/3.12 fail-fast），失败项全部指向既有环境缺失（P-009），非本批改动；U-001 远端判据未达成，不关闭
- **待执行**: 远端复核已完成（2026-11-05，run `41970636863` failure）；下一步按依赖链启动 **P-009**（CI 环境缺失，T1）→ 修复后重跑远端关闭 U-001/U-007；`black-check` / `mypy-check` 维持基线 fail（P-003 / P-007）
- **范围约束**: 零生产代码；仅 `.github/workflows/tests.yml`、`README.md`、本台账与四文档
- **验收口径**: U-001 = 测试在固定 `MPLBACKEND=Agg` 下全绿；U-005 = 文档写明测试解释器选择；不宣称“Tk 已修复”
- **回退点**: 还原 `tests.yml` 与 README，删除本批文档

### 3.6 P-009（CI 测试环境缺失）执行序与进度

判定为 **T1 完整管线**（`tests/` 与 `.github/workflows/` 属 Layer-1）：

- **立项（2026-11-05）**: P-009 登记（P1）；新增 U-007（CI 全绿判据）、U-008（numba CI 覆盖）
- **Step 1 调研（已完成 2026-11-05）**: [RESEARCH_ci_test_env.md](RESEARCH_ci_test_env.md) 形成；4 个 T1 外部来源（S1 pytest skipping / S2 Numba version support / S3 pathlib / S4 gitignore）+ 14 条本仓事实（P1-P14）；可行性探测：合成夹具（50×100，`adj=1`/`industry=1`/`suspend=0`，seed 42）→ 27 项真实数据测试全过（E1）；裁决 A1（CI 生成合成夹具）+ B1（仓库相对路径）+ C1（`importorskip`）
- **Step 2 Review（已完成 2026-11-05）**: 独立复核 pass 通过（RESEARCH §6.1）；2 项 P3 发现已修复（F-R1 gitignore 行号 L64→L67、F-R2 P13 证据等级改 `[未入仓-不可重放]`）
- **社区锚点补充（2026-11-05）**: RESEARCH §2.1B 新增 S4-S9 社区案例锚点（S4 gitignore T1；S5/S6 numba Discourse T2，S6 标注 `[单源-待二核]`；S7/S8 T4 线索已回溯 T1；S9 Python Discourse T3 对照）；检索通道 stackexchange 配额异常，按降级链切 WebSearch；**新发现**：本仓 `!data/.gitkeep` 负模式实际无效（`git check-ignore -v` 证实被 L62 `data/` 命中、`data/.gitkeep` 不存在）→ §4 新增 R9（设计不走 gitignore 负模式路线）；§6.1 追加补充复核 pass（F-S1 状态行、F-S2 结论计数，两项 P3 已修复）
- **Step 3 设计（已完成 2026-11-05）**: [DESIGN_ci_test_env.md](DESIGN_ci_test_env.md) 完稿（D1-D6 决策 + 被拒方案与代价、锚点表、四文件精确变更面、回退点）；关键细化：夹具脚本 CLI 契约（无 `--force` 时 exit 2，对应 R8/P14 覆盖防护）、输出数据契约（7 个 pkl 与测试断言的逐项映射）、CI step 位置（安装后测试前、不带 `--force`）、D6 显式拒绝测试数据路径锚定（实测 6 处，超最小修复面）
- **Step 4 设计 Review（已完成 2026-11-05）**: 独立复核 pass 通过（DESIGN §11）；3 项 P3 发现已修复（F-D3 `engine_v3_vector` 降级机制表述失准 + CI 计数推演补全 477−6+27+4=502、F-D4 补 PyYAML 本地校验依赖、F-D5 black gate 范围注记）；12 项 E1/E3 复核全命中
- **Step 5 实施规划（已完成 2026-11-05）**: [IMPL_ci_test_env.md](IMPL_ci_test_env.md) 完稿（T-0~T-6 任务分解 + 生成算法逐字实现 + V0-V7 验证断言 + 反例覆盖 + 红绿执行序 + 回退点）；**规划期预演（隔离 `%TEMP%` 目录）**：拟定算法生成 7 个 `(100,50)` pkl（296037 B）→ 27 项数据测试 `27 passed in 12.06s`；新增外部锚点 S10-S15（pytest #4599 `reason` 4.6.0 / NumPy Generator 流兼容 / pandas pickle 跨大版本 / GITHUB_WORKSPACE 默认 cwd / Custos importorskip 实践 T3 / 合成数据 CI 指南 T4）；**2 项 DESIGN 修正**：C-1 模块级 skip 计数 `7 skipped`→`1 skipped`（pytest 9.0.3 探针：3 测试模块报 `1 skipped`）、C-2 `importorskip` 默认 `exc_type=ImportError` 会连 numba 版本不匹配一起 skip（原「不兜底」表述不成立），均已回写 DESIGN §11 留痕
- **Step 6 实施 Review（已完成 2026-11-05）**: 独立复核 pass 通过（IMPL §5）；**1 项 P2 + 2 项 P3** 发现已修复（F-I1 V1/V2b `%TEMP%` 路径错位——照原文执行 V2b 得 `9 failed, 18 errors` 而非 `27 passed`，`data` 子目录层级修正；F-I2 argparse usage 错误 exit 2 撞码加注；F-I3 PROGRESS 行数标注）；10 项检查项通过，`importorskip` 签名运行时证实含 `reason`/`exc_type`
- **Step 7 验收清单（已完成 2026-11-05）**: [CHECKLIST_ci_test_env.md](CHECKLIST_ci_test_env.md) 完稿（A1-A10 功能 / B1-B8 测试 / C1-C4 性能 / D1-D6 文档 / E1-E5 兼容 / F1-F6 质量，逐项 DoR/DoD + 证据出口 + 锚点）；实测列一律 `[待 Step 9]`（RULE-1 禁预填）；A3 绑定夹具基线快照（7×42419 B / `2026-11-05 13:31:40`），A7 绑定 distillation 19 项，A9 绑定 `len(steps)=7` 与索引 4
- **Step 8 一致性 Review（已完成 2026-11-05）**: 机械校验 pass（CHECKLIST §9）；五文档互引 **32 条链接全可解析**；键值计数矩阵 + `7 skipped` 残留逐行判定（4 处全为修正/历史记录，无当前预期值）；「27 项不得 skip」五处同口径；1 项 P3 发现已修复（F-S1 C-1 同步列表漏列 §11，IMPL/DESIGN 两处补列）；2 项派生需求登记（D-R1 A3 快照权威载体、D-R2 计数 0 角色分工规则）
- **Step 9 TDD/实施（已完成 2026-11-05）**: RED 4 条（空目录 `9 failed, 18 errors in 8.01s` + 静态 `5/0/0`）→ GREEN 6 条；新增 `scripts/prepare_test_fixture.py`（137 行，7×`(100,50)`/296037 B/0.006s，`--force` 缺失 exit 2 且本地夹具 `UNCHANGED=True`，27 项 `9.05s`）；5 处硬编码 → `GURU_DIR`（0 残留，19 passed）；numba 模块级 `importorskip`（本地 7 passed）；`tests.yml` +1 step（`len(steps)=7`，索引 4）；全量 `509 passed in 21.45s`；门禁 seq 7 unit-tests **pass**（23.06s）、seq 8 black **fail 75**、seq 9 mypy **fail 168**（均与基线一致）；4 项 P3（F-9-1 行数预估 +4、F-9-2 脚本 137 行、F-9-3 black 合并、F-9-4 A2 竖线）
- **Step 10 ADD 审计（已完成 2026-11-05）**: 四阶段全过（Phase 0 措辞扫描 0 命中；Phase 1-3 design↔code 双向对照 + 盲区扫描 **0 项设计外改动**、保护路径 diff 空；Phase 4 目标未降级 + fail 未伪装）；门禁链复跑——probe pass / black-check fail 基线 75 无漂移（seq 10）/ mypy-check fail 基线 168 无漂移（seq 11）；`replay: 11 rows OK`；39/39 验收项达成（CHECKLIST §12）；累计 P3 13 项全部留痕，0 阻断；**状态：待提交**——提交后需 ① 补绑 E3 hash ② push 触发远端 CI ③ 按 C-1 推演核对 `502 passed, 1 skipped` 判定 U-007/U-001
- **提交推送（已完成 2026-11-05）**: `33872c3`（10 files，+1379/−8）已推送；E3 hash 补绑回写 CHECKLIST §8（留待本批提交）
- **远端复核（已完成 2026-11-08）**: run [`42030484187`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42030484187) @ `33872c3` = **success**，三 job 全绿（1m21s / 1m15s / 1m20s）；每版 `Prepare test fixture` 成功 → `collected 502 items / 1 skipped` → **`502 passed, 1 skipped`**（17.46s / 17.22s / 19.55s）——与 C-1 推演**逐字一致**；27 项数据测试零 skip（RULE-3）；夹具体积 3.10=296051 B、3.11/3.12=296436 B（矩阵依赖版本差异，job 内生成即读，S12 未触碰）；annotations 仅 Node 20 弃用/`ubuntu-latest` 迁移预告（非失败）。**U-007 关闭、U-001 关闭**（RULE-6 绑 run id）；U-008 留作哨兵（numba 降级路径不再被 CI 执行，触发条件未发生）。P-009 done
- **范围约束**: 零生产代码；改动面为 `tests/test_distillation_isolation.py`、`tests/test_numba_jit_performance.py`、新增 `scripts/prepare_test_fixture.py`、`.github/workflows/tests.yml`、四文档与台账
- **验收口径**: CI 3.10/3.11/3.12 `Run tests` 全绿（numba 文件允许 skip）；本地保持 `509 passed`；27 项数据测试在 CI **不得 skip**
- **回退点**: `git revert` 本批提交；本地夹具由 `scripts/prepare_test_data.py` 可从 `E:` 重建

### 3.7 本批（P-002 + P-006 文档一致性）档位与进度（2026-11-09）

判定为 **T3 轻批**（Layer-0：docstring-only + 纯文档；零运行时行为、零门禁波动；循 §3.4 先例不出四件套）：

- **改动面**: [core/config_v2.py](../core/config_v2.py)（module docstring 追加冻结声明块，零代码行变更）、[DECISIONS.md](DECISIONS.md)（ADR-013 后补录 ADR-016）、本台账；捎带入库 [P001_FINAL_REPORT.md](P001_FINAL_REPORT.md)（P-001 闭环存档，按用户指示随本批提交）
- **P-002 内容**: TD-2 方案 C「冻结+标注」落地——⚠️ FROZEN (TD-2) 声明 + 冻结期间约束（不新增功能 / 不接生产 / 新模块禁止 import）+ 再激活条件（配置层统一立项并经 SPEC 评审）；口径对齐 ARCHITECTURE「⚠️ 冻结（零生产引用）」
- **P-006 内容**: ADR-016 补录（TD-1.2 = `2848331` 轻量子包化：双 `__init__.py` 轻量化 + 最小子包化；ADR-014/015 全仓不存在，条目内注明历史编号跳空）；三处代码引用保留
- **验证（E1）**: `py_compile core/config_v2.py` exit 0；`import core.config_v2` OK；全量 `507 passed, 82 warnings in 33.02s`；black `72 files` / mypy `119 errors in 19 files`（基线无漂移）；`git grep -n "ADR-016"` = 代码 3 处 + DECISIONS 条目；config_v2 冻结标注 grep 2 行命中
- **门禁 session**: `factorv3-p002-p006-doc-20261109`——probe **pass** / unit-tests **pass** / black-check **fail(72)** / mypy-check **fail(119)**（均与基线一致）；`replay: 4 rows OK`
- **U-002 关闭**（判据「DECISIONS.md 出现 ADR-016」达成）；P-002 / P-006 → done
- **回退点**: 还原 `config_v2.py` docstring 与 `DECISIONS.md` 至 `53f3024` 版本，删除台账本小节

### 3.8 P-003（TD-9 black 全量重排）执行序与进度（2026-11-09）

判定为 **T1 完整管线**（批量 style-only，覆盖 `core/`、`tests/` 等 Layer-1 路径；TD-9 原文要求独立窗口）：

- **Step 1 调研（已完成 2026-11-09）**: [RESEARCH_td9_black.md](RESEARCH_td9_black.md)；3 个 T1 外部来源（S1 black Stability Policy / S2 Using Black with other tools / S3 git-blame，均直读原文，F3 无降级）+ 18 条本仓事实（P1-P18）；**关键实证**：可行性预演——126 文件重排后 `507 passed in 25.20s`、black 幂等 135 全绿、mypy 119 不变（工作区已还原）；范围候选 A（core+tests 72）/ B（全量 126）移交 DESIGN
- **Step 2 Review（已完成 2026-11-09）**: 独立复核 pass；**2 项 P3** 已回写——F-R1 TD-9 原文数值偏差（79 文件/7872 行 → 实测 77/135 文件、21199 改动行）、F-R2 §1.3 分目录构成初稿错误（core 26/3、tests 46/2 → 实测 **27/2、45/3**）；0 阻断
- **Step 3 设计（已完成 2026-11-09）**: [DESIGN_td9_black.md](DESIGN_td9_black.md)；**D1-D7**：全量 126 文件 / `black~=26.0` 锁定 / 门禁 `black --check .` / `.git-blame-ignore-revs` 两笔提交 / CI 不加 black step（如实声明未覆盖）/ 默认 exclude / 提交策略；V1-V12 验证契约
- **Step 4 Review（已完成 2026-11-09）**: 独立复核 pass；**3 项 P3**——F-D1 变更行数口径不自洽（core+tests 9169 → 全量 **+11145/−10054**）、F-D2 遗漏 `adapter.py` L66 门禁命令（语义改动须单列）、F-D3 缺 D5/保护路径证据出口（补 V10/V11）
- **Step 5 实施规划（已完成 2026-11-09）**: [IMPL_td9_black.md](IMPL_td9_black.md)；T-0~T-9 + RED-1~5 + 9 条危险操作排除表
- **Step 6 Review（已完成 2026-11-09）**: **1 项 P2 拦截**——F-I1「朴素 AST 等价」前提不成立：实测 `core/factory.py` 重排后 `ast.dump` 比较 **False**，根因 black 清理 docstring 行尾空白（改变 `Constant.value`）；修正为 **docstring 逐行 `rstrip` 归一化后比较**（实测 True）+ 排除 adapter.py + 新增 R8；另 2 项 P3（F-I2 暂存范围、F-I3 commit message 声明）
- **Step 7 验收清单（已完成 2026-11-09）**: [CHECKLIST_td9_black.md](CHECKLIST_td9_black.md) **43 项**（A10/B9/C4/D8/E6/F6），实测列全部占位（RULE-1 零预填）
- **Step 8 一致性 Review（已完成 2026-11-09）**: 机械校验 pass——**25 条链接 0 broken**、43 验收项、零预填（45 处占位、0 处预填 ✅）、7 条断言延续链贯通；**3 项 P3**——F-S1/S2 上游头部未同步 P17-P18/V12、F-S3 P12 口径歧义
- **Step 9 实施（已完成 2026-11-09）**: RED 5 项 → `black .` **126 reformatted / 9 unchanged（5.1s）** → 立即回归 **`507 passed, 82 warnings in 19.35s`** → 门禁扩展 → **GREEN**：`black --check .` exit 0 / **125/125 AST 等价**（排除 adapter）/ mypy **119 errors 不变** / numba `7 passed` / `__doc__` 两文件 `21 passed` / 收集 507 / 48 文件 / `.github/` diff 空 / diff **+10992/−9903**（容差内）；门禁 4 条：probe pass / unit-tests pass / **black-check pass（首次转绿）** / mypy-check fail(119)；`replay: 4 rows OK`；**1 项设计表述缺陷**（F-9-1：V11 将 engine_v2/factory 误列为「零 diff」，实为重排范围内 → 改为「允许格式 diff、语义由 V12 保」）
- **Step 10 ADD 审计（已完成 2026-11-09）**: 四阶段全过——**Phase 0** 不可审计措辞 0 命中（3 处「不确定面」为拒绝理由非断言）；**Phase 1** D1-D7 逐条落地（A1-A10/F3/E1 为证）；**Phase 2** 提交 1 实测 134 文件 = 126 py + 8 non-py，与 DESIGN §3 精确一致，语义改动仅 pyproject L64 + adapter L66 两行；**Phase 3** 盲区扫描 **0 项设计外改动**；**Phase 4** 目标未降级（真实合规 135 unchanged，非绕过）、mypy fail(119) 未伪装、CI 边界与 blame 限制如实声明、V12 AST 提供独立语义证据；**P1/P2 = 0，P3 = 13 项**全部处置；CHECKLIST **43/43**（42 ✅ + E3 附条件 ⚠️ 附实测数）
- **提交与远端复核（已完成 2026-11-09）**: 两笔提交 `4098629`（134 文件，style + 2 处语义）+ `17fc69d`（3 文件，零 py）已推送 `080f3a3..17fc69d`；run [`42609336249`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42609336249) 三 job success（3.12 1m25s / 3.11 1m17s / 3.10 58s），3.12 job 实测 `500 passed, 1 skipped, 408 warnings in 18.43s`（与 507−7 numba 推演一致）；`gh run watch --exit-status` 透传 exit 0
- **范围约束**: 126 py 文件纯格式 + 2 处语义改动（`pyproject.toml` L64 版本锁定、`adapter.py` L66 门禁范围）+ 4 文档 + 台账；`.github/`、`[tool.black]`、`[tool.isort]` 零改动；isort 未执行
- **验收口径**: `black --check .` exit 0；全量 507 passed；mypy 119 不劣化；AST 125/125 等价；CI `500 passed, 1 skipped`（**格式校验 `[未在 CI 覆盖]`**）
- **回退点**: 提交 1 `git revert`（提交 2 独立）；两笔连续 revert 可完全恢复

---

### 3.9 P-007 层 A（非引擎 mypy 清理）执行序与进度（2026-11-09）

判定为 **T1 完整管线**（`core/` 16 个非引擎文件；含 4 处真实缺陷修复与 1 处 Optional 防御，属 Layer-1 运行时行为面）：

- **Step 1 调研（已完成 2026-11-09）**: [RESEARCH_p007_mypy_layera.md](RESEARCH_p007_mypy_layera.md)；26 个 error 全量分类——**A 类真实缺陷 4 处 / 6 errors**、**B 类潜在缺陷 4 处 / 4 errors**、C 类纯注解 16 errors；A 类实证：A-1 `remove_monitor` 引用未定义 `RiskAction`（`NameError`）、A-2 `analyze_market_contagion` 调用不存在的 `evaluate`（`AttributeError`）、A-3 `create_trigger` 3 位置参数（`TypeError`）、A-4 `data.py` 重复定义且生效版本丢失安全默认值；A-3 的覆盖缺口实证为 `tests/test_engine_plugins.py:325-329` 被整段注释
- **Step 2 Review（已完成）**: 0 阻断，3 项 P3（F-R1 A-1 表述精度 / F-R2「潜在语义改动」/ F-R3 `name-defined` 引用）已回写
- **Step 3 设计（已完成）**: [DESIGN_p007_mypy_layera.md](DESIGN_p007_mypy_layera.md)；**D1-D9**：删死代码不改行为（P-010 另立）/ A-1 改无注解赋值 / A-2 改 `monitor()` / A-3 改 `dates=` / B 类 `assert`+`isinstance` / C 类 `cast` 禁 `type: ignore` / 3 项 smoke / `config_v2` 单点 / 引擎零改动 + U-006 不关闭
- **Step 4 Review（已完成）**: 0 阻断，2 项 P3（F-D1 `factor.py` 修法含糊 / F-D2 `global_contagion:192` 实为补注解）已回写
- **Step 5 实施规划（已完成）**: [IMPL_p007_mypy_layera.md](IMPL_p007_mypy_layera.md)；T-0~T-9 + RED-1~5 + 递减序（26→25→22→21→20→16→0）+ 9 条排除表
- **Step 6 Review（已完成）**: **3 项 P2 事实性修正**——F-I1 `portfolio.py:300` 报错对象实为 `cov_matrix`（非 `expected_returns`，原方案改完 error 不消失）、F-I2 `live_bridge.py` 全文无 `AssetType`（须新增运行期 import）、F-I3 5 个 `cast` 目标文件均未导入 `cast`；另 4 项 P3（F-I4 `stats: dict[str, Any]` 替代 int 截断 / F-I5 `factor.py` 行号与 `extend` 遗漏 / F-I6 smoke 构造具体化 / F-I7 P-010 必登记）
- **Step 7 验收清单（已完成）**: [CHECKLIST_p007_mypy_layera.md](CHECKLIST_p007_mypy_layera.md) **49 项**（A10/B10/C6/D10/E7/F6），实测列全部占位（RULE-1 零预填）
- **Step 8 一致性 Review（已完成）**: 机械校验 pass——**11 条链接 0 broken**、49 验收项、49 个验收行 0 预填；**1 项 P2**（F-S1 DESIGN 总览 D2 与正文/IMPL 自相矛盾）+ 2 项 P3（F-S2 D8「1 处修正」未计 cast 导入 / F-S3 A-4 不得写成 Fixed）已回写
- **Step 9 实施（已完成 2026-11-09）**: RED 5 项（26 / 119 / 507 / 135 / 1）→ T-1~T-6 递减核对（119→118→115→113→109→93）→ T-7 新增 3 项 smoke → **GREEN**：非引擎 **0 error** / mypy **`93 errors in 3 files`**（54/26/13 与基线逐字一致）/ **`510 passed`（17.84s）** / 新测试 `3 passed` / `black --check .` **136 unchanged** / 引擎三件套 **diff 空** / `type: ignore` 仍 1 处 / 测试文件 49 / diff **16 文件 +36/−87**
- **门禁 session**: `factorv3-p007-mypy-layera-20261109`——probe **pass** / unit-tests **pass** / black-check **pass** / **mypy-check fail(93，如实)**；`replay: 4 rows OK`
- **Step 10 ADD 审计（已完成 2026-11-09）**: 四阶段全过——**Phase 0** 不可审计措辞 0 命中；**Phase 1** D1-D9 逐条落地（A/B/D 证据列）；**Phase 2** +36 行 36/36 可归属 T-1~T-6、−87 = −48 死代码 + −12 `__main__` + −27 替换；**Phase 3** 盲区扫描 **0 项设计外改动**；**Phase 4** 目标未降级（4 处缺陷有根因探针 + 正向 smoke 双证）、mypy fail(93) 未伪装、边界如实（P-010 / `-O` / 探针时点）；**P1/P2 = 0，P3 = 11 项**全部处置；CHECKLIST **49/49**
- **提交与远端复核（已完成 2026-11-09）**: 单笔 `e0247ce`（23 文件，+1211 −88）已推送 `8082784..e0247ce`；run [`42614740925`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42614740925) 三 job success（3.12 1m06s / 3.11 1m04s / 3.10 53s），3.12 实测 `503 passed, 1 skipped`（= 510 − 7 numba）
- **范围约束**: 仅 `core/` 16 文件 + 1 个新测试文件 + 4 文档 + 台账；引擎三件套、`pyproject.toml`、`.github/` 零改动；零新增 `# type: ignore`；`data.py` 仅删 48 行死代码（未合并安全默认值）
- **验收口径**: 26 → 0；119 → 93（改善 21.8%）；507 → 510；`mypy-check` 仍 fail，**U-006 不关闭**，层 B（93 errors）另立批次
- **回退点**: 单笔提交 `git revert` 即可完全恢复（含测试与文档）

---

### 3.10 P-010（辅助数据缺失处理）执行序与进度（2026-11-09）

判定为 **T1 完整管线**（`core/data.py` 数据层行为变更；含 1 处已披露的行为变更）：

- **Step 1 调研（已完成 2026-11-09）**: [RESEARCH_p010_aux_defaults.md](RESEARCH_p010_aux_defaults.md)；15 条本仓事实 + 4 类判定——**D-1 幂等缺陷（实测 `.st` 3 次 → 6 次读盘；100 次 → 206 次 / 144.90 ms）**、**D-2 类型契约缺陷（`suspend` 声明 DataFrame 实返 None）**、D-3 停牌/ST 缺默认值（P3）、D-4 行业/市值无可辩护默认值（非缺陷）；**关键反证**：旧版停牌默认 `True` 按 `1=停牌` 语义等于「全市场停牌」，旧默认值不可复制
- **Step 2 Review（已完成）**: 0 阻断，3 项 P3（F-R1 D-3 降级 / F-R2 量化读数 / F-R3 方案 B 覆盖声明）已回写
- **Step 3 设计（已完成）**: [DESIGN_p010_aux_defaults.md](DESIGN_p010_aux_defaults.md)；**D1-D7**：幂等 guard / 停牌·ST 默认 `0` / 行业·市值保持 `None` / 消费方零改动 / 4 项测试 / **D6 末日可交易性变更披露** / 幂等边界；V1-V8
- **Step 4 Review（已完成）**: **1 项 P2**（F-D1 初稿遗漏 `_build_next_day_tradable_mask` 末日 True→False 的行为变更）+ 2 项 P3 已回写
- **Step 5 实施规划（已完成）**: [IMPL_p010_aux_defaults.md](IMPL_p010_aux_defaults.md)；T-0~T-6 + RED 5 项 + 8 条排除表
- **Step 6 Review（已完成）**: 0 阻断，3 项 P3（F-I1 assert 与 R4 矛盾 / F-I2 行业·市值 warning 遗漏 / F-I3 夹具表述）已回写
- **Step 7 验收清单（已完成）**: [CHECKLIST_p010_aux_defaults.md](CHECKLIST_p010_aux_defaults.md) **36 项**（A9/B7/C9/D6/E5）
- **Step 8 一致性 Review（已完成）**: **11 条链接 0 broken**、36 项验收、0 预填；2 项 P3（F-S1「仍 514」表述 / F-S2 C9 DoD 二义）已回写
- **Step 9 实施（已完成 2026-11-09）**: **实施期发现 1 项**——原计划的幂等测试用 `.st` 不可行（D2 后 `.st` 恒非 None，不再触发重载）；改用 `.industry`（保持 None）作判据，实测 guarded **1 次** / guard-off 模拟 **3 次**。GREEN：`514 passed`（24.26s）/ 新测试 `4 passed` / mypy **93** / black **137 unchanged** / 消费方 diff 空 / `data.py` **+33 −2**
- **门禁 session**: `factorv3-p010-aux-defaults-20261109`——probe pass / unit-tests pass(514) / black-check pass(137) / mypy-check **fail(93，如实)**；`replay: 4 rows OK`
- **Step 10 ADD 审计（已完成 2026-11-09）**: 四阶段全过（Phase 0 措辞 0 命中 / Phase 1 D1-D7 逐条落地 / Phase 2 diff **+33 −2** 与 69 行测试量级一致 / Phase 3 盲区 0 / Phase 4 真实缺陷有计数与探针双证、D6 行为变更明示）；**P1/P2 = 0，P3 = 8 项**全部处置；CHECKLIST **36/36**
- **提交与远端复核（已完成 2026-11-09）**: 单笔 `ac48a22`（8 文件，+883 −3）已推送 `e6ed18d..ac48a22`；run [`42620788610`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42620788610) 三 job success，3.12 实测 `507 passed, 1 skipped`（= 514 − 7 numba）
- **范围约束**: 仅 `core/data.py` + 1 个测试文件 + 4 文档 + 台账；`filter/`、`core/factor.py`、`core/config.py`、`pyproject.toml` 零改动；零新增 `# type: ignore`
- **行为变更（D6，如实声明）**: 停牌数据缺失时 `_build_next_day_tradable_mask` 末日由 True → **False**（有数据路径的既有语义，末日无「次日」）；其余掩码数值不变；仓库夹具不受影响
- **回退点**: 单笔提交 `git revert` 即可完全恢复

---

### 3.11 P-007 层 B（引擎 mypy 93 errors 清理）执行序与进度（2026-11-09 起）

判定为 **T1 完整管线**（`core/` 三个引擎相关文件 + 共享接口契约）：

- **Step 1 调研（已完成 2026-11-09）**: [RESEARCH_p007_mypy_layerb.md](RESEARCH_p007_mypy_layerb.md)；基线 `93 errors in 3 files`（engine_v2 54 / engine_v3_vector 26 / factory 13），错误码 `union-attr 59 / index 16 / no-any-return 9 / arg-type 4 / name-defined 2 / var-annotated 1 / valid-type 1 / misc 1`；24 条本仓事实（P1-P24）+ 16 条外部锚点（15 T1 / 1 T3）；**关键发现**——A-1 `_composite_signal` 为 None 可从公开 API 到达（`factor_files=[]` → 100 条 ERROR 被 `except Exception` 吞 → 空回测，E2 探针）；A-2 `_generate_results()` 无 setup 守卫（`AttributeError`）；B-1 `IPositionTracker.get_snapshots` 声明 `list[dict]` 与 `PositionTracker` 实际返回不符；B-2 `IExecutionSimulator` 缺 `trade_log`；**`setup()` 零注解 → 函数体不受检查**（`--check-untyped-defs` 另曝 9 条）
- **Step 2 Review（已完成 2026-11-09）**: 独立 pass——复算 10 项全过（mypy 93 / 102 / 216、分组统计、探针 ×5、引文 14 条逐字命中）；文献验证表 15 已验证 / 1 未验证（A16 PyPI 直取失败，T3 不承载结论）；**1 项 P2（F-R1 P22 失实：首轮 Grep `glob="tests/*.py"` 静默空匹配，path 直指后实测 factor_files 37 行/10 文件、`_composite_signal` 8 行、`setup()` 9 处；6 处测试手动赋值 `_composite_signal` 反而加强 A-1 的测试缺口结论）+ 6 项 P3（方案编号改名 FC/PR/ST、A-2 行措辞、A6 版本 3.12.15、X1 机制精确化、A4 升级已验证 + mypy stable 版本号降级未验证、本机 2.1.0 版本差声明）全部已回写**；Q1-Q4 待裁决
- **Q1-Q4 补充调研（已完成 2026-11-09）**: [RESEARCH_p007_mypy_layerb.md](RESEARCH_p007_mypy_layerb.md) §12；按 `DECISION_MATRIX_TEMPLATE.md` v1.0 七维矩阵（成本/收益/可维护性/兼容/升级潜力/短期/长期）+ 5 条新增外部锚点（PEP 20 / PEP 387 / mypy Getting started / SemVer 2.0.0 / ignore-without-code）；**新增事实**——零信号回退在 `MinVarianceOptimizer` 下会建任意组合（E2：选中 `['000001','000002']` 权重和 1.0，仅等权滤零）；4 个具体组件**全部**不满足各自协议（含 `ExecutionSimulator.execute_order` 独立冲突）；`core/` 未注解函数仅 4 个（116 行）；CI mypy 步骤 `|| true` **永不失败**。**推荐 Q1-A fail-fast / Q2-A 最小真实化 / Q3-A 不打开 / Q4-A 关闭 U-006**
- **Q1-Q3 深度分析（已完成 2026-11-09）**: §13；新增 9 条外部锚点（PEP 544 / Liskov & Wing 1994 / mypy `existing_code` / arXiv `2109.05049` / arXiv `1704.00778` / Fowler《Fail Fast》/ pydantic Settings / SO 77002238 / SO 68471392）+ P34/P35；三问逐条「支持/反驳」对账，方向不变：Q1-A、Q2-A（`trade_log` 细化为 `ITradeLog` 最小协议，+9 行）、Q3-A（附未来 B 的 4 步实施顺序）。关键澄清：`setup()` **从未调用** `cfg.validate()`（P34），Q1-A 是新增守卫而非接线
- **裁决记录（2026-11-09）**: **Q1 = A fail-fast / Q2 = A 最小真实化（含 `ITradeLog` 最小协议）/ Q3 = A 不打开 / Q4 = B 保持开启**（用户）——U-006 不在本批关闭，本批只交付 93 → 0 与门禁 verdict 变化；Q1-Q3 收敛，可进入 Step 3 DESIGN
- **Step 3 DESIGN（已完成 2026-11-09）**: [DESIGN_p007_mypy_layerb.md](DESIGN_p007_mypy_layerb.md)；D1-D9 决策（D1 fail-fast 落在 `setup()` 入口以避免部分初始化；D2 `get_snapshots` + `ITradeLog`；D3 `_generate_results` 守卫；D4/D5/D6 局部别名窄化 78 条；D7 factory 13 条；D8 2 项 smoke）；精确变更面 **4 个 core 文件 + 1 测试**；验证契约 V1-V11（`mypy core` 93→0、`--check-untyped-defs` 仍 9、`514→516 passed`）；风险 R1-R9
- **Step 4 DESIGN Review（已完成 2026-11-10）**: 独立 pass——复算 8 项（含 `--check-untyped-defs` 102/4 files 拆分 engine_v2 +7 / data_v3 +2 → V3「9 in 2 files」成立）+ **E2 探针 ×2 验证设计形态**；**1 项 P1（F-D1：`trade_log: ITradeLog` 可变属性触发 PEP 544 不变性，实现方不符 → 改为只读 property 成员，探针实证 Sim/MockSim 双通过）+ 3 项 P3（L762 物理双行口径注记、`__future__ annotations` 去引号统一、补 V12 测试文件数）全部回写**；V 契约扩为 V1-V12；**Step 4 通过**
- **Step 5 IMPL（已完成 2026-11-10）**: [IMPL_p007_mypy_layerb.md](IMPL_p007_mypy_layerb.md)；T-0~T-8 任务分解 + **递减算术 93 → 91 → 86 → 39 → 13 → 0**；逐方法 `self.<field>` 引用计数（engine_v2 替换 48 处 / 消除 47 条；v3 替换 27 / 消除 26）；别名放置规则（有早退守卫的方法，别名下移到守卫之后，零行为 delta）；外部案例 4 条（mypy Protocol 不变性 / mypy narrowing+cast / Dropbox 4M 行渐进迁移 / pytest match）+ 本仓层 A 递减先例；零新增依赖
- **Step 6 IMPL Review（已完成 2026-11-10）**: 独立 pass——事实核实 14 项（含 base/flag 错误清单逐行 diff）；**1 项 P2（F-I1：V3/RED-3 的 GREEN 目标失实——flag 增量 7 条中 L231 随 T-2 协议修正消失，批后残差 = 8（engine_v2 6 + data_v3 2）而非 9/7；已回写 IMPL + DESIGN V3/D2 + RESEARCH U-3 注记三处）+ 3 项 P3（L194 物理双条口径、D6 `signal_matrix` 命名双向对齐、black 折行实施期残余）**；**Step 6 通过，可进入 Step 7**
- **Step 7 CHECKLIST（已完成 2026-11-10）**: [CHECKLIST_p007_mypy_layerb.md](CHECKLIST_p007_mypy_layerb.md)；**54 项验收**（A 行为 7 / B 接口 7 / C 窄化 7 / D 测试 6 / E 验证口径 12 / F 台账 7 / G 排除 8），每项绑定 DoD 证据出口与上游锚点；**Step 7 只定义「怎么算做完」，实测列全部 `[待 Step 9]`（RULE-1 零预填）**；§10.1 统计表结构就位（Step 10 回填纯整数并满足逐行/总计算术）
- **Step 8 一致性 Review（已完成 2026-11-10）**: 独立 pass——机械校验（链接 12 条 0 broken / 验收行 54 含✅为 0 / 计数矩阵 12 项 / 断言延续链 8 条全贯通 / 术语 5 组一致）；**1 项 P3（F-S1：DESIGN D9 汇总行「仍 9」与 V3 修正后的 8 矛盾，Step 6 漏改 → 已回写 DESIGN D9）**；其余 Grep 命中均为合法历史引用（IMPL F-I1 引旧文本、RESEARCH U-3 差值原始定义带注记）；**可进入 Step 9 实施**
- **Step 9 实施（已完成 2026-11-10）**: T-0 RED（mypy `93 errors in 3 files` / 盲区 `102` / 新 smoke `2 failed`——① `data\close.pkl` 缺失的 `FileNotFoundError`、② `AttributeError: 'NoneType'...get_snapshots`，与预期「DID NOT RAISE」形态不同，按实测记录）→ **递减逐格命中**：T-2 91（52/26/13）→ T-3 86（47/26/13）→ T-4 39（0/26/13）→ T-5 13（0/0/13）→ T-6 **0**；GREEN：`mypy` 29 文件全绿 / 盲区 `8 errors in 2 files` / `516 passed` / black `138 files unchanged` / `type: ignore` 1 / 测试文件 51 / `gate mypy-check verdict=pass`。**1 项 P2（F-S9-1：D1 无条件 fail-fast 使 13 个既有用例失败——注入 `factor_pipeline`+`factor_combiner` 后以空 `factor_files` 调 `setup()` 再手工注入信号；守卫收紧为「默认因子路径且空 `factor_files`」才抛，已回写 DESIGN D1 + IMPL T-1）**；1 项 P3（F-S9-2 black 折行）；CHECKLIST 实测回填 **47/54 ✅**（余 7 项属 Step 10 台账/提交/CI）
- **Step 10 ADD 审计（已完成 2026-11-10）**: 四阶段全过（Phase 0 可审计 / Phase 1 D1-D9 全实现带行号 / Phase 2 无静默偏离——2 项偏离均已登记回写 / Phase 3 盲区扫描 **47 hunk / 379 改动行 0 项设计外** / Phase 4 意图达成）；取证矩阵 10 行回填（CHECKLIST §9.2，E1-E4，无 E5）；门禁链统一 session `factorv3-p007-mypy-layerb-20261110`——probe / unit-tests / black-check / mypy-check **4 gate 全 pass**，`replay: 4 rows OK`；**2 项 P3**（F-A1 豁免路径残留盲区——注入 pipeline+combiner 后忘记注入信号仍静默空回测，与 U-3 并列下批次评估；F-A2 发现记录核查非跨批次模式，不新增 discoveries 条目）；CHECKLIST §10.1 统计与 §10.2/10.3 签字回填
- **提交推送与远端复核（已完成 2026-11-10）**: 主提交 `05af52f`（11 files，`+2362/−130`）已推送 `762ff5f..05af52f`；run [`42666962752`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42666962752) **三 job success**，3.10/3.11/3.12 均 `509 passed, 1 skipped`；本地 516 − CI 510 = 6 项差与层 A/P-010 恒定差同构（numba 模块 `importorskip`），本批 2 项 smoke 在 CI 真实执行；docs 回填 `54/54 ✅`（CHECKLIST）+ hash/run 绑定
- **本批收口**: P-007 层 A+B 全部完成（`core/` mypy **168 → 0**，全仓基线 119 → 93 → 0）；`mypy-check` 门禁 verdict=pass；**U-006 按 Q4=B 保持挂起**（含 U-3 盲区残差 8 与 F-A1 豁免路径盲区，下一批次一并重评）；远期候选 P-004 / P-005 待用户指令

### 3.12 P-011（回测准确性验证、学术规范与基准比较）执行序与进度（2026-11-10）

判定为 **T1 完整管线**（调研批；若实施将触及 `tests/`、`core/`、`scripts/`，可能含 CI）：

- **立项（2026-11-10）**: 用户四问——①如何判断回测准确性；②如何验证建模/求解/程序/数据正确且符合学术规范；③是否具备断点排查与模型·程序·数据 bug 诊断；④是否需要 Qlib / Backtrader / VectorBT 作为基准比较、如何处理
- **Step 1 调研（已完成 2026-11-10）**: [RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md)；**16 条外部锚点**（A1-A16：Qlib PIT/复权/CI、Backtrader Testing Guide、VectorBT Contributing、LEAN Regression Testing、NautilusTrader parity、Arnott-Harvey-Markowitz 22 问、PBO/CSCV、DSR、Harvey-Liu-Zhu t>3.0、Open Source Asset Pricing、蜕变测试 review、pandera、可复现三条件、确定性 replay）+ **18 条本仓事实**（P1-P18，E1/E3/E4 逐条绑定 `@05af52f`）
- **关键发现**: ①准确性四层判据中 **L1/L2（组件级、内部对账）强、L3（跨实现差分）弱、L4（统计级）半缺**；②`test_08_no_future_info_leakage` 名不副实（只查 NaN 形状，不查时间方向）；③`test_v3_engine_integration.py` 声称「V3 与 V1/V2 可比」但 0 个跨引擎数值对比；④V2 次日开盘成交 vs V3 当日 close 成交，**两引擎默认不可比**，任何外部框架对拍必须先做口径映射；⑤断点排查「事后可查（176 处日志 + EventLog + 4 诊断出口）、过程不可查（无逐日 trace / 无 debug 开关 / 数据无 schema）」；⑥Sharpe 双口径（rf=3% vs rf=0）、无多重检验、`benchmark` 仅暂留接口
- **产出**: 四层判据表 + 逐问诊断 + 四组方案 7 维矩阵（Q1 准确性 / Q2 学术规范 / Q3 断点排查 / Q4 基准比较）+ L0-L3 建议路线 + **U-1~U-4 四元块**（待裁决）
- **Step 2 Review（已完成 2026-11-10，独立 pass）**: E1（`05af52f..2c34283` core/filter/tests 零 diff；`Glob tests/test_*.py`=51；`breakpoint/pdb`=0）+ E3 抽检 5 处全命中（Sharpe rf=3% `analytics.py:88-92` / V3 rf=0 `engine_v3_vector.py:170-174` / `benchmark` 暂留 `config.py:371` / `test_08` 无时间方向 / V3 当日 close 成交）+ 计数矩阵（A=16 / P=18 / 文献 14 连续）；**F-R4（P3）§5.2 幸存者偏差行补 P-012 U-1 裁决联动注**；F-R5（初判 A16 等级不一致）读回核实为**误报核销**。**P1=0，通过**
- **Step 2 补充调研（已完成 2026-11-10，§11）**: P0 决策门剩余项外部检索——**A17-A30 共 14 新锚点 / 文献 15-28**（SciPy2020 差分 property、Barr oracle 综述、metamorphic ML、golden master、OSTI 科学软件测试、**美联储 SR 11-7 + SR 26-02（2026 取代）**、Baker 2016 Nature 复现调查、**NautilusTrader DST 确定性契约**、MLflow manifest 三件套、backtrader/vectorbt 实测对拍（默认参数差 5.5%、「一致是 manufactured」）、成交模型不一致根因、量子模拟器交叉验证、**变更分解受控实验 arXiv 1805.10978**）
  - **U-1 → V-A**：L1/L2 先行（参考实现差分 + metamorphic 属性）；golden 直接锁现状会焊死 P-012 已证实缺陷（A20）
  - **U-2 → S-A + S-C 首批**（SR 26-02 使独立验证+回测对照成合规基线）；S-B 挂起至对外发布需求（无 trials log 则 DSR/PBO 无数据可算）
  - **U-3 → D-A 逐日 trace + D-B run manifest**（A25 DST 契约 / A26 MLflow 三件套）；D-C 交互式不采纳；trace 与六层归因共用 dump
  - **U-4 → X-A 口径映射 + 内核差分**（A27/A28：默认参数对拍必败；A30① 基础任务交叉验证形态）；X-B 仅被明确要求时重审
  - **合并判定 → 独立两个 DESIGN、P-012 先行**（A30② 受控实验支持按概念拆分；合并使六层归因与 Step 8 计数矩阵跨基线失效）
  - **U-6~U-9**：交叉引用 P-012 §12（证据已足，不重复）；D-B manifest 与 U-6 manifest 字段兼容已确认
- **待办（P0 决策门剩余）**: U-1~U-4 与合并判定**确认**（推荐已给出，见 §11）；确认后 P-012 先进 Step 3 DESIGN，P-011 DESIGN 待 P-012 L2/L4 落地后启动
- **Step 3 DESIGN（已完成 2026-11-10）**: [DESIGN_backtest_validation.md](DESIGN_backtest_validation.md)；证据时点 `@dc71c1a`（P-012 收官后 HEAD，`550 tests collected`）。**D1-D9**：六批切分（B3 唯一行为批次 = 报告口径统一；其余零数值）+ 不变量模块 + 参考实现差分 + 事件级等价 + 指标单一口径 + 偏差声明 + run manifest + trace 复用 P-012 `LayerDumper`。**I1-I10** 不变式（NAV/持仓/成本/收益恒等 + V3 三式 + manifest 可恢复 + 口径唯一 + trace 完备）。**设计期读码发现（E3 @`dc71c1a`）**：F-D1 V2 无「关闭 T+1」配置（`engine_v2.py:933`）→ 全历史逐日对拍不可实现、降级事件级等价并登记 U-D2；F-D2 V2 整数股 + `value_buffer=0.985`（`target_positions.py:51/130-134`）；F-D3 ~~年化分母 `252/n` vs `252/(n-1)`~~（**Step 4 E2 证伪**：两引擎均 252/N；真实差异 = rf 口径 + 回撤符号相反 + V3 缺锚点，见 Step 4 记录）；F-D4 `commission_min=5` 在零费率下仍生效（`execution.py:355-356`）；F-D5 层 dump 为 CSV 且 `pyarrow` 未声明；F-D6 V3 信号不经 `FactorPipeline`。**替代方案** 5 个被否决/延后（golden / 外部对拍 / 全历史对拍 / 交互式调试 / parquet trace）。**未决项 U-D1~U-D4**（golden 时点 / V2 同日收盘模式 / trace 保留策略 / manifest CI 完整性）
- **Step 4 Review（已完成 2026-11-10，独立 pass，DESIGN §13）**: 审查基座 GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash（RULE-5 异构满足）。**E1/E3 锚点复核**：F-D1/F-D2/F-D4/F-D5/F-D6 全命中（F-D1 原引 `:904` 不精确 → F-R2 修正 `:896-900/:927-931/:933`）；新增取证 `_refresh_last_nav` 不产生快照（`engine_v2.py:430-440`，V2 快照数=N）、test_16 锚定 V2 回撤正值（`test_real_ashare_strict_validation.py:610-630`）、calmar 依赖 mdd>0（`analytics.py:112`）、tracker 第三实现正值（`tracker.py:426/440`）、V3 负值被 test_numba/test_v3_engine_integration 锚定。**E2 探针**（`%TEMP%\p011_step4_probe.py`）：V2/V3 年化分母**均 252/N**（正文原断言「N−1 vs N 不一致」**被证伪**）；V2 mdd=+0.19 vs V3 mdd=−0.1（**符号相反**）；V3 回撤**缺初始锚点低估幅度**（pv=[100,90,81] 真实 19% 报 10%）。**发现 4 项全部回写**：F-R1（P1——F-D3 重写 + D5 重写：分母维持 252/N 零变化、回撤统一量级约定、V3 kernel 补锚点 + results 层取量级；§4.2/§5.4/I9/§7.3/§10.2 同步）、F-R2（P2 锚点修正）、F-R3（P3 §4.5-3 措辞）、F-R4（P3 §10.2 消费方清单：唯一需更新断言 = test_v3_engine_integration:217）。可追溯性 9/9；归因扭曲检查通过（A27/A28 否决为多因）。**P1 回写后残差 = 0，Step 4 通过，可进入 Step 5**
- **Step 5 IMPL（已完成 2026-11-10）**: [IMPL_backtest_validation.md](IMPL_backtest_validation.md)；证据时点 `@dc71c1a`。**任务分解 T-0~T-14** 映射六批（B1 不变量+参考差分 / B2 组件差分+事件等价+口径文档 / **B3 报告口径（唯一行为批）** / B4 偏差声明 / B5 manifest / B6 trace）。**RED 基线 R1-R10**（550 passed / black 153 / mypy 0 / 盲区 4 errors 2 files / collect 550；R6 指标探针 E2 已录；R7 B3 before 待 T-0 记录）。**RED 形态按批登记**（B2 诚实声明为描述性验证：首跑即绿是预期，失败即缺陷）。**接口与公式**：`core/invariants.py`（I1-I7 + `check_all`）、`tests/_reference_impl.py`（4 参考函数，要求比特一致）、`core/metrics.py`（252/N、回撤含锚点、量级约定）、`core/validation.py`、`core/manifest.py`（指纹/哈希/序列化白名单）、`tests/_synth_fixture.py`（合成夹具复用）。**T-5 事件等价**：TV=1e7 / P=[10,25] → V2 `[492500,197000]` vs V3 `[500000,200000]`，NAV 三日全等，cash 差 150,000，阴性对照 `[7500,3750]`。**V1-V16**（含 B3 Δ 表、change_report 全零、指纹稳定、回退演练）；新增 52 用例 → 预期 **602 passed** / black **167**。**待 Step 6 Review 独立 pass**
- **Step 6 Review（已完成 2026-11-10，独立 pass，IMPL §8）**: 审查基座 GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash（RULE-5 异构满足）。**E2 探针**（`%TEMP%\p011_step6_probe.py`）：numba **0.65.1** 本地可用且 `@njit` **默认参数编译 OK**（§2.2 最高风险声明成立，M6 API 下限教训过）。**E1/E3 事实核实 12 项**：PerformanceAnalyzer 8 处调用全零参（默认参数兼容）、config.py:13 已导入 Literal、`--profile` CLI 存在、get_execution_stats/factor_dict→factor_data/B3 断言行号全命中；**1 项证伪**：TradeLog 方法名 `get_all_trades` 不存在。**发现 5 项全部回写**：F-I1（P2——接线改 `get_trades()`，execution.py:71-77）；F-I2（P2——R7 夹具「60 日×10 股」不可行，baseline 下限 MIN_STOCKS=31/MIN_DAYS=51，改 31 股×60 日）；F-I3（P2——T-0 收窄为 B1 的 2 个测试文件 + 2 辅助，B2-B6 测试各批实现前创建，防失败骨架破坏零数值批次绿性）；F-I4（P3——「§4.10」悬空引用改「T-10」）；F-I5（P3——DESIGN §4.1 `check_return_identity` 补 `initial_capital` 形参，Step 6 回写）。**覆盖 9/9**（D1-D9 ↔ T/批次）；算术核对通过（52=10+9+5+5+8+4+7+4；602=550+52；167=153+14）。**P1=0，Step 6 通过，可进入 Step 7**
- **Step 7 CHECKLIST（已完成 2026-11-10）**: [CHECKLIST_backtest_validation.md](CHECKLIST_backtest_validation.md)；按批次分组、逐条绑定证据出口，**共 76 项**（A 不变量 8 / B 参考差分与事件等价 10 / C 报告口径 10 / D 偏差声明 5 / E manifest 7 / F trace 4 / G 测试 8 / INV 不变式 10 / RL 红线 9 / DOC 台账 5）。**RULE-1**：实测列 **76 行全 `[待 Step 9]`、零预填**（机械计数 76 行；全文 78 含 2 处说明性引用）。**目标末态**：602 passed（550+52）/ black 167 / mypy 0 / 盲区 4 errors 2 files 不劣化 / 68 测试文件。**§8 预登记 5 项核对点**（双向引用 / 0 预填 / 断言延续 / 术语 7 组 / 文档无矛盾）；**§10.1 分母登记 76 待办**；§9 ADD 审计与 §10.2/10.3 签字留待 Step 9/10
- **Step 8 一致性 Review（已完成 2026-11-10，独立 pass，CHECKLIST §8）**: 审查基座 GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash（RULE-5 异构满足）。**机械校验**：四文档 markdown 链接 **13 条 0 broken**；清单 ID **76 个连续无缺号无重复**（A8/B10/C10/D5/E7/F4/G8/INV10/RL9/DOC5）；`[待 Step 9]` = 78 = 76 表格行 + 2 说明性引用（自洽）；实测列 `✅` = 0（全文 2 处均在 L8/L190 说明性文本）；§10.1 分母 8+10+10+5+7+4+8+10+9+5 = **76** 自洽；四文档 **0 个** STEP_GAP/CONFLICT/FALSIFIED/单源标记（RESEARCH U-1~U-4 已在 §11.8 全部裁决闭合）。**预登记 5/5 通过**：双向引用（含 ADR-002/003/005/007/012/017 存在性）、0 预填、断言延续、术语 7 组（量级约定 DESIGN12/IMPL2/CL2、事件级等价 DESIGN12/IMPL3/CL2，无漂移；golden 用法统一）、文档无矛盾（D→I 签名 / 批次↔任务 / V↔G 16 项全有归宿 / 目标末态 602/167/68 三文档一致）。**发现 3 项 P3 全部回写**：F-S8-1（A 组头注 T-1/T-2/T-3 → T-1/T-3，T-2 验收项在 §2）；F-S8-2（C5 锚点 DESIGN §2.2 → IMPL §2.2）；F-S8-3（预填判据精确化：实测列 ✅=0 vs 全文 2）。派生需求预检：实施未开始，无实施期派生需求；完整清点留 Step 10 Phase 3。**P1=P2=0，Step 8 通过，可进入 Step 9**
- **Step 9 实施（已完成 2026-11-10）**: 六批各一提交 + 1 补丁——B1 `cd6d619`（`core/invariants.py` I1-I7 + 参考实现 + 不变量/差分测试 20 项）、B2 `26929c6`（V2 组件 8 + 事件等价 5 + `BACKTEST_CALIBER_MAPPING.md` 5 章）、B3 `9ec9f7d`（**唯一行为批**：`core/metrics.py` + analytics 委托 + V3 kernel rf/锚点/量级）、B4 `e59dee2`（`core/validation.py` 偏差声明）、B5 `beaa3a1`（`core/manifest.py` 运行清单）、B6 `b6bcee3`（`cli.py --trace-dir` + trace 完备 4 项）、补丁 `d270511`（manifest E1/E7 用例）。**末态读数**：`609 passed`（550 + 59；逐文件 11/9/8/5/9/4/9/4）、black **167 unchanged**、mypy 门禁 `Success: 36 files`、盲区 `4 errors 2 files` 不劣化、测试文件 68。**B3 归因双证**：Δ 表（V2 vol 0.08122845→0.08189931、sharpe −1.45492→−1.44300；V3 mdd −0.02965→+0.02965、sharpe 0.93900→0.59117 == rf/vol；其余字段 0 或 1 ulp）+ `change_report` `residual 0.0` / `attribution_complete true` / 六层 `changed` 全 0。**实施期发现**：F-S9-1（**P1** 快照浅拷贝共享 `Position` → 引擎实跑 53 项 I1/I2 违规，改逐 Position `replace()`，NAV 标量不变）；F-S9-2（numba `np.sum` 顺序累加 vs NumPy pairwise，参考实现改 `_seq_sum`，`py_func` 路径 `rtol=1e-12`）；F-S9-3（同日多快照 → I2 跳过，补 ambiguous 用例）；F-S9-4（阴性对照 `3_750`→`3_000`）；F-S9-5（trace 自差分 residual 1.16e-10 → `<1e-8`）；F-S9-6（B3 单提交回退在 `config.py` 1 处行相邻冲突，净回退 7 文件）；F-S9-7（V3 三个 `check_*` 为公共 API，无直接单测，I5-I7 由参考差分覆盖）。**回填**：IMPL §9、DESIGN §4.2/§4.5/§6、CHECKLIST 76 项、CHANGELOG。**远端 CI**：首跑 `42768109104` 在 3.11 暴露无 numba 路径（主用例 cash 末位差 2.3e-10，F-S9-2 远端补正）→ 补丁 `7bcdd57`（JIT 活跃比特一致 / 否则 `rtol=1e-12`）→ run `42768525717` **三 job 全 success**（3.10 `602 passed, 1 skipped`，本地 609 − 7 为 numba 相关 `importorskip`）；CHECKLIST **76/76**
- **Step 10 ADD 审计（已完成 2026-11-10，CHECKLIST §9）**: 四阶段全过——Phase 0 措辞扫描 0 命中 + 发现 D5 交付物无验收行的 Phase 0 缺口；Phase 1 D1-D9 全实现带行号（E3 @`a754a2d`）；Phase 2 numstat 24 文件对账 + 公式逐字 + 偏差闭环（F-S9-1~7 + F-A1~A3）；Phase 3 盲区扫描 24 文件 diff 全文**发现 3 项、0 项无依据代码行为**（保护路径 `pyproject`/`.github`/`change_report.py`/`execution.py`/`data.py`/`filter/` diff 全 0）；Phase 4 Iron Law——**F-A1（P2）即反例**：`metrics_method` 声明测试全绿仍缺失，由审计捕获并修复 `a754a2d`（`METRICS_METHOD` 常量 + V2/V3 接线，断言并入既有 2 用例，609 不变）。**P1=0 / P2=1（已修复）/ P3=2（已回写）**；门禁链审计时点 4 pass + `replay: 10 rows OK`；RULE-5 异构复审留待独立会话（同 P-012 限定）
- **Step 11 审计总结（已完成 2026-11-10，用户指令扩展步）**: [AUDIT_SUMMARY_backtest_validation.md](AUDIT_SUMMARY_backtest_validation.md)——四问→交付映射、Step 1-11 时间线（异构 Review 4 轮全命中实质问题；F-S9-1 由观测网自身暴露；F-A1 为唯一漏网 P2，根因「设计交付物无验收行」）、**28 项发现全量归并**（P1=2 / P2=7 / P3=19，全部闭环）、13 提交链、末态指标、能力边界声明、遗留 5 项（RULE-5 异构复审待执行；U-D4 标注实际闭合）与 3 条流程建议（Phase 0 验收行映射前置 / 观测网先行 / CI 无 numba 一等场景）；无新发现（2 项 P3 注记归并）
- **RULE-5 异构第二会话复审（已完成 2026-11-10，用户指令）**: 复审基座 **GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash**（异质性成立；复审会话上下文经压缩，近似独立会话），按 CHECKLIST §9.3 取证矩阵 **E1-E5 全量独立重放**（§9.6，复审时点 HEAD `025b412`）——E1 全命中（`609 passed` / black 167 unchanged / mypy 0（36 files）/ 盲区 4 errors 2 files / collect 609 / `replay: 10 rows OK` / 14 提交链 + 24 文件 numstat + 保护路径 diff=0）；E3 锚点 @`025b412` 抽查（2 处漂移 = F-R5-1，系 F-A1 修复插入行后的旧行号残留，已就地修正）；E4 盲区重扫（engine_v2 全 9 hunk + config 3 行归属 + 保护路径）确认审计「发现 3 项」无漏报；E2 `[未入仓-不可重放]` 与 E5 两项未覆盖声明诚实性成立。**复审 pass：0 P1 / 0 P2，2 项 P3 文档残留（F-R5-1 锚点漂移、F-R5-2 行数口径）就地修正，审计结论维持不变**

### 3.13 P-012（偏差防护与接口锁定）执行序与进度（2026-11-10）

判定为 **T1 完整管线**（专项调研批；若实施将触及 `core/data.py`、`filter/`、`core/interfaces.py`、`tests/`）：

- **立项（2026-11-10）**: 用户五问——①幸存者偏差；②前视偏差；③复权；④ST / 停牌；⑤接口锁定。**口径声明**：接口锁定按「契约是否唯一真源 / 实现是否可替换 / 版本兼容是否可验证」取证；若指数据供应商锁定见 P16-P18，留 U-5 裁决
- **Step 1 调研（已完成 2026-11-10）**: [RESEARCH_bias_interface.md](RESEARCH_bias_interface.md)；**16 条外部锚点**（Qlib PIT、Shumway 退市偏差、CRSP 退市收益、PIT 成分、训练期统计量、前/后复权定义、成交价用不复权价、Qlib 首日归一、上交所 2026 交易规则、证监会 ST 5% 规则、新华网 2026-07-06 ST 10% 新规、PEP 544、ABC vs Protocol、Pact 契约测试、N/N-1 兼容）+ **20 条本仓事实**（P1-P20，E1/E3/E4 绑 `@05af52f`）
- **关键发现**: ①**幸存者偏差不具备**——无退市/上市日期字段，股票池为 `close.pkl` 静态列集合；②**前视两处疑似**——涨跌停掩码用执行日收盘收益、`next_day_tradable` 用 `suspend.shift(-1)` 并入 `buyable`；③**复权疑似颠倒**——`forward = price*adj_factor`（按定义是后复权）、`backward = price*adj/adj[-1]`（按定义是前复权），且**成交价用复权价**；④**ST 阈值 4.8% 已过时**——沪深主板 ST 自 2026-07-06 起为 10%，且 ST 状态阈值用 `shift(1)` 与当日掩码不一致；⑤**接口未锁定**——14 Protocol + 7 ABC 双轨、`UniverseConfig`/`UniverseFilterConfig` 双定义（P-007 层 B 盲区残差来源之一）、DataManager/DataLoaderV3 双实现、config/config_v2 双版本、无契约测试
- **产出**: 五问逐项诊断（能力/证据/缺口/风险等级）+ 5 组方案 7 维矩阵（S/L/A/U/I）+ L0-L4 路线（**先 E2 证实、再改代码**）+ **U-1~U-5 四元块**
- **Step 1 补充调研（已完成 2026-11-10，§11）**: 用户裁决 U-1~U-5 后逐项落地
  - **U-1 口径纠正（用户指出）**: 初稿把「无数据声明 + 预留字段」当默认路径，**错误**；已改为 **S-A 退市数据契约 + 动态池为默认实现**（`list_date.pkl` / `delist.pkl`；`stock_codes(t) = {s | list_date <= t < delist_date}`），**S-C 降级仅在数据缺失时触发**（显式 warning + `survivorship:"uncorrected"` + 敏感性分析 + 禁止静默）
  - **U-2**: 六层归因链 L1 掩码 → L2 可交易集合 → L3 目标持仓 → L4 订单 → L5 成交 → L6 净值；产出 `change_report.json`，残差 < 1e-8
  - **U-3**: Tushare 官方公式证实本仓 **`forward = price*adj` 实为后复权、`backward = price*adj/latest` 实为前复权（命名颠倒）**；新增 **P21：`returns` 用复权价计算却被用于涨跌停判定**（价格口径错配）；方案 A-A′ = 重命名 / 成交用 raw / 三口径分离 / `legacy_adjustment` 兼容开关
  - **U-4**: 规则矩阵——主板 10%；主板 ST 5%（≤2026-07-05）→ 10%（≥2026-07-06）；创业板/科创板 20%（含 ST）；北交所 30%；IPO 前 5 日无限制；退市整理期首日无限制、此后 10%；板块前缀推断（300/301、688/689、8xx/4xx）
  - **U-5a 契约稳定性 E2 排查**: DataManager 8/8 ✅、UniverseFilter 5/5 ✅、PositionTracker 8/8 ✅；**不通过 3 项**——FactorPipeline 缺 `process_single`、FactorCombiner 缺 `combine_single`、ExecutionSimulator 签名不兼容（V10）；配置双定义 21 字段全同名、**2 处默认值漂移**（`exclude_na_factors`、`exclude_stock_prefixes`）
  - **U-5b 供应商锁定**: `DataProvider` Protocol（`load_price`/`load_aux`/`load_universe`）+ `PklDataProvider` + manifest/schema_version
  - **补充发现 P21-P25**: P21 returns 口径错配；P22 夹具零覆盖（`adj≡1`/`suspend≡0`/`industry≡1`/全 `000`）；P23 无板块字段；P24 ST 无日期段；P25 无退市整理期
  - **新增未决项 U-6~U-9**: 退市数据落地形式 / 复权切换兼容期 / ST 规则表维护方式 / `DataProvider` 与 P-004 边界
  - **修订路线 L0-L5**: L0 证实（真实分红样本 + 扰动探针）→ L1 测试网（夹具扩展 + 恒等式 + 规则表 + 契约测试）→ L2 复权与掩码 → L3 ST 规则表 → L4 退市能力（默认路径）→ L5 接口治理
- **Step 1 补充调研（U-6~U-9，已完成 2026-11-10，§12）**: 外部锚点扩至 **A24-A41**（Tushare/AKShare 退市接口、Qlib 股票池日期区间、Zipline `auto_close_date`、DVC 数据版本、pickle 安全警告、PEP 387/NEP 23/PDEP-17/SemVer、OMG DMN 1.5、SCD Type 2、Cockburn 六边形、LEAN Time Frontier）
  - **U-6 → D-A 本地快照 + 生成脚本 + `manifest.json`（sha256/schema_version）**：Tushare 官方明确「建议保存到本地存储后使用」；运行时拉取回测不可复现，已排除
  - **U-7 → C-A 双轨 ≥2 个 minor + 冻结基线逐值对拍**：PEP 387 / NEP 23 / PDEP-17 三份官方政策的弃用期下限一致；「保留 3 个月」类无事件锚定表述不可验证
  - **U-8 → R-A 内置不可变规则表 + `(board, is_st, t)` 唯一命中 fail-fast**：禁止回落 10% 默认值（即 P11/P23 失效模式）；DMN 对当前 <10 条规则属过度设计
  - **U-9 → B-A 只做 `DataProvider` 端口 + `PklDataProvider` + 契约测试**：消费方迁移与旧实现删除归 P-004；边界表已固化，避免与六层归因冲突
  - **实施顺序**: U-8 → U-9 → U-7 → U-6（U-8/U-9 无前置依赖）
- **ADR 登记（2026-11-10）**: [DECISIONS.md](DECISIONS.md) 新增 **ADR-017 复权口径校正与三口径分离**（状态 📋 已规划）——命名校正（`forward→hfq` / `backward→qfq`，旧名 ≥2 minor 弃用期）+ 口径分离（trade/valuation=`raw`、signal/return/limit=`hfq`）+ `legacy_adjustment` 兼容开关 + 六层归因；**明确不做**：收益/涨跌停口径改为 `raw`（除权日会产生假涨跌停）。同步修正 RESEARCH P21 的口径描述（原「复权收益漏判涨跌停」方向有误，实为**口径耦合**：复权收益判涨跌停本身正确）
- **Step 2 Review（已完成 2026-11-10，独立 pass）**: E1（HEAD `2c34283`，`05af52f..2c34283` core/filter/tests 零 diff）+ E2 三探针重放全命中（A 复权夹具 / B 配置双定义 / C 协议符合性）+ E3 抽检 7 处 + 计数矩阵（A=41 / P=25 / 文献 41 连续）；**3 项发现全部回写**——F-R1（P2）锚点 A17-A23 悬空 → 补 §11.0.1；F-R2（P3）文献缺 14 号 + 创业板 2020-08-24 无出处 → 补录；F-R3（P3）§11.4 创业板行缺日期段 → 补 10%/5% → 20%（2020-08-24）。**P1=0，通过**
- **P0 决策门（已完成 2026-11-10）**: 5/5 闭合——P-012 Step 2 Review 通过（§10）；P-011 Step 2 Review 通过（P-011 §10）；P-012 U-6~U-9 按 §12.5 推荐确认（D-A/C-A/R-A/B-A）；P-011 U-1~U-4 按 §11 推荐确认（V-A / S-A+S-C / D-A+D-B / X-A）；合并判定=**独立双 DESIGN、P-012 先行**
- **Step 3 设计（已完成 2026-11-10）**: [DESIGN_p012_bias_interface.md](DESIGN_p012_bias_interface.md) 完稿——**D1-D11**（D11 为 Step 4 补录）：D1 拆 **B1-B6 六组、7 个提交**（B1 观测网 / B2 ST 规则表 / B3a 复权命名零数值 / B3b 口径分离 / B4 掩码时点 / B5 退市 / B6 接口治理含 D11）；D2 `get_adj_price` 三口径 + `PriceModeConfig` + `legacy_adjustment`；D3 `filter/limit_rules.py` 不可变规则表 + `(board,is_st,t)` 恰好 1 条 fail-fast + 板块前缀推断；D4 涨跌停改**价格法**（开盘价 vs 除权参考价×限幅）+ `next_day_tradable` 默认 `ignored`（不采纳 shift(1)，理由见 D4）；D5 `UniverseSnapshot` + 上市/退市掩码 + 显式降级；D6 六层 layer dump + `scripts/change_report.py`（残差 <1e-8 + `attribution_complete` 门）；D7 协议**收窄** + `execute_order` 以实现为准修订协议 + 契约符合性测试 + `__api_version__` + `DataProvider` 端口（不接线）；D8 夹具 `--profile {baseline,biased}`；D9 范围边界（不做 P-011 golden/统计/对拍、不做 P-004 迁移、不改 V3）；D10 配置/报告字段兼容；D11 `UniverseFilterConfig.from_universe_config()` 转换 + 21 字段级单测
  - **不变式 9 条**（§8）：成交估值不含 adj；掩码 t 行仅用 ≤t 开盘信息；规则表唯一命中；缺失不静默；`legacy_adjustment` rtol=0 复现；行为变更单批归因；协议唯一；dump 默认关且零差异；`DataProvider` 零接线
  - **未决项 U-D1~U-D4**（退市结算价格优先级 / 整理期首日数据表达 / 北交所 ST 标识 / 规则表维护方式）；**决策矩阵不启用**（全部 Type-2 可逆）
  - **ADR-017 补记**：D4 改为价格法后，「禁止 raw」仅针对不复权**收益**，不针对 raw 价格本身
- **Step 4 设计 Review（已完成 2026-11-10，独立 pass）**: E1/E3 重验 6 项全命中（`process_single/combine_single` 零消费方 / 协议 vs 实现签名 / `engine_v2.py:195` 错配 / 夹具脚本存在 / 证据 commit 零 diff / `fetch_universe` 缺失证实）+ D1-D11 可追溯性 11/11 + 不变式自洽检查；**7 项发现全部回写**——**F-D1（P1）RESEARCH §11.5 P0 配置双定义未纳入设计 → 补 D11 `from_universe_config()` 转换 + 字段级单测**；F-D2（P2）不变式 9 与行为批次矛盾 → 改「零 import data_provider」口径；F-D3（P2）模块表缺 `scripts/fetch_universe.py` + `data/` gitignore 事实 → 补 B5 交付物与约束 8；F-D4~F-D7（P3）不变式 2 的 adj(t) 论证 / D4 不采纳 shift(1) 理由 / P15 行号 191→195 / execute_order 对齐方向。**通过，可进 Step 5**
- **Step 5 实施规划（已完成 2026-11-10）**: [IMPL_p012_bias_interface.md](IMPL_p012_bias_interface.md) 完稿——**T-0~T-13** 任务分解 + 批次映射（B1=T-0/1/2 零行为 / B2=T-3/4 行为 / B3a=T-5 零数值 / B3b=T-6 行为 / B4=T-7 行为 / B5=T-8/9/10 行为 / B6=T-11/12 零数值 / docs=T-13）；**10 项 RED 基线读数**（R1-R10，含 baseline 夹具 sha256）；**逐批 RED 测试 10 项**（先失败后实现）；**新增测试 34 项**（2+3+7+4+2+3+6+4+3），预测全量 **550 passed**、CI **543 passed, 1 skipped**（Step 6 由 544 修正：CI = 本地 − 7 numba；声明为预测，Step 9 实测回填）；**V1-V20 验证清单** + **低效/危险操作排除 8 条** + **逐批回退点** + 门禁 session `factorv3-p012-bias-20261110`
- **Step 6 实施 Review（已完成 2026-11-10，独立 pass）**: E1 重跑 10 项读数（516 passed / black 138 / mypy 0 / 盲区 8 errors 2 files / 7 pkl / 仅 docs 变更）+ E3 读码 + D1-D11↔T 双向覆盖（11/11，无孤儿任务）+ 算术复核；**10 项发现全部回写**——**F-I1（P1）T-5 丢失 `"none"` 口径**（基线 9 处用法，已补 `none→raw`）；**F-I3（P1）parquet 引入未声明依赖 pyarrow**（CI 不保证安装，已改 CSV+JSON 并同步 DESIGN）；F-I2（P2）取价点实为 8 次（440 漏计）；F-I5（P2）D11 的 `exclude_stock_prefixes` list→bool 错配；F-I10（P2）`universe_dir` 未定义（默认改 `cfg.data_dir/"universe"`）；F-I4/F-I6/F-I7/F-I8/F-I9（P3）27 项拆分、CI 544→543、文件数口径、早退门/北交所 ST 闭合行/L4 reason、退市结算价公式与重复盯市。**通过，可进 Step 7**
- **Step 7 验收清单（已完成 2026-11-10）**: [CHECKLIST_p012_bias_interface.md](CHECKLIST_p012_bias_interface.md) 完稿——**74 项 DoD**（A 观测网与夹具 7 / B 规则表与 ST 7 / C 复权三口径 8 / D 涨跌停与掩码 5 / E 退市与动态池 6 / F 接口治理 6 / G 测试与验证 8 / INV 不变式 9 / RL 排除红线 12 / DOC 台账 6）+ 错误处理映射 9 场景（不重复计数）；实测列一律 `[待 Step 9/8/10]`，禁预填（RULE-1）；§8 预登记 5 项 Step 8 核对；**起草期发现 2 项并回写 IMPL**——**F-S7-1（P2）**：T-6 默认 `returns=hfq` 会使 `test_adjustment.py` 3 项旧耦合断言失败（E3 证实 mock 夹具 adj 在第 4 个交易日（0-based index=3）由 1→0.5）→ 构造补 `legacy_adjustment=True` 保留旧语义覆盖；**F-S7-2（P3）**：DESIGN §4.2 `special_no_limit_mask`（IPO 前 5 日）未落入任何 T 任务 → 补 T-3 要点 6 + T-7 掩码叠加（断言并入既有测试，34 项计数不变）
- **Step 8 一致性 Review（已完成 2026-11-10，独立 pass）**: 机械校验（`%TEMP%\p012_step8_check*.py`，`[未入仓-不可重放]`）——四文档链接 **11 条 0 broken**、CHECKLIST **74 项**（A7/B7/C8/D5/E6/F6/G8/INV9/RL12/DOC6）且 **0 预填**、RESEARCH **A1-A41 缺号 0**（16 标题 + 25 表格行）、DESIGN D1-D11=11 / I1-I9=9、IMPL T14/V20/R10 / F-I1~F-I10=10；5 项预登记核对点全通过（B7 归属 / F-S7-1 三项与 34 计数 / 三旧名 / 550-543 唯一 / ADR 映射）；断言延续链 10 条贯通、术语 7 组一致；**4 项 P3 全部回写**——**F-S8-1** DESIGN §2.1「引擎 7 处取价」→「8 次（7 位置）」；**F-S8-2** RESEARCH §12.1.4 补 CSV+JSON 落盘注记（parquet 为早期表述）；**F-S8-3** RESEARCH §11.3 补 `none→raw` 回写注记；**F-S8-4** 「t=4」改「第 4 个交易日（0-based index=3）」。**P1/P2=0，通过，可进 Step 9**
- **Step 9 实施（已完成 2026-11-10）**: 七批次提交 `a5ae5cc`(B1) → `4e2ab0b`(B2) → `ad40490`(B3a) → `79c4dea`(B3b) → `3717246`(B4) → `94018f2`(B5) → `6e5eeba`(B6)，T-13 取证修正 `5f95b48` / `0ccc7f6` / `9be78e9` / `766c007` / `9d16a2a` / `86f7650`
  - **GREEN 读数**: `550 passed`（516 + 34）/ `black 153 unchanged` / `mypy 0（32 files）` / 盲区 `4 errors in 2 files` / 测试文件 **60** / 门禁 4/4 pass + `replay 16 rows OK`（session `factorv3-p012-bias-20261110`）
  - **逐批行为归因**（均 `residual < 1e-8`、`attribution_complete=true`）: B2 `1,155,172.33→1,155,172.33`（全零，夹具无阈值事件）/ B3b `→832,682.77`（L4=175/L5=217/L6=59）/ B4 `→831,073.02`（L1=1 @`2024-02-27:000001` 涨停开盘）/ B5 `→787,609.76`（L1=25/L2=25 退市与动态池）；JSON 见 `docs/dev-log/p012/`
  - **T-13 机械验证**: V1-V20 全部执行——V6 恒等式 / V7 legacy `rtol=0`（NAV 1,155,172.3318119394，136 笔 trades 全等）/ V8 28 边界日唯一命中 / V9 无前视 / V10 退市掩码 / V11 降级字段 / V13 dump 零影响 / V14 契约 4/4 / V15 零接线 / V16 baseline sha256 全同 / V17 远端 run `42694945888`（3.10/3.11/3.12 各 `543 passed, 1 skipped`）/ V18 报告四字段（+`unknown_board_codes`）/ V19 取价仅 `_exec_price` / V20 逆序回退 9/9
  - **实施发现 F-S9-1~F-S9-9**（CHECKLIST §10.0-4 / IMPL §9）: 归因链修正 4 项（L6 终值刷新 / L1 含 listing / 删除 L4→L3 硬链 / 首日现金流重复）/ 夹具修正 2 项（除权日伪跳空 + 层 CSV 代码读串；manifest 补 `fetched_at`）/ DESIGN §7 未知前缀告警与报告字段补齐 / 盲区标注
  - **验收**: CHECKLIST **74/74 通过**（G7 由远端 CI run `42694945888` 回填）
- **Step 10 ADD 审计 + 推送/CI（已完成 2026-11-10）**: 推送 `2c34283..a17ebce` 共 15 提交；远端 CI run `42694945888` / `42695386497` 三 job（3.10/3.11/3.12）各 `543 passed, 1 skipped`；**ADD 审计**（CHECKLIST §9，独立 pass）——Phase 0 模糊措辞 0 命中；Phase 1 D1-D11 逐项 E3 @`a17ebce`；Phase 2 numstat 对账（24 文件 +2731/−146，与 §2.3 清单 + F-S7-1 吻合）；Phase 3 盲区扫描 **发现 2 项均文档粒度**（F-A1 `limit_check_price` 补列名于 DESIGN D10；F-A2 RL-12 docs 提交计数），**0 项无依据代码行为**；Phase 4 Iron Law 通过（V1-V20 双门 + D1-D11 映射 + numstat 三层补足）；P1/P2=0；**RULE-5 异构复审留待独立会话**（同基座限定，§9.4）
- **P-012 状态**: **done**（2026-11-10，Step 1-10 全通过）

### 3.14 未闭环事项依赖链与优先级（2026-11-10，分析落档）

> 本节为跨批次规划视图，只登记依赖关系与优先级判定，不重复 §1.4 / §2 / §3.1-§3.13 的逐项细节。

**① 未闭环事项归组（15 项，映射既有编号）**

| 组 | 事项 | 阻塞性 |
|----|------|--------|
| 决策门 ×5 | P-011 Step 2 Review；P-011 U-1~U-4 裁决；P-012 Step 2 Review；P-012 U-6~U-9 确认（§12.5 已给推荐）；P-011/P-012 是否合并 DESIGN | 全部实施项的前置 |
| 技术债挂起 ×4 | U-006（mypy 盲区残差 8，按 Q4=B 挂起）；F-A1（注入式工作流未注入信号 → 静默空回测，CHECKLIST §11 P3）；P-004；P-005 | 独立，可插空 |
| P-012 实施包 ×6 | L0 证实 → L1 测试网 → L3 ST 规则表 → L2 复权与掩码 → L4 退市能力 → L5 接口治理 | 待决策门 |
| P-011 实施包 ×3 | L1 golden/内部差分 → L2 统计规范 → L3 断点 trace + run manifest | 待决策门 |

**② 依赖链**

```text
[决策门]
P-011 Review → P-011 U 裁决 → P-011 DESIGN ─┐
P-012 Review → P-012 U 确认 → P-012 DESIGN ─┴→ 合并判定 → 实施

[能力层（不改生产行为）]
L0 证实 ──→ L1 测试网 ──┬─→ L3 ST 规则表
P-011 trace/manifest ───┘
                        ├─→ L2 复权（ADR-017，两子批次：命名 → 口径分离）
                        ├─→ L2 掩码时点（独立批次）
                        └─→ L4 退市 ──→ L5 接口治理 ──→ P-004 迁移
                                                └─→ U-006 重评

[收尾]
L2 两项 + L4 全部落地 → P-011 golden 全局基线 → P-011 统计规范
```

**③ 五条硬约束**（违反即返工）

1. 先改口径、后固 golden——L2/L4 改变回测结果，全局基线必须排其后；
2. 每次行为变更单独批次 + `change_report.json` 六层归因（复权命名、口径分离、掩码为三个独立批次）；
3. Protocol 先定型（P-012 L5）、P-004 后启动——否则出现第二套 Provider 定义；
4. U-006 在 L5 之后重评——接口改造会移动 `engine_v2`/`data_v3` 的 mypy 残差；
5. P-011 外部框架对拍（U-4）在复权与接口治理之后——当前 V2 次日开盘 vs V3 当日 close 不可比。

**④ 优先级与执行顺序**

| 优先级 | 事项 | 理由 |
|--------|------|------|
| **P0** | 决策门 ×5 | 不决策则实施项全部无法启动 |
| **P1** | L0 探针 + L1 夹具扩展 + P-011 trace/manifest | 观测与回归能力；`data/test_ashare` 无 `st.pkl`/退市文件，ST 与退市路径当前无法写出有效测试，夹具扩展是硬前置 |
| **P1** | L3 ST 规则表 | 独立正确性缺陷（P11/P23），无前置依赖、不新增数据需求 |
| **P2** | L2 复权（ADR-017）+ L2 掩码 | 影响面最大（股数/现金/成本/涨跌停同时失真），必须等测试网；各为独立批次 |
| **P2** | L4 退市 | 依赖 U-6 数据脚本；否则只能走降级 |
| **P3** | L5 接口治理 | 纯增量，但会移动 U-006 残差 |
| **P3** | P-011 golden + 统计规范 | 必须在口径稳定后，否则基线/统计结论作废 |
| **P4** | F-A1、P-005 | 独立小项，可插空 |
| **P4** | P-004 | 必须等 L5 端口定型 |

执行顺序：**P0 决策 → P1 观测（L0/L1/trace）→ P2 ST（L3）→ P3 复权命名（零数值变化）→ P4 复权口径分离（破坏性）→ P5 掩码 → P6 退市（L4）→ P7 接口（L5）→ P8 基线与清尾（golden / 统计 / U-006 / P-004 / F-A1 / P-005）**。

**⑤ 待用户决策 ×3**（**2026-11-10 已全部裁决**：① 合并判定=独立双 DESIGN、P-012 先行；② P-012 U-6~U-9 按 §12.5；③ P1 观测阶段随 P-012 B1 启动）。

> 关联：复权实施决策已登记 **ADR-017**（✅ 已实施，见 [DECISIONS.md](DECISIONS.md)）。
>
> **状态更新（2026-11-10）**: P0 决策门 **5/5 已闭合**；**P-012 done（Step 1-10 全通过）**——Step 9 七批次实施 + T-13 验证 74/74，远端 CI run `42694945888` 三 job `543 passed, 1 skipped`，Step 10 ADD 审计全过（CHECKLIST §9，P1/P2=0）；**P-011 Step 3-8 全部完稿**（DESIGN / Step 4 Review / IMPL / Step 6 Review / CHECKLIST 76 项 / Step 8 一致性 Review；F-D1~F-D6 + F-R1~F-R4 + F-I1~F-I5 + F-S8-1~3 全部回写）；**P-011 Step 9 实施已完成**（六批 + 补丁 `cd6d619`..`d270511`；**609 passed** / black 167 / mypy 0 / 盲区 4 errors 2 files；B3 Δ 表 + `change_report residual 0.0` 双证；F-S9-1 P1 快照共享缺陷已修；远端 CI run `42768525717` 三 job 全绿）；**P-011 Step 10 ADD 审计已通过**（CHECKLIST §9：P1=0 / P2=1 F-A1 已修复 `a754a2d` / P3=2；门禁 `replay: 10 rows OK`）——**P-011 done（Step 1-10 全通过 + RULE-5 异构复审 pass，2026-11-10，CHECKLIST §9.6：0 P1/P2 + 2 项 P3 文档修正）**；终态远端 CI run `42771058634` 三 job success。

**⑥ 终态盘点（2026-11-10，P-011/P-012 收口后）**: 原 ①-④ 规划的执行情况——

| 原计划组 | 状态 |
|----------|------|
| 决策门 ×5（P0） | ✅ 全部闭合（5/5 裁决） |
| P-012 实施包 ×6（L0 证实 / L1 测试网 / L3 ST 规则表 / L2 复权+掩码 / L4 退市 / L5 接口治理） | ✅ 全部完成（B1-B6 七批次，74/74） |
| P-011 实施包 ×3 | L2 统计规范 ✅（偏差声明 D 组 + 指标口径统一）、L3 trace/manifest ✅（F 组 + E 组）；**L1 golden 挂起 → 升格为 [§1.4 U-D1(P-011)](#14-未完成事项)（P2 条件触发）** |
| 技术债挂起 ×4 | U-006 重评前置（L5）已满足 → 升格 §1.4（P3）；F-A1(P-012) → 升格 §1.4（P3）；**P-004 前置（L5 端口定型）已满足 → §1.4 上调 P2**；P-005 → §1.4 维持 P3 |
| 条件触发项 | U-D2 / U-D3 / U-2(P-011 DSR/PBO) → 升格 §1.4（P3） |

> 残余可启动项汇总：**P1 = 无**（P-014 已于 2026-11-10 关闭）；**P2 = P-004（数据层统一）**；P3 = U-006-R / F-A1(P-012) / P-005 / U-D2 / U-D3 / U-2 / U-P014-1 / U-P014-3。原执行顺序 P0→P7 全部完成；**U-D1（golden 基线）已由 P-013 落地**；**P-014（停牌账目）已由本批关闭**。

### 3.15 P-013（Golden 基线固化 · L4 判据）执行记录（2026-11-10，done）

- **立项**: P-011 U-D1 升格（L4 golden 从挂起转实施）；前置条件核查 5 项全部满足（复权三口径 / 掩码时点 / 退市动态池 / 指标单一口径 / RULE-5 复审 pass），此时录制不会把已知缺陷焊死
- **Step 1 调研**: [RESEARCH_golden_baseline.md](RESEARCH_golden_baseline.md)——复用 P-011 锚点 A20（Golden Master 只锁行为、不证正确性）/ A21（分层回归）/ A25（可复现契约）/ A26（记录 commit+配置+环境）；本仓事实 P1-P10（关键：`data/` 被 gitignore → golden 必须用合成夹具；`_synth_fixture` 的 open/high/low 复用 close）
- **Step 2 Review（同基座自查）**: 4 项待核 3 命中 + **F-R-G1（P2）**：原写「仅 3.10 无 numba」，实为 **CI 三版本 dev 依赖均未声明 numba** → CI 全程 `py_func`、本地 `@njit`，容差设计据此升级
- **Step 3 DESIGN**: [DESIGN_golden_baseline.md](DESIGN_golden_baseline.md)——D1-D11（I1-I6 / JSON schema v1.0 / 分字段容差 / 6 case / 夹具扩展 / 录制脚本 / 测试 / CI / 批次 / 范围 / 风险）
- **Step 4 Review**: 5 项设计假设全部证实（涨跌停可触发 `EPS_PRICE=0.005` / 退市走 `data_dir/universe` 懒加载 / V2 入口 / 夹具向后兼容 / `limit_check_price="open"`）；**F-D-G1（P3）** 限价公式未写明
- **Step 5 IMPL**: [IMPL_golden_baseline.md](IMPL_golden_baseline.md)——T-0~T-7 / R1-R9 / V1-V12
- **Step 6 Review**: **F-I-G1（P2）** case 构造器无单一来源（录制与断言各建夹具会漂移）→ 新增 `tests/_golden_cases.py`；F-I-G2（P3）测试文件计数
- **Step 7 CHECKLIST**: [CHECKLIST_golden_baseline.md](CHECKLIST_golden_baseline.md)——**36 项**（A6/B5/C6/D4/E7/F3/G5），实测列零预填
- **Step 8 一致性 Review**: 四文档 7 链接 0 broken、G1-G6 = 6 处、623/14 引用自洽；P1=P2=0 通过
- **Step 9 实施**: `tests/_synth_fixture.py` 扩展 + `tests/_golden_cases.py` + `scripts/record_golden.py` + `tests/golden/G1..G6.json` + 2 个测试文件；**626 passed** / black 171 / mypy 0（36） / 盲区 4 errors 2 files 不劣化 / `core/`·`filter/` **零改动**
  - **V3 可重现**：连续两次录制 6 份 JSON SHA256 完全一致
  - **V6 涨停**：涨停日 `2024-01-16` 对 `000001` 买入 0 笔、`limit_up_mask=False`
  - **V7 退市**：退市日 `2024-01-22` 起无 BUY，仅 1 笔清仓 SELL，持仓归零
  - **V10 防护**：脏工作区 / `CI=true` 均拒绝录制（exit=1）
  - **实施期发现 7 项**：**F-S9-G1（P1，停牌路径账目缺陷 → 另立 P-014）**、F-S9-G2（P2，涨停构造污染价格序列）、F-S9-G5（P2，`recorded_at` 破坏可重现）、F-S9-G3/G4/G6/G7（P3）
- **Step 10 ADD 审计**: Phase 0-4 全过（措辞 0 命中 / D1-D11 逐项落地 / numstat 对账 / 盲区无无依据行为 / Iron Law 以 F-S9-G1 为反例）——**P1=1（不在本批修复）/ P2=2（已修）/ P3=4（已回写）**；CHECKLIST **36/36**；RULE-5 异构复审留待独立会话
- **CI 回收**: run `42786173151`（commit `77b110b`）三 job `success`，3.10/3.11/3.12 各 `619 passed, 1 skipped`（= 本地 626 − 7 项 numba `importorskip`）→ 6 条 golden 在无 numba 的 `py_func` 路径全部通过，分字段容差有效；**既有观察**：CI `Type check (mypy)` 为 `|| true` 不阻断且报 `Source file found twice`（CI 目录 + 已安装包命名冲突，非本批引入；本地 `Success: 36 source files`）

### 3.16 P-014（V2 停牌路径账目缺陷修复 · P1）执行记录（2026-11-10，done）

- **立项**: P-013 F-S9-G1 升格；复现脚本 E2 证实：次日路径（`enable_pending_orders=False`）停牌期重复生成清仓单 → 恢复日 `SELL 113600 + SELL 338600 ×2` → 持仓 **-113600** + **5 项 I2 违规**；队列路径（生产默认）无此问题
- **症状订正（E1）**: 原登记「停牌日仍发生买入」**未复现**（掩码两路径均生效），已在 [RESEARCH §4.3](RESEARCH_p014_suspension_accounting.md) 保留原值并标注处置
- **Step 1-2 调研 + Review**: [RESEARCH_p014](RESEARCH_p014_suspension_accounting.md)——P1-P12 事实 + 方案矩阵 U-A~U-E（拒绝 U-B 在途感知 / U-E 持仓层截断）；F-R-P014-1（P2 数值口径）/ F-R-P014-2（P3 漏列 U-E）
- **Step 3-4 设计 + Review**: [DESIGN_p014](DESIGN_p014_suspension_accounting.md)——D1-D10（三层防线：语义对齐 / 生命周期 / 执行兜底）+ I1-I5；F-D-P014-1（P2 单因归因修正）
- **Step 5-6 实施规划 + Review**: [IMPL_p014](IMPL_p014_suspension_accounting.md)——T-1~T-7 / V1-V13；F-I-P014-1（P2 用例数预测）/ F-I-P014-2（P3 夹紧顺序）
- **Step 7-8 验收清单 + 一致性**: [CHECKLIST_p014](CHECKLIST_p014_suspension_accounting.md)——31 项；链接 0 broken、I1-I5 与 T-1~T-7 全映射
- **Step 9 实施**: `core/engine_v2.py`（`_clamp_sell_quantity` / `_cancel_next_day_orders` / `_expire_next_day_orders` + 三处接入）、`core/pending.py`（`cancel_order`）、`core/interfaces.py`（协议声明）；测试 `tests/test_p014_suspension_accounting.py`（8 项）；golden **G7** 新增、**G3 重录**
  - **F5 红→绿**: 红 `7 failed, 1 passed`（@`29cd6fa`，含 `I2 违规 5 项` / `assert 'EXECUTED' == 'CANCELLED'` / 两路径净值 13.19M vs 9.93M）→ 绿 `8 passed`
  - **门禁**: `635 passed` / black **172** unchanged / mypy 0（36）/ 盲区 4 errors 2 files 不劣化 / `tests/*.py` **74**
  - **基线影响**: G1/G2/G4/G5/G6 数值 `IDENTICAL`；G3 `56→55` 笔、NAV `rel 1.11e-6`（涨停日被阻断买单不再跨日重试，与队列路径语义对齐）
  - **实施期发现 5 项**: F-S9-P014-1（P2 mock 签名与协议不一致）/ F-S9-P014-2（P2 协议缺 `cancel_order`）/ F-S9-P014-3~5（P3：`--out-dir` 仓外崩溃未修、G3 描述残留停牌、用例数预测）
- **Step 10 ADD 审计**: 见 CHECKLIST §9（Phase 0-4 + 取证矩阵 E1-E5；**31/31**；P1=0 / P2=2 已修 / P3=3）；**RULE-5 异构复审 pass**（CHECKLIST §9.4：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash，E1 七项 / E2 三项 / E3 八项独立重放全命中，P1=P2=0，P3×3 F-R5-P014-1~3 登记待后续批次）
- **CI 回收**: run `42791704254`（@`6ad7678`）三 job success，3.10/3.11/3.12 各 `628 passed, 1 skipped`（= 本地 635 − 7 项 numba `importorskip`）→ G7 与 8 项性质测试在 `py_func` 路径通过

### 3.17 P-015（外部框架对拍校准 · 单框架打通）执行序与进度（2026-11-10 起）

- **立项**: U-4 触发（用户 2026-11-10 说明外部框架作准确性基准的目的与理由）；用户裁决 ① 正式立项 spec 流程 ② 先一个框架打通再扩展
- **Step 1 调研 + Step 2 Review**: [RESEARCH_p015_external_benchmark.md](RESEARCH_p015_external_benchmark.md) 完稿——本仓事实 P1-P8（E1/E3 @`607f1c3`）；外部证据 A1-A6（vectorbt 1.2.0 / backtrader 1.9.78.123 / pyqlib 0.9.7 PyPI T1 元数据 + F1-F3 降级链留痕：vectorbt.dev JS 渲染 → raw 源码截断 → docs rst 缺路径 → WebSearch T2 片段，权威默认值核验移交 U-P015-3）；框架选择矩阵（**推荐 V-A：VectorBT↔V3 首例**——残差项最少 + 语义同构）与产物形态（**推荐 O-A：隔离 venv + CSV 文件交换**——vectorbt 1.2.0 依赖 pandas>=3.0.3/numba>=0.66 与主环境冲突实锤 A1+A2 双源）；未决项 U-P015-1~3 四元块；引用验证表 F4（4 T1 命中 + 2 部分验证/T2 已标注）；Step 2 门禁四项通过（F2 断言双源满足；F5 默认费用为单源 T2 已标 [单源-待二核]）
- **当前状态**: done（Step 1-10 全通过，2026-11-10）

### 3.17.1 P-015 Step 3-10 执行序（2026-11-10）

- **Step 3-4 设计 + Review**: [DESIGN_p015](DESIGN_p015_external_benchmark.md)——D1-D6（含被拒方案）/ B1-B5 分层恒等式 / I1-I5 / 产物形态 O-A（隔离 venv + CSV 交换）；Step 4 门禁五项通过
- **Step 5-6 实施规划 + Review**: [IMPL_p015](IMPL_p015_external_benchmark.md)——T-1~T-4 / V1-V10 / 风险预案 / F5 形态预注册；Step 6 六项通过
- **Step 7-8 验收清单 + 一致性**: [CHECKLIST_p015](CHECKLIST_p015_external_benchmark.md)——19 项零预填；机械校验 6 链接 0 broken / ID 闭环；P3×2（ID 撞名改连字符形态、B3 措辞）当场回写
- **Step 9 实施**（提交 `5da0c29` 后）:
  - **T-1 venv**: PyPI 官方源两次 ReadTimeout → 清华镜像降级；钉版 vectorbt==1.2.0 / pandas==3.1.1 / numba==0.68.1 / numpy==2.5.4；`audit_signatures.py` 权威读数 → **U-P015-3 关闭**（A5 T2→E1）
  - **T-2/T-3**: `_spec.py` 规格层 + export/run/verify 三脚本；**F5 红→绿**（红 exit 1 缺 vbt 侧 → 绿 exit 0 七项 0 失败）
  - **实施期发现 5 项**（F-S9-P015-1~5，全回写）：① from_signals 不支持 TargetPercent → B2 改 from_orders(targetpercent)；② **V3 无现金约束 vs vbt 部分成交**（B4 初版负持仓实锤，`allow_negative` 不存在）→ B4 重构常量价翻转 + 语义差登记 M4；③ API 漂移（cash 方法 / 无 asset_qty）；④ I2c 闭式一般化（路径分叉后现金项不抵消）；⑤ B3/B5 fees>0 全等结构性不可达 → 断言重定义 + 阴性对照移 V3 侧
  - **终态**: 29 项断言 0 失败（I1 全零 / I2c 2.0e-10 / I3 一致性+缺口 38658.94 / I4 5.8e-11 / I5 −10000.000000 精确）——**P-017 口径更正**：原计数含 B5 恒真豁免行 1 项，P-016 D1 后口径 = **28 项断言 + 1 项豁免登记**（见 [CHECKLIST_p016 §9.4](CHECKLIST_p016_p015_review_fixes.md)）
- **Step 10 ADD 审计**: CHECKLIST §9——Phase 0-4 全过 / 取证矩阵 E1-E5 / **19/19 ✅** / P1=P2=P3=0 / E4 零发现（降级重扫确认）；门禁 **635 passed / black 0 / 主环境 pip list 零污染**；[BACKTEST_CALIBER_MAPPING §2.2](BACKTEST_CALIBER_MAPPING.md) 获首个实测列（同提交）；报告 [APPENDIX_p015](APPENDIX_p015_external_calibration.md)（M1-M5：**零不可解释残差，准确性校准通过**）；**RULE-5 异构复审 pass**（CHECKLIST §9.4：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash，E1 九项 / E2 三探针（含 B5 单跑负路径 + 独立重写规格核算 I2c=2.02e-10）/ E3 六组锚点独立重放全命中，P1=P2=0，P3×3 F-R5-P015-1~3 登记待后续批次）；CI run `42809038823`（@`07ddeb3`）+ `42809138807`（@`eab4594`）双 success

---

### 3.18 P-016（P-015 复审 P3 修正）执行记录（2026-11-10，done）

- **立项**: P-015 RULE-5 复审 §9.4 的 F-R5-P015-1~3；档位 **T1**（Layer-1 路径 + 无本地 T2 先例 → fail-closed）
- **Step 1-2**: [RESEARCH_p016](RESEARCH_p016_p015_review_fixes.md)——P1-P9 事实（E3 @`90eb879`）+ **本轮 E1 红读数 A/B/C**（豁免被计为断言 / rate>0 无防线 / `--report` 覆盖人工章节）；方案矩阵 N-A/W-A/X-A/R-A；未决项 U-P016-1；F1-F4 = N/A（无外部来源）
- **Step 3-4**: [DESIGN_p016](DESIGN_p016_p015_review_fixes.md)——D1 三态词表 / D2 报告人工章节保护 / D3 fail-fast / D4 只补文档映射；I1-I6；七项被拒方案
- **Step 5-6**: [IMPL_p016](IMPL_p016_p015_review_fixes.md)——T-1~T-5 / V1-V8 / 风险与回退 / F5 预注册
- **Step 7-8**: [CHECKLIST_p016](CHECKLIST_p016_p015_review_fixes.md)——18 项零预填；机械校验 10 链接 0 broken / ID 闭环；P3×2（P6 风险表述→既成事实、D2 代价列）当场回写
- **Step 9 实施**:
  - `verify_p015.py`：`Checks` 三态（`add`/`waive`/`finalize`）+ `_REPORT_MARK` + `MANUAL_MARKERS` + `_resolve_report_target`
  - `_spec.py`：`simulate_vbt_spec` 对 `cost_rate > 0` 抛 `NotImplementedError`
  - **F5 红→绿三组**：A 豁免渲染（`PASS`→`WAIVER(非断言)`）/ B 守卫（静默返回→异常）/ C 保护（覆盖→改名 + 原文件哈希不变）
  - **F-S9-P016-1（P2，已修）**：`git show HEAD:APPENDIX` 证实 P-015 入库版 §1/§3/§4 **已是占位模板**——覆盖已真实发生（black 后最终复放所致）；本批重新回填 §1（E1 现场重放签名核验）/§3（M1-M5）/§4（实跑命令）
  - **F-S9-P016-2（P3，登记）**：P-015 RULE-5 复审 E1 九项未覆盖「交付物内容完整性」→ 未发现已发生的覆盖；建议后续复审增「生成物占位残留扫描」
  - **终态**: `28 断言（失败 0）+ 豁免 1`，exit 0；生成版与入库版 §2 **逐行一致**；`635 passed` / black 0 / 主环境零污染
- **Step 10 ADD 审计**: CHECKLIST §9——Phase 0-4 全过；取证矩阵 E1×9 + E3×1 + E4「发现 1 项」（保护只判标记存在、不判生成态，低风险不阻断）；**18/18 ✅**；RULE-5 异构复审 pass（详见下行）
- **CI 回收**: 本地 `635 passed` / black 5 unchanged；远端 run `42815329691`（@`4a1cdb4`）**三 job success**；`42815809194`（@`bd50b54`）success
- **RULE-5 异构复审（2026-11-10）**: **pass（0 P1 / 0 P2 / 4 P3 登记）**——[CHECKLIST_p016 §9.4](CHECKLIST_p016_p015_review_fixes.md)：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；E1 十项（含采纳 F-S9-P016-2 的**生成物占位残留扫描**——唯一真实残留 = IMPL_p015 §8.5）；E2 六探针（全链 28+1 复放 / B5 单跑负路径 / 守卫正负双路径 / **worktree @`90eb879` 三组红读数独立重放全复现**：A 逐字（旧 5 断言含恒真豁免 + exit 1）、B 逐位（`pv_last=9843199.479897` 静默产出）、C 含行号（L8/L47 占位覆盖）/ 报告保护正路径 ORIG 零改动）；E3 锚点全命中（三态词表 / 保护 / 守卫 / 三处文档映射注 / APPENDIX 回填 ↔ audit_signatures 现场读数）；**P3×4 登记**：F-R5-P016-1（PROGRESS §3.17.1 终态行「29 项断言」未注口径更正）/ -2（IMPL_p015 §8.5 占位残留）/ -3（MANUAL_MARKERS 子串自指：`.generated` 级联 + B-3 路径对生成器产物不可达）/ -4（CHECKLIST E-1 docs 计数 6 ≠ 实际 9）

---

### 3.19 P-017（P-016 复审 E4 四项 P3 修正）执行记录（2026-11-10，done）

- **立项**: P-016 RULE-5 复审 §9.4 E4 的 F-R5-P016-1~4；档位 **T1**（Layer-1：`scripts/external_benchmark/verify_p015.py`）
- **Step 1-2**: [RESEARCH_p017](RESEARCH_p017_p016_review_fixes.md)——P1-P5 事实（E3 @`4a34c49`）+ E1 红读数（级联实证 `…generated.generated.md` / `git show --stat 4a1cdb4` = 12 文件 / 占位扫描 35→1 真实残留 / 绿态 28+1）；方案矩阵 N-A / M-A / G-A / C-A；F1-F4 = N/A（无外部来源）
- **Step 3-4**: [DESIGN_p017](DESIGN_p017_p016_review_fixes.md)——D1 口径注不改数值 / D2 占位回填 + 未保全声明 / D3 生成物命名空间守卫 / D4 计数更正 + 分支精确化；I1-I5；八项被拒方案
- **Step 5-6**: [IMPL_p017](IMPL_p017_p016_review_fixes.md)——T-1~T-5 / V1-V6 / 风险与回退 / 排除低效操作
- **Step 7-8**: [CHECKLIST_p017](CHECKLIST_p017_p016_review_fixes.md)——13 项零预填；机械校验 10 链接 0 broken / ID 闭环；**F-S8-P017-1（P3）**：IMPL §6 初稿误预填 Step 9 读数（违反 RULE-1），当场删除
- **Step 9 实施**:
  - `verify_p015.py`：新增 `GENERATED_SUFFIX = ".generated"` + `_resolve_report_target` 四分支（新增「生成物 → 原地重写」守卫），改名表达式改用常量
  - 文档：PROGRESS §3.17.1 + §1.4 两处口径注；IMPL_p015 §8.5 占位 → 读数表；CHECKLIST_p016 E-1 计数更正 + B-3 分支精确化
  - **F5 红→绿**：红 = 指向 `.generated.md` 复放产出 `.generated.generated.md`（三文件并存 7767/3913/3913 B）；绿 = 同命令原地写入、`CASCADE_EXISTS=False`
  - **四分支探针**：A① 策展版改名 / A② 生成物原地 / C 副本 `ORIG_UNCHANGED=True` / D 存在无标记 `OVERWRITTEN=True` → `RESULT: ALL_PASS`
  - **终态**: `28 断言（失败 0）+ 豁免 1` ×4 复放；`pytest` **635 passed**（47.26s）/ black 5 unchanged / 项目解释器无 vectorbt；占位真实残留 **0**
  - **环境取证说明**：本终端 `python` 默认解析到 Anaconda 3.13.5（自带 vectorbt 0.28.4），全部读数改用项目解释器 `…Python312\python.exe`（3.12.10）复跑
- **Step 10 ADD 审计**: CHECKLIST §9——Phase 0-4 全过；取证矩阵 E1×8 + E3×1 + E4 零发现；**13/13 ✅**；RULE-5 未执行（P3 小修批）
- **CI 回收**: 远端 run `42819919916`（@`319c450`）**success**
- **RULE-5 异构复审（2026-11-10）**: **pass（0 P1 / 0 P2 / 2 P3 登记 + 1 观察）**——[CHECKLIST_p017 §9.4](CHECKLIST_p017_p016_review_fixes.md)：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；E1 十项（pytest 以 `MPLBACKEND=Agg` 出具 **635 passed**——默认 TkAgg 全量间歇 `TclError` 为本地环境态；占位扫描 12 命中全为引用、真实残留 0）；E2 九探针全 PASS（四分支 + I1 + I3 + P-016 守卫未回归 + **worktree @`4a34c49` 红读数重放复现级联** + 复审补覆盖分支 1）；E3 锚点全命中（`:254/:268/:272` ↔ DESIGN §4 逐字）；**P3×2 登记**：F-R5-P017-1（无扩展名目标 `bar.generated` 二次运行仍级联——`stem` 剥离后缀致守卫不命中；正常 `.md` 用法不受影响）/ F-R5-P017-2（分支 1 覆盖归因失实——作者探针 A①/C/D 目标运行前均存在，分支 1 未被直接覆盖；行为本身正确，复审探针补覆盖 PASS）；观察：本地全量跑建议固定 `MPLBACKEND=Agg`

---

### 3.20 P-018（P-017 复审 E4 两项 P3 修正）执行记录（2026-11-10，done）

- **立项**: F-R5-P017-1 / -2；档位 **T1**（Layer-1：`scripts/external_benchmark/verify_p015.py`）
- **Step 1-2**: [RESEARCH_p018](RESEARCH_p018_p017_review_fixes.md)——P1-P4 事实（E3 @`97b71b2`）+ E1 红读数（`rep.generated` 连跑两次 → `rep.generated.generated` 1820B 级联）+ 归因复核（A①/C/D 目标运行前均存在）；方案矩阵 G-A / N-A；G-B/C/D 与 N-B/C 被拒理由；F1-F4 = N/A
- **Step 3-4**: [DESIGN_p018](DESIGN_p018_p017_review_fixes.md)——D1 守卫并判 name 与 stem（零行号位移约束）/ D2 归因注 + 补真实覆盖探针；命中矩阵四行；I1-I4
- **Step 5-6**: [IMPL_p018](IMPL_p018_p017_review_fixes.md)——T-1~T-3 / V1-V5 / 三项风险预案
- **Step 7-8**: [CHECKLIST_p018](CHECKLIST_p018_p017_review_fixes.md)——10 项零预填；机械校验 8 链接 0 broken / ID 闭环；一致性 0 发现
- **Step 9 实施**:
  - `verify_p015.py`：`:268` `path.stem.endswith` → `path.name.endswith or path.stem.endswith`（1:1）；`:261` docstring 同步——行号零位移
  - 文档：IMPL_p017 §6.2 / CHECKLIST_p017 C-4 追加 P-018 更正注（原句逐字保留）
  - **F5 红→绿**：红 = `rep.generated` + `rep.generated.generated`（1820B×2）；绿 = `noext_exists=True cascade=False`
  - **8 探针全 PASS**：全链 / 无扩展名 ×2 / `X.generated.md` 原地 / 分支 3 SHA / 分支 4 覆盖 / **分支 1 真实覆盖（`FRESH_EXISTS=True`）** / 行号锚点 `:254/:268/:272`
  - **终态**: `28 断言（失败 0）+ 豁免 1` exit 0；`635 passed`（`MPLBACKEND=Agg`，64.62s）/ black 5 unchanged
- **Step 10 ADD 审计**: CHECKLIST §9——Phase 0-4 全过；取证矩阵 E1×7 + E3×1 + E4「发现 1 项」（`a.generated.bak` 形态属命名契约内后果，不阻断）；**10/10 ✅**；RULE-5 未执行（P3 小修批）
- **CI 回收**: 远端 run `42837224919`（@`0410505`）**success**
- **RULE-5 异构复审（2026-11-10）**: **pass（0 P1 / 0 P2 / 1 P3 登记 + 1 观察）**——[CHECKLIST_p018 §9.4](CHECKLIST_p018_p017_review_fixes.md)：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；E1 八项（pytest Agg **635 passed** / 占位扫描真实残留 0 / 代码零位移核对）；E2 十一项读数全 PASS（全链 + 命中矩阵四形态 + **幂等形态 `X.generated.generated` 不膨胀** + B5 负路径 + P-016 守卫未回归 + **worktree @`97b71b2` 红读数重放复现无扩展名级联**）；E3 锚点全命中（`:268` 并判判定 ↔ DESIGN §4 逐字 / 零位移达成——P-017 行号漂移观察项未复发 / 两处归因更正落位）；**P3×1 登记**：F-R5-P018-1（分支 1「父目录不存在」形态 `write_text` 抛 `FileNotFoundError` 实测 exit 1，IMPL §6.2 探针 ⑥「含不存在的父目录」覆盖声明失实——**F-R5-P017-2 归因失实模式复发**）；观察：`endswith` 大小写敏感（无现实触发面）

---

### 3.21 P-019（报告写入父目录缺失修正）执行记录（2026-11-10，done）

- **立项**: F-R5-P018-1；档位 **T1**（Layer-1：`scripts/external_benchmark/verify_p015.py`）
- **Step 1-2**: [RESEARCH_p019](RESEARCH_p019_report_parent_dir.md)——P1-P4 事实（E3 @`6149cc6`）+ E1 红读数（`FileNotFoundError` traceback / exit 1）+ 写入点唯一性；方案矩阵 M-A；M-B/C/D 被拒理由；F1-F4 = N/A
- **Step 3-4**: [DESIGN_p019](DESIGN_p019_report_parent_dir.md)——D1 写入前 mkdir / D2 归因注 + 真探针；I1-I4；实现规格
- **Step 5-6**: [IMPL_p019](IMPL_p019_report_parent_dir.md)——T-1~T-3 / V1-V5 / 三项风险预案
- **Step 7-8**: [CHECKLIST_p019](CHECKLIST_p019_report_parent_dir.md)——10 项零预填；机械校验 8 链接 0 broken / ID 闭环；一致性 0 发现
- **Step 9 实施**:
  - `verify_p015.py`：`:324` 增 `target.parent.mkdir(parents=True, exist_ok=True)`（+1 行，`:254/:268/:272` 零位移）
  - 文档：IMPL_p018 §6.2 / CHECKLIST_p018 B-3 追加 P-019 更正注（原句保留）
  - **F5 红→绿**：红 = `FileNotFoundError` traceback / exit 1；绿 = `EXIT=0 EXISTS=True`
  - **7 探针全 PASS**：父目录缺失 / 多级父目录 / 父目录已存在 / 全链 / 分支 3 SHA / 无扩展名无级联 / 锚点零位移
  - **探针首轮误判**：仅传 B1 时 I5 跨 case 阴性对照未齐 → exit 1（非父目录缺陷），改传五 case 后全 exit 0
  - **终态**: `28 断言（失败 0）+ 豁免 1` exit 0；`635 passed`（`MPLBACKEND=Agg`，64.29s）/ black 5 unchanged
- **Step 10 ADD 审计**: CHECKLIST §9——Phase 0-4 全过；取证矩阵 E1×6 + E3×1 + E4 零未登记发现；**10/10 ✅**；RULE-5 未执行（P3 小修批）
- **CI 回收**: 远端 run `42844710498`（@`d17eb62`）+ `42845513267`（@`59afb6a`）+ `42865666688`（@`77abe41` 复审回写）均 **success**
- **RULE-5 异构复审（2026-11-11）**: **pass（0 P1 / 0 P2 / 0 P3 登记 + 2 观察）**——[CHECKLIST_p019 §9.4](CHECKLIST_p019_report_parent_dir.md)：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；E1 八项（HEAD=origin/master=`59afb6a` 干净 / CI `42844710498`+`42845513267` 双 success / 变更面 9 文件 / 解释器 3.12.10 无 vectorbt / pytest Agg **635 passed** / 占位扫描真实残留 0 / 代码零位移 `:254/:268/:324`）；E2 十一项读数全 PASS（父目录缺失 `EXIT=0` / 四分支与无扩展名守卫不回归 / 全链 `28 断言（失败 0）+ 豁免 1` exit 0 / B5 负路径 exit 1 / P-016 守卫 / 边界父路径为文件 `FileExistsError` 不吞异常 / **worktree @`6149cc6` 旧代码红重放 FileNotFoundError 复现——红绿对照成立**）；E3 锚点全命中（`:324` mkdir ↔ DESIGN D1 逐字 / 零位移达成——P-017 行号漂移观察项未复发 / IMPL_p018 L101 + CHECKLIST_p018 L27 两处更正注落位）；E4：**0 P3 登记 + 2 观察**（① 父路径被文件占用抛 `FileExistsError`——DESIGN §1 声明边界 OSError 同族，作者 E4 只点名 `PermissionError`，复审补登记；② 复审探针 ⑨ 自身断言缺陷——初判只查 stdout 漏 stderr，修正后 PASS，如实登记）

---

### 3.22 P-004（数据层统一）执行记录（2026-11-11，done）

- **立项**: [PROGRESS §1.4](#14-未完成事项) 唯一 P2（2026-11-10 盘点上调）；档位 **T1**（Layer-1：`core/data*.py`、`core/interfaces.py`、`core/engine_v2.py`、`core/factory.py`、`filter/`）
- **前置**: 已满足——P-012 B6 已交付 `DataProvider` 端口 + `PklDataProvider` + 契约测试（U-9 B-A 边界，消费方迁移归本批）
- **Step 1-2**: [RESEARCH_p004](RESEARCH_p004_data_layer_unification.md)——P1-P9 事实（E3 @`3af285a`）+ E1 五读数（DataManager 170 处/35 文件 = 生产 62/16 + 测试 108/19；DataLoaderV3 72/14；构造点 6；`635 passed`（Agg 64.22s）；死 API 零调用）+ 成员级消费方图 + 7 维方案矩阵
- **关键发现（FALSIFIED）**: TD-1「`DataLoaderV3` 是按 V1 替代品设计、接口兼容已就位」不成立——`from_data_manager` 外部调用 **0**、V3 仅 10 个公开成员且无因子/复权/辅助数据能力（24 vs 10）；**合并到 V3 不可达**
- **方案判定**: **M-A**（`DataManager` 保留门面 + 注入 `DataProvider` 统一 I/O，删 V3 死 API）为首批；M-B（端口扩全 + 消费方迁移）后置独立批次；M-C 证伪；M-D 否决。建议 B1（端口注入，零行为）→ B2（删死 API + agents 直读改端口）→ B3（协议对齐）→ B4（可选扩全）
- **Step 2 Review**: 通过（1 项 FALSIFIED 表述更正 + 1 项边界方向细化；不阻断）；未决项 U-P004-1~4 已登记
- **RULE-5 异构复审（2026-11-11）**: **pass（0 P1 / 0 P2 / 3 P3 登记并已回写 + 3 观察）**——[RESEARCH_p004 §9](RESEARCH_p004_data_layer_unification.md)：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；E1 八项重放（170/35、62/16+108/19、72/14、死 API 零调用、pytest Agg **635 passed**（78.45s）六项复现；测试构造点与 filter 计数两项更正）；E2/E3 补扫：**F-R5-P004-2**（协议 `get_adj_price` 形参 `adjustment` ≠ 实现 `adjustment_type`，关键字调用 TypeError——契约测试只锁成员不锁签名，转入 B3 以实现签名为准修订 + 锁签名）+ `AbstractDataManager` 零消费方死代码（观察 1，转入 B2 清单）+ web docstring 词元澄清 + filter 非 clean 模块疑似孤儿（TD-5 范畴不并入）；F-R5-P004-1（测试构造点实测 **37 处/13 文件**）/ F-R5-P004-3（filter 38 行/53 匹配、辅助字段 15 处）均已回写；三大主结论（FALSIFIED / M-C 证伪 / M-A 路线）独立重放全部成立
- **Step 3-4**: [DESIGN_p004](DESIGN_p004_data_layer_unification.md)——D1-D6 / I1-I6 / B1-B3 实现规格 / V1-V8 / 六项风险预案；Step 4 Review 通过。设计期补核发现**第二处协议签名不一致**（`load_factor(name)` ≠ 实现 `load_factor(factor_file)`，已回写 RESEARCH P7）；D5 主动收窄 RESEARCH B2：agents `data_dir` 直读**移出本批**（原样 pickle vs 对齐 DataFrame，非零行为）；D6 更正 golden 为 **7 份（G1-G7）**
- **DESIGN RULE-5 异构复审（2026-11-11）**: **pass（0 P1 / 1 P2 已修入 §4.1 / 1 P3 已更正 / 3 观察已吸收）**——[DESIGN_p004 §9](DESIGN_p004_data_layer_unification.md)：复审基座 GLM-5.3-Flash ≠ 设计作者 DeepSeek-V4.1-Flash；E1 七项重放（四签名断言、B2 六处行锚、D5 证据、`load()` 无连锁全命中；`get_adj_price` 15 处消费调用复现 + 发现全仓唯一关键字自调用 data.py:455 补强论据）；**F-D-R5-P004-1（P2）**：§4.1 `_load_auxiliary_data` 规格缺 **cfg-falsy 守卫**——`mktcap_file` 默认 None → aux_map 过滤 → `load_aux` 走 provider `raise ValueError`，照初稿实现默认配置必崩（现状 = 跳过保持 None），已修入 §4.1 + §6 风险表；F-D-R5-P004-2（P3）：`load_factor` 计数 7→**9**（漏 examples 2 处）已更正；观察：kind 白名单三处硬编码（IMPL 以 `_PRICE_KINDS` 收敛）/ `industry_file` falsy 异常路径漂移（IsADirectoryError→静默 None，B4 统一）/ data.py:455 关键字自调用论据
- **Step 5-6**: [IMPL_p004](IMPL_p004_data_layer_unification.md)——T-1~T-7（B1 provider 构造/价格/辅助/universe/归一化；B2 死 API 删除；B3 协议签名 + 契约测试）/ V1-V8 / 8 项风险预案；**外部锚点 7 条已验证 + 1 条未验证**（Cockburn HaT TR 2005.02、PEP 544 Final、Fowler Strangler Fig、Feathers Seam、Qlib Data Layer、Nunkesser ICSOFT 2022 DOI、`inspect.signature`；F3 降级链：MCP 搜索 522 → 内置 WebSearch）；工程细节：`_PRICE_KINDS` 单一来源、cfg-falsy 守卫、`_load_and_align_data(data, label)` 与幂等测试 wrapper 一行适配、B1/B2/B3 三提交测试面增减；Step 6 Review 通过；F5 = N/A（Step 9 回填红/绿，不预填）
- **Step 7**: [CHECKLIST_p004](CHECKLIST_p004_data_layer_unification.md)——**24 项**（A6 端口注入 / B4 死 API 删除 / C5 协议对齐 / D5 零行为回归与门禁 / E4 文档治理），实测列全 `[待 Step 9]` 零预填；含 F-D-R5-P004-1（mktcap 默认 None 不崩）、F-R5-P004-2（两处形参名 + 关键字调用回归）、`_PRICE_KINDS` 单一来源、DI 注入、三提交切分等验收
- **CI 回收**: 远端 run `42872934713`（@`997ffeb`，Step 1-2 + 复审回写提交）+ `42992764101`（@`e53b03f`，DESIGN + 设计复审回写提交）均三 job **success**；Step 5-8 提交 `b2e3f63` run [`43001831287`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43001831287) 三 job **success**（3.12 1m21s / 3.11 1m46s / 3.10 1m53s）；Step 9 提交链 `3ddc895`→`8b72145`→`bb50009` + 回写 `4d1a47b` run [`43005785446`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43005785446) 三 job **success**（3.12 1m47s / 3.11 1m12s / 3.10 1m57s）；Step 10 收口提交 `946fe01` run [`43007130246`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43007130246) **success**
- **Step 8 一致性 Review（已完成 2026-11-11）**: [CHECKLIST_p004 §8](CHECKLIST_p004_data_layer_unification.md)——机械校验 pass（**14 个唯一链接目标 0 broken**；24 项验收 = 24 处 `[待 Step 9]` 零预填；ID 闭环：U-P004 ×7 / F-D-R5-P004-1 / F-R5-P004-2 / `_PRICE_KINDS` ×4 / G1-G7 ×4 / D-I-T-V 全跨文档）；对齐矩阵 8 行全贯通（RESEARCH §6 B1-B3 → DESIGN → IMPL T 组 → CHECKLIST A-E 组；B2② 与 B3②③ 两处收窄均显式登记）；**2 项 P3 + 1 笔误已修**——F-S8-P004-1（IMPL 验证项 V 编号与 DESIGN 同 ID 异义：IMPL 重排 V1-V8 + CHECKLIST 六处引用同步）、F-S8-P004-2（RESEARCH B3 两扩展子项「多资产成员去留 / 消费方类型标注迁移」在 DESIGN 静默收窄 → §1 出界清单补登，B4 承接）、IMPL T-1 标题 ID 形态笔误（→「DESIGN §9 观察 1」）；**结论：通过，可进入 Step 9**
- **Step 9 实施（已完成 2026-11-11）**: 三独立提交 `3ddc895`(B1 端口注入) → `8b72145`(B2 死 API 删除) → `bb50009`(B3 协议对齐)；F5 红/绿逐批入档 [IMPL §8](IMPL_p004_data_layer_unification.md)：B1 红 `TypeError: ... unexpected keyword argument 'provider'` → 绿 `635 passed`（持平）；B2 红 四死 API `hasattr=True` → 绿 `634 passed`；B3 红 `2 failed`（`universe_status` 缺失 + `adjustment != adjustment_type`）→ 绿 `636 passed`。终态门禁：black **110 unchanged** / mypy **36 files 0** / V6 死 API grep **0 命中** / V8 外部对拍 **28 断言（失败 0）+ 豁免 1，exit 0**；CHECKLIST **24/24 ✅**；**Step 9 发现 1 项 P3（F-S9-P004-1）**：`test_adjustment_semantics` 实为 4 用例（原写 2，合计 13→15），已同步 DESIGN/IMPL/CHECKLIST
- **Step 10 ADD 审计（已完成 2026-11-11）**: [CHECKLIST_p004 §9](CHECKLIST_p004_data_layer_unification.md)——四阶段全过（Phase 0 六决策可证伪 / Phase 1 D1-D6 逐项落地 / Phase 2 diff 全文审读与 DESIGN §4 逐字对应、变更面恰 6 文件、6 构造点零改动 / Phase 3 新增对象仅规格内四项 / Phase 4 零行为意图三重证实）；取证矩阵 10 类手段回填（RULE-6）；**E4 盲区扫描 2 项观察**（data_v3 类 docstring「向后兼容」残留失实 / data.py `pickle`+`lru_cache` 删除前已存在的未使用导入）——均文档残留类，登记不阻断，留 B4/TD-5；审计结论 **P1 = P2 = P3 = 0，ADD 通过**；签字表 §10 九行落齐
- **本批收口**: P-004 全链 done（台账 §1.4 已更新）——台账唯一 P2 清零；终态 `636 passed` / black 110 / mypy 36 files 0 / 死 API grep 0 / V8 对拍 28 断言 + 1 豁免 exit 0；遗留：U-P004-1~4 未决项、B4（端口扩全 / agents 直读 / RESEARCH B3 两扩展子项）、E4 观察 2 项（TD-5 范畴）、P-005（前置「P-004 之后」已解除）

---

### 3.23 P-005（Factor_DB 文档与依赖对齐）执行记录（2026-11-11，done）

- **立项**: [PROGRESS §1.4](#14-未完成事项) P3（前置「P-004 之后」已解除）；档位 **T1**（`cli.py` 运行时输出 + `pyproject.toml` 打包面）
- **Step 1-2**: [RESEARCH_p005](RESEARCH_p005_factor_db_alignment.md)——P1-P9 事实（`database.py` 236 行 JSON 元数据 + Parquet / 唯一生产消费方 `BatchBacktestEngine` / README 三处 + web 一处 + ARCHITECTURE 依赖表一处文档残留 / 零 `import duckdb` / `factor_db/` 零数据）+ 外部锚点 E1-E4（DuckDB Concurrency、pandas `to_parquet` v3.0.6、Packaging Guide、DuckDB Parquet 直读）+ 七维矩阵 M-A~M-D + U-P005-1~4
- **方案判定**: **M-A**（文档与依赖对齐）采用；M-B 迁移 DuckDB **否决**（零数据 + 单消费方 + 无基准 + E1 小事务非设计目标 + E4 可直读 Parquet）；M-C 抽象证伪；M-D 缺陷修复移出（U-P005-2）
- **Step 2 Review**: 通过（0 P1/P2；1 项措辞收敛：M-D 改独立立项）；RULE-5 未执行（RESEARCH §8 待用户指派）
- **Step 3-4**: [DESIGN_p005](DESIGN_p005_factor_db_alignment.md)——D1-D5 / I1-I5 / §4 实现规格 / V1-V5；Step 4 Review 通过
- **Step 5-6**: [IMPL_p005](IMPL_p005_factor_db_alignment.md)——T-1~T-6 / B1-B2 切分 / V1-V5；Step 6 Review 通过；F5 = N/A（Step 9 回填红/绿）
- **Step 7**: [CHECKLIST_p005](CHECKLIST_p005_factor_db_alignment.md)——**15 项**（A5 文档对齐 / B3 依赖与 CLI / C4 回归门禁 / D3 治理），实测列零预填
- **Step 8 一致性 Review**: [CHECKLIST_p005 §8](CHECKLIST_p005_factor_db_alignment.md)——6 唯一链接 0 broken / 15=15 预填 / 对齐矩阵 7 行；**F-S8-P005-1（P3）**已修（web 等宽字符方向写反）
- **Step 9 实施**: B1 `938f413` + B2 `fb94280`；F5 红 6 命中 → 绿 0；`info` 含 → 不含 duckdb；deps **26 → 25**；`636 passed`（76.41s）/ black 111 / mypy 36 files 0；**F-S9-P005-1~3（P3）**已修（架构图同列两 token / README 规划表述与 D-1 冲突 / ARCHITECTURE 注插错位）
- **Step 10 ADD 审计**: [CHECKLIST_p005 §9](CHECKLIST_p005_factor_db_alignment.md)——Phase 0-4 全过 + 取证矩阵 10 类；**F-S10-P005-1（P2，`uv.lock` 仍锁 duckdb）已由 B3 修复（−44 行）**；F-S10-P005-2（P3，`DECISIONS` ADR-001 状态失真）已修；E4 3 观察（D-1 允许集修订 / U-P005-5 锁漂移 / PATH 解释器）；结论 P1=0 / P2=1 已修 / P3=4 已修；**15/15 ✅**
- **CI 回收**: 远端 run [`43012172205`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43012172205) 三个 job **success**（3.10 1m51s / 3.11 1m53s / 3.12 1m22s）+ 回填提交 run `43012554920` **success**
- **RULE-5 异构复审（2026-11-11，全批）**: **pass（0 P1 / 0 P2 / 3 P3 登记 + 3 观察）**——[CHECKLIST_p005 §9.5](CHECKLIST_p005_factor_db_alignment.md)：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；E1 八项重放全复现（变更面 numstat / 红 6 行 grep / 绿 0 / deps 25+uv.lock 30 / **636 passed** 44.44s 复审自跑 / black 111 / mypy 0）；E2 红绿对照成立（旧 `cli.py` @`586e817` 落临时脚本重放 `info` 打印 `duckdb 1.5.3` ↔ 当前无）；E3 锚点全命中（`database.py` 7 def + `FactorMetadata` L36-40 五统计键与 README `update_stats(...)` 逐字吻合 / `query` 四参数逐字吻合 / RESEARCH P1-P9 重放）；**F-R5-P005-1（P3，IMPL T-1 引用行误为 ARCHITECTURE 中文行 + 「7 字符→7 字符」注记错）已回写**、**F-R5-P005-3（P3，RESEARCH 头部 §8 编号）已回写**、**F-R5-P005-2（P3，ARCHITECTURE L66-68 `Price数据/Macro/News/Alternative` 同源幻觉残留——grep 词元法不可见，Step 8/10 漏扫）登记留后续文档批 + U-P005-3 判据补强**；E4 观察 3 项（README 测试计数 507/48 files 与 ARCHITECTURE「489 个」漂移——实测 636，先于本批 / README L196 裸 ID 无链接 / uv.lock `provides-extras` TOML 子表探测注）；复审记录提交 `f3cf3b8` run [`43015720127`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43015720127) 三 job **success**
- **本批收口**: P-005 done；文档与依赖面收敛到实现真相且零行为；遗留 U-P005-1/2/4/5 未决项 + F-R5-P005-2 幻觉残留（后续文档批）

---

### 3.24 P-020（文档一致性收尾）执行记录（2026-11-11，done · T3 轻批）

- **立项**: P-005 RULE-5 复审 [§9.5](CHECKLIST_p005_factor_db_alignment.md) F-R5-P005-2 + E4 观察 1/2；档位 **T3**：Layer-0 纯文档订正，零代码 / 零门禁（改前路径集 `README.md` / `docs/ARCHITECTURE.md` 不落 scripts/tests/tools）
- **5 步决策流**: ① **范围** = 只修文档真相（`ARCHITECTURE` 图表幻觉 + 测试计数 + 裸 ID），不动代码/依赖 ② **依据** = RULE-5 实测读数（`database.py` 7 def / 636 passed / 71 测试文件）③ **修法** = 图表 token 逐格对照能力清单；计数取 pytest 实际读数 ④ **不做** = U-P005-2 缺陷修复 / U-P005-5 重锁 / P-024 B4（各自独立批）⑤ **回退点** = 单提交可 `git revert`
- **变更面**: `docs/ARCHITECTURE.md`（L3/L269 测试数 + L66-68 三 token，列宽 14 不变）/ `README.md`（L7 badge、L98、L263、L412、L196 链接、L441 失效链接）/ `docs/PROGRESS.md`（P-020 行 + U-P005-1/2/4/5 补登 + 本节）
- **实施期新增发现（2 项，均同批修复）**: ① ARCHITECTURE L269「489 测试通过」为第二处计数漂移（首轮只扫到 L3）→ 同改 636；② README L441 `[CONTRIBUTING.md](CONTRIBUTING.md)` 目标不存在（真断链）→ 移除链接保留文案
- **验证**: 全量 `636 passed`（Agg，项目解释器）/ black 111 unchanged / mypy 36 files 0 / 相对链接 0 broken / `Grep 'Price数据|Macro/News|Alternative'` = 0 / `Grep '507|489'` 在 README/ARCHITECTURE 头部 = 0
- **T3 证据出口**: session（本节）+ PROGRESS 行 + 机械校验三项（链接存在性 / 零预填 / ID 闭环）+ 回退点；`console_gen --check` **N/A**——仓内无受跟踪 `CONSOLE.md`，且工具对本仓 PROGRESS 解析为「P 行=13 / done=0」与事实不符，生成会引入错误派生物（诚实边界，不伪造通过）
- **CI 回收**: 远端 run [`43019737462`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43019737462) 三个 job **success**（3.10 1m49s / 3.11 1m28s / 3.12 1m32s）

---

### 3.25 P-021（依赖与锁维护）执行记录（2026-11-12，done · T1）

- **立项**: P-005 RULE-5 §9.5 E4 观察 2（`uv lock --check` 失败——锁根包 `provides-extras = ["dev"]` 缺 `web`）+ U-P005-5；同批承接 U-P005-4（`pyarrow`/`fastparquet` 是否声明）；档位 **T1**（`uv.lock` 真值面，判档规则 2 保守升级）；规范源 SPEC_PROCESS **v1.7.2**
- **Step 1-8**: 四文档落稿（RESEARCH P1-P9 + E1-E5 锚点 / DESIGN D1-D5 + I1-I5 / IMPL T-1~T-3 + V1-V5 / CHECKLIST 15 项零预填）；Step 2 Review 0 P1/P2（M-D CI 门禁改登记 U-P021-1）；Step 4/6 Review 通过；Step 8 一致性 **0 发现**（17 处 `[待 Step 9]` = 15 格 + 2 合法）
- **Step 9 实施**: B1 `2245962`（`uv.lock` `+1207/−2`：plain `uv lock`，extras `["dev"]→["dev","web"]`、120→148 包 / 新增 19、既有 pin changed 0 / removed 0、duckdb 0、旧锁 black specifier `>=23.0.0→~=26.0`）/ B2 `6c4adb5`（`ARCHITECTURE` §9.2 改「可选与未声明依赖」3 行 + 3 条纪律，`+7/−6`）/ B3 docs；`uv lock --check` **1 → 0**、`uv export --frozen` exit 0（325 行）；**636 passed**（49.83s）/ black 111 unchanged / mypy 36 files 0；`pyproject.toml` 零改动；F-S9-P021-1（旧锁 black specifier 漂移，P3）已随 B1 修正
- **Step 10 ADD 审计**: [CHECKLIST_p021 §9](CHECKLIST_p021_dependency_lock_maintenance.md)——Phase 0-4 全过 + 取证矩阵 10 类；**P1=0 / P2=0 / P3=1（已修）**；E4 3 观察（README `uv sync` 未提示 `--extra web` / `pyarrow` 经 streamlit 传递入锁 / U-P005-5 原估 `−46` 与实测 `−2` 偏差已注）+ 1 环境观察（PATH 解释器）；**15/15 ✅**
- **CI 回收**: B3 `0e0d594` 触发 run [`43167039277`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43167039277) 三 job **success**（3.10 1m54s / 3.11 1m11s / 3.12 1m30s）；回填提交 `4fd65ea` 触发 run [`43167328785`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43167328785) 三 job **success**（3.10 1m14s / 3.11 1m9s / 3.12 1m55s）
- **RULE-5 异构复审（2026-11-12，全批）**: **pass（0 P1 / 0 P2 / 4 P3 登记 + 2 观察）**——[CHECKLIST_p021 §11](CHECKLIST_p021_dependency_lock_maintenance.md)：复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；E1 十一项重放全复现（CI 双 run / numstat 四笔 / `--check` 0 / export 325 行 / tomllib 对拍 120→148 + changed 0 + added 19 / **636 passed** 43.40s 复审自跑 / black 111 / mypy 0 / 保护面空）；E2 红绿对照闭合（旧锁字节级落临时目录 exit 1 → 同目录 relatch 后 exit 0）；E3 锚点全命中 + 四文档链接 0 broken / ID 闭环；**F-R5-P021-1（RESEARCH 头部 §7 编号）/ -2（§3.1 沿用锚点计数 3→2）/ -3（纪律条数口径 2↔3 子句）/ -4（回填 run 43167328785 未登记）均 P3 已回写**；E4 2 观察；复审记录提交 `89c4f68` run `43169697196` 三 job success
- **本批收口**: U-P005-4 / U-P005-5 关闭；新增 U-P021-1（CI 锁门禁）/ U-P021-2（numba 声明）/ U-P021-3（升级节奏）三项条件触发未决项

---

### 3.26 P-022（Factor_DB 四项实现缺陷）执行记录（2026-11-12，done · T1）

- **立项**: U-P005-2（P-005 P7 静态读码四项）；档位 **T1**（`factor_library/` 行为变更 + 4 组红绿测试）；规范源 SPEC_PROCESS **v1.7.2**；证据时点 HEAD `cc3214c`
- **Step 1 严重度重估**: 运行探针全部复现四项，且缺陷③（str-datetime）实为**写后重开崩溃**——重开后 `add_factor` / `update_stats` / 双因子 `delete_factor` 均 `AttributeError`；缺陷①静默覆盖、②删除复活（`get_factor` 从残留 csv 复活）为 P2；④双份存储 P3
- **Step 1-8**: 四文档落稿（RESEARCH P1-P10 + E1-E4 锚点 / DESIGN D1-D6 + I1-I6 / IMPL T-1~T-5 + V1-V6 / CHECKLIST 18 项零预填）；Step 2 Review（1 项严重度重估 + E4 未采用）/ Step 4 / Step 6 均通过；Step 8 一致性 **0 发现**（20 处 `[待 Step 9]` = 18 格 + 2 合法）
- **Step 9 实施**: B1 `9c50bcd`（加载期 datetime 解析）/ B2 `ec21dc5`（覆盖守卫 = metadata ∪ 内存 ∪ 两种文件）/ B3 `9ffbfde`（删除 parquet+csv）/ B4 `1550e63`（写入后单一格式）/ B4b `59e1273`（black）；逐批红 **4/2/2/2 failed** → 绿 **11 passed**；全量 **647 passed**（636+11，44.46s）/ black **112 files unchanged** / mypy 36 files 0；7 个公开方法与 `FactorMetadata` 字段 AST **完全相等**；`batch_backtest`/`pyproject` 零改动；**CI 首跑 `43175692308` failure**（D-1/D-2 依赖真实 parquet，CI 无引擎）→ B5b 固定分支修复（D-1 哨兵 parquet / D-2 预置哨兵 + `ImportError`）
- **Step 10 ADD 审计**: [CHECKLIST_p022 §9](CHECKLIST_p022_factor_db_defects.md)——Phase 0-4 全过 + 取证矩阵 9 类；**P1=0 / P2=0 / P3=1（F-S9-P022-1 已记录）**；E4 1 观察升级 **U-P022-4**（overwrite 重置 created_at）+ 3 观察；**18/18 ✅**
- **CI 回收**: 首跑 run `43175692308` **failure**（D-1/D-2 依赖真实 parquet，CI 无引擎 × 三版本）；B5b `e03c650` 固定分支后 run [`43176076114`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43176076114) 三 job **success**（3.10 1m52s / 3.11 1m32s / 3.12 1m36s）；回填提交 `a29b498` 触发 run [`43176435214`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43176435214) 三 job **success** 2m20s（F-R5-P022-1 补登）；复审回填提交 `c2a1918` 触发 run `43181033219` 三 job **success** 2m0s（P-023 收口时补登）
- **RULE-5 异构复审**: **pass**（复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash）——E1 机械重放 8/8（CI 三 run / 8 笔 numstat / `647 passed` / black 112 / mypy 36 files 0 / AST 签名全等 / 四缺陷独立探针 6/6 / 保护面空）+ E2 合成红态重放（`cc3214c` 旧码 + 新测试 → **10 failed 1 passed**，与逐批红态 4/2/2/2 同构；恢复 HEAD 后 11 passed）+ E3 锚点 10 处全命中 + 四文档 14 链接 0 broken + ID 闭环 + E4 盲区扫描；**F-R5-P022-1（P3）回写补登 run `43176435214`** + 4 观察；详见 [CHECKLIST_p022 §11](CHECKLIST_p022_factor_db_defects.md)；复审记录提交 `326ba3c`，CI run [`43180639633`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43180639633) 三 job success（3.12 2m2s / 3.10 1m28s / 3.11 1m42s）
- **本批收口**: U-P005-2 关闭；新增 U-P022-1（原子写）/ U-P022-2（返回副本）/ U-P022-3（非 ImportError 清理）/ U-P022-4（保留 created_at）四项条件触发未决项

---

### 3.27 P-023（质量护栏：F-A1 静默空回测 + U-006-R mypy 盲区）执行记录（2026-11-12，done · T1）

- **立项**: U-006-R（盲区 4 errors 2 files）+ F-A1（静默空回测）；档位 **T1**（`core/` 行为变更，判档规则 2 强制升级）；规范源 SPEC_PROCESS **v1.7.2**；证据时点 HEAD `c2a1918`
- **Step 1 调研**: F-A1 由「已知限制」**上调 P1**——三条静默路径读码（setup 豁免 L187-195 / `_precompute_factors` warning+return L286-288 / 逐日 catch-all L328-330 吞 `assert signal_df is not None` L361）+ 第四处 `_generate_results` 不查空快照（L1135）；探针 A/C（注入任一组件 + 空 factor_files）**setup OK → run OK → snapshots=0 / trades=0 / 4 条空消息 ERROR**；探针 E（setup 后直接 `_generate_results`）不抛；对照 D 正常（snapshots=5 / trades=8）
- **Step 1 来源订正**: PROGRESS 原记「P-012 CHECKLIST §11」失准——P-012 的 `F-A1` 是同名另一发现（`limit_check_price`），权威源为 **P-007 CHECKLIST §9.3 L210**（编号撞车）
- **Step 1-8**: 四文档落稿（RESEARCH P1-P13 + E1-E4 锚点 / DESIGN D1-D6 + I1-I6 / IMPL T-1~T-5 + V1-V7 / CHECKLIST 25 项零预填）；Step 2 Review（1 P3：P2 初稿「0 命中」改为「编号撞车」）/ Step 4（2 P3）/ Step 6（1 P3）/ Step 8（2 P3：24→25 计数、RESEARCH 补下游链）全部通过
- **Step 9 实施**: 提交 `a5b95bb`（3 文件 **+222/−5**）——B1 `run()` 信号未就绪 `RuntimeError` / B2 `_generate_results()` 零快照 `RuntimeError` / B3 四项窄化（`data_v3._build_maps` 别名+assert、`engine_v2` L224 `cast(DataManager, ...)`、L293 别名+assert）
- **F5 红绿**: B1 红 `1 failed 1 passed`（`DID NOT RAISE` + 4 条空 ERROR）→ 绿 2 passed；B2 红 `1 failed 3 passed`（`DID NOT RAISE`）→ 绿 4 passed；B3 红 **`Found 4 errors in 2 files`** → 绿 `Success: no issues found in 36 source files`
- **V1-V7 实读**: **651 passed**（647+4，39.91s）/ black **113 files unchanged** / mypy 门禁 **36 files 0** / 盲区 **0** / 注入式 **27 passed** / 保护面 diff **空**
- **探针复跑**: A/C 由「静默 OK」→ `RuntimeError(信号未就绪)`；E 由「OK」→ `RuntimeError(快照)`；D 不变
- **CI 回收**: 提交 `a5b95bb`（代码）+ `74f08ff`（文档）合并推送 → run [`43187514724`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43187514724) 三 job **success**（3.11 1m25s / 3.12 2m0s / 3.10 1m15s）；回填提交 `ab61d2b` → run `43187917684` 三 job **success**（3.10 1m24s / 3.12 1m11s / 3.11 1m59s，登记收敛：终态登记提交自身 run 不计入验收证据）
- **RULE-5 异构复审**: **pass**（复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash）——E1 机械重放 8/8（CI 三 run / 4 笔 numstat / `651 passed` / black 113 / mypy 双口径 36 files 0 / 注入式 27 passed / 探针 A/C/E 转抛 RuntimeError / 保护面空）+ E2 合成红态重放（`c2a1918` 旧码 + 新测试 → **2 failed 2 passed**，双守卫缺失复现；恢复 HEAD 后 4 passed）+ E3 锚点行号全命中 + 四文档 21 链接 0 broken + ID 闭环 + 25/25 ✅ + E4 盲区扫描；**0 P1 / 0 P2 / 0 P3 + 4 观察**（含 `43188290186` 已声明合法态）；详见 [CHECKLIST_p023 §11](CHECKLIST_p023_quality_guardrails.md)；复审记录提交 `a903e25`，CI run [`43190333737`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43190333737) 三 job success（3.12 1m59s / 3.11 1m26s / 3.10 1m49s）
- **本批收口**: **U-006-R 关闭**（盲区 4 → 0）；**F-A1 关闭**（双守卫 + 来源订正）；新增 U-P023-1（catch-all retry 语义）/ U-P023-2（`--check-untyped-defs` 是否入门禁）/ U-P023-3（零交易日语义）/ U-P023-4（v3 引擎信号路径未取证）四项条件触发未决项

---

### 3.28 P-024（CI 门禁对齐：mypy 假门禁 + README uv extras）执行记录（2026-11-12，done · T1）

- **立项**: U-006（`mypy-check` 口径收紧待重评，Q4=B）+ U-P023-2（`--check-untyped-defs` 是否入门禁）+ U-P023-4（v3 信号路径取证）；档位 **T1**（Layer-1 `.github/workflows/` + 门禁口径，判档规则 1 + 2）；规范源 SPEC_PROCESS **v1.7.2**；证据时点 HEAD `6ed74d0`
- **Step 1 调研**: ① `tests.yml` L46 `mypy core/ --ignore-missing-imports --no-error-summary || true`，`|| true` 自初版 `c7a0f29`（2026-06-07）即存在 → **恒吞退出码（假门禁，P1）**；② **双口径不可互换**——CI 那串参数在本地 **exit 2**（`Factor_Trading_v3.0 ... is not a valid Python package name`），本地参数 0 errors/36 files（P2）；③ README `uv sync` 缺 extras，与 [ARCHITECTURE L332](ARCHITECTURE.md) 纪律冲突（P3）；④ §1.4 缺 U-P023-1~4 行（P3）；⑤ `--check-untyped-defs` 当前 **0 残差**（P-023 已清零）→ 纳入零成本；⑥ `[tool.mypy]` 已全局 `ignore_missing_imports=true`（pyproject L110）→ CI 该旗标冗余
- **Step 1-8**: 四文档落稿（RESEARCH P1-P13 + E1-E5 锚点 / DESIGN D1-D7 + I1-I7 / IMPL T-0~T-8 + V1-V9 / CHECKLIST **28 项**零预填）；Step 2 Review（1 P3：P7 矩阵来源误记为 pyproject）/ Step 4（2 P3：守卫命令规范化）/ Step 6（2 P3）/ Step 8（3 P3：未创建文件 3 broken 链接 → 代码字面量、I7 悬空 → 补定义、P7 来源订正复核）全部通过
- **Step 9 实施**: B1 `e360436`（3 文件 **+77/−2**：`tests.yml` L46 / adapter L67 / 新增守卫测试 3 断言）/ B2 `ac2a3d6`（README L220）/ B3 `c1c67b2`（台账 + 四文档）/ B4 `pyproject.toml` 追加 `[[tool.mypy.overrides]] module = ["filter.*"] ignore_errors = true`（+8 行，诊断见下）
- **F5 红绿**: V1 先红 **exit 1**（`core/_p024_probe.py` 注入 `x: int = "s"` → `Incompatible types in assignment`，checked 37 files）→ V2 同命令 + `|| true` **exit 0**（对照：无 `|| true` 时 `V2_RAW_EXIT=1`）→ V3 删探针后 **exit 0**（36 files）
- **CI 首跑红与根因更正（F-S9-P024-4/5，P2×2）**: run [`43193963200`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43193963200) 3.10 leg failure（3.11/3.12 canceled）——**21 errors / 7 files 全在 `filter/*`**，`core/` 0 条。首轮误判为「mypy 2.4.1 vs 2.1.0 版本漂移」并提交 `745e2b7` 钉 `~=2.1.0`；复核发现该读数来自 `uv run --no-project` **缺 pydantic/pandas** 的污染环境（`ignore_missing_imports` → pydantic 成 `Any` → `config_v2.py` 3 条伪影）。X1-X4 隔离实验定因：**pandas 3.1.1 类型桩**（`pandas>=2.0.0` 无上限；CI 3.1.1 vs 本地 2.2.3）。处置：撤回钉版（恢复 `mypy>=1.5.0`、`uv.lock` 复原），改以 `filter.* ignore_errors` 越界声明收口（X2/X3 跨 mypy 版本均 0 errors）；`filter/` 21 条登记 U-P024-4
- **V4-V8 实读**: **654 passed**（651+3，52.13s）/ black **180 files would be left unchanged** / mypy 门禁与盲区均 **36 files 0** / `uv lock --check` **exit 0**（148 packages）/ `mypy.*|| true` grep **0** / `git status` 无探针残留
- **CI 回收**: 首跑 `43193963200` failure（`filter/*` 21 errors）→ 修复 `f8cb9ba`（`filter.*` 越界声明 + 撤回钉版）→ run [`43196177149`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43196177149) 三 job **success**（3.10 1m58s / 3.11 1m27s / 3.12 1m47s）；回填提交自身 run 不计入验收证据
- **本批收口**: **U-006 / U-P023-2 / U-P023-4 关闭**（判据达成）；新增 U-P024-2（CI `uv lock --check`）/ U-P024-3（检查面扩展）/ U-P024-4（`filter/` 在 pandas 3.x 下 21 errors）三项条件触发未决项；U-P024-1 维持 pending（误诊已撤回）；四文档 [RESEARCH](RESEARCH_p024_ci_gate_alignment.md) / [DESIGN](DESIGN_p024_ci_gate_alignment.md) / [IMPL](IMPL_p024_ci_gate_alignment.md) / [CHECKLIST](CHECKLIST_p024_ci_gate_alignment.md)

### 3.29 远端 legacy `main` 分支收口 + CI 分支过滤清理（2026-11-12，done · 无批次编号）

- **背景**: 远端 `main`（`dba4be8`，2026-05-13，5 提交 / 235 文件 / 48,457 行，全为 `Add files via upload`）与 `master` **无共同祖先**（`git merge-base` 为空、`--is-ancestor` = False），却长期是 **GitHub 默认分支** → 访客与 clone 默认落到 5 月快照；README L8 CI 徽章未带 `?branch=`，状态取自 `main` 而非现网门禁
- **前置核查**: `main` 无保护规则（`Branch not protected`，404）/ 以 `main` 为基的 PR = 0 / 无 tag / README 与 `tests/`+`scripts/` 无分支名引用；仅 `main` 独有的 125 文件中非 `.pyc` 部分为被重构取代的旧扁平布局 + `demo_data/` + `output/` 产物 + 2 张零引用的 `Instruction.PNG`/`UI.PNG` → 无独有工程价值
- **处置（顺序不可换）**: ① 存档 tag `archive/legacy-main-2026-05-13` → `dba4be8`（已推送）；② 默认分支 `main` → `master`（`gh api -X PATCH -f default_branch=master`）；③ `git push origin --delete main`（`- [deleted] main`）→ `git remote set-head origin -a` 得 `origin/HEAD -> origin/master`
- **代码变更**: `0482df7` — `tests.yml` L5/L7 `branches: [main, master, develop]` / `[main, master]` 收敛为 `[master]`（1 文件 **+2/−2**），7 步骤（含 mypy 门禁）零改动
- **验证**: YAML 解析合法（`push: ['master']` / `pr: ['master']` / steps 7）；守卫测试 `test_p024_ci_gate_alignment.py` + `test_spec_runner_adapter.py` **9 passed**；CI run [`43206371865`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43206371865) 三 job **success**（默认分支切换后首跑）
- **终态**: 远端仅 `refs/heads/master`（`0482df7`）+ tag `archive/legacy-main-2026-05-13`；默认分支 `master`；工作区干净

### 3.30 P-025（日循环异常分类与 retry 语义）执行记录（2026-11-13，Step 1-10 完成 + RULE-5 pass · T1）

- **立项**: U-P023-1 升格；档位 **T1**（`core/` 行为契约 + 结果字典新增键）；规范源 SPEC_PROCESS **v1.7.2**；证据时点 HEAD `43cfa36`
- **Step 1-2**: 七探针 A/A2/A3/B/B2/C/D（三层静默：日循环 20 快照仅 19 去重日 / 优化 `except→return` / 执行 `except→(False,None)`）；方案矩阵 5 案选 **M-A**；锚点 PEP 654 / AWS Builders retries / SRE golden signals；异构 Review pass（2 P3 回写）
- **Step 3-4**: D1-D7 / I1-I7 / V1-V12 / T1-T10；设计期新发现 **F-D3-P025-1（P2）**——`build_optimizer` 用 `mvo` 而 CLI 提供 `mean_variance` → 静默降级等权（探针实测读数与 `equal_weight` 完全相同）；异构 Review pass（7 P3 回写，含 raise 语义裁决「首错即抛」）
- **Step 5-6**: T-1~T-6 / 12 项接口签名与回退点 / 9 项低效排除 / fixture 7 项；Review pass（**1 P2**：sink 注解 mypy 不兼容 + hasattr 直调 Protocol → `object` 化 + `getattr` 探测；3 P3 回写）
- **Step 7-8**: CHECKLIST **42 项**零预填；一致性 Review pass（ID 闭环 17 组 / 计数 42 / 2 P3 回写 IMPL 的 black 数字）
- **Step 9 五批红绿**: B1 `ModuleNotFoundError: core.diagnostics` → 4 函数绿 / B2 `2×KeyError: run_diagnostics` + `DID NOT RAISE <ExceptionGroup>` → 绿 / B3a `degraded False` → 绿 / B3b `mean_variance → EqualWeightOptimizer`（F-D3-P025-1 复现）→ 绿 / B3c `DID NOT RAISE <RuntimeError>` → 绿
- **代码变更**: `core/diagnostics.py` **新增**（`classify_day_error` + `DayErrorRecord` + `DayErrorCollector`，`_category_counts` 对 50 条截断免疫）/ `config.py` +1 行 `day_error_mode` / `engine_v2.py` 4 处（`__init__` 采集器 / `run()` catch / 优化 catch / `setup()` sink 绑定 + D7-O2 预检 + `run_diagnostics` 入结果）/ `execution.py` 3 处（`_error_sink` / `set_error_sink` / except 调 sink）/ `portfolio.py` D6（`mean_variance` 别名 + fail-closed）
- **门禁终态**: **671 passed**（654 + 17 实例 / 10 函数，42.24s）/ mypy **37 files 0** / black **116 + 182** unchanged / golden **13 passed 零重录** / `test_decoupled_engine` **12 passed**（fake executor 不被 sink 绑定破坏）
- **探针复跑**: A2 **20 快照 / 19 去重日 / `counts.day_loop=1`**（与 HEAD 逐字一致）；B2 **`setup()` 抛「必然失败」**（原假成功 0 成交/sharpe 0.0）；C **`counts.execution=6`**、恢复后成交 4 笔；A3 **21 快照 / 20 去重日**（I7 未顺带修复）；AST `execute_order` / `__init__` 签名一致；零改动面 8 路径 diff 空；I1 report/off 双跑键差均 `{run_diagnostics}`
- **提交与 CI**: `22b833e`（代码 6 文件 +547/−2）→ `69a6d22`（文档 5 文件 +140/−46）→ run [`43260476319`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43260476319) 三 job **success**（3.10 / 3.11 / 3.12）；回填提交自身的 run 不计入验收证据（P-023/P-024 先例）
- **Step 10 ADD**: Phase 0-4 全过；取证矩阵 7 类；盲区扫描 3 P3（2 修 + 1 登记）+ 3 观察；审计后重跑 `671 passed` / 37 files 0 / 116 unchanged
- **RULE-5 异构复审 pass**（复审基座 **GLM-5.3-Flash** ≠ 各文档/实施/审计作者基座 **DeepSeek-V4.1-Flash**，异构成立）：E1 机械重放 **9/9**（numstat 4 笔 / CI 3 run / pytest 671 / mypy 37 files 0 / black 116+182 / 新增 17 / decoupled 12 / 保护面 diff 空 / golden 零重录）；E2 红态重放（checkout `43cfa36` 四 core 文件 → **6 红**：`day_error_mode` TypeError ×3 + `KeyError: run_diagnostics` + EqualWeight 静默降级 + 预检 DID NOT RAISE → 恢复 → 17 绿、工作区干净）；E3 锚点全命中 + 验收区段 42/42 ✅ + 链接 0 broken；E4 盲区扫描 **2 P3 均已回写修复**（**F-R5-P025-1** §12.4 RULE-5 状态声明「作者同为 GLM」与作者归属铁证不符已订正——若采信原声明本复审会话将不满足异质性而失效，属异构复审核心命中；**F-R5-P025-2** README 计数漂移 4 处 654→671、74→78 files〔F-R5-P024-1 同类复发〕）+ 3 观察（sink 自定义注入逃逸面 / record_failure 无调用点 / run 二次累积，均维持既有裁决）；0 P1 / 0 P2；复审落稿提交 `1413e1b` → CI run [`43268888853`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43268888853) 三 job success；详见 [CHECKLIST_p025 §13](CHECKLIST_p025_daily_loop_exception_semantics.md)
- **本批收口**: **U-P023-1 关闭**（由 P-025 完成）；**U-P025-5 关闭**（3.11+/3.10 分支已实现且 CI 3.10 job 覆盖）；U-P025-4 裁决不做；U-P025-1/2/3/6 维持 pending；四文档 [RESEARCH](RESEARCH_p025_daily_loop_exception_semantics.md) / [DESIGN](DESIGN_p025_daily_loop_exception_semantics.md) / [IMPL](IMPL_p025_daily_loop_exception_semantics.md) / [CHECKLIST](CHECKLIST_p025_daily_loop_exception_semantics.md)

### 3.31 P-026（静默失败治理第二批 · U-P025-3）执行记录（2026-11-13，Step 1-10 + RULE-5 终审完成 · T1）

- **立项**: U-P025-3 承接（触发条件「其中任一处产生可复现的静默错误」经 Step 1 读码**实证成立**）；档位 **T1**（`core/` 行为契约 + 结果/返回值新增可观测字段）；代码证据时点 HEAD `7ff7a4d`
- **Step 1 候选池实测（E1）**: 全仓 `except Exception` **49 处**——`core/` 27 / `agents/` 11 / `filter/` 5 / `scripts/` 2 / `batch_backtest/` 2 / `strategy_evaluation/` 1 / `cli.py` 1；core 27 = 已埋点 3（engine_v2 ×2 + execution ×1）+ 采集器兜底 2（diagnostics）+ **待评估 22**
- **Step 1 逐点裁决（22 处全覆盖）**: **K 保持 8**（`data.py` ×3 记录后重抛 / `event_log` listener 隔离 ×2 + 恢复 warning + 快捷函数 / `walk_forward` 回调隔离）/ **D 升级诊断 10** / **F fail-fast 0** / **排除 4**（`config_v2` ×3 冻结且形态正确 / `execution` L251 P-025 已裁正确降级）
- **Step 1 三处 P2 实证（读码）**: ① `factor.py` L344 `except Exception: continue` **零日志**（去常数列失败 → 该日中性化整体跳过 → 信号缺失）；② `engine_plugins.py` L235 Guard 异常 **fail-open**（`return True, []`，异常不计入既有 `_blocked_count`/`_warning_count`）；③ `walk_forward_engine.py` L185 `set_period` 失败仅 warning（窗口以**错误期间模式**运行且无字段标记）
- **Step 1 辅助发现**: `engine_plugins.py` L161 为 **`debug` 级**（A3 铁证 root logger 默认 WARNING → 默认不可见）；`event_log` L160 读取失败返回空列表（**「无事件」与「读失败」不可区分**）；`global_contagion` L433/L447 **零日志**兜底、L589 假阴性不可区分；静默路径测试覆盖近零（9 关键词中 7 项 0 命中）
- **方案矩阵**: 5 案（M-A 逐点三态分级显形 / M-B 仅提日志级别 / M-C 全局注册表 / M-D 全量 fail-fast / M-E 维持）选 **M-A**——延续 P-025「显式静默 vs 未声明静默」判据（PEP 20 后句）、复用 sink 注入先例（P-025 D5）、**零全局状态**、本批 0 项 fail-fast
- **外部锚点（4 项全 T1 命中，2026-11-13 直读）**: PEP 20「Errors should never pass silently. Unless explicitly silenced.」/ CWE-390「detects a specific error, but takes no actions」/ Python logging 文档「root logger is created with level WARNING」/ AWS Builders' Library「almost always prefer alternatives to fallback」
- **未决项**: U-P026-1（EventLog 写盘失败是否 fail-fast，倾向只计量）/ U-P026-2（contagion `degraded` 字段粒度）/ U-P026-3（core 外 22 处后续分批）/ U-P026-4（listener 限流，不做）/ U-P026-5（是否建全局采集器，本批不建）/ **U-P026-6**（`read()` 窄类型跳坏行计量，已由本批顺带收口）——**六项已补登 §1.4**
- **批次切分**: B1 factor / B2 plugins / B3 contagion / B4 event_log + walk_forward / B5 文档与回归
- **Step 2 独立 Review（异构基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash）**: **pass**——E1 机械复核（生产代码 `except Exception` 49 处逐文件复现 @`7c48d50` + 31 代码锚点零漂移 + 链接/算术全过）；E2 门禁四项（pytest **671 passed** / mypy 37 files 0 / black core 37 + tests 78 unchanged）；E3 幻觉排除（A1-A4 逐条复验全命中 + P12 复现）。发现 **F-S2-P026-1（P2：§5 #6/#7 引用不存在的 `EventLog.stats()`，已订正为「新增 stats() 方法」）** / F-S2-P026-2（P3：M-A 实施面为 **6 文件**，含 walk_forward.py 的 `WalkForwardResult` 字段）/ F-S2-P026-3（P3：「全仓 49」订正为「生产代码 49」，tests 21 / tools 3 / examples 1 另有 25 处）+ 3 观察（§1「18 处吞掉」口径订正 / P12「中性化失败」命中为测试自身打印，有效路径覆盖更接近 1/9 / `read()` 内层窄类型跳坏行 → **U-P026-6**）；均已回写 [RESEARCH_p026 §10](RESEARCH_p026_silent_exception_governance.md)
- **Step 3 DESIGN（T1）**: **完稿**（[DESIGN_p026](DESIGN_p026_silent_exception_governance.md)，D1-D8 决策 + 12 测试规格 + 7 不变式 + 6 验证契约）——D1 factor sink 与双原因计数 / D2 插件层计量（Guard **保持 fail-open**）/ D3 `ContagionNetwork.degraded_components` + Granger `failed` / D4 `EventLog.stats()` 三计数器（采纳 U-P026-6 的 `skipped_lines`）/ D5 `WalkForwardResult.agent_period_failures` / D6 K 类 8 + 排除 4 零改动 / D7 计数生命周期 / D8 文案约定。**变更面订正为 8 core + 1 test**（RESEARCH「6 文件」漏计 sink 接线与阶段词表）
- **Step 3 设计期发现**: **F-D-P026-2（P2）** sink 注入**时点**是正确性条件——`self.pipeline` 在 `engine_v2.py` L228 创建、`_precompute_factors()` 在 L237 立即调用，若按 P-025 惯例放到 setup 末尾则 setup 期因子异常**全部漏采**，B1 交付判据永不成立 → 硬性规定插于 L235-L237 之间；F-D-P026-1（P3）成本行 6→8 文件；F-D-P026-3（观察）`STAGES` 无运行时使用；F-D-P026-4（观察）Granger 样本不足早退路径本就缺 `strength` 键，本批不补
- **Step 4 独立 Review（异构基座 GLM-5.3-Flash ≠ DESIGN 作者 DeepSeek-V4.1-Flash）**: **pass**（[DESIGN_p026 §11](DESIGN_p026_silent_exception_governance.md)）——E1 机械复核（32 处锚点零漂移 + 算术全过 + D2.1「新增」/D2.2「追加」措辞核查均正确）；E2 门禁（pytest **671 passed, 172 warnings** 83.89s / mypy 37 files 0 / black 115 = 37+78 unchanged）；E3 幻觉排除（STAGES 无运行时使用全仓 grep 实证 / EventLog 无 stats / Granger 早退无 strength / executor sink 惯例 L287-288 / K 类锚点 L278/L286/L313/L214 实证）。发现 **0 P1 / 0 P2 / 4 P3 + 2 观察，P3 均已回写订正正文**：F-S4-P026-1（`_report_error` 的 `reason` 死参数 → 签名修订 `(date, exc)`）/ **F-S4-P026-3（D4.3「不加锁」论证引用错误锁类型——`self._lock` 实为 `threading.RLock()` L61 可重入，「自死锁」前提不成立；结论维持、论证重写）** / F-S4-P026-2（raise 模式语义扩散未声明：factor data/internal ∈ RAISE_CATEGORIES → 首交易日 `raise_if_needed` engine_v2 L364 抛出，D1.3 补声明）/ F-S4-P026-4（T9 MST patch 目标须为 `core.global_contagion.minimum_spanning_tree`，L28 from-import 绑定）；观察 ×2：`_recover_state` 外层 except L313-314 不计入 stats（本批不补）/ `_stats` 初始化须早于 L75 `_recover_state()`（D4.1 补时点约束）。既有 `test_engine_plugins.py` 的 get_stats 断言为键访问式（L141/L223），D2.2 追加 `error_count` 键零破坏
- **Step 5 IMPL（T1）**: **完稿**（[IMPL_p026](IMPL_p026_silent_exception_governance.md)）——B1 factor 链路（`set_error_sink` / `neutralize_skip_counts` / `_report_error` 按 F-S4-P026-1 去死参数；`STAGES` +`"factor"`；`engine_v2` L237-242 sink 注入**早于** `_precompute_factors()`）/ B2 插件层（`EventLogPlugin._log` debug→warning + `get_stats`；Guard 计数 + 文案，**fail-open 不变**）/ B3 传染（`degraded_components` + Granger 三路径 `failed`）/ B4 `EventLog.stats()` 三计数器（初始化早于 `_recover_state`，不加锁）+ `WalkForwardResult.agent_period_failures`（run 重置）/ B4t 新测试 12 函数 16 实例 / B5 门禁 + 文档
- **Step 5 门禁实测（E1）**: **687 passed, 173 warnings in 71.42s**（671 + 16）/ mypy **37 files 0** / black **116 unchanged**（115 + 新测试文件 1）/ 受影响面快速回归 26 passed（改动前后同绿）/ golden G1-G7 随全量通过且 `tests/golden/*.json` 零改动；变更面 `git diff --numstat` **8 文件 +100/−10**（DESIGN 估 +97/−13）
- **Step 5 实施期发现**: F-I-P026-1（P3）DESIGN V1 未计 T1 参数化——实际 16 items 故全量为 **687** 而非 683（测试函数数仍 12,与 §4.2 一致）/ F-I-P026-2（观察）`WalkForwardEngine` docstring 参数名 `base_engine` 与实现 `base_engine_class` 不一致 / F-I-P026-3（P3）新测试 422 行 vs 估 240（独立复制引擎夹具）/ F-I-P026-4（P3）代码行数 +100/−10 vs 估 +97/−13 / **F-I-P026-5（观察）**`_set_agent_period` 的 `hasattr(agent,"distillation_config")` 为 True 但值为 `None` 时抛 `AttributeError`（L194 无 None 守卫，相邻静默失败面，本批不改）/ F-I-P026-6（观察）T10 触发 statsmodels `FutureWarning`（172→173 warnings）
- **Step 6 IMPL 独立 Review（异构基座 GLM-5.3-Flash ≠ IMPL 作者 DeepSeek-V4.1-Flash）**: **pass**（[IMPL_p026 §10](IMPL_p026_silent_exception_governance.md)）——E1 机械复核（numstat 15 files +744/−19、8 core **+100/−10** 与 §6 一致 + §4.1-4.8 行数逐一吻合 + 五文件 diff 全量重放逐行一致 + 门禁三重放 pytest **687 passed, 173 warnings in 77.94s** / mypy 37 files 0 / black 116）；E2 红态重放（checkout 8 core 文件 @`bbb55bc` → 新测试 **14 failed, 2 passed**，失败均为接口不存在/计数缺失类；2 passed 属红态预期不红——T1[exc4] 旧通用兜底同结果 + T6 旧引擎无注入调用；恢复后工作区干净）；E3 幻觉排除（T1-T12 断言逐条对码一致 + F-I-P026-2/F-I-P026-5 均核实为真实代码事实）；E4 盲区扫描（8 文件 except 全扫，本批治理点全部带计量+日志）。发现 **0 P1 / 0 P2 / 1 P3 已订正 / 3 观察**：**F-S6-P026-1（P3）IMPL §2 B1 产出「+42/−4」删除行算术错误（实测 −2，作者重复计入修改行），已订正原文**；O-S6-P026-1（`walk_forward_engine` L218 回调失败仅 warning 无计量）/ O-S6-P026-2（`event_log` L292/L300/L328 listener 与 recovery 外层无计量）/ O-S6-P026-3（`diagnostics` L129/L160 属 P-025 设计语义）——三项均登记待「静默失败治理」第三批裁决
- **Step 7 CHECKLIST（T1）**: **完稿**（[CHECKLIST_p026](CHECKLIST_p026_silent_exception_governance.md)）——**45 项零预填**（A 9 / B 4 / C 4 / D 5 / E 9 / F 8 / G 6，逐行机械计数，RULE-2），实测列全为 `[待 Step 9]`（RULE-1 时序独立）；A 组 factor 链路 T1-T6 + raise 语义 9 项 / B 组插件层 fail-open 4 项 / C 组传染 degraded+Granger 4 项 / D 组 EventLog+WF 5 项 / E 组不变式 I1-I7 与保护面 9 项 / F 组门禁 8 项（含 687 与 173 warnings）/ G 组治理台账 6 项；Step 7 实测基线：新测试 **16 tests collected**、全量 **687 passed**
- **Step 7 交接事项（7 条）**: ① DESIGN V1 683→687 口径订正（F-I-P026-1）；② DESIGN §4.1 估行 +337/−13 vs 实测 +100/−10 代码 + 422 测试行（F-I-P026-3/4）；③ IMPL §2 B1 删除行已在 Step 6 订正（−4→−2）；④ 测试规格统一「12 函数 / 16 实例」；⑤ V5 红线映射 B1→A7 / B2→B2+B3 / B3→C1+C2 / B4→D2+D5；⑥ 未覆盖声明（O-S6-P026-1/2 + F-I-P026-5 不在本批范围）；⑦ **审查基座约束——CHECKLIST 作者 DeepSeek-V4.1-Flash 与 DESIGN/IMPL 同源，Step 8 / Step 10 须换异构基座满足 RULE-5**
- **Step 8 一致性 Review（异构基座 GLM-5.3-Flash ≠ 四文档作者 DeepSeek-V4.1-Flash）**: **pass**（[CHECKLIST_p026 §11](CHECKLIST_p026_silent_exception_governance.md)）——链接完整性 **0 broken**（脚本重放）/ 计数口径一致（687/671/16/12/173/+100−10/37/116；671+172 为 Step 2/4 时点读数；+337/−13 为估算值已声明偏差）/ 编号连续无断号（D/I/V/T/F-*/U-*/O-* 全系列）/ 45 项复核精确（A9/B4/C4/D5/E9/F8/G6 + 零预填）/ 三对对齐全过（RESEARCH↔DESIGN 三处 P2→D1/D2/D5 覆盖、DESIGN↔IMPL D1-D8→B1-B4 映射 + Step 6 diff 重放背书、IMPL↔CHECKLIST T1-T12→A/B/C/D 组全覆盖）/ 提交链 7 笔与 git log 一致。发现 **0 P1 / 0 P2 / 2 P3 已修复 / 1 观察**：**F-S8-P026-1（P3）DESIGN V1 判据「12 项后 = 683」未按 F-I-P026-1 落地订正（Step 7 仅列交接事项）→ 已订正为 ≥687（16 items = 12 函数）**；**F-S8-P026-2（P3）DESIGN §4.2 标题「12 项」口径 → 已订正为「12 函数 / 16 实例」**；O-S8-P026-1（DESIGN §11 历史 683 算术复核保留不改）
- **Step 9 TDD 回填（作者基座 DeepSeek-V4.1-Flash，非复审步）**: **完成**（[CHECKLIST_p026 §12](CHECKLIST_p026_silent_exception_governance.md)）——45/45 实测列落证据（**44 ✅ / 1 ❌ G2 待 Step 10 收口**，`[待 Step 9]` 剩余 0）；红态重放 8 core 文件回退至 `76f7e6e` → 新测试 **14 failed, 2 passed**（T1[exc4] 与 T6 属预期不红），恢复后工作区干净 → 绿态 **16 passed**；门禁复测全量 **687 passed, 172 warnings** / mypy **37 files 0** / black **116 unchanged** / 受影响面 **26 passed** / 解耦引擎 **12 passed** / golden **9 passed 零重录**；读码锚点全量取证（STAGES 11 值 factor L31 / `raise_if_needed` 唯一调用点 engine_v2 L369 / EventLog `_stats` L74 早于 `_recover_state` L82 / Lock 仅 L61）。发现 **F-S9-P026-1（P2，已修复）**：CI Python 3.10/3.11 装 `statsmodels 0.15.0` 已移除 `verbose` 参数，T10 `grangercausalitytests(..., verbose=False)` 抛 `TypeError` 被 except 捕获 → `failed=True` → `assert True is False`（本地 0.14.6 仅告警，故本地绿 CI 红，Step 5 起 4 个 run 连续失败）；修复 = `core/global_contagion.py` 移除 `verbose=False` 实参（+1/−1）；副作用 **F-S9-P026-2（P3）**：warnings 173→**172**（FutureWarning 消失，零新增）；观察 O-S9-P026-1（E6 字段实测 6 处非 5）、O-S9-P026-2（G2 属 Step 10 收口）；提交 `8756f9a` 推送后 CI run `43386673276` **三 job 全 success**（3.10 / 3.11 / 3.12），F8 / G6 已回填
- **Step 10 ADD 审计（异构基座 GLM-5.3-Flash ≠ 四文档作者 DeepSeek-V4.1-Flash）**: **pass**（[CHECKLIST_p026 §13](CHECKLIST_p026_silent_exception_governance.md)）——Phase 0 设计文档质量门 **5/5 Tier A**（可测试约束 / 模块映射 / 接口契约 / 修正项 / 跨模块契约全过，无 B 档封顶）；Phase 2 五子代理并行审计五维度（B1 factor 链路 / B2 插件层 / B3 传染 / B4 EventLog+WF / 跨模块契约）证据全对齐；Phase 3.5 主审源码级复核：零改动面 `git diff --name-only 76f7e6e..HEAD` **16 文件全在声明面**（8 core + test_p026 + CHANGELOG/README/ARCHITECTURE + 四 P-026 文档）、新增 warning `exc_info` **0 命中**（D8）、D1.4 sink 注入早于 `_precompute_factors()`（engine_v2 L238-242）、D4.1 `_stats` L74 早于 `_recover_state` L82、F-S9-P026-1 补丁与设计意图一致；**0 P0 / 0 P1 / 0 P2 + 2 观察**（O-S10-P026-1 子代理未产出结构化 verdict → 按校准规则主审全量复核零幻觉 / O-S10-P026-2 D6 fail-open 与 D8 文案为持续约束项登记）；评分 `100 − 0` = **100 → A+**；**G2 收口**（§1.4 新增 P-026 done 行 + 本节 Step 1-10 记录；U-P025-3 置 done）
- **RULE-5 异构终审（异构基座 Qwen3.8-Max ≠ 四文档作者 DeepSeek-V4.1-Flash ≠ Step 4/6/8/10 审计 GLM-5.3-Flash）**: **pass**（[CHECKLIST_p026 §14](CHECKLIST_p026_silent_exception_governance.md)）——E1 机械重放全复现（提交链 11 笔 + numstat **+100/−10** + 零改动面 **16 文件** + CI 三 run success@`8756f9a`/`84054fc`/`f789e4b` + pytest **687 passed, 172 warnings** + mypy **37 files 0** + black **116 unchanged** + 新测试 **16 collected** + golden G1-G7 零重录）；E2 红态重放 **14 failed / 2 passed** → 恢复后 **16 passed** 且工作区干净；E3 锚点抽验全命中（STAGES factor L31 / sink 注入 L238-242 早于 `_precompute_factors` / `raise_if_needed` 唯一调用点 L369 / `_stats` L74 早于 `_recover_state` L82 / CHECKLIST **45/45 ✅** / 四文档链接 33 条 0 broken）；E4 盲区扫描（README 687×3 + 79 文件、ARCHITECTURE 687 无计数漂移；`exc_info` 仅 diagnostics 两处既有语义；8 文件 except 治理面全带日志+计量）。**0 P0-P3 + 1 观察**（O-R5-P026-1：engine_v2 L597/L1023 两处既有静默点不在本批裁决范围，登记为后续批次候选）
- **下一 Step**: **批次关闭**——Step 1-10 + RULE-5 异构终审全部通过（2026-11-13）；U-P025-3 已 done；静默失败治理残余面 **U-P026-1~6 已登记 §1.4**（U-P026-6 顺带收口，其余 5 项条件触发）+ O-S6-P026-1/2/3、F-I-P026-5、O-R5-P026-1 观察点待后续批次
- **台账补登（2026-11-15）**: **F-R5-P026-2**（P3，台账登记缺口）——U-P026-1~6 六项此前仅见 RESEARCH_p026 §7 与本段文字，未落入 §1.4 未完成事项表；本轮补登 6 行（U-P026-6 经 CHECKLIST D1/D3 复核判为已收口，其余 5 项维持 pending 条件触发）；U-P026-3 构成已于 HEAD `e6caafd` 复核（22 处逐模块吻合）

### 3.32 P-027（静默失败治理第三批 · core 外 22 处 · U-P026-3）执行记录（2026-11-15，Step 1 完成 · T1）

- **Step 1 取证（作者基座 DeepSeek-V4.1-Flash）**: **触发条件成立**——静态（无日志 / 无计量 / 无降级说明）+ 动态（注入异常后返回默认值且日志记录数 = 0）两要件同时满足；[RESEARCH_p027](RESEARCH_p027_silent_exception_governance_phase3.md) 已落盘（§0 摘要 / §1 触发判据 / §2 E1-E4 方法 / §3 22 处全量清单 / §4 分类统计 / §5 E2 复现 / §6 U-P024-4 结论 / §7 治理建议 / §8 风险 R-P027-1~3 / §9 下一 Step）
- **E1 全量定位（HEAD `10e0553`）**: core 外 `except Exception` 共 **22 处**，逐模块计数 `agents/` **11**（`agent_framework` 3 / `multi_strategy_engine` 3 / `guru_agent_v2` 2 / `auto_parameter_optimizer` 1 / `assumption_monitor` 1 / `research_team_v2` 1）+ `filter/` **5**（`custom.py` 4 + `universe_filter_clean.py` 1，真实行号 **L371**）+ `scripts/` **2**（`fetch_universe.py` L100/L118）+ `batch_backtest/` **2**（`engine.py` L107/L167）+ `strategy_evaluation/` **1**（`stats.py` L139）+ `cli.py` **1**（L136）；早前误计的 `filter/utils.py:40`、`filter/filters.py:151` 经 count 复核后剔除
- **分类统计（口径 A/B/C/E）**: **A 2**（`batch_backtest/engine.py` L107/L167：`logger.error` + `results[name] = {"error": ...}`，日志+结构化输出的参照范式）/ **B 14**（`agents/` 9 + `filter/` 5，有日志无计量；其中 `agent_framework.py:1074` 为 `debug` 级 `continue`，记为 B−）/ **C 2**（`agents/assumption_monitor.py:201` 静默 `return 0.0, 1.0`；`strategy_evaluation/stats.py:139` 静默 `return np.nan`）/ **E 4**（进程边界 `print` / `sys.exit`，排除：`agent_framework.py:1529`、`scripts/fetch_universe.py` ×2、`cli.py:136`）
- **E2 运行时复现（双要件之动态证据）**: 仓库外探针 `%TEMP%\p027_probe.py`（`logging.Handler` 计数 + `monkeypatch` `np.corrcoef` / `np.var` 抛 `RuntimeError`）——`FactorStatsCalculator.calculate_half_life` → `return "nan"` / `log_records = 0`；`ReturnDistributionMonitor._kpss_test` → `return [0.0, 1.0]` / `log_records = 0`。两处均**静默返回乐观默认值**，且 `stats.py:139` 与上游 3 处合法早退（L124/L131 样本不足、L136 rho 越界）返回同值，调用方无法区分
- **U-P024-4 合并判断撤回**: 实测 `pandas 2.2.3`（非 CI 侧 3.x）、`mypy --explicit-package-bases filter` = **Success: no issues found in 10 source files**（0 error），历史 21 errors / 7 files 不可复现 → **触发条件不成立，不并入本批**；U-P024-4 维持 pending，待 pandas 升级 3.x 时复核
- **风险登记（交 Step 3 DESIGN 裁决）**: R-P027-1 `filter/custom.py` 4 处 fail-open 属既有降级语义，治理须显式登记而非改语义；R-P027-2 新增计量字段统一 `*_failures` 后缀，避免与既有 `*_errors` 混淆；R-P027-3 单测注入统一用 `monkeypatch` fixture，禁 `unittest.mock` 混用
- **提交与门禁**: 提交 `84ca76b`（2 文件 +159/−1，docs-only）→ CI run `43710060316` **三 job success**（3.10 / 3.11 / 3.12，test + mypy 全绿）
- **Step 2 Review（异构基座 GLM-5.3-Flash ≠ Step 1 作者 DeepSeek-V4.1-Flash，时点 HEAD `b13e7d6`）**: **pass**（[RESEARCH_p027 §10](RESEARCH_p027_silent_exception_governance_phase3.md)）——E1 重放：逐目录 grep 22 处行号与 §3 清单**逐行吻合**，分类算术 A2+B14+C2+E4=22、分布 11+5+2+2+1+1=22 均复核，内部链接 0 broken；E2 重放：探针重跑输出与 §5 **逐字段一致**（`nan`+0 记录 / `[0.0,1.0]`+0 记录）；E4 重放：pandas **2.2.3** + `mypy --explicit-package-bases filter` **10 files 0 error**，§6「不可合并」结论复现；E3 分类抽验 **16 处全量读码**（A 2/2 全验、E 4/4 全验、C 2/2 全验、B 8 处代表 + 3 处同构背书）**零分类错误**；门禁四项 (a)-(d) 全过。发现 **0 P1 / 0 P2 / 0 P3 + 2 观察**（O-S2-P027-1 `filter/custom.py` fail-open 的降级说明以行内注释形式存在，B 类归属不变、判据不受影响；O-S2-P027-2 §4「不改文案」与 §7.2「1074 debug→warning」的边界交 Step 3 DESIGN 显式声明「允许级别提升、禁止文案与语义变更」）
- **Step 3 DESIGN（作者基座 DeepSeek-V4.1-Flash，HEAD `ad04dfe`）**: [DESIGN_p027](DESIGN_p027_silent_exception_governance_phase3.md) 完稿——**D1** `filter/` 5 处载体下沉 `BaseFilter`（`_failure_counts` + `_record_failure()` + `get_failure_stats()`，4 子类各 1 行；`UniverseFilter` 自带同构三件套），**保留 fail-open 语义**；**D2** `agents/` 9 处逐类实例计数，唯一级别提升 `agent_framework.py:1074` `debug`→`warning`（文案逐字不变）；**D3** C 类 2 处「日志 + 计量」双补（`stats.py:139` → `IC 半衰期计算失败（返回 NaN）: %s`；`assumption_monitor.py:201` → `KPSS 检验失败（返回乐观默认值 0.0/1.0）: %s`，均 `exc_info=True`），**合法早退不计入**（早退 0 / 异常 1，可区分）；**D4** 5 个既有报告出口追加 `failure_counts` 键 + 5 个新只读方法（已核查仓库无严格 schema 断言）；**D5** E 4 + A 2 零改动；**D6** `StrategyEngine.run()` / `UniverseFilter.build_masks()` / `create_all_gurus()` 三处入口清零；**D7** 不新增 raise、不改捕获类型、既有文案逐字不变
- **Step 3 量化口径**: 计量点 **16**（B 14 + C 2）+ 零改动 **6**（E 4 + A 2）= **22**；变更面 **10 代码文件 + 1 测试**（`filter/base.py` / `filter/custom.py` / `filter/universe_filter_clean.py` / `agents/` 6 / `strategy_evaluation/stats.py`）；不变式 **I1-I8**（I1 `except Exception` 仍 22、I3 返回值语义零变更、I7 golden 零重录、I8 测试 ≥ **711** = 687 + 24）；测试规格 **12 函数 / 24 实例**全 `monkeypatch`；分 **B1-B4** 四个可独立回退提交单元；新增风险 **R-P027-4**（类级计数器跨调用污染 → 入口 `clear()` + T8）/ **R-P027-5**（嵌套重复累加 → 计量点均在末级 handler）
- **O-S2 观察裁决（Step 3 关闭）**: O-S2-P027-1 → 判据口径澄清为「无日志、无计数、无返回说明（注释/日志/文档任一载体）」，C 类 2 处三者皆无，结论不变；O-S2-P027-2 → D2/D7 明确「允许日志级别提升、禁止文案与语义变更」，仅 `:1074` 一处行使
- **Step 4 DESIGN Review（异构基座 GLM-5.3-Flash ≠ DESIGN 作者 DeepSeek-V4.1-Flash，时点 HEAD `0ffb68a`）**: **pass（含 2 P3 文档修正，已闭环）**（[DESIGN_p027 §11](DESIGN_p027_silent_exception_governance_phase3.md)）——E3 载体核验：`BaseFilter.__init__`(base.py:44)、4 子类 except 归属（`MultiConditionFilter` L146 无 except，与 §9.2 一致）、`CompositeFilter.__init__` 显式 `super().__init__(config)`（L169，下沉属性无 AttributeError 风险）、`UniverseFilter` 非子类 + `build_masks` L130、6 类载体全存在、`create_all_gurus` 确为 `@classmethod`、D4 五出口全实证（`get_performance_summary` 属 `:1138` ResearchTeamAgent；`agent_framework.py:336` 存在另一同名方法，实施勿误改）、`:1075` 文案锚点逐字确认；算术复核：D1 5 + D2 9 + D3 2 = **16 计量** + D5 **6 零改动** = 22 ✓、24 实例 ✓、I8 711 ✓；发现 **0 P1 / 0 P2 / 2 P3（当轮修正）+ 1 观察（关闭）**：F-S4-P027-1 §1 D4 行「6 既有+4 新」与详表 5+5 不一致（已修 §1 与本节同步行）、F-S4-P027-2 §1 D6 行漏列 `create_all_gurus`（已修为三入口）、O-S4-P027-1 R-P027-5「末级 handler」表述不精确 → 已改写为「内层 `:825` 吞异常后不冒泡至外层 `:1074`，独立异常源无重复计数；T5/T12 分用例」；门禁四项 (a)-(d) 全过 → **满足进入 Step 5 IMPL 条件**
- **Step 5 IMPL（作者基座 DeepSeek-V4.1-Flash，HEAD `6d3e0b7`）**: [IMPL_p027](IMPL_p027_silent_exception_governance_phase3.md) 完稿——§1 范围与四条不可越界前提（fail-open 保留 / `:1075` 文案逐字 / `create_all_gurus` 类级计数 / `:336` 同名方法勿误改）；§2 拆 **B1 filter/**（3 文件 + T1 5 items）/ **B2 agents/**（6 文件 + T2-T8/T11 15 items）/ **B3 C 类显形**（2 文件 + T9/T10/T12 4 items）/ **B4 文档回填**，计量 16 + 零改动 6 = 22；§4 逐文件精确变更规格（10 文件，全部锚点为实施前 HEAD 行号，含插入位置、键名、保留行为与代码片段）；§5 测试 12 函数 / 24 实例逐条指定注入方式与断言；§6 门禁口径（预期 **711 passed** / mypy **37** / black **117** / golden 零重录，实测列一律待 Step 9）；§7 新增实施注意项 **A1-A7**
- **Step 5 实施期核验（新增证据，非 DESIGN 复述）**: ① `filter/custom.py` 四子类 `__init__` 均显式 `super().__init__(config)`（L43/L99/L242/L297）→ D1 载体下沉**无 AttributeError 风险**（A1 相邻结论，二次实证）；② `GuruDataLoader.__init__` L55 即调 `self._load_all()` → 计数初始化**必须先于 L55**，否则首个坏 JSON 触发 `AttributeError`（**A1 / P2**）；③ `_kpss_test` 合法早退 L189 与异常兜底 L202 返回值**完全相同**（`0.0, 1.0`），计数为唯一区分手段（**A4**）；④ `calculate_half_life` 三处早退 L124/L131/L136 返回值均 `nan`（**A5**）；⑤ `research_team_v2.py` 共 9 个 `__init__`，仅 `FundManager`（L753）需计数（**A3**）；⑥ `StrategyEngine.run` L159 直返 `self._generate_results()`，改为「取 result → 追加键 → return」可不动签名（**A6**）
- **Step 6 IMPL Review（异构基座 GLM-5.3-Flash ≠ IMPL 作者 DeepSeek-V4.1-Flash，时点 HEAD `aafc7cd`；Step 5 提交 CI run `43713527576` 三 job success 先行确认）**: **pass**（[IMPL_p027 §10](IMPL_p027_silent_exception_governance_phase3.md)）——E3 逐文件锚点核验：10 代码文件 **53 锚点**全部落位（`custom.py` 8/8、`agent_framework` 6/6 含 `:1075` `logger.debug` 实证、`multi_strategy_engine` 8/8 且全文件 `except Exception` 恰 3 处、`guru_agent_v2` 7/7 含 A1 顺序 L53→L54→L55 与 `@classmethod` L473、`assumption_monitor` 3/3 含 A4 同值早退、`stats.py` 6/6 含 A5 三早退）；I1 全仓 `except Exception` 计数 agents 11 + filter 5 + stats 1 = **17**（= 计量 16 + `:1529` 零改动 1）+ scripts/batch/cli 零改动 5 = **22 ✓**（= 计量 16 + 零改动 6；Step 8 F-S8-P027-1 表述修正）；命名冲突扫描 `_record_failure` / `get_failure_stats` / `_failure_counts` / `_create_failure_counts` 代码面零命中；注入可行性实证（T3 路径：L1041 `make_decision` 调用点在 L1022 `try` 内、内层 L825 仅捕 `role.analyze`，异常必达外层 L1074）；发现 **0 P1 / 0 P2 / 3 P3（当轮修正）+ 1 观察（移交 Step 7）**：F-S6-P027-1 §4.1 `_data_manager = None` 锚点 L49 → 实为 **L53**、F-S6-P027-2 §4.1「`MultiConditionFilter` 无 `__init__` 覆写」不实（L153 覆写 + L167 `super().__init__(config)`，「继承安全」结论不变）、F-S6-P027-3 §7 A3「8 个 `__init__`」实为 **9 个**（grep 实证）；O-S6-P027-1 `tools/` 3 处 + `examples/` 1 处 `except Exception` 不在 RESEARCH §3 清单（口径继承 RESEARCH_p026 七单元，IMPL 变更面无越界，疑 E 类工具/示例脚本）→ 移交 CHECKLIST 确认归类
- **Step 7 CHECKLIST（作者基座 DeepSeek-V4.1-Flash，HEAD `2cf8c38`）**: [CHECKLIST_p027](CHECKLIST_p027_silent_exception_governance_phase3.md) 完稿——六组 **44 项**零预填（A `filter/` B1 5 / B `agents/` B2 10 / C C 类显形 5 / D 不变式 I1-I8 8 / E 测试与门禁 V1-V5 9 / F 治理台账 7），每项含 DoR/DoD + 证据出口 + 锚点，实测列 44 处全为 `[待 Step 9]`（RULE-1 零 ✅ 预填，机械计数复核 5+10+5+8+9+7=44）；**覆盖映射**：T1-T12 **12/12**、I1-I8 **8/8**、V1-V5 全落 E 组；**Step 8 交接 4 项**（口径一致性 22/24/711-37-117 三文档对拍 / A1-A2-A6 顺序敏感核验 / O-S6-P027-1 归类先行判定 / 三批红态留档）
- **Step 8 一致性 Review（异构基座 GLM-5.3-Flash ≠ CHECKLIST 作者 DeepSeek-V4.1-Flash，时点 HEAD `f97f27d`；Step 7 CI run `43732759944` 三 job success 先行确认）**: **pass**（[CHECKLIST_p027 §10](CHECKLIST_p027_silent_exception_governance_phase3.md)）——口径对拍 8 行全绿（22 四文档一致 / 24 三处一致 / 711-mypy37-black117 三处一致 / golden 零重录 / I1-I8 ↔ D1-D8 **8/8** / 锚点基线 `6d3e0b7` 继承一致）；**O-S6-P027-1 判定落位（CHECKLIST F6 ✅）**：`tools/` 3 处 + `examples/` 1 处读码均**非 C 类静默形态**（`benchmark.py:155` print+logger.error / `distillation_audit.py:195` logger.error+结构化 append / `ui_dashboard.py:271` tracer+raise / `run_full_backtest_fixed.py:115` print+traceback+return None），不在 RESEARCH §3 七单元口径 → **22 维持，观察关闭，不新增 U 项**；发现 **0 P1 / 0 P2 / 6 P3（当轮修正）+ 0 观察**：F-S8-P027-1 IMPL §10.2 与上节 Step 6 行「17 在治理面」算术不严谨（agents 11 已含 `:1529` 重复计入；两处同步改「17 = 计量 16 + `:1529` 零改动 1；合计 22 = 16 + 6」）、F-S8-P027-2 CHECKLIST B3 证据命令改带引号字面键 `'"failure_counts"'`、F-S8-P027-3 B10 第 6 载体限定 `GuruDataLoader.get_failure_stats()`、F-S8-P027-4 E8 改「全绿 0 failed / 0 error」（-k 子集基线数未登记）、F-S8-P027-5 A2 参数集归属澄清（前 4 归 A2、第 5 归 A3）、F-S8-P027-6 DESIGN §6 目标态 black 116→**117** → 满足进入 Step 9 条件
- **Step 9 TDD（作者基座 DeepSeek-V4.1-Flash，实施前 HEAD `6d3e0b7`）**: 三批红绿闭环——**B1** `filter/`（`BaseFilter` 三件套 + `custom.py` 4 处 + `UniverseFilter` 自备 + `build_masks` 清零）→ T1 红 `5 failed`（AttributeError）→ 绿 `5 passed`，提交 `b3f6b5e`；**B2** `agents/` 6 文件（实例计数 + 5 个 dict 出口 + `create_all_gurus` 类级计数）→ T2-T8/T11/T12 红 `15 failed, 5 passed` → 绿 `21 passed`，提交 `6259e42`（`stats.py` 出口键按 F-S9-P027-3 前置）；**B3** C 类 2 处（`calculate_half_life` / `_kpss_test` 补 `as e` + 计数 + WARNING）→ T9/T10 红 `2 failed, 21 passed` → 绿 **`24 passed`**，提交 `7dfe755`；**B4 文档回填**（IMPL §6/§11、CHECKLIST 43 处、PROGRESS、CHANGELOG、README/ARCHITECTURE 计数）
- **Step 9 门禁实测**: 全量 **711 passed**（687 + 24）/ `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error** / `black --check core tests` **117 unchanged** / golden G1-G7 零重录（`tests/golden/` 零改动）/ `except Exception` 合计 **22**（10 代码文件 17 处含 `:1529` 零改动 1 + scripts 2 + batch 2 + cli 1）/ 零改动面 diff 空 / 零新增 `raise`
- **Step 9 顺序敏感核验**: A1 ✅ `GuruDataLoader` 计数 L55 早于 `_load_all()` L56；A2 ✅ `"failure_counts"` 字面键仅 L1152（`ResearchTeamAgent`），`BaseAgent:336` 同名方法零改动；A6 ✅ `_generate_results` def 行零变更（`run()` 三行追加出口）
- **Step 9 偏差登记**: F-S9-P027-1（T11⑥ `GuruDataLoader.get_failure_stats()` 直接返回 dict，用例引入 `nested` 标志）/ F-S9-P027-2（`industry_rotation_v2` 模块缺失，T2 以 `sys.modules` 注入替身）/ F-S9-P027-3（`stats.py` 出口键前置至 B2 以保提交绿）/ F-S9-P027-4（观察：`^def test_` 12 计数口径）——详见 [IMPL_p027 §11.5](IMPL_p027_silent_exception_governance_phase3.md)
- **Step 9 提交与 CI**: `b3f6b5e` → `6259e42` → `7dfe755` → `4974552`（B4 文档），推送 origin/master；CI run `43774985791`（B3 `7dfe755`）/ `43775385346`（B4 `4974552`）三 job（3.10 / 3.11 / 3.12）均 success
- **Step 10 ADD 审计（同基座 DeepSeek-V4.1-Flash，HEAD `4974552`；[CHECKLIST_p027 §12](CHECKLIST_p027_silent_exception_governance_phase3.md)）**: **自审 pass 99/A**——Phase 0 DESIGN 5/5（无模糊词）；Phase 1 完整性 10 载体 + 16 接入 + 6 出口 + 3 清零 + 6 零改动面全覆盖；Phase 2 保真度（插入位置先于日志/返回、唯一级别改动、生产 diff 仅 **+116/−4** 且 4 行删除全部可解释、5 既有签名零变更）；Phase 3 必要性（0 新增 `raise`、无越界文件、无顺手重构）；Phase 4 语义（清零生命周期 / 跨调用不累加 / 早退与异常靠计数区分 / 嵌套不重复 / getter 返回拷贝）
- **Step 10 E4 盲区扫描**: AST 脚本（仓库外 `%TEMP%\p027_step10_blindspot.py`）扫 **97 文件**，零可观测 except **21 项**——**本批 22 处口径内 0 项**；其中 `agents/` 8 项同类静默路径登记 **U-P027-1**（下一批候选），其余 13 项（import 降级 4 / core 3 / scripts 3 / tools 2 / factor_library 1）只登记
- **Step 10 发现分级**: **0 P0 / 0 P1 / 0 P2 / 1 P3（F-ADD-P027-1 `_create_failure_counts` 类属性无锁，当前调用点全单线程 → 登记不改）+ 3 观察（O-S10-P027-1~3）**；自审基座与作者同源 → 异构终审前提成立
- **Step 10 RULE-5 异构终审（GLM-5.3-Flash，HEAD `d381fd6`；[CHECKLIST §13](CHECKLIST_p027_silent_exception_governance_phase3.md)）**: **pass 99/A**——E1（+116/−4 逐文件复核 / 0 raise / 删除行 4 行 / 零改动面空）/ E1 门禁复跑（711 / 37 files / 117 / golden 空）/ E3 独立读码（10 载体 + 16 接入 + 6 出口 + 3 清零 + A1/A7 顺序约束 + 出口键无碰撞）逐项一致；E4 重跑 97/21 与脚本判据审查一致；F-ADD-P027-1、U-P027-1、O-S10-P027-3、Phase 0 5/5 四项裁定均维持；唯一发现 **F-R5-P027-1（P3）**：§12.8 机械校验读数漏计自身行（❌ 声明 3 实测 5、`[待 Step 9]` 声明 2 实测 3，零真实判定单元格受影响），当轮修正
- **P-027 批次关闭**（2026-11-16）：Step 1-10 全通过 + 异构终审 pass + 门禁绿 + CI 绿；唯一待办 **U-P027-1**（`agents/` 8 项同类静默路径，下一批候选）
- **下一 Step**: 无（P-027 收口；后续触发条件见 U-P027-1）

### 3.33 P-028 台账去重（T3 轻批，2026-11-16）

- **触发**: P-027 收口后待办分析发现 **U-P021-1 与 U-P024-2 重复登记**（同一事项：CI 增加 `uv lock --check`），且 U-P024-2 自身已注明「与 U-P021-1 同源」——双跟踪源会在触发时导致重复立项。
- **变更面（4 文件，纯文档 / 零代码 / 零测试）**:
  - [PROGRESS §1.4](PROGRESS.md)：L89 `U-P021-1` → 「已合并」指针（不删行，保留 RESEARCH_p021 锚点）；L109 `U-P024-1` 追加实测注记（mypy 2.1.0 / pandas 2.2.3 / numba 已装未声明）；L110 `U-P024-2` 标注「承接 U-P021-1，单一跟踪源」+ 触发条件并集；§1.4 新增本批 P-028 行
  - [RESEARCH_p021 §6](RESEARCH_p021_dependency_lock_maintenance.md)：U-P021-1 四元块首行追加「2026-11-16 并入 U-P024-2」
  - [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)：U-P024-2 四元块首行追加「单一跟踪源，承接 U-P021-1」
  - `CHANGELOG.md`：`[Unreleased] Changed` 追加 P-028 条目
- **历史零改写**: §3.21（P-021 收口）/ §3.28（P-024 收口）保留原文；U-P021-1 行保留（历史与文档引用可达）。
- **门禁（纯文档批）**: 全量 `pytest -q` **711 passed**（E1 复跑，exit 0）；mypy **37 files 0 error** / black **117 unchanged**（零 Python 改动，引用 P-027 收口读数）。
- **结论**: 台账单一来源成立；U 表独立 pending 项 **24 → 23**（U-P021-1 转已合并，非关闭）；U-P021-2/3 与 U-P024-3/4 维持独立跟踪。

### 3.34 P-029（静默失败治理第四批 · `agents/` 8 处）Step 1 记录（2026-11-16）

- **触发**: 用户指令「执行 U-P027-1」→ 立项 P-029；U-P027-1 触发条件「发起静默失败治理第四批」成立。范围继承 [CHECKLIST_p027 §12.6](CHECKLIST_p027_silent_exception_governance_phase3.md) 的 8 项 E4 扫描结果。
- **E2 复现（8/8，探针 `%TEMP%\p029_probe.py`，基线 HEAD `310998d`）**: S1-S3 `prepare_factors` 三个 bare except → 三份缓存全部 `None` 且 0 条错误日志（仅 2 条管道初始化日志）；S4 `get_performance_summary` → `team_report` 键缺失且 `failure_counts={}`；S5 `_generate_orders` → 目标持仓为空、0 日志；S6 `_execute_next_day_orders` / S7 `_process_pending_orders` → 静默 `return`、队列保留、0 日志；S8 `MeanVarianceAllocator.allocate` → `LinAlgError` 走 pinv、无计数器、0 日志。
- **分类**: **B 7**（S1-S7）+ **待裁决 1**（S8：注释为载体但运行期不可见，建议判 B，R-P029-1）+ **观察 1**（S3b：`_init_research_team` L928 条件不满足时静默不建轮动分析器，U-P029-1 交 Step 3 裁决）。
- **文档**: [RESEARCH_p029](RESEARCH_p029_silent_exception_governance_phase4.md) 完稿（§3 八处清单 / §4 分类 / §5 E2 原文 / §6 复用面 / §7 方案矩阵 M-A + 8 个键名草案 + 低效排除 / §8 风险四元块 / §9 负向发现 / §10 下一 Step）；§1.4 新增 P-029 行、U-P027-1 转 in-progress。
- **约束**: 零 fail-fast、零返回值语义变更、零既有文案改写；`except Exception` 合计仍 **22**（8 处均非 `except Exception`）。
- **提交与 CI**: 提交 `9422a42`（2 文件 +193/−1，docs-only）→ CI run `43787578197` **三 job success**（3.10 / 3.11 / 3.12）。
- **下一 Step**: **Step 2 独立 Review（异构基座）**——本文件作者基座 DeepSeek-V4.1-Flash，须由非作者基座复核（P-027 先例 GLM-5.3-Flash）；重点：8 处行号与异常类型重放、E2 探针重跑、S8 分类裁决（R-P029-1）、S3b 纳入裁决（U-P029-1）、`agents/` 同型站点 E4 复扫。

### 3.34.1 P-029 Step 2 异构 Review 记录（2026-11-16）

- **基座**: GLM-5.3-Flash（≠ RESEARCH 作者 DeepSeek-V4.1-Flash），基线 HEAD `eeec92b`；记录见 [RESEARCH_p029 §11](RESEARCH_p029_silent_exception_governance_phase4.md)。
- **E1 重放（8/8 一致）**: bare ×4（L971/981/991/1158）、窄类型 ×3（L330/390/452）、`LinAlgError` ×1（L628），行号与异常类型全部落在 §3 声明区间；S3b L928 条件后直接 `try`、无 `else`。
- **E2 重跑**: 探针 7 行输出与 §5 **逐字一致**；日志归因复核确认 2 条日志出自管道/合成器构造器（`try` 之前），与异常无关。
- **E4 复扫**: 独立重写 AST 脚本（`%TEMP%\p029_rescan.py`）——`agents/` 22 处理器中零可观测 **9 处** = 8 项待治理逐一命中 + `research_team_v2.py:27`（既有 import 降级分类）→ **无遗漏同型站点，口径封闭**。
- **裁决**: R-P029-1 **维持 S8 判 B**（pinv 改变数值路径，属 F-D3-P025-1 同型静默数值降级；注释说明 why 非 whether）；U-P029-1 **纳入 S3b 但形态修正**——计量键 `rotation_analyzer_skipped`（`else` 分支 1 行），不加 warning（可选数据缺失属合法形态，防刷屏）→ **F-S2-P029-1（P3）当轮回写 §8**；R-P029-2/3 维持。
- **分级**: 0 P1 / 0 P2 / **1 P3（当轮已修）** + 2 观察（O-S2-P029-1 import 降级维持既有裁决 / O-S2-P029-2 S8 键名形态统一移交 Step 3）。
- **Step 3 定稿口径**: **9 计量 / 3 文件 / 零新增日志**（8 站点 + S3b 跳过键）；新增载体仅 `MeanVarianceAllocator`（实例级三件套）；`except Exception` 合计恒 **22**。
- **提交与 CI**: 提交 `7fc094b`（2 文件 +70/−4，docs-only）→ CI run `43788645756` **三 job success**（3.10 / 3.11 / 3.12）。

### 3.34.2 P-029 Step 3 DESIGN 记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash，基线 HEAD `7045001`；[DESIGN_p029](DESIGN_p029_silent_exception_governance_phase4.md) 完稿（§1 D1-D7 / §2 映射 / §3 决策详述 / §4 实现规格 / §5 I1-I8 / §6 V1-V5 / §7 R-P029-4~7 / §8 B1-B3 回退点 / §9 设计期发现 / §10 下一 Step）。
- **口径**: **9 计量 / 3 文件 / 0 新增日志 / 0 新增 raise**——D1 S1-S3（`price_cache` / `industry_cache` / `mktcap_cache`）/ D2 S3b（`rotation_analyzer_skipped`，`else` 挂 `if`）/ D3 S4（`performance_summary_team_report`）/ D4 S5-S7（`orders_missing_price` / `next_day_open_price` / `pending_open_price`）/ D5 S8（`pinv_fallback` + 新建实例三件套，M-A 不下沉 `BaseAllocator`）。
- **出口**: S1-S4 → 既有 `get_performance_summary` 的 `failure_counts`（零改动）；S5-S7 → 既有 `StrategyEngine.run()`（零改动）；S8 → 新增 `get_failure_stats()`（1 getter）。
- **不变式**: I1 `except Exception` 恒 22 / I2 零 raise / I3 返回值语义零变更 / I4 零改动面九面 / I5 既有签名零变更 / **I6 零新增日志 + 既有文案逐字** / I7 golden 零重录 / I8 目标 **722 passed / 81 文件 / black 118 / mypy 37**。
- **测试**: 7 函数 / 11 实例（V1 3 + V2 1 + V3 1 + V4 2 + V5 2 + V6 1 + V7 1），全部 `monkeypatch`，禁 mock 库；红态预期全失败。
- **设计期核验**: `rotation_analyzer` 于 L881 初始化为 `None`（D2 不新增赋值）；`MeanVarianceAllocator` 无子类（R-P029-5 成立）；`BaseAllocator` 无 `__init__`（M-A 理由实证）；S4 出口已在 P-027 就绪（零出口改动）。
- **提交与 CI**: 提交 `0afcfec`（2 文件 +275/−1，docs-only）→ CI run `43790175885` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.34.3 P-029 Step 4 异构 Review 记录（2026-11-16）

- **基座**: GLM-5.3-Flash（≠ DESIGN 作者 DeepSeek-V4.1-Flash），基线 HEAD `f802bbe`（代码与 `0afcfec` 一致，仅 docs）；记录见 [DESIGN_p029 §11](DESIGN_p029_silent_exception_governance_phase4.md)。
- **E1 锚点核验（9/9 命中）**: S1-S3 L971/981/991 bare except + `pass`；S3b L928-936（`if` 直下 `try`，无 `else`）；S4 L1154-1159 bare except；S5-S7 L330/390/452 窄类型；S8 L625-630 `LinAlgError`→pinv。9 键名与 P-027 既有键零冲突；`get_failure_stats` 在 `strategy_allocator.py` 无同名；载体三件套已存在于 `ResearchTeamAgent`（L882/L891/L895）与 `StrategyEngine`（L111/L115/L119）。
- **E2 基线实测（I8 四元对拍）**: pytest collected **711** / tests/ 全 .py **80**（77 test + 3 `_` 辅助）/ black **117 unchanged**（= core 37 + tests 80，口径自洽）/ mypy **37 files 0** → 目标 722 / 81 / 118 / 37 算术全成立。
- **E4 独立扫描**（自写 `%TEMP%\p029_step4_scan.py`，不复用作者脚本）: `agents/` handlers=22 / **silent=9**（8 站点 + `research_team_v2.py:27` import 降级）——无遗漏、无新增；`except Exception` 41 文件 = **22**（I1 成立）；`BaseAllocator` 5 子类均有自有 `__init__`、基类无 `__init__`（M-A 实证）。
- **五项裁决全 pass**: 锚点键名 / D2 `else` 挂 `if`（误挂 `try` 的 `else` 会在成功时误计）/ M-A 维持（M-B 需改 6 类 + 漏 super 风险）/ I8 四计数 / 零新增日志裁定（可选数据缺失 warning 将刷屏，与 R-P029-4 同源）。
- **分级**: 0 P1 / 0 P2 / **3 P3（当轮回写 DESIGN）**——F-S4-P029-1 S4 出口同调滞后（L1152 快照先于 try/except，V5 对 S4 同调不成立 → D3 增 L1152 下移微改，§2/D6/§4.1/V3/§9.1 同步）/ F-S4-P029-2 V1 触发面（缺失文件不进 except，须用存在但损坏的 pkl → §4.2 V1 补注记）/ F-S4-P029-3 静默面清点（§1「零改动 0 处」→「1 处」，`research_team_v2.py:25-28` import 降级下游经 L914→L843 可观测）；2 观察——O-S4-P029-1 `allocate` L633-637 非异常等权回退（「非异常静默回退」判据扩展候选）/ O-S4-P029-2 I8「81 文件」口径注记。
- **提交与 CI**: 提交 `ce5911c`（2 文件 +97/−12，docs-only）→ CI run `43792545570` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.34.4 P-029 Step 5 IMPL 记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash（= DESIGN 作者，Step 5 允许；Step 6 须异构），基线 HEAD `23132cb`（代码与 `7045001` 一致）；[IMPL_p029](IMPL_p029_silent_exception_governance_phase4.md) 完稿（§1 范围五前提 / §2 B1-B4 拆解 / §3 实施顺序 / §4 逐锚点变更规格 / §5 测试 7 函数 11 实例 + §5.1 注入实证 / §6 门禁口径 / §7 A1-A7 + F-I-P029-1 / §8 回退点 / §9 下一 Step）。
- **精确变更面**: `agent_framework.py` **净 +2**（S1-S3 与 S4 均为 `pass` → 计量行，净 0；S3b `else` +2；L1152 位移净 0；**变更 7 行**）/ `multi_strategy_engine.py` **净 +3**（三处 except 首行插入）/ `strategy_allocator.py` **净 ≈+10**（计数器 1 + `_record_failure` 3 + `get_failure_stats` 3 + except 1 + 2 空行）+ 新测试文件（≈260 行）。
- **§5.1 注入路径实证**（探针 `%TEMP%\p029_step5_probe.py`，改前代码，7 组全通）: V1 `prepare_factors` 在 `FactorPipeline`/`FactorCombiner` 模块级替身 + 损坏 pkl 下正常进入 except（三缓存 `None`）；V2 `sys.modules` 双模块注入后 `_init_research_team(None)` 正常返回；**V3 红态 `summary["failure_counts"] == {}` 直接实证 F-S4-P029-1（L1152 快照先于 except）**；V4/V5 注入后队列语义不变；V6 无 getter（红态 `AttributeError`）、正常/pinv 权重均归一；V7 正常路径基线通过。
- **实施注意项**: A1 `else` 缩进对齐 `if`（AST 校验归属）/ A2 V2 须先置 `_research_team_available=True` / A3 bare except 零改写（I1 恒 22）/ A4 S5 双参数 / A5 测试替身面 / A6 `caplog.clear()` 规避构造期 2 条 warning / A7 V7 no-op 日处理固定无失败路径。
- **实施期发现**: F-I-P029-1（P3）DESIGN §4.1「agent_framework ≈9 新增行」实为「变更 7 行 / 净 +2」——本文件已按净增标注，Step 9 以 `git diff --numstat` 回填；O-I-P029-1（观察）`strategy_allocator` 估算 ≈12 vs 实测 ≈10（空行余量）。
- **I1 复核命令已实证**: AST 十文件扫描输出 **22**（命令写入 IMPL §6，可独立复跑）。
- **提交与 CI**: 提交 `e6daa05`（2 文件 +464/−1，docs-only）→ CI run `43817469869` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.34.5 P-029 Step 6 独立 Review 记录（2026-11-16）

- **基座**: GLM-5.3-Flash（≠ IMPL 作者 DeepSeek-V4.1-Flash），基线 HEAD `50f3a01`（代码与 `23132cb` 一致，仅 docs）；记录见 [IMPL_p029 §10](IMPL_p029_silent_exception_governance_phase4.md)。
- **E1 三方锚点对拍（IMPL §4 ↔ 代码 ↔ DESIGN §4.1，3 文件全命中）**: agent_framework 5/5（载体 L882/L891-893/L895-897 + S1-S3/S3b/S4 锚点 + L336 禁区）；multi_strategy_engine 6/6（grep 重放全文件 try/except 恰 6 组 8 处，S5-S7 落位精确）；strategy_allocator 5/5（`BaseAllocator` 无 `__init__` / S8 L625-630 / 注册表 L775 / `get_failure_stats` 无同名）。9 键名逐字一致。
- **E2 重放与独立复核**: 作者探针 `%TEMP%\p029_step5_probe.py` 复跑 7 组读数**逐字一致**；I1 AST 独立复跑 = **22**；`MultiStrategyEngine` class 实测 **L502**（IMPL §4.2 旧写 L487 为 P-027 实施前旧号）；P-027 回归面核验——test_p027 T11 ① 断言 `payload["failure_counts"]` 为 dict，L1152 下移后键恒存在（`fund_manager is None` 亦写入），**T11 不受影响**。
- **E3 测试规格推演（V1-V7 逐项）**: 全部 ✅——V1 模块级 patch 可达 + 替身签名匹配；V2 = P-027 T2 同范式（`industry_rotation_v2` 仓库不可导入，fake 注入必要）；V5 S6 需预置 `_next_day_orders`（L385-386 守卫）；V6 `np.linalg.inv` 单参匹配 + 真实 `StrategyEvaluator` 正常路径不触 `LinAlgError`；V7 `_generate_results` 可用（P-027 T4 同路径已绿）。
- **A1-A7**: 7/7 实证成立。
- **分级**: 0 P1 / 0 P2 / **5 P3（当轮修正）**——F-S6-P029-1 V1 损坏 pkl 未限定 per-case（三例互串破坏 `{key: 1}` 精确断言 → §5 V1 回写：price 例不写 pkl / industry 例仅 industry.pkl / mktcap 例仅 mktcap.pkl）/ F-S6-P029-2 §4.4 `import pickle` 未使用（删除）/ F-S6-P029-3 `MultiStrategyEngine` L487→L502（行号漂移更正）/ F-S6-P029-4 DESIGN §6 契约 V1-V5 与测试 V1-V7 ID 空间重叠（DESIGN §6 补注记，Step 7 以测试 V1-V7 为准）/ F-S6-P029-5 B4 回填目标 §10→§11（§10 由本 Review 占用，P-027 先例）；0 新观察。
- **提交与 CI**: 提交 `9614ba4`（3 文件 +79/−8，docs-only）→ CI run `43819626058` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.34.6 P-029 Step 7 CHECKLIST 记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash（与 RESEARCH/DESIGN/IMPL 同源；Step 8 须异构），基线 HEAD `285d952`；[CHECKLIST_p029](CHECKLIST_p029_silent_exception_governance_phase4.md) 完稿（六组 **38 项** / 每项 DoR-DoD + 证据出口 / §7 预填检查 / §8 Step 8 交接 5 项 / §9 签字表）。
- **分组**: A 6（`agent_framework.py` 5 计量 + bare 零改写）/ B 4（`multi_strategy_engine.py` 3 计量 + 出口复用）/ C 5（`strategy_allocator.py` 三件套 + S8 + 拷贝语义 + 正常零计数 + M-A 边界）/ D 8（I1-I8）/ E 9（V1-V7 覆盖 + 红态纪律 + 11/722/mypy/black/零 mock/回归/CI）/ F 6（四文档/PROGRESS/CHANGELOG/README+ARCH 计数/未决与回退/提交链）。
- **RULE-1 零预填（机械自检）**: 验收项 **38**（ID 去重 38/38）、实测列 `[待 Step 9]` **38 处**、行内 ✅ **0 处**；全文 `[待 Step 9]` 计数 40 = 38 验收 + 2 合法字面引用（文档头规则行 + §7 本行）。
- **覆盖映射**: 测试用例 V1-V7 **11/11 实例**全覆盖（A1-A3=V1 3 / A4=V2 / A5=V3 / B1=V4 2 / B2+B3=V5 2 / C2+C3=V6 / C4=V7）；不变式 I1-I8 **8/8**（D1-D8）；设计决策 D1-D7 全落点。
- **基线/目标**: 基线 **711 / 80 / 117 / 37 / I1 22** → 目标 **722 passed / 81 文件 / 118 / 37 / 22**；F4 已实测 README **4 处**（L7 badge / L99 / L278 / L427 含「80 files」）+ ARCHITECTURE L3。
- **Step 8 交接 5 项**: ① 四处口径一致性（9 计量 / 11 实例 / 722-81-118-37 / 零改动 1 处）；② F-S6-P029-4 的契约 V1-V5 vs 测试 V1-V7 两套 ID 复核；③ Step 9 顺序敏感三项（`else` 挂 `if` / V2 先置 `_research_team_available` / bare 零改写）；④ 红态留档须标注 V4 合法参数与 V7 engine 侧「红态即通过」豁免；⑤ 实施后行号漂移登记。
- **提交与 CI**: 提交 `2a67a59`（2 文件 +153/−1，docs-only）→ CI run `43820570395` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.34.7 P-029 Step 8 一致性 Review 记录（2026-11-16）

- **基座**: GLM-5.3-Flash（≠ Step 7 作者 DeepSeek-V4.1-Flash），基线 HEAD `b2014aa`；记录见 [CHECKLIST_p029 §10](CHECKLIST_p029_silent_exception_governance_phase4.md)。
- **机械校验五项（独立脚本 `%TEMP%\p029_step8_check.py`，全过）**: ① 四文档互链 9 条 **0 broken**；② ID 闭环 **38/38**（A 6 / B 4 / C 5 / D 8 / E 9 / F 6 六组序列全连续）；③ 计数 38 与 §7 声称一致；④ 零预填——行内 ✅ **0**、`[待 Step 9]` Step 7 时点 40 = 38 + 2 合规（Step 8 记录自身引入第 3 处字面引用 → 现 41 = 38 + 3，已在 §10.1 注明）；⑤ 角色引用链完整（CHECKLIST 签字表 Step 8 行已补 GLM）。
- **四处口径对拍（全一致）**: 9 计量 / 3 文件（RESEARCH §11 L237 定稿 ← §1/§4 分类推导；DESIGN §1 ×4 / IMPL §2 ×5 / CHECKLIST 标题+A5+B3+C1）；11 实例（DESIGN §4.2 / IMPL §5 / CHECKLIST E1+§7）；722-81-118-37（DESIGN I8 / IMPL §6 / CHECKLIST 头部+D8+E4-E6）；零改动 1 处（DESIGN §1 / IMPL §2 / CHECKLIST §8.1）+ I1=22 四处。
- **F-S6-P029-4 复核**: CHECKLIST 锚点列 V 编号全部为测试用例编号；DESIGN §6 契约→测试映射覆盖完整，**无混用**。
- **对齐矩阵**: 八站点→D1-D7→IMPL §4.1-4.3→CHECKLIST A/B/C 组 + I1-I8→D1-D8 + R/U/O 项→F5，**零遗留落点**。
- **E8 可执行性抽查**: `-k "agent or strategy_engine or strategy_alloc or portfolio or pending or p027 or p026"` 实测 **83/711 collected**——七关键词全命中。
- **分级**: 0 P1 / 0 P2 / **1 P3（当轮修正）**——F-S8-P029-1 **A ID 双套**（CHECKLIST 验收项 A1-A6 与 IMPL §7 注意项 A1-A7 同名异义）→ 4 处行内锚点 + B 组 DoR 统一加 `IMPL§7-` 前缀 + A 组 DoR 补 ID 空间注记 + §8.3 统一；1 观察 O-S8-P029-1（RESEARCH 9 计量口径落 §11 推导链 + `research_team_v2.py` 粒度引用 `:27` vs `:25-28` 并存，登记不改）。
- **提交与 CI**: 提交 `1f2f7b4`（2 文件 +89/−9，docs-only）→ CI run `43822155305` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.34.8 P-029 Step 9 TDD 实施记录（2026-11-16）

- **执行基座**: DeepSeek-V4.1-Flash（与上游同源，Step 9 允许），基线 HEAD `2080784`；记录见 [IMPL_p029 §11](IMPL_p029_silent_exception_governance_phase4.md) + [CHECKLIST_p029](CHECKLIST_p029_silent_exception_governance_phase4.md)。
- **三批红绿（逐批取证）**: B1 `e86b09d`——红 `5 failed`（V1 三参数 / V2 / V3）→ 绿 `5 passed`；B2 `7cf6718`——红 `3 failed, 6 passed`（V4 异常 + V5 双参数；V4 合法参数与 B1 合法基线豁免）→ 绿 `9 passed`；B3 `58954bd`——红 `2 failed, 9 passed`（`AttributeError: get_failure_stats`，V7 engine 侧豁免）→ 绿 **`11 passed`**。
- **代码变更（3 文件）**: `agent_framework.py` **+7/−5（净 +2）**——S1-S3 三处 `pass` → 计量（bare 保持）、S3b `else` 挂 `If`（AST 实证 `If L928 orelse=['Expr']`、无 `Try.orelse`）、S4 计量 + `failure_counts` 快照下移；`multi_strategy_engine.py` **+3/−0**——S5/S6/S7 except 首行插入；`strategy_allocator.py` **+10/−0**——`MeanVarianceAllocator` 三件套 + `pinv_fallback`。
- **门禁终态**: pytest **722 passed**（711 + 11，172 warnings）/ 测试文件 **81** / black **118 unchanged** / mypy **37 files 0 error** / golden **13 passed 零重录** / I1 **22** / I2 **0** / I5 `^-\s*def ` **0**（`get_performance_summary` 仍 2 处）/ I6 `logger.` 行 **0 增 0 删** / 零改动面九面 diff 空 / 回归子集 **84 passed**。
- **实施期发现**: F-S9-P029-1（P3）新增测试文件首版未过 black（格式化后复检 118 unchanged）；F-S9-P029-2（观察）black 调整 `numpy` 导入位序。F-I-P029-1（净 +2 / 变更 7）与 O-I-P029-1（≈+10）**假设验证闭环**。
- **提交与 CI**: 代码三批 `e86b09d` / `7cf6718` / `58954bd` → CI run `43824569283` success；B4 文档 `596e325`（6 文件 +120/−60）→ CI run `43825106609` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.34.9 P-029 Step 10 ADD 审计 + RULE-5 异构终审记录（2026-11-16）

- **基座**: **GLM-5.3-Flash**（≠ 四文档作者 DeepSeek-V4.1-Flash）——**RULE-5 异构条件天然成立，ADD 审计与异构终审合并为一轮**（区别于 P-027 的「同源自审 + 异基座终审」两段式）；审计对象区间 `2080784..e8578c2`（5 提交：`e86b09d`/`7cf6718`/`58954bd` 三批代码 + `596e325`/`e8578c2` 两批文档），记录见 [CHECKLIST_p029 §11](CHECKLIST_p029_silent_exception_governance_phase4.md)。
- **Phase 0-4**: Phase 0 spec 质量门 **5/5 = Tier A**；Phase 1 完整性（10 文件 **+398/−65** = 3 代码 + 1 测试 + 6 文档；9 计量站点引号键名逐一命中 `agent_framework` L938/974/984/994/1160 + `multi_strategy_engine` L331/392/455 + `strategy_allocator` L638，P-027 遗留 5 处零混淆；九面零改动零命中）；Phase 2 保真度（S1-S8 七锚点独立读码全 pass——4 处 bare `except:` 行零变更、`^-\s*def ` = 0、注释 L639 逐字、快照下移 L1162 同调）；Phase 3 必要性（生产面 raise = **0**、logger 行 **0 增 0 删**、无越界文件、无顺手重构）；Phase 4 语义（出口同调 / V4 双参数只计异常 / getter 拷贝 / 正常路径零计数 / M-A 边界 5 子类继承谱系零污染）。
- **E1-E5 门禁独立复跑**: pytest **722 passed**（73.87s）/ mypy **37 files 0 error** / black **118 unchanged** / golden **13 passed 零重录** / I1 AST **22** / 测试文件 **81**。
- **E4 盲区复扫**（`%TEMP%\p029_step4_scan.py`）: `agents/` **silent 9 → 1**——8 处计量站点全部转为可观测（body 含 `_record_failure`），唯一残留 `research_team_v2.py:27` import 降级（登记零改动点）；S4 出口顺序 L1159→L1160→L1162→L1163 同调实证。
- **发现分级**: **0 P0 / 0 P1 / 0 P2 / 1 P3（当轮已修）**——**F-R5-P029-1（P3）** CHECKLIST D2 实测列初版「测试辅助无 raise」表述失实（全区间 diff 实测测试注入辅助含 **5 处** raise：V2/V3/V4/V6 异常探针；生产面 = 0 成立），D2 实测列当轮改写并留痕；**2 观察**（O-S10-P029-1 残留静默点属显式设计 / O-S10-P029-2 U-P029-2 维持 pending 待独立批次）。
- **结论**: **pass（99/A）**——**P-029 批次关闭**（Step 1-10 全通过 + 异构终审 pass + 门禁绿 + CI 绿）。
- **提交与 CI**: 提交 `1c68f5f`（2 文件 +107/−4，docs-only）→ CI run `43827468599` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。
- **交付物**: 批次总结报告 [SUMMARY_p029](SUMMARY_p029_silent_exception_governance_phase4.md)（309 行 / §1-§10 全景：治理谱系、9 站点表、红绿与门禁、12 项 P3 台账、提交链、边界遗留）提交 `83a27aa` → CI run `43832206129` **success**。

### 3.35 P-030 台账收口（T3 轻批，2026-11-16）

- **触发**: P-029 关闭后待办分析发现两处台账失真——① **U-P027-1 仍标 `in-progress`**（P-029 已承接并关闭），会让后续待办分析把已完成项当成在办；② **U-P029-2 未在 §1.4 建行**，只散落在 P-029 行与 CHECKLIST，会漏跟踪。
- **变更面（2 文件，纯文档 / 零代码 / 零测试）**:
  - [PROGRESS §1.4](PROGRESS.md)：U-P027-1 → **done**（P-029 承接：9 计量 / `agents/` silent 9→1 / 终审 99/A）；新增 **U-P029-2** 行（`StrategyEngine` 次日订单簿时序语义，pending P3）；新增本批 P-030 行。
  - [PROGRESS §3.34.9](PROGRESS.md)：补批次总结报告交付物（`83a27aa` → CI `43832206129`）。
  - [CHANGELOG](CHANGELOG.md)：`[Unreleased] Changed` 追加 P-030 条目。
- **历史零改写**: §3.34（P-029 Step 1 记录）中「U-P027-1 转 in-progress」保留原文（当时事实）。
- **门禁（纯文档批）**: 全量 `pytest -q` **722 passed** / mypy **37 files 0 error** / black **118 unchanged**（零 Python 改动，与 P-029 终态持平）。
- **结论**: 台账恢复单一事实源——P-029 的承接链（U-P027-1 → P-029 → done）与新增未决项（U-P029-2）各自可追；U 表 pending **22 → 23**（U-P029-2 新增，U-P027-1 由 in-progress 转 done）。

### 3.36 P-031（StrategyEngine 订单簿与估值时序）Step 1 记录（2026-11-16）

- **触发**: U-P029-2（P-029 登记「`_next_day_orders` 无过期 / 无再平衡撤销 / 无卖量夹紧」）；P-030 待办分析核出 P-014 三层防线未下沉 `agents/`；用户 2026-11-16 裁决「立项 P-031 全量」。
- **探针（3 脚本，仓库外 `%TEMP%`）**: `p031_step1_probe.py`（S1 信号剔除 / S2 买单重复 / S3 卖单重复）、`probe2.py`（S0 最小换手复现 / C1 退出单 / C2 超卖）、`probe3.py`（R1 NAV 根因追踪 / R2 超卖账目）。
- **四项实证**:
  - **R2（P1）退出单缺失**：持仓 1000 股、target_weights 仅含他股 → 卖出单 **0** 张；默认 `optimizer=equal_weight`（只返回入选标的）即触发。
  - **R4（P1）超卖虚增现金**：100 股 + 3 张各 100 股卖单 → 3 笔成交、持仓静默钳制 0、现金 `9,999,000 → 10,002,000`（应 +1,000）、NAV 虚增 2,000。
  - **R1（P2）自激换手**：1 股 / 常量价 / 恒定 100% 目标 / 10 日 → **9 笔**（应 1 笔）；根因读数 `cash=0 / mkt_val=0 / NAV_used=0`（买入日再平衡，`market_value` 待日终才写）。
  - **R3（P2）失败单重复累积**：开盘价缺失 6 日 → 队列 **7 张**同向买单，恢复日集中成交 **7,000,000 股**（7× 目标）。
  - **O1（观察）**: `update_market_values` 仅更新 `quantity > 0`，`direction="both"` 空头市值恒 0。
- **负向发现（已排除）**: V2 不受影响——`engine_v2` 已用 `compute_portfolio_value` + `build_target_positions`（含调出清仓项）且在再平衡前撤销在途单；`G1.json` 在 `daily` 下仅 **4 笔**（买入 2 + 末日清仓 2）、NAV 恒 10,000,000，反证 V2 估值路径正确。
- **文档**: [RESEARCH_p031](RESEARCH_p031_strategy_engine_order_accounting.md)（§3 四项缺陷 + 代码位置 / §4 复现矩阵 / §5 探针读数 / §7 方案矩阵 M-A/M-B/M-C 选 **M-A** 对齐 V2 语义 / §8 风险四元块 / §9 负向发现 / §10 Step 2 复核重点）；§1.4 新增 P-031 行（P1）、U-P029-2 转 in-progress。
- **下一 Step**: **Step 2 独立 Review（异构基座）**——重点：四组读数重放、C1/C2 组件探针等价性、M-A 的 `value_buffer=0.985` 口径漂移、O1 是否升格、short/both 方向的同形影响。
- **提交与 CI**: 提交 `a97ba1b`（2 文件 +253/−2，docs-only）→ CI run `43846628720` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）；回填 `fae43ce` → CI `43847032840` **success**。

### 3.36.1 P-031 Step 2 异构 Review 记录（2026-11-16）

- **基座**: GLM-5.3-Flash（≠ RESEARCH 作者 DeepSeek-V4.1-Flash），复审对象 `a97ba1b`，复审时点 HEAD `fae43ce`；记录见 [RESEARCH_p031 §11](RESEARCH_p031_strategy_engine_order_accounting.md)。
- **E1 代码锚点重放**: 十项全一致（`_generate_orders` 遍历面 / EqualWeightOptimizer 输出 / tracker 现金先入账 / BUY 不维护 market_value / 盯市只更新多头 / 默认配置 / `_next_day_orders` 生命周期 / 测试盲区 grep 0 命中）；本基座补证 **executor 无持仓校验**（[execution.py](../core/execution.py) 仅价格检查，SELL 无持仓照常成交）与 **README L310-316 示例调用不存在的 `register_agent` API**（幻觉残留，观察）。
- **E2 探针重放**: 三脚本重跑，六组读数逐字一致（S0 9 笔 / C1 卖出单 0 / C2 cash +3,000 / R1 `NAV_used=0` / S2 7 张→7,000,000 股 / S1 污染声明成立）；S3 作者运行被截断、本基座完整跑通（期末 1,553,200 股，与机制一致）。
- **E3 独立探针（复审基座自编 `p031_step2_review_probe.py`）**: **N1**——中性策略 8 日空头腿 SELL 成交 7 笔、期末持仓 0 股、cash 10M → **90M**、NAV **+1,212.5%** 幻影收益 → R4 在 `direction="both"` 下**常态触发**；**N2**——`build_target_positions` 对负权重抛 `ValueError` → **M-A 的 B1 直用方案与中性策略不兼容**。
- **E4 负向发现复核**: §9 四项全部成立（V2 估值路径读码 / G1 4 笔 NAV 恒定 / P-014 防线 / golden 不涉及）。
- **五项复核重点裁决**: 读数一致 ✓；C1/C2 组件探针**等价** ✓；`value_buffer=0.985` 可接受须显式化（次级，负权重才是主要口径问题）；O1 **维持观察**（N1 实证负持仓前提不可达，真问题是幻影现金）；short/both 同形——R2 成立、R4 升级常态，`direction="short"` 语义歧义登记观察。
- **发现分级**: **0 P0 / 0 P1 / 2 P2（当轮回写）/ 0 P3 + 3 观察**——F-S2-P031-1（M-A 负权重不兼容，回写 §7）/ F-S2-P031-2（R4 影响面失实：中性常态触发，回写 §0/§3/§4）；O-S2-P031-1（short 语义歧义）/ O-S2-P031-2（S3 截断留档）/ O-S2-P031-3（README 幻觉示例，候选 T3）。
- **结论**: **Step 2 pass**。下一 **Step 3 DESIGN** 必须先裁决：① 多头/中性路径拆分与空头腿账目语义；② R4 修复位置（执行侧夹紧 vs `core/tracker.py` 现金守卫——V2 共用 tracker，须保 golden 零重录）；③ `value_buffer=0.985` 是否沿用；④ O1/short 语义澄清是否并入。
- **提交与 CI**: 提交 `ef5438e`（2 文件 +98/−4，docs-only）→ CI run `43848605214` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）；回填 `bf4a71b` → CI `43848935480` **success**。

### 3.36.2 P-031 Step 3 DESIGN 记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash（= RESEARCH 作者，Step 3 允许；Step 4 须异构），基线 HEAD `bf4a71b`；[DESIGN_p031](DESIGN_p031_strategy_engine_order_accounting.md) 完稿（D1-D7 / I1-I8 / V1-V6 / R-P031-1~4 / U-P031-1~3 / O-P031-1~3 / B1-B5 回退点）。
- **四项必答裁决**:
  1. **中性账目（F-S2-P031-1）**：比较四案后选 **C——空头腿显式禁用**（`_execute_neutral_rebalance` 只合并多头腿 + `neutral_short_leg_skipped` 计数 + `__init__` 一条 warning + `_generate_results().additional_info.neutral_short_leg="unsupported"`）。拒绝完整做空（需改 `core/tracker.py`/`execution.py`，波及 golden）与 fail-fast（会连带打断 `MultiStrategyEngine` 的 long/short 两腿）；如实披露「中性退化为多头单边」，登记 U-P031-1。
  2. **R4 修复位置**：选**执行侧夹紧**（`_execute_next_day_orders` SELL 前 `qty=min(order.quantity, max(held,0))`，0 则 `oversell_blocked`、部分则 `oversell_trimmed` 重建订单）；**`core/tracker.py` 零改动**（被 V2/V3/golden 共用，现金语义变更风险不可控），登记 O-P031-1。
  3. **`value_buffer=0.985`**：**采纳**（对齐 V2 单一语义；买入量降 1.5% 属可解释口径统一）；`round_lot` 改为跟随 `base_cfg.optimizer.round_lot`（默认 True，行为一致）；风险登记 R-P031-1。
  4. **O1 / short 语义**：**不并入**——O1 前提不可达（N1 证实负持仓恒 0，真病是幻影现金），`direction="short"` 属产品定义未定，分别登记 O-P031-1 / U-P031-3。
- **关键设计约束**：`_execute_next_day_orders` 存在**双调用路径**（`_process_trading_day` 与多策略自建循环 L726-740 / L84x）→ 撤销/过期/夹紧必须落在**被调函数内部**（F-D3-P031-1）；`additional_info` 写进 `_generate_results()` 而非 `run()`（多策略循环直接调前者，L786 / L928）。
- **批量切分**: B1 中性禁用（前置，保非负权重前提）→ B2 目标持仓（`compute_portfolio_value` + `build_target_positions`，修 R1+R2）→ B3 卖量夹紧（R4）→ B4 撤销+过期（R3）→ B5 门禁与文档；B1 必须先于 B2，B3/B4 独立。
- **不变式/契约**: I1-I8（清仓单必生成 / 现金守恒 / NAV 价格重算 / 在途单有界 / 签名零变更 / core+golden 零改动 / 中性显式 / 门禁）+ V1-V6 六用例（V6 正常路径回归保护）。
- **设计期发现**: F-D3-P031-1（双调用路径，P3，已内化为 D4/D6）；F-D3-P031-2（`run()` 末尾 `_next_day_orders` 残单不清理，观察）；F-D3-P031-3（`MultiStrategyEngine` L918 直写 `tracker.cash`，观察 O-P031-2）。
- **下一 Step**: **Step 4 独立 Review（异构基座）**——重点：D2 最小诚实解权衡 / D3 拒绝改 tracker 的理由需实证 / 0.985 与 round_lot 口径变更披露 / 撤销范围与半衰期适用性 / B1→B2 顺序 / 5 个新计数键命名口径。
- **提交与 CI**: 提交 `af198bc`（2 文件 +288/−2，docs-only）→ CI run `43849761573` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.36.3 P-031 Step 4 异构 Review 记录（2026-11-16）

- **复审基座**: GLM-5.3-Flash（≠ DESIGN 作者 DeepSeek-V4.1-Flash，RULE-5 合规）；复审对象 `af198bc` 提交版，复审时点 HEAD `d0ae37b`。
- **E1 机械复核五锚点**: ① `_process_pending_orders`（agents L442-483）无卖量夹紧且为**默认主路径**（config L375）——D3 盲区；② 多策略循环 L751/L882 调 `_execute_rebalance` **无 try**——D1 的 `ValueError` 会杀死整个回测；③ `adjustment_type` 默认 forward（config L355）vs V2 raw——价格基准既有差异；④ `cancel_orders`/`mark_expired` 存在（pending.py L437/L404）——D4 双载体前提成立；⑤ D6 表「5 键」与 D1 新键未同步。
- **E2 独立探针两项**（`p031_step4_review_probe.py`，%TEMP%）: **Q1** queue 路径 3 张 SELL → 3 笔全成交、cash 9,999,000→10,002,000（**虚增 2,000**）、`oversell_*` 计数 0——默认主路径 R4 仍可达；**Q2** `cancel_orders(stock, date)`/`mark_expired(date)` 均命中。
- **发现分级**: **0 P0/P1，3 P2 + 1 P3 当轮回写，3 观察**——F-S4-P031-1（P2，D3/D4 仅覆盖次日路径，默认主路径 queue 无夹紧无撤销）/ F-S4-P031-2（P2，D1 未定义 nav≤0，`build_target_positions` 抛 `ValueError` × 多策略循环无 try）/ F-S4-P031-4（P2，D2 未定义禁用空头腿后资金部署——`long_weight=0.5` 永久闲置 50% 现金未披露）/ F-S4-P031-3（P3，`orders_missing_price` 触发面变更，P-029 V4 回归面）；观察 O-S4-P031-1/2/3（failure_counts 语义混载 / 价格基准差异 / D3 理由精化）。
- **当轮回写 11 处**: D1 补 nav 守卫（新键 `rebalance_nav_invalid`）+ 触发面注记 / D2 补资金部署子裁决（采纳 (a) 维持 `long_weights * long_weight` 半仓 + 双重披露，拒绝重归一化）+ `short_optimizer` 删除 / D3 落点改双路径夹紧 + 理由精化注记 / D4 落点 1 改双载体撤销 / D6 表 5→6 键 / V6 断言 5→6 / §4.3 双载体注记 / 新增 §4.7（queue 夹紧）/ §7 登记 U-P031-4 / 新增 §11 当轮回写导读 + §12 复审记录。
- **六项复核重点裁决**: ① D2 维持 C 案但补资金部署子裁决 ② D3 拒绝改 tracker 的真实依据精化为 T1 范围纪律（非「必然破坏 golden」）③ 0.985+round_lot 披露充分、连带发现触发面变更 ④ D4 语义同源成立但须双载体 ⑤ B1→B2 顺序「成立且加强」（B2 单独落地杀死整个多策略回测）⑥ 键命名风格一致、语义混载登记观察。
- **结论**: **pass**——Step 5 IMPL 前置条件 4 项（回写后 D1-D4 / 6 键口径 / Step 9 实证 V4 回归面 / V6 六键断言）。
- **提交与 CI**: 提交 `f879d67`（2 文件 +116/−9，docs-only）→ CI run `43853333069` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.36.4 P-031 Step 5 IMPL 记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash（= DESIGN 作者；Step 6 实施 Review 可同基座自查，RULE-5 终审仍在 Step 10）；基线 HEAD `96bed8d`；[IMPL_p031](IMPL_p031_strategy_engine_order_accounting.md) 完稿（§1 范围六前提 / §2 B1-B5 + 9 测试实例 / §3 顺序与依赖 / §4 逐函数锚点规格 / §5 V1-V6+V2b / §6 fixture 6 项 / §7 低效排除 7 项 / §8 接口回退点 9 项 / §9 实施期发现 7 项 / §10 Step 6 复核重点 6 项）。
- **批次与用例**: B1 中性禁用（V5）→ B2 估值/目标持仓（V1/V2/V2b）→ B3 双路径夹紧（V3×2）→ B4 双载体撤销+过期（V4×2 / V6）→ B5 门禁文档；**9 实例** → 目标 pytest **731**、测试文件 **82**、black **119**。
- **七项实施期发现**:
  1. **F-I-P031-1（P3）** 过期过滤置于开盘价切片**之后**（DESIGN §4.2 原为之前）——P-029 V5 fixture 用 `object()` 占位订单，前置会 `AttributeError`；改后既有回归面零改动，代价仅为退化日推迟一天过期（有界）。
  2. **F-I-P031-2（P3）** 队列路径不能用 `execute_pending_order`（固定取 `order.quantity`）→ 改直调 `execute_order(..., qty, ...)`（与 V2 L815 同形）；`order.quantity` 不改写，`filled_qty` 与 V2 同期口径。
  3. **F-I-P031-7（P3）** DESIGN V2 期望「成交 1 笔」在**默认成本**下不可达（0.985 缓冲 + 费用 → 稳态每日整手往返微调）→ V2/V3 改用**零成本配置**；旧实现在零成本下仍为 9 笔清仓-重建，判别力保留。
  4. F-I-P031-3/4/5/6（观察）：`np.isfinite` 替代 `math.isfinite`；`_generate_rebalance_orders` 改收 `TargetPosition`（旧临时 dict 无第二消费者）；双载体按 DESIGN 而非 V2 的 `elif`；净行数待实测。
- **覆盖补充**: **V2b**（nav≤0 守卫）——DESIGN V1-V6 未单列 F-S4-P031-2 的可验证出口。
- **关键约束落到规格**: 双路径夹紧逐字同形 / 撤销在信号索引早退后且 tradable 之前 / `neutral_short_leg_skipped` 必须在 `optimize` 成功之后（否则污染 test_p027 精确断言）/ 既有 `except Exception` 恒 22（D1 新增的是 `except (KeyError, IndexError)`）。
- **下一 Step**: **Step 6 实施 Review**——六项复核重点（双路径一致性 / 撤销时序 / domain 遍历开销 / 中性计数位置 / nav 守卫分支可达性 / P-029 V4-V5 回归面实证）。
- **提交与 CI**: 提交 `0219047`（2 文件 +425/−1，docs-only）→ CI run `43854958855` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.36.5 P-031 Step 6 实施 Review 记录（2026-11-16）

- **复审基座**: GLM-5.3-Flash（≠ IMPL 作者 DeepSeek-V4.1-Flash——强于「同基座自查」原口径，RULE-5 精神提前兑现，终审仍留 Step 10）；复审对象 `0219047`，复审时点 HEAD `4278179`。
- **E1 锚点机械复核十二项全命中**: 9 函数起止行号 / import 区 L29-38 / 早退 L203-204 与 daily_signal L207 / short_optimizer L271-279 与替换面 L292-302 / queue `execute_pending_order` L475 / V2 五组锚点（L671-688 / L792 / L815 / L911-917 / L1063-1079）/ core 四签名（`cancel_order` L355 / `is_expired` L202 / `execute_order` L262 / `execute_pending_order` 固定 `order.quantity` L407-414）/ config L375-377 / 多策略循环四调用点 / `build_target_positions` 双拒 L76-80 / 测试实例化面（仅 p027+p029）。
- **E2 门禁基线独立复测四项一致**: pytest 收集 **722** / black **118 files unchanged** / mypy **37 source files no issues** / tests .py **81**——IMPL §1 基线声明全部实证。
- **E3 探针两项**（`p031_s6_review_probe.py`，%TEMP%）: nav 守卫形态 `not np.isfinite(nav) or nav <= 0` 对 nan/inf/-inf/0/-1 全触发、10.0 通过（§10 复核点 #5 成立）；`is_expired` 阈值 BUY@6日 True / **SELL@6日 False**（6<10 且 vitality 0.25>0.125）/ SELL@10日 True（**F-S6-P031-1 实锤**）。
- **六项复核重点裁决（IMPL §10）全过**: ① 双路径同形成立（差异两处均有裁决）② 撤销时序正确（早退后、daily_signal 前）③ domain 遍历与 V2 L913-915 同构、`cancel_orders` O(1) 早退无可观测开销 ④ 中性计数在 optimize 成功之后（test_p027 精确断言保真）⑤ nav 守卫探针实证 ⑥ P-029 V4/V5 回归面静态实证（`_MissingPriceFrame`/`object()` 占位单/ZZZ 缺价三形态逐一对表）。
- **发现分级**: **0 P0/P1/P2，1 P3 当轮回写，3 观察**——F-S6-P031-1（P3）V4② 构造未指定订单方向，SELL 单 6 日不满足任一过期条件 → 测试假红；已回写 §5 V4（显式 BUY ≥6 自然日）+ §6 F6。观察：O-S6-P031-1（DESIGN 伪代码「重建订单」vs IMPL「直调 execute_order(qty)」成交语义等价，重试簿记差异由再夹紧兜底）/ O-S6-P031-2（次日过期单无 `mark_expired` 状态迁移，agents 本地簿无消费者，V2 有迁移属观感差异）/ O-S6-P031-3（queue 路径价格仅成员检查无有效性校验——既有行为且 V2 同款，候选后续批）。
- **结论**: **pass**——Step 7 前置条件 3 项（9 实例口径 / 六组零预填引用 §13.2 基线 / Step 9 含 V4-V5 回归面实跑终证）。
- **提交与 CI**: 提交 `8d26530`（2 文件 +82/−3，docs-only）→ CI run `43858051695` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.36.6 P-031 Step 7 CHECKLIST 记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash（= 四文档同源）→ Step 8 一致性 Review 须异构；基线 HEAD `6a7771e`；[CHECKLIST_p031](CHECKLIST_p031_strategy_engine_order_accounting.md) 完稿（六组 A-F / 46 项 / 每项 DoR-DoD + 证据出口 + 锚点 + 实测列）。
- **基线四项独立实测**（`MPLBACKEND=Agg` + Python312）: 全量 `pytest -q` **722 passed**（172 warnings）/ `tests/` .py **81**（78 `test_*.py` + 3 辅助）/ `black --check core tests` **118 unchanged** / `mypy --explicit-package-bases core` **37 files 0 error**；另 `tests/golden/` **7** 份 json（13 条用例）、`except Exception` **22**。
- **目标读数**: **731 passed** / 测试文件 **82** / black **119** / mypy **37 files 0** / golden **13 零重录** / `except Exception` 恒 **22**。
- **分组与覆盖**: A 中性禁用 6（D2/V5）/ B 估值与目标持仓 8（D1/V1/V2/V2b + P-029 V4 回归面）/ C 双路径夹紧 6（D3/V3×2）/ D 撤销+过期 6（D4/V4×2/V6）/ E 不变式 8（I1-I8 一一对应）/ F 测试门禁治理 12（9 实例 / 红态 / 三段门禁 / golden / fixture 独立 / 快速回归 / CI / 四文档 / 未决登记 / 行号漂移）→ **V 用例 9/9、I 不变式 8/8 全覆盖**。
- **零预填核验**: 46 个验收单元格全为 `[待 Step 9]`；机械匹配 49 = 46 单元格 + 3 处合法字面引用（头部规则行 / §7 计数说明 / 签名表 Step 9 行）；✅ 出现 2 次均为规则说明字面引用，**零预填**。
- **自检修正 1 处**: E5 初稿判据 `^-\s*def ` 命中 0 与 B4 允许的私有方法签名变更（`_generate_rebalance_orders`）冲突 → 收窄为「**公开**三个方法零变更 + 私有变更显式允许」。
- **交接 Step 8 五项**: 9 实例口径三处对拍 / 4 修 1 降级四处口径 / 6 计数键四处对拍 / 两套 V-ID 不得混用（DESIGN-V* 前缀）/ 五处顺序敏感核验（撤销位置、过期位置、计数位置、nav 守卫位置、B1 先于 B2）。
- **下一 Step**: **Step 8 一致性 Review（异构基座 GLM-5.3-Flash）**。
- **提交与 CI**: 提交 `c913243`（2 文件 +162/−1，docs-only）→ CI run `43859690027` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.36.7 P-031 Step 8 一致性 Review 记录（2026-11-16）

- **复审基座**: GLM-5.3-Flash（≠ Step 7 作者 DeepSeek-V4.1-Flash，RULE-5 异构成立）；复审对象 `c913243`（CHECKLIST_p031 提交版），复审时点 HEAD `a126379`。
- **E1 机械校验五项全过**（`p031_step8_check.py`，%TEMP%）: ① 相对链接 3 条 **0 broken** ② ID 闭环 **46 行 / 46 唯一**，分组 A6+B8+C6+D6+E8+F12 与 §7 声称精确一致 ③ 计数自洽（46×10 / 731×4 / 82×3 / 119×4 / 37×4 / 13 零重录×2）④ 零预填 **49 = 46 单元格 + 3 合法字面引用**、✅×2 均为规则字面 ⑤ 角色引用四行齐备。
- **E2 对齐矩阵七项全过**: ① 9 实例三处一致 ② 4 修 1 降级四处一致（RESEARCH R1-R4 / DESIGN §1 表 / IMPL §1 / CHECKLIST F10+A-D 标题）③ 6 计数键 DESIGN-IMPL-CHECKLIST 三文档全含（RESEARCH 无键属预期）④ 731/82/119/37 三处一致且基线与 Step 6 §13.3 同源 ⑤ V-ID：DESIGN 契约 V1-V6 ↔ IMPL 用例 V1-V6+V2b 语义 1:1（V2b 唯一新增）⑥ 顺序敏感五项（撤销 / 过期 / 计数 / nav 守卫 / B1→B2）均已在 IMPL 定稿并被 CHECKLIST 对应行引用 ⑦ 基线-目标读数链无漂移（96bed8d..6a7771e 全 docs-only）。
- **发现分级**: **0 P0/P1/P2，3 P3 当轮处置，3 观察**——F-S8-P031-1（CHECKLIST A2/A6 要求半仓断言但 IMPL §5 V5 未列 → **回写 IMPL §5 V5** 补「买入名义 ≈ 0.5 × nav × 0.985」）/ F-S8-P031-2（CHECKLIST E5 引用 AST 扫描但 IMPL 无命令 → **回写 IMPL §11** 增补 I1 AST 计数行，复用 IMPL_p029 §6 十文件命令）/ F-S8-P031-3（CHECKLIST B4 锚点「V2 语义」违反 §8.2 自立 DESIGN-V* 规则 → **当轮修正**为 DESIGN-V2）；观察 O-S8-P031-1（F1「函数数 ≤ 7」为估算上限）/ O-S8-P031-2（半仓断言实现方式未钉死，Step 9 自由）/ O-S8-P031-3（头注代码面一致性确认成立）。
- **结论**: **pass**——四文档口径闭环，46 项验收可执行；Step 9 前置条件 3 项（V5 回写后断言 / §11 含 AST 行 / 五处顺序敏感留证 + V6 红态豁免标注）。
- **下一 Step**: **Step 9 TDD 实施**（B1-B4 四批红绿 + B5 门禁文档）。
- **提交与 CI**: 提交 `3c2e3de`（3 文件 +62/−4，docs-only）→ CI run `43861365698` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.36.8 P-031 Step 9 TDD 实施记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash（= 四文档同源）；起点 HEAD `a126379`；[IMPL_p031 §11](IMPL_p031_strategy_engine_order_accounting.md) 实施记录 + [CHECKLIST_p031](CHECKLIST_p031_strategy_engine_order_accounting.md) **46/46 ✅** 回填。
- **逐批红→绿**（每批先取红态断言失败再实施）: **B1** D2 中性腿禁用 → V5 红 `1 failed`（缺 "unsupported" WARNING）→ 绿 `1 passed`；**B2** D1 估值/目标持仓 → V1/V2/V2b 红 `3 failed`（V1 sells 期望 1 实 0；V2 期望 1 实 **9 笔**，与 RESEARCH R1 读数逐字一致；V2b 守卫未触发）→ 绿 `4 passed`；**B3** D3 双路径夹紧 → V3×2 红 `2 failed`（两路径各 3 笔全成交，cash 虚增 2,000）→ 绿 `6 passed`；**B4** D4 双载体撤销 + 过期 → V4①/V4② 红 `2 failed`（V6 红态即通过 = 回归保护，显式标注不伪造红态）→ 绿 **`9 passed`**。
- **代码变更**（`agents/multi_strategy_engine.py` 单文件 **+133/−83**）: D1 `_generate_orders` 改 `compute_portfolio_value` 价格重算 + `build_target_positions` 目标并集（含 `rebalance_nav_invalid` 守卫）；D2 构造期 WARNING + `_execute_neutral_rebalance` 删空头腿并计 `neutral_short_leg_skipped`；D3 `_clamp_sell_quantity` 在 `_execute_next_day_orders` 与 `_process_pending_orders` 双路径同形夹紧；D4 `_execute_rebalance` 双载体撤销（`_next_day_orders` 过滤 + `pending_queue.cancel_orders`）+ 次日路径过期过滤（置于开盘价切片之后，保 P-029 V5）；`_generate_results` 增 `additional_info.neutral_short_leg`。
- **新测试**: `tests/test_p031_strategy_engine_accounting.py`（≈270 行，独立 fixture 不改 test_p027/test_p029；8 个 `def test_`，V3 双路径参数化 → **9 实例**）。
- **门禁终态**: pytest **731 passed**（722+9，172 warnings，42.70s）/ tests .py **82** / `black --check core tests` **119 unchanged** / `mypy --explicit-package-bases core` **37 files 0 error** / golden+p027+p029 **48 passed**（13+24+11，golden **13 零重录**）/ AST `except Exception` 恒 **22** / `git status --short core tests/golden` 空 / 公开签名零变更（唯一 `-def` 为私有 `_generate_rebalance_orders`，允许项）。
- **顺序敏感五项留证**: 撤销位置（早退后、`daily_signal` 前）/ 过期位置（开盘价切片后）/ 计数位置（各 except 首行）/ nav 守卫位置（`compute_portfolio_value` 之后、`build_target_positions` 之前）/ B1 先于 B2（D2 先行避免中性腿空头权重触发 `build_target_positions` 拒负权重）。
- **实施期发现 3 项（均 P3）**: F-S9-P031-1 CHECKLIST D4 原判据「`mark_expired` 仅 1 处」实为 **2 调用 + 1 注释**（L176 / L528 / L407），当轮修正；F-S9-P031-2 新测试文件 black 首轮 reformatted（`black --check` 失败 → 格式化后 119 unchanged）；F-S9-P031-3 V6 红态即通过（回归保护用例，红绿纪律显式豁免并留证）。
- **文档回填**: CHECKLIST 46/46 全 ✅ + 头部状态 + §7 零预填说明 + 签字表 Step 9 行；IMPL §11（11.1 红绿读数 / 11.2 门禁 / 11.3 行号漂移 11 项 / 11.4 顺序敏感五项 / 11.5 残留检查 / 11.6 实施期发现）；README 4 处 + ARCHITECTURE L3 同步 731/82。
- **下一 Step**: **Step 10 ADD 审计 + RULE-5 异构终审**（须 GLM-5.3-Flash ≠ 作者基座）。
- **提交与 CI**: 提交 `750674e`（8 文件 **+541/−147**：代码 1 + 测试 1 + 文档 6）→ CI run `43864133531` **success**（3.10 2m0s / 3.11 1m29s / 3.12 1m37s，EXIT=0）。

### 3.36.9 P-031 Step 10 ADD 审计 + RULE-5 异构终审记录（2026-11-16）

- **审计基座**: **GLM-5.3-Flash**（≠ 四文档作者 DeepSeek-V4.1-Flash，RULE-5 异构成立）——审计与终审合并一轮（同 P-029 先例）；审计对象区间 `6a7771e..780197c`（6 提交，代码面集中于 `750674e`）；审计时点 HEAD `780197c`。
- **Phase 0 spec 质量门**: **5/5 = Tier A**（可测试约束 / 模块映射 / 接口契约 / 修正项 / 跨模块契约，DESIGN_p031 五维全满分）。
- **Phase 1 完整性**: 8 文件 **+714/−98**；代码 `agents/multi_strategy_engine.py` **+133/−83** + 测试 **+272**；6 计数键 **8 站点**逐行命中；新增日志仅 **+1**（init warning，D6 口径）；新增 `raise` **0**；零改动面（core / golden / filter / scripts / cli / pyproject）区间名单**零命中**。
- **Phase 2 保真度**: IMPL §4.1-4.9 九函数独立读码逐项 **pass**（撤销/过期/计数/nav 守卫四处顺序敏感行号序逐项复核；漂移表 11 项 def 行号全命中；签名零变更——唯一 `-def` 为私有 `_generate_rebalance_orders`）。
- **Phase 3 必要性**: 代码 diff **11 hunk** 与 IMPL §4 + D1-D7 逐一归因，**零游离行**。
- **Phase 4 语义/生命周期**: 超卖（生成侧不可超卖 + 执行侧兜底陈旧单，纵深防御）/ 撤销（先撤销后生成，无自撤销）/ 过期（`is_expired` 复用，退化日推迟一天有界）/ NAV 时序（守卫拦截 nan/±inf/0/负不入无 try 循环）/ 中性降级（半仓 + 双重披露）五面裁决全过。
- **E1-E5 门禁独立复跑**（本基座全量重跑，不采信 Step 9 自报）: pytest **731 passed**（172 warnings，43.66s）/ 新测试 collect **9**（`def test_` 8）/ black **119 unchanged** / mypy **37 files 0** / golden+p027+p029 **48 passed** / tests .py **82** / I1 AST **22** / 零改动面空。
- **盲区扫描**: agents/ handlers=22，严格启发 silent=2（`research_team_v2.py:27` P-029 登记点 + `agent_framework.py:1543` demo 入口 print+traceback 可观测、P-027 登记零改动面 `:1529` 行号漂移）——均早于本批且已登记；P-031 **零新增静默路径**（6 新计数站点全带 `_record_failure`，typed except 不计入 I1）。
- **发现分级**: **0 P0/P1/P2 + 1 P3 当轮修正 + 2 观察**——**F-R5-P031-1**（P3：IMPL §11.2「新测试文件 +270（未计入 numstat）」与提交后实测 **+272** 不符且原注记前提失效 → 当轮修正该单元格）/ O-R5-P031-1（PROGRESS「≈270 行」为约数，历史记录不回改）/ O-R5-P031-2（盲区 silent 读数为定义依赖，P-029「silent=1」与本轮「silent=2」差异已对账登记）。
- **结论**: **pass**——**P-031 批次关闭**；U-P031-1~4 与 O-P031-1~3 随批次归档，触发条件不变。完整记录见 [CHECKLIST_p031 §11](CHECKLIST_p031_strategy_engine_order_accounting.md)。
- **提交与 CI**: 提交 `c1fed32`（3 文件 +123/−4，docs-only，含 F-R5-P031-1 当轮修正）→ CI run `43867147356` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。
- **交付物**: 批次总结报告 [SUMMARY_p031](SUMMARY_p031_strategy_engine_order_accounting.md)（§1-§10 全景：缺陷谱系与治理链、四层防线落点、9 实例红绿与门禁、15 项发现台账、20 提交链 + 11 CI、边界遗留与启示）——批次归档收口；提交 `a34afa8` → CI run `43879483152` **success**。

---

## 3.37 P-032（台账收口 + 文档幻觉修正）T3 轻批记录（2026-11-16）

- **触发**: P-031 关闭后待办分析三项：① §1.4 U-P029-2 状态滞后（仍 `in-progress`，实际已关闭——与 P-030 修过的 U-P027-1 同型）；② U-P031-1~4 未建台账行（P-030 教训：散落正文会漏跟踪）；③ O-P031-3 实测复验仍成立——README L314-315 对 `MultiStrategyEngine` 调用 `register_agent`（该方法仅存在于 `MultiAgentBacktestEngine`，agent_framework L1213），且 `MultiStrategyEngine` 无 `run()`（仅 `run_sequential` L658 / `run_parallel` L686 / `run_vectorized` L721）——**示例双重幻觉**。
- **处置（4 项）**: ① U-P029-2 → **done**（P-031 承接：四缺陷修复 + 防线下沉 + 722→731）；② §1.4 新增 **U-P031-1~4** 四行（P2×1 + P3×3，触发条件各自独立）；③ README Multi-Agent 示例改 `MultiAgentBacktestEngine`（`register_agent` / `setup` / `run` 真实链）+ 补 `MultiStrategyEngine` 真实 API 注记——**O-P031-3 关闭**；④ CHANGELOG `[Unreleased] Changed` 追加本批条目。
- **门禁**: 零代码、零测试、零门禁变更——全量 `pytest -q` **731 passed** 持平 / `black --check core tests` **119 unchanged** / `mypy --explicit-package-bases core` **37 files 0**。
- **遗留**: 下一 T1 候选为 **O-S6-P031-3**（queue 路径价格有效性校验，NaN/非正透传，V2 L799-808 同样无校验——需 Step 1 探针定级是否双引擎同修）；U-P031-1~4 条件触发类挂起。
- **提交与 CI**: 提交 `dde5485`（3 文件 +23/−3，docs-only）→ CI run `43883325472` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。
- **独立复审（同基座，RULE-5 披露）**: P-032 作者与复审者**同为 GLM-5.3-Flash**（本会话），异构条件不成立——按 P-027 两段式先例执行**同基座独立复审**，真异构终审预留 **U-P032-1**（须非 GLM 基座）。复审五项全过：**E1** README API 签名实证（`MultiAgentBacktestEngine.__init__(base_config: BacktestConfig)` / `register_agent(agent: BaseAgent)` / `GuruAgentV2(guru_id: str, ...)` 均命中；`MultiStrategyEngine` 确无 `run` 与 `register_agent`——原「双重幻觉」判定与修正方向均成立）/ **E2** PROGRESS 结构（`## 4. 审查记录` ×1 / `提交后回填` 残留 **0** / §3.37 ×1 / 新增五行均 5 列齐）/ **E3** CHANGELOG 落位（`Changed` 首条 L46，口径与 §3.37 一致）/ **E4** diff 面精确（`dde5485` = 3 文件 +23/−3；`0d7f6b4` 仅 CI 行回填，无越界文件）/ **E5** 门禁复跑（**731 passed** / black **119 unchanged** / mypy **37 files 0**）。**0 缺陷 + 2 观察**——O-P032-1（Multi-Agent 示例引用上例 `config` 变量、块内未定义，与相邻示例风格一致，不处置）/ O-P032-2（SUMMARY_p031 §9.2 为冻结归档，O-P031-3 关闭状态以本节为准，不回改历史）。复审记录提交 `92322d6` → CI run `43885297784` **success**。
- **异构终审（DeepSeek-V4.1-Flash，U-P032-1 关闭）**: 复审基座 **DeepSeek-V4.1-Flash ≠ P-032 作者 GLM-5.3-Flash**，RULE-5 成立（P-027 两段式第二段）。五项复核全过：**E1** 运行期 introspection（`MultiAgentBacktestEngine.register_agent / setup / run` 均 True；`MultiStrategyEngine.run` / `register_agent` 均 **False**——README 修正方向与「双重幻觉」判定成立）/ **E2** 结构（`## 4. 审查记录` ×1 / §3.37 ×1 / P-032 行 5 列 / U-P031-1~4 均 5 列）/ **E3** CHANGELOG `Changed` 首条 L46 / **E4** diff（`dde5485` 3 文件 +23/−3、`92322d6` 1 文件 +3/−1、`8d66787` 1 文件 +1/−1，无越界文件）/ **E5** 门禁本基座独立复跑 **731 passed / black 119 unchanged / mypy 37 files 0**。**0 缺陷 + 1 观察**（O-R5-P032-1：§3.37 同基座复审段「异构终审预留」表述已由本节接续，历史不回改）。

---

## 3.38 P-033（待执行订单价格有效性）Step 1 取证记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash；基线 HEAD `8d66787`；上游 **O-S6-P031-3**（P-031 Step 6 观察，P-032 待办分析列为下一 T1 候选）。
- **取证方法**: 静态读码（两引擎 queue/next-day 四条路径 + `execute_order` + `Tracker.execute_trade`）+ 独立探针 `%TEMP%\p033_step1_probe.py`（**10 场景**：agents/V2 × queue/next-day × NaN/0/默认成本/负值/inf/close=0），仓库外运行。
- **缺陷定级**: **R1（P1）** 开盘价 `NaN`/`±inf` → `execute_order` 无守卫 → `Trade(price/amount=NaN)` → `PositionTracker.execute_trade` 把 **cash 永久置 NaN** → NAV 全 NaN → P-031 nav 守卫逐日 `rebalance_nav_invalid`、组合静默冻结、指标 NaN（不可恢复）；**R2（P2）** 开盘价 `0` → **免费持仓**（零成本 0 元 100 股，默认成本仅付 `commission_min=5`）、`-5` → **现金 +500**（BUY 负价反向入账）；**R3（P3）** `close=0` 因 numpy 除零返回 `inf` 仅告警，无账目污染。
- **负向发现 6 项**: N1 次日路径**两引擎均已完整防护**（对照组 `n_trades=0 / retained=1`）→ 缺陷严格限于 queue；N2 `close=0` 不抛 `ZeroDivisionError`；N3 全仓 37 处 `execute_order` 调用**零** 0/NaN/负价入参（测试破坏面 0）；N4 V2 fallback 经 `execute_pending_order` 委托 `execute_order`，单点守卫可覆盖；N5 非 P-031 回归（前后同构）；N6 `update_market_values` 已跳过 NaN 价，污染源在 `execute_trade`。
- **方案矩阵**: 选 **M-A**——`core/execution.py::execute_order` 入口单点守卫（`None/NaN/±inf/<=0` → warning + `return False, None`）+ 两引擎 queue 路径显式计量（agents 新键 / V2 复用 `skipped_price`）；`False` 返回在 5 个调用点的既有语义均为「保留重试」，无需改调用方。
- **范围**: **T1**（`core/execution.py` + `core/engine_v2.py` + `agents/multi_strategy_engine.py`）；`tracker` 与 `PendingOrderQueue` 零改动；golden 13 条全为合法价，预期零重录。
- **遗留**: Step 2 须评估 0 价拒绝后的长期重试噪声（`mark_expired` 兜底时效）与 R3/VWAP NaN 是否同批；U-P031-2（BUY 现金夹紧）与 U-P014-3 仍独立挂起。
- **下一 Step**: **Step 2 异构 Review**（须 GLM-5.3-Flash ≠ 本文件作者 DeepSeek-V4.1-Flash）。
- **提交与 CI**: 提交 `839f5b5`（2 文件 **+229/−1**：RESEARCH 新建 + PROGRESS §1.4/§3.37/§3.38）→ CI run `43887581920` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.38.1 P-033 Step 2 异构 Review 记录（2026-11-16）

- **复审基座**: **GLM-5.3-Flash**（≠ RESEARCH 作者 DeepSeek-V4.1-Flash，RULE-5 成立）；复审对象 `839f5b5`（RESEARCH_p033 提交版）；复审时点 HEAD `0615a6c`。
- **E1 锚点重放**: 七锚点全命中（agents L451/L505/L520、V2 L799/L815/L1140、execution 零 `isfinite/isna`、tracker L202/234、config L375）；**一处盘点修正**——§6「生产调用点 5 处」实为 **6 直接调用 + 1 委托链**（漏列 `engine_v2.py:1161`），守卫面 **3 有 / 3 无**（agent_framework L1420 上游 L1340 亦仅成员检查）→ F-S2-P033-1 当轮回写。
- **E2 探针重放**: `p033_step1_probe.py` 原样重跑，十场景读数与 RESEARCH §5 **逐字一致**（含 A2b `cash=9999995` / A3 `cash=10000500` / 对照组 `n_trades=0 / retained=1`）。
- **E3 独立探针四项新证**（`p033_step2_review_probe.py`）: **B1** VWAP + NaN OHLV → `success=True, price=NaN`（**第二 NaN 入口实锤**，M-A 单点守卫可覆盖，M-B 则 VWAP 裸奔）/ **B2** SELL queue + NaN（有持仓）→ `cash=NaN, qty=0`（**持仓静默清零** + realized_pnl=NaN，比 BUY 隐蔽）/ **B3** 无效价保留重试 → `mark_expired` 半衰期约 **4 交易日排空**（bounded，无长期噪声）/ **B4** V2 强平 L563 守卫实证（NaN close → `liquidated=0`，持仓保留）。
- **E4 负向发现复核**: N1-N6 全成立；N3 独立 grep **0 hits**；N5 补全细节——P-031 D1 曾删除生成侧逐股 `close_price` 校验（由 `build_target_positions` 无价跳过承接）→ 价格处理全景：生成侧归 `build_target_positions`、执行侧归夹紧、**queue 有效性归本批**。
- **六项裁决**: ① R1 P1 / R2 P2 **维持不合并**（触发与后果可分离，B2 强化 R1）② M-A **维持**（core/ 先例合法；M-B 有 F-S4-P031-1 同型漂移风险且 VWAP 裸奔）③ agents 新键定名 **`pending_invalid_price`** / V2 复用 `skipped_price` ④ 重试噪声 **bounded** ⑤ VWAP 随 M-A 同批覆盖，R3 仅登记 ⑥ 5 调用点 `False` 语义逐一成立（无一处依赖「无效价必成交」）。
- **发现分级**: **0 P0/P1/P2 / 2 P3 当轮回写**（F-S2-P033-1 §6 调用点全表 / F-S2-P033-2 §7 VWAP 实锤）**/ 2 观察**（O-S2-P033-1 SELL 清零形态登记 §3 / O-S2-P033-2 bounded 登记裁决 #4）。
- **结论**: **pass**——准予进入 **Step 3 DESIGN**；前置条件四项（守卫单点 + VWAP 覆盖 / 计量键名 / queue 守卫位置与 next-day 同形 / 测试规格含 B1-B4 形态与零误报）。
- **提交与 CI**: 提交 `c233846`（2 文件 **+105/−11**：RESEARCH §6/§7/§11 回写 + PROGRESS §1.4/§3.38.1）→ CI run `43890214980` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.38.2 P-033 Step 3 DESIGN 记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash（= RESEARCH 作者；Step 4 须异构）。基线 HEAD `d9f821b`；[DESIGN_p033](DESIGN_p033_pending_order_price_validation.md) 完稿（D1-D6 / I1-I7 / V1-V8 / R-P033-1~3 / U-P033-1~3 / O-D-P033-1~2 / B1-B4 回退点）。
- **四项设计决策**:
  - **D1 守卫位置**：`execute_order` 中**解析后**价格（`_get_execution_price` 返回值）而非入参 `open_price`——覆盖 OPEN/CLOSE/VWAP/CUSTOM/未知回退**五分支**（CLOSE 对 `NaN` 不回退 L222、VWAP 聚合 NaN L238、CUSTOM 仅判 `>0` L246）；新增模块级 `is_valid_price`（`None/NaN/±inf/<=0` → False），守卫 warning + `return False, None`，不写 `trade_log`。
  - **D2 双层过滤**：引擎 queue 前置过滤（agents L508 后 → 新键 `pending_invalid_price`；V2 L803 后 → 复用 `skipped_price`）与 D1 共用同一判定函数——executor 层保安全、引擎层保可归因，零重复判定（无 P-031 F-S4 型漂移）。
  - **D3 不重构**：两引擎 next-day（L451/L1140）与 V2 强平（L563）既有 inline 判定保留（D1 下游兜底，双保险）。
  - **D5 不降噪**：Step 2 B3 实测重试 ≤4 交易日排空，warning 频次 bounded。
- **回归面**：D4 七调用点 `False` 语义逐一核对（V2 queue / V2 next-day / V2 强平 / agents 两路径 / agent_framework / fallback 委托）——**无一处依赖「无效价必成交」**。
- **门禁预测**: 731 → **748 passed**（V1 参数 6 + V2 2 + V3 2 + V4 1 + V5 1 + V6 2 + V7 1 + V8 2 = **17 实例**）/ 测试文件 **82 → 83** / black **119 → 120** / mypy **37 files 0** / golden **13 零重录**。
- **设计期发现**: F-D3-P033-1（CLOSE 分支 `close_price=NaN` 不回退 = 第二类「入参合法、解析价无效」，D1 已覆盖）/ F-D3-P033-2（`IExecutionSimulator` 协议无需扩，模块级函数即可）。
- **下一 Step**: **Step 4 异构 Review**（须 GLM-5.3-Flash ≠ 本文件作者 DeepSeek-V4.1-Flash）；复核重点六项（守卫位置 / 双层是否过度 / 引擎预过滤口径 / 计量不对称 / 测试规格 / 门禁推算）。
- **提交与 CI**: 提交 `9d3e4d7`（2 文件 **+258/−1**：DESIGN 新建 + PROGRESS §1.4/§3.38.2）→ CI run `43893100625` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）；本批零代码，门禁持平 **731 passed / black 119 unchanged / mypy 37 files 0**。

### 3.38.3 P-033 Step 4 异构 Review 记录（2026-11-16）

- **复审基座**: **GLM-5.3-Flash**（≠ DESIGN 作者 DeepSeek-V4.1-Flash，RULE-5 成立）；复审对象 `9d3e4d7`（DESIGN_p033 提交版）；复审时点 HEAD `470efea`。
- **E1 锚点机械复核（十项）**: A1-A5/A10 全命中；**三处锚点精化**——§4.1「Trade 之后约 L50」实为 `TradeLog` 类占 L52-150（精确锚点 `ExecutionSimulator` 类前 L152/153）/ §4.2 agents「L508 之后」精化为 **L509 后、L511 夹紧块前** / §4.3 V2「L803 之后」精化为 **L808 后、L810 前**（V2 内部顺序 clamp→成员检查→取价与 agents 不同，既有语义不影响插入）→ F-S4-P033-1 当轮回写。
- **E2 独立探针 C1-C5**（`p033_step4_review_probe.py`）: **C1** CLOSE + close=NaN → `success=True, price=nan`（**F-D3-P033-1 独立复现**，解析后守卫必要性成立）/ **C2** CUSTOM 回调 inf → `success=True, price=inf`（**L246 缺口实锤**）/ **C3** CUSTOM None → 回退 open=10（既有正确基线）/ **C5** 未知类型分支正常构造**不可达**（`__init__` L183 构造期枚举校验）；变异后存在「trade 已入 `trade_log` 但 success=False」既有 quirk（add_trade L330 先于 logger L332，`.value` AttributeError）——理论面登记 O-S4-P033-3 / **C4** `is_valid_price` 语义表（六无效值 False、10.0/1e-9 True）与 V1 矩阵逐一对应。
- **六项裁决**: ① 守卫位置**成立且必要**（C1/C2 实锤入参守卫会漏）② 双层过滤**不冗余**——D1 安全层 + D2 可观测层，共用 `is_valid_price` 无漂移 ③ 预过滤 `open_price` 口径**可接受**（与 next-day 对称优先；非 OPEN 下保守收窄登记 O-S4-P033-1）④ 计量不对称**维持**（V2 无 `_failure_counts` 基础设施，强行对齐 = API 扩张）⑤ 测试规格覆盖**成立**（V4/V5/V7 三新证均有回归锁；V6 断言改 caplog → F-S4-P033-2；R3 无锚点可接受 O-S4-P033-2）⑥ 门禁推算 **748/83/120/37/13 全正确**（black +1 为新测试文件；提醒首轮 black 先行，F-S9-P031-2 先例）。
- **发现分级**: **0 P0/P1/P2 / 2 P3 当轮回写**（F-S4-P033-1 三锚点精化 §4.1-4.3 / F-S4-P033-2 V6 caplog §6，均已回写）**/ 3 观察**（O-S4-P033-1/2/3）。
- **结论**: **pass**——准予进入 **Step 5 IMPL**；前置条件四项（精化锚点 / 单一 `is_valid_price` 来源 / 新测试先 black / V6 caplog + V8 红态标注）。
- **提交与 CI**: 提交 `5c8962b`（2 文件 **+80/−6**：DESIGN §4/§6/§12 回写 + PROGRESS §1.4/§3.38.3）→ CI run `43897106641` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.38.4 P-033 Step 5 IMPL 记录（2026-11-16）

- **作者基座**: DeepSeek-V4.1-Flash（= RESEARCH/DESIGN 同源；Step 6 实施 Review 须异构）。基线 HEAD `013c4d3`；[IMPL_p033](IMPL_p033_pending_order_price_validation.md) 完稿（B1-B4 / §4 逐文件锚点 / §5 V1-V8 / §6 六 fixture / §7 八项低效排除 / §8 回退点 / §9 五项实施期裁决）。
- **精确锚点（Step 4 F-S4-P033-1 落实）**: `is_valid_price` 置 **`TradeLog`（L52-150）与 `ExecutionSimulator`（L153）之间**；agents 过滤块置 **L509（`close_price` 赋值）后、L511 夹紧注释前**；V2 过滤块置 **L808（`close_price` 多行赋值结束）后、L810 前**；执行守卫置 **L292 解析后、L296 差异告警前**。
- **代码规格（三处 + 一函数）**: `is_valid_price(price)` 纯函数（`None/NaN/±inf/<=0` → False）；`execute_order` 守卫（warning + `return False, None`，不写 `trade_log`）+ docstring 契约句；agents queue 过滤（`_record_failure("pending_invalid_price")` + `continue`）；V2 queue 过滤（`skipped_price.append` + `continue`）。
- **测试规格**: V1 守卫矩阵 6 / V2 agents NaN·0 2 / V3 负价 2 / V4 SELL 持仓保留 1 / V5 重试 bounded 1 / V6 V2 NaN·0（caplog）2 / V7 VWAP NaN 1 / V8 正常路径 2 = **17 实例**；fixture 六项独立（F1-F6），零 `unittest.mock`。
- **实施期裁决**: F-I-P033-1 `is_valid_price` 位置内聚于 `TradeLog` 后（`np` 已导入无前向依赖）/ F-I-P033-2 V5 断言改区间（`0 < count <= 5`）避免半衰期与日历耦合 / F-I-P033-3 agents 过滤置于 `close_price` 后保持语句零位移 / F-I-P033-4 V6 经 caplog（`skipped_price` 无 getter）/ O-I-P033-1 新测试首轮先 black。
- **回归面与门禁预测**: 合法价零变化（golden 13 零重录硬门禁）；**731 → 748 passed** / 测试文件 **82 → 83** / black **119 → 120** / mypy **37 files 0** / `except Exception` 恒 **22**；零改动面含 `tracker` / `pending` / `interfaces` / `target_positions` / golden。
- **下一 Step**: **Step 6 实施 Review**（须 GLM-5.3-Flash）；六项复核重点（守卫位置 / 单一来源 1 定义 3 调用 / 插入点 / 计量口径 / 合法价回归 / 静默面）。
- **提交与 CI**: 提交 `ca78f5f`（2 文件 **+248/−1**：IMPL 新建 + PROGRESS §1.4/§3.38.4）→ CI run `43900441923` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）；零代码，门禁持平 **731 passed / black 119 unchanged / mypy 37 files 0**。

### 3.38.5 P-033 Step 6 实施 Review 记录（2026-11-16）

- **复审基座**: **GLM-5.3-Flash**（≠ IMPL 作者 DeepSeek-V4.1-Flash，RULE-5 成立）；复审对象 `ca78f5f`（IMPL_p033 提交版）；复审时点 HEAD `b837d5f`（代码面与 `013c4d3` 一致）。
- **E1 锚点机械复核（十项）**: 全命中——`is_valid_price` 插入点 L151-152 / 守卫 L292-294 后 L296 前（try L290 / except L339 完整）/ docstring L287-289 / agents L32·L509·L511 / V2 L23·L808·L810 / `skipped_price` L780·L836-839 / `_record_failure` L126 / `np` L16 / 不改清单三处（L451/L1140/L563）/ `_get_execution_price` L191-260。
- **E2 门禁基线独立复测**: pytest **731 passed**（71.10s）/ black **119 unchanged** / mypy **37 files 0** / tests .py **82**——四项一致。
- **E3 红态行为探针（V1 矩阵六值）**: `None` → **`success=False`（既有 TypeError 漏斗 L339 兜底）红态即通过**；`NaN/inf/-inf/0/-5` → 全部 `success=True` 且入账（红态失败）。**F-S6-P033-1（P3）**：IMPL §3「V1 全 6 例失败」失实——实际 **B1t 5F/1P**，全批红态 **14F/3P**（豁免三例 V1-None / V8a / V8b）→ 当轮回写 §3 + §5（已回写）。
- **E4 六项裁决**: ① 守卫位置正确（前置 `if` 非异常路径）② 单一来源规格成立（1 定义 + 3 调用；实施后须复验 grep）③ 插入点精确（两引擎内部顺序差异不影响）④ 计量口径正确（agents 1 新键 / V2 零新键）⑤ 合法价回归基线一致（N3 + S5 双证）⑥ 静默面规格成立（warning 2 类 / AST 22 恒定）。
- **发现分级**: **0 P0/P1/P2 / 1 P3 当轮回写 / 2 观察**（O-S6-P033-1 None 行为兼容性 / O-S6-P033-2 `!r` 消息形态）。
- **结论**: **pass**——准予进入 **Step 7 CHECKLIST**；前置条件三项（17 实例口径 + 红态豁免三例登记 / 实测列引用 §13.3 / Step 9 红绿 B1t 5F/1P → B2t 6F/1P → B3t 2F/1P → 748）。
- **提交与 CI**: 提交 `ae86506`（2 文件 +99/−2：IMPL §3 红态修正 + §5 V1 豁免标注 + §12 自检 + §13 复审记录；PROGRESS §3.38.5）→ CI run `43902539354` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.38.6 P-033 Step 7 CHECKLIST 编制记录（2026-11-17）

- **作者基座**: DeepSeek-V4.1-Flash（= RESEARCH/DESIGN/IMPL 同源；Step 8 一致性 Review 须异构 GLM-5.3-Flash）；基线 HEAD `204b15f`；[CHECKLIST_p033](CHECKLIST_p033_pending_order_price_validation.md) 完稿（5 组 **39 项**：A 7 / B 8 / C 5 / D 7 / E 12，机械计数）。
- **分组口径**: **A** = B1 `is_valid_price` + 解析价守卫（DESIGN-D1 → V1/V7）；**B** = B2 agents queue 前置过滤（DESIGN-D2 → V2-V5/V8a）；**C** = B3 V2 queue 前置过滤（DESIGN-D2 → V6/V8b）；**D** = 不变式 I1-I7；**E** = 测试/门禁/治理（B4）。
- **基线实测（Step 7 @`204b15f`）**: `tests/` .py **82** / golden json **7**（13 用例）/ 回归子集 `-k "golden or p027 or p029 or p031"` **57 passed + 674 deselected = 731** / AST `except Exception` **22**；black **119** 与 mypy **37 files 0** 采 §13.3 复测值（代码面未变）。
- **Step 6 前置条件三项落实**: ① 17 实例口径（V1 6 / V2 2 / V3 2 / V4 1 / V5 1 / V6 2 / V7 1 / V8 2）在 E1 + §6 覆盖映射双落点，红态豁免三例（V1-None / V8a / V8b）在 E2 显式登记；② 实测列统一引用 §13.3 基线（731 / 119 / 37 / 82）；③ E2 固化 Step 9 红绿序列 B1t **5F/1P** → B2t **6F/1P** → B3t **2F/1P** → **748**。
- **零预填纪律（RULE-1）**: 39 处实测单元格全部 `[待 Step 9]`；全文机械匹配 `[待 Step 9]` **43** = 39 单元格 + 2 签字表占位 + 2 合法字面引用（头部规则行 / §6 计数说明）。
- **覆盖映射**: 测试 **8/8 用例 ID、17/17 实例**；不变式 **7/7**；设计决策 **6/6**（DESIGN-D1→A / DESIGN-D2→B+C / DESIGN-D3→A4 / DESIGN-D4→D4 / DESIGN-D5→B3+B7 / DESIGN-D6→E11）。
- **顺序敏感五项（Step 9 必做）**: ① 守卫在解析后、差异告警前；② 守卫在 `amount`/`Trade`/`add_trade` 前；③ agents 过滤在 L509 后 L511 前；④ V2 过滤在 L808 后 L810 前；⑤ B1 先于 B2/B3。
- **下一 Step**: **Step 8 一致性 Review**（须 GLM-5.3-Flash）；交接事项七项（四文档口径 / 两套 ID 不混用 / 顺序敏感五项 / 红态豁免标注 / 行号漂移 E12 / black 先行 / AST 口径不含 `core/`）。
- **提交与 CI**: 提交 `e0aba52`（2 文件 **+150/−1**：CHECKLIST 新建 **+137** + PROGRESS §1.4/§3.38.6 **+13/−1**）→ CI run `43905254341` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）；零代码，门禁持平 **731 passed / black 119 unchanged / mypy 37 files 0**。

### 3.38.7 P-033 Step 8 一致性 Review 记录（2026-11-17）

- **复审基座**: **GLM-5.3-Flash**（≠ Step 7 作者 DeepSeek-V4.1-Flash，RULE-5 成立）；复审对象 `e0aba52`（CHECKLIST_p033 提交版，137 行）；复审时点 HEAD `7723bfe`；方法 = 独立机械脚本（`%TEMP%\p033_step8_check.py`）五项 + 对齐矩阵七项（CHECKLIST §7 交接七项逐条裁决）。
- **E1 机械五项全过**: 链接 3 / 0 broken；ID 39 行 39 唯一（A7+B8+C5+D7+E12 与 §6 精确一致）；关键计数自洽（39×15 / 17 实例×5 / 731×5 / 748×4 / 22×8 / 57×3 / 14F/3P×2）；`[待 Step 9]` 字面 **43**（39 单元格 + 规则行 1 + §6 标签 1 + 签字表 2）与账目行吻合；签字表四行齐备。
- **E2 对齐矩阵**: A（17 实例：DESIGN §6 × IMPL §2/§5 × CHECKLIST E1/§6）✅ / B（门禁链 748·83·120·37·13·22：DESIGN I7 L176 × IMPL §1 L18 × CHECKLIST 三处）✅ / C（1 语义修正 + 1 新键：DESIGN §1/§4.2 × IMPL §1/§4.3 × CHECKLIST B2-B4/D6/E10）✅ / F（顺序敏感五项落 A2/A3/B2/C2 + IMPL §3）✅ / G（基线引用链 `b837d5f..204b15f` docs-only、诚实披露）✅；**D（红态分批）与 E（两套 ID）⚠ → 当轮修正**。
- **F-S8-P033-2（P3，最重）**: 「B1t 5F/1P」为 V1 矩阵内读数误作批次级——B1t 批次 = V1（6 实例）+ V7（1 实例），V7 当前对 VWAP-NaN 成交（Step 2 B1 实锤）→ 批次级红态 **6F/1P**；E2 行内 5+6+2=13F ≠ 14F 自相矛盾；同源失准在 IMPL §3 / §13.4 / §13.7 → 当轮修正 E2 + 回写 IMPL 三处（**全批 14F/3P 不变**；PROGRESS §3.38.5/§3.38.6 历史记录不回改，O-R5-P031-1 先例）。
- **F-S8-P033-1/3/4/5/6（各 P3）**: E10 引用过时节号 §3.38.6→**§3.38.7**；四处裸引用 D1/D2/D3 违反 §7.2 自立规则→标 `DESIGN-D*`（P-031 F-S8-P031-3 同型）+ §6 映射「D1→A1-A3+A5-A7」消除与 A4 的区间重叠；C3 证据命令未限定 `engine_v2.py` 且 `^+` 未转义（.NET regex 抛错）→改限文件命令；`core/` 侧零新增 `except` 无机械校验命令（AST 十文件口径不含 core/，§7.7 自认留证未落命令）→ D5 补 `git diff core/` 中 `^\+.*\bexcept\b` = 0；A2「两段 warning」歧义→「单条 warning（消息两段拼接）」。
- **发现分级**: **0 P0/P1/P2 / 6 P3 当轮修正 / 2 观察**（O-S8-P033-1 基线引用链成立 / O-S8-P033-2 PROGRESS 历史记录不回改）。
- **结论**: **pass**——四文档口径闭环（17 实例 / 门禁链 / 语义修正 / 顺序敏感五项全对齐，红态分批与 ID 规范经修正后闭环），39 项验收可执行，准予进入 **Step 9 TDD**；前置条件四项（批次级红态口径 6F/1P / 顺序敏感五项留证 / D5 core/ except 命令随门禁 / black 先行 + C3 限文件命令）。
- **提交与 CI**: 提交 `0f9adff`（3 文件 **+81/−17**：CHECKLIST §9 复审记录 + 签字表回填 + 6 P3 当轮修正；IMPL §3/§13.4/§13.7 红态批次口径回写；PROGRESS §1.4/§3.38.7）→ CI run `43908389016` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.38.8 P-033 Step 9 TDD 实施记录（2026-11-17）

- **执行基座**: DeepSeek-V4.1-Flash（与四文档同源）；基线 HEAD `e53f560`；Python312 + `MPLBACKEND=Agg`。
- **改动面（4 文件）**: `core/execution.py` **+21/−1**（`is_valid_price` L153-161 + 执行守卫 L308-315 + docstring 契约句）/ `agents/multi_strategy_engine.py` **+6/−1**（导入 L32 + 过滤块 L511-514）/ `core/engine_v2.py` **+6/−1**（导入 L23 + 过滤块 L810-813）/ `tests/test_p033_order_price_validation.py` **+259 新增**（Step 10 F-R5-P033-1 更正，原记 +203 为非空行计数偏差）。
- **三批红→绿（批次级口径，F-S8-P033-2）**: B1t **6F/1P**（V1 矩阵 5F/1P + V7 1F；`None` 经 TypeError 漏斗 L339 红态即通过）→ 7 passed；B2t **6F/1P**（V8a 豁免）→ 14 passed；B3t **2F/1P**（V8b 豁免）→ **17 passed**。全批 **14F/3P** 与预测逐项吻合。
- **门禁（六项全绿）**: pytest **748 passed**（172 warnings，45.47s）/ `tests/` .py **83** / black **120 unchanged** / mypy `core` **37 files 0** / golden **13 passed 零重录** / AST `except Exception` **22**；另 `core/` 新增 `except` **0**、`^-\s*def ` **0**、零改动面 `git status` 全空、回归子集 `-k "golden or p027 or p029 or p031"` **57 passed**。
- **单一来源核验**: `is_valid_price` 全仓 **1 定义 + 3 调用**（execution L309 / agents L512 / V2 L811）；`pending_invalid_price` **1 处写入**；V2 零新键（`skipped_price.append` 2 处 = 1 既有 + 1 新守卫）。
- **顺序敏感五项**: ① 解析 L304-306 → 守卫 L308-315 → 告警 L316 ② 守卫 < amount L327 < add_trade L350 ③ agents close L509 → 守卫 L511-514 → clamp L517 ④ V2 close L804-808 → 守卫 L810-813 → clamp 告警 L815 ⑤ B1 先于 B2/B3——全过。
- **实施期发现**: F-S9-P033-2（P3）B3t 首跑因新测试缺 `import logging` 致 3 failed（含 V8b），**当轮修复**后回到 2F/1P；F-S9-P033-1（观察）新测试首轮被 black 重排（O-I-P033-1 预判）；O-S9-P033-1（观察）B3t 红态仅由「汇总日志缺失」驱动——D1 安全层先于 D2 可观测层生效，反向印证双层防线。
- **CHECKLIST 回填**: 39 项实测列 **39/39** 全部回填（E9 于 CI 回收后回填），签字表 Step 9 行已落。
- **文档同步**: README 4 处（L7 badge / L99 / L278 / L431）与 ARCHITECTURE L3 的测试计数 **731→748 / 82→83** 同步（P-031 F10 惯例）。
- **下一 Step**: **Step 10 ADD 审计 + RULE-5 异构终审**（须 GLM-5.3-Flash）。
- **提交与 CI**: 提交 `31c5d36`（10 文件 **+419/−52**：代码 3 文件 +33/−3、新测试 +259、IMPL §11、CHECKLIST 39 项回填、PROGRESS §1.4/§3.38.8、CHANGELOG、README 4 处、ARCHITECTURE L3）→ CI run `43911402921` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

### 3.38.9 P-033 Step 10 ADD 审计 + RULE-5 异构终审记录（2026-11-17）

- **审计基座**: **GLM-5.3-Flash**（≠ 四文档作者 DeepSeek-V4.1-Flash，RULE-5 成立，ADD 审计与异构终审合并为一轮）；审计对象区间 `e53f560..c0cef1c`（2 提交，代码面集中于 `31c5d36`）；审计时点 HEAD `c0cef1c`；独立脚本 `%TEMP%\p033_step10_audit.py`。
- **Phase 0 质量门**: DESIGN_p033 **5/5 Tier A**（可测试约束 / 模块映射 / 接口契约 / 修正项 / 跨模块契约全 1 分）。
- **Phase 1 完整性**: 区间 10 文件 +419/−52（3 代码 +33/−3、测试 **+259**、6 文档）；代码 7 hunk；计量键 agents 1 / V2 0；新增 logger +1（executor 守卫）/ raise 0 / except 0 / 删除 def 0；零改动面零命中。
- **Phase 2 保真度**: IMPL §4 四规格独立读码逐字吻合（`is_valid_price` L153-161 / 守卫 L308-315 早于 amount L327 与 add_trade L350 / agents 过滤 L511-514 / V2 过滤 L810-813）；§11.4 漂移表 18 项逐项复核吻合。审计脚本首跑「order ok False」系正则首匹配命中 next-day 路径伪影，手工核验队列路径真实顺序正确。
- **Phase 3 必要性**: 7 hunk 逐一归因 §4.1/§4.2/§4.3①②/§4.4①②，**零游离行**。
- **Phase 4 语义**: 守卫语义 / 重试生命周期（V5 实证 8 日排空）/ 计量不对称 / 合法价不变（golden 13 零重录 + 731 全绿）/ 双层防线（B3t 红态实证 D1 先行兜底）——五面裁决成立。
- **E1-E5 门禁独立复跑（全量重跑）**: pytest **748 passed**（64.53s）/ P-033 套件 **17 passed** / black **120 unchanged** / mypy **37 files 0** / 回归子集 `-k "golden or p027 or p029 or p031 or p033"` **74 passed**（13+24+11+9+17 口径精确）/ tests .py **83** / AST **22** / `core/` 新增 except **0** / CI 两跑 success。
- **盲区扫描**: 本批新增面（agents / execution / 测试文件）严格启发 **0 命中**，零新增静默路径；engine_v2 浮出两处**既有 typed except**（L597 / L1028，显式降级语义，早于本批）——登记对账（O-R5-P033-1）。
- **发现分级**: **0 P0/P1/P2 + 1 P3 当轮修正（F-R5-P033-1：测试文件净行数 +203→+259，非空行计数偏差，P-031 F-R5-P031-1 同型，IMPL §11.2 + 本节已更正）+ 1 观察**。
- **结论**: **pass——P-033 批次关闭**。未决 U-P033-1（R3 告警文案 T3）/ U-P033-2（BUY 现金夹紧）/ U-P033-3（账目层守卫，不采纳）随批归档。
- **提交与 CI**: 提交 `61e8f97`（3 文件 **+123/−6**：CHECKLIST §10 终审记录 + 签字表 Step 10 回填 + 头部状态批次关闭；IMPL §11.2 +259 更正；PROGRESS §1.4 done + §3.38.9）→ CI run `43913759781` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。
- **交付物**: 批次总结报告 [SUMMARY_p033](SUMMARY_p033_pending_order_price_validation.md)（§1-§10 全景：缺陷谱系与治理链、守卫单点 + 双层防线落点、17 实例三批红绿与门禁、13 P3 + 19 观察台账、20 提交链 + 13 CI、边界遗留与启示）——批次归档收口；提交 `94a6243` → CI run `43916771847` **success**（3.10 / 3.11 / 3.12 三 job 全绿，EXIT=0）。

---

### 3.39 P-034 台账收口 · 价格差异校验守卫 · CI 锁门禁（Step 1 取证，2026-11-17）

- **触发**: 用户裁决「按建议执行 P-034 = 三件合批走完十步」；三件来源 = ① U-P033-1（R3 `close=0` 告警文案）② U-P024-2（CI `uv lock --check` 门禁）③ PROGRESS §1.4 台账三缺口（P-030/P-032 同型第三次）。
- **判档（当轮修正）**: 待办分析曾称「T3 零行为风险档」，但任务 C = **新增 CI 门禁** → SPEC_PROCESS §批次档位 判档规则 2「新增 / 删除 / 弱化任何门禁 → 一律 T1」**强制升级**，且改动路径含 `.github/workflows/`（Layer-1）→ 整批 **T1**，四文档 + 8 道 Review 全量不裁剪。
- **Step 1 探针（`%TEMP%\p034_step1_probe.py`，Python312）**: R3 差异校验六形态实测——**R1 新证（P3 结构性隐患）** `close_price=0.0`（Python float）→ `abs(10.0-0.0)/0.0` 抛 `ZeroDivisionError` → 被 L359 `except Exception` 捕获 → **合法价订单 `success=False`**（诊断代码吞单）；**R2** `np.float64(0)` → `inf` → 「差异=inf%」告警噪声（U-P033-1 原范围）；**R3 新形态** `close=NaN` / `-5.0` → 比值 `nan` / `-3.0` → `> 0.1` 恒 False → **校验静默失效**；合法价对照（`close=10` / `close=8`）逐字正确；`open=NaN, close=0` 由 P-033 守卫先行拦截（双层防线不受影响）。
- **R1 可达性判定（诚实降级 P3）**: 三引擎全部 8 个 `execute_order` 调用点的 `close_price` 均来自 pandas 横截面 `.loc[date]`（`np.float64`）→ numpy 除零返回 `inf` 不抛 → **生产不可达**；R1 仅在外部直接调用 / 未来新调用方传入 Python float 时触发。修复不因此降级（观测逻辑不应有副作用，成本 1 行）。
- **任务 C 基线**: `uv 0.11.14` + `uv lock --check` **exit 0**（148 packages / 25ms）；`uv.lock` `version = 1` / `revision = 3` / `requires-python = ">=3.10"`；CI `tests.yml` 单 job（matrix 3.10/3.11/3.12）+ `pip install ".[dev]"`，**零 uv 步骤** → 锁漂移无拦截。
- **任务 A 缺口（8 处）**: U-P033-1~3 未建行 / U-P014-1·U-P014-3·U-P015-1·U-P016-1 仅存于批次文档 / U-008 与 U-P021-2 双源同项；处置 = U-P033-1 本批关闭、U-P033-2 + U-P014-3 并入 U-P031-2 单一跟踪源、U-P033-3 标「已裁决不采纳」、其余建行、U-008 标「已合并至 U-P021-2」。
- **根因纪律（新增 D5）**: 三次同型（P-030 → P-032 → P-034）的成因均为「批次关闭只写 §3.x 正文、不建 §1.4 行」→ 批次关闭动作清单新增一项「本批新增 U-\* / O-\* 是否已在 §1.4 建行」。
- **负向发现六项**: N1「R3 仅文案噪声」部分不成立（Python float 形态吞单）/ N2「生产可触发 R1」不成立（全 `np.float64`）/ N3「P-033 守卫已覆盖 close 无效」不成立（守卫判执行价，close 仅参与诊断）/ N4「既有测试依赖 close=0」不成立（grep 零命中）/ N5「CI 加 uv 影响测试 job」不成立（独立 job）/ N6「`--check` 受 Python 版本影响」不成立（uv 二进制，钉版本规避）。
- **下一 Step**: ~~Step 2 独立 Review~~（已完成，见下）

### 3.39.1 P-034 Step 2 独立 Review 记录（2026-11-17）

- **基座披露**: 复审基座 **DeepSeek-V4.1-Flash = 作者同源** → **RULE-5 异构条件不成立**，按 P-032 先例执行**同基座独立复审**（RULE-4 单视角披露），异构终审登记 **U-P034-3**（须非 DeepSeek 基座）。复审对象 `279c86a`。
- **E1 锚点十二项全命中**: 差异校验 L316-324 / P-033 守卫 L308-315 在前 / `except` L359 覆盖 / `_get_execution_price` 五分支（OPEN 无 float 转换、VWAP 聚合、CUSTOM 仅判 `>0`）/ V2 L770-773·L804-808·L820 / agents L489·L509·L525 / agent_framework L1345·L1420 / `tests.yml` L9-46 零 uv / `uv.lock` 头三字段。
- **E2 探针重放**: 十场景（六形态）读数与 Step 1 §5 **逐字一致**。
- **E3 独立探针四项新证**: **C1** `is_valid_price` 12 值语义表（无效 8 全 False / 合法 4 全 True，含 `1e-9` 零误伤）/ **C2** pandas 取值形态——Series 索引 → `np.float64`，**`to_dict()` / `dict(items())` → Python `float`**；`np.float64 / Python 0.0` = `inf`（不抛），`Python / Python 0.0` 才抛 → **R1 可达性对写法敏感**（F-S2-P034-1 当轮回写 §2.2）/ **C3** M-A 等价性——合法 close 三例 `old == new` 逐位一致、无效四例 SKIPPED / **C4 锁漂移检出实证**——临时目录改 `numpy>=1.23.0`→`>=1.24.0` → `uv lock --check` **exit 1**（文案「The lockfile at 'uv.lock' needs to be updated, but '--check' was provided」），副本未改 exit 0 → **门禁可真实变红**（P-024 假门禁教训正面实证）。
- **六项裁决**: ① 判档 T1 **成立**（CI 门禁 ∈ 判档规则 2 明列）② R1 **维持 P3**（C2 精化后按现行代码可达性）③ M-A **零合法价差异** ④ 保留 `is not None` **成立**（mypy 窄化必需；`TypeGuard` 需改 P-033 已验收签名 → 拒绝）⑤ CI 独立 job **成立**（1 次 vs matrix 3 次），`setup-uv` 版本真实性交 Step 6 ⑥ 台账处置**合先例**（P-028 / P-030 / P-032 / P-025-4）。
- **发现分级**: **0 P0/P1/P2 / 1 P3 当轮回写（F-S2-P034-1）/ 4 观察**（O-S2-P034-1 `RUST_LOG=info` 致 131KB INFO 输出 / O-S2-P034-2 `setup-uv` 版本待 Step 6 / O-S2-P034-3 外部调用面 / O-S2-P034-4 `bool` vs `TypeGuard`）。
- **结论**: **pass**——准予进入 **Step 3 DESIGN**；前置条件四项（M-A 形态 / CI 独立 job + 禁 `|| true` + Step 6 核验 / 测试规格覆盖 C1·C3·三类红态 / 台账 8 处处置）。

### 3.39.2 P-034 Step 3 DESIGN 记录（2026-11-17）

- **作者基座**: DeepSeek-V4.1-Flash（= Step 1/2 同源；Step 4 须异构，若同基座则披露 + 预留 U-P034-3）。基线 HEAD `47b7430`；[DESIGN_p034](DESIGN_p034_ledger_diff_guard_and_lock_gate.md) 完稿（D1-D4 / I1-I6 / V1-V5 **12 实例** / B1-B4 回退点 / 4 观察）。
- **D1 差异校验守卫**: `if close_price is not None and is_valid_price(close_price):` 包裹 L318-324；保留 `is not None` **仅为 mypy 类型窄化**（`is_valid_price` 返回 `bool` 非 `TypeGuard`）；无效 close **静默跳过**（不计算 / 不告警 / 不改成交）；告警文案与 10% 阈值逐字不变。
- **D2 CI 锁门禁**: 新增独立 job `lock-check`（**不进 matrix**）→ `astral-sh/setup-uv@v6` + `version: "0.11.14"` + `enable-cache: true` + `uv lock --check`；**禁 `|| true`**（P-024 假门禁教训）；测试 job 零改动（仍 `pip install ".[dev]"`）；降级链 `pip install uv==0.11.14`。
- **D3 台账 8 处**: U-P033-1 → done（D1 承接）/ U-P033-2 + U-P014-3 → 合并至 U-P031-2 / U-P033-3 → 已裁决不采纳 / U-P014-1·U-P015-1·U-P016-1 → 建行 pending / U-008 → 合并至 U-P021-2；附则「批次关闭动作清单须检查 U-\* / O-\* 建行」。
- **红态口径精化（自查，P-033 F-S8-P033-2 教训直接应用）**: V1 六参数中仅 **2 红**（`0.0` 抛异常吞单 / `np.float64(0)` 产生 `inf%`），其余 4 例（`nan` / `-5` / `inf` / `-inf`）**现状即无告警**——R3 的「静默」无法从外部与「跳过」区分，如实归为**回归保护**；V4 **1 红**；V2/V3/V5 全通过 → **全批 3 红 / 9 通过**。不伪造红态（P-031 F-S9-P031-3 先例）。
- **门禁预测**: 748 → **760**（+12）/ tests 文件 83 → **84** / black 120 → **121** / mypy 37 files 0 / golden 13 零重录 / AST 22。
- **不改项（D4）**: `TypeGuard` 改造 / 阈值可配置 / 文案格式 / `uv export`·`uv sync` / §1.4 全表重构——五项均拒绝并留理由。
- **下一 Step**: **Step 4 独立 Review**（RULE-5 要求异构基座）；复核重点六项（D1 等价性与 mypy / D2 action 版本真实性 / D3 处置完整性 / V1-V5 覆盖与红态豁免 / 门禁推算 / 静默观测缺口披露）。

### 3.39.3 P-034 Step 4 独立 Review 记录（2026-11-17）

- **基座披露**: 复审基座 **DeepSeek-V4.1-Flash = 作者同源** → RULE-5 异构不成立，**同基座独立复审**（RULE-4 披露）；异构终审仍由 **U-P034-3** 跟踪。复审对象 `8f7f05a`。
- **E1 锚点八项全命中**: 差异校验 L316-324 / P-033 守卫 L308-315 / `is_valid_price` L153-161 / `execute_order` 签名 L280 / `tests.yml` L9-46 / `uv.lock` 头 / 台账三处位置 / 红态口径表自洽。
- **E2 外部事实核验三项**: ① **mypy 窄化正反例**——`good`（`is not None and is_valid_price`）**0 error**、`bad`（仅 `is_valid_price`）**2 errors**（`Unsupported operand types for / ("float" and "None")`）→ 保留 `is not None` **是必需而非冗余**（机械证据）；② `gh api` 实测 **`setup-uv` 最新 v10.3.3**（原稿 `@v6` 过时）+ **uv `0.11.14` 命中**；③ v10 `action.yml` 中 `enable-cache` 语义为 `'auto'` → 省略该输入。
- **六项裁决**: ① D1 写法成立且必要 ② **D2 原稿错误已修正**（`@v6` → `@v10.3.3`）③ D3 与 Step 1 §2.1 一一对应、无新增散落 ④ V1-V5 覆盖 R1/R2/R3/合法价/`None`/P-033 交互，红态 3 / 通过 9 自洽 ⑤ 门禁推算全对（760 / 84 / 121 / 37 / 13 / 22）⑥ 静默观测缺口已披露（R-P034-1）。
- **发现分级**: **0 P0/P1 / 1 P2 当轮回写（F-S4-P034-1 `setup-uv@v6` 过时 + `enable-cache` 语义变化）/ 3 观察**（O-S4-P034-1 `quiet` 输入 / O-S4-P034-2 `version-file` / O-S4-P034-3 `1e-9` 边界）。
- **结论**: **pass**——准予进入 **Step 5 IMPL**；前置条件四项（D1 不得省略 `is not None` / D2 `@v10.3.3` 禁 `|| true` / 12 实例 + 红态 3F/9P 逐批留证 / 台账与 CHANGELOG·ARCHITECTURE 在 B3 回写）。

### 3.39.4 P-034 Step 5 IMPL 记录（2026-11-17）

- **作者基座**: DeepSeek-V4.1-Flash（= 上游同源；Step 6 须异构，若同基座则披露）。基线 HEAD `a0db635`；[IMPL_p034](IMPL_p034_ledger_diff_guard_and_lock_gate.md) 完稿（B1-B4 / §4 逐文件锚点 / §5 V1-V5 12 实例 / §6 四 fixture / §7 七项低效排除 / §8 回退点 / §9 三项实施期裁决）。
- **B1 代码规格**: `core/execution.py` L316-317 → 注释改「P-034 D1：价格合理性检查（close 无效时跳过——避免 inf 噪声 / 除零吞单 / NaN 静默）」+ 条件改 `close_price is not None and is_valid_price(close_price)`；L318-324（ratio / 阈值 / warning）**逐字不动**；估 **+2/−1**。
- **B2 CI 规格**: `tests.yml` 末尾新增 `lock-check` job（`astral-sh/setup-uv@v10.3.3` + `version: "0.11.14"`，**省略 `enable-cache`**，`uv lock --check`，**禁 `|| true`**）；`test` job 逐行不动；估 **+12/−0**。
- **B3 台账规格（8 处逐行文本已定稿）**: 新增 **7 行**（U-P033-1 done / U-P033-2 已合并 / U-P033-3 已裁决不采纳 / U-P014-1 pending / U-P014-3 已合并 / U-P015-1 pending / U-P016-1 pending）+ U-P031-2 行尾补注「单一跟踪源」+ 旧表 U-008 行尾补注「并入 U-P021-2」= 8 处处置全部落位。
- **B3 同步**: `CHANGELOG [Unreleased] Changed` 首条（价格差异校验守卫 + CI 锁门禁，748 → 760）+ `ARCHITECTURE §9.2` L335「CI 使用 pip，不校验锁」订正为「`lock-check` job 以 `uv lock --check` 校验（失败即红）」。
- **测试规格**: V1 无效 close 六参数 / V2 合法三参数（`8.0`→25.00%、`7.0`→42.86%、`10.5`→零）/ V3 `None` / V4 R1 吞单 / V5 P-033 交互；fixture 四项独立、零 `unittest.mock`。
- **红态预算**: B1t 首跑 **3 failed / 9 passed**（V1 的 `0.0` 与 `np.float64(0)` + V4）；其余 9 例为回归保护，**不得**把四例「静默」误报为红态。
- **下一 Step**: **Step 6 实施 Review**（RULE-5 要求异构基座）；复核重点六项（守卫条件 / 单一来源 1 定义 4 调用 / CI job 形态 / 台账 8 处 / 门禁推算 / 红态 3F/9P 口径）。

### 3.39.5 P-034 Step 6 实施 Review 记录（2026-11-17）

- **基座披露**: **DeepSeek-V4.1-Flash = 作者同源** → RULE-5 异构不成立，**同基座独立复审**（RULE-4）；异构终审仍由 **U-P034-3** 跟踪。复审对象 `05778d1`。
- **E1 锚点十项全命中**: L316/L317 / L318-324 / `is_valid_price` L153-161 / `execute_order` L273·L280 / `tests.yml` L9-46 / `uv.lock` 头 / §1.4 三处（L81·L75·L158）/ CHANGELOG `### Changed` / ARCHITECTURE §9.2 L335 / golden 7 json。
- **E2 门禁基线独立复测（四项）**: pytest **748 passed**（172 warnings，49.67s）/ black **120 unchanged** / mypy **37 files 0** / `tests/` .py **83**（`*.py` 全量）/ **80**（`test_*.py`）。
- **E3 红态预览（`%TEMP%\p034_step6_red_probe.py` 模拟 12 实例，不改代码）**: **3 failed / 9 passed**——失败三例 = `V1[python-0.0]`（`success=False`/`trades=0`/`errors=1`）、`V1[np-0]`（`diff_warns=1` `inf%`）、`V4[close=0.0]`（吞单）；其余 9 例（V1 `nan`/`neg`/`inf`/`neg_inf` + V2×3 + V3 + V5）全部通过 → 与 IMPL §3 红态预算**逐项吻合**。
- **六项裁决**: ① 守卫条件规格精确 ② 单一来源 1 定义（实施后 3 → 4 调用）③ CI job 形态成立（`@v10.3.3` / 无 `enable-cache` / 无 `|| true`）④ 台账 8 处规格完整可落地 ⑤ 门禁推算全对（760/84/121/37/13/22）⑥ 红态 3F/9P 经 E3 实证、四例回归保护未伪造。
- **发现分级**: **0 P0/P1/P2 / 1 P3 当轮回写（F-S6-P034-1 `tests/` .py 计数口径未注明——`*.py` 83 vs `test_*.py` 80，§1 已补注）/ 2 观察**（O-S6-P034-1 V1/V4 断言重叠 / O-S6-P034-2 `np-0` 的 `RuntimeWarning` 修复后应消失）。
- **结论**: **pass**——准予进入 **Step 7 CHECKLIST**；前置条件三项（12 实例口径 + 红态 3F/9P 与四例回归保护登记 / 门禁实测引用 §11.2 并注明 `.py` 全量口径 / Step 9 红绿须与 E3 逐项对拍）。

### 3.39.6 P-034 Step 7 CHECKLIST 编制记录（2026-11-17）

- **作者基座**: DeepSeek-V4.1-Flash；基线 HEAD `8f65170`；[CHECKLIST_p034](CHECKLIST_p034_ledger_diff_guard_and_lock_gate.md) 完稿（五组 **37 项**：A 8 / B 5 / C 7 / D 6 / E 11，机械计数）。
- **分组口径**: **A** = B1 差异校验守卫（DESIGN-D1 → V1/V3/V4/V5）；**B** = B2 CI `lock-check`（DESIGN-D2）；**C** = B3 台账 8 处 + CHANGELOG + ARCHITECTURE（DESIGN-D3）；**D** = 不变式 I1-I6；**E** = 测试/门禁/治理。
- **基线实测（Step 6 §11.2 @`05778d1` 代码面）**: pytest **748** / `tests/` .py **83**（**口径 = 全部 `.py`**；`test_*.py` 80）/ black **120** / mypy **37 files 0** / golden 13 用例（7 json）/ AST **22**。
- **零预填纪律（RULE-1）**: 37 处实测单元格全部 `[待 Step 9]`；§6 计数与分组机械相加一致（8+5+7+6+11=37）。
- **Step 6 前置条件三项落实**: ① 12 实例口径在 E1 + §6 双落点，红态 3F/9P 与四例回归保护在 E2 显式登记；② 门禁实测引用 §11.2 并注明 `.py` 全量口径（F-S6-P034-1）；③ E2 固化 Step 9 红绿须与 §11.3 E3 逐项对拍。
- **ID 规范**: 组标题一律标 `DESIGN-D*`，避免与本文件 D 组（不变式）同字母碰撞（P-033 F-S8-P033-3 教训）。
- **下一 Step**: **Step 8 一致性 Review**（RULE-5 异构优先；同基座则披露）；交接七项（口径一致性 / 两套 ID / 顺序敏感四项 / 红态豁免 / `.py` 口径 / black 先行 / CI action 版本）。

### 3.39.7 P-034 Step 8 一致性 Review 记录（2026-11-17）

- **基座披露**: **DeepSeek-V4.1-Flash = Step 7 同源** → RULE-5 异构不成立，**同基座独立复审**（RULE-4）；异构终审由 **U-P034-3** 跟踪。复审对象 `0285f25`；方法 = 独立机械脚本（`%TEMP%\p034_step8_check.py`）五项 + 对齐矩阵七项。
- **E1 机械五项全过**: M1 链接 3 / 0 broken；M2 **37 行 / 37 唯一**、分组 **A8+B5+C7+D6+E11** 与 §6 精确一致；M3 计数自洽（37×9 / 12 实例×3 / 748×4 / 760×4 / 84×3 / 121×3 / 37 files 0×3 / 22×5 / 红态两写法各 1）；M4 `[待 Step 9]` 字面 **39** = 37 单元格 + 规则行 1 + §6 标签 1；M5 签字表四行齐备。
- **E2 对齐矩阵 A-G 全过**: A 12 实例三处一致 / B 门禁链三处一致（含 `.py` 全量口径注）/ C 台账 8 处三处一致 / D 红态 3F/9P 与 IMPL §11.3 逐项对应 / E 两套 ID 无裸引用（`DESIGN-D*` 前缀已落实）/ F 顺序敏感四项均落验收项 / G 基线引用链成立（`05778d1..8f65170` docs-only）。
- **发现分级**: **0 P0/P1/P2 / 1 P3 当轮修正（F-S8-P034-1：§6 未列明 `[待 Step 9]` 字面 39 的构成 → 当轮补注账目）/ 2 观察**（O-S8-P034-1 红态两种写法并存 / O-S8-P034-2 签字表占位回填）。
- **结论**: **pass**——四文档口径闭环，37 项验收可执行，准予进入 **Step 9 TDD**；前置条件四项（红态 3F/9P 逐例留证 / 顺序敏感四项 / 台账与同步文档在 B3 回填 / black 先行 + CI 四 job success）。
- **下一 Step**: **Step 9 TDD**。

### 3.39.8 P-034 Step 9 TDD 实施记录（2026-11-17）

- **执行基座**: DeepSeek-V4.1-Flash；基线 HEAD `642ec60`；Python312 + `MPLBACKEND=Agg`。
- **红→绿（F5 两读数）**: 红 = **3 failed, 9 passed, 1 warning**——`[python-0]`（`assert False is True`）/ `[numpy-0]`（`差异=inf%` 告警残留）/ `v4_zero_close_not_swallowed`（`assert False is True`）；绿 = **12 passed in 0.56s**。红态三例与 IMPL §11.3 E3 预览逐项一致；九例回归保护红态即通过（未伪造红态）。
- **改动面（8 文件 +316/−48，`git diff --numstat 642ec60..de0268d` 实测）**: `core/execution.py` **+2/−2**（L316 注释 + L317 条件）/ `tests.yml` **+14/−1**（`lock-check` job）/ `tests/test_p034_price_diff_guard.py` **+136**（新增，5 函数 12 实例）/ `CHANGELOG` +2/−1 / `ARCHITECTURE` +1/−1 / `PROGRESS` +24/−3 / `CHECKLIST` +92/−40 / `IMPL` +45。
- **门禁（全绿）**: pytest **760 passed**（43.53s）/ `tests/` .py **84**（`test_*.py` 81）/ black **121 unchanged** / mypy **37 files 0** / golden **13 passed 零重录**（747 deselected）/ AST `except Exception` **22** / `core/` 新增 except **0** / `git diff` 签名删除 **0** / `uv lock --check` **exit 0** / 回归子集 `-k "golden or p027 or p029 or p031 or p033 or p034"` **86 passed**（13+24+11+9+17+12 口径精确）。
- **单一来源**: `is_valid_price` **1 定义**（execution L153）+ **4 调用**（execution L309 / **L317 新增** / agents L512 / engine_v2 L811）——AST 实测。
- **顺序敏感四项**: L316 注释 → L317 条件 → L318 ratio；`is not None` 在 `and` 左侧；YAML `jobs = ['test', 'lock-check']`；台账 §1.4 L82-88。
- **台账 8 处落地**: 新增 7 行（U-P033-1 done / U-P033-2 合并 / U-P033-3 不采纳 / U-P014-1 / U-P014-3 合并 / U-P015-1 / U-P016-1）+ U-P031-2 与旧表 U-008 行尾补注。
- **实施期发现**: **F-S9-P034-1（P3）** CHECKLIST E8 判据「≥ 74 passed」为下限判据，无法检出 p034 的 12 例漏跑 → 当轮修正为「**86 passed**」精确等值；F-S9-P034-2（观察）新测试首轮被 black 重排 1 文件（O-I-P034-1 预判）；O-S9-P034-1（观察）P-034 行 done 待 Step 10 置。
- **净行数自查（F-R5 教训）**: 初稿曾按估算写 `+191` / `execution +15/−1`，`git diff --cached --numstat` 实测为 **+136** / **+2/−2**，**提交前当轮更正**（§12.2 表）。
- **CHECKLIST 回填**: 36/37 已回填（E9 待 CI 回收）。
- **下一 Step**: **Step 10 ADD 审计 + RULE-5 异构终审**。

### 3.39.9 P-034 Step 10 ADD 审计 + 终审记录（2026-11-17）

- **审计基座**: **DeepSeek-V4.1-Flash = 四文档作者同源** → **RULE-5 异构条件不成立**，本轮为**同基座 ADD 审计 + 同基座终审**（RULE-4 披露）；异构终审由 **U-P034-3** 单一跟踪。审计对象区间 `fbed072..f2e719b`（9 提交，代码面集中于 `de0268d`；**U-P034-3 更正**：区间端点实测 **10** 提交，「9」与内容链 `fbed072..de0268d` 吻合——计数与 diff 两口径混用，见 §3.39.10 F-U3-P034-1）；审计时点 HEAD `f2e719b`。
- **Phase 0 质量门**: DESIGN_p034 **5/5 Tier A**（可测试约束 / 模块映射 / 接口契约 / 修正项 / 跨模块契约全 1 分）。
- **Phase 1 完整性**: 区间 **10 文件 +1425/−7**（代码 2 文件 + 测试 +136 + 文档 7；**U-P034-3 更正**：删除实测 −7，原记 −6，见 §3.39.10）；代码 hunk **2**（`execution.py @@ -313,8 +313,8` 条件替换 / `tests.yml @@ -43,4 +43,17` 新增 job）；代码面新增 `raise` / `except` / `logger.` 均 **0**；公开签名删除 **0**；零改动面零命中；本批零计量键。
- **Phase 2 保真度**: §4.1 条件 hunk 与 IMPL 规格逐字一致（L318-324 零改动）；§4.2 CI job 逐字（`@v10.3.3` / `version: "0.11.14"` / 无 `enable-cache` / 无 `\|\| true`）；§4.3 台账 8 处落位；§4.4/§4.5 文档同步；§12.2 净行数表与 `git diff --numstat 642ec60..de0268d` 逐文件吻合（+316/−48）。
- **Phase 3 必要性**: **2 hunk 零游离**——分别归因 DESIGN-D1（差异校验条件）与 DESIGN-D2（CI job）。
- **Phase 4 语义**: 守卫语义（诊断与决策解耦，不改变成交）/ 观测语义（合法价告警逐字保留，无效 close 安静跳过且已披露）/ 门禁语义（失败即红，C4 实证 exit 1）/ 台账语义（三源收敛 + 不采纳标注 + 双源合并）/ 复用语义（`is_valid_price` 1 定义 4 调用）——五面成立。
- **E1-E5 门禁独立复跑（全量重跑）**: pytest **760 passed**（68.17s）/ black **121 unchanged** / mypy **37 files 0** / 回归子集 `-k "golden or p027 or p029 or p031 or p033 or p034"` **86 passed**（13+24+11+9+17+12）/ `uv lock --check` **exit 0** / CI run `43923154391` 四 job（`lock-check` + 3.10/3.11/3.12）全 success。
- **盲区扫描**: 本批新增面（execution L316-324 前置 `if` / 新测试文件 / workflow 非 Python）**零新增静默路径**；既有浮出无新增（AST 十口径恒 22）。
- **发现分级**: **0 P0/P1/P2 + 1 P3 当轮修正（F-R5-P034-1：`O-P034-3` 引用幻觉——DESIGN §9.3/§9.4 与 CHECKLIST E11 引用从未定义的 `O-P034-3`，实为 `O-S4-P034-3`；三处已改）+ 2 观察**（O-R5-P034-1 `tests.yml` 无末尾换行与原文件一致非回归 / O-R5-P034-2 五轮复审全同基座，RULE-5 全程未满足 → U-P034-3）。
- **结论**: **pass——P-034 批次关闭**。未决 U-P034-1（`setup-uv` 维护）/ U-P034-2（外部调用面）/ **U-P034-3（RULE-5 异构终审预留）** 与 `R-P034-1~3` / `O-P034-1~2` / `O-S4-P034-1~3` / `O-R5-P034-1~2` 随批归档，触发条件不变。
- **提交与 CI**: 提交 `499524e`（3 文件 **+113/−6**：CHECKLIST §11 + 签字表 + 头部批次关闭；DESIGN 两处 `O-S4-P034-3` 修正；PROGRESS §1.4 done + §3.39.9）→ CI run `43924423589` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿，EXIT=0）。

### 3.39.10 P-034 U-P034-3 异构终审记录（2026-11-17）

- **终审基座**: **GLM-5.3-Flash ≠ 四文档作者与五轮复审者（Step 2/4/6/8/10）DeepSeek-V4.1-Flash** → **RULE-5 异构条件成立**，本节为 U-P034-3 预留的补做终审（先例 U-P032-1 同型；P-034 全程首个异构审查）。复审区间 `fbed072..7082c7a`（**12 提交**，`git rev-list --count` 实测 = 9 内容链 `fbed072..de0268d` + `f2e719b` + 终审记录 `499524e` + CI 回填 `7082c7a`）；复审时点 HEAD `7082c7a`。
- **E1 代码锚点重放**: execution L316-317 条件（`is not None` 在 `and` 左侧，mypy 窄化保留）/ L318-324 逐字未动 / P-033 守卫 L308-314 在前 / `is_valid_price` L153-161 未动；tests.yml `lock-check`（`@v10.3.3` + `version: "0.11.14"`、无 `enable-cache`、无 `\|\| true`）/ `test` job L9-46 逐行未动——全一致。
- **E2 diff 面核验**: 区间 12 提交；代码面新增 `raise` / `except` / `logger.` 全 **0**；公开签名删除 **0**；零改动面零命中。**发现 F-U3-P034-1（P3）**：§11.2 / §3.39.9「审计区间 9 提交 / −6」与区间端点实测不符——`fbed072..f2e719b` 实测 **10 提交、+1425/−7**，「9」仅与内容链 `fbed072..de0268d` 吻合（计数按内容链、diff 按区间端点两口径混写，同基座终审漏检）；两处当轮补正。
- **E3 门禁独立复跑**: pytest **760 passed** / black **121 unchanged** / mypy **37 files 0** / 回归子集 `-k "golden or p027 or p029 or p031 or p033 or p034"` **86 passed** / P-034 套件 **12 passed** / `uv lock --check` **exit 0**；CI run `43925230603`（`7082c7a`）四 job（`lock-check` + 3.10 / 3.11 / 3.12）全 success。
- **E4 运行期复验（独立探针，本基座编写）**: `%TEMP%\p034_u_p0343_probe.py` **7/7 PASS**——R1 吞单修复（`success=True trades=1 errors=0`）/ R2 噪声消除（`diff_warns=0`）/ R3 无效 close 静默跳过 / 合法价 25.00% 告警保留 / None 回归 / P-033 守卫交互（`success=False guard=1`）/ `is_valid_price` 语义 8/8。
- **E5 F-R5-P034-1 修正复核**: `O-P034-3` 现存 5 处命中（CHECKLIST E11 行 / 签字表 Step 10 行 / §11.8 F-R5-P034-1 行、PROGRESS P-034 行 / §3.39.9 发现分级行）全为修正历史合法引用；DESIGN §9.3 / §9.4 裸引用清零（均改 `O-S4-P034-3`）。
- **发现分级**: **0 P0/P1/P2 + 2 P3 当轮修正 + 1 观察**——F-U3-P034-1（审计区间记录口径混用 → CHECKLIST §11.2 与本档 §3.39.9 补正）/ F-U3-P034-2（**D5 派生纪律执行缺口**：U-P034-1/2/3 仅散落 §3.39.9 正文未在 §1.4 建行，散落正文同型第四次 → 本档 §1.4 建三行，其中 U-P034-3 done）/ O-U3-P034-1（终审区间 12 > 审计区间 10，差额 2 提交为审计后流程提交，正常时序）。
- **结论**: **pass——U-P034-3 关闭，P-034 过程链全闭合**（Step 1-10 + 五轮同基座复审 + 同基座终审 + 异构终审）；两项 P3 均为文档记录缺陷、零代码影响，批次维持关闭。
- **提交与 CI**: 提交 `cf13f98`（2 文件 **+53/−7**，docs-only：CHECKLIST §12 + §11.2 补正 + 签字表 + 头部状态；本档 §1.4 三行建行 + §3.39.9 补正 + §3.39.10）→ CI run `43929524333` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。
- **交付物**: 批次总结报告 [SUMMARY_p034](SUMMARY_p034_ledger_diff_guard_and_lock_gate.md)（§1-§10 全景：R3 三形态与三件合批谱系、D1-D4 设计口径与七项低效排除、12 实例红态 3F/9P 与门禁 760、1 P2 + 7 P3 + 23 观察台账、14 提交链 + 14 CI、边界遗留与六条启示）——批次归档收口；提交 `be429b8`（2 文件 **+305/−0**）→ CI run `43931900297` **success**。

### 3.40 P-035 台账同步（T3 轻批，2026-11-17）

- **触发**: 2026-11-17 待办优先级分析（§1.4 全表盘点 **31 项 pending**）发现 **U-P024-2 状态失效**——该项即 P-034 任务 B「CI 增加 `uv lock --check` 门禁」，已完整落地（[tests.yml](../.github/workflows/tests.yml) `lock-check` job：`astral-sh/setup-uv@v10.3.3` + `version: "0.11.14"` + `uv lock --check`，无 `|| true`），且自首跑 `43923154391` 起每个 CI run 的该 job 全部 success（P-034 阶梯 14 run + SUMMARY_p034 2 run），但台账仍标 `pending`。
- **归因**: P-034 DESIGN-D3 的八处收口清单为「U-P033-1 done / U-P033-2·U-P014-3 合并 / U-P033-3 不采纳 / U-P014-1·U-P015-1·U-P016-1 建行 / U-008 合并」——**不含本批实现项自身**。原 D5 纪律只覆盖「本批新增 U-\*/O-\* 须建行」，未覆盖「本批实现/承接的既有项须转 done」。同型缺口第 5 次（P-030 / P-032 / P-034 / F-U3-P034-2 / 本次）。
- **档位**: **T3**（纯文档：零代码 / 零测试 / 零门禁变更；仅 PROGRESS + CHANGELOG + DESIGN_p034 附则）。
- **变更**: ① `U-P024-2` → **done**（P-034 承接；C4 实证门禁可红 / 16 run 全绿）；② `U-P021-1`（已合并至 U-P024-2）追加关闭指针注；③ **D5 派生纪律扩展**——批次关闭动作清单定为两项：**(a)** 本批新增 U-\*/O-\* 是否已在 §1.4 建行；**(b)** 本批实现/承接的既有台账项是否已转 done / 已合并；④ [CHANGELOG](../CHANGELOG.md) `[Unreleased] Changed` 追加本批条目。
- **核验**: §1.4 pending 计数 **31 → 30**（`Grep` 机械复测）；U-P024-2 状态字段为 `done`；D5 扩展文本落于 DESIGN_p034 D3 附则 + 本节两处。
- **门禁持平（实测 @ 修改前工作区全绿态）**: `pytest -q` **760 passed**（172 warnings，51.38s）/ `black --check core tests` **121 unchanged** / `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error**——零代码变更，读数与 P-034 终态一致。
- **提交与 CI**: 提交 `c8fa759`（3 文件 **+15/−2**，docs-only：PROGRESS §1.4 U-P024-2 done + U-P021-1 关闭指针 + P-035 行 + §3.40 / DESIGN_p034 D3 附则扩展注 / CHANGELOG 条目）→ CI run `43934945348` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.1 P-036 Step 1 调研（U-P024-3 mypy 检查面取证，2026-11-17）

- **触发**: 用户「启动 U-P024-3 mypy 检查面扩展取证批」；上游 = U-P024-3（检查面）/ U-P024-4（filter 21 errors）/ U-P024-1（版本上限）。
- **判档**: **T1**——SPEC_PROCESS 判档规则 2 强制升级（扩面 = 变更 CI 门禁判据；即便取证结论为「不扩面」，评估已触达门禁真值面），禁止降 T3。
- **取证环境**：主环境 mypy **2.1.0** / pandas 2.2.3 / py3.12.10；CI（run `43934945348` 安装日志实证）mypy **2.4.1** / pandas **3.1.1** / numpy 2.4.6 / pydantic 2.14.3；隔离复刻 venv `%TEMP%\p036ci2`（`pip install -e ".[dev]"`，版本与 CI 一致）。
- **保真校验（关键）**: 隔离 venv 原样复刻 CI 命令 `mypy --explicit-package-bases --check-untyped-defs core` → **`Success: no issues found in 37 source files`**，与 CI 日志逐字一致 → 扩面读数可信。
- **读数（CI 等价口径）**: 全候选 **129 errors / 25 files**（保留 `filter.*` 豁免则 **108 / 18**）；按目录 `agents` **94**（占 73%）/ `filter` 21 / `scripts` 5 / `cli.py` 3 / `strategy_evaluation` 3 / `order_strategy` 2 / `batch_backtest` 1；`core`(37) · `web`(9) · `factor_library`(2) **0**。错误码：`union-attr` **50** / `no-any-return` 34 / `var-annotated` 11 / 其余 34；Top 文件 `guru_agent_v2` 26 / `agent_framework` 17 / `universe_filter_clean` 13。
- **R1 机制实锤**: 同一配置仅换 mypy 版本——**2.1.0 下 `core` = 0；2.4.1 下 `core` = 21 errors / 7 files**（被 follow 的 `filter/` 错误计入）。**pandas 类型桩假设被证伪**：pandas 2.2.3 与 3.1.1 的 `py.typed` 均为 `False`，`dev` extras 无 `pandas-stubs`。
- **R2 归因更正**: P-024 的「X1-X4 已验证 mypy 2.1.0/2.4.1 均 0、根因 pandas 3.1.1 类型桩」**不成立**，方向相反；`filter.* ignore_errors` 实际掩盖的是 filter 自身的 21 条代码级错误。
- **R3 台账更正**: U-P024-4 前提重写（21 errors 与 pandas 版本无关）；U-P024-1 倾向由「不钉」改判为「钉上界」（版本漂移会改变门禁读数）。
- **R4 缺陷面**: 50 条 `union-attr` 为潜在 `AttributeError` 候选（样本含 `agent_framework.py` 6 处 `DataManager | None → .get_adj_price` / `UniverseFilter | None → .tradable`，与 P-029/P-031 缺陷同型）。
- **方案矩阵**: M-A 全量 / **M-B 两级分批（推荐：B1 小模块 14 + B2 agents 94 + B3 filter 21）** / M-C 仅钉版本 / M-D 扩面保留 filter 豁免；七项低效排除（含「`--follow-imports=silent` 治标」「统一 `# type: ignore`」「顺带 `strict=true`」）。
- **未决（四元块）**: U-P036-1 版本上界 / U-P036-2 filter 豁免处置 / U-P036-3 50 条 union-attr 是否全修 / U-P036-4 `tools`·`examples`·`demo`·`memory` 未覆盖。
- **产出**: [RESEARCH_p036](RESEARCH_p036_mypy_check_surface_expansion.md)（§1 四问 / §2 现状 / §3 环境矩阵 + 保真校验 / §4 两方案读数 / §5 R1-R5 + N1-N3 / §6 A-B-C 三级分类 50+30+46 / §7 方案矩阵 / §8 四元块 / §9 可重放命令 / §10 下一 Step）。
- **下一 Step**: **Step 2 Review（须异构基座）**——核验读数可重放性、R1/R2 对照实验、错误分级是否越界成结论。
- **代码面零变更**（本 Step 仅新增文档 + 台账行）；门禁读数不变 **760 / 121 / 37**。
- **提交与 CI**: 提交 `d8c1a3c`（2 文件 **+295/−3**：RESEARCH_p036 +274 / PROGRESS +21）→ CI run `43935418758` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.2 P-036 B0 子项实施（mypy 版本上界，2026-11-17）

- **触发/档位**: 用户裁决「先钉 mypy 上界」；依赖真值源变更 → **T1**（判档规则 2），作为 P-036 的 M-C 前置子项独立落地（Step 3/5/9/10 的 B0 面合并记录于 [RESEARCH_p036 §11](RESEARCH_p036_mypy_check_surface_expansion.md)）。
- **裁决**: 采纳 **`mypy~=2.4.1`**（`>=2.4.1,<2.5`）。拒绝 `<3.0`（2.x 内仍漂移，R1 已实证 2.1→2.4 改变读数）/ `==2.4.1`（冻结补丁）/ 维持无上限（D）。
- **变更面**: `pyproject.toml` 依赖行 + 三行注释（R1 锚点）；`[[tool.mypy.overrides]] filter.*` 注释更正（21 条为 filter 自身错误，非 pandas 类型桩，B3 修完移除）；`uv lock` mypy **2.1.0 → 2.4.1**（+`ast-serialize` 0.5.0→0.13.1 / `librt` 0.11.0→0.16.1，numstat **+240/−163**）；本机主环境同步升级 2.4.1。
- **验证（全绿）**: `uv lock --check` **exit 0**（148 packages）/ 门禁 `mypy core` **0 errors / 37 files** / **反证** `mypy filter` 直检 **21 errors / 7 files**（override 仍是门禁绿的唯一原因，非缺陷消失）/ `black --check core tests` **121 unchanged** / `pytest -q` **760 passed**（172 warnings，56.55s）。
- **台账**: U-P024-1 → **done**；U-P036-1 → **done**；U-P036-2~4 建行 pending（按 D5 纪律，本批新增 U-\* 全部建行）。
- **未做（显式）**: 门禁 target 未扩（仍 `core`）；`filter.*` 豁免未移除；`agents/` 等 129 条错误未触碰——留待 B1/B2/B3。
- **提交与 CI**: 提交 `76174c2`（6 文件 **+307/−167**：`pyproject.toml` +7/−2 / `uv.lock` +240/−163 / RESEARCH_p036 §11 +42 / PROGRESS +15/−2 / CHANGELOG +1 / ARCHITECTURE +2）→ CI run `43938329499` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.3 P-036 Step 2 异构 Review 记录（GLM-5.3-Flash，2026-11-17）

- **基座披露**: 复审基座 **GLM-5.3-Flash ≠ Step 1 作者 DeepSeek-V4.1-Flash** → **RULE-5 异构条件成立**（P-036 首个异构审查）。复审对象 = RESEARCH_p036 Step 1 版（`d8c1a3c`）+ B0 实施（`76174c2`）；复审时点 HEAD `ca7dd3e`。
- **E1 读数重放**: 保真校验 Success 37 files ✓；B 方案重放 **129 / 25 / 81** ✓；C 方案重放**不符**（129/25 ≠ 108/18）→ **F-S2-P036-1（P3）**：§4.2 C 方案读数是仓库 config（override 生效）口径，无 override 下 filter 21 条经 follow 仍渗入——「去目标 ≠ 去错误」，已回写 config 口径列 + 更正注（B3 移除 override 当天门禁新增 21 条须入 DESIGN 预期）。
- **E2 控变量闭合（新证，P2）**: **F-S2-P036-2**——R1「mypy 版本行为差异」被证伪。四象限实验（p036r1 = 2.1.0 / p036r2 = 2.4.1，numpy 钉 2.4.6，pandas 可切换，全部删 `.mypy_cache` 测量）：**r1/r2 四组合 `core` 无 override 均渗入 21 条**（pandas 2.2.3/3.1.1 二分无差）；主环境（2.4.1 + 2.2.3）fresh 恒 0 且 verbose 证实 filter 被解析——原「2.1.0 = 0」是主环境特有现象而非版本行为。site-packages 劫持 / 缓存 / MYPY_CACHE_DIR 逐一排除，机制未归因 → **U-P036-5 建行（O-P036-5）**。
- **E3 机械对账**: 错误码求和 = 129 ✓；分级 A50+B30+C46+3 = 129 ✓；M-B 分批 14+94+21 = 129 ✓；B0 后锁 / pyproject / 本地三方一致 ✓。
- **E4 缺陷面抽核**: R4 样本行（`agent_framework.py:1292/1334-1337` 等 union-attr）在重放输出中逐字存在 ✓。
- **E5 负向发现复核**: N1-N3 全部复现 ✓。
- **发现分级**: **1 P2（F-S2-P036-2）+ 3 P3（F-S2-P036-1 config 口径 / F-S2-P036-3 R2 的 X1-X3 口径澄清 / O-S2-P036-1 = O-P036-5 登记）+ 4 观察**（字母碰撞 / TEMP 工件被清理 / numpy 变量已控 / —），全部当轮处置，零丢弃。
- **R2' 强化**: filter 21 条为自身类型错误的结论**强化确认**（三环境直检恒 21）；P-024「X1-X3 均 0」口径澄清（含 override 读数至今成立，失实的是归因）；「pandas 类型桩」维持证伪（`.pyi` 文件数同为 41）。
- **B0 处置**: 钉版决策**保留**、理由改写为「锁 / CI / 本地三方一致 + 可复现性」；`pyproject.toml` 注释 / ARCHITECTURE §9.2 / CHANGELOG 条目 / 本档 U-P024-1、U-P036-1 行同步更正。
- **结论**: **pass（带 1 P2 当轮更正）**——Step 1 机械读数全部可重放、R2/R4 强化确认、方案矩阵不受影响；R1 归因更正已闭环。
- **下一 Step**: **Step 3 DESIGN**（B1/B2/B3 分批边界 + union-attr 修复策略裁决 + B3 移除 override 的 21 条预期登记 + O-P036-5 是否单独立项）。
- **提交与 CI**: 提交 `32e8fc9`（5 文件 **+103/−23**：RESEARCH_p036 §5 R1'/R2'/§4.2/§11/§12 +77/−14 / PROGRESS +20/−4 / pyproject 注释 +4/−3 / CHANGELOG +1/−1 / ARCHITECTURE +1/−1）→ CI run `43939440126` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.4 P-036 Step 3 DESIGN（2026-11-17）

- **基座**: DeepSeek-V4.1-Flash（Step 4 Review 须异构）；产出 [DESIGN_p036](DESIGN_p036_mypy_check_surface_expansion.md)；代码证据时点 HEAD `775358c`（B0 已落地）。
- **F-D3-P036-1（P2，设计期新发现）**: **读数对 pandas 版本敏感 2 条**——CI 口径（pandas 3.1.1）**129** vs 本地（2.2.3）**131**，差异 = `no-any-return` 34→38 / `call-overload` 4→2（全在 `agents/`）。Step 1/2 均按单一口径记录未识别该变量；若按 129 修到 0，本地可能残留 2 条。→ **D1 固定双口径验证**（判据以 CI 口径为准，每批双口径复跑），登记 O-D3-P036-1。
- **设计决策**: **D1** 双口径基线（129/131）；**D2** 三批边界（B1 小模块 14 / B2 `agents` 96 / B3 `filter` 21 + 去 override）+ 最终 target 10 面（含零成本的 `web`/`factor_library` 防回归）；**D3** 修复四层策略（L1 根因收窄 > L2 访问点窄化 > L3 注解修正 > L4 受限 ignore ≤3 且禁裸 ignore）；**D4** 行为变更裁决（U-a 已有前提→`assert` 零行为变更 / U-b 无前提→默认值优先、`raise` 须单列验收）；**D5** override 移除与 B3 原子绑定（前置：`mypy filter`=0 且移除后 `mypy core` 仍 0）；**D6** O-P036-5 不立项；**D7** 不引入 `warn_unused_ignores` / `strict`。
- **根因聚类（F-D3-P036-2）**: 131 条 ≈ **87 簇**（行距 ≤5 估算）；**2 个根因占 36 条（27%）**——`guru_agent_v2.guru_data: Optional[dict]` 26 条 1 处守卫可消 / `universe_filter_clean` 的 3 个 `_*_mask` 属性 12 条。按条数估工作量会高估。
- **红态实测（@`775358c`，本地口径）**: B1 面 **14 errors / 7 files（31 source files）** / B2 `agents` **96 / 11（14）** / B3 `filter` **21 / 7（10）**；`web`·`factor_library` 现状 0（纳入 target 属回归保护，不计红态）。
- **不变式与契约**: I1 golden 零重录 / I2 公开签名零变更 / I3 `except Exception` 恒 22 / I4 pytest 不减 / I5 代码与 target 同批原子提交 / I6 双口径 0 / I7 裸 ignore = 0、带 code ≤3；V1-V6 对应三批 + 最终门禁 + 行为守恒 + 忽略审计。
- **风险**: R-P036-1 根因收窄引入 `raise`/早退属行为变更 / R-P036-2 `cast` 掩盖 Any 传播 / R-P036-3 双口径不同步 / **R-P036-4 B2 96 条可能藏真实缺陷（`agent_framework.py` 的 `DataManager | None` 解引用），允许升级为缺陷修复批**。
- **下一 Step**: **Step 4 设计 Review（须异构基座）**——核验 D1 双口径读数、D3 分层可执行性、D4 裁决边界、V1-V6 可复现性。
- **代码面零变更**（本 Step 仅新增设计文档 + 台账行）。
- **提交与 CI**: 提交 `f99a938`（2 文件 **+190/−1**：DESIGN_p036 +177 / PROGRESS +13/−1）→ CI run `43943952688` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.5 P-036 Step 4 设计 Review 记录（GLM-5.3-Flash，2026-11-17）

- **基座披露**: 复审基座 **GLM-5.3-Flash ≠ Step 3 设计作者 DeepSeek-V4.1-Flash** → **RULE-5 异构成立**。复审对象 = [DESIGN_p036](DESIGN_p036_mypy_check_surface_expansion.md) Step 3 版（`f99a938`）+ 上游 RESEARCH §5/§11/§12 + B0 落地；复审时点 HEAD `74c45f0`。
- **E1 双口径重放**: 本地口径（pandas 2.2.3 + numpy 2.4.6）重放 = **131 errors / 25 files** ✓；「CI 口径」重放（p036r2，pandas 3.1.1 + **numpy 2.4.6**）= **131**（非 Step 3 记录的 129）→ 触发 E4 二分。
- **E2 关键分类读码**: `agents/guru_agent_v2.py` L185-188 构造期守卫实锤（`if self.guru_data is None: raise ValueError(f"未知Guru: {guru_id}...")`）——guru_data 的 25 条解引用（union-attr 24 + index 1 @L330）**全部 U-a**，L2 assert 零行为变更可消（Step 3 误举为 U-b）；L452 为独立 pandas 无桩噪音；`filter/universe_filter_clean.py` `build_masks()` 副作用赋值确认（12 条 mask 解引用同属 U-a）。
- **E4 numpy 二分（新证）**: p036r2 固定 pandas 3.1.1 仅换 numpy——**2.4.6 = 131 / 2.5.5 = 129** → 锁定差异变量为 **numpy 桩版本**（numpy 有 `py.typed` 桩内容随版本变；pandas 两版均无 `py.typed` 恒 Any，`.pyi` 文件数同为 41）；CI 安装日志实证 numpy = 2.4.6 → **真 CI 口径 = 131 = 本地，双口径收敛**。
- **E3 机械对账**: 14 + 96 + 21 = **131** ✓；D2 表「96（本地 98）」的「98」为笔误（实锤不存在）；根因计数不一致实锤（26 / 36 → 读码定论 25 + 12 = **37**）。
- **E5 既有约束复核**: D3 四层 / D5 绑定条件 / D6-D7 / I1-I7 / V1-V6 全过，未改动；V1-V3 红态读数与 E1 重放一致（B1 14 / B2 96 / B3 21）。
- **发现分级（全部当轮回写 DESIGN）**: **F-S4-P036-4（P2）** F-D3-P036-1 的 pandas 归因证伪 → D1 全节改写（复刻 venv 钉 `numpy==2.4.6`）+ O-D3-P036-1 改判 + R-P036-3 更正；**F-S4-P036-3（P2）** D4 分类与裁决原则错误（U-b 例子选错 + 原「优先默认值」会在现网崩溃场景引入静默降级，违反 P-025 F-D3-P025-1 先例）→ D4 全节改写（现网崩溃 → 保持 fail-fast，禁止默认值降级）+ R-P036-1 更正；F-S4-P036-1（P3）D2 表「本地 98」笔误更正；F-S4-P036-2（P3）根因计数 37 更正（O-D3-P036-3 + §7 F-D3-P036-2 行）；1 观察（L452 佐证 pandas 无桩噪音机制）。
- **结论**: **pass（2 P2 + 2 P3 当轮更正）**；详见 [DESIGN_p036 §9](DESIGN_p036_mypy_check_surface_expansion.md)。
- **台账同步**: U-P024-3 行 129 读数追加更正注；U-P024-4 行 follow 表述维持 Step 2 更正（Step 4 的 numpy 改判不涉 filter 21 条归因）。
- **代码面零变更**（本 Step 仅文档回写）。
- **提交与 CI**: 提交 `de2f122`（2 文件 **+84/−22**：DESIGN_p036 +68/−20 / PROGRESS +16/−2）→ CI run `43947344164` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.6 P-036 Step 5 IMPL（2026-11-17）

- **基座**: DeepSeek-V4.1-Flash（Step 6 实施 Review 须异构）；产出 [IMPL_p036](IMPL_p036_mypy_check_surface_expansion.md)；基线 HEAD `65da5f9`。
- **红态实测（@`65da5f9`，本地 pandas 2.2.3 + numpy 2.4.6，mypy 2.4.1）**: B1 面 **14 errors / 7 files（checked 68）**；`agents` **96 / 11（14）**；`filter`（无 override）**21 / 7（10）**——与 DESIGN §4/§5 逐字一致（14+96+21 = **131**）。
- **B1 错误码分布（实测）**: no-any-return 6 / union-attr 3 / assignment 3 / arg-type 1 / func-returns-value 1。
- **B2 分文件计数（实测）**: guru 26 / agent_framework 17 / strategy_allocator 9 / assumption_monitor 9 / auto_parameter_optimizer 8 / style_reflection_engine 8 / multi_strategy_engine 6 / style_drift_analysis 5 / sentiment_framework 5 / hierarchical_bayesian_agent 2 / research_team_v2 1 = **96**。
- **变更规格**: B1 14 条逐条（§4.2）/ B2 96 条按 11 文件簇（§4.3）/ B3 21 条逐条（§4.4）；`tests.yml` mypy 行三阶段扩面（8 → 9 → 10 面）。
- **行为变更清单（4 项，CHECKLIST 单列验收）**: **C1** `BatchBacktestEngine.run_factors` 加 fail-fast（U-b → ValueError，与 `run_all_factors` 逐字一致）；**C2** `multi_strategy_engine:973` `tracker.cash` → `_cash`（现网 AttributeError，真实缺陷）；**C3** `research_team_v2:260` 删 `period=period`（现网 TypeError，真实缺陷）；**C4** `agent_framework:1386/1401` `int(trade_qty)`（float→int，数量本为 100 倍数）。其余 127 条零行为变更（注解 / 局部变量 / U-a assert）。
- **I2 口径澄清（F-I-P036-1）**: `def` 行仅允许**返回注解**差异（5 处：`verify_case` / `_weighted_vote` / `_confidence_weighted` / `create_filter` / `NAFactorFilter.__init__`），参数名 / 默认值 / 函数名逐字不变。
- **裁决**: L4（`# type: ignore`）全程 **0 使用**；`guru_data` 25 条由构造期既有守卫处**一处收窄**全消（零行为变更，D4 Step 4 定论的直接落地）；B3 的 12 条 mask 解引用由 `build_masks()` 副作用前提 + L2 `assert` 收窄。
- **测试**: **不新增 pytest（I4 的 X=0）**——判据 = mypy 退出码 + 全量 760 + golden 13 + C1-C4 的 `%TEMP%` 探针留证。
- **代码面零变更**（本 Step 仅新增 IMPL 文档 + 台账）。
- **提交与 CI**: 提交 `ec33dd7`（2 文件 **+339/−1**：IMPL_p036 +324/−0 / PROGRESS +15/−1）→ CI run [`44021229549`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44021229549) **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.7 P-036 Step 6 实施 Review 记录（GLM-5.3-Flash，2026-11-17）

- **基座披露**: 复审基座 **GLM-5.3-Flash ≠ IMPL 作者 DeepSeek-V4.1-Flash** → **RULE-5 异构成立**。复审对象 = [IMPL_p036](IMPL_p036_mypy_check_surface_expansion.md) Step 5 版（`ec33dd7`）；复审时点 HEAD `b277313`（代码零变更，纯规格复审）。
- **E2 门禁基线独立复测**: pytest **760 passed**（82.98s）/ black **121 unchanged** / mypy core **0（37 files）** / pyproject override 块在位（L121-123 + 注释 L116-120 为 B3 待删面）——全一致。
- **E3 红态三批复测**: B1 **14 / 7 files（checked 68）**、agents **96 / 11（14）**、filter（无 override）**21 / 7（10）**——与 IMPL §5 逐字一致（合计 131）。
- **E4 七项裁决**: ① 锚点（B1 14 条全命中 / B2 计数对账一致 / B3 分组错误 1 处）；② 分层合规成立（全部 L2 assert 前提可指认——`engine.dm`/`self.universe` 由 setup 赋值、`allocator` 由 enable_dynamic_allocation 分支赋值、`build_masks` 副作用、`baseline_profile` 构造期 L539 恒调；L1 仅 C1；L4 = 0）；③ C1-C4 全部读码复现（`run_all_factors` L81-82 逐字源 / tracker 仅 `_cash` / `update_belief` 无 `period` / `current_qty` float）；④ I2 清单 5 → **8 处 def 行 + 1 处参数注解**；⑤ 红态逐字复现；⑥ 门禁链与 D2 一致、无 `|| true`；⑦ B3 绑定顺序与 D5 一致。
- **发现分级（全部当轮回写 IMPL）**: **F-S6-P036-1（P2）** §4.4.1 方法归属错误——L522/526 属 **`filter_stocks`**（L498-531）非 `get_universe_stats`（后者实为 4 条），原修复规格漏 filter_stocks 2 条 → 当轮补规格（L520 后 `assert mask is not None`）；**F-S6-P036-2（P2）** 三个 filter 工厂函数（`create_na_filter` / `create_market_cap_filter` / `create_industry_filter`）字典混入 `BaseFilter` 子类，仅改字典注解会引入 return-value 新错 → **返回注解须同批改 `-> BaseFilter`**，I2 清单 5 → 8 处（且 `NAFactorFilter.__init__` 归类为参数注解）；F-S6-P036-3~6（P3）——`create_prefix_filter` 实名更正 / `-> np.ndarray | None`（PEP 604 零 import）/ L587 `base_config.universe` + L909 dict 推导式笔误 / `UniverseFilterConfig` import 追加注——均当轮更正；3 观察（**F-I-P036-3/4 闭合**：baseline_profile 构造期前提实锤 → L250 = U-a；CrossSectionalNAFilter 混入实锤；agents 13 文件 `Any` 全部已导入）。
- **结论**: **pass（0 P0/P1，2 P2 + 4 P3 当轮回写）**；详见 [IMPL_p036 §11](IMPL_p036_mypy_check_surface_expansion.md)。Step 9 可按更正后规格直接落码。
- **提交与 CI**: 提交 `61876a9`（2 文件 **+102/−19**：IMPL_p036 +91/−18——§11 复审记录 + §1/§4/§8/§9 回写 / PROGRESS +11/−1）→ CI run [`44023440112`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44023440112) **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.8 P-036 Step 7 CHECKLIST（2026-11-17）

- **基座**: DeepSeek-V4.1-Flash（Step 8 一致性 Review 须异构）；产出 [CHECKLIST_p036](CHECKLIST_p036_mypy_check_surface_expansion.md)；代码证据时点 HEAD `65da5f9`。
- **六组 65 项零预填（机械计数）**: **A** B1 14 条 12 项 / **B** B2 96 条 14 项（按 11 文件簇）/ **C** B3 21 条 11 项（含 override 删除 D5 三条件）/ **D** 行为变更 C1-C4 8 项（含 D5 新增 raise 清单、D6 零默认值降级、D7 8 处注解差异）/ **E** 不变式 I1-I7 + V1-V6 10 项 / **F** 门禁链与治理 10 项。
- **Step 7 基线实测（本 Step 独立复核）**: pytest **760 passed** / `tests/` .py **84**（`test_*.py` 81）/ golden **13 用例**（7 份 json）/ black **121 unchanged** / mypy `core` **0（37 files）** / `except Exception`（P-029 口径：`agents`+`filter`+`scripts`+`batch_backtest`+`strategy_evaluation` 全 `.py` + `cli.py`）= **22** / `uv lock --check` **exit 0**。
- **目标读数（Step 9）**: pytest **760**（X=0）/ .py **84 不变** / black **121 不变** / mypy **8 → 9 → 10 面**均 0 / golden 13 零重录 / AST 22 / 裸 + 带 code ignore 均 **0**。
- **红态纪律**: 三批 Step 9 首跑须出示修复前读数（B1 `14/7/68`、B2 `96/11/14`、B3 `21/7/10`）；`web`/`factor_library` 现状 0 属回归保护不计红态。
- **RULE-1 零预填**: 65 单元格全 `[待 Step 9]`；`[待 Step 9]` 全文机械匹配 **68** = 65 单元格 + 头部规则行 1 + §7 回填行 1 + 账目行 1（已核验）。
- **ID 防混用**: DESIGN 决策 `D1-D7` vs CHECKLIST **D 组**（行为变更）——引用一律 `DESIGN-D*`。
- **代码面零变更**（本 Step 仅新增 CHECKLIST + 台账）。
- **提交与 CI**: 提交 `97840dd`（2 文件 **+174/−1**：CHECKLIST_p036 +161/−0 / PROGRESS +13/−1）→ CI run [`44024144262`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44024144262) **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.9 P-036 Step 8 一致性 Review 记录（GLM-5.3-Flash，2026-11-17）

- **基座披露**: 复审基座 **GLM-5.3-Flash ≠ CHECKLIST 作者 DeepSeek-V4.1-Flash** → **RULE-5 异构成立**。复审对象 = [CHECKLIST_p036](CHECKLIST_p036_mypy_check_surface_expansion.md) Step 7 版（`97840dd`）+ IMPL（`61876a9`）/ DESIGN / RESEARCH；复审时点 HEAD `0d9876c`。
- **机械五项全过**: ① 链接 6 条 **0 broken**（1 处伪命中 = IMPL L214 代码片段 `(**kwargs)` 被正则误判，人工判定，P-034 先例同型）；② ID 闭环表行 **65**（六组连续无跳号）；③ 计数自洽 65 = 12+14+11+8+10+10；④ 零预填 `[待 Step 9]` = **68**（65 单元格 + 3 正文，`✅`/`❌` 预填 0）；⑤ 角色引用异构成立。
- **对齐矩阵六项**: ① **131 = 14+96+21** 三处一致（DESIGN §2/§9 / IMPL §2/§11 / CHECKLIST 头部+A10+B13+C11）✓；② **B2 分文件计数** 26/17/9/9/8/8/6/5/5/2/1 在 IMPL §4.3.1-11 / CHECKLIST B2-B12 逐项一致（求和 96）✓；③ **B3 方法归属** filter_stocks 2 / get_universe_stats 4 / get_mask_summary 6（+L108 = 13；13+1+2+4+1 = 21）在 IMPL §4.4.1 / CHECKLIST C2-C5 逐字一致 ✓；④ **注解差异清单**发现 1 处口径精度问题（见下）⚠️ 当轮精化；⑤ **C1-C4** 在 IMPL §1 表 / CHECKLIST D1-D4 逐项对应 ✓；⑥ **门禁链** 760/84/121/8→9→10 面 0/13/22/uv 0 三文档逐字一致 ✓。
- **发现分级**: **F-S8-P036-1（P3）** 「8 处 def 行」口径不精确——`NAFactorFilter.__init__` 参数注解位于**续行 L33**（非 def 行 L31），其修改不触 def 行，机械判据 `^-\s*def ` 实际 = **7**（仅返回注解）；原表述会使 Step 9 核对出现 7 ≠ 8 假性失败 → **当轮精化三处**（IMPL §1 前提 4 / CHECKLIST D7 证据出口 / CHECKLIST E2 改为「7 处 def 行 + 1 处参数注解行」）；2 观察（链接伪命中人工判定 / CHECKLIST 头部基线时点精度注记——`1261865`/`b277313`/`65da5f9` 三者代码面相同）。
- **结论**: **pass（0 P0/P1，1 P3 当轮精化）**；详见 [CHECKLIST_p036 §9](CHECKLIST_p036_mypy_check_surface_expansion.md)。Step 9 按更正后 D7 口径执行。
- **提交与 CI**: 提交 `6349a5c`（3 文件 **+60/−4**：CHECKLIST_p036 +49/−2——§9 复审记录 + D7/E2 精化 / IMPL_p036 +1/−1——§1 前提 4 精化 / PROGRESS +10/−1）→ CI run [`44025817190`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44025817190) **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。

### 3.41.10 P-036 Step 9 B1（mypy 8 面，14 条，2026-11-17）

- **基座**: DeepSeek-V4.1-Flash（Step 9 实施；Step 10 终审须异构）；实施基点 `65da5f9`。
- **红→绿**: `Found 14 errors in 7 files (checked 68 source files)` → `Success: no issues found in 68 source files`。
- **修复面（7 文件 14 条）**: `strategy_evaluation/evaluator.py`（`row: dict[str, Any]`）/ `strategy_evaluation/stats.py`（`half_life: float` / `turnover: float`）/ `order_strategy/strategies.py`（`fill_timestamps: list | None` / `total_impact: float`）/ `scripts/external_benchmark/verify_p015.py`（`verify_case` 返回注解 `-> np.ndarray | None`，三错同根）/ `scripts/external_benchmark/_spec.py`（`s` / `abs_s` 局部注解 + `np.asarray` 返回）/ `batch_backtest/engine.py`（**C1** fail-fast 守卫）/ `cli.py`（`factor_weights={}` + `dm` 断言收窄）。
- **次生修改（批内闭合）**: `fill_timestamps` union 化后 3 处 `.append` union-attr → L168/249/320 各加 `assert order.fill_timestamps is not None`；`verify_case` 注解改 union 后 L124 必须 `return None` + L119/223 `np.asarray(pv_v3)`（F-S9-P036-3）；`_run_single_factor` 独立 `assert self.factor_db is not None`。
- **门禁（本机）**: pytest **760**（首跑曾因 F-S9-P036-1 双载体遗漏 1 failed，同步 `scripts/spec_runner_adapter.py` 后恢复）/ golden 13 / black 121 / AST 22 / diff `^-\s*def ` = 7、`^\+.*except` = 0、`^\+.*raise ` = 1（C1）。
- **提交与 CI**: `e2dafff`（9 文件 **+27/−18**：7 代码 + tests.yml + adapter）→ CI run `44026780449` **failure**（mypy step，3.12 numpy 2.5.5 cumsum，F-S9-P036-2；终态由 `43ed468`+`f1fdab4` 闭合，见 §3.41.13）。

### 3.41.11 P-036 Step 9 B2（mypy 9 面，96 条，2026-11-17）

- **红→绿**: `Found 96 errors in 11 files (checked 14 source files)` → 9 面 `Success: no issues found in 82 source files`。
- **修复面（11 文件 96 条）**: `guru_agent_v2.py` **25 条一处收窄**（局部 `guru_data` + 既有 `raise` 原样 + `self.guru_data: dict[Any, Any]`）+ L453 `bool(...)`；`agent_framework.py` 17 条（`bool` ×4 / 返回注解 union ×2 / `value: str` / `from_universe_config` / `assert` 三组 / **C4** `int(trade_qty)` ×2 / `results: dict[str, Any]`）；`style_reflection_engine.py` 8 条一处根因；`strategy_allocator.py` 9 条（`np.asarray` ×8 + `inspect.signature(allocator_cls)`）；`sentiment_framework.py` 5 条；`auto_parameter_optimizer.py` 8 条（**落点更正 F-S9-P036-5**：`roles: list[Any]` 置首次定义 L947）；`assumption_monitor.py` 9 条；`multi_strategy_engine.py` 6 条（含 **C2** `tracker._cash`）；`style_drift_analysis.py` 5 条；`hierarchical_bayesian_agent.py` 2 条；`research_team_v2.py` 1 条（**C3** 删 `period=period`）。
- **行为变更探针**: C2 —— 原以为 `AttributeError`，实测为**静默影子属性**（`hasattr` 写后 True、`get_cash()` 不变 100000，调资静默失效）；改 `_cash` 后 `get_cash()=42000.0`（F-S9-P036-4，P2 口径更正）；C3 —— `update_belief` 签名无 `period`，旧调用 `TypeError`、新调用 bind OK；C4 —— `33378.9 → 33378`，`_execute_trade` quantity 注解 int。
- **门禁**: pytest **760** / golden 13 / black 121 / AST 22；9 面无 `^\+.*except`。
- **提交与 CI**: `e781b75`（13 文件 **+82/−61**）→ CI run `44027975513` **failure**（mypy step，同 F-S9-P036-2；终态 §3.41.13）。

### 3.41.12 P-036 Step 9 B3（mypy 10 面 + 删 override，21 条，2026-11-17）

- **红→绿（无 override ini 直检）**: `Found 21 errors in 7 files (checked 10 source files)` → 10 面 `Success: no issues found in 92 source files`。
- **修复面（7 文件 21 条）**: `universe_filter_clean.py` 13 条（`_prefix_info: dict[str, bool]` + `filter_stocks` 1 条 assert + `get_universe_stats` / `get_mask_summary` 三局部 + 合并 assert，**实现细化 F-S9-P036-7**）；`prefix.py` / `na_factor.py` / `market_cap.py` / `industry.py` 返回注解 `-> BaseFilter` + 工厂 dict 注解；`extended.py` / `custom.py` dict 注解 + `filter_obj: BaseFilter`（置首赋值 L192）；`na_factor.py` 另删已无引用的 `Literal` import。
- **override 删除（DESIGN-D5 三条件顺序执行）**: 无 override ini `mypy filter` = 0 → 删 `pyproject.toml` L116-123 整块 → `mypy core` 仍 = `Success: no issues found in 37 source files`；`Grep "filter\.\*"` = 0。
- **门禁**: pytest **760** / golden 13 / black 121（`.` 188）/ AST 22 / diff `^-\s*def ` = 7（+1 参数注解行）。
- **提交与 CI**: `eb3ae55`（10 文件 **+36/−34**：7 filter + pyproject + tests.yml + adapter）→ CI run `44028421866` **failure**（mypy step，`web/05_Performance.py:48` cumsum；终态 §3.41.13）。

### 3.41.13 P-036 Step 9 CI 桩兼容修复与终态复绿（2026-11-17）

- **根因（F-S9-P036-2，P2）**: CI 依赖未钉版本，运行时解析与本地「双口径 2.4.6」不同——3.12 leg 装 **numpy 2.5.5**（零参 `ndarray.cumsum()` 桩报 `call-overload` 3 条：`web/05_Performance.py:48` / `agents/auto_parameter_optimizer.py:929` / `agents/research_team_v2.py:1029`）；3.10 leg 装 **numpy 2.2.6** + pandas 2.3.3（形状/标量更严 7 条：`_spec.py:83` 形状重赋值、`strategy_allocator.py:570/571`、`hierarchical_bayesian_agent.py:219`、`assumption_monitor.py:363/472/646`）。
- **修复一（`43ed468`）**: 3 处零参 `.cumsum()` → `np.cumsum(...)`（实测 `x.cumsum(axis=None)` 在 2.5.5 桩下亦不可用）；复刻 venv `%TEMP%\p036r2`（py3.12 + numpy 2.5.5 + mypy 2.4.1）复现并验证。CI run `44028763627`：3.10 leg 仍红 / 3.12 cancelled / 3.11 + lock-check success。
- **修复二（`f1fdab4`）**: 6 处形状/标量收窄——`_spec.py` `close: np.ndarray = np.full((t, 2), np.nan)` / `strategy_allocator.py` `samples: np.ndarray = np.zeros(n)` / `hierarchical_bayesian_agent.py` `stability: float = max(0.0, 1.0 - float(std) * 5)`（使 TypeVar 绑定 float，原 `max(0, 1 - std*5)` 仍报 arg-type）/ `assumption_monitor.py` 三处 `float(...)` 标量收口。复刻 venv `%TEMP%\p036r310`（uv 安装 py3.10.20 + numpy 2.2.6 + pandas 2.3.3 + pydantic 2.14.3 + mypy 2.4.1；numpy 2.5.5 要求 py≥3.12）逐条复现后修复。
- **门禁终态（`f1fdab4`）**: mypy 10 面**三口径均 0**（92 files：本机 3.12+2.4.6 / 3.12+2.5.5 / 3.10+2.2.6）/ `mypy core` 0（37）/ pytest **760** / golden **13**（`747 deselected`，`tests/golden/` 无改动）/ black **121**（`.` 188）/ AST **22** / `uv lock --check` exit 0 / tests 84、`test_*.py` 81 / 新增 `# type: ignore` **0**（既有带 code 4 处，F-S9-P036-6 口径更正）。
- **CI**: `f1fdab4` run [`44029888652`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44029888652) **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿）。
- **文档提交与 CI**: `191bbf8`（4 文件 **+212/−76**：CHECKLIST_p036 +§10/F4/§7 回填 / IMPL_p036 §12 / PROGRESS §3.41.10-§3.41.13 + §1.4 / CHANGELOG Fixed+CI 两条）→ CI run [`44030760894`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44030760894) **success**（四 job 全绿）；P-036 四文档链接校验仅 2 处代码片段伪命中（`(**kwargs)`，O-S8-P036-1 同型），真实链接 0 broken。
- **Step 9 实施期发现**: F-S9-P036-1（P2 双载体遗漏）/ -2（P2 CI 桩版本）/ -3（P3 §4.2 #6 注失实）/ -4（P2 C2 静默影子属性口径更正）/ -5（P3 roles 落点）/ -6（P3 ignore 口径）/ -7（P3 B3 实现细化）——详见 [IMPL_p036 §12.4](IMPL_p036_mypy_check_surface_expansion.md) 与 [CHECKLIST_p036 §10](CHECKLIST_p036_mypy_check_surface_expansion.md)。

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
