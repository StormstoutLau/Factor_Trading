# CHECKLIST：P-059 数据校验与边界场景库（scenario validation）

> **批次**: P-059 · 场景库地基 + 17 条边界场景 + 逐日 trace + 10 断言原语 + 统一 CLI + G4 修复
> **上游**: [DESIGN_p059](DESIGN_p059_data_validation.md)（§6 断言原语 / §7 R1-R3 / §8 S01-E03 / §10 能力边界 / §12 I1-I13 / §15 DoD A1-A12 / §16.1 Step 5 执行回写 / §17.2 Step 6 pass：1 P2 + 7 P3 / §17.3 Step 8 pass：1 P2 + 3 P3）；[RESEARCH_p059](RESEARCH_p059_data_validation.md)；[PROGRESS §3.53.1-§3.53.9](PROGRESS.md)
> **状态**: Step 7 产出（2026-11-19，DeepSeek-V4.1-Flash）；**Step 9 验收回填 58/58 `✅`**（2026-11-19）；**Step 10 终审回填 61/61 `✅`**（2026-11-19，GLM-5.3-Flash；批次关闭 commit `4eed0fa` / CI 44385648682 四 job 全绿）；`❌` **0**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；禁止预填
> **行号口径（F-S10-P045-2 教训）**: 本文件行号均 @未提交工作区（HEAD `5f85363` + diff）；提交后随 commit hash 稳定
> **基线读数（@`5f85363`，P-047 关闭）**: pytest **846** / `-k golden` **18** / mypy **109 files 0** / black `core tests` **137**、全仓 **205** / `tests/*.py` **95** / AST `except Exception`（core 外生产面）**22** / `uv lock --check` exit **0**
> **目标读数**: pytest **906**（846 + 60）/ `-k golden` **18（零重录）** / mypy **110 files 0**（+1 源 `scripts/verify_scenario.py`）/ black `core tests` **146**（+9 测试）、全仓 **215**（+10 = 9 测试 + 1 脚本）/ `tests/*.py` **104**（+9）/ AST **22（不变）** / `uv lock --check` exit **0**

---

## 1. A 组：DESIGN §15 DoD（12 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `SCENARIOS` 注册 **17** 条（14 必做 + 3 扩展），id 唯一，层覆盖 **7/7**（L1-L7） | 场景注册表落码 | `verify_scenario.py --list` + `::test_registry_contract` | ✅ `--list` 输出 17 行（S01-S14 / E01-E03）+ 末行「共 17 条；层覆盖 7/7」；`::test_registry_contract` PASS |
| A2 | 每条场景**闭式期望非空**且无「跑后录制」：`backtest` 的 `ExpectedBlock` 至少一项非空；`raises` 期望块为空；`stops`/`limit_price` 有 payload | 17 条 `expected` 落码 | `::test_each_scenario_declares_closed_form`（17 实例） | ✅ 17 实例全 PASS（14 backtest 有期望块 / S11 空块 / S13 与 E01 有 payload） |
| A3 | 每条 `backtest` 场景 `len(metamorphic) >= 1`，且三条关系（scale / inert / shift）全覆盖 | `Metamorphic` 声明落码 | `::test_every_backtest_scenario_declares_relation` | ✅ PASS；14 条 backtest 全覆盖，关系 15 条 = scale 11 + inert 2 + shift 2，三关系齐 |
| A4 | 逐日桶字段 == §4.3 表格 **10 键**（`date`/`target_weight`/`buyable`/`sellable`/`orders`/`filled`/`rejected`/`cash`/`nav`/`positions`）；拒单 `reason` ⊆ 10 项闭集 | trace + 断言落码 | `::test_bucket_and_reason_contract` + `assert_trace_shape` / `assert_reasons_closed` | ✅ `::test_bucket_and_reason_contract` PASS（10/10/3）；`assert_trace_shape` + `assert_reasons_closed` 在 14 条 backtest 场景全通过 |
| A5 | `trace_enabled=False` → **不 attach**，引擎持有原生 `ExecutionSimulator` / `PositionTracker` / `EqualWeightOptimizer`，`trace.buckets == {}` | T2 落码 | `::test_trace_disabled_keeps_native_components` | ✅ PASS：三组件 `is` 原生实例、`buckets == {}` |
| A6 | **G4 修复**：次日路径改用 `estimate_buy_cash`；现金 **1004** 两路径双拒（旧口径次日路径会成交）、**1010** 两路径双成交且 qty 相同；买入后现金 **4.00**、期末（末日强平后）**997.00** | T7 落码 | `::test_g4_hand_computed_boundary` / `::test_g4_paths_are_symmetric`（2 档）/ `::test_g4_1004_rejects_on_both_paths` / `::test_g4_1010_fills_on_both_paths` | ✅ 5 实例全 PASS：1004 双路径 `fills==[]` + `final_cash 1004`；1010 双路径 BUY 100@10、买入后 4.00、期末 997.00；手算 1006.00/6.00；红态已由 Step 6 临时回滚实跑 **2 failed** 实证 |
| A7 | **18 条 golden 零重录**（D10）：`tests/golden/*.json` 零 diff | 全量实现 | `pytest -q -k golden` + `git status tests/golden/` | ✅ **18 passed / 888 deselected**（13.99s）；`git status --short tests/golden/` 空输出 |
| A8 | 全量 **≥ 864 passed**（实际目标 906 = 846 + 60） | A1-A6 落码 | `pytest -q`（`MPLBACKEND=Agg`） | ✅ **906 passed, 239 warnings, 100.28s** |
| A9 | black / mypy（CI 等价命令，含 `scripts`）/ `uv lock --check` **三绿** | 全量实现 | 三条命令逐字复跑 | ✅ black 146·215 unchanged, 0 reformatted；mypy **110 files 0 issue**；uv exit **0** |
| A10 | 能力边界 **8 键**齐备且键集**完全等于** §10 清单（多/少均失败） | T6 落码 | `::test_capability_boundaries_declared` + `verify_scenario.py --boundaries`（JSON） | ✅ `::test_capability_boundaries_declared` PASS；`--boundaries` 输出 8 键 JSON（timeframe / intraday_auction / intraday_halt / delist_period_no_limit / expiry_basis / alpha_claim / execution_price / limit_price_rounding） |
| A11 | 接入规范 **≤3 行**：`SCENARIOS` 为 dict，新增一条 = 注册表加一行；测试与 CLI 自动拾取 | T4/T5 + CLI 落码 | `verify_scenario.py --list` + `::test_registry_contract` | ✅ `SCENARIOS` 为 17 键 dict；`--list` 自动列出全部；Step 8 的 17 处 `gaps` 改动后 60 项自动重跑全绿（零测试代码改动） |
| A12 | `core/` **仅 G4 一处行为改动**；`filter/limit_rules.py` **仅 docstring**；其余生产面零 diff | 全量实现 | `git diff --stat` + `git status --short` | ✅ `git diff --numstat`：`core/engine_v2.py` **+8/−1**（G4 行为）、`filter/limit_rules.py` **+6/−3**（仅 docstring）；其余生产面零 diff（`git status` 已跟踪源仅此 2 文件） |

## 2. B 组：实现任务 T1-T9 交付物（9 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | **T1** `tests/_scenarios_spec.py`（`REASONS` 10 / `ORDER_STATES` 3 / `BUCKET_KEYS` 10 / `SCENARIO_KINDS` 4 / `ScenarioSpec` frozen / `ExpectedBlock` / `Metamorphic` r1-r3）+ `tests/_scenarios_builder.py`（`build_scenario` 唯一入口 + `_validate_spec` 八类守卫） | — | 读码 + `::test_bucket_and_reason_contract` | ✅ 读码：[spec.py L24-54](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_spec.py#L24-L54) 四常量齐；`ScenarioSpec` `frozen=True, eq=False`（L119-120）；`_validate_spec`（[builder L258-305](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_builder.py#L258-L305)）含 dates 空/重复/非递增、codes 空/重复、factors 空、kind、layer 八类 + 矩阵形状/有限/正价 |
| B2 | **T2** `tests/_scenarios_trace.py`：三 proxy（`RecordingExecutor` / `RecordingTracker` / `RecordingOptimizer`）以 `__getattr__` 透传；`close_bucket` 以 `update_market_values` 为边界；末日二次调用幂等合并；`finalize` 收口仍活跃订单 | B1 | 读码 + `::test_scenario_trace_is_closed_and_complete` | ✅ `_RecordingBase.__getattr__` 透传（[trace L304-305](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_trace.py#L304-L305)）；`RecordingTracker.update_market_values` → `close_bucket`（L319-322）；`finalize` L188-193；`::test_scenario_trace_is_closed_and_complete` PASS |
| B3 | **T3** `tests/_scenarios_assert.py`：10 个原语（shape / order_states / reasons / mask / cash / price / weight_bounds / target_deviation / capability / dirty_input）+ `assert_scenario` 组合入口 + `_match_fills` 双向精确匹配 | B2 | 读码 + 各原语被 `assert_scenario` 调用 | ✅ 10 原语齐（assert.py L30-179）；组合入口 L204-276；`_match_fills` 双向（缺失即断言 + 余量 `assert not actual`，L201） |
| B4 | **T4** `_scenarios_cases.py` S01-S08 八例（L4×5 / L1×1 / L5×1 / L4 T+1） | B1-B3 | `verify_scenario.py --list` | ✅ S01-S08 在 `--list` 全部可见；8 个 `::test_p059_scenario[S0x]` 全 PASS |
| B5 | **T5** `_scenarios_cases.py` S09-S14 六例（L5×1 / L3×1 / L1×1 / L2×1 / L6×1 / L7×1） | B4 | `verify_scenario.py --list` | ✅ S09-S14 在 `--list` 全部可见；6 个实例全 PASS |
| B6 | **T6** `_scenarios_capability.py`：8 键（`timeframe` / `intraday_auction` / `intraday_halt` / `delist_period_no_limit` / `expiry_basis` / `alpha_claim` / `execution_price` / `limit_price_rounding`），各含 `supported` + `note` | B3 | 读码 + A10 | ✅ 8 键各含 `supported`+`note`（capability L11-43）；键集等值断言 PASS（A10） |
| B7 | **T7** G4 改造块与 DESIGN §9.1 目标代码逐字一致（仅替换费用口径，数量基数仍为 `order.quantity`，SELL 分支零改动）；修复前后 golden 均 18 passed | 独立 | 读码 + `pytest -k golden` | ✅ [engine_v2 L1273-1284](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1273-L1284) 与 §9.1 逐字一致（`order.quantity * open_price` + 三参数）；golden 修复前/后均 18 passed |
| B8 | **T8** 三个测试模块（39 / 16 / 5 = **60**）+ `scripts/verify_scenario.py` 五命令（`--list` / `--scenario` / `--day` / `--json` / `--boundaries`）；`--json` 可序列化 dataclass | B4-B7 | `pytest --collect-only` + CLI 五命令冒烟 | ✅ collect 39/16/5 = **60**；五命令实测：`--list` 17 行、`--scenario S02 --day 2024-01-04` 输出当日桶（cash 2000/positions 9800）、`--scenario S02 --json` exit 0、`--scenario S13` 走非 backtest 分支、`--boundaries` 8 键 JSON |
| B9 | **T9** E01-E03 三例注册（涨跌停不舍入 / 长假缺口 / 复权因子变更）+ `special_no_limit_mask` docstring 订正（删除不存在的 `delist_start_date` 分支，补记 `list_date` 过早副作用） | B8 | `verify_scenario.py --list` + 读码 | ✅ E01/E02/E03 在 `--list`；[limit_rules L180-189](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L180-L189) 新 docstring 无 `delist_start_date` 分支表述，含 `list_date` 过早副作用说明 |

## 3. C 组：不变式（DESIGN §12 I1-I13，13 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1 确定性**：闭式期望逐日全等（非确定性会立即红）；独立双跑测试未单列（§12 Step 6 回写口径） | 全部场景 | `::test_p059_scenario`（17） | ✅ 17 实例全 PASS（逐日 NAV/现金/持仓与手算闭式逐值相等） |
| C2 | **I2 账目恒等**：运行期 `core.invariants.check_all` 不报错；trace 侧逐桶 `cash + Σqty×close == nav` | B3 | `assert_scenario` 的 `_assert_cash_identity` | ✅ `cash_identity=True` 默认；14 条 backtest 场景逐桶通过（`_assert_cash_identity` L278-288） |
| C3 | **I3 trace off 零行为**：同 A5 | B2 | `::test_trace_disabled_keeps_native_components` | ✅ PASS（同 A5） |
| C4 | **I4 订单三态完备**：终态 ⊆ {filled, retry, dropped}；订单身份 = `(code, side, create_date, quantity)`，同一订单不得同时 filled 与 dropped | B3 | `assert_order_states_closed`（`assert_scenario` 内） | ✅ 全部 PASS；S02 的「旧卖单 dropped + 新卖单 filled」按 create_date 分键正确 |
| C5 | **I5 掩码一致**：不可买 → 无买成交；不可卖 → 无卖成交（`exempt` 豁免退市结算） | B3 | `assert_mask_semantics` | ✅ 全部 PASS；S07 退市清算 SELL 经 `exempt` 放行 |
| C6 | **I6 现金非负**：逐桶 `cash >= -1e-6` | B3 | `assert_cash_non_negative` | ✅ 全部 PASS |
| C7 | **I7 价格合法**：成交价 ∈ [跌停价, 涨停价]（由 `filter.limit_rules` 计算，场景内不重算；无涨跌幅日与 `exempt` 跳过） | B3 | `assert_price_legal` | ✅ 全部 PASS（E03 复权口径与 S06 IPO 无限制窗口正确跳过） |
| C8 | **I8 golden 零重录**：同 A7 | 全量 | `pytest -k golden` | ✅ 18 passed / 888 deselected；golden 目录零改动 |
| C9 | **I9 R1 价格缩放**：价格四键 × k 且 `initial_capital × k` → 成交笔数/持仓股数不变、金额类按 k 等比 | B8 | `::test_p059_metamorphic[*-scale]`（11 实例） | ✅ 11 实例全 PASS（k = 1.5 / 2.0 / 3.0） |
| C10 | **I10 R2 惰性标的**：追加惰性标的（因子 NaN / 信号 0）→ 现金、NAV、成交逐日完全一致 | B8 | `::test_p059_metamorphic[*-inert]`（2 实例） | ✅ 2 实例（S05 / S09）PASS |
| C11 | **I11 R3 日期平移**：交易日整体平移 → 桶数一致、逐日金额与持仓一致 | B8 | `::test_p059_metamorphic[*-shift]`（2 实例） | ✅ 2 实例（S04 / S14，+7 天）PASS |
| C12 | **I12 脏数据显式失败**：`close` 含 NaN → 构建期 `ValueError`（不进入引擎） | B8 | `::test_p059_scenario[S11]` | ✅ PASS（`assert_dirty_input_raises` 捕获 ValueError） |
| C13 | **I13 trace 桶数 == 交易日数**且日期严格递增、10 键齐备 | B2 | `assert_trace_shape`（全部 backtest 场景） | ✅ 14 条 backtest 场景全通过；S02 另由 `::test_scenario_trace_is_closed_and_complete` 独立复验（5 桶 == 5 交易日） |

## 4. D 组：场景逐条验收（17 项）

> 每行给**手算闭式关键值**（A2 反录制）；完整期望见 `_scenarios_cases.py` 对应块。

| ID | 场景与关键闭式值 | 层 | 证据出口 | 实测 |
|----|------------------|----|----------|------|
| D1 | **S01** 涨停买不进：d1 A 开盘 11.0 拒、d2 @10 成交 4900；B 4900；末日双卖 → 现金/NAV 100000 | L4 | `::test_p059_scenario[S01]` | ✅ PASS（4 笔成交逐笔匹配、期末 100000） |
| D2 | **S02** 跌停顺延：d0 全仓 A 9800；d1 卖单 d2 跌停拒（dropped+重建）；d3 @9 成交；NAV d2 = 2000+9800×9 = **90200** | L4 | `::test_p059_scenario[S02]` | ✅ PASS（NAV d2/d4 = 90200、期末现金 90200） |
| D3 | **S03** 一字板：11.0/12.1/13.31 三日 buyable=False；d4 @12.5 买 4900 并强平 | L4 | `::test_p059_scenario[S03]` | ✅ PASS（三日 buyable False + d4 买/卖 4900） |
| D4 | **S04** 停牌 2 日：d1/d2 retry 且 NAV=100000；d3 @10 买 9800；d4 清仓 | L1 | `::test_p059_scenario[S04]` | ✅ PASS（d1/d2 retry、NAV 恒 100000、d3 成交 9800） |
| D5 | **S05** 主板 ST 5%：d1 开盘 10.5 = 10×1.05 拒；d2 @10.5 成交 4900（数量按创建日价 10 计算） | L4 | `::test_p059_scenario[S05]` | ✅ PASS（d1 buyable False、d2 成交 4900@10.5） |
| D6 | **S06** IPO 前 5 日无涨跌幅：d1 @13 成交 4900（超 10% 带仍可买）；d5 = 13×1.1 = 14.3 涨停 buyable=False | L4 | `::test_p059_scenario[S06]` | ✅ PASS（d1 buyable True 成交、d5 buyable False） |
| D7 | **S07** 退市清算：d3 清算价 10×0.5 = **5.0**，9800 股回款 49000 → 期末现金 **51000**（`exempt`） | L5 | `::test_p059_scenario[S07]` | ✅ PASS（SELL 9800@5.0、期末 51000、持仓归零） |
| D8 | **S08** T+1：d1 买 9800 当日不可卖（no_fill）；d2 @10 卖出 | L4 | `::test_p059_scenario[S08]` | ✅ PASS（d1 无 SELL 成交、d2 SELL 9800 成交） |
| D9 | **S09** 最低佣金整单拒绝：现金 1004 < 1000+5+1 = **1006** → 无成交、现金仍 1004（队列路径） | L5 | `::test_p059_scenario[S09]` | ✅ PASS（`fills == []`、期末现金 1004） |
| D10 | **S10** 权重和 >1：注入 0.8/0.8 → 各 **7800** 股；仅 A 成交（现金 22000），B 因现金不足 retry 至过期 | L3 | `::test_p059_scenario[S10]` | ✅ PASS（A 7800 成交、B d1 retry 且 d4 仍无成交） |
| D11 | **S11** 脏输入：`close[1,0]=NaN` → 构建期 `ValueError` | L1 | `::test_p059_scenario[S11]` | ✅ PASS |
| D12 | **S12** 全标的停牌：再平衡早退、零订单、NAV 恒 100000 | L2 | `::test_p059_scenario[S12]` | ✅ PASS（5 日 NAV 全 100000、零成交） |
| D13 | **S13** 止损止盈同 bar：`low=88 ≤ 90` 且 `high=110 ≥ 105` → 优先级 **stop_loss** | L6 | `::test_p059_scenario[S13]`（`StopEngine` 纯函数） | ✅ PASS（期望序列 `[("hold",""),("exit","stop_loss")]` 逐项相等） |
| D14 | **S14** 空信号清仓：d0 三标的各 **3200** 股；d1 目标归零、d2 三笔卖出 → 现金 100000 | L7 | `::test_p059_scenario[S14]` | ✅ PASS（6 笔成交逐笔匹配、期末 100000） |
| D15 | **E01** 涨跌停不舍入：前收 **10.03** → 涨停 **11.033**（≠ 11.03，且 ≠ round(·,2)） | L4 | `::test_p059_scenario[E01]`（`build_limit_prices`） | ✅ PASS（`up == 11.033` 且 `!= round(up,2)`） |
| D16 | **E02** 长假缺口：d0 挂单在 **01-15** 首个交易日按开盘 @10 成交 9800；d4 清仓 | L4 | `::test_p059_scenario[E02]` | ✅ PASS（d1 01-15 成交 9800、d4 清仓） |
| D17 | **E03** 复权因子变更：adj 1→2，raw 口径 NAV 恒 **100000**；d2 起限价参考 **5.0** → 涨停 5.5，buyable=False | L5 | `::test_p059_scenario[E03]` | ✅ PASS（5 日 NAV 全 100000、d1 buyable True / d2 False） |

## 5. E 组：门禁与静态检查（7 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| E1 | pytest 全量 **906 passed**（846 + 60，`MPLBACKEND=Agg` + Python312） | A1-A12 | 全量末行 | ✅ **906 passed, 239 warnings, 100.28s** |
| E2 | `-k golden` **18 passed / 888 deselected**（906 − 18 = 888）；`git status tests/golden/` 无改动 | A7 | 命令 + `git status` | ✅ **18 passed, 888 deselected, 13.99s**；golden 目录 `git status` 空输出 |
| E3 | 新测试收集数 **60**（39 + 16 + 5，逐模块 collect 计数） | B8 | `pytest --collect-only -q tests/test_p059_*.py` | ✅ scenarios **39** + metamorphic **16** + g4 **5** = **60** collected |
| E4 | black **146**（`core tests`，137 + 9）/ **215**（全仓，205 + 10）files unchanged，0 reformatted | B8/B9 | `black --check core tests` + `black --check .` | ✅ **146 files unchanged**（core tests）/ **215 files unchanged**（全仓），0 reformatted |
| E5 | mypy **CI 确切命令**（`--explicit-package-bases --check-untyped-defs` 十四目录含 `scripts`）→ **110 source files, 0 issue**（109 + 1） | B8 | 逐字命令 | ✅ **Success: no issues found in 110 source files** |
| E6 | **AST 等价（ad-hoc 22 文件口径）**：`core/engine_v2.py` 差异 = **1 语句块（G4 有意行为修复，豁免理由 D2）**；`filter/limit_rules.py` 差异 = **仅 docstring（第二豁免，T9）**；`scripts/verify_scenario.py` 不在 22 清单；`except Exception` 生产面（core 外）**22 不变**、`core` 内 **29 不变**，本批零新增 | B7/B9 | AST 静态扫描 + `git diff` | ✅ AST：core 外 **22**（agents 11 / filter 5 / scripts 2 / batch_backtest 2 / strategy_evaluation 1 / cli 1）、core **29**、全扫 **55** —— 与基线逐目录一致；diff 仅 2 生产文件（engine_v2 **+8/−1**、limit_rules **+6/−3**），均为双豁免声明项 |
| E7 | `uv lock --check` exit **0**（`pyproject.toml` / `uv.lock` 零 diff，零新依赖） | 全量 | 命令 + `git diff` | ✅ exit **0**（Resolved 148 packages）；两文件零 diff |

## 6. F 组：提交与文档（3 项，待 Step 10）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| F1 | 提交原子（**17 文件** = 新源 **1** `scripts/verify_scenario.py` + 新测试 **9** `tests/_scenarios_*.py`×6 + `tests/test_p059_*.py`×3 + 已跟踪源 **2** `core/engine_v2.py` + `filter/limit_rules.py` + 新文档 **3** RESEARCH/DESIGN/CHECKLIST + 已跟踪文档 **2** PROGRESS/UPGRADE_MASTER_PLAN；核算 1+9+2+3+2 = 17）；**须用户明确授权后才可 commit** | E1-E7 通过 + 用户授权 | `git show --stat` | ✅ commit **`4eed0fa`**：**17 files changed, +3823/−7**（13 create mode + 4 modified），清单与 DoD 逐项一致（`git status` 提交前核对 4 M + 13 ??）；用户 AskUserQuestion 明确授权（2026-11-19「授权，执行 D8+D9」） |
| F2 | CI 四 job 全绿（lock-check / Python 3.10 / 3.11 / 3.12） | F1 | `gh run view` | ✅ run **44385648682**（push `4eed0fa` 触发）四 job 全绿：lock-check **8s** / test 3.10 **2m2s** / 3.11 **2m38s** / 3.12 **2m19s** |
| F3 | 文档回填：DESIGN §16.1 / §17.2 / §17.3 在位；PROGRESS §3.53.6-§3.53.11（Step 5-10）；本文件 61 行实测列（58 项已回填 + 3 项待终审）；CHANGELOG 是否需要条目按仓库惯例判定 | F2 | 读回 | ✅ 读回：DESIGN §16.1 / §17.2 / §17.3 在位 + §17.4 本步回填；PROGRESS §3.53.6-§3.53.11 在位（§3.53.11 本步补）；本文件 61 行实测列全 ✅（本步回填 F1-F3）；CHANGELOG 按仓库惯例增 **P-059 Added 条目**（`[Unreleased]` 首位） |

---

## 7. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **61**（A 12 + B 9 + C 13 + D 17 + E 7 + F 3 = 61，逐表行数机械计数） |
| Step 7 实测列状态（产出时） | `[待 Step 9]` **58** + `[待 Step 10]` **3**；`✅` **0**；`❌` **0** |
| Step 9 实测列状态（回填后） | `✅` **58** + `[待 Step 10]` **3**；`❌` **0**；**58 + 3 = 61 ✓** |
| Step 10 实测列状态（回填后） | `✅` **61**；`[待 Step 9]` **0**；`[待 Step 10]` **0**；`❌` **0**；**61 = 61 ✓** |
| 新用例数 | **60** = `test_p059_scenarios` **39**（17 场景 + 1 注册 + 17 闭式 + 1 桶/reason + 1 能力 + 1 trace-off + 1 trace 闭合）+ `test_p059_metamorphic` **16**（15 关系 + 1 注册）+ `test_p059_g4_cash_parity` **5** |
| Step 9 门禁实测 | pytest **906**（100.28s）/ golden **18**（888 deselected）/ collect **60**（39+16+5）/ black **146·215**（0 reformatted）/ mypy **110 files 0 issue** / AST **22·29**（不变）/ `tests/*.py` **104** / uv exit **0** |

> **RULE-2 统计溯源**：61 = 12 + 9 + 13 + 17 + 7 + 3（逐表行数）；58 + 3 = 61（Step 9 回填）；60 = 39 + 16 + 5（模块 collect）；906 = 846 + 60；110 = 109 + 1（`scripts/verify_scenario.py`）；146 = 137 + 9（`tests/_scenarios_*` 6 + `tests/test_p059_*` 3）；215 = 205 + 10（上列 9 + 1 脚本）；104 = 95 + 9；AST 22/29 不变（本批文件零 `try/except Exception`）。
> **RULE-5 声明**：Step 1/3/5/7/9 作者 **DeepSeek-V4.1-Flash**；Step 2 / 4 / 6 / 8 复审**异构成立**（GLM-5.3-Flash：RESEARCH §11 / DESIGN §17.1 / DESIGN §17.2 / DESIGN §17.3）；Step 10 终审**已由 GLM-5.3-Flash 执行**（§10，与作者异构成立）。

---

## 8. Step 7 → Step 8 交接

1. **核计数链**：846 + 60 = **906**；15 关系 + 1 注册 = 16；39 + 16 + 5 = **60**；109 + 1 源 = **110**；137 + 9 = **146**、205 + 10 = **215**；95 + 9 = **104**；AST **22 不变**。绝对基线以 Step 9 复跑为准。
2. **核零预填**：Step 9 前 `[待 Step 9]` 须为 **58**、`[待 Step 10]` 须为 **3**；任何 `✅` 出现即为违规。
3. **核 ID 不混用**：DESIGN §15 的 **A1-A12**（DoD）与本文件 **A 组**同号同义（有意对齐）；DESIGN §16 的 **T1-T9** 对应本文件 **B 组**；DESIGN §12 的 **I1-I13** 对应 **C 组**；场景 **S01-S14 / E01-E03** 对应 **D 组**；**G4** 在 DESIGN 中指「缺口编号」，本文件 **D 组 D 行**才指验收项；发现编号 `F-S{4,5,6,8,9}-P059-*`。**RESEARCH §8 I1-I12 与 DESIGN §12 I1-I13 同号不同义**（RESEARCH I2=零行为 846 / DESIGN I2=账目恒等；RESEARCH I7 含整手 / DESIGN I7 仅价格带；F-S8-P059-4，P-047 O-S8-P047-1 同型）——C 组一律锚定 **DESIGN 口径**。场景 `gaps` 已按 DESIGN §8 覆盖列对齐（**Step 8 回写** F-S8-P059-1，S12 随 F-S5-P059-2 前提改挂 BZ14/G9）。
4. **核手算口径**：整手公式 `floor(w·100000·0.985/price/100)·100` **按订单创建日价**（非执行日价，S05 为反例证据）；零成本场景（除 S09/G4 对拍）现金口径为整数；末日强平按收盘价 —— 期末现金可能不同于「买入后现金」（G4 1010 档：4.00 vs 997.00）。
5. **核不变式口径**：`assert_target_deviation` 已定义但**未接线**（F-S6-P059-4 登记，C 组不列该项）；I1 为「闭式期望逐日全等」而非独立双跑（F-S6-P059-7 回写）。
6. **核不做清单**：不改 `core/` 除 G4 一处行为 + `limit_rules` docstring；不引入 Hypothesis / 第三方回测框架；不建模盘中临停 / 集合竞价 / 退市整理期无涨跌幅；不重录 golden；不为 alpha 作任何声明。
7. **核遗留登记**：F-S6-P059-4（`assert_target_deviation` 未接线）/ -5（`_reject_reason` BUY 兜底死代码）/ -6（`close_bucket` 末日幂等合并不彻底）为**登记项**，不在本批修复；F-S5-P059-1~8 已在 DESIGN §16.1 留档；F-S8-P059-1~4 已在 DESIGN §17.3 留档。

---

## 9. Step 9 验收小结（2026-11-19，DeepSeek-V4.1-Flash）

| 门禁 | 命令 / 方法 | 实测 | 目标 | 判定 |
|------|-------------|------|------|------|
| pytest 全量 | `MPLBACKEND=Agg` + Python312 `pytest -q` | **906 passed**, 239 warnings, 100.28s | 906 | ✅ |
| golden 计数 | `pytest -q -k golden` | **18 passed, 888 deselected**, 13.99s | 18 / 888 | ✅ |
| 用例收集 | 逐模块 `pytest --collect-only -q` | **39 + 16 + 5 = 60** | 60 | ✅ |
| black（`core tests`） | `black --check core tests` | **146 unchanged**, 0 reformatted | 146（137+9） | ✅ |
| black（全仓） | `black --check .` | **215 unchanged**, 0 reformatted | 215（205+10） | ✅ |
| mypy（CI 等价） | 十四目录 `mypy --explicit-package-bases --check-untyped-defs` | **110 source files, 0 issue** | 110 | ✅ |
| AST 盲区 | `except Exception` AST 扫描 | core 外 **22** / core **29** / 全扫 **55** | 22·29 不变 | ✅ |
| 测试文件数 | `tests/*.py` | **104** | 104（95+9） | ✅ |
| lock 一致性 | `uv lock --check` | exit **0**（Resolved 148 packages） | exit 0 | ✅ |
| diff 范围 | `git diff --numstat` | `core/engine_v2.py` **+8/−1**；`filter/limit_rules.py` **+6/−3**（docstring） | 见 A12 | ✅ |
| CLI 五命令 | `--list` / `--scenario` / `--day` / `--json` / `--boundaries` | 全部 exit 0；`--json` 含 fills/expectation 全字段；非 backtest 场景走声明分支 | 5/5 | ✅ |
| golden 目录 | `git status --short tests/golden/` | 空输出 | 零改动 | ✅ |

**回填统计**：58 项 `[待 Step 9]` → **58 ✅ / 0 ❌**；F 组 3 项维持 `[待 Step 10]`（提交需用户授权）。

**发现（当轮处置）**：

- **F-S9-P059-1（P3，文档笔误）**：本文件 F3 在 Step 7 版把 PROGRESS 章节预写为「§3.53.8（Step 9）/ §3.53.9（Step 10）」，但 §3.53.8 实为 Step 7、§3.53.9 实为 Step 8 → Step 9 = **§3.53.10**、Step 10 = **§3.53.11**。**处置**：F3 DoD 改为「§3.53.6-§3.53.11（Step 5-10）」，并在 PROGRESS 按实际序号登记本步骤。
- **F-S9-P059-2（P3，口径说明）**：A6 的「红态」不在 Step 9 重跑（重跑需再次临时回滚生产代码），沿用 Step 6 §17.2.4-F-S6-P059-3 的实证（旧口径对拍 **2 failed** → 恢复后全绿、文件哈希一致）；本步骤不重复破坏性验证。

**结论**：**61 项中 58 项 ✅ / 3 项 `[待 Step 10]` / 0 项 ❌**，全部门禁达标，**准予进入 Step 10 终审**（D8/D9 待用户授权后执行）。

---

## 10. Step 10 终审小结（2026-11-19，GLM-5.3-Flash）

> 终审者 GLM-5.3-Flash 与作者 DeepSeek-V4.1-Flash 异构成立（RULE-5）；**U-P059-6（终审异构）于此闭合**。

**门禁独立复跑**（不采信 Step 9 自报，全部本步骤重跑）：

| 门禁 | 实测 | 目标 | 判定 |
|------|------|------|------|
| pytest 全量 | **906 passed**, 239 warnings, 102.18s | 906 | ✅ |
| golden 计数 | **18 passed / 888 deselected** | 18 / 888 | ✅ |
| 用例收集 | **39 + 16 + 5 = 60** | 60 | ✅ |
| black | **146**（core tests）/ **215**（全仓）unchanged | 146·215 | ✅ |
| mypy（CI 命令） | **110 source files, 0 issue** | 110 | ✅ |
| AST `except Exception` | core 外 **22** / core **29** / 全扫 **55** | 22·29 不变 | ✅ |
| `tests/*.py` | **104** | 104 | ✅ |
| `uv lock --check` | exit **0** | exit 0 | ✅ |
| 工作区（提交前） | **17 文件**（4 M + 13 ??） | 17 | ✅ |

**锚点核对与派生需求抽核**：CHECKLIST 3 项 `[待 Step 10]`（L102-104）+ §10 占位在位；DESIGN §17.4 占位在位；`scripts/verify_scenario.py` L45 `dataclasses.asdict`（F-S6-P059-1 修复）在位；`_scenarios_cases.py` S11 `gaps=("BZ1","G10")`（F-S8-P059-1 对齐）在位；CHANGELOG 惯例核对（`[Unreleased]` 每批次登记，P-011..P-047 全覆盖）→ P-059 需 Added 条目。遗留后台 diff（`core/stops.py` / `tests/test_p047_position_sizing.py` 格式化对比）为 P-047 已入库内容的陈旧输出，不在本批 17 文件内，无需处理。

**D8 提交**（用户 AskUserQuestion 明确授权后执行）：commit **`4eed0fa`** `feat(P-059): 数据校验与边界场景库（17 场景 + 逐日 trace + 10 断言原语 + G4 修复）`，**17 files +3823/−7**；push `5f85363..4eed0fa`；CI run **44385648682** 四 job 全绿（lock-check 8s / 3.10 2m2s / 3.11 2m38s / 3.12 2m19s）。

**D9 关闭回填**：本文件 F1/F2/F3 ✅ + §10 本节 + §7 Step 10 行 + 状态头；DESIGN §17.4；PROGRESS §3.53.11；CHANGELOG P-059 Added 条目；关闭提交 `docs(P-059)` + push + CI 复验。

**结论**：**61/61 ✅ / 0 ❌ / 0 新发现**，**批次 P-059 关闭**。遗留登记项 F-S6-P059-4 / -5 / -6（`assert_target_deviation` 未接线 / BUY 兜底死代码 / 末日幂等合并不彻底）随台账跟踪，不在本批。
