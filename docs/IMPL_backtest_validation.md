# P-011 回测准确性验证、学术规范与基准比较 · 实施规划

> **文档编号**: IMPL_backtest_validation
> **阶段**: Phase 1 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 5 完稿；**Step 6 Review 通过**（2026-11-10，§8；P2×3 + P3×2 全部回写，审查基座 GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash，RULE-5 异构满足）；可进入 Step 7
> **上游**: [DESIGN_backtest_validation.md](DESIGN_backtest_validation.md)（Step 4 通过；D1-D9 / I1-I10；F-R1~F-R4 已回写）
> **下游**: CHECKLIST_backtest_validation
> **证据时点**: 本仓读数 @ `dc71c1a`（2026-11-10）；Python 3.12.10 / pytest 9.0.3 / black 26.5.0 / mypy 2.1.0
> **档位**: T1（`core/` 4 新 + 4 改、`tests/` 7 新 + 1 辅助、`cli.py` 1 处、`docs/` 1 新）
> **解释器**: `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`；`MPLBACKEND=Agg`

---

## 1. 执行总览

### 1.1 任务分解

| ID | 任务 | 依赖 | 产出 | 批次 |
|----|------|------|------|------|
| T-0 | RED 基线（10 项读数）+ B1 RED 测试 | — | §3 读数表 + B1 的 2 个测试文件（RED）+ 2 个辅助模块 | B1 |
| T-1 | 不变量模块 `core/invariants.py` | T-0 | I1-I7 纯函数 + `InvariantReport` | B1 |
| T-2 | 参考实现 `tests/_reference_impl.py` | T-1 | 4 个纯函数参考 | B1 |
| T-3 | 不变量/参考差分测试 | T-2 | `test_invariants.py`（10）/ `test_reference_diff.py`（9） | B1 |
| T-4 | V2 组件差分测试 | T-3 | `test_v2_components.py`（5） | B2 |
| T-5 | V2↔V3 事件级等价测试 | T-4 | `test_cross_engine_equivalence.py`（5） | B2 |
| T-6 | 跨框架口径映射文档 | T-5 | `docs/BACKTEST_CALIBER_MAPPING.md` | B2 |
| T-7 | 指标单一实现 `core/metrics.py` | T-6 | `compute_metrics` + `MetricsResult` | B3 |
| T-8 | `analytics` 委托 + rf 可配置 | T-7 | `analytics.py`、`engine_v2.py` 传参 | B3 |
| T-9 | V3 kernel 对齐（rf + 回撤锚点 + 量级） | T-8 | `engine_v3_vector.py`、`config.py` | B3 |
| T-10 | 三口径一致测试 + B3 指标对拍 | T-9 | `test_metrics_single_source.py`（8）+ Δ 表 | B3 |
| T-11 | 偏差声明 `core/validation.py` | T-10 | 能力常量 + `build_validation_declaration`（4 测试） | B4 |
| T-12 | run manifest `core/manifest.py` | T-11 | 序列化/哈希/指纹 + 7 测试 | B5 |
| T-13 | trace 接线 + 完整性验收 | T-12 | `cli.py --trace-dir` + 4 测试 | B6 |
| T-14 | 全量验证 + 四文档 + 台账 + 提交 + CI | T-13 | — | — |

### 1.2 提交与批次映射

| 提交 | 任务 | 行为 | 归因要求 |
|------|------|------|----------|
| **B1** | T-0 + T-1 + T-2 + T-3 | 零数值 | 无（`invariant_mode` 默认 `report`，仅增诊断字段） |
| **B2** | T-4 + T-5 + T-6 | 零数值 | 无（纯测试 + 文档） |
| **B3** | T-7 + T-8 + T-9 + T-10 | **行为（报告指标）** | `change_report.json`（应全零）+ **指标 Δ 表**（T-10） |
| **B4** | T-11 | 零数值 | 无（报告增声明字段） |
| **B5** | T-12 | 零数值 | 无（新增 `manifest.json`） |
| **B6** | T-13 | 零数值 | 无（CLI 参数 + 测试） |
| **docs** | T-14 | 零代码 | — |

### 1.3 执行顺序

```text
T-0 RED 基线（10 读数 + 7 测试文件骨架，全部先失败）
  │
  ├─► T-1 不变量 ─► T-2 参考实现 ─► T-3 测试转绿 ────────►【B1 提交】
  │                                     │
  │                                     └─► T-4 V2 组件差分 ─► T-5 事件等价 ─► T-6 口径文档 ─►【B2 提交】
  │                                                                                 │
  │                                                                                 └─► T-7 metrics ─► T-8 analytics ─► T-9 V3 kernel ─► T-10 测试+Δ表 ─►【B3 提交 + change_report】
  │                                                                                                                                                       │
  │                                                                                                                                                       └─► T-11 声明 ─►【B4】
  │                                                                                                                                                              └─► T-12 manifest ─►【B5】
  │                                                                                                                                                                    └─► T-13 trace ─►【B6】
  │                                                                                                                                                                          └─► T-14 全量+文档+CI
```

**任一零数值批次出现数值差异 / B3 出现 NAV 或六层 dump 差异 → 停止并回退该批次**，不跨批修补。

### 1.4 关键原则

| 原则 | 说明 |
|------|------|
| 先观测、后变更 | B1/B2 必须先固化不变量与差分，B3 才有「指标变化是否只来自公式」的判据 |
| 零数值批次严格隔离 | B1/B2/B4/B5/B6 不得改变任何 NAV、交易、掩码、指标数值 |
| B3 单独成批 | 唯一改动报告指标的批次；NAV 与六层 dump 必须零变化 |
| 测试不得依赖本地数据 | 禁止读 `data/test_ashare`（`.gitignore` 忽略，CI 不可用）；一律合成夹具 |
| 不引入运行时依赖 | 仅 `numpy` / `pandas` / `stdlib`；不引入 `hypothesis`/`pandera`/`pyarrow` |
| 参考实现独立编写 | 按 DESIGN §4 公式写，禁止复制被测内核代码（防「同源同错」） |
| 默认路径保守 | `invariant_mode="report"`、`write_manifest=True`、`risk_free_rate=0.03`、`dump_layers_dir=None` |
| 零 opportunistic 重构 | 不动匹配引擎语义、不动 P-012 层文件格式、不动 `change_report` 归因链、不改 V2/V3 成交时点 |

---

## 2. 工程细节

### 2.1 技术栈与版本（E1）

| 组件 | 版本 | 验证 |
|------|------|------|
| Python | 3.12.10（本地）/ 3.10-3.12（CI） | `pyproject.toml` 矩阵既有 |
| pytest / black / mypy | 9.0.3 / 26.5.0 / 2.1.0 | P-007 层 B 锁定 |
| numpy / pandas / numba | 既有版本（不新增约束） | 现有 550 测试通过 |
| **新增运行时依赖** | **无** | 显式约束（DESIGN §10.1-3） |
| 新增测试依赖 | 无（`pytest` 自带参数化即可） | 固定 `np.random.default_rng(seed)` |

### 2.2 兼容性

| 项 | 处理 |
|----|------|
| Python 3.10 | `from __future__ import annotations`；不用 3.11+ 语法 |
| `generate_report(...)` | 新增 `risk_free_rate` **带默认值 0.03**，旧调用保持可用 |
| `_metrics_kernel(pv)` | 新增 `risk_free_rate` **带默认值 0.03**，旧单参调用保持可用（numba 支持默认参数；若编译失败则回退为显式双参并同步 3 处调用） |
| `max_drawdown` 语义 | V2/`tracker` 维持正值；V3 kernel 内部负值、results 层取量级 → 对外统一正值（**行为变更**，B3 披露） |
| `BacktestConfig` | 三个新字段均有默认值：`invariant_mode="report"`、`risk_free_rate=0.03`、`write_manifest=True` |
| `manifest.json` | 新增文件，不被既有代码读取；`write_manifest=False` 可关闭 |
| `dump_layers_dir` | 不改名、不改格式；仅新增 CLI 映射与 manifest 同写 |

### 2.3 文件结构（新增/修改）

```text
core/
├── invariants.py        # 新：I1-I7 + InvariantReport/Violation + check_all
├── metrics.py           # 新：MetricsResult + compute_metrics + sharpe_ratio
├── validation.py        # 新：能力常量 + build_validation_declaration
├── manifest.py          # 新：_jsonable/_sha256_file/_git_info/build_manifest/write_manifest
├── config.py            # 改：invariant_mode / risk_free_rate / write_manifest
├── analytics.py         # 改：PerformanceAnalyzer(rf) + generate_report(rf) + 委托 compute_metrics
├── engine_v2.py         # 改：_generate_results 增 invariant/declaration/manifest；run() 记 started_at
└── engine_v3_vector.py  # 改：_metrics_kernel(rf + 回撤锚点) + _generate_results(rf + 量级)
cli.py                   # 改：run 子命令 --trace-dir
tests/
├── _reference_impl.py              # 新（辅助，非 test_ 前缀，不被收集）
├── _synth_fixture.py               # 新（辅助：合成 pkl 夹具写入 tmp_path，供 3 处复用）
├── test_invariants.py              # 新（10）
├── test_reference_diff.py          # 新（9）
├── test_v2_components.py           # 新（5）
├── test_cross_engine_equivalence.py# 新（5）
├── test_metrics_single_source.py   # 新（8）
├── test_validation_declaration.py  # 新（4）
├── test_manifest.py                # 新（7）
└── test_trace_completeness.py      # 新（4）
docs/
└── BACKTEST_CALIBER_MAPPING.md     # 新：V2/V3/Qlib/Backtrader/VectorBT 口径映射 + 等价差异
```

### 2.4 低效/危险操作排除

| 潜在低效/危险 | 排除措施 |
|---------------|----------|
| 参数网格过大导致测试慢 | 固定 32 组参数（股数 ∈ {1,2,5,20,40}、top_n ∈ {1,n/2,n}、含零价/NaN/掩码），单文件目标 < 5s |
| 不变量逐日 O(D×S) 全量扫描 | 每日仅遍历持仓字典（稀疏）；总耗时 O(D×持仓数)，实测下限流 |
| manifest 一次性读大 pkl 计算哈希 | 1 MiB 分块流式 `hashlib.sha256`，内存恒定 |
| manifest 每次 run 都调 git 子进程 | 单次 `rev-parse` + `status --porcelain`，`timeout=2`，失败降级 null 不重试 |
| 参考实现复制内核代码 | `tests/_reference_impl.py` 按 DESIGN 公式独立实现；审阅时逐行比对语义而非文本 |
| 事件等价测试构造数据「喂答案」 | 必须含阴性对照（§4.5），残差必须精确等于声明差异 |
| manifest 写入阻塞主流程 | `try/except OSError` 记 warning，不阻断回测（与 trace 目录的 fail-fast 区分：trace 是用户显式路径） |
| 既有测试断言 `output_dir` 的文件集合 | 新文件只增不删；如遇「文件数/目录列表」类断言失败，更新断言而非关闭 `write_manifest` 默认值，并在提交消息披露 |
| 新测试误读本地数据目录 | 全部 `tmp_path` + 内存 DataFrame；`Grep data/test_ashare` 新增测试 0 命中（V12） |

---

## 3. RED 基线（T-0，实施前必录）

### 3.1 十项读数

| # | 读数 | 命令 | 预期（@`dc71c1a`） |
|---|------|------|--------------------|
| R1 | 全量测试 | `MPLBACKEND=Agg python -m pytest tests -q` | `550 passed` |
| R2 | black | `python -m black --check .` | `153 files would be left unchanged`（E1 已复核） |
| R3 | mypy 门禁口径 | `python -m mypy --explicit-package-bases core` | `Success: no issues found` |
| R4 | mypy 盲区口径 | 追加 `--check-untyped-defs` | `4 errors in 2 files`（E1 已复核） |
| R5 | 用例收集 | `python -m pytest tests --collect-only -q` | `550 tests collected`（E1 已复核） |
| R6 | 指标口径探针 | `%TEMP%\p011_step4_probe.py` | V2 mdd=**+0.19**、V3 mdd=**−0.1**、两引擎年化分母**均 252/N**（E2，Step 4 已录） |
| R7 | B3 基准运行指标 | 用 `prepare_test_fixture.py --profile baseline --n-stocks 31 --n-days 60` 生成夹具（**31 股 × 60 日**；脚本下限 `MIN_STOCKS=31`/`MIN_DAYS=51`，F-I2 修正原「10 股」错误），V2 跑一次并导出 `performance_metrics.json`；V3 同数据跑一次导出 results | `[T-0 记录]`（B3 Δ 表的 before 列） |
| R8 | 既有测试文件数 | `Get-ChildItem tests -Filter 'test_*.py'` | **60** |
| R9 | 测试夹具文件数 | `Glob data/test_ashare/*.pkl`（本地） | **7**（`data/` 被 gitignore，CI 用生成夹具） |
| R10 | 工作区 | `git status --short` | 仅 docs 变更（RESEARCH / DESIGN / PROGRESS） |

### 3.2 各批次 RED 测试（先写失败测试，再实现）

> **范围（F-I3）**：T-0 只创建 **B1 的 2 个测试文件**与 `tests/_reference_impl.py`、`tests/_synth_fixture.py` 两个辅助模块；B2-B6 的 6 个测试文件在各批次实现**前**创建——保证每个提交点上全量测试为绿（若 B1 提交含 B2-B6 的失败骨架，零数值批次的全量验收即被破坏）。

| 批次 | 失败测试 | 预期失败形态 |
|------|----------|--------------|
| B1 | `test_invariants.py::test_nav_identity_ok` | `ModuleNotFoundError: core.invariants` |
| B1 | `test_invariants.py::test_engine_emits_invariant_report` | 结果缺 `additional_info["invariant_report"]`（KeyError） |
| B1 | `test_reference_diff.py::test_rebalance_kernel_matches_reference` | `ModuleNotFoundError: tests._reference_impl` |
| B2 | `test_v2_components.py::test_target_positions_matches_reference` | 首跑即 **GREEN**（描述性验证，B1 已交付 `_reference_impl`；失败 = 真实缺陷，见下方说明） |
| B2 | `test_cross_engine_equivalence.py::test_event_level_equivalence` | **预期首跑即 GREEN**（见下方说明） |
| B3 | `test_metrics_single_source.py::test_v3_sharpe_uses_config_rf` | `AssertionError`（当前 V3 rf=0） |
| B3 | `test_metrics_single_source.py::test_v3_drawdown_includes_initial_anchor` | `AssertionError`（pv=[100,90,81] 当前报 0.1，应 0.19） |
| B3 | `test_metrics_single_source.py::test_v2_volatility_uses_diff_returns` | `AssertionError`（当前 vol 含首日 0 收益） |
| B4 | `test_validation_declaration.py::test_declaration_present` | KeyError（结果缺 `validation_declaration`） |
| B5 | `test_manifest.py::test_manifest_written` | `FileNotFoundError: manifest.json` |
| B6 | `test_trace_completeness.py::test_all_six_layers_present` | 当前无 `--trace-dir` 入口，未开启 dump → 目录空 |

> **诚实声明（B2）**：T-4/T-5 是**描述性验证测试**（characterization），不是缺陷修复型 RED。若首次运行即全绿，说明当前实现与 DESIGN 自洽（预期）；**若失败，即为发现的真实缺陷**，须登记 F-I* 并在 IMPL/CHECKLIST 披露，不得改测试迁就实现。

---

## 4. 逐任务实施要点

### T-1 不变量模块（D2，`core/invariants.py`）

**接口**（与 DESIGN §4.1 一致）：

```python
InvariantMode = Literal["off", "report", "raise"]


class InvariantViolationError(RuntimeError):
    """raise 模式下的首个违规。"""


@dataclass
class Violation:
    code: str  # I1..I7
    date: str | None
    detail: str
    value: float | None


@dataclass
class InvariantReport:
    mode: str
    checked: int
    violations: list[Violation]

    @property
    def ok(self) -> bool: ...

    def to_dict(self) -> dict[str, Any]: ...


def check_nav_identity(snapshots, *, rtol=1e-9, atol=1e-6) -> list[Violation]: ...
def check_position_identity(snapshots, trades, *, atol=1e-6) -> list[Violation]: ...
def check_cost_identity(trades, stats, *, atol=1e-6) -> list[Violation]: ...
def check_return_identity(snapshots, initial_capital, *, rtol=1e-9, atol=1e-9) -> list[Violation]: ...
def check_v3_nav_identity(portfolio_value, cash, positions, prices, *, rtol=1e-9, atol=1e-6) -> list[Violation]: ...
def check_v3_static_positions(positions, rebalance_indices, *, atol=1e-12) -> list[Violation]: ...
def check_v3_cost_identity(positions, prices, cash, cost_rate, *, rtol=1e-9, atol=1e-6) -> list[Violation]: ...
def check_all(snapshots, trades, stats, initial_capital, mode) -> InvariantReport: ...
```

**实施要点**：

1. I1 用 `snapshot.positions.values()` 的 `market_value` 求和；空持仓字典 → `total == cash`。
2. I2 对每个快照日 `d`，`Σ_{trade.date<=d} sign(side)*quantity` 与 `snapshot.positions` 数量比对；**退市/强平经 `execute_order` 落 trade**（`engine_v2.py:516-521`/`:580-586`），天然计入；若未来出现无 trade 的仓位变更，本不变量应报错而非静默。
3. I3 用 `executor.get_execution_stats()`（键：`total_cost`/`total_amount`/`total_trades`/`buy_trades`/`sell_trades`，`execution.py:129-150`）；`net_amount` 符号：买 `amount+cost`、卖 `amount-cost`。
4. I4 首日基准 = `initial_capital`；`daily_return` 与 `total_value` 递推比对；`cumulative_return == tv/initial - 1`。
5. I5-I7 供 V3 单测使用，不在引擎内接线（V3 无 tracker）。
6. `check_all` 只跑 I1-I4（V2 引擎上下文），`checked` 计快照数；`raise` 模式抛首条违规。

**引擎接线**（`engine_v2.py::_generate_results`，`additional_info` 之后）：

```python
mode = getattr(self.cfg, "invariant_mode", "report")
if mode != "off" and snapshots and self.executor is not None:
    report = check_all(
        snapshots,
        self.executor.trade_log.get_trades(),  # F-I1：TradeLog 方法名为 get_trades（execution.py:71-77），无 get_all_trades
        self.executor.get_execution_stats(),
        initial_capital=self.cfg.initial_capital,
        mode=mode,
    )
    additional_info["invariant_report"] = report.to_dict()
    if mode == "raise" and not report.ok:
        raise InvariantViolationError(report.violations[0])
```

**配置**（`core/config.py::BacktestConfig`）：

```python
invariant_mode: Literal["off", "report", "raise"] = "report"
```

### T-2 参考实现（D3，`tests/_reference_impl.py`）

> 文件名不以 `test_` 开头 → 不被 pytest 收集；按 DESIGN 公式独立编写。

```python
def ref_rebalance_kernel(positions, cash, last_portfolio_value, signal, prices,
                         buyable_mask, sellable_mask, top_n, cost_rate): ...
def ref_build_target_positions(target_weights, current_positions, prices, total_value,
                               *, round_lot=True, lot_size=100, value_buffer=0.985): ...
def ref_calculate_cost(amount, is_buy, *, commission_rate, commission_min,
                       stamp_tax_rate, slippage_pct, exchange_fee=0.0): ...
def ref_v3_nav(cash, positions, prices): ...
```

**实施要点**：

1. `ref_rebalance_kernel` 必须与内核**归约顺序一致**：成本与现金均用**逐元素循环累加**（numba `@njit` 下 `np.sum` 即顺序累加；NumPy `np.sum` 为 pairwise 归约，实测 200 组中 100 组末位差 1 ulp——F-S9-2），以保证比特一致。
2. 选股阈值语义镜像：`n_stocks <= top_n → signal>0`；否则 `threshold = np.partition(abs_signal, -top_n)[-top_n]`，`selected = abs_signal >= threshold`（**保留并列超选语义**）。
3. `ref_build_target_positions` 覆盖四分支：权重 ≤0 且有持仓 → 清仓；价格 `None`/≤0 → 维持；`raw = weight*tv*buffer/price`；`round_lot` → `floor(raw/lot)*lot`，否则 `int(raw)`。
4. `ref_calculate_cost` 公式：`max(amount*rate, commission_min) + amount*exchange_fee + (卖 ? amount*stamp : 0) + amount*slippage`；`asset_cost.commission_rate is None` 时用 cfg 费率（调用方传有效值）。
5. 禁止 import `core.engine_v3_vector` / `core.target_positions` / `core.execution` 的实现函数（仅可 import 常量/枚举）。

### T-3 不变量与参考差分测试（B1）

`tests/test_invariants.py`（10 项）：

| # | 用例 | 断言 |
|---|------|------|
| 1 | `test_nav_identity_ok` | 构造 3 快照（cash+mv=tv）→ 0 违规 |
| 2 | `test_nav_identity_detects_mismatch` | 篡改 1 元 → I1 违规（code/date 正确） |
| 3 | `test_position_identity_ok` | 买入 100/卖出 40 → 持仓 60，0 违规 |
| 4 | `test_position_identity_detects_untracked_change` | 无 trade 改仓位 → I2 违规 |
| 5 | `test_cost_identity_ok` | 2 笔成本合计 == stats → 0 违规 |
| 6 | `test_cost_identity_detects_negative_cost` | cost<0 → I3 违规 |
| 7 | `test_return_identity_ok` | 手工递推一致 → 0 违规 |
| 8 | `test_return_identity_detects_drift` | 篡改 daily_return → I4 违规 |
| 9 | `test_check_all_report_mode` | 混合违规 → `ok=False`、`checked` 正确、不抛 |
| 10 | `test_engine_emits_invariant_report` | 跑 20 日小样本 V2 → `additional_info["invariant_report"]["ok"] is True` |

`tests/test_reference_diff.py`（9 项）：

| # | 用例 | 断言 |
|---|------|------|
| 1 | `test_rebalance_kernel_matches_reference` | 32 组网格：`np.array_equal` 仓位、`==` 现金（比特一致） |
| 2 | `test_rebalance_kernel_python_fallback_matches` | `getattr(fn,"py_func",fn)` 同参考 |
| 3 | `test_rebalance_kernel_all_nan_signal` | 全 NaN → 持仓/现金原样返回 |
| 4 | `test_rebalance_kernel_zero_price` | 零价不可建仓、可清仓 |
| 5 | `test_target_positions_matches_reference` | 权重/价格/整手网格比特一致 |
| 6 | `test_cost_matches_reference` | 佣金下限边界（amount=1000 vs 100000） |
| 7 | `test_v3_nav_matches_reference` | I5 参考递推一致 |
| 8 | `test_determinism_metamorphic` | 同输入两次 → 输出完全一致（V2 快照序列 + V3 pv） |
| 9 | `test_price_scaling_metamorphic` | 价格 ×2、零费用 → 仓位 /2、现金不变、NAV 不变 |

### T-4 V2 组件差分测试（B2，`tests/test_v2_components.py`）

| # | 用例 | 断言 |
|---|------|------|
| 1 | `test_target_positions_matches_reference` | 直接调用 `build_target_positions` vs 参考 |
| 2 | `test_target_positions_round_lot_boundary` | `round_lot=True/False` 恰好整除/不整除两组 |
| 3 | `test_calculate_cost_commision_min_binding` | `amount*rate < 5` → cost==5；`>=5` → 费率值 |
| 4 | `test_calculate_cost_stamp_only_on_sell` | 买无印花税、卖有 |
| 5 | `test_execute_order_trade_fields` | `amount==qty*price`、`cost==参考`、`net_amount` 符号正确 |

### T-5 事件级等价测试（D4，`tests/test_cross_engine_equivalence.py`）

**夹具**（全部 `tmp_path` 生成，不读本地数据）：

| 项 | 值 |
|----|-----|
| 日期 | 3 个交易日（2024-01-02/03/04） |
| 股票 | `000001`、`600000` |
| OHLC | `open == close == high == low ==` 常量矩阵 `[[10,25]]×3` |
| `stock_adj` | 全 1.0（raw == hfq，隔离复权） |
| `suspend` / `st` | 全 0（全可交易） |
| 因子 | `factor_value.pkl` 常量 `[[1.0, 2.0]]×3` |
| V2 配置 | `enable_pending_orders=False`、`cost` 四项全 0（含 `commission_min=0`）、`optimizer(method="equal_weight", target_count=2, max_weight=1.0, round_lot=True, select_top=True)`、`rebalance(frequency="daily")`、`factor(winsorize/standardize/fill="none", neutralize=False)`、`universe(exclude_na_factors=False)` |
| V3 配置 | `initial_capital=10_000_000`、`top_n=2`、`rebalance_freq=1`、`cost_rate=0.0`、buyable/sellable 全 True、`factor_dict={"factor": 同因子}` |

**断言**（§4.5 五条）：

```python
assert list(v2_qty) == [492_500, 197_000]                # floor(0.985×0.5×1e7/P)
assert list(v3_qty) == [500_000, 200_000]
assert v2_pv == v3_pv == [10_000_000] * 3                 # 常量价，rtol=0（全部 3 日）
assert v2_cash - v3_cash == 150_000                      # 0.015×TV，rtol=0
# 阴性对照：不含 0.985 的假设下，残差精确等于声明差异
assert v3_qty[0] - v2_qty[0] == 7_500
assert v3_qty[1] - v2_qty[1] == 3_000                # 0.015×0.5×1e7/25；原 3_750 有误（F-S9-4）
```

**实施注意**：

1. 夹具统一由 `tests/_synth_fixture.py` 提供：`write_price_fixture(tmp_path, dates, codes, prices, adj=1.0, suspend=0, st=0)` 与 `write_factor(tmp_path, name, values)`；T-3 #10、T-5、T-13 共用，禁止各自复制 pkl 写盘代码。
2. V2 日 0 触发再平衡 → 订单入 `_next_day_orders` → 日 1 开盘（=10/25）成交；V3 日 0 跳过、日 1（`1%1==0`）用 close 成交 → 同一经济事件。
3. V2 `build_target_positions` 默认 `value_buffer=0.985`（`target_positions.py:51`）；T-5 不需修改引擎，只需在断言中显式建模。
4. 取 V2 日 1 持仓：`engine.tracker.get_snapshots()[1].positions`；V3：`engine.get_positions()[1]` 与 `results["portfolio_value"][1]`。
5. V2 的 `DataManager` 需 `industry.pkl`/`mktcap` 可选；缺失走 P-010 默认（`exclude_by_market_cap=False`）。

### T-6 口径映射文档（B2，`docs/BACKTEST_CALIBER_MAPPING.md`）

必备章节：

1. 为什么要映射（RESEARCH A27/A28/A29：默认口径差异 → 假阳性）；
2. 五列口径表：信号时点 / 成交时点与价格 / 费用 / 复权 / 股票池与掩码 / 估值 / 输出（本仓 V2、V3、Qlib、Backtrader、VectorBT）；
3. **本仓两引擎的声明差异**（T+1 vs 同日收盘、0.985 缓冲、整数股、费用模型、V3 无待执行队列）；
4. 等价测试的构造与残差恒等式（指向 `test_cross_engine_equivalence.py`）；
5. 明确声明：**不声称与任何外部框架数值一致**；外部对拍属 U-D2/X-B，未启用。

### T-7 指标模块（D5，`core/metrics.py`）

```python
DEFAULT_RISK_FREE_RATE = 0.03
ANNUALIZATION_DAYS = 252
SHARPE_METHOD = "annual_return_minus_rf_over_annual_vol"


@dataclass(frozen=True)
class MetricsResult:
    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    max_drawdown: float  # >= 0 量级约定
    final_value: float
    n_periods: int
    risk_free_rate: float


def compute_metrics(portfolio_value, *, risk_free_rate=DEFAULT_RISK_FREE_RATE,
                    periods=ANNUALIZATION_DAYS) -> MetricsResult: ...
def sharpe_ratio(annual_return, annual_volatility, risk_free_rate) -> float: ...
```

**公式**（与 DESIGN §4.2 逐字一致）：`returns = np.diff(pv)/pv[:-1]`；`cumulative = pv/pv0`（N 点，含锚点 1.0）；`total_return = cumulative[-1]-1`；`annual_return = (1+total_return)**(periods/N)-1`；`annual_vol = std(returns, ddof=0)*sqrt(periods)`；`sharpe = (annual_return-rf)/vol`（vol≤0→0）；`mdd = max((cummax(cumulative)-cumulative)/cummax(cumulative))`。

**边界**：`len(pv) < 2` → `ValueError`（唯一抛出处；V3 kernel 保留返回零值历史行为，二者差异由 T-10 显式覆盖）。

### T-8 analytics 委托 + rf 透传（B3）

1. `PerformanceAnalyzer.__init__(self, risk_free_rate: float = DEFAULT_RISK_FREE_RATE)`；`self.risk_free_rate = float(risk_free_rate)`。
2. `calculate_performance_metrics`：
   - `total_values = [s.total_value for s in snapshots]`；
   - `m = compute_metrics(total_values, risk_free_rate=self.risk_free_rate)`；
   - 五个口径字段取 `m.*`（`total_return`/`annual_return`/`annual_volatility`/`sharpe_ratio`/`max_drawdown`）；
   - `daily_returns`（快照口径，N 项）**保留**用于 `win_rate`/`avg_win`/`avg_loss`/`win_loss_ratio`/`sortino_ratio`/`max_drawdown_duration`/`_calculate_drawdown_periods`；
   - `calmar_ratio` 仍用 `annual_return / max_drawdown`（mdd>0 成立）；
   - 新增键 `risk_free_rate`。
3. `generate_report(snapshots, trades_df, output_dir, *, risk_free_rate=DEFAULT_RISK_FREE_RATE)` → `PerformanceAnalyzer(risk_free_rate)`。
4. `engine_v2._generate_results`：`generate_report(snapshots, trades_df, output_dir, risk_free_rate=self.cfg.risk_free_rate)`。

### T-9 V3 kernel 对齐（B3，`engine_v3_vector.py` + `config.py`）

1. `_metrics_kernel(portfolio_value, risk_free_rate=DEFAULT_RISK_FREE_RATE)`：
   - `returns`、`total_return`、`annual_return`（`252/n`）、`volatility` 维持现状；
   - `sharpe = (annual_return - rf)/vol if vol>0 else 0`；
   - **回撤补锚点**：`cum[0]=1.0`；`for t in 1..n-1: cum[t]=cum[t-1]*(1+returns[t-1])`；`running_max[0]=cum[0]`；手写循环（numba 不支持 `np.maximum.accumulate`）；`max_dd = min(dd)`（**保持负值原语**）。
2. `_generate_results`：
   - `rf = float(self.cfg.get("risk_free_rate", 0.03))`；kernel 调用传 rf；
   - 输出 `"max_drawdown": -float(max_drawdown)`（**量级约定**）、`"risk_free_rate": rf`。
3. `config.py` 加 `risk_free_rate: float = 0.03`。
4. **测试影响**：`test_v3_engine_integration.py:217` 断言 `-1<=mdd<=0` → `0<=mdd<=1`（B3 内更新）；`test_numba_jit_performance.py:178/:280` 断言针对 kernel 负值 → **不变**（锚点修正仅改变幅度，仍 ∈[-1,0]）。

### T-10 三口径一致测试 + B3 Δ 表（B3）

`tests/test_metrics_single_source.py`（8 项）：

| # | 用例 | 断言 |
|---|------|------|
| 1 | `test_compute_metrics_matches_analytics` | 同一 pv（用 snapshots 构造）→ `rtol=1e-12` |
| 2 | `test_v3_kernel_matches_compute_metrics` | `-kernel.mdd` 与 `compute_metrics.mdd` 一致；total/annual/vol 一致 |
| 3 | `test_v3_results_use_config_rf` | `cfg={"risk_free_rate":0.0}` vs 默认 → sharpe 差 == rf/vol |
| 4 | `test_v3_drawdown_includes_initial_anchor` | pv=[100,90,81] → 0.19（当前 0.1，RED） |
| 5 | `test_v2_volatility_uses_diff_returns` | 构造首日 0 收益 → vol 按 N−1 差分计算 |
| 6 | `test_compute_metrics_empty_and_single` | len<2 → ValueError |
| 7 | `test_kernel_single_point_returns_zeros` | 历史行为保留（零值） |
| 8 | `test_trading_days_equals_snapshot_count` | `metrics["trading_days"] == len(pv)`（I9 前提） |

**B3 Δ 表产出**（T-0 R7 的 before + 实施后 after）：

```text
%TEMP%\p011_b3_delta.py
  读 before_metrics.json / after_metrics.json
  输出字段对比（V2 全字段、V3 全字段），abs/rel Δ 与符号解释
→ 结果粘贴 IMPL §9（Step 9 回写）与 CHECKLIST
```

### T-11 偏差声明（D6，`core/validation.py`）

```python
SCHEMA_VERSION = "1.0"
PIT_SUPPORTED = False
MULTIPLE_TESTING_SUPPORTED = False
BENCHMARK_SUPPORTED = False
WALK_FORWARD_AVAILABLE = True

def build_validation_declaration(*, risk_free_rate, universe_report,
                                 execution_timing) -> dict[str, Any]: ...
```

**实施要点**：

1. `survivorship.corrected = universe_report.get("survivorship") == "corrected"`；`source` 取原值。
2. `benchmark.configured = cfg.benchmark is not None`（本次传参）；`comparable=False`（能力常量）。
3. `multiple_testing = {"corrected": MULTIPLE_TESTING_SUPPORTED, "n_trials": None}`。
4. `known_limitations` 固定 5 条（DESIGN §4.3）——**每条对应一个 false 字段或已知差异**，不得新增未实现的能力声明。
5. 接线：`additional_info["validation_declaration"] = build_validation_declaration(...)`（`_universe_report()` 已存在，`engine_v2.py:598`）。

`tests/test_validation_declaration.py`（4 项）：字段齐备、能力 false、survivorship 派生、rf/config 透传。

### T-12 run manifest（D7，`core/manifest.py`）

```python
MANIFEST_SCHEMA_VERSION = "1.0"

def build_manifest(cfg, *, data_dir, data_files, caliber, started_at, finished_at,
                   outputs=None, benchmark=None) -> dict[str, Any]: ...
def write_manifest(manifest, paths) -> list[Path]: ...
```

**实施要点**：

1. `_jsonable(value)`：`Path→str`、`Enum→.value`、dataclass→dict（`dataclasses.fields`）、`Mapping/Sequence`（先判 `str/bytes`）、`callable→"<callable>"`、`numpy` 标量→`.item()`、其他→`repr()` + warning。
2. `_sha256_file(path)`：1 MiB 分块；不存在返回 `None`。
3. `_git_info(root)`：`git rev-parse HEAD`、`git status --porcelain`（`timeout=2`，`capture_output`）；异常 → `{"commit": None, "dirty": None}` + warning。
4. `input_fingerprint = "sha256:" + sha256(canonical_json({"commit","data","config"}))`，`sort_keys=True`、`ensure_ascii=False`、`separators=(",",":")`；**不含** `run_id`/时间戳。
5. `data.files` 由 `data_files` 列表（`close/open/high/low/adj_factor/suspend/industry/st` + `factor_files`，`mktcap_file` 非空才含）逐项 `{name, exists, sha256, bytes}`。
6. `environment`：`platform.python_version()`、`platform.platform()`、`numpy.__version__`、`pandas.__version__`、`numba.__version__`（缺失 → None）。
7. `caliber`：`ruleset_version`（`filter.limit_rules.RULESET_VERSION`）、`price_modes`、`next_day_tradable_mode`、`api_version`（`core.__api_version__`，`core/__init__.py:14`）。
8. 引擎：`run()` 开头记 `self._run_started_at = datetime.now()`（`setup()` 不记，避免 setup/run 分离误算）；`_generate_results` 末尾写 `[cfg.output_dir]` + `dump_layers_dir`（若非空）；`write_manifest` 默认 `True`；异常 `OSError` 记 warning 不抛（manifest 可写性不作为回测成败条件）。
9. `config` 键集必须 == `BacktestConfig` dataclass 顶层字段集（I8）。

`tests/test_manifest.py`（7 项）：写入存在、字段齐备、sha256 与 `hashlib` 一致、缺失文件 `exists=false`、指纹两次相同、config 键集一致、callable 序列化为 `"<callable>"`。

### T-13 trace 接线（D8，`cli.py` + 测试）

1. `run_parser.add_argument("--trace-dir", help="输出六层逐日快照目录（默认关闭）")`。
2. `BacktestConfig(..., dump_layers_dir=Path(args.trace_dir) if args.trace_dir else None)`。
3. trace 目录的 `manifest.json` 由 T-12 自动同写（`dump_layers_dir` 在 targets 中）。
4. `tests/test_trace_completeness.py`（4 项）：
   - 六层文件全部存在（`LAYER_FILES` 逐项）；
   - `L6_nav.csv` 行数 == `len(dm.trade_dates)`；
   - `L1/L2` 列名 == `["date","stock","can_buy","can_sell"]`/`["date","stock","buyable","sellable"]`（长表）；
   - `compare_runs(trace_dir, trace_dir)` → `residual == 0`、`attribution_complete is True`（自差分可消费）。

### T-14 全量验证与文档

- V1-V16 全跑（§5）；
- 四文档：本 IMPL + CHECKLIST 起草（Step 7）；DESIGN 若有回写记 §9；
- 台账：PROGRESS §1.4 / §3.12、CHANGELOG（B3 行为变更、B5 新增文件）、DECISIONS（如需要，本批不新增 ADR——指标口径属 DESIGN 决策，B3 在 CHANGELOG 披露）；
- 提交 + 推送 + 远端 CI。

---

## 5. 验证清单（V1-V16）

| ID | 验证项 | 命令/方式 | 预期 |
|----|--------|-----------|------|
| V1 | 全量测试 | `MPLBACKEND=Agg python -m pytest tests -q` | `550 + 52 = 602 passed`（逐文件核对见 §5 末算术核对） |
| **V2** | black | `python -m black --check .` | `167 files would be left unchanged`（153 + 14 新 py：4 core + 2 辅助 + 8 测试） |
| V3 | mypy 门禁 | `python -m mypy --explicit-package-bases core` | `Success: no issues found` |
| V4 | mypy 盲区 | 追加 `--check-untyped-defs` | `4 errors in 2 files`（不劣化；新增 core 模块 0 error） |
| V5 | 收集数 | `--collect-only -q` | 与 V1 一致 |
| V6 | 参考差分比特一致 | `pytest tests/test_reference_diff.py -q` | 全绿（含 `py_func` 路径） |
| V7 | 事件级等价 | `pytest tests/test_cross_engine_equivalence.py -q` | 5/5（含阴性对照） |
| V8 | 三口径一致 | `pytest tests/test_metrics_single_source.py -q` | 8/8 |
| V9 | B3 Δ 表 | `%TEMP%\p011_b3_delta.py` | 逐字段实测（V2 vol/sharpe 变；V3 sharpe/mdd 变；其余不变） |
| V10 | change_report（B3） | 同一夹具 before/after 运行 + `scripts/change_report.py` | `residual == 0`、`attribution_complete == true`、**六层全零** |
| V11 | manifest 指纹 | 同输入两次 `build_manifest` | `input_fingerprint` 相同；`run_id` 可不同 |
| V12 | 无新依赖 / 不读本地数据 | `git diff pyproject.toml` 空；`Grep pyarrow\|hypothesis\|pandera` 新增代码 0 命中；`Grep data/test_ashare` 8 个新测试文件 0 命中 |
| V13 | CLI | `python cli.py run --help` | 含 `--trace-dir`，exit 0 |
| V14 | trace 完备 | `pytest tests/test_trace_completeness.py -q` | 4/4；`compare_runs` 自差分 residual 0 |
| V15 | 回退演练 | `git revert --no-commit <B3>` 后 `git diff --stat` | 仅 B3 文件回退；`git revert --abort` 复原 |
| V16 | 工作区/CI | `git status --short` + 远端 run | 干净；三 job 全绿 |

> **算术核对（RULE-2）**：新增用例 = 10（invariants）+ 9（reference）+ 5（v2 components）+ 5（equivalence）+ 8（metrics）+ 4（declaration）+ 7（manifest）+ 4（trace）= **52**；预期总数 **602**，V1 中以实测为准并逐文件核对。
>
> **实施实测（Step 9，覆盖上式）**：11 + 9 + 8 + 5 + 9 + 4 + 9 + 4 = **59**；550 + 59 = **609 passed**。差异来源见 §9.2（F-S9-3 新增 ambiguous 用例、参数化展开、E1/E7 补测）。

---

## 6. 回退点

| 批次 | 回退方式 | 影响 |
|------|----------|------|
| B1 | `git revert` 单提交 | 零生产影响（`invariant_mode` 默认 report 仅增字段） |
| B2 | `git revert` 单提交 | 零生产影响（纯测试 + 文档） |
| B3 | `git revert` 单提交 | 报告指标回旧口径；NAV 不变。**注（F-S9-6）**：B4 起声明引用 `cfg.risk_free_rate`，单独回退 B3 时须保留 `config.py` 该字段（实测 1 处行相邻机械冲突，保留 B5 新增行即解，净回退 7 文件） |
| B4 | `git revert` 单提交 | 报告少一组字段 |
| B5 | `write_manifest=False` 或 `git revert` | 不再产出 `manifest.json` |
| B6 | 去掉 `--trace-dir` 或 `git revert` | 回到库内 `dump_layers_dir` |

---

## 7. 会话与门禁

| 项 | 值 |
|----|----|
| Spec_Runner session | `factorv3-p011-backtest-validation-20261110` |
| 门禁 | `probe` / `unit-tests` / `black-check` / `mypy-check` + replay |
| 本地命令 | `$env:MPLBACKEND='Agg'; & <PY312> -m pytest tests -q` |
| commit 纪律 | 每批一提交；消息用 `[System.IO.File]::WriteAllText` 写 UTF-8 无 BOM 临时文件 + `git commit -F`（防 BOM） |
| 远程 | `git push origin master`；CI `.github/workflows/tests.yml` 三版本 |

---

## 8. Step 6 Review（幻觉抑制，独立 pass，2026-11-10）

- **执行时点**: Step 5 正文完稿后的独立 pass；**审查基座 GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash**（RULE-5 异构满足）；本记录与正文非同一次写入（RULE-1）
- **审查方式**: E1（机械计数/grep）+ E3（读码，绑 `@dc71c1a`）+ **E2（numba 编译探针）**；不依赖正文自报

### 8.1 事实核实

| 断言 | 方式/位置 | 结果 |
|------|-----------|------|
| **numba 默认参数可编译**（§2.2 最高风险声明） | **E2** 探针 `%TEMP%\p011_step6_probe.py`：`@njit def f(x, y=0.03)` 默认调用 + 显式调用 | ✅ numba **0.65.1** 本地可用，DEFAULT-PARAM COMPILE: **OK**（M6 stdlib/API 下限教训已过；回退方案保留） |
| `PerformanceAnalyzer()` 旧零参调用兼容 | E1 grep 全仓：8 处调用（examples×2 / agents×3 / tests×2 / analytics:481）全部零参 | ✅ 默认参数新增不破坏任何调用方 |
| `config.py` 已导入 `Literal` | `config.py:13` `from typing import Any, Literal, cast` | ✅（`invariant_mode: Literal[...]` 可直接用） |
| `--profile` CLI 存在（R7 依据） | `prepare_test_fixture.py:212-224`；baseline 支持 `--n-stocks`/`--n-days` | ✅（但**维度下限** MIN_STOCKS=31 / MIN_DAYS=51 → **F-I2**） |
| TradeLog 全量 trades 方法名（T-1 接线） | `execution.py:71-77` `def get_trades(self)` | ❌ 正文原写 `get_all_trades()` **不存在** → **F-I1** 修正 |
| `get_execution_stats` 存在及键集 | `execution.py:426`；L129-150（total_cost/total_amount/total_trades/buy_trades/sell_trades/cost_rate） | ✅ |
| V3 `factor_dict` → `dl.factor_data`（T-5 夹具路径） | `data_v3.py:165-167` `self.factor_data[name] = df.values` | ✅ |
| `_metrics_kernel` 现签名/返回 6 元组；`_generate_results` 用 `self.cfg.get` | `engine_v3_vector.py:155-185`/`:387-410` | ✅（带默认值的新签名可编译，见 E2） |
| B3 需更新的既有断言行号 | `test_v3_engine_integration.py:217`、`test_numba_jit_performance.py:178/:280` | ✅ 与正文一致 |
| engine_v2 现有 import（datetime 缺位） | `engine_v2.py:7-19`（仅 time，无 datetime） | ✅ T-12 需新增 `from datetime import datetime`（实施细节，不影响计划） |
| stdlib 3.10 兼容（M6 教训） | `dataclasses.fields` / `hashlib`（**手工分块**，未用 3.11+ 的 `file_digest`）/ `subprocess.run(timeout=)` / `platform` | ✅ 全部 ≥3.10 |

### 8.2 发现项（5 项，全部回写）

| ID | 等级 | 发现 | 修复 |
|----|------|------|------|
| **F-I1** | **P2** | T-1 接线代码调用 `trade_log.get_all_trades()`——该方法**不存在**（实际为 `get_trades`，`execution.py:71-77`），实施时必然 AttributeError | 接线代码改为 `get_trades()` 并注记 |
| **F-I2** | **P2** | §3.1 R7「60 日×10 股夹具」**不可行**：baseline 下限 `MIN_STOCKS=31` / `MIN_DAYS=51`（`prepare_test_fixture.py:54-55`） | 改为 `--n-stocks 31 --n-days 60`（31 股 × 60 日），注记下限 |
| **F-I3** | **P2** | §1.1 T-0「8 个新测试文件骨架」与批次绿性冲突：B1 若提交 B2-B6 的失败骨架，零数值批次全量验收被破坏 | T-0 收窄为 B1 的 2 个测试文件 + 2 个辅助模块；§3.2 增范围声明（B2-B6 测试在各批次实现前创建）；B2 RED 行同步改为「首跑即 GREEN」 |
| **F-I4** | P3 | §1.2 B3 行「指标 Δ 表（§4.10）」悬空引用（§4 以 T 编号，无 §4.10） | 改为「（T-10）」 |
| **F-I5** | P3 | DESIGN §4.1 `check_return_identity` 签名缺 `initial_capital` 形参（I4 首日基准需要；IMPL T-1 签名正确）——DESIGN↔IMPL 签名不一致 | 回写 [DESIGN §4.1](DESIGN_backtest_validation.md)（Step 6 回写惯例，P-012 先例） |

### 8.3 覆盖与算术核对

- **任务↔批次↔设计映射**：D1→T-0/§1.2、D2→T-1、D3→T-2/T-3/T-4、D4→T-5、D5→T-7~T-10、D6→T-11、D7→T-12、D8→T-13、D9→§1.4 约束表——**9/9 覆盖**，无设计未覆盖的实施、无实施无设计的凭空项。
- **用例算术（RULE-2）**：10+9+5+5+8+4+7+4 = **52**；550+52 = **602** ✅。
- **black 算术**：153 + 14（4 core 新 + `_reference_impl` + `_synth_fixture` + 8 test）= **167** ✅。
- **文件清单↔任务映射**：§2.3 的 14 个新 py / 5 个改 py / 1 个文档逐一有归属任务 ✅。

### 8.4 模板自查（§9.1-9.4）

- [x] 9.1 依赖版本：本批**零新增依赖**（numpy/pandas/numba 既有；E2 证实 numba 0.65.1 可用）；无虚构库
- [x] 9.2 接口签名可实现（E2 numba 默认参数编译 OK；`Literal`/`get_trades` 等 API 逐项核实——F-I1 为唯一误名，已修正）
- [x] 9.3 实施与设计对齐（8.3 映射 9/9；签名不一致 1 处已回写 DESIGN——F-I5）
- [x] 9.4 低效操作排除（§2.4 九项：网格上限、流式哈希、git 子进程、夹具复用、阴性对照等）

**结论**: **P1 = 0；P2 = 3（F-I1/F-I2/F-I3，已修复）；P3 = 2（F-I4/F-I5，已修复）**；9/9 覆盖；算术核对通过；异构基座审查（GLM-5.3-Flash vs DeepSeek-V4.1-Flash）。**P-011 Step 6 Review 通过**，可进入 Step 7（CHECKLIST 起草）。

---

**Review 签字**: GLM-5.3-Flash（独立 pass） 日期: 2026-11-10

---

## 9. Step 9 实施记录（2026-11-10，实施完成后写入）

> 执行方式：单 Agent 自查（RULE-4）；六批各一提交 + 1 个补丁提交。本记录与正文非同一次写入（RULE-1）。环境：Python 3.12.10 / pytest 9.0.3 / black 26.5.0 / mypy 2.1.0 / numba 0.65.1。

### 9.1 提交链

| 批次 | 提交 | 内容 | 行为 |
|------|------|------|------|
| B1 | `cd6d619` | `core/invariants.py`（I1-I7 + `check_all`）、`tests/_reference_impl.py`、`tests/_synth_fixture.py`、`test_invariants.py`（11）、`test_reference_diff.py`（9）；`tracker._take_snapshot` 逐 Position 复制 | 零数值（仅增诊断字段；NAV 标量序列不变） |
| B2 | `26929c6` | `test_v2_components.py`（8）、`test_cross_engine_equivalence.py`（5）、`docs/BACKTEST_CALIBER_MAPPING.md`（5 章） | 零数值 |
| B3 | `9ec9f7d` | `core/metrics.py`、`analytics` 委托、V3 `_metrics_kernel`（rf / 回撤锚点 / `results` 量级） | **行为（报告指标）** |
| B4 | `e59dee2` | `core/validation.py`（能力常量 + 声明）、引擎接线 | 零数值（仅增声明字段） |
| B5 | `beaa3a1` | `core/manifest.py`（序列化 / sha256 / 指纹）、引擎落盘 | 零数值（仅增 `manifest.json`） |
| B6 | `b6bcee3` | `cli.py --trace-dir`、`test_trace_completeness.py`（4） | 零数值 |
| 补丁 | `d270511` | manifest 补 `write_manifest=False`（E1）与 git `OSError`（E7）用例 | 零数值 |

### 9.2 用例数与末态读数（覆盖 §5 的 52/602 预测）

| 文件 | 计划（§5） | 实测 | 差异原因 |
|------|-----------|------|----------|
| `test_invariants` | 10 | **11** | 新增 `test_position_identity_skips_ambiguous_same_day_snapshots`（F-S9-3） |
| `test_reference_diff` | 9 | 9 | — |
| `test_v2_components` | 5 | **8** | `round_lot` 边界参数化 2 组 + 目标持仓 5 项 |
| `test_cross_engine_equivalence` | 5 | 5 | — |
| `test_metrics_single_source` | 8 | **9** | `empty_and_single` 参数化 2 组 |
| `test_validation_declaration` | 4 | 4 | — |
| `test_manifest` | 7 | **9** | E1 开关 + E7 git 不可用 |
| `test_trace_completeness` | 4 | 4 | — |
| **新增合计** | **52** | **59** | 550 + 59 = **609 passed** |
| black | 167 | **167 unchanged** | — |
| mypy 门禁 | Success | **Success: no issues found in 36 source files** | — |
| mypy 盲区 | 4 errors 2 files | **4 errors in 2 files**（不劣化） | 新增 4 个 core 模块 0 error |
| 测试文件 | 68 | **68**（60 + 8） | — |

### 9.3 B3 指标 Δ 表（R7 夹具：31 股 × 60 日；before `@cd6d619`）

| 引擎 | 字段 | before | after | Δ |
|------|------|--------|-------|---|
| V2 | `annual_volatility` | 0.08122845 | 0.08189931 | +6.709e-4（样本基差 N → N−1） |
| V2 | `sharpe_ratio` | −1.45492 | −1.44300 | 随 vol 变化 |
| V2 | `total_return` | — | — | 1 ulp（6.9e-18，浮点路径差） |
| V2 | `annual_return` / `max_drawdown` | — | — | 0 |
| V3 | `max_drawdown` | −0.02965091 | **+0.02965091** | 仅符号（量级约定） |
| V3 | `sharpe_ratio` | 0.93900 | 0.59117 | −0.34783 == rf/vol（rf 0 → 0.03） |
| V3 | 其余 9 字段 | — | — | 0 |
| 两引擎 | NAV / trades / 六层 dump | — | — | **逐值不变** |

### 9.4 归因证据（V10）

`scripts/change_report.py`（git worktree `@cd6d619` vs 当前工作区）：`residual = 0.0`、`attribution_complete = true`、L1-L6 `changed` 全 0。

### 9.5 实施期发现（F-S9-*）

| ID | 等级 | 发现 | 处理 |
|----|------|------|------|
| **F-S9-1** | **P1** | `PositionTracker._take_snapshot` 浅拷贝：快照与实时持仓共享 `Position` 对象，后续调仓/盯市/强平改写历史快照 → 引擎实跑报 53 项 I1/I2 违规 | `tracker.py` 改逐 Position `replace()`；NAV 标量序列与指标零影响 |
| **F-S9-2** | **P2** | numba `@njit` 的 `np.sum` 为顺序累加、NumPy 为 pairwise；参考实现按 `np.sum` 写会末位不等（实测 200 组中 100 组差 1 ulp） | 参考实现改 `_seq_sum` 显式顺序累加；`py_func` 回退仍走 NumPy → 该用例 `rtol=1e-12` 并注明。**远端补正**：CI 无 numba（3.11 首跑 `cash` 差 2.3e-10），主用例同改为「JIT 活跃 → 比特一致；否则 `rtol=1e-12`」（`NUMBA_DISABLE_JIT=1` 本地复跑 9 passed） |
| **F-S9-3** | **P2** | 末日强平在收盘快照后成交并追加同日第二快照 → I2 在末日误报 3 项 | I2 对「同日多快照日期」跳过（同日配对存在歧义）；新增 ambiguous 用例 |
| F-S9-4 | P3 | 阴性对照理论值 `3_750` 错误：`P[1]=25` 时 `0.015×0.5×1e7/25 = 3_000`（3_750 仅在 P=20 且不取整手时成立） | 测试断言 `[7_500, 3_000]`；DESIGN §4.5 / 本 IMPL T-5 已回写 |
| F-S9-5 | P3 | trace 自差分 residual = 1.16e-10（CSV round-trip 浮点噪声），非 0 | 断言改 `< RESIDUAL_TOL(1e-8)`，与 P-012 契约一致 |
| F-S9-6 | P3 | B3 单提交回退在 `config.py` 与 B5 相邻新增行产生 1 处机械冲突；且 B4 声明引用 `cfg.risk_free_rate` | 回退时保留 `risk_free_rate` 字段（§6 已注记）；净回退 7 文件 |
| F-S9-7 | P3 | `check_v3_{nav_identity,static_positions,cost_identity}` 为 DESIGN §4.1 公共诊断 API，当前无调用方与直接单测；I5-I7 由参考差分（B2/B9）覆盖 | 保留并披露（不新增测试，防凑数） |

### 9.6 V1-V16 实测读数

| ID | 实测 | 结论 |
|----|------|------|
| V1 | `609 passed, 138 warnings` | ✅（550 + 59） |
| V2 | `167 files would be left unchanged` | ✅ |
| V3 | `Success: no issues found in 36 source files` | ✅ |
| V4 | `Found 4 errors in 2 files (checked 36 source files)` | ✅ 不劣化 |
| V5 | `609 tests collected` | ✅ |
| V6 | `test_reference_diff` 9 passed（本地 JIT 比特一致；`NUMBA_DISABLE_JIT=1` 复跑 9 passed） | ✅ |
| V7 | `test_cross_engine_equivalence` 5 passed（含阴性对照 `[7_500, 3_000]`） | ✅ |
| V8 | `test_metrics_single_source` 9 passed | ✅ |
| V9 | §9.3 Δ 表 | ✅ 变化仅来自公式 |
| V10 | `residual 0.0` / `attribution_complete true` / 六层 `changed` 全 0 | ✅ |
| V11 | `test_fingerprint_stable` 通过；同输入两次指纹相同 | ✅ |
| V12 | `pyproject.toml` diff 空；新增 14 文件 `pyarrow\|hypothesis\|pandera\|data/test_ashare` 0 命中 | ✅ |
| V13 | `python cli.py run --help` 含 `--trace-dir`，exit 0 | ✅ |
| V14 | `test_trace_completeness` 4 passed；自差分 residual 1.16e-10 < 1e-8（F-S9-5） | ✅ |
| V15 | worktree 演练：B3 提交 8 文件回退，`config.py` 1 处行相邻冲突（保留 B5 行即解）→ 净 7 文件；主工作区零影响 | ✅（含 F-S9-6） |
| V16 | 本地提交后工作区干净；远端 CI 随文档提交推送后回收（CHECKLIST G7） | 待远端 |

### 9.7 与计划的差异汇总

1. **用例数 52 → 59**（§9.2）：均为参数化展开或验收所需的补测，**无为凑数增删**。
2. **参考差分"比特一致"边界**（F-S9-2）：njit 路径严格比特一致；`py_func` 回退因 NumPy pairwise 归约，末位允许 1 ulp（`rtol=1e-12`）。
3. **B2/B4/B5/B6 零数值**：diff 不含 NAV / 指标 / 执行路径（`core/execution.py`、`core/data.py`、`filter/` 0 改动）；B3 对拍 `residual 0` 证明六层未动。
4. **额外修复 1 项 P1**（F-S9-1）：不变量观测网在接入时暴露了快照共享缺陷；修复仅影响诊断快照内容，NAV 标量不变。
