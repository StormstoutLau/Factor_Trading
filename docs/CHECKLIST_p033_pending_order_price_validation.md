# CHECKLIST：P-033 待执行订单价格有效性（守卫单点 + VWAP 覆盖）

> **批次**: P-033 · **T1**（`core/execution.py` + `core/engine_v2.py` + `agents/multi_strategy_engine.py` + 新增账目测试）
> **上游**: [IMPL_p033](IMPL_p033_pending_order_price_validation.md)（B1-B4 / §4 精确锚点 / §5 V1-V8 十七实例 / §6 fixture / §7 八项低效排除 / §8 回退点 / §12 Step 5 自检 / §13 Step 6 复审 pass）；[DESIGN_p033](DESIGN_p033_pending_order_price_validation.md)（D1-D6 / I1-I7 / V1-V8 / §12 Step 4 复审）；[RESEARCH_p033](RESEARCH_p033_pending_order_price_validation.md)（§3 R1-R3 / §6 调用点全表 / §7 M-A / §11 Step 2 复审）
> **状态**: **Step 7 CHECKLIST 编制完成**（2026-11-17，待 Step 8 一致性 Review，须由异构基座 GLM-5.3-Flash 执行）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**禁止与正文同一次写入时打勾**
> **基线读数（Step 7 实测 @HEAD `204b15f`，Python312 + `MPLBACKEND=Agg`）**: 全量 `pytest -q` **731 passed**（Step 6 E2 实测 @`b837d5f`；Step 7 子集对拍 `57 passed + 674 deselected = 731` 一致）/ `tests/` .py **82** / `black --check core tests` **119 unchanged**（§13.3）/ `mypy --explicit-package-bases core` **37 files 0 error**（§13.3）/ `tests/golden/` **7** 份 json（13 条 golden 用例）/ `except Exception`（P-029 十文件口径）**22** / 回归子集 `-k "golden or p027 or p029 or p031"` **57 passed, 674 deselected**
> **目标读数（Step 9）**: **748 passed** / 测试文件 **83** / black **120** / mypy **37 files 0** / golden **13 零重录** / `except Exception` 恒 **22**
> **代码证据时点**: 实施前 HEAD `204b15f`（与 IMPL §4 锚点基准 `013c4d3` 代码面一致，仅 docs 变更）；Step 9 后按 F-I 惯例登记行号漂移
> **缺陷对象**: queue 主路径（agents L520 / V2 L815）仅做成员检查，`NaN`/`±inf`/`≤0` 开盘价透传 `execute_order` 入账 → cash 永久 NaN（R1 **P1**）/ 免费持仓与幻影现金（R2 **P2**）；根因收敛为「执行价格无有效性契约」

---

## 1. A 组：B1 `is_valid_price` + 解析价守卫（D1 → 测试 V1 / V7）

> **DoR**: `execute_order` 的 `try` 结构（L290 / `except` L339）与 `_get_execution_price` 五分支（L191-260）已在 Step 6 E1 冻结；`np` 已导入（L16）；`TradeLog` 类占 L52-150，`ExecutionSimulator` 起 L153。**DoD**: 五分支解析价在一处汇聚判定，无效价零入账零异常，合法价路径逐字不变。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | 新增模块级函数 `is_valid_price(price: Optional[float]) -> bool`，位于 `TradeLog` 类结束（L150）与 `ExecutionSimulator`（L153）之间；实现为 `None → False` + `bool(np.isfinite(price) and price > 0)`；纯函数（零日志 / 零异常 / 零 IO）；复用 L16 `np` 导入，不新增依赖 | 读码插入位置；`Select-String "def is_valid_price" core/execution.py` = **1** 命中 | DESIGN-D1 / IMPL §4.1 / F-I-P033-1 | [待 Step 9] |
| A2 | 守卫块位置：`execution_price = self._get_execution_price(...)`（L292-294）**之后**、`# 价格合理性检查`（L296）**之前**；仍在 `try:`（L290）内；形态为注释 + `if not is_valid_price(execution_price):` + 两段 warning + `return False, None` | 读码行序（守卫行号 ∈ (294, 296)）；`git diff core/execution.py` 该块全为 `+` 行 | DESIGN-D1 / IMPL §4.2 / §13.5-#1 | [待 Step 9] |
| A3 | 拒绝语义：warning 文案含「执行价格无效」与「P-033 价格守卫」；`return False, None` **早于** L307 `amount = quantity * execution_price` 与 L330 `add_trade` → 零 `trade_log` 入账；**零新增 `except`**（守卫为前置 `if`，不进异常漏斗） | 读码前置顺序；V1 断言 `get_trades() == []`；AST 命令 = **22** | DESIGN-D1 / I1 / I5 | [待 Step 9] |
| A4 | **零改动留证**（D3）：`_get_execution_price` **L191-260** 五分支（OPEN / CLOSE / VWAP / CUSTOM / 未知回退）逐字保留；agents next-day **L451**、V2 next-day **L1140**、V2 强平 **L563** 三处 inline 判定在位；`core/tracker.py` / `core/pending.py` / `core/interfaces.py` 零改动 | `git diff` 无 `_get_execution_price` hunk；三处 inline 判定读码在位；`git status --short core/tracker.py core/pending.py core/interfaces.py` 空 | DESIGN-D3 / IMPL §4.5 / O-D-P033-1 | [待 Step 9] |
| A5 | docstring 契约句：`Returns:`（L287-289）段后补「若解析后的执行价格为 None / NaN / ±inf / <=0，返回 (False, None)，不写入 trade_log」；`execute_order` 签名零变更 | 读码 docstring；`git diff \| Select-String '^[-+]\s*def execute_order'` = **0** | IMPL §4.2 / §8 A8 | [待 Step 9] |
| A6 | V1 绿：`open_price ∈ {None, NaN, inf, -inf, 0.0, -5.0}` 六参数全 `(False, None)`、`trade_log.get_trades() == []`、无异常抛出；**红态预期 5F/1P**（`None` 入参经既有 TypeError 漏斗 L339 已返回 False，豁免须标注） | `pytest -q -k "v1_price_guard_matrix"` = **6 passed** | V1 / I1 / F-S6-P033-1 | [待 Step 9] |
| A7 | V7 绿：`ExecutionPriceType.VWAP` + open/close = 10 合法、high/low/volume = NaN → `(False, None)`、`trade_log` 空（VWAP 聚合 NaN 第二入口已封） | `pytest -q -k "v7_vwap_nan"` = **1 passed** | V7 / I1 / F-S2-P033-2 | [待 Step 9] |

---

## 2. B 组：B2 agents queue 前置过滤（D2 → 测试 V2-V5 / V8a）

> **DoR**: `_process_pending_orders` 内成员检查（L505-506）→ 取价（L508-509）→ 夹紧（L511-519）→ `execute_order`（L520）→ `mark_expired`（L528）顺序已在 P-031 冻结；`_record_failure`（L126）可承接任意键。**DoD**: 无效开盘价订单零成交、零入账、留队重试，且拒绝次数可归因。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | 导入 L32 改为 `from core.execution import ExecutionSimulator, is_valid_price`；模块可正常导入（无循环依赖） | 读码 L32；`python -c "import agents.multi_strategy_engine"` 退出码 0 | DESIGN-D2 / IMPL §4.3① | [待 Step 9] |
| B2 | 过滤块位置：L509（`close_price` 赋值）**之后**、L511（夹紧注释）**之前**；三行形态 `if not is_valid_price(open_price):` / `self._record_failure("pending_invalid_price")` / `continue` | 读码行序（过滤块行号 ∈ (509, 511)）；`git diff` 该块 3 行 `+` | DESIGN-D2 / IMPL §4.3② / F-I-P033-3 | [待 Step 9] |
| B3 | 订单保留重试语义：无效价分支**不** `cancel_order`、**不** `mark_executed`；`mark_expired(date)`（L528）原位保留 → 半衰期兜底（≤4 交易日排空，不新增限流/去重） | 读码；B4/B7 断言 `len(get_pending_orders()) == 1` / `== []` | DESIGN-D5 / I4 / R-P033-3 | [待 Step 9] |
| B4 | V2 绿（参数 2：NaN / 0）：100 股 BUY 入队 + `enable_pending_orders=True` → 零成交、`cash == 10_000_000`、`len(get_pending_orders()) == 1`、`get_failure_stats()["pending_invalid_price"] == 1` | `pytest -q -k "v2_agents_queue"` = **2 passed** | V2 / I2 / I6 | [待 Step 9] |
| B5 | V3 绿（参数 2：-5.0 / -inf）：零成交、`cash` 不变、`pending_invalid_price == 1`（覆盖 R2「现金 +500」与 R1 `-inf`） | `pytest -q -k "v3_agents_negative"` = **2 passed** | V3 / I2 / R2 | [待 Step 9] |
| B6 | V4 绿（SELL NaN 持仓保留）：先建仓 100 股 @10 → 入 SELL 100 + `open=NaN` → 零成交、`qty == 100`（**不清零**）、`avg_cost == 10.0`、`cash` 不变 | `pytest -q -k "v4_sell_nan"` = **1 passed** | V4 / I2 / O-S2-P033-1 | [待 Step 9] |
| B7 | V5 绿（重试 bounded）：全程 `open=NaN`，逐日 `_process_pending_orders` + `mark_expired` 共 8 日 → 总成交 0、期末 `get_pending_orders() == []`、`0 < pending_invalid_price <= 5`（**区间断言，不写精确等值**） | `pytest -q -k "v5_retry_bounded"` = **1 passed** | V5 / DESIGN-D5 / F-I-P033-2 | [待 Step 9] |
| B8 | V8a 绿（agents 正常路径零误报）：合法价 10 + 1 张 BUY → 成交恰 1 笔 `price == 10` / `quantity == 100`；`pending_invalid_price` 缺席或 0；**红态即通过须显式标注**（回归保护） | `pytest -q -k "v8_normal_path"` 的 agents 参数通过 | V8 / I3 / F-S6-P033-1 | [待 Step 9] |

---

## 3. C 组：B3 V2 queue 前置过滤（D2 → 测试 V6 / V8b）

> **DoR**: `skipped_price` 局部名单（L780）与汇总日志（L836-839，`logger.warning("跳过N个缺少价格数据订单: ...")`）既有；V2 内部顺序 clamp（L792）→ 成员检查（L799）→ 取价（L803-808）→ 夹紧告警（L810）→ `execute_order`（L815）。**DoD**: 无效价订单零成交、零入账，且进入既有 skipped 归因链路（零新键零新日志语句）。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | 导入 L23 改为 `from core.execution import ExecutionSimulator, is_valid_price`；**不新增** V2 侧 `_failure_counts`（API 扩张已被排除） | 读码 L23；`Select-String "_failure_counts" core/engine_v2.py` = 0 | DESIGN-D2 / IMPL §4.4① / §7-#5 | [待 Step 9] |
| C2 | 过滤块位置：L808（`close_price` 多行赋值结束）**之后**、L810（夹紧告警）**之前**；三行形态 `if not is_valid_price(open_price):` / `skipped_price.append(order.stock)` / `continue` | 读码行序（过滤块行号 ∈ (808, 810)）；`git diff` 该块 3 行 `+` | DESIGN-D2 / IMPL §4.4② / F-S4-P033-1 | [待 Step 9] |
| C3 | 计量零新增：复用 L780 `skipped_price` 名单与 L836-839 既有汇总 `logger.warning`；**零新增键、零新增日志语句**；文案「缺少价格数据」语义扩展（R-P033-2）不改文案 | 区间 `git diff` 中 `^+.*logger\.` = **0**；读码 L836-839 未改 | I6 / DESIGN-D2 / R-P033-2 | [待 Step 9] |
| C4 | V6 绿（参数 2：NaN / 0）：向 `PendingOrderQueue` 注入 1 张 BUY → 零成交、`cash` 不变、`caplog` 捕获 WARNING 含「缺少价格数据订单」与该股代码（`skipped_price` 为局部名单无 getter） | `pytest -q -k "v6_v2_queue"` = **2 passed** | V6 / I2 / F-S4-P033-2 | [待 Step 9] |
| C5 | V8b 绿（V2 正常路径零误报）：合法价 10 + 1 张 BUY → 成交恰 1 笔 `price == 10`；`caplog` 无「缺少价格数据」日志；**红态即通过须显式标注**（回归保护） | 同 `-k "v8_normal_path"` 的 V2 参数通过 | V8 / I3 | [待 Step 9] |

---

## 4. D 组：不变式与保护面（I1-I7）

> **DoR**: 七条不变式已在 DESIGN §5 定稿；零改动面清单在 IMPL §1 定稿；golden 7 份 json 已存在。**DoD**: 断言组合成立或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | I1：任何入账 `Trade.price` 恒为有限正数（守卫后置条件）——V1 六值全部拒绝 + VWAP 聚合 NaN 拒绝 | A6 + A7 断言 | I1 / V1 / V7 | [待 Step 9] |
| D2 | I2：无效价 → `trade_log` 零增、`cash` / 持仓零变化、订单保留（BUY 与 SELL 双侧） | B4 + B5 + B6 + C4 断言 | I2 / V2-V4 / V6 | [待 Step 9] |
| D3 | I3：合法价路径逐字不变——既有 **731** 全绿 + golden **13 零重录** | E4 + E6 | I3 / V8 | [待 Step 9] |
| D4 | I4：调用方语义保持（DESIGN-D4 七行表零变更）——queue 不 `mark_executed`（留队）、next-day 入 `failed_orders`、强平 `if success and trade` 才入账、`agent_framework` 与 fallback 委托不受影响 | 读码 DESIGN §3.4 七行；B3 断言 | I4 / DESIGN-D4 | [待 Step 9] |
| D5 | I5：公开签名零变更（`execute_order` / 两处 `_process_pending_orders` / `_get_execution_price`）；`is_valid_price` 为新增模块级函数（非公开 API 变更）；`except Exception` 恒 **22** | `git diff \| Select-String '^-\s*def '` = **0**；AST 命令 = **22** | I5 / §8 A8 | [待 Step 9] |
| D6 | I6：计量不对称成立——agents 恰 **+1 键** `pending_invalid_price`（1 处写入）；V2 **零新键**（复用 `skipped_price`）；零新出口 | `Select-String "pending_invalid_price"` = 1 写入 + 测试引用；`git diff` 无 V2 键新增 | I6 / DESIGN-D2 | [待 Step 9] |
| D7 | I7：门禁 **748 passed / 83 文件 / black 120 / mypy 37 files 0 / golden 13 零重录 / AST 22** | E4 + E5 + E6 + D5 | I7 / §1 门禁口径 | [待 Step 9] |

---

## 5. E 组：测试、门禁与治理（B4）

> **DoR**: §5 V1-V8 十七实例与 §6 F1-F6 fixture 表已定稿；四文档互链清单已定（RESEARCH / DESIGN / IMPL / CHECKLIST + §12/§13）；`CHANGELOG` `[Unreleased]` 结构既有。**DoD**: 计数与末行读数逐字一致；红态先于绿态；台账闭环。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 新测试文件 `tests/test_p033_order_price_validation.py` 恰含 **17 实例** = V1 6 + V2 2 + V3 2 + V4 1 + V5 1 + V6 2 + V7 1 + V8 2；`^def test_` = **8**（V1 / V2 / V3 / V6 / V8 五处参数化，其余三例单实例） | `pytest --collect-only -q tests/test_p033_order_price_validation.py` 末行 **17 tests collected**；`Select-String '^def test_'` = 8 | V1-V8 / IMPL §5 | [待 Step 9] |
| E2 | 红态纪律：B1t **5F/1P** → B2t **6F/1P** → B3t **2F/1P**，全批 **14F/3P**；**豁免三例**（V1-None 经 TypeError 漏斗 L339 / V8a / V8b）显式标注；三批红态读数记入 IMPL §11 | 三批红态输出留档 + IMPL §11 记录 | IMPL §3 / §5 / §13.4 / F-S6-P033-1 | [待 Step 9] |
| E3 | 新测试 **17 passed** | `pytest tests/test_p033_order_price_validation.py -q` 末行 | V1-V8 | [待 Step 9] |
| E4 | 全量回归 **748 passed**（731 基线 + 17） | `MPLBACKEND=Agg pytest -q` 末行 | I7 | [待 Step 9] |
| E5 | black `--check core tests` **120 unchanged**（新测试文件计入）；mypy `--explicit-package-bases core` **37 files 0 error** | 两条门禁命令末行 | I7 / O-I-P033-1 | [待 Step 9] |
| E6 | golden **13 passed** 且 `tests/golden/*.json` 零改动（零重录）；**零改动面**全空：`core/tracker.py` / `core/pending.py` / `core/interfaces.py` / `core/target_positions.py` / `filter/` / `scripts/` / `cli.py` / `pyproject.toml` / `tests/test_p029_*.py` / `tests/test_p031_*.py` | `pytest -q -k golden`；`git status --short` 上述面空 | I3 / I6 / IMPL §1 | [待 Step 9] |
| E7 | 测试零 `unittest.mock`（统一 `monkeypatch` / 直接注入）；fixture F1-F6 全部落在新文件内，**不修改**既有 `test_p027*` / `test_p029*` / `test_p031*` | `Select-String "unittest.mock"` = 0；`git diff --name-only tests/` 仅新增 1 文件 | IMPL §6 约束 / §7 | [待 Step 9] |
| E8 | 受影响面快速回归：`-k "golden or p027 or p029 or p031"` **57 passed / 0 failed / 0 error**（基线 57，量化不回归） | 该子集输出末行 | 回归面 / §1 基线 | [待 Step 9] |
| E9 | 远端 CI 三 job（3.10 / 3.11 / 3.12）success | `gh run view <id> --json conclusion,jobs` | 交付纪律 | [待 Step 9] |
| E10 | 四文档互链 0 broken；`PROGRESS` §1.4 P-033 行更新 + §3.38.6 Step 9 记录；`CHANGELOG` `[Unreleased]` 记录本批行为变更（**1 处语义修正** + **1 个新计数键** + 零公开签名变更） | 机械校验链接数/broken 数；读回 §1.4 与 CHANGELOG | IMPL §2 B4 / 台账惯例 | [待 Step 9] |
| E11 | 未决/观察登记完整：`U-P033-1~3` / `R-P033-1~3` / `O-D-P033-1~2` / `F-D3-P033-1~2` / `F-I-P033-1~4` + `O-I-P033-1` / `F-S2-P033-1~2` + `O-S2-P033-1~2` / `F-S4-P033-1~2` + `O-S4-P033-1~3` / `F-S6-P033-1` + `O-S6-P033-1~2` 全部有落点 | 读回 DESIGN §7 / IMPL §9 / §13.6 / RESEARCH §11.6 / PROGRESS 未决表 | DESIGN §7 / IMPL §9 | [待 Step 9] |
| E12 | 行号漂移登记：Step 9 后三文件被改函数实测行号 vs IMPL §4 实施前锚点（`013c4d3` 代码面），差异逐项登记（F-I 惯例） | IMPL §11 新增漂移表 | IMPL §4 / §11 | [待 Step 9] |

---

## 6. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **39**（A 7 + B 8 + C 5 + D 7 + E 12 = 39，机械计数；ID 去重 39/39） |
| 实测列 `[待 Step 9]` 数 | Step 7 时点：**39 处单元格**零预填；字面引用仅规则说明与占位（头部规则行 1 / 本行 1 / 签字表 Step 9 行 2），**零单元格预填** |
| 覆盖映射（测试用例） | V1 → A6；V2 → B4；V3 → B5；V4 → B6；V5 → B7；V6 → C4；V7 → A7；V8 → B8 + C5 —— **8/8 用例 ID、17/17 实例全覆盖** |
| 覆盖映射（不变式） | I1→D1 / I2→D2 / I3→D3 / I4→D4 / I5→D5 / I6→D6 / I7→D7 —— **7/7** |
| 覆盖映射（设计决策） | DESIGN-D1→A1-A7 / DESIGN-D2→B1-B8+C1-C5 / DESIGN-D3→A4 / DESIGN-D4→D4 / DESIGN-D5→B3+B7 / DESIGN-D6→E11（R3 仅登记 + U-P033-1）—— **6/6** |

> **RULE-2 统计溯源**：39 由 §1-§5 五张表逐行机械计数得出（A1-A7 = 7 / B1-B8 = 8 / C1-C5 = 5 / D1-D7 = 7 / E1-E12 = 12，合计 39），非估计值。17 实例由 IMPL §2 计数口径（V1 6 + V2 2 + V3 2 + V4 1 + V5 1 + V6 2 + V7 1 + V8 2）机械相加得出。

> **本文件作者基座**: DeepSeek-V4.1-Flash（与 RESEARCH / DESIGN / IMPL 同源）→ **Step 8 一致性 Review 须由异构基座执行**（RULE-5）。

---

## 7. Step 7 → Step 8 交接事项

1. **Step 8 一致性 Review（异构基座 GLM-5.3-Flash）**：核四文档口径——
   - **17 实例**（V1 6 / V2 2 / V3 2 / V4 1 / V5 1 / V6 2 / V7 1 / V8 2）在 DESIGN §6 / IMPL §2+§5 / 本文件 E1+§6 三处一致；
   - **门禁链** 731→**748** / 82→**83** / 119→**120** / 37 不变 / golden 13 零重录 / AST 22 在 DESIGN I7 / IMPL §1 / 本文件头 + D7 + E4-E5 三处一致；
   - **1 处语义修正 + 1 个新计数键**（`pending_invalid_price`）在 DESIGN §1+§4.2 / IMPL §1+§4.3 / 本文件 B2-B4 一致；
   - **红态 14F/3P** 与豁免三例（V1-None / V8a / V8b）在 IMPL §3+§13.4 / 本文件 E2 一致。
2. **两套 ID 不得混用**：DESIGN 决策 `D1-D6` 与本文件分组 **D**（不变式组）同字母——凡引用 DESIGN 决策一律标 `DESIGN-D*`；用例 ID `V1-V8` 在 DESIGN 契约 / IMPL 用例 / 本文件三处语义一致（同一套，17 实例口径）。
3. **顺序敏感核验（Step 9 必做）**：① 守卫必须在 `execution_price` 解析**后**、差异告警**前**；② 守卫必须在 `amount` / `Trade` / `add_trade` **之前**；③ agents 过滤必须在 L509 **后**、L511（clamp）**前**；④ V2 过滤必须在 L808 **后**、L810（clamp 告警）**前**；⑤ B1 必须先于 B2 / B3 落地（导入依赖）。
4. **红态豁免标注**：V1-None（既有 TypeError 漏斗 L339）、V8a、V8b 三例红态即通过属预期，E2 留档须显式标注，防误判为「红态不成立」。
5. **行号漂移**：Step 9 完成后按 F-I 惯例登记（IMPL §4 锚点为实施前 `013c4d3` / 当前 `204b15f` 代码面），E12 为专用验收项。
6. **black 先行**：新测试文件首轮须先跑 `black` 再进门禁（O-I-P033-1，P-029 / P-031 两次先例）。
7. **AST 口径注记**：`except Exception` 22 的 P-029 十文件命令（`agents` / `filter` / `scripts` / `batch_backtest` / `strategy_evaluation` + `cli.py`）**不含 `core/`**；本批 `core/` 改动亦须零新增 `except`（读码 + `git diff` 留证，E11 之外的 D5 已覆盖）。

---

## 8. 签字表

| 角色 | 基座 | 结论 | 日期 |
|------|------|------|------|
| Step 7 验收清单作者 | DeepSeek-V4.1-Flash | 39 项完稿，零预填 | 2026-11-17 |
| Step 8 一致性 Review | [待 Step 8]（须异构基座 GLM-5.3-Flash） | [待 Step 8] | — |
| Step 9 TDD 执行 | [待 Step 9] | [待 Step 9] | — |
| Step 10 ADD 审计 + RULE-5 异构终审 | [待 Step 10] | [待 Step 10] | — |
