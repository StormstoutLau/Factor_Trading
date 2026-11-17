# IMPL：P-037 类型门禁边界收口

> **批次**: P-037 · **Step 5 实施规划** · 日期 2026-11-17
> **判档**: **T1**（门禁判据变更；判档规则 2）
> **上游**: [DESIGN_p037](DESIGN_p037_type_gate_boundary.md)（D1-D5 / I1-I6 / V1-V5 / §8 Step 4 复审 pass：2 P2 + 3 P3 当轮回写）；[RESEARCH_p037](RESEARCH_p037_type_gate_boundary.md)（§4 20 条 / §5 C1-C2 / §11 Step 2 复审 pass）
> **代码证据时点**: HEAD `ad7815d`（§4 锚点为实施前行号）
> **基座**: DeepSeek-V4.1-Flash（Step 6 Review 须自报基座；异构未证实时登记 U-P037-3）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（代码 10） | `tools/ui_dashboard.py` / `tools/distillation_audit.py` / `tools/benchmark.py` / `examples/demo.py` / `examples/full_backtest_demo.py` / `examples/full_backtest_2020_2026.py` / `examples/full_backtest_2020_2026_simple.py` / `examples/run_backtest_minimal.py` / `examples/run_full_backtest_fixed.py` / `examples/run_single_backtest.py` |
| 变更文件（门禁 2） | `.github/workflows/tests.yml` L46 + `scripts/spec_runner_adapter.py` L67（**同提交**追加 ` tools examples`） |
| 变更文件（文档） | 本文件 / `docs/PROGRESS.md`（§1.4 + §3.42.x）/ `CHANGELOG.md` |
| 零改动面 | `core/**` / `tests/**`（含 golden 13）/ `pyproject.toml` / `uv.lock` / `agents/` / `filter/` / `web/` / `factor_library/` / `cli.py` / 生产面其余 |
| 门禁口径 | pytest **760 不变**（X=0）/ golden **13 零重录** / black **121** / `except Exception` 恒 **22** / mypy 12 面**三口径 0** / 新增 `# type: ignore` **0** |

**五条不可越界的前提**：

1. **L2 `assert` 仅用于 U-a**：插入点必须能指出现有运行期前提（`setup()` 调用行 / 手动赋值行）；正常路径零变更。
2. **L1 仅 1 簇**：`PositionTracker` 构造缺陷（C1）——修的是**构造实参**，不改生产签名。
3. **L3 注解目标为运行期真值类型**：禁止 `cast(Any, ...)`；`event_days` 用 `np.ndarray | list[int]`（不引 `Any`）。
4. **I2 口径**：`^-\s*def ` = **2**（仅 `complete_step` / `record_error` 参数注解放宽）；参数名 / 默认值 / 函数名零变更；`trace()` 注解在续行不触 def 行。
5. **禁止** `--follow-imports=silent` / `ignore_errors` / 裸 `# type: ignore` / 新增 `[[tool.mypy.overrides]]`。

### 行为变更清单（2 项）

| # | 位置 | 现网行为 | 修复后 | 性质 |
|---|------|---------|--------|------|
| C1 | `examples/full_backtest_2020_2026_simple.py:124` | `PositionTracker(initial_capital)` → 运行期 `TypeError`（示例不可构造） | `PositionTracker(dm.n_stocks, initial_capital)` | 缺陷修复 |
| C2 | 同上:116 | 传 `UniverseConfig` 给期望 `UniverseFilterConfig` 的构造器（duck-typing 下可运行，字段语义按源对象） | `UniverseFilterConfig.from_universe_config(config.universe)` | 值层改写（逐字段值等价） |

### 不扩做（DESIGN-D5 复述，Step 6 F-S6-P037-4 补录）

1. **不为 `demo/` / `memory/` 造门禁对象**——两目录零 `.py` 文件（mypy exit 2）。
2. **不给 `tools` / `examples` 补 `__init__.py`**——`--explicit-package-bases` 已可直检 11 modules；补包结构改变 import 语义。
3. **不改 `[tool.mypy]`**（`strict` / `warn_unused_ignores` / `disallow_untyped_defs`）。
4. **不重写陈旧示例**（不迁 `setup()` 模式）——只做类型面 + C1。
5. **不引入 `TypedDict`**、**不新增 pytest（X=0）**、**不把 `tests/` 纳入 target**。

---

## 2. 任务拆解

| ID | 任务 | 对应 | 条数 |
|----|------|------|------|
| **B1** | 修 13 行 / 20 条（3.12 = 19，3.10 追加 1）+ 双载体追加 `tools examples` | DESIGN-D1/D2/D3 | 19 / 20 |
| **DOC1** | 文档回填（本文件 §11 / PROGRESS / CHANGELOG / CHECKLIST） | DESIGN §7 | —— |

**计数**：3.12 口径 = 2（L1）+ 9（L2）+ 7（L3）+ 1（C2 值层）= **19**；3.10 追加 #13 → **20**。

---

## 3. 实施顺序与依赖

```text
修 20 条 → 本机 `mypy tools examples` = 0
  → r2（3.12+2.5.5）= 0 → r310（3.10+2.2.6）= 0
  → 本地 12 面 = 0（既有 10 面不回归）
  → tests.yml L46 + adapter L67 同提交追加 ` tools examples`
  → pytest 760 / golden 13 / black 121 / AST 22 / uv lock 复验
  → 单提交（10 代码 + 2 门禁载体）→ CI 四 job 绿
```

- **红态**：Step 9 首跑必须出示修复前读数（19 / 19 / 20）。
- **顺序敏感三项**：① `trace()` 连带入参；② C2 导入路径（`filter.universe_filter_clean`）；③ 5 组 `assert` 前提逐组核。

---

## 4. 精确变更规格

> 锚点为实施前 HEAD `ad7815d`；净行数以 `git diff --numstat` 为准（§11 回填）。

### 4.1 门禁双载体（2 文件各 1 行）

**B1 后**（`tests.yml` L46）：

```yaml
        run: python -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
```

`adapter.py` L67 同步（`{_PY312} -m mypy ...` 前缀不同，target 串逐字一致）。

**约束**：禁止 `|| true` / `continue-on-error`；`test` job 其余行与 `lock-check` job 逐字不动。

### 4.2 `tools/` —— 5 条（3 文件）

| # | 文件:行 | 错误码 | 根因 | 改法 |
|---|---------|--------|------|------|
| 1 | `ui_dashboard.py:167` | return-value | `trace()` 返回注解 `-> ExecutionStep` 却返回 None | **三处**：① `trace()` 返回注解 `-> ExecutionStep \| None`（注解在续行 L164）；② `complete_step(step: ExecutionStep \| None, ...)` L189；③ `record_error(step: ExecutionStep \| None, ...)` L198。两方法首行已 `if step is None: return`，零行为变更 |
| 2 | `distillation_audit.py:173` | var-annotated | `results = []` | `results: list[dict] = []`（与返回注解 `-> list[dict]` 一致） |
| 3 | `benchmark.py:130` ×2 / `:149` | arg-type ×2 / operator | `test_configs` 推断 `list[dict[str, object]]` | L102 `test_configs: list[dict[str, Any]] = [`（`Any` 已在 L12 import） |

### 4.3 `examples/` —— 15 条（7 文件）

| # | 文件:行 | 错误码 | 改法 |
|---|---------|--------|------|
| 4 | `full_backtest_demo.py:584` | assignment | L583-L584 改为：`position = current_positions.get(stock)` / `current_qty = position.quantity if position else 0`（变量名 `current_qty` 保持，用于后续 L586-L587） |
| 5 | `full_backtest_2020_2026_simple.py:116` | arg-type | `engine.universe = UniverseFilter(dm, UniverseFilterConfig.from_universe_config(config.universe))`；L109 import 改为 `from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig`（**不得**从 `filter` 包根导入） |
| 6 | 同上:124 | call-arg ×1 + arg-type ×1 | `engine.tracker = PositionTracker(dm.n_stocks, config.initial_capital)` |
| 7 | `run_single_backtest.py:62,63` | union-attr ×2 | L61 插 `dm = engine.dm` + `assert dm is not None`；L62-63 改用 `dm` |
| 8 | `run_full_backtest_fixed.py:76,78` | union-attr ×2 | L75 插 `dm = engine.dm` + `assert dm is not None`；L76/78 改用 `dm` |
| 9 | `run_backtest_minimal.py:71` | union-attr ×1 | L70 后插 `dm = engine_long.dm` + `assert dm is not None`；L71 改用 `dm` |
| 10 | `full_backtest_2020_2026.py:80,84` | union-attr ×2 | L79 插 `dm = engine_full.dm` + `assert dm is not None`；L80/84 改用 `dm` |
| 11 | `run_single_backtest.py:66,67` | union-attr ×2 | L65 插 `signal = engine._composite_signal` + `assert signal is not None`；L66-67 改用 `signal` |
| 12 | `demo.py:73` | var-annotated | `event_days: np.ndarray \| list[int] = (`（文件无 `typing` import，不引 `Any`） |
| 13 | `demo.py:79`（**仅 3.10**） | assignment | **L68 声明**：`adj: np.ndarray = np.ones((n_days, n_stocks))`（**Step 6 F-S6-P037-1 实测订正**：原两种改法均不可行——`np.asarray(adj / adj[-1:])` 在 r310 仍报形状赋值；行内 `adj: np.ndarray = adj / adj[-1:]` 触发 `no-redef`。P-036 `_spec.py:68` 同型先例） |

> **行号偏移提示（Step 6 F-S6-P037-3）**：同文件多处插入时，后续锚点会偏移（如 `run_single_backtest.py` 先改 #7 会使 #11 的 L65/66/67 → L67/68/69）。**实施顺序按行号降序**（先改文件尾部，再改头部），或每改一处后重读文件确认锚点。

### 4.4 C1 / C2 细节

- **C1**：`dm.n_stocks`（`core/data.py:120` property）而非 `len(dm.close.columns)`——不强制加载价格数据。
- **C2**：`from_universe_config` 的 21 字段全部取自源 `UniverseConfig` → 与原 duck-typed 传参**逐字段值等价**；**不等于**目标默认构造（`excluded_prefixes=["300","688"]` 等）。
- **导入硬约束**：`from filter.universe_filter_clean import UniverseFilter, UniverseFilterConfig`（`filter/__init__.py` 不导出后者）。

---

## 5. 红态（Step 9 必须出示）

| 口径 | 修复前 |
|------|--------|
| 本机 py3.12 + numpy 2.4.6 | `Found 19 errors in 10 files (checked 11 source files)` |
| r2 py3.12 + numpy 2.5.5 | 19 / 10 |
| r310 py3.10 + numpy 2.2.6 | `Found 20 errors in 10 files (checked 11 source files)`（追加 `demo.py:79`） |

---

## 6. 门禁终态（预期）

| 项 | 读数 |
|----|------|
| mypy 12 面 | 三口径均 0（`checked 103 source files` 相邻数值以实测为准） |
| `mypy tools examples` | 0 |
| pytest / golden | 760 / 13（`747 deselected`） |
| black / AST / uv | 121 / 22 / exit 0 |
| 新增 `# type: ignore` | 0 |
| `^-\s*def ` | 2（仅两处参数注解） |

---

## 7. 回退点

- 单提交 revert → 回到 10 面门禁 + 修复前代码（无跨批依赖）。
- 若 C1/C2 修复引发意外（示例语义），可**仅回退** `full_backtest_2020_2026_simple.py` 并改为 `# type: ignore`？——**禁止**（L4 上限 0）；正确做法是回归 DESIGN §8 重新裁决。

---

## 8. Step 6 交接

1. **复审须自报基座**（RULE-5）：核 ① 20 条规格与 RESEARCH §4 逐条一致；② 每处 `assert` 前提行；③ `trace()` 三处连带；④ C2 导入路径；⑤ 门禁双载体字符串。
2. **版本存在性**：本批无新依赖（stdlib + numpy/pandas 既有），无需 PyPI 核验。
3. **可机械执行性**：逐条核 `def` / 赋值 / 属性名当前是否存在（防幻觉锚点）。

---

## 9. Step 6 复审记录（2026-11-17）

> **基座披露**：复审会话第 0 步逐字自报 `You are powered by the model named DeepSeek-V4.1-Flash.` → **与作者同源，RULE-5 不成立**（同基座独立上下文复审，RULE-4 披露）；U-P037-3 累计第 3 轮异构未证实。
> **复审方式**：独立会话 + 探针（`%TEMP%\p037_probe\`，三变体对比）+ 全量门禁实跑；复审时点 HEAD `ad7815d`（代码未改动）。

### 9.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | 8 组锚点（`ui_dashboard` L162/164/167/189/198、`distillation_audit` L171/173、`benchmark` L102/12、5 个 examples 的插入点与前提行） | **全部命中** | ✅ 零幻觉 |
| B | IMPL 13 行 vs RESEARCH 13 行 | 内容逐条一致，仅编号顺序不同 | ⚠️ F-S6-P037-2 |
| B | 计数 2+9+7+1 = 19 / +1 = 20 | 与三口径实跑对齐 | ✅ |
| B | `trace()` 三处连带 / I2=2 | 一致 | ✅ |
| C | `event_days: np.ndarray \| list[int]` | 三口径均消除该错 | ✅ |
| C | **#13 两种改法** | `np.asarray` 在 r310 **仍报**；行内注解触发 `no-redef`；**L68 声明 `adj: np.ndarray = np.ones(...)` 三口径全绿** | ❌ F-S6-P037-1（P2） |
| C | C1 的 `dm` 作用域 / C2 的 `config` 作用域 | 均同函数可见（L69 / L35） | ✅ |
| D | 基线读数 | pytest 760 / golden 13 / black 121 / AST 22 / uv exit 0 / 10 面 92 files 0 / 12 面 19 errors 103 files | ✅ 全部一致 |
| D | 判档 T1 / U-P037-3 | 保留 | ✅ |

### 9.2 发现与当轮处置（1 P2 + 3 P3）

| ID | 级别 | 发现 | 当轮处置 |
|----|------|------|---------|
| **F-S6-P037-1** | **P2** | §4.3 #13 的两种改法**均不可归零**：`np.asarray` 不改变形状推断（r310 仍 1 error）；行内 `adj: np.ndarray = ...` 触发 `no-redef` | #13 改为 **L68 声明** `adj: np.ndarray = np.ones((n_days, n_stocks))`（P-036 `_spec.py:68` 同型先例，三口径实测全绿） |
| F-S6-P037-2 | P3 | IMPL 与 RESEARCH 编号错位（#8↔#11） | §4.3 表按 RESEARCH 顺序重排（#7/#8/#9/#10/#11 对齐） |
| F-S6-P037-3 | P3 | 同文件多处插入会使后续锚点偏移，文档未提示 | §4.3 表后补「按行号降序实施 / 每次重读」提示 |
| F-S6-P037-4 | P3 | §1 缺 D5「不扩做」小节 | §1 补 5 条（demo/memory、`__init__.py`、`[tool.mypy]`、重写示例、TypedDict/tests） |

### 9.3 结论

**复审结论**：**pass（1 P2 + 3 P3 全部当轮回写）**——锚点零幻觉、计数自洽、基线读数全部命中；P2 修正后 §4.3 规格可执行，**准予进入 Step 7 CHECKLIST**。
**RULE-5**：连续第 3 轮同基座 → U-P037-3 维持 pending。

---

## 11. Step 9 实施记录（2026-11-17）

> **实施基点**: `ad7815d` → **代码终态**: `22644e3`

### 11.1 红→绿与净行数

| 项 | 读数 |
|----|------|
| 红态（本机 / r2 / r310） | 19 / 19 / 20 errors（10 files / checked 11） |
| 绿态（`tools examples`） | 三口径 `Success: no issues found in 11 source files` |
| 绿态（12 面） | `Success: no issues found in 103 source files` |
| 提交 | `22644e3` 12 文件 **+34/−24**（10 代码 +2 门禁载体） |
| 逐文件净行数 | demo 2/2 · full_2020_2026 4/2 · simple 3/3 · full_backtest_demo 2/2 · minimal 3/1 · fixed 4/2 · single 7/5 · benchmark 1/1 · distillation 1/1 · ui_dashboard 5/3 |

### 11.2 探针（`%TEMP%\p037_s9_probe.py`）

| 项 | 读数 | 判定 |
|----|------|------|
| V4（C1） | `V4 construct OK: n_stocks=2 cash=10000000.0` | ✅ 缺陷修复实锤 |
| V4b（C2） | `fields=21 mismatches=0` / `not-equal-to-default fields: ['exclude_na_factors','na_factor_names','excluded_prefixes']` | ✅ 逐字段等价、且非默认构造 |

### 11.3 门禁终态（`22644e3`）

`mypy` 12 面 103 files 0（三口径 `tools examples` 0）/ pytest **760** / golden **13** / black **121**（全仓 188）/ AST **22** / `uv lock` exit 0 / 新增 ignore **0** / `^-\s*def ` = **2** / 零改动面 diff 空 / CI run `44046313784` 四 job 全绿。

### 11.4 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P037-1 | P3 | §4.3 #4 的改名 `position` 与同函数 L566 `for stock, position in current_positions.items()` 冲突 → 首版触发 assignment | 改用 `held`（语义等价） |
| F-S9-P037-2 | P3 | PowerShell `Select-String` 默认大小写不敏感，`Exception` 被 `^\+.*except` 误计 1 条 | 以 `-CaseSensitive` 重算 = 0（口径已写入 CHECKLIST C3） |

### 11.5 结论

**Step 9 结论**: **pass** —— 红态逐字、绿态三口径 0、C1/C2 探针实锤、I1-I6 全部成立。**Step 10 前置**：ADD 审计（须自报基座；异构未证实则 U-P037-3 跟踪）。
