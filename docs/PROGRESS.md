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
| U-P021-1 | CI 增加 `uv lock --check` 门禁 | [RESEARCH_p021 §6](RESEARCH_p021_dependency_lock_maintenance.md)；CI 当前 `pip install ".[dev]"`，锁不参与安装；本地 `--check` 已归零但不约束提交 | pending（条件触发：锁再次漂移或引入 uv 安装路径） | P3 |
| U-P021-2 | `numba` 依赖声明 | [RESEARCH_p021 §6](RESEARCH_p021_dependency_lock_maintenance.md)；未声明；缺失时降级 `py_func`；CI 无 JIT 覆盖（与 U-008 同源） | pending（条件触发：CI 需覆盖 JIT 或出现性能回归） | P3 |
| U-P021-3 | 锁升级节奏 | [RESEARCH_p021 §6](RESEARCH_p021_dependency_lock_maintenance.md)；本批只补缺不升级（plain `uv lock`），既有 pin 保持 2026 年旧值 | pending（条件触发：安全通告 / 显式升级需求） | P3 |
| U-P023-1 | `run()` 逐日 `except Exception: continue` 的 retry 语义 | [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)；P-007 RESEARCH A26 已登记 `Catch Generic` 反模式 | **done（2026-11-13 由 P-025 承接并完成）**：触发条件经 P-025 Step 1 取证改判为**已成立**（探针 B2：`min_variance` + `cov_lookback=60` → 0 成交 / sharpe 0.0 / 零诊断）；P-025 落地三处统一采集 + `run_diagnostics` + `day_error_mode` 三态 + D7-O2 setup 预检，探针 B2 现由 setup 直接拦截，详见 [CHECKLIST_p025](CHECKLIST_p025_daily_loop_exception_semantics.md) | P3 |
| U-P025-1 | `EventLog` 接入引擎作为统一事件通道 | `run_diagnostics` 已落地且有第二个消费方（web/批处理）需要事件流 | pending（条件触发，本批不接入） | P3 |
| U-P025-2 | `EngineV3Vector` 是否需要同形诊断 | V3 出现「静默空结果」实例 | pending（条件触发；V3 单次向量求值无日循环） | P3 |
| U-P025-3 | 其余 22 处 `except Exception` 治理 | 其中任一处产生可复现的静默错误 | pending（本批出界，按模块分批） | P3 |
| U-P025-4 | 优化失败时退化为等权（而非跳过调仓） | — | **已裁决不做**：静默降级会掩盖配置错误（正是 F-D3-P025-1 的成因） | P3 |
| U-P025-5 | `ExceptionGroup`（raise 模式）与 3.10 分支实现 | DESIGN 阶段确认最低版本 3.10 | **done**：3.11+ `getattr(builtins,"ExceptionGroup")` / 3.10 `RuntimeError`；T7 版本分支断言 + CI 3.10 job 覆盖 | P3 |
| U-P025-6 | 末日重复快照治理（`_force_liquidation` 末日二次 `update_market_values`） | 需要精确交易日数统计 / golden 有意重录 | pending（本批不动；A3 复跑 21 快照 / 20 去重日，golden 依赖该形态） | P3 |
| U-P023-2 | `--check-untyped-defs` 是否纳入门禁 | [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)；原倾向「不纳入」 | **done（2026-11-12 由 P-024 承接）**：CI 与 adapter 双侧统一纳入，残差 0 | P3 |
| U-P023-3 | 零交易日回测的合法形态 | [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)；`_generate_results` 空快照守卫已统一 fail-fast（不区分原因） | pending（条件触发：真实数据出现空交易日集） | P3 |
| U-P023-4 | `EngineV3Vector` 信号路径 | [RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)；P-024 取证：无因子时 `_precompute_signals` 用收盘价动量回填（非 `None`）+ `run()` 有 `dl is None` 守卫 → 无同形缺陷 | **done（2026-11-12 由 P-024 承接）**：[RESEARCH_p024 P12](RESEARCH_p024_ci_gate_alignment.md) | P3 |
| U-P024-1 | mypy 版本上限（`mypy>=1.5.0` 无上限） | [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)；CI 三版本各自回溯解析 | pending（倾向不钉）。**2026-11-12 注记（P-024）**：Step 9 一度判为「已触发」并提交 `745e2b7` 钉 `~=2.1.0`，经 X1-X4 隔离实验证伪——差异实为 **pandas 3.1.1 类型桩**；钉版已撤回，本项维持 pending | P3 |
| U-P024-2 | CI 增加 `uv lock --check` 门禁 | [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)；与 U-P021-1 同源，本批不重复承接 | pending（条件触发：锁再次漂移或 CI 改 uv 安装） | P3 |
| U-P024-3 | mypy 检查面扩展（`cli.py`/`agents`/`web`/`scripts`） | [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)；本批只对齐口径，target 仍为 `core` | pending（条件触发：`core` 外类型事故 / 全仓治理需求） | P3 |
| U-P024-4 | `filter/` 在 pandas 3.x 下的 21 errors | [RESEARCH_p024 §6](RESEARCH_p024_ci_gate_alignment.md)；CI 依赖集（pandas 3.1.1）实测 21 errors / 7 files（`universe_filter_clean.py` 13）；本批以 `filter.* ignore_errors` 声明越界 | pending（条件触发：`filter/` 纳入门禁 / 需钉 pandas 上限） | P3 |
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
| U-008 | numba JIT 路径在 CI 有覆盖 | CI 出现 numba 相关回归却无法拦截 | 暂不新增 optional job；以 C1（`importorskip`）保留本地执行，后续按需评估 | E1（`pyproject.toml` 无 numba） |

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

### 3.31 P-026（静默失败治理第二批 · U-P025-3）执行记录（2026-11-13，Step 1-6 完成 · T1）

- **立项**: U-P025-3 承接（触发条件「其中任一处产生可复现的静默错误」经 Step 1 读码**实证成立**）；档位 **T1**（`core/` 行为契约 + 结果/返回值新增可观测字段）；代码证据时点 HEAD `7ff7a4d`
- **Step 1 候选池实测（E1）**: 全仓 `except Exception` **49 处**——`core/` 27 / `agents/` 11 / `filter/` 5 / `scripts/` 2 / `batch_backtest/` 2 / `strategy_evaluation/` 1 / `cli.py` 1；core 27 = 已埋点 3（engine_v2 ×2 + execution ×1）+ 采集器兜底 2（diagnostics）+ **待评估 22**
- **Step 1 逐点裁决（22 处全覆盖）**: **K 保持 8**（`data.py` ×3 记录后重抛 / `event_log` listener 隔离 ×2 + 恢复 warning + 快捷函数 / `walk_forward` 回调隔离）/ **D 升级诊断 10** / **F fail-fast 0** / **排除 4**（`config_v2` ×3 冻结且形态正确 / `execution` L251 P-025 已裁正确降级）
- **Step 1 三处 P2 实证（读码）**: ① `factor.py` L344 `except Exception: continue` **零日志**（去常数列失败 → 该日中性化整体跳过 → 信号缺失）；② `engine_plugins.py` L235 Guard 异常 **fail-open**（`return True, []`，异常不计入既有 `_blocked_count`/`_warning_count`）；③ `walk_forward_engine.py` L185 `set_period` 失败仅 warning（窗口以**错误期间模式**运行且无字段标记）
- **Step 1 辅助发现**: `engine_plugins.py` L161 为 **`debug` 级**（A3 铁证 root logger 默认 WARNING → 默认不可见）；`event_log` L160 读取失败返回空列表（**「无事件」与「读失败」不可区分**）；`global_contagion` L433/L447 **零日志**兜底、L589 假阴性不可区分；静默路径测试覆盖近零（9 关键词中 7 项 0 命中）
- **方案矩阵**: 5 案（M-A 逐点三态分级显形 / M-B 仅提日志级别 / M-C 全局注册表 / M-D 全量 fail-fast / M-E 维持）选 **M-A**——延续 P-025「显式静默 vs 未声明静默」判据（PEP 20 后句）、复用 sink 注入先例（P-025 D5）、**零全局状态**、本批 0 项 fail-fast
- **外部锚点（4 项全 T1 命中，2026-11-13 直读）**: PEP 20「Errors should never pass silently. Unless explicitly silenced.」/ CWE-390「detects a specific error, but takes no actions」/ Python logging 文档「root logger is created with level WARNING」/ AWS Builders' Library「almost always prefer alternatives to fallback」
- **未决项**: U-P026-1（EventLog 写盘失败是否 fail-fast，倾向只计量）/ U-P026-2（contagion `degraded` 字段粒度）/ U-P026-3（core 外 22 处后续分批）/ U-P026-4（listener 限流，不做）/ U-P026-5（是否建全局采集器，本批不建）
- **批次切分**: B1 factor / B2 plugins / B3 contagion / B4 event_log + walk_forward / B5 文档与回归
- **Step 2 独立 Review（异构基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash）**: **pass**——E1 机械复核（生产代码 `except Exception` 49 处逐文件复现 @`7c48d50` + 31 代码锚点零漂移 + 链接/算术全过）；E2 门禁四项（pytest **671 passed** / mypy 37 files 0 / black core 37 + tests 78 unchanged）；E3 幻觉排除（A1-A4 逐条复验全命中 + P12 复现）。发现 **F-S2-P026-1（P2：§5 #6/#7 引用不存在的 `EventLog.stats()`，已订正为「新增 stats() 方法」）** / F-S2-P026-2（P3：M-A 实施面为 **6 文件**，含 walk_forward.py 的 `WalkForwardResult` 字段）/ F-S2-P026-3（P3：「全仓 49」订正为「生产代码 49」，tests 21 / tools 3 / examples 1 另有 25 处）+ 3 观察（§1「18 处吞掉」口径订正 / P12「中性化失败」命中为测试自身打印，有效路径覆盖更接近 1/9 / `read()` 内层窄类型跳坏行 → **U-P026-6**）；均已回写 [RESEARCH_p026 §10](RESEARCH_p026_silent_exception_governance.md)
- **Step 3 DESIGN（T1）**: **完稿**（[DESIGN_p026](DESIGN_p026_silent_exception_governance.md)，D1-D8 决策 + 12 测试规格 + 7 不变式 + 6 验证契约）——D1 factor sink 与双原因计数 / D2 插件层计量（Guard **保持 fail-open**）/ D3 `ContagionNetwork.degraded_components` + Granger `failed` / D4 `EventLog.stats()` 三计数器（采纳 U-P026-6 的 `skipped_lines`）/ D5 `WalkForwardResult.agent_period_failures` / D6 K 类 8 + 排除 4 零改动 / D7 计数生命周期 / D8 文案约定。**变更面订正为 8 core + 1 test**（RESEARCH「6 文件」漏计 sink 接线与阶段词表）
- **Step 3 设计期发现**: **F-D-P026-2（P2）** sink 注入**时点**是正确性条件——`self.pipeline` 在 `engine_v2.py` L228 创建、`_precompute_factors()` 在 L237 立即调用，若按 P-025 惯例放到 setup 末尾则 setup 期因子异常**全部漏采**，B1 交付判据永不成立 → 硬性规定插于 L235-L237 之间；F-D-P026-1（P3）成本行 6→8 文件；F-D-P026-3（观察）`STAGES` 无运行时使用；F-D-P026-4（观察）Granger 样本不足早退路径本就缺 `strength` 键，本批不补
- **Step 4 独立 Review（异构基座 GLM-5.3-Flash ≠ DESIGN 作者 DeepSeek-V4.1-Flash）**: **pass**（[DESIGN_p026 §11](DESIGN_p026_silent_exception_governance.md)）——E1 机械复核（32 处锚点零漂移 + 算术全过 + D2.1「新增」/D2.2「追加」措辞核查均正确）；E2 门禁（pytest **671 passed, 172 warnings** 83.89s / mypy 37 files 0 / black 115 = 37+78 unchanged）；E3 幻觉排除（STAGES 无运行时使用全仓 grep 实证 / EventLog 无 stats / Granger 早退无 strength / executor sink 惯例 L287-288 / K 类锚点 L278/L286/L313/L214 实证）。发现 **0 P1 / 0 P2 / 4 P3 + 2 观察，P3 均已回写订正正文**：F-S4-P026-1（`_report_error` 的 `reason` 死参数 → 签名修订 `(date, exc)`）/ **F-S4-P026-3（D4.3「不加锁」论证引用错误锁类型——`self._lock` 实为 `threading.RLock()` L61 可重入，「自死锁」前提不成立；结论维持、论证重写）** / F-S4-P026-2（raise 模式语义扩散未声明：factor data/internal ∈ RAISE_CATEGORIES → 首交易日 `raise_if_needed` engine_v2 L364 抛出，D1.3 补声明）/ F-S4-P026-4（T9 MST patch 目标须为 `core.global_contagion.minimum_spanning_tree`，L28 from-import 绑定）；观察 ×2：`_recover_state` 外层 except L313-314 不计入 stats（本批不补）/ `_stats` 初始化须早于 L75 `_recover_state()`（D4.1 补时点约束）。既有 `test_engine_plugins.py` 的 get_stats 断言为键访问式（L141/L223），D2.2 追加 `error_count` 键零破坏
- **Step 5 IMPL（T1）**: **完稿**（[IMPL_p026](IMPL_p026_silent_exception_governance.md)）——B1 factor 链路（`set_error_sink` / `neutralize_skip_counts` / `_report_error` 按 F-S4-P026-1 去死参数；`STAGES` +`"factor"`；`engine_v2` L237-242 sink 注入**早于** `_precompute_factors()`）/ B2 插件层（`EventLogPlugin._log` debug→warning + `get_stats`；Guard 计数 + 文案，**fail-open 不变**）/ B3 传染（`degraded_components` + Granger 三路径 `failed`）/ B4 `EventLog.stats()` 三计数器（初始化早于 `_recover_state`，不加锁）+ `WalkForwardResult.agent_period_failures`（run 重置）/ B4t 新测试 12 函数 16 实例 / B5 门禁 + 文档
- **Step 5 门禁实测（E1）**: **687 passed, 173 warnings in 71.42s**（671 + 16）/ mypy **37 files 0** / black **116 unchanged**（115 + 新测试文件 1）/ 受影响面快速回归 26 passed（改动前后同绿）/ golden G1-G7 随全量通过且 `tests/golden/*.json` 零改动；变更面 `git diff --numstat` **8 文件 +100/−10**（DESIGN 估 +97/−13）
- **Step 5 实施期发现**: F-I-P026-1（P3）DESIGN V1 未计 T1 参数化——实际 16 items 故全量为 **687** 而非 683（测试函数数仍 12,与 §4.2 一致）/ F-I-P026-2（观察）`WalkForwardEngine` docstring 参数名 `base_engine` 与实现 `base_engine_class` 不一致 / F-I-P026-3（P3）新测试 422 行 vs 估 240（独立复制引擎夹具）/ F-I-P026-4（P3）代码行数 +100/−10 vs 估 +97/−13 / **F-I-P026-5（观察）**`_set_agent_period` 的 `hasattr(agent,"distillation_config")` 为 True 但值为 `None` 时抛 `AttributeError`（L194 无 None 守卫，相邻静默失败面，本批不改）/ F-I-P026-6（观察）T10 触发 statsmodels `FutureWarning`（172→173 warnings）
- **Step 6 IMPL 独立 Review（异构基座 GLM-5.3-Flash ≠ IMPL 作者 DeepSeek-V4.1-Flash）**: **pass**（[IMPL_p026 §10](IMPL_p026_silent_exception_governance.md)）——E1 机械复核（numstat 15 files +744/−19、8 core **+100/−10** 与 §6 一致 + §4.1-4.8 行数逐一吻合 + 五文件 diff 全量重放逐行一致 + 门禁三重放 pytest **687 passed, 173 warnings in 77.94s** / mypy 37 files 0 / black 116）；E2 红态重放（checkout 8 core 文件 @`bbb55bc` → 新测试 **14 failed, 2 passed**，失败均为接口不存在/计数缺失类；2 passed 属红态预期不红——T1[exc4] 旧通用兜底同结果 + T6 旧引擎无注入调用；恢复后工作区干净）；E3 幻觉排除（T1-T12 断言逐条对码一致 + F-I-P026-2/F-I-P026-5 均核实为真实代码事实）；E4 盲区扫描（8 文件 except 全扫，本批治理点全部带计量+日志）。发现 **0 P1 / 0 P2 / 1 P3 已订正 / 3 观察**：**F-S6-P026-1（P3）IMPL §2 B1 产出「+42/−4」删除行算术错误（实测 −2，作者重复计入修改行），已订正原文**；O-S6-P026-1（`walk_forward_engine` L218 回调失败仅 warning 无计量）/ O-S6-P026-2（`event_log` L292/L300/L328 listener 与 recovery 外层无计量）/ O-S6-P026-3（`diagnostics` L129/L160 属 P-025 设计语义）——三项均登记待「静默失败治理」第三批裁决
- **下一 Step**: Step 7 CHECKLIST 落稿（含 F-I-P026-1 的 DESIGN V1 口径 683→687 订正）→ Step 8 一致性 Review → Step 9 TDD → Step 10 ADD 审计 → RULE-5 异构终审

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
