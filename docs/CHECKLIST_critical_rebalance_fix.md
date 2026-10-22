# CRITICAL 再平衡修复 · 审查验收清单

> **文档编号**: CHECKLIST_critical_rebalance_fix
> **阶段**: Phase 3 - 验收
> **日期**: 2026-10-23
> **上游文档**: [DESIGN_critical_rebalance_fix.md](DESIGN_critical_rebalance_fix.md) · [IMPL_critical_rebalance_fix.md](IMPL_critical_rebalance_fix.md)
> **状态**: 已完成（2026-10-23 归档）

---

## 1. 功能完整性

- [x] 新增 `core/target_positions.py`：`TargetPosition`、`build_target_positions`、`compute_portfolio_value` 均已实现
- [x] 目标持仓覆盖 `target_weights ∪ current_positions`，调出标的以 `target_quantity=0` / `is_exit=True` 出现
- [x] 调出标的即使无有效价格也生成清仓目标（清仓数量由当前持仓决定，成交价在次日开盘获取）
- [x] V1/V2 两引擎共用同一构建函数，目标持仓与订单生成逻辑不再分叉
- [x] 同一调仓日订单顺序为 **SELL 先于 BUY**
- [x] `results` 新增 `unclosed_positions` 诊断字段（强平前快照）
- [x] 异常路径：`total_value` 非有限/非正、负权重 → `ValueError`；持仓无价格 → 维持现状并告警；空仓无价格 → 跳过；调仓日价格缺失 → 告警并跳过本次调仓
- [x] 未新增配置开关（Q1：正确性缺陷无条件生效）
- [x] 新模块不 import `core.config` / `core.tracker` / `core.pending` / `core.engine*`（仅 `logging` / `math` / `dataclasses` / `typing` / `pandas`）

## 2. 测试完整性

- [x] 单元测试 U1–U9 覆盖目标持仓契约（`tests/test_rebalance_exits.py`）
- [x] 黄金集成 G1–G5：调出清仓、部分减仓、V1/V2 目标一致、现金非负、SELL 优先
- [x] 边界条件：空目标且无价格、持仓无价格、非法输入、卖单被掩码阻断（U8）
- [x] 新增测试全部通过：**14 passed**
- [x] 新模块覆盖率：**96%**（68 statements / 3 missed：91 超权重告警、134 `round_lot=False`、175 零持仓跳过）
- [x] 全量回归：**503 passed**（49 个测试文件）
- [x] 真实数据冒烟：500 日 / 200 股，`unclosed_positions={}`，年化 13.92%

## 3. 性能验收

- [x] 目标构建为纯内存计算，无磁盘/网络 I/O
- [x] 调仓日价格只读取一次，不再逐股查询
- [x] 复杂度 O(N log N)（`sorted` 并集），N = 目标权重 ∪ 当前持仓
- [x] 微基准：N=5000（含 2500 持仓）**16.55 ms/run**（20 次均值）

## 4. 文档一致性

- [x] `build_target_positions` 签名与 DESIGN §4.2.1 / IMPL §4 一致（含 `round_lot` / `lot_size` / `value_buffer`）
- [x] `compute_portfolio_value` 签名与 DESIGN §4.2.1 一致（价格优先、`market_values` 兜底）
- [x] 测试编号 U1–U9 / G1–G5 与 DESIGN §9 / IMPL §5 对齐
- [x] `unclosed_positions` 字段与 DESIGN Q2 / IMPL §4.4 一致
- [x] 未新增第三方依赖，`pyproject.toml` 无需变更
- [x] CHANGELOG / DEVLOG 记录本次行为性变更（归档步骤执行）

## 5. 兼容性

- [x] `results` 仅新增键，未删除或重命名既有键
- [x] V1/V2 目标持仓逐项一致（G3）
- [x] 复用 `cfg.optimizer.round_lot`，无新配置项
- [x] 行为变更已识别：调出标的现在会产生卖单，且卖单先于买单
- [x] CLI 默认路径（V1 引擎）同步生效，无需切换引擎
- [x] CHANGELOG 标注行为变更（归档步骤执行）

## 6. 代码质量

- [x] 新模块 `black --check` 通过；遗留 `engine.py` / `engine_v2.py` 受 TD-9 基线影响未整体重排
- [x] `mypy`：新模块零错误；两引擎错误数 **103 = HEAD 基线 103**（新增快照方法已加 `None` 守卫）
- [x] 新模块与新增测试无 `TODO` / `FIXME` / `print()`
- [x] 日志级别：异常/降级路径 `warning`，正常跳过 `debug`
- [x] 新模块公开 API 类型标注完整（含 `TargetPosition` 字段）

## 7. 验证记录

| 项 | 命令 | 结果 |
|----|------|------|
| 新增测试 | `pytest tests/test_rebalance_exits.py -q` | 14 passed in 7.26s |
| 全量回归 | `pytest tests -q` | 503 passed, 82 warnings in 30.45s |
| 覆盖率 | `pytest tests/test_rebalance_exits.py --cov=core.target_positions` | 96% (68 stmts / 3 missed) |
| 类型检查 | `mypy core/engine.py core/engine_v2.py core/target_positions.py --explicit-package-bases --no-incremental` | 103 errors = HEAD 基线 103 |
| 格式检查 | `black --check core/target_positions.py tests/test_rebalance_exits.py` | 2 files unchanged |
| 微基准 | `build_target_positions` N=5000 × 20 次 | 16.55 ms/run |
| CLI 冒烟 | `python cli.py run --start-date 2022-01-04 --end-date 2022-03-31` | +5.27%，期末 1,052,660 |
| 真实数据冒烟 | 500 日 / 200 股 | `unclosed_positions={}`，年化 13.92% |

说明：`mypy` 的 103 个错误均为引擎既有的 `Optional` 属性访问问题，CI 以 `|| true` 非阻断运行；本次未新增错误。

## 8. 归档记录

- [x] `CHANGELOG.md` 增加 CRITICAL 修复条目（含行为变更说明）
- [x] `DEVLOG.md` 记录修复内容、验证结果与决策（Q1–Q4）
- [x] DESIGN / IMPL 文档标记“已完成”
- [x] 代码、测试、设计/实施/清单文档合并为单一提交

---

**验收结论**：功能、测试、性能、文档一致性、兼容性、代码质量六项均满足；已于 2026-10-23 完成归档。
