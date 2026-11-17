# IMPL：P-036 mypy 检查面扩展

> **批次**: P-036 · **T1**（门禁判据面变更；SPEC_PROCESS 判档规则 2）
> **上游**: [DESIGN_p036](DESIGN_p036_mypy_check_surface_expansion.md)（D1-D7 / I1-I7 / V1-V6 / §9 Step 4 异构复审 pass：2 P2 + 2 P3 当轮回写）
> **状态**: **Step 5 实施规划**（2026-11-17，基线 HEAD `65da5f9`）
> **代码证据时点**: 实施前 HEAD `65da5f9`；§4 全部锚点为**实施前行号**
> **基座**: DeepSeek-V4.1-Flash（Step 6 实施 Review 须异构，RULE-5）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（B1 代码，7） | `strategy_evaluation/evaluator.py` / `strategy_evaluation/stats.py` / `order_strategy/strategies.py` / `scripts/external_benchmark/verify_p015.py` / `scripts/external_benchmark/_spec.py` / `batch_backtest/engine.py` / `cli.py` |
| 变更文件（B2 代码，11） | `agents/guru_agent_v2.py` / `agent_framework.py` / `style_drift_analysis.py` / `style_reflection_engine.py` / `strategy_allocator.py` / `sentiment_framework.py` / `auto_parameter_optimizer.py` / `assumption_monitor.py` / `hierarchical_bayesian_agent.py` / `multi_strategy_engine.py` / `research_team_v2.py` |
| 变更文件（B3 代码，7） | `filter/universe_filter_clean.py` / `prefix.py` / `na_factor.py` / `market_cap.py` / `industry.py` / `extended.py` / `custom.py` |
| 变更文件（CI） | `.github/workflows/tests.yml` 的 mypy 步骤（L45-46）分三次扩 target |
| 变更文件（文档） | 本文件 / `docs/PROGRESS.md`（§1.4 + §3.41.6~§3.41.8）/ `CHANGELOG.md` |
| 零改动面 | `core/**` / `tests/**`（含 golden 13 份基线）/ `pyproject.toml` / `uv.lock` / `filter/base.py` / `agents/interfaces.py` / `examples/` / `tools/` |
| 门禁口径 | pytest **760 不变**（I4 的 X=0，本批不新增测试）；black **121**；mypy 逐步 **8 面 → 9 面 → 10 面**均为 0；golden **13 零重录**；`except Exception` 恒 **22**；裸 `# type: ignore` **0**、带 code **0**（全程不使用 L4） |

**五条不可越界的前提**：

1. **L2 `assert` 仅用于 U-a**：插入点必须能指出现有运行期前提（构造期 `raise` / 前一分支 `if x is None: build()` / 方法前置 `setup()`）；正常路径零变更，失败路径仅异常类型变化（本已崩溃）。
2. **L1 变更加守卫，不改语义**：`guru_data` 的守卫**已存在**（L186-188），本批只把 `Optional` 属性声明改为经窄化后赋值——**零行为变更**；真正新增的 fail-fast 仅 `batch_backtest/engine.py::run_factors` 一处（§4.2）。
3. **L3 注解目标为运行期真值类型**：`no-any-return` 一律用**局部变量注解**收窄（`x: float = np.sum(...)`），不用 `cast(Any, ...)`；`np.asarray(...)` 仅用于已是 ndarray 的返回值（`asarray` 对 ndarray 不复制）。
4. **I2 的机械口径澄清**：`git diff` 中删除的 `def` 行必须**逐字回归**，唯一允许的差异是**返回注解修正**（`_weighted_vote` / `_confidence_weighted` / `verify_case` / `create_filter` / `NAFactorFilter.__init__` 五处，见 §8），参数名 / 参数默认值 / 函数名零变更。
5. **公开行为零变更**：除 §1 表「行为变更清单」4 项外，全部修复为零行为变更；**禁止**用 `--follow-imports=silent`、`ignore_errors`、裸 ignore。

**行为变更清单（4 项，须 CHECKLIST 单列验收）**：

| # | 位置 | 现网行为 | 修复后 | 性质 |
|---|------|---------|--------|------|
| C1 | `batch_backtest/engine.py::run_factors` | `factor_db=None` 时 `AttributeError` | 顶部 `raise ValueError("未提供因子数据库")`（与 `run_all_factors` L81-82 逐字一致） | fail-fast 显式化（D4 ①） |
| C2 | `agents/multi_strategy_engine.py:973` | `tracker.cash = ...` → `AttributeError`（`PositionTracker` 无 `cash` 属性） | `tracker._cash = ...`（与 `get_cash()` 同源字段） | 缺陷修复（R-P036-4 升级） |
| C3 | `agents/research_team_v2.py:260` | `update_belief(..., period=period)` → `TypeError`（签名无该参数） | 删除 `period=period` 实参 | 缺陷修复（R-P036-4 升级） |
| C4 | `agents/agent_framework.py:1386 / 1401` | `_execute_trade(quantity=float)`（`current_qty` 为 float） | `int(trade_qty)`（数量本为 100 倍数，截断无实际影响） | 类型契约对齐 |

---

## 2. 任务拆解

| ID | 批次 | 任务 | 对应 | 错误数 |
|----|------|------|------|--------|
| **B1** | 代码 + CI | 修复 7 文件 14 条 + `tests.yml` target 加 7 面（`scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`） | D2 | 14 |
| **B2** | 代码 + CI | 修复 `agents/` 11 文件 96 条 + target 加 `agents` | D2 | 96 |
| **B3** | 代码 + CI | 修复 `filter/` 7 文件 21 条 + **删除** `[[tool.mypy.overrides]] filter.*` + target 加 `filter` | D2 / D5 | 21 |
| **D1** | 文档 | 每批 `PROGRESS §3.41.x` + `CHANGELOG` 条目 + 本文件 §11 实测回填 | —— | —— |

**计数**：14 + 96 + 21 = **131**（CI 对齐口径 = 本地口径，D1 定论）。

---

## 3. 实施顺序与依赖

```text
B1：修 14 条 → 本地 8 面 mypy 0 → tests.yml 扩 8 面 → pytest/black/golden 复验 → 提交
B2：修 96 条 → 本地 9 面 mypy 0 → tests.yml 扩 9 面 → 复验 → 提交
B3：修 21 条 → 本地 filter（无 override）0 → 删 override → 10 面 0 + `mypy core` 仍 0 → 复验 → 提交
```

- **B1 → B2 → B3** 严格串行（D2）；每批 = 1 主提交（代码 + workflow）+ 1 回填提交。
- **红态**：每批 Step 9 首跑必须出示**修复前**读数（§5 表），绿态 = 同 target 0 error。
- **B2 依赖 B1 的门禁**：target 是累加的，B2 的绿态含 B1 面。
- **B3 前置**：`mypy filter`（无 override）0 **之后**才删 override（D5 / F-S2-P036-1）。

---

## 4. 精确变更规格

> 锚点为实施前 HEAD `65da5f9`；净行数以 `git diff --numstat` 为准（§11 回填）。

### 4.1 `.github/workflows/tests.yml` —— mypy 步骤三阶段（L45-46）

**B1 后**（1 行）：

```yaml
        run: python -m mypy --explicit-package-bases --check-untyped-defs core scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library
```

**B2 后**：追加 `agents`。**B3 后**：追加 `filter`（最终 10 面，DESIGN D2）。

**约束**：禁止 `|| true` / `continue-on-error`；`test` job 其余行逐字不动；`lock-check` job 零改动。

### 4.2 B1 —— 14 条逐条规格

| # | 文件:行 | 错误码 | 根因 | 层 | 改法（运行期零变更） |
|---|---------|--------|------|----|---------------------|
| 1 | `strategy_evaluation/evaluator.py:74` | assignment | `row = {"name": name}` 推断 `dict[str, str]` | L3 | `row: dict[str, Any] = {"name": name}`（`Any` 已导入） |
| 2 | `order_strategy/strategies.py:30` | assignment | `fill_timestamps: list = None` | L3 | `fill_timestamps: list \| None = None`；`__post_init__` L33-34 不动 |
| 3 | `order_strategy/strategies.py:374` | no-any-return | `volume` 为 Any → `total_impact` Any | L3 | `total_impact: float = temporary_impact + permanent_impact` |
| 4 | `strategy_evaluation/stats.py:139` | no-any-return | `np.log(rho)` Any → `half_life` Any | L3 | `half_life: float = -np.log(2) / np.log(rho)` |
| 5 | `strategy_evaluation/stats.py:169` | assignment | `turnover = 0` 推断 int | L3 | L167 改 `turnover: float = 0` |
| 6 | `scripts/external_benchmark/verify_p015.py:119` | no-any-return | `verify_case` 声明 `-> None`（L78）却 `return pv_v3` | L3 返回注解 | L78 改 `-> Optional[np.ndarray]`；L124 裸 `return` 不动 |
| 7 | `scripts/external_benchmark/verify_p015.py:223` | no-any-return | 同 #6 | 同 #6 | 同 #6 自动消 |
| 8 | `scripts/external_benchmark/verify_p015.py:337` | func-returns-value | 同 #6（mypy 认为只返回 None） | 同 #6 | 同 #6 自动消 |
| 9 | `scripts/external_benchmark/_spec.py:101` | no-any-return | `np.nan_to_num(...)` → Any | L3 | `s: np.ndarray = np.nan_to_num(signal_row, nan=0.0)` + `return np.asarray(s > 0)` |
| 10 | `scripts/external_benchmark/_spec.py:104` | no-any-return | `np.abs(s)` → Any | L3 | `abs_s: np.ndarray = np.abs(s)` + `return np.asarray(abs_s >= threshold)` |
| 11 | `batch_backtest/engine.py:117` | union-attr | `run_factors` 无 `factor_db` 守卫（U-b） | **L1** | `run_factors` 顶部加 `if self.factor_db is None: raise ValueError("未提供因子数据库")`（**C1**） |
| 12 | `cli.py:48` | arg-type | `factor_weights=None`，字段声明 `dict[str, float]`（config L261） | L3 | 改 `factor_weights={}`（`core/factor.py:487` `or {}`，等价） |
| 13 | `cli.py:87` | union-attr | `engine.dm: IDataManager \| None`，`setup()` 后已赋值 | L2 | `engine.setup()` 后插 `dm = engine.dm` + `assert dm is not None`，L87-88 改用 `dm` |
| 14 | `cli.py:88` | union-attr | 同 #13 | 同 #13 | 同 #13 自动消 |

### 4.3 B2 —— 96 条按文件簇规格

> 计数实测（@`65da5f9`）：guru 26 / agent_framework 17 / strategy_allocator 9 / assumption_monitor 9 / auto_parameter_optimizer 8 / style_reflection_engine 8 / multi_strategy_engine 6 / style_drift_analysis 5 / sentiment_framework 5 / hierarchical_bayesian_agent 2 / research_team_v2 1 = **96**。

#### 4.3.1 `agents/guru_agent_v2.py` —— 26 条（25 + 1）

- **根因（25 条：union-attr 24 + index 1@L330）**：`self.guru_data = ...get(guru_id)` 推断 `dict | None`，尽管 L186-188 已 `raise`。改法（**零行为变更**，守卫原样）：
  ```python
  guru_data = GuruAgentV2._loader_cache[data_dir_str].get(guru_id)
  if guru_data is None:
      available = GuruAgentV2._loader_cache[data_dir_str].list_gurus()
      raise ValueError(f"未知Guru: {guru_id}。可用: {available}")
  self.guru_data: dict[Any, Any] = guru_data
  ```
  一处收窄消 25 条（L257/279/312/318/328/329/330/371/396/407/419/422/425/429/444/460-466/475/479/579）。
- **L452**（no-any-return）：`return bool(date.day == self.cfg.rebalance_day)`（`date.day` 经 pandas Any）。

#### 4.3.2 `agents/agent_framework.py` —— 17 条

| 行 | 错误码 | 簇 | 改法 |
|----|--------|----|------|
| 433 / 514 / 596 / 1149 | no-any-return ×4 | `date.day` 经 pandas Any | `return bool(date.day == self.cfg.rebalance_day)` |
| 692 / 754 | return-value ×2 | `_weighted_vote` / `_confidence_weighted` 声明 `-> dict[str, Any]` 却 `return None`；调用方 `_aggregate_stock_signals`（L661）已声明 `dict \| None` | 两处返回注解改 `dict[str, Any] \| None`（§8 已登记） |
| 1144 | no-any-return | `day_industry[stock]` Any | `value: str = day_industry[stock]` + `return value` |
| 1239 | arg-type | 传 `UniverseConfig`，`UniverseFilter` 要 `UniverseFilterConfig` | `UniverseFilter(self.dm, UniverseFilterConfig.from_universe_config(self.cfg.universe))`（与 `core/engine_v2.py:218` 同口径；补 import） |
| 1292 | union-attr | `self.universe: UniverseFilter \| None`，`setup()` 后已赋值（U-a） | 方法内 `universe = self.universe` + `assert universe is not None`，改用 `universe` |
| 1334-1337 / 1434 | union-attr ×5 | `self.dm: DataManager \| None`（U-a，`setup()` 后已赋值） | 各自方法首行 `dm = self.dm` + `assert dm is not None`，改用 `dm` |
| 1386 / 1401 | arg-type ×2 | `trade_qty` 为 `float \| int`（`current_qty` float） | 实参改 `int(trade_qty)`（**C4**） |
| 1447 | var-annotated | `results = {...}` 推断过窄 | `results: dict[str, Any] = {...}` |

#### 4.3.3 `agents/style_reflection_engine.py` —— 8 条（1 根因）

L203 `result = {...}`（混合值）推断过窄 → `result: dict[str, Any] = {...}`，L218（index + call-overload）、L222（union-attr ×3）、L235（index + call-overload）随根因消除。

#### 4.3.4 `agents/strategy_allocator.py` —— 9 条

| 行 | 错误码 | 改法 |
|----|--------|------|
| 72 / 313 / 416 / 492 / 533 / 579 / 653 / 839 | no-any-return ×8（返回 `np.ndarray`） | 返回前局部注解收窄：`result: np.ndarray = <expr>`；或 `return np.asarray(<expr>)`（已是 ndarray 时不复制） |
| 793 | misc | `inspect.signature(allocator_cls.__init__)` → `inspect.signature(allocator_cls)`（等价：类签名不含 `self`，L794 的 `- {"self"}` 保留无害） |

#### 4.3.5 `agents/sentiment_framework.py` —— 5 条

| 行 | 错误码 | 改法 |
|----|--------|------|
| 783 / 784 / 789 | operator / no-any-return / assignment | **根因 L736**：`self.rate_limiter = {...}` 推断 `dict[str, dict[str, None \| int]]` → 注解 `self.rate_limiter: dict[str, dict[str, Any]] = {...}`，三错全消 |
| 228 | assignment | `keywords` 同分支既被赋 `np.random.choice(...)`（ndarray）又被赋 `["正常","平稳"]` → 首个赋值前声明 `keywords: Any` |
| 796 | var-annotated | `by_tier: dict[str, int] = {}` |

#### 4.3.6 `agents/auto_parameter_optimizer.py` —— 8 条

- L984-986 / 988×2（list-item ×3 + attr-defined ×2）：均在 `if __name__ == "__main__":` 演示块——`roles` 被 `compute_role_weights(roles: list[str], ...)` 推断为 `list[str]`。改法：`roles: list[Any] = [MockRole("A", 1.0, 0.7), ...]`（演示块，1 行消 5 条）。
- L325 / 339 / 426（no-any-return）：返回 `float` / `np.ndarray` / `dict` 的局部注解收窄（同 §4.3.4 配方）。

#### 4.3.7 `agents/assumption_monitor.py` —— 9 条

- L220 / 327 / 596 / 709（var-annotated）：`checks: list[Any] = []`。
- L427 / 434 / 439 / 552（no-any-return）：`np.sum` / `np.exp` 返回 Any → 局部注解（如 `total: float = np.sum(np.abs(w_new - w_old)) / 2`）。
- L821（no-any-return）：返回 ndarray → 局部注解。

#### 4.3.8 `agents/multi_strategy_engine.py` —— 6 条

| 行 | 错误码 | 改法 |
|----|--------|------|
| 111 | assignment | 首分支改 `self.pending_queue: PendingOrderQueue \| None = PendingOrderQueue(...)`（`else` 分支 `= None` 不动） |
| 587 | arg-type | 同 §4.3.2 L1239：经 `UniverseFilterConfig.from_universe_config(self.cfg.universe)` |
| 777 / 909 | var-annotated | `strategy_daily_returns: dict[str, list[float]] = {}` / `nav_history: list[float] = []`（按使用形态取具体元素类型） |
| 829 | union-attr | `allocator` 由 L756 `= None` 推断 Optional；L829 在 `if enable_dynamic_allocation and i > 0` 分支内（U-a）→ 块内 `assert allocator is not None` |
| 973 | attr-defined | `tracker.cash` → `tracker._cash`（**C2**；`PositionTracker` 仅 `_cash` + `get_cash()`） |

#### 4.3.9 `agents/style_drift_analysis.py` —— 5 条

- L221 / 243 / 257（no-any-return float）：`min(...)` 参数经 pandas Any → 局部注解（`drift: float = ...`）。
- L250（union-attr）：`self.baseline_profile.get(...)`，`baseline_profile` 为 `dict | None` → **Step 9 读构造期初始化定性**：若构造期恒赋值 → L2 `profile = self.baseline_profile; assert profile is not None`；否则按 L1 fail-fast 登记（优先 L2）。
- L806（assignment）：演示块循环变量 `v` 与同作用域既有 float `v` 冲突 → 重命名 `violation`（仅演示块）。

#### 4.3.10 `agents/hierarchical_bayesian_agent.py` —— 2 条

- L220（no-any-return）：局部注解 `value: float = ...`。
- L287（var-annotated）：`active_events: list[Any] = []`。

#### 4.3.11 `agents/research_team_v2.py` —— 1 条

- L259-260（call-arg）：`update_belief(factor_name, ..., period=period)`，实际签名（L424）无 `period` → **删除 `period=period` 实参（C3）**；L254 `capability_belief.update(lr, period=period)` 不在报错面，不动。

### 4.4 B3 —— 21 条逐条规格

#### 4.4.1 `filter/universe_filter_clean.py` —— 13 条

| 行 | 错误码 | 改法 |
|----|--------|------|
| 108 | var-annotated | `self._prefix_info: dict[str, bool] = {}`（L184 赋 `any(...)` → bool） |
| 542-552（`get_universe_stats`，6 条） | union-attr | L542-543 `if self._tradable_mask is None: self.build_masks()` 之后（`build_masks` 副作用**不被 mypy 追踪**）→ L544 插 `mask = self._tradable_mask` + `assert mask is not None`，L545-552 改用 `mask` |
| 563-573（`get_mask_summary`，6 条） | union-attr | 同型：L563-564 后插 `mask = self._tradable_mask` + `assert mask is not None`，L567-573 改用 `mask` |

> 依据：`build_masks()`（L139-150）调用 `_build_suspend_mask()` 等赋值各 `_*_mask`，属**既有运行期前提**（U-a，O-D3-P036-3 的 L2 模板）。

#### 4.4.2 `filter/prefix.py:359` —— 1 条

`create_filter` 声明 `-> PrefixFilter` 但 `RegexPrefixFilter(BaseFilter)` 与 `PrefixFilter` 无继承关系 → 返回注解改 `BaseFilter`（L355 `BoardFilter(PrefixFilter)` 与 L357 `PrefixFilter` 均兼容；`filter/__init__.py` 的 `create_filter` 是另一函数，不在本批）。

#### 4.4.3 `filter/na_factor.py` —— 2 条

- L352（arg-type）：`NAFactorFilter(strategy=strategy, ...)`，`strategy: str` vs 构造器 `Literal[...]` → **放宽 L31 构造器注解为 `str`**（实现本就接受任意字符串并内部判定，注解与实现对齐）。
- L354（no-any-return）：`strategies` 字典值混类 → 注解 `strategies: dict[str, type[NAFactorFilter]]`（L176/187/200 均 `NAFactorFilter` 子类；L219 `CrossSectionalNAFilter` 为 `BaseFilter` 子类 → 若混入则改 `dict[str, type[BaseFilter]]`，Step 9 以实读定）。

#### 4.4.4 `filter/market_cap.py:381` / `industry.py:392` / `extended.py:331` / `custom.py:438` —— 4 条

工厂字典 `filters` 值混类 → `filters[filter_type](**kwargs)` 返回 Any。改法：字典注解 `dict[str, type[BaseFilter]]`（各文件按实际基类；`custom` 的五个类均 `BaseFilter` 子类）。

#### 4.4.5 `filter/custom.py:195` —— 1 条

`filter_obj` 在 L192 绑 `ExpressionFilter`、L195 绑 `CustomFunctionFilter` → L192 前声明 `filter_obj: BaseFilter`（两分支均兼容；或分支内改名，二选一，Step 9 取前者）。

### 4.5 不改动清单（复核留证）

| 位置 | 状态 |
|------|------|
| `core/**`（含 `tracker.py` / `execution.py` / `engine_v2.py`） | 逐字不动 |
| `tests/**`（含 `tests/golden/*.json` 7 份 13 用例） | 逐字不动 |
| `pyproject.toml` 的 `mypy~=2.4.1`（B0） | 不动 |
| `filter.* ignore_errors` override | **B3 主提交内删除**（注释一并删） |
| `agents/` 的 `if __name__ == "__main__":` 演示块语义 | 除 L806 变量重命名与 L984 `roles` 注解外不动 |

---

## 5. 验证规格（V1-V6 落地）

| 批 | 红态（修复前，实测 @`65da5f9`） | 绿态判据 |
|----|-----------------------------------|----------|
| **B1** | `mypy core scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library` = **14 errors / 7 files（checked 68 source files）**；码分布 no-any-return 6 / union-attr 3 / assignment 3 / arg-type 1 / func-returns-value 1 | 同命令 **0 error**；本地 + 复刻 venv（钉 `numpy==2.4.6`）双口径 |
| **B2** | `mypy agents` = **96 errors / 11 files（checked 14 source files）** | B1 面 + `agents` = 0；双口径 |
| **B3** | `mypy filter --config-file <无 override>` = **21 errors / 7 files（checked 10 source files）**；删 override 后 `mypy core` 将渗入 21 | filter 0 且 10 面 0 且 `mypy core` 仍 0；双口径 |
| **V5** | —— | golden 13 零重录 / pytest 760 / AST except 22 / `git diff` 中 `def` 行仅 §8 五处返回注解差异 |
| **V6** | —— | `grep '# type: ignore'` 在 10 面 = **0**（含带 code） |

**每批复验命令（Python312 + `MPLBACKEND=Agg`）**：

```powershell
python -m pytest tests/ -q
python -m black --check core tests
python -m mypy --explicit-package-bases --check-untyped-defs <批 target>
python -m pytest tests/ -k golden -q
python -m uv lock --check   # 或 uv lock --check
```

---

## 6. 测试规格

**本批不新增 pytest 用例（I4 的 X=0）**——理由：

1. 判据本身就是 `mypy` 退出码与错误数，CI 的 mypy 步骤即为回归测试，新增 pytest 会重复已有信号；
2. 行为守恒由 golden 13 + 全量 760 覆盖；
3. 4 项行为变更（C1-C4）中 C2/C3 属缺陷修复，其触发路径依赖动态分配 / 贝叶斯信念层，构造单测成本高于收益 → 由 Step 9 运行时探针（`%TEMP%` 脚本）留证，不入库。

**Step 9 留证要求**：每批「红读数 → 绿读数」两次 mypy 输出原文；C1-C4 各一条最小探针（`%TEMP%`）。

---

## 7. 低效排除

| # | 候选 | 排除理由 |
|---|------|----------|
| 1 | `# type: ignore` 批量压制 | 违反 D3 / I7；本批 0 使用 |
| 2 | `--follow-imports=silent` | 治标，D3 明令禁止 |
| 3 | 给 `agents` 新增 `ignore_errors` override | 与 G2 真修冲突 |
| 4 | 开 `strict` / `warn_unused_ignores` | D7 已裁决不做 |
| 5 | 改 `core/tracker.py` 加 `cash` property | 扩大 B2 面到 core；`_cash` 直写与 `get_cash()` 同源，最小改动（C2） |
| 6 | 为 `date.day` 引入 `cast(Timestamp, ...)` | pandas 恒 Any，cast 目标不诚实；用 `bool(...)` |
| 7 | 拆分 B2 为 B2a/B2b | 96 条簇已清晰，单批可验收（O-D3-P036-2 仅作备选） |
| 8 | 为 `_spec.py` 复制两份返回数组 | `np.asarray` 对 ndarray 不复制，避免内存翻倍 |

---

## 8. 接口签名与回退点

| 对象 | 变化 | 回退点 |
|------|------|--------|
| `cli.py` `run()` | 无（仅局部变量 `dm`） | 还原 2 行 |
| `BatchBacktestEngine.run_factors` | 无签名变化；新增 fail-fast（C1） | 删 2 行守卫 |
| `verify_case` | **返回注解** `-> None` → `-> Optional[np.ndarray]`（无运行期变化） | 还原注解 |
| `_weighted_vote` / `_confidence_weighted` | **返回注解** → `dict[str, Any] \| None`（私有方法） | 还原注解 |
| `UniverseFilter(...)` 调用点（agents 2 处） | 实参经 `from_universe_config` 转换 | 还原 2 行 |
| `create_filter`（filter/prefix.py） | **返回注解** `-> PrefixFilter` → `-> BaseFilter` | 还原注解 |
| `NAFactorFilter.__init__` | **注解** `strategy: Literal[...]` → `str` | 还原注解 |
| `tests.yml` mypy 行 | 三次追加 target | 每批 revert 主提交即回退 |
| `PositionTracker._cash`（外部直写） | agents 侧 1 行（C2） | 还原 1 行 |

**回退粒度**（DESIGN §6）：B1 / B2 / B3 各自 revert 主提交即回到上一批状态；B3 revert 同时恢复 override 与 9 面 target。

---

## 9. 实施期裁决（预登记）

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-I-P036-1 | 观察 | **I2 机械口径澄清**：返回注解修正会触碰 `def` 行；判定改为「`def` 行仅允许返回注解差异，参数/函数名逐字不变」 | 已写入 §1 前提 4；Step 6 复核 |
| F-I-P036-2 | 观察 | C2（`tracker.cash`）与 C3（`period`）为**真实缺陷**——若 Step 9 探针证明触发路径可达，按 P-029/P-031 口径升级登记（R-P036-4 预期内） | Step 9 判定 |
| F-I-P036-3 | 观察 | `style_drift_analysis.baseline_profile` 的 U-a/U-b 定性未在规划期闭合（构造期初始化路径待读） | Step 9 读码定性；优先 L2 |
| F-I-P036-4 | 观察 | `na_factor.strategies` 字典元素基类（`NAFactorFilter` vs `BaseFilter`）以实读定 | Step 9 定 |
| O-I-P036-1 | 观察 | 复刻 venv 必须钉 `numpy==2.4.6`（D1 / F-S4-P036-4）；否则 129 假口径复现 | 每批双口径复验前先 `pip install numpy==2.4.6` 并删 `.mypy_cache` |

---

## 10. 下一 Step 复核重点（Step 6 实施 Review）

1. **锚点**：§4 的 21 组文件:行是否与 `65da5f9` 实读一致（尤其 B2 的 96 条分文件计数 26/17/9/9/8/8/6/5/5/2/1）；
2. **分层合规**：L2 `assert` 是否全部能指出既有前提；L1 是否仅 C1 一处新增 fail-fast；L4 是否 0 使用；
3. **行为变更**：C1-C4 四项是否可从读码复现「现网崩溃 / 类型错配」；
4. **I2**：`def` 行仅 §8 五处返回注解差异，参数零变更；
5. **红态**：§5 三批读数（14/96/21）是否与实测逐字一致；
6. **门禁链**：`tests.yml` 三阶段 target 是否与 D2 最终 10 面一致、无 `|| true`；
7. **B3 绑定**：override 删除是否与 filter 0 + `mypy core` 0 同批（D5）。

---

## 11. Step 9 实施记录（待填）

<!-- Step 9 后回填：每批红→绿 mypy 原文、净行数、C1-C4 探针读数、门禁终态 -->
