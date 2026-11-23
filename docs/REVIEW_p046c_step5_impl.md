# REVIEW（Step 6）：P-046c IMPL 异构复审

> **批次**: P-046c · **Step 6 IMPL 异构复审**（RULE-5：reviewer ≠ 作者）
> **被审物**: [IMPL_p046c_f2_closeout](IMPL_p046c_f2_closeout.md)（作者 DeepSeek-V4.1-Flash，2026-11-23 落盘）
> **复审者**: GLM-5.3-Flash（≠ 作者）
> **代码证据时点**: HEAD `3495683`；被审物**零代码变更**，门禁基线引用 [RESEARCH §9](RESEARCH_p046c_f2_closeout.md)（collect 1464 / 78 / 22 / 120 / 160·0 / 322 / 22·30 / 3 kept / 0 / 158·51·19·13）
> **复审日期**: 2026-11-23
> **结论**: **PASS —— 0 P1/P2 + 3 P3（当轮全修）+ 2 观察**；门禁目标维持不变（1503 / 117 / 22 / 120 / 160·0 / 325 / 22·30 / 3 kept / 0 / 161·51·19·13）

---

## 1. 复审方法（对照 P-046b Step 6 先例）

1. **规范两大硬约束**：版本存在性（锚点包/版本可解析 + wheel METADATA）；签名可实现性（14 接口可实现 + 新符号全域 grep）。
2. **锚点行号机械核验**：A27-A36 的文件 + 行号 + 逐字要点逐一比对 wheel 源码。
3. **插入锚点核验**：§3 全部行号对 @`3495683` 实测（config.py / portfolio.py / engine_v2.py）。
4. **DESIGN↔IMPL 对齐**：D1-D22 → T1-T9 无悬空；39 例映射 ↔ DESIGN §8 逐例比对；门禁算术复核。
5. **F 链完整性**：F-4-1..3（Step 4）/ O-4-1..3 / F-5-1..3 的落地情况。
6. **骨架可实现性**：代码骨架缩进 / 变量作用域 / 与现状结构的兼容性。

---

## 2. 核验矩阵

### 2.1 规范硬约束

| 项 | 复审 | 判定 |
|---|---|---|
| 版本存在性 | A27-A36 引用 skfolio **1.14.4** / riskfolio-lib **7.4.1** / pypfopt **1.5.5**——三包 wheel 在 `%TEMP%\p046b_pkgs`（P-046b Step 6 METADATA 实读 T1 命中，版本可解析） | ✓ |
| 签名可实现性 | 14 接口全部可实现；新符号 12 个（`KellyConfig`/`MaxSharpeConfig`/`risk_budget`/`kelly`/`max_sharpe`/`_risk_budget_vector`/`_solve_risk_budget_convex`/`KellyOptimizer`/`MaxSharpeOptimizer`/`IndustryCapResult`/`project_industry_cap`/`_WARNING_ERROR_TYPES`/`_industry_tags`/`_industry_cap_warned`）全域 grep（`*.py`）**0 命名冲突** | ✓ |
| 零改动面声明 | `config_v2.py` / `sizing.py` / `target_positions.py` / `interfaces.py` / `IOptimizer` / 6 既有优化器——IMPL §1.2/§2 未触碰 | ✓ |

### 2.2 锚点行号机械核验（A27-A36）

| ID | 引用 | 复审（wheel 实读） | 判定 |
|---|---|---|---|
| A27 | skfolio `_risk_budgeting.py` L30-L41 公式 | docstring 公式块 L32-L41 覆盖 ✓ | ✓ |
| A27b | 同上 L653-L666 `factor=cp.Variable()` | `w = cp.Variable(n_assets)` L653、`factor` L654、log 约束 L666 ✓ | ✓ |
| A27c | 同上 L640-L650 零预算夹 1e-10 | `risk_budget = self.risk_budget` L640、`np.where(...==0, 1e-10...)` L650 ✓ | ✓ |
| A28 | riskfolio `Portfolio.py` L3465-L3493 docstring | `bᵀlog(w) ≥ c` 公式块 L3472-L3479 ✓ | ✓ |
| A28b | 同上 L3626 `k = cp.Variable((1,1))` + L4333-L4335 `sum(w)==k` | 逐字命中 ✓ | ✓ |
| A28c | 同上 L1991-L1995 + L2145-L2157 | `kelly` docstring L1991-L1995 ✓；`exact/approx/None` 分支 L2146-L2157（L2156-2157 `elif kelly is None`）✓ | ✓ |
| A29 | skfolio `_mean_risk.py` L152-L155 | `risk_aversion` docstring ✓ | ✓ |
| A29b | 同上 L1554-L1560 | `MAXIMIZE_UTILITY` case + `expected_return − risk_aversion·risk` ✓ | ✓ |
| A29c | 同上 L1561-L1575 | `MAXIMIZE_RATIO` case L1561 + `np.max(mu) − rf ≤ 0` L1567 + `ValueError` L1569-L1572 ✓ | ✓ |
| A30 | pypfopt `efficient_frontier.py` L253-L292 | `objective = quad_form` L253、`(μ−rf)ᵀw==1` L285、`Σw==k` L286、`k≥0` L287、反变换 L292 ✓ | ✓ |
| A31 | `objective_functions.py` L140-L163 | `quadratic_utility` def L140 + `μ − ½δ·wᵀΣw` L142 + `cp.Parameter` L161-L162 ✓ | ✓ |
| A32 | `base_optimizer.py` L366-L403 | Step 2b 已核（逐位）✓ | ✓ |
| A33 | skfolio `_base.py` L392-L409 | Step 2b 已核 ✓ | ✓ |
| A34 | riskfolio `ConstraintsFunctions.py` L34-L69 | Step 2b 已核 ✓ | ✓ |
| A35 | pypfopt `objective_functions.py` L168-L183 / L186-L202 | Step 2b 已核 ✓ | ✓ |
| A36 | riskfolio `Portfolio.py` L109-L111 `kindbench` | Step 2b 已核（含 F-R2b-2 命名修正的渊源）✓ | ✓ |

**16/16 PASS**；B9-B15 书目级未被误用于实现断言（仅 §4.4 佐证列 + 边界声明）✓。

### 2.3 插入锚点（@`3495683` 实测）

| 锚点 | IMPL 引用 | 实测 | 判定 |
|---|---|---|---|
| config.py：`HRPConfig` L297-L308 / `OptimizerConfig` L311 / 字段区 L322-L344 / `risk_parity_max_iter` L335 / `hrp` L344 / `__post_init__` L346-L358 | 逐位命中 | ✓ |
| portfolio.py：常量区 L32-L39 / `_solve_mean_variance` 结束 L586 / MinVariance L589 / BL 结束 L714 / RP L717-L794 / HRP 结束 L846 / 工厂 L890-L899 | 逐位命中；**§3.3 两段行号重叠**（L736-L764 vs L758-L765）→ F-6-1 | ✗→修 |
| engine_v2.py：导入 **L65**（IMPL 原写 L~60）/ `_unclosed_positions` **L192**（原写 L~225，偏差 33 行）/ `_execute_rebalance` L1302 / 末语句 L1538 / L1375 / L1507 | 两处行号精度 → F-6-2；语义锚（`_unclosed_positions` 后）正确 | ✗→修 |

### 2.4 DESIGN↔IMPL 对齐

| 项 | 复审 | 判定 |
|---|---|---|
| D1-D22 → T1-T9 | D1→全局 / D2-D5→T2-T3 / D6-D7→T2 / D8-D9→T1+T4 / D10-D11→T1+T5 / D12-D17→T6-T7 / D18→T7 / D19→全局零改动面 / D20→T7 / D21→T4-T5 / D22→T8——**无悬空** | ✓ |
| 39 例映射 ↔ DESIGN §8 | A1-A14 / B1-B15 / C1-C10 逐例一致；Step 4 修复全部继承（A7 构型注记 σ_p²>0、C9/C10 `max_weight=0.5`、C8 `max_weight=0.3`） | ✓ |
| 门禁算术 | 1464+39=1503 / 1463+39=1502+1 / 78+39=117 / 322+3=325 / 158+3=161 / mypy 160（CI 范围不含 tests，Step 4 已核）/ AST 22·30（新测试文件不在 AST 五目录）/ golden 22 零重录（默认路径零变更） | ✓ |
| 低效排除表 | 12 行非空，每行有排除原因与采用方案 | ✓ |
| 降级链 | riskfolio 数值对拍 `ModuleNotFoundError: arch`（Step 5 实测）→ 降级源码锚点；未安装（零新依赖）✓ | ✓ |

### 2.5 F 链与骨架可实现性

| 项 | 复审 | 判定 |
|---|---|---|
| F-4-1（diag 预判） | §3.3 骨架步骤 1 + A7 构型注记 ✓ | ✓ |
| F-4-2（zero_vol 误判） | 骨架 L277/L279 `not zero_vol and` 前置 ✓ | ✓ |
| F-4-3（C8/C9/C10 max_weight） | §6.2 三例已带显式配置 ✓ | ✓ |
| O-4-1（联测探针） | §6.4 登记（不计入 39 例，保冻结数）✓ | ✓ |
| O-4-2（零预算） | §4.3 分歧表 + T1 校验 ✓ | ✓ |
| F-5-1（Σw=1 不可行） | DESIGN D4 已回填 + §3.2 docstring ✓ | ✓ |
| F-5-2（δ=2/f） | DESIGN D8 已回填 + `KellyConfig` docstring ✓ | ✓ |
| F-5-3（riskfolio 降级） | §4.0/§4.2 记录 ✓ | ✓ |
| **骨架缩进** | §3.3 L287-288 fallback 重算在 **else 分支内**（12 空格）——预算分支（elif）的 `fallback_reason="risk_budget"` 不会触发等风险重算覆盖凸解 ✓；与 DESIGN §5.1 伪代码一致 | ✓ |
| **upper+fallback 组合** | upper 分支 `warning_kind=warning_kind` 可为 `erc_fallback` → 引擎映射 `RiskParityFallback`；`zero_vol` 优先级与 P-046b F-6-4 一致（单一 warning_kind 判定） | ✓ |
| **二次归一** | 预算/预判分支的 weights 已归一，L294-296 再归一无害（幂等） | ✓ |
| **rc_mismatch 口径** | `pct = w·(Σw)/σ_p²` 与 DESIGN §5.1 条件④同式；快速路径收敛后偏差 ~tol 级 << 1e-3，不误伤 | ✓ |

---

## 3. 发现与当轮修复

| ID | 级别 | 位置 | 内容 | 修复 |
|---|---|---|---|---|
| **F-6-1** | P3 | IMPL §3.3 | **行号区间重叠**：第一段「替换 L736-L764」与第二段「L758-L765 改为」重叠 7 行（L758-L764 同属两段），实施者会困惑替换边界 | 当轮修正：第一段改为 **L736-L756**（计算段），并注记「两段不重叠——F-6-1 修正」 |
| **F-6-2** | P3 | IMPL §1.2 / §3.7 | **引擎行号精度**：属性锚「L~225」实为 **L192**（`_unclosed_positions`）；导入「L~60」实为 **L65**。语义锚正确、行号不准 | 当轮修正：§1.2 与 §3.7 改为精确行号并标注 F-6-2 |
| **F-6-3** | P3 | IMPL §3.6 | **骨架与风险缓解不一致**：骨架 `labels == 0`，§8 风险表缓解为 `labels.eq(0)`（object 列混合类型的稳健写法） | 当轮修正：骨架统一为 `labels.isna() | labels.eq(0)` |
| O-6-1 | 观察 | §1.1 T9 / §3.8 | T9 写「§3.103」——该序号已被 Step 5 分节占用；Step 9 后应使用**下一可用序号** | 当轮措辞修正（标注占用事实） |
| O-6-2 | 观察 | §4.3 分歧表 | 「pypfopt 允许负权重/无 upper 概念」措辞不精——pypfopt 有 `weight_bounds`，准确说法是「无 upper 型不可行语义（Σw=1 经 k 变换恒成立，不留现金）」 | 当轮措辞修正 |

---

## 4. 结论

- **判定**：**PASS**。0 P1 / 0 P2；3 P3 当轮全修（IMPL 已落字）；2 观察当轮措辞修正。
- **核心确认**：规范两大硬约束全过（版本可解析 + 12 新符号 0 冲突）；锚点 16/16 机械命中；插入锚点除 2 处行号精度外全准；D↔T↔39 例无悬空；门禁算术复核全过；骨架缩进与作用域正确（fallback 重算不覆盖预算解）。
- **门禁目标维持**：1503 / 117 / 22 / 120 / 160·0 / 325 / 22·30 / 3 kept / 0 / 161·51·19·13。
- **下一步**：Step 7 CHECKLIST（A-H 组，实测列 0 预填）。
