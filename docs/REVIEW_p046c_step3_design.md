# REVIEW（Step 4）：P-046c DESIGN 异构复审

> **批次**: P-046c · **Step 4 DESIGN 异构复审**（RULE-5：reviewer ≠ 作者）
> **被审物**: [DESIGN_p046c_f2_closeout](DESIGN_p046c_f2_closeout.md)（作者 DeepSeek-V4.1-Flash，2026-11-23 落盘）
> **复审者**: GLM-5.3-Flash（≠ 作者）
> **代码证据时点**: HEAD `3495683`；被审物**零代码变更**，门禁基线引用 [RESEARCH §9](RESEARCH_p046c_f2_closeout.md)
> **复审日期**: 2026-11-23
> **结论**: **PASS —— 0 P1 + 1 P2 + 2 P3（当轮全修）+ 3 观察**；门禁目标维持不变（测试数 39 不变）

---

## 1. 复审方法

1. **D↔代码逐字比对**：D2/D3 对照 [portfolio.py L738-L756](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L738-L756) 现状语义；D10 对照 pypfopt A1（wheel `efficient_frontier.py` L225-L293）约束缩放；D14 对照 [data.py L442-L470](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L442-L470) 的 `fill_value=0` 语义；D15 对照引擎 L1391 既有 except 语义。
2. **数值独立重算**：E1 5A/2A、E2 预算、E4 pypfopt 参考、E4 无箱体闭式、Kelly 闭式、E8 加 `max_weight=0.1`（设计期探针 + 本轮取证探针）。
3. **门禁算术**：collect/p046/black/tests/mypy 增量复核 + CI mypy 范围核实。
4. **数学推导**：D4 无 `Σw=1` 的 KKT 论证；部分零方差凸回退可行性分析。

---

## 2. 核验矩阵

### 2.1 核心设计决策（D1-D22）

| 项 | 复审 | 判定 |
|---|---|---|
| D1 范围五项 + 显式延后 | 与 U7 裁决/§2.2 非目标一致；P-046d 行已建（I8 达成） | ✓ |
| D2 快速路径零漂移 | 伪代码循环体与现状 L740-L756 逐字等价；**发现措辞缺陷**（F-4-1，已修） | ✓（修后） |
| D3 回退四条件 + diag 预判 | 部分零方差凸回退探针：status=optimal 但 **w₃=2.69e6 病态解** → diag 预判必要；**发现伪代码判定缺陷**（F-4-2，已修） | ✓（修后） |
| D4 凸模型无 `Σw=1` | KKT 独立推导：加 `Σw=1`（乘子 ν）→ `RC_i = λb_i − νw_i`，不保证 RC∝b ✓；E2 复算 max\|rc−b\|=5.67e-05（不加约束口径）✓ | ✓ |
| D5 诊断载体 | 复用 `message`+`warning_kind`，映射表分流；zero_vol 路径行为逐字（现状三元表达式 → dict `.get` 默认值等价） | ✓ |
| D6 `risk_budget` 命名 | 与 `_scale_to_budget` 权重预算撞词已消歧；仅 risk_parity 可用（A14） | ✓ |
| D7 预算归一规则 | 五分支覆盖完整；「缺失补剩余」优于「补 1/n 再归一」（稀释论证成立）；**零分量被拒**从严（O-4-2 观察） | ✓ |
| D8/D9 Kelly | `risk_aversion=1/f` 复用共享求解器；`fraction=1` 与 MVO δ=1 逐位同解；需 returns fail-loud（B7）；keyword-only 参数有 `feas` 先例 | ✓ |
| D10/D11 MaxSharpe | 与 pypfopt A1 逐点比对：`(μ−rf)ᵀy=1`、`Σy=k≥0`、box 按 k 缩放、`w=round(y/k,16)+0.0`（L292）、`max(μ)≤rf → ValueError`（L244-L247）全等价；E4 复算逐位命中（Sharpe 1.3857552798） | ✓ |
| D12-D17 行业投影 | 插入点唯一性（L1507/L1508）✓；`fill_value=0` 语义核实（L444/L462/L470）→ D14 的 0=未分类正确；`labels==0` 对 object 列安全；D17 拒绝 config_v2 反向规则（行业上限 0.3>个股 0.1 合法）理由成立 | ✓ |
| D15 不可行处理 | `InfeasibleConstraintError` 在 rebalance 捕获落账 return——与 L1391 既有 except 语义同构；RuntimeError → internal（classify_day_error） | ✓ |
| D18-D20 | CLI 不扩（P-046b 先例）；零改动面清单与 I11 一致；观测设计合理 | ✓ |
| D21 upper 语义 | 与 U1-A/BL lazy 语义一致（upper 早退先于 returns 检查） | ✓ |
| D22 依赖边界 | pypfopt 参考值固化为常量（容差 1e-6，复算余量 1e-17）；CI 不 import | ✓ |

### 2.2 数值与构型

| 项 | 复审 | 判定 |
|---|---|---|
| E1 5A/2A 回退参考 | 复算 `[0.200213,0.401382,0.278986,0.074362,0.045057]` / `[0.599999,0.400001]`（差 ≤1e-6） | ✓ |
| E4 构型确证 | μ=[0.08,0.06,0.05,0.04,0.03] + rf=0.02 + max=0.6 → 参考解与 Sharpe **逐位命中**；RESEARCH §15 未登记 μ → §8.4 已注明确证过程（诚实） | ✓ |
| E4 无箱体闭式 | 复算含 **−0.1385** → 长多绑定；I5/I6 精化为「内部解闭式」（对角 Σ：Kelly λ=2 差 1.11e-16、Sharpe 差 5.55e-17）正确 | ✓ |
| A3/A4/A6/A8/B1/B2/B9/B10/C1/C2 构型与容差 | 逐项复算可复现；A6 一步迭代变化 8.69 >> 1e-12（触发 max_iter ✓）；C1 L2=0.1522 复现 | ✓ |
| **C9/C10 构型缺陷** | 默认 `max_weight=0.10` 下 n=4 → n·max=0.4<1 → **upper 型**，equal_weight 返回各 0.1 → A 组和 0.2<cap → 投影不触发，断言（A 组 0.4）不可达；`max_weight=0.5` 时解 [0.2,0.2,0.3,0.3] 证实可达（探针） | ✗ F-4-3（已修） |
| A7 构型 | σ_p²=0.0144>0 → 现状静默等权、DESIGN zero_vol——诊断差异无既有断言（C19）；构型注记已补 | ✓（修后） |

### 2.3 门禁算术与范围守卫

| 项 | 复审 | 判定 |
|---|---|---|
| collect 1464+39=1503 / passed 1463+39=1502+1 skipped / `-k p046` 78+39=117 | 算术正确；新文件名含 `p046c` → `-k p046` 匹配 | ✓ |
| mypy 160 不变 | CI 命令范围 `core agents filter scripts ... live services` **不含 tests/**（[tests.yml L46](file:///f:/Coding/Factor_Trading_v3.0/.github/workflows/tests.yml#L46)）；本批不新增 scripts → 160 不变 | ✓ |
| black 322+3=325 / tests 158+3=161 / core 51 不变 | `--check .` 全仓；零 core 新文件 | ✓ |
| golden 22 零重录 | 默认 equal_weight + `industry_max_weight=None` 路径零变更；诊断映射 dict 化 zero_vol 逐字 | ✓ |
| 测试编号 | A1-A14（14）+ B1-B15（15）+ C1-C10（10）= **39** ✓ | ✓ |
| 范围守卫 | 无 P-046d/P-053 夹带；无新依赖；`config_v2`/`sizing`/`interfaces`/`target_positions` 零触碰 | ✓ |
| 派生接口 F-3-1/2/3 | 登记完整、回退点明确 | ✓ |

---

## 3. 发现与当轮修复

| ID | 级别 | 位置 | 内容 | 修复 |
|---|---|---|---|---|
| **F-4-1** | **P2** | D2/I12 + §5.1 步骤 2 + A7 | **零漂移承诺与 diag 预判矛盾**：原文「快速路径逐字保留 / 既有诊断语义逐字保留」未限定范围，而步骤 2 把「任一 diag≤0」提前判 zero_vol——部分零方差（diag 含 0、σ_p²>0）现状为静默等权无诊断，DESIGN 新增 zero_vol 诊断（权重不变）。**取证**：部分零方差走凸回退产生 ~10⁶ 病态解（Σ=diag(0.04,0.09,0) → w₃=2.69e6，status=optimal）→ 预判必要不可删；诊断差异无既有断言（C19 零退化用例）不构成破坏 | **当轮修订**：D2/D3/I12 限定「零漂移 = 正常路径权重；diag 退化为新增防护路径（权重一致 + 诊断从静默→zero_vol）」；A7 构型注记 σ_p²>0 与依据 |
| **F-4-2** | P3 | §5.1 伪代码步骤 3/4 | **zero_vol 误判 max_iter**：原文 `if reason is None and not converged: reason="max_iter"` 在循环内 σ_p²≤0 break（zero_vol=True、converged=False）时误触发 → 走回退覆盖 zero_vol 结果（message/warning_kind 被改写，权重被凸解替换） | **当轮修订**：判定加 `not zero_vol` 前置（两处）；循环内 σ_p² 分支注记「保持末次 w（现状语义）」 |
| **F-4-3** | P3 | §8.3 C9/C10/C8 | **用例构型不可达**：C9/C10 未显式配 `max_weight` → 默认 0.10 下 4 股为 upper 型（各 0.1、cash 0.6）、投影不触发、断言（A 组 0.4 / [0.25]*4）不可达；C8 未写明 max_weight 与 w0 相容性 | **当轮修订**：C9/C10 补 `max_weight=0.5`（探针证实解 [0.2,0.2,0.3,0.3]）；C8 补 `max_weight=0.3` |
| O-4-1 | 观察 | §6/D16 | cap **触发时** sizing/overlay 放大后的权重会被投影的 `w≤max_weight` 压回（有意语义，§6/R4 已声明）；建议 Step 5 增 1 例「overlay 放大 + cap 触发」联测（不计入 39 例冻结，登记于 IMPL 期） | 登记不修 |
| O-4-2 | 观察 | D7 | 零预算分量（b_i=0 → w_i=0，凸模型本可支持）被 `ValueError` 从严拒绝；本批预算场景全为正分量，可接受；未来如需再放宽 | 登记不修 |
| O-4-3 | 观察 | I2/A1 | 两资产例容差 ±1e-4（RESEARCH §7 I2 原为 ±1e-6；复算实际偏差 ~1e-6，1e-4 为求解器版本稳健性余量）→ 已在 RESEARCH 保持原值、DESIGN 放宽，无矛盾但建议 Step 9 实测后统一注记 | 登记不修 |

---

## 4. 结论

- **判定**：**PASS**。0 P1；1 P2 + 2 P3 当轮全修（DESIGN 已落字）；3 观察登记（1 项转 IMPL 期动作）。
- **核心确认**：D4 的 KKT 论证、D10 的 pypfopt 等价性、D14 的 0/NaN 语义、门禁算术（含 mypy 范围）、39 例测试编号全部独立成立；部分零方差病态解为新发现证据（设计期未探）。
- **门禁目标维持**：1503 / 117 / 22 / 120 / 160·0 / 325 / 22·30 / 3 kept / 0 / 161·51·19·13（测试数 39 不变）。
- **下一步**：Step 5 IMPL（按 DESIGN §13 红→绿顺序；O-4-1 联测例登记于 IMPL）。
