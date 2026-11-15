# DESIGN：P-027 静默失败治理第三批（core 外 22 处 except 分级显形）

> **上游**: [RESEARCH_p027](RESEARCH_p027_silent_exception_governance_phase3.md)（Step 1 取证 + Step 2 Review pass）
> **档位**: **T1**（`agents/` / `filter/` / `scripts/` / `batch_backtest/` / `strategy_evaluation/` / `cli.py`；零 fail-fast、零返回值语义变更）
> **设计基座**: DeepSeek-V4.1-Flash（Step 4 复审须异构）
> **日期**: 2026-11-15

---

## 1. 决策总览

| ID | 决策 | 覆盖处 | 一句话 |
|----|------|--------|--------|
| **D1** | `filter/` 5 处：载体下沉 `BaseFilter`，补计量、**保留 fail-open** | 5 | `_failure_counts` + `_record_failure()` 在基类，4 子类各 1 行接入 |
| **D2** | `agents/` 9 处：逐类实例计数器，补计量；**仅 1 处级别提升** | 9 | 6 个类各挂 `_failure_counts`，`debug` → `warning` 仅 `agent_framework.py:1074` |
| **D3** | C 类 2 处：**补日志 + 补计量**（静默 → 显形），返回值不变 | 2 | `stats.py:139`、`assumption_monitor.py:201` 各 1 条 `logger.warning(..., exc_info=True)` |
| **D4** | 结构化出口：6 个既有报告方法追加 `failure_counts` 键 + 4 个新只读方法 | — | 对齐 A 类范式（日志 + 结构化输出） |
| **D5** | E 类 4 处 + A 类 2 处：**零改动** | 6 | 进程边界与既有合规范式不动 |
| **D6** | 计数生命周期：实例累计；**两个批量入口显式清零** | — | `StrategyEngine.run()`、`UniverseFilter.build_masks()` |
| **D7** | 文案与异常约定：不新增 raise、不改捕获类型、不改既有文案 | — | 仅新增 2 条 warning + 1 处级别提升 |

**计量点合计 16 处**（B 14 + C 2）+ **零改动 6 处**（E 4 + A 2）= 22 处，与 RESEARCH §3 清单逐一对应。

---

## 2. 调研结论 → 设计映射

| RESEARCH 结论 | 设计落点 |
|---------------|----------|
| 触发成立：C 类 2 处 E2 复现（返回默认值 + 0 记录） | D3 以「日志 + 计数」双补，Step 9 把 E2 探针固化为单测（§4.2 T9/T10） |
| B 14 处有日志无计量 | D1/D2 只补计数，**不新增日志**（既有 `logger.error/warning` 已可诊断） |
| `agent_framework.py:1074` 为 `debug` 级（B−） | D2 唯一级别提升：`debug` → `warning`，文案逐字不变 |
| `filter/custom.py` 4 处 fail-open（R-P027-1） | D1 显式登记 fail-open 为**既有语义**，治理只加计量，不改返回 |
| A 类 2 处（`batch_backtest/engine.py`）为参照范式 | D4 结构化出口对齐该范式（`{"error": ...}` 同级加 `failure_counts`） |
| U-P024-4 不可合并 | 本设计**不触碰** `filter/` 类型面（无 pandas 3.x 桩改动） |

---

## 3. 决策详述

### D1 `filter/` 5 处：载体下沉基类（B 类）

**动机**：4 个 `custom.py` 子类 + `UniverseFilter` 都要计数，逐类复制 3 行是重复；`BaseFilter` 已是共同父类，天然载体。

```python
# filter/base.py — BaseFilter.__init__ 追加
self._failure_counts: dict[str, int] = {}

def _record_failure(self, key: str) -> None:
    """记录一次降级失败（只增不清；子类在 except 块首行调用）"""
    self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

def get_failure_stats(self) -> dict[str, int]:
    """只读失败计量快照"""
    return dict(self._failure_counts)
```

接入点（每处**仅 1 行**，插在 `except Exception as e:` 之后、既有 `logger.error` 之前）：

| 位置 | 键 | 保留行为 |
|------|----|----------|
| `filter/custom.py:71`（`CustomFunctionFilter.build_mask`） | `custom_function` | `logger.error` + fail-open 全 `True` DataFrame |
| `filter/custom.py:141`（`ExpressionFilter.build_mask`） | `expression` | 同上 |
| `filter/custom.py:269`（`DynamicFilter.build_mask`） | `dynamic` | 同上 |
| `filter/custom.py:327`（`ConditionalFilter.build_mask`） | `conditional` | 同上 |
| `filter/universe_filter_clean.py:371`（`_build_custom_masks`） | `f"custom_mask_build:{filter_name}"` | `logger.error`，无降级返回 |

`UniverseFilter` 不继承 `BaseFilter`，自带同构三件套（`__init__` 计数、`_record_failure`、`get_failure_stats`）；`build_masks()` 入口 `self._failure_counts.clear()`（D6）。

**R-P027-1 裁决**：fail-open 是 `filter/` 既有产品语义（自定义过滤失败不应中断回测），本批**只登记不修改**；计量让「静默降级」变为可观测，语义面零变更。

### D2 `agents/` 9 处：逐类实例计数器（B 类）

统一形态：`__init__` 增 `self._failure_counts: dict[str, int] = {}`，except 块首行 `self._failure_counts[KEY] = self._failure_counts.get(KEY, 0) + 1`。

| 位置（类.方法） | 键 | 备注 |
|-----------------|----|------|
| `agent_framework.py:924`（`ResearchTeamAgent._init_research_team`） | `rotation_analyzer_init` | 保留 `self.rotation_analyzer = None` |
| `agent_framework.py:1074`（`ResearchTeamAgent.generate_signals`） | `research_team_analysis` | **`logger.debug` → `logger.warning`**，文案逐字不变（O-S2-P027-2 裁决） |
| `auto_parameter_optimizer.py:807`（`AutoOptimizedFundManager.make_decision_with_regularization`） | `decision_making` | 保留 `logger.warning` |
| `guru_agent_v2.py:72`（`GuruDataLoader._load_all`） | `guru_load` | 新增 `get_failure_stats()` |
| `guru_agent_v2.py:491`（`GuruAgentV2.create_all_gurus`，classmethod） | `guru_create` | **类级** `_create_failure_counts`，调用入口 `clear()` |
| `multi_strategy_engine.py:148`（`StrategyEngine.run` 日循环） | `daily_process` | 保留 `continue` |
| `multi_strategy_engine.py:233`（`_execute_directional_rebalance`） | `directional_optimize` | 保留 `return` |
| `multi_strategy_engine.py:290`（`_execute_neutral_rebalance`） | `neutral_optimize` | 保留 `return` |
| `research_team_v2.py:825`（`FundManager.make_decision`） | `role_analysis` | 保留 `logger.warning` |

`GuruAgentV2` 是唯一无实例载体的点（`classmethod` 工厂），设计为**类级**计数器并新增 `get_creation_failure_stats()`；`create_all_gurus` 入口 `cls._create_failure_counts.clear()`，避免多次调用累加污染（R-P027-4）。

**O-S2-P027-2 裁决**：`§4「不改文案」` 与 `§7.2 级别提升` 不冲突——本批允许**日志级别提升**（`debug` 在默认 WARNING 阈值下不可见，等同静默），**禁止**文案文本与返回值语义变更；仅 `:1074` 一处行使该许可。

### D3 C 类 2 处：补日志 + 补计量（静默 → 显形）

```python
# strategy_evaluation/stats.py — calculate_half_life 的 except
except Exception as e:
    self._failure_counts["half_life"] = self._failure_counts.get("half_life", 0) + 1
    logger.warning("IC 半衰期计算失败（返回 NaN）: %s", e, exc_info=True)
    return np.nan
```

```python
# agents/assumption_monitor.py — _kpss_test 的 except
except Exception as e:
    self._failure_counts["kpss_test"] = self._failure_counts.get("kpss_test", 0) + 1
    logger.warning("KPSS 检验失败（返回乐观默认值 0.0/1.0）: %s", e, exc_info=True)
    return 0.0, 1.0
```

两个类各自 `__init__` 增 `self._failure_counts: dict[str, int] = {}` 与 `get_failure_stats()`。

**关键区分（防误判）**：`calculate_half_life` 的上游 3 处合法早退（L124 样本 <10、L131 lag <5、L136 `rho` 越界）**不计入**；只有 `except` 路径计数。Step 9 断言「早退场景计数 = 0、异常场景计数 = 1」，从而让「合法无值」与「计算失败」在计量层可区分（RESEARCH §5 指出的可观测性缺口）。

### D4 结构化出口（对齐 A 类范式）

| 载体 | 形式 | 新增内容 |
|------|------|----------|
| `ResearchTeamAgent.get_performance_summary()` | 追加键 | `"failure_counts": self.get_failure_stats()` |
| `StrategyEngine.run()` 返回值 | 追加键 | `"failure_counts": ...`（`run` 末尾写入，不改 `_generate_results` 签名） |
| `FundManager.get_team_report()` | 追加键 | `"failure_counts": ...` |
| `AutoOptimizedFundManager.get_optimization_report()` | 追加键 | `"failure_counts": ...` |
| `FactorStatsCalculator.calculate_all_stats()` | 追加键 | `"failure_counts": ...` |
| `GuruDataLoader` | 新方法 | `get_failure_stats() -> dict[str, int]` |
| `GuruAgentV2` | 新类方法 | `get_creation_failure_stats() -> dict[str, int]` |
| `BaseFilter` | 新方法 | `get_failure_stats()`（4 子类继承） |
| `UniverseFilter` | 新方法 | `get_failure_stats()` |
| `ReturnDistributionMonitor` | 新方法 | `get_failure_stats()` |

已核查：仓库内无 `get_performance_summary` / `get_team_report` / `get_optimization_report` 的严格 schema 断言（`keys() ==` / 全等），追加键安全。

### D5 零改动清单（6 处）

| 位置 | 分类 | 理由 |
|------|------|------|
| `batch_backtest/engine.py:107` / `:167` | A | 已具备 `logger.error` + `results[key] = {"error": str(e)}` |
| `agent_framework.py:1529` | E | `__main__` 入口 `print` + `traceback` |
| `scripts/fetch_universe.py:100` / `:118` | E | 脚本入口，`print` + 回退指引 |
| `cli.py:136` | E | 进程边界 `print` + `sys.exit(1)` |

### D6 计数生命周期

| 载体 | 生命周期 | 清零点 |
|------|----------|--------|
| `StrategyEngine` | 单次 `run()` | `run()` 入口 |
| `UniverseFilter` | 单次 `build_masks()` | `build_masks()` 入口 |
| `GuruAgentV2`（类级） | 单次 `create_all_gurus()` | 方法入口 |
| 其余 7 个实例载体 | 实例生命周期累计 | 不清零 |

清零仅为防批量重入累积，不改变既有行为；计数器写入均在单线程路径（引擎主循环 / 过滤器构建），不加锁（与 P-026 D7 一致，避免过度设计）。

### D7 文案与异常传播约定

1. **不新增 `raise`**，不改 `except Exception` 捕获类型与范围。
2. 既有 `logger.error/warning` 文案**逐字不变**；仅 `agent_framework.py:1074` 提升级别。
3. 新增 warning 仅 2 条（D3），均带 `exc_info=True`；不向既有 B 类 error 追加 `exc_info`（保持 P-026 口径：`exc_info` 增量只出现在 C 类显形处）。
4. 返回值语义零变更：fail-open 全 `True` 掩码保留、`np.nan` 保留、`(0.0, 1.0)` 保留、`continue`/`return` 保留。

---

## 4. 实现规格

### 4.1 变更面（10 代码文件 + 1 测试）

| # | 文件 | 变更 |
|---|------|------|
| 1 | `filter/base.py` | `BaseFilter.__init__` + `_record_failure` + `get_failure_stats` |
| 2 | `filter/custom.py` | 4 处 except 各 +1 行 |
| 3 | `filter/universe_filter_clean.py` | `__init__` 计数三件套 + `build_masks` 清零 + L371 接入 |
| 4 | `agents/agent_framework.py` | `ResearchTeamAgent.__init__` 计数 + 2 处接入 + `get_performance_summary` 追加 |
| 5 | `agents/multi_strategy_engine.py` | `StrategyEngine.__init__` 计数 + `run` 清零/返回追加 + 3 处接入 |
| 6 | `agents/research_team_v2.py` | `FundManager.__init__` 计数 + 1 处接入 + `get_team_report` 追加 |
| 7 | `agents/auto_parameter_optimizer.py` | `AutoOptimizedFundManager.__init__` 计数 + 1 处接入 + `get_optimization_report` 追加 |
| 8 | `agents/guru_agent_v2.py` | 加载器实例计数 + 类级计数 + 2 处接入 + 2 个 getter |
| 9 | `agents/assumption_monitor.py` | `ReturnDistributionMonitor.__init__` 计数 + C 类显形 |
| 10 | `strategy_evaluation/stats.py` | `FactorStatsCalculator.__init__` 计数 + C 类显形 + `calculate_all_stats` 追加 |
| 11 | `tests/test_p027_silent_exception_governance.py` | 新增（12 函数 / 24 实例） |

零改动：`scripts/`、`batch_backtest/`、`cli.py`、`core/`、`pyproject.toml`。

### 4.2 测试规格（12 函数 / 24 实例，全部 `monkeypatch`）

| ID | 测试 | 实例 | 断言要点 |
|----|------|------|----------|
| T1 | `test_filter_failopen_counts`（参数化 5） | 5 | 注入异常 → 计数 = 1；返回仍为全 `True` DataFrame / 无降级返回 |
| T2 | `test_rotation_analyzer_init_failure` | 1 | `rotation_analyzer is None` + `{"rotation_analyzer_init": 1}` |
| T3 | `test_research_team_analysis_level` | 1 | `caplog` 捕获 **WARNING** 级（非 DEBUG）+ 计数 1 + 该股被跳过 |
| T4 | `test_strategy_engine_failure_counts`（参数化 3） | 3 | 三个键分别计数；`run()` 返回值含 `failure_counts` |
| T5 | `test_fund_manager_role_analysis` | 1 | 角色异常 → 计数 1，其余角色正常参与投票 |
| T6 | `test_optimized_fund_manager_decision` | 1 | 计数 1 + `get_optimization_report()["failure_counts"]` |
| T7 | `test_guru_loader_load_failure` | 1 | 坏 JSON → 计数 1，加载器仍可用 |
| T8 | `test_guru_create_all_failures`（含 fixture 重置） | 1 | 类级计数 1；再次调用不累加（清零生效） |
| T9 | `test_half_life_exception_vs_early_exit`（参数化 2） | 2 | 异常 → `nan` + 计数 1；样本不足 → `nan` + 计数 **0** |
| T10 | `test_kpss_exception` | 1 | `(0.0, 1.0)` + 计数 1 + 1 条 WARNING |
| T11 | `test_structured_exits`（参数化 6） | 6 | 6 个载体均含 `failure_counts` 且为 `dict` |
| T12 | `test_return_semantics_unchanged` | 1 | 失败路径返回值类型/值域与改前一致（防语义漂移） |

### 4.3 新增文案（逐条，唯一允许的文本增量）

| 位置 | 级别 | 文案 |
|------|------|------|
| `strategy_evaluation/stats.py:139` | WARNING | `IC 半衰期计算失败（返回 NaN）: %s` |
| `agents/assumption_monitor.py:201` | WARNING | `KPSS 检验失败（返回乐观默认值 0.0/1.0）: %s` |

`agent_framework.py:1075` 文案保持 `投研团队分析{stock}失败: {e}` 不变，仅级别 `debug` → `warning`。

---

## 5. 不变式

| ID | 不变式 | 验证方式 |
|----|--------|----------|
| I1 | 治理范围内 `except Exception` 计数仍为 **22** | `Grep -c` 七单元合计 |
| I2 | 零新增 `raise` / 零 fail-fast | `git diff` 关键词扫描 |
| I3 | 返回值语义零变更（类型 + 值域） | T1/T9/T10/T12 |
| I4 | E 类 4 处 + A 类 2 处零改动 | `git diff --stat` 不含 `scripts/`、`batch_backtest/`、`cli.py` |
| I5 | 既有公开方法签名不变（仅新增方法与 dict 键） | AST 比对 / E3 抽验 |
| I6 | 既有日志文案逐字不变 | `git diff` 人工核 + E4 关键词扫描 |
| I7 | golden G1-G7 零重录 | `pytest tests/ -k golden` |
| I8 | 测试总数 ≥ **687 + 24 = 711** | `pytest -q` 汇总行 |

---

## 6. 验证契约

**Step 3 实测基线（HEAD `ad04dfe`，Python312）**：`pytest` **687 passed**（114.12s）/ `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error** / `black --check core tests` **116 unchanged**。目标态：**711 passed** / 37 / 116。

```powershell
# 1) 新增测试（红 → 绿）
$py -m pytest tests/test_p027_silent_exception_governance.py -q

# 2) 全量门禁
$env:MPLBACKEND="Agg"; $py -m pytest -q
$py -m mypy --explicit-package-bases --check-untyped-defs core
$py -m black --check core tests

# 3) 静态不变式（I1/I4）
#    七单元 except Exception 合计 = 22；scripts/batch_backtest/cli.py 零 diff

# 4) 类型面抽查（非门禁，仅登记基线差异）
$py -m mypy --explicit-package-bases filter strategy_evaluation

# 5) golden
$py -m pytest tests -q -k golden
```

Step 9 要求：E2 探针（`%TEMP%\p027_probe.py`）的能力**固化为 T9/T10**，此后不再依赖仓库外脚本。

---

## 7. 风险登记

| ID | 级别 | 风险 | 处置 |
|----|------|------|------|
| R-P027-1 | 设计约束 | fail-open 属既有语义，误改会改变回测结果 | D1 明示「只加计量」；I3 + T1 双保险 |
| R-P027-2 | 设计约束 | 新计量字段与既有 `*_errors` 混淆 | 统一 `_failure_counts` / `get_failure_stats()` / `failure_counts` 键名 |
| R-P027-3 | 测试约束 | mock 混用导致注入不可控 | 全部 `monkeypatch` fixture，禁 `unittest.mock` |
| R-P027-4 | 新增 | `GuruAgentV2` 类级计数器跨调用污染 | `create_all_gurus` 入口 `clear()` + T8 断言二次调用不累加 |
| R-P027-5 | 新增 | 递归/嵌套调用下计数可能重复累加 | 计量点均位于末级 handler（无嵌套 except 路径），E3 抽验确认 |
| O-S2-P027-1 | 观察 | 静态判据「无降级说明」存在注释载体 | 判据口径澄清为「无日志、无计数、无返回说明（注释/日志/文档任一载体）」，C 类 2 处三者皆无，结论不受影响（不改 Step 1 文档正文） |
| O-S2-P027-2 | 观察 | 「不改文案」与「级别提升」口径张力 | D2/D7 裁决：允许级别提升、禁止文本与语义变更，仅 `:1074` 一处 |

---

## 8. 回退点

| 批次建议 | 提交单元 | 可独立回退 |
|----------|----------|-----------|
| B1 | `filter/`（3 文件）+ T1 | 是 |
| B2 | `agents/` 计量（6 文件，不含 C 类显形）+ T2-T8/T11 | 是 |
| B3 | C 类显形（`stats.py` + `assumption_monitor.py`）+ T9/T10/T12 | 是 |
| B4 | 文档与计数回填（PROGRESS / IMPL / CHECKLIST） | 是 |

分批顺序保证「补计量」与「补日志」可分别验证、分别回退。

---

## 9. 设计期发现

1. `strategy_evaluation/stats.py` 的 `calculate_all_stats()` 是唯一「返回 dict 且被外部消费」的出口，追加键安全（仓库内无严格 schema 断言）。
2. `filter/custom.py` 实际为 5 个过滤类、仅 4 处 except（`MultiConditionFilter` 无 except 块）——RESEARCH §3 清单准确，无需订正。
3. `multi_strategy_engine.py` 3 处 except 全部位于 `StrategyEngine`（`MultiStrategyEngine` 无 except），与 §3 归属一致。
4. `agent_framework.py:1529` 位于模块级 `main()`（非类方法），确属 E 类进程边界。
5. `GuruAgentV2.create_all_gurus` 为 `classmethod`，是 22 处中唯一无实例载体的点，需类级计数器（R-P027-4）。

---

## 10. 结论

- 覆盖 **16 处计量 + 6 处零改动 = 22 处**，与 Step 1 清单一一对应，无遗漏无越界。
- 治理手段最小化：B 类只补计数（1 行/处），C 类补「日志 + 计数」（2 行/处），无 fail-fast、无返回值变更、无既有文案改写。
- 所有决策项（R-P027-1~3、O-S2-P027-1/2）已在本文件裁决，无遗留待议项。
- 变更面 10 代码文件 + 1 测试，T1 档位内；分 4 个可独立回退的提交单元。
- **下一 Step：Step 4 独立 Review**（异构基座复核本设计：计量点覆盖、语义零变更、测试可红可绿）。
