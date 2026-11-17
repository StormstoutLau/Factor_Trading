# RESEARCH：P-037 类型门禁边界收口（U-P036-4 取证）

> **批次**: P-037 · **Step 1 调研** · 日期 2026-11-17 · 来源日期 2026-11-17（读取日）
> **判档**: **T1**（SPEC_PROCESS 判档规则 2 强制升级：把 `tools` / `examples` 纳入 CI mypy target = 变更门禁判据；即便结论为「不纳入」亦触达门禁真值面，禁止降 T3）
> **作者基座**: DeepSeek-V4.1-Flash（Step 2 Review 须异构，RULE-5）
> **上游台账**: U-P036-4（「`tools/` / `examples/` / `demo/` / `memory/` 是否纳入类型门禁」，P-036 Step 1 登记）
> **代码证据时点**: HEAD `ad7815d`（P-036 收口提交）
> **前置批次**: [P-036](SUMMARY_p036_mypy_check_surface_expansion.md) 已把门禁面从 `core` 扩至 **10 面**（`core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`），U-P036-4 是其显式登记的边界遗留

---

## 1. 批次目标与取证问题

用户指令：按首选方案执行 P-037「类型门禁边界收口」。本 Step 只做机械取证与定性，不做实现。

| # | 问题 | 本 Step 回答出口 |
|---|------|-----------------|
| Q1 | U-P036-4 的四个目录在门禁口径下各有多少错误？ | §3（三口径读数）+ §4（逐条清单） |
| Q2 | 触发条件「出现生产调用」是否成立？ | §2.3（grep 实证：**未成立**） |
| Q3 | 这些错误是注解卫生、U-a 窄化，还是真实缺陷？ | §4（9 簇分级）+ §5（E2 探针实锤 1 项真实缺陷） |
| Q4 | 纳入门禁的代价、边界与不做的后果？ | §6（方案矩阵 + 低效排除） |

---

## 2. 治理对象与现状

### 2.1 台账题干（U-P036-4）

> 「`tools/` / `examples/` / `demo/` / `memory/` 是否纳入类型门禁；本批未测（显式未覆盖项）」
> 触发条件：「任一目录出现生产调用」。

### 2.2 门禁现状（E1 读码 @`ad7815d`）

- `.github/workflows/tests.yml` L46 target = **10 面**（P-036 终态）。
- `scripts/spec_runner_adapter.py` L67 与之一一对应（双载体，`tests/test_p024_ci_gate_alignment.py` 强制）。
- `pyproject.toml [tool.mypy]`（L109-114）：`python_version = "3.10"` / `warn_return_any = true` / `disallow_untyped_defs = false` / `ignore_missing_imports = true`；**无 exclude 段**，无 `[[tool.mypy.overrides]]`（P-036 B3 已删）。

### 2.3 四目录实况（E1）

| 目录 | `.py` 文件数 | `__init__.py` | mypy 直检 | 结论 |
|------|-------------|---------------|-----------|------|
| `tools/` | **4**（`benchmark.py` / `cleanup_project.py` / `distillation_audit.py` / `ui_dashboard.py`） | 无 | **5 errors / 3 files（checked 4）** | 纳入候选 |
| `examples/` | **7**（`demo.py` / `full_backtest_demo.py` / `full_backtest_2020_2026.py` / `full_backtest_2020_2026_simple.py` / `run_backtest_minimal.py` / `run_full_backtest_fixed.py` / `run_single_backtest.py`） | 无 | **14 errors / 7 files（checked 7）** | 纳入候选 |
| `demo/` | **0** | — | `exit 2`（`There are no .py[i] files in directory 'demo'`） | **从题干剔除** |
| `memory/` | **0** | — | 同上 | **从题干剔除** |

> **题干收窄（本 Step 定论）**：U-P036-4 的四个目录中 `demo/` 与 `memory/` **不含任何 Python 文件**（非 Python 目录），纳入门禁无对象。实际范围 = `tools` + `examples`。

### 2.4 触发条件取证（E1，grep）

- 生产面（10 面全 `.py` + `cli.py`）对 `tools` / `examples` 的 import：**0 命中**。
- 仅 `tests/test_distillation_isolation.py` L267/L278/L295 引用 `from tools.distillation_audit import DistillationAuditor`（**测试引用**，非生产调用）。
- 结论：U-P036-4 的触发条件「任一目录出现生产调用」**未成立** → 本批属**主动扩做**，须用户裁决（用户已于 2026-11-17 选定本方向）。

### 2.5 依赖前置（E1，决定 CI 可行性）

`tools/` 与 `examples/` 的 import 全集 = **stdlib + numpy + pandas + 本仓 `core`/`filter`**；**无 streamlit / typer / 任何 `[web]` extra 依赖**。CI 的 `pip install ".[dev]"` 环境足够，无需新增依赖。

---

## 3. 取证环境与三口径读数

> 口径沿 P-036 D1 + F-S9-P036-2（CI 依赖未钉版本 → 必须三口径复跑）。

| 口径 | 环境 | `mypy --explicit-package-bases --check-untyped-defs tools examples` |
|------|------|--------------------------------------------------------------------|
| 本机 | py3.12 + numpy 2.4.6 + mypy 2.4.1 | **19 errors / 10 files（checked 11）** |
| CI 3.12 复刻（`%TEMP%\p036r2`） | py3.12 + **numpy 2.5.5** + mypy 2.4.1 | **19 errors / 10 files（checked 11）** |
| CI 3.10 复刻（`%TEMP%\p036r310`） | py3.10 + **numpy 2.2.6** + pandas 2.3.3 + mypy 2.4.1 | **20 errors / 10 files（checked 11）** |

**差异 1 条（3.10 独有）**：`examples/demo.py:79` `assignment`——`adj = adj / adj[-1:]` 在 numpy 2.2.6 桩下形状信息丢失（`ndarray[tuple[int,int]]` ← `ndarray[tuple[int,...]]`）。与 P-036 `f1fdab4` 的 `_spec.py:83` **同型**，修复手法可复用。

**结论口径**：本批红态以 **3.12 = 19 条**为基线，**3.10 追加 1 条**（验收时两口径都须 0）。

---

## 4. 逐条清单与根因分类（20 条 / 10 簇）

> **编号说明（Step 2 复审 F-05 订正）**：下表 **13 行 = 10 簇**——#7-#10 四行同属「`engine.dm` U-a 窄化」**1 簇**（7 条），其余每行 1 簇。

| # | 位置 | 错误码 | 根因 | 层 | 改法（零行为变更） |
|---|------|--------|------|----|-------------------|
| 1 | `tools/ui_dashboard.py:167` | return-value | `trace()` 声明 `-> ExecutionStep` 却在 `is_recording=False` 时 `return None`；唯一调用方 L258 的 `step` 传给 `complete_step`（L189）/ `record_error`（L198），**两者首行均已 `if step is None: return`** —— 运行期本就接受 None | L3 返回注解（**连带 2 处入参**） | `trace() -> ExecutionStep \| None`；**同时**把 `complete_step(step: ExecutionStep \| None, ...)` / `record_error(step: ExecutionStep \| None, ...)` 入参同步放宽（否则新增 2 条 arg-type——Step 2 F-01 实测） |
| 2 | `tools/distillation_audit.py:173` | var-annotated | `results = []` 空列表无法推断；方法签名 `-> list[dict]` | L3 | `results: list[dict] = []` |
| 3 | `tools/benchmark.py:130` ×2 + `:149` | arg-type ×2 / operator ×1 | `test_configs = [{...}]` 混合 str/int 值 → 推断 `list[dict[str, object]]`，`n_dates` / `n_stocks` 为 `object` | L3 | `test_configs: list[dict[str, Any]] = [...]`（`Any` 已 import） |
| 4 | `examples/full_backtest_demo.py:584` | assignment | `current_qty` L583 绑定 `Position \| None`（`current_positions.get`），L584 又赋 `float \| int` —— **同变量两种类型** | L3 局部改名 | `position = current_positions.get(stock)` / `current_qty = position.quantity if position else 0` |
| 5 | `examples/full_backtest_2020_2026_simple.py:116` | arg-type | `UniverseFilter(dm, config.universe)` 传 `UniverseConfig`，构造器需 `UniverseFilterConfig` | L3 实参改写（值层） | `UniverseFilterConfig.from_universe_config(config.universe)`；**导入必须取自 `filter.universe_filter_clean`**——`filter/__init__.py` 仅导出 `UniverseFilter`（L126），不从包根导入（否则运行期 ImportError，Step 2 F-02；先例 `core/engine_v2.py:63`） |
| 6 | `examples/full_backtest_2020_2026_simple.py:124` ×2 | call-arg + arg-type | `PositionTracker(config.initial_capital)` 只传 1 个位置参数；实际签名 `__init__(n_stocks: int, initial_capital: float)`（`core/tracker.py:165`）→ **运行期 TypeError** | **缺陷修复** | `PositionTracker(dm.n_stocks, config.initial_capital)`（`core/data.py:120` 的 `n_stocks` property；优于 `len(dm.close.columns)`——不强制加载价格数据，Step 2 F-07） |
| 7 | `examples/run_single_backtest.py:62,63` | union-attr ×2 | `engine.dm: IDataManager \| None`；L60 `engine.setup()` 后已赋值（U-a） | L2 | `dm = engine.dm` + `assert dm is not None`，改用 `dm` |
| 8 | `examples/run_full_backtest_fixed.py:76,78` | union-attr ×2 | 同上；L74 `engine.setup()`（U-a） | L2 | 同上 |
| 9 | `examples/run_backtest_minimal.py:71` | union-attr ×1 | 同上；L70 `engine_long.setup()`（U-a） | L2 | 同上 |
| 10 | `examples/full_backtest_2020_2026.py:80,84` | union-attr ×2 | 同上；L78 `engine_full.setup()`（U-a） | L2 | 同上 |
| 11 | `examples/run_single_backtest.py:66,67` | union-attr ×2 | `engine._composite_signal: Optional[pd.DataFrame]`（`core/engine_v2.py:175`），L60 setup 后 L337 已赋值（U-a） | L2 | `signal = engine._composite_signal` + `assert signal is not None` |
| 12 | `examples/demo.py:73` | var-annotated | `event_days = rng.choice(...) if n_events > 0 else []` —— 两分支为 ndarray / list，无法统一推断 | L3 | `event_days: np.ndarray \| list[int] = ...`（`demo.py` **无 `typing` import**，故不引 `Any`——Step 2 F-03） |
| 13 | `examples/demo.py:79`（**仅 3.10 口径**） | assignment | `adj = adj / adj[-1:]` 形状在 numpy 2.2.6 桩下丢失（P-036 同型） | L3 | **L68 声明**：`adj: np.ndarray = np.ones((n_days, n_stocks))`（**Step 6 F-S6-P037-1 实测订正**：`np.asarray(adj / adj[-1:])` 在 r310 仍报形状赋值；行内 `adj: np.ndarray = adj / adj[-1:]` 触发 `no-redef`；L68 声明为三口径实测唯一可行解，P-036 `_spec.py:68` 同型先例） |

**汇总**：union-attr **9** / arg-type **4**（含 2 条由 call-arg 同根）/ var-annotated **2** / return-value **1** / call-arg **1** / assignment **2**（含 3.10 独有 1）/ operator **1** = **20 条 / 10 簇**（3.12 口径 19 条 = 剔除 #13）。

---

## 5. 真实缺陷与行为变更裁决

### 5.1 F-S1-P037-1（P2，真实缺陷）：`examples/full_backtest_2020_2026_simple.py:124`

**E2 探针实锤**：

```
inspect.signature(PositionTracker.__init__) → (self, n_stocks: 'int', initial_capital: 'float')
PositionTracker(1e7) → TypeError: PositionTracker.__init__() missing 1 required positional argument: 'initial_capital'
```

- 该示例把 `initial_capital` 当第 1 个参数传入（实际绑定到 `n_stocks`），缺 `initial_capital` → **脚本运行即在 setup 阶段崩溃**。
- **归因（Step 2 F-04 订正）**：`git show c7a0f29:core/tracker.py` 已含 `def __init__(self, n_stocks: int, initial_capital: float)`，而同提交的示例已为 1 参调用 → **该示例自诞生即不可运行**，并非「API 后续演进导致陈旧」。原「P-011 前后签名变更」表述无据，已撤回。
- 定性：**缺陷修复**（非类型修复）；修复后示例恢复可构造性。**运行期端到端可用性不在本批承诺内**（依赖真实数据文件，见 §7.2）。

### 5.2 行为变更清单（预计 1 项 + 1 项值层改写）

| # | 位置 | 现网行为 | 修复后 | 性质 |
|---|------|---------|--------|------|
| C1 | `examples/full_backtest_2020_2026_simple.py:124` | 构造 `PositionTracker` 即 `TypeError`（示例不可用） | 正确构造 `PositionTracker(dm.n_stocks, initial_capital)` | 缺陷修复（示例恢复可构造） |
| C2 | 同上:116 | `UniverseFilter(dm, config.universe)` 传错配置类型（duck-typing 下仍可运行，字段语义按源 `UniverseConfig` 取值） | 显式 `UniverseFilterConfig.from_universe_config(...)` | **值层改写（逐字段值等价）**：21 字段全部取自源对象（`universe_filter_clean.py:68-90`），转换后与**原 duck-typed 传参**的字段值一致；**不等于目标默认构造**（目标默认 `excluded_prefixes=["300","688"]` / `exclude_na_factors=False` / `na_factor_names=["factor_value"]`，L44-49）——Step 4 F-S4-P037-1 / Step 8 F-S8P037-1 两次订正 |

其余 18 条均为注解级 / U-a 窄化 / 局部改名——**零行为变更**。`engine.dm` 的 5 组 `assert` 全部属 U-a（`setup()` 或手动赋值已成立），失败路径本已崩溃。

---

## 6. 方案矩阵与低效排除

### 6.1 候选方案

| 方案 | 内容 | 成本 | 裁决 |
|------|------|------|------|
| **M-A 全量纳入** | 修 20 条 → target 追加 `tools examples`（10 面 → **12 面**）→ 双载体同提交 | 1 批（19+1 条 / 10 文件） | **推荐** |
| M-B 仅纳入 `tools` | 修 5 条 → target 追加 `tools`（11 面）；`examples` 维持未覆盖 | 半批 | 不采纳：`examples` 是 README Quick Start 入口，保护价值高于 `tools`；且 14 条规模可控 |
| M-C 不纳入（维持 pending） | 零改动，U-P036-4 继续 pending | 0 | 不采纳（用户已选定扩做）：门禁边界留半成品，后续每次扩面评估都要重新取证 |
| M-D 用 `ignore_errors` 纳入 | 加 override 压 20 条 | 0 | **禁止**：P-036 刚拆掉同型假绿（U-P024-4），重蹈覆辙 |

### 6.2 低效排除（7 项）

1. **不为 `demo/` / `memory/` 造门禁对象**——零 `.py` 文件（§2.3）。
2. **不新增 `[[tool.mypy.overrides]]`**——与 P-036 D3-L4「新增 ignore = 0」纪律冲突。
3. **不改 `[tool.mypy]` 全局配置**（不引入 `strict` / `warn_unused_ignores` / `disallow_untyped_defs`），理由同 P-036 D7。
4. **不给 `examples` 补 `__init__.py`**——`--explicit-package-bases` 已可直检，新增包结构会改变 import 语义（低效且越界）。
5. **不重写陈旧示例**（如把 `full_backtest_2020_2026_simple.py` 迁到 `setup()` 模式）——超出题干；本批只做类型面 + C1 缺陷修复。
6. **不引入 `TypedDict` 重构 `benchmark.py` 的配置表**——`list[dict[str, Any]]` 已是最小改动，TypedDict 属结构重构。
7. **不在本批扩 `tests/`**（X=0，沿 P-036 I4 口径）——除非 C1 需要回归断言；按「示例不纳入 pytest」现状，不新增测试。

---

## 7. 风险、未决与观察

| ID | 类型 | 内容 | 处置 |
|----|------|------|------|
| **R-P037-1** | 风险 | `tools` / `examples` 无 `__init__.py`，`--explicit-package-bases` 在 CI 三 leg 下的模块解析可能与本地不同 | Step 9 须三口径复跑（`tools examples` 全量） |
| **R-P037-2** | 风险 | `examples` 脚本依赖真实数据文件（`data/` / `gurus/`），类型修复无法证明运行期可用 | 本批只承诺「类型面 + 可构造性」，端到端可用性登记观察（O-P037-1） |
| **R-P037-3** | 风险 | `trace()` 返回注解放宽为 `Optional` 后，若无连带放宽 `complete_step` / `record_error` 入参，会新增 2 条 arg-type（Step 2 F-01 已实证） | §4 #1 改法已含「连带 2 处入参」；Step 9 以 0 新增错误为验收 |
| **R-P037-4** | 风险 | `benchmark.py` 的 `list[dict[str, Any]]` 会削弱该文件的类型约束（Any 传播） | 可接受：基准脚本非生产面；若后续需要，单独立项 TypedDict |
| **R-P037-5** | 风险 | `filter` 包根不导出 `UniverseFilterConfig`，若按直觉写 `from filter import UniverseFilterConfig` 会运行期 ImportError | §4 #5 已锁定 `from filter.universe_filter_clean import ...`；Step 9 探针复核 import |
| U-P037-1 | 未决 | `demo/` / `memory/` 无 Python 文件——若不属 Python 目录，U-P036-4 题干应正式收窄 | 本批关闭 U-P036-4 时一并改台账措辞 |
| U-P037-2 | 未决 | `examples` 陈旧程度（`full_backtest_2020_2026_simple.py` 等是否仍与当前 API 语义一致） | 维持 pending（触发：用户实际运行示例报错） |
| U-P037-3 | 未决 | **本批 Step 2 复审会话自报基座 `UNKNOWN`（系统提示未声明模型名）→ RULE-5 异构性无法证实** | 登记；Step 10 前由用户指定的异构基座会话补做终审（先例 U-P036-6） |
| O-P037-1 | 观察 | 示例脚本端到端运行需数据前置，CI 无覆盖 | 登记（类型门禁 ≠ 运行验证） |
| O-P037-2 | 观察 | `tests/test_distillation_isolation.py` 引用 `tools.distillation_audit` —— 类型修复为该测试提供静态保护 | 正面收益，登记 |

---

## 8. 台账四元块（U-P036-4 关闭判据）

| 字段 | 内容 |
|------|------|
| **判据** | `mypy tools examples` 三口径 = 0 error；`tests.yml` L46 + adapter L67 target = 12 面且逐字一致；`mypy` 10 面既有面仍 0 |
| **触发条件** | 本批（用户 2026-11-17 裁决扩做）；关闭时 U-P036-4 → done |
| **当前倾向** | 全量纳入（M-A），20 条真修，新增 ignore = 0 |
| **证据等级** | E1（三口径 mypy 读数 / grep）+ E2（PositionTracker 探针） |

---

## 9. 可重放命令（E1）

```powershell
# 本机口径
& 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe' -m mypy --explicit-package-bases --check-untyped-defs tools examples

# CI 3.12 复刻（numpy 2.5.5）
& "$env:TEMP\p036r2\Scripts\python.exe" -m mypy --explicit-package-bases --check-untyped-defs tools examples

# CI 3.10 复刻（numpy 2.2.6）
& "$env:TEMP\p036r310\Scripts\python.exe" -m mypy --explicit-package-bases --check-untyped-defs tools examples

# 生产调用面（期望 0 命中，除 tests 3 处）
git grep -nE '^\s*(from|import)\s+(tools|examples)\b'

# 目录实况
Get-ChildItem tools,examples,demo,memory -Filter *.py -Recurse
```

---

## 10. Step 2 交接事项

1. **异构复审（RULE-5）**：作者 DeepSeek-V4.1-Flash → 须异构基座。核验重点：① 三口径读数重放（19/19/20）；② 10 簇分类是否与代码一致（尤其 #6 真实缺陷定性）；③ §6 低效排除是否越界；④ U-P036-4 题干收窄（剔除 `demo`/`memory`）是否合规。
2. **判档确认**：扩 target = 门禁判据变更 → T1（不可降档）。
3. **顺序敏感**：修复与 `tests.yml` + adapter **同提交**（P-036 F-S9-P036-1 教训）；`examples` 的 U-a `assert` 必须能指出 `setup()` / 手动赋值前提。
4. **红态纪律**：Step 9 首跑必须出示修复前读数（19 / 19 / 20），不得用修复后读数倒填。

---

## 11. Step 2 复审记录（2026-11-17）

> **基座披露（R≠5 诚实声明）**：复审执行会话的 system prompt **未声明模型名**，其第 0 步自报 `UNKNOWN` → **RULE-5 异构性无法证实**，本轮**不得**记为异构审查；登记 **U-P037-3** pending（Step 10 前由用户指定的异构基座会话补做终审，先例 U-P036-6）。作者基座 = DeepSeek-V4.1-Flash。
> **复审方式**：独立全新上下文会话（消除记忆污染）+ 独立探针（`%TEMP%\p037_widen_repro.py`）+ 三口径重跑；复审时点 HEAD `ad7815d`（本文档未提交态）。

### 11.1 复核读数（全部与原文一致）

| 项 | 复审实测 | 原文 | 判定 |
|----|---------|------|------|
| 本机 3.12+numpy2.4.6 | 19 errors / 10 files（checked 11） | 19 | ✅ |
| r2 3.12+numpy2.5.5 | 19 / 10 | 19 | ✅ |
| r310 3.10+numpy2.2.6 | 20 / 10（差异唯一 = `demo.py:79`） | 20 | ✅ |
| 单目录 | `tools` 5/3（4 checked）、`examples` 14/7（7 checked） | 同 | ✅ |
| 逐条 20 行 | 文件名 / 行号 / 错误码**逐行命中，无漏列无多列** | — | ✅ |
| 生产面 import | grep 3 行全在 `tests/test_distillation_isolation.py` | 同 | ✅ |
| `demo/` `memory/` | 零 `.py`（mypy exit 2） | 同 | ✅ |
| 依赖面 | `streamlit|typer|plotly|dash|gradio` 0 命中 | 同 | ✅ |

### 11.2 发现与当轮处置（7 项：2 P2 + 5 P3）

| ID | 级别 | 发现 | 当轮处置 |
|----|------|------|---------|
| **F-S2-P037-1** | **P2** | 只放宽 `trace()` 返回注解**不能归零**：`complete_step` / `record_error` 入参仍为 `ExecutionStep` → 新增 **2 条 arg-type**（独立探针实测） | §4 #1 改法扩为「返回注解 + 2 处入参同步放宽」；R-P037-3 重写 |
| **F-S2-P037-2** | **P2** | `filter/__init__.py` **未导出** `UniverseFilterConfig`（L126 仅 `UniverseFilter`）→ 按原改法从包根导入会运行期 `ImportError` | §4 #5 锁定 `from filter.universe_filter_clean import ...`（先例 `core/engine_v2.py:63`）；新增 R-P037-5 |
| F-S2-P037-3 | P3 | `examples/demo.py` **无 `typing` import**，原改法 `event_days: Any` 不可用 | §4 #12 改用 `np.ndarray \| list[int]` |
| F-S2-P037-4 | P3 | §5.1 归因失实：`c7a0f29` 时 `PositionTracker` 已是 2 参签名、同提交示例已 1 参调用 → **自诞生即不可运行**，非「API 演进导致陈旧」 | §5.1 归因改写并撤回原表述 |
| F-S2-P037-5 | P3 | 表编号 1-13 却称「20 条 / 10 簇」，未说明 #7-#10 合并为 1 簇 | §4 表前加「13 行 = 10 簇」编号说明 |
| F-S2-P037-6 | P3 | #5 是**构造实参改写（值层）**，不属「注解级」 | §5.2 单列 C2（值层改写、运行期等价） |
| F-S2-P037-7 | P3 | `len(dm.close.columns)` 可行但次优（强制加载价格数据）；`dm.n_stocks`（`core/data.py:120`）更轻且为仓内惯例 | §4 #6 改用 `dm.n_stocks` |

### 11.3 结论

**复审结论**：**pass（带 2 P2 + 5 P3 全部当轮回写）**——三口径读数、20 条逐条定性、触发条件取证、判档 T1 全部可复现；两项 P2 属「按原文实施会不归零 / 运行期 ImportError」的实质缺口，已在本文档修正，**准予进入 Step 3 DESIGN**。
**RULE-5**：复审基座 `UNKNOWN` → **异构不成立**，U-P037-3 跟踪；Step 4/6/8/10 复审同样须先自报基座，无法证实异构时一律登记而非默认为异构。
