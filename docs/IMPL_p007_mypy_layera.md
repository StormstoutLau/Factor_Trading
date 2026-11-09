# P-007 层 A（非引擎 mypy 清理） · 实施规划

> **文档编号**: IMPL_p007_mypy_layera
> **阶段**: Phase 1 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: Step 6 Review 通过（3 项 P2 事实性修正已回写 T-5/T-6/T-7）
> **上游**: [DESIGN_p007_mypy_layera.md](DESIGN_p007_mypy_layera.md)（Step 4 通过，D1-D9 / V1-V10）
> **下游**: [CHECKLIST_p007_mypy_layera.md](CHECKLIST_p007_mypy_layera.md)
> **证据时点**: 本仓读数 @ `8082784`；解释器 Python 3.12.10
> **档位**: T1（`core/` 16 文件）

---

## 1. 执行总览

### 1.1 任务分解

| ID | 任务 | 依赖 | 产出 | 验证 |
|----|------|------|------|------|
| T-0 | 记录 RED 基线（5 项读数） | — | §2 表 | 5 项全部符合预期 |
| T-1 | A-4：删除 `data.py` L184-231 死代码 | T-0 | −48 行 | V1（data.py 0 error） |
| T-2 | A-1：修 `risk_monitor.py` 的 `RiskAction` 与重复声明 | T-1 | ±3 行 | V1 |
| T-3 | A-2：修 `global_contagion.py` 的 `evaluate` → `monitor` | T-2 | ±2 行 | V1 |
| T-4 | A-3：修 `engine_plugins.py` 参数传递 | T-3 | ±1 行 | V1 |
| T-5 | B 类：`live_bridge` isinstance + `portfolio` 3 处 assert | T-4 | ±5 行 | V1 |
| T-6 | C 类 16 项注解修正（含删除 `walk_forward_engine` 的 `__main__` 块） | T-5 | ±25 行 | V1 / V2 |
| T-7 | 新增 `tests/test_mypy_layera_smoke.py`（3 项） | T-4 | +40 行 | V5 |
| T-8 | 全量验证 V1-V10 | T-1~T-7 | 读数 | §4 全绿 |
| T-9 | 四文档 + 台账 + 提交 + 推送 + CI | T-8 | — | V9 / CI |

### 1.2 执行顺序

```
T-0 RED
  │
  ├─► T-1 删死代码 ──► T-2 A-1 ──► T-3 A-2 ──► T-4 A-3 ──┐
  │                                                       ├─► T-8 全量验证 ──► T-9
  ├─► T-5 B 类 ───────────────────────────────────────────┤
  ├─► T-6 C 类 ───────────────────────────────────────────┤
  └─► T-7 smoke 测试（依赖 T-4 完成的实现）───────────────┘

任一步失败 → 停止并按 §6 回退，不跨步骤修补
```

### 1.3 关键原则

| 原则 | 说明 |
|------|------|
| 先删死代码再修缺陷 | T-1 先消除最大噪声（48 行重复实现），便于后续 mypy 读数聚焦真实项 |
| 每任务后立即看 mypy 读数 | 用 `mypy core` 的分文件计数确认该任务消除的错误数，防止「改了但没消除」 |
| 不做 opportunistic 重构 | 只修 26 项，不动相邻代码、不改命名风格、不调整 import |
| 测试失败不得弱化 | 若 T-7 的 smoke 暴露新问题，如实登记并停下确认，不得放宽断言凑绿 |

---

## 2. T-0：RED 基线（实施前必录）

| ID | 断言 | 命令 | RED 读数 | GREEN 目标 |
|----|------|------|----------|------------|
| RED-1 | 非引擎 errors 应为 0 | `mypy core` 过滤三引擎文件 | **26** | **0** |
| RED-2 | 总数应降至 93 | `mypy --explicit-package-bases core` | **119 errors in 19 files** | **93 errors in 3 files** |
| RED-3 | 全量测试 | `pytest -q` | **507 passed** | **510 passed** |
| RED-4 | 格式合规 | `black --check .` | exit 0，`135 files would be left unchanged` | exit 0，**136**（+1 新测试） |
| RED-5 | `type: ignore` 基线 | Grep 全仓 | **1 处**（`tests/test_execution_policy.py:294`） | 仍 **1 处** |

**门禁基线**：`mypy-check` verdict = **fail**（119）；`black-check` = **pass**；`unit-tests` = **pass**（507）。

---

## 3. 逐任务实施文本

### T-1 A-4：删除 `core/data.py` 的死方法（L184-231）

```powershell
# 精确删除 L184-231（含 def 行与其后空行边界），保留 L232 起的 _apply_date_filter
```

| 项 | 内容 |
|----|------|
| 依据 | 同名方法在 L312 重复定义，L184 版本在 Python 语义上**永不可达**（被覆盖） |
| 删除范围 | L184（`def _load_auxiliary_data`）至 L231（方法体末行）；L232 为 `def _apply_date_filter`，保留 |
| 不做的 | 不把 L184 的安全默认值逻辑合并进 L312（DESIGN D1；行为修复 → P-010） |
| 验证 | `mypy core` 中 data.py 的 `no-redef` 消失；`pytest -q` 仍 507 passed |

### T-2 A-1：`core/risk_monitor.py`（L720-724）

```python
# 旧
        self._signal_history: list[RiskSignal] = []
        self._action_history: list[RiskAction] = []
# 新
        self._signal_history = []
        self._action_history = []
```

| 项 | 内容 |
|----|------|
| 消除 | `name-defined` 1 + `no-redef` 2 = **3** |
| 说明 | 去掉带注解的重复声明即可；`RiskAction` 随注解移除而消失（类型已在 L713/L714 声明为 `MonitorAction`） |
| 备选（被拒） | 改 `RiskAction` → `MonitorAction` 保留注解——仍会报 `no-redef`，未解决重复声明 |

### T-3 A-2：`core/global_contagion.py`（L631）

```python
# 旧
    signal, _ = monitor.evaluate(market_returns=market_returns, market_vols=market_vols)
# 新
    signal = monitor.monitor(market_returns=market_returns, market_vols=market_vols)
```

| 项 | 内容 |
|----|------|
| 消除 | `attr-defined` 1 |
| 说明 | 返回单值 `RiskSignal`；原 tuple 解包写法必然抛 `AttributeError`，无兼容负担 |

### T-4 A-3：`core/engine_plugins.py`（L381）

```python
# 旧
        return get_trigger_registry().create(config.method, config, trade_dates)
# 新
        # 工厂第二形参名为 dates（见 _register_triggers 的三个注册）
        return get_trigger_registry().create(config.method, config, dates=trade_dates)
```

| 项 | 内容 |
|----|------|
| 消除 | `call-arg` 1 |
| 说明 | `**kwargs` 透传至 `lambda cfg, dates:`；用 `dates=` 关键字与既有契约一致 |
| 备选（被拒） | 改 3 个 lambda 形参名 → 改动面 4 行且触及触发器语义 |

### T-5 B 类：4 处防御

| 文件:行 | 改动 |
|---------|------|
| `live_bridge.py:174` | 模块头补 `from core.config import AssetType`（现未导入，**必须新增**）；`asset_type=(intent.asset_type.value if isinstance(intent.asset_type, AssetType) else intent.asset_type),` |
| `portfolio.py:223` | 在 `cov_matrix = cov_estimator(returns[selected_stocks])` 前加 `assert returns is not None` |
| `portfolio.py:300` | 在 `portfolio_variance = cp.quad_form(w, cov_matrix.values)` **前**加 `assert cov_matrix is not None`（报错对象是 `cov_matrix`，非 `expected_returns`） |
| `portfolio.py:355` | 在 `cov_matrix = cov_estimator(returns[selected_stocks])` 前加 `assert returns is not None` |

| 项 | 内容 |
|----|------|
| 消除 | `union-attr` 2（live_bridge `str|AssetType` + portfolio `cov_matrix`）+ `index` 2 = **4** |
| 前提 | `AssetType` 位于 `core/config.py:119`（`class AssetType(str, Enum)`）；`live_bridge.py` 现仅 `TYPE_CHECKING` 导入 `OrderIntent`，运行时不导入任何 `core.*`——**本任务须新增运行期 import**。`core/config.py` 仅依赖 stdlib，无循环导入风险；`execution_policy.py:27` 已有同样导入可作先例 |
| 限制 | `assert` 在 `-O` 下失效（DESIGN R1） |

### T-6 C 类：16 项

| 文件:行 | 错误码 | 改动 |
|---------|--------|------|
| `config.py:199` | `no-any-return` | 返回处 `cast(AssetCost, ...)` |
| `walk_forward.py:250` / `258` | `no-any-return` ×2 | `cast(float, ...)` |
| `execution.py:235` | `no-any-return` | `cast(float, ...)` |
| `pending.py:538` | `no-any-return` | `cast(list[str], ...)` |
| `config_v2.py:237` | `no-any-return` | `cast(Path, ...)`（冻结资产，仅此一处） |
| `rebalance.py:202` | `return-value` | `return float(...)` |
| `pending.py:462` | `assignment` | L446 `stats = {` → `stats: dict[str, Any] = {`（`stats` 现被推断为 `dict[str, int]`；**不做 int() 截断**，与返回类型 `dict[str, Any]` 一致） |
| `global_contagion.py:192` / `163` | `assignment` | L163 `metadata: dict[str, Any] = {}` |
| `factor.py:338/343/352` | `assignment` ×2 + `call-overload` | 收集阶段改 `X_list: list[np.ndarray] = []`（L310）、`X_list.extend(...)`（L323）、`X_list.append(...)`（L331）、`if not X_list:`（L333）；L338 起 `X = np.column_stack(X_list)`（L343/L352 随即落在 ndarray 上） |
| `attribution.py:335` | `var-annotated` | `sectors: set[str] = set()` |
| `global_contagion.py:346` | `var-annotated` | `results: dict[str, Any] = {}` |
| `tracker.py:335` | `var-annotated` | `sector_exposure: dict[str, float] = {}` |
| `walk_forward_engine.py:284-293` | `arg-type` | **删除整个 `if __name__ == "__main__":` 块** |

> 所有 `cast` 处需确认目标类型已导入：`config.py` / `walk_forward.py` / `execution.py` / `pending.py` / `config_v2.py` 当前**均未导入 `cast`**（现有 typing 导入分别为 `Any`、`Iterator, Optional`、`Any, Callable, Optional`、`Any, Optional`、`Any, Callable, Literal, Optional`），T-6 须逐文件补 `cast`。

### T-7 新增 `tests/test_mypy_layera_smoke.py`（3 项）

| 测试 | 构造 | 断言 |
|------|------|------|
| `test_remove_monitor_does_not_raise` | `CompositeRiskEngine()`（`risk_monitor.py:698`，无参构造 → 默认 5 个监控器）→ `engine.remove_monitor("nonexistent")` | 不抛异常；`len(engine.monitors) == 5`（RED：T-2 前 L724 抛 `NameError: RiskAction`） |
| `test_analyze_market_contagion_returns_dict` | `analyze_market_contagion({"A": pd.Series(...), "B": pd.Series(...)})`（`market_vols=None`，由 L629 内部按 std 推导） | 返回 `dict`，键集含 `signal` 与 `summary`（`global_contagion.py:633`）（RED：T-3 前抛 `AttributeError: evaluate`） |
| `test_create_trigger_via_registry` | `RegistryPlugin().enable()` + `create_trigger(RebalanceConfig(method="fixed", frequency="monthly"), pd.date_range("2024-01-01", "2024-12-31", freq="B"))` | 不抛 `TypeError`；返回 `FixedIntervalTrigger` 实例（RED：T-4 前 `Too many arguments for "create"`） |

| 项 | 内容 |
|----|------|
| 计数 | 507 → **510**；测试文件 48 → **49** |
| 覆盖缺口证据 | `tests/test_engine_plugins.py:325-329` 存在**被注释掉**的 `plugin.create_trigger(...)` 三行断言，正文为 `print("✓ Registry 创建 trigger (跳过，参数适配需额外处理)")`——这正是 A-3 长期未被发现的原因；本任务**不修改该文件**（避免扩大 diff），新测试复刻其构造 |
| 禁止 | 用 `pytest.raises` 把「应该不崩」写成「验证会崩」 |

### T-8 全量验证

按 DESIGN V1-V10 逐条执行并记录读数（§4）。

### T-9 文档与提交

| 文件 | 动作 |
|------|------|
| 四文档 `*_p007_mypy_layera.md` | 本批工件 |
| `docs/PROGRESS.md` | P-007 状态更新（层 A 完成、层 B 剩余）；**新增 P-010** 登记；§3.9 批次记录 |
| `docs/RESEARCH_tech_debt_cleanup.md` | 如需（TD 无 mypy 专项条目，可只在 PROGRESS 记录） |
| `CHANGELOG.md` | `[Unreleased] > Fixed` 追加（3 处真实缺陷 A-1/A-2/A-3 + 1 处死代码移除 A-4，后者注明「行为不变」；P-010 的登记只进 PROGRESS，不写进 CHANGELOG 的 Fixed） |

提交：单笔 `fix(P-007): 清理非引擎 mypy 错误并修复 4 处缺陷（层 A）`。

---

## 4. 验证清单（V1-V10）

| ID | 命令 | 期望 |
|----|------|------|
| V1 | `mypy core` 过滤三引擎 | **0** |
| V2 | `mypy --explicit-package-bases core` | **`93 errors in 3 files`** |
| V3 | 同上按文件分流 | engine_v2 **54** / v3_vector **26** / factory **13**（与基线逐字一致） |
| V4 | `pytest -q` | **`510 passed`** |
| V5 | `pytest tests/test_mypy_layera_smoke.py -q` | **`3 passed`** |
| V6 | `black --check .` | exit 0，**136** unchanged |
| V7 | `git diff --stat -- core/engine_v2.py core/engine_v3_vector.py core/factory.py` | **空** |
| V8 | Grep `type: ignore` | **1 处**（未扩张） |
| V9 | `adapter gate mypy-check` | verdict **fail**（93，如实） |
| V10 | `Get-ChildItem tests -Filter 'test_*.py'` | **49** |

---

## 5. 低效/危险操作排除表

| 禁止操作 | 原因 |
|----------|------|
| 新增 `# type: ignore` | 违背清理目标，且本仓仅有 1 处惯例 |
| 修改 `[tool.mypy]`（降低 `warn_return_any` 等） | 读数不可比，等于掩盖问题 |
| 改引擎三件套（`engine_v2`/`v3_vector`/`factory`） | 属层 B；本批零改动 |
| 把 `data.py` 的安全默认值合并进来 | 行为变更须独立批次（P-010） |
| 用 `try/except pass` 替代 assert | 吞掉异常，比 assert 更糟 |
| 为让 smoke 通过而放宽断言 | 违反「测试失败须如实登记」 |
| 顺手重命名/重排 import/格式化相邻代码 | 扩大 diff 面，掩盖真实改动 |
| 删除 `remove_monitor` / `analyze_market_contagion` 等函数 | 它们是合理 API 面，修复优于删除 |
| 一个任务内混合多类修复 | 违反单任务可追溯到错误码的原则 |

---

## 6. 红 → 绿执行序

| 序 | 动作 | 预期 |
|----|------|------|
| 1 | T-0 记录 RED | 26 / 119 / 507 / 135 / 1 |
| 2 | T-1 删死代码 | 26 → 25 |
| 3 | T-2 A-1 | 25 → 22（消除 3） |
| 4 | T-3 A-2 | 22 → 21 |
| 5 | T-4 A-3 | 21 → 20 |
| 6 | T-5 B 类 | 20 → 16 |
| 7 | T-6 C 类 | 16 → **0** |
| 8 | T-7 smoke | 507 → 510 |
| 9 | T-8 全量验证 | V1-V10 全绿 |
| 10 | T-9 文档 + 提交 + 推送 + CI | 三 job 全绿 |

> **递减验证**：每步后跑一次分文件计数，确认该步消除的错误数与预期一致；不符即停。

---

## 7. 回退点

| 断点 | 操作 |
|------|------|
| 单任务失败 | `git checkout -- <该文件>` 恢复到 T-0 状态，重做该任务 |
| 全部完成后发现问题 | `git revert <本批提交>`（单笔含测试与文档） |
| 仅回退删死代码 | `git checkout <前提交> -- core/data.py` |

---

## 8. 会话与门禁

- **Session**: `factorv3-p007-mypy-layera-20261109`
- **门禁预期**：probe pass / unit-tests pass(510) / black-check pass(136) / **mypy-check fail(93)**——较基线 119 改善但**仍 fail，U-006 不关闭**
- **replay 期望**：4 rows OK

---

## 9. Step 6 Review（独立 pass）

> 审查方式：对照 D1-D9 / V1-V10 逐条核对任务覆盖 + 递减序算术 + 排除表覆盖度 + smoke 构造可行性。以下每一条均以 `mypy --explicit-package-bases core` 实测（@ `8082784`）与本仓读码为依据。
> 结论：**通过**；3 项 P2 事实性错误已回写正文（T-5 / T-6 / T-7），4 项 P3 已就地收紧表述。

### 9.1 事实核实（E1 实测）

| ID | 核实项 | 方式 | 结果 |
|----|--------|------|------|
| C-1 | 非引擎 error 总数 | `mypy --explicit-package-bases core` 过滤 | **26**，逐文件分布：config 1 / walk_forward 2 / risk_monitor 3 / rebalance 1 / pending 2 / data 1 / attribution 1 / walk_forward_engine 1 / global_contagion 3 / execution 1 / factor 3 / portfolio 3 / live_bridge 1 / tracker 1 / engine_plugins 1 / config_v2 1 |
| C-2 | 引擎侧 error 分布 | 同上 | engine_v2 **54** / engine_v3_vector **26** / factory **13** = 93；与 DESIGN V3 逐字一致 |
| C-3 | 递减序算术 | 26 →（T-1 减 1）25 →（T-2 减 3）22 →（T-3 减 1）21 →（T-4 减 1）20 →（T-5 减 4）16 →（T-6 减 16）**0** | 合计 26 ✓ |
| C-4 | T-2 目标类可构造 | 读 `risk_monitor.py:698-724` | `CompositeRiskEngine(monitors: Optional[list] = None)`，无参可构造，默认 5 个监控器 ✓ |
| C-5 | T-3 目标函数契约 | 读 `global_contagion.py:622-633` | `analyze_market_contagion(market_returns, market_vols=None)` → `{"signal": ..., "summary": ...}` ✓ |
| C-6 | T-4 工厂形参名 | 读 `engine_plugins.py:353-367` + `registry.py:135/147-153` | 三个 lambda 均为 `(cfg, dates)`；`PluginRegistry.create(name, config=None, **kwargs)` 透传 ✓ |
| C-7 | A-3 未被发现的根因 | 读 `tests/test_engine_plugins.py:325-329` | `create_trigger` 断言被整段注释，替换为 print「跳过」——覆盖缺口实证 ✓ |

### 9.2 发现项

| ID | 级别 | 位置 | 问题 | 处置 |
|----|------|------|------|------|
| F-I1 | **P2** | T-5 `portfolio.py:300` | 原定「加 `assert expected_returns is not None`」与实测报错对象不符：mypy 原文为 `Item "None" of "Any \| None" has no attribute "values"`，指向 `cov_matrix`（`returns is None` 的 else 分支中 `cov_matrix` 保持 Optional）；`expected_returns` 在两个分支均已赋值，不会报错 → 按原方案改完 error **不会消失** | 已改为 `assert cov_matrix is not None`（正文 T-5） |
| F-I2 | **P2** | T-5 `live_bridge.py:174` | 原文将「`AssetType` 已导入」降级为「实施时确认」；实测 `live_bridge.py` 全文无 `AssetType`，仅 `TYPE_CHECKING` 导入 `OrderIntent` → 直接写 `isinstance(..., AssetType)` 会 `NameError` | 已把「模块头补 `from core.config import AssetType`」升级为任务必做项，并核实无循环导入（`config.py` 仅依赖 stdlib；`execution_policy.py:27` 同款导入为先例） |
| F-I3 | **P2** | T-6 全表 | 5 个待 `cast` 文件（`config.py` / `walk_forward.py` / `execution.py` / `pending.py` / `config_v2.py`）**当前均未导入 `cast`**；IMPL 原注「本仓多数文件已有」为误判 | 已改为逐文件点名并要求补导入（正文 T-6 注） |
| F-I4 | P3 | T-6 `pending.py:462` | 原表述「`int(...)` 或 `float(...)` 按语义选」留了二义；实测 `stats` 由 L446 字面量推断为 `dict[str, int]`，任何 float 赋值都报错。`int()` 会**截断平均重试次数**（0.7→0），属语义变更 | 已改为 `stats: dict[str, Any] = {`（零运行时影响，与返回类型一致），并显式禁止 int 截断 |
| F-I5 | P3 | T-6 `factor.py` | 报错行实为 **338 / 343 / 352**（L310/331/333 本身不报）；且遗漏 L323 `X.extend(...)` 也须同步改名 | 已更正行号与改动点清单 |
| F-I6 | P3 | T-7 | 原「实例化风险聚合器（构造签名实施时确认）」属未定项 | 已补全三个测试的具体构造（类名 / 导入路径 / 配置对象 / 日期索引 / RED 现象） |
| F-I7 | P3 | T-9 台账 | 原仅写「`docs/RESEARCH_tech_debt_cleanup.md` 如需」——DESIGN D1 明确要求登记 **P-010**，该登记必须在 `docs/PROGRESS.md` 落地 | 正文 T-9 已明确「新增 P-010 登记」为必做；本 Review 再次确认为 CHECKLIST 验收项 |

### 9.3 覆盖度与排除表核对

| 核对项 | 结果 |
|--------|------|
| D1-D9 → 任务映射 | D1→T-1；D2→T-2；D3→T-3；D4→T-4；D5→T-5；D6→T-6；D7→T-7；D8→T-6（`config_v2` 单点）；D9→T-8/V1-V10 与 §8 门禁预期 —— **全覆盖，无遗漏、无越界** |
| V1-V10 → 任务映射 | V1/V2/V3←T-1~T-6；V4/V5←T-7；V6←新增测试文件格式；V7←排除表（引擎零改动）；V8←排除表（禁 `type: ignore`）；V9←§8；V10←T-7 文件计数 —— **全覆盖** |
| 排除表覆盖度 | 9 条禁止项与 D1-D9 无冲突；「不得合并安全默认值」（D1/P-010）、「不得改 mypy 配置」（V2 可比性）、「不得改引擎」（层 A 边界）三条是本批红线，已进入 CHECKLIST |
| 增量风险 | T-1 删除 48 行后 `data.py` 的 `_load_auxiliary_data` 仅剩 L312 版本，`mypy` 的 `no-redef` 消失且**运行时行为零变化**（死代码）；T-5 的 4 处 `assert` 在正常路径永不触发，仅在调用方违约时提前失败——属防御性改善，无行为变更 |
| 未纳入项 | `tests/test_engine_plugins.py` 的注释块保持原样（避免扩大 diff）；`data.py` 安全默认值缺失登记为 P-010 而非本批修复（D1） |

### 9.4 Review 结论

- P0 / P1：**0**
- P2：**3**（F-I1 / F-I2 / F-I3，均已回写正文，无遗留）
- P3：**4**（F-I4~F-I7，均已就地收紧）
- 判定：IMPL 与 DESIGN 一致，任务粒度满足「单任务可追溯到错误码 + 可独立回退」，可进入 Step 7。
