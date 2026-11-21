# REVIEW：P-052 Step 4 — DESIGN 异构复审

> **批次**: P-052 · **Step 4 设计复审** · 日期 2026-11-21
> **复审对象**: [DESIGN_p052_live_safety_gate.md](DESIGN_p052_live_safety_gate.md)（Step 3 产物，512 行）
> **作者基座**: DeepSeek-V4.1-Flash · **复审基座**: GLM-5.3-Flash · **异构 ✅**（RULE-5）
> **复审输入**: DESIGN §0-§10 全文 + §9 指定复审输入（§3 签名 / §5 阈值 / §7 用例映射 / §8 偏差）
> **方法**: 锚点回验（每条引用实读源码）→ 语义推演（kill/熔断/速率/审计闭环）→ 用例映射核对 → 依赖门禁比对

---

## 1. 结论速览

| 项 | 结果 |
|----|------|
| P1 | **1 项**（F-D1 `cancel_all` 与 Bridge 实际 API 不匹配——同型于 P-051c N-2 伪码失配） |
| P2 | **6 项**（F-D2..F-D7：签名缺口 / 双处定义 / 状态映射 / 依赖边 / 边界矛盾 / 阈值承载） |
| P3 | **8 项**（F-D8..F-D15：计数漂移 / 除零 / 跨日 / decision_id / 定案收口 / 默认值 / 必填清单 / 归属注记） |
| 处置 | **15/15 全部修复**（2026-11-21，回写 DESIGN §2/§3/§4，见 §4 回执） |
| 复审结论 | **Step 4 通过（修复后 0 P1 / 0 P2 残留）**；70 例映射与 pytest ≥1214 目标维持不变 |

---

## 2. 锚点回验矩阵（V1-V13，全部实读核验）

| ID | 核验点 | 结果 | 证据 |
|----|--------|------|------|
| V1 | `GuardContext`（L29）/`GuardResult`（L54）/`Guard.check`（L72）签名与 DESIGN §3.4 一致 | ✅ | core/guard_pipeline.py |
| V2 | 既有预设 `default/conservative/aggressive`（L328/L340/L352）；`live_safe()` 为第 4 预设，无命名冲突 | ✅ | core/guard_pipeline.py |
| V3 | `GuardPlugin` fail-open（L244-247「异常时放行」+ L198 P-026 D2.2 注释）→ D-G2/D10「默认 open」成立 | ✅ | core/engine_plugins.py |
| V4 | `EventType`（L50）/`IEventBus`（L61）/`append`（L129）接受任意 event_type → D-G3「不改 schema 只加常量」成立；EventType 类注释「单一来源；引擎侧禁止写裸字符串」→ 直接支撑 F-D3 | ✅ | core/event_log.py |
| V5 | `OrderIntent` 字段（execution_policy.py L57，L71-75：`asset/asset_type/target_quantity/current_quantity/urgency`）→ **无 price、无 account_id/strategy_id** | ⚠️ | 引出 F-D2 |
| V6 | `LiveTradingBridge.cancel_orders(asset: str\|None=None) -> int`（live_bridge.py L97-107）；Mock 实现 L191-198 只返回笔数 → DESIGN「cancel_orders(全部活跃 order_id) → list[str]」失配 | ⚠️ | 引出 F-D1（P1） |
| V7 | `filter/limit_rules.py`：`resolve_limit`（L106）/`build_limit_prices`（L132，DataFrame 级批量）→ 注入式消费可行；但总纲 L114/L286 允许边 `live→strategies/core` **不含 filter** | ⚠️ | 引出 F-D5 |
| V8 | `risk_overlay.py` L54-55 `dd_soft=0.08/dd_hard=0.12` → E16 引用准确（U-P052-10 依据成立） | ✅ | core/risk_overlay.py |
| V9 | `core/interfaces.py` 存在且为核心接口定义处（L1-40 Protocol 集合）→ F-D12 定案 `AuthConfig` 位置可行 | ✅ | core/interfaces.py |
| V10 | I8 零 diff 清单四文件均存在：engine_v2 / engine_v3_vector / sizing / stops | ✅ | Glob 核验 |
| V11 | 总纲引用：L114 分层 ✓、L155-167 S1-S7 ✓（S2 明确「复用 filter/limit_rules.py」）、L269 P-052 行 ✓、L277 关键路径 ✓、L324 D2（≤1/s、≤1000/日）✓、L286 依赖门禁 ✓ | ✅ | UPGRADE_MASTER_PLAN.md |
| V12 | §7 用例合计 14+9+10+15+6+10+4+2 = **70** ✓；1144+70 = **1214** ✓；RESEARCH +45~65 偏差已登记（§8） | ✅ | DESIGN §7 |
| V13 | 代码证据时点 HEAD `1f950c6` ✓；工作区仅 docs 变更（RESEARCH/REVIEW_step2/DESIGN/PROGRESS），零代码 ✓ | ✅ | git rev-parse / status |

**S1-S7 覆盖复核**：S1（§3.1+§3.6 store）、S2（§3.4 5 Guard + 既有 MaxPosition=单票 + IndustryExposure=行业，对齐总纲 L160 全部六要素）、S3（§3.2）、S4（§3.3）、S5（§3.7 契约）、S6（§3.5）、S7（§3.1 FaultPolicy + runbook）——范围无遗漏、无越界。

---

## 3. 发现清单（F-D1..F-D15）

### 3.1 P1（1 项）

**F-D1（P1）`cancel_all` 契约与 Bridge 实际 API 不匹配（§3.6）**
- **原文**: `def cancel_all(self, bridge: LiveTradingBridge, *, ts: float) -> list[str]`，docstring「调 bridge.cancel_orders(全部活跃 order_id)」。
- **证据**: `LiveTradingBridge.cancel_orders(self, asset: str | None = None) -> int`（live_bridge.py L97-107）——入参是**标的**而非 order_id 列表，`None` 才是「取消全部未成交」；返回**取消笔数（int）**而非订单 id 列表。Mock 实现（L191-198）同样只返回 int。
- **影响**: 按原文实现必然失败（传入参类型错误）或被迫在本批修改 Bridge 抽象（越界，D-G7 只承诺「调用不改」）。
- **同型先例**: P-051c N-2（伪码与 `WalkForwardSplitter` 实际 API 不匹配）。
- **修复**: `cancel_all(bridge, *, ts) -> int`——调 `bridge.cancel_orders(None)`，返回取消笔数，`audit.cancel` payload 记 `cancelled_count`；id 级明细待 P-053 扩展 Bridge API 后增强（注记）。

### 3.2 P2（6 项）

**F-D2（P2）`pre_trade_check` 签名缺 `account_id/strategy_id` 输入（§3.6）**
- **证据**: `effective_kill(state, account_id, strategy_id)`（DESIGN §3.1）需要账户/策略标识；但 `OrderIntent`（execution_policy.py L71-75）无此二字段，`GuardContext` 既有+新增 20 字段亦无。
- **影响**: 签名按原文无法实现 kill 判定；同时 `OrderIntent` 无 `price` 字段，价格/市值输入来源未声明（GuardContext 有 price/order_value，但设计未指明以 ctx 为准）。
- **修复**: 签名补 keyword-only `account_id: str, strategy_id: str`；docstring 注明「价格/市值类输入以 ctx 为准（OrderIntent 无 price 字段）」。

**F-D3（P2）`AUDIT_*` 8 常量双处定义（§3.3 vs §3.5）**
- **证据**: §3.3 `core/compliance.py` 块列出 AUDIT_INTENT..AUDIT_CIRCUIT 全套；§3.5 `core/event_log.py` EventType 增补同一套；§2 拓扑两行也分别记「AUDIT_* 常量」与「+8 审计常量」。event_log.py L50 类注释明示「单一来源；引擎侧禁止写裸字符串」。
- **影响**: 双定义漂移风险，违反单一来源原则。
- **修复**: 唯一定义在 `core/event_log.EventType`；`compliance.py` 从其 import 复用，自身仅保留 `AUDIT_EVENT_TYPES` frozenset、`build_audit_payload`、retention 常量。

**F-D4（P2）熔断 `reason → state` 映射未定义（§3.2）**
- **证据**: `CircuitDecision.reason ∈ {"", "daily_loss", "max_drawdown", "consecutive_rejects"}`，`evaluate_circuit` 只给优先级；D4 定义了 `DERISK_ONLY`/`HALTED` 语义，但**哪个 reason 落哪个 state 全文未写**。而 `allows_close`（HALTED=False）与 I5 单测直接依赖该映射。
- **修复**: `daily_loss / max_drawdown → DERISK_ONLY`（风险降级，保留平仓出路）；`consecutive_rejects → HALTED`（通道故障，连平仓也停，待人工接管）；人工全停走 kill switch（`blocked_actions` 含 CLOSE）。

**F-D5（P2）`live → filter` 未登记依赖边（§2 D-G6 注 vs 总纲 L114/L286）**
- **证据**: D-G6 注写「调用方（**live/safety_gate.py** 或回测适配器）用 filter.limit_rules.build_limit_prices 预算后注入」；但总纲 L286 允许边为 `live→strategies/core`，无 `filter`；DESIGN §2 依赖表 live 行允许依赖也只写 `core/*`。
- **影响**: 按原文实现将产生未登记依赖边，import-linter 门禁（总纲 L286）会拒绝。
- **修复**: `live/` 不 import `filter`；`limit_up/limit_down` 由**上层调用方**（services/执行适配器层——P-053 网关、P-054 服务或回测适配器）经 `build_limit_prices` 预算后注入。§2 依赖表与 D-G6 注同步改写。

**F-D6（P2）`OrderRateGuard` 等号边界自相矛盾 + 撤单率分母口径缺失（§3.4）**
- **证据**: 判定列写「`daily_order_count >= max` → 阻断」，边界列写「等于上限放行」——`>=` 语义下等号即阻断，两列矛盾；且撤单率分母（orders？orders+cancels？分母为 0 如何处理）未定义，而 §7 明确 15 例含「等号」边界测试。
- **修复**: 判定维持 `>= max` → 阻断（新单将超限）；边界列改「count < max 放行；撤单率分母 = `daily_order_count`，为 0 → 不判撤单率；样本 < `min_cancel_samples` → 不判撤单率」。

**F-D7（P2）`FaultPolicy` 无重试阈值承载，`decide_fault` 文档化阈值与 I10 冲突（§3.1）**
- **证据**: `FaultPolicy` 仅含 `actions: dict[FaultType, tuple[FaultAction, ...]]`；`decide_fault` docstring 写「attempt<3→RETRY」「+HALT if 连续」——阈值 3 与「连续」判定**无配置承载**，实现者只能在函数体内硬编码 3，直接违反 I10（「阈值全部可配置，判定函数体内无硬编码」）。
- **修复**: `FaultPolicy` 增字段 `max_retries: dict[FaultType, int]`（`default_fault_policy` 给 DISCONNECT=3、REJECT=1、PARTIAL_FILL=0、COUNTER_RESTART=0）；`attempts` 参数语义明确为「同类故障连续发生次数」，`attempts >= max_retries[fault]` → 退出 RETRY 阶段进入升级动作。

### 3.3 P3（8 项）

**F-D8（P3）§2 拓扑「GuardContext +5 字段」与 §3.4 实列 9 字段不一致**——§3.4 新增 `industry/industry_exposure/industry_limits/daily_order_count/daily_cancel_count/order_rate_config/limit_up/limit_down/counterparty_open_orders` 共 9 项。修复：§2 改「+9 字段」。

**F-D9（P3）`CircuitSnapshot.day_start_equity/peak_equity ≤ 0` 除零边界未写**——修复：≤0 视为该项未触发（不判 daily_loss/max_drawdown）。

**F-D10（P3）`RateLedger` 跨日重置策略未写**——修复：`record()` 检测 `date` 变化 → 重置 `daily_orders/daily_cancels`（`per_second` 滑窗天然过期）。

**F-D11（P3）`SafetyDecision.decision_id` 生成策略未指定**——修复：`live/` 层 `uuid4().hex`（I1 只约束 core 纯函数；live 层允许）。

**F-D12（P3）`AuthConfig` 位置「Step 5 二选一」留尾**——修复：定案 `core/interfaces.py`（文件已存在且为核心接口定义处，V9 核验）。

**F-D13（P3）`SafetyGate(pipeline=None)` 默认行为未写**——修复：默认构造 `GuardPipeline.live_safe()`。

**F-D14（P3）`ProgrammaticTradingReport.missing_required()` 必填清单未枚举**——修复：注记 Step 5 实现时按第九条（一）~（五）类别枚举；最小必填集 = `investor_name/account_code/member/strategy_type/execution_mode/software_name`，其余留空记入返回元组由测试 I7 断言。

**F-D15（P3）`audit.order/audit.fill/audit.reconcile` 本批无写入方**——修复：§3.5 增归属注记（本批只定义常量；写入方 = P-053 执行链路 / P-054 服务层），防 Step 5 误以为需在本批实现写入。

---

## 4. 修复回执（DESIGN 回写对照，2026-11-21）

| ID | DESIGN 回写位置 | 回执状态 |
|----|-----------------|----------|
| F-D1 | §3.6 `cancel_all` → `-> int`，调 `cancel_orders(None)`，注记 P-053 增强 | ✅ |
| F-D2 | §3.6 `pre_trade_check` 签名 + `account_id/strategy_id`；docstring 注明价格取自 ctx | ✅ |
| F-D3 | §3.3 AUDIT 块改「import 复用 event_log.EventType」；§3.5 为唯一定义处 | ✅ |
| F-D4 | §3.2 `evaluate_circuit` docstring + §4 D4 补映射（daily_loss/max_drawdown→DERISK_ONLY；consecutive_rejects→HALTED） | ✅ |
| F-D5 | §2 依赖表 live 行 + D-G6 注：live 不 import filter，上层注入 | ✅ |
| F-D6 | §3.4 OrderRateGuard 行：边界改「<max 放行；分母=daily_order_count，0 → 不判」 | ✅ |
| F-D7 | §3.1 `FaultPolicy.max_retries` 字段 + `decide_fault` 语义改按阈值数据 | ✅ |
| F-D8 | §2 「+5 字段」→「+9 字段」 | ✅ |
| F-D9 | §3.2 补「≤0 视为未触发」 | ✅ |
| F-D10 | §3.3 `record` 注释补跨日重置 | ✅ |
| F-D11 | §3.6 `decision_id` 注释补 uuid4 | ✅ |
| F-D12 | §3.7 位置定案 `core/interfaces.py` | ✅ |
| F-D13 | §3.6 `pipeline=None → live_safe()` | ✅ |
| F-D14 | §3.3 `missing_required` 注记必填最小集 | ✅ |
| F-D15 | §3.5 归属注记 | ✅ |

**复核方式**：全部回写由复审方执行并逐条对照本表；回写后 DESIGN §2/§3/§4 与本节一致，用例数（70）、阈值表（§5）、不变式（I1-I12）数量均未变动。

**连带检查**：F-D4 修复后 I5 验证路径不变（仍为 `allows_open/close` 单测）；F-D7 修复后 I10 可机械验证；F-D5 修复后 §10 出口条件 5（无浮空依赖）成立；§8 偏差表无需新增行（F-D5 是设计内部修正，非对总纲/RESEARCH 的偏差）。

---

## 5. 复审结论

1. **Step 4 通过**：15 项发现已全部修复回写，0 P1 / 0 P2 残留，8 项 P3 修复均为注记级；
2. DESIGN §0 裁决链（U-P052-1/2/4 用户裁决 + D-G1..D-G9）与 Step 2 REVIEW 登记一致；
3. 用例映射 70 例 / pytest ≥1214 / golden 22 / I1-I12 维持原判，可进入 Step 5 IMPL；
4. 遗留至后续批次的事项（非本批缺陷）：Bridge 订单 id 级明细（P-053）、`audit.order/fill/reconcile` 写入方（P-053/P-054）、`AuthConfig` 中间件实现（P-054）。

> **下一步**: Step 5 IMPL——按 DESIGN §2 拓扑与 §3 契约逐处落码（三新 core 模块 + 5 Guard + EventType 常量 + 最小 `live/` + runbook + 8 测试文件 70 例）。
