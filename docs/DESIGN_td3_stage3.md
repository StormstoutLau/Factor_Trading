# TD-3 Stage 3（移除 core/engine.py） · 设计文档

> **文档编号**: DESIGN_td3_stage3
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: 完稿（Step 4 Review **通过**，2026-11-09；12 项复核 9 命中 + 3 项偏差回写 + 1 项 P2 以 D7 闭环，见 §9）
> **上游**: [RESEARCH_td3_stage3.md](RESEARCH_td3_stage3.md)（Step 2 复核通过，0 项阻断）
> **下游**: [IMPL_td3_stage3.md](IMPL_td3_stage3.md) → [CHECKLIST_td3_stage3.md](CHECKLIST_td3_stage3.md)
> **证据时点**: 本仓读数 @ `696bd7b`；解释器 Python 3.12.10（F-R5 回放约束）
> **档位**: T1（改动路径含 `core/`、`tests/`、`examples/`，Layer-1）

---

## 1. 设计目标

基于 [RESEARCH §5](RESEARCH_td3_stage3.md) 的收敛结论，本设计回答四个问题：

1. **删除边界**：`core/engine.py` 删除后，哪些活跃引用必须迁移、哪些历史记录必须保留原样。
2. **examples 的等价迁移**：6 个脚本中 5 个是 config-driven、1 个是手动装配；两类必须用不同迁移路径，且不改变脚本意图。
3. **测试资产的取舍**：g2/g3 与两个 0 收集诊断脚本删除后，跨引擎等价性的证据载体是什么。
4. **可验证性**：如何证明「零生产逻辑变更 + 零 V1 残留 + 门禁基线只降不升」。

### 1.1 量化目标

| 目标 | 验收标准 | 复算方式 |
|------|----------|----------|
| V1 文件移除 | `core/engine.py` 不存在 | `Test-Path core/engine.py` → `False` |
| V1 import 零残留 | 全仓 `*.py` 无 `from core.engine import` / `from core import engine` | `Get-ChildItem -Recurse -Filter *.py \| Select-String` |
| examples 可执行性 | 6/6 `py_compile` 通过；`demo.py` 端到端烟测 exit 0 | `<Python312> -m py_compile`；`<Python312> examples/demo.py` |
| 本地零回归 | 全量 **`507 passed`**（82 warnings） | `<Python312> -m pytest -q` |
| 测试文件数 | `50 → 48` | `Get-ChildItem tests -Filter 'test_*.py'` |
| 测试项数 | `509 → 507`（−g2 −g3） | `--collect-only` |
| 活文档一致 | ARCHITECTURE / CODE_WIKI / DECISIONS / README 无未标注的 V1 路径 | Step 8 机械核对 |
| black 基线 | `75 → 72` files would be reformatted（预期 fail，无回归） | `black --check core tests` |
| mypy 基线 | `168 → 119` errors（预期 fail，无回归；`core/engine.py` 占 49） | `mypy --explicit-package-bases core` |
| 远端 CI | 3.10/3.11/3.12 均 `500 passed, 1 skipped`（推演） | 远端 run（Step 10 后） |

> 计数算式：本地 `509 − 2 = 507`；CI `507 − 7`（numba 模块级 skip 计 1 项）`= 500 passed + 1 skipped`。
> black / mypy 为**预期 fail 门禁**的基线下调（P-003 / P-007 后续按新基线执行），不是新增失败。

## 2. 设计依据

### 2.1 调研结论 → 设计决策映射

| 调研发现 | 设计决策 | 引用 |
|---------|---------|------|
| 10 个活跃 import（6 examples + 4 tests），`core/__init__.py` 仅注释，`cli.py` 零引用 | 删除 V1；examples 全迁移；tests 定点清理；注释示例改写 | RESEARCH P1/P2/P10 |
| `DeprecationWarning` 默认被忽略（`ignore::DeprecationWarning`） | 不保留 shim：静默 shim 会让旧路径继续存活 | RESEARCH S2 |
| PEP 594 分阶段模型（3.11 警告 → 3.12 最后含 → 3.13 移除） | 本批执行「移除」阶段，与 Stage 2 已完成的事实衔接 | RESEARCH S1 |
| PEP 387「软弃用 = 不发警告、不排期」 | 本仓 V1 是硬弃用（三层标记），不属于软弃用，移除合规 | RESEARCH S3 |
| 两个 visual_trace 脚本 0 收集、纯 V1 诊断、无文档引用 | 删除整文件（不迁移） | RESEARCH P7 |
| g2/g3 的被测对象是 V1 本身 | 删除；等价性证据迁移到 CHANGELOG / DIFF_REPORT 归档 | RESEARCH P6/P5 |
| 活文档命中 ARCH 3 / WIKI 15 / DEC 1 / README 4 行 | 按精确行号同步，历史记录不动 | RESEARCH P11 |
| `core/engine.py` 占 mypy 168 中的 49；3 个待删文件均在 black 75 内 | 记录基线下调，不伪装为「门禁通过」 | 本设计 §6 R9 |

### 2.2 假设携带（Step 4 门禁 d）

| ID | 假设 | 状态 | 验证方式 |
|----|------|------|----------|
| A1′ | 6 个 examples 使用的 V1 公开/私有成员在 V2 全部存在且语义等价 | **已验证（静态）** | §5.2 逐脚本成员表；`_composite_signal`/`dm` 等成员在 `engine_v2.py:147-159`（11 个属性初始化）中全部存在 |
| A2′ | `core/engine.py` 无仓库外消费者 | **已验证** | RESEARCH P1/P7/P10 机械扫描 |
| A3′ | 删除 g2/g3 后，跨引擎等价性仍可追溯 | **已验证（归档存在）** | `CHANGELOG.md:21`「最大差异 0.000000」+ `DIFF_REPORT_2026-10-23.md` |
| A4′ | `full_backtest_2020_2026_simple.py` 的手动装配在 V2 属性集上成立 | **修正（Step 4）**：静态属性成立；但脚本 L91-96 的 5 个顶层导入（`portfolio`/`rebalance`/`execution`/`tracker`/`pending`）的包与模块**均不存在**（实测 `dir=False py=False`）——脚本**今天就已 ImportError**（先存缺陷，与 V1 无关）。处置见 D7 | §5.2 #5；D7 |

### 2.3 职责边界

| 类别 | 内容 |
|------|------|
| **职责内** | 删除 `core/engine.py`；迁移 6 examples；删除 g2/g3 与 2 个 0 收集脚本；改写 `core/__init__.py` 与 3 处 docstring 示例；同步 ARCHITECTURE / CODE_WIKI / DECISIONS / README / CHANGELOG / PROGRESS / TD-3 注记 |
| **职责外（有独立载体，不吞并）** | 不重写 CODE_WIKI 为完整 V2 文档（ARCHITECTURE 为权威）；不迁移 visual_trace 的诊断能力（无 CI 覆盖、无引用）；不改历史记录（DEVLOG / DIFF_REPORT / dev-log / archive）；不执行 P-003（black 全量）与 P-007（mypy 全量） |
| **能力边界（想做但做不到）** | examples 的运行时行为无法纳入 CI：`testpaths = ["tests"]`（P14）且脚本依赖 `E:/Ashare_data` 或自行生成数据；只能做语法检查 + `demo.py` 单点烟测 |
| **明确不做** | 不新增 shim / 兼容层；不保留 `core/engine.py` 空壳；不改 `agents/multi_strategy_engine.py:64` 的历史沿革表述 |

## 2A. 方案对比矩阵（Type-1 / Type-2 判定）

**本轮判定：Type-2（可逆）**，不启用 7 维决策矩阵（`docs/SPEC_STANDARD.md` §11.8.1）。

| 判据 | 结论 | 依据 |
|------|------|------|
| 回退点存在 | ✅ 单提交 `git revert` 即完整恢复；`core/engine.py` 为 tracked 文件（RESEARCH P15） | 无数据迁移、无外部状态 |
| 变更真值源 / 契约 | ❌ 不变 | 不新增公开 API；`create_default_engine` 已存在（`core/factory.py:242-257`） |
| 方案数 ≥2 且选择导致返工 | 候选 A/B/C 与 A1/A2/B/C 已在 [RESEARCH §3](RESEARCH_td3_stage3.md) 记录；本设计只细化已采纳方案 | 被拒方案与代价见 §4 |

## 3. 删除边界与迁移架构

### 3.1 删除边界（精确）

| 类型 | 路径 | 动作 | 体量 |
|------|------|------|------|
| 删除 | `core/engine.py` | 整文件删除 | 724 行 / 29910 B |
| 删除 | `tests/test_visual_trace.py` | 整文件删除（0 收集、纯 V1 诊断、无文档引用） | 238 行 / 9520 B |
| 删除 | `tests/test_visual_trace_v2.py` | 整文件删除（同上） | 179 行 / 7280 B |
| 修改 | `examples/` 6 个脚本 | 迁移 import + 实例化（§5.2）；#5 另修 5 行先存坏导入（D7） | 6 文件，约 18 行 |
| 修改 | `tests/test_rebalance_exits.py` | 删 V1 helper / g2 / g3 / 3 个 import / `_FakeCombiner` | 约 −80 行；14 → 12 项 |
| 修改 | `tests/test_compatibility.py` | L48 替换为 `engine_v2` 导入（保留断言意图） | 1 行 |
| 修改 | `core/__init__.py` | L6/L9 注释示例改为 V2 | 2 行 |
| 修改（注释级） | `core/engine_plugins.py` L14/L383、`core/walk_forward_engine.py` L45 | `BacktestEngine` → `BacktestEngineV2` | 3 行 |
| 不改 | `agents/multi_strategy_engine.py:64` | 历史沿革表述（「基于原始的 BacktestEngine 改造」） | 0 |

### 3.2 迁移路径

```
删除前                                   删除后
core/engine.py (V1, 724 行)  ────────►   [不存在]
   ▲ 6 examples / 4 tests                 │
   │                                      ├─ 5 config-driven scripts ──► core.factory.create_default_engine(config)
   │                                      │                              └─► BacktestEngineV2 (setup/run 签名一致)
   │                                      ├─ 1 manual wiring script ────► BacktestEngineV2(config) + 属性直装配
   │                                      ├─ test_compatibility ────────► from core.engine_v2 import BacktestEngineV2
   │                                      ├─ test_rebalance_exits ──────► 删除 g2/g3 + _run_engine_v1
   │                                      └─ visual_trace ×2 ───────────► 删除（0 收集）
   │
   └─ 注释/docstring ─────────────────────► core/__init__.py + engine_plugins.py + walk_forward_engine.py

证据链：CHANGELOG.md:21（R-1 受控对比，最大差异 0.000000）+ DIFF_REPORT_2026-10-23.md
```

### 3.3 不变项（生产逻辑零变更声明）

| 不变项 | 证据 |
|--------|------|
| `core/engine_v2.py`、`core/factory.py`、`core/target_positions.py` | 0 行改动（`git diff --stat`） |
| `core/config.py`、`filter/`、`portfolio/`、`execution/`、`tracker/`、`pending/`、`rebalance/` | 0 行改动 |
| `cli.py` | 0 行改动（已于 Stage 2 迁移） |
| `pyproject.toml` | 0 行改动 |
| 算法与参数 | 无变更；`examples/demo.py` 因子预处理参数不变，但因 V2 执行 `FactorPipeline`，输出数值会变化（见 R1，属已归档的预期行为） |

## 4. 决策记录（D1-D6）

### D1 移除方式：直接删除（采纳 A）

| 项 | 内容 |
|----|------|
| 决策 | 删除 `core/engine.py`，不保留 shim、不冻结 |
| 依据 | Stage 3 的语义就是 Remove；S2 证明弃用标记默认不可见，shim 会让旧 import 静默延续；A2′ 证明无外部消费者 |
| 被拒 B | shim（re-export V2）——旧 import 永久存活，债务名存实亡；与 S1 的移除阶段矛盾 |
| 被拒 C | 冻结不删——TD-3 永不闭环；ARCHITECTURE 债务行长期挂账 |
| 回退 | `git revert` 单提交恢复 724 行文件 |

### D2 examples 迁移：按脚本意图分两类（采纳 A + 细化）

| 项 | 内容 |
|----|------|
| 决策 | 5 个 config-driven 脚本改用 `create_default_engine`；`full_backtest_2020_2026_simple.py` 保留手动装配，改用 `BacktestEngineV2` 并修正 `build_trigger` 参数 |
| 依据 | 手动装配脚本的意图是演示「组件可替换」；用 factory 会抹掉该意图。V2 在 `engine_v2.py:147-159` 初始化 **11** 个属性（L147-155 九个组件 + L158 `_composite_signal` + L159 `_returns_matrix`），与示例使用的成员一一对应 |
| 被拒 A2 | 全部改成 factory——简单但丢失手动装配示例 |
| 被拒 B | 删除手动装配脚本——丢失唯一的组件级示例 |
| 回退 | `git checkout <hash>~1 -- examples/` |

### D3 tests 处置：删 g2/g3 + 删 2 个死脚本；兼容性测试改为 V2 导入（采纳 A1 + 细化）

| 项 | 内容 |
|----|------|
| 决策 | `test_rebalance_exits.py` 删除 `_run_engine_v1` / g2 / g3 / V1-only imports / `_FakeCombiner`；`test_compatibility.py` 的 engine 行**替换**为 `from core.engine_v2 import BacktestEngineV2`；删除两个 visual_trace 文件 |
| 依据 | g2/g3 的被测对象消失；g1/g4/g5 已覆盖 V2 的清仓/杠杆/卖先于买。兼容性测试的意图是「导入路径有效」，应指向新引擎而非纯删除 |
| 被拒 A2 | visual_trace 迁移到 V2——无 CI 覆盖（P14），迁移成本高且回归不可见 |
| 被拒 B | g2/g3 改写为 V2-only——与 g1 重复，无增量断言 |
| 回退 | 单提交 revert 恢复 2 个测试文件与 g2/g3 |

### D4 注释与 docstring 同步：改写示例，不改历史沿革

| 项 | 内容 |
|----|------|
| 决策 | `core/__init__.py` L6/L9、`engine_plugins.py` L14/L383、`walk_forward_engine.py` L45 改为 `BacktestEngineV2`；`multi_strategy_engine.py:64` 保留原文 |
| 依据 | 前 3 处是**可复制的使用示例**，继续指向已删除类会误导；后者是历史沿革陈述，改写会伪造历史 |
| 回退 | 随主提交 revert |

### D5 活文档同步：4 份活文档 + CHANGELOG + 台账；历史记录不动

| 文件 | 精确动作 |
|------|----------|
| `docs/ARCHITECTURE.md` | 删除 L81「Engine V1」模块行；L198 表头改为 `Engine V1（已移除）`、状态单元格改为「❌ 已移除（P-001）」；删除 L304 债务行 |
| `docs/CODE_WIKI.md` | **分级处理 15 处（Step 4 修正，禁盲改）**：① 改名 `engine.py`→`engine_v2.py`：L23/38/99/152/705；② L127 尺寸行：`~20KB` 对 engine_v2.py 不实，改为 V2 实际体量与「依赖注入 + factory」描述；③ L173 耦合表：V2 经注入不直接构造各组件，改写；④ L925-946 调用图：V1 直接构造语义已失效，替换为 V2 数据流（factory → 注入 → 逐日循环）并注「V1 已于 P-001 移除」；⑤ §12 正文（L705-788）整体替换为 V2 摘要（保留编号 12，避免 13-15 重排与锚点失效） |
| `docs/DECISIONS.md` | L30 `core/engine.py` (弃用) → `core/engine.py`（已于 P-001 移除） |
| `README.md` | L7 徽章 `509`→`507`；L98 `509 passed`→`507 passed`；L262 同；L411 `509 tests, 50 files`→`507 tests, 48 files` |
| `CHANGELOG.md` | `[Unreleased] / Removed` 新增 1 条：移除 V1 + 迁移 examples + g2/g3 与 2 个死脚本删除 |
| `docs/PROGRESS.md` | P-001 状态与 §3.1 进度；门禁基线更新为 black 72 / mypy 119 |
| `docs/RESEARCH_tech_debt_cleanup.md` | TD-3 复核记录追加「Stage 3 已执行（P-001，2026-11-09）」注记，不改历史结论 |
| 历史记录 | `DEVLOG.md` / `DIFF_REPORT_2026-10-23.md` / `docs/dev-log/` / `docs/archive/` / `DESIGN_critical_rebalance_fix.md` **零改动** |

### D6 兼容性边界：不提供 shim，不保留空壳

| 项 | 内容 |
|----|------|
| 决策 | `import core.engine` 在删除后为 `ModuleNotFoundError`；不提供任何 redirect |
| 依据 | 无外部消费者（A2′）；提供 redirect 会让 S2 的「默认不可见」问题重演 |
| 可接受性 | 仓库内 10 处引用全部在本批迁移；`cli.py` 早已走 factory（Stage 2） |

### D7 先存导入缺陷修复（Step 4 派生决策）

| 项 | 内容 |
|----|------|
| 发现 | `full_backtest_2020_2026_simple.py` L92-96 的 `from portfolio/rebalance/execution/tracker/pending import ...` 顶层包与模块**均不存在**（实测 5 项 `dir=False py=False`；`filter/` 包存在且 L125 导出 `UniverseFilter`，故 L91 有效）。脚本**在本批之前就必然 ImportError**，属先存缺陷，与 V1 无关 |
| 决策 | 迁移时一并修复这 5 行导入为权威路径：`from core.portfolio import build_optimizer`（`core/portfolio.py:404`）、`from core.rebalance import build_trigger`、`from core.execution import ExecutionSimulator`、`from core.tracker import PositionTracker`、`from core.pending import PendingOrderQueue`（均为 `test_compatibility.test_new_import_paths` 已验证的有效路径）；L91 `from filter import UniverseFilter` 有效，保留 |
| 理由 | 该文件本批必改（D2 模板 B）；不修则迁移后脚本仍必坏，「examples 迁移完成」名不副实；修复与迁移同文件、同意图（示例可用性）；5 行均为路径替换，零逻辑变更 |
| 被拒 | 只记录不修复——迁移价值归零；删除脚本——丢失唯一手动装配示例（同 D2-B） |
| 登记 | 本决策为**派生需求**（实施前发现、非上游推导），在 CHECKLIST 单独验收；PROGRESS 台账同步 |
| 回退 | 随主提交 revert |

## 5. 接口契约

### 5.1 工厂接口（已存在，不新增）

```python
# core/factory.py:242-257（现状，零改动）
def create_default_engine(config: BacktestConfig) -> 'BacktestEngineV2':
    from core.engine_v2 import BacktestEngineV2
    factory = ComponentFactory(config)
    kwargs = factory.create_engine_kwargs()
    engine = BacktestEngineV2(config, **kwargs)
    return engine
```

| 契约 | 内容 |
|------|------|
| 调用约定 | `engine = create_default_engine(config)`；随后 `engine.setup()` / `engine.run()` |
| 返回类型 | `BacktestEngineV2`，`dm` / `_composite_signal` / `_returns_matrix` / `optimizer` / `trigger` / `tracker` / `executor` / `pending_queue` 均可访问 |
| 结果字典 | `portfolio_value` / `performance_metrics` / `charts` / `reports` / `additional_info` / `unclosed_positions`（`engine_v2.py:803-810`） |

### 5.2 examples 逐脚本迁移契约

**模板 A（5 个 config-driven 脚本）**：

```python
# 旧
from core.engine import BacktestEngine
engine = BacktestEngine(config)
# 新
from core.factory import create_default_engine
engine = create_default_engine(config)
```

| # | 脚本 | 旧位置 | 迁移动作 | 成员/结果键核对 |
|---|------|--------|----------|------------------|
| 1 | `examples/demo.py` | L223 import；L225 实例化 | 模板 A | `results['performance_metrics']` / `['additional_info']` 均存在；因子预处理（mad/zscore/neutralize）在 V2 下生效 → 数值变化（R1） |
| 2 | `examples/run_single_backtest.py` | L13；L41 | 模板 A | L50 `engine._composite_signal` 在 V2 存在（L158/269）；`factor` 全 `none` → 与 V1 等价 |
| 3 | `examples/run_backtest_minimal.py` | L20；L53、L72（两实例） | 模板 A ×2 | `engine.dm` 存在（V2 L147） |
| 4 | `examples/full_backtest_2020_2026.py` | L16；L55 | 模板 A | `result['portfolio_value']` 存在 |
| 5 | `examples/full_backtest_2020_2026_simple.py` | L14；L87-104 手动装配 | **模板 B（见下）** | 11 项属性直装配 + `build_trigger` 参数修正 + 5 行先存坏导入修复（D7） |
| 6 | `examples/run_full_backtest_fixed.py` | L19；L54 | 模板 A | L61 `_composite_signal` 存在 |

**模板 B（手动装配脚本，唯一特例）**：

```python
# 旧（L14 / L87 / L104）
from core.engine import BacktestEngine
engine = BacktestEngine(config)
...
engine.trigger = build_trigger(config.rebalance, engine.optimizer)   # 第二参语义错误

# 新
from core.engine_v2 import BacktestEngineV2
engine = BacktestEngineV2(config)
...
engine.trigger = build_trigger(config.rebalance, dm.trade_dates)      # 对齐 core/rebalance.py 签名
```

> 保留 `engine.dm = dm`、`engine.universe`、`engine.pipeline = None`、`engine.combiner`、`engine._composite_signal`、`engine._returns_matrix`、`engine.optimizer`、`engine.trigger`、`engine.executor`、`engine.tracker`、`engine.pending_queue` 共 **11 项**直装配（与 `engine_v2.py:147-159` 的 11 个属性一一对应）；V2 `run()` 只强依赖 `dm` 非空（`engine_v2.py:275-276`）。
> **附带修正 1**：原脚本把 `optimizer` 传给 `build_trigger` 的 `trade_dates` 形参（L104）；在 `fixed/monthly` 下未暴露，属潜在错误。本批按真实签名修正，不属行为变更。
> **附带修正 2（D7）**：L92-96 的 5 个顶层导入改为 `core.*` 权威路径（先存缺陷）。

### 5.3 tests 清理契约

| 文件 | 删除项 | 保留项 | 计数 |
|------|--------|--------|------|
| `tests/test_rebalance_exits.py` | `import warnings`(L13)、`from contextlib import ExitStack`(L15)、`from core.engine import BacktestEngine`(L31)、`_FakeCombiner`(L228，仅 L301 使用)、`_run_engine_v1()`(L294-316)、`test_g2_*`(L343)、`test_g3_*`(L352) | `patch`（`_run_engine_v2` L286 仍用）、`_FakeDataManager` / `_FakeUniverse` / `_FakePipeline` / `_Top2Optimizer` / `_AlwaysTrigger` / `_build_config` / `_run_engine_v2`、g1/g4/g5、U1-U9 | 14 → 12 |
| `tests/test_compatibility.py` | `from core.engine import BacktestEngine`(L48) | 其余 9 个导入 | 替换为 `from core.engine_v2 import BacktestEngineV2`；6 项不变 |
| `tests/test_visual_trace.py` | 整文件 | — | 文件 −1；0 项 |
| `tests/test_visual_trace_v2.py` | 整文件 | — | 文件 −1；0 项 |

> 合计：测试 `509 → 507`；文件 `50 → 48`；两文件收集 `20 → 18`。

### 5.4 文档改写契约（关键文本）

| 位置 | 目标文本 |
|------|----------|
| `docs/ARCHITECTURE.md` L198 | 表头 `Engine V1（已移除）`；状态行 `❌ 已移除（P-001）` |
| `docs/CODE_WIKI.md` §12 | 标题 `## 12. 回测引擎 (engine_v2.py)`；正文 ≤15 行：指向 `BacktestEngineV2` / `create_default_engine` / `CHANGELOG.md:21` 等价性证据，并注明「V1 `core/engine.py` 已于 P-001 移除」 |
| `docs/DECISIONS.md` L30 | `` `core/engine.py`（已于 P-001 移除） `` |
| `README.md` L7/L98/L262/L411 | `507` / `507 passed` / `507 passed` / `507 tests, 48 files` |
| `CHANGELOG.md` `[Unreleased] > Removed` | 1 条：TD-3 Stage 3 完成，V1 删除 + 6 examples 迁移 + g2/g3 与 2 个 0 收集诊断脚本删除；测试 509→507、文件 50→48 |

## 6. 风险与缓解

| 风险 | 触发条件 | 缓解策略 |
|------|----------|----------|
| R1 demo 输出数值变化 | demo 启用 mad/zscore/neutralize，V2 真实执行 `FactorPipeline` | 属 CHANGELOG 已记录的预期行为；demo 无 golden 断言；本批在 CHANGELOG 再注明 |
| R2 删除 g2/g3 丢失跨引擎等价回归 | 未来 V2 行为回退 | 等价证据由 `CHANGELOG.md:21`（0.000000）+ `DIFF_REPORT_2026-10-23.md` 承载；g1/g4/g5 继续覆盖 V2 行为 |
| R3 活文档漏改 | CODE_WIKI 15 处分散 | Step 8 用精确行号 + `Select-String` 机械核对；允许残留仅限「已移除」注记行 |
| R4 examples 无 CI 覆盖 | `testpaths=["tests"]`（P14） | 6/6 `py_compile` + `demo.py` 端到端烟测 + 静态 V1 import 扫描 |
| R5 回退不完整 | 只 revert 部分文件 | 整批单提交；回退点 = 一次 `git revert` |
| R6 存在未知外部消费者 | 假设错误 | A2′ 机械证实（P1/P7/P10）；删除后 `ModuleNotFoundError` 即暴露 |
| R7 V2 缺少示例使用的成员 | 静态核对遗漏 | §5.2 逐成员核对；`_composite_signal` / `dm` 等已确认存在于 `engine_v2.py:147-159` |
| R8 远端 CI 变红 | import 错误 | 零生产逻辑变更 + `unit-tests` 门禁 + 远端三版本复核 |
| R9 black/mypy 基线漂移 | 删除 3 个非 black 合规文件 + `engine.py` 49 个 mypy 错误 | 预期下调：black `75→72`、mypy `168→119`；Step 9 实测并回写 PROGRESS，P-003/P-007 按新基线执行 |
| R10 手动装配脚本运行时未覆盖 | 无数据、无 CI | 静态属性表（§5.2）+ `py_compile`；在 Step 9 记录「运行时未执行」而非宣称已验证 |
| R11 先存缺陷修复引入回归（D7） | 5 行导入路径替换出错 | 修复路径全部为 `test_new_import_paths` 已验证的有效导入；`py_compile` + 逐行 diff 复核；改动仅限 import 行 |

## 7. 回退点

| 层级 | 操作 | 恢复范围 |
|------|------|----------|
| 整批 | `git revert <P-001 commit>` | `core/engine.py`（724 行）、2 个 visual_trace、6 examples、tests、全部文档 |
| 仅 examples | `git checkout <commit>~1 -- examples/` | 6 个脚本 |
| 仅 tests | `git checkout <commit>~1 -- tests/` | g2/g3、`_run_engine_v1`、2 个 visual_trace |
| 运行产物 | 手工删除 `demo_data/`、`demo_output/`（`demo_output/` 已被 `.gitignore` L56 覆盖；`demo_data/` 未被忽略） | 工作区清洁 |

## 8. 验证计划（V1-V8，Step 9 执行）

| ID | 断言 | 命令 | 预期 |
|----|------|------|------|
| V1 | V1 文件不存在 | `Test-Path core/engine.py` | `False` |
| V2 | 全仓 V1 import 零命中 | `Get-ChildItem -Recurse -Filter *.py \| Select-String -Pattern 'from core.engine import','from core import engine' -SimpleMatch` | 0 hit |
| V3 | 6 examples + cli 语法有效 | `<Python312> -m py_compile examples/demo.py examples/run_single_backtest.py examples/run_backtest_minimal.py examples/full_backtest_2020_2026.py examples/full_backtest_2020_2026_simple.py examples/run_full_backtest_fixed.py cli.py`（**Step 4 修正**：PowerShell 不为原生命令展开 `*` 通配符，禁写 `examples/*.py`） | exit 0 |
| V4 | 全量测试 | `<Python312> -m pytest -q` | `507 passed` |
| V5 | 测试文件数 | `Get-ChildItem tests -Filter 'test_*.py'` | `48` |
| V6 | 两个测试文件收集数 | `<Python312> -m pytest tests/test_rebalance_exits.py tests/test_compatibility.py --collect-only -q` | `18 tests collected` |
| V7 | 门禁基线 | `black --check core tests`；`mypy --explicit-package-bases core` | black `72` fail / mypy `119` errors fail（均预期） |
| V8 | 运行时烟测 | `<Python312> examples/demo.py`；`<Python312> cli.py --help` | exit 0；随后清理 `demo_data/`、`demo_output/` |

## 9. Step 4 Review（独立复核 pass，2026-11-09）

> 本节由 Step 4 独立执行并单独写入（RULE-1）；不复用 Step 3 的中间输出。**审查者**：单 Agent 自查（RULE-4）。**方式**：重新运行 E1/E3 命令核对设计断言，不依赖正文自报。

### 9.1 门禁核对（SPEC_PROCESS Step 4 Review 清单）

| 门禁项 | 结论 | 证据 |
|--------|------|------|
| 设计基于已验证的调研结论 | ✅ | §2.1 映射表逐条引用 RESEARCH P/S 编号；RESEARCH §6.1 复核通过（0 阻断） |
| 无未经验证的假设 | ✅（修正后） | A1′/A2′/A3′ 已验证；A4′ 原「静态成立」失准 → F-D6 修正并新增 D7 |
| 无论证驱动的归因扭曲 | ✅ | 逐案例核对：CHANGELOG:21 的 R-1 对比语境（关闭因子处理后等价）未被裁剪为「全条件等价」；§3.3 与 R1 明确区分 |
| 替代方案 ≥2 且被否决 | ✅ | D1-B/C、D2-A2/B、D3-A2/B、D7-被拒 2 项 |
| 职责边界清晰（职责外 + 能力边界） | ✅ | §2.3 四类边界显式声明（含「明确不做」） |

### 9.2 E-Review 复核表（独立重跑）

| # | 复核项 | 命令 | Step 4 读数 | 判定 |
|---|--------|------|-------------|------|
| 1 | V2 属性区计数 | 读 `engine_v2.py:145-161` | L147-155（9 组件）+ L158 `_composite_signal` + L159 `_returns_matrix` = **11 个初始化** | 偏差 → F-D1 |
| 2 | warnings/ExitStack/_FakeCombiner 使用面 | `Select-String test_rebalance_exits.py` | warnings 仅 L13+L310-311、ExitStack 仅 L15+L297、`_FakeCombiner` 仅 L228 定义 + L301 使用——均封闭于 `_run_engine_v1` | 设计 §5.3 删除安全，确认 |
| 3 | `patch` 保留正确性 | 同上 | L286（`_run_engine_v2`）仍用 | 确认 |
| 4 | `_run_engine_v1` 范围 | 读 L292-322 | **L294-316**（L319 为 `_quantity`） | 偏差 → F-D5 |
| 5 | 两测试文件收集数 | `<Python312> -m pytest ... --collect-only -q` | `14 tests` + `6 tests` = **20**；删 g2/g3 后 12+6=**18** | 确认 |
| 6 | 手动脚本顶层导入存在性 | `Test-Path` 6 项 | `filter/` 存在且 `filter/__init__.py:125` 导出 `UniverseFilter`（L91 有效）；`portfolio/rebalance/execution/tracker/pending` 顶层**包与模块均不存在** → 脚本今天就 ImportError | **先存缺陷 → F-D4/D7** |
| 7 | `build_optimizer` 权威路径 | `Select-String core/portfolio.py 'def build_optimizer'` | `core/portfolio.py:404`；V1 `engine.py:30` 亦从 `core.portfolio` 导入 | 确认 D7 路径 |
| 8 | README L98 语境 | 读 L92-99 | `# 5. Run all tests` → `# Output: 509 passed ✓`（Quick Start 代码块） | 改 507 合理，确认 |
| 9 | visual_trace 引用面 | 全仓 `*.py,*.md` 检索 | 仅本批 RESEARCH/DESIGN 提及；活文档与历史记录零引用 | 确认删除无副作用 |
| 10 | black 基线算式 | `black --check core/engine.py tests/test_visual_trace*.py` | 「3 files would be reformatted」→ 75−3=**72** | 确认 |
| 11 | mypy 基线算式 | `mypy --explicit-package-bases core` 计数 | total **168**，`core\engine.py` 占 **49** → 168−49=**119** | 确认 |
| 12 | V3 命令可重放性 | PowerShell 语义分析 | `py_compile examples/*.py` 通配符不展开 → 字面量传给 python 必报 no such file | 偏差 → F-D2 |

### 9.3 发现与处置（F-D 系列）

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-D1 | P3 | D2/§5.2#5 写「10 个属性（L147-159）」，实测该范围含 **11** 个属性初始化；手动装配涉及 **11 项**赋值（含 trigger） | 已修正（A1′/D2/§5.2#5/模板 B 说明） |
| F-D2 | P3 | §8 V3 命令 `py_compile examples/*.py` 在 PowerShell 下通配符不展开，按字面传参必失败 | 已修正为逐文件列举并加禁写注记 |
| F-D3 | P3 | D5 对 CODE_WIKI「15 处盲改 `engine.py`→`engine_v2.py`」会引入新失真：L127 `~20KB` 不实、L925-946 调用图为 V1 直接构造语义（V2 是依赖注入） | 已修正为分级处理（改名 5 处 / L127 体量 / L173 耦合 / L925-946 调用图重写 / §12 整体替换） |
| F-D4 | **P2** | `full_backtest_2020_2026_simple.py` L92-96 的 5 个顶层导入包/模块均不存在——脚本**今天就 ImportError**（先存缺陷）。原设计模板 B 未识别，若照原设计迁移，脚本删除 V1 后仍必坏，「迁移完成」名不副实 | 已新增 **D7**（派生决策）：迁移时一并修复 5 行导入为 `core.*` 权威路径；CHECKLIST 单独验收；R11 登记回归风险 |
| F-D5 | P3 | §5.3 `_run_engine_v1` 范围 L294-319 失准，实测 **L294-316** | 已修正 |
| F-D6 | P3 | A4′「静态成立，运行时未覆盖」表述失准——脚本导入层先存损坏 | 已修正（状态改为「修正（Step 4）」并指向 D7） |

> **无 P1 阻断**；1 项 P2（F-D4）已通过新增 D7 闭环。F-D1/F-D2/F-D3/F-D5/F-D6 属取证与可重放性修正，已回写正文。

### 9.4 复核结论

| 项 | 结论 |
|----|------|
| 门禁 5 项 | 全过（A4′ 经 F-D6/D7 修正后达成） |
| 断言复核 | 12 项中 9 项逐值命中；3 项偏差（F-D1/F-D5/F-D2）已回写；1 项先存缺陷升级为派生决策（D7） |
| 方案稳定性 | D1/D2/D3/D5/D6 主决策不受影响；D2 的 #5 脚本迁移动作扩充（+5 行导入修复） |
| 阻断项 | **0** |
| 门禁 | **Step 4 Review pass** → 进入 Step 5 实施规划 |

## 10. 设计结论

1. **删除边界确定**：1 个生产文件（724 行）+ 2 个 0 收集诊断脚本；6 examples 迁移、2 tests 定点清理、4 处注释/docstring 同步。
2. **迁移方式分两类**：5 个 config-driven 用 `create_default_engine`；1 个手动装配用 `BacktestEngineV2` 直装配，并修正 `build_trigger` 形参错误 + 5 行先存坏导入（D7 派生决策）。
3. **等价性证据不消失**：由 `CHANGELOG.md:21` 与 `DIFF_REPORT_2026-10-23.md` 承载；V2 行为继续由 g1/g4/g5 覆盖。
4. **门禁基线只降不升**：black `75→72`、mypy `168→119`，均属预期 fail 的下调，非新增失败。
5. **可回退**：单提交 `git revert` 完整恢复；无数据迁移、无外部状态。
6. **下一步**：Step 4 Review **已通过**（§9，1 项 P2 以 D7 闭环）；进入 Step 5 实施规划。
