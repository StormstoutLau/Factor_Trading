# DESIGN：P-044 策略接口抽象（Strategy Protocol + BacktestAdapter）

> **批次**: P-044 · **Step 3 设计** · 日期 2026-11-18
> **判档**: **T1**（新建 `core/strategy.py` 契约 + `core/registry.py` 扩展 + `core/engine_v2.py` 信号模式分支 + `tests/`）
> **上游**: [RESEARCH_p044](RESEARCH_p044_strategy_interface.md)（§7 S1-S10 / §8 I1-I9 / §13 Step 2 pass：1 P2 + 2 P3 / **§14 补充调研：E1-EXT 社区锚点**）
> **代码证据时点**: HEAD `96384f6`（P-043 关闭；工作区净）
> **基座**: 正文 DeepSeek-V4.1-Flash；Step 4 Review 由 GLM-5.3-Flash 执行（**异构复审成立**；Step 2 曾同源 → U-P044-5 维持登记，Step 10 终审仍由 GLM-5.3-Flash 承接闭合——**（S8 措辞订正）**）

---

## 1. 范围与前置

**做**（B1 → B2 → B3 → B4；批次字母与 IMPL §2 文件对齐拆分一致——B1=下方 1+2+4（`core/strategy.py` 全量）/ B2=5 的 registry / B3=3（引擎）/ B4=5 的测试）：
1. `core/strategy.py`：`StrategyMeta` / `StrategyState` / `MarketView` / `TargetWeights` / `Strategy` Protocol / `code_hash`；
2. `BacktestAdapter`：策略逐日驱动 → 权重矩阵；`views_from_data` 视图组装；`state_history` 审计；
3. 引擎**信号模式**：`set_signal(df, mode="scores"|"weights")` + `_execute_rebalance` 单分支（weights 跳过优化器）；
4. 等价迁移：`FactorSignalStrategy`（默认路径）+ `DirectionalStrategy`（long/short/both，P-031 D2）；
5. `core/registry.py` +strategy 类别；`tests/test_p044_strategy_interface.py` 8 用例。

**不做**：`strategies/` 模板库（P-051）；`live/`（P-053）；`StrategyEngine` 内部重构（U-P044-3）；择时/风险/负权重（P-045/048/050）；`BacktestConfig` 新字段。

**前置**（E3 @`96384f6`）：`core/strategy.py` / `strategies/` 不存在；`core/registry.py` 5 类别；引擎 `_composite_signal` 私有、`run()` 已对未就绪抛 `RuntimeError`；`SignalTranslator.from_weights` 已有（下游不改）。

---

## 2. 设计决策

### D1 协议放置：`core/strategy.py`（U-P044-1 裁决）

外部锚点（§14.1）：qlib `BaseStrategy` / vnpy `CtaTemplate` / backtrader `Strategy` 均在**专用策略模块**；hexagonal「端口定义在领域层」。本地先例：P-042 D5 契约与实现同域。

| 被拒 | 代价 |
|------|------|
| `core/interfaces.py` | 需反向依赖策略专属 4 类型；该文件已 549 行，跨层聚合模块再膨胀 |
| 新建 `core/strategy_contract.py` + 实现分家 | 无先例；多一个文件与概念，mypy/black 计数 +1 无收益 |

### D2 类型模型：frozen dataclass + Protocol property

```python
@dataclass(frozen=True)
class StrategyMeta:
    strategy_id: str
    version: str
    param_schema: dict[str, Any]
    code_hash: str

@dataclass(frozen=True)
class StrategyState:
    as_of: str                       # YYYY-MM-DD
    positions: dict[str, float]      # 上一日目标权重（策略可用；当前两策略忽略）
    extras: dict[str, Any]           # JSON 安全扩展位
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyState: ...

@dataclass(frozen=True)
class MarketView:
    date: pd.Timestamp
    signal: pd.Series                # 当日因子分/原始信号
    tradable: pd.Series              # bool
    prices: pd.Series                # 当日收盘价（执行口径 raw）
    returns: Optional[pd.DataFrame]  # 截至前一日的收益窗口；None=不可用

TargetWeights = pd.Series            # 类型别名（index=标的，value=非负权重；负权重属 P-050）
# （S9 订正）落码为 `TargetWeights: TypeAlias = pd.Series`——mypy 需 TypeAlias 注解才认作类型
# （pandas 无 stubs 时裸赋值被判 `valid-type`）；运行时 `TargetWeights is pd.Series` 不变（V1 断言）

@runtime_checkable
class Strategy(Protocol):
    @property
    def meta(self) -> StrategyMeta: ...
    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights: ...
```

- `meta` 声明为 **property**（而非数据成员）。**论据订正（Step 4 探针 F-S4-P044-1）**：property 与注解成员均被 typing 计入 `__non_callable_proto_members__`（探针 A3：`['meta']`），`issubclass()` 对两者**同样**抛 `TypeError`（探针 A2/B2）——初稿「property 规避 TypeError」论据不成立。保留 property 的真实理由：实现类用普通属性即可静态满足 + 只读语义表达。V1 仅用 `isinstance`（探针 A1/B1/C1/C2 对 property/注解两种协议均 `True`），设计不变。
- `StrategyState` 仅放 JSON 安全类型（`str/float/dict`）；`MarketView` 不快照大矩阵（prices/returns 引用只读）。

### D3 `code_hash` 规格（U-P044-4 裁决）

外部锚点（§14.3）：`inspect.getsource` 源不可得抛 `OSError`；动态 `exec` 类因 `__module__='builtins'` 对类取源抛 `TypeError` 而非 `OSError`（Step 4 探针 D1/D2 实测，方法取源仍 OSError）→ 回退链须捕获 `(OSError, TypeError)` 双异常（下方代码块已如此）；社区实现均为「getsource → dedent → 回退链」；MLflow 语义是「绑定确切代码」。

```python
def code_hash(target: Any) -> str:
    """策略代码指纹：类源码归一化 sha256 前 12 hex；回退带前缀（不静默）。"""
    try:
        source = inspect.getsource(target)
    except (OSError, TypeError):
        method = getattr(target, "generate_signals", None)
        if method is not None:
            try:
                source = inspect.getsource(method)
            except (OSError, TypeError):
                source = ""
    if not source:
        seed = f"{qualname}|{version}|{canonical_json(param_schema)}"
        return "q:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    normalized = textwrap.dedent(source).replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
```

- **类级**粒度；参数值不入 hash（参数在 `param_schema`）；
- **换行归一必须做**（Windows CRLF / CI LF）；
- 回退前缀 `q:` 使审计可判别（`q:` = 非源码回退），不静默。

| 被拒 | 代价 |
|------|------|
| 仅 git commit | 未提交/本地改动策略无法区分 |
| 模块级源码 | 同模块多策略同哈希 |
| 仅 `co_code` bytecode | 跨 Python 3.10/3.12 CI 漂移 |

### D4 `BacktestAdapter`：批量物化 + 视图组装（U-P044-2 裁决 A）

外部锚点（§14.2A）：qlib `WeightStrategyBase`「策略只产权重，框架转订单」；vectorbt `from_weights/targetpercent`；批量 DataFrame 与现引擎同形。

```python
class BacktestAdapter:
    def __init__(self, strategy: Strategy) -> None: ...
    @property
    def state_history(self) -> list[StrategyState]: ...
    def signals_frame(
        self, views: Iterable[MarketView], initial_state: Optional[StrategyState] = None
    ) -> pd.DataFrame: ...                     # index=dates, columns=标的并集；缺省 0
    @staticmethod
    def views_from_data(
        dm: IDataManager,
        signal: pd.DataFrame,
        tradable: Optional[pd.DataFrame] = None,
        returns_window: int = 0,
    ) -> list[MarketView]: ...
```

- `signals_frame` 逐日调用 `strategy.generate_signals`，把返回 Series 填入当日行；**未出现的标的当日权重记 0**（目标权重语义，显式文档化）；
- 状态演进：`next_state = StrategyState(as_of=当日, positions=…, extras=state.extras)`；`state_history` 追加（审计/重放）。**（S8 订正）**`positions` 实际存**非零项**（IMPL 先 `weights[weights != 0]` 再入状态）——零权重 ≡ 缺席已由 `build_target_positions` 读码证实（IMPL §9.1-3），语义等价；
- `views_from_data`：`tradable` 缺省 `signal.notna()`；`prices=dm.get_adj_price("close","raw")`（与引擎 `_exec_price` 默认口径一致）；`returns_window>0` 时切「截至前一日」窗口，否则 `None`；
- **历史不足规格（F-S4-P044-3）**：`returns_window>0` 且 `date_index < returns_window` 时该日 `returns=None`（镜像引擎 `date_index >= cov_lookback` 才构造窗口的逐日语义）；内存口径声明：views list 逐日持有切片引用（signal/tradable/prices 为 Series 视图）+ returns 窗口 DataFrame，生产规模（约 1460 日 × 5688 标的）总量与引擎 `_execute_directional_rebalance` 逐日构造等量级，不复制全量收益矩阵；
- `BacktestAdapter` 只依赖 `IDataManager` 抽象（`TYPE_CHECKING` 导入），不依赖 `UniverseFilter`/引擎。

### D5 引擎信号模式与 `set_signal`（U-P044-2 裁决 B）

**语义澄清（本设计的核心）**：引擎 `_composite_signal` 原为**因子分**（下游 `optimizer.optimize`）。策略契约产出的是**目标权重**；若直接把权重塞进 `_composite_signal`，优化器会把权重当分数二次优化 → 语义错误。因此必须引入**显式模式**：

```python
# core/engine_v2.py
self._signal_mode: Literal["scores", "weights"] = "scores"   # __init__，默认零行为

def set_signal(self, signal: pd.DataFrame, *, mode: Literal["scores", "weights"] = "scores") -> None:
    if self.dm is None:
        raise RuntimeError("请先调用setup()方法")
    if mode not in ("scores", "weights"):
        raise ValueError(f"未知信号模式: {mode}")
    if not signal.index.equals(self.dm.trade_dates):
        raise ValueError("signal.index 必须与 dm.trade_dates 完全一致")
    unknown = set(signal.columns) - set(self.dm.stock_codes)
    if unknown:
        raise ValueError(f"signal 含未知标的: {sorted(unknown)[:5]}")
    aligned = signal.reindex(columns=self.dm.stock_codes)
    if mode == "weights":
        values = aligned.fillna(0.0)
        if (values.to_numpy() < 0).any():
            raise ValueError("weights 模式不接受负权重（空头属 P-050）")
        if (values.sum(axis=1) > 1.0 + 1e-9).any():
            raise ValueError("weights 模式要求每行权重和 ≤ 1")
        aligned = values
    self._composite_signal = aligned
    self._signal_mode = mode
```

`_execute_rebalance` 在「组合优化」try 之前加**单分支**：

```python
if self._signal_mode == "weights":
    target_weights = daily_signal.clip(lower=0.0)   # 策略直出，跳过优化器
else:
    try:  # 既有优化器路径，逐字不动
        ...
```

- 默认 `"scores"` → 既有路径逐字执行，**零行为**；
- `weights` 模式的 `returns_data` 构造被跳过（策略侧已在 `MarketView.returns` 内自带窗口）；
- `clip(lower=0.0)` 在 `set_signal` 非负校验之后属冗余，保留为防御（分支被绕过校验直接调用时兜底），非语义依赖（F-S4-P044-5）；
- `should_trigger(signal=...)` 在 weights 模式下拿到权重而非分数——Step 4 读码：`FixedIntervalTrigger`（含 daily，[core/rebalance.py](file:///f:/Coding/Factor_Trading_v3.0/core/rebalance.py#L47-L111)）不读 signal；`ConditionalTrigger`（L112-226）直接读 `kwargs["signal"]`（L138-177）；`HybridTrigger`（L228-277）经 L265 `**kwargs` 透传给内部条件触发器**间接消费**——**weights 模式禁配 conditional/hybrid**，边界统一登记 O-P044-2（F-D3-P044-3 范围修正）。

| 被拒 | 代价 |
|------|------|
| 适配器写私有 `_composite_signal` | 跨模块私有耦合（G7），且无模式区分 → 权重被二次优化 |
| `run(strategy=...)` | 引擎签名扩张并在主链路引入策略编排；weights 模式已足够 |
| 构造注入 signal | 信号依赖 `setup()` 后数据对齐，构造期不可得（§14.2B） |

### D6 等价迁移映射（P-031 D2 逐字）

| 策略类 | 等价来源 | 规格 |
|--------|----------|------|
| `FactorSignalStrategy` | 引擎默认路径 | `generate_signals` = `optimizer.optimize(view.signal[view.tradable].dropna(), view.returns)` |
| `DirectionalStrategy(select_top=True)` | `StrategyConfig(direction="long")` | 同上，`select_top=True` |
| `DirectionalStrategy(select_top=False)` | `StrategyConfig(direction="short")` | 同上，`select_top=False` |
| `DirectionalStrategy(direction="both")` | `StrategyConfig(direction="both")` | 多头腿 `select_top=True` × `long_weight`；空头腿禁用（`short_leg_supported=False` 类常量，对应 P-031 D2） |

- 两个策略类**复用既有 `IOptimizer`**（构造注入），等价性由「同一优化器实例」保证，不复制选股逻辑；
- `meta.param_schema` 记录 `select_top` / `long_weight` / 优化器方法名等；`meta.version = "1.0.0"`；
- `StrategyEngine` 内部零改动（U-P044-3）。

### D7 registry：+strategy 类别

`core/registry.py`：`_strategy_registry` + `get_strategy_registry()` + `register_strategy(...)`，与既有 5 类别同构（重复注册 warning + 覆写，L77-79 语义）。§6 门禁「每策略必有 id+版本+参数 schema+代码 hash」由 `StrategyMeta` + 注册表共同承载。

### D8 零行为边界

- 默认路径：不调用 `set_signal` → `_signal_mode="scores"` → `_execute_rebalance` 走原 try 块**逐字**；
- `agents/` 生产文件**零 diff**；`BacktestConfig` 零新字段；不建 `strategies/` / `live/`；
- golden 13 零重录；`tests/golden/` 零 diff。

---

## 3. 精确签名

### 3.1 `core/strategy.py`（新建）

imports：`hashlib` / `inspect` / `json` / `textwrap` / `dataclasses` / `typing`（`Any, Callable, Iterable, Optional, Protocol, runtime_checkable`）/ `pandas as pd`；`TYPE_CHECKING` 下 `from core.interfaces import IDataManager, IOptimizer`。

```python
TargetWeights = pd.Series
StrategyFactory = Callable[..., "Strategy"]


def canonical_json(value: Any) -> str: ...      # sort_keys, ensure_ascii=False, separators=(",", ":")
def code_hash(target: Any) -> str: ...          # 见 D3


@dataclass(frozen=True)
class StrategyMeta: ...
@dataclass(frozen=True)
class StrategyState: ...                        # to_dict / from_dict
@dataclass(frozen=True)
class MarketView: ...


@runtime_checkable
class Strategy(Protocol): ...


class FactorSignalStrategy:
    def __init__(self, optimizer: IOptimizer, *, strategy_id: str = "factor_signal",
                 version: str = "1.0.0") -> None: ...
    @property
    def meta(self) -> StrategyMeta: ...
    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights: ...


class DirectionalStrategy:
    def __init__(self, optimizer: IOptimizer, *, direction: str = "long",
                 select_top: bool = True, long_weight: float = 1.0,
                 strategy_id: Optional[str] = None, version: str = "1.0.0") -> None: ...
    short_leg_supported = False                  # P-031 D2
    @property
    def meta(self) -> StrategyMeta: ...
    def generate_signals(self, view: MarketView, state: StrategyState) -> TargetWeights: ...


class BacktestAdapter: ...                       # 见 D4
```

- `StrategyState.from_dict` 只接受 `dict`，`positions` 值 `float()`、`extras` 原样（JSON 安全由调用方保证，文档声明）；
- `MarketView` 不做 `__post_init__` 校验（构造廉价；校验在 `set_signal` / `views_from_data` 边界）。

### 3.2 `core/registry.py`

在 L176-180 追加 `_strategy_registry`；L183-220 追加 `get_strategy_registry()`；L309-328 之后追加 `register_strategy`（与 `register_agent` 同构）。

### 3.3 `core/engine_v2.py`

| 项 | 规格 |
|----|------|
| import | `from typing import Literal` 并入既有 typing 导入 |
| `__init__` | `self._signal_mode: Literal["scores", "weights"] = "scores"`（`_composite_signal` 附近） |
| `set_signal` | D5 代码块；置于 `_precompute_factors` 之后、`run()` 之前 |
| `_execute_rebalance` | 「组合优化」try 前 +1 分支（D5）；原 try/except 缩进进 `else` |

---

## 4. 数据流与边界

```
回测（本批）:
  IDataManager ──views_from_data──> list[MarketView]
       └─> Strategy.generate_signals(view, state) ──> TargetWeights
              └─> BacktestAdapter.signals_frame ──> DataFrame
                     └─> engine.set_signal(df, mode="weights") ──> 既有 build_target_positions/ExecutionSimulator
```

- 策略**不接触**订单/执行/账目；适配器**不接触**订单；引擎仍是唯一执行者（与 qlib 分层一致）。
- `set_signal` 是边界校验点：负权重 / 行和 >1 / 未知标的 / index 不一致 → `ValueError`（fail-fast，不静默截断）。
- `scores` 模式保留原行为（NaN 不填充；既有 `_precompute_factors` 的 `fillna(0)` 不变）。
- **模式语义差异（F-S4-P044-2）**：`scores` 模式由优化器只选可交易股（`tradable` 掩码内 dropna）；`weights` 模式**不强制** tradable——策略经 `MarketView.tradable` 自主决策，产出即目标权重。等价测试须显式同源传 `tradable`（V5）。
- **因子文件前置（F-S4-P044-4）**：`setup()` 预检要求 `factor_files` 非空，纯策略运行（weights 模式）仍需占位因子文件；占位仅用于通过 setup——`set_signal` 会整体替换 `_composite_signal`，边界文档化。

---

## 5. 测试规格（`tests/test_p044_strategy_interface.py`，V1-V8）

夹具：复用 [tests/_synth_fixture.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_synth_fixture.py)（5 日 × 2 股；零费用 / daily / `enable_pending_orders=False` / `write_manifest=False`）。核心符号函数内导入。预计红态：**`7 failed, 1 passed`**（V4 为零行为护栏，当前代码即通过）。

| # | 用例 | 断言 |
|---|------|------|
| V1 | 契约 | 三 frozen dataclass 赋值抛 `FrozenInstanceError`；`isinstance(FactorSignalStrategy(...), Strategy)`；`meta` 四字段类型；`TargetWeights is pd.Series`；`inspect.signature(generate_signals)` 参数逐字 |
| V2 | `code_hash` | 同源两次相同、12 hex；测试类改参数（源码不变）hash 不变；`exec` 动态类 → `q:` 前缀回退；CRLF 源码与 LF 源码同 hash |
| V3 | 状态序列化 | `StrategyState.to_dict` → `json.dumps` → `from_dict` 往返相等；`as_of/positions/extras` 逐值 |
| V4 | **零行为护栏** | 默认引擎两次运行 metrics/NAV/trades 完全一致；`getattr(engine, "_signal_mode", "scores") == "scores"`（红态亦 PASS） |
| V5 | weights 模式集成等价 | baseline（默认 scores）vs strategy（`FactorSignalStrategy(engine.optimizer)` + adapter + `set_signal(mode="weights")`）→ trades 逐值、`portfolio_value` 逐值、metrics 相等；`views_from_data` 显式传 `tradable=engine.universe.tradable`（weights 模式不强制 tradable，须与 baseline 同源，F-S4-P044-2） |
| V6 | 三方向等价 | long/short/both 的 `generate_signals` 与 `EqualWeightOptimizer(select_top=...)` 直接输出逐值相等；both = long × `long_weight`；`DirectionalStrategy.short_leg_supported is False` |
| V7 | `set_signal` 边界 | index 不一致 / 未知标的 / 负权重 / 行和 >1 → `ValueError`（逐案）；`scores` 模式允许 NaN；调用后 `_signal_mode` 正确 |
| V8 | registry | `get_strategy_registry()` 单例；`register_strategy` 注册/`has`/`create`；重复注册 `caplog` 含 warning 且覆写 |

**映射**：V1↔I2/I10；V2↔I7；V3↔I4；V4↔I1；V5↔I3/I9；V6↔I3；V7↔I6；V8↔I5。

---

## 6. 不变式与门禁口径

| ID | 不变式 |
|----|--------|
| I1 | 默认路径零行为：golden **13 零重录**；`agents/` 零 diff；`BacktestConfig` 零新字段 |
| I2 | `Strategy` 运行时满足契约（`isinstance`）；`meta` 四要素齐备 |
| I3 | 等价迁移：`FactorSignalStrategy` / `DirectionalStrategy` 输出与既有路径**逐值相等** |
| I4 | `StrategyState` JSON 往返相等；同状态重放输出一致 |
| I5 | registry `strategy` 类别：注册/查询/创建/覆写 warning |
| I6 | `set_signal` 四类非法输入 fail-fast；`weights` 模式非负且行和 ≤1 |
| I7 | `code_hash`：同源码稳定、12 hex、CRLF/LF 同值、动态类回退带 `q:` |
| I8 | `core/strategy.py` 无 I/O（AST：`open`/`requests`/全局写 = 0） |
| I9 | weights 模式与 scores 模式在同一策略/优化器下结果**逐值一致**（V5） |
| I10 | 契约测试含 `inspect.signature`（`runtime_checkable` 不校验签名） |

**计数链（Step 9 实测回填）**

| 门禁 | 现值 | 预期 | 说明 |
|------|------|------|------|
| pytest | 803 | **811** | +8（V1-V8） |
| golden | 13·790 | **13·790** | 默认 scores 零重录 |
| black | 130·197 | **132·199** | 新增 2 个文件（`core/strategy.py` + 测试）；**S5 订正**：原记 131·198 漏算测试文件（两口径均含 `tests/`，见 IMPL F-S5-P044-1） |
| mypy | 104 | **105** | 新增 `core/strategy.py` |
| AST `except Exception` | 22 | **22** | 新文件无该模式；`set_signal` 用 `ValueError` |
| `tests/*.py` | 92 | **93** | 1 个新测试文件 |
| uv lock | 0 | **0** | 零依赖 |

---

## 7. 风险与回退

| ID | 风险 | 处置 / 验证 |
|----|------|-------------|
| R1 | weights 模式被误用于因子分 | 显式 `mode` 参数 + 默认 `scores`；V7 覆盖模式校验 |
| R2 | `set_signal` 静默丢列/填零 | 未知标的 fail-fast；缺列填 0 **文档化**并由 V7 覆盖 |
| R3 | 权重行和 >1 造成现金透支 | `set_signal` 校验 `sum ≤ 1+1e-9`；策略侧 `long_weight ≤ 1` |
| R4 | `code_hash` 跨平台漂移 | CRLF/LF 归一 + V2 断言 |
| R5 | `inspect.getsource` 在动态类失败 | 回退链 + `q:` 前缀 + V2 覆盖 |
| R6 | 权重当成信号触发 `should_trigger` | fixed/daily 不读 signal（读码 L47-111）；**conditional 直接读（L138-177）、hybrid 经 kwargs 透传间接读（L265）**（Step 4 读码）→ weights 模式禁配这两类；登记 O-P044-2（范围扩大） |
| R7 | 适配器状态膨胀 | `state_history` 仅存 `positions` 字典（每日本身已在 DataFrame）；文档声明 |
| R8 | 与 `StrategyEngine` 双实现漂移 | 等价测试锁 P-031 语义；内部重构归 P-051（U-P044-3） |

**回退点**（批次字母与 IMPL §2 对齐，**（S8 订正）**原按初稿 B1 含 registry）：B1（`core/strategy.py` 全量：契约+适配器+迁移）零行为可单独 revert；B2（registry 三符号）还原即净；B3（引擎 `set_signal` + `_signal_mode` + 分支）revert 后默认路径不变；B4 测试文件可独立删除。

---

## 8. 与后续批次的接口约定

| 批次 | 依赖本批的什么 |
|------|----------------|
| P-045 择时/止损 | `Strategy.generate_signals` 可在内部叠加状态机；`StrategyState.extras` 携带状态 |
| P-047 仓位管理 | `TargetWeights` 由 sizing 产出；`set_signal(mode="weights")` 作为投放口 |
| P-051 策略模板库 | `strategies/` 继承 `Strategy`，registry 注册 + `meta.code_hash` 追溯 |
| P-053 实盘 | `LiveAdapter` 复用同一 `Strategy`，逐事件驱动 |

---

## 9. 设计期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-D3-P044-1 | P2 | 权重不能直接塞入 `_composite_signal`——下游优化器会把权重当分数二次优化 | D5 引入 `_signal_mode` + `set_signal(mode=...)`；默认 `scores` 零行为；V5 逐值等价锁 |
| F-D3-P044-2 | P3 | `runtime_checkable` 对非方法成员 `issubclass` 抛 `TypeError` | D2 `meta` 声明为 property；V1 用 `isinstance` + `inspect.signature`（文档明示签名不校验）。**（S4 订正）**「property 规避 TypeError」论据被探针证伪（F-S4-P044-1）：property 同属非可调用成员，`issubclass` 仍抛；D2 论据已改写，处置不变 |
| F-D3-P044-3 | P3 | weights 模式下 `should_trigger(signal=...)` 语义变化 | 读码：fixed/daily 不读 signal → 零影响。**（S4 修正范围）**conditional 直接读（L138-177）、hybrid 经 kwargs 透传间接读（L265）→ weights 模式禁配；O-P044-2 范围扩大 |

---

## 10. Step 4 Review（异构基座复审）

> **评审基座**: GLM-5.3-Flash（≠ 正文作者 DeepSeek-V4.1-Flash）→ **异构复审成立**；按头部约定 U-P044-5 不触发（Step 10 终审另轮）。
> **评审日期**: 2026-11-18 · 对象：D1-D8 / §3 签名 / §5 V1-V8 / §6 I1-I10 / §9 发现。
> **取证方式**: 运行时探针（`%TEMP%\p044_s4_probe.py`，Python 3.12）+ 读码（core/rebalance.py）+ 机械复核。**零预填，本节为评审后回填。**

### 10.1 探针证据（E2 运行时）

| 组 | 输出 | 结论 |
|----|------|------|
| A1-A3（property 协议） | `isinstance=True`；`issubclass → TypeError: Protocols with non-method members don't support issubclass()`；`__non_callable_proto_members__=['meta']` | **证伪 D2 初稿论据**「property 规避 TypeError」→ F-S4-P044-1 |
| B1-B2（注解成员协议） | `isinstance=True`；`issubclass → TypeError` | 与 A 组同构，property/注解无差别 |
| C1-C2（交叉 isinstance） | 均 `True` | V1 仅用 `isinstance` → 设计不受影响 |
| D1-D2（getsource 异常） | `exec` 动态类：`getsource(class) → TypeError`（`__module__='builtins'`）；`getsource(method) → OSError` | D3 回退链须捕获 `(OSError, TypeError)`——代码块已写对，文字规格补正 |
| E1（hash 归一） | CRLF/LF 归一后同 hash `e8d8903c0aed` | D3 归一化规格可行，V2 可断言 |

### 10.2 读码证据（E3，[core/rebalance.py](file:///f:/Coding/Factor_Trading_v3.0/core/rebalance.py)）

| 位置 | 事实 |
|------|------|
| L47-111 `FixedIntervalTrigger` | `should_trigger` 不读 signal → weights 模式零影响 |
| L112-226 `ConditionalTrigger` | **直接读 `kwargs["signal"]`**（L138-177）→ weights 模式下拿到权重而非分数 |
| L228-277 `HybridTrigger` | L265 将含 signal 的 `**kwargs` 透传给内部 `_conditional_trigger` → **间接消费** |

→ **O-P044-2 范围扩大**：weights 模式禁配 conditional/hybrid（D5/R6/F-D3-P044-3 已同步修正）。

### 10.3 发现与处置（当轮处置，全部 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S4-P044-1 | P3 | D2「property 规避 issubclass TypeError」被探针 A2/A3 证伪：property 同属非可调用成员 | D2 论据改写（真实理由=实现类普通属性满足协议+只读语义）；设计不变（V1 仅 isinstance） |
| F-S4-P044-2 | P3 | weights 模式不强制 tradable（策略经 `MarketView.tradable` 自主决策）vs scores「优化器只选可交易股」语义差异 | §4 增补声明；V5 显式传 `tradable=engine.universe.tradable` 同源对齐 |
| F-S4-P044-3 | P3 | `views_from_data` 缺「历史不足 → None」规格；生产规模 views 内存口径未声明 | D4 增补：`date_index < returns_window` → `returns=None`（镜像 `cov_lookback` 语义）+ 内存口径声明 |
| F-S4-P044-4 | P3 | weights 模式仍需 `factor_files` 非空（setup 预检），纯策略运行需占位文件 | §4 增补边界：占位仅用于通过 setup，`set_signal` 整体替换信号 |
| F-S4-P044-5 | P3 | D5 weights 分支 `clip(lower=0.0)` 在校验后冗余 | 保留为防御，D5 注明非语义依赖 |
| （补记 1） | — | D3 文字规格只提 OSError，探针 D1 证实 exec 类抛 `TypeError` | D3 文字规格补双异常（代码块本已 `except (OSError, TypeError)`） |
| （补记 2） | — | O-P044-2 范围不足：conditional/hybrid 会（间接）读 signal | D5/R6/F-D3-P044-3 修正：weights 禁配两类触发器 |

### 10.4 机械复核

- 计数链自洽：pytest 803→811（+8=V1-V8）、golden 13·790 零重录、black **132·199**（+1 源 +1 测试；S5 订正，原记 131·198）、mypy 105（+1 新文件）、AST **22 不变**（`set_signal` 用 `ValueError` 非 `except Exception`，新文件无 I/O）、tests 92→93 ✓
- V1-V8 ↔ I1-I10 映射全覆盖，无不变式遗漏 ✓
- B1-B4 回退点逐一独立可 revert；`agents/` 零 diff 与 M-A 裁决一致 ✓
- D6 与 P-031 D2 对齐（`short_leg_supported=False`、`long_weight` 缩放）✓

### 10.5 结论

**准予进入 Step 5 IMPL**。发现 5 项 + 2 项补记均 P3 且已当轮处置（正文已同步修订）；核心语义 F-D3-P044-1 的处置（`_signal_mode` 显式模式 + `set_signal` fail-fast）经探针与读码双重证实成立；无 P1/P2 阻塞项。
