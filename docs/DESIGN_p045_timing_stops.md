# DESIGN：P-045 择时原语与止损状态机（timing + stops）

> **批次**: P-045 · **Step 3 设计** · 日期 2026-11-18
> **判档**: **T1**（新建 `core/timing.py` + `core/stops.py` 纯函数契约 + `tests/` + golden case）
> **上游**: [RESEARCH_p045](RESEARCH_p045_timing_stops.md)（§4 G1-G9 / §7 S1-S10 / §8 I1-I9 / §13 Step 2 pass：**2 P2 + 4 P3**）
> **代码证据时点**: HEAD `0482881`（P-044 关闭；工作区净）
> **基座**: DeepSeek-V4.1-Flash（Step 4 Review 须异构 GLM-5.3-Flash；U-P045-5 于 Step 10 终审闭合）

---

## 1. 范围与前置

**做**（B1 → B2 → B3）：
1. `core/timing.py`：`SignalSet` / `crossed_above` / `crossed_below` / `resolve_conflicts` / `holdings_from_signals` / `weights_from_holdings` / `apply_timing`；
2. `core/stops.py`：`StopConfig` / `StopBar` / `StopState` / `StopDecision` / `StopEngine` / `apply_stops` / `ohlc_from_data`；
3. 测试：`tests/test_p045_timing_stops.py`（V1-V8）+ 两个**规格锁定 golden**（`tests/golden/P045_S1.json` / `P045_S2.json`）；
4. 四文档 + 台账。

**不做**：做空/负权重（P-050）；sizing/再归一/部分减仓/金字塔（P-047）；订单层 size_type·call_seq·共享现金（P-047/P-053）；引擎主循环接线与 `RiskActionItem` → 订单闭环（P-048）；盘中 tick；`Strategy` wrapper（见 F-D3-P045-1）；修改 `core/risk_manager.py` / `core/strategy.py` / `core/engine_v2.py` / `core/config.py` / `agents/`。

**前置**（E3 @`0482881`）：`core/timing.py` / `core/stops.py` 不存在；`MarketView` 无 OHLC（G9）；`Position` 无水位/持仓龄；`trailing_stop_pct` 死配置；`.venv-vbt` 内 `vectorbt==1.2.0` 可导入（`from_signals` stop 参数 8 个）。

---

## 2. 设计决策

### 2.0 上游未决裁决（RESEARCH §9）

| 未决 | 裁决 | 落点 |
|------|------|------|
| U-P045-1 short 侧范围 | **仅保留类型位**：`SignalSet.entries_short/exits_short` 字段存在但全流程忽略；负权重仍由 `set_signal` fail-fast（P-050 接线时无需改签名） | D2 / §4 边界 5 |
| U-P045-2 止损接入点 | **矩阵级叠加**（不提供 `Strategy` wrapper；引擎/`risk_manager` 均不接线） | D1 / F-D3-P045-1 |
| U-P045-3 golden 新增 case | **2 个规格锁定 case**（`P045_S1`/`P045_S2`），独立 schema，P-013 harness 零 diff；golden 13→15 | D8 |
| U-P045-4 对拍范围与符号 | 对拍 `sl_stop`/`sl_trail`/`tp_stop`（免费版 1.2.0 实测参数）；本项目 `StopConfig` 统一**正数阈值** | D5 / I3 |
| F-S2-P045-1 对拍口径 | 只对拍**触发判定序列**；成交/NAV 差异按 P-015 恒等式闭式声明 | I3 / R4 |
| F-S2-P045-2 OHLC 载体（G9） | `StopBar` + `bars: Mapping[str, DataFrame]` 四键；**P-044 `MarketView` 零改动** | D5 / D7 |

### D1 模块职责与放置（U-P045-2 收敛）

| 模块 | 职责 | 依赖 |
|------|------|------|
| `core/timing.py` | 信号原语：交叉检测、冲突仲裁、持仓状态机、权重生成、**目标任务 gate** | 仅 `pandas` / `numpy`；**不 import `core.strategy`**（避免与 P-044 循环） |
| `core/stops.py` | 止损止盈状态机 + 矩阵级叠加 + OHLC 组装 | 仅 `pandas` / `numpy` / `dataclasses`；`TYPE_CHECKING` 下 `IDataManager` |

**裁决：不提供 `Strategy` wrapper（F-D3-P045-1）**。理由三条：
1. **OHLC 载体缺口**（G9）：`MarketView` 只有 `prices`（close），止损判定需 open/high/low；wrapper 只能靠构造期注入外部矩阵 → 成为「伪策略」；
2. **对称性与可测性**：timing/stops 均为**矩阵级纯变换**（`weights → weights`），与 `BacktestAdapter.signals_frame` 产物直接串联，`set_signal(mode="weights")` 一次注入即可闭环；
3. `StrategyState.extras` 仍承载 `StopState` 的序列化形态（`StopResult.states`），**P-044 §8 的「状态可重放」目标不变**，仅改变叠加位置（矩阵级而非 `generate_signals` 内）。

> **对 P-044 §8 的接口修正（已回写 P-044 DESIGN §8 注）**：P-045 以「矩阵级叠加」而非「`generate_signals` 内组成」交付；P-044 契约零改动。

### D2 timing 类型模型

```python
@dataclass(frozen=True)
class SignalSet:
    entries_long: pd.DataFrame                      # bool，dates × codes
    exits_long: pd.DataFrame                        # bool
    entries_short: Optional[pd.DataFrame] = None    # 类型位（P-050），本批忽略
    exits_short: Optional[pd.DataFrame] = None      # 类型位（P-050），本批忽略
```

- 形状约束：`entries_long` 与 `exits_long` 必须 index/columns 完全一致（`ValueError` fail-fast）；
- `short` 两侧字段存在但**全流程不读取**（`resolve_conflicts` / `holdings_from_signals` 忽略）→ P-050 接线时无需改签名（U-P045-1 裁决）；
- **（S4 注，F-S4-P045-2）**`SignalSet` 含 DataFrame 字段 → **`==` 比较不可用**（frozen dataclass 生成的逐字段 `__eq__` 触发 DataFrame 真值歧义 `ValueError`，探针实测）；等价断言用 `pd.testing.assert_frame_equal` 逐字段。

### D3 交叉检测（S2 细化）

```python
def crossed_above(series: pd.Series, level: float) -> pd.Series:
    prev = series.shift(1)
    return (series > level) & (prev <= level)      # NaN 比较恒 False
```

- 首行 `prev=NaN` → 恒 False；
- `level` 为标量（标量阈值）；逐标的阈值由调用方广播成 DataFrame 后按列调用（不做矩阵版，避免 API 膨胀）；
- `crossed_below` 为对偶（`series < level & prev >= level`）。

### D4 冲突仲裁与持仓状态机（S3/S4 裁决）

- **冲突仲裁**：同日同时 `entry=True` 与 `exit=True` → **exit 优先**（entry 被抵消）。理由：A 股 T+1 下「先卖后买」可执行但会增加换手；保守取「不新开仓」，且与 vbt `exits` 覆盖 `entries` 的主流语义一致。
- **持仓状态机**（向量化，无 Python 逐日循环）：

```python
raw = pd.DataFrame(np.nan, index=entries.index, columns=entries.columns)
raw = raw.mask(exits, 0.0)                 # exit 优先级最高
raw = raw.mask(entries & ~exits, 1.0)      # 同日 entry+exit 已由上一行覆盖为 0
holdings = raw.ffill().fillna(0.0).astype(bool)
```

- **权重生成**：`mode="equal"` → 每日按持仓数量等权（`1/n`），**空持仓日全 0**（现金）；**不重归一**（S4 裁决）——`exit` 后剩余持仓权重保持，行和 <1 合法（`build_target_positions` 允许余额留现金，P-031 D2 已证实）。
- **timing gate**：`apply_timing(targets, holdings) = targets.where(holdings, 0.0)`（逐日逐标的相乘；**不再归一**）。

### D5 止损类型模型

```python
@dataclass(frozen=True)
class StopConfig:
    stop_loss_pct: Optional[float] = None          # 正数跌幅阈值（0.10 = -10%）
    trailing_stop_pct: Optional[float] = None      # 正数，自峰值回撤
    take_profit_pct: Optional[float] = None        # 正数涨幅阈值
    time_stop_days: Optional[int] = None           # 持仓 bar 数上限（≥1）
    trailing_activate_pct: Optional[float] = None  # 移动止损激活阈值（PRO tsl_th 对应）

@dataclass(frozen=True)
class StopBar:
    date: pd.Timestamp
    open: float
    high: float
    low: float
    close: float

@dataclass(frozen=True)
class StopState:
    entry_price: float
    peak_price: float
    bar_count: int
    entry_date: str                                 # YYYY-MM-DD
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StopState: ...

@dataclass(frozen=True)
class StopDecision:
    action: str        # "hold" | "exit"
    reason: str        # "" | "stop_loss" | "trailing_stop" | "take_profit" | "time_stop"
    severity: float = 1.0

@dataclass(frozen=True)
class StopTrigger:
    date: pd.Timestamp
    code: str
    reason: str
    entry_date: str
    entry_price: float
    exit_price_ref: float    # 触发日收盘（成交在次日开盘，仅审计参考）

@dataclass(frozen=True)
class StopResult:
    weights: pd.DataFrame              # 触发日目标权重归 0（其余逐值不变）
    triggers: tuple[StopTrigger, ...]
    states: dict[str, dict[str, Any]]  # 末日各持仓 state（JSON 安全，可重放）
    deferred: int                      # 因不可交易被推迟的退出次数
```

- **符号约定**：`StopConfig` 全部**正数阈值**（与 vbt `sl_stop`/`tp_stop` 一致）；既有 `StopLossConfig.stop_loss_pct=-0.10`（负号）**不复用、不修改**，差异在此声明（U-P045-4 裁决）；
- **`__post_init__` 校验**：所有 `*_pct` 非 None 时必须 `> 0`；`time_stop_days` 非 None 时必须 `≥ 1`；违规 `ValueError`。

### D6 状态机与 bar 内触发顺序（S8 细化）

`StopEngine.update(state, bar) -> tuple[StopState, StopDecision]`：

| 步 | 规则 |
|----|------|
| 1 | `state is None` → 建仓：`entry_price=bar.close`、`peak_price=max(bar.high, bar.close)`、`bar_count=1`、`entry_date=bar.date`；返回 `hold` |
| 2 | `peak_price = max(state.peak_price, bar.high)`；`bar_count = state.bar_count + 1` |
| 3 | **固定止损**（gap 或盘中）：`bar.open <= entry*(1-sl)` 或 `bar.low <= entry*(1-sl)` → `exit/stop_loss`。**（S4 注，F-S4-P045-3）**`low <= open` 为 OHLC 不变量（探针 1000 随机样本实证）→ open 分支为 low 分支的**真子集**，判定上冗余；保留仅为 gap 语义显式（非逻辑依赖） |
| 4 | **移动止损**（激活后）：`trailing_activate_pct` 为 None 或 `peak >= entry*(1+act)`，且 `bar.low <= peak*(1-trail)` → `exit/trailing_stop`。**（S4 注，F-S4-P045-4）**激活判定用**更新后 peak**（步 2 已含当 bar high）→ 同 bar 允许「激活即触发」；该语义由 IMPL 与 G1 锁定 |
| 5 | **止盈**：`bar.high >= entry*(1+tp)` → `exit/take_profit`（**同 bar 若 3 已触发则不判 5**——SL 优先）。**（S4 注，F-S4-P045-4）**完整触发优先级链 = **SL > trailing > TP > time**（步序即优先级；trailing 与 TP 同 bar 并发时 trailing 胜，保守口径） |
| 6 | **时间止损**：`bar_count >= time_stop_days` → `exit/time_stop`。**（S4 注，F-S4-P045-4）**建仓日（步 1）**不做止损检查**——理由：T+1 成交前无持仓可止损（`entry_price`=当日收盘近似成交价，O-P045-1 口径自洽） |
| 7 | 无触发 → `hold`；返回更新后的 state。**（S4 注，F-S4-P045-4）**延迟退出日（D7 不可交易）bar_count 照常递增（持仓未了结，计入持仓龄） |

**口径声明**：
- `entry_price = 建仓日收盘`（近似）；真实成交价为次日开盘（A 股 T+1），误差由 golden 锁定并在 §4 声明（O-P045-1，精化归 P-048/P-053）；
- **触发 ≠ 成交**（**S8 订正，F-S8-P045-6**）：`apply_stops` 在触发日 T 把目标权重矩阵**第 T 行对应项**归 0（该行目标经既有执行链在 T+1 开盘成交；G1 锁定 T+1 行为重建值而非 0）→ **无前视**（I5）；
- 时间止损按「持仓 bar 数」计（建仓日为 1）。

### D7 矩阵级叠加 `apply_stops`（G9 载体裁决）

```python
def apply_stops(
    targets: pd.DataFrame,
    bars: Mapping[str, pd.DataFrame],     # 必须含 open/high/low/close 四键
    config: StopConfig,
    *,
    tradable: Optional[pd.DataFrame] = None,
) -> StopResult:
```

- **OHLC 载体**：`bars` 为四键 DataFrame 映射（`ohlc_from_data(dm)` 由 `dm.get_adj_price(kind, "raw")` 组装，与引擎成交口径一致）；**P-044 `MarketView` 零改动**（G9 关闭）；
- **严格校验**：四键缺失 / 任一矩阵按 `(targets.index, targets.columns)` 重排后含 NaN → `ValueError`（fail-fast，不静默跳过）；**（S4 注，F-S4-P045-5）**`targets` 自身含 NaN 同样 `ValueError`（与 bars 同口径；`signals_frame` 产物无 NaN，防御性拒绝外部构造）；
- **（S4 注，F-S4-P045-7）**`ohlc_from_data` 硬编码 `raw` 口径——引擎 `_exec_price` 的 `legacy_adjustment` 旧口径**不在本批**（P-012 已冻结，`PriceModeConfig` 默认 raw 与执行链一致）；
- **逐日算法**：
  1. 先对**已有 state** 的标的应用 `StopEngine.update`；若 `exit` 且 `tradable[t, code]` 为真 → `weights[t, code] = 0`、删除 state、追加 `StopTrigger`；
  2. 若 `exit` 但 `tradable[t, code]` 为假（跌停/停牌）→ **保持权重与 state**、`deferred += 1`（下一可交易日重新判定，不预扣未来）；
  3. 再处理**新开仓**：`targets[t, code] > 0` 且无 state → `update(None, bar)` 建 state；
  4. `targets[t, code] <= 0` 且无 state → 不动；有 state 且目标为 0（策略主动清仓）→ 删除 state；
- **（S6 注，F-S6-P045-2）止损退出日禁止同日重建**（退出分支 `continue`）：退出日权重强制 0，重建最早于次日（targets>0 时）。G1 的 C 路径已锁定该语义——若允许同日重建，C 将以 01-03 close（100）/peak（122）重建并于 01-04 以 trailing_stop 再次退出，与 G1 期望冲突；
- **输出约束**：`weights` 与输入同形、非负、行和 ≤ 输入行和（只减不增）；
- `tradable` 缺省 `None` → 全部可交易；提供了则按 `(targets.index, targets.columns)` 重排 `fillna(False)`。

### D8 golden：**规格锁定**（U-P045-3 裁决）

| 项 | 裁决 |
|----|------|
| 新增 case | `P045_S1`（固定止损 + 移动止损 + 止盈优先级）、`P045_S2`（时间止损 + 跌停延迟退出） |
| 文件 | `tests/golden/P045_S1.json` / `P045_S2.json`（**独立 schema**：`case_id` / `git_commit` / `config` / `weights` 小矩阵 / `triggers` / `deferred` / `tolerance`） |
| 断言 | `tests/test_p045_timing_stops.py` 内两个函数（命名含 `golden`，以纳入 `-k golden` 统计） |
| 性质 | **规格锁定（analytically specified）而非行为录制**——期望值由本 DESIGN 手工推导（触发日期/reason/权重），不用实现输出自证；强于 P-013 的「当前行为锁」 |
| 既有 golden | `G1..G7.json` / `_golden_cases.py` / `test_golden_baseline.py` **零 diff**（跨 schema 隔离） |
| 计数 | golden **13 → 15**（构成：`test_golden_baseline.py` 9 + `TestGoldenRebalanceIntegration` 4 + 新增 2） |

### D9 零行为边界

- 新增 2 模块 + 1 测试文件 + 2 golden json + 4 文档；`core/` 既有文件**零 diff**（含 `engine_v2` / `strategy` / `risk_manager` / `config`）；
- 不调用即零副作用（无 import 副作用、无全局单例）；
- 既有 golden 13 零重录；`agents/` / `tests/golden/G*.json` 零 diff。

---

## 3. 精确签名

### 3.1 `core/timing.py`（新建）

imports：`dataclasses` / `typing`（`Any, Optional`）/ `numpy as np` / `pandas as pd`。

```python
def crossed_above(series: pd.Series, level: float) -> pd.Series: ...
def crossed_below(series: pd.Series, level: float) -> pd.Series: ...

@dataclass(frozen=True)
class SignalSet: ...

def resolve_conflicts(signals: SignalSet) -> SignalSet: ...
def holdings_from_signals(signals: SignalSet) -> pd.DataFrame: ...
def weights_from_holdings(holdings: pd.DataFrame, *, mode: str = "equal") -> pd.DataFrame: ...
def apply_timing(targets: pd.DataFrame, holdings: pd.DataFrame) -> pd.DataFrame:
    """gate：holdings=False 处归 0；**（S4 订正，F-S4-P045-1）**reindex 必须用 keyword 形式
    （``holdings.reindex(index=targets.index, columns=targets.columns)``——位置参数形式
    ``reindex(targets.index, targets.columns)`` 实测 TypeError，DataFrame.reindex 只收 1-2 个位置参数）。"""
```

- `resolve_conflicts`：返回新 `SignalSet`，`entries_long = entries & ~exits`，`exits_long` 不变；`short` 两侧原样透传；
- `weights_from_holdings`：`mode` 仅接受 `"equal"`（其他 `ValueError`），输出 `float` 且行和 ∈ {0, 1}；
- `apply_timing`（**S8 订正，F-S8-P045-5**）：`_as_bool(holdings.reindex(index=targets.index, columns=targets.columns))` 后 `targets.where(aligned, 0.0)`——reindex 必须 keyword 形式（F-S4-P045-1），布尔归一由 `_as_bool` 承担。

### 3.2 `core/stops.py`（新建）

imports：`dataclasses` / `typing`（`Any, Mapping, Optional, TYPE_CHECKING`）/ `numpy as np` / `pandas as pd`；`TYPE_CHECKING` 下 `from core.interfaces import IDataManager`。

```python
@dataclass(frozen=True)
class StopConfig: ...          # 5 字段 + __post_init__ 校验
@dataclass(frozen=True)
class StopBar: ...
@dataclass(frozen=True)
class StopState: ...           # to_dict / from_dict
@dataclass(frozen=True)
class StopDecision: ...
@dataclass(frozen=True)
class StopTrigger: ...
@dataclass(frozen=True)
class StopResult: ...

class StopEngine:
    def __init__(self, config: StopConfig) -> None: ...
    def update(
        self, state: Optional[StopState], bar: StopBar
    ) -> tuple[StopState, StopDecision]: ...

def ohlc_from_data(dm: "IDataManager") -> dict[str, pd.DataFrame]: ...
def apply_stops(
    targets: pd.DataFrame,
    bars: Mapping[str, pd.DataFrame],
    config: StopConfig,
    *,
    tradable: Optional[pd.DataFrame] = None,
) -> StopResult: ...
```

- `StopEngine` **无内部可变状态**（config 只读；`update` 纯函数），可并发复用；
- `ohlc_from_data` 四键顺序固定 `("open","high","low","close")`，全部 `get_adj_price(kind, "raw")`；**（S4 注，F-S4-P045-7）**legacy 复权口径不在本批（见 D7）；
- **（S4 注，F-S4-P045-2）**`StopConfig` / `StopBar` / `StopState` / `StopDecision` / `StopTrigger` 五类全标量字段 → `==` 可用（dataclass 逐字段比较）；`StopResult` 含 DataFrame/tuple/dict → **禁用 `==`**，断言逐字段。

### 3.3 `tests/` 与 golden

| 文件 | 内容 |
|------|------|
| `tests/test_p045_timing_stops.py`（新建） | V1-V8（8 函数）+ `test_golden_p045_s1` / `test_golden_p045_s2`（2 函数）= **10** |
| `tests/golden/P045_S1.json` / `P045_S2.json`（新建） | 规格锁定期望（手工推导） |

---

## 4. 数据流与边界

```
既有策略（P-044）:
  IDataManager ──views_from_data──> views ──signals_frame──> targets (DataFrame)
                                                              │
  timing（可选）:  entries/exits ──holdings_from_signals──> holdings ──apply_timing──> targets'
                                                              │
  stops（可选）:   ohlc_from_data(dm) + config ──apply_stops──> StopResult.weights + triggers
                                                              │
                        engine.set_signal(weights, mode="weights") ──> 既有执行链（T+1 开盘）
```

**边界声明**：

| # | 边界 | 语义 |
|---|------|------|
| 1 | 止损触发 ≠ 成交 | 触发日归零**当日目标权重行**（该行目标经 T+1 执行链成交；F-S8-P045-6 措辞订正），成交价由既有链路 T+1 开盘决定（无前视） |
| 2 | `entry_price` | 建仓日收盘（近似）；真实成交价精化归 P-048/P-053（O-P045-1） |
| 3 | 不可交易退出 | `tradable=False` 当日保持权重并计 `deferred`，下一可交易日重判（不预扣未来） |
| 4 | 分批退出 | **不支持**（`exit_fraction` 归 P-047；本批退出即全清） |
| 5 | 做空 | `entries_short`/`exits_short` 仅类型位，全流程忽略；负权重仍由 `set_signal` fail-fast |
| 6 | 再归一 | 不重归一（行和 <1 合法，余额留现金）；sizing 归 P-047 |
| 7 | 避免循环 import | `timing`/`stops` 不 import `core.strategy`；叠加为矩阵级 |

---

## 5. 测试规格（`tests/test_p045_timing_stops.py`，10 用例）

夹具：`tests/_synth_fixture.py` 的 `write_price_fixture`（可写独立 OHLC）+ 本文件内构造小矩阵（5 日 × 2-3 股，价格手工指定）。核心符号函数内导入。（**S8 订正，F-S8-P045-7**：终态以 [IMPL_p045 §4.1/§5](IMPL_p045_timing_stops.md) 为准——**纯内联小矩阵，不引入 `_synth_fixture`**（纯函数测试无需引擎夹具））

| # | 用例 | 断言 |
|---|------|------|
| V1 | 交叉检测 | `crossed_above`：首行 False；`NaN` 当前/前值 → False；真实交叉恰 1 个 True；`crossed_below` 对偶；`level` 边界（等于不触发） |
| V2 | 冲突仲裁 + 持仓状态机 | 同日 entry+exit → `resolve_conflicts` 后 entry 为 False；`holdings_from_signals`：entry 后持续持有、exit 后清空、entry→exit→entry 重建；全 False 日保持前值（ffill） |
| V3 | 权重生成 | `weights_from_holdings("equal")`：2 持有 → 各 0.5；空持仓行全 0；行和 ∈ {0,1}；非法 `mode` → `ValueError` |
| V4 | timing gate | `apply_timing`：holdings=False 处权重归 0；holdings=True 处逐值保留；**不重归一**（行和 < 输入行和） |
| V5 | 固定止损 | `StopEngine.update`：建仓 state 正确（entry=close、peak=max(high,close)、count=1）；gap 触发（`open <= entry*(1-sl)`）；盘中触发（`low <= ...`）；未触发 hold |
| V6 | 移动止损 + 止盈优先级 | 峰值更新后回撤触发 trailing；`trailing_activate_pct` 未达 → 不触发；同 bar SL 与 TP 同时满足 → **reason 为 stop_loss**；仅 TP → take_profit |
| V7 | 时间止损 + 延迟退出 | `bar_count >= time_stop_days` → time_stop；`apply_stops` + `tradable=False` 当日 → 权重保持、`deferred == 1`、无 trigger；下一可交易日触发并归零 |
| V8 | `apply_stops` 端到端 | 多标的：触发日权重归 0、非触发日逐值不变、`triggers` 逐值（date/code/reason/entry_price）、`states` JSON 往返、行和只减不增、四键缺失 → `ValueError` |
| **G1** | golden S1 | `P045_S1.json`：固定+移动+止盈优先级（权重矩阵逐值 + triggers 逐值 + deferred=0） |
| **G2** | golden S2 | `P045_S2.json`：时间止损 + 跌停延迟（triggers 日期与 reason 逐值 + deferred=1） |

**映射**：V1↔S2/I3；V2↔S3/S4；V3/S4↔S4；V5/V6/V7↔S5-S9；V8↔D6/D7；G1/G2↔I4 + 验收「止损状态机 golden」。

**红态预测**：**`10 failed`**（`ModuleNotFoundError: core.timing` / `core.stops`；golden JSON 不存在 → `FileNotFoundError`）。

---

## 6. 不变式与门禁口径

| ID | 不变式 |
|----|--------|
| I1 | 既有 golden **13 零重录**；`agents/` / `core/engine_v2.py` / `core/engine_v3_vector.py`（**S8 补，F-S8-P045-4**，RESEARCH I1 原列）/ `core/strategy.py` / `core/risk_manager.py` / `core/config.py` 零 diff |
| I2 | `core/timing.py` / `core/stops.py` 纯函数：`open(`/`requests.` grep = 0；无模块级副作用 |
| I3 | **止损触发判定序列**与 vectorbt（隔离 venv `1.2.0`）逐值一致（**S8 订正，F-S8-P045-2**——vbt 免费版无交叉原语可比，交叉检测由 S2 语义 + V1 锁定）；成交/NAV 差异按 P-015 恒等式闭式声明（F-S2-P045-1） |
| I4 | 止损状态机确定性：同输入两次输出逐值相同；G1/G2 规格锁定 |
| I5 | 无前视：T 日仅用 ≤T bar；触发日归零**当日**目标权重行（经 T+1 执行链成交，F-S8-P045-6），成交价由执行链决定 |
| I6 | A 股可成交性：`tradable=False` 退出延迟（V7）；负权重/行和 >1 由 `set_signal` 兜底 |
| I7 | 零新增依赖 |
| I8 | `StopState` / `StopResult.states` JSON 往返相等（V8） |
| I9 | 状态清理：目标权重归 0（策略主动清仓）→ state 删除；再入场重建（V8） |

**计数链（Step 9 实测回填）**

| 门禁 | 现值 | 预期 | 说明 |
|------|------|------|------|
| pytest | 811 | **821** | +10（V1-V8 + G1/G2） |
| golden | 13 | **15** | +2 规格锁定 case（P-013 既有 13 零重录） |
| black（`core tests` / 全仓） | 132·199 | **135·203** | +2 源 +1 测试 +1 对拍脚本（**F-S9-P045-5 订正**）；**（订正）**RESEARCH §8 原记 134·201 漏算测试文件（F-S2-P045-5 同类，F-D3-P045-3） |
| mypy | 105 | **108** | +2 模块 +1 对拍脚本（命令含 `scripts/`；**F-S10-P045-1 订正**，原记 107 漏算对拍脚本） |
| AST `except Exception` | 22 | **22** | 新模块零该模式（无 try/except） |
| `tests/*.py` | 93 | **94** | +1 测试文件 |
| 对拍 | —（新建） | **verify_p045 exit 0** | 隔离 venv；触发序列逐值 + 豁免显式（F-S6-P045-1；**S8 补行，F-S8-P045-8**） |
| uv lock | 0 | **0** | 零依赖 |

命令同 IMPL §7（沿用 P-044）。

---

## 7. 风险与回退

| ID | 风险 | 处置 / 验证 |
|----|------|-------------|
| R1 | `entry_price=收盘` 与真实成交价（次日开盘）不一致 | 文档声明（§4 边界 2）+ G1/G2 锁定；精化归 P-048（O-P045-1） |
| R2 | 触发日归零 → 次日开盘成交，跳空导致实际亏损 > 阈值 | 属 A 股执行现实（vbt `StopMarket` 同语义）；`exit_price_ref` 记录触发日收盘供审计 |
| R3 | 停牌/跌停日无法卖出 → 退出延迟 | `tradable` 门控 + `deferred` 计数（V7）；不预扣未来 |
| R4 | 与 vbt 对拍口径混淆（同 bar 成交 vs T+1） | I3 已收窄为触发序列；NAV 差异闭式声明（F-S2-P045-1） |
| R5 | 逐日 Python 循环性能 | 标的数 × 日数（1460×数十持仓）≈ 万级 `update` 调用，单次 <10µs；不引入 numba（避免 CI 类型桩风险） |
| R6 | golden 规格锁定写错（手工推导错误） | G1/G2 期望在 IMPL 中逐步推导并交叉复核；Step 9 若实现与规格不符，**先审规格**（不得改期望迁就实现） |
| R7 | 与 P-044 `extras` 约定漂移 | `StopResult.states` 为 JSON 安全 dict，可由调用方写入 `extras`；P-048 复核 |

**回退点**：B1（`timing.py`）删除即净；B2（`stops.py`）删除即净；B3（测试 + golden）可独立删除；三批互不依赖既有文件。

---

## 8. 与后续批次的接口约定

| 批次 | 依赖本批的什么 |
|------|----------------|
| P-047 仓位管理 | `weights_from_holdings` 输出作为 sizing 输入；**再归一/部分减仓**在 P-047 实现 |
| P-048 风险 overlay | `StopResult.triggers` + `states` 作为 `RiskActionItem` 来源；`entry_price` 口径精化 |
| P-051 策略模板 | `apply_timing` / `apply_stops` 作为模板的标准后处理 |
| P-053 实盘 | `StopEngine` 逐 bar 复用（`StopBar` 由实时行情组装）；触发单类型 StopMarket 归柜台层 |
| P-050 空头 | `SignalSet.entries_short/exits_short` 类型位接线；`StopConfig` 增加空头方向 |

---

## 9. 设计期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-D3-P045-1 | **P2** | 止损需 OHLC（G9），而 `Strategy.generate_signals(view, state)` 的 `MarketView` 仅含 close → **`StopsStrategy` wrapper 不可实现**（除非构造期注入外部矩阵成为伪策略）；RESEARCH §1/M-A 的「Strategy wrapper 组合器」与载体冲突 | D1 裁决：**矩阵级叠加**（`apply_timing` / `apply_stops`），不提供 wrapper；`StopResult.states` 承载可序列化状态；P-044 §8 预期修正并回写 |
| F-D3-P045-2 | P3 | RESEARCH §8 I8 与 §6 计数链只计 2 个源文件（black 134·201），漏算新增测试文件 | §6 订正为 **135·202**（+2 源 +1 测试）；pytest/golden/tests 同步 |
| F-D3-P045-3 | P3 | golden 若沿用 P-013 schema（`engine ∈ {v2,v3}`、`scenario` 枚举、money/ratio 路径），纯函数 case 无法表达且须改 `test_golden_baseline.py` | D8 裁决：**独立 schema + 独立期望文件**，P-013 harness 零 diff；并采用**规格锁定**而非行为录制 |
| F-D3-P045-4 | P3 | `StopConfig.trailing_activate_pct` 对应 PRO `tsl_th`，免费版 1.2.0 无对应参数 | D5 声明「本仓实现、**不在对拍范围**」（U-P045-4 一致） |
| F-D3-P045-5 | P3 | `entry_price` 取建仓日收盘为近似，真实成交在次日开盘 | §4 边界 2 + O-P045-1（精化归 P-048） |
| F-D3-P045-6 | P3 | 分批退出（RESEARCH S3/F4 第 3 项）需部分权重/仓位分配，属 P-047 sizing | §1 不做清单 + §4 边界 4 显式排除 |

### 9.1 观察项登记

| ID | 观察 | 处置 |
|----|------|------|
| O-P045-1 | `entry_price = 建仓日收盘` 为近似值；真实成交价为次日开盘（A 股 T+1），跳空会使止损实际亏损偏离阈值 | 本批文档声明 + G1/G2 锁定；**精化（按真实成交价建 state）归 P-048/P-053** |
| O-P045-2 | `StopResult.states` 为末日快照，不含逐日状态轨迹（审计需逐日可查时需扩展 `history`） | 不扩做；P-048 若需逐日轨迹再扩展（`triggers` 已含逐日触发记录） |

---

## 10. Step 4 Review（异构基座复审）

> **评审基座**: GLM-5.3-Flash（≠ 正文作者 DeepSeek-V4.1-Flash）→ **异构复审成立**（Step 2/4 连续两轮异构；U-P045-5 维持至 Step 10）。
> **评审日期**: 2026-11-18 · 对象：D1-D9 / §3 签名 / §5 测试规格 / §6 计数链 / §9 发现。
> **取证方式**: 运行时探针（`%TEMP%\p045_s4_probe.py`，Python 3.12）+ 机械复核。**零预填，本节为评审后回填。**

### 10.1 探针证据（E2 运行时）

| 组 | 输出 | 结论 |
|----|------|------|
| P1（D4 holdings 状态机） | A 列 `[T,T,T,F,T]`（entry→hold→exit→re-entry）；B 列 `[F,F,F,F,F]`（同日 entry+exit → **exit 优先**） | D4 mask 序 + ffill 语义实证 ✓ |
| P2（D3 交叉 NaN） | `crossed_above` = `[F,F,F,T,F,F]`——prev=NaN 阻断 idx5、当前 NaN 恒 False | S2/F-S2-P045-3 NaN 语义实证 ✓ |
| P3（D6 步 3 冗余性） | 1000 随机 OHLC 样本 `low <= open` **全部成立** | open 分支为 low 分支真子集 → 冗余证实 → F-S4-P045-3 |
| P4（apply_timing 语义） | row sums = `[1.0, 0.6]`——B 退出后 A 权重保持 0.6，**不重归一** ✓；**`reindex(targets.index, targets.columns)` 位置参数形式实测 `TypeError`** | S4 不重归一实证 ✓；**§3.1 代码片段不可实现** → F-S4-P045-1 |
| P5（frozen dataclass `==`） | 含 DataFrame 字段的 frozen dataclass `==` 抛 **`ValueError: truth value of a DataFrame is ambiguous`** | `SignalSet`/`StopResult` 禁用 `==` → F-S4-P045-2 |

### 10.2 发现与处置（当轮处置，全部 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S4-P045-1 | P3 | §3.1 `apply_timing` 代码片段 `holdings.reindex(targets.index, targets.columns)` **不可实现**（`DataFrame.reindex` 只收 1-2 个位置参数，探针 P4 实测 TypeError） | §3.1 订正为 keyword 形式 `reindex(index=..., columns=...)` 并加注 |
| F-S4-P045-2 | P3 | 含 DataFrame 字段的 frozen dataclass `==` 不可用（探针 P5 实测 ValueError）——`SignalSet`/`StopResult` 等价断言若写 `==` 必炸 | D2/D5 补注：`SignalSet`/`StopResult` 断言用 `assert_frame_equal` 逐字段；五类全标量 dataclass `==` 可用 |
| F-S4-P045-3 | P3 | D6 步 3 open 分支判定冗余（`low <= open` 为 OHLC 不变量，探针 P3 实证） | 保留为 gap 显式文档语义，注明非逻辑依赖（P-044 clip 冗余同款处理） |
| F-S4-P045-4 | P3 | D6 三点未显式：① 完整优先级链（步序隐含 **SL > trailing > TP > time**）；② 同 bar「激活即触发」（步 4 用更新后 peak）；③ 建仓日不做止损检查的理由（T+1 成交前无持仓） | D6 步 3-7 各补注显式化；IMPL 与 G1 按此锁定 |
| F-S4-P045-5 | P3 | `apply_stops` 对 `targets` 含 NaN 未规格化（NaN 落入 `>0`/`<=0` 之外静默穿透） | D7 补注：`targets` 含 NaN 同口径 `ValueError`（防御性拒绝） |
| F-S4-P045-6 | P3 | RESEARCH §6（B3 wrapper 提案 / pytest 819）/ §8 I8（black 134·201）与 DESIGN（矩阵级叠加 / 821 / 135·202）不一致 | RESEARCH §6/§8 补订正注（以 DESIGN §6 为准） |
| F-S4-P045-7 | P3 | `ohlc_from_data` 硬编码 `raw` vs 引擎 `_exec_price` 尊重 `legacy_adjustment` | D7/§3.2 补注：legacy 旧口径不在本批（P-012 已冻结，默认 raw 与执行链一致） |
| F-S4-P045-8 | P3 | 延迟退出日（`deferred`）bar_count 继续递增的语义未写明（持仓未了结应计入持仓龄） | D6 步 7 补注显式 |

### 10.3 机械复核

- 计数链自洽：pytest 811→**821**（+10 = V1-V8 + G1/G2）、golden **13→15**（构成实证：`test_golden_baseline.py` 9 + `TestGoldenRebalanceIntegration` 4，`-k golden --collect-only` 读数）、black **135·203**（+2 源 +1 测试 +1 脚本；F-S9-P045-5）、mypy **107**（Step 4 时点；Step 10 复跑订正 **108**，F-S10-P045-1）、AST **22**（新模块无 try/except）、tests **94** ✓
- §2.0 上游裁决表覆盖 U-P045-1/2/3/4 + F-S2-P045-1/2 全部六项 ✓；RESEARCH §13 强制输入全承接 ✓
- V1-V8+G1/G2 ↔ I1-I9 映射全覆盖；七条边界与 P-050/P-047/P-048 划界清晰 ✓
- P-044 DESIGN §8 修正注已回写（矩阵级叠加，契约零改动）✓；`agents/`/引擎/`risk_manager`/`config` 零 diff 声明与 I1 一致 ✓
- B1-B3 回退点独立（新模块删除即净）；R6「规格与实现不符先审规格」纪律 ✓

### 10.4 结论

**准予进入 Step 5 IMPL**。发现 8 项均 P3 且已当轮处置（正文已修订）；两项 P2 上游输入（F-S2-P045-1 对拍口径、F-S2-P045-2 OHLC 载体）已在 D1/D7/I3 完整承接；探针证实的两处实现级缺陷（reindex 位置参数、DataFrame 字段 `==`）已订正为可落码规格。无 P1/P2 阻塞项。
