# 关键决策记录 (Architecture Decision Records)

> 格式: ADR (Architecture Decision Record) | 最后更新: 2026-06-20

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
- **影响**: `core/engine_v2.py` (活跃), `core/engine_v3_vector.py` (活跃), `core/engine.py` (弃用)

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

## 决策状态说明

| 状态 | 含义 |
|------|------|
| ✅ 已采纳 | 已实施并生效 |
| 📋 已规划 | 决策已做出，尚未实施 |
| ⚠️ 已废弃 | 被后续决策替代 |
| 🔄 审查中 | 正在重新评估 |