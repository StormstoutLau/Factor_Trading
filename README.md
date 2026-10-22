# Factor Trading v3.2

<div align="center">

**[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)**
**[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)**
**[![Tests](https://img.shields.io/badge/Tests-503%20passed-brightgreen.svg)](tests/)**
**[![CI](https://github.com/StormstoutLau/Factor_Trading/actions/workflows/tests.yml/badge.svg)](https://github.com/StormstoutLau/Factor_Trading/actions)**

**专业量化回测框架  ·  Multi-Agent 投研  ·  五维风控  ·  Walk-Forward 分析**

</div>

---

## 📰 News

- **[2026-06]** **v3.2** — 架构清理：根目录桥接文件全部移除，导入路径统一为 `from core.xxx`，245 测试全部通过
- **[2026-05]** **v3.1** — 模块化升级：新增 EventLog、GuardPipeline、PluginRegistry、Agent风格化反思、蒸馏隔离审计
- **[2026-01]** **v3.0** — 重构自 Backtest_Opus_2.0，模块化设计、配置驱动、多策略支持

---

## 🏗️ Framework Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              APPLICATION LAYER                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐│
│  │   CLI Runner      │  │  Streamlit Dash  │  │  Jupyter Notebooks            ││
│  │  factor-trading    │  │  (5-page panel)  │  │  (research / tutorials)       ││
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────┬───────────────┘│
├───────────┼─────────────────────┼────────────────────────────┼────────────────┤
│           ▼                     ▼                            ▼                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        ANALYTICS & AGENTS LAYER                          │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌────────────────────────────────┐│ │
│  │  │ Multi-Agent    │  │ Walk-Forward  │  │  Performance Analytics          ││ │
│  │  │ · Guru Agents  │  │ · Rolling/Exp │  │  · Sharpe / Sortino / Calmar     ││ │
│  │  │ · ResearchTeam │  │ · Purge Gap   │  │  · Brinson Attribution           ││ │
│  │  │ · Bayes Agent  │  │ · Multi-Window│  │  · Monthly Heatmap               ││ │
│  │  └───────────────┘  └───────────────┘  └────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                            CORE ENGINE LAYER                             │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐ │ │
│  │  │ Engine V2 │  │ Factor   │  │ Portfolio│  │  Risk Monitor (5-dim)     │ │ │
│  │  │ (DI)      │  │ Pipeline │  │ Optimizer│  │  · Fundamental / Industry │ │ │
│  │  │           │  │ · MAD    │  │ · EqualW │  │  · Macro / CapitalFlow     │ │ │
│  │  │           │  │ · Neutral│  │ · MinVar │  │  · Sentiment              │ │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────────────┘ │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐ │ │
│  │  │ Execution │  │ Tracker  │  │ Guard    │  │  Plugin System            │ │ │
│  │  │ Simulator │  │          │  │ Pipeline │  │  · Registry / Factory     │ │ │
│  │  │ · VWAP    │  │          │  │ · PreChk │  │  · EventLog (JSONL+Buf)   │ │ │
│  │  │ · TWAP    │  │          │  │ · Limits │  │  · Global Contagion       │ │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                            DATA LAYER                                    │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐│ │
│  │  │ Data Manager │  │ Factor_DB    │  │  Stock Filter                     ││ │
│  │  │ · Daily K    │  │ · DuckDB     │  │  · Suspended / Limit-up/down      ││ │
│  │  │ · Level 1    │  │ · Macro/News │  │  · Industry / MarketCap           ││ │
│  │  │ · Factor     │  │ · Alternative│  │  · ST / Custom                    ││ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

```bash
# 1. Clone & Install
git clone https://github.com/StormstoutLau/Factor_Trading.git
cd Factor_Trading_v3.0
pip install -e ".[web]"

# 2. Generate demo data (pkl files are git-ignored, not shipped with the repo)
python examples/demo.py    # writes ./demo_data/*.pkl and runs a demo backtest

# 3. CLI quick run
python cli.py info
python cli.py run --factors factor_value.pkl

# 4. Launch Dashboard
python cli.py dashboard
# or: streamlit run web/streamlit_app/main.py

# 5. Run all tests
python cli.py test
# Output: 503 passed ✓
```

```python
from core.config import BacktestConfig, FactorConfig, OptimizerConfig
from core.engine import BacktestEngine

config = BacktestConfig(
    data_dir="./demo_data",
    factor_files=["factor_value.pkl", "factor_momentum.pkl"],
    factor_weights={"factor_value": 0.6, "factor_momentum": 0.4},
    factor=FactorConfig(winsorize_method="mad"),
    optimizer=OptimizerConfig(method="equal_weight", target_count=30),
    initial_capital=10_000_000,
)

engine = BacktestEngine(config)
engine.setup()
results = engine.run()

print(f"Sharpe: {results['performance_metrics']['sharpe_ratio']:.3f}")
```

---

## 🎯 Core Features

### 🤖 Multi-Agent Trading System

| Agent | Style | Key Factors | Description |
|-------|-------|------------|-------------|
| **Guru Agent** | 巴菲特/索罗斯/芒格/达里奥 | 价值/动量/质量/风险平价 | 投资大师理念模拟 |
| **Research Team** | 6-role team | Multi-factor | 宏观/财务/技术/量化/风控/情绪 |
| **Bayesian Agent** | Hierarchical | Belief-based | 3层分层贝叶斯推断 |
| **Style Engine** | Reflection | Style-aware | 风格化反思 + 锚定评估 |

```python
from agents.guru_agent_v2 import GuruAgentV2
from agents.research_team_v2 import ResearchTeamV2

buffett = GuruAgentV2(guru_id="buffett", initial_capital=10_000_000)
team = ResearchTeamV2(team_id="alpha_team", target_count=30)
```

### 📊 Factor Pipeline

```
Raw Factor → [Winsorize] → [Fill Missing] → [Neutralize] → [Standardize] → Combined Signal
```

| Stage | Methods | Description |
|-------|---------|-------------|
| **Winsorize** | MAD / Percentile / Std | 去极值处理 |
| **Fill** | Median / Mean / Industry | 缺失值填充 |
| **Neutralize** | Industry + MarketCap | 截面回归去残差 |
| **Standardize** | Z-score / Rank / MinMax | 标准化处理 |
| **Combine** | Weighted / Rank-Weighted | 多因子合成 |

### 🛡️ Five-Dimensional Risk Monitoring

```
        Fundamental
           ╱╲
          ╱  ╲
  Sentiment    Industry
         ╲    ╱
          ╲  ╱
     CapitalFlow ──── Macro
```

| Level | Trigger | Action |
|-------|---------|--------|
| 🟢 L3 | score ≥ 0.3 | 加强监控 |
| 🟡 L2 | score ≥ 0.6 | 仓位降至50% |
| 🔴 L1 | score ≥ 0.85 | 不计成本清仓 |

### 🔍 Analysis & Optimization

| Module | Function |
|--------|----------|
| **Walk-Forward** | Rolling/Expanding + Purge Gap + Multi-Window |
| **Brinson Attribution** | Industry Allocation + Stock Selection + Interaction |
| **Global Contagion** | Cross-market correlation + Volatility spillover + CoVaR |
| **Guard Pipeline** | Pre-trade checks: position limit / drawdown / cooldown / turnover |
| **EventLog** | JSONL persistence + ring buffer + subscription/query |
| **Plugin System** | Registry + Factory + auto-registration decorators |

### 🗄️ Factor_DB (DuckDB)

High-performance local storage for multi-source data:

| Data Type | Tables | Query |
|-----------|--------|-------|
| **Price** | daily_prices, level1_snapshots | PriceQuery |
| **Factor** | factor_data, factor_info | FactorQuery |
| **Macro** | macro_data, macro_indicators | MacroQuery |
| **Sentiment** | news_sentiment, report_sentiment | SentimentQuery |
| **Alternative** | alternative_data, alternative_types | AlternativeQuery |

---

## 📦 Installation

### Pip

```bash
pip install -e .            # core only
pip install -e ".[web]"     # with Streamlit dashboard
pip install -e ".[dev]"     # with dev tools (pytest, mypy, black)
```

### Docker (Recommended)

```bash
docker compose run --rm test
docker compose run --rm backtest
```

### uv

```bash
uv sync
```

### Requirements

- Python 3.10+
- Core: numpy, pandas, scipy, matplotlib, seaborn
- Optimization: cvxpy
- Database: duckdb
- Validation: pydantic
- Full list: [pyproject.toml](pyproject.toml)

---

## 🚀 Usage Scenarios

### Single Factor Backtest

```python
from core.config import BacktestConfig, FactorConfig, OptimizerConfig, RebalanceConfig
from core.engine import BacktestEngine

config = BacktestConfig(
    data_dir="./demo_data",
    factor_files=["factor_value.pkl"],
    factor=FactorConfig(winsorize_method="mad", standardize="zscore"),
    optimizer=OptimizerConfig(method="equal_weight", target_count=30),
    rebalance=RebalanceConfig(method="fixed", frequency="monthly"),
    initial_capital=10_000_000,
)
engine = BacktestEngine(config)
engine.setup()
results = engine.run()
```

### Multi-Agent Strategy

```python
from agents.multi_strategy_engine import MultiStrategyEngine
from agents.guru_agent_v2 import GuruAgentV2

engine = MultiStrategyEngine(config)
engine.register_agent(GuruAgentV2(guru_id="buffett"))
engine.register_agent(GuruAgentV2(guru_id="soros"))
results = engine.run()
```

### Multi-Source Fusion Analysis

```python
from analytics.multi_source_analysis import MultiSourceAnalysis

msa = MultiSourceAnalysis("market.db")
scores = msa.combine_score(
    date="2024-06-30",
    weights={"factor": 0.4, "sentiment": 0.3, "macro": 0.3},
)
```

### Batch Parameter Scan

```python
from batch_backtest.engine import BatchBacktestEngine

batch = BatchBacktestEngine(config, factor_db=db)
results = batch.run_all_factors()
comparison = batch.compare_results(results)
```

### CLI Quick Commands

```bash
# System info
python cli.py info

# Run backtest
python cli.py run --factors factor_value.pkl,factor_momentum.pkl --target-count 30

# Analyze results
python cli.py analyze --results output/portfolio.csv

# Run tests
python cli.py test --verbose

# Launch dashboard
python cli.py dashboard --port 8501
```

### Streamlit Dashboard

```bash
streamlit run web/streamlit_app/main.py
```

5-page dashboard: Overview · Backtest Runner · Factor Analysis · Risk Monitor · Performance

---

## 📁 Project Structure

```
Factor_Trading_v3.0/
├── core/                          # 核心引擎 (27 files)
│   ├── engine.py / engine_v2.py   # 回测引擎 (V1 deprecated, V2 with DI)
│   ├── engine_v3_vector.py        # 向量化引擎 (high-performance)
│   ├── config.py / config_v2.py   # 配置系统 (dataclass / Pydantic)
│   ├── data.py / data_v3.py       # 数据管理器
│   ├── factor.py                  # 因子处理管道 (Pipeline + Combiner)
│   ├── portfolio.py               # 组合优化 (EqualW / MinVar / MeanVar / RiskParity)
│   ├── execution.py               # 交易执行模拟 (VWAP / TWAP / Close)
│   ├── tracker.py / pending.py    # 持仓跟踪 + 待执行订单
│   ├── rebalance.py               # 再平衡触发 (Fixed / Conditional / Hybrid)
│   ├── analytics.py               # 绩效分析 (Sharpe / Sortino / Calmar)
│   ├── attribution.py             # Brinson 归因
│   ├── walk_forward.py            # Walk-Forward 框架
│   ├── risk_monitor.py            # 五维风控引擎
│   ├── global_contagion.py        # 全球市场传染分析
│   ├── event_log.py               # 事件日志 (JSONL + Ring Buffer)
│   ├── guard_pipeline.py          # 风控管道 (Pre-trade checks)
│   ├── engine_plugins.py          # 插件系统
│   ├── factory.py / registry.py   # 工厂 + 注册中心
│   └── interfaces.py              # 核心接口定义
│
├── agents/                        # Multi-Agent 投研框架 (14 files)
│   ├── agent_framework.py         # Agent 基类 + 信念/信号/反思
│   ├── guru_agent_v2.py           # 投资大师 Agent (巴菲特/索罗斯/芒格/达里奥)
│   ├── research_team_v2.py        # 6角色投研团队
│   ├── hierarchical_bayesian_agent.py  # 分层贝叶斯 Agent
│   ├── multi_strategy_engine.py   # 多策略并行引擎
│   ├── strategy_allocator.py      # 策略分配器
│   ├── style_profile.py           # 风格画像
│   ├── style_reflection_engine.py # 风格化反思引擎
│   ├── assumption_monitor.py      # 假设监控
│   └── sentiment_framework.py     # 情感分析框架
│
├── filter/                        # 股票池过滤器 (9 files)
│   ├── universe_filter_clean.py   # 主过滤器
│   ├── industry.py / market_cap.py # 行业/市值过滤
│   └── custom.py / extended.py    # 自定义扩展
│
├── factor_library/                # 因子库管理
├── batch_backtest/                # 批量回测引擎
├── strategy_evaluation/           # 策略评估
├── order_strategy/                # 下单策略
│
├── web/                           # Web Dashboard
│   ├── streamlit_app/             # Streamlit 5-page dashboard
│   │   ├── main.py                # Entry point + navigation
│   │   └── pages/                 # 01_Overview / 02_Backtest / 03_Factor
│   │                             # 04_Risk / 05_Performance
│   ├── server.py                  # Static HTTP server
│   ├── index.html                 # Quant Dashboard (manual HTML)
│   └── cli.html                   # CLI-style interface
├── assets/                        # 静态资源 (架构图等)
├── examples/                      # 示例脚本 (7 files)
├── tests/                         # 测试套件 (503 tests, 49 files)
├── docs/                          # 文档 (9 files)
├── tools/                         # 工具脚本 (benchmark / audit / ui)
├── data/                          # 事件日志存储
├── demo_data/                     # Demo 数据
├── gurus/                         # Guru 配置 (JSON)
│
├── cli.py                         # CLI 命令行入口 (run/test/analyze/info/dashboard)
├── pyproject.toml                 # 项目配置 + 依赖
├── Dockerfile                     # Docker 支持
├── docker-compose.yml             # 一键启动
├── CHANGELOG.md                   # 版本日志
└── README.md                      # 本文件
```

---

## 📚 Documentation

- [ARCHITECTURE_ANALYSIS.md](docs/ARCHITECTURE_ANALYSIS.md) — 架构设计分析
- [CODE_WIKI.md](docs/CODE_WIKI.md) — 代码手册
- [BACKTEST_ENGINE_UPGRADE_PLAN.md](docs/BACKTEST_ENGINE_UPGRADE_PLAN.md) — 引擎升级方案
- [WALK_FORWARD_PLAN.md](docs/WALK_FORWARD_PLAN.md) — Walk-Forward 设计
- [INTEGRATION_PROPOSAL.md](docs/INTEGRATION_PROPOSAL.md) — Factor_DB 集成方案

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas where help is especially welcome:
- New factor implementations
- Additional Agent styles
- Risk monitor dimensions
- Documentation improvements
- Performance benchmarks

---

## 📄 Citation

If you use this framework in your research, please cite:

```bibtex
@software{factor_trading_v3,
  author = {Factor Trading v3.0 Team},
  title = {Factor Trading v3.0: A Professional Quantitative Backtesting Framework},
  year = {2026},
  url = {https://github.com/StormstoutLau/Factor_Trading}
}
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Factor Trading v3.2** — 专业、模块化、可扩展的 A 股量化回测框架

</div>