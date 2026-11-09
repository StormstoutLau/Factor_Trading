# P-007 层 B（引擎 mypy 93 errors 清理） · 设计文档

> **文档编号**: DESIGN_p007_mypy_layerb
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: Step 3 完稿；**Step 4 Review 通过**（2026-11-10；1 P1 + 3 P3 全部回写，见 §10）；可进入 Step 5
> **上游**: [RESEARCH_p007_mypy_layerb.md](RESEARCH_p007_mypy_layerb.md)（Step 2 通过；Q1=A / Q2=A / Q3=A / Q4=B 已裁决，见 §13.5）
> **下游**: [IMPL_p007_mypy_layerb.md](IMPL_p007_mypy_layerb.md) → [CHECKLIST_p007_mypy_layerb.md](CHECKLIST_p007_mypy_layerb.md)
> **证据时点**: 本仓读数 @ `762ff5f`；Python 3.12.10 / mypy 2.1.0；测试基线 `514 passed`（2026-11-09 复跑）
> **档位**: T1（`core/` 4 文件 + 1 测试；含 2 项行为变更：D1 公共路径 / D3 私有方法守卫）

---

## 1. 决策总览

| ID | 决策项 | 决定 | 对应 |
|----|--------|------|------|
| **D1** | Q1 空 `factor_files`（A-1） | **`_precompute_factors` 抛 `ValueError`（fail-fast）**；不改 `cfg.validate()` 的调用方式 | Q1 / U-1 |
| **D2** | Q2 协议真实化（B-1/B-2） | **`get_snapshots -> list["PortfolioSnapshot"]` + 新增 `ITradeLog` 最小协议并声明 `trade_log`** | Q2 / U-2 |
| **D3** | A-2 `_generate_results` 无守卫 | **加 `RuntimeError` 守卫**（与 `run()` 同文案），并局部别名窄化 | A-2 |
| **D4** | C-1 组件 Optional 窄化（engine_v2，43 条） | **逐方法「局部别名 + 合并 assert」**，覆盖 8 个方法 | C-1 |
| **D5** | A-1 窄化 + C-2 + C-3（9 条） | `_composite_signal` / `_returns_matrix` 同用局部别名；`all_orders: list[PendingOrder]` | A-1 / C-2 / C-3 |
| **D6** | C-4 `engine_v3_vector`（26 条） | **3 个方法局部别名**：`dl` + `_signals` / `_positions` / `_cash` / `_portfolio_value` | C-4 |
| **D7** | C-5 `factory`（13 条） | `Callable[..., Any]` + **9 处 `cast`** + `TYPE_CHECKING` 导入 `BacktestEngineV2` | C-5 |
| **D8** | 测试 | 新增 **2 项** smoke：空因子 fail-fast、未 setup 的 `_generate_results` 守卫 | Q1 / A-2 |
| **D9** | 范围边界 | **93 → 0**；Q3 盲区不动（`--check-untyped-defs` 批后残差 **8**，见 V3）；**U-006 不关闭**（Q4=B）；CI 与 `pyproject.toml` 零改动 | — |

**总量核对**：error 消除归属为 D2 **2** + D4 **43** + D5 **9**（7 信号 + 1 矩阵 + 1 注解）+ D6 **26** + D7 **13** = **93**，与基线逐字相等（不重不漏）。D1 是**行为修复**，不直接消除 error；A-1 的 7 条 error 由 D5 的 `_composite_signal` 别名消除。
> **物理行口径（Step 4 注记）**：L762 实为 **2 条** mypy error（`Item "IExecutionSimulator" …` 与 `Item "None" …` 两行，E1 raw 输出）；B-2 按「条目」记 1。按物理行口径为 D2=3 行（762×2+767）、D4=42 行，总和不变；两口径下全部清除。

> 口径说明：A-2 的静态表现计入 C-1 的 43 条（RESEARCH §5.2 已声明），D3 是**运行时守卫**，不额外计数。

---

## 2. 逐项决策与依据

### 2.0 调研结论 → 设计决策映射

| 调研结论 | 设计决策 | 引用 |
|----------|----------|------|
| 空因子分支仅 3 行；fail-fast 与回退均个位数 diff | D1 选 fail-fast（3 行 + 测试） | RESEARCH §12.1 P25 / §13.2.5 |
| 零信号在 `MinVarianceOptimizer` 下建任意组合；`setup()` 从未调用 `validate()` | D1 拒绝零信号回退与空仓模式 | RESEARCH §12.1 P26/P34、§13.2.4 |
| 4 个组件全部不满足协议；`PortfolioSnapshot` 是 dataclass；`TradeLog.get_trades_df` 存在 | D2 修 `get_snapshots` + 补 `ITradeLog` | RESEARCH §12.1 P27、§13.3.2/§13.3.4 |
| 43 条组件 Optional 窄化；方法级单 assert 会被方法调用失效 | D4 局部别名 + 合并 assert | RESEARCH §5.2、§7.1 S1、P21 |
| v3 26 条集中在 3 个方法；`setup()` 已注解 | D6 仅方法内窄化，不改 `setup()` | RESEARCH §5.2 P17/P18、§13.4.1 |
| `callable` 误用 + 泛型工厂探针 T 退化为 `Any` | D7 非泛型：`Callable[..., Any]` + 9 cast | RESEARCH §7.3 FC-1/FC-2（P20 探针） |
| `setup()` 盲区 9 条、CI mypy 带短路兜底 | D9 不打开、不改 CI | RESEARCH §12.1 P30/P31、Q3=A |

### D1 空 `factor_files`：fail-fast

**现状**（`core/engine_v2.py:249-273`）：

```python
    def _precompute_factors(self):
        """预计算因子数据"""
        # 只处理第一个因子（简化）
        if not self.cfg.factor_files:
            logger.warning("未指定因子文件")
            return
```

`_composite_signal` 保持 `None` → 逐日 `TypeError` 被 `run()` 的 `except Exception` 吞掉（E2：100 条 ERROR 后返回空结果，RESEARCH §3.1 PROBE-1~7）。

**决定**（`setup()` 入口，`core/engine_v2.py:163-169`）：

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
| 位置选择 | 放在 `setup()` **入口**：① 公共入口，最早边界；② 不产生「部分组件已初始化」的中间态；③ 失败后 `dm` 仍为 `None`，`run():277-278` 既有守卫继续有效（若放在 `_precompute_factors`，`dm` 已被赋值，调用方 catch 后 `run()` 会进入逐日循环并回到静默失败） |
| `_precompute_factors` 的空分支 | **保持原样**（防御性，经 `setup()` 不可达）；不在两处重复抛错 |
| 与 RESEARCH 的差异 | RESEARCH §13.2.5 建议放在 `_precompute_factors`；本设计按上述「部分初始化」风险改为 `setup()` 入口，行为契约（空因子 → `ValueError`）不变 |
| 不改 `validate()` | `validate()` 返回 `list[str]` 而不抛（P34）；改调用会连带改变 `data_dir` 等校验时机，超出本批 |
| 异常类型 | `ValueError`（配置值非法）；与 `config.validate()` 的语义分级一致 |
| 行为变更 | 空因子调用方由「静默空回测」变为 `ValueError`；CHANGELOG `Changed` 必须披露 |
| 可达面 | 仅「默认构造 + 直接 `setup()`」的库方式（P35）；CLI/examples 全部显式非空（`cli.py:47`、examples 9 处） |
| **实施注记（Step 9，F-S9-1）** | 原文「可达面」低估了测试面：`tests/test_real_ashare_backtest.py` / `tests/test_real_ashare_strict_validation.py` 注入 `factor_pipeline` + `factor_combiner` 后以空 `factor_files` 调 `setup()`，再手工注入 `_composite_signal`（13 个用例）。无条件守卫会使其全数失败，故守卫条件收紧为「**因子路径全为默认**（无注入 pipeline/combiner）且 `factor_files` 为空」；默认路径的 P34 缺陷仍 fail-fast，手工信号工作流不受影响 |

**被拒方案**：

| 方案 | 否决理由 |
|------|----------|
| 零信号回退（全 0 信号） | E2：`MinVarianceOptimizer` 不滤零 → `nlargest(2)` 建任意组合（`['000001','000002']` 权重和 1.0）；Fowler《Fail Fast》把「默认值兜底」归为 failing slowly（A27） |
| 空仓模式（跳过再平衡） | 新增「无信号」第三态，但触发路径在产品侧不可达（P35）；且空回测成功返回会让调用方误读为「策略无信号」 |
| 仅加 `assert` | `-O` 下消失且仍是每日异常被吞（RESEARCH §7.2 A-1c） |

### D2 协议真实化：`get_snapshots` + `ITradeLog`

**决定 1**（`core/interfaces.py`）：

```python
from typing import TYPE_CHECKING, Any, Optional, Protocol

if TYPE_CHECKING:
    from core.tracker import PortfolioSnapshot


class IPositionTracker(Protocol):
    """持仓跟踪器接口"""

    # ... 其余成员不变 ...

    def get_snapshots(self) -> list[PortfolioSnapshot]:
        """获取持仓快照"""
        ...
```

> 本文件已有 `from __future__ import annotations`（`interfaces.py:7`）→ 注解惰性求值，引号非必需（Step 4 修正：与 D7「去掉引号」口径统一）。

**决定 2**（同文件，执行层接口之前；**Step 4 修正：只读 property 形态**）：

```python
class ITradeLog(Protocol):
    """交易日志最小契约（结果生成所需）"""

    def get_trades_df(self) -> pd.DataFrame:
        """获取交易记录 DataFrame"""
        ...


class IExecutionSimulator(Protocol):
    """交易执行模拟器接口"""

    # ... 其余方法成员不变 ...

    @property
    def trade_log(self) -> ITradeLog:
        """交易日志（只读）"""
        ...
```

| 项 | 内容 |
|----|------|
| 依据 | `PortfolioSnapshot` 是 `@dataclass`（`tracker.py:133-135`），不是 `dict` → 原协议声明不存在子类型关系（A23 / PEP 544 A22） |
| 依据 | `TradeLog` 有 `get_trades_df() -> pd.DataFrame`（`execution.py:52,79`），`ITradeLog` 结构上可满足 |
| 附带收益（Step 6 实证） | flag 下 `engine_v2.py:231` 的 `PositionTracker`↔`IPositionTracker` assignment 错误随本决策消失（全成员符合）→ `--check-untyped-defs` 批后残差 = **8**（engine_v2 6 + data_v3 2） |
| **不变性（Step 4 实证）** | 若声明为**可变属性** `trade_log: ITradeLog`，PEP 544 要求实现方属性类型**不变**（mutable attribute invariant）→ `TradeLog` 虽是 `ITradeLog` 子类型仍被判不符（E2 探针 `p007b_design_shape_probe.py`：`trade_log: expected "ITradeLog", got "TradeLog"`）；改为**只读 property 成员**后返回类型协变，`ExecutionSimulator`（普通属性）与 `MockExecutionSimulator`（`trade_log = self`）双双通过（E2 探针 `p007b_tradelog_variants.py`：`Success`） |
| 兼容 | Mock：`MockExecutionSimulator.get_trades_df` 存在（`tests/test_decoupled_engine.py:172`）、`trade_log = self`（L148）；`MockPositionTracker.get_snapshots() -> list`（L239）= `list[Any]`，协变兼容 |
| 运行时 | **零影响**；`TYPE_CHECKING` 不触发导入（`tracker.py` 只 import `core.execution`，无环）；property 仅存在于协议，实现方仍是普通属性 |
| 诚实限制 | `ITradeLog` 的结构一致性只在**有注解的赋值点**被检查；`setup()` 未注解（Q3=A），当前不新增静态保证——本项价值是「契约变真 + 未来 typed 消费方受检」 |
| 残余 | `ExecutionSimulator.execute_order` 第 5 参数名 `open_price` vs 协议 `price` 仍不符（`execution.py:250-260` vs `interfaces.py:203-211`），属 Q3/U-3 范围 |

**被拒方案**：engine 侧 `cast`（契约缺陷固化，A3/A22）；可变属性形态 `trade_log: ITradeLog`（PEP 544 不变性下实现方不符，见上表）；4 协议全面真实化（需决定「补 2 个零调用方方法」或「删协议成员」，属 API 决策，另立批次）。

### D3 `_generate_results` 守卫（A-2）

**决定**（`core/engine_v2.py:759-762`）：

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
| 依据 | E2 PROBE-8：未 setup 直接调用 `_generate_results()` → `AttributeError`（`tracker` 为 `None`） |
| 一致性 | 与 `run():277-278` 的守卫同文案「请先调用setup()方法」 |
| 行为变更 | 仅影响直接调用私有方法者（非公共 API）；正常 `run()` 路径不受影响 |
| 为何不用「`_require_setup()` + 方法调用」 | 方法调用会使 `self.x` 的窄化失效（P21 / A5），无法满足 mypy |

### D4 C-1：engine_v2 组件窄化（43 条）

**统一写法**（每方法开头）：

```python
    def _some_method(self, ...):
        dm = self.dm
        tracker = self.tracker
        assert dm is not None and tracker is not None
        ...  # 方法体内改用 dm / tracker
```

**逐方法别名清单**（行号 = 该方法内 error 行；E3 @`762ff5f`）：

| 方法 | 行范围 | 需要别名（字段） | error 行 | 条数 |
|------|--------|------------------|----------|------|
| `_process_trading_day` | 305-344 | `trigger` / `tracker` / `dm` / `_composite_signal`（D5） | 318,321,322,325,333,334,338 | 7 |
| `_force_liquidation` | 363-401 | `tracker` / `dm` / `executor` | 367,373,390,395,399 | 5 |
| `_process_pending_orders` | 402-475 | `dm` / `universe` / `executor` / `tracker` | 413,415,416,420,421,448,453 | 7 |
| `_try_fallback_order` | 476-519 | `_composite_signal`（D5）/ `universe` / `dm` / `executor` / `tracker` | 478,481,491,497,508,511 | 6 |
| `_execute_rebalance` | 520-599 | `_composite_signal` / `_returns_matrix`（D5）/ `universe` / `dm` / `optimizer` / `tracker` | 522,527,532,535,548,549,550,555,565,570,577 | 11 |
| `_generate_orders_via_policy` | 600-653 | `tracker` / `dm` / `_execution_policy` | 615,620,628,640,642 | 5 |
| `_execute_next_day_orders` | 693-758 | `dm` / `universe` / `tracker` / `executor` | 701,707,710,740,744,749 | 6 |
| `_generate_results` | 759-819 | `tracker` / `executor`（D3 守卫后别名） | 761,762×2,767,781,790,804 | 7 |

> 合计 7+5+7+6+11+5+6+7 = **54**（engine_v2 全部 error）；其中 D2 覆盖 2 条（L762 `trade_log`、L767 `get_snapshots`），D5 覆盖 9 条，D4 覆盖 43 条。

**要点**：

1. **alias 后不得再出现 `self.<field>`**（同一方法内），否则窄化不成立。
2. 合并 `assert` 用 `and` 串联，mypy 对 `assert a is not None and b is not None` 同时窄化两者（本机 2.1.0 已验证同类写法，RESEARCH §3.1 P21）。
3. `executor` 在 `_force_liquidation` 内使用前已有 `if ... executor` 之类的路径？逐行核对后统一用别名，不做多余分支。
4. 不为 `pending_queue` 加别名：现有代码均以 `if self.pending_queue:` 真值判断使用，mypy 已在分支内窄化，无 error。

### D5 A-1 窄化 + C-2 + C-3（9 条）

**决定**：

| 项 | 改动 | 覆盖 |
|----|------|------|
| `_composite_signal` | 3 个方法各加 `signal_df = self._composite_signal` + assert；方法体内 7 处改用 `signal_df` | L321,322 / 478,481 / 522,527,532（7 条） |
| `_returns_matrix` | `_execute_rebalance` 加 `returns_matrix = self._returns_matrix` + assert；L548 改用别名 | L548（1 条） |
| `all_orders` | `all_orders: list[PendingOrder] = []`（L640），并在 `core/pending` 导入中补 `PendingOrder` | L640（1 条） |

```python
    def _execute_rebalance(self, date: pd.Timestamp, date_index: int):
        """执行再平衡"""
        signal_df = self._composite_signal
        returns_matrix = self._returns_matrix
        dm = self.dm
        universe = self.universe
        optimizer = self.optimizer
        tracker = self.tracker
        assert (
            signal_df is not None
            and returns_matrix is not None
            and dm is not None
            and universe is not None
            and optimizer is not None
            and tracker is not None
        )
        ...
```

**为何不用 §13.2.5 建议的 `_signal` property**：本批 9 个 Optional 字段统一采用「局部别名 + assert」，避免新增类成员与 `self._signal` / `self._composite_signal` 双名并存；两种写法消除的 error 数相同，S1 的审查面更小（RESEARCH §7.1 首选 S1）。此偏离仅是实现手段，不影响 Q1 的 fail-fast 决策。

**为何 `list[PendingOrder]` 而不是 `list[Any]`**：`ExecutionPolicy.create_orders` 的返回类型明确为 `list[PendingOrder]`（`execution_policy.py:177,217,282`），用真类型可让 `extend` 也受检。

### D6 C-4：`engine_v3_vector` 窄化（26 条）

| 方法 | 行范围 | 别名 | error 行 | 条数 |
|------|--------|------|----------|------|
| `_precompute_signals` | 257-275 | `dl` | 261,262,263,265,268 | 5 |
| `run` | 276-320 | `positions` / `cash` / `pv`（`_portfolio_value`） | 299×2,303×2,304×2,311,312×2 | 9 |
| `_rebalance_vectorized` | 322-364 | `dl` / `signal_matrix` / `positions` / `cash` / `pv` | 329,332,335,336,339,340,345,348,352,353,363,364 | 12 |

```python
    def _rebalance_vectorized(self, date_idx: int, top_n: int) -> None:
        dl = self.dl
        signal_matrix = self._signals  # IMPL 收紧命名：避免与行向量 signal 混淆
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
        n_stocks = dl.n_stocks
        signal = signal_matrix[date_idx].astype(np.float64)
        ...
        positions[date_idx] = new_positions
        cash[date_idx] = new_cash
```

**不变式**：别名是**同一 ndarray 对象**的引用，方法内只做原地写入（`positions[i] = ...`），不得重绑定 `self._positions = ...`；`setup()` 是唯一分配点。已核对 3 个方法内无重绑定（E3）。

**`run()` 的 `dl` 不改**：L282 的 `if self.dl is None: raise` 已窄化，L288/289 无 error；只对 3 个数组加别名。

### D7 C-5：factory（13 条）

```python
from typing import TYPE_CHECKING, Any, Callable, Optional, cast

if TYPE_CHECKING:
    from core.engine_v2 import BacktestEngineV2


    def _create_component(
        self, component_type: str, default_factory: Callable[..., Any], *args, **kwargs
    ) -> Any:
        ...


    def create_data_manager(self) -> IDataManager:
        """创建数据管理器"""
        return cast(
            IDataManager,
            self._create_component("data_manager", lambda: DataManager(self.cfg)),
        )
```

| 项 | 内容 |
|----|------|
| 覆盖 | `valid-type` 1（L95）+ `misc` 1（L112）+ `no-any-return` 9（L116/123/132/141/148/155/164/171/183）+ `name-defined` 2（L245/263）= **13** |
| cast 目标 | 9 个包装方法各自返回类型：`IDataManager` / `IUniverseFilter` / `IFactorPipeline` / `IFactorCombiner` / `IOptimizer` / `IRebalanceTrigger` / `IExecutionSimulator` / `IPositionTracker` / `Optional[IPendingOrderQueue]` |
| TYPE_CHECKING | 运行时无导入；`engine_v2` 不在模块级 import `factory`（只在函数内 L254 局部导入），无环 |
| 去掉引号 | `create_default_engine` / `create_engine_with_custom` 的返回注解改为 `BacktestEngineV2` |

**被拒方案**：泛型 `Callable[..., T]`（P20 探针：lambda 形参无注解 → T 退化为 `Any`，`no-any-return` 仍在）；传类替代 lambda（改 9 处调用形态 + DI 语义变化）。

### D8 测试：2 项 smoke

新增 `tests/test_mypy_layerb_smoke.py`：

| ID | 测试 | 断言 |
|----|------|------|
| T-B1 | `test_empty_factor_files_raises_value_error` | `BacktestEngineV2(BacktestConfig(factor_files=[]))` → `setup()` 抛 `ValueError`（`match="factor_files"`）；`engine.dm is None`（未进入组件创建） |
| T-B2 | `test_generate_results_requires_setup` | `BacktestEngineV2(BacktestConfig())` 未 setup → `pytest.raises(RuntimeError, match="setup")` |

- 不新增协议一致性运行时测试：`Protocol` 非 `runtime_checkable`，静态契约由 V1 承担；既有集成测试已覆盖 `_generate_results` 正常路径。
- 测试计数：**514 → 516**。

### D9 范围边界

| 项 | 状态 |
|----|------|
| 引擎三件套 mypy | **93 → 0**（V1） |
| `--check-untyped-defs` | 不动；仍 **9** 条（Q3=A，V3） |
| `U-006` | **不关闭**（Q4=B）；门禁 verdict 会机械转 pass，仅记录，不改台账状态 |
| CI mypy 步骤 | **零改动**（`tests.yml:45-46` 仍带 `&#124;&#124; true` 短路兜底；P31） |
| `pyproject.toml [tool.mypy]` | **零改动** |
| `# type: ignore` | 不新增（全仓仍 1 处） |
| 引擎逐日行为 | 除「空因子路径」外**不变** |

---

## 3. 精确变更面

| 文件 | 变更性质 | 预估行数 |
|------|----------|----------|
| `core/engine_v2.py` | D1 抛错（±4）+ D3 守卫与别名（±6）+ D4 8 方法别名/assert（+30）+ D5 `all_orders` 注解与 `PendingOrder` 导入（+2） | **+42 / −4** |
| `core/engine_v3_vector.py` | D6 3 方法别名/assert，约 25 处引用替换 | **+16 / −0** |
| `core/interfaces.py` | D2 `TYPE_CHECKING` 导入 + `ITradeLog` + property 成员 + 2 处签名 | **+12 / −1** |
| `core/factory.py` | D7 导入、`Callable`、9 cast、TYPE_CHECKING | **+14 / −3** |
| `tests/test_mypy_layerb_smoke.py`（新增） | D8 2 项 smoke | **+55** |
| `docs/`（四文档 + PROGRESS + CHANGELOG） | 本批工件 | 新增 |

**代码净变化预估**：约 **+82 / −8**（不含测试与文档）。引用替换（`self.x` → 别名）不计入行数变化。

---

## 4. 验证契约

| ID | 断言 | 命令 | 期望 |
|----|------|------|------|
| V1 | `core` 零 error | `%PY312% -m mypy --explicit-package-bases core` | `Success: no issues found in 29 source files`，exit 0 |
| V2 | 三文件各自清零 | 同上，按文件分流 | engine_v2 **0** / v3 **0** / factory **0** |
| V3 | 盲区口径不变 | `%PY312% -m mypy --explicit-package-bases --check-untyped-defs core` | `8 errors in 2 files`（engine_v2 6 + data_v3 2；Q3=A；**T-2 使 flag 下 L231 转过**，Step 6 修正） |
| V4 | 全量回归 | `$env:MPLBACKEND="Agg"; %PY312% -m pytest tests/ -q` | **`516 passed`**（514 + 2） |
| V5 | 新测试通过 | `%PY312% -m pytest tests/test_mypy_layerb_smoke.py -q` | `2 passed` |
| V6 | 格式不回流 | `%PY312% -m black --check .` | exit 0，0 reformatted |
| V7 | 无 ignore 扩张 | `Select-String -Path core\*.py,tests\*.py -Pattern "type: ignore"` | **1** 处（不变） |
| V8 | CI 未改 | `git diff --stat -- .github/workflows/tests.yml` | 输出**空** |
| V9 | 门禁机械结果 | `%PY312% scripts/spec_runner_adapter.py gate mypy-check`（或等价调用） | verdict **pass**；**U-006 仍不关闭**（Q4=B） |
| V10 | 协议探针 | `%PY312% -m mypy --explicit-package-bases %TEMP%\p007b_proto_conform.py` | **4 → 3**（`PositionTracker` 转通过；`ExecutionSimulator` 仍差 `execute_order`，`FactorPipeline`/`FactorCombiner` 属 Q2-C 被拒项）`[未入仓-不可重放]` |
| V11 | 改动面受控 | `git diff --stat -- core/ tests/` | 仅 4 个 core 文件 + 1 个新测试文件 |
| V12 | 测试文件数 | `(Get-ChildItem tests -Filter 'test_*.py').Count` | **51**（50 + 1） |

> V10 为旁证（脚本未入仓），不替代 V1；若读数与预期不符，以实际为准并在 CHECKLIST 记录差异，不得改断言凑数。

---

## 5. 风险登记

| ID | 风险 | 等级 | 缓解 |
|----|------|------|------|
| R1 | 局部 `assert` 在 `python -O` 下被剥离，别名返回 `None` | 低 | 本仓无 `-O` 运行；且 `setup()` 成功是路径前提（D1/D3 双重保证） |
| R2 | 空因子由静默变 `ValueError`，外部库方式脚本受影响 | 中 | 可达面仅默认构造（P35）；CHANGELOG `Changed` + DESIGN 披露；examples/CLI 不受影响 |
| R3 | `all_orders: list[PendingOrder]` 若实际元素类型不符会新增 error | 低 | `create_orders` 返回类型明确（`execution_policy.py:177`）；若不符按实际调整，不盲目 cast |
| R4 | 改 `get_snapshots` 契约可能影响未纳入 `core` 的消费方 | 低 | **经 `IPositionTracker` 协议**访问的消费点仅 `engine_v2:761`；examples/agents/tests 的 `.get_snapshots()` 均通过具体 `PositionTracker`（E3），不受协议签名影响；`mypy .` 不在本批口径 |
| R5 | `ITradeLog` 当前无 typed 赋值点，结构一致性未被静态验证 | 低 | 已在 D2 如实声明；后续 typed 消费方受益 |
| R6 | 93 → 0 后门禁转绿，被误读为 U-006 已关闭 | 中 | CHECKLIST 与 PROGRESS 显式写「Q4=B，U-006 不关闭」 |
| R7 | 别名替换漏改一处导致仍引用 `self.x` | 中 | V1 机械拦截；按 D4 清单逐方法核对 |
| R8 | v3 别名若遇重绑定会产生陈旧引用 | 低 | D6 不变式：只原地写入；已核对无重绑定 |
| R9 | 新增 2 项测试可能暴露其他缺陷 | 低 | 若失败如实登记，不得弱化断言（RULE-3） |

---

## 6. 回退点

| 场景 | 操作 |
|------|------|
| 整体回退 | `git revert <本批提交>`（单笔，含测试与文档） |
| 仅回退行为变更（D1/D3） | `git checkout <前提交> -- core/engine_v2.py`，随之回退 D4/D5 的同文件改动 |
| 仅回退接口（D2） | `git checkout <前提交> -- core/interfaces.py`（engine_v2 的 B-1/B-2 会复现，需同步回退） |
| 仅回退 v3 / factory | 按文件 `git checkout` |

---

## 7. 范围外（明确不做）

| 项 | 理由 |
|----|------|
| Q3 `setup()` 盲区（9 条） | 用户裁决 A；含 X1/X2/`execute_order` 3 个语义决策（RESEARCH §13.4.4） |
| Q2-C 4 协议全面真实化 | 需 API 决策（补零调用方方法或删协议成员），另立批次 |
| 移除 `except Exception: continue`（A-1 症状放大器） | 改变逐日容错语义，需独立批次与测试设计 |
| `mypy .` 216 errors / 32 files | 不属 U-006；另立批次 |
| CI mypy 硬门禁（去掉 `&#124;&#124; true`） | Q4=B；且需先评估三版本差异 |
| `pyproject.toml` 严格度（`check_untyped_defs` / `strict`） | Q3=A；A24 建议按模块逐步启用 |
| 关闭 U-006 | 用户裁决 B |
| X1/X2/X3 语义修复 | 范围外发现，另行登记 |

---

## 8. 不变式（ADD 审计依据）

1. `setup()` 成功后，`dm` / `universe` / `pipeline` / `combiner` / `optimizer` / `trigger` / `executor` / `tracker` **必非 None**；`pending_queue` 在 `enable_pending_orders=True` 时非 None（与 `setup()` 分支一致）。
2. `factor_files` 为空时，`setup()` **必抛 `ValueError`**，且不进入逐日循环。
3. 未 setup 时调用 `_generate_results()` **必抛 `RuntimeError`**，不得抛 `AttributeError`。
4. `PositionTracker` 满足 `IPositionTracker`（含 `get_snapshots -> list[PortfolioSnapshot]`）。
5. `ExecutionSimulator` / `MockExecutionSimulator` 结构上满足 `IExecutionSimulator` 的 `trade_log` 只读 property 成员（E2 探针 `p007b_tradelog_variants.py`；`execute_order` 参数名差异除外，属 U-3）。
6. 除空因子路径外，引擎逐日交易行为不变（V4 全量回归为证）。
7. 不新增 `# type: ignore`；不改 mypy/CI 配置。
8. v3 的方法内别名只做原地写入，不重绑定 `self._*` 数组。

---

## 9. 未决项登记（四元块）

（无新增。Q1-Q4 已于 2026-11-09 裁决；残余 U-3（`setup()` 盲区）与 U-6（U-006）按 RESEARCH §13.5 继续挂起，触发条件不变。）

---

## 10. Step 4 Review（独立 pass）

- **执行时点**: 正文完稿（427 行）后的单独 pass（2026-11-10），与正文非同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 重跑 E1 基线命令 + 新建 E2 探针验证设计的 mypy 行为断言 + 逐行核对 93 条归因与 V1-V12 + 保护路径核查；不依赖正文自报

### 10.1 复算记录

| 项 | 方式 | 正文读数 | 复算读数 | 判定 |
|----|------|----------|----------|------|
| 基线 | `mypy --explicit-package-bases core`（本会话 raw 输出存档） | 93 = 54/26/13 | 93，逐行 54 条（engine_v2）/26（v3）/13（factory） | ✅ |
| 盲口径 | `mypy --explicit-package-bases --check-untyped-defs core` | V3 预期 9 / 2 files | **102 in 4 files**：engine_v2 **61**（+7）/ data_v3 **2**（+2）/ v3 26 / factory 13 → 批后余 9 in **2 files** | ✅ V3 成立 |
| 方法行号映射 | 分组脚本（`p007b_group.py`）+ def 行号 grep | D4 表 8 方法 54 条 | 7+5+7+6+11+5+6+7 = 54，逐行号一致（305/363/402/476/520/600/693/759 起） | ✅ |
| L762 条数 | raw 输出 | 正文「D2 覆盖 2 项」 | **762 两行**（`Item "IExecutionSimulator"` + `Item "None"`） | ⚠️ → F-D2（P3） |
| generate_report 签名 | Read `analytics.py:468-470` | L767 期望 `list[PortfolioSnapshot]` | `def generate_report(snapshots: list[PortfolioSnapshot], ...)` | ✅ D2 决定 1 可消除 arg-type |
| Mock 兼容 | Read `test_decoupled_engine.py:148,172,239,487-508` | D2 兼容行 | `trade_log = self` / `get_trades_df` / `get_snapshots() -> list`；**无类型化赋值点**（`mock` 为裸局部变量）→ D2 不产生新检查 | ✅ |
| 接口消费面 | Grep 两个接口名（`IPositionTracker` / `IExecutionSimulator`）全仓 | R4「协议访问仅 engine_v2:761」 | 命中仅 interfaces / engine_v2 / factory（返回注解）/ test 导入；examples/agents/tests 均经具体类 | ✅ R4 成立 |
| `__future__` | `interfaces.py:7` | Step 4 修正前提 | `from __future__ import annotations` 在文件头 | ✅ |

### 10.2 E2 探针（设计形态验证，`%TEMP%`，`[未入仓-不可重放]`）

**探针 1 `p007b_design_shape_probe.py`**（mypy 2.1.0，exit 1，2 errors）：

| 断言 | 结果 |
|------|------|
| P-1 链式 assert `a is not None and b is not None` 双窄化（D4 要点 2） | ✅ 0 error |
| P-2 `trade_log: ITradeLog` 可变属性成员 → `ExecutionSimulator` 式实现 | ❌ **`trade_log: expected "ITradeLog", got "TradeLog"`** → F-D1（P1） |
| P-3 协议方法返回 `list[PortfolioSnapshot]`（协变）+ `TYPE_CHECKING` dataclass | ✅ `accept_tracker(PositionTracker())` 通过 |
| P-4 局部别名 + assert 后 `.loc` / `.iloc` / `len` / `.columns` / 下标（D5/D6 机制） | ✅ 0 error |
| P-5 `cast(Optional[IPendingOrderQueue], v)`（D7 L183 形态） | ✅ 0 error |

**探针 2 `p007b_tradelog_variants.py`**（mypy 2.1.0，exit 0，`Success`）：

| 形态 | 普通属性实现（`Sim`） | `trade_log = self`（`MockSim`） |
|------|----------------------|--------------------------------|
| `@property def trade_log(self) -> ITradeLog`（协议只读成员） | ✅ 通过 | ✅ 通过 |
| `trade_log: Any`（对照） | ✅（但放弃类型） | ✅（但放弃类型） |

### 10.3 发现项

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-D1** | **P1** | **D2 决定 2 原形态（`trade_log: ITradeLog` 可变属性）在 mypy 下使实现方不符**：PEP 544 对可变协议属性要求**不变**（invariant），`TradeLog` 是子类型仍冲突（探针 1 实证）→ 不变式 5 为假、D7 的 `cast(IExecutionSimulator, ...)` 成为类型谎言 | 已回写：改为**只读 property 成员**（探针 2 实证 `Sim` + `MockSim` 双通过）；D2 代码块 / 依据表 / 被拒方案 / 不变式 5 / §3 行数（+12）同步修正 |
| F-D2 | P3 | 归因口径混用：B-2 按条目记 1，但 L762 物理为 2 行；「D2=2 / D4=43」是条目口径，物理行口径为 3/42 | 已回写：§1 补物理行口径注记（总和 93 不变，两口径下全部清除） |
| F-D3 | P3 | `interfaces.py` 已有 `from __future__ import annotations`，`list["PortfolioSnapshot"]` 引号非必需；与 D7「去掉引号」口径不一 | 已回写：决定 1 改无引号 + 注记 |
| F-D4 | P3 | V 契约缺测试文件数校验（层 A 有对应项） | 已回写：新增 V12（51 = 50 + 1） |

### 10.4 D ↔ Q 覆盖与保护路径

| 决策 | 来源 | 覆盖验证 |
|------|------|----------|
| D1（setup 入口 fail-fast） | Q1 / U-1 | V1 / V4 / T-B1；位置论证（部分初始化风险）与 RESEARCH §13.2.5 的偏离已披露 |
| D2（协议真实化，property 形态） | Q2 / U-2 | V1 / V10 / 探针 1+2 |
| D3（`_generate_results` 守卫） | A-2 | V1 / T-B2；agents 直接调用点（`multi_strategy_engine.py:768,910`）均在 `run()` 之后，不受影响 |
| D4/D5/D6（局部别名 78 条） | C-1/C-2/C-3/C-4 + A-1 | V1 / V2 / 探针 1 P-1/P-4 |
| D7（factory 13 条） | C-5 | V1 / V2 / 探针 1 P-5 |
| D8（2 项 smoke） | Q1 / A-2 | V4 / V5 / V12 |
| D9（范围边界） | Q3 / Q4 | V3 / V8 / V9 |

| 路径 | 约束 | 验证 |
|------|------|------|
| CI workflow | 零改动 | V8 |
| `pyproject.toml [tool.mypy]` | 零改动 | D9 + V1 读数可比性 |
| `# type: ignore` | 不扩张（仍 1 处，实测确认） | V7 |
| 逐日行为 | 除空因子路径外不变 | V4（516）+ 不变式 6 |
| agents 直调 `_generate_results` | 不回归 | D3 守卫仅在未 setup 时触发；调用点均在 `run()` 后 |

**被拒代价完整性**：D1 三方案 + 位置偏离披露；D2 三被拒（cast / 可变属性 / 全面真实化）；D5 与 RESEARCH 的 property 偏离披露；D7 泛型与传类两被拒。

**结论**: 1 P1 + 3 P3，**全部已回写**。D1-D9 与 Q1-Q4 裁决全覆盖，V1-V12 无悬空，探针实证设计代码形态在本机 mypy 2.1.0 下可行。**Step 4 通过，可进入 Step 5 实施规划。**

---

**Review 签字**: 单 Agent 自查（RULE-4） 日期: 2026-11-10
