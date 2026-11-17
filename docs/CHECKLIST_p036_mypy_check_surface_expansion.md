# CHECKLIST：P-036 mypy 检查面扩展

> **批次**: P-036 · **T1**（门禁判据面变更；判档规则 2）
> **上游**: [IMPL_p036](IMPL_p036_mypy_check_surface_expansion.md)（B1/B2/B3 规格 / §1 五条前提 + C1-C4 / §4 逐条与按簇规格 / §5 红态 / §8 8 处注解差异 / §11 Step 6 异构复审 pass：2 P2 + 4 P3 当轮回写）；[DESIGN_p036](DESIGN_p036_mypy_check_surface_expansion.md)（D1-D7 / I1-I7 / V1-V6 / §9 Step 4 复审）；[RESEARCH_p036](RESEARCH_p036_mypy_check_surface_expansion.md)（§5 R1'/R2' / §11 B0 / §12 Step 2 复审）
> **状态**: **Step 10 同基座 ADD 审计 + 终审 pass**（2026-11-17；65 项回填 §10 / 审计记录 §11；**RULE-5 异构终审待 U-P036-6**——Step 2/4/6/8 已由 GLM-5.3-Flash 异构执行，唯 Step 10 缺异构 leg）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**禁止与正文同一次写入时打勾**
> **基线读数（Step 6 独立实测 @`1261865` 代码面 = `65da5f9`，Step 7 对拍）**: 全量 `pytest -q` **760 passed**（172 warnings）/ `tests/` .py **84**（口径 = 全部 `.py`，含辅助；`test_*.py` = **81**）/ golden **13 用例**（7 份 json）/ `black --check core tests` **121 unchanged** / `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error** / `except Exception`（P-029 口径：`agents`+`filter`+`scripts`+`batch_backtest`+`strategy_evaluation` 全 `.py` + `cli.py`）**22** / `uv lock --check` **exit 0**
> **目标读数（Step 9）**: pytest **760**（I4 的 X=0，不减）/ `tests/` .py **84 不变** / black **121 不变** / mypy **B1 8 面 → B2 9 面 → B3 10 面**均 **0 error** / golden **13 零重录** / `except Exception` 恒 **22** / 裸 `# type: ignore` **0**（带 code 亦 **0**）/ `uv lock --check` exit 0
> **代码证据时点**: 实施前 HEAD `65da5f9`（§4 锚点为实施前行号）；CI 门禁行 `.github/workflows/tests.yml` L45-46
> **⚠️ 两套 ID 不得混用**: DESIGN 决策为 `D1-D7`，本文件 **D 组 = 行为变更 C1-C4 验收**——凡引用设计决策一律写 `DESIGN-D*`（P-033/P-034 教训）。

---

## 1. A 组：B1 小模块 14 条（IMPL §4.2 / DESIGN-D2）

> **DoR**: B1 面红态 `14 errors / 7 files（checked 68）`（@`65da5f9` 实测）；7 文件锚点已由 Step 6 E1 冻结。**DoD**: 同 target 0 error；14 条根因全部可追溯；零行为变更。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `tests.yml` mypy 行扩至 **8 面**（`core scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`），单行、无 `\|\| true` / `continue-on-error` | 读码 L45-46；`Select-String "\|\| true"` = 0 | IMPL §4.1 / DESIGN-D2 | ✅ `git show e2dafff` tests.yml hunk = 8 面单行；两模式全文 0 |
| A2 | `strategy_evaluation/evaluator.py:74`：`row: dict[str, Any] = {"name": name}`（`Any` 已导入，零 import 变更） | 读码 L63；`mypy strategy_evaluation` 该行消失 | IMPL §4.2 #1 | ✅ 落 L63（实际行号）；B1 绿态含 strategy_evaluation 面 0 |
| A3 | `order_strategy/strategies.py`：L30 `fill_timestamps: list \| None = None` + L374 `total_impact: float = ...`（`__post_init__` L33-34 逐字不动） | 读码 L30 / L374；`mypy order_strategy` 2 条消失 | IMPL §4.2 #2-#3 | ✅ 落 L30 / L373；另加 3 处 `assert order.fill_timestamps is not None`（L168/249/320，次生 union-attr） |
| A4 | `strategy_evaluation/stats.py`：L139 `half_life: float = ...` + L167 `turnover: float = 0`（L169 表达式逐字不动） | 读码 L139 / L167 | IMPL §4.2 #4-#5 | ✅ 落 L138 / L167，表达式未改 |
| A5 | `scripts/external_benchmark/verify_p015.py`：L78 返回注解 `-> None` → `-> np.ndarray \| None`（**PEP 604 形式，零 import**）；L119 / L223 / L337 三错同根消除；L124 裸 `return` 不动 | 读码 L78；`mypy scripts` 3 条消失 | IMPL §4.2 #6-#8 / F-S6-P036-4 | ✅ 注解落 L78；**口径更正 F-S9-P036-3**：L124 裸 `return` 实改 `return None`（否则新错 `Return value expected`），L119/223 改 `np.asarray(pv_v3)` |
| A6 | `scripts/external_benchmark/_spec.py`：L99 `s: np.ndarray = np.nan_to_num(...)` + L101 `return np.asarray(s > 0)` + L102 `abs_s: np.ndarray = np.abs(s)` + L104 `return np.asarray(abs_s >= threshold)`（`asarray` 对 ndarray 不复制） | 读码 L97-104；`mypy scripts` 2 条消失 | IMPL §4.2 #9-#10 | ✅ 落 L99-104 逐字；scripts 面 0 |
| A7 | `batch_backtest/engine.py::run_factors` 顶部加 `if self.factor_db is None: raise ValueError("未提供因子数据库")`——与 `run_all_factors` L81-82 **逐字一致**（**C1**） | 读码 run_factors 首行；探针：`BatchBacktestEngine(cfg).run_factors(["x"])` → `ValueError`（红态 `AttributeError`） | IMPL §4.2 #11 / D 组 D1 | ✅ 探针 `C1 VALUE_ERROR: 未提供因子数据库`（§12.2） |
| A8 | `cli.py:48` `factor_weights=None` → `factor_weights={}`（`core/factor.py:487` `or {}` 等价，零行为变更） | 读码 L48；`mypy cli.py` arg-type 消失 | IMPL §4.2 #12 | ✅ 落 L48 |
| A9 | `cli.py:87-88` `engine.setup()` 后插 `dm = engine.dm` + `assert dm is not None`，两行改用 `dm`（U-a：setup 后恒赋值） | 读码 L84-89；`mypy cli.py` union-attr ×2 消失 | IMPL §4.2 #13-#14 | ✅ 落 L87-90；cli.py 面 0 |
| A10 | **B1 红→绿**：修复前 **14 errors / 7 files（checked 68）** → 修复后 **0 error**（同 target 原文留证） | 两次 `mypy` 输出原文（Step 9 记录） | IMPL §5 / DESIGN-V1 | ✅ 红 `Found 14 errors in 7 files (checked 68 source files)` → 绿 `Success: no issues found in 68 source files`（IMPL §12.1） |
| A11 | **B1 双口径 0**：本地（pandas 2.2.3 + numpy 2.4.6）与复刻 venv（pandas 3.1.1 + **numpy 2.4.6**，删 `.mypy_cache` 后）= 0 | 两个环境各一条 `Success` 原文 | DESIGN-I6 / D1 / F-S4-P036-4 | ✅ 2.4.6 两环境均 0；**⚠️ CI 真实为 numpy 2.5.5**（B1 面 `web/05_Performance.py:48` cumsum 1 条，F-S9-P036-2，43ed468 修复） |
| A12 | **B1 行为守恒**：pytest **760** 不减 / golden **13** 零重录 / black **121** 不变 / AST **22** 不变；代码 + workflow **同提交**（原子） | 四条门禁读数 + `git show --stat` 单提交含代码与 `tests.yml` | DESIGN-I1/I4/I5 / IMPL §6 | ✅ 760 / 13 / 121（core+tests 口径）/ 22；单提交 `e2dafff` 9 文件含 tests.yml + adapter（F-S9-P036-1 补） |

---

## 2. B 组：B2 `agents` 96 条（IMPL §4.3 / DESIGN-D2）

> **DoR**: `mypy agents` 红态 `96 errors / 11 files（checked 14）`；分文件计数 26/17/9/9/8/8/6/5/5/2/1 已由 Step 6 对账。**DoD**: `mypy agents` 0；单文件计数逐项归零；L4 = 0。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `tests.yml` 追加 `agents`（9 面）；无 `\|\| true` | 读码 L46 | IMPL §4.1 | ✅ `git show e781b75` tests.yml hunk = 9 面；两模式 0 |
| B2 | `guru_agent_v2.py` **25 条一处收窄**：L185-190 改为局部 `guru_data` + 既有 `raise ValueError` 原样 + `self.guru_data: dict[Any, Any] = guru_data`；L452 `return bool(date.day == self.cfg.rebalance_day)` | 读码 L184-191 / L452；`mypy agents` 该文件 26 条 → 0 | IMPL §4.3.1 / DESIGN-D4 | ✅ 落 L185-189 + L453；该文件 26 → 0（25 union-attr + 1 no-any-return） |
| B3 | `agent_framework.py` 17 条：`bool(...)` ×4（L433/514/596/1149）/ 返回注解 `dict[str, Any] \| None` ×2（L692/754，私有方法）/ `value: str` ×1（L1144）/ `from_universe_config` ×1（L1239 + L42 import 追加）/ `assert` 三组（L1292 universe、L1334-1337 + L1434 dm）/ `int(trade_qty)` ×2（L1386/1401，**C4**）/ `results: dict[str, Any]`（L1447） | 读码各锚点；`mypy agents` 该文件 17 条 → 0 | IMPL §4.3.2 / F-S6-P036-2/6 | ✅ 17 → 0；import 追加在 L42 既有行（不新增行） |
| B4 | `style_reflection_engine.py` 8 条一处根因：L203 `result: dict[str, Any] = {...}`（L218/222/235 自动消） | 读码 L203；该文件 8 → 0 | IMPL §4.3.3 | ✅ 8 → 0 |
| B5 | `strategy_allocator.py` 9 条：8 处 `no-any-return`（L72/313/416/492/533/579/653/839）局部注解或 `np.asarray`；L793 `inspect.signature(allocator_cls)`（去 `.__init__`） | 读码 L793；该文件 9 → 0 | IMPL §4.3.4 | ✅ 8 处 `np.asarray` + `inspect.signature(allocator_cls)`；9 → 0 |
| B6 | `sentiment_framework.py` 5 条：L736 `self.rate_limiter: dict[str, dict[str, Any]] = {...}`（L783/784/789 自动消）+ L228 前 `keywords: Any` + L796 `by_tier: dict[str, int] = {}` | 读码 L736 / L228 / L796；该文件 5 → 0 | IMPL §4.3.5 | ✅ 5 → 0；L784 另加 `bool(...)` 收口（`Any >= Any`） |
| B7 | `auto_parameter_optimizer.py` 8 条：L983 `roles: list[Any]`（演示块，L984-988 五条自动消）+ L325/339/426 局部注解 | 读码 L983 / L325 / L339 / L426；该文件 8 → 0 | IMPL §4.3.6 | ✅ 8 → 0；**落点更正 F-S9-P036-5**：`roles: list[Any]` 置于首次定义 L947（L983 重注解触发 no-redef） |
| B8 | `assumption_monitor.py` 9 条：L220/327/596/709 `checks: list[Any] = []`；L427/434/439/552/821 局部注解 | 读码四处 `checks` + 五处返回；该文件 9 → 0 | IMPL §4.3.7 | ✅ 9 → 0（含 py3.10 leg 三处 `AssumptionCheck` 标量 `float()` 收口，F-S9-P036-2） |
| B9 | `multi_strategy_engine.py` 6 条：L106 `self.pending_queue: PendingOrderQueue \| None = ...` / L587 `from_universe_config(base_config.universe)` + L43 import 追加 / L777 `strategy_daily_returns: dict[str, list[float]] = {}` / L829 `assert allocator is not None` / L909 `nav_history: dict[str, list[float]] = {name: [] for name in strategy_names}` / L973 `tracker._cash`（**C2**） | 读码各锚点；该文件 6 → 0 | IMPL §4.3.8 / F-S6-P036-5 | ✅ 6 → 0 |
| B10 | `style_drift_analysis.py` 5 条：L221/243/257 局部注解 / L250 `profile = self.baseline_profile` + `assert profile is not None`（U-a，构造期 L539 恒调） / L806 循环变量 `v` → `violation` | 读码各锚点；该文件 5 → 0 | IMPL §4.3.9 / O-S6-P036-1 | ✅ 5 → 0（局部名 `concentration_drift/beta_drift/volatility_drift`） |
| B11 | `hierarchical_bayesian_agent.py` 2 条：L220 局部注解 / L287 `active_events: list[Any] = []` | 读码 L220 / L287；该文件 2 → 0 | IMPL §4.3.10 | ✅ 2 → 0；py3.10 leg 需 `stability: float = max(0.0, 1.0 - float(std) * 5)`（F-S9-P036-2） |
| B12 | `research_team_v2.py` 1 条：L260 **删除 `period=period` 实参**（`update_belief` L424 无该参数，现网 TypeError——**C3**）；L254 `capability_belief.update(..., period=period)` 不动 | 读码 L259-261；探针：注入 TACTIC 信念后 `learn` 不再 TypeError | IMPL §4.3.11 / D 组 D3 | ✅ 1 → 0；探针 `C3 OLD CALL TypeError` / `NEW CALL bind: OK`；L254 未动；同步修正失效注释「（传递period）」 |
| B13 | **B2 红→绿**：修复前 **96 errors / 11 files（checked 14）** → 修复后 **0 error**；B1 面同时仍 0 | 两次 `mypy` 原文（含 9 面） | IMPL §5 / DESIGN-V2 | ✅ 红 `Found 96 errors in 11 files (checked 14 source files)` → 绿 9 面 `Success: no issues found in 82 source files` |
| B14 | **B2 双口径 0** + 行为守恒（pytest 760 / golden 13 / black 121 / AST 22）+ 代码与 `tests.yml` **同提交** | 双环境 `Success` 原文 + 四门禁读数 + 单提交 `git show --stat` | DESIGN-I1/I4/I5/I6 | ✅ 三口径（3.12+2.4.6 / 3.12+2.5.5 / 3.10+2.2.6）均 0（F-S9-P036-2 扩容）；760/13/121/22；单提交 `e781b75` 13 文件含 tests.yml + adapter；首推 CI 红已由 43ed468/f1fdab4 闭合 |

---

## 3. C 组：B3 `filter` 21 条 + 去 override（IMPL §4.4 / DESIGN-D5）

> **DoR**: `mypy filter`（无 override ini）红态 `21 errors / 7 files（checked 10）`；pyproject override 块 L116-123 在位。**DoD**: filter 0、10 面 0、`mypy core` 仍 0、override 删除三者**同批原子**。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `tests.yml` 追加 `filter`（**10 面最终形态**，与 DESIGN-D2 字符串逐字一致） | 读码 L46 | IMPL §4.1 | ✅ `git show eb3ae55` tests.yml hunk = 10 面单行 |
| C2 | `universe_filter_clean.py:108`：`self._prefix_info: dict[str, bool] = {}`（L184 赋 `any(...)`） | 读码 L108 | IMPL §4.4.1 | ✅ 落 L108 |
| C3 | `filter_stocks`（L498-531）**2 条**：L520 `mask = mask_map.get(...)` 后插 `assert mask is not None`（L511-512 的 `build_masks()` 副作用为既有前提）；L522/526 自动收窄 | 读码 L511-526；该函数 2 → 0 | IMPL §4.4.1 / **F-S6-P036-1** | ✅ 落 L521 `assert mask is not None`；L522/526 收窄 |
| C4 | `get_universe_stats`（L533-552）**4 条**：L544 插 `mask = self._tradable_mask` + `assert mask is not None`，L545/550-552 改用 `mask` | 读码 L542-552；该函数 4 → 0 | IMPL §4.4.1 / F-S6-P036-1 | ✅ 实现用 `tradable/buyable/sellable` 三局部 + 单条合并 assert（等价，F-S9-P036-7）；4 → 0 |
| C5 | `get_mask_summary`（L561-573）**6 条**：L564 插 `mask = self._tradable_mask` + `assert mask is not None`，L567-573 改用 `mask` | 读码 L563-573；该函数 6 → 0 | IMPL §4.4.1 | ✅ 同型三局部 + 合并 assert；6 → 0 |
| C6 | `prefix.py` L343 `create_prefix_filter` 返回注解 `-> PrefixFilter` → `-> BaseFilter`（L359 `RegexPrefixFilter(BaseFilter)` 不含继承关系）——**1 条** | 读码 L343；该文件 1 → 0 | IMPL §4.4.2 / F-S6-P036-3 | ✅ 1 → 0 |
| C7 | `na_factor.py` **2 条**：L33 构造器参数注解 `Literal[...]` → `str`；L343 `strategies: dict[str, type[BaseFilter]]` + **L332 `create_na_filter` 返回注解同批改 `-> BaseFilter`**（防 return-value 新错） | 读码 L33 / L332 / L343；该文件 2 → 0 且零新增错误 | IMPL §4.4.3 / F-S6-P036-2 | ✅ 2 → 0；另删已无引用的 `Literal` import |
| C8 | 四个工厂（**4 条**）：`market_cap.py` L369 + 返回注解 L358 改 `-> BaseFilter` / `industry.py` L382 + L371 同 / `extended.py` L319（返回注解已 `BaseFilter` 不变）/ `custom.py` L427（同上）；均 `dict[str, type[BaseFilter]]` | 读码四文件字典与 def 行 | IMPL §4.4.4 / F-S6-P036-2 | ✅ 四文件字典注解 + market_cap/industry 返回注解；4 → 0 |
| C9 | `custom.py:195`：L192 前声明 `filter_obj: BaseFilter`（L192 `ExpressionFilter` / L195 `CustomFunctionFilter` 共用变量） | 读码 L188-196；该文件第 2 条消失 | IMPL §4.4.5 | ✅ 注解置于首赋值 L192（等价「L192 前声明」，F-S9-P036-7）；2 → 0 |
| C10 | **override 删除（D5 三条件同批）**：`mypy filter`（无 override）= **0**；删除后 `mypy core` **仍 0**；pyproject **L116-123 整块删除**（含「B3 修完后应移除」注释） | 读码 pyproject 尾部无 `[[tool.mypy.overrides]]`；`Grep "filter\.\*"` = 0；`mypy core` Success 原文 | DESIGN-D5 / U-P036-2 | ✅ 顺序执行：无 override ini filter `Success: no issues found in 10 source files` → 删块 → `mypy core` = `Success: no issues found in 37 source files`；`filter\.\*` grep = 0 |
| C11 | **B3 红→绿 + 双口径 + 行为守恒 + 原子提交**：修复前 **21 errors / 7 files（checked 10）** → 0；10 面双口径 0；pytest 760 / golden 13 / black 121 / AST 22；代码 + workflow + pyproject **同提交** | 红绿 mypy 原文 + 四门禁 + `git show --stat` 单提交 | IMPL §5 / DESIGN-I5/I6 | ✅ 红 `Found 21 errors in 7 files (checked 10 source files)` → 绿 10 面 `Success: no issues found in 92 source files`（三口径）；760/13/121/22；单提交 `eb3ae55` 10 文件含 pyproject + tests.yml + adapter；首推 CI 红已由 f1fdab4 闭合 |

---

## 4. D 组：行为变更 C1-C4（IMPL §1 / DESIGN-D4 改写后原则）

> **DoR**: C1-C4 四项已在 Step 6 E4 读码复现「现网崩溃 / 类型错配」。**DoD**: 每项有探针读数；新增 `raise` 仅 C1；默认值降级 = 0。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | **C1** `BatchBacktestEngine.run_factors`：`factor_db=None` 时由 `AttributeError` → `ValueError("未提供因子数据库")`（与 `run_all_factors` L81-82 同文案） | `%TEMP%` 探针：红态 `AttributeError` / 绿态 `ValueError` + 文案 | IMPL C1 / DESIGN-D4 ① | ✅ 探针 `C1 VALUE_ERROR: 未提供因子数据库`；红态读码 `self.factor_db.list_factors()` |
| D2 | **C2** `multi_strategy_engine.py:973`：`tracker.cash` → `tracker._cash`（`PositionTracker` 仅 `_cash` + `get_cash()`，无 `cash` 属性）；探针证明原行为 `AttributeError` | 探针：`setattr(tracker, "cash", 1.0)` 前读 `hasattr(tracker, "cash")` = False；修复行读码 | IMPL C2 / R-P036-4 | ✅ **口径更正 F-S9-P036-4**：非 `AttributeError`，而是静默影子属性——`before get_cash=100000.0 hasattr=False`；旧写 `t.cash=42000` 后 `get_cash()` 仍 100000（静默失效）；新写 `_cash` → `get_cash()=42000.0` |
| D3 | **C3** `research_team_v2.py:260`：删 `period=period`；探针证明原调用 `TypeError`（`update_belief` L424 签名无 `period`） | 探针：`inspect.signature(update_belief)` 无 `period`；修复后 `learn(...)` 不抛 TypeError | IMPL C3 / R-P036-4 | ✅ `params: ['self','name','evidence','evidence_strength']`；`OLD CALL TypeError: got an unexpected keyword argument 'period'`；`NEW CALL bind: OK` |
| D4 | **C4** `agent_framework.py:1386/1401`：实参 `int(trade_qty)`（`target_qty` L1368 已 int；`current_qty` 经 `get_position` 为 float）；数量本为 100 倍数，截断无实际影响 | 读码 L1368-1401；探针：构造 float 持仓后单笔 `_execute_trade` quantity 为 int | IMPL C4 | ✅ `trade_qty type: float value: 33378.9` → `int(trade_qty): 33378`；`_execute_trade quantity annotation: int` |
| D5 | **新增 `raise` 清单仅 C1 一处**：`git diff` 中 `^\+.*raise ` 限 10 面 = **1**（`batch_backtest/engine.py`）；`agents/` / `filter/` = **0** | `git diff` 正则计数（生产面） | DESIGN-D4 / IMPL §1 | ✅ `git diff 65da5f9..f1fdab4`（10 面）`^\+.*raise ` = **1**（engine.py 守卫）；agents/filter = 0 |
| D6 | **零默认值降级**：无任何 `or {}` / `or 0` / `or []` 式新增兜底（**C1 采用 fail-fast 而非默认值**，对齐 P-025 F-D3-P025-1 先例） | `git diff` 中 `^\+.*or \{\}` / `^\+.*= 0$` 新增 = 0（逐条人工复核） | DESIGN-D4 改写后原则 | ✅ 人工复核全 diff：新增兜底 = 0（唯一 `{}` 是 A8 的实参 `factor_weights={}`，属去掉 `None` 而非兜底） |
| D7 | **I2 注解差异恰 7 处 def 行 + 1 处参数注解行**（Step 8 精化 F-S8-P036-1）：返回注解 7（`verify_case` / `_weighted_vote` / `_confidence_weighted` / `create_prefix_filter` / `create_na_filter` / `create_market_cap_filter` / `create_industry_filter`，均触 def 行）+ 参数注解 1（`NAFactorFilter.__init__` 续行 L33，**不触 def 行**）；参数名 / 默认值 / 函数名**逐字零变更** | `git diff` 中 `^-\s*def ` 逐行比对 = **7 处**（每处仅返回注解差异）+ L33 参数注解行差异 1 处 | IMPL §1 前提 4 / §8 / F-S6-P036-2 / F-S8-P036-1 | ✅ `git diff 65da5f9..f1fdab4`（10 面）`^-\s*def ` = **7**；L33 参数注解行 1 处（`Literal[...]` → `str`） |
| D8 | C2/C3 若探针证明生产路径可达 → 按 P-029/P-031 口径**登记为缺陷修复**（F-I-P036-2 升级）；不可达则降为「潜在缺陷」观察 | IMPL §11 实施期发现表一行 | R-P036-4 / F-I-P036-2 | ✅ 均判**缺陷修复**——C2 静默调资失效（探针实测旧写无效果）/ C3 现网 TypeError（探针 bind 复现）；登记入 IMPL §12.4（F-S9-P036-4） |

---

## 5. E 组：不变式 I1-I7 与验证契约 V1-V6

> **DoR**: DESIGN §3/§4 已冻结七条不变式与六项契约。**DoD**: 全组合成立。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | **I1** golden **13 零重录**：`pytest -q -k golden` = 13 passed 且 `git status --short tests/golden/` = 空 | 两命令读数 | I1 / V5 | ✅ `13 passed, 747 deselected`；`git status --short tests/golden/` = 空 |
| E2 | **I2** 公开签名零变更（口径见 D7）：7 处 `def` 行仅返回注解差异 + 1 处参数注解行 | D7 证据 | I2 / F-I-P036-1 | ✅ 同 D7（7 + 1） |
| E3 | **I3** `except Exception`（P-029 口径命令）= **22**；10 面 `git diff` 中 `^\+.*except` = **0** | AST 单行命令 + diff 正则 | I3 | ✅ AST = **22**；10 面 diff `^\+.*except` = **0** |
| E4 | **I4** pytest **760 不减**（X=0，本批不新增测试）；`tests/` .py **84 不变**（`test_*.py` 81） | 全量末行 + 文件计数 | I4 / IMPL §6 | ✅ `760 passed`；84 / 81 |
| E5 | **I5** 三批各自**原子提交**（代码 + `tests.yml` [+ pyproject] 同提交），可单独 revert；CI 四 job 全绿 | `git show --stat` ×3 + `gh run view` | I5 / DESIGN §6 | ✅ 原子提交成立（`e2dafff` / `e781b75` / `eb3ae55`）；⚠️ 三主提交首推 CI 红（numpy 桩，F-S9-P036-2），`43ed468`+`f1fdab4` 后复绿（§10） |
| E6 | **I6** 每批 target 双口径 0：本地（pandas 2.2.3 / numpy 2.4.6）+ 复刻 venv（pandas 3.1.1 / **numpy 2.4.6**，删 `.mypy_cache`） | 每批两环境 `Success` 原文 | I6 / DESIGN-D1 | ✅ 终态**三口径** 0：py3.12+np2.4.6 / py3.12+np2.5.5 / py3.10+np2.2.6（92 files）；口径扩容 F-S9-P036-2 |
| E7 | **I7** 忽略审计：10 面 `grep '# type: ignore'` = **0**（裸 + 带 code 合计 0） | `Grep '# type: ignore'` 限 10 面 | I7 / DESIGN-D3 | ✅ **本批新增 = 0**（10 面 diff）；⚠️ 既有带 code 4 处（`core/change_report.py` / `core/diagnostics.py` / `scripts/fetch_universe.py`×2，均 P-036 前）——口径更正 F-S9-P036-6；裸 ignore 全文 = 0 |
| E8 | **V4 最终门禁**：`tests.yml` mypy 步骤 target = 10 面字符串逐字一致，CI 三版本 leg 各 0 error | 读码 L46 + CI 日志 `Success` | V4 | ✅ L46 逐字 = `core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`；三版本 leg 以 `f1fdab4` 修复后 run 为准（§10） |
| E9 | **V5 行为守恒组合**：golden 13 + pytest 760 + 签名（D7）+ AST 22 四项同时成立 | E1 + E2 + E3 + E4 | V5 | ✅ 四项同批成立（终态 `f1fdab4`） |
| E10 | **V6 忽略审计**（等价 E7，独立复跑一次确认 0）：`Grep '# type: ignore'` 全仓限 10 面 = 0；`# type: ignore[` 亦 = 0 | 两条 Grep | V6 | ✅ 独立复跑：新增 0；既有带 code 4（同 E7，F-S9-P036-6） |

---

## 6. F 组：门禁链、CI 与治理

> **DoR**: `tests.yml` L45-46 现为 `core` 单面；CI 矩阵 3.10/3.11/3.12 + `lock-check`。**DoD**: 三阶段扩面顺序正确、CI 全绿、文档与台账收口。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | **三阶段扩面顺序**：B1 提交含 8 面 → B2 提交含 9 面 → B3 提交含 10 面；每次扩面与对应修复**同提交** | 三个提交的 `git show` 中 `tests.yml` hunk 逐次核对 | IMPL §3 / DESIGN §6 | ✅ `e2dafff` 8 面 / `e781b75` 9 面 / `eb3ae55` 10 面，各自与当批修复同提交 |
| F2 | **最终 target 字符串**：`core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`（10 面，顺序与 DESIGN-D2 一致） | 读码 L46 逐字比对 | DESIGN-D2 / V4 | ✅ 逐字一致（tests.yml L46 与 adapter L67） |
| F3 | **门禁真实可红**：`tests.yml` 内 `\|\| true` / `continue-on-error` = **0**；`test` job 其余行与 `lock-check` job **逐字零改动** | `Select-String` 两模式 + `git diff` 仅 mypy 行变化 | P-024 教训 / I5 | ✅ 两模式 0；`git diff 65da5f9..f1fdab4 -- .github/workflows/tests.yml` = 仅 L46 单行三态变更 |
| F4 | **CI 全绿**：B1 / B2 / B3 三次主提交的 run 均四 job success（`lock-check` + 3.10/3.11/3.12） | `gh run view <id> --json conclusion,jobs` ×3 | I5 / DESIGN-V4 | ✅ 终态 `f1fdab4` run `44029888652` = **4 job 全 success**（lock-check / 3.10 / 3.11 / 3.12）。**过程如实留证**：三主提交首推均红（B1 `44026780449` / B2 `44027975513` / B3 `44028421866`，mypy step，F-S9-P036-2）→ `43ed468`（`44028763627`：3.10 红 / 3.12 cancelled / 3.11 + lock-check success）→ `f1fdab4` 复绿 |
| F5 | **红态留证**：三批修复前 mypy 输出原文 = B1 `14 / 7 / 68`、B2 `96 / 11 / 14`、B3 `21 / 7 / 10`（与 IMPL §5 逐字） | IMPL §12 实施记录三条原文 | IMPL §5 / DESIGN §4 | ✅ 三条逐字复现（IMPL §12.1） |
| F6 | **绿态留证**：三批修复后 mypy 输出 = 各自 `Success: no issues found in N source files`（N = 68 / 82 / 92 累进，以实测为准） | IMPL §12 三条原文 | V1-V4 | ✅ 68 / 82 / 92（IMPL §12.1；终态三口径均 92） |
| F7 | **文档回填**：PROGRESS §3.41.8~§3.41.10 三批记录 + §1.4 P-036 与 U-P024-3/U-P024-4 状态 + `CHANGELOG` 条目 + IMPL §12 实测；四文档互链 0 broken | 读回 + 链接机械校验 | IMPL §2 D1 | ✅ PROGRESS §3.41.10-§3.41.13 + §1.4 / CHANGELOG / IMPL §12 / 本文件 §10 已回填；链接校验 0 broken |
| F8 | **DESIGN-D6 遵守**：未为 O-P036-5 造调查批；U-P036-5 维持 pending | 读回 PROGRESS §1.4 | DESIGN-D6 | ✅ 未建调查批；U-P036-5 维持 pending |
| F9 | **DESIGN-D7 遵守**：`pyproject.toml [tool.mypy]` **未新增** `warn_unused_ignores` / `strict` / `disallow_untyped_defs` | `git diff pyproject.toml` 仅 override 块删除（B3） | DESIGN-D7 | ✅ `git diff 65da5f9..f1fdab4 -- pyproject.toml` = 仅 override 块（L116-123）删除，`[tool.mypy]` 五行未动 |
| F10 | **台账收口**：U-P024-3 → done / U-P024-4 → done（filter 0 且 override 移除）/ U-P036-2 → done / U-P036-3 → done（50 条逐条留证）/ U-P036-4 / U-P036-5 维持 pending；F-S6-P036-1~6 与 O-S6-P036-1~3 有落点 | 读回 §1.4 与各文档 | D5 纪律扩展（P-035）/ 台账惯例 | ✅ PROGRESS §1.4 已逐项改写（U-P024-3/4 done、U-P036-2/3 done、U-P036-4/5 pending）；F-S6 六项 / O-S6 三项在 IMPL §11.4 与 CHECKLIST §9.3 有落点 |

---

## 7. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **65**（A 12 + B 14 + C 11 + D 8 + E 10 + F 10 = 65，机械计数） |
| 实测列回填 | **65/65**（Step 9 完成；Step 7 编制时为 0/65 零预填，回填过程见 §10） |

> **RULE-2 统计溯源**：65 由 §1-§6 六张表逐行机械计数得出（A1-A12 = 12 / B1-B14 = 14 / C1-C11 = 11 / D1-D8 = 8 / E1-E10 = 10 / F1-F10 = 10），非估计值。
>
> **`[待 Step 9]` 字面账目**：Step 7 编制时全文机械匹配 **68** = **65 单元格** + 头部规则行 1 处（L6）+ §7 回填行 1 处（L138）+ 本节账目行 1 处（L142）；**65 单元格零预填**。Step 9 回填后剩余 **0 单元格**（L6 规则行属规则定义保留；§7 回填行已改为 `65/65`）。
>
> **回填分级**：✅ **65** / ❌ **0**。其中 **6 项口径更正/细化**（A5 / B7 / D2 / E5 / E7 / E10 与 F4 过程留证），全部登记为 F-S9-P036-3~6（IMPL §12.4），无 ❌ 项。
>
> **本文件作者基座**: DeepSeek-V4.1-Flash（Step 5 IMPL 同源）→ **Step 8 一致性 Review 由 GLM-5.3-Flash 异构执行**（RULE-5，§9）；Step 9 实施与回填由 DeepSeek-V4.1-Flash 执行 → **Step 10 终审须异构**（RULE-5）。

---

## 8. Step 7 → Step 8 交接事项

1. **Step 8 一致性 Review（异构基座优先）**：核四文档口径——
   - **131 = 14 + 96 + 21** 在 DESIGN §2 / IMPL §2+§5 / 本文件头 + A10 + B13 + C11 三处一致；
   - **B2 分文件计数** 26/17/9/9/8/8/6/5/5/2/1 在 IMPL §4.3 / 本文件 B2-B12 一致；
   - **B3 方法归属**（filter_stocks 2 / get_universe_stats 4 / get_mask_summary 6 = 12 mask 条）在 IMPL §4.4.1 / 本文件 C3-C5 一致（F-S6-P036-1 更正后）；
   - **8 处注解差异**（7 返回 + 1 参数）在 IMPL §1 前提 4 / §8 / 本文件 D7 一致（F-S6-P036-2 更正后）；
   - **C1-C4** 在 IMPL §1 表 / 本文件 D1-D4 一致；
   - **门禁链** 760 / 84 / 121 / 37→0 扩面 / 13 / 22 / 双口径在 DESIGN §3-§4 / IMPL §1 / 本文件头三处一致。
2. **两套 ID 不得混用**：DESIGN 决策 `D1-D7` vs 本文件 **D 组**（行为变更）——引用决策一律 `DESIGN-D*`。
3. **顺序敏感核验（Step 9 必做）**：① `tests.yml` 三阶段扩面与修复同提交；② B3 必须「filter 0 → 删 override → core 仍 0」顺序；③ `guru_data` 收窄必须保留 L186-188 既有 `raise` 原文；④ `from_universe_config` 导入追加在既有 import 行（不新增行）。
4. **红态纪律**：三批 Step 9 首跑必须出示**修复前**读数（14/96/21）——不得用修复后读数倒填；`web` / `factor_library` 现状即 0 属**回归保护**，不计红态。
5. **双口径纪律**：复刻 venv 必须钉 `numpy==2.4.6` 并删 `.mypy_cache`，否则 129 假口径复现（F-S4-P036-4 / O-I-P036-1）。
6. **计数口径**：`tests/` .py = **全部 `.py`**（含 `_golden_cases.py` 等辅助），`test_*.py` = 81（F-S6-P034-1 先例）。

---

## 9. Step 8 一致性 Review 记录（GLM-5.3-Flash，2026-11-17）

> **基座**: **GLM-5.3-Flash ≠ CHECKLIST 作者 DeepSeek-V4.1-Flash** → **RULE-5 异构成立**。
> **复审对象**: 本文件 Step 7 版（提交 `97840dd`）+ 上游 IMPL（Step 6 更正版 `61876a9`）/ DESIGN（Step 4 版）/ RESEARCH；复审时点 HEAD `0d9876c`。
> **方法**: 机械五项（脚本 + 机械计数）+ 对齐矩阵六项（对应 §8 交接清单）。

### 9.1 机械五项

| # | 项 | 读数 | 结果 |
|---|----|------|------|
| 1 | 链接校验（四文档互链） | 相对链接 **7** 处命中 → **1 处伪命中**（IMPL L214 代码片段 `filters[filter_type](**kwargs)` 被 `\]\(...\)` 正则误判，人工判定非链接）；实际链接 **6 条 0 broken** | ✅（先例：CHECKLIST_p034 §9 代码块伪命中同口径） |
| 2 | ID 闭环 | 表行 **65**（A1-A12 / B1-B14 / C1-C11 / D1-D8 / E1-E10 / F1-F10，组内连续无跳号） | ✅ |
| 3 | 计数自洽 | 65 = 12 + 14 + 11 + 8 + 10 + 10（§7 RULE-2 声明与逐表实数一致） | ✅ |
| 4 | 零预填合规 | `[待 Step 9]` 全文 **68** = 65 单元格 + 头部规则行 1 + §7 回填行 1 + §7 账目行 1（与 §7 账目声明一致）；`✅` / `❌` 预填 **0** | ✅ |
| 5 | 角色引用 | §7 披露「作者 DeepSeek-V4.1-Flash → Step 8 须异构」——本节由 **GLM-5.3-Flash** 执行，异构成立 | ✅ |

### 9.2 对齐矩阵六项（§8 交接清单逐项）

| # | 对齐项 | 三处/两处读数 | 结果 |
|---|--------|--------------|------|
| 1 | **131 = 14 + 96 + 21** | DESIGN §2 注（L59）+ §9 E3 / IMPL §2 计数行（L51）+ §11.2 裁决 5 / CHECKLIST 头部目标 + A10 + B13 + C11 | ✅ 一致 |
| 2 | **B2 分文件计数** 26/17/9/9/8/8/6/5/5/2/1 | IMPL §4.3.1-§4.3.11 十一小节 / CHECKLIST B2-B12（各验收项「该文件 N → 0」）逐项对得上；11 项求和 = 96 | ✅ 一致 |
| 3 | **B3 方法归属**（filter_stocks 2 / get_universe_stats 4 / get_mask_summary 6 = 12 mask 条 + L108 var-annotated = 13） | IMPL §4.4.1（F-S6-P036-1 更正后）/ CHECKLIST C2-C5 逐字对应；13 + prefix 1 + na_factor 2 + 工厂 4 + custom:195 1 = **21** | ✅ 一致 |
| 4 | **注解差异清单** | IMPL §1 前提 4 / §8 表 / CHECKLIST D7——**发现 1 处口径精度问题（F-S8-P036-1）**，见 §9.3 | ⚠️ 已当轮精化 |
| 5 | **C1-C4 行为变更** | IMPL §1 表（C1 `run_factors` fail-fast / C2 `tracker.cash→_cash` / C3 删 `period` / C4 `int(trade_qty)`）/ CHECKLIST D1-D4 探针出口逐项对应 | ✅ 一致 |
| 6 | **门禁链**（760 / 84 / 121 / mypy 8→9→10 面 0 / golden 13 / AST 22 / uv exit 0） | DESIGN §3 I1-I7 + §4 红态 / IMPL §1 门禁口径 + §5 / CHECKLIST 头部基线与目标 + E 组——数值逐字一致 | ✅ 一致 |

### 9.3 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S8-P036-1** | **P3** | **「8 处 def 行」口径不精确**：`NAFactorFilter.__init__` 的参数注解位于**续行 L33**（`strategy: Literal[...] = "drop"`），不在 def 行 L31——其修改**不触碰 def 行**，机械判据 `git diff` 中 `^-\s*def ` 实际 = **7**（仅返回注解 ×7）。IMPL §1 前提 4 / CHECKLIST D7 / E2 原写「8 处 def 行」会把参数注解误计入 def 行差异，Step 9 核对时会得到 7 ≠ 8 的假性失败 | **当轮回写三处**——IMPL §1 前提 4 精化为「7 处 def 行（返回注解）+ 1 处参数注解行（续行 L33，不触 def 行）」；CHECKLIST D7 验收项与证据出口同步（`= 7 处 + 1 处参数注解行`）；E2 同步 |
| O-S8-P036-1 | 观察 | 链接校验 1 处伪命中（IMPL L214 `(**kwargs)` 代码片段），与 CHECKLIST_p034 §9「2 处代码块伪命中人工判定」同型 | 人工判定登记 |
| O-S8-P036-2 | 观察 | CHECKLIST 头部基线时点「@`1261865` 代码面 = `65da5f9`」——Step 6 实测时点实为 `b277313`，三者代码面相同（全为 docs 提交），读数不受影响 | 登记（时点精度注记） |

### 9.4 结论与 Step 9 前置

**结论**: **pass**（0 P0/P1 / **1 P3 当轮精化** / 2 观察）——机械五项全过、对齐矩阵六项中五项逐字一致、1 项口径精度问题当轮闭合。

**Step 9 前置**:
1. 按**更正后** D7 口径执行 I2 核对（`^-\s*def ` = 7 + L33 参数注解行 1）；
2. 三批红态首跑读数（14/96/21）与 F5 留证对拍；
3. C1-C4 探针按 D 组出口落 `%TEMP%` 并回填；
4. 双口径复验前钉 `numpy==2.4.6` + 删 `.mypy_cache`（O-I-P036-1）。

---

## 10. Step 9 实施记录（DeepSeek-V4.1-Flash，2026-11-17）

> **实施基点**: `65da5f9` → **代码终态**: `f1fdab4` · **详细规格回填**: [IMPL_p036](IMPL_p036_mypy_check_surface_expansion.md) §12
> **提交序列（5 次）**: `e2dafff`（B1 8 面）→ `e781b75`（B2 9 面）→ `eb3ae55`（B3 10 面 + 删 override）→ `43ed468`（numpy 2.5.5 兼容）→ `f1fdab4`（py3.10 / numpy 2.2.6 兼容）

### 10.1 提交 × CI run 表

| # | 提交 | 内容 | 净行数 | CI run | 结论 |
|---|------|------|--------|--------|------|
| 1 | `e2dafff` | B1：7 文件 14 条 + tests.yml/adapter 8 面 | 9 文件 +27/−18 | `44026780449` | ❌ mypy step（3.12 首条 numpy 2.5.5 cumsum） |
| 2 | `e781b75` | B2：11 文件 96 条 + C2/C3/C4 + 9 面 | 13 文件 +82/−61 | `44027975513` | ❌ mypy step（同上 + agents 侧 cumsum） |
| 3 | `eb3ae55` | B3：7 文件 21 条 + 删 pyproject override + 10 面 | 10 文件 +36/−34 | `44028421866` | ❌ mypy step（`web/05_Performance.py:48` cumsum） |
| 4 | `43ed468` | 3 处零参 `.cumsum()` → `np.cumsum(...)` | 3 文件 +3/−3 | `44028763627` | ❌ 3.10 leg 仍红（numpy 2.2.6 形状/标量 7 条）；3.12 cancelled |
| 5 | `f1fdab4` | 6 处形状/标量收窄（`np.full` / `np.zeros` / `max(0.0, ...)` / `float(...)` ×3） | 4 文件 +6/−6 | `44029888652` | ✅ **lock-check + 3.10 + 3.11 + 3.12 四 job 全 success** |

### 10.2 三口径实测环境（终态均 `Success: no issues found in 92 source files`）

| 口径 | 环境 | 用途 |
|------|------|------|
| 本机 | py3.12 + numpy 2.4.6 + mypy 2.4.1 | 日常门禁复验 |
| CI 3.12 复刻 | py3.12 + **numpy 2.5.5** + mypy 2.4.1（`%TEMP%\p036r2`） | 复现 `43ed468` 修复面 |
| CI 3.10 复刻 | py3.10.20 + **numpy 2.2.6** + pandas 2.3.3 + pydantic 2.14.3 + mypy 2.4.1（`%TEMP%\p036r310`，uv 安装） | 复现 `f1fdab4` 修复面（numpy 2.5.5 要求 py≥3.12，3.10 leg 解析为 2.2.6） |

### 10.3 实施期发现（详见 IMPL §12.4）

| ID | 级别 | 一句话 |
|----|------|--------|
| F-S9-P036-1 | P2 | 门禁**双载体**遗漏：只改 tests.yml 会使 `test_p024_ci_gate_alignment` 红（B1 首跑 760 → 1 failed），须同步 `scripts/spec_runner_adapter.py` |
| F-S9-P036-2 | P2 | CI 依赖未钉版本 → 真实桩为 numpy **2.5.5**（3.12）/ **2.2.6**（3.10），「双口径 2.4.6」不足 → 扩为三口径 |
| F-S9-P036-3 | P3 | IMPL §4.2 #6「L124 裸 `return` 不动」失实，实改 `return None` |
| F-S9-P036-4 | P2 | **C2 口径更正**：`tracker.cash=` 不抛 AttributeError，而是静默影子属性（调资静默失效）——缺陷定性不变、风险描述更正 |
| F-S9-P036-5 | P3 | `roles: list[Any]` 落点移至首次定义 L947（L983 重注解触发 `no-redef`） |
| F-S9-P036-6 | P3 | `# type: ignore` 口径更正为「**本批新增 0**」；既有带 code 4 处（P-036 前）保留 |
| F-S9-P036-7 | P3 | B3 实现细化（三局部 + 合并 assert / 注解置首赋值 L192 / 删 `Literal` import），语义等价 |

### 10.4 门禁终态（`f1fdab4`；读数与 IMPL §12.3 逐字一致）

`mypy` 10 面三口径 **0**（92 files）/ `mypy core` **0**（37 files）/ pytest **760 passed** / golden **13 passed, 747 deselected**，`git status --short tests/golden/` 空 / black `core tests` **121**、`.` **188** / AST `except Exception` **22** / `uv lock --check` exit **0** / `tests/*.py` **84**、`test_*.py` **81** / diff 机械读数 `^-\s*def ` = **7**、`^\+.*except` = **0**、`^\+.*raise ` = **1**（C1）、新增 `# type: ignore` = **0**。

### 10.5 结论

**Step 9 结论**: **pass** —— 65/65 实测回填、无 ❌ 项；三批红态（14/96/21）逐字复现、绿态三口径 0；C1-C4 全部探针留证（C2 降级为语义更正，见 F-S9-P036-4）；I1-I7 全部成立；CI 终态四 job 全绿（run `44029888652`）。**Step 10 前置**：ADD 审计 + RULE-5 异构终审（本文件与 IMPL 作者均为 DeepSeek-V4.1-Flash）。

---

## 11. Step 10：同基座 ADD 审计 + 独立新会话终审记录（2026-11-17）

> **基座披露（RULE-4/RULE-5）**：主会话 = **DeepSeek-V4.1-Flash（= 四文档作者同源）→ RULE-5 异构不成立**。本轮结构 = 主会话执行 E1 机械取证 + **独立全新上下文同基座会话**执行 Phase 0-4 对抗审计（消除记忆污染与实现者确认偏差；仍非异构基座）→ **异构终审登记 U-P036-6**（Step 2/4/6/8 已由 GLM-5.3-Flash 异构执行，唯 Step 10 缺异构 leg；先例 U-P032-1 / U-P034-3）。
> **审计区间（双口径显式声明，F-U3-P034-1 教训）**：代码面 = `7e91932..f1fdab4`（**5 提交**，`git rev-list --count` 实测）；全程 = `65da5f9..83a8d5f`（**15 提交**，其中 `65da5f9..e2dafff` 的 8 提交为 Step 5-8 文档提交）；审计时点 HEAD `83a8d5f`。

### 11.1 门禁与 CI 独立复跑（主会话 + 独立会话双份读数）

| 项 | 期望 | 主会话实测 | 独立会话实测 |
|----|------|-----------|--------------|
| mypy 10 面 | 0 / 92 files | `Success: no issues found in 92 source files` | 同左（独立复跑一致） |
| pytest 全量 | 760 | `760 passed, 172 warnings`（46.64s） | `760 passed, 172 warnings`（64.78s，须 `MPLBACKEND=Agg`——O-S10-P036-1） |
| golden | 13 / 747 | `13 passed, 747 deselected`（16.62s） | 同左 |
| black `core tests` | 121 | 121 unchanged | 同左 |
| `uv lock --check` | exit 0 | `Resolved 148 packages`，exit 0 | exit 0 |
| CI 三 run | 四 job success | `44029888652`（`f1fdab4`）/ `44030760894`（`191bbf8`）/ `44031073193`（`83a8d5f`） | 同左（`gh run view` 独立读取，headSha 三者对上） |

### 11.2 Phase 0-4 结论

| 阶段 | 结论 | 证据要点 |
|------|------|---------|
| Phase 0 规格质量 | ✅ | D1-D7 判据全部可机械核查（D1 钉 numpy 重放 / D2 字符串+14·96·21 计数 / D3 raise=1·assert 前提·L4=0 / D5 三条件顺序 / D6/D7 diff 可查）；I1-I7 验证出口齐备且全部复跑成立；V1-V6 可重放；无模糊不可审计项 |
| Phase 1 完整性（design→code） | ✅ | D2 十面 target **四处逐字一致**（tests.yml L46 / adapter L67 / DESIGN §2 / 本文件 F2+E8）；L4 新增 = 0；C1 = `engine.py` run_factors 顶部（与 `run_all_factors` 逐字）/ C2 = `multi_strategy_engine.py` / C3 = `research_team_v2.py` / C4 = `agent_framework.py` ×2 逐一读码定位；pyproject overrides 残留 = 0；D7 `[tool.mypy]` 五行未动 |
| Phase 2 忠实度（双向对照） | ✅ | 三主提交全 hunk 与 IMPL §4.2-§4.4 逐条对照，除已登记 F-S9-P036-3/5/7 外零偏离；numstat 五提交（+27/−18、+82/−61、+36/−34、+3/−3、+6/−6）与 IMPL §12.1 逐行吻合 |
| Phase 3 必要性（code→design） | ✅ | 全 hunk 归因完毕（B1→C1+次生 / B2→C2-C4 / B3→D5 / `43ed468`+`f1fdab4`→F-S9-P036-2 / 文档提交→流程回填）；**不可归因 hunk = 0**；零改动面（core / tests / examples / tools）diff = **空** |
| Phase 4 语义 + Iron Law | ✅ | C1-C4 外零运行期变更（9 处桩兼容改写逐一判定语义等价：`np.cumsum` ×3 数学恒等 / `float(...)` 收口 ×3 值保持 / `max(0.0, ...)` 数值恒等 / 纯注解 ×2）；Iron Law 三层补足 = 门禁面复跑 + C1-C4 探针（独立会话复现 C2/C3）+ golden 零重录（tests/ 零 diff 佐证） |

### 11.3 机械计数（E1，主会话实测 @`83a8d5f`）

10 面 diff（`7e91932..f1fdab4`）：`^\+.*raise ` = **1**（C1）/ `^\+.*except` = **0** / `^-\s*def ` = **7** / 新增 `# type: ignore` = **0**；零改动面 diff = 空；AST `except Exception`（P-029 口径 = handler 类型恰为 `Exception`，校准实测：全 handler 43 / Exception 22 / 裸 4）= **22**；`# type: ignore` 存量：裸 **0** / 带 code **4**（`core/change_report.py` / `core/diagnostics.py` / `scripts/fetch_universe.py` ×2，均 P-036 前）；`[待 Step 9]` 残余 3 处 = 规则定义（L6）/ §7 账目 / §9.1 机械项的合法历史引用，**0 未填单元格**。

### 11.4 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|---|---|---|
| 门禁五项复跑 ×2 会话（E1） | V4 / V5 / I1 / I4 / D7 | ✅ 全过（双份读数一致） |
| `gh run view` ×3（E1） | I5 / V4 / F4 | ✅ 三 run 四 job 全 success |
| diff 正则 ×4 + 零改动面（E1） | I2 / I3 / D5 / D7 / E7 | ✅ 1/0/7/0 + 空 |
| `git show --numstat` 对账 ×5（E1） | I5 / IMPL §12.1 | ✅ 逐行吻合 |
| C1-C4 读码定位 + C2/C3 运行期探针（E2，场景 = 行为变更边界与异常路径） | D1-D4 | ✅ 实锤 |
| assert 前提读码 ×5 组（E3 @`83a8d5f`） | D3-L2 约束 | ✅ 全 U-a（前提实锤） |
| ignore 存量定点 grep（E1） | I7 / V6 / E7 | ✅ 裸 0 / 既有带 code 4 / 新增 0 |
| 台账与 CHANGELOG 读回（E1） | F7 / F10 | ✅ U-P024-3/4、U-P036-2/3 = done，U-P036-4/5 = pending；F-S6 六项 / O-S6 三项落点齐；CHANGELOG P-036 条目在 |
| 文档口径自洽盲区扫描（E4，范围 = DESIGN I1-I7/V1-V6 + IMPL §1 门禁口径 + 本文件头部与结论行） | 全部口径声明 | **发现 3 项**（F-S10-P036-1/-2/-3） |

### 11.5 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S10-P036-1 | P3 | DESIGN I6「双口径」/ I7+V6「带 code ≤3」未随 F-S9-P036-2/-6 回写，与实况（三口径；既有带 code 4）冲突 | 当轮在 DESIGN §3 表后补 Step 10 口径注（I6/I7/V6 原文保留） |
| F-S10-P036-2 | P3 | IMPL §4.3.2 的 L1292 / L1334-1337 / L1434 三组规格写「局部变量+改用局部」，实现为方法内直断 assert（零语义差、mypy 收窄等效，B3 已按实际记载） | 当轮在 IMPL §4.3.2 表后补落点注，规格原文保留 |
| F-S10-P036-3 | P3 | **分级统计笔误**（主会话写入 §11 时自查发现，独立会话未覆盖该项）：IMPL §12.5 与 PROGRESS §1.4 P-036 行「2 P2 + 5 P3」与明细表不符——F-S9-P036-1/-2/-4 = P2、-3/-5/-6/-7 = P3，实为 **3 P2 + 4 P3** | 当轮两处更正（明细表分级为准） |
| O-S10-P036-1 | 观察 | 本地全量 pytest 需 `MPLBACKEND=Agg`（无则 3 例 Tk 后端红）；CI 已设、IMPL §5 已声明、非本批引入 | 登记（环境注记） |

### 11.6 结论与 U-P036-6 异构终审交接

**结论**: **pass——同基座终审闭合（0 P0/P1/P2 + 3 P3 当轮处置 + 1 观察）**；批次过程链 Step 1-10 完成，唯 **RULE-5 异构终审**由 **U-P036-6** 跟踪。

**U-P036-6 交接清单（供异构基座会话执行）**:
1. **E1 代码锚点重放**：C1（`batch_backtest/engine.py` run_factors 顶部 ValueError）/ C2（`multi_strategy_engine.py` `tracker._cash`）/ C3（`research_team_v2.py` 删 `period=period`）/ C4（`agent_framework.py` `int(trade_qty)` ×2）/ tests.yml L46 与 adapter L67 十面字符串 / pyproject 无 overrides；
2. **E2 diff 面**：区间 `65da5f9..HEAD` 全量——`raise`+ = 1 / `except`+ = 0 / `^-\s*def ` = 7 / 新增 ignore = 0；零改动面 = 空；numstat 与 IMPL §12.1 对账；
3. **E3 门禁独立复跑**：mypy 10 面 / pytest 760（带 `MPLBACKEND=Agg`）/ golden 13 / black 121 / `uv lock --check` / `gh run view` 终态 run；
4. **E4 运行期复验**：C1-C4 探针**独立编写**（勿复用 `%TEMP%\p036_s9_probe_*.py`，防同源盲区）；
5. **E5 修正复核**：F-S10-P036-1/-2/-3 三处补正到位、F-S9-P036-1~7 登记链完整；
6. 记录落本文件 **§12** + PROGRESS §1.4 U-P036-6 → done；批次总结报告（SUMMARY_p036）随终审交付（先例 SUMMARY_p034）。

### 11.7 签字表

| 角色 | 基座 | 结论 | 日期 |
|------|------|------|------|
| Step 7 验收清单作者 | DeepSeek-V4.1-Flash | 65 项完稿，零预填 | 2026-11-17 |
| Step 8 一致性 Review | GLM-5.3-Flash（≠ 作者，**异构成立**） | pass：机械五项全过 + 对齐矩阵 5/6 一致 + 1 P3 当轮精化（F-S8-P036-1），见 §9 | 2026-11-17 |
| Step 9 TDD 执行 | DeepSeek-V4.1-Flash（与上游同源） | pass：三批红→绿 14/96/21→0（8→9→10 面）+ C1-C4 探针 + CI 桩兼容修复复绿，见 §10 | 2026-11-17 |
| Step 10 同基座 ADD 审计 + 终审 | DeepSeek-V4.1-Flash（= 作者同源；Phase 0-4 由**独立全新上下文同基座会话**对抗执行，RULE-4 披露） | pass：Phase 0-4 全过 + 门禁双份复跑全绿 + 全 hunk 可归因；**0 P1/P2 + 3 P3 当轮处置 + 1 观察**，见 §11；异构终审记 U-P036-6 | 2026-11-17 |
| U-P036-6 异构终审 | （待 GLM-5.3-Flash 承接） | pending——交接清单见 §11.6 | — |
