# Changelog

All notable changes to Factor Trading v3.0 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.2.0] — 2026-06

### Changed
- **Architecture cleanup**: Removed all 18 root-level re-export bridge files
- **Import paths unified**: All imports now use `from core.xxx` / `from agents.xxx` consistently
- **`core/__init__.py`**: Rewritten with explicit public API exports (22 entities)
- **`pyproject.toml`**: Consolidated all dependencies; removed `requirements.txt`

### Fixed
- 28+ files updated with corrected import paths after root-file removal
- Test suite updated to reflect new architecture (no stale import tests)
- `core/engine_plugins.py` lazy imports corrected to absolute paths

### Added
- `.github/workflows/tests.yml` — CI pipeline (Python 3.10/3.11/3.12, pytest + mypy)
- `README.md` — Complete rewrite with TradingAgents/Qlib style: badges, architecture diagram, quick start, feature tables, project structure tree, citation template

### Removed
- `_redundant/` directory
- `requirements.txt` (merged into `pyproject.toml`)
- 18 root-level bridge files: `config.py`, `data.py`, `factor.py`, `execution.py`, `portfolio.py`, `rebalance.py`, `tracker.py`, `pending.py`, `analytics.py`, `engine.py`, `agent_framework.py`, `guru_agent_v2.py`, `research_team_v2.py`, `sentiment_framework.py`, `multi_strategy_engine.py`, `style_drift_analysis.py`, `adaptive_agent.py`, `hierarchical_bayesian_agent.py`

---

## [3.1.0] — 2026-05

### Added
- **EventLog**: JSONL persistence + in-memory ring buffer + subscription/query API
- **Guard Pipeline**: Pre-trade safety checks chain (position limit / drawdown / cooldown / turnover / concentration)
- **Plugin System**: Registry + Factory + auto-registration decorators
- **Style Reflection Engine**: Style-aware reflection + anchoring evaluation for Agent strategies
- **Distillation Isolation Audit**: Cross-agent knowledge distillation with safety isolation
- **Dependency Injection (DI)**: `BacktestEngineV2` supports Mock testing via DI
- **Pydantic Config**: `config_v2.py` with schema validation, JSON serialization, hot-reload

### Changed
- **Engine**: `BacktestEngineV2` promoted as primary engine; V1 marked deprecated
- **Risk Monitor**: Five-dimensional engine upgraded with composite scoring and LLM agent integration
- **Agent Framework**: Refactored with belief/signal/reflection base classes

---

## [3.0.0] — 2026-01

### Added
- **Modular architecture**: Refactored from `Backtest_Opus_2.0` monolith
- **Core Engine**: `BacktestEngine` with config-driven setup/run cycle
- **Factor Pipeline**: Winsorize → Fill Missing → Neutralize → Standardize → Combine
- **Portfolio Optimizer**: EqualWeight, MinVar, MeanVar, RiskParity
- **Execution Simulator**: VWAP, TWAP, Close price execution
- **Multi-Agent System**: Guru Agents (Buffett/Soros/Munger/Dalio), Research Team (6 roles), Bayesian Agent
- **Walk-Forward Analysis**: Rolling/Expanding + Purge Gap + Multi-Window
- **Brinson Attribution**: Industry Allocation + Stock Selection + Interaction decomposition
- **Global Contagion**: Cross-market correlation + Volatility spillover + CoVaR + Granger causality
- **Risk Monitor**: Five-dimensional framework (Fundamental / Industry / Macro / CapitalFlow / Sentiment)
- **Stock Filter**: Universe filter with industry, market cap, ST, suspended, limit-up/down
- **Factor_DB**: DuckDB-based multi-source data storage (Price / Factor / Macro / Sentiment / Alternative)
- **Configuration System**: Dataclass-based config with nested validation
- **Batch Backtest**: Multi-factor batch engine with result comparison
- **Strategy Evaluation**: Performance metrics, ranking, and visualization

### Migration
- This is a complete rewrite of `Backtest_Opus_2.0`. No migration path is provided.