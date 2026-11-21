# IMPL：P-051c 策略生命周期（lifecycle / oos / virtual_account）

> **批次**: P-051c · **Step 5 实施设计（逐处代码）** · 日期 2026-11-21
> **上游**: [DESIGN_p051c](DESIGN_p051c_strategy_lifecycle.md)（D1-D12 / I1-I11 / 20 项裁决 / §7 测试表）；[REVIEW_p051c_step4 §10](REVIEW_p051c_step4_design.md)（三轮定点核验通过，**0 P1 / 0 P2**，2 P3 已修）
> **代码证据时点**: HEAD `53db4f7`（工作区仅 docs 改动）；本文仅新增文档，代码零改动
> **基座**: DeepSeek-V4.1-Flash（Step 6 复审须异构 GLM-5.3-Flash）

---

## 1. 变更总览

| # | 文件 | 变更 | 规模 |
|---|------|------|------|
| 1 | `core/lifecycle.py` | **新建**：`LifecycleError` + 六枚举/七契约 + `initial_record` / `evaluate_gate` / `apply` / `archive` / `replay` / `resolve_monitor_action` | ≈ 330 行 |
| 2 | `core/oos.py` | **新建**：`OOSReport` / `WindowOutcome` / `run_engine` / `evaluate_strategy` / `to_evidence` / 内部指标聚合与 IC | ≈ 300 行 |
| 3 | `core/virtual_account.py` | **新建**：`VirtualAccount`（4 变更加 pure）+ `BudgetCheck` + `check_allocation` + `check_book` | ≈ 170 行 |
| 4 | `tests/test_p051c_lifecycle.py` | 新建：L 组 14 + G 组 10 + R 组 5 | ≈ 520 行 |
| 5 | `tests/test_p051c_oos.py` | 新建：O 组 11（含 `_synth_fixture` 复用） | ≈ 360 行 |
| 6 | `tests/test_p051c_virtual_account.py` | 新建：A 组 10 | ≈ 220 行 |
| 7 | `tests/test_p051c_end_to_end.py` | 新建：E 组 3（含四模板参数化） | ≈ 180 行 |
| 8 | `.github/workflows/tests.yml` | **零改动**（mypy 已覆盖 `core`，[tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46)） | 0 |

**零改动**（I11）：`core/engine_v2.py`、`core/strategy.py`、`core/walk_forward.py`、`core/metrics.py`、`core/config.py`、`core/registry.py`、`core/sizing.py`、`core/stops.py`、`strategies/*`、`tests/_golden_cases.py`、22 条 golden、`core/__init__.py`（[L1-L14](file:///f:/Coding/Factor_Trading_v3.0/core/__init__.py#L1-L14) 明示「仅元数据版本号，不恢复重导出」→ DESIGN §2「若存在聚合导出」核对结论：**无聚合导出，无需改**）。

**编码约束**：black `line-length=100`（[pyproject.toml L94-L96](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L94-L96)）；mypy 已含 `core` 与 `strategies`。

---

## 2. IMPL 澄清（伪码 → 可执行语义）

DESIGN 在 D6/D7 层留了若干「设计上成立、落地需定死」的点。以下 C-1..C-11 为**实施口径**，Step 6 须逐条复核。

### C-1 `run_engine` 的引擎装配（DESIGN D6.2 未覆盖）

`setup()` 有硬守卫：`not cfg.factor_files and pipeline is None and combiner is None` → `ValueError`（[engine_v2.py L243-L251](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L243-L251)）；`_precompute_factors` 在无因子文件时**直接 return**（[L589-L591](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L589-L591)）；`self.combiner` 在 setup 后**无任何调用点**（仅 L205/L303/L306 赋值）。故装配方式定为：

```python
engine = BacktestEngineV2(cfg, data_manager=dm, factor_combiner=_NullCombiner())
engine.setup()                      # 守卫被注入的 combiner 满足；_composite_signal 保持 None
engine.set_signal(weights, mode="weights")   # 注入目标权重（L614-L656）
results = engine.run()              # weights 模式跳过优化器直出（L1338-L1347）
```

`_NullCombiner` 为模块内 3 行空实现（`combine()` 返回入参），**不进入 core 公共面**。`factor_files=[]` 是刻意的：lifecycle 评估的是「已生成的权重序列」，因子加载不在本批语义内。

### C-2 I/O 边界（I1 的必要澄清）

`_generate_results` **无条件** `output_dir.mkdir()` + `generate_report(..., output_dir)` + 写 `trades.csv` / `portfolio_snapshots.csv` / manifest（[L1763-L1768](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1763-L1768)、[L1839-L1848](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1839-L1848)）。因此 `oos.run_engine` 不可能零 I/O。

**处置**：`run_engine` 内用 `tempfile.TemporaryDirectory()` 作为 `cfg.output_dir`，函数返回前自动销毁；`write_manifest=False`（[config.py L368](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L368)）再减一处写盘。

**I1 语义修正**（Step 6 复核，建议 DESIGN I1 加脚注）：
> 三模块**自身代码**零 I/O、零 logging、无全局状态；**唯一受控例外**是 `oos.run_engine` —— 其 I/O 完全发生在引擎内部、落点限于函数内临时目录、返回前销毁，模块不读写任何业务路径。

不改 `engine_v2`（U-P051c-4 / I11 零 diff）。

### C-3 组合价值序列的字段（DESIGN D6.2「Step 5 核对字段名」→ 结论）

`run()` 返回 `dict["portfolio_value"]` = `pd.Series(snapshots["total_value"], index=snapshots["date"])`（[L1857-L1865](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1857-L1865)）。**取此键，不取 `additional_info`**。空序列 → `LifecycleError("回测未产生快照")`（引擎侧同为 RuntimeError，[L1756-L1760](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1756-L1760)，此处转成域内异常）。

⚠ `run()` 末日会 `_snapshot_unclosed_positions` + `_force_liquidation` + `_refresh_last_nav`（[L687-L690](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L687-L690)）→ 末值为强平后现金。与 P-044/P-051b 全量回测口径一致，不特殊处理（文档声明）。

### C-4 U-P051c-18 裁决：**不做 segmented 模式**

| 判据 | 实证 | 结论 |
|------|------|------|
| 引擎能否注入初始持仓/现金 | `__init__` 仅注入组件（[L138-L153](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L138-L153)）；`PositionTracker` 以 `cfg.initial_capital` 起账（[L349-L353](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L349-L353)） | ❌ 无初始状态注入 |
| 能否只跑 test 窗 | `set_signal` 强校验 `signal.index.equals(dm.trade_dates)`（[L632-L633](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L632-L633)） | ❌ 逐窗须重建 DataManager + 重算 views → 口径分叉 |

**裁决：默认不做（与 U-P051c-18 一致），维持 continuous（U-P051c-17）**。R1 风险由 DESIGN 显式声明承担。

### C-5 `StageEvidence` 契约补两字段（§3 契约遗漏）

DESIGN §3 的 `StageEvidence` 缺 D6.3 与 U-P051c-19 要求的两字段，IMPL 补齐：

```python
warmup_days: int = 0                       # U-P051c-19：被排除的预热日数
is_oos_decay: Optional[float] = None       # D6.3：(IS-OOS)/|IS|；None = insufficient_signal
```

`is_oos_decay = None` 与 NaN 同义（Python 侧用 `None` 而非 `float("nan")`，以兼容 I10「归档无 NaN」）。

### C-6 `LifecycleError` 的归属（D1「三模块互不 import」的唯一例外）

`LifecycleError(ValueError)` 定义在 `core/lifecycle.py`；`core/oos.py` **仅** `from core.lifecycle import LifecycleError`。

理由：D6.2 明文要求 oos 抛 `LifecycleError`；D1 的实质约束是「无数据耦合、不回调 lifecycle 的决策逻辑」，异常类型是纯类型依赖、零数据流。**不改 DESIGN**，Step 6 复核确认此解释成立（若复审否决，退路：`oos` 抛 `ValueError` 并在 `evaluate_strategy` 文档声明与 `LifecycleError` 同源语义 —— 不推荐，会让上层 `except LifecycleError` 漏接）。

`core/virtual_account.py` **不** import lifecycle（其错误一律 `ValueError`，D7 明文）。

### C-7 `signals_frame` 的列集合与 `set_signal` 的补列

`signals_frame` 的 columns = 全区间**出现过非零权**的标的并集（[strategy.py L267-L276](file:///f:/Coding/Factor_Trading_v3.0/core/strategy.py#L267-L276)），可能是 `dm.stock_codes` 的真子集；`set_signal` 会 `reindex(columns=dm.stock_codes)` 并 `fillna(0.0)`（[engine_v2 L637-L639](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L637-L639)）→ **列子集合法**。故 D6.1 的 `head` 必须用 `frame.columns`（不能自造 `dm.stock_codes`），否则 `pd.concat` 会产出两套列。

### C-8 decay 的 None 语义与取值口径

- `mean(IS)` / `mean(OOS)` 均指**逐窗 sharpe 的算术平均**（不是聚合指标的 sharpe）；
- 有效窗 = `test_metrics is not None and train_metrics is not None`；
- 有效窗数 == 0 或 `abs(mean_is) < EPS_SHARPE(0.1)` → `decay=None`、`decay_reason="insufficient_signal"`；
- 否则 `decay = (mean_is - mean_oos) / abs(mean_is)`。

### C-9 预热段与短窗的边界

- `W = min_history + 1`；`W` 同时作为 `history_window`（`views_from_data(..., history_window=W)`）与 `iloc` 下界（D6.1/D6.2）；
- `len(dm.trade_dates) <= W` → `LifecycleError("样本不足：需要 > W 个交易日")`（D6.1）；
- `len(pv) <= W`（快照数少于日历时）→ `OOSReport.aggregate=None`、`reason="insufficient_warmup"` → `StageEvidence.metrics=None` → Gate `HOLD`；
- 窗口左锚 `max(idx - 1, W)`、右端 `searchsorted(..., side="right")`、`len(seg) < 2` → 该窗记 `window_too_short`（D6.2 原文，不改）。

### C-10 IC 的具体算法（D6.4 落地）

```python
next_ret = dm.get_adj_price("close", "raw").pct_change().shift(-1)
for date in oos_dates:                    # 窗口 test 段日期并集（去锚点日，见 F-I8①）
    w = frame.loc[date]                   # frame = 全区间权重（含预热段，但只取 oos_dates）
    sel = w[w > 0]
    if sel.empty: continue                # 全零权重日 → NaN（不放 NaN 进序列）
    pair = pd.concat([sel, next_ret.loc[date, sel.index]], axis=1).dropna()   # 对齐 stats.py L66-L67
    if len(pair) < 10: continue           # <10 有效标的 → NaN（对齐 stats.py L70-L72）
    ic = pair.iloc[:, 0].corr(pair.iloc[:, 1], method="spearman")
    if pd.notna(ic): series[date] = float(ic)
```

**有效对数口径（F-I5）**：`next_ret` 含 NaN（末日 `shift(-1)`、停牌）时，须**先 dropna 再计数**——与 [stats.py L66-L72](file:///f:/Coding/Factor_Trading_v3.0/strategy_evaluation/stats.py#L66-L72) 的 `f.dropna()/r.dropna() → 交集 → len<10 → NaN` 完全同序，否则停牌日会虚高有效对数并算出与对齐口径不同的 IC。

**只保留非 NaN 值**（NaN 不入序列），避免下游 `mean` 传播；"全零 / 不足 10 标的 → NaN" 的语义在 O 组用例中以「该日不在 `ic_series.index`」断言。`ic_series` 仅含 OOS 段日期。

**`oos_dates` 定义（F-I8①）**：各 test 段在 `pv.index` 上的**实际交易日**（`seg.index`），**排除段首锚点日**（`searchsorted(start)-1` 定位的前一交易日，属 purge gap 末日的持仓延续日，不是 OOS 起点）；实现为 `seg.index[1:]`（O-2-2：`len(seg) < 2` 的段已被 `window_too_short` 拦截、不进入本函数，故无防御分支——有锚点必有其后的 OOS 日）。

### C-11 HOLD 是否落记录（D2/D10 未明写）

`HOLD` **落一条 `from_stage == to_stage` 的 `TransitionRecord`**（`action="hold"`）。依据：D10 写「green→HOLD（**记录**）」；且 I9 前缀重放要求任意前缀可重放——HOLD 记录是「该日评估过」的审计事实，不落记录会丢失评估轨迹。

---

## 3. 逐处代码

### 3.1 `core/lifecycle.py`（新建）

```python
"""策略生命周期状态机（P-051c，DESIGN D1-D5/D8-D11）。

纯函数、零 I/O、零 logging、无全局状态（I1）。所有时间为调用方传入的
``YYYY-MM-DD`` 字符串（禁 ``datetime.now``）。
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from core.metrics import MetricsResult

__all__ = [
    "LifecycleError", "LifecycleStage", "GateAction",
    "StrategyFingerprint", "StageEvidence", "ReadinessCriteria", "ValueCriteria",
    "GateCriteria", "GateDecision", "TransitionRecord", "LifecycleRecord",
    "initial_record", "evaluate_gate", "apply", "archive", "replay",
    "resolve_monitor_action",
]


class LifecycleError(ValueError):
    """生命周期域错误（非法迁移 / 判据输入非法 / 版本冲突 / 归档非法）。"""


class LifecycleStage(str, Enum):
    DRAFT = "draft"; BACKTEST = "backtest"; PAPER = "paper"
    GRAY = "gray"; LIVE = "live"; RETIRED = "retired"


class GateAction(str, Enum):
    GO = "go"; HOLD = "hold"; RECYCLE = "recycle"; KILL = "kill"


_GO_TARGET: dict[LifecycleStage, LifecycleStage] = {
    LifecycleStage.DRAFT: LifecycleStage.BACKTEST,
    LifecycleStage.BACKTEST: LifecycleStage.PAPER,
    LifecycleStage.PAPER: LifecycleStage.GRAY,
    LifecycleStage.GRAY: LifecycleStage.LIVE,
}   # LIVE / RETIRED 无 GO 目标（D2：live 为最高阶段、retired 终态）
```

契约 dataclass 与 DESIGN §3 一致，`StageEvidence` 追加 C-5 两字段。`__post_init__` 校验（fail-fast，均为 `LifecycleError`）：

| 契约 | 校验 |
|------|------|
| `StrategyFingerprint` | `strategy_id`/`version`/`code_hash` 非空 |
| `ReadinessCriteria` | `oos_sharpe_min`/`ic_min` 有限；`oos_max_drawdown_max`∈(0,1]；`paper_days_min`/`paper_trades_min`/`ic_lookback` ≥ 0 |
| `TransitionRecord` | `at` 匹配 `^\d{4}-\d{2}-\d{2}$`；`action` 合法四值 |
| `LifecycleRecord` | `history` 为空或 `stage == history[-1].to_stage` |

核心函数：

```python
def initial_record(fingerprint: StrategyFingerprint) -> LifecycleRecord:
    """新建记录：stage=DRAFT，history 为空。"""

def evaluate_gate(
    record: LifecycleRecord,
    evidence: StageEvidence,
    criteria: GateCriteria,
) -> GateDecision:
    """四值决策（D4 顺序 + D5 source 门 + D10 语义）。纯函数，无 now()。"""

def apply(
    record: LifecycleRecord,
    decision: GateDecision,
    *,
    at: str,
    new_version: Optional[str] = None,
) -> LifecycleRecord:
    """落迁移：GO 一步 / HOLD 原地 / RECYCLE 回 draft / KILL（paper 一步、gray|live 两步）。"""

def archive(record: LifecycleRecord, account: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    """归档快照（D9）：JSON 往返稳定、无 NaN/Inf（I10）。"""

def replay(records: Sequence[TransitionRecord]) -> tuple[LifecycleStage, ...]:
    """重放校验（D11/I9）：逐条核 from_stage 与当前一致，返回各步 to_stage。"""

def resolve_monitor_action(overall_level: str, stage: LifecycleStage) -> GateAction:
    """监控级别 → 动作（D10）：入参字符串，不 import agents。"""
```

**`evaluate_gate` 判定顺序（严格按 D4/D5）**

**返回语义（F-I6 定死）**：序 0-4 为**立即返回**（`reasons` = 已累积命中 + 触发判据）；序 5-12 评估完完整判据表后返回（`reasons` = 全部命中项，保序确定性）。

| 序 | 条件 | 结果 |
|----|------|------|
| 0 | `stage == RETIRED` | `HOLD`（`reasons=("retired",)`，不迁移；`apply` 对 RETIRED 的任何迁移抛错） |
| 1 | `stage == PAPER and evidence.source != "paper_record"` | `HOLD`，`reasons` 追加 `evidence_source`（I6） |
| 2 | `evidence.metrics is None` | `HOLD`，`reasons` 追加 `no_evidence` |
| 3 | `metrics.sharpe_ratio < 0` | **立即** `backtest → RECYCLE`；`paper/gray/live → KILL`（`reasons` 追加 `oos_sharpe_negative`） |
| 4 | `drawdown > 2 × oos_max_drawdown_max`（`drawdown` 取 `metrics.max_drawdown`，非负量级） | **立即**，同 3（`reasons` 追加 `drawdown_catastrophic`） |
| 5 | `metrics.sharpe_ratio < oos_sharpe_min` | 追加 `oos_sharpe`（不立即定案） |
| 6 | `drawdown > oos_max_drawdown_max` | 追加 `oos_max_drawdown` |
| 7 | `is_oos_decay is None` | 追加 `insufficient_signal`；`> is_oos_decay_max` → 追加 `is_oos_decay` |
| 8 | IC 尾部均值（非 NaN 尾部 `ic_lookback` 个）`< ic_min` 或序列空 | 追加 `ic` |
| 9 | `stage == PAPER`：`paper_days < min` | 追加 `paper_days`；`paper_trades < min` → 追加 `paper_trades` |
| 10 | `stage == GRAY`：`capital_min > 0 and (account_total 缺省或 < capital_min)` | 追加 `capital` |
| 11 | `not reasons` | `GO`，`target = _GO_TARGET[stage]` |
| 12 | 其余 | `reasons` 中含 `paper_days/paper_trades/ic/insufficient_signal` 类 → `HOLD`；`stage == BACKTEST` → `RECYCLE` |

注：`capital` 判据的资金来源为 `evidence.account_total`（`StageEvidence` 追加可选字段 `account_total: Optional[float] = None`，与 C-5 同步；缺省视为不满足）。**该字段为 §3 契约的第二处补齐。**

**`apply` 的迁移规则（D2/I2/I3/I4）**

```python
LEGAL = {
    (DRAFT, GO): BACKTEST, (BACKTEST, GO): PAPER, (PAPER, GO): GRAY, (GRAY, GO): LIVE,
    (BACKTEST, RECYCLE): DRAFT,
    (PAPER, KILL): RETIRED,
    (GRAY, KILL): PAPER, (LIVE, KILL): PAPER,     # 第一步
    (PAPER, KILL_from_demote): RETIRED,           # 第二步（内部）
}
# HOLD 不入表：走特判路径（F-I1）——apply 要求 target is None，落 from==to 记录；
# replay 对 (action=="hold" and from_stage==to_stage) 直接放行，不做查表校验。
```

- 非表中组合 → `LifecycleError(f"非法迁移: {stage} --{action}--> ...")`；
- **`HOLD` 特判（F-I1）**：不走 LEGAL 查表；要求 `decision.target is None`（否则 `LifecycleError`），落 `from_stage == to_stage == 当前 stage` 的一条记录，`stage` 不变；
- `RETIRED` 任何入参 → `LifecycleError("retired 为终态")`；
- `(LIVE, GO)` → `LifecycleError("live 为最高阶段")`；
- `RECYCLE`：`new_version` 必须非空且与 `record.history` 中**所有** `fingerprint.version` 及当前 `version` 均不同（F-D7），否则 `LifecycleError`；成功后 `fingerprint = replace(fingerprint, version=new_version)`；
- `KILL` 两步：先 `stage→paper`（`reason="kill_trigger"`），再 `paper→retired`（`reason` 沿用原判据 tuple）；
- `at` 必须 ≥ `history[-1].at`（字典序，`YYYY-MM-DD` 可直接比较）否则 `LifecycleError`。

**`archive`**：`{"schema_version": 1, "fingerprint": asdict(...), "final_stage": stage.value, "history": [asdict(r) ...], "account": dict(account) if account else None, "unresolved": [...]}`；构造后递归检查所有 float 有限（`math.isfinite`），否则 `LifecycleError("归档含 NaN/Inf")`。

**`replay`**：空序列 → `()`；逐条校验 `r.from_stage == 当前 stage`；`r.action == "hold"` 时要求 `r.from_stage == r.to_stage`（**不查 LEGAL 表**，F-I1），其余动作按 `apply` 同一张合法表校验 `(from, action)`，非法即抛；返回 `tuple(to_stage)`。

**`resolve_monitor_action`**：`green → HOLD`；`yellow → HOLD`；`red → KILL`（paper/gray/live）、`RECYCLE`（backtest）、`HOLD`（draft）；`retired` → `LifecycleError`；未知 level → `LifecycleError`。

### 3.2 `core/oos.py`（新建）

```python
"""OOS 绩效产出器（P-051c，DESIGN D6 / U-P051c-15/17/18/19/20）。

``evaluate_strategy`` 把「策略 + 数据」变成 ``StageEvidence``：连续回测一次，
按 WalkForward 窗口切段取 OOS/IS 指标，并算滚动 IC 与衰减。

I/O 边界见 IMPL C-2：仅 ``run_engine`` 经引擎产生临时目录 I/O，返回前销毁。
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

from core.config import (
    BacktestConfig,
    CostConfig,
    OptimizerConfig,
    RebalanceConfig,
    UniverseConfig,
)
from core.engine_v2 import BacktestEngineV2
from core.interfaces import IDataManager
from core.lifecycle import LifecycleError, StageEvidence
from core.metrics import MetricsResult, compute_metrics
from core.strategy import BacktestAdapter, Strategy
from core.walk_forward import WalkForwardSplitter

__all__ = ["OOSReport", "WindowOutcome", "run_engine", "evaluate_strategy", "to_evidence"]

MIN_CAPITAL = 1_000_000.0
DEFAULT_INITIAL_CAPITAL = 10_000_000.0
EPS_SHARPE = 0.1
MIN_IC_UNIVERSE = 10
```

```python
@dataclass(frozen=True)
class WindowOutcome:
    label: str                                  # "w{index}_test" / "w{index}_train"
    window_index: int
    split: str                                  # "test" | "train"
    metrics: Optional[MetricsResult] = None
    skipped_reason: str = ""                    # "" | "window_too_short"


@dataclass(frozen=True)
class OOSReport:
    aggregate: Optional[MetricsResult]
    window_metrics: tuple[tuple[str, MetricsResult], ...]
    ic_series: pd.Series
    warmup_days: int
    decay: Optional[float]
    decay_reason: str = ""                      # "" | "insufficient_signal" | "insufficient_warmup"
    skipped_windows: tuple[str, ...] = ()
    oos_dates: tuple[pd.Timestamp, ...] = ()
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
```

```python
class _NullCombiner:
    """满足 setup() 的 combiner 守卫（engine_v2 L243-L251）；weights 模式下永不调用。"""
    def combine(self, factors: Any, **kwargs: Any) -> Any:  # pragma: no cover - 永不调用
        return factors


def run_engine(
    dm: "IDataManager",
    weights: pd.DataFrame,
    *,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> pd.Series:
    """以目标权重跑一次完整回测，返回逐日组合价值（DESIGN D6.2 规格）。

    Raises:
        LifecycleError: ``initial_capital < 1e6``（最低佣金主导成本结构，N-4）；
            或引擎未产生快照。
    """
    if not np.isfinite(initial_capital) or initial_capital < MIN_CAPITAL:
        raise LifecycleError("资金过小：最低佣金 5 元将主导成本结构")
    cfg = BacktestConfig(
        output_dir=Path("."),                  # 占位，下面被临时目录覆盖
        factor_files=[],
        initial_capital=float(initial_capital),
        cost=CostConfig(),                      # commission_min=5.0（config.py L194），刻意保留真实成本
        optimizer=OptimizerConfig(method="equal_weight", target_count=1, max_weight=1.0),
        rebalance=RebalanceConfig(method="fixed", frequency="daily"),
        universe=UniverseConfig(
            exclude_na_factors=False, exclude_suspended=False, exclude_limit_up=False
        ),
        enable_pending_orders=False,
        write_manifest=False,
        invariant_mode="off",
        day_error_mode="off",
    )
    with tempfile.TemporaryDirectory(prefix="p051c_oos_") as tmp:
        cfg.output_dir = Path(tmp)
        engine = BacktestEngineV2(cfg, data_manager=dm, factor_combiner=_NullCombiner())
        engine.setup()
        engine.set_signal(weights, mode="weights")
        results = engine.run()
        pv = results.get("portfolio_value")
        if not isinstance(pv, pd.Series) or pv.empty:
            raise LifecycleError("回测未产生组合价值序列")
        return pv.astype(float).copy()
```

```python
def evaluate_strategy(
    dm: "IDataManager",
    strategy: Strategy,
    *,
    min_history: int,
    signal: Optional[pd.DataFrame] = None,
    tradable: Optional[pd.DataFrame] = None,
    splitter: Optional[WalkForwardSplitter] = None,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> OOSReport:
    """OOS 绩效产出器（D6.1-D6.4）。纯计算；唯一 I/O 经 ``run_engine``（C-2）。"""
```

**执行顺序（与 D6.1-D6.4 逐条对应）**

1. 参数校验：`min_history < 1` → `LifecycleError`；`W = min_history + 1`；`len(dm.trade_dates) <= W` → `LifecycleError("样本不足：需要 > W 个交易日")`；
2. 视图：`signal = pd.DataFrame(True, index=dm.trade_dates, columns=dm.stock_codes)`（调用方给 `signal` 时用之）+ `views_from_data(dm, signal, tradable=tradable, history_window=W)`；
3. 权重：`adapter = BacktestAdapter(strategy)`、`frame = adapter.signals_frame(views[W:])`、`head = pd.DataFrame(0.0, index=dm.trade_dates[:W], columns=frame.columns)`、`full = pd.concat([head, frame])`；`list(full.index) != list(dm.trade_dates)` → `LifecycleError`；
4. 净值：`pv = run_engine(dm, full, initial_capital=initial_capital)`；
5. 切窗：`splitter or WalkForwardSplitter(dates=dm.trade_dates, train_size=252, test_size=63, purge_gap=5)`（[walk_forward.py L111-L120](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py#L111-L120)）；**不得用 `create_walk_forward_splits`**——该便捷函数内部自建 `pd.date_range(..., freq="B")`，工作日历 ≠ 实际交易日（同 D6.2 禁用 `test_dates` 的理由）；`for win in splitter.split()` **无参**；
6. 段抽取（D6.2 原文）：

```python
def _segment(pv: pd.Series, start: pd.Timestamp, end: pd.Timestamp, w: int) -> pd.Series:
    left = max(int(pv.index.searchsorted(start)) - 1, w)
    right = int(pv.index.searchsorted(end, side="right"))
    return pv.iloc[left:right] if right > left else pv.iloc[0:0]
```

7. 逐窗指标：`len(seg) < 2` → `WindowOutcome(skipped_reason="window_too_short")`；否则 `compute_metrics(seg.to_numpy())`（唯一绩效口径，`len>=2` 由 7 保证）；train 段同法；
8. 聚合：有效 test 段 `seg / seg.iloc[0]` 依次连乘（锚点 1.0）→ `agg_pv`；`len(agg_pv) >= 2` → `compute_metrics`；否则 `aggregate=None, decay_reason="insufficient_warmup"`；
9. decay（C-8）：`mean_is`/`mean_oos` 为逐窗 sharpe 均值；无有效窗或 `abs(mean_is) < EPS_SHARPE` → `decay=None, decay_reason="insufficient_signal"`；
10. IC（C-10）：`next_ret = dm.get_adj_price("close", "raw").pct_change().shift(-1)`，只对 `oos_dates`（各 test 段日期并集）计算；
11. 返回 `OOSReport`（`warmup_days=W`、`skipped_windows`、`oos_dates`）。

```python
def to_evidence(
    report: OOSReport,
    *,
    source: str,
    paper_days: int = 0,
    paper_trades: int = 0,
    current_drawdown: Optional[float] = None,
    account_total: Optional[float] = None,
) -> StageEvidence:
    """OOSReport → StageEvidence（lifecycle 的唯一输入形态）。"""
```

`to_evidence` 只做字段搬运：`metrics=report.aggregate`、`is_metrics=None`（D6.2「train 仅供 decay」）、`window_metrics=report.window_metrics`、`ic_series=report.ic_series`、`warmup_days`、`is_oos_decay=report.decay`。

### 3.3 `core/virtual_account.py`（新建）

```python
"""多策略虚拟子账户（P-051c，DESIGN D7 / I7 / I8）。

纯记账：不接引擎、不读写文件、不 import lifecycle（D7）。变更全部返回新实例。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

__all__ = ["VirtualAccount", "BudgetCheck", "check_allocation", "check_book"]

TOL = 1e-9
```

```python
@dataclass(frozen=True)
class VirtualAccount:
    strategy_id: str
    cash: float
    reserved: float
    positions: Mapping[str, float]
    total: float

    def __post_init__(self) -> None:
        # I7：cash + reserved + Σpositions == total（1e-9）
        # cash/reserved/positions 均 >= 0；violation -> ValueError

    def allocate(self, notional: float) -> "VirtualAccount":
        """额度层：注资/撤资（cash += notional，total += notional）；cash 不足抛 ValueError。"""

    def try_reserve(self, notional: float) -> tuple["VirtualAccount", bool]:
        """订单层：cash → reserved；不足返回 (self, False) 不抛错。"""

    def release(self, notional: float) -> "VirtualAccount":
        """reserved → cash；超过 reserved 抛 ValueError。"""

    def fill(self, code: str, notional: float) -> "VirtualAccount":
        """以实际成交额入账：reserved -= notional，positions[code] += notional（F-D6）。"""
```

**语义定死（D7 留白处的落地）**

| 方法 | 前置校验 | 记账 |
|------|----------|------|
| `allocate` | `notional` 有限非零；注资（`>0`）恒可；撤资（`<0`）须 `cash + notional >= 0` **且** `total + notional >= reserved`（F-I8②：总额仍须覆盖锁定资金） | `cash += notional`；`total += notional` |
| `try_reserve` | `notional > 0`（否则 `ValueError`） | `cash -= n`, `reserved += n`；不足 → `(self, False)` |
| `release` | `0 < notional <= reserved + TOL` | `reserved -= n`, `cash += n` |
| `fill` | `0 < notional <= reserved + TOL`（否则 `ValueError`，F-D6） | `reserved -= n`, `positions[code] += n` |

`allocate` 的语义（**IMPL 澄清 C-12**）：D7 原文「调整 cash/positions 目标」不足以唯一实现。本稿取**额度/注资语义**——`total` 是策略被分配的资金规模，`allocate` 改变它而不改变持仓构成；`allocate` 与 `try_reserve` 分属两层、互不重复记账（I8 的实质）。若 Step 6 认为应为「cash→positions 目标划转」，需同时改 `total` 不变性与 D7 文本，成本更高，故不取。

```python
@dataclass(frozen=True)
class BudgetCheck:
    ok: bool
    violations: tuple[str, ...]


def check_allocation(
    weights: Mapping[str, float], total: float, *, max_weight: float = 1.0
) -> BudgetCheck:
    """单策略目标权重校验：非负、≤ max_weight、Σ ≤ 1（均含 TOL）。"""

def check_book(accounts: Mapping[str, VirtualAccount], total: float) -> BudgetCheck:
    """账本校验：Σ account.total ≤ total + TOL；任一账户 I7 破缺时在该层已抛错。"""
```

### 3.4 测试文件映射（53 条）

| 文件 | 组 | 条数 | 关键断言 |
|------|----|------|----------|
| `tests/test_p051c_lifecycle.py` | L | 14 | 四段 GO 链 + `(LIVE, GO)` 抛错 + HOLD 原地落记录 + RECYCLE 新版本 + 版本重复抛错 + 非法迁移 + RETIRED 终态 + KILL 一步/两步（paper/gray/live 各一）+ I5 确定性（同输入两次相等） |
| 同上 | G | 10 | sharpe<0 → KILL/RECYCLE；sharpe 不足 → backtest RECYCLE；drawdown 超阈值 → HOLD；>2× → KILL；decay 超限 → HOLD；decay None → `insufficient_signal`；IC 不足 → HOLD；paper_days 双条件 → HOLD；`source` 门 → HOLD；`capital` 门 → HOLD |
| 同上 | R | 5 | `archive` 结构与 `schema_version`；JSON 往返 `json.dumps/loads` 相等；含 NaN → 抛错；`replay` 前缀收敛（I9，**含 HOLD 记录放行、不查 LEGAL 表**，F-I1）；`from_stage` 链断 → 抛错 |
| `tests/test_p051c_oos.py` | O | 11 | `searchsorted` 非交易日端点；左锚 clamp `W`；短窗 → `window_too_short` 且 Gate HOLD；聚合按段首归一；decay → `None`；IC 全零日缺省；IC <10 标的缺省（**含末日/停牌 NaN 的 dropna 有效对数断言**，F-I5）；`min_history<1` 抛错；`initial_capital<1e6` 抛错；预热段排除（`aggregate.n_periods` 不含前 W 日）；无前视（篡改未来数据不改过去段指标 + dm 面板只读断言，F-I8③） |
| `tests/test_p051c_virtual_account.py` | A | 10 | I7 守恒；`try_reserve` 成功/不足；`release`；`fill` 入账；`fill` 差额两步守恒；`fill` 超 reserved 抛错；`allocate` 不动 positions（I8）；`check_allocation` 三类 violation；`check_book` Σ 超限 |
| `tests/test_p051c_end_to_end.py` | E | 3 | ①**GO 全链**：非等权 fake Strategy + **12 标的** fixture（O-2-1：IC 门槛 `len(pair) >= 10` 与 2 标的 fixture 结构性冲突——`ic_series` 恒空 → 判据 8「序列空 → 追加 ic」→ HOLD，GO 永不可达；权重差异化不够，**标的数必须 ≥ 10**）→ `evaluate_strategy` → `to_evidence` → `evaluate_gate == GO`；②**四模板参数化**（4 例计 1 条，**Step 8 R-1 定死口径：E2 单函数循环断言、1 个 pytest 收集项**——若改 `@parametrize` 展开为 4 收集项则总数 56、pytest 目标漂移至 1147，禁改）：四模板沿用 2 标的 fixture，仅断言「产出合法 `OOSReport` + `to_evidence` 可构造 + `evaluate_gate` 返回合法 `GateAction`」——**不**断言 GO（等权 → IC 恒 NaN，F-I3 机理不变）；③全量 golden 数不变（22） |

**实测目标**：`pytest` 1091 + 53 = **1144**；mypy 0 error（新增 3 文件纳入既有 `core` target，119→**122 files**）；black `--check .` 通过（240→**247 files**）。

### 3.5 O 组测试的数据构造

复用 [tests/_synth_fixture.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_synth_fixture.py) 的 `write_price_fixture`（P-051b 已用于 E2），`PERIODS=120`、`WINDOW=10`，`dm` 走真实 `DataManager`（`BacktestEngineV2(cfg).setup()` 后取 `engine.dm`，与 E2 同法）。

**必须显式传小窗口 splitter（F-I2）**：默认 `train_size=252` 对 120 日样本**产不出任何窗口**（`split()` 首轮 `test_end_idx = 252+5+63-1 = 319 >= 120` → 立即 break，[walk_forward.py](file:///f:/Coding/Factor_Trading_v3.0/core/walk_forward.py)），此时 `aggregate=None`、全部窗口类断言无对象。O 组统一传：

```python
WalkForwardSplitter(dates=dm.trade_dates, train_size=40, test_size=20, purge_gap=2)
```

窗口算术（`step_size` 默认 = `test_size` = 20）：`w0` train 0-39 / test 42-61；`w1` 62-81；`w2` 82-101；`w3` 要求 test_end 122 ≥ 120 → break → **共 3 窗**，末窗 test_end = 索引 101，其后尚有 18 个交易日可作「未来数据」。

**无前视用例的构造**：先在原数据上取 OOS 指标；再把索引 102 之后的收盘价整体 +50% 重写价格文件、重建 dm 重跑；断言**此前所有窗口指标逐值不变**（`pytest.approx` 相等）**且重建前后原 dm 的面板逐值相等**（F-I8③：`run_engine` 只读不写，共享 dm 不得被引擎污染）。该用例同时充当 C-1 装配的可执行验证。

---

## 4. 与 DESIGN 的偏差与补齐（Step 6 复核清单）

| # | 项 | 性质 | 处置 |
|---|----|------|------|
| D-1 | I1「零 I/O」与 D6.2 调用引擎冲突 | **DESIGN 缺口** | C-2 语义修正（临时目录 + 返回前销毁）；**已回写 DESIGN I1 脚注（Step 6）** |
| D-2 | `StageEvidence` 缺 `warmup_days` / `is_oos_decay` | **DESIGN 契约遗漏** | C-5 补齐；**已回写 DESIGN §3 三字段（F-I7）** |
| D-3 | D1「三模块互不 import」与 D6.2 要求 oos 抛 `LifecycleError` 冲突 | **DESIGN 内部张力** | C-6：仅 import 异常类型，无数据流；**已回写 DESIGN D1 例外脚注（F-I4）** |
| D-4 | D7 `allocate` 语义不足以唯一实现 | **DESIGN 留白** | C-12：注资/撤资语义（改 `total`，不动持仓）；撤资含锁定资金保护（F-I8②） |
| D-5 | D4 `capital` 判据无数据来源 | **DESIGN 留白** | `StageEvidence.account_total`（虚拟账户 `total` 聚合后传入；已回写 DESIGN §3） |
| D-6 | D2/D10 未写 HOLD 是否落记录 | **DESIGN 留白** | C-11：落 `from==to` 记录；**HOLD 走特判、不入 LEGAL 表（F-I1）** |

**Step 6 首轮 8 项修复回执（2026-11-21，作者基座 DeepSeek-V4.1-Flash）**

| 编号 | 严重度 | 修复落点 |
|------|--------|----------|
| F-I1 | P1 | §3.1 `apply` 增「HOLD 特判」条目（`target is None` + 落 `from==to` 记录，不查表）；`replay` 增 hold 放行；LEGAL 代码块加注释；L 组 HOLD 用例 + R 组 replay 用例各补 1 断言（计入既有条目，**用例数不变**） |
| F-I2 | P2 | §3.5 定 `PERIODS=120` + 显式 `train_size=40/test_size=20/purge_gap=2`（3 窗，末窗 test_end=idx 101，其后 18 日可作未来数据）；给出窗口算术与零窗口成因（`252+5+63-1 = 319 >= 120`） |
| F-I3 | P2 | §3.4 E 组改为「非等权 fake Strategy 断言 GO」+「四模板仅断言合法报告/可构造/合法动作」；注明等权 → spearman 常数 → IC 恒 NaN → 锁死 HOLD 的机理 |
| F-I4 | P2 | **回写 DESIGN D1 例外脚注**（仅异常类型 import，零数据流）；§4 D-3 行同步 |
| F-I5 | P2 | C-10 伪码改 `pd.concat([...]).dropna()` 后 `len<10`，与 stats.py L66-L72 同序；O 组 IC 用例补停牌/末日 NaN 断言 |
| F-I6 | P3 | `evaluate_gate` 增返回语义段：序 0-4 立即返回、序 5-12 全表后返回；序 3/4 标注「立即」并入 `reasons` |
| F-I7 | P3 | **回写 DESIGN §3 `StageEvidence` 三字段**（`warmup_days` / `is_oos_decay` / `account_total`） |
| F-I8 | P3 | ① `oos_dates` 定义排除段首锚点日（C-10 末段）；② `allocate` 撤资校验补 `total + notional >= reserved`；③ 无前视用例增 dm 面板只读断言 |

**用例数不变**：8 项修复全部落在既有 53 条用例的断言与文档口径内（新增断言并入既有条目），pytest 目标仍 **1144**。

---

## 5. 实施顺序（Step 5 执行序）

1. `core/lifecycle.py`（零依赖，先立契约）→ 跑 L/G/R 三组；
2. `core/virtual_account.py`（零依赖）→ 跑 A 组；
3. `core/oos.py`（依赖 1 + 既有 5 模块）→ 跑 O 组（先跑 `run_engine` 冒烟：`initial_capital<1e6` 抛错 + 装配成功）；
4. `tests/test_p051c_end_to_end.py`（依赖 1-3 + `strategies`）→ 跑 E 组；
5. 门禁：`pytest`（目标 1144）/ `mypy`（0 error）/ `black --check .`；golden 22 条零重录。

**风险预案**：若 `run_engine` 冒烟失败（如 `setup()` 仍要求因子文件、或快照不产生），**不得**改 `engine_v2`（I11）；退路为「注入 `factor_combiner` + 显式 `factor_files=[]`」已覆盖的前置条件再排查 `Tracker` 起账路径；仍不通则上报为 DESIGN 缺陷回到 Step 4，而不是在实现里打补丁。
