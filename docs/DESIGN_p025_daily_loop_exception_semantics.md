# DESIGN：P-025 日循环异常分类与 retry 语义

> **批次**: P-025 · **T1**（`core/` 行为契约 + 结果字典新增键）
> **上游**: [RESEARCH_p025](RESEARCH_p025_daily_loop_exception_semantics.md)（P1-P14 / E1-E4 / §10 Step 2 Review）
> **下游**: IMPL_p025 → CHECKLIST_p025
> **代码证据时点**: HEAD `3e4b896`（2026-11-12，工作区干净）
> **状态**: Step 3 设计完稿（待 Step 4 独立 Review）

---

## 1. 决策总览

| ID | 决策项 | 决定 | 对应 |
|----|--------|------|------|
| **D1** | 错误策略开关 | 新增 `day_error_mode: Literal["off","report","raise"] = "report"`，与 `invariant_mode` 同形（config L345 之后） | P12 / M-A |
| **D2** | 异常分类 | 四类：`data` / `execution` / `solver` / `internal`；分类由 `(stage, exception_type)` 双键决定，**不按消息文本匹配** | P2-P4 / E1 |
| **D3** | 采集器落位 | 新增 **`core/diagnostics.py`** 独立模块（不放入 engine_v2）——供 `execution.py` 复用，避免反向依赖 | P4 / P13 |
| **D4** | 日循环改造 | `run()` 的 catch 改为 `classify → record → 按 mode 决定继续/抛出`；`report`/`off` 保持 `continue`，`raise` 抛聚合异常 | P2 / E4 |
| **D5** | 内层接入 | 优化失败（engine L915）与执行失败（execution L327）接入同一采集器；executor 以**可选 sink** 注入，默认 `None` 零行为变化 | P3 / P4 |
| **D6** | 优化器方法名去静默 | `build_optimizer` 补 `"mean_variance"` 别名；**未知 method 不再静默降级等权**，改抛 `ValueError`（fail-closed） | **F-D3-P025-1（新发现）** |
| **D7** | 边界裁决 | O1：末日重复快照**不动**（golden 已编码）；O2：`setup()` 增 `cov_lookback` 预检（仅依赖协方差的方法） | §10.3 O1/O2 |

---

## 2. 调研结论 → 设计映射

| 调研结论 | 设计决策 | 引用 |
|----------|----------|------|
| 三层静默：日循环 / 优化 / 执行 | D2 分类 + D4/D5 三处统一采集 | P2/P3/P4 |
| 探针 B2：`min_variance` + 短历史 → sharpe 0.0 假成功 | D5 计量 + D7 前置预检 | P7 |
| `invariant_mode` 三态先例已在本仓服役 | D1 完全同形复用 | P12 |
| `EventLog` 零生产接线 | D3 不引入 EventLog，走独立轻量采集器 | P13 |
| `additional_info` 无诊断位 | D4 新增 `run_diagnostics`（只增键） | P11 |
| 末日重复快照在正常回测同样出现 | D7-O1 不动（改则 golden 全破） | 观察 O1 |
| 方法名分派 `mean_variance` → 等权（**探针实测**） | D6 词表对齐 + fail-closed | F-D3-P025-1 |

**F-D3-P025-1（DESIGN 期新发现，P2）**：`build_optimizer` 的 `optimizer_map` 只有 `equal_weight / min_variance / mvo / risk_parity`（[portfolio.py L435-L442](../core/portfolio.py#L435-L442)），而 CLI 提供 `--optimizer mean_variance`（[cli.py L295](../cli.py#L295)）、`config_v2` 的 Literal 也含该值 → 用户选 `mean_variance` 得到的是**等权**。探针实测（`%TEMP%\p025_probe_d1.py`）：

```
分派表直读：mean_variance -> EqualWeightOptimizer；bogus -> EqualWeightOptimizer
端到端（80 日）：equal_weight 与 mean_variance 读数完全相同（64 笔 / sharpe −1.4611384945695667），mvo 才真正生效（3 笔 / sharpe 1.4918）
```

**并订正 RESEARCH P7 的对照组**：原写「同数据 `mean_variance` 成功 13 笔（对照组），说明失败来自方法分支而非数据不足」——该 13 笔实为**等权降级**读数，不是均值方差成功。B2 的 P1 结论不变（`min_variance` 确为静默全失败），但对照组命名错误，已在 RESEARCH P7 追加订正注。

---

## 3. 决策详述

### D1 `day_error_mode` 三态开关

**位置**：`core/config.py` `BacktestConfig`，紧跟 `invariant_mode`（L344）之后。

```python
    invariant_mode: Literal["off", "report", "raise"] = "report"  # 不变量校验（P-011 D2）
    day_error_mode: Literal["off", "report", "raise"] = "report"  # 日级异常策略（P-025 D1）
```

| 取值 | 语义 |
|------|------|
| `off` | 完全旧行为：不采集、不新增诊断键（`run_diagnostics` 仅含 `{"mode": "off"}`） |
| `report` | **默认**：采集并写入 `run_diagnostics`，控制流与现状一致（`continue`） |
| `raise` | 采集后**抛出**：3.11+ 用 `ExceptionGroup` 聚合全部 internal/data 错误；3.10 抛首个并附诊断字典到异常属性。`execution`/`solver` 类**不参与抛出**（业务可恢复） |

**理由**：与 `invariant_mode` 同形（P12）→ 消费方零学习成本；默认 `report` 保证 654 测试与 golden 零回归；`raise` 供 CI/pytest 严格模式。

**被拒方案**：布尔开关 `abort_on_day_error`（无法表达「只记录」）；环境变量控制（不可在 `BacktestConfig` 快照/序列化中体现）。

### D2 异常四分类

**分类键**：`(stage, exception_type)` 双键，**不看消息文本**（消息会随语言/版本漂移）。

| 类别 | 判定 | 典型来源 | 可重试 |
|------|------|----------|--------|
| `data` | `KeyError` / `FileNotFoundError` / `ValueError`（数据形态）且 stage ∈ {settle, pending, next_day, mark} | 缺价格列、缺 universe 行、日期不齐 | 是（下一交易日可能恢复） |
| `execution` | 成交失败（`success=False`）或 `ExecutionError` | 资金不足、整手取整为 0、掩码限制 | 是（订单留队） |
| `solver` | `np.linalg.LinAlgError` / cvxpy `SolverError` / `ValueError("…需要收益率数据…")` 且 stage == rebalance | 协方差奇异、回看不足 | 否（同输入必再失败） |
| `internal` | `TypeError` / `AttributeError` / `AssertionError` / `NameError` / `IndexError` / 其余 `Exception` | 代码缺陷 | 否 |

**落位**：`core/diagnostics.py` 的 `classify_day_error(stage, exc) -> tuple[str, bool]`（类别, 可重试）。

**理由**：`retryable` 是 D5/后续 retry 语义的唯一依据；E2「only transient failures」与 E3「failures masked by retries」要求区分确定性与瞬时。

### D3 `core/diagnostics.py` 采集器

**为什么新建模块**：`execution.py` 需要上报成交异常，但 `execution.py` 不能 import `engine_v2`（反向依赖 + 循环）。独立模块给两侧共用，且可单测（无引擎依赖）。

**契约**：

```python
@dataclass(frozen=True)
class DayErrorRecord:
    date: str            # ISO 日期
    stage: str           # settle|pending|next_day|rebalance|mark|risk|dump|finalize
    category: str        # data|execution|solver|internal
    error_type: str      # 异常类名
    message: str         # 截断至 200 字符
    retryable: bool

class DayErrorCollector:
    def record(self, date, stage, exc) -> DayErrorRecord | None: ...  # 内部 try/except 兜底
    def record_failure(self, date, stage, reason: str, category="execution") -> None: ...
    def summary(self) -> dict[str, Any]: ...   # counts / samples / truncated / degraded
    def raise_if_needed(self) -> None: ...     # 仅 raise 模式调用
```

**约束**：`record` **不得抛错**（R4 缓解）——内部 `try/except Exception` 后降级为 `logger.error`；去重键 `(date, stage, category, error_type, message)`，同名合并计次；明细上限 **50 条**，超出置 `truncated=True`。

### D4 日循环改造

**位置**：`run()` L326-L337。

```python
        for i, date in enumerate(self.dm.trade_dates):
            try:
                self._process_trading_day(date, i)
                if i == last_date_index:
                    self._snapshot_unclosed_positions()
                    self._force_liquidation(date, i)
                    self._refresh_last_nav(date)
            except Exception as e:
                self._diagnostics.record(date, "day_loop", e)
                if self.cfg.day_error_mode == "raise":
                    self._diagnostics.raise_if_needed()
                continue
```

**要点**：`off` 模式下 `record` 立即返回并不分配记录（零开销）；`raise` 分支到达时若已聚合多个 internal 错误则一次性抛出（E1）。

**`run_diagnostics` 结构**（写入 `additional_info`，只增不改 P11 的 10 键）：

```python
"run_diagnostics": {
    "mode": "report",
    "degraded": True,          # 存在 internal/data/solver 类错误
    "counts": {"day_loop": 1, "rebalance": 4, "execution": 3},
    "samples": [ {...DayErrorRecord...} ],   # ≤50
    "truncated": False,
}
```

### D5 内层接入（优化 / 执行）

**优化**（engine L898-L917）：`except Exception as e:` 分支内追加 `self._diagnostics.record(date, "rebalance", e)`，随后保持 `return`（当日不调仓）。

**执行**（execution L327-L329）：`ExecutionSimulator` 增可选注入点：

```python
    def set_error_sink(self, sink: Callable[[pd.Timestamp, str, BaseException], None]) -> None:
        self._error_sink = sink      # 默认 None → 零行为变化
```

`except` 分支先调 sink（若设）再 `return False, None`。`engine.setup()` 末段把 `self._diagnostics.record` 绑为 sink。

**理由**：不改方法签名（`execute_order` 有 **4 处生产调用**（engine_v2 L533 / L782 / L1127 + execution L392 内部）与 **9 个测试文件共 28 处**调用）；sink 是单向旁路，异常时也不改变成交语义。

### D6 优化器方法名去静默（F-D3-P025-1）

**位置**：[portfolio.py L435-L442](../core/portfolio.py#L435-L442)。

```python
    optimizer_map = {
        "equal_weight": EqualWeightOptimizer,
        "min_variance": MinVarianceOptimizer,
        "mean_variance": MeanVarianceOptimizer,   # 新增：与 CLI / config_v2 词表对齐
        "mvo": MeanVarianceOptimizer,
        "risk_parity": RiskParityOptimizer,
    }
    if config.method not in optimizer_map:
        raise ValueError(
            f"未知优化方法: {config.method!r}；合法值: {sorted(optimizer_map)}"
        )
    return optimizer_map[config.method](config)
```

**为什么纳入本批**：属「静默降级导致假结果」同族缺陷（用户选 `mean_variance` 得到等权却不被告知）；且它是 RESEARCH P7 对照组的成因，不修则本批的诊断会记录「一切正常」而实际上优化器方法根本没生效。

**风险控制**：`build_optimizer` 在 `engine.setup()` L240 调用 → 未知 method 在 **setup 期**即失败（早于 run）；`equal_weight` 仍为 config 默认值，golden 与 654 测试不受影响（实测无测试传 `mean_variance`）。

### D7 边界裁决

**O1（末日重复快照）——不动**：探针 A3 无注入时同样 21 快照 / 20 去重日；`_force_liquidation(..., update_market_values=True)` 在末日再次 `update_market_values` → 重复快照。golden G1-G7 已编码该形态，改动将使 7 条基线全部重录。本批只在 DESIGN/IMPL 注明，治理另立未决项（U-P025-6）。

**O2（setup 预检）——纳入**：

```python
        # setup() 末段，trade_dates 已就绪
        cov_methods = {"min_variance", "mean_variance", "mvo", "risk_parity"}
        if self.cfg.optimizer.method in cov_methods:
            n_days = len(self.dm.trade_dates)
            if n_days <= self.cfg.optimizer.cov_lookback:
                raise RuntimeError(
                    f"优化方法 {self.cfg.optimizer.method} 需要协方差，但交易日数 {n_days} "
                    f"≤ cov_lookback {self.cfg.optimizer.cov_lookback}，全轮调仓将必然失败"
                )
```

**理由**：`_execute_rebalance` L899 的 `date_index >= cov_lookback` 决定 `returns_data` 是否为 `None`；`len(trade_dates)-1 < cov_lookback` 时**每一次**调仓都必然抛 `ValueError`（P7 的 P1 假成功）。预检把它前移到 setup，与 P-023「入口 fail-fast」同型。

**被拒方案**：运行期首次失败即抛（仍在循环内，用户已等完前 N 天）；自动降级等权（U-P025-4 已裁决不做——静默降级正是本批要消灭的）。

---

## 4. 实现规格

### 4.1 变更面

| 文件 | 批次 | 变更 |
|------|------|------|
| `core/diagnostics.py` | B1 | **新增**：`DayErrorRecord` / `classify_day_error` / `DayErrorCollector`（≈110 行） |
| `core/config.py` | B1 | +1 行 `day_error_mode` |
| `core/engine_v2.py` | B2/B3 | setup 建采集器 + sink 绑定；`run()` catch 改造；优化 catch 接入；setup 预检（D7-O2）；`run_diagnostics` 入 `additional_info` |
| `core/execution.py` | B3 | +`set_error_sink` + `except` 内调用（≈8 行） |
| `core/portfolio.py` | B3 | `optimizer_map` +1 键 + 未知 method fail-closed（≈6 行） |
| `tests/test_p025_day_error_diagnostics.py` | B1-B3 | **新增** ≈ 10 项 |
| `README.md` / `docs/ARCHITECTURE.md` | B4 | 结果字段说明 + 诊断节 |

### 4.2 测试规格（10 项）

| # | 用例 | 断言 |
|---|------|------|
| T1 | `classify_day_error` 四类映射 | 参数化 8 组 `(stage, exc)` → `(category, retryable)` 逐字相等 |
| T2 | 采集器零抛错 | 传入非法 `date`（None）→ 不抛，返回 `None`，`logger.error` 记录 1 条 |
| T3 | 去重与计数 | 同 `(date, stage, type, message)` 记 3 次 → `samples` 1 条、`counts` 计 3 |
| T4 | 明细上限 | 记 60 条不同错误 → `len(samples) == 50` 且 `truncated is True` |
| T5 | `off` 模式零记录 | 注入日级异常 + `day_error_mode="off"` → 无诊断键内容、行为与现状一致 |
| T6 | `report` 模式 | 注入日级异常 → 无上抛；`run_diagnostics.degraded is True`、`counts.day_loop == 1` |
| T7 | `raise` 模式 | 同上 + `mode="raise"` → 抛 `ExceptionGroup`（3.11+）/ `RuntimeError`（3.10），异常携带诊断 |
| T8 | 优化失败计量 | `min_variance` + 80 日 + `cov_lookback=60` 正常跑 → `counts.rebalance ≥ 1`；短历史场景由 T9 拦截 |
| T9 | setup 预检（D7-O2） | 20 日 + `cov_lookback=60` + `min_variance` → `setup()` 抛 `RuntimeError`，消息含「必然失败」 |
| T10 | 方法名真值（D6） | `build_optimizer(OptimizerConfig(method="mean_variance"))` → `MeanVarianceOptimizer`；`method="bogus"` → `ValueError` 且消息列出合法值 |

### 4.3 文案约定

- 错误消息中文，含**日期 + 阶段 + 建议**（如「该日已跳过，回测继续；如需中断请设 `day_error_mode=\"raise\"`」）。
- `run_diagnostics.counts` 的键固定为阶段名，不拼错误消息。
- 日志级别：`internal` → `logger.error`；`data`/`execution`/`solver` → `logger.warning`（现状 `error` 保持不变，仅分类附加）。

---

## 5. 不变式

| ID | 不变式 | 校验方式 |
|----|--------|----------|
| **I1** | `additional_info` 既有 10 键名与语义不变，仅新增 `run_diagnostics` | 键集合差 = `{"run_diagnostics"}` |
| **I2** | `report` / `off` 模式下控制流与 HEAD 完全一致（仍 `continue`） | 探针 A2 快照数/日期序列与 HEAD 逐字节相同 |
| **I3** | 采集器任何路径不抛异常 | T2 + 代码审查（`record` 内 try/except） |
| **I4** | `off` 模式零新开销（不构造 record、不写键内容） | 计时探针 ≤2% 差异；`run_diagnostics == {"mode": "off"}` |
| **I5** | 成交语义不变：`execute_order` 签名、返回值、异常处理路径不变 | AST 比较 + 4 处调用点零改动 |
| **I6** | golden G1-G7 数值不变 | Step 9 逐字节比对 |
| **I7** | 末日重复快照形态保留 | 快照数 = 22（末日重复）与 HEAD 相同 |

---

## 6. 验证契约

| ID | 验证项 | 命令/证据出口 | 对应 |
|----|--------|---------------|------|
| V1 | 分类表 8 组参数化 | `pytest tests/test_p025_*.py -q` | D2/I1 |
| V2 | 采集器零抛错 + 去重 + 上限 | 同上（T2-T4） | D3/I3 |
| V3 | 三态行为（off/report/raise） | T5-T7 | D1/D4 |
| V4 | 重跑探针 A/A2（`report` 模式） | 快照 20 条 / 19 去重日 与 HEAD **逐字节一致**；`counts.day_loop == 1` | I2 |
| V5 | 重跑探针 B/B2 | B：`counts.rebalance == 4` + `degraded`；B2 由 T9 前置拦截（setup 抛错） | D5/D7 |
| V6 | 优化器方法名真值 | T10 | D6 |
| V7 | 执行失败计量 | 探针 C + `counts.execution ≥ 3` | D5 |
| V8 | 结果键契约 | `set(additional_info) - HEAD_KEYS == {"run_diagnostics"}` | I1 |
| V9 | golden G1-G7 | `pytest tests/test_golden*.py -q` 全绿、无重录 | I6 |
| V10 | 静态门禁 | `mypy --explicit-package-bases --check-untyped-defs core` → 0；`black --check .` 不变 | — |
| V11 | 全量回归 | `pytest -q` ≥ **664 passed**（654 + 10 新） | — |
| V12 | 远端 CI | 三 job success | — |

---

## 7. 风险登记

| ID | 风险 | 级 | 缓解 |
|----|------|----|------|
| **R1** | D6 fail-closed 打破外部用户传任意字符串的习惯 | P2 | `equal_weight` 仍为默认；消息列出全部合法值；CHANGELOG 记录行为变更 |
| **R2** | D7-O2 预检误伤「短历史 + 等权」用户 | P3 | 仅对 4 个依赖协方差的方法生效；等权不受影响 |
| **R3** | 采集器成为新故障点 | P2 | I3 零抛错契约 + T2 |
| **R4** | `raise` 模式破坏 654 既有测试 | P2 | 默认 `report`；全量回归中 `raise` 仅在 T7 显式构造 |
| **R5** | 新增第 36→37 个 core 模块影响 ARCHITECTURE 计数 | P3 | B4 同步订正 ARCHITECTURE「核心模块」行 |
| **R6** | `run_diagnostics` 体积（50 条 × 200 字符）写入结果字典 | P3 | 上限 50 + 截断标记；`off` 零开销 |
| **R7** | golden 因 sink 注入产生时序变化 | P2 | sink 仅在异常分支调用，正常路径零调用 |
| **R8** | Python 3.10 无 `ExceptionGroup` | P3 | `raise` 分支按 `sys.version_info` 分支实现（U-P025-5） |

---

## 8. 回退点

| 批次 | 回退方式 | 影响 |
|------|----------|------|
| B1 | 删除 `core/diagnostics.py` + 回退 config 1 行 | 无（未接线） |
| B2 | 回退 `run()` catch 与 `run_diagnostics` | 恢复 HEAD 行为 |
| B3 | 回退 sink / 预检 / `optimizer_map` | 恢复 HEAD 行为 |
| B4 | 仅文档，无需回退 | — |

**运行时退出闸**：`day_error_mode="off"` 可在不修改代码的情况下恢复 HEAD 的完全旧行为。

---

## 9. 设计期发现

| ID | 级 | 发现 | 处置 |
|----|----|------|------|
| **F-D3-P025-1** | **P2** | `build_optimizer` 用 `mvo` 作均值方差键，而 CLI 与 `config_v2` 用 `mean_variance` → 用户选 `mean_variance` **静默得到等权**（探针实测：与 `equal_weight` 读数完全相同）；任意未知字符串同样静默降级 | 纳入本批 **D6**（别名 + fail-closed）；RESEARCH P7 对照组归因已订正 |
| F-D3-P025-2 | P3 | RESEARCH §4 选型理由②「同数据 `mean_variance` 成功 13 笔」失准（实为等权降级） | 已在 RESEARCH P7 追加订正注，选型结论不变 |
| 观察 | — | O1 末日重复快照成因确认：`_force_liquidation(update_market_values=True)` 在末日二次 `update_market_values` | D7-O1 不动；登记 U-P025-6 |
