# IMPL：P-025 日循环异常分类与 retry 语义

> **批次**: P-025 · **T1**（`core/` 行为契约 + 结果字典新增键）
> **上游**: [DESIGN_p025](DESIGN_p025_daily_loop_exception_semantics.md)（D1-D7 / I1-I7 / V1-V12 / §10 Step 4 Review）
> **状态**: Step 5 完稿；**Step 6 Review 通过**（§6：1 P2 + 3 P3 回写 + 3 观察）
> **代码证据时点**: HEAD `0636358`（2026-11-12，工作区干净）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件 | `core/diagnostics.py`（新增）/ `core/config.py` / `core/engine_v2.py` / `core/execution.py` / `core/portfolio.py` / `tests/test_p025_day_error_diagnostics.py`（新增）/ `README.md` / `docs/ARCHITECTURE.md` / `CHANGELOG.md` / `docs/PROGRESS.md` |
| 零改动面 | `core/interfaces.py`（**不**给 `IExecutionSimulator` 加抽象方法——sink 走可选 duck-typing，否则全部 fake 执行器立刻 TypeError）/ `core/pending.py` / `core/data.py` / `core/rebalance.py` / `core/factory.py`（仅间接受益于 D6）/ `engine_v3_vector.py` / `cli.py` / `tests/golden/*.json` / `pyproject.toml` / `.github/` |
| 行为变更 | **3 项**：① `build_optimizer` 未知 method → `ValueError`（原静默等权）；② `mean_variance` 实际生效 `MeanVarianceOptimizer`（原静默等权）；③ 4 个协方差方法在 `n_days <= cov_lookback` 时 `setup()` 抛 `RuntimeError`（原 run 期静默全失败）。④ 结果字典新增 `run_diagnostics` 键（只增，不改既有 10 键） |
| 门禁口径 | `mypy --explicit-package-bases --check-untyped-defs core`：37 files 0 error（新增 1 文件）；`black --check`：文件数 +1；`pytest -q`：654 → ≥664 |

**设计前提**：mypy `python_version = "3.10"`（pyproject L106）→ `ExceptionGroup` 不能直接写名字（3.10 typeshed 无此符号），必须经 `getattr(builtins, "ExceptionGroup")` 取得（见 §4.1 实现）。

---

## 2. 任务拆解

| ID | 批次 | 任务 | 对应 | 产出 |
|----|------|------|------|------|
| **T-1** | B1 | `core/diagnostics.py` 新增（`DayErrorRecord` / `classify_day_error` / `DayErrorCollector`）+ `config.py` +1 行 + T1-T4 单测 | D2 / D3 / D1 | 新文件 ≈135 行；config +1；测试 4 项 |
| **T-2** | B2 | `engine_v2.py`：`__init__` 建采集器 / `run()` catch 改造 / `run_diagnostics` 入 `additional_info` + T5-T7 | D4 | 引擎 +10 行；测试 3 项 |
| **T-3** | B3 | `execution.py` `set_error_sink` + except 内调用；`engine_v2` 优化 catch 接入 + setup sink 绑定 + T8 | D5 | execution +11；engine +5；测试 1 项 |
| **T-4** | B3 | `portfolio.py` D6 别名 + fail-closed + T10 | D6 | +7 行；测试 1 项 |
| **T-5** | B3 | `engine_v2.py` setup 预检（D7-O2）+ T9 | D7 | +10 行；测试 1 项 |
| **T-6** | B4 | README 结果字段 / ARCHITECTURE 模块与计数 / CHANGELOG `Changed` / PROGRESS | — | docs |

---

## 3. 实施顺序与依赖

```text
T-1（B1 采集器基座）─→ T-2（B2 引擎诊断主线）─→ T-3（B3 sink 接线）
                                                      ├─→ T-4（D6，独立）
                                                      └─→ T-5（D7 预检，依赖 T-3 的 T8 先绿）
T-1..T-5 ─→ T-6（文档）
```

- **T-1 必须最先**：`diagnostics.py` 是 T-2/T-3 的被依赖项；T1-T4 单测可独立跑（无引擎）。
- **T-3 先于 T-5**：T8（80 日 + `cov_lookback=60`）需要 setup 预检**未**触发（80 > 60）；若先做 T-5，T8 仍不触发预检，但 T9 的「4 日 + min_variance」会因 T-5 先绿而无法取证红态，故按 T-3 → T-5 顺序保留两个可独立观测的红态。
- **T-4 与 T-1..T-3 无依赖**，但必须**后于 T-1**（否则 T10 的 `mean_variance` 红态会与 D7 预检混淆——`mean_variance` 若进 `cov_methods` 且 4 日数据，setup 会先抛预检错，取不到 D6 的红）。
- **T-4 与 T-5 不同批**：D6 是「词表/分派」缺陷，D7 是「入口预检」；提交边界分开以保回退粒度（DESIGN §8）。
- **合批判断**：T-1..T-5 全部落在 `core/` 且多数集中于 `engine_v2.py`，Step 9 可按 §7 回退表做「单 commit + 文件级回退」，与 P-023 同法。

---

## 4. 精确变更预案

### 4.1 T-1a 新增 `core/diagnostics.py`

> 无 `core.*` 依赖（仅 `numpy` / 标准库）→ 不构成循环依赖；不下沉到 `engine_v2` 是为了让 `execution.py` 可反向复用（D3）。

```python
"""日级异常诊断采集（P-025）

与引擎解耦的轻量采集器：日循环 / 组合优化 / 订单执行三处统一汇入。
设计约束见 docs/DESIGN_p025_daily_loop_exception_semantics.md（D2 / D3）。

- 分类只依赖 (stage, 异常类型)，不匹配消息文本（D2）
- record 任何路径不抛错（I3）：内部兜底后降级为 logger.error
- off 模式零分配（I4）：record 首行直接返回 None
"""

from __future__ import annotations

import builtins
import logging
import sys
from dataclasses import asdict, dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# 阶段词表（D3）：本批实际产生 day_loop / rebalance / execution 三类；
# 其余值为前向兼容预留，本批不在这些粒度插桩（见 §9 F-S5-P025-1）。
STAGES = (
    "day_loop", "settle", "pending", "next_day", "rebalance",
    "mark", "execution", "risk", "dump", "finalize",
)

# raise 模式参与抛出的类别（D1/D4：execution/solver 业务可恢复，不抛）
RAISE_CATEGORIES = frozenset({"data", "internal"})

# 判定为降级的类别（D4 的 degraded 语义）
DEGRADED_CATEGORIES = frozenset({"data", "solver", "internal"})


@dataclass(frozen=True)
class DayErrorRecord:
    """单条日级异常记录"""

    date: str
    stage: str
    category: str
    error_type: str
    message: str
    retryable: bool


def classify_day_error(stage: str, exc: BaseException) -> tuple[str, bool]:
    """按 (stage, 异常类型) 判定 (类别, 是否可重试)；不看消息文本（D2）"""
    if stage == "execution":
        return "execution", True
    if stage == "rebalance":
        if isinstance(exc, np.linalg.LinAlgError):
            return "solver", False
        if type(exc).__name__ in {"SolverError", "DCPError"}:
            # 不 import cvxpy：仅按类名识别，避免 diagnostics 依赖重求解器
            return "solver", False
        if isinstance(exc, ValueError):
            # 「…需要收益率数据或协方差矩阵」等输入不足
            return "solver", False
        return "internal", False
    if isinstance(exc, (KeyError, FileNotFoundError, ValueError)):
        # day_loop 下的数据形态：缺列 / 缺键 / 日期不齐
        return "data", True
    return "internal", False


class DayErrorCollector:
    """日级异常采集器（零抛错 / 有上限 / 可去重）"""

    MAX_SAMPLES = 50
    MAX_MESSAGE = 200

    def __init__(self, mode: str = "report"):
        self._mode = mode
        self._records: list[DayErrorRecord] = []
        self._index: set[tuple[str, str, str, str, str]] = set()
        self._counts: dict[str, int] = {}
        self._category_counts: dict[str, int] = {}  # 按 category 计数，不受明细上限影响（F-S6-P025-2）
        self._first_raiseable: Optional[DayErrorRecord] = None  # 首条 raiseable 样本（防截断后取不到）
        self._truncated = False

    def record(self, date: Any, stage: str, exc: BaseException) -> Optional[DayErrorRecord]:
        """记录一条异常；本方法不得抛错（I3）"""
        if self._mode == "off":
            return None
        try:
            category, retryable = classify_day_error(stage, exc)
            rec = DayErrorRecord(
                date=str(date),
                stage=str(stage),
                category=category,
                error_type=type(exc).__name__,
                message=str(exc)[: self.MAX_MESSAGE],
                retryable=retryable,
            )
            self._counts[rec.stage] = self._counts.get(rec.stage, 0) + 1
            self._category_counts[rec.category] = self._category_counts.get(rec.category, 0) + 1
            if rec.category in RAISE_CATEGORIES and self._first_raiseable is None:
                self._first_raiseable = rec
            key = (rec.date, rec.stage, rec.category, rec.error_type, rec.message)
            if key in self._index:
                return rec
            if len(self._records) >= self.MAX_SAMPLES:
                self._truncated = True
                return rec
            self._records.append(rec)
            self._index.add(key)
            return rec
        except Exception:
            logger.error("日级异常采集失败（已忽略）", exc_info=True)
            return None

    def record_failure(
        self, date: Any, stage: str, reason: str, category: str = "execution"
    ) -> None:
        """记录非异常型失败（success=False）；本批无生产调用点（§9 F-S5-P025-2）"""
        if self._mode == "off":
            return
        try:
            rec = DayErrorRecord(
                date=str(date),
                stage=str(stage),
                category=str(category),
                error_type="FailureResult",
                message=str(reason)[: self.MAX_MESSAGE],
                retryable=True,
            )
            self._counts[rec.stage] = self._counts.get(rec.stage, 0) + 1
            self._category_counts[rec.category] = self._category_counts.get(rec.category, 0) + 1
            if rec.category in RAISE_CATEGORIES and self._first_raiseable is None:
                self._first_raiseable = rec
            key = (rec.date, rec.stage, rec.category, rec.error_type, rec.message)
            if key in self._index:
                return
            if len(self._records) >= self.MAX_SAMPLES:
                self._truncated = True
                return
            self._records.append(rec)
            self._index.add(key)
        except Exception:
            logger.error("日级异常采集失败（已忽略）", exc_info=True)

    def summary(self) -> dict[str, Any]:
        """结果字典载荷；off 模式最小化（I4）"""
        if self._mode == "off":
            return {"mode": "off"}
        degraded = self._truncated or any(
            self._category_counts.get(c, 0) > 0 for c in DEGRADED_CATEGORIES
        )
        return {
            "mode": self._mode,
            "degraded": degraded,
            "counts": dict(self._counts),
            "samples": [asdict(r) for r in self._records],
            "truncated": self._truncated,
        }

    def raise_if_needed(self) -> None:
        """raise 模式：首个 data/internal 错误即抛（DESIGN §10 F-S4-P025-6 裁决）"""
        if self._mode != "raise":
            return
        if not any(self._category_counts.get(c, 0) > 0 for c in RAISE_CATEGORIES):
            return
        first = self._first_raiseable
        assert first is not None  # 计数 > 0 与 first_raiseable 同分支顺序写入，恒成立
        err = RuntimeError(
            f"日级异常（{first.stage}/{first.error_type}，{first.date}）: {first.message}；"
            '需跳过该日请设 day_error_mode="report"'
        )
        err.diagnostics = self.summary()  # type: ignore[attr-defined]
        if sys.version_info >= (3, 11):
            # mypy target=3.10（pyproject L106）：名字经 getattr 取得，避免 name-defined 报错
            raise getattr(builtins, "ExceptionGroup")("日级异常", [err])
        raise err
```

### 4.2 T-1b `core/config.py`（+1 行）

插入位置：L344 `invariant_mode` 之后。

```python
    invariant_mode: Literal["off", "report", "raise"] = "report"  # 不变量校验（P-011 D2）
    day_error_mode: Literal["off", "report", "raise"] = "report"  # 日级异常策略（P-025 D1）
```

### 4.3 T-2 `core/engine_v2.py`（3 处）

**① 导入**（`from core.portfolio import build_optimizer` 之后）：

```python
from core.diagnostics import DayErrorCollector
```

**② `__init__` 末段**（L178 `self._layer_dumper = ...` 之后、L180 `logger.info` 之前）：

```python
        # 日级异常采集（P-025 D3/D4）：off 模式下 record 首行短路，零分配
        self._diagnostics = DayErrorCollector(config.day_error_mode)
```

**③ `run()` catch（L335-L337）**：

```python
            except Exception as e:
                self._diagnostics.record(date, "day_loop", e)
                logger.error(f"处理交易日 {date} 时发生错误: {e}")
                if self.cfg.day_error_mode == "raise":
                    self._diagnostics.raise_if_needed()
                continue
```

> `report`/`off` 仍走 `logger.error` + `continue`（I2 控制流不变）；`raise` 在首个 `data`/`internal` 处抛出，`execution`/`solver` 类不抛（由 `RAISE_CATEGORIES` 保证）。

**④ `_generate_results` 的 `additional_info`**（`"execution_stats"` 之后）：

```python
            "execution_stats": executor.get_execution_stats(),
            "run_diagnostics": self._diagnostics.summary(),
```

> **键恒存在**（含 `off` 模式，值为 `{"mode": "off"}`）——否则 I1 的「键集合差 = `{"run_diagnostics"}`」在 `off` 下不成立（§9 F-S5-P025-3 裁决）。

### 4.4 T-3a `core/execution.py`（2 处）

**① `__init__` 末尾**（L175 `self.trade_log = TradeLog()` 之后）：

```python
        # 日级异常旁路（P-025 D5）：None = 零行为变化
        # 返回值注解为 object 而非 None：绑定的 self._diagnostics.record 返回
        # Optional[DayErrorRecord]，mypy 对 Callable[..., None] 参数位不接受非 None 返回
        # （F-S6-P025-1）；调用侧忽略返回值。
        self._error_sink: Optional[Callable[[pd.Timestamp, str, BaseException], object]] = None
```

**② 新增方法**（放在 `execute_order` 之前）：

```python
    def set_error_sink(
        self, sink: Optional[Callable[[pd.Timestamp, str, BaseException], object]]
    ) -> None:
        """注入执行异常旁路（P-025 D5）；不影响成交语义（I5）"""
        self._error_sink = sink
```

**③ `execute_order` except（L327-L329）**：

```python
        except Exception as e:
            sink = self._error_sink
            if sink is not None:
                sink(date, "execution", e)
            logger.error(f"交易执行失败: {stock} {side.name} {quantity}股, 错误: {e}")
            return False, None
```

> `sink` 由 `DayErrorCollector.record` 承担，其内部已整体 try/except（I3）→ 无需二次包裹；返回 `Optional[DayErrorRecord]` 赋给返回 `None` 的 Callable 符合 PEP 484「返回值可忽略」规则。

### 4.5 T-3b `core/engine_v2.py`（2 处）

**① 优化 catch（L915-L917）**：

```python
        except Exception as e:
            self._diagnostics.record(date, "rebalance", e)
            logger.error(f"组合优化失败: {e}")
            return
```

**② `setup()` 末段 sink 绑定**（L277-L278 的 `LayerDumper` 之后、L280 `elapsed` 之前）：

```python
        # 执行异常旁路（P-025 D5）：仅真实 ExecutionSimulator 有该方法；
        # 注入的 fake executor 保持零改动（零改动面：interfaces.py 不加抽象方法）。
        # getattr 探测写法（F-S6-P025-1）：hasattr 后直接访问会触发 mypy
        # 「IExecutionSimulator has no attribute set_error_sink」
        sink_setter = getattr(self.executor, "set_error_sink", None)
        if sink_setter is not None:
            sink_setter(self._diagnostics.record)
```

### 4.6 T-4 `core/portfolio.py`（D6）

```python
    optimizer_map = {
        "equal_weight": EqualWeightOptimizer,
        "min_variance": MinVarianceOptimizer,
        "mean_variance": MeanVarianceOptimizer,  # 与 CLI / config_v2 词表对齐（P-025 D6）
        "mvo": MeanVarianceOptimizer,
        "risk_parity": RiskParityOptimizer,
    }

    if config.method not in optimizer_map:
        raise ValueError(
            f"未知优化方法: {config.method!r}；合法值: {sorted(optimizer_map)}"
        )
    return optimizer_map[config.method](config)
```

> 两个调用点（`engine.setup()` L240、`factory.create_optimizer()` L167）均在建引擎/setup 期触发，早于 `run()`。

### 4.7 T-5 `core/engine_v2.py`（D7-O2，setup 末段）

插入位置：§4.5 ② 的 sink 绑定之后、`elapsed` 之前。

```python
        # 协方差方法预检（P-025 D7-O2）：短历史下每一次调仓都必然失败
        cov_methods = {"min_variance", "mean_variance", "mvo", "risk_parity"}
        if self.cfg.optimizer.method in cov_methods:
            dm = self.dm
            assert dm is not None
            n_days = len(dm.trade_dates)
            if n_days <= self.cfg.optimizer.cov_lookback:
                raise RuntimeError(
                    f"优化方法 {self.cfg.optimizer.method} 需要协方差估计，"
                    f"但交易日数 {n_days} ≤ cov_lookback {self.cfg.optimizer.cov_lookback}，"
                    "全轮调仓将必然失败"
                )
```

### 4.8 T-1c/T-2b/T-3c/T-4b/T-5b 测试文件

新增 `tests/test_p025_day_error_diagnostics.py`，10 项（对应 DESIGN §4.2 T1-T10）。

| # | 用例 | 关键构造 | 断言 |
|---|------|----------|------|
| T1 | 分类真值表 | `pytest.mark.parametrize` 8 组 | `(category, retryable)` 逐字相等 |
| T2 | 采集器零抛错 | `record(None, "day_loop", ValueError("x"))` + `record(None, "day_loop", object())` | 不抛；非法输入返回 None 或记录，`caplog` 无未捕获异常 |
| T3 | 去重与计数 | 同串 3 次 | `len(samples)==1`；`counts["day_loop"]==3` |
| T4 | 明细上限 | 60 条不同 message | `len(samples)==50`；`truncated is True` |
| T5 | `off` 零记录 | 单日注入日级异常 + `day_error_mode="off"` | `run()` 不抛；`run_diagnostics == {"mode": "off"}` |
| T6 | `report` 模式 | 同 T5 + `"report"` | `degraded is True`；`counts["day_loop"]==1` |
| T7 | `raise` 模式 | 同 T5 + `"raise"` | 断言按 `sys.version_info` **分支**（F-S6-P025-4）：3.11+ `pytest.raises(getattr(builtins, "ExceptionGroup"))`（直接写 `ExceptionGroup` 名字在 3.10 收集期 NameError）；3.10 分支 `pytest.raises(RuntimeError)` |
| T8 | 优化失败计量 | 80 交易日 fake + `OptimizerConfig(method="min_variance", cov_lookback=60)`（真优化器） | `counts["rebalance"] >= 1`；`degraded is True` |
| T9 | setup 预检 | 4 交易日 fake + `method="min_variance"`（`cov_lookback` 默认 60） | `engine.setup()` → `RuntimeError` match=`必然失败` |
| T10 | 方法名真值 | 纯函数 | `build_optimizer(OptimizerConfig(method="mean_variance"))` 是 `MeanVarianceOptimizer`；`method="bogus"` → `ValueError` match=`合法值` |

**注入日级异常的统一手法**（T5-T7）：`engine.setup()` 后**只对第 3 个交易日**抛，其余日透传原方法。

```python
_orig = engine._process_trading_day
_target = engine.dm.trade_dates[2]


def _boom_on_target(date, date_index):
    if date == _target:
        raise RuntimeError(f"injected day error @ {date}")
    _orig(date, date_index)


engine._process_trading_day = _boom_on_target   # → counts["day_loop"] == 1
```

> **必须单日注入**：若每日都抛，tracker 无任何快照，`_generate_results` 会先撞上 P-023 的空快照守卫（`RuntimeError("回测未产生任何组合快照…")`），T5/T6 将无法区分「日级异常」与「零快照」。末日不注入也保证 `_force_liquidation` 正常执行。
>
> `run()` 的 `_generate_results` 需要 `generate_report` 被 patch（仿 `test_rebalance_exits.py` L278-L281），避免图表 I/O。

**T8 的 fake 数据**：`_FakeDataManager` 参数化为 80 日；`_composite_signal` 由 `factor_files=["dummy.pkl"]` + `_FakePipeline` 提供 80 行因子帧 → `date_index >= len(signal_df)` 不触发；前 60 日 `returns_data=None` → `ValueError` → `counts["rebalance"] == 60`（保守断言 `>= 1`）。

---

## 5. 接口签名与回退点

| 接口 | 签名 | 位置 | 回退点 |
|------|------|------|--------|
| `classify_day_error` | `(stage: str, exc: BaseException) -> tuple[str, bool]` | `core/diagnostics.py` | 删除文件即回退（无调用方残留） |
| `DayErrorRecord` | frozen dataclass：`date: str, stage: str, category: str, error_type: str, message: str, retryable: bool` | 同上 | 同上 |
| `DayErrorCollector.__init__` | `(mode: str = "report") -> None` | 同上 | 同上 |
| `.record` | `(date: Any, stage: str, exc: BaseException) -> Optional[DayErrorRecord]` | 同上 | 同上 |
| `.record_failure` | `(date: Any, stage: str, reason: str, category: str = "execution") -> None` | 同上 | 同上（本批无生产调用点） |
| `.summary` | `() -> dict[str, Any]` | 同上 | 同上 |
| `.raise_if_needed` | `() -> None` | 同上 | 同上 |
| `BacktestConfig.day_error_mode` | `Literal["off","report","raise"] = "report"` | `core/config.py` L344 后 | 删 1 行；`self._diagnostics` 需同步删除 |
| `ExecutionSimulator.set_error_sink` | `(sink: Optional[Callable[[pd.Timestamp, str, BaseException], None]]) -> None` | `core/execution.py` | 删方法与 `_error_sink` 字段；`except` 内 3 行回退 |
| `build_optimizer` | 签名不变 `(config: OptimizerConfig) -> BaseOptimizer`；**行为变更**（fail-closed + 别名） | `core/portfolio.py` L435-L442 | 恢复 `.get(..., EqualWeightOptimizer)` 并删 `mean_variance` 键 |
| `BacktestEngineV2._diagnostics` | 新增实例属性 `DayErrorCollector` | `core/engine_v2.py` `__init__` | 删属性 + 3 处调用点 |
| `additional_info["run_diagnostics"]` | `dict[str, Any]`（`mode/degraded/counts/samples/truncated`） | `_generate_results` | 删 1 键（I1 恢复 10 键） |

**回退批次**（对齐 DESIGN §8）：

| 批次 | 提交边界 | 回退命令（示意） | 影响 |
|------|----------|------------------|------|
| B1 | `diagnostics.py` + config 1 行 + T1-T4 | `git checkout <base> -- core/config.py` + `git rm core/diagnostics.py` | 无（未接线） |
| B2 | engine `__init__`/`run()` catch/`run_diagnostics` + T5-T7 | `git checkout <base> -- core/engine_v2.py`（B2 提交后） | 恢复 HEAD 日循环行为 |
| B3 | execution sink + engine 优化 catch/sink/预检 + portfolio | 文件级 checkout 三个文件 | 恢复 HEAD 内层行为与等权降级 |
| B4 | docs | 无需回退 | — |

**运行时退出闸**：`day_error_mode="off"` 可零代码回退到 HEAD 行为（`run_diagnostics` 仅 `{"mode": "off"}` 一个键）。

---

## 6. 低效排除表

| 操作 | 位置 | 频次 | 复杂度 | 结论 |
|------|------|------|--------|------|
| `if self._mode == "off": return None` | `DayErrorCollector.record` 首行 | 每次异常上报 | O(1) | `off` 模式零分配、零字典写入 |
| `record()` 调用 | `run()` 日循环 catch | **仅异常日**（正常回测 0 次） | O(1) | 正常路径零新增指令（try 体内未加代码） |
| `record()` 调用 | `_execute_rebalance` 优化 catch | 仅优化失败日 | O(1) | 同上 |
| `sink is not None` 判空 | `execute_order` except | 仅异常时 | O(1) | 正常成交路径无新增分支（except 体内） |
| `hasattr(executor, "set_error_sink")` | `setup()` | 每次 setup 1 次 | O(1) | 非循环 |
| `optimizer_map` +1 键 / `in` 判定 | `build_optimizer` | 每次构建 1 次 | O(1) | 无 |
| 预检 | `setup()` | 每次 setup 1 次 | O(1) | 非循环，不触碰行情数据 |
| `summary()` | `_generate_results` | 每次 run 1 次 | O(n)，n ≤ 50 | 上限 50 条 × 200 字符（R6 已登记） |
| `str(exc)[:200]` | `record()` | 每次异常 | O(len(msg)) | 截断在切片处，不做正则/序列化 |

**排除项**：无循环内新增 I/O、无 `run()` 热路径（`try` 体）新增语句、无 pandas 全表操作、无日志格式化在非异常路径执行。

---

## 7. fixture 表

| 组件 | 来源 | 用途 / 说明 |
|------|------|------------|
| `_FakeDataManager` | 参数化复制 `tests/test_rebalance_exits.py` L166-L187（`DATES` 扩为 80 日） | T5-T9 无文件 I/O；`returns` / `_prices` / `_factors` 按日数生成 |
| `_FakeUniverse` | 复制 L190-L215 | 全可交易掩码 |
| `_FakePipeline` | 复制 L218-L222 | 原样返回因子帧 |
| `_Top2Optimizer` | 复制 L225-L234 | T5-T7 用确定性优化器，隔离 cvxpy 噪声 |
| `_AlwaysTrigger` | 复制 L237-L239 | 每日触发 |
| `_build_config(tmpdir, **overrides)` | 改造自 L242-L261 | 零成本 + `daily` + `target_count=2`；新增 `day_error_mode` / `optimizer.method` / `cov_lookback` 覆盖参数 |
| `_collector()` | 新增 | 纯单测用 `DayErrorCollector("report")` 实例 |

> 夹具独立复制、不改 `test_rebalance_exits.py`（与 P-023 IMPL §5 同纪律），避免跨批次耦合。

---

## 8. 验证映射

| DESIGN 验证 | 落地 |
|-------------|------|
| V1 / V2 | T1-T4（`pytest tests/test_p025_day_error_diagnostics.py -q`） |
| V3 | T5-T7 |
| V4 | 重跑 `%TEMP%\p025_probe_a2.py`（`report` 模式）：快照 20 / 19 去重日与 HEAD 一致 + `counts.day_loop == 1` |
| V5 | 重跑 `%TEMP%\p025_probe_b2.py`：20 日 + `min_variance` → **setup 抛错**（T9 前置拦截） |
| V6 | T10 |
| V7 | 探针 C 重跑：`counts.execution >= 3`（3 次注入全计量） |
| V8 | `set(additional_info) - HEAD_KEYS == {"run_diagnostics"}`（`report` 与 `off` 双跑） |
| V9 | `pytest tests/test_golden*.py -q` 全绿、无重录 |
| V10 | `mypy --explicit-package-bases --check-untyped-defs core` → 37 files 0；`black --check .` |
| V11 | `pytest -q` ≥ 664 passed |
| V12 | 远端 CI 三 job success |

---

## 9. IMPL 期裁决与发现

| ID | 级 | 发现 | 处置 |
|----|----|------|------|
| **F-S5-P025-1** | P3 | DESIGN D2 的 `data` 判定以 `stage ∈ {settle, pending, next_day, mark}` 为前提，但本批**只在 3 处插桩**（`day_loop` / `rebalance` / `execution`），上述 4 个 stage 不会被实际产生 → 若照抄，`data` 类将永不命中 | 裁决：把 `day_loop` 纳入 data 判定（§4.1 `classify_day_error` 末段），其余 stage 值保留为前向兼容词表并在 `STAGES` 常量注明 |
| **F-S5-P025-2** | P3 | `record_failure`（success=False 计量）在 DESIGN 中已缩范围（§10 F-S4-P025-3），但仍属公开契约 | 裁决：**实现但不接线**（保持契约完整、便于后续批次接入），注释标明「本批无生产调用点」，不为它单独写测试 |
| **F-S5-P025-3** | P3 | DESIGN D1 表中 `off` 语义写「不新增诊断键（`run_diagnostics` 仅含 `{"mode": "off"}`）」——「不新增键」与「仅含」自相矛盾；若真不新增键，I1/V8 的键集合差在 `off` 下为空 | 裁决：**键恒存在**（`off` 时值为 `{"mode": "off"}`），保障 I1 在任何 mode 下成立（§4.3 ④ 已注明） |
| **F-S5-P025-4** | P3 | `IExecutionSimulator` 是 Protocol，若给其加 `set_error_sink`，所有 fake（`test_decoupled_engine.MockExecutionSimulator` 等）立即不满足协议 → 大面积 TypeError | 裁决：**不改 interfaces.py**，sink 走 `hasattr` 探测（§4.5 ②），列入零改动面 |
| **F-S5-P025-5** | P3 | mypy `python_version = "3.10"`：`ExceptionGroup` 直接写名字会报 `name-defined`，而 3.10 运行时也确实没有该内置 | 裁决：`getattr(builtins, "ExceptionGroup")`（§4.1），mypy 视为 Any；运行时按 `sys.version_info` 分支，3.10 走普通 `RuntimeError` |
| 观察-1 | — | DESIGN T8 表述「`counts.rebalance >= 1`；短历史场景由 T9 拦截」——80 日 > `cov_lookback=60` 预检不触发，异常来自前 60 日 `returns_data=None`（实为 **60 次**失败而非 1 次） | T8 断言取保守下界 `>= 1`，Step 9 记录实测值 |
| 观察-2 | — | `mean_variance` 进入 `cov_methods` 预检集合后，若用户显式选它且历史不足，失败点从「等权静默成功」变为「setup 抛错」——这是 D6+D7 叠加的预期效果，但属**双重行为变更** | CHANGELOG 合并为一条说明（`Changed`：`mean_variance` 真正生效 + 短历史 fail-fast） |

---

## 10. Step 6 开放点（已全部关闭）

1. ~~classify_day_error 是否覆盖 D2 全部「典型来源」~~ → **已核对**：缺列/缺键（`KeyError/FileNotFoundError`）、日期不齐（`ValueError`，`day_loop` 下归 `data`）、协方差奇异（`LinAlgError`/类名匹配）、回看不足（`ValueError` 且 `rebalance` 归 `solver`）；「整手取整为 0」是 success=False 路径，F-S4-P025-3 已裁决本批不计量。
2. ~~counts 键是否只含阶段名~~ → **已核对**：实现按 `rec.stage` 累加，`record_failure` 未接线不产生污染。
3. ~~T7 在 3.10 的期望~~ → **已裁决回写**（F-S6-P025-4，见 §4.8 T7 行）。

---

## 11. Step 6 Review（实施文档幻觉抑制）

> **执行方式**：IMPL 完稿后逐条核对设计对齐、版本存在性、签名可实现（RULE-1 时序独立；RULE-4 单 Agent）。
> **核对基线**：HEAD `43cfa36`（IMPL 提交时点），全部代码锚点实查取证。

### 11.1 检查表

| # | 检查项 | 结论 |
|---|--------|------|
| 1 | 任务与设计一一对应 | ✅ T-1←D1/D2/D3、T-2←D4、T-3←D5、T-4←D6、T-5←D7、T-6←DESIGN §4.1 B4 行；无设计外任务 |
| 2 | DESIGN ↔ IMPL 对齐 | ✅ I1→§4.3④（键恒存在）、I2→§4.3③（logger+continue 保留）、I3→§4.1（record 整体 try/except）、I4→off 首行短路、I5→sink 单向旁路、I6/I7→Step 9 验证；V1-V12 映射见 §8 |
| 3 | 依赖版本真实存在 | ✅ 零新增三方依赖：numpy 既有；标准库 `builtins/sys/dataclasses/typing/logging` |
| 4 | stdlib API 下限 | ✅ `getattr(builtins, "ExceptionGroup")` 仅在 `sys.version_info >= (3, 11)` 分支内触达（3.10 运行时无 AttributeError）；`frozenset` / `dataclass(frozen=True)` / `asdict` 全版本；mypy `python_version=3.10`（pyproject L106 实证）下无 name-defined（getattr 返回 Any） |
| 5 | 签名可实现 | ✅ `set_error_sink` 落在具体类而非 Protocol（F-S5-P025-4）；`Callable/Optional` 在 execution.py L14 已导入（实查，无需新增导入行）；sink 注解 object 化（F-S6-P025-1 回写后闭环） |
| 6 | 低效操作排除 | ✅ §6 表 9 项非空；正常路径（`run()` try 体 / `execute_order` 成交路径）零新增指令 |
| 7 | 回退点 | ✅ §5 接口表 12 项签名+回退齐备；B1-B4 批次回退命令 + `day_error_mode="off"` 运行时退出闸 |
| 8 | 红态可观测 | ✅ T5-T7 红 = `run_diagnostics` 键不存在（KeyError）；T8 红 = counts 键不存在；T9 红 = `DID NOT RAISE`；T10 红 = `is` 断言失败 + 缺 `ValueError` |
| 9 | 导入副作用 | ✅ `diagnostics.py` 零 `core.*` 依赖（仅 numpy + stdlib）→ 无循环依赖；engine_v2 仅新增 1 条 import |
| 10 | 行号/引用核对 | ✅ L344 invariant_mode / L335-L337 run catch / L915-L917 优化 catch / L1183 execution_stats / execution L175-L177 / L327-L329 / L277-L278 dumper / L240 build_optimizer / pyproject L106 / tests.yml L46 / fixture 行号（test_rebalance_exits L166-L187、L190-L215、L218-L222、L225-L234、L237-L239、L242-L261、L278-L281）全部实查命中 |
| 11 | cvxpy 类名匹配（不 import 仅按 `__name__`） | ✅ `SolverError` / `DCPError` 为 cvxpy.error 公开异常名；匹配顺序 LinAlgError→类名→ValueError 无继承冲突（二者均非 ValueError 子类） |

### 11.2 发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S6-P025-1** | **P2** | sink 注解 `Callable[[...], None]` 与绑定的 `record` 返回 `Optional[DayErrorRecord]` 在 mypy 下 incompatible（返回类型非 None 不被 None 参数位接受）→ V10/CI 门禁必红；且 `hasattr` 探测后直接 `self.executor.set_error_sink(...)` 会报 `IExecutionSimulator has no attribute set_error_sink`（静态类型为 Protocol，hasattr 不收窄） | ✅ 已回写 §4.4①②（注解改 `object`）+ §4.5②（`getattr(executor, "set_error_sink", None)` 探测写法） |
| **F-S6-P025-2** | P3 | `raise_if_needed` / `degraded` 判定基于截断后的 `_records`（≤50 条）：≥50 条 execution 类之后出现的 internal 会漏抛/漏标（raise 语义失效但不违反 I3） | ✅ 已回写 §4.1（新增 `_category_counts` 计数器 + `_first_raiseable` 样本引用，判定改基于计数） |
| **F-S6-P025-3** | P3 | DESIGN D4 代码形态缺现状 `logger.error` 行（与 DESIGN §4.3 文案约定「现状 error 保持不变」矛盾）；IMPL §4.3③ 初稿已正确保留 | ✅ 已回写 DESIGN D4 代码块补 `logger.error`（IMPL 方向正确，DESIGN 对齐） |
| **F-S6-P025-4** | P3 | T7 若直接写 `pytest.raises(ExceptionGroup)`，在 CI 3.10 job 收集期即 NameError（3.10 无该内置名） | ✅ 已回写 §4.8 T7 行（按 `sys.version_info` 分支断言）；关闭 §10 开放点 3 |
| 观察-1 | — | T8 fixture 若沿用原版全零 returns，`_ledoit_wolf_shrinkage` 的 `kappa=(pi-rho)/gamma` 在 gamma=0 时 ZeroDivisionError（混入 internal 类失败记录）；T8 断言（`>=1` + degraded）不受影响 | 落码时 fixture 用非全零收益，避免噪声 |
| 观察-2 | — | `record_failure` 无测试覆盖 | 维持 F-S5-P025-2 裁决（实现不接线、不单独测试） |
| 观察-3 | — | execution.py 导入行零改动（`Callable/Optional` 已在 L14）——IMPL 未单列导入 diff，实查确认无需改动 | 登记（对照 P-023 F-S6-P023-1 同类项） |

### 11.3 结论

**通过**——0 P1 / 1 P2（已回写）/ 3 P3（全部回写）/ 3 观察（1 项落码时采纳、2 项登记）；§10 开放点 3 项全部关闭。可进入 Step 7 验收清单（CHECKLIST）。
