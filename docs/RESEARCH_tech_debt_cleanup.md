# 技术债务清理调研报告

> **文档编号**: RESEARCH_tech_debt_cleanup
> **阶段**: Phase 0 - 调研
> **日期**: 2026-08-15
> **状态**: 已归档（Phase 0 调研完成；P0-3 文档修正在 2026-10-23 执行）
> **归档日期**: 2026-10-23
> **上游文档**: [ARCHITECTURE.md](ARCHITECTURE.md) 第八章、[SPEC_STANDARD.md](SPEC_STANDARD.md)

---

## 1. 背景与目标

### 1.1 背景

Factor Trading v3.0 经历了 V1 → V2 → V3 的快速迭代，产生了多版本并行存在的局面：数据层、配置层、引擎层、过滤器层均存在双实现。ARCHITECTURE.md 第八章已识别初始技术债务，但尚未系统化清理。

### 1.2 目标

1. 建立**完整、可验证**的技术债务清单（含引用计数测量）
2. 调研外部最佳实践（Python 弃用周期、量化框架数据层抽象）
3. 对比清理方案，评估风险
4. 产出优先级排序的清理路线图，供 Phase 1（设计）使用

### 1.3 调研方法

- **引用计数测量**: 对每个双实现模块执行 grep 分析（import 语句 + 显式调用），区分生产代码引用与测试引用
- **外部调研**: Python PEP 594 弃用流程、APIScanner 学术研究、Qlib Provider 模式
- **文档-代码一致性核查**: 对照 ARCHITECTURE.md 的描述与实际实现，识别文档幻觉
- **风险识别**: 对每项清理动作预判失败模式并制定缓解措施

---

## 2. 技术债务清单

### TD-1: 数据层双实现（DataManager V1 vs DataLoaderV3）

**现状**:

- `core/data.py` — DataManager (V1)，通用数据管理器
- `core/data_v3.py` — DataLoaderV3 (V3)，面向 Engine V3 向量化操作的数据加载器

**引用计数测量**（grep 分析，2026-08-15）:

| 模块 | 引用数 | 引用位置性质 |
|------|--------|--------------|
| DataManager (V1) | **38 处（22 个文件）= 生产 12 处 + 测试 26 处** | 生产：`engine_v2.py`、`engine.py`、`factory.py`、`factor.py`、`filter/universe.py`（本身是孤儿旧过滤器）、`examples/`×4、`agents/`×3；测试：10 个测试文件 26 处 |
| DataLoaderV3 | **2 处生产引用** | `engine_v3_vector.py`（V3 向量化引擎）、`tools/benchmark.py`（基准测试）；`core/__init__.py` 中仅注释提及 |

**关键发现**（源码级溯源补充）: DataManager 是**承重墙组件** —— engine_v2（当前主力引擎）和 factory（组件工厂）深度依赖它。DataLoaderV3 的定位需精化：其 docstring 明确声明"**向后兼容 DataManager 接口**"（data_v3.py:27），即它是按 V1 替代品设计的；ARCHITECTURE.md 第 293/302 行也写明计划"迁移到 V3，废弃 V1"。**但该迁移从未执行** —— 生产消费方仅 engine_v3_vector 与 benchmark。

**债务性质**: 不是"旧版未删"，而是**已规划未执行的迁移**。接口兼容设计已就位（V3 可替代 V1），但 12 处生产引用仍全部压在 V1 上。数据层统一是架构演进课题，本次清理仅记录方向。

### TD-2: 配置层双实现（dataclass V1 vs Pydantic V2）

**现状**:

- `core/config.py` — V1 dataclass 配置，**133 处引用（53 个文件）**，全项目事实标准
- `core/config_v2.py` — V2 Pydantic 配置，**9 处引用，全部位于 `tests/test_config_v2.py`**，生产代码零使用（另有 ARCHITECTURE.md 等文档提及）

**关键发现**: config_v2.py 是**孤儿模块** —— 开发投入显著（Pydantic 校验、类型安全），但从未接入生产路径。133 处 V1 引用意味着迁移成本极高（几乎每个模块都 import BacktestConfig）。

**源码级溯源新发现（H-3）**: ARCHITECTURE.md:85 将 Config V2 标记为 "**✅ 活跃**"，与事实相反（生产零引用），且与该文档自身的债务表（第 303 行"Engine V2 使用 V1"）**内部矛盾**。这是第三处文档幻觉。

**债务性质**: 沉没成本 + 未来迁移成本的双重负担。保留它会误导新读者以为 V2 是活跃路径 —— ARCHITECTURE.md:85 的错误标注正在主动制造这种误导。

**修正状态（2026-10-23）**: ARCHITECTURE.md:85 已改为 "⚠️ 冻结（零生产引用）"，并同步 §6.1 对比表 :223 的 "✅ 推荐" → "⚠️ 冻结"。

### TD-3: 引擎层 V1 残留（engine.py 已弃用未移除）

**现状**:

- `core/engine.py` — V1 引擎，已标记弃用但未移除
- `core/engine_v2.py` — V2 引擎，当前主力
- `core/engine_v3_vector.py` — V3 向量化引擎，开发中

**引用计数测量**: engine.py（V1）共 **10 个文件引用**，其中**关键一处为 CLI 入口点 `cli.py:36`** —— 命令行默认调用的竟是已弃用的 V1 引擎。其余为 `core/__init__.py`（re-export）、`examples/` 5 个脚本、`tests/` 3 个测试。

**迁移路径已存在**: `core/factory.py` 已实现 `create_default_engine()`，返回 `BacktestEngineV2`，可直接替换 cli.py 中的直接 V1 调用：

```python
def create_default_engine(config: BacktestConfig) -> 'BacktestEngineV2':
    """创建默认配置的引擎"""
    from core.engine_v2 import BacktestEngineV2
    factory = ComponentFactory(config)
    kwargs = factory.create_engine_kwargs()
    engine = BacktestEngineV2(config, **kwargs)
    return engine
```

**债务性质**: **最高优先级的实际风险** —— 用户通过 CLI 跑的回测可能一直在用弃用引擎，结果可信度存疑。

**源码级溯源补充**: engine.py 的弃用标记是**完整的双保险** —— module docstring 第 3 行 "⚠️ DEPRECATED" + 类 docstring `.. deprecated::` + 构造函数内运行时 `warnings.warn(DeprecationWarning)`（engine.py:54-59）。即 PEP 594 的 Stage 1（Deprecate）**已在源码层面完成**，剩余工作仅为 Stage 2（cli.py 替换）与 Stage 3（移除），P1 工作量比预评估更小。

### TD-4: Factor_DB 实现与文档不符（文档幻觉 H-1）

**现状**:

- `factor_library/database.py` — 因子库存储实现
- ARCHITECTURE.md 声称其 "DuckDB-based"

**实际实现**: **JSON 元数据 + parquet 文件**存储（parquet 不可用时降级 csv），与 DuckDB 无关。全仓代码无 `import duckdb` 引用（仅 `cli.py:224` 的依赖自检字符串与规划文档提及 DuckDB）。

**源码级溯源补充**: ARCHITECTURE.md 存在**内部自相矛盾** —— 组件表（第 65、132 行）将 Factor_DB 表述为 "DuckDB 因子存储"，而同文档缺口表（第 291 行）承认 "Factor_DB DuckDB 集成 | 骨架已建，需完成写入/查询 CLI"，第 132 行状态列也标了 "⚠️ 骨架"。即文档一半知道真相、一半在虚构，组件表的表述需与缺口表对齐。

**债务性质**: 文档幻觉 —— 误导读者对存储层可靠性、并发能力、查询能力的判断。存储格式本身（JSON + parquet）无 pickle 式反序列化安全风险，主要差距在于：文档承诺的 DuckDB 查询/并发能力实际不存在，多因子联合检索需全量加载后内存过滤。

**修正状态（2026-10-23）**: ARCHITECTURE.md:65 改为 "Parquet"、:132 改为 "JSON 元数据 + Parquet 文件存储（DuckDB 为规划方向）"、:291 改为 "Factor_DB 查询层（DuckDB 规划）"、:321 注明 duckdb 依赖当前未使用。

### TD-5: 过滤器层双实现（universe.py vs universe_filter_clean.py）

**现状**:

- `filter/universe.py` — 旧版过滤器（功能堆叠、结构混乱）
- `filter/universe_filter_clean.py` — 清理版（向量化、结构清晰），**当前主力**，被 `factory.py` 引用

**引用计数测量**（grep `from filter\.universe import`，2026-08-15）: 旧版 `universe.py` **生产代码零引用** —— 仅 2 个测试文件引用（`test_pending_order_improvements.py:210`、`test_v3_engine_integration.py:69`）。clean 版消费方：`engine_v2.py:48`、`engine.py:33`（连弃用的 V1 引擎都用 clean 版）、`factory.py:31`、`agents/`×2、`examples/`、`filter/__init__.py:125`。

**债务性质**: 旧版在生产路径上是**完全孤儿**（比初判更彻底），两个类同名 `UniverseFilter`，新读者经 `from filter.universe import` 会拿到错误版本且无任何警告。移除阻力仅剩 2 个测试文件的迁移。

### TD-6: memory/ 目录未纳入 gitignore

**现状**: `memory/` 目录（会话记忆、临时上下文）未列入 .gitignore，存在被提交进版本库的风险，污染仓库并可能泄露本地路径信息。

**债务性质**: 仓库卫生问题，修复成本极低。

**修正状态（2026-10-23）**: `.gitignore` 已新增 `memory/`；8 个已跟踪 JSON 文件已通过 `git rm -r --cached memory` 移出版本跟踪（本地文件保留）。

### TD-7: conversation/ 目录未归档

**现状**: `conversation/` 目录存放历史对话上下文，属于一次性工作产物，占据工作区顶层目录位置，干扰项目结构导航。

**债务性质**: 仓库卫生问题。应归档至 `docs/archive/` 或独立存储位置。

**修正状态（2026-10-23）**: 7 个文件已移动至 `docs/archive/conversation/`；`.gitignore` 的 `archive/` 收窄为 `/archive/`（仅根级），使该归档可入版本库；grep 确认无代码路径引用，全量测试 503 passed。

### TD-8: Data V3 描述失实（文档幻觉 H-2）

**现状**: ARCHITECTURE.md:87 将 `core/data_v3.py` 描述为 "多源数据加载器 (AKShare, YFinance)"。

**实际实现**: DataLoaderV3 是单一的 Qlib 风格向量化数据加载器（docstring 自述，data_v3.py:1-4），**全文件无任何 AKShare/YFinance/tushare 等数据源接入代码**（grep 零命中）。多源接入在 Open_Data 数据基础设施层完成。

**债务性质**: 文档幻觉 —— 点名了两个不存在的数据源依赖，夸大模块职责，误导架构判断。

**修正状态（2026-10-23）**: ARCHITECTURE.md:87 已改为 "Qlib 风格向量化加载器（NumPy 数组，供 Engine V3）"。

---

### TD-9: 代码格式化基线不合规（black）

**现状**: `black --check core tests` 在 79 个 py 文件中判定 75 个需重排（`black --diff` 约 7,872 行变动；black 26.5.0，2026-10-21 实测）。仅本次新增的 `core/target_positions.py`、`tests/test_rebalance_exits.py` 合规。

**证据**: `pyproject.toml:91-93` 已声明 `line-length = 100`；`.github/workflows/tests.yml` 只跑 pytest 与非阻断的 mypy（`|| true`），无格式化检查；仓库无 pre-commit / flake8 配置。结论：基线从未格式化，与具体功能改动无关。

**债务性质**: 工具链承诺（black 配置 + dev 依赖）与实际基线不一致，导致 `black --check` 不可作为 CI 闸门使用；若强行开启会立即红灯。

**策略**: 暂不重排，避免让 style 改动混入功能 diff。约束：新增文件必须 black-clean；遗留文件只在专门的 style-only 提交中整体重排（执行前锁定 black 版本，重排后跑全量测试，再考虑加入 CI 阻断项）。触发条件：当前 CRITICAL 修复提交完成后，选择无在途分支的窗口执行。

---

## 3. 外部调研

### 3.1 Python 弃用周期最佳实践（PEP 594 模式）

PEP 594（Remove dead batteries from Python stdlib）确立的弃用流程已成为 Python 生态的标准实践：

```
Stage 1: Deprecate     → 文档标注 + DeprecationWarning + 保留功能
Stage 2: Replace       → 提供并验证迁移路径（新 API + 迁移指南）
Stage 3: Remove        → 在预定版本移除（通常距弃用公告 ≥ 2 个版本周期）
```

**对本项目的启示**:

1. **弃用必须有运行时信号**: 仅靠注释不够，需 `warnings.warn(DeprecationWarning)`，让 CI 能捕获残留调用
2. **移除前需"零引用验证"**: grep 到零生产引用后才可删除，而非按日历时间删除
3. **单人项目可压缩周期**: 无外部 API 消费者，三阶段可在数天内完成，但顺序不可省略

### 3.2 学术参考：APIScanner

APIScanner（Python 生态 API 稳定性扫描研究）的核心发现：**多数破坏性变更源于"静默双实现"** —— 新旧 API 并存但无明确弃用标记，下游 unknowingly 依赖旧路径。这正是本项目 TD-1/2/3/5 的现状，验证了清理的必要性。

### 3.3 量化框架数据层抽象（Qlib Provider 模式）

Qlib 的数据层抽象将数据访问解耦为三类 Provider：

| Provider | 职责 | 本项目对应 |
|----------|------|-----------|
| CalendarProvider | 交易日历 | DataManager 内嵌（未拆分） |
| InstrumentProvider | 标的元数据/股票池 | UniverseFilter 自行加载 |
| FeatureProvider | 特征/行情数据 | DataManager + DataLoaderV3 双路径 |

**启示**: TD-1 的长期解法不是"删 V1 保 V3"，而是**统一到 Provider 接口层** —— 让 V2 引擎（通过适配器）和 V3 引擎（原生）消费同一份数据抽象。但这属于架构演进，超出本次清理范围，仅作为方向性结论记录。

### 3.4 文档幻觉治理（结合本项目 LLM 辅助开发现实）

本项目采用 LLM 辅助开发，文档由 AI 生成初稿 + 人工校验。H-1/H-2 两处幻觉的共性：**描述的是"设计意图"而非"实现现实"**。治理手段：

1. 文档中区分 **[已实现]** / **[规划中]** 两类陈述
2. 架构文档的每个模块描述附文件路径 + 关键类名，使断言可被 grep 验证
3. Review 闸门中加入"文档-代码一致性"检查项（已纳入本调研 Review 清单）

---

## 4. 清理方案对比

### 4.1 方案 A：激进式清理（一次性移除全部旧版）

**内容**: 单个 PR 内删除 engine.py、universe.py、config_v2.py，cli.py 切换至 factory。

| 维度 | 评估 |
|------|------|
| 速度 | 最快（1 次提交） |
| 风险 | **高** —— cli.py 切换未经回测对比验证；config_v2 删除丢失 Pydantic 设计资产 |
| 可回滚性 | 差（大 diff 交织） |
| 结论 | **否决** —— 违反 SPEC_STANDARD 的渐进实施原则 |

### 4.2 方案 B：严格三阶段（Deprecate → Replace → Remove，逐项执行）

**内容**: 按 PEP 594 模式，每项债务独立走三阶段，阶段间插入验证（回测对比、零引用 grep、测试通过）。

| 维度 | 评估 |
|------|------|
| 速度 | 慢（每项 2-3 次提交） |
| 风险 | 低 —— 每步可验证、可回滚 |
| 适用 | TD-3（cli.py 迁移）、TD-5（filter 弃用） |
| 结论 | **采纳**，作为默认方案 |

### 4.3 方案 C：冻结 + 标注（对无迁移价值的模块）

**内容**: 对 config_v2.py 这类孤儿模块：加显著"冻结"说明（frozen, not in production path），移入 `attic/` 或就地标注，不删除。

| 维度 | 评估 |
|------|------|
| 速度 | 快 |
| 风险 | 极低 |
| 权衡 | 保留设计资产（Pydantic schema 未来迁移可用），代价是仓库多一个非活跃目录 |
| 结论 | **采纳**，用于 TD-2 |

### 4.4 各债务项的方案映射

| 债务项 | 方案 | 理由 |
|--------|------|------|
| TD-1 数据层 | **暂不清理**（记录方向） | 12 处生产承重引用；接口兼容设计已就位（V3 向后兼容 V1 接口），待 Engine V3 稳定后执行文档已规划的迁移 |
| TD-2 config_v2 | C（冻结+标注）+ 修正 ARCHITECTURE.md:85 "✅活跃"（H-3） | 零生产引用，删除无收益，保留设计资产；文档错误标注必须同步修正 |
| TD-3 engine.py | B（三阶段，最高优先；**Stage 1 源码已完成**） | CLI 正在用弃用引擎，风险实际存在；弃用警告已存在，直接进 Stage 2 |
| TD-4 文档 H-1 | 直接修正文档（组件表与缺口表对齐） | 零代码风险 |
| TD-5 filter | B 简化版（生产零引用，迁 2 个测试后即可移除） | 源码级溯源确认旧版是完全孤儿，无需完整观察期 |
| TD-6 memory/ | 直接加 gitignore | 零风险 |
| TD-7 conversation/ | 归档移动 | 零风险 |
| TD-8 文档 H-2 | 直接修正文档（删除虚构的 AKShare/YFinance 表述） | 零代码风险 |
| TD-9 格式化基线 | 延后（独立 style-only 提交） | 75/79 文件、约 7,872 行机械改动；混入功能 diff 会破坏评审可读性，需单独窗口执行 |

---

## 5. 风险评估与缓解

| 编号 | 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|------|----------|
| R-1 | cli.py 切换 V2 引擎后回测结果与 V1 不一致 | 中 | 高 | 迁移前先跑基准回测（V1 引擎）存档结果；切换后对比净值曲线/持仓/成交记录；差异超阈值则暂停并调查 |
| R-2 | 移除 DataManager 引用时破坏 engine_v2 | 低 | 高 | 本次**不动 DataManager**（TD-1 暂缓）；未来迁移前先生成完整依赖图 |
| R-3 | filter 旧版仍有隐藏调用方 | **低**（源码级溯源后降级） | 中 | 已实测：生产零引用，仅 2 个测试文件（test_pending_order_improvements.py:210、test_v3_engine_integration.py:69）；移除前将这 2 处测试迁移至 clean 版即可，无需观察期 |
| R-4 | Factor_DB JSON+parquet 存储在数据量增长后查询性能退化（TD-4 关联） | 低 | 中 | 短期：文档如实标注存储格式与能力边界；长期：Factor_DB 迁移至 DuckDB（另行立项） |
| R-5 | 归档 conversation/ 时误删仍在引用的文件 | 低 | 中 | 移动而非删除；移动后跑全量测试 + grep 验证无路径引用 |
| R-6 | 文档修正引入新幻觉 | 中 | 中 | 修正内容必须附带代码证据（文件+行号），经 grep 复核后才合入 |
| R-7 | 清理提交与功能开发提交混杂，回滚困难 | 中 | 中 | 每项债务独立提交，commit message 带 TD 编号（如 `refactor(TD-3): ...`），禁止混合改动 |

---

## 6. 优先级路线图

### P0 — 立即执行（零代码风险，收益即时）

1. ✅ **[已完成 2026-10-23] TD-6**: `memory/` 加入 .gitignore，并移出已跟踪文件
2. ✅ **[已完成 2026-10-23] TD-7**: `conversation/` 归档移动至 `docs/archive/conversation/`
3. ✅ **[已完成 2026-10-23] TD-4 + TD-8 + TD-2(H-3)**: 修正 ARCHITECTURE.md 三处文档幻觉（附代码证据）—— Factor_DB "DuckDB" 表述（:65/:132/:291/:321）、Data V3 "多源 (AKShare, YFinance)" 表述（:87）、Config V2 "✅ 活跃/推荐" 标注（:85/:223）

### P1 — 本迭代内（低风险代码改动）

4. **TD-3 Stage 2**: cli.py 从 V1 引擎切换至 `factory.create_default_engine()`（Stage 1 弃用警告源码已存在，直接进替换），切换前后跑 R-1 基准对比
5. **TD-5**: `filter/universe.py` 的 2 个测试文件（test_pending_order_improvements.py、test_v3_engine_integration.py）迁移至 clean 版后，直接移除旧版（源码级溯源确认生产零引用，无需观察期）

### P2 — 下一迭代

6. **TD-3 Stage 3**: 观察一个周期、确认零生产引用后移除 `engine.py`（需同步处理 core/__init__.py re-export、examples/ 5 个脚本、tests/ 3 个测试）
7. **TD-2**: config_v2.py 冻结标注（module docstring 声明 frozen 状态与再激活条件）

### P3 — 长期方向（不在本次范围，仅记录）

8. **TD-1**: 数据层迁移（ARCHITECTURE.md 已规划"统一到 V3，废弃 V1"，接口兼容设计已就位，待 Engine V3 稳定后执行；长期可参考 Qlib Provider 模式进一步抽象）
9. **TD-4 长期**: Factor_DB 存储迁移（JSON+parquet → DuckDB，获得查询/并发能力）
10. **TD-9**: 全量 black 重排（独立 style-only 提交；先锁定 black 版本，重排后跑全量测试，再评估 CI 强制）

### 优先级判定依据

- **风险实际性** > **美学整洁度**: TD-3 的 CLI 问题影响当前每一次回测，最优先
- **验证成本**: P0 项均可在一次 grep/测试内验证完成
- **依赖顺序**: TD-3 的"移除"必须晚于"替换"一个观察周期（PEP 594 原则）；TD-5 经源码溯源降级后无需观察期

---

## 7. 结论与下一步

### 7.1 核心结论

1. 本项目技术债务的主形态是**静默双实现**（四层均有），而非典型的代码劣化
2. **唯一具有实际运行风险的是 TD-3**（CLI 调用弃用引擎），其余为可规划清理；且 engine.py 的弃用标记已完整（docstring + 运行时 Warning），剩余工作量小于预评估
3. DataManager（12 处生产引用）是承重墙，本次明确不动；数据层是"已规划未执行的迁移"（接口兼容已设计），属架构演进课题
4. **三处文档幻觉**（H-1 Factor_DB "DuckDB"、H-2 Data V3 "多源 AKShare/YFinance"、H-3 Config V2 "✅活跃"）反映"设计意图替代实现现实"的系统性风险，且 ARCHITECTURE.md 存在组件表与缺口表自相矛盾，需在 Review 闸门制度化治理；三处已于 2026-10-23 全部修正（见 TD-2/TD-4/TD-8 的修正状态）
5. 源码级溯源价值实证：相对 grep 计数级 Review，溯源额外抓出 1 处幻觉（H-3）、修正 2 处定性（TD-1 引用构成、TD-5 孤儿程度）、简化 2 项清理工作量（TD-3 Stage 1 已完成、TD-5 免观察期）

### 7.2 下一步（Phase 1 - 设计）

**当前进度（2026-10-23）**: P0-1（TD-6）、P0-2（TD-7）、P0-3 均已完成；Phase 1 设计尚未启动。

依据本调研，Phase 1 需产出 `DESIGN_tech_debt_cleanup.md`，内容应包含：

- P0/P1 各项的具体实施步骤（文件级 diff 预案）
- R-1 基准回测对比方案（测试用例、对比指标、差异阈值）
- TD-3 的 cli.py 迁移前后行为对照表
- 验收清单（Checklist）初稿

### 7.3 Review 检查清单（幻觉排除闸门）

**第一轮：grep 计数级验证（2026-08-15）**

- [x] TD-1 引用计数 38 处/22 文件可复现（grep `from core\.data import|core\.data\.DataManager|import DataManager`）
- [x] TD-2 引用计数 V1: 133 处/53 文件；V2: 9 处且仅 test_config_v2.py，可复现
- [x] TD-3 引用 10 个文件、cli.py:36 位置属实（实测 `from core.engine import BacktestEngine`）
- [x] TD-4/H-1: `factor_library/database.py` 实测无 duckdb 引用，存储为 JSON + parquet（降级 csv）；初稿误写 pickle 已修正
- [x] TD-5: `factory.py:31` 实测 `from filter.universe_filter_clean import UniverseFilter` 属实
- [x] TD-6: .gitignore 实测无 memory/conversation 条目
- [x] TD-7: conversation/ 目录存在（7 项内容），memory/ 存在（8 项内容）
- [x] TD-8/H-2: `data_v3.py` 实测无 akshare/yfinance/tushare/multi-source 关键词
- [x] 所有文件路径真实存在，无虚构引用（V3 引擎文件名初稿误写 engine_v3.py，实测为 engine_v3_vector.py，已修正）
- [x] 外部调研引用（PEP 594、Qlib）与公开资料一致

**第二轮：源码级追踪溯源（2026-08-15）**

- [x] TD-3: 打开 cli.py 源码核实 — :36 import、:77 实例化 BacktestEngine（V1），断言属实
- [x] TD-3: 打开 engine.py 核实弃用标记 — :3 "⚠️ DEPRECATED"、:41-43 `.. deprecated::`、:54-59 运行时 DeprecationWarning，"已标记弃用"属实且强于报告初判
- [x] TD-3: factory.py:242-254 create_default_engine 实测存在，返回 BacktestEngineV2
- [x] TD-1: 打开 data_v3.py 核实 — :27 "向后兼容 DataManager 接口"，报告初判"非替代品"已修正为"已规划未执行的迁移"；ARCHITECTURE.md:293/302 迁移计划属实
- [x] TD-1: 38 处引用构成拆分核实 — 生产 12 处/测试 26 处（初版表格将全部 38 处笼统标注为生产，已修正）
- [x] H-1: ARCHITECTURE.md:65/:132 "DuckDB" 表述属实存在，且与 :291 缺口表自相矛盾（新发现，已补录）
- [x] H-2: ARCHITECTURE.md:87 原文为"多源数据加载器 (AKShare, YFinance)"，点名的数据源在 data_v3.py 全文件零命中（比初判更具体）
- [x] **H-3（新发现）**: ARCHITECTURE.md:85 将 config_v2 标记 "✅ 活跃"，与生产零引用事实及其自身 :303 债务表矛盾，已补录为第三处文档幻觉
- [x] TD-5: 源码级核实旧过滤器引用面 — 生产零引用，仅 2 个测试文件（test_pending_order_improvements.py:210、test_v3_engine_integration.py:69）；连弃用的 engine.py:33 都使用 clean 版（R-3 风险降级）
- [x] TD-2: 打开 config_v2.py 核实 — Pydantic BaseModel + Field 校验属实；类名与 V1 同名（CostConfig 等），grep "ConfigV2" 零命中与源码一致

---

*本文档由 Spec-driven Development Phase 0 产出。数据测量日期 2026-08-15，若清理启动时间与测量日期间隔超过 2 周，实施前需重新测量引用计数。*








