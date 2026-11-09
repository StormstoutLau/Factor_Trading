# P-007 层 A（非引擎 mypy 清理） · 设计文档

> **文档编号**: DESIGN_p007_mypy_layera
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: 完稿；Step 4 Review **通过**（2026-11-09；0 项阻断，2 项 P3 已回写，见 §9）；Step 8 一致性 Review 修正 §1 总览 D2 表述（F-S1，见 CHECKLIST §7）
> **上游**: [RESEARCH_p007_mypy_layera.md](RESEARCH_p007_mypy_layera.md)（Step 2 通过，A/B/C 三类 + Q1-Q6）
> **下游**: [IMPL_p007_mypy_layera.md](IMPL_p007_mypy_layera.md) → [CHECKLIST_p007_mypy_layera.md](CHECKLIST_p007_mypy_layera.md)
> **证据时点**: 本仓读数 @ `8082784`；解释器 Python 3.12.10
> **档位**: T1（`core/` 16 文件）

---

## 1. 决策总览

| ID | 决策项 | 决定 | 对应 |
|----|--------|------|------|
| **D1** | A-4 `data.py` 重复定义 | **删除 L184 死代码（48 行），保留 L312 为唯一实现；不改运行时行为**；行为退化另立待办 P-010 | Q1 |
| **D2** | A-1 `risk_monitor` | **修**：L723/L724 改为无注解赋值（类型已在 L713/L714 声明），`RiskAction` 随注解移除而消失；**不改名为 `MonitorAction` 保留注解**（仍会 `no-redef`） | Q2 |
| **D3** | A-2 `global_contagion` | **修**：`monitor.evaluate(...)` → `signal = monitor.monitor(...)`（单值返回） | Q2 |
| **D4** | A-3 `engine_plugins` | **修**：位置参数 `create(name, config, trade_dates)` → 关键字 `create(name, config, dates=trade_dates)` | Q2 |
| **D5** | B 类防御 | B-1 用 `isinstance` 分支；B-2/3/4 用 `assert x is not None` | Q3 |
| **D6** | C 类 16 项 | `cast` / 补注解 / 变量重声明；**禁止 `# type: ignore`** | Q5 |
| **D7** | 测试 | 为 A-1/A-2/A-3 各补 **1 项 smoke 测试**；A-4 不补（未改行为） | Q4 |
| **D8** | `config_v2.py`（冻结） | **允许 1 处注解修正**（`cast`），不动其他 | Q6 |
| **D9** | 范围边界 | 引擎三件套零改动；mypy **119 → 93**；**U-006 不关闭** | — |

---

## 2. 逐项决策与依据

### D1 A-4：删除死代码，不改行为

**现状**：`_load_auxiliary_data` 在 `data.py` L184 与 L312 各定义一次，后者覆盖前者。L312 缺失「数据缺失时设安全默认值」逻辑。

**决定**：删除 L184-231（48 行），L312 保持原样。

**理由**：
1. 本批目标是 mypy 清理，**行为修复应独立批次**——改默认值会改变「文件缺失时回测是否继续」的语义，需独立测试设计（构造缺失场景）与验收口径。
2. 删除死代码即可消除 `no-redef`，达成 mypy 目标。
3. 诚实前提：该行为退化**必须登记**，不得因删除死代码而「看起来已修」。

**被拒方案与代价**：

| 方案 | 代价 |
|------|------|
| ① 保留 L312 现状 + 删除 L184（**采纳**） | 行为退化留存，须另立待办 |
| ② 删除 L184 并把默认值合并进 L312 | 改变运行时行为（文件缺失时由返回 `None` 变为返回默认 DataFrame）；本批无对应测试，回归面不可控 |
| ③ 删除 L312、保留 L184 | 丢失 L312 的前置 `_load_basic_data()` 检查，且 L184 无该检查，可能引发 `NoneType` 索引错误——**方向错误** |

**派生待办（登记为 P-010）**：`data.py` `_load_auxiliary_data` 缺失安全默认值 → 辅助数据文件缺失时 getter 返回 `None` 且每次访问重复加载/重复告警。

### D2 A-1：修复 `RiskAction` 与重复声明

**改动**（`risk_monitor.py` L720-724）：

```python
# 旧
    def remove_monitor(self, monitor_name: str) -> None:
        """移除监控器"""
        self.monitors = [m for m in self.monitors if m.name != monitor_name]
        self._signal_history: list[RiskSignal] = []
        self._action_history: list[RiskAction] = []
# 新
    def remove_monitor(self, monitor_name: str) -> None:
        """移除监控器"""
        self.monitors = [m for m in self.monitors if m.name != monitor_name]
        self._signal_history = []
        self._action_history = []
```

| 项 | 内容 |
|----|------|
| 消除 | `name-defined` 1 + `no-redef` 2 |
| 语义 | 修复 `NameError`；去掉带注解的重复声明（L713/L714 已声明类型） |
| 风险 | 极低（0 调用） |
| 验证 | 新增 smoke 测试调用 `remove_monitor()` |

### D3 A-2：修复不存在的方法调用

**改动**（`global_contagion.py` L631）：

```python
# 旧
    signal, _ = monitor.evaluate(market_returns=market_returns, market_vols=market_vols)
# 新
    signal = monitor.monitor(market_returns=market_returns, market_vols=market_vols)
```

| 项 | 内容 |
|----|------|
| 依据 | `GlobalContagionMonitor.monitor()` 返回 `RiskSignal`（E3 `global_contagion.py:138-151`）；基类抽象方法亦为 `monitor()` |
| 消除 | `attr-defined` 1 |
| 语义 | 修复 `AttributeError`；返回值由「tuple 解包」改为单值（原写法必然抛错，故无兼容负担） |
| 风险 | 极低（0 调用） |

### D4 A-3：修复触发器创建的参数传递

**改动**（`engine_plugins.py` L381）：

```python
# 旧
        return get_trigger_registry().create(config.method, config, trade_dates)
# 新
        return get_trigger_registry().create(config.method, config, dates=trade_dates)
```

| 项 | 内容 |
|----|------|
| 依据 | 3 个已注册工厂统一签名为 `lambda cfg, dates: ...`（`engine_plugins.py:353-367`）；`PluginRegistry.create(name, config=None, **kwargs)` 透传 `**kwargs` 至工厂（`registry.py:135`/`153`） |
| 消除 | `call-arg` 1 |
| 语义 | 修复 `TypeError: create() takes from 2 to 3 positional arguments but 4 were given` |
| 备选（被拒） | 改 3 个 lambda 形参名为 `trade_dates` —— 改动面 4 行、涉及 3 个触发器语义，超出「修复调用错误」的最小面 |
| 风险 | 低（0 调用）；已用注释注明「工厂第二形参名为 `dates`」 |

### D5 B 类：最小防御

| 位置 | 改动 | 理由 |
|------|------|------|
| `live_bridge.py:174` | `asset_type=(intent.asset_type.value if isinstance(intent.asset_type, AssetType) else intent.asset_type)` | `str \| AssetType` 是**真两态**，`isinstance` 是正确的区分方式；仅改注解不能防 `str` 分支的 `AttributeError` |
| `portfolio.py:223` | `assert returns is not None` | 契约声明：`optimize` 必须有收益数据 |
| `portfolio.py:300` | `assert expected_returns is not None` | 同上 |
| `portfolio.py:355` | `assert returns is not None` | 同上 |

**承诺与限制（如实声明）**：`assert` 在 `python -O` 下被移除，届时防御失效。本仓未启用 `-O` 运行（CI 与本地均无），故当前有效；该限制须登记于风险表。

**被拒方案**：仅把参数注解改为非 Optional——会让 mypy 消失但**掩盖真实风险**（调用方仍可能传 None），违背清理初衷。

### D6 C 类 16 项修法

| 错误码 | 数量 | 修法 |
|--------|------|------|
| `no-any-return` | 6 | 返回处 `cast(T, expr)`；若来源可收窄则收窄（逐处判断，优先 cast 保持最小改动） |
| `assignment` | 4 | ① `rebalance.py:202` / `pending.py:462`：`float(...)` / `int(...)` 显式转换（numpy `floating[Any]` → 原生类型）；② `factor.py:338` / `352`：**变量改名分离两阶段**——收集阶段用 `X_list: list[np.ndarray] = []`（L310 + L331 的 `append` + L333 的 `if not`），计算阶段 `X = np.column_stack(X_list)` 后即 ndarray；③ `global_contagion.py:192`：**给 `metadata` 补显式注解** `dict[str, Any]`（L163），因其值类型被 mypy 从后续 dict 赋值误推断为 `dict[Any, Any]` |
| `var-annotated` | 3 | 补显式注解（`attribution.py:335` `set[str]`、`global_contagion.py:346`、`tracker.py:335` `dict[...]`，均以实际元素类型为准） |
| `return-value` | 1 | `rebalance.py:202` 与 `assignment` 同处，`float(...)` 一并解决 |
| `call-overload` | 1 | `factor.py:343` 随 `X` 改名（`X` 在整个计算阶段均为 ndarray）自然消除 |
| `arg-type` | 1 | `walk_forward_engine.py:290` 位于 `if __name__ == "__main__":` 块（L284-293）→ **删除该块**（非生产路径，且块内 `base_engine_class=None` / `config=None` 本身就不可用） |

**禁止**：`# type: ignore`——本仓全仓仅 1 处，本批不得扩张。

### D7 测试：3 项 smoke

| ID | 测试 | 断言 |
|----|------|------|
| T-A1 | `test_remove_monitor_does_not_raise` | 构造聚合监控器 → `remove_monitor("nonexistent")` → 不抛 `NameError` |
| T-A2 | `test_analyze_market_contagion_returns_dict` | 传最小 `market_returns` → 返回 dict 含 `signal` / `summary` |
| T-A3 | `test_create_trigger_via_registry` | 启用 RegistryPlugin → `create_trigger(config, dates)` → 不抛 `TypeError` |

**测试计数**：507 → **510**（新增 3 项）。

**A-4 不补测试**：因未改变行为，补测将固化为「当前的错误行为」。

### D8 冻结资产改动边界

`config_v2.py` 仅允许 L237 一处 `cast` 修正（`no-any-return`），附带 1 行 `cast` 导入（`from typing import ... cast`，不构成第二处修正）。判据：TD-2 冻结语义为「不新增功能、不接生产路径」，**修正既有类型缺陷不属于新增功能**。

### D9 范围边界

| 项 | 状态 |
|----|------|
| 引擎三件套（`engine_v2` / `engine_v3_vector` / `factory`） | **零改动** |
| mypy 总数 | **119 → 93**（仍 fail） |
| U-006 | **不关闭**（判据是 0 errors） |
| black | 保持 P-003 基线（`black --check .` exit 0） |

---

## 3. 精确变更面

| 文件 | 变更性质 | 预估行数 |
|------|----------|----------|
| `core/data.py` | 删除死方法 L184-231 | **−48** |
| `core/risk_monitor.py` | 修 `RiskAction` + 去重复声明 | ±3 |
| `core/global_contagion.py` | 修 `evaluate`→`monitor`；C 类 2 处 | ±5 |
| `core/engine_plugins.py` | 修参数传递 | ±1 |
| `core/live_bridge.py` | `isinstance` 分支 | ±2 |
| `core/portfolio.py` | 3 处 assert | +3 |
| `core/factor.py` | `X` 类型修正（3 error） | ±6 |
| `core/config.py` / `config_v2.py` / `execution.py` / `pending.py` / `rebalance.py` / `walk_forward.py` / `attribution.py` / `tracker.py` | C 类注解 | 各 ±1-3 |
| `core/walk_forward_engine.py` | 删除 `__main__` 块 | −10 |
| `tests/test_mypy_layera_smoke.py`（新增） | 3 项 smoke | +40 左右 |
| `docs/`（四文档 + PROGRESS） | 本批工件 | 新增 |

**净变化预估**：代码约 `−60 / +30`。

---

## 4. 验证契约

| ID | 断言 | 命令 | 期望 |
|----|------|------|------|
| V1 | 层 A errors 清零 | `mypy core` 非引擎过滤 | **0** |
| V2 | 总数降至 93 | `mypy --explicit-package-bases core` | `93 errors in 3 files` |
| V3 | 引擎 3 文件读数不变 | 同上按文件分流 | engine_v2 **54** / v3_vector **26** / factory **13** |
| V4 | 全量测试 | `pytest -q` | **`510 passed`**（507 + 3） |
| V5 | 新增 smoke 通过 | `pytest tests/test_mypy_layera_smoke.py -q` | `3 passed` |
| V6 | 格式不回流 | `black --check .` | exit 0，`136 files would be left unchanged`（135 + 1 新测试） |
| V7 | 引擎文件零改动 | `git diff --stat -- core/engine_v2.py core/engine_v3_vector.py core/factory.py` | 输出**空** |
| V8 | 无 `type: ignore` 扩张 | `Grep 'type: ignore'` | 仍为 **1 处**（`tests/test_execution_policy.py:294`） |
| V9 | 门禁 mypy 如实 | `adapter gate mypy-check` | verdict **fail**（93，存量，不得伪装 pass） |
| V10 | 测试文件数 | `Get-ChildItem tests -Filter 'test_*.py'` | **49**（48 + 1） |

---

## 5. 风险登记

| ID | 风险 | 等级 | 缓解 |
|----|------|------|------|
| R1 | `assert` 在 `-O` 下失效，B-2/3/4 防御被移除 | 低 | 本仓无 `-O` 运行；风险表如实登记 |
| R2 | A-2 返回形态由 tuple 改为单值，若有外部消费者会受影响 | 极低 | 全仓 0 调用（P5）；且原写法必然抛错，不存在可用消费者 |
| R3 | 补 3 项 smoke 可能暴露其他未测缺陷 | 中 | 若失败则如实登记，不得为通过而弱化断言 |
| R4 | A-4 行为退化未在本批修复 | 中 | 登记为 **P-010**，避免「删死代码 = 已修复」的误读 |
| R5 | C 类 `cast` 可能掩盖真实类型错误 | 低 | 优先收窄来源类型；`cast` 仅用于确实无法收窄处，并在 IMPL 逐项说明理由 |
| R6 | `data.py` 删除 48 行可能误删仍在用的分支 | 低 | 删除对象是**被覆盖的同名方法**，Python 语义上本就不可达；V4 全量回归 |
| R7 | 层 A 完成后门禁仍 fail，易被误读为「本批无效果」 | 中 | CHECKLIST 与台账显式声明「U-006 不关闭」 |

---

## 6. 回退点

| 场景 | 操作 |
|------|------|
| 整体回退 | `git revert <本批提交>`（单笔，含测试与文档） |
| 仅回退 A-4 删除 | `git checkout <前提交> -- core/data.py` |
| 仅回退某类修复 | 按文件粒度 `git checkout` |

---

## 7. 范围外（明确不做）

| 项 | 理由 |
|----|------|
| 引擎三件套 93 errors | 层 B 独立批次 |
| A-4 行为修复（默认值） | 需独立测试设计 → P-010 |
| 补 A-4 测试 | 会把当前错误行为固化为期望 |
| 删除 A-1/A-2/A-3 死函数 | 三者均为合理 API 面（尤其 `remove_monitor` 与 `add_monitor` 成对），修复优于删除 |
| 重构 `PluginRegistry.create` 签名 | 会波及 `create_optimizer` 等既有调用，超出最小面 |
| 降低 mypy 严格度 | 等于掩盖问题，违背 P-007 目标 |
| CI 加 mypy 硬门禁 | 层 B 未完成前加会立即红灯 |

---

## 8. 与 P-010 的关系

本批产生的派生待办 **P-010**（`data.py` 辅助数据缺失时无安全默认值）须在 PROGRESS 登记，内容：

- 现象：辅助数据文件缺失 → `_suspend_data` / `_industry_data` / `_st_data` / `_mktcap_data` 保持 `None`；getter 返回 `None` 且每次访问重试加载（重复 IO + 重复告警）
- 建议方向：合并 L184 的安全默认值逻辑进唯一实现，并为每类缺失场景补测试
- 档位：T1（改 `core/data.py` 行为）
- 优先级：P2（数据缺失时回测可能崩溃）

---

## 9. Step 4 Review（独立 pass）

- **执行时点**: 正文完稿后单独执行，未与正文同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 核对 D1-D9 与 Q1-Q6 的对应关系 + 逐条检查被拒代价 + 重读 `factor.py` / `global_contagion.py` 验证 D6 修法可执行性 + 保护路径核查

**发现 2 项（均 P3，均已修复）**：

| ID | 发现 | 处理 |
|----|------|------|
| **F-D1** | D6 对 `factor.py` 的修法表述含糊（「改初值为 `X: list[Any] = []` 并在赋值后重声明 `X_arr: np.ndarray`」）——若只加注解，L338 的 `X = np.column_stack(X)` 仍会被判为 assignment 错误，无法达成目标 | 已改为**变量改名分离两阶段**：收集阶段 `X_list`（L310/331/333），计算阶段 `X`（L338 起）。实测 `X.append` 仅 L331 一处，改名面可控 |
| **F-D2** | D6 把 `global_contagion.py:192` 描述为「拆分变量」，实际读码为 `metadata = {}`（L163）被 mypy 从后续 dict 赋值误推断值类型，**正确修法是补显式注解**而非拆变量 | 已改为「给 `metadata` 补 `dict[str, Any]` 注解（L163）」，并说明误推断成因 |

**D ↔ Q 对应性核对**：

| 决策 | 来源 | 覆盖验证 |
|------|------|----------|
| D1（A-4 删死代码不改行为） | Q1 | V4 / R4 / P-010 登记 |
| D2（A-1 修 RiskAction） | Q2 | V1 / V5（T-A1） |
| D3（A-2 修 evaluate→monitor） | Q2 | V1 / V5（T-A2） |
| D4（A-3 修参数传递） | Q2 | V1 / V5（T-A3） |
| D5（B 类最小防御） | Q3 | V1 / R1（-O 限制） |
| D6（C 类 16 项） | Q5 | V1 / V8 |
| D7（3 项 smoke） | Q4 | V4 / V5 / V10 |
| D8（冻结资产 1 处 cast） | Q6 | V1 |
| D9（范围边界） | — | V2 / V3 / V7 / V9 |

**保护路径核查**：

| 路径 | 约束 | 验证 |
|------|------|------|
| `engine_v2.py` / `engine_v3_vector.py` / `factory.py` | 零改动 | V7（diff 空） |
| `mypy` 严格度配置（`pyproject.toml [tool.mypy]`） | 不改 | 隐含于 V2（若改配置读数不可比） |
| `black` 基线 | 保持 exit 0 | V6 |
| `type: ignore` | 不扩张（仍 1 处） | V8 |

**被拒代价完整性**：D1 给 3 个方案对比；D4 给出「改 lambda 形参名」的被拒理由与代价；D5 给出「仅改注解」的被拒理由；D6 明确禁止 `# type: ignore`。

**结论**: 0 项阻断（P1/P2 = 0）；2 项 P3 已回写；D1-D9 与 Q1-Q6 全覆盖、V1-V10 无悬空，可进入 Step 5 实施规划。
