# REVIEW：P-046b Step 6 实施文档异构复审（IMPL）

> **批次**: P-046b · **Step 6 实施 Review** · 日期 2026-11-23
> **被审物**: [IMPL_p046b_bl_hrp](IMPL_p046b_bl_hrp.md)（Step 5 交付）
> **reviewer**: GLM-5.3-Flash（≠ Step 5 作者 DeepSeek-V4.1-Flash，异构成立）
> **证据时点**: HEAD `8f8b912`；复审全程零代码变更
> **取证**: E1 IMPL/DESIGN/RESEARCH 全文逐字读取；E2 wheel METADATA 实读 + 运行时版本实读（§2）；E3 锚点行号逐字机械核验 **16/16 PASS**（§3）；E4 签名可实现性（无命名冲突 grep + 插入锚点读码）
> **结论**: **PASS（修复后）**——0 P1 / 0 P2 / 4 P3 当轮全修；版本存在性与签名可实现性两项规范硬约束全过。

---

## 1. 复审范围（SPEC_PROCESS Step 6 幻觉抑制清单）

| # | 清单项 | 核对方式 | 结论 |
|---|---|---|---|
| 1 | 版本存在性核验 | §2 版本核验表（引用四步：抽取→解析→字段比对→落状态） | ✅ 全部 T1 命中 |
| 2 | 签名可实现性 | §4 逐接口对照既有代码锚点/导入/调用点 | ✅ 14 项全部可实现 |
| 3 | **派生需求登记** | §5.1——实施中产生、DESIGN 未显式声明的新接口 | ⚠️ `_upper_result` 漏登 → F-6-1 |
| 4 | DESIGN 模块 ↔ IMPL 对应 | D1-D20 → T1-T12 逐条映射 | ✅ 无悬空模块 |
| 5 | IMPL 功能点 ↔ CHECKLIST | 留 Step 7（本文不审） | — |
| 6 | DESIGN↔IMPL 对齐（消息格式/签名增量） | §5.2 | ✅（F-5-1 `feas` 精化已声明且合理） |
| 7 | 门禁数字一致性 | §5.3 算术复核 | ✅ 1464/78/322/160/158/51/19/13/22·30 |
| 8 | 对拍边界可执行性 | §5.4（§4.2 实测 + §4.3 分歧登记交叉验证） | ✅ F-5-3 成立 |

---

## 2. 版本核验表（引用四步，E2 实测 2026-11-23）

**抽取**：IMPL §4.0-§4.1 声明的全部版本 ID → **解析**：PyPI wheel `*.dist-info/METADATA` 实读（`uv pip install --no-deps --target %TEMP%\p046b_pkgs`，Step 5 降级链产物）→ **字段比对** → **落状态**如下：

| ID | 声明 | 解析记录（METADATA 逐字） | 字段比对 | 状态 |
|---|---|---|---|---|
| A20/A20b-A20e/A21/A21b | PyPortfolioOpt **1.5.5** | `Name: pyportfolioopt \| Version: 1.5.5` | 名称+版本一致 | ✅ 已验证（T1 wheel） |
| A22/A23 | skfolio **1.14.4** | `Name: skfolio \| Version: 1.14.4` | 一致 | ✅ 已验证（T1 wheel） |
| A24 | Riskfolio-Lib **7.4.1** | `Name: riskfolio-lib \| Version: 7.4.1` | 一致（`riskfolio_lib` 目录名 = 正规化名） | ✅ 已验证（T1 wheel） |
| A25 | pandas **3.0.3** 运行时 | `importlib.metadata: pandas 3.0.3`（venv 实读） | 一致 | ✅ 已验证（T1 可重放） |
| A26 | scipy **1.17.1** / numpy 2.4.6 | venv 实读 | 一致 | ✅ 已验证（T1 可重放） |
| 未取证 | GitHub commit hash | 无解析记录 | — | **未验证**（IMPL §4.0 已如实声明，不引 master 结论）✅ 合规 |

> 无「已验证但无解析记录」行；未验证项已显式声明——符合规范禁止条款。

---

## 3. 锚点行号逐字机械核验（E3，16/16 PASS）

对 IMPL §4.1 声明的 16 处「文件+行号+逐字要点」逐一机械比对（wheel 源码 splitlines 后区间内 needle 命中即 PASS）：

| 组 | 断言 | 结果 |
|---|---|---|
| A20 | `default_omega` L346-356 / 「avoid inversion」L403 / `pi=="equal"` L277-278 / 观点不在 universe L235 / 隐含权重 L452-453 | **5/5 PASS** |
| A21/A21b/A25 | `pre_order` L105 / `pd.Series(1, ...)` L120 / `squareform(...,checks=False)` L166 | **3/3 PASS** |
| A22 | `posterior_mu` L280 / `posterior_cov` 尾项 L284 | **2/2 PASS** |
| A23 | `squareform(X, checks=False)` L189-190 / 零风险 raise L487 / `alpha` L512 | **3/3 PASS** |
| A24 | `squareform(dist)` L381-382 / `1/np.power(inv_risk,2)` L240 / `alpha_1` L503 | **3/3 PASS** |

**合计 16/16 PASS**——IMPL §4.1 无行号漂移、无幻觉引用。

---

## 4. 签名可实现性（E4）

| 接口 | 可实现性依据 | 结论 |
|---|---|---|
| `BLConfig`/`HRPConfig` | `dataclass`/`field` 已在 config.py L10 导入；`math` 补导入已计划；无同名符号（grep 0 命中） | ✅ |
| `OptimizerConfig.bl/hrp` | 插入点 L300 后、`__post_init__` L302 前与锚点吻合 | ✅ |
| `warning_kind` | 末尾字段 + 默认值；9 处位置构造（Step 4 已核）+ engine kwargs 构造均兼容 | ✅ |
| `black_litterman_posterior`/`_bl_prior` | 依赖 `math`/`Mapping`/`Sequence`（导入计划 §3.3）；`np`/`pd`/`logger` 已在 portfolio.py | ✅ |
| `correlation_distance`/`quasi_diagonal_order`/`recursive_bisection` | 依赖 scipy 导入（§3.3 计划）；`InfeasibleConstraintError` 已在 L39 | ✅ |
| `_upper_result`/`_solve_mean_variance` | 依赖 `cp`/`_precheck`/`_Feasibility`/`OptimizationResult` 均已在 portfolio.py；插入点 L370 前 | ✅ |
| `BlackLittermanOptimizer`/`HRPOptimizer` | `BaseOptimizer._select/_cov_for/_apply_constraints/_empty_result` 均存在（L231-L312） | ✅ |
| `build_optimizer` 3 键 | map 结构 L619-L625；未知-method 测试仅匹配 `"合法值"` | ✅ |
| 引擎三元 | L1375 现为字面量 `"InfeasibleConstraints"`，替换点唯一 | ✅ |
| `estimate_cov` 2 处替换 | L214-215 / L221-222 与现码逐行对应 | ✅ |
| T11 bench | `disallow_untyped_defs=false` + `--check-untyped-defs` → 标注义务可满足；scripts 在 CI mypy 路径 | ✅ |
| T12 假优化器 | 位置参数 5 + 关键字 2 合法；`_optimize_with_diagnostics` L88-90 优先走 `optimize_with_diagnostics` | ✅ |

**命名冲突检查**：`_upper_result`/`_bl_prior`/`_solve_mean_variance`/`correlation_distance`/`quasi_diagonal_order`/`recursive_bisection`/`black_litterman`/`warning_kind` 在 core 全域 grep **0 命中** → 全部为新符号，无遮蔽。

---

## 5. 对齐与发现

### 5.1 派生需求登记核对

| 项 | 状态 |
|---|---|
| F-5-1（`feas` 关键字） | ✅ 已登记（§3.4 + §9） |
| F-5-2（`max_assets` → `InfeasibleConstraintError`） | ✅ 已登记（§3.7 + §9；`ValueError` 子类契约保持） |
| F-5-3（对拍边界） | ✅ 已登记（§4.2/§4.3 + §9） |
| **`_upper_result` 模块级函数** | ❌ **漏登**——实施中产生、DESIGN 未声明的新接口（DESIGN §4.5 只声明 `_solve_mean_variance`）→ **F-6-1** |

### 5.2 DESIGN ↔ IMPL 对齐（D1-D20 → T1-T12）

20 项决策全部有对应任务；消息格式（`_upper_result` 与 MVO 旧 f-string 逐字同构）、`zero_vol` 语义（§3.2 upper 分支保留约束 message、`zero_vol` 仅由 `warning_kind` 承载）均与 DESIGN §7.2/§8.1 一致。**无悬空模块、无夹带**。

### 5.3 门禁数字算术复核

| 项 | 算式 | 结论 |
|---|---|---|
| pytest collect | 1441 + 23 = **1464**（1463 passed + 1 skipped） | ✅ |
| `-k p046` | 55 + 23 = **78** | ✅ |
| black | 319 + 2 测试文件 + 1 脚本 = **322** | ✅ |
| mypy files | 159 + 1 脚本（CI 路径含 scripts）= **160** | ✅ |
| `tests/*.py` | 156 + 2 = **158**；core 51 / live 19 / services 13 不新增文件 | ✅ |
| AST | 新代码无裸 except → **22 / 30** | ✅ |

### 5.4 发现与当轮修复（F-6-1..F-6-4，全部 P3）

| ID | 级 | 发现 | 修复（当轮完成，IMPL 已落字） |
|---|---|---|---|
| **F-6-1** | P3 | 派生接口 **`_upper_result`** 未按规范登记（§9 仅 F-5-1..F-5-3） | §9 补 **F-5-4**：`_upper_result(cfg, selected, method)` 为派生接口（三优化器 upper 消息去重），DESIGN §4.5 未声明、行为等同既有内联 |
| **F-6-2** | P3 | §2 `warning_kind` 回退点写「单点」不准确——回退涉及字段 + RiskParity/HRP 置位 + 引擎三元（4 处） | §2 该行改为「删字段 + RiskParity/HRP 置位（3 处）+ 引擎三元回退常量」 |
| **F-6-3** | P3 | `MinVarianceOptimizer` 处置未显式声明——其 upper 分支内联消息与 `_upper_result` 并存；MinVariance 不共用 `_solve_mean_variance`（目标函数为纯 min variance，无 μ 项） | §3.4 补注：MinVariance 本批**零改动**（含 upper 内联消息）；`_upper_result` 仅 MVO/BL/HRP 消费 |
| **F-6-4** | P3 | upper + zero_vol 组合（RiskParity cov 全零且 n×max<1）时引擎 `error_type="ZeroVariance"` 优先于 `InfeasibleConstraints`——语义自洽但优先级未明说 | §3.2 补注：组合情形 `ZeroVariance` 优先（零方差是更根本的失效原因；infeasible_kind 字段仍保留 upper 供诊断） |

> 复审过程探针笔误 0；无被审物外的连带问题。

---

## 6. 结论

- 规范 Step 6 两大硬约束：**版本存在性**（§2 表，全部 T1 命中）与**签名可实现性**（§4，14 项 + 无命名冲突）**全部通过**。
- **0 P1 / 0 P2 / 4 P3**，当轮全修并已落字 IMPL；门禁目标不变；对拍边界 F-5-3 复核成立。
- **放行**：Step 6 复审 **PASS**，可进入 Step 7 CHECKLIST。

## 7. 状态链

- **2026-11-23**：Step 6 实施文档异构复审（本文）——16/16 锚点机械核验、3 包 METADATA 版本核验、4 P3 当轮全修（F-6-1..F-6-4）。
- **下一步**：Step 7 CHECKLIST（DoR/DoD 逐项 + 门禁目标冻结）。
