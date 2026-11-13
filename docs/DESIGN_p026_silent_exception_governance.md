# DESIGN：P-026 静默失败治理第二批（core/ 剩余 except 分级显形）

> **批次**: P-026 · **T1**（`core/` 行为契约变更 + 结果/返回值新增可观测字段）
> **上游**: [RESEARCH_p026](RESEARCH_p026_silent_exception_governance.md)（Step 2 独立 Review pass，§10）
> **下游**: IMPL_p026 → CHECKLIST_p026
> **代码证据时点**: HEAD `9c332cc`（2026-11-13，工作区干净）
> **状态**: Step 3 设计完稿 + **Step 4 独立 Review 通过**（复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；0 P1/P2，4 P3 回写订正 + 2 观察，见 §11）+ **Step 5 IMPL 已实施**（见 [IMPL_p026](IMPL_p026_silent_exception_governance.md)；实测 687 passed / mypy 37 files 0 / black 116）+ **Step 6 IMPL 复审 pass** + **Step 7 CHECKLIST 完稿**（45 项零预填）

---

## 1. 决策总览

| ID | 决策 | 落点 | 批 | 依据 |
|----|------|------|----|------|
| **D1** | `FactorPipeline` 增 `set_error_sink` + 双原因跳过计数；两处 except 补日志并上报 | `factor.py` / `engine_v2.py` / `diagnostics.py` | B1 | RESEARCH §5 #4/#5 |
| **D2** | `EventLogPlugin._log` debug→warning + `_error_count`；`GuardPlugin` 异常独立计数（**保持 fail-open**） | `engine_plugins.py` | B2 | §5 #12/#13 |
| **D3** | `ContagionNetwork.degraded_components` 标记两处静默兜底；Granger 返回值加 `failed` | `global_contagion.py` | B3 | §5 #14/#15/#16 |
| **D4** | `EventLog.stats()` 三计数器（read / write / skipped_lines），**不改** `read/query` 返回值 | `event_log.py` | B4 | §5 #6/#7 + U-P026-6 |
| **D5** | `WalkForwardResult.agent_period_failures` + 引擎实例级计数（每次 `run()` 重置） | `walk_forward.py` / `walk_forward_engine.py` | B4 | §5 #17 + R7 |
| **D6** | K 类 8 处与排除 4 处**零改动**；不引入 fail-fast、不建全局注册表 | — | 全批 | §5 / §4 M-A |
| **D7** | 计数生命周期：因子 / 插件 / EventLog = 实例累计；WalkForward = 每 `run()` 重置 | 各模块 | 全批 | R7 |
| **D8** | 日志文案统一「位置 + 后果」中文短句，warning 级不带 `exc_info` | 各模块 | 全批 | 4.3 |

**变更面实为 8 个 core 文件 + 1 个测试文件**（RESEARCH 成本行的「6 文件」只计了 D 类目标文件，漏了 sink 接线 `engine_v2.py` 与阶段词表 `diagnostics.py`）→ 设计期发现 **F-D-P026-1**。

---

## 2. 调研结论 → 设计映射

| RESEARCH | 设计落点 | 说明 |
|----------|----------|------|
| §4 选型 M-A（逐点三态 + 分级显形） | D1-D5 | 每批只增计数/字段，正常路径零控制流变更 |
| §4 复用 P-025 sink 注入（D5 先例） | D1 | `getattr(obj, "set_error_sink", None)` 探测，fake 对象零破坏 |
| §5 #4/#5（factor 零日志 / warning 无计数） | D1 | 两处统一走 `_report_error`，按 reason 分桶计数 |
| §5 #12/#13（debug 不可见 / fail-open 无计量） | D2 | 级别升级 + 独立 `_error_count`，**override 语义不变** |
| §5 #14/#15/#16（contagion 零日志 / 语义混淆） | D3 | 网络对象自带 `degraded_components`；Granger 加 `failed` |
| §5 #6/#7（读失败不可辨 / 写失败丢盘） | D4 | 新增 `stats()`（EventLog 当前无此方法，F-S2-P026-1） |
| §5 #17（窗口期间失真无字段） | D5 | `WalkForwardResult` 新增计数 |
| U-P026-6（窄类型跳坏行） | D4 | 采纳：`skipped_lines` 覆盖 `read` + `_recover_state` 两处 |
| §6 R1-R7 | §7 风险登记 | 逐条给缓解与验证点 |
| §8 B1-B5 | §4.1 变更面 + §8 回退点 | B1-B4 代码批，B5 文档与回归 |

---

## 3. 决策详述

### D1 因子链路显形（B1）

**D1.1 `FactorPipeline` 新增旁路接口**（`core/factor.py`）

```python
# __init__ 追加
self._error_sink: Optional[Callable[[Any, str, BaseException], None]] = None
self._neutralize_skip_counts: dict[str, int] = {"degenerate_columns": 0, "regression": 0}

def set_error_sink(self, sink: Callable[[Any, str, BaseException], None]) -> None:
    """注入异常旁路（P-026 D1）；接口与 DayErrorCollector.record 同形"""
    self._error_sink = sink

@property
def neutralize_skip_counts(self) -> dict[str, int]:
    """中性化跳过计数快照（degenerate_columns / regression）"""
    return dict(self._neutralize_skip_counts)

def _report_error(self, date: Any, exc: BaseException) -> None:
    """上报到旁路；本方法不得抛错（I2）；签名经 Step 4 复审订正（F-S4-P026-1）"""
    if self._error_sink is None:
        return
    try:
        self._error_sink(date, "factor", exc)
    except Exception:
        logger.debug("因子异常旁路调用失败（已忽略）")
```

**D1.2 两处 except 改造**

L341-L345（去常数列）：

```python
except Exception as e:
    logger.warning(f"日期 {date} 去常数列失败，跳过中性化: {e}")
    self._neutralize_skip_counts["degenerate_columns"] += 1
    self._report_error(date, e)
    continue
```

L366-L368（回归中性化）：保留既有 warning 文案前缀「日期 {date} 中性化失败」，追加计数与上报：

```python
except Exception as e:
    logger.warning(f"日期 {date} 中性化失败: {e}")
    self._neutralize_skip_counts["regression"] += 1
    self._report_error(date, e)
    continue
```

复审订正 **F-S4-P026-1**（P3）：初稿 `_report_error(date, reason, exc)` 的 `reason` 为死参数——分桶计数由调用方直接完成，sink 调用与 `DayErrorCollector.record` 同形只收 `(date, stage, exc)`、stage 硬编码 `"factor"`，`reason` 无消费点。签名已修订为 `_report_error(date, exc)`；分类信息**不进入** `DayErrorRecord`（保持 P-025 D2「分类只看 stage + 异常类型」不变式）。

**D1.3 阶段词表扩展**（`core/diagnostics.py`）

- `STAGES` 元组追加 `"factor"`（该常量无运行时使用，仅作契约词表 —— 与 P-025 F-S10-P025-3 同性质）。
- `classify_day_error` 在 `rebalance` 分支之后、通用 `isinstance` 判定之前插入：

```python
if stage == "factor":
    # 因子预处理（setup 期一次性完成，无逐日重试语义）
    if isinstance(exc, np.linalg.LinAlgError):
        return "solver", False
    if isinstance(exc, (KeyError, FileNotFoundError, ValueError)):
        return "data", False
    return "internal", False
```

**raise 模式语义（复审订正 F-S4-P026-2）**：factor 分支的 `data`/`internal` 类别属于 `RAISE_CATEGORIES`——`day_error_mode="raise"` 时，setup 期因子异常将在首个交易日 `raise_if_needed()`（engine_v2 L364，全仓唯一调用点）抛出（记录 date 为因子日期）。属预期语义扩散（用户显式 opt-in fail-fast）；off/report 模式不受影响。

**D1.4 接线时点（关键）**（`core/engine_v2.py` L228-L237 之间）

```python
# 3.5 因子异常旁路（P-026 D1）：仅真实 FactorPipeline 有该方法
factor_sink_setter = getattr(self.pipeline, "set_error_sink", None)
if factor_sink_setter is not None:
    factor_sink_setter(self._diagnostics.record)

self._precompute_factors()   # 既有 L237
```

**必须位于 `_precompute_factors()` 之前**——中性化发生在 `process()` 内，若在 L237 之后注入，setup 期的因子错误全部漏采（设计期发现 F-D-P026-2）。

### D2 插件层计量（B2）

**D2.1 `EventLogPlugin`**（`core/engine_plugins.py`）

- `__init__` 追加 `self._error_count = 0`。
- `_log` 的 except：`logger.debug` → `logger.warning`，并 `self._error_count += 1`。
- 新增 `get_stats()`：`{"enabled": self._enabled, "error_count": self._error_count}`。

依据 A3：root logger 默认 WARNING，原 `debug` 在默认配置下**完全不可见**。

**D2.2 `GuardPlugin`**

- `__init__` 追加 `self._error_count = 0`。
- L235-L237：

```python
except Exception as e:
    self._error_count += 1
    logger.warning(f"Guard 检查异常（已放行）: {e}")
    return True, []   # 保持 fail-open：风控可用性优先
```

- `get_stats()` 追加 `"error_count": self._error_count`。

**不引入** `mode="raise"`：风控链自身故障时阻断交易会造成比放行更大的损失（A4「降级须显式并计量」，计量即满足）。

### D3 传染分析显形（B3）

**D3.1 `ContagionNetwork`**（`core/global_contagion.py` L63-L72）

```python
degraded_components: list[str] = field(default_factory=list)
```

带默认值 → 既有一切 `ContagionNetwork(...)` 构造点（含 L397-L404 空早退）零改动。`field` 已在模块顶部导入（L21）。

**D3.2 中心性兜底**（L420-L434）

try 前初始化 `degraded_components: list[str] = []`；except 改为：

```python
except Exception as e:
    logger.warning(f"特征向量中心性计算失败，退化为等权: {e}")
    centrality = {m: 1.0 / n for m in markets}
    degraded_components.append("centrality")
```

**D3.3 MST 兜底**（L437-L448）

```python
except Exception as e:
    logger.warning(f"最小生成树计算失败，返回空边集: {e}")
    mst_edges = []
    degraded_components.append("mst")
```

最终 `return ContagionNetwork(...)` 追加 `degraded_components=degraded_components`。

**D3.4 `compute_granger_causality`**（L568-L591）

三条 return 路径统一含 `failed` 键（只增键、不改既有键）：

| 路径 | 返回值 |
|------|--------|
| 样本不足早退（L574-L575） | `{"causal": False, "p_value": 1.0, "lag": 0, "failed": False}` |
| 正常（L588） | 原键 + `"failed": False` |
| except（L589-L591） | 原键 + `"failed": True` |

**`failed` 的语义严格限定为「计算抛异常」**；样本不足属前置条件不满足，已有 `causal=False` 表达，不计入 `failed`（避免语义二次混淆）。

### D4 EventLog 失败计量（B4）

**D4.1 计数器**（`core/event_log.py` `__init__`）

```python
self._stats: dict[str, int] = {
    "read_failures": 0,
    "write_failures": 0,
    "skipped_lines": 0,
}
```

初始化位置**必须早于 `self._recover_state()`（L75）**——恢复期 `skipped_lines` 自增依赖 `_stats` 已存在，否则构造期 AttributeError（复审观察 F-S4-P026-6；T11 坏行用例兜底）。

**D4.2 自增点（4 处）**

| 位置 | 计数键 |
|------|--------|
| `read` L158-L159 窄类型跳行（U-P026-6） | `skipped_lines += 1` |
| `read` L160-L161 外层 except | `read_failures += 1` |
| `_append_to_disk` L269-L270 | `write_failures += 1` |
| `_recover_state` L304-L305 窄类型跳行（U-P026-6） | `skipped_lines += 1` |

**D4.3 `stats()`**

```python
def stats(self) -> dict[str, int]:
    """运行期失败计数快照（只读；P-026 D4）"""
    return dict(self._stats)
```

**不加锁**（复审订正 F-S4-P026-3）：初稿论证「`threading.Lock` 非可重入会自死锁」引用了错误锁类型——`self._lock` 实为 `threading.RLock()`（L61，可重入），重入不会死锁。结论仍成立，理由重写：write 路径自增点已在 `append` 的锁临界区内（RLock 保护）；read 路径两处自增点本不在任何锁内，加锁无法与之互斥；构造期 `_recover_state` 单线程；三计数器仅观测用途，GIL 下容忍极端并发丢增量，加锁收益趋零。

**不改 `read/query` 返回值**——保持既有消费方零改动，`stats()` 是唯一观察出口。

### D5 Walk-Forward 窗口失真计量（B4）

**D5.1 `WalkForwardResult`**（`core/walk_forward.py` L219-L231）

```python
window_results: list[dict]
agent_period_failures: int = 0
```

**D5.2 引擎计数**（`core/walk_forward_engine.py`）

- `__init__`：`self._agent_period_failures = 0`
- `run()` 开头（与 `self.window_results = []` 同处）：`self._agent_period_failures = 0`（D7，规避 R7 多次 run 累积）
- `_set_agent_period` L185-L186 except：`self._agent_period_failures += 1`（日志文案不动）
- `_aggregate_results` L231：`return WalkForwardResult(window_results=test_results, agent_period_failures=self._agent_period_failures)`

### D6 零改动清单

K 类 8 处（`data.py` ×3、`event_log.py` L278/L286/L313/L383、`walk_forward_engine.py` L214）与排除 4 处（`config_v2.py` ×3、`execution.py` L251）**不触碰任何一行**。

### D7 计数生命周期

| 对象 | 生命周期 | 重置点 |
|------|----------|--------|
| `FactorPipeline._neutralize_skip_counts` | 实例累计 | 无（setup 期一次性跑完） |
| `GuardPlugin._error_count` / `EventLogPlugin._error_count` | 实例累计 | 无 |
| `EventLog._stats` | 实例累计（含构造期恢复） | 无 |
| `WalkForwardEngine._agent_period_failures` | 每轮 run | `run()` 开头 |

### D8 文案与类型约定

- 文案格式：`f"<位置> <动作>失败，<后果>: {e}"`，中文，不含堆栈（`exc_info` 保持关闭，与既有 warning 风格一致）。
- 新增公开方法一律带类型标注（mypy `--check-untyped-defs` 口径）。
- 新增字段一律带默认值，保证既有构造调用点零改动。

---

## 4. 实现规格

### 4.1 变更面（8 core + 1 test）

| # | 文件 | 变更 | 估行 |
|---|------|------|------|
| 1 | `core/factor.py` | `Callable` 导入、`_error_sink` / `_neutralize_skip_counts`、`set_error_sink` / `neutralize_skip_counts` / `_report_error`、两处 except | +32 / -3 |
| 2 | `core/diagnostics.py` | `STAGES` 追加 `"factor"`；`classify_day_error` 加 `factor` 分支 | +8 |
| 3 | `core/engine_v2.py` | `_precompute_factors()` 前注入 sink（D1.4） | +5 |
| 4 | `core/engine_plugins.py` | `EventLogPlugin._error_count` + `_log` 升级 + `get_stats`；`GuardPlugin._error_count` + except + `get_stats` | +14 / -2 |
| 5 | `core/global_contagion.py` | `ContagionNetwork.degraded_components`；两处兜底 warning + append；Granger 三处 return 加 `failed` | +16 / -5 |
| 6 | `core/event_log.py` | `_stats` 初始化 + 4 自增点 + `stats()` | +16 / -2 |
| 7 | `core/walk_forward.py` | `WalkForwardResult.agent_period_failures` | +1 |
| 8 | `core/walk_forward_engine.py` | 计数字段 / run 重置 / except 自增 / aggregate 传入 | +5 / -1 |
| 9 | `tests/test_p026_silent_exception_governance.py` | T1-T12（新建） | +240 |

合计 ≈ **+337 / -13**（代码 ≈97 行，测试 ≈240 行）。

### 4.2 测试规格（12 函数 / 16 实例，T1 参数化 5 例）

| ID | 覆盖 | 断言要点 |
|----|------|----------|
| **T1** | `classify_day_error("factor", ...)` | `LinAlgError`→`("solver", False)`；`ValueError`/`KeyError`→`("data", False)`；`TypeError`→`("internal", False)` |
| **T2** | factor sink 未注入 | `process()` 正常返回；`neutralize_skip_counts == {"degenerate_columns": 0, "regression": 0}` |
| **T3** | factor 去常数列失败 | 注入使 `np.std` 抛错的 X（`monkeypatch` `np.std`）→ 计数 `degenerate_columns == 1`，sink 收到 `stage == "factor"` |
| **T4** | factor 回归失败 | `monkeypatch` `np.linalg.lstsq` 抛 `LinAlgError` → 计数 `regression == 1`，结果等于输入副本（跳过该日） |
| **T5** | 端到端 `run_diagnostics` | 构造最小引擎 + `factor` 异常 → `additional_info["run_diagnostics"]["counts"]["factor"] >= 1`；正常路径 `counts` 无 `factor` 键 |
| **T6** | fake pipeline 零破坏 | 注入无 `set_error_sink` 的 fake pipeline → `setup()` 不抛错（`getattr` 探测生效） |
| **T7** | `EventLogPlugin._log` 失败 | 令 `event_log.append` 抛错 → `_error_count == 1`，`caplog` 记录 **WARNING** 级（非 DEBUG） |
| **T8** | `GuardPlugin` 异常 | 令 `create_guard_context_from_engine` 抛错 → `check_trade` 返回 `(True, [])`；`get_stats()["error_count"] == 1` 且 `blocked_count` 不变 |
| **T9** | `ContagionNetwork.degraded_components` | 令 `np.linalg.eigh` 与 `minimum_spanning_tree` 抛错（后者 patch `core.global_contagion.minimum_spanning_tree`——L28 from-import 绑定，patch scipy 原名无效；复审订正 F-S4-P026-4）→ `degraded_components == ["centrality", "mst"]`；正常路径为 `[]`；空市场早退仍为 `[]` |
| **T10** | `compute_granger_causality` 三路径 | 正常→`failed is False`；样本不足→`failed is False`；`monkeypatch` 抛错→`failed is True` |
| **T11** | `EventLog.stats()` | 写盘失败（路径指向目录）→ `write_failures >= 1`；坏行文件（1 有效 + 1 截断 JSON）→ `skipped_lines >= 1`；`read()` 返回有效条目不变 |
| **T12** | `WalkForwardResult.agent_period_failures` | fake agent 的 `set_period` 抛错 → `agent_period_failures >= 1`；不支持 `set_period` 的 agent → `== 0`；二次 `run()` 不累积 |

### 4.3 文案约定（逐条）

| 位置 | 文案 |
|------|------|
| factor 去常数列 | `日期 {date} 去常数列失败，跳过中性化: {e}` |
| factor 回归 | `日期 {date} 中性化失败: {e}`（既有文案保持） |
| EventLog 记录 | `EventLog 记录失败: {e}`（既有文案保持，仅升级别） |
| Guard 异常 | `Guard 检查异常（已放行）: {e}` |
| 中心性 | `特征向量中心性计算失败，退化为等权: {e}` |
| MST | `最小生成树计算失败，返回空边集: {e}` |
| 因子旁路调用 | `因子异常旁路调用失败（已忽略）`（debug） |

---

## 5. 不变式

| ID | 不变式 | 验证 |
|----|--------|------|
| **I1** | 正常路径零控制流变更：无异常时返回值 / 控制流与 HEAD 逐字节一致 | golden G1-G7 + T2/T9/T10 的正常路径断言 |
| **I2** | 计数与上报路径自身不得抛错 | `_report_error` try/except；T3/T4 反向注入 |
| **I3** | 只增字段、不改既有键 | `ContagionNetwork` / `WalkForwardResult` / `get_stats()` / `stats()` 全为新增 |
| **I4** | `day_error_mode="off"` 语义不变（采集器首行返回 None） | T5 的 off 变体 |
| **I5** | 注入 / fake 对象零破坏（`getattr` 探测） | T6 |
| **I6** | 无全局可变状态 | 全批新增字段均挂在实例上 |
| **I7** | K 类 8 处 + 排除 4 处零 diff | `git diff --stat` 逐文件核对 |

---

## 6. 验证契约

| ID | 契约 | 命令 / 判据 |
|----|------|-------------|
| **V1** | 全量测试不回归 | `MPLBACKEND=Agg python -m pytest -q tests` → **≥687 passed**（671 基线 + 新增 **16 items** = 12 函数，T1 参数化 5 例；原稿「12 项后 = 683」经 Step 8 一致性 Review 订正，订正链 F-I-P026-1） |
| **V2** | 类型门禁 | `python -m mypy --explicit-package-bases --check-untyped-defs core` → 37 files, no issues |
| **V3** | 格式门禁 | `python -m black --check core tests` → unchanged |
| **V4** | golden 不变 | G1-G7 逐字节对比 HEAD 产物，零漂移 |
| **V5** | 红线可观测性 | 每批交付判据（RESEARCH §8）：B1 `counts["factor"]≥1` / B2 `error_count==1` / B3 `degraded_components` / B4 `stats()["write_failures"]≥1` 与 `agent_period_failures≥1` |
| **V6** | 保护面 | `config_v2.py` / `execution.py` / K 类 8 处所在行 `git diff` 为空 |

---

## 7. 风险登记

| # | 风险 | 映射 | 缓解 | 验证 |
|---|------|------|------|------|
| R1 | 新增字段破坏消费方 | RESEARCH R1 | 只增带默认值字段；`ContagionNetwork` / `WalkForwardResult` / `read()` 返回形状不变 | T9/T10/T12 + V1 |
| R2 | 日志级别提升致既有测试断言失败 | R2 | Step 9 先跑全量定位受影响测试；文案保持不变、仅改级别 | V1 |
| R3 | factor sink 破坏 fake pipeline | R3 | `getattr` 探测（P-025 D5 同形） | T6 |
| R4 | 全局状态 | R4 | 已规避（D6） | I6 |
| R5 | 过度治理放大日志噪声 | R5 | K 类 8 处零改动；warning 只在异常时输出一次/日 | V6 |
| R6 | golden 漂移 | R6 | 正常路径零改动 | V4 |
| R7 | 计数多次 run 累积 | R7 | D7：WalkForward 每 `run()` 重置 | T12 |
| R8 | `_stats` 加锁导致自死锁 | 新增 | D4.3 明确不加锁（复审订正：锁实为 RLock，「死锁」前提不成立；结论改由观测容忍度 + read 路径无锁支撑） | T11（写盘失败路径） |
| R9 | 因子 sink 注入晚于 `_precompute_factors()` → 漏采 | 新增 | D1.4 硬性规定插入位置 | T5 端到端 |

---

## 8. 回退点

| 回退位 | 范围 | 方式 |
|--------|------|------|
| **RB1** | B1（factor / diagnostics / engine_v2） | `git revert` 单提交；无跨批依赖 |
| **RB2** | B2（engine_plugins） | 同上；`get_stats()` 新增键被删不影响既有调用方（`dict.get`） |
| **RB3** | B3（global_contagion） | 同上；`degraded_components` 带默认值，删除字段不影响构造 |
| **RB4** | B4（event_log / walk_forward） | 同上；`stats()` 为纯新增方法 |
| **RB5** | 全批 | 四批彼此独立，无共享中间态；全批回退后工作区等于 `9c332cc` |

---

## 9. 设计期发现

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| **F-D-P026-1** | P3 | RESEARCH 成本行「6 文件」低估：实际 **8 个 core 文件** —— 漏计 `engine_v2.py`（sink 接线，无此改动 B1 无法端到端观测）与 `diagnostics.py`（`STAGES` / `classify_day_error` 扩展） | 本 DESIGN §4.1 按 8 文件列全；IMPL 以本表为准 |
| **F-D-P026-2** | **P2** | sink 注入**时点**是正确性条件而非风格问题：`self.pipeline` 在 L228 创建，但 `_precompute_factors()` 在 L237 立即调用，中性化即发生在该调用内。若按 P-025 惯例（executor sink 放在 setup 第 12 步）把 factor sink 也放到 setup 末尾，则 **setup 期全部因子异常漏采**，B1 的交付判据 `counts["factor"]≥1` 永远不成立 | D1.4 硬性规定插入于 L235 与 L237 之间；T5 端到端覆盖 |
| **F-D-P026-3** | 观察 | `STAGES` 常量无运行时使用（P-025 F-S10-P025-3 已登记同性质问题），追加 `"factor"` 属词表契约变更，对运行时零影响 | 保持；在 IMPL 中于常量注释补一句「P-026 追加 factor」 |
| **F-D-P026-4** | 观察 | `compute_granger_causality` 的样本不足早退路径（L575）**本就缺 `strength` 键**，与另两条路径不对称 | 本批不补（避免超出「只增 failed」范围）；登记待 U-P025-2 类字段治理时一并裁决 |

---

## 10. 结论

**设计选型**：M-A 逐点三态 + 分级显形，按 B1-B5 五批实施，**本批 0 项 fail-fast、0 项全局状态**。

**四个 P2 级设计约束**（Step 4 Review 重点核验）：
1. **F-D-P026-2**：factor sink 必须早于 `_precompute_factors()`（L235→L237 之间）。
2. **D2.2**：Guard **保持 fail-open**，只加计数，不改返回值。
3. **D4.3**：`_stats` 自增**不加锁**（复审订正 F-S4-P026-3：锁为 RLock 可重入，「自死锁」原论证作废；结论由观测容忍度支撑）。
4. **D5.2**：`agent_period_failures` 在 `run()` 开头重置，否则多次 run 累积。

**下一步**：Step 5 IMPL 已完成（B1-B5，[IMPL_p026](IMPL_p026_silent_exception_governance.md)）；Step 6 IMPL 独立 Review **pass**（§10，异构基座 GLM-5.3-Flash）；**Step 7 CHECKLIST 已完稿**（[CHECKLIST_p026](CHECKLIST_p026_silent_exception_governance.md)，45 项零预填）；下一为 Step 8 一致性 Review（须异构基座 ≠ DeepSeek-V4.1-Flash）。

---

## 11. Step 4 独立 Review 记录（2026-11-13）

- **复审基座**: GLM-5.3-Flash ≠ DESIGN 作者 DeepSeek-V4.1-Flash（RULE-5 异质性成立）
- **复审对象**: 本文件 @ 提交 `76f7e6e`（HEAD）

### 11.1 E1 机械复核（pass）

锚点逐点验证 32 处零漂移：factor.py L32-41 / L341-345（`except Exception: continue` 无 `as e`）/ L366-368；diagnostics.py L25-36（STAGES 10 值无 factor）/ L57-74（rebalance 分支 L61-70 → 通用判定 L71-74，插入点存在）/ L94（record 签名 `(date, stage, exc)`，sink 同形成立）/ L96-97（off 首行）/ L108+L165（counts 按 stage 分键，T5 依据）；engine_v2.py L224 / L228 / L235 / L237（插入空隙 L236）/ L287-288（executor sink 惯例）/ L364（`raise_if_needed` 唯一调用点）；engine_plugins.py L157-162（debug）/ L179-190（无 `_error_count`）/ L235-237（fail-open）/ L264-271（Guard `get_stats` 4 键已存在）；global_contagion.py L21（`field` 已导入）/ L63-72 / L397+L453（构造点）/ L424-434 / L437-448（两兜底形态与 D3.2/D3.3 一致）/ L568 / L574-575（早退无 `strength`）/ L588 / L589-591；event_log.py L61（**RLock**）/ L101-L112（append 持锁调 `_append_to_disk`）/ L158-159 / L160-161 / L269-270 / L304-305；walk_forward.py L219-231；walk_forward_engine.py L68 / L77（run 重置点）/ L178（hasattr set_period，T12 依据）/ L185-186 / L231。

算术复核：变更面 8 core + 1 test；估行 +97/−13 代码 + 240 测试 = +337/−13；V1 671+12=683；black 115 = 37+78；§2 映射 10/10。措辞核查：D2.1「新增 get_stats」/ D2.2「追加 get_stats」与现状（EventLogPlugin 无 / GuardPlugin 有 L264）均正确。

### 11.2 E2 门禁（pass）

| 门禁 | 结果 |
|------|------|
| pytest（MPLBACKEND=Agg，Python312） | **671 passed, 172 warnings**（83.89s，与基线一致） |
| mypy `--explicit-package-bases --check-untyped-defs core` | **37 files, no issues** |
| black --check core tests | **115 files unchanged** |

### 11.3 E3 幻觉排除（pass）

A1 STAGES 无运行时使用（全仓 grep 唯一命中定义处，F-D-P026-3 属实）/ A2 EventLog 无 stats 方法（方法全清单）/ A3 Granger 早退无 strength（L575 实证）/ A4 executor `set_error_sink` 惯例存在（engine_v2 L287-288 + execution.py L185）/ A5 K 类锚点 L278 / L286 / L313 / L214 实证 / A6 §2 映射 D1-D8 ↔ RESEARCH §4/§5/§6/§8 逐条对应。

### 11.4 E4 发现（0 P1 / 0 P2 / 4 P3 + 2 观察；P3 均已回写订正正文）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S4-P026-1 | P3 | D1.1 `_report_error(date, reason, exc)` 的 `reason` 为死参数：分桶计数由调用方直接完成，sink 调用硬编码 `"factor"`（与 record 同形只收 stage），reason 无消费点 | 签名修订为 `_report_error(date, exc)`，D1.2 两调用点同步 |
| F-S4-P026-2 | P3 | raise 模式语义扩散未声明：factor 分支 data/internal ∈ `RAISE_CATEGORIES`，`day_error_mode="raise"` 时 setup 期因子异常将在首个交易日 `raise_if_needed()`（engine_v2 L364 唯一调用点）抛出，date 为因子日期 | D1.3 补语义声明；off/report 不受影响 |
| F-S4-P026-3 | P3 | D4.3/R8/§10.3「不加锁」论证事实错误：`self._lock` 实为 `threading.RLock()`（event_log L61，可重入），「Lock 非可重入自死锁」前提不成立 | 结论「不加锁」维持，论证重写（write 在锁内 / read 无锁 / 构造期单线程 / 观测容忍丢增量） |
| F-S4-P026-4 | P3 | T9 的 `minimum_spanning_tree` 为 global_contagion L28 from-import 绑定，patch 必须指向 `core.global_contagion.minimum_spanning_tree`，patch scipy 原名无效 | T9 断言要点补 patch 目标 |
| F-S4-P026-5 | 观察 | `_recover_state` 外层 except（L313-314「EventLog recovery error」）不计入任何 stats 计数器，恢复整体失败对 `stats()` 不可见 | 本批不补（有 warning + 概率低）；登记 U 类字段治理时一并裁决 |
| F-S4-P026-6 | 观察 | D4.1 `_stats` 初始化若置于 `__init__` 末尾，晚于 L75 `self._recover_state()` → 构造期 AttributeError | D4.1 补初始化时点约束（须早于 L75）；T11 坏行用例兜底 |

### 11.5 结论

**pass**——设计进入 Step 5 IMPL；实施以本文件 §11 复审后文本（D1.1 修订签名 / D1.3 raise 声明 / D4.1 初始化时点 / D4.3 重写论证 / T9 patch 目标）为准。
