# RESEARCH：P-031 `StrategyEngine` 订单簿与估值时序

> **批次**: P-031 · **T1**（`agents/multi_strategy_engine.py` 单文件 + 新增账目测试）
> **状态**: **Step 1 完成**（2026-11-16，HEAD `2f5a6e0`，Python312 + `MPLBACKEND=Agg`）
> **上游**: [U-P029-2](../docs/PROGRESS.md)（P-029 §8 登记）→ P-030 待办分析核出代码级缺口 → 用户 2026-11-16 裁决「立项 P-031 全量」
> **探针**: `%TEMP%\p031_step1_probe.py` / `probe2.py` / `probe3.py`（仓库外，复用 `tests/_synth_fixture.py`）

---

## 0. 结论摘要（TL;DR）

`StrategyEngine` 的**估值时序**与**订单簿生命周期**存在四项缺陷，其中两项在默认配置下即触发：

| ID | 缺陷 | 级别 | 默认配置是否触发 |
|----|------|------|------------------|
| R2 | 目标外持仓**不生成卖出单** → 标的被剔除后永久滞留 | **P1** | **是**（`optimizer=equal_weight`） |
| R4 | 超卖成交仍入账 → **现金虚增**、持仓被静默钳制 | **P1** | 多头：需超卖单；**中性（both）：常态触发**（Step 2 N1 实证 8 日 cash 10M → 90M） |
| R1 | 再平衡时刻 NAV 漏计当日新成交持仓 → **自激换手** | **P2** | 否（需 `frequency="daily"`） |
| R3 | `_next_day_orders` 无过期 / 无撤销 → **失败单重复累积** | **P2** | 是（需价格缺失/不可成交） |
| O1 | `update_market_values` 只更新 `quantity > 0` → 空头市值恒 0 | 观察 | `direction="both"` 时 |

**关键背景**：`core/` 侧已存在全部四项的参考实现——[target_positions.py](../core/target_positions.py)（`compute_portfolio_value` / `build_target_positions`）与 [engine_v2.py](../core/engine_v2.py)（P-014 的 `_clamp_sell_quantity` / `_cancel_next_day_orders` / `is_expired`）。`StrategyEngine` 是 3 个 `StrategyEngine` 实例的宿主 `MultiStrategyEngine` 的组成部分，但**从未对齐**这些语义，且**零账目测试覆盖**。

**推荐路线 M-A**：将 `StrategyEngine` 的估值与订单生成改为复用 `core/target_positions.py` 的两个函数，执行侧补齐 P-014 的两道防线。行为变更集中在 `agents/` 单文件，golden 不涉及。

---

## 1. 触发与范围

### 1.1 触发

- P-029 的 S6/S7 计量落地时，按「`return` 语义零变更」纪律登记 **U-P029-2**（`_next_day_orders` 的重试语义）。
- 2026-11-16 P-030 待办分析发现：P-014 为 `core/engine_v2.py` 建立的三层防线（卖量夹紧 / 再平衡撤销 / 订单过期）**未下沉**至 `agents/`，且 `agents/multi_strategy_engine.py` 的 `_next_day_orders` 仅追加（L382）与回写失败单（L437），无任何上限。
- 用户裁决：立项 **P-031 全量**（R1-R4 全部纳入，O1 登记）。

### 1.2 范围

| 在范围 | 说明 |
|--------|------|
| `agents/multi_strategy_engine.py::StrategyEngine` | 估值、目标持仓推导、订单生成、次日执行、现金账目 |
| 新增 `tests/test_p031_*.py` | 四项缺陷各一组红绿 |

| 不在范围 | 理由 |
|----------|------|
| `core/` | V2 已有正确实现（§9 负向发现），不做任何改动 |
| `MultiStrategyEngine` 的并行编排 | 仅受 `StrategyEngine` 缺陷传导，本身无独立缺陷 |
| O1（空头市值） | 需先确认 `direction="both"` 的实际使用面，登记观察 |

---

## 2. 调用链与时序

`StrategyEngine._process_trading_day`（[L174-199](../agents/multi_strategy_engine.py#L174-L199)）：

```
1. _execute_next_day_orders(date)      # 以当日开盘价执行队列
2. _process_pending_orders(date)       # enable_pending_orders=True 时
3. trigger.should_trigger(...)         # 用 tracker.get_total_value()
4. _execute_rebalance(date)            # 优化 → _generate_orders → 追加队列
5. tracker.update_market_values(date)  # 收盘价盯市 + 快照
```

**第 1 步与第 3/4 步的顺序是本批两个 P1 缺陷的共同背景**：开盘成交后、日终盯市前，新建仓位的 `market_value` 仍为 0。

`_generate_orders`（[L312-354](../agents/multi_strategy_engine.py#L312-L354)）：

```
current_value = tracker.get_total_value()          # ← R1 的取值点
for stock, weight in target_weights.items():       # ← R2 的遍历面
    target_value = weight * current_value
    ... target_quantity = int(abs(target_value / close)) ...
    trade_qty = target_quantity - current_quantity
```

---

## 3. 缺陷清单

### R2（P1）目标外持仓不生成卖出单

**位置**：`_generate_orders` 仅遍历 `target_weights.items()`（[L320](../agents/multi_strategy_engine.py#L320)）；`EqualWeightOptimizer.optimize` 只返回**入选标的**（[portfolio.py L184](../core/portfolio.py#L184)），不返回 0 权重。二者组合导致：已持仓但未入选的标的**永远不会被卖出**。

**读数（C1，组件级）**：
```
注入持仓 000001 = 1000 股
调用 _generate_orders(date, 1, pd.Series({"600000": 1.0}))
  [READ] 生成队列 = ['2024-01-03:BUY:600000:1000000']
  [READ] 000001 卖出单数 = 0（期望 1 张清仓单）
```

**默认触发**：`OptimizerConfig.method` 默认 `"equal_weight"`（[config.py L276](../core/config.py#L276)），因此默认配置即命中。行为级旁证（S1）：信号剔除 `000001` 后，其 1,000,000 股持仓一直持有到期末，期间无任何卖出单。

**参照实现**：`build_target_positions`（[target_positions.py L43](../core/target_positions.py#L43)）显式「覆盖 `target_weights` 与 `current_positions` 的并集」，并对调出标的生成 `is_exit=True` 的清仓项；`engine_v2._execute_rebalance`（[L953-978](../core/engine_v2.py#L953-L978)）即走该函数。

---

### R4（P1）超卖成交入账 → 现金虚增

**位置**：`PositionTracker.execute_trade`（[tracker.py L192-217](../core/tracker.py#L192-L217)）先按成交方向增减现金（L200-204），再调用 `Position.execute_trade`；后者 SELL 分支带 `if self.quantity > 0` 守卫（[tracker.py L88](../core/tracker.py#L88)），超出持仓的部分被**静默丢弃**，但现金已入账。

**读数（R2，组件级）**：
```
注入 100 股后：cash=9,999,000 NAV=10,000,000
队列 3 张 SELL 各 100 股 → 执行
  [READ] 成交笔数 = 3（SELL/SELL/SELL）
  [READ] 执行后持仓 = 0 股（无负持仓，但第 2/3 笔无对应持仓）
  [READ] cash 9,999,000 -> 10,002,000（合法应为 +1,000）
  [READ] NAV 10,000,000 -> 10,002,000
```

**后果**：现金不守恒 → 虚增 2,000 元「无中生有」收益；成交日志与持仓账目不一致（3 笔卖出对应 1 笔持仓）。

**影响面升级（Step 2 复审 N1 实证）**：中性策略（`direction="both"`）的空头腿走负权重 → `target_quantity` 为负 → SELL 单在**无持仓**时由 `executor.execute_order` 照常成交（该函数无持仓校验），`tracker` 现金照常入账、持仓被 `quantity > 0` 守卫静默钳制在 0——即**空头腿的每次再平衡都是一次幻影现金入账**。8 日探针：600000 SELL 成交 **7 笔**、期末持仓 **0 股**、cash 10,000,000 → **90,000,000**、NAV → **131,250,000**（+1,212.5% 幻影收益）。R4 在中性路径下**无条件触发**，非边界场景。

**参照实现**：P-014 的 `_clamp_sell_quantity`（[engine_v2.py L671](../core/engine_v2.py#L671)）在执行侧按可卖持仓夹紧，无持仓即作废订单；`engine_v2` 两条执行路径共用（L792 / L1150）。

---

### R1（P2）再平衡时刻 NAV 漏计当日新成交持仓 → 自激换手

**位置**：`_generate_orders` 的 `current_value = tracker.get_total_value()`（[L314](../agents/multi_strategy_engine.py#L314)），而 `get_total_value` = 现金 + `Position.market_value`（[tracker.py L290-297](../core/tracker.py#L290-L297)）；`market_value` 仅在日终 `update_market_values`（L223-239）写入，且 `Position.execute_trade` 的 BUY 分支不维护该字段。

**读数（R1 根因追踪）**：
```
[REBAL] 2024-01-02 cash=10,000,000 mkt_val=0        qty=0       NAV_used=10,000,000
[REBAL] 2024-01-03 cash=0          mkt_val=0        qty=1,000,000 NAV_used=0      ← 当日买入后
[REBAL] 2024-01-04 cash=10,000,000 mkt_val=0        qty=0       NAV_used=10,000,000
[REBAL] 2024-01-05 cash=0          mkt_val=0        qty=1,000,000 NAV_used=0
```

**读数（S0 最小复现）**：1 股、常量价 10、目标恒定 100%、10 个交易日 → **9 笔**买卖（应 1 笔），队列逐日交替 `BUY → SELL → BUY`。

**触发条件**：`RebalanceConfig.frequency="daily"`（默认 `"monthly"`，[config.py L310](../core/config.py#L310)）；`hybrid`/连续触发同样可能命中。月/周频下执行日与再平衡日不重合，不触发。

**参照实现**：`compute_portfolio_value`（[target_positions.py L148](../core/target_positions.py#L148)）的 docstring 已逐字记载该坑——「`tracker.get_total_value()` 在"开盘成交后、日终盯市前"不可信……调仓估值一律用价格重算」。

---

### R3（P2）失败单重复累积、无过期、无撤销

**位置**：`_next_day_orders` 仅在 `_execute_order_next_open` 追加（[L382](../agents/multi_strategy_engine.py#L382)）与 `_execute_next_day_orders` 回写 `failed_orders`（[L437](../agents/multi_strategy_engine.py#L437)）；无过期、无再平衡前撤销。每个再平衡日按「当前持仓仍为 0」重新生成同向单。

**读数（S2）**：`000001` 开盘价缺失 6 个交易日 →
```
[READ] 队列累积 7 张 BUY（2024-01-02 .. 2024-01-10）
[READ] 2024-01-11 恢复日集中成交 7,000,000 股 @10
        （单次目标 1,000,000 股 → 7 倍超配）
```

**参照实现**：`_cancel_next_day_orders`（[engine_v2.py L690](../core/engine_v2.py#L690)，L917 在每次再平衡开头调用）+ `PendingOrder.is_expired`（买 5 / 卖 10 自然日）。

---

### O1（观察）空头市值不更新

`update_market_values` 的循环条件为 `if position.quantity > 0`（[tracker.py L231](../core/tracker.py#L231)），`direction="both"` 产生的负持仓不会盯市，`MultiStrategyEngine` 的中性策略净值不可信。本批不改，登记观察。

---

## 4. 复现矩阵

| 配置 / 场景 | R1 | R2 | R3 | R4 |
|-------------|----|----|----|----|
| 默认（`monthly` + `equal_weight`） | — | **触发** | 需数据缺失 | 需超卖 |
| `frequency="daily"` | **触发** | **触发** | 需数据缺失 | 需超卖 |
| 开盘价缺失（无停牌/无涨跌停） | — | **触发** | **触发** | — |
| 停牌（`exclude_suspended=True`） | — | **触发** | 目标外标的被跳过（叠加） | — |
| `enable_pending_orders=True` | — | **触发** | 队列侧有 `is_expired` 兜底 | 同 |
| `direction="both"`（中性） | 触发 | **触发** | 需数据缺失 | **常态触发**（空头腿每日 SELL 无持仓，Step 2 N1 实证） |

---

## 5. 探针原文（关键读数汇总）

| 探针 | 脚本 | 读数 |
|------|------|------|
| S0 自激换手最小复现 | `probe2.py` | 10 日 / 恒定目标 → **9 笔**（应 1 笔） |
| S1 信号剔除已持仓 | `probe.py` | `000001` 期末仍持 1,000,000 股，剔除后无卖出 |
| S2 买单重复累积 | `probe.py` | 队列 7 张 → 恢复日 **7,000,000 股**（7×） |
| C1 退出单组件探针 | `probe2.py` | 目标外持仓卖出单 **0** 张 |
| C2 超卖组件探针 | `probe2.py` / `probe3.py` | 3 笔成交、持仓 0、现金 **+3,000**（应 +1,000）、NAV **+2,000** |
| R1 NAV 根因追踪 | `probe3.py` | 买入日 `cash=0 / mkt_val=0 / NAV_used=0` |

---

## 6. 影响面

1. **结果可用性**：默认配置命中 R2 → 任何 `MultiStrategyEngine` 多头/空头回测的持仓集合只增不减，净值曲线失真。
2. **账目完整性**：R4 使现金与成交记录不自洽，虚增收益。
3. **公开接口**：README 有 `MultiStrategyEngine(config)` 用法示例（L310-313），属对外暴露路径。
4. **测试盲区**：全仓无 `StrategyEngine` 实例化测试（`test_strategy_allocator.py` 只测分配管理器），四项缺陷均无回归网。

---

## 7. 方案矩阵

| 方案 | 内容 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **M-A** | 估值与目标持仓改为复用 `compute_portfolio_value` + `build_target_positions`；执行侧补 `_clamp_sell_quantity` 语义 + 再平衡前撤销/过期 | 与 V2 单一语义来源；两个函数已有 P-011/P-014 测试背书 | 需处理 `target_positions` 的 `value_buffer=0.985` 与 `StrategyEngine` 现有小数取整差异 | **推荐** |
| M-B | 在 `StrategyEngine` 内就地补丁（自行实现清仓项、价格重算、夹紧、过期） | 改动最小、无跨模块依赖 | 与 V2 形成第二套语义，后续漂移风险高 | 备选 |
| M-C | 仅加防御（NAV ≤ 0 时 fail-fast，不修语义） | 最小改动 | 不修复 R2/R4，结果仍错，只是不再静默 | 拒绝 |

**M-A 落点（建议）**：
- B1：`_generate_orders` 改为先 `compute_portfolio_value(cash, current_positions, close_prices, market_values)` 再 `build_target_positions(...)`，遍历 `targets` 而非 `target_weights`（修 R1 + R2）。**约束（Step 2 F-S2-P031-1）**：`build_target_positions` 对负权重直接抛 `ValueError`（N2 实证），与中性策略的合并权重形态（`{'000001': 0.5, '600000': -0.5}`）**不兼容**——DESIGN 须裁决多头/中性路径拆分（中性路径独立处理或扩展该函数），且空头腿的账目语义（当前 SELL 无持仓 = 幻影现金）必须先于订单生成定义。
- B2：`_execute_next_day_orders` 引入卖量夹紧（可复用 `_clamp_sell_quantity` 逻辑，或抽到 `core/target_positions.py` 供两侧共用）（修 R4）。
- B3：再平衡开头撤销本策略信号域内的在途单；复用 `PendingOrder.is_expired`（买 5 / 卖 10）（修 R3）。
- B4：新增 `tests/test_p031_*.py`，四项各一组红绿 + 正常路径零误报。

---

## 8. 风险四元块

| 维度 | 内容 |
|------|------|
| **行为变更** | 订单数量与换手率会显著变化（尤其 `daily`）；R2 修复后首次出现「调出即卖出」的交易 |
| **破坏面** | 仅 `agents/multi_strategy_engine.py`；`core/` 零改动；`tests/golden/*.json` 不涉及（golden 走 V2/V3） |
| **回退点** | 单文件回退；B1-B3 可独立回退（B1 依赖 `target_positions`，B2/B3 独立） |
| **验证** | 四项红绿 + `MultiStrategyEngine` 集成 smoke + 探针复跑（S0 应为 1 笔；C1 应 1 张清仓单；C2 现金 +1,000；S2 应 1 张单） |

---

## 9. 负向发现（已排除的猜测）

1. **V2 不受影响**：`engine_v2._execute_rebalance` 已在 L953-978 使用 `compute_portfolio_value` + `build_target_positions`，并在 L911-917 做再平衡撤销。`G1.json` 在 `frequency="daily"` 下仅 **4 笔**成交（买入 2 + 末日清仓 2）、NAV 恒 10,000,000——与 R1 的 9 笔自激形态截然不同，反证 V2 的估值路径正确。
2. **`compute_portfolio_value` 的 docstring 已明确记载该时序坑**（L154-158），说明这是已知设计约束而非新发现，`StrategyEngine` 是漏网实现。
3. **R3 不是停牌特有**：只要「标的仍可交易但开盘价不可用/成交失败」，队列即重复累积；停牌只是其中一种数据形态（此时目标外标的还会叠加 R2）。
4. **S1 的行为级读数被 R1 污染**（daily 下出现 1 笔卖出），因此 R2 的定罪证据以 C1 组件探针为准，S1 仅作旁证。

---

## 10. 下一 Step

**Step 2 独立 Review（异构基座）**——本文件作者基座待定，须由非作者基座复核。复核重点：

1. R1-R4 的四组读数独立重放（`%TEMP%` 三个探针脚本）；
2. C1/C2 组件探针的构造是否等价于生产路径（是否人为注入不可达状态）；
3. M-A 的 `value_buffer=0.985` 与 `StrategyEngine` 现有整手取整差异是否构成行为口径漂移；
4. O1 是否应升格为本批范围；
5. `MultiStrategyEngine` 的短/中性策略（`direction="short"/"both"`）是否受 R2/R4 同形影响。

---

## 11. Step 2 独立 Review 记录（异构基座 GLM-5.3-Flash，2026-11-16）

> **异构性（RULE-5）**: 本文件作者 DeepSeek-V4.1-Flash ≠ 本节复审基座 **GLM-5.3-Flash**。
> **复审对象**: 本文件提交 `a97ba1b` 版本（Step 1 收口）；复审时点 HEAD `fae43ce`（代码与 `2f5a6e0` 一致，仅 docs）。
> **方法**: E1 代码锚点逐项重放 + E2 三探针脚本重跑比对 + **E3 复审基座独立编写探针**（`%TEMP%\p031_step2_review_probe.py`，N1 中性空头腿 / N2 M-A 兼容性）+ E4 负向发现独立复核 + §10 五项复核重点逐一裁决；不采信任何未经本基座复现的读数。
> **结论**: **pass（0 P0 / 0 P1 / 2 P2 当轮回写 / 3 观察）**——满足进入 Step 3 DESIGN 条件，但 DESIGN 必须先裁决 F-S2-P031-1。

### 11.1 E1 代码锚点重放（逐项核实，全过）

| 锚点 | §3 声明 | 本基座复现 | 结论 |
|------|---------|------------|------|
| `_generate_orders` 遍历面 | 仅 `target_weights.items()`（L320） | L320 `for stock, weight in target_weights.items():`；L314 `current_value = tracker.get_total_value()` | **一致** |
| `EqualWeightOptimizer` 输出 | 只返回入选标的 | [portfolio.py L184](../core/portfolio.py#L184) `weights = pd.Series(1.0 / len(selected_stocks), index=selected_stocks)`——仅选中股票 | **一致** |
| tracker 现金先入账 | L200-204 先增减现金，L88 SELL 守卫丢弃超额 | `execute_trade` L201-204 现金分支无守卫；`Position.execute_trade` L88 `if self.quantity > 0` | **一致** |
| BUY 不维护 market_value | L79-84 | BUY 分支仅更新 `quantity`/`avg_cost` | **一致** |
| 盯市只更新多头 | L231 `quantity > 0` | `update_market_values` L231 | **一致** |
| 默认配置 | `equal_weight` / `monthly` | [config.py L276 / L310](../core/config.py#L276) | **一致** |
| `_next_day_orders` 生命周期 | 仅追加 L382 / 回写 L437，无过期无撤销 | grep `is_expired\|mark_expired\|cancel_orders` 在 agents 引擎内仅命中 pending_queue 两处（L165 / L483）；`_next_day_orders` 零命中 | **一致** |
| executor 无持仓校验 | —（§3 未声明，本基座补证） | [execution.py L290-330](../core/execution.py#L290-L330)：仅价格合理性检查，SELL 无持仓照常成交并入 trade_log | **一致**（R4 前置条件恒真） |
| 测试盲区 | 全仓无 `StrategyEngine` 实例化测试 | `grep "StrategyEngine(\|MultiStrategyEngine(" tests/` = **0 命中** | **一致** |
| README 公开示例 | L310-313 | L310-316 存在；**但示例调用 `register_agent`/`GuruAgentV2`——`MultiStrategyEngine` 无该方法（grep 仅 `def run`）**，示例为失实 API（见 O-S2-P031-3） | **一致 + 新证** |

### 11.2 E2 探针重放（三脚本重跑，读数逐字一致）

| 探针 | §5 声明 | 本基座复现 | 结论 |
|------|---------|------------|------|
| S0（probe2） | 10 日 9 笔 | **9 笔**、期末 1,000,000 股 | **一致** |
| C1（probe2） | 卖出单 0 张 | 队列 `['2024-01-03:BUY:600000:1000000']`、卖出单 **0** | **一致** |
| C2（probe2/probe3） | 3 笔 / 持仓 0 / cash +3,000 / NAV +2,000 | 3 笔 SELL、持仓 0、`9,999,000 → 10,002,000`、NAV `10,000,000 → 10,002,000` | **一致** |
| R1 根因（probe3） | 买入日 `cash=0 / mkt_val=0 / NAV_used=0` | 6 个再平衡日读数逐字一致 | **一致** |
| S2→R3（probe） | 队列 7 张 → 恢复日 7,000,000 股 | 2024-01-11 集中成交 **7 笔 BUY**、`BUY 按日汇总 2024-01-11: 7 / 7,000,000` | **一致** |
| S1（probe） | 剔除后持有到期末 | 3 笔 / 卖出 1 笔（R1 污染）/ 期末 1,000,000 股 | **一致**（§9.4 污染声明成立） |
| S3（probe，作者运行被截断） | —（未引用） | 本基座重放**完整跑通**：期末 1,553,200 股（买卖混合累积，无负持仓，钳制地板 0） | 与机制一致，补全留档 |

### 11.3 E3 复审基座独立探针（新证，`p031_step2_review_probe.py`）

| 探针 | 设计 | 读数 | 含义 |
|------|------|------|------|
| **N1** | `direction="both"`、2 股、常量价、8 日逐日驱动 | 600000 SELL 成交 **7 笔**、期末持仓 **0 股**、cash 10,000,000 → **90,000,000**、NAV → **131,250,000**（+1,212.5% 幻影收益） | **R4 在中性路径常态触发**——空头腿每次再平衡 = 一次幻影现金入账；§0/§4「需超卖单」表述失实（已当轮回写 §0/§3/§4） |
| **N2** | `build_target_positions` 传入中性合并权重形态 | `ValueError: 目标权重不允许为负（A股不做空）`；中性合并权重实测 `{'000001': 0.5, '600000': -0.5}` | **M-A 的 B1 落点与中性策略不兼容**——直用必抛错（从静默错变崩溃）；已当轮回写 §7 |

### 11.4 E4 负向发现独立复核（§9 全部成立）

| 项 | §9 声明 | 本基座复核 | 结论 |
|----|---------|------------|------|
| V2 估值路径 | L953-978 用 `compute_portfolio_value` + `build_target_positions`，L911-917 再平衡撤销 | 逐行读码一致；`compute_portfolio_value` docstring（L154-158）明载时序坑 | **成立** |
| G1 反证 | `daily` 下仅 4 笔、NAV 恒 10,000,000 | `G1.json`: `trades count=4 / total_amount=19,700,000`；`nav first=last=10,000,000` | **成立** |
| P-014 防线在 V2 | `_clamp_sell_quantity` L671 / `_cancel_next_day_orders` L690，L792/L1150 共用 | grep 命中一致 | **成立** |
| golden 不涉及 | 本批 golden 走 V2/V3 | `_golden_cases.py` 仅构造 `BacktestEngineV2`/`VectorBacktestEngine` | **成立** |

### 11.5 §10 五项复核重点裁决

| # | 复核重点 | 裁决 | 依据 |
|---|----------|------|------|
| 1 | 四组读数独立重放 | **一致** | 11.2 全表 |
| 2 | C1/C2 组件探针等价性 | **等价** | C1 直接调用生产函数 `_generate_orders`，注入的 `target_weights` 形态与 `EqualWeightOptimizer` 输出同构（入选标的 Series）；C2 经 `_execute_order_next_open` → 真实 `_execute_next_day_orders` 执行，且 3 张同向卖单在生产可达（S2 队列累积已证同机制） |
| 3 | M-A `value_buffer=0.985` 口径漂移 | **可接受，须 DESIGN 显式化** | 0.985 缓冲使买入量降 1.5%，与 V2 单一语义对齐是收益非漂移；但真正的口径问题更大——**负权重不兼容**（F-S2-P031-1），0.985 只是次级 |
| 4 | O1 是否升格 | **维持观察（前提不可达）** | N1 实证空头腿持仓被钳制在 0（`SELL` 分支 `quantity > 0` 守卫）→ 当前 tracker 语义下**负持仓根本不会产生**，O1「空头市值不盯市」的前提不可达；真问题是幻影现金（F-S2-P031-2）。DESIGN 裁决空头腿语义时一并处理 |
| 5 | short/both 同形影响 | **R2 同形成立；R4 升级常态** | `_generate_orders` 三方向共享 → R2 对 short/both 同形；R4 见 N1；另登记 `direction="short"` 语义歧义（O-S2-P031-1） |

### 11.6 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S2-P031-1 | **P2** | **M-A 与中性策略不兼容**：`build_target_positions` 对负权重抛 `ValueError`（N2 实证），而中性合并权重必含负值——§7 M-A 的 B1 直用方案在 `direction="both"` 下首日即崩 | **当轮回写 §7**：B1 补约束——DESIGN 须裁决多头/中性路径拆分（或扩展函数支持带符号权重），且空头腿账目语义先于订单生成定义 |
| F-S2-P031-2 | **P2** | **R4 影响面表述失实**：§0/§4 写「需出现超卖单」（条件触发），实际中性路径**无条件常态触发**（N1：8 日 cash 10M → 90M、NAV +1,212.5%）——中性策略回测结果完全不可用，且现有测试零覆盖 | **当轮回写 §0/§3/§4**：触发面改为「多头：需超卖单；中性：常态触发」 |
| O-S2-P031-1 | 观察 | `direction="short"` 语义歧义：`select_top=False` 仍产出正权重 → `_generate_orders` 生成 **BUY** 单（买低分股），与模块 docstring「卖出得分最低的股票（或买入得分最低的股票做空）」的两义表述相符——属产品设计意图未定义，非本批缺陷 | 登记：DESIGN 裁决空头语义时一并澄清 |
| O-S2-P031-2 | 观察 | 探针 S3 在作者运行时被输出管道截断（exit -1），RESEARCH 未引用其读数——本基座重放完整跑通（期末 1,553,200 股），不影响定罪链；后续探针建议落盘重放而非管道直读 | 留档 |
| O-S2-P031-3 | 观察 | README L310-316 的 `MultiStrategyEngine` 示例调用不存在的 `register_agent`/`GuruAgentV2` API（幻觉残留，同型于 F-R5-P005-2）；不影响 §6.3「公开暴露路径」的结论（类本身可导入） | 登记：候选 T3 文档批，不并入 P-031 |

**P0 = 0 / P1 = 0 / P2 = 2（均当轮回写）/ P3 = 0。**

### 11.7 复审结论

- **Step 2 pass**：E1 十项锚点全一致、E2 六组读数逐字复现、E3 两项新证补全影响面、E4 负向发现全部成立、五项复核重点全部裁决。
- 2 项 P2 级设计约束缺口（F-S2-P031-1/2）**当轮回写**至 §0/§3/§4/§7；3 项观察登记。
- **下一 Step：Step 3 DESIGN**——以回写后口径为准，必须先裁决：① 多头/中性路径拆分与空头腿账目语义（F-S2-P031-1）；② R4 修复位置（执行侧夹紧 vs tracker 现金守卫，须评估 `core/tracker.py` 改动的波及面——V2 也共用该 tracker，虽然 V2 夹紧后不可达，改动仍须保持 V2 golden 零重录）；③ `value_buffer=0.985` 是否沿用；④ O1/`direction="short"` 语义澄清是否并入。
