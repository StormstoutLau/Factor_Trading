# Factor Trading v3.0 - 专业量化回测框架

> **v3.1 升级**: 借鉴 OpenAlice 优秀设计，新增 EventLog、GuardPipeline、PluginRegistry 等基础设施

## 核心特性

### 完整的待执行订单管理
- **失败交易自动重试**：卖出失败每日重试，买入失败备选替补
- **智能过期机制**：基于因子信号半衰期的过期管理
- **备选替补策略**：买入失败时的智能替补机制
- **详细事件日志**：完整的订单生命周期记录

### 多种组合优化策略
- **等权重优化**：简单有效的等权分配
- **最小方差优化**：基于协方差矩阵的风险最小化
- **均值方差优化**：经典马科维茨优化
- **风险平价优化**：等风险贡献分配

### 灵活的因子处理管道
- **去极值处理**：MAD、百分位、标准差法
- **缺失值填充**：中位数、均值、零值填充
- **行业市值中性化**：完整的中性化处理
- **标准化处理**：Z-score、排序、最小最大标准化
- **多因子合成**：加权合成和排序加权

### 真实市场约束
- **停牌股票过滤**：实时停牌状态检查
- **涨跌停股票过滤**：普通股和 ST 股不同阈值
- **下一交易日可交易性**：前瞻性交易能力检查
- **完整交易成本**：佣金、印花税、滑点模拟

### 高级功能
- **整手数优化**：100 股整数倍约束
- **多种再平衡触发**：固定间隔、条件触发、混合模式
- **详细性能分析**：收益、风险、交易指标全覆盖
- **可视化报告**：净值曲线、回撤分析、月度收益热图

### v3.1 新增基础设施（借鉴 OpenAlice）
- **EventLog**: 持久化 JSONL 事件日志，支持订阅/查询/恢复
- **GuardPipeline**: 可插拔风控管道（持仓上限/回撤/冷却/换手率）
- **PluginRegistry**: 统一插件注册中心，支持自注册
- **向后兼容**: 旧导入路径完全保留

---

## Agent 系统设计

### 架构概览

本项目实现了**多层级、多风格的 Agent 协作决策系统**，模拟真实投研团队的运作方式：

```
┌─────────────────────────────────────────────────────────────────┐
│                      投研团队 (ResearchTeam)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 宏观分析师   │  │ 财务分析师   │  │ 技术分析师   │            │
│  │ 量化研究员   │  │ 风控专员     │  │ 情绪分析师   │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                │                │                    │
│         └────────────────┼────────────────┘                    │
│                          ▼                                      │
│              ┌─────────────────────┐                           │
│              │   元策略控制器       │                           │
│              │   (Meta-Controller)  │                           │
│              └─────────────────────┘                           │
│                          │                                      │
│                          ▼                                      │
│              ┌─────────────────────┐                           │
│              │   共识聚合与决策     │                           │
│              └─────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Guru Agent 层                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 巴菲特   │  │ 索罗斯   │  │ 芒格     │  │ 达里奥   │       │
│  │ 价值投资 │  │ 宏观趋势 │  │ 多元思维 │  │ 全天候   │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### Agent 类型

#### 1. BaseAgent - 基础 Agent

所有 Agent 的基类，提供通用能力：

- **信念引擎 (BeliefEngine)**: 分层贝叶斯信念系统，支持多层级信念管理
- **预测追踪**: 准确率窗口、预测历史记录
- **反思机制**: 定期或事件驱动的自我评估
- **信号生成**: 基于信念生成买卖信号

```python
from agents.agent_framework import BaseAgent, AgentConfig

config = AgentConfig(
    agent_id="my_agent",
    style=AgentStyle.MODERATE,
    initial_capital=10_000_000,
    target_count=20,
    max_weight=0.10,
)
agent = BaseAgent(config)
```

#### 2. GuruAgentV2 - 投资大师 Agent

基于真实投资大师理念构建的 Agent：

| Guru | 风格 | 核心因子 | 持有期 | 特点 |
|------|------|----------|--------|------|
| **巴菲特** | 长期价值 | ROE、毛利率、低负债 | 10年+ | 护城河、安全边际 |
| **索罗斯** | 宏观趋势 | 动量、宏观数据 | 数月-1年 | 反身性、大额押注 |
| **芒格** | 多元思维 | 质量、价值 | 长期 | 多学科模型 |
| **达里奥** | 全天候 | 风险平价 | 长期 | 经济周期、分散化 |

```python
from agents.guru_agent_v2 import GuruAgentV2

# 创建巴菲特风格 Agent
buffett = GuruAgentV2(
    guru_id="buffett",
    initial_capital=10_000_000,
    target_count=20,
    max_weight=0.15,
)

# 生成信号
signal = buffett.generate_signal(market_data, date)
```

#### 3. ResearchTeamV2 - 投研团队

模拟真实投研团队的协作决策：

- **6 个角色**: 宏观分析师、财务分析师、技术分析师、量化研究员、风控专员、情绪分析师
- **共识机制**: 加权投票，权重基于历史准确率
- **元策略控制**: 动态调整各角色影响力
- **风格漂移检测**: 监控团队整体风格变化

```python
from agents.research_team_v2 import ResearchTeamV2

team = ResearchTeamV2(
    team_id="alpha_team",
    initial_capital=10_000_000,
    target_count=30,
)

# 运行团队决策
result = team.run_step(market_data, date)
```

#### 4. HierarchicalBayesianAgent - 分层贝叶斯 Agent

基于分层贝叶斯推断的信念系统：

- **三层信念**: 理念层(Philosophy) → 战略层(Strategy) → 战术层(Tactic)
- **贝叶斯更新**: 根据市场反馈更新后验概率
- **父节点影响**: 上层信念对下层施加先验约束
- **宏观冲击**: 支持外部冲击事件的影响传导

```python
from agents.hierarchical_bayesian_agent import HierarchicalBayesianAgent

agent = HierarchicalBayesianAgent(
    agent_id="bayesian_001",
    style=AgentStyle.MODERATE,
)

# 构建信念层级
agent.build_belief_hierarchy()

# 更新信念
agent.update_beliefs(market_data, date)
```

---

## 蒸馏机制 (Distillation)

### 什么是 Agent 蒸馏？

Agent 蒸馏是将投资大师的理念、策略和心智模型编码为结构化配置的过程，使程序能够：

1. **复用大师智慧**: 将巴菲特、索罗斯等的投资哲学转化为可执行代码
2. **保持风格一致性**: 确保 Agent 行为与大师理念一致
3. **防止数据窥探**: 通过三层隔离确保蒸馏配置不泄露未来信息

### 蒸馏配置结构

```json
{
  "guru_id": "buffett",
  "name": "沃伦·巴菲特",
  "style": "value",
  "typical_holding_period": "very_long",
  "position_style": "concentrated",
  "preferred_factors": {
    "factor_value": 0.5,
    "factor_quality": 0.3,
    "factor_profitability": 0.2
  },
  "distillation_config": {
    "source": "manual",
    "learning_mode": "frozen",
    "data_source_declared": "人工编写，基于投资大师公开理念",
    "frozen_in_test": true
  }
}
```

### 三层隔离防护

| 层级 | 机制 | 作用 |
|------|------|------|
| **配置层** | `DistillationSource` 枚举 | 声明数据来源（人工/训练/混合） |
| **运行层** | `LearningMode` 枚举 | 控制测试期是否允许学习（冻结/在线/重置） |
| **持久层** | `frozen_in_test` 标志 | 测试期强制冻结信念更新 |

### 使用示例

```python
from core.config import AgentDistillationConfig, DistillationSource, LearningMode

# 创建蒸馏配置
distillation = AgentDistillationConfig(
    source=DistillationSource.MANUAL,      # 人工编写
    learning_mode=LearningMode.FROZEN,      # 测试期冻结
    frozen_in_test=True,
)

# 应用到 Guru Agent
buffett = GuruAgentV2(
    guru_id="buffett",
    distillation_config=distillation,
)

# 测试期自动冻结
buffett.set_period("test")  # 信念不再更新
```

### 蒸馏审计

提供审计工具检查蒸馏配置是否存在数据窥探风险：

```python
from tools.distillation_audit import DistillationAuditor

auditor = DistillationAuditor()

# 审计单个 Guru
report = auditor.audit_guru_json("gurus/buffett.json")

# 审计全部
all_reports = auditor.audit_all_gurus()
```

---

## 反思机制 (Reflection)

### 设计哲学

不同投资风格的 Agent 应有不同的反思节奏和锚定对象：

- **长期价值投资者**不应每天反思，而应关注**护城河是否被侵蚀**
- **技术交易员**应在**每笔交易后立即复盘**，关注胜率和盈亏比
- **宏观投资者**应在**重大政策事件后反思**，关注假设是否被证伪

### 风格化反思配置

| 风格 | 反思触发 | 最小间隔 | 核心锚定 | 信息偏好 |
|------|----------|----------|----------|----------|
| **长期价值** | 定期+事件 | 1年 | 护城河评分、ROE持续性 | 年报、产业链 |
| **宏观趋势** | 定期+事件 | 1季度 | 宏观假设验证、趋势强度 | 宏观数据、政策 |
| **基本面** | 定期+事件 | 1季度 | 盈利预测准确度、估值误差 | 季报、行业数据 |
| **技术交易** | 每笔交易后 | 1日 | 胜率、盈亏比、最大连亏 | 价量数据 |
| **量化** | 定期+绩效 | 1周 | 因子衰减、过拟合指标 | 因子绩效 |

### 使用示例

```python
from agents.style_reflection_engine import StyleReflectionEngine
from agents.style_profile import InvestmentStyle

# 为巴菲特风格 Agent 创建反思引擎
engine = StyleReflectionEngine(InvestmentStyle.LONG_TERM_VALUE)

# 检查是否应该反思
should_reflect, reason = engine.should_reflect(
    current_time=datetime.now(),
    current_drawdown=0.15,
)

# 评估锚定对象
result = engine.evaluate_anchor({
    "moat_score": 0.8,
    "roe_stability": 0.18,
})

if result["needs_adjustment"]:
    print("需要调整持仓")
```

### 三层反思架构

```
┌─────────────────────────────────────────────────────────────────┐
│  层级1: Belief.reflect()                                        │
│  锚定: 信念后验概率的时序轨迹                                    │
│  内容: "我的信念变化是否合理？"                                  │
├─────────────────────────────────────────────────────────────────┤
│  层级2: Agent.reflect()                                         │
│  锚定: 所有信念的反思结果 + 近期预测准确率                        │
│  内容: "我的整体认知状态是否健康？"                              │
├─────────────────────────────────────────────────────────────────┤
│  层级3: Team.reflect()                                          │
│  锚定: 团队角色准确率 + 元控制器配置                              │
│  内容: "作为团队一员，我的调整参数是否合适？"                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 风险监控模块设计

### 设计原理

风险监控模块采用**多维度、分层级、可扩展**的设计哲学：

1. **多维度覆盖**：从基本面、行业、宏观、资金、情绪五个维度全面监控风险
2. **松耦合架构**：各维度监控器独立运行，通过统一接口输出信号
3. **可配置策略**：各维度权重、阈值、启用状态均可配置
4. **分级响应**：三级预警对应不同的风控动作强度

### 架构结构

```
┌─────────────────────────────────────────────────────────────────┐
│                    CompositeRiskEngine                          │
│                      (综合风控引擎)                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  加权综合评分  +  最高等级取并集  →  综合风险等级          │   │
│  │  composite_score = Σ(score_i × weight_i) / Σweight_i    │   │
│  │  max_level = max(level_i)                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │  风控动作生成 │    │  信号历史   │    │  LLM Agent  │       │
│  │  _generate_  │    │  记录追踪   │    │  智能分析   │       │
│  │  actions()   │    │             │    │  (预留)     │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Fundamental   │   │   Industry    │   │    Macro      │
│ Monitor       │   │   Monitor     │   │   Monitor     │
│ (基本面)       │   │   (行业)       │   │   (宏观)       │
├───────────────┤   ├───────────────┤   ├───────────────┤
│ - 财报异常     │   │ - 行业景气度   │   │ - 利率环境     │
│ - 风险事件     │   │ - 政策冲击     │   │ - 通胀水平     │
│ - 财务健康度   │   │ - 竞争格局     │   │ - 经济周期     │
└───────────────┘   └───────────────┘   └───────────────┘
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ CapitalFlow   │   │   Sentiment   │   │  (可扩展)      │
│ Monitor       │   │   Monitor     │   │               │
│ (资金流向)     │   │   (市场情绪)   │   │               │
├───────────────┤   ├───────────────┤   ├───────────────┤
│ - 主力资金流向 │   │ - 舆情情绪     │   │ - 自定义维度   │
│ - 北向资金     │   │ - 恐慌指数     │   │               │
│ - 融资融券     │   │ - 异常波动     │   │               │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 核心组件

#### 1. RiskSignal - 风险信号

统一的风险信号数据模型：

```python
@dataclass
class RiskSignal:
    dimension: str           # 维度名称
    level: RiskLevel         # 风险等级 (SAFE/LOW/MEDIUM/HIGH)
    score: float             # 风险分数 0-1
    symbol: Optional[str]    # 相关股票代码
    message: str             # 信号描述
    timestamp: datetime      # 时间戳
    metadata: dict           # 扩展数据
```

#### 2. BaseRiskMonitor - 监控器基类

所有监控器的抽象基类：

```python
class BaseRiskMonitor(ABC):
    def __init__(self, name: str, enabled: bool = True, weight: float = 1.0):
        self.name = name
        self.enabled = enabled
        self.weight = weight
        self._history: list[RiskSignal] = []

    @abstractmethod
    def monitor(self, symbol: Optional[str] = None, **kwargs) -> RiskSignal:
        """执行监控，返回风险信号"""
        pass
```

#### 3. 五维监控器

| 监控器 | 监控内容 | 关键指标 |
|--------|----------|----------|
| **FundamentalMonitor** | 基本面风险 | 财报异常、风险事件、财务健康度 |
| **IndustryMonitor** | 行业风险 | 行业景气度、政策冲击、竞争格局 |
| **MacroMonitor** | 宏观风险 | 利率环境、通胀水平、经济周期 |
| **CapitalFlowMonitor** | 资金风险 | 主力资金流向、北向资金、融资融券 |
| **SentimentMonitor** | 情绪风险 | 舆情情绪、恐慌指数、异常波动 |

### 三级预警体系

| 等级 | 颜色 | 触发条件 | 风控动作 |
|------|------|----------|----------|
| **三级预警** | 🟢 | score ≥ 0.3 | 维持关注，加强监控 |
| **二级预警** | 🟡 | score ≥ 0.6 | 调低仓位至50%，暂停买入 |
| **一级预警** | 🔴 | score ≥ 0.85 | 不计成本清仓，暂停所有买入 |

### 综合评分算法

```python
# 1. 加权平均计算综合分数
composite_score = Σ(signal.score × monitor.weight) / Σmonitor.weight

# 2. 取最高风险等级
max_level = max(signal.level for signal in signals)

# 3. 综合分数override
if composite_score >= 0.8:
    max_level = HIGH
elif composite_score >= 0.6:
    max_level = max(max_level, MEDIUM)
```

### 使用示例

```python
from core.risk_monitor import (
    CompositeRiskEngine,
    FundamentalMonitor,
    IndustryMonitor,
    RiskLevel,
)

# 创建风控引擎
engine = CompositeRiskEngine([
    FundamentalMonitor(weight=1.5),   # 基本面权重更高
    IndustryMonitor(weight=1.0),
    # ... 其他监控器
])

# 执行风险评估
signal, actions = engine.evaluate(
    symbol="000001.SZ",
    fundamental={
        "earnings_miss": True,
        "debt_ratio": 0.85,
    },
    industry={
        "policy_shock": True,
    }
)

print(f"风险等级: {signal.emoji} {signal.level_name}")
print(f"综合评分: {signal.score:.2f}")

# 执行风控动作
for action in actions:
    print(f"动作: {action.action_type}, 原因: {action.reason}")
```

### 扩展自定义监控器

```python
from core.risk_monitor import BaseRiskMonitor, RiskSignal, RiskLevel

class CustomMonitor(BaseRiskMonitor):
    """自定义监控器示例"""

    def __init__(self):
        super().__init__("custom", enabled=True, weight=1.0)
        self.threshold_medium = 0.5
        self.threshold_high = 0.8

    def monitor(self, symbol=None, **kwargs):
        # 实现自定义监控逻辑
        score = self._calculate_custom_score(kwargs)

        if score >= self.threshold_high:
            level = RiskLevel.HIGH
        elif score >= self.threshold_medium:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        return self._record(RiskSignal(
            dimension=self.name,
            level=level,
            score=score,
            symbol=symbol,
            message="自定义风险信号",
        ))

# 注册到引擎
engine = CompositeRiskEngine()
engine.add_monitor(CustomMonitor())
```

---

## 因子模块功能

### 因子处理管道 (Factor Pipeline)

完整的因子处理流程，确保数据质量：

```
原始因子数据
    ↓
[去极值处理]  ──→ MAD / 百分位 / 标准差法
    ↓
[缺失值填充]  ──→ 中位数 / 均值 / 零值 / 行业均值
    ↓
[中性化处理]  ──→ 行业市值中性化（截面回归去残差）
    ↓
[标准化处理]  ──→ Z-score / 排序标准化 / Min-Max
    ↓
[多因子合成]  ──→ 加权合成 / 排序加权
    ↓
合成信号
```

### 去极值方法

| 方法 | 说明 | 适用场景 |
|------|------|----------|
| **MAD** | 中位数绝对偏差，对异常值鲁棒 | 默认推荐 |
| **百分位** | 基于分位点截断 | 分布未知时 |
| **标准差** | 基于均值和标准差 | 正态分布假设 |

### 中性化处理

```python
from core.factor import FactorPipeline

pipeline = FactorPipeline(
    winsorize_method="mad",
    winsorize_n=5.0,
    neutralize=True,           # 启用中性化
    neutralize_fields=["industry", "mktcap"],  # 对行业和市值中性化
    standardize_method="zscore",
)

# 处理因子
processed = pipeline.process(raw_factor, industry_data, mktcap_data)
```

### 因子库管理 (Factor Library)

独立的因子数据库模块，支持因子的全生命周期管理：

```python
from factor_library.database import FactorDatabase, FactorMetadata

# 创建因子库
db = FactorDatabase("./factor_db")

# 注册因子
db.add_factor(
    "roe_ttm",
    factor_data,
    metadata={
        "category": "fundamental",
        "frequency": "quarterly",
        "description": "ROE TTM",
        "author": "quant_team",
    }
)

# 查询因子
factors = db.query(category="value")

# 获取因子谱系（版本历史）
lineage = db.get_lineage("roe_ttm")
```

### 因子统计评估

```python
from strategy_evaluation.stats import FactorStatsCalculator

# 计算因子统计指标
calc = FactorStatsCalculator(factor_data, returns_data)
stats = calc.calculate_all_stats()

# 输出:
# - IC 均值、标准差、IR
# - IC 半衰期
# - 因子换手率
# - 因子衰减速度
```

### 批量因子回测

```python
from batch_backtest.engine import BatchBacktestEngine

# 批量评估所有因子
batch = BatchBacktestEngine(config, factor_db=db)
results = batch.run_all_factors()

# 对比结果
comparison = batch.compare_results(results)

# 找出最佳因子
best_factor, best_sharpe = batch.get_best_factor(metric="sharpe_ratio")
```

---

## 项目架构

```
Factor_Trading_v3.0/
├── core/                          # 核心引擎模块
│   ├── config.py                  # 全局配置管理
│   ├── data.py                    # 数据管理器
│   ├── engine.py                  # 回测引擎核心 (deprecated)
│   ├── engine_v2.py               # 解耦引擎（推荐）
│   ├── interfaces.py              # 核心接口定义
│   ├── factory.py                 # 组件工厂
│   ├── factor.py                  # 因子处理管道
│   ├── portfolio.py               # 组合优化器
│   ├── execution.py               # 交易执行模拟
│   ├── tracker.py                 # 持仓跟踪器
│   ├── rebalance.py               # 再平衡触发器
│   ├── pending.py                 # 待执行订单管理
│   ├── analytics.py               # 性能分析模块
│   ├── risk_monitor.py            # 五维风险监控
│   ├── walk_forward.py            # Walk-Forward框架
│   ├── event_log.py               # 事件日志
│   ├── guard_pipeline.py          # 风控管道
│   └── registry.py                # 插件注册中心
│
├── agents/                        # Agent 框架
│   ├── agent_framework.py         # Agent 基类与框架
│   ├── guru_agent_v2.py           # Guru Agent
│   ├── research_team_v2.py        # 投研团队
│   ├── hierarchical_bayesian_agent.py  # 分层贝叶斯
│   ├── style_profile.py           # 风格画像
│   ├── style_reflection_engine.py # 风格化反思引擎
│   ├── assumption_monitor.py      # 假设监控
│   ├── strategy_allocator.py      # 策略分配器
│   ├── sentiment_framework.py     # 情感分析
│   └── auto_parameter_optimizer.py # 自动参数优化
│
├── factor_library/                # 因子库模块
│   └── database.py                # 因子数据库
│
├── batch_backtest/                # 批量回测模块
│   └── engine.py                  # 批量回测引擎
│
├── strategy_evaluation/           # 策略评估模块
│   ├── stats.py                   # 因子统计
│   └── evaluator.py               # 策略评估器
│
├── order_strategy/                # 下单策略模块
│   ├── strategies.py              # 策略实现
│   └── evaluator.py               # 策略评估
│
├── filter/                        # 股票池过滤器
│
├── gurus/                         # Guru 配置数据
│
├── tools/                         # 工具脚本
│   ├── distillation_audit.py      # 蒸馏审计
│   └── ui_dashboard.py            # UI 仪表盘
│
├── web/                           # Web UI
│   └── index.html                 # 极客 Quant 风格仪表盘
│
├── examples/                      # 示例脚本
├── tests/                         # 测试（228+ 测试用例）
├── docs/                          # 文档
├── requirements.txt               # 依赖
└── README.md                      # 本文件
```

---

## 安装与使用

### 1. 环境安装

```bash
cd Factor_Trading_v3.0
pip install -r requirements.txt
```

### 2. 快速开始

```python
from config import BacktestConfig, CostConfig, UniverseConfig, FactorConfig, OptimizerConfig, RebalanceConfig
from engine import BacktestEngine

config = BacktestConfig(
    data_dir=Path("./data"),
    factor_files=["factor_value.pkl", "factor_momentum.pkl"],
    factor_weights={"factor_value": 0.6, "factor_momentum": 0.4},
    cost=CostConfig(commission_rate=0.0003),
    universe=UniverseConfig(exclude_suspended=True),
    factor=FactorConfig(winsorize_method="mad"),
    optimizer=OptimizerConfig(method="equal_weight", target_count=30),
    rebalance=RebalanceConfig(method="fixed", frequency="monthly"),
    initial_capital=10_000_000.0
)

engine = BacktestEngine(config)
engine.setup()
results = engine.run()

metrics = results['performance_metrics']
print(f"累计收益率: {metrics['total_return']:.2%}")
print(f"夏普比率: {metrics['sharpe_ratio']:.3f}")
```

### 3. 运行测试

```bash
# 运行全部测试
python -m pytest tests/ -q

# 运行特定模块测试
python -m pytest tests/test_style_reflection.py -v
```

---

## 版本历史

### v3.1 (当前)
- 模块化架构升级（factor_library, batch_backtest, strategy_evaluation, order_strategy）
- Agent 风格化反思机制
- Walk-Forward 回测框架（防数据窥探）
- 价格复权机制（前复权/后复权/不复权）
- 下单策略评估（TWAP/VWAP/冰山订单）
- 蒸馏隔离与审计工具
- 解耦引擎 v2（依赖注入）

### v3.0
- 基于 Backtest_Opus_2.0 重构
- 模块化设计
- 配置驱动
- 多策略支持

---

## 使用场景

- **因子研究**: 多因子组合测试、IC/IR 分析、半衰期评估
- **策略开发**: 量化策略回测、参数优化、过拟合防护
- **风险管理**: 五维风险监控、全球传染分析、假设检验
- **绩效归因**: Brinson 归因、收益来源分解
- **Agent 研究**: 投资大师模拟、团队协作决策、风格漂移检测

---

## 开放问题与设计决策

以下问题在架构设计中存在多种合理方案，当前实现采用其中一种，欢迎讨论和贡献：

### 1. 投研团队 Agent 与 Guru Agent 的关系

**问题**: 投研团队 Agent (`ResearchTeamAgent`) 与 Guru Agent (`GuruAgentV2`) 之间应建立何种关系？

**当前状态**: 两者完全独立，无任何交互。在 `MultiAgentBacktestEngine` 中作为平级 Agent 注册，各自独立生成信号。

**可选方案**:

| 方案 | 关系 | 优点 | 缺点 |
|------|------|------|------|
| **A. 完全独立** (当前) | 平级并列 | 实现简单，无循环依赖 | 信息孤岛，决策可能矛盾 |
| **B. Guru 作为顾问** | 团队咨询 Guru | 融合大师智慧，决策更稳健 | 实现复杂，需定义交互协议 |
| **C. Guru 作为成员** | Guru 是团队一员 | 直接参与投票，权重可配置 | 模糊了"人"与"理念"的边界 |
| **D. 双层架构** | 团队选方向，Guru 选个股 | 分工明确 | 协调复杂度高 |

**推荐方向**: 方案 B（顾问模式）—— Guru 作为投研团队的"外部顾问团"，团队决策时参考 Guru 观点，但保留最终决策权。Guru 权重默认 30%，极端市场可提高。

**相关代码**:
- `agents/agent_framework.py` - `ResearchTeamAgent` 类
- `agents/guru_agent_v2.py` - `GuruAgentV2` 类
- `agents/research_team_v2.py` - 团队共识机制

---

**Factor Trading v3.0 - 专业的量化回测解决方案**
