# DESIGN：P-052 实盘安全闸门（kill switch / 网关事前风控 / 账户熔断 / 合规报告 / 鉴权 / 审计 / 故障处置）

> **批次**: P-052 · **Step 3 设计** · 日期 2026-11-21
> **上游**: [RESEARCH_p052](RESEARCH_p052_live_safety_gate.md)（Step 1，17 条代码锚点 E1-E17 + G1-G9 缺口 + §8.1 决策锚点）；[REVIEW_p052_step2](REVIEW_p052_step2_research.md)（Step 2 异构复审 0 P1，2 P2 + 5 P3 全修）
> **总纲**: [UPGRADE_MASTER_PLAN §3.0 S1-S7](UPGRADE_MASTER_PLAN.md)（L155-L167）、§2.1 分层（L114）、§5 P-052 行（L269）、关键路径（L277）
> **代码证据时点**: HEAD `1f950c6`
> **基座**: DeepSeek-V4.1-Flash（Step 4 复审须异构）
> **Step 4 复审**: 已通过（2026-11-21，GLM-5.3-Flash 异构 ✅；1 P1 + 6 P2 + 8 P3 全修，见 [REVIEW_p052_step4](REVIEW_p052_step4_design.md)）

---

## 0. 裁决记录（Step 3 定案）

### 0.1 用户已裁决（Step 2 登记）

| ID | 裁决 | 来源 |
|----|------|------|
| U-P052-1 | 安全判定纯函数放 `core/`，持久化/撤单/告警适配器放 `live/` | 用户 2026-11-21 |
| U-P052-2 | 本批新建**最小** `live/`（仅 S1/S3 状态持久化与执行适配器；真实交易通道留 P-053） | 用户 2026-11-21 |
| U-P052-4 | S5 本批只交付 `AuthConfig` 契约 + 401/403 用例骨架，实现归 P-054 | 用户 2026-11-21 |
| U-P052-5 | 默认速率 1 笔/秒、1000 笔/日 = **D2 项目内部默认值**，可配置，禁写成监管要求 | D2（总纲 L324） |
| U-P052-9 | 自用工具 + 完成程序化报备；不对外服务、不做等保/多租户 | D2（总纲 L324） |

### 0.2 Step 3 工程口径定案（本文件新增）

| ID | 定案 | 理由 |
|----|------|------|
| **U-P052-3 → D-G1** | **扩展 `GuardPipeline`**（新增 5 类 Guard）+ 新增 `GuardPipeline.live_safe()` 预设；不新建平行网关风控 | 复用 E1-E3 已存在的 6-Guard 架构与 `GuardResult` 契约；上下文/测试可共享 |
| **U-P052-6 → D-G2** | `GuardPlugin` 增参数 `on_error: Literal["open","closed"] = "open"`（**默认保持 open 不破坏回测**）；`SafetyGate` 使用 `on_error="closed"` 语义（或直接走独立校验） | 回测既有 fail-open 语义由 P-026 D2.2 登记，不能一刀切改动；实盘路径单独收紧 |
| **U-P052-7 → D-G3** | **新增 `EventType` 审计常量 + 统一 payload 键约定**；**不改** `EventLogEntry` 序列化 schema | `EventLog.append` 已接受任意 `event_type`（E5 L146-L154）；改 schema 会波及 golden 与旧日志兼容；payload 约定用 helper 强制 |
| **U-P052-8 → D-G4** | 交付 `FaultType`/`FaultAction` 纯决策 + `docs/RUNBOOK_p052_fault_handling.md` + 故障注入测试骨架；**重连实现归 P-053** | 总纲 L165 要求「故障注入演练记录」；无真实通道时只能做决策层与演练骨架 |
| **U-P052-10 → D-G5** | 账户熔断经验默认：日亏损 3%、最大回撤 10%、连续拒单 5 次；全部可配置 | 无外部强制阈值；参考 `risk_overlay` dd_soft 0.08/dd_hard 0.12（E16）的内部先例，取更保守的账户级阈值 |
| **U-P052-11 → D-G6** | `PriceBandGuard` 只消费 `GuardContext.limit_up/limit_down`（由调用方经 `filter.limit_rules` 计算后注入），**`core` 不 import `filter`** | 保持 `core` 纯计算与零上行依赖；价格带计算留在数据层 |
| **U-P052-12 → D-G7** | `cancel_all` 只对 `LiveTradingBridge`/`MockLiveBridge` 调用；本批不接真实券商 | P-053 才建真实通道 |
| **U-P052-13 → D-G8** | 审计保留期默认 **5 年可配置**；常量上限 **20 年**（细则第十五条 / 《证券法》137 条） | 自用定位；若承担券商级记录义务对齐 20 年 |
| **U-P052-14 → D-G9** | `SafetyGate` 只**阻止新开仓 + 发 DERISK 信号**，不自动平仓；平仓由执行层/P-053 落实 | 自动平仓涉及真实通道与滑点，超出安全闸门职责 |

---

## 1. 目标与非目标

**目标**（交付可机械验证的 7 项）：

1. **S1**：三级 kill switch 纯状态机 + `live/` 持久化（重启恢复）；
2. **S2**：5 类新增事前风控 Guard（单笔金额 / 价格带 / 行业暴露 / 日笔数+撤单率 / 自成交）；
3. **S3**：账户级熔断纯状态机（日亏损 / 回撤 / 连续拒单 → 只平不开 + 告警事件）；
4. **S4**：程序化交易报告 schema（第九条 6 类 + 第三十四条 3 项）+ 速率台账（1/s、1000/日可配）+ 异常交易类型枚举；
5. **S5**：`AuthConfig` 契约 + 401/403 用例骨架（实现外置 P-054）；
6. **S6**：审计事件类型 + `operator`/`time_source` payload 约定 + append-only 复用；
7. **S7**：故障处置纯决策 + runbook + 故障注入骨架。

**非目标**：真实券商/QMT/CTP 通道（P-053）、FastAPI/WS（P-054）、Redis/微服务（P-055）、自动平仓、报备推送、等保/多租户。

---

## 2. 模块拓扑与依赖

```
新增 core（纯计算，零 I/O）:
  core/safety.py          KillLevel/KillState/KillSwitch + FaultType/FaultAction/decide_fault
  core/circuit_breaker.py CircuitState/CircuitConfig/evaluate_circuit
  core/compliance.py      ProgrammaticTradingReport/RateLedger/AbnormalTradeType/build_audit_payload + 保留常量（审计常量唯一落 event_log，F-D3/D-2）
新增 live（I/O 适配，最小）:
  live/__init__.py
  live/safety_store.py    KillState/CircuitSnapshot 原子落盘与恢复
  live/safety_gate.py     SafetyGate：组合 kill + circuit + guard + rate + audit
扩展:
  core/guard_pipeline.py  GuardContext +9 字段；+5 Guard；+live_safe() 预设
  core/engine_plugins.py  GuardPlugin +on_error 参数
  core/event_log.py       EventType +8 审计常量（不改 Entry schema）
文档:
  docs/RUNBOOK_p052_fault_handling.md（Step 5 落盘）
```

**依赖边**（符合总纲 §2.1 L114 / §6 L286）：

| 源 | 允许依赖 | 禁止 |
|----|----------|------|
| `core/safety.py` `core/circuit_breaker.py` `core/compliance.py` | Python 标准库 | 任何项目内模块 |
| `core/guard_pipeline.py` | `core/*` | `filter` / `live` / `services` / `strategies` |
| `live/safety_store.py` `live/safety_gate.py` | `core/*` | `services` / `strategies` / `filter`（可被 services 调用；价格带由上层注入，F-D5） |
| `services/*`（P-054） | `live` / `core` | — |

> **D-G6 落地（Step 4 F-D5 修订）**：`PriceBandGuard` 只消费注入字段；**`core` 与 `live/` 均不 import `filter`**（总纲 L286 允许边 `live→strategies/core` 不含 filter）——`limit_up/limit_down` 由上层调用方（services/执行适配器层：P-053 网关、P-054 服务或回测适配器）用 `filter.limit_rules.build_limit_prices`（L132）预算后注入。

---

## 3. 数据契约

### 3.1 `core/safety.py`（S1 + S7）

```python
class KillLevel(str, Enum):
    GLOBAL = "global"
    ACCOUNT = "account"
    STRATEGY = "strategy"

class KillAction(str, Enum):          # 被阻断的动作类别
    OPEN = "open"                      # 新开仓
    CLOSE = "close"                    # 平仓（默认不被 kill 阻断，D-G9）
    CANCEL = "cancel"                  # 撤单（kill 可要求一键撤单）

@dataclass(frozen=True)
class KillEntry:
    level: KillLevel
    key: str                           # GLOBAL=""; ACCOUNT=account_id; STRATEGY=strategy_id
    active: bool
    reason: str = ""
    operator: str = ""
    ts: float = 0.0
    # kill 生效时阻断的动作集合；默认只阻断开仓
    blocked_actions: tuple[KillAction, ...] = (KillAction.OPEN,)

@dataclass(frozen=True)
class KillState:
    entries: tuple[KillEntry, ...] = ()     # 不可变快照

@dataclass(frozen=True)
class KillCommand:
    level: KillLevel
    key: str
    active: bool
    reason: str
    operator: str
    ts: float                            # 调用方提供，纯函数不取 now
    blocked_actions: tuple[KillAction, ...] = (KillAction.OPEN,)

@dataclass(frozen=True)
class KillDecision:
    blocked: bool
    level: KillLevel | None              # 生效的最高层级
    reason: str
    blocked_actions: tuple[KillAction, ...]

def initial_kill_state() -> KillState: ...
def apply_command(state: KillState, cmd: KillCommand) -> tuple[KillState, KillEntry]:
    """纯函数：同 (level,key) 覆盖；更高层级 active 时，低层级的 active=False 不得解除高层（I3）。"""
def effective_kill(state: KillState, account_id: str, strategy_id: str) -> KillDecision:
    """优先级 GLOBAL > ACCOUNT > STRATEGY；返回最高 active 层级的阻断决策。"""
def allows(kill: KillDecision, action: KillAction) -> bool: ...
def to_dict(state: KillState) -> dict: ...
def from_dict(data: dict) -> KillState: ...
```

**S7 故障处置**（同文件）：

```python
class FaultType(str, Enum):
    DISCONNECT = "disconnect"
    REJECT = "reject"
    PARTIAL_FILL = "partial_fill"
    COUNTER_RESTART = "counter_restart"

class FaultAction(str, Enum):
    RETRY = "retry"
    PAUSE_NEW = "pause_new"
    CANCEL_ALL = "cancel_all"
    RECONCILE = "reconcile"
    HALT = "halt"
    RESUME = "resume"

@dataclass(frozen=True)
class FaultPolicy:
    actions: dict[FaultType, tuple[FaultAction, ...]]
    max_retries: dict[FaultType, int]   # 同类故障连续次数上限（I10 阈值可配置，Step 4 F-D7）

def default_fault_policy() -> FaultPolicy: ...
def decide_fault(policy: FaultPolicy, fault: FaultType, attempts: int) -> tuple[FaultAction, ...]:
    """确定性决策；``attempts`` = 同类故障连续发生次数。
    attempts < max_retries[fault] → 按 actions[fault] 前缀 RETRY；达到上限 → 升级动作
    （断线: PAUSE_NEW+RECONCILE；拒单: PAUSE_NEW（不追加 HALT——连续拒单熔断由 circuit_breaker 承担，IMPL D-5 单轨定案）；部分成交: RECONCILE；
    柜台重启: CANCEL_ALL+RECONCILE+HALT）。默认 max_retries：DISCONNECT=3、REJECT=1、
    PARTIAL_FILL=0、COUNTER_RESTART=0（由 default_fault_policy 提供，不在函数体内硬编码）。"""
```

### 3.2 `core/circuit_breaker.py`（S3）

```python
class CircuitState(str, Enum):
    NORMAL = "normal"
    DERISK_ONLY = "derisk_only"     # 只平不开
    HALTED = "halted"               # 全停（含平仓需人工）

@dataclass(frozen=True)
class CircuitConfig:
    daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.10
    max_consecutive_rejects: int = 5

@dataclass(frozen=True)
class CircuitSnapshot:
    day_start_equity: float
    peak_equity: float
    equity: float
    consecutive_rejects: int = 0

@dataclass(frozen=True)
class CircuitDecision:
    state: CircuitState
    reason: str                     # "" | "daily_loss" | "max_drawdown" | "consecutive_rejects"
    alerts: tuple[str, ...] = ()    # 供上游推送的告警键

def evaluate_circuit(cfg: CircuitConfig, snap: CircuitSnapshot) -> CircuitDecision:
    """判定顺序 = 严重度优先（Step 6 D-1 定案）：consecutive_rejects（HALTED）先判，
    再 daily_loss、max_drawdown（同入 DERISK_ONLY，报告优先级 daily_loss > max_drawdown）；
    原因：若 daily_loss 先判，会把已 HALTED 的「全停」降级为「只平不开」（安全倒挂）。
    reason→state 映射（F-D4）：daily_loss / max_drawdown → DERISK_ONLY（保留平仓出路）；
    consecutive_rejects → HALTED；人工全停走 kill switch（blocked_actions 含 CLOSE）。
    day_start_equity / peak_equity ≤ 0 → 该项视为未触发（避免除零，F-D9）。"""
def allows_open(decision: CircuitDecision) -> bool: ...   # NORMAL=True
def allows_close(decision: CircuitDecision) -> bool: ...  # NORMAL/DERISK_ONLY=True；HALTED=False
```

### 3.3 `core/compliance.py`（S4 + S6 常量）

```python
class AbnormalTradeType(str, Enum):
    INSTANT_ORDER_RATE = "instant_order_rate"          # 瞬时申报速率异常
    FREQUENT_INSTANT_CANCEL = "frequent_instant_cancel" # 频繁瞬时撤单
    FREQUENT_PUSH_PULL = "frequent_push_pull"          # 频繁拉抬打压
    SHORT_TERM_LARGE_TRADE = "short_term_large_trade"  # 短时间大额成交
    # 科创板异常交易实时监控补充
    FALSE_DECLARATION = "false_declaration"            # 虚假申报
    MAINTAIN_LIMIT_PRICE = "maintain_limit_price"      # 维持涨跌幅限制价格
    SELF_TRADE = "self_trade"                          # 自买自卖/互为对手方
    ABNORMAL_DECLARATION_RATE = "abnormal_declaration_rate"  # 严重异常波动股票申报速率异常

@dataclass(frozen=True)
class ProgrammaticTradingReport:
    # 第九条（一）账户基本信息
    investor_name: str
    account_code: str
    member: str
    product_manager: str = ""
    # （二）账户资金信息
    capital_scale: float = 0.0
    capital_source: str = ""
    leverage_scale: float = 0.0
    leverage_source: str = ""
    leverage_ratio: float = 0.0
    # （三）账户交易信息
    strategy_type: str = ""
    strategy_desc: str = ""
    execution_mode: str = ""
    max_order_rate: int = 0        # 笔/秒
    max_daily_orders: int = 0      # 笔/日
    # （四）交易软件信息
    software_name: str = ""
    software_version: str = ""
    developer: str = ""
    # （五）其他信息
    contact: str = ""
    contact_info: str = ""
    # 第三十四条 高频额外（非高频留 None）
    server_location: str | None = None
    system_test_report: str | None = None
    emergency_plan: str | None = None

    def missing_required(self) -> tuple[str, ...]:
        """返回第九条必填项中为空/零的字段名（bool/数值 0 视为未填）。
        Step 5 实现按第九条（一）~（五）类别枚举；最小必填集 = investor_name /
        account_code / member / strategy_type / execution_mode / software_name（F-D14）。"""

@dataclass(frozen=True)
class RateLimitConfig:
    max_per_second: int = 1
    max_per_day: int = 1000
    max_cancel_ratio: float | None = None   # None=不限制；仅样本量≥min_cancel_samples 时生效
    min_cancel_samples: int = 20

@dataclass(frozen=True)
class RateLedger:
    date: str                         # "YYYY-MM-DD"
    per_second: dict[int, int]        # epoch_second -> count（仅保留近 2 秒）
    daily_orders: int = 0
    daily_cancels: int = 0

def record(ledger: RateLedger, ts: float, is_cancel: bool) -> RateLedger: ...
# record 注：检测 date 变化 → 重置 daily_orders/daily_cancels（per_second 滑窗天然过期，F-D10）
def check_rate(ledger: RateLedger, ts: float, cfg: RateLimitConfig) -> tuple[bool, str]:
    """返回 (allowed, reason)；reason ∈ {"","per_second","per_day","cancel_ratio"}。
    秒级判定只查当前秒桶 ``per_second.get(sec,0) >= max_per_second``（Step 6 F-I2 定案：
    不做 {sec-1, sec} 滑窗求和——否则相邻秒互斥，实际限速 1 笔/2 秒，与「≤1 笔/秒」不符）。"""
def cancel_ratio(ledger: RateLedger) -> float: ...
def ledger_to_dict / ledger_from_dict（IMPL D-3 定名，避免与 core/safety.py 同名冲突）

# S6 审计常量（D-G3：不改 EventLogEntry schema，payload 键约定）
# AUDIT_* 8 常量与 AUDIT_EVENT_TYPES 唯一定义于 core/event_log.py（§3.5；F-D3 单一来源）。
# Step 6 D-2/F-I4 定案：compliance 零项目内依赖，不 import event_log，本模块不引用审计常量。

def build_audit_payload(*, operator: str, time_source: str, **fields: Any) -> dict[str, Any]:
    """强制注入 operator/time_source，其余字段透传。"""

AUDIT_RETENTION_YEARS_DEFAULT = 5
AUDIT_RETENTION_YEARS_MAX = 20    # 细则第十五条 / 证券法 137 条
```

### 3.4 `GuardPipeline` 扩展（S2）

**`GuardContext` 新增字段（全部带默认值，向后兼容 I11）**：

```python
    # --- P-052 扩展 ---
    industry: str = ""
    industry_exposure: dict[str, float] = field(default_factory=dict)   # industry -> 当前权重
    industry_limits: dict[str, float] = field(default_factory=dict)     # industry -> 上限
    daily_order_count: int = 0
    daily_cancel_count: int = 0
    order_rate_config: dict[str, Any] = field(default_factory=dict)     # max_daily_orders/max_cancel_ratio/min_cancel_samples
    limit_up: Optional[float] = None          # 由调用方经 filter.limit_rules 注入
    limit_down: Optional[float] = None
    counterparty_open_orders: list[dict[str, Any]] = field(default_factory=list)  # {"side","price","qty"}
```

**新增 5 类 Guard**（均实现 `check(ctx) -> GuardResult`）：

| Guard | 配置键 | 判定 | 边界 |
|-------|--------|------|------|
| `MaxOrderValueGuard` | `max_order_value` | `ctx.order_value > max` → 阻断 | 等于上限放行 |
| `PriceBandGuard` | 无（读 ctx） | BUY 且 `price > limit_up` → 阻断；SELL 且 `price < limit_down` → 阻断；limit 为 None → 放行（附 warning 消息，不阻断） | 等于涨跌停价放行 |
| `IndustryExposureGuard` | `default_industry_limit` | 新权重 `= industry_exposure.get(ind,0) + order_value/portfolio_value`；> 上限 → 阻断 | portfolio_value≤0 → 跳过 |
| `OrderRateGuard` | `max_daily_orders` / `max_cancel_ratio` / `min_cancel_samples` | `daily_order_count >= max` → 阻断（新单将超限）；`cancel_count >= min_samples 且 cancel_ratio > limit` → 阻断 | count < max 放行；撤单率分母 = `daily_order_count`，为 0 → 不判；样本不足不判撤单率（F-D6） |
| `SelfTradeGuard` | 无（读 ctx） | BUY 且存在 `side==SELL 且 price<=price` 的对手挂单 → 阻断；SELL 反之 | 空列表放行 |

**预设**：

```python
@classmethod
def live_safe(cls) -> "GuardPipeline":
    """实盘安全预设：MaxPosition + PriceBand + MaxOrderValue + IndustryExposure
    + OrderRate + SelfTrade + MinCash + Drawdown（不含 Cooldown/Whitelist，可叠加）。"""
```

### 3.5 `EventLog` 审计扩展（S6）

```python
# core/event_log.py EventType 增补（仅常量，不改 Entry schema）
AUDIT_INTENT = "audit.intent"
AUDIT_RISK_DECISION = "audit.risk_decision"
AUDIT_ORDER = "audit.order"
AUDIT_FILL = "audit.fill"
AUDIT_CANCEL = "audit.cancel"
AUDIT_RECONCILE = "audit.reconcile"
AUDIT_KILL = "audit.kill"
AUDIT_CIRCUIT = "audit.circuit"
```

**约定**：所有审计事件 `payload` 必须含 `operator` 与 `time_source`（`"exchange" | "local" | "broker"`）；由 `build_audit_payload` 强制。`append` 签名与 `EventLogEntry` **零改动**（I12）。

> **写入归属（F-D15）**：`audit.risk_decision / kill / circuit / cancel` 由 `SafetyGate`（§3.6）写入；`audit.intent / order / fill / reconcile` 本批仅定义常量，写入方为 P-053 执行链路 / P-054 服务层。

### 3.6 `live/` 最小适配层（S1/S3 持久化 + S6 写盘）

```python
# live/safety_store.py
class SafetyStateStore:
    def __init__(self, path: Path) -> None: ...
    def save(self, data: dict[str, Any]) -> None:      # 临时文件 + os.replace 原子写
    def load(self) -> dict[str, Any] | None: ...        # 不存在/损坏 → None

# live/safety_gate.py
@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    action: str                       # 允许/阻断后的动作
    reasons: tuple[str, ...] = ()
    decision_id: str = ""             # 审计关联键；live 层 uuid4().hex 生成（I1 仅约束 core，F-D11）
    kill_level: KillLevel | None = None
    circuit_state: CircuitState = CircuitState.NORMAL

class SafetyGate:
    def __init__(self, *, event_log: IEventBus, store: SafetyStateStore,
                 rate_config: RateLimitConfig, circuit_config: CircuitConfig,
                 fault_policy: FaultPolicy, pipeline: GuardPipeline | None = None,   # None → live_safe()（F-D13）
                 operator: str = "system") -> None: ...
    def pre_trade_check(self, intent: OrderIntent, ctx: GuardContext, *,
                        account_id: str, strategy_id: str,
                        ts: float, time_source: str = "local") -> SafetyDecision:
        """顺序：kill → circuit → rate → guard pipeline；任一阻断即返回，并写 audit.risk_decision。
        方向由 intent.action 推导（property，execution_policy.py L87-100）：BUY/SELL_SHORT=开、
        SELL/BUY_TO_COVER=平；kill 按 allows(OPEN/CLOSE)、circuit 按 allows_open/close 分流
        （Step 6 F-I1：默认 kill 与 DERISK_ONLY 均不得阻断平仓）。
        account_id/strategy_id 显式传参（OrderIntent 与 GuardContext 均不含，F-D2）；
        价格/市值类输入以 ctx 为准（OrderIntent 无 price 字段，execution_policy.py L71-75）。"""
    def gate_kill(self, level: KillLevel, key: str, active: bool, reason: str, *, ts: float) -> KillEntry:
        """更新 kill 状态 → store.save → event_log.append(AUDIT_KILL, build_audit_payload(...))."""
    def on_order_result(self, *, rejected: bool, ts: float) -> CircuitDecision:
        """更新连续拒单计数 → 重新评估 circuit → 写 audit.circuit。"""
    def cancel_all(self, bridge: LiveTradingBridge, *, ts: float) -> int:
        """调 bridge.cancel_orders(None)（= 取消全部未成交；live_bridge.py L97-107 实际
        签名为 ``asset: str | None = None -> int``）→ 返回取消笔数并写 audit.cancel
        （D-G7，Step 4 F-D1 修订：原「order_id 列表 → list[str]」与实际 API 失配）。
        订单 id 级明细待 P-053 扩展 Bridge API 后增强。"""
    @property
    def kill_decision(self) -> KillDecision: ...
    @property
    def circuit_decision(self) -> CircuitDecision: ...
```

**顺序语义（I2）**：`pre_trade_check` 中 kill 与 circuit 的阻断**优先于** Guard；任一 `allowed=False` 必须写 `audit.risk_decision` 且**不发单**（fail-closed）。Guard 内部异常在 `SafetyGate` 中视为 `allowed=False`（D-G2）。

### 3.7 S5 `AuthConfig` 契约（占位，实现归 P-054）

```python
# 位置：core/interfaces.py（Step 4 F-D12 定案；该文件即核心接口定义处）
@dataclass(frozen=True)
class AuthConfig:
    mode: str = "local"                 # "local" | "api_key" | "jwt"
    api_key_env: str = "FT_API_KEY"     # 密钥只经环境注入，不落配置文件
    bind_host: str = "127.0.0.1"        # Q9 推荐 4：仅本机/内网
    require_tls: bool = False           # P-054 承载 TLS
    allowed_origins: tuple[str, ...] = ()
    enable_401_403: bool = True         # 本批只断言契约与用例骨架
```

> 本批**不实现**中间件，只提供 dataclass + 用例骨架（`tests/test_p052_auth_contract.py`，2 例：默认值、环境变量名注入约定）。

---

## 4. 关键决策 D1-D14

| ID | 决策 | 备选与否决理由 |
|----|------|----------------|
| D1 | 安全判定全部纯函数，时间由调用方传入 | `datetime.now` 破坏可重放（I1） |
| D2 | kill 状态用**不可变快照 + 纯迁移**，`live/` 只做落盘 | 可单测、可重放（U-P052-1） |
| D3 | kill 优先级 GLOBAL > ACCOUNT > STRATEGY；低层 `active=False` 不解除高层 | 防绕过（I3） |
| D4 | 熔断 `DERISK_ONLY` 只平不开；`HALTED` 连平仓也停；映射：daily_loss/max_drawdown→DERISK_ONLY，consecutive_rejects→HALTED，人工全停走 kill（F-D4）；判定顺序**严重度优先**：HALTED 先于 DERISK_ONLY（Step 6 D-1，防「全停」被日亏损降级） | 与「只平不开」语义一致 |
| D5 | 熔断阈值经验默认 3%/10%/5 次，可配置 | 无外部强制（U-P052-10） |
| D6 | 速率台账按「epoch 秒滑窗」+「日累计」；撤单率需最小样本 | 避免开盘首笔误判 |
| D7 | 报告 schema 严格对齐第九条 6 类 + 第三十四条 3 项；`missing_required()` 可机械校验 | I7 |
| D8 | `PriceBandGuard` 只读注入字段，不 import `filter` | 保持 core 纯度（D-G6） |
| D9 | `SelfTradeGuard` 先做「同价/穿价对手挂单」最小实现 | 无完整订单簿；足够拦截自成交 |
| D10 | `GuardPlugin` 默认 `on_error="open"`，`SafetyGate` 走 closed | 不破坏回测（P-026 D2.2） |
| D11 | 审计走 `EventLog` 任意 `event_type` + payload 约定，不扩 Entry schema | 避免 golden/旧日志兼容风险（D-G3） |
| D12 | `SafetyGate` 不自动平仓，只发 DERISK 信号 | 平仓属执行层/P-053（D-G9） |
| D13 | 最小 `live/` 只含 `safety_store` + `safety_gate`，不含任何网关 | U-P052-2 |
| D14 | 故障决策确定性（attempts 输入） | 可测、可演练（D-G4） |

---

## 5. 阈值与默认值表

| 配置 | 默认 | 来源/依据 | 可配置 |
|------|------|-----------|--------|
| `RateLimitConfig.max_per_second` | 1 | D2（总纲 L324）项目内部默认 | ✅ |
| `RateLimitConfig.max_per_day` | 1000 | 同上 | ✅ |
| `RateLimitConfig.max_cancel_ratio` | None（关） | 交易所四类异常交易含撤单比例（细则第十八条） | ✅ |
| `CircuitConfig.daily_loss_pct` | 0.03 | 经验默认（U-P052-10） | ✅ |
| `CircuitConfig.max_drawdown_pct` | 0.10 | 经验默认；参考 E16 dd_hard 0.12 | ✅ |
| `CircuitConfig.max_consecutive_rejects` | 5 | 经验默认 | ✅ |
| `AUDIT_RETENTION_YEARS_DEFAULT` | 5 | Q9 推荐 5 | ✅ |
| `AUDIT_RETENTION_YEARS_MAX` | 20 | 细则第十五条 / 证券法 137 条 | 常量 |
| 高频认定（仅参考，不做阈值） | ≥300/秒 或 ≥20000/日 | 细则第三十三条 | 不落地为默认 |

> **红线**：以上内部默认值**不得**在文档/报告/UI 中写成「监管要求」；高频 300/20000 只作为报告字段 `max_order_rate`/`max_daily_orders` 的参考上限背景。

---

## 6. 不变式 I1-I12

| ID | 不变式 | 验证方式 |
|----|--------|----------|
| I1 | `core/safety.py`、`core/circuit_breaker.py`、`core/compliance.py` 无 I/O、无 `datetime.now`、无随机 | AST/按码审查 + 单测固定 ts |
| I2 | `pre_trade_check` 任一阻断 → 不发单；异常 → `allowed=False` | 单测：kill/circuit/rate/guard 各阻断 + 异常注入 |
| I3 | 高层级 kill active 时，低层级 disable 不解除 | 迁移链单测 |
| I4 | kill 状态落盘后 `load()` 恢复一致 | 往返单测 |
| I5 | `DERISK_ONLY` 允许 close、禁止 open；`HALTED` 全禁 | `allows_open/close` 单测 |
| I6 | 审计事件 append-only、`seq` 单调、`replay` 结果一致 | EventLog 既有 + 新类型单测 |
| I7 | 报告字段逐项对齐第九条/第三十四条 | `missing_required()` 单测 |
| I8 | `core/engine_v2.py` / `engine_v3_vector.py` / `sizing.py` / `stops.py` 主路径零 diff | `git diff --stat` |
| I9 | golden 22 条零重录 | `pytest -k golden` |
| I10 | 阈值全部可配置，判定函数体内无硬编码 | 按码审查 + 配置覆盖单测 |
| I11 | `GuardContext` 新字段全带默认，既有 6 Guard 行为不变 | 既有 guard 测试全绿 |
| I12 | `EventLogEntry`/`append` 签名零改动；旧 JSONL 可读 | 旧日志回放单测 |

---

## 7. 测试策略与用例映射

| 测试文件 | 覆盖 | 预计用例 |
|----------|------|----------|
| `tests/test_p052_safety_kill.py` | 三级设置/优先级/低层不解除高层/往返/故障决策 | 14 |
| `tests/test_p052_circuit_breaker.py` | 三阈值/优先级/allows_open/close | 9 |
| `tests/test_p052_compliance.py` | 报告字段校验/速率滑窗/日累计/撤单率/保留常量 | 10 |
| `tests/test_p052_guard_extensions.py` | 5 新 Guard 正反例+边界（等号、None、空列表、样本不足） | 15 |
| `tests/test_p052_eventlog_audit.py` | 8 审计类型 + operator/time_source 约定 + 旧日志兼容 | 6 |
| `tests/test_p052_live_safety_gate.py` | pre_trade_check 顺序/fail-closed/落盘恢复/cancel_all | 10 |
| `tests/test_p052_end_to_end.py` | 策略意图→gate→MockLiveBridge 的 kill/熔断链路 | 4 |
| `tests/test_p052_auth_contract.py` | AuthConfig 默认值 + 环境变量名约定 | 2 |
| **合计** | | **70** |

**读数目标**：pytest **1144 → ≥1214**（+70；Step 5 以 CHECKLIST 实测为准）；`-k golden` 22 零重录；mypy 新增文件 0 error；`black --check .` 保持 unchanged。

> RESEARCH §7 曾估 +45~65；Step 3 细化后为 70（新增 auth 契约 2 例 + 故障决策并入 safety），属合理收敛，差异已记录。

---

## 8. 与总纲 / RESEARCH 的偏差

| 项 | 总纲/RESEARCH | 本设计 | 理由 |
|----|---------------|--------|------|
| S5 实现 | §3.0 列 S5 | 仅契约 + 用例骨架 | U-P052-4；载体 P-054 |
| S6 EventLog | RESEARCH §5.6 拟扩 Entry 字段 | 改为 payload 约定（D11） | 避免 golden/旧日志兼容风险，语义等价 |
| S7 重连 | §3.0 列故障处置 | runbook + 决策 + 注入骨架 | 无真实通道（P-053） |
| S4 报备推送 | §3.0 列合规报告 | 仅 schema + 台账 | 报备主体/通道属 P-053/§7.9 |
| 用例数 | RESEARCH +45~65 | 70 | 测试面细化 |

---

## 9. 风险与未决

| 风险 | 影响 | 缓解 |
|------|------|------|
| 账户熔断阈值无外部依据 | 误熔断/漏熔断 | 全部可配置；默认保守；只进状态迁移测试 |
| `SelfTradeGuard` 无完整订单簿 | 漏拦跨价位自成交 | 最小实现 + 文档标注局限；P-053 接真实订单簿再增强 |
| `live/` 首建目录 | 可能与 P-053 结构冲突 | 仅 2 文件、无网关；P-053 在其上扩展 |
| kill 状态落盘并发 | 多写者覆盖 | 单写者约束（`SafetyGate` 单实例）；P-053 每账户单写者 |
| 审计 payload 约定靠自觉 | 漏 operator | `build_audit_payload` 强制 + 单测 |

**Step 4 复审输入**：本文 §3 全部签名、§5 阈值表、§7 用例映射、§8 偏差。

---

## 10. 出口条件

1. 本设计落盘，Step 4 异构复审 **0 P1**；
2. 三新模块 + 5 Guard + EventLog 常量 + 最小 `live/` + runbook 的签名与语义无歧义；
3. 70 例测试映射可逐条对应到 G1-G9；
4. I1-I12 可机械验证；
5. 无浮空依赖（core 不 import filter/live/services）。
