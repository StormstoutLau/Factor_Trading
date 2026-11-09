# Changelog

All notable changes to Factor Trading v3.0 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Spec_Runner 接入**: 新增 `scripts/spec_runner_adapter.py`（官方模板 v1.0 + 本项目配置：`PREFIX=factorv3`，门禁 `probe / unit-tests / black-check / mypy-check`）与 `tests/test_spec_runner_adapter.py`（6 项）；门禁 verdict/exit/stdout_tail 以 append-only JSONL 落在 `F:\Spec_Runner\sessions\`，可用 `replay` 重放。全量测试 503 → 509 passed；`black-check`（75 files）与 `mypy-check`（168 errors）已登记为已知基线

### Fixed
- **`IPositionTracker.get_snapshots` 契约失实（P-007 层 B）**: 协议声明 `list[dict]` 与 `PositionTracker` 实际返回 `list[PortfolioSnapshot]` 不符，改为真实类型（`TYPE_CHECKING` 导入，零运行时开销）
- **`IExecutionSimulator` 缺失 `trade_log` 声明（P-007 层 B）**: 引擎在结果生成中访问 `executor.trade_log.get_trades_df()`，协议未声明该成员；新增 `ITradeLog` 最小协议（仅 `get_trades_df`）并以只读 `@property` 暴露（PEP 544 协议属性不变性要求）
- **`DataManager` 辅助数据重复读盘 + 类型契约（P-010）**: `_load_auxiliary_data` 增加幂等 guard，可选文件缺失时不再每次属性访问都重读已存在文件（实测 `.industry` 3 次访问的读盘次数 **3 → 1**；100 次 `.st` 访问的读盘次数由 **206 次**降至首次加载后 0 次）；`suspend`/`st` 缺失时按配置约定 `0=正常` 提供全 0 默认帧（旧版被覆盖实现的 `True` 默认值与 `1=停牌` 语义相反，已弃用）；`industry` 注解修正为 `Optional[pd.DataFrame]`，缺失时由消费方跳过过滤/中性化；新增 4 项测试（510 → **514 passed**）
- **`CompositeRiskEngine.remove_monitor` 崩溃（P-007 层 A）**: `core/risk_monitor.py` 引用了未定义名 `RiskAction` 且与类内已声明的 `_signal_history`/`_action_history` 重复注解；调用 `remove_monitor()` 即 `NameError`。改为无注解赋值（类型仍由 L713/L714 提供），并补 smoke 测试
- **`analyze_market_contagion` 崩溃（P-007 层 A）**: `core/global_contagion.py` 调用了 `GlobalContagionMonitor` 上不存在的 `evaluate()`；调用便捷函数即 `AttributeError`。改为 `monitor.monitor(...)` 单值返回
- **`RegistryPlugin.create_trigger` 崩溃（P-007 层 A）**: 以 3 个位置参数调用只接受 `(name, config, **kwargs)` 的 `PluginRegistry.create`，调用即 `TypeError`。改为 `dates=trade_dates` 关键字传参（与三个 trigger 工厂的 `(cfg, dates)` 契约一致）
- **`DataManager._load_auxiliary_data` 重复定义（P-007 层 A，行为不变）**: 删除被同名方法覆盖的 48 行死代码，唯一实现保持原状；「辅助数据缺失时无安全默认值」的行为缺口**未在本条修复**，另立 P-010 跟踪
- **CRITICAL 再平衡修复（行为变更）**: 调出组合的标的现在会生成清仓卖单（此前永不卖出），同一次调仓中卖单先于买单；`results` 新增 `unclosed_positions` 诊断；新增 `core/target_positions.py` 统一 V1/V2 目标持仓，并以价格重算组合价值，修复开盘成交后组合价值虚高导致的超额买入
- **ARCHITECTURE.md 文档幻觉**: Factor_DB 存储由 "DuckDB" 改为 "JSON 元数据 + Parquet（DuckDB 为规划方向）"，架构图/模块表/缺口表/依赖表同步；Data V3 由 "多源 (AKShare, YFinance)" 改为 "Qlib 风格向量化加载器"；Config V2 由 "✅ 活跃/推荐" 改为 "⚠️ 冻结（零生产引用）"
- **demo_data 复权文件缺失**: `examples/demo.py` 生成器改为输出 `stock_adj.pkl`（与配置默认一致），修复旧布局导入与硬编码路径；本地补齐 `demo_data/stock_adj.pkl`

### Changed
- **空 `factor_files` fail-fast（P-007 层 B，行为变更）**: `BacktestEngineV2.setup()` 在「未注入因子管道/合成器且 `factor_files` 为空」时抛 `ValueError`（此前静默空回测：逐日 `TypeError` 被 `except Exception` 吞掉，100 条 ERROR 后返回空结果）；注入 `factor_pipeline`/`factor_combiner` 的手工信号工作流不受影响；新增 2 项 smoke（**514 → 516 passed**）
- **`_generate_results` 未 setup 守卫（P-007 层 B，行为变更）**: 未 `setup()` 直接调用 `_generate_results()` 由 `AttributeError` 改为 `RuntimeError("请先调用setup()方法")`，与 `run()` 守卫文案一致
- **引擎 mypy 清零（P-007 层 B）**: `engine_v2` 54 / `engine_v3_vector` 26 / `factory` 13 共 **93 errors → 0**（局部别名窄化 + factory `cast` 白名单，无 `type: ignore`）；`mypy-check` 门禁自接入以来首次 verdict=pass；盲区口径（`--check-untyped-defs`）102 → 8（另批评估）
- **停牌数据缺失时的末日可交易性（P-010，行为变更）**: 停牌数据缺失时改为提供 `0=正常` 默认帧，`universe_filter_clean` 的 next-day 可交易掩码因此走「有数据」路径，**最后一天由可交易变为不可交易**（末日无次日，语义更正确）；其余日期与其余掩码数值不变。仓库测试夹具含 `suspend.pkl`，全量回归不受影响（510 → 514 passed）
- **CLI 默认引擎**: `python cli.py run` 从已弃用的 V1 `BacktestEngine` 切换至 `core.factory.create_default_engine()`（V2）。V2 会执行 `FactorPipeline`，`--winsorize/--standardize/--fill/--neutralize` 参数自此真实生效（此前在 V1 下被忽略），默认结果随之变化；R-1 受控对比确认关闭因子处理后两引擎逐日净值完全一致（最大差异 0.000000）
- **README**: Quick Start 增加 `python examples/demo.py` 数据生成步骤；测试统计更新为 503 passed / 49 files
- **CODE_WIKI**: 数据格式表复权因子文件名改为 `stock_adj.pkl`
- **仓库卫生**: `memory/` 加入 `.gitignore` 并移出版本跟踪（本地 8 个 JSON 保留）；`conversation/` 7 个文件归档至 `docs/archive/conversation/`，`archive/` 忽略规则收窄为根级 `/archive/`
- **代码格式基线（TD-9 / P-003）**: `black` 全量重排 **126 个 Python 文件**（`core/`、`tests/`、`examples/`、`agents/`、`filter/`、`web/` 等 14 路径），纯格式变更——125 个文件经 AST 等价性机械验证（唯一差异为 docstring 行尾空白清理，`__doc__` 相关断言均为子串匹配不受影响），全量 `507 passed` 零回归；`black` 版本由 `>=23.0.0` 锁定为 `~=26.0`（black 官方同年度格式稳定性政策）；`black-check` 门禁命令由 `black --check core tests` 扩展为 `black --check .` 并**首次转绿**；新增 `.git-blame-ignore-revs` 保持历史 blame 可追溯（需本地 `git config blame.ignoreRevsFile .git-blame-ignore-revs` 启用）。**已知未覆盖**：CI 仍未加入格式校验步骤

### Removed
- **旧版过滤器**: 移除 `filter/universe.py`（生产零引用，`filter/__init__.py` 早已导出 clean 版）；2 个测试的导入迁移至 `filter.universe_filter_clean`
- **TD-3 Stage 3 / P-001 — 移除 Engine V1**: 删除 `core/engine.py`（724 行，`BacktestEngine`），删除仅诊断 V1 且 0 收集的 `tests/test_visual_trace.py` 与 `tests/test_visual_trace_v2.py`，删除 `tests/test_rebalance_exits.py` 中 g2/g3 两个 V1 专用用例（等价性证据保留在本文 R-1 受控对比与 `docs/DIFF_REPORT_2026-10-23.md`）；6 个 `examples/` 脚本迁移至 `core.factory.create_default_engine()`（`full_backtest_2020_2026_simple.py` 改为手工装配 `BacktestEngineV2`，并顺带修复其 5 个不存在模块的导入）；本地测试 509 → 507 passed、测试文件 50 → 48。**行为说明**：`examples/demo.py` 改由 V2 执行 `FactorPipeline`，合成数据的数值输出随之变化（无 golden 断言，属预期）

### Docs
- **台账校正**: `docs/PROGRESS.md` 快照刷新至 `df652f9`（Agg `509 passed`、black `75/5`、默认后端 Tk 失效读数）；关闭 U-004；`CHECKLIST_spec_runner_integration.md` §8 静态读码证据升级为 E3 @`df652f9`
- **进度台账**: 新增 `docs/PROGRESS.md` 与 `docs/dev-log/DEV-LOG-001-progress-baseline-20261104.md`，按 `Spec_Workflow` v1.7.1 登记 T1/T3 档位、证据等级与未决项；`docs/SPEC_STANDARD.md` 标注外部权威源
- **Spec 规则增补**: `docs/SPEC_STANDARD.md` v1.1.0 新增 §十一，规定设计/实施/验收/TDD 阶段的搜索工具调用与外部案例锚点（T1-T4 分级、降级链、反模式、环境态工具映射）
- **方案对比矩阵规则**: 同文件 §11.8 规定 Type-1 决策的 7 维矩阵（成本 / 收益 / 兼容 / 维护 / 升级潜力 / 短期 / 长期）逐格取证，每方案 ≥2 个外部 T1/T2 锚点覆盖 ≥3 维、每维度行至少一个外部锚点；前置声明时间口径与 Type-1/2 判定；接入 Phase 0 §3、Phase 0/1 Review 与 Design §2A；新增 `docs/dev-log/DEV-LOG-003-comparison-matrix-anchors-20261104.md`
- 技术债调研 Phase 0 归档（TD-1~TD-9）；H-1/H-2/H-3 修正状态回填；新增 TD-9 black 格式化基线

---

## [3.2.0] — 2026-06

### Added
- **Spec Standard**: 5-phase spec-driven development workflow (Research → Design → Implementation → Checklist → TDD → Archive)
- **Architecture Doc**: Authoritative `ARCHITECTURE.md` consolidating all architecture analysis
- **DevLog**: `DEVLOG.md` tracking all major changes since v3.0.0
- **Decision Records**: `DECISIONS.md` with 13 ADRs covering architecture, tooling, and process decisions
- **LLM Risk Doc**: `LLM_PREDICTION_AS_TRUTH_RISK.md` with 6-round discussion archive and P0-P5 action plan
- **UI Redesign**: Anthropic Terminal Fusion theme (deep charcoal, amber, terracotta, sage green)
- **Real A-share Validation**: 18 strict validation tests covering data/factor/engine/cost/metrics layers
- **Numba JIT**: @njit acceleration for Engine V3 (0.10ms/5000 stocks, 0.006s for 500×500)

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