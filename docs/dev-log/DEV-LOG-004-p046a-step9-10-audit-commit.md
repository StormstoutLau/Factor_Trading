# DEV-LOG-004：P-046a Step 9-10（实施 + 终审提交）

- **日期**: 2026-11-20
- **批次**: P-046a（组合优化语义修复：约束不变量 + 协方差单一入口，T1 判档）
- **作者/复审**: 实现 DeepSeek-V4.1-Flash（Step 1-9）；终审 GLM-5.3-Flash（Step 10，异构合规）

## 做了什么

1. **Step 9 实施（T1-T7）**: `core/portfolio.py` 全量重写（`InfeasibleConstraintError` / `OptimizationResult` / `_precheck` 四类分型 / `_scale_to_budget` 二分投影 / `estimate_cov` sklearn LedoitWolf 单一入口 / 四优化器 `optimize_with_diagnostics`）；`config.py` `__post_init__` 四条校验；`diagnostics.py` 三件套（`detail` / `record_detail` / config 分流）；`engine_v2.py` Σ 只算一次注入 optimizer+overlay。
2. **测试**: 新建 3 模块 55 例（constraints 38 / cov 10 / engine 7）；修 2 处既有测试（`test_p031` 补 `max_weight=1.0`、`test_p048` vol 腿改 sklearn LW 复算——均语义修正，无宽松断言）。
3. **门禁**: 987 passed（932+55）/ golden 18 零重录 / mypy 111·0 / black 152·221 / `uv lock --check` 0 / AST core 30·外 26。
4. **Step 10 终审**: ADD 四阶段 + 取证矩阵（E1/E2/E3/E4）；**P1=0 / P2=0 / P3=3 / INFO=1**（zero_vol message、退化分支 warning、codes 参数语义、INFO×1），全部登记归 P-046b。
5. **提交**: 原子提交 `15f608a`（14 files，+3263/−240）；终审文档第二提交。

## 决策依据

- 四类不可行语义 = 用户裁决（U1-A→B2 留现金 / U1-B→B1 抛错 / U1-C 既有 / U1-D 配置期校验）；
- 诊断载体 = D-R2（新方法 + 结果对象，`optimize` 薄包装签名冻结）；
- Σ 单一入口 = 选项 i（engine 统一注入 optimizer 与 overlay）。

## 遇到的问题

- collect 41→55 偏移（F-S9-P046-1）：以实测为准，计划值保留；
- AST 基线「core 外 22」不可复现（F-S9-P046-2）：本批 core 外零 diff，口径固化归 P-046b 前置；
- E2 对抗脚本首轮 2 例口径错误（U1-B 容差阈值、空集 vs 无数据）：修正后 21/21，原样记录于 RESEARCH §21.2。

## 下一步

- P-046a 收口；push/CI 待用户另行授权；
- P-046b 启动前：裁决 U-P046-12（HRP 一手原文）、固化 AST 扫描口径、消化 F-S10-P046-1..3；
- `_apply_constraints_legacy` 删除条件见 PROGRESS §3.55.2（P-046b 后评估）。
