# DESIGN：P-051c 策略生命周期（晋级门 + 监控/退役 + 多策略虚拟子账户）

> **批次**: P-051c · **Step 3 设计** · 日期 2026-11-21
> **上游**: [RESEARCH_p051c](RESEARCH_p051c_strategy_lifecycle.md)（E1-E14 / G1-G9 / §4.0 / §11.7-11.8 / I1-I10）；**Step 4 复审**: [REVIEW_p051c_step4](REVIEW_p051c_step4_design.md)（GLM-5.3-Flash 异构 ✅）→ 一轮 **1 P1 + 2 P2 + 4 P3**（已修）→ 二轮 **2 P1 + 2 P3**，其中 N-4 经分析**重估为 P1**（共 3 P1 + 1 P3）→ **已按方案全部修复（N-1 方案 A / N-2 实 API / N-4 资金下限 / N-3 图注）→ 三轮定点核验通过（2 P3 同步残留已修正），Step 4 关闭**
> **代码证据时点**: HEAD `53db4f7`，工作区仅有 docs 改动
> **状态**: Step 3 完成 → Step 4 关闭（三轮定点核验通过，0 P1）→ Step 5 IMPL → Step 6 关闭（二轮异构，机制层 0 P1）→ Step 7 CHECKLIST → **Step 8 一致性通过（2026-11-21，R-1..R-4 已修）**
> **基座**: DeepSeek-V4.1-Flash（**Step 4 复审须异构：GLM-5.3-Flash**）

---

## 0. 裁决记录（Step 3 定案）

| 编号 | 议题 | 定案 | 依据 |
|------|------|------|------|
| U-P051c-1 | 状态机归属 | `core/lifecycle.py` 纯函数核 | 总纲 L205 指名；core 不依赖 agents |
| U-P051c-2 | 无实盘时 paper 机械化 | **证据注入**，`StageEvidence.source` 三值 | §11.2；**DESIGN 标注为工程选择，非行业最佳实践** |
| U-P051c-3 | 虚拟子账户 | 纯账本 + 校验，**不接引擎** | R8/R9/R10 |
| U-P051c-4 | 是否顺带解 U-P044-3 | 不解，引擎零 diff | R18（信息隐藏）+ 风险不对称 |
| U-P051c-5 | `BacktestAdapter` 状态回写 | 本批不改 | 本批只读 `state_history` |
| U-P051c-6 | `SizingState` 持久化 | 本批不需要 | 生命周期不消费 sizing 状态 |
| U-P051c-7 | 归档落盘位置 | 工作区外；core 只产 JSON | 与 golden/报告纪律一致 |
| U-P051c-8 | regime 预留 | 仅 `regime: str \| None` 字段 + 注释 | HMM 归 P-057 |
| U-P051c-9 | 判据阈值来源 | 初值 + 可配置；测试锁迁移规则不锁阈值 | §11.7 诚实边界 |
| U-P051c-10 | DSR/PBO | 仅预留字段，**不写空实现** | 需多重试验记录 |
| U-P051c-11 | 判据分组命名 | `GateCriteria(readiness, value)`；**不复用** `AssumptionCheck`（后者语义是运行时监控） | 二者生命周期位置不同 |
| U-P051c-12 | 月度归因 | **外置**，本批零代码 | R20 单期模型 + R21 多期链接 |
| U-P051c-13 | 版本化注册 | 指纹方案，不改 registry | R14（MLflow 弃用 Model Stages） |
| U-P051c-14 | 滚动 IC | **core 内自实现横截面 rank IC**，口径对齐 `calculate_ic(method="spearman")` | 反向依赖禁止（`strategy_evaluation` 不被 core 消费） |
| U-P051c-15 | OOS 产出器 | Splitter + `BacktestAdapter` + **`engine_v2` 复跑** + `compute_metrics` | 引擎口径唯一，避免新写净值算法 |
| U-P051c-16 | Gate 决策枚举 | **Go / Hold / Recycle / Kill** 四值 | R15（Stage-Gate 官方） |
| **U-P051c-17**（新） | OOS 切段语义 | **continuous 切片**（默认）；segmented 逐窗重跑留待 Step 5 视引擎能力 | 见 D6 与 §13 R1 |
| **U-P051c-18**（新） | 是否提供 segmented 模式 | Step 5 依 `engine_v2` 是否支持起始日/初始状态裁决，**默认不做** | 见 §13 R1 |
| **U-P051c-19**（新，Step 4 F-D1） | 预热段（前 W 日强制空仓）是否计入绩效 | **排除**；`StageEvidence.warmup_days = W` 记录 | 空仓段会稀释年化收益、压低波动，扭曲夏普 |
| **U-P051c-20**（新，Step 4 二轮 N-1） | `W` 的来源 | **方案 A**：`evaluate_strategy(..., min_history: int)` 由调用方显式传入，不从策略反推 | 四模板 min_rows 均为实例配置函数 + Protocol 无该属性 → 反推会令第三方策略永久不可评估 |

---

## 1. 目标与非目标

**目标**：把「策略候选」从 draft 推到 live 的每一步变成**可机械判定、可审计、可重放**的记录；并提供多策略资金账本与退役归档。

**非目标**（本批零代码）：月度归因、regime/HMM、DSR/PBO 计算、LLM 策略生成、`MultiStrategyEngine` 改造、`core/registry.py` 版本化、实盘对接。

---

## 2. 模块与依赖

```
core/lifecycle.py        ← 状态机 + 判据 + 决策 + 归档 JSON（纯函数，零 I/O）
core/oos.py              ← OOS 绩效产出器（消费 Splitter/BacktestAdapter/engine_v2/metrics）
core/virtual_account.py  ← 虚拟账户 + 多策略账本 + 校验（纯记账）
        │
        ├── core/walk_forward.py（只读 WalkForwardSplitter）
        ├── core/strategy.py（BacktestAdapter / views_from_data / StrategyMeta）
        ├── core/engine_v2.py（只读调用，零改动）
        ├── core/metrics.py（compute_metrics，唯一绩效口径）
        └── core/stops.py（可选叠加，零改动）
```

**依赖纪律**：三新模块**不得** import `agents.*`、`strategy_evaluation.*`、`scripts.*`；不得读写文件（I1）。

新增公共导出：仅经各模块 `__all__`，不改 `core/__init__.py`（若存在聚合导出，Step 5 核对）。

---

## 3. 数据契约

```python
class LifecycleStage(str, Enum):
    DRAFT = "draft"; BACKTEST = "backtest"; PAPER = "paper"
    GRAY = "gray"; LIVE = "live"; RETIRED = "retired"

class GateAction(str, Enum):
    GO = "go"; HOLD = "hold"; RECYCLE = "recycle"; KILL = "kill"

@dataclass(frozen=True)
class StrategyFingerprint:
    strategy_id: str; version: str
    param_snapshot: dict[str, Any]   # 来自 StrategyMeta.param_schema
    code_hash: str                   # 来自 StrategyMeta.code_hash

@dataclass(frozen=True)
class StageEvidence:
    source: str                      # "walk_forward" | "paper_record" | "live_account"
    metrics: Optional[MetricsResult] = None          # OOS 聚合指标
    is_metrics: Optional[MetricsResult] = None       # 样本内指标（用于衰减）
    window_metrics: tuple[tuple[str, MetricsResult], ...] = ()  # 逐窗
    ic_series: Optional[pd.Series] = None
    paper_days: int = 0
    paper_trades: int = 0
    current_drawdown: Optional[float] = None          # 非负量级
    # —— Step 5 IMPL 补齐（F-I7）——
    warmup_days: int = 0                              # U-P051c-19：被排除的预热日数
    is_oos_decay: Optional[float] = None              # D6.3：(IS-OOS)/|IS|；None = insufficient_signal
    account_total: Optional[float] = None             # D4 capital 判据的资金来源（虚拟账户 total）

@dataclass(frozen=True)
class ReadinessCriteria:
    oos_sharpe_min: float = 0.8
    oos_max_drawdown_max: float = 0.25
    is_oos_decay_max: float = 0.5      # (IS-OOS)/IS
    paper_days_min: int = 20
    paper_trades_min: int = 50
    ic_min: float = 0.02
    ic_lookback: int = 60

@dataclass(frozen=True)
class ValueCriteria:
    capital_min: float = 0.0           # 灰度→全量资金门槛（0 = 不启用）

@dataclass(frozen=True)
class GateCriteria:
    readiness: ReadinessCriteria = ReadinessCriteria()
    value: ValueCriteria = ValueCriteria()

@dataclass(frozen=True)
class GateDecision:
    action: GateAction
    reasons: tuple[str, ...]           # 命中的判据名（有序，确定性）
    target: Optional[LifecycleStage]   # GO/RECYCLE 的目标阶段

@dataclass(frozen=True)
class TransitionRecord:
    at: str                            # YYYY-MM-DD（调用方给，禁 datetime.now）
    action: str; from_stage: str; to_stage: str
    reasons: tuple[str, ...]; fingerprint: StrategyFingerprint
    evidence_source: str = ""
    account_snapshot: Optional[dict[str, Any]] = None

@dataclass(frozen=True)
class LifecycleRecord:
    fingerprint: StrategyFingerprint
    stage: LifecycleStage
    history: tuple[TransitionRecord, ...] = ()
```

**阈值一律标注「经验默认值（可配置）」**；§11.7 已声明外部锚点只证方向。

---

## 4. 决策

### D1 模块划分

`lifecycle` 只管**状态与决策**；`oos` 只管**证据生产**；`virtual_account` 只管**记账**。三者互不 import（`oos` 不 import `lifecycle`，`lifecycle` 只接受 `StageEvidence` 数据）。

> **例外（Step 6 F-I4 补注）**：`LifecycleError` 定义于 `core/lifecycle.py`，`core/oos.py` **仅 import 该异常类型**（D6.2 要求 oos 对 `initial_capital < 1e6` 抛 `LifecycleError`）。异常类型为零数据流、零行为耦合的纯类型依赖；D1 的实质约束「不共享数据、不回调决策逻辑」不被违反。`virtual_account` 不适用此例外（一律 `ValueError`）。

理由：Parnas 信息隐藏（R18）——三条变化轴（判据规则 / 回测口径 / 记账规则）分离。

### D2 迁移图（含退役唯一入边）

```
draft ──GO──> backtest ──GO──> paper ──GO──> gray ──GO──> live
   ▲              │              │            │            │
   └──RECYCLE─────┘              │            │            │
                  HOLD(原地)     │            │            │
                                 └──KILL──────┴──KILL──────┘
                            ↓ gray/live 两步；paper 一步
                                   retired（终态）
```

- **`retired` 唯一入边 = `paper`**：`gray`/`live` 的 KILL 在记录中落为**两条** `TransitionRecord`（`gray → paper`，reason=`kill_trigger`；`paper → retired`，reason 原判据）；**`paper` 自身的 KILL 只落一条**（`paper → retired`）。保证可审计且符合总纲 L207「降 paper → 归档」；
- `RECYCLE` 只从 `backtest` 出发 → `draft`，且必须携带**与历史所有记录均不同的新 `version`**（机制校验见 D8，F-D7）；
- 其余非法迁移 → `LifecycleError`（`ValueError` 子类）。

### D3 四值决策

对齐 R15（Stage-Gate 官方 Go/Kill/Hold/Recycle）：`Go` 前进并分配资源（此处=进入下一阶段）、`Hold` 原地待补证据、`Recycle` 打回重做、`Kill` 终止并归档。

### D4 判据评估顺序（确定性）

固定顺序：`oos_sharpe` → `oos_max_drawdown` → `is_oos_decay` → `ic` →（仅 paper→gray）`paper_days` → `paper_trades` →（仅 gray→live）`capital`。

- 全部通过 → `GO`；
- 仅因**样本类不足**（`paper_days` / `paper_trades` / 窗口数不足）→ `HOLD`；
- `oos_sharpe < 0` 或 `oos_max_drawdown > 2 × 阈值`（不可修复）→ `KILL`（paper 及其后）或 `RECYCLE`（backtest）；
- 其余不通过 → 该阶段 `HOLD`（backtest 阶段为 `RECYCLE`，因参数已不可调 → 需改参重来）。

### D5 证据模型与来源门

- `source` 三值；**paper 阶段的 GO 必须 `source == "paper_record"`**，否则 `HOLD(reason="evidence_source")`——防止用回测冒充 paper；
- 双条件 `paper_days >= 20 && paper_trades >= 50`（§11.2）；**DESIGN 承认：`source` 注入机制为本仓库工程选择，无外部先例**（§11.7）。

### D6 OOS 绩效产出器（U-P051c-15 / U-P051c-17）

**流程总览**：`core/oos.py::evaluate_strategy(dm, strategy, *, min_history: int, signal=None, tradable=None, splitter=..., initial_capital=10_000_000.0) -> OOSReport`；规格见 D6.1-D6.4（`min_history` 必填见 D6.1；`initial_capital` 下限校验见 D6.2）。

#### D6.1 视图构造约定（F-D1）

```python
W = min_history + 1     # 调用方显式传入（U-P051c-20 方案 A），不从策略反推
signal = pd.DataFrame(True, index=dm.trade_dates, columns=dm.stock_codes)  # 占位全集
views_all = BacktestAdapter.views_from_data(dm, signal, tradable=tradable, history_window=W)
usable = views_all[W:]                      # 前 W 个 view 的 history is None → 模板必抛错
frame = BacktestAdapter(strategy).signals_frame(usable)
head = pd.DataFrame(0.0, index=dm.trade_dates[:W], columns=frame.columns)
full = pd.concat([head, frame])
assert list(full.index) == list(dm.trade_dates)   # 否则 set_signal 直接 ValueError
```

- **min_history（N-1，方案 A）**：`evaluate_strategy(..., min_history: int)` **必填**。四模板的 min_rows 全部是**实例配置的函数**——grid `atr_period+1`（[grid.py L70](file:///f:/Coding/Factor_Trading_v3.0/strategies/grid.py#L70)）、trend `max(ma_n, entry_n, exit_n)`（[trend.py L57-62](file:///f:/Coding/Factor_Trading_v3.0/strategies/trend.py#L57-L62)）、momentum `max(lookbacks)`（[momentum.py L63](file:///f:/Coding/Factor_Trading_v3.0/strategies/momentum.py#L63)）、mean_reversion `lookback`（[mean_reversion.py L59](file:///f:/Coding/Factor_Trading_v3.0/strategies/mean_reversion.py#L59)）——且 `Strategy` Protocol 无该属性 → **不得按类名反推**（否则 lifecycle 只能评估四模板，第三方注册策略永久不可评估）；`min_history < 1` → `LifecycleError`。
- **signal 占位**：四模板只消费 `history` / `prices` / `state.positions`（P-051b 实证），`signal` 仅用于提供「日期 × 标的」全集 → 取**全 `True` 布尔框**（`tradable=None` 时视图 mask = `row.notna()`，亦全 True）；
- **tradable**：可选参数，默认 `None`；端到端测试传 `engine.universe.tradable`，生产由 P-053 提供；
- **预热段**：前 `W` 日必须补零（`head`）拼回，否则 index ≠ `dm.trade_dates`；**绩效排除预热段**（U-P051c-19）——所有指标只基于 `pv[W:]`，`warmup_days = W` 写入 `StageEvidence`；
- **样本不足**：`len(dm.trade_dates) <= W` → `LifecycleError("样本不足：需要 > W 个交易日")`。

#### D6.2 净值与窗口（F-D3）

```python
pv = run_engine(dm, full, initial_capital)
splitter = WalkForwardSplitter(dates=dm.trade_dates, train_size=..., test_size=..., purge_gap=...)
for win in splitter.split():          # 无参；Iterator[WalkForwardWindow]（walk_forward.py L111/L153）
    seg_test = pv.iloc[
        max(pv.index.searchsorted(win.test_start) - 1, W) :
        pv.index.searchsorted(win.test_end, side="right")
    ]
    seg_train = pv.iloc[
        max(pv.index.searchsorted(win.train_start) - 1, W) :
        pv.index.searchsorted(win.train_end, side="right")
    ]
```

- **窗口 API（N-2，实证）**：`WalkForwardSplitter.__init__(dates, train_size=252, test_size=63, purge_gap=5, method="rolling", ...)`（[walk_forward.py L111-L120](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L111-L120)）；`split()` **不接收参数**、返回 `Iterator[WalkForwardWindow]`（[L153](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L153)）；窗口字段为 `train_start/train_end/test_start/test_end/window_index`（[L51-L55](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L51-L55)）。
- **禁用 `win.test_dates` / `win.train_dates`**：二者用 `pd.date_range(..., freq="B")` **重建**日期（[L58-L65](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L58-L65)），工作日历 ≠ 实际交易日（不含中国节假日）→ 会错位/漏日。一律用 `win.*_start/*_end` 在 `pv.index` 上 `searchsorted` 定位**真实交易日**；端点非交易日时 `searchsorted` 自动落到相邻交易日，语义为「窗口日期区间内的全部真实交易日」。
- **段收益公式**：左锚 = `searchsorted(start) - 1`（段前一个真实交易日，且不小于 `W`）→ **段首日收益归本段**；右端 = `searchsorted(end, side="right")` 实现闭区间。continuous 语义下段首持仓继承自前序，这是自然推论，非任意选择；
- **`run_engine` 规格（N-4）**：签名 `run_engine(dm, full, *, initial_capital: float = 10_000_000.0) -> pd.Series`；cfg 取 `EngineConfig` 默认（P-044 既有，`commission_min=5.0` [config.py L194](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L194)），并以 `initial_capital` **覆盖** `cfg.initial_capital`（默认值同为 1e7，[config.py L408](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L408)）；返回**逐日组合价值** `pv`（Step 5 核对 engine_v2 的实际字段名）。**显式失败**：`initial_capital < 1e6` → `LifecycleError("资金过小：最低佣金 5 元将主导成本结构")`——防止「资金 1 元 → 数量压到 0 → 全程空仓 → OOS 指标全 0 → 晋级门静默失效」；
- **最短长度**：`len(seg) < 2` → 该窗口 `test_metrics = None`，reason=`window_too_short`，证据层整体记 `HOLD`（`compute_metrics` 的 `len>=2` 由此外置保证）；
- **聚合**：每个有效 test 段归一化 `seg / seg.iloc[0]`，依次连乘（起点 1.0）得 `agg_pv`，`aggregate = compute_metrics(agg_pv)`；
- **train 指标**：同公式，仅供 decay 使用，不参与聚合。
- **脚注（I1 例外，Step 6 F-I4/D-1 补注）**：`run_engine` 经 `BacktestEngineV2.run()` 产净值，而引擎的 `_generate_results` 无条件写报告/CSV（[L1763-L1768](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1763-L1768)、[L1839-L1848](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1839-L1848)）。因此 `run_engine` 以 `tempfile.TemporaryDirectory()` 作 `cfg.output_dir`、`write_manifest=False`，返回前销毁；三模块自身代码仍零 I/O（不读写业务路径、不 logging）。

#### D6.3 衰减（F-D2）

`is_oos_decay = (mean(IS sharpe) − mean(OOS sharpe)) / |mean(IS sharpe)|`；**`|mean(IS)| < EPS_SHARPE (= 0.1)` 或有效 IS 窗口数为 0 → 返回 `NaN`**。NaN 语义：判据名 `insufficient_signal` → `HOLD`（**既不是 GO，也不是 KILL**）——IS 无信号 ≠ 衰减。字段 `StageEvidence.is_oos_decay: Optional[float]`。

#### D6.4 滚动 IC（F-D5）

- 次日收益：`next_ret = dm.get_adj_price("close", "raw").pct_change().shift(-1)`（第 t 行对应 t+1 的 close/close 收益）；
- 逐日：`w = frame.iloc[t]`，仅取 `w > 0` 的标的，`ic_t = corr(w_sel, next_ret.iloc[t].loc[w_sel.index], method="spearman")`；
- **全零权重日 → NaN**（空仓无 IC 语义）；**有效标的 < 10 → NaN**（对齐 [stats.py L69-L72](file:///f:/Coding/Factor_Trading_v3.0/strategy_evaluation/stats.py#L69-L72)）；
- `ic_series` 只保留 OOS 段日期，供 `ic_min` 按 `ic_lookback` 取尾部均值。

**语义声明（U-P051c-17）**：默认 `continuous`——OOS 段是**同一连续回测的时间切片**，段首继承前序持仓，**不是独立重跑**。好处：口径与引擎 100% 一致、无窗边界伪影；代价：OOS 独立性解释弱于逐窗重跑。若 Step 5 核实 `engine_v2` 支持起始日/初始状态，再评估 `segmented` 模式。

**免责**：本批 IS/OOS 只用于**衰减度量与晋级证据**，**不做参数寻优**（寻优属超参搜索批次）。

### D7 虚拟账户与账本

```python
@dataclass(frozen=True)
class VirtualAccount:
    strategy_id: str; cash: float; reserved: float
    positions: Mapping[str, float]     # code -> 市值
    total: float
    # 变更（全部返回新实例）
    def allocate(self, notional: float) -> "VirtualAccount"        # 额度层：调整 cash/positions 目标
    def try_reserve(self, notional: float) -> tuple["VirtualAccount", bool]  # 订单层：cash→reserved
    def release(self, notional: float) -> "VirtualAccount"         # reserved→cash
    def fill(self, code: str, notional: float) -> "VirtualAccount"   # 以实际成交额入账

@dataclass(frozen=True)
class BudgetCheck:
    ok: bool; violations: tuple[str, ...]

def check_allocation(weights: Mapping[str, float], total: float, *, max_weight: float = 1.0) -> BudgetCheck
def check_book(accounts: Mapping[str, VirtualAccount], total: float) -> BudgetCheck  # Σ ≤ total + 容差
```

边界：`allocate`（额度）与 `try_reserve`（订单锁定）不重复记账（I8）；sleeve 与引擎共享现金的**对账属 P-053**（F-R7）。**`fill` 的差额规则（F-D6）**：`fill` 以实际成交额 `notional` 计（`reserved -= notional`、`positions[code] += notional`）；若成交额小于该单预留额，调用方须**先 `release(预留 − 成交)` 再 `fill(成交)`**（两步，守恒仍在每步成立）；`fill` 使 `reserved < 0` 时抛 `ValueError`。

### D8 指纹与版本

`StrategyFingerprint` 直接取 `StrategyMeta` 四件套（E4 已实证）。`version` 由策略作者维护，**不自动递增**；`RECYCLE` 的机制校验是「**新 `version` 与 `history` 中所有记录的 `version` 均不同**」（F-D7），否则 `LifecycleError`——`+1` 仅为推荐约定（SemVer 由作者维护，lifecycle 不做算术假设）。

### D9 归档

`archive(record, account=None) -> dict[str, Any]`：`{"schema_version": 1, "fingerprint", "final_stage", "history", "account", "unresolved": [...]}`；要求 JSON 往返一致、不含 NaN/Inf（I10）。**不写盘**（调用方决定位置，U-P051c-7）。

### D10 监控映射

`resolve_monitor_action(overall_level: str, stage: LifecycleStage) -> GateAction`（入参为字符串 `"green"|"yellow"|"red"`，**不 import agents**）：green→HOLD（记录）、yellow→HOLD（记录，建议复核）、red→KILL（paper 及其后，两步）/ RECYCLE（backtest）/ **HOLD（draft，Step 8 R-2 补注——draft 无 evidence 无从 KILL/RECYCLE，唯一合法动作；IMPL §3.1 `resolve_monitor_action` 定案）**。

### D11 重放

`replay(records: Sequence[TransitionRecord]) -> tuple[LifecycleStage, ...]`：逐条校验 `from_stage` 与当前一致，非法则 `LifecycleError`；返回各步 `to_stage`。**任意前缀重放必收敛到同一 stage**（I9）。

### D12 范围外置声明

| 项 | 处理 |
|----|------|
| 月度归因（总纲 L207） | 外置；生命周期只提供 `archive()` 快照供归因批次消费 |
| `core/strategy_registry.py`（L205 指名） | 不新建；**偏差声明**：指纹替代，理由 R14（MLflow 已弃用注册表内嵌 stage）+ 避免平行注册表 |
| U-P044-3 引擎重构 | 不做（U-P051c-4） |
| DSR/PBO（U-P051c-10） | `GateCriteria` **不设**这些字段（不假装支持）；文档承诺留待独立批次 |

---

## 5. 判据表（阈值均为可配置初值）

| 判据 | 字段 | 默认 | 失败后果 |
|------|------|------|----------|
| OOS 夏普 | `oos_sharpe_min` | 0.8 | backtest: RECYCLE；paper+: KILL（若 <0）或 HOLD |
| OOS 最大回撤 | `oos_max_drawdown_max` | 0.25 | 同上（>2× 阈值 → KILL） |
| IS-OOS 衰减 | `is_oos_decay_max` | 0.5 | HOLD（提示过拟合） |
| 滚动 IC | `ic_min` / `ic_lookback` | 0.02 / 60 | paper: HOLD；持续低于 → KILL |
| paper 时长 | `paper_days_min` | 20 | HOLD |
| paper 笔数 | `paper_trades_min` | 50 | HOLD（低频策略可调低或改比例式） |
| 证据来源 | `source == "paper_record"` | — | HOLD |
| 资金门槛 | `capital_min` | 0.0（不启用） | HOLD（gray→live） |

---

## 6. 不变式

| 编号 | 内容 |
|------|------|
| I1 | 三新模块纯函数、零 I/O、零 logging、无全局状态（**例外见 D6.2 脚注**：`oos.run_engine` 的引擎内部写盘限于函数内临时目录，返回前销毁；三模块自身代码 I/O 为零） |
| I2 | 非法迁移必抛 `LifecycleError`；合法迁移 100% 覆盖 |
| I3 | `retired` 唯一入边 = `paper`（gray/live 的 KILL 落两条记录） |
| I4 | `RECYCLE` 必须携带新 `version`，且历史只追加不修改 |
| I5 | 判据确定性：同 `(evidence, criteria, stage)` → 同 `GateDecision`（无随机、无 `now()`） |
| I6 | paper 阶段 GO 强制 `source=="paper_record"` |
| I7 | 账户守恒 `cash + Σpositions + reserved == total`（1e-9） |
| I8 | `reserved` 只从 `cash` 划出；`allocate` 与 `try_reserve` 不重复记账 |
| I9 | 迁移前缀重放收敛（总纲 L210） |
| I10 | 归档 JSON 往返稳定、无 NaN/Inf |
| I11 | 零退化：既有 1091 passed + 22 golden 零重录；`sizing/engine_v2/stops/volatility/registry/_golden_cases` 零 diff |

---

## 7. 测试策略（Step 5 落实，Step 6 复审）

| 组 | 覆盖 | 预估 |
|----|------|------|
| L | 迁移合法性（含 I2/I3/I4）、四决策、KILL 两步、RECYCLE 版本、确定性（I5） | 14 |
| G | 各判据单点 + 优先级顺序 + 双条件 + source 门（I6） | 10 |
| O | 窗口切分、**warmup 排除（U-P051c-19）**、**`searchsorted` 段边界（含非交易日端点）**、短窗 → HOLD、聚合连乘、**decay NaN → insufficient_signal**、**IC 全零 / <10 标的 → NaN**、**`min_history<1` 抛错**、**`initial_capital<1e6` 抛错**、无前视（构造未来数据不变式） | 11 |
| A | 守恒（I7）、reserve/release/fill、超额、`check_book`、语义不重复（I8） | 10 |
| R | 归档往返（I10）、重放（I9） | 5 |
| E | 四模板端到端（参数化 4）、golden 零重录 | 3 |
| **合计** | | **≈53（Step 5 精确化）** |

pytest 目标：1091 + 53 ≈ **1144**（RESEARCH §7 的 ≥1131 区间内）。

---

## 8. 与总纲的偏差（须在 Step 4 复审确认）

| 总纲 | 本设计 | 理由 |
|------|--------|------|
| L205 `core/strategy_registry.py`（版本化注册） | 不新建，用指纹 | R14；避免平行注册表 |
| L207 月度归因 | 外置 | R20/R21（单期模型 + 多期链接成本） |
| L207「降 paper → 归档」 | 保留，KILL 两步实现 | 与 D2 一致 |
| L209 虚拟子账户 | 纯账本，不接引擎 | U-P051c-3；引擎对账归 P-053 |
| L210 任意时点重放 | I9 迁移重放 + 归档快照 | 已覆盖 |

---

## 9. 风险与未决

| 编号 | 风险 | 处置 |
|------|------|------|
| R1 | **continuous 切片的 OOS 独立性弱于逐窗重跑**（U-P051c-17） | DESIGN 显式声明；Step 5 核实 `engine_v2` 是否支持起始日，若支持则加 `segmented` 模式 |
| R2 | 判据阈值无外部权威值（§11.7 诚实边界） | 全部可配置；测试锁迁移规则不锁数值 |
| R3 | IC 自实现与 `calculate_ic` 可能存在边界差（<10 标的返回 NaN） | 对齐其 `len(common) < 10 → NaN` 规则；O 组用例锁定 |
| R4 | `signals_frame` 过滤 0 权重（E5 实证），grid 的显式 0 会消失 | 对绩效无影响（0 权重=空仓），文档记录 |
| R5 | 虚拟账户与真实共享现金的语义差 | 边界写入 D7；对账归 P-053 |
| **U-P051c-18**（新） | 是否提供 `segmented` 模式 | Step 5 依 `engine_v2` 能力裁决，默认不做 |

---

## 10. 出口条件（Step 3 → Step 4）

1. 20 项裁决全部有定案（§0 已满足）；
2. 数据契约、决策表、不变式、测试策略齐备（本文件）；
3. 与总纲偏差逐条声明（§8）；
4. 由**异构基座（GLM-5.3-Flash）**执行 Step 4 复审，出口要求 **0 P1**。
