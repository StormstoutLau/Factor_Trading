# DESIGN：P-047 仓位管理（position sizing）+ U-P031-2 现金闸门

> **批次**: P-047 · **Step 3 设计** · 日期 2026-11-18
> **判档**: **T1**（新建 `core/sizing.py` 纯函数契约 + `tests/` + golden；`core/engine_v2.py` 单点 BUY 现金闸门）
> **上游**: [RESEARCH_p047](RESEARCH_p047_position_sizing.md)（§4 G1-G11 / §5 M-A+A2 / §6 B1-B5 / §7 S1-S11 / §8 I1-I10 / §9 U-P047-1..5 / §13 Step 2 **有条件通过**：F1 MEDIUM + F2 LOW + F3-F6 INFO / §3.3-补 D1-D6、X16-X18）
> **代码证据时点**: HEAD `531795e`（工作区仅两份文档未提交，代码零 diff）
> **基座**: DeepSeek-V4.1-Flash（Step 4 Review 须异构 GLM-5.3-Flash；U-P047-5 于 Step 10 终审闭合）

---

## 1. 范围与前置

**做**（B1 → B2 → B3 → B4 → B5；**B1 范围收窄声明 F-S8-P047-1**：RESEARCH §6 B1 的波动原语 `estimate_volatility`/`atr` **不落本批**——sizing 层输入为**外部传入** `cov` 与 `atr`（M-A 纯函数解耦，波动估计随 P-051 接线批/数据层批次落地；`SizingConfig.vol_lookback/atr_period/atr_k` 为**预留字段，本批零消费**，见 §12 D-R3））：
1. `core/sizing.py`（新建）：`SizingConfig` / `SizingState` / `SizingResult` / `RiskContribution` / `CashBudgetResult` + **7 个纯函数**（§3.1；含 `holding_age` 持仓龄证明——§1 首版漏列，F-S8-P047-6 订正；`estimate_buy_cash` 见做②）；
2. 现金预算原语 `estimate_buy_cash`（**唯一口径**，sizing 与引擎共用）；
3. 测试 `tests/test_p047_position_sizing.py`（V1-V12）+ golden `tests/golden/p047/`（3 例）；
4. `core/engine_v2.py` `_process_pending_orders` **仅 BUY 分支**插入现金闸门（A2，U-P031-2 闭合）；
5. 四文档 + 台账。

**不做**：做空/负权重（P-050）；非等风险预算求解（P-046）；止损/择时契约修改（P-045 已交付，只消费权重）；策略模板/多策略资金分配（P-051）；引擎主循环其他任何语义变更；`core/config.py` 新增字段；`RiskParityOptimizer` 重写；订单层 size_type（P-053）。

**前置**（E3 @`531795e`）：`core/sizing.py` 不存在；`tracker.execute_trade` 无现金检查（L200-204）；队列路径无现金检查（L841-935）；次日路径 `qty*open*1.002` 整单跳过（L1257-1261）；`estimate_buy_cash` 需与 [execution.py L384-405](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L384-L405) 同源。

---

## 2. 设计决策

### 2.0 上游未决裁决（RESEARCH §9 + §13 F1-F6）

| 未决 | 裁决 | 落点 |
|------|------|------|
| **F1 费式（MEDIUM）** | **精确成本式**：`amount + max(amount·commission_rate, commission_min) + amount·slippage_pct`，与 `ExecutionSimulator._calculate_cost` 逐项同源；**废除** S11② 的 `exec_price·qty·(1+commission_rate)`（漏滑点 + 漏最低佣金）。回退条件见 §7 R1 | D4 / D5 |
| **R1 排序** | **不重排**：保持队列插入顺序（D4 证据：`list.append` 顺序；改序=行为变更），接受「同日先买后卖多跳过」，登记 P-048 观察项 | D5 / §7 R2 |
| **U-P047-2 风险预算** | **只做诊断**（`risk_contributions`）+ 等预算复用 `RiskParityOptimizer` 对拍（I10）；非等预算归 P-046 | D3 / I10 |
| **U-P047-3 默认参数** | `method="none"`；`kelly_fraction=0.5` / `target_vol=0.15` / `vol_lookback=60` / `atr_period=14` / `atr_k=2.0` / `granularity=100` / `cash_buffer=0.985`；金字塔默认关闭 | D2 / §3.1 |
| **U-P047-4 golden** | **3 例**：`P047_S1_kelly` / `P047_S2_vol_target` / `P047_S3_cash_budget`，置 `tests/golden/p047/` + 独立 `GOLDEN_DIR` 装载（`tests/test_p047_position_sizing.py`）；`-k golden` 15 → **18** | D6 |
| **F4 量化不动点** | 预算缩减后**统一 floor 量化 + 断言**（不做二次 ceil）；`estimate_buy_cash` 用 floor 后数量计算 | D4 |
| **F5 容差** | 闸门用**严格 `<`**（无 `1e-9`），与既有 L1259 同式 | D5 |
| **F6 σ_p=0** | `scale=1.0` 且 `diagnostics.reason="zero_vol"`；warning 由接线方（P-051）落地——本批纯函数层零副作用（I4/D1 依赖白名单无 logging）【Step 6 订正 F-S6-P047-2】 | D3 |
| **F2 措辞** | 测试规格中以「未断言引擎行为」替代「无断言」 | §5 |
| **F3 计数口径** | 全部计数以 `-k golden` 收集数为准，备注口径 | D6 / I1 |

### D1 模块职责与放置

| 模块 | 职责 | 依赖 |
|------|------|------|
| `core/sizing.py`（新建） | 目标权重 → 可执行目标权重；风险贡献诊断；现金预算；金字塔增量；持仓龄 | 仅 `numpy` / `pandas` / `dataclasses` / `typing`；**不 import `core.tracker` / `core.engine_v2` / `core.config`**（保持纯函数、无 I/O、无全局态） |
| `core/engine_v2.py`（改） | 队列路径 BUY 现金闸门（调用 `estimate_buy_cash`） | 仅新增 1 个 import + `_process_pending_orders` 内 BUY 分支 |

**裁决：`estimate_buy_cash` 放 `core/sizing.py`**，理由：①sizing 预算法（S9）与引擎闸门（S11）必须**同式**，同模块即单一真值源；②避免 sizing → `core.execution` 的跨层依赖；③引擎已 import 多个 `core.*`，新增一个 import 不改变依赖方向（`engine_v2` 本就是装配层）。

**不提供** `apply_sizing` 的引擎接线：默认 `method="none"` + `build_target_positions` 仍是权重→整手唯一出口（G4 边界见 §4）。

### D2 类型模型

```python
@dataclass(frozen=True)
class SizingConfig:
    method: Literal["none", "kelly", "vol_target", "risk_parity"] = "none"
    #                              ^ F-S8-P047-3：RESEARCH S1/U-P047-2 术语 `risk_budget` 本批定名 `risk_parity`（语义一致：风险贡献诊断）
    kelly_fraction: float = 0.5          # 0 < f <= 1（合法性校验）；X1 推荐运行区间 [0.25,0.5] 为文档约束（F-S8-P047-5）
    target_vol: float = 0.15             # 年化（X2）
    vol_lookback: int = 60               # 交易日（X17）【预留，本批零消费，D-R3】
    atr_period: int = 14                 # Wilder（X6）【预留，本批零消费，D-R3】
    atr_k: float = 2.0                   # Turtle 2N（X7）【预留，本批零消费，D-R3】
    max_weight: float = 1.0
    min_weight: float = 0.0
    max_size: Optional[float] = None      # 单标的金额上限（元）
    min_size: Optional[float] = None      # 单标的金额下限（元），过滤后余额留现金
    granularity: int = 100
    cash_buffer: float = 0.985            # 与 build_target_positions L51 同值
    commission_rate: float = 0.0003       # 与 CostConfig L187 同默认
    commission_min: float = 5.0
    slippage_pct: float = 0.001
    pyramid_enabled: bool = False         # 默认关闭（X15 证据冲突）
    pyramid_max_adds: int = 3
    pyramid_decay: float = 0.5
    pyramid_step_atr: float = 1.0         # F-S8-P047-4：RESEARCH S1/X7 原锚 0.5N，本批收紧 1.0·ATR（更少加仓更保守；X15 冲突按保守侧处理）
```

```python
@dataclass(frozen=True)
class SizingDiagnostics:
    reasons: Mapping[str, str]            # code -> reason（zero_vol/dropped_min_size/clipped_max_weight/...）
    dropped: tuple[str, ...] = ()
    clipped: tuple[str, ...] = ()

@dataclass(frozen=True)
class SizingResult:
    weights: Mapping[str, float]          # 最终目标权重（JSON 安全）
    scale: float
    diagnostics: SizingDiagnostics

@dataclass(frozen=True)
class RiskContribution:
    rc: Mapping[str, float]               # RC_i = w_i(Σw)_i/σ_p
    pct: Mapping[str, float]              # 占比，和=1（σ_p>0）

@dataclass(frozen=True)
class CashBudgetResult:
    weights: Mapping[str, float]
    buy_cost: float
    budget: float
    scale: float

@dataclass(frozen=True)
class SizingState:                        # 金字塔状态（可序列化，P-051 可存 extras）
    entry_price: float
    last_add_price: float
    add_count: int = 0
```

- 所有 dataclass `frozen=True`；`Mapping` 字段用普通 dict 存储（不引入 DataFrame，保证 JSON 可序列化，S10）；
- 权重入参用 `Mapping[str, float]`（不绑定 pandas），价格用 `Mapping[str, float]`；
- 协方差入参 `np.ndarray` + `codes: Sequence[str]`（顺序对齐，fail-fast 校验）。

### D3 方法契约（S1-S8 细化）

| 函数 | 语义 | 边界 |
|------|------|------|
| `kelly_fraction_scale(expected_return, variance, *, fraction)` | `f* = μ/σ²`；`scale = clip(fraction·f*, 0, 1)`；`variance<=0` → `0.0` + `zero_var` | μ 必须为**可估计收益**（X1），负 μ → 0；**对角近似声明（F-S8-P047-2）**：RESEARCH S4 的矩阵式 `f=Σ⁻¹μ` 简化为**逐标的 μ/σ²** + `apply_sizing` 组合层 `scale=新和/旧和`——避免满秩求逆的数值病态与高相关标的的过度集中；矩阵式凯利归 P-046 |
| `vol_target_scale(weights, cov, *, target_vol)` | `σ_p = sqrt(wᵀΣw)`；`scale = min(target_vol/σ_p, 1.0)`（**不加杠杆**，X2） | `σ_p==0` → `scale=1.0` + `zero_vol`（F6） |
| `risk_contributions(weights, cov)` | `RC_i = w_i(Σw)_i/σ_p`；`pct = RC/σ_p`；和=1 | `σ_p==0` → rc/pct 全 0（`RiskContribution` 无 reason 载体，零波动语义由全 0 表达）【Step 6 订正 F-S6-P047-4】；**只诊断，不求解**（U-P047-2） |
| `apply_sizing(weights, *, config, cov=None, expected_returns=None)` | 按 `method` 分派：`none` 原样返回（**零行为**）；`kelly` 逐标的缩放；`vol_target` 组合缩放；`risk_parity` 仅输出诊断（权重不变）；再裁剪 `[min_weight, max_weight]` 与 `[min_size, max_size]`；总权重 `>1` 等比缩放 | 未知 code 处置**仅 kelly 方法**（保持原权重 + `no_cov`）；`vol_target`/`risk_parity` 要求 `weights` ⊆ `codes`，越界 `ValueError`（fail-fast）【Step 6 订正 F-S6-P047-3】；`min_size` 过滤后**不归一**（余额留现金，S8） |
| `pyramid_step(state, *, price, atr, config)` | 仅 `price ≥ entry_price` 且 `price ≥ last_add_price + pyramid_step_atr·atr` 且 `add_count < max_adds` → 增量 `decay^add_count`；否则 0 | `price < entry_price` → **永不加仓**（禁摊亏）；`pyramid_enabled=False` → 恒 0 |
| `holding_age(entry_date, current_date, trade_dates)` | 返回 `trade_dates` 中 `> entry_date` 且 `<= current_date` 的 bar 数（建仓日=1） | `current_date < entry_date` → `ValueError`；纯函数，不读状态 |

### D4 现金预算（S9 + F4）

```python
def estimate_buy_cash(amount, *, commission_rate, commission_min, slippage_pct) -> float:
    """买入成交所需现金（与 ExecutionSimulator._calculate_cost 同源）。"""
    if amount <= 0:
        return 0.0  # F-S4-P047-2：qty=0 空单不计成本（否则 max(0, min)=5 污染预算，探针 P5）
    commission = max(amount * commission_rate, commission_min)
    return amount + commission + amount * slippage_pct
```

> **同源限定（F-S4-P047-5）**：「同源」指默认 `AssetType.STOCK` 且无 `CostConfig.asset_costs` 覆盖的路径；`asset_costs` 对 `commission_rate` 的按资产覆盖不在本批（闸门取 `cfg.cost` 通用字段，为保守近似）。

- **`cash_budget_scale(weights, *, cash, prices, total_value, config)`**：
  1. `qty_i = floor(weight_i·total_value·cash_buffer / price_i / granularity)·granularity`（**floor**，F4）；
  2. `buy_cost = Σ estimate_buy_cash(qty_i·price_i, ...)`；
  3. `budget = cash·cash_buffer`；`buy_cost > budget` → `scale = budget/buy_cost`，权重乘 `scale` 后**重新 floor 量化并复算**（单次迭代；仍超则按同式再缩一次，最多 3 次，仍超 → `scale=0` + `cash_budget_exhausted`）；
  4. **只用当前现金**，不含当日卖出回款（G10）；
  5. 返回 `CashBudgetResult`（含实算 `buy_cost` 与 `budget`，供诊断/测试断言）。
- 断言：`buy_cost <= budget + 1e-6`（测试口径，非运行期容差）。

### D5 引擎闸门（S11 修订版，A2）

**位置**：`_process_pending_orders`（L841-935）BUY 分支，在 `is_valid_price` 校验（L900-902）之后、`executor.execute_order(...)`（L909-911）**之前**。

```python
# 仅 BUY 分支新增（伪码；tracker 为 L849 既有局部别名，F-S4-P047-3）
amount = open_price * order.quantity
required_cash = estimate_buy_cash(
    amount,
    commission_rate=self.cfg.cost.commission_rate,
    commission_min=self.cfg.cost.commission_min,
    slippage_pct=self.cfg.cost.slippage_pct,
)
if tracker.get_cash() < required_cash:          # 严格 <，F5
    logger.warning(
        "BUY 现金不足，整单跳过（保留队列）: %s qty=%d 需要=%.2f 可用=%.2f",
        order.stock, order.quantity, required_cash, tracker.get_cash(),
    )
    continue                                      # 不成交、不扣款、不改数量；订单保留
```

- **不做**：不改遍历顺序（R1）、不新增配置开关、不资金预支、不做部分成交、不改 SELL 路径；
- **闸门跳过 ≠ execute 失败（F-S4-P047-4）**：`continue` 直接进入下一单，**不会**触发 L919-922 的 `enable_fallback` 替补逻辑（该逻辑仅在 `execute_order` 返回失败后触发）；闸门语义 = 保留队列等现金回补，IMPL 不得将闸门改写为「execute 后判失败」；
- **BUY 的 `order.quantity` == 实际执行的 `qty`**（`_clamp_sell_quantity` 对 BUY 原样返回，L766-767），amount 口径无歧义；
- **回退条件（R1）**：若 Step 9 golden 出现差异且差异来源=「小额单临界现金」，则闸门改用既有字面 `1.002`（`required_cash = amount*1.002`），sizing 侧仍用精确式；
- `self.cfg.cost` 字段名以 [config.py L187-190](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L187-L190) 为准（`commission_rate` / `commission_min` / `slippage_pct`）。

### D6 golden：规格锁定（U-P047-4）

| case | 输入 | 锁定内容 |
|------|------|----------|
| `P047_S1_kelly` | 2 标的（A/B）、固定 μ/σ²（对角）、`fraction=0.5` | `scale` 与最终权重逐值（验证 `f*=μ/σ²` 逐标的缩放；负 μ→0 / `σ²=0` 边界由 V3 单测覆盖） |
| `P047_S2_vol_target` | 2 标的固定协方差（含非对角项）、`target_vol=0.15` | `σ_p`、`scale`、缩放后权重（验证 `wᵀΣw` 与不加杠杆） |
| `P047_S3_cash_budget` | 2 标的（A/B）、`cash=60000`、`total_value=100000`、`granularity=100`、费率默认 | `qty`（floor）、`buy_cost`、`scale`、最终权重（验证预算不超 + 3 次等比收缩 + floor 整手；最低佣金临界由 V8/V9 单测覆盖） |

- 放置：`tests/golden/p047/`，由 `tests/test_p047_position_sizing.py` 内独立 `GOLDEN_DIR` 装载（沿用 P-045 模式，D6 证据）；
- **不触碰** `tests/golden/*.json` 与 `tests/_golden_cases.py`（根断言 `glob("*.json")==set(CASE_IDS)` 零影响）；
- 计数：`-k golden` 15 → 18（F3 口径：收集数）。
- **Step 5 落地夹具（F-S5-P047-3）**：夹具规模按实际落地收窄（S1 3→2 标的、S3 5→2 标的且 `cash` 100000→60000），未削弱所锁定的算式关系；负 μ / `σ²=0` / 最低佣金临界三条边界由 V3 / V5 / V8-V9 单测直接覆盖。

### D7 零行为边界

1. `SizingConfig.method="none"` → `apply_sizing` 返回**输入权重副本**（逐值相等），`scale=1.0`；
2. 本批**不接线** `apply_sizing` 到引擎/policy/多策略路径；`build_target_positions` 零改动；
3. `engine_v2.py` diff **仅限**：①1 个 import；②`_process_pending_orders` BUY 分支闸门；③（如需要）`logger` 代码无新增；
4. golden 15 零重录为 I1 硬门禁（Step 9 复跑）。

---

## 3. 精确签名

### 3.1 `core/sizing.py`（新建）

```python
def estimate_buy_cash(amount: float, *, commission_rate: float,
                      commission_min: float = 5.0,
                      slippage_pct: float = 0.0) -> float: ...

def kelly_fraction_scale(expected_return: float, variance: float, *,
                         fraction: float = 0.5) -> tuple[float, str]: ...

def vol_target_scale(weights: Mapping[str, float], cov: np.ndarray, *,
                     codes: Sequence[str], target_vol: float = 0.15
                     ) -> tuple[dict[str, float], float, str]: ...

def risk_contributions(weights: Mapping[str, float], cov: np.ndarray, *,
                       codes: Sequence[str]) -> RiskContribution: ...

def apply_sizing(weights: Mapping[str, float], *, config: SizingConfig,
                 cov: Optional[np.ndarray] = None,
                 codes: Optional[Sequence[str]] = None,
                 expected_returns: Optional[Mapping[str, float]] = None,
                 total_value: Optional[float] = None,
                 prices: Optional[Mapping[str, float]] = None) -> SizingResult: ...

def cash_budget_scale(weights: Mapping[str, float], *, cash: float,
                      prices: Mapping[str, float], total_value: float,
                      config: SizingConfig) -> CashBudgetResult: ...

def pyramid_step(state: SizingState, *, price: float, atr: float,
                 config: SizingConfig) -> tuple[SizingState, float]: ...

def holding_age(entry_date: pd.Timestamp, current_date: pd.Timestamp,
                trade_dates: pd.DatetimeIndex) -> int: ...
```

**契约**：全部无副作用；不 print；不读文件；异常仅 `ValueError`（形状/参数非法）与 `KeyError`（缺价格）——后者调用方用 `prices.get` 规避。

### 3.2 `core/engine_v2.py`（最小 diff）

- 新增：`from core.sizing import estimate_buy_cash`；
- `_process_pending_orders` BUY 分支：§2 D5 伪码落地（约 9 行）；
- **无其他改动**（不得调整函数签名/顺序/日志文案之外的行为）。

### 3.3 `tests/` 与 golden

- `tests/test_p047_position_sizing.py`：V1-V12（§5），独立 `GOLDEN_DIR = Path(__file__).parent / "golden" / "p047"`；
- `tests/golden/p047/P047_S1.json` / `P047_S2.json` / `P047_S3.json`（`case_id` 分别为 `P047_S1` / `P047_S2` / `P047_S3`；D6 表中的 `P047_S1_kelly` 等为**用例标签**，非文件名）；
- 快照内容含 `inputs` / `config` / `expected` / `tolerance`（浮点保留 `repr` 精度，比较用 `pytest.approx`，`P047_S3` 因闭式反推取 `atol=1e-6`）。

---

## 4. 数据流与边界

```
weights(策略/优化器) ──apply_sizing(method/cov/expected_returns)──▶ 目标权重
                                                        │
                          cash_budget_scale(cash,prices,total_value) │
                                                        ▼
                                     build_target_positions(0.985, floor lot)  ← 唯一整手出口
                                                        │
                                             T+1 开盘 → pending 队列 / 次日路径
                                                        ▼
                              engine BUY 现金闸门（estimate_buy_cash）→ 成交或整单跳过
```

**边界**：
1. **sizing 不做整手**：`granularity=100` 仅用于预算估算与 `min_size/max_size` 过滤；最终整手由 `build_target_positions` floor 落地（避免双重量化）；
2. **T+1 不变**：sizing 只改权重数值，不改「T 决策 / T+1 开盘」时序；`holding_age` 仅提供口径证明；
3. **不使用 `get_total_value()` 做盘中真值**（G7）：sizing 的 `total_value` 由调用方传入（策略层用 `compute_portfolio_value` 口径）；本批不接线，故不引入新风险；
4. **卖出侧**不受预算限制（清仓项必须保留）；
5. **多策略路径**（`multi_strategy_engine`）本批不接线，接口签名已兼容 `Mapping[str, float]`。

---

## 5. 测试规格（`tests/test_p047_position_sizing.py`，12 用例）

| # | 用例 | 断言 |
|---|------|------|
| V1 | `method="none"` 幂等 | 输出权重 == 输入（逐值），`scale==1.0` |
| V2 | 凯利闭式 | `μ=0.10, σ²=0.04, f=0.5` → `scale=1.0`（`0.5·2.5>1` 裁剪）；`μ=0.01` → `0.125` |
| V3 | 凯利边界 | 负 μ → 0；`variance=0` → 0 + `zero_var`；`fraction<=0` → `ValueError` |
| V4 | vol-target 闭式 | 2 标的手算 `σ_p` 与 `scale`；`scale<=1` 恒成立（不加杠杆） |
| V5 | σ_p=0 | `scale==1.0` + `reason=="zero_vol"` |
| V6 | 风险贡献 | `ΣRC ≈ σ_p`、`Σpct ≈ 1`；等权等相关时 `pct≈1/n`；I10 对拍构造 `OptimizerConfig(max_weight=1.0)`（默认 `0.10` 的 clip+归一化会破坏 ERC 解 → 探针 P2a/P2b，F-S4-P047-1） |
| V7 | 权重/金额裁剪 | `max_weight` 生效且总权重 ≤1；`min_size` 过滤后余额留现金（不归一） |
| V8 | 现金预算 | 构造超预算组合 → `buy_cost <= budget+1e-6`、floor 整手、最低佣金计入；`qty=0` 标的计成本 0（F-S4-P047-2） |
| V9 | 成本同源 | `estimate_buy_cash(amount) == amount + ExecutionSimulator._calculate_cost(amount, BUY)`（净现金式，探针 P1 口径；`amount≥5000` 与 `<5000` 小额、`amount=0` 三档） |
| V10 | 金字塔 | 浮亏不加；满足步长加仓且递减；`add_count` 达上限停止；`pyramid_enabled=False` 恒 0 |
| V11 | 持仓龄 | 建仓日=1；跨周末按交易日计；`current<entry` → `ValueError` |
| V12 | 引擎闸门（A2） | 小额现金 + 超额 BUY → 不成交、现金非负、队列长度不变、返回继续处理后续订单 |

> 说明（F2）：V12 是**首个直接断言引擎现金行为**的测试；既有 `test_b3_insufficient_cash` 未调用引擎、未断言引擎行为，本批不修改该文件。

---

## 6. 不变式与门禁口径

| 不变式 | 口径 | 取证 |
|--------|------|------|
| I1 零行为 | 默认 `method="none"` + `engine_v2` diff 限 §2 D7；golden 既有 15 零重录 | Step 9：`git diff` + golden |
| I2 现金非负 | 闸门生效后 `tracker.get_cash() >= 0`（队列路径与次日路径均不产生负现金） | V12 + 引擎级用例 |
| I3 成本恒等 | `estimate_buy_cash` 与 `ExecutionSimulator` 同源（V9）；现金流恒等式复用 `check_v3_cost_identity` | V9 |
| I4 纯函数 | `core/sizing.py` 无 I/O、无全局态、无 random、无时间读取（`holding_age` 显式传参） | AST/静态检查 |
| I5 不加杠杆 | vol-target `scale<=1`；`max_weight<=1`；总权重 ≤1 | V4 / V7 |
| I6 禁摊亏 | 金字塔 `price<entry_price` 恒 0 | V10 |
| I7 预算保守 | 只用当前现金、floor 量化、`buy_cost<=budget` | V8 |
| I8 计数链 | `-k golden` 15 → 18（收集数口径） | Step 9 复跑 |
| I9 无配置扩散 | `core/config.py` **零改动**（`SizingConfig` 独立 dataclass） | git diff |
| I10 等预算对拍 | `risk_contributions` 等权输入 + `RiskParityOptimizer`（**显式 `OptimizerConfig(max_weight=1.0)`**，F-S4-P047-1）输出 → `pct≈1/n`；「clip 后非 ERC」为既有优化器已知行为，登记 P-046（G9 不改） | V6 扩展断言 |

---

## 7. 风险与回退

| ID | 风险 | 触发条件 | 回退 |
|----|------|----------|------|
| R1 | 精确成本式导致既有 golden 差异（小额+临界现金用例） | Step 9 golden 15 出现 diff | 闸门回退字面 `1.002`（`amount*1.002`）；sizing 侧保留精确式；DESIGN 双式并存需在 IMPLEMENTATION 注明 |
| R2 | 同日先买后卖多跳过 | 队列插入顺序先 BUY 后 SELL 且现金不足 | 接受（保守）；登记 P-048；不改顺序 |
| R3 | 量化不动点（缩减后复算仍超） | 极端 `granularity`/低价股 | 最多 3 次迭代 → `scale=0` + `cash_budget_exhausted`（宁可空仓不超支） |
| R4 | `σ_p` 估计不稳（回看期短、样本少） | `bars < vol_lookback` | 【Step 8 订正 F-S8-P047-1】本批 `σ_p` 由**调用方**传入（B1 波动原语不落本批），`insufficient_history` 诊断与样本充足性判定**随波动原语批次（P-051 数据层）落地**；本批仅保证：`σ_p==0 → scale=1.0`（zero_vol，F6）且 `scale<=1` 恒成立（不放大） |
| R5 | 最低佣金对小单影响 | `amount < 5,000` 元时精确成本率 > `1.002` 隐含的 0.2%；`amount < 16,667` 元时 5 元最低佣金主导 | 预算式已计入；`min_size` 默认 `None`，不擅自过滤 |

---

## 8. 与后续批次的接口约定

| 批次 | 约定 |
|------|------|
| P-046 | 非等风险预算求解、BL/HRP；本批 `risk_contributions` 可直接复用为诊断 |
| P-048 | R1/R2 观察项；风险动作 → 订单闭环 |
| P-050 | 负权重/做空：`apply_sizing` 对负权重 fail-fast（本批即拒绝，签名不变） |
| P-051 | 多策略资金分配：`SizingResult` 可直接序列化进 `extras`；`SizingState` 已 frozen |
| P-053 | 订单 `size_type`：本批只输出目标权重，不触碰订单类型 |

---

## 9. 设计期发现

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-D3-P047-1 | INFO | `build_target_positions` 的 `0.985` 与 `SizingConfig.cash_buffer` 同值不同源（前者硬编码） | 本批不合并（避免改 `target_positions.py`）；IMPLEMENTATION 注明「同值约定」，后续批次统一 |
| F-D3-P047-2 | INFO | `estimate_buy_cash` 放 sizing 而非 `execution.py`，引擎 import 方向为 `engine_v2 → sizing`（装配层依赖，可接受） | 已在 D1 裁决；若 Step 4 认为越界，可改放 `core/execution.py` 并让 sizing 反向 import（会引入 sizing→execution 依赖，不优） |
| F-D3-P047-3 | INFO | `commission_min` 使小额单费率非线性，`1.002` 与精确式在小额区差异最大 | 已由 V9 双场景断言覆盖 |

---

## 10. Step 4 Review（异构，已回填）

> **评审基座**: GLM-5.3-Flash（≠ 正文作者 DeepSeek-V4.1-Flash）→ **异构复审成立**（Step 2/4 连续两轮异构；U-P047-5 维持至 Step 10）。
> **评审日期**: 2026-11-18 · 对象：§2.0 裁决表 / D1-D7 / §3 签名 / §4 数据流 / §5 V1-V12 / §6 I1-I10 / §7 R1-R5 / §9 发现。
> **取证方式**: E1 重放（Glob/Grep）+ E2 运行时探针（`%TEMP%\p047_s4_probe.py`，Python 3.12，只读）+ E3 静态读码 @工作区（HEAD `531795e`，代码零 diff）。**零预填，本节为评审后回填。**

### 10.1 探针证据（E2 运行时，31 断言全 PASS）

| 组 | 输出 | 结论 |
|----|------|------|
| P1（D4/V9 同源对拍） | 10 档 amount（1,000 → 1,000,000）：`amount + _calculate_cost(amount, BUY)` 与 `estimate_buy_cash` **逐位相等**（<1e-9）；与字面 `1.002` 差值：小额 **+4.00**（a=1000）、a=5000 处 **0.00**、大额 **−700**（a=1M） | 精确式同源实证 ✓；`1.002` 仅在 a=5000 恰等、双侧皆可低估 → R1 回退条款必要性实证 ✓ |
| P2a（I10 默认构造） | `OptimizerConfig` 默认（`max_weight=0.10`）下 `RiskParityOptimizer.optimize` 输出**等权** [1/3,1/3,1/3]，其 pct=[**0.158, 0.322, 0.520**] ≠ 1/3 | **I10/V6 按字面实现必 FAIL** → F-S4-P047-1（P2） |
| P2b（I10 放宽构造） | `max_weight=1.0` 时真 ERC 解 w=[0.4616, 0.3040, 0.2344]，pct=[1/3, 1/3, 1/3] ✓ | 根因 = `optimize` 尾部 `_apply_constraints`（[portfolio.py L389](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L389)）clip+归一化破坏 ERC → 处置：I10/V6 构造显式 `max_weight=1.0`；「clip 后非 ERC」登记 P-046（G9 不改） |
| P3（D2 算术临界） | a=4999 → rate=0.002000+（>0.2%）；a=5000 → 恰 0.002；a=16666 → `5 > 4.9998`（最低佣金主导）；a=16667 → `5.0001 > 5`（按率主导） | 5,000 / 16,667 两临界**精确成立** ✓ |
| P4（D4/R3 预算迭代） | 场景 1（2 标的超预算）：iter0 即收敛（floor 量化天然保守）；场景 2（qty floor→0）：收敛但 `buy_cost=5.00` | qty=0 空单仍计最低佣金 5 元 → F-S4-P047-2（P3）；floor 量化下「最多 3 次迭代」上限充分 ✓ |
| P5（F-S4-P047-2 复现） | `estimate_buy_cash(0) == 5.0`（`max(0·0.0003, 5)`） | 规格缺陷复现 → D4 补 `amount<=0 → 0` 守卫 |

### 10.2 发现与处置（当轮处置：1 P2 + 5 P3，正文已修订）

| ID | 级别 | 发现 | 处置（落点） |
|----|------|------|--------------|
| F-S4-P047-1 | **P2** | I10/V6 等预算对拍按字面（默认 `OptimizerConfig`）**必 FAIL**：`RiskParityOptimizer.optimize` 尾部 `_apply_constraints`（L389）以默认 `max_weight=0.10` clip+归一化，ERC 解被破坏为等权（探针 P2a/P2b 对照实证） | §6 I10 / §5 V6：对拍构造**显式 `max_weight=1.0`**；「clip 后非 ERC」为既有优化器已知行为，登记 P-046（G9 禁止本批改） |
| F-S4-P047-2 | P3 | `estimate_buy_cash(0)` 因最低佣金返回 5 元（探针 P5）；qty=0 标的污染 `buy_cost` 与 `P047_S3` golden 期望 | D4 补 `amount<=0 → 0` 守卫；V8 补 qty=0 计 0 断言（引擎闸门不受影响：真实 BUY qty≥100） |
| F-S4-P047-3 | P3 | D5 伪码 `self.tracker.get_cash()` 与作用域既有局部别名 `tracker`（L848-849）不一致；落点「L900 之后」未精确到 `execute_order`（L909-911）之前 | D5 伪码改用局部 `tracker`（两处）；位置精确化为「L900-902 之后、L909-911 之前」 |
| F-S4-P047-4 | P3 | 闸门 `continue` **不会**触发 L919-922 `enable_fallback` 替补逻辑（fallback 仅在 `execute_order` 失败后触发）；DESIGN 未声明，IMPL 可能误改写为「execute 后判失败」 | D5 补注「闸门跳过 ≠ execute 失败」+ 禁止改写说明 |
| F-S4-P047-5 | P3 | `_calculate_cost` 支持 `asset_costs` 按资产覆盖 `commission_rate`（L385-389）→「同源」声明在该覆盖下不成立 | D4 补「同源限定」注：默认 STOCK 无覆盖路径；覆盖场景闸门为保守近似，不在本批 |
| F-S4-P047-6 | P3 | V9 断言表述「`Trade.cost` 相等」口径歧义（`cost` 不含本金，`estimate_buy_cash` 返回含本金总额） | V9 订正为**净现金式** `estimate_buy_cash(amount) == amount + _calculate_cost(amount, BUY)`（探针 P1 形式，三档断言） |

### 10.3 机械复核

- **E1 重放 7 项全 ✅**：`core/sizing.py` ❌ 不存在；sizing 方法 grep **3 命中零实现**（`adaptive_agent.py` L578/585 + `style_profile.py` L267）；ATR **0 命中**；`engine_v2` 全文 `guard|Guard` **0 命中**；golden 根 7 + `p045/` 2 = **15 实例**、`p047/` 不存在；`CASE_IDS`=G1-G7（[`_golden_cases.py` L36](file:///f:/Coding/Factor_Trading_v3.0/tests/_golden_cases.py#L36)）；根断言 L100-105。
- **E3 行号逐条验证 20 项全 ✅**：`_process_pending_orders` L841 / buyable L872-875 / `open_price` L892 / `is_valid_price` L900-902 / `execute_order` L909-911 / `mark_executed` 仅成交后 L913-916（**队列保留语义成立**，跳过路径仅 `continue`） / `mark_expired` L935 / 次日路径 L1257-1261 + 失败保留 L1282 / `self.cfg.cost` 路径（L272 `ExecutionSimulator(self.cfg.cost)`） / `_clamp_sell_quantity` BUY 原样 L766-767 / `CostConfig` L187-190 / `_calculate_cost` 佣金+滑点 L384-405 / `net_amount` L335 / pending 插入顺序 L287/L301/L330-340 无排序 / `RiskParityOptimizer.optimize` 签名无预算参数 L329-334 / `value_buffer=0.985` L51 / `enable_fallback` L919。
- **映射完整性**：V1-V12 ↔ 8 函数全覆盖（V1→apply_sizing none / V2-V3→kelly / V4-V5→vol_target / V6→risk_contributions / V7→裁剪 / V8→cash_budget / V9→estimate_buy_cash / V10→pyramid / V11→holding_age / V12→闸门）✓；I1-I10 取证列齐备（I10 经 F-S4-P047-1 订正）✓；计数链算术 15→18 = 3 独立测试函数 ✓。
- **上游承接**：§2.0 裁决表覆盖 RESEARCH §13 F1-F6 全部 6 项 + §3.3-补.3 五项建议 + F4/F5/F6 ✓；D1-D7 与 RESEARCH §7 S1-S11 的修订（S11② 废除式、S9 fee_buffer 精确式）一致 ✓。
- **零预填合规**：§10 占位于评审前未填 ✓；RULE-5 异构 ✓；D7 零行为边界与 I1/I9 一致 ✓。

### 10.4 结论

**有条件通过，准予进入 Step 5 IMPL**。发现 6 项（1 P2 + 5 P3）**全部当轮处置完毕**（§2 D4/D5、§5 V6/V8/V9、§6 I10 已修订）：唯一 P2 项（I10 对拍构造）不推翻任何 §2.0 裁决，仅收紧优化器构造参数并登记 P-046；探针同时实证了精确成本式同源性（P1）、算术双临界（P3）与预算迭代收敛性（P4）。无 P1 阻塞项；R1 回退条款必要性获 P1 差值表支撑。

## §11 Step 6 IMPL Review（异构基座 GLM-5.3-Flash，已回填）

> **评审身份**: GLM-5.3-Flash（≠ Step 5 作者 DeepSeek-V4.1-Flash，RULE-5）。复审对象：`core/sizing.py`（全文 450 行）、`core/engine_v2.py` diff（+16/−0）、`tests/test_p047_position_sizing.py`、`tests/golden/p047/*.json` ×3，对照本 DESIGN §2-§7 契约。

### 11.1 证据

- **E1 重放**（HEAD `531795e` + 工作区）: P-047 模块 **24→25 passed**（含 F-S6-P047-1 补测）/ `-k golden` **18** / `git diff core/config.py` **空**（I9）/ `engine_v2` 全文 `apply_sizing|SizingConfig|cash_budget_scale|kelly|vol_target` **0 接线命中**（D7②）/ mypy CI 等价口径 **109 files 0 issue** / black 4 文件 clean。
- **E2 探针**（`%TEMP%\p047_s6_probe.py`，33 断言全 PASS）: T1-T3 golden 三例**闭式独立复算逐位一致**（S1 kelly `f*=μ/σ²` / S2 `σ_p²=0.0355`→scale=0.7961173386514129 / S3 三次迭代 qty=(4900,1900)→(3000,1200)→(2900,1100)、cost=56573.45 逐值复现）/ T4-T6 发现取证 / T7 两订单 continue 语义实证 / T8 I4 纯函数 AST（零 try-except、零 print/open/random/time、import 白名单）/ T9 V9 净现金式三档逐位。
- **E3 静态**: engine diff 逐行核对——import L28 + 闸门 L905-918，`qty` 定义于 L882（`_clamp_sell_quantity`，BUY 原样）→ 落点/严格 `<`（L913）/`continue`（L918）/不触发 fallback（L935 在 execute 失败后）全部符合 D5；`sizing.py` 对照 D2 字段 19 项、D3/D4 契约逐条核对。

### 11.2 发现与处置（当轮处置：4 P3 + 2 INFO，正文与测试已修订）

| ID | 级别 | 发现 | 处置（落点） |
|----|------|------|--------------|
| F-S6-P047-1 | P3 | V12 规格要求断言「返回继续处理后续订单」，实现为**单订单场景**——无法区分闸门 `continue` 与 `break`（若误写 break，24 测试仍全绿） | 补 `test_v12_gate_continues_to_later_orders_after_skip`（双标的：AAA 被闸门跳过保留、BBB 继续成交、现金精确扣减）；探针 T7 预验证后落地，**24→25 passed** |
| F-S6-P047-2 | P3 | F6 裁决「+ `logger.warning`」未落地：`core/sizing.py` 无 logger（探针 T4），与 I4 纯函数契约 / D1 依赖白名单（无 logging）存在张力 | §2.0 F6 行订正：诊断以 `reason="zero_vol"` 返回，warning 由接线方（P-051）落地 |
| F-S6-P047-3 | P3 | D3「未知 code → 保持原权重 + `no_cov`」**仅 kelly 分支成立**；`vol_target`/`risk_parity` 对 weights ⊄ codes 经 `_as_vector` 直接 `ValueError`（探针 T5），DESIGN 未区分 | D3 `apply_sizing` 行订正：未知 code 宽容仅 kelly；其余方法 fail-fast |
| F-S6-P047-4 | P3 | D3 `risk_contributions` 行「σ_p==0 → 全 0 + `zero_vol`」——`RiskContribution`（D2）无 reason 载体，`zero_vol` 无处安放（探针 T6） | D3 行订正：全 0 即零波动语义 |
| O-S6-P047-1 | INFO | V2 规格字面（μ=0.10/σ²=0.04→clip 1.0）由 V3 语义等价覆盖（μ=2.5/σ²=1.0，同为 `0.5·2.5>1`）；数值不同、数学式相同 | 登记，不改动（裁剪语义已锁定） |
| O-S6-P047-2 | INFO | `apply_sizing` kelly 分支 mu 先取默认 0.0 再判 `no_expected_return` continue，顺序冗余但行为正确 | 登记，不改（避免无谓 diff） |

### 11.3 机械复核

- **契约符合性**: D2 字段 19 项逐一核对（名称/默认值/frozen）✓；D3 六函数语义+边界逐条 ✓（三处文档缺陷经 11.2 订正后齐）；D4 预算三迭代闭式复算逐位 ✓；D5 闸门 5 要素（位置/严格 `</continue/不触发 fallback/f-string 日志无行为差）✓；D6 golden schema（`inputs`/`config`/`expected`/`tolerance`、S3 `atol=1e-6`）✓；D7 四边界 ✓。
- **不变式 I1-I10**: I1 既有 golden 15 零重录（全量 845 通过）✓；I2 现金非负（V12×3）✓；I3 成本恒等（V9+T9 逐位）✓；I4 纯函数（T8 AST）✓；I5 不加杠杆（V4/V7+`min(…,1.0)`）✓；I6 禁摊亏（V10）✓；I7 预算保守（V8+T3）✓；I8 计数链 15→18 ✓；I9 config 零 diff ✓；I10 对拍构造 `max_weight=1.0`（F-S4-P047-1 处置落地）✓。
- **零预填合规**: §11 占位于评审前未填 ✓；RULE-5 异构 ✓；发现当轮处置（4 处置 + 2 登记）✓。

### 11.4 结论

**通过，准予进入 Step 7 CHECKLIST**。发现 6 项（4 P3 + 2 INFO）全部当轮处置：1 项补测（V12 continue 语义锁定，24→25）、3 项 DESIGN 订正（F6/D3×2，均为规格措辞与实现自洽化，不推翻任何 §2.0 裁决）、2 项 INFO 登记。golden 三例闭式独立复算**逐位一致**（非实现自证），engine 闸门静态与运行时双实证。无 P1/P2 阻塞项。

## §12 Step 8 一致性 Review（异构基座 GLM-5.3-Flash，已回填）

> **评审身份**: GLM-5.3-Flash（≠ Step 7 作者 DeepSeek-V4.1-Flash，RULE-5）。对象：RESEARCH ↔ DESIGN ↔ CHECKLIST 三向一致性 + PROGRESS 台账（本批无 IMPL 文档，T1 判档）。

### 12.1 机械校验（全 ✅）

- **互引链接**: 四文档互引（RESEARCH/DESIGN/CHECKLIST/PROGRESS）目标全部存在，0 broken；`UPGRADE_MASTER_PLAN` §5 批次表有 P-047 行；三文档均无 ADR 引用（本批无新 ADR，无双向补链义务）。
- **引用锚点存在性**: DESIGN 头部引用的 RESEARCH §4 G1-G11 / §5 M-A+A2 / §6 B1-B5 / §7 S1-S11 / §8 I1-I10 / §9 U-P047-1..5 / §13 / §3.3-补 D1-D6 + X16-X18 全部真实存在；RESEARCH §13 F1-F6 定级（F1 MEDIUM + F2 LOW + F3-F6 INFO）与 DESIGN 头部引用一致。
- **验收计数**: CHECKLIST **45 = 12(A) + 14(B) + 10(C) + 9(D)**（逐表行数机械复核）；零预填 `[待 Step 9]` **43** + `[待 Step 10]` **2**，单元格 `✅` **0**。
- **计数链**: 846 = 821 + 25 / 18 = 15 + 3 / 109 = 108 + 1 / 95 = 94 + 1 / AST 22 不变 / black 基线 + 2，CHECKLIST §5 与 PROGRESS §3.52.6-§3.52.8 三处一致。

### 12.2 发现与处置（当轮处置 5 P3 + 登记 3 INFO，正文已修订）

| ID | 级别 | 发现 | 处置（落点） |
|----|------|------|--------------|
| F-S8-P047-1 | **P2** | **B1 波动原语静默裁剪**：DESIGN §1 声称「做（B1→B5）」承接 RESEARCH §6 B1，但 `estimate_volatility`/`atr` 在 §3.1 / 实现 / CHECKLIST 三处均无；`SizingConfig.vol_lookback/atr_period/atr_k` 实现零消费（死字段）；§7 R4「`insufficient_history` 诊断」无实现载体（幻影条款）；RESEARCH S2/S3 成幽灵需求。「sizing 层只消费外部传入 cov/atr」是合理的 M-A 解耦决策但**未声明** | §1 做清单加 **B1 范围收窄声明**；D2 三字段标注【预留，本批零消费，D-R3】；§7 R4 行订正（σ_p 由调用方传入，`insufficient_history` 随 P-051 数据层落地）；CHECKLIST A1 同步注记 |
| F-S8-P047-2 | P3 | **kelly 方法形态漂移**：RESEARCH S4 矩阵式 `f=Σ⁻¹μ` → DESIGN/实现**逐标的 μ/σ² 对角近似**（golden S1 cov 亦用对角），未声明 | D3 kelly 行加**对角近似声明**（避免满秩求逆数值病态与高相关过度集中；矩阵式归 P-046） |
| F-S8-P047-3 | P3 | **术语漂移**：RESEARCH S1/U-P047-2 `risk_budget` → DESIGN/实现 `risk_parity`，未声明 | D2 method 行加术语定名注（语义一致：风险贡献诊断） |
| F-S8-P047-4 | P3 | **金字塔步长漂移**：RESEARCH S1/X7 `add_step_atr=0.5`（Turtle 0.5N）→ DESIGN/实现 `pyramid_step_atr=1.0`，未声明 | D2 pyramid_step_atr 行加保守化理由注（X15 证据冲突按保守侧处理） |
| F-S8-P047-5 | P3 | **kelly_fraction 区间漂移**：RESEARCH S1「[0.25,0.5] 越界 fail-fast」→ DESIGN/实现校验 `(0,1]`，未声明 | D2 kelly_fraction 行注：`(0,1]` 为合法性校验，`[0.25,0.5]` 为 X1 推荐运行区间（文档约束） |
| F-S8-P047-6 | P3 | DESIGN §1 做①「6 个纯函数」与 §3.1 实列 8 签名不符（`holding_age` 漏列；`estimate_buy_cash` 在做②） | 做① 改「7 个纯函数」并补列 `holding_age` |
| O-S8-P047-1 | INFO | RESEARCH §8 I1-I10 与 DESIGN §6 I1-I10 **同号不同义**（如 RESEARCH I4=确定性 vs DESIGN I4=纯函数；RESEARCH I8=计数基线 vs DESIGN I8=计数链）；CHECKLIST §6 已声明 D 系列冲突但未声明 I 系列 | CHECKLIST §6 交接第 3 条补 I 系列映射注记；C 组锚定 DESIGN 口径为准 |
| O-S8-P047-2 | INFO | RESEARCH I9「`SizingState` JSON 往返相等」验收无落点——DESIGN L106/L112 已声明可序列化保证 + 「P-051 可存 extras」，但 round-trip 测试未入 CHECKLIST | 登记随 P-051 接线批验收（遗留清单） |
| O-S8-P047-3 | INFO | **派生需求登记缺口**（v1.2 要求）：实施产生、DESIGN 未声明的语义决策散落未汇总 | 新增 §12.3 汇总登记 |

### 12.3 派生需求登记（实施中产生、DESIGN 首版未显式声明）

| ID | 内容 | 载体 | 状态 |
|----|------|------|------|
| D-R1 | `apply_sizing` **no_price 处置**：`min_size/max_size` 过滤时 `price is None or price<=0` → `reasons[code]="no_price"` + 权重置 0（fail-soft，不 raise） | `apply_sizing` L329-334 | 已落码，DESIGN 首版未声明，此处登记 |
| D-R2 | `pyramid_step` **`atr<=0 → 0` 防御**（D3 首版 5 条否决条件之外的第 6 条） | `pyramid_step` | 已落码，此处登记 |
| D-R3 | `SizingConfig.vol_lookback/atr_period/atr_k` **预留零消费**（B1 原语随 P-051 数据层落地，见 F-S8-P047-1） | `SizingConfig` L53-55 | 已落码 + DESIGN D2 注记 |
| D-R4 | golden S3 装载测试 `qty = round(…)` 后断言整手（闭式反推浮点容差处置，`atol=1e-6`） | `test_p047_golden_cash_budget` | 已落码（F-S5 golden S3 修复产物） |

### 12.4 结论

**通过，准予进入 Step 9**。发现 9 项（1 P2 + 5 P3 + 3 INFO）全部当轮处置：6 项正文订正（B1 范围声明 / 对角近似 / 术语 / 步长 / 区间 / 函数计数）、CHECKLIST 两处注记、派生需求 D-R1~D-R4 集中登记。本批**无 P1**；唯一 P2（F-S8-P047-1）为文档声明缺口而非代码缺陷——代码行为（外部传入 cov/atr）自 Step 5 起即被 V1-V12/golden 正确锁定，订正后 RESEARCH↔DESIGN↔IMPL↔CHECKLIST 四方口径闭合。Step 9 验收时按 §12.3 派生需求核对实现即可，无新增代码义务。
