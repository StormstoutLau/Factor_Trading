# REVIEW：P-052 Step 6 — IMPL 异构复审

> **批次**: P-052 · **Step 6 实施方案复审** · 日期 2026-11-21
> **复审对象**: [IMPL_p052](IMPL_p052_live_safety_gate.md)（1307 行）+ [RUNBOOK_p052](RUNBOOK_p052_fault_handling.md)（72 行）
> **作者基座**: DeepSeek-V4.1-Flash · **复审基座**: GLM-5.3-Flash · **异构 ✅**（RULE-5）
> **方法**: 逐处代码与实际 API 对表（execution_policy / engine_plugins / live_bridge / pyproject / DESIGN 回验）→ 语义推演（方向分流 / 限速窗口 / 重启恢复）→ 用例映射复核

---

## 1. 结论速览

| 项 | 结果 |
|----|------|
| P1 | **1 项**（F-I1 `pre_trade_check` 未按开/平方向分流——默认 kill 与 `DERISK_ONLY` 均会阻断平仓，违反 S1「停止新开仓」语义） |
| P2 | **2 项**（F-I2 秒级限速窗口语义错、F-I3 熔断权益基准不持久化） |
| P3 | **4 项**（F-I4..F-I7：DESIGN 同步 / ts 未用 / 字符串注解 / 超 100 列） |
| 偏差裁定 | **D-1..D-6 全部采纳**（D-1 严重度优先正确；D-4 `update_equity` 必要；D-5 单轨 HALT 与 RUNBOOK 一致；D-6 tests.yml 必要） |
| 处置 | **7/7 全部修复**（回写 IMPL §2/§3/§4/§5 + DESIGN §3.2/§3.3/§3.6/§4 D4，见 §4 回执） |
| 复审结论 | **Step 6 通过（修复后 0 P1 / 0 P2 残留）**；70 例映射与 pytest ≥1214 目标不变，可进入 Step 7 |

---

## 2. 核验矩阵（V1-V12，全部实读核验）

| ID | 核验点 | 结果 | 证据 |
|----|--------|------|------|
| V1 | `OrderIntent.action` 为 **property**（非字段），由 `trade_quantity/current_quantity` 推导 `BUY/SELL/SELL_SHORT/BUY_TO_COVER/HOLD`（execution_policy.py L87-100）→ IMPL `intent.action` 用法合法；`MockLiveBridge.place_intents` 同样消费该 property 并跳过 HOLD（L167） | ✅ | core/execution_policy.py |
| V2 | `GuardPlugin.__init__` 现签名 `(engine, pipeline=None, mode="block")`（L186-191），`check_trade -> tuple[bool, list[str]]`（L213-219），异常分支 L244-247 返回 `True, []` → IMPL §3.5 `on_error` 扩展**兼容**（保留 `_error_count`，closed 模式返回 `(False, [reason])` 符合契约） | ✅ | core/engine_plugins.py |
| V3 | `MockLiveBridge`（L144）：`cancel_orders` L191-198 返回笔数 ✓、`get_placed_orders()` L216 存在 ✓ → E 组观测点成立，IMPL 风险预案引用有效 | ✅ | core/live_bridge.py |
| V4 | `LiveTradingBridge.cancel_orders(asset: str \| None = None) -> int`（抽象 L96-107）→ `cancel_all(None)` 调用合法 | ✅ | core/live_bridge.py |
| V5 | mypy 配置（pyproject L109-114）：`disallow_untyped_defs=false`、`ignore_missing_imports=true` → `live/` 新代码类型无阻碍；字符串注解可接受（F-I6 仅建议） | ✅ | pyproject.toml |
| V6 | DESIGN §3.6 `SafetyGate.__init__` 已是 keyword-only（DESIGN L370-373）→ IMPL 一致（疑点撤销，未立 finding） | ✅ | DESIGN_p052 L370-373 |
| V7 | **方向语义**：`pre_trade_check` 对全部动作统一用 `allows_open` / `allows(kill, OPEN)` → 平仓被默认 kill 与 `DERISK_ONLY` 阻断 | ⚠️ | **F-I1（P1）** |
| V8 | **限速语义**：`check_rate` 秒级窗口 `{sec-1, sec}` 求和 → 相邻秒订单互斥，实际 = 1 笔/2 秒 | ⚠️ | **F-I2（P2）** |
| V9 | **重启恢复**：C-3 schema 仅持久化 `consecutive_rejects`/`equity_day`，`day_start_equity/peak_equity` 丢失 → 重启后日亏损基准重置 | ⚠️ | **F-I3（P2）** |
| V10 | 偏差 D-1..D-6 逐项推演：D-1 安全倒挂论证成立（日亏损先判会把 HALTED 降级为 DERISK_ONLY）；D-2 与「compliance 零项目内依赖」自洽；D-3 改名避免 `safety_gate` 双 `to_dict` 冲突；D-4 缺 `update_equity` 则熔断永不触发；D-5 双轨 HALT 状态源不唯一；D-6 tests.yml L46 现无 `live` | ✅ | 全部采纳 |
| V11 | 用例合计 14+9+10+15+6+10+4+2 = **70** ✓；1144+70 = **1214** ✓；C4/C5 需随 F-I2 修正后语义落笔 | ✅ | IMPL §3.12 |
| V12 | 编码约束：black line-length=100（pyproject L94-96）、mypy python_version=3.10（L109-110）→ IMPL 引用准确；IMPL 代码含超 100 列行（F-I7） | ⚠️ | pyproject.toml |

---

## 3. 发现清单（F-I1..F-I7）

### 3.1 P1（1 项）

**F-I1（P1）`pre_trade_check` 未按开/平方向分流（IMPL §3.10）**
- **证据**：实现对所有非 HOLD 意图统一判定 `kill.blocked and not allows(kill, KillAction.OPEN)` 与 `not allows_open(circuit)`。而 `intent.action` 由 property 推导出四个方向（execution_policy.py L87-100）：`BUY/SELL_SHORT` = 开仓方向，`SELL/BUY_TO_COVER` = 平仓方向。
- **后果**（双违反）：
  1. 默认 kill（`blocked_actions=(OPEN,)`）下，`SELL` 平仓单被 `allows(kill, OPEN)=False` 阻断——与 S1「停止**新开仓**」、D-G9「不自动平仓（平仓默认放行）」、纯函数 K10 语义直接矛盾（持仓被锁死，无法退出）；
  2. `DERISK_ONLY` 下 `allows_open=False` 阻断一切委托——与「只平不开」矛盾，且与 IMPL §3.12 自身的 L3 用例「阻断开仓（**放行平仓**）」互相矛盾：按现实现写 L3 必失败，按 L3 期望写则实现必改。
- **修复**：方向分流——`is_open_direction = action in ("BUY", "SELL_SHORT")`；kill 用 `allows(kill, OPEN if is_open else CLOSE)`，circuit 用 `allows_open/allows_close`。HALTED 下 `allows_close=False` → 全停 ✓。L2/L3 用例补平仓放行断言。

### 3.2 P2（2 项）

**F-I2（P2）`check_rate` 秒级窗口语义错误：实际限速 1 笔/2 秒（IMPL §3.3）**
- **证据**：`window = sum(v for k in per_second if k >= sec-1)` 把上一秒桶计入。`max_per_second=1` 时：t=100.9 一笔 → t=101.1 的订单窗口和 = 1 ≥ 1 → 阻断。相邻秒互斥 = **1 笔/2 秒**，与配置语义「≤1 笔/秒」（D2 内部默认）不符，吞吐无谓减半；C4/C5 用例会按错误语义固化。
- **修复**：秒级判定只查当前秒桶 `per_second.get(sec, 0) >= cfg.max_per_second`（桶语义与「瞬时申报速率」监管口径一致）；`record` 保留两桶仅作滑除。C-5 澄清行与 DESIGN §3.3 同步。

**F-I3（P2）熔断权益基准不持久化：跨重启当日亏损被遗忘（IMPL §2 C-3 / §3.10）**
- **证据**：C-3 schema 的 `circuit` 段只有 `consecutive_rejects`；`day_start_equity/peak_equity/equity` 不落盘。进程重启后快照归零，下次 `update_equity` 走 `day_start_equity <= 0` 分支**重置当日基准**——今日已亏 20% 的账户重启后日亏损熔断从零起算，S3 失效；与 kill/ledger 持久化不对称（kill 跨重启生效有 L8/E4 用例，熔断没有）。
- **修复**：`circuit` 段扩为四字段（`consecutive_rejects/day_start_equity/peak_equity/equity`），`_restore` 全量恢复；`update_equity` 现有 `equity_day` 日切条件恰好保证「同日恢复不重置基准」，无需改逻辑。L8 用例补权益基准断言。

### 3.3 P3（4 项）

**F-I4（P3）DESIGN §3.3 与 D-2 残留不一致**——DESIGN §3.3 注记仍写「本模块 `from core.event_log import EventType` 后仅引用」，与 IMPL D-2（compliance 零项目内依赖）冲突，且 `AUDIT_EVENT_TYPES` 行留 compliance 块内。修复：DESIGN §3.3 注记改为「常量与 frozenset 均在 event_log，compliance 不引用」，删除该行。

**F-I5（P3）`on_order_result(*, rejected, ts)` 的 `ts` 未使用**——`audit.circuit` payload 无 ts，事件时间由 `EventLogEntry.ts` 承载。修复：保留参数（签名前向兼容），docstring 注明预留语义。

**F-I6（P3）`store: "SafetyStateStore"` 字符串注解无必要**——`live.safety_store` 不 import `safety_gate`，无环。修复：IMPL 已自注「Step 9 可改直接 import」，复审确认即可，不阻塞。

**F-I7（P3）IMPL 代码含超 100 列行**（如 HOLD 分支 `_audit_decision(...)` 单行 ≈107 列，超 black line-length=100）。修复：§5 门禁步骤改为「先 `black .` 格式化再 `--check`」（P-051c 惯例），以格式化输出为准。

---

## 4. 修复回执（2026-11-21，复审方执行并逐条核验）

| ID | 回写位置 | 回执 |
|----|----------|------|
| F-I1 | IMPL §3.10 `pre_trade_check` 方向分流（kill_action / circuit_ok 按 `is_open_direction`）+ docstring；§3.12 L2/L3 补平仓断言；DESIGN §3.6 docstring 同步 | ✅ |
| F-I2 | IMPL §3.3 `check_rate` 改当前秒桶；§2 C-5 行修订；DESIGN §3.3 `check_rate` docstring 同步 | ✅ |
| F-I3 | IMPL §2 C-3 schema 四字段；§3.10 `_restore`/`_persist` 权益基准持久化；§3.12 L8 补断言 | ✅ |
| F-I4 | DESIGN §3.3 审计注记重写（compliance 不引用审计常量） | ✅ |
| F-I5 | IMPL §3.10 `on_order_result` docstring 补 ts 预留注记 | ✅ |
| F-I6 | IMPL §3.10 脚注已存在（直接 import 去引号，Step 9 执行）——确认即可 | ✅ |
| F-I7 | IMPL §5 门禁步骤 10 改「先 black 格式化再 --check」 | ✅ |
| D-1..D-6 | IMPL §4 增复审裁定段（全部采纳）；DESIGN §3.2 docstring + §4 D4 行同步「严重度优先」 | ✅ |

**连带检查**：F-I1 修复后 `allows_close` 由未用变已用（import 清单不变）；F-I3 修复后 `_restore` 使用已导入的 `CircuitSnapshot` 构造器（无新 import）；E4/L8 语义与持久化字段一致；70 例总数不变（L2/L3/L8 为断言增强非新增用例）。

---

## 5. 复审结论

1. **Step 6 通过**：7 项发现全部修复，0 P1 / 0 P2 残留；D-1..D-6 六项偏差全部采纳并完成 DESIGN 双向同步；
2. 逐处代码与实际 API 对表通过：`OrderIntent.action` property、`GuardPlugin` 契约、`MockLiveBridge` 观测点、mypy 宽松度、`cancel_orders(asset|None)->int` 均与实现假设一致；
3. 70 例映射 / pytest ≥1214 / golden 22 / I1-I12 维持原判，可进入 Step 7 CHECKLIST；
4. Step 9 执行提示：`live/` 纳入 mypy 目标（D-6）；先 black 后 check（F-I6/F-I7）。

> **下一步**: Step 7 CHECKLIST——按 CHECKLIST_p051c 惯例产出 `docs/CHECKLIST_p052_live_safety_gate.md`（70 项断言全部 `[待 Step 9]`，RULE-1 禁预填）。
