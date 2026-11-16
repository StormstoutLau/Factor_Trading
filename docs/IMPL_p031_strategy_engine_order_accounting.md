# IMPL：P-031 `StrategyEngine` 订单簿与估值时序

> **批次**: P-031 · **T1**（`agents/multi_strategy_engine.py` 单文件 + 新增账目测试）
> **上游**: [DESIGN_p031](DESIGN_p031_strategy_engine_order_accounting.md)（D1-D7 / I1-I8 / V1-V6 / §7 风险未决 / §8 回退点 / §11 当轮回写导读 / §12 Step 4 异构 Review pass）
> **状态**: **Step 5 实施规划**（2026-11-16，基线 HEAD `96bed8d`）
> **代码证据时点**: 实施前 HEAD `96bed8d`；§4 全部锚点为**实施前行号**（`agents/multi_strategy_engine.py`）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（代码） | `agents/multi_strategy_engine.py`（**唯一**） |
| 变更文件（测试/文档） | `tests/test_p031_strategy_engine_accounting.py`（新增）/ 本文件 / `docs/PROGRESS.md` / `CHANGELOG.md` |
| 零改动面 | `core/`（含 `target_positions.py` / `tracker.py` / `execution.py` / `pending.py`）/ `tests/golden/*.json` / `filter/` / `scripts/` / `cli.py` / `pyproject.toml` / `tests/test_p029_*.py` / `tests/test_p027_*.py` |
| 行为变更 | **四处语义修正**（R1/R2/R4/R3）+ 一处显式降级（中性空头腿）。无新增 `except` 分支，`except Exception` 合计恒 22 |
| 门禁口径 | `MPLBACKEND=Agg` + Python312：pytest **722 → 731**（+9 实例）；`tests/` .py **81 → 82**；black `--check core tests` **118 → 119**；mypy `core` **37 files 0 error**（`agents/` 不在门禁路径，不变）；golden G1-G7 零重录 |

**六条不可越界的设计前提**：

1. **`core/` 零改动**：`compute_portfolio_value` / `build_target_positions` / `PendingOrderQueue.cancel_orders` / `is_expired` 全部**只读复用**（I6 / D7）。
2. **修复必须落在被调函数内部**：`_execute_next_day_orders` / `_process_pending_orders` / `_execute_rebalance` 有两条调用路径（`_process_trading_day` 与 `MultiStrategyEngine` 自建循环 L735/L751/L867/L882），禁止在调用方打补丁（F-D3-P031-1 / D6）。
3. **双路径夹紧**：次日路径与队列路径**同形**插入（DESIGN D3 + F-S4-P031-1）；只修一条则默认配置（`enable_pending_orders=True`）R4 仍可达。
4. **双载体撤销**：`_next_day_orders` keep/drop + `pending_queue.cancel_orders`（DESIGN D4 + F-S4-P031-1）。
5. **nav 守卫先于 `build_target_positions`**：`ValueError` 在 `MultiStrategyEngine` 循环 L751/L882（无 try）会杀死整个回测（F-S4-P031-2）。
6. **中性不重归一化**：`long_weights * long_weight` 原样缩放（半仓多头 + 半仓现金），双重披露（init warning + `additional_info`）——F-S4-P031-4 裁决 (a)。

---

## 2. 任务拆解

| ID | 批次 | 任务 | 对应 | 产出 |
|----|------|------|------|------|
| **B1** | 代码 | D2 中性空头腿禁用：删 `short_optimizer` 构建与调用 + `neutral_short_leg_skipped` 计数 + `__init__` warning + `_generate_results` 的 `additional_info` | D2 | 1 文件，**净 −8 / +10 行** |
| **B1t** | 测试 | V5（中性无 SELL 成交 + 计数 + 结果标记） | V5 / I7 | +1 实例 |
| **B2** | 代码 | D1 估值与目标持仓：`_generate_orders` 改 `compute_portfolio_value` + `build_target_positions` + nav 守卫；`_generate_rebalance_orders` 改收 `TargetPosition` 并先卖后买 | D1 | 1 文件，**净 +12 / −28 行** |
| **B2t** | 测试 | V1（退出单）/ V2（NAV 时序零换手）/ V2b（nav 守卫） | V1 / V2 / I1 / I3 | +3 实例 |
| **B3** | 代码 | D3 双路径卖量夹紧：新增 `_clamp_sell_quantity`；次日路径与队列路径同形插入 | D3 | 1 文件，**净 +18 行** |
| **B3t** | 测试 | V3（参数化次日/队列两路径：1 笔成交 + 2 次 blocked + 现金守恒） | V3 / I2 | +2 实例 |
| **B4** | 代码 | D4 双载体撤销 + 次日路径过期过滤 | D4 | 1 文件，**净 +22 行** |
| **B4t** | 测试 | V4（参数化 cancel/expire）+ V6（正常路径 6 键全 0） | V4 / V6 | +3 实例 |
| **B5** | 文档 | 全量门禁 + 本文件 §11 实测回填 + `PROGRESS` §3.36.5 + `CHANGELOG` | — | docs |

**计数口径**：新增计数键 **6** 个（D6 口径）；测试 **9 实例** = V1 1 + V2 1 + V2b 1 + V3 2 + V4 2 + V5 1 + V6 1 → `722 + 9 = 731`。

---

## 3. 实施顺序与依赖

```text
B1（中性禁用）──→ B1t（V5 红→绿）
B2（估值/目标持仓）─→ B2t（V1/V2/V2b 红→绿）
B3（夹紧）────→ B3t（V3 红→绿）
B4（撤销/过期）──→ B4t（V4/V6 红→绿）
B1t+B2t+B3t+B4t → B5（全量门禁 + 文档回填）
```

- **B1 必须先于 B2**（DESIGN §8）：B2 落地后 `build_target_positions` 拒绝负权重，`direction="both"` 首日即抛 `ValueError`——而 `MultiStrategyEngine` 循环 L751/L882 无 try，会**杀死整个多策略回测**（Step 4 E1-2 实证）。
- **B3 / B4 相互独立**，可并行；但同属执行侧，建议按 B3 → B4 顺序落地以便 V3/V4 共享夹具。
- **每批红态先跑**（新增用例必须失败）、补实现后再跑（绿态），红态读数记入本文件 §11（F-S6 纪律）。

---

## 4. 精确变更规格

> 锚点为实施前 HEAD `96bed8d`；净行数以 `git diff --numstat` 为准（估算偏差登记 §9 F-I-P031-6）。

### 4.1 `__init__`（L69-113）——D2 warning

在 `self._failure_counts: dict[str, int] = {}`（L111）之后追加：

```python
        if strategy_config.direction == "both":
            logger.warning(
                f"[{strategy_config.name}] direction='both' 的空头腿不支持（账目模型无负持仓结算），"
                "本次回测仅执行多头腿（半仓多头 + 半仓现金），结果标记 neutral_short_leg=unsupported"
            )
```

**约束**：只打一次（构造期），不改签名、不抛错、不影响 long/short 腿。

### 4.2 `_execute_rebalance`（L201-226）——D4 落点 1（双载体撤销）

在「日期不在信号索引」早退（L203-204）之后、`daily_signal`（L207）之前插入：

```python
        # P-031 D4：再平衡刷新订单簿（信号域内在途单撤销，域外保留）
        domain = set(self._composite_signal.columns)
        if self._next_day_orders:
            keep: list[dict] = []
            dropped = 0
            for item in self._next_day_orders:
                if item["order"].stock in domain:
                    dropped += 1
                else:
                    keep.append(item)
            self._next_day_orders = keep
            if dropped:
                self._record_failure("next_day_orders_cancelled")
        if self.pending_queue:
            for stock in domain:
                self.pending_queue.cancel_orders(stock, date)
```

**口径说明**：

- 两载体在 `StrategyEngine` 中**互斥**（`enable_pending_orders=True` 时订单只入队列，`_next_day_orders` 恒空；`False` 时 `pending_queue is None`）——同时书写是幂等无害，且比 V2 的 `elif`（L912-917）更严格对齐 DESIGN D4（F-I-P031-5）。
- `next_day_orders_cancelled` 计「发生次数」（每次再平衡至多 +1），非单数订单数（DESIGN D4 原文）。
- queue 载体撤销**不新增计数键**：`cancel_orders` 内置 `logger.info` 事件（core 既有行为），且键名 `next_day_orders_*` 不覆盖队列语义（O-S4-P031-1 语义混载观察的边界，本批不扩）。

### 4.3 `_execute_neutral_rebalance`（L254-310）——D2 落点

**删除**（L271-279）`short_optimizer` 构建；**替换**（L292-302）：

```python
            long_weights = long_optimizer.optimize(tradable_stocks, returns_data)

            # P-031 D2：空头腿显式禁用——账目模型不支持可结算空头（N1 幻影现金）
            self._record_failure("neutral_short_leg_skipped")
            target_weights = long_weights * self.strategy_cfg.long_weight
```

**保留**：`try/except Exception` 包裹结构（`neutral_optimize` 键与 P-027 测试契约不变）；`long_optimizer` 仍在 try 内调用 → optimize 抛错时**不会**误计 `neutral_short_leg_skipped`（test_p027 断言 `stats == {"neutral_optimize": 1}` 精确相等）。

**资金部署**：`target_weights` 权重和 ≈ `long_weight`（默认 0.5），余额留现金；**不重归一化**（F-S4-P031-4 裁决 (a)）。

### 4.4 `_generate_orders`（L312-354）——D1 估值与目标持仓

整函数替换为：

```python
    def _generate_orders(self, date: pd.Timestamp, date_index: int, target_weights: pd.Series):
        """生成交易订单（价格重算 NAV + 目标持仓并集）"""
        # 1. 调仓日收盘价（失败 → 统一计量后跳过本次调仓）
        try:
            prices = self.dm.get_adj_price("close", self.base_cfg.adjustment_type).loc[date]
        except (KeyError, IndexError):
            self._record_failure("orders_missing_price")
            return

        # 2. 价格重算 NAV（tracker.get_total_value 在开盘成交后、日终盯市前不可信）
        positions = self.tracker.get_all_positions()
        current = {
            stock: int(position.quantity)
            for stock, position in positions.items()
            if int(position.quantity) > 0
        }
        nav = compute_portfolio_value(
            self.tracker.get_cash(),
            current,
            prices,
            {stock: position.market_value for stock, position in positions.items()},
        )
        if not np.isfinite(nav) or nav <= 0:
            self._record_failure("rebalance_nav_invalid")
            return

        # 3. 目标持仓（并集含调出标的的清仓项）
        targets = build_target_positions(
            target_weights,
            current,
            prices,
            nav,
            round_lot=self.base_cfg.optimizer.round_lot,
        )
        self._generate_rebalance_orders(date, targets)
```

**注记**：

- `orders_missing_price` 语义由「逐股 KeyError/IndexError」变为「日期切片失败」（F-S4-P031-3）——P-029 V4（`_MissingPriceFrame`，`.loc` 必抛 `KeyError`）在新入口仍命中，Step 9 实证。
- 守卫用 `np.isfinite`（`numpy` 已导入，不新增 `math` 导入——F-I-P031-3）。

### 4.5 `_generate_rebalance_orders`（L356-378）——D1 落点

签名由 `dict` 改为 `dict[str, TargetPosition]`，实现改为先卖后买（与 V2 L1063-1079 同形）：

```python
    def _generate_rebalance_orders(self, date: pd.Timestamp, targets: dict[str, TargetPosition]):
        """生成再平衡订单（先卖出含清仓与减仓，再买入）"""
        orders = []
        for target in targets.values():
            trade_qty = target.target_quantity - target.current_quantity
            if trade_qty < 0:
                orders.append(create_pending_order(target.stock, OrderSide.SELL, -trade_qty, date))
        for target in targets.values():
            trade_qty = target.target_quantity - target.current_quantity
            if trade_qty > 0:
                orders.append(create_pending_order(target.stock, OrderSide.BUY, trade_qty, date))

        for order in orders:
            if self.pending_queue:
                self.pending_queue.add_order(order)
            else:
                self._execute_order_next_open(order, date)
```

**导入新增**（L29-38 区）：`from core.target_positions import TargetPosition, build_target_positions, compute_portfolio_value`（插在 L37 `core.tracker` 之后）；`PendingOrder` 追加到 L34 `core.pending` 导入行（仅类型注解）。

### 4.6 新增 `_clamp_sell_quantity`（D3 公共载体）

置于 `_execute_next_day_orders` 之前（与 V2 L671-688 同名同义）：

```python
    def _clamp_sell_quantity(self, order: PendingOrder) -> int:
        """卖出数量按可卖持仓夹紧（P-031 D3）；BUY 原样返回。"""
        if order.side != OrderSide.SELL:
            return int(order.quantity)
        position = self.tracker.get_position(order.stock)
        available = max(int(position.quantity), 0) if position is not None else 0
        if available <= 0:
            return 0
        return min(int(order.quantity), available)
```

### 4.7 `_execute_next_day_orders`（L384-440）——D3 + D4 落点

三处插入：

| # | 位置 | 代码 |
|---|------|------|
| ① 过期过滤 | 开盘价 try/except **之后**、`buyable_mask` 之前 | 见下 |
| ② SELL 夹紧 | 循环内 `execute_order` 之前 | 见下 |
| ③ 执行调用 | 数量由 `order.quantity` → `qty` | `execute_order(order.stock, order.side, qty, date, open_price)` |

```python
        # ① P-031 D4：过期过滤（含半衰期，与队列 mark_expired 同语义）
        max_buy = self.base_cfg.max_pending_days_buy
        max_sell = self.base_cfg.max_pending_days_sell
        active = []
        expired = 0
        for order_info in self._next_day_orders:
            order = order_info["order"]
            max_days = max_buy if order.side == OrderSide.BUY else max_sell
            if order.is_expired(date, max_days):
                expired += 1
                continue
            active.append(order_info)
        self._next_day_orders = active
        if expired:
            self._record_failure("next_day_orders_expired")
```

```python
            # ② P-031 D3：卖出数量按可卖持仓夹紧
            qty = self._clamp_sell_quantity(order)
            if qty <= 0:
                self._record_failure("oversell_blocked")
                continue
            if qty < order.quantity:
                self._record_failure("oversell_trimmed")

            success, trade = self.executor.execute_order(
                order.stock, order.side, qty, date, open_price
            )
```

**放置裁决（F-I-P031-1）**：① 放在开盘价切片**之后**而非 DESIGN §4.2 的「空队列早退之后」——P-029 V5 fixture 用 `object()` 占位订单（`_next_day_orders = [{"order": object(), ...}]`），置于切片前会在 `.side` / `.is_expired` 上 `AttributeError`；置于切片后则该用例在价格 KeyError 处早退，**既有回归面零改动**。语义代价：仅在「整日无开盘价」的退化日推迟一天过期，有界且不可观测（恢复正常价日即过期）。

### 4.8 `_process_pending_orders`（L442-483）——D3 队列侧（默认主路径）

在 `execute_pending_order` 之前插入夹紧，并改用 `execute_order(..., qty, ...)`（与 V2 L815 同形）：

```python
            # P-031 D3：卖出数量按可卖持仓夹紧（默认主路径，Q1 实证同机制）
            qty = self._clamp_sell_quantity(order)
            if qty <= 0:
                self._record_failure("oversell_blocked")
                self.pending_queue.cancel_order(order, date)
                continue
            if qty < order.quantity:
                self._record_failure("oversell_trimmed")

            success, trade = self.executor.execute_order(
                order.stock, order.side, qty, date, open_price, close_price
            )
```

**裁决（F-I-P031-2）**：队列路径不复用 `execute_pending_order`（其内部固定取 `order.quantity`，无法夹紧）；改直调 `execute_order` 与 V2 L815 完全同形。`mark_executed(order, ...)` 仍对**原订单对象**调用 → 队列簿记无孤儿；被夹紧订单的 `quantity` **不就地改写**，`filled_qty` 语义与 V2 一致（V2 同期口径，登记 §9 F-I-P031-2）。

### 4.9 `_generate_results`（L485-502）——D2 落点 3

返回字典追加：

```python
            "additional_info": {
                "neutral_short_leg": (
                    "unsupported" if self.strategy_cfg.direction == "both" else "not_applicable"
                )
            },
```

写在此处而非 `run()`：`MultiStrategyEngine` 两条循环（L786 / L928）直接调用 `_generate_results()`。

---

## 5. 测试规格（`tests/test_p031_strategy_engine_accounting.py`）

| ID | 用例 | 构造 | 断言 |
|----|------|------|------|
| V1 | 退出单（R2） | 持仓 A=1000；`target_weights={"B": 0.5}`；`enable_pending_orders=False` | `_next_day_orders` 含 `SELL A 1000`；次日路径执行后 A=0、B>0 |
| V2 | NAV 时序（R1） | 1 股常量价 10、`daily`、恒定 `{"A": 1.0}`、10 个交易日；**成本零化**（`CostConfig(commission_rate=0, commission_min=0, stamp_tax_rate=0, slippage_pct=0)`） | 成交 **恰 1 笔**（旧实现 9 笔）；每日 `cash + Σqty×price == 初始资金`（NAV 恒定） |
| V2b | nav 守卫（F-S4-P031-2） | `tracker._cash = 0`、无持仓 → nav=0 | **不抛异常**；`rebalance_nav_invalid == 1`；零订单 |
| V3 | 超卖夹紧（R4，参数化 2） | 持仓 A=100；3×`SELL A 100`；`next_day` / `queue` 两路径；**成本零化** | 成交 **1 笔 100 股**；`oversell_blocked == 2`；`cash` 恰 **+1,000**（非 +3,000） |
| V4 | 在途单（R3，参数化 2） | ① 撤销：两次 `_execute_rebalance` 间残留 1 张单；② 过期：订单创建日距当前 ≥ 6 自然日 | ① 撤销后 `_next_day_orders` 不含该股 + `next_day_orders_cancelled > 0`；② `next_day_orders_expired > 0` 且订单不再执行 |
| V5 | 中性（D2） | `direction="both"`，`long_weight=0.5` | 无 SELL 成交；`neutral_short_leg_skipped > 0`；`additional_info.neutral_short_leg == "unsupported"`；`__init__` 有 1 条 WARNING |
| V6 | 正常路径（回归） | 常规多头两股调仓，全链路 `run()` | 6 个新计数键全 0；`orders_missing_price` / `next_day_open_price` 零误报 |

**红态纪律**：B1t/B2t/B3t/B4t 逐批先红后绿；V6 在红态即通过属预期（回归保护），须在 §11 显式标注。

---

## 6. fixture 表

| ID | 名称 | 内容 | 说明 |
|----|------|------|------|
| F1 | `_P031DM` | `trade_dates`（bdate_range）、`stock_codes`、`n_stocks`、`returns`、`get_adj_price(field, adj)` 返回常量价 DataFrame | 独立复制（不改 `test_p029`/`test_p027` fixture） |
| F2 | `_P031Universe` | `tradable` / `buyable` / `sellable` 三个全 True DataFrame | `_process_pending_orders` 无 `hasattr` 保护，三面必须齐备 |
| F3 | `_make_engine(direction, enable_pending, zero_cost?)` | 组装 `StrategyConfig` + `BacktestConfig(enable_pending_orders=…, rebalance=RebalanceConfig(frequency="daily"), optimizer=OptimizerConfig(method="equal_weight", round_lot=True), cost=CostConfig(...))` | 优化器用 `equal_weight`（不依赖协方差）；V2/V3 用零成本（F-I-P031-7） |
| F4 | `_seed_position(engine, stock, qty, price)` | 直接构造 `Trade` → `tracker.execute_trade` + `update_market_values` | 避免依赖成交路径 |
| F5 | `_price_frame(mapping, dates)` | 生成可按 `.loc[date]` 切片、`.get(stock)` 取值的价格行 | V1-V5 |
| F6 | `_days(n)` | 自然日间隔的 `DatetimeIndex`（用于 V4 过期：≥ 6 自然日） | `is_expired` 用自然日 |

**约束**：F1-F6 全部落在新文件内，**不修改** `tests/test_p029_silent_exception_governance.py` / `tests/test_p027_silent_exception_governance.py` / `tests/test_rebalance_exits.py`。

---

## 7. 低效排除

| # | 候选 | 排除理由 |
|---|------|----------|
| 1 | 为 D2 新建「中性降级」配置开关 | 配置面扩张超出 T1；默认行为 + 双重披露已足 |
| 2 | 把 tracker 现金守卫一并修掉（O-P031-1） | `core/` 零改动是硬约束；V2 夹紧后 golden 不可达（D3 理由精化） |
| 3 | 队列撤销新增计数键 | D6 已定 6 键；扩键属 Step 4 观察（O-S4-P031-1 语义混载）范畴 |
| 4 | `_next_day_orders` 终态清仓（F-D3-P031-2） | 未成交即回测结束，保持既有语义 |
| 5 | 用 `math.isfinite` 替代 `np.isfinite` | 新增导入无收益（F-I-P031-3） |
| 6 | 重归一化中性权重至满仓 | F-S4-P031-4 裁决 (a) 明确拒绝（静默放大风险敞口） |
| 7 | 修改 P-029 V5 fixture 以适配过期顺序 | 回归面零改动优先；改用「切片后过期」等价方案（F-I-P031-1） |

---

## 8. 接口签名与回退点

| 函数 | 签名变化 | 回退点（单函数可回退） |
|------|----------|------------------------|
| `StrategyEngine.__init__` | **无**（仅加 warning） | B1 删除 warning 块 |
| `_execute_rebalance` | 无 | B4 删除撤销块 |
| `_execute_neutral_rebalance` | 无 | B1 恢复 `short_optimizer` + 合并循环 |
| `_generate_orders` | 无（内部全换） | B2 恢复旧函数体 |
| `_generate_rebalance_orders` | `dict` → `dict[str, TargetPosition]` | B2 与 `_generate_orders` 同批回退 |
| `_clamp_sell_quantity` | **新增私有方法** | B3 删除方法与两处调用 |
| `_execute_next_day_orders` | 无（三处内插） | B3/B4 按块回退（夹紧块 / 过期块独立） |
| `_process_pending_orders` | 无 | B3 恢复 `execute_pending_order` |
| `_generate_results` | 返回字典 +1 键 | B1 删除该键 |

**A8 口径**：`_clamp_sell_quantity` 为私有新增（非公开 API），I5「既有公开签名零变更」成立。

---

## 9. 实施期裁决与发现

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-I-P031-1 | P3 | DESIGN §4.2 要求过期过滤在开盘价切片**之前**；P-029 V5 fixture 用 `object()` 占位订单，前置会 `AttributeError` | 改置于切片**之后**（回归面零改动）；代价为退化日推迟一天过期，有界 |
| F-I-P031-2 | P3 | 队列路径 `execute_pending_order` 固定取 `order.quantity`，无法夹紧 | 改直调 `execute_order(..., qty, ...)`（与 V2 L815 同形）；`order.quantity` 不改写，`filled_qty` 与 V2 同期口径 |
| F-I-P031-3 | 观察 | nav 守卫用 `np.isfinite` 而非 `math.isfinite` | 避免新增导入；语义等价 |
| F-I-P031-4 | 观察 | `_generate_rebalance_orders` 旧入参为临时 dict，B2 后改为 `TargetPosition` | 与 V2 同名同义，且旧临时结构无第二消费者（grep 实证） |
| F-I-P031-5 | 观察 | DESIGN 要求双载体均撤销，V2 为 `elif` 二选一 | 按 DESIGN 实现（两载体在 agents 中互斥，幂等无害） |
| F-I-P031-6 | 观察 | §2 净行数为估算 | 以 `git diff --numstat` 实测为准，B5 回填 |
| F-I-P031-7 | P3 | DESIGN V2 期望「成交 1 笔」在**默认成本**下不可达：0.985 缓冲 + 佣金/滑点使稳态目标略低于持仓，每日按整手往返微调（约 9 笔小额，非旧实现的清仓-重建） | V2/V3 改用**零成本配置**隔离估值时序与被费用摩擦；旧实现（NAV 漏计当日成交）在零成本下仍为 9 笔清仓-重建，判别力保留。DESIGN V2 数字口径由本项修正 |

**覆盖补充**：DESIGN V1-V6 未单列 nav≤0 分支的可验证出口（F-S4-P031-2 的守卫），IMPL 增 **V2b**（见 §5）。

---

## 10. 下一 Step 复核重点（Step 6 实施 Review）

1. **双路径一致性**：`_execute_next_day_orders` 与 `_process_pending_orders` 的夹紧逻辑是否**逐字同形**（键、顺序、cancel 语义），是否存在只修一条的漏点；
2. **撤销时序**：`_execute_rebalance` 中撤销是否确在信号索引早退之后、tradable 计算之前——错位会撤销当日新单；
3. **frozenset 与性能**：`domain = set(self._composite_signal.columns)` 每再平衡全量遍历是否引入可观测开销（对照低效排除表）；
4. **中性计数位置**：`neutral_short_leg_skipped` 必须在 `optimize` **成功之后**——前置会污染 test_p027 精确断言；
5. **nav 守卫分支可达性**：`np.isfinite(nav)` 对 `nan`（`nan > 0` 为 False）与 `inf`（`inf > 0` 为 True）是否均被拦截；
6. **既有回归面**：P-029 V4/V5 与新 `orders_missing_price` / `next_day_open_price` 入口的对应关系是否实证（非推断）。

---

## 11. 待 Step 9 回填

| 项 | 状态 |
|----|------|
| 各批红态读数 | `[待 Step 9]` |
| 各批绿态读数 | `[待 Step 9]` |
| 门禁终态（pytest / mypy / black / golden） | `[待 Step 9]` |
| 净行数实测（`git diff --numstat`） | `[待 Step 9]` |
| P-029 V4/V5 回归面实证 | `[待 Step 9]` |

---

## 12. Step 5 自检

| # | 检查项 | 结果 |
|---|--------|------|
| S1 | DESIGN D1-D7 全落点 | D1 §4.4-4.5 / D2 §4.1+4.3+4.9 / D3 §4.6-4.8 / D4 §4.2+4.7 / D5 无代码（§7 排除 #2）/ D6 6 键全覆盖 / D7 §1 零改动面 —— **7/7** |
| S2 | I1-I8 → 验证出口 | I1→V1 / I2→V3 / I3→V2 / I4→V4 / I5→§8 A8 / I6→§1 / I7→V5 / I8→§1 门禁 —— **8/8** |
| S3 | 红态可观测 | V1/V2/V2b（B2 前）、V3（B3 前）、V4（B4 前）、V5（B1 前）均可断言失败；V6 红态即绿（回归保护，须标注） |
| S4 | 锚点实查 | 9 个函数起止行号与 HEAD `96bed8d` 逐项核对命中；import 区 L29-38 实查 |
| S5 | 既有回归面 | 仅 `test_p027` / `test_p029` 实例化 `StrategyEngine`（均 `direction="long"`、不跑全链路）；`MultiStrategyEngine` 无测试实例化 —— 行为变更不触及既有断言；`_MissingPriceFrame`（`.loc` 抛 `KeyError`）在新入口仍命中 |
| S6 | 门禁口径 | 731 = 722 + 9；测试文件 82；black 119；mypy `core` 37 files 0（`agents/` 不在门禁路径） |
| S7 | 签名可实现性 | `build_target_positions` / `compute_portfolio_value` / `cancel_orders` / `is_expired` / `execute_order(..., qty, ...)` 参数逐项核对（core 只读） |
| S8 | 零新增 `except Exception` | D1 新增 `except (KeyError, IndexError)`；D2 保留原 try/except —— 合计恒 22 |
