# 再平衡未平仓（CRITICAL）修复 · 实施文档

> **文档编号**: IMPL_critical_rebalance_fix
> **阶段**: Phase 2 - 实施规划（Spec-driven Development）
> **日期**: 2026-10-21
> **状态**: 已完成（2026-10-23 归档）
> **上游**: [DESIGN_critical_rebalance_fix.md](DESIGN_critical_rebalance_fix.md)
> **下游**: CHECKLIST_critical_rebalance_fix.md

---

## 1. 决策确认（Phase 1 待决问题结论）

| ID | 问题 | 决策 | 依据与影响 |
|----|------|------|------------|
| Q1 | 是否设 config 开关 | **无条件修复，不新增配置项** | 正确性缺陷不应保留"错误可复现"的开关；项目规范禁止不必要配置。影响面由 CHANGELOG 标注 breaking behavior 消化 |
| Q2 | 是否增加残留持仓诊断 | **增加 `results['unclosed_positions']`** | 实现方式取最小：`run()` 中最后交易日强平**之前**快照"仍持有且不在最后目标集合"的标的。约 15 行/引擎，零新增类、零新增配置 |
| Q3 | CLI 切换 V2 是否并入 | **不并入** | 本 spec 完成后两引擎行为一致，切换可作为独立变更（TD-3）单独验证与归因 |
| Q4 | 是否有基准对比数据 | **有，可行** | `demo_data/` 含 `close/open/adj/factor_value/factor_momentum/st/suspend/industry/mktcap` 全套 pkl；CLI 默认 `data_dir="./demo_data"`、默认因子 `factor_value.pkl`（[cli.py:38-41](file:///f:/Coding/Factor_Trading_v3.0/cli.py#L38-L41)），可直接跑基线。注意 CLI 走 V1，故基线同时验证 V1 修复 |

**Q4 基线操作**：修复前执行一次 `python cli.py run`，把 `output/` 整体复制为 `output_baseline_before_fix/`（现有 `output/` 为历史未知配置产物，不可直接当基线）；修复后用同一命令重跑，对比 `trades.csv`、`portfolio_snapshots.csv`、`performance_metrics.csv`。

---

## 2. 任务分解

| Task | 内容 | 涉及文件 | 对应测试 | 预计行数 | 前置 |
|------|------|----------|----------|----------|------|
| **T1** | 编写目标持仓单元测试（RED） | `tests/test_rebalance_exits.py`（新增） | U1–U7 | ~120 | — |
| **T2** | 实现共享目标持仓模块（GREEN） | `core/target_positions.py`（新增） | U1–U7、U9 | ~160 | T1 |
| **T3** | 编写两引擎黄金测试（RED） | `tests/test_rebalance_exits.py`（追加） | G1–G5 | +150 | T2 |
| **T4** | engine_v2 接入共享模块（GREEN） | `core/engine_v2.py` | G1、G4、G5 | 删 ~35 / 增 ~30 | T3 |
| **T5** | engine.py(V1) 接入共享模块（GREEN） | `core/engine.py` | G2、G3 | 删 ~45 / 增 ~30 | T4 |
| **T6** | 增加 `unclosed_positions` 诊断 | `core/engine.py`、`core/engine_v2.py` | 新增 U8（诊断单测） | +15 ×2 | T5 |
| **T7** | 修正旧测试适用范围说明 | `tests/test_p0_engine_integration.py` | — | +1 | T5 |
| **T8** | 归档：CHANGELOG / DEVLOG | `CHANGELOG.md`、`docs/DEVLOG.md` | — | ~30 | T6、T7 |

**变更规模**：源文件 3 个（新增 1、修改 2：`engine.py`、`engine_v2.py`），测试文件 2 个（新增 1、修改 1），净增约 300 行（含测试）。与 DESIGN §8 一致，无偏差。

---

## 3. 工程细节

### 3.1 版本约束

| 项 | 约束 | 来源 |
|----|------|------|
| Python | `>=3.10` | [pyproject.toml:10](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L10) |
| pandas | `>=2.0.0` | [pyproject.toml:30](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L30) |
| numpy | `>=1.23.0` | [pyproject.toml:29](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L29) |
| pytest | `>=7.4.0`（dev） | [pyproject.toml:62](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L62) |
| mypy / black | `>=1.5.0` / `>=23.0.0`（dev） | [pyproject.toml:64-66](file:///f:/Coding/Factor_Trading_v3.0/pyproject.toml#L64-L66) |

**不新增任何依赖**，pyproject 不改。

### 3.2 文件结构

```
core/
├── target_positions.py        [新增] TargetPosition + build_target_positions（纯函数，~110 行）
├── engine.py                  [修改] _execute_rebalance 构建段、_generate_rebalance_orders 签名与顺序、run() 诊断快照
├── engine_v2.py               [修改] 同 engine.py（保留 _generate_orders_via_policy 分支不动）
├── tracker.py                 [不改] get_all_positions / get_total_value 已满足
├── pending.py                 [不改]
├── portfolio.py               [不改]
└── config.py                  [不改]

tests/
├── test_rebalance_exits.py    [新增] U1–U8（单元）+ G1–G5（黄金集成），~270 行
└── test_p0_engine_integration.py  [修改] 类 docstring 补适用范围说明（1 行）
```

**约束**：`core/target_positions.py` 只 import `dataclasses`、`typing`、`logging`、`math`、`pandas`；**禁止** import `core.config` / `core.tracker` / `core.pending` / `core.engine*`，以避免循环依赖并保持可单测性。

### 3.3 接口签名（完整版）

```python
# core/target_positions.py
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Mapping, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetPosition:
    """单只标的的目标持仓（再平衡输入）"""
    stock: str
    current_quantity: int
    target_quantity: int
    price: Optional[float]
    weight: float
    is_exit: bool


def build_target_positions(
    target_weights: pd.Series,
    current_positions: Mapping[str, int],
    prices: pd.Series,
    total_value: float,
    *,
    round_lot: bool = True,
    lot_size: int = 100,
    value_buffer: float = 0.985,
) -> dict[str, TargetPosition]:
    """由目标权重、当前持仓与价格推导目标持仓（含调出标的的清仓项）。

    Args:
        target_weights: 优化器输出（index=股票代码, value=权重, 非负）。
        current_positions: 当前持仓 {股票: 股数}，仅含股数 > 0 的标的。
        prices: 调仓日复权收盘价（index=股票代码），缺失/NaN 视为不可定价。
        total_value: 组合总市值（现金 + 持仓市值），必须 > 0。
        round_lot: 是否按整手取整（对应 cfg.optimizer.round_lot）。
        lot_size: 每手股数，A股为 100。
        value_buffer: 买入现金缓冲系数，沿用现有 0.985 语义。

    Returns:
        {股票: TargetPosition}；覆盖 target_weights 与 current_positions 的并集，
        仅省略 current=0 且 target=0 的标的。

    Raises:
        ValueError: total_value <= 0；target_weights 含负权重。
    """
```

**实现分支（伪代码，逐步对应设计 §4.3）**：

```
1. total_value <= 0               -> raise ValueError
2. (target_weights < 0).any()     -> raise ValueError
3. sum(weights) > 1 + 1e-6        -> logger.warning（隐性杠杆风险）
4. universe = set(target_weights.index) | set(current_positions)
5. for stock in universe:
     current = int(current_positions.get(stock, 0))
     weight  = float(target_weights.get(stock, 0.0))
     raw     = prices.get(stock, nan)
     price   = float(raw) if pd.notna(raw) and raw > 0 else None
     if weight <= 0:                       # 情形 4：调出 or 权重为 0
         if current > 0: emit(target=0, is_exit=True)
         continue                           # 情形 8：空仓未入选不输出
     if price is None:                      # 情形 6/9：不可定价
         if current > 0:
             logger.warning(...); emit(target=current, is_exit=False)   # 情形 6：维持现状
         continue                           # 情形 9：空仓且无法定价 → 不输出
     qty = weight * total_value * value_buffer / price
     target = int(math.floor(qty / lot_size) * lot_size) if round_lot else int(qty)
     is_exit = target == 0 and current > 0  # 情形 5：不足一手退化为清仓
     emit(target=target, is_exit=is_exit)
```

**组合价值重算（CRITICAL-2，T2 同批实现）**：

```python
def compute_portfolio_value(
    cash: float,
    current_positions: Mapping[str, int],
    prices: pd.Series,
    market_values: Optional[Mapping[str, float]] = None,
) -> float:
    """cash + Σ(数量 × 价格)；价格缺失或非正时回退 market_values，仍无则跳过该标的。"""
```

实现要点：`tracker.get_total_value()` 在"成交后、日终盯市前"不可信（`Position.execute_trade` 不维护 `market_value`），故调仓估值一律用价格重算；`market_values` 仅作兜底。**不修改 `core/tracker.py`**。

**引擎侧签名变更**（两引擎一致）：

```python
def _generate_rebalance_orders(
    self,
    date: pd.Timestamp,
    targets: dict[str, TargetPosition],   # 原为 dict[str, dict]
    date_index: int,
) -> None:
    """生成再平衡订单：SELL（含清仓/减仓）优先，BUY 在后。"""
```

**引擎侧新增状态**（两引擎 `__init__` 初始化）：

```python
self._last_targets: dict[str, TargetPosition] = {}   # 供 G3 一致性与诊断使用
self._last_target_stocks: set[str] = set()           # target_quantity > 0 的股票集合
self._unclosed_positions: dict[str, int] = {}
```

**`_execute_rebalance` 改动要点**（两引擎相同，替换原目标持仓构建段）：

```python
prices = self.dm.get_adj_price("close", self.cfg.adjustment_type).loc[date]
current = {
    s: int(p.quantity)
    for s, p in self.tracker.get_all_positions().items()
    if int(p.quantity) > 0
}
targets = build_target_positions(
    target_weights, current, prices, self.tracker.get_total_value(),
    round_lot=self.cfg.optimizer.round_lot,
)
self._last_targets = targets
self._last_target_stocks = {s for s, t in targets.items() if t.target_quantity > 0}
self._generate_rebalance_orders(date, targets, date_index)
```

**订单生成顺序**：`_generate_rebalance_orders` 内两趟遍历——第一趟 `trade_qty < 0`（含清仓），第二趟 `trade_qty > 0`。原因见 DESIGN §4.4：队列路径无资金校验，卖出先成交可在同一开盘把回款计入现金。

**诊断快照**（`run()` 中最后交易日、`_force_liquidation` **之前**）：

```python
self._unclosed_positions = {
    s: int(p.quantity)
    for s, p in self.tracker.get_all_positions().items()
    if int(p.quantity) > 0 and s not in getattr(self, "_last_target_stocks", set())
}
```

`_generate_results()` 返回值新增键 `unclosed_positions`（dict，无残留时为空 dict）。

### 3.4 性能注意事项

| 禁止 | 原因 | 替代 |
|------|------|------|
| 循环内调用 `dm.get_adj_price(...)` | 虽有缓存，但每次返回整表 | 循环外一次 `.loc[date]` 得到 Series |
| 循环内 `.iloc[date_index, df.columns.get_loc(stock)]` | 列定位 O(N) | Series 字典式查找 O(1) |
| `DataFrame.iterrows()` / 逐行 `.loc` 赋值 | 已知全项目性能债务（掩码构建处） | 纯 Python dict 运算 |
| 在 `build_target_positions` 内做 I/O 或日志刷屏 | 破坏纯函数性质 | 仅对异常情形打 WARNING |

复杂度：O(N) 时间、O(N) 空间，N = 并集大小（全 A 约 5000），单次再平衡新增开销可忽略。

### 3.5 测试策略

**单元测试（U1–U9）**——`build_target_positions` 全覆盖，见 DESIGN §9.1；补充：

| ID | 场景 | 断言 |
|----|------|------|
| U8 | `unclosed_positions` 诊断 | 构造一个"已调出但仍持有"的场景，`results['unclosed_positions'] == {股票: 数量}` |
| U9 | `compute_portfolio_value` 重算（CRITICAL-2） | `cash=1000`、持仓 `{A:70}`、`A 价格=10` → `1700`；价格缺失且有 `market_values={A:650}` → `1650` |

**黄金集成测试（G1–G5）**——固定 4 股 × 4 日、价格恒定、因子第 3 个交易日切换，见 DESIGN §9.2。

**Fake 组件清单**（最小鸭子类型，按引擎实际调用点）：

| Fake | 必须提供 |
|------|----------|
| FakeDataManager | `trade_dates`、`stock_codes`、`n_stocks`、`returns`、`get_adj_price(price_type, adjustment_type)->DataFrame`、`load_factor(name)->DataFrame`、`get_data_info()` |
| FakeUniverse | `build_masks()`、`buyable`/`sellable`/`tradable` -> 全 True DataFrame |
| FakePipeline | `process(raw)->DataFrame`（原样返回，使 V1/V2 行为对齐） |
| FakeOptimizer | `optimize(factor_scores, returns=None, cov_matrix=None)->pd.Series`（按日期返回固定权重） |
| FakeTrigger | `should_trigger(date, **kwargs)->bool`（每日触发） |

**边界条件清单**：空持仓、权重和为 0、权重和 < 1、负权重（报错）、单价 > 资金（target 取整为 0）、价格 NaN、持仓非整手（清仓卖出全部股数，不再取整）。

**回归命令**：`pytest tests/ -q`、`mypy core/ --ignore-missing-imports`、`black --check core/ tests/`。

---

## 4. TDD 执行顺序

| 步 | 动作 | 预期 RED 现象（用于确认测试真的在测东西） |
|----|------|------------------------------------------|
| 1 | 写 U1–U7 | `ImportError: cannot import name 'build_target_positions'` |
| 2 | 实现 `core/target_positions.py` | U1–U7 全绿 |
| 3 | 写 G1–G5（对当前引擎） | G1 失败：`A.quantity == 1000`（应为 0）；G5 失败：无 SELL 记录 |
| 4 | 改 `engine_v2.py` | G1/G4/G5 绿，G2/G3 仍红（V1 未改） |
| 5 | 改 `engine.py` | G2/G3 绿 |
| 6 | 加 U8 + 诊断实现 | U8 红→绿 |
| 7 | 全量回归 + mypy + black | 全绿；如有旧用例失败，按 DESIGN R5 逐一评估，**不放宽断言** |
| 8 | 基线对比 | `output_baseline_before_fix/` vs 修复后 `output/`：残留持仓归零、换手上升、现金不再为负 |

---

## 5. 提交策略

| # | 建议 commit message | 内容 |
|---|---------------------|------|
| 1 | `test(critical-rebalance): 目标持仓单元测试（RED）` | 仅测试 |
| 2 | `feat(critical-rebalance): 新增共享目标持仓模块（GREEN）` | `core/target_positions.py` |
| 3 | `test(critical-rebalance): 两引擎调仓黄金测试（RED）` | 仅测试 |
| 4 | `refactor(critical-rebalance): engine_v2 接入共享目标持仓` | `engine_v2.py` |
| 5 | `refactor(critical-rebalance): engine 接入共享目标持仓` | `engine.py` |
| 6 | `feat(critical-rebalance): 增加残留持仓诊断字段` | 诊断 + U8 |
| 7 | `docs(critical-rebalance): CHANGELOG/DEVLOG 归档` | 文档 |

**约束**：每个 commit 只含一个 Task；禁止把修复与功能开发混提（对应 DESIGN R1 的可回滚性）。

---

## 6. 风险控制点（对应 DESIGN §10）

| 风险 | 本阶段的控制动作 |
|------|------------------|
| R1 结果剧变 | 修复前存档基线；差异逐项解释（残留归零/换手上升/现金非负），不可解释即停止 |
| R2 SELL 优先副作用 | G4（现金）+ G5（顺序）双断言；黄金测试价格恒定排除价格干扰 |
| R3 两引擎分叉 | 目标持仓计算只存在于新模块；G3 逐项相等断言 |
| R4 卖不掉仍残留 | U8 诊断字段显式上报，不静默 |
| R5 旧测试依赖错误行为 | `pytest` 失败用例逐个评估并在 CHANGELOG 记录；禁止放宽断言 |
| R6 测试不稳定 | 全固定价格与因子，禁用随机、禁用文件 I/O |

---

## 7. 完成标志

1. T1–T8 全部完成，`pytest tests/ -q` 全绿；
2. `mypy core/`、`black --check` 无新增问题；
3. 黄金测试与基线对比结论写入 DEVLOG；
4. 交付 CHECKLIST_critical_rebalance_fix.md（Phase 3），逐项勾选后进入归档。
