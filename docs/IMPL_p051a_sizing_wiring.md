# IMPL：P-051a 策略接线底座（vol/ATR 波动原语 + `apply_sizing` 引擎接线）

> **批次**: P-051a · **Step 5 实施设计（逐处代码）** · 日期 2026-11-20
> **上游**: [DESIGN_p051a](DESIGN_p051a_sizing_wiring.md)（D1-D9 / I1-I13 / B1-B16；§0.1 Step 4 收敛；**0 P1 / 1 P2 / 4 P3 已全收敛**）
> **代码证据时点**: HEAD `95a6f6c`（代码同 `6fe5e08`）；本文仅新增文档，代码零改动
> **基座**: DeepSeek-V4.1-Flash（Step 6 复审须异构 GLM-5.3-Flash）

---

## 1. 变更总览

| # | 文件 | 变更 | 规模 |
|---|------|------|------|
| 1 | `core/volatility.py` | **新建**：`TRADING_DAYS` + `estimate_volatility` + `atr` | 新文件 ≈ 95 行 |
| 2 | `core/config.py` | TYPE_CHECKING 增 1 行导入；`BacktestConfig` 增 `sizing` 字段 | +2 行 |
| 3 | `core/engine_v2.py` | ① imports 2 处；② `setup()` 两处校验/告警；③ `_execute_rebalance` 段迁移 + sizing 块 | ≈ +55 / −2 行 |
| 4 | `tests/test_p051a_sizing_wiring.py` | **新建**：B1-B16 | 新文件 ≈ 330 行 |

**零改动**：`core/sizing.py`（I12）、三条 P-047 golden、22 条 golden 全集、`core/risk_overlay.py`（O-P051a-2 不修）。

---

## 2. 逐处代码

### 2.1 `core/volatility.py`（新建，全文）

```python
"""波动率原语（P-051a）。

设计依据：``docs/DESIGN_p051a_sizing_wiring.md`` D2/D3。

契约：
- 纯函数：无 I/O、无 logging、无随机、无全局状态；
- 仅 ``numpy`` / ``pandas``；异常仅 ``ValueError``（参数/形状非法）；
- 输入 Series → 返回 Series；输入 DataFrame → 返回 DataFrame；
- NaN 一律传播，禁止静默补 0 或 skipna 跳过（D3 F-D3）。

窗口口径（O-P051a-3）：``estimate_volatility`` 的窗口**含当日**
``[t-lookback+1, t]``；与引擎内部 Σ 窗口（不含当日，防前视）不同口径，
策略层接线时须显式对齐。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["TRADING_DAYS", "estimate_volatility", "atr"]

TRADING_DAYS = 252  # A 股年化惯例；不声称一手文献（U-P051a-6）


def _require_positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value <= 0:
        raise ValueError(f"{name} 必须为正整数: {value!r}")
    return int(value)


def estimate_volatility(
    returns: pd.Series | pd.DataFrame,
    *,
    lookback: int = 60,
    annualize: bool = True,
    periods: int = TRADING_DAYS,
) -> pd.Series | pd.DataFrame:
    """滚动样本波动率（``ddof=1``）。

    - 输出点 ``t`` 使用行 ``[t-lookback+1, t]``（含当日）；
    - 窗口行数不足 **或窗口内含任一 NaN** → NaN；
    - ``annualize=True`` 时 ``× sqrt(periods)``。
    """
    lookback = _require_positive_int("lookback", lookback)
    periods = _require_positive_int("periods", periods)

    is_series = isinstance(returns, pd.Series)
    frame = returns.to_frame() if is_series else returns
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"returns 必须为 Series 或 DataFrame: {type(returns)!r}")

    rolling = frame.rolling(window=lookback, min_periods=lookback)
    values = rolling.std(ddof=1).where(rolling.count() == lookback)
    if annualize:
        values = values * np.sqrt(float(periods))
    return values.iloc[:, 0] if is_series else values


def atr(
    high: pd.Series | pd.DataFrame,
    low: pd.Series | pd.DataFrame,
    close: pd.Series | pd.DataFrame,
    *,
    period: int = 14,
) -> pd.Series | pd.DataFrame:
    """Wilder ATR（标准口径，D3）。

    ``TR[0] = H-L``；``TR[t] = max(H-L, |H-C_prev|, |L-C_prev|)``；
    ``ATR[period-1] = mean(TR[0..period-1])``（**skipna=False**，任一 NaN → NaN）；
    ``ATR[t] = (ATR[t-1]*(period-1) + TR[t]) / period``；
    前 ``period-1`` 个 bar 为 NaN。
    """
    period = _require_positive_int("period", period)

    is_series = isinstance(high, pd.Series)
    if is_series != isinstance(low, pd.Series) or is_series != isinstance(close, pd.Series):
        raise ValueError("high/low/close 必须同为 Series 或同为 DataFrame")

    h = high.to_frame() if is_series else high
    lo = low.to_frame() if is_series else low
    c = close.to_frame() if is_series else close
    if not isinstance(h, pd.DataFrame) or h.shape != lo.shape or h.shape != c.shape:
        raise ValueError(
            f"high/low/close 形状必须一致: {getattr(h, 'shape', None)}/"
            f"{getattr(lo, 'shape', None)}/{getattr(c, 'shape', None)}"
        )
    if not (h.index.equals(lo.index) and h.index.equals(c.index)):
        raise ValueError("high/low/close 索引必须一致")

    prev_close = c.shift(1).to_numpy(dtype=float)
    high_arr = h.to_numpy(dtype=float)
    low_arr = lo.to_numpy(dtype=float)
    hl = high_arr - low_arr
    tr = np.maximum(np.maximum(np.abs(high_arr - prev_close), np.abs(low_arr - prev_close)), hl)
    if len(tr) > 0:
        tr[0] = hl[0]  # 首日无 C_prev（NaN 自然传播：H/L 为 NaN 时仍为 NaN）

    out = np.full(tr.shape, np.nan, dtype=float)
    if len(tr) >= period:
        out[period - 1] = tr[:period].mean(axis=0)  # numpy mean：NaN → NaN（skipna=False）
        for t in range(period, len(tr)):
            out[t] = (out[t - 1] * (period - 1) + tr[t]) / period

    values = pd.DataFrame(out, index=h.index, columns=h.columns)
    return values.iloc[:, 0] if is_series else values
```

**自检（Step 5 复核用）**：B3 表内 `TP[0..4]=[1.0,1.0,0.7,0.7,0.8]`，`out[2]=0.9`，`out[3]=(0.9·2+0.7)/3=0.8333333`，`out[4]=(0.8333333·2+0.8)/3=0.8222222`。

### 2.2 `core/config.py`

**(a) TYPE_CHECKING 块（现状 L15-16）**

```python
if TYPE_CHECKING:  # 仅类型检查期导入，避免运行期循环（engine → config → risk_overlay）
    from core.risk_overlay import RiskOverlayConfig
    from core.sizing import SizingConfig          # ← 新增
```

**(b) `BacktestConfig` 字段（插在 L424 `risk_overlay` 之后、L426 期货段之前）**

```python
    # 风险 overlay（P-048）；None = 未配置（零行为变更，22 条 golden 不受影响）
    risk_overlay: "RiskOverlayConfig | None" = None

    # 仓位管理（P-051a）；None = 零行为变更（22 条 golden 不受影响）
    sizing: "SizingConfig | None" = None
```

### 2.3 `core/engine_v2.py` — imports

**(a) L28 改写**

```python
from core.sizing import apply_sizing, estimate_buy_cash
```

**(b) `core.target_positions` 导入块（L34-38）之后新增一行**

```python
from core.volatility import TRADING_DAYS
```

### 2.4 `core/engine_v2.py` — `setup()` 两处

**(a) `factor_files` 校验块之后（现状 L250 之后、`t0 = time.perf_counter()` 之前）**

```python
        if self.cfg.sizing is not None:
            if self.cfg.sizing.method not in ("none", "vol_target"):
                raise ValueError(
                    "P-051a 引擎接线仅支持 sizing.method ∈ {none, vol_target}；"
                    f"当前={self.cfg.sizing.method!r}（kelly/risk_parity 由策略层消费，P-051b）"
                )
            if self.cfg.sizing.method == "vol_target" and (
                self.cfg.risk_overlay is not None
                and self.cfg.risk_overlay.target_vol is not None
            ):
                logger.warning(
                    "sizing.vol_target 与 risk_overlay.target_vol 同时启用 → 两腿独立缩放，"
                    "实际杠杆为乘积（F-R5）"
                )
            if self.cfg.sizing.min_weight > 0.0:
                raise ValueError(
                    "P-051a 引擎面禁止 sizing.min_weight > 0：apply_sizing 裁剪层把 0 权重"
                    "抬升至 min_weight（sizing.py L322-324），weights 模式下等于全市场建仓"
                    "（F-D1）；如需下限语义，归 P-051b 策略层显式白名单"
                )
```

**(b) `self._contract_specs = self._build_contract_specs()` / `futures_specs = ...`（现状 L310-311）之后**

```python
        if self.cfg.sizing is not None and (
            self.cfg.allows_short(AssetType.STOCK) or self._contract_specs
        ):
            logger.warning("sizing 配置已忽略：短仓/期货路径不在 P-051a 范围（P-058）")
```

### 2.5 `core/engine_v2.py` — `_execute_rebalance` 段迁移

**迁移范围（唯一允许的机械位移，逐字搬移、不改内容）**：

| 原位置 | 内容 | 去向 |
|--------|------|------|
| L1398-1406 | `try: prices = ...` + `positions` + `stock_short` + `allow_short` | 移到 L1375（optimizer 块结束）之后 |
| L1413-1425 | `current_positions` + `total_value` | 同上 |
| L1407-1412 | 股票负权重截断块（`if allow_short and not stock_short:`） | **原位不动**（overlay 之后） |

迁移后顺序：optimizer/weights → **prices/positions/allow_short/current_positions/total_value** → **sizing（新增）** → overlay → 截断块 → `build_target_positions`。

### 2.6 `core/engine_v2.py` — sizing 块（插在迁移段之后、overlay 之前）

```python
        # 仓位管理（P-051a，opt-in；D6：位于 overlay 之前、optimizer 之后）
        sizing_cfg = self.cfg.sizing
        if sizing_cfg is not None and not allow_short:
            target_map = {str(code): float(weight) for code, weight in target_weights.items()}
            finite_prices = {
                str(code): float(price)
                for code, price in prices.items()
                if code in target_map
                and price is not None
                and np.isfinite(float(price))
                and float(price) > 0.0
            }
            if len(finite_prices) < len(target_map):
                logger.warning(
                    "sizing 跳过：sizing_skipped_bad_price（%d/%d 无有限正价格）",
                    len(target_map) - len(finite_prices),
                    len(target_map),
                )
            else:
                cov = None
                codes = None
                if sizing_cfg.method == "vol_target":
                    window = sizing_cfg.vol_lookback
                    if date_index < window:
                        logger.warning(
                            "sizing 跳过：insufficient_history（%d < %d）", date_index, window
                        )
                    else:
                        assert returns_matrix is not None
                        rets = pd.DataFrame(
                            returns_matrix[date_index - window : date_index],
                            index=dm.trade_dates[date_index - window : date_index],
                            columns=dm.stock_codes,
                        )
                        cov_daily = estimate_cov(rets, method=self.cfg.optimizer.cov_method)
                        # G5 / I4：Σ 与 target_vol 同口径（日频 → 年化）
                        cov = cov_daily.to_numpy() * TRADING_DAYS
                        codes = [str(code) for code in cov_daily.columns]
                if sizing_cfg.method == "none" or cov is not None:
                    sized = apply_sizing(
                        target_map,
                        config=sizing_cfg,
                        cov=cov,
                        codes=codes,
                        total_value=float(total_value),
                        prices=finite_prices,
                    )
                    if sized.diagnostics.reasons.get("portfolio") == "zero_vol":
                        logger.warning("sizing zero_vol：Σ 退化，scale=1.0（P-047 F6）")
                    target_weights = (
                        pd.Series(sized.weights).reindex(target_weights.index).fillna(0.0)
                    )
```

**要点核对（实现时逐条对照）**：
- `none` 也调用（F-R2），`vol_target` 仅在 `cov is not None` 时调用（历史不足 → 整段跳过）；
- `finite_prices` 只保留目标权重内的有限正价格；数量不足 → 整日跳过（F-R6）；
- `date_index >= window` 与 optimizer L1326 同式；切片 `[date_index-window, date_index)` 恰 `window` 行；
- `estimate_cov` 已在 engine 导入并用于 L1340（签名 `(returns, *, method)`）；
- `min_size` drop ⇒ 权重 0 ⇒ 清仓，属预期重组语义（F-D2），无额外代码；
- `min_weight` 恒 0（D5 fail-fast 保证），裁剪层不会抬升任何 0 权重。

---

## 3. 测试计划（`tests/test_p051a_sizing_wiring.py`，B1-B16）

### 3.1 文件头与公共 fixture

```python
"""P-051a：波动原语 + sizing 引擎接线（B1-B16）。

红态设计：核心符号函数内导入 → 逐用例失败而非收集期 error。
"""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from _synth_fixture import write_factor, write_price_fixture

DATES = pd.bdate_range("2024-01-02", periods=6)
CODES = ["000001", "600000"]


def _fixture(root: Path) -> None:
    prices = np.array([[10.0 + 0.1 * i, 20.0 + 0.2 * i] for i in range(len(DATES))])
    write_price_fixture(root, DATES, CODES, prices)
    write_factor(root, "factor_value", np.tile([1.0, 2.0], (len(DATES), 1)), DATES, CODES)


def _make_engine(root: Path, *, sizing=None):
    # F-C1（Step 8）：原 allow_short 形参未接线 cfg，属死参数，已删除；
    # B10 按 F-I3 自行构造 cfg（allow_negative_stock_positions=True）+ set_signal 注入负权重。
    from core.config import (
        BacktestConfig, CostConfig, FactorConfig, OptimizerConfig, RebalanceConfig, UniverseConfig,
    )
    from core.engine_v2 import BacktestEngineV2

    cfg = BacktestConfig(
        data_dir=root,
        output_dir=root / "out",
        factor_files=["factor_value.pkl"],
        cost=CostConfig(commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0),
        factor=FactorConfig(
            winsorize_method="none", standardize_method="none", fill_method="none", neutralize=False,
        ),
        optimizer=OptimizerConfig(
            method="equal_weight", target_count=2, max_weight=1.0, round_lot=True, select_top=True,
        ),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False,
        ),
        initial_capital=10_000_000.0,
        enable_pending_orders=False,
        write_manifest=False,
        sizing=sizing,
    )
    return BacktestEngineV2(cfg)
```

### 3.2 B1-B4：波动原语（纯函数）

| ID | 断言（闭式） |
|----|--------------|
| B1 | `estimate_volatility(pd.Series([0.01,-0.01]), lookback=2)` → `0.2244994`；`([0.01,-0.01,0.02,-0.02], lookback=4)` → `0.2898271`（`abs=1e-6`） |
| B2 | `lookback=3` 于长度 4 → `[nan,nan,0.01…, …]` 前 2 个 NaN；含 NaN 窗口 → NaN；`annualize=False` → `0.0141421`（`abs=1e-7`）**→ 实施以 §9.2 F-I2（Step 7 重算）钉死值为准** |
| B3 | D3 表 5 行，`period=3`：`[nan,nan,0.9,0.8333333,0.8222222]`（`abs=1e-7`） |
| B4 | `atr(h, low, c)` 三方形状不一致 → `ValueError`；`period=0` → `ValueError`；Series/DataFrame 混用 → `ValueError` |

实现示例（B3）：

```python
def test_b3_atr_standard_wilder():
    from core.volatility import atr

    high = pd.Series([10.5, 11.0, 11.2, 11.5, 11.8])
    low = pd.Series([9.5, 10.0, 10.5, 10.8, 11.0])
    close = pd.Series([10.0, 10.8, 11.0, 11.3, 11.6])
    out = atr(high, low, close, period=3)
    assert math.isnan(out.iloc[0]) and math.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(0.9, abs=1e-7)
    assert out.iloc[3] == pytest.approx(0.8333333, abs=1e-7)
    assert out.iloc[4] == pytest.approx(0.8222222, abs=1e-7)
```

### 3.3 B5-B16：引擎接线

| ID | 构造 | 判据 |
|----|------|------|
| B5 | `_make_engine(root)`（`sizing=None`）→ `setup()`，取 `_execute_rebalance` 前两日 `_last_targets` | 与 `git stash` 前基线逐值相同（实现为「与 `BacktestConfig()` 对照运行」或固定期望 dict）**→ 实施以 §9.2 F-I1 钉死值为准（不得依赖 git 状态）** |
| B6 | `SizingConfig(method="none", max_weight=0.2)` | 目标权重每位 ≤ 0.2 + 1e-12；和 ≤ 1 |
| B7 | `SizingConfig(method="vol_target", target_vol=0.15, vol_lookback=2)`；`engine._returns_matrix` 置已知 2 行收益 | `scale = min(0.15/(σ_daily·√252), 1)` 闭式，权重 = 原权重×scale **→ 取数日以 §9.2 F-I5 钉死（首个 `date_index>=2` 的再平衡日）** |
| B8 | 同 B7 但 `vol_lookback=60`（`date_index < 60`） | 权重原样 + `caplog` 含 `insufficient_history` |
| B9 | 同 B7，`_returns_matrix` 全 0 | 权重原样 + `caplog` 含 `zero_vol` |
| B10 | `allow_short=True` + `sizing=SizingConfig(method="vol_target")` | 权重原样（不被裁剪）**→ 构造以 §9.2 F-I3 钉死（weights 模式 `set_signal` 注入负权重）** |
| B11 | `SizingConfig(method="kelly")` / `method="risk_parity"` | `setup()` `ValueError`，message 含 `P-051a` |
| B12 | `SizingState(100.0, 100.0, 1)` → `asdict` → `json.dumps/loads` | 重构对象相等 |
| B13 | 价格 fixture 令某目标 code 当日 close 为 NaN | 整日跳过 + `caplog` 含 `sizing_skipped_bad_price` **→ monkeypatch 形式以 §9.2 F-I4 钉死** |
| B14 | sizing.vol_target + `RiskOverlayConfig(enabled=True, target_vol=0.2)` | `setup()` 一次 warning（`caplog` 计数 == 1） |
| B15 | `pytest -k golden` | **22**；`tests/golden/**` 无新增目录 |
| B16 | `SizingConfig(method="none", min_weight=0.1)` | `setup()` `ValueError`，message 含 `P-051a` 与 `F-D1` |

**B7 闭式（登记用，Step 9 校准）**：**必须先固定 `cov_method="sample"`**——默认 `ledoit_wolf` 在 2 行样本上收缩，闭式不可手算。取 `_returns_matrix` 两行
`[[0.01, 0.02], [-0.01, -0.02]]`，`w=(0.5,0.5)` →
`σ_p = √(wᵀ(Σ̂·252)w)`，`scale = min(0.15/σ_p, 1)`；
测试内用 `estimate_cov(rets, method="sample")` 独立重算 Σ（不复用引擎实现），并断言 `0.4 < scale < 0.7`
（漏 ×252 或漏 Σ 时 `scale` 会被夹到 1.0，必失败），最后断言 `qty_sized/qty_base ≈ scale`（`rel=2e-3`，容纳整手 floor）。
（Step 9 实测：`scale≈0.6299`，`cov_method="sample"` 的 `_cov_sample` 为 ddof=0 口径。）

**B13 注意事项**：`write_price_fixture` 产出的价格面板需支持人工覆写 NaN；若 fixture 不支持，则用 `engine._exec_price` 的返回值后置 `loc` 覆写并 `monkeypatch`，不得改动其他测试共享文件。

---

## 4. 不变式 → 代码落点对照

| 不变式 | 落点 |
|--------|------|
| I1 `sizing=None` 零行为 | 2.4/2.6 全部 `if ... is not None`；B5 |
| I2 短仓/期货跳过 | 2.4(b) 告警 + 2.6 `and not allow_short`；B10 |
| I3 和 ≤ 1 | `apply_sizing` 既有缩量层；B6/B7 |
| I4 Σ 年化同口径 | 2.6 `* TRADING_DAYS`；B7 |
| I5 跳过不抛 | 2.6 两处 `logger.warning` 分支；B8/B13 |
| I6 zero_vol | 2.6 `reasons.get("portfolio")`；B9 |
| I7 双 vol 乘积 + 一次 warning | 2.4(a) 第二段；B14 |
| I8 method 子集 fail-fast | 2.4(a) 第一段；B11 |
| I9 volatility 无 I/O | 2.1 全文（imports 仅 numpy/pandas）；AST 检查 |
| I10 SizingState 往返 | B12 |
| I11 golden 不变 | B15 |
| I12 `core/sizing.py` 零 diff | `git diff --stat core/sizing.py` 为空 |
| I13 `min_weight>0` fail-fast | 2.4(a) 第三段；B16 |

---

## 5. 门禁命令（Step 9 执行）

```powershell
$env:MPLBACKEND='Agg'
.\.venv\Scripts\python.exe -m pytest tests/test_p051a_sizing_wiring.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q -k golden
.\.venv\Scripts\python.exe -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
.\.venv\Scripts\python.exe -m black --check core tests
git diff --stat core/sizing.py
```

目标：B1-B16 全绿 / 全量 **1024+16=1040** / golden **22** / mypy **113 files 0** / black **157 unchanged** / `core/sizing.py` 无 diff。

---

## 6. 风险与回退

| 风险 | 检测 | 回退 |
|------|------|------|
| 段迁移改变 golden | B5 / `-k golden` | 退回 overlay 之后 + `min_weight==0` 强制（DESIGN D6-R1） |
| `estimate_cov` 对 2 行样本返回奇异 | B7 断言失败 | 加大 fixture 行数或改用 4 行闭式；不改引擎 |
| `rolling.count()` 语义与预期不符 | B2 失败 | 改 `frame.notna().rolling(...).sum() == lookback` |
| `target_weights` 为 dict（非 Series） | 2.6 `reindex` 抛 `AttributeError` | 统一 `pd.Series(target_weights)` 包装（两模式均已为 Series，L1316/L1345） |
| B13 fixture 不支持 NaN | 测试内 `monkeypatch` | 不改共享 fixture |

---

## 7. Step 6 复审入口

异构复审（GLM-5.3-Flash）重点：

1. **2.1 `atr` 的 `np.maximum` NaN 传播**：首行覆写顺序是否可能被 `hl` NaN 污染（H/L 缺失场景）；
2. **2.5 段迁移**：`prices`/`positions`/`total_value` 在 sizing 后是否被 overlay 或截断块复用而产生 stale 值；
3. **2.6 伪码**：`sizing=None` 与 `allow_short` 两条件组合、`date_index == window` 边界、`codes` 与 `target_map` 的键类型（str）；
4. **B5 零行为**：如何构造可比基线（不允许录 golden）；
5. mypy：`pd.Series | pd.DataFrame` 联合返回、`to_frame()` 后类型收窄是否通过 `--check-untyped-defs`。

---

## 8. 本步自检

| 项 | 结果 |
|----|------|
| 每处代码是否有原位置/插入点 | ✅ 2.1-2.6 全部标行号或锚点 |
| 是否与 DESIGN D1-D9 一一对应 | ✅ D2/D3→2.1；D4→2.2；D5→2.4；D6→2.5/2.6；D7→2.6；D8→2.4(a)；D9→B12 |
| 是否引入 DESIGN 外的新语义 | ❌ 无 |
| 是否改 `core/sizing.py` | ❌ 零 diff（I12） |
| 是否新增 golden | ❌ 无（I11/B15） |
| 期望值是否闭式可复算 | ✅ B1-B4/B7 均给出手算式 |
| 待 Step 6 裁决项 | ❌ 无阻塞项（§7 为复审重点，非未决） |

---

## 9. Step 6 异构复审记录（复审方 GLM-5.3-Flash，2026-11-20）

> **复审身份**: GLM-5.3-Flash（≠ IMPL 作者 DeepSeek-V4.1-Flash，RULE-5）。按 §7 五项重点独立取证，另对 B1-B16 构造规格逐条复核。未采信作者自报。

### 9.1 §7 五项重点复核

| # | 重点 | 复审取证 | 结果 |
|---|------|----------|------|
| 1 | `atr` NaN 传播 | `np.maximum(1.0, nan)=nan`（numpy NaN 传播，异于 Python `max`）→ TR 任一输入 NaN 即 NaN；首行覆写 `tr[0]=hl[0]`：H/L NaN → `hl[0]=NaN` 传播正确；`tr[:period].mean(axis=0)` 为 numpy mean（不 skipna）→ 与 D3 `skipna=False` 一致；单行 `period=1` → `out[0]=TR[0]` 自洽 | ✅ |
| 2 | 段迁移 stale | overlay 输入仅 `target_weights/_nav_history/cov_matrix`（不消费迁移段变量）；截断块仅用 `target_weights/_contract_specs/allow_short`；`build_target_positions` 消费变量均定义于其前且同一日内无时变 → 无 stale；optimizer 失败 `return` 在迁移段之前；overlay 纯函数无 dumper/emit → 缺价提前 return 可观测等价 | ✅ |
| 3 | 2.6 伪码 | `date_index==window` → 切片 `[0,window)` 恰 window 行；`target_weights.index ⊆ dm.stock_codes`（scores：tradable_stocks.dropna；weights：set_signal 已 fillna(0) 无 NaN）→ `apply_sizing` weights⊆codes fail-fast 不触发；`method="none"` 时 `cov=None` 合法；`estimate_cov(rets, method=...)` 与 L1340 同式 | ✅ |
| 4 | B5 基线 | 「与 git stash 前基线」不可作为测试构造（测试不得依赖 git 状态）→ **F-I1（P3）** | ⚠️ 见 9.2 |
| 5 | mypy 收窄 | `h.columns`（Series 无此属性）：`if not isinstance(h, DataFrame) or ...: raise` 后 `h` 收窄 DataFrame；or 链其余属性（`lo.shape`/`c.shift`/`to_numpy`/`index`）两类型均有；`estimate_volatility` 以 `raise` 形式收窄 frame ✓；返回联合注解匹配；`apply_sizing(cov=Optional, codes=Optional)` 签名匹配 | ✅ |

### 9.2 发现清单（0 P1 / 0 P2 / 5 P3，全部为测试构造规格精确化）

| ID | 级别 | 发现 | 处置（Step 7/9 落实） |
|----|------|------|----------------------|
| F-I1 | P3 | B5 基线构造表述含糊（「git stash 前基线」无效） | **钉死**：同一 fixture 下 `sizing=None` vs `sizing=SizingConfig(method="none")`（全默认）→ `_last_targets` 逐值相同 + 无 sizing 告警；I1 的 golden 逐值不变由 B15 `-k golden`=22 兜底 |
| F-I2 | P3 | B2 输入序列未给出，「0.01…」与「0.0141421」混两种构造 | **钉死闭式（Step 7 重算，Step 9 精度校准）**：序列 `[0.01,-0.01,0.03,0.01]`、`lookback=2` → 年化 `[nan, 0.2244994432, 0.4489988864, 0.2244994432]`；`annualize=False` → `[nan, 0.0141421356, 0.0282842712, 0.0141421356]`；NaN 窗口 `[0.01, nan, 0.02, 0.01]` → `[nan, nan, nan, 0.1122497216]`（**末位有效**；t=3 窗口 `[0.02,0.01]` 的 SS=5e-5、var=5e-5、σ_d=0.0070710678）；全部 `abs=1e-9` |
| F-I3 | P3 | B10 构造途径缺失：scores 模式 optimizer 输出非负，验证不了「负权重不被夹」 | **钉死（Step 9 改法）**：`set_signal` 本身拒绝负权重（P-050 约束，须改架构超出本批），故 B10 改为 **`allow_negative_stock_positions=True` + `SizingConfig(method="none", max_weight=0.2)`**：断言行数与基线**完全相同**（ratio==1，证明 sizing 整段被跳过、max_weight 未生效），loop 内再断言 `setup()` 短仓告警已发 |
| F-I4 | P3 | B13 monkeypatch 细节不完整 | **钉死**：`monkeypatch.setattr(engine, "_exec_price", lambda dm, pt: patched_panel)`，`patched_panel` 为覆写 `[date, code]=NaN` 后的面板副本（不改共享 fixture） |
| F-I5 | P3 | B7 取数日未指明（6 日 fixture 中 vol_lookback=2 的生效日） | **钉死**：取首个满足 `date_index >= vol_lookback` 的再平衡日（第 3 日）断言闭式 scale |

### 9.3 结论

**有条件通过（0 P1 / 0 P2 / 5 P3）**。

- 代码本体（2.1-2.6）方向、语义、类型收窄、段迁移行为中性全部独立验证成立；
- 5 项 P3 全部集中在 B1-B16 的测试构造规格，随 Step 7 CHECKLIST 把 F-I1..F-I5 的钉死值写入 B 组验收项，Step 9 TDD 按钉死值实现；
- 收敛前不得启动 Step 9 编码；Step 7 CHECKLIST 需在 B5/B2/B10/B13/B7 行内直接采用 §9.2 钉死值。
