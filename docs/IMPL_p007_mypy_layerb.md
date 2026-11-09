# P-007 层 B（引擎 mypy 93 errors 清理） · 实施规划

> **文档编号**: IMPL_p007_mypy_layerb
> **阶段**: Phase 1 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 5 完稿；**Step 6 Review 通过**（2026-11-10；1 P2 + 3 P3 全部回写，见 §10）；可进入 Step 7
> **上游**: [DESIGN_p007_mypy_layerb.md](DESIGN_p007_mypy_layerb.md)（Step 4 通过；D1-D9 / V1-V12）
> **下游**: [CHECKLIST_p007_mypy_layerb.md](CHECKLIST_p007_mypy_layerb.md)
> **证据时点**: 本仓读数 @ `762ff5f`；Python 3.12.10 / mypy 2.1.0 / pytest 9.0.3 / black 26.5.0（E1，2026-11-10 复跑）
> **档位**: T1（`core/` 4 文件 + 1 测试；含 2 项行为变更）

---

## 1. 执行总览

### 1.1 任务分解

| ID | 任务 | 依赖 | 产出 | 验证 |
|----|------|------|------|------|
| T-0 | RED 基线（7 项读数）+ 先落 2 项失败测试 | — | §3 表 + 2 failed | 读数逐项一致 |
| T-1 | D1：`setup()` 入口 fail-fast | T-0 | `core/engine_v2.py` +6 行 | T-B1 转绿；mypy 仍 93 |
| T-2 | D2：协议真实化（`get_snapshots` + `ITradeLog` property） | T-1 | `core/interfaces.py` +12/−1 | 93 → **91** |
| T-3 | D3：`_generate_results` 守卫 + 别名 | T-2 | `engine_v2.py` ±12 | 91 → **86**；T-B2 转绿 |
| T-4 | D4/D5：engine_v2 其余 7 方法窄化 + `all_orders` | T-3 | `engine_v2.py` +30 | 86 → **39** |
| T-5 | D6：`engine_v3_vector` 3 方法窄化 | T-4 | `engine_v3_vector.py` +16 | 39 → **13** |
| T-6 | D7：factory 13 条 | T-5 | `factory.py` +14/−3 | 13 → **0** |
| T-7 | 全量验证 V1-V12 + black | T-1~T-6 | 读数 | §5 全绿 |
| T-8 | 四文档 + 台账 + CHANGELOG + 提交 + 推送 + CI | T-7 | — | V9 / CI 三版本 |

### 1.2 执行顺序

```
T-0 RED（7 读数 + 2 失败测试）
  │
  ├─► T-1 D1 fail-fast（行为，不改 mypy 计数）──► T-B1 绿
  │        │
  │        └─► T-2 D2 接口（-2）──► T-3 D3 守卫（-5）
  │                                   │
  │                                   ├─► T-4 engine_v2 其余（-47）──┐
  │                                   ├─► T-5 v3（-26）─────────────┤
  │                                   └─► T-6 factory（-13）─────────┤
  │                                                                  ▼
  └──────────────────────────────────────────────────────► T-7 全量验证 ──► T-8
```

**任一步 mypy 递减数与 §6 不符 → 立即停止**，按 §7 回退该文件，不跨任务修补。

### 1.3 关键原则

| 原则 | 说明 |
|------|------|
| 接口先真、引擎后窄 | T-2 先让契约变真（B-1/B-2），否则 T-3 的 `_generate_results` 会残留 2 条 |
| 每任务后跑分文件计数 | 用 `mypy core` 的分文件读数验证递减，防止「改了但没消除」 |
| 别名下移到守卫之后 | 有早退守卫的方法，别名放在守卫后（`_try_fallback_order` 的 signal 除外，守卫本身要用）；**零行为 delta** |
| 不做 opportunistic 重构 | 不动 `except Exception`、不动 `setup()` 注解、不改 mypy 配置、不删公开成员 |
| 测试先行且不得弱化 | T-0 先落 2 项失败测试；若实现后仍失败，如实登记，不放宽断言 |

---

## 2. 工程细节

### 2.1 技术栈与版本（E1，2026-11-10）

| 组件 | 版本 | 验证方式 |
|------|------|----------|
| Python | 3.12.10 | `python --version` |
| mypy | 2.1.0（compiled） | `python -m mypy --version` |
| pytest | 9.0.3 | `python -m pytest --version` |
| black | 26.5.0（compiled） | `python -m black --version` |
| numpy / pandas | 2.4.6 / 2.2.3 | `python -c "import numpy, pandas; print(numpy.__version__, pandas.__version__)"`（B7 同口径） |

> **命令约定**：`%PY312%` = `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`；本批所有命令在该解释器下执行，`MPLBACKEND=Agg` 仅测试命令需要。

**零新增依赖**：本批不引入任何库；`typing.TYPE_CHECKING` / `Callable` / `cast` / `Protocol` 均为 3.8+ 标准库能力，CI 最低版本 3.10 满足。

### 2.2 兼容性

| 面 | 结论 |
|----|------|
| Python 3.10 / 3.11 / 3.12（CI 矩阵） | ✅ `list[...]`、`from __future__ import annotations` 均已在本仓使用；无 3.12 专属语法 |
| `core/__init__.py` 对外导出 | 空（TD-1.2 / ADR-016）→ 协议成员变更不改变包级 API |
| 运行时行为 | 仅 2 处：D1（空因子 → `ValueError`）、D3（未 setup 调 `_generate_results` → `RuntimeError`） |
| CI workflow / `pyproject.toml` | **零改动**（D9） |

### 2.3 文件结构

```
core/
├── interfaces.py          # T-2：+TYPE_CHECKING、ITradeLog、property 成员、get_snapshots 签名
├── engine_v2.py           # T-1/T-3/T-4：setup 守卫、_generate_results 守卫、7 方法别名、all_orders 注解
├── engine_v3_vector.py    # T-5：3 方法别名
└── factory.py             # T-6：Callable、9 cast、TYPE_CHECKING 导入
tests/
└── test_mypy_layerb_smoke.py   # T-0 新增：2 项（T-B1 / T-B2）
docs/
├── RESEARCH_p007_mypy_layerb.md
├── DESIGN_p007_mypy_layerb.md
├── IMPL_p007_mypy_layerb.md
├── CHECKLIST_p007_mypy_layerb.md
└── PROGRESS.md
```

### 2.4 外部案例与工程锚点（A31-A34）

| ID | 来源 | Layer | 原文要点（逐字） | 用于 |
|----|------|-------|------------------|------|
| A31 | mypy docs · Protocols §Invariance of protocol attributes | T1（stable） | 「A common issue with protocols is that protocol attributes are invariant.」；「This can be fixed by declaring `content` to be read-only in the `Box` protocol using `@property`」 | T-2 的 property 形态（D2） |
| A32 | mypy docs · Type narrowing | T1（stable） | 「We can also use `assert` to narrow types in the same context」；Casts「mypy casts are only used as hints for the type checker, and they don't perform a runtime type check」 | T-3/T-4/T-5 的 assert 别名；T-6 的 cast 边界 |
| A33 | Dropbox · Our journey to type checking 4 million lines of Python（2019-09-05，Jukka Lehtosalo） | T2（工业实践） | 「Incremental checking really helps when annotating existing code in bulk, as this typically involves numerous iterative mypy runs, as types are gradually inserted and refined.」；「A type checker will find many subtle (and not so subtle) bugs. A typical example is forgetting to handle a `None` value or some other special condition.」 | 逐任务递减验证（§6）；A-1/A-2 的缺陷类型 |
| A34 | pytest docs · How to write and report assertions | T1（stable） | 「The `match` parameter is matched with the `re.search()` function」 | T-B1/T-B2 的 `match=` 断言 |
| — | 本仓 `IMPL_p007_mypy_layera.md` §6 | 内部先例 | 「每步后跑一次分文件计数，确认该步消除的错误数与预期一致；不符即停」 | §6 递减纪律 |

> 复用 Step 3 锚点：A24（mypy 官方增量迁移/按模块收紧）、A29（未注解方法不被检查）、A30（`assert` 是「我很确信」的声明）。

### 2.5 低效/危险操作排除

| 禁止操作 | 原因 |
|----------|------|
| 新增 `# type: ignore` | 违背清理目标（全仓仅 1 处惯例） |
| 修改 `[tool.mypy]` 或 CI `mypy` 步骤 | 读数不可比；CI 仍是 `&#124;&#124; true`（P31） |
| 给 `setup()` 加 `-> None` | Q3=A；会把 9 条盲区错误带进本批 |
| 用 `cast(IDataManager, self.dm)` 代替别名 | A32：cast 无运行时检查；且掩盖「setup 未调用」 |
| 把 `except Exception: continue` 一并删掉 | 改变逐日容错语义，超出本批（DESIGN §7） |
| 全文件重排 / 顺手重命名 / 调整无关 import | 扩大 diff，掩盖真实改动 |
| 在热路径新增运行时校验（如每笔订单检查组件非 None） | 别名只是局部变量读取，零额外开销 |
| 为让测试通过而放宽 `match=` 或改断言 | 违反「测试失败如实登记」 |

---

## 3. T-0：RED 基线（实施前必录）

| ID | 断言 | 命令 | RED 读数 | GREEN 目标 |
|----|------|------|----------|------------|
| RED-1 | 总 errors | `mypy --explicit-package-bases core` | **93 errors in 3 files** | **0** |
| RED-2 | 分文件 | 同上分流 | engine_v2 **54** / v3 **26** / factory **13** | 0 / 0 / 0 |
| RED-3 | 盲区口径 | `mypy --explicit-package-bases --check-untyped-defs core` | **102 errors in 4 files**（engine_v2 61 / data_v3 2 / v3 26 / factory 13） | **8 errors in 2 files**（engine_v2 6 + data_v3 2；T-2 使 L231 转过，Step 6 修正） |
| RED-4 | 全量测试（未含新测试） | `$env:MPLBACKEND="Agg"; python -m pytest tests -q` | **514 passed** | **516 passed** |
| RED-5 | 格式 | `python -m black --check .` | exit 0 | exit 0 |
| RED-6 | `type: ignore` | `Select-String -Path core\*.py,tests\*.py -Pattern "type: ignore"` | **1** | **1** |
| RED-7 | 测试文件数 | `(Get-ChildItem tests -Filter 'test_*.py').Count` | **50** | **51** |

**RED 测试（TDD 先落）**：T-0 末新增 `tests/test_mypy_layerb_smoke.py` 后：

```
2 failed, 514 passed
FAILED test_empty_factor_files_raises_value_error  - DID NOT RAISE <class 'ValueError'>
FAILED test_generate_results_requires_setup       - DID NOT RAISE <class 'RuntimeError'> (AttributeError)
```

> 若 RED 读数与上表不符（如基线漂移），先停下核对 `git status` 与 HEAD，不得直接开工。

---

## 4. 逐任务实施文本

### T-1 D1：`setup()` 入口 fail-fast

**文件**：`core/engine_v2.py` L163-169。

```python
    def setup(self):
        """设置回测引擎

        根据注入的组件或创建默认组件。
        """
        if (
            not self.cfg.factor_files
            and self._injected_pipeline is None
            and self._injected_combiner is None
        ):
            raise ValueError(
                "factor_files 不能为空：BacktestEngineV2 需要至少一个因子文件；"
                "请在 BacktestConfig.factor_files 中指定（至少 1 项）"
            )
        t0 = time.perf_counter()
        logger.info("开始设置回测引擎V2...")
```

| 项 | 内容 |
|----|------|
| 插入点 | `setup` docstring 之后、`t0 = time.perf_counter()` 之前（任何组件创建之前） |
| 不改 | `_precompute_factors` 的 `if not self.cfg.factor_files: warning; return`（防御性，经 setup 不可达） |
| 不改 | `cfg.validate()` 调用（它返回 `list[str]`，不抛；P34） |
| 验证 | T-B1 转绿；`engine.dm is None`（无部分初始化）；mypy 计数不变（93） |
| **Step 9 修正（F-S9-1）** | 无条件守卫使 13 个既有用例失败（注入 `factor_pipeline` + `factor_combiner` 后手工注入信号，`factor_files` 为空）：`test_real_ashare_backtest` 4 failed + `test_real_ashare_strict_validation` 9 errors。守卫条件收紧为「无注入 pipeline/combiner 且 `factor_files` 为空」；默认路径缺陷仍 fail-fast，T-B1 仍成立 |

### T-2 D2：协议真实化（`core/interfaces.py`）

**改动 1**：`interfaces.py:10` 导入行补 `TYPE_CHECKING`，并在 import 段后新增类型导入块：

```python
from typing import TYPE_CHECKING, Any, Optional, Protocol

if TYPE_CHECKING:
    from core.tracker import PortfolioSnapshot
```

**改动 2**：`IPositionTracker.get_snapshots`（L271）：

```python
    def get_snapshots(self) -> list[PortfolioSnapshot]:
        """获取持仓快照"""
        ...
```

**改动 3**：执行层接口之前新增 `ITradeLog`，并给 `IExecutionSimulator` 补只读成员：

```python
class ITradeLog(Protocol):
    """交易日志最小契约（结果生成所需）"""

    def get_trades_df(self) -> pd.DataFrame:
        """获取交易记录 DataFrame"""
        ...


class IExecutionSimulator(Protocol):
    """交易执行模拟器接口"""

    # ... 既有 execute_order / execute_pending_order / get_execution_stats 不变 ...

    @property
    def trade_log(self) -> ITradeLog:
        """交易日志（只读）"""
        ...
```

| 项 | 内容 |
|----|------|
| 顺序 | `ITradeLog` 必须定义在 `IExecutionSimulator` **之前**（同文件解析顺序） |
| 不改 | `ExecutionSimulator`（实现侧仍是普通属性 `self.trade_log = TradeLog()`） |
| 不改 | `MockExecutionSimulator` / `MockPositionTracker`（结构上已满足，Step 4 已核） |
| 验证 | `mypy core` 93 → **91**：L767 `arg-type` 与 L762 `Item "IExecutionSimulator" … trade_log` 各消失 1 条；L762 的 `Item "None"` 仍留到 T-3 |
| 盲口径（Step 6 修正） | flag 下 L231 `PositionTracker`↔`IPositionTracker` assignment 随本任务消失（协议修正后 `PositionTracker` 全成员符合：`Trade`/`Position` 对 `Any` 协变兼容，E3 核对）→ 批后 `--check-untyped-defs` 残差 = **8**（engine_v2 6 + data_v3 2），非 9 |
| 递减容差 | 若 L767 的 `arg-type` 因 `Any` 残留未随 T-2 消失（预期不会），则 T-2 只减 1、T-3 减 6，**总数与最终目标不变**；按实测记录，不调任务顺序 |

### T-3 D3：`_generate_results` 守卫 + 别名

**文件**：`core/engine_v2.py:759-762`。

```python
    def _generate_results(self) -> dict[str, Any]:
        """生成回测结果"""
        if self.tracker is None or self.executor is None:
            raise RuntimeError("请先调用setup()方法")
        tracker = self.tracker
        executor = self.executor
        snapshots = tracker.get_snapshots()
        trades_df = executor.trade_log.get_trades_df()
```

| 项 | 内容 |
|----|------|
| 守卫范围 | 只覆盖 `tracker` / `executor`（二者是本方法唯二无守卫的必用组件；`dm` / `universe` / `pending_queue` 已有真值分支） |
| 守卫后 | 方法体内 `self.tracker` → `tracker`（3 处：L761/790/804）、`self.executor` → `executor`（2 处：L762/781） |
| 保留 | L776 `self.dm.get_data_info() if self.dm else {}`、L777 `self.universe... if self.universe`、L778-780 `self.pending_queue` 的真值分支**原样不动** |
| 验证 | 91 → **86**（消除 5 条 `union-attr`）；T-B2 转绿 |

### T-4 D4/D5：engine_v2 其余 7 方法 + `all_orders`

**统一形态**（别名 + 合并 assert；方法内不再出现被别名的 `self.<field>`）：

```python
        dm = self.dm
        tracker = self.tracker
        assert dm is not None and tracker is not None
```

**逐方法清单**（引用数=该方法内 `self.<field>` 出现次数，E1 AST 统计；error 数见 §6）：

| 方法 | 别名（替换全部引用） | 引用数 | 放置位置 |
|------|----------------------|--------|----------|
| `_process_trading_day` L305 | `dm` / `trigger` / `tracker` / `signal_df` | 1+1+3+2 = **7** | 方法首行 |
| `_force_liquidation` L363 | `dm` / `executor` / `tracker` | 1+1+3 = **5** | 方法首行 |
| `_process_pending_orders` L402 | `dm` / `universe` / `executor` / `tracker` | 3+2+1+1 = **7** | `if not self.pending_queue: return` **之后** |
| `_try_fallback_order` L476 | `signal_df`；`universe` / `dm` / `executor` / `tracker` | 2；1+1+1+1 = **6** | `signal_df` 在首行守卫**之前**；其余在守卫**之后** |
| `_execute_rebalance` L520 | `signal_df`；`returns_matrix` / `dm` / `universe` / `optimizer` / `tracker` | 3；1+3+1+1+2 = **11** | `signal_df` 在 L522 守卫**之前**；其余在守卫**之后** |
| `_generate_orders_via_policy` L600 | `tracker` / `dm` / `policy`（=`_execution_policy`） | 2+1+1 = **4** | 方法首行（含 `assert policy is not None`） |
| `_execute_next_day_orders` L693 | `dm` / `universe` / `tracker` / `executor` | 1+4+2+1 = **8** | `if not hasattr(...) ...: return` **之后** |

> 合计替换 **48** 处引用，消除 **47** 条 error（`_execute_next_day_orders` 的 2 处 `hasattr(self.universe, ...)` 不报错但必须同步替换；`all_orders` 的注解修正不计入引用数，对应 1 条 `var-annotated`）。

**命名冲突核查（E3）**：

| 方法 | 已存在的局部名 | 结论 |
|------|----------------|------|
| `_execute_rebalance` | `positions`（L570）、`prices`、`target_weights`、`returns_data` | `tracker` / `dm` / `universe` / `optimizer` / `signal_df` / `returns_matrix` 均不冲突 |
| `_process_trading_day` | `positions`（L338，仅 risk_manager 分支）、`close_prices`、`should_rebalance` | `signal_df` / `trigger` 不冲突 |
| `_execute_next_day_orders` | `open_prices` / `buyable_mask` / `sellable_mask` / `failed_orders` | `universe` 不与 `buyable_mask` 冲突 |
| `_generate_orders_via_policy` | `current_positions` / `adj_close` / `close_prices` / `total_value` / `intents` / `all_orders` / `orders` | `policy` 不冲突 |
| `_force_liquidation` | `positions` / `close_prices` / `liquidated_count` | `tracker` 不冲突 |

**`_execute_rebalance` 的保留项**：L595 `if self._execution_policy is not None:` 保留原样（真值守卫已窄化；被调用的 `_generate_orders_via_policy` 内部另做 assert）。

**`all_orders`（D5 / C-3）**：

```python
        all_orders: list[PendingOrder] = []
```

`core/engine_v2.py:43-48` 的 `from core.pending import (...)` 补 `PendingOrder,`。

**估算**：+30 行（别名 ~22 行 + assert 7 行 + 注解 1 行），替换 48 处引用。

### T-5 D6：`engine_v3_vector` 3 方法

**逐方法清单**（引用数 E1 AST 统计）：

| 方法 | 别名 | 引用数 | 放置位置 |
|------|------|--------|----------|
| `_precompute_signals` L257 | `dl` | **5** | 方法首行 |
| `run` L276 | `positions` / `cash` / `pv` | 3+4+2 = **9** | `if self.dl is None: raise` **之后**；`self.dl` 的 4 处引用**不动**（守卫已窄化） |
| `_rebalance_vectorized` L322 | `dl` / `signal_matrix` / `positions` / `cash` / `pv` | 6+1+2+3+1 = **13** | 方法首行 |

**示例**：

```python
    def _rebalance_vectorized(self, date_idx: int, top_n: int) -> None:
        dl = self.dl
        signal_matrix = self._signals
        positions = self._positions
        cash = self._cash
        pv = self._portfolio_value
        assert (
            dl is not None
            and signal_matrix is not None
            and positions is not None
            and cash is not None
            and pv is not None
        )
        ...
        signal = signal_matrix[date_idx].astype(np.float64)
```

| 项 | 内容 |
|----|------|
| 命名 | DESIGN §D6 写 `signals`；IMPL 收紧为 **`signal_matrix`**，避免与同方法内的行向量 `signal` 视觉混淆（语义不变） |
| 不变式 | 别名是同一 ndarray 的引用，只做原地写入（`positions[date_idx] = ...`）；方法内**不得**重绑定 `self._positions = ...` |
| 估算 | +16 行，替换 27 处引用，消除 26 条 |

### T-6 D7：factory 13 条

**改动 1**（`core/factory.py:10` 导入）：

```python
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

if TYPE_CHECKING:
    from core.engine_v2 import BacktestEngineV2
```

**改动 2**（L94-95）：

```python
    def _create_component(
        self, component_type: str, default_factory: Callable[..., Any], *args, **kwargs
    ) -> Any:
```

**改动 3**：9 个包装方法各自 `cast` 到返回类型。示例（其余 8 个同构）：

```python
    def create_data_manager(self) -> IDataManager:
        """创建数据管理器"""
        return cast(
            IDataManager,
            self._create_component(
                "data_manager",
                lambda: DataManager(self.cfg),
            ),
        )

    def create_pending_queue(self) -> Optional[IPendingOrderQueue]:
        """创建待执行订单队列"""
        if not self.cfg.enable_pending_orders:
            return None
        return cast(
            Optional[IPendingOrderQueue],
            self._create_component(
                "pending_queue",
                lambda buy_days, sell_days: PendingOrderQueue(
                    max_pending_days_buy=buy_days,
                    max_pending_days_sell=sell_days,
                ),
                self.cfg.max_pending_days_buy,
                self.cfg.max_pending_days_sell,
            ),
        )
```

**改动 4**（L245 / L263）：返回注解去掉引号（`TYPE_CHECKING` 导入后名称可解析）：

```python
def create_default_engine(config: BacktestConfig) -> BacktestEngineV2:
def create_engine_with_custom(config: BacktestConfig, **custom_components) -> BacktestEngineV2:
```

| 项 | 内容 |
|----|------|
| cast 目标 | `IDataManager` / `IUniverseFilter` / `IFactorPipeline` / `IFactorCombiner` / `IOptimizer` / `IRebalanceTrigger` / `IExecutionSimulator` / `IPositionTracker` / `Optional[IPendingOrderQueue]` |
| 为何 cast | 注册表分支返回 `Any`（`_registry` 存类对象）；A32：cast 无运行时检查，故只在「工厂自身保证返回该协议」处使用 |
| 被拒 | 泛型 `Callable[..., T]`（P20 探针：lambda 无注解 → T 退化 `Any`）；传类替代 lambda（改 9 处调用形态） |
| 验证 | 13 → **0** |

### T-7 全量验证

按 §5 的 V1-V12 逐条执行并记录读数；V9 记录门禁 verdict，但**不关闭 U-006**（Q4=B）。

### T-8 文档与提交

| 文件 | 动作 |
|------|------|
| 四文档 `*_p007_mypy_layerb.md` | 本批工件（RESEARCH / DESIGN / IMPL / CHECKLIST） |
| `docs/PROGRESS.md` | §3.11 追加 Step 5-10；§1.4 P-007 状态更新（层 B 完成、mypy 93 → 0、U-006 仍挂起）；§2 U-006 注记「裁决 B」 |
| `CHANGELOG.md` | `[Unreleased] > Changed`：空因子 fail-fast + `_generate_results` 守卫；`Fixed`：`get_snapshots` 契约、`trade_log` 缺失声明 |
| 提交 | 单笔 `fix(P-007): 清理引擎 mypy 93 errors（层 B）`；推送后核对 CI 三版本 |

---

## 5. 验证清单（V1-V12）

| ID | 命令 | 期望 |
|----|------|------|
| V1 | `%PY312% -m mypy --explicit-package-bases core` | `Success: no issues found in 29 source files`，exit 0 |
| V2 | 同上按文件分流 | engine_v2 **0** / v3 **0** / factory **0** |
| V3 | `%PY312% -m mypy --explicit-package-bases --check-untyped-defs core` | `8 errors in 2 files`（engine_v2 6 + data_v3 2；T-2 使 L231 转过，Step 6 修正） |
| V4 | `$env:MPLBACKEND="Agg"; %PY312% -m pytest tests -q` | **`516 passed`** |
| V5 | `%PY312% -m pytest tests/test_mypy_layerb_smoke.py -q` | `2 passed` |
| V6 | `%PY312% -m black --check .` | exit 0，0 reformatted |
| V7 | `Select-String -Path core\*.py,tests\*.py -Pattern "type: ignore"` | **1** 处（不变） |
| V8 | `git diff --stat -- .github/workflows/tests.yml` | 输出**空** |
| V9 | `%PY312% scripts/spec_runner_adapter.py gate mypy-check` | verdict **pass**；**U-006 不关闭**（Q4=B） |
| V10 | `%PY312% -m mypy --explicit-package-bases %TEMP%\p007b_proto_conform.py` | **4 → 3**（`PositionTracker` 转通过；`ExecutionSimulator` 仍差 `execute_order`；另 2 条属 Q2-C）`[未入仓-不可重放]` |
| V11 | `git diff --stat -- core/ tests/` | 仅 4 个 core 文件 + 1 个新测试文件 |
| V12 | `(Get-ChildItem tests -Filter 'test_*.py').Count` | **51** |

---

## 6. 红 → 绿执行序（递减算术）

| 序 | 动作 | mypy 总数 | 分文件 | 测试 |
|----|------|-----------|--------|------|
| 0 | T-0 RED | **93** | 54 / 26 / 13 | 2 failed, 514 passed |
| 1 | T-1 D1 fail-fast | **93** | 54 / 26 / 13 | 1 failed, 515 passed |
| 2 | T-2 D2 接口 | **91** | 52 / 26 / 13 | 1 failed, 515 passed |
| 3 | T-3 D3 守卫 | **86** | 47 / 26 / 13 | 516 passed |
| 4 | T-4 engine_v2 其余 | **39** | 0 / 26 / 13 | 516 passed |
| 5 | T-5 v3 | **13** | 0 / 0 / 13 | 516 passed |
| 6 | T-6 factory | **0** | 0 / 0 / 0 | 516 passed |
| 7 | T-7 V1-V12 | **0** | — | 516 passed |
| 8 | T-8 文档 + 提交 + CI | **0** | — | CI 三版本 |

**递减验证**：每步后执行 `mypy --explicit-package-bases core 2>&1 | Select-String ": error:" | ForEach-Object { ($_ -split ":")[0] } | Group-Object`，与上表逐格比对；不符即停。

---

## 7. 回退点

| 断点 | 操作 |
|------|------|
| 单任务失败 | `git checkout -- <该文件>` 恢复到 T-0；重新做该任务，不跨任务修补 |
| 接口改动导致意外新 error | 先回退 `core/interfaces.py`，T-2 重做；不得在 engine 侧加 cast 绕过 |
| 全部完成后发现问题 | `git revert <本批提交>`（单笔含测试与文档） |
| 仅回退行为变更 | `git checkout <前提交> -- core/engine_v2.py`（会同时回退 D3/D4/D5，需重做窄化） |

---

## 8. 会话与门禁

- **Session**: `factorv3-p007-mypy-layerb-20261110`
- **门禁预期**：probe pass / unit-tests pass(516) / black-check pass / **mypy-check pass(0)**
- **台账口径**：门禁机械转 pass，但 **U-006 不关闭**（用户裁决 B，2026-11-09）；下一批次重新评估
- **replay 期望**：4 rows OK

---

## 10. Step 6 Review（独立 pass）

- **执行时点**: 正文完稿（471 行）后的单独 pass（2026-11-10），与正文非同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: E1 命令复算（含 flag 口径逐行 diff）+ E3 逐方法核对引用数与守卫位置 + 外部锚点引文回溯 + 递减算术复核；不依赖正文自报

### 10.1 事实核实

| ID | 核实项 | 方式 | 结果 |
|----|--------|------|------|
| C-1 | 基线与分文件 | `mypy --explicit-package-bases core`（raw 输出） | 93 = 54/26/13 ✅ |
| C-2 | flag 口径基线 | `--check-untyped-defs core` 分文件计数 | **102 = 61/2/26/13** ✅（RED-3 RED 读数一致） |
| C-3 | **flag 增量逐行清单** | base/flag 两个错误清单按 `文件:行` diff | engine_v2 增量 7 条 = **L185 / L194×2 / L201 / L224 / L231 / L259**；data_v3 2 条（`_build_maps`）→ **F-I1** |
| C-4 | L231 可被 T-2 消除 | E3：`PositionTracker` 全成员 vs 修正后 `IPositionTracker`（`execute_trade(trade: Trade)` vs `Any`、`get_all_positions -> dict[str, Position]` vs `dict[str, Any]` 等，返回协变 / 参数逆变兼容） | ✅ T-2 后 L231 消失 → 批后残差 **8**（engine_v2 6 + data_v3 2），非 9/7 |
| C-5 | 递减算术 | 93 →（T-2 −2）91 →（T-3 −5）86 →（T-4 −47）39 →（T-5 −26）13 →（T-6 −13）**0** | ✅ 与 §6 逐格一致 |
| C-6 | 引用计数 | AST 扫描（`p007b_refcount.py`）逐方法 `self.<field>` 计数 | engine_v2：7/5/7/6/12/4/8（`_execute_rebalance` 12 中 1 处 `self._execution_policy` 为 L595 守卫保留 → 替换 11）→ 替换 **48** ✅；v3：5/13/13（`run` 的 `dl`=4 处守卫内不替换）→ 替换 **27** ✅ |
| C-7 | 别名放置与守卫 | E3 读码：`_process_pending_orders` L404 早退、`_execute_next_day_orders` L695 早退、`_try_fallback_order` L478 / `_execute_rebalance` L522 守卫使用 signal | ✅ 与 T-4/T-5「守卫后下移」规则一致；`_precompute_signals` 的 `self._signals` 赋值点 L273-274 经赋值窄化无 error，不需别名 ✅ |
| C-8 | 命名冲突 | E3 逐方法局部名扫描 | `positions`（`_execute_rebalance` L570、`_force_liquidation` L367、`_process_trading_day` L338）与别名集无冲突；`signal`（v3 L332 行向量）→ `signal_matrix` 收紧合理 ✅ |
| C-9 | T-1 插入点 | E3 `engine_v2.py:163-169`（docstring L164-167、`t0` L168） | ✅ |
| C-10 | T-2 位置 | E3 `interfaces.py:10` 导入行、L197 `IExecutionSimulator`、L271 `get_snapshots`；`__future__ annotations` L7 | ✅ `ITradeLog` 定义于 L197 前，无引号可行 |
| C-11 | T-3 守卫面 | E3 `_generate_results` L776-780：`dm`/`universe`/`pending_queue` 均有真值分支 | ✅ 守卫只需 tracker/executor |
| C-12 | T-6 目标行 | E3 `factory.py:10/94-95/116…183/245/263` 逐行 | ✅ 13 条与 cast 目标一一对应 |
| C-13 | RED 测试预期 | E3：现版 setup 仅 warning+return（不抛）；`_generate_results` L761 在 tracker=None 时抛 AttributeError | ✅ 两条 `DID NOT RAISE` 预期成立；`match=` 子串均在消息内（A34） |
| C-14 | 外部锚点 A31-A34 | 本会话 WebFetch 回溯：mypy protocols §Invariance（L96/111）、type_narrowing（L59/118）、Dropbox 2019（L147/67）、pytest assert（L106） | ✅ 四条引文逐字命中 |

### 10.2 发现项

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-I1** | **P2** | **V3/RED-3 的 GREEN 目标失实**：正文写「9 errors in 2 files（engine_v2 7 + data_v3 2）」，但 flag 增量 7 条中的 **L231**（`PositionTracker`↔`IPositionTracker` assignment）随 T-2 协议修正消失（C-4 实证）→ 批后残差 = **8**（engine_v2 6 + data_v3 2）。根因：DESIGN §13.4.1 第 4 条本已写明「L231（Q2-A 顺带消除）」，但 DESIGN V3 与 IMPL 均按 9/7 设目标——上游内部不一致被沿袭 | 已回写：IMPL RED-3 / V3 / T-2 表（盲口径行）；DESIGN V3 + D2 表（附带收益行）；RESEARCH §13.5 U-3 补 Step 6 注记（重审基线 = 8） |
| F-I2 | P3 | flag 口径下 L194 实为 **2 条**（`assignment` + `arg-type`），DESIGN §13.4.1 的「6 条」清单按行合并计数——口径差异是 F-I1 的成因之一 | 已并入 F-I1 证据（C-3 清单按物理条计数） |
| F-I3 | P3 | DESIGN §D6 样例与别名表用 `signals`，IMPL 收紧为 `signal_matrix`（避免与行向量 `signal` 混淆） | 已同步 DESIGN（样例 + 别名表），偏离已双向对齐 |
| F-I4 | P3 | 多行 `assert (...)` / 多行 `cast(...)` 的精确折行以 black 26.5 实测为准（V6 兜底） | 接受为实施期残差；V6 不绿则按 black 输出调整，不改断言 |

### 10.3 覆盖与红线核对

| 核对项 | 结果 |
|--------|------|
| D1-D9 → 任务映射 | D1→T-1；D2→T-2；D3→T-3；D4/D5→T-4；D6→T-5；D7→T-6；D8→T-0/T-1/T-3；D9→T-7/V1-V12 + §8 —— **全覆盖，无越界** |
| V1-V12 → 任务映射 | V1/V2←T-4~T-6；V3←T-2（8 非 9，F-I1）；V4/V5/V12←T-0+T-7；V6←T-7；V7/V8←排除表；V9←§8；V10←T-2；V11←变更面 —— **全覆盖** |
| 排除表 | 8 条禁止项与 D1-D9 无冲突；「不给 setup 加注解」（Q3=A）、「不改 CI/mypy 配置」（D9/P31）、「不用 cast 替代别名」（A32）为本批红线，已进 CHECKLIST 候选 |
| 零新增依赖 | T-2/T-6 仅用 stdlib `typing`（3.8+）；CI 最低 3.10 ✅ |
| 行为 delta | 仅 T-1（公共路径）与 T-3（私有方法守卫）；agents 直调 `_generate_results`（`multi_strategy_engine.py:768,910`）均在 `run()` 后，不触发新守卫 ✅ |

### 10.4 Review 结论

- P0 / P1：**0**
- P2：**1**（F-I1，已回写 IMPL + DESIGN + RESEARCH 三处）
- P3：**3**（F-I2 / F-I3 / F-I4，已回写或登记为实施期残差）
- 判定：任务粒度满足「单任务可追溯到错误码 + 递减可机械核验 + 可独立回退」；**Step 6 通过，可进入 Step 7（CHECKLIST）**。

---

**Review 签字**: 单 Agent 自查（RULE-4） 日期: 2026-11-10
