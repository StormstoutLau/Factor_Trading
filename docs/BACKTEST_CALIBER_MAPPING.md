# 回测口径映射（BACKTEST_CALIBER_MAPPING）

> **批次**: P-011「回测准确性验证、学术规范与基准比较」· B2 / T-6
> **上游**: [DESIGN_backtest_validation.md](DESIGN_backtest_validation.md) §4.5（事件级等价）；[RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md) A27/A28/A29
> **下游**: [CHECKLIST_backtest_validation.md](CHECKLIST_backtest_validation.md) B 组
> **代码证据时点**: P-011 B1 提交 `cd6d619`（基线 `dc71c1a`）+ B2 工作区

---

## 1. 为什么必须做口径映射

三份实测型外部证据给出同一个结论：

| 锚点 | 事实 | 对本仓的含义 |
|------|------|--------------|
| A27（QuantEngines 实测） | 两库默认参数下同策略结果差异巨大；"一致"需先钉死 3 项默认值 | 不声明默认口径就谈"对拍"，结论不可用 |
| A28（FeedsMonitor 实测） | Backtrader / vectorbt / Backtesting.py 开箱差 5.5%，对齐规则后差距可逐美元解释 | 差异本身不是缺陷；**不可解释的差异**才是缺陷 |
| A29 | 不一致的第一根因是成交模型（信号价 vs 滑点/延迟/缺口保护） | 本仓 V2（T+1 开盘）vs V3（同日收盘）属同源问题 |

因此本批的做法是：**先写口径表，再写差分测试**；测试断言的不是"结果相同"，而是"差异精确等于声明常量"。

---

## 2. 口径矩阵

### 2.1 本仓两引擎（唯一有代码证据的两列）

| 维度 | V2 `BacktestEngineV2`（事件驱动） | V3 `VectorBacktestEngine`（向量化） | 代码锚点 |
|------|-----------------------------------|--------------------------------------|----------|
| **信号时点** | 交易日 T 收盘后计算（`_composite_signal`） | 同一索引日 `signal[i]`（全期预计算） | `engine_v2.py:345-430`；`engine_v3_vector.py:257-277` |
| **成交时点与价格** | **T+1 开盘**（待执行队列 / `ExecutionPolicy`） | **同日 i 收盘**（`_rebalance_kernel` 用 `close[i]`） | `engine_v2.py:310-321`；`engine_v3_vector.py:315-317`、`:366` |
| **目标仓位缓冲** | `value_buffer=0.985`（留 1.5% 现金） | 无缓冲，满仓 `Σw=1` | `target_positions.py:51`；`engine_v3_vector.py:126-127` |
| **整手约束** | 有，`lot_size=100`，`floor` | 无（连续股数） | `target_positions.py:130-134`；`_rebalance_kernel` |
| **选股并列** | 按优化器权重，`target_count` 截断 | `argpartition` 阈值 `>=`，并列超选 | `engine_v3_vector.py:114-117` |
| **费用** | 佣金（万 3，下限 5 元）+ 印花税 0.1%（仅卖）+ 滑点 0.1% | 单一 `cost_rate`（默认 0.001），**双边对称、无下限、无印花税细分** | `execution.py:331-372`；`engine_v3_vector.py:145-150` |
| **复权** | 成交/估值用 `raw`，信号/收益用 `hfq`（P-012 D2） | 使用 `DataLoaderV3` 传入价（`from_data_manager` 取 `hfq`） | `engine_v2.py:339-343`；`data_v3.py:103-128` |
| **可交易掩码** | universe filter：停牌 / 涨跌停 / ST / 次新 / 因子缺失 | `buyable`/`sellable` 可选入参，**缺省全 True** | `filter/universe_filter_clean.py`；`engine_v3_vector.py:355-363` |
| **估值** | 逐日盯市 `cash + Σ|qty|×price` | `pv[i] = cash[i] + Σ positions[i]×close[i]` | `tracker.py:289-296`、`:223-239`；`engine_v3_vector.py:318-320` |
| **强平** | 末日强制平仓并追加同日第二次快照 | 无（持仓跨末日持有） | `engine_v2.py:314-317`、`:461-529` |
| **输出** | `snapshots` / `trades` / 绩效指标 / `additional_info` | `portfolio_value` / `returns` / 6 项指标 | `engine_v2.py:1019-1100`；`engine_v3_vector.py:387-410` |

### 2.2 外部框架默认值（**仅作对照，本仓未实测**）

> 下表不是本仓的验证结论，而是"若要跨框架对拍，必须先钉死的旋钮"。外部默认值按其官方文档/实测文章口径列出，**未在本仓复核**（U-4 = X-A，见 §5）。

| 维度 | Qlib | Backtrader | VectorBT |
|------|------|-----------|----------|
| 成交价 | `TopkDropoutStrategy` 默认 `deal_price="close"` | 默认**下一根 bar 开盘**（`cheat_on_open=False`） | `from_signals` 默认按 `close` 成交 |
| 费用 | 执行器默认：开仓 5bp、平仓 15bp、`min_cost=5`、`trade_unit=100` | `setcommission()` 不设 → **默认 0 手续费** | `fees=0`、`slippage=0` |
| 复权 | 需自行保证 `$close` 为复权序列 | 数据源决定，框架不强制 | 用户传入 |
| 股票池 | 由 `instruments` + 交易日历约束 | 用户自行过滤 | 无内置过滤器 |
| 输出 | `report_normal` / `positions` / `indicators` | `analyzers`（需显式添加） | 返回 `Portfolio` 对象 |

---

## 3. 本仓两引擎的声明差异（可写成常数）

在**同一经济事件**（同一目标组合、同一价格、零费用）下，两引擎的差异只来自三处：

| 差异源 | 数学形式 | 常量 |
|--------|----------|------|
| 0.985 现金缓冲 | `V2_qty ≈ 0.985 × V3_qty` | `(1 − 0.985) × w × TV / P` |
| 整手取整 | `floor(·/100) × 100` | 至多 99 股 / 标的 |
| 成交时点（T+1 开盘 vs 同日收盘） | 常量价假设下**无差异**；价格变动下差异 = `qty × (open[T+1] − close[T])` | 逐日可算 |

费用差异与此正交：V2 有佣金下限与印花税单边，V3 只有对称 `cost_rate`；对拍时必须把 V2 的四项设为 0、V3 的 `cost_rate=0`，否则残差混合了两个概念。

---

## 4. 等价测试与残差恒等式

实现见 [test_cross_engine_equivalence.py](../tests/test_cross_engine_equivalence.py)（5 个用例）。

**夹具**：3 个交易日 × 2 只股票；`open=close=high=low=[[10, 25]]×3`；`stock_adj=1.0`；`suspend=st=0`；因子常量 `[[1, 2]]×3`；V2 四项费用全 0（含 `commission_min=0`）、`enable_pending_orders=False`、`rebalance=daily`、`target_count=2`；V3 `top_n=2`、`rebalance_freq=1`、`cost_rate=0`；`initial_capital=1e7`。

**实测（B2 已转绿）**：

| 量 | V2 | V3 |
|----|----|----|
| 日 1 持仓 | `[492 500, 197 000]` = `floor(0.985×0.5×1e7/P/100)×100` | `[500 000, 200 000]` = `0.5×1e7/P` |
| 日 1 现金 | `150 000` | `0` |
| NAV（3 日） | `[1e7, 1e7, 1e7]` | `[1e7, 1e7, 1e7]` |

**残差恒等式**（测试逐条断言，`rtol=0` 或 `1e-12`）：

```
V3_qty[i] − V2_qty[i] == (1 − 0.985) × (1/2) × 1e7 / P[i]
                      == [7 500, 3 000]          # P = [10, 25]
V2_cash − V3_cash     == (1 − 0.985) × 1e7 == 150 000
V2_pv[t]              == V3_pv[t] == 1e7          # 常量价 + 零费用
```

> **勘误（P-011 F-S9-4）**：DESIGN §4.5 与 IMPL T-5 曾把第二个标的的持仓残差写作 **3 750**，该值只有在 `P[1]=20` 且**不取整手**时成立；本夹具 `P[1]=25` 的精确值为 **3 000**。以本条与测试为准。

**阴性对照的作用**：若有人把 `value_buffer` 改成 1.0、或把整手去掉，持仓差会变成 `[0, 0]`——断言立刻失败。这排除"差异确实存在但方向对"的弱断言。

---

## 5. 声明边界

1. **本仓不声称与任何外部框架（Qlib / Backtrader / VectorBT / Backtesting.py）数值一致。** 上表外部列仅用于说明"对拍前要钉死什么"。
2. 外部对拍属 **U-D2 / X-B**，本批**未启用**：理由是 A27 指出的维护成本（一旦声明一致，就要跟随对方版本与默认值演进）。
3. 若未来启用外部对拍，前置条件（顺序不可颠倒）：
   - 先用本表钉死三库默认值；
   - 再构造**最小共同任务**（A30① 的交叉验证形态：把共性拆到最小、逐项对齐），而非端到端对拍；
   - 残差必须写成恒等式并配阴性对照，禁止只报"差异很小"。
4. **变更纪律**：任何影响上表的改动（新增费用项、改变成交时点、改变缓冲系数）必须**同一提交内**更新本文件 + 对应测试；否则视为口径漂移。
