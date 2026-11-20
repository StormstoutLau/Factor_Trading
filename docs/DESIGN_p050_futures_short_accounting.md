# DESIGN：P-050 期货保证金账目 / 逐日结算 / 强平 / 换月 + 股票负持仓研究模式

> **批次**: P-050 · **Step 3 设计** · 日期 2026-11-20
> **判档**: **T1**（改 `core/tracker.py` / `core/execution.py` / `core/engine_v2.py` / `core/config.py` / `core/invariants.py`，波及 V2/V3/golden）
> **上游**: [RESEARCH_p050](RESEARCH_p050_futures_short_accounting.md)（§4.4 E2 实测 / §5 方案矩阵 / §7 I-P050-1..10 / §8 DoD / §10.0 裁决记录 / §10.5 N-1..N-9 / §14.1 复审通过）
> **代码证据时点**: `c6f172d`（工作区仅文档变更，代码零 diff）
> **作者**: DeepSeek-V4.1-Flash · **Step 4 Review 须异构**（GLM-5.3-Flash）

---

## 1. 范围与前置

**做**
1. 三账模型 A3′：`cash`（可用）、`margin_locked`、`mtm_pnl`；新增 `notional_value`；`get_total_value` 公式不变。
2. 逐日结算 `settle()`：期货盈亏净额入现金、重置结算基准、重算保证金。
3. 强平 C1：结算后 `cash_available < 0` 触发，次日开盘成交，双向平仓，支持顺延。
4. 换月 D1：`expiry - roll_days` 触发 roll，硬约束"不进入交割月"，缺元数据抛错。
5. 股票负持仓开关（默认关）+ 研究模式账目。
6. 反手"先平后开"两笔 + tracker 越量 fail-fast。
7. 成本接线：`asset_type` 透传、乘数、按手费用；V3 显式拒绝。

**不做**：CTP/QMT 实盘、下单协议、实物交割、期权、融券费用模型、多币种（P-056 及以后）；分钟级盘中强平（C3，数据契约不支持）；品种级整倍数/额度规则（仅作元数据输入）。

**前置事实（E2/E3）**
- 空头 `mv/upnl/exposure` **恒 0**，根因是 `update_market_values` 的 `>0` 过滤先于 `abs`（`tracker.py` L223-239）。
- `execute_trade` 双向越量均**静默**：`SELL` 越量翻负且均价不重置；`BUY_TO_COVER` 越量翻多且现金不付（`tracker.py` L73-116）。
- golden 只断言 `portfolio_value` 序列 + metrics + `trades.count`（`tests/_golden_cases.py` L198-217），不读 `cash`/`positions`。
- `IPositionTracker` 无 `settle`；`AbstractPositionTracker` 仅 2 个抽象方法（`interfaces.py` L324-360 / L538-549）。

---

## 2. 设计决策

### 2.0 上游裁决落点

| 裁决 | 结论 | 落点 |
|------|------|------|
| U-P050-1 | A3′ 三账；`market_value` = 持仓权益 | D1 / D2 / §4 |
| U-P050-2 | 引擎内 `settle()`，插在触发判定前；结算价=可选 provider > 收盘价代理 | D3 / D6 / §5 |
| U-P050-3 | C1 触发 + 次日开盘；期末保留当日收盘 | D4 / §6.3 |
| U-P050-4 | D1 roll + 不进入交割月 + 缺元数据抛错；全局默认窗口 + 逐合约覆盖 | D5 / §6.4 |
| U-P050-5 | `allow_negative_stock_positions=False` | D7 / §6.5 |
| U-P050-6 | `AssetInfo` 逐合约 > `MarginConfig` 全局兜底；不内置品种表 | D8 / §5.2 |
| U-P050-7 | 先平后开两笔 + tracker fail-fast | D9 / §6.6 |
| N-1 | `notional_value` + risk_manager 判据重定义 | D2 / D10 / §6.7 |
| N-2 | `settle` 可选能力探测 + 非抽象 no-op + API minor | D11 / §5.1 |
| N-5 | 单一全局 roll 窗口 + 逐合约覆盖 | D5 |
| N-8 | V3 对期货/负持仓显式 raise | D12 / §7 |

### D1 三账的字段语义（A3′）

| 字段 | 股票（现状） | 股票空头（研究模式） | 期货 |
|------|--------------|----------------------|------|
| `cash` | 可用现金 | 可用现金（含开空收款） | **可用资金**（已扣保证金） |
| `margin_locked` | 0 | 0（D3：不计保证金） | 占用保证金 |
| `mtm_pnl` | 0 | 0 | 相对**当日结算价**的浮动盈亏 |
| `notional_value` | `abs(qty)×price` | 同左 | `abs(qty)×price×multiplier` |
| `market_value` | `qty×price` | `qty×price`（**负值**） | `margin_locked + mtm_pnl` |
| `exposure` | `notional_value` | `notional_value` | `notional_value` |

**约束**：`get_total_value() = cash + Σ market_value`（`tracker.py` L290-297）**不改公式**。股票 `margin=0, mtm=0` → 与现状逐位一致。

`notional_value` 在 **`execute_trade`（按成交价）与 `update_market_value`（按最新价）两处写入**；`exposure` 统一返回 `notional_value`（修复 G-16：不再依赖 `market_value`，未盯市时也非 0）。`market_value` 的赋值时机保持现状，避免改变股票 NAV 路径（E2：买入未盯市时 `market_value=0`、`NAV=cash` 不变）。

### D2 类型模型

```python
# core/tracker.py（扩展，全部带默认值）
@dataclass
class Position:
    quantity: float = 0.0
    avg_cost: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    margin_used: float = 0.0          # 既有字段，语义定为"占用保证金"
    # --- P-050 新增 ---
    asset_type: AssetType = AssetType.STOCK
    multiplier: float = 1.0
    notional_value: float = 0.0
    mtm_pnl: float = 0.0              # 相对结算基准的浮动盈亏
    settle_base: float = 0.0          # 结算基准价（期货=最近结算价；股票=avg_cost）
```

```python
# core/execution.py（Trade 扩展）
@dataclass
class Trade:
    ...
    asset_type: AssetType = AssetType.STOCK
    multiplier: float = 1.0
    settlement_price: Optional[float] = None
```

```python
# core/futures_accounting.py（新建，纯函数 + 中立类型，不 import tracker/engine）
@dataclass(frozen=True)
class ContractSpec:
    symbol: str
    multiplier: float = 1.0
    margin_ratio: float = 0.0
    expiry_date: Optional[pd.Timestamp] = None
    roll_days_before_expiry: Optional[int] = None
    roll_target: Optional[str] = None      # 远月合约代码；缺省 → 抛错

@dataclass(frozen=True)
class LiquidationRequest:
    symbol: str
    quantity: float                        # 有符号；正=平多，负=平空
    reason: str = "margin_call"
    deferred_days: int = 0

@dataclass(frozen=True)
class RollInstruction:
    close_symbol: str
    open_symbol: str
    quantity: float                        # 旧合约手数（新合约按 1:1 手数，风险敞口守恒）
    reason: str = "expiry_roll"

@dataclass(frozen=True)
class SettlementResult:
    date: pd.Timestamp
    pnl_by_symbol: dict[str, float]
    total_pnl: float
    margin_after: dict[str, float]
    margin_delta: float                    # 正=补缴（从 cash 扣），负=释放
    settlements_used: dict[str, float]
    proxy_used: bool                       # True = 收盘价代理

class MarginModel(Protocol):
    def initial_margin(self, notional: float, spec: ContractSpec) -> float: ...
    def maintenance_margin(self, notional: float, spec: ContractSpec) -> float: ...
```

```python
# core/engine_v2.py（私有状态）
self._contract_specs: dict[str, ContractSpec] = {}
self._pending_liquidations: list[LiquidationRequest] = []
```

### D3 逐日结算（`settle`）

**触发**：`_process_trading_day` 内、**L545 触发判定之前**、当日行情可用之后。

**公式**（`q` 有符号，`m` 乘数，`S_{t-1}` 为上一结算基准，`S_t` 为当日结算价）：

| 量 | 公式 |
|----|------|
| 当日盈亏 | `pnl = q × (S_t − S_{t-1}) × m` |
| 现金 | `cash += pnl − fee` |
| 结算基准 | `settle_base = S_t`；`avg_cost = S_t`（期货） |
| 保证金 | `margin_locked = Σ abs(q) × S_t × m × ratio` |
| 保证金差额 | `margin_delta = margin_locked − margin_locked_prev`；`cash −= margin_delta` |
| 浮动盈亏 | `mtm_pnl = 0`（结算后归零） |
| 权益 | `market_value = margin_locked` |

**股票**：`settle` 立即早退（`if not self._futures_symbols: return None`），保证零开销、零行为变更。

### D4 强平（C1 + 次日开盘）

**触发**：`settle` 之后，若 `cash < 0`（可用资金为负）→ 生成 `LiquidationRequest`。

**执行**：次一交易日开盘，按 `abs(notional)` 降序逐笔平仓，直至 `cash >= 0` 或全部平仓；无法成交（停板/无价格）→ 保留请求并顺延，日终记 `liquidation_deferred=True`。

**价格**：走 `IExecutionSimulator` 的 `execution_price_type`（默认 `OPEN`），不硬编码收盘价；期末强平用 `price_override=close` 表达。

**订单**：复用 `_next_day_orders` 通道（`engine_v2.py` L1303-1311，泛型 dict 列表，仅需 duck-type `stock/side/quantity`）；`LiquidationRequest` 不是 `PendingOrder` 的子类，避免污染既有队列语义。

**通道适配（复审 RD-1，必须项）**：
1. 强平单**豁免 `_expire_next_day_orders`**（L859-884 按 `max_pending_days_sell` 过期非 BUY 单，且 `order.is_expired` 为 `PendingOrder` 方法——duck-type 强平单会 AttributeError 或被过期，强平单被过期 = 风控失效）；
2. 执行失败**顺延**而非走 L1380-1383 的 `qty<=0` 丢弃分支；空头被前笔平掉后 `BUY_TO_COVER` 全量执行会触发 D9 越量 raise → 需 try/except 转顺延；
3. "按 abs(notional) 降序、直至 cash>=0"的**最小集合裁剪在 `liquidation_requests()` 生成时完成**（泛型执行循环无法中途停止），生成时用"预计释放保证金 + 平仓盈亏投影"排序裁剪。

**与 `_force_liquidation` 的分工**（消除双重实现）：
- **C1 强平（本批主路径）**：结算后 `cash<0` → `LiquidationRequest` → 次日开盘执行；不在当日改仓。
- **`_force_liquidation`（既有路径，仅保留给"期末强制平仓"与显式配置）**：改为双向（移除 `quantity<=0: continue`），价格走执行器；不再承担保证金强平。

### D5 换月（D1）

**触发**：`expiry_date − roll_days_before_expiry(默认 5 个自然日)` 的首个交易日。

**动作**：两笔——`SELL`（或 `BUY_TO_COVER`）平旧 + 反向开新；两笔同样先平后开。

**硬约束**
- 持仓 `expiry` 落在交割月内 → setup 期 `raise ValueError`（不进入交割月）。
- `expiry_date` / `roll_target` / `multiplier` / `margin_ratio` 任一缺失 → `raise ValueError`（不静默持有）。
- 不内置品种表；`roll_days_before_expiry` 全局默认 5，`AssetInfo` 可逐合约覆盖。

### D6 结算价来源

优先级：
1. `IDataManager.get_settlement_prices(date, symbols)`（**可选能力**，`getattr` 探测）；
2. `BacktestConfig.settlement_file`（可选 CSV，列=`date,symbol,settlement`）；
3. 收盘价代理（默认）+ **warning 仅一次**（`self._settle_proxy_warned` 标志）。

不得新增必选数据键；缺省路径在股票模式下完全不触发。

### D7 股票负持仓开关

```python
# core/config.py
allow_negative_stock_positions: bool = False
```

**单一判定入口**（避免 6 处散落布尔）：

```python
def allows_short(self, asset_type: AssetType = AssetType.STOCK) -> bool:
    if asset_type != AssetType.STOCK:
        return True                      # 期货天然双向
    return self.allow_negative_stock_positions
```

6 个闸门（权重截断 L1093、`from_weights` L444-451、`build_target_positions` L79-80、`get_all_positions` L288、`update_market_values` L231、`validate_positions` L466-467）**全部调用该入口**；关闭时短路到既有分支，逐位一致。

### D8 元数据来源与优先级

```
AssetInfo（逐合约，configure_assets 注入）
  → MarginConfig.initial_margin_ratio（全局兜底，默认 0.10）
    → 缺失且 asset_type=FUTURE → raise
```

**期货合约枚举通道（复审 RD-3）**：`get_asset_info` 对未知代码返回默认 STOCK（`data.py` L699-701），引擎**无法反向枚举**哪些合约是期货 → 新增 `BacktestConfig.futures_symbols: list[str] = []`（显式声明），setup 期按该列表 + `dm.get_asset_info` 构建 `_contract_specs`；列表为空 → 全程走股票路径（零开销）。不新增 dm 枚举方法，避免扩 `IDataManager` 契约。

`multiplier`、`margin_ratio`、`expiry_date` 三者对期货为**必填**；股票缺省 `(1.0, 0.0, None)`。

### D9 反手与越量守卫

- **意图层**：`SignalTranslator.from_weights` 在 `target_w < 0` 且 `allow_short` 时生成两笔 `OrderIntent`（先 `SELL` 到 0，再 `SELL_SHORT` 到目标）。
- **legacy 层**：`_generate_rebalance_orders` 抽公共助手 `split_reversal(current_qty, target_qty) -> list[(side, qty)]`，与意图层同源；legacy 仅在其无 policy 时使用。
- **tracker 层**：`execute_trade` 越量（`SELL` 数量 > 多头持仓、`BUY_TO_COVER` > 空头持仓、`SELL_SHORT` 遇多头持仓、`BUY` 遇空头持仓）→ `raise ValueError`。开关关闭且股票 → 保持既有行为（生产路径已有 clamp，不触发）。

### D10 risk_manager 诊断口径重定义

| 项 | 现状（死代码） | 重定义后 |
|----|----------------|----------|
| 分母 | `market_value` | `notional_value` |
| 比率 | `margin_used / market_value` | `risk_ratio = margin_used / notional_value` |
| 动作 | `FORCE_CLOSE` 信号 | **仅诊断输出，不产生动作**；本批强平唯一判据是 C1（`cash_available < 0`），避免双判据冲突（G-11 留待后续批次闭环） |

本批 `MarkToMarketPolicy` 默认不注入（`engine_v2.py` L144/L180），生产行为不变；重定义只保证该组件在期货下口径正确。复审 R3 的"方向不自洽"以**停用动作、只保留诊断**方式消解，不再沿用 `<` 判据。

### D11 契约兼容

- `IPositionTracker` 增 `settle(...)` **文档成员**；引擎用 `getattr(self.tracker, "settle", None)` 探测，缺省跳过。
- `AbstractPositionTracker` 增**非抽象** `settle` no-op（返回 `None`），子类零改动。
- `core/__init__.py` `__api_version__`：`3.1.0 → 3.2.0`。

### D12 V3 拒绝

`BacktestEngineV3.__init__`（`engine_v3_vector.py` L222，接受**普通 dict** 配置）在 `run()` 前检查（复审 RD-2：V3 无 per-symbol `asset_type` 通道，`DataLoaderV3` 仅股票数据，原表述"cfg 中存在 asset_type=FUTURE 的标的"不可实现）：
- `cfg.get("allow_negative_stock_positions", False)` 为真，或
- `cfg.get("futures_symbols")` 非空列表

→ `raise ValueError("V3 不支持期货/负持仓；请使用 V2")`。不改变既有股票配置行为。

---

## 3. 精确签名

### 3.1 `core/futures_accounting.py`（新建）

```python
def compute_settlement(
    positions: Mapping[str, Position],
    settlements: Mapping[str, float],
    specs: Mapping[str, ContractSpec],
    margin_model: MarginModel,
) -> SettlementResult: ...

def apply_settlement(
    cash: float,
    margin_prev: float,
    result: SettlementResult,
) -> tuple[float, float]: ...          # (cash_after, margin_after)

def liquidation_requests(
    positions: Mapping[str, Position],
    cash: float,
    specs: Mapping[str, ContractSpec],
) -> list[LiquidationRequest]: ...

def roll_orders(
    positions: Mapping[str, Position],
    specs: Mapping[str, ContractSpec],
    date: pd.Timestamp,
    default_roll_days: int = 5,
) -> list[RollInstruction]: ...

def split_reversal(current_qty: float, target_qty: float) -> list[tuple[str, float]]: ...
```

纯函数约束：不 import `core.tracker` / `core.engine_v2`；只依赖 `numpy` / `pandas` / `dataclasses` / `typing`。

### 3.2 `core/tracker.py`

```python
class Position:
    def update_market_value(self, price: float) -> None: ...
    def notional(self, price: float) -> float: ...

class PositionTracker:
    def settle(
        self,
        date: pd.Timestamp,
        settlements: Mapping[str, float],
        specs: Mapping[str, ContractSpec],
        fallback_prices: Optional[Mapping[str, float]] = None,  # RI-1 同步：tracker 无价格缓存
        margin_model: Optional[MarginModel] = None,
    ) -> Optional[SettlementResult]: ...
    def get_available_cash(self) -> float: ...
    def get_total_cash(self) -> float: ...     # available + Σ margin_used
```

### 3.3 `core/config.py`

```python
@dataclass
class AssetInfo:
    ...
    roll_days_before_expiry: Optional[int] = None
    roll_target: Optional[str] = None

@dataclass
class BacktestConfig:
    ...
    allow_negative_stock_positions: bool = False
    settlement_file: Optional[Path] = None
    liquidation_price_type: ExecutionPriceType = ExecutionPriceType.OPEN
```

### 3.4 `core/engine_v2.py`（最小 diff）

| 位置 | 改动 |
|------|------|
| `setup()` | 解析 `AssetInfo` → `_contract_specs`；期货缺字段 → raise；交割月校验 |
| L545 之前 | `settle` 探测调用 + `_pending_liquidations` 生成 |
| L541-542 次日队列 | 前置注入 `LiquidationRequest`（开盘价、优先于信号单） |
| L556-557 | 期货：**仍调用** `update_market_values`（快照在此生成，不能跳过），但按 `asset_type=FUTURE` 走"重算 mtm 与 `market_value=margin+mtm`"分支，不改现金；股票保持原路径 |
| L1093 / L1175-1186 | 负权重与空头腿按 `allows_short` 分支 |
| L1274-1301 | 反手拆单调用 `split_reversal` |
| `target_positions.compute_portfolio_value` L148-188 | **估值口径（复审 RD-4 + Step 8 SC-6 勘误）**：该函数按 `qty×price` 重算（文档串 L157-158 明示不用 `market_value`）。A3′ 可用现金口径下，期货按名义乘数重算会漏掉保证金占用（NAV 差 `margin_t`）→ 期货改走 `market_values`（= margin+mtm，settle 每日刷新、日序先于调仓）；股票保持重算；`qty<=0` 跳过（L174）接 `allows_short` 分支 |
| `tracker.get_position_weights` L307-325 / L347 | **期货权重口径（复审 RD-5）**：现用 `market_value/total_value`（L323），期货下=保证金占比（≈名义 10%）→ 期货改用 `notional_value` 计权重与行业敞口；股票不变 |
| `tracker.validate_positions` L473-476 | 市值一致性校验 `qty×prices` 对期货必误报 → 按 `asset_type` 分支（期货校验 `market_value == margin_used + mtm_pnl`） |
| L650-718 | 期末/显式强平：双向 + 价格走 executor（保证金强平走 D4 新通道，不经此处） |
| `__init__` | V3 拒绝不在本类；V3 自身加校验 |

---

## 4. 数据流与边界

### 4.1 单日时序（期货启用）

```
1. 开盘价成交（含前一日强平/roll 指令）
2. 结算价解析（provider > file > close 代理）
3. tracker.settle()            ← 盈亏入 cash、保证金重算、基准重置
4. 强平判定 → _pending_liquidations（次日开盘执行）
5. 触发判定 → 再平衡 → 目标持仓
6. 收盘快照（cash/margin/mtm 一致）
7. overlay NAV（读 get_total_value，公式不变）
8. 风控日志
```

### 4.2 账目闭式样例（IH，`m=300`，`ratio=0.10`）

开仓 1 手 @3500，初始 1,000,000：
- 保证金 = `1×3500×300×0.10 = 105,000`；`cash = 1,000,000 − 105,000 = 895,000`；NAV = `895,000 + 105,000 = 1,000,000`。
- 结算价 3480：`pnl = 1×(3480−3500)×300 = −6,000` → `cash = 889,000`；新保证金 `= 3480×300×0.10 = 104,400`，`margin_delta = 104,400 − 105,000 = −600`（释放）→ `cash = 889,000 + 600 = 889,600`。
- `mtm = 0`，`market_value = 104,400`；NAV = `889,600 + 104,400 = 994,000 = 1,000,000 − 6,000` ✓（保证金差额已计入现金，不可重复扣减）。

反手（股票研究模式，`q=+100 → −50`，价 10）：
- 第一笔 `SELL 100` → `qty=0`，`cash += 1,000`；第二笔 `SELL_SHORT 50` → `qty=−50`，`cash += 500`。
- 越量守卫：若误发 `SELL 150` → `ValueError`（不静默翻负）。

---

## 5. 接口与兼容性

### 5.1 可选能力探测（N-2）

```python
settle = getattr(self.tracker, "settle", None)
if settle is not None and self._contract_specs:
    self._last_settlement = settle(date, settlements, self._contract_specs)
```

与既有 `pipeline.set_error_sink` 探测同式（`engine_v2.setup()`）。

### 5.2 成本与乘数接线

- `_calculate_cost(amount, side, asset_type=STOCK)` 已有默认值（`execution.py` L367-382）→ 调用处补传 `trade.asset_type`（L330）。
- `amount = quantity × price × multiplier`（L327）→ 仅 `asset_type=FUTURE` 时乘 `multiplier`，股票路径不变。
- 期货费用：`exchange_fee`（按名义）+ `commission_rate`/`commission_min`（沿用），**不做平今/平昨细分**（研究 §5.6 未裁决，P-056 补）；`asset_type=FUTURE` 时**印花税恒为 0**（不按 side 判断，避免平仓侧误收）。
- 平仓现金流：期货 `cash += released_margin + q×(exit_px − settle_base)×m − fee`；股票按全额成交额入账（`tracker.execute_trade` 内按 `asset_type` 分支）。

### 5.3 兼容矩阵

| 配置 | 代码路径 | 既有输出 |
|------|----------|----------|
| 纯股票多头（现状） | 全部走 `asset_type=STOCK` 分支 | **逐位一致**（I-P050-7） |
| 股票 + 负持仓开关关 | 同上 + `allows_short` 短路 | 逐位一致 |
| 股票 + 开关开 | 空头记账、不取 abs、不保证金 | 新增测试 |
| 期货 | `settle` + 保证金 + 强平/roll | synthetic golden |
| V3 + 期货/开关开 | `raise ValueError` | 新测试 |

---

## 6. 错误与拒绝路径

| 场景 | 行为 | 消息要点 |
|------|------|----------|
| 期货缺 `multiplier/margin_ratio/expiry` | `raise ValueError`（setup 期） | 指明合约与缺失字段 |
| `expiry` 落在交割月 | `raise ValueError`（setup 期） | 禁止进入交割月 |
| roll 缺 `roll_target` | `raise ValueError`（触发日） | 无远月合约 |
| 越量成交 | `raise ValueError`（tracker） | 当前数量/成交数量/方向 |
| V3 + 期货或负持仓 | `raise ValueError`（初始化） | 指向 V2 |
| 结算价缺失 | 收盘代理 + warning 一次 | 不静默改变口径 |
| 强平无法成交 | 保留请求、日终标记、次日重试 | 不吞掉失败 |

---

## 7. 不变式与门禁

| invariant | 断言 | 实现位置 |
|-----------|------|----------|
| I1（改注释） | `total_value == cash + Σ market_value`（语义已含 margin+mtm） | `invariants.py` L88-110 |
| I6（新；RI-9：模块内 I5 已被 `check_v3_nav_identity` 占用；== 研究 I-P050-3 保证金，Step 8 SC-3 勘误） | `margin_used == Σ abs(qty)×settle×m×ratio` | `invariants.py` |
| I7（新；== 研究 I-P050-10 名义/exposure，SC-3 勘误） | `notional_value == abs(qty)×price×m` | `invariants.py` |
| I8（新；== 研究 I-P050-2 现金流，SC-3 勘误） | `cash_t − cash_{t-1} == Σ pnl − fee − Δmargin` | 单测 |
| I-P050-9 | 越量 → raise | 单测 |
| I-P050-10 | `exposure == abs(qty)×price×m`（未盯市也非 0） | 单测 |

**门禁**：`pytest` 基线须在 Step 4 重跑（研究 §9 的 987 为继承值，不可直接引用）；`tests/golden/` 12/12 diff 为空；`mypy` 0 error；`black` 不劣化。

---

## 8. 测试设计

### 8.1 单测 `tests/test_p050_futures_accounting.py`

| # | 用例 | 断言 |
|---|------|------|
| F1 | 期货多头开仓 | `cash` 扣保证金、`margin_used`、`notional` 三值闭式 |
| F2 | 期货逐日结算（涨/跌） | `cash` 变动 = `pnl − Δmargin`；`mtm=0`；`settle_base` 更新 |
| F3 | 期货平仓 | 保证金全额释放；累计盈亏 = 两日 pnl |
| F4 | 期货空头 | `q<0` 时方向/盈亏/保证金符号正确 |
| F5 | 保证金不足触发 | `cash<0` → 生成 `LiquidationRequest` |
| F6 | 强平次日成交 | 持仓归零、`cash>=0`；无法成交 → 顺延 |
| F7 | roll | 新旧合约敞口守恒；`expiry` 缺失 → raise |
| F8 | 股票空头研究模式 | `NAV = C + q(P0−P)`（`q`=开空股数，正数）；`exposure>0` |
| F9 | 股票开关关闭 | 与现状逐位一致（对照 3 个场景） |
| F10 | 越量四向 | `SELL/BUY_TO_COVER/SELL_SHORT/BUY` 越量均 raise |
| F11 | 反手拆单 | 两笔、顺序、费用分笔、中间 `cash` 断言 |
| F12 | V3 拒绝 | 期货配置 raise |
| F13 | 成本接线 | `asset_type=FUTURE` 时 `exchange_fee` 生效、印花税不生效 |

### 8.2 golden `tests/golden/p050/`

| 文件 | 场景 | 断言面 |
|------|------|--------|
| `P050_S1_futures_long.json` | 1 手 IH 三日，含一次结算 | NAV 序列 + trades.count |
| `P050_S2_futures_short.json` | 空头三日 | 同上 |
| `P050_S3_margin_call.json` | 结算后 `cash<0` → 次日强平 | 同上 + 最终持仓 0 |
| `P050_S4_roll.json` | 到期前 roll | 同上 + 敞口守恒 |

期望值全部闭式手算入档（§4.2 样式），禁止录制。

### 8.3 零重录验证

`git diff tests/golden/` 为空 + `pytest -k golden` 通过；新增 golden 用独立 `GOLDEN_DIR` 装载，不改既有用例收集逻辑。

---

## 9. 风险与回退

| ID | 风险 | 触发信号 | 回退 |
|----|------|----------|------|
| R1 | 股票路径被意外改动 | 12 golden 任一 diff 非空 | 回滚 `tracker` 分支改动，保留字段默认值 |
| R2 | `market_value` 语义变更影响 overlay/sizing | overlay 读数变化 | 新增 `equity_value` 字段并保持 `market_value` 旧义（备选方案） |
| R3 | risk_manager 判据方向 | Step 4 闭式表不自洽 | 本批停用该分支（保持 `margin_used=0` 早退） |
| R4 | 注入式 tracker Mock 被 `settle` 打断 | 单测 `AttributeError` | 已用 `getattr` 探测，仍失败则改为 config 开关 |
| R5 | golden 新例波动导致门禁抖动 | 重跑不一致 | 固定种子 + 合成数据，不依赖外部行情 |

---

## 10. 待验证假设（Step 4 Review 输入）

| # | 假设 | 验证方式 |
|---|------|----------|
| V1 △ | 通道可承载（泛型 dict），但 2 个硬闸门：L859-884 过期逻辑会过期/崩溃强平单；L1380-1383 丢弃而非顺延 | 已读 L1303-1398 + L859-884，适配方案见 D4（RD-1） |
| V2 ✓ | `PendingOrder` 无 `reason` 字段（仅有 `order_type`）→ 强平需独立结构 | 已读 `pending.py` L51-64（2026-11-20 验证） |
| V3 △ | `__init__`（L222，dict 配置）可插校验；但"asset_type=FUTURE 标的"无通道，触发条件改为配置键 | 已读 L222/L256/L287-401，见 D12（RD-2） |
| V4 △ | 读取通道存在（L690-718 ✓），但引擎**无法枚举**期货合约（未知代码返回默认 STOCK）→ 新增 `cfg.futures_symbols` | 已读，见 D8（RD-3） |
| V5 ✓ | 字段名（action/asset/reason/severity）不变；risk_manager 默认不注入、动作仅记日志（engine L571-578） | 已读 L161-188（2026-11-20） |
| V6 ✗ | 发现设计遗漏：`compute_portfolio_value` 按 `qty×price` 无乘数（差 1/m）；权重=保证金占比口径未定义；`validate_positions` L473 市值校验对期货必误报 | 已读 target_positions L148-188 + tracker L307-347/L473，修复落点见 §3.4（RD-4/RD-5） |
| V7 ✓ | `core.tracker` 引入 `AssetType` 不产生循环导入 | 已实测：`import core.tracker, core.config` 通过（tracker→execution→config，2026-11-20 验证） |

---

## 11. 自检

- [x] 每条上游裁决均有唯一落点（§2.0）
- [x] 兼容性：未启用期货/负持仓时零新路径（§5.3 + I-P050-7）
- [x] 可升级：不内置品种表，roll 窗口与保证金率均为元数据/配置驱动
- [x] 易插拔：`settle` 可选探测、`MarginModel` 协议、结算价 provider、费用复用 `CostConfig`
- [x] 所有新增字段带默认值，不破坏既有构造调用
- [x] 错误路径全部显式（§6），无静默降级
- [x] 测试期望值闭式手算，无录制
- [x] Step 4 异构 Review（GLM-5.3-Flash，2026-11-20）——**有条件通过**（RD-1..RD-5 全部处置，见 §12）
- [x] V1-V7 假设验证完成：V2/V5/V7 直接通过；V1/V3/V4 有条件通过（适配方案已回写正文）；V6 发现设计遗漏（已补 §3.4）
- [x] Step 5 IMPL 落地 + Step 6 IMPL 复审（RI-1..RI-9 全部处置，见 IMPL §15）——本文件已同步 settle 签名（`fallback_prices`）与不变量编号（I6/I7/I8）
- [x] Step 8 一致性检查**通过**（SC-1..SC-6，见 CHECKLIST §7）——本文件已同步 §3.4 估值口径（期货走 `market_values`，SC-6）与 §7 映射（SC-3）

---

## 12. Step 4 异构复审记录（复审方 GLM-5.3-Flash，2026-11-20）

**方式**：复审方独立读码验证 §10 全部假设与关键锚点（`engine_v2.py` L520-560 / L806-828 / L859-884 / L1298-1398、`engine_v3_vector.py` L26-37 / L222-401、`data.py` L686-718、`risk_manager.py` L140-190、`interfaces.py` L26-136、`target_positions.py` L148-188、`pending.py` L28-73），不信任作者转述。

**结论**：**有条件通过**。7 项假设中 V2/V5/V7 直接通过；V1/V3/V4 有条件通过（通道存在但需适配，方案已回写正文）；V6 发现 1 处设计遗漏（已补 §3.4）。另复核：D3 插入点（L543-544，queue 之后 trigger 之前）与 §4.1 时序自洽——次日开盘单在 L537-538 执行、settle 在 L543-544、强平判定随后、L556-557 收盘分支不改现金；§4.2 闭式样例重算无误（NAV=994,000 与"初始−亏损"闭合）。

**发现与处置**

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| RD-1 | **major** | `_next_day_orders` 通道 2 个硬闸门：①L1326 过期步骤按 `max_pending_days_sell` 过期非 BUY 单（`order.is_expired` 为 `PendingOrder` 方法，duck-type 强平单会 AttributeError 或被过期）→ **强平单被过期 = 风控失效**；②L1380-1383 `qty<=0` 丢弃而非顺延；空头被前笔平掉后 `BUY_TO_COVER` 全量执行触发 D9 越量 raise 未捕获 | D4 已补"通道适配"三条：豁免过期、失败转顺延、最小集合生成时裁剪 |
| RD-2 | minor | D12 原触发条件"cfg 中存在 asset_type=FUTURE 的标的"不可实现：V3 接受普通 dict（L222），无 per-symbol 通道，`DataLoaderV3` 仅股票数据 | D12 已改为配置键判定（`allow_negative_stock_positions` / `futures_symbols`） |
| RD-3 | minor | 引擎无法枚举期货合约：`get_asset_info` 未知代码返回默认 STOCK（`data.py` L699-701），无反向枚举入口 | D8 已补 `BacktestConfig.futures_symbols` 显式声明，空列表=纯股票零开销 |
| RD-4 | **major** | **设计遗漏**：`compute_portfolio_value`（`target_positions.py` L148-188）按 `qty×price` 重算调仓估值（文档串 L157-158 明示不用 `market_value`），期货差 1/m 倍；研究 §10.2 已列影响面但设计 §3.4 落点表漏写 | §3.4 已补乘数修复行 |
| RD-5 | **major** | 期货权重/校验口径未定义：`get_position_weights` 用 `market_value`（期货=保证金占比≈名义 10%，权重失真）；`validate_positions` L473 `qty×prices` 市值校验对期货必误报 | §3.4 已补：期货权重/行业敞口用 `notional_value`；validate 按 `asset_type` 分支 |

**复审意见**：RD-4/RD-5 属"研究影响面已列、设计落点漏写"，补齐后设计完整；RD-1 是实现期最易踩的坑（强平单混入通用过期/丢弃逻辑），已在 D4 写死适配方案。无未决分歧，**可进入 Step 5（IMPL）**。
