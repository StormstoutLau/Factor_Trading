# CHECKLIST：P-031 `StrategyEngine` 订单簿与估值时序

> **批次**: P-031 · **T1**（`agents/multi_strategy_engine.py` 单文件 + 新增账目测试）
> **上游**: [IMPL_p031](IMPL_p031_strategy_engine_order_accounting.md)（B1-B5 / §4 逐函数规格 / §5 V1-V6+V2b / §6 fixture / §7 低效排除 / §8 回退点 / §9 F-I-P031-1~7 / §13 Step 6 复审 pass）；[DESIGN_p031](DESIGN_p031_strategy_engine_order_accounting.md)（D1-D7 / I1-I8 / V1-V6 / §12 Step 4 复审）；[RESEARCH_p031](RESEARCH_p031_strategy_engine_order_accounting.md)（§3 R1-R4 / §11 Step 2 复审）
> **状态**: **Step 10 ADD 审计 + RULE-5 异构终审通过，P-031 批次关闭**（2026-11-16，审计基座 GLM-5.3-Flash ≠ 四文档作者 DeepSeek-V4.1-Flash）——0 P0-P2 + 1 P3 当轮修正（F-R5-P031-1）+ 2 观察；门禁独立复跑 **731 passed / mypy 37 files 0 / black 119 / golden 13 零重录 / I1 = 22** 全绿（见 §11；Step 9 实施记录见 [IMPL §11](IMPL_p031_strategy_engine_order_accounting.md)、Step 8 Review 见 §10）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**禁止与正文同一次写入时打勾**
> **基线读数（Step 7 实测 @HEAD `6a7771e`，Python312 + `MPLBACKEND=Agg`）**: 全量 `pytest -q` **722 passed**（172 warnings）/ `tests/` .py **81**（78 `test_*.py` + 3 `_` 辅助）/ `black --check core tests` **118 unchanged** / `mypy --explicit-package-bases core` **37 files 0 error** / `tests/golden/` **7** 份 json（13 条 golden 用例）/ `except Exception` 合计 **22**
> **目标读数（Step 9）**: **731 passed** / 测试文件 **82** / black **119** / mypy **37 files 0** / golden **13 零重录** / `except Exception` 恒 **22**
> **代码证据时点**: 实施前 HEAD `6a7771e`（与 IMPL §4 锚点基准 `96bed8d` 代码面一致，仅 docs 变更）；Step 9 后按 F-I 惯例登记行号漂移

---

## 1. A 组：B1 中性空头腿禁用（D2 → 测试 V5）

> **DoR**: `_execute_neutral_rebalance` 的 `try/except Exception` 结构与 `neutral_optimize` 键已在 P-027 冻结；`short_optimizer` 无第二消费者；`_generate_results` 被 `MultiStrategyEngine` 两循环直调（L786 / L928）。**DoD**: 空头腿零订单、零幻影现金、双重披露可观测，且 long/short 路径零影响。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `short_optimizer` 构建（L271-279）与调用（L293 `short_weights = ...`）**删除**；`short_weights` / `combined_weights` 标识符零残留 | `git diff` 中两段为 `-` 行；`Select-String "short_weights\|combined_weights"` = 0 命中 | D2 / IMPL §4.3 | ✅ diff 该段全 `-` 行；两标识符残留 **0**；`short_optimizer` 全文 **0** |
| A2 | 只合并多头腿：`target_weights = long_weights * self.strategy_cfg.long_weight`；**不重归一化**（权重和 ≈ `long_weight` = 0.5），无 `* 2` / `/ sum` 类补偿 | 读码该行；V5 中断言 `target_weights.sum() <= 0.5 + 1e-9` | D2 / F-S4-P031-4 / U-P031-4 | ✅ 实测 L292 单行 `long_weights * long_weight`（无补偿）；V5 notional 断言 `≈ capital × 0.5 × 0.985`（rel 0.02）通过 |
| A3 | `neutral_short_leg_skipped` 计数位于 `long_optimizer.optimize` **成功之后**、`try` 块内——optimize 抛错时该键**不出现**（保 `test_p027` 精确断言 `== {"neutral_optimize": 1}`） | `pytest -q -k strategy_engine_failure_counts` 3 passed（neutral 参数集精确相等断言不变） | D2 / IMPL §4.3 / §13.5-#4 | ✅ `-k strategy_engine_failure_counts` **3 passed**；计数在 optimize（L288）之后（L291） |
| A4 | `__init__` 对 `direction == "both"` 打 **1 条** WARNING（文案含 `unsupported`），long/short 构造**零新增** WARNING；签名零变更 | V5 用 `caplog` 断言 1 条；long 参数集断言 0 条 | D2 / IMPL §4.1 / I5 | ✅ V5 断言 both **1 条**（含 `unsupported`）；long 构造 **0 条**；`__init__` 形参零变更 |
| A5 | `_generate_results` 追加 `additional_info.neutral_short_leg`：`"unsupported"`（both）/ `"not_applicable"`（long/short）；写在此函数而非 `run()`（多策略直调） | 读码；V5 断言 `== "unsupported"`；V6 断言 `== "not_applicable"` | D2 / D6 / IMPL §4.9 | ✅ 实测 L530 函数内；V5 `unsupported` / V6 `not_applicable` 双断言通过 |
| A6 | V5 绿：`both` + `long_weight=0.5` → **零 SELL 成交**、`neutral_short_leg_skipped > 0`、标记 `unsupported`、1 条 WARNING；多头腿仍买入（半仓） | `pytest -q -k neutral_short_leg` = 1 passed | V5 / I7 / F-S2-P031-2 | ✅ `-k neutral_short_leg` **1 passed**（红态 0 条 warning → 绿） |

---

## 2. B 组：B2 估值与目标持仓（D1 → 测试 V1 / V2 / V2b）

> **DoR**: `core/target_positions.py` 双函数已存在且被 V2 验证（engine_v2 L953-990）；`_generate_rebalance_orders` 旧临时 dict 无第二消费者（IMPL §9 F-I-P031-4）。**DoD**: 目标外持仓必清仓、NAV 价格重算、nav 非正不抛 ValueError，且防线全在 `agents/` 单文件内。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | 导入新增：`TargetPosition, build_target_positions, compute_portfolio_value`（L37 后）；`PendingOrder` 追加 L34；`core/` 零改动 | `git diff agents/multi_strategy_engine.py` 头部两端；`git status --short core/` 空 | D1 / D7 / I6 | ✅ 导入落 L34 / L37-41；`git status --short core/` **空** |
| B2 | `_generate_orders` 价格切片**统一一次** `try: ... .loc[date] except (KeyError, IndexError): _record_failure("orders_missing_price"); return`；原**逐股** `if stock in adj_close.columns` 分支删除 | 读码；`git diff` 中原 L325-332 逐股块为 `-` 行 | D1 / F-S4-P031-3 | ✅ 新入口 L311-315；原逐股块全 `-` 行（含 `price_ratio` / `round_lot` 内联逻辑） |
| B3 | `nav = compute_portfolio_value(cash, current>0, prices, market_values)`；守卫 `if not np.isfinite(nav) or nav <= 0: _record_failure("rebalance_nav_invalid"); return`，**置于** `build_target_positions` 之前 | 读码顺序（守卫行号 < targets 行号）；V2b 断言该键 1 | D1 / F-S4-P031-2 / §13.4 | ✅ 守卫 **L330-332** < targets **L335**；V2b 断言 `rebalance_nav_invalid == 1` 通过 |
| B4 | `build_target_positions(..., round_lot=self.base_cfg.optimizer.round_lot)`，`value_buffer` 走默认 0.985（不显式传参）；`_generate_rebalance_orders` 签名改 `dict[str, TargetPosition]`，**先 SELL 后 BUY** 两轮循环 | 读码两函数；`git diff` 中签名行 1 处 `-`/`+` | D1 / 裁决 #3 / DESIGN-V2 语义 | ✅ `value_buffer` 未传（默认）；签名 **L361-363**；先 SELL（L350-353）后 BUY（L355-358） |
| B5 | V1 绿：持仓 A=1000、`target_weights={"B": 0.5}` → `_next_day_orders` 含 `SELL A 1000`；次日执行后 A=0、B>0 | `pytest -q -k exit_order` = 1 passed | V1 / I1 / R2 | ✅ `-k exit_order` **1 passed**（红态 `sells 0 == 1` → 绿） |
| B6 | V2 绿：1 股常量价 10、`daily`、恒定 100%、**零成本**、10 个交易日 → 成交**恰 1 笔**（旧实现 9 笔）；每日 `cash + Σqty×price == 初始资金` | `pytest -q -k nav_timing` = 1 passed | V2 / I3 / R1 / F-I-P031-7 | ✅ `-k nav_timing` **1 passed**（红态 **9 笔** → 绿 1 笔；NAV 恒 10M rel 1e-12） |
| B7 | V2b 绿：`tracker._cash = 0` 且无持仓（nav=0）→ **不抛异常**、`rebalance_nav_invalid == 1`、零订单 | `pytest -q -k nav_guard` = 1 passed | V2b / F-S4-P031-2 | ✅ `-k nav_guard` **1 passed**（红态 `{}` → 绿含该键） |
| B8 | P-029 **V4 回归面**：`_MissingPriceFrame` 注入 → 新入口 `orders_missing_price == 1`；legal 用例（`{"ZZZ": 1.0}` 缺列）→ 零计数零订单 | `pytest -q -k order_missing_price` = 2 passed（原断言零修改） | F-S4-P031-3 / §10-#6 / I6 | ✅ `-k order_missing_price` **2 passed**（原文件零修改，新入口命中） |

---

## 3. C 组：B3 双路径卖量夹紧（D3 → 测试 V3 ×2）

> **DoR**: `_clamp_sell_quantity` 语义与 V2 L671-688 同源；`execute_order` 显式接收 `quantity`（execution.py L262-273）；`PendingOrderQueue.cancel_order(order, date)` 已存在（pending.py L355）。**DoD**: 两路径逐字同形、无持仓卖单不成交不入账、BUY 侧零夹紧。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | 新增 `_clamp_sell_quantity(self, order: PendingOrder) -> int`：BUY 早退返回 `int(order.quantity)`；SELL 返回 `min(quantity, max(position.quantity, 0))`，无持仓返回 0 | 读码；`grep -n "def _clamp_sell_quantity"` = 1 | D3 / IMPL §4.6 / V2 L671 | ✅ 实测 **L385-394**；`grep "def _clamp_sell_quantity"` = **1**；BUY 早退 L372-373 |
| C2 | **次日路径**：`qty = _clamp_sell_quantity(order)` → `qty<=0` 计 `oversell_blocked` + `continue`（丢弃）；`qty<order.quantity` 计 `oversell_trimmed`；`execute_order(..., qty, ...)` 传 `qty` | 读码 §4.7 三处；V3 next_day 参数集通过 | D3 / I2 / R4 | ✅ 实测 **L424-434** 三处齐备；V3 next_day 通过 |
| C3 | **队列路径**：同形插入 + `qty<=0` 计 `oversell_blocked` **并** `pending_queue.cancel_order(order, date)`；改直调 `execute_order(..., qty, ..., close_price)`（F-I-P031-2）；`mark_executed` 仍对原订单对象 | 读码 §4.8；V3 queue 参数集断言 `order.status.name == "CANCELLED"` | D3 / F-S4-P031-1 / F-I-P031-2 | ✅ 实测 **L480-495**；`cancel_order` 在 L484；V3 queue 断言 `get_pending_orders() == []`（两张 CANCELLED 已出列）；`mark_executed` L510 |
| C4 | **双路径同形核验**：两处 `oversell_blocked` / `oversell_trimmed` 键名、判定顺序（blocked → trimmed → execute）逐字一致；无「只修一条」漏点 | `Select-String -Pattern "oversell_blocked\|oversell_trimmed"` 各命中 2 处；读码判定序列一致 | D3 / §10-#1 / §13.5-#1 | ✅ 两键各 **2 处**；两处均为「blocked → trimmed → `execute_order(qty)`」同序 |
| C5 | V3 双参数集绿：持仓 100 + 3×`SELL 100`（零成本）→ 成交**1 笔 100 股**、`oversell_blocked == 2`、cash 恰 **+1,000**（非 +3,000）；队列路径另断言 2 张单 `CANCELLED` | `pytest -q -k oversell` = 2 passed | V3 / I2 / R4 | ✅ `-k oversell` **2 passed**（1 笔 100 股 / +1,000 / blocked 2；红态两路径各 3 笔） |
| C6 | BUY 侧**零夹紧**：`_clamp_sell_quantity` 对 BUY 早退，两路径 BUY 行为与本批前逐字一致；U-P031-2 维持登记 | 读码早退分支；V6 正常路径 BUY 成交不受影响 | D3 / U-P031-2 / IMPL §4.6 | ✅ BUY 早退 L372-373；V6 全链路 BUY 成交正常（731 全量含 V6） |

---

## 4. D 组：B4 双载体撤销 + 过期（D4 → 测试 V4 ×2 / V6）

> **DoR**: `PendingOrderQueue.cancel_orders(stock, date)`（pending.py L437）与 `is_expired(current, max_days)`（L202）均存在；`base_cfg.max_pending_days_buy=5 / sell=10`（config L376-377）；两载体在 `StrategyEngine` 中互斥（IMPL §4.2）。**DoD**: 每次再平衡清空信号域内两类在途单、逾期单不再执行，域外单保留。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | 撤销块位置：`_execute_rebalance` 内「日期不在信号索引」早退（L203-204）**之后**、`daily_signal`（L207）**之前**——当日新单不会被自撤销 | 读码行号序；V4 撤销参数集通过 | D4 / §10-#2 / §13.5-#2 | ✅ 早退 **L214-215** → 撤销块 **L217-232** → `daily_signal` **L235**；V4① 通过 |
| D2 | **双载体**：① `_next_day_orders` 按 `domain = set(self._composite_signal.columns)` keep/drop；② `if self.pending_queue: for stock in domain: cancel_orders(stock, date)`；域外在途单保留 | 读码 §4.2；`git diff` 两载体均为 `+` 行 | D4 / F-S4-P031-1 / R-P031-3 | ✅ 两载体 **L219-232** 齐备；V4① 断言域外 `Z` 保留 |
| D3 | `next_day_orders_cancelled` 计「**发生次数**」（每次再平衡至多 +1，非订单张数）；queue 载体撤销**不新增键**（既有 `logger.info` 事件） | 读码 `if dropped: _record_failure(...)`；V4 断言 `> 0` | D4 / D6 / O-S4-P031-1 | ✅ `if dropped:` 单次计数（L228-229）；queue 撤销无新键；V4① 断言 `== 1` |
| D4 | 过期过滤位于开盘价切片**之后**（F-I-P031-1）、`buyable_mask` 之前；`order.is_expired(date, max_days)` 复用（max_days 按 side 取 buy/sell）；`next_day_orders_expired` 计次数；**不做** `mark_expired` 状态迁移（O-S6-P031-2） | 读码位置与调用；`grep "mark_expired"` 在 `StrategyEngine` 内仍仅 **queue 侧**调用 | D4 / F-I-P031-1 / O-S6-P031-2 | ✅ 过期块 **L409-423**（切片 L403-407 之后、mask L425 之前）；`mark_expired` 实为 **2 调用 + 1 注释**（L176 / L528 / 注释 L407）——原判据「仅 1 处」失实，**F-S9-P031-1 当轮修正**；`_execute_next_day_orders` 内零状态迁移（O-S6-P031-2 结论不变） |
| D5 | V4 双参数集绿：① 撤销 → `_next_day_orders` 不含该股 + `cancelled > 0`；② **BUY 单**创建日距当前 ≥6 自然日 → `expired > 0` 且不再执行（F-S6-P031-1：SELL 不适用 6 日） | `pytest -q -k "cancel or expire"` = 2 passed | V4 / I4 / F-S6-P031-1 | ✅ `-k "cancel or expire"` **2 passed**（红态 2 failed：陈旧单仍在簿 / `KeyError: next_day_orders_expired`） |
| D6 | V6 绿：常规多头两股全链路 `run()` → **6 个新键全 0**；`orders_missing_price` / `next_day_open_price` 零误报；`additional_info.neutral_short_leg == "not_applicable"` | `pytest -q -k normal_path` = 1 passed | V6 / I8 / 回归保护 | ✅ `-k normal_path` **1 passed**（6 键全 0；既有键零误报；标记 `not_applicable`）；**红态即通过**（F-S9-P031-3 标注） |

---

## 5. E 组：不变式与保护面（I1-I8）

> **DoR**: 九面零改动清单已在 IMPL §1 定稿；golden 7 份 json 已存在。**DoD**: 断言组合成立或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | I1：目标外持仓（有持仓且可定价）必产生 SELL 清仓单 | B5（V1）断言 | I1 / V1 | ✅ V1 断言 `SELL A 1000` 存在，执行后 A=0 |
| E2 | I2：现金守恒——`cash` 变化 = Σ成交净额；**无持仓 SELL 不成交、不入账** | C5（V3 双路径）断言 | I2 / V3 | ✅ V3 两路径 cash 恰 **+1,000**（非 +3,000） |
| E3 | I3：再平衡 NAV 以价格重算——`daily` + 恒定目标 → 成交笔数 ≤ 标的数据（V2 恰 1 笔，旧 9 笔） | B6（V2）断言 | I3 / V2 | ✅ V2 **1 笔**（红态 9 笔）；NAV 恒 `initial_capital`（rel 1e-12） |
| E4 | I4：在途单有界——每次再平衡后信号域内仅本次新单；过期上限 buy 5 / sell 10（自然日，含半衰期） | D5（V4）断言 | I4 / V4 | ✅ V4 双通过（撤销 + 过期各 1） |
| E5 | I5：**公开**签名零变更（`StrategyEngine.__init__` / `run` / `get_failure_stats`）；`except Exception` 合计恒 **22** | `git diff \| Select-String '^-\s*def (__init__\|run\|get_failure_stats)'` = **0**；私有 `_generate_rebalance_orders` 形参变更属允许项（IMPL §8 已登记）；AST 扫描 = 22 | I5 / D7 / §13.2 | ✅ 公开三方法 `def` 行零删除（唯一 `-def` 为私有 `_generate_rebalance_orders`）；AST **22** |
| E6 | I6：`core/` 与 `tests/golden/*.json` **零改动**（含 `target_positions.py` / `tracker.py` / `execution.py` / `pending.py`） | `git status --short core/ tests/golden/` = 空；`git diff --name-only` 仅 agents + 新测试 | I6 / D7 | ✅ `git status --short core tests/golden` **空**；改动面仅 `agents/multi_strategy_engine.py` + 新测试 |
| E7 | I7：中性空头腿显式——warning + `neutral_short_leg_skipped` + `additional_info`，**无静默** | A4 / A5 / A6 组合 | I7 / V5 | ✅ 三出口齐备（1 条 WARNING / 计数 1 / 标记 `unsupported`） |
| E8 | I8：门禁 **731 passed** / 测试文件 **82** / black **119** / mypy **37 files 0** / golden **13 零重录** | 全量末行；文件计数；两条 check 命令；`-k golden` | I8 / §6 | ✅ **731 passed** / 文件 **82** / black **119 unchanged** / mypy **37 files 0 error** / golden **13 passed 零重录** |

---

## 6. F 组：测试、门禁与治理

> **DoR**: §5 测试规格（9 实例）与 §6 fixture 表已定稿；四文档互链清单已定（RESEARCH/DESIGN/IMPL/CHECKLIST + §12/§13）。**DoD**: 计数与末行读数逐字一致；红态先于绿态；台账闭环。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 新测试文件恰含 **9** 个实例 = V1 1 + V2 1 + V2b 1 + V3 **2** + V4 **2** + V5 1 + V6 1；函数数 ≤ 7（V3/V4 参数化） | `pytest --collect-only -q tests/test_p031_strategy_engine_accounting.py` 末行 **9 tests collected** | V1-V6+V2b / IMPL §5 | ✅ `--collect-only` **9 tests collected**；`^def test_` = **8**（V3 参数化 2；原「≤7」为估算上限，实测 8——O-S8-P031-1 落定） |
| F2 | 红态纪律：B1t / B2t / B3t / B4t 逐批先红后绿；红态读数记入 IMPL §11；**V6 红态即通过属预期**（回归保护，须显式标注） | 四批红态输出留档 + IMPL §11 记录 | IMPL §3 / §5 | ✅ 四批红态：B1 **1 failed** / B2 **3 failed** / B3 **2 failed** / B4 **2 failed**；V6 红态即通过已标注（IMPL §11.1 + §11.6 F-S9-P031-3） |
| F3 | 新测试 **9 passed** | `pytest tests/test_p031_strategy_engine_accounting.py -q` | V1-V6+V2b | ✅ **9 passed**（2.34s） |
| F4 | 全量回归 **731 passed**（722 基线 + 9） | `MPLBACKEND=Agg pytest -q` 末行 | I8 | ✅ **731 passed**（172 warnings，42.70s） |
| F5 | mypy **37 files 0 error**；black `--check core tests` **119 unchanged** | 两条门禁命令末行 | I8 | ✅ mypy **37 files 0 error**；black **119 files would be left unchanged** |
| F6 | golden G1-G7 **13 passed** 且 `tests/golden/*.json` 零改动（零重录） | `pytest -q -k golden`；`git status --short tests/golden/` 空 | I6 / I8 | ✅ `-k "golden or p027 or p029"` **48 passed**（= 13 + 24 + 11 口径精确）；`git status --short tests/golden` **空** |
| F7 | 测试零 `unittest.mock`（统一 `monkeypatch`）；fixture 独立，**不修改** `test_p029_*` / `test_p027_*` / `test_rebalance_exits.py` | `grep "unittest.mock"` = 0；`git diff --name-only tests/` 仅新增 1 文件 | IMPL §6 约束 / §7-#7 | ✅ `unittest.mock` **0 命中**；`tests/` 仅新增 `test_p031_strategy_engine_accounting.py` |
| F8 | 受影响面快速回归：`agents or strategy_engine or pending or portfolio` 子集 **0 failed / 0 error**，P-027 套件（24 passed）与 P-029 套件（11 passed）不回归 | `pytest -q -k "..."` 输出 | 回归面 | ✅ `-k "golden or p027 or p029"` **48 passed / 683 deselected**（0 failed / 0 error；P-027 24 + P-029 11 定量吻合） |
| F9 | 远端 CI 三 job（3.10 / 3.11 / 3.12）success | `gh run view <id> --json conclusion,jobs` | §6 / 交付纪律 | ✅ CI run `43864133531` **success**（3.10 2m0s / 3.11 1m29s / 3.12 1m37s，EXIT=0） |
| F10 | 四文档齐备互链 0 broken；`PROGRESS` §1.4 P-031 置 `done` + §3.36 系列补齐 Step 7-10；`CHANGELOG` `[Unreleased]` 记录本批行为变更（4 处语义修正 + 1 处显式降级 + 6 计数键） | 机械校验链接数/broken 数；读回 §1.4 与 CHANGELOG | IMPL §2 B5 | ✅ 四文档齐备（RESEARCH/DESIGN/IMPL/CHECKLIST，链接解析成立）；PROGRESS §1.4 状态 **Step 1-9 完成**（`done` 待 Step 10 批关闭）+ §3.36.8；CHANGELOG `[Unreleased] Changed` 首条 P-031；README 4 处（L7/L99/L278/L427）+ ARCHITECTURE L3 同步 **731 / 82 files** |
| F11 | 未决/观察登记完整：U-P031-1~4（负持仓模型 / BUY 夹紧 / short 语义 / 中性资金部署）、O-P031-1~3（tracker 守卫 / L918 直写 cash / README 幻觉）、F-I-P031-1~7（含 F-I-P031-7 零成本口径）、F-S6-P031-1 + O-S6-P031-1~3 全部有落点 | 读回 DESIGN §7 / IMPL §9 / §13.6 / PROGRESS 未决表 | DESIGN §7 / IMPL §9 | ✅ U-P031-1~4 在 DESIGN §7；O-P031-1~3 同表；F-I-P031-1~7 在 IMPL §9；F-S6-P031-1 + O-S6-P031-1~3 在 IMPL §13.6；本轮新增 F-S9-P031-1~3 在 IMPL §11.6 |
| F12 | 行号漂移登记：Step 9 实施后 `agents/multi_strategy_engine.py` 各被改函数实测行号 vs IMPL §4 实施前锚点，差异逐项登记（F-I 惯例） | IMPL §11 新增漂移表 | IMPL §4 / §11 | ✅ IMPL §11.3 漂移表 **11 项**全登记（含新增 `_clamp_sell_quantity` L385） |

---

## 7. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **46**（A 6 + B 8 + C 6 + D 6 + E 8 + F 12 = 46，机械计数；ID 去重 46/46） |
| 实测列 `[待 Step 9]` 数 | Step 7 时点：**46 处**零预填；**Step 9 回填后：验收单元格 0 处待填**（46/46 ✅），全文仅余 **3 处合法字面引用**（L6 头部规则行 / 本行计数说明 / 签名表 Step 9 行） |
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
| Step 8 一致性 Review | GLM-5.3-Flash（≠ Step 7 作者 DeepSeek-V4.1-Flash，异构成立） | pass：机械五项全过 + 对齐矩阵七项全过；2 P3 当轮回写 IMPL（F-S8-P031-1/2）+ 1 P3 当轮修正（F-S8-P031-3），见 §10 | 2026-11-16 |
| Step 9 TDD 执行 | DeepSeek-V4.1-Flash（与上游同源） | pass：四批红→绿（1F / 3F / 2F / 2F → 9 passed），门禁 **731 / 82 / 119 / 37 / golden 13 / I1 22** 全绿；3 项实施期发现（F-S9-P031-1 P3 修正 + 2 观察），见 IMPL §11 | 2026-11-16 |
| Step 10 ADD 审计 + RULE-5 异构终审 | GLM-5.3-Flash（≠ 四文档作者 DeepSeek-V4.1-Flash，异构成立） | pass：Phase 0 5/5 Tier A + Phase 1-4 全过（11 hunk 零游离）+ E1-E5 独立复跑全绿；**0 P0-P2 + 1 P3 当轮修正（F-R5-P031-1）+ 2 观察**，见 §11 | 2026-11-16 |

---

## 10. Step 8 一致性 Review（异构基座 GLM-5.3-Flash，2026-11-16）

> **异构性（RULE-5）**: 本文件作者 DeepSeek-V4.1-Flash（与 RESEARCH/DESIGN/IMPL 同源）≠ 本节复审基座 **GLM-5.3-Flash**。
> **复审对象**: 本文件提交 `c913243` 版本（Step 7 收口）；复审时点 HEAD `a126379`
> **方法**: 机械校验脚本（`%TEMP%\p031_step8_check.py`，独立编写）五项 + 对齐矩阵七项 + §8 交接五项逐条裁决

### 10.1 E1 机械校验五项

| # | 检查项 | 读数 | 结果 |
|---|--------|------|------|
| M1 | 相对链接 | 3 条 / **0 broken** | ✅ |
| M2 | ID 闭环 | 46 行 / 46 唯一 / 无重复；分组 **A6+B8+C6+D6+E8+F12** 与 §7 声称精确一致 | ✅ |
| M3 | 计数一致性 | `46`×10 / `731`×4 / `82`×3 / `119`×4 / `37 files 0`×4 / `13 零重录`×2——全部与正文口径自洽 | ✅ |
| M4 | 零预填合规 | `[待 Step 9]` 机械匹配 **49** = 46 单元格 + 3 合法字面引用（L6 规则行 / §7 计数说明 / 签名表 Step 9 行）；`✅` **2** 次均为规则说明字面引用 | ✅ |
| M5 | 角色引用形态 | 签名表四行齐备；Step 8/9/10 行均为 `[待 Step N]` 占位（本轮回填 Step 8 行） | ✅ |

### 10.2 E2 对齐矩阵七项

| # | 对拍项 | 落点 | 结果 |
|---|--------|------|------|
| A | **9 实例** | IMPL §2（计数口径）×3 / 本文件 F1 + §7 覆盖映射 ×5——V1 1 + V2 1 + V2b 1 + V3 2 + V4 2 + V5 1 + V6 1 = 9 | ✅ 三处一致 |
| B | **4 修 1 降级** | RESEARCH §3（R1-R4 四缺陷）/ DESIGN §1（四行缺陷表 + D2 行）/ IMPL §1（「四处语义修正 + 一处显式降级」）/ 本文件 F10 + A-D 组标题 | ✅ 四处口径一致 |
| C | **6 计数键** | DESIGN D6 / IMPL §2 / 本文件 A3+C2+C3+D3+D4+B3 三文档全含（RESEARCH 无键属预期——缺陷取证文档） | ✅ |
| D | **731/82/119/37 链** | IMPL §1 ↔ 本文件头部 + E8 + F4-F5；基线 722/81/118/37 与 Step 6 §13.3 实测同源 | ✅ 三处一致 |
| E | **V-ID 映射** | DESIGN 契约 V1-V6 ↔ IMPL 用例 V1-V6+**V2b**（唯一新增）；语义 1:1 对齐（V1 退出单 / V2 NAV / V3 夹紧 / V4 在途 / V5 中性 / V6 正常）；本文件锚点列除 B4 外全为用例 ID | ✅（B4 见 F-S8-P031-3） |
| F | **顺序敏感五项** | ① 撤销位置→D1（IMPL §4.2 早退后/daily_signal 前）② 过期位置→D4（F-I-P031-1 切片后）③ 计数位置→A3（optimize 成功后）④ nav 守卫→B3（build_target_positions 前）⑤ B1→B2（IMPL §3 + DESIGN §8）——五项均已在 IMPL 定稿且本文件对应行引用 | ✅ |
| G | **基线-目标读数链** | Step 6 §13.3（722/118/37/81 @4278179）↔ 本文件头部（@6a7771e，代码面一致）↔ 目标 731/82/119/37 | ✅ 无漂移 |

### 10.3 E3 发现分级与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P031-1 | P3 | 本文件 A2/A6 要求「半仓断言」（`target_weights.sum() <= 0.5 + 1e-9` / 买入名义半仓），但 IMPL §5 V5 断言列未列（全文「半仓」仅见于 §1 前提 6 与 §4.1 warning 文案）——规格缺口 | **当轮回写 IMPL §5 V5**：断言补「买入名义 ≈ 0.5 × nav × 0.985（半仓、不重归一化）」 |
| F-S8-P031-2 | P3 | 本文件 E5 引用「AST 扫描 = 22」但 IMPL_p031 无命令定义（grep AST = 0）；P-029 先例命令在 [IMPL_p029 §6](IMPL_p029_silent_exception_governance_phase4.md)（十文件口径） | **当轮回写 IMPL §11**：增补「I1 AST 计数」待回填行（复用 P-029 命令，D1 新增 `except (KeyError, IndexError)` 不计入） |
| F-S8-P031-3 | P3 | 本文件 B4 锚点列「V2 语义」实指 DESIGN 契约 V2（NAV 时序语义），违反 §8.2 自立的「DESIGN 契约引用须标 DESIGN-V*」规则 | **当轮修正**：B4 锚点列改「DESIGN-V2 语义」 |
| 观察 | 3 | O-S8-P031-1：F1 写「函数数 ≤ 7」为估算上限（V3/V4 参数化后实际函数数 5-7 均可），Step 9 实测为准。O-S8-P031-2：A2 证据「`target_weights.sum()`」依赖测试捕获 `target_weights` 的实现方式（monkeypatch `_generate_orders` 或由订单名义反推），IMPL 未钉死实现——与 F-S8-P031-1 回写合并后由 Step 9 自由选择。O-S8-P031-3：本文件头注「与 IMPL §4 锚点基准 `96bed8d` 代码面一致」成立（`96bed8d..6a7771e` 全为 docs-only 提交），无需处置 |

### 10.4 结论与 Step 9 前置条件

**结论**: **pass**（0 P0/P1/P2 / 2 P3 当轮回写 IMPL / 1 P3 当轮修正本文件 / 3 观察）——四文档口径闭环，46 项验收可执行，准予进入 Step 9 TDD。

**Step 9 前置条件**:
1. V5 按回写后断言实现（含半仓名义校验，O-S8-P031-2 的实现方式自由）；
2. §11 回填含「I1 AST 计数」行（F-S8-P031-2 命令源）；
3. 五处顺序敏感核验（10.2-F）逐项留证；V6 红态即绿须显式标注（F2）。

---

## 11. Step 10 ADD 审计 + RULE-5 异构终审（2026-11-16）

> **审计基座**: **GLM-5.3-Flash**（≠ RESEARCH / DESIGN / IMPL / CHECKLIST 四文档作者 DeepSeek-V4.1-Flash）→ **RULE-5 异构条件天然成立**，ADD 审计与异构终审**合并为一轮**（同 P-029 先例）。
> **方法**: Phase 0 spec 质量门 → Phase 1 完整性盘点 → Phase 2 保真度比对（IMPL §4 独立读码）→ Phase 3 必要性（diff 逐 hunk 归因）→ Phase 4 语义/生命周期 → E1-E5 门禁独立复跑 + 盲区扫描；不采信任何未经本基座复现的读数。
> **审计对象**: 区间 `6a7771e..780197c`（**6 提交**：`c913243` / `a126379` / `3c2e3de` / `6eb016d` / `750674e` / `780197c`；代码面集中于 `750674e`）；审计时点 HEAD `780197c`；Python312 + `MPLBACKEND=Agg`。

### 11.1 Phase 0 spec 质量门（DESIGN_p031）

| 维度 | 得分 | 依据 |
|------|------|------|
| 可测试约束 | 1 | V1-V6+V2b 每条断言可机械判定（V2 恰 1 笔 / V3 cash 恰 +1,000 / V4① 域外保留 / V5 半仓 notional rel 0.02 / V6 6 键全 0）；6 计数键语义各自明确 |
| 模块映射 | 1 | D1→§4.4+4.5 / D2→§4.1+4.3+4.9 / D3→§4.6-4.8 / D4→§4.2+4.7① / D5 无代码（§7 排除 #2）/ D6 出口表 / D7 零改动面——全 1:1 |
| 接口契约 | 1 | IMPL §8 签名回退表 9 函数 + 6 键 snake_case 命名 + `additional_info.neutral_short_leg` 二值枚举，均签名级明确 |
| 修正项 | 1 | F-S2-P031-1/2 + F-S4-P031-1~4 + F-I-P031-1~7 + F-S6-P031-1 + F-S8-P031-1~3 + F-S9-P031-1~3 全枚举且各有回写落点 |
| 跨模块契约 | 1 | I1-I8 不变式 + U-P031-1~4 + O-P031-1~3 + D7 九面零改动清单（core / golden / filter / scripts / cli / pyproject 等） |
| **合计** | **5/5 = Tier A** | 无 B 档封顶 |

### 11.2 Phase 1 完整性盘点

| 设计元素 | 应有 | 实测 | 证据 |
|----------|------|------|------|
| 审计区间形态 | 6 提交 | **6** | `git log --oneline 6a7771e..780197c` 逐条列出（4 docs-only + 1 代码 + 1 docs 回填） |
| 全区间 diff | 8 文件 +714/−98 | **8 文件 +714/−98** | `git diff --numstat` 逐文件；构成 = 1 代码 + 1 测试 + 6 文档 |
| 代码 numstat | — | `agents/multi_strategy_engine.py` **+133/−83** / 测试 **+272** | 逐文件实测；+272 与 IMPL §11.2 的偏差见 F-R5-P031-1 |
| 6 计数键 | 6 键 8 站点 | **6 键 / 8 站点** | blocked ×2 / trimmed ×2 / cancelled ×1 / expired ×1 / skipped ×1 / nav_invalid ×1，逐行命中 |
| 新增日志 | 1 条 init warning | **+1** | 区间 diff `^[+-].*logger\.` 仅 `+logger.warning(`（D6 口径） |
| 新增 raise | 0 | **0** | 区间 diff `^\+.*\braise\b` 零命中（I2 零 fail-fast） |
| 零改动面 | core / golden / filter / scripts / cli / pyproject | **零命中** | 区间 8 文件名单不含上述任何面；`git status --short core tests/golden` 空 |
| 出口 | `additional_info.neutral_short_leg` | **1** | `_generate_results` L547-551（多策略两循环直调面覆盖） |

### 11.3 Phase 2 保真度（对照 IMPL §4，独立读码九函数）

| 锚点 | 结论 | 证据 |
|------|------|------|
| §4.1 `__init__` warning | **pass** | L113-117：仅 `direction == "both"` 分支，文案含 `unsupported`，签名零变更（V5 断言 1 条 / long 0 条） |
| §4.2 双载体撤销 | **pass** | L217-232：位置在信号索引早退（L214-215）之后、`daily_signal`（L235）之前；`_next_day_orders` keep/drop + `pending_queue.cancel_orders`；`if dropped:` 计次数；queue 侧零新键 |
| §4.3 中性腿禁用 | **pass** | `short_optimizer` 零残留（grep 0）；`neutral_short_leg_skipped` 在 optimize（L311）成功之后、try 内（L314）；`long_weights * long_weight` 无重归一化（L315）；`except Exception` + `neutral_optimize` 结构逐字保留（P-027 契约） |
| §4.4 `_generate_orders` | **pass** | 统一价格切片 try（L328-332，typed `except (KeyError, IndexError)`）→ current 仅 qty>0 → `compute_portfolio_value`（L341-346）→ nav 守卫（L347-349）**先于** `build_target_positions`（L352）；`value_buffer` 未传（默认 0.985） |
| §4.5 `_generate_rebalance_orders` | **pass** | 签名 `dict[str, TargetPosition]`（L361）；先 SELL（L365-368）后 BUY（L370-373）两轮；routing 双路径保持（L375-379） |
| §4.6 `_clamp_sell_quantity` | **pass** | L385-394 与规格逐字一致；BUY 早退；无持仓返回 0 |
| §4.7 次日路径 | **pass** | 空队列早退（L398-399）→ 开盘价切片（L401-405，P-029 S6 保留）→ **过期过滤在切片后**（L407-421，F-I-P031-1）→ mask → 夹紧（L455-461，blocked 丢弃 / trimmed）→ `execute_order(..., qty, ...)`；`mark_expired` 零状态迁移（O-S6-P031-2） |
| §4.8 队列路径 | **pass** | 夹紧同形（L511-518）+ blocked 调 `cancel_order`（L515）+ 直调 `execute_order(..., qty, ..., close_price)`（L520-522，F-I-P031-2）；`mark_executed` 对原订单对象（L526）；`mark_expired` 保留（L528） |
| §4.9 `_generate_results` | **pass** | L547-551：`"unsupported"`（both）/ `"not_applicable"`（long/short） |
| 签名零变更 | **pass** | 区间 diff `^-\s*def ` 唯一 `_generate_rebalance_orders`（私有，IMPL §8 允许项）；公开三方法零删改 |
| 行号漂移 | **pass** | §11.3 漂移表 11 项 vs 实测 def 行号逐项复核全命中（L74/L155/L212/L282/L325/L361/L385/L396/L478/L530/L130） |

### 11.4 Phase 3 必要性（diff 逐 hunk 归因）

区间代码 diff 共 **11 hunk**，逐一归因 IMPL §4 / D1-D7，**零游离行**：

| hunk（旧→新） | 归因 |
|---------------|------|
| -31,9 +31,14 | 导入区（`PendingOrder` + `target_positions` 三名，B1 验收项） |
| -110,6 +115,12 | D2 §4.1 init warning |
| -203,6 +214,23 | D4 §4.2 双载体撤销（+17 行） |
| -256,7 +284,8 / -268,16 +297,6 / -290,16 +309,10 | D2 §4.3（docstring + `short_optimizer` 删除 + 权重替换） |
| -310,77 +323,76 | D1 §4.4-4.5 + D3 §4.6（`_generate_orders` 整函数替换 + 目标持仓路由 + `_clamp_sell_quantity` 新增，净 −1 行） |
| -392,6 +404,22 | D4 §4.7① 过期过滤（+16 行） |
| -424,8 +452,16 | D3 §4.7②③ 次日夹紧（+8 行） |
| -472,8 +508,17 | D3 §4.8 队列夹紧（+9 行） |
| -499,6 +544,11 | D2 §4.9 `additional_info`（+5 行） |

### 11.5 Phase 4 语义/生命周期

| 面 | 裁决 |
|----|------|
| 超卖生命周期 | 生成侧（D1 目标持仓）SELL 量 ≤ 持仓，天然不可超卖；执行侧夹紧兜底**陈旧单**（前日簿/注入单）——纵深防御成立；blocked 次日路径丢弃（P-014 V2 同款）、队列路径 `cancel_order` 状态迁移，两差异均有裁决 |
| 撤销生命周期 | 撤销先于当日新单生成（同函数内 L217 < L322/323 生成点），无自撤销；域外保留与 V2 L911-917 同口径；queue 载体经 `cancel_orders(stock, date)` 内置 `logger.info` 事件 |
| 过期生命周期 | 复用 `is_expired`（自然日 + 半衰期 3，BUY 5 / SELL 10）；过期单仅从簿丢弃、无状态迁移（agents 本地簿无 status 消费者，O-S6-P031-2 零账目影响）；退化日（整日无开盘价）推迟一天过期，有界且不可观测（F-I-P031-1） |
| NAV 时序 | `compute_portfolio_value` 消费当日收盘价切片，消除「开盘成交后 get_total_value 不可信」窗口；守卫拦截 nan/±inf/0/负（Step 6 E3 探针实证），不抛 `ValueError` 入无 try 循环 |
| 中性降级语义 | 半仓多头 + 半仓现金 + 双重披露（warning / 计数 / `additional_info`）；`short` 方向维持现状（U-P031-3）；`neutral_short_leg_skipped` 仅在 tradable 非空时可达（L246-248 早退在前） |

### 11.6 E1-E5 门禁独立复跑（本基座全量重跑，不采信 Step 9 自报）

| 门禁 | 目标 | 实测 |
|------|------|------|
| 全量 pytest | 731 | ✅ **731 passed**（172 warnings，43.66s） |
| 新测试收集 | 9 实例 | ✅ **9 tests collected**（`^def test_` = 8，V3 参数化 +1） |
| black `--check core tests` | 119 | ✅ **119 files would be left unchanged** |
| mypy `--explicit-package-bases core` | 37 files 0 | ✅ **Success: no issues found in 37 source files** |
| golden + P-027 + P-029 回归面 | 48 | ✅ **48 passed, 683 deselected**（13+24+11 口径精确） |
| `tests/` .py 数 | 82 | ✅ **82** |
| I1 AST `except Exception`（十文件命令） | 恒 22 | ✅ **22** |
| 零改动面 | 空 | ✅ `git status --short core tests/golden` 空 |
| CI（Step 9 两跑） | success | ✅ run `43864133531` + `43864567650` 各三 job success |

### 11.7 盲区扫描（独立 AST 脚本 `%TEMP%\p031_step10_blindspot.py`）

- **读数**：`agents/` ExceptHandler **handlers=22**；严格启发（body 无 `_record_failure` / 无 `logger.` / 无 `raise`）命中 **2** 处——`research_team_v2.py:27`（P-029 登记点：可选依赖显式降级）与 `agent_framework.py:1543`（`demo_multi_agent_backtest()` 入口 `except Exception: print(e) + traceback.print_exc()`——stdout 可观测，且属 **P-027 登记零改动面** `agent_framework.py:1529`，行号因 P-029 S3b/S4 上方 +14 行漂移至 :1543）。
- **对账**：P-029 §11.6 的「silent=1」读数依赖其脚本定义（排除已登记点）；本基座严格启发下两点均浮出，**均早于 P-031 且均已登记**（O-R5-P031-2 观察），非本批引入。
- **P-031 新增面**：D1 的 typed `except (KeyError, IndexError)` 不计入 I1（非 Name Exception）；全部 6 新计数站点均带 `_record_failure`——**零新增静默路径**。

### 11.8 发现分级与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-R5-P031-1 | P3 | IMPL §11.2 门禁表「新测试文件 **+270**（未计入 numstat 因未跟踪）」与提交后实测不符——区间 numstat 实测 **+272**，且提交后该文件已计入 numstat、原注记前提失效（+270 为 Step 9 B5 期间提交前手工估算） | **当轮修正**：IMPL §11.2 该单元格改 +272 并注明修正来源 |
| O-R5-P031-1 | 观察 | PROGRESS §3.36.8「≈270 行」为约数（实际 272）——历史记录不回改，以本表为准 | 不改 |
| O-R5-P031-2 | 观察 | 盲区扫描严格启发下 agents/ silent=2（见 11.7）——P-029「silent=1」为定义依赖读数；两点均早于本批且已登记（P-027 零改动面 / P-029 O-S10-P029-1），P-031 零新增静默 | 不改（登记对账） |

### 11.9 结论

**结论**: **pass**（Phase 0 **5/5 Tier A** + Phase 1-4 全过 + E1-E5 门禁独立复跑全绿 + 盲区零新增；**0 P0/P1/P2 + 1 P3 当轮修正 + 2 观察**）——DESIGN D1-D7 / IMPL §4 与提交代码**语义与文本双闭环**，四项缺陷修复忠实落地且零改动面零越界，**P-031 批次关闭**。未决项 U-P031-1~4 与观察 O-P031-1~3 随批次归档，触发条件不变。
