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
4. **I2 的机械口径澄清（Step 6 更正 F-S6-P036-2；Step 8 精化 F-S8-P036-1）**：`git diff` 中删除的 `def` 行必须**逐字回归**，唯一允许的差异是**注解修正**——**7 处 def 行**（返回注解 ×7：`verify_case` / `_weighted_vote` / `_confidence_weighted` / `create_prefix_filter` / `create_na_filter` / `create_market_cap_filter` / `create_industry_filter`）+ **1 处参数注解行**（`NAFactorFilter.__init__` 的 `strategy: Literal[...]` → `str`，位于**续行 L33**，不触 def 行 L31）；参数名 / 参数默认值 / 函数名零变更。
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
| 6 | `scripts/external_benchmark/verify_p015.py:119` | no-any-return | `verify_case` 声明 `-> None`（L78）却 `return pv_v3` | L3 返回注解 | L78 改 `-> np.ndarray \| None`（文件有 `from __future__ import annotations` 且无 typing import——Step 6 更正 F-S6-P036-4）；L124 裸 `return` 不动 |
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
| 1239 | arg-type | 传 `UniverseConfig`，`UniverseFilter` 要 `UniverseFilterConfig` | `UniverseFilter(self.dm, UniverseFilterConfig.from_universe_config(self.cfg.universe))`（与 `core/engine_v2.py:218` 同口径；L42 既有 `from filter.universe_filter_clean import UniverseFilter` 行**追加** `UniverseFilterConfig`——F-S6-P036-6） |
| 1292 | union-attr | `self.universe: UniverseFilter \| None`，`setup()` 后已赋值（U-a） | 方法内 `universe = self.universe` + `assert universe is not None`，改用 `universe` |
| 1334-1337 / 1434 | union-attr ×5 | `self.dm: DataManager \| None`（U-a，`setup()` 后已赋值） | 各自方法首行 `dm = self.dm` + `assert dm is not None`，改用 `dm` |
| 1386 / 1401 | arg-type ×2 | `trade_qty` 为 `float \| int`（`current_qty` float） | 实参改 `int(trade_qty)`（**C4**） |
| 1447 | var-annotated | `results = {...}` 推断过窄 | `results: dict[str, Any] = {...}` |

> **Step 10 落点注（F-S10-P036-2，审计发现当轮登记）**：上表 L1292 / L1334-1337 / L1434 三组实际实现为**方法内直断**（`assert self.universe is not None` / `assert self.dm is not None`，未引入局部变量改名）——零语义差、mypy 收窄等效、均在 U-a 前提上；CHECKLIST B3 已按实际落码口径记载，规格原文保留不改。

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
| 587 | arg-type | 同 §4.3.2 L1239：经 `UniverseFilterConfig.from_universe_config(base_config.universe)`（实际变量为 `base_config`——Step 6 更正 F-S6-P036-5）；L43 import 行追加 `UniverseFilterConfig` |
| 777 / 909 | var-annotated | `strategy_daily_returns: dict[str, list[float]] = {}` / `nav_history: dict[str, list[float]] = {name: [] for name in strategy_names}`（L909 实为 dict 推导式——Step 6 更正 F-S6-P036-5） |
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
| 522 / 526（`filter_stocks` L498-531，2 条） | union-attr | L511-512 `if self._tradable_mask is None: self.build_masks()` 前提成立（`build_masks` 副作用不被 mypy 追踪）→ L520 `mask = mask_map.get(...)` 后插 `assert mask is not None`，L522/526 自动收窄（**Step 6 更正 F-S6-P036-1**——原规格误并入 get_universe_stats） |
| 545 / 550-552（`get_universe_stats`，4 条） | union-attr | L542-543 `if self._tradable_mask is None: self.build_masks()` 之后 → L544 插 `mask = self._tradable_mask` + `assert mask is not None`，L545/550-552 改用 `mask`（Step 6 更正：**4 条**非 6 条） |
| 567-573（`get_mask_summary`，6 条） | union-attr | 同型：L563-564 后插 `mask = self._tradable_mask` + `assert mask is not None`，L567-573 改用 `mask` |

> 依据：`build_masks()`（L139-150）调用 `_build_suspend_mask()` 等赋值各 `_*_mask`，属**既有运行期前提**（U-a，O-D3-P036-3 的 L2 模板）。

#### 4.4.2 `filter/prefix.py:359` —— 1 条

`create_prefix_filter`（L343——**Step 6 更正 F-S6-P036-3**：实名，易与 `filter/__init__.py:130` 的另一 `create_filter` 混淆）声明 `-> PrefixFilter` 但 `RegexPrefixFilter(BaseFilter)` 与 `PrefixFilter` 无继承关系 → 返回注解改 `-> BaseFilter`（L355 `BoardFilter(PrefixFilter)` 与 L357 `PrefixFilter` 均兼容；全仓无调用点、仅 `filter/__init__.py` re-export，注解变更安全）。

#### 4.4.3 `filter/na_factor.py` —— 2 条

- L352（arg-type）：`NAFactorFilter(strategy=strategy, ...)`，`strategy: str` vs 构造器 `Literal[...]`（L33）→ **放宽 L31 构造器参数注解为 `str`**（实现本就接受任意字符串并内部判定，注解与实现对齐；属**参数注解**差异——Step 6 归类更正 F-S6-P036-2）。
- L354（no-any-return）：`strategies` 字典值混类——L344-346 为 `NAFactorFilter` 子类、L347 `CrossSectionalNAFilter(BaseFilter)` 非其子类（**Step 6 实读定案，F-I-P036-4 关闭**）→ 注解 `strategies: dict[str, type[BaseFilter]]`，且 **`create_na_filter`（L332）返回注解须同批改 `-> NAFactorFilter` → `-> BaseFilter`**（否则引入 return-value 新错；全仓无调用点，安全）。

#### 4.4.4 `filter/market_cap.py:381` / `industry.py:392` / `extended.py:331` / `custom.py:438` —— 4 条

工厂字典 `filters` 值混类 → `filters[filter_type](**kwargs)` 返回 Any。改法（**Step 6 读码定案 F-S6-P036-2**）：

| 文件 | 字典混入实况 | 字典注解 | def 行返回注解 |
|------|-------------|---------|----------------|
| `market_cap.py`（L358 `-> MarketCapFilter`） | L374-375 `MarketCapRatioFilter` / `MarketCapMomentumFilter` 为 `BaseFilter` 子类 | `dict[str, type[BaseFilter]]` | **须同批改 `-> BaseFilter`**（否则 return-value 新错） |
| `industry.py`（L371 `-> IndustryFilter`） | L386 `IndustryRotationFilter` 为 `BaseFilter` 子类 | `dict[str, type[BaseFilter]]` | **须同批改 `-> BaseFilter`** |
| `extended.py`（L307 `-> BaseFilter`） | 六类全 `BaseFilter` 子类 | `dict[str, type[BaseFilter]]` | 不变 |
| `custom.py`（L416 `-> BaseFilter`） | 五类全 `BaseFilter` 子类 | `dict[str, type[BaseFilter]]` | 不变 |

四个工厂函数全仓无调用点（仅 `filter/__init__.py` re-export），返回注解放宽安全。

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
| `verify_case` | **返回注解** `-> None` → `-> np.ndarray \| None`（F-S6-P036-4：无 typing import，用 PEP 604 形式） | 还原注解 |
| `_weighted_vote` / `_confidence_weighted` | **返回注解** → `dict[str, Any] \| None`（私有方法） | 还原注解 |
| `UniverseFilter(...)` 调用点（agents 2 处） | 实参经 `from_universe_config` 转换；2 文件 import 行追加 `UniverseFilterConfig` | 还原 2 行 + import |
| `create_prefix_filter`（filter/prefix.py L343） | **返回注解** `-> PrefixFilter` → `-> BaseFilter` | 还原注解 |
| `create_na_filter`（filter/na_factor.py L332） | **返回注解** `-> NAFactorFilter` → `-> BaseFilter`（Step 6 补录） | 还原注解 |
| `create_market_cap_filter`（market_cap.py L358） | **返回注解** `-> MarketCapFilter` → `-> BaseFilter`（Step 6 补录） | 还原注解 |
| `create_industry_filter`（industry.py L371） | **返回注解** `-> IndustryFilter` → `-> BaseFilter`（Step 6 补录） | 还原注解 |
| `NAFactorFilter.__init__` | **参数注解** `strategy: Literal[...]` → `str`（Step 6 归类更正：参数注解非返回注解） | 还原注解 |
| `tests.yml` mypy 行 | 三次追加 target | 每批 revert 主提交即回退 |
| `PositionTracker._cash`（外部直写） | agents 侧 1 行（C2） | 还原 1 行 |

**回退粒度**（DESIGN §6）：B1 / B2 / B3 各自 revert 主提交即回到上一批状态；B3 revert 同时恢复 override 与 9 面 target。

---

## 9. 实施期裁决（预登记）

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-I-P036-1 | 观察 | **I2 机械口径澄清**：返回注解修正会触碰 `def` 行；判定改为「`def` 行仅允许返回注解差异，参数/函数名逐字不变」 | 已写入 §1 前提 4；Step 6 复核 |
| F-I-P036-2 | 观察 | C2（`tracker.cash`）与 C3（`period`）为**真实缺陷**——若 Step 9 探针证明触发路径可达，按 P-029/P-031 口径升级登记（R-P036-4 预期内） | Step 9 判定 |
| F-I-P036-3 | 观察 | `style_drift_analysis.baseline_profile` 的 U-a/U-b 定性——**Step 6 已闭合（O-S6-P036-1）**：`AntiDriftAgent.__init__` L539 恒调 `_setup_baseline_profile()` → `set_baseline` L126 赋值 → L250 定性 **U-a**；L145/179/198/225 的 None 守卫属防御式冗余（构造期恒赋值），不得引为「return 0.0 降级」依据（D4 Step 4 原则） | Step 9 用 L2 assert（`profile = self.baseline_profile` + `assert profile is not None`） |
| F-I-P036-4 | 观察 | `na_factor.strategies` 字典元素基类——**Step 6 已定案**：L347 `CrossSectionalNAFilter(BaseFilter)` 混入 → `dict[str, type[BaseFilter]]` + `create_na_filter` 返回注解同批改（§4.4.3） | 已并入规格 |
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

## 11. Step 6 实施 Review 记录（GLM-5.3-Flash，2026-11-17）

> **基座**: **GLM-5.3-Flash ≠ IMPL 作者 DeepSeek-V4.1-Flash** → **RULE-5 异构成立**。
> **复审对象**: 本文档 Step 5 版（提交 `ec33dd7`）；复审时点 HEAD `b277313`（代码零变更，纯规格复审）。
> **方法**: E1 锚点机械复核（B1 全 14 条 / B2 11 文件簇代表锚点 + 计数对账 / B3 全量读码）+ E2 门禁基线独立复测 + E3 红态三批复测 + E4 七项裁决。

### 11.1 E2 门禁基线独立复测（Python312 + `MPLBACKEND=Agg`）

| 门禁 | IMPL 声称 | 实测 | 结果 |
|------|-----------|------|------|
| 全量 pytest | 760 | **760 passed, 172 warnings**（82.98s） | ✅ |
| black `--check core tests` | 121 | **121 files would be left unchanged** | ✅ |
| mypy `core`（仓库 config） | 0 / 37 files | **Success: no issues found in 37 source files** | ✅ |
| pyproject override 块 | L121-123 + 注释 L116-120（B3 待删面） | 读码确认在位 | ✅ |

### 11.2 E3 红态三批复测

| 批 | IMPL 声称 | 实测 | 结果 |
|----|-----------|------|------|
| B1 面（8 target） | 14 / 7 files（checked 68） | **Found 14 errors in 7 files (checked 68 source files)** | ✅ |
| `agents` | 96 / 11（14） | **Found 96 errors in 11 files (checked 14 source files)** | ✅ |
| `filter`（无 override ini） | 21 / 7（10） | **Found 21 errors in 7 files (checked 10 source files)** | ✅ |

### 11.3 E4 七项裁决（对应 §10）

| # | 复核点 | 裁决 |
|---|--------|------|
| 1 | 锚点 | B1 14 条全命中；B2 分文件计数 26/17/9/9/8/8/6/5/5/2/1 与实测对账一致；B3 **分组错误 1 处**（F-S6-P036-1：L522/526 属 `filter_stocks` 非 `get_universe_stats`）——已当轮更正 |
| 2 | 分层合规 | **成立**——全部 L2 assert 前提可指认（`engine.dm`/`self.universe` 由 setup 赋值、`allocator` 由 enable_dynamic_allocation 分支赋值、`build_masks` 副作用、`baseline_profile` 构造期 L539 恒调）；L1 仅 C1 一处新增 fail-fast；L4 = **0** |
| 3 | 行为变更 C1-C4 | **全部读码复现**——C1 守卫与 `run_all_factors` L81-82 逐字源 / C2 `PositionTracker` 仅 `_cash`（tracker L179）无 `cash` 属性 / C3 `update_belief`（hierarchical L424）签名无 `period` / C4 `current_qty` 经 `get_position` 为 float |
| 4 | I2 | **清单 5 处 → 8 处 def 行 + 1 处参数注解**（F-S6-P036-2：三个 filter 工厂返回注解遗漏 + `NAFactorFilter.__init__` 属参数注解）——当轮更正 §1 前提 4 / §8 |
| 5 | 红态 | 14 / 96 / 21 逐字复现 ✅（合计 131 ✓） |
| 6 | 门禁链 | tests.yml L45-46 现 `core` 单面；三阶段 8→9→10 面与 DESIGN D2 一致；无 `\|\| true` ✅ |
| 7 | B3 绑定 | §3 顺序「先 filter 0 → 删 override → `mypy core` 仍 0」与 D5 一致 ✅ |

### 11.4 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S6-P036-1** | **P2** | §4.4.1 B3 union-attr 方法归属错误：L522/526 属 **`filter_stocks`**（L498-531），非 `get_universe_stats`；后者实为 **4 条**（545/550-552）。原修复规格不覆盖 filter_stocks 的 2 条（且「L544 插 mask」的行号在 filter_stocks 中不存在） | **当轮回写 §4.4.1**——补 `filter_stocks` 行（L520 后插 `assert mask is not None`，L522/526 自动收窄）；get_universe_stats 改 4 条。文件总数 13 不变 |
| **F-S6-P036-2** | **P2** | §4.4.4/§8 I2 清单错误：market_cap（字典混入 2 个 `BaseFilter` 子类）/ industry（混入 1 个）/ na_factor（混入 `CrossSectionalNAFilter`）**仅改字典注解会引入 return-value 新错**——三个工厂函数返回注解须同批改 `-> BaseFilter`；且 `NAFactorFilter.__init__` 属**参数注解**非返回注解。I2 def 行差异 5 → **8 处** | 当轮回写 §1 前提 4 / §4.4.3 / §4.4.4 / §8；四个工厂全仓无调用点（仅 re-export），注解变更安全 |
| F-S6-P036-3 | P3 | §4.4.2/§8 把 prefix.py 工厂写作 `create_filter`——实名 **`create_prefix_filter`**（L343），与 `filter/__init__.py:130` 同名函数易混淆 | 当轮更正命名 |
| F-S6-P036-4 | P3 | §4.2 #6 `-> Optional[np.ndarray]`——verify_p015.py **无 typing import**（仅 `from __future__ import annotations`）→ 改 `-> np.ndarray \| None` 零 import 变更 | 当轮更正 |
| F-S6-P036-5 | P3 | §4.3.8 两处笔误：L587 实际变量为 **`base_config.universe`**（非 `self.cfg.universe`）；L909 `nav_history` 实为 **dict 推导式**（注解应为 `dict[str, list[float]]`，非 `list[float] = []`） | 当轮更正 |
| F-S6-P036-6 | P3 | §4.3.2/§4.3.8 的 `UniverseFilterConfig` 修复需在两文件既有 `from filter.universe_filter_clean import UniverseFilter` 行（L42 / L43）**追加**导入——原规格未注明 | 当轮补注 |
| O-S6-P036-1 | 观察 | **F-I-P036-3 / F-I-P036-4 闭合**（§9 两行已标）——baseline_profile 构造期前提实锤（L250 = U-a）；CrossSectionalNAFilter 混入实锤 | 已并入 §9 |
| O-S6-P036-2 | 观察 | 全部 13 个 agents 文件均已导入 `Any`——`dict[str, Any]` / `list[Any]` 类修复零 import 变更 | 无需改规格 |
| O-S6-P036-3 | 观察 | 局部注解目标变量名以实读为准（hierarchical L220 为 `stability`、auto L325 为 `volatility_penalty` 等）——层级与手法不变，Step 9 落码按实读 | 登记 |

### 11.5 结论与 Step 7 前置条件

**结论**: **pass**（0 P0/P1 / **2 P2 + 4 P3 当轮回写** / 3 观察）——红态三批逐字复现、门禁基线四项一致、C1-C4 全部读码可复现、分层合规成立；B3 修复规格两处缺口（filter_stocks 分组 + 工厂返回注解）已当轮闭合，Step 9 可按更正后规格直接落码。

**Step 7 前置条件**:
1. CHECKLIST 按**更正后** §4 规格编制（含 8 处注解差异清单 + filter_stocks 修复行）；
2. C1-C4 行为变更**单列验收组**（每项一组 DoR/DoD + 探针证据出口）；
3. I7 忽略审计口径按 §1（裸 ignore = 0 且带 code = 0——全程不使用 L4）。

---

## 12. Step 9 实施记录（2026-11-17 完成）

> **基座**: DeepSeek-V4.1-Flash（与 §1-§11 同源）· **实施基点**: `65da5f9` → **代码终态**: `f1fdab4`
> **提交序列**: `e2dafff`（B1）→ `e781b75`（B2）→ `eb3ae55`（B3）→ `43ed468`（numpy 2.5.5 兼容）→ `f1fdab4`（py3.10 / numpy 2.2.6 兼容）

### 12.1 三批红→绿与净行数

| 批 | 红态原文 | 绿态原文 | 提交（净行数） |
|----|----------|----------|----------------|
| B1 | `Found 14 errors in 7 files (checked 68 source files)` | `Success: no issues found in 68 source files` | `e2dafff` 9 文件 **+27 / −18** |
| B2 | `Found 96 errors in 11 files (checked 14 source files)` | `Success: no issues found in 82 source files`（9 面） | `e781b75` 13 文件 **+82 / −61** |
| B3 | `Found 21 errors in 7 files (checked 10 source files)`（无 override ini） | `Success: no issues found in 92 source files`（10 面） | `eb3ae55` 10 文件 **+36 / −34** |

**B1 次生修改**（红→绿过程中新暴露，均在批内闭合）：`fill_timestamps: list | None` 引入 3 处 `.append` union-attr → L168/249/320 各加 `assert order.fill_timestamps is not None`；`verify_case` 返回注解改 union 后 L119/223/124 需 `np.asarray(pv_v3)` ×2 + `return None`；`_run_single_factor` 需独立 `assert self.factor_db is not None`（mypy 不跨方法追踪守卫）。

### 12.2 C1-C4 运行时探针（`%TEMP%\p036_s9_probe_c1c4.py` / `p036_s9_probe_c2.py`）

| 项 | 读数原文（节选） | 判定 |
|----|------------------|------|
| C1 | `C1 VALUE_ERROR: 未提供因子数据库` | ✅ 红态为 `self.factor_db.list_factors()` 的 `AttributeError`（读码），绿态显式 fail-fast |
| C2 | `C2 before: get_cash=100000.0 hasattr(cash)=False` / `C2 old write: get_cash=100000.0 hasattr(cash)=True shadow=42000.0` / `C2 new write: get_cash=42000.0` | ✅ **口径更正**（F-S9-P036-4）：原行为**不是** `AttributeError` 崩溃，而是静默创建影子属性、调资**静默失效**；`_cash` 直写后真实生效 |
| C3 | `C3 params: ['self', 'name', 'evidence', 'evidence_strength']` / `C3 OLD CALL TypeError: got an unexpected keyword argument 'period'` / `C3 NEW CALL bind: OK` | ✅ 真实缺陷（现网 TypeError 路径） |
| C4 | `C4 trade_qty type: float value: 33378.9` / `C4 int(trade_qty): 33378` / `C4 _execute_trade quantity annotation: int` | ✅ 类型契约对齐；数量为 100 倍数，截断无实际影响 |

### 12.3 门禁终态（`f1fdab4`，10 面 = `core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`）

| 门禁 | 读数 |
|------|------|
| mypy · py3.12 + numpy 2.4.6（本机） | `Success: no issues found in 92 source files` |
| mypy · py3.12 + numpy 2.5.5（CI 3.12 复刻） | `Success: no issues found in 92 source files` |
| mypy · py3.10 + numpy 2.2.6 / pandas 2.3.3（CI 3.10 复刻） | `Success: no issues found in 92 source files` |
| mypy `core`（override 删除后，仓库 config） | `Success: no issues found in 37 source files` |
| pytest 全量 | **760 passed**（172 warnings） |
| golden | `pytest -q -k golden` = **13 passed, 747 deselected**；`git status --short tests/golden/` = 空 |
| black | `black --check core tests` = **121 unchanged**；`black --check .` = **188 unchanged** |
| AST | `except Exception`（P-029 口径）= **22** |
| 忽略审计 | 本批新增 `# type: ignore`（10 面 diff）= **0**；既有带 code 4 处（P-036 前） |
| `uv lock --check` | `Resolved 148 packages`，exit **0** |
| tests 计数 | `tests/` .py = **84**，`test_*.py` = **81**（不变） |

### 12.4 实施期发现与分级（F-S9）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S9-P036-1** | **P2** | **门禁双载体遗漏**：扩面只改 `.github/workflows/tests.yml` 会让 `tests/test_p024_ci_gate_alignment.py::test_ci_mypy_flags_match_local_gate` 变红（`scripts/spec_runner_adapter.py` GATES 未同步）。B1 首跑 760 → 1 failed / 759 passed，根因即此；§1「零改动面 tests/**」声明不准确（该测试读两载体做比对） | 当轮同步 adapter，pytest 恢复 760；B2/B3 每批双载体同提交 |
| **F-S9-P036-2** | **P2** | **CI 真实桩口径 = 运行时解析**：CI 3.12 装 **numpy 2.5.5**（`ndarray.cumsum()` 零参桩报 `call-overload`，3 条：`web/05_Performance.py:48` / `agents/auto_parameter_optimizer.py:929` / `agents/research_team_v2.py:1029`）；CI 3.10 装 **numpy 2.2.6**（形状/标量更严，7 条：`_spec.py:83` 形状重赋值、`strategy_allocator.py:570/571`、`hierarchical_bayesian_agent.py:219`、`assumption_monitor.py:363/472/646`）。D1/E6 的「双口径 2.4.6」不足以覆盖 CI 三版本 leg | `43ed468`（3 处 `np.cumsum`）+ `f1fdab4`（6 处形状/标量收窄）；终态三口径均 0；E6 口径扩容登记 |
| **F-S9-P036-3** | **P3** | §4.2 #6 注「L124 裸 `return` 不动」失实：返回注解改 `np.ndarray \| None` 后，L124 必须 `return None`（否则新错 `Return value expected`） | 实际落码 `return None`，CHECKLIST A5 标注口径更正 |
| **F-S9-P036-4** | **P2** | **C2 现网语义更正**：`tracker.cash = ...` 不会 `AttributeError`（普通类实例可动态建属性），而是**静默影子属性**——`get_cash()` 仍读 `_cash`，动态调资**静默失效**。mypy `attr-defined` 捕获的是「写错字段名」类真实缺陷；原 §3 表「→ AttributeError」描述不准确 | 探针留证（§12.2）；缺陷修复定性不变，风险等级上调为「静默失效」 |
| **F-S9-P036-5** | **P3** | `auto_parameter_optimizer.py` 的 `roles: list[Any]` 若按 §4.3.6 落 L983（第二赋值）会触发 `no-redef`（L947 已隐式定义）；实际注解移至**首次定义 L947**，L983 保持裸赋值 | 同效；CHECKLIST B7 标注落点 |
| **F-S9-P036-6** | **P3** | E7/E10/V6 的「`# type: ignore` = 0（含带 code）」与既有环境冲突：`65da5f9` 前已有 **4 处带 code**（`core/change_report.py` / `core/diagnostics.py` / `scripts/fetch_universe.py` ×2）；本批新增 = 0。D3 的「L4 总数上限 3」同样未计入既有存量 | 口径更正为「**本批新增 0**；既有带 code 4 处保留（P-036 前）」，登记不改存量 |
| **F-S9-P036-7** | **P3** | B3 实现细化（语义等价、行号 ±）：C3/C4/C5 以 `tradable / buyable / sellable` 局部 + **单条合并 assert** 实现（原规格写 `mask = self._tradable_mask` 逐处）；`custom.py` 注解置于首赋值 L192（等价「L192 前声明」）；`na_factor.py` 删除已无引用的 `Literal` import | 不触行为，登记 |

### 12.5 Step 9 结论

**结论**: **pass（带 3 P2 + 4 P3 登记——Step 10 审计更正 §12.5 原笔误「2 P2 + 5 P3」，明细表 §12.4 分级为准：-1/-2/-4 = P2，-3/-5/-6/-7 = P3；均在实施期闭合）**——三批红态逐字复现（14/96/21）、绿态三口径 0（92 files）、行为变更 C1-C4 全部探针留证、不变式 I1-I7 全部成立（`except Exception` 22 / 新增 ignore 0 / 签名差异恰 7 def 行 + 1 参数注解行 / pytest 760 / golden 13 / black 121 / `uv lock` exit 0）。CI 首推曾因 numpy 桩版本（F-S9-P036-2）红，修复提交 `43ed468` + `f1fdab4` 后三版本 leg 复绿（读数见 CHECKLIST §10）。

