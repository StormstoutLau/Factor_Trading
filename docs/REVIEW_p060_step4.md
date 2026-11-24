# REVIEW：P-060 Step 4 设计复审记录

> **复审对象**: [DESIGN_p060_module_verification](DESIGN_p060_module_verification.md)（Step 3 DESIGN）
> **复审依据**: RESEARCH S1-S12 / I1-I10 / U-P060-1..6、DESIGN §15 复审输入 7 项
> **作者 / 复审人**: 作者 DeepSeek-V4.1-Flash；**主审 GLM-5.3-Flash（独立上下文，RULE-5 满足）**
> **日期**: 2026-11-24
> **结论**: **PASS-WITH-COMMENTS** —— 可进入 Step 5 实现，1 处 major + 1 处 minor 需实现期解决

---

## 复审方法

单一独立 reviewer 逐项核对 DESIGN §15 列出的 7 项输入，对照 RESEARCH 规格、不变式与裁定，输出发现清单。

---

## 发现清单

| 级别 | 编号 | 发现 | 依据 |
|---|---|---|---|
| **major** | F-11 | **G5 mypy 基线漂移**：基线「160 files / 0 error」不含新增 12 文件（11 测试 + 1 脚本）；`pyproject.toml` 无 `mypy.exclude` → mypy 将检查 172 文件，导致「与基线一致」判定失效 | DESIGN §8 G5 与 pyproject.toml 实况核对 |
| **minor** | F-12 | **T-A04 语义冲突**：`_calculate_cost(0)=5.0` 符合公式 `max(0,5)=5`，但 docstring「引擎不生成 0 金额」→ 该公式值可能锁定非预期行为，U-P060-8 已识别「先断言公式值，Step 6 再裁决」 | DESIGN §4.1 T-A04 / §16 U-P060-8 |
| **note** | F-13 | **零改动守卫实现路径双轨**：§10 声明「优先 monkeypatch」；T-B04/T-B10 标注「白名单 Transport」；若实测用 monkeypatch 替换 `bus`/`serve` 则合规；若修改生产签名接受 `bus` 参数则触发白名单第 ③ 条（接口参数注入），须单独 commit + T1 复审。设计两条路径并存，实现需择一明确 | DESIGN §10 / §5.1-5.3 / U-P060-5 白名单四条 |
| **note** | F-14 | **覆盖率基线微差异**：RESEARCH §3.1 `10437/12165`，DESIGN §7 `10432/12165`（差 5 行 / 0.04pp）；不影响 +315 → 88.34% 算术，但 T-C02 基线文档化时需以单次权威运行为准 | RESEARCH §3.1 vs DESIGN §7 |
| **note** | F-15 | **rebalance/factor 行数假设可达性**：rebalance +70 行依赖 Conditional/Hybrid/Calendar 可执行面（~150 行）覆盖合理；factor +42 行依赖 5 开关分支 + 退化列，预算 45 行含余量。Step 9 以实测 covA JSON 为准，不足登记残余缺口（U-P060-9） | DESIGN §7 / §16 U-P060-9 |
| **note** | F-16 | **Oracle 类型标注不一致**：T-A04 标注「公式推导」但实有语义争议；T-A10 用「不变量 + 相关系数」非纯闭式。建议 docstring 统一标注 oracle 类型（闭式/不变量/对拍/手算），便于 Step 6 抽检 | DESIGN §4.1-4.2 |
| **note** | F-17 | **分支覆盖基线记录时点**：§9 第 4 条「Step 9 首次采集后写入 baseline」，DoD 第 3 条要求「分支覆盖 JSON 已采集并写入基线」——表述一致，但需确认首次采集在 P-060c 还是 P-060a 完成后，避免基线缺失 | DESIGN §9 / §13 DoD |

---

## 规格映射完整性确认（RESEARCH S1-S12 → DESIGN）

| S-ID | 映射位置 | 状态 |
|---|---|---|
| S1 三层归属 | DD1 + §4/§5/§6 命名与 oracle | ✓ |
| S2 oracle 阶梯 | DD3 + §4/§5 显式闭式/对拍/不变量 | ✓ |
| S3 确定性 | DD10 + T-B01 确定性断言 | ✓ |
| S4 闭式期望 | §4.1 T-A01/A02/A05/A11/A13 + §4.2 T-A06/A08 | ✓（F-12 为语义争议，非映射缺失） |
| S5 边界分类 | §4.1 T-A05、§4.2 T-A09、§4.3 T-A11/A14 | ✓ |
| S6 异常契约 | §4.1 T-A03、§4.5 T-A23、§5.3 T-B11、§5.5 T-B19 | ✓ |
| S7 意图追溯 | §2 DD2 T-ID + §13 DoD 第 4 条 | ✓ |
| S8 全量命令 | §8 G1-G4/G8/G10 + §9 覆盖率脚本 | ✓ |
| S9 棘轮 | §8 G7 + I8 + DD10 | ✓ |
| S10 分类 | DD6 + §6 T-C04 | ✓ |
| S11 夹具复用 | DD1 + §4/§5 数据来源声明 | ✓ |
| S12 零新依赖 | DD10 / §5.2 真实 Redis 仅 skip | ✓ |

**不变式 I1-I10**：全部落位 DESIGN §11 表与门禁/脚本。

---

## 总体判定

**PASS-WITH-COMMENTS**

设计完整、规格映射全覆盖、算术自洽、范围与 P-059 边界清晰。仅存 **1 个 major（G5 mypy 基线漂移）** 与 **1 个 minor（T-A04 语义冲突待裁决）**，均在 Step 6/实现期可解决，不阻碍 P-060a 启动。

**建议实施前动作**：
1. `pyproject.toml` 补充 `[tool.mypy] exclude = ["tests/**", "scripts/**"]` 或更新 G5 基线读数；
2. T-A04 按 U-P060-8「先断言公式值，Step 6 再裁决」执行，不阻塞当批；
3. T-B04/T-B10 实现优先用 `monkeypatch` / `unittest.mock`，避免生产签名改动（符合 DD9 与 U-P060-5 白名单第 ③ 条）。

---

## 作者响应（2026-11-24，定稿）

> 复审结论保留不改；以下为逐条处置，已落 DESIGN §17。

| 发现 | 处置 |
|---|---|
| F-11 | **复审建议的前提需修正**：CI mypy 命令只检查 `scripts` 等生产路径，**不含 `tests`**（[tests.yml:46](../.github/workflows/tests.yml#L46)），故 11 个测试文件无影响、无需 `exclude`。真实影响面 = 新增 `scripts/coverage_snapshot.py` 必须全量类型标注；G5 改为 CI 同命令 + files 160→161 / 0 error |
| F-12 | 采纳：T-A04 收窄为「公式一致性 + `pending-semantics`」，不认定业务期望；U-P060-8 裁决后按 DD8 改断言 |
| F-13 | 采纳：§10 增加实现单轨——一律 monkeypatch/mock，本批默认不启用白名单，禁止先改签名再审批 |
| F-14 | 采纳：基线统一为 Step 2 重放 JSON（10432/12165），文件内记 `source=step2-replay`；RESEARCH §3.1 补 5 行差异脚注 |
| F-15 | 采纳：未达 O2 登记 **G-P060-13** 残余缺口，不放宽标准 |
| F-16 | 采纳：DD2 固定 docstring 首行 `T-ID | oracle=...`；T-A04/T-A10 已改标签 |
| F-17 | 采纳：分支覆盖首次采集固定为 **P-060c 完成后**（`source=p060c-first`） |

**修订后判定**：F-11 major 已消解（且风险面小于原判定），F-12 minor 已收窄；**可进入 Step 5 实现**。