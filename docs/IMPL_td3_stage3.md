# TD-3 Stage 3（移除 core/engine.py） · 实施规划

> **文档编号**: IMPL_td3_stage3
> **阶段**: Phase 1 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: 完稿（Step 6 Review **通过**，2026-11-09；10 项复核 6 命中 + 6 项 P3 已回写，0 项阻断，见 §9）
> **上游**: [DESIGN_td3_stage3.md](DESIGN_td3_stage3.md)（Step 4 Review 通过，含 D1-D7）
> **下游**: [CHECKLIST_td3_stage3.md](CHECKLIST_td3_stage3.md)
> **证据时点**: 本仓读数 @ `696bd7b`；解释器 Python 3.12.10（F-R5）
> **档位**: T1（`core/`、`tests/`、`examples/`，Layer-1）
> **会话**: `factorv3-p001-td3-stage3-20261109`

---

## 1. 执行总览

### 1.1 任务分解

| ID | 任务 | 依赖 | 产出 | 验证 |
|----|------|------|------|------|
| T-0 | 记录 RED 基线（5 项负向断言 + 门禁基线） | — | §6.1 表 | 5 项 RED 全部「符合预期未达成」 |
| T-1 | 删除 `core/engine.py` | T-0 | 文件不存在 | `Test-Path` = False |
| T-2 | 删除 2 个 0 收集诊断脚本 | T-0 | 文件不存在 | `Test-Path` ×2 = False |
| T-3 | 迁移 6 个 examples（5 模板 A + 1 模板 B/D7） | T-1 | 6 文件修改 | `py_compile` 6/6 exit 0 |
| T-4 | 清理 `tests/test_rebalance_exits.py`（删 V1 helper/g2/g3） | T-1 | 14 → 12 项 | collect = 12 |
| T-5 | 修改 `tests/test_compatibility.py` L48 为 V2 导入 | T-1 | 6 项不变 | collect = 6 |
| T-6 | 注释/docstring 同步（4 处） | T-1 | 4 行 | 静态扫描 0 命中 |
| T-7 | 活文档同步（ARCH/WIKI/DECISIONS/README/CHANGELOG） | T-3~T-6 | 5 文件 | Step 8 机械核对 |
| T-8 | 台账同步（PROGRESS / RESEARCH_tech_debt_cleanup） | T-7 | 2 文件 | 行存在且状态正确 |
| T-9 | 全量验证 + 门禁 + E3 绑定 | T-1~T-8 | V1-V8 读数 | §5 全绿 / 门禁 pass |

### 1.2 执行顺序与依赖图

```
T-0 记录 RED
  │
  ├─► T-1 删 engine.py ──┬─► T-3 examples 迁移 ──┐
  │                      ├─► T-4 tests 清理 ─────┤
  │                      ├─► T-5 兼容性测试 ─────┼─► T-7 活文档 ──► T-8 台账 ──► T-9 验证
  │                      └─► T-6 注释/docstring ─┘
  └─► T-2 删 2 个死脚本 ───────────────────────────┘

任一步失败 → 停止 → 按 §7 回退（不跨步骤修补）
```

### 1.3 关键原则

| 原则 | 说明 |
|------|------|
| 先删后迁移（TDD 红→绿） | T-1/T-2 先制造 `ModuleNotFoundError`，作为删除生效的 RED 证据；T-3~T-5 修复至 GREEN |
| 单提交 | 全部任务完成后一次提交；不产生中间提交（R5） |
| 零算法变更 | 不改 `core/engine_v2.py` / `core/factory.py` / 任何算法与参数 |
| 精确行号 | 所有编辑按 DESIGN §5 与本文 §3 的行号锚点执行；行号漂移时以「唯一文本锚点」为准 |

---

## 2. T-0 前置：RED 基线记录

> **F5 先失败记录**：本批是删除型变更，「先失败」= 负向断言在当前树未达成。以下 5 项必须在 T-1 之前记录。

| ID | 断言 | 命令 | RED 读数（当前） | GREEN 目标 |
|----|------|------|------------------|------------|
| RED-1 | V1 文件应不存在 | `Test-Path core/engine.py` | `True` | `False` |
| RED-2 | 全仓 V1 import 应为 0 | 见 §5 V2 命令 | **10 个活跃 import**（6 examples + 4 tests） | `0` |
| RED-3 | 两测试文件应收集 18 | `<Python312> -m pytest tests/test_rebalance_exits.py tests/test_compatibility.py --collect-only -q` | `20`（14 + 6） | `18`（12 + 6） |
| RED-4 | 测试文件数应为 48 | `Get-ChildItem tests -Filter 'test_*.py'` | `50` | `48` |
| RED-5 | 活文档不应含旧计数 | `Select-String README.md -Pattern '509' -SimpleMatch` | 4 行命中 | 0 行（改为 507） |

**门禁基线（T-0 同时记录，T-9 对照）**：

| 门禁 | 基线读数 | 预期 T-9 |
|------|----------|----------|
| `unit-tests` | `509 passed, 82 warnings` | `507 passed` |
| `black-check` | `75 files would be reformatted`（fail） | `72`（仍 fail） |
| `mypy-check` | `168 errors`（fail） | `119`（仍 fail） |

---

## 3. 逐任务实施文本

### T-1 删除 `core/engine.py`

```powershell
Remove-Item core/engine.py
```

| 项 | 内容 |
|----|------|
| 接口影响 | `import core.engine` → `ModuleNotFoundError`（D6：无 shim） |
| 替代契约 | `core.factory.create_default_engine(config)` / `core.engine_v2.BacktestEngineV2` |
| 回退 | `git checkout 696bd7b -- core/engine.py` |
| 中间态预期 | `tests/test_rebalance_exits.py` 与 `tests/test_compatibility.py` 各 1 个 collection ERROR（`No module named 'core.engine'`）——**这是 T-1 生效的 RED 证据** |

### T-2 删除 2 个 0 收集诊断脚本

```powershell
Remove-Item tests/test_visual_trace.py
Remove-Item tests/test_visual_trace_v2.py
```

| 项 | 内容 |
|----|------|
| 依据 | 各 0 收集（`collected 0 items`，exit 5）；纯 V1 诊断；全仓活文档零引用（DESIGN §9.2 #9） |
| 回退 | `git checkout 696bd7b -- tests/test_visual_trace.py tests/test_visual_trace_v2.py` |
| 禁止 | 不使用 `test_visual_trace*` 通配（PowerShell 原生命令不展开） |

### T-3 迁移 6 个 examples

> **缩进契约（Step 6 注记 F-I2）**：以下迁移文本省略缩进展示；实施时**必须保留目标行原缩进**——`demo.py` L223-225（函数内 4 空格）、`full_backtest_2020_2026.py` L55（函数内 4 空格）、`run_full_backtest_fixed.py` L54（`try` 块内 8 空格）、`full_backtest_2020_2026_simple.py` L87/L92-96/L104（函数内 4 空格）；模块级行（`run_single_backtest.py` L13、`run_backtest_minimal.py` L20、`full_backtest_2020_2026.py` L16、`full_backtest_2020_2026_simple.py` L14、`run_full_backtest_fixed.py` L19）顶格。

#### T-3.1 `examples/demo.py`（模板 A，L223-225）

```python
# 旧
    from core.engine import BacktestEngine

    engine = BacktestEngine(config)
# 新
    from core.factory import create_default_engine

    engine = create_default_engine(config)
```

> 行为说明：demo 启用 `mad/zscore/neutralize`，V2 真实执行 `FactorPipeline`，输出数值会变化（R1，预期行为，无 golden 断言）。

#### T-3.2 `examples/run_single_backtest.py`（模板 A，L13 / L41）

```python
# 旧
from core.engine import BacktestEngine
...
engine = BacktestEngine(config)
# 新
from core.factory import create_default_engine
...
engine = create_default_engine(config)
```

> L50 `engine._composite_signal` 在 V2 存在（`engine_v2.py:158/269`）；`factor` 全 `none` → 与 V1 等价。

#### T-3.3 `examples/run_backtest_minimal.py`（模板 A ×2，L20 / L53 / L72）

```python
# 旧
from core.engine import BacktestEngine
...
engine_long = BacktestEngine(config_long)
...
engine_short = BacktestEngine(config_short)
# 新
from core.factory import create_default_engine
...
engine_long = create_default_engine(config_long)
...
engine_short = create_default_engine(config_short)
```

#### T-3.4 `examples/full_backtest_2020_2026.py`（模板 A，L16 / L55）

```python
# 旧
from core.engine import BacktestEngine
...
engine_full = BacktestEngine(config_full)
# 新
from core.factory import create_default_engine
...
engine_full = create_default_engine(config_full)
```

#### T-3.5 `examples/full_backtest_2020_2026_simple.py`（模板 B + D7，L14 / L87 / L92-96 / L104）

```python
# 旧（L14）
from core.engine import BacktestEngine
# 新
from core.engine_v2 import BacktestEngineV2

# 旧（L87）
engine = BacktestEngine(config)
# 新
engine = BacktestEngineV2(config)

# 旧（L92-96，先存缺陷，D7）
from portfolio import build_optimizer
from rebalance import build_trigger
from execution import ExecutionSimulator
from tracker import PositionTracker
from pending import PendingOrderQueue
# 新
from core.portfolio import build_optimizer
from core.rebalance import build_trigger
from core.execution import ExecutionSimulator
from core.tracker import PositionTracker
from core.pending import PendingOrderQueue

# 旧（L104，形参语义错误）
engine.trigger = build_trigger(config.rebalance, engine.optimizer)
# 新
engine.trigger = build_trigger(config.rebalance, dm.trade_dates)
```

> L91 `from filter import UniverseFilter` 保留（`filter/__init__.py:125` 已导出，实测有效）。
> 其余 11 项直装配（L98-110）保持不变。

#### T-3.6 `examples/run_full_backtest_fixed.py`（模板 A，L19 / L54）

```python
# 旧
from core.engine import BacktestEngine
...
engine = BacktestEngine(config)
# 新
from core.factory import create_default_engine
...
engine = create_default_engine(config)
```

**T-3 完成判据**：

```powershell
<Python312> -m py_compile examples/demo.py examples/run_single_backtest.py examples/run_backtest_minimal.py examples/full_backtest_2020_2026.py examples/full_backtest_2020_2026_simple.py examples/run_full_backtest_fixed.py
# exit 0
```

### T-4 清理 `tests/test_rebalance_exits.py`

**删除 1：import 区（L13 / L15 / L31）**

```python
-import warnings
...
-from contextlib import ExitStack
...
-from core.engine import BacktestEngine
```

**删除 2：`_FakeCombiner` 类（L228-230）**

```python
-class _FakeCombiner:
-    def __init__(self, *args, **kwargs):
-        pass
```

**删除 3：`_run_engine_v1()`（L294-316）**

```python
-def _run_engine_v1(tmpdir: str):
-    """V1 的 setup() 直接构造组件，故用 patch 注入等价 fake"""
-    ...（整函数 23 行）
-    return engine, results
```

**删除 4：两个 golden 测试（L343-359）**

```python
-    def test_g2_engine_v1_liquidates_exited_positions(self):
-        ...
-    def test_g3_engines_share_identical_targets(self):
-        ...
```

**保留**：`patch`（L286 `_run_engine_v2` 仍用）、`_FakeDataManager` / `_FakeUniverse` / `_FakePipeline` / `_Top2Optimizer` / `_AlwaysTrigger` / `_build_config` / `_run_engine_v2` / `_quantity` / g1/g4/g5 / U1-U9。

> **空行契约（Step 6 注记 F-I4）**：删除 `_FakeCombiner`（L228-230）、`_run_engine_v1`（L294-316，含其后 1 个空行）、g2/g3（L343-359，含中间空行）后，保持 PEP8 类间/方法间两空行间隔；以删除后 `py_compile` + collect = 12 为准。

**完成判据**：

```powershell
<Python312> -m pytest tests/test_rebalance_exits.py --collect-only -q
# 12 tests collected
```

### T-5 修改 `tests/test_compatibility.py`

```python
# 旧（L48）
from core.engine import BacktestEngine
# 新
from core.engine_v2 import BacktestEngineV2
```

> 保留「引擎导入路径有效」断言意图；不新增/删除测试项（仍 6 项）。

### T-6 注释与 docstring 同步

| 文件 | 行 | 旧 | 新 |
|------|----|----|----|
| `core/__init__.py` | L6 | `#     from Factor_Trading_v3_0.core.engine import BacktestEngine` | `#     from Factor_Trading_v3_0.core.factory import create_default_engine` |
| `core/__init__.py` | L9 | `#     from core.engine import BacktestEngine` | `#     from core.factory import create_default_engine` |
| `core/engine_plugins.py` | L14 | `engine = BacktestEngine(config)` | `engine = BacktestEngineV2(config)` |
| `core/engine_plugins.py` | L383 | `engine = BacktestEngine(config)` | `engine = BacktestEngineV2(config)` |
| `core/walk_forward_engine.py` | L45 | `...     base_engine=BacktestEngine,` | `...     base_engine=BacktestEngineV2,` |

> **不改** `agents/multi_strategy_engine.py:64`（历史沿革表述，D4）。
> `engine_plugins.py` 的 docstring 仅示例，无 import；若 Step 6 发现需补导入说明，按「注释级」处理，不引入运行代码。

### T-7 活文档同步

#### T-7.1 `docs/ARCHITECTURE.md`（3 处）

```markdown
# L81：整行删除
- | **Engine V1** | `engine.py` | 800+ | 经典回测引擎，config-driven setup/run cycle | ⚠️ 已弃用 |

# L198：表头与数据行
- | 特性 | Engine V1 | Engine V2 (主引擎) | Engine V3 (预筛选) |
+ | 特性 | Engine V1（已移除） | Engine V2 (主引擎) | Engine V3 (预筛选) |
...
- | 状态 | ⚠️ 已弃用 | ✅ 活跃 | ✅ 活跃 |
+ | 状态 | ❌ 已移除（P-001） | ✅ 活跃 | ✅ 活跃 |

# L304：整行删除
- | `core/engine.py` (V1) 未删除 | 标记已弃用但未移除，历史测试依赖 |
```

#### T-7.2 `docs/CODE_WIKI.md`（分级处理）

| 类别 | 行 | 动作 |
|------|----|------|
| ① 改名 | L23、L38、L99、L152、L705 | `engine.py` → `engine_v2.py`；**L23 目录锚点同步** `#12-回测引擎-enginepy` → `#12-回测引擎-enginev2py`（L705 标题同时改 `(engine_v2.py)`） |
| ①′ 类名同步 | L38、L98、L151 | `BacktestEngine` → `BacktestEngineV2`（ASCII 图内的类名，Step 6 补） |
| ② 体量行 | L127 | 整行改为：`` | `engine_v2.py` | 回测主循环（依赖注入 + factory 装配） | `BacktestEngineV2` | ~31KB | `` |
| ③ 耦合表 | L173 | 依赖列改为 `data, config, universe_filter, factor, portfolio, execution, rebalance, analytics`；说明改为「注入装配，不直接构造」 |
| ④ 调用图 | L925-946 | 全部 `engine.py` → `engine_v2.py`，并在代码块首行加注 `# V1 engine.py 已于 P-001 移除` |
| ⑤ §12 正文 | L705-788 | 整段替换为 ≤15 行 V2 摘要：标题 `## 12. 回测引擎 (engine_v2.py)`；要点 `BacktestEngineV2` / `create_default_engine` / 结论字典键 / 等价性证据 `CHANGELOG.md:21` / 「V1 已于 P-001 移除」（覆盖 L707/714 类名） |
| ⑥ §15.2 运行时序 | L952/954/964/972 | `BacktestEngine.` → `BacktestEngineV2.`（4 处方法链，Step 6 补） |

> 保留编号 12（不重排 13-15，避免锚点失效）。附录与前 11 章不动。

#### T-7.3 `docs/DECISIONS.md`（1 处）

```markdown
- **影响**: `core/engine_v2.py` (活跃), `core/engine_v3_vector.py` (活跃), `core/engine.py` (弃用)
+ **影响**: `core/engine_v2.py` (活跃), `core/engine_v3_vector.py` (活跃), `core/engine.py`（已于 P-001 移除）
```

#### T-7.4 `README.md`（4 处）

| 行 | 旧 | 新 |
|----|----|----|
| L7 | `Tests-509%20passed` | `Tests-507%20passed` |
| L98 | `# Output: 509 passed ✓` | `# Output: 507 passed ✓` |
| L262 | `**509 passed**` | `**507 passed**` |
| L411 | `509 tests, 50 files` | `507 tests, 48 files` |

#### T-7.5 `CHANGELOG.md`（`[Unreleased] > Removed` 追加）

```markdown
### Removed
- **TD-3 Stage 3（V1 引擎移除）**: 删除 `core/engine.py`（724 行，V1 已弃用并完成 Stage 1/2）；6 个 `examples/` 脚本迁移至 `create_default_engine`（手动装配脚本改用 `BacktestEngineV2`，并修复 5 行先存坏导入与 `build_trigger` 形参）；删除 g2/g3 两项 V1 golden 测试与 2 个 0 收集诊断脚本；测试 509 → 507、文件 50 → 48；等价性证据保留于本文件 R-1 对比（最大差异 0.000000）与 `docs/DIFF_REPORT_2026-10-23.md`
```

### T-8 台账同步

| 文件 | 动作 |
|------|------|
| `docs/PROGRESS.md` | **T-8 范围（T-9 前）**：§3.1 追加 Step 5-8 进度、门禁基线更新为 black 72 / mypy 119；**T-9 后补写**：Step 9/10 进度、P-001 行状态 `pending → done` |
| `docs/RESEARCH_tech_debt_cleanup.md` | 在 TD-3 复核记录（L333 附近）追加注记：`Stage 3 已执行（P-001，2026-11-09）`，不改历史结论 |

---

## 4. 接口签名与回退点

| 任务 | 接口/边界 | 签名或形态 | 回退点 |
|------|-----------|------------|--------|
| T-1 | 删除模块 | `core/engine.py` 移除；`import core.engine` → `ModuleNotFoundError` | `git checkout 696bd7b -- core/engine.py` |
| T-2 | 删除测试资产 | 2 个文件移除，pytest 收集数不变（0 项） | `git checkout 696bd7b -- <2 文件>` |
| T-3 | 工厂替代 | `create_default_engine(config: BacktestConfig) -> BacktestEngineV2` | `git checkout 696bd7b -- examples/` |
| T-3.5 | 手动装配 | `BacktestEngineV2(config)` + 11 项属性 + `build_trigger(config.rebalance, dm.trade_dates)` | 同上 |
| T-4 | 测试清理 | 删除 `_run_engine_v1` / g2 / g3；收集 14 → 12 | `git checkout 696bd7b -- tests/test_rebalance_exits.py` |
| T-5 | 导入替换 | `from core.engine_v2 import BacktestEngineV2` | `git checkout 696bd7b -- tests/test_compatibility.py` |
| T-6 | 注释同步 | 5 行文本替换，零运行影响 | `git checkout 696bd7b -- core/__init__.py core/engine_plugins.py core/walk_forward_engine.py` |
| T-7 | 文档同步 | 按 §3 T-7 精确文本 | `git checkout 696bd7b -- docs/README/CHANGELOG` |
| 整批 | — | 单提交 | `git revert <commit>` |

---

## 5. 验证断言（V1-V8）

| ID | 断言 | 命令（可重放） | 预期 |
|----|------|----------------|------|
| V1 | V1 文件不存在 | `Test-Path core/engine.py` | `False` |
| V2 | 全仓 V1 import 零命中 | `Get-ChildItem -Recurse -Filter *.py \| Select-String -Pattern 'from core.engine import','from core import engine' -SimpleMatch` | `0` hit |
| V3 | 6 examples + cli 语法有效 | `<Python312> -m py_compile examples/demo.py examples/run_single_backtest.py examples/run_backtest_minimal.py examples/full_backtest_2020_2026.py examples/full_backtest_2020_2026_simple.py examples/run_full_backtest_fixed.py cli.py` | exit `0` |
| V4 | 全量测试 | `$env:MPLBACKEND='Agg'; <Python312> -m pytest -q` | **`507 passed`** |
| V5 | 测试文件数 | `Get-ChildItem tests -Filter 'test_*.py'` | `48` |
| V6 | 两文件收集数 | `<Python312> -m pytest tests/test_rebalance_exits.py tests/test_compatibility.py --collect-only -q` | `18 tests collected` |
| V7 | 门禁基线 | `black --check core tests`；`mypy --explicit-package-bases core` | black `72` fail；mypy `119` errors fail（均预期） |
| V8 | 运行时烟测 | `<Python312> examples/demo.py`；`<Python312> cli.py --help` | exit `0`；跑后删除 `demo_data/`、`demo_output/` |

**V8 清理契约**：`demo_output/` 已被 `.gitignore` L56 覆盖；`demo_data/` **未被忽略**，必须手工删除，`git status` 应无新增未跟踪目录。

---

## 6. 红→绿执行序（F5 先失败记录）

### 6.1 RED 阶段（T-0 → T-2 完成）

| # | 读数 | 含义 |
|---|------|------|
| R1 | `Test-Path core/engine.py` = `True` | 删除前：V1 仍存在 |
| R2 | V1 import = `10` | 迁移前：10 处活跃引用 |
| R3 | 两文件收集 = `20` | g2/g3 仍在 |
| R4 | 测试文件 = `50` | 死脚本仍在 |
| R5 | README 509 = `4` 行 | 计数未更新 |
| R6 | T-1 后 `pytest tests/test_rebalance_exits.py tests/test_compatibility.py` | **2 errors**（`No module named 'core.engine'`）——删除生效的硬证据 |

> **R6 实测修正（Step 9，F-9-1）**：实际读数为 **1 个 collection error**（`test_rebalance_exits.py`，模块级 import）+ **1 个 runtime failure**（`test_compatibility.py::test_new_import_paths`，V1 import 在函数体内，只会在运行时失败）。「删除生效」结论不变，仅失败形态与「2 errors」预测不同。

### 6.2 GREEN 阶段（T-3 → T-9 完成）

| # | 读数 | 目标 |
|---|------|------|
| G1 | V1 文件 | `False` |
| G2 | V1 import | `0` |
| G3 | 两文件收集 | `18` |
| G4 | 测试文件 | `48` |
| G5 | 全量测试 | `507 passed` |
| G6 | `README.md` 中 `509` | `0` 行命中；`507` 命中 4 行（3 处 `507 passed` + 1 处 `507 tests, 48 files`） |
| G7 | black / mypy | `72` / `119`（预期 fail） |
| G8 | 门禁 `unit-tests` | `pass` |
| G9 | `demo.py` 烟测 | exit `0` |

> R6 的破坏性失败（实测 1 collection error + 1 runtime failure，见 §6.1 修正）必须**先观测到**再进入 T-3；若 T-1 后测试仍绿，说明删除未生效或存在缓存（检查 `__pycache__`）。

---

## 7. 低效与危险操作排除表

| 禁止操作 | 原因 | 替代 |
|----------|------|------|
| 全仓 `sed`/正则替换 `engine.py`→`engine_v2.py` | 会误改历史文档、RESEARCH、DESIGN、引号内字符串与 `batch_backtest/engine.py` | 按 §3 逐文件定点 |
| `git rm tests/test_visual_trace*` | PowerShell 原生命令不展开通配符 | 显式两个路径 |
| `py_compile examples/*.py` | 同上，字面量传参必失败 | 逐文件列举 |
| 运行 `black core tests`（写模式） | 会格式化 75 个既有文件，diff 爆炸 | 仅 `--check` 只读 |
| 修改 `pyproject.toml` 加 `filterwarnings=error` | 会改变全仓测试语义，超出本批范围 | 不触碰 |
| 保留 `core/engine.py` 空文件或 `__init__` re-export | 违反 D6，债务名存实亡 | 彻底删除 |
| 删除 `tests/test_batch_backtest.py` 等非本批文件 | 超出 DESIGN 删除边界 | 仅删 §3 T-1/T-2 列出的 3 个文件 |
| 用 `git add -A` 提交 | 可能带入 `demo_data/` 等运行产物 | 按文件清单 `git add` |
| 在工作区有未提交改动时执行 T-1/T-2 的 `Remove-Item` | 未提交的 engine.py 改动删除后无法从工作区找回（须靠 git 对象） | T-1 前确认 `git status --porcelain` 仅含本批预期条目 |

---

## 8. 回退点

| 触发条件 | 回退动作 | 恢复范围 |
|----------|----------|----------|
| T-3 任一脚本 `py_compile` 失败且 5 分钟内无法定位 | `git checkout 696bd7b -- examples/` + 撤销 T-1/T-2 | 6 examples + 2 scripts + engine.py |
| T-4 后收集数 ≠ 12 | `git checkout 696bd7b -- tests/test_rebalance_exits.py` | 测试文件完整恢复 |
| 全量测试出现非预期失败（≠ 507 且非已知基线） | `git revert` 整批或 `git checkout 696bd7b -- <相关文件>` | 按文件恢复 |
| 远端 CI 变红 | 本地复现 → 定位 → 单文件回退；必要时整批 revert | 见 DESIGN §7 |
| 整体放弃 | `git revert <P-001 commit>`（单提交） | 全部恢复 |

---

## 9. Step 6 Review（独立复核 pass，2026-11-09）

> 本节由 Step 6 独立执行并单独写入（RULE-1）；不复用 Step 5 的中间输出。**审查者**：单 Agent 自查（RULE-4）。**方式**：重读全文 + 重跑/重读目标文件核对每条实施文本的可执行性，不依赖正文自报。

### 9.1 门禁核对（SPEC_PROCESS Step 6 Review 清单）

| 门禁项 | 结论 | 证据 |
|--------|------|------|
| 所有依赖/API 真实存在 | ✅ | `create_default_engine`（`core/factory.py:242-257`）、`BacktestEngineV2`（`engine_v2.py:58`）、`build_trigger`（`core/rebalance.py`）、`build_optimizer`（`core/portfolio.py:404`）均已实测命中 |
| stdlib API 下限检查 | ✅ | 实施文本仅用 `Remove-Item` / `py_compile` / `git checkout` / `Select-String`；Python 侧无版本敏感 API |
| 所有签名可实现 | ✅（修正后） | T-3.5 的 `dm.trade_dates` 可用性已验证（见 9.2 #1）；§4 签名省略已修正（F-I3） |
| 无虚构的库或函数 | ✅ | 全部引用自本仓既有符号；`filter/__init__.py:125` 导出已实测 |
| 兼容性声明已验证 | ✅ | `demo.py` 数值变化（R1）属预期并有 CHANGELOG 承载；`test_new_import_paths` 路径全部有效 |
| 低效操作已排除 | ✅ | §7 排除表 8 条（通配符/写模式 black/`git add -A` 等），另经 9.2 #7 复核补 1 条 |

### 9.2 E-Review 复核表（独立重跑）

| # | 复核项 | 方法 | Step 6 读数 | 判定 |
|---|--------|------|-------------|------|
| 1 | T-3.5 `dm.trade_dates` 可用性 | 读 `full_backtest_2020_2026_simple.py` L20-60 | `dm`（L58）与 `engine`（L87）同在 `run_simplified_backtest` 函数内；L104 处 `dm` 已定义 | **新文本正确** |
| 2 | T-3.5 `build_trigger` 返回兼容性 | 对照 V1 `engine.py:114` | `build_trigger(cfg.rebalance, dm.trade_dates)` 与 V1 装配完全同构 | 确认 |
| 3 | 目标行缩进 | 读 4 个脚本目标行 | `full_backtest_2020_2026.py` L55 = 4 空格；`run_full_backtest_fixed.py` L54 = 8 空格（try 块）；`full_backtest_2020_2026_simple.py` L87/L92-96/L104 = 4 空格 | 偏差 → F-I2 |
| 4 | T-4 删除范围 | 读 L292-322 / L228-232 / L343-360 | `_run_engine_v1` = 23 行（L294-316）；`_FakeCombiner` = 3 行；g2/g3 各 8 行；空行处理未注明 | 偏差 → F-I4 |
| 5 | CODE_WIKI V1 残留全集 | 全文匹配 `engine.py` 与 `BacktestEngine\b`（排除 V2） | `engine.py` 字面 15 处（原清单）+ **`BacktestEngine` 类名 10 处**（L38/98/127/151/707/714/952/954/964/972），其中 L98/L151 不在改名清单、L952-972 完全遗漏；L23 目录锚点 `#12-回测引擎-enginepy` 未同步 | 偏差 → F-I1 |
| 6 | cli.py `--help` 可行性 | 读 `cli.py:16-25` | 顶层仅 `argparse/sys/pathlib`；`core.factory` 为函数内导入 → `--help` 轻量 exit 0 | 确认 |
| 7 | §7 排除表完整性 | 逐条推演 | 遗漏「`Remove-Item core/engine.py` 前必须确认无未提交改动」——误删不可恢复窗口 | 补 1 条 → F-I5 |
| 8 | R6「2 errors」推断 | 对照活跃 import 清单 | 两文件（test_rebalance_exits / test_compatibility）均模块级 `from core.engine import`；其余测试无 V1 import | 确认 |
| 9 | V8 清理契约 | 对照 `.gitignore` L53-58 | `demo_output/` L56 已忽略；`demo_data/` 未忽略须手工删 | 确认 |
| 10 | T-8 时序 | 读回 | 「done」条件已注明但与 T-8→T-9 顺序易误读 | 拆分 → F-I6 |

### 9.3 发现与处置（F-I 系列）

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-I1 | P3 | T-7.2 覆盖不全：CODE_WIKI 另有 10 处 `BacktestEngine` 类名（L98/L151 不在清单；§15.2 L952-972 四处完全遗漏）；L23 目录锚点未同步 | 已补 ①′（类名 3 处）+ ⑥（运行时序 4 处）+ ① 锚点同步 + ⑤ 覆盖注记 |
| F-I2 | P3 | T-3 迁移文本未标注目标行缩进（4 个脚本共 7 行在函数/try 块内） | 已加「缩进契约」注记并逐行列明 |
| F-I3 | P3 | §4 T-3.5 签名 `build_trigger(config, trade_dates)` 省略 rebalance 前缀 | 已修正为 `build_trigger(config.rebalance, dm.trade_dates)` |
| F-I4 | P3 | T-4 删除块未注明空行处理 | 已加「空行契约」注记（PEP8 两空行） |
| F-I5 | P3 | §7 排除表遗漏「删除前确认工作区干净」（T-1 误删不可恢复窗口） | 已补第 9 条 |
| F-I6 | P3 | T-8 的「done」时序与 T-8→T-9 顺序易误读 | 已拆分为「T-8 范围（T-9 前）/ T-9 后补写」两段 |

> **无 P1/P2 阻断**；6 项均为 P3 取证与可执行性精度修正，已全部回写正文。

### 9.4 复核结论

| 项 | 结论 |
|----|------|
| 门禁 6 项 | 全过 |
| 实施文本 | T-1~T-9 全部给出可执行的前后文本；关键新文本（T-3.5 的 V2 装配 + D7 修复）经作用域与签名双重验证 |
| 断言复核 | 10 项中 6 项逐值命中；4 项偏差（F-I1/F-I2/F-I4/F-I6）+ 2 项补强（F-I3/F-I5）已回写 |
| 任务面稳定性 | T-0~T-9 框架不变；T-7.2 动作面扩充（15 → 25 处精确编辑点） |
| 阻断项 | **0** |
| 门禁 | **Step 6 Review pass** → 进入 Step 7 验收清单 |

---

## 10. 结论

1. **9 个任务**（T-0~T-9）线性依赖，先记录 RED 再删除，最后统一验证。
2. **精确到行**：6 examples / 2 tests / 4 处注释 / 4 份活文档 + CHANGELOG + 2 份台账，全部给出前后文本；CODE_WIKI 编辑点经 Step 6 扩充至 25 处（含类名与锚点）。
3. **D7 已纳入实施**：手动装配脚本的 5 行先存坏导入与 `build_trigger` 形参一并修复。
4. **验证闭环**：V1-V8 全部可重放；RED 6 项 → GREEN 9 项；门禁基线 75→72 / 168→119 只降不升。
5. **回退单点**：整批单提交，`git revert` 一次完成。
