# IMPL：P-033 待执行订单价格有效性（守卫单点 + VWAP 覆盖）

> **批次**: P-033 · **T1**（`core/execution.py` + `core/engine_v2.py` + `agents/multi_strategy_engine.py`）
> **上游**: [DESIGN_p033](DESIGN_p033_pending_order_price_validation.md)（D1-D6 / I1-I7 / V1-V8 / §12 Step 4 异构 Review pass，2 P3 当轮回写）
> **状态**: **Step 5 实施规划**（2026-11-16，基线 HEAD `013c4d3`）
> **代码证据时点**: 实施前 HEAD `013c4d3`；§4 全部锚点为**实施前行号**

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（代码） | `core/execution.py` / `core/engine_v2.py` / `agents/multi_strategy_engine.py` |
| 变更文件（测试/文档） | `tests/test_p033_order_price_validation.py`（新增）/ 本文件 / `docs/PROGRESS.md` / `CHANGELOG.md` |
| 零改动面 | `core/tracker.py` / `core/pending.py` / `core/interfaces.py` / `core/target_positions.py` / `tests/golden/*.json` / `filter/` / `scripts/` / `cli.py` / `pyproject.toml` / `tests/test_p029_*.py` / `tests/test_p031_*.py` |
| 行为变更 | **1 处语义修正**：无效价（`None` / `NaN` / `±inf` / `≤0`）由「静默成交并污染账目」改为「拒绝 + 计量 + 订单保留重试」。合法价路径零变化 |
| 门禁口径 | `MPLBACKEND=Agg` + Python312：pytest **731 → 748**（+17 实例）；`tests/` .py **82 → 83**；black `--check core tests` **119 → 120**；mypy `core` **37 files 0**（不变）；golden G1-G7 **13 零重录** |

**六条不可越界的设计前提**：

1. **守卫在解析后**：作用于 `_get_execution_price` 的返回值，覆盖 OPEN / CLOSE / VWAP / CUSTOM / 未知回退五分支（Step 4 C1/C2 实锤）。
2. **单一判定来源**：`is_valid_price` 为模块级函数，executor 与两引擎共用；禁止各处自写 `pd.isna` 组合。
3. **双层不合并**：executor 保安全（6 调用点 + 委托链 + 未来调用方）、引擎保可归因（`failure_counts` / `skipped_price`）。
4. **合法价逐字不变**：守卫条件之外的路径零改动；golden 13 条零重录是硬门禁。
5. **零新增 `except`**：守卫不进异常漏斗，`except Exception` 合计恒 22。
6. **次日/强平路径不重构**：三处既有 inline 判定保留（D3），仅作为双保险的上游。

---

## 2. 任务拆解

| ID | 批次 | 任务 | 对应 | 产出 |
|----|------|------|------|------|
| **B1** | 代码 | `core/execution.py`：新增 `is_valid_price`（`ExecutionSimulator` 类前 L152/153）+ `execute_order` 解析价守卫（L292 之后）+ docstring 契约句 | D1 | 1 文件 **+13/−1**（估） |
| **B1t** | 测试 | V1（守卫矩阵 6）+ V7（VWAP NaN） | V1 / V7 / I1 | +7 实例 |
| **B2** | 代码 | `agents/multi_strategy_engine.py`：导入 `is_valid_price` + queue 前置过滤（L509 后 / L511 前）+ `pending_invalid_price` 计数 | D2 | 1 文件 **+4/−1** |
| **B2t** | 测试 | V2（NaN/0）+ V3（负价）+ V4（SELL 持仓保留）+ V5（bounded）+ V8a（agents 正常路径） | V2-V5 / V8 | +7 实例 |
| **B3** | 代码 | `core/engine_v2.py`：导入 `is_valid_price` + queue 前置过滤（L808 后 / L810 前，复用 `skipped_price`） | D2 | 1 文件 **+4/−1** |
| **B3t** | 测试 | V6（V2 NaN/0，caplog 断言）+ V8b（V2 正常路径） | V6 / V8 | +3 实例 |
| **B4** | 文档 | 全量门禁 + 本文件 §11 实测回填 + `PROGRESS` §3.38.4 + `CHANGELOG` | — | docs |

**计数口径**：测试 **17 实例** = V1 6 + V2 2 + V3 2 + V4 1 + V5 1 + V6 2 + V7 1 + V8 2 → `731 + 17 = 748`。

---

## 3. 实施顺序与依赖

```text
B1（is_valid_price + 守卫）──→ B1t（V1/V7 红→绿）
                              ├──→ B2（agents 过滤）──→ B2t（V2-V5/V8a 红→绿）
                              └──→ B3（V2 过滤）  ──→ B3t（V6/V8b 红→绿）
B1t+B2t+B3t ──→ B4（全量门禁 + 文档）
```

- **B1 必须最先**：B2/B3 的 `from core.execution import is_valid_price` 依赖 B1。
- **B2 / B3 相互独立**，可并行；建议 B2 → B3（V6 的 caplog 断言依赖 V2 路径，与 B3 同批）。
- **每批红态先跑**：B1t 红态 = 当前 `execute_order` 对 NaN/0 成交（V1 全 6 例失败）；B2t 红态 = agents queue 仍成交且无新键；B3t 红态 = V2 queue 仍成交且无「缺少价格数据」日志。

---

## 4. 精确变更规格

> 锚点为实施前 HEAD `013c4d3`；净行数以 `git diff --numstat` 为准（B4 回填）。

### 4.1 `core/execution.py` —— 新增 `is_valid_price`

**位置**：`TradeLog` 类结尾（L150）与 `ExecutionSimulator` 类定义（L153）之间（L151 空行后）。

```python
def is_valid_price(price: Optional[float]) -> bool:
    """价格是否可成交：有限且为正。

    None / NaN / ±inf / <=0 均视为无效（P-033 D1 单一判定口径，
    供执行入口与两引擎 queue 路径共用）。
    """
    if price is None:
        return False
    return bool(np.isfinite(price) and price > 0)
```

**约束**：`np` 已导入（L16）；纯函数、无日志、无异常；不加入 `interfaces.py` 协议（模块级工具函数）。

### 4.2 `core/execution.py` —— `execute_order` 解析价守卫

**位置**：L292-294 `execution_price = self._get_execution_price(...)` **之后**、L296 收盘价差异告警**之前**。

```python
            # P-033 D1：执行价格有效性守卫（None / NaN / ±inf / <=0 → 不成交、不入账）
            if not is_valid_price(execution_price):
                logger.warning(
                    f"{stock}在{date}执行价格无效: {execution_price!r}，"
                    "订单未成交（P-033 价格守卫）"
                )
                return False, None
```

**docstring 增补**（L274-289 `Returns:` 段后追加一行）：

```
            若解析后的执行价格为 None / NaN / ±inf / <=0，返回 (False, None)，不写入 trade_log。
```

**理由**：五分支（OPEN / CLOSE / VWAP / CUSTOM / 未知回退）的解析价在此汇聚；守卫在此一处即覆盖全部，含 Step 4 C1（CLOSE NaN）/ C2（CUSTOM inf）/ Step 2 B1（VWAP NaN）。

### 4.3 `agents/multi_strategy_engine.py` —— queue 前置过滤

| # | 位置 | 变更 |
|---|------|------|
| ① | L32 | `from core.execution import ExecutionSimulator` → `from core.execution import ExecutionSimulator, is_valid_price` |
| ② | `_process_pending_orders` L509（`close_price` 赋值）之后、L511 夹紧注释之前 | 插入 3 行（见下） |

```python
            # P-033 D2：开盘价有效性过滤（与 next-day 路径 L451 同口径）
            if not is_valid_price(open_price):
                self._record_failure("pending_invalid_price")
                continue
```

**口径**：订单保持 `PENDING`（不 `cancel_order`、不 `mark_executed`），由 `mark_expired`（L528）在半衰期内自然出队——与 next-day 路径 `failed_orders` 保留重试语义一致（DESIGN D5）。

### 4.4 `core/engine_v2.py` —— queue 前置过滤

| # | 位置 | 变更 |
|---|------|------|
| ① | L23 | `from core.execution import ExecutionSimulator` → `from core.execution import ExecutionSimulator, is_valid_price` |
| ② | `_process_pending_orders` L808（`close_price` 多行赋值结束）之后、L810 夹紧告警之前 | 插入 3 行（见下） |

```python
            # P-033 D2：开盘价有效性过滤（与 next-day 路径 L1140 同口径）
            if not is_valid_price(open_price):
                skipped_price.append(order.stock)
                continue
```

**口径**：复用既有 `skipped_price` 局部名单（L780 定义），由 L836-839 汇总输出 `跳过N个缺少价格数据订单: ...`——零新增键（Step 2 裁决 #3）。

### 4.5 不改动清单（复核留证）

| 位置 | 状态 |
|------|------|
| `agents` next-day L451（`open_price is None or pd.isna ...`） | 保留（D3） |
| V2 next-day L1140（同形） | 保留 |
| V2 `_force_liquidation` L563（`pd.isna(price) or price <= 0`） | 保留（Step 2 B4 实证） |
| `core/tracker.py` / `core/pending.py` / `core/interfaces.py` | 零改动 |
| `_get_execution_price`（L191-260） | 零改动（守卫在下游） |

---

## 5. 测试规格（`tests/test_p033_order_price_validation.py`）

| ID | 用例 | 构造 | 断言 |
|----|------|------|------|
| V1 | 守卫矩阵（参数 6） | 零成本 `ExecutionSimulator`；`open_price ∈ {None, NaN, inf, -inf, 0.0, -5.0}`；BUY 100 | 每例 `(False, None)`；`trade_log.get_trades() == []`；无异常抛出 |
| V2 | agents queue NaN / 0（参数 2） | 100 股 BUY 入队；`enable_pending_orders=True`；开盘价 NaN / 0；零成本 | 零成交；`cash == 10_000_000`；`len(get_pending_orders()) == 1`；`get_failure_stats()["pending_invalid_price"] == 1` |
| V3 | agents queue 负价（参数 2） | 同上，`open ∈ {-5.0, -inf}` | 零成交；`cash` 不变；计数 == 1（覆盖 R2「现金 +500」） |
| V4 | agents queue SELL NaN（持仓保留） | 先建仓 100 股 @10；入 SELL 100；`open=NaN` | 零成交；`qty == 100`；`avg_cost == 10.0`；`cash` 不变（覆盖 O-S2-P033-1「静默清零」） |
| V5 | 重试 bounded | 全程 `open=NaN`，逐日 `_process_pending_orders` + `mark_expired` 共 8 日 | 总成交 0；期末 `get_pending_orders() == []`；`0 < pending_invalid_price <= 5`（半衰期兜底，非精确等值——F-I-P033-2） |
| V6 | V2 queue NaN / 0（参数 2） | 注入 1 张 BUY 至 `PendingOrderQueue`；`caplog` 捕 WARNING | 零成交；`cash` 不变；日志含 `缺少价格数据订单` 与股票代码 A（L836-839；`skipped_price` 无 getter——F-S4-P033-2） |
| V7 | VWAP NaN（B1 回归锁） | `ExecutionPriceType.VWAP`；open/close=10 合法；high/low/volume=NaN | `(False, None)`；`trade_log` 空（第二入口已封） |
| V8 | 正常路径零误报（参数 2：agents / V2） | 合法价 10；各注入 1 张 BUY | 成交 1 笔 `price == 10`、`quantity == 100`；agents `pending_invalid_price` 缺席或 0；V2 无「缺少价格数据」日志 |

**红态纪律**：B1t/B2t/B3t 逐批先红后绿；**V8 在红态即通过属预期**（回归保护），须在 §11 显式标注（F-S9-P031-3 先例）。

---

## 6. fixture 表

| ID | 名称 | 内容 | 说明 |
|----|------|------|------|
| F1 | `_P033DM(prices, n_days, stocks)` | `trade_dates`（`bdate_range`）、`stock_codes`、`n_stocks`、`returns` 全 0、`get_adj_price(field, adj)` 返回常量价 DataFrame（**可分别为 open/close 赋 NaN/0/负/inf**） | 独立复制，不改 `test_p027` / `test_p029` / `test_p031` |
| F2 | `_P033Universe(dates, stocks)` | `tradable` / `buyable` / `sellable` 三面全 True | V2 与 agents 均需三面 |
| F3 | `_zero_cost()` | `CostConfig(0,0,0,0)` | V2 零成本便于精确断言 `cash` |
| F4 | `_make_agents_engine(enable_pending, n_days)` | `StrategyConfig(name="long", direction="long")` + `BacktestConfig(enable_pending_orders=…, rebalance=RebalanceConfig(frequency="daily"), optimizer=OptimizerConfig(method="equal_weight", round_lot=True), cost=_zero_cost())` + `signal` 全 0 | 仅直接调被调函数，不跑全链路 |
| F5 | `_make_v2_engine(n_days)` | `BacktestEngineV2(cfg)` + 直接注入 `dm` / `universe` / `ExecutionSimulator` / `PositionTracker(1, CAPITAL)` / `PendingOrderQueue()`（**不调 `setup()`**，避免因子文件依赖） | 与 Step 1 探针同构 |
| F6 | `_seed_position(tracker, qty, price)` | 构造 `Trade` → `tracker.execute_trade` | V4 用 |

**约束**：F1-F6 全部落在新文件内；`unittest.mock` 零使用（统一 `monkeypatch` / 直接注入）。

---

## 7. 低效排除

| # | 候选 | 排除理由 |
|---|------|----------|
| 1 | 把 `_get_execution_price` 五个分支各自加校验 | 五处重复判定，新增分支即漏；解析后单点等价且更小 |
| 2 | 在 `tracker.execute_trade` 加价格守卫 | 账目层堵漏掩盖上游错误，且 V3 共用（DESIGN D1 理由 / U-P033-3） |
| 3 | 引擎层按执行价格类型做 type-aware 过滤 | 引入引擎↔executor 配置耦合，收益边际（O-S4-P033-1） |
| 4 | 统一三处 next-day/强平 inline 判定为 `is_valid_price` | 无行为收益，触及 golden 敏感路径（D3） |
| 5 | 为 V2 新建 `_failure_counts` 以对齐 agents 键 | API 扩张超出 T1（Step 2 裁决 #4） |
| 6 | 对无效价订单 `cancel_order` 立即作废 | 改变重试语义（与 next-day 不一致）；`mark_expired` 已 bounded（D5） |
| 7 | 新增 warning 限流 | B3 实测 ≤4 交易日排空，无需限流（D5） |
| 8 | 修 R3（`close=0` 告警 `inf%`） | 无账目污染，独立 T3 候选（U-P033-1） |

---

## 8. 接口签名与回退点

| 函数 | 签名变化 | 回退点 |
|------|----------|--------|
| `core.execution.is_valid_price` | **新增模块级函数**（非公开 API 变更） | B1 删除函数 |
| `ExecutionSimulator.execute_order` | **无**（仅内部守卫 + docstring） | B1 删除守卫块 |
| `StrategyEngine._process_pending_orders` | 无 | B2 删除 3 行 + 导入回退 |
| `BacktestEngineV2._process_pending_orders` | 无 | B3 删除 3 行 + 导入回退 |
| `ExecutionSimulator._get_execution_price` | 无 | 不改（§4.5） |

**A8 口径**：`is_valid_price` 为模块级新增，I5「既有公开签名零变更」成立。

---

## 9. 实施期裁决与发现

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-I-P033-1 | 观察 | `is_valid_price` 置于 `TradeLog` 之后而非文件头 | 与 `TradeLog` 的模块内聚一致；`np` 已在 L16 导入，无前向依赖 |
| F-I-P033-2 | 观察 | V5 bounded 计数依赖半衰期与交易日历跨周末，**不可写精确等值** | 断言改为 `0 < count <= 5` + 期末队列为空（区间断言） |
| F-I-P033-3 | 观察 | agents 过滤块置于 `close_price` 赋值之后（DESIGN §4.2 精化）而非 `open_price` 之后 | 保持既有语句顺序零位移；`close_price` 计算不依赖有效性 |
| F-I-P033-4 | 观察 | V6 断言经 `caplog` 而非直接读 `skipped_price` | 该名单为 `_process_pending_orders` 局部变量，无 getter（F-S4-P033-2） |
| O-I-P033-1 | 观察 | 新测试文件首轮需 `black` 格式化（P-031 F-S9-P031-2 / P-029 F-S9-P029-1 两次先例） | B4 门禁前先跑 `black` |

---

## 10. 下一 Step 复核重点（Step 6 实施 Review）

1. **守卫位置**：`is_valid_price` 确在 `execution_price` 解析后、差异告警前；`execute_order` 的 `try` 结构未破坏；
2. **单一来源**：全仓 `is_valid_price` 仅 1 处定义、3 处调用（executor + 两引擎）；无第二套 `pd.isna` 组合新增；
3. **插入点精确性**：agents 过滤在 L509/L511 之间、V2 在 L808/L810 之间；两处均在 `execute_order` 之前；
4. **计量口径**：agents 新键 1 处写入；V2 复用 `skipped_price` 且未新增键；
5. **合法价回归**：`-k "golden or p027 or p029 or p031"` 全绿；13 条 golden 零重录；
6. **静默面**：新增 warning 仅 2 类（executor 守卫 / V2 汇总既有）；零新增 `except`（AST 22）。

---

## 11. Step 9 实施记录（TDD 三批红→绿 + 门禁）

（待 Step 9 回填）
