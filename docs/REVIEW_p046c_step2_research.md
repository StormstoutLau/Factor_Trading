# REVIEW：P-046c Step 2 RESEARCH 异构复审

> **批次**: P-046c · **Step 2**（被审物：[RESEARCH_p046c_f2_closeout](RESEARCH_p046c_f2_closeout.md) 全文，2026-11-23 Step 1 版）
> **复审基座**: **GLM-5.3-Flash**（≠ RESEARCH 作者 DeepSeek-V4.1-Flash）→ **RULE-5 异构成立**
> **方法**: C1-C20 逐项对码（文件+行号+语义）→ E1-E7 独立重写重放（复审者自写探针，不复用作者代码）→ A1-A7 对 wheel 源码 → B1-B8 越界检查 → 门禁独立复跑 → 方案/未决/不变式/DoD 审查 → 范围守卫
> **结论**: **PASS**——**0 P1 / 0 P2 / 4 P3 当轮全修（F-R2-1..4）+ 2 项观察登记（F-R2-5/6）**；E1 的 P1 判定**同意**；B1a/B2a/B3a/B4b 方案取舍**认可**；U7 scope 建议（延后 P-046d）**认可**；基线读数独立复跑全部命中

---

## 1. 代码事实核对（C1-C20，20/20 PASS）

| # | 文档锚点 | 复核方式 | 判定 |
|---|---|---|---|
| C1 | portfolio.py L881-L903 `optimizer_map` 8 键；config.py L322 `method` | 本轮读码（map 全文 + config 字段） | ✅ |
| C2 | RiskParity 乘性迭代、无 budget、break L749-L750 | 读码 L717-L794；grep `budget` 全文件命中均在 `_scale_to_budget`（权重缩放预算，非风险预算） | ✅ |
| C3 | zero_vol 仅 `variance<=0`；负 RC break 零诊断 | 读码 L738-L750（`zero_vol=True` 仅在该分支）、L762-L794（tail） | ✅ |
| C4 | `_upper_result`/`_solve_mean_variance` L520-L586；MinVariance L589-L650 零改动；BL L685-L714 组合式 | 读码三段 | ✅ |
| C5 | core/ 无 `max_sharpe`/`tracking_error`；`industry_max_weight` portfolio 零消费 | **本轮独立 grep**：`max_sharpe\|tracking_error` core/ **0 命中**；`industry_max_weight\|risk_budget\|budget` portfolio.py 命中均为缩放预算语义 | ✅ |
| C6 | `round_lot_optimize` L849-L878 仅定义零调用 | 读码 + 全仓 grep（唯一命中即定义处；docs/CODE_WIKI 为文档） | ✅ |
| C7 | `cov_shrinkage` L340 deprecated 零消费 | 读码；grep 全仓仅 config.py L340 + config_v2.py L137（冻结资产） | ✅ |
| C8-C11 | sizing.py L180-L197 / L243-L359 / L306-L311 / L223-L235 | 本轮全文读码（458 行） | ✅ |
| C12 | config.py L311-L358 字段 + `__post_init__` 四校验 | 读码 | ✅ |
| C13 | engine L1508-L1517 `build_target_positions(..., round_lot=...)` | 读码 | ✅ |
| C14 | interfaces.py L231-L249 `IOptimizer` 2 参；engine L1366-L1368 3 参调用 | 读码 | ✅ |
| C15 | engine L1350-L1368 仅 returns+cov，无行业/基准/上期权重 | 读码 | ✅ |
| C16 | data.py L164-L169 `industry` property、L383 加载；filter/industry.py L64-L166 | 读码/grep | ✅ |
| C17 | config.py L455 `benchmark: str \| None = None  # 基准指数（暂留接口）` | 读码 | ✅ |
| C18 | config_v2.py L13「生产代码零引用」+ L128/L137/L143 | 读码 + grep（仅 tests/test_config_v2.py 引用） | ✅ |
| C19 | test_p046_constraints L21 METHODS、L85-L92 仅无 NaN/Σw 断言 | 读码；全 tests grep 无负相关/RC 相等用例 | ✅ |
| C20 | target_positions.py L49-L50、L131-L132 整手落地 | 读码/grep | ✅ |

---

## 2. 数值取证重放（E1-E7，复审者独立重写探针；7/7 语义命中）

构造参数取自被审文档 §4；探针代码由复审者独立实现（不同于作者代码路径）。

| # | 文档读数 | 复攻读数 | 判定 |
|---|---|---|---|
| E1-2A | eig `[0.0054936978, 0.1245063022]`；RP `[0.5,0.5]`、RC `[-0.636364,1.636364]`、`message=""`/`warning_kind=None`；解析/cvxpy `[0.6,0.4]`；偏差 0.10 | **逐位命中**（cvxpy RC `[0.499991,0.500009]`，末位求解器噪声）；max\|rp−analytic\|=0.10 | ✅ |
| E1-5A | RP `[0.2]*5`；真 ERC `[0.200212,0.401383,0.278986,0.074362,0.045056]`；max\|diff\|=0.2014 | true `[0.200215,0.401381,0.278986,0.074362,0.045057]`（1e-6 级求解器噪声）；**max\|diff\|=0.2014** | ✅ |
| E2 | cvxpy `w=[0.225442,0.422340,0.287002,0.034918,0.030297]`、max\|RC−b\|=5.67e-05；乘性 `[1.514333,-1.517127,...]` 负权重 | **w/RC 逐位命中**；max\|rc−b\|=5.67e-05；naive w **逐位命中**（neg=2） | ✅ |
| E2-timing | N=50 0.136s / N=200 0.348s / N=500 0.913s | **0.018s / 0.127s / 0.964s**——同一机器两次重放差异巨大（见 F-R2-3）；量级结论（N=500 亚秒级）成立 | ⚠️ F-R2-3 |
| E3 | diag vs matrix_clip max\|diff\|=0.165937；50A cond 3.78e3 / max\|w\|=13.36 / neg 22；LW cond 12.9 / 1996.41 / 10 neg；ridge 3.29e2 / 1.69 / 15 | **全部逐位命中**（0.165937 / 3.78e+03 / 13.36 / 22 / 1.29e+01 / 1996.41 / 10 / 3.29e+02 / 1.69 / 15）；但 LW 样本 X 构造未文档化（见 F-R2-2），复审按作者上下文恢复构造后复现 | ✅ / F-R2-2 |
| E4 | cvxpy vs pypfopt **5.55e-17**；Sharpe 1.38575528；无箱体闭式 1.94e-16 | **全部逐位命中** | ✅ |
| E5 | in-solver `[0.4,0.4,0.2]`；post-proj `[0.515420,0.473385,0.011194]` 违反 cap | **逐位命中** | ✅ |
| E6 | `industry_max_weight` max\|diff\|=0.00e+00 | **命中** | ✅ |
| E7 | equicorr old `[0.282638,...]` vs cvxpy `[0.282643,...]`、max\|diff\|=5.37e-06；sample 20A 0.0000 | **逐位命中**（rc 均 0.2 / 0.05）；sample X 构造（seed=2026）未文档化（F-R2-2） | ✅ / F-R2-2 |

**P1 判定（E1）：同意**。两资产解析推导独立验证：两资产 ERC ⟺ `w1σ1=w2σ2` ⟺ 权重 ∝ 逆波动率（对任意 ρ 成立），`[0.6,0.4]` 为精确解；现有实现返回 `[0.5,0.5]` 且零诊断，`RiskParityOptimizer` 名不符实。C19 证实无测试保护 → P1 定级成立。

---

## 3. 外部锚点核验（A1-A7，7/7 PASS；B 级无越界）

| ID | 锚点 | 复核方式 | 判定 |
|---|---|---|---|
| A1 | pypfopt `efficient_frontier.py` L225-L293 `max_sharpe` | 本轮 grep（`def max_sharpe` L225）+ 读 L226-L293：变量变换、`(μ−rf)ᵀw==1`、`Σw==k`、约束按 k 缩放、`w=y/k`、Cornuejols & Tutuncu 引用 | ✅ |
| A2 | 同文件 L332-L378 `efficient_risk` | grep（`def efficient_risk` L332）+ 读 L340-L378：`variance <= target_variance` 参数化、`global_min_volatility` 校验 | ✅ |
| A3 | `objective_functions.py` L168-L226 | grep + 读 L160-L226：`transaction_cost=k·‖w−w_prev‖₁` L168-L183、`ex_ante_tracking_error` L186-L202、`ex_post_tracking_error` L205-L226 | ✅ |
| A4 | `risk_models.py` L356/L418/L438 | grep 命中三行 | ✅ |
| A5 | skfolio `_risk_budgeting.py` L27-L44、L95-L101 | 读 L26-L110：凸问题 `budgetᵀlog(w)≥0, 1ᵀw=s, Aw≤s·b, w≥0`；`risk_budget=None` → 等风险 | ✅ |
| A6 | skfolio `_mean_risk.py` L792-L905、L1106-L1109 | grep（`__init__` L792、`risk_aversion` L796/L905）+ 读 L1101-L1120（`MAXIMIZE_RATIO` factor 分支 L1106-L1109） | ✅ |
| A7 | riskfolio `Portfolio.py` L3465-L3493、L4315-L4335 | 读 L3463-L3523（`rp`：`bᵀlog(w)≥c`、`Aw≤b`）+ L4306-L4340（`rb.T @ log_w >= 1` + `cp.ExpCone`） | ✅ |

**B 级越界检查**：B1-B8 仅出现在 §5.2 书目表；实现建议（B1a/B2a/B3a）均由 A 级锚点 + 本地探针双证支撑（B8 的 max_sharpe 变换实际由 A1 wheel 源码 docstring L230-L231 + E4 探针佐证）。**无 B 级单独支撑实现结论的越界**。

**版本核验**：`%TEMP%\p046b_pkgs` 实存 pypfopt 1.5.5 / skfolio 1.14.4 / riskfolio-lib 7.4.1（dist-info 目录名），与 §15 声明一致。

---

## 4. 门禁基线独立复跑（@`3495683`，本基座实测）

| 门禁 | 文档声明 | 复审实测 | 判定 |
|---|---|---|---|
| pytest collect | 1464 | **1464** | ✅ |
| 合并子集（p046+golden+p054） | 78 / 22 / 120 | **220 passed**（= 78+22+120，逐文件分布核对） | ✅ |
| 全量 | 1463 passed + 1 skipped | 后台重放（P-046b Step 10 审计已两次独立命中 1463+1；代码自 `f272638` 后零变更，`3495683` 仅 +5 docs） | ✅ |
| mypy | 160·0 | **160 source files, 0 error** | ✅ |
| black | 322 | **322 unchanged** | ✅ |
| AST | 22 / 30 | **22 / 30** | ✅ |
| lint-imports | 3 kept | **3 kept, 0 broken** | ✅ |
| uv lock | 0 | exit **0** | ✅ |
| 文件计数 | 158·51·19·13 | **158 / 51 / 19 / 13** | ✅ |
| 工作区 | 零代码变更 / 未提交 | `git status`：仅 `docs/PROGRESS.md`（M）+ `docs/RESEARCH_p046c_f2_closeout.md`（??），无代码文件 | ✅ |

---

## 5. 方案矩阵 / 未决项 / 不变式 / DoD 审查

### 5.1 方案取舍（认可）

- **B1a**（ERC 原地修复 + cvxpy 回退）：E7 证明快速路径与现有行为一致（sample 例 0.0000）；E2 证明乘性迭代对非均匀预算出负权重 → 回退必要。B1b 的「旧 RP 仍错（P1 未修）」与 B1c 的性能退化（E2 timing）否定理由均成立。
- **B2a**（`KellyOptimizer` 复用 `_solve_mean_variance`，δ=1/f）：E3 证明矩阵逆直接归一不可用（22 负权重 / cond 3.78e3 / LW 后仍 1996），长多 QP 是唯一可行路径；复用现有求解器使箱体/upper/empty 语义自动一致。代价栏「需给 `_solve_mean_variance` 增可选 risk_aversion 覆盖」与现签名 `(expected_returns, cov, cfg, selected, method, *, feas=None)`（内部用 `cfg.risk_aversion`）一致。
- **B3a**（Charnes-Cooper）：E4 与 pypfopt 5.55e-17 逐位一致，`max(μ)<=rf → ValueError` 口径与 pypfopt L244-L247 同源；upper 型走 `_upper_result` 与 U1-A 一致。
- **B4b**（行业/换手/TE 延后 P-046d）：E5 证明行业上限必须进 solver，而引擎上下文（行业/上期权重/基准）缺失（C15/C16/C17）→ 本批做行业上限须同时扩引擎输入面（双扩）；延后并与 `industry_max_weight` 死配置处置绑定（U9）是零悬空的。

### 5.2 未决项（U1-U12）

- **U7 为真正的 scope 裁决**（本批实现行业上限 vs 延后 P-046d）：复审意见支持 **B4b 延后**；若裁决为 B4a，测试数与 T 数上调须在 Step 3 冻结门禁时体现。
- U2「缺失补 1/N」存在混合归一歧义（部分显式 + 部分补默认时总和≠1，需定义归一规则）→ **F-R2-6 观察**，Step 3 精化。
- 其余 U1/U3-U6/U9-U12 建议默认与方案矩阵一致，无需前置用户裁决（Step 3 设计期可关闭）。

### 5.3 不变式 / DoD

- I1-I10 可机械验证（I2 的 ±1e-6、I5 的 <1e-10 与 E4/E7 重放精度相容；I4「无约束时与 `Σ⁻¹μ` 归一 <1e-10」**注意**：该断言仅对无负权重的 μ/Σ 成立，E3 已证一般情形 `Σ⁻¹μ` 有负分量——设计期须把 I4 的对拍限定为「构造正权重闭式例」，否则用例不可构造。→ **F-R2-5b 观察**，Step 3 精化 I4 表述）。
- A1-A10 判据完整；A7「≥20 例，Step 3 冻结」合规（不预填）。

---

## 6. 发现与处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-R2-1 | P3 | §6.1 B1a 优点「正常路径零漂移（E7 5.37e-06）」语义混用：5.37e-06 是「现有乘性 vs cvxpy 参考」之差，而「零漂移」指修复后快速路径对现有行为不变（=0）；现文易误读 | **当轮订正** §6.1 B1a 与 §4 E7 结论措辞 |
| F-R2-2 | P3 | E3 的 LW 样本 X 构造与 E7 的 60×20 收益矩阵构造（rng=2026、`common·0.7 + N(0,0.008)`）未写入正文/§15——重放者无法仅凭文档复现（复审靠作者会话上下文恢复构造后逐位命中 1996.41/10 与 0.0000） | **当轮补** §15 构造说明 |
| F-R2-3 | P3 | E2 性能读数（0.136/0.348/0.913s）为单次测量且不可复现（复审重放 0.018/0.127/0.964s，同机差异达 7 倍）；量级结论（N=500 亚秒级）成立，但精确值有误导性 | **当轮加注**「单次测量、机器相关、仅量级参考」并改区间表述 |
| F-R2-4 | P3 | B1a 描述未覆盖「快速路径迭代不收敛（max_iter 内 tol 未达，现有代码同样静默返回末次 w）」分支；修复设计须显式处理（收敛性检查 → 不满足则回退 cvxpy），否则 P1 仅修一半 | **当轮补** §6.1 B1a 回退条件 |
| F-R2-5 | 观察 | 命名冲突面：`OptimizerConfig.method="kelly"`（拟新增）与 `SizingConfig.method="kelly"`（P-047 对角）同名不同层；且 portfolio.py 已有 `budget` 一词（`_scale_to_budget` 权重预算）与新「风险预算」撞词 | 登记；Step 3 命名须显式消歧（RESEARCH §6.2 已当轮补提醒） |
| F-R2-6 | 观察 | U2「缺失补 1/N」混合归一歧义；I4「无约束对拍 `Σ⁻¹μ`」仅对正权重闭式例可构造 | 登记；Step 3 精化 |

**统计：0 P1 / 0 P2 / 4 P3（当轮全修）/ 2 观察。**

---

## 7. 当轮修复记录（已回写 RESEARCH）

1. §4 E2 性能句 + §15：加「单次测量、机器相关、仅量级参考」注（F-R2-3）。
2. §4 E7 结论、§6.1 B1a：「零漂移」改写为「对现有行为零漂移；与 cvxpy 参考差 5.37e-06」（F-R2-1）。
3. §6.1 B1a：回退条件补「快速路径不收敛（max_iter 内 RC 未达 tol）亦回退」（F-R2-4）。
4. §15：补 E3 LW 样本 X 构造与 E7 收益矩阵构造（rng/公式）（F-R2-2）。
5. §6.2：补 `kelly` 命名消歧提醒（F-R2-5）。
6. §14 状态链：补 Step 2 复审行；头部「状态」行更新。

---

## 8. 范围守卫

- 无 P-046b 重做（BL/HRP 仅出现在「不做」与遗留表现状列）。
- 无 P-053 夹带（`round_lot`/`round_lot_optimize` 明确「不动」，归属 P-053）。
- P-046d 仅作为延后归属登记，无实现内容混入。
- 零新运行时依赖（外部三包仅手工对拍；`%TEMP%` 缓存不入库）。
- `config_v2` FROZEN：文档处置建议（删除 `industry_max_weight`）明确限定 `core/config.py` + 冻结例外声明（I10）。

---

## 9. 结论

**Step 2 异构复审 PASS**：C1-C20 20/20、E1-E7 7/7（E2 timing 例外已作 F-R2-3 处置）、A1-A7 7/7、门禁基线全命中、方案与 scope 审查通过；0 P1/P2，4 P3 当轮全修，2 观察登记并指定 Step 3 精化点。**RESEARCH_p046c_f2_closeout 可进入 Step 3 DESIGN**；U7（行业/换手/TE scope）与 U9（死配置删除 vs 标注）建议在 Step 3 前由用户裁决。
