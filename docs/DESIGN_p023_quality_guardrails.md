# DESIGN：P-023 质量护栏（F-A1 静默空回测 + U-006-R mypy 盲区）

> **批次**: P-023 · **T1**
> **上游**: [RESEARCH_p023_quality_guardrails.md](RESEARCH_p023_quality_guardrails.md)（Step 2 通过；M-A 判定；F-A1 上调 P1）
> **状态**: Step 3 完稿
> **代码证据时点**: HEAD `c2a1918`

---

## 1. 决策总览

| ID | 决策项 | 决定 | 对应 |
|----|--------|------|------|
| **D1** | F-A1 主修位置 | **`run()` 入口**校验 `_composite_signal is None` → `RuntimeError`（setup 不校验） | P3/P6/P10 |
| **D2** | F-A1 补修 | **`_generate_results()` 空快照** → `RuntimeError` | P5/P9 |
| **D3** | U-006-R data_v3 两条 | `_build_maps()` 局部别名 + `assert` 双窄化（不改 `__init__` 注解） | P11①②/P13 |
| **D4** | U-006-R engine_v2 两条 | L224 `cast(DataManager, self.dm)`（零运行时）；L293 局部别名 + `assert` | P11③④/P12 |
| **D5** | 守卫开关 | **不新增配置开关**；不区分「注入式」与「文件式」的失败文案 | 范围控制 |
| **D6** | 范围边界 | 不改 `setup()` 守卫条件；不收窄 `except Exception: continue`；不动 `engine_v3_vector`；不改 CI mypy 命令 | P4/P10/U-P023-1/2 |

---

## 2. 调研结论 → 设计映射

| 调研结论 | 设计决策 | 引用 |
|----------|----------|------|
| `setup()` 后信号可由调用方手工注入（13 个既有用例） | D1 把校验放在 `run()` 而非 `setup()` | P3 / P10 |
| `_generate_results()` 只查 tracker/executor，零快照仍返回完整字典 | D2 补空快照守卫 | P5 / P9 |
| `run()` 逐日 catch-all 吞掉 `AssertionError`（空消息） | D1 在循环前 fail-fast，**不进入**逐日路径 | P4 / P6 |
| `FactorPipeline` 形参要求 `DataManager` 具体类且使用 `industry`/`mktcap` | D4 用 `cast`（E3：cast 无运行时检查），不改协议注解 | P12 |
| `DataLoaderV3.dates/stocks` 声明 Optional，`_build_maps` 为唯一 enumerate 点 | D3 局部别名 + assert（P-007 D4 先例） | P13 |

---

## 3. 决策详述

### D1 `run()` 信号就绪守卫

**位置**：`run()` 内 `if self.dm is None: raise RuntimeError("请先调用setup()方法")` **之后**、`t0 = time.perf_counter()` **之前**。

**代码形态**：

```python
    def run(self) -> dict[str, Any]:
        """运行回测"""
        if self.dm is None:
            raise RuntimeError("请先调用setup()方法")
        if self._composite_signal is None:
            raise RuntimeError(
                "回测信号未就绪：注入 factor_pipeline/factor_combiner 的工作流"
                "需在 setup() 后设置 _composite_signal（或提供非空 factor_files）"
            )
```

**理由**：
- P10 证明 13 个既有用例在 `setup()` 后、`run()` 前手工赋值 `_composite_signal`——**setup 时点必然为 None**，校验必须后移。
- `run()` 是「信号已就绪」的唯一充分时点；在此 fail-fast 使逐日 catch-all（P4）不再有吞错机会。
- `RuntimeError` 与 P-007 D3 同型：`setup()` 成功 = 状态已建立，但运行前置条件缺失 = 状态错误（非配置值非法，故不用 `ValueError`）。

**被拒方案**：

| 方案 | 否决理由 |
|------|----------|
| 在 `setup()` 末尾校验 | 13 个既有用例全破（P10），与 P-007 F-S9-1 裁决正面冲突 |
| 在 `_precompute_factors()` 内抛 | 与「注入路径不产信号」的合法语义冲突：注入式工作流本就不走该函数 |
| 仅 `logger.error` | 返回值仍为假成功（M-B 否决） |
| 收窄 `except Exception` | 改动面覆盖全部交易日路径，出界（U-P023-1） |

### D2 `_generate_results()` 空快照守卫

**位置**：`snapshots = tracker.get_snapshots()` 之后、`output_dir.mkdir` **之前**。

**代码形态**：

```python
        snapshots = tracker.get_snapshots()
        if not snapshots:
            raise RuntimeError(
                "回测未产生任何组合快照，拒绝生成结果："
                "请检查交易日范围与信号就绪状态"
            )
        trades_df = executor.trade_log.get_trades_df()
```

**理由**：
- P9 实测：`setup()` 后直接调 `_generate_results()` 不抛、返回完整字典 → 假成功。
- 零快照 ≈ 零交易日（快照逐日生成），故该守卫同时覆盖「空交易日集」与「绕过 run() 直接调私有方法」两形态（U-P023-3 统一处置）。
- 放在 `mkdir` 之前：失败调用不产生空输出目录副作用。

**被拒方案**：

| 方案 | 否决理由 |
|------|----------|
| 只在 `run()` 守卫 | 直接调用 `_generate_results()` 的测试/诊断路径仍假成功（P9） |
| 返回带 `status="empty"` 的字典 | 破坏既有返回契约，下游无消费方区分该字段 |
| 用 `InvariantViolationError` | 语义不符：不变量校验针对已产生的快照，空集不是违规 |

### D3 `_build_maps()` 双窄化

**代码形态**：

```python
    def _build_maps(self):
        """构建日期/股票到索引的映射"""
        dates = self.dates
        stocks = self.stocks
        assert dates is not None and stocks is not None
        self.date_map = {date_str: i for i, date_str in enumerate(dates)}
        self.stock_map = {stock_code: i for i, stock_code in enumerate(stocks)}
```

**理由**：`_build_maps()` 仅在 `_load_from_pandas()` L115 被调用，且 L111-L112 已赋值（P13）；`assert` 为 P-007 D4 已验证的窄化形态，零运行时。

### D4 engine_v2 两条窄化

**L224（arg-type）**：

```python
            self.pipeline = FactorPipeline(cast(DataManager, self.dm), self.cfg.factor)
```

- 需在 `from typing import Any, Optional` 增 `cast`。
- E3 支撑：cast 只作用于类型检查器，无运行时行为。
- 诚实限制：注入的 `IDataManager` 若在 `process()` 走到 `neutralize_industry`/`neutralize_mktcap` 分支（需 `industry`/`mktcap`），运行时会 `AttributeError`——该责任由注入方承担，本批**不新增运行时 isinstance 检查**（会改变 13 用例的注入契约）。

**L293（union-attr）**：

```python
        dm = self.dm
        assert dm is not None
        raw = dm.load_factor(fname)
```

**理由**：`_precompute_factors()` 仅由 `setup()` 在 L205/L201 赋值 `self.dm` 之后调用（L233），断言恒真。

### D5 不加开关

不引入 `strict_signal_check` / `allow_empty_signal` 等配置项：两项守卫均为「假成功 → 明确失败」的语义修正，不存在需要保留旧行为的合法场景；加开关会让静默路径继续可达。

### D6 范围边界

| 不做 | 理由 |
|------|------|
| 改 `setup()` 守卫条件/文案 | 13 用例依赖豁免语义（P3/P10） |
| 收窄 `run()` 的 `except Exception: continue` | 覆盖全部交易日路径，需独立批次（U-P023-1） |
| `engine_v3_vector` 同形检查 | 无消费方、无证据（U-P023-4 未取证） |
| 把 `--check-untyped-defs` 加入 CI | 属扩大门禁面（U-P023-2） |
| 新增 `isinstance` 运行时校验 | 改变注入契约，破 13 用例 |

---

## 4. 实现规格

### 4.1 变更面

| 文件 | 变更 | 预估 |
|------|------|------|
| `core/engine_v2.py` | D1 守卫（+6）+ D2 守卫（+5）+ D4 L224 cast（+2/−1，含 `cast` 导入）+ D4 L293 别名与 assert（+3/−1） | **+16 / −2** |
| `core/data_v3.py` | D3 局部别名 + assert（+3/−2） | **+3 / −2** |
| `tests/test_p023_quality_guardrails.py`（新增） | 4 项测试（T1-T4） | **+110 量级** |
| 文档 | 四文档 + PROGRESS + CHANGELOG | — |

### 4.2 测试规格（4 项）

| ID | 测试 | 断言 |
|----|------|------|
| **T1** | `test_run_without_signal_raises` | 注入 pipeline+combiner、`factor_files=[]` → `setup()` OK；`run()` 抛 `RuntimeError` match=`信号未就绪` |
| **T2** | `test_run_after_manual_signal_injection` | 同构造 → setup → 手工 `_composite_signal = df` → `run()` 正常返回 dict（回归 13 用例形态） |
| **T3** | `test_generate_results_empty_snapshots_raises` | 注入构造 → setup → 直接 `_generate_results()` 抛 `RuntimeError` match=`快照` |
| **T4** | `test_normal_injected_backtest_still_works` | 注入构造 + `factor_files=["dummy.pkl"]` → run 返回 dict，`portfolio_value` 非空 |

> 夹具复用 `tests/test_rebalance_exits.py` 的 `_FakeDataManager` / `_FakeUniverse` / `_FakePipeline` / `_Top2Optimizer` / `_AlwaysTrigger` 设计（独立复制到新文件，避免跨文件 import 测试夹具）。

### 4.3 文案约定

| 守卫 | 异常类型 | 必含子串 |
|------|----------|----------|
| D1 信号未就绪 | `RuntimeError` | `信号未就绪` |
| D2 空快照 | `RuntimeError` | `快照` |

---

## 5. 不变式

| ID | 不变式 |
|----|--------|
| **I1** | `setup()` 的守卫条件、异常类型、文案逐字不变 |
| **I2** | 注入式两测试文件（`test_real_ashare_backtest` + `test_real_ashare_strict_validation`，基线 **27 passed**）全绿 |
| **I3** | 有信号、有快照的正常回测返回值结构不变（`portfolio_value` / `performance_metrics` / `additional_info` 等键全在） |
| **I4** | `run()` 的逐日循环体与 `except Exception: continue` 逐字不变 |
| **I5** | `FactorPipeline` / `IDataManager` / `DataLoaderV3.__init__` 的注解与签名零改动 |
| **I6** | 门禁口径不变：`mypy --explicit-package-bases core` = 0；`black` 不劣化 |

---

## 6. 验证契约

| ID | 验收 | 命令/证据 | 期望 |
|----|------|-----------|------|
| **V1** | 新增 4 项 | `pytest tests/test_p023_quality_guardrails.py -q` | 4 passed |
| **V2** | 全量回归 | `pytest -q` | **651 passed**（647 + 4） |
| **V3** | 门禁口径不劣化 | `mypy --explicit-package-bases core` | 36 files 0 errors |
| **V4** | 盲区清零 | `mypy --explicit-package-bases --check-untyped-defs core` | **0 errors**（由 4 清零） |
| **V5** | 格式 | `black --check core tests cli.py` | 113 files unchanged（112 + 新测试） |
| **V6** | 注入式回归 | `pytest tests/test_real_ashare_backtest.py tests/test_real_ashare_strict_validation.py -q` | **27 passed**（基线实测，V1 前） |
| **V7** | 保护面 | `git diff --name-only <base>..HEAD -- pyproject.toml .github/ core/interfaces.py` | 空 |

---

## 7. 风险登记

| ID | 风险 | 等级 | 缓解 |
|----|------|------|------|
| R1 | 外部调用方依赖「静默空回测」的返回值 | 低 | 该形态本身即缺陷；CHANGELOG `Changed` 明示两项行为变更 |
| R2 | `assert` 在 `python -O` 下被剥离 | 低 | 本仓无 `-O` 运行（P-007 R1 同款声明） |
| R3 | `_generate_results` 空快照守卫影响「零交易日」合法场景 | 低 | 零交易日回测无业务意义；U-P023-3 登记，若出现真实空数据源再裁决 |
| R4 | `cast` 掩盖「注入对象非 DataManager」 | 中 | 诚实限制写入 D4 与 CHANGELOG；不新增 isinstance（会破 13 用例） |
| R5 | 新增测试依赖注入夹具，若夹具与 `test_rebalance_exits` 漂移 | 低 | 夹具独立复制，断言只覆盖本批 4 条语义 |

---

## 8. 回退点

| 场景 | 操作 |
|------|------|
| 整体回退 | `git revert <本批提交>`（含测试与文档） |
| 仅回退行为守卫（D1/D2） | `git checkout <base> -- core/engine_v2.py`（同时回退 D4 同文件窄化） |
| 仅回退盲区窄化 | `git checkout <base> -- core/data_v3.py` + 手工撤销 engine_v2 的 `cast`/别名两处 |

---

## 9. Step 4 Review（独立 pass）

> **执行方式**：DESIGN 完稿后重读全文 + 逐条核对调研锚点（RULE-1 时序独立；RULE-4 单 Agent「自查·单视角」）。

### 9.1 检查表

| # | 检查项 | 结论 |
|---|--------|------|
| 1 | 设计基于已验证的调研结论 | ✅ D1←P3/P6/P10、D2←P5/P9、D3←P13、D4←P11/P12；无引用 `[未验证]` 锚点 |
| 2 | 无未经验证的假设 | ✅ 唯一潜在假设「零快照 ≈ 零交易日」已转为 U-P023-3 四元块 + R3 风险登记，不作结论 |
| 3 | 无论证驱动的归因扭曲 | ✅ 未把 F-A1 简化为「调用方忘记」——P6/P7 证明注入任一组件即触发，且**无公开注入口**；D4 的 `cast` 诚实限制未隐藏（R4 明示 `AttributeError` 责任） |
| 4 | 替代方案 ≥2 且被否决 | ✅ D1 列 4 项被拒、D2 列 3 项被拒；M-B/M-C/M-D 在 RESEARCH §4 |
| 5 | 职责外边界 | ✅ 出界 5 项（P-023 范围外）：`except` 收窄 / `--check-untyped-defs` 入门禁 / v3 引擎 / isinstance 运行时校验 / 零交易日语义裁决（U-P023-1~4） |
| 6 | 能力边界 | ✅ D4 声明：`cast` 不做运行时校验，注入非 `DataManager` 对象在 `industry`/`mktcap` 分支会 `AttributeError`——本批**回答不了**「注入契约的结构合法性」，只解决静态类型 |
| 7 | V6 可跑性 | ✅ 基线实测 `27 passed in 10.52s`（本机 Agg）；非条件 skip |
| 8 | D2 既有测试冲突扫描 | ✅ `_generate_results` 直接调用仅 `test_mypy_layerb_smoke.py:26`，其 `tracker` 为 `None` → 先命中既有 `RuntimeError`，D2 不改变该用例 |
| 9 | 行号核对 | ✅ `run()` dm 守卫 L311-L312、`t0` L314（D1 插入点）；`snapshots` L1139、`trades_df` L1140、`mkdir` L1142-L1143（D2 插入点） |

### 9.2 发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S4-P023-1 | P3 | I2 初稿写「13 个既有注入式用例」，实为 P-007 F-S9-1 当时的受影响计数（4+9）；当前两文件实测 **27 passed** | 已改为「两文件全绿，基线 27 passed」 |
| F-S4-P023-2 | P3 | D2 插入点初稿未核实 `trades_df` 与 `mkdir` 的相对顺序，存在「守卫后仍执行一行读取」的歧义 | 已在 §4.2 代码样例明确把 `trades_df` 移到守卫之后，`mkdir` 保持在最末 |

### 9.3 结论

**通过**——0 P1 / 0 P2 / 2 P3（均已回写）；可进入 Step 5 实施规划。
