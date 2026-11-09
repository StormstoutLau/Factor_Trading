# 关键决策记录 (Architecture Decision Records)

> 格式: ADR (Architecture Decision Record) | 最后更新: 2026-11-10

---

## ADR-001: 选择 DuckDB 作为因子数据库

- **日期**: 2026-01
- **状态**: ✅ 已采纳
- **背景**: 需要本地存储多源因子数据（价格/因子/宏观/新闻/另类），避免每次回测重新计算
- **方案对比**:
  - SQLite: 简单但 OLAP 性能差，列式操作慢
  - DuckDB: 嵌入式列式数据库，OLAP 性能优秀，支持 Parquet/CSV 直接查询
  - PostgreSQL: 功能强大但需要外部服务，部署复杂
- **决策**: DuckDB
- **影响**: `factor_library/database.py` 骨架已建，待完成写入/查询 CLI

---

## ADR-002: 三引擎并行策略

- **日期**: 2026-05
- **状态**: ✅ 已采纳
- **背景**: 需要同时支持精确策略回测和快速因子筛选
- **方案对比**:
  - 单一引擎: 维护简单但无法同时满足两个不同场景
  - 双引擎 (V2 + V3): 各司其职，V2 精确模拟，V3 向量化快速验证
- **决策**: V1 弃用，V2 作为主引擎，V3 作为预筛选工具
- **影响**: `core/engine_v2.py` (活跃), `core/engine_v3_vector.py` (活跃), `core/engine.py` (已于 P-001 移除)

---

## ADR-003: 依赖注入架构

- **日期**: 2026-05
- **状态**: ✅ 已采纳
- **背景**: V1 引擎中 DataManager 和 UniverseFilter 直接实例化，导致高耦合，无法独立测试
- **方案对比**:
  - 保持 V1 架构: 简单但测试困难
  - 依赖注入: 所有组件通过接口交互，支持 Mock 测试和组件替换
- **决策**: 依赖注入，通过 `core/interfaces.py` 定义全部 Protocol
- **影响**: Engine V2 支持 Mock 测试，所有核心组件可独立替换

---

## ADR-004: Pydantic 配置验证

- **日期**: 2026-05
- **状态**: ✅ 已采纳
- **背景**: V1 的 dataclass 配置无验证，错误配置在运行时才暴露
- **方案对比**:
  - 保持 dataclass: 零学习成本但无验证
  - Pydantic v2: 类型约束 + 范围限制 + JSON 序列化 + 热重载
- **决策**: Pydantic v2，保留 V1 dataclass 向后兼容
- **影响**: `core/config_v2.py` 提供完整验证，Engine V2 仍使用 V1 配置

---

## ADR-005: T+1 执行策略

- **日期**: 2026-05
- **状态**: ✅ 已采纳
- **背景**: A 股市场 T+1 交易机制，需要正确模拟信号→订单→成交的延迟
- **决策**: 通过 `ExecutionPolicy` + `SignalTranslator` + `PendingOrderQueue` 实现
- **影响**: `core/execution_policy.py`, `core/pending.py`

---

## ADR-006: Walk-Forward 训练/验证/测试分离

- **日期**: 2026-05
- **状态**: ✅ 已采纳
- **背景**: 需要防止数据窥探，正确评估策略样本外表现
- **决策**: Rolling/Expanding 窗口 + Purge Gap + Agent 蒸馏隔离
- **影响**: `core/walk_forward.py`, `core/walk_forward_engine.py`

---

## ADR-007: Numba JIT 加速 Engine V3

- **日期**: 2026-06-05
- **状态**: ✅ 已采纳
- **背景**: Engine V3 的再平衡和指标计算在纯 NumPy 上仍有优化空间
- **决策**: 添加 @njit 装饰器，保留 numba 不可用时的 fallback
- **结果**: 再平衡 0.10ms/5000股, 指标 0.014ms/2500天, 500股×500天 = 0.006s
- **影响**: `core/engine_v3_vector.py`, 引入 numba 可选依赖

---

## ADR-008: 根目录桥接文件移除

- **日期**: 2026-06-04
- **状态**: ✅ 已采纳
- **背景**: 18 个根目录文件仅是 `from core.X import Y` 的桥接，增加维护负担
- **决策**: 全部移除，统一使用 `from core.xxx import YYY`
- **影响**: 28+ 文件更新导入路径，245 测试通过

---

## ADR-009: LLM 预测偏差校正 (DSL 方案)

- **日期**: 2026-06-06
- **状态**: 📋 已规划 (P0-P5 待执行)
- **背景**: LLM 预测值直接当真实值输入回测引擎，导致不可逆推断偏差 (Theorem 3)
- **决策**: 采用 DSL 的 `designAdjustedOutcome` 公式，1-5% 人工标注 + IPW 校正全量预测
- **行动计划**: P0 JudgeCalibration → P1 因子协方差调整 → P2 ClusteredVariance → P3 引擎输入校正 → P4 贝叶斯扩展 → P5 Layer 3 一致性
- **关联**: `docs/LLM_PREDICTION_AS_TRUTH_RISK.md`

---

## ADR-010: Layer 3 标注一致性验证用规则引擎

- **日期**: 2026-06-06 (四轮讨论后收敛)
- **状态**: ✅ 已决策
- **背景**: 需要在规则引擎和 Lean4 形式化验证之间选择 Layer 3 标注一致性检查工具
- **决策**: 当前阶段用规则引擎（规则 < 50 条，规则在演化），迁移条件：> 6 个月 + > 10000 条标注 + 规则稳定 > 100 条 → 评估 Lean4 迁移
- **性质**: 可逆决策，规则引擎先跑，稳定后再评估
- **关联**: `docs/LLM_PREDICTION_AS_TRUTH_RISK.md` 第四章

---

## ADR-011: Anthropic Terminal 主题

- **日期**: 2026-06-20
- **状态**: ✅ 已采纳
- **背景**: Web UI 需要更专业的金融终端风格
- **决策**: 采用 Financial Terminal Fusion 配色 (深炭灰 `#0f0f0e`, 琥珀 `#e6a817`, 陶土 `#d97757`, 鼠尾草绿 `#6ab0a3`)
- **影响**: `web/index.html`, `web/cli.html`

---

## ADR-012: Spec 驱动开发流程

- **日期**: 2026-06-20
- **状态**: ✅ 已采纳
- **背景**: 项目复杂度和模块数量增长，需要标准化的开发流程确保质量
- **决策**: 5 阶段 Spec 流程 (调研 → 设计 → 实施 → 清单 → TDD → 归档)，每阶段 Review 闸门
- **影响**: 全项目，`docs/SPEC_STANDARD.md` 为权威规范
- **豁免**: Bug 修复 (< 50 行)、类型标注补充、测试补充、文档修正可跳过

---

## ADR-013: 文档体系重构

- **日期**: 2026-06-20
- **状态**: ✅ 已采纳
- **背景**: 10 份 docs/ 文档分散、部分过时、存在矛盾
- **决策**: 建立 4 份核心文档体系 (ARCHITECTURE.md + DEVLOG.md + DECISIONS.md + SPEC_STANDARD.md)，旧文档标记为历史存档
- **影响**: 文档索引见 `ARCHITECTURE.md` 第十章

---

## ADR-016: TD-1.2 轻量子包化（移除隐式重导出）

- **日期**: 2026-10-24 实施；2026-11-09 补录（P-006 / U-002）
- **状态**: ✅ 已采纳
- **背景**: 根 `__init__.py` 与 `core/__init__.py` 此前隐式重导出核心模块，`import` 即触发 cvxpy/ta/tushare/akshare 等重依赖链；pyproject 亦未声明子包。
- **决策**: ① 两个 `__init__.py` 改为轻量（仅注释与版本元数据），移除全部隐式重导出，改为用户显式导入（如 `from core.config import BacktestConfig`）；② pyproject 最小子包化——仅声明实际依赖的 `Factor_Trading_v3_0` 与 `Factor_Trading_v3_0.core`，其他子包按需追加。
- **影响**: 全项目导入约定（显式导入）；实施提交 `2848331`（全量 503 passed，仓内无 `from core import ...` 隐式依赖）。编号沿用代码注释既有引用（`__init__.py:3`、`core/__init__.py:3`、`pyproject.toml:79`）；ADR-014/015 未使用（历史编号跳空），不存在对应决策。

---

## ADR-017: 复权口径校正与三口径分离

- **日期**: 2026-11-10（登记；P-012 Step 9 已实施）
- **状态**: ✅ 已实施
- **背景**: `DataManager.get_adj_price` 的 `forward` 分支实现为 `price × adj_factor`、`backward` 分支实现为 `price × adj_factor / adj_factor.iloc[-1]`（`core/data.py:444-456` @`05af52f`）；按 Tushare 官方复权公式（文献 15）与 A7 定义，二者语义**恰好互换**——`forward` 实为后复权（hfq）、`backward` 实为前复权（qfq）。同时 `BacktestConfig.adjustment_type`（默认 `forward`）被引擎用于**全部成交与估值价格**（`core/engine_v2.py:346/391/438/440/529/608/669/757`）与**收益计算**（`core/data.py:403-407`），而该 `returns` 又被涨跌停掩码复用（`filter/universe_filter_clean.py:154-182`）。三个后果：①成交/费用/手数在复权价格体系下失真（P8）；②命名与语义相反，调用方无法凭名称判断（P7）；③一个开关同时改变成交、绩效与涨跌停三处语义（P21 口径耦合）。
- **方案对比**:
  - A 仅文档声明：零改动，但成交仍用复权价、命名仍误导 → 否决
  - B 仅重命名：名称正确，但成交价与口径耦合未解 → 不完整
  - C 命名校正 + 三口径分离 + 成交/估值用 raw + 兼容开关 → **采纳**
- **决策**:
  1. **命名校正**：`forward → hfq`（`price × adj`）、`backward → qfq`（`price × adj / adj[-1]`）、`none → raw`；旧名保留 **≥2 个 minor**，发 `DeprecationWarning`（弃用期口径对齐 PDEP-17）
  2. **口径分离**：`trade_price_mode="raw"`（成交/估值/费用/手数）、`signal_price_mode="hfq"`（信号/因子）、`return_price_mode="hfq"`（绩效）、`limit_price_mode="hfq"`（涨跌停判定）
  3. 涨跌停**价**用不复权价；涨跌停**判定**用复权收益（除权日已对齐除权参考价）
     - **2026-11-10 设计补充（DESIGN_p012 D4）**：判定改为**价格法**——`limit_up_price = 除权参考价 × (1+ratio)`，与当日开盘价比较。此时「禁止 raw」只针对**不复权收益**，不针对 raw 价格本身；`adj_factor` 仅用于还原除权参考价。
  4. `legacy_adjustment=False` 为默认新口径；`True` 恢复「复权价成交 + 旧收益口径」旧路径，且输出须与冻结基线 `rtol=0` 逐值相等
  5. 每次行为变更单独批次 + `change_report.json` 六层归因，残差 < 1e-8
- **明确不做**: 不将 `return_price_mode` / `limit_price_mode` 设为 `raw`——除权日会在 ST 5% 等窄阈值下产生假涨跌停（见 RESEARCH §11.3 反例测试⑤）
- **影响**: `core/data.py`（`get_adj_price` / `_calculate_returns`）、`core/engine_v2.py`（成交与估值取价）、`core/config.py` / `core/config_v2.py`（口径字段）、`filter/universe_filter_clean.py`（涨跌停掩码口径）、回测报告字段（`adjustment_mode` / `legacy_adjustment`）、README / CODE_WIKI / CHANGELOG、基线刷新
- **可逆性**: 高——旧名别名 + `legacy_adjustment` 开关，可整体回退
- **实施**: P-012 Step 9（2026-11-10）——`a5ae5cc`(B1 观测网) → `4e2ab0b`(B2 规则表) → `ad40490`(B3a 命名) → `79c4dea`(B3b 口径分离) → `3717246`(B4 价格法) → `94018f2`(B5 退市) → `6e5eeba`(B6 接口治理)；全量 **550 passed**，四份行为 `change_report.json` 满足 `residual < 1e-8` 且 `attribution_complete=true`；`legacy_adjustment=True` 与改前基线 `rtol=0` 逐值相等
- **关联**: `docs/RESEARCH_bias_interface.md` §11.3 / §12.2（P-012 U-3 / U-7）；ADR-005（T+1 执行策略，与本决策不冲突）

---

## 决策状态说明

| 状态 | 含义 |
|------|------|
| ✅ 已采纳 | 已实施并生效 |
| 📋 已规划 | 决策已做出，尚未实施 |
| ⚠️ 已废弃 | 被后续决策替代 |
| 🔄 审查中 | 正在重新评估 |