# P-011 回测准确性验证、学术规范与基准比较 · 设计文档

> **文档编号**: DESIGN_backtest_validation
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 3 完稿；**Step 4 Review 通过**（2026-11-10，§13；P1×1 + P2×1 + P3×2 全部回写，审查基座 GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash，RULE-5 异构满足）；可进入 Step 5
> **上游**: [RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md)（Step 2 Review 通过；U-1~U-4 + 合并判定已裁决，见 §11.8）
> **下游**: IMPL_backtest_validation → CHECKLIST_backtest_validation
> **证据时点**: 本仓读数 @ `dc71c1a`（P-012 收官后 HEAD，2026-11-10）；Python 3.12.10；测试基线 `550 passed`
> **档位**: T1（新增 `core/` 3 模块、`tests/` 5 文件、`scripts/cli` 1 处、`docs/` 1 文档；**零新增运行时依赖**）
> **关联 ADR**: ADR-002（三引擎并行）、ADR-003（依赖注入）、ADR-005（T+1）、ADR-007（Numba）、ADR-017（复权口径）

---

## 1. 决策总览

| ID | 决策项 | 决定 | 对应 |
|----|--------|------|------|
| **D1** | 批次切分 | 拆为 **B1-B6 六组、共 6 个独立提交**：B1 不变量 + 参考内核差分（零数值）→ B2 组件差分 + 事件级等价 + 口径映射（零数值）→ **B3 报告口径统一（行为：V2/V3 报告指标受影响字段见 §7.3；NAV 与六层 dump 零变化）** → B4 偏差声明（零数值）→ B5 run manifest（零数值）→ B6 trace 接线（零数值） | U-1（V-A）/ U-2 / U-3 / U-4 |
| **D2** | 不变量体系 | 新增 `core/invariants.py`：I1-I7 纯函数校验；`BacktestConfig.invariant_mode ∈ {off, report, raise}`，默认 `report`（零数值行为，结果增 `invariant_report`） | U-1（V-A） |
| **D3** | 参考实现差分 | 新增 `tests/_reference_impl.py`（按 DESIGN 公式独立编写，非抄内核）+ 固定种子参数网格；V3 `_rebalance_kernel` / V2 `build_target_positions` / `_calculate_cost` / NAV 递推四组差分，**纯函数要求比特一致**；`numba` 路径与 `py_func` 回退路径同参考对拍 | U-1（V-A）+ A17/A18/A19 |
| **D4** | 跨引擎等价 | **事件级等价**（3 日常量价 + 常量信号 + 零费用构造），断言 V2/V3 仓位与 NAV 的**声明差异恒等式**（T+1 vs 同日收盘、`value_buffer=0.985`、整数股），残差必须为 0；附**阴性对照**（删除声明差异后残差必须非 0） | U-4（X-A）+ A27/A28/A30 |
| **D5** | 报告口径统一 | 新增 `core/metrics.py` 单一实现（**含初始锚点 1.0 的回撤公式、量级约定输出**）；`analytics` 委托之；V3 `_metrics_kernel` 增 `risk_free_rate` 参数并**修正回撤缺锚点缺陷**（输出仍为负值原语，`_generate_results` 取量级）；年化分母维持两引擎现状 `252/N`（零变化）；`BacktestConfig.risk_free_rate=0.03`（保留 V2 现值）；报告新增 `metrics_method` 声明 | U-2（S-A）+ P9/A22/A23 + F-R1 |
| **D6** | 偏差声明 | 新增 `core/validation.py`：能力常量（PIT/多重检验/基准）+ `build_validation_declaration()`；报告 `additional_info["validation_declaration"]`，字段**由状态派生、不足处显式 false** | U-2（S-C）+ A22/A23 |
| **D7** | run manifest | 新增 `core/manifest.py`：`manifest.json`（git commit/dirty + 解析后完整配置 + 数据文件 sha256 + 环境/口径 + `input_fingerprint`）；`write_manifest=True` 默认写 `output_dir`，trace 目录开启时同步一份 | U-3（D-B）+ A25/A26 |
| **D8** | 逐日 trace | **复用 P-012 的 `LayerDumper`/`dump_layers_dir`（CSV）**，不新建第二套过程态；`cli.py run` 增 `--trace-dir`；补「dump 完整性」测试；**不采用 parquet** | U-3（D-A）+ A25 |
| **D9** | 范围边界 | **不做** golden 回归（U-D1 挂起）、**不做** V2 同日收盘模式（U-D2）、**不做** DSR/PBO（U-2 已裁决挂起）、**不引入** Qlib/Backtrader/VectorBT 依赖、**不改** P-012 六层 dump 格式与归因链、**不改** V2/V3 成交时点与掩码语义 | §11.8 合并判定 / 职责边界 |

**总量核对**：行为变更批次 = **B3**（1 个，报告指标——V2 变化字段与 V3 变化字段见 §7.3；NAV、交易、六层 dump 不变）；零数值批次 = **B1 / B2 / B4 / B5 / B6**（5 个）。B3 单独成批的理由：它是本设计唯一改动既有数值输出的变更，必须与其他零数值工作隔离归因。

---

## 2. 设计依据

### 2.1 调研结论 → 设计决策映射

| 调研结论 | 设计决策 | 引用 |
|----------|----------|------|
| L1/L2 强、**L3 缺失**、L4 半缺；oracle 问题无通用解，差分/蜕变是可行替代 | D3 参考实现差分 + 蜕变属性（确定性/价格缩放/掩码单调） | RESEARCH §5.1、A13/A17/A18/A19 |
| 不变量对账已有（P2/P12）但**未固化为每引擎必跑** | D2 不变量模块 + `invariant_mode` | RESEARCH §5.1、P2/P12 |
| R-1 跨引擎受控对比曾达 0 差异但**未固化为测试**（P7） | D4 事件级等价（受 F-D1/F-D2 约束收窄，见 §2.4） | RESEARCH P7、§5.1 |
| `sharpe` 双口径（rf=3% vs 0）+ `max_drawdown` 符号相反且 V3 缺回撤锚点（P9 + F-R1 复核发现，E2 实证） | D5 单一口径 + rf 可配置 + 回撤量级约定统一 + 报告声明 | RESEARCH P9、A22/A23 |
| 无多重检验校正（P10）；DSR/PBO 需 trials log | D6 偏差声明显式 `corrected: false`；S-B 挂起 | RESEARCH P10、A9/A10/A11 |
| 数据无 checksum、无 run manifest（P14/P18） | D7 manifest（数据 sha256 + commit + 配置指纹） | RESEARCH P14/P18、A15/A25/A26 |
| 过程诊断缺逐日 trace（P13）；P-012 已实现六层 dump | D8 复用 dump + CLI 暴露 + 完整性测试 | RESEARCH P13、P-012 D6 |
| 外部框架默认口径不同，对拍必然产生假阳性（A27/A28/A29） | D9 仅口径映射文档，不引入依赖 | RESEARCH §5.4、A27-A30 |
| U-1 = V-A（L1/L2 先行）；golden 须在 P-012 口径落地后录制 | D1 B1/B2 先行；golden 延后并登记 U-D1 | RESEARCH §11.1 |
| U-3 = D-A + D-B；trace 与六层 dump 共用一套 | D7 + D8 | RESEARCH §11.3 |
| 独立批次、不同概念分开提交（A30② 受控实验） | D1 六批切分 | RESEARCH §11.5、A30 |

### 2.2 相关 ADR

| ADR | 决策 | 对本设计的影响 |
|-----|------|----------------|
| ADR-002 | 三引擎并行（V1 已移除，V2/V3 定位不同） | D4 只做**事件级**等价，不承诺全历史可比；V3 保留「筛选器」定位 |
| ADR-003 | 依赖注入 + `core/interfaces.py` | D2/D5/D7 的新模块均为纯函数/无状态，不接线到协议 |
| ADR-005 | T+1 执行（pending queue + 次日开盘） | D4 的等价关系必须显式建模 T+1（F-D1） |
| ADR-007 | Numba JIT 加速 V3 | D3 必须覆盖 `njit` 与回退路径；D5 的 kernel 公式改动不得破坏 njit 可编译性 |
| ADR-012 | Spec 驱动开发流程 | 本设计处于 Step 3-4，Review 独立 pass（§13） |
| ADR-017 | 复权三口径与成交/估值 raw | D5 的指标计算输入已是 raw NAV，不涉及复权；manifest 记录 `price_modes` 以固化口径 |

### 2.3 职责边界

**职责内**（验证与报告基建，全部可独立回退）：

- 不变量校验（NAV/持仓/成本/收益恒等）与引擎 report 模式；
- V3 内核、V2 目标持仓/成本函数、NAV 递推的参考实现差分；
- V2↔V3 事件级等价与差异恒等式；
- 报告指标单一口径（Sharpe/年化/rf）与口径声明；
- 偏差声明字段（多重检验/生存偏差/PIT/基准）；
- 运行清单（commit/配置/数据哈希/环境）；
- 逐日 trace 的 CLI 暴露与完整性验收；
- 跨框架口径映射文档（仅文档，不接依赖）。

**职责外**（明确不回答）：

- **不修正**引擎语义缺陷（P-012 已完成；本批只验证，不改变成交时点、掩码、取价、退市逻辑）；
- **不做** PIT 数据层与数据版本轴（P-004 / TD-1 的边界，见 ARCHITECTURE）；
- **不做** 因子显著性统计（DSR/PBO 需 trials log，U-2 已裁决挂起）；
- **不做** 外部框架集成与常驻 CI 对拍（U-4 = X-A）；
- **不做** 性能基准（`tools/benchmark.py` 现有职责，本批不接管）；
- **不改** `core/change_report.py` 的层文件格式与归因链。

**能力边界**（想做但做不到，必须显式声明）：

- 无 PIT 数据 → 只能验证「快照内部一致性 + 快照哈希可追溯」，**不能**验证历史时点数据正确性；
- 无独立 oracle → 差分与蜕变只能**发现不一致**，不能证明「绝对正确」；
- V3 无执行策略/风控/待执行队列 → **不能**作为执行语义基准，只能作为内核计算基准；
- V2 无同日收盘执行模式（F-D1）→ **不能**做全历史逐日对拍（U-D2）。

### 2.4 关键取证与设计约束发现（E3 @`dc71c1a`）

> 本节记录**设计期读码发现**，用于解释本设计为何收窄 RESEARCH 的两项原始主张。全部为静态读码，可在该 commit 上复核。

| ID | 发现 | 位置 | 对设计的影响 |
|----|------|------|--------------|
| **F-D1** | V2 **无「关闭 T+1」配置**：`enable_pending_orders=False` 仍走 `_execute_order_next_open`，订单延至次日开盘；涨跌停/掩码语义不随之改变 | `engine_v2.py:896-900`（policy 路径 else 分支）、`:927-931`（再平衡订单路径）、`:933`（`_execute_order_next_open` 定义）；`rebalance.py:70-72`（daily 触发）（Step 4 F-R2 修正锚点） | RESEARCH §5.1 的「关闭 V2 T+1 后全历史逐日对齐」**不可实现**；D4 降级为**事件级等价**，全历史对拍登记 U-D2 |
| **F-D2** | V2 目标持仓为**整数股**且默认 `value_buffer=0.985`；V3 为**浮点股数**、无 buffer | `target_positions.py:51`、`:130-134`；`engine_v3_vector.py:127` | 等价关系必须显式包含「0.985 缓冲」与「整数取整」两项**声明差异**；构造数据须使取整无损（选可整除价格/资金） |
| **F-D3** | **（Step 4 复核改写，F-R1）** 双引擎指标真实差异为三项：① Sharpe rf：`analytics` 硬编码 0.03、V3 kernel 用 0；② `max_drawdown` **符号约定相反**（V2 `np.max` 正值量级、`tracker.get_performance_metrics` 同为正值；V3 kernel `np.min` 负值），且 **V3 回撤公式缺初始锚点 1.0（`cumprod(1+returns)` 不含 pv[0]），幅度系统性低估**——E2 实证 pv=[100,90,81]：真实回撤 19%，V3 报 −0.1；③ 波动率样本基差：V2 用 N 个快照日收益（含首日 vs 初始资金），V3 用 N−1 个 PV 差分收益。~~原断言「年化分母 N−1 vs N 不一致」被 E2 探针证伪~~：两引擎年化分母**均为 252/N**（`n_days=len(daily_returns)=N`，`_refresh_last_nav` 不产生额外快照） | `analytics.py:74-105`、`:112`（calmar 依赖 mdd>0）、`tracker.py:426/440`；`engine_v3_vector.py:170-185`；`engine_v2.py:430-440`；E2 探针 `%TEMP%\p011_step4_probe.py` | D5 重写：年化分母维持 `252/N`（零变化）；回撤统一**量级约定**（正），`core.metrics` 含锚点公式（与 V2/test_16/calmar/tracker 兼容）；V3 kernel 补锚点（负值原语）+ results 层取量级；V2 变化字段与 V3 变化字段见 §7.3 |
| **F-D4** | `commission_min=5.0` 在 `commission_rate=0` 时仍生效（`max(commission, commission_min)`） | `execution.py:355-356` | 零费用对照必须同时置 `commission_min=0.0`，否则 V2 每笔仍有 5 元成本 |
| **F-D5** | 逐日 trace 已由 P-012 `LayerDumper` 实现，层文件为 **CSV/JSON**；`pyarrow` 未在 `pyproject.toml` 声明 | `change_report.py:20-27`、`:96`；IMPL_p012 F-I3 | D8 **复用 CSV dump**，不新建 parquet 过程态（RESEARCH D-A 的 parquet 建议降级） |
| **F-D6** | V3 信号不经 `FactorPipeline`：直接取 `dl.factor_data` 首个因子；V2 的 `_composite_signal` 经管道处理 | `engine_v3_vector.py:257-277`；`engine_v2.py:274-296` | D4 的构造测试必须**直接注入同值信号**（V2 注入 pipeline/combiner，V3 注入 factor_data），不得依赖默认管道 |

---

## 3. 架构设计

### 3.1 整体架构

```text
                     ┌──────────────────────────────┐
   固定种子参数网格 ─►│ tests/_reference_impl.py (D3) │◄─ DESIGN 公式（非抄内核）
                     │  ref_rebalance_kernel         │
                     │  ref_target_positions         │
                     │  ref_cost / ref_nav_recursion │
                     └──────────────┬───────────────┘
                                    │ 对拍（比特一致）
   V3 _rebalance_kernel ────────────┤
   V3 _metrics_kernel ──────────────┤──────────► core/metrics.py (D5)
   V2 build_target_positions ───────┤              ▲
   V2 _calculate_cost ──────────────┘              │ 单一实现
                                                   │
   V2 Engine ──► tracker snapshots ──► core/invariants.py (D2) ──► additional_info
        │                                    ▲
        ├──► LayerDumper(dump_layers_dir) ───┘ (D8, 复用 P-012)
        │            │
        │            └──► manifest.json (D7) ──► output_dir / trace_dir
        │
        └──► generate_report ──► additional_info["validation_declaration"] (D6)
                                   additional_info["metrics_method"]      (D5)
```

### 3.2 模块划分

| 模块 | 职责 | 输入 | 输出 | 决策 |
|------|------|------|------|------|
| `core/invariants.py`（新） | I1-I7 纯函数校验；违规聚合 | snapshots / trades / positions / PV | `InvariantReport` | D2 |
| `core/metrics.py`（新） | 单一口径指标：年化/波动/Sharpe（rf）/回撤 | `portfolio_value` 序列 + rf | `MetricsResult` | D5 |
| `core/validation.py`（新） | 能力常量 + 偏差声明构造 | cfg / universe_report / metrics | `dict` | D6 |
| `core/manifest.py`（新） | 解析配置 + 数据哈希 + 环境/口径 → `manifest.json` | cfg / data_dir / git | JSON 文件 | D7 |
| `core/analytics.py`（改） | `calculate_performance_metrics` 委托 `core.metrics`；报告增 rf 字段 | snapshots / trades | metrics dict | D5 |
| `core/engine_v3_vector.py`（改） | `_metrics_kernel` 增 rf 参数、年化分母 `n-1`；`_generate_results` 传 rf | PV | results dict | D5 |
| `core/engine_v2.py`（改） | `_generate_results` 组装 `invariant_report`/`validation_declaration`/写 manifest | 组件 | results + JSON | D2/D6/D7 |
| `core/config.py`（改） | `risk_free_rate` / `invariant_mode` / `write_manifest` 三个新字段（均有默认值） | — | dataclass | D2/D5/D7 |
| `cli.py`（改） | `run` 子命令增 `--trace-dir` | CLI args | `dump_layers_dir` | D8 |
| `tests/_reference_impl.py`（新） | 独立参考实现（4 个纯函数） | 数组/映射 | 数组/映射 | D3 |
| `tests/test_invariants.py`（新） | 不变量正例/反例/边界 | 构造数据 | 断言 | D2 |
| `tests/test_reference_diff.py`（新） | 参考差分 + numba/回退 + 蜕变属性 | 参数网格 | 断言 | D3 |
| `tests/test_cross_engine_equivalence.py`（新） | 事件级等价 + 差异恒等式 + 阴性对照 | 构造 3 日数据 | 断言 | D4 |
| `tests/test_metrics_single_source.py`（新） | analytics / V3 kernel / `core.metrics` 三方一致 | PV 序列 | 断言 | D5 |
| `tests/test_manifest.py`（新） | manifest 字段、哈希、序列化、指纹稳定性 | tmp 目录 | 断言 | D7 |
| `docs/BACKTEST_CALIBER_MAPPING.md`（新） | V2/V3/Qlib/Backtrader/VectorBT 口径映射表 + 等价差异 | — | 文档 | D9 |

### 3.3 数据流

1. **验证流**：构造参数网格（固定 `seed`）→ 参考实现与目标函数分别计算 → 断言一致；不变量在引擎 run 结束时读取 `tracker.get_snapshots()` 与 `trade_log` 计算报告。
2. **报告流**：`_generate_results` → `core.metrics`（V2）或 `_metrics_kernel`（V3）→ `additional_info` 增 `metrics_method` / `validation_declaration` / `invariant_report` → `core.manifest.write_manifest` 落 `manifest.json`。
3. **trace 流**：`dump_layers_dir` 非空时，`LayerDumper` 逐日累积、`finalize` 写 6 个层文件；`manifest.json` 同时写入 `output_dir` 与 trace 目录。

### 3.4 控制流

```text
V2 run():
  setup()  -> invariant_mode 解析（off/report/raise）
  loop     -> 每日交易（不改动）
  _generate_results():
      metrics = core.metrics.compute(snapshots.total_value, cfg.risk_free_rate)
      report  = generate_report(...)                     # 委托同一 metrics
      inv     = core.invariants.check_all(...)            # off 时跳过
      decl    = core.validation.build_declaration(...)
      manifest= core.manifest.build(...) -> write(paths)  # write_manifest=True
```

---

## 4. 接口定义

### 4.1 不变量（D2，`core/invariants.py`）

```python
InvariantMode = Literal["off", "report", "raise"]


@dataclass
class Violation:
    code: str              # I1..I7
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


def check_nav_identity(
    snapshots: Sequence[PortfolioSnapshot], *, rtol: float = 1e-9, atol: float = 1e-6
) -> list[Violation]:
    """I1: total_value == cash + Σ position.market_value（逐快照）。"""


def check_position_identity(
    snapshots: Sequence[PortfolioSnapshot], trades: Sequence[Trade], *, atol: float = 1e-6
) -> list[Violation]:
    """I2: 每个快照日的持仓数量 == 截至该日的成交累计（买 +，卖 −）。

    退市结算 / 强制平仓经 `execute_order` 落真实 trade，故同样被计入；
    若未来出现不经 trade 的仓位变更，本不变量应报 I2 而非静默通过。
    """


def check_cost_identity(
    trades: Sequence[Trade], stats: Mapping[str, Any], *, atol: float = 1e-6
) -> list[Violation]:
    """I3: Σ trade.cost == stats["total_cost"]；cost >= 0；
    net_amount == amount + cost（买）/ amount - cost（卖）。"""


def check_return_identity(
    snapshots: Sequence[PortfolioSnapshot],
    initial_capital: float,
    *,
    rtol: float = 1e-9,
    atol: float = 1e-9,
) -> list[Violation]:
    """I4: daily_return(t) == tv(t)/tv(t-1) - 1（首日为 tv/initial - 1）；
    cumulative_return(t) == tv(t)/initial - 1。"""


def check_v3_nav_identity(
    portfolio_value: np.ndarray,
    cash: np.ndarray,
    positions: np.ndarray,
    prices: np.ndarray,
    *, rtol: float = 1e-9, atol: float = 1e-6,
) -> list[Violation]:
    """I5: pv[t] == cash[t] + Σ positions[t] * prices[t]。"""


def check_v3_static_positions(
    positions: np.ndarray, rebalance_indices: set[int], *, atol: float = 1e-12
) -> list[Violation]:
    """I6: 非调仓日 positions[t] == positions[t-1]。"""


def check_v3_cost_identity(
    positions: np.ndarray,
    prices: np.ndarray,
    cash: np.ndarray,
    cost_rate: float,
    *,
    rtol: float = 1e-9,
    atol: float = 1e-6,
) -> list[Violation]:
    """I7: cash 变化 == -Σ Δqty*price - Σ |Δqty|*price*rate（逐日）。"""
```

**引擎接入**：`invariant_mode="report"` 时仅在结果中附 `invariant_report`（违规记 `logger.error`，不中断）；`"raise"` 时首个违规抛 `InvariantViolationError`；`"off"` 零计算。默认 `report`。

### 4.2 指标单一口径（D5，`core/metrics.py`）

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
    max_drawdown: float          # >= 0 量级约定（V2/test_16/calmar/tracker 兼容；F-R1）
    final_value: float
    n_periods: int
    risk_free_rate: float


def compute_metrics(
    portfolio_value: Sequence[float],
    *,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    periods: int = ANNUALIZATION_DAYS,
) -> MetricsResult:
    """由组合价值序列计算指标（唯一口径）。

    公式（N = len(portfolio_value)，要求 N >= 2；`pv0 = portfolio_value[0]`）：
      returns[t]      = (pv[t] - pv[t-1]) / pv[t-1]          # N-1 个差分收益（V3 kernel 现状）
      cumulative[t]   = pv[t] / pv0                          # N 点、含 t=0 锚点 1.0
      total_return    = cumulative[-1] - 1
      annual_return   = (1+total_return)**(periods/N) - 1    # 与两引擎现状一致（252/N），零变化
      annual_vol      = std(returns, ddof=0) * sqrt(periods)
      sharpe_ratio    = (annual_return - risk_free_rate) / annual_vol   # vol=0 → 0
      max_drawdown    = max((cummax(cumulative) - cumulative) / cummax(cumulative))
                        # >= 0 量级约定；含初始锚点，修复 V3 缺 pv[0] 的低估缺陷（F-R1）
    """


def sharpe_ratio(annual_return: float, annual_volatility: float, risk_free_rate: float) -> float:
    """vol <= 0 返回 0.0；不做其它兜底。"""
```

**V3 kernel 对齐**：`_metrics_kernel(portfolio_value, risk_free_rate=DEFAULT_RISK_FREE_RATE)`——签名增 rf；**回撤公式补初始锚点 1.0**（`running_max` 初始化与 drawdown 序列纳入 pv[0]，njit 手写循环内实现；输出仍为负值数学原语，`test_numba` 的范围断言 `-1<=mdd<=0` 不变）；其余公式与上表一致（年化分母 `n`）。`_generate_results`：sharpe 用 `self.cfg.get("risk_free_rate", DEFAULT_RISK_FREE_RATE)`；**`max_drawdown` 输出取量级 `-mdd`**（与 V2/`core.metrics` 报告层对齐，F-R1）。

**归约顺序边界（F-S9-2）**：numba `@njit` 下 `np.sum` 为顺序累加，NumPy `np.sum` 为 pairwise；参考实现须显式逐元素累加才能与 njit 路径**比特一致**。`py_func` 回退路径在 CPython 下仍走 NumPy pairwise，末位可能差 1 ulp（实测 200 组中 100 组），该用例以 `rtol=1e-12` 判定而非 `==`。

**analytics 委托**：`calculate_performance_metrics` 保留现有输出键，`total_return`/`annual_return`/`annual_volatility`/`sharpe_ratio`/`max_drawdown` 取 `compute_metrics`；`sortino_ratio` 沿用现有下行波动公式但 rf 同源；新增键 `risk_free_rate`。V2 相对现状的变化字段：`annual_volatility`（样本基差 N → N−1）、`sharpe_ratio`（随 vol）；`total_return`/`annual_return`/`max_drawdown` 数值不变（浮点路径差 ≤1e-12）；`calmar_ratio`（依赖 mdd>0）与 `max_drawdown_duration` 计算不动。

### 4.3 偏差声明（D6，`core/validation.py`）

```python
SCHEMA_VERSION = "1.0"

# 能力常量：随能力变化而修改，禁止在报告中就地硬编码
PIT_SUPPORTED = False
MULTIPLE_TESTING_SUPPORTED = False
BENCHMARK_SUPPORTED = False          # BacktestConfig.benchmark 仅为占位
WALK_FORWARD_AVAILABLE = True


def build_validation_declaration(
    *,
    risk_free_rate: float,
    universe_report: Mapping[str, Any],
    execution_timing: str,           # V2 = "next_open"
) -> dict[str, Any]:
    """构造可被第三方复核的「本回测不声称什么」声明。

    字段全部来自状态或能力常量；不得写入未经计算的 True。
    """
```

输出结构：

```json
{
  "schema_version": "1.0",
  "multiple_testing": {"corrected": false, "n_trials": null},
  "survivorship": {"corrected": false, "source": "uncorrected"},
  "pit_data": false,
  "benchmark": {"configured": false, "comparable": false},
  "out_of_sample": {"walk_forward_available": true, "used_in_this_run": false},
  "risk_free_rate": 0.03,
  "sharpe_method": "annual_return_minus_rf_over_annual_vol",
  "execution_timing": "next_open",
  "known_limitations": [
    "未做多重检验校正（无 trials 登记）",
    "数据层无 point-in-time 版本轴",
    "基准指数未实现（benchmark 为占位字段）",
    "V2 目标持仓为整数股且含 0.985 现金缓冲系数",
    "V3 为筛选器定位：同日收盘成交、无风控/待执行队列"
  ]
}
```

### 4.4 运行清单（D7，`core/manifest.py`）

```python
MANIFEST_SCHEMA_VERSION = "1.0"


def build_manifest(
    cfg: Any,
    *,
    data_dir: Path,
    data_files: Sequence[str],
    caliber: Mapping[str, Any],
    started_at: datetime,
    finished_at: datetime,
    outputs: Mapping[str, str] | None = None,
    benchmark: str | None = None,     # Step 10 补注（F-A2）：登记 cfg.benchmark 原值
    repo_root: Path | None = None,    # Step 10 补注（F-A2）：默认仓根，测试可注入
) -> dict[str, Any]:
    """构造运行清单。

    - config：dataclass 递归序列化（Path→str、Enum→value、callable→"<callable>"）
    - data：逐文件 {name, exists, sha256, bytes}
    - environment：python/platform/numpy/pandas/numba
    - git：commit / dirty（subprocess 失败 → null，不抛）
    - input_fingerprint：sha256(canonical_json(git.commit, data.sha256, config))
    """


def write_manifest(manifest: Mapping[str, Any], paths: Sequence[Path]) -> list[Path]:
    """写入 0..n 个目标目录的 manifest.json；目录不存在则创建。"""
```

### 4.5 跨引擎等价（D4，`tests/test_cross_engine_equivalence.py`）

构造夹具（**全部由测试内生成，不读 `data/test_ashare`**）：

| 维度 | 取值 | 目的 |
|------|------|------|
| 交易日 | 3 日 | 覆盖 V2 的 T+1 与 V3 的首日跳过 |
| 价格 | `open == close == [10.0, 25.0]` 常量矩阵 | 消除价格漂移，使 NAV 恒等可判定 |
| 信号 | 两股恒定正信号（如 `[1.0, 2.0]`） | 两引擎选中同一集合 |
| 股票数 / top_n / target_count | 2 / 2 / 2 | 等权 `w = 0.5`，避开 `max_weight` 上限（测试配 `max_weight=1.0`） |
| 初始资金 | `10_000_000` | `0.5×1e7/10=500_000`、`/25=200_000`；V2 含 0.985 后为 `492_500`、`197_000`，**均为 100 的整数倍**，整手取整无损（F-D2） |
| 费用 | `commission_rate=0`、`commission_min=0`、`stamp_tax_rate=0`、`slippage_pct=0` | 消除 F-D4 干扰 |
| 掩码 | 全 True | 隔离掩码语义差异 |
| 再平衡 | V2 `daily`；V3 `rebalance_freq=1` | 同一经济事件 |

断言（全部要求残差为 0；`TV=10_000_000`，`P=[10,25]`，`w=0.5`）：

1. `qty_V3 == w × TV / P` = `[500_000, 200_000]`（浮点）；
2. `qty_V2 == floor(0.985 × w × TV / P)` = `[492_500, 197_000]`（整数，且为 100 的整数倍，整手取整无损）；
3. `NAV_V2 == NAV_V3 == 10_000_000` 在全部 3 日成立（常量价下 `rtol=0`）；
4. `cash_V2 - cash_V3 == 0.015 × TV` = `150_000`（零费用下）；
5. **阴性对照**：若按「不含 0.985」比较仓位，残差必须 `== 0.015 × w × TV / P` = `[7_500, 3_000]`（证明测试非空转）。**注（F-S9-4）**：`P=[10,25]` 时第二只股票的精确值为 `0.015×0.5×10^7/25 = 3_000`；原写 `3_750` 对应 `P=20` 且不取整手，属笔误，已按实测回写。

### 4.6 逐日 trace（D8）

```text
python cli.py run --data-dir ... --trace-dir ./output/trace
```

- 映射为 `BacktestConfig(dump_layers_dir=Path(args.trace_dir))`；
- trace 目录内容 = P-012 既有 6 层 CSV/JSON + `manifest.json`；
- 验收：6 个层文件全部存在；`L6_nav.csv` 行数 == 交易日数；`L1/L2` 为长表且只含受限单元格；`scripts/change_report.py` 可直接消费该目录。

---

## 5. 数据结构

### 5.1 `InvariantReport` / `Violation`

见 §4.1。结果落点：`results["additional_info"]["invariant_report"]`，结构 `{mode, checked, violations:[{code,date,detail,value}]}`。

### 5.2 `manifest.json`

```json
{
  "schema_version": "1.0",
  "run_id": "<uuid4>",
  "input_fingerprint": "sha256:<hex>",
  "git": {"commit": "<40 hex 或 null>", "dirty": true},
  "config": {"initial_capital": 10000000.0, "price_modes": {"trade": "raw", "...": "..."}},
  "data": {"dir": "data/test_ashare", "files": [{"name": "close.pkl", "exists": true, "sha256": "<hex>", "bytes": 123456}]},
  "environment": {"python": "3.12.10", "platform": "Windows-...", "numpy": "...", "pandas": "...", "numba": "..."},
  "caliber": {"ruleset_version": "cn_a_2026_07", "price_modes": {}, "next_day_tradable_mode": "ignored", "api_version": "3.1.0"},
  "timestamps": {"started_at": "...", "finished_at": "..."},
  "outputs": {"trades": "trades.csv", "snapshots": "portfolio_snapshots.csv"},
  "benchmark": null
}
```

> **Step 10 补注（F-A2）**：实际实现含 `benchmark` 键（登记 `cfg.benchmark` 原值，未配置为 `null`）——D6 的 `benchmark.configured` 之外，manifest 层保留原始配置便于复现；`repo_root` 为 `build_manifest` 可选参数（默认仓根），不出现在输出中。

**确定性**：`input_fingerprint` 只覆盖 `git.commit`、数据 sha256、配置（不含时间戳/uuid）；同一输入两次运行指纹必须相同，`run_id` 允许不同。

### 5.3 `validation_declaration`

见 §4.3；落点 `results["additional_info"]["validation_declaration"]`。

### 5.4 `metrics_method`

```json
{
  "annualization_days": 252,
  "risk_free_rate": 0.03,
  "annual_return": "(1+total_return)**(252/N)-1, N=len(portfolio_value)",
  "annual_volatility": "std(diff_returns,ddof=0)*sqrt(252)",
  "sharpe_ratio": "(annual_return-risk_free_rate)/annual_volatility",
  "max_drawdown": "max((cummax(pv/pv0)-pv/pv0)/cummax(pv/pv0)), >=0 量级约定（F-R1）"
}
```

---

## 6. 不变式（Invariants）

> 以下为 ADD 审计（Step 10）的可判定依据；每条必须有对应测试。

1. **I1 NAV 恒等**：任一 V2 快照 `total_value == cash + Σ position.market_value`（`rtol=1e-9, atol=1e-6`）。
2. **I2 持仓恒等**：任一快照日的持仓数量 == 截至该日成交累计（买 +、卖 −）；退市结算与强平同样经 trade 计入。**同日多快照日期跳过**（F-S9-3）：末日强平会在收盘快照后成交并追加同日第二快照，该日的「快照 ↔ 成交」配对存在歧义，不计入 I2 判定；判定口径以 `test_position_identity_skips_ambiguous_same_day_snapshots` 固化。
3. **I3 成本恒等**：`Σ trade.cost == execution_stats["total_cost"]`；每笔 `cost >= 0`；`net_amount` 与买卖方向一致。
4. **I4 收益恒等**：`daily_return`/`cumulative_return` 与 NAV 序列递推一致（首日基准为 `initial_capital`）。
5. **I5 V3 NAV 恒等**：`pv[t] == cash[t] + Σ positions[t]*close[t]`。
6. **I6 V3 静态持仓**：非调仓日 `positions[t] == positions[t-1]`。
7. **I7 V3 成本恒等**：`cash[t] - cash[t-1] == -Σ Δqty*price - Σ|Δqty|*price*rate`。
8. **I8 manifest 可恢复**：`config` 序列化后不含不可 JSON 化对象；`manifest.config` 的键集 == `BacktestConfig` 顶层字段集（无静默丢字段）。
9. **I9 口径唯一**：同一 `portfolio_value` 序列在**报告层**的三方输出——`core.metrics.compute_metrics`、V2 `analytics.calculate_performance_metrics`、V3 `_generate_results`——的 `total_return`/`annual_return`/`annual_volatility`/`sharpe_ratio`/`max_drawdown`（量级约定）两两一致（`rtol=1e-12`）；V3 kernel 内部回撤保持负值数学原语（补锚点后幅度 == 报告层量级，F-R1）。
10. **I10 trace 完备**：`dump_layers_dir` 开启时 6 个层文件齐备，`L6_nav.csv` 行数 == 交易日数。

---

## 7. 批次与提交计划

### 7.1 批次表

| 批次 | 内容 | 行为 | 主要交付 | 验收出口 |
|------|------|------|----------|----------|
| **B1** | 不变量 + 参考内核差分 | 零数值 | `core/invariants.py`、`tests/_reference_impl.py`、`tests/test_invariants.py`、`tests/test_reference_diff.py`、`config.py`（`invariant_mode`） | I1-I7 测试全绿；`550 + N passed`；全量 black/mypy 不变 |
| **B2** | 组件差分 + 事件级等价 + 口径映射 | 零数值 | `tests/test_cross_engine_equivalence.py`、`docs/BACKTEST_CALIBER_MAPPING.md` | §4.5 五条断言 + 阴性对照；V2 指标逐字段不变 |
| **B3** | 报告口径统一 | **行为（V2/V3 报告指标，见 §7.3）** | `core/metrics.py`、`analytics.py`、`engine_v3_vector.py`、`tests/test_metrics_single_source.py` | I9；NAV 与六层 dump 零变化；§7.3 对拍表逐字段实测 |
| **B4** | 偏差声明 | 零数值 | `core/validation.py`、`engine_v2.py` 接线、单测 | 声明字段逐项来自状态；缺省即 false |
| **B5** | run manifest | 零数值 | `core/manifest.py`、`engine_v2.py` 接线、`tests/test_manifest.py` | I8；两次同输入指纹相同；数据哈希可复算 |
| **B6** | trace 接线 | 零数值 | `cli.py --trace-dir`、完整性测试 | I10；`change_report.py` 可消费 |

### 7.2 执行顺序

```text
B1 不变量 + 参考差分
  │
  └─► B2 组件差分 + 事件等价 + 口径文档
        │
        └─► B3 报告口径统一（唯一行为批次，独立 change_report）
              │
              └─► B4 偏差声明 ─► B5 manifest ─► B6 trace 接线
```

**任一零数值批次出现数值差异 / B3 出现 NAV 差异 → 停止并回退该批次**，不跨批修补。

### 7.3 B3 的归因方式（行为批次特殊口径）

B3 只改报告指标，不改 NAV，因此 `change_report` 的六层差分应**全零**——这本身是「未触碰执行路径」的证据。指标变化必须另附**指标对拍表**（逐字段实测，提交消息附 CHANGELOG「行为变更」）：

| 引擎 | 字段 | 期望 |
|------|------|------|
| 共同 | `portfolio_value` / 六层文件 | 零变化（`change_report.residual == 0`，`attribution_complete == true`） |
| V2 | `total_return` / `annual_return` | 不变（分母维持 `252/N`；浮点路径差 ≤1e-12） |
| V2 | `annual_volatility` | 变化：样本基差 N 个快照日收益 → N−1 个 PV 差分收益（列实测 Δ） |
| V2 | `sharpe_ratio` | 变化：随 vol（rf 仍 0.03）（列实测 Δ） |
| V2 | `max_drawdown` | 不变（量级约定与现状一致；含锚点公式与 `cumulative_values` 路径同值，≤1e-12） |
| V2 | `calmar_ratio` / `max_drawdown_duration` / `sortino_ratio` | 公式不动（calmar 依赖 mdd>0，量级约定下保持工作） |
| V3 | `total_return` / `annual_return` / `volatility` | 不变（公式未动，≤1e-12） |
| V3 | `sharpe_ratio` | 变化：rf 0 → cfg（默认 0.03）（列实测 Δ 与符号解释） |
| V3 | `max_drawdown` | **变化：符号（−→+ 量级）+ 幅度修正（补初始锚点 1.0，E2 实证首段回撤被漏）**（列实测前后值） |
| 测试 | `test_v3_engine_integration.py:217` | 断言更新 `-1<=mdd<=0` → `0<=mdd<=1`（B3 内完成并披露）；`test_numba_jit_performance.py` 范围断言不变（kernel 保持负值原语，值变仍界内） |

---

## 8. 错误处理

| 场景 | 处理 | 可见信息 |
|------|------|----------|
| 不变量违规（`report` 模式） | 不中断，聚合进 `invariant_report` | `logger.error` + 报告字段 |
| 不变量违规（`raise` 模式） | 抛 `InvariantViolationError` | 首条违规 code/date/detail |
| `portfolio_value` 长度 < 2 | `compute_metrics` 抛 `ValueError` | 明确最小长度要求（V3 kernel 保留返回零值的历史行为，二者差异在测试中显式覆盖） |
| manifest 读取 git 失败（无 git/权限/仓库外） | `git.commit=null`、`git.dirty=null` + warning | 不阻断回测 |
| 数据文件不存在 | `data.files[].exists=false`、`sha256=null`；不抛 | 报告可复算性下降的事实 |
| 配置含不可序列化对象 | callable → `"<callable>"`；未知类型 → `repr()` 并记 warning | 保证 manifest 永远可写 |
| trace 目录不可写 | 由 `mkdir` 抛 `OSError`（fail-fast） | 用户显式指定的路径必须可用 |
| 声明字段无数据来源 | 一律 `false` / `null` 并附 `known_limitations` | 禁止推断为 True |

---

## 9. 替代方案

### 9.1 方案 A：L1/L2 验证基建 + 事件级等价 + 报告治理（**选择**）

- 描述：D2-D8 组合；先固化不变量与参考差分，再以事件级等价校准 V2↔V3，最后统一报告口径并补齐声明/manifest/trace。
- 优点：全部改动可独立回退；差分不依赖外部 oracle；与本仓 L1/L2 已强的格局匹配。
- 缺点：不提供「绝对正确」证明；不覆盖 V2 全历史执行语义。
- 选择理由：RESEARCH §11.1 U-1 = V-A 裁决；A21 分层测试策略；F-D1 使更强主张不可实现。

### 9.2 方案 B：Golden 回归（LEAN 式，**本批否决/延后**）

- 描述：为 3-5 个代表策略录制期望统计 JSON + 容差，CI 比对。
- 优点：防回归能力强；LEAN 工业样板（A6）。
- 否决理由：① U-1 明确 L4 后置；② 无参考实现时 golden 只锁现状（A20），会把任何残余口径缺陷焊死；③ 本批 B3 恰会改变 V3 指标，录制基线会立即作废。改登记 U-D1，触发条件见 §11。

### 9.3 方案 C：外部框架对拍（Qlib/Backtrader/VectorBT，**否决**）

- 描述：同策略在多框架重跑，统计级比对。
- 优点：可对外声明第三方一致性。
- 否决理由：A27/A28 实测默认参数下同策略差 5.5%、需钉死多项默认值才「制造一致」；A29 指出第一根因是成交模型差异；常驻 CI 将引入重依赖与版本联动维护（本仓无此人力）。保留 X-A（口径映射文档）。

### 9.4 方案 D：全历史 V2↔V3 逐日净值对拍（**否决**）

- 描述：关闭 V2 的 T+1/费用/风控后与 V3 逐日对齐（RESEARCH §5.1 原始建议）。
- 否决理由：F-D1 证明 V2 无「同日收盘成交」模式，`enable_pending_orders=False` 仍是次日开盘；要实现须给生产引擎新增执行时点语义（新行为批次，超出验证基建范围）。降级为 D4 事件级等价，登记 U-D2。

### 9.5 方案 E：交互式调试（`--debug`/`pdb`，**否决**）

- 描述：环境变量开启断点/单步。
- 否决理由：无可重放产物、不可入 CI（A18）；本仓 176 处日志 + 6 层 dump 已覆盖事后与过程诊断。

### 9.6 方案 F：parquet 逐日 trace（**否决**）

- 描述：按 RESEARCH D-A 原文用 parquet 存逐日中间态。
- 否决理由：`pyarrow` 未在 `pyproject.toml` 声明（P-012 F-I3），CI `pip install ".[dev]"` 不保证安装；P-012 的 CSV dump 已满足诊断与差分需求（F-D5）。复用不重写。

---

## 10. 对实施的输入

### 10.1 关键工程约束

1. **B1 / B2 / B4 / B5 / B6 零数值**：不得改变任何 NAV、交易、掩码、指标输出；B3 是唯一行为批次。
2. **默认路径不变**：`invariant_mode="report"`、`write_manifest=True`、`risk_free_rate=0.03`、`dump_layers_dir=None` 均不改变既有数值；新增文件写入 `output_dir` 属预期副作用，需在 CHANGELOG 明示。
3. **不引入运行时依赖**：参考实现、不变量、manifest 一律用 `numpy`/`pandas`/`stdlib`；测试不得引入 `hypothesis`/`pandera`（如引入须为 dev-only 且 CI 可跳过）。
4. **不读本地数据目录**：新测试一律使用合成夹具；禁止读 `data/test_ashare`（`.gitignore` 忽略，CI 不可用）。
5. **numba 兼容**：`_metrics_kernel` 新签名必须可被 `@njit` 编译；回退装饰器路径同样要过测试（`getattr(fn, "py_func", fn)`）。
6. **不改 P-012 契约**：六层文件名、列名、CSV 编码、`compare_runs` 语义保持；trace 只做「接线 + 验收」。
7. **manifest 序列化白名单**：`Path`/`Enum`/dataclass/Mapping/Sequence/原始类型；callable 记 `"<callable>"`；禁止 `pickle` 或 `repr` 作为主路径。
8. **数据哈希分块**：1 MiB 流式读取，避免大 pkl 一次性读入内存。
9. **CI 时间预算**：新增测试目标 < 15s（参考差分用 32 组参数网格、≤ 60 股 × 40 日）。

### 10.2 风险与缓解

| 风险 | 缓解 |
|------|------|
| 不变量在真实数据上误报（浮点/Nan 价格/缺失行情） | 默认 `report` 不中断；容差按量级设置（NAV `atol=1e-6`）；先在小样本与 `biased` 夹具验证 |
| 参考实现与内核「同源同错」 | 参考实现按 DESIGN 公式独立编写（禁止复制内核代码）；V2/V3 组件各自有独立参考，形成交叉约束 |
| 事件级等价被构造数据「喂答案」 | 必须包含阴性对照（§4.5-5）；差异恒等式含三项声明差异，缺一即失败 |
| B3 改动报告指标引发下游消费方对账差异 | 消费方清单（E3 已盘点）：V2 侧 `test_16`（test_real_ashare_strict_validation:610，正值锚定——量级约定下不受影响）、`calmar_ratio`（analytics:112，不受影响）、`tracker.get_performance_metrics`（tracker:426，本批不改）；V3 侧 `test_v3_engine_integration:217`（唯一需更新断言，见 §7.3）；单独提交 + CHANGELOG「行为变更」+ §7.3 对拍表；不改变 `portfolio_value`/NAV |
| manifest 泄露敏感信息（路径/配置） | 只记录本地路径与口径，不含 token；数据哈希为单向摘要 |
| 新增 `manifest.json` 影响既有流程对输出目录的假设 | 默认写但不被任何既有代码读取；测试只增不删；回退只需 `write_manifest=False` |
| trace 体积过大 | 默认关闭；仅 `--trace-dir` 显式开启；文档标注长回测的体积风险（U-D3） |
| `_metrics_kernel` 签名变更破坏外部调用 | 新参数带默认值；现有单参调用保持可用；测试覆盖一参/两参两种调用 |

---

## 11. 未决项登记（四元块）与决策矩阵

**11.1 未决项登记**：

- **U-D1 Golden 回归（L4）的启用时点与范围**
  - **判据**：是否已在「参考实现差分 + 口径统一」之后，且存在稳定代表策略（3-5 个）
  - **触发条件**：下一次引擎行为变更前，或需对外发布回测结论时
  - **当前倾向**：本批不做；届时先以 `core/metrics` 输出为期望值、附容差表，并明确「golden 只锁行为、不证正确」（A20）
  - **证据等级**：A6/A20/A21 + RESEARCH §11.1

- **U-D2 V2 同日收盘执行模式（全历史逐日对拍前提）**
  - **判据**：是否存在「必须在全历史逐日对齐 V2/V3」的需求
  - **触发条件**：第三方要求逐日净值一致性，或 V2/V3 内核差异成为争议点
  - **当前倾向**：不新增模式；以事件级等价 + 口径映射替代
  - **证据等级**：E3（F-D1，@`dc71c1a`）

- **U-D3 trace 的采样与保留策略**
  - **判据**：单次 trace 体积是否超过可接受阈值（如 > 500 MB）
  - **触发条件**：出现长区间/全市场 trace 需求
  - **当前倾向**：全量逐日（仅受限单元格 + NAV），不做采样；文档标注体积
  - **证据等级**：E3（`change_report.py:143-247`）

- **U-D4 manifest 在 CI/容器环境的完整性**
  - **判据**：`git.commit` 可获取、数据哈希可复算、指纹跨运行一致
  - **触发条件**：CI 首次运行 B5 后
  - **当前倾向**：git 失败降级为 null；数据缺失降级 `exists=false`；不因环境差异改变口径
  - **证据等级**：E1（实施后 CI 读数）

**11.2 决策矩阵**：不启用。本批决策均为**可逆（Type-2）**——各批次独立 `git revert`，配置字段均有默认值，新增输出不改变既有数值。

---

## 12. 回退点

| 批次 | 回退方式 | 影响 |
|------|----------|------|
| B1 不变量 + 参考差分 | `git revert` 单提交；`invariant_mode="off"` | 零生产影响（默认 report 只增诊断字段） |
| B2 组件差分 + 事件等价 | `git revert` 单提交（纯测试 + 文档） | 零生产影响 |
| B3 报告口径 | `git revert`；或 `risk_free_rate` 置旧值（V3 年化分母需回退代码） | V3 指标回到旧口径；NAV 不变 |
| B4 偏差声明 | `git revert` | 报告少一组字段 |
| B5 manifest | `write_manifest=False` 或 `git revert` | 不再产出 `manifest.json` |
| B6 trace 接线 | 去掉 `--trace-dir` 参数或 `git revert` | 回到仅库内 `dump_layers_dir` |

---

## 13. Step 4 Review（幻觉抑制，独立 pass，2026-11-10）

- **执行时点**: Step 3 正文完稿后的独立 pass；**审查基座 GLM-5.3-Flash ≠ 正文作者基座 DeepSeek-V4.1-Flash**（RULE-5 异构基座满足——跨会话且跨模型家族）；本记录与正文非同一次写入（RULE-1）
- **审查方式**: E1（锚点行号复核）+ E3（读码，绑 `@dc71c1a`）+ **E2（运行时探针）** + 可追溯性矩阵 + 不变式自洽；不依赖正文自报

### 13.1 E1/E3 取证（锚点真实性逐条复核）

| 断言 | 位置 | 结果 |
|------|------|------|
| F-D1：V2 无「关闭 T+1」配置 | `engine_v2.py:896-900`（policy 路径 else 分支）/`:927-931`/`:933`（def）；`rebalance.py:70-72`（daily） | ✅（正文原引 `:904` 不精确 → **F-R2** 修正） |
| F-D2：整数股 + `value_buffer=0.985` | `target_positions.py:51`/`:130-134`；`engine_v3_vector.py:127` | ✅ |
| F-D4：`commission_min` 零费率仍生效 | `execution.py:355-356` | ✅ |
| F-D5：层 dump CSV + 无 pyarrow | `change_report.py:20-27`/`:96`；`pyproject.toml` Grep `pyarrow` **0 命中** | ✅ |
| F-D6：V3 信号不经管道 | `engine_v3_vector.py:257-277`；`engine_v2.py:274-296` | ✅ |
| `_refresh_last_nav` 不产生快照（V2 快照数 = N） | `engine_v2.py:430-440`（仅 `dumper.update_last_nav`，无 `_take_snapshot`） | ✅ |
| V2 回撤正值被测试锚定 | `test_real_ashare_strict_validation.py:610-630`（test_16：`manual_max_dd = np.max(drawdowns)` ≥ 0，`assertAlmostEqual`） | ✅ |
| `calmar_ratio` 依赖 mdd>0 | `analytics.py:112` | ✅ |
| `tracker.get_performance_metrics` 回撤同为正值（第三实现） | `tracker.py:426`/`:440` | ✅ |
| V3 回撤负值被测试锚定 | `test_numba_jit_performance.py:178`/`:280`；`test_v3_engine_integration.py:217` | ✅ |

### 13.2 E2 探针（`%TEMP%\p011_step4_probe.py`，Python312，exit 0）

| 读数 | 结果 |
|------|------|
| V2 `annual_return` 分母 | `252/N` match=**True**；`252/(N-1)` match=False（N=3，`trading_days`=3） |
| V3 kernel `annual_return` 分母 | `252/N` match=**True**（两引擎一致 → 正文原断言「分母不一致」**被证伪**） |
| V2 `max_drawdown` | **+0.19**（正值量级）；`calmar_ratio` = −5.263（= annual/mdd，依赖 mdd>0） |
| V3 kernel `max_drawdown` | **−0.1**（负值），且 pv=[100,90,81] 真实回撤 19% → **缺初始锚点导致幅度低估**（cumprod 序列不含 1.0，首段回撤漏计） |

### 13.3 可追溯性核对

D1→§11.8/§11.5/A30、D2→§5.1/P2/P12、D3→§5.1/A13/A17-A19、D4→§5.4/A27-A30/P7、D5→P9/A22/A23、D6→P10/A9-A11/A22-A24、D7→P14/P18/A15/A25/A26、D8→P13/P-012 D6/A25、D9→§11.4/A27-A30——**9/9 可追溯**；引用的 RESEARCH 条目（A/P/§）全部存在，引用 ADR（002/003/005/007/012/017）全部在 [DECISIONS.md](DECISIONS.md) 登记。

### 13.4 不变式自洽

I1-I8/I10 与 §4 接口定义对照自洽；**I9 与 §4.2 原负值约定、test_16/calmar/tracker 三处消费方冲突**（F-R1）——修正后（量级约定 + 报告层比较）自洽；I2 的「退市/强平经 trade 计入」与 `_force_liquidation → execute_order → tracker.execute_trade`（`engine_v2.py:516-521`、`:580-586`）一致。

### 13.5 发现 4 项（全部回写）

| ID | 等级 | 发现 | 修复 |
|----|------|------|------|
| **F-R1** | **P1** | **F-D3 原断言错误 + 双处遗漏**：①「年化分母 N−1 vs N 不一致」被 E2 探针证伪（两引擎均 252/N）；原 D5「V3 分母改 N−1」+「V2 逐字段 rtol=0」组合**自相矛盾**（分母统一必改 V2）；②遗漏 **max_drawdown 符号约定相反**（V2 正/test_16+calmar+tracker 锚定；V3 负/test_numba+test_v3_engine_integration 锚定）——原 §4.2 负值约定会破坏 test_16 与 calmar；③遗漏 **V3 回撤缺初始锚点（幅度低估）**的实现缺陷 | F-D3 重写（含证伪记录）；D5 重写（分母维持 252/N 零变化；回撤统一**量级约定**；V3 kernel 补锚点 + results 层取量级）；§4.2 公式/MetricsResult/kernel/analytics 段、§5.4、I9、§7.1 B3 行、§7.3 对拍表、§10.2 消费方清单同步 |
| **F-R2** | P2 | F-D1 锚点 `engine_v2.py:904` 不精确（:904 为 `_generate_rebalance_orders` 定义行） | 修正为 `:896-900`/`:927-931`/`:933` |
| **F-R3** | P3 | §4.5-3「NAV(day1)」表述歧义（首日 vs index 1） | 改为「全部 3 日成立」 |
| **F-R4** | P3 | B3 消费方影响面盘点不全（正文只提「下游脚本」） | §10.2 补 E3 消费方清单：test_16 / calmar / tracker:426 / test_v3_engine_integration:217（唯一需更新断言） |

### 13.6 归因扭曲检查（ADR-0001 教训）

§9.3 以 A27/A28（默认参数差 5.5%、「一致是 manufactured」）否决外部对拍——核对 RESEARCH 原文：该否决为**多因**（默认口径差异 + A29 成交模型根因 + A27 对外声明的联动维护成本 + U-4 裁决），非单因裁剪 ✅。

### 13.7 模板自查（§9.1-9.3）

- [x] 9.1 所有设计决策可追溯到 RESEARCH.md（13.3 矩阵 9/9）；无未经验证的假设（E1/E3/E2 重验——**F-R1 即「未验证假设」实例，已被探针捕获并修正**）；无论证驱动的归因扭曲（13.6）
- [x] 9.2 替代方案 ≥2 且均有否决理由（§9 共 5 个否决/延后：golden/外部对拍/全历史对拍/交互式调试/parquet trace）
- [x] 9.3 职责边界清晰（§2.3 「职责外」与「能力边界」分列，各 6/4 项）

**结论**: **P1 = 1（F-R1，已修复）、P2 = 1（F-R2，已修复）、P3 = 2（F-R3/F-R4，已修复）**；9/9 可追溯；不变式自洽（修正后）；异构基座审查（GLM-5.3-Flash vs DeepSeek-V4.1-Flash）。**P-011 Step 4 Review 通过**，可进入 Step 5 实施规划。

---

**Review 签字**: GLM-5.3-Flash（独立 pass） 日期: 2026-11-10
