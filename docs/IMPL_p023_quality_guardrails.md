# IMPL：P-023 质量护栏（F-A1 静默空回测 + U-006-R mypy 盲区）

> **批次**: P-023 · **T1**
> **上游**: [DESIGN_p023_quality_guardrails.md](DESIGN_p023_quality_guardrails.md)（D1-D6 / I1-I6 / §4 实现规格）
> **状态**: Step 5 完稿；**Step 6 Review 通过**（§6）
> **代码证据时点**: HEAD `c2a1918`

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件 | `core/engine_v2.py` / `core/data_v3.py` / `tests/test_p023_quality_guardrails.py`（新增） |
| 零改动面 | `setup()` 守卫 / 逐日循环与 `except Exception: continue` / `pyproject.toml` / `.github/` / `core/interfaces.py` / `core/factor.py` / `engine_v3_vector.py` |
| 行为变更 | **2 项**：`run()` 无信号 → `RuntimeError`；`_generate_results()` 零快照 → `RuntimeError`（CHANGELOG `Changed` 必披露） |
| 门禁口径 | `mypy --explicit-package-bases core` 不变（0）；盲区口径 `--check-untyped-defs` 由 4 → 0（不入 CI） |

---

## 2. 任务拆解

| ID | 任务 | 对应 | 产出 |
|----|------|------|------|
| **T-1** | B1：`run()` 信号就绪守卫 + T1/T2 测试 | D1 / V1 | 引擎 +6 行；测试 +2 项 |
| **T-2** | B2：`_generate_results()` 空快照守卫 + T3/T4 测试 | D2 / V1 | 引擎 +5 行；测试 +2 项 |
| **T-3** | B3：U-006-R 四项窄化（`_build_maps` / L224 `cast` / L293 别名） | D3 / D4 / V4 | data_v3 +3/−2；engine_v2 +5/−1 |
| **T-4** | B4：四文档落位 + PROGRESS/CHANGELOG + F-A1 来源订正 | D6 | docs |
| **T-5** | B5：CI 回收与回填 | — | docs |

---

## 3. 实施顺序与依赖

```text
T-1（B1）─→ T-2（B2）─→ T-3（B3）─→ T-4（B4）─→ T-5（B5）
```

- T-1 与 T-2 分两批：D1 是「信号未就绪」、D2 是「零快照」，红态可独立观测（T1 红 / T3 红）。
- T-3 必须后置：`engine_v2.py` 的 L224/L293 行号在 T-1/T-2 落位后会位移，先做窄化会二次对齐。
- T-3 与 T-1/T-2 可同提交？**否**——保持「行为变更」与「零行为窄化」两个提交边界清晰（回退粒度）。

---

## 4. 精确变更预案

### 4.1 T-1 `core/engine_v2.py`（D1）

插入位置：`run()` 内 `if self.dm is None: raise RuntimeError("请先调用setup()方法")` 之后。

```python
        if self._composite_signal is None:
            raise RuntimeError(
                "回测信号未就绪：注入 factor_pipeline/factor_combiner 的工作流"
                "需在 setup() 后设置 _composite_signal（或提供非空 factor_files）"
            )
```

### 4.2 T-2 `core/engine_v2.py`（D2）

原顺序：`snapshots = tracker.get_snapshots()` → `trades_df = executor.trade_log.get_trades_df()` → `output_dir = ...`

新顺序：`snapshots` → **守卫** → `trades_df` → `output_dir`。

```python
        snapshots = tracker.get_snapshots()
        if not snapshots:
            raise RuntimeError(
                "回测未产生任何组合快照，拒绝生成结果："
                "请检查交易日范围与信号就绪状态"
            )
        trades_df = executor.trade_log.get_trades_df()
```

### 4.3 T-3（D3 + D4）

**`core/data_v3.py::_build_maps`**：

```python
    def _build_maps(self):
        """构建日期/股票到索引的映射"""
        dates = self.dates
        stocks = self.stocks
        assert dates is not None and stocks is not None
        self.date_map = {date_str: i for i, date_str in enumerate(dates)}
        self.stock_map = {stock_code: i for i, stock_code in enumerate(stocks)}
```

**`core/engine_v2.py` 导入行**：`from typing import Any, Optional` → `from typing import Any, Optional, cast`

**L224**：

```python
            self.pipeline = FactorPipeline(cast(DataManager, self.dm), self.cfg.factor)
```

**L293**：

```python
        dm = self.dm
        assert dm is not None
        raw = dm.load_factor(fname)
```

> `DataManager` 已在 L22 导入（无需新增）。

### 4.4 新增测试文件

`tests/test_p023_quality_guardrails.py`，含 4 项（T1-T4），夹具独立复制自 `tests/test_rebalance_exits.py` 的 5 个 fake 组件（不改原文件）。

| 测试 | 夹具 | 期望 |
|------|------|------|
| **T1** `test_run_without_signal_raises` | 注入 pipeline+combiner、`factor_files=[]` | `setup()` OK；`run()` → `RuntimeError` match=`信号未就绪` |
| **T2** `test_run_after_manual_signal_injection` | 同 T1 + setup 后赋值 `_composite_signal` | `run()` 返回 dict |
| **T3** `test_generate_results_empty_snapshots_raises` | 同 T1 | `_generate_results()` → `RuntimeError` match=`快照` |
| **T4** `test_normal_injected_backtest_still_works` | 注入 + `factor_files=["dummy.pkl"]` | `run()` 返回 dict 且 `portfolio_value` 非空 |

**T2/T4 的 `run()` 需 patch `core.engine_v2.generate_report`**（与 `test_rebalance_exits.py` 同法），避免写图表 I/O。

---

## 5. fixture 表

| 组件 | 来源 | 说明 |
|------|------|------|
| `_FakeDataManager` | 复制 `test_rebalance_exits.py` L166-L187 | 4 天 × 4 股票恒定价 + 因子帧 |
| `_FakeUniverse` | 复制 L190-L215 | 全可交易掩码 |
| `_FakePipeline` | 复制 L218-L222 | 原样返回 |
| `_FakeCombiner` | 新增（`combine(self, factors)`） | 引擎不调用，仅满足注入类型 |
| `_Top2Optimizer` | 复制 L225-L234 | 取前 2 等权 |
| `_AlwaysTrigger` | 复制 L237-L239 | 每日触发 |
| `_build_config(tmpdir, factor_files)` | 参数化改造自 L242-L261 | 零成本 + daily + target_count=2 |

---

## 6. Step 6 Review（独立 pass）

> **执行方式**：IMPL 完稿后逐条核对设计对齐、版本存在性、签名可实现（RULE-1 时序独立；RULE-4 单 Agent）。

### 6.1 检查表

| # | 检查项 | 结论 |
|---|--------|------|
| 1 | 任务与设计一一对应 | ✅ T-1←D1、T-2←D2、T-3←D3+D4、T-4←D6；无设计外任务 |
| 2 | 依赖版本真实存在 | ✅ 零新增三方依赖；仅标准库 `typing.cast`（PEP 484，Python ≥3.5，本仓 requires-python ≥3.10） |
| 3 | stdlib API 下限 | ✅ `typing.cast` 自 3.5、`assert` / `RuntimeError` 全版本；无 3.12+ 专属 API |
| 4 | 签名可实现 | ✅ 不新增/修改任何公开签名（I5）；`cast` 与 `assert` 均不改运行时 |
| 5 | 低效操作排除 | ✅ D1/D2 为 O(1) 判空；D3 为字典推导前的一次性断言；无循环内新增开销 |
| 6 | 回退点 | ✅ DESIGN §8 三档（整体 / 行为守卫 / 窄化）与 §3 的提交边界一致 |
| 7 | 红态可观测 | ✅ T1（DID NOT RAISE）、T3（DID NOT RAISE）为真红；T2/T4 为对照绿（保护性）——符合 TDD 双要素「正例 + 边界」 |
| 8 | 导入副作用 | ✅ `cast` 加入现有 `typing` 导入行，无新增 import 语句、无循环依赖 |

### 6.2 发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S6-P023-1 | P3 | §4.3 初稿写「`DataManager` 已在 L22 导入（无需新增）」，但 `cast` 的导入行改动在初稿中未单列 diff | 已明确写出导入行前后形态 |

### 6.3 结论

**通过**——0 P1 / 0 P2 / 1 P3（已回写）；可进入 Step 7 验收清单。

---

## 7. Step 9 实施记录

### 7.1 提交链

| 批次 | 提交 | 内容 | numstat |
|------|------|------|---------|
| **B1-B3** | `a5b95bb` | `run()` 信号守卫 + `_generate_results` 空快照守卫 + U-006-R 四项窄化 + 4 项测试 | 3 文件 **+222/−5** |

> **合批说明**：B1/B2/B3 的引擎改动集中在同一文件（`core/engine_v2.py`）且行号相邻，交互式分块提交不可用；按 DESIGN §8 回退点，仍可「`git checkout <base> -- core/data_v3.py` + 手工撤销 engine_v2 两处窄化」单独回退盲区部分。红绿读数仍按三批分别取证（§7.2）。

### 7.2 F5 逐批红绿

| 批次 | 红（实现前） | 绿（实现后） |
|------|--------------|--------------|
| **B1** | `pytest tests/test_p023_quality_guardrails.py -q` → **1 failed, 1 passed**；`test_run_without_signal_raises` = `Failed: DID NOT RAISE <class 'RuntimeError'>`；捕获日志含 **4 条空消息 ERROR**（每日一条）+ `没有快照数据` WARNING×2 | **2 passed** |
| **B2** | 追加 T3/T4 后 → **1 failed, 3 passed**；`test_generate_results_empty_snapshots_raises` = `Failed: DID NOT RAISE <class 'RuntimeError'>`；捕获日志含 `没有快照数据，无法生成性能图表` + `月度收益热图` 两条 WARNING | **4 passed** |
| **B3** | `mypy --explicit-package-bases --check-untyped-defs core` → **exit 1，`Found 4 errors in 2 files (checked 36 source files)`** | **exit 0，`Success: no issues found in 36 source files`** |

### 7.3 V1-V7 实读

| ID | 命令 | 读数 |
|----|------|------|
| V1 | `pytest tests/test_p023_quality_guardrails.py -q` | **4 passed in 2.52s** |
| V2 | `pytest -q`（Agg，3.12.10） | **651 passed, 152 warnings in 39.91s** |
| V3 | `mypy --explicit-package-bases core` | **`Success: no issues found in 36 source files`**（exit 0） |
| V4 | `mypy --explicit-package-bases --check-untyped-defs core` | **`Success: no issues found in 36 source files`**（exit 0，由 4 清零） |
| V5 | `black --check core tests cli.py` | **113 files would be left unchanged** |
| V6 | `pytest tests/test_real_ashare_backtest.py tests/test_real_ashare_strict_validation.py -q` | **27 passed, 21 warnings in 9.13s** |
| V7 | `git diff --name-only -- pyproject.toml .github/ core/interfaces.py core/factor.py` | **空** |

### 7.4 探针读数（同 Step 1 探针复跑）

| 场景 | Step 1（修复前） | Step 9（修复后） |
|------|------------------|------------------|
| A 注入+空 factor_files | setup OK → run OK → snapshots=0 / trades=0 | setup OK → **run 抛 RuntimeError「信号未就绪」** |
| C 仅注入 pipeline | 同 A | 同 A（同守卫覆盖） |
| E setup 后直接 `_generate_results` | OK（返回空结果） | **抛 RuntimeError「快照」** |
| D 对照（非空 factor_files） | snapshots=5 / trades=8 | 不变（T4 覆盖） |

### 7.5 实施发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S9-P023-1** | P3 | D1/D2 落位后 `engine_v2.py` 行号由 L309→L309（D1 前）/ L1133→L1139（D2 前）；DESIGN/IMPL 中「L1139/L1140/L1142-L1143」为**落位前**坐标 | 本文 §7.3 不依赖行号；DESIGN §9.1 #9 已标「插入点」语义，Step 10 审计按 commit `a5b95bb` 复核实际行号 |
| **F-S9-P023-2** | 观察 | `test_run_after_manual_signal_injection` 的 `_FakeCombiner.combine` 未被引擎调用（引擎只经 `_composite_signal` 取信号），注入仅为满足构造 | 不改（与 `test_rebalance_exits` 的 fake 同构）；登记为本批测试夹具的已知冗余 |
| **环境** | 观察 | `MPLBACKEND=Agg` + 项目解释器 `Python312` 全部命令显式指定 | 沿用 P-021/P-022 纪律 |

