# 再平衡未平仓（CRITICAL）修复 · 设计文档

> **文档编号**: DESIGN_critical_rebalance_fix
> **阶段**: Phase 1 - 设计（Spec-driven Development）
> **日期**: 2026-10-21
> **状态**: 已完成（2026-10-23 归档）
> **上游**: [RESEARCH_tech_debt_cleanup.md](RESEARCH_tech_debt_cleanup.md)、2026-10-21 外部评审核验记录
> **下游**: IMPL_critical_rebalance_fix.md → CHECKLIST_critical_rebalance_fix.md

---

## 1. 设计目标

### 1.1 问题复核（设计前已完成的源码级验证）

| 断言 | 源码证据 | 结论 |
|------|----------|------|
| 优化器只返回入选股票 | [portfolio.py:172](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L172)、[portfolio.py:206](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L206) `nlargest/nsmallest(target_count)` | 成立 |
| 目标持仓仅由权重构建 | [engine.py:472-517](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L472-L517)、[engine_v2.py:531-563](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L531-L563) | 成立 |
| 订单只遍历目标持仓 | [engine.py:527](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L527)、[engine_v2.py:627](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L627) | 成立 |
| 仅最后交易日强制平仓 | [engine.py:177](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L177)、[engine_v2.py:330](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L330) | 成立 |
| 队列路径无资金校验 | [execution.py:227-287](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L227-L287) 无现金检查；资金检查只存在于队列关闭时的 [engine.py:635](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L635) | **成立 → 现金可为负** |

**实际失效链**（比外部评审的描述更严重）：

1. 调出股票永不生成卖单 → 旧持仓长期滞留；
2. 滞留持仓仍占用 `total_value`（[tracker.py:283](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L283)），而目标权重之和≈1 全额分配给新入选股票；
3. 买入按 `weight × total_value × 0.985` 全额计算（[engine.py:498](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L498)），叠加存量持仓后**总仓位超过 100%，现金转负**且无人拦截（[tracker.py:430-443](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L430-L443) 的 `validate_positions` 会返回错误列表，但全项目**零调用**，故负现金静默通过）；
4. 最后一个交易日一次性砸盘平仓，制造虚假巨额换手与收益跳变。

因此本缺陷不只是"换手失真"，而是**隐含杠杆 + 净值不可信**。

**溯源新增（T3 阶段实证，CRITICAL-2）**：黄金测试暴露第二个独立缺陷——`Position.execute_trade` 买入时不设置 `market_value`，部分卖出时也不清零（[tracker.py:72-95](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L72-L95)），而 `get_total_value()` 直接累加 `market_value`（[tracker.py:283-290](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L283-L290)）。于是"开盘成交 → 收盘再平衡"的同一天里，`current_value` 严重虚高（实测 197 万 vs 实际 100 万），目标仓位被系统性放大，即便修好清仓逻辑，买入仍会抽干现金。

**决策**：本 spec 一并修复 CRITICAL-2，方式为**以调仓日收盘价重算组合价值**，不修改 `tracker` 语义（`get_total_value()` 还被快照与触发器使用，改动面过大）。详见 §4.2.1。

### 1.2 量化目标

| 目标 | 验收标准 |
|------|----------|
| 调仓后残留持仓 | 无不可卖约束时，`持仓集合 == 目标集合`（0 残留） |
| 现金约束 | 黄金测试中调仓后 `cash >= -1e-6`（不产生隐性杠杆） |
| 两引擎一致 | 同一输入下 V1/V2 目标持仓与订单集合完全相同 |
| 代码收敛 | 目标持仓计算逻辑**只存在一份**（新增 1 模块，2 处调用） |
| 改动规模 | ≤ 3 个源文件 + 2 个测试文件，新增模块 ≤ 120 行 |
| 无新依赖 | pyproject 不变 |
| 回归 | `pytest tests/` 全绿 |

### 1.3 非目标（明确排除，另行立项）

- 前视偏差（涨跌停掩码、替补当日信号、次日停牌）
- 主循环异常吞没 / fail-fast
- ST 及选股类过滤器污染卖出掩码
- 复权命名纠正、`_load_auxiliary_data` 去重
- CLI 从 V1 切换到 V2（TD-3）
- 队列路径资金校验（现金为负的拦截）

---

## 2. 架构设计

### 2.1 现状数据流（缺陷所在）

```
optimizer.optimize(tradable_stocks)
        │  只含 top-N 入选股票（portfolio.py:172）
        ▼
target_weights: Series[stock → weight]
        │
        ▼
for stock, weight in target_weights.items():     ← 缺失"当前持仓 − 目标"差集
        target_positions[stock] = {...}          ← engine.py:472-517
        │
        ▼
_generate_rebalance_orders(target_positions)     ← engine.py:519-553
        │  只遍历 target_positions
        ▼
pending_queue  →  次日开盘执行
```

调出股票自始不在 `target_positions`，故不存在任何卖出路径。

### 2.2 目标数据流

```
optimizer.optimize() ──► target_weights (top-N)
                                │
tracker.get_all_positions() ──► current_positions (含调出股票)
                                │
dm.get_adj_price('close') ────► prices (单次切片)
                                │
                                ▼
              build_target_positions(...)          ← 新增 core/target_positions.py
                                │  取并集：target_weights ∪ current_positions
                                │  调出股票 → target_quantity=0, is_exit=True
                                ▼
                     dict[str, TargetPosition]
                                │
                                ▼
              _generate_rebalance_orders()          ← 两引擎共用调用点
                                │  排序：先 SELL（含清仓/减仓），后 BUY
                                ▼
                        pending_queue → 次日开盘
```

### 2.3 模块职责边界

| 模块 | 职责 | 不做什么 |
|------|------|----------|
| `core/target_positions.py`（新增） | 纯函数：由权重 + 当前持仓 + 价格 + 总资产推导目标数量；整手取整；缓冲系数 | 不建订单、不查掩码、不读配置、不写日志以外副作用 |
| `core/engine.py` / `core/engine_v2.py` | 收集当前持仓与价格、调用纯函数、按 SELL 优先顺序生成订单并入队 | 不再自行计算目标数量 |
| `core/pending.py` | 订单对象与队列语义（不变） | — |
| `core/execution_policy.py` | 保留未来规范化通路（本次不改） | — |

**设计原则**：把"该持有什么"与"怎么下单"解耦，使两引擎共享同一份目标持仓语义，避免同类 bug 第二次分叉。

---

## 3. 方案对比与选型

| 方案 | 做法 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **A：两引擎各自打补丁** | 在 `_execute_rebalance` 中就地遍历当前持仓补 target=0 | 改动最小 | 同一修复写两遍，未来再次分叉（现有 bug 已证明双实现必分叉） | 否决 |
| **B：默认启用 `T1StockPolicy` 通路** | 让 `_execution_policy` 默认非 None，走 `SignalTranslator.from_weights` | 复用已有差集逻辑（[execution_policy.py:426](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L426) 已含 `set(current_positions)`） | **行为面过大**：`from_weights` 不做整手取整（[execution_policy.py:437](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L437) 直接浮点除法）、不施加 0.985 现金缓冲，`create_orders` 用 `int(abs(tq))`（:250）→ 会同时改变仓位规模与资金安全边际；且该通路无 fallback 逻辑 | 本次不采纳，作为后续独立 spec |
| **C：抽取共享纯函数** | 新增 `core/target_positions.py`，两引擎调用 | 修一次、双引擎一致、可单元测试、性能更好（价格只取一次） | 需新增 1 个模块 | **采纳** |

**选型理由**：C 在"最小行为变更"和"消除重复"之间取得平衡。B 的正解（订单差分）其实已被 `SignalTranslator` 实现，但其仓位规模语义与现行回测不同，直接切换会让本次修复无法单独归因——先以 C 修正正确性，再由后续 spec 决定是否迁移到 policy 通路。

---

## 4. 接口定义

### 4.1 数据结构

```python
from dataclasses import dataclass
from typing import Mapping, Optional
import pandas as pd

@dataclass(frozen=True)
class TargetPosition:
    """单只标的的目标持仓（再平衡输入）"""
    stock: str
    current_quantity: int      # 调仓前持仓（股）
    target_quantity: int       # 调仓后目标持仓（股），0 表示退出
    price: Optional[float]     # 调仓日复权收盘价；退出标的可为 None
    weight: float              # 目标权重；退出标的为 0.0
    is_exit: bool              # True = 不在目标权重中、需清仓
```

### 4.2 公开函数

```python
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
        target_weights: 优化器输出，索引为股票代码，值为目标权重（0~1）。
            允许权重和小于 1（余额留现金），不允许出现负权重（A股不做空）。
        current_positions: 当前持仓 {股票: 股数}，股数 > 0。
        prices: 调仓日复权收盘价，索引为股票代码；缺失或 NaN 视为不可定价。
        total_value: 组合总市值（现金 + 持仓市值），必须 > 0。
        round_lot: 是否按整手取整。
        lot_size: 每手股数（A股=100）。
        value_buffer: 现金缓冲系数，沿用现有 0.985 语义。

    Returns:
        {股票: TargetPosition}，包含 target_weights 与 current_positions 的并集；
        仅当 current=0 且 target=0 时省略该股票。

    Raises:
        ValueError: total_value <= 0；或 target_weights 含负权重。

    Note:
        退出标的（is_exit=True）不要求价格有效——清仓数量由 current_quantity
        决定，成交价在次日开盘获取。
    """
```

### 4.2.1 组合价值重算（CRITICAL-2，新增）

```python
def compute_portfolio_value(
    cash: float,
    current_positions: Mapping[str, int],
    prices: pd.Series,
    market_values: Optional[Mapping[str, float]] = None,
) -> float:
    """以最新价格重算组合总价值：cash + Σ(数量 × 价格)。

    Args:
        cash: 现金余额。
        current_positions: 当前持仓 {股票: 股数}。
        prices: 调仓日收盘价；缺失或非正时回退到 market_values。
        market_values: 可选，tracker 记录的市值（仅作为价格缺失时的兜底）。

    Returns:
        组合总价值（非负；无持仓时等于现金）。
    """
```

**存在理由**：`tracker.get_total_value()` 在"成交后、日终盯市前"不可信（见 §1.1 CRITICAL-2）。本函数以价格为准，兜底用市值，保证调仓日估值与日终快照口径一致。

### 4.3 行为契约

| # | 情形 | current | 目标权重 | 价格 | 输出 |
|---|------|---------|----------|------|------|
| 1 | 新进 | 0 | w>0 | 有效 | target = floor(w·V·buffer / price / lot)·lot，is_exit=False |
| 2 | 加仓 | >0 | w>0，target>current | 有效 | 同上 |
| 3 | 减仓 | >0 | w>0，target<current | 有效 | 同上，trade_qty<0 → 卖出差额 |
| 4 | **清仓（核心修复）** | >0 | 无 / w=0 | 任意 | target=0，is_exit=True，卖出全部 current |
| 5 | 权重不足一手 | >0 | w>0，target 取整后=0 | 有效 | 退化为情形 4（全部卖出），避免残仓 |
| 6 | 在场但价格缺失 | >0 | w>0 | NaN/缺失 | 维持现状，不产生订单，记 WARNING |
| 7 | 在场但价格缺失且已被调出 | >0 | 无 | NaN/缺失 | 仍生成 is_exit=True（情形 4 优先于价格缺失） |
| 8 | 空仓未入选 | 0 | 无 | 任意 | 不输出该股票 |
| 9 | 空仓但入选且无可定价 | 0 | w>0 | NaN/缺失 | 不输出（无法计算下单数量，与情形 6 区分：无持仓可维持） |

**权重校验**：权重之和 > 1.0 + 1e-6 时记 WARNING（不抛错，交由优化器约束），因这会直接导致隐性杠杆。

### 4.4 引擎侧调用契约

```python
# 两引擎共用（伪代码，实施阶段落到具体方法）
target_weights = self.optimizer.optimize(tradable_stocks, returns_data)
prices = self.dm.get_adj_price('close', self.cfg.adjustment_type).loc[date]
positions = self.tracker.get_all_positions()
current = {s: int(p.quantity) for s, p in positions.items() if int(p.quantity) > 0}
total_value = compute_portfolio_value(
    self.tracker.get_cash(), current, prices,
    {s: p.market_value for s, p in positions.items()},
)
targets = build_target_positions(
    target_weights, current, prices, total_value,
    round_lot=self.cfg.optimizer.round_lot,
)
self._generate_rebalance_orders(date, targets, date_index)
```

**订单顺序契约**：`_generate_rebalance_orders` 必须先行生成全部 SELL 订单（含清仓与减仓），再生成 BUY 订单。原因：队列路径无资金校验（[execution.py:227-287](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L227-L287)），卖出先成交可在同一开盘把回款计入现金，避免不必要的现金为负。

### 4.5 向后兼容性

| 项目 | 影响 |
|------|------|
| 公开 API | 新增函数与数据结构，不删改现有签名 |
| 引擎行为 | **行为性破坏变更**：历史回测结果将显著变化（这正是修复目的），需在 CHANGELOG 标注 |
| `_generate_rebalance_orders` 入参 | 由 `dict[str, dict]` 改为 `dict[str, TargetPosition]`（内部私有方法，非公开 API） |
| 现有测试 | [test_p0_engine_integration.py:32](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p0_engine_integration.py#L32) 声称"新旧路径一致"，其用例 `current_positions={}`（:78）无法覆盖调出场景；需在该文件补充注释说明适用范围，而非删除 |

---

## 5. 依赖分析

| 类别 | 内容 |
|------|------|
| 运行时依赖 | `pandas`、`numpy`（项目已有，无新增） |
| 内部依赖 | 无。新模块只依赖 `pandas` 与标准库 `dataclasses/typing`，**不 import** `core.config`、`core.tracker`、`core.pending`，以保持纯函数与可测试性 |
| 被依赖 | `core/engine.py`、`core/engine_v2.py` |
| 可选依赖 | 无 |

**设计约束**：新模块不得 import 引擎或配置模块，避免循环依赖（现有 `core/factory.py` 已承担装配职责）。

---

## 6. 性能与资源

| 维度 | 现状 | 设计后 |
|------|------|--------|
| 价格获取 | 循环内每只股票调 `get_adj_price(...)` + `.iloc[date_index, col]`（[engine.py:479-482](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L479-L482)） | 循环外**一次** `.loc[date]` 得到 Series，函数内按代码取值 |
| 时间复杂度 | O(N) 但常数含 DataFrame 列定位 | O(N) 集合运算 + 字典查找，无列定位 |
| 空间 | O(N) | O(N)（每标的 1 个 frozen dataclass） |
| I/O | 无新增 | 无新增 |

N = 当日在场股票数（全 A 约 5000），单次再平衡新增开销可忽略（微秒~毫秒级）。

---

## 7. 错误处理

| 场景 | 处理 | 级别 |
|------|------|------|
| `total_value <= 0` | `raise ValueError`（属于调用方状态错误，不降级） | — |
| `target_weights` 含负权重 | `raise ValueError`（A股不做空，出现即为优化器契约违约） | — |
| 权重和 > 1+1e-6 | 记 WARNING，继续执行 | WARNING |
| 在场标的无可定价 | 跳过该标的（维持现状） | WARNING |
| 退出标的无可定价 | **仍生成清仓订单**（设计要点，见 4.3 情形 7） | INFO |
| 清仓后卖单被掩码拦截 | 由引擎现有逻辑记 `skipped_suspended`；本 spec 增加汇总计数（见 §9） | WARNING |
| 整手取整导致 target=0 但 current>0 | 按清仓处理 | DEBUG |

**降级策略**：新函数不捕获任何异常——它是纯计算，失败必须向上暴露。引擎侧沿用现有 try/except（异常吞没问题不在本 spec 范围，但修复后的清仓订单失败必须可观测，见 §9）。

---

## 8. 变更清单（文件级）

| 类型 | 路径 | 改动范围 | 预计行数 |
|------|------|----------|----------|
| 新增 | `core/target_positions.py` | `TargetPosition` + `build_target_positions` + `compute_portfolio_value`（纯函数，含 docstring） | ~160 |
| 修改 | `core/engine.py` | `_execute_rebalance` 中目标持仓构建段（[472-517](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L472-L517)）→ 调用 helper；`_generate_rebalance_orders`（[519-553](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L519-L553)）改签名并 SELL 优先 | 删 ~45 / 增 ~25 |
| 修改 | `core/engine_v2.py` | 同上（[531-569](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L531-L569)、[625-647](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L625-L647)）；`_generate_orders_via_policy` 分支保持现状（policy 未启用） | 删 ~35 / 增 ~25 |
| 新增 | `tests/test_rebalance_exits.py` | 单元测试 7 + 黄金集成 5 | ~260 |
| 修改 | `tests/test_p0_engine_integration.py` | 类 docstring 补一句"仅覆盖无调出持仓场景"（不改断言） | 1 |
| 不改 | `core/config.py`、`core/portfolio.py`、`core/execution_policy.py`、`core/factory.py`、`core/pending.py` | — | 0 |

**说明**：V1 虽已标记弃用，但 CLI 仍调用它（[cli.py:36](file:///f:/Coding/Factor_Trading_v3.0/cli.py#L36)），故本次两引擎同修；共用 helper 使增量成本仅约 25 行。

---

## 9. TDD 测试设计（Phase 4 红→绿依据）

### 9.1 单元测试（`tests/test_rebalance_exits.py`）

| ID | 场景 | 输入摘要 | 断言 | 初始状态 |
|----|------|----------|------|----------|
| U1 | **调出清仓（核心）** | weights={C:0.5,D:0.5}，current={A:1000,B:1000}，prices 含四只 | `targets['A'].is_exit and targets['A'].target_quantity==0`；B 同理 | RED（函数不存在） |
| U2 | 部分减仓 | weights={A:0.1}，current={A:2000}，A 价格 10，V=1e6 | `0 < target < 2000` 且 `is_exit=False` | RED |
| U3 | 新进整手 | weights={A:0.5}，current={}，A 价格 33.3，V=1e6 | `target % 100 == 0` 且 `target == floor(0.5*1e6*0.985/33.3/100)*100` | RED |
| U4 | 清仓标的无价格 | current={A:500}，weights={}，prices 不含 A | 仍返回 A，`is_exit=True`、`target=0` | RED |
| U5 | 在场但价格缺失且仍在目标中 | current={A:500}，weights={A:0.5}，prices 不含 A | 返回 A 且 `target==current`（不产生交易）| RED |
| U6 | 非法输入 | `total_value=0`；或 weights 含负值 | `pytest.raises(ValueError)` | RED |
| U7 | 空仓未入选 | current={}，weights={A:0.5}，prices 含 B | 结果不含 B | RED |
| U9 | 组合价值重算（CRITICAL-2） | cash=1000，持仓 {A:70}，A 价格 10；另测价格缺失场景 | 有价格时 = 1000+700；价格缺失时回退 `market_values` | RED |

### 9.2 黄金集成测试（同文件，确定性场景）

**固定场景**：4 只股票、4 个交易日、价格恒定（避免随机性）；因子在第 3 个交易日切换：
- 第 1–2 日：A、B 因子靠前 → stub optimizer 返回 `{A:0.5,B:0.5}`
- 第 3 日及以后：C、D 因子靠前 → 返回 `{C:0.5,D:0.5}`
- 再平衡配置：`RebalanceConfig(method="fixed", frequency="daily")`，订单次日开盘成交

| ID | 目标 | 断言 |
|----|------|------|
| G1 | engine_v2 调仓后无残留 | 第 4 日收盘：`get_position('A').quantity == 0`、`B == 0`、`C>0`、`D>0` |
| G2 | engine_v1 同场景（CLI 路径） | 与 G1 完全相同的持仓集合与数量 |
| G3 | 两引擎一致性 | V1 与 V2 的目标持仓字典、订单（股票/方向/数量/日期）逐项相等 |
| G4 | 无隐性杠杆 | 每个成交日结束后 `tracker.get_cash() >= -1e-6` |
| G5 | SELL 优先 | 同一成交日 `executor.trade_log.get_trades()` 的列表顺序中，全部 SELL 记录位置 < BUY 记录位置 |

**测试装配方式**：

- **V2**：使用官方依赖注入（[engine_v2.py:88-101](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L88-L101)）注入 `data_manager` / `universe_filter` / `factor_pipeline` / `optimizer` / `trigger`，无需文件 I/O。注意：注入的 universe 仍会被调用 `build_masks()`（[engine_v2.py:176](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L176)），stub 必须实现该方法。
- **V1**：`setup()` 直接构造组件（[engine.py:87-104](file:///f:/Coding/Factor_Trading_v3.0/core/engine.py#L87-L104)），故用 `unittest.mock.patch` 替换 `core.engine.DataManager / UniverseFilter / FactorPipeline / build_optimizer / build_trigger`，保持 `setup()` 与 `run()` 为被测代码。
- **Fake 组件最小接口**（依据 `IDataManager` / `IUniverseFilter` / `IOptimizer` 协议与引擎实际调用点）：
  - DataManager：`trade_dates`、`stock_codes`、`n_stocks`、`returns`、`get_adj_price(price_type, adjustment_type) -> DataFrame`、`load_factor(name) -> DataFrame`、`get_data_info()`
  - UniverseFilter：`build_masks()`、`buyable / sellable / tradable -> DataFrame`（全 True）
  - FactorPipeline：`process(raw) -> DataFrame`
  - Optimizer：`optimize(scores, returns) -> Series`
  - Trigger：`should_trigger(date, **kwargs) -> bool`
- **配置前提**：`cfg.factor_files` 必须非空（[engine_v2.py:242-244](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L242-L244) 为空时 `_composite_signal` 不会被赋值），黄金测试统一设为 `["dummy.pkl"]` 由 fake `load_factor` 返回固定矩阵。

### 9.3 回归与基准

| 项 | 命令 / 做法 | 通过标准 |
|----|-------------|----------|
| 全量回归 | `pytest tests/ -q` | 全绿 |
| 类型/格式 | `mypy core/`、`black --check core/ tests/` | 无新增错误 |
| 基准对比 | 有本地数据时：修复前后各跑同一 CLI 回测，存档 `output/` 结果 | 差异**必须可解释**：换手率上升、残留持仓归零、现金不再为负；不可解释差异则停止 |
| 无数据时 | 以 G1–G5 作为唯一验收依据，并在文档中记录该限制 | — |

---

## 10. 风险与回滚

| ID | 风险 | 概率 | 影响 | 缓解 |
|----|------|------|------|------|
| R1 | 历史回测结果剧变，与既往结论不可比 | **高（必然）** | 中 | 预期内；CHANGELOG 标注 breaking behavior，基准存档前后对照；旧结论标注"基于缺陷版本" |
| R2 | SELL 优先改变成交顺序，影响资金与成交价 | 中 | 中 | G4/G5 覆盖；黄金测试价格恒定，排除价格干扰 |
| R3 | V1/V2 再次分叉 | 低 | 高 | 目标持仓计算集中到单模块；G3 强一致断言 |
| R4 | 清仓订单被停牌/跌停掩码拦截 → 仍残留 | 中 | 中 | 失败卖单进 `skipped_suspended` 日志；本 spec 增加残留计数上报（见待决 Q2），掩码本身在 P1 spec 修 |
| R5 | 既有测试依赖旧（错误）行为 | 中 | 低 | 逐一评估失败用例；**禁止**为通过而放宽断言；确属旧行为契约的用例更新断言并在 CHANGELOG 记录 |
| R6 | 黄金测试自身不稳定 | 低 | 中 | 固定价格与固定因子，禁用随机数；不依赖文件系统 |

**回滚方式**：本变更为单一 commit（含新模块与两处调用），`git revert` 即可完整回退；无数据/配置迁移，无持久化副作用。

---

## 11. 验收要点（交付 Phase 3 CHECKLIST）

- [ ] `build_target_positions` 行为契约 8 项全部有对应单测（U1–U7 覆盖，情形 2/3 并入 U2）
- [ ] 无不可卖约束时，黄金场景 `持仓集合 == 目标集合`
- [ ] 两引擎目标持仓与订单逐项一致（G3）
- [ ] 现金不为负（G4）
- [ ] SELL 优于 BUY（G5）
- [ ] `pytest tests/` 全绿；`mypy`、`black` 通过
- [ ] 新模块不 import `core.config` / `core.tracker` / `core.pending`
- [ ] CHANGELOG 标注行为性破坏变更；DEVLOG 记录
- [ ] 现有"新旧路径一致"类断言补充适用范围说明

---

## 12. 待决问题（需确认后进入 Phase 2）

| ID | 问题 | 建议 |
|----|------|------|
| Q1 | 修复是否无条件生效（不设 config 开关）？ | **建议无条件**：这是正确性缺陷，开关会让"错误结果"继续可复现，且违反"不添加不必要配置" |
| Q2 | 是否在 `results` 中新增残留持仓诊断字段（如 `unclosed_positions`）？ | **建议加**：约 10 行，直接暴露"卖不掉"的隐藏失败，与本次修复同源 |
| Q3 | CLI 从 V1 切到 V2 是否并入本 spec？ | **建议不并入**：属 TD-3，另立 spec；本 spec 已让两引擎行为一致，切换可独立验证 |
| Q4 | 本地是否有可用于修复前后基准对比的数据集？ | 待确认；无则仅以黄金测试验收，并记录限制 |

