# P-014 V2 停牌路径账目缺陷修复 · 设计（Step 3）

> **文档编号**: DESIGN_p014_suspension_accounting
> **阶段**: Phase 2 - 设计（T1 完整管线）
> **日期**: 2026-11-10
> **档位**: T1
> **上游**: [RESEARCH_p014_suspension_accounting.md](RESEARCH_p014_suspension_accounting.md)（§4 复现 / §7 方案矩阵 / §10 Step 2 Review）
> **下游**: IMPL / CHECKLIST
> **门禁 session**: `factorv3-p014-suspension-20261110`

---

## 1. 目标与非目标

**目标**：使 V2 引擎在「订单被掩码/现金阻断」时，不产生负持仓、不重复记账、不让陈旧订单无限重试；两条执行路径共享同一套账目语义。

**非目标（显式边界）**：
- 不改变停牌/涨跌停掩码语义，不改变「不在目标即清仓」的策略语义（U-P014-1）；
- 不引入部分成交、不改 `Position` 的做空语义（不触碰期货/融券路径）；
- 不统一两条路径的**逐笔成交明细**（U-P014-2）；
- 不为队列路径补买侧现金校验（U-P014-3）。

## 2. 关键决策（含被拒绝方案与代价）

### D1 三层防线，按「语义 → 生命周期 → 执行」排序

| 层 | 决策 | 被拒绝方案 | 拒绝理由 | 代价 |
|----|------|-----------|----------|------|
| L1 语义对齐 | 次日路径在每次再平衡开始时撤销信号域内的全部在途订单，与 `pending_queue.cancel_orders` 对齐 | 只做执行侧夹紧 | 治标：重复订单持续生成、队列膨胀 | 已有基线的成交明细会变（G3 等） |
| L2 生命周期 | 次日订单按 `PendingOrder.is_expired` 过期（买 5 / 卖 10 自然日） | 自造交易日计数 | 与队列路径语义漂移，违反「同一规则」 | 无 |
| L3 执行兜底 | 卖出前以可卖持仓夹紧；无持仓即作废订单 | 在 `Position.execute_trade` 截断 | 会静默篡改成交量并影响空头语义 | 仅在不可能状态触发，但保证 I2 |

### D2 夹紧只作用于 SELL

- 依据：负持仓只可能来自超卖；买入不会产生负持仓。
- 被拒绝：双向夹紧（BUY 需引入现金/可用额度模型）→ 属 U-P014-3，越界。
- 代价：买侧若出现「现金不足但已成交」不属于本批（队列路径现状）。

### D3 订单作废用 `mark_cancelled`，不复用 `mark_expired`

- 语义区分：**过期** = 时间到了（D5/L2）；**取消** = 不再需要的旧目标（D4/L1）；**作废** = 无可执行数量（D2/L3）。
- 被拒绝：全部用 `mark_expired` → 事件日志无法区分「因为超时而废」与「因为没有持仓而废」。
- 代价：`PendingOrderQueue` 需新增单订单取消 API（D4）。

### D4 新增 `PendingOrderQueue.cancel_order(order, date) -> bool`

- 理由：现有 `cancel_orders(stock, date)` 只能按股票批量取消，执行侧需要「只作废这一笔」。
- 被拒绝：在执行侧直接 `order.mark_cancelled()` + 手工 `_log_event`（访问私有成员）。
- 代价：`core/pending.py` 增加 1 个公共方法（纯增量，不改变既有调用）。

### D5 次日路径撤单范围 = 信号列全集（与队列路径完全一致）

- 依据：队列路径 `available_stocks = set(signal_df.columns)`（`engine_v2.py:778`）。
- 被拒绝：只撤「本次会重新生成订单的标的」→ 需预判目标，逻辑重复且易漂移。
- 代价：某些「目标未变、本就无需交易」的在途订单也会被撤销——**与队列路径当前行为一致**，非新增偏差。

### D6 夹紧命中时执行「部分数量」而非整单放弃

- 规则：`qty = min(order.quantity, available)`；`available == 0` → 作废；`0 < qty < order.quantity` → 按 `qty` 成交并告警。
- 被拒绝：整单放弃 → 在「持仓被其他路径部分消耗」的场景下会少卖。
- 代价：成交数量与订单数量不一致，需在日志中显式记录。

### D7 过期检查放在次日路径入口，而非生成时

- 理由：过期是「时间驱动」，与是否再平衡无关；放在入口可覆盖「长期无再平衡」场景。
- 被拒绝：在 `_execute_rebalance` 里顺手清理 → 无再平衡时永不触发。
- 代价：每个交易日一次 O(n) 扫描（n = 在途订单数，通常 < 10）。

### D8 不改变 `_last_target_stocks` 与 `unclosed_positions` 语义

- 理由：两者用于报告「调出却卖不掉」，与本次账目修复正交。
- 代价：无。

### D9 新增 golden case G7（V2 停牌），不改 G3

- 理由：G3 已锁定「涨停掩码」行为；停牌是独立场景，独立 case 便于定位回归。G3 的既有基线若因 L1 变化而变动，按 A20 单独说明并重录。
- 被拒绝：把停牌塞回 G3 → 一个 case 覆盖两种掩码，diff 不可归因。
- 代价：`CASE_IDS` 6 → 7，golden 断言 +1，基线文件 +1。

### D10 用性质测试（不变量）而非逐笔快照锁定修复

- 理由：修复的目标是「账目性质」，不是某个具体成交序列；性质测试对价格构造不敏感。
- 被拒绝：只加 golden → golden 会被「重录」绕过，无法区分「修好了」与「又变了」。
- 代价：测试需构造可复现的停牌场景（复用 P-013 夹具能力）。

## 3. 不变量（本批验收判据）

| ID | 不变量 | 检查方式 |
|----|--------|----------|
| **I1** | 两条路径的 `invariant_report.ok == True`（I2 违规 0） | 运行结果字段 |
| **I2** | 任意快照的任意持仓 `quantity >= 0` | 遍历 `tracker.get_snapshots()` |
| **I3** | 任一笔 SELL 的成交量 ≤ 该笔执行前的持仓 | 按时间顺序重放 trades |
| **I4** | 同一 `(date, stock, side)` 不出现两笔 `quantity` 完全相同的成交 | trades 去重计数 |
| **I5** | 次日路径订单的存活自然日 ≤ `max_pending_days_{buy,sell}` | 队列快照 / 单测 |

## 4. 接口与改动点（设计层签名）

```python
# core/engine_v2.py

def _clamp_sell_quantity(self, order: PendingOrder) -> int:
    """SELL 按可卖持仓夹紧；BUY 原样返回。纯读，无副作用。"""

def _cancel_next_day_orders(
    self, date: pd.Timestamp, stocks: Optional[set[str]] = None
) -> int:
    """撤销次日订单（队列路径 cancel_orders 的对应物）；返回撤销数。"""

def _expire_next_day_orders(self, date: pd.Timestamp) -> int:
    """按 max_pending_days_* 过期次日订单；返回过期数。"""
```

```python
# core/pending.py
def cancel_order(self, order: PendingOrder, cancel_date: pd.Timestamp) -> bool:
    """取消单个 PENDING 订单并记事件；非 PENDING 返回 False。"""
```

**调用点**：
| 位置 | 改动 |
|------|------|
| `_process_pending_orders`（≈L661-706） | SELL 前夹紧；`qty<=0` → `cancel_order` 并跳过；执行用 `execute_order(..., qty, ...)` |
| `_execute_next_day_orders`（≈L953-1020） | 入口先 `_expire_next_day_orders`；SELL 前夹紧；`qty<=0` → 丢弃并告警 |
| `_execute_rebalance`（≈L776-780） | `else` 分支调用 `_cancel_next_day_orders(date, set(signal_df.columns))` |

## 5. 数据流

```
再平衡日 T:
  _execute_next_day_orders(T)      ← 先过期（D7）→ 再执行（含夹紧 D6）
  _process_pending_orders(T)       ← 队列路径（含夹紧 D6）
  _execute_rebalance(T)            ← L1：先撤在途（队列 or 次日），再算目标、生成新单
```

## 6. 风险与回退点

| 风险 | 概率 | 缓解 |
|------|------|------|
| G1-G6 基线因 L1 变化 | 中（G3 含被涨停阻断的买单，见 RESEARCH §4.5） | 逐 case 对照 diff、在 IMPL §8 说明合理性后重录；非「重录了事」 |
| 撤单导致两路径成交差异扩大 | 低 | U-P014-2 登记；以不变量与关键指标（非逐笔）为验收 |
| 夹紧在正常路径误触发 | 极低 | 触发即 `logger.warning`，Step 9 全量回归中若出现告警即视为异常 |
| 过期误杀有效订单 | 低 | 仅当订单跨 ≥5（买）/≥10（卖）自然日仍未成交时触发 |

**回退点**：三个调用点互不依赖，可按 D1 三层分别回退；回退后最坏恢复为当前行为（负持仓），无数据损坏风险。

## 7. 派生需求预登记（Step 8 核对）

| ID | 派生需求 | 来源 |
|----|----------|------|
| DR-1 | `PendingOrderQueue.cancel_order` 新 API | D4 |
| DR-2 | `_clamp_sell_quantity` 的 `qty == 0 → 作废` 分支 | D6 |
| DR-3 | G7 的 `CASE_IDS` / `CASES` / `build_case` 扩展 | D9 |
| DR-4 | 夹紧告警日志文案（便于 E4 扫描） | D6 |

## 8. Step 4 Review（设计文档幻觉抑制，独立 pass）

> **审查基座**: 本会话 DeepSeek-V4.1-Flash（同基座）；RULE-4 = 自查（单视角）

| 检查项 | 方法 | 结果 |
|--------|------|------|
| 设计基于已验证的调研结论 | 逐条回链 RESEARCH §3/§4 | ✅ D1←§4.4；D2←§4.2；D9←§4.5；D10←§6 |
| 无未经验证假设 | 检查「队列路径撤单集合」「过期字段存在」两处 | ✅ `engine_v2.py:778` 与 `config.py:375-376` 已回读 |
| 无归因扭曲 | 复核「缺陷仅次日路径」是否被简化为单因 | ⚠️ 见 F-D-P014-1：另两路径**也有**同类隐患（夹紧缺失），不能宣称「仅一条路径有问题」，已改述为「默认路径靠撤单规避」 |
| 替代方案 ≥2 且被否决 | 检查 D1-D10 | ✅ 每项均列被拒方案与代价 |
| 职责边界清晰 | §1 非目标 | ✅ 职责外（停牌语义/买侧现金/部分成交/空头）与能力边界（真实撮合一致性）均已声明 |

**发现（1 项，已回写）**

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-D-P014-1 | P2 | 初稿把「停牌账目缺陷只存在于次日路径」写成单因，忽略「队列路径同样无持仓夹紧，只是靠撤单规避」 | §1/D2 改为「两条路径共享夹紧防线」；RESEARCH §5 已含该表述 |

**结论**：P1=0 / P2=1（已回写）/ P3=0；**可进入 Step 5 IMPL**。
