# CHECKLIST：P-044 策略接口抽象（Strategy Protocol + BacktestAdapter）

> **批次**: P-044 · **T1**（新建 `core/strategy.py` 契约 + `core/registry.py` 扩展 + `core/engine_v2.py` 信号模式分支 + `tests/`）
> **上游**: [IMPL_p044](IMPL_p044_strategy_interface.md)（§3 逐处代码 / §4 V1-V8 / §9 Step 6 pass：0 P1/P2 + 2 P3）；[DESIGN_p044](DESIGN_p044_strategy_interface.md)（D1-D8 / I1-I10 / §10 Step 4 pass：0 P1/P2 + 5 P3 + 2 补记）；[RESEARCH_p044](RESEARCH_p044_strategy_interface.md)（§7 S1-S10 / §8 I1-I9 / §13 Step 2 pass / §14 E1-EXT 锚点）
> **状态**: **批次关闭（2026-11-18）：45/45 + Step 10 ADD pass + U-P044-5 异构终审闭合（GLM-5.3-Flash，0 P1/P2/P3 新缺陷）+ D7 提交 `c4281d1` / CI `44260469437` 四 job 全绿**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；禁止预填
> **基线读数（@`96384f6`，P-043 关闭）**: pytest **803** / golden **13 passed, 790 deselected** / black `core tests` **130**（全仓 **197**）/ mypy **104 files 0** / AST `except Exception` **22**（core 外口径）/ `tests/*.py` **92** / `uv lock --check` exit **0**
> **目标读数**: pytest **811** / golden 13 零重录 / black **132**（全仓 **199**）/ mypy **105 files 0** / AST **22（不变）** / `tests/*.py` **93** / uv exit **0**

---

## 1. A 组：代码变更（14 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `canonical_json`（sort_keys/紧凑分隔符/ensure_ascii=False）+ `code_hash`：`getsource` 双异常（`OSError`/`TypeError`）回退链 → dedent + CRLF/CR→LF + strip + sha256 前 **12 hex**；源不可得 → `"q:"+12 hex` | 无（工具函数优先落码） | 读码 + V2 | ✅ strategy.py L42-44 / L47-77 逐字；V2 PASS |
| A2 | `StrategyMeta` 为 `@dataclass(frozen=True)`，四字段 `strategy_id/version/param_schema/code_hash` | 无（新建模块首个类型） | 读码 + V1 | ✅ L80-87；V1 PASS |
| A3 | `StrategyState` frozen 三字段 + `to_dict()`（positions 值 float 归一）/ `from_dict()`（仅接受含三键 dict）；`json.dumps` 往返相等 | A2 落码 | 读码 + V3 | ✅ L90-115；V3 PASS |
| A4 | `MarketView` frozen 五字段（`date/signal/tradable/prices/returns`），`returns: Optional[pd.DataFrame]`；无 `__post_init__` 校验 | A2 落码 | 读码 + V1 | ✅ L118-125；V1 PASS |
| A5 | `TargetWeights = pd.Series` / `StrategyFactory = Callable[..., "Strategy"]`；`Strategy` 为 `@runtime_checkable` Protocol，含 `meta` property + `generate_signals(view, state)` | A2 落码 | 读码 + V1 | ✅ L34（`TypeAlias`，F-S9-P044-1）/ L37 / L128-135；V1 PASS（`is pd.Series`） |
| A6 | `FactorSignalStrategy`：注入 `IOptimizer`；`generate_signals` = `optimizer.optimize(view.signal[view.tradable].dropna(), view.returns)`；空 scores 返回空 `TargetWeights`；`meta.param_schema` 含 `optimizer/select_top/target_count`；`code_hash` 构造期一次 | A5 落码 | 读码 + V1/V5 | ✅ L138-166；V1/V5 PASS |
| A7 | `DirectionalStrategy`：`direction ∈ {long, short, both}`（非法值 `ValueError`）；both = 多头腿 × `long_weight`；类常量 `short_leg_supported = False`（P-031 D2）；`meta.strategy_id` 缺省 `directional_{direction}` | A5 落码 | 读码 + V6 | ✅ L169-219；V6 PASS（含非法方向） |
| A8 | `BacktestAdapter.__init__/state_history/signals_frame`：**先求列并集再构造** DataFrame；逐日调用策略并把返回 Series 填入当日行；未出现标的记 **0**；每次推进追加 `StrategyState`（`positions` float 归一、`extras` 透传）；`state_history` 返回副本 | A6/A7 落码 | 读码 + V5 | ✅ L222-275；V5 PASS（`len(state_history)==5`、index==DATES） |
| A9 | `BacktestAdapter.views_from_data`：signal 先按 `(trade_dates, stock_codes)` 重排（视图日期全集）；`tradable` 缺省当日 `signal.notna()`，显式传入时 `reindex(stock_codes).fillna(False).astype(bool)`；`prices = get_adj_price("close","raw")`；`returns_window>0` 且 `i >= returns_window` 时切「截至前一日」窗口，**历史不足 → None** | A8 落码 | 读码 + V5 | ✅ L277-322；V5 PASS |
| A10 | `core/registry.py`：`_strategy_registry` 全局（`_agent_registry` 后）/ `get_strategy_registry()`（`get_agent_registry` 后）/ `register_strategy()` 装饰器（文件末），与既有 5 类别逐字同构；docstring「适用于:」+`Strategy (策略)` | 无（纯追加，与 B1-B9 解耦） | 读码 + V8 | ✅ registry.py L15 / L182 / L225-230 / L341-359；V8 PASS |
| A11 | `core/engine_v2.py`：typing 导入 +`Literal`；`__init__` 增 `self._signal_mode: Literal["scores","weights"] = "scores"`（`_returns_matrix` 后） | 无（既有模块改动） | 读码 + V4/V7 | ✅ L13 / L184-185；V4/V7 PASS |
| A12 | `set_signal(signal, *, mode="scores")`（`_precompute_factors` 与 `run()` 之间）：未 setup → `RuntimeError`；未知模式 / index 不一致 / 未知标的 / weights 负权重 / weights 行和 >1+1e-9 → `ValueError`；weights `fillna(0.0)`、scores 保留 NaN；整体替换 `_composite_signal` + `_signal_mode` | A11 落码 | 读码 + V7 | ✅ L361-387；V7 PASS（5 类逐案 + scores NaN + 未 setup） |
| A13 | `_execute_rebalance` 组合优化段：`if self._signal_mode == "weights": target_weights = daily_signal.clip(lower=0.0)`；**原 try/except 体逐字缩进进 `else`**（含 `logger.debug`/error 发射/`return`） | A11 落码 | 读码 + V4/V5 + `git diff` | ✅ L1024-1057；V4/V5 PASS；diff 仅缩进位移（F-S9-P044-3） |
| A14 | `core/strategy.py` 无 I/O 与全局写：`open`/`requests`/模块级副作用 = 0（I8） | A1-A9 落码 | grep + AST 目视 | ✅ grep `open(\|requests\.` = **0** |

## 2. B 组：测试（12 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | V1 契约：三 frozen dataclass 赋值抛 `FrozenInstanceError`；`isinstance(FactorSignalStrategy(...), Strategy)`；meta 四字段类型 + `param_schema["select_top"] is True`/`["target_count"]==2` + `len(code_hash)==12`；`TargetWeights is pd.Series`；`inspect.signature(generate_signals)` == `["view","state"]` | A2-A6 落码 | `tests/test_p044_strategy_interface.py` | ✅ PASS |
| B2 | V2 `code_hash`：同源两次相同且 12 hex；两实例参数不同（源码同类）→ hash 相同而 `param_schema` 不同；CRLF/LF 双模块同 hash；`exec` 动态类 → `q:` 前缀且 `len==14` | A1 落码 | 同上 | ✅ PASS（4 组断言全过） |
| B3 | V3 状态往返：`to_dict` → `json.dumps` → `from_dict` 相等；`positions` 逐值 float；`extras` 透传 | A3 落码 | 同上 | ✅ PASS |
| B4 | V4 **零行为护栏**：默认引擎 `_signal_mode=="scores"`；两次运行 NAV 逐值、7 个标量指标 `approx`、成交数与金额一致（红态亦 PASS） | A11 落码 | 同上 | ✅ PASS（红态亦 PASS） |
| B5 | V5 weights 集成等价：`FactorSignalStrategy(engine.optimizer)` + `views_from_data(..., tradable=engine.universe.tradable, returns_window=cov_lookback)` + `signals_frame` → `frame.index == DATES`、`len(state_history)==5` → `set_signal(mode="weights")` 后 run：trades stock/quantity 逐值、NAV `round(6)` 逐值、5 个标量指标 `approx` | A8/A9/A12/A13 落码 | 同上 | ✅ PASS（trades/NAV/指标逐值一致） |
| B6 | V6 三方向等价：long/short 输出与 `EqualWeightOptimizer(select_top=...)` 直出 `assert_series_equal`；both = long × 0.5 且 sum≈0.5；`short_leg_supported is False`；`meta.strategy_id=="directional_both"`；**非法 direction → `ValueError("未知方向")`**（F-S6-P044-1） | A7 落码 | 同上 | ✅ PASS |
| B7 | V7 `set_signal` 边界：index 不一致 / 未知标的 / 负权重 / 行和 >1 / 未知模式 → `ValueError`（逐案 5 类）；scores 保留 NaN 且 shape 正确；未 setup → `RuntimeError` | A12 落码 | 同上 | ✅ PASS（5 类逐案 + scores NaN + RuntimeError） |
| B8 | V8 registry：`get_strategy_registry()` 单例且 `category=="strategy"`；注册→`has`/`category`/`create(foo=1)`；重复注册 `caplog` 含 `already registered` 且 description 覆写；`finally` 注销后 `has` 为 False | A10 落码 | 同上 | ✅ PASS |
| B9 | 红态留证：IMPL §4.3 预测 `7 failed, 1 passed`（V1/V2/V3/V5/V6 导入失败、V7 AttributeError、V8 ImportError；V4 PASS） | 新测试文件已写、实现未落 | pytest 输出逐字 | ✅ 实测 **`7 failed, 1 passed in 8.61s`**（ModuleNotFoundError×5 / AttributeError×1 / ImportError×1；V4 PASS） |
| B10 | 绿态：`test_p044_strategy_interface.py` **8 passed** | A1-A13 落码 | pytest | ✅ `8 passed, 5 warnings in 5.49s`（格式化后复跑仍 8 passed） |
| B11 | 既有测试零订正且全绿：`test_engine_plugins` / `test_manifest` / `test_p026_silent_exception_governance` / `test_compatibility` | A11-A13 落码 | `pytest` 指定四文件 | ✅ **45 passed**（新 8 + 既有 37，零订正） |
| B12 | 夹具一致性：复用 `tests/_synth_fixture.py`（5 日 × 2 股；零费用 / `fixed`+`daily` / `enable_pending_orders=False` / `write_manifest=False`）；`target_count=2` / `max_weight=1.0` | B1 前置 | 读码 + 全量 pytest | ✅ 夹具逐字复用；全量 **811 passed** |

## 3. C 组：不变式（DESIGN I1-I10 + 既有语义，11 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1** 默认路径零行为：golden **13 零重录**；`tests/golden/` 零 diff；`agents/` **零 diff**；`BacktestConfig` **零新字段**；默认 `_signal_mode=="scores"`（V4） | 全量实现 | `pytest -k golden` + `git status` + V4 | ✅ golden `13 passed, 798 deselected`；`git status` 无 `tests/golden/`、无 `agents/`、无 `config.py`；V4 PASS |
| C2 | **I2** 运行时契约：`isinstance(impl, Strategy)` True（property 协议，Step 4 探针 A1）；`meta` 四要素齐备（V1） | A5/A6 落码 | V1 | ✅ V1 PASS |
| C3 | **I3** 等价迁移：`FactorSignalStrategy`/`DirectionalStrategy` 输出与既有路径**逐值相等**（V5 trades/NAV；V6 Series） | A6/A7 落码 | V5/V6 | ✅ V5/V6 PASS |
| C4 | **I4** `StrategyState` JSON 往返相等；`as_of/positions/extras` 逐值（V3） | A3 落码 | V3 | ✅ V3 PASS |
| C5 | **I5** registry `strategy` 类别：注册/查询/创建/覆写 warning（V8） | A10 落码 | V8 | ✅ V8 PASS |
| C6 | **I6** `set_signal` 5 类非法输入 fail-fast；weights 非负且行和 ≤1+1e-9（V7） | A12 落码 | V7 | ✅ V7 PASS |
| C7 | **I7** `code_hash`：同源码稳定、12 hex、CRLF/LF 同值、动态类 `q:` 回退（V2） | A1 落码 | V2 | ✅ V2 PASS |
| C8 | **I8** `core/strategy.py` 无 I/O：`grep -E "open\(|requests\." core/strategy.py` = 0；模块级仅常量/类定义 | A1-A9 落码 | grep | ✅ **0** |
| C9 | **I9** weights 与 scores 模式在同一策略/优化器下结果**逐值一致**（V5）；零权重项 ≡ 缺席项（`build_target_positions` L100-111 读码证实，IMPL §9.1-3） | A13 落码 | V5 + 读码 | ✅ V5 PASS（NAV round(6) 逐值） |
| C10 | **I10** 契约测试含 `inspect.signature(generate_signals)`（`runtime_checkable` 不校验签名）（V1） | A5 落码 | V1 | ✅ V1 PASS（`["view","state"]`） |
| C11 | 既有语义零变更：`SignalTranslator` / `core/portfolio.py` / `core/target_positions.py` / `core/rebalance.py` **零 diff**；`_execute_rebalance` 原 try 体逐字（`git diff` 仅缩进） | 全量实现 | `git diff --stat` | ✅ 生产 diff 仅 `engine_v2.py` + `registry.py`（+新增 `strategy.py`）；四模块零 diff；try 体仅缩进（F-S9-P044-3） |

## 4. D 组：门禁、提交与文档（8 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | pytest **811 passed**（803 + 8） | 全量实现 | 全量末行 | ✅ `811 passed, 184 warnings in 52.81s` |
| D2 | golden **`13 passed, 798 deselected`**；`git status --short tests/golden/` 为空 | 全量实现 | 命令 + git | ✅ `13 passed, 798 deselected`；目录零改动 |
| D3 | black `core tests` **132** / 全仓 **199**（+2 文件，F-S5-P044-1 订正口径）；`tests/*.py` **93** | 新测试文件落盘 | `black --check` 双口径 + 计数 | ✅ **132 · 199** unchanged（首跑 1 文件待格式化，F-S9-P044-2）；**93** |
| D4 | mypy **105 source files 0**（+1 `core/strategy.py`；命令不含 `tests/`） | 全量实现 | CI 逐字命令 | ✅ `Success: no issues found in 105 source files` |
| D5 | AST `except Exception` **22（不变；core 外口径）**；新增 `# type: ignore` = 0（`except (OSError, TypeError)` 不计） | A1-A13 落码 | P-029 单行命令 + grep | ✅ AST **22**（agents 11/filter 5/scripts 2/batch 2/strategy 1/cli 1）；生产文件新增 ignore **0** |
| D6 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零 diff | 全量实现 | 命令 + `git diff` | ✅ exit **0**（Resolved 148 packages）；两文件零 diff |
| D7 | 提交原子（3 生产文件：`core/strategy.py` 新建 + `registry.py`/`engine_v2.py` 修改；1 新建测试；**6 文档**：RESEARCH/DESIGN/IMPL/CHECKLIST/PROGRESS/CHANGELOG）+ CI 四 job 全绿 | D1-D6 通过 | `git show --stat` + `gh run view` | ✅ **`c4281d1`**（10 文件，+2905/−31）；push `96384f6..c4281d1`；CI **`44260469437`** run=completed/success（lock-check 12s / test 3.10 2m18s / 3.11 2m19s / 3.12 1m30s 四 job 全 success） |
| D8 | 文档回填：IMPL §10 / PROGRESS 对应小节 / CHANGELOG / 本文件 **45/45** | D7 通过 | 读回 | ✅ IMPL §10（落码/红绿/门禁/发现）+ PROGRESS §3.50.9·§3.50.10 + CHANGELOG（P-044 条目，`### Added` 首位）+ 本文件 **45/45** |

---

## 5. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **45**（A 14 + B 12 + C 11 + D 8 = 45，机械计数；B9-B12 为取证项非新用例） |
| 实测列回填 | **45/45**（45 × `✅`；D7 含提交 `c4281d1` + CI `44260469437` 四 job 全绿） |

> **RULE-2 统计溯源**：45 = 14 + 12 + 11 + 8（逐表行数）；新用例 **8** = V1-V8（8 函数，B6 含两条断言组）。
> **RULE-5 声明**：Step 1-2 同源（DeepSeek-V4.1-Flash）；Step 4 / Step 6 / **Step 8 异构成立**（GLM-5.3-Flash）；Step 10 异构终审由 GLM-5.3-Flash 承接（U-P044-5）。

---

## 6. Step 7 → Step 8 交接

1. 核红态口径：IMPL §4.3 预测 `7 failed, 1 passed`（V4 护栏 PASS）；实测若偏离，以实测回填 B9 与 IMPL §10。
2. 核计数链：803 + 8 = **811**；130 + 2 = **132**；197 + 2 = **199**；92 + 1 = **93**；mypy 104 + 1 = **105**；AST **22 不变**（`except (OSError, TypeError)` 不在门禁模式内）。
3. 核零预填：`[待 Step 9]` 须为 **45**（Step 9 前不得回填）。
4. 核 ID 不混用：DESIGN 决策 `D1-D8` vs 本文件 **D 组**；用例 `V1-V8`；发现 `F-S{2,4,5,6,8,9,10}-P044-*`；引用一律 `DESIGN-D*`。
5. 核既有测试：B11 四文件必须**零订正**（本批不改 `agents/`，`StrategyEngine` 内部重构归 P-051）。
6. 核边界：weights 模式禁配 `conditional`/`hybrid` 触发器（O-P044-2）；`factor_files` 占位与「全 0 行 = 清仓」须在 CHECKLIST 边界声明中可追溯（C1/C9 + DESIGN §4）。

---

## 7. Step 8 一致性 Review 记录（异构 GLM-5.3-Flash，2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 复审 **GLM-5.3-Flash** ≠ 四文档作者 DeepSeek-V4.1-Flash → **异构成立**（Step 4/6/8 连续三轮）；U-P044-5（异构终审）维持登记，Step 10 由 GLM 承接闭合。

### 7.1 机械五项

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 清单总数 | 45 = A 14 + B 12 + C 11 + D 8（逐表行数）；实测列 45 × `[待 Step 9]` | ✅ 零预填保持 |
| 2 | 计数链五文档一致 | RESEARCH §8·§13.1（F-S8-P044-1 订正后）/ DESIGN §6·§10.4 / IMPL §7·§9.1 / 本文件头部·D 组 / PROGRESS §3.50.5·§3.50.7 均为 **811 / 132·199 / 105 / 22 / 93** | ✅（订正后） |
| 3 | 用例数与函数数 | **8 函数** = test_v1..v8（IMPL §4.2 逐一清点）；803+8=811；红态 **7F/1P** 三文档一致（DESIGN §5 / IMPL §4.3 / 本文件 B9）；无 P-043 F-S8-P043-1 同类计数断裂 | ✅ |
| 4 | ID 链 | F-S2-P044-1..3 / F-D3-P044-1..3 / F-S4-P044-1..5 / F-S5-P044-1 / F-S6-P044-1..2 引用闭环；DESIGN-D1..D8 与本文件 **D 组**无混用；U-P044-1/2/4 已裁决、U-P044-3→P-051、U-P044-5→Step 10 | ✅ |
| 5 | 基座链 | RESEARCH Step2 同源 / Step4·6·8 异构 GLM / Step10 终审 GLM | ✅ 与 §5 RULE-5 声明一致 |

### 7.2 对齐矩阵（RESEARCH S/I/G ↔ DESIGN ↔ IMPL ↔ CHECKLIST）

| RESEARCH | DESIGN | IMPL | CHECKLIST | 判定 |
|----------|--------|------|-----------|------|
| S1 `StrategyMeta` | D2/§3.1 | §3.1 | A2 | ✅ |
| S2 `StrategyState` | D2/§3.1 | §3.1 | A3 | ✅ |
| S3 `MarketView` | D2/§3.1 | §3.1 | A4 | ✅ |
| S4 `TargetWeights` 非负边界 | D2（P-050 声明） | §3.1 | A5 + V7 负权重 fail-fast | ✅ |
| S5 `Strategy` Protocol 纯函数 | D2 | §3.1 | A5/A14 | ✅ |
| S6 `code_hash` 12hex | D3（演进 `target:Any`+双异常回退链，§14.3 裁决） | §3.1 | A1/B2 | ✅ |
| S7 `signals_frame` | D4（演进 views 入参 + `views_from_data` 拆分，U-P044-2） | §3.1 | A8/A9/B5 | ✅ |
| S8 三方向 P-031 D2 | D6 | §3.1 | A7/B6/C3 | ✅ |
| S9 registry | D7 | §3.2 | A10/B8/C5 | ✅ |
| S10 默认路径不变 | D8/D5 | §1/§3.3 | A11-A13/C1/C11 | ✅ |
| I1 golden+agents 零 diff | I1/D8 | §6/§8 | C1 | ✅ |
| I2/I3 等价迁移 | I3（合并细化） | §3.1 | C3（V5/V6） | ✅ |
| I4 状态往返 | I4 | §3.1 | C4（V3） | ✅ |
| I5 无 I/O | I8 | §3.1 | C8/A14 | ✅ |
| I6 registry | I5 | §3.2 | C5（V8） | ✅ |
| I7 零依赖 | —（落 §6 兼容性表） | §6 | D6 | ✅ |
| I8 计数链 | §6 | §7 | 头部/D1-D4 | ✅（F-S8-P044-1 后） |
| I9 AST/uv | §6 | §7 | D5/D6 | ✅ |
| G1-G7 缺口 | D1-D8 全映射（G1/G2→D2、G3→D4、G4→D7、G5→D3、G6→D6、G7→D5） | §2-§3 | A 组 | ✅ 全关闭（Step 10 复核） |

### 7.3 发现与当轮处置（4 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P044-1 | P3 | RESEARCH §8 I8 与 §13.1 复核行 black 仍记 **131·198**（S5 订正前旧值），与 DESIGN §6 / IMPL §7 / 本文件头部 / PROGRESS §3.50.5 的 **132·199** 不一致（同类先例 F-S8-P043-2） | RESEARCH 两处补订正并标注 F-S5-P044-1 来源 |
| F-S8-P044-2 | P3 | **批次字母三文档漂移**：RESEARCH §6 提案（B1=契约+注册/B2=适配器/B3=迁移/B4=测试）→ DESIGN §8（B1=strategy+registry/B2=adapter/B3=engine/B4=tests）→ IMPL §2 文件对齐拆分（B1=strategy.py 全量/B2=registry/B3=engine/B4=tests）——回退单元内容一致但字母错位，依赖声明同步漂移（RESEARCH「B3 依赖 B2」vs IMPL「B3 无 B1 依赖」） | DESIGN §1/§8 批次字母对齐 IMPL §2（订正标注）；RESEARCH §6 补「以 IMPL §2 为准」注 |
| F-S8-P044-3 | P3 | DESIGN 头部「同源评审才触发 U-P044-5，本轮不触发」与 RESEARCH §9 登记语义漂移（U-P044-5 因 Step 2 同源**已登记**，触发条件=进入 Step 10 终审）——现行措辞可被误读为「已不适用」 | DESIGN 头部措辞订正：U-P044-5 维持登记，Step 10 由 GLM 承接闭合 |
| F-S8-P044-4 | P3（micro） | DESIGN D4 状态演进 bullet 字面为 `positions=dict(weights)`，IMPL 实现为**零过滤后入状态**（`weights[weights != 0]`）——零 ≡ 缺席已证（IMPL §9.1-3），语义等价但字面不一致 | DESIGN D4 bullet 补注「positions 存非零项」 |

### 7.4 结论

**Step 8 一致性 Review pass（0 P1 / 0 P2 / 4 P3，全部当轮处置）**——RESEARCH S1-S10 / I1-I9 / G1-G7 与 DESIGN D1-D8 / IMPL §2-§3 / CHECKLIST 45 项四层对齐闭合；计数链经 F-S8-P044-1 订正后五文档一致；批次字母经 F-S8-P044-2 对齐后回退指引唯一。**准予进入 Step 9 TDD**（红态预测维持 `7 failed, 1 passed`，以实测为准）。

---

## 8. Step 10 ADD 审计记录（异构 GLM-5.3-Flash，2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 审计者 **GLM-5.3-Flash** ≠ Step 9 实施者 DeepSeek-V4.1-Flash → **本轮 ADD 即异构终审**（Step 4/6/8/10 四轮异构；**U-P044-5 在本轮闭合**，不再设独立终审轮）。
> **E3 绑定**: 审计在**未提交工作区**进行（HEAD `96384f6` + 未暂存 diff；D7 提交待用户授权）。

### 8.1 四阶段结论

| Phase | 项 | 读数 | 判定 |
|-------|----|------|------|
| 0 | 模糊词自审（审计语言） | 本节无「显然/明显/应该没问题」类断言；全部读数带命令 | ✅ |
| 1 | DESIGN D1-D8 落地 | D1 契约单文件（strategy.py L34-L322）/ D2 三 dataclass+Protocol（`TypeAlias` 为 F-S9-P044-1 落码订正）/ D3 `code_hash` 双异常回退（V2+P2）/ D4 适配器三件套（V5+P5）/ D5 `_signal_mode`+`set_signal`+单分支（V7+P4）/ D6 两迁移策略（V6）/ D7 registry 三符号（V8+P8）/ D8 零行为（V4+P7）——E2 探针逐项命中 | ✅ |
| 2 | 生产 diff ↔ IMPL §3 对拍 | `git diff --stat`：`engine_v2.py` +96/−31、`registry.py` +31、`PROGRESS.md` +101；**`git diff -w`：engine_v2 真实语义 +38/−2**（~58 行为缩进位移，F-S9-P044-3 证实）；`core/strategy.py` 新建（322 行）；测试新建（8 函数） | ✅ |
| 3 | 变更面越界 | `git status --short` 恰 **9 文件**（3 M：engine_v2/registry/PROGRESS + 6 新：strategy.py/4 文档/测试）；`config.py`/`event_log.py`/`streaming.py`/`agents/`/`tests/golden/`/`_synth_fixture.py`/`pyproject.toml`/`uv.lock` **零 diff** | ✅ |
| 4 | 深挖（探针 + 盲区） | E2 十五断言全过（**P5 `returns_window` 语义为套件未覆盖增量**——V5 因 cov_lookback=60>5 全 None，探针以 window=3 证实「历史不足→None + 窗口=截至前一日」）；E4 全净（8.3）；**0 新缺陷** | ✅ |

### 8.2 发现与处置（0 P1 / 0 P2 / 0 P3 新缺陷）

零新发现。按 RULE-6(c) 零发现不直接判合规，已完成**多角度降级重扫**并声明扫描范围：

| 重扫角度 | 覆盖 | 结果 |
|----------|------|------|
| E1 七门禁独立复跑 | 全量 pytest / golden / black 双口径 / mypy / AST / tests 计数 / uv | 全命中目标 |
| E2 独立探针（非测试套件） | 契约符号 / hash 粒度 / 状态 / fail-fast / **returns_window** / 端到端等价 / 零行为 / registry | 15/15 PASS |
| E3 语义 diff | `git diff -w` 量化缩进位移；新符号引用面 | +38/−2；无泄漏 |
| E4 盲区 | 既有批次产物（P-042 streaming / P-043 event_log）/ config / golden / 外部消费方 | 零触碰；registry 新符号无 core 外消费方（注册侧专用，预期） |

G1-G7 缺口闭合映射（RESEARCH→DESIGN）：G1/G2→D2、G3→D4、G4→D7、G5→D3、G6→D6、G7→D5——**七缺口全关闭**；U-P044-1/2/4 已裁决、U-P044-3→P-051 维持、**U-P044-5 本轮闭合**。

### 8.3 取证矩阵（RULE-6）

| 层 | 读数 |
|----|------|
| **E1** | pytest **`811 passed, 184 warnings in 63.47s`** / golden **`13 passed, 798 deselected`** / black **132 · 199** / mypy **`Success: no issues found in 105 source files`** / AST **22** / `tests/*.py` **93** / `uv lock --check` exit **0**——七门禁独立复跑全命中 |
| **E2** | 自编探针 `%TEMP%\p044_add_probe.py`（非测试套件）**15 断言全过**：P1 契约符号全集+`runtime_checkable` isinstance / P2 类级 hash 区分两策略（`FactorSignal≠Directional`）+`canonical_json` 键序无关 / P3 状态 JSON 往返 / P4 `set_signal` 五类 fail-fast+scores NaN / **P5 `returns_window` 历史不足→None+窗口=截至前一日（套件未覆盖增量）** / P6 weights≡scores trades+NAV / P7 默认零行为+两次运行一致 / P8 registry 注册/查询/覆写/注销；`PROBE_OK p044_all_8_groups` |
| **E3** | 读码 @未提交工作区（HEAD `96384f6` + diff）：`strategy.py` L34 `TypeAlias` / L47-77 `code_hash` 双异常回退 / L128-135 Protocol / L138-219 两策略 / L222-322 适配器；`registry.py` L15/L182/L225-230/L341-359；`engine_v2` L13/L184-185/L361-387/L1024-1057；`git diff -w` engine_v2 真实语义 **+38/−2**；`_signal_mode`/`set_signal` 引用面 = engine_v2+测试文件（无泄漏） |
| **E4** | 盲区扫描：变更面白名单外**零文件**；P-042 `streaming.py` / P-043 `event_log.py` / `config.py` / `agents/` / `tests/golden/` / `_synth_fixture.py` / `pyproject.toml` / `uv.lock` 零 diff；`_execute_rebalance` 原 try 体仅缩进（`git diff -w` 证实）；cursor/live/WS 面零触碰 |
| **E5** | 无推测——全部读数可重放 |

### 8.4 结论

**Step 10 ADD pass（0 P1 / 0 P2 / 0 P3 新缺陷，多角度重扫后记合规，扫描范围见 8.2）**；**U-P044-5 异构终审由本轮承接并闭合**（Step 4/6/8/10 四轮异构）。G1-G7 全关闭；U-P044-3 维持（P-051）。批次剩 **D7 提交与 CI 待用户授权**（6 文档中 CHANGELOG 尚待随提交写入，D8 随之闭合）。
