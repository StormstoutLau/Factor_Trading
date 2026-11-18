# CHECKLIST：P-045 择时原语与止损状态机（timing + stops）

> **批次**: P-045 · **T1**（新建 `core/timing.py` + `core/stops.py` + `tests/` + 2 golden case + 对拍脚本）
> **上游**: [IMPL_p045](IMPL_p045_timing_stops.md)（§2 B1-B3 / §3 完整代码 / §4 V1-V8+G1/G2 / §4.6 对拍规格 / §7 门禁 / §9 Step 6 pass：1 P2 + 2 P3）；[DESIGN_p045](DESIGN_p045_timing_stops.md)（D1-D9 / §6 不变式 I1-I9 / §10 Step 4 pass：8 P3）；[RESEARCH_p045](RESEARCH_p045_timing_stops.md)（§7 S1-S10 / §8 I1-I9 / §13 Step 2 pass）
> **状态**: Step 10 ADD 审计 **pass**（2026-11-18；异构 GLM-5.3-Flash，U-P045-5 闭合，见 §8）；实测列 **45/47**（D8/D9 待提交授权）；2 P3 当轮订正（F-S10-P045-1/2）+ 1 P3 订正（F-S10-P045-5）+ 2 观察（F-S10-P045-3/4）；八门禁复跑全绿 + 对拍 exit 0 + 探针 32 断言全过
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；禁止预填
> **基线读数（@`0482881`，P-044 关闭）**: pytest **811** / golden **13 passed, 798 deselected** / black `core tests` **132**（全仓 **199**）/ mypy **105 files 0** / AST `except Exception` **22**（core 外口径）/ `tests/*.py` **93** / `uv lock --check` exit **0**
> **目标读数**: pytest **821** / golden **15**（既有 13 零重录）/ black **135**（全仓 **203**）/ mypy **108 files 0**（F-S10-P045-1 订正）/ AST **22（不变）** / `tests/*.py` **94** / `verify_p045` exit **0** / uv exit **0**

---

## 1. A 组：代码变更（14 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `crossed_above` / `crossed_below`：`prev = series.shift(1)` + 严格不等式（`>`/`<` 与 `<=`/`>=`）；首行与任一 NaN 参与比较恒 **False**（DESIGN-D3，F-S8-P045-10 订正引用） | 无（原语优先落码） | 读码 + V1 | ✅ timing.py L16-28 逐字；V1 PASS |
| A2 | `SignalSet` 为 `@dataclass(frozen=True)` 四字段（`entries_long`/`exits_long` 必填，`entries_short`/`exits_short` 默认 `None`）；`__post_init__` 用 `.equals` 校验 index 与 columns，不一致抛 `ValueError`（match 分别含 `index` / `columns`）；docstring 标注 **禁用 `==`**（F-S4-P045-2） | A1 落码 | 读码 + V2 | ✅ timing.py L31-48（构造期 `match="index"`）；V2 PASS |
| A3 | `_as_bool`：`fillna(False).astype(bool)`，**不修改入参**；`resolve_conflicts`：`entries & ~exits`（exit 优先、entry 被抵消），`exits` 原样，short 两侧透传 | A2 落码 | 读码 + V2 | ✅ timing.py L51-65；V2 PASS |
| A4 | `holdings_from_signals`：NaN 底矩阵 → `mask(exits, 0.0)` → `mask(entries & ~exits, 1.0)` → `ffill()` → `fillna(0.0)` → `bool`（mask 序即 exit 优先，DESIGN-D4，F-S8-P045-10 订正引用） | A2/A3 落码 | 读码 + V2 | ✅ timing.py L68-75；V2 PASS（A `[T,T,T,F,T]` / B 全 F） |
| A5 | `weights_from_holdings`：`mode != "equal"` → `ValueError`（match `未知权重模式`）；`counts = held.sum(axis=1)`；除数 `counts.replace(0.0, np.nan)`（**不用 `where`/裸除**）；`fillna(0.0)`；**不重归一**、行和 ∈ {0,1} | A4 落码 | 读码 + V3 | ✅ timing.py L78-85；V3 PASS |
| A6 | `apply_timing`：`holdings.reindex(index=targets.index, columns=targets.columns)` **keyword 形式**（F-S4-P045-1）；`targets.where(aligned, 0.0)`；不重归一 | A3 落码 | 读码 + V4 | ✅ timing.py L88-95（keyword reindex）；V4 PASS |
| A7 | `StopConfig` frozen 五字段（`stop_loss_pct`/`trailing_stop_pct`/`take_profit_pct`/`time_stop_days`/`trailing_activate_pct`，均 `Optional`）；`__post_init__`：四百分比字段 `<= 0` → `ValueError`（match `正数`），`time_stop_days < 1` → `ValueError`（match `time_stop_days`）；docstring 声明「正号约定，与 `risk_manager.StopLossConfig` 不复用」 | 无（新建模块首个类型） | 读码 + V8 | ✅ stops.py L20-44；V8 PASS（`正数` / `time_stop_days` 双 raises） |
| A8 | `StopBar`（`date`/`open`/`high`/`low`/`close`）+ `StopState`（`entry_price`/`peak_price`/`bar_count`/`entry_date`）+ `to_dict`（float/int 归一）/ `from_dict`（仅按四键取值） | A7 落码 | 读码 + V5/V8 | ✅ stops.py L47-82；V5/V8 PASS |
| A9 | `StopDecision`（`action`/`reason` 默认 `""`/`severity` 默认 `1.0`）+ `StopTrigger`（六字段，含 `exit_price_ref`）+ `StopResult`（`weights`/`triggers`/`states`/`deferred`；docstring 标注 **禁用 `==`**） | A8 落码 | 读码 + V8 | ✅ stops.py L85-113；V8 PASS |
| A10 | `StopEngine.update` 七步：① `state is None` → 建仓（`entry=close`、`peak=max(high, close)`、`count=1`、`entry_date` 格式化）**不判触发**；② `peak=max(prev_peak, high)`、`count+1`，先建 `updated`；③ SL：`open <= entry*(1-sl)` **或** `low <= entry*(1-sl)`（gap 与盘中同归 `stop_loss`）；④ trailing：激活条件 `trailing_activate_pct is None or peak >= entry*(1+activate)`，且 `low <= peak*(1-trailing)`（**更新后峰值**，同 bar 激活即触发）；⑤ TP：`high >= entry*(1+tp)`；⑥ time：`count >= time_stop_days`；⑦ 兜底 `hold` | A7-A9 落码 | 读码 + V5/V6/V7 | ✅ stops.py L122-168；V5/V6/V7 PASS（七步优先级链） |
| A11 | `ohlc_from_data`：`{key: dm.get_adj_price(key, "raw") for key in _BAR_KEYS}`，`_BAR_KEYS = ("open","high","low","close")`；`IDataManager` 仅 `TYPE_CHECKING` 导入（运行期零依赖） | A7 落码 | 读码 | ✅ stops.py L171-173；`TYPE_CHECKING` 导入；读码 |
| A12 | `apply_stops`：入场三类 fail-fast（缺键 match `缺少键` / `bars` 网格 NaN match `缺失值` / `targets` NaN match `NaN`）；`tradable` reindex + `fillna(False).astype(bool)`；逐日逐标的：无 state 且 `weight > 0` → 建仓；有 state → `update`；`exit` 且可交易 → `weights.at = 0.0` + 追加 trigger + `del states[code]` + **`continue`（禁同日重建）**；`exit` 不可交易 → `deferred += 1` + 保留 state；`hold` 且 `weight <= 0` → `del states[code]`（策略主动清仓）；`hold` 且 `weight > 0` → 更新 state；返回 `StopResult`（`triggers` 转 tuple、`states` 转 `to_dict`） | A10 落码 | 读码 + V7/V8 | ✅ stops.py L175-263；V7/V8 PASS（三类 fail-fast + deferred + 禁同日重建） |
| A13 | 两模块为纯函数：`grep -E "open\(|requests\."` = **0**；无模块级副作用（仅常量/类型/函数）；`core/timing.py` **不 import `core.strategy`**（避免 P-044 循环） | A1-A12 落码 | grep + 读码 | ✅ grep `open(|requests.` = **0**（两模块）；timing 零 `core.strategy` 导入 |
| A14 | `scripts/external_benchmark/verify_p045.py`（新建）：隔离 venv `.venv-vbt`（`vectorbt==1.2.0`）；`P045_S1` 共同输入；本仓 `apply_stops` vs vbt `from_signals(sl_stop=0.10, sl_trail=True, tp_stop=0.20, fees=0)`；**触发判定序列（date, code, reason）逐值比对**；waiver 显式（激活阈值免费版无 `tsl_th`、成交价/NAV 差异）；三态词表 pass/fail/waiver；输出附录 | A12 落码 | 脚本 exit 0 + 附录 | ✅ exit **0**（7 断言 + 4 waiver）；[附录](APPENDIX_p045_external_calibration.md) |

## 2. B 组：测试与 golden（14 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | V1 交叉检测：`[F,F,F,T,F,F]`（上穿）/ `[F,F,T,F,F,F]`（下穿）；等值序列**零交叉**（严格不等式） | A1 落码 | `tests/test_p045_timing_stops.py::test_v1_crossed_above_below` | ✅ PASS |
| B2 | V2 冲突与持仓：同日 entry+exit → `resolved.entries_long` 对应位 False；holdings A `[T,T,T,F,T]`、B 全 False；`SignalSet` index 不等 → `ValueError(match="index")`（**构造期**；Step 6 复核订正 pytest.raises 位置，F-S8-P045-10） | A2-A4 落码 | `::test_v2_conflicts_and_holdings` | ✅ PASS |
| B3 | V3 等权权重：`[0.5,0.5,0.0]` / `[0.0,0.0,0.0]` / `[1.0,0.0,0.0]`；行和集合 ⊆ {0,1}；`mode="risk_parity"` → `ValueError(match="未知权重模式")` | A5 落码 | `::test_v3_weights_from_holdings` | ✅ PASS |
| B4 | V4 gate：`gated.sum(axis=1) == [1.0, 0.6]`（**不重归一**）；`gated.iloc[1,0] == 0.6` | A6 落码 | `::test_v4_apply_timing_gate` | ✅ PASS |
| B5 | V5 固定止损：建仓 state 四字段精确相等；gap（open 89）→ `stop_loss`；盘中（low 89）→ `stop_loss`；未触发 → `hold` 且 `bar_count==2` / `peak_price==101.0` | A8/A10 落码 | `::test_v5_fixed_stop_loss` | ✅ PASS |
| B6 | V6 移动止损与优先级：激活后 d2/d3 hold、d4 low 47 → `trailing_stop`；`activate=0.5` 未激活 → hold（d2 low 47 亦不触发）；SL 与 TP 同日 → **`stop_loss`**；纯 TP（high 125）→ `take_profit` | A10 落码 | `::test_v6_trailing_and_take_profit_priority` | ✅ PASS |
| B7 | V7 时间止损与延迟：weights X `[0.5,0.0,0.5,0.0]`、Y `[0.5,0.5,0.0,0.5]`；`deferred == 1`（Y 跌停延迟）；3 条 trigger 全 `time_stop` | A12 落码 | `::test_v7_time_stop_and_deferred_exit` | ✅ PASS |
| B8 | V8 端到端：`len(triggers)==1`（A `stop_loss`，entry 100 / ref 90）；weights 01-04 A=0.0、01-05 A=0.5（重建）；`StopState.from_dict(payload).to_dict()==payload`；行和只减不增；三类 fail-fast 逐案 + `StopConfig` 两条 raises | A12 落码 | `::test_v8_apply_stops_end_to_end` | ✅ PASS |
| B9 | **G1** `P045_S1` 规格锁定：weights 5×3 逐值、triggers 3 条（C 01-03 / A 01-04 / B 01-05）、deferred 0、states 末日三标的 | A12 + golden JSON | `::test_golden_p045_s1` | ✅ PASS |
| B10 | **G2** `P045_S2` 规格锁定：weights 5×2 逐值、triggers 4 条、deferred **1**、states 仅 X | A12 + golden JSON | `::test_golden_p045_s2` | ✅ PASS |
| B11 | 红态留证：IMPL §4.5 预测 **`10 failed` / 0 passed**（`ModuleNotFoundError: core.timing` / `core.stops`） | 新测试已写、实现未落 | pytest 输出逐字 | ✅ 实测 **`10 failed in 0.75s`**（0 passed；全 `ModuleNotFoundError`） |
| B12 | 绿态：本文件 **10 passed**（V1-V8 + G1/G2） | A1-A12 落码 | pytest 指定文件 | ✅ `10 passed in 0.58s`（black 重排后复跑仍 10） |
| B13 | 既有测试零订正且全绿：`test_golden_baseline.py`（既有 13 case 全绿）、`test_p044_strategy_interface.py`（8）、`test_engine_plugins.py`、`test_manifest.py` | A1-A12 落码 | pytest 指定文件 | ✅ **32 passed**（四文件零订正） |
| B14 | golden JSON 独立 schema：两份文件含 `schema_version`/`case_id`/`git_commit`/`kind`/`config`/`targets`/`bars`/`tradable`/`expected`/`tolerance`；P-013 harness（`_golden_cases.py` / `test_golden_baseline.py` / `G*.json`）**零 diff**；装饰字段不参与断言（F-S6-P045-3 观察） | B9/B10 前置 | 读文件 + `git status` | ✅ 两份 JSON 在 `tests/golden/p045/`（**目录订正 F-S9-P045-1**）；`G*.json` / harness 零 diff |

## 3. C 组：不变式（DESIGN I1-I9 + 既有语义，10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | **I1** 默认路径零行为：既有 golden **13 零重录**；`agents/` / `core/engine_v2.py` / `core/strategy.py` / `core/risk_manager.py` / `core/config.py` **零 diff** | 全量实现 | `pytest -k golden` + `git status` | ✅ 既有 13 零重录（15−2）；受保护面 `git status` 空 |
| C2 | **I2** 纯函数：见 A13（grep = 0 + 无模块级副作用） | A1-A12 落码 | grep | ✅ 见 A13（grep = 0） |
| C3 | **I3** 对拍：`verify_p045` 触发判定序列与 vectorbt 1.2.0 逐值一致；成交/NAV 差异 waiver 闭式声明（不静默缩窄） | A14 落码 | D7 | ✅ verify_p045 exit **0**（C3 排序规范化后 7 断言 0 失败 + 4 waiver） |
| C4 | **I4** 确定性：G1/G2 规格锁定；同输入重跑逐值相同（V5-V8 无随机源） | A10/A12 落码 | B9/B10 + 重跑 | ✅ G1/G2 PASS；两轮 10 passed 逐值相同 |
| C5 | **I5** 无前视：T 日仅用 ≤T bar；触发日在 `targets[T]` 行置 0（该行目标经 T+1 执行链成交，无前视）；`exit_price_ref = bar.close` 仅审计参考，不用于成交 | A12 落码 | 读码 + B8 | ✅ stops.py L230-245 读码 + V8（01-04 归零 / 01-05 重建 0.5） |
| C6 | **I6** 可成交性：`tradable=False` → 退出延迟 + `deferred` 计数（V7）；负权重/行和 >1 由 P-044 `set_signal` 兜底（本批不接线） | A12 落码 | V7 + 读码 | ✅ V7（`deferred == 1`）+ 读码 |
| C7 | **I7** 零新增依赖：`pyproject.toml` / `uv.lock` **零 diff**；`vectorbt` 仅隔离 venv | A14 前置 | `git diff` + D6 | ✅ `pyproject.toml` / `uv.lock` 零 diff；vbt 仅 `.venv-vbt` |
| C8 | **I8** 状态可序列化：`StopState` JSON 往返相等（V8）；`StopResult.states` 为 JSON 安全 dict | A8 落码 | V8 | ✅ V8 `from_dict(to_dict) == payload` |
| C9 | **I9** 状态清理：目标权重归 0（策略主动清仓）→ state 删除；再入场重建（V8 01-04→01-05） | A12 落码 | V8 | ✅ V8（01-04 A=0.0 → 01-05 A=0.5） |
| C10 | 既有语义零变更：`core/target_positions.py` / `core/execution_policy.py` / `core/engine_v3_vector.py`（**F-S8-P045-4 补**，RESEARCH I1 原列）/ `filter/` / `tests/_golden_cases.py` / `tests/test_golden_baseline.py` / `tests/golden/G*.json` **零 diff**；生产 diff 仅新增两个模块 + 对拍脚本 | 全量实现 | `git diff --stat` | ✅ 受保护面 `git status` 全空；生产 diff = 2 新模块 + 1 对拍脚本 |

## 4. D 组：门禁、提交与文档（9 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | pytest **821 passed**（811 + 10） | 全量实现 | 全量末行 | ✅ `821 passed, 184 warnings in 57.55s` |
| D2 | golden **`15 passed, 806 deselected`**（821 − 15）；`git status --short tests/golden/` 仅含两个新文件、既有 13 零改动 | 全量实现 | 命令 + git | ✅ `15 passed, 806 deselected`；`?? tests/golden/p045/` |
| D3 | black `core tests` **135** / 全仓 **203**（+2 源 +1 测试 +1 对拍脚本）；`tests/*.py` **94** | 新文件落盘 | `black --check` 双口径 + 计数 | ✅ **135** · **203**；`tests/*.py` **94**（F-S9-P045-5 订正）|
| D4 | mypy **108 source files 0**（+`core/timing.py` + `core/stops.py` + `scripts/external_benchmark/verify_p045.py`；命令含 `scripts/`、不含 `tests/`；F-S10-P045-1 订正） | 全量实现 | CI 逐字命令 | ✅ `Success: no issues found in 108 source files`（Step 10 复跑） |
| D5 | AST `except Exception` **22（不变）**；新增 `# type: ignore` = **0**（两模块无 try/except） | A1-A12 落码 | P-029 单行命令 + grep | ✅ AST **22**；新增 `# type: ignore` **0** |
| D6 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零 diff | 全量实现 | 命令 + `git diff` | ✅ exit **0**（Resolved 148 packages）；两文件零 diff |
| D7 | `verify_p045` exit **0**：触发序列逐值断言全过；waiver 条目显式列出（激活阈值 / 成交价 / NAV）；附录已记录读数（E2） | A14 + B9 | 隔离 venv 运行 + 附录 | ✅ exit **0**（7 断言 + 4 waiver；附录已落盘） |
| D8 | 提交原子（2 新源 + 1 新测试 + 2 golden JSON + 1 对拍脚本 + 5 新文档：RESEARCH/DESIGN/IMPL/CHECKLIST/**APPENDIX** + 3 已跟踪订正：PROGRESS/CHANGELOG/DESIGN_p044，共 **14 文件**；F-S10-P045-5 订正）+ CI 四 job 全绿 | D1-D7 通过 | `git show --stat` + `gh run view` | [待 Step 10] |
| D9 | 文档回填：IMPL §10（落码/红绿/门禁/发现）/ PROGRESS 对应小节 / CHANGELOG / 本文件 **47/47** | D8 通过 | 读回 | [待 Step 10] |

---

## 5. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **47**（A 14 + B 14 + C 10 + D 9 = 47，逐表行数机械计数；B11-B14 为取证/结构项非新用例） |
| 实测列回填 | **45/47**（45 × `✅ + 证据`；D8/D9 待 Step 10） |
| 新用例数 | **10** = V1-V8（8 函数）+ G1/G2（2 函数） |

> **RULE-2 统计溯源**：47 = 14 + 14 + 10 + 9（逐表行数）；821 = 811 + 10（B1-B10）；15 = 13 + 2（B9/B10）；135/203 = 132/199 + 2 源 + 1 测试 + 1 对拍脚本；108 = 105 + 2 源（A1/A7 所在模块）+ 1 对拍脚本（F-S10-P045-1 订正）；94 = 93 + 1（B1-B14 同一文件）。
> **RULE-5 声明（S8 订正，F-S8-P045-9）**：Step 1-7 四文档作者同源（DeepSeek-V4.1-Flash）；Step 2 / Step 4 / Step 6 复审**异构成立**（GLM-5.3-Flash，RESEARCH §13 / DESIGN §10 / IMPL §9）；Step 8 异构成立（GLM-5.3-Flash，本文件 §7）；Step 10 异构终审 GLM-5.3-Flash（**已闭合**，U-P045-5 → 本文件 §8）。

---

## 6. Step 7 → Step 8 交接

1. **核红态口径**：IMPL §4.5 预测 `10 failed / 0 passed`；Step 9 实测若偏离（如收集期 error），以实测回填 B11 与 IMPL §10，并排查是否引入 `conftest` 级导入。
2. **核计数链**：811 + 10 = **821**；13 + 2 = **15**；132 + 2 源 + 1 测试 = **135**；199 + 4 = **203**；93 + 1 = **94**；mypy 105 + 2 源 + 1 对拍脚本 = **108**（F-S10-P045-1 订正）；AST **22 不变**（两模块无 try/except）。
3. **核零预填**：Step 9 前 `[待 Step 9]` 须为 **45**、`[待 Step 10]` 须为 **2**；任何 `✅` 出现即为违规。（**Step 9 后实测**：45 项已回填 `✅`，余 D8/D9 待 Step 10。）
4. **核 ID 不混用**：DESIGN 决策 `D1-D9` vs 本文件 **D 组**；用例 `V1-V8` / golden `G1/G2`（勿与 P-013 的 `G1-G7` 混淆，二者 schema 隔离）；发现 `F-S{2,4,6,8,10}-P045-*`；引用一律 `DESIGN-D*`。
5. **核 golden 方法论**：G1/G2 为**规格锁定**（期望手工推导），若 Step 9 实现与期望不符 → **先审规格**（DESIGN R6），禁止改期望迁就实现；`git status tests/golden/` 只允许出现 `P045_S1.json` / `P045_S2.json` 两个新文件。
6. **核对拍边界**：I3 已收窄为**触发判定序列**（F-S2-P045-1）；`trailing_activate_pct` 不在对拍范围（F-D3-P045-4）；成交价/NAV 差异必须 waiver 显式，不得静默缩窄断言。
7. **核不做清单**：不做空（P-050）/ 不 sizing 与再归一（P-047）/ 不接引擎与风险动作闭环（P-048）/ 不做盘中 bar 与部分退出。

---

## 7. Step 8 一致性 Review 记录（异构 GLM-5.3-Flash，2026-11-18）

> **基座披露（RULE-4/RULE-5）**: 复审 **GLM-5.3-Flash** ≠ 四文档作者 DeepSeek-V4.1-Flash → **异构成立**（Step 2/4/6/8 连续四轮；U-P045-5 维持至 Step 10 终审）。
> **取证方式**: E3 机械复核（清单行数逐表点数 / 计数链五文档交叉 / ID 闭环 grep / 对齐矩阵逐行 / golden 期望抽检）；零代码执行。

### 7.1 机械五项

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 清单总数 | 47 = A 14 + B 14 + C 10 + D 9（逐表行数）；实测列 45 × `[待 Step 9]` + 2 × `[待 Step 10]`（D8/D9）（Step 8 时点读数；Step 9 后 45 项已回填，见头部状态） | ✅ 零预填保持 |
| 2 | 计数链五文档一致 | RESEARCH §8 I8（订正注终值）/ DESIGN §6（本轮补对拍行，F-S8-P045-8）/ IMPL §7 / 本文件头部·D 组 / PROGRESS §3.51.5·§3.51.7 均为 **821 / 15 / 135·203 / 107 / 22 / 94 / uv 0**（Step 9 实测订正，F-S9-P045-5）；对拍行 IMPL §7 ↔ D7 ↔ DESIGN §6（补后）一致 | ✅（订正后） |
| 3 | 用例数与函数数 | **10 函数** = V1-V8 + G1/G2（DESIGN §5 表 10 行 / IMPL §4.2 八函数 + §4.3 两函数 / 本文件 B1-B10）；811+10=**821**；15 = 13（9+4 构成实证）+2；deselected **806** = 821−15；红态 **10 failed** 三文档一致（DESIGN §5 / IMPL §4.5 / B11） | ✅ |
| 4 | ID 链 | F-S2-P045-1..6（RESEARCH §13.2）/ F-D3-P045-1..6（DESIGN §9）/ F-S4-P045-1..8（DESIGN §10 注）/ F-S6-P045-1..3（IMPL §9.2）引用闭环；本文件引用的全部 F-ID 可解析（B2 悬空 `F-S9` 已订正，F-S8-P045-10）；U-P045-1..4 已裁决（DESIGN §2.0）、U-P045-5→Step 10；DESIGN-D1..D9 与本文件 D 组无混用（A1/A4 裸引用已订正） | ✅（订正后） |
| 5 | 基座链 | Step 1-7 作者同源 DeepSeek；Step 2/4/6 复审异构 GLM（RESEARCH §13 / DESIGN §10 / IMPL §9）；Step 8 异构 GLM（本轮）；Step 10 终审 GLM（U-P045-5） | ✅（本文件 §5 声明已订正，F-S8-P045-9） |

### 7.2 对齐矩阵（RESEARCH S/I/G ↔ DESIGN ↔ IMPL ↔ CHECKLIST）

| RESEARCH | DESIGN | IMPL | CHECKLIST | 判定 |
|----------|--------|------|-----------|------|
| S1 SignalSet | D2 | §3.1 | A2 | ✅ |
| S2 交叉/NaN | D3 | §3.1 | A1/B1 | ✅ |
| S3 exit 优先 | D4 | §3.1 | A3/B2 | ✅ |
| S4 等权不重归一 | D4 | §3.1 | A5/B3、A6/B4 | ✅ |
| S5 StopConfig 正数 | D5 | §3.2 | A7/V8 | ✅ |
| S6 StopState 往返 | D5 | §3.2 | A8/V8/C8 | ✅ |
| S7 StopDecision | D5 | §3.2 | A9 | ✅ |
| S8 bar 内顺序/成交口径 | D6 | §3.2 | A10/V5/V6/C5 | ✅（F-S8-P045-6 措辞订正后） |
| S9 状态更新/清理 | D6/D7 | §3.2 | A12/V8/C9 | ✅ |
| S10 组合器 | **D1 推翻 → 矩阵级** | §3.1/§3.2 | A6/A12/A14 | ✅（F-S8-P045-1 补注后） |
| I1 零行为 | I1 | §1 | C1/C10 | ✅（F-S8-P045-4 补 engine_v3_vector 后） |
| I2 纯函数 | I2 | §3 | A13/C2 | ✅ |
| I3 对拍口径 | I3 | §4.6 | C3/D7/A14 | ✅（F-S8-P045-2 收窄订正后） |
| I4 确定性 | I4 | §4.4 | C4/B9/B10 | ✅ |
| I5 无前视 | I5/D6 | §3.2 | C5 | ✅ |
| I6 可成交性 | I6/D7 | §3.2 | C6/V7 | ✅ |
| I7 零依赖 | I7 | §6 | C7/D6 | ✅ |
| I8 JSON 往返 | I8 | §3.2 | C8/V8 | ✅（编号移位注见下） |
| I9 状态清理 | I9 | §3.2 | C9/V8 | ✅ |
| G1-G9 缺口 | D1-D9 关闭 | §2/§3 | A 组/C 组 | ✅（G8→A14/D7/C3；G9→D7/A12；G6 显式延后 P-048） |

> **编号移位注**：RESEARCH I8（计数链）在 DESIGN 重排为 §6 计数链表，I8/I9 语义顺延（I8=JSON 往返、I9=状态清理）；本文件 C 组以 DESIGN 编号为准，无混用（RESEARCH I8 自带「终值以 DESIGN §6 为准」订正注）。

### 7.3 发现与当轮处置（10 P3，全部当轮回写；0 P1/P2）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P045-1 | P3 | RESEARCH §5 M-A 与 §7 S10 的 `TimingStrategy`/`StopsStrategy` wrapper 描述未标注被 D1 推翻为矩阵级叠加（§6 已有 F-S4-P045-6 同类订正注，§5/§7 缺） | RESEARCH §5 裁决段 + S10 补注 |
| F-S8-P045-2 | P3 | 对拍对象三文档漂移：RESEARCH I3「信号交叉与止损触发」/ DESIGN I3「交叉检测触发序列」/ IMPL §4.6 实际仅对拍**止损触发判定序列**（vbt 免费版无交叉原语可比；交叉检测由 S2 语义 + V1 锁定） | DESIGN I3 措辞订正 + RESEARCH I3 补收窄注 |
| F-S8-P045-3 | P3 | RESEARCH §10 对拍命令引用 P-015 `audit_signatures.py`，本批载体已裁决 `verify_p045.py`（F-S6-P045-1） | RESEARCH §10 补注 |
| F-S8-P045-4 | P3 | RESEARCH I1 显式要求 `core/engine_v3_vector.py` 零 diff，但 DESIGN I1 与本文件 C1/C10 均未列入 | DESIGN I1 补 + 本文件 C10 补 |
| F-S8-P045-5 | P3 | DESIGN §3.1 第三条 bullet 仍为位置参数 reindex + `fillna(False)` 旧口径，与同节 F-S4-P045-1 订正后的签名块及 IMPL §3.1（`_as_bool` + keyword）不一致 | DESIGN §3.1 bullet 订正 |
| F-S8-P045-6 | P3 | DESIGN D6 口径声明「次日生效的目标权重」、§4 边界 1「归零次日权重」、I5「只改次日权重」措辞歧义——golden S1 锁定的是**触发日 T 行**归 0（T+1 行为重建值非 0） | DESIGN D6/§4 边界 1/I5 三处措辞订正（与本文件 C5 口径一致） |
| F-S8-P045-7 | P3 | DESIGN §5 夹具声明含 `_synth_fixture.write_price_fixture`，IMPL §4.1/§5-5 已裁决**纯内联小矩阵**（不引入夹具） | DESIGN §5 补订正注（IMPL 为准） |
| F-S8-P045-8 | P3 | DESIGN §6 计数链缺对拍行（IMPL §7 / 本文件 D7 均含 verify_p045 exit 0） | DESIGN §6 补行 |
| F-S8-P045-9 | P3 | 本文件 §5 RULE-5 声明「Step 1-2 同源」与 RESEARCH §13/IMPL §9 基座链矛盾（P-045 Step 2 复审已异构成立，F-S2-P045-6①） | §5 声明订正 |
| F-S8-P045-10 | P3 | 本文件两条自身违规：A1/A4 裸 `（D3）/（D4）` 引用违反 §6-4「引用一律 DESIGN-D*」；B2 引用「F-S9 同类订正」为悬空 ID（P-045 无 F-S9；V2 构造期订正发生于 Step 6 复核编辑） | A1/A4 改 `DESIGN-D3/DESIGN-D4`；B2 改「Step 6 复核订正」；§6-4 发现枚举补 S8 |

### 7.4 结论

- **判档**: 10 P3 全部当轮回写，0 P1/P2，无未决阻塞。
- **结论**: **pass** —— 准予进入 Step 9 TDD（红态预测 10 failed / 0 passed → 绿态 10 passed + 八门禁 + verify_p045）。
- U-P045-5（异构链）维持至 Step 10 终审。

---

## 8. Step 10 ADD 审计与异构终审（2026-11-18）

> **终审基座**: GLM-5.3-Flash ≠ Step 9 实施（DeepSeek-V4.1-Flash）→ **异构成立**；U-P045-5 五轮异构链（Step 2/4/6/8/10）于本轮闭合。
> **取证**: E1 门禁八项独立复跑（逐字命令）+ E2 独立探针 **31+1 断言**（非测试套件，含对抗场景与套件未覆盖增量）+ E3 静态读码 @未提交工作区（HEAD `0482881` + diff）+ E4 盲区扫描 14 项 + E5。
> **探针留痕（RULE-6）**: 探针开发期 5 处期望错误（等值 11<11 / ffill 延续 / 冲突对照 / DataFrame 行列映射 / gate 后 weights≠targets）全部以**实测反证后修正探针自身**，代码零改动、零迁就（探针第 5 版起 31 断言全过）。

### 8.1 E1 门禁独立复跑（八项，逐字命令）

| # | 门禁 | 目标 | 实测 | 判定 |
|---|------|------|------|------|
| 1 | pytest 全量 | 821 passed | `821 passed in 56.49s` | ✅ |
| 2 | golden 子集 | 15 passed, 806 deselected | `15 passed, 806 deselected` | ✅（既有 13 零重录） |
| 3 | black `core tests` / 全仓 | 135 / 203 | **135** / **203** | ✅ |
| 4 | mypy 逐字命令 | 108 files 0（F-S10-P045-1 订正后） | `Success: no issues found in 108 source files` | ✅（读数漂移 → F-S10-P045-1） |
| 5 | AST `except Exception`（core 外） | 22 不变 | agents 11 / filter 5 / scripts 2（verify_p045 **零命中**）/ batch_backtest 2 / strategy_evaluation 1 / cli 1 = **22** | ✅ |
| 6 | `tests/*.py` 计数 | 94 | **94** | ✅ |
| 7 | `uv lock --check` | exit 0 | exit **0** | ✅ |
| 8 | `verify_p045`（隔离 venv） | exit 0 | exit **0**（7 断言 0 失败 + 4 waiver） | ✅ |

### 8.2 E2 独立探针（31+1 断言全过；套件未覆盖增量 8 组）

| 组 | 增量场景 | 判定 |
|----|----------|------|
| G1 | crossed_below 对偶 + 等值零交叉 + NaN 阻断（3 断言） | ✅ |
| G2 | SignalSet **columns** 校验构造期触发（套件 V2 仅 index 口径） | ✅ |
| G3 | short 侧类型位：resolve_conflicts 透传不读取 / holdings 忽略 / 同日冲突 exit 优先（A 抵消 + B 无冲突正常开仓对照，4 断言） | ✅ |
| G4 | weights 空持仓行全 0 且无 NaN（`counts.replace(0.0, nan)` 路径） | ✅ |
| G5 | apply_timing **乱序网格** reindex keyword 对齐 + gate 归 0 不重归一（四单元格读数） | ✅ |
| G6 | StopConfig 四百分比字段逐个 `=0` 拒绝 + `time_stop_days=0` 拒绝 + `=1` 合法边界（6 断言） | ✅ |
| G7 | StopEngine：建仓日免疫（bar 跌破 SL 不触发）/ **同 bar「激活即触发」**（activate=0.15）/ 未激活低穿透对抗（activate=0.5, low 47）/ time_stop `count>=limit`（4 断言） | ✅ |
| G8 | apply_stops：hold&weight≤0 删状态 + 再入场重建（entry=新 close, count 重置）/ 三类 fail-fast 逐案 / **不可交易延迟全链路**（d2 跌停 deferred → d3 实际退出归 0 + state 删除 + 单 trigger）/ tradable=None 对照组 / StopTrigger 全字段 / 容器形态 / StopDecision 默认 / JSON 往返 / 确定性双跑（10 断言） | ✅ |
| G9 | `ohlc_from_data` stub dm 四键 raw 透传（**套件零覆盖项**） | ✅ |
| 补 | `trailing_activate_pct=None` 立即激活路径（套件与 golden 均未覆盖；stops.py L154-155 `is None or` 短路；low 91 ≤ peak 100.6×0.92=92.55 → trailing_stop） | ✅（F-S10-P045-3） |

### 8.3 ADD 四阶段判定

| 阶段 | 范围 | 方法与证据 | 判定 |
|------|------|-----------|------|
| Phase 0 规格质量 | DESIGN D1-D9 / §4 七边界 | E3 抽检：阈值/签名/语义均可机械核对，无「合理处理」类模糊词 | ✅ 净 |
| Phase 1 完整性 | DESIGN→IMPL→落码 | E1 计数链复跑 + E3 全符号读码（timing 7 符号 / stops 9 符号全落地；D1-D9 ↔ A1-A14 / I1-I9 ↔ C1-C10 全映射） | ✅ |
| Phase 2 忠实度 | IMPL↔落码↔测试 | timing.py ↔ IMPL §3.1 逐字一致；stops.py 差异仅 F-S8-P045-6 docstring 订正 + black style-only；测试 V1-V8+G1/G2 ↔ §4 逐函数对齐；GOLDEN_DIR=`golden/p045`（F-S9-P045-1） | ✅ |
| Phase 3 必要性 | 落码↔设计依据 | 变更面 3 M + 9 新全映射 IMPL §2 B1-B3；core 外消费方 grep = 仅 `tests/test_p045_timing_stops.py`（零生产接线 = P-048 显式边界）；`pyproject.toml`/`uv.lock` 零 diff | ✅ |
| Phase 4 语义意图 | 代码 vs 意图 | 触发≠成交无前视（探针 G8 延迟链路 + golden S1 触发日 T 行归 0）；止损触发序列与 vbt 一致（C3 对拍）；I1-I9 全过 | ✅ |

### 8.4 发现与当轮处置（3 P3 订正 + 2 观察；0 P1/P2）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S10-P045-1 | P3 | mypy 文件数读数漂移：Step 9 各文档记 **107**，E1 逐字命令复跑实测 **108**。根因：Step 9 门禁运行时点早于 verify_p045.py 落盘（TDD 顺序：⑤ 八门禁 → ⑥ 对拍脚本），mypy 命令含 `scripts/`；105 + 2 源 + 1 对拍脚本 = 108。0 issues 不变（门禁仍绿） | 五处终态声称值订正 107→108：本文件头部 / D4 / §5 RULE-2 / §6-2 / IMPL §7 与 §10 订正注 / DESIGN §6 与 §10.3 订正注 / PROGRESS §3.51.10 |
| F-S10-P045-2 | P3 | CHECKLIST 行号证据漂移：A1-A12 + C5 共 **13 处**为 black 重排前时点（= IMPL §3 规格块行号），与当前文件偏移（stops.py −12 尾差；timing.py 尾部 3 项偏移至错误区间）。教训：行号证据须绑定 commit hash（E3 属性） | 13 处按当前文件订正：A1 L16-28 / A2 L31-48 / A3 L51-65 / A4 L68-75 / A5 L78-85 / A6 L88-95 / A7 L20-44 / A8 L47-82 / A9 L85-113 / A10 L122-168 / A11 L171-173 / A12 L175-263 / C5 L230-245（@未提交工作区；提交后随 hash 稳定） |
| F-S10-P045-5 | P3 | D8 提交原子清单不完整：漏 **APPENDIX**（A14/C3 引用的新文档）与 **DESIGN_p044** 已跟踪订正（P-044 §8 接口修正回写）；实际提交 = **14 文件**（2 新源 + 1 新测试 + 2 golden JSON + 1 对拍脚本 + 5 新文档 + 3 已跟踪订正） | D8 DoD 订正（本文件） |
| F-S10-P045-3 | P3 观察 | `trailing_activate_pct=None`（立即激活）路径套件 V1-V8 与 golden G1/G2 均未覆盖（V6 用 0.05/0.5；G1 B case 用 0.05） | 补探针验证 PASS（§8.2 补行）；不阻断，P-048 接线触及止损配置时再补套件 case |
| F-S10-P045-4 | P3 观察 | 语义边角：触发日目标权重恰为 0 时 exit 分支仍记录 trigger（`weights.at=0` 无操作）。可达性：state 存在要求此前日 weight>0（hold 分支保留），同日目标归 0 + 止损触发同刻即出现；后果仅冗余审计记录，weights 输出正确且 DESIGN-D7 规格未以 weight>0 为 exit 前置 | 登记不阻断；若 P-048 接线后 trigger 归因需排除「策略已清仓」场景再评估 |

### 8.5 E4 盲区扫描（14 项，挑刺视角）

| # | 盲区 | 检查与证据 | 判定 |
|---|------|-----------|------|
| 1 | 接线缺口 | core 外消费方 grep `core.timing|core.stops` = 仅测试文件；零生产接线 = P-048 显式边界（DESIGN §1 不做清单） | ✅ 闭式声明 |
| 2 | G9 OHLC 载体 | StopBar 显式载体 + `MarketView` 零 diff；`ohlc_from_data` 仅封装入口（探针 G9） | ✅ |
| 3 | short 侧（P-050） | `entries_short/exits_short` 消费面 = 定义 L41-42 + resolve_conflicts 透传 L63-64，全流程不读取（探针 G3） | ✅ U-P045-1 闭式 |
| 4 | Strategy wrapper 缺失 | D1 裁决矩阵级叠加（F-D3-P045-1）；`core/strategy.py` 零 diff；P-044 §8 接口修正已回写（DESIGN_p044 3 M 之一） | ✅ |
| 5 | 前视 | 触发日 T 行归 0（L233）+ 成交 T+1 开盘链路（设计语义）；`exit_price_ref=bar.close` 仅审计（探针 G8） | ✅ |
| 6 | 禁同日重建 | exit 分支 `continue`（L245）先于建仓分支；探针 G8 d3 退出后无同日重建（states 空） | ✅ |
| 7 | deferred 状态推进 | 延迟日 state 保留且 bar_count 递增（F-S4-P045-8）；探针 G8 全链路 | ✅ |
| 8 | trailing None 激活 | 套件未覆盖 → 补探针 PASS（F-S10-P045-3） | ✅ 补验 |
| 9 | trailing 同 bar 激活即触发 | 探针 G7（更新后峰值） | ✅ |
| 10 | bars 网格 NaN | fail-fast 在 reindex 后按 targets 网格检查（L192-197）；探针 G8 逐案 | ✅ |
| 11 | `_BAR_KEYS` 顺序一致性 | ohlc_from_data 输出与 apply_stops 解包同用常量（L210） | ✅ |
| 12 | golden harness 兼容 | P-013 harness 零 diff（C10）；golden 15 passed 含两新 case（E1-2） | ✅ |
| 13 | trigger-on-zero-target 边角 | F-S10-P045-4（可达、无害、规格符合） | ✅ 登记 |
| 14 | 提交面完整性 | D8 清单漏 APPENDIX/DESIGN_p044 → F-S10-P045-5 订正；实际 14 文件 | ✅ 订正后闭式 |

### 8.6 结论

- **判档**: 0 P1 / 0 P2 / **3 P3**（F-S10-P045-1/2/5 全部当轮订正完毕）+ **2 观察**（F-S10-P045-3/4，登记不阻断）。
- **结论**: **pass** —— ADD 四阶段 + E4 盲区扫描通过；准予提交（待用户授权）；U-P045-5 异构链五轮闭合。
- **遗留**: D8/D9 于提交授权后回填（commit hash + CI run 绑定；本文件行号证据随提交稳定）。
