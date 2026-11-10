# P-014 V2 停牌路径账目缺陷修复 · 实施（Step 5）

> **文档编号**: IMPL_p014_suspension_accounting
> **阶段**: Phase 3 - 实施规划（T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 5 完稿，待 Step 6 Review
> **上游**: [DESIGN_p014_suspension_accounting.md](DESIGN_p014_suspension_accounting.md)（D1-D10 / I1-I5 / §8 Step 4 Review）
> **下游**: CHECKLIST（验收项）
> **门禁 session**: `factorv3-p014-suspension-20261110`

---

## 1. RED 基线读数（Step 9 前实测 @`29cd6fa`）

| ID | 读数 | 命令 / 证据 |
|----|------|-------------|
| R1 | `626 passed, 142 warnings in 37.37s` | `pytest tests -q`（`MPLBACKEND=Agg`） |
| R2 | `171 files would be left unchanged` | `python -m black --check .` |
| R3 | `Success: no issues found in 36 source files` | `python -m mypy --explicit-package-bases core` |
| R4 | `Found 4 errors in 2 files (checked 36 source files)`（不劣化基线） | `python -m mypy ... --check-untyped-defs core` |
| R5 | `tests/*.py` = **73**（70 测试 + 3 辅助） | `(Get-ChildItem tests/*.py).Count` |
| R6 | `CASE_IDS` = **6**（G1-G6） | `tests/_golden_cases.py:36` |
| R7 | `_clamp_sell_quantity` **不存在** | `Select-String` → 0 命中 |
| R8 | `_cancel_next_day_orders` / `_expire_next_day_orders` / `cancel_order` **均不存在** | `Select-String` → 0 命中 |
| R9 | 工作区除本批两份新文档外干净 | `git status --short` |

**目标末态（预测，Step 9 实测修正见 §8）**：`634 passed`（626 + 7 性质测试 + 1 golden G7；若 G7 参数化展开方式不同则按实测修正）/ black 不变 / mypy 0（36）/ 盲区 4 errors 2 files 不劣化 / `tests/*.py` **74**（+1 测试文件）/ `tests/golden/*.json` 7 份。

## 2. 任务分解（T-1 ~ T-7）

| ID | 任务 | 交付物 | 批次 | 行为变更 |
|----|------|--------|------|----------|
| **T-1** | `PendingOrderQueue.cancel_order(order, date) -> bool` | `core/pending.py` | B1 | 否（纯增量） |
| **T-2** | `_clamp_sell_quantity` + 两个执行点接入（作废分支 + 部分数量） | `core/engine_v2.py` | B1 | 是（仅异常状态） |
| **T-3** | `_cancel_next_day_orders` + `_execute_rebalance` 的 `else` 分支（D5 语义对齐） | `core/engine_v2.py` | B1 | 是（被阻断订单不再跨日重试） |
| **T-4** | `_expire_next_day_orders` + 入口调用（D7 生命周期） | `core/engine_v2.py` | B1 | 是（陈旧订单过期） |
| **T-5** | 性质测试 7 项（I1-I5 + 夹紧单测 + 过期单测） | `tests/test_p014_suspension_accounting.py` | B2 | 否（测试） |
| **T-6** | golden G7（停牌场景）：`CASE_IDS`/`CASES`/`build_case` + 录制 | `tests/_golden_cases.py`、`tests/golden/G7.json` | B3 | 否（基线） |
| **T-7** | 基线回归：G1-G6 逐 case 比对，说明 diff 后重录 | `tests/golden/*.json` | B3 | 否（基线） |

## 3. 接口签名与实现要点

### T-1 `core/pending.py`

```python
def cancel_order(self, order: PendingOrder, cancel_date: pd.Timestamp) -> bool:
    """取消单个待执行订单（P-014 D4）。

    只对 PENDING 生效；返回是否实际取消。与 cancel_orders 的批量语义互补。
    """
```

### T-2 `core/engine_v2.py::_clamp_sell_quantity`

```python
def _clamp_sell_quantity(self, order: PendingOrder) -> int:
    if order.side != OrderSide.SELL:
        return order.quantity
    position = self.tracker.get_position(order.stock) if self.tracker else None
    available = int(position.quantity) if position is not None else 0
    available = max(available, 0)
    if available <= 0:
        return 0
    return min(order.quantity, available)
```

接入点：

| 路径 | 现有代码 | 改为 |
|------|----------|------|
| 队列 | `executor.execute_pending_order(order, date, open_price, close_price)` | `qty = self._clamp_sell_quantity(order)`；`qty<=0` → `pending_queue.cancel_order(order, date)` + `continue`；否则 `executor.execute_order(order.stock, order.side, qty, date, open_price, close_price)` |
| 次日 | `executor.execute_order(order.stock, order.side, order.quantity, ...)` | 同上，`qty<=0` → 丢弃该 `order_info` 并 `logger.warning` |

夹紧告警文案（DR-4）：`"卖出数量按可卖持仓夹紧: {stock} 订单={order.quantity} 可卖={available} 实际={qty}"`。

### T-3 `_cancel_next_day_orders`

```python
def _cancel_next_day_orders(
    self, date: pd.Timestamp, stocks: Optional[set[str]] = None
) -> int:
    """撤销次日订单；stocks=None 表示全部。返回撤销数。"""
```

`_execute_rebalance` 中：

```python
if self.pending_queue:
    available_stocks = set(signal_df.columns)
    for stock in available_stocks:
        self.pending_queue.cancel_orders(stock, date)
elif getattr(self, "_next_day_orders", None):
    self._cancel_next_day_orders(date, set(signal_df.columns))
```

### T-4 `_expire_next_day_orders`

```python
def _expire_next_day_orders(self, date: pd.Timestamp) -> int:
    """按 cfg.max_pending_days_{buy,sell} 过期次日订单；返回过期数。"""
```

- 复用 `PendingOrder.is_expired(date, max_days)`（与队列路径完全同语义，含半衰期）；
- 过期时 `order.mark_expired(date)` + `logger.info("次日订单已过期: ...")`；
- 在 `_execute_next_day_orders` 的 `if not self._next_day_orders: return` 之后、取价之前调用。

### T-6 golden G7

```python
"G7": CaseMeta("G7", "v2", "suspend", "V2 停牌：停牌 2 日后恢复，账目满足 I2")
```

构造：20 日 × 3 股真实波动价（与 G2/G3 同源），`suspend[12:14, 1] = 1`，`cost=True`，`suspended=True`，`enable_pending_orders=False`（默认 golden 口径）。

## 4. 低效操作排除

| 潜在低效 | 处置 |
|----------|------|
| 每次执行都查 `tracker.get_position`（dict 查找） | O(1)，可忽略；不做缓存（避免与持仓变动失同步） |
| 过期扫描每日 O(n) | n = 在途订单数，通常 < 10；无额外数据结构 |
| 撤单重建列表 | 单次 O(n) 列表过滤，避免原地删除的索引维护 |

## 5. 兼容性

| 面 | 结论 |
|----|------|
| 公开接口 | 仅新增 `cancel_order`；`execute_pending_order` 保留（fallback 仍用） |
| 配置 | 不改 `BacktestConfig`；复用既有两个 `max_pending_days_*` |
| Python 下限 | 仅用 `Optional` / `set[str]`（`from __future__ import annotations` 已存在） |
| golden schema | 不变（仍 schema 1.0，新增 1 个 case） |

## 6. 验证计划（V1-V13）

| ID | 验证 | 方法 |
|----|------|------|
| V1 | 全量回归 0 fail | `pytest tests -q` |
| V2 | 三层门禁不劣化 | black / mypy / 盲区 |
| V3 | 失败态先记录（F5 红） | 新测试在修复前运行，记录非零退出与关键失败行 |
| V4 | 修复后性质测试全绿 | `pytest tests/test_p014_suspension_accounting.py -q` |
| V5 | 停牌场景 I2 = 0（两条路径） | 测试断言 `invariant_report.ok` |
| V6 | 无负持仓 | 遍历快照断言 `quantity >= 0` |
| V7 | 无同键重复成交 | trades 去重断言 |
| V8 | 卖出不超持仓 | 重放断言 |
| V9 | 订单过期生效 | 单测 + 运行时队列快照 |
| V10 | 夹紧单测（0 / 部分 / 足额） | 单测 |
| V11 | G7 基线可重现（两次录制 SHA256 一致） | 录制脚本跑两次 |
| V12 | `core/` 改动范围仅 `engine_v2.py` + `pending.py` | `git diff --stat` |
| V13 | CI 三版本全绿 | `gh run watch` |

## 7. 风险与回退点

| 风险 | 缓解 |
|------|------|
| G3 等既有基线变化 | 逐 case 比对；在 §8 记录「改前/改后 + 合理性」；不无脑重录 |
| 夹紧告警在正常回归中出现 | 全量测试期间 grep 告警文案；出现即视为异常 |
| 撤单影响「目标未变」的标的 | 与队列路径行为一致（D5）；以 U-P014-2 记录 |

**回退点**：T-1~T-4 为独立编辑块，可分层回退（先回 T-3，再 T-4，最后 T-2）；回退后最坏恢复当前行为，不损坏基线数据。

## 8. Step 6 实施规划 Review 结论（2026-11-10）

> **审查基座**: DeepSeek-V4.1-Flash（同基座）；RULE-4 = 自查（单视角）

| 检查项 | 方法 | 结果 |
|--------|------|------|
| R1-R9 复录自洽 | E1 本会话实测 | ✅ 626 / 171 / 36 files / 4 errors 2 files / 73 / CASE_IDS=6 / 三个新符号 0 命中 / 工作区仅 2 份新文档 |
| 依赖版本真实存在 | 无新增三方依赖 | ✅ N/A（仅 stdlib） |
| stdlib API 下限 | 检查 `set[str]` / `Optional` / `max` | ✅ 3.10+（项目 requires-python 3.10） |
| API 签名可实现 | 回读 `tracker.get_position` / `PendingOrder.mark_*` / `cfg.max_pending_days_*` | ✅ 全部存在（`tracker.py:271`、`pending.py:184-200`、`config.py:375-376`） |
| 无虚构函数 | 检查 §3 全部调用 | ✅ |
| 低效排除表非空 | §4 | ✅ 3 条 |
| 任务覆盖 D1-D10 | 双向核对 | ✅ D1→T-2/T-3/T-4；D2→T-2；D3→T-1；D4→T-1；D5→T-3；D6→T-2；D7→T-4；D8→无任务（正确）；D9→T-6；D10→T-5 |

**发现（2 项，已回写）**

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-I-P014-1 | P2 | T-6 目标末态预测「634 passed」未考虑 `test_golden_baseline` 对 G7 的参数化展开方式（可能 +1），且未计 `test_all_cases_present` 的集合断言是否仍成立 | §1 已注明「按实测修正」；Step 9 以实测回填 |
| F-I-P014-2 | P3 | §3 未写明夹紧在「持仓已被其他订单消耗」时的执行顺序语义（同一日多笔卖单按队列顺序依次夹紧） | §3 T-2 已补「按队列顺序逐笔夹紧」 |

**结论**：P1=0 / P2=1（已回写）/ P3=1（已回写）；**可进入 Step 7 CHECKLIST**。

## 9. Step 9 实施记录（2026-11-10）

### 9.1 F5 先失败记录（红 → 绿）

| 阶段 | 命令 | 读数 | 关键失败行 |
|------|------|------|-----------|
| **红**（修复前代码 @`29cd6fa`，最终 8 项测试集） | `git worktree add <tmp> 29cd6fa` + 复制测试文件 + `pytest tests/test_p014_suspension_accounting.py -q` | **7 failed, 1 passed**（exit=1） | `I2 违规 5 项: 600000 持仓=-400.0 != 成交累计=-218000.0`；`assert 'EXECUTED' == 'CANCELLED'`；`assert 1 == 0`（次日路径仍成交）；`两路径净值差异过大: 13186607.36 vs 9926472.07`；3 × `AttributeError`（三个新方法不存在） |
| **绿**（修复后工作区） | `pytest tests/test_p014_suspension_accounting.py -q` | **8 passed**（exit=0） | — |

> 说明：红阶段唯一通过的是 `test_accounting_properties[queue]`——队列路径修复前已无 I2 违规（与 RESEARCH §4.2 一致），该用例正是「生产默认路径不受影响」的对照证据。

### 9.2 全量门禁实测（@ 修复后工作区）

| 读数 | 实测 | 与预测 |
|------|------|--------|
| pytest | **635 passed, 152 warnings in 42.26s** | 预测 634 → 实测 635（新增 8 性质测试 + 1 G7；F-I-P014-1） |
| black | `172 files would be left unchanged` | 171 + 1 新测试文件 ✅ |
| mypy | `Success: no issues found in 36 source files` | 0 ✅ |
| 盲区 | `Found 4 errors in 2 files (checked 36 source files)` | 不劣化 ✅ |
| `tests/*.py` | **74** | 73 + 1 ✅ |
| 生产代码范围 | `core/engine_v2.py` / `core/pending.py` / `core/interfaces.py` | 协议补声明属必要派生（DR-1） |

### 9.3 golden 基线影响（A20/D10）

| case | 结论 | 证据 |
|------|------|------|
| G1 / G2 / G4 / G5 / G6 | **数值完全一致**（metrics/nav/trades 三项逐值相等） | 全量复录后与仓内 JSON 比对 `IDENTICAL` |
| **G3** | **行为变更**：trades `56 → 55`、`final_value 10286486.93 → 10286475.48`（rel `1.11e-6`）、`total_return 0.0286486931 → 0.0286475482` | 合理性：G3 在涨停日（01-16）被阻断的 300 股买单，旧行为在次日无条件重试成交；新行为在当日再平衡时撤销旧单、按当日目标重新决策 → 少 1 笔交易、NAV 差约 11 元（占初始资金 1.1e-6）。与队列路径（生产默认）语义一致 |
| G7 | **新增**：`total_return=-0.0070155673`、`nav.len=21`、`trades=55`、`cost=59868.6380` | 停牌 2 日后恢复，`_run_v2` 的不变量 fail-fast 通过（I2 零违规） |

### 9.4 实施期发现（F-S9-P014-1 ~ F-S9-P014-5）

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| **F-S9-P014-1** | P2 | `tests/test_decoupled_engine.py::MockExecutionSimulator.execute_order` 签名为 `(stock, side, quantity, date, price, **kwargs)`，与 `IExecutionSimulator` 协议的 `(open_price, close_price=None, ...)` 不一致；改为按协议传 6 个位置参数后该 mock 直接 `TypeError`，使注入测试 0 成交 | 修正 mock 签名并显式 `price = open_price`；协议本身未变 |
| **F-S9-P014-2** | P2 | `IPendingOrderQueue` 协议缺 `cancel_order`，引擎经由协议类型调用触发 mypy `attr-defined` | 协议补声明（`interfaces.py`），实现与协议同步 |
| **F-S9-P014-3** | P3 | `scripts/record_golden.py --out-dir` 指向仓外目录时 `path.relative_to(REPO_ROOT)` 抛 `ValueError`，往仓外录制不可用 | **未修**（不属本批目标）；记录为已知限制；本批用仓内临时目录完成复录比对后删除 |
| **F-S9-P014-4** | P3 | G3 的 `description` 仍写「+ 停牌」，但 P-013 已把停牌撤出该 case（实际由 G7 承担） | 已更正为「V2 掩码：涨停（开盘价触及限幅）」 |
| **F-S9-P014-5** | P3 | 预测用例数 634 与实测 635 不符（性质测试最终 8 项 + G7 1 项；初稿按 7 项估算） | 已按实测回填 §1 / §9.2 与 CHECKLIST D4 |

### 9.5 复现场景修复前后对照（E2，同一脚本切布尔量）

| 读数 | 修复前（次日路径） | 修复后（次日路径） | 修复后（队列路径） |
|------|---------------------|---------------------|---------------------|
| 01-22 600000 成交 | `SELL 113600` + `SELL 338600` ×2 | **`SELL 338600` 一笔** | `SELL 338600` 一笔 |
| 收盘持仓 | **-113600** | 0 | 0 |
| I2 违规 | **5 项** | **0** | 0 |
