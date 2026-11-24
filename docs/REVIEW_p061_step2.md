# REVIEW：P-061 Step 2 异构复审（RESEARCH_p061_observability_traceability）

> **复审人**：GLM-5.3-Flash（≠ RESEARCH 作者 DeepSeek-V4.1-Flash，RULE-5 异构成立）
> **对象**：[RESEARCH_p061_observability_traceability](RESEARCH_p061_observability_traceability.md)（含 §13 详细方案分析）
> **基线**：`4367775`（P-060a 关闭；collect 1557 / golden 22 / p059 63 / mypy 160·0 / black 330）
> **裁决输入**：用户 2026-11-24「按这个方案来」→ U-P061-1..7 按建议列全部闭合（M-B 三期 + 允许最小 seam + stop 接入独立批次）
> **结论**：**PASS-WITH-COMMENTS** —— 0×P0 / 0×P1 / **4×P2 / 4×P3**，全部当轮修订落回 RESEARCH（沿 U-P060-4 裁决口径：P1/P2 当批修，P3 登记）；文档级修订，零生产代码变更。

---

## 1. 复核方法

1. **事实核对**：对 RESEARCH 的 E1-E9、O1-O4、§13.1 钩点行号、§13.2 可用性表逐条与源码比对（`core/engine_v2.py` / `core/pending.py` / `core/rebalance.py` / `core/tracker.py` / `core/target_positions.py` / `core/execution.py` / `core/manifest.py` / `scripts/change_report.py` / `output/trades.csv` 样例）。
2. **覆盖面审查**：以「订单对象的一生」为轴（创建 → 入队/入列 → 重试/跳过 → 成交/取消/过期）穷举 `engine_v2` 全部分支，检验 §13.3 SEAM 清单与 §13.4 表结构是否完备。
3. **时序审查**：核对 run 主循环、末日三连（snapshot → force_liquidation → refresh_last_nav）与 DAY_END 发射点的相对顺序。

## 2. 确认无误项（抽样举证）

| 项 | 复核结果 |
|---|---|
| E1 `REBALANCE` 载荷 | ✅ L1572-1578 仅 `{date, n_targets}` |
| E2 `DAY_END` 载荷 | ✅ L802-808 仅 `{date, total_value}` |
| E3 `Trade` 无 reason | ✅ [execution.py](../core/execution.py#L26-L40) 字段集属实 |
| E4 stops 零接入 | ✅ `core/`、`strategies/` 内无 `apply_stops` 调用 |
| E5 无 trace 主键 | ✅ 全仓仅 manifest 有 `run_id` |
| O1 波动率触发死分支 | ✅ L784-788 仅传 `signal`/`portfolio_value` |
| O2 L4 reason 恒 `rebalance` | ✅ `PendingOrder` 无 `reason` 属性，`getattr` 恒默认 |
| O3 旧 trades.csv 缺 `net_amount` | ✅ `output/trades.csv` 头为 `stock,side,quantity,price,date,amount,cost`，与现 `TradeLog.get_trades_df`（date 起、含 net_amount）列集不一致 |
| §13.2 因子/目标/掩码可用性 | ✅ `daily_signal`（L1338）、`TargetPosition`（[target_positions.py](../core/target_positions.py#L22-L40)）、掩码（L1162-1163/L1341）均在钩点作用域内 |
| §13.4.1 run_id 时序 | ✅ `uuid4` 在 `build_manifest` 调用时生成（[manifest.py](../core/manifest.py#L160-L162)），运行结束才发生，主键修订必要性成立 |

## 3. 发现清单

> 分级：**P2 = 方案设计错误/覆盖缺口，不修则 B2 产物不可信**；P3 = 计数/口径/文档精度问题。全部当轮闭合。

### F1（P2）SEAM-3 漏计两处订单创建位：实际共 4 处

- **证据**：除再平衡创建（[engine_v2.py](../core/engine_v2.py#L1686-L1698)）外：
  - `_queue_urgent_order`（[L515-L531](../core/engine_v2.py#L515-L531)）：强平/换月经 `create_pending_order` 新建订单入次日队列，带 `_kind ∈ {liquidation, roll}` 豁免标记；
  - `_try_fallback_order`（[L1297-L1302](../core/engine_v2.py#L1297-L1302)）：新建 `fallback_order` 并**立即**经 `execute_pending_order` 成交。
- **影响**：SEAM-3 只标 rebalance 创建位会漏掉期货强平/换月与 fallback 订单的 `order_seq` 分配。
- **处置**：§13.3 SEAM-3 修订为「4 处创建位」。

### F2（P2）trace_order 的执行字段不能取自 order 对象：次日路径成功后从不 `mark_executed`

- **证据**：次日路径成交分支（[L1799-L1805](../core/engine_v2.py#L1799-L1805)）仅 `tracker.execute_trade(trade)` + 计数，**无 `mark_executed` 调用**；`status` 停留 `PENDING`、`execute_date/execute_price` 保持 `None`、`_filled_qty` 不更新。队列路径才有 `mark_executed`（L1239）。
- **影响**：§13.4.2 `trace_order.execute_date/execute_price/filled_qty` 若以 order 字段为源，次日路径（`enable_pending_orders=False` 默认路径）全错。
- **处置**：§13.4.2 修订——执行字段以 **SEAM-5 成交关联为唯一事实源**；order 字段仅队列路径可用，标注路径差异。

### F3（P2）fallback 成交跨标的：order→fill 关联需支持「原单成交于替补标的」

- **证据**：[L1302-L1307](../core/engine_v2.py#L1302-L1307)——fill 是 `fallback_stock` 的成交，但 `mark_executed(original_order, date, trade.price)` 把**原单**标记为已执行，并回写 `original_order.fallback_stock = fallback_stock`。
- **影响**：一笔 fill 同时涉及两个 order_ref（fallback_order 与 original_order）；若只按「一 fill 一 order」建模，fallback 场景对账会重/漏。
- **处置**：§13.4 补充——`trace_fill` 增加可空 `replaces_order_ref`；原单行记 `status=executed_by_fallback`（或保留 executed + `fallback_stock` 列），并在 §13.3 SEAM-5 明确双登记。

### F4（P2）末日时序：SEAM-6/-7 挂点早于强平，末行持仓/NAV 不含最终平仓

- **证据**：run 主循环（[L695-L702](../core/engine_v2.py#L695-L702)）在末日依次执行 `_process_trading_day`（内含 DAY_END 发射 L802-808）→ `_snapshot_unclosed_positions`（[L871-L887](../core/engine_v2.py#L871-L887)）→ `_force_liquidation`（直接 `execute_order`，无订单对象，[L947-L954](../core/engine_v2.py#L947-L954)）→ `_refresh_last_nav`（[L859-L869](../core/engine_v2.py#L859-L869)，**仅**经 `LayerDumper.update_last_nav` 刷 L6）。
- **影响**：SEAM-7 若只挂 DAY_END，末日 `trace_day` 行显示强平前持仓；`trace_fill` 的 final_liquidation 成交与之矛盾。这正是六层 dump 用 `update_last_nav` 覆写末行的原因。
- **处置**：§13.3 增补——trace 需在 `_refresh_last_nav` 同位增加**末行覆写**（或 finalize 阶段统一回填末行持仓/NAV），与 `update_last_nav` 语义对齐。

### F5（P3）SEAM-4 打点计数 12 → 14

- **证据**：队列路径 7 处（buyable L1171 / sellable L1175 / BTC 无持仓 L1184 / 夹紧 L1193 / 无开盘价 L1198 / 无效价 L1209 / 现金不足 L1221）；次日路径 7 处（BTC 无持仓 L1750 / mask L1757+L1761 / 无开盘价 L1765 / 无效价 L1771 / 现金不足 L1784 / 夹紧丢弃 L1789）。
- **处置**：§13.3 SEAM-4 计数修订为 14 处（另加执行失败 else 分支 2 处为状态终态记录，非拒单码）。

### F6（P3）S9 退出码「2=缺产物」与 `change_report` 实际语义不符

- **证据**：[change_report.py](../../scripts/change_report.py#L7-L48) 退出码**仅 0/1**；层缺失由 `MissingLayerError` 未捕获异常呈现（进程退出码 1）。
- **处置**：S9 修订为 0/1 对齐；若保留 2 需显式捕获并自行定义，文档注明与 `change_report` 的差异。

### F7（P3）liquidation/roll 订单豁免取消与过期，状态机需注明

- **证据**：[L1089-L1091](../core/engine_v2.py#L1089-L1091)（撤销豁免）、[L1122-L1124](../core/engine_v2.py#L1122-L1124)（过期豁免）。
- **处置**：S4 状态机补注：`_kind ∈ {liquidation, roll}` 订单**永不**进入 `cancelled/expired`；且再平衡日的 `cancelled` 是批量发生（`cancel_orders` [L1330-L1335](../core/engine_v2.py#L1330-L1335) / `_cancel_next_day_orders`）。

### F8（P3）trace_fill.order_ref 需允许 `direct`：强平/退市成交无订单对象

- **证据**：`_force_liquidation` 直接 `execute_order`（[L947-L949](../core/engine_v2.py#L947-L949)），全程不创建 `PendingOrder`；退市结算复用同路径（L1011-1017）。
- **处置**：§13.4.2 修订——`order_ref` 允许 `"direct"` 哨兵值；`alignment.json` 的 `counts.orders ≠ fills` 属合法态（差额=直接成交数），对账规则相应放宽并显式记录 `direct_fills` 计数。

## 4. 修订落点（已全部落回 RESEARCH）

| 发现 | 落点 |
|---|---|
| F1 / F5 | §13.3 SEAM-3（4 处创建位）、SEAM-4（14 处） |
| F2 | §13.4.2 trace_order 执行字段事实源改为 SEAM-5 |
| F3 | §13.4.2 trace_fill 增 `replaces_order_ref`；SEAM-5 双登记 |
| F4 | §13.3 设计要点 + §13.7 B2 验收：末行覆写（仿 `update_last_nav`） |
| F6 | §6 S9 退出码 0/1 |
| F7 | §6 S4 状态机补注 |
| F8 | §13.4.2 order_ref=`direct` + §13.4.3 对账规则 |
| F-09（落修订时自查，P3） | §6 S1 旧主键 `run_id:{date}:{stock}` 与 §13.4.1 矛盾 → 已对齐为 `{date}|{stock}` + alignment 关联 |

## 5. 遗留与下一步

- **零 P0/P1**；9 项发现（F-01..F-09，F-09 为落修订时自查）当轮闭合，RESEARCH §14 增设修订记录。
- F2/F3/F8 共同指向同一设计修正：**以成交为事实源、订单为过程记录**——已作为 DESIGN 阶段输入写入 §14。
- **下一步**：Step 3 DESIGN（按已闭合的 U-P061-1..7 与 §14 修订后的 S/I 规格）。
