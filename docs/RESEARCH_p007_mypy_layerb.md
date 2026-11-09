# P-007 层 B（引擎 mypy 93 errors 清理） · 调研文档

> **文档编号**: RESEARCH_p007_mypy_layerb
> **阶段**: Phase 1 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: Step 1 完稿；Step 2 Review 见 §11；Q1-Q4 补充调研见 §12；Q1-Q3 深度分析见 §13（2026-11-09）；**Q1=A / Q2=A / Q3=A / Q4=B 已裁决**，可进入 Step 3 DESIGN
> **上游**: [PROGRESS.md](PROGRESS.md) §1.4 P-007 / §3.9 层 A；[PROGRESS.md](PROGRESS.md) §2 U-006
> **下游**: DESIGN_p007_mypy_layerb.md → IMPL_p007_mypy_layerb.md → CHECKLIST_p007_mypy_layerb.md
> **档位**: T1（引擎主路径 + 接口契约修正；含 1 项待裁决的行为变更候选）
> **证据时点**: 本仓读数 @ `762ff5f`；Python 3.12.10 / mypy 2.1.0 / numpy 2.4.6 / pandas 2.2.3

---

## 1. 问题定义

P-007 层 A 已把 `core/` 非引擎 16 文件的 mypy error 从 26 清零，门禁读数由 `119 errors in 19 files` 降至 **`93 errors in 3 files`**（[CHECKLIST_p007_mypy_layera.md](CHECKLIST_p007_mypy_layera.md) §8 GREEN-2）。层 A 的范围约束明确写了「引擎三件套零改动 + U-006 不关闭，层 B 另立批次」（[PROGRESS.md](PROGRESS.md) §3.9「范围约束」「验收口径」）。

本轮需要回答四个问题：

1. 93 个 error 的真实构成是什么（纯注解缺口 / 契约缺口 / 真实缺陷）？
2. 其中是否存在**运行时真实后果**（不是只让 mypy 闭嘴）？
3. 修复应采用哪种窄化手段（`assert` / 局部别名 / `cast` / 重构），代价与边界各是什么？
4. 是否存在「层 A 已排除、但本批必须触碰」的接口文件（`core/interfaces.py`）？

---

## 2. 基线读数（E1）

| ID | 命令（`%PY312%` = `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`） | 读数 | 说明 |
|----|------|------|------|
| B1 | `python -m mypy --explicit-package-bases core` | **`Found 93 errors in 3 files (checked 29 source files)`**，exit 1 | U-006 门禁口径；与层 A 收口逐字一致 |
| B2 | 同上，按文件 | engine_v2 **54** / engine_v3_vector **26** / factory **13** | 54+26+13=93 |
| B3 | 同上，按错误码 | `union-attr` **59** / `index` **16** / `no-any-return` **9** / `arg-type` **4** / `name-defined` **2** / `var-annotated` **1** / `valid-type` **1** / `misc` **1** | 脚本统计（见 B9） |
| B4 | `python -m mypy --explicit-package-bases --check-untyped-defs core` | **`Found 102 errors in 4 files`**，exit 1 | 新增 **9** 条：engine_v2 **7** + data_v3 **2** |
| B5 | `python -m mypy . --explicit-package-bases` | `Found 216 errors in 32 files` | **范围外**：含 tests/agents/examples/cli/batch_backtest；U-006 口径仅 `core/` |
| B6 | `python -m mypy --version` | `mypy 2.1.0 (compiled: yes)` | 本机工具版本 |
| B7 | `python -c "import numpy,pandas"` | numpy 2.4.6 / pandas 2.2.3 | `index` 类报错的 stub 来源 |
| B8 | `git rev-parse --short HEAD` | `762ff5f` | E3 读码绑定 commit |
| B9 | 统计脚本：解析 mypy 输出 → 按文件/错误码/所在函数分组 | 见 §5 归因表 | 脚本在 `%TEMP%`，未入仓（`[未入仓-不可重放]`） |

> B5 如实记录：本仓 mypy 技术债的完整面是 216 errors / 32 files；U-006 只承诺 `core` 归零，本批**不**扩大范围（否则批次不可收敛）。

---

## 3. 本仓事实（E1/E2/E3）

| ID | 事实 | 证据 |
|----|------|------|
| P1 | `BacktestEngineV2.__init__` 把 8 个组件声明为 `Optional[I...] = None`（`dm/universe/pipeline/combiner/optimizer/trigger/executor/tracker`），另加 `pending_queue` 与 `_execution_policy`（`core/engine_v2.py:138,147-155`） | E3 @`762ff5f` |
| P2 | 这 8 个组件由 `setup()` 填充（`core/engine_v2.py:163-247`），`setup(self)` **零注解**（无参数注解、无返回注解） | E3 @`762ff5f` |
| P3 | 依据 mypy 官方口径「函数完全无注解则函数体不被检查」（A12），`setup()` 函数体**整体不在检查范围内** | E3 + A12 |
| P4 | 实证 P3：`--check-untyped-defs` 后新增 9 条，其中 7 条落在 `setup()` 及其调用链（6 条在 setup 函数体 `engine_v2.py:185,194×2,201,224,231`，1 条在其调用的 `_precompute_factors` L259） | E1 B4 |
| P5 | `run()` 只守卫 `self.dm is None → RuntimeError`（`core/engine_v2.py:277-278`）；其余 7 个组件在 `run()` 路径上无任何守卫 | E3 @`762ff5f` |
| P6 | `run()` 的日循环用 `except Exception as e: logger.error(...); continue` 吞掉所有交易日异常（`core/engine_v2.py:292-294`） | E3 @`762ff5f` |
| P7 | `_composite_signal: Optional[pd.DataFrame]`（`core/engine_v2.py:158`）仅在 `_precompute_factors()` 赋值；`cfg.factor_files` 为空时该函数 `logger.warning + return`（`core/engine_v2.py:252-254`），属性保持 `None` | E3 @`762ff5f` |
| P8 | `BacktestConfig.factor_files` 默认值为 `[]`（`core/config.py:345`）；`validate()` 已把空列表列为错误（`core/config.py:392-394`），但**引擎与 CLI 均未调用 `validate()`**（`cli.py` 无 `validate` 命中；仅 tests/agents 调用） | E3 @`762ff5f` |
| P9 | **探针 A-1（真实可达）**：`BacktestConfig(data_dir=data/test_ashare, factor_files=[])` → `setup()` 成功但 `_composite_signal is None = True` → `run()` 产出 **100 条 ERROR**（100 个交易日各 1 条），首条 `TypeError: object of type 'NoneType' has no len()`；`results["portfolio_value"].empty is True`；`unclosed_positions = {}` | E2 探针（`%TEMP%\p007b_probe_signal_none.py`），读数见 §3.1 |
| P10 | **探针 A-2（守卫缺口）**：未 `setup()` 直接 `run()` → `RuntimeError: 请先调用setup()方法`（有守卫）；未 `setup()` 直接 `_generate_results()` → `AttributeError: 'NoneType' object has no attribute 'get_snapshots'`（无守卫） | E2 探针（同上，PROBE-1 / PROBE-8） |
| P11 | `IPositionTracker.get_snapshots` 声明 `-> list[dict]`（`core/interfaces.py:271`），`PositionTracker.get_snapshots` 实际返回 `list[PortfolioSnapshot]`（`core/tracker.py:350`，`PortfolioSnapshot` 是 `@dataclass`，非 dict，`core/tracker.py:133-156`） | E3 @`762ff5f` |
| P12 | 实证 P11 的契约违约：`t: IPositionTracker = PositionTracker(10, 1e6)` → `[assignment]`，note 明确列出 `Expected: list[dict]` / `Got: list[PortfolioSnapshot]` | E2 探针（`%TEMP%\p007b_proto_probe.py`） |
| P13 | `_generate_results()` 的 `arg-type`（`engine_v2.py:767`）就是 P11 的症状：`generate_report(snapshots: list[PortfolioSnapshot], ...)`（`core/analytics.py:468-469`）收到协议声明的 `list[dict]` | E3 @`762ff5f` |
| P14 | `IExecutionSimulator` 协议未声明 `trade_log`（`core/interfaces.py:197-238`），而 `_generate_results()` 依赖 `self.executor.trade_log.get_trades_df()`（`core/engine_v2.py:762`）→ 该行 2 条 error 中 1 条是 Optional 窄化、1 条是**协议缺成员** | E3 @`762ff5f` |
| P15 | `PortfolioSnapshot` 为 `core.tracker` 内的 dataclass；`core/tracker.py` 不 import `core.interfaces`，可安全使用 `TYPE_CHECKING` 反向引用 | E3 `core/tracker.py:11-20` |
| P16 | `engine_v2` 的 54 条 error 按方法：`_process_trading_day` 7、`_force_liquidation` 5、`_process_pending_orders` 7、`_try_fallback_order` 6、`_execute_rebalance` 11、`_generate_orders_via_policy` 5、`_execute_next_day_orders` 6、`_generate_results` 7 | E1 脚本 B9 |
| P17 | `engine_v3_vector` 的 26 条：`_precompute_signals` 5（`self.dl` Optional）、`run` 9（4 个 Optional ndarray 的下标读写）、`_rebalance_vectorized` 12（`self.dl` + Optional ndarray） | E1 脚本 B9 |
| P18 | `engine_v3_vector.run()` 有 `if self.dl is None: raise RuntimeError`（`core/engine_v3_vector.py:282-283`），`_precompute_signals` / `_rebalance_vectorized` 无守卫；两者只由 `setup()` / `run()` 调用 | E3 @`762ff5f` |
| P19 | `factory.py` 13 条：`default_factory: callable`（`valid-type` 1 + `misc` 1，`core/factory.py:95,112`）、`_create_component -> Any` 造成 9 个包装方法 `no-any-return`（L116-183）、`"BacktestEngineV2"` 仅在函数内 import 导致 2 条 `name-defined`（L245,263） | E3 @`762ff5f` |
| P20 | **探针（泛型工厂不免费）**：把 `_create_component` 泛型化为 `Callable[..., T]` + 单处 `cast(T, ...)` 时，lambda 形参无注解会使 `T` 退化为 `Any`，`no-any-return` 仍出现 1 条（`make_str`） | E2 探针（`%TEMP%\p007b_factory_probe.py`） |
| P21 | **探针（窄化失效）**：`assert self.a is not None` 在**后续方法调用**后失效（`self.h()` 之后 `self.a + 1` 报 `[operator]`）；改为局部别名 `a = self.a; assert a is not None` 后跨调用保持窄化（0 error） | E2 探针（`%TEMP%\p007b_narrow_probe.py` / `p007b_narrow_local.py`） |
| P22 | 测试覆盖缺口（Step 2 复算修正，F-R1）：`tests/` 对 `factor_files` **37 行 / 10 文件**命中、对 `_composite_signal` **8 行 / 2 文件**命中；`setup()+run()` 集成测试 **9 处 / 5 文件**（`test_decoupled_engine.py:297` 全 Mock、`test_rebalance_exits.py:275` Fake 组件、`test_real_ashare_backtest.py:123,139,174,198`、`test_real_ashare_strict_validation.py:310,452,584`），**全部提供非空 `factor_files` 或手动赋值 `_composite_signal`**（`test_real_ashare_strict_validation.py:315,456,588`、`test_real_ashare_backtest.py:144,178,202` 直接 `engine._composite_signal = ...`）——`factor_files=[]` → `_composite_signal=None` 路径**无任何测试覆盖** | E1 `Grep tests/`（path 直指目录） |
| P23 | 基线测试数：`514 passed`（P-010 收口读数，`ac48a22`）→ 本批以同一解释器复跑为 RED/GREEN 基线 | E1 [CHECKLIST_p010_aux_defaults.md](CHECKLIST_p010_aux_defaults.md) §7 |
| P24 | 协议无 `@runtime_checkable`（`core/interfaces.py` 0 命中），因此「实现是否符合协议」只能由 mypy 静态校验，不能靠 `isinstance` 运行时断言 | E3 @`762ff5f` |

### 3.1 探针原始读数（E2）

`%TEMP%\p007b_probe_signal_none.py`（夹具 `data/test_ashare`，`factor_files=[]`）：

```
PROBE-1 no-setup run(): RuntimeError: 请先调用setup()方法
PROBE-2 _composite_signal is None: True
PROBE-3 components all set: True
PROBE-4 error log lines: 100
PROBE-5 first error: 处理交易日 2024-01-02 00:00:00 时发生错误: object of type 'NoneType' has no len()
PROBE-6 portfolio_value empty: True
PROBE-7 unclosed_positions: {}
PROBE-8 no-setup _generate_results(): AttributeError: 'NoneType' object has no attribute 'get_snapshots'
```

> 结论：A-1 不是「mypy 洁癖」——它是一条**从公开 API 可达、被 `except Exception` 吞掉、最终返回空结果**的静默失败链路。唯一的提示是 `WARNING core.engine_v2: 未指定因子文件` 与 100 条 ERROR 日志。

---

## 4. 外部锚点（T1/T2/T3）

> 检索通道与降级链见 §4.2。所有「读取日」均为 2026-11-09。

| ID | 结论（用于本批哪一步） | 来源 | Layer | 版本 / ID | 原文要点 |
|----|------|------|-------|-----------|----------|
| A1 | 「构造时置 None、initialize 后非 None」是官方承认的窄化盲区，**官方推荐 `assert x is not None`** → 支撑 S1/S2 方案 | mypy 文档 “Kinds of types” §Optional | **T1** | stable edition = mypy **2.4.1** 文档 | “This notably happens when a class instance can exist in a partially defined state, where some attribute is initialized to `None` during object construction, but a method assumes that the attribute is no longer `None`.” |
| A2 | `union-attr` 的官方出路就是 `assert obj is not None` / `assert isinstance(...)` → 与 A1 互证 | mypy 文档 “Error codes enabled by default” §union-attr | **T1** | stable（2.4.1） | “You can often work around these errors by using `assert isinstance(obj, ClassName)` or `assert obj is not None`” |
| A3 | `cast()` **不做运行时检查**，只是给类型检查器的提示 → 支撑「拒绝全量 cast」 | mypy 文档 “Type narrowing” §Casts | **T1** | stable（2.4.1） | “mypy casts are only used as hints for the type checker, and they don't perform a runtime type check.” |
| A4 | 另一处独立强调 cast 无运行时检查（互证 A3） | mypy 官方 cheat sheet | **T1** | latest edition | “It's only for mypy -- there's no runtime check.” |
| A5 | 窄化会被**函数调用**打断；对**可变对象的成员**做窄化风险最高 → 支撑 P21 与「局部别名」方案 | typing.python.org 官方指南 §Invalidated assumptions | **T1** | latest edition（读取日 2026-11-09） | “...in the meantime other code may have run (for example, in another thread, another coroutine, or simply some code that was invoked by a function call) and invalidated the earlier condition. Such problems are most likely when narrowing is performed on elements of mutable objects...” |
| A6 | `assert` 在 `-O` 下**不生成任何代码** → 支撑「assert 不改变生产语义」的边界声明 | Python Language Reference §7.3 | **T1** | 3.12.15（Review 轮补取 3.12 专页逐字确认，F-R4） | “The current code generator emits no code for an assert statement when optimization is requested at compile time.” |
| A7 | Protocol 是结构化子类型，成员**类型必须兼容** → 支撑 P11/P14 的契约判定 | mypy 文档 “Protocols and structural subtyping” | **T1** | stable（2.4.1） | “Class Dog is a structural subtype of class Animal if the former has all attributes and methods of the latter, and with compatible types.” |
| A8 | 仅用于注解的跨模块导入应放进 `if TYPE_CHECKING:` → 支撑 factory / interfaces 的修法 | mypy 文档 “Annotation issues at runtime” §Import cycles | **T1** | stable（2.4.1） | “if the import is only needed for type annotations ... you can write the imports inside `if TYPE_CHECKING:` so that they are not executed at runtime.” |
| A9 | 跨模块前向引用**不能**只靠字符串注解绕过，必须真实存在该名字 → 支撑 `name-defined` 的修法 | 同上 §String literal types | **T1** | stable（2.4.1） | “String literal types must be defined (or imported) later *in the same module*. They cannot be used to leave cross-module references unresolved.” |
| A10 | `callable` 是内建函数不是类型，应使用 `Callable` | mypy 文档 “Error codes enabled by default” §valid-type | **T1** | stable（2.4.1） | “You can use `Callable` as the type for callable objects” |
| A11 | 空集合初始化需显式注解（`all_orders = []`） | 同上 §var-annotated | **T1** | stable（2.4.1） | “This typically happens when you initialize a variable with an empty collection or `None`.” |
| A12 | **完全无注解的函数，函数体不被检查** → 支撑 P3/P4 的「setup 盲区」判定 | mypy 文档 “Common issues and solutions” | **T1** | stable（2.4.1） | “Functions that do not have any annotations (neither for any argument nor for the return type) are not type-checked” |
| A13 | `--warn-return-any` 下返回 `Any` 即报 `no-any-return` → 说明本批不能靠「返回 Any 混过去」 | mypy 文档 “Error codes for optional checks” §no-any-return | **T1** | stable（2.4.1） | “mypy generates an error if you return a value with an `Any` type in a function that is annotated to return a non-`Any` value.” |
| A14 | 第三方 stub 类型缺陷会显著放大客户端错误：**70%** 客户端仓库至少有 1 个来自第三方 API 的类型错误，numpy/pandas/django/pytorch 占不成比例份额 → 解释本批 `Optional[np.ndarray]` 相关 `index` 错误的来源性质 | *All or Nothing: How Library Type Annotations Affect Client-Side Errors in Python* | **T1（摘要级）** | DOI `10.1145/3832783.3834434` | 13,751 客户端仓库 × 4,178 库，Pyright 检查 |
| A15 | 静态类型错误修复存在可归纳的模式（可作为「按错误码分组修复」的方法学支撑） | *PyTy: Repairing Static Type Errors in Python* | **T1（摘要级）** | arXiv `2401.06619v1` / DOI `10.1145/3597503.3639184` | “an empirical study that investigates how developers [repair type errors]” |
| A16 | 工程界真实项目同样出现本批的报错形态（`Item "None" of "Optional[...]" has no attribute`） | PyPI 包 `mypy-gh-action-report` 0.1.0 的 mypy 输出 | **T3** | 0.1.0（Step 2 直取页面失败，仅有检索摘要 → **未验证**，F-R6） | 仅用于说明「不是本仓孤例」，**不承载任何结论** |

### 4.1 结论的独立来源配对

| 关键结论 | 来源 1 | 来源 2 | 满足 |
|----------|--------|--------|------|
| assert 是官方推荐的窄化手段 | A1（kinds_of_types） | A2（error_code_list） | ≥2 独立 T1 |
| cast 无运行时检查 | A3（type_narrowing） | A4（cheat sheet） | ≥2 独立 T1 |
| 窄化会被调用打断 | A5（typing 规范） | P21（本仓探针 E2） | 1 T1 + 1 实证 |
| `assert` 不改变生产语义 | A6（语言参考 -O） | A1（官方推荐用法） | ≥2 独立 T1 |
| 协议成员必须类型兼容 | A7（protocols） | P12（本仓探针） | 1 T1 + 1 实证 |

### 4.2 检索通道与降级链（F3）

| 通道 | 结果 | 降级 |
|------|------|------|
| 学术检索 `mcp_paper-search`（21 源） | 28 条命中；相关 5 条（A14/A15 + SANER 2023 `10.1109/saner56733.2023.00046`、FSE 2022 `10.1145/3540250.3549114`、`10.1145/3691620.3695545`）；biorxiv/medrxiv/zenodo 命中为生物医学噪声；**zenodo 通道报错** `'str' object has no attribute 'isoformat'` | 仅采信 Python 类型系统方向的相关条目；zenodo 失效如实记录，未影响结论 |
| 通用检索（WebSearch 第 1 轮：`Item "None" of ... initialized in __init__ set in setup`） | 结果噪声大（PyPI 包页、邮件列表、无关 GitHub 原始文件） | 降级到第 2 轮定向检索 + 官方文档直取 |
| 通用检索（WebSearch 第 2/3 轮） | 命中 mypy 官方文档 3 页 + typing 官方指南 1 页 | 无降级 |
| 官方文档直取（WebFetch） | 成功：mypy `common_issues` / `error_code_list` / `error_code_list2` / `type_narrowing` / `kinds_of_types` / `protocols` / `runtime_troubles`；Python 3.12 `simple_stmts`；typing.python.org `type_narrowing` | 无降级 |
| 本仓检索（Grep / Read / Glob） | 正常 | 无降级 |

> 边界（诚实声明）：A14/A15 为**摘要级**读数，仅用于解释错误来源的性质，**不作为门禁判据**（符合 `F:\Spec_Workflow\SPEC_PROCESS.md` §边界「摘要级读数不得作为门禁判据」）。本机 mypy 为 2.1.0，与文档 stable（检索标题示 2.4.1）存在版本差；窄化/报错行为以本机 E2 探针复算为准（§11.2），文档仅支撑「官方推荐手段」的定性结论（F-R7）。

---

## 5. 缺陷分类

### 5.1 分类口径

- **A 类（真实缺陷）**：可从公开 API 到达，且产生运行时后果（崩溃 / 静默错误结果）。
- **B 类（契约缺陷）**：类型系统与运行时不符，当前无已知崩溃，但会让调用方/实现方在边界上失配。
- **C 类（纯窄化缺口）**：语义正确，仅缺类型收窄，运行期无差异。

### 5.2 归因表（93 = 43 窄化 + 2 契约 + 7 信号 + 1 矩阵 + 1 注解 + 26 v3 + 13 factory）

| 类别 | ID | 位置 | 条数 | 依据 | 运行时后果 |
|------|----|------|------|------|-----------|
| **A** | A-1 | `_composite_signal` 为 `None`：`engine_v2.py:321,322,478,481,522,527,532` | **7** | P7/P8 + P9 探针 | **有**：每日 `TypeError` 被吞，返回空回测（E2 已证） |
| **A** | A-2 | `_generate_results()` 无 setup 守卫（症状行 `engine_v2.py:761,762,781,790,804` 属 C-1 静态表现） | **0**（本条是运行时守卫缺口，静态表现已计入 C-1） | P5/P10 | **有**：`AttributeError`（E2 已证）；`run()` 只守 `dm` |
| **B** | B-1 | `IPositionTracker.get_snapshots -> list[dict]` 与 `PositionTracker -> list[PortfolioSnapshot]` 不符：`engine_v2.py:767` | **1** | P11/P12/P13 | 无崩溃；但 `PositionTracker` **不满足自身协议**（E2 已证） |
| **B** | B-2 | `IExecutionSimulator` 缺 `trade_log`：`engine_v2.py:762` | **1** | P14 | 无崩溃（运行时有该属性） |
| **C** | C-1 | `engine_v2` 组件 Optional 窄化（dm/universe/optimizer/trigger/executor/tracker） | **43** | P1/P2/P3/P5 | 无（setup 后必非 None） |
| **C** | C-2 | `_returns_matrix` Optional 下标：`engine_v2.py:548` | **1** | P1 | 无 |
| **C** | C-3 | `all_orders = []` 缺注解：`engine_v2.py:640` | **1** | A11 | 无 |
| **C** | C-4 | `engine_v3_vector` 的 `self.dl` 窄化 + 4 个 Optional ndarray 下标 | **26** | P17/P18 | 无（`setup()` 后必非 None；`run()` 有 dl 守卫） |
| **C** | C-5 | `factory.py` 的 `callable` / `Any` 返回 / 前向引用 | **13** | P19/P20 | 无（注解为字符串，运行期不解析） |
| 合计 | | | **93** | | |

> 计数校验：43（C-1）+ 1（B-1）+ 1（B-2）+ 7（A-1）+ 1（C-2）+ 1（C-3）= **54**（engine_v2）；+26（v3）+13（factory）= **93**。A-2 不单独计数（其静态表现已含在 C-1 的 43 条内），避免重复归因。

### 5.3 关键判断

1. **93 个 error 背后只有 2 类可复现的运行时缺陷**（A-1 / A-2）：A-1 对应 7 条 error，A-2 的静态表现散落在 C-1 的 43 条内；其余 error 均无法证明存在运行时后果。若只做窄化，A-1 仍会每天刷 100 条 ERROR 并返回空结果——这就是本批必须落地行为变更的原因。
2. **A-1 的根因不是 Optional 注解，而是「空 `factor_files` 时 `_precompute_factors` 静默返回」**。仅加 `assert self._composite_signal is not None` 会把「静默空回测」变成「每日 AssertionError 被吞」，仍是静默失败（更糟：`-O` 下 assert 消失，回到 TypeError）。
3. **B-1 不是 engine 的错**：协议声明错了，engine 只是受害者；在 engine 侧 `cast` 会把缺陷固化在接口层。
4. **`setup()` 是结构性盲区**（P3/P4）：即使本批把 93 清零，`setup()` 及其调用链仍有 7 条未检查错误。是否顺手打开（加 `-> None`）属于范围决策，见 §7.5。

---

## 6. 影响面

| 面 | 现状 | 本批可能的影响 |
|----|------|----------------|
| 门禁 `mypy-check` | `fail(93)`（如实） | 若清零 → **verdict 转 pass**；U-006 可关闭（需在 PROGRESS §2 回填） |
| 全量测试 | `514 passed`（P-010） | 新增 A-1/A-2 测试 + 可能的协议一致性测试；引擎主路径测试（`test_decoupled_engine` / `test_rebalance_exits` / `test_real_ashare_strict_validation`）必须保持绿 |
| 运行时行为 | A-1 静默空回测；A-2 无守卫 | A-1 若选 fail-fast → **行为变更**（`setup()` 抛错），需 CHANGELOG `Changed` + DESIGN 披露 |
| `-O` 运行 | assert 消失 | 若用 assert 做守卫，生产 `-O` 下仍在 `dm` 处报 `RuntimeError`（`run()` 既有守卫），其余位置回到 AttributeError——**与今日一致，无回归** |
| 文件面 | 3 个 error 文件 | 预期触碰 `core/engine_v2.py`、`core/engine_v3_vector.py`、`core/factory.py`、`core/interfaces.py`（+ 1 测试文件） |
| 跨模块 | `filter/`、`agents/`、`tests/` 有各自的同类错误 | **不在 U-006 口径**；本批只记录不修（§8） |

---

## 7. 候选方案（含被拒绝的替代方案与代价）

### 7.1 窄化手段（覆盖 C-1 / C-2 / C-4，共 70 条）

| 方案 | 做法 | 代价 | 判定 |
|------|------|------|------|
| **S1 局部别名 + assert** | 每个方法开头 `dm = self.dm; assert dm is not None`，方法体内改用局部名 | 机械改动 ~70 行；需逐方法核对 | **候选（推荐）** |
| S2 组件包 dataclass + accessor | `_comp: Optional[_Components]`；`@property def comp(self) -> _Components: assert ...; return self._comp` | 改写 44 处调用点 + 新增类；diff 更大、回归面更广 | 候选（次选） |
| S3 方法级单 assert（层 A 风格） | 方法开头 `assert self.dm is not None`，方法体仍用 `self.dm` | **不成立**：A5 + P21 实证，方法调用后窄化失效，仍有大量残余 error | 拒绝（实证否定） |
| S4 全量 `cast` | `cast(IDataManager, self.dm)` | A3/A4：cast 无运行时检查 → 若 setup 未调用，类型系统说谎 | 拒绝（违反诚实性） |
| S5 改注解为非 Optional | 把 8 个字段改成非 Optional | 运行时仍可能是 None → 注解与事实不符（正是本批要消灭的缺陷形态） | 拒绝 |
| S6 放宽 mypy 配置 | `warn_return_any=false` / 排除文件 / `# type: ignore` | 掩盖基线，U-006 永不关闭 | 拒绝（RULE 级红线） |

### 7.2 A-1（`_composite_signal` 为 None）

| 方案 | 做法 | 行为 | 判定 |
|------|------|------|------|
| **A-1a fail-fast** | `_precompute_factors()` 在 `factor_files` 为空时 `raise ValueError(...)`（与 `config.validate()` 口径一致，P8） | `setup()` 抛错，不再产出空结果 | **候选（推荐）** |
| A-1b 零信号回退 | 空因子时构造全 0 信号 + `WARNING`，回测可跑但无交易 | 仍是「静默无交易」，只是不刷 ERROR | 候选（保守） |
| A-1c 只加 assert | 各使用点 `assert self._composite_signal is not None` | 每日 AssertionError 被 `except` 吞；`-O` 下退回 TypeError | 拒绝（type theater） |

> 无论选 a 还是 b，都必须保留「使用点非 None」的静态保证（局部别名），否则 mypy 仍报 7 条。

### 7.3 factory（13 条）

| 方案 | 做法 | 代价 | 判定 |
|------|------|------|------|
| **FC-1 `Callable[..., Any]` + 9 处 `cast`** | 修正 `callable` 注解；每个包装方法 `return cast(IDataManager, ...)` | 9 处显式 cast，直白可审 | **候选（推荐）** |
| FC-2 泛型工厂 + 单处 cast | `Callable[..., T]` + `cast(T, ...)` | P20 实证：lambda 形参无注解 → T 退化为 Any，`no-any-return` 仍在 | 拒绝（探针否定） |
| FC-3 传类 + 参数替代 lambda | `_create_component("dm", DataManager, self.cfg)` | 改所有调用形态；DI 语义变化（注册表分支仍返回 Any） | 拒绝（风险大于收益） |
| FC-4 `TYPE_CHECKING` 导入 | 顶层 `if TYPE_CHECKING: from core.engine_v2 import BacktestEngineV2`，返回注解去掉引号 | 无运行时导入，A8/A9 支持 | **候选（推荐，与 FC-1 组合）** |

### 7.4 协议修正（B-1 / B-2，2 条）

| 方案 | 做法 | 代价 | 判定 |
|------|------|------|------|
| **PR-1 修协议** | `get_snapshots() -> list["PortfolioSnapshot"]`（`TYPE_CHECKING` 导入）；`IExecutionSimulator` 增 `trade_log: Any`（或最小 `ITradeLog` 协议） | 协议语义变准；`MockPositionTracker.get_snapshots() -> list` 仍兼容（`list[Any]`） | **候选（推荐）** |
| PR-2 engine 侧 cast | `cast(list[PortfolioSnapshot], self.tracker.get_snapshots())` | 把契约缺陷留在接口层；任何其他消费者仍会踩 | 拒绝 |

### 7.5 `setup()` 盲区（P3/P4，隐藏 7 条）

| 方案 | 做法 | 影响 | 判定 |
|------|------|------|------|
| **ST-1 不打开** | 保持 `setup()` 零注解，记录为已知盲区 | 基线维持 93 → 目标 0；隐藏的 7 条与 §8 的 X1/X2 留在台账 | **候选（推荐，控范围）** |
| ST-2 打开并全修 | `def setup(self) -> None:`，追加修 7 条 | 需触碰 `filter/`（X1）、`core/factor.py`（X2）；批次范围外扩 | 候选（若用户要求一次到底） |

---

## 8. 范围外发现（另立批次候选）

| ID | 发现 | 证据 | 建议 |
|----|------|------|------|
| X1 | `UniverseFilter(self.dm, self.cfg.universe)` 传入 `core.config.UniverseConfig`，而 `UniverseFilter.__init__` 声明 `UniverseFilterConfig`（`filter/universe_filter_clean.py:16-55`）。两者**同名字段类型/默认值不一致**：`exclude_stock_prefixes` 为 `list[str]` vs `bool`；`exclude_na_factors` 默认 `True` vs `False`；`na_factor_names` 默认 `[]` vs `["factor_value"]` | E3 @`762ff5f`；`mypy --check-untyped-defs` 在 `engine_v2.py:185` 复现 | **另立 P-xxx**（语义面，不属于 mypy 清理） |
| X2 | `FactorPipeline(self.dm, ...)` 参数声明为具体 `DataManager`，而引擎持有 `IDataManager`（注入场景下过窄） | E3 + B4（`engine_v2.py:194`） | 另立（契约放宽，需评估 `factor.py`） |
| X3 | `DataLoaderV3._build_maps` 依赖 `self.dates/self.stocks`（Optional），`--check-untyped-defs` 下 2 条 | E1 B4（`data_v3.py:173-174`） | 并入层 B 时可选（若 T2 打开） |
| X4 | `mypy .` 全仓 216 errors / 32 files（tests/agents/examples/cli/batch_backtest） | E1 B5 | 明确不属 U-006；如需清理另立批次 |

> 特别说明：**X1 是真实语义陷阱**——`core` 配置把 `exclude_stock_prefixes` 写成 `list[str]`，但消费方把它当布尔开关，且真正的数据来自 `excluded_prefixes`。若用户按 `core` 字段语义填 `exclude_stock_prefixes=["300","688"]`：gate 为真会打开前缀过滤，但 `excluded_prefixes` 默认 `[]` → 前缀掩码全 True → **过滤不生效**；反之只填 `excluded_prefixes` 则 gate 为假同样不生效——两个字段须同时按 `filter` 侧语义填写才有效（Step 2 F-R5 精确化）。本批只登记，不在「mypy 清理」批次里偷改行为。

---

## 9. 待 Review / 待用户裁决

| ID | 问题 | 影响 |
|----|------|------|
| Q1 | A-1 选 **A-1a fail-fast** 还是 **A-1b 零信号回退**？ | 决定是否有行为变更、是否写 CHANGELOG `Changed` |
| Q2 | 协议修正是否允许改 `core/interfaces.py`（层 A 的排除表未含该文件，但它是「共享契约」）？ | 决定 B-1/B-2 是「修接口」还是「engine 侧 cast」 |
| Q3 | `setup()` 盲区选 **T1 不打开** 还是 **T2 打开并全修**？ | 决定批次是否外扩到 `filter/` / `core/factor.py` |
| Q4 | 若 93 → 0，`mypy-check` 门禁 verdict 由 `fail` 转 `pass`，是否在本批一并更新 U-006 与 CI/文档口径？ | 决定 Step 10 的台账动作 |

> 以上问题在 Step 3 DESIGN 前需收敛；未收敛项不得进入 IMPL。
>
> **已收敛（2026-11-09，用户）**：Q1 = A fail-fast；Q2 = A 最小真实化（含 `ITradeLog` 最小协议）；Q3 = A 不打开；Q4 = B 保持开启。裁决记录见 §12.7 / §13.5。

---

## 10. 来源清单（F1-F3 形态）

| # | 来源 | Layer | 读取日 | 版本 / ID | 用途 |
|---|------|-------|--------|-----------|------|
| 1 | mypy docs · Kinds of types | T1 | 2026-11-09 | stable edition（mypy 2.4.1 文档） | A1 |
| 2 | mypy docs · Error codes enabled by default | T1 | 2026-11-09 | stable（2.4.1） | A2 / A10 / A11 |
| 3 | mypy docs · Type narrowing | T1 | 2026-11-09 | stable（2.4.1） | A3 |
| 4 | mypy official cheat sheet | T1 | 2026-11-09 | latest edition | A4 |
| 5 | typing.python.org · Type Narrowing §Invalidated assumptions | T1 | 2026-11-09 | latest edition | A5 |
| 6 | Python Language Reference · §7.3 assert | T1 | 2026-11-09 | 3.12 edition | A6 |
| 7 | mypy docs · Protocols and structural subtyping | T1 | 2026-11-09 | stable（2.4.1） | A7 |
| 8 | mypy docs · Annotation issues at runtime（§Import cycles / §String literal types） | T1 | 2026-11-09 | stable（2.4.1） | A8 / A9 |
| 9 | mypy docs · Error codes for optional checks | T1 | 2026-11-09 | stable（2.4.1） | A13 |
| 10 | mypy docs · Common issues and solutions | T1 | 2026-11-09 | stable（2.4.1） | A12 |
| 11 | *All or Nothing: How Library Type Annotations Affect Client-Side Errors in Python* | T1（摘要级） | 2026-11-09 | DOI `10.1145/3832783.3834434` | A14 |
| 12 | *PyTy: Repairing Static Type Errors in Python* | T1（摘要级） | 2026-11-09 | arXiv `2401.06619v1` / DOI `10.1145/3597503.3639184` | A15 |
| 13 | PyPI `mypy-gh-action-report` 0.1.0 | T3 | 2026-11-09 | 0.1.0 | A16（仅反例参照） |
| 14 | 本仓 `core/engine_v2.py` / `engine_v3_vector.py` / `factory.py` / `interfaces.py` / `tracker.py` / `analytics.py` / `config.py` / `data_v3.py` | T1（源码） | 2026-11-09 | `762ff5f` | P1-P19 / P22 / P24 |
| 15 | 本仓运行期探针 4 个（`%TEMP%`，未入仓） | E2 | 2026-11-09 | `[未入仓-不可重放]` | P9 / P10 / P12 / P20 / P21 |
| 16 | 本仓 mypy 输出统计脚本 | E1 | 2026-11-09 | `[未入仓-不可重放]`，原始输出可重跑 B1/B4 | B3 / B9 / P16 / P17 |

> **降级链**：见 §4.2。**未验证项（Step 2 F-R6 更新）**：A16（PyPI 直取失败，T3 不承载结论）；mypy stable 的版本号 2.4.1（仅来自检索结果标题，stable 首页无版本指示，未经页面证实）。其余外部条目均为官方文档直取引文比对，或 Crossref / paper-search 双通道解析命中（见 §11.1）。

---

## 11. Step 2 Review（独立 pass）

> **执行时点**: 正文完稿后的独立 pass（2026-11-09），与正文非同一次写入（RULE-1）
> **审查者**: 单 Agent 自查（RULE-4）
> **审查方式**: 重跑 E1 命令 + 复跑 E2 探针 + 逐字比对引文 + 标识符解析通道核验；不依赖正文自报

### 11.1 文献验证表（F4 形态）

| 引用 | ID | 验证方式 | 状态 |
|------|----|----------|------|
| A1 mypy docs · Kinds of types | `mypy.readthedocs.io/en/stable/kinds_of_types.html` | WebFetch 直取 + 引文逐字比对（`call_6hr75hYa7Vd1BblOHdzNJsXa.txt` L203） | 已验证（T1 命中） |
| A2 mypy docs · Error codes enabled by default | `.../en/stable/error_code_list.html` | WebFetch + 引文比对（`call_FJC4NSzwfzhxLLiQbDOAO5w4.txt` L40/93/136/265） | 已验证 |
| A3 mypy docs · Type narrowing | `.../en/stable/type_narrowing.html` | WebFetch + 引文比对（`call_4ZoRJ1KLZqVinkDsdeHXpEZ1.txt` L118） | 已验证 |
| A4 mypy cheat sheet | `.../en/latest/_sources/cheat_sheet_py3.rst.txt` | 成文时仅检索摘要；Review 轮直取 rst 源 + 引文比对（`call_y4rrboUXwDkAuQcxuc7Qhp7U.txt` L248） | 已验证（Review 轮升级） |
| A5 typing.python.org · Type Narrowing §Invalidated assumptions | `typing.python.org/en/latest/guides/type_narrowing.html` | WebFetch + 引文比对（`call_JQ55q2PaUz7Zl1sOFLRmM43w.txt` L209） | 已验证 |
| A6 Python 语言参考 §7.3 | `docs.python.org/3.12/reference/simple_stmts.html` | Review 轮补取 3.12.15 专页 + 引文比对（`call_FOwYSmmXS5kNSBLacpyPxsEY.txt` L225）；成文时误标为 /3/ 页 | 已验证（版本标注已修正） |
| A7 mypy docs · Protocols | `.../en/stable/protocols.html` | WebFetch + 引文比对（`call_Gr0x2L2XvK252kPRuZrd1lmh.txt` L7） | 已验证 |
| A8/A9 mypy docs · runtime_troubles | `.../en/stable/runtime_troubles.html` | WebFetch + 引文比对（`call_mKZAhGRnuEp9DS7uuYLpGzJ8.txt` L38/98） | 已验证 |
| A10/A11/A2 同上 error_code_list | 同 A2 | 同 A2（valid-type L93-105 / var-annotated L136-148） | 已验证 |
| A12 mypy docs · Common issues | `.../en/stable/common_issues.html` | WebFetch + 引文比对（`call_FciII4dBS3Hz1RsfiPMvaioY.txt` L11） | 已验证 |
| A13 mypy docs · Error codes for optional checks | `.../en/stable/error_code_list2.html` | WebFetch + 引文比对（`call_YvpmfhSkJdhMNPFrRHM25wjK.txt` L103-113） | 已验证 |
| A14 *All or Nothing: How Library Type Annotations Affect Client-Side Errors in Python* | DOI `10.1145/3832783.3834434` | Crossref API 解析命中：ASE '26，2026-10-07，Asare / Di Grazia / Nadi，页 1308-1319，标题一致 | 已验证（元数据一致；70% 数字为摘要级） |
| A15 *PyTy: Repairing Static Type Errors in Python* | arXiv `2401.06619v1` / DOI `10.1145/3597503.3639184` | paper-search arXiv 源命中 + Crossref 解析命中：2024-04-12，Chow / Di Grazia / Pradel，页 1-13，标题一致 | 已验证（双通道；摘要级） |
| A16 PyPI `mypy-gh-action-report` 0.1.0 | `pypi.org/project/mypy-gh-action-report/0.1.0/` | WebFetch 直取**失败**（连接错误）；仅有检索摘要 | **未验证**（T3，仅反例参照，不承载结论） |
| mypy 文档 stable 版本号 | 「stable = 2.4.1」 | stable 首页直取**无版本指示**（`call_Bgd3KVmgxx7hHdzeeenvffVC.txt`）；2.4.1 仅来自检索结果标题 | **未验证（版本号）**；引文按 stable 页面逐字比对，结论不受影响 |
| 检索命中未采信 | DOI `10.1109/saner56733.2023.00046` / `10.1145/3540250.3549114` / `10.1145/3691620.3695545` | 仅出现在 §4.2 降级链记录，未用作结论锚点 | 不适用（未采信） |

### 11.2 复算记录

| 项 | 命令 / 方式 | 正文读数 | 复算读数 | 判定 |
|----|-------------|----------|----------|------|
| B1 | `mypy --explicit-package-bases core` | 93 / 3 files | `Found 93 errors in 3 files (checked 29 source files)` | ✅ 一致 |
| B2/B3/B9 | 分组脚本（mypy 输出 + AST 定位函数） | 54/26/13 + 错误码分布 + 按方法分布 | **逐字一致**（union-attr 59 / index 16 / no-any-return 9 / arg-type 4 / name-defined 2 / var-annotated 1 / valid-type 1 / misc 1；按方法分布逐行一致） | ✅ 一致 |
| B4 | `--check-untyped-defs core` | 102 / 4 files | `Found 102 errors in 4 files` | ✅ 一致 |
| B5 | `mypy --explicit-package-bases .` | 216 / 32 files | `Found 216 errors in 32 files (checked 137 source files)` | ✅ 一致 |
| P9/P10 | 探针复跑（E2，`p007b_probe_signal_none.py`） | §3.1 八条 PROBE | **逐字一致**（100 条 ERROR / 首条 TypeError / 空结果 / PROBE-8 AttributeError） | ✅ 一致 |
| P12 | 协议一致性探针复跑 | `[assignment]` Expected `list[dict]` Got `list[PortfolioSnapshot]` | 复现一致（1 error） | ✅ 一致 |
| P20 | 泛型工厂探针复跑 | 1 条 `no-any-return`（`make_str`） | 复现一致（L19） | ✅ 一致 |
| P21 | 窄化失效探针 ×2 复跑 | self 属性窄化失效 / 局部别名通过 | 复现一致（L16 error / Success） | ✅ 一致 |
| P22 | `Grep tests/`（**path 直指目录**，绕过 glob） | ~~0 命中~~（首轮 `glob="tests/*.py"` 静默空匹配） | `factor_files` **37 行 / 10 文件**；`_composite_signal` **8 行 / 2 文件**；`.setup()` **9 处 / 5 文件** | ❌ **失实** → F-R1（P2） |
| 引文 | 已存 fetch 文件逐字 grep | §4 表 16 条要点 | A1-A13 关键句逐字命中（文件+行号见 §11.1） | ✅ 一致 |

> **未复跑**: P23 全量测试基线（`514 passed`）引用 P-010 CHECKLIST 的 E1 读数，留待 Step 9 RED 复跑；E2 探针脚本在 `%TEMP%` 未入仓（`[未入仓-不可重放]`，本会话内可复跑，已复跑）。

### 11.3 发现项

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-R1 | **P2** | **P22 失实**：正文写「tests/ 对 factor_files 0 命中」「唯一 setup()+run() 集成测试」。复算（path 直指 tests/）实测 factor_files 37 行/10 文件、_composite_signal 8 行/2 文件、setup() 9 处/5 文件。根因：Step 1 首轮 Grep 使用 `glob="tests/*.py"` 在本环境**静默返回空**（工具层缺陷，非检索无果），正文未复核即采信。另：`test_real_ashare_strict_validation.py:315,456,588` 与 `test_real_ashare_backtest.py:144,178,202` **手动赋值** `engine._composite_signal`，反证 None 路径无任何测试覆盖——A-1 的测试缺口结论不变、反而加强 | 已回写 P22 |
| F-R2 | P3 | 方案编号与既有命名空间冲突：§7.4 P1/P2 撞事实编号 P1-P24；§7.5 T1/T2 撞来源分层 T1-T4；§7.3 F1-F4 撞契约取证形态 F1-F5 | 已回写（PR-1/PR-2、ST-1/ST-2、FC-1..FC-4） |
| F-R3 | P3 | §5.2 A-2 行「位置」列出 5 行实为 C-1 的窄化症状行，与「条数 0」并置易误读；P4 与 §5.3-4 把 `_precompute_factors` 内的 L259 说成「setup() 内」（准确口径：setup 函数体 6 条 + 调用链 1 条） | 已回写措辞 |
| F-R4 | P3 | A6 版本标注「3.12 edition」成文时依据 /3/ 页（3.14.7）；Review 轮补取 3.12.15 专页逐字确认 | 已回写（版本 → 3.12.15） |
| F-R5 | P3 | X1 的「过滤不会生效」机制未展开：gate 字段打开但数据字段 `excluded_prefixes` 默认 `[]` → 前缀掩码全 True；单独填任一字段均不生效 | 已回写 |
| F-R6 | P3 | A4 成文时仅有检索摘要（Review 轮直取 rst 源升级已验证）；A16 PyPI 直取失败 → 标**未验证**；mypy stable 首页无版本指示，「2.4.1」仅来自检索标题 → 版本主张降级为未验证注记（§10 注记 + §11.1） | 已回写 |
| F-R7 | P3 | 本机 mypy 2.1.0 与文档 stable（检索标题示 2.4.1）存在版本差；窄化行为以本机 E2 探针复算为准（已复跑），文档仅作手段支撑 | 已回写（§4 边界补充） |

### 11.4 结论

- **0 P1；1 P2 + 6 P3，全部已回写**。P22 修正后不改变任何方向性结论：A-1 的「无测试覆盖」判断被 6 处手动赋值 `_composite_signal` **加强**。
- 复算 10 项全部一致（B1/B2/B3/B4/B5、探针 ×5、分组统计）；引文 14 条已验证、1 条未验证（A16，T3 不承载结论）、1 项版本号未验证（mypy stable 页无版本指示，不影响引文有效性）。
- **未决项 Q1-Q4 仍待裁决**（§9），进入 Step 3 DESIGN 前须收敛。

---

## 12. 补充调研：Q1-Q4 方案对比（2026-11-09）

> **触发**: Step 2 Review 后，用户要求对 Q1-Q4 做「成本 / 收益 / 兼容 / 维护 / 升级」多维度补充调研并寻找外部事实锚点。
> **形态依据**: `F:\Spec_Workflow\spec\templates\DECISION_MATRIX_TEMPLATE.md` v1.0（维度逐行固定七维，选项列按需增删；每格 `评估（E?；日期）`；计数须附复算命令）；`F:\Spec_Workflow\SPEC_PROCESS.md` §迭代收敛与未决项登记（Type-1 全维度取证，Type-2 先做再改）。
> **新增事实**: P25-P33；**新增外部锚点**: A17-A21（来源清单见 §12.9）。

### 12.1 新增本仓事实（E1/E2/E3）

| ID | 事实 | 证据 |
|----|------|------|
| P25 | 空因子分支只有 3 行（`core/engine_v2.py:252-254`：`if not self.cfg.factor_files: logger.warning(...); return`）；fail-fast 与回退两种改法均为个位数 diff | E3 @`762ff5f` |
| P26 | **零信号回退不是安全默认值（E2 实测）**：全 0 信号下 `EqualWeightOptimizer` 过滤零值后返回空权重（无交易）；`MinVarianceOptimizer` **不滤零**，`nlargest(2)` 选中索引前两只 `['000001','000002']`、权重和 **1.0** → **建立任意组合** | E2 `%TEMP%\p007b_zero_signal.py`：`EQUAL_WEIGHT empty: True` / `MIN_VARIANCE len: 2 index: ['000001','000002'] sum: 1.0`；根因 E3 `core/portfolio.py:168-174` vs `214-218` |
| P27 | **4 个具体组件全部不满足各自协议（E2）**：`ExecutionSimulator`↔`IExecutionSimulator`（`execute_order` 形参名/返回值冲突 **+** 缺 `trade_log`，两处冲突独立）、`PositionTracker`↔`IPositionTracker`（`get_snapshots`）、`FactorPipeline`↔`IFactorPipeline`（缺 `process_single`）、`FactorCombiner`↔`IFactorCombiner`（缺 `combine_single`）；后两个成员**全仓 0 调用**（仅接口声明） | E2 `mypy %TEMP%\p007b_proto_conform.py` → **4 errors**；E3 `core/factor.py:43,476` 仅有 `process`/`combine`；E1 `Grep "process_single"` 与 `Grep "combine_single"` 均仅命中 `interfaces.py:139,161` |
| P28 | `core/__init__.py` 为空（TD-1.2 / ADR-016 显式移除便利导出）→ `core.interfaces` 非对外导出，协议变更的外部爆炸半径 = 0 | E3 `core/__init__.py:1-11` |
| P29 | 协议实现者仅 4 个：`core/tracker.py::PositionTracker`、`core/execution.py::ExecutionSimulator`、`tests/test_decoupled_engine.py::MockPositionTracker`、`MockExecutionSimulator`；Mock 的 `get_snapshots() -> list`（=`list[Any]`，兼容）与 `trade_log = self`（`Any`，兼容）均不受协议修正影响 | E1 逐类 Grep（4 个类定义，其余 0 命中）；E3 `tests/test_decoupled_engine.py:143-148,192-239` |
| P30 | `core/` 全部未注解函数仅 **4 个**：`engine_v2.setup`（85 行）、`engine_v2._precompute_factors`（25 行）、`data_v3._build_maps`（4 行）、`engine_v3_vector.decorator`（2 行）；全部注解后新增 **9** 条（= `--check-untyped-defs` 增量） | E1 `%TEMP%\p007b_untyped.py`（AST 扫描）；R-2 / R-3 |
| P31 | **CI 的 mypy 步骤永不失败**：`.github/workflows/tests.yml:45-46` 为 `mypy core/ --ignore-missing-imports --no-error-summary` 加短路兜底（命令尾部 `&#124;&#124; true`），且参数与门禁不同（无 `--explicit-package-bases`）→ Q4 的门禁转绿**只在本地 Spec_Runner 生效** | E3 `tests.yml:45-46` |
| P32 | 门禁 `mypy-check` 命令 = `mypy --explicit-package-bases core`；`verdict` 为 exit code 的机械映射 | E3 `scripts/spec_runner_adapter.py:61,67` |
| P33 | Q1 行为变更的可达面：`examples/` **9 处** `factor_files` 全部非空；`cli.py` 缺省为 `["factor_value.pkl"]`；`tests/` 无空 `factor_files` 用例（37 行命中全部非空） | E1 R-6 / R-7；E3 `cli.py:47` |

### 12.2 复算命令表（R7 同构）

| ID | 命令 | 用途 |
|----|------|------|
| R-1 | `%PY312% -m mypy --explicit-package-bases core` | 93 / 3 files |
| R-2 | `%PY312% -m mypy --explicit-package-bases --check-untyped-defs core` | 102 / 4 files |
| R-3 | `%PY312% %TEMP%\p007b_untyped.py <repo>` | 4 个未注解函数的行号与行数 |
| R-4 | `%PY312% -m mypy --explicit-package-bases %TEMP%\p007b_proto_conform.py` | 4 处协议不符合 |
| R-5 | `%PY312% %TEMP%\p007b_zero_signal.py` | 零信号在等权/最小方差下的行为 |
| R-6 | `Grep pattern="factor_files" path=tests` | 37 行 / 10 文件 |
| R-7 | `Grep pattern="factor_files" path=examples` | 9 处 |
| R-8 | `Read .github/workflows/tests.yml` | CI mypy 步骤原文 |

### 12.3 Type-1 / Type-2 判定

| 议题 | 判定 | 依据 |
|------|------|------|
| Q1 A-1 空因子处理 | **Type-1** | 改变 `setup()` 的 raised exceptions 与 side effects（PEP 387 把「raised exceptions of a function」列为 public API，A18） |
| Q2 协议修正 | **Type-1** | 变更共享契约（`core/interfaces.py`）；虽无运行时影响，但改变「谁是合法实现」的真值源（A7/A18） |
| Q3 `setup()` 盲区 | **Type-1** | 打开检查范围 + 需追加 3 处跨模块契约决策（X1/X2 + 2 个缺失方法，P27） |
| Q4 关闭 U-006 | **Type-2** | 仅台账状态与门禁读数；可逆、无常驻副作用；矩阵不适用，改决策记录（§12.7） |

### 12.4 Q1 决策矩阵（A-1：`factor_files` 为空）

| 维度 | 选项 A：fail-fast（`setup()` 抛 `ValueError`） | 选项 B：零信号回退（全 0 信号） | 选项 C：空仓模式（跳过再平衡） |
|------|------|------|------|
| **成本** | 改 3 行（P25）+ 1 个测试（E3；2026-11-09） | 改 4 行 + 1 测试（E3；2026-11-09） | 改 ~8 行（`_precompute_factors` + `run`/`_execute_rebalance` 守卫）+ 1 测试（E3；2026-11-09） |
| **收益** | 消除 A-1 的 **7** 条 error（R-1）且错误在 `setup()` 立即暴露；与 `config.validate()` 口径一致（E3 `core/config.py:392-394`） | 消除 **7** 条 error（R-1）；不抛错 | 消除 **7** 条 error（R-1）；不抛错且不建仓 |
| **可维护性** | 契约单一：空因子=配置错误，无隐式分支（E3；2026-11-09） | 需长期解释「零信号」语义；且非等权优化器下**仍会建仓**（E2 R-5） | 需维护「无信号模式」第三态；与「因子回测引擎」定位冲突 |
| **兼容** | **行为变更**：空因子调用方由「静默空结果」变为 `ValueError`；PEP 387 明示「reasonable bug fixes」可豁免（A18）；可达面仅库方式构造（P33），示例/CLI 不受影响（R-6/R-7） | 无异常；默认 `equal_weight` 下无交易（E2 R-5） | 无异常；无交易 |
| **升级潜力** | 未来可显式新增「无因子模式」开关，语义清晰（E3；2026-11-09） | 零信号可作「现金模式」雏形，但须先给 3 个非等权优化器补滤零（E3 `portfolio.py:214-218`） | 可直接演进为「纯现金/基准」模式 |
| **短期** | 最小（3 行） | 小（4 行） | 中（8 行 + 守卫面） |
| **长期** | 最好：杜绝静默空回测（A17「Errors should never pass silently」） | 最差：非等权下建立任意组合（E2 R-5 实测 `['000001','000002']` 权重和 1.0） | 中：安全但语义隐晦，且新增分支需长期测 |

**Q1 倾向**：**A（fail-fast）**。理由：唯一同时满足「消除 7 条 error」「不产生任意组合」「错误可见」三项的方案；B 的「安全」只在默认优化器成立（E2 反例），C 增加第三态且无必要。

### 12.5 Q2 决策矩阵（协议修正）

| 维度 | 选项 A：最小真实化（`get_snapshots` + `trade_log`） | 选项 B：engine 侧 `cast` | 选项 C：4 个协议全面真实化 |
|------|------|------|------|
| **成本** | `interfaces.py` **+4 行**（`TYPE_CHECKING` 导入 + 2 处签名）（E3；2026-11-09） | `engine_v2.py` **+2 行** `cast`（E3；2026-11-09） | A + 修 `execute_order` 签名 + 补 `process_single`/`combine_single`（或删协议成员），**~20-40 行 / 3 文件**（E3 P27） |
| **收益** | 清 **2** 条（B-1/B-2）（R-1）；`PositionTracker` 恢复满足自身协议（E2 R-4 前两项） | 清 **2** 条；零接口改动 | 清 **2** 条 + 为 Q3 铺路（4 处不符合全清，R-4） |
| **可维护性** | 契约与实现一致；后续实现者拿到正确约束（A7） | 契约缺陷固化在接口层，任何新消费者继续踩（A3「cast 不做运行时检查」） | 最真实；但需决定「补方法」还是「删协议成员」，两者都改 API 面 |
| **兼容** | **0 运行时影响**；4 个实现者中 Mock 均兼容（`list[Any]` / `Any`，P29） | 0 运行时影响 | 补方法=**新增 2 个无调用方的公共方法**（API 扩面 + 死代码）；删成员=契约收窄（0 调用方，无破坏，但永久失去该约束） |
| **升级潜力** | 中：仍留 2 处不符合（P27） | 低：类型系统继续失真 | 高：Q3 的前置条件 |
| **短期** | 最小（4 行） | 最小（2 行） | 中（20-40 行） |
| **长期** | 中：契约只真一半 | 差：谎言被固化 | 最好，但应另立批次（涉及 API 面） |

**Q2 倾向**：**A（最小真实化）**。理由：只修与 93 基线直接相关的 2 处、零运行时影响、Mock 全兼容；C 虽更彻底，但「补两个公共方法」属于 API 扩面，超出 mypy 清理批次（P27 已把 C 的成本量化）。

### 12.6 Q3 决策矩阵（`setup()` 盲区）

| 维度 | 选项 A：不打开（保留盲区） | 选项 B：注解 `setup` 并修 6 条 | 选项 C：注解全部 4 个未注解函数（9 条） |
|------|------|------|------|
| **成本** | 0 行（E3；2026-11-09） | **1 行注解 + 6 条修复**：仅 1 条由 Q2-A 消除（231 `get_snapshots`）；余 5 条需动 `filter/`（185）、`core/factor.py`（194×2、201）、`interfaces.py`（224 `execute_order` 签名）、`engine_v2.py`（259 局部别名）→ **4 文件**（E3；R-3/R-4） | B + `data_v3._build_maps` 注解（2 条）→ **5 文件**（R-2/R-3） |
| **收益** | 基线可从 93 → 0，批次收敛（E1 R-1） | 消除 `setup()` 盲区（85 行）；暴露 **6** 条未检查错误（含 4 处协议不符合，P27） | 消除 `core/` 全部盲区（116 行）；`--check-untyped-defs` 增量归零（R-2） |
| **可维护性** | 盲区长期存在；`setup()` 内错误只能靠集成测试发现（A19：官方建议增量迁移） | 盲区消失，但把 **5** 处跨模块契约决策塞进 mypy 批次，审查面变大 | 最好，但同上且再增 `data_v3` 面 |
| **兼容** | 0 影响 | 仅注解，无运行时影响；但 `filter/` 的 `UniverseConfig`↔`UniverseFilterConfig` 适配（X1）可能改变默认过滤行为 → **有语义风险** | 同 B + `data_v3` 的 `dates/stocks` 非空假设需补守卫 |
| **升级潜力** | 低：无法推进到更严格 mypy | 中：为严格模式铺路 | 高：接近 `--check-untyped-defs` 全绿 |
| **短期** | 最小 | 中（4 文件） | 中大（5 文件） |
| **长期** | 差：技术债留在最核心的装配函数 | 中：需单独批次兜底 X1/X2 | 好，但应独立立项 |

**Q3 倾向**：**A（不打开）**。理由：`setup()` 的 6 条修复里只有 1 条能靠 Q2-A 顺带清掉（231），其余 5 条是**跨模块契约决策**（X1 配置语义、X2 参数过窄、2 个无调用方的缺失方法、`execute_order` 签名），在 mypy 批次内做会同时改变行为面与审查边界；官方亦建议增量迁移（A19）。该盲区以四元块登记（§12.8 U-3）。

### 12.7 Q4 决策记录（Type-2，不启动矩阵）

| 维度 | 选项 A：本批关闭 U-006 | 选项 B：保持开启 |
|------|------|------|
| **成本** | 台账 2 行 + CHECKLIST 记录门禁 verdict（E3；2026-11-09） | 0 |
| **收益** | U-006 判据「`mypy-check` 门禁转绿（`core` 0 errors）」可机械达成（E3 `PROGRESS.md:86` + R-1/R-8） | 无 |
| **兼容** | 无运行时影响；CI 不感知（P31：CI mypy 步骤带短路兜底，永不失败） | 无 |
| **维护** | 防止「基线永远 fail」常态化；若实际 0 仍挂 fail，会制造虚假基线 | 基线继续失真 |
| **结论（倾向）** | **A**：仅当 Q1-Q3 后 `R-1` 实测 0 才关闭；关闭时同步声明「CI 未强制 mypy（P31），本项只代表本地门禁」 | — |

> 反模式校验：关闭 U-006 不得靠新增裸 `# type: ignore` 或放宽 `pyproject.toml`；mypy 官方建议 `ignore-without-code` 以保证「只静默预期错误」（A21）。
>
> **裁决更新（2026-11-09，用户）**：选择 **B 保持开启**，本表「结论（倾向）A」为裁决前记录，保留以资对照；最终记录见 §13.5 U-4。

### 12.8 收敛出口

**本轮结论**：推荐 **Q1-A / Q2-A / Q3-A / Q4-A**（四者组合后 `core` 预期 93 → 0，diff 约 100 行、4 文件、新增 1-2 个测试）。最终裁决权在用户（人工裁决点），本补充调研不代替裁决。
> **后续**：Q4 已被用户裁决为 **B 保持开启**（2026-11-09）；Q1-Q3 在 §13 补入社区案例与学术锚点后方向不变。以 §13.5 为最新收敛出口。

**未闭合的未决项**（四元块）：

- **U-1（= Q1）空因子处理策略**
  - **判据**：`BacktestConfig(factor_files=[])` + `setup()` 的行为被测试锁定（抛 `ValueError` 或空仓）
  - **触发条件**：Step 3 DESIGN 启动前
  - **当前倾向**：A fail-fast
  - **证据等级**：E1（R-1）+ E2（R-5）+ E3
- **U-2（= Q2）协议修正范围**
  - **判据**：`mypy %TEMP%\p007b_proto_conform.py` 中 `IPositionTracker` / `IExecutionSimulator` 两项转为通过
  - **触发条件**：Step 3 DESIGN 启动前
  - **当前倾向**：A 最小真实化
  - **证据等级**：E2（R-4）+ E3
- **U-3（= Q3）`setup()` 盲区**
  - **判据**：`mypy --explicit-package-bases core` 与 `--check-untyped-defs core` 差值（**102 − 93 = 9**，R-1/R-2）是否收敛
  - **触发条件**：下一批次启动，或 `core` 基线需进一步收紧时
  - **当前倾向**：A 不打开（另立批次）
  - **证据等级**：E1（R-2/R-3）
- **U-4（= Q4）U-006 关闭**
  - **判据**：R-1 输出 `Found 0 errors` 且门禁 `mypy-check` verdict=pass
  - **触发条件**：下一批次启动时重新评估
  - **当前倾向**：**已裁决：B 保持开启**（用户，2026-11-09；见 §13.5）
  - **证据等级**：E1（R-1/R-8）

### 12.9 来源清单补充

| # | 来源 | Layer | 读取日 | 版本 / ID | 用途 |
|---|------|-------|--------|-----------|------|
| 17 | PEP 20 · The Zen of Python | T1 | 2026-11-09 | Active，2004-08-19（页面 Last modified 2025-02-01） | A17「Errors should never pass silently. Unless explicitly silenced.」→ Q1 |
| 18 | PEP 387 · Backwards Compatibility Policy | T1 | 2026-11-09 | Active，2009-06-18 | A18 public API 含「side effects, and raised exceptions」；「reasonable bug fixes」豁免 → Q1/Q2 |
| 19 | mypy docs · Getting started | T1 | 2026-11-09 | stable edition | A19「it's usually easier to migrate by incrementally adding type hints to your code rather than adding them all at once」→ Q3 |
| 20 | Semantic Versioning 2.0.0 | T1 | 2026-11-09 | 2.0.0 | A20 MAJOR=incompatible API / MINOR=backward compatible → Q1/Q2 影响分级 |
| 21 | mypy docs · Error codes for optional checks §ignore-without-code | T1 | 2026-11-09 | stable edition | A21「ensures that only the expected errors are silenced」→ Q4 反 masking |
| 22 | `F:\Spec_Workflow\spec\templates\DECISION_MATRIX_TEMPLATE.md` | T1（规范） | 2026-11-09 | v1.0（2026-09-30） | 七维矩阵形态 |
| 23 | `F:\Spec_Workflow\SPEC_PROCESS.md` §迭代收敛与未决项登记 | T1（规范） | 2026-11-09 | v1.7.2 L431-467 | Type-1/Type-2 取证要求、四元块 |

> **未验证项**：无新增。R-3/R-4/R-5 的脚本在 `%TEMP%` 未入仓（`[未入仓-不可重放]`，命令见 §12.2，本会话内已复算）。

---

## 13. Q1-Q3 深度分析：社区案例 + 学术锚点（2026-11-09）

> **触发**：用户在 §12 裁决对话中回答——Q1/Q2/Q3「先搜索社区案例 学术锚点 详细分析处理方案」；Q4「B 保持开启」（已裁决，见 §13.5）。
> **与 §12 的关系**：§12 已给出七维矩阵与成本读数；§13 不推翻矩阵，只补三件事——(a) 外部事实锚点 A22-A30；(b) 每个候选的「支持 / 反驳」逐条对账；(c) 落到代码位置的实施方案与残余风险。
> **证据等级**：A22-A28 为 T1/T2（官方规范 / 同行评议或 IEEE Software 专栏 / 官方文档）；A29-A30 为 T3 社区问答，仅作旁证，不单独承载结论。
> **读码绑定**：`762ff5f`（本节所有 E3 行号的 commit）。

### 13.1 新增外部锚点（A22-A30）

| ID | 来源 | Layer | 原文要点（逐字） | 用于 |
|----|------|-------|------------------|------|
| A22 | PEP 544 · Protocols: Structural subtyping | T1（Final，2017-03-05，Python 3.8） | L279「The attributes (variables and methods) of a protocol that are mandatory for other class in order to be considered a structural subtype are called protocol members.」；L290「a `close()` method that has a compatible signature」；L306「a `close()` method with a compatible type signature」；L310「If any parameters of a protocol method are not annotated, then their types are assumed to be `Any`」 | Q2 / Q3 |
| A23 | Liskov & Wing 1994 · A behavioral notion of subtyping | T1（学术，TOPLAS 16(6):1811-1841，1994-11，DOI `10.1145/197320.197383`） | 摘要「any property proved about supertype objects also holds for its subtype objects」 | Q2 |
| A24 | mypy docs · Using mypy with an existing codebase | T1（stable edition） | 「pick a subset of your codebase (say, 5,000 to 50,000 lines) and get mypy to run successfully only on this subset at first, *before adding annotations*」；「Mypy is designed to support gradual typing … so it's okay to leave some of these modules unannotated」；「you may want to enable `disallow_untyped_defs` for modules which you've completed annotations for」 | Q3 |
| A25 | Phipps-Costin / Anderson / Greenberg / Guha 2021 · Solver-based Gradual Type Migration | T1（学术，arXiv `2109.05049`，2021-09-10，cs.PL） | 「We argue that the type migration problem involves fundamental compromises: optimizing for a single goal often comes at the expense of others」（目标含 precision / compatibility with unmigrated code / preserving semantics） | Q3 |
| A26 | de Pádua & Shang 2017 · Studying the Prevalence of Exception Handling Anti-Patterns | T1（学术，arXiv `1704.00778`，2017-04-03，cs.SE） | 「only a few anti-patterns (e.g. Unhandled Exceptions, Catch Generic, Unreachable Handler, Over-catch, and Destructive Wrapping) can be commonly identified」 | Q1 |
| A27 | Fowler 2004 · Fail Fast | T2（IEEE Software 专栏，2004-09/10） | 配置缺属性时「return null or a default value」→「failing slowly」；「A system that fails fast does exactly the opposite: when a problem occurs, it fails immediately and visibly」 | Q1 |
| A28 | pydantic docs · Settings management | T1（官方文档，latest） | required 字段（无默认）缺失时在构造期抛 `ValidationError`，报「1 validation error … Field required [type=missing]」；默认值只用于 optional 字段 | Q1 |
| A29 | Stack Overflow 77002238 · Type checking python function signatures of Protocol subclass with mypy | T3（问答，2 答案，2023-08-29） | accepted 答案「you weren't type annotating your method, which essentially tells mypy 'don't check this'」；另一答案「The `publish` method *must have the same signature in the class as in the protocol* to conform」 | Q2 / Q3 |
| A30 | Stack Overflow 68471392 · Can I inform mypy that an expression will not return an Optional? | T3（问答，accepted 21 分，2021-07） | 「You can tell it 'no, I'm very confident that will not be the case' by doing an `assert` to that effect」 | Q1 / Q2 |

### 13.2 Q1：空 `factor_files` 的详细处理方案

#### 13.2.1 补两条 §12 未说清的事实（E3 @`762ff5f`）

| ID | 事实 | 证据 | 对 §12 的影响 |
|----|------|------|----------------|
| P34 | `BacktestConfig.validate()` 对空因子**只返回错误字符串**（`core/config.py:384-394`，返回 `list[str]`），且 `setup()` **从未调用** `validate()`（`core/engine_v2.py:163-247` 无该调用） | E3 @`762ff5f` | §12.4「与 `config.validate()` 口径一致」的准确含义是**语义一致**，不是「已有执行」；Q1-A 是新增 3 行守卫，不是接线 |
| P35 | `BacktestConfig()` 默认 `factor_files=[]`（`core/config.py:345`），但产品路径全部显式非空：`cli.py:47` 缺省 `["factor_value.pkl"]`，examples 9 处非空、tests 37 行非空（P33） | E3 @`762ff5f` + E1 R-6/R-7 | 「默认构造 + 直接 `setup()`」是唯一触发路径（库方式），兼容面可控 |

#### 13.2.2 社区案例对账

两个独立来源给出同一条规则，且都恰好以「配置项缺失」为例：

- **A27（Fowler，T2）**：缺配置项时返回默认值是「failing slowly」——程序继续跑，但在别处以奇怪方式失败；fail-fast 则在问题发生处立即、可见地失败。
- **A28（pydantic，T1）**：required 的判定标准就是「没有默认值」；缺失在**构造期**抛 `ValidationError`；默认值只用于 optional 字段。

对本仓的直接含义：`factor_files` 已被 `validate()` 声明为 required（P34），对它做「零信号回退」正是 A27 批评的「给 required 配置发明默认值」。**社区锚点不支持 B/C，只支持 A。**

> 边界声明：A27/A28 支撑的是「required 值缺失应报错」这一原则，不等于「任何配置缺失都必须抛错」。`DataManager` 对停牌/行业/ST 等**可选**辅助数据保留安全默认值（P-010 已裁决），二者不冲突——区别在 required 与 optional。

#### 13.2.3 学术 / 规范锚点对账

- **A17（PEP 20）**「Errors should never pass silently. Unless explicitly silenced.」——当前 `logger.warning` + `return` 是「显式静默」，但静默的产品后果是空回测，不是可接受的降级。
- **A18（PEP 387）**：public API 包含「the return value, side effects, and raised exceptions of a function」，且「This does not preclude changes from reasonable bug fixes」。→ Q1-A 的行为变更属于 reasonable bug fix 范畴，但**仍须披露**（CHANGELOG + DESIGN）。
- **A26（arXiv 1704.00778）**：`Catch Generic` / `Over-catch` / `Destructive Wrapping` 是跨项目高频反模式。本仓 `core/engine_v2.py:292-294` 的 `except Exception as e: logger.error(...); continue` 是典型 `Catch Generic`——A-1 的 7 条 TypeError 每天被它吞掉（P9 实测 100 条 ERROR 后返回空结果）。**任何保留「空信号继续跑」的 B/C 方案都继续依赖这条反模式。**

#### 13.2.4 三候选逐条对账

| 候选 | 支持锚点 | 反驳锚点 / 本仓反证 | 判定 |
|------|----------|----------------------|------|
| A fail-fast | A27 / A28 / A17 / A18 | 无（唯一代价是 breaking change，A18 允许 reasonable bug fix） | **成立** |
| B 零信号回退 | 无（未找到「required 配置用零值兜底」的权威支持） | A27 明确归类为 failing slowly；E2 R-5：`MinVarianceOptimizer` 不滤零 → 建任意组合（`['000001','000002']` 权重和 1.0） | 不成立 |
| C 空仓模式 | 无 | 新增第三态（无信号模式）但触发路径在产品侧不可达（P35）；且「空回测成功返回」与 B 同样让调用方误读为「策略无信号」 | 不成立 |

#### 13.2.5 实施方案（Q1-A，落点精确到行）

1. **行为修复（3 行）**：`core/engine_v2.py:252-254`
   - `logger.warning("未指定因子文件"); return` → `raise ValueError("factor_files 为空：BacktestEngineV2 需要至少一个因子文件（见 BacktestConfig.validate）；如需空仓基准请使用显式基准模式")`
   - 放在 `_precompute_factors` 而非 `setup()` 开头：它是该前置条件的归属者，直接调用它的脚本/测试同样被覆盖。
   - 不改为调用 `cfg.validate()`：它返回 `list[str]` 而不抛（P34），且会连带改变 `data_dir` 等其它校验的时机，超出本批。
2. **窄化（7 条 → 0）**：7 处引用分布在 3 个方法（L321/322 `_process_trading_day`、L478/481 `_try_fallback_order`、L522/527/532 `_execute_rebalance`）。
   - 推荐新增私有 property：`@property def _signal(self) -> pd.DataFrame: assert self._composite_signal is not None; return self._composite_signal`，7 处改引用 → **1 个 assert 覆盖 7 处**。
   - 备选：每方法「局部别名 + assert」（S1），3 个 assert。
   - 两种写法都只是**断言**（A30：assert 是「我很确信」的声明，不是证明）；真正的保证来自步骤 1。
3. **测试（1 个用例）**：`BacktestConfig(factor_files=[])` + `engine.setup()` → `pytest.raises(ValueError, match="factor_files")`；并断言 `engine._composite_signal is None`（未进入计算）。
4. **披露**：CHANGELOG `Changed`；DESIGN 记录 breaking change 与可达面。

#### 13.2.6 残余风险

- 外部库方式脚本若依赖「空因子 → 空结果」会由静默变为异常；P35 已证 examples/CLI 不受影响。
- `-O` 下 property 的 assert 被剥离 → 返回 `None`；但步骤 1 使 `setup()` 先失败，仅在「绕过 setup 直接调用内部方法」时不成立（非公共 API）。

### 13.3 Q2：协议修正范围的详细分析

#### 13.3.1 形式要求（A22 / A23 / A29）

- A22 L279：protocol members 是「mandatory」；L290/L306：实现必须提供「compatible signature / compatible type signature」；L310：协议参数未注解 → `Any`。
- A23：行为子类型要求「supertypes 的性质在 subtypes 上仍成立」。`get_snapshots() -> list[dict]` 声明的是「元素为 dict 的列表」，而 `PositionTracker` 返回 `list[PortfolioSnapshot]`（`@dataclass`，`core/tracker.py:133-135`，**不是 dict**）→ 二者不存在子类型关系；运行时能跑只是鸭子类型的偶然。
- A29：SO 77002238 的 accepted 答案指出「未注解方法 = 告诉 mypy 不要检查」；另一答案「方法签名必须与协议一致」。这两条正好解释本仓为什么 93 基线里看不到 `execute_order` 冲突——`setup()` 未注解（P30），冲突被盲区吞掉。

#### 13.3.2 三个成员的准确定位（E3 @`762ff5f`）

| 成员 | 协议声明 | 实现 | 冲突性质 |
|------|----------|------|----------|
| `get_snapshots` | `list[dict]`（`interfaces.py:271`） | `list[PortfolioSnapshot]`（`tracker.py:350`） | 协议**写错**；实现是对的 |
| `trade_log` | 未声明（`interfaces.py:197-238`） | `TradeLog`（`execution.py:175`），有 `get_trades_df() -> pd.DataFrame`（`execution.py:79`） | 协议**比实现窄**（漏声明） |
| `execute_order` | 第 5 参数名 `price`（`interfaces.py:203-211`） | 第 5 参数名 `open_price`（`execution.py:250-260`） | **名不符**；当前被 `setup()` 盲区隐藏（Q3 面） |

#### 13.3.3 三候选逐条对账

| 候选 | 支持锚点 | 反驳锚点 / 本仓反证 | 判定 |
|------|----------|----------------------|------|
| A 最小真实化（2 条） | A22 / A23 / A29；`PortfolioSnapshot` 是 dataclass（E3）；`TradeLog.get_trades_df` 存在（E3） | 仍留 `execute_order` 名冲突（属 Q3 面，见 U-3） | **成立** |
| B engine 侧 cast | 无 | A22/A23：cast 不校验成员；A3（mypy 文档）：cast 不做运行时检查 → 把契约缺陷固化在接口层 | 不成立 |
| C 4 个协议全面真实化 | A22（最彻底） | 「补 `process_single` / `combine_single`」= 新增 2 个**零调用方**公共方法（API 扩面 + 死代码）；「删协议成员」= 契约收窄；两者都是 API 决策而非 mypy 决策。A25 的 fundamental compromises 同样适用：精度提升以兼容/语义面为代价 | 不成立（另立批次） |

#### 13.3.4 实施方案（Q2-A，含 1 处细化）

1. `core/interfaces.py` 顶部：`if TYPE_CHECKING: from core.tracker import PortfolioSnapshot`（`tracker.py` 只 import `core.execution`，无运行时环，E3）。
2. `interfaces.py:271` → `def get_snapshots(self) -> list["PortfolioSnapshot"]:`（+1 行导入、+1 行签名改动）。
3. `IExecutionSimulator` 增补 `trade_log`。**细化**：不用 `trade_log: Any`（那只是换个方式闭嘴），改为最小协议：

   ```python
   class ITradeLog(Protocol):
       def get_trades_df(self) -> pd.DataFrame: ...
   ```

   `IExecutionSimulator.trade_log: ITradeLog`。`TradeLog` 结构上满足（E3 `execution.py:52,79`）；4 个实现者中 Mock 用 `trade_log = self`（`Any`）仍兼容（P29）。
   成本从 §12.5 的「+4 行」调整为 **+9 行**（1 协议 + 2 成员 + 2 导入 + 注释）；收益多一条：不是把缺陷换成 `Any`。
4. 验证：`mypy --explicit-package-bases core` 的 B-1/B-2 消失；`p007b_proto_conform.py` 前两项转通过（R-4）。

#### 13.3.5 残余

- `execute_order` 的名不符仍存在，且只有打开 `setup()` 才会暴露；登记为 U-3 的一部分，不在 Q2 处理。
- `ITradeLog` 的结构一致性只在**有注解的赋值点**被检查；`setup()` 未注解时该检查不存在（A29 的同一机制）。因此本项的价值是「契约变真 + 未来 typed 消费方受检」，当前不会新增静态保证——这一点在 DESIGN 中须如实写明。
- `interfaces.py` 通过 `TYPE_CHECKING` 依赖 `core.tracker` 的具体类型，属于「接口依赖实现」的方向瑕疵；替代方案是把 `PortfolioSnapshot` 上移到 `interfaces.py`（或抽 `core/types.py`），但那会改 3 个文件的 import，超出本批。

### 13.4 Q3：`setup()` 盲区的详细分析

#### 13.4.1 盲区的规模与构成（E1/E3）

- `core/` 全部未注解函数 4 个（P30）：`engine_v2.setup` 85 行、`engine_v2._precompute_factors` 25 行、`data_v3._build_maps` 4 行、`engine_v3_vector.decorator` 2 行。
- `--check-untyped-defs` 增量 9 条（B4），其中 `setup()` 相关 6 条（§12.6）：
  1. L185 `UniverseFilter(self.dm, self.cfg.universe)`：`UniverseConfig` ≠ `UniverseFilterConfig`（X1，**语义陷阱**，不是纯类型问题）
  2. L194 / L201 两处 `FactorPipeline`：声明 `DataManager` 具体类，引擎持有 `IDataManager`（X2）
  3. L224 `ExecutionSimulator` ↔ `IExecutionSimulator`：`execute_order` 参数名冲突（§13.3.2）
  4. L231 `get_snapshots`（Q2-A 顺带消除）
  5. L259 `_precompute_factors` 内 `self.dm` 窄化（局部别名即可）

#### 13.4.2 锚点对账（这一问的锚点决定「时机」，不决定「对错」）

- A24（mypy 官方）：**Start small**——先在子集上让 mypy 通过，**再**加注解；「it's okay to leave some of these modules unannotated」；严格项按**模块**逐步启用。→ 支持「本轮不打开，另立批次」。
- A24 同时给出反向证据：`check_untyped_defs` 被列为「Strongly recommend enabling this one as soon as you can」，且要求「run mypy as part of your CI」。→ 官方并不主张永久保留盲区；本仓 CI 的 mypy 步骤还带短路兜底（P31），因此打开盲区必须配 CI 收紧，否则只是本地多 9 条。
- A25（arXiv 2109.05049）：类型迁移存在「fundamental compromises」——精度 / 与未迁移代码的兼容 / **保持原程序语义**三者互相拉扯。本仓 5 条残余里有 3 条（X1、X2、`execute_order`）是**语义/契约决策**，不是加注解能自动解决的；把它们塞进 mypy 批次，正是 A25 所说的「优化单一目标、牺牲其它目标」。
- A29：未注解方法不被检查——这解释了盲区为何存在，也说明盲区是**真实风险**（不只是数字）。因此结论不是「永远不打开」，而是「打开需要独立的范围与验收」。

#### 13.4.3 三候选逐条对账

| 候选 | 支持锚点 | 反驳锚点 / 本仓反证 | 判定 |
|------|----------|----------------------|------|
| A 不打开（本批） | A24 Start small / 按模块收紧；A25 compromises | 盲区风险仍在（A29）；但已用四元块 U-3 显式登记 | **成立** |
| B 注解 `setup` 并修 6 条 | A24「as soon as you can」；A29（消除盲区） | 需同时决策 X1（配置语义）、X2（参数放宽）、`execute_order`（改名 = 公共 API 变更）→ 4 文件、3 个语义决策；违反「单一批次单一目标」 | 不成立（本批） |
| C 注解全部 4 个函数（9 条） | 最彻底 | = B + `data_v3._build_maps` 的 `dates/stocks` 非空假设（X3，需行为守卫）；审查面再扩 1 文件 | 不成立（本批） |

#### 13.4.4 若未来选 B 的实施顺序（供 U-3 触发时直接执行）

1. `def setup(self) -> None:`（1 行）→ 先看新增 6 条的真实清单（应与 `--check-untyped-defs` 一致）。
2. 先做无争议项：L259 局部别名 + L231（若 Q2-A 已落地则自动消失）。
3. 再做 3 个语义决策，各自单独评审：
   - X1：`UniverseFilter` 接受哪套配置（适配器 vs 统一配置类）——必须先解决 `exclude_stock_prefixes` 的 list/bool 语义冲突（§8）；
   - X2：`FactorPipeline` 参数放宽到 `IDataManager`；
   - `execute_order`：改实现参数名 `open_price` → `price`（先检查是否有 `open_price=` 关键字调用方），或改协议参数名。
4. 最后在 `pyproject.toml` 按模块启用 `check_untyped_defs`（A24 的 per-module 做法），并同步 CI（P31）。

### 13.5 收敛出口（更新 §12.8）

**Q4 已裁决（2026-11-09，用户）**：**B 保持开启**。U-006 的判据「`mypy-check` 门禁转绿」不在本批关闭；本批只把 93 → 0 并记录门禁 verdict 变化，U-006 留待下一批次裁决。

**Q1-Q3 已裁决（2026-11-09，用户）**：**Q1 = A fail-fast / Q2 = A 最小真实化 / Q3 = A 不打开**。三项与 §13.2-§13.4 的推荐一致，Step 3 DESIGN 的输入自此确定。

**Q1-Q3 的推荐（加入外部锚点后方向不变）**：

| 议题 | 推荐 | 锚点支持 | 与 §12 的差异 |
|------|------|----------|----------------|
| Q1 | **A fail-fast** | A17 / A18 / A26 / A27 / A28 | 补 P34（`validate` 未被调用）、P35（可达面）；细化落点与 property 方案 |
| Q2 | **A 最小真实化** | A22 / A23 / A29 | `trade_log` 由 `Any` 细化为 `ITradeLog` 最小协议（+9 行而非 +4 行） |
| Q3 | **A 不打开** | A24 / A25 / A29 | 补「未来 B 的实施顺序」4 步；明确 A24 的反向证据（`check_untyped_defs` 应尽早） |

**未闭合项（四元块，更新 §12.8）**：

- **U-1（= Q1）空因子处理策略**
  - **判据**：`BacktestConfig(factor_files=[])` + `setup()` 抛 `ValueError`，且测试锁定
  - **触发条件**：Step 3 DESIGN 启动前
  - **当前倾向**：**已裁决：A fail-fast（用户，2026-11-09）**（证据：A27/A28 + P34/P35）
  - **证据等级**：E1（R-1）+ E2（R-5）+ E3 + T1/T2（A17/A18/A27/A28）
- **U-2（= Q2）协议修正范围**
  - **判据**：`mypy %TEMP%\p007b_proto_conform.py` 中 `IPositionTracker` / `IExecutionSimulator` 两项转为通过
  - **触发条件**：Step 3 DESIGN 启动前
  - **当前倾向**：**已裁决：A 最小真实化 + `ITradeLog` 最小协议（用户，2026-11-09）**
  - **证据等级**：E2（R-4）+ E3 + T1/T3（A22/A23/A29）
- **U-3（= Q3）`setup()` 盲区**
  - **判据**：`mypy --explicit-package-bases core` 与 `--check-untyped-defs core` 差值（**102 − 93 = 9**，R-1/R-2）是否收敛
  - **触发条件**：下一批次启动，或 `core` 基线需进一步收紧时
  - **当前倾向**：**已裁决：A 不打开（另立批次，用户，2026-11-09）**；附「未来 B 的 4 步实施顺序」（§13.4.4）
  - **证据等级**：E1（R-2/R-3）+ T1/T3（A24/A25/A29）
  - **Step 6 注记（2026-11-10）**：层 B 的 Q2-A 将使 flag 下 `engine_v2.py:231` 转过（协议修正附带收益，E1 diff 实证）→ **批后残差 = 8**（engine_v2 6：L185/L194×2/L201/L224/L259 + data_v3 2）；本判据的重审基线以 8 为准
- **U-4（= Q4）U-006 关闭**
  - **判据**：R-1 输出 `Found 0 errors` 且门禁 `mypy-check` verdict=pass
  - **触发条件**：下一批次启动时重新评估
  - **当前倾向**：**已裁决：B 保持开启（用户，2026-11-09）**
  - **证据等级**：E1（R-1/R-8）

### 13.6 来源清单补充（24-32）

| # | 来源 | Layer | 读取日 | 版本 / ID | 用途 |
|---|------|-------|--------|-----------|------|
| 24 | PEP 544 · Protocols: Structural subtyping | T1 | 2026-11-09 | Final，2017-03-05，Python 3.8 | A22 |
| 25 | *A behavioral notion of subtyping*（Liskov & Wing） | T1（学术） | 2026-11-09 | DOI `10.1145/197320.197383`，TOPLAS 16(6):1811-1841，1994-11 | A23 |
| 26 | mypy docs · Using mypy with an existing codebase | T1 | 2026-11-09 | stable edition | A24 |
| 27 | *Solver-based Gradual Type Migration*（Phipps-Costin et al.） | T1（学术） | 2026-11-09 | arXiv `2109.05049`，2021-09-10 | A25 |
| 28 | *Studying the Prevalence of Exception Handling Anti-Patterns*（de Pádua & Shang） | T1（学术） | 2026-11-09 | arXiv `1704.00778`，2017-04-03 | A26 |
| 29 | Martin Fowler · Fail Fast | T2 | 2026-11-09 | IEEE Software，2004-09/10 | A27 |
| 30 | pydantic docs · Settings management | T1 | 2026-11-09 | latest | A28 |
| 31 | Stack Overflow 77002238 | T3 | 2026-11-09 | 2 答案，2023-08-29 | A29 |
| 32 | Stack Overflow 68471392 | T3 | 2026-11-09 | accepted 21 分，2021-07 | A30 |

> **未验证项**：无新增。A29/A30 为 T3，仅作旁证；其结论同时被 A22（PEP 544）与 A24（mypy 官方）覆盖。A28 的引用是「required 字段缺失 → 构造期 ValidationError」的官方示例行为，非本仓结论。

### 13.7 §13 引文核验（F4 形态）

> **执行时点**：§13 写入后的自查（2026-11-09）；**审查者**：单 Agent 自查（RULE-4）；**方式**：直取页面/API 后逐字比对，不依赖检索摘要。

| 锚点 | 验证方式 | 状态 |
|------|----------|------|
| A22 PEP 544 | WebFetch 直取 `peps.python.org/pep-0544/`；L279/L290/L306/L310 四处引文逐字命中 | 已验证（T1） |
| A23 Liskov & Wing 1994 | Crossref API `10.1145/197320.197383` 解析命中：TOPLAS 16(6):1811-1841，1994-11，摘要含所引句 | 已验证（T1） |
| A24 mypy existing codebase | WebFetch 直取 stable 页；「Start small」「gradual typing」「per-module `disallow_untyped_defs`」「CI」四处逐字命中 | 已验证（T1） |
| A25 arXiv 2109.05049 | WebFetch 直取 abs 页；标题/作者/日期/摘要「fundamental compromises」命中 | 已验证（T1） |
| A26 arXiv 1704.00778 | WebFetch 直取 abs 页；标题/作者/日期/反模式清单命中 | 已验证（T1） |
| A27 Fowler Fail Fast | WebFetch 直取 IEEE Software PDF 文本层；配置默认值例子与定义句命中 | 已验证（T2） |
| A28 pydantic Settings | WebFetch 直取文档；`Field required [type=missing]` 示例原文命中 | 已验证（T1） |
| A29 SO 77002238 | StackExchange API 直取 question + 2 answers；两条引文逐字命中 | 已验证（T3，旁证） |
| A30 SO 68471392 | StackExchange API 直取 answers；accepted 答案「assert」原句命中 | 已验证（T3，旁证） |

> **结论**：§13 未引入新的 P1/P2；外部锚点 9 条全部可追溯。A29/A30 的结论均另有 T1 锚点独立支撑（A22、A24），不构成单点依赖。
