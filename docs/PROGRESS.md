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

### 1.4 未完成事项

| ID | 事项 | 依据（含档位） | 状态 | 优先级 |
|----|------|----------------|------|--------|
| P-001 | TD-3 Stage 3：移除 `core/engine.py` | `docs/RESEARCH_tech_debt_cleanup.md` TD-3；实测 10 个实际导入文件（6 examples + 4 tests），`core/__init__.py` 仅注释提及；**T1**（Layer-1：删除 `core/engine.py` 并迁移 `tests/`、`examples/`） | done（2026-11-09，Step 1-10 全通过；本地 `507 passed`、black 72 / mypy 119 新基线；`ccd0c98`；远端 CI run `42598775895` 三版本 `500 passed, 1 skipped`） | P2 |
| P-002 | TD-2：`core/config_v2.py` 冻结标注 | `docs/RESEARCH_tech_debt_cleanup.md` TD-2；当前文件无 `冻结/frozen/TD-2` 标注；**T3**（docstring-only，零运行时行为；路径不落在 scripts/tests/tools/workflows） | done（2026-11-09，T3 轻批：module docstring 落地 ⚠️ FROZEN/TD-2 冻结声明 + 冻结期间约束 + 再激活条件，口径对齐 ARCHITECTURE「⚠️ 冻结（零生产引用）」；`py_compile` exit 0，全量 507 passed，零代码行变更） | P2 |
| P-003 | TD-9：black 全量重排 | `docs/RESEARCH_tech_debt_cleanup.md` TD-9；实测 `75 files would be reformatted, 5 unchanged`（black 26.5.0；2026-11-04 复核，新增测试已格式化）；**T1**（改动覆盖 `core/` 与 `tests/`，虽 style-only 但属批量重写） | done（2026-11-09，Step 1-10 全通过；**126 文件重排**、`black~=26.0` 锁定、门禁扩展 `black --check .` 并首转绿、`.git-blame-ignore-revs` 落地；全量 `507 passed`、AST 125/125 等价、mypy 119 无劣化；提交 `4098629` + `17fc69d`；远端 CI run `42609336249` 三版本 `500 passed, 1 skipped`） | P3 |
| P-004 | TD-1：数据层统一（DataManager → DataLoaderV3 / Provider） | `docs/RESEARCH_tech_debt_cleanup.md` TD-1；两套实现仍并存；**T1**（数据层接口与生产消费方变更） | pending | P3 |
| P-005 | TD-4：Factor_DB 存储迁移 / 文档对齐（DuckDB 为规划方向） | `docs/RESEARCH_tech_debt_cleanup.md` TD-4；全仓仍无 `import duckdb`；**T1**（存储层接口变更） | pending | P3 |
| P-006 | ADR-016 补录或引用修正 | `__init__.py:3@1058cbb`、`core/__init__.py:3@1058cbb`、`pyproject.toml:79@1058cbb` 引用 ADR-016；`docs/DECISIONS.md` 当前仅 ADR-001~013；**T3**（纯文档一致性，零代码） | done（2026-11-09，T3 轻批：DECISIONS.md 补录 ADR-016（TD-1.2 轻量子包化，实施提交 `2848331`；ADR-014/015 编号跳空已注明）；三处代码引用保留；U-002 关闭） | P3 |
| P-007 | mypy 基线清理（`core` 168 errors / 20 files） | `python312 -m mypy --explicit-package-bases core`（E1，2026-11-04）；`mypy-check` 门禁当前预期 fail | done（2026-11-09 **层 A**：16 个非引擎文件 **26 → 0**；mypy **119 → 93**；修复 **4 处真实缺陷**（A-1 `remove_monitor` NameError / A-2 `analyze_market_contagion` AttributeError / A-3 `create_trigger` TypeError / A-4 `_load_auxiliary_data` 重复定义）+ 4 处 B 类防御；新增 3 项 smoke（507 → 510 passed）；`e0247ce`）。**2026-11-10 层 B 完成**：引擎三件套 `93 → 0`（engine_v2 54 / engine_v3_vector 26 / factory 13）+ 盲区口径 **102 → 8**（engine_v2 6 / data_v3 2，Q3=A 未打开）；协议真实化（`get_snapshots -> list[PortfolioSnapshot]`、`ITradeLog` 最小协议 + `trade_log` 只读 property）；2 项行为变更（空因子 fail-fast、`_generate_results` 未 setup 守卫）；新增 2 项 smoke（**514 → 516 passed**）；`mypy-check` 门禁 verdict=pass(0)，**U-006 按 Q4=B 保持挂起**，下一批次重评；主提交 `05af52f`，远端 CI run `42666962752` 三 job `509 passed, 1 skipped`） | P3 |
| P-008 | P0 环境规范化：U-001 + U-005 | 默认后端全量 `1 failed, 508 passed`，栈 `engine_v2 → analytics.generate_report → plt.figure → _backend_tk → tk.Tk`；默认 `python`=Anaconda 3.13.5 缺 `cvxpy`；CI 已存在 `.github/workflows/tests.yml`（未设 `MPLBACKEND`）；**T1**（Layer-1：`.github/workflows/` + README） | done（2026-11-05，Step 1-10 全通过；`06e9e11`；本地 U-001 达成、远端红为既有环境缺失见 P-009） | P1 |
| P-009 | CI 测试环境依赖缺失（远端红基线根因） | run `41970636863` @ `06e9e11`：3.10 `14 failed, 477 passed, 18 errors`。① `data/test_ashare/close.pkl` 被 `.gitignore:62`（`data/`）忽略 → **9 failed + 18 errors**（27 项数据测试）；② `tests/test_distillation_isolation.py:255-327` 硬编码 `F:\Coding\Factor_Trading_v3.0\gurus`（E3 @`06e9e11`）→ 4 failed；③ `numba` 不在 `pyproject.toml`（E1 `Select-String` 0 命中）→ 1 failed。历史 `df652f9` / `116426e` 两次运行同样 failure；**T1**（Layer-1：`tests/`） | done（2026-11-08 远端复核通过：run `42030484187` @ `33872c3` 三版本 `502 passed, 1 skipped`，U-007/U-001 关闭；Step 1-10 全记录见 §3.6） | P1 |
| P-010 | `DataManager` 辅助数据缺失时无安全默认值（行为缺口） | P-007 层 A D1 实证：`core/data.py` L184 死版本曾对停牌/行业/ST/市值数据提供安全默认值（全可交易 / 同行业 / 无 ST / 10 亿），唯一生效版本（原 L312）直接跳过加载，缺失文件时相应数据保持 `None`；**T1**（数据层行为变更，需构造缺失场景测试） | done（2026-11-09，T1 全流程：**幂等 guard**（`.industry` 3 次访问 3→1 次读盘）+ **停牌/ST 缺失按 `0=正常` 给默认值**（旧版 `True` 语义相反，已拒绝）+ 行业/市值保持 `None` 且 `industry` 注解改 `Optional`；新增 4 项测试 **510 → 514 passed**；mypy 93 / black 137 unchanged；**行为变更**：缺失停牌数据时 next-day 掩码末日为 False（已披露）；消费方零改动） | P2 |

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
