# TD-3 Stage 3（移除 core/engine.py） · 调研文档

> **文档编号**: RESEARCH_td3_stage3
> **阶段**: Phase 1 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: Step 1 完稿；Step 2 Review **通过**（2026-11-09；0 项阻断，5 项 P3 发现已处置：4 项回写正文 + 1 项回放约束，见 §6.1）
> **上游**: `docs/PROGRESS.md` §1.4 P-001 / §2 U-003；[RESEARCH_tech_debt_cleanup.md](RESEARCH_tech_debt_cleanup.md) §TD-3
> **下游**: [DESIGN_td3_stage3.md](DESIGN_td3_stage3.md) → [IMPL_td3_stage3.md](IMPL_td3_stage3.md) → [CHECKLIST_td3_stage3.md](CHECKLIST_td3_stage3.md)
> **档位**: T1（改动路径含 `core/`、`tests/`、`examples/`，Layer-1）
> **证据时点**: 本仓读数 @ `696bd7b`；外部来源读取日 2026-11-09
> **规范版本**: `F:\Spec_Workflow\SPEC_PROCESS.md` **v1.7.2**（新增 §契约取证字段形态 F1-F5，本批按 F1/F2/F3/F4 出具；F5 留 Step 9）

---

## 1. 问题定义

P-001 的目标是执行 TD-3 的 **Stage 3（Remove）**：删除已弃用的 `core/engine.py`，并把唯一剩余的 10 处活跃引用迁移到 V2 引擎路径。TD-3 的 Stage 1（Deprecate）与 Stage 2（cli.py 替换）均已完成。

### 1.1 U-003 修正：引用清单实测（本轮核心输入）

| 断言行 | 上游表述（[RESEARCH_tech_debt_cleanup §TD-3](RESEARCH_tech_debt_cleanup.md)） | 实测 @ `696bd7b` | 判定 |
|--------|-------------------------------------------------------------------|------------------|------|
| 引用文件数 | 「10 个文件引用」 | **10 个活跃 import 文件 + 1 处注释** | 数值巧合，构成不同 |
| `cli.py` | 「关键一处为 CLI 入口点 `cli.py:36`」——**已过期** | `cli.py:36` 为 `from core.factory import create_default_engine`；**零 `core.engine` 引用** | **Stage 2 已完成，上游表述失效** |
| `core/__init__.py` | 「re-export」 | 仅 `L6`/`L9` **注释**示例；文件声明「`__init__.py` 改为空，避免导入时触发重依赖链」（L3） | **非 re-export，无活跃依赖** |
| `examples/` | 「5 个脚本」 | **6 个**：`demo.py:223`、`run_single_backtest.py:13`、`run_backtest_minimal.py:20`、`full_backtest_2020_2026.py:16`、`full_backtest_2020_2026_simple.py:14`、`run_full_backtest_fixed.py:19` | **修正 +1** |
| `tests/` | 「3 个测试」 | **4 个文件**：`test_compatibility.py:48`、`test_rebalance_exits.py:31`、`test_visual_trace.py:146`、`test_visual_trace_v2.py:66` | **修正 +1** |

> **U-003 关闭判据达成**：清单已按实测更新为「6 examples + 4 tests = 10 个活跃 import；`core/__init__.py` 仅注释；`cli.py` 已迁移」。

**实测命令（E1，可重放）**：对 `**/*.py` 逐文件匹配 `from core\.engine import` / `from core import engine`，区分注释与活跃行 → `total 11, active 10`。

### 1.2 依赖面分类（决定迁移方式）

| 类别 | 文件 | 位置 | 依赖性质 | 迁移难度 |
|------|------|------|----------|----------|
| **E. examples（6）** | `examples/demo.py` | L223（函数内） | 实例化 V1 `BacktestEngine` | 低：`create_default_engine` 接口等价（§1.4） |
| | `examples/run_single_backtest.py` | L13（模块级） | 同上 | 低 |
| | `examples/run_backtest_minimal.py` | L20（模块级），L53/L72 两次实例化 | 同上 | 低 |
| | `examples/full_backtest_2020_2026.py` | L16（模块级），L55 | 同上 | 低 |
| | `examples/full_backtest_2020_2026_simple.py` | L14（模块级），L87 | 同上 | 低 |
| | `examples/run_full_backtest_fixed.py` | L19（模块级），L54 | 同上 | 低 |
| **T. tests（4）** | `tests/test_compatibility.py` | L48（`test_new_import_paths` 内） | 断言「新导入路径有效」，逐项导入 10 个模块 | 低：从列表移除 engine 一行 |
| | `tests/test_rebalance_exits.py` | L31（模块级），L312 `_run_engine_v1()` | **V1/V2 黄金对比**：`test_g2_engine_v1_liquidates_exited_positions`(L343) 与 `test_g3_engines_share_identical_targets`(L352) 显式调用 V1 | **高：删除对象后测试失去被测目标** |
| | `tests/test_visual_trace.py` | L146（`run_engine_and_trace()` 内） | 诊断脚本；**实测 0 项被 pytest 收集**（函数无 `test_` 前缀） | 中：迁移或删除 |
| | `tests/test_visual_trace_v2.py` | L66（`run_detailed_trace()` 内） | 同上，**0 收集** | 中：迁移或删除 |
| **C. 注释（1）** | `core/__init__.py` | L6 / L9 | 文档示例注释 | 低：改写示例 |

### 1.3 测试计数影响（须在 DESIGN 显式裁决）

| 项 | 当前 | 删除 V1 后 | 依据 |
|----|------|-----------|------|
| 全量测试数 | `509 passed` | **507**（若删除 g2/g3 两 golden 测试） | `pytest --collect-only -q`：`test_rebalance_exits.py` + `test_compatibility.py` 共收集 20 项，其中 g2/g3 两项依赖 `_run_engine_v1` |
| `tests/test_*.py` 文件数 | `50` | **48**（若删除两个 visual_trace 死脚本） | 两文件实测 `collected 0 items`（`pytest --collect-only` exit 5） |
| 依赖 V1 的活跃测试 | 3 项（g2、g3、`test_new_import_paths`） | 1 项（仅 `test_new_import_paths`，去掉 engine 行后仍成立） | 同上 |

> **对 P-008/P-009 已落定基线的影响**：`README.md` 的 `509 passed` / `50 files` 与 `pyproject.toml` 无耦合，但 README 计数将失准 → 属本批必须同步的文档面（§1.5）。

### 1.4 Stage 2 已完成的事实依据（迁移目标接口）

`core/factory.py:242-257` 已提供：

```python
def create_default_engine(config: BacktestConfig) -> 'BacktestEngineV2':
    from core.engine_v2 import BacktestEngineV2
    factory = ComponentFactory(config)
    kwargs = factory.create_engine_kwargs()
    return BacktestEngineV2(config, **kwargs)
```

| 事实 | 读数 | 证据 |
|------|------|------|
| `cli.py` 已切换至 factory | `cli.py:36` import、`cli.py:77` 调用 | E3 @ `696bd7b` |
| 切换已做受控对比 | 「R-1 受控对比确认关闭因子处理后两引擎逐日净值完全一致（最大差异 0.000000）」 | `CHANGELOG.md:21`（E3） |
| V1 弃用为三层标记 | module docstring `⚠️ DEPRECATED`（L3）+ 类 docstring `.. deprecated::`（L46）+ 运行时 `warnings.warn(DeprecationWarning)`（L60-61） | E3 |
| V1 体量 | **724 行 / 29910 B** | E1 `Get-Content` / `Get-Item` |

### 1.5 文档面（活文档 vs 历史记录）

| 分类 | 文件 | 命中数 | 处置倾向 |
|------|------|--------|----------|
| **活文档（须同步）** | `docs/ARCHITECTURE.md` | **3**（V1 相关精确命中：L81 模块表「Engine V1 ⚠️ 已弃用」/ L198 三引擎对比表「特性 \| Engine V1 \|」/ L304 债务表「`core/engine.py` 未删除」） | 改：删除/改写这三行 |
| | `docs/CODE_WIKI.md` | **15**（`engine.py` 字面命中：L23/38/99/127/152/173/705/925/928/931/934/937/940/943/946） | 改：删除 engine.py 章节或标注已移除 |
| | `docs/DECISIONS.md` | **1**（L30「`core/engine.py` (弃用)」；L76 为 `walk_forward.py`，不属本项） | 改：改为「已移除（P-001）」 |
| | `README.md` | **4 行含 509**：L7 徽章 `Tests-509%20passed` / L98 `509 passed ✓` / L262 `509 passed`（3 处 `509 passed`）+ L411 `509 tests, 50 files` | 改：`507 passed` / `48 files`（若按 §1.3 方案） |
| **历史记录（不改）** | `docs/DEVLOG.md`、`docs/DIFF_REPORT_2026-10-23.md`、`docs/dev-log/`、`docs/archive/`、`CHANGELOG.md` | 约 20 处 | **不改**：历史记录按发生期事实保留，回改会伪造历史 |
| **本批台账** | `docs/PROGRESS.md`（4）、`docs/RESEARCH_tech_debt_cleanup.md`（15，含 TD-3 过期表述） | — | 改：PROGRESS 状态；TD-3 追加「Stage 3 已执行」注记（不改历史结论） |

### 1.6 影响范围汇总

| 范围 | 内容 |
|------|------|
| 删除 | `core/engine.py`（724 行）；2 个 golden 测试方法（g2/g3）；2 个 0 收集诊断脚本（待 Step 3 裁决） |
| 迁移 | 6 examples → `create_default_engine`；`test_compatibility.py` 去掉 engine 行；`core/__init__.py` 注释示例改写 |
| 文档 | 4 份活文档同步 + 台账；历史记录不动 |
| 生产逻辑 | **零算法变更**：V1 与 V2 的净值等价已有 R-1 受控对比（`CHANGELOG.md:21`） |

---

## 2. 来源调研（Step 1，F1/F2 字段齐备）

### 2.1 外部来源

| ID | 来源 | 等级 | F1 日期 | F2 版本 | 关键事实 | 可解析 ID |
|----|------|------|---------|---------|----------|-----------|
| S1 | PEP 594《Removing dead batteries from the standard library》 | **T1** | 发布 2019-05-20；**读取 2026-11-09** | Status **Final**；Python-Version **3.11** | 分阶段移除模型：`3.11` 起弃用模块开始发 `DeprecationWarning` → `3.12` 为「最后一个仍含弃用模块的版本」→ `3.13`「All modules deprecated by this PEP are removed」 | https://peps.python.org/pep-0594/ |
| S2 | Python 文档《`warnings` — Warning control》 | **T1** | 读取 2026-11-09 | `docs.python.org/3`（当前渲染 3.14）；记录 3.2 / 3.7 变更 | `DeprecationWarning`「Base category for warnings about deprecated features … (**ignored by default, unless triggered by code in `__main__`**)」；默认过滤器 `default::DeprecationWarning:__main__` + `ignore::DeprecationWarning` | https://docs.python.org/3/library/warnings.html |
| S3 | PEP 387《Backwards Compatibility Policy》 | **T1** | 发布 2009-06-18；页面 last modified 2026-01-15；**读取 2026-11-09** | Status **Active**；Type Process | ①「**Soft Deprecation**」= 只在文档标注、**不发警告、不排期移除**；②「Making Incompatible Changes」要求：讨论 → 发警告 →「Wait for the warning to appear in at least two minor Python versions … preferred … wait 5 years before removal」 | https://peps.python.org/pep-0387/ |

**F3 降级链**：**无降级**——S1/S2/S3 均由 `WebFetch` 直读原文命中（非搜索摘要），未发生通道失败。

**来源间关系与适用边界（外部 vs 本仓差异）**：

| 关系 | 说明 |
|------|------|
| S1 ↔ S3 一致 | 二者都要求「先弃用发警告、后移除」，S1 给出**日历化**的阶段（3.11→3.13），S3 给出**政策**要求（≥2 个 minor 版本，倾向 5 年） |
| S3 的「Soft Deprecation」不适用 | 本仓 V1 是**硬弃用**（`warnings.warn(DeprecationWarning)` 三层标记），按 S3 语义属于「已声明移除意图」 |
| S1/S3 的时间表**不外推** | 二者约束 **Python 标准库公共 API**；本仓是**应用内部模块**，无外部消费者（§2.2 P7/P8 证实 `core/` 外无第三方依赖）。故**只采纳「分阶段 + 先弃用后移除」的结构**，不采纳 5 年/2 个 minor 的日历约束；差异须在 DESIGN 显式声明 |
| S2 解释**为何弃用标记失效** | `DeprecationWarning` 默认被忽略（`ignore::DeprecationWarning`），仅 `__main__` 触发时可见——这正是 V1 在 `cli.py` 中长期被当作默认引擎而未被发现、且仓库内 10 处 import 未收敛的机制原因（弃用标记不等于阻断） |

### 2.2 本仓事实（E1/E3，@ `696bd7b`）

| ID | 断言 | 证据 |
|----|------|------|
| P1 | 活跃 import = **10 文件**（6 examples + 4 tests）；`core/__init__.py` 仅 1 处**注释** | E1 全仓扫描：`total 11, active 10` |
| P2 | `cli.py` **零** `core.engine` 引用；L36 `from core.factory import create_default_engine`、L77 调用 | E3 |
| P3 | `core/engine.py` = **724 行 / 29910 B**，三层弃用标记（L3 / L46 / L60-61） | E1 + E3 |
| P4 | `factory.create_default_engine` 返回 `BacktestEngineV2`，`ComponentFactory` 注入 kwargs | E3 `core/factory.py:242-257` |
| P5 | V1/V2 净值等价有受控对比记录（关闭因子处理后最大差异 `0.000000`） | E3 `CHANGELOG.md:21` |
| P6 | `test_rebalance_exits.py` 中 **2 项**收集测试依赖 V1：`test_g2_engine_v1_liquidates_exited_positions`(L343)、`test_g3_engines_share_identical_targets`(L352)，经 `_run_engine_v1()`(L294-316) 并对 `core.engine.*` 打 **7 个** patch（L298-L305：DataManager/UniverseFilter/FactorPipeline/FactorCombiner/build_optimizer/build_trigger/generate_report） | E1 `--collect-only` + E3 |
| P7 | `tests/test_visual_trace.py` 与 `tests/test_visual_trace_v2.py` **各 0 项**被收集（`pytest --collect-only` → `collected 0 items`，exit 5）；内部仅 `run_engine_and_trace()` / `run_detailed_trace()` 等非 `test_` 函数使用 V1 | E1 |
| P8 | 当前全量测试 `509 passed`（P-009 远端 `502 passed, 1 skipped` 为 CI 无 numba 口径）；`tests/test_*.py` = 50 | E1（RESEARCH_ci_test_env / PROGRESS 基线） |
| P9 | `core/engine_plugins.py:14,383`、`core/walk_forward_engine.py:45`、`agents/multi_strategy_engine.py:64` 仅在 **docstring** 提及 `BacktestEngine`，无 import | E3 + E1（活跃 import 扫描未命中） |
| P10 | `core/__init__.py` 已声明「改为空，避免导入时触发重依赖链」，无 re-export | E3 `core/__init__.py:3-11` |
| P11 | 活文档精确命中：ARCHITECTURE **3**（V1 相关）/ CODE_WIKI **15**（`engine.py` 字面）/ DECISIONS **1** / README **4 行含 509**（3 处 `509 passed` + 1 处 `509 tests, 50 files`） | E1 `Select-String -SimpleMatch` 计数（Step 2 复核修正） |
| P12 | `docs/RESEARCH_tech_debt_cleanup.md:333,344` 的「TD-3 引用 10 个文件、cli.py:36 位置属实」为**当时**的复核记录，其中 cli.py 断言已被 Stage 2 改变 | E3 |
| P13 | 仓库无 `deprecated` 相关的 `filterwarnings = error` 配置（`pyproject.toml [tool.pytest.ini_options]` 仅 testpaths/python_files/python_classes/python_functions/addopts） | E3 `pyproject.toml:99-104` |
| P14 | `examples/` 不被 pytest 收集（`testpaths = ["tests"]`），删除 V1 后 examples 迁移的失败不会被 CI 捕获 | E3 `pyproject.toml:100` |
| P15 | `git ls-files core/engine.py` 命中（可 `git revert` 恢复）；`git log` 该文件最近改动可见 | E1 |
| P16 | P-009 后远端 CI 三版本 `502 passed, 1 skipped` 全绿（run `42030484187` @ `33872c3`）为本批回归基线 | E1 |

---

## 3. 候选方案与初步倾向

> Step 1 只给出候选与代价；**最终裁决在 Step 3（DESIGN）**，含被拒方案与代价表。

### 3.1 移除方式

| 候选 | 描述 | 优点 | 代价 | 初步倾向 |
|------|------|------|------|----------|
| **A. 直接删除 `core/engine.py`** | Stage 3 定义动作；一次性移除 724 行 | 彻底；零维护面；与 S1 的 3.13 阶段同构 | 不可 `import core.engine`（无外部消费者，P1/P7 证实） | **倾向采纳** |
| B. 保留 shim（re-export V2 + 警告） | `engine.py` 改为 `from core.engine_v2 import BacktestEngineV2 as BacktestEngine` | 兼容旧 import | 债务名存实亡却仍占位；与「Stage 3 = Remove」矛盾；`DeprecationWarning` 默认不可见（S2），shim 会静默延续 | 拒绝（倾向） |
| C. 冻结不删（维持现状） | 仅更新文档 | 零风险 | TD-3 永不闭环；ARCHITECTURE 债务行长期挂着；与 P-001 目标冲突 | 拒绝（倾向） |

### 3.2 examples 处置

| 候选 | 描述 | 代价 | 初步倾向 |
|------|------|------|----------|
| **A. 迁移至 `create_default_engine`** | 6 个脚本改 import + 实例化 | 逐个核对 API 差异（V2 的 `setup/run` 签名一致，`engine.dm` 同有） | **倾向采纳** |
| B. 删除 examples | 直接移除 | 丢失端到端演示入口（`demo.py` 是 README 引用的示例） | 拒绝（倾向） |
| C. 保留 examples 不动 | 会导致 `ImportError` | 脚本必坏 | 拒绝（倾向） |

### 3.3 tests 处置

| 候选 | 描述 | 代价 | 初步倾向 |
|------|------|------|----------|
| **A1. 删除 g2/g3 + 删除两个 visual_trace 死脚本** | g2/g3 的被测对象消失；两个脚本 0 收集且是 V1 诊断器 | 测试 509→**507**、文件 50→48（见下） | **倾向**（最彻底） |
| A2. 删除 g2/g3 + visual_trace 迁移到 V2 | 保留脚本可人工运行 | 迁移 2 个 724 行诊断脚本的内部调用；无 CI 覆盖（P14），回归风险不可见 | 备选 |
| B. g2/g3 改写为 V2-only | 把「V1 行为」改成「V2 行为」 | g2/g3 的语义是**跨引擎等价**，改后与 g1 重复，无增量断言 | 拒绝（倾向） |
| C. `test_new_import_paths` 保留 engine 行 | — | 删除后该行必失败 | 拒绝（必然） |

**测试计数算式（A1）**：

| 项 | 变化 | 结果 |
|----|------|------|
| 删除 `test_g2_engine_v1_liquidates_exited_positions` | −1 | |
| 删除 `test_g3_engines_share_identical_targets` | −1 | |
| 删除 `test_visual_trace.py` / `test_visual_trace_v2.py`（各 0 收集） | −0 测试 / −2 文件 | |
| **合计** | | **测试 509 → 507；文件 50 → 48** |

> A2 的算式：测试 509 → 507，文件仍 50（迁移而非删除）。

### 3.4 文档同步范围

| 候选 | 描述 | 代价 | 初步倾向 |
|------|------|------|----------|
| **A. 只改「活文档」+ 台账** | ARCHITECTURE / CODE_WIKI / DECISIONS / README 计数 / PROGRESS / TD-3 注记 | CODE_WIKI 15 处需逐条改，工作量集中 | **倾向采纳** |
| B. 全仓改写（含 DEVLOG / DIFF_REPORT / archive） | 一致但**伪造历史** | 历史记录失去「当时事实」价值 | 拒绝（倾向） |

---

## 4. 风险识别

| 风险 | 触发条件 | 缓解策略 |
|------|----------|----------|
| R1 examples 迁移后行为漂移 | V2 默认执行 `FactorPipeline`（V1 忽略因子参数） | P5 已有 R-1 受控对比（关闭因子处理后净值一致）；迁移后用 1 个脚本做烟测（非 CI 覆盖，P14） |
| R2 删除 g2/g3 丢失跨引擎等价回归 | 未来 V2 行为回退 | 等价性已被 R-1 归档（`CHANGELOG.md:21` + `DIFF_REPORT_2026-10-23.md`）；本批在 DESIGN 记录「等价证明的替代载体」 |
| R3 测试计数与 README 失准 | 未同步 `509 passed` / `50 files` | 列入 CHECKLIST 验收项；P-008 先例（3 处计数同步） |
| R4 活文档漏改 | CODE_WIKI 15 处分散 | Step 8 一致性 Review 用 `Select-String` 机械核对「活文档 0 残留」 |
| R5 `git revert` 后 examples 半迁移 | 只 revert 部分文件 | 整批单提交；回退点 = 单次 `git revert` |
| R6 无外部消费者被误删 | 假设错误 | P1/P7 已机械证实 `core/` 外无第三方调用；`core/__init__.py` 无 re-export（P10） |
| R7 V2 缺少 V1 的某个公开方法 | examples 用到 V1 特有 API | Step 5 逐个 examples 核对调用面（`setup` / `run` / `dm` / `_force_liquidation` 等） |
| R8 远端 CI 出现新红 | 迁移引入 import 错误 | 本批零生产逻辑变更；`unit-tests` 门禁 + 远端复核（U-007 先例） |

---

## 5. 调研结论

1. **U-003 已关闭**：引用面实测为「6 examples + 4 tests（10 个活跃 import）+ 1 处注释」；`cli.py` 已于 Stage 2 迁移；`core/__init__.py` 无 re-export。
2. **Stage 3 的必要性由 S2 直接支撑**：`DeprecationWarning` 默认被忽略，仅靠弃用标记无法阻止新代码继续使用 V1；S1 的「弃用→移除」阶段模型为 Stage 3 提供结构依据。
3. **初步裁决倾向（待 Step 3 定稿）**：
   - 移除方式 **A（直接删除）**；
   - examples **A（迁移至 `create_default_engine`）**；
   - tests **A1（删 g2/g3 + 删 2 个 0 收集死脚本）** → 测试 `509→507`、文件 `50→48`；
   - 文档 **A（只改活文档 + 台账）**。
4. **关键假设**：
   - A1′：V1 与 V2 在 examples 使用面上行为等价（P5 R-1 对比 + Step 5 逐脚本核对）；
   - A2′：`core/engine.py` 无仓库外消费者（P1/P7/P10 机械证实）；
   - A3′：删除 g2/g3 后，跨引擎等价性仍有归档证据可追溯（R2）。
5. **未决项**：无新增 U 项；U-003 在本轮关闭。
6. **下一步**：Step 2 Review（外部引用 ≥3 条 → 必须建 F4 验证表；核 P1-P16 可重放性），通过后进入 Step 3 设计。

---

## 6. 来源验证表（Step 2 Review，F4）

> 外部引用 **3 条（S1-S3）**，按 SPEC_PROCESS v1.7.2 §契约取证字段形态 F4「≥3 条必须建表」出具。
> **复核方式**：Step 2 独立二次 `WebFetch`（不复用 Step 1 输出），读取日 **2026-11-09**；三源均直读原文命中。

| 引用 | ID / 路径 | 验证方式 | 命中或差异 | 状态 |
|------|-----------|----------|-----------|------|
| S1 | PEP 594（Final / Python-Version 3.11 / Created 2019-05-20） | 独立 `WebFetch` 直读 https://peps.python.org/pep-0594/ | 逐字命中 `Deprecation schedule` 三段：3.11「deprecated modules will start issuing `DeprecationWarning`」；3.12「This is the last version of Python with the deprecated modules」；3.13「All modules deprecated by this PEP are removed from the `main` branch」 | **已验证（T1 直读）** |
| S2 | Python `warnings` 文档（`docs.python.org/3`，页面渲染 3.14） | 独立 `WebFetch` 直读 https://docs.python.org/3/library/warnings.html | 逐字命中：`DeprecationWarning`「(ignored by default, unless triggered by code in `__main__`)」；默认过滤器「`default::DeprecationWarning:__main__` / `ignore::DeprecationWarning`」；3.2 / 3.7 变更记录 | **已验证（T1 直读）** |
| S3 | PEP 387（Active / Type Process / Created 2009-06-18） | 独立 `WebFetch` 直读 https://peps.python.org/pep-0387/ | 逐字命中：Soft Deprecation「does not imply scheduling the removal」「does not issue a warning: it's only mentioned in the documentation」；Making Incompatible Changes 第 3 步「Wait for the warning to appear in at least two minor Python versions … It is preferred, though, to wait 5 years before removal」 | **已验证（T1 直读）** |
| P1-P16 | 本仓（@ `696bd7b`） | E1 命令重跑（§6.1.1 逐项） | 14 项逐值命中；**2 项偏差（P6/P11）已修正**（F-R1/F-R3/F-R4）；另 1 项回放约束（F-R5） | **已验证（E1 重跑）** |

### 6.1 独立复核 pass

> 本节由 Step 2 独立执行并单独写入（RULE-1：Review 与正文分离）；不复用 Step 1 的中间输出，命令全部重跑。

#### 6.1.1 E1 复核表（@ `696bd7b`，工作区仅新增本文档）

| # | 复核项 | 命令（可重放） | Step 2 读数 | 判定 |
|---|--------|----------------|-------------|------|
| 1 | HEAD | `git rev-parse --short HEAD` | `696bd7b` | 命中 |
| 2 | V1 体量 | `(Get-Content core/engine.py \| Measure-Object -Line).Lines` + `(Get-Item core/engine.py).Length` | `724 行 / 29910 B` | 命中 |
| 3 | CLI 已迁移 | `Select-String cli.py -Pattern 'core.engine' -SimpleMatch` / `'create_default_engine'` | `core.engine=0`；L36 `from core.factory import create_default_engine`、L77 `engine = create_default_engine(config)` | 命中 |
| 4 | 活跃 import 面 | 全仓 `*.py` 匹配 `from core.engine import` / `from core import engine` | 11 文件 = **10 活跃**（6 examples + 4 tests）+ `core/__init__.py` 1 处注释 | 命中 |
| 5 | g2/g3 与收集数 | `<Python312> -m pytest tests/test_rebalance_exits.py --collect-only -q`；两文件合计 | 2 项：`test_g2_engine_v1_liquidates_exited_positions`、`test_g3_engines_share_identical_targets`；两文件合计 **20 tests collected** | 命中 |
| 6 | 死脚本 | `<Python312> -m pytest tests/test_visual_trace.py tests/test_visual_trace_v2.py --collect-only -q` | `collected 0 items`，exit **5** | 命中 |
| 7 | 全量基线 | `$env:MPLBACKEND='Agg'; <Python312> -m pytest -q` | **`509 passed, 82 warnings in 30.05s`** | 命中 |
| 8 | 测试文件数 | `Get-ChildItem tests -Filter 'test_*.py'` | `50` | 命中 |
| 9 | pytest 配置 | `Select-String pyproject.toml 'filterwarnings'` + 读 `[tool.pytest.ini_options]` | `filterwarnings=0`；仅 testpaths/python_files/python_classes/python_functions/addopts | 命中 |
| 10 | 活文档 | `Select-String -SimpleMatch`（ARCH：`engine.py`+`Engine V1`；WIKI：`engine.py`；DEC：`core/engine.py`；README：`509`） | ARCH **3**（L81/L198/L304）/ WIKI **15** / DEC **1**（L30）/ README **4 行**（L7/L98/L262/L411） | 偏差 2 项（F-R1/F-R4） |
| 11 | 可恢复性 | `git ls-files core/engine.py` | 命中（tracked） | 命中 |
| 12 | docstring 提及 | `Select-String` 三文件 `BacktestEngine` | `engine_plugins.py:14,383` / `walk_forward_engine.py:45` / `multi_strategy_engine.py:64` | 命中 |
| 13 | 迁移目标接口 | 读 `core/factory.py:242-257` | `create_default_engine(config) -> 'BacktestEngineV2'`，经 `ComponentFactory.create_engine_kwargs()` | 命中 |
| 14 | 等价性归档 | 读 `CHANGELOG.md:21` | 「最大差异 0.000000」逐字命中 | 命中 |
| 15 | 弃用三层标记 | 读 `core/engine.py` L3/L46/L60-L61 | `⚠️ DEPRECATED` / `.. deprecated::` / `warnings.warn(...DeprecationWarning...)` | 命中 |

#### 6.1.2 发现与修正（F-R 系列）

| ID | 等级 | 发现 | 证据 | 处置 |
|----|------|------|------|------|
| F-R1 | P3 | P11/§1.5 原记「README 计数 2 处」，实测 **4 行含 509**（3 处 `509 passed`：L7 徽章 / L98 / L262；1 处 `509 tests, 50 files`：L411） | 复核项 10 | **已修正**（P11、§1.5 README 行） |
| F-R2 | P3 | §3.3 A1 行原写「测试 509→505」，与 §1.3 算式「509→507」自相矛盾 | 509 − g2 − g3 = **507** | **已修正**为 507 |
| F-R3 | P3 | P6 原写「打 6 个 patch」，实测 `_run_engine_v1` 为 **7 个**（L298-L305） | `Select-String 'patch('` 命中 L298-L305 共 7 处 | **已修正**为 7 并列出组件 |
| F-R4 | P3 | P11/§1.5 原记 ARCHITECTURE 6 / DECISIONS 2，为**宽匹配**（混入 `walk_forward_engine.py`、`batch_backtest/engine.py` 等非 V1 行）；V1 相关精确值为 **3 / 1** | 复核项 10 | **已修正**为精确口径并列出命中行号 |
| F-R5 | P3 | 全量测试须**固定 Python 3.12.10 解释器**：base Anaconda（`C:\ProgramData\Anaconda3`）缺 `cvxpy` → 2 个 collection ERROR；项目 `.venv` 无 `pytest` | 两次失败读数 + `<Python312>` 成功读数 | **记录为回放约束**：Step 3 起 E1 命令统一标注 `<Python312>` |

> F-R1~F-R4 属**取证精度**修正（P3），不改变结论与方案倾向；F-R5 为回放约束注记。**无 P1/P2 阻断项。**

#### 6.1.3 复核结论

| 项 | 结论 |
|----|------|
| 外部引用（F4） | S1/S2/S3 三条 T1 来源独立复读、逐字命中；**F3 无降级**（无通道失败） |
| 本仓事实 | P1-P16 中 14 项逐值命中；2 项（P6/P11）偏差已回写；1 项回放约束（F-R5）已记录 |
| 结论稳定性 | §5 倾向「删除 A / examples 迁移 A / tests A1 / 文档 A」**不受修正影响** |
| 阻断项 | **0** |
| 门禁 | **Step 2 Review pass** → 进入 Step 3 设计 |
