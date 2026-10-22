# Factor Trading v3.2 · 架构文档

> 版本: v3.2.0 | 最后更新: 2026-06-20 | 测试: 489 个 | 核心模块: 28 个
> 权威来源: 本文件是项目架构的唯一权威文档，替代所有旧版架构分析文件。

---

## 一、项目概述

Factor Trading v3.0 是专业的 A 股量化回测框架，从 Backtest_Opus_2.0 重构而来。核心能力：

- **回测引擎**: 三引擎并行（V1 经典 / V2 插拔式 / V3 向量化），覆盖从精确模拟到快速筛选
- **Multi-Agent 投研**: 4 位 Guru Agent + 6 角色 Research Team + 分层贝叶斯 Agent
- **五维风控**: 基本面 / 行业 / 宏观 / 资金流 / 情绪
- **Walk-Forward 分析**: 训练/验证/测试三期分离，防数据窥探
- **因子全生命周期**: 预处理 → 存储 → 清洗 → 分析 → 回测

---

## 二、四层架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER                                   │
│  CLI (cli.py)  │  Streamlit Dash (web/streamlit_app/)  │  Jupyter        │
│  5 子命令        │  5 页面面板                          │  研究/教程      │
├──────────────────────────────────────────────────────────────────────────┤
│                      ANALYTICS & AGENTS LAYER                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────┐  │
│  │ Multi-Agent      │  │ Walk-Forward    │  │  Performance Analytics   │  │
│  │ · Guru (4)       │  │ · Rolling/Exp   │  │  · 收益/风险/交易指标    │  │
│  │ · ResearchTeam(6)│  │ · Purge Gap     │  │  · Brinson 归因          │  │
│  │ · Bayes Agent    │  │ · Multi-Window  │  │  · 月度热力图            │  │
│  │ · 风格反思       │  │ · 蒸馏隔离      │  │  · 策略评估              │  │
│  └─────────────────┘  └─────────────────┘  └──────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│                          CORE ENGINE LAYER                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  ENGINE V2 (主引擎)              ENGINE V3 (向量预筛选)               │ │
│  │  · 依赖注入 (DI)                 · 全向量化 NumPy                    │ │
│  │  · 插拔式组件                    · @njit JIT 加速                    │ │
│  │  · T+1 执行策略                  · 批量因子回测                      │ │
│  │  · 待执行订单队列                · 5000股×2500天: ~0.006s            │ │
│  │  · 风险管理 (止损/盯市)          · 快速因子方向验证                  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐ │
│  │ Factor   │  │ Portfolio│  │ Execution│  │  Risk Monitor (5-dim)     │ │
│  │ Pipeline │  │ Optimizer│  │ Simulator│  │  · Fundamental/Industry   │ │
│  │ · MAD    │  │ · EqualW │  │ · VWAP   │  │  · Macro/CapitalFlow      │ │
│  │ · Neutral│  │ · MinVar │  │ · TWAP   │  │  · Sentiment              │ │
│  │ · Std    │  │ · MVO    │  │ · Close  │  │  · Composite Score        │ │
│  │ · Combine│  │ · RiskPar│  │          │  │  · LLM Agent              │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐ │
│  │ Tracker  │  │ Guard    │  │ Plugin   │  │  Infrastructure           │ │
│  │ · 持仓   │  │ Pipeline │  │ System   │  │  · EventLog (JSONL+Buf)   │ │
│  │ · 收益   │  │ · 仓位限 │  │ · Registry│  │  · Global Contagion       │ │
│  │ · 风险   │  │ · 回撤限 │  │ · Factory │  │  · Live Bridge            │ │
│  │          │  │ · 冷却限 │  │ · AutoReg │  │                           │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────┤
│                            DATA LAYER                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐│
│  │ Data Manager │  │ Factor_DB    │  │  Stock Filter (10种过滤器)        ││
│  │ · Daily K    │  │ · Parquet    │  │  · 停牌/涨跌停/ST                ││
│  │ · Level 1    │  │ · Price数据  │  │  · 行业/市值/自定义              ││
│  │ · Factor     │  │ · Macro/News │  │  · 前缀/NA因子/扩展              ││
│  │ · 懒加载+缓存│  │ · Alternative│  │  · 可交易性预计算掩码            ││
│  └──────────────┘  └──────────────┘  └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 三、模块职责矩阵

### 3.1 核心引擎层 (`core/`)

| 模块 | 文件 | 行数(约) | 职责 | 状态 |
|------|------|---------|------|------|
| **Engine V1** | `engine.py` | 800+ | 经典回测引擎，config-driven setup/run cycle | ⚠️ 已弃用 |
| **Engine V2** | `engine_v2.py` | 900+ | 主引擎，依赖注入 + 插拔式架构 | ✅ 活跃 |
| **Engine V3** | `engine_v3_vector.py` | 700+ | 向量化快速因子预筛选，@njit 加速 | ✅ 活跃 |
| **Config V1** | `config.py` | 400+ | Dataclass 配置系统 | ⚠️ 遗留 |
| **Config V2** | `config_v2.py` | 500+ | Pydantic 验证 + 热重载 + JSON 序列化（设计资产，未接入生产） | ⚠️ 冻结 |
| **Data Manager** | `data.py` | 500+ | 本地 pkl 数据加载，懒加载 + 缓存 | ⚠️ 遗留 |
| **Data V3** | `data_v3.py` | 400+ | Qlib 风格向量化加载器（NumPy 数组，供 Engine V3） | ✅ 活跃 |
| **Factor Pipeline** | `factor.py` | 500+ | MAD去极值 → 填充 → 中性化 → 标准化 → 合成 | ✅ 活跃 |
| **Portfolio** | `portfolio.py` | 600+ | 4种优化器 (EqualW/MinVar/MVO/RiskPar) | ✅ 活跃 |
| **Execution** | `execution.py` | 400+ | 交易执行模拟 (VWAP/TWAP/Close) | ✅ 活跃 |
| **Execution Policy** | `execution_policy.py` | 300+ | T+1 执行策略 + SignalTranslator | ✅ 活跃 |
| **Pending Orders** | `pending.py` | 400+ | 待执行订单队列 + 替补股票 + 过期管理 | ✅ 活跃 |
| **Tracker** | `tracker.py` | 300+ | 持仓跟踪 + 组合价值 + 收益计算 | ✅ 活跃 |
| **Rebalance** | `rebalance.py` | 300+ | 再平衡触发器 (固定间隔/条件/混合) | ✅ 活跃 |
| **Analytics** | `analytics.py` | 400+ | 绩效分析 + 报告生成 | ✅ 活跃 |
| **Attribution** | `attribution.py` | 200+ | Brinson 归因 (行业配置 + 个股选择 + 交互) | ✅ 活跃 |
| **Risk Manager** | `risk_manager.py` | 300+ | 止损/保证金/盯市风险检查 | ✅ 活跃 |
| **Risk Monitor** | `risk_monitor.py` | 500+ | 五维风控 + 综合评分 + LLM Agent | ✅ 活跃 |
| **Guard Pipeline** | `guard_pipeline.py` | 200+ | 事前安全检查链 (仓位/回撤/冷却/换手/集中度) | ✅ 活跃 |
| **Event Log** | `event_log.py` | 200+ | JSONL 持久化 + 内存环形缓冲区 + 订阅/查询 API | ✅ 活跃 |
| **Plugin System** | `engine_plugins.py` | 200+ | Registry + Factory + 自动注册装饰器 | ✅ 活跃 |
| **Interfaces** | `interfaces.py` | 300+ | 全部核心接口 Protocol 定义 (IDataManager 等) | ✅ 活跃 |
| **Factory** | `factory.py` | 100+ | 回测引擎工厂方法 | ✅ 活跃 |
| **Walk-Forward** | `walk_forward.py` | 200+ | 窗口分割器 (Rolling/Expanding + Purge Gap) | ✅ 活跃 |
| **Walk-Forward Engine** | `walk_forward_engine.py` | 300+ | 多窗口回测引擎 + 蒸馏隔离集成 | ✅ 活跃 |
| **Global Contagion** | `global_contagion.py` | 300+ | 跨市场相关性 + 波动溢出 + CoVaR + Granger | ✅ 活跃 |
| **Live Bridge** | `live_bridge.py` | 100+ | 实盘对接接口 | ⚠️ 骨架 |

### 3.2 Agent 层 (`agents/`)

| 模块 | 文件 | 职责 | 状态 |
|------|------|------|------|
| **Agent Framework** | `agent_framework.py` | 基类: Belief/Signal/Reflection | ✅ 活跃 |
| **Guru Agent V2** | `guru_agent_v2.py` | 4 位投资大师 (Buffett/Soros/Munger/Dalio) | ✅ 活跃 |
| **Research Team V2** | `research_team_v2.py` | 6 角色研究团队 (Macro/Fundamental/Technical/Quant/Risk/PM) | ✅ 活跃 |
| **Hierarchical Bayes** | `hierarchical_bayesian_agent.py` | 分层贝叶斯信念融合 | ✅ 活跃 |
| **Sentiment** | `sentiment_framework.py` | 情绪分析框架 | ✅ 活跃 |
| **Multi-Strategy** | `multi_strategy_engine.py` | 多策略引擎 | ✅ 活跃 |
| **Strategy Allocator** | `strategy_allocator.py` | 策略分配器 | ✅ 活跃 |
| **Style Drift** | `style_drift_analysis.py` | 风格漂移检测 | ✅ 活跃 |
| **Style Profile** | `style_profile.py` | 风格画像 | ✅ 活跃 |
| **Style Reflection** | `style_reflection_engine.py` | 风格化反思 + 锚定评估 | ✅ 活跃 |
| **Adaptive Agent** | `adaptive_agent.py` | 自适应学习 | ✅ 活跃 |
| **Auto Param Optimizer** | `auto_parameter_optimizer.py` | 自动参数优化 | ✅ 活跃 |
| **Assumption Monitor** | `assumption_monitor.py` | 假设有效性监控 | ✅ 活跃 |

### 3.3 数据层

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| **Stock Filter** | `filter/` | 10 种过滤器 (停牌/涨跌停/ST/行业/市值/前缀/NA/自定义/扩展) | ✅ 活跃 |
| **Factor DB** | `factor_library/database.py` | JSON 元数据 + Parquet 文件存储（DuckDB 为规划方向） | ⚠️ 骨架 |
| **Order Strategy** | `order_strategy/` | 订单策略评估 | ✅ 活跃 |
| **Strategy Evaluation** | `strategy_evaluation/` | 策略评估指标 | ✅ 活跃 |
| **Batch Backtest** | `batch_backtest/engine.py` | 批量因子回测 | ✅ 活跃 |

---

## 四、关键数据流

### 4.1 回测主循环 (Engine V2)

```
BacktestEngineV2.run()
  │
  ├─ 1. 初始化
  │   ├─ DataManager.load()          → 价格/因子/收益率矩阵
  │   ├─ UniverseFilter.compute()    → 可交易掩码
  │   ├─ FactorPipeline.process()    → 合成因子值
  │   └─ PositionTracker.init()      → 初始持仓
  │
  ├─ 2. 逐日循环 (for date in trade_dates)
  │   ├─ PendingOrderQueue.process() → 处理过期订单
  │   ├─ GuardPipeline.check()       → 事前安全检查
  │   ├─ if Trigger.should_rebalance()
  │   │   ├─ Optimizer.optimize()    → 目标权重
  │   │   ├─ SignalTranslator.translate() → 订单意图
  │   │   └─ ExecutionSimulator.execute() → 模拟成交
  │   ├─ PendingOrderQueue.process_failed() → 失败订单重试
  │   ├─ RiskManager.check()         → 风险管理检查
  │   └─ PositionTracker.update()    → 持仓/收益更新
  │
  └─ 3. 输出
      └─ PerformanceAnalyzer.generate() → 报告/图表
```

### 4.2 Agent 决策流

```
Blogger 文本 / 新闻 / 研报
  │
  ├─ SentimentFramework.extract()    → 情绪信号
  ├─ GuruAgent.analyze()             → 大师风格信号
  ├─ ResearchTeam.research()         → 多维研究信号
  │
  ├─ HierarchicalBayesianAgent.fuse() → 信念融合
  ├─ StyleReflectionEngine.reflect()  → 风格反思
  ├─ AdaptiveAgent.adapt()            → 自适应调整
  │
  └─ StrategyAllocator.allocate()     → 策略权重 → 回测引擎
```

### 4.3 向量化快速通道 (Engine V3)

```
因子数据 (NumPy array)
  │
  ├─ _rebalance_kernel @njit    → 纯 NumPy 再平衡 (0.10ms/5000股)
  ├─ _metrics_kernel @njit      → 纯 NumPy 指标计算 (0.014ms/2500天)
  │
  └─ 结果: Sharpe/MaxDD/年化收益/波动率 (无持仓跟踪/无订单管理)
```

---

## 五、引擎对比

| 特性 | Engine V1 | Engine V2 (主引擎) | Engine V3 (预筛选) |
|------|-----------|-------------------|-------------------|
| 架构 | 单体 | 依赖注入 + 插拔 | 纯向量化 NumPy |
| 执行模型 | 逐日循环 | 逐日循环 + 事件队列 | 全矩阵一次性 |
| T+1 支持 | ❌ | ✅ (ExecutionPolicy) | ❌ |
| 待执行订单 | ❌ | ✅ (PendingOrderQueue) | ❌ |
| 风险管理 | ❌ | ✅ (止损/保证金/盯市) | ❌ |
| 股票池过滤 | ✅ | ✅ (10种过滤器) | ❌ |
| 多资产 | ❌ | ✅ | ❌ |
| 性能 (500股×500天) | ~180s | ~120s | ~0.006s |
| 适用场景 | 遗留兼容 | 精确策略回测 | 因子方向快速验证 |
| 状态 | ⚠️ 已弃用 | ✅ 活跃 | ✅ 活跃 |

---

## 六、配置系统

### 6.1 V1 (Dataclass) → V2 (Pydantic) 迁移

| 特性 | V1 (`config.py`) | V2 (`config_v2.py`) |
|------|-----------------|---------------------|
| 验证 | 手动 assert | Pydantic Field 约束 |
| 序列化 | 无 | JSON 导入/导出 |
| 热重载 | 无 | 文件监控 + 回调 |
| 向后兼容 | — | 支持 V1 dataclass 转换 |
| 状态 | ⚠️ 遗留 | ⚠️ 冻结（零生产引用） |

### 6.2 配置层级

```
BacktestConfigV2
├── CostConfig        (佣金/印花税/滑点)
├── UniverseConfig    (过滤规则)
├── FactorConfig      (因子处理参数)
├── OptimizerConfig   (优化器类型 + 约束)
├── RebalanceConfig   (触发条件)
├── AgentDistillationConfig (蒸馏隔离)
└── RiskConfig         (风控参数)
```

---

## 七、插件系统

### 7.1 注册机制

```python
# 自动注册: 装饰器模式
@register_plugin("my_optimizer")
class MyOptimizer:
    pass

# 工厂获取
optimizer = PluginFactory.create("optimizer", "my_optimizer", config)
```

### 7.2 已注册插件类型

- `optimizer`: 组合优化器
- `trigger`: 再平衡触发器
- `execution_policy`: 执行策略
- `universe_filter`: 股票池过滤器
- `guard`: 安全检查规则

---

## 八、当前状态评估

### 8.1 已完成

| 模块 | 完成度 | 验证 |
|------|--------|------|
| Engine V2 核心回测 | 100% | 489 测试通过 |
| Engine V3 向量化 | 100% | 7 个 Numba JIT 测试 |
| 因子管线 | 100% | 集成测试覆盖 |
| 组合优化器 (4种) | 100% | 单元测试覆盖 |
| 交易执行模拟 | 100% | 集成测试覆盖 |
| 待执行订单系统 | 100% | 边界测试覆盖 |
| 持仓跟踪 | 100% | 回归测试覆盖 |
| 五维风控 | 100% | 单元测试覆盖 |
| Guard Pipeline | 100% | 单元测试覆盖 |
| EventLog | 100% | 单元测试覆盖 |
| Walk-Forward | 100% | 集成测试覆盖 |
| Agent 系统 | 90% | 行为测试覆盖 |
| 真实 A 股数据验证 | 100% | 18 个严格验证测试 |
| CLI | 100% | 5 子命令 |
| Web UI | 100% | Streamlit 5 页 + CLI 展示页 |
| Docker | 100% | 多阶段构建 + 3 profile |

### 8.2 已知缺口

| 缺口 | 严重程度 | 计划 |
|------|---------|------|
| Factor_DB 查询层（DuckDB 规划） | 🟡 中 | 当前为 JSON 元数据 + Parquet 文件存储；查询/CLI 待建 |
| Live Bridge 实盘对接 | 🟡 中 | 接口已定义，需实现具体券商 API |
| 数据源统一 (data.py vs data_v3.py) | 🟡 中 | 需迁移到 V3，废弃 V1 |
| DSL 校正层 (LLM 预测偏差) | 🟡 中 | P0-P5 计划已定义 (见 `LLM_PREDICTION_AS_TRUTH_RISK.md`) |
| 高性能向量回测 (对标 Qlib) | 🟢 低 | Engine V3 是第一步，后续需表达式 DSL |
| 订单簿微结构模拟 | 🟢 低 | 长期目标 |

### 8.3 技术债务

| 债务 | 说明 |
|------|------|
| `core/data.py` 与 `core/data_v3.py` 并存 | 两套数据加载器，应统一到 V3 |
| `core/config.py` 与 `core/config_v2.py` 并存 | 两套配置系统，Engine V2 使用 V1 |
| `core/engine.py` (V1) 未删除 | 标记已弃用但未移除，历史测试依赖 |

---

## 九、依赖关系

### 9.1 运行时依赖 (核心)

| 包 | 版本 | 用途 |
|----|------|------|
| numpy | >=1.23.0 | 矩阵运算 |
| pandas | >=2.0.0 | 数据框架 |
| scipy | >=1.10.0 | 优化/统计 |
| cvxpy | >=1.2.0 | 组合优化 |
| pydantic | >=2.0.0 | 配置验证 |
| duckdb | >=0.10.0 | 规划中的 Factor_DB 查询层（当前代码未使用） |
| scikit-learn | >=1.3.0 | ML 模型 |
| statsmodels | >=0.14.0 | 计量模型 |
| matplotlib | >=3.7.0 | 可视化 |
| plotly | >=5.14.0 | 交互图表 |

### 9.2 可选依赖

| 包 | 用途 | 条件 |
|----|------|------|
| numba | Engine V3 JIT 加速 | 自动检测，不可用时降级 |
| streamlit | Web Dashboard | `[web]` extra |
| ta | 技术指标 | 因子计算 |
| tushare/akshare | 数据源 | 实时数据获取 |

---

## 十、文档索引

| 文档 | 用途 | 状态 |
|------|------|------|
| `ARCHITECTURE.md` (本文件) | 权威架构文档 | ✅ 活跃 |
| `SPEC_STANDARD.md` | Spec 驱动开发规范 | ✅ 活跃 |
| `DEVLOG.md` | 开发日志 | ✅ 活跃 |
| `DECISIONS.md` | 关键决策记录 (ADR) | ✅ 活跃 |
| `CODE_WIKI.md` | 模块级代码手册 | ⚠️ 需更新 (引用 V1 架构) |
| `LLM_PREDICTION_AS_TRUTH_RISK.md` | LLM 预测偏差风险跟踪 | ✅ 活跃 |
| `REFACTORING_SUMMARY.md` | v3.0 重构总结 | ⚠️ 历史存档 |
| `ARCHITECTURE_ANALYSIS.md` | 耦合度分析 | ⚠️ 历史存档 (内容已合并到本文件) |
| `INTEGRATION_PROPOSAL.md` | 多 Agent 融合方案 | ⚠️ 提案阶段 |
| `BACKTEST_ENGINE_UPGRADE_PLAN.md` | 回测引擎 v4.0 升级计划 | ⚠️ 提案阶段 |
| `architecture_upgrade_plan.md` | 因子批量回测升级计划 | ⚠️ 提案阶段 |
| `WALK_FORWARD_PLAN.md` | Walk-Forward 实施计划 | ✅ 已完成 |
| `LEVEL1_DUCKDB_ANALYSIS.md` | DuckDB 分析 | ⚠️ 调研阶段 |
| `LOCAL_DATA_STORAGE_ANALYSIS.md` | 本地数据存储分析 | ⚠️ 调研阶段 |