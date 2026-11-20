# IMPL P-050 期货账目 / 逐日结算 / 强平 / 换月（Step 5 实施文档）

> **批次**: P-050 · **Step 5 实施规格** · 2026-11-20
> **上游**: [DESIGN_p050](DESIGN_p050_futures_short_accounting.md)（含 Step 4 复审 RD-1..RD-5）+ [RESEARCH_p050](RESEARCH_p050_futures_short_accounting.md)（含 E2 实测）
> **代码基线**: `c6f172d` 后工作区（代码零 diff）
> **作者**: DeepSeek-V4.1-Flash · **Step 6 Review 须异构**（GLM-5.3-Flash）
> **性质**: 实施指南——精确到函数签名、代码骨架、锚点与验收命令；**不含**已落盘代码

---

## 1. 实施总览

### 1.1 任务与依赖

| 任务 | 内容 | 依赖 | 规模 |
|------|------|------|------|
| **T0** | 基线读数（测试/ golden / mypy / black） | — | 0 行 |
| **T1** | `core/config.py` + `core/tracker.py` 字段扩展（零行为） | T0 | ~55 行 |
| **T2** | `core/execution.py` 乘数 + 成本接线 | T1 | ~25 行 |
| **T3** | 股票负持仓开关 + 6 闸门 + 越量守卫 | T1 | ~45 行 |
| **T4** | `core/futures_accounting.py` 纯函数 + 单测 F1-F5/F8/F10/F11 | T1 | ~230 行 |
| **T5** | `PositionTracker.settle` + `get_available_cash` | T4 | ~80 行 |
| **T6** | 引擎接线：settle / 强平 / 换月 / 结算价 / 估值乘数（§8.5）/ 权重与校验口径（§8.6） | T2/T3/T5 | ~140 行 |
| **T7** | `invariants.py` I6/I7 + `risk_manager` 分母与诊断化（S7 补登）+ V3 拒绝 + `__api_version__` | T6 | ~85 行 |
| **T8** | golden `p050/` 4 例（闭式手算） | T6 | ~200 行 |
| **T9** | 全量门禁 + 文档回写 | 全部 | 0 行 |

**依赖序**：T0 → T1 →（T2 ∥ T3）→ T4 → T5 → T6 →（T7 ∥ T8）→ T9

**每步硬门禁**（不可跳）：
1. `pytest -q` 全绿；
2. `git diff --stat tests/golden/` **为空**（T8 前）；
3. T8 后仅允许新增 `p050/` 子目录，既有 12 例字节不变。

### 1.2 文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `core/futures_accounting.py` | **新建** | 唯一新源模块（纯函数，mypy 文件数 +1） |
| `core/config.py` | 改 | `BacktestConfig` +4 字段；`AssetInfo` +2 字段 |
| `core/tracker.py` | 改 | `Position` +5 字段；`execute_trade` 分支；`settle`；`exposure`；权重/校验 |
| `core/execution.py` | 改 | `Trade` +3 字段；`execute_order` 乘数；`_calculate_cost` 传 `asset_type` |
| `core/engine_v2.py` | 改 | 6 处：specs 构建、settle、强平队列、过期豁免、顺延、roll |
| `core/invariants.py` | 改 | I6/I7（模块新增）；I1 注释 |
| `core/interfaces.py` | 改 | `IPositionTracker` 文档成员 `settle`；`AbstractPositionTracker` 非抽象 no-op（DESIGN D11，Step 8 SC-2 补登） |
| `core/target_positions.py` | 改 | `compute_portfolio_value` 增 `equity_symbols`/`allow_negative_stock`（期货权益口径，SC-6）；`qty<=0` 分支 |
| `core/execution_policy.py` | 改 | `SignalTranslator` 增 `allow_short`；负权重反向意图（T3） |
| `core/risk_manager.py` | 改 | **S7 补登（Step 6 漏列）**：分母 `market_value → notional_value`，动作降为仅诊断（DESIGN D10 / N-1） |
| `core/engine_v3_vector.py` | 改 | 配置键拒绝 |
| `core/__init__.py` | 改 | `__api_version__` → `3.2.0` |
| `tests/test_p050_futures_accounting.py` | **新建** | 纯函数 + tracker 单测 |
| `tests/test_p050_engine_integration.py` | **新建** | 引擎/强平/roll/V3 |
| `tests/golden/p050/*.json` | **新建** | 4 例 |

---

## 2. T0 基线

```bash
pytest -q > %TEMP%\p050_t0_pytest.txt 2>&1
pytest -q -k golden > %TEMP%\p050_t0_golden.txt 2>&1
mypy core filter tests > %TEMP%\p050_t0_mypy.txt 2>&1
black --check core tests > %TEMP%\p050_t0_black.txt 2>&1
git status --short > %TEMP%\p050_t0_status.txt 2>&1
```

**入档**：passed/跳过数、golden 用例数、mypy 文件数、black 差异数、工作区已改文件清单。**禁止引用研究 §9 的 987**（继承值）。

**回退点**：无需回退（只读）。

---

## 3. T1 字段扩展（零行为）

### 3.1 `core/config.py`

```python
# AssetInfo（L151-166 内追加，均在末尾以默认值结尾）
roll_days_before_expiry: Optional[int] = None
roll_target: Optional[str] = None

# BacktestConfig（L421-422 risk_overlay 之后追加）
allow_negative_stock_positions: bool = False
settlement_file: Optional[Path] = None
futures_symbols: list[str] = field(default_factory=list)
liquidation_price_type: ExecutionPriceType = ExecutionPriceType.OPEN
```

`allows_short` 方法（D7 单一入口）：

```python
def allows_short(self, asset_type: AssetType = AssetType.STOCK) -> bool:
    if asset_type != AssetType.STOCK:
        return True
    return self.allow_negative_stock_positions
```

放置位置：`BacktestConfig` 方法区（`validate()` 之前）。注意 `AssetType` 已在同文件定义，无需导入。

### 3.2 `core/tracker.py`

```python
@dataclass
class Position:
    # 既有 6 字段不变
    asset_type: AssetType = AssetType.STOCK
    multiplier: float = 1.0
    notional_value: float = 0.0
    mtm_pnl: float = 0.0
    settle_base: float = 0.0
```

导入：`from core.config import AssetType`（V7 已验证无环）。

**本步只加字段，不改任何赋值逻辑**；`Position` 现有构造调用（含测试）全部依赖默认值。

### 3.3 `core/execution.py`

```python
@dataclass
class Trade:
    # 既有 8 字段不变
    asset_type: AssetType = AssetType.STOCK
    multiplier: float = 1.0
    settlement_price: Optional[float] = None
```

**验收**：`pytest -q` 与 T0 同结果；`git diff tests/golden/` 空。

**回退点**：仅 `config.py` / `tracker.py` / `execution.py` 的字段块——删除新增行即可，无行为耦合。

---

## 4. T2 乘数与成本接线

### 4.1 `execute_order`（L273-364）

```python
# L327 原：amount = quantity * execution_price
multiplier = getattr(asset_info_or_trade, "multiplier", 1.0)
amount = quantity * execution_price * multiplier
```

**取值路径（复审 RI-6 定案，消除实施期悬置）**：`execute_order`（签名 L273-284，无 asset 通道；`ExecutionSimulator` 为独立类）→ 构造函数增可选 `asset_specs: Optional[Mapping[str, object]] = None`（引擎 setup 用 `cfg.futures_symbols` 构建并注入）：

```python
info = self._asset_specs.get(stock) if self._asset_specs else None
mult = getattr(info, "multiplier", 1.0) or 1.0
a_type = getattr(info, "asset_type", AssetType.STOCK)
amount = quantity * execution_price * mult                  # L327 替换
cost = self._calculate_cost(amount, side, asset_type=a_type)  # L330
# Trade(..., asset_type=a_type, multiplier=mult)             # 构造处
```

**定案理由**：若改走"tracker 侧乘"，`_calculate_cost` 收到的 `amount` 仍是无乘数点值 → 期货佣金/交易所费错 1/m（与 §4.2 自相矛盾）。乘数必须在 `execute_order` 落入 `amount`，成本与净额一次算对。`asset_specs=None` 时 `mult=1`、`a_type=STOCK` → 股票路径逐位不变。

### 4.2 `_calculate_cost`（L366-407）

- 调用处 L330 补 `asset_type=...`（默认 STOCK，路径不变）；
- 印花税：`side == SELL and asset_type != FUTURE`（期货恒 0）；
- 平仓现金流（`tracker.execute_trade`）：

```python
if asset_type == AssetType.FUTURE:
    released = margin_used * (closed_qty / abs(qty_before))
    cash += released + q * (price - settle_base) * multiplier - cost
else:  # 股票原路径
    ...
```

**验收**：股票 golden 零 diff；新增单测断言 `asset_type=FUTURE` 时印花税 0、`exchange_fee` 生效。

**回退点**：`execution.py` 两处 + `tracker.execute_trade` 的 FUTURE 分支（股票分支不触碰）。

---

## 5. T3 股票负持仓 + 越量守卫

### 5.1 6 个闸门统一

| 位置 | 原 | 改 |
|------|----|----|
| `engine_v2.py` L1093 | `clip(lower=0.0)` | `clip(lower=0.0) if not allows_short else 原值` |
| `execution_policy.py` L444-451 | 仅 `target_w > 0` | `SignalTranslator` 构造增 `allow_short: bool = False`；为真时负权重走反向意图 |
| `target_positions.py` L79-80 | 负权重 raise | `allows_short` 为真时放行 |
| `tracker.get_all_positions` L288 | `quantity > 0` | `quantity > 0 or allows_short` |
| `tracker.update_market_values` L231 | `quantity > 0` | 同上 |
| `tracker.validate_positions` L466-467 | 负数量记错误 | `allows_short` 为真时跳过该条 |

`allows_short` 在 tracker 内无 `cfg` 引用 → 用构造函数注入 `allow_negative_stock_positions: bool = False`，`engine.setup()` 传入；缺省 False。

### 5.2 越量守卫（I-P050-9）

```python
# tracker.Position.execute_trade 四个分支入口
if side == OrderSide.SELL and trade.quantity > max(self.quantity, 0.0) + 1e-9:
    raise ValueError(f"SELL 越量: 持有 {self.quantity}, 卖出 {trade.quantity}")
if side == OrderSide.BUY_TO_COVER and trade.quantity > abs(min(self.quantity, 0.0)) + 1e-9:
    raise ValueError(...)
if side == OrderSide.SELL_SHORT and self.quantity > 1e-9:
    raise ValueError(...)
if side == OrderSide.BUY and self.quantity < -1e-9:
    raise ValueError(...)
```

**约束**：股票路径已有 `_clamp_sell_quantity`（L811-828）保证不越量 → 新增 raise 在存量测试中**不应触发**；若触发，说明存在既有越量调用，必须先查清再放行（不得用 try/except 吞掉）。

**验收**：F10 四向 raise；F9 开关关闭 3 场景与现状逐位一致（RI-5：归入 `test_p050_futures_accounting.py`，DESIGN §8.1 的 F9 此前无落点）；`pytest -q` 全绿（重点看 `test_p014` / `test_p031` / `test_p045`）。

**回退点**：闸门改动逐文件独立，可单独 revert；`execute_trade` 守卫可整块删除。

---

## 6. T4 `core/futures_accounting.py`（纯函数）

### 6.1 模块头

```python
"""P-050 期货账目纯函数层。

不 import tracker/engine；只依赖 numpy/pandas/dataclasses/typing。
所有函数无副作用，输入不可变视图，输出新对象。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol, Sequence, runtime_checkable

import pandas as pd

__all__ = [
    "ContractSpec", "LiquidationRequest", "RollInstruction", "SettlementResult",
    "MarginModel", "ExchangeMarginModel",
    "compute_settlement", "apply_settlement",
    "liquidation_requests", "roll_orders", "split_reversal",
]
```

### 6.2 类型（与 DESIGN §3.1 逐字一致）

```python
@dataclass(frozen=True)
class ContractSpec:
    symbol: str
    multiplier: float = 1.0
    margin_ratio: float = 0.0
    expiry_date: Optional[pd.Timestamp] = None
    roll_days_before_expiry: Optional[int] = None
    roll_target: Optional[str] = None

@dataclass(frozen=True)
class LiquidationRequest:
    symbol: str
    quantity: float          # 有符号：正=平多，负=平空
    reason: str = "margin_call"
    deferred_days: int = 0

@dataclass(frozen=True)
class RollInstruction:
    close_symbol: str
    open_symbol: str
    quantity: float
    reason: str = "expiry_roll"

@dataclass(frozen=True)
class SettlementResult:
    date: pd.Timestamp
    pnl_by_symbol: dict[str, float]
    total_pnl: float
    margin_after: dict[str, float]
    margin_delta: float
    settlements_used: dict[str, float]
    proxy_used: bool

@runtime_checkable
class MarginModel(Protocol):
    def initial_margin(self, notional: float, spec: ContractSpec) -> float: ...
    def maintenance_margin(self, notional: float, spec: ContractSpec) -> float: ...

class ExchangeMarginModel:
    """默认：按 spec.margin_ratio（交易所最低保证金率）计提。"""
    def initial_margin(self, notional, spec): return notional * spec.margin_ratio
    def maintenance_margin(self, notional, spec): return notional * spec.margin_ratio
```

### 6.3 函数骨架

```python
def compute_settlement(positions, settlements, specs, margin_model) -> SettlementResult:
    """逐合约：pnl = q × (S_t − settle_base) × m；重建保证金。缺 settlement → 跳过并记 proxy_used=False。"""

def apply_settlement(cash, margin_prev, result) -> tuple[float, float]:
    """cash += total_pnl − margin_delta；返回 (cash_after, margin_after)。"""

def liquidation_requests(positions, cash, specs):
    """cash >= 0 → []；否则按 |notional| 降序生成，直到"预计释放保证金 + 平仓盈亏投影"覆盖缺口。"""

def roll_orders(positions, specs, date, default_roll_days=5):
    """expiry − roll_days ≤ date 且未平 → RollInstruction；缺 roll_target → ValueError。"""

def split_reversal(current_qty, target_qty) -> list[tuple[str, float]]:
    """同号 → 单笔差额；异号 → [(平仓侧, |current|), (开仓侧, |target|)]。
    侧别用字符串（"SELL"/"SELL_SHORT"/"BUY"/"BUY_TO_COVER"），与 OrderSide.value 对齐，
    **不 import core.pending**，保持纯函数层零业务依赖。
    """
```

**注意**：`split_reversal` 返回字符串侧别（见 §6.3），调用方（engine / policy）负责映射为 `OrderSide`；模块层零业务依赖，避免 `futures_accounting → pending` 的无谓耦合。

### 6.4 单测先行（F 编号对齐 DESIGN §8.1）

`tests/test_p050_futures_accounting.py`：

| 用例 | 断言 |
|------|------|
| F1 开仓 | `margin = notional × ratio`；`cash` 扣减；`notional` 乘数正确 |
| F2 结算涨/跌 | `pnl` 闭式；`margin_delta`；`cash_after = cash + pnl − delta` |
| F3 平仓 | 保证金全释放；累计盈亏守恒 |
| F4 空头 | `q<0` 时 pnl/保证金符号正确 |
| F5 强平生成 | `cash<0` → 非空且按 |notional| 降序；`cash>=0` → 空 |
| F8 股票空头 | `NAV = C + q(P0−P)` |
| F10 越量 | 四向 raise |
| F11 反手 | 两笔、顺序、合计数量 |
| F9 开关逐位一致（归属 T3 §5.2） | 3 场景读数与改动前相同 |
| F13 成本接线（归属 T2 §4.2） | FUTURE 印花 0 / exchange_fee 生效；STOCK 三费不变 |

**验收**：仅新增测试文件，`pytest -q tests/test_p050_futures_accounting.py` 全绿且全量不回归。

**回退点**：删除新模块 + 新测试文件，零残留。

---

## 7. T5 `PositionTracker.settle`

### 7.1 签名

```python
def settle(
    self,
    date: pd.Timestamp,
    settlements: Mapping[str, float],
    specs: Mapping[str, ContractSpec],
    fallback_prices: Optional[Mapping[str, float]] = None,
    margin_model: Optional[MarginModel] = None,
) -> Optional[SettlementResult]:
```

**实现要点**
1. `if not specs: return None`（股票零开销）；
2. 遍历 `self.positions`，`asset_type != FUTURE` 跳过；
3. 结算价缺失 → 用 `fallback_prices[symbol]`（**引擎传当日收盘**；RI-1：tracker 无价格缓存——`update_market_values` L223-239 只写 `market_value`，`Position` 无 last_price 字段，原"`self._last_prices`"不存在）并置 `proxy_used=True`；
4. `result = compute_settlement(...)` → `self.cash, margin_total = apply_settlement(...)`；
5. 回写 `settle_base/avg_cost/mtm_pnl/market_value/margin_used`；
6. **不产生快照**（快照仍由 L556-557 的 `update_market_values` 生成）。

### 7.2 现金语义拆分

```python
def get_available_cash(self) -> float: return self.cash
def get_total_cash(self) -> float: return self.cash + sum(p.margin_used for p in ...)
def get_cash(self) -> float:
    """兼容别名：股票模式=总现金=可用；期货模式=可用（DESIGN D1）。"""
    return self.cash
```

`engine` 的 BUY 闸门（L955-968 / L1366-1377）改用 `_avail_cash()` 助手——`getattr(self.tracker, "get_available_cash", self.tracker.get_cash)`（RI-18→并入 RI 处置：注入式 tracker 可能没有新方法，与 `settle` 探测同式），股票读数不变。

**验收**：F1-F5 走 tracker 路径全绿；股票 `get_cash()` 对照 T0 读数一致。

**回退点**：`settle` 方法整块 + `get_available_cash/get_total_cash` 两个方法；`get_cash` 不改。

---

## 8. T6 引擎接线

### 8.1 setup：构建 specs

```python
# engine_v2.py setup() 末尾
self._contract_specs: dict[str, ContractSpec] = {}
for sym in (self.cfg.futures_symbols or []):
    info = self.dm.get_asset_info(sym)
    if info.asset_type != AssetType.FUTURE:
        raise ValueError(f"{sym} 声明为期货但 AssetInfo 非 FUTURE")
    for f in ("multiplier", "margin_ratio", "expiry_date"):
        if getattr(info, f, None) in (None, 0, ""):
            raise ValueError(f"{sym} 缺少 {f}")
    expiry = pd.Timestamp(info.expiry_date)
    roll_days = info.roll_days_before_expiry or 5
    last_holdable = expiry - pd.Timedelta(days=roll_days)
    if (last_holdable.year, last_holdable.month) == (expiry.year, expiry.month):
        raise ValueError(f"{sym} 的 roll 窗口落在交割月内，违反'不进入交割月'")
    self._contract_specs[sym] = ContractSpec(...)
self._has_futures = bool(self._contract_specs)
```

**交割月判定**：`expiry` 所在月即交割月 → 要求 `last_holdable = expiry − roll_days ≥ 交割月首日`；否则 setup 期 raise（D5）。

### 8.2 settle 插入（L543-544，queue 之后、trigger 之前）

```python
if self._has_futures and (settle := getattr(self.tracker, "settle", None)):
    close_today = self._exec_price(self.dm, "close").loc[today]
    self._last_settlement = settle(
        today, self._settlements_today(), self._contract_specs,
        fallback_prices=close_today.to_dict(),
    )
    avail = getattr(self.tracker, "get_available_cash", self.tracker.get_cash)()
    if avail < 0:
        self._pending_liquidations = liquidation_requests(...)
```

**插入锚点勘误（RI-11→并入 RI 处置）**：实际日序为 L534 退市 → L536-538 次日单执行 → L540-542 pending queue → **L543 插 settle** → L544-549 trigger → L551-553 再平衡 → L556-557 收盘。

**结算价解析**（D6）：`get_settlement_prices` 探测 → `settlement_file` → 当日收盘代理（warning 一次）。

### 8.3 强平注入与豁免（RD-1）

```python
# settle 之后 append（今日生成 → 次日 L536-538 开盘最先执行）
def _close_side(qty: float) -> OrderSide:
    return OrderSide.SELL if qty > 0 else OrderSide.BUY_TO_COVER

entries = [
    {"stock": r.symbol, "side": _close_side(r.quantity),
     "quantity": abs(r.quantity), "reason": "liquidation", "_kind": "liquidation"}
    for r in self._pending_liquidations
]
self._next_day_orders[:0] = entries   # RI-3：整体前插，保持 |notional| 降序
```

- 过期循环（L859-884）：`if item.get("_kind") == "liquidation": continue`；
- 执行失败（L1380-1383）：`_kind == "liquidation"` → `deferred_days += 1` 并保留，不丢弃；
- **D9 越量 raise 捕获仅限强平单**：`try: execute except ValueError: defer`（不得吞掉普通订单的越量错误）。

### 8.4 换月

```python
if self._has_futures:
    for ins in roll_orders(positions, self._contract_specs, today):
        self._next_day_orders.extend([_close_intent(ins), _open_intent(ins)])
```

两笔均带 `_kind="roll"`，与普通单同队列、先平后开。

**验收**：F5/F6/F7/F12 全绿；股票 golden 零 diff。

### 8.5 调仓估值乘数（RD-4）

`core/target_positions.py` `compute_portfolio_value`（L148-188，**实际签名 `(cash, current_positions: Mapping[str, int], prices, market_values=None)`——收 int 数量字典而非 Position 对象**；RI-7）→ 增两个可选参数：

```python
def compute_portfolio_value(
    cash: float,
    current_positions: Mapping[str, int],
    prices: pd.Series,
    market_values: Optional[Mapping[str, float]] = None,
    equity_symbols: Optional[Collection[str]] = None,   # 新增（Step 8 SC-6）
    allow_negative_stock: bool = False,                  # 新增（T3 开关）
) -> float:
    ...
    for stock_key, quantity in current_positions.items():
        qty = int(quantity)
        if qty <= 0 and not allow_negative_stock:        # L174 分支接开关
            continue
        if stock_key in (equity_symbols or ()):          # 期货：权益口径
            total += (market_values or {}).get(stock_key, 0.0)
            continue
        price = _resolve_price(prices, stock_key)
        if price is not None:
            total += qty * price                         # 股票路径逐位不变
            continue
        ...  # market_values 兜底不变
```

**Step 8 勘误（SC-6，推翻 Step 6 RD-4 的"乘数修复"方案）**：A3′ 下 `cash` 为**可用**口径，期货 NAV = 可用 + (margin + mtm)。若按 `qty×price×multiplier` 重算名义，会漏掉保证金占用（NAV 差 `margin_t`），与 `get_total_value` 不一致。正确口径：**期货走 `market_values`**（= margin+mtm，`settle` 每日刷新且日序先于调仓）；股票（含研究模式空头，`qty×price` 为负=负债）保持重算。调用方（engine `_execute_rebalance` L1181-1186，实测传 `tracker.get_cash()` + market_values dict）补传 `equity_symbols=self._contract_specs.keys()` 与 `allow_negative_stock=self.cfg.allows_short()`；缺省 None/False → 股票逐位不变。

### 8.6 权重与校验口径（RD-5）

```python
# tracker.get_position_weights L307-325
value = pos.notional_value if pos.asset_type == AssetType.FUTURE else pos.market_value
# L343 `position.quantity > 0` 门同步接 allow_short（Step 8 SC-5：否则空头行业敞口漏计）；
# L347 取值同一替换

# tracker.validate_positions L465-477（RI-8：现市值校验在 L472 `quantity>0` 门内
#   ——期货空头被整体跳过、期货多头按 qty×price 必误报）
for stock, pos in self._positions.items():
    if pos.asset_type == AssetType.FUTURE:
        expected = pos.margin_used + pos.mtm_pnl
        if abs(pos.market_value - expected) > 0.01:
            errors.append(f"{stock}期货权益不自洽: {pos.market_value} vs {expected}")
    elif stock in prices and pos.quantity > 0:      # L472 股票原门不动
        expected_market_value = pos.quantity * prices[stock]
        if abs(pos.market_value - expected_market_value) > 0.01:
            errors.append(...)                       # L473-477 原逻辑
```

**理由**：期货 `market_value = margin + mtm`（D1），用 `qty×price` 校验必然误报；权重用 `market_value` 会把名义敞口压成保证金占比（≈10%），使 overlay/sizing 失真。

**验收**：F1-F13 全绿；股票 `get_position_weights` 对照 T0 读数一致。

**回退点**：`engine_v2.py` 6 处均为新增块，可逐块注释回退（`_has_futures` 为 False 时全部短路）。

---

## 9. T7 不变量与 V3

### 9.1 `invariants.py`

```python
def check_margin_consistency(snapshot, specs) -> list[str]:
    """I6（RI-9：模块内 I5 已被 `check_v3_nav_identity` L254 docstring 占用）：
    margin_used == Σ |qty| × settle × m × ratio（误差 1e-6）。"""

def check_notional(snapshot, prices, specs) -> list[str]:
    """I7：notional_value == |qty| × price × m。"""
```

编号映射（Step 8 SC-3 勘误）：I6 == 研究 I-P050-3（保证金）、I7 == 研究 I-P050-10（名义/exposure）、I8 == 研究 I-P050-2（现金流）；研究 I-P050-1/4/5/6/7/8/9 分别由 I1 语义、C8、C9、B8、C10、B13、C5 承载。避免与模块既有 I1-I5 冲突。接入 `check_all`（**L336**，RI-9 勘误：原写 L253+ 实为 `check_v3_nav_identity`），仅当 `specs` 非空执行；I1 只改注释（语义已含 margin+mtm）。

I8 为单测级恒等式（`cash_t − cash_{t−1} = Σpnl − fee − Δmargin`；对应研究 I-P050-2），不入 `check_all`（缺逐日上下文）。

### 9.2 V3 拒绝

```python
# engine_v3_vector.py __init__（L222 后）
if cfg.get("allow_negative_stock_positions") or cfg.get("futures_symbols"):
    raise ValueError("V3 不支持期货/负持仓；请使用 V2")
```

### 9.3 版本

`core/__init__.py`：`__api_version__ = "3.2.0"`（minor：新增可选成员，无破坏）。

### 9.4 `risk_manager.py` 分母与诊断化（S7 补登）

```python
# risk_manager.py L161-188
notional = sum(p.notional_value for p in positions if p.asset_type == AssetType.FUTURE)
ratio = (margin_used / notional) if notional > 0 else 0.0   # 原 market_value
action = "diagnostic"                                       # 原 FORCE_CLOSE 分支删除
```

仅写日志/诊断字段，**不产生动作**（强平唯一判据为 C1）。默认不注入，生产路径零变化。

**验收**：`pytest -q tests/test_p050_engine_integration.py` 全绿；F12 raise。

**回退点**：invariants 新增函数可整块删；V3 校验 3 行可删；版本号单行回退。

---

## 10. T8 golden

### 10.1 目录与装载

沿用 `tests/golden/p047/` 子目录模式（装载器已支持），新增 `tests/golden/p050/`：

| 文件 | 场景 | 期数 | 手算要点 |
|------|------|------|----------|
| `tests/golden/p050/S1.json` | 期货多头逐日结算（1 手 IH@3000，m=300，r=0.1） | 4 | NAV `[1e6, 1e6, 1,015,000, 1,003,000]`，trades=1 |
| `tests/golden/p050/S2.json` | 期货空头（股票负持仓开关关闭） | 4 | NAV `[1e6, 1e6, 985,000, 997,000]`，trades=1 |
| `tests/golden/p050/S3.json` | 结算后 cash<0 → 次日强平（r=0.9，settle 3400） | 4 | NAV `[1e6, 880,000, 880,000, 880,000]`，强平后持仓 0，trades=2 |
| `tests/golden/p050/S4.json` | 到期前 roll（IH2406 → IH2409，同价） | 4 | NAV `[1e6, 1e6, 1e6, 1,003,000]`，新旧 notional 均 900,000，trades=3 |

**期望值全部闭式手算写进 README 注释或 `_golden_cases` 旁注**，禁止录制。断言面沿用 `_nav_block` + `_metrics_block_v2` + `trades.count`。

### 10.2 零重录验证

```bash
git diff --stat tests/golden/G*.json tests/golden/p047/*.json   # 必须为空
pytest -q -k golden                                             # 22 例全绿（18 既有 + 4 新增）
```

**回退点**：删除 `tests/golden/p050/` 与对应用例注册，既有 12 例不受影响。

---

## 11. T9 门禁与回写

```bash
pytest -q
pytest -q -k golden
mypy core filter tests
black --check core tests
git status --short
```

**必须项**
- 全量 passed 数 ≥ T0 读数 + 新增用例数；
- golden 既有 12 例字节不变，新增 4 例通过；
- mypy 0 error（文件数 +1）；
- black 不劣化（`--check` 通过）；
- `docs/PROGRESS.md` / `CHANGELOG.md` 按既有台账格式补 P-050 记录（**需用户裁决是否提交**）。

---

## 12. 低效排除表（Step 5 必填）

| 看似需要 | 为何不做 | 替代 |
|----------|----------|------|
| 改 `get_total_value` 公式 | 三账已闭合：股票 `mv=qP`、期货 `mv=margin+mtm` | 公式本体零改动 |
| `IDataManager` 增"枚举期货合约"方法 | 扩协议破坏所有注入实现 | `cfg.futures_symbols` 显式声明 |
| `PendingOrder` 加 `reason` / `order_type=STOP` 复用 | 污染通用队列语义，过期逻辑耦合 | 独立 `LiquidationRequest` + `_kind` 标记 |
| 新增 `ExecutionPriceType.SETTLEMENT` | 结算价是数据而非执行价格类型 | provider / file / close 三级 |
| 新增 `equity_value` 字段 | `market_value` 语义已定为"权益" | 保持字段名，改公式分支 |
| 内置 IH/IF/T 品种参数表 | 元数据驱动原则（D8） | `AssetInfo` / `ContractSpec` |
| 平今/平昨费用、按手最低佣金 | 研究 §5.6 未裁决 | P-056 单独批次 |
| 盘中强平（C3） | 无分钟级数据契约 | 次日开盘 + 顺延 |
| 分钟级结算价 | 同上 | 日线结算价 |
| 改 golden 断言面（加 cash/positions） | 会迫使 12 例重录 | 断言面不变，新增 `p050/` |
| 股票空头融资费 | D3 定为研究模式 | 后续批次 |
| `T0FuturesPolicy` 全面改造 | 本批只需接线，不重写 | 保持零调用点，Step 9 标注 |

---

## 13. 实施记录（Step 9 填写）

| 任务 | 状态 | 提交/快照 | pytest | golden | 备注 |
|------|------|-----------|--------|--------|------|
| T0 | ✅ 完成 | 工作区（未提交） | 987 | 18 | 基线读数复核（2026-11-20，`MPLBACKEND=Agg`） |
| T1 | ✅ 完成 | 工作区（未提交） | 1024 | 22 | `Position` 5 字段 / `Trade` 3 字段 / `AssetInfo` 2 字段 / `BacktestConfig` 4 字段 + `allows_short` |
| T2 | ✅ 完成 | 工作区（未提交） | 1024 | 22 | `asset_specs` 注入 + 乘数落 `amount` + 印花税恒 0（`ContractSpec.asset_type` 见 CHECKLIST §8 D-5） |
| T3 | ✅ 完成 | 工作区（未提交） | 1024 | 22 | 股票有符号市值 + 四向越量 raise + `SELL_SHORT`/`BUY_TO_COVER` 现金分支 |
| T4 | ✅ 完成 | 工作区（未提交） | 1024 | 22 | `core/futures_accounting.py`（4 frozen dataclass + Protocol + 4 纯函数） |
| T5 | ✅ 完成 | 工作区（未提交） | 1024 | 22 | `settle` + 三现金方法 + `update_market_values` 期货分支（快照不产生） |
| T6 | ✅ 完成 | 工作区（未提交） | 1024 | 22 | `_build_contract_specs` 校验 / 日序 settle / 强平顺延 / 换月 / `_avail_cash`；D7 细化见 §8 D-6；重复平仓作废见 D-7 |
| T7 | ✅ 完成 | 工作区（未提交） | 1024 | 22 | `check_margin_identity`/`check_notional_identity`（代码串 `P050-I6/I7`，§8 D-1）+ V3 双开关拒绝 + `risk_manager` 仅诊断 |
| T8 | ✅ 完成 | `tests/golden/p050/{S1,S2,S3,S4}.json`（未提交） | 1024 | 22 | 4 例闭式手算（非录制）：NAV `[1e6,1e6,1.015e6,1.003e6]` / `[1e6,1e6,0.985e6,0.997e6]` / `[1e6,0.88e6,0.88e6,0.88e6]` / `[1e6,1e6,1e6,1.003e6]` |
| T9 | ✅ 完成 | 工作区（未提交） | 1024 | 22 | 门禁：1024 passed / 22 golden / 1024 collect / mypy 112 files 0 issue / black 155 unchanged / `tests/golden` 仅 `?? p050/` |

**回退总原则**：T1-T3 为"字段 + 分支"，可独立 revert；T4-T5 为新模块/新方法，可整块删除；T6-T7 全部由 `_has_futures=False` 短路；T8 为新目录。任一步失败，回退至上一任务完成态，不回退整个批次。

---

## 14. 自检

- [x] 每个接口有签名 + 回退点（§3-§10）
- [x] 依赖序明确，可并行点已标注（T2∥T3、T7∥T8）
- [x] 每任务有独立验收命令与回退边界
- [x] 低效排除表非空（12 项）
- [x] 股票零变更由"字段默认值 + `_has_futures` 短路 + golden 零 diff"三重保证
- [x] RD-1..RD-5 全部落实到具体任务（RD-1→§8.3、RD-2→§9.2、RD-3→§8.1、RD-4→§8.5、RD-5→§8.6）
- [x] Step 6 异构 Review（GLM-5.3-Flash，2026-11-20）——**有条件通过**（RI-1..RI-9 全部处置，见 §15）
- [x] Step 7 CHECKLIST 落盘（[CHECKLIST_p050](CHECKLIST_p050_futures_short_accounting.md)，54 项，实测列零预填）；S7 补登 `risk_manager.py`（§9.4）
- [x] Step 8 一致性检查**通过**（SC-1..SC-6，见 CHECKLIST §7）——本文件已同步：§1.2 编号与 interfaces 补登、§6.4 F9/F13、§8.5 `equity_symbols` 口径勘误（SC-6）、§8.6 L343 门、§9.1 映射

---

## 15. Step 6 异构复审记录（复审方 GLM-5.3-Flash，2026-11-20）

**方式**：复审方独立读码验证全部行号锚点与签名（`tracker.py` L223-239 / L449-479、`target_positions.py` L148-188、`invariants.py` L88 / L113 / L170 / L216 / L254 / L281 / L305 / L336、`engine_v2.py` L528-563、`execution.py` L273-301、`tests/test_golden_baseline.py` L102 + p047 装载 L464-474），不信任作者转述。

**结论**：**有条件通过**。任务拆解 / 依赖序 / 回退点 / 低效排除表结构合格；RD-1..RD-5 全部落点。9 项发现（4 major + 5 minor）全部处置并回写正文；DESIGN 已同步（§3.2 settle 签名、§7 不变量编号）。

| ID | 级别 | 发现（幻觉抑制） | 处置 |
|----|------|------------------|------|
| RI-1 | **major** | §7.1 引用 `self._last_prices`（称由 `update_market_values` 缓存）——**该缓存不存在**（L223-239 只写 `market_value`，`Position` 无 last_price 字段） | `settle` 增 `fallback_prices` 参数，引擎传当日收盘；DESIGN §3.2 已同步 |
| RI-2 | minor | §6.1 导入缺 `runtime_checkable`（§6.2 使用）、`field` 未用 | 已改导入行 |
| RI-3 | minor | §8.3 逐条 `insert(0, ...)` 会**反转** \|notional\| 降序 | 改整体前插 `[:0] = entries` |
| RI-4 | minor | §5.2 SELL 守卫 `> self.quantity` 对负持仓碰巧成立但语义错 | 改 `> max(self.quantity, 0.0)` |
| RI-5 | minor | F9（开关关闭逐位一致，DESIGN §8.1）未分配到任何任务/文件 | 归入 §5.2 验收 + `test_p050_futures_accounting.py` |
| RI-6 | **major** | §4.1 留"实施期锁定"决策（乘数放 tracker 侧）——与 §4.2 成本自相矛盾：`_calculate_cost` 的 `amount` 若无乘数，期货佣金/交易所费错 1/m | 定案：`ExecutionSimulator` 增可选 `asset_specs`，乘数在 `execute_order` 落入 `amount` |
| RI-7 | **major** | §8.5 骨架按 `Position` 对象遍历——实际签名收 `Mapping[str, int]` 数量字典，`pos.multiplier` 无处取 | 改增 `multipliers` / `allow_negative_stock` 可选参数，调用方注入 |
| RI-8 | minor | §8.6 锚点 L473-476 不准：市值校验在 L472 `quantity>0` 门内（期货空头被跳过、多头被误报） | 锚点改 L465-477 + 分支结构重写，保留股票原门 |
| RI-9 | **major** | 不变量编号冲突：**I5 已被 `check_v3_nav_identity`（L254 docstring）占用**；`check_all` 实位于 **L336**（原写 L253+） | 新不变量改 I6/I7（== 研究 I-P050-5/6），现金恒等式改 I8；锚点勘误 |

**复核通过项**：golden 子目录装载模式（p047 先例：独立 GOLDEN_DIR + 根目录 glob 隔离断言）；日序锚点（L534 / L536-538 / L540-542 / L544-549 / L556-557）与 §8.2 插入位自洽；`pytest -k golden` 16 例口径（7+2+3+4）正确；T0 命令、低效排除表 12 项、回退总原则无幻觉。

**复审意见**：RI-1 / RI-7 属"骨架与真实签名不符"的典型幻觉，RI-9 属编号占用未查模块全集，RI-6 属悬置决策含成本矛盾——四者若带入实现会直接编译失败或静默错账，均已写死替代方案。无未决分歧，**可进入 Step 7（CHECKLIST）**。
