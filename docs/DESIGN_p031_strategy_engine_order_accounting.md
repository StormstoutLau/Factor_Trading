# DESIGN：P-031 `StrategyEngine` 订单簿与估值时序

> **批次**: P-031 · **T1**（`agents/multi_strategy_engine.py` 单文件 + 新增账目测试）
> **状态**: **Step 3 完成**（2026-11-16，基线 HEAD `bf4a71b`）
> **作者基座**: DeepSeek-V4.1-Flash（= RESEARCH 作者；Step 4 复审须异构）
> **上游**: [RESEARCH_p031](RESEARCH_p031_strategy_engine_order_accounting.md)（§3 R1-R4 + §11 Step 2 复审，含 F-S2-P031-1/2 当轮回写）
> **设计对象**: 仅 `agents/multi_strategy_engine.py` 的 `StrategyEngine`；`core/` 零改动

---

## 1. 设计目标

把 `StrategyEngine` 的**估值**与**订单簿**语义对齐到 `core/` 已有的正确实现，在**不修改 `core/`**、**不破坏 golden**、**不新增静默失败**的前提下修掉四项缺陷：

| 缺陷 | 级别 | 设计出口 |
|------|------|----------|
| R2 目标外持仓不生成卖出单 | P1 | **D1**：目标持仓改用 `build_target_positions`（并集含清仓项） |
| R4 超卖成交入账 → 现金虚增 | P1 | **D3**：执行侧卖量夹紧（不改 tracker） |
| R1 再平衡 NAV 漏计当日成交 | P2 | **D1**：估值改用 `compute_portfolio_value`（价格重算） |
| R3 在途单无过期/无撤销 | P2 | **D4**：再平衡撤销 + 复用 `is_expired` |
| F-S2-P031-1 M-A 负权重不兼容 | P2 | **D2**：中性空头腿显式禁用（多头-only 权重） |
| O1 空头市值不更新 | 观察 | **D5**：不并入（前提不可达），登记 |

**约束**：`core/` 零改动；`tests/golden/*.json` 零改动；`except Exception` 合计恒 22；既有公开签名零变更。

---

## 2. 调研结论 → 设计映射

| RESEARCH | 设计落点 | 落点依据 |
|----------|----------|----------|
| R2 + R1（估值/目标持仓） | **D1** + §4.1 | V2 已验证 `compute_portfolio_value` + `build_target_positions`（engine_v2 L953-990） |
| R4（幻影现金） | **D3** + §4.2 | P-014 的 `_clamp_sell_quantity`（engine_v2 L671） |
| R3（队列无界） | **D4** + §4.3 | P-014 的 `_cancel_next_day_orders`（L690）+ `PendingOrder.is_expired` |
| F-S2-P031-1（负权重） | **D2** + §4.4 | N2 实证 `build_target_positions` 抛 `ValueError` |
| F-S2-P031-2（中性常态触发） | **D2** + §4.4 | N1 实证 cash 10M → 90M |
| O1 / `direction="short"` 语义 | **D5** §7 | 前提不可达 / 产品定义未定 |
| 双路径调用（`_process_trading_day` 与多策略自建循环） | **D6** §4.5 | L726-740 / L84x 直接调用被调函数 |

---

## 3. 决策详述

### D1（修 R1 + R2）：目标持仓走 `core/target_positions.py`

**决策**：`_generate_orders` 不再自行遍历 `target_weights`，改为「价格重算 NAV → 目标持仓并集 → 卖出先行/买入随后」。

```
prices = dm.get_adj_price("close", adjustment_type).loc[date]     # 失败 → orders_missing_price
positions = tracker.get_all_positions()
current   = {s: int(p.quantity) for s, p in positions.items() if int(p.quantity) > 0}
nav       = compute_portfolio_value(tracker.get_cash(), current, prices,
                                    {s: p.market_value for s, p in positions.items()})
targets   = build_target_positions(target_weights, current, prices, nav,
                                   round_lot=base_cfg.optimizer.round_lot)   # value_buffer=0.985 默认
# 先 SELL（含 is_exit 清仓与减仓），后 BUY
```

**理由**：
- `compute_portfolio_value` 的 docstring 已明载「开盘成交后、日终盯市前 `get_total_value()` 不可信」，与 R1 根因逐字对应；
- `build_target_positions` 的并集语义（`current_positions` ∪ `target_weights`）直接消除 R2，且 `is_exit=True` 条目在价格缺失时仍可清仓（由次日开盘价成交）。

**裁决 #3（`value_buffer=0.985`）**：**沿用默认 0.985**。与 V2 单一语义对齐；代价是买入量较原实现降 1.5%，属可解释的口径统一，不是漂移。`round_lot` 沿用 `base_cfg.optimizer.round_lot`（原实现固定按 100 股取整，改为跟随配置；默认值为 `True`，行为一致）。

**保留既有计量**：价格切片失败仍记 `orders_missing_price`（P-029 S5 键），不新增键。

### D2（修 F-S2-P031-1 / F-S2-P031-2）：中性策略空头腿显式禁用

**背景**：当前账目模型（`Position.quantity` 可为负但 `update_market_values` 只更新 `quantity > 0`，且 executor 无持仓/保证金校验）**无法表达可结算的空头**。N1 已证：空头腿每再平衡都产生一次「无持仓 SELL → 现金入账 → 持仓钳制 0」的幻影现金。

**备选与裁决**：

| 方案 | 后果 | 裁决 |
|------|------|------|
| A. 实现完整做空（负持仓 + 保证金 + 负市值盯市） | 需改 `core/tracker.py` 与 `core/execution.py`，波及 V2/V3/golden | **超出 T1，拒绝**（登记 U-P031-1） |
| B. `__init__` 对 `direction="both"` fail-fast | 诚实但会连带使 `MultiStrategyEngine`（固定构造 long/short/both 三腿）整体不可用 | **拒绝**（修复账目的批次不应打断 long/short 可用性） |
| C. 空头腿**不生成订单** + 显式可观测（warning + 计数 + 结果字段） | 中性策略退化为「多头腿单边」，但账目正确、无幻影现金、用户可见 | **采纳** |
| D. 生成订单后由执行层夹紧 | 仍会走一遍「作废/夹紧」路径，且中性语义依旧不可用 | 拒绝（多绕一层，收益为零） |

**落点**：
- `_execute_neutral_rebalance`：只合并多头腿（`long_weights * long_weight`），**不合并** `short_weights`；每跳过一次计 `neutral_short_leg_skipped`。
- `__init__`：`strategy_cfg.direction == "both"` 时打一次 `logger.warning`（文案含「空头腿不支持」与「结果标记 neutral_short_leg=unsupported」）。
- `_generate_results()`：结果追加 `additional_info: {"neutral_short_leg": "unsupported" | "not_applicable"}`。选择写进 `_generate_results` 而非 `run()`，因为 `MultiStrategyEngine` 的两条循环（L786 / L928）直接调用 `_generate_results()` 而不走 `run()`。

**已知边界（必须如实披露）**：中性策略在本批后**不再是市场中性**，而是「多头腿 + 空头腿禁用」。`MultiStrategyEngine` 的三腿组合因此实际为 2.5 腿（long / short-as-buy-low / neutral-long-only）。DESIGN 不掩饰这一点，登记 **U-P031-1**（负持仓账目模型）与 **U-P031-3**（`direction="short"` 语义）。

### D3（修 R4）：执行侧卖量夹紧，`core/tracker.py` 零改动

**裁决 #2（修复位置）**：**执行侧夹紧**，不改 tracker 现金入账。

| 位置 | 评估 | 裁决 |
|------|------|------|
| `core/execution.py::execute_order` | 纯模拟器，无持仓视图；加持仓校验需注入 tracker，破坏无状态契约 | 拒绝 |
| `core/tracker.py::execute_trade` | 全局账目收口，改它能一次覆盖所有引擎；但被 V2/V3/golden 共用，任何现金语义变化都可能影响 13 条 golden 基线 | **拒绝（本批）**；登记 O-P031-1 |
| `StrategyEngine._execute_next_day_orders` | 与 P-014 同一层次；V2 已有同类实现（`_clamp_sell_quantity`）；改动只在 agents 单文件 | **采纳** |

**落点**（`_execute_next_day_orders` 循环内，`execute_order` 之前）：
```
if order.side == SELL:
    held = max(int(position.quantity), 0) if position else 0
    qty  = min(order.quantity, held)
    if qty <= 0:      _record_failure("oversell_blocked"); continue
    elif qty < order.quantity:
                      _record_failure("oversell_trimmed")
                      order = create_pending_order(stock, SELL, qty, order.create_date)
```
**BUY 侧不做现金夹紧**（与 U-P014-3 同列，登记 U-P031-2）。

### D4（修 R3）：在途单撤销 + 过期

**落点 1｜再平衡撤销**：`_execute_rebalance` 在「日期不在信号索引」早退之后、`tradable_stocks` 计算之前，撤销信号域内在途单：
```
domain = set(self._composite_signal.columns)
keep, drop = [], []
for item in self._next_day_orders:
    (keep if item["order"].stock not in domain else drop).append(item)
self._next_day_orders = keep
if drop: self._record_failure("next_day_orders_cancelled")   # 计数为「发生次数」而非单数
```
域外在途单保留（与 V2 L913-917 的 `set(signal_df.columns)` 同口径）。

**落点 2｜过期**：`_execute_next_day_orders` 入口（空队列早退之后）：
```
max_days = cfg.max_pending_days_sell if side==SELL else cfg.max_pending_days_buy
if order.is_expired(date, max_days): _record_failure("next_day_orders_expired"); drop
```
复用 `PendingOrder.is_expired`（含半衰期语义），阈值取 `base_cfg.max_pending_days_buy=5` / `max_pending_days_sell=10`（[config.py L376-377](../core/config.py#L376-L377)）。**注意**：`is_expired` 用**自然日**且含半衰期（约 9 自然日即失效），与 V2/P-014 完全同源，本批不改该函数。

**为什么必须落在被调函数内部（D6）**：`_execute_next_day_orders` 有两条调用路径——`_process_trading_day`（L177-178）与 `MultiStrategyEngine` 两条自建循环（L726-740 / L84x）。只在 `_process_trading_day` 打补丁会漏掉多策略路径。

### D5（裁决 #4）：O1 与 `direction="short"` 不并入本批

- **O1**：N1 证实空头腿持仓被钳制在 0 → 「空头市值不盯市」的**前提不可达**；真正的病是幻影现金（D3 已修）。不改 `core/tracker.py`，登记 O-P031-1（若未来实现负持仓，须同时改盯市条件）。
- **`direction="short"`**：`select_top=False` 产正权重 → 买低分股，属产品语义未定义（模块 docstring 两义），本批保持现状，登记 U-P031-3。

### D6（可观测出口）

| 出口 | 位置 | 形态 |
|------|------|------|
| `additional_info.neutral_short_leg` | `_generate_results()` | `"unsupported"`（both）/ `"not_applicable"`（long/short） |
| 5 个新计数键 | `_failure_counts`（既有出口 `run()["failure_counts"]`） | `oversell_blocked` / `oversell_trimmed` / `next_day_orders_cancelled` / `next_day_orders_expired` / `neutral_short_leg_skipped` |
| 中性 warning | `__init__` | 一次，文案含 `direction="both"` 与 `unsupported` |

**零新增日志级别**（仅一条初始化 warning）；不新增 `except` 分支。

### D7（范围与零改动面）

| 面 | 状态 |
|----|------|
| `agents/multi_strategy_engine.py` | **唯一代码变更文件** |
| `core/target_positions.py` | **只读复用**（不改） |
| `core/tracker.py` / `core/execution.py` / `core/pending.py` | **零改动** |
| `tests/golden/*.json` | **零改动、零重录** |
| `filter/` / `scripts/` / `cli.py` / `pyproject.toml` | 零改动 |
| 新增测试 | `tests/test_p031_strategy_engine_accounting.py` |

---

## 4. 实现规格（逐函数）

### 4.1 `_generate_orders(date, date_index, target_weights)`
1. 价格切片：`try: prices = dm.get_adj_price("close", adj).loc[date] except (KeyError, IndexError): _record_failure("orders_missing_price"); return`
2. 组装 `current` / `nav` / `targets`（D1 代码块）。
3. 生成订单：先 SELL 后 BUY（与 V2 L1063-1073 同序），经 `_execute_order_next_open` 或 `pending_queue.add_order`（保持两只路径）。
4. 删除原「逐 weight 计算 target_quantity」的内联逻辑与 `orders_missing_price` 的逐股分支（价格切片失败已在入口统一处理）。

### 4.2 `_execute_next_day_orders(date, date_index)`
1. 空队列早退（不变）。
2. **过期过滤**（D4 落点 2，新增）。
3. 开盘价切片失败仍 `_record_failure("next_day_open_price")` + `return`（P-029 S6 保留）。
4. 循环内：mask → 价格存在性/有效性 → **SELL 夹紧**（D3）→ `execute_order`。
5. `self._next_day_orders = failed_orders`（不变）。

### 4.3 `_execute_rebalance(date, date_index)`
1. 日期不在信号索引 → return（不变）。
2. **撤销信号域在途单**（D4 落点 1，新增）。
3. 其余流程不变。

### 4.4 `_execute_neutral_rebalance(date, date_index, tradable_stocks)`
1. 保留 `long_optimizer` 计算。
2. `short_optimizer` 的调用**保留但结果不使用**？→ **删除**（无消费者的计算是死代码），改为 `_record_failure("neutral_short_leg_skipped")` 一次 + 仅合并多头腿。
3. `target_weights = long_weights * strategy_cfg.long_weight`（非负）。

### 4.5 `_generate_results()`
追加 `"additional_info": {"neutral_short_leg": ...}`；其余键不变。

### 4.6 `__init__`
`direction == "both"` 时一条 `logger.warning`（不改签名、不抛错）。

---

## 5. 不变式 I1-I8

| ID | 不变式 | 验证出口 |
|----|--------|----------|
| I1 | 目标外持仓（有持仓且可定价）必产生 SELL 清仓单 | V1 |
| I2 | 现金守恒：`cash` 变化 = Σ成交净额；无持仓 SELL 不成交、不入账 | V3 |
| I3 | 再平衡 NAV 以价格重算：`daily` + 恒定目标 → 零换手（成交笔数 ≤ 标的数） | V2 |
| I4 | 在途单有界：每次再平衡后信号域内仅含本次新单；过期上限 buy 5 / sell 10（自然日，含半衰期） | V4 |
| I5 | 既有公开签名零变更（`StrategyEngine.__init__` / `run` / `get_failure_stats`）；`except Exception` 合计恒 22 | E3 |
| I6 | `core/` 与 `tests/golden/*.json` 零改动 | E2 |
| I7 | 中性空头腿显式：`warning` + `neutral_short_leg_skipped` + `additional_info.neutral_short_leg`，无静默 | V5 |
| I8 | 门禁：722 + 新增 passed / mypy 37 files 0 / black 118+1 | §6 |

---

## 6. 验证契约 V1-V6

| ID | 用例 | 断言 |
|----|------|------|
| V1 | 退出单 | 持仓 A=1000，`target_weights` 仅 B → 队列含 `SELL A 1000`；执行后 A=0、B>0 |
| V2 | NAV 时序 | 1 股、常量价、`daily`、恒定 100% → **成交 1 笔**（旧实现 9 笔）；每步 `cash + Σqty×price` 守恒 |
| V3 | 超卖夹紧 | 100 股 + 3×SELL 100 → 成交 **1 笔 100 股**；cash **+1,000**；`oversell_blocked == 2` |
| V4 | 在途单 | 开盘缺失 6 日 → 队列长度恒 **≤1**（撤销生效）；恢复日成交 1 笔；`next_day_orders_cancelled/expired` 计数 > 0 |
| V5 | 中性 | `both` → **无 SELL 成交**；`neutral_short_leg_skipped > 0`；`additional_info.neutral_short_leg == "unsupported"` |
| V6 | 正常路径 | 常规多头调仓 → 5 个新计数全 0；`orders_missing_price` / `next_day_open_price` 既有键零误报 |

**红态纪律**：B1→B4 逐批先红后绿，红态读数记入 IMPL §11；V6 在红态即通过属预期（回归保护），须标注。

---

## 7. 风险、未决与观察

| ID | 类型 | 内容 | 处置 |
|----|------|------|------|
| R-P031-1 | 风险 | 0.985 缓冲 + `round_lot` 跟随配置 → 目标股数与原实现有系统性差异 | 接受（对齐 V2）；IMPL 记录首日目标股数对照 |
| R-P031-2 | 风险 | 先卖后买改变同开盘的现金序 | 与 V2 一致；IMPL 说明「无资金校验队列下先卖可避免负现金」 |
| R-P031-3 | 风险 | 撤销仅限信号域，域外在途单保留 | 与 V2 同口径；V4 断言域内 |
| R-P031-4 | 风险 | `is_expired` 含半衰期（自然日）→ sell 单实际约 9 日失效而非 10 日 | 既有语义，不改；文档披露 |
| U-P031-1 | 未决 | 中性策略负持仓账目模型（保证金/借券/负市值盯市） | 登记；触发：需要真正市场中性 |
| U-P031-2 | 未决 | BUY 侧现金夹紧 | 登记（与 U-P014-3 同列） |
| U-P031-3 | 未决 | `direction="short"` 语义（买低分 vs 真做空） | 登记；DESIGN 不裁决产品定义 |
| O-P031-1 | 观察 | `core/tracker.py` 现金入账守卫（全局收口） | 不改；若未来多引擎复现幻影现金再评估 |
| O-P031-2 | 观察 | `MultiStrategyEngine` L918 直接改写 `tracker.cash`（动态资金分配） | 超出本批；登记 |
| O-P031-3 | 观察 | README 示例调用不存在的 `register_agent` | 候选 T3 文档批（O-S2-P031-3 承接） |

---

## 8. 批量切分与回退点

| 批 | 内容 | 修复 | 回退 |
|----|------|------|------|
| **B1** | D2 中性空头腿禁用（前置，保 `build_target_positions` 非负前提） | F-S2-P031-1/2 | 单函数回退 |
| **B2** | D1 目标持仓推导（`compute_portfolio_value` + `build_target_positions`） | R1 + R2 | 单函数回退 |
| **B3** | D3 执行侧卖量夹紧 | R4 | 单函数回退 |
| **B4** | D4 撤销 + 过期 | R3 | 单函数回退 |
| **B5** | 门禁 + 文档回填（IMPL/CHECKLIST/PROGRESS/CHANGELOG） | — | docs |

B1 必须先于 B2（否则 `direction="both"` 在 B2 后首日抛 `ValueError`）；B3/B4 相互独立。

---

## 9. 设计期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-D3-P031-1 | P3 | `_execute_next_day_orders` 存在**双调用路径**（`_process_trading_day` L177 与多策略自建循环 L726-740 / L84x）——若只在 `_process_trading_day` 加撤销/过期，多策略路径漏修 | 设计已内化为 D4/D6：修复落在**被调函数内部**，不依赖调用方 |
| F-D3-P031-2 | 观察 | `run()` 结束后 `_next_day_orders` 可能残留未成交单（`pending_queue.mark_expired` 只清队列路径，L163-165） | 本批不做终态清仓（未成交即回测结束，保持既有语义）；残单可通过 `failure_counts` 间接观察，登记不改 |
| F-D3-P031-3 | 观察 | `MultiStrategyEngine` L918 直接写 `tracker.cash` 做动态资金分配，与 D1 的价格重算 NAV 叠加时行为未取证 | 登记 O-P031-2；V2 无此路径，不影响 golden |

---

## 10. 下一 Step

**Step 4 独立 Review（异构基座）**——本文件作者 DeepSeek-V4.1-Flash，须由非作者基座复核。复核重点：

1. D2 的「空头腿禁用」是否是可接受的最小诚实解（对比 fail-fast / 完整做空的权衡）；
2. D3 拒绝改 `core/tracker.py` 的理由是否成立（golden 零重录是否真的会被破坏，需实证风险面）；
3. D1 的 `value_buffer=0.985` + `round_lot` 跟随配置是否构成未披露的口径变更（V2 与 agents 的目标股数会不同，是否允许）；
4. D4 撤销范围（信号域）与 `is_expired` 半衰期语义在 agents 引擎的适用性；
5. B1→B2 的强制顺序是否成立（B2 单独回退是否会崩中性路径）；
6. 5 个新计数键的命名与出口是否与 P-029 口径一致（`_record_failure` 键风格）。
