# 开发日志 (Development Log)

> 最后更新: 2026-11-04 | 维护规则: 每次重要变更后追加一条记录

---

## 2026-11-04

### P0 台账校正（T3 轻批）
- **类型**: 文档（Layer-0）
- **文件**: `docs/PROGRESS.md`、`docs/CHECKLIST_spec_runner_integration.md`
- **内容**: HEAD 刷新至 `df652f9`；测试状态更新为 Agg `509 passed` / 默认后端 `1 failed + 3 errors`（均为 Tk）；black 基线 `75/5`；关闭 U-004；CHECKLIST §8 静态读码证据由 E2 升级为 E3 @`df652f9`
- **验证**: 5 步决策流 session `factorv3-p0-ledger-fix-20261104`（step-research/design/implement/verify/finalize）+ `replay`
- **关联**: `docs/PROGRESS.md` §1.1/§1.2/§2/§3.4/§4.4

### Spec_Runner 接入（T1 完整管线）
- **类型**: 工具接入（Layer-1）
- **文件**: `scripts/spec_runner_adapter.py`（新增）、`tests/test_spec_runner_adapter.py`（新增）、`docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_spec_runner_integration.md`（新增）、`docs/PROGRESS.md`
- **内容**: 复制官方 `spec_runner_adapter.py` v1.0，仅改配置区（`PREFIX=factorv3`、4 门禁 `probe/unit-tests/black-check/mypy-check`）；门禁 verdict / exit / stdout_tail 落入 `F:\Spec_Runner\sessions\factorv3-*.jsonl`
- **验证**: TDD RED `6 errors` → GREEN `6 passed`；全量 `509 passed`；门禁实测 pass / pass / fail(1) / fail(1)；`replay` 1 行与 2 行均 OK
- **已知基线**: `black-check` 75 files 待重排（TD-9）；`mypy-check` 168 errors（新登记 P-007 / U-006）
- **边界**: `F:\Spec_Runner\sessions/` 与其自动 commit 为框架设计内行为；未改其源码
- **ADD 审查发现（Step 10）**: 0 个 P1/P2；3 个 P3——F-1 black 报告走 stderr（命令追加 `2>&1`）、F-2 模板格式与项目 black 冲突（保持模板逐行一致，仅格式化新测试）、F-3 `mypy` 需 `--explicit-package-bases`
- **关联**: `docs/CHECKLIST_spec_runner_integration.md` §10/§11

### 进度基线落档（Spec_Workflow v1.7.1）
- **类型**: 文档（T3 轻批，Layer-0）
- **文件**: `docs/PROGRESS.md`（新建）、`docs/dev-log/DEV-LOG-001-progress-baseline-20261104.md`（新建）、`docs/SPEC_STANDARD.md`、`CHANGELOG.md`
- **内容**: 落档当前进度快照、P-001~P-006 待办与 U-001~U-004 四元未决项；按 SPEC_PROCESS v1.7.1 登记 T1/T3 档位；`SPEC_STANDARD.md` 标注外部权威源
- **验证**: `MPLBACKEND=Agg` 下 503 passed；默认后端 1 failed 由本机 Tk 缺 `ttk/xpTheme.tcl` 引起
- **关联**: `docs/PROGRESS.md`, `docs/dev-log/DEV-LOG-001-progress-baseline-20261104.md`, `docs/RESEARCH_tech_debt_cleanup.md`

### Spec 搜索锚点规则增补
- **类型**: 文档（T3 轻批，Layer-0）
- **文件**: `docs/SPEC_STANDARD.md`（v1.1.0 §十一）、`docs/dev-log/DEV-LOG-002-search-anchor-rules-20261104.md`
- **内容**: 设计/实施/验收/TDD 四阶段加入搜索工具调用与外部案例锚点硬约束；T1-T4 分级、降级链、反模式、环境态工具映射；“不懂不要乱写”硬约束；外部参考仓只读
- **验证**: 外部 `SPEC_PROCESS.md` L116-L196 @ `bf83e48` 逐条对照；`git -C F:\Spec_Workflow status --short` 空输出；`MPLBACKEND=Agg` 下 503 passed

### 方案对比 7 维矩阵与外部锚点
- **类型**: 文档（T3 轻批，Layer-0）
- **文件**: `docs/SPEC_STANDARD.md`（§11.8）、`docs/dev-log/DEV-LOG-003-comparison-matrix-anchors-20261104.md`
- **内容**: Type-1 决策的 7 维矩阵（成本 / 收益 / 兼容 / 维护 / 升级潜力 / 短期 / 长期）逐格取证；每方案 ≥2 个外部 T1/T2 锚点覆盖 ≥3 维、每维度行至少一个外部锚点；前置声明时间口径与 Type-1/2 判定；收敛出口与被拒代价；接入 Phase 0 §3、Phase 0/1 Review、Design §2A
- **验证**: 外部 `DECISION_MATRIX_TEMPLATE.md` v1.0 L34-L42 @ `bf83e48` 逐行对照；外部 `SPEC_PROCESS.md` L431-L467 @ `bf83e48`；`MPLBACKEND=Agg` + Python312 下 503 passed
- **关联**: `docs/PROGRESS.md` U-005（解释器漂移）, `docs/SPEC_STANDARD.md` §11.8

## 2026-10-23

### TD-3 Stage 2：CLI 切换至 V2 引擎
- **类型**: 重构（行为变更）
- **文件**: `cli.py`
- **内容**: `cmd_run` 由 `BacktestEngine`（V1，已弃用）改为 `core.factory.create_default_engine()`（V2）；V2 执行 `FactorPipeline`，CLI 的 `--winsorize/--standardize/--fill/--neutralize` 参数自此真实生效
- **验证**: R-1 基准 V1 +16.79%（终值 11,679,182）→ V2 +6.77%（终值 10,676,608）；关闭因子处理的受控对比下两引擎 500 日净值逐日一致（最大差异 0.000000）；全量 503 passed
- **关联**: TD-3, `docs/RESEARCH_tech_debt_cleanup.md`

### 技术债调研归档（Phase 0）
- **类型**: 文档
- **文件**: `docs/RESEARCH_tech_debt_cleanup.md`（归档）、`docs/ARCHITECTURE.md`（修正）
- **内容**: H-1 Factor_DB "DuckDB" → "JSON 元数据 + Parquet（DuckDB 规划）"；H-2 Data V3 "多源 AKShare/YFinance" → "Qlib 风格向量化加载器"；H-3 Config V2 "✅活跃/推荐" → "⚠️冻结（零生产引用）"；修正状态回填至 TD-2/TD-4/TD-8，P0-3 标记完成
- **证据**: `factor_library/database.py` 使用 json + parquet；全仓代码无 `import duckdb`；`data_v3.py:1-4` 自述 Qlib 风格；config_v2 仅测试引用
- **关联**: RESEARCH_tech_debt_cleanup.md, ARCHITECTURE.md, CHANGELOG.md
- **备注**: P0-1/P0-2/P0-3 均已完成；Phase 1 设计未启动

### TD-6/TD-7 仓库卫生清理
- **类型**: 重构（仓库卫生）
- **文件**: `.gitignore`、`memory/`、`conversation/` → `docs/archive/conversation/`
- **内容**: `memory/` 加入 gitignore 并 `git rm -r --cached` 移出版本跟踪（8 个本地 JSON 保留）；`conversation/` 7 个文件归档，`archive/` 忽略规则收窄为根级 `/archive/`
- **验证**: grep 无代码路径引用；全量测试 503 passed
- **关联**: TD-6, TD-7

### demo_data 复权文件与 README 修复
- **类型**: 修复
- **文件**: `examples/demo.py`, `README.md`, `docs/CODE_WIKI.md`
- **内容**: 生成器输出 `stock_adj.pkl`，修复旧布局导入（`core.config`/`core.engine`）与硬编码 `D:/` 路径；README Quick Start 增加 demo 数据生成步骤；测试统计 245 → 503
- **验证**: CLI 默认 forward 复权 63 个交易日跑通；`examples/demo.py` 端到端跑通，重生成数据哈希一致

### TD-5 移除旧版过滤器
- **类型**: 重构
- **文件**: `filter/universe.py`（删除）、`tests/test_pending_order_improvements.py`、`tests/test_v3_engine_integration.py`
- **内容**: 2 处测试导入迁移至 `filter.universe_filter_clean`；删除旧版过滤器。`filter/__init__.py` 原本已导出 clean 版，生产路径无变化
- **验证**: 迁移后两测试 12 passed；全量 503 passed；grep 无生产引用残留
- **关联**: TD-5

### CRITICAL 再平衡修复（T1–T8）
- **类型**: 修复（行为变更）
- **文件**: `core/target_positions.py`（新建）、`core/engine.py`、`core/engine_v2.py`、`tests/test_rebalance_exits.py`（新建）、`tests/test_p0_engine_integration.py`、`docs/DESIGN/IMPL/CHECKLIST_critical_rebalance_fix.md`
- **根因**: 优化器只返回 top-N，`target_positions` 不含调出标的 → 永不生成卖单；pending 队列路径无资金校验；`Position.execute_trade` 不维护 `market_value`，导致开盘成交后组合价值虚高
- **修复**: 共享纯函数构建目标持仓（权重 ∪ 持仓，含清仓项）、SELL 先于 BUY、以价格重算组合价值、新增 `unclosed_positions` 诊断
- **验证**: 14 个新增测试；全量 503 passed；真实数据 500 日 `unclosed_positions={}`，年化 13.92%；N=5000 目标构建 16.55 ms
- **决策**: Q1 无条件修复不设开关；Q3 CLI 切换另立 TD-3；Q4 无修复前基准，以黄金测试验收
- **关联**: DESIGN/IMPL/CHECKLIST_critical_rebalance_fix.md, CHANGELOG.md

---

## 2026-06-20

### Spec 驱动开发规范建立
- **类型**: 基础设施
- **文件**: `docs/SPEC_STANDARD.md` (新建)
- **内容**: 建立 5 阶段 Spec 开发流程 (调研 → 设计 → 实施 → 清单 → TDD → 归档)
- **影响**: 全项目，所有非 trivial 变更必须遵循此流程
- **关联**: SPEC_STANDARD.md

### 架构文档统一
- **类型**: 文档
- **文件**: `docs/ARCHITECTURE.md` (新建)
- **内容**: 整合 `ARCHITECTURE_ANALYSIS.md` + `CODE_WIKI.md` + `REFACTORING_SUMMARY.md` 为权威架构文档
- **影响**: 旧架构文档标记为历史存档
- **关联**: ARCHITECTURE.md

### 开发日志与决策记录建立
- **类型**: 基础设施
- **文件**: `docs/DEVLOG.md` (新建), `docs/DECISIONS.md` (新建)
- **内容**: 建立持续跟踪机制
- **关联**: DEVLOG.md, DECISIONS.md

### LLM 预测偏差风险讨论归档
- **类型**: 研究
- **文件**: `docs/LLM_PREDICTION_AS_TRUTH_RISK.md` (更新)
- **内容**: 新增第九章"讨论过程记录"，完整记录六轮迭代讨论的推理链条
- **影响**: 为 P0-P5 行动计划提供完整上下文
- **关联**: FormalProbability DSL 分析

### UI 重设计 (Anthropic Terminal 主题)
- **类型**: 功能
- **文件**: `web/index.html`, `web/cli.html` (修改)
- **内容**: 切换到 Financial Terminal Fusion 配色 (深炭灰 `#0f0f0e`, 琥珀 `#e6a817`, 陶土 `#d97757`, 鼠尾草绿 `#6ab0a3`)
- **关联**: huashu-design 技能

---

## 2026-06-06

### 真实 A 股数据严格验证
- **类型**: 测试
- **文件**: `tests/test_real_ashare_strict_validation.py` (新建)
- **内容**: 18 个严格验证测试，覆盖数据层/因子层/引擎层/成本层/绩效层
- **结果**: 18/18 通过，全量回归 489 测试通过
- **修复**: OHLC 一致性测试、组合价值核对、信号-持仓映射
- **关联**: commit `c7a0f29`

### LLM 预测偏差风险文档
- **类型**: 文档
- **文件**: `docs/LLM_PREDICTION_AS_TRUTH_RISK.md` (新建)
- **内容**: 问题定义、学术文献追踪、风险映射、P0-P5 行动计划
- **关联**: FormalProbability DSL 分析

---

## 2026-06-05

### Numba JIT 加速
- **类型**: 性能
- **文件**: `core/engine_v3_vector.py` (修改), `tests/test_numba_jit_performance.py` (新建)
- **内容**: `_rebalance_kernel` @njit (0.10ms/5000股), `_metrics_kernel` @njit (0.014ms/2500天)
- **结果**: 270 测试通过, V3 引擎 500股×500天 = 0.006s
- **关联**: `conversation/2026-06-05-Numba-JIT加速总结.md`

---

## 2026-06-04

### P0: README + CHANGELOG + Docker
- **类型**: 基础设施
- **文件**: `README.md` (重写), `CHANGELOG.md` (新建), `Dockerfile` (新建), `docker-compose.yml` (新建)
- **内容**: README 对标 TradingAgents/Qlib 风格，CHANGELOG 覆盖 v3.0-v3.2，Docker 多阶段构建 + 3 profile
- **结果**: 245 测试通过

### P1: 项目元数据
- **类型**: 基础设施
- **文件**: `CHANGELOG.md`, `Dockerfile`, `docker-compose.yml`
- **内容**: 版本变更记录 + Docker 部署

### P2: CLI + Streamlit Dashboard
- **类型**: 功能
- **文件**: `cli.py` (新建), `web/streamlit_app/` (新建 8 文件)
- **内容**: CLI 5 子命令 (run/test/analyze/info/dashboard), Streamlit 5 页面板
- **关联**: `conversation/2026-06-04-P0-P2-执行总结.md`

---

## 2026-05 (v3.1.0)

### EventLog + Guard Pipeline + Plugin System
- **类型**: 架构
- **文件**: `core/event_log.py`, `core/guard_pipeline.py`, `core/engine_plugins.py`
- **内容**: JSONL 持久化 + 环形缓冲, 事前安全检查链, Registry + Factory + 自动注册

### Style Reflection Engine
- **类型**: 功能
- **文件**: `agents/style_reflection_engine.py`
- **内容**: 风格化反思 + 锚定评估

### Distillation Isolation Audit
- **类型**: 功能
- **文件**: `tools/distillation_audit.py`
- **内容**: 跨 Agent 知识蒸馏安全隔离

### DI + Pydantic Config
- **类型**: 架构
- **文件**: `core/engine_v2.py`, `core/config_v2.py`
- **内容**: 依赖注入支持 Mock 测试, Pydantic schema 验证 + 热重载

---

## 2026-01 (v3.0.0)

### 初始重构
- **类型**: 架构
- **来源**: Backtest_Opus_2.0
- **内容**: 模块化架构、Config-driven 设计、Factor Pipeline、Portfolio Optimizer (4种)、Execution Simulator、Multi-Agent 系统、Walk-Forward 分析、Brinson 归因、Global Contagion、五维风控、Stock Filter (10种)、Factor_DB、Batch Backtest、Strategy Evaluation