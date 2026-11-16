# RESEARCH：P-033 待执行订单价格有效性（queue 路径 NaN / 非正价透传）

> **批次**: P-033 · **T1**（`core/execution.py` + `core/engine_v2.py` + `agents/multi_strategy_engine.py`；行为变更 = 无效价订单由「静默成交污染账目」改为「拒绝 + 计量 + 保留重试」）
> **状态**: **Step 1 完成**（2026-11-16，基线 HEAD `8d66787`）
> **作者基座**: DeepSeek-V4.1-Flash（Step 2 复审须异构，RULE-5）
> **上游**: **O-S6-P031-3**（[IMPL_p031 §13.6](IMPL_p031_strategy_engine_order_accounting.md)：「queue 路径价格无有效性校验（仅 `in open_prices` 成员检查，NaN/非正可透传）——既有行为，本批前后一致，V2 L799-808 同样无校验，候选后续批」）；O-P031-3 已在 P-032 关闭，与本批无关
> **取证脚本**: `%TEMP%\p033_step1_probe.py`（10 场景 / 两引擎 / queue 与 next-day 对照），仓库外运行

---

## 0. 结论摘要（TL;DR）

| 项 | 结论 |
|----|------|
| 缺陷本体 | **queue 路径**（`_process_pending_orders`）只做 `order.stock not in open_prices` 成员检查，**无价格有效性校验**；`agents` 与 `core/engine_v2` **同构** |
| R1（**P1**） | 开盘价 `NaN` / `±inf` → 成交入账后 **cash 永久为 NaN**（`Price`/`amount`/`avg_cost` 同步 NaN）→ NAV 全 NaN → P-031 nav 守卫每次再平衡计数、组合冻结、指标 NaN |
| R2（**P2**） | 开盘价 `0` → **免费获得持仓**（零成本 0 元 100 股；默认成本仅付 5 元佣金，市值按收盘 10 元计 1,000 元）；开盘价 `-5` → **现金 +500**（BUY 负价反向入账） |
| R3（P3） | 收盘价 `0` 时 `abs(exec - close)/close` 产生 `inf` 仅告警、不阻断——无账目污染，属提示噪声 |
| 负向发现 | **次日路径两引擎均已完整防护**（`open_price is None or pd.isna or <= 0`）→ 对照组零成交、订单保留；缺陷仅 queue 路径 |
| 与 P-031 关系 | **非回归**：P-031 修 SELL 侧超卖夹紧，未覆盖价格有效性；本缺陷在 P-031 前后同构 |
| 触发可达性 | `NaN`：价格数据缺口；`0`：停牌日价格写 0 且 `suspend` 缺失时掩码默认 `0=正常`（P-010 约定）→ 掩码放行；负值：脏数据 |
| 建议方案 | **M-A**：`execute_order` 入口单点守卫（兜底全部调用方）+ 两引擎 queue 路径显式计量（可观测） |
| 测试破坏面 | 全仓 `execute_order` 调用方 **37 处**，**零处**使用 0/NaN/负价（grep 实证）→ 守卫对既有测试零破坏 |

一句话：**引擎在「价格不可用」时本应"不成交"，却在 queue 路径按价格不可用的数值直接记账——一次数据缺口即可把账户现金污染为 NaN 或凭空产生持仓。**

---

## 1. 触发与范围

### 1.1 触发

P-031 Step 6 实施 Review 的 O-S6-P031-3 观察项（[IMPL_p031 §13.6](IMPL_p031_strategy_engine_order_accounting.md)）在 P-032 待办分析中被列为下一 T1 候选。本批 Step 1 的任务是：**把「观察」升级为可定级的缺陷取证**——确认是否存在、影响多大、修复面在哪。

### 1.2 范围

| 面 | 内容 |
|----|------|
| **包含** | ① `agents/multi_strategy_engine.py::_process_pending_orders`（默认主路径，`enable_pending_orders=True`）；② `core/engine_v2.py::_process_pending_orders`（默认引擎 `create_default_engine` → V2）；③ `core/execution.py::execute_order` 的价格入参契约（唯一账目入口）；④ V2 fallback 路径经 `execute_pending_order`（委托 `execute_order`） |
| **不包含** | ① 次日路径（两引擎已防护，见 N1）；② `engine_v3_vector`（无逐日订单执行）；③ 停牌/退市掩码语义（P-010/P-012 既有口径，不在本批重议）；④ BUY 侧现金夹紧（U-P031-2 / U-P014-3，独立项）；⑤ `close_price` 校验语义（R3 仅观察） |

---

## 2. 调用链与时序

```
交易日循环
  ├─ agents: _process_trading_day (L185)
  │    ├─ _execute_next_day_orders (L396)   ← 已校验 open_price（L451）
  │    └─ _process_pending_orders (L478)    ← 仅成员检查（L505）→ execute_order (L520)
  └─ V2: _process_trading_day (L394)
       ├─ _execute_next_day_orders (L1091)  ← 已校验 open_price（L1140）
       ├─ _process_pending_orders (L752)    ← 仅成员检查（L799）→ execute_order (L815)
       └─ _try_fallback_order → execute_pending_order (L884) → execute_order (execution L407)
```

`core/execution.py::execute_order`（L262-344）**无价格有效性校验**：`amount = quantity * execution_price`（L307）→ `cost`（L310）→ `Trade`（L318）→ `trade_log.add_trade`（L330），全程不做 `isfinite` / `> 0` 判定。`_get_execution_price`（L292）在 VWAP/TWAP 分支同样可能返回 NaN（high/low/volume 缺失时），即**除入参价之外的第二个 NaN 入口**。

**价格有效性检查的唯一既有点**：两处次日路径（agents L451 / V2 L1140），均为「无效 → 放入 `failed_orders` 保留重试」，不成交、不入账。queue 路径无对应块。

---

## 3. 缺陷清单

### R1（P1）开盘价 `NaN` / `±inf` → 现金永久 `NaN`

| 证据 | 读数（探针 A1 / A4 / V1） |
|------|---------------------------|
| agents open=NaN | `n_trades=1, price=NaN, amount=NaN, cash=NaN, qty=100, avg_cost=NaN` |
| agents open=inf | `n_trades=1, price=inf, amount=inf, cash=NaN, avg_cost=inf` |
| V2 open=NaN | `n_trades=1, price=NaN, amount=NaN, cash=NaN, qty=100, avg_cost=NaN` |

**传导链**：`execute_order` → `Trade(price=NaN, amount=NaN, net_amount=NaN)` → `PositionTracker.execute_trade`：`cash -= net_amount` → **cash 永久 NaN**（后续任何加减法都保持 NaN）；`Position.execute_trade` BUY 分支 `avg_cost = (qty*avg_cost + amount)/qty` → `avg_cost = NaN`。

**后果**：`get_total_value()` 恒 NaN → P-031 D1 的 nav 守卫 `not np.isfinite(nav)` 每次再平衡命中 → `rebalance_nav_invalid` 逐日累积、**不再生成任何订单**（组合静默冻结）；同时 `trades_df` 与绩效指标全部 NaN。这是「一次坏价格 → 整条回测报废且无恢复路径」。

### R2（P2）开盘价 `≤ 0` → 免费持仓 / 幻影现金

| 证据 | 读数 |
|------|------|
| agents open=0（零成本） | `n_trades=1, price=0, amount=0, cash=10000000, qty=100, avg_cost=0` |
| agents open=0（默认成本） | `cash=9999995`（仅扣 `commission_min=5`），`qty=100` |
| agents open=-5 | `price=-5, amount=-500, cash=10000500`（**现金 +500**），`avg_cost=-5`，`qty=100` |
| V2 open=0 | `price=0, amount=0, cash=10000000, qty=100, avg_cost=0` |

**后果**：0 价买入即**零成本建仓**——收盘按 10 元盯市则凭空产生 1,000 元 NAV（默认成本下 995 元）；负价买入使 BUY 的 `net_amount` 为负、`cash -= 负数` → **现金反向增加**，且 `avg_cost=-5` 使 `unrealized_pnl=(10-(-5))*100=1,500` 幻影浮盈。

### R3（P3）收盘价 `0` → 除零仅告警

| 证据 | 读数（A5：open=10, close=0） |
|------|------------------------------|
| agents | `n_trades=1, price=10, amount=1000, cash=9999000`；日志 `差异=inf%` |

`close_price` 来自 pandas Series（`np.float64`），`10.0/np.float64(0.0)` 返回 `inf` 而非抛 `ZeroDivisionError`（numpy 语义），故 L297-304 只打一条「差异过大」告警，成交照常。**无账目污染**，属告警文案噪声；本批建议不改判定、仅登记。

### N1（负向发现，非缺陷）次日路径已完整防护

| 证据 | 读数 |
|------|------|
| agents next-day open=NaN（A6） | `n_trades=0, retained=1, cash=10000000, qty=0` |
| V2 next-day open=NaN（V3） | `n_trades=0, retained=1, cash=10000000, qty=0` |

两引擎次日路径的 `open_price is None or pd.isna(open_price) or open_price <= 0` 分支有效：订单保留重试、账目零变化。**缺陷严格限于 queue 路径**——这决定了修复面而不是「全引擎无防护」。

---

## 4. 复现矩阵

| # | 引擎 | 路径 | 开盘价 | 收盘价 | 期望行为 | 实测 | 判定 |
|---|------|------|--------|--------|----------|------|------|
| A1 | agents | queue | `NaN` | 10 | 拒绝 + 保留重试 | 成交，cash `NaN` | **❌ R1** |
| A2 | agents | queue | `0` | 10 | 拒绝 + 保留重试 | 成交 0 元 100 股 | **❌ R2** |
| A2b | agents | queue | `0` | 10 | 同上（默认成本） | 扣 5 元佣金获 100 股 | **❌ R2** |
| A3 | agents | queue | `-5` | 10 | 拒绝 + 保留重试 | 成交，cash **+500** | **❌ R2** |
| A4 | agents | queue | `inf` | 10 | 拒绝 + 保留重试 | 成交，cash `NaN` | **❌ R1** |
| A5 | agents | queue | 10 | `0` | 成交（价格本身有效） | 成交 + `inf%` 告警 | ⚠ R3 |
| A6 | agents | next-day | `NaN` | 10 | 拒绝 + 保留 | **零成交 / 保留 1** | ✅ N1 |
| V1 | V2 | queue | `NaN` | 10 | 拒绝 + 保留重试 | 成交，cash `NaN` | **❌ R1** |
| V2 | V2 | queue | `0` | 10 | 拒绝 + 保留重试 | 成交 0 元 100 股 | **❌ R2** |
| V3 | V2 | next-day | `NaN` | 10 | 拒绝 + 保留 | **零成交 / 保留 1** | ✅ N1 |

---

## 5. 探针原文（关键读数逐字）

```
[A1 agents/queue open=NaN close=10] n_trades=1 | price=NaN | amount=NaN | cash=NaN | qty=100 | avg_cost=NaN | pending_left=0 | err=-
[A2 agents/queue open=0 close=10] n_trades=1 | price=0.0000 | amount=0.0000 | cash=10000000.0000 | qty=100 | avg_cost=0.0000 | pending_left=0 | err=-
[A2b agents/queue open=0 close=10 默认成本] n_trades=1 | price=0.0000 | amount=0.0000 | cash=9999995.0000 | qty=100 | avg_cost=0.0000 | pending_left=0 | err=-
[A3 agents/queue open=-5 close=10] n_trades=1 | price=-5.0000 | amount=-500.0000 | cash=10000500.0000 | qty=100 | avg_cost=-5.0000 | pending_left=0 | err=-
[A4 agents/queue open=inf close=10] n_trades=1 | price=inf | amount=inf | cash=NaN | qty=100 | avg_cost=inf | pending_left=0 | err=-
[A5 agents/queue open=10 close=0] n_trades=1 | price=10.0000 | amount=1000.0000 | cash=9999000.0000 | qty=100 | avg_cost=10.0000 | pending_left=0 | err=-
[A6 agents/nextday open=NaN（对照）] n_trades=0 | retained=1 | cash=10000000.0000 | qty=0 | err=-
[V1 v2/queue open=NaN close=10] n_trades=1 | price=NaN | amount=NaN | cash=NaN | qty=100 | avg_cost=NaN | err=-
[V2 v2/queue open=0 close=10] n_trades=1 | price=0.0000 | amount=0.0000 | cash=10000000.0000 | qty=100 | avg_cost=0.0000 | err=-
[V3 v2/nextday open=NaN（对照）] n_trades=0 | retained=1 | cash=10000000.0000 | qty=0 | err=-
```

---

## 6. 影响面

| 面 | 读数 | 依据 |
|----|------|------|
| 生产调用点 | **5 处** | `agent_framework.py:1420` / `multi_strategy_engine.py:463,520` / `engine_v2.py:566,815`；另有 `execute_pending_order`（execution L389-414）→ `execute_order` 委托链（V2 fallback L884） |
| 默认配置可达 | **是** | `enable_pending_orders=True` 为默认（config L375）→ queue 为主路径；`create_default_engine` → V2 |
| 价格缺失形态 | 两类 | ① `NaN`（数据缺口 / 新股 / 退市边界）；② `0`（停牌日价格写 0；`suspend.pkl` 缺失时 P-010 约定掩码默认 `0=正常` → 掩码不再兜底） |
| 后果等级 | R1 **P1** / R2 **P2** | P1：单次触发即不可恢复（NaN 无逆运算）；P2：需 0/负价形态，产生幻影净值但仍可继续运行 |
| 与既有批次关系 | 非回归 | P-031 修复 SELL 侧超卖（`_clamp_sell_quantity`），未覆盖价格有效性；P-029 仅计量（`pending_open_price` 只覆盖日期切片缺失） |
| 测试破坏面 | **0** | 全仓 `execute_order(` 调用 37 处，`0.0` / `nan` / 负价入参 **零命中**（grep 实证） |

---

## 7. 方案矩阵

| 维度 | **M-A（推荐）** | M-B | M-C |
|------|-----------------|-----|-----|
| 形态 | `execute_order` 入口守卫（`not isfinite or <= 0` → warning + `return False, None`）**+** 两引擎 queue 路径显式前置过滤与计量 | 仅两引擎 queue 路径各自加守卫，`core/execution.py` 零改动 | 仅 `execute_order` 守卫，引擎层零改动 |
| 覆盖面 | **全部 5 个调用点 + 未来调用方 + VWAP NaN 入口** | 仅两处 queue；`agent_framework:1420` 与 VWAP 分支仍裸奔 | 全覆盖，但无归因 |
| 可观测 | 引擎层计数（agents 新键 / V2 复用 `skipped_price`）+ warning | 同左（两处） | 仅 warning |
| 行为变更面 | `core/execution.py` 一次（合法价零影响） | `core/engine_v2.py` + `agents` 双处 | `core/execution.py` 一次 |
| 重复代码 | 无（守卫单点） | 两份同形判定（易漂移，P-031 F-S4 先例） | 无 |
| 测试破坏面 | **0**（无 0/NaN 价调用） | 0 | 0 |
| 复杂度 | 低 | 中 | 低 |
| 缺口 | 需在 5 个调用点确认 `False` 分支语义（均已具备：保留重试） | 未来新调用方仍需自觉 | 无法区分「拒绝原因」，静默 |

**推荐 M-A**：守卫单点收口（与 P-014「执行侧夹紧」同层哲学：账目入口拒绝非法价），引擎层补计量保证可归因。`False` 返回在各调用点的既有语义天然正确——V2 queue 保留订单（下日重试）、V2 next-day 入 `failed_orders`、agents 两路径均不 `mark_executed`。

**不采纳**：① 在 `tracker.execute_trade` 加守卫（账目层堵漏，会掩盖上游数据错误，且 V3 共用）；② 在 `PendingOrderQueue` 加价格校验（建单时价格未知）；③ 对 0 价「按停牌处理」（需掩码层语义裁决，超出 T1，登记未决）。

---

## 8. 风险四元块

| 面 | 内容 |
|----|------|
| **风险** | 守卫会改变「0 价成交」这一既有（错误）行为：若某真实回测曾依赖 0 价建仓（无测试先例、无文档记载），结果会变化 |
| **缓解** | 守卫条件严格限定 `None / NaN / ±inf / <= 0`；合法价路径零改动（13 条 golden 全为合法价）；行为变更写入 CHANGELOG 与 PROGRESS |
| **回退** | `execute_order` 单函数回退（新增守卫块可整块删除）；引擎层计数独立可回退 |
| **观测** | 守卫 warning（含 stock/date/price）+ 引擎计数；order 保留在队列，次日照常重试，不引入新状态 |

---

## 9. 负向发现（已排除的猜测）

| ID | 猜测 | 结论 |
|----|------|------|
| N1 | 「两引擎全路径均无价格校验」 | **不成立**——次日路径两引擎均完整防护（A6/V3 对照组零成交） |
| N2 | 「`close_price=0` 会抛 `ZeroDivisionError` 中断回测」 | **不成立**——`np.float64` 除零返回 `inf`，仅触发告警（A5） |
| N3 | 「既有测试依赖 0/NaN 价成交，守卫会破坏测试」 | **不成立**——37 处调用零命中非正价入参 |
| N4 | 「V2 fallback 路径绕过守卫」 | **不成立**——`execute_pending_order` 委托 `execute_order`，M-A 单点即覆盖 |
| N5 | 「P-031 修复引入了本缺陷」 | **不成立**——queue 路径价格检查在 P-031 前后同构（P-031 diff 未触及 L505-509 判定） |
| N6 | 「`update_market_values` 会把 NaN 市值污染快照」 | **不成立**——tracker L233-236 已跳过 NaN/非正价（保持上次市值）；污染源是 `execute_trade` 的 cash 与 `avg_cost` |

---

## 10. 下一 Step

**Step 2 独立 Review（异构基座 GLM-5.3-Flash，RULE-5）**——本文件作者 DeepSeek-V4.1-Flash。复核重点：

1. **定级**：R1 判 P1（NaN 不可恢复）、R2 判 P2（0/负价幻影净值）是否成立，还是应合并为单一 P1；
2. **方案边界**：M-A 改 `core/execution.py` 是否属 T1 可接受范围（判档规则 1：`core/` 行为变更）；是否有更小的等价解；
3. **计量口径**：agents 侧新增键名（候选 `pending_invalid_price`）与 V2 侧复用 `skipped_price` 名单是否一致；是否需要 `failure_counts` 之外的出口；
4. **0 价语义**：拒绝后「保留订单重试」直到过期，是否会与 P-010「suspend 缺失默认 0=正常」形成长期重试噪声（需评估 `next_day_orders_expired` / `mark_expired` 兜底）；
5. **R3 与 VWAP**：`close=0` 告警噪声与 `_get_execution_price` 的 VWAP/ TWAP NaN 入口是否同批处理，还是分别登记；
6. **回归面**：`execute_order` 的 5 个调用点在 `False` 分支上的语义是否逐一成立（V2 fallback / agents 两路径 / agent_framework 直接调用）。

---

## 11. Step 2 独立 Review 记录

（待 Step 2 回填）
