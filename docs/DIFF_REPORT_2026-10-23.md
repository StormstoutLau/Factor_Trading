# 完整差异报告 — 技术债清理会话（2026-10-23）

> 生成时间：2026-10-23 23:24（UTC+8）
> 基线提交：`9aded2dbf9cd15427f957f6ab3656df61e1cb153`（2026-06-20，`docs: LLM预测替代真实值的推断风险 · 问题跟踪`）
> 当前 HEAD：`699063f2ace02454037fc8034c7a9d1647a8b53d`（`refactor(TD-5): 移除旧版过滤器 universe.py`）
> 证据采集方式：git 命令、pytest 输出、R-1 基准 CSV 重算、受控对比脚本、源码行号核对

---

## 0. 阅读说明与证据等级

本报告中的每条事实断言均标注证据来源：

| 标记 | 含义 | 可复核方式 |
|------|------|-----------|
| `[GIT]` | git 直接输出 | 报告内附命令，可在当前仓库复现 |
| `[TEST]` | pytest 运行结果 | 附命令与日志路径 |
| `[RUN]` | 本次执行产生的数值/文件 | 附命令、CSV 路径与 SHA256 |
| `[CODE]` | 源码行号 | 给出文件与当前行号，可直接打开核对 |
| `[SESSION]` | 仅来自本次会话的中间快照 | 不是持久化 git 证据，已明确标注 |

本报告文件本身是新增的报告产物，不计入下述变更集。

---

## 1. 执行摘要

| 项目 | 文件数 | 行变更 | 状态 |
|------|--------|--------|------|
| 已提交变更（基线 `9aded2d` → HEAD `699063f`） | 34 | +2538 / -550 | 5 个提交，已入库 |
| 未提交：TD-3 Stage 2（本次任务） | 6 | +22 / -12 | 待提交 |
| 未提交：工作区其他既有改动（非本次任务） | 8 个已跟踪 + 2 个未跟踪 | +426 / -156（已跟踪部分） | 未纳入本次变更 |

验证结果：

- R-1 基准：CLI 默认配置 V1 +16.7918% → V2 +6.7661%；受控对比（关闭因子处理）两引擎 500 个交易日逐日净值完全一致，最大绝对差异 0.000000。`[RUN]`
- 全量回归：503 passed。`[TEST]`

---

## 2. 变更集 A：TD-3 Stage 2（未提交，本次任务）

### 2.1 文件清单与用途

数据来源：`git diff --numstat`、`git diff --name-status`。`[GIT]`

| 文件 | +/- | 变更性质 | 关键位置 |
|------|-----|----------|----------|
| `cli.py` | +2 / -2 | 代码：切换默认引擎 | 导入 `:36`，实例化 `:77` |
| `docs/RESEARCH_tech_debt_cleanup.md` | +4 / -2 | 文档：TD-3 修正状态、P1 勾选、进度 | `:95`、`:284`、`:318` |
| `CHANGELOG.md` | +1 / -0 | 文档：Unreleased / Changed | `:18` |
| `docs/DEVLOG.md` | +7 / -0 | 文档：当日变更记录 | `:9-14` |
| `README.md` | +5 / -5 | 文档：两处示例改用工厂 | `:103/:114`、`:239/:244/:249` |
| `docs/CODE_WIKI.md` | +3 / -3 | 文档：快速开始示例改为现行导入路径 | `:857-858`、`:874` |

### 2.2 完整差异（逐字摘自 `git diff`）`[GIT]`

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index e9bd4b5..babc2a7 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -15,6 +15,7 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 - **demo_data 复权文件缺失**: `examples/demo.py` 生成器改为输出 `stock_adj.pkl`（与配置默认一致），修复旧布局导入与硬编码路径；本地补齐 `demo_data/stock_adj.pkl`
 
 ### Changed
+- **CLI 默认引擎**: `python cli.py run` 从已弃用的 V1 `BacktestEngine` 切换至 `core.factory.create_default_engine()`（V2）。V2 会执行 `FactorPipeline`，`--winsorize/--standardize/--fill/--neutralize` 参数自此真实生效（此前在 V1 下被忽略），默认结果随之变化；R-1 受控对比确认关闭因子处理后两引擎逐日净值完全一致（最大差异 0.000000）
 - **README**: Quick Start 增加 `python examples/demo.py` 数据生成步骤；测试统计更新为 503 passed / 49 files
 - **CODE_WIKI**: 数据格式表复权因子文件名改为 `stock_adj.pkl`
 - **仓库卫生**: `memory/` 加入 `.gitignore` 并移出版本跟踪（本地 8 个 JSON 保留）；`conversation/` 7 个文件归档至 `docs/archive/conversation/`，`archive/` 忽略规则收窄为根级 `/archive/`
diff --git a/README.md b/README.md
index 837293b..73c4356 100644
--- a/README.md
+++ b/README.md
@@ -100,7 +100,7 @@ python cli.py test
 
 ```python
 from core.config import BacktestConfig, FactorConfig, OptimizerConfig
-from core.engine import BacktestEngine
+from core.factory import create_default_engine
 
 config = BacktestConfig(
     data_dir="./demo_data",
@@ -111,7 +111,7 @@ config = BacktestConfig(
     initial_capital=10_000_000,
 )
 
-engine = BacktestEngine(config)
+engine = create_default_engine(config)
 engine.setup()
 results = engine.run()
 
@@ -236,17 +236,17 @@ uv sync
 
 ```python
 from core.config import BacktestConfig, FactorConfig, OptimizerConfig, RebalanceConfig
-from core.engine import BacktestEngine
+from core.factory import create_default_engine
 
 config = BacktestConfig(
     data_dir="./demo_data",
     factor_files=["factor_value.pkl"],
-    factor=FactorConfig(winsorize_method="mad", standardize="zscore"),
+    factor=FactorConfig(winsorize_method="mad", standardize_method="zscore"),
     optimizer=OptimizerConfig(method="equal_weight", target_count=30),
     rebalance=RebalanceConfig(method="fixed", frequency="monthly"),
     initial_capital=10_000_000,
 )
-engine = BacktestEngine(config)
+engine = create_default_engine(config)
 engine.setup()
 results = engine.run()
 ```
diff --git a/cli.py b/cli.py
index 2488ddb..4ac3f4b 100644
--- a/cli.py
+++ b/cli.py
@@ -33,7 +33,7 @@ def cmd_run(args: argparse.Namespace) -> None:
 
     try:
         from core.config import BacktestConfig, FactorConfig, OptimizerConfig, RebalanceConfig, CostConfig
-        from core.engine import BacktestEngine
+        from core.factory import create_default_engine
 
         data_dir = args.data_dir or "./demo_data"
         config = BacktestConfig(
@@ -74,7 +74,7 @@ def cmd_run(args: argparse.Namespace) -> None:
         print(f"  Neutralize:  {not args.no_neutralize}")
         print()
 
-        engine = BacktestEngine(config)
+        engine = create_default_engine(config)
         engine.setup()
 
         print(f"  Trade dates: {len(engine.dm.trade_dates)}")
diff --git a/docs/CODE_WIKI.md b/docs/CODE_WIKI.md
index b076eb1..015bbe3 100644
--- a/docs/CODE_WIKI.md
+++ b/docs/CODE_WIKI.md
@@ -854,8 +854,8 @@ pip install -r requirements.txt
 
 ```python
 from pathlib import Path
-from config import BacktestConfig, CostConfig, UniverseConfig, FactorConfig, OptimizerConfig, RebalanceConfig
-from engine import BacktestEngine
+from core.config import BacktestConfig, CostConfig, UniverseConfig, FactorConfig, OptimizerConfig, RebalanceConfig
+from core.factory import create_default_engine
 
 # 创建配置
 config = BacktestConfig(
@@ -871,7 +871,7 @@ config = BacktestConfig(
 )
 
 # 运行回测
-engine = BacktestEngine(config)
+engine = create_default_engine(config)
 engine.setup()
 results = engine.run()
 
diff --git a/docs/DEVLOG.md b/docs/DEVLOG.md
index 6c69ba1..de31738 100644
--- a/docs/DEVLOG.md
+++ b/docs/DEVLOG.md
@@ -6,6 +6,13 @@
 
 ## 2026-10-23
 
+### TD-3 Stage 2：CLI 切换至 V2 引擎
+- **类型**: 重构（行为变更）
+- **文件**: `cli.py`
+- **内容**: `cmd_run` 由 `BacktestEngine`（V1，已弃用）改为 `core.factory.create_default_engine()`（V2）；V2 执行 `FactorPipeline`，CLI 的 `--winsorize/--standardize/--fill/--neutralize` 参数自此真实生效
+- **验证**: R-1 基准 V1 +16.79%（终值 11,679,182）→ V2 +6.77%（终值 10,676,608）；关闭因子处理的受控对比下两引擎 500 日净值逐日一致（最大差异 0.000000）；全量 503 passed
+- **关联**: TD-3, `docs/RESEARCH_tech_debt_cleanup.md`
+
 ### 技术债调研归档（Phase 0）
 - **类型**: 文档
 - **文件**: `docs/RESEARCH_tech_debt_cleanup.md`（归档）、`docs/ARCHITECTURE.md`（修正）
diff --git a/docs/RESEARCH_tech_debt_cleanup.md b/docs/RESEARCH_tech_debt_cleanup.md
index 2b1dfd8..a0262d5 100644
--- a/docs/RESEARCH_tech_debt_cleanup.md
+++ b/docs/RESEARCH_tech_debt_cleanup.md
@@ -92,6 +92,8 @@ def create_default_engine(config: BacktestConfig) -> 'BacktestEngineV2':
 
 **源码级溯源补充**: engine.py 的弃用标记是**完整的双保险** —— module docstring 第 3 行 "⚠️ DEPRECATED" + 类 docstring `.. deprecated::` + 构造函数内运行时 `warnings.warn(DeprecationWarning)`（engine.py:54-59）。即 PEP 594 的 Stage 1（Deprecate）**已在源码层面完成**，剩余工作仅为 Stage 2（cli.py 替换）与 Stage 3（移除），P1 工作量比预评估更小。
 
+**修正状态（2026-10-23，Stage 2 已完成）**: `cli.py:36` 改为 `from core.factory import create_default_engine`，`cli.py:77` 改为 `create_default_engine(config)`。R-1 基准对比：CLI 默认配置下 V1 +16.79%（终值 11,679,182）→ V2 +6.77%（终值 10,676,608）。受控对比（`winsorize/standardize/fill=none`、`neutralize=False`）显示两引擎 **500 个交易日逐日净值完全一致（最大绝对差异 0.000000）**，差异根因是 V1 `_precompute_factors` 直接使用原始因子、V2 执行 `FactorPipeline.process` —— CLI 暴露的 `--winsorize/--standardize/--fill/--neutralize` 参数此前在 V1 下被忽略，切换后开始生效，属预期的行为变更。全量测试 503 passed。
+
 ### TD-4: Factor_DB 实现与文档不符（文档幻觉 H-1）
 
 **现状**:
@@ -279,7 +281,7 @@ Qlib 的数据层抽象将数据访问解耦为三类 Provider：
 
 ### P1 — 本迭代内（低风险代码改动）
 
-4. **TD-3 Stage 2**: cli.py 从 V1 引擎切换至 `factory.create_default_engine()`（Stage 1 弃用警告源码已存在，直接进替换），切换前后跑 R-1 基准对比
+4. ✅ **[已完成 2026-10-23] TD-3 Stage 2**: cli.py 已从 V1 引擎切换至 `factory.create_default_engine()`；R-1 已跑，两引擎机制一致（受控对比逐日净值完全相同），默认结果差异仅来自因子处理管道生效
 5. ✅ **[已完成 2026-10-23] TD-5**: `filter/universe.py` 的 2 个测试文件已迁移至 clean 版，旧版已移除（源码级溯源确认生产零引用，无需观察期）
 
 ### P2 — 下一迭代
@@ -313,7 +315,7 @@ Qlib 的数据层抽象将数据访问解耦为三类 Provider：
 
 ### 7.2 下一步（Phase 1 - 设计）
 
-**当前进度（2026-10-23）**: P0-1（TD-6）、P0-2（TD-7）、P0-3 均已完成；P1 的 TD-5 已完成；TD-3 Stage 2 待执行。
+**当前进度（2026-10-23）**: P0-1（TD-6）、P0-2（TD-7）、P0-3 均已完成；P1 的 TD-5 与 TD-3 Stage 2 已完成；剩余 P2（TD-3 Stage 3 移除 engine.py、TD-2 冻结标注）。
 
 依据本调研，Phase 1 需产出 `DESIGN_tech_debt_cleanup.md`，内容应包含：
```

### 2.3 行为变更的技术依据 `[CODE]`

| 断言 | 代码证据 |
|------|----------|
| V1 直接使用原始因子 | `core/engine.py:142` `raw = self.dm.load_factor(fname)`；`:146` `self._composite_signal = raw.fillna(0)` |
| V2 执行因子处理管道 | `core/engine_v2.py:264` `processed = self.pipeline.process(raw)`；`:269` `self._composite_signal = processed.fillna(0)` |
| CLI 此前确实调用 V1 | 切换前运行输出 `cli.py:77: DeprecationWarning: BacktestEngine is deprecated, use BacktestEngineV2 from engine_v2`（见 5.1） |
| README 原示例参数名无效 | `FactorConfig(standardize="zscore")` 实测抛出 `TypeError: FactorConfig.__init__() got an unexpected keyword argument 'standardize'`；`standardize_method` 为合法字段 |

结论：两引擎的再平衡、成交、估值机制一致；默认回测结果的变化来自因子预处理开始真实生效，属于 CLI 参数从“静默无效”到“生效”的行为修正，而非引擎逻辑回归。

---

## 3. 变更集 B：工作区其他未提交改动（非本次任务）

下列文件在本次任务开始前已处于修改状态；本次任务未对其执行写操作。来源为会话初始快照 `[SESSION]`，不作为 git 历史证据。`[GIT]` 仅证明它们当前仍未提交。

| 文件 | +/- | 状态 |
|------|-----|------|
| `__init__.py` | +5 / -31 | 已跟踪，未提交 |
| `core/__init__.py` | +8 / -77 | 已跟踪，未提交 |
| `docs/ARCHITECTURE_ANALYSIS.md` | +2 / -0 | 已跟踪，未提交 |
| `docs/LLM_PREDICTION_AS_TRUTH_RISK.md` | +321 / -8 | 已跟踪，未提交 |
| `docs/REFACTORING_SUMMARY.md` | +2 / -0 | 已跟踪，未提交 |
| `pyproject.toml` | +13 / -0 | 已跟踪，未提交 |
| `web/cli.html` | +26 / -20 | 已跟踪，未提交 |
| `web/index.html` | +49 / -20 | 已跟踪，未提交 |
| `docs/DECISIONS.md` | 118 行 | 未跟踪 |
| `docs/SPEC_STANDARD.md` | 271 行 | 未跟踪 |

已跟踪部分合计：+426 / -156。`[GIT]`

---

## 4. 变更集 C：已提交部分（基线 → HEAD）

数据来源：`git diff --name-status 9aded2d..HEAD`、`git diff --shortstat 9aded2d..HEAD`、`git show --stat`。`[GIT]`

### 4.1 提交清单

| 提交（完整哈希） | 信息 | 文件数 |
|------------------|------|--------|
| `65d750ff430020ce8849bc4ef3fd64d2dc348ce4` | `chore(TD-6): 停止跟踪 memory/ 本地会话文件` | 8 |
| `f4c13c31a7dad1f99e70d5d64197d8f012602800` | `chore(TD-6/TD-7): 补齐 memory 忽略规则并归档 conversation` | 12 |
| `84e9d4ce6fb057fae21dc8d12d76778f72435916` | `fix(demo): 生成 stock_adj.pkl 并对齐 README/CODE_WIKI` | 3 |
| `c0d34e27ca84c43ddc0d088b9db4f553ce576f07` | `fix(critical-rebalance): 调出持仓强制清仓并统一双引擎目标持仓` | 10 |
| `699063f2ace02454037fc8034c7a9d1647a8b53d` | `refactor(TD-5): 移除旧版过滤器 universe.py` | 6 |

累计：34 个文件，+2538 / -550。

### 4.2 文件状态清单

| 状态 | 文件 |
|------|------|
| 新增（A） | `core/target_positions.py`、`tests/test_rebalance_exits.py`、`docs/ARCHITECTURE.md`、`docs/CHECKLIST_critical_rebalance_fix.md`、`docs/DESIGN_critical_rebalance_fix.md`、`docs/DEVLOG.md`、`docs/IMPL_critical_rebalance_fix.md`、`docs/RESEARCH_tech_debt_cleanup.md` |
| 修改（M） | `.gitignore`、`CHANGELOG.md`、`README.md`、`core/engine.py`、`core/engine_v2.py`、`docs/CODE_WIKI.md`、`examples/demo.py`、`tests/test_p0_engine_integration.py`、`tests/test_pending_order_improvements.py`、`tests/test_v3_engine_integration.py` |
| 删除（D） | `filter/universe.py`、`memory/` 下 8 个 JSON 文件 |
| 重命名（R100） | `conversation/` 下 7 个文件 → `docs/archive/conversation/` |

逐文件行数可用 `git show --stat <hash>` 复核；提交内容可用 `git show <hash>` 复核。

---

## 5. 验证证据

### 5.1 R-1 CLI 基准回测

执行环境：`C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`，工作目录 `f:\Coding\Factor_Trading_v3.0`，数据 `demo_data/`，其余为 CLI 默认参数。`[RUN]`

切换前（V1）：

```powershell
& "C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe" cli.py run --output "$env:TEMP\td3_r1_before.csv"
```

关键输出（含弃用警告，证明运行时确为 V1）：

```text
cli.py:77: DeprecationWarning: BacktestEngine is deprecated, use BacktestEngineV2 from engine_v2
  engine = BacktestEngine(config)
Total Return:   +16.79%
Annual Return:  +8.45%
Annual Vol:     8.10%
Sharpe Ratio:   1.04
Max Drawdown:   -7.89%
Trading Days:   501
Final Value:    ¥11,679,182
```

切换后（V2）：

```powershell
& "C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe" cli.py run --output "$env:TEMP\td3_r1_after.csv"
```

关键输出：

```text
Total Return:   +6.77%
Annual Return:  +3.40%
Annual Vol:     8.01%
Sharpe Ratio:   0.43
Max Drawdown:   -8.07%
Trading Days:   501
Final Value:    ¥10,676,608
```

指标重算（直接读取两份 CSV，使用 CLI 相同公式）：`[RUN]`

| 指标 | V1（before） | V2（after） |
|------|--------------|-------------|
| 累计收益 | +16.7918% | +6.7661% |
| 年化收益 | +8.4462% | +3.4033% |
| 年化波动 | 8.0993% | 8.0062% |
| Sharpe | 1.0428 | 0.4251 |
| 最大回撤 | -7.8930% | -8.0745% |
| 交易日 | 501 | 501 |
| 终值 | 11,679,182.47 | 10,676,608.18 |

CSV 完整性：

| 文件 | 行数（含表头） | SHA256 |
|------|----------------|--------|
| `%TEMP%\td3_r1_before.csv` | 502 | `E364DC8F373EB9A8550340E8EA945ACEB90F33694F7D203C822C34551AF19F28` |
| `%TEMP%\td3_r1_after.csv` | 502 | `81EE33F5D7941C3652835C46AF6AEAB61E8A8F58748F3ACA5F9F90A52715256D` |

确定性复核：切换后再次执行 CLI 输出至 `%TEMP%\td3_r1_recheck.csv`，SHA256 与 after 完全一致（`81EE33F5…`）。`[RUN]`

### 5.2 受控对比（关闭因子处理）

目的：隔离因子处理管道的影响，验证两引擎的调仓/成交/估值机制是否一致。

对比脚本：`%TEMP%\td3_r1_compare.py`（全文见附录 A）。两引擎使用同一份 `BacktestConfig`，其中：

- `FactorConfig(winsorize_method="none", standardize_method="none", fill_method="none", neutralize=False)`
- `OptimizerConfig(method="equal_weight", target_count=30)`
- `RebalanceConfig(method="fixed", frequency="monthly")`
- `CostConfig(commission_rate=0.0003, stamp_tax_rate=0.001, slippage_pct=0.001)`
- `initial_capital=10_000_000`，区间 `2020-01-01` ~ `2024-12-31`
- 引擎输出写入各自的临时目录，不写入仓库

执行与输出：`[RUN]`

```text
V1 final: 11,679,182.47
V2 final: 11,679,182.47
V1 days: 501, V2 days: 501
common days: 500
max abs diff: 0.000000
mean abs diff: 0.000000
identical: True
```

日志：`%TEMP%\td3_r1_compare.log`，SHA256 `87782FDD42E849144E1C7BECA2A58CF281C8F41FDAA962B929E794B7CDC7F3F6`。`[RUN]`

说明：两份净值序列均为 501 行，`2023-12-04` 各出现两次，唯一日期数为 500，因此日期交集计数为 500；两序列的重复日期集合一致，对比基于 500 个唯一日期。重复记录的成因本次未溯源。`[RUN]`

### 5.3 全量回归测试

```powershell
& "C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests -q --tb=short
```

结果：`503 passed, 82 warnings in 22.04s`。`[TEST]`

日志路径：`C:\Users\Peng\AppData\Local\Temp\trae-agent-toolhost\jobs\job-7972910ed5fb41fcbf181b46fa9c35a8\output.log`（第 471 行）。`[TEST]`

### 5.4 静态检查说明

本次任务未修改 `core/` 下任何模块。CI 的 mypy 范围为 `mypy core/`（`.github/workflows/tests.yml:41`），因此未对 `cli.py` 单独运行 mypy。`[CODE]`

---

## 6. 可追溯矩阵

| 断言 | 证据 | 复核命令/位置 |
|------|------|----------------|
| 工作区 TD-3 变更仅涉及 6 个文件 | `[GIT]` | `git diff --name-status` |
| TD-3 变更行数为 +22 / -12 | `[GIT]` | `git diff --numstat` 求和 |
| CLI 导入与实例化位置为 36/77 行 | `[CODE]` | `Select-String -Path cli.py -Pattern 'create_default_engine'` |
| V1 使用原始因子、V2 使用处理后的因子 | `[CODE]` | `core/engine.py:142,146`；`core/engine_v2.py:264,269` |
| 切换前 CLI 运行时确为 V1 | `[RUN]` | 5.1 中弃用警告原文 |
| 默认结果差异为 16.7918% → 6.7661% | `[RUN]` | 5.1 CSV 重算 |
| 关闭因子处理后两引擎逐日净值一致 | `[RUN]` | 5.2 受控对比输出 |
| 全量测试 503 passed | `[TEST]` | 5.3 命令与日志 |
| 已提交 5 个提交、34 个文件 | `[GIT]` | `git diff --shortstat 9aded2d..HEAD` |
| 其余未提交文件不属于本次任务 | `[SESSION]` + `[GIT]` | 会话初始快照；当前 `git diff --name-status` |

---

## 7. 未验证项与限制

1. **临时产物可失效**：`%TEMP%` 下的 CSV、日志与对比脚本可能被系统清理；本报告记录了 SHA256 与脚本全文，可据此复现，但不能据此恢复原始文件。
2. **切换前 CLI 无法直接重跑**：当前 `cli.py` 已切换至 V2；如需复现 V1 默认结果，可通过 `git show 699063f:cli.py` 取旧版入口，或直接运行附录 A 的受控脚本（其中显式实例化 V1 `BacktestEngine`）。
3. **demo 数据不在版本库**：`*.pkl` 被 `.gitignore:67` 忽略，R-1 结果依赖本地 `demo_data/`。若数据被重新生成，净值数值可能变化，需以相同数据文件重跑。
4. **`output/` 为忽略目录**：`output/` 被 `.gitignore:58` 忽略；本次 CLI 运行刷新了该目录下的报告文件（复核时 `portfolio_snapshots.csv` 修改时间由 04:02:44 变为 23:24:43），该目录不参与版本差异。
5. **工作区既有改动的来源**：仅能确认这些文件在本次任务开始前已处于修改状态，及其当前未提交状态；未核验其具体内容与产生时间。
6. **未运行的检查**：未运行 mypy（原因见 5.4）、未运行 black 检查（仓库已知基线不合规，见 TD-9），未对 `cli.py` 的其他子命令做端到端测试；本次仅执行了 `run` 子命令。

---

## 附录 A：受控对比脚本全文

来源：`%TEMP%\td3_r1_compare.py`。脚本仅在临时目录写入引擎报告，不修改仓库文件。

```python
"""R-1: V1 vs V2 引擎受控对比（因子处理全部关闭）"""
import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, r"f:\Coding\Factor_Trading_v3.0")

import numpy as np

from core.config import BacktestConfig, CostConfig, FactorConfig, OptimizerConfig, RebalanceConfig
from core.engine import BacktestEngine
from core.engine_v2 import BacktestEngineV2

warnings.simplefilter("ignore", DeprecationWarning)


def make_config(output_dir):
    return BacktestConfig(
        data_dir=Path("f:/Coding/Factor_Trading_v3.0/demo_data"),
        factor_files=["factor_value.pkl"],
        factor=FactorConfig(
            winsorize_method="none",
            standardize_method="none",
            fill_method="none",
            neutralize=False,
        ),
        optimizer=OptimizerConfig(method="equal_weight", target_count=30),
        rebalance=RebalanceConfig(method="fixed", frequency="monthly"),
        cost=CostConfig(commission_rate=0.0003, stamp_tax_rate=0.001, slippage_pct=0.001),
        initial_capital=10_000_000,
        start_date="2020-01-01",
        end_date="2024-12-31",
        output_dir=Path(output_dir),
    )


def run(engine_cls):
    with tempfile.TemporaryDirectory() as tmp:
        engine = engine_cls(make_config(tmp))
        engine.setup()
        results = engine.run()
        return results["portfolio_value"]


v1 = run(BacktestEngine)
v2 = run(BacktestEngineV2)

print(f"V1 final: {v1.iloc[-1]:,.2f}")
print(f"V2 final: {v2.iloc[-1]:,.2f}")
print(f"V1 days: {len(v1)}, V2 days: {len(v2)}")
common = v1.index.intersection(v2.index)
diff = (v1.loc[common] - v2.loc[common]).abs()
print(f"common days: {len(common)}")
print(f"max abs diff: {diff.max():.6f}")
print(f"mean abs diff: {diff.mean():.6f}")
print(f"identical: {np.allclose(v1.loc[common].values, v2.loc[common].values, rtol=1e-9, atol=1e-6)}")
```
