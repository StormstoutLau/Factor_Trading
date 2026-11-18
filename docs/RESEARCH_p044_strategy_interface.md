# RESEARCH：P-044 策略接口抽象（Strategy Protocol + BacktestAdapter）

> **批次**: P-044 · **Step 1 调研** · 日期 2026-11-18
> **判档**: **T1**（Layer-1：新建 `core/strategy.py` + `core/registry.py` 扩展 + `tests/`；新契约）
> **上游**: [UPGRADE_MASTER_PLAN.md §2.2/§5](UPGRADE_MASTER_PLAN.md) P-044（前置 P-042；P-043 已关闭）；[PROGRESS §3.49.10](PROGRESS.md) P-043 批次关闭
> **代码证据时点**: HEAD `96384f6`（P-043 关闭；工作区净）
> **基座**: DeepSeek-V4.1-Flash（Step 2 Review 同源 → 登记 U-P044-5；终审须异构）

---

## 1. 触发与题干

- **触发**: 用户「进入 P-044」；总纲 §5 P-044：「`core/strategy.py` Protocol + BacktestAdapter」，验收「既有策略迁移零行为变更；状态可序列化重放」。
- **题干（本批做什么）**:
  1. **策略契约**：`core/strategy.py` 新增 `StrategyMeta` / `StrategyState` / `MarketView` / `TargetWeights` / `Strategy`（`@runtime_checkable` Protocol，`generate_signals(view, state) -> TargetWeights` 纯函数）；
  2. **回测适配器**：`BacktestAdapter` 把 `Strategy` 驱动为逐日目标权重矩阵，供既有 V2 执行链消费（复用 optimizer → `build_target_positions` → `ExecutionSimulator`）；
  3. **既有策略迁移（等价）**：默认因子信号路径 + 三方向 `StrategyConfig`（long / short / both）以契约对象等价表达，**零行为变更**（等价由测试逐值锁定）；
  4. **可追溯**：`core/registry.py` 增 `strategy` 类别（§6 门禁「每策略必有 id+版本+参数 schema+代码 hash」）；
  5. **状态可序列化重放**：`StrategyState` JSON 往返 + 重放输出一致。
- **明确不做**:
  - 不建 `strategies/` 模板库（网格/趋势/动量 → **P-051**）；
  - 不建 `live/` / `LiveAdapter`（→ **P-053**）；
  - **不重构** `agents/multi_strategy_engine.StrategyEngine` 内部（见 U-P044-3）；
  - 不做择时/止损（P-045）、风险 overlay（P-048）、优化器扩展（P-046）；
  - 不给 `TargetWeights` 引入负权重/空头账目（→ P-050）。
- **职责外（不回答）**: 实盘事件驱动（P-053）；策略晋级/退役生命周期（P-051）；多策略资金分配（`agents/strategy_allocator.py` 既有，本批不动）。
- **能力边界（回答不了）**: 本批只证明「契约 + 回测驱动 + 等价迁移」；不证明策略库可交易性（P-051 的样本外验证）。

---

## 2. 代码事实基线（E3 @`96384f6`）

### 2.1 现有策略面盘点

| 对象 | 位置 | 现状 | 与本批关系 |
|------|------|------|-----------|
| **默认因子信号路径** | [engine_v2.py:374-382](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L374-L382)（run_started 发射后）/ `_execute_rebalance` L1009-1063 | `_composite_signal: pd.DataFrame` → `optimizer.optimize(daily_signal, returns_data)` → `build_target_positions` → 订单 | **迁移对象 A**（等价包装） |
| **三方向策略** | [multi_strategy_engine.py:49-64](file:///f:/Coding/Factor_Trading_v3.0/agents/multi_strategy_engine.py#L49-L64) `StrategyConfig`（`direction: long/short/both`、`select_top`、`long_weight`） | `StrategyEngine`（L67）独立回测引擎；`_execute_directional_rebalance` L256 / `_execute_neutral_rebalance` L282（P-031 D2：空头腿禁用，多头腿 × `long_weight`） | **迁移对象 B**（等价映射，不改其内部） |
| **信号→订单翻译** | [execution_policy.py:410-466](file:///f:/Coding/Factor_Trading_v3.0/core/execution_policy.py#L410-L466) `SignalTranslator.from_weights` | 目标权重 → `OrderIntent`（target≠current 才产生） | 适配器下游，本批不改 |
| **插件注册表** | [registry.py:174-220](file:///f:/Coding/Factor_Trading_v3.0/core/registry.py#L174-L220) | 5 类别：optimizer / trigger / filter / guard / agent；**无 strategy** | **扩展对象** |
| **执行算法** | `order_strategy/strategies.py`（TWAP/VWAP/Iceberg） | 订单拆分执行 | **排除**（非 alpha 策略，P-053 邻域） |
| **绩效评估** | `strategy_evaluation/`（stats/evaluator） | 评估指标 | 排除（只读消费方） |
| **core 导出策略** | [core/__init__.py](file:///f:/Coding/Factor_Trading_v3.0/core/__init__.py) | 空导出（ADR-016），仅 `__api_version__` | 新模块沿用显式导入 |

### 2.2 契约缺失证据

- `core/strategy.py` **不存在**（Glob 0）；
- `strategies/` 目录 **不存在**（Glob 0）；
- 全仓代码 `BacktestAdapter` / `MarketView` / `StrategyState` / `StrategyMeta` / `TargetWeights` / `class Strategy(Protocol)` **0 命中**（仅 `UPGRADE_MASTER_PLAN.md` 文档命中）；
- `core/registry.py` 全局注册中心 5 个（L176-180），无 strategy。

### 2.3 行为锁（迁移零变更的判据来源）

| 锁 | 位置 | 作用 |
|----|------|------|
| P-031 账目/时序 | `tests/test_p031_strategy_engine_accounting.py`（8 def） | 三方向路径、空头腿禁用、次日订单簿语义 |
| P-033 订单价格校验 | `tests/test_p033_order_price_validation.py`（8 def） | 订单价格合法性 |
| golden 13 | `tests/golden/` | V2/V3 数值基线 |
| P-014 停牌账目 | `tests/test_p014_suspension_accounting.py` | 双路径净值一致 |

---

## 3. E1 取证（可重放）

| 读数 | 命令 / 方法 | 结果 |
|------|-------------|------|
| A `core/strategy.py` | `Test-Path core/strategy.py` | **False** |
| B `strategies/` | `Test-Path strategies` | **False** |
| C `BacktestAdapter` 代码命中 | 全仓 `*.py` grep | **0**（仅 master plan 文档） |
| D 契约类型代码命中 | `MarketView\|StrategyState\|StrategyMeta\|TargetWeights` | **0** |
| E registry 类别 | Read `core/registry.py:176-220` | optimizer / trigger / filter / guard / agent = **5** |
| F 引擎信号消费点 | Read `engine_v2.py:1009-1063` | `optimizer.optimize` → `build_target_positions` 无策略抽象 |
| G 三方向定义 | Read `multi_strategy_engine.py:626-663` | long(`select_top=True`) / short(`False`) / both(`long_weight=0.5`) |
| H 基线门禁 | P-043 关闭读数 | pytest **803** / golden **13·790** / black **130·197** / mypy **104** / AST **22** / `tests/*.py` **92** / uv **0** |
| I 信号注入现状 | Read `engine_v2.run()` L360-368 | 注入 pipeline/combiner 后需手工设 `_composite_signal`（**私有属性**，无公共 setter） |

> 本批 Step 1 为只读取证，未运行 pytest/git 写入；H 读数沿用 P-043 关闭基线，Step 9 必须本批复跑。

---

## 4. 缺口清单

| ID | 缺口 | 级别 | 证据 |
|----|------|------|------|
| **G1** | 无统一策略契约（alpha 逻辑只能以 DataFrame 或 config 表达） | P2 | A/C/D |
| **G2** | 无状态模型与序列化（策略无法独立复算/重放） | P2 | D |
| **G3** | 无回测适配器（策略无法脱离引擎内部类被驱动） | P2 | C/F |
| **G4** | registry 无 strategy 类别，§6「策略可追溯」门禁无载体 | P3 | E |
| **G5** | 无代码 hash / 版本追溯（id+版本+参数 schema+hash 四要素缺三） | P3 | E |
| **G6** | 三方向策略以 `StrategyConfig` 硬编码在 `agents/`，与 core 信号路径双实现无等价性证明 | P3 | G |
| **G7** | 无公共信号注入入口（`_composite_signal` 私有，适配器只能写私有属性） | P3 | I |

---

## 5. 方案矩阵

| 方案 | 内容 | 判定 |
|------|------|------|
| **M-A（推荐）** | **契约 + 纯内存适配器 + 等价迁移**：`core/strategy.py` 四类型 + Protocol；`BacktestAdapter` 产逐日权重矩阵；三方向与因子信号路径以 wrapper 等价表达并由测试逐值锁定；registry +strategy 类别 | ✅ 最小、零行为（生产执行链零改动）、可独立验证、为 P-045/P-051 提供契约 |
| M-B | 把 `BacktestEngineV2` 重构为 Strategy 驱动（替换 `_composite_signal` 路径） | ❌ 触碰交易/净值主链路，T1 风险爆炸；等价性无法在单批内证明 |
| M-C | 只加 Protocol 不做迁移 | ❌ 不满足验收「既有策略迁移零行为变更」 |
| M-D | 直接建 `strategies/` 模板库 | ❌ 越界 P-051（且无 P-045/P-047 原语，模板无意义） |
| M-E | 引入 vnpy `CtaTemplate` 依赖 | ❌ 新依赖 + 事件模型与现有矩阵回测不兼容 |

**裁决**: **M-A**。理由：唯一同时满足「零行为 / 关闭缺口 / 不越界后续批次」；`StrategyEngine` 内部重构登记 O-P044-2。

---

## 6. 批次切分（供 DESIGN 采用）

| 批次 | 内容 | 行为 | 验收 |
|------|------|------|------|
| **B1 契约与注册** | `core/strategy.py`：`StrategyMeta` / `StrategyState` / `MarketView` / `TargetWeights` / `Strategy` Protocol / `code_hash` 工具；`core/registry.py` +strategy 类别 | 零行为（新符号） | Protocol 方法 1 个 + 4 类型；registry 注册/查询/覆写 |
| **B2 回测适配器** | `BacktestAdapter`：`signals_frame(strategy, market)` + `run_engine(engine, strategy)`；状态逐日演进 | 零行为（默认路径不变） | 输出与 `_composite_signal` 逐值一致 |
| **B3 等价迁移** | `FactorSignalStrategy`（默认路径）+ `DirectionalStrategy`（long/short/both，映射 P-031 D2） | 零行为（wrapper） | 与 `StrategyConfig` 路径目标权重逐值一致；状态往返 |
| **B4 测试与文档** | `tests/test_p044_strategy_interface.py`（V1-V8）+ 四文档 + 台账 | 新增只读面 | pytest **803 → 811**；golden 13 零重录 |

> B2 依赖 B1；B3 依赖 B2；B4 与 B3 同批提交。四批均不触碰 `agents/` 生产代码。
> **（S8 注）**本节为 Step 1 提案；DESIGN/IMPL 落地时按**文件对齐**重排批次（适配器与两策略类同置 `core/strategy.py`）：**B1=core/strategy.py 全量（契约+适配器+迁移）/ B2=registry / B3=engine_v2 / B4=测试**，依赖与回退以 [IMPL §2/§8](IMPL_p044_strategy_interface.md) 为准（F-S8-P044-2）。

---

## 7. 精确语义（实施规格输入）

| # | 语义 |
|---|------|
| S1 | `StrategyMeta`（frozen dataclass）：`strategy_id: str` / `version: str` / `param_schema: dict[str, Any]` / `code_hash: str` |
| S2 | `StrategyState`（frozen dataclass）：`as_of: str`（`YYYY-MM-DD`）/ `positions: dict[str, float]` / `extras: dict[str, Any]`；提供 `to_dict()` / `from_dict()`（仅 JSON 安全类型） |
| S3 | `MarketView`（frozen dataclass）：`date: pd.Timestamp` / `signal: pd.Series`（当日因子/原始信号）/ `tradable: pd.Series`（bool）/ `prices: pd.Series` / `returns: Optional[pd.DataFrame]` |
| S4 | `TargetWeights = pd.Series`（类型别名；index=标的，value=非负权重；负权重属 P-050） |
| S5 | `Strategy`（`@runtime_checkable` Protocol）：`meta: StrategyMeta` + `generate_signals(view: MarketView, state: StrategyState) -> TargetWeights`；**纯函数**（无 I/O、无全局写） |
| S6 | `code_hash(source: str) -> str`：`sha256(source.encode("utf-8")).hexdigest()[:12]`；参数值不入 hash（在 `param_schema`） |
| S7 | `BacktestAdapter.signals_frame(strategy, market_stream) -> pd.DataFrame`：逐日 `generate_signals` → DataFrame（index=dates, columns=codes）；空日返回空 Series |
| S8 | 三方向映射（逐字对齐 P-031 D2）：`long` = `select_top=True`；`short` = `select_top=False`；`both` = 多头腿 `select_top=True` 且权重 × `long_weight`（空头腿禁用，`neutral_short_leg` 计量在 `StrategyEngine` 侧不变） |
| S9 | registry：`get_strategy_registry()` + `register_strategy(name, factory, ...)`；重复注册 `logger.warning` + 覆写（与既有 5 类别同语义） |
| S10 | 默认路径不变：不设 `BacktestConfig` 新字段；引擎 `_composite_signal` 逻辑零改动（适配器只读引擎、写公共入口或在测试中显式赋值） |

---

## 8. 行为变更与不变式

**默认路径（不用新契约）**：交易/净值/产物逐值不变；golden 13 零重录。
**使用新契约**：策略以纯函数被驱动，适配器输出中间矩阵，最终仍由既有执行链下单。

| ID | 不变式 |
|----|--------|
| I1 | golden **13 零重录**；`agents/` 生产文件零 diff |
| I2 | `FactorSignalStrategy` 输出与 `_composite_signal` **逐值相等** |
| I3 | `DirectionalStrategy`（long/short/both）输出与 `StrategyConfig` 路径**逐日目标权重逐值相等** |
| I4 | `StrategyState.from_dict(to_dict(s)) == s`；同状态重放 `generate_signals` 输出一致 |
| I5 | `core/strategy.py` 无 I/O（AST 扫描 `open` / `requests` / 全局写 = 0） |
| I6 | registry 注册/查询/覆写（覆写打 warning）；类别名 `strategy` |
| I7 | 零新增依赖 |
| I8 | `tests/*.py` **92 → 93**；pytest **803 → 811**；mypy **104 → 105**（新模块）；black **130·197 → 132·199**（**（S8 订正）**初稿 131·198 漏算测试文件，F-S5-P044-1，两口径均含 `tests/`） |
| I9 | AST `except Exception` 门禁 **22 不变**（新文件无该模式）；`uv lock --check` exit 0 |

---

## 9. 未决项登记（四元块）

> **补充调研**: U-P044-1 / U-P044-2 / U-P044-4 的社区与官方文档锚点见 **§14**（2026-11-18 联网检索）；Step 3 以 **§14.4** 推荐值为初值，仍须 DESIGN 显式裁决。

- **U-P044-1 协议放置**
  - 判据：`Strategy` 放新建 `core/strategy.py` 还是并入 `core/interfaces.py`
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**`core/strategy.py`**（总纲指定；契约+类型+hash 工具同域；interfaces.py 已 549 行）
  - 证据等级：E3（架构原则）

- **U-P044-2 适配器产物形态与注入入口**
  - 判据：`signals_frame` 返回 DataFrame vs 逐日 Series 回调；是否给 `BacktestEngineV2` 加公共 `set_signal(df)`
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**DataFrame + 给引擎加 1 个公共 setter**（避免适配器写私有 `_composite_signal`；setter 无行为变更）
  - 证据等级：E3（G7）

- **U-P044-3 `StrategyEngine` 内部重构**
  - 判据：是否把 `agents/multi_strategy_engine.StrategyEngine` 改为调用新契约
  - 触发条件：P-051（策略模板库）或出现第三处信号实现
  - 当前倾向：**本批不动**（等价 wrapper + 锁定测试；内部重构风险 > 收益）
  - 证据等级：E3（G6）

- **U-P044-4 `code_hash` 覆盖范围**
  - 判据：模块源码 vs 类源码 vs 文件字节
  - 触发条件：Step 3 DESIGN
  - 当前倾向：**类源码 `inspect.getsource(cls)` 归一化后 sha256 前 12 hex**（函数级改动即变，参数不入 hash）
  - 证据等级：E3（§6 门禁）

- **U-P044-5 异构终审**
  - 判据：Step 2/4/6/8/10 复审基座与作者不同
  - 触发条件：进入 Step 10
  - 当前倾向：作者 DeepSeek-V4.1-Flash；终审由 GLM-5.3-Flash 承接
  - 证据等级：E1（会话基座）

---

## 10. 可重放命令

```powershell
$py = 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe'
# E3：契约缺失（只读）
& $py -c "import pathlib; print('strategy.py:', pathlib.Path('core/strategy.py').exists()); print('strategies/:', pathlib.Path('strategies').exists())"
# E1 基线（Step 9 必跑）
$env:MPLBACKEND='Agg'; & $py -m pytest tests -q -p no:cacheprovider
& $py -m pytest tests -k golden -q -p no:cacheprovider
& $py -m black --check core tests
& $py -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
uv lock --check
```

> Step 1 未执行上述命令（只读取证）；基线沿用 P-043 关闭读数，Step 9 回填红/绿。

---

## 11. Step 1 自查（RULE-4）

| # | 自查项 | 结论 |
|---|--------|------|
| 1 | 题干是否收窄 | ✅ `strategies/`/`live/`/择时/风险/优化器/空头全部排除 |
| 2 | 事实与推测分离 | ✅ G1-G7 均有 E3 行号；迁移对象以既有测试为行为锁 |
| 3 | 是否重做 P-042/P-043 | ✅ 不复用 `MarketEvent`/`EventLog`；不触碰数据/事件层 |
| 4 | 是否以「跑通」代替正确性 | ✅ 验收含逐值等价 + 状态往返 + 纯函数扫描 |
| 5 | 方案矩阵是否穷举 | ✅ M-A~M-E；四条拒绝理由 |
| 6 | 是否触碰交易/净值语义 | ✅ 零变更（I1/I8） |
| 7 | 是否新增外部依赖 | ✅ 零新增（`hashlib`/`inspect` 均 stdlib） |

---

## 12. 判档

**T1**——新建 `core/strategy.py` 契约（判档规则 2 强制）且改动面含 `core/registry.py` 与 `tests/`。

---

## 13. Step 2 Review（同基座独立视角，2026-11-18）

> **基座披露（RULE-4）**: 复审 DeepSeek-V4.1-Flash = 作者**同源**；RULE-5 不成立 → U-P044-5 跟踪；终审须异构。

### 13.1 机械复核

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 契约缺失 | `core/strategy.py` / `strategies/` 均不存在；代码 0 命中 | ✅ G1-G3 成立 |
| 2 | registry 类别 | 5 类别（L176-220），无 strategy | ✅ G4/G5 成立 |
| 3 | 迁移对象行为锁 | p031(8 def) / p033(8 def) / golden 13 / p014 | ✅ 等价测试有判据来源 |
| 4 | 三方向语义 | `_create_strategy_configs` L626-663 与 P-031 D2 对齐 | ✅ S8 逐字 |
| 5 | 私有注入入口 | `_composite_signal` 无公共 setter | ✅ G7 成立（U-P044-2） |
| 6 | 计数链 | 803+8=811；92+1=93；104+1=105；black 130·197→**132·199**（**（S8 订正）**原记 131·198，F-S5-P044-1）；AST 22 不变 | ✅ 自洽 |

### 13.2 发现与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S2-P044-1 | P2 | 「迁移」若按字面改造 `StrategyEngine` 内部，会触碰 P-031/P-033 锁定的账目/时序语义，且与「零行为」冲突 | §1/§5 显式裁决：**迁移 = 等价 wrapper + 逐值锁定**；`StrategyEngine` 内部重构登记 **U-P044-3 / O-P044-2**，本批 `agents/` 零 diff |
| F-S2-P044-2 | P3 | 适配器写引擎私有 `_composite_signal` 属越界耦合 | U-P044-2：倾向给引擎加公共 `set_signal(df)`（无行为变更），DESIGN 裁决 |
| F-S2-P044-3 | P3 | `TargetWeights` 用 `pd.Series` 别名不承载「非负」约束 | S4 显式声明边界（负权重 → P-050）；V 系列加非负断言 |

### 13.3 结论

**Step 2 Review pass（1 P2 + 2 P3 当轮处置）**——G1-G7 均有 E3 证据、方案矩阵穷举、迁移口径显式收敛；**准予进入 Step 3 DESIGN**。
**RULE-5**: 同基座 → U-P044-5 pending（终审须 GLM-5.3-Flash）。

---

## 14. 补充调研：三个决策点的社区/文档锚点（2026-11-18）

> **证据等级**: **E1-EXT**——外部官方文档与开源实现，URL 可复核；只证明「社区主流做法」，不证明本项目正确性。本地正确性仍由 Step 9 测试与 Step 10 审计承担。
> **检索方式**: WebSearch（2026-11-18），对象限定 qlib / vnpy / backtrader / freqtrade / vectorbt / Python 官方文档 / PEP 544 / joblib / MLflow / hexagonal architecture。

### 14.1 U-P044-1 协议放置

| 锚点 | 事实 | 对本项目的含义 |
|------|------|----------------|
| Qlib | 策略契约 `qlib.strategy.base.BaseStrategy` 位于**专用策略模块**，`WeightStrategyBase` 同域；不在通用 interfaces 聚合模块 | 策略契约归策略域 |
| VeighNa（vnpy） | `CtaTemplate` 位于 `vnpy_ctastrategy/template.py`（模板专用模块），用户策略在 `strategies/` 目录继承 | 模板/契约与业务策略分层，契约在域模块 |
| Backtrader | `Strategy` 定义在 `backtrader/strategy.py`（框架核心专用模块），非集中式 interfaces | 同上 |
| Hexagonal / Ports & Adapters | 「Define ports as interfaces in your **domain layer** before writing any adapter code」；端口由领域拥有，适配器在外层 | 契约应与其领域类型同域，不塞进跨层聚合模块 |
| 本项目先例 | P-042 D5：`IStreamingFeed` 与 `InMemoryStreamingFeed` 同置 `core/streaming.py`；`IDataManager` 等跨层契约在 `core/interfaces.py` | 两种先例并存；策略契约含 4 个专属类型 + hash 工具 → 同域更一致 |

**推荐**: **`core/strategy.py`**（与三家外部实现一致；`interfaces.py` 保持「跨层通用契约」定位，不再膨胀）。
**被拒**: `core/interfaces.py`——需反向依赖策略专属类型且该文件已 549 行；新建 `core/strategy_contract.py` + 实现分家——无先例，计数 +1 无收益。

### 14.2 U-P044-2 适配器形态与 `set_signal`

**A. 适配器产物形态**

| 锚点 | 事实 | 含义 |
|------|------|------|
| Qlib `WeightStrategyBase` | 策略只实现 `generate_target_weight_position`（目标权重）；框架负责「权重 → 目标数量 → 订单列表」 | **策略只产权重，不产订单**——与 `BacktestAdapter` 分层同构 |
| vectorbt | `Portfolio.from_orders(size_type="targetpercent")` / `from_weights`：目标权重是主流表达 | 权重矩阵是一等输入 |
| Freqtrade | `populate_entry_trend(dataframe) -> DataFrame` 批量返回整表，非逐日回调 | 向量化框架偏好批量 |
| vnpy / Backtrader | `on_bar` / `next` 逐 bar 回调，策略内直接下单 | 事件驱动实盘形态（对应 P-053 `LiveAdapter`） |
| 本项目引擎 | `_composite_signal` 为 DataFrame，消费端按日 `.loc[date]` 切片；`run()` 前就绪 | **批量 DataFrame 与现有引擎同形**，逐日回调需改主循环 |

**裁决锚点**: 契约方法保持逐日纯函数（`generate_signals(view, state)`，回测/实盘共用）；`BacktestAdapter` 负责**批量物化**为 DataFrame（回测侧），LiveAdapter（P-053）负责逐事件驱动。二者共用同一 `Strategy`。

**B. `set_signal` 是否新增**

| 锚点 | 事实 | 判断 |
|------|------|------|
| Setter 注入风险 | 「Setter based injection only works cleanly if the class guarantees some sensible default or validates that required dependencies are in place before use」；否则对象可能处于半初始化状态 | 引擎已有 `setup() → run()` 两阶段，且 `run()` 对信号未就绪**已显式抛 RuntimeError** → 不是新增半初始化，而是补全既有生命周期的**显式入口** |
| DI 反模式目录 | 关注「Constrained Construction / Service Locator / Bastard Injection」；显式 setter + 前置校验不在反模式之列 | 需带校验（index/columns 对齐） |
| 构造注入替代 | 信号依赖 `setup()` 后的数据对齐（`dm.trade_dates/stock_codes`），构造期无法可靠计算 | 构造注入语义更差 |
| 私有属性现状 | 适配器写 `engine._composite_signal` 属跨模块私有耦合（G7） | 必须消除 |

**推荐**: 新增 `BacktestEngineV2.set_signal(df: pd.DataFrame) -> None`——校验 `index/columns` 与 `dm` 对齐后赋值；默认路径不调用 → 零行为。**不**把 `Strategy` 类型引入引擎签名（避免引擎主链路绑定策略概念，P-051 再评估）。
**被拒**: 适配器直接写 `_composite_signal`（私有耦合）；`run(strategy=...)`（引擎签名扩张，且需在 core 引擎内引入策略编排）。

### 14.3 U-P044-4 `code_hash` 范围

| 锚点 | 事实 | 含义 |
|------|------|------|
| MLflow / DVC 版本追踪 | 主流做法用 **git commit 短哈希** 绑定代码版本；模型注册表字段「Commit hash: Ties the model to the exact training code」 | 若有稳定提交，commit hash 最可靠；但策略代码可能未提交/本地改动 → 需源码级 hash |
| `inspect.getsource` 官方文档 | 源不可得抛 **`OSError`**；内置对象抛 `TypeError`；CPython 对 `__main__` 且无 `__file__` 时 `OSError('source code not available')` | 必须有**显式 fallback**，不能假设总能取到源码 |
| 社区源码指纹实现 | `getsources.getsourcehash`：`inspect.getsource` → 去缩进；fastflowtransform：`getsource` → dedent → 文件切片 → qualname+bytecode 兜底 | 与「dedent + 回退链」一致 |
| `joblib.hash` | 对函数/类做内容哈希（含源码与状态，带兜底） | 内容哈希可行，但本项目只需代码标识，不必引入依赖 |
| PEP 544 / typing | 与 hash 无关；但 `runtime_checkable` 的 `isinstance` **只检查成员存在、不检查签名** | 契约测试需辅以 `inspect.signature`（P-043 V1 已用同法） |

**推荐**（逐字）:
1. `code_hash(cls)`：`inspect.getsource(cls)` → `textwrap.dedent` → 换行归一（`\r\n|\r → \n`）→ `strip()` → `sha256` → **前 12 hex**；
2. 回退链（返回带前缀，**不静默**）：`getsource(cls)` → `getsource(cls.generate_signals)` → `"q:" + sha256(qualname + version + canonical_json(param_schema))[:12]`；
3. **类级**粒度（同文件多策略可区分）；参数值不入 hash（参数属 `param_schema`/config，不属代码版本）；
4. 换行归一必须做——本仓 Windows（CRLF）与 CI Linux（LF）并存，否则跨平台 hash 漂移。

**被拒**: 仅用 git commit（未提交策略无法区分）；模块级源码（同模块多策略同哈希）；仅 bytecode（`co_code` 跨 Python 版本漂移，3.10/3.12 CI 三版本会不一致）。

### 14.4 决策对照汇总（供 Step 3 采用）

| 未决 | 推荐 | 主锚点 | 主要代价 |
|------|------|--------|----------|
| U-P044-1 | `core/strategy.py` | qlib / vnpy / backtrader 三家同域 + hexagonal 端口归领域 | `interfaces.py` 与策略域二选一，需在文档声明边界 |
| U-P044-2 | `signals_frame` 批量 DataFrame + `engine.set_signal(df)` | qlib `WeightStrategyBase` 权重分层 + vectorbt `from_weights` + 引擎现有 DataFrame 形态 | 引擎 +1 公共方法（约 6 行）；需 V 系列覆盖对齐校验与非法输入 |
| U-P044-4 | 类源码 dedent/换行归一 + sha256 12 hex + 显式 fallback 前缀 | CPython `getsource` OSError 事实 + getsources/fastflowtransform 回退链 + MLflow commit-hash 语义 | fallback 场景需单测（动态类/交互式定义） |

### 14.5 外部锚点与本地证据的边界

- 本节为 **E1-EXT**：只回答「社区怎么做、官方文档承诺什么」，**不**回答「本项目哪条更正确」；
- 本地判据仍为：§8 I1-I9 不变式、§12 判档、Step 9 红绿、Step 10 E1-E5；
- 外部实现均非 A 股矩阵回测形态（qlib 最接近），**不作为性能或语义等价证据**。
