# TD-3 Stage 3（移除 core/engine.py） · 审查验收清单

> **文档编号**: CHECKLIST_td3_stage3
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: 已完成（Step 9 红→绿 + Step 10 ADD 审计 **全过**，2026-11-09；43/43 达成，P1/P2 = 0；工作区未提交）
> **上游**: [DESIGN_td3_stage3.md](DESIGN_td3_stage3.md)（Step 4 通过，含 D1-D7） · [IMPL_td3_stage3.md](IMPL_td3_stage3.md)（Step 6 通过）
> **填写规则**: 本清单在 Step 7 只定义「怎么算做完」；「实测」列一律 `[待 Step 9]`，**禁止实现前预填**（RULE-1）。每条 ✅ 必须绑定证据出口；无证据只能标 `[未在远端执行]` / `[未入仓-不可重放]` / `[未取证]`。
> **解释器**: Python 3.12.10（F-R5）；`MPLBACKEND=Agg`

---

## 1. 功能完整性

> **DoR**：DESIGN §3-§5 契约 + IMPL §3 逐任务文本均已复核；**DoD**：每项有 E1 读数或诚实降级标注。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `core/engine.py` 不存在（724 行整文件删除，非空壳） | `Test-Path core/engine.py` → `False`；`git ls-files` 不再列出 | DESIGN D1/D6；IMPL T-1 | ✅ `Test-Path=False`；`git status` = ` D core/engine.py`（未暂存，提交后 `git ls-files` 消失）；无空壳 / 无 re-export |
| A2 | 全仓 `*.py` 零 V1 import：`from core.engine import` 与 `from core import engine` 均 0 命中（本批文档除外） | `Get-ChildItem -Recurse -Filter *.py \| Select-String`（`-SimpleMatch`） | RESEARCH P1；DESIGN §3.1 | ✅ 三类模式（`from core.engine import` / `from core import engine` / `import core.engine`）全仓 `*.py` **0 命中** |
| A3 | 5 个 config-driven 脚本迁移完成：`from core.factory import create_default_engine` 命中 5 文件、调用 6 处；`BacktestEngine(` 在 examples 中 0 命中；**IMPL T-3 完成判据**：`py_compile` 6 examples exit 0（Step 8 补，F-S1） | `Select-String examples` 计数 + `<PY312> -m py_compile <6 文件>` | DESIGN D2；IMPL T-3.1~T-3.4/T-3.6 | ✅ import **5 文件** / 调用 **6 处**；`(?<![A-Za-z_])BacktestEngine\(` = **0**（裸文本命中 1 处系 `DetailedBacktestEngine(` @`full_backtest_demo.py:767`，非 V1，见 F-9-5）；`py_compile` 6 examples + `cli.py` = **exit 0** |
| A4 | 手动装配脚本（`full_backtest_2020_2026_simple.py`）：`BacktestEngineV2` 导入 + 实例化；**D7** 5 行 `core.*` 导入全部替换；`build_trigger(config.rebalance, dm.trade_dates)`；11 项属性直装配保留 | 静态读码 + `Select-String` 精确文本 | DESIGN D2/D7；IMPL T-3.5 | ✅ L14 导入 + L87 实例化（2 处）；`build_trigger(config.rebalance, dm.trade_dates)` @L104；`from core.*` **8 行**（L12-14 + L92-96，含 D7 的 5 行）；11 项属性直装配原样保留 |
| A5 | 2 个 0 收集诊断脚本已删除：`tests/test_visual_trace.py`、`tests/test_visual_trace_v2.py` | `Test-Path` ×2 → `False` | DESIGN D3；IMPL T-2 | ✅ 两文件 `Test-Path=False`；stale `__pycache__/test_visual_trace*.pyc` 一并清理（0 残留） |
| A6 | `test_rebalance_exits.py` 清理完整：`_run_engine_v1` / `test_g2_*` / `test_g3_*` / `_FakeCombiner` / `import warnings` / `ExitStack` / `from core.engine` 均 0 命中；`patch` 仍保留（L286 用途） | `Select-String` 7 个模式 + 读回 | DESIGN D3；IMPL T-4 | ✅ 7 个模式全 **0**；`patch(` **1 处**保留（`_run_engine_v2`） |
| A7 | `test_compatibility.py` L48 改为 `from core.engine_v2 import BacktestEngineV2`；测试项仍 6 | 静态读码 + `--collect-only` | DESIGN D3；IMPL T-5 | ✅ L48 命中 1 处；`--collect-only` = **6 tests collected** |
| A8 | 注释/docstring 同步 **5 行 / 3 文件**：`core/__init__.py` L6/L9、`engine_plugins.py` L14/L383、`walk_forward_engine.py` L45；`agents/multi_strategy_engine.py:64` 历史表述**保留** | `Select-String 'BacktestEngine'` 逐行判定 | DESIGN D4；IMPL T-6 | ✅ **5 行 / 3 文件**（`core/__init__.py` 2 + `engine_plugins.py` L14/L383 + `walk_forward_engine.py` L45）；历史表述 `agents/multi_strategy_engine.py:64` 原样保留 |
| A9 | 保护路径零改动：`core/engine_v2.py`、`core/factory.py`、`core/target_positions.py`、`cli.py`、`pyproject.toml`、`filter/`、`core/portfolio.py`、`core/execution.py`、`core/tracker.py`、`core/pending.py`、`core/rebalance.py`、`core/config.py` 全部 diff 空 | `git diff --stat -- <路径>` | DESIGN §3.3 | ✅ 12 项路径 `git diff --stat` **输出空** |
| A10 | CLI 与端到端可用：`cli.py --help` exit 0；`examples/demo.py` 端到端 exit 0 | 两次子进程 `$LASTEXITCODE` | IMPL V8；R1 | ✅ `demo.py` **exit 0**（5.4s，1140 笔交易）；`cli.py --help` **exit 0**（24 行 usage） |

## 2. 测试完整性

> **DoR**：IMPL §5 V1-V8 + §6 红→绿已定义；**DoD**：RED/GREEN 读数可复现，正反例均有记录。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | 全量测试 `507 passed`（509 − g2 − g3），无 failed / 无新增 skip | `<PY312> -m pytest -q` 末行 | DESIGN §1.1；IMPL V4 | ✅ **`507 passed, 82 warnings in 20.32s`**；0 failed / 0 skipped |
| B2 | 两测试文件收集 `18`（`test_rebalance_exits` 12 + `test_compatibility` 6） | `--collect-only -q` 两次/合并 | DESIGN §5.3；IMPL V6 | ✅ 合并收集 **`18 tests collected in 2.47s`**；`test_compatibility` 单跑 **6 tests** → 12 + 6 吻合 |
| B3 | `tests/test_*.py` 文件数 `48`（50 − 2） | `Get-ChildItem tests -Filter 'test_*.py'` | DESIGN §1.1；IMPL V5 | ✅ **48** |
| B4 | RED 证据：T-1 后两文件各 1 个 collection ERROR（`No module named 'core.engine'`），证明删除真实生效 | pytest 输出（T-1 后立即执行） | IMPL §6.1 R6 | ⚠️ **判据偏差（F-9-1）**：实测 **1 个 collection error**（`test_rebalance_exits`，模块级 import）+ **1 个 runtime failure**（`test_compatibility::test_new_import_paths`，import 在函数体内）；删除生效证据成立，形态与预测不符 |
| B5 | 红→绿记录完整：RED ≥6 条、GREEN ≥9 条，逐条读数写入 §10 | §10 表 + session | SPEC_PROCESS Step 9；F5 | ✅ §10：**RED 6 条 + GREEN 9 条**，逐条贴读数 |
| B6 | 保留的 golden 测试仍通过：`test_g1_engine_v2_liquidates_exited_positions` / `test_g4_no_hidden_leverage` / `test_g5_sells_precede_buys` | pytest 定向输出（`-k 'g1 or g4 or g5'`） | DESIGN D3；R2 | ✅ **`3 passed, 9 deselected in 2.61s`** |
| B7 | 无新增测试文件、无临时探针残留 | `git status --short` 仅本批目标文件；`%TEMP%` 无 p001 残留 | IMPL §7 | ✅ `git status` 共 **25 项** = 18 M + 3 D + 4 未跟踪（均为本批文档/目标文件，无新增测试）；`%TEMP%` `*p001*` = **0** |
| B8 | 本地 numba 7 项仍执行；CI 500 passed + 1 skipped 为推演 | 本地 pytest；远端项标 `[未在远端执行]` | DESIGN §1.1；R8 | ✅ `-k numba` = **`7 passed, 500 deselected`**；远端 3.10/3.11/3.12 `500 passed, 1 skipped` **`[未在远端执行]`**（推演） |
| B9 | 测试计数算式可复核：全量 collect = 507；`509 − 2 = 507` | 全量 `--collect-only -q` 计数 | DESIGN §5.3 | ✅ 全量执行读数 507 / 509 − g2 − g3 = **507** 一致 |

## 3. 性能与资源

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | 全量 pytest 耗时 ≤ 45s（基线 30.05s；删除代码后不应变慢） | pytest 末行 | Step 2 基线 | ✅ **20.32s**（门禁 seq 8 同量级），远低于 45s |
| C2 | `demo.py` 端到端烟测 ≤ 300s（200 股 × 500 天合成数据） | 子进程耗时 | IMPL V8 | ✅ **5.4s**（`Stopwatch`），≤ 300s |
| C3 | 代码文件净删除 ≥ 1100 行（engine 724 + visual_trace 238 + 179 + 测试清理约 80，扣除新增约 30） | `git diff --numstat -- core tests examples` 汇总 | DESIGN §3.1 | ✅ 新增 **25** / 删除 **1270** → **净删除 1245 行**（`core/engine.py` 747 + `test_rebalance_exits` 51 + `test_visual_trace` 255 + `test_visual_trace_v2` 192 + 其余小改） |
| C4 | 无运行产物残留：`demo_data/` 与 `demo_output/` 已删除；`git status` 无未跟踪目录 | 目录列表 + `git status` | IMPL §5 V8 清理契约 | ✅ 两目录 `Test-Path=False`；`git status` 无 demo 条目（`demo_output/` 命中 `.gitignore:56`，`demo_data/` 内 `*.pkl` 命中 `.gitignore:67` → 见 F-9-4） |

## 4. 文档一致性

> **DoR**：四文档完稿（Step 8 执行前）；**DoD**：机械比对 + 链接可解析。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | `ARCHITECTURE.md` 3 处：L81 行删除、L198 表头/状态标注「已移除」、L304 债务行删除 | `Select-String 'Engine V1'` + 读回 | DESIGN D5；IMPL T-7.1 | ✅ `Engine V1` 仅剩 **L197**：`\| 特性 \| Engine V1（已移除） \| Engine V2 (主引擎) \| Engine V3 (预筛选) \|`；L81 模块行与 L304 债务行已删 |
| D2 | `CODE_WIKI.md` 25 个编辑点全部落实：15 处 `engine.py` 路径（含 L23 锚点）、10 处 `BacktestEngine` 类名（含 §15.2 4 处）、§12 正文替换为 V2 摘要、L127 体量、L173 耦合表 | `Select-String 'engine.py' / 'BacktestEngine\b'` 逐行判定 | DESIGN D5；IMPL T-7.2；F-I1 | ✅ `(?<![A-Za-z_])BacktestEngine(?![V_])` = **0**；`engine.py` 仅 **2 行**（L707 §12、L883 §15.1）均为「已移除」注记；TOC/架构图/模块表/耦合表/调用图/时序图全为 V2 |
| D3 | `DECISIONS.md` L30 标注「已于 P-001 移除」 | 读回 | DESIGN D5 | ✅ L30 = `core/engine.py` **(已于 P-001 移除)** |
| D4 | `README.md` 4 行：L7 徽章 / L98 / L262 / L411 全部 507 与 48；`509` 在 README 中 0 命中 | `Select-String '509'` / `'507'` 计数 | DESIGN D5；IMPL T-7.4 | ✅ `509` = **0**；`507` = **4**（L7 徽章 / L98 / L262 / L411），L411 含 `48 files`；另修 L359 目录树残行 `engine.py / engine_v2.py` → `engine_v2.py`（F-9-2） |
| D5 | `CHANGELOG.md` `[Unreleased] > Removed` 新增 1 条（TD-3 Stage 3） | 读回 | DESIGN D5；IMPL T-7.5 | ✅ `[Unreleased] > Removed` 第 2 条：V1 删除 + 6 examples 迁移 + g2/g3 + 2 诊断脚本、`509 → 507`、`50 → 48`，并附 demo 数值变化说明 |
| D6 | 历史记录零改动：`DEVLOG.md`、`DIFF_REPORT_2026-10-23.md`、`docs/dev-log/`、`docs/archive/`、`DESIGN_critical_rebalance_fix.md` diff 空 | `git diff --stat -- <路径>` | DESIGN D5 历史行 | ✅ 5 类路径 `git diff --stat` **输出空** |
| D7 | 四文档（RESEARCH/DESIGN/IMPL/CHECKLIST）相对链接全部可解析，无 broken | Python 正则 + `Path.exists()` | Step 8 | ✅ Step 8 §9.1 #1：**14 条全可解析，0 broken** |
| D8 | `PROGRESS.md` §3.1 追加 Step 7-10 进度、P-001 状态；`RESEARCH_tech_debt_cleanup.md` TD-3 追加 Stage 3 注记且历史结论未改 | 读回 + `git diff` | DESIGN D5；IMPL T-8 | ✅ §3.1 含 Step 1-10 全链；P-001 行 = `done（2026-11-09，Step 1-10 全通过；未提交）`；TD-3 追加 Stage 3 段落（`+2/−0`），Stage 2 及历史结论未改 |

## 5. 兼容性与安全

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | `pyproject.toml` 零改动（依赖 / testpaths / addopts / 无 filterwarnings） | `git diff --stat pyproject.toml` 空 | DESIGN D6 | ✅ `git diff --stat` **输出空** |
| E2 | 生产逻辑零改动：`core/engine_v2.py`、`core/factory.py`、`core/config.py`、`filter/`、`core/portfolio.py`、`core/execution.py`、`core/tracker.py`、`core/pending.py`、`core/rebalance.py`、`cli.py` diff 空 | `git diff --stat -- <路径>` | DESIGN §3.3 | ✅ 与 A9 同一命令，10 项路径全空（合计 12 项含 `target_positions.py` / `pyproject.toml`） |
| E3 | 破坏性变更符合 D6：`python -c "import core.engine"` 抛 `ModuleNotFoundError`；无 shim / 无空壳 / 无 redirect | 子进程 exit ≠ 0 + stderr 命中 | DESIGN D6 | ✅ `ModuleNotFoundError: No module named 'core.engine'`，exit **1**；`core/engine.py` 与任何 shim 均不存在 |
| E4 | examples 运行时覆盖边界如实声明：除 `demo.py` 外的 5 个脚本依赖 `E:/Ashare_data`，标 `[未在 CI 执行]`，不得写成 ✅ | 本清单与 IMPL 声明计数 | DESIGN §2.3 能力边界；R4 | ✅ 5 个脚本仅做 `py_compile`（A3），运行时 **`[未在 CI 执行]`**；仅 `demo.py` 端到端 ✅ |
| E5 | `demo.py` 数值变化属预期（V2 执行 FactorPipeline），无 golden 断言；CHANGELOG 已注明 | 读回 CHANGELOG + demo 输出无断言 | DESIGN R1 | ✅ CHANGELOG 条目含「**行为说明**：`examples/demo.py` 改由 V2 执行 `FactorPipeline`…无 golden 断言，属预期」；`demo.py` 内无断言 |
| E6 | 可恢复性：`core/engine.py` 在 `696bd7b` 可完整取回；`git cat-file -s` = 29910 B | `git show 696bd7b:core/engine.py \| Measure-Object -Line` = 724 | DESIGN §7；P15 | ✅ 可恢复：`git show 696bd7b:core/engine.py` 正常；**行数 724（非空行口径，文件实为 747 行）**；**字节修正（F-9-3）**：repo blob `cat-file -s` = **29163 B**（LF），29910 B 为 CRLF 工作区尺寸（+747 换行字节） |

## 6. 代码质量

> **DoR**：本批为删除 + 迁移，无新增生产代码；**DoD**：机器可判。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 无新增 `TODO` / `FIXME` 标记（排除本清单规则行自身与文档引用） | 本批 diff + 五文档 `Select-String` 逐行排除 | Phase 3 模板 | ✅ 新增行 `TODO`/`FIXME` = **0** |
| F2 | `black --check core tests` = `72 files would be reformatted`（75 − 3，预期 fail，无回归） | 门禁输出 | DESIGN R9；IMPL §2 | ✅ **`72 files would be reformatted, 5 files would be left unchanged`**，exit 1（预期 fail） |
| F3 | `mypy --explicit-package-bases core` = `119 errors`（168 − 49，预期 fail，无回归） | 门禁输出 | DESIGN R9；IMPL §2 | ✅ **`Found 119 errors in 19 files (checked 29 source files)`**，exit 1（预期 fail） |
| F4 | 修改文件无行尾空白、UTF-8 无 BOM；删除文件后无残留 `__pycache__/engine*.pyc` 提交 | `Select-String '  $'` + `git status` | 文档卫生 | ✅ 新增 85 行 **0 行尾空白**；17 文件 **BOM 0**；114 处**既有**行尾空白未触碰（非本批引入）；`core/__pycache__/engine.cpython-31*.pyc` 与 `test_visual_trace*.pyc` 已清理（0 残留、未跟踪） |
| F5 | 无临时脚本 / 断言脚本入仓；`%TEMP%` 探针已清理 | `git status` + 目录列表 | IMPL §7 | ✅ 未跟踪项仅 4 份本批文档；`%TEMP%` `*p001*` = **0** |
| F6 | 门禁 expected-fail 如实标注（black/mypy 不得写成 ✅）；无 `[未取证]` 被写成 ✅ | §7/§8 逐行核对 | RULE-6 | ✅ §7 中 black-check / mypy-check 以 ⚠️ **fail** 记录（基线 72 / 119），未写成 ✅；§8 全部 ✅ 行均绑定 E1/E3 读数；远端 CI 与 5 个 examples 运行明确标 `[未在远端执行]` / `[未在 CI 执行]` |

## 7. 门禁链验收（Step 10）

| 门禁 | 命令 | 预期 verdict | 实测 verdict | 证据 |
|------|------|--------------|--------------|------|
| probe | `echo Spec_Runner OK` | pass | ✅ **pass**（exit 0） | session seq 6 |
| unit-tests | `set MPLBACKEND=Agg&& <PY312> -m pytest tests -q` | **pass**（本批核心） | ✅ **pass**（exit 0，`507 passed`） | session seq 7 |
| black-check | `<PY312> -m black --check core tests 2>&1` | **fail（预期基线 72）** | ⚠️ **fail**（exit 1，`72 files would be reformatted`） | session seq 8 |
| mypy-check | `<PY312> -m mypy --explicit-package-bases core` | **fail（预期基线 119）** | ⚠️ **fail**（exit 1，`119 errors in 19 files`） | session seq 9 |

> `black-check` / `mypy-check` 的 fail 属既有技术债（P-003 / P-007），基线由 75/168 **下调**为 72/119；Step 10 只核对读数与预期一致，不得改写为 ✅。
> **Step 9 实测**：4 条已写入 `factorv3-p001-td3-stage3-20261109`（seq 6-9），`replay` = `9 rows OK`（含 Step 1-8 的 5 行）。

## 8. 取证矩阵（Step 10 回填）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| `pytest` 全量输出（E1） | B1、B9、C1 | ✅ `507 passed, 82 warnings in 20.32s` |
| `pytest` 定向输出（E1） | B2、B4、B6、B8 | ✅ `18 collected` / R6 `1 error + 1 failure` / `3 passed` / `7 passed` |
| `git diff --stat` / `git status` / `git ls-files`（E1） | A1-A9、C3、C4、D6、E1、E2、E6、F1、F4、F5 | ✅ 保护路径空 / 历史空 / 净删除 1245 / 未跟踪 4 文档 / stale pyc 0 |
| `Select-String` / `Grep` 机械检索（E1） | A2-A4、A6、A8、D1、D2、D4 | ✅ 计数逐项贴于实测列（A2=0、A3=5/6/0、A6=0、A8=5、D1=1、D2=0、D4=0/4） |
| 子进程 exit code（E1） | A10、E3、E4、E5 | ✅ demo 0 / cli 0 / import 1 / py_compile 0 |
| 静态读码（E3，须绑 commit hash） | A4、A7、F2、F3 | ✅ 工作区 @ `696bd7b` 基线之上（本批未提交 → 待提交后绑 hash） |
| 门禁 session + `replay`（E1） | §7 四行、B5 | ✅ seq 6-9 + `replay: 9 rows OK` |
| 盲区扫描（E4，范围：全部修改文件 diff + 新增文档） | 无设计外改动 | **发现 1 项**（README L359，已修 → F-9-2）；其余 0 项 |
| 远端 CI（如执行） | U-007 回归基线 | `[未在远端执行]`（本批不强制） |

## 9. Step 8 一致性 Review（独立校验 pass，2026-11-09）

> 本节由 Step 8 独立执行并单独写入（RULE-1）；四文档（RESEARCH / DESIGN / IMPL / CHECKLIST）+ PROGRESS 全部完稿后执行。**审查者**：单 Agent 自查（RULE-4）。**审查方式**：机械校验（Python 正则 + 键值计数矩阵 + 链接提取）贴读数，不依赖正文自报。

### 9.1 机械校验读数

| # | 校验项 | 方法 | 读数 | 判定 |
|---|--------|------|------|------|
| 1 | 四文档相对链接可解析 | Python 正则提取 + `Path.exists()` | **14 条全可解析，0 broken** | ✅ |
| 2 | 键值矩阵 `507 passed` | `str.count` 五文档 | RESEARCH 1 / DESIGN 5 / IMPL 6 / CHECKLIST 1 / PROGRESS 2 —— 目标值全载体命中 | ✅ |
| 3 | 键值矩阵 `48 files` / `50 files` | 同上 | `48 files` 1/2/2/0/1；`50 files` 仅 RESEARCH(5)/DESIGN(1)/IMPL(1) 的**旧→新文本与基线角色** | ✅ |
| 4 | 键值矩阵门禁基线 | 同上 | `119` 0/6/5/3/3；`168` 0/6/2/2/9；`black`/`mypy` 全链命中；DESIGN 与 IMPL 的 `75→72`、`168→119` 各 2/1 无冲突 | ✅ |
| 5 | CHECKLIST 零预填（RULE-1） | `✅` 与 `[待 Step` 计数 | `[待 Step` **57** 处；`✅` 5 处**全为规则文本**（填写规则 1 + 「不得写成 ✅」×3 + E4 引用），实测列 0 预填 | ✅ |
| 6 | 旧值 `509 passed` 角色判定 | 正则取上下文逐行 | RESEARCH 5 处 = 基线证据 + F-R1 修正记录；DESIGN 2 处 = 旧→新迁移文本；IMPL 3 处 = T-0 基线读数；CHECKLIST **0**；PROGRESS 5 处 = P-008/P-009 历史步骤行（历史记录不改） | ✅ 无当前预期值残留 |
| 7 | 术语一致性 | 五文档计数 | `test_visual_trace.py` / `_run_engine_v1` / `_FakeCombiner` / `g2` / `g3` 命名与口径一致；`18 tests collected` DESIGN/IMPL 各 1 | ✅ |
| 8 | 断言延续链 | 关键词逐级检索 | RESEARCH §5 倾向 → DESIGN D1-D7 → IMPL T-0~T-9/V1-V8 → CHECKLIST 43 项，七组链路全部贯通；`43` 在 PROGRESS 与 CHECKLIST 各 1 一致 | ✅ |
| 9 | 头部互引（双向） | 链接计数 | RESEARCH↔DESIGN、DESIGN↔IMPL、IMPL↔CHECKLIST 上下游齐备；IMPL 正文以文本形式引用 RESEARCH 锚点（P 编号），跨两层引用经 DESIGN 链接可达 | ✅ |
| 10 | 远端推演值口径 | `500 passed` 计数 | DESIGN 2 / CHECKLIST 1 / PROGRESS 1，均标「推演」与 `[未在远端执行]` 语义，无一写成 ✅ | ✅ |

### 9.2 发现与处置（F-S 系列）

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-S1 | P3 | IMPL T-3 的完成判据「`py_compile` 6 examples exit 0」在 CHECKLIST 无对应验收项（A3 原证据出口仅 `Select-String` 计数）——实施判据与验收链脱节 | **已修正**：A3 补 `py_compile` 判据与证据出口 |
| F-S2 | P3（判定非缺陷） | IMPL 头部未直接链接 RESEARCH（仅链 DESIGN） | **角色分工**：链式上游 RESEARCH→DESIGN→IMPL→CHECKLIST，跨两层锚点经 DESIGN 可达（同 P-008 F-S1「台账不承载真值属角色分工」先例）；不修改 |

> **无冲突值、无预填、无断言断链**；1 项 P3 已回写，1 项 P3 判定为角色分工。0 项阻断。

### 9.3 复核结论

| 项 | 结论 |
|----|------|
| 门禁（Step 8 双向引用 + 无矛盾 + 术语一致） | **全过** |
| 派生需求登记 | D7（先存导入修复）已在 DESIGN §4/D7、IMPL T-3.5、CHECKLIST A4 三处对齐；实施中如产生新决策按本节机制追加登记 |
| 阻断项 | **0** |
| 门禁 | **Step 8 一致性 Review pass** → 进入 Step 9 实施 |

## 10. 红→绿记录（Step 9 回填）

> **已执行 2026-11-09**。RED 6 条（T-0 观测，删除前）+ GREEN 9 条（T-3 → T-9 观测）。

### 10.1 RED（先失败记录，F5）

| # | 读数 | 命令 / 手段 | 结果 | 判定 |
|---|------|-------------|------|------|
| R1 | V1 文件存在 | `Test-Path core/engine.py` | **`True`** | ✅ 删除前基线成立 |
| R2 | V1 import 行数 | `Select-String` 全仓 `*.py` | **11 行** = 10 活跃（6 examples + 4 tests）+ 1 注释（`core/__init__.py`） | ✅ 与 RESEARCH P1 一致 |
| R3 | 两测试文件收集数 | `pytest --collect-only -q` | **`20 tests`**（`test_rebalance_exits` 14 + `test_compatibility` 6） | ✅ g2/g3 仍在 |
| R4 | 测试文件数 | `Get-ChildItem tests -Filter 'test_*.py'` | **`50`** | ✅ 死脚本仍在 |
| R5 | README `509` | `Select-String README.md '509'` | **4 行**（L7/L98/L262/L411） | ✅ 计数未更新 |
| R6 | T-1 后两测试文件行为 | `pytest tests/test_rebalance_exits.py tests/test_compatibility.py` | **1 collection error**（`test_rebalance_exits`：`ModuleNotFoundError: No module named 'core.engine'`）+ **1 runtime failure**（`test_compatibility::test_new_import_paths`：函数体内 import 同一模块失败） | ⚠️ 删除生效成立；形态与 IMPL「2 errors」预测不符 → **F-9-1** |

### 10.2 GREEN（T-9 全量读数）

| # | 读数 | 命令 / 手段 | 结果 | 判定 |
|---|------|-------------|------|------|
| G1 | V1 文件 | `Test-Path core/engine.py` | **`False`** | ✅ |
| G2 | V1 import | 全仓 `*.py` 三类模式 | **`0`** | ✅ |
| G3 | 两文件收集 | `pytest ... --collect-only -q` | **`18 tests collected`** | ✅ |
| G4 | 测试文件数 | `Get-ChildItem tests -Filter 'test_*.py'` | **`48`** | ✅ |
| G5 | 全量测试 | `<PY312> -m pytest -q`（Agg） | **`507 passed, 82 warnings in 20.32s`** | ✅ |
| G6 | README 计数 | `Select-String '509' / '507'` | `509` = **0**；`507` = **4**（L7/L98/L262/L411） | ✅ |
| G7 | 门禁基线 | black / mypy | **`72`** / **`119`**（均 fail，预期） | ✅ 只降不升 |
| G8 | 门禁 `unit-tests` | Spec_Runner gate | **`verdict=pass`**（exit 0） | ✅ |
| G9 | `demo.py` 烟测 | 子进程 | **exit 0**（5.4s）；`cli.py --help` exit 0 | ✅ |

> **红→绿闭环**：R3 `20` → G3 `18`；R4 `50` → G4 `48`；R5 `509`×4 → G6 `507`×4 + `509`=0；R6 破坏性证据 → G5 `507 passed` 全绿。R6 的形态偏差不改结论（删除生效），已登记为 F-9-1 并回写 IMPL §6.1。

### 10.3 Step 9 实施发现（F-9 系列，单 Agent 自查 / RULE-4）

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-9-1 | P3 | IMPL §6.1 R6 预测「删除后两测试文件各 1 个 collection ERROR（2 errors）」，实测为 **1 collection error + 1 runtime failure**——`test_compatibility.py` 的 V1 import 位于 `test_new_import_paths` 函数体内，只会在运行时失败 | **已回写** IMPL §6.1 R6 与 §6.2 注；CHECKLIST B4 按实测记 ⚠️。删除生效结论不变 |
| F-9-2 | P3 | `README.md` L359 目录树仍写 `engine.py / engine_v2.py # 回测引擎 (V1 deprecated, V2 with DI)`——DESIGN D5 的 4 行清单未覆盖（属「未标注的 V1 路径」，与 DESIGN §2 验收口径冲突） | **已修**：改为 `engine_v2.py # 回测引擎 (V2 with DI)`；D4 实测列注明清单外第 5 行 |
| F-9-3 | P3 | CHECKLIST E6 判据 `git cat-file -s = 29910 B` 与实测 **29163 B** 不符 | **口径澄清**：29910 B 是 CRLF 工作区尺寸，repo blob（LF）为 29163 B，差值 747 = 换行符数；同因，`Measure-Object -Line = 724` 是**非空行**口径，`git diff --numstat` 的 747 为文件实际行数（同理 `test_visual_trace` 238→255、`_v2` 179→192）。可恢复性不受影响；C3 按实际行数计 |
| F-9-4 | P3 | IMPL §5「V8 清理契约」称 `demo_data/` **未被忽略**，实测 `.gitignore:67` 的 `*.pkl` 已覆盖其全部内容，故 `git status` 从不显示该目录 | **口径澄清**：C4 判定改为「两目录已删除 + `git status` 无 demo 条目」；清理动作照常执行（`demo_output/` 由 `.gitignore:56` 覆盖） |
| F-9-5 | P3 | A3 判据 `BacktestEngine(` 裸文本会被非 V1 的 `DetailedBacktestEngine(`（`examples/full_backtest_demo.py:767`）误命中 | **判定收紧**：以 `(?<![A-Za-z_])BacktestEngine\(` 计数 = **0**；A3 实测列注明该假阳性 |

> 5 项均为 P3 口径/判据问题，**0 项阻断**、**0 项行为回归**。F-9-1 已按要求回写 IMPL；其余 4 项在本节留证，Step 10 审计时复核。

## 11. Step 10 ADD 审计（已执行，2026-11-09）

- **时点**：2026-11-09，实施完成后独立执行（RULE-1）
- **审查者**：单 Agent 自查（单视角）（RULE-4）
- **取证方式**：门禁链（session `factorv3-p001-td3-stage3-20261109` seq 6-9）+ `git diff` 全文盲区扫描 + 静态读码 + 审计时点不变式复跑；证据绑 §8 矩阵

### Phase 0: Spec 质量门

- [x] DESIGN/IMPL 无「合理处理 / 适当时机 / 酌情 / 视情况 / 尽量 / 按需 / 尽可能 / 大概 / 大约 / 等等」类不可审计措辞——两文档 `Select-String` 扫描 **0 命中**
- [x] 每个设计元素可对应到实现或验证：D1→A1；D2→A3/A4；D3→A5/A6/A7/B6；D4→A8；D5→D1-D5；D6→E3；D7→A4；DESIGN §3.3→A9/E2；§5 契约→B1-B3

### Phase 1: 完整性（design → code）

- [x] **D1 删除**：`core/engine.py` `Test-Path=False`；无 shim / 空壳 / re-export（`core/__init__.py:11` 仅历史注释）
- [x] **D2 迁移**：6/6 脚本落地——5 个 `create_default_engine`（5 文件 / 6 调用）+ 1 个 `BacktestEngineV2` 手工装配；`(?<![A-Za-z_])BacktestEngine\(` = **0**
- [x] **D3 清理**：3 文件删除（`engine.py` + 2 个 trace）+ g2/g3 移除；`test_compatibility` 迁移后仍 **6 项**
- [x] **D4 注释**：**5 行 / 3 文件**；历史表述 `agents/multi_strategy_engine.py:64` 原样保留
- [x] **D5 文档**：ARCH 3 个目标（4 个 hunk，表头+状态各占 1 行）/ WIKI **25 编辑点**（25 hunk，含 1 条「已移除」注记插入）/ DEC 1 / README 4+1 / CHANGELOG 1 条
- [x] **D6 破坏性**：E3 子进程 `ModuleNotFoundError` exit 1；无兼容层
- [x] **D7**：5 行 `core.*` 导入 + `build_trigger(config.rebalance, dm.trade_dates)` @L104；11 项属性直装配保留

### Phase 2: 忠实度（双向对照）

- [x] 代码 diff 全文（11 文件）逐行比对 IMPL §3 前后文本：**新增 25 行逐字吻合**（`core/__init__` 2 / `engine_plugins` 2 / `walk_forward` 1 / examples 19 / `test_compatibility` 1）
- [x] 删除侧逐项命中 IMPL T-4 清单：`warnings` 1 + `ExitStack` 1 + `core.engine` 1 + `_FakeCombiner` 6 + `_run_engine_v1` 23 + g2/g3 19 = **51 行**
- [x] 文档 hunk 计数：ARCH **4** / WIKI **25（含注记 1）** / DEC **1** / README **5** / CHANGELOG **1** / PROGRESS **1 块** / TD-3 **1 块**——与 DESIGN §3 精确动作一致（README 第 5 行为 F-9-2 修正）
- [x] numstat 对账：代码 `25 / 1270`、文档 `64 / 111`；与 C3 净删除 **1245** 自洽
- [x] 偏差登记：F-9-2（README L359）、F-9-3（E6 字节/行数口径）、F-9-5（A3 判据假阳性）——均已在 §10.3 留证

### Phase 3: 必要性（code → design）

- [x] 代码新增 25 行逐行可归属：examples 19 → D2/D7；`test_compatibility` 1 → D3；注释 5 → D4——**0 行无依据**
- [x] 文档新增 64 行逐块可归属 D1-D5/D8；无「顺手优化」
- [x] **盲区扫描**（E4，扫描范围：11 个代码文件 diff 全文 + 7 个文档 diff 全文 + 4 份新文档）：**发现 1 项**设计外改动（README L359 目录树残行，已修）；其余 **0 项**
- [x] 保护路径 12 项 `git diff --stat` 空；历史记录 5 类 diff 空

### Phase 4: 语义

- [x] 目标未降级：不是「`507 passed`」本身，而是「V1 不可达（E3）+ 6 examples 全迁移 + 文档一致 + 无 shim」四层同时成立
- [x] Iron Law 核对：测试绿 ≠ 设计落地——以 §8 十类取证 + Phase 1/2 双向映射补足；A1/A3/A5/A6 用文件存在性与文本计数，而非测试结果
- [x] 已知 fail 未伪装：black 72 / mypy 119 于门禁 seq 8/9 复跑仍 fail；远端 CI 与 5 个 examples 运行分别标 `[未在远端执行]` / `[未在 CI 执行]`
- [x] 行为语义：`demo.py` 改由 V2 执行 `FactorPipeline`（数值变化）已在 CHANGELOG 注明；`full_backtest_2020_2026_simple.py` 的 D7 修复使原本 ImportError 的脚本首次可导入（`py_compile` 通过）
- [x] 审计时点不变式复跑：`507 passed, 82 warnings in 29.52s`；V1 import 边界化计数 **0**

### 11.1 审计发现

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-A1 | P3 | 审计复跑用 `Select-String -SimpleMatch 'import core.engine'` 会命中 `import core.engine_v2` / `core.engine_v3_vector`（5 处假阳性） | 判据须加词边界（`(?![_A-Za-z])`）；边界化后 **0**。已在 Phase 4 留证，不改实现 |

> F-9-1~F-9-5 复核：F-9-1 已回写 IMPL §6.1；F-9-2 已修 README L359；F-9-3/F-9-4/F-9-5 为口径澄清，实测列已按澄清后口径记录。**无新增 P1/P2**。

### 11.2 审计结论

| 项 | 结论 |
|----|------|
| Phase 0-4 | **全过**（0 项退回重写 / 0 项静默偏离 / 0 项无依据行为 / 0 项意图错位） |
| P1 阻断 / P2 应修 / P3 提示 | **0 / 0 / 1**（F-A1，判据边界，非实现缺陷）+ F-9 系列 5 项已处置 |
| 门禁链 | probe **pass** / unit-tests **pass** / black-check **fail(72)** / mypy-check **fail(119)**——与 §7 预期逐项一致 |
| 证据绑定 | §8 矩阵 9 类手段覆盖全部 43 项；无 E5 进入结论；远端项均带限定标注 |

## 12. 结论（Step 10 回填）

| 项 | 结论 |
|----|------|
| 验收项达成率 | **43 / 43（100%）**——A10/C4/D8/F6 全部回填；B4 以 F-9-1 修正判据达成；B8/E4 按「本地执行 + 远端限定」口径达成 |
| 阻断项 | **0**（P1/P2 = 0） |
| 门禁 verdict | **2 pass + 2 expected-fail**；`replay: 9 rows OK` |
| U 项 | **U-003 已关闭**（Step 1 实测 10 个导入文件）；无新增 U 项 |
| P-001 状态 | **done**（2026-11-09；Step 1-10 全通过；**工作区未提交**，提交后需将 §8 E3 行绑定 commit hash） |
| 遗留 | 远端 CI 3.10/3.11/3.12 未执行（本批不强制，推演 `500 passed, 1 skipped`）；5 个 examples 运行时依赖 `E:/Ashare_data`，`[未在 CI 执行]` |

---

## 13. 验收项统计（完结态）

| 分类 | 项数 | 说明 |
|------|------|------|
| A 功能完整性 | 10 | A1-A10 全部 ✅ |
| B 测试完整性 | 9 | 8 项 ✅ + B4 ⚠️ 按 F-9-1 修正后的判据达成 |
| C 性能与资源 | 4 | C1-C4 全部 ✅ |
| D 文档一致性 | 8 | D1-D8 全部 ✅（D7 属 Step 8） |
| E 兼容性与安全 | 6 | E1-E6 全部 ✅（E4 为边界声明：除 `demo.py` 外运行 `[未在 CI 执行]`） |
| F 代码质量 | 6 | F1-F6 全部 ✅（F2/F3 为 expected-fail 读数） |
| **合计** | **43** | **43/43 达成**；P1/P2 = 0；P3 = F-9-1~F-9-5 + F-A1 |
