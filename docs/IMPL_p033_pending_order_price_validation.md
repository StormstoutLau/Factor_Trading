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
- **每批红态先跑**：B1t 红态 = 当前 `execute_order` 对 NaN/0/负/inf **成交**（**批次 6 failed / 1 passed** = V1 5F/1P + V7 1F——`None` 入参经既有 TypeError 漏斗 L339 已返回 `(False, None)`，红态即通过须标注，Step 6 F-S6-P033-1 / Step 8 F-S8-P033-2 批次口径更正）；B2t 红态 = agents queue 仍成交且无新键（**6 failed / 1 passed**，V8a 豁免）；B3t 红态 = V2 queue 仍成交且无「缺少价格数据」日志（**2 failed / 1 passed**，V8b 豁免）。全批红态 **14 failed / 3 passed**（6+6+2=14F；1+1+1=3P）。

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
| V1 | 守卫矩阵（参数 6） | 零成本 `ExecutionSimulator`；`open_price ∈ {None, NaN, inf, -inf, 0.0, -5.0}`；BUY 100 | 每例 `(False, None)`；`trade_log.get_trades() == []`；无异常抛出。**红态：5 failed / 1 passed——`None` 经 TypeError 漏斗 L339 已返回 False（Step 6 F-S6-P033-1，豁免标注）** |
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

> **执行基座**: DeepSeek-V4.1-Flash（与四文档同源）；基线 HEAD `e53f560`（Step 8 收口）；Python312 + `MPLBACKEND=Agg`。

### 11.1 三批红→绿（批次级口径，F-S8-P033-2）

| 批次 | 实施内容 | 红态实测 | 绿态实测 |
|------|----------|----------|----------|
| **B1t** | V1 矩阵 6 + V7 VWAP NaN | **6 failed / 1 passed**（V1 五例 NaN/inf/-inf/0/-5 均成交入账 + V7 成交；`None` 经 `100 * None` TypeError 漏斗 L339 返回 `(False, None)` → **红态即通过，豁免**） | **7 passed** |
| **B2t** | V2 两参数 + V3 两参数 + V4 + V5 + V8a | **6 failed / 1 passed**（agents queue 六例仍成交且无 `pending_invalid_price`；V8a **红态即通过，豁免**） | **14 passed**（累计） |
| **B3t** | V6 两参数 + V8b | **2 failed / 1 passed**（V2 queue 两例零成交但缺「缺少价格数据」汇总日志——D1 已兜底、D2 未落地；V8b **红态即通过，豁免**） | **17 passed** |

**全批红态 14 failed / 3 passed** = 6F + 6F + 2F 与 1P + 1P + 1P，与 Step 8 F-S8-P033-2 修正口径**逐项吻合**。

### 11.2 门禁复跑（Step 9 实施后）

| 门禁 | 目标 | 实测 |
|------|------|------|
| 全量 pytest | 748 | ✅ **748 passed**（172 warnings，45.47s） |
| 新测试收集 | 17 实例 / 8 函数 | ✅ **17 tests collected**（`^def test_` = **8**，V1/V2/V3/V6/V8 五处参数化） |
| 新测试绿 | 17 passed | ✅ **17 passed**（2.16s） |
| black `--check core tests` | 120 | ✅ **120 files would be left unchanged**（新测试文件首轮重排 1 文件，O-I-P033-1 先例） |
| mypy `--explicit-package-bases core` | 37 files 0 | ✅ **Success: no issues found in 37 source files** |
| golden | 13 零重录 | ✅ **13 passed, 735 deselected**；`tests/golden/` 零改动 |
| `tests/` .py 数 | 83 | ✅ **83** |
| 回归子集 `-k "golden or p027 or p029 or p031"` | 57 | ✅ **57 passed, 691 deselected**（0 failed / 0 error） |
| AST `except Exception`（十文件口径） | 22 | ✅ **22** |
| `core/` 新增 `except`（F-S8-P033-5） | 0 | ✅ `git diff core/execution.py` 中 `^\+.*\bexcept\b` = **0** |
| 公开签名删除 | 0 | ✅ `git diff \| Select-String '^-\s*def '` = **0** |
| 零改动面（tracker / pending / interfaces / target_positions / golden / filter / scripts / cli / pyproject / test_p029* / test_p031*） | 空 | ✅ `git status --short` 全空 |

**净行数（`git diff --numstat`）**: `core/execution.py` **+21/−1** / `agents/multi_strategy_engine.py` **+6/−1** / `core/engine_v2.py` **+6/−1** / `tests/test_p033_order_price_validation.py` **+203（新增）**。

### 11.3 顺序敏感五项留证（CHECKLIST §7.3）

| # | 约束 | 实测 | 结果 |
|---|------|------|------|
| ① | 守卫在解析后、差异告警前 | `execution_price` **L304-306** → 守卫 **L308-315** → `# 价格合理性检查` **L316** | ✅ |
| ② | 守卫在 `amount` / `Trade` / `add_trade` 前 | 守卫 **L308** < `amount` **L327** < `add_trade` **L350** | ✅ |
| ③ | agents 过滤在 L509 后、L511（clamp）前 | `open_price` **L508** / `close_price` **L509** → 守卫 **L511-514** → clamp **L517** | ✅ |
| ④ | V2 过滤在 L808 后、L810（clamp 告警）前 | `close_price` 赋值 **L804-808** → 守卫 **L810-813** → clamp 告警 **L815** | ✅ |
| ⑤ | B1 先于 B2/B3 | B1t 红→绿（7 passed）后方实施 B2 / B3（导入依赖） | ✅ |

**单一来源**: `is_valid_price` 全仓 **1 处定义**（`core/execution.py:153`）+ **3 处调用**（execution L309 / agents L512 / engine_v2 L811），零第二套 `pd.isna` 组合。

### 11.4 行号漂移登记（F-I 惯例）

| 文件 | 锚点 | 实施前 | 实施后 | 漂移 |
|------|------|--------|--------|------|
| `core/execution.py` | `is_valid_price`（新增） | — | **L153** | 新增 11 行 |
| `core/execution.py` | `class ExecutionSimulator` | L153 | **L164** | +11 |
| `core/execution.py` | `_get_execution_price` | L191-260 | **L202-271** | +11 |
| `core/execution.py` | `execute_order` def / docstring / try / except | L262 / L287-289 / L290 / L339 | **L273 / L298-300 / L302 / L359** | +11 / +11 / +12 / +20 |
| `core/execution.py` | 守卫插入点 | L292-294 之后 | **L308-315** | — |
| `agents/multi_strategy_engine.py` | 导入 L32 / `_record_failure` / `_clamp_sell_quantity` / `_execute_next_day_orders` / `_process_pending_orders` | L32 / L126 / L385 / L396 / L478 | **L32（改行）/ L126 / L385 / L396 / L478** | 0（插入点在函数体内） |
| `agents/multi_strategy_engine.py` | 过滤块 / `mark_expired` | L509-511 之间 / L528 | **L511-514 / L533** | 下游 +5 |
| `core/engine_v2.py` | 导入 L23 / `_force_liquidation` / `_clamp_sell_quantity` / `_process_pending_orders` | L23 / L510 / L671 / L752 | **L23（改行）/ L510 / L671 / L752** | 0（强平守卫 L563 原位） |
| `core/engine_v2.py` | 过滤块 / 汇总日志 / `_execute_next_day_orders` | L808-810 之间 / L836-839 / L1091 | **L810-813 / L841-844 / L1096** | 下游 +5（next-day 守卫 **L1145**） |

### 11.5 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P033-1 | 观察 | 新测试文件首轮被 `black` 重排（1 文件）——O-I-P033-1 预判成立，非缺陷 | 已格式化，门禁 120 unchanged |
| F-S9-P033-2 | P3 | B3t 首跑红态异常：新测试文件缺 `import logging` → `caplog.set_level` 抛 `NameError`，致 3 failed（含 V8b）而非预期 2F/1P——**测试自身缺陷**，与 B3 守恒无关 | **当轮修复**（补 `import logging`）后重跑，红态回到 **2F/1P** 与预测一致 |
| O-S9-P033-1 | 观察 | B3t 红态实证：即使 D2 未落地，D1 守卫已使 V6 的「零成交/现金不变」断言成立——红态仅由「汇总日志缺失」驱动，反向印证**双层防线**（D1 安全层先于 D2 可观测层生效） | 登记（DESIGN-D2 预期） |

---

## 12. Step 5 自检

| # | 检查项 | 结果 |
|---|--------|------|
| S1 | DESIGN D1-D6 全落点 | D1 §4.1+4.2 / D2 §4.3+4.4 / D3 §4.5 不改清单 / D4 §8 调用方表 / D5 §7-#6#7 / D6 §7-#8 —— **6/6** |
| S2 | I1-I7 → 验证出口 | I1→V1/V7 / I2→V2-V6 / I3→V8+B4 门禁 / I4→V2/V5/V6 / I5→§8 A8+AST / I6→V2/V6 / I7→§1 门禁口径 —— **7/7** |
| S3 | 红态可观测 | V1 五例（NaN/inf/-inf/0/-5）当前成交→红；**V1-None 经 TypeError 漏斗红态即通过**（Step 6 E3 实证，须标注）；V2-V6 当前成交→红；V7 当前成交→红；V8 回归保护红态即通过（标注） |
| S4 | 锚点实查 | `TradeLog` L52-150 / `ExecutionSimulator` L153 / `execute_order` L262、解析 L292-294 / agents L32·L509·L511 / V2 L23·L808·L810 与 HEAD `013c4d3` 逐项核对命中 |
| S5 | 既有回归面 | `test_execution_price.py` 十用例全合法价（10.0/11.0）；golden 13 条全合法价（N3 零非正价调用实证）；`test_p031` fixture 全合法价——行为变更不触及 |
| S6 | 门禁口径 | 748 = 731 + 17；测试文件 83；black 120（新测试文件）；mypy `core` 37 files 0（无新文件） |
| S7 | 签名可实现性 | `is_valid_price(Optional[float]) -> bool` 纯函数；`execute_order` 签名零变更；引擎导入行仅加名 |
| S8 | 零新增 `except Exception` | 守卫与过滤块均为前置 `if`，不进异常漏斗——合计恒 22 |

---

## 13. Step 6 实施 Review 记录（异构基座 GLM-5.3-Flash）

### 13.1 基座与对象

- **复审基座**: **GLM-5.3-Flash**（≠ IMPL 作者 DeepSeek-V4.1-Flash，RULE-5 成立）
- **复审对象**: `ca78f5f`（IMPL_p033 提交版）；复审时点 HEAD `b837d5f`（代码面与 `013c4d3` 一致，仅 docs 变更）
- **方法**: E1 锚点机械复核 + E2 门禁基线独立复测 + E3 红态行为探针 + E4 六项复核重点裁决（IMPL §10）

### 13.2 E1 锚点机械复核（关键 10 项）

| # | IMPL 声称 | 实查 | 结果 |
|---|-----------|------|------|
| A1 | `is_valid_price` 插入点 L151-152（`TradeLog` L150 结束 / `ExecutionSimulator` L153） | 读码 L144-153 | ✅ 命中 |
| A2 | 守卫插入点 L292-294（解析）之后、L296（差异告警注释）之前；`try` L290 / `except` L339 结构完整 | 读码 | ✅ 命中 |
| A3 | docstring Returns 段 L287-289 | 读码 | ✅ 命中 |
| A4 | agents 导入 L32 / 过滤点 L509 后、L511 前 | 读码 | ✅ 命中 |
| A5 | V2 导入 L23 / 过滤点 L808 后、L810 前 | 读码 | ✅ 命中 |
| A6 | `skipped_price` 局部名单 L780 / 汇总日志 L836-839（`logger.warning`） | 读码 | ✅ 命中（V6 caplog 可行） |
| A7 | agents `_record_failure` L126 可承接新键 | 读码 | ✅ 命中 |
| A8 | `np` 已导入 execution.py L16 | 读码 | ✅ |
| A9 | 不改清单：agents next-day L451 / V2 next-day L1140 / 强平 L563 | 读码 | ✅ 三处 inline 判定在位 |
| A10 | `_get_execution_price` L191-260 零改动 | 读码 | ✅ 五分支结构确认 |

### 13.3 E2 门禁基线独立复测（HEAD `b837d5f`）

| 门禁 | IMPL 声称（实施前基线） | 实测 | 结果 |
|------|--------------------------|------|------|
| 全量 pytest | 731 | **731 passed**（172 warnings，71.10s） | 一致 |
| black `--check core tests` | 119 | **119 unchanged** | 一致 |
| mypy `core` | 37 files 0 | **37 files 0** | 一致 |
| `tests/` .py 数 | 82 | **82** | 一致 |

### 13.4 E3 红态行为探针（V1 矩阵六值，当前 `execute_order`）

| 入参 | 现行行为 | 红态判定 |
|------|----------|----------|
| `None` | **`success=False`（TypeError 漏斗 L339 兜底），trade_log 零入账** | **红态即通过** |
| `NaN` / `inf` / `-inf` / `0.0` / `-5.0` | **全部 `success=True` 且入账**（trades_so_far 1→5） | 红态失败 ✅ |

**结论**：IMPL §3「B1t 红态 = V1 全 6 例失败」**不准确**——实际 **5 failed / 1 passed**（None 经 `100 * None` TypeError 被既有 `except` 捕获）。全批红态合计 **14 failed / 3 passed**（V1-None、V8a、V8b 三例豁免）→ **F-S6-P033-1（P3）当轮回写**。（Step 8 更正，F-S8-P033-2：B1t 批次含 V7，**批次级红态 6F/1P**——「5F/1P」为 V1 矩阵内读数；全批 14F/3P 不变。）

### 13.5 E4 六项复核重点裁决（对应 §10）

| # | 复核点 | 裁决 |
|---|--------|------|
| 1 | 守卫位置 | **正确**——L292-294 解析后 / L296 告警前；`try` 结构未破坏（守卫为前置 `if`，非异常路径） |
| 2 | 单一来源 | **规格成立**——1 定义（execution 模块级）+ 3 调用（executor / agents / V2）；全仓无第二套判定（grep `is_valid_price` 现 0 命中，实施后须复验 =1 处定义） |
| 3 | 插入点 | **精确**——agents L509/L511、V2 L808/L810 均在 `execute_order` 之前；两引擎内部顺序差异（clamp 前后）不影响 |
| 4 | 计量口径 | **正确**——agents 新键 1 处写入（`_record_failure`）；V2 复用 `skipped_price` 零新键；两口径经 Step 2 裁决 #4 |
| 5 | 合法价回归 | **基线一致**（E2 四项复测）；golden 13 条 + 既有 731 测试全合法价（N3 + S5）→ 预期零重录零破坏 |
| 6 | 静默面 | **规格成立**——新增 warning 2 类（executor 守卫 / V2 既有汇总）；零新增 `except`（规格 S8）；AST 22 预期恒定 |

### 13.6 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S6-P033-1 | P3 | §3 B1t 红态描述「V1 全 6 例失败」失实——`None` 入参经既有 TypeError 漏斗（L339）红态即通过，实际 **5 failed / 1 passed**；全批红态 **14F/3P**（豁免三例：V1-None / V8a / V8b） | **当轮回写 §3 + §5 V1 行**（已回写） |
| O-S6-P033-1 | 观察 | 守卫后 None 案例行为从「TypeError 静默漏斗」变为「显式守卫 warning」——对调用方同为 `(False, None)`，仅日志面变化，行为兼容 | 登记 |
| O-S6-P033-2 | 观察 | 守卫消息用 `{execution_price!r}`——对 NaN/inf/None 输出 `nan`/`inf`/`None`（repr 形态），可读性可接受 | 登记 |

### 13.7 结论与 Step 7 前置条件

**结论**: **pass**（0 P0/P1/P2 / 1 P3 当轮回写 / 2 观察）——锚点十项全命中、门禁基线四项一致、红态预期修正后与实测吻合、六项复核重点全过，准予进入 **Step 7 CHECKLIST**。

**Step 7 前置条件**:
1. CHECKLIST 按 §5 V1-V8（17 实例）口径编制，红态豁免三例（V1-None / V8a / V8b）在红态纪律项显式登记；
2. 实测列引用本文件 §13.3 基线读数（731 / 119 / 37 / 82）；
3. Step 9 红绿须逐批落 §11（B1t **6F/1P** → B2t 6F/1P → B3t 2F/1P → 748；Step 8 F-S8-P033-2 更正批次口径，V1 矩阵内 5F/1P）。
