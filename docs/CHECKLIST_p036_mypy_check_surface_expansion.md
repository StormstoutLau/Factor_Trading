# CHECKLIST：P-036 mypy 检查面扩展

> **批次**: P-036 · **T1**（门禁判据面变更；判档规则 2）
> **上游**: [IMPL_p036](IMPL_p036_mypy_check_surface_expansion.md)（B1/B2/B3 规格 / §1 五条前提 + C1-C4 / §4 逐条与按簇规格 / §5 红态 / §8 8 处注解差异 / §11 Step 6 异构复审 pass：2 P2 + 4 P3 当轮回写）；[DESIGN_p036](DESIGN_p036_mypy_check_surface_expansion.md)（D1-D7 / I1-I7 / V1-V6 / §9 Step 4 复审）；[RESEARCH_p036](RESEARCH_p036_mypy_check_surface_expansion.md)（§5 R1'/R2' / §11 B0 / §12 Step 2 复审）
> **状态**: **Step 7 编制完成，待 Step 8 一致性 Review**（2026-11-17；65 项零预填）
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
| A1 | `tests.yml` mypy 行扩至 **8 面**（`core scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`），单行、无 `\|\| true` / `continue-on-error` | 读码 L45-46；`Select-String "\|\| true"` = 0 | IMPL §4.1 / DESIGN-D2 | [待 Step 9] |
| A2 | `strategy_evaluation/evaluator.py:74`：`row: dict[str, Any] = {"name": name}`（`Any` 已导入，零 import 变更） | 读码 L63；`mypy strategy_evaluation` 该行消失 | IMPL §4.2 #1 | [待 Step 9] |
| A3 | `order_strategy/strategies.py`：L30 `fill_timestamps: list \| None = None` + L374 `total_impact: float = ...`（`__post_init__` L33-34 逐字不动） | 读码 L30 / L374；`mypy order_strategy` 2 条消失 | IMPL §4.2 #2-#3 | [待 Step 9] |
| A4 | `strategy_evaluation/stats.py`：L139 `half_life: float = ...` + L167 `turnover: float = 0`（L169 表达式逐字不动） | 读码 L139 / L167 | IMPL §4.2 #4-#5 | [待 Step 9] |
| A5 | `scripts/external_benchmark/verify_p015.py`：L78 返回注解 `-> None` → `-> np.ndarray \| None`（**PEP 604 形式，零 import**）；L119 / L223 / L337 三错同根消除；L124 裸 `return` 不动 | 读码 L78；`mypy scripts` 3 条消失 | IMPL §4.2 #6-#8 / F-S6-P036-4 | [待 Step 9] |
| A6 | `scripts/external_benchmark/_spec.py`：L99 `s: np.ndarray = np.nan_to_num(...)` + L101 `return np.asarray(s > 0)` + L102 `abs_s: np.ndarray = np.abs(s)` + L104 `return np.asarray(abs_s >= threshold)`（`asarray` 对 ndarray 不复制） | 读码 L97-104；`mypy scripts` 2 条消失 | IMPL §4.2 #9-#10 | [待 Step 9] |
| A7 | `batch_backtest/engine.py::run_factors` 顶部加 `if self.factor_db is None: raise ValueError("未提供因子数据库")`——与 `run_all_factors` L81-82 **逐字一致**（**C1**） | 读码 run_factors 首行；探针：`BatchBacktestEngine(cfg).run_factors(["x"])` → `ValueError`（红态 `AttributeError`） | IMPL §4.2 #11 / D 组 D1 | [待 Step 9] |
| A8 | `cli.py:48` `factor_weights=None` → `factor_weights={}`（`core/factor.py:487` `or {}` 等价，零行为变更） | 读码 L48；`mypy cli.py` arg-type 消失 | IMPL §4.2 #12 | [待 Step 9] |
| A9 | `cli.py:87-88` `engine.setup()` 后插 `dm = engine.dm` + `assert dm is not None`，两行改用 `dm`（U-a：setup 后恒赋值） | 读码 L84-89；`mypy cli.py` union-attr ×2 消失 | IMPL §4.2 #13-#14 | [待 Step 9] |
| A10 | **B1 红→绿**：修复前 **14 errors / 7 files（checked 68）** → 修复后 **0 error**（同 target 原文留证） | 两次 `mypy` 输出原文（Step 9 记录） | IMPL §5 / DESIGN-V1 | [待 Step 9] |
| A11 | **B1 双口径 0**：本地（pandas 2.2.3 + numpy 2.4.6）与复刻 venv（pandas 3.1.1 + **numpy 2.4.6**，删 `.mypy_cache` 后）= 0 | 两个环境各一条 `Success` 原文 | DESIGN-I6 / D1 / F-S4-P036-4 | [待 Step 9] |
| A12 | **B1 行为守恒**：pytest **760** 不减 / golden **13** 零重录 / black **121** 不变 / AST **22** 不变；代码 + workflow **同提交**（原子） | 四条门禁读数 + `git show --stat` 单提交含代码与 `tests.yml` | DESIGN-I1/I4/I5 / IMPL §6 | [待 Step 9] |

---

## 2. B 组：B2 `agents` 96 条（IMPL §4.3 / DESIGN-D2）

> **DoR**: `mypy agents` 红态 `96 errors / 11 files（checked 14）`；分文件计数 26/17/9/9/8/8/6/5/5/2/1 已由 Step 6 对账。**DoD**: `mypy agents` 0；单文件计数逐项归零；L4 = 0。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `tests.yml` 追加 `agents`（9 面）；无 `\|\| true` | 读码 L46 | IMPL §4.1 | [待 Step 9] |
| B2 | `guru_agent_v2.py` **25 条一处收窄**：L185-190 改为局部 `guru_data` + 既有 `raise ValueError` 原样 + `self.guru_data: dict[Any, Any] = guru_data`；L452 `return bool(date.day == self.cfg.rebalance_day)` | 读码 L184-191 / L452；`mypy agents` 该文件 26 条 → 0 | IMPL §4.3.1 / DESIGN-D4 | [待 Step 9] |
| B3 | `agent_framework.py` 17 条：`bool(...)` ×4（L433/514/596/1149）/ 返回注解 `dict[str, Any] \| None` ×2（L692/754，私有方法）/ `value: str` ×1（L1144）/ `from_universe_config` ×1（L1239 + L42 import 追加）/ `assert` 三组（L1292 universe、L1334-1337 + L1434 dm）/ `int(trade_qty)` ×2（L1386/1401，**C4**）/ `results: dict[str, Any]`（L1447） | 读码各锚点；`mypy agents` 该文件 17 条 → 0 | IMPL §4.3.2 / F-S6-P036-2/6 | [待 Step 9] |
| B4 | `style_reflection_engine.py` 8 条一处根因：L203 `result: dict[str, Any] = {...}`（L218/222/235 自动消） | 读码 L203；该文件 8 → 0 | IMPL §4.3.3 | [待 Step 9] |
| B5 | `strategy_allocator.py` 9 条：8 处 `no-any-return`（L72/313/416/492/533/579/653/839）局部注解或 `np.asarray`；L793 `inspect.signature(allocator_cls)`（去 `.__init__`） | 读码 L793；该文件 9 → 0 | IMPL §4.3.4 | [待 Step 9] |
| B6 | `sentiment_framework.py` 5 条：L736 `self.rate_limiter: dict[str, dict[str, Any]] = {...}`（L783/784/789 自动消）+ L228 前 `keywords: Any` + L796 `by_tier: dict[str, int] = {}` | 读码 L736 / L228 / L796；该文件 5 → 0 | IMPL §4.3.5 | [待 Step 9] |
| B7 | `auto_parameter_optimizer.py` 8 条：L983 `roles: list[Any]`（演示块，L984-988 五条自动消）+ L325/339/426 局部注解 | 读码 L983 / L325 / L339 / L426；该文件 8 → 0 | IMPL §4.3.6 | [待 Step 9] |
| B8 | `assumption_monitor.py` 9 条：L220/327/596/709 `checks: list[Any] = []`；L427/434/439/552/821 局部注解 | 读码四处 `checks` + 五处返回；该文件 9 → 0 | IMPL §4.3.7 | [待 Step 9] |
| B9 | `multi_strategy_engine.py` 6 条：L106 `self.pending_queue: PendingOrderQueue \| None = ...` / L587 `from_universe_config(base_config.universe)` + L43 import 追加 / L777 `strategy_daily_returns: dict[str, list[float]] = {}` / L829 `assert allocator is not None` / L909 `nav_history: dict[str, list[float]] = {name: [] for name in strategy_names}` / L973 `tracker._cash`（**C2**） | 读码各锚点；该文件 6 → 0 | IMPL §4.3.8 / F-S6-P036-5 | [待 Step 9] |
| B10 | `style_drift_analysis.py` 5 条：L221/243/257 局部注解 / L250 `profile = self.baseline_profile` + `assert profile is not None`（U-a，构造期 L539 恒调） / L806 循环变量 `v` → `violation` | 读码各锚点；该文件 5 → 0 | IMPL §4.3.9 / O-S6-P036-1 | [待 Step 9] |
| B11 | `hierarchical_bayesian_agent.py` 2 条：L220 局部注解 / L287 `active_events: list[Any] = []` | 读码 L220 / L287；该文件 2 → 0 | IMPL §4.3.10 | [待 Step 9] |
| B12 | `research_team_v2.py` 1 条：L260 **删除 `period=period` 实参**（`update_belief` L424 无该参数，现网 TypeError——**C3**）；L254 `capability_belief.update(..., period=period)` 不动 | 读码 L259-261；探针：注入 TACTIC 信念后 `learn` 不再 TypeError | IMPL §4.3.11 / D 组 D3 | [待 Step 9] |
| B13 | **B2 红→绿**：修复前 **96 errors / 11 files（checked 14）** → 修复后 **0 error**；B1 面同时仍 0 | 两次 `mypy` 原文（含 9 面） | IMPL §5 / DESIGN-V2 | [待 Step 9] |
| B14 | **B2 双口径 0** + 行为守恒（pytest 760 / golden 13 / black 121 / AST 22）+ 代码与 `tests.yml` **同提交** | 双环境 `Success` 原文 + 四门禁读数 + 单提交 `git show --stat` | DESIGN-I1/I4/I5/I6 | [待 Step 9] |

---

## 3. C 组：B3 `filter` 21 条 + 去 override（IMPL §4.4 / DESIGN-D5）

> **DoR**: `mypy filter`（无 override ini）红态 `21 errors / 7 files（checked 10）`；pyproject override 块 L116-123 在位。**DoD**: filter 0、10 面 0、`mypy core` 仍 0、override 删除三者**同批原子**。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `tests.yml` 追加 `filter`（**10 面最终形态**，与 DESIGN-D2 字符串逐字一致） | 读码 L46 | IMPL §4.1 | [待 Step 9] |
| C2 | `universe_filter_clean.py:108`：`self._prefix_info: dict[str, bool] = {}`（L184 赋 `any(...)`） | 读码 L108 | IMPL §4.4.1 | [待 Step 9] |
| C3 | `filter_stocks`（L498-531）**2 条**：L520 `mask = mask_map.get(...)` 后插 `assert mask is not None`（L511-512 的 `build_masks()` 副作用为既有前提）；L522/526 自动收窄 | 读码 L511-526；该函数 2 → 0 | IMPL §4.4.1 / **F-S6-P036-1** | [待 Step 9] |
| C4 | `get_universe_stats`（L533-552）**4 条**：L544 插 `mask = self._tradable_mask` + `assert mask is not None`，L545/550-552 改用 `mask` | 读码 L542-552；该函数 4 → 0 | IMPL §4.4.1 / F-S6-P036-1 | [待 Step 9] |
| C5 | `get_mask_summary`（L561-573）**6 条**：L564 插 `mask = self._tradable_mask` + `assert mask is not None`，L567-573 改用 `mask` | 读码 L563-573；该函数 6 → 0 | IMPL §4.4.1 | [待 Step 9] |
| C6 | `prefix.py` L343 `create_prefix_filter` 返回注解 `-> PrefixFilter` → `-> BaseFilter`（L359 `RegexPrefixFilter(BaseFilter)` 不含继承关系）——**1 条** | 读码 L343；该文件 1 → 0 | IMPL §4.4.2 / F-S6-P036-3 | [待 Step 9] |
| C7 | `na_factor.py` **2 条**：L33 构造器参数注解 `Literal[...]` → `str`；L343 `strategies: dict[str, type[BaseFilter]]` + **L332 `create_na_filter` 返回注解同批改 `-> BaseFilter`**（防 return-value 新错） | 读码 L33 / L332 / L343；该文件 2 → 0 且零新增错误 | IMPL §4.4.3 / F-S6-P036-2 | [待 Step 9] |
| C8 | 四个工厂（**4 条**）：`market_cap.py` L369 + 返回注解 L358 改 `-> BaseFilter` / `industry.py` L382 + L371 同 / `extended.py` L319（返回注解已 `BaseFilter` 不变）/ `custom.py` L427（同上）；均 `dict[str, type[BaseFilter]]` | 读码四文件字典与 def 行 | IMPL §4.4.4 / F-S6-P036-2 | [待 Step 9] |
| C9 | `custom.py:195`：L192 前声明 `filter_obj: BaseFilter`（L192 `ExpressionFilter` / L195 `CustomFunctionFilter` 共用变量） | 读码 L188-196；该文件第 2 条消失 | IMPL §4.4.5 | [待 Step 9] |
| C10 | **override 删除（D5 三条件同批）**：`mypy filter`（无 override）= **0**；删除后 `mypy core` **仍 0**；pyproject **L116-123 整块删除**（含「B3 修完后应移除」注释） | 读码 pyproject 尾部无 `[[tool.mypy.overrides]]`；`Grep "filter\.\*"` = 0；`mypy core` Success 原文 | DESIGN-D5 / U-P036-2 | [待 Step 9] |
| C11 | **B3 红→绿 + 双口径 + 行为守恒 + 原子提交**：修复前 **21 errors / 7 files（checked 10）** → 0；10 面双口径 0；pytest 760 / golden 13 / black 121 / AST 22；代码 + workflow + pyproject **同提交** | 红绿 mypy 原文 + 四门禁 + `git show --stat` 单提交 | IMPL §5 / DESIGN-I5/I6 | [待 Step 9] |

---

## 4. D 组：行为变更 C1-C4（IMPL §1 / DESIGN-D4 改写后原则）

> **DoR**: C1-C4 四项已在 Step 6 E4 读码复现「现网崩溃 / 类型错配」。**DoD**: 每项有探针读数；新增 `raise` 仅 C1；默认值降级 = 0。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | **C1** `BatchBacktestEngine.run_factors`：`factor_db=None` 时由 `AttributeError` → `ValueError("未提供因子数据库")`（与 `run_all_factors` L81-82 同文案） | `%TEMP%` 探针：红态 `AttributeError` / 绿态 `ValueError` + 文案 | IMPL C1 / DESIGN-D4 ① | [待 Step 9] |
| D2 | **C2** `multi_strategy_engine.py:973`：`tracker.cash` → `tracker._cash`（`PositionTracker` 仅 `_cash` + `get_cash()`，无 `cash` 属性）；探针证明原行为 `AttributeError` | 探针：`setattr(tracker, "cash", 1.0)` 前读 `hasattr(tracker, "cash")` = False；修复行读码 | IMPL C2 / R-P036-4 | [待 Step 9] |
| D3 | **C3** `research_team_v2.py:260`：删 `period=period`；探针证明原调用 `TypeError`（`update_belief` L424 签名无 `period`） | 探针：`inspect.signature(update_belief)` 无 `period`；修复后 `learn(...)` 不抛 TypeError | IMPL C3 / R-P036-4 | [待 Step 9] |
| D4 | **C4** `agent_framework.py:1386/1401`：实参 `int(trade_qty)`（`target_qty` L1368 已 int；`current_qty` 经 `get_position` 为 float）；数量本为 100 倍数，截断无实际影响 | 读码 L1368-1401；探针：构造 float 持仓后单笔 `_execute_trade` quantity 为 int | IMPL C4 | [待 Step 9] |
| D5 | **新增 `raise` 清单仅 C1 一处**：`git diff` 中 `^\+.*raise ` 限 10 面 = **1**（`batch_backtest/engine.py`）；`agents/` / `filter/` = **0** | `git diff` 正则计数（生产面） | DESIGN-D4 / IMPL §1 | [待 Step 9] |
| D6 | **零默认值降级**：无任何 `or {}` / `or 0` / `or []` 式新增兜底（**C1 采用 fail-fast 而非默认值**，对齐 P-025 F-D3-P025-1 先例） | `git diff` 中 `^\+.*or \{\}` / `^\+.*= 0$` 新增 = 0（逐条人工复核） | DESIGN-D4 改写后原则 | [待 Step 9] |
| D7 | **I2 注解差异恰 7 处 def 行 + 1 处参数注解行**（Step 8 精化 F-S8-P036-1）：返回注解 7（`verify_case` / `_weighted_vote` / `_confidence_weighted` / `create_prefix_filter` / `create_na_filter` / `create_market_cap_filter` / `create_industry_filter`，均触 def 行）+ 参数注解 1（`NAFactorFilter.__init__` 续行 L33，**不触 def 行**）；参数名 / 默认值 / 函数名**逐字零变更** | `git diff` 中 `^-\s*def ` 逐行比对 = **7 处**（每处仅返回注解差异）+ L33 参数注解行差异 1 处 | IMPL §1 前提 4 / §8 / F-S6-P036-2 / F-S8-P036-1 | [待 Step 9] |
| D8 | C2/C3 若探针证明生产路径可达 → 按 P-029/P-031 口径**登记为缺陷修复**（F-I-P036-2 升级）；不可达则降为「潜在缺陷」观察 | IMPL §11 实施期发现表一行 | R-P036-4 / F-I-P036-2 | [待 Step 9] |

---

## 5. E 组：不变式 I1-I7 与验证契约 V1-V6

> **DoR**: DESIGN §3/§4 已冻结七条不变式与六项契约。**DoD**: 全组合成立。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | **I1** golden **13 零重录**：`pytest -q -k golden` = 13 passed 且 `git status --short tests/golden/` = 空 | 两命令读数 | I1 / V5 | [待 Step 9] |
| E2 | **I2** 公开签名零变更（口径见 D7）：7 处 `def` 行仅返回注解差异 + 1 处参数注解行 | D7 证据 | I2 / F-I-P036-1 | [待 Step 9] |
| E3 | **I3** `except Exception`（P-029 口径命令）= **22**；10 面 `git diff` 中 `^\+.*except` = **0** | AST 单行命令 + diff 正则 | I3 | [待 Step 9] |
| E4 | **I4** pytest **760 不减**（X=0，本批不新增测试）；`tests/` .py **84 不变**（`test_*.py` 81） | 全量末行 + 文件计数 | I4 / IMPL §6 | [待 Step 9] |
| E5 | **I5** 三批各自**原子提交**（代码 + `tests.yml` [+ pyproject] 同提交），可单独 revert；CI 四 job 全绿 | `git show --stat` ×3 + `gh run view` | I5 / DESIGN §6 | [待 Step 9] |
| E6 | **I6** 每批 target 双口径 0：本地（pandas 2.2.3 / numpy 2.4.6）+ 复刻 venv（pandas 3.1.1 / **numpy 2.4.6**，删 `.mypy_cache`） | 每批两环境 `Success` 原文 | I6 / DESIGN-D1 | [待 Step 9] |
| E7 | **I7** 忽略审计：10 面 `grep '# type: ignore'` = **0**（裸 + 带 code 合计 0） | `Grep '# type: ignore'` 限 10 面 | I7 / DESIGN-D3 | [待 Step 9] |
| E8 | **V4 最终门禁**：`tests.yml` mypy 步骤 target = 10 面字符串逐字一致，CI 三版本 leg 各 0 error | 读码 L46 + CI 日志 `Success` | V4 | [待 Step 9] |
| E9 | **V5 行为守恒组合**：golden 13 + pytest 760 + 签名（D7）+ AST 22 四项同时成立 | E1 + E2 + E3 + E4 | V5 | [待 Step 9] |
| E10 | **V6 忽略审计**（等价 E7，独立复跑一次确认 0）：`Grep '# type: ignore'` 全仓限 10 面 = 0；`# type: ignore[` 亦 = 0 | 两条 Grep | V6 | [待 Step 9] |

---

## 6. F 组：门禁链、CI 与治理

> **DoR**: `tests.yml` L45-46 现为 `core` 单面；CI 矩阵 3.10/3.11/3.12 + `lock-check`。**DoD**: 三阶段扩面顺序正确、CI 全绿、文档与台账收口。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | **三阶段扩面顺序**：B1 提交含 8 面 → B2 提交含 9 面 → B3 提交含 10 面；每次扩面与对应修复**同提交** | 三个提交的 `git show` 中 `tests.yml` hunk 逐次核对 | IMPL §3 / DESIGN §6 | [待 Step 9] |
| F2 | **最终 target 字符串**：`core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library`（10 面，顺序与 DESIGN-D2 一致） | 读码 L46 逐字比对 | DESIGN-D2 / V4 | [待 Step 9] |
| F3 | **门禁真实可红**：`tests.yml` 内 `\|\| true` / `continue-on-error` = **0**；`test` job 其余行与 `lock-check` job **逐字零改动** | `Select-String` 两模式 + `git diff` 仅 mypy 行变化 | P-024 教训 / I5 | [待 Step 9] |
| F4 | **CI 全绿**：B1 / B2 / B3 三次主提交的 run 均四 job success（`lock-check` + 3.10/3.11/3.12） | `gh run view <id> --json conclusion,jobs` ×3 | I5 / DESIGN-V4 | [待 Step 9] |
| F5 | **红态留证**：三批修复前 mypy 输出原文 = B1 `14 / 7 / 68`、B2 `96 / 11 / 14`、B3 `21 / 7 / 10`（与 IMPL §5 逐字） | IMPL §12 实施记录三条原文 | IMPL §5 / DESIGN §4 | [待 Step 9] |
| F6 | **绿态留证**：三批修复后 mypy 输出 = 各自 `Success: no issues found in N source files`（N = 68 / 82 / 92 累进，以实测为准） | IMPL §12 三条原文 | V1-V4 | [待 Step 9] |
| F7 | **文档回填**：PROGRESS §3.41.8~§3.41.10 三批记录 + §1.4 P-036 与 U-P024-3/U-P024-4 状态 + `CHANGELOG` 条目 + IMPL §12 实测；四文档互链 0 broken | 读回 + 链接机械校验 | IMPL §2 D1 | [待 Step 9] |
| F8 | **DESIGN-D6 遵守**：未为 O-P036-5 造调查批；U-P036-5 维持 pending | 读回 PROGRESS §1.4 | DESIGN-D6 | [待 Step 9] |
| F9 | **DESIGN-D7 遵守**：`pyproject.toml [tool.mypy]` **未新增** `warn_unused_ignores` / `strict` / `disallow_untyped_defs` | `git diff pyproject.toml` 仅 override 块删除（B3） | DESIGN-D7 | [待 Step 9] |
| F10 | **台账收口**：U-P024-3 → done / U-P024-4 → done（filter 0 且 override 移除）/ U-P036-2 → done / U-P036-3 → done（50 条逐条留证）/ U-P036-4 / U-P036-5 维持 pending；F-S6-P036-1~6 与 O-S6-P036-1~3 有落点 | 读回 §1.4 与各文档 | D5 纪律扩展（P-035）/ 台账惯例 | [待 Step 9] |

---

## 7. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **65**（A 12 + B 14 + C 11 + D 8 + E 10 + F 10 = 65，机械计数） |
| 实测列回填 | **0/65**（全部 `[待 Step 9]`——零预填） |

> **RULE-2 统计溯源**：65 由 §1-§6 六张表逐行机械计数得出（A1-A12 = 12 / B1-B14 = 14 / C1-C11 = 11 / D1-D8 = 8 / E1-E10 = 10 / F1-F10 = 10），非估计值。
>
> **`[待 Step 9]` 字面账目**：Step 7 编制时全文机械匹配 **68** = **65 单元格** + 头部规则行 1 处（L6）+ §7 回填行 1 处（L138）+ 本节账目行 1 处（L142）；**65 单元格零预填**。Step 9 回填后剩余应为 **0 单元格**。
>
> **本文件作者基座**: DeepSeek-V4.1-Flash（Step 5 IMPL 同源）→ **Step 8 一致性 Review 须由异构基座执行**（RULE-5）。

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
