# CHECKLIST：P-031 `StrategyEngine` 订单簿与估值时序

> **批次**: P-031 · **T1**（`agents/multi_strategy_engine.py` 单文件 + 新增账目测试）
> **上游**: [IMPL_p031](IMPL_p031_strategy_engine_order_accounting.md)（B1-B5 / §4 逐函数规格 / §5 V1-V6+V2b / §6 fixture / §7 低效排除 / §8 回退点 / §9 F-I-P031-1~7 / §13 Step 6 复审 pass）；[DESIGN_p031](DESIGN_p031_strategy_engine_order_accounting.md)（D1-D7 / I1-I8 / V1-V6 / §12 Step 4 复审）；[RESEARCH_p031](RESEARCH_p031_strategy_engine_order_accounting.md)（§3 R1-R4 / §11 Step 2 复审）
> **状态**: **Step 7 验收清单完稿**（2026-11-16，作者基座 DeepSeek-V4.1-Flash = 四文档同源；Step 8 一致性 Review 须异构）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**禁止与正文同一次写入时打勾**
> **基线读数（Step 7 实测 @HEAD `6a7771e`，Python312 + `MPLBACKEND=Agg`）**: 全量 `pytest -q` **722 passed**（172 warnings）/ `tests/` .py **81**（78 `test_*.py` + 3 `_` 辅助）/ `black --check core tests` **118 unchanged** / `mypy --explicit-package-bases core` **37 files 0 error** / `tests/golden/` **7** 份 json（13 条 golden 用例）/ `except Exception` 合计 **22**
> **目标读数（Step 9）**: **731 passed** / 测试文件 **82** / black **119** / mypy **37 files 0** / golden **13 零重录** / `except Exception` 恒 **22**
> **代码证据时点**: 实施前 HEAD `6a7771e`（与 IMPL §4 锚点基准 `96bed8d` 代码面一致，仅 docs 变更）；Step 9 后按 F-I 惯例登记行号漂移

---

## 1. A 组：B1 中性空头腿禁用（D2 → 测试 V5）

> **DoR**: `_execute_neutral_rebalance` 的 `try/except Exception` 结构与 `neutral_optimize` 键已在 P-027 冻结；`short_optimizer` 无第二消费者；`_generate_results` 被 `MultiStrategyEngine` 两循环直调（L786 / L928）。**DoD**: 空头腿零订单、零幻影现金、双重披露可观测，且 long/short 路径零影响。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `short_optimizer` 构建（L271-279）与调用（L293 `short_weights = ...`）**删除**；`short_weights` / `combined_weights` 标识符零残留 | `git diff` 中两段为 `-` 行；`Select-String "short_weights\|combined_weights"` = 0 命中 | D2 / IMPL §4.3 | [待 Step 9] |
| A2 | 只合并多头腿：`target_weights = long_weights * self.strategy_cfg.long_weight`；**不重归一化**（权重和 ≈ `long_weight` = 0.5），无 `* 2` / `/ sum` 类补偿 | 读码该行；V5 中断言 `target_weights.sum() <= 0.5 + 1e-9` | D2 / F-S4-P031-4 / U-P031-4 | [待 Step 9] |
| A3 | `neutral_short_leg_skipped` 计数位于 `long_optimizer.optimize` **成功之后**、`try` 块内——optimize 抛错时该键**不出现**（保 `test_p027` 精确断言 `== {"neutral_optimize": 1}`） | `pytest -q -k strategy_engine_failure_counts` 3 passed（neutral 参数集精确相等断言不变） | D2 / IMPL §4.3 / §13.5-#4 | [待 Step 9] |
| A4 | `__init__` 对 `direction == "both"` 打 **1 条** WARNING（文案含 `unsupported`），long/short 构造**零新增** WARNING；签名零变更 | V5 用 `caplog` 断言 1 条；long 参数集断言 0 条 | D2 / IMPL §4.1 / I5 | [待 Step 9] |
| A5 | `_generate_results` 追加 `additional_info.neutral_short_leg`：`"unsupported"`（both）/ `"not_applicable"`（long/short）；写在此函数而非 `run()`（多策略直调） | 读码；V5 断言 `== "unsupported"`；V6 断言 `== "not_applicable"` | D2 / D6 / IMPL §4.9 | [待 Step 9] |
| A6 | V5 绿：`both` + `long_weight=0.5` → **零 SELL 成交**、`neutral_short_leg_skipped > 0`、标记 `unsupported`、1 条 WARNING；多头腿仍买入（半仓） | `pytest -q -k neutral_short_leg` = 1 passed | V5 / I7 / F-S2-P031-2 | [待 Step 9] |

---

## 2. B 组：B2 估值与目标持仓（D1 → 测试 V1 / V2 / V2b）

> **DoR**: `core/target_positions.py` 双函数已存在且被 V2 验证（engine_v2 L953-990）；`_generate_rebalance_orders` 旧临时 dict 无第二消费者（IMPL §9 F-I-P031-4）。**DoD**: 目标外持仓必清仓、NAV 价格重算、nav 非正不抛 ValueError，且防线全在 `agents/` 单文件内。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | 导入新增：`TargetPosition, build_target_positions, compute_portfolio_value`（L37 后）；`PendingOrder` 追加 L34；`core/` 零改动 | `git diff agents/multi_strategy_engine.py` 头部两端；`git status --short core/` 空 | D1 / D7 / I6 | [待 Step 9] |
| B2 | `_generate_orders` 价格切片**统一一次** `try: ... .loc[date] except (KeyError, IndexError): _record_failure("orders_missing_price"); return`；原**逐股** `if stock in adj_close.columns` 分支删除 | 读码；`git diff` 中原 L325-332 逐股块为 `-` 行 | D1 / F-S4-P031-3 | [待 Step 9] |
| B3 | `nav = compute_portfolio_value(cash, current>0, prices, market_values)`；守卫 `if not np.isfinite(nav) or nav <= 0: _record_failure("rebalance_nav_invalid"); return`，**置于** `build_target_positions` 之前 | 读码顺序（守卫行号 < targets 行号）；V2b 断言该键 1 | D1 / F-S4-P031-2 / §13.4 | [待 Step 9] |
| B4 | `build_target_positions(..., round_lot=self.base_cfg.optimizer.round_lot)`，`value_buffer` 走默认 0.985（不显式传参）；`_generate_rebalance_orders` 签名改 `dict[str, TargetPosition]`，**先 SELL 后 BUY** 两轮循环 | 读码两函数；`git diff` 中签名行 1 处 `-`/`+` | D1 / 裁决 #3 / V2 语义 | [待 Step 9] |
| B5 | V1 绿：持仓 A=1000、`target_weights={"B": 0.5}` → `_next_day_orders` 含 `SELL A 1000`；次日执行后 A=0、B>0 | `pytest -q -k exit_order` = 1 passed | V1 / I1 / R2 | [待 Step 9] |
| B6 | V2 绿：1 股常量价 10、`daily`、恒定 100%、**零成本**、10 个交易日 → 成交**恰 1 笔**（旧实现 9 笔）；每日 `cash + Σqty×price == 初始资金` | `pytest -q -k nav_timing` = 1 passed | V2 / I3 / R1 / F-I-P031-7 | [待 Step 9] |
| B7 | V2b 绿：`tracker._cash = 0` 且无持仓（nav=0）→ **不抛异常**、`rebalance_nav_invalid == 1`、零订单 | `pytest -q -k nav_guard` = 1 passed | V2b / F-S4-P031-2 | [待 Step 9] |
| B8 | P-029 **V4 回归面**：`_MissingPriceFrame` 注入 → 新入口 `orders_missing_price == 1`；legal 用例（`{"ZZZ": 1.0}` 缺列）→ 零计数零订单 | `pytest -q -k order_missing_price` = 2 passed（原断言零修改） | F-S4-P031-3 / §10-#6 / I6 | [待 Step 9] |

---

## 3. C 组：B3 双路径卖量夹紧（D3 → 测试 V3 ×2）

> **DoR**: `_clamp_sell_quantity` 语义与 V2 L671-688 同源；`execute_order` 显式接收 `quantity`（execution.py L262-273）；`PendingOrderQueue.cancel_order(order, date)` 已存在（pending.py L355）。**DoD**: 两路径逐字同形、无持仓卖单不成交不入账、BUY 侧零夹紧。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | 新增 `_clamp_sell_quantity(self, order: PendingOrder) -> int`：BUY 早退返回 `int(order.quantity)`；SELL 返回 `min(quantity, max(position.quantity, 0))`，无持仓返回 0 | 读码；`grep -n "def _clamp_sell_quantity"` = 1 | D3 / IMPL §4.6 / V2 L671 | [待 Step 9] |
| C2 | **次日路径**：`qty = _clamp_sell_quantity(order)` → `qty<=0` 计 `oversell_blocked` + `continue`（丢弃）；`qty<order.quantity` 计 `oversell_trimmed`；`execute_order(..., qty, ...)` 传 `qty` | 读码 §4.7 三处；V3 next_day 参数集通过 | D3 / I2 / R4 | [待 Step 9] |
| C3 | **队列路径**：同形插入 + `qty<=0` 计 `oversell_blocked` **并** `pending_queue.cancel_order(order, date)`；改直调 `execute_order(..., qty, ..., close_price)`（F-I-P031-2）；`mark_executed` 仍对原订单对象 | 读码 §4.8；V3 queue 参数集断言 `order.status.name == "CANCELLED"` | D3 / F-S4-P031-1 / F-I-P031-2 | [待 Step 9] |
| C4 | **双路径同形核验**：两处 `oversell_blocked` / `oversell_trimmed` 键名、判定顺序（blocked → trimmed → execute）逐字一致；无「只修一条」漏点 | `Select-String -Pattern "oversell_blocked\|oversell_trimmed"` 各命中 2 处；读码判定序列一致 | D3 / §10-#1 / §13.5-#1 | [待 Step 9] |
| C5 | V3 双参数集绿：持仓 100 + 3×`SELL 100`（零成本）→ 成交**1 笔 100 股**、`oversell_blocked == 2`、cash 恰 **+1,000**（非 +3,000）；队列路径另断言 2 张单 `CANCELLED` | `pytest -q -k oversell` = 2 passed | V3 / I2 / R4 | [待 Step 9] |
| C6 | BUY 侧**零夹紧**：`_clamp_sell_quantity` 对 BUY 早退，两路径 BUY 行为与本批前逐字一致；U-P031-2 维持登记 | 读码早退分支；V6 正常路径 BUY 成交不受影响 | D3 / U-P031-2 / IMPL §4.6 | [待 Step 9] |

---

## 4. D 组：B4 双载体撤销 + 过期（D4 → 测试 V4 ×2 / V6）

> **DoR**: `PendingOrderQueue.cancel_orders(stock, date)`（pending.py L437）与 `is_expired(current, max_days)`（L202）均存在；`base_cfg.max_pending_days_buy=5 / sell=10`（config L376-377）；两载体在 `StrategyEngine` 中互斥（IMPL §4.2）。**DoD**: 每次再平衡清空信号域内两类在途单、逾期单不再执行，域外单保留。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | 撤销块位置：`_execute_rebalance` 内「日期不在信号索引」早退（L203-204）**之后**、`daily_signal`（L207）**之前**——当日新单不会被自撤销 | 读码行号序；V4 撤销参数集通过 | D4 / §10-#2 / §13.5-#2 | [待 Step 9] |
| D2 | **双载体**：① `_next_day_orders` 按 `domain = set(self._composite_signal.columns)` keep/drop；② `if self.pending_queue: for stock in domain: cancel_orders(stock, date)`；域外在途单保留 | 读码 §4.2；`git diff` 两载体均为 `+` 行 | D4 / F-S4-P031-1 / R-P031-3 | [待 Step 9] |
| D3 | `next_day_orders_cancelled` 计「**发生次数**」（每次再平衡至多 +1，非订单张数）；queue 载体撤销**不新增键**（既有 `logger.info` 事件） | 读码 `if dropped: _record_failure(...)`；V4 断言 `> 0` | D4 / D6 / O-S4-P031-1 | [待 Step 9] |
| D4 | 过期过滤位于开盘价切片**之后**（F-I-P031-1）、`buyable_mask` 之前；`order.is_expired(date, max_days)` 复用（max_days 按 side 取 buy/sell）；`next_day_orders_expired` 计次数；**不做** `mark_expired` 状态迁移（O-S6-P031-2） | 读码位置与调用；`grep "mark_expired"` 在 `StrategyEngine` 内仍仅 1 处（`run()` 末尾 queue 清理） | D4 / F-I-P031-1 / O-S6-P031-2 | [待 Step 9] |
| D5 | V4 双参数集绿：① 撤销 → `_next_day_orders` 不含该股 + `cancelled > 0`；② **BUY 单**创建日距当前 ≥6 自然日 → `expired > 0` 且不再执行（F-S6-P031-1：SELL 不适用 6 日） | `pytest -q -k "cancel or expire"` = 2 passed | V4 / I4 / F-S6-P031-1 | [待 Step 9] |
| D6 | V6 绿：常规多头两股全链路 `run()` → **6 个新键全 0**；`orders_missing_price` / `next_day_open_price` 零误报；`additional_info.neutral_short_leg == "not_applicable"` | `pytest -q -k normal_path` = 1 passed | V6 / I8 / 回归保护 | [待 Step 9] |

---

## 5. E 组：不变式与保护面（I1-I8）

> **DoR**: 九面零改动清单已在 IMPL §1 定稿；golden 7 份 json 已存在。**DoD**: 断言组合成立或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | I1：目标外持仓（有持仓且可定价）必产生 SELL 清仓单 | B5（V1）断言 | I1 / V1 | [待 Step 9] |
| E2 | I2：现金守恒——`cash` 变化 = Σ成交净额；**无持仓 SELL 不成交、不入账** | C5（V3 双路径）断言 | I2 / V3 | [待 Step 9] |
| E3 | I3：再平衡 NAV 以价格重算——`daily` + 恒定目标 → 成交笔数 ≤ 标的数据（V2 恰 1 笔，旧 9 笔） | B6（V2）断言 | I3 / V2 | [待 Step 9] |
| E4 | I4：在途单有界——每次再平衡后信号域内仅本次新单；过期上限 buy 5 / sell 10（自然日，含半衰期） | D5（V4）断言 | I4 / V4 | [待 Step 9] |
| E5 | I5：**公开**签名零变更（`StrategyEngine.__init__` / `run` / `get_failure_stats`）；`except Exception` 合计恒 **22** | `git diff \| Select-String '^-\s*def (__init__\|run\|get_failure_stats)'` = **0**；私有 `_generate_rebalance_orders` 形参变更属允许项（IMPL §8 已登记）；AST 扫描 = 22 | I5 / D7 / §13.2 | [待 Step 9] |
| E6 | I6：`core/` 与 `tests/golden/*.json` **零改动**（含 `target_positions.py` / `tracker.py` / `execution.py` / `pending.py`） | `git status --short core/ tests/golden/` = 空；`git diff --name-only` 仅 agents + 新测试 | I6 / D7 | [待 Step 9] |
| E7 | I7：中性空头腿显式——warning + `neutral_short_leg_skipped` + `additional_info`，**无静默** | A4 / A5 / A6 组合 | I7 / V5 | [待 Step 9] |
| E8 | I8：门禁 **731 passed** / 测试文件 **82** / black **119** / mypy **37 files 0** / golden **13 零重录** | 全量末行；文件计数；两条 check 命令；`-k golden` | I8 / §6 | [待 Step 9] |

---

## 6. F 组：测试、门禁与治理

> **DoR**: §5 测试规格（9 实例）与 §6 fixture 表已定稿；四文档互链清单已定（RESEARCH/DESIGN/IMPL/CHECKLIST + §12/§13）。**DoD**: 计数与末行读数逐字一致；红态先于绿态；台账闭环。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 新测试文件恰含 **9** 个实例 = V1 1 + V2 1 + V2b 1 + V3 **2** + V4 **2** + V5 1 + V6 1；函数数 ≤ 7（V3/V4 参数化） | `pytest --collect-only -q tests/test_p031_strategy_engine_accounting.py` 末行 **9 tests collected** | V1-V6+V2b / IMPL §5 | [待 Step 9] |
| F2 | 红态纪律：B1t / B2t / B3t / B4t 逐批先红后绿；红态读数记入 IMPL §11；**V6 红态即通过属预期**（回归保护，须显式标注） | 四批红态输出留档 + IMPL §11 记录 | IMPL §3 / §5 | [待 Step 9] |
| F3 | 新测试 **9 passed** | `pytest tests/test_p031_strategy_engine_accounting.py -q` | V1-V6+V2b | [待 Step 9] |
| F4 | 全量回归 **731 passed**（722 基线 + 9） | `MPLBACKEND=Agg pytest -q` 末行 | I8 | [待 Step 9] |
| F5 | mypy **37 files 0 error**；black `--check core tests` **119 unchanged** | 两条门禁命令末行 | I8 | [待 Step 9] |
| F6 | golden G1-G7 **13 passed** 且 `tests/golden/*.json` 零改动（零重录） | `pytest -q -k golden`；`git status --short tests/golden/` 空 | I6 / I8 | [待 Step 9] |
| F7 | 测试零 `unittest.mock`（统一 `monkeypatch`）；fixture 独立，**不修改** `test_p029_*` / `test_p027_*` / `test_rebalance_exits.py` | `grep "unittest.mock"` = 0；`git diff --name-only tests/` 仅新增 1 文件 | IMPL §6 约束 / §7-#7 | [待 Step 9] |
| F8 | 受影响面快速回归：`agents or strategy_engine or pending or portfolio` 子集 **0 failed / 0 error**，P-027 套件（24 passed）与 P-029 套件（11 passed）不回归 | `pytest -q -k "..."` 输出 | 回归面 | [待 Step 9] |
| F9 | 远端 CI 三 job（3.10 / 3.11 / 3.12）success | `gh run view <id> --json conclusion,jobs` | §6 / 交付纪律 | [待 Step 9] |
| F10 | 四文档齐备互链 0 broken；`PROGRESS` §1.4 P-031 置 `done` + §3.36 系列补齐 Step 7-10；`CHANGELOG` `[Unreleased]` 记录本批行为变更（4 处语义修正 + 1 处显式降级 + 6 计数键） | 机械校验链接数/broken 数；读回 §1.4 与 CHANGELOG | IMPL §2 B5 | [待 Step 9] |
| F11 | 未决/观察登记完整：U-P031-1~4（负持仓模型 / BUY 夹紧 / short 语义 / 中性资金部署）、O-P031-1~3（tracker 守卫 / L918 直写 cash / README 幻觉）、F-I-P031-1~7（含 F-I-P031-7 零成本口径）、F-S6-P031-1 + O-S6-P031-1~3 全部有落点 | 读回 DESIGN §7 / IMPL §9 / §13.6 / PROGRESS 未决表 | DESIGN §7 / IMPL §9 | [待 Step 9] |
| F12 | 行号漂移登记：Step 9 实施后 `agents/multi_strategy_engine.py` 各被改函数实测行号 vs IMPL §4 实施前锚点，差异逐项登记（F-I 惯例） | IMPL §11 新增漂移表 | IMPL §4 / §11 | [待 Step 9] |

---

## 7. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **46**（A 6 + B 8 + C 6 + D 6 + E 8 + F 12 = 46，机械计数；ID 去重 46/46） |
| 实测列 `[待 Step 9]` 数 | Step 7 时点：**46 处**（= 46 验收单元格，零 ✅ 预填）；**机械匹配 49 处 = 46 单元格 + 3 处合法字面引用**（L6 头部规则行 / 本行计数说明 / 签名表 Step 9 行） |
| 覆盖映射（测试用例） | V1 → B5；V2 → B6；V2b → B7；V3 → C5（2 实例）；V4 → D5（2 实例）；V5 → A6；V6 → D6（兼 A5）→ **9/9 实例全覆盖** |
| 覆盖映射（不变式） | I1→E1 / I2→E2 / I3→E3 / I4→E4 / I5→E5 / I6→E6 / I7→E7 / I8→E8 —— **8/8** |
| 覆盖映射（设计决策） | D1→B1-B8 / D2→A1-A6 / D3→C1-C6 / D4→D1-D6 / D5→（无代码，A2 边界注记 + F11 登记）/ D6→A5 + D3 + D4 + C2-C3 / D7→B1 + E6 —— **D1-D4/D6/D7 全落点，D5 按设计无代码** |

> **RULE-2 统计溯源**：46 由 §1-§6 六张表逐行机械计数得出（A1-A6 = 6 / B1-B8 = 8 / C1-C6 = 6 / D1-D6 = 6 / E1-E8 = 8 / F1-F12 = 12，合计 46），非估计值。

> **本文件作者基座**: DeepSeek-V4.1-Flash（与 RESEARCH / DESIGN / IMPL 作者同源）→ **Step 8 一致性 Review 须由异构基座执行**（RULE-5）。

---

## 8. Step 7 → Step 8 交接事项

1. **Step 8 一致性 Review（异构基座）**：核四文档口径一致——
   - **9 实例**（V1 1 / V2 1 / V2b 1 / V3 2 / V4 2 / V5 1 / V6 1）在 IMPL §5 / 本文件 F1 / §7 覆盖映射三处一致；
   - **6 计数键**（`oversell_blocked` / `oversell_trimmed` / `next_day_orders_cancelled` / `next_day_orders_expired` / `neutral_short_leg_skipped` / `rebalance_nav_invalid`）在 DESIGN D6 / IMPL §2 / 本文件 A3+C2+D3+D4+B3 四处一致；
   - **731 / 82 / 119 / 37** 在 IMPL §1 / 本文件头 + E8 + F4-F5 三处一致（基线 722 / 81 / 118 / 37）；
   - **4 处语义修正 + 1 处显式降级**在 RESEARCH §3 / DESIGN §1 / IMPL §1 / 本文件 A-D 组标题四处一致。
2. **两套 ID 不得混用**：DESIGN 契约 V1-V6（6 条）× IMPL/CHECKLIST 用例 V1-V6+V2b（9 实例）——本文件一律按**用例 ID**，凡引用 DESIGN 契约处标 `DESIGN-V*`。
3. **顺序敏感核验（Step 9 必做）**：① 撤销块必须在信号索引早退之后；② 过期过滤必须在开盘价切片之后；③ `neutral_short_leg_skipped` 必须在 optimize 成功之后；④ nav 守卫必须在 `build_target_positions` 之前；⑤ B1 必须先于 B2 落地。
4. **红态豁免标注**：V6 在红态即通过（回归保护），F2 留档须显式标注，防误判。
5. **行号漂移**：Step 9 完成后按 F-I 惯例登记（IMPL §4 锚点为实施前 `96bed8d`/`6a7771e`），F12 为专用验收项。

---

## 9. 签字表

| 角色 | 基座 | 结论 | 日期 |
|------|------|------|------|
| Step 7 验收清单作者 | DeepSeek-V4.1-Flash | 46 项完稿，零预填 | 2026-11-16 |
| Step 8 一致性 Review | `[待 Step 8]`（须异构基座） | — | — |
| Step 9 TDD 执行 | `[待 Step 9]` | — | — |
| Step 10 ADD 审计 + RULE-5 异构终审 | `[待 Step 10]`（须异构基座） | — | — |
