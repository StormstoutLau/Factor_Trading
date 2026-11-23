# REVIEW：P-046b Step 4 DESIGN 异构复审（BL / HRP 优化器）

> **批次**: P-046b · **Step 4 设计复审** · 日期 2026-11-23
> **被审物**: [DESIGN_p046b_bl_hrp](DESIGN_p046b_bl_hrp.md)（Step 3 交付）
> **reviewer**: GLM-5.3-Flash（≠ Step 3 作者 DeepSeek-V4.1-Flash，异构成立）
> **证据时点**: HEAD `8f8b912`；代码面 `git status` 仅 docs 改动（复审全程零代码变更）
> **取证**: E1 仓内源码逐字读取（portfolio.py / config.py / engine_v2.py / diagnostics.py / tests / pyproject / CI workflow）；E2 门禁基线实测 7 组（§2，命令可重放）；E3 数值探针 3 组（§3，BL 7 性质 + HRP 论文链 + scipy 边界，reviewer 独立实现）
> **结论**: **PASS（修复后）**——2 P2 + 6 P3 当轮全修；无 P1。

---

## 1. DESIGN §13 复审清单 10 项逐项核对

| # | 清单项 | 核对方式 | 结论 |
|---|---|---|---|
| 1 | U1-U17 关闭一致性 | §1 表 17 行逐条与 D1-D20/§4-§8 对照 | ✅ 一一对应，无悬空项 |
| 2 | BL 数学 | E3 探针 §3.1（Woodbury/Ω/τ 消去/K=0/单观点 F-R2） | ✅ 7/7 闭式吻合 |
| 3 | BL 组合不继承 | `isinstance` 语义由 §10.1 #9 锁定；`_solve_mean_variance` 抽取与 MVO L434-L502 结构对照 | ✅ 可行域判定/cvxpy/upper 单点解均可原样迁移 |
| 4 | HRP 论文一致性 | E3 探针 §3.2（`pdist(d)`=d̃ 逐位、Z/叶序、递归二分独立复算） | ✅ 与论文 Example 1-2 及 E1 一致 |
| 5 | 配置 | `BLConfig/HRPConfig` 校验读码；`config_v2` 未触碰（git status） | ✅（`math` 导入悬问已定案 → F-4-3） |
| 6 | 诊断 | engine_v2.py L1370-L1385 插入点、`category`/`retryable` 口径、diagnostics.py 计数机制 | ✅ + F-4-1 扩展 HRP 侧 |
| 7 | 遗留四项 | `estimate_cov` L214-222 现状、AST P-029 实测 22/30、legacy 保留 | ✅ |
| 8 | 范围控制 | §2.2 N1-N10 对照实现面；无 Registry/context/D3 夹带；`uv lock` 零新依赖 | ✅ |
| 9 | 性能 | Woodbury O(N²K)/`pdist` O(N²)/`max_assets` 守卫；脚本不进 CI | ✅（脚本 mypy 义务补记 → F-4-7） |
| 10 | 可测性 | §10 23 例逐条可机械断言；不触碰既有断言/golden | ⚠️ #5/#7 需修订 → F-4-1/F-4-2 |

---

## 2. 门禁基线实测（E2，全部吻合 DESIGN §12）

| 项 | DESIGN §12 声称 | 实测（2026-11-23） | 结论 |
|---|---|---|---|
| pytest 全量 collect | 1440 passed / 1 skipped | **1441 collected**（1440+1 skipped 口径一致） | ✅ |
| `-k p046` | 55 | **55** | ✅ |
| `-k p054` | 120 | **120** | ✅ |
| `-k golden` | 22 | **22** | ✅ |
| black `--check .` | 319 | **319 unchanged** | ✅ |
| AST P-029 外层 / core | 22 / 30 | **22 / 30** | ✅ |
| mypy CI 同款路径 | 159 files / 0 | **Success: no issues found in 159 source files** | ✅ |

**mypy 160 目标自洽性**：CI 命令（`.github/workflows/tests.yml` L46）显式含 **`scripts`** 路径 → 新增 `scripts/p046b_bench_optimizers.py` 必使 159→160，且**该脚本必须通过 mypy 0 error 与 black**（DESIGN §11 原文未记此义务 → F-4-7 补记）。

**build_optimizer 词表变更安全性**：既有唯一未知-method 测试（test_p025_day_error_diagnostics.py L291）匹配子串 `"合法值"`，不锁 sorted 全表 → 新增 3 个 map 键不破坏既有断言 ✅。

---

## 3. 数值探针复放（E3，reviewer 独立实现）

### 3.1 BL Woodbury（DESIGN §5）— 7/7 PASS

| 性质 | 结果 |
|---|---|
| K=0 → 逐位等于 prior | ✅（不进入 solve） |
| 默认 Ω 下 τ 消去（0.05 vs 0.5） | ✅ `atol=1e-12` |
| Ω→1e-14 观点资产→Q；Ω→1e14 → prior | ✅ |
| 单观点闭式 `post = π + Σe_i(Q−π_i)/(2Σ_ii)`（τ 消去后） | ✅（与 E2 数值 [0.0905, 0.116375, 0.15775] 同链） |
| F-R2 一般性：随机 5×5 Σ（seed=42）下 `(δΣ)⁻¹post` 非观点资产位移 `<1e-10`、观点资产 `>1e-8` | ✅ |
| 零观点方差 fail-loud `ValueError` | ✅ |

### 3.2 HRP（DESIGN §6）— 论文链逐位 + 递归自洽

| 性质 | 结果 |
|---|---|
| `d = sqrt(½(1−ρ))` / `d̃` 论文 Example 1-2 | ✅ `atol=1e-4` 逐位 |
| `pdist(d)` 输出恰为论文 `d̃=[0.5659, 0.9747, 1.1225]`（§6.2 注记正确） | ✅ |
| `linkage(d̃, single)`：Z=[[0,1,0.5659,2],[2,3,0.9747,3]]，叶序 **[2,0,1]** | ✅ 与 E1/论文 Example 2 一致 |
| 递归二分（§6.3 独立复刻）：diag Σ 叶序权重 Σw=1.000000、非负 | ✅ 叶序 [0.1475, 0.5902, 0.2623] 与手算逐位一致 |
| 随机 6×6 Σ（seed=42 链）Σw=1、非负 | ✅ |
| 部分零方差 diag(0, 0.09, 0.16) | ✅ → [0.64, **0.0**, 0.36]（零方差资产权重 0，无 NaN，Σw=1） |

### 3.3 scipy 边界（§6.2/§6.4 退化分支）

| 性质 | 结果 |
|---|---|
| `linkage(pdist(1×1))` → **`ValueError: ... empty distance matrix`** | ✅ 证实 §6.2「N=1 → order=[0]」**必须**在纯函数内部显式守卫（→ F-4-6） |
| N=2 leaves=[0,1] | ✅ |
| **全零 6×6 → 叶权重 [0.25, 0.125, 0.125, 0.25, 0.125, 0.125]，Σw=1** | ⚠️ **非 1/6 均权** → F-4-1 |

---

## 4. 代码事实与测试面兼容性核对（E1）

| 事实 | DESIGN 声称 | 实测 | 结论 |
|---|---|---|---|
| `OptimizationResult` 位置构造点 | portfolio.py 内 9 处 | **9 处**（L262/345/360/392/424/456/495/553/568）+ engine_v2.py 1 处（kwargs） | ✅ |
| 引擎诊断插入点 | L1370 触发条件 `infeasible_kind is not None or message` | L1370-1384 逐字吻合；`category="config" if kind=="lower" else "optimizer"`、`retryable=False` 与 §7.2 一致 | ✅ |
| D15 对既有零方差测试的影响 | 无回归 | test_p046_engine.py `test_zero_variance_window`（L150-164）断言 `counts.get("internal", 0)==0`——`counts` 按 **stage** 键；zero_vol detail 属 stage=`rebalance`/category=`optimizer`（不在 `DEGRADED_CATEGORIES`/`RAISE_CATEGORIES`）→ 断言不受影响 | ✅ |
| `test_ac_c_04_no_nan_on_zero_raw` | 不变 | 仅断言权重无 NaN/Σ=1，不读 message | ✅ |
| RiskParity 零方差分支形态 | §8.1 拟码 | L527-542 循环形态吻合；仅方差检查 break 需置 flag（L535-536 `risk_contrib<=0` break 不属零方差，维持静默——既有行为不变） | ✅ |
| `config.py` 导入 | §4.1 悬问「math 已导入？」 | **未导入**（L9-L13）→ 定案：Step 5 必须补 `import math` | → F-4-3 |
| `estimate_cov` codes/退化现状 | D16/§8.2-8.3 | L214-215 静默交集、L221-222 无 warning，与拟码修复位吻合 | ✅ |
| 全零 cov 是否真实可达 | （未记） | `estimate_cov` 有效行 <2 → `nan_to_num` → 零矩阵 → 引擎 `len(returns_data)>=2` 放行 → **HRP 会收到全零 cov（生产路径，非纯理论）** | → F-4-1 加重 |

---

## 5. 发现与当轮修复（F-4-1..F-4-8）

| ID | 级 | 发现 | 修复（当轮完成） |
|---|---|---|---|
| **F-4-1** | **P2** | **全零 cov 规格矛盾**：§10.2 测试 #5 与 D11「全零→等权」 vs §6.3 算法 α=0.5 链→叶权重 0.5^depth（实测 N=6 得 [0.25,0.125,…] ≠ 1/6）。且全零 cov 是 `estimate_cov` 有效行 <2 的**真实生产产物**（§8.2 路径） | DESIGN §6.4/D11/§10.2 修订：**HRP 优化器层显式特判「diag 全零 → 等权 1/N」**（与 RiskParity 零方差等权回退同构），并置 `warning_kind="zero_vol"` + `message="zero_vol"`（引擎 `ZeroVariance` 同构，§4.2 措辞同步）；测试 #5 断言语义由此成立 |
| **F-4-2** | **P2** | **HRP `_precheck` 三分支未规格化**：§6.4 只写「上限型只截断留现金」，未定义 upper 结果字段（`infeasible_kind="upper"` + message，RiskParity L551-567 模板）与 lower 抛 `InfeasibleConstraintError`（引擎归类 config）——HRP 大量零权重使 lower 型不可行并非罕见 | DESIGN §6.4 表补两行（upper 透传字段 / lower 原样抛）；§10.2 测试 #7 扩断言（`infeasible_kind=="upper"` + message 非空 + `pytest.raises(InfeasibleConstraintError)`），**不新增用例，门禁数字不变** |
| F-4-3 | P3 | `core/config.py` 无 `import math`（§4.1 悬问）；`core/portfolio.py` 亦无 `math`/`Mapping`/`Sequence` 导入 | §4.1 定案改写：Step 5 须补 `config.py` 的 `import math` 与 `portfolio.py` 的 `import math` + `typing.Mapping/Sequence` |
| F-4-4 | P3 | `_bl_prior` explicit 分支：`reindex` 将**多出的**非选中资产静默丢弃，与 D5 views「warning 后丢弃」哲学不一致 | §5.1 补：prior_returns 含未入选资产时 `logger.warning` 后丢弃（与 §5.2 对称） |
| F-4-5 | P3 | §6.3 `cluster_var` 拟码 `np.where(diag>0, 1.0/diag, 0.0)` 会对零元求 1/0 触发 `RuntimeWarning`（探针实测复现） | §6.3 改 `np.divide(1.0, diag, out=np.zeros_like(diag), where=diag>0)` |
| F-4-6 | P3 | `quasi_diagonal_order` 未声明 N<2 守卫；实测 scipy `linkage` 对 N=1 抛 `ValueError` | §4.3 docstring 补「N<2 不调用 linkage，直接返回 `[0,..N-1]`/空表」 |
| F-4-7 | P3 | bench 脚本位于 CI mypy 路径（tests.yml L46 含 `scripts`）与 `black --check .` 范围 → 有 mypy/black 合规义务，§11 未记 | §11/§12 补记该义务（门禁数字不变：mypy 160、black 322 已按此口径） |
| F-4-8 | P3 | **RESEARCH §4.1 E1 权重行不可复现**：声称 Σ=diag(0.04,0.09,0.16) 的 `w(order)=[0.1665,0.5771,0.2565]`，reviewer 独立复算同设定叶序权重 = **[0.1475, 0.5902, 0.2623]**；E1 行本就声明「非 golden」（F-R4），但 Σ 标注与数值不一致会误导 Step 9 | RESEARCH §4.1 该行订正为独立复算值并注明「Σ 标注订正；不作 golden」 |

> reviewer 探针自身笔误 2 处（闭式项多除 Σ_ii、随机 Σ 维度反置）已在探针内修正后复跑，不计入被审物发现。

---

## 6. 结论

- **§13 十项**：8 项直接 PASS；2 项（#6 诊断 / #10 可测性）经 F-4-1/F-4-2 当轮修订后 PASS。
- **门禁目标 §12**：七组基线实测全部吻合；mypy 160 / black 322 口径经 CI workflow 证据证实自洽；23 例测试数经 F-4-2 修订后不变 → 门禁目标**维持原值**。
- **判档**：T1 维持；零代码变更维持。
- **放行**：Step 4 复审 **PASS**，可进入 Step 5 IMPL。

## 7. 状态链

- **2026-11-23**：Step 4 异构复审（本文）——2 P2 + 6 P3 当轮全修；DESIGN §4/§5/§6/§10/§11 与 RESEARCH §4.1 已按 F-4-1..F-4-8 修订。
- **下一步**: Step 5 IMPL（TDD；按 DESIGN §4-§8 落码，含 F-4-1 特判与 F-4-3 导入）。
