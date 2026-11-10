# CHECKLIST：P-015 外部框架对拍校准（VectorBT ↔ V3 首例）

> **批次**: P-015 · T1
> **上游**: [IMPL_p015_external_benchmark.md](IMPL_p015_external_benchmark.md)（T-1~T-4 / V1-V10）；[DESIGN_p015_external_benchmark.md](DESIGN_p015_external_benchmark.md)（I1-I5 / D1-D6）
> **实测列规则（RULE-1）**: 「实测」列只允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` 三态，禁止无证据勾选
> **状态**: Step 7 完稿；Step 8 一致性 Review 见 §8；Step 10 审计见 §9

---

## 1. 验收项总表

### A 组：venv 与环境（3 项）

| ID | 验收项 | DoR | DoD | 实测 |
|----|--------|-----|-----|------|
| A-1 | `.venv-vbt` 建立且 vectorbt 可导入 | T-1.1/T-1.2 执行 | venv 内 `python -c "import vectorbt; print(vectorbt.__version__)"` 输出 `1.2.0`（exit 0） | [待 Step 9] |
| A-2 | requirements 钉版回填（F2） | T-1.3 执行 | `requirements-vectorbt.txt` 含 `vectorbt==1.2.0` 与传递依赖实测版本；`pip freeze` 可重放 | [待 Step 9] |
| A-3 | venv 不入 git | T-1.5 执行 | `.gitignore` 含 `.venv-vbt/`；`git status --short` 无 venv 条目 | [待 Step 9] |

### B 组：三脚本与数据交换（4 项）

| ID | 验收项 | DoR | DoD | 实测 |
|----|--------|-----|-----|------|
| B-1 | export_case 逐 case 导出成功 | T-2.1 完成 | B1-B5 五个 case 目录五件套齐全，exit 0 | [待 Step 9] |
| B-2 | run_vectorbt 逐 case 运行成功（venv） | T-1 + T-2.2 完成 | vbt_results/vbt_orders 落盘，exit 0 | [待 Step 9] |
| B-3 | 跨 pandas CSV 往返自检通过（U-P015-2） | B-2 运行 | run_vectorbt 启动自检读数「逐元素一致」落 stdout | [待 Step 9] |
| B-4 | verify_p015 全 case exit 0 | B-1~B-3 完成 | 五 case 断言全过，逐条读数输出 | [待 Step 9] |

### C 组：恒等式（5 项，对应 I1-I5）

| ID | 验收项 | 判据（可证伪恒等式） | 实测 |
|----|--------|----------------------|------|
| C-1 | I1 记账恒等（B1） | `qty_v3==qty_vbt==qty_spec`（rtol=1e-12）；`pv==1e7`（money_atol=1e-6） | [待 Step 9] |
| C-2 | I2 规模语义差分（B2） | I2a/I2b 各侧对规格零残差；I2c 差 == 闭式（rtol=1e-12） | [待 Step 9] |
| C-3 | I3 费用恒等（B3） | 两侧费用 == `Σ\|trade\|×P×rate`；首日 pv == `1e7×(1−rate)`（money_atol=1e-6） | [待 Step 9] |
| C-4 | I4 多期逐日恒等（B4） | T=6 逐日 qty/cash/pv 三量恒等（rtol=1e-12） | [待 Step 9] |
| C-5 | I5 阴性对照（B5） | fees 扰动 0.001 → 偏移 == `−1e7×0.001`（money_atol=1e-6） | [待 Step 9] |

### D 组：文档与口径映射（3 项）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| D-1 | 附录报告入库 | `docs/APPENDIX_p015_external_calibration.md` §1-§4 齐，恒等式逐条有读数 | [待 Step 9] |
| D-2 | 口径映射实测列（同一提交） | [BACKTEST_CALIBER_MAPPING.md](BACKTEST_CALIBER_MAPPING.md) §2.2 增补 vectorbt 实测列；git log 确认同提交 | [待 Step 9] |
| D-3 | U-P015-3 关闭 | from_orders/from_signals 签名 + defaults E1 读数落附录 §1 | [待 Step 9] |

### E 组：纪律面（2 项）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| E-1 | 不进 CI / 不进 tests / 主环境零污染 | 主环境 `pip list` pandas 仍 2.2.3、numba 仍 0.65.1；新增文件仅 `scripts/external_benchmark/` + docs | [待 Step 9] |
| E-2 | 全量回归不劣化 | 主环境 `pytest tests` 仍 `635 passed`；`black --check .` 新脚本 0 变更 | [待 Step 9] |

### F 组：可重放性（2 项）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| F-1 | 复放命令留痕 | 附录 §4 含 venv 重建 + 五 case 全链复放命令（含实跑路径） | [待 Step 9] |
| F-2 | F5 红→绿记录 | IMPL §8 含红（命令+非零退出+失败行）与绿（命令+exit 0+用例计数）两读数 | [待 Step 9] |

---

## 2. 统计

- 总数：**19 项**（A3 / B4 / C5 / D3 / E2 / F2）
- 状态：Step 7 时点全部 `[待 Step 9]`（RULE-1 零预填）
- 判定规则：Step 10 逐项回填实测列后，P1/P2 清零方为通过

## 8. Step 8 一致性 Review

**执行时点**: 四文档（RESEARCH / DESIGN / IMPL / CHECKLIST）完稿后的独立 pass（RULE-1）；**[RULE-4] 自查（单视角）**，异构复审留待收尾。

### 8.1 机械校验读数（2026-11-10）

| 校验项 | 命令/方法 | 读数 |
|--------|-----------|------|
| 链接存在性 | 逐个 `Test-Path` | 6/6 OK（四文档 + BACKTEST_CALIBER_MAPPING + RESEARCH_backtest_validation），0 broken |
| 预填检查（RULE-1） | `Select-String '✅\|❌'` | **1 命中 = L5 规则声明行本身**（合法），19 项实测列全 `[待 Step 9]` |
| ID 引用闭环 | 逐 ID 跨四文档计数 | U-P015-1(5)/U-P015-2(3)/U-P015-3(12)；I1(10)/I2(8)/I3(4)/I4(5)/I5(9)；T-1(22)/T-2(8)/T-3(3)/T-4(5)；V10(3)——全部双文档以上出现，无孤引 |

### 8.2 一致性发现与修复

| ID | 发现 | 处置 |
|----|------|------|
| F-S8-P015-1 | CHECKLIST 组项 ID（A1/B1...F2）与对拍 case 编号（B1-B5）撞名，跨文档引用歧义 | 组项 ID 全部改连字符形态（A-1~F-2）；DoR 引用同步（B-3 ← B-2 运行；B-4 ← B-1~B-3） |
| F-S8-P015-2 | IMPL T-3 B3 行「两次再平衡」与 freq=1 语义不符（T=4 → i=1..3 三次） | 改为「i=1..3 逐日再平衡」 |

### 8.3 对齐矩阵

| 上游 → 下游 | 对齐结果 |
|-------------|----------|
| RESEARCH U-P015-1/2/3 → DESIGN D1/D5、§5、T-1.4 → IMPL T-1/CHECKLIST D-3、B-3 | 全部有落点 |
| DESIGN B1-B5 / I1-I5 → IMPL T-2/T-3 / V3-V8 → CHECKLIST C-1~C-5 | 一一映射 |
| DESIGN §4 数据流 → IMPL T-2 产物 → CHECKLIST B 组 | 一致（三脚本 + case 五件套 + vbt 两件） |
| DESIGN D6（venv 纪律）→ IMPL T-1.5 → CHECKLIST A-3/E-1 | 一致 |

**Step 8 结论：通过**（P1=P2=0；P3×2 已当场回写）。

## 9. Step 10 ADD 审计（回填区）

（Phase 0-4 + 取证矩阵 E1-E5，实施完成后执行）

## 10. 签字表（回填区）
