# DESIGN P-059 模拟数据验证体系（Step 3）

> **批次**: P-059（§5 批次表 L264；执行序 **P-048 之前**）
> **上游**: [RESEARCH_p059_data_validation.md](RESEARCH_p059_data_validation.md)（Step 1 + Step 2 §11 复审）
> **规范**: `F:\Spec_Workflow\SPEC_PROCESS.md` v1.7.1（十步流程 / RULE-1~6 / E1-E5）
> **判档**: **T1**（新增测试侧基础设施 + **仅 G4** 一处生产修复）
> **基线**: HEAD `5f853637d6dc`；`846 passed` / golden 18 / black `line-length=100` / mypy 生产面 109 files 0
> **作者**: DeepSeek-V4.1-Flash　**Step 4 复审**: GLM-5.3-Flash（待）
> **零预填**: 本文 §17 为 Step 4/6/8/10 预留；**未填写处不得推断**

---

## 1. 目标与非目标

### 1.1 目标（可验收）

| # | 目标 | 对应 RESEARCH |
|---|------|---------------|
| O1 | 边界场景**可声明**：每条场景是数据 + 闭式期望的纯声明，不写流程代码 | G1 / M-A |
| O2 | 中间态**可观测**：逐日 trace（目标权重 / 掩码 / 订单三态 / 成交 / 现金 / 持仓 / NAV） | G2 |
| O3 | 断言**可组合**：掩码语义、现金非负、限价合法、订单三态完备、目标偏离、变质关系 | G9 / G20 |
| O4 | 入口**统一**：`scripts/verify_scenario.py` 单命令列出 / 跑单场景 / 打某日 trace | G8 |
| O5 | 新模块挂验证 **≤3 行**（注册表加一条） | G8 |
| O6 | 修掉 **G4**（两路径现金口径分裂），并以「同单两路径对拍」场景锁死 | G4 / D2 |
| O7 | 能力边界**机器可读**（不建模分钟/tick/盘中临停/集合竞价；不证明 alpha） | G21 / D7 / D8 |

### 1.2 非目标（明确不做）

| # | 不做 | 依据 |
|---|------|------|
| N1 | **G5 不修**（经 Step 2 复核撤回：实现 + 测试 + 自然日口径声明三者齐备） | §11.2 / F-S2-P059-x |
| N2 | 不改生产数据层入参校验（BZ1/G10 只落**验证侧守卫**） | D9 / S14 |
| N3 | 不建模退市整理期首日无涨跌幅、盘中临停、集合竞价撮合 | D8 / S13 |
| N4 | 不引入 Hypothesis / 第三方回测框架 | D5 / D11 |
| N5 | 不动 18 条 golden 基线 | D10 / S10 |
| N6 | 不改 `core/` 除 G4 一处之外的任何行为 | D2 |

---

## 2. 继承约束（D1-D11 → 设计决策）

| RESEARCH | 内容 | 本文落地 |
|----------|------|----------|
| D1 | M-A 扩展现有资产，不新建平行体系 | §3（复用 `_synth_fixture` / `_golden_cases` 构造与容差） |
| D2 | 仅 G4 生产修复 | §9 |
| D3 | trace 落测试侧 | §5（proxy 注入，`core/` 零改动） |
| D4 | 编号 P-059 | 文件名前缀 |
| D5 | 不引 Hypothesis，采纳变质关系 | §7 |
| D6 | ≥10 例且 ≥6 层 | §8（14 必做 / 7 层） |
| D7 | 能力边界显式声明 | §10 |
| D8 | 日频口径 | §10 |
| D9 | 脏数据守卫仅验证侧 | §8-S11 |
| D10 | 18 golden 零重录 | §9.3 / §14 |
| D11 | 不做第三方框架全链路对拍 | §3.4 |

---

## 3. 架构与文件布局

### 3.1 决策 DD1：复用既有三层资产，不新建夹具体系

| 既有资产 | 复用方式 |
|----------|----------|
| [tests/_synth_fixture.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_synth_fixture.py)（`write_price_fixture` / `write_factor` / `write_universe`） | 场景构造器**直接调用**；缺口 = `open/high/low` 缺省复用 `close`（G3），由 DD3 在场景层**显式传独立 OHLC** 解决，**不改该模块签名** |
| [tests/_golden_cases.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_golden_cases.py)（`TOLERANCE` / `INITIAL_CAPITAL` / `_v2_config` 思路） | 容差沿用 `TOLERANCE = {"rtol": 1e-9, "atol": 1e-12, "money_atol": 1e-6}`；配置构造在场景层重建（golden 的 `_v2_config` 为私有函数，不 import 私有 API） |
| [core/invariants.py](file:///f:/Coding/Factor_Trading_v3.0/core/invariants.py) | 账目恒等仍由运行期 `check_all` 承担；trace 侧**另有**逐桶 `cash+MV==nav` 复核（`ExpectedBlock.cash_identity` 开关，默认开——**Step 6 回写** F-S6-P059-8，原文「场景不重复实现」与实现不符） |

> **不新建**：不建第二套数据生成器、不建第二套容差表、不建第二套账目校验。

### 3.2 决策 DD2：扁平文件布局（**与 RESEARCH §5 措辞的差异声明**）

RESEARCH §5 曾写 `tests/scenarios/`。**本设计改为扁平前缀文件**，理由（须 Step 4 复核）：

1. `tests/` 无 `__init__.py`，pytest 以 `tests/` 作为 basedir 插入 `sys.path`，既有模块一律 `from _synth_fixture import ...` 扁平导入；
2. 嵌套子包会导致「`tests/` 扁平导入」与「`tests.scenarios` 包导入」两套并存，`scripts/record_golden.py` L27-32 已确立扁平 + `sys.path.insert` 约定；
3. 扁平文件不会与被 `python_files = ["test_*.py"]` 收集的测试混淆（`pyproject.toml` L103-104）。

```
tests/
  _scenarios_spec.py        # ScenarioSpec / ExpectedBlock / FillExpectation / OrderState（纯数据契约）
  _scenarios_builder.py     # build_scenario(root, spec) -> ScenarioRun（写临时夹具 + 建引擎 + attach trace）
  _scenarios_trace.py       # TraceRecorder + 3 个 proxy（executor / tracker / optimizer）
  _scenarios_assert.py      # 断言原语 + 变质关系原语
  _scenarios_cases.py       # SCENARIOS 注册表（**单一来源**，17 条）
  _scenarios_capability.py  # CAPABILITY_BOUNDARIES（机器可读）
  test_p059_scenarios.py    # 主测试：parametrize(SCENARIOS)，结构断言 + 闭式期望
  test_p059_metamorphic.py  # R1/R2/R3 变质关系
  test_p059_g4_cash_parity.py # 两路径现金对拍（G4 回归锁）
scripts/
  verify_scenario.py        # 统一 CLI（--list / --scenario / --day / --json / --boundaries；
                            #   RESEARCH B5 的 --dump 由 --json/--day 承载——**Step 8 回写声明** F-S8-P059-3）
```

### 3.3 决策 DD3：场景 = 声明，执行 = 唯一入口

`build_scenario()` 是**唯一**执行入口；测试与 CLI 都调它，杜绝「测试用夹具 A、CLI 用夹具 B」（沿用 `_golden_cases.py` 单一来源原则）。`OHLC` 由 spec 显式给出，若 `open/high/low` 为 `None` 则按 `close` 填充并在 trace 中标注 `ohlc_synthetic=True`（可被断言拒绝：S03 一字板用例要求 `ohlc_synthetic=False`）。

### 3.4 不做的架构项

- 不建 `core/trace.py`（D3）；不建第三方框架对比 harness（D11）；不建覆盖率插件门禁（本批以「场景数 + 层数」验收）。

---

## 4. 数据契约

### 4.1 `ScenarioSpec`（frozen dataclass）

| 字段 | 类型 | 说明 |
|------|------|------|
| `scenario_id` | `str` | `S01`..`S14` / `E01`..`E03` |
| `title` | `str` | 中文标题 |
| `layer` | `str` | `L1`..`L7`（覆盖度统计用） |
| `gaps` | `tuple[str, ...]` | 覆盖的 `G*` / `BZ*` |
| `dates` | `pd.DatetimeIndex` | 交易日（可为不规则日期，用于 BZ18） |
| `codes` | `tuple[str, ...]` | 标的（含 `000001`/`600000`/`430xxx` 北交所等） |
| `close` / `open` / `high` / `low` | `np.ndarray \| None` | `(n_dates, n_codes)`；`None` → 复用 `close` 并标 `ohlc_synthetic` |
| `suspend` / `st` | `np.ndarray \| None` | 布尔掩码 |
| `factors` | `Mapping[str, np.ndarray]` | 因子名 → 矩阵（注册到 `factor_files`） |
| `universe_extra` | `Mapping[str, Any]` | `list_date` / `delist` 透传 |
| `config` | `Mapping[str, Any]` | 覆盖 `BacktestConfig` 字段（`enable_pending_orders`、`cost`、`universe` 等） |
| `expected` | `ExpectedBlock` | **闭式期望**（S2） |
| `metamorphic` | `tuple[Metamorphic, ...]` | ≥1 条（S11） |

### 4.2 `ExpectedBlock`（闭式，禁止「跑完录制」）

| 字段 | 说明 |
|------|------|
| `fills` | `tuple[FillExpectation, ...]`：`(date, code, side, qty, price, price_atol)` |
| `no_fill` | `tuple[tuple[date, code, side], ...]`：显式「不得成交」清单 |
| `order_states` | `tuple[OrderStateExpectation, ...]`：`(date, code, side, state)`，`state ∈ {"filled","retry","dropped"}`（S8） |
| `final_cash` / `final_positions` / `final_nav` | 末值（`money_atol=1e-6`） |
| `cash_identity` | `bool`：启用「现金 + 市值 = NAV」逐日恒等（I2 交叉） |

> **S2 落地**：`expected` 的每个数值必须可由 spec 数据**手算**（例：`100 股 × 10.00 元 + max(30,5) + 1.00 = 1006.00`）。测试首行断言 `spec.expected` 非空，禁止「先跑后填」。

### 4.3 `DayBucket`（trace，字段固定 = S7）

> **Step 8 回写（F-S8-P059-2）**: RESEARCH S7 字面清单与本表存在聚合差异——`mask(buy,sell)` 拆为 `buyable`/`sellable` 两键、`submitted` 并入 `orders`、`reason` 并入 `rejected` 条目字段——语义等价、键数 10；以本表为实现真值（`BUCKET_KEYS`）。

| 键 | 类型 | 说明 |
|----|------|------|
| `date` | `str` | `YYYY-MM-DD` |
| `target_weight` | `dict[str, float]` | 当日再平衡目标（无再平衡 → `{}`） |
| `buyable` / `sellable` | `list[str]` | 当日掩码为 True 的标的 |
| `orders` | `list[dict]` | `{"code","side","qty","reason"}`（reason 见 4.4） |
| `filled` | `list[dict]` | `{"code","side","qty","price","amount","cost"}` |
| `rejected` | `list[dict]` | `{"code","side","qty","reason"}` |
| `cash` / `nav` | `float` | 日终 |
| `positions` | `dict[str, int]` | 日终持股 |

### 4.4 订单 reason 枚举（固定闭集）

`limit_up` / `limit_down` / `suspended` / `st_blocked` / `cash_short` / `t1_locked` / `invalid_price` / `no_position` / `expired` / `filled`

> 新增 reason 须同步 `_scenarios_spec.REASONS` 与断言，否则 `assert_order_reasons_closed()` 失败。

---

## 5. trace 实现（测试侧，零生产改动）

### 5.1 决策 DD4：proxy 注入而非埋点

引擎在 `setup()` 后持有 `executor` / `tracker` / `optimizer` 三个可替换属性（[engine_v2.py L148-161](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L148-L161) 由 `setup()` 填充），`run()` 只通过 `self.*` 访问 → 测试侧可整体替换：

| proxy | 包装的真实组件 | 记录 |
|-------|----------------|------|
| `RecordingExecutor` | `IExecutionSimulator` | `execute_order(stock, side, qty, date, open_price, close_price=None)` → `filled` 追加 |
| `RecordingTracker` | `IPositionTracker` | `update_market_values(date, prices)` → **收口当日桶**（cash / nav / positions）+ `execute_trade` 追加（可选） |
| `RecordingOptimizer` | `IOptimizer` | `optimize(signals, returns_data=None)` → 暂存 `target_weight`，在下一个桶收口时写入 |

**透传纪律**（防「记录器改变行为」）：三个 proxy 一律 `__getattr__` 委托，**不缓存可变状态**、不改参数、不捕获异常（仅观测）。

### 5.2 决策 DD5：日分桶以 `update_market_values` 为边界，按日期**幂等合并**

依据 [engine_v2.py L477-519](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L477-L519) 的日循环顺序：`退市结算 → 次日订单 → 队列订单 → 再平衡 → update_market_values → DAY_END`。

- 每个 `date` 首次出现即建桶，同日再次 `update_market_values`（结算路径 L665-666 可能二次调用）→ **合并而非新建**；
- 收口时把暂存的 `target_weight` 写入该桶并清空；
- **I13（新增不变式）**：`len(buckets) == len(trade_dates)` 且 `dates` 严格递增 —— 任一不满足即 `AssertionError`（防 proxy 漏日/错日）。

### 5.3 关闭语义（S6 / I3）

`TraceRecorder(enabled=False)` → **不 attach 任何 proxy**，引擎使用原生组件（`engine.executor is isinstance(ExecutionSimulator)` 断言可证），运行时开销为零，行为不可能改变。

---

## 6. 断言原语（`_scenarios_assert.py`）

| 原语 | 断言内容 | 对应 |
|------|----------|------|
| `assert_trace_shape(trace, dates)` | 键集合固定、桶数 == 交易日数、日期递增 | S7 / I13 |
| `assert_order_states_closed(trace)` | 每个订单恰好落在 `filled/retry/dropped` 之一，**总数守恒**（进 = 出 + 挂起） | S8 / I4 |
| `assert_reasons_closed(trace)` | `reason ∈ REASONS` | 4.4 |
| `assert_mask_semantics(trace, spec)` | 不可买 → 无买成交；不可卖 → 无卖成交 | I5 |
| `assert_cash_non_negative(trace)` | 逐日 `cash >= 0` | I6 |
| `assert_price_legal(trace, spec, ruleset)` | 成交价 ∈ [跌停价, 涨停价]（由 `filter.limit_rules` 计算，**不在场景内重算**） | S4 / I7 |
| `assert_target_deviation(trace, tol)` | 连续不可买时 `Σ|实际-目标|` ≤ tol 且现金闲置可解释（**Step 6 回写**：可选接线，当前场景的 T+1/停牌延迟语义由成交/挂单断言覆盖，见 F-S6-P059-4） | G7 |
| `assert_capability_declared()` | 能力边界清单非空且含必备键 | S13 |
| `assert_dirty_input_raises(fn)` | 脏数据守卫触发明确异常 | I12 / S14 |
| `assert_scenario(spec, run)` | 组合上面全部 + 闭式 `expected` 比对（`TOLERANCE`） | 主入口 |

---

## 7. 变质关系（R1-R3）

### 7.1 决策 DD6：三条关系，逐场景声明 ≥1 条

> **Step 8 回写（F-S8-P059-3）**: RESEARCH S11「每个场景须声明 ≥1 条」在本设计收窄为**仅 backtest 场景**——`raises`（构建期即抛、无运行轨迹）、`stops` / `limit_price`（纯函数级 payload，无端到端轨迹）无可比较的 trace，变质关系不适用；由 `test_every_backtest_scenario_declares_relation` 强制。

| ID | 变换 | 不变量 | 前提（S12，防假阳性） |
|----|------|--------|----------------------|
| R1 | `close/open/high/low × k`、`initial_capital × k`、价格带上限同步（避免跨涨停带） | 收益率 / 成交笔数 / 持仓股数不变 | **整手可比**：①若 `k` 使「最低佣金占比」跨越阈值（`amount < 5000` 边界，见 §9.2），**禁止**对现金类断言套用；②（**Step 4 回写**）`k` 须远离整手 floor 边界——`qty = floor(cash/(price×100))×100` 在边界翻转会使「持仓股数不变」误红（F-S4-P059-5） |
| R2 | 增删「惰性标的」（从不入目标集、从不成交） | NAV / 现金 / 成交逐日一致 | 该标的不得影响截面排名（因子取 NaN 且 `exclude_na_factors=True`） |
| R3 | `dates` 整体平移（数量与顺序不变） | 桶数一致、末值相对指标不变 | 平移后不得跨「上市/退市/ST」状态边界 |

### 7.2 实现要点

- `assert_metamorphic_scale(spec, k)` 内部**重跑同一 spec**（两次独立 `build_scenario`），比较 `trace` 的相对量；容差用 `TOLERANCE`；
- 关系失败时输出**首个分歧桶 + 字段**（可排查性，O4）；
- R1/R3 由 `test_p059_metamorphic.py` 统一 parametrize，不占场景配额（D6 的「场景 ≥10」只计 `SCENARIOS` 注册表）。

---

## 8. 场景清单（14 必做 + 3 扩展）

### 8.1 必做（14 例，覆盖 **L1-L7 全部 7 层**）

| ID | 场景 | 层 | 覆盖 | 闭式期望要点 |
|----|------|----|------|--------------|
| S01 | 涨停买不进 + 次日重试 | L4 | G9（**Step 8 回写**：原列 `BZ7 / G4 / G9` 中 BZ7/G4 为现金口径缺口，属 S09，系笔误删除） | 买 0 笔；提单入 `retry`；恢复日按开盘价成交 |
| S02 | 跌停卖不出 | L4 | BZ9 / G13 | 卖 0 笔；持仓不变；现金不变 |
| S03 | 一字板 3 日（独立 OHLC） | L4 | G3 / G9 | `ohlc_synthetic=False`；掩码逐日 True；解板日一次性成交 |
| S04 | 停牌 2 日复牌 | L1 | BZ14 / G16 | 停牌日零成交、NAV 用最后价；复牌日成交 |
| S05 | ST ±5% 限幅 | L4 | G6（**Step 8 回写**：原列 `G6 / BZ11` 中 BZ11 无限制窗口属 S06，删除） | 涨停价 = 前收 × 1.05；买 0 笔。**日期约束**：必须 `< 2026-07-06`（RULES L57-58：主板 ST 该日起改 10%） |
| S06 | IPO 前 5 日无涨跌幅 | L4 | BZ11 / G14 | 第 1-5 日掩码放行；第 6 日恢复 10% |
| S07 | 退市动态池移除 + 清算 | L5 | BZ13 / G16 | 退市日按 `delist_return` 或最后收盘清算；持股归零 |
| S08 | T+1 禁卖 | L4 | G13（X3 为外部规则锚，不入场景码——**Step 8 回写**声明） | 建仓日卖出 → `t1_locked`；次日可卖 |
| S09 | 小额单最低佣金（两路径对拍） | L5 | BZ10 / **G4** | 两条路径 `required_cash` **完全相等**（`money_atol`） |
| S10 | 权重和 > 1 | L3 | BZ5 / G12 | 记录 warning；现金不为负；`Σw*NAV > cash` 时由执行端夹紧 |
| S11 | 脏数据（NaN / 负价） | L1 | BZ1 / G10 | 验证侧守卫抛明确异常（生产层不抛，见 N2） |
| S12 | 全标的停牌无订单（**Step 8 回写**：原「常量截面因子」前提不成立——`_precompute_factors` 末尾 `fillna(0)`，见 F-S5-P059-2） | L2 | BZ14 / G9（原列 BZ3 / G11 随前提失效改挂） | 全标的 suspend → `tradable` 空 → 再平衡早退、零订单、NAV 恒 100000 |
| S13 | 止损/止盈同 bar 双触发 | L6 | BZ15 / G17 | 按 P-045 D6 优先级 `SL → trailing → TP → time`；取 SL 价 |
| S14 | 空信号 → 全清仓 | L7 | BZ6 / G18 | 目标空 → 全卖出 3 笔；末值 = 现金 |

> **覆盖统计（RULE-2）**: 层覆盖 `L1: S04,S11` / `L2: S12` / `L3: S10` / `L4: S01,S02,S03,S05,S06,S08` / `L5: S07,S09` / `L6: S13` / `L7: S14` → **7 层 ✓ ≥6**；**14 例 ✓ ≥10**。

### 8.2 扩展（3 例，P2 残余；若 Step 5 工期紧张可降级为 `@pytest.mark.skip` + 原因）

| ID | 场景 | 层 | 覆盖 | 说明 |
|----|------|----|------|------|
| E01 | 限价**不做 0.01 分位舍入** | L4 | G6 | `build_limit_prices`（L170-176）直接浮点乘、无 `round`；锁现状并在能力边界声明与交易所「0.01 四舍五入」口径差异（不改生产，D2 仅授权 G4） |
| E02 | 跨长假日期跳空 | L1/L4 | BZ18 | 持仓龄/T+1 用**交易日**索引，非自然日 |
| E03 | 复权因子变更日 NAV 连续性 | L5 | BZ12 / G15 | 锁 hfq 下 NAV 无跳变（原「除权持仓调整」前提不成立，见 §11.2-F-S2-P059-4） |

---

## 9. G4 生产修复（唯一生产改动）

### 9.1 精确改动（1 处，6 行）

[core/engine_v2.py L1273-1277](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1273-L1277)：

```python
# 现状
if order.side == OrderSide.BUY:
    required_cash = order.quantity * open_price * 1.002

# 目标（与队列路径 L907-912 同源；estimate_buy_cash 已在 L23 导入）
if order.side == OrderSide.BUY:
    required_cash = estimate_buy_cash(
        order.quantity * open_price,
        commission_rate=self.cfg.cost.commission_rate,
        commission_min=self.cfg.cost.commission_min,
        slippage_pct=self.cfg.cost.slippage_pct,
    )
```

**边界**：仅替换**费用口径**；数量基数仍为 `order.quantity`（不引入 clamp，避免夹带行为变更）；SELL 分支零改动；`estimate_buy_cash` 的 `amount <= 0 → 0.0` 分支由上游 `open_price > 0` 与 `quantity > 0` 保证不触发。

### 9.2 影响带（RULE-2 手算，默认 `commission_rate=0.0003 / commission_min=5 / slippage_pct=0.001`）

`old = 1.002·A`；`new = A + max(0.0003A, 5) + 0.001A`

| 区间 | 条件 | 差异 | 结论 |
|------|------|------|------|
| A < 5000 | 最低佣金主导（`new = 1.001A + 5`） | `new − old = 5 − 0.001A > 0` | **旧口径偏松**（小额单可能放行到执行端才失败）→ 修复后更严，属正确收敛 |
| 5000 ≤ A ≤ 16666.67 | `new = 1.001A + 5` | `new − old = 5 − 0.001A ≤ 0` | 修复后略宽松（≤5 元） |
| A > 16666.67 | 比例佣金主导（`new = 1.0013A`） | `new − old = −0.0007A` | 修复后宽松 0.07% |

> 零点：`A = 5000`（口径反转点）、`A = 16666.67`（`cmin` 让位于比例佣金）。

### 9.3 golden 影响评估与冲突升级

- 既有 18 golden 的资金为 `10_000_000`、标的价 10-40 元 → 单笔 `A` 量级 ≫ 16666.67 → 落在「修复后宽松 0.07%」带；**仅在现金恰好落在 `[new, old)` 的 0.07% 窗口内才会改变成交结果**；
- **T7 第一步**必须跑 `pytest -q -k golden` 并记录读数：
  - 全绿 → 继续（D10 满足）；
  - 有变更 → **停止**，登记 `U-P059-8` 交由用户裁决（不得自行重录基线，D10 + RULE-1）。

### 9.4 回归锁（S09）—— **Step 4 回写：断言机制改为现金边界行为矩阵**

`test_p059_g4_cash_parity.py`：构造同一笔小额单（`A = 100 股 × 10.00 = 1000 元`），分别在「队列路径」（`enable_pending_orders=True`）与「次日路径」（涨停拒单 → `_next_day_orders`）下运行，以**现金边界处的 fill/no-fill 对称性**断言两路径口径一致（引擎两路径均不暴露 `required_cash`：队列路径仅 warning 日志 [L913-918](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L913-L918)，次日路径 [L1275-1277](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1275-L1277) 静默 append；trace 的 `filled` 桶可观测）：

| 现金 | 旧口径（`1002.00`） | 新口径（`1006.00`） | 修复后期望（两路径一致） |
|------|--------------------|--------------------|--------------------------|
| `1004.00` | 队列拒 / **次日成交**（不对称 = 红） | **双拒**（对称） | 双拒 + 订单 `retry` |
| `1010.00` | 双成交 | 双成交 | 双成交，qty 相同 |

红绿证据：修复前 `(1004, nextday)` 成交而 `(1004, queue)` 拒绝（口径分裂可见）；修复后两路径在两个现金档位行为完全对称。

---

## 10. 能力边界声明（S13 / D7 / D8）

`tests/_scenarios_capability.py` 定义（机器可读，`verify_scenario.py --boundaries` 输出 JSON）：

| key | 声明 |
|-----|------|
| `timeframe` | `daily`（不含分钟 / tick） |
| `intraday_auction` | `not_modeled`（不含集合竞价撮合） |
| `intraday_halt` | `not_modeled`（深交所退市整理首日 ±30%/±60% 盘中临停不建模） |
| `delist_period_no_limit` | `not_modeled`（退市整理期首日不设涨跌幅不建模，`delist_start_date` 零消费，见 F-S2-P059-7） |
| `expiry_basis` | `calendar_day`（次日订单过期按自然日，`max_pending_days_buy=5 / sell=10`） |
| `alpha_claim` | `none`（不证明策略收益 / 统计显著性；PBO / Deflated Sharpe 见 RESEARCH X8） |
| `execution_price` | `next_open`（队列与次日路径均按次日开盘价） |
| `limit_price_rounding` | `none`（限价按浮点直接乘，不做 0.01 分位舍入；见 E01） |

`assert_capability_declared()` 断言：键集合 **完全等于** 上述 8 项（多/少均失败），值非空。

---

## 11. 接入规范（O5，≤3 行）

新增模块要挂验证，只需在 [tests/_scenarios_cases.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_cases.py) 注册表加一条：

```python
SCENARIOS["S15"] = ScenarioSpec(
    scenario_id="S15", title="…", layer="L4", gaps=("G…",), dates=…, codes=…, close=…,
    config={…}, expected=ExpectedBlock(fills=(…,), final_cash=…, final_nav=…),
    metamorphic=(Metamorphic.r2_inert(code="000002"),),
)
```

测试侧 `test_p059_scenarios.py` 通过 `parametrize(list(SCENARIOS.values()))` **自动拾取**（0 行改动），CLI 同步可见。**验收证据**：新增场景后 `pytest -q -k p059` 用例数 +1 且 `verify_scenario.py --list` 出现该 ID。

---

## 12. 不变式映射

> **Step 8 回写（F-S8-P059-4）**: RESEARCH §8 的 **I1-I12** 与本表 **I1-I13 同号不同义**（P-047 O-S8-P047-1 同型）：RESEARCH I2=「零行为 846 全绿」（本表无对应行，由 E1 全量门禁承载）、RESEARCH I7=「价格合法**且整手**」（本表 I7 仅价格带，整手由 `build_target_positions(round_lot)` 承载）、本表新增 I13；RESEARCH I1 出口 `test_scenario_determinism` 未单列（见 I1 行）。C 组/CHECKLIST 一律锚定**本表口径**。

| 不变式 | 主责 | 落点 |
|--------|------|------|
| I1 确定性 | 场景层 | 闭式期望逐日全等（隐式钉死确定性）；独立双跑测试未单列（**Step 6 回写** F-S6-P059-7） |
| I2 账目恒等 | `core/invariants.py` | 运行期 `check_all`（场景不重复） |
| I3 trace off 零行为 | 场景层 | proxy 不 attach + 组件 `is` 断言 |
| I4 订单三态完备 | 断言 | `assert_order_states_closed` |
| I5 掩码一致 | 断言 | `assert_mask_semantics` |
| I6 现金非负 | 断言 | `assert_cash_non_negative` |
| I7 价格合法 | 断言 | `assert_price_legal`（限价由 `limit_rules` 计算） |
| I8 18 golden 零重录 | 门禁 | `pytest -k golden` |
| I9 R1 价格缩放 | 变质 | `assert_metamorphic_scale` |
| I10 R2 惰性标的 | 变质 | `assert_metamorphic_inert` |
| I11 R3 日期平移 | 变质 | `assert_metamorphic_shift` |
| I12 脏数据显式失败 | 断言 | `assert_dirty_input_raises` |
| **I13**（新）**桶数 == 交易日数且日期递增** | trace | `assert_trace_shape` |

---

## 13. 门禁与 CI（不新增 CI 命令）

| 门禁 | 命令 | 本批期望 |
|------|------|----------|
| 全量 | `MPLBACKEND=Agg python -m pytest -q` | 846 → **846 + 新增**（S01-S14 + R1-R3 + G4 对拍，预期 +18~21） |
| golden | `pytest -q -k golden` | 18 不变（D10） |
| 格式 | `black --check .`（`line-length = 100`） | 新增文件全部 unchanged |
| 类型 | mypy 生产面（**不含 `tests/`**） | CI 命令含 `scripts`（[tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46)）→ **109 → 110 files**，0 issue 维持（**Step 4 回写订正**） |
| AST 等价 | 生产面 22 文件（**ad-hoc，非常驻 CI**） | **Step 4 澄清**：AST 等价为批次内复核实践（P-029 口径；`scripts 2` = `record_golden` / `prepare_test_fixture`，`verify_scenario.py` 不在清单）；G4 → 该项预期变化，IMPL 须给出「行为修复豁免说明」+ docstring 订正的第二条豁免 |
| uv 锁 | `uv lock --check` | 0 变更（零新依赖） |

> **AST 门禁说明**：AST 等价用于「重构不得改行为」；G4 是**有意的行为修复**，故 IMPL 须显式声明「AST 差异 = 1 文件 1 语句块，理由 = D2」，并在 Step 6/8 核对。

---

## 14. 风险与回滚

| # | 风险 | 缓解 |
|---|------|------|
| R1 | proxy 透传不全导致 `AttributeError` | 一律 `__getattr__` 委托 + 全量回归（846 若红即暴露） |
| R2 | 日分桶错位（结算路径二次 `update_market_values`） | 幂等合并 + **I13** 桶数断言 |
| R3 | 闭式期望手算出错 | 每个数字在 IMPL 中给算式（如 S09 的 `1006.00`）；失败时先核 spec 再核引擎 |
| R4 | G4 修复意外改变 golden | §9.3 第一步验 golden，冲突则升级 `U-P059-8`，**不自行重录** |
| R5 | 场景码体积膨胀 | 场景只声明数据与期望，禁止 `if/else` 流程分支；Code Review 把关 |
| R6 | E02/E03 依赖状态边界假设 | 标注 `@pytest.mark.skip` 条件与原因，不硬凑 |
| 回滚 | G4 单点回滚 | 恢复 L1274 一行；其余全在 `tests/` + `scripts/`，删除即回滚 |

---

## 15. DoD（Step 9 验收口径）

| # | 条目 | 证据 |
|---|------|------|
| A1 | `SCENARIOS` 注册 **17** 条（14 必做 + 3 扩展），层覆盖 **7/7** | `verify_scenario.py --list` + 计数脚本 |
| A2 | 每条场景**闭式期望非空**且无「跑后录制」 | `test_p059_scenarios.py` 首行断言 |
| A3 | 每条场景 `len(metamorphic) >= 1` | 同上 |
| A4 | trace 字段集合 == §4.3 固定 **10** 键（`buyable`/`sellable` 分行；**Step 5 回写**：原文「9 键」为计数笔误）；`reason` 闭集 | `assert_trace_shape` / `assert_reasons_closed` |
| A5 | trace off → 组件 `is` 原生实例 | `test_trace_off_noop` |
| A6 | **G4 修复**且两路径在现金边界档位（1004/1010）行为对称（S09 红→绿，§9.4 矩阵） | `test_p059_g4_cash_parity.py` |
| A7 | 18 golden 零重录 | `pytest -k golden` = 18 passed |
| A8 | 全量 ≥ 864 passed（846 + 18） | `pytest -q` |
| A9 | black / mypy / uv 三绿 | 各自命令 |
| A10 | 能力边界 **8** 键齐备 | `--boundaries` |
| A11 | 接入规范 ≤3 行（新增场景验收） | IMPL 记录 + `--list` |
| A12 | 无 `core/` 变更除 G4 一处 | `git diff --stat` |

---

## 16. IMPL 任务映射（B1-B7 → T1-T9，Step 5 执行）

| T | 任务 | 产出 | 依赖 |
|---|------|------|------|
| T1 | `_scenarios_spec.py` + `_scenarios_builder.py` | 数据契约 + 唯一执行入口 | — |
| T2 | `_scenarios_trace.py`（含 I13） | proxy + 日分桶 | T1 |
| T3 | `_scenarios_assert.py` | 10 个断言原语 | T2 |
| T4 | `_scenarios_cases.py` S01-S08 | 8 例 | T1-T3 |
| T5 | `_scenarios_cases.py` S09-S14 | 6 例 | T4 |
| T6 | `_scenarios_capability.py` + `assert_capability_declared` | 边界声明 | T3 |
| T7 | **G4 修复**（L1274）+ 先验 golden | 1 处生产改动 + 红绿 | 独立 |
| T8 | `test_p059_*.py` 三文件 + `scripts/verify_scenario.py` | 测试 + CLI | T4-T7 |
| T9 | 扩展 E01-E03 + 全量门禁 + 接入规范文档（§11 实化）+ **`special_no_limit_mask` docstring 订正**（**Step 4 回写补行**：F-S2-P059-7/F-S3-P059-3 声明纳入本批；涉及生产面 `filter/limit_rules.py` → AST 第二条豁免） | 收尾 | T8 |

> T7 可**最早**执行（不依赖测试设施），但须先跑 golden 确认无漂移（§9.3）。

### 16.1 Step 5 执行回写（DeepSeek-V4.1-Flash，2026-11-19）

| T | 状态 | 证据 |
|---|------|------|
| T1 | ✅ | `tests/_scenarios_spec.py`（`ScenarioSpec` / `ExpectedBlock` / `Metamorphic` / 10 reason + 3 state + 10 桶键）、`tests/_scenarios_builder.py`（`build_scenario` 唯一入口） |
| T2 | ✅ | `tests/_scenarios_trace.py`（proxy `__getattr__` 透传 + `close_bucket` + `finalize`；`trace_enabled=False` 不 attach） |
| T3 | ✅ | `tests/_scenarios_assert.py`（10 个原语 + `assert_scenario` 组合入口 + `_match_fills` 双向精确匹配） |
| T4 | ✅ | `_scenarios_cases.py` S01-S08 |
| T5 | ✅ | `_scenarios_cases.py` S09-S14 |
| T6 | ✅ | `_scenarios_capability.py`（8 键）+ `assert_capability_declared` |
| T7 | ✅ | [engine_v2.py L1273-1284](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1273-L1284) 改用 `estimate_buy_cash`；golden 修复前 18 passed、修复后 18 passed（零漂移） |
| T8 | ✅ | `test_p059_scenarios.py`(39) / `test_p059_metamorphic.py`(16) / `test_p059_g4_cash_parity.py`(5) + `scripts/verify_scenario.py`（`--list/--scenario/--day/--json/--boundaries`） |
| T9 | ✅ | E01-E03 注册；[limit_rules.py L180-189](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L180-L189) docstring 订正（删除不存在的 `delist_start_date` 分支）；门禁见 PROGRESS §3.53.6 |

**IMPL 发现（F-S5-P059-1 ~ 8）**：

| # | 发现 | 处置 |
|---|------|------|
| 1 | §4.3 表为 **10** 键（`buyable`/`sellable` 分行），正文/A4 写「9 键」 | 实现按表取 10 键；A4 已订正 |
| 2 | S12 原前提（常量截面 → NaN 被 `exclude_na_factors` 排除）不成立：`_precompute_factors` 末尾 `.fillna(0)` | 改为「全标的停牌 → 无可交易集 → 早退无订单」，断言等价 |
| 3 | `special_no_limit_mask` 对「`list_date` 很早」的标的把窗口内**全部**前 5 日判为无涨跌幅；测试夹具自动补 `list_date=2000-01-03` 会让 S01 涨停失效 | `_write_fixtures` 仅在 `universe_extra` 非空（S06/S07）时写 universe 快照 |
| 4 | S02 真实行为：跌停日再平衡刷新先 `cancel_orders`、再因无可交易标的提前返回 → 旧卖单被取消且无新单，卖出自然后延一天 | 场景加惰性标的 B（权重 0）保持 `tradable_stocks` 非空，使 d2 重建卖单、d3 成交（保留「顺延重试」语义） |
| 5 | 订单终态若仅按 `(code, side)` 聚合，会把「旧单 dropped + 新单 filled」误判为同一单双终态 | trace 事件键扩为 `(code, side, create_date, quantity)` |
| 6 | `SCENARIOS` 原文按 dict 注册（§11 `SCENARIOS["S15"] = ...`），首版实现为 tuple | 改为 `dict[str, ScenarioSpec]`（插入序保持），测试/CLI 统一 `.values()` |
| 7 | G4 档位 1010 在**末日强平**后现金为 997.00（非买入后的 4.00） | 断言拆为「买入后现金 4.00」+「期末现金 997.00」 |
| 8 | `raises` 场景无 payload，被闭式期望检查误判 | `test_each_scenario_declares_closed_form` 对 `raises` 改为断言「期望块为空」 |

---

## 17. 零预填预留

### 17.1 Step 4 设计复审（GLM-5.3-Flash，2026-11-19）

> **复审者**: GLM-5.3-Flash（≠ 作者 DeepSeek-V4.1-Flash，RULE-5）。独立读码复核 DESIGN 引用的全部代码事实。

#### 17.1.1 设计决策逐项复核

| 决策 | 复核方式 | 结论 |
|------|----------|------|
| DD1 复用不新建 | Read `_synth_fixture.py` 全文 / `_golden_cases.py` | ✅ 复用点存在；`TOLERANCE` / `INITIAL_CAPITAL` 均为模块级公开常量 |
| DD2 扁平布局 | Glob `tests/__init__.py` → **不存在**；pyproject `python_files=["test_*.py"]`；`record_golden.py` L27-32 扁平导入 | ✅ 三项前提全部成立 |
| DD3 单一入口 | 设计层 | ✅ 与 golden 单一来源原则同构 |
| DD4 proxy 注入 | grep `self\.executor\|self\.tracker\|self\.optimizer` → **32 处全部为方法内局部绑定**（`xxx = self.executor` 形式，L481/540/573/619-620/673/770/849-850/962-963/1015-1016/1135/1227-1228/1307-1308），run() 期间每次方法调用重新绑定 | ✅ **setup() 后替换 `self.*` 完全有效**；唯一 setup 期调用 L303（sink）经 wrapper 委托保留。**补充纪律**：必须**包装**而非替换（否则丢失 L303 已设置的 error sink） |
| DD5 日分桶幂等合并 | Read L600-668 + grep `_force_liquidation` 调用点：**[L421](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L421) 以默认参数调用（`update_market_values=True`）→ 最后交易日发生二次盯市（L665-666 + L512）** | ✅ 幂等合并是**必需设计**（非防御性冗余）；`_settle_delisted` 路径 L720-725 显式传 False ✓ |
| DD6 变质关系 | 数学验算 | ✅ 三关系成立；R1 前提补一条（F-S4-P059-5） |

#### 17.1.2 G4 影响带数学验算（独立复算）

`old = 1.002A`；`new = A + max(0.0003A, 5) + 0.001A`：

| 区间 | `new − old` | DESIGN 表述 | 验算 |
|------|-------------|-------------|------|
| `A < 5000` | `5 − 0.001A > 0`（更严） | 「旧口径偏松」 | ✅ |
| `5000 ≤ A ≤ 16666.67` | `0.001A − 5 ≤ 0`（宽松 ≤5 元） | 「略宽松」 | ✅ 零点 `A = 5000` |
| `A > 16666.67` | `−0.0007A`（宽松 0.07%） | 「宽松 0.07%」 | ✅ 临界 `A = 16666.67`（`0.0003A = 5`） |

#### 17.1.3 场景与门禁核对

- **14 例层分布复算**: L1:2（S04/S11）/ L2:1（S12）/ L3:1（S10）/ L4:6（S01-S03/S05/S06/S08）/ L5:2（S07/S09）/ L6:1（S13）/ L7:1（S14）= **14 ✓，7 层全覆盖 ✓**；
- **能力边界 8 键计数** ✓；**A8 下界 846+18**（14 场景 + 3 变质 + 1 对拍）✓；
- **S05 日期约束** ✓（RULES L57-58：主板 ST 2026-07-06 起 10%）；**E01 无舍入** ✓（L170-176 直接浮点乘）。

#### 17.1.4 发现（F-S4-P059-1..5，1 P2 / 4 P3，0 P1）

| ID | 严重度 | 发现 | 处置 |
|----|--------|------|------|
| **F-S4-P059-1** | **P2** | **§16 任务映射缺「docstring 订正」任务**：F-S2-P059-7 / F-S3-P059-3 已声明「本批订正 `special_no_limit_mask` docstring」，但 T1-T9 无对应行；且 `filter/limit_rules.py` 属生产面 22 → 需 AST 第二条豁免 | **已回写**：并入 T9（补行） |
| F-S4-P059-2 | P3 | S09 原断言「两路径 `required_cash` 相等」**不可直接观测**（队列路径仅日志、次日路径静默 append）→ 改为现金边界行为矩阵（1004/1010 × 两路径） | **已回写**：§9.4 + A6 |
| F-S4-P059-3 | P3 | §13「mypy 109 files 不变」不准确：CI 命令含 `scripts`（tests.yml L46）→ `verify_scenario.py` 入扫，109 → **110** | **已回写**：§13 |
| F-S4-P059-4 | P3 | AST 等价**非常驻 CI 门禁**（tests/ 与 workflows 均无 `ast.parse`；系 P-029 批次内 ad-hoc 实践，口径 scripts 2 = `record_golden`/`prepare_test_fixture`）→ §13 表述澄清 | **已回写**：§13 |
| F-S4-P059-5 | P3 | R1 前提补「`k` 须远离整手 floor 边界」——`qty = floor(cash/(price×100))×100` 在边界翻转会使「持仓股数不变」断言误红（可检出、非假阳性，但属噪声） | **登记**，Step 5 实现时落 `_scenarios_assert.py` docstring |

#### 17.1.5 复审结论

**PASS**（0 P1 / 1 P2 / 4 P3）。六项设计决策全部经独立读码确认成立；G4 数学三区间 + 两零点验算正确；DD5 经 L421 调用点证实为必需设计。1 项 P2（任务映射缺行）已回写修复，4 项 P3 已回写或登记。**Step 5 可开工**（T1→T9，T7 可先行并首验 golden）。

### 17.2 Step 6 实现复审（GLM-5.3-Flash，2026-11-19）

> **复审者**: GLM-5.3-Flash（≠ 作者 DeepSeek-V4.1-Flash，RULE-5）。独立读码复核 T1-T9 全部产物 + 独立重跑门禁，不依赖 Step 5 自报。

#### 17.2.1 实现对齐核对（Step 6 Review 清单）

| 检查项 | 方式 | 结论 |
|--------|------|------|
| 实现与设计对齐 | 逐文件读 `_scenarios_{spec,trace,builder,assert,capability,cases}.py` / 3 测试 / CLI / engine_v2 G4 区 | ✅ 桶 10 键 / reason 10 项 / 订单态 3 项 / 能力 8 键与 §4/§10 一致；G4 与 §9.1 目标代码一致 |
| 依赖版本真实存在 | 全部 import 来自 stdlib + numpy/pandas + 仓内模块（`estimate_buy_cash` / `create_pending_order` / `build_limit_prices` 等均经读码确认存在） | ✅ 无虚构库/函数；零新三方依赖 |
| API 签名可实现 | `_next_day_orders` 条目结构 `{"order","create_date","create_date_index"}`（engine_v2 L1215-1217）与 `_inject_orders` 注入结构一致；`StopEngine.update` / `build_limit_prices` 调用签名核对 | ✅ |
| stdlib API 下限 | `dataclasses.asdict`（3.7+）、`math.isclose`（3.5+）、`str \| None`（PEP 604，`from __future__ import annotations` 下安全） | ✅ requires-python 下限内可用 |
| 低效操作排除 | `_match_fills` O(n²)（n ≤ 6，可接受）；trace `_cash_before` 每次排序桶键（桶 ≤ 7，可接受）；无其他热路径低效 | ✅ |
| 兼容性声明验证 | `trace_enabled=False` 保持原生组件（I3 测试实跑）✓；`SCENARIOS` dict 注册与 §11 接入规范一致 ✓ | ✅ |

#### 17.2.2 手算闭式值抽核（A2 反录制）

| 场景 | 手算复核 | 结论 |
|------|----------|------|
| S01/S05/S10/S14 整手股数 | `floor(w·100000·0.985/price/100)·100`：S01 4900（d0 价 10 创建、d2 @10 成交）；S05 4900（**d0 价 10 创建**，d1 @10.5 拒、d2 @10.5 成交——订单量按创建日价，非执行日价）；S10 7800；S14 3200 | ✅ |
| S02 NAV | 2000 + 9800×9 = 90200 ✓；R1(1.5) 变体 NAV 3000+9800×13.5 = 135300 = 90200×1.5 ✓ | ✅ |
| S06 IPO 窗口 | list_date=d0 → 无涨跌幅窗 d0-d4；d5 = 13×1.1 = 14.3 涨停 buyable=False ✓ | ✅ |
| G4 边界 | 1006 = 1000+max(0.3,5)+1 ✓；1010 档买入后 4.00、强平成本 7（5+1印花+1滑点）→ 期末 997.00 ✓ | ✅ |

#### 17.2.3 门禁独立复跑（全部实跑，非转录）

| 门禁 | 结果 |
|------|------|
| P-059 三模块 | **60 passed**（44.84s，复审修复后重跑） |
| golden | **18 passed, 888 deselected** |
| 全量 | **906 passed**（96.94s） |
| black | **119 files unchanged**（含 CLI 修复后复检） |
| mypy（CI 命令） | **110 source files, 0 issue** |
| uv lock --check | exit 0 |

#### 17.2.4 发现（F-S6-P059-1..7，0 P1 / 1 P2 / 6 P3）

| ID | 严重度 | 发现 | 处置 |
|----|--------|------|------|
| **F-S6-P059-1** | **P2** | `verify_scenario.py --json` **崩溃**：`_plain` 未转换 `ExpectedBlock.fills/order_states` 中的 dataclass（`FillExpectation`），`json.dumps` 抛 `TypeError: not JSON serializable`（实跑复现，exit 1）。Step 5 冒烟只测了非 `--json` 路径，漏检 | **复审中修复**：`_plain` 增加 dataclass → `dataclasses.asdict` 递归转换（兼处理 `set`）；修复后 `--scenario S02 --json` exit 0（输出含 fills/no_fill/order_states/nav_days/final_cash 全字段） |
| F-S6-P059-2 | P3 | `--boundaries` 输出人类可读文本，与 §10「`--boundaries` 输出 JSON」不符 | **复审中修复**：改为 `json.dumps(CAPABILITY_BOUNDARIES)` |
| F-S6-P059-3 | P3 | **A6「红→绿」缺红态实证**：§9.4 写明「修复前 (1004, nextday) 成交而 (1004, queue) 拒绝」，但 Step 5 仅记录 golden 前后对照，对拍测试未在旧口径下实跑 | **复审补证**：临时回滚 G4（`TEMP REVERT` 注释，`1.002` 近似）→ 对拍 **2 failed**（1004 档次日路径成交、与队列不对称 = 口径分裂可见）；恢复后哈希一致（SHA256 前 8 位 `434B8F16`）→ 60 passed。红→绿闭环完成 |
| F-S6-P059-4 | P3 | `assert_target_deviation`（§6 十原语之一，对应 G7）**已定义未被任何调用方接线**（`assert_scenario` 不含、测试/CLI 未用）——S08 的 T+1 语义实际由 `no_fill`/`fills` 锁定 | **登记不接线**（评审期不引入行为变化）；§6 补注「该原语为可选接线，当前场景由成交/挂单断言覆盖」 |
| F-S6-P059-5 | P3 | trace `_reject_reason` BUY 兜底分支**死代码**（L261-263：`if cash_short: return "cash_short"` 后无条件 `return "cash_short"`，两分支同值）；且 BUY retry 全检查通过时亦归因 `cash_short`（启发式兜底）。值均在闭集内，不影响断言 | **登记**（测试侧归因启发式，与 docstring「已知近似」同性质） |
| F-S6-P059-6 | P3 | trace `close_bucket` 幂等合并**不彻底**：末日 `_force_liquidation` 二次调用时 cash/nav/positions/filled 覆盖合并，但 `_active_prev` 循环会**重复追加** retry 事件与 `bucket["rejected"]` 条目（G4 parity 1004 档等末日仍有挂单的场景受影响）。当前断言均为集合/成员语义，不受影响；`--day` 输出可能出现重复条目 | **登记**（零生产影响；如后续 `--day` 用于人工核对再修） |
| F-S6-P059-7 | P3 | §12 I1「同 spec 连跑两次 trace 全等」**未落地为独立测试**：变质测试比较的是 base vs 变换体（I9-I11），非确定性双跑。实际行为由闭式期望逐日全等隐式钉死（非确定性会立刻红），但声明与实现存在措辞落差 | **已回写**：§12 I1 行改为「闭式期望逐日全等（隐式钉死）；独立双跑测试未单列」 |
| F-S6-P059-8 | P3 | §3.1/DD1 写「账目恒等仍由运行期 `check_all` 承担（**场景不重复实现**）」，但 `_scenarios_assert._assert_cash_identity` 实际做了**逐桶 cash+MV==nav 复核**（spec close 口径）——实现为增强而非矛盾，但与声明文字不符 | **已回写**：§3.1 补注「trace 侧另有逐桶复核（`cash_identity` 开关，默认开）」 |

#### 17.2.5 复审结论

**PASS**（0 P1 / 1 P2 / 7 P3）。实现与 DESIGN 全面对齐；全部手算闭式值经独立复算成立；六项门禁独立复跑全绿。唯一 P2（CLI `--json` 崩溃）已在复审中修复并重验；A6 红态证据已补齐（临时回滚实跑 2 failed → 恢复 → 全绿）。7 项 P3 中 2 项修复、3 项登记、2 项回写订正。**Step 7（CHECKLIST）可开工**。

### 17.3 Step 8 一致性复审（GLM-5.3-Flash，2026-11-19）

> **复审者**: GLM-5.3-Flash（≠ 作者 DeepSeek-V4.1-Flash，RULE-5）。对象：RESEARCH / DESIGN / CHECKLIST / PROGRESS 四文档 + 实现文件交叉核对；实施记录载体 = PROGRESS §3.53.6（本批无独立 IMPL 文档，§3.2 DD2 已声明扁平布局）。

#### 17.3.1 SPEC Step 8 清单逐项

| 项 | 方式 | 结论 |
|----|------|------|
| 四文档完稿后执行（禁止实现前预填） | 时序 | ✅ Step 8 于 Step 7 CHECKLIST 落盘后执行 |
| 派生需求登记 | 读 §16.1 / §17.2 | ✅ 实施期 16 项发现（F-S5-P059-1..8 / F-S6-P059-1..8）全部单独登记并留处置记录 |
| RESEARCH 结论在 DESIGN 中被使用 | D1-D11 → §2 / B1-B7 → §16 T1-T9 / G·BZ → §8 覆盖列 | ✅（覆盖列经 F-S8-P059-1 修复后真实对齐） |
| DESIGN 模块 ↔ 实施对应 | §3.2 六模块 + CLI ↔ PROGRESS §3.53.6 / 实现文件 | ✅ 一一对应 |
| 实施功能点 ↔ CHECKLIST 验收项 | T1-T9 → B 组 / DoD A1-A12 → A 组 / I1-I13 → C 组 / 17 场景 → D 组 | ✅ 无遗漏 |
| 无文档间矛盾 | 机械矩阵 + 逐节读 | ⚠️ 发现 4 项（17.3.2），已修复/回写 |
| 术语一致 | 关键值机械矩阵 | ✅ 10 键 / reason 10 / 三态 / 能力 8 键 / 17 条 / 60 / 906 / 110 全仓一致 |

**机械矩阵（RESEARCH/DESIGN/CHECKLIST/PROGRESS 命中数）**: `906` = 0/1/7/7；`110 files|source` = 0/2/2/3；`17 条` = 0/1/3/9；`61 项` = 0/0/1/1；`--dump` = 1/0/0/0（仅 RESEARCH，经 F-S8-P059-3 补声明）；`I1-I12` = 2/0/0/1 vs `I1-I13` = 0/0/3/1（同号不同义，经 F-S8-P059-4 补声明）。UPGRADE_MASTER_PLAN 增量 = P-059 注册行 + 关键路径 `→059→`，与 RESEARCH 执行序一致 ✓。

#### 17.3.2 发现（F-S8-P059-1..4，0 P1 / 1 P2 / 3 P3）

| ID | 严重度 | 发现 | 处置 |
|----|--------|------|------|
| **F-S8-P059-1** | **P2** | **场景 `gaps` 元组与 §8「覆盖」列系统性不一致**（17 条中 13 条不一致）：S11 脏数据挂 `G18/BZ16`（应为 BZ1/G10）、S12 挂 `G15/BZ15`、S13 止损挂 `G19/BZ17`（应为 BZ15/G17）、S14 空信号挂 `G14/BZ18`（应为 BZ6/G18）、E01 舍入挂 `G17`（应为 G6）、E02 长假挂 `G13`（应为 BZ18）、E03 复权挂 `G20`（应为 BZ12/G15）等——可追溯链（场景 → RESEARCH 缺口/盲区）断裂；`gaps` 无任何断言消费，故 60 项测试全绿未能暴露 | **双侧订正**：`_scenarios_cases.py` 17 处 `gaps` 按 §8 覆盖列重写（S08 的 X3 为外部规则锚不入场景码，取 G13）；§8.1 三行回写（S01 删 BZ7/G4 笔误——现金口径属 S09；S05 删 BZ11——无限制窗口属 S06；S12 随 F-S5-P059-2 前提失效改写为「全标的停牌」并改挂 BZ14/G9）。修复后 P-059 **60 passed**、black clean，无行为影响 |
| F-S8-P059-2 | P3 | RESEARCH S7 字面字段清单（`mask(buy,sell)` / `submitted` / `reason` 为独立项）与 §4.3 十键（拆分/聚合）存在差异且未声明 | **已回写**：§4.3 补注——语义等价（mask 拆 `buyable`/`sellable`、`submitted` 并入 `orders`、`reason` 并入 `rejected` 条目），以 §4.3 为实现真值 |
| F-S8-P059-3 | P3 | RESEARCH S11「**每个**场景须声明 ≥1 变质关系」被收窄为 backtest-only、RESEARCH B5 `--dump` 被 `--json`/`--day` 承载，两处收窄/更名均未声明 | **已回写**：§7.1 补注（raises/stops/limit_price 无 trace，变质关系不适用）；§3.2 文件树补注（`--dump` 由 `--json`/`--day` 承载） |
| F-S8-P059-4 | P3 | **RESEARCH §8 I1-I12 与 §12 I1-I13 同号不同义**（P-047 O-S8-P047-1 同型）：RESEARCH I2=「零行为 846 全绿」vs §12 I2=「账目恒等」；RESEARCH I7 含「整手」vs §12 I7 仅价格带（整手由 `build_target_positions(round_lot)` 承载）；§12 新增 I13；RESEARCH I1 出口 `test_scenario_determinism` 未单列（= F-S6-P059-7） | **已回写**：§12 补注（C 组/CHECKLIST 一律锚定 §12 口径）+ CHECKLIST §8.3 同步补注 |

#### 17.3.3 复审结论

**PASS**（0 P1 / 1 P2 / 3 P3）。四文档在关键值（17 / 60 / 906 / 110 / 61 / 10 键 / 8 能力键）上全仓一致；派生需求、追溯映射、模块对应、验收覆盖四条主线闭合。唯一 P2（gaps 可追溯链断裂）双侧订正并以 60 passed 复验；3 项 P3 全部回写为显式声明。**Step 9（CHECKLIST 回填）可开工**。

### 17.4 Step 10 终审

**2026-11-19，GLM-5.3-Flash**（与作者 DeepSeek-V4.1-Flash 异构成立，RULE-5；**U-P059-6 于此闭合**）。

#### 17.4.1 门禁独立复跑（不采信 Step 9 自报）

pytest **906 passed**（239 warnings, 102.18s）/ `-k golden` **18 passed, 888 deselected** / collect **60**（39+16+5）/ black **146**（core tests）· **215**（全仓）unchanged / mypy（CI 命令）**110 source files, 0 issue** / AST `except Exception` core 外 **22**（agents 11 / filter 5 / scripts 2 / batch_backtest 2 / strategy_evaluation 1 / cli 1）、core **29**、全扫 **55** / `tests/*.py` **104** / `uv lock --check` exit **0** / 工作区 **17 文件**（4 M + 13 ??，与 CHECKLIST F1 清单逐项一致）——与 Step 9 自报读数逐项一致。

#### 17.4.2 锚点核对与派生需求抽核

| 项 | 结果 |
|----|------|
| CHECKLIST F1/F2/F3 `[待 Step 10]` + §10 占位 | 在位 |
| 本文 §17.4 占位 | 在位（本节即回填产物） |
| `scripts/verify_scenario.py` L45 `dataclasses.asdict` | 在位（F-S6-P059-1 修复实证） |
| `_scenarios_cases.py` S11 `gaps=("BZ1","G10")` | 在位（F-S8-P059-1 双侧订正实证） |
| CHANGELOG 惯例 | `[Unreleased]` 每批次登记（P-011..P-047 全覆盖）→ P-059 增 Added 条目 |
| 遗留后台 diff（`core/stops.py` / `tests/test_p047_position_sizing.py`） | P-047 已入库内容陈旧输出，不在本批 17 文件，无需处理 |

#### 17.4.3 D8 / D9 提交记录

- **D8**（用户 AskUserQuestion 明确授权后执行）：commit **`4eed0fa`** `feat(P-059): 数据校验与边界场景库（17 场景 + 逐日 trace + 10 断言原语 + G4 修复）`，17 files **+3823/−7**；push `5f85363..4eed0fa`；CI run **44385648682** **四 job 全绿**（lock-check 8s / test 3.10 2m2s / 3.11 2m38s / 3.12 2m19s）。
- **D9**：CHECKLIST F1/F2/F3 ✅ + §10 终审小结 + §7 Step 10 行 + 状态头；PROGRESS §3.53.11；CHANGELOG P-059 Added 条目；关闭提交 `docs(P-059)` + push + CI 复验。

#### 17.4.4 终审结论

**PASS**：CHECKLIST **61/61 ✅ / 0 ❌ / 0 新发现**（无 P1/P2/P3）；门禁独立复跑与 Step 9 一致；全链锚点闭合。**批次 P-059 关闭**。遗留登记项 F-S6-P059-4 / -5 / -6 随台账跟踪，不在本批。
