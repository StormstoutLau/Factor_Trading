# IMPL：P-026 静默失败治理第二批（因子链路 / 插件 / 传染 / 事件日志 / Walk-Forward）

> **批次**: P-026 · **T1**（`core/` 行为契约 + 新增可观测字段与方法，零 fail-fast）
> **上游**: [DESIGN_p026](DESIGN_p026_silent_exception_governance.md)（D1-D8 / I1-I7 / V1-V6 / §11 Step 4 独立 Review）
> **状态**: Step 6 独立复审 **pass**（2026-11-13，GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；0 P1/P2，1 P3 已订正 §2，3 观察登记，见 §10）+ **Step 7 CHECKLIST 已完稿**（45 项零预填，见 [CHECKLIST_p026](CHECKLIST_p026_silent_exception_governance.md)）
> **代码证据时点**: 实施前 HEAD `bbb55bc`（2026-11-13，工作区干净）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（代码） | `core/factor.py` / `core/diagnostics.py` / `core/engine_v2.py` / `core/engine_plugins.py` / `core/global_contagion.py` / `core/event_log.py` / `core/walk_forward.py` / `core/walk_forward_engine.py`（**8 个，与 DESIGN §4.1 一致**） |
| 变更文件（测试/文档） | `tests/test_p026_silent_exception_governance.py`（新增）/ `docs/IMPL_p026_silent_exception_governance.md`（本文件）/ `docs/PROGRESS.md` / `CHANGELOG.md` |
| 零改动面 | `core/interfaces.py`（**不**加抽象方法，sink 走 `getattr` duck-typing，与 P-025 一致）/ `core/data.py` / `core/execution.py` / `core/rebalance.py` / `core/portfolio.py` / `core/pending.py` / `core/factory.py` / `filter/` / `agents/` / `scripts/` / `cli.py` / `engine_v3_vector.py` / `tests/golden/*.json` / `pyproject.toml` / `.github/` |
| 行为变更 | **4 类，均为可观测性增强**：① `FactorPipeline` 新增 `set_error_sink` / `neutralize_skip_counts` / `_report_error`；② `classify_day_error` 新增 `factor` 分支、`STAGES` 追加 `"factor"`；③ `EventLogPlugin._log` 失败由 `debug` 升 `warning` 并计数、新增 `get_stats()`；`GuardPlugin.get_stats()` 追加 `error_count` 键；④ `ContagionNetwork` 新增 `degraded_components` 字段、Granger 结果新增 `failed` 键；`EventLog` 新增 `stats()`；`WalkForwardResult` 新增 `agent_period_failures` 字段。**零 fail-fast**（本批 0 项 F 类裁决） |
| 门禁口径 | `pytest -q`（`MPLBACKEND=Agg`，Python312）：**671 → 687**（新增 16 个测试项 = 12 个测试函数，T1 参数化 5 例）；`mypy --explicit-package-bases --check-untyped-defs core`：**37 files 0 error**；`black --check core tests`：**116 unchanged**（115 + 新测试文件 1） |

**设计前提（§11 复审后文本）**：① factor sink 注入必须插在 `FactorCombiner` 之后、`_precompute_factors()` 之前（F-D-P026-2）；② `_stats` 初始化必须早于 `_recover_state()`（F-S4-P026-6）；③ `EventLog._stats` 自增**不加锁**（F-S4-P026-3 订正论证：`self._lock` 为 `RLock` 可重入，写路径自增点已在锁临界区内，read 路径自增点本无锁，观测容忍极端并发丢增量）；④ T9 的 MST patch 目标为 `core.global_contagion.minimum_spanning_tree`（from-import 绑定，F-S4-P026-4）。

---

## 2. 任务拆解

| ID | 批次 | 任务 | 对应 | 产出 |
|----|------|------|------|------|
| **B1** | 代码 | `factor.py` 旁路接口 + 双原因计数；`diagnostics.py` `STAGES`/`classify_day_error`；`engine_v2.py` setup 期 sink 注入 | D1.1-D1.4 | 3 文件 +42/−2 |
| **B2** | 代码 | `engine_plugins.py`：`EventLogPlugin` 计数 + `_log` 升级 + `get_stats()`；`GuardPlugin` 计数 + 文案（**保持 fail-open**） | D2.1-D2.2 | 1 文件 +13/−2 |
| **B3** | 代码 | `global_contagion.py`：`degraded_components` 字段 + 两兜底 warning/标记 + Granger 三路径 `failed` | D3.1-D3.4 | 1 文件 +20/−5 |
| **B4** | 代码 | `event_log.py` `stats()` + 4 自增点；`walk_forward.py` 字段；`walk_forward_engine.py` 计数/重置/回填 | D4.1-D4.3 / D5.1-D5.2 | 3 文件 +25/−1 |
| **B4t** | 测试 | 新增 `tests/test_p026_silent_exception_governance.py`（T1-T12） | V1-V6 | 422 行 / 16 items |
| **B5** | 文档 | 门禁回归 + 本 IMPL + `PROGRESS` §3.31 + `CHANGELOG` | — | docs |

---

## 3. 实施顺序与依赖

```text
B1（factor 链路）─┐
B2（插件层）      ├─→ B4t（测试，依赖全部代码面）
B3（传染分析）    │
B4（EventLog / WF）┘
B1..B4t ─→ B5（门禁 + 文档）
```

- **B1 的 D1.4 是全批唯一「顺序敏感」改动**：sink 注入早于 `_precompute_factors()`，否则 setup 期因子异常全部漏采（T5 以 `sink_was_set` 断言固化该顺序）。
- **B2 的 `GuardPlugin` 保持 fail-open**：本批只补计量与文案，`return True, []` 不动（DESIGN §10 第 2 条 P2 级约束）。
- **B4 的 `_stats` 初始化位置**必须早于 `_recover_state()` 调用，否则构造期 `AttributeError`（T11 坏行用例兜底）。
- **合批判断**：8 个文件均落在 `core/`，按 DESIGN §8 回退表采用「单 commit + 文件级回退」，与 P-023/P-025 同法。

---

## 4. 精确变更实录

### 4.1 `core/factor.py`（+29/−2）

| 锚点 | 变更 |
|------|------|
| L8 | `from typing import Any, Callable, Optional`（新增 `Callable`） |
| L41-L44 | `__init__` 新增 `self._error_sink = None` 与 `self._neutralize_skip_counts = {"degenerate_columns": 0, "regression": 0}` |
| L47-L49 | 新增 `set_error_sink(sink)`（形态同 `DayErrorCollector.record`：`(date, stage, exc)`） |
| L51-L54 | 新增 `@property neutralize_skip_counts` 返回 `dict` 拷贝（防外部改写） |
| L56-L64 | 新增 `_report_error(date, exc)`：未注入直接 return；注入后 try 包裹，**自身失败仅 debug 并忽略**（I2：旁路不得影响主流程）。**签名按 F-S4-P026-1 去掉死参数 `reason`** |
| L362-L370 | 去常数列失败：`except Exception as e` + `warning("日期 {date} 去常数列失败，跳过中性化")` + `degenerate_columns` 计数 + `_report_error` + `continue`（原为零日志 `except Exception: continue`） |
| L389-L395 | 回归失败：保留既有 warning 文案，追加 `regression` 计数 + `_report_error` + `continue` |

### 4.2 `core/diagnostics.py`（+8）

| 锚点 | 变更 |
|------|------|
| L31 | `STAGES` 追加 `"factor"`（`# P-026 追加：因子预处理（setup 期一次性）`） |
| L72-L77 | `classify_day_error` 在 `rebalance` 分支之后、通用 `KeyError/FileNotFoundError/ValueError` 判定之前插入 `stage == "factor"` 分支：`LinAlgError → ("solver", False)`；`KeyError/FileNotFoundError/ValueError → ("data", False)`；其余 `("internal", False)` |

**raise 模式语义（DESIGN F-S4-P026-2 声明）**：factor 的 `data`/`internal` 属 `RAISE_CATEGORIES`，`day_error_mode="raise"` 时 setup 期因子异常在首个交易日 `raise_if_needed()`（`engine_v2.py` L364 唯一调用点）抛出；`off`/`report` 不受影响。

### 4.3 `core/engine_v2.py`（+5）

```python
# L237-L242（原 L235 FactorCombiner 与 L237 _precompute_factors 之间）
# 3.5 因子异常旁路（P-026 D1.4）：必须早于 _precompute_factors()，否则 setup 期因子异常漏采
factor_sink_setter = getattr(self.pipeline, "set_error_sink", None)
if factor_sink_setter is not None:
    factor_sink_setter(self._diagnostics.record)

self._precompute_factors()
```

### 4.4 `core/engine_plugins.py`（+13/−2）

| 锚点 | 变更 |
|------|------|
| L60 | `EventLogPlugin.__init__` 新增 `self._error_count = 0` |
| L163-L169 | `_log` 失败：`logger.debug → logger.warning("EventLog 记录失败: …")` + 计数；新增 `get_stats()` 返回 `{"enabled", "error_count"}` |
| L199 | `GuardPlugin.__init__` 新增 `self._error_count = 0` |
| L245-L247 | 检查异常：文案改「Guard 检查异常（已放行）」+ 计数；**`return True, []` 保持 fail-open** |
| L281 | `GuardPlugin.get_stats()` 追加 `"error_count"` 键（原 4 键 → 5 键，**只增不改**） |

**既有测试兼容性**：`tests/test_engine_plugins.py` 对 `get_stats()` 的断言为键访问式（L141 `stats["blocked_count"] >= 1`、L223 键存在性），追加 `error_count` 零破坏（Step 4 复审已核，本批实测通过）。

### 4.5 `core/global_contagion.py`（+20/−5）

| 锚点 | 变更 |
|------|------|
| L74 | `ContagionNetwork` 新增 `degraded_components: list[str] = field(default_factory=list)`（`field` 已在 L21 导入） |
| L425 | `_build_contagion_network` 内新增局部 `degraded_components: list[str] = []` |
| L437-L440 | 中心性兜底：`except Exception as e` + `warning("特征向量中心性计算失败，退化为等权")` + `append("centrality")` |
| L453-L456 | MST 兜底：`except Exception as e` + `warning("最小生成树计算失败，返回空边集")` + `append("mst")` |
| L467 | 构造 `ContagionNetwork(...)` 回填 `degraded_components` |
| L584 / L602 / L606 | Granger 三路径统一带 `"failed"`：样本不足（前置条件不满足）`False` / 正常 `False` / 异常 `True` |

**零改动面核实**：`L397`/`L453` 之外的空市场早退构造点未传 `degraded_components`，依赖 dataclass 默认值 → `[]`（T9 覆盖）。

### 4.6 `core/event_log.py`（+15）

| 锚点 | 变更 |
|------|------|
| L73-L78 | `__init__` 新增 `self._stats = {"read_failures": 0, "write_failures": 0, "skipped_lines": 0}`，**位置在 `_recover_state()` 之前**（F-S4-P026-6） |
| L165-L166 | `read` 内层窄类型 `except (json.JSONDecodeError, KeyError)` → `skipped_lines += 1` |
| L168-L169 | `read` 外层 `except Exception` → `read_failures += 1`（原已 warning） |
| L278-L284 | `_append_to_disk` 失败 `write_failures += 1`；紧随其后新增 `stats()` 返回 `dict` 拷贝 |
| L318-L319 | `_recover_state` 窄类型 except → `skipped_lines += 1` |

**不加锁**：`read`/`query` 返回值形态不变（I6）；`stats()` 只读拷贝（I7）。

### 4.7 `core/walk_forward.py`（+2）

L228：`WalkForwardResult` 新增 `agent_period_failures: int = 0`（默认值保证既有构造点零改动）。

### 4.8 `core/walk_forward_engine.py`（+8/−1）

| 锚点 | 变更 |
|------|------|
| L65-L66 | `__init__` 新增 `self._agent_period_failures = 0` |
| L80 | `run()` 开头重置（与 `window_results = []` 同处；T12 断言不累积） |
| L188-L190 | `_set_agent_period` 的 `set_period` 异常分支计数 + 保留 warning |
| L235-L238 | `_aggregate_results` 回填 `agent_period_failures=self._agent_period_failures` |

---

## 5. 测试与红绿证据

新增 `tests/test_p026_silent_exception_governance.py`（422 行，16 个测试项）：

| 用例 | 断言要点 | 结果 |
|------|----------|------|
| T1（参数化 5 例） | `classify_day_error("factor", …)`：`LinAlgError→solver` / `ValueError·KeyError·FileNotFoundError→data` / `TypeError→internal`，retryable 全 `False` | 5 passed |
| T2 | 未注入 sink：`process` 正常返回，双计数保持 0 | passed |
| T3 | patch `core.factor.np.std` 抛错 → `degenerate_columns >= 1`，sink 收到 `stage=="factor"` | passed |
| T4 | patch `np.linalg.lstsq` 抛 `LinAlgError` → `regression >= 1`，结果帧与输入完全相等（该日整体跳过） | passed |
| T5 | 引擎端到端：`sink_was_set is True`（D1.4 顺序）、`summary()["counts"]["factor"] >= 1`、`degraded is True`；正常路径无 `factor` 键 | passed |
| T6 | 无 `set_error_sink` 的假管道：`setup()` 不抛错（`getattr` 探测） | passed |
| T7 | `EventLogPlugin._log` 抛 `OSError` → `error_count == 1` + WARNING 级 + 文案命中 | passed |
| T8 | `GuardPlugin` 注入异常 → `(True, [])` 仍放行 + `error_count == 1` + `blocked/warning` 均为 0 | passed |
| T9 | 正常 → `[]`；空市场早退 → `[]`；patch `np.linalg.eigh` 与 `core.global_contagion.minimum_spanning_tree` → `["centrality", "mst"]` | passed |
| T10 | Granger 正常/样本不足 → `failed is False`；patch `statsmodels.tsa.stattools.grangercausalitytests` → `failed is True` | passed |
| T11 | 写盘失败（`log_path` 为目录）→ `write_failures >= 1`；坏行文件 → `read` 返回 1 条有效 + `skipped_lines >= 1` | passed |
| T12 | 抛错 agent → `_agent_period_failures == 1`；无 `set_period` agent → 不增；预置 5 后 `run()`（空窗口）→ `result.agent_period_failures == 0` | passed |

**红态取证（实施顺序内）**：测试文件首轮运行 **1 failed, 15 passed**——T12 因 `WalkForwardEngine` 导入路径写错（`core.walk_forward` → `core.walk_forward_engine`）失败，属测试自身缺陷非实现缺陷；同轮另暴露 `WalkForwardEngine.__init__` 文档串参数名 `base_engine` 与实现 `base_engine_class` 不一致（**已登记 F-I-P026-2 观察，本批不改**）。修正后 **16 passed**。

**T1 计数口径偏差（F-I-P026-1）**：DESIGN V1 预期「12 测试 → 683」，实测 T1 参数化 5 例 → **16 items**，故全量 **687**（671 + 16）；测试**函数**数仍为 12（T1-T12），与 DESIGN §4.2 表格一致。

---

## 6. 门禁结果（2026-11-13 实测）

| 门禁 | 命令 | 结果 |
|------|------|------|
| 全量测试 | `MPLBACKEND=Agg` + Python312 `-m pytest tests -q` | **687 passed, 173 warnings in 71.42s** |
| 类型 | `python -m mypy --explicit-package-bases --check-untyped-defs core` | **Success: no issues found in 37 source files** |
| 形态 | `python -m black --check core tests` | **116 files would be left unchanged**（115 → 116，新增测试文件 1） |
| 受影响面快速回归 | `pytest tests/test_engine_plugins.py tests/test_phase2_factor.py tests/test_p025_day_error_diagnostics.py` | **26 passed**（改动前后均绿，D2.2 追加键零破坏） |
| golden | 随全量 suite 执行（`tests/test_golden_baseline.py` G1-G7） | **全部通过，零重录**（`tests/golden/*.json` 未被修改，`git status` 无变更） |

变更量：`git diff --numstat` 8 文件 **+100/−10**（DESIGN 估算 +97/−13，偏差见 F-I-P026-4）；新测试文件 422 行（DESIGN 估算 ≈240，偏差见 F-I-P026-3）。

> **Step 9 复测（2026-11-13，含 F-S9-P026-1 补丁）**：全量 **687 passed, 172 warnings**（移除 `verbose` 后 statsmodels `FutureWarning` 消失，较 Step 5 读数少 1，**相对 671 基线零新增 warning**）；mypy **37 files 0** / black **116 unchanged** 不变；红态重放 **14 failed / 2 passed** → 绿态 **16 passed**（详见 CHECKLIST §12）。

---

## 7. 实施期发现与偏差

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-I-P026-1 | P3 | DESIGN V1「新增 12 测试 → 683」未计 T1 参数化：T1 5 例 → 实际 16 items，全量 **687** | 本文件 §1/§5/§6 按实测口径记录；DESIGN V1 口径在 CHECKLIST 阶段统一订正 |
| F-I-P026-2 | 观察 | `WalkForwardEngine` docstring（L37/L43）参数名写 `base_engine`，实现为 `base_engine_class`（L52）——文档与签名不一致，测试按实现写 | 本批不改（超范围）；登记 U 类，随下次触碰 `walk_forward_engine.py` 订正 |
| F-I-P026-3 | P3 | 测试实际 422 行 vs DESIGN 估算 ≈240 行：差异来自独立复制的引擎夹具（`_FakeDM`/`_FakeUniverse`/`_Top2Optimizer`/`_AlwaysTrigger`/`_build_config`）+ 12 个用例的 docstring | 接受（夹具独立复制避免与 P-025 测试耦合，符合 DESIGN §4.1「不改原文件」） |
| F-I-P026-4 | P3 | 代码行数 +100/−10 vs DESIGN 估算 +97/−13：`factor.py` 旁路接口与注释比预估多 3 行、`global_contagion.py` 新增局部变量与标记比预估少 3 行删除 | 接受（净差 ≤3 行，无功能偏差） |
| F-I-P026-5 | 观察 | `_set_agent_period` 在 `hasattr(agent, "distillation_config")` 为 True 但值为 `None` 时抛 `AttributeError`（L194 无 None 守卫） | 本批不改（D5 仅补计数）；已登记 U 类，属「静默失败治理」相邻面，待第三批裁决 |
| F-I-P026-6 | 观察 | T10 触发 `statsmodels` `FutureWarning: verbose is deprecated`（库内部默认参数，非本项目调用导致） | **Step 9 已消除**：移除 `grangercausalitytests(..., verbose=False)` 实参（F-S9-P026-1），warnings 回落 **172**（零新增），见 §11 |

---

## 8. 回退点

| 批 | 文件 | 回退方式 |
|----|------|----------|
| B1 | `factor.py` / `diagnostics.py` / `engine_v2.py` | 文件级 `git checkout <base> -- <file>`；三者互相独立可单退（`engine_v2` 的 `getattr` 探测对无 sink 管道零影响） |
| B2 | `engine_plugins.py` | 单文件回退；`get_stats` 追加键为只增，回退无消费方破坏 |
| B3 | `global_contagion.py` | 单文件回退；`degraded_components` 有 dataclass 默认值，回退后既有构造点无感 |
| B4 | `event_log.py` / `walk_forward.py` / `walk_forward_engine.py` | 按文件回退；`stats()` 与字段默认值均为只增 |
| B4t | 新测试文件 | 直接删除；不构成对其他测试的依赖 |

**全批回退**：`git revert <SHA>` 单 commit 即可恢复（8 文件 + 1 测试文件）。

---

## 9. 下一步

**Step 9 已完成**：[CHECKLIST_p026](CHECKLIST_p026_silent_exception_governance.md) 45/45 实测列落证据（红态 **14 failed / 2 passed** → 绿态 **16 passed**；全量 **687** / mypy **37** / black **116**）。Step 9 实施期发现并修复 **F-S9-P026-1**（CI Python 3.10/3.11 装 statsmodels 0.15.0 已移除 `verbose` 参数 → T10 在 CI 失败）：补丁与本文件 §11 留痕。下一为 **Step 10 ADD 审计**（须异构基座 ≠ 本 IMPL / DESIGN / CHECKLIST 作者 DeepSeek-V4.1-Flash）→ RULE-5 异构终审 → CI 回收收口。

---

## 10. Step 6 独立复审记录（2026-11-13）

> **复审基座**: GLM-5.3-Flash ≠ IMPL 作者 DeepSeek-V4.1-Flash（异质性成立）；复审对象 = 本文件 @ 提交 `e79bf06`。

| 维度 | 结果 |
|------|------|
| E1 机械复核 | ✅ `git show --stat` / `--numstat` 重放：15 files +744/−19、8 core **+100/−10** 与 §6 一致，§4.1-4.8 各文件行数逐一吻合；门禁三重放全过——pytest **687 passed, 173 warnings in 77.94s**、mypy **37 files 0**、black **116 unchanged**；B1-B4 五文件 diff 全量重放与 §4.1-4.8 声明逐行一致 |
| E2 红态重放 | ✅ `git checkout bbb55bc -- <8 core 文件>` → 新测试 **14 failed, 2 passed**（失败均为「目标接口不存在/计数缺失」类：`AttributeError` `set_error_sink`/`neutralize_skip_counts`/`get_stats`/`degraded_components`/`stats`/`_agent_period_failures`、`KeyError` `failed`/`error_count`、T1 retryable 断言 `False` vs 旧 `('data', True)`）；2 passed 属红态预期不红——T1[exc4]（TypeError→internal，旧通用兜底恰好同结果）与 T6（旧引擎无注入调用，setup 天然不抛错）；恢复 HEAD 后 `git status` 干净 |
| E3 幻觉排除 | ✅ T1-T12 断言与 §5 表格逐条对码一致；F-I-P026-2 属实（docstring L37 `base_engine` vs 实现 L52 `base_engine_class`）；F-I-P026-5 属实（L194 `distillation_config` 直接赋值无 None 守卫）——两条观察声明均为真实代码事实 |
| E4 盲区扫描 | ✅ 8 文件全部 `except Exception` 块扫描：本批治理点全部带计量+日志；3 项范围外遗留见下表观察 |

**发现与定级**：

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-S6-P026-1 | P3 | §2 任务表 B1 产出「3 文件 +42/−4」删除行算术错误：numstat 实测 = factor −2 + diagnostics −0 + engine_v2 −0 = **−2**（+42 正确；作者将「修改行」重复计入删除行；B2 −2 / B3 −5 / B4 −1 正确，合计 −10 一致） | **已订正 §2 原文**（−4 → −2）；不影响代码与门禁结论 |
| O-S6-P026-1 | 观察 | `walk_forward_engine.py` L218-219 窗口回调（`window_callbacks`）失败仅 warning、无计量——DESIGN D5 范围仅声明 agent period 失败计数 | 范围外遗留（有 warning 非完全静默），登记待「静默失败治理」第三批裁决 |
| O-S6-P026-2 | 观察 | `event_log.py` L292/L300 listener 异常与 L328 recovery 外层 except 仅 warning、无计量——D4 三计数器范围仅含 read/write/skipped 窄类型路径 | 同上，登记待第三批裁决 |
| O-S6-P026-3 | 观察 | `diagnostics.py` L129/L160 采集器自身失败仅 error 日志——属 P-025 I2 设计语义（sink 旁路自身容错），非缺陷 | 接受，无需处置 |

**复审结论**: **pass**（0 P1 / 0 P2 / 1 P3 已订正 / 3 观察登记）。E1-E4 全维度通过，门禁三重放与 §6 完全一致，无幻觉、无范围外改动（numstat 15 files 均在声明面内）。

---

## 11. Step 9 TDD 实施期补丁记录（2026-11-13）

> **执行基座**: DeepSeek-V4.1-Flash（Step 9 非复审步，RULE-5 不要求异构）。

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-S9-P026-1 | **P2** | 远端 CI（Python 3.10 / 3.11，`statsmodels==0.15.0`）T10 失败：`grangercausalitytests() got an unexpected keyword argument 'verbose'`，异常被 D3.4 的 `except` 捕获后 `failed=True`，触发 `assert True is False`。本地 0.14.6 仅 `FutureWarning` 不报错 → **本地绿、CI 红**（Step 5 起 4 个 run 连续失败） | **已修复**（单行）：`core/global_contagion.py` 调用改为 `grangercausalitytests(data[["y", "x"]], maxlag=max_lag)`（0.15 已删 `verbose`；0.14 默认即 False），跨版本兼容。复测：新测试 **16 passed** / 全量 **687 passed** / mypy **37** / black **116** |
| F-S9-P026-2 | P3 | F-I-P026-6 的 `FutureWarning` 随补丁消失，warnings 由 173 回落 **172**（与 671 基线的差值即新增 16 测试的既有 warning 之外的零新增） | 接受；§6 / §7 已同步订正，CHECKLIST F7 实测列注明偏差 |

**变更面（Step 9 增量）**：`core/global_contagion.py` **+1/−1**（仅调用行）；无其他代码改动；不改变 D3.4 三路径键契约。

**回退**：`git checkout e79bf06 -- core/global_contagion.py` 可单独回退本补丁（但 CI T10 将复红）。
