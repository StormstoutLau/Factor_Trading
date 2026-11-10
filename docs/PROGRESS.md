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
| P-004 | TD-1：数据层统一（DataManager → DataLoaderV3 / Provider；消费方迁移 + 旧实现删除，边界见 P-012 U-9 B-A） | `docs/RESEARCH_tech_debt_cleanup.md` TD-1；两套实现仍并存；**硬前置已满足**——P-012 B6 已落地 `DataProvider` 端口 + `PklDataProvider` + 契约测试（零接线），Protocol 先定型约束解除；数据层自 P-010（安全默认值）/P-012（复权三口径、掩码时点、退市动态池）连续叠加变更，双轨维护面扩大；**T1**（数据层接口与生产消费方变更） | pending（前置解除，可启动） | **P2**（原 P3，2026-11-10 盘点上调） |
| P-005 | TD-4：Factor_DB 存储迁移 / 文档对齐（DuckDB 为规划方向） | `docs/RESEARCH_tech_debt_cleanup.md` TD-4；2026-11-10 复核代码仍零 `import duckdb`（仅 docs 提及）；**宜排 P-004 之后**——接口未统一前迁移会波及两套实现；无外部触发 | pending | P3（维持） |
| U-006-R | mypy 盲区残差重评（`mypy core --check-untyped-defs` 现存 4 errors 2 files） | P-007 Q4=B 裁决挂起（§3.13）；**重评前置已满足**——§3.14 硬约束 4「U-006 在 L5 之后重评」的 L5 接口治理已随 P-012 B6 完成；残差实测 8 → 4 errors 2 files（P-012/P-011 实施后）；**T3**（评估决策 + 可选小修，零行为） | pending（前置解除） | P3 |
| F-A1(P-012) | 注入式工作流未注入信号 → 静默空回测（空因子/空信号时引擎无输出无告警） | P-012 CHECKLIST §11 P3 发现；期望 fail-fast 或显式 warning；注意 P-007 层 B 已有「空因子 fail-fast」行为（`05af52f`），需核对是否已覆盖该场景后再定修法；**T3**（小修 + 1 测试） | pending | P3 |
| U-D1(P-011) | golden 全局基线固化（L4 判据） | P-011 U-D1 设计裁决挂起；**硬约束「先改口径、后固 golden」已满足**——复权三口径/掩码/退市均已随 P-012 落地且 RULE-5 复审确认无未归因行为；**T1**（基线固化 + manifest 绑定） | **done（2026-11-10 由 P-013 承接**，见下） | **P2** |
| P-013 | Golden 基线固化（L4 判据落地） | P-011 U-D1 升格；6 条基线（V2/V3 × baseline·cost·mask·delisting）× 分字段容差 × CI 三版本；**T1** | done（2026-11-10，Step 1-10 全通过：四文档 + B1/B2 两批；**626 passed**（609+17）/ black 171 / mypy 0 / 盲区不劣化 / 6 份基线**逐字节可重现**；`tests/golden/*.json` + `scripts/record_golden.py` + `tests/_golden_cases.py` 单一构造器；实施期发现 **F-S9-G1（P1 停牌账目缺陷）** + F-S9-G2~G7） | P2 |
| **P-014** | **V2 停牌路径账目缺陷（P-013 实施期发现）** | 次日开盘路径（`enable_pending_orders=False`）在停牌期重复生成清仓单，恢复日一次性成交 → 负持仓 + 5 项 I2 违规；E2 复现见 [RESEARCH_p014 §4](RESEARCH_p014_suspension_accounting.md)；**症状订正**：原登记「停牌日仍成交」未复现（掩码生效），详见该文 §4.3；**T1** | **done（2026-11-10，Step 1-10）**：三层防线（执行侧持仓夹紧 / 再平衡刷新订单簿 / 次日订单过期）+ 8 项性质测试 + golden **G7**；**635 passed** / black 172 / mypy 0（36）/ 盲区不劣化；G1/G2/G4/G5/G6 基线**数值不变**，G3 行为变更重录（56→55 笔，NAV rel 1.11e-6，理由见 [IMPL §9.3](IMPL_p014_suspension_accounting.md)）；四文档 [RESEARCH](RESEARCH_p014_suspension_accounting.md) / [DESIGN](DESIGN_p014_suspension_accounting.md) / [IMPL](IMPL_p014_suspension_accounting.md) / [CHECKLIST](CHECKLIST_p014_suspension_accounting.md) | **P1** |
| **P-015** | **外部框架对拍校准（U-4 触发 · 单框架打通）** | U-4 触发条件「用户/评审要求第三方框架对照时」由用户 2026-11-10 说明构成——目的=**准确性基准**（验证「准确计算 + 回测机制设计意图落地」），非对外声明一致；用户裁决：① 正式立项 ② 先一个框架打通；**VectorBT↔V3 首例 + 隔离 venv**（vectorbt 1.2.0 依赖 pandas>=3.0.3 / numba>=0.66，与主环境冲突，清华镜像安装）；Backtrader↔V2、Qlib 登记后续（U-P015-1）；**T1**（Layer-1：`scripts/external_benchmark/`） | **done（2026-11-10，Step 1-10）**：四文档 + 规格层/三脚本 + **隔离 venv**（.gitignore 豁免）+ [校准报告](APPENDIX_p015_external_calibration.md)；**29 项恒等式断言 0 失败**（**P-017 口径更正**：含 B5 恒真豁免 1 项 → 28 断言 + 1 豁免登记）（I1 全零残差 / I2c 闭式一般式 2.0e-10 / I3 费用模型一致性 + 缺口 38658.94 登记 / I4 翻转全等 5.8e-11 / I5 阴性对照 −10000.000000 精确命中）；**两处结构性语义差异实锤**（V3 last_pv 规模参考值 vs vbt current-NAV；V3 费用透支现金 vs vbt 部分成交——已写恒等式/缺口）；**635 passed / black 0 / 主环境零污染**；mapping §2.2 获首个实测列；执行序 §3.17；四文档 [RESEARCH](RESEARCH_p015_external_benchmark.md) / [DESIGN](DESIGN_p015_external_benchmark.md) / [IMPL](IMPL_p015_external_benchmark.md) / [CHECKLIST](CHECKLIST_p015_external_benchmark.md) | P2 |
| **P-016** | **P-015 复审 P3 修正（F-R5-P015-1~3 + F-S9-P016-1）** | RULE-5 复审 §9.4 输出 3 项 P3；改动落 `scripts/external_benchmark/`（Layer-1）→ **T1**（判档规则 1 + 规则 3 fail-closed；本仓无 T2 本地先例）；实施前取证新发现 F-S9-P016-1（报告覆盖**已真实发生**，P2） | **done（2026-11-10，Step 1-10）**：三态词表（pass/fail/waiver，豁免不计断言）/ 报告人工章节保护（命中即改写 `.generated.md`）/ `simulate_vbt_spec` rate>0 fail-fast / I2a↔G1 命名映射三处文档注；**重新回填** APPENDIX §1/§3/§4（P-015 会话内已被覆盖为占位）；**18/18**；**28 断言 + 1 豁免，exit 0**；`635 passed` / black 0 / 主环境零污染；发现 P2×1 + P3×1（F-S9-P016-2 复审漏检项，登记）；四文档 [RESEARCH](RESEARCH_p016_p015_review_fixes.md) / [DESIGN](DESIGN_p016_p015_review_fixes.md) / [IMPL](IMPL_p016_p015_review_fixes.md) / [CHECKLIST](CHECKLIST_p016_p015_review_fixes.md) | **P3** |
| **P-017** | **P-016 复审 E4 四项 P3 修正** | P-016 RULE-5 复审 §9.4 E4 输出 4 项 P3（F-R5-P016-1~4）；改动落 `scripts/external_benchmark/verify_p015.py`（Layer-1）→ **T1**（判档规则 1；无 T2 本地先例） | **done（2026-11-10，Step 1-10）**：① PROGRESS §3.17.1 + §1.4 两处「29 项断言」补 P-017 口径注（原句保留，不改冻结读数）；② IMPL_p015 §8.5 占位回填为读数表 + 「T-4 原始读数未保全」声明；③ `_resolve_report_target` 增 `GENERATED_SUFFIX` 命名空间守卫（生成物原地重写，消除 `.generated.generated.md` 级联）；④ CHECKLIST_p016 E-1 计数更正为 12 文件 + B-3 分支精确化。**13/13 ✅**；四分支探针全 PASS；**28 断言 + 1 豁免，exit 0**；`635 passed` / black 0；占位真实残留 0；四文档 [RESEARCH](RESEARCH_p017_p016_review_fixes.md) / [DESIGN](DESIGN_p017_p016_review_fixes.md) / [IMPL](IMPL_p017_p016_review_fixes.md) / [CHECKLIST](CHECKLIST_p017_p016_review_fixes.md) | **P3** |
| U-D2(P-011) | V2 同日收盘模式（跨引擎逐日净值一致） | P-011 U-D2 挂起（倾向不做）；触发=第三方要求 V2/V3 逐日净值一致 | pending（倾向不做） | P3 |
| U-D3(P-011) | trace 采样/保留策略 | P-011 U-D3 挂起；触发=长区间/全市场 trace（体积 > 500 MB） | pending（条件触发） | P3 |
| U-2(P-011) | DSR/PBO 多重检验校正 | P-011 RESEARCH U-2 裁决：S-B 方案挂起至对外发布需求——无 trials log 则 DSR/PBO 无数据可算；触发=对外发布因子结论或建立 trials 记录 | pending（条件触发） | P3 |
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
| U-006 | `mypy-check` 门禁转绿（`core` 0 errors） | mypy 清理批次启动 / 每次门禁链验收 | 先清理 P-007（168 errors），再收紧；门禁保持如实 fail。**2026-11-10 注记（P-007 层 B 收口）**：P-007 层 A+B 完成，`mypy --explicit-package-bases core` = 0、门禁 verdict 已机械转 **pass**；但按用户裁决 **Q4=B（2026-11-09）本项不关闭**——收紧 `mypy-check` 命令口径（如 `--check-untyped-defs`）另行评估（残差 8），下一批次重评 | E1 |
| U-007 | CI `Run tests` 三版本全绿（U-001 远端判据） | P-009 修复后 / 每次远端验收 | 先修 P-009（数据夹具策略 + 路径相对化 + 可选依赖声明），再重跑；不得用 skip 掩盖缺失（RULE-3） | E1（run `41970636863`） |
| U-008 | numba JIT 路径在 CI 有覆盖 | CI 出现 numba 相关回归却无法拦截 | 暂不新增 optional job；以 C1（`importorskip`）保留本地执行，后续按需评估 | E1（`pyproject.toml` 无 numba） |

> **已关闭（2026-11-04）**: U-004 —— [SPEC_STANDARD.md](SPEC_STANDARD.md) 头部已声明 `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1 为冲突时的权威源（@`400394e`），判据达成。
> **已关闭（2026-11-05，P-008）**: U-005 —— 收敛口径按 [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md) §5.3 落定并达成：「README 写明测试解释器选择方式」。README `## 🧪 Testing` 节落地（`py -0p` / `py -3.12` / 临时 `MPLBACKEND=Agg`），V2 断言 PASS（E2）；CI 矩阵显式 3.10-3.12（S4）。原倾向「命令固定 Python312 路径」仅适用于本机门禁（`unit-tests` gate 已固定）。
> **本地达成，远端未达成（2026-11-05，P-008）**: U-001 —— `MPLBACKEND=Agg` 全量 `509 passed`（E1 × 3：30.18s / 32.23s / 31.99s）；CI 侧 job 级 `env` 已落地（`.github/workflows/tests.yml` @`06e9e11`），**但远端 run `41970636863` = failure**：根因是数据夹具被 `.gitignore` 忽略（**9 failed + 18 errors**）、[`tests/test_distillation_isolation.py`](tests/test_distillation_isolation.py) 硬编码 Windows 路径（4 failed）、缺 `numba`（1 failed），与本批改动无关（历史 `df652f9`/`116426e` 同样 failure）。U-001 **不关闭**，转 U-007 跟踪；Tk 根因仍不在范围（[RESEARCH](RESEARCH_env_normalization.md) §1.1）。
> **已关闭（2026-11-08，P-009）**: U-007 —— run [`42030484187`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42030484187) @ `33872c3` 三 job success，每版 `502 passed, 1 skipped`（3.10 17.46s / 3.11 17.22s / 3.12 19.55s），与 C-1 推演（477−6+27+4=502，模块级 skip 计 1）逐字一致；27 项数据测试计入 passed、零 skip（RULE-3 达成）；`Prepare test fixture` 每版成功（`0.005s`，296051/296436 B）。
> **已关闭（2026-11-08，P-009）**: U-001 —— 本地 Agg `509 passed`（E1×3）+ 远端三版本全绿（run `42030484187`），判据「固定 Agg 下全绿（本地 + CI）」达成；Tk 组件本身仍未修复（不在判据内，见 [RESEARCH_env_normalization.md](RESEARCH_env_normalization.md) §1.1）。
> **映射说明**: U-002 由 P-006 关闭；U-003 作为 P-001 Step 1 的输入，不单独占工作流。
> **已关闭（2026-11-09，P-006）**: U-002 —— [DECISIONS.md](DECISIONS.md) 出现 ADR-016（§决策状态说明前，TD-1.2 轻量子包化）；三处代码引用保留（E1 `git grep -n "ADR-016"` = 代码 3 处 + DECISIONS 条目）。

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
