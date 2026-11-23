# CHECKLIST：P-046c F2 收尾（矩阵凯利 + 非等风险预算 + max_sharpe + 行业上限投影）

> **批次**: P-046c · **T1**（`core/config.py` / `core/portfolio.py` / `core/engine_v2.py` + 3 个新测试文件；全部新增能力 opt-in，golden 22 预期零漂移）
> **上游**: [DESIGN_p046c_f2_closeout](DESIGN_p046c_f2_closeout.md)（D1-D22 / I1-I12 / §8 测试 / §9 门禁）+ [REVIEW_p046c_step3_design](REVIEW_p046c_step3_design.md)（F-4-1..F-4-3 / O-4-1..O-4-3）+ [IMPL_p046c_f2_closeout](IMPL_p046c_f2_closeout.md)（T1-T9 / §2 签名回退 / §4 A27-A36 + B9-B15 / §5 低效排除 / §6 红→绿 / §9 F-5-1..F-5-3）+ [REVIEW_p046c_step5_impl](REVIEW_p046c_step5_impl.md)（F-6-1..F-6-3 / O-6-1..O-6-2）
> **状态**: **Step 10 ADD 审计 + RULE-5 异构终审 PASS（2026-11-23，§16）**——门禁独立重放 **10/10 全绿** / 探针独立重写重放 **8/8** / 代码 vs DESIGN 对齐 D1-D22 分组核验全过 / **0 P0-P2 + 1 观察 O-R5-P046c-1**；实测列 **79 × ✅ + J6 × 1 `[待 Step 10]`**（待用户授权提交 + CI 后回填 80/80）；零提交
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 8]` / `[待 Step 9]` / `[待 Step 10]`；**禁止预填**
> **行号口径**: 落码后行号失效；实测证据统一使用「文件 + 符号名 + 用例名 + 命令读数」
> **基线读数（@`3495683`）**: pytest collect **1464**（1463 passed + 1 skipped）/ `-k p046` **78** / `-k golden` **22** / `-k p054` **120** / mypy **160 files · 0** / black `--check .` **322** / `tests/*.py` **158** / `core/*.py` **51** / `live/**/*.py` **19** / `services/*.py` **13** / AST `except Exception` core 外 **22**、core **30** / `lint-imports` **3 kept** / `uv lock --check` exit **0**
> **实测读数（Step 9）**: collect **1503**（**1502 passed + 1 skipped**）/ `-k p046` **117** / `-k golden` **22（零重录）** / `-k p054` **120** / mypy **160·0** / black **325** / `tests/*.py` **161** / `core/*.py` **51** / `live/**/*.py` **19** / `services/*.py` **13** / AST **22 · 30** / `lint-imports` **3 kept** / `uv lock --check` exit **0**

---

## 1. A 组：配置与类型契约（8 项，锚 DESIGN §4.1 + IMPL T1）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `KellyConfig` 字段 `fraction: float=0.5`；`0<fraction≤1` 否则 `ValueError`；docstring 声明「风险厌恶单调旋钮，非字面仓位倍数；pypfopt δ=2/f」 | T1 落码 | 读码 + REPL 探针（0.5/1.0 合法）+ 用例 B4（0 / 1.5 非法） | ✅ `config.KellyConfig` 字段+校验+docstring 齐备；用例 B4 通过（0/1.5 ValueError）；全量 1502 passed 证 0.5/1.0 合法 |
| A2 | `MaxSharpeConfig` 字段 `risk_free_rate: float=0.0`；`math.isfinite` 否则 `ValueError` | T1 落码 | 读码 + REPL 探针（nan/inf 非法） | ✅ `config.MaxSharpeConfig.__post_init__` isfinite 校验；用例 B14（nan→ValueError）通过 |
| A3 | `OptimizerConfig.risk_budget: dict[str,float]\|None=None`；五校验：非空 dict / 键均 str / 值非负有限 / 和>0 / `method=="risk_parity"` 否则 `ValueError` | T1 落码 | 读码 + 探针（5 非法构造）+ 用例 A14（method 部分） | ✅ `OptimizerConfig.risk_budget` + 五校验落码；用例 A12（负值）/A14（method 错配）通过；非空/和>0 由读码确认 |
| A4 | `industry_max_weight` 校验 `0<x≤1`；**不采纳** `config_v2` L143 的 `≤max_weight` 规则（D17；`cap=0.3, max_weight=0.1` 合法） | T1 落码 | 读码 + 探针（0.3 合法）+ 用例 A14（cap 0 / 1.5 非法） | ✅ 用例 A14：cap=0/1.5 → ValueError；`cap=0.3, max_weight=0.1` 构造成功（D17 生效） |
| A5 | 末尾新增 `kelly` / `max_sharpe` 两字段（`field(default_factory=...)`）；既有四校验（max/min/target_count）逐字不变 | A1/A2 落码 | 读码 + `git diff core/config.py` | ✅ 两字段 `default_factory` 位于 `hrp` 之后；既有四校验零改动；全量 1502 passed 零回归 |
| A6 | `core/config_v2.py` **零 diff**（FROZEN/TD-2） | A1-A5 落码 | `git status --short core/config_v2.py` 空 | ✅ `git status --short` 无 config_v2.py |
| A7 | 新符号签名与 IMPL §2 一致：`project_industry_cap(weights, industry, *, cap, max_weight)`、`_risk_budget_vector(selected, raw)`、`_solve_risk_budget_convex(cov, budget)`、两优化器 3 参 `optimize_with_diagnostics` | T2/T4/T5/T6 落码 | `inspect.signature` 探针 | ✅ 四签名与 IMPL §2 一致；关键字调用在用例 C1-C8 全通过；两优化器 3 参调用在 B1-B15 全通过 |
| A8 | 导入齐备无冗余：`core/portfolio.py` 使用 `cp.psd_wrap`（cvxpy 1.9.1 可用）；`Optional`/`Mapping` 已导入；mypy/black 不报未使用 | T2/T5/T6 落码 | 读码 + mypy/black | ✅ `cp.psd_wrap` 三处使用（ERC/Kelly 复用 MVO/MaxSharpe/投影）；mypy **160·0**、black **325** 通过 |

## 2. B 组：ERC 修复（9 项，锚 DESIGN §5.1 + IMPL T3）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | **diag 预判（D3）**：任一 `diag(Σ)≤0` 或非有限 → 等权 + `zero_vol`，**不进入循环与回退**（拦部分零方差病态凸解） | T3 落码 | 读码 + 用例 A7 | ✅ 用例 A7：Σ=diag(0.04,0.09,0) → `[1/3]*3`、message/warning_kind=`zero_vol`（未落入病态凸解） |
| B2 | **快速路径逐字（D2）**：循环体保留 `target_risk_contrib = risk_contrib.mean()` / `weights * target / risk_contrib`；仅新增 `converged`/`fallback_reason` 状态 | T3 落码 | 读码 + `git diff` 循环体零 ± 行 | ✅ 循环体两行表达式逐字保留；用例 A4 权重 `[0.282638,0.226110,0.188425,0.161507,0.141319]`±1e-5、message 空 |
| B3 | 负 RC → `fallback_reason="negative_rc"` → 凸解；不得静默 break 返回等权（P1 修复） | T3 落码 | 用例 A1/A2 | ✅ 用例 A1 `[0.6,0.4]`±1e-4、RC 0.5±1e-3；A2 `erc_fallback:negative_rc` + warning_kind=`erc_fallback` |
| B4 | `max_iter` 耗尽 → `"max_iter"`；收敛后 `max\|pct−1/n\|>1e-3` → `"rc_mismatch"`；两者均凸解，不返回末次 w | T3 落码 | 用例 A6 + 读码 | ✅ 用例 A6 `erc_fallback:max_iter` + RC 仍 0.2±1e-3（凸解生效）；rc_mismatch 分支读码确认（F-S9-P046c-1 构型注记） |
| B5 | 凸模型 `min 0.5wᵀΣw s.t. w≥0, bᵀlog w≥0`；**约束列表无 `Σw==1`**；解后归一；status 非最优 → `RuntimeError` | T2/T3 落码 | 读码 + grep 约束列表 | ✅ `_solve_risk_budget_convex` 约束仅 `w>=0` + `bᵀlog w>=0`；解后归一；status 非最优 → RuntimeError；用例 A8 RC 命中 5.67e-05 |
| B6 | 两资产负相关（σ=[0.2,0.3], ρ=−0.9）→ `[0.6,0.4]`±1e-4；RC 各 0.5±1e-3 | T3 落码 | 用例 A1 | ✅ 用例 A1 通过（实测 `[0.5999994,0.4000006]`、RC `[0.499987,0.500013]`） |
| B7 | 五资产随机 SPD（seed=1）→ RC 各 0.2±1e-3；`max\|w−0.2\|>0.1`（非等权） | T3 落码 | 用例 A3 | ✅ 用例 A3：RC 全 0.200±2e-5、`max|w−0.2|`=0.2014>0.1 |
| B8 | 诊断：负 RC 路径 `message="erc_fallback:negative_rc"` + `warning_kind="erc_fallback"`；upper 分支保留约束 message；`zero_vol` 优先（不叠加） | T3 落码 | 用例 A2 + 读码 | ✅ 用例 A2/A6 诊断字段命中；upper 分支 message 逐字保留（读码）；zero_vol 优先由分支顺序保证 |
| B9 | 求解失败 fail-loud：非 OPTIMAL/INACCURATE 或值非有限 → `RuntimeError`（不返回末次 w）；`RuntimeError` 归引擎 internal | T2 落码 | 读码 + 注入非法 Σ 探针 | ✅ 读码 status 白名单 + 非正权重和双守卫；AST `except Exception` **22·30**（未新增裸 except） |

## 3. C 组：非等风险预算（7 项，锚 DESIGN §5.2 + IMPL T2）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| C1 | 多余键（不在 selected）→ `logger.warning` 后丢弃；权重结果不受影响 | T2 落码 | 用例 A9（caplog） | ✅ 用例 A9：caplog 含「已丢弃」；RC≈[0.5,0.3,0.0667×3]±1e-3 |
| C2 | 缺失键 → 均分剩余额度（`remain/n_missing`）；例：5A 指定 2 只和 0.7 → 其余各 0.1 | T2 落码 | 用例 A10 | ✅ 用例 A10：RC [0.400045,0.299963,0.099981,0.099984,0.100027] |
| C3 | 覆盖全部且和≠1 → `ValueError`；已指定部分和>1 → `ValueError` | T2 落码 | 用例 A11 + 读码 | ✅ 用例 A11（和 0.9 → ValueError「合计为 1」）；和>1 分支读码确认 |
| C4 | 配置期负值 → `ValueError`；归一后任一分量 ≤0 或非有限 → `ValueError`（零预算不被静默夹值） | A3/T2 落码 | 用例 A12 + 读码 | ✅ 用例 A12（负值→ValueError）；归一后 ≤0/非有限 ValueError 读码确认（O-4-2 从严） |
| C5 | `risk_budget` 与选中集**无交集** → 等风险 + `logger.warning`，不中断回测 | T2/T3 落码 | 用例 A13 | ✅ 用例 A13：caplog 含「无交集」；RC 各 0.2±1e-3 |
| C6 | 预算 RC 与 `b` 误差 <1e-3（b=[0.4,0.3,0.15,0.1,0.05]，S5；参考 5.67e-05） | T2/T3 落码 | 用例 A8 | ✅ 用例 A8：RC `[0.400057,0.299957,0.149971,0.099988,0.050028]`，max 偏差 **5.67e-05** |
| C7 | 预算路径**恒走凸解**（`risk_budget is not None` → 不进乘性循环），避免 E2 负权重 | T3 落码 | 读码（elif 分支）+ 用例 A8 | ✅ RP `elif self.cfg.risk_budget is not None` 分支直走凸解；用例 A8 无负权重 |

## 4. D 组：矩阵凯利（7 项，锚 DESIGN §5.3 + IMPL T4）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| D1 | `KellyOptimizer(BaseOptimizer)`，`method="kelly"`，工厂可构建；docstring 声明组合层 vs sizing 层对角近似 | T4/T7 落码 | 用例 B8 + 读码 | ✅ 用例 B8 `build_optimizer(method="kelly")` 返回 `KellyOptimizer`；docstring 双处声明层次差异 |
| D2 | `risk_aversion = 1/fraction` 映射（keyword-only 覆盖）：f=1 与 δ=1 逐位；f=0.5 与 δ=2 逐位 | T4 落码 | 用例 B3 + 读码 | ✅ 用例 B3：f=1 与 MVO(δ=1) / f=0.5 与 MVO(δ=2) 逐位一致（atol=1e-12） |
| D3 | `returns is None` → `ValueError("凯利优化需要收益率数据")`（不静默退化为 min-variance） | T4 落码 | 用例 B7 | ✅ 用例 B7 ValueError（match「凯利」） |
| D4 | 50A（seed=7）长多不变量：`w≥−1e-12`、`Σw=1±1e-8`、无 NaN | T4 落码 | 用例 B1 | ✅ 用例 B1：min w≥−1e-12、Σw=1±1e-8、无 NaN |
| D5 | 内部解闭式（对角 Σ、f=0.5、max=1）：与 `w=Σ⁻¹(μ−ν1)/(2λ)` 差 <1e-8（I5 精化口径） | T4 落码 | 用例 B2 | ✅ 用例 B2：QP 与 KKT 闭式 max\|Δ\|=1.1e-16 < 1e-8 |
| D6 | upper（n·max<1）→ `_upper_result` 各 max + 现金；empty → `_empty_result`；lower 原样抛 | T4 落码 | 用例 B5/B6 | ✅ 用例 B5（各 0.1、cash 0.5、upper）/B6（empty）；lower 由 `_precheck` 原样抛（读码） |
| D7 | `core/sizing.py` **零 diff**（P-047 对角 kelly 行为不变）；两层 kelly 命名在 docstring 消歧 | T4 落码 | `git status --short core/sizing.py` 空 + 读码 | ✅ `git status --short` 无 sizing.py；Kelly docstring 声明两层可独立启用 |

## 5. E 组：max_sharpe（7 项，锚 DESIGN §5.4 + IMPL T5）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| E1 | `MaxSharpeOptimizer(BaseOptimizer)`，`method="max_sharpe"`，工厂可构建 | T5/T7 落码 | 用例 B15 + 读码 | ✅ 用例 B15 返回 `MaxSharpeOptimizer` |
| E2 | Charnes-Cooper 形态：`(μ−rf)ᵀy==1`、`Σy==k`、`k≥0`、`y≥min·k`、`y≤max·k`、目标 `min yᵀΣy`、反变换 `round(y/k,16)+0.0`（对齐 A30） | T5 落码 | 读码 | ✅ 约束/目标/反变换逐项与 A30 同式（读码）；数值由 B9/B10 命中 |
| E3 | E4 参考：`[0.164545,0.478144,0.345451,0,0.011859]`±1e-6；Sharpe 1.385755±1e-6 | T5 落码 | 用例 B9 | ✅ 用例 B9 逐位命中（实测 Sharpe 1.3857552798） |
| E4 | 内部解闭式（对角 Σ、rf=0.02、max=1）：`w∝Σ⁻¹(μ−rf)` 差 <1e-8 | T5 落码 | 用例 B10 | ✅ 用例 B10：max\|Δ\|=4.16e-17 < 1e-8 |
| E5 | `max(μ)≤rf` → `ValueError`（与 A1/A29c 同口径） | T5 落码 | 用例 B11 | ✅ 用例 B11 ValueError（match「无风险利率」） |
| E6 | upper → `_upper_result`；empty → `_empty_result`；`risk_free_rate` 非有限在配置期抛 `ValueError` | T1/T5 落码 | 用例 B12/B14 | ✅ 用例 B12（upper、cash 0.5）/B14（nan→ValueError）；empty 由 `_precheck` 分支（读码） |
| E7 | `returns is None` → `ValueError("max_sharpe 需要收益率数据（μ）")` | T5 落码 | 用例 B13 | ✅ 用例 B13 ValueError（match「max_sharpe」） |

## 6. F 组：行业上限严格投影（9 项，锚 DESIGN §5.5 + IMPL T6）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| F1 | `IndustryCapResult` 七字段：`weights/applied/n_groups/n_unclassified/max_group_before/max_group_after/l1_deviation`，`frozen=True` | T6 落码 | 读码 + `inspect.signature` | ✅ `IndustryCapResult(frozen=True)` 七字段齐备；用例 C1-C8 逐字段访问通过 |
| F2 | `project_industry_cap(weights, industry, *, cap, max_weight)`；`cap/max_weight ∉ (0,1]` → `ValueError` | T6 落码 | 用例 C1/C8 + 读码 | ✅ 签名与关键字调用一致（C1-C8）；cap/max_weight 范围校验读码确认 |
| F3 | E8 N=100/G=10/cap=0.12（seed=400）：最大组和 =0.12±1e-9、`Σw=budget`±1e-9、L2=0.1522±1e-3 | T6 落码 | 用例 C1 | ✅ 用例 C1：max_group=0.120000000、Σ=1.000000000、L2=**0.152239**、L1=0.86 |
| F4 | E8 N=500/G=20/cap=0.08（seed=800）：0.08±1e-9、L2=0.1244±1e-3 | T6 落码 | 用例 C2 | ✅ 用例 C2：max_group=0.080000000、L2=**0.124438** |
| F5 | 未绑定（各组和 ≤cap+tol）→ **返回原 Series 逐位不变**、`applied=False`；空权重 / 零预算 → no-op | T6 落码 | 用例 C3/C6 | ✅ 用例 C3 `assert_series_equal` 逐位 + applied False；C6 空/零预算 no-op |
| F6 | 不可行（`Σ组容量 + 未分类容量 < budget` 或 `n·max_weight < budget`）→ `InfeasibleConstraintError`；求解器 INFEASIBLE 同抛 | T6 落码 | 用例 C4 | ✅ 用例 C4 `InfeasibleConstraintError`（match「不可行」）；INFEASIBLE 分支同抛（读码） |
| F7 | 行业标签 NaN 或 0 → 未分类：参与调整但不计入组约束、仍受 `max_weight`；`n_unclassified` 计数 + `logger.warning` | T6 落码 | 用例 C5（caplog） | ✅ 用例 C5：n_unclassified=2、组和 ≤0.25+1e-9、max≤0.3+1e-9；未分类 warning 读码 |
| F8 | 不在 `industry` 索引的代码（期货 `IF0001`）→ 权重**逐位不变**；`out = weights.copy()` 后仅覆盖股票子集 | T6 落码 | 用例 C7 | ✅ 用例 C7：IF0001 逐位 0.1；股票子集 Σ=0.8±1e-9 |
| F9 | cap 绑定时解满足 `w≤max_weight`（Q2 目标最小偏离）；上限仅在触发时施加（未触发不修复个股） | T6 落码 | 用例 C8 | ✅ 用例 C8：max≤0.3+1e-9；O-4-1 探针 B 段 0.4→0.3 压回 |

## 7. G 组：引擎与工厂接线（8 项，锚 DESIGN §6 + IMPL T7）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| G1 | 导入追加 `InfeasibleConstraintError, project_industry_cap`（engine L65 原行）；模块常量 `_WARNING_ERROR_TYPES = {"zero_vol": "ZeroVariance", "erc_fallback": "RiskParityFallback"}` | T7 落码 | 读码 + `git diff core/engine_v2.py` | ✅ `engine_v2` 导入块含两符号（多行形式）；`_WARNING_ERROR_TYPES` 两键与 IMPL §2 逐字一致 |
| G2 | `__init__` 增 `_industry_cap_warned=False`；`_industry_tags(date)`：`getattr(dm,"industry",None)` 为 None 或日期缺失 → **一次性** warning 并返回 None | T7 落码 | 读码 + 用例 C10（mock DM 无 industry） | ✅ `_industry_cap_warned` + `_industry_tags` 落码（一次性 warning 语义读码）；C9/C10 引擎实跑走行业表在位路径 |
| G3 | 插入点唯一：overlay/sizing/股票负权截断之后、`build_target_positions` 之前；`industry_max_weight=None` 时整块短路 | T7 落码 | 读码 + 用例 C10 | ✅ 插入块位于股票截断后、`build_target_positions` 前；用例 C10（None）权重 `[0.25]*4` |
| G4 | 诊断映射零漂移：`zero_vol` → `ZeroVariance` **逐字保留**；`erc_fallback` → `RiskParityFallback`；其余 → `InfeasibleConstraints`；`warning_kind is None` 时 `.get("", ...)` 走默认 | T7 落码 | 读码 + `test_zero_vol_records_zero_variance` 零回归 | ✅ `_WARNING_ERROR_TYPES.get(result.warning_kind or "", "InfeasibleConstraints")`；既有 zero_vol 用例零回归（全量 1502 passed） |
| G5 | 投影不可行：`_diagnostics.record(date,"rebalance",exc)` + `_emit(ERROR)` + `logger.error` + `return`（跳过当日再平衡，不中断回测） | T7 落码 | 读码 + 注入不可行 cap 探针 | ✅ 四动作齐备（record/emit/logger/return）；不可行路径由 T6 单测覆盖（C4） |
| G6 | 引擎生效（C9 构型）：4 股/3 行业（A:2,B:1,C:1）、`max_weight=0.5`、cap=0.4、equal_weight → 捕获权重 A 组 0.4±1e-9、B/C 各 0.3 | T7 落码 | 用例 C9（monkeypatch `build_target_positions`） | ✅ 用例 C9：捕获权重 A 组 0.4±1e-9、B/C 各 0.3±1e-9、Σ=1 |
| G7 | 引擎 no-op（C10 构型）：`industry_max_weight=None` → 捕获权重 `[0.25]*4`（E6 回归） | T7 落码 | 用例 C10 | ✅ 用例 C10：捕获权重 `[0.25]*4`（atol=1e-12） |
| G8 | 工厂 map 新增 `kelly` / `max_sharpe`；未知 method `ValueError` 消息仍含「合法值」；既有 8 键行为不变 | T7 落码 | 用例 B8/B15 + `test_p025` | ✅ 用例 B8/B15；未知 method 报错集含 `kelly`/`max_sharpe`；`-k p046` 117 / 全量零回归 |

## 8. H 组：不变式与零漂移（10 项，DESIGN §7 I1-I12）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| H1 | **I1** 默认 `equal_weight` + `industry_max_weight=None` → golden **22 零重录** | G3 落码 | `-k golden` + `git status tests/golden/` 空 | ✅ `-k golden` **22 passed**；`git status --short tests/golden/` 空 |
| H2 | **I2** 负相关两资产恢复解析解 + 诊断非空（`message`/`warning_kind`） | B3/B6 落码 | 用例 A1/A2 | ✅ 用例 A1/A2 通过 |
| H3 | **I3** 五资产 SPD ERC RC 各 0.2（±1e-3）、权重非等权 | B7 落码 | 用例 A3 | ✅ 用例 A3 通过 |
| H4 | **I4** 预算 ERC：RC 与 b 误差 <1e-3；b 归一、非负、逐项 >0 | C6 落码 | 用例 A8 | ✅ 用例 A8 max 偏差 5.67e-05 |
| H5 | **I5（精化）** Kelly 长多/Σw=1/无 NaN；**内部解**闭式 <1e-8（原「Σ⁻¹μ 归一」因箱体绑定不成立） | D4/D5 落码 | 用例 B1/B2 | ✅ 用例 B1/B2 通过 |
| H6 | **I6** max_sharpe 与 pypfopt 参考 <1e-6；**内部解**闭式 <1e-8 | E3/E4 落码 | 用例 B9/B10 | ✅ 用例 B9/B10 通过 |
| H7 | **I7** 投影：组和 ≤cap+1e-9、Σw=budget±1e-9、期货列逐位不变、未触发逐位不变 | F3-F8 落码 | 用例 C1-C8 | ✅ 用例 C1-C8 全通过 |
| H8 | **I8** 换手/TE 零实现；PROGRESS **P-046d** 行存在且含触发条件（零悬空） | 文档 | 读 PROGRESS + grep `turnover\|tracking_error` 新代码 0 命中 | ✅ 三源文件 grep `turnover/tracking_error/previous_weights/OptimizationContext` **0 命中**；PROGRESS P-046d 行含触发条件 |
| H9 | **I9/I11** 零新运行时依赖；`config_v2.py` / `sizing.py` / `target_positions.py` / `interfaces.py` 零 diff | A6/D7 | `git status` + `git diff --stat` | ✅ 四文件零 diff；`pyproject.toml`/`uv.lock` 零 diff；`uv lock --check` exit **0** |
| H10 | **I12** 正常路径诊断语义逐字保留：`upper`/`empty`/`lower` 消息与字段、快速路径 `message==""`、`warning_kind is None` | B2/B8 落码 | 既有用例全绿 + 用例 A4/A5 | ✅ 用例 A4/A5 message 空、warning_kind None；全量 1502 passed（既有诊断用例零回归） |

## 9. I 组：门禁（9 项，Step 7 冻结）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| I1 | pytest 全量 **collect 1503 / 1502 passed / 1 skipped**（`MPLBACKEND=Agg` + `.venv`；偏移须登记 `F-S9-P046c-*`） | A-H 落码 | 全量末行 | ✅ `pytest -q` → **1502 passed, 1 skipped**；`--collect-only -q` → **1503 tests collected**（零偏移） |
| I2 | `-k p046` **117**（78 + 39） | 测试落盘 | 命令末行 | ✅ **117 passed, 1386 deselected** |
| I3 | `-k golden` **22 passed 零重录**；`git status --short tests/golden/` 空 | 全量落码 | 命令 + `git status` | ✅ **22 passed**；golden 目录无变更 |
| I4 | `-k p054` **120**（零回归） | 全量落码 | 命令末行 | ✅ **120 passed, 1383 deselected** |
| I5 | mypy **CI 同款命令**（`tests.yml` L46，范围不含 `tests/`）→ **160 source files · 0** | 落码 | 逐字命令末行 | ✅ **Success: no issues found in 160 source files** |
| I6 | `black --check .` → **325 unchanged**（+3 测试文件），0 reformatted | 测试落盘 | 命令末行 | ✅ **325 files would be left unchanged** |
| I7 | 文件计数：`tests/*.py` **161** / `core/*.py` **51** / `live/**/*.py` **19** / `services/*.py` **13** | 落码 | `Get-ChildItem` 计数 | ✅ tests **161** / core **51** / live **19** / services **13** |
| I8 | AST `except Exception` core 外 **22**、core **30**；`lint-imports` **3 kept** | 落码 | AST 命令 + `lint-imports` | ✅ AST **22 · 30**；`Contracts: 3 kept, 0 broken` |
| I9 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零 diff | 落码 | 命令 + `git diff` | ✅ `uv lock --check` exit **0**；两文件 `git status` 空 |

## 10. J 组：文档、改动面与提交（6 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| J1 | **三文档对齐（Step 8）**：DESIGN D1-D22 ↔ IMPL T1-T9 ↔ 本 CHECKLIST A-J 无悬空；IMPL 功能点在 CHECKLIST 有验收项；机械校验读数贴出 | 本文件落盘 | Step 8 一致性报告 | ✅ [Step 8 PASS（§14）：机械校验器 v3 124/124；D1-D22 / I1-I12 / T1-T9 连续；39 例三处对齐；门禁数字三文档命中] |
| J2 | **改动面白名单**：改 3 源（`config.py` / `portfolio.py` / `engine_v2.py`）+ 新建 3 测试；零 diff 面：`config_v2.py` / `sizing.py` / `target_positions.py` / `interfaces.py` / `diagnostics.py` / `risk_overlay.py` / `tests/golden/` / `pyproject.toml` / `uv.lock` | I 组通过 | `git diff --stat` + `git status` | ✅ `git status --short` = 3 源 M + 3 新测试；九项零 diff 面全空 |
| J3 | **台账回写**：PROGRESS 主行 + 下一可用序号分节；DESIGN §14 / RESEARCH §14 / IMPL §10 状态链；CHECKLIST 实测列回填（RULE-1） | I 组通过 | 读回 diff | ✅ 本文件实测列 79 ✅ + J6 待 Step 10；PROGRESS §3.107；四文档状态链已同步 |
| J4 | **O-4-1 联测探针**：`sizing.vol_target` 放大权重 + cap 绑定 → 投影把超 `max_weight` 权重压回且组和 ≤cap；读数记入 Step 9 报告；**不新增 pytest 用例**（保 39 冻结） | F/G 落码 | Step 9 报告 | ✅ §15.4 探针：sizing/overlay 腿 clip≤1 实测不放大（scale=1.0）；外部权重 0.4→0.3 压回、组和 0.4、Σ=1；39 例不变 |
| J5 | **F 链完整性**：F-4-1/F-4-2/F-4-3、F-5-1/F-5-2/F-5-3、F-6-1/F-6-2/F-6-3 全部有落点（DESIGN/IMPL/代码/用例）；O-4-1/O-4-2/O-4-3/O-6-1/O-6-2 登记在案 | 四文档完稿 | 读四文档 + 交叉检索 | ✅ [Step 8 PASS（§14）：F-4-1..3 / F-5-1..3 / F-6-1..3 全落点 + O-4-1..3 / O-6-1..2 在案（校验器域 5 全 PASS）；Step 9 派生 F-S9-P046c-1 已登记 §15] |
| J6 | **提交与 CI**：提交原子（3 源 + 3 新测试 + 7 新文档 + 1 台账）；CI 四 job 全绿；**须用户明确授权后方可 commit/push**；CHECKLIST 实测列 80/80 | J1-J5 通过 | `git show --stat` + `gh run view` | [待 Step 10] |

---

## 11. 预填检查（RULE-1 / RULE-2）

| 项 | 读数 |
|----|------|
| 验收项总数 | **80**（A 8 + B 9 + C 7 + D 7 + E 7 + F 9 + G 8 + H 10 + I 9 + J 6 = 80，逐表行数机械计数） |
| 实测列初始状态（Step 7） | `[待 Step 9]` **77** + `[待 Step 8]` **2**（J1/J5）+ `[待 Step 10]` **1**（J6）；`✅` 0（预填=违规） |
| 实测列现状（Step 9） | `✅` **79** + `[待 Step 10]` **1**（J6）；`[待 Step 8]` / `[待 Step 9]` 均 **0** |
| 实测列终态（Step 10） | 目标 **80 × ✅** |
| 新用例数（实测） | **39 收集** = ERC/预算 14 + Kelly/Sharpe 15 + 投影/引擎 10 |
| pytest collect（实测） | **1503**（1502 passed + 1 skipped） |
| Step 9 门禁（实测） | **1502 passed / 1 skipped**、`-k p046` **117**、`-k golden` **22**、`-k p054` **120**、mypy **160·0**、black **325**、`tests/*.py` **161**、`core` **51**、`live` **19**、`services` **13**、AST **22·30**、`lint-imports` **3 kept**、`uv lock` **0** |

> RULE-2：上述统计仅来自本文件 A-J 组逐项行数机械计数与实跑命令读数；不得从设计目标或推断值转抄。

---

## 12. 范围守卫（N1-N10，不计入验收项）

| # | 不做项（DESIGN §2.2） | 机械检查 |
|---|---|---|
| N1 | 换手 L1 / 跟踪误差实现 | 新代码 `grep -n "turnover\|tracking_error"` 0 命中；无 `previous_weights` 消费 |
| N2 | in-solver 行业约束（7 优化器签名） | `optimize_with_diagnostics` 仍 3 参；无 `industry` 参数；`IOptimizer` 零 diff |
| N3 | 修改 `config_v2.py`（FROZEN/TD-2） | `git status --short core/config_v2.py` 空 |
| N4 | 修改 `core/sizing.py`（P-047 对角 kelly） | `git status --short core/sizing.py` 空 |
| N5 | 扩展 CLI `--optimizer-method` choices | `cli.py` 零 diff（仍 4 项） |
| N6 | 删除/改造 `cov_shrinkage` / `round_lot` / `round_lot_optimize` | 三符号仍在且零 diff |
| N7 | 新运行时依赖 / pypfopt 入 CI（不进 CI、不装依赖） | `pyproject.toml` / `uv.lock` 零 diff；无 `import pypfopt` |
| N8 | 多阶段 DP / `PortfolioPolicy` / Registry 统一 | 无 `policy` / `dp` / registry 新符号 |
| N9 | 删除 `_apply_constraints_legacy` | 符号仍存在且调用点仅 AC-C-01a |
| N10 | 引入 `OptimizationContext`（G-P046c-8） | 新代码无 `OptimizationContext`；PROGRESS P-046d 行承接 |

---

## 13. 状态链

- **2026-11-23**：Step 5 IMPL（[IMPL_p046c_f2_closeout](IMPL_p046c_f2_closeout.md)）+ Step 6 复审 PASS（[REVIEW_p046c_step5_impl](REVIEW_p046c_step5_impl.md)，3 P3 全修）。
- **2026-11-23**：**Step 7 CHECKLIST 落盘（本文）**——80 项验收（A 8 / B 9 / C 7 / D 7 / E 7 / F 9 / G 8 / H 10 / I 9 / J 6）；每项 DoR/DoD/证据出口；门禁目标冻结（**1503 collect / 1502 passed + 1 skipped / `-k p046` 117 / golden 22 / `-k p054` 120 / mypy 160·0 / black 325 / `tests` 161 / `core` 51 / `live` 19 / `services` 13 / AST 22·30 / lint 3 kept / uv lock 0**）；实测列 0 ✅（77×`[待 Step 9]` + 2×`[待 Step 8]` + 1×`[待 Step 10]`，RULE-1）。**零代码变更 / 未提交**。
- **2026-11-23**：**Step 8 一致性复审 PASS（§14）**——机械校验器 v3 **124/124**（初跑 v1 117/124：4 校验器正则/切分误报 + 2 文档 P3 当轮修 + 1 跟随；复跑 v2 122/124：1 连写正则误报 + 1 用例引用缺口当轮修）；J1/J5 回填 ✅；reviewer **GLM-5.3-Flash** ≠ CHECKLIST 作者 DeepSeek-V4.1-Flash（RULE-5 异构成立）。
- **2026-11-23**：**Step 9 TDD PASS（§15）**——红态 2 收集错误（`ImportError: KellyConfig / project_industry_cap`）→ 绿态 **39 passed**；门禁全命中（1502+1 / 117 / 22 / 120 / 160·0 / 325 / 161·51·19·13 / 22·30 / 3 kept / 0）；派生 **F-S9-P046c-1**（A6 构型：S5 等权起点负 RC 先于 max_iter 触发）；实测列 **79 ✅ + 1 `[待 Step 10]`**；零提交。
- **2026-11-23**：**Step 10 ADD 审计 + RULE-5 异构终审 PASS（§16）**——审计者 GLM-5.3-Flash ≠ 实施者 DeepSeek-V4.1-Flash；门禁独立重放 **10/10 全绿**（全量 1502+1 / 117 / 22 / 120 / 160·0 / 325 / 22·30 / 3 kept / 0 / 161·51·19·13）；代码 vs DESIGN 对齐 D1-D22 分组核验全过（快速路径逐字 / 凸模型无 Σw=1 / 投影 D13-D17 / 引擎 D20 / 零改动面 / N1·N7·N10 grep 0 命中）；探针独立重写重放 **8/8**（R1a 逐位复现 RESEARCH E1 原值）；**0 P0-P2 + 1 观察 O-R5-P046c-1**（未触发路径保留原 dtype，与 D16 一致）；J6 待用户授权提交。
- **下一步**：用户授权 → commit（原子：3 源 + 3 新测试 + 7 新文档 + 1 台账）→ CI 四 job 全绿 → J6 回填（80/80 ✅）→ 批次关闭。

---

## 14. Step 8 一致性复审报告（2026-11-23，PASS）

> **复审者**: GLM-5.3-Flash ≠ 本文作者 DeepSeek-V4.1-Flash（RULE-5 异构成立）
> **方法**: 机械校验器（`%TEMP%\p046c_step8_check.py` v1→v3，124 项）+ 人工定点核验；四文档基线 `3495683`；零代码变更

### 14.1 机械校验轨迹（诚实披露）

| 轮次 | 读数 | FAIL 项 | 定性 |
|---|---|---|---|
| v1 初跑 | **117/124** | `gate_161_DESIGN` / `gate_161_IMPL` / `F-4-2_in_IMPL` / `cases_design` / `cases_match` / `cl_cases_cover_impl` / `no_pypfopt_ci_CHECKLIST`（7） | 4 校验器自身 + 2 文档 P3 + 1 跟随 |
| v2 复跑 | **122/124** | `cl_case_refs_cover`（A14/B4）/ `no_pypfopt_IMPL` | 1 校验器连写正则 + 1 文档 P3 缺口 |
| v3 终跑 | **124/124** | 无 | **PASS** |

**v1 七 FAIL 逐项定性**：

- 校验器自身 4：
  - `gate_161_DESIGN` / `gate_161_IMPL`——正则 `\*\*161\*\*` 不匹配复合写法 `\*\*161 · 51 · 19 · 13\*\*`（门禁数字实为复合格式）；
  - `cases_design`——`"### 8.1"` 含 `"## 8."` 子串致 §8 切分截断（sec 仅 16 字符 → 用例数 0）；`cases_match` / `cl_cases_cover_impl` 为跟随 FAIL；
- 文档 P3 2（当轮修）：
  - IMPL 无 `F-4-2` 单独字面（仅有「F-4-1..F-4-3」范围写法）→ §3.3 骨架补 `# F-4-2：zero_vol break 不误判 max_iter` 标签注释（L278）；
  - CHECKLIST N7 无「不进 CI」字样 → 措辞增强为「新运行时依赖 / pypfopt 入 CI（**不进 CI、不装依赖**）」。

**v2 两 FAIL 逐项定性**：

- 校验器 1：IMPL §4 对拍边界 L639 已有「**不得把 pypfopt 加入依赖或 CI**」等价表述（v2 仅匹配「不进 CI」字面过严）；同轮发现连写引用「用例 A4/A5」「B5/B6」「B12/B14」「C3/C6」未被 v2 拆分——**A5 / B6 / B14 / C6 实已被引用**（正则误报）；
- 文档 P3 1（当轮修）：**A14 / B4 在 CHECKLIST 无任何引用**（Step 9 跑用例后无验收项挂靠，可追溯性缺口）→ A1 行证据出口补「用例 B4（0 / 1.5 非法）」、A3 行补「用例 A14（method 部分）」、A4 行补「用例 A14（cap 0 / 1.5 非法）」。

### 14.2 一致性九域结论（v3 全 PASS）

| # | 校验域 | 读数 |
|---|---|---|
| 1 | 四文档存在 + 引用链（REVIEW step2/2b/3/5 上游齐备、D↔R3 / I↔R6 / C↔I↔D） | ✅ |
| 2 | CHECKLIST 结构：80 项（A 8 / B 9 / C 7 / D 7 / E 7 / F 9 / G 8 / H 10 / I 9 / J 6）、实测列 77+2+1、回填前 ✅ 预填 0、N1-N10 齐、**39 用例编号全覆盖**（含连写拆分与 `C1-C8` 范围展开） | ✅ |
| 3 | D1-D22 / I1-I12 / T1-T9 编号连续无悬空 | ✅ |
| 4 | 门禁数字冻结：1503 / 117 / 325 / 161 于 DESIGN+IMPL+CHECKLIST 命中；1503 亦在 RESEARCH | ✅ |
| 5 | F 链（F-4-1..3 / F-5-1..3 / F-6-1..3）+ O 链（O-4-1..3 / O-6-1..2）落点齐备 | ✅ |
| 6 | U1-U12 全关闭（12 行均映射 D 项 + 「全部关闭」表述） | ✅ |
| 7 | 新符号 8 个（`risk_budget` / `project_industry_cap` / `erc_fallback` / `KellyOptimizer` / `MaxSharpeOptimizer` / `KellyConfig` / `MaxSharpeConfig` / `IndustryCapResult`）三文档齐 + 锚点 A27-A36（16 行）/ B9-B15（7 项） | ✅ |
| 8 | 39 例三处对齐（DESIGN §8 = IMPL §6.2 = 39 唯一名）+ 凸模型无 `Σw==1` + `cp.log(w)` 在位 | ✅ |
| 9 | 术语（`negative_rc` / `max_iter` / `rc_mismatch`、`RiskParityFallback`、`InfeasibleConstraintError`）+ pypfopt 排除（IMPL L639 / CK N7）+ O-4-1 探针节（§6.4）+ P-046d 零悬空（触发条件 + OptimizationContext 承接） | ✅ |

### 14.3 回填与后续

- 本节 PASS 后回填：**J1 / J5 → ✅**（回填发生在 v3 读数之后；`08 cl_no_prefill` 单项按「回填前口径」失效属预期，非违规——RULE-1 允许 Step 8 项在 Step 8 内回填）；实测列现状 **77 × `[待 Step 9]` + 2 × ✅（J1/J5）+ 1 × `[待 Step 10]`（J6）= 80**。
- 当轮累计修复 4 处文档 P3（IMPL F-4-2 标签、CK N7 措辞、CK A1/A3/A4 用例引用），全部为措辞/引用级，零代码变更、零门禁数字变更。
- **下一步**：Step 9 TDD（红→绿 39 例 + O-4-1 手工探针 + 门禁实测回填 I1-I9 / H 组 / A-J 实测列）。

---

## 15. Step 9 TDD 报告（2026-11-23，PASS）

> **实施者**: DeepSeek-V4.1-Flash（Step 10 复审须 reviewer ≠ 实施者）；基线 HEAD `3495683`；门禁目标全部命中、零偏移

### 15.1 红 → 绿轨迹

| 阶段 | 读数 | 说明 |
|---|---|---|
| 红（3 测试文件先行） | **2 收集错误** | `ImportError: cannot import name 'KellyConfig'`（config）/ `'project_industry_cap'`（portfolio）→ 与 IMPL §6.1 预期一致；ERC 文件因只依赖既有符号已可收集 |
| 绿（第 1 轮） | **34 passed / 5 failed** | 三类失败见 §15.2（2 类测试构型 + 1 类笔误） |
| 绿（第 2 轮） | **39 passed** | 3 文件全绿（14 / 15 / 10） |

### 15.2 绿态前的三处修正（全部为测试侧，零实现缺陷）

| # | 失败 | 根因 | 处置 |
|---|---|---|---|
| 1 | A6 期望 `max_iter` 实得 `negative_rc` | **F-S9-P046c-1**：S5 等权起点 RC 含负分量（−0.006358），D3 条件②（负 RC）先于③（max_iter）触发；Step 4「一步 Δ=8.69」复算未覆盖等权起点符号 | 改用 A4 等相关构型（等权 RC 全正：0.0235–0.0582；一步 max\|Δw\|=0.1415 ≫ tol=1e-12）隔离③；断言与容差不变 |
| 2 | C1/C2 `applied=False`、`n_unclassified=10/25` | E8 构型行业码取 0..G−1，与 **D14 的「0=缺失填充」哨兵**冲突（组 0 被计为未分类） | 测试行业码平移为 **1..G**；分组结构与随机流不变 → cap/Σ/L2 读数与 E8 原值一致（0.152239 / 0.124438） |
| 3 | C9/C10 `ValueError: Shape ... (4,1) vs (5,4)` | 引擎夹具 `pd.DataFrame(list, index=DATES, columns=CODES)` 缺 tile | 改 `np.tile(..., (len(DATES), 1))` |

> 实现侧零修正：T1-T7 骨架落码后即通过 34/39，3 处失败全部定位在测试构型。

### 15.3 门禁实测（全命中，零偏移）

| 指标 | 目标 | 实测 |
|---|---|---|
| pytest collect / 全量 | 1503 / 1502+1 | **1503 / 1502 + 1** |
| `-k p046` | 117 | **117 passed** |
| `-k golden` | 22（零重录） | **22 passed**；`git status tests/golden/` 空 |
| `-k p054` | 120 | **120 passed** |
| mypy（CI 同款） | 160·0 | **160 source files · 0** |
| black `--check .` | 325 | **325 unchanged** |
| 文件计数 | 161·51·19·13 | **161 · 51 · 19 · 13** |
| AST / lint / lock | 22·30 / 3 kept / 0 | **22 · 30 / 3 kept, 0 broken / 0** |

**改动面**（`git status --short`）：3 源 M（`core/config.py` / `core/portfolio.py` / `core/engine_v2.py`）+ 3 新测试 + 9 文档；九项零 diff 面（含 `config_v2` / `sizing` / `target_positions` / `interfaces` / `golden` / `pyproject` / `uv.lock`）全空。

### 15.4 O-4-1 联测探针（不入库、不进 pytest；39 例冻结不变）

链路：`equal_weight` 0.25×4 → `apply_sizing(method="kelly")` → `project_industry_cap(cap=0.4, max_weight=0.3)`。

| 段 | 输入 | 输出 | 结论 |
|---|---|---|---|
| A（sizing 腿） | kelly 缩放后 `[0.25]*4`，scale=**1.0** | 投影 → `[0.2,0.2,0.3,0.3]`；max=0.3、A 组=0.4、Σ=1、L1=0.2 | **sizing/overlay 腿实测不放大**：`kelly_fraction_scale` 与 `vol_target_scale` 均 clip ≤1（原 O-4-1「放大」前提不成立，如实记录）；cap 触发时个股上限 0.3 生效 |
| B（外部权重，引擎 weights 模式可达） | `[0.4,0.2,0.2,0.2]`（max 0.4 > 0.3） | 投影 → `[0.3,0.1,0.3,0.3]`；max=0.3、A 组=0.4、Σ=1、L1=0.4 | **超限权重被压回 max_weight**，组和 ≤cap，Σ 保持 |

### 15.5 派生需求登记

| ID | 内容 | 落点 |
|---|---|---|
| **F-S9-P046c-1** | DESIGN §8.1 A6 构型不可达：S5 等权起点 RC 含负分量（−0.006358）→ 条件② `negative_rc` 先于③ `max_iter`；A6 改用 A4 等相关构型（等权 RC 全正、一步 0.1415） | 本表 + DESIGN §8.1 A6 注记 + IMPL §6.2 A6 注记 + PROGRESS §3.107 |

### 15.6 下一步

- **Step 10 ADD 审计 + RULE-5 异构终审**（reviewer ≠ 本步实施者）：门禁独立重放、F 链/O 链核验、CHECKLIST 79→80 回填（J6）、提交授权 + CI 四 job。

---

## 16. Step 10 ADD 审计 + RULE-5 异构终审报告（2026-11-23，PASS）

> **审计者**: GLM-5.3-Flash ≠ Step 9 实施者 DeepSeek-V4.1-Flash（RULE-5 异构成立）
> **审计范围**: P-046c 全部改动面（`core/config.py` / `core/portfolio.py` / `core/engine_v2.py` + 3 新测试）；基线 HEAD `3495683`
> **方法**: ADD 四阶段（Phase 0 范围确认 → Phase 1 门禁独立重放 → Phase 2 代码 vs DESIGN 对齐 → Phase 3 探针独立重放 → Phase 4 结论）；探针为审计者独立重写（`%TEMP%\p046c_step10_add_probe.py`，不复用实施者脚本）

### 16.1 Phase 1：门禁独立重放（10/10 全绿，零偏移）

| # | 门禁 | 目标 | 审计重放 | 判定 |
|---|---|---|---|---|
| 1 | pytest 全量 | 1502 + 1 skipped | **1502 passed, 1 skipped**（170s） | ✓ |
| 2 | `-k p046` | 117 | **117 passed** | ✓ |
| 3 | `-k golden` 零重录 | 22 + 目录无变更 | **22 passed** + `git status tests/golden/` 空 | ✓ |
| 4 | `-k p054` | 120 | **120 passed** | ✓ |
| 5 | mypy CI 同款 | 160·0 | **Success: no issues found in 160 source files** | ✓ |
| 6 | black `--check .` | 325 | **325 files would be left unchanged** | ✓ |
| 7 | AST `except Exception` | 22 · 30 | **22 · 30** | ✓ |
| 8 | `lint-imports` | 3 kept | **3 kept, 0 broken** | ✓ |
| 9 | `uv lock --check` | exit 0 | **exit 0**（Resolved 139 packages） | ✓ |
| 10 | 文件计数 | 161·51·19·13 | **161 · 51 · 19 · 13** | ✓ |

### 16.2 Phase 2：代码 vs DESIGN 对齐（D1-D22 分组核验）

| 组 | 核验项 | 审计方式 | 判定 |
|---|---|---|---|
| ERC（D2/D3/D4/D5） | diag 预判 / 快速路径两行逐字 / F-4-2 前置 / 凸回退在 else 内 / rc_mismatch 闸门 / 诊断 zero_vol 优先 | 读码 [portfolio.py L902-L962](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L902-L962) + grep `target_risk_contrib = risk_contrib.mean()` 逐字命中 | ✓ |
| 预算（D6/D7） | `_risk_budget_vector` 归一规则五分支 / `_solve_risk_budget_convex` 约束无 `Σw==1` | 读码 + 用例 A8-A13 | ✓ |
| Kelly（D8/D9/D21） | `risk_aversion=1/f` keyword / `KellyConfig` 嵌套 / upper 复用 `_upper_result` | 读码 + 用例 B1-B8（B3 δ 映射逐位 1e-12） | ✓ |
| MaxSharpe（D10/D11/D22） | Charnes-Cooper 六约束 + `round(16)+0.0` / `MaxSharpeConfig` / pypfopt 参考常量固化（不 import） | 读码 + 用例 B9-B15（B9 逐位 1e-6） | ✓ |
| 投影（D12/D13/D14/D15/D16/D17） | 交集 stocks / budget=Σ股 / 组约束 / NaN·0 未分类 + warning / 容量预判 + INFEASIBLE 同抛 / 未触发逐位 / cap 校验 | 读码 [portfolio.py L1059-L1149](file:///f:/Coding/Factor_Trading_v3.0/core/portfolio.py#L1059-L1149) + 用例 C1-C8 | ✓ |
| 引擎（D12/D15/D20） | 单插入点（截断后/`build_target_positions` 前）/ ICE 四动作 / applied logger.info 四数 / `_industry_tags` 一次性 warning | 读码 [engine_v2.py L1519-L1553](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1519-L1553) + 用例 C9/C10 | ✓ |
| 零改动面（D19） | HRP 区段 / `MinVarianceOptimizer` / `config_v2` / `sizing` / `interfaces` / `golden` | 读码 + `git status` 九项零 diff 全空 | ✓ |
| 守卫（N1/N7/N10） | 三源 grep `turnover/tracking_error/previous_weights/OptimizationContext/import pypfopt` | grep **0 命中**（`turnover` 命中均在既有 `analytics/guard_pipeline/risk_monitor`，非本批改动面） | ✓ |

### 16.3 Phase 3：探针独立重放（8/8 PASS）

| # | 探针 | 读数 | 判定 |
|---|---|---|---|
| R1a | RESEARCH E1 P1 场景（2A 负相关） | w=`[0.599999,0.400001]`、rc=`[0.499987,0.500013]`、`erc_fallback:negative_rc`——与 RESEARCH §15 原值逐位一致 | ✓ |
| R1b | 5 资产随机 SPD（seed=42） | rc_max_dev=**1.23e-05**（等风险） | ✓ |
| R2a | 预算缺失补剩余（指定 A=0.5） | rc=`[0.5, 0.125×4]` | ✓ |
| R2b | 部分和>1 | `ValueError(已指定部分之和 1.200000 > 1)` | ✓ |
| R3 | O-4-1 外部权重压回 | pre_max=0.4 → post_max=0.3、组=0.4、Σ=1 | ✓ |
| R4 | D16 未触发 + int dtype | 逐位不变（含 `IF0001=1` 原值保留） | ✓ |
| R4b | 触发 + int dtype | 期货保留 1、dtype→float64、A+B 压至 0.5、Σ=0.9+1 | ✓ |
| R5 | 不可行 | `InfeasibleConstraintError`（含 budget/capacity 全参数） | ✓ |

### 16.4 Phase 4：结论

- **判定**：**PASS**。**0 P0 / 0 P1 / 0 P2**；1 观察登记：
- **O-R5-P046c-1**（观察，登记不修）：`project_industry_cap` 未触发路径返回原 Series **保留原始 dtype**（int 亦原样）；触发路径整体提升 float64 但期货列保留原值。与 D16「逐位不变」语义一致；引擎路径 `target_weights` 恒为 float（optimizer 输出），非 float 输入仅出现在直接函数调用场景，不构成行为缺陷。
- **RULE-5 异构终审**：审计者（GLM-5.3-Flash）≠ DESIGN/IMPL/CHECKLIST 作者与 Step 9 实施者（DeepSeek-V4.1-Flash）；探针独立重写重放；门禁独立重放 10/10。
- **J6 前置全绿**：J1-J5 ✅；实测列 79 ✅ + J6 待用户授权提交后回填。
