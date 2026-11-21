# RUNBOOK：P-052 实盘安全闸门故障处置

> **批次**: P-052 · **S7 故障处置** · 日期 2026-11-21
> **上游**: [DESIGN_p052](DESIGN_p052_live_safety_gate.md) §3.1 / §4 D14；[IMPL_p052](IMPL_p052_live_safety_gate.md) §3.1 / §3.11
> **适用范围**: 程序化交易实盘运行期（真实通道未接入时用于演练，P-053 接入后按同表执行）
> **定位**: 自用交易工具 + 已完成券商程序化报备（D2）；本文不构成对外服务承诺

---

## 1. 四类故障处置表

`decide_fault(policy, fault, attempts)` 的确定性输出（`attempts` = 同类故障连续发生次数）：

| 故障 | 默认策略（`max_retries`） | 自动动作 | 人工动作 |
|------|---------------------------|----------|----------|
| 行情/交易断线 `DISCONNECT` | 3 | `attempts < 3` → `RETRY`；`≥3` → `PAUSE_NEW` + `RECONCILE` | 确认通道恢复、持仓与委托对账一致后，`gate_kill` 解除 PAUSE 语义 |
| 拒单 `REJECT` | 1 | `attempts < 1` → `RETRY`；`≥1` → `PAUSE_NEW` | 查拒单原因（资金/涨跌停/合规）；连续拒单达熔断阈值由 `consecutive_rejects → HALTED` 接管 |
| 部分成交 `PARTIAL_FILL` | 0 | `RECONCILE` | 核剩余数量与在途委托，必要时人工撤单后重下 |
| 柜台重启 `COUNTER_RESTART` | 0 | `CANCEL_ALL` + `RECONCILE` + `HALT` | 对账完成、确认柜台状态后按 §3 逐步恢复 |

> 红线：`HALTED` 不自动恢复；`DERISK_ONLY` 允许平仓、禁止开仓（`core/circuit_breaker.py` `allows_open/allows_close`）。

---

## 2. 一键停机流程

1. `gate_kill(KillLevel.GLOBAL, "", True, reason="manual_halt", ts=<exchange_ts>)`
   → 状态落盘 + `audit.kill`（payload 含 `operator`/`time_source`）；
2. `cancel_all(bridge, ts=<exchange_ts>)` → 调 `bridge.cancel_orders(None)`（取消全部未成交），返回取消笔数并写 `audit.cancel`（`cancelled_count`）；
3. 核对审计链：`-- 期望顺序 audit.kill → audit.cancel`，`seq` 单调、`replay` 可复现；
4. 通知责任人（自用场景：本人 + 券商客户经理），记录 `decision_id`。

**校验点**：`kill_decision.blocked == True` 且 `blocked_actions` 含 `open`（默认）；如需连平仓一并停，用 `blocked_actions=(OPEN, CLOSE)` 下发。

---

## 3. 恢复流程

1. 对账通过（持仓、在途委托、成交回报三方一致）；
2. `gate_kill(KillLevel.GLOBAL, "", False, reason="resume_after_reconcile", ts=…)`；
3. `on_order_result(rejected=False, ts=…)` → 连续拒单归零 → 复核 `circuit_decision.state == NORMAL`；
4. 若仍为 `DERISK_ONLY`（日亏损/回撤未修复）→ **不得**仅靠解除 kill 恢复开仓，须按风控口径确认；
5. 恢复后首笔用最小金额验证，观察 3 个 tick 无异常再常规化。

**禁止**：跳过对账直接解除 `HALTED`；以重启进程方式「规避」kill 状态（`live/safety_store.py` 会恢复状态，重启无效）。

---

## 4. 演练记录模板

| 字段 | 填写要求 |
|------|----------|
| 日期 / 执行人 | YYYY-MM-DD / 姓名 |
| 故障注入方式 | 断线（拔网/禁端口）、拒单（错误资金）、部分成交（Mock 桥）、柜台重启（进程 kill） |
| 涉及 `decision_id` | 从 `audit.risk_decision` 取 |
| 期望动作 vs 实际动作 | 对应 §1 表格逐项打勾 |
| 状态迁移 | `NORMAL → DERISK_ONLY → HALTED → NORMAL`，附 `audit.circuit` 的 `seq` |
| 耗时 | 从故障注入到人工确认完成 |
| 结论 / 改进项 | 通过 / 需改进（写明） |

> 每次演练须至少覆盖：1 次 `DISCONNECT` 达重试上限、1 次 `REJECT` 触发 `HALTED`、1 次一键停机 + 恢复闭环。

---

## 5. 升级路径与边界

| 场景 | 动作 | 备注 |
|------|------|------|
| 自动动作已执行但异常持续 | 升级人工接管：`HALT` + 通知券商 | 不再自动重试，避免放大损失 |
| 需要平仓但处于 `HALTED` | 人工确认后以 `blocked_actions=(OPEN,)` 收窄，或直接人工委托 | 不由 `SafetyGate` 自动平仓（D-G9） |
| 发现审计缺失 `operator` | 立即停用该入口，排查是否绕过 `build_audit_payload` | 契约强制项 |
| 真实通道接入后接口变化 | 按 P-053 更新 §2 的 `cancel_all` 调用与订单 id 级明细 | `LiveTradingBridge.cancel_orders(asset|None) -> int` |
