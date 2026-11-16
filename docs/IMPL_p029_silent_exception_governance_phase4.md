# IMPL：P-029 静默失败治理第四批（`agents/` 9 处计量）

> **批次**: P-029 · **T1**（`agents/` 3 文件；零 fail-fast、零返回值语义变更、零既有文案改写、**零新增日志**）
> **上游**: [DESIGN_p029](DESIGN_p029_silent_exception_governance_phase4.md)（D1-D7 / I1-I8 / V1-V5 / §4 规格 / §7 风险 / §8 回退点 / §11 Step 4 异构 Review pass，3 P3 已回写）
> **状态**: **Step 5 IMPL 完稿**（2026-11-16，作者基座 DeepSeek-V4.1-Flash；Step 6 须异构复核）
> **代码证据时点**: HEAD `23132cb`（代码与 `7045001` / `f802bbe` 一致，其后均为 docs-only）；§4 全部锚点为**实施前行号**

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（代码） | `agents/agent_framework.py` / `agents/multi_strategy_engine.py` / `agents/strategy_allocator.py`（**3 个，与 DESIGN §4.1 一致**） |
| 变更文件（测试/文档） | `tests/test_p029_silent_exception_governance.py`（新增）/ 本文件 / `docs/PROGRESS.md` / `CHANGELOG.md` |
| 零改动面 | `filter/` / `core/` / `strategy_evaluation/` / `scripts/` / `batch_backtest/` / `cli.py` / `pyproject.toml` / `.github/` / `tests/golden/*.json`（九面） |
| 行为变更 | **仅可观测性增强**：9 处补计量（S1-S8 + S3b）、1 处快照下移（L1152，F-S4-P029-1）；**零 fail-fast、零返回值语义变更、零日志、零捕获类型变更** |
| 门禁口径 | `MPLBACKEND=Agg` + Python312：pytest **711 → 722**（+11 实例）；`tests/` .py **80 → 81**；black `--check core tests` **117 → 118**；mypy `core` **37 files 0 error**（`agents/` 不在门禁路径，不变）；golden G1-G7 零重录 |

**不可越界的五条设计前提**：

1. **bare except 保持 bare**（S1-S3 + S4）：只替换 body 的 `pass`，**禁止**改成 `except Exception:`（D7 + I1 + R-P029-6）。
2. **零新增日志**：本批不新增任何 `logger.*` 调用、不提升既有级别、不改既有文案（I6）。
3. **S3b 的 `else` 挂 `if`（L928）而非 `try`（L929）**：挂错会在分析器创建**成功**时误计（DESIGN §9.3）。
4. **S5 合法分支不计数**：L328-329 的 `continue`（列/日期缺失）是既有合法路径，仅 L330 异常分支计量（DESIGN §9.2）。
5. **S4 快照下移不改变出口存在性**：`failure_counts` 键在 `get_performance_summary` 恒存在（`fund_manager is None` 时同样写入），仅位置后移到 S4 try/except 之后（F-S4-P029-1）。

---

## 2. 任务拆解

| ID | 批次 | 任务 | 对应 | 产出 |
|----|------|------|------|------|
| **B1** | 代码 | `agent_framework.py`：S1-S3（3 计量）+ S3b `else`（1 计量）+ S4（1 计量 + L1152 下移） | D1 / D2 / D3 | 1 文件，**净 +2 行** |
| **B1t** | 测试 | V1（参数化 3）/ V2 / V3 | V1-V2 | 新增测试文件（5 实例） |
| **B2** | 代码 | `multi_strategy_engine.py`：S5-S7（3 计量，首行插入） | D4 | 1 文件，**净 +3 行** |
| **B2t** | 测试 | V4（参数化 2）/ V5（参数化 2） | V3 | +4 实例 |
| **B3** | 代码 | `strategy_allocator.py`：`MeanVarianceAllocator` 三件套 + S8 计量（M-A） | D5 / D6 | 1 文件，**净 ≈+10 行** |
| **B3t** | 测试 | V6 / V7 | V4-V5 | +2 实例 |
| **B4** | 文档 | 门禁回归 + 本文件 §6/§10 实测回填 + `PROGRESS` §3.34.4 + `CHANGELOG` | — | docs |

**计数口径**：B1 5 计量（S1/S2/S3/S3b/S4）+ B2 3 计量（S5/S6/S7）+ B3 1 计量（S8）= **9 计量**；零改动 1 处（`research_team_v2.py:25-28` import 降级，F-S4-P029-3）；测试 **11 实例** = V1 3 + V2 1 + V3 1 + V4 2 + V5 2 + V6 1 + V7 1 → `711 + 11 = 722`。

---

## 3. 实施顺序与依赖

```text
B1（agent_framework 5 计量）─→ B1t（V1/V2/V3，红→绿）
B2（multi_strategy 3 计量） ─→ B2t（V4/V5，红→绿）
B3（allocator 三件套+1 计量）─→ B3t（V6/V7，红→绿）
B1t + B2t + B3t ─→ B4（全量门禁 + 文档回填）
```

- **B1 → B2 → B3 无代码依赖**：三个文件互不引用被测路径；每批独立提交、独立红绿、独立可回退（DESIGN §8）。
- **B1 先行**：其 5 计量中有 2 处形态特殊（`else` 分支、快照下移），先落地可为 B2/B3 提供形态基准。
- **B3 最后**：`get_failure_stats()` 为 `strategy_allocator.py` **首次引入**该命名，先行在 B1/B2 落地可确认命名习惯一致（P-027 先例）。
- **每批提交前跑该批新增用例**（红态取证），补实现后再跑（绿态取证），证据记入 §10。

---

## 4. 精确变更规格

> 全部锚点为实施前 HEAD `23132cb` 行号；「净 +N」以 `git diff --numstat` 为准（估算偏差登记 §7 F-I-P029-1）。

### 4.1 `agents/agent_framework.py`（5 计量，净 +2）

**载体已存在**（P-027 落地，B1 无需新建）：`_failure_counts` L882、`_record_failure` L891-893、`get_failure_stats` L895-897。

#### S1-S3：`prepare_factors` 三处 bare except 的 `pass` → 计量（L969-992）

```python
        # 缓存投研团队需要的数据
        try:
            self._price_data = data_manager.get_adj_price("close", "forward")
        except:                                            # L971（bare 保持）
            self._record_failure("price_cache")             # 替换 L972 pass

        try:
            import pickle

            industry_path = data_manager.data_dir / "industry.pkl"
            if industry_path.exists():
                with open(industry_path, "rb") as f:
                    self._industry_data = pickle.load(f)
        except:                                            # L981
            self._record_failure("industry_cache")          # 替换 L982 pass

        try:
            import pickle

            mktcap_path = data_manager.data_dir / "mktcap.pkl"
            if mktcap_path.exists():
                with open(mktcap_path, "rb") as f:
                    self._mktcap_data = pickle.load(f)
        except:                                            # L991
            self._record_failure("mktcap_cache")            # 替换 L992 pass
```

| 站点 | 锚点 | 键 | 保留 |
|------|------|----|------|
| S1 | L971-972 | `price_cache` | `self._price_data` 保持 `None` |
| S2 | L981-982 | `industry_cache` | `self._industry_data` 保持 `None` |
| S3 | L991-992 | `mktcap_cache` | `self._mktcap_data` 保持 `None` |

#### S3b：`_init_research_team` 新增 `else`（L928-936）

```python
        if self._industry_data is not None and self._price_data is not None:   # L928
            try:
                self.rotation_analyzer = IndustryRotationAnalyzer(
                    self._industry_data, self._price_data, self._mktcap_data
                )
            except Exception as e:                                            # L933（P-027 既有，勿动）
                self._record_failure("rotation_analyzer_init")
                logger.warning(f"行业轮动分析器初始化失败: {e}")
                self.rotation_analyzer = None
        else:                                                                  # 新增
            self._record_failure("rotation_analyzer_skipped")                  # 新增
```

- `else` 缩进对齐 **L928 的 `if`**（非 L929 的 `try`）。
- 不新增 `logger.*`（D7 / F-S2-P029-1）；`self.rotation_analyzer` 保持 `__init__` 的 `None`（L881）。

#### S4：`get_performance_summary` 计量 + 快照下移（L1149-1161）

变更前：

```python
    def get_performance_summary(self) -> dict[str, Any]:
        """获取绩效摘要（扩展）"""
        summary = super().get_performance_summary()
        summary["failure_counts"] = self.get_failure_stats()      # L1152 原位置

        if self.fund_manager is not None:
            try:
                team_report = self.fund_manager.get_team_report()
                summary["team_report"] = team_report
            except:
                pass

        return summary
```

变更后：

```python
    def get_performance_summary(self) -> dict[str, Any]:
        """获取绩效摘要（扩展）"""
        summary = super().get_performance_summary()

        if self.fund_manager is not None:
            try:
                team_report = self.fund_manager.get_team_report()
                summary["team_report"] = team_report
            except:                                              # L1158（bare 保持）
                self._record_failure("performance_summary_team_report")

        summary["failure_counts"] = self.get_failure_stats()      # L1152 下移至 try/except 之后
        return summary
```

| 项 | 约束 |
|----|------|
| `team_report` | **仍不写入** summary（失败路径）；成功路径行为逐字不变（I3） |
| `failure_counts` 键 | 恒存在（`fund_manager is None` 时同样写入），仅位置后移 |
| 快照语义 | 同调失败**计入本次返回**（F-S4-P029-1）；旧行为需下一次调用才可见 |

**禁止触碰**：L336 `BaseAgent.get_performance_summary`（另一同名方法，非本批范围）。

### 4.2 `agents/multi_strategy_engine.py`（3 计量，净 +3）

**载体已存在**（P-027 落地）：`_failure_counts` L111、`_record_failure` L115-117、`get_failure_stats` L119-121、`run()` 入口清零 L154、出口 `result["failure_counts"]` L171。B2 **零载体改动**。

| 站点 | 锚点（变更前） | 插入（except 块首行） | 保留行为 |
|------|----------------|------------------------|----------|
| S5 | L330 `except (KeyError, IndexError):` | `self._record_failure("orders_missing_price")` | L331 `continue` 逐字保留；L328-329 合法 `continue` **不计数** |
| S6 | L390 `except KeyError:` | `self._record_failure("next_day_open_price")` | L391 `return`；`_next_day_orders` 不被清空（`failed_orders` 赋值在其后，不可达） |
| S7 | L452 `except KeyError:` | `self._record_failure("pending_open_price")` | L453 `return`；`pending_queue` 状态不变 |

```python
            try:
                if stock in adj_close.columns and date in adj_close.index:
                    close_price = adj_close.loc[date, stock]
                else:
                    continue
            except (KeyError, IndexError):
                self._record_failure("orders_missing_price")   # 新增
                continue
```

```python
        try:
            open_prices = self.dm.get_adj_price("open", self.base_cfg.adjustment_type).loc[date]
        except KeyError:
            self._record_failure("next_day_open_price")        # 新增
            return
```

```python
        try:
            open_prices = self.dm.get_adj_price("open", self.base_cfg.adjustment_type).loc[date]
            close_prices = self.dm.get_adj_price("close", self.base_cfg.adjustment_type).loc[date]
        except KeyError:
            self._record_failure("pending_open_price")         # 新增
            return
```

- **U-P029-2 维持**：S6/S7 的队列重试语义（`return` 后队列保留）本批不改。
- 归属核实：三处均在 `StrategyEngine`（L62 起）；`MultiStrategyEngine`（L487 起）无 except。

### 4.3 `agents/strategy_allocator.py`（三件套 + 1 计量，净 ≈+10）

**M-A**：只在 `MeanVarianceAllocator` 内自备，**不下沉 `BaseAllocator`**（L354-371 无 `__init__`，5 子类均有自有 `__init__`）。

#### 载体（`MeanVarianceAllocator.__init__` L590-607，形参零变更）

```python
    def __init__(
        self,
        risk_aversion: float = 1.0,
        turnover_penalty: float = 0.0,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ):
        """..."""
        self.lambda_risk = risk_aversion
        self.lambda_turnover = turnover_penalty
        self.min_w = min_weight
        self.max_w = max_weight
        self._failure_counts: dict[str, int] = {}          # 新增（L608）

    def _record_failure(self, key: str) -> None:            # 新增
        """记录一次降级失败（只增不清）"""
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

    def get_failure_stats(self) -> dict[str, int]:          # 新增
        """只读失败计量快照"""
        return dict(self._failure_counts)
```

#### S8：`allocate` 的 `LinAlgError` 分支（L625-630）

```python
        try:
            Sigma_inv = np.linalg.inv(Sigma)
            raw_weights = Sigma_inv @ mu
        except np.linalg.LinAlgError:
            self._record_failure("pinv_fallback")           # 新增
            # 如果奇异，使用伪逆
            raw_weights = np.linalg.pinv(Sigma) @ mu
```

- 注释 `# 如果奇异，使用伪逆` **逐字保留**（既有文案不属 `logger.*`，但 I6 口径按「既有文本零改写」从宽执行）。
- `get_failure_stats` 返回 `dict(...)` 拷贝（外部改写不影响内部，V6 断言）。

### 4.4 `tests/test_p029_silent_exception_governance.py`（新增）

单文件 7 个测试函数 / 11 实例，全部 `monkeypatch`，**禁 `unittest.mock`**。文件头 docstring 指向本文件 §5。

```python
"""P-029 静默失败治理第四批（agents/ 9 处计量）测试。

对应 docs/IMPL_p029_silent_exception_governance_phase4.md §5（V1-V7）。
全部使用 monkeypatch（禁用 mock 库，DESIGN D7）。
"""
```

导入面（实施时按此顺序）：

```python
from __future__ import annotations

import logging
import pickle
import sys
import types

import numpy as np
import pandas as pd
import pytest

import agents.agent_framework as agent_framework_module
import agents.research_team_v2 as research_team_module
from agents.agent_framework import ResearchTeamAgent
from agents.multi_strategy_engine import StrategyConfig, StrategyEngine
from agents.strategy_allocator import MeanVarianceAllocator, StrategyEvaluator
from core.config import BacktestConfig
from core.pending import OrderSide, PendingOrderQueue, create_pending_order
```

共享夹具与替身（模块级）：

```python
STOCKS = ["A", "B", "C"]
DATES = pd.bdate_range("2024-01-02", periods=3)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(10.0, index=DATES, columns=STOCKS)


def _boom(*args, **kwargs):
    raise RuntimeError("boom")


class _RaisingLoc:
    def __getitem__(self, key):
        raise KeyError("missing price")


class _MissingPriceFrame:
    """columns/index 正常但 .loc 取值必抛 KeyError（模拟日期/列缺失命中窄类型 except）。"""

    columns = pd.Index(["A"])
    index = pd.DatetimeIndex(DATES)
    loc = _RaisingLoc()


class _FakeDM:
    def __init__(self, n_days: int = 1):
        self.trade_dates = pd.bdate_range("2024-01-02", periods=n_days)
        self.stock_codes = STOCKS
        self.n_stocks = len(STOCKS)
        self.returns = pd.DataFrame(0.0, index=self.trade_dates, columns=STOCKS)

    def get_adj_price(self, field: str, adjustment_type: str) -> pd.DataFrame:
        return pd.DataFrame(10.0, index=self.trade_dates, columns=STOCKS)


def _make_engine(signal: pd.DataFrame | None = None) -> StrategyEngine:
    strategy_cfg = StrategyConfig(name="long", direction="long", target_count=2)
    base_cfg = BacktestConfig(enable_pending_orders=False)
    return StrategyEngine(
        strategy_cfg,
        base_cfg,
        _FakeDM(),
        None,
        pd.DataFrame(0.0, index=DATES, columns=STOCKS) if signal is None else signal,
    )
```

---

## 5. 测试规格（7 函数 / 11 实例）

| ID | 测试函数 | 实例 | 注入方式 | 断言要点 |
|----|----------|------|----------|----------|
| V1 | `test_cache_failure_counts` | 3 | 参数化 `("price","price_cache")` / `("industry","industry_cache")` / `("mktcap","mktcap_cache")`；`monkeypatch.setattr(agent_framework_module, "FactorPipeline", _Pipe)` + `"FactorCombiner", _Comb`；假 DM：`load_factor` 返回帧、`get_adj_price` 按 case 抛错、`data_dir=tmp_path`；industry/mktcap 写**存在但损坏**的 pkl；`monkeypatch.setattr(agent, "_init_research_team", lambda dm: None)` | 计数 `{key: 1}`；对应缓存属性 `None`；构造后 `caplog.clear()`，`prepare_factors` 期间 **WARNING+ 零记录** |
| V2 | `test_rotation_analyzer_skipped` | 1 | `monkeypatch.setitem(sys.modules, "research_team_v2", research_team_module)`；`industry_rotation_v2` 注入 fake 模块（`IndustryRotationAnalyzer` 为哑类）；`agent._research_team_available = True`；`_price_data=None` / `_industry_data=None` | `get_failure_stats() == {"rotation_analyzer_skipped": 1}`；`rotation_analyzer is None`；无 `rotation_analyzer_init` 键 |
| V3 | `test_team_report_failure` | 1 | 本地类 `_BrokenFM.get_team_report()` 抛 `RuntimeError`；`agent.fund_manager = _BrokenFM()` | `"team_report" not in summary`；`summary["failure_counts"] == {"performance_summary_team_report": 1}`（**同调**，F-S4-P029-1）；`agent_id` / `style` 等既有键仍在 |
| V4 | `test_order_missing_price` | 2 | ① 合法：`target_weights = pd.Series({"ZZZ": 1.0})` + 正常 DM ② 异常：`monkeypatch.setattr(engine.dm, "get_adj_price", lambda *a, **k: _MissingPriceFrame())` + `target_weights = pd.Series({"A": 1.0})` | ① `get_failure_stats() == {}` ② `== {"orders_missing_price": 1}`；两例均不产生订单（`_next_day_orders` 空、`pending_queue` 空/None） |
| V5 | `test_open_price_failures` | 2 | 参数化 `("next_day","next_day_open_price")` / `("pending","pending_open_price")`；均 patch `engine.dm.get_adj_price` → `_MissingPriceFrame()` ① S6：`engine._next_day_orders = [{"order": object(), "create_date": DATES[0]}]` ② S7：`engine.pending_queue = PendingOrderQueue()` + `add_order(create_pending_order("A", OrderSide.BUY, 100, DATES[0]))` | 计数各 1；S6 `len(_next_day_orders)` 不变；S7 `len(get_pending_orders())` 不变；返回 `None`；`caplog.clear()` 后 WARNING+ 零记录 |
| V6 | `test_pinv_fallback` | 1 | `def _singular(m): raise np.linalg.LinAlgError("singular")`；`monkeypatch.setattr(np.linalg, "inv", _singular)`；`evaluator = StrategyEvaluator(n_strategies=2)` | `alloc.get_failure_stats() == {"pinv_fallback": 1}`；`abs(weights.sum() - 1.0) < 1e-9`；改写 getter 返回值后内部仍为 1（拷贝语义） |
| V7 | `test_normal_path_zero_counts` | 1 | ① engine：`monkeypatch.setattr(engine, "_process_trading_day", lambda date, i: None)` 后 `run()` ② allocator：不 patch `np.linalg.inv`，`StrategyEvaluator(n_strategies=2)` | ① `result["failure_counts"] == {}` ② `alloc.get_failure_stats() == {}` 且权重归一 |

**红态预期（实施前）**：

| 用例 | 失败形态 |
|------|----------|
| V1 | `assert {} == {"price_cache": 1}`（键不存在 → 计数缺失） |
| V2 | `assert {} == {"rotation_analyzer_skipped": 1}`（`else` 分支尚不存在） |
| V3 | `assert {} == {"performance_summary_team_report": 1}`（先在 L1152 快照 → 空字典） |
| V4 | 异常参数 `assert {} == {"orders_missing_price": 1}`；合法参数**已通过**（计数 0） |
| V5 | `assert {} == {"next_day_open_price": 1}` / `{"pending_open_price": 1}` |
| V6 | `AttributeError: 'MeanVarianceAllocator' object has no attribute 'get_failure_stats'` |
| V7 | engine 侧**已通过**（P-027 已加 `failure_counts` 出口）；allocator 侧 `AttributeError: 'MeanVarianceAllocator' object has no attribute 'get_failure_stats'` |

**红态纪律**：V4 合法参数与 V7 engine 侧在实施前即通过属预期（防「只计异常」与「正常零计数」的既有行为基线），红态验收以**参数化整体**为准（V4 红 1 绿 1、V7 红 1 绿 1）。

### 5.1 注入路径实证（Step 5 探针，改前代码）

**探针**: `%TEMP%\p029_step5_probe.py`（仓库外，只读；改前 HEAD `23132cb`，7 组注入逐一跑通）

| 组 | 实测读数 | 与 §5 预期 |
|----|----------|-----------|
| V1-price | `prepare_factors` 正常返回；`counts={}`、`_price_data is None`、industry/mktcap 均 `None`（损坏 pkl 已进 except） | 红态 `{}`，符合 |
| V2 | `_init_research_team(None)` 正常返回；`counts={}`、`rotation_analyzer is None` | 红态 `{}`，符合 |
| V3 | `team_report in summary == False`；`summary["failure_counts"] == {}` | **实证 F-S4-P029-1**：L1152 快照先于 S4 except，红态即空 |
| V4 合法 / 异常 | 两例 `counts={}`、无订单 | 合法侧预期通过；异常侧红态 `{}` |
| V5 S6 / S7 | `counts={}`；S6 `_next_day_orders` 保留 1 条；S7 队列长度不变 | 红态 `{}`，队列语义实证不变 |
| V6 | `hasattr(alloc, "get_failure_stats") == False`；正常路径 `weights.sum()==1.0`；强制 `LinAlgError` 后 pinv 路径 `weights.sum()==1.0` | 红态 `AttributeError`，符合 |
| V7 | 正常求逆 `weights.sum()==1.0` | 基线通过 |

**附带证实**：构造期日志 `投研团队模块未完全可用` / `分层贝叶斯引擎不可用` 出现在 `prepare_factors` **之前** → A6 的 `caplog.clear()` 处置必要。

---

## 6. 门禁口径

| 门禁 | 命令 | 基线（Step 4 实测） | 目标 |
|------|------|---------------------|------|
| 新增测试 | `$py -m pytest tests/test_p029_silent_exception_governance.py -q` | 红（0 收集于实施前） | **11 passed** |
| 全量测试 | `$env:MPLBACKEND="Agg"; $py -m pytest -q` | **711** | **722 passed** |
| 类型 | `$py -m mypy --explicit-package-bases --check-untyped-defs core` | **37 files 0** | **37 files 0**（`agents/` 不在门禁） |
| 形态 | `$py -m black --check core tests` | **117 unchanged** | **118 unchanged** |
| 测试文件数 | `Get-ChildItem tests -Recurse -Filter *.py \| Measure-Object` | **80** | **81** |
| 静态不变式 I1 | AST 扫描十文件 `except Exception` | **22** | **22** |
| 静态不变式 I4 | `git diff --stat` | — | 仅 3 代码 + 1 测试；九面 diff 空 |
| 静态不变式 I6 | `git diff -U0 \| Select-String "logger\."` | — | **0 增 0 删** |
| golden | `$py -m pytest tests -q -k golden` + `git status --short tests/golden/` | 全绿 | 全绿 + golden 目录空 |

`$py` = `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（默认 `python` 指向 Anaconda 3.13，勿用）。

**I1 复核命令**（与 Step 4 同口径，独立可复跑）：

```powershell
$py -c "import ast,pathlib;r=pathlib.Path('.');s=[p for d in ['agents','filter','scripts','batch_backtest','strategy_evaluation'] for p in (r/d).rglob('*.py')]+[r/'cli.py'];print(sum(1 for p in s if p.exists() for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n,ast.ExceptHandler) and isinstance(n.type,ast.Name) and n.type.id=='Exception'))"
```

预期输出 `22`。

---

## 7. 实施注意项（顺序敏感与易误改点）

| ID | 级别 | 注意项 | 处置 |
|----|------|--------|------|
| **A1** | **P2** | S3b 的 `else` 缩进必须对齐 **L928 的 `if`**；若误写成 L929 `try` 的 `else`，分析器**创建成功时**会误计 `rotation_analyzer_skipped` | 实施后以 AST 校验：`else` 的 `orelse` 归属 `If` 节点而非 `Try`（`ast.walk` 打印父节点类型） |
| **A2** | **P2** | `_init_research_team` 首行 `if not self._research_team_available: return`（L901-902）；V2 若未先置 `True`，`else` 分支不可达、计数恒 0 | V2 显式 `agent._research_team_available = True` + `sys.modules` 注入两模块 |
| **A3** | **P2** | S1-S3 + S4 是 **bare `except:`**；只替换 body `pass`，**禁止**改写为 `except Exception:` | `git diff` 复核 4 处 `except:` 行零变更（I1 恒 22 的直接保证） |
| **A4** | P3 | S5 的合法 `continue`（L328-329）与异常 `continue`（L331）返回同值 | V4 双参数（合法 0 / 异常 1）才能证明「只计异常」 |
| **A5** | P3 | `prepare_factors` 依赖 `FactorPipeline` / `FactorCombiner` / `DataManager.load_factor` | V1 以模块级 `monkeypatch.setattr` 注入轻量 `_Pipe` / `_Comb` + 假 DM，不构造真实管道 |
| **A6** | P3 | `ResearchTeamAgent()` 构造期会因 `hierarchical_bayesian_agent` / `research_team_v2` 顶层导入失败打 **2 条 warning**（与 S1-S3 无关） | V1「零 WARNING」断言在构造后 `caplog.clear()`，只覆盖 `prepare_factors` 期间 |
| **A7** | P3 | V7 engine 侧若走真实 `_process_trading_day`，rebalance 触发器在测试日期上的行为不确定 | V7 以 no-op `_process_trading_day` 固定「无失败路径」，只验证清零 + 正常出口 |

**实施期发现（Step 5 自查）**：

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-I-P029-1 | P3 | DESIGN §4.1「`agent_framework.py` ≈ 9 新增行」为**变更行数**而非净新增：S1-S3 与 S4 各为 `pass` → 计量行（净 0），S3b 净 +2，L1152 位移净 0 → **净 +2 / 变更 7** | 本文件 §2/§4.1 已按「净 +2」标注；Step 9 以 `git diff --numstat` 回填实测 |
| O-I-P029-1 | 观察 | DESIGN §4.1「`strategy_allocator.py` ≈ 12」估算含空行余量，实测约 +10（计数器 1 + 两方法 6 + except 1 + 2 空行） | 不修正 DESIGN，Step 9 回填实测 |

---

## 8. 回退点

| 批 | 提交单元 | 文件 | 回退方式 |
|----|----------|------|----------|
| B1 | S1-S3 + S3b + S4（5 计量） | `agents/agent_framework.py` | `git checkout <base> -- agents/agent_framework.py`；回退后 4 处恢复 `pass`、`else` 消失（无构造期依赖） |
| B2 | S5-S7（3 计量） | `agents/multi_strategy_engine.py` | 单文件回退；`failure_counts` 键为只增，消费方（`run()` 出口）回退无破坏 |
| B3 | S8 载体 + 1 计量 | `agents/strategy_allocator.py` | 单文件回退；`MeanVarianceAllocator` 恢复无计数器（`get_failure_stats` 调用方唯 V6/V7） |
| B4 | 文档回填 | 本文件 / `PROGRESS` / `CHANGELOG` | `git revert <docs SHA>` |

**全批回退**：`git revert <SHA>`（3 代码文件 + 1 测试文件）；因分 3 个代码提交单元 + 1 文档单元，可逐单元 revert。

---

## 9. 下一步

1. **Step 6 独立 Review**（异构基座 ≠ 本文作者 DeepSeek）：核对 §4 三文件锚点与 DESIGN §4.1 一一对应、`f"..."` 键名 9 个可机检、V1-V7 注入路径可实现、I1/I8 算术自洽、A1-A7 七项注意项成立。
2. **Step 7 CHECKLIST**：按 V1-V7 + I1-I8 落验收条件，实测列一律 `[待 Step 9]`（RULE-1 零预填），目标约 30+ 项。
3. **Step 9 TDD**：按 B1 → B1t → B2 → B2t → B3 → B3t 逐批红绿，最后 B4 回填本文件 §6 实测列与 §10。
