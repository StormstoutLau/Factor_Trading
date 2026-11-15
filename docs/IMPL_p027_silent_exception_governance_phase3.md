# IMPL：P-027 静默失败治理第三批（core 外 22 处 except 分级显形）

> **批次**: P-027 · **T1**（`agents/` / `filter/` / `strategy_evaluation/`；零 fail-fast、零返回值语义变更）
> **上游**: [DESIGN_p027](DESIGN_p027_silent_exception_governance_phase3.md)（D1-D7 / I1-I8 / §4 实现规格 / §7 风险 / §8 回退点 / §11 Step 4 独立 Review pass）
> **状态**: **Step 5 实施文档完稿**——本文为「实施规格」，代码与门禁结果待 Step 9 TDD 回填（RULE-1：不预填实测）
> **代码证据时点**: HEAD `6d3e0b7`（2026-11-15，工作区干净）；§4 全部锚点为**实施前行号**，实施后行号漂移属预期

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（代码） | `filter/base.py` / `filter/custom.py` / `filter/universe_filter_clean.py` / `agents/agent_framework.py` / `agents/multi_strategy_engine.py` / `agents/research_team_v2.py` / `agents/auto_parameter_optimizer.py` / `agents/guru_agent_v2.py` / `agents/assumption_monitor.py` / `strategy_evaluation/stats.py`（**10 个，与 DESIGN §4.1 一致**） |
| 变更文件（测试/文档） | `tests/test_p027_silent_exception_governance.py`（新增）/ 本文件 / `docs/PROGRESS.md` / `CHANGELOG.md` |
| 零改动面 | `scripts/fetch_universe.py`（E 类 2 处）/ `batch_backtest/engine.py`（A 类 2 处）/ `cli.py`（E 类 1 处）/ `agents/agent_framework.py:1529`（E 类 1 处）/ `core/` / `pyproject.toml` / `.github/` / `tests/golden/*.json` |
| 行为变更 | **仅可观测性增强**：16 处补计量（B 14 + C 2）、2 处补 warning 日志、1 处日志级别 `debug`→`warning`；**零 fail-fast、零返回值语义变更、零既有文案改写** |
| 门禁口径 | `MPLBACKEND=Agg` + Python312 `pytest -q`：**687 → 711**（+24 实例）；`mypy --explicit-package-bases --check-untyped-defs core`：**37 files 0 error**（code 面不含 `core/`，应保持 37）；`black --check core tests`：**116 → 117**（新增测试文件 1）；golden G1-G7 零重录 |

**不可越界的四条设计前提**：

1. `filter/` 5 处 **fail-open 保留**（R-P027-1）：只加计量，返回的全 `True` 掩码不动。
2. `agent_framework.py:1075` 文案 `投研团队分析{stock}失败: {e}` **逐字不变**，仅 `logger.debug` → `logger.warning`。
3. `GuruAgentV2.create_all_gurus` 为 `classmethod`，用**类级**计数器（22 处中唯一无实例载体的点）。
4. `agent_framework.py:336` 存在**另一个同名** `get_performance_summary`（`BaseAgent`）——本批只改 `:1138`（`ResearchTeamAgent` 覆写），勿误改。

---

## 2. 任务拆解

| ID | 批次 | 任务 | 对应 | 产出 |
|----|------|------|------|------|
| **B1** | 代码 | `filter/base.py` 三件套下沉；`filter/custom.py` 4 处各 +1 行；`filter/universe_filter_clean.py` 三件套 + 清零 + 1 处接入 | D1 / D6 | 3 文件 |
| **B1t** | 测试 | T1（参数化 5 例） | V1 | 5 items |
| **B2** | 代码 | `agents/` 6 文件：6 类实例计数器 + 6 处接入 + `create_all_gurus` 类级计数 + 5 个 dict 出口/新 getter | D2 / D4 / D6 | 6 文件 |
| **B2t** | 测试 | T2-T8 / T11（1+1+3+1+1+1+1+6 = 15 items） | V2-V4 | 15 items |
| **B3** | 代码 | `strategy_evaluation/stats.py` + `agents/assumption_monitor.py`：C 类「日志 + 计量」双补 | D3 | 2 文件 |
| **B3t** | 测试 | T9（参数化 2）/ T10 / T12 | V5 | 4 items |
| **B4** | 文档 | 门禁回归 + 本文件实测回填 + `PROGRESS` §3.32 + `CHANGELOG` | — | docs |

**计数口径**：B1 计量 5 处（D1 5）+ B2 计量 9 处（D2 9）+ B3 计量 2 处（D3 2）= **16 计量**；E 4 + A 2 = **6 零改动**；合计 **22**，与 RESEARCH §3 清单一一对应。

---

## 3. 实施顺序与依赖

```text
B1（filter/ 载体 + 4 接入）─→ B1t（T1，红→绿）
B2（agents/ 计量）         ─→ B2t（T2-T8/T11，红→绿）
B3（C 类显形）             ─→ B3t（T9/T10/T12，红→绿）
B1t + B2t + B3t ─→ B4（全量门禁 + 文档回填）
```

- **B1 是 B2 的形态基准**：`_record_failure(key)` / `get_failure_stats()` 命名先在 `filter/` 落地，`agents/` 6 类按同一形态复制（**不抽公共 mixin**——跨层依赖会污染 `agents/` 对 `filter/` 的引用，且仅 3 行/类，属过度设计）。
- **B2 内 `GuruDataLoader` 顺序敏感**（见 §7 A1）：计数初始化必须早于 `self._load_all()`。
- **B3 与 B1/B2 无代码依赖**，仅测试共用 `monkeypatch` 风格；放最后可让「补计量」与「补日志」的红绿证据互不干扰。
- **每批独立提交**，对应 DESIGN §8 的回退单元；便于逐批红绿验证与分别回退。

---

## 4. 精确变更规格

> 全部锚点为实施前 HEAD `6d3e0b7` 行号；「+N」为净新增行数估算，实测以 `git diff --numstat` 为准（偏差按 P-026 惯例登记 F-I 项）。

### 4.1 `filter/base.py`（+9）

| 锚点 | 变更 |
|------|------|
| L44-L49 `BaseFilter.__init__` | L49 `self._data_manager = None` 之后追加 `self._failure_counts: dict[str, int] = {}` |
| L112-L115（`reset` 之前） | 新增 `_record_failure(self, key: str) -> None`：`self._failure_counts[key] = self._failure_counts.get(key, 0) + 1` |
| 紧随其后 | 新增 `get_failure_stats(self) -> dict[str, int]`：`return dict(self._failure_counts)`（只读拷贝，防外部改写） |

```python
    def _record_failure(self, key: str) -> None:
        """记录一次降级失败（只增不清；子类在 except 块首行调用）"""
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

    def get_failure_stats(self) -> dict[str, int]:
        """只读失败计量快照"""
        return dict(self._failure_counts)
```

**继承安全已实证**：`CompositeFilter.__init__`（L169）与 `custom.py` 四子类 `__init__`（L43 / L99 / L242 / L297）**全部显式调用 `super().__init__(config)`** → 下沉属性无 `AttributeError` 风险（Step 4 §11.1 关键疑点已排除，本 IMPL 二次逐行复核）。`MultiConditionFilter` 无 `__init__` 覆写，自动继承。

### 4.2 `filter/custom.py`（+4，每处 1 行）

| 锚点 | 插入行 | 保留行为 |
|------|--------|----------|
| L71 `except Exception as e:` | `self._record_failure("custom_function")` | L72 `logger.error` + L74 全 `True` DataFrame |
| L141 `except Exception as e:` | `self._record_failure("expression")` | L142 `logger.error` + L143 全 `True` DataFrame |
| L269 `except Exception as e:` | `self._record_failure("dynamic")` | L270 `logger.error` + L271 全 `True` DataFrame |
| L327 `except Exception as e:` | `self._record_failure("conditional")` | L328 `logger.error` + L329 全 `True` DataFrame |

插入位置：`except` 行**之后、`logger.error` 之前**（与 DESIGN D1 表一致）。

### 4.3 `filter/universe_filter_clean.py`（+12）

| 锚点 | 变更 |
|------|------|
| L96 `__init__` | L104 `self.cfg = config` 之后追加 `self._failure_counts: dict[str, int] = {}`（`UniverseFilter` 非 `BaseFilter` 子类，自带三件套） |
| L130 `build_masks` | L132 `logger.info` 之后追加 `self._failure_counts.clear()`（D6 批量入口清零） |
| L371 `except Exception as e:` | 追加 `self._record_failure(f"custom_mask_build:{filter_name}")`；保留 L372 `logger.error` |
| 类内新增 | `_record_failure` / `get_failure_stats`（形态同 §4.1） |

**键名带变量**：`f"custom_mask_build:{filter_name}"` 使不同自定义过滤器的失败可分辨（DESIGN D1 表已定）。

### 4.4 `agents/agent_framework.py`（+10）

| 锚点 | 变更 |
|------|------|
| L804 `ResearchTeamAgent.__init__` | 追加 `self._failure_counts: dict[str, int] = {}`（放在首个属性赋值后即可，无顺序约束） |
| L924 `except Exception as e:` | 追加 `self._record_failure("rotation_analyzer_init")`；保留 L925 `logger.warning` + L926 `self.rotation_analyzer = None` |
| L1074 `except Exception as e:` | 追加 `self._record_failure("research_team_analysis")`；**L1075 `logger.debug` → `logger.warning`**（文案逐字不变）；保留 L1076 `continue` |
| L1138 `get_performance_summary` | 返回 dict 追加 `"failure_counts": self.get_failure_stats()` |
| 类内新增 | `_record_failure` / `get_failure_stats`（形态同 §4.1） |

**禁止触碰**：L336 `BaseAgent.get_performance_summary`（另一同名方法，见 §1 第 4 条）。

### 4.5 `agents/multi_strategy_engine.py`（+12）

| 锚点 | 变更 |
|------|------|
| L69 `StrategyEngine.__init__` | 追加 `self._failure_counts: dict[str, int] = {}` |
| L145 `run` 主循环之前 | 追加 `self._failure_counts.clear()`（D6） |
| L148 `except Exception as e:` | 追加 `self._record_failure("daily_process")`；保留 L149 `logger.error` + L150 `continue` |
| L233 `except Exception as e:` | 追加 `self._record_failure("directional_optimize")`；保留既有 `return` |
| L290 `except Exception as e:` | 追加 `self._record_failure("neutral_optimize")`；保留既有 `return` |
| L159 `return self._generate_results()` | 改为三行：`result = self._generate_results()` / `result["failure_counts"] = self.get_failure_stats()` / `return result`（**不改 `_generate_results` 签名**） |
| 类内新增 | `_record_failure` / `get_failure_stats` |

**归属核实**：3 处 except 全部位于 `StrategyEngine`（L62-L486）；`MultiStrategyEngine`（L487 起）无 except，不在范围（DESIGN §9.3）。

### 4.6 `agents/research_team_v2.py`（+5）

| 锚点 | 变更 |
|------|------|
| L753 `FundManager.__init__` | 追加 `self._failure_counts: dict[str, int] = {}`（L59/L172/... 的其他 `__init__` 属其他类，勿动） |
| L825 `except Exception as e:` | 追加 `self._record_failure("role_analysis")`；保留既有 `logger.warning` 与后续流程 |
| L944 `get_team_report` | 追加 `"failure_counts": self.get_failure_stats()` |
| 类内新增 | `_record_failure` / `get_failure_stats` |

**R-P027-5 验证结论的落地**：L825 为**内层** handler，吞掉异常后不冒泡至 `agent_framework.py:1074`（外层）；两层捕获独立异常源，计数不重复。T5（内层）与 T12（外层）须分别构造触发用例。

### 4.7 `agents/auto_parameter_optimizer.py`（+5）

| 锚点 | 变更 |
|------|------|
| L723 `AutoOptimizedFundManager.__init__` | 追加 `self._failure_counts: dict[str, int] = {}` |
| L807 `except Exception as e:` | 追加 `self._record_failure("decision_making")`；保留既有 `logger.warning` |
| L844 `get_optimization_report` | 追加 `"failure_counts": self.get_failure_stats()` |
| 类内新增 | `_record_failure` / `get_failure_stats` |

### 4.8 `agents/guru_agent_v2.py`（+14）

| 锚点 | 变更 |
|------|------|
| L52 `GuruDataLoader.__init__` | **必须在 L55 `self._load_all()` 之前**追加 `self._failure_counts: dict[str, int] = {}`（顺序敏感，见 §7 A1） |
| L72 `except Exception as e:` | 追加 `self._record_failure("guru_load")`；保留 L73 `logger.error` |
| L75 附近 | 新增 `get_failure_stats()`（该类的唯一 dict 出口，无既有报告方法） |
| L123 `GuruAgentV2` 类体 | 新增类属性 `_create_failure_counts: dict[str, int] = {}`（类级，不影响实例） |
| L484 `create_all_gurus` 入口 | `loader = GuruDataLoader(data_dir)` 之前追加 `cls._create_failure_counts.clear()`（D6 / R-P027-4） |
| L491 `except Exception as e:` | 追加 `cls._create_failure_counts["guru_create"] = cls._create_failure_counts.get("guru_create", 0) + 1`；保留 L492 `logger.error` |
| 类内新增 | `@classmethod get_creation_failure_stats() -> dict[str, int]`（返回 `dict(cls._create_failure_counts)`） |

**类级而非实例级的理由**：`create_all_gurus` 为 `@classmethod`，无实例载体；计数的是「工厂创建失败」，与具体 Agent 实例无关。

### 4.9 `agents/assumption_monitor.py`（+6，C 类显形）

| 锚点 | 变更 |
|------|------|
| L90-L107 `ReturnDistributionMonitor.__init__` | L107 `self.kpss_threshold = kpss_threshold` 之后追加 `self._failure_counts: dict[str, int] = {}` |
| L201-L202 `_kpss_test` | `except Exception:` → `except Exception as e:`；插入计数 + 新增 warning；L202 `return 0.0, 1.0` 保留 |
| 类内新增 | `get_failure_stats()` |

```python
        except Exception as e:
            self._failure_counts["kpss_test"] = self._failure_counts.get("kpss_test", 0) + 1
            logger.warning("KPSS 检验失败（返回乐观默认值 0.0/1.0）: %s", e, exc_info=True)
            return 0.0, 1.0
```

**必须保留的「合法早退」**：L188-L189 `if s2 < 1e-12: return 0.0, 1.0` —— 与异常路径**返回值完全相同**，全靠计数区分（早退 0 / 异常 1）。T10 需同时断言两条路径。

### 4.10 `strategy_evaluation/stats.py`（+8，C 类显形）

| 锚点 | 变更 |
|------|------|
| L36-L44 `FactorStatsCalculator.__init__` | L44 `self.returns = returns_data` 之后追加 `self._failure_counts: dict[str, int] = {}` |
| L139-L140 `calculate_half_life` | `except Exception:` → `except Exception as e:`；插入计数 + 新增 warning；L140 `return np.nan` 保留 |
| L183-L190 `calculate_all_stats` | 返回 dict 追加 `"failure_counts": self.get_failure_stats()` |
| 类内新增 | `get_failure_stats()` |

```python
        except Exception as e:
            self._failure_counts["half_life"] = self._failure_counts.get("half_life", 0) + 1
            logger.warning("IC 半衰期计算失败（返回 NaN）: %s", e, exc_info=True)
            return np.nan
```

**必须保留的「合法早退」三处**：L124（样本 < 10）、L131（`len(ic_lag) < 5`）、L136（`rho` 越界）——均不计入（早退 0 / 异常 1）。T9 参数化 2 例即「异常」与「样本不足」两条路径。

> **注意**：L139 原为裸 `except Exception:`（无 `as e`）。改为 `as e` 不改变捕获范围，仅使日志可带异常信息；`exc_info=True` 与 P-026 的 C 类显形口径一致。

### 4.11 `tests/test_p027_silent_exception_governance.py`（新增）

单文件 12 个测试函数 / 24 实例，全部 `monkeypatch`，**禁 `unittest.mock`**（R-P027-3）。详见 §5。

---

## 5. 测试规格（12 函数 / 24 实例）

| ID | 测试函数 | 实例 | 注入方式（`monkeypatch`） | 断言要点 |
|----|----------|------|---------------------------|----------|
| T1 | `test_filter_failopen_counts` | 5 | patch 各自的过滤函数/表达式/eval 使其抛错 | 计数 = 1；返回值仍为全 `True` DataFrame（`UniverseFilter` 项断言无降级返回且计数键含 `filter_name`） |
| T2 | `test_rotation_analyzer_init_failure` | 1 | patch `IndustryRotationAnalyzer.__init__` | `rotation_analyzer is None` + `{"rotation_analyzer_init": 1}` |
| T3 | `test_research_team_analysis_level` | 1 | patch 单股分析路径抛错 + `caplog` | 捕获 **WARNING**（非 DEBUG）+ 文案含 `失败` + 计数 1 + 该股被跳过 |
| T4 | `test_strategy_engine_failure_counts` | 3 | 分别 patch 日处理 / 方向再平衡 / 中性再平衡 | 三个键各自为 1；`run()` 返回值含 `failure_counts` 且为 `dict` |
| T5 | `test_fund_manager_role_analysis` | 1 | patch 单个 role 的分析方法 | 计数 1，其余角色正常参与投票（决策仍产出） |
| T6 | `test_optimized_fund_manager_decision` | 1 | patch 决策路径抛错 | 计数 1 + `get_optimization_report()["failure_counts"]["decision_making"] == 1` |
| T7 | `test_guru_loader_load_failure` | 1 | 临时目录写坏 JSON | 计数 1，加载器仍可用（`get()` 返回 `None` 不抛） |
| T8 | `test_guru_create_all_failures` | 1 | patch `GuruAgentV2.__init__` 抛错 + fixture 前置 `clear()` | 类级计数 1；**连续两次调用不累加**（清零生效） |
| T9 | `test_half_life_exception_vs_early_exit` | 2 | ① patch `np.corrcoef` 抛错 ② 构造 < 10 样本 | ① `nan` + 计数 1 ② `nan` + 计数 **0** |
| T10 | `test_kpss_exception` | 1 | patch 计算路径抛错 + `caplog` | `(0.0, 1.0)` + 计数 1 + 1 条 WARNING |
| T11 | `test_structured_exits` | 6 | 直接构造 6 个载体 | ① `ResearchTeamAgent.get_performance_summary()` ② `StrategyEngine.run()` ③ `FundManager.get_team_report()` ④ `AutoOptimizedFundManager.get_optimization_report()` ⑤ `FactorStatsCalculator.calculate_all_stats()` ⑥ `GuruDataLoader.get_failure_stats()`——均含 `failure_counts` 且为 `dict` |
| T12 | `test_return_semantics_unchanged` | 1 | 同时触发内层（`FundManager`）与外层（`ResearchTeamAgent`）失败 | 失败路径返回值类型/值域与改前一致；两层计数各 +1、**互不重复**（R-P027-5） |

**红绿纪律**：每批先跑新增用例取红态（应为「属性不存在 / 键缺失 / 级别不符」类失败），再补实现取绿；红态证据记入 §6 与 CHECKLIST。

---

## 6. 门禁口径

| 门禁 | 命令 | 预期（待 Step 9 实测） |
|------|------|------------------------|
| 新增测试 | `$py -m pytest tests/test_p027_silent_exception_governance.py -q` | 红 → **24 passed** |
| 全量测试 | `$env:MPLBACKEND="Agg"; $py -m pytest -q` | **711 passed**（687 基线 + 24） |
| 类型 | `$py -m mypy --explicit-package-bases --check-untyped-defs core` | **37 files 0 error**（`core/` 零改动） |
| 形态 | `$py -m black --check core tests` | **117 unchanged**（116 + 新测试文件 1） |
| 静态不变式 I1 | 七单元 `except Exception` 计数 | 合计仍 **22** |
| 静态不变式 I4 | `git diff --stat` | 不含 `scripts/` / `batch_backtest/` / `cli.py` |
| golden | `$py -m pytest tests -q -k golden` | G1-G7 全通过，`tests/golden/*.json` 零变更 |

`$py` = `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（默认 `python` 指向 Anaconda 3.13，勿用）。

**Step 9 要求**：`%TEMP%\p027_probe.py`（E2 探针）的能力固化为 T9/T10 之后即可废弃，此后不依赖仓库外脚本（DESIGN §6）。

---

## 7. 实施注意项（顺序敏感与易误改点）

| ID | 级别 | 注意项 | 处置 |
|----|------|--------|------|
| **A1** | **P2** | `GuruDataLoader.__init__` 在 L55 就调用 `self._load_all()`；若计数初始化写在 L55 之后，`_load_all` 的 `except` 分支将 `AttributeError`（异常被自身 `except` 吞掉后二次失败） | 计数初始化**必须**插在 L54-L55 之间；T7 以坏 JSON 用例兜底 |
| **A2** | P2 | `agent_framework.py` 有两个 `get_performance_summary`（L336 `BaseAgent` / L1138 `ResearchTeamAgent`） | 只改 L1138；改后用 `grep -n` 复核仅一处新增 `failure_counts` |
| **A3** | P2 | `research_team_v2.py` 有 8 个 `__init__`（L59/L172/L357/L419/L472/L531/L583/L656/L753），只有 `FundManager`（L753）需要计数 | 按行号锚定，勿按「类名模糊匹配」批改 |
| **A4** | P3 | `_kpss_test` 的合法早退（L189）与异常兜底（L202）返回值完全相同 | 计数是唯一区分手段；T10 断言早退不计数 |
| **A5** | P3 | `calculate_half_life` 有 3 处合法早退（L124/L131/L136） | 只改 L139 的 `except`，早退分支一行不动；T9 覆盖 |
| **A6** | P3 | `StrategyEngine.run()` 的返回由 `_generate_results()` 直接产出 | 改为「取 result → 追加键 → return」，不动 `_generate_results` 签名（DESIGN D4） |
| **A7** | P3 | `filter/` 四子类 except 均返回全 `True` 掩码 | 插入行必须在 `logger.error` **之前**、`return` **之前**，返回语句一字不动 |

---

## 8. 回退点

| 批 | 提交单元 | 文件 | 回退方式 |
|----|----------|------|----------|
| B1 | `filter/` 载体 + 4 接入 + T1 | `base.py` / `custom.py` / `universe_filter_clean.py` | 三文件 `git checkout <base> -- <file>`；`base.py` 回退后子类仅不再有计数器（无构造期依赖） |
| B2 | `agents/` 计量 + T2-T8/T11 | 6 文件 | 按文件回退；`failure_counts` 键为只增，消费方（报告出口）回退无破坏 |
| B3 | C 类显形 + T9/T10/T12 | `stats.py` / `assumption_monitor.py` | 两文件独立回退；回退后恢复「静默返回默认值」 |
| B4 | 文档回填 | 本文件 / `PROGRESS` / `CHANGELOG` | 直接 revert 文档提交 |

**全批回退**：`git revert <SHA>`（10 代码文件 + 1 测试文件），因分 4 个提交单元，可逐单元 revert。

---

## 9. 下一步

1. **Step 6 独立 Review**（异构基座 ≠ 本文作者）：核对 §4 锚点与 DESIGN §4.1 的 10 文件一一对应、接口签名可实现、计数口径 16+6=22、测试 24 实例可红可绿。
2. **Step 7 CHECKLIST**：按 T1-T12 + I1-I8 逐项落验收条件（实测列一律 `[待 Step 9]`）。
3. **Step 9 TDD**：按 B1 → B1t → B2 → B2t → B3 → B3t 逐批红绿，最后 B4 回填本文件 §6 实测列。
