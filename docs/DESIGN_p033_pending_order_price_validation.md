# DESIGN：P-033 待执行订单价格有效性（守卫单点 + VWAP 覆盖）

> **批次**: P-033 · **T1**（`core/execution.py` + `core/engine_v2.py` + `agents/multi_strategy_engine.py`）
> **状态**: **Step 3 完成**（2026-11-16，基线 HEAD `d9f821b`）
> **作者基座**: DeepSeek-V4.1-Flash（= RESEARCH 作者；Step 4 复审须异构，RULE-5）
> **上游**: [RESEARCH_p033](RESEARCH_p033_pending_order_price_validation.md)（§3 R1-R3 / §6 调用点全表 / §7 方案 M-A / §11 Step 2 异构 Review pass 六项裁决）
> **设计对象**: 执行入口价格契约（`execute_order`）+ 两引擎 queue 路径可观测过滤；`tracker` / `PendingOrderQueue` / `interfaces` 零改动

---

## 1. 设计目标

把「价格不可用」的**唯一正确语义**（不成交、不入账、订单保留重试）下沉到账目入口，并用**单点守卫**覆盖全部价格通道（含 VWAP 内部聚合），修复三项缺陷：

| 缺陷 | 级别 | 设计出口 |
|------|------|----------|
| R1 开盘价 `NaN`/`±inf` → cash 永久 NaN（BUY 与 SELL 双侧，SELL 还静默清零持仓） | **P1** | **D1** `execute_order` 解析价守卫 + **D2** 两引擎 queue 前置过滤 |
| R2 开盘价 `≤0` → 免费持仓 / 幻影现金（`0` 零成本建仓、`-5` 现金 +500） | **P2** | 同 D1/D2（同一守卫条件 `price > 0`） |
| R3 `close=0` → 差异告警 `inf%`（无账目污染） | P3 | **D6** 仅登记，不改判定 |
| N1 次日路径已防护 / B1 VWAP 第二 NaN 入口 | — | **D1** 守卫置于「解析后」，天然覆盖 VWAP/CLOSE/CUSTOM/未知类型回退 |

**约束**：合法价路径**逐字不变**（golden 13 条零重录）；公开签名零变更；`except Exception` 合计恒 22；`tracker` 与 `interfaces` 零改动。

---

## 2. 调研结论 → 设计映射

| RESEARCH / Step 2 | 设计落点 | 落点依据 |
|-------------------|----------|----------|
| R1 + R2（无效价入账） | **D1** §4.1 | 账目唯一入口 `execute_order`（六直接调用 + 一委托链全经此处，§6 全表） |
| B1 VWAP 第二入口 | **D1** §4.1 + **D3** §4.4 | 守卫作用于 `_get_execution_price` 的**返回值**，而非入参 `open_price` |
| queue 路径无计量 | **D2** §4.2/4.3 | agents 新键 `pending_invalid_price`；V2 复用 `skipped_price`（Step 2 裁决 #3） |
| 重试噪声 bounded（B3） | **D5** §3.5 | `mark_expired` 半衰期兜底（约 4 交易日排空），不新增降噪机制 |
| 5 调用点 `False` 语义 | **D4** §3.4 | 逐一核对：V2 queue / next-day / agents 两路径 / agent_framework / fallback 委托 |
| R3 `close=0` | **D6** §3.6 | 仅登记（无账目污染） |
| 次日路径既有守卫 | **D3** §4.4 | **不重构**（避免无收益改动与 golden 风险） |

---

## 3. 决策详述

### D1（修 R1 + R2）：`execute_order` 解析价守卫（单点）

**决策**：在 `core/execution.py::execute_order` 中，`execution_price = self._get_execution_price(...)` **之后**、收盘价差异告警**之前**插入守卫：

```python
            # P-033 D1：执行价格有效性守卫（None / NaN / ±inf / <=0 → 不成交、不入账）
            if not is_valid_price(execution_price):
                logger.warning(
                    f"{stock}在{date}执行价格无效: {execution_price!r}，"
                    "订单未成交（P-033 价格守卫）"
                )
                return False, None
```

新增模块级纯函数（`core/execution.py`，`Trade` 定义之后、`ExecutionSimulator` 之前）：

```python
def is_valid_price(price: Optional[float]) -> bool:
    """价格是否可成交：有限且为正。None / NaN / ±inf / <=0 均视为无效。"""
    if price is None:
        return False
    return bool(np.isfinite(price) and price > 0)
```

**为什么守卫「解析后价格」而不是入参 `open_price`**：
- `_get_execution_price` 有 **5 条分支**（OPEN / CLOSE / VWAP / CUSTOM / 未知回退），VWAP 用 `sum(prices)/len(prices)` 聚合（L238）——**入参全合法仍可能聚合出 NaN**（Step 2 B1 实锤 `success=True, price=NaN`）；CLOSE 分支的 `close_price=NaN` 也不是 `None`（L222 不回退）；CUSTOM 分支仅判 `>0` 不判有限（L246）。
- 守卫只认最终入账价 → **一个判定覆盖全部 5 条分支与未来新增分支**，无遗漏面。

**为什么不放在 `tracker.execute_trade`**：账目层堵漏会掩盖上游数据错误（P-031 O-P031-1 已登记），且 V3 共用该层；执行入口是「成交是否成立」的正确判定层。

### D2（修 R2 的可观测）：两引擎 queue 路径前置过滤 + 计量

**决策**：在**两处 queue 主路径**的「成员检查之后、`execute_order` 之前」插入同形过滤，使用同一 `is_valid_price`（单一口径）：

| 引擎 | 落点 | 代码 | 计量 |
|------|------|------|------|
| agents | `_process_pending_orders` L508 之后 | `if not is_valid_price(open_price): self._record_failure("pending_invalid_price"); continue` | 新键 `pending_invalid_price` |
| V2 | `_process_pending_orders` L803 之后 | `if not is_valid_price(open_price): skipped_price.append(order.stock); continue` | 复用既有 `skipped_price` 名单（L780 定义 / L836-839 汇总日志） |

**为什么引擎层还要过滤（D1 已兜底）**：
1. **可归因**：D1 只打 warning，无法被 `failure_counts` / 既有 skipped 名单聚合；引擎层计数让「本次回测有多少单因价格无效被拒」可对拍（P-026/P-029 治理口径）。
2. **语义一致**：两引擎的 **next-day 路径已按 `open_price` 拒绝**（agents L451 / V2 L1140），queue 路径按同一口径过滤后，**两条路径行为对称**（R-P033-1）。
3. **不重复实现**：判定函数 `is_valid_price` 单一来源，引擎与 executor 共用，无 P-031 F-S4 型「两份同形判定漂移」。

**为什么不预过滤 `close_price`**：queue 路径的执行价默认取 `open_price`；`close_price` 仅用于差异告警与 CLOSE 类型。D1 已在 executor 内覆盖 CLOSE 分支的无效 close。

### D3（范围裁决）：次日路径与强平路径不重构

两引擎 next-day（agents L451 / V2 L1140）与 V2 强平（L563）**已有等价的 inline 判定**（Step 2 B4 实证 `liquidated=0`）。本批**不改这三处**：
- 改则需统一为 `is_valid_price`，收益仅为代码复用，但触及 golden 敏感路径；
- D1 守卫在其下游兜底，存在双保险，无遗漏风险。

登记为设计期观察（O-D-P033-1）。

### D4（回归面）：`False` 返回的调用方语义（逐一核对，Step 2 裁决 #6）

| 调用点 | `False` 分支现状 | 结论 |
|--------|------------------|------|
| V2 queue L815 | 不入 `executed_orders`；订单不 `mark_executed` → 留队重试 | ✅ 正确 |
| V2 next-day L1161 | 入 `failed_orders` → 次日重试 | ✅ 正确 |
| V2 强平 L566 | `if success and trade` 才入账 → 该股本日不强平 | ✅ 正确（且 D3 前已有 L563 守卫，不触发） |
| agents next-day L463 | 同上，入 `failed_orders` | ✅ 正确 |
| agents queue L520 | 不 `mark_executed` → 留队（本批新增前置过滤后通常不进入此分支） | ✅ 正确 |
| agent_framework L1420 | `if success and trade` 才 `tracker.execute_trade` | ✅ 正确 |
| fallback 委托 L884 | `fallback_success=False` → 不标记完成 | ✅ 正确 |

**无一处依赖「无效价必成交」** → D1 返回 `False` 不产生任何调用方语义变更。

### D5（重试噪声）：不新增降噪机制

Step 2 B3 实测：全程无效价下，queue 长度在第 4 个交易日归零（`mark_expired` 半衰期 3 + `max_pending_days_buy=5` 兜底）。因此：
- 每个无效价订单最多产生 **≤4 条** guard warning（可接受）；
- 不新增限流 / 去重 / 熔断（避免过度工程，U-P026-4 同口径）。

### D6（R3 与观察项）：仅登记

| 项 | 处置 |
|----|------|
| R3 `close=0` → `inf%` 告警 | 不改判定（无账目污染）；告警文案改进属独立 T3 候选（U-P033-1） |
| CUSTOM 分支 `inf` 通过 `>0`（L246） | D1 守卫已覆盖（解析后判有限），不另改 CUSTOM |
| `agent_framework:1420` 上游 L1340 仅成员检查 | D1 单点覆盖，不在该文件加计量（超出 T1 观测需求，O-D-P033-2） |

---

## 4. 实现规格（逐函数）

### 4.1 `core/execution.py` —— 新增 `is_valid_price` + 守卫

| 位置 | 变更 |
|------|------|
| 模块级（**`ExecutionSimulator` 类定义之前**，即 L152/153 空行处——`Trade`（L25-50）与 `ExecutionSimulator`（L153）之间为 `TradeLog` 类 L52-150，Step 4 F-S4-P033-1 精化） | 新增 `is_valid_price(price: Optional[float]) -> bool`，实现见 D1 |
| `execute_order` L292-294 之后 | 插入守卫块（4 行，含 warning + `return False, None`） |
| `execute_order` docstring（L274-289） | 补一句：「若解析后的执行价格为 `None` / `NaN` / `±inf` / `≤0`，返回 `(False, None)`，不写入 `trade_log`」 |

**约束**：守卫在 `try` 块内（沿用既有异常漏斗）；新增代码**零 `except`**；`np` 已导入（L16），不新增依赖。

### 4.2 `agents/multi_strategy_engine.py` —— queue 前置过滤

| 位置 | 变更 |
|------|------|
| 导入行 L32 | `from core.execution import ExecutionSimulator` → `from core.execution import ExecutionSimulator, is_valid_price` |
| `_process_pending_orders` **L509 之后（`close_price` 赋值完成）、L511 夹紧块之前**（Step 4 F-S4-P033-1 精化） | 插入 3 行：`if not is_valid_price(open_price):` / `self._record_failure("pending_invalid_price")` / `continue` |

### 4.3 `core/engine_v2.py` —— queue 前置过滤

| 位置 | 变更 |
|------|------|
| 导入行 L23 | `from core.execution import ExecutionSimulator` → `from core.execution import ExecutionSimulator, is_valid_price` |
| `_process_pending_orders` **L808 之后（`close_price` 多行赋值完成）、L810 之前**（Step 4 F-S4-P033-1 精化） | 插入 3 行：`if not is_valid_price(open_price):` / `skipped_price.append(order.stock)` / `continue` |

**不改**：`_force_liquidation` L563、V2 next-day L1140、agents next-day L451（D3）。**顺序注记（Step 4）**：V2 queue 内部为 clamp（L792）→ 成员检查（L799）→ 取价（L803-808），与 agents（成员 → 取价 → 夹紧）顺序不同——既有语义，插入点均在 `execute_order` 之前，不受影响。

### 4.4 `execute_order` 守卫与 VWAP 的覆盖关系（B1 复核点）

| 执行价格类型 | 解析价来源 | D1 守卫是否覆盖 |
|--------------|------------|-----------------|
| OPEN（默认） | `open_price` | ✅ |
| CLOSE | `close_price`（`None` 回退 open；`NaN` 不回退） | ✅ |
| VWAP | `sum(prices)/len(prices)`（含 NaN 即 NaN） | ✅（**B1 实锤**） |
| CUSTOM | 回调值（仅判 `>0`，不判有限 → `inf` 通过） | ✅ |
| 未知类型 | 回退 `open_price`（L259-260） | ✅ |

---

## 5. 不变式 I1-I7

| ID | 不变式 | 验证出口 |
|----|--------|----------|
| I1 | 任何 `Trade` 的 `price` 恒为有限正数（守卫后置条件） | V1 / V7 |
| I2 | 无效价 → `trade_log` 不增、`cash`/持仓零变化、订单保留 | V2 / V3 / V4 / V6 |
| I3 | 合法价路径逐字不变（golden 13 条零重录，731 既有测试全绿） | V8 / B4 门禁 |
| I4 | 调用方语义保持（不 `mark_executed` / 入 `failed_orders` / 不强平） | V2 / V5 / V6 |
| I5 | 公开签名零变更；新增模块级函数不属公开 API 变更；`except Exception` 恒 22 | B4 AST |
| I6 | 计量：agents +1 键 `pending_invalid_price`；V2 复用 `skipped_price`；零新出口 | V2 / V6 |
| I7 | 门禁：**731 → 748 passed** / 测试文件 **82 → 83** / black **119 → 120** / mypy **37 files 0** / golden 13 零重录 | B4 |

---

## 6. 验证契约 V1-V8（17 实例）

| ID | 用例 | 构造 | 断言 |
|----|------|------|------|
| V1 | 守卫矩阵（参数 6） | 直接调 `execute_order`，`open_price ∈ {None, NaN, inf, -inf, 0.0, -5.0}`，零成本 | 全部 `(False, None)`；`trade_log.get_trades() == []`；无异常 |
| V2 | agents queue NaN / 0（参数 2） | 100 股 BUY 单入队；开盘价 NaN / 0；零成本 | 零成交；`cash == 10,000,000`；订单仍在队（`get_pending_orders()` 长度 1）；`pending_invalid_price == 1` |
| V3 | agents queue 负价（参数 2） | `open=-5` / `-inf` | 零成交；`cash` 不变；`pending_invalid_price == 1`（覆盖 R2「现金 +500」） |
| V4 | agents queue SELL NaN（持仓保留） | 先建仓 100 股，再入 SELL 100 单，`open=NaN` | 零成交；`qty == 100`（**不清零**）；`avg_cost == 10`；`cash` 不变 |
| V5 | 重试 bounded | 全程 `open=NaN`，逐日跑 `_process_pending_orders` + `mark_expired` 8 日 | 订单在 ≤5 交易日内出队（`is_expired` 兜底）；总成交 0；`pending_invalid_price` 计数等于实际尝试天数 |
| V6 | V2 queue NaN / 0（参数 2） | V2 `_process_pending_orders` 注入 1 张 BUY 单 | 零成交；`cash` 不变；`skipped_price` 含该股——**经 `caplog` 断言汇总日志「跳过N个缺少价格数据订单: A」（L836-839），`skipped_price` 为局部名单不可直接访问（Step 4 F-S4-P033-2 精化）** |
| V7 | VWAP NaN（B1 回归锁） | `ExecutionPriceType.VWAP` + `high/low/volume=NaN`，open/close 合法 | `(False, None)`；`trade_log` 空（**第二入口已封**） |
| V8 | 正常路径零误报（参数 2：agents / V2） | 合法价 10；agents queue 1 张 BUY、V2 queue 1 张 BUY | 成交 1 笔 `price=10`；`pending_invalid_price` 缺席或 0；`skipped_price` 空 |

**红态纪律**：B1-B3 逐批先红后绿；V8 在红态即通过属回归保护，须显式标注（P-031 F-S9-P031-3 先例）。

---

## 7. 风险、未决与观察

| ID | 类型 | 内容 | 处置 |
|----|------|------|------|
| R-P033-1 | 风险 | 引擎 queue 预过滤按 `open_price` 判定（与 next-day 同口径）——非 OPEN 执行类型下「open 无效但 close 有效」由成交变拒绝 | **有意**：路径对称优先；与 next-day 既有行为一致，文档披露 |
| R-P033-2 | 风险 | `skipped_price` 名单语义由「成员缺失」扩展为「成员缺失 ∪ 价格无效」 | 汇总日志文案「缺少价格数据」仍适用；不新增键 |
| R-P033-3 | 风险 | guard warning 频次 | B3 实测 ≤4 交易日排空，不限额流（D5） |
| U-P033-1 | 未决 | R3 `close=0` 告警文案（`inf%`） | 不改；T3 候选 |
| U-P033-2 | 未决 | BUY 侧现金夹紧 | 与 U-P031-2 / U-P014-3 同列，独立批 |
| U-P033-3 | 未决 | 账目层（`tracker.execute_trade`）价格守卫 | 与 O-P031-1 同列，不采纳（D1 理由） |
| O-D-P033-1 | 观察 | 次日/强平路径 inline 判定未统一为 `is_valid_price` | 不改（D3）；若未来重构统一 |
| O-D-P033-2 | 观察 | `agent_framework:1420` 上游缺校验（仅成员检查） | D1 覆盖；不额外加计量 |

---

## 8. 批量切分与回退点

| 批 | 内容 | 修复 | 回退 |
|----|------|------|------|
| **B1** | `core/execution.py`：`is_valid_price` + 守卫 + docstring；测试 V1/V7 | R1/R2 根因 | 单函数回退（守卫块 + 函数） |
| **B2** | `agents` queue 前置过滤 + `pending_invalid_price`；测试 V2/V3/V4/V5/V8(agents) | R1/R2 可观测 | 3 行回退 + 删键 |
| **B3** | `core/engine_v2.py` queue 前置过滤（复用 `skipped_price`）；测试 V6/V8(v2) | R1/R2 覆盖默认引擎 | 3 行回退 |
| **B4** | 全量门禁 + 文档回填（IMPL/CHECKLIST/PROGRESS/CHANGELOG） | — | docs |

B1 必须最先（B2/B3 依赖 `is_valid_price`）；B2/B3 相互独立。

---

## 9. 设计期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-D3-P033-1 | 观察 | `execute_order` 的 CLOSE 分支对 `close_price=NaN` **不回退**（L222 只判 `None`），是 VWAP 之外的第二类「入参合法、解析价无效」形态 | D1 解析后守卫已覆盖；不单独改 CLOSE 分支 |
| F-D3-P033-2 | 观察 | `interfaces.py::IExecutionSimulator` 无需新增 `is_valid_price`（模块级函数，非协议方法），协议零改动 | 已落实于 D1 |

---

## 10. 下一 Step

**Step 4 独立 Review（异构基座 GLM-5.3-Flash，RULE-5）**——本文件作者 DeepSeek-V4.1-Flash。复核重点：

1. **守卫位置**：解析后 vs 入参的取舍是否成立（CLOSE/CUSTOM/VWAP 三分支的覆盖论证，F-D3-P033-1）；
2. **双层过滤是否冗余**：D1 + D2 是否属于过度工程，还是可观测性必需（对比 M-C）；
3. **引擎预过滤口径**：按 `open_price` 过滤与 next-day 一致（R-P033-1）是否可接受；
4. **计量键名与出口**：`pending_invalid_price` 与 V2 `skipped_price` 的不对称是否有更优解；
5. **测试规格**：V1-V8 是否覆盖 R1/R2/R3 与 B1-B4 形态，红态豁免（V8）是否标注；
6. **门禁目标**：748 / 83 / 120 / 37 / golden 13 零重录的口径是否由 17 实例推算正确。

---

## 12. Step 4 独立 Review 记录（异构基座 GLM-5.3-Flash，2026-11-16）

> **复审基座**: **GLM-5.3-Flash**（≠ 本文件作者 DeepSeek-V4.1-Flash，RULE-5 成立）
> **复审对象**: `9d3e4d7`（DESIGN_p033 提交版）；复审时点 HEAD `470efea`
> **方法**: E1 锚点机械复核 + E2 独立探针（`%TEMP%\p033_step4_review_probe.py`，C1-C5）+ E3 §10 六项裁决

### 12.1 E1 锚点机械复核

| # | DESIGN 声称 | 实查 | 结果 |
|---|-------------|------|------|
| A1 | 守卫插入点 `execute_order` L292-294 之后、`try` 块内 | 读码 | ✅ |
| A2 | CLOSE 分支 L221-225 仅判 `None`（NaN 不回退） | 读码 | ✅（C1 实锤） |
| A3 | VWAP L238 `sum/len` 聚合 | 读码 | ✅（Step 2 B1 已实锤） |
| A4 | CUSTOM L246 仅判 `>0`（`inf` 通过） | 读码 | ✅（C2 实锤） |
| A5 | `np` 已导入 execution.py L16；新函数零 `except` | 读码 | ✅ |
| A6 | agents 导入 L32 / 过滤点 L508 | 读码 | ⚠ 精化——精确锚点为 **L509 之后、L511 夹紧块之前** → F-S4-P033-1 |
| A7 | V2 导入 L23 / 过滤点 L803 | 读码 | ⚠ 精化——精确锚点为 **L808 之后（close_price 多行赋值完成）、L810 之前**；且 V2 内部顺序 clamp(L792) → 成员检查(L799) → 取价(L803-808) 与 agents 不同（既有语义，不影响插入） | 
| A8 | `is_valid_price` 置于「Trade 之后约 L50」 | **`TradeLog` 类占 L52-150**——精确锚点为 **`ExecutionSimulator` 类定义前（L152/153 间）** → F-S4-P033-1 |
| A9 | V2 `skipped_price` 名单（L780 定义 / L836-839 汇总日志） | 读码 | ✅；**但为局部列表无 getter** → V6 断言方式精化 F-S4-P033-2 |
| A10 | agents `_record_failure`（L126）可承接新键 | 读码 | ✅ |

### 12.2 E2 独立探针（C1-C5，全部实锤）

| 探针 | 构造 | 读数 | 结论 |
|------|------|------|------|
| C1 | CLOSE + open=10 合法、close=NaN | `success=True, price=nan, amount=nan` | **F-D3-P033-1 独立复现**——CLOSE 对 NaN 不回退，解析后守卫的必要性成立 |
| C2 | CUSTOM + 回调返回 `inf` | `success=True, price=inf` | **L246 缺口实锤**（仅判 `>0` 不判有限），解析后守卫覆盖 |
| C3 | CUSTOM + 回调返回 `None` | `success=True, price=10.0`（回退 open） | 既有正确行为基线（L248-250） |
| C5 | 未知类型（构造后属性变异） | `success=False, trade=None` | **新证（O-S4-P033-3）**：该分支正常构造**不可达**（`__init__` L183 即校验枚举 `.value`）；变异后存在「`logger.info` 的 `.value` AttributeError → `success=False` 但 trade 已入 `trade_log`」既有 quirk（L330 add_trade 先于 L332 日志）——纯理论面，不影响 D1，登记不改 |
| C4 | `is_valid_price` 语义表（V1 六值 + 10.0 + 1e-9） | 六无效值全 `False`、两合法值全 `True` | **V1 矩阵语义逐一对应**，守卫条件完备 |

### 12.3 E3 §10 六项裁决

| # | 复核点 | 裁决 |
|---|--------|------|
| 1 | 守卫位置 | **成立且必要**——C1（CLOSE NaN）+ C2（CUSTOM inf）实锤「入参合法、解析价无效」两类形态；入参守卫会漏。**维持 D1 解析后守卫** |
| 2 | 双层过滤冗余性 | **不冗余，维持 D1+D2**。D1 = 安全层（6 调用点 + 委托链 + 未来调用方 + VWAP）；D2 = 可观测层（`failure_counts` / skipped 归因，P-026~P-029 治理口径）。去 D2 则 queue 拒绝无计数；去 D1 则 agent_framework/委托链/VWAP 裸奔。两层共用 `is_valid_price` 无漂移。M-C 缺归因 |
| 3 | 引擎预过滤口径 | **可接受，维持 `open_price` 口径**：① 与 next-day 两路径既有行为对称；② 默认 OPEN 下即执行价；③ 非 OPEN 下「open 无效但 close 有效」被拒属保守收窄（D1 本会放行）——差异仅非默认配置，登记 O-S4-P033-1。备选 type-aware 过滤引入引擎↔executor 配置耦合，收益边际 |
| 4 | 计量不对称 | **维持**：V2 无 `_failure_counts` 基础设施（P-027 未下沉 V2；V2 用 DayErrorCollector + skipped 名单），强行对齐需 API 扩张。形态由既有基础设施决定 |
| 5 | 测试规格 | **覆盖成立**：V1 ↔ C4 语义表逐一对应；V4=O-S2-P033-1（SELL 清零）/ V5=B3（bounded）/ V7=B1（VWAP）三新证均有回归锁；V8 红态豁免已标注。**1 处精化**：V6 断言须经 caplog（F-S4-P033-2）。R3 无测试锚点可接受（D6 不改判定，O-S4-P033-2） |
| 6 | 门禁推算 | **全部正确**：731+17=**748** / 82+1=**83** / 119+1=**120**（新测试文件；`core/execution.py` 已计入 119）/ mypy 37 files 不变（无新文件）/ golden 13 零重录。提醒：新测试文件首轮须过 black（F-S9-P031-2 先例） |

### 12.4 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S4-P033-1 | P3 | 三处插入锚点不精确：§4.1「Trade 之后约 L50」——其间实为 `TradeLog` 类（L52-150）；§4.2「L508 之后」——精化为 L509 后 / L511 前；§4.3「L803 之后」——精化为 L808 后 / L810 前 | **当轮回写 §4.1-4.3**（已回写） |
| F-S4-P033-2 | P3 | V6 断言「`skipped_price` 含该股」不可直接断言——局部列表无 getter，须经 `caplog` 断言 L836-839 汇总日志 | **当轮回写 §6**（已回写） |
| O-S4-P033-1 | 观察 | 非 OPEN 执行类型下，引擎预过滤保守收窄（open 无效但 close 有效 → 拒绝；D1 单独会放行）——与 next-day 对称的有意选择 | 登记（裁决 #3） |
| O-S4-P033-2 | 观察 | R3（`close=0` 告警）无测试锚点——D6 不改判定、无行为可断言；U-P033-1 实施时须补 | 登记 |
| O-S4-P033-3 | 观察 | C5 新证：未知类型分支正常构造不可达（构造期枚举校验）；变异后「trade 已入账但 success=False」为既有 quirk（add_trade 先于 logger）——理论面，不影响 D1 | 登记不改 |

### 12.5 结论与 Step 5 前置条件

**结论**: **pass**（0 P0/P1/P2 / 2 P3 当轮回写 / 3 观察）——守卫位置论证经 C1/C2 实锤成立、双层过滤不冗余、预过滤口径可接受、计量形态合理、测试规格覆盖完备、门禁推算正确。准予进入 **Step 5 IMPL**。

**Step 5 IMPL 前置条件**:
1. 按 §4 精化后锚点实现：`is_valid_price` 置于 `ExecutionSimulator` 类前；agents 过滤块在 L509/L511 之间；V2 过滤块在 L808/L810 之间；
2. 守卫与前置过滤共用 `is_valid_price`（单一来源，双引擎导入同一名）；
3. 新测试文件（V1-V8，17 实例）完稿后先跑 `black`（F-S9-P031-2 先例）；
4. V6 断言用 `caplog`（L836-839 汇总日志文案）；V8 红态即通过须显式标注。
