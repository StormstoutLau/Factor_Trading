# DESIGN：P-051b 策略模板库（`strategies/` + registry 接线）

> **批次**: P-051b · **Step 3 设计** · 日期 2026-11-21
> **判档**: **T1**（新增 `strategies/` 包 6 文件 + `core/strategy.py` 两处 additive 扩展 + 测试；**不新增 golden**）
> **上游**: [RESEARCH_p051b](RESEARCH_p051b_strategy_templates.md)（§4 方案矩阵 / §5 模板规格 / §6 I1-I10 / §8 U-P051b-1..14 / §17 出口判定 / §18 三项缺口闭环）；[REVIEW_p051b_step2](REVIEW_p051b_step2_research.md)（**Step 2 通过：0 P1 + 4 P3**）；P-044 已关闭（Strategy / BacktestAdapter / registry）；P-045 已关闭（`core/stops.py` 止损状态机）；P-051a 已关闭（`core/volatility.py`）
> **代码证据时点**: HEAD `9c914df`（工作区仅 docs 新增）
> **基座**: DeepSeek-V4.1-Flash（Step 4 复审须异构 GLM-5.3-Flash）

---

## 0. Step 2 复审发现收敛表（设计前置）

| ID | 级别 | 复审发现 | 本设计裁决 | 落点 |
|----|------|----------|------------|------|
| **P3-1** | P3 | §18.1 A4-A6 探针证据为转录级、不可重放 | **采纳**：把「hash 仍 TypeError、不同实例 `==` 仍 ValueError、5 位置参数仍可用」写成正式 pytest 断言（V1/V2） | §4 V1-V2 |
| **P3-2** | P3 | `mean_reversion` / `ts_momentum` 只吃 history（≤t−1），相对 `next_open` 多滞后一 bar | **维持**：属**保守方向**，非缺陷。裁决为显式设计决策 **D8**：`prices` 只用于 `grid_atr`（当日价位）与 `trend_breakout`（当日收盘判定突破），其余一律用 `history`。登记理由：与 `apply_stops`（P-045）的「触发日收盘、次日成交」口径一致 | D8 / I3 |
| **P3-3** | P3 | `sign(0) → 0 票` 约定无覆盖用例 | **采纳**：新增 M3 边界用例（构造收益恰为 0 的标的） | §4 M3 |
| **P3-4** | P3 | 基线为 collect-only 复测，非全量实跑 | **采纳**：Step 9 门禁以实跑读数为准；本设计只登记目标值 | §7 |

### 0.1 对 RESEARCH 的订正（Step 8 回填）

| # | RESEARCH 原文 | 订正 | 理由 |
|---|---------------|------|------|
| **R-1** | §4 U-P051b-6：网格基准 = **首建仓日收盘** | **`base_price: Mapping[str, float]` 必填**（缺省/空 → `StrategyConfigError`） | **`BacktestAdapter` 无 extras 回写通道**（实证：[strategy.py L254-258](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L254-L258) `extras=dict(state.extras)` 原样复制，策略无法写入）→ 「首建仓日收盘」不可实现而不改 P-044 契约。**Step 4 F-D2 修复 c**：原「缺省窗口首值」是每日重锚的滚动基准，恰为 U-P051b-6 明确要避免的语义 → 改为必填显式参数，固定基准可达且无歧义 | D9 / Rk-2 |
| **R-2** | §5 `trend_breakout` 参数含 `atr_period(14)` | **删除该参数** | 趋势模板算法（突破 + MA）不使用 ATR；保留会在 `param_schema` 中留死参数，违反 I4「schema 与构造参数一一对应」 | D6 |
| **R-3** | §5 `mean_reversion` 参数含 `max_hold_days(10)`；`grid_atr` 含 `stop_loss_pct` 兜底 | **移出模板参数**，改为回测流程层调用 `core.stops.apply_stops` | P-045 已交付矩阵级止损/止盈/时间止损（`StopConfig.stop_loss_pct` / `time_stop_days`），模板内重复实现会产生**双层止损**（同 P-051a F-R5 的乘积杠杆问题）。样例值等价：`max_hold_days=10` ↔ `StopConfig(time_stop_days=10)`；`stop_loss_pct=0.20` ↔ `StopConfig(stop_loss_pct=0.20)` | D7 / I9 |

### 0.2 新增未决项

| ID | 未决 | 备选 | 推荐 |
|----|------|------|------|
| **U-P051b-15** | `BacktestAdapter` 是否增加策略状态回写通道（extras） | 本批不改 / 增 duck-typed `take_extras()` 钩子 / 改 `generate_signals` 返回 tuple | **本批不改**（登记给 P-051c：多策略虚拟子账户需要持仓级状态时一并设计；本批四模板经 D9 证明无需回写） |

### 0.3 Step 4 复审发现收敛表（2 P1 + 1 P2 + 8 P3）

| ID | 级别 | 复审发现 | 收敛动作 | 落点 |
|----|------|----------|----------|------|
| **F-D1** | **P1** | `ts_momentum` 伪码 `iloc[-1-lb]` 实读 `t−1−lb`，与 §18.3.1 样例锚点 `P(t−lb)` 错位 1 bar | **修复 b（用户裁定）**：伪码改 `iloc[-lb]`；`min_rows` 恢复 `max(lookbacks)`；**撤销 R-4**；M8 改为「行数 = `max(lookbacks) − 1` → fail」 | D4.1 / M8 |
| **F-D2** | **P1** | `grid_atr` 默认基准 = `history["close"].iloc[0]`（每日滚动），恰为 U-P051b-6 要避免的语义 | **修复 c（用户裁定）**：`base_price` 必填；缺省/空 → `StrategyConfigError`；样例改显式传参；G4 改缺省 fail-fast、G5 改缺键行为 | D4.4 / G4-G5 |
| **F-D3** | P2 | `trend_breakout` 的 upper/lower/ma 走隐式 skipna，NaN 政策未定 | 伪码显式 `skipna=False`；未持仓 NaN → 不入选；持仓且 `lower` NaN → 保持（不误清仓） | D4.3 / D10 |
| F-D4 | P3 | D4.2 文字「不出场」与伪码矛盾 | 文字改「未持仓不入场；已持仓出场」；R6 补持仓分支 | D4.2 / R6 |
| F-D5 | P3 | I6「未 import 时无模板」不可测 | 改为「未注册 id → `get()` 返回 `None`；import 后四个 id 可取」 | I6 |
| F-D6 | P3 | `atr_period + 1` 比最小必要多 1 行 | 注记「保守无害」，不改公式 | D4.4 |
| F-D7 | P3 | `state.positions` 为目标权重而非实际持仓 | D9 加语义注记（P-044 契约边界，差异由 sizing/stop 层兜底） | D9 |
| F-D8 | P3 | 「iloc 切片为视图」pandas 不作保证 | 措辞改「copy/view 由 pandas 决定；只读使用行为一致」 | D3 |
| F-D9 | P3 | D11 写 ~1082，与 §5/§7 的 1087 不一致 | 统一为 **1088**（G 组 +1 后重算） | D11 / §5 / §7 |
| F-D10 | P3 | C2「`factory(None)` 与 `{"levels":2}` 三形态等价」不成立 | 改「`dict` 形态与 `**overrides` 形态等价；`None` 为全默认」 | C2 |
| F-D11 | P3 | V6 未注明 `returns_window` 前提 | 补前提 `returns_window = history_window = W` | V6 |

---

## 1. 范围与前置

### 1.1 做

| # | 内容 | 落点 |
|---|------|------|
| 1 | `core/strategy.py`：`MarketView` 末位加 `history: Optional[dict[str, pd.DataFrame]] = None`；`views_from_data` 加 `history_window: int = 0` | D2 |
| 2 | 新建 `strategies/`：`base.py` / `grid.py` / `trend.py` / `momentum.py` / `mean_reversion.py` / `__init__.py` | D1 |
| 3 | 四模板实现 `Strategy` Protocol + `@register_strategy` | D4 / D6 |
| 4 | 端到端接线测试：`views_from_data(history_window>0)` → `signals_frame` → `set_signal(mode="weights")` → `run()` | §4 E 组 |
| 5 | CI/本地门禁扩围：mypy 加 `strategies`、black 加 `strategies` | D11 |
| 6 | 四文档 + 台账 | §7 |

### 1.2 不做

- 生命周期 / 晋级门 / 多策略虚拟子账户（P-051c）；
- 截面多空、股指期货对冲、月差套利；
- 参数自动寻优（`batch_backtest.run_param_grid` 已有）；
- LLM / agent 策略生成（U-P051b-7 已裁决：另立批次）；
- Fin_Agent Guru 接入（U-P051b-12）、研报/KOL（U-P051b-13）、预测市场（U-P051b-14）；
- 改 `BacktestAdapter` 的状态演进逻辑（U-P051b-15）；
- 改 `core/sizing.py` / `core/engine_v2.py` / `core/stops.py` 任何一行；
- 改 `core/strategy.py` 既有 5 字段的语义与顺序（只追加末位可选字段）；
- 新增 golden 或重录既有 22 条（I8）。

### 1.3 前置事实（@`9c914df`，实读）

| # | 事实 | 证据 |
|---|------|------|
| P1 | `MarketView` 5 字段 frozen dataclass，全仓仅 3 处构造且**全为关键字**（生产 1 + 测试 2） | [strategy.py L111-120](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L111-L120)；grep 复验 |
| P2 | `views_from_data` 的 `returns` 窗口为 `iloc[i-W:i]`（**不含当日**） | [strategy.py L299-300](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L299-L300) |
| P3 | `BacktestAdapter.signals_frame` 的 state 演进 `extras=dict(state.extras)`，**策略无回写通道** | [strategy.py L254-258](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L254-L258) |
| P4 | `IDataManager.get_adj_price` 支持 `open/high/low/close` × `raw/hfq/qfq` | [interfaces.py L107-119](file:///f:/Coding/Factor_Trading_v3.0/core/interfaces.py#L107-L119) |
| P5 | `core.stops` 已交付 `StopEngine` / `StopState`（JSON 安全）/ `ohlc_from_data` / `apply_stops` | [stops.py L116-263](file:///f:/Coding/Factor_Trading_v3.0/core/stops.py#L116-L263) |
| P6 | `core.volatility.atr` 为标准 Wilder（seed 在 `period-1`，前 `period-1` 个 NaN，`skipna=False`） | [volatility.py L60-90](file:///f:/Coding/Factor_Trading_v3.0/core/volatility.py#L60-L90) |
| P7 | CI mypy 范围**不含** `strategies`；无 black job | [tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46) |
| P8 | 测试夹具支持独立 `high_prices` / `low_prices` | [_synth_fixture.py L38-71](file:///f:/Coding/Factor_Trading_v3.0/tests/_synth_fixture.py#L38-L71) |
| P9 | 基线：pytest **1040** / `-k golden` **22** / mypy **113 files** / black `core tests` **157** | Step 2 复审 V7 独立复测 |

---

## 2. 架构设计

### 2.1 模块划分（D1）

| 模块 | 职责 | 依赖 |
|------|------|------|
| `core/strategy.py`（改） | `MarketView.history` 契约 + `views_from_data(history_window)` | 既有（pandas / `IDataManager`） |
| `strategies/base.py`（新） | 公共工具：`require_history()` / `equal_weight()` / `scale_to_one()` / `StrategyConfigError` | `pandas` / `core.strategy` |
| `strategies/grid.py` | `GridATRStrategy` + `GridATRConfig` | `base` / `core.volatility.atr` |
| `strategies/trend.py` | `TrendBreakoutStrategy` + `TrendBreakoutConfig` | `base` |
| `strategies/momentum.py` | `TSMomentumStrategy` + `TSMomentumConfig` | `base` |
| `strategies/mean_reversion.py` | `MeanReversionStrategy` + `MeanReversionConfig` | `base` |
| `strategies/__init__.py` | 集中 import 触发注册 + `__all__` | 四个模板模块 |

**为什么放 `strategies/` 而不是 `core/`**：模板是**消费方**（依赖 `core.strategy` 契约），放在 `core/` 会造成 core → 消费方的反向依赖；且 `strategies/` 与既有 `strategy_evaluation/` 语义正交（后者是**评估**，前者是**生成信号**），目录名不冲突。

### 2.2 数据流

```
dm (IDataManager)
  └─ BacktestAdapter.views_from_data(dm, signal, tradable, history_window=W)
        └─ 逐日 MarketView(date, signal, tradable, prices, returns, history)
              └─ strategy.generate_signals(view, state) -> TargetWeights
                    └─ signals_frame(views) -> DataFrame(dates × codes)
                          └─ engine.set_signal(frame, mode="weights")
                                └─ run()
```

### 2.3 控制流与注册

1. `import strategies` → `strategies/__init__.py` 依次 import 四个模块 → 各模块内 `@register_strategy("grid_atr")` 等装饰器执行 → `get_strategy_registry()` 填充。
2. `get_strategy_registry().get("grid_atr")` → `factory(config, **overrides)` → 策略实例。
3. 注册顺序：`grid → trend → momentum → mean_reversion`（`__init__.py` 显式 import 顺序即注册顺序；因 id 唯一，顺序不影响语义，仅影响 `list()` 输出顺序——登记为可观测但无语义）。

---

## 3. 接口定义

### 3.1 `MarketView`（D2）

```python
@dataclass(frozen=True)
class MarketView:
    date: pd.Timestamp
    signal: pd.Series
    tradable: pd.Series
    prices: pd.Series
    returns: Optional[pd.DataFrame]
    history: Optional[dict[str, pd.DataFrame]] = None   # ← 新增，末位带默认
```

**契约（九条款，承 §18.2）**：

| 项 | 定稿 |
|----|------|
| 字段 | 第 6 位，`Optional[dict[str, pd.DataFrame]] = None` |
| 键 | `"close"` / `"high"` / `"low"`（不含 `open` / `volume`） |
| 行 | 严格 `[t−W, t−1]`，共 W 行，**不含当日 t** |
| 列 | 全量 `dm.stock_codes` |
| 索引 | `DatetimeIndex`，取自 `dm.trade_dates` 连续切片 |
| 口径 | `dm.get_adj_price(field, "raw")`（与 `prices` 同源） |
| 默认 | `history_window=0` → `history=None`（零行为变更） |
| 关闭态 | `i < W` 或 `W <= 0` → `None`（镜像 `returns` 的逐日语义） |
| 扩展 | 新增键（如 `volume`）不改签名 |

### 3.2 `views_from_data` 扩展

```python
@staticmethod
def views_from_data(
    dm: "IDataManager",
    signal: pd.DataFrame,
    tradable: Optional[pd.DataFrame] = None,
    returns_window: int = 0,
    history_window: int = 0,          # ← 新增
) -> list[MarketView]:
```

- `history_window <= 0` → 不加载任何价格面板（**零 I/O 增量**）；
- `history_window > 0` → 一次加载 `close/high/low` 三张 `raw` 面板，逐日切 `iloc[i-W:i]`；
- `i < history_window` → `history=None`；
- 三张面板先 `reindex(index=dates, columns=dm.stock_codes)`，保证列集与索引对齐（与 `aligned` 同源）；
- 切片与 `returns` **同窗**：`history[k] = panel.iloc[i-W:i]`，`returns = returns_matrix.iloc[i-W:i]`，两者 `index` 逐值相等（可断言）。

### 3.3 公共工具（`strategies/base.py`）

```python
class StrategyConfigError(ValueError):
    """模板参数或视图契约不满足（fail-fast，不静默降级）。"""

def require_history(view: MarketView, min_rows: int, *, name: str) -> dict[str, pd.DataFrame]:
    """校验并返回 history；缺失或行数不足 → StrategyConfigError。"""

def require_keys(history: Mapping[str, pd.DataFrame], keys: Sequence[str], *, name: str) -> None:
    """校验 history 键集；缺键 → StrategyConfigError。"""

def equal_weight(codes: Sequence[str]) -> pd.Series:
    """等权 1/n（n=0 → 空 Series，dtype=float）。"""

def scale_to_one(weights: pd.Series) -> pd.Series:
    """行和 > 1 时按 1/sum 缩放；非负校验；和 ≤ 1+1e-12 保证。"""
```

### 3.4 工厂与注册（D6）

```python
@register_strategy(
    "grid_atr",
    description="网格（ATR 间距）",
    config_schema={"grid_k": "float", "levels": "int", "atr_period": "int", "base_price": "dict (required)"},
)
def grid_atr_factory(
    config: Mapping[str, Any] | None = None, **overrides: Any
) -> GridATRStrategy: ...
```

- `config is None` → 全默认；`config` 为 `Mapping` → 展开；`**overrides` 覆盖；
- 未知键 → `StrategyConfigError`（fail-fast，不静默忽略）；
- `param_schema` 由 `dataclasses.asdict(config)` 生成（I4：schema ↔ 构造参数一一对应）。

---

## 4. 设计决策

### D2 `MarketView.history`（承 §3.1）

已定稿见 §3.1。**additive 论证**（承 §18.1 + 复审 P3-1）：

- 全仓 3 处构造均关键字 → 加末位默认字段不破坏；
- `hash(view)` 加字段前后均 `TypeError`（`pd.Series.__hash__ is None`）；
- 不同实例 `==` 加字段前后均 `ValueError`（Series 逐元素比较歧义）；
- `runtime_checkable` 仅检查方法存在性，与字段数无关；
- 唯一可观测差异：`dataclasses.fields()` 5→6，全仓无消费方（grep 0 命中）。

### D3 `history` 构造（性能与内存）

- 3 次 `get_adj_price`（内部有缓存），不在循环内重复调用；
- 逐日 `iloc[i-W:i]` 产生 3 字段 × N 日 = 3N 个轻量 DataFrame（copy/view 由 pandas 决定；模板只读使用，两种情况行为一致）；
- `history_window=0`（默认）→ 零额外调用、零额外对象；
- 不做「按需键」优化（如 `history_keys` 参数）：四模板键需求已覆盖 close/high/low，且 `grid` 需要三键，过早优化无收益。

### D4 四模板算法（精确规格）

**通用**：决策日 t；`history` 为 `[t−W, t−1]`；`prices` 为当日收盘；输出 `pd.Series(index=codes, dtype=float)`，非负，和 ≤ 1。

#### D4.1 `ts_momentum`（`TSMomentumConfig(lookbacks=(20,60,120), min_votes=2)`）

```
hist = require_history(view, max(lookbacks), name="ts_momentum")["close"]
p_now = hist.iloc[-1]                        # t−1
votes = sum over lb in lookbacks: sign(p_now / hist.iloc[-lb] - 1)   # +1/0/−1
selected = [code for code in columns if votes[code] >= min_votes]
return equal_weight(selected)
```

- `sign(0) → 0`（不含持平，P3-3 用例 M3）；
- 需求行数 `max(lookbacks)`：W 行窗口索引 `0..W−1` 对应 `t−W..t−1`；`iloc[-lb]` 在 `W = max(lookbacks)` 时恰为 `t−lb`（如 `lb=120, W=120 → iloc[0] = t−120`），与 §18.3.1 样例锚点 `P(t−lb)` 逐点吻合；
- **R-4 已撤销**（Step 4 F-D1 修复 b）：原「需 `max(lookbacks)+1`」的订正不成立——那是 `iloc[-1-lb]` 口径下的结论；改 `iloc[-lb]` 后 `max(lookbacks)` 行恰好够用，RESEARCH §18.2 已恢复原式。

#### D4.2 `mean_reversion`（`MeanReversionConfig(lookback=20, z_entry=2.0, z_exit=0.5)`）

```
hist = require_history(view, lookback, name="mean_reversion")["close"]
window = hist.iloc[-lookback:]               # [t−lookback, t−1]
z = (window.iloc[-1] - window.mean()) / window.std(ddof=1)
for code:
    holding = state.positions.get(code, 0.0) > 0
    if holding:   keep if z[code] < -z_exit else exit
    else:         enter if z[code] <= -z_entry
```

- `std(ddof=1)`（pandas 默认，§18.3.2 已声明）；`std == 0` → z 记 0：**未持仓 → 不入场；已持仓 → 出场**（无偏离即回归完成，离场）；
- 持仓中且 `z` 继续低于 `−z_entry` → **继续持有，不加仓**（无状态，无金字塔，D9）；
- 时间止损**不在模板内**（R-3）→ 由 `apply_stops(StopConfig(time_stop_days=...))` 承担。

#### D4.3 `trend_breakout`（`TrendBreakoutConfig(entry_n=20, exit_n=10, ma_n=60)`）

```
h = require_history(view, max(ma_n, entry_n, exit_n), name="trend_breakout")
close_t = view.prices                              # 当日收盘（decide-at-close）
upper = h["high"].iloc[-entry_n:].max(skipna=False)  # max over [t−entry_n, t−1]
lower = h["low"].iloc[-exit_n:].min(skipna=False)    # min over [t−exit_n, t−1]
ma = h["close"].iloc[-ma_n:].mean(skipna=False)
for code:
    if holding:
        if isnan(lower[code]): keep                # NaN 不误清仓
        else:                  keep if close_t >= lower else exit
    else:
        if isnan(upper[code]) or isnan(ma[code]): skip   # 窗口不完整不入选
        else: enter if (close_t > upper) and (close_t > ma)
```

- **两个条件必须同时满足**（T2 反伪通过用例）；
- `upper` / `lower` 含 t−1，不含 t；`close_t` 为当日 → 无前视（决策在收盘后，成交次日开盘）；
- **NaN 政策（Step 4 F-D3）**：`skipna=False` 显式声明「窗口不完整即不可判定」；未持仓标的不入选（避免基于缺失窗口伪突破），已持仓标的 `lower` 为 NaN 时**保持**（避免 NaN 误清仓）。

#### D4.4 `grid_atr`（`GridATRConfig(grid_k=1.0, levels=3, atr_period=14, base_price=<必填>)`）

```
h = require_history(view, atr_period + 1, name="grid_atr")
atr = core.volatility.atr(h["high"], h["low"], h["close"], period=atr_period).iloc[-1]
base = base_price                            # 必填（Mapping[str, float]）
s = grid_k * atr                             # 每标的间距
j = floor((base - view.prices) / s)          # 逐标的
raw_weight = clip(j, 0, levels) / levels
return scale_to_one(raw_weight)              # 和多于 1 时缩放
```

- **`base_price` 必填**（`Mapping[str, float]`）：网格基准是策略语义的一部分，不做隐式默认 → 缺省 / 空映射 → `StrategyConfigError`（Step 4 F-D2 修复 c）；
- `atr <= 0` 或 NaN → 该标的权重 0（跳过，不 fail 全表）；
- `s <= 0` → 同上；
- `base_price` 缺某标的键 → 该标的权重 0（与 ATR NaN 同策略）；
- `levels >= 1`，`grid_k > 0`，`atr_period >= 2`（构造期校验）；
- `atr_period + 1` 行比最小必要（`atr_period` 行，seed 在 `iloc[period−1]`）多 1 行，**保守无害**（F-D6）。

### D5 权重归一与约束（I1）

- 等权模板：`1/n`（n=0 → 空 Series）；
- `grid_atr`：`clip(j,0,levels)/levels` 后 `scale_to_one`；
- 统一出口 `scale_to_one`：`sum > 1.0 → × (1.0/sum)`；`sum <= 1.0` 原样；**不做**向上归一（保持「空仓是合法输出」）；
- 非负由构造保证（`clip(...,0,...)` + `1/n>0`）；
- 浮点相容（复审 V-质疑 3）：n=3 时 `3×(1/3)` 精确收敛 1.0；任意 n 误差 ≤ ~1e-13 ≪ `1e-9`。

### D6 工厂签名与 `param_schema`（U-P051b-4 落地）

- 签名 `(config: Mapping[str, Any] | None = None, **overrides: Any) -> Strategy`；
- `config` 为 `frozen dataclass` 的 `dict` 形式；`overrides` 逐键覆盖；
- 未知键 → `StrategyConfigError`；
- `meta.param_schema = asdict(config)`（含全部默认值，可复核）；
- `meta.code_hash = code_hash(type(self))`（P-044 既有，12 hex）。

> **注**：四模板**不使用** `optimizer`（与 `FactorSignalStrategy` 不同），因模板直接产权重。`meta.param_schema` 因此不含 `optimizer` 键。

### D7 止损 / 时间止损归属（R-3）

| 需求 | 归属 | 调用方式 |
|------|------|----------|
| 模板入场/出场逻辑 | 模板 | `generate_signals` |
| 硬止损 / 移动止损 / 止盈 / 时间止损 | `core.stops.apply_stops`（P-045） | `apply_stops(signals_frame, ohlc_from_data(dm), StopConfig(...))` |
| 组合波动目标 | 引擎 sizing（P-051a） | `BacktestConfig.sizing` |

**为什么模板不内建**：模板逐日无状态，无法维护 `entry_price` / `peak_price` / `bar_count`；`apply_stops` 已在矩阵层实现这些量的演进，重复实现会产生**两层止损叠加**（与 P-051a F-R5 同类）。四模板的 `I9`（模板层不做组合 vol-target）扩展为 **I9′：模板层不做任何 stop 叠加**。

### D8 `prices` vs `history` 分工（P3-2 裁决）

| 模板 | 用 `history`（≤t−1） | 用 `prices`（当日） |
|------|----------------------|---------------------|
| `ts_momentum` | 全部（3 个 lookback 的收益符号） | 不用 |
| `mean_reversion` | 全部（z-score 窗口） | 不用 |
| `trend_breakout` | `high`/`low`/`close`（区间与 MA） | **用**（当日收盘判突破/跌破） |
| `grid_atr` | `high`/`low`/`close`（ATR）、`close.iloc[0]`（基准） | **用**（当日价位定档） |

理由：`trend_breakout` / `grid_atr` 的判定天然是「今日收盘 vs 昨日区间」，用 `prices` 无前视（决策后成交在次日开盘）；`ts_momentum` / `mean_reversion` 的统计量定义在 `[t−W, t−1]` 窗口上，加当日会改变 §18.3 的闭式数值。**保守方向，非缺陷**（P3-2）。

### D9 无状态与重放（承 P3 / U-P051b-15）

- 四模板对 `state` **只读**：`state.positions`（判断是否持仓）；不写 `state.extras`；
  - **语义注记（F-D7）**：`state.positions` 是**上一日目标权重**（非实际持仓，P-044 契约既定边界）；sizing / `apply_stops` 改变实际持仓时模板仍按目标判定，差异由该层兜底；
- 所有「记忆量」的处理：
  - `grid_atr` 基准 → 构造参数 `base_price`（可显式给，回测可复现）；
  - `mean_reversion` 持仓天数 → 交 `apply_stops`；
  - `ts_momentum` / `trend_breakout` → 无需记忆；
- 纯函数性（I3）：同一 `(view, state)` 两次调用逐值相等；
- 重放（I7）：给定同一 `views` 序列，`signals_frame` 逐值可复现，与策略实例是否新建无关。

### D10 错误处理

| 场景 | 处理 | 异常 |
|------|------|------|
| `history is None` 且模板需要历史 | fail-fast | `StrategyConfigError`（⊂ `ValueError`） |
| `history` 行数 < `min_rows` | fail-fast | `StrategyConfigError` |
| `history` 缺键（如无 `high`） | fail-fast | `StrategyConfigError` |
| 参数越界（`levels<1` / `grid_k<=0` / `atr_period<2` / `lookbacks` 空 / `min_votes` 越界 / **`base_price` 缺失或空**） | 构造期 fail-fast | `StrategyConfigError` |
| 未知配置键 | 构造期 fail-fast | `StrategyConfigError` |
| `grid_atr` 单标的 ATR ≤ 0 或 NaN | 该标的权重 0（不 fail 全表） | 无 |
| `grid_atr` `base_price` 缺某标的键 | 该标的权重 0 | 无 |
| 窗口内某标的价 NaN（momentum / mean_reversion） | 该标的 z / 收益为 NaN → 不入选 | 无 |
| `trend_breakout` 判定窗口含 NaN | `skipna=False`：未持仓不入选；持仓且 `lower` NaN → 保持 | 无 |
| `signals` 含负数（不可能，构造保证） | —— | —— |

### D11 工具链扩围

| 门禁 | 变更 |
|------|------|
| CI mypy | `.github/workflows/tests.yml` L46 命令追加 `strategies` |
| 本地 mypy 基线 | 113 → **119**（新增 6 个 `.py`） |
| black | 真实门禁 `black --check .`（Step 9 实测 **240 files unchanged**；预估 170 系口径误判，见 CHECKLIST §7） |
| pytest | 1040 → **实测 1091**（预估 ~1088；差 +3 = E1 参数化 4 例未计入预估） |

---

## 5. 测试规格（用例清单，禁录制）

| 文件 | ID | 断言要点 | 类型 |
|------|----|----------|------|
| `test_p051b_strategy_contract.py` | C1 | 四模板 `isinstance(x, Strategy)` + `meta` 四要素齐备 | 契约 |
| | C2 | `registry.get(name)` 可取到；三模板 `factory(None)` 为全默认；**grid_atr 因 `base_price` 必填，`factory(None)` / `factory({})` 须抛 `StrategyConfigError`**（P3-4b-1）；`factory({"levels":2})` 与 `factory(levels=2)` 两种传参形态等价 | 契约 |
| | C3 | 同 id 重复注册 → warning + 覆写（I5） | 契约 |
| | C4 | `code_hash` 12 hex、同类稳定 | 契约 |
| | C5 | `param_schema` 键集 == dataclass 字段集（I4） | 契约 |
| | C6 | 未知配置键 → `StrategyConfigError` | 契约 |
| | C7 | 四模板 `history=None` → `StrategyConfigError`（I10，参数化 4） | 契约 |
| `test_p051b_views_history.py` | V1 | 5 位置参数构造仍可用；`history` 默认 `None` | 回归 |
| | V2 | `hash(view)` → TypeError；不同实例 `==` → ValueError（P3-1 转正） | 回归 |
| | V3 | `history` 键集 == `{close,high,low}`；列 == `stock_codes` | 新契约 |
| | V4 | `history_window=0` → 全部 `None`；且 `returns`/`prices` 与改动前逐值相同 | 零行为 |
| | V5 | `i < W` → `None` | 新契约 |
| | V6 | `returns_window = history_window = W` 时 `history[k].index == view.returns.index`（同窗） | 新契约 |
| | V7 | `history` 末行 == `raw` 面板 `iloc[i-1]`（口径一致） | 新契约 |
| `test_p051b_ts_momentum.py` | M1 | §18.3.1 表 → `{A:0.5,B:0.5}`，C 不在 | 闭式 |
| | M2 | `min_votes=3` → 仅 B | 参数 |
| | M3 | 某 lb 收益恰为 0 → 该 lb 记 0 票（P3-3） | 边界 |
| | M4 | 空 codes → 空 Series、`dtype=float` | 边界 |
| | M5 | 非负 + 行和 ≤ `1+1e-9` + index ⊆ codes | I1 |
| | M6 | 两次调用逐值相等（I3） | 纯函数 |
| | M7 | 改 `history` 末行 → 结果变；改 `prices` → 结果不变（I2） | 无前视 |
| | M8 | `history` 行数 = `max(lookbacks) − 1` → `StrategyConfigError` | 边界 |
| `test_p051b_mean_reversion.py` | R1 | k=3 → z=−2.3202 → 入场 `{A:1.0}` | 闭式 |
| | R2 | k=4 → z=−1.9494 → 不入选 | 闭式 |
| | R3 | k=1 → z=−4.24853（不变量，与偏离幅度无关） | 闭式 |
| | R4 | 持仓中 k=16 → z=−0.4873 ≥ −0.5 → 清仓 | 出场 |
| | R5 | 持仓中 k=15 → z=−0.5627 < −0.5 → 继续持有 | 出场 |
| | R6 | `std==0`（恒定价）：未持仓 → 不入场；已持仓 → 出场（F-D4） | 边界 |
| | R7 | 纯函数 + index 约束 | I1/I3 |
| `test_p051b_trend_breakout.py` | T1 | 入场：`11>10` 且 `11>MA60=10` | 闭式 |
| | T2 | 拒绝：`10.5<11`（仅满足 MA）→ 不入选 | 反伪通过 |
| | T3 | 出场：持仓中 `8.5<9` → 清仓 | 闭式 |
| | T4 | 持仓中 `9.5>=9` → 继续持有 | 出场 |
| | T5 | 纯函数 + index 约束 | I1/I3 |
| `test_p051b_grid_atr.py` | G1 | ATR=1.0（全 TR 相等，与种子无关） | 闭式 |
| | G2 | 权重表 P=10/9/8/7/6 → 0 / 1/3 / 2/3 / 1 / 1（显式 `base_price=10`） | 闭式 |
| | G3 | 多标的 `{A:0.25,B:0.75}`（4/3 → ×3/4） | 闭式 |
| | G4 | `base_price` 缺失 / 空映射 → `StrategyConfigError`（R-1 / F-D2） | 参数 |
| | G5 | `base_price` 缺某标的键 → 该标的 0，其余正常 | 边界 |
| | G6 | 单标的 ATR NaN → 该标的 0，其余正常 | 边界 |
| | G7 | 纯函数 + index 约束 | I1/I3 |
| `test_p051b_end_to_end.py` | E1 | 四模板（参数化）× `views_from_data(history_window=W)` → `signals_frame` → `set_signal("weights")` → `run()` 不抛，且 `_signal_mode=="weights"` | 端到端 |
| | E2 | `grid_atr` + `apply_stops(StopConfig(stop_loss_pct=0.2))` → 触发日权重归 0（I9′ 组合闭合） | 组合 |
| | E3 | `signals_frame` 行和 ≤ `1+1e-9`（全链路 I1） | 端到端 |
| | E4 | 同一 views 两次 `signals_frame` 逐值相等（重放 I7） | 端到端 |

**计数**：C 7 + V 7 + M 8 + R 7 + T 5 + G 7 + E 4 = **45**（C7 参数化 4 例，pytest 计数按 4 计 → 预估 +48）。预估 `1040 → 1088`；**Step 9 实测 = 1091**（+3 差额 = E1 参数化 4 例未计入预估，见 CHECKLIST §7）。

---

## 6. 不变式

| ID | 不变式 |
|----|--------|
| I1 | 模板输出非负、行和 ≤ `1+1e-9`、index ⊆ `dm.stock_codes` |
| I2 | 无前视：仅消费 `history`（≤t−1）/ `prices`（当日，决策后成交）/ `state.positions`（≤t−1） |
| I3 | 纯函数：同一 `(view, state)` 两次调用逐值相等 |
| I4 | `meta.param_schema` 键集 == 构造参数集；`code_hash` 12 hex |
| I5 | 注册幂等：重复同 id → warning + 覆写，不抛错 |
| I6 | 未注册 id → `get()` 返回 `None`/报错（fail-fast）；`import strategies` 后四个 id 全部可取（F-D5：不依赖「未 import」的全局状态，改为可测断言） |
| I7 | 重放：同一 views 序列 → 同一 `signals_frame`（跨实例） |
| I8 | 不新增 golden；既有 22 条零重录 |
| I9′ | 模板层不做任何 stop 叠加、不做组合 vol-target、不调用 `apply_sizing` / `apply_stops` |
| I10 | `history` 缺失/行数不足/缺键 → `StrategyConfigError`（fail-fast，不静默返回空权重） |
| I11 | `history_window=0`（默认）→ P-044 既有行为逐值不变（含 1040 基线不退化） |
| I12 | 四模板对 `state` 只读；不写 `extras`；不持有可变实例状态（D9） |

---

## 7. DoD 与门禁

| 项 | 目标 |
|----|------|
| pytest | **1040 → 1091**（Step 9 实测：45 条 + C7 参数化 3 + E1 参数化 3） |
| `-k golden` | **22 零重录**（I8） |
| mypy | 113 → **119 files 0 error**（CI 命令加 `strategies`） |
| black | `black --check .` 全绿（Step 9 实测 240 unchanged） |
| `core/sizing.py` / `core/engine_v2.py` / `core/stops.py` | **零 diff** |
| `core/strategy.py` | 仅 2 处 additive（`MarketView` 末位字段 + `views_from_data` 末位参数） |
| 文档 | RESEARCH 回填 R-1..R-4（Step 8）；本 DESIGN；IMPL；CHECKLIST |
| CI | 四 job 全绿（须用户授权后推送） |

---

## 8. 风险与缓解

| ID | 风险 | 缓解 |
|----|------|------|
| Rk-1 | `MarketView` 加字段破坏 P-044 回归 | 只加末位默认字段；V1/V2/V4 三条回归用例 + 全量 1040 跑（I11） |
| Rk-2 | `grid_atr` 基准语义与调研「首建仓日收盘」不一致（R-1） | **`base_price` 必填**（修复 c）：调用方显式给出固定基准，语义与「首建仓日收盘」等价可达；无隐式滚动默认，无歧义 |
| Rk-3 | 模板与 `apply_stops` 组合被误认为「模板自带止损」 | I9′ + E2 用例 + DESIGN D7 三处明示 |
| Rk-4 | `history` 切片造成内存放大（2500 日 × 3 字段） | 只读使用，copy/view 由 pandas 决定；`history_window=0` 零开销；仅在需要时开启 |
| Rk-5 | `1/n` 浮点超限 | 已复算误差 ≤1e-13 ≪ 1e-9；E3 全链路断言 |
| Rk-6 | 新增包未纳入 CI mypy 覆盖 | D11 显式追加 `strategies` |

---

## 9. 幻觉抑制审查（Step 4 复审输入）

### 9.1 设计基于已验证的调研结论

- [x] 所有设计决策可追溯到 RESEARCH §4/§5/§6/§18 或本文件 P1-P9 实读事实
- [x] 无未经验证的假设（`BacktestAdapter` 无回写通道 = P3 实读；`atr` 语义 = P6；夹具支持 high/low = P8）
- [x] 对 RESEARCH 的订正（R-1 / R-2 / R-3；**R-4 已于 Step 4 F-D1 撤销**）均有代码证据支撑，并登记 Step 8 回填
- [x] Step 4 复审 2 P1 + 1 P2 + 8 P3 已全部收敛（见 §0.3），待 4b 异构复验

### 9.2 替代方案审查

| 方案 | 描述 | 判定 |
|------|------|------|
| **A1 扩展 `MarketView`**（采纳） | 末位可选 `history` | 真相单一、可重放、可测；additive 已实证 |
| A2 策略内部累积 | append 到 deque / `state.extras` | **否决**：`BacktestAdapter` 无 extras 回写（P3）→ 不可实现；中途加载不可重放 |
| A3 注入 fetcher 回调 | 构造传 `Callable[[date], DataFrame]` | **否决**：破坏可测性/序列化；模板无法纯函数测试 |
| A4 仅用 `returns` 窗口 | 累计收益代价格 | **否决**：拿不到 high/low → 网格/突破不可实现 |
| B1 模板内建止损 | 模板维护 `StopState` | **否决**：需状态回写（U-P051b-15）+ 与 `apply_stops` 双层叠加 |
| B2 改 `generate_signals` 返回 tuple | `(weights, extras)` | **否决**：破坏 P-044 Protocol 与既有两实现；本批无必要 |

### 9.3 职责边界审查

- 职责内：模板产权重（价量驱动）、`MarketView.history` 契约、registry 注册；
- 职责外（明确不做）：止损叠加（`core.stops`）、组合波动目标（引擎 sizing）、状态持久化（`BacktestAdapter` / P-051c）、策略生成（另立批次）。

---

## 10. 未决项登记

- **U-P051b-15 `BacktestAdapter` 状态回写通道**
  - **判据**：出现「模板必须记忆 entry/peak/bar_count 才能正确」的需求，且 `apply_stops` 无法覆盖
  - **触发条件**：P-051c 多策略虚拟子账户立项，或新增带金字塔加仓的模板
  - **当前倾向**：不改（本批四模板经 D9 证明无需）
  - **证据等级**：E1（P3 实读）

- 承 RESEARCH 既有未决项：U-P051b-1..14（其中 1/2/3/4/5/6/7 已在本 DESIGN 裁决落地；8/11/12/13/14 维持「另立批次」；9 维持「新建 `StrategyGenerator`」；10 待 IMPL 写「声明式四问」）。

---

## 11. 对实施的输入（Step 5）

| # | 实施要点 |
|---|----------|
| 1 | 先改 `core/strategy.py`（2 处 additive），跑全量 1040 确认零退化，再建 `strategies/` |
| 2 | `strategies/base.py` 先落地（错误类型 + 四工具），四模板复用；`grid_atr` 的 `base_price` 必填校验放在配置 `__post_init__` |
| 3 | 每模板先写闭式测试（红态）→ 实现 → 绿（TDD） |
| 4 | 注册装饰器写在工厂函数上，`__init__.py` 集中 import |
| 5 | CI mypy 命令追加 `strategies`；black 范围加 `strategies` |
| 6 | 禁录制：所有断言为闭式手算值或不变量 |
| 7 | 不动 golden 录制脚本与 22 条基线 |
