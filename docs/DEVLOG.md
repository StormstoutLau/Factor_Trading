# 开发日志 (Development Log)

> 最后更新: 2026-10-23 | 维护规则: 每次重要变更后追加一条记录

---

## 2026-10-23

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