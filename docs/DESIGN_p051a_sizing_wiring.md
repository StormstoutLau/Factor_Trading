# DESIGN：P-051a 策略接线底座（vol/ATR 波动原语 + `apply_sizing` 引擎接线）

> **批次**: P-051a · **Step 3 设计** · 日期 2026-11-20
> **判档**: **T1**（新增 `core/volatility.py` + `core/config.py` 一个可选字段 + `core/engine_v2.py` 单点接线 + 测试；**不新增 golden**）
> **上游**: [RESEARCH_p051a](RESEARCH_p051a_sizing_wiring.md)（§4 G1-G10 / §5 S-A..S-G / §7 I1-I10 / §10 U-P051a-1..7 / **§15 Step 2 有条件通过：0 P1 + 1 P2 F-R1 + 5 P3 F-R2..F-R6 + 2 观察**）
> **代码证据时点**: HEAD `95a6f6c`（仅 docs；代码同 `6fe5e08`，工作区仅本文新增）
> **基座**: DeepSeek-V4.1-Flash（Step 4 复审须异构 GLM-5.3-Flash）

---

## 0. Step 2 发现收敛表（设计前置）

| ID | 级别 | 复审发现 | 本设计裁决 | 落点 |
|----|------|----------|------------|------|
| **F-R1** | **P2** | ATR seed 内部不一致：TR[0]（首日 H−L）与 `seed=mean(TR[1..period])` 互斥，TR[0] 成死语义；B3 锁 0.8 属非标准口径 | **采标准 Wilder**：TR 含首日（H−L），`seed=mean(TR[0..period−1])`，首个有效值落在索引 `period−1`；**B3 期望改为 0.9 / 0.8333333 / 0.8222222**；删「前 `period` 个 bar 为 NaN」改为「前 `period−1` 个 bar 为 NaN」；对 P-047 RESEARCH S3 的偏移登记 D3-B | D3 |
| F-R2 | P3 | `method="none"` 引擎语义只在伪码；sizing.py L9「完全零行为」vs L256「仍施加约束层」张力 | **引擎按 `sizing is not None` 一律调用 `apply_sizing`**：`none` = 不做方法缩放，但约束层生效（对齐 L256）；默认 `None` 才零行为；L9 的「零行为」限定为「无方法缩放」 | D5 / D6 |
| F-R3 | P3 | 「`__post_init__` 6 项校验」实为 5 项 | 已随 Step 3 修订 RESEARCH §2.1（5 项） | RESEARCH L62 |
| F-R4 | P3 | kelly 静默 continue 锚 L270-277 漂移，实际 L285-287 | 已随 Step 3 修订 RESEARCH §3.1；「静默」限定为引擎面 | RESEARCH L100 |
| F-R5 | P3 | sizing `vol_target` × overlay `target_vol` 复合缩放未登记 | **允许并存**（层架构正交），`setup()` 打一次 warning 明示「乘积缩放」；DESIGN 记录复合语义 | D8 / I7 |
| F-R6 | P3 | `apply_sizing` 的 no_price 不拦 NaN（`price <= 0.0` 对 NaN 为 False） | **fail-open 跳过**：目标权重中任一 code 无有限正价格 → 当日整个 sizing 跳过 + `sizing_skipped_bad_price` 告警，权重原样 | D7 / I5 |

**U-P044-3 处置**：本批**不承接**，转 P-051b（触发条件「模板库或第三处信号实现」未在 P-051a 满足）。PROGRESS L198 P-051a 行「+ U-P044-3」措辞建议在 Step 10 回填时改为「U-P044-3 → P-051b」。

### 0.1 Step 4 复审发现收敛（2026-11-20 补，复审记录见 §10）

| ID | 级别 | 复审发现 | 收敛动作 | 落点 |
|----|------|----------|----------|------|
| **F-D1** | **P2** | `min_weight > 0` 抬升语义：sizing.py L322-324 确认 `weight < min_weight → min_weight`，**0 权重也被抬升**；weights 模式下等于全市场建仓 | **D5 增第三条 fail-fast**：引擎面 `sizing.min_weight > 0` → `ValueError`；B 组补 B16；产品确需下限语义归 P-051b 策略层白名单 | D5 / I13 / B16 |
| F-D2 | P3 | `min_size` drop ⇒ 目标权重 0 ⇒ 清仓已有持仓（sizing.py L336-339 置 0） | D7 钉死为预期重组语义；IMPL 补测试锁定 | D7 / §4 |
| F-D3 | P3 | `atr` seed 均值 pandas 默认 skipna=True，与「不填补」矛盾 | D3 补明 seed `skipna=False`：任一 NaN → 该位置及后续递归全 NaN | D3 |
| F-D4 | P3 | 双窗口口径差：原语含当日 `[t−lookback+1, t]` vs 引擎 Σ 不含当日 `[t−window, t)`（防前视） | 登记 **O-P051a-3**；P-051b 设计时显式对齐 | D2 注记 |
| F-D5 | P3 | B6 期望值未闭式列出 | B6 补闭式：输入 {A:0.3, B:0.2} + `max_weight=0.2` → {A:0.2, B:0.2}，和 0.4 ≤ 1 不缩放 | §4 B6 |

---

## 1. 范围与前置

### 1.1 做

| # | 内容 | 落点 |
|---|------|------|
| 1 | 新建 `core/volatility.py`：`TRADING_DAYS` / `estimate_volatility` / `atr` | D1-D3 |
| 2 | `BacktestConfig.sizing: SizingConfig \| None = None`（TYPE_CHECKING 导入） | D4 |
| 3 | `setup()` fail-fast（method 子集 + 双 vol 告警 + 短仓告警） | D5 / D8 |
| 4 | `_execute_rebalance`：`prices/total_value/allow_short` 上移至 overlay 之前 + sizing 段 | D6 / D7 |
| 5 | `insufficient_history` / `zero_vol` / `sizing_skipped_short` / `sizing_skipped_bad_price` 四类告警 | D7 |
| 6 | `SizingState` JSON 往返验收（零生产 API） | D9 |
| 7 | 测试 `tests/test_p051a_sizing_wiring.py`（B1-B16）+ 四文档 + 台账 | §4 / §5 |

### 1.2 不做

- `strategies/` 模板与 registry（P-051b）；生命周期（P-051c）；
- `kelly` / `risk_parity` 引擎接线（fail-fast）；
- `cash_budget_scale` / `pyramid_step` / `holding_age` 接线（零消费方；后两者 P-051c）；
- 短仓/期货 sizing（P-058）；
- 改 `core/sizing.py` 任何一行（本批零 diff）；
- 改 P-047 三条 golden 与既有 22 条 golden；
- 修 P-048 overlay 年化口径（O-P051a-2 已建行，修复归后续批次）；
- 新增 CLI 参数 / 新配置模块。

### 1.3 前置（E3 @`95a6f6c`）

`core/volatility.py` 不存在；`BacktestConfig` 无 sizing 字段（[config.py L424](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L424) 之后为 P-050 字段）；`apply_sizing` 零生产调用；`core/sizing.py` 有 5 项 `__post_init__` 校验；`engine_v2` 已 `from core.sizing import estimate_buy_cash`（同向依赖先例，L28）。

---

## 2. 设计决策

### D1 模块职责与放置（F-S10-P051-1 落定）

| 模块 | 职责 | 依赖 |
|------|------|------|
| `core/volatility.py`（新建） | 价格/收益面板 → 波动/ATR；纯函数、无 I/O、无 logger、无全局态 | 仅 `numpy` / `pandas` / `typing` |
| `core/config.py`（改） | 承载 `sizing` 配置（可选） | 新增 1 行字段 + TYPE_CHECKING 导入 |
| `core/engine_v2.py`（改） | 接线：窗口判定 / Σ 构造 / `apply_sizing` 调用 / 告警 | 新增 `from core.sizing import SizingConfig, apply_sizing` + `from core.volatility import TRADING_DAYS` |

**裁决（承 RESEARCH §5.1）**：归 P-051a，选新模块 B。机械判据三条全过（无数据管道改动 / 消费方在本批 / core-only）。`core/sizing.py` 零 diff → P-047 契约与 golden 天然不受影响。
**对 DESIGN_p047 L319 的订正（D-R3）**：原文「`insufficient_history` 诊断与样本充足性判定随波动原语批次（P-051 数据层）落地」中的「数据层」为拆批前假设；P-051 拆批后无独立数据层批，本批以接线层 `vol_lookback` 判定落 `insufficient_history`，波动原语归 P-051a。

### D2 `core/volatility.py` API

```python
TRADING_DAYS = 252  # A 股年化惯例；不声称一手文献

def estimate_volatility(
    returns: pd.Series | pd.DataFrame,
    *,
    lookback: int = 60,
    annualize: bool = True,
    periods: int = TRADING_DAYS,
) -> pd.Series | pd.DataFrame: ...

def atr(
    high: pd.Series | pd.DataFrame,
    low: pd.Series | pd.DataFrame,
    close: pd.Series | pd.DataFrame,
    *,
    period: int = 14,
) -> pd.Series | pd.DataFrame: ...
```

- 输入类型保持（Series→Series，DataFrame→DataFrame）；
- `lookback <= 0` / `period <= 0` / `periods <= 0` → `ValueError`；
- 仅样本口径（`ddof=1`）；**EWMA 不落本批**（无 λ/span 一手锚点，U-P051a-7）；
- `__all__ = ["TRADING_DAYS", "estimate_volatility", "atr"]`。

**`estimate_volatility` 窗口语义**：输出点 `t` 使用行 `[t−lookback+1, t]`；窗口行数不足 **或窗口内含任一 NaN** → NaN（禁止静默 0，承 P-047 RESEARCH S2）。实现用 `rolling(window=lookback, min_periods=lookback).std(ddof=1)` 后再把「窗口含 NaN」置 NaN（`rolling(...).count() < lookback` 判定），保证与闭式一致。`annualize=True` 时 `× sqrt(periods)`。

> **窗口口径注记（O-P051a-3，F-D4）**：本原语窗口**含当日** `[t−lookback+1, t]`；引擎 Σ 窗口**不含当日** `[t−window, t)`（防前视，与 optimizer 同式）。两者各自合理，P-051b 模板接线时须显式对齐，禁止混用。

### D3 `atr` 语义（F-R1 收敛：标准 Wilder）

- `TR[0] = H[0] − L[0]`（无 `C_prev`）；`TR[t] = max(H[t]−L[t], |H[t]−C[t−1]|, |L[t]−C[t−1]|)`，`t ≥ 1`；
- **首个 ATR 落在索引 `period−1`**：`ATR[period−1] = mean(TR[0..period−1])`；
- `ATR[t] = (ATR[t−1]·(period−1) + TR[t]) / period`，`t ≥ period`；
- 前 `period−1` 个 bar 为 NaN；输入三方形状必须一致，否则 `ValueError`；`high/low/close` 内任一 NaN → 该列对应位置输出 NaN（不跳过、不填补）；
- **seed 的 skipna 语义（F-D3）**：`ATR[period−1] = mean(TR[0..period−1])` 以 **`skipna=False`** 计算——窗口内任一 TR 为 NaN → seed 为 NaN，且后续 Wilder 递归全 NaN（禁用 pandas `.mean()` 默认 skipna=True 的静默跳过）。

**闭式（period=3，与本设计 B3 一致）**：

| 日 | H | L | C | TR |
|---|---|---|---|---|
| 1 | 10.5 | 9.5 | 10.0 | 1.0 |
| 2 | 11.0 | 10.0 | 10.8 | max(1.0,1.0,0.0)=1.0 |
| 3 | 11.2 | 10.5 | 11.0 | max(0.7,0.4,0.3)=0.7 |
| 4 | 11.5 | 10.8 | 11.3 | max(0.7,0.5,0.2)=0.7 |
| 5 | 11.8 | 11.0 | 11.6 | max(0.8,0.5,0.3)=0.8 |

`ATR[2] = (1.0+1.0+0.7)/3 = 0.9`；`ATR[3] = (0.9·2+0.7)/3 = 0.8333333`；`ATR[4] = (0.8333333·2+0.8)/3 = 0.8222222`。

**D3-B 对上游的偏移登记**：P-047 RESEARCH S3 写「前 `period` 个 bar 为 NaN」，在标准 Wilder seed（含 TR[0]）下应为「前 `period−1` 个」。采标准口径的理由：①标准定义唯一且可外部核验；②消除「首日 TR 计算但不消费」的死语义；③与 P-051b 模板对 ATR 的常规用法一致。偏移仅影响首 bar 差 1，风险可忽略；RESEARCH §3.2 的 0.8 系非标准变体，B3 以本表为准。

### D4 配置承载

```python
# core/config.py（TYPE_CHECKING 块内）
if TYPE_CHECKING:
    from core.sizing import SizingConfig

@dataclass(frozen=True)
class BacktestConfig:
    ...
    risk_overlay: Optional["RiskOverlayConfig"] = None
    sizing: Optional["SizingConfig"] = None   # ← 新增；None = 零行为
```

- **仅类型注解 + TYPE_CHECKING**：不把 numpy/pandas 拉进 `config` 运行期导入链；默认 `None` 不需要运行期构造。
- 不新增 CLI 参数；`SizingConfig.__post_init__` 的 5 项校验已够，不在 `BacktestConfig` 重复。

### D5 `setup()` 校验（fail-fast）

`BacktestEngineV2.setup()` 内两处插入（**不是**单一位置）：

**(a) `factor_files` 校验之后（现状 L250 之后）**——纯配置校验，不依赖数据：

```python
if self.cfg.sizing is not None:
    if self.cfg.sizing.method not in ("none", "vol_target"):
        raise ValueError(
            "P-051a 引擎接线仅支持 sizing.method ∈ {none, vol_target}；"
            f"当前={self.cfg.sizing.method!r}（kelly/risk_parity 由策略层消费，P-051b）"
        )
    if self.cfg.sizing.method == "vol_target" and (
        self.cfg.risk_overlay is not None and self.cfg.risk_overlay.target_vol is not None
    ):
        logger.warning(
            "sizing.vol_target 与 risk_overlay.target_vol 同时启用 → 两腿独立缩放，"
            "实际杠杆为乘积（F-R5）"
        )
    if self.cfg.sizing.min_weight > 0.0:
        raise ValueError(
            "P-051a 引擎面禁止 sizing.min_weight > 0：apply_sizing 裁剪层把 0 权重抬升"
            "（sizing.py L322-324），weights 模式下等于全市场建仓（F-D1）；"
            "如需下限语义，归 P-051b 策略层显式白名单"
        )
```

**(b) `self._contract_specs = self._build_contract_specs()`（现状 L310）之后**——期货合约集此时才可用：

```python
if self.cfg.sizing is not None and (
    self.cfg.allows_short(AssetType.STOCK) or self._contract_specs
):
    logger.warning("sizing 配置已忽略：短仓/期货路径不在 P-051a 范围（P-058）")
```

- 失败信息含批次 ID 与替代归属，满足「禁止静默」；
- 短仓告警在 `setup()` 打一次（`allow_short` 在运行期恒定），避免逐日刷屏；
- `kelly` 的静默 no-op（`expected_returns=None` 时权重不变）由此在入口被拦截，不会出现「配了但无效果」。

### D6 接线位置与顺序

**顺序：optimizer / weights 模式 → sizing → risk overlay → `build_target_positions`。**

- 现状 overlay（[L1377-1395](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1377-L1395)）在 `prices/total_value`（L1398-1425）之前；sizing 的 `min_size/max_size` 需要后两者 → **把 L1398-1406 + L1413-1425 上移到 overlay 之前**（Step 8 终验裁定：`try:` 在 L1398；Step 4 复审笔误 L1399，IMPL §2.5 行号为准）；
- **L1407-1412 的股票负权重截断块保留原位**（overlay 之后）：若随段上移，期货/短仓模式下 overlay 的输入会从「含负股票权重」变为「已截断」，改变 `σ_p` 与 P-050 golden 行为；sizing 在 `allow_short` 时整段跳过，无需该块先行；
- 行为中性论证：上移段只读 `tracker` / `prices` / `_contract_specs`，唯一副作用是缺价时 `logger.warning + return`；上移后缺价仍在 `build_target_positions` 前返回，可观测结果一致；
- **不采用 overlay 之后插入**：架构语义上 overlay 是最后一道缩放（P-048 D1 三层）；F-D1 fail-fast 后 `min_weight` 恒 0，抬回风险已在入口消除；
- 回退 R1：若 Step 9 出现 golden 差异且来源为顺序，则退回 overlay 之后，并在 `setup()` 强制「引擎启用 sizing 时 `min_weight == 0`」（`ValueError`）。

### D7 接线伪码与四类告警

```python
# ① 上移（原 L1398-1406 + L1413-1425 逐字搬移；**不含** L1407-1412 的股票负权重截断块）
try:
    prices = self._exec_price(dm, "close").loc[date]
except (KeyError, IndexError):
    logger.warning(f"日期 {date} 缺少收盘价数据，跳过本次再平衡")
    return
positions = tracker.get_all_positions()
stock_short = self.cfg.allows_short(AssetType.STOCK)
allow_short = stock_short or bool(self._contract_specs)
current_positions = {
    stock: int(position.quantity)
    for stock, position in positions.items()
    if int(position.quantity) > 0 or (allow_short and int(position.quantity) != 0)
}
total_value = compute_portfolio_value(
    self._avail_cash(), current_positions, prices,
    {stock: position.market_value for stock, position in positions.items()},
    equity_symbols=set(self._contract_specs),
    allow_negative_stock=self.cfg.allow_negative_stock_positions,
)

# ② sizing 层（opt-in）——紧随其后，仍在 overlay 之前
sizing_cfg = self.cfg.sizing
if sizing_cfg is not None and not allow_short:
    target_map = {str(c): float(w) for c, w in target_weights.items()}
    finite = {
        str(c): float(p) for c, p in prices.items()
        if c in target_map and p is not None and np.isfinite(float(p)) and float(p) > 0.0
    }
    if len(finite) < len(target_map):
        logger.warning("sizing 跳过：sizing_skipped_bad_price（%d/%d 无有限正价格）",
                       len(target_map) - len(finite), len(target_map))
    else:
        cov = codes = None
        if sizing_cfg.method == "vol_target":
            window = sizing_cfg.vol_lookback
            if date_index < window:
                logger.warning("sizing 跳过：insufficient_history（%d < %d）", date_index, window)
            else:
                rets = pd.DataFrame(
                    self._returns_matrix[date_index - window:date_index],
                    index=dm.trade_dates[date_index - window:date_index],
                    columns=dm.stock_codes,
                )
                cov_daily = estimate_cov(rets, method=self.cfg.optimizer.cov_method)
                cov = cov_daily.to_numpy() * TRADING_DAYS          # 年化对齐（G5 / I4）
                codes = [str(c) for c in cov_daily.columns]
        if sizing_cfg.method == "none" or cov is not None:
            result = apply_sizing(
                target_map, config=sizing_cfg, cov=cov, codes=codes,
                total_value=float(total_value), prices=finite,
            )
            if result.diagnostics.reasons.get("portfolio") == "zero_vol":
                logger.warning("sizing zero_vol：Σ 退化，scale=1.0（P-047 F6）")
            target_weights = pd.Series(result.weights).reindex(target_weights.index).fillna(0.0)
```

要点：
- **`none` 也调用**（F-R2）：约束层生效；默认 `None` 才完全零行为；
- `codes` 取 `cov_daily.columns`（= `dm.stock_codes`），目标权重 `⊆ codes` 恒成立；期货已被 `allow_short` 拦截；
- `finite` 过滤保证 NaN 不进入 `min_size/max_size` 比较；**任一目标 code 缺有限价格 → 整日跳过**（F-R6，fail-open，避免把停牌股 weight 归 0 触发清仓）；
- `total_value/prices` 仅服务 `min_size/max_size`；整手与 `value_buffer=0.985` 仍由 `build_target_positions` 唯一出口完成；
- **`min_size` drop ⇒ 清仓（F-D2 钉死）**：`dropped_min_size` 置 0（sizing.py L336-339）→ 目标权重 0 → 对已有持仓生成卖出单，属**目标权重重组预期语义**（低于最小金额的持仓不保留）；IMPL 以测试锁定；
- 不重新归一化（`apply_sizing` 已保证和 ≤1）。

### D8 双层缩放的复合语义（F-R5）

sizing `vol_target` 与 overlay `target_vol` 可同时启用：两者都是 `min(target/σ, 1)`，最终杠杆 = 两 scale 乘积（双重降杠杆，方向保守）。裁决：**允许并存 + `setup()` 一次 warning**，不强制互斥（层架构正交，且强制互斥会让 P-048 已有配置组合失效）。文档明示：需要单一波动目标时只配其一。

### D9 `SizingState` JSON 往返

只加验收测试，不改生产 API：

```python
d = dataclasses.asdict(state)
assert json.loads(json.dumps(d)) == d
assert SizingState(**json.loads(json.dumps(d))) == state
```

若 P-051c 需要持久化，再升级 `to_dict/from_dict`（登记 O-P051a-1）。

---

## 3. 不变式（I-P051a-*）

| ID | 不变式 | 验证 |
|----|--------|------|
| I1 | `cfg.sizing is None` ⇒ 22 条 golden 逐值不变 | B5 + `-k golden` |
| I2 | `allow_short` 或存在期货合约 ⇒ sizing 零作用 | B10 |
| I3 | sizing 生效后 `sum(weights) <= 1.0 + 1e-12` | B7 |
| I4 | 引擎传入 Σ 已年化（`×252`），与 `target_vol` 同口径 | B7 闭式 |
| I5 | 历史不足 / 目标 code 无有限价格 ⇒ 跳过 + 告警，不抛异常，权重原样 | B8 / B13 |
| I6 | `σ_p == 0` ⇒ `scale=1.0` + `zero_vol` 告警，权重不变 | B9 |
| I7 | 双 vol 同时启用 ⇒ 乘积缩放 + 一次 warning | B14 |
| I8 | `method ∈ {kelly, risk_parity}` ⇒ `setup()` `ValueError` | B11 |
| I9 | `core/volatility.py` 无 I/O / logger / 随机 / 全局写 | AST + grep |
| I10 | `SizingState` JSON 往返相等 | B12 |
| I11 | `-k golden` 仍 22；`tests/golden/` 无新目录 | B15 |
| I12 | `core/sizing.py` 零 diff | `git diff --stat` |
| I13 | 引擎面 `sizing.min_weight > 0` ⇒ `setup()` `ValueError`（F-D1） | B16 |

---

## 4. 测试规格（B1-B16）

| ID | 用例 | 期望值 / 判据 |
|----|------|----------------|
| B1 | `estimate_volatility` 样本闭式 | `[0.01,-0.01]` → 0.224499；`[0.01,-0.01,0.02,-0.02]` → 0.289827（`abs=1e-6`） |
| B2 | 窗口不足 / 窗口含 NaN | 前 `lookback−1` 行 NaN；含 NaN 窗口输出 NaN；`annualize=False` 返回原始 std |
| B3 | `atr` 标准 Wilder 闭式（period=3） | 前 2 个 NaN；`ATR[2]=0.9`、`ATR[3]=0.8333333`、`ATR[4]=0.8222222`（`abs=1e-7`） |
| B4 | `atr` 形状不一致 / 参数非法 | 三方形状不一致 → `ValueError`；`period=0` → `ValueError` |
| B5 | 引擎 `sizing=None` | 目标权重与 HEAD 逐值相同（复用既有假 DM fixture）**→ 实施口径以 IMPL §9.2 F-I1 / CHECKLIST B5 为准（None vs `method="none"` 对照，禁 git 依赖）** |
| B6 | 引擎 `method="none"` + `max_weight=0.2` | 输入 {A:0.3, B:0.2} → {A:0.2, B:0.2}，和 0.4 ≤ 1 不缩放（约束层生效，F-R2；闭式 F-D5） |
| B7 | 引擎 `vol_target` 闭式 | 构造日频 Σ 已知 → `scale = min(0.15/(σ_daily·√252), 1)`，权重按 scale 缩放；`sum ≤ 1 + 1e-12` |
| B8 | `insufficient_history` | `date_index < vol_lookback` → 权重原样 + caplog 含 `insufficient_history` |
| B9 | `zero_vol` | 全 0 Σ → 权重原样 + caplog 含 `zero_vol` |
| B10 | 短仓路径 | `allow_short=True` + sizing → 权重原样（含负权重不被夹） |
| B11 | `kelly` / `risk_parity` | `setup()` 抛 `ValueError`，message 含 `P-051a` |
| B12 | `SizingState` 往返 | `asdict` → `json.dumps/loads` → 重构相等 |
| B13 | 目标 code 无有限价格 | 价格含 NaN → 整日跳过 + caplog 含 `sizing_skipped_bad_price` |
| B14 | 双 vol 告警 | sizing.vol_target + overlay.target_vol → `setup()` 一次 warning |
| B15 | golden 锁定 | `-k golden` = 22；`tests/golden/**` 无新增目录 |
| B16 | `min_weight > 0` fail-fast（F-D1） | `setup()` 抛 `ValueError`，message 含 `P-051a` 与 `F-D1` |

---

## 5. DoD

### 5.1 A 组：代码（7 项）

| ID | 验收项 | 证据 |
|----|--------|------|
| A1 | `core/volatility.py` 三符号 + 参数校验 | 读码 + B1-B4 |
| A2 | `estimate_volatility` NaN 语义与年化开关 | B1/B2 |
| A3 | `atr` 标准 Wilder + warmup `period−1` + 形状校验 | B3/B4 |
| A4 | `BacktestConfig.sizing`（TYPE_CHECKING） | 读码 |
| A5 | `setup()` fail-fast（method 子集 + `min_weight>0`）+ 双 vol 告警 + 短仓告警 | B11/B14/B16 |
| A6 | `_execute_rebalance`：段上移 + sizing 段 + 四类告警 | B5-B10/B13 + `git diff` |
| A7 | `core/sizing.py` 零 diff | `git diff --stat` |

### 5.2 B 组：测试（16 项）— 见 §4

### 5.3 C 组：门禁（4 项）

| ID | 门禁 | 目标 |
|----|------|------|
| C1 | pytest 全绿 | 1024 + 16（预计 1040，实测为准） |
| C2 | `-k golden` | **22**（零重录） |
| C3 | mypy | 112 → **113** files 0 error |
| C4 | black `core tests` | 155 → **157** unchanged |

---

## 6. 风险与回退

| 风险 | 触发条件 | 回退 |
|------|----------|------|
| R1 | 上移 `prices/total_value` 导致 golden 差异 | 退回 overlay 之后 + 强制 `min_weight == 0`（D6-R1） |
| R2 | `estimate_cov` 在 weights 模式数据形状不符（`_returns_matrix` 未按 trade_dates 对齐） | 复用 optimizer 的构造式（[L1330-1334](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1330-L1334)）；Step 5 逐字对齐 |
| R3 | ATR seed 偏移影响 P-051b | 偏移已在 D3-B 登记，B3 期望随标准口径；P-051b 引用本设计 |
| R4 | `none` + 约束层改变既有测试 | 默认 `None` 不变；B6 只覆盖显式配置 |

---

## 7. 基线读数与目标

| 读数 | 基线 @`95a6f6c` | 目标 |
|------|------------------|------|
| pytest | 1024 | 1024 + 16 |
| `-k golden` | 22 | 22 |
| mypy | 112 files 0 | 113 files 0 |
| black `core tests` | 155 | 157 |
| `tests/*.py` | 111 | 112 |
| `core/*.py` | 44 | 45 |

---

## 8. Step 4 复审入口

异构复审（GLM-5.3-Flash）重点：

1. **D3 标准 Wilder 闭式**：0.9 / 0.8333333 / 0.8222222 手算复核；
2. **D6 段上移行为中性**：prices/total_value 是否有隐含副作用（缓存、日志顺序）；
3. **D7 伪码**：`none` 调用路径、`finite` 过滤、`date_index` 与窗口边界（`window` vs `window+1`）；
4. **D5 fail-fast** 是否误伤既有配置（`sizing=None` 默认不受影响）；
5. 与 P-047/P-048/P-050 的边界是否越界。

---

## 9. 本步自检

| 项 | 结果 |
|----|------|
| Step 2 的 1 P2 + 5 P3 是否逐条有时间/位置裁决 | ✅ §0 全表 |
| F-R1 是否收敛为单一口径 | ✅ 标准 Wilder；B3 期望 0.9/0.8333333/0.8222222 |
| 是否改 `core/sizing.py` | ❌ 零 diff（D1 / I12） |
| 是否新增 golden | ❌ 无（I11 / B15） |
| 行号锚点是否复核 | ✅ 关键锚点均在本轮或 Step 2 复读确认 |
| 是否有未裁决项 | ❌ 无（U-P051a-1..7 全部落定；U-P044-3 转 P-051b） |

---

## 10. Step 4 异构复审记录（复审方 GLM-5.3-Flash，2026-11-20）

> **复审身份**: GLM-5.3-Flash（≠设计作者 DeepSeek-V4.1-Flash，RULE-5）。对象：D1-D9 + I1-I12 + B1-B15 全文读回，关键锚点独立读码（`engine_v2.py` L1278-1425 全段 / `sizing.py` L315-360 / `portfolio.py` L199-228 / `config.py` L13-17），闭式全部手算复算。未采信作者自报。

### 10.1 机械复核矩阵

| # | 复核项 | 复审取证 | 结果 |
|---|--------|----------|------|
| 1 | D3 标准 Wilder 闭式 | 手算：TR=[1.0,1.0,0.7,0.7,0.8]；`ATR[2]=(1.0+1.0+0.7)/3=0.9`；`ATR[3]=(0.9·2+0.7)/3=2.5/3=0.8333333`；`ATR[4]=(0.8333333·2+0.8)/3=2.4666667/3=0.8222222` | ✅ |
| 2 | B1 样本波动闭式 | 手算：`[0.01,−0.01]`→0.0141421×15.874508=0.224499；`[0.01,−0.01,0.02,−0.02]`→0.0182574×15.874508=0.289827 | ✅ |
| 3 | D6 上移段变量无 shadow | `_execute_rebalance` L1278-1425 全段读码：上移段变量（prices/positions/allow_short/current_positions/total_value）在 optimizer/weights 段（L1280-1395）均未定义；L1288 `tracker` 局部别名与伪码一致 | ✅ |
| 4 | D6 overlay 输入不受上移影响 | overlay 输入 = `target_weights` / `self._nav_history` / `cov_matrix`（L1313 两模式共享），上移段不产生其中任一 | ✅ |
| 5 | D7 Σ 构造同构性 | 伪码与 optimizer L1330-1334 **逐字同构**（`returns_matrix[a:b]` + `dm.trade_dates[a:b]` + `dm.stock_codes`）；`estimate_cov(..., method=self.cfg.optimizer.cov_method)` 与 L1340 **逐字同式**，签名匹配（`portfolio.py` L199-204） | ✅ |
| 6 | D7 窗口边界 | `date_index >= window` 与 optimizer L1326 `>= cov_lookback` 同式；`date_index==window` → 切片 `[0,window)` 恰 window 行 | ✅ |
| 7 | D7 zero_vol 通路 | `vol_target_scale` reason → `apply_sizing` `reasons["portfolio"]`（sizing.py 实读）→ 伪码 `.get("portfolio")` | ✅ |
| 8 | D5 不误伤默认配置 | 默认 `sizing=None` → 两处 if 全短路；`risk_overlay.target_vol` 默认 None（L52 复读） | ✅ |
| 9 | D5(b) 位置 | `_build_contract_specs()` 在 L310，期货集此后可用；L330-332 注入路径同源 | ✅ |
| 10 | D4 TYPE_CHECKING 同法 | config.py L15-16 现有 `RiskOverlayConfig` 同法块实读 | ✅ |
| 11 | 边界不越界 | `core/sizing.py` 零 diff（I12）；golden 不动（I11）；overlay 顺序不变；P-050 负权重截断块 L1407-1412 保留原位 | ✅ |
| 12 | `estimate_cov` 退化行为 | L221-222：有效行 <2 → 全 0 → σ_p=0 → `zero_vol` 路径，与 B9 衔接 | ✅ |

### 10.2 发现清单

| ID | 级别 | 发现 | 处置要求 |
|----|------|------|----------|
| **F-D1** | **P2** | **`min_weight > 0` 的抬升语义在引擎面危险**：sizing.py L322-324 实读确认 `weight < min_weight → base[code]=min_weight`——**0 权重也会被抬升**。weights 模式下 `target_weights` 含大量 0（L1322 clip 产生 / 策略直出），min_weight>0 → **全市场抬升建仓**；scores 模式 optimizer 输出亦可能含 0 权重成员。默认 0.0 无害，但 D5 fail-fast 未覆盖此组合 | Step 5 前收敛：D5 增第三条 fail-fast——引擎面 `sizing.min_weight > 0` → `ValueError`（message 说明抬升语义与 0=不持有约定冲突）；B 组补 B16（min_weight>0 → setup 抛错）。若产品确需 min_weight，归 P-051b 策略层显式白名单 |
| F-D2 | P3 | **min_size drop ⇒ 清仓已有持仓**：sizing.py L336-339 `dropped_min_size → base[code]=0.0`，伪码 reindex+fillna(0) 后目标权重 0 → 清仓。no_price 已被 finite 过滤整日拦截（不发生）；min_size 会发生 | D7 补一句语义钉死：「min_size drop ⇒ 目标权重 0 ⇒ 清仓，属目标权重重组预期语义」；IMPL 补测试锁定（已有持仓 + min_size 触发 → 生成卖出单） |
| F-D3 | P3 | **atr seed 的 skipna 未定义**：pandas `.mean()` 默认 skipna=True，与 D3「不跳过、不填补」矛盾——seed 含 NaN 会被静默跳过 | D3 补明：seed 均值 skipna=False，任一 NaN → 该位置及后续 Wilder 递归全 NaN |
| F-D4 | P3 | **双窗口口径差**：D2 `estimate_volatility` 含当日 `[t−lookback+1, t]`；引擎 Σ 窗口不含当日 `[t−window, t)`（防前视，与 optimizer 同式）。各自合理，但 P-051b 模板直接用原语接引擎语义会有 1 日口径差 | 登记观察项 O-P051a-3（RESEARCH/本 DESIGN 注明）；P-051b 设计时显式对齐 |
| F-D5 | P3 | **B6 期望值未闭式列出**：「夹到 0.2」未给输入/输出 dict；且若输入含 0 权重将触发 F-D1 抬升（fail-fast 后该组合不可构造） | Step 5 IMPL 给闭式：输入 {A:0.3, B:0.2} + max_weight=0.2 → {A:0.2, B:0.2}，和 0.4 ≤ 1 不缩放 |

### 10.3 结论

**有条件通过（0 P1 / 1 P2 / 4 P3）**。

- **全部方向性裁决成立**：接线位置（overlay 前）、段上移范围（L1399-1406 + L1413-1425，截断块留原位）、Σ 构造同构、D5 两处插入、D9 往返、边界不越界——逐项经独立读码验证；
- **1 P2（F-D1）**：`min_weight>0` fail-fast 必须在 Step 5 前补进 D5 与 B16，收敛前不得进 TDD；
- **4 P3**：F-D2（min_size 清仓语义钉死）/ F-D3（seed skipna）/ F-D4（窗口口径观察项）/ F-D5（B6 闭式化）随 Step 5 IMPL 一并落实；
- ~~复审不改设计正文~~ → **收敛已完成（2026-11-20）**：F-D1 落 D5 第三条 fail-fast + I13/B16；F-D2 落 D7 语义钉死；F-D3 落 D3 skipna；F-D4 落 D2 注记（O-P051a-3）；F-D5 落 B6 闭式；计数全面同步（B1-B16 / I13 / 1040 / A5）。收敛明细见 §0.1。**Step 4 闭环，可进 Step 5。**
