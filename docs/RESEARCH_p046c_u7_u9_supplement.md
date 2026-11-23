# RESEARCH（补充）：P-046c U7/U9 决策锚点——行业上限 / 换手 / 跟踪误差 scope 与死配置去向

> **批次**: P-046c · **补充调研**（Step 2 复审后，用户要求补充社区案例 / 证据 / 学术锚点，用于 U7/U9 裁决）
> **上游**: [RESEARCH_p046c_f2_closeout](RESEARCH_p046c_f2_closeout.md)（§3 G-P046c-5/6/7、§6.4 B4b、§10 U7/U9）；[REVIEW_p046c_step2](REVIEW_p046c_step2_research.md)（U7 scope 认可延后、U9 删除/标注二选一）；[P-046a DESIGN D-3](DESIGN_p046_portfolio_optimization.md)（死配置不删除先例）
> **状态**: **补充调研落盘（2026-11-23，DeepSeek-V4.1-Flash）**；零代码变更 / 未提交；**本文件修订 Step 2 对 U7/U9 的建议**；**用户裁决（2026-11-23）：U7=B4d、U9=保字段接线**（U7/U9 关闭）；**Step 2b 定点复审 PASS（2026-11-23，[REVIEW_p046c_step2b](REVIEW_p046c_step2b_u7u9.md)，GLM-5.3-Flash ≠ 作者）**：0 P1/P2 + 3 P3 当轮全修（F-R2b-1/2/3）+ 1 观察，裁决维持有效
> **基线**: @`3495683`；collect 1464（1463 passed + 1 skipped）；门禁与 Step 2 复审一致（本文件不重复复跑，引用 [REVIEW §4](REVIEW_p046c_step2_research.md)）

---

## 0. 本文定位

用户要求为 **U7**（行业上限 / 换手 L1 / 跟踪误差：本批实现 vs 延后 P-046d）与 **U9**（`industry_max_weight`：删除 vs 保留 deprecated）补充**社区案例、源码级证据、学术/规范锚点**。本文只提供决策证据与建议，不写设计与代码。

**结论先行（修订 Step 2 建议）**：

1. **U7 拆分**：**行业上限本批实现**（引擎级严格投影，1 个插入点 + 1 个纯函数）；**换手 L1 与跟踪误差延后 P-046d**。原 B4b「三项全部延后」被修订为 **B4d**。
2. **U9：保留字段并接线消费**（`industry_max_weight` 由引擎投影消费）→ **零死配置、零兼容破坏**；不再建议删除；若最终不实现行业上限，则保留 deprecated + warning + P-046d 指针，**仍不删除**。

---

## 1. 决策问题与 Step 2 原建议

| ID | 问题 | Step 2 原建议 | 本文修订 |
|---|---|---|---|
| U7 | 行业上限 / 换手 / TE 是否本批实现 | **B4b：三项全部延后 P-046d**（`OptimizationContext`） | **B4d：行业上限本批做（引擎级投影）；换手/TE 延后** |
| U9 | `industry_max_weight` 删除 vs deprecated | 删除（`config.py`，`config_v2` 冻结例外）或 deprecated 二选一 | **保字段 + 接线消费**（首选）；不删除 |

---

## 2. 新证据：三条约束的输入可得性

| 输入 | 现状 | 证据 | 结论 |
|---|---|---|---|
| 行业标签 | **已加载**（日期 × 股票） | [data.py L164-L169](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L164-L169)、L383；engine 在 rebalance 内有 `dm = self.dm`（L420/L524）与 `dm.trade_dates`（L1356） | 行业上限**数据可得** |
| 上期权重 | **引擎侧可得**：`current_positions` + `prices` + `total_value` 在 `build_target_positions` 调用点已具备 | [engine_v2.py L1508-L1517](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1508-L1517) | 换手**可实现**，但需进入优化目标（见 §3.2） |
| 基准权重/收益 | **不可得**：`cfg.benchmark` 为占位字符串，无加载链路 | [config.py L455](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L455) | 跟踪误差**本批不可实现** |
| 行业上限配置 | 字段已存在但零消费 | [config.py L325](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L325) | U9 可直接接线 |

> 关键差异：行业上限只缺**一个引擎插入点**；换手缺**优化目标接入**；TE 缺**数据源**。三者成本不同，不应打包裁决。

---

## 3. 社区实现对照（A 级：本轮读 wheel 源码）

### 3.1 行业/板块上限

| 包/版本 | 位置 | 实现方式 | 对 P-046c 的含义 |
|---|---|---|---|
| pypfopt **1.5.5** | `pypfopt/base_optimizer.py` L366-L403 | `add_sector_constraints(sector_mapper, sector_lower, sector_upper)`；`is_sector = [sector_mapper.get(t) == sector for t in tickers]`；`cp.sum(w[is_sector]) <= upper` / `>= lower`——**in-solver 线性约束** | 凸优化器可 in-solver；未在 `hierarchical_portfolio.py` 提供同类接口 → HRP 需单独处理 |
| skfolio **1.14.4** | `skfolio/optimization/convex/_base.py` L392-L401（`groups`）、L403-L409（`Aw≤b`）、L359-L366（组名参与 `linear_constraints`） | `groups` 定义资产组，`linear_constraints` 以组名写 `A w ≤ b`；**in-solver** | 凸优化器统一线性约束；HRP 另有层次实现 |
| riskfolio-lib **7.4.1** | `riskfolio/src/ConstraintsFunctions.py` L34-L70（`assets_constraints(constraints, asset_classes)` → `A,B` with `Aw≤B`）；L1595（`hrp_constraints`） | 凸优化器用 `A,B`；**HRP 专用 `hrp_constraints`** 单独接口 | 社区同样把「凸优化器 in-solver」与「HRP 专用」分开 |

**观察**：三家均把行业上限实现为 **cvxpy 线性约束**；对 HRP 要么无接口（pypfopt），要么单独 API（riskfolio）。这与 P-046b DESIGN D12「HRP 后投影近似」一致——**后投影并非异端，但必须严格投影**（E5 已证「截断+归一」会违反上限）。

### 3.2 换手 L1

| 包/版本 | 位置 | 实现方式 |
|---|---|---|
| pypfopt 1.5.5 | `pypfopt/objective_functions.py` L168-L183 | `transaction_cost(w, w_prev, k) = k·‖w−w_prev‖₁`，作为 **additional objective** |
| skfolio 1.14.4 | `skfolio/optimization/convex/_base.py` L224-L243（`transaction_costs` 公式 `Σ c_i|w_i−w_prev_i|`）、L301-L312（`previous_weights`） | **in-solver 线性成本**，显式要求 `previous_weights` |
| riskfolio-lib 7.4.1 | `riskfolio/src/Portfolio.py` L113-L115（`turnover` 参数）、L299/L439、L3005-L3009（`TO_1 <= self.turnover * k`） | **in-solver 换手上限**，同样依赖上期/基准权重 |

**观察**：换手在三家都是**优化目标/约束**，必须有 `previous_weights`；没有一家把换手当作「输出后处理」。EW/RP/HRP 没有可交易的目标函数，若强行做只能启发式混合（`(1−λ)w+λw_prev`），语义与其他优化器不一致 → **支持延后 P-046d**。

### 3.3 跟踪误差

| 包/版本 | 位置 | 输入 |
|---|---|---|
| pypfopt 1.5.5 | `objective_functions.py` L186-L202（ex-ante `(w−w_b)ᵀΣ(w−w_b)`）、L205-L226（ex-post，需 `benchmark_returns`） | 基准**权重**或**收益序列** |
| skfolio 1.14.4 | `convex/_benchmark_tracker.py` L24-L58 | `BenchmarkTracker` 直接以**基准收益** `y` 构造超额收益 `X−y`，并强制 `budget=1` |
| riskfolio-lib 7.4.1 | `Portfolio.py` L109-L111（`kindbench`；Step 2b 复审修正 F-R2b-2，原误记 `benchmark_is_weights`） | 基准权重或指数收益 |

**观察**：TE 无一例外需要**基准数据**；本仓 `cfg.benchmark` 仅占位（§2）→ **本批不可实现**，延后 P-046d/P-058 是唯一诚实选项。

---

## 4. 新数值证据（E8-E12，可重放）

### E8 引擎级严格投影 vs 朴素后处理

构造：N 资产、G 行业、`w0` 将 55% 集中到行业 0，`cap` 低于该集中度。

| 情形 | 严格投影（QP: min‖w−w0‖² s.t. Σw=1, 0≤w≤max, Gw≤cap） | 朴素 clip+归一 |
|---|---|---|
| N=100 / G=10 / cap=0.12 | max_group **0.120000**、Σw=1、dev=0.1522、**0.014s** | max_group **0.210526**（**+0.0905 违反**） |
| N=500 / G=20 / cap=0.08 | max_group **0.080000**、Σw=1、dev=0.1244、**0.022s** | max_group **0.150943**（**+0.0709 违反**） |

**结论**：严格投影在 500 资产仅 0.022s，且精确满足行业上限；朴素后处理不可用（与 E5 同向）。

### E9 in-solver 行业上限（MVO）

| 情形 | 结果 |
|---|---|
| N=50 / G=8 / cap=0.20 | 0.019s，max_group=0.167305（≤cap） |
| N=200 / G=12 / cap=0.15 | 0.073s，max_group=0.134408（≤cap） |

in-solver 同样可行且快，但需改 6 个优化器签名（§5.2）。

### E10 换手 L1 的效果与输入依赖

| λ（L1 惩罚） | turnover | 年化收益 | 波动 |
|---|---|---|---|
| 0.000 | 0.6650 | 0.0629 | 0.1254 |
| 0.001 | 0.6276 | 0.0626 | 0.1234 |
| 0.010 | 0.4636 | 0.0608 | 0.1209 |

换手从 0.665 降到 0.464，收益代价约 0.0021、波动降低 0.0045——**有效但需 prev weights 进入目标函数**。

### E11 跟踪误差约束

`target_te=0.02` → 实际 0.020000；`target_te=0.05` → 实际 0.050000（精确命中，需 benchmark weights `w_b`）。

### E12 改动面计数

| 路径 | 改动面 |
|---|---|
| in-solver 行业上限 | 7 个 `optimize_with_diagnostics` 定义（Base + 6 具体类）+ 引擎 helper/调用 + 测试桩 → 大 |
| 引擎级投影 | 1 个插入点（[engine L1507](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1507) 后、L1508 前）+ 1 个纯函数 + 配置消费 + 测试 → 小；6 个优化器与 `IOptimizer` **零改动** |

---

## 5. U7 方案重估

### 5.1 决策矩阵

| 方案 | 行业上限 | 换手 L1 | TE | 改动面 | 结论 |
|---|---|---|---|---|---|
| A（Step 2 原 B4b） | 延后 | 延后 | 延后 | 0 | 保守；但行业数据可得，延后理由不充分 |
| **B（B4d，建议）** | **本批（引擎级严格投影）** | 延后 P-046d | 延后 P-046d | 1 插入点 + 1 纯函数 | **收益/成本最优**；关闭死配置；P-046d 缩为换手/TE |
| C | 本批（in-solver） | 本批 | 本批 | 7 签名 + 引擎 + 新数据源 | scope 失控；TE 数据缺失 |

### 5.2 B4d 架构（设计输入，非最终设计）

- **位置**：overlay 与股票负权截断之后、`build_target_positions` 之前（[engine L1502-L1507](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1502-L1507)）。
- **输入**：`target_weights`（股票子集）、`dm.industry.loc[date]` reindex 到股票代码、`cfg.optimizer.industry_max_weight`、`max_weight`。
- **算法**：严格凸投影 `min‖w−w0‖² s.t. Σw=budget, 0≤w≤max_weight, Σ_{i∈g}w_i≤cap`；`budget` = 当前股票 sleeve 权重和（期货/现金不受影响）。
- **退化**：行业缺失 → fail-loud 或按「不约束」warning（U 裁决）；caps 不可行（`Σ cap < budget`）→ `InfeasibleConstraintError`（config 类别，U1-B 同构）；全零/空集 → 原样返回。
- **诊断**：投影前后 L1 偏差、最大组和、触发资产数；不新增 `warning_kind` 枚举（U11）。
- **语义声明**：后投影近似会改变优化器最优性；与 D12（HRP 箱体后投影）同构，须在 docstring 声明，不得宣称 in-solver 最优。
- **为何优于 in-solver**：E8 证明精确且 0.02s；E12 改动面 1 vs 7；对 EW/RP/HRP 同样生效（社区对 HRP 也是单独/后处理）。

### 5.3 换手/TE 仍延后的理由

- 换手：三家社区实现均为 **in-solver**（§3.2），需 `previous_weights`；EW/RP/HRP 无目标函数，启发式混合会破坏语义一致性 → P-046d（`OptimizationContext` 统一传入 prev weights，先在 cvxpy 优化器落地）。
- TE：**基准数据缺失**（§2），任何实现都是空转 → P-046d/P-058。

---

## 6. U9 方案重估

### 6.1 三个选项

| 选项 | 做法 | 优点 | 代价 |
|---|---|---|---|
| **A（建议）** | **保字段 + 接线**：`industry_max_weight` 由引擎级投影消费 | 零死配置、零兼容破坏、F2 行业缺口关闭 | 需实现 B4d（本批已建议） |
| B | 保字段 + deprecated + warning + P-046d 指针 | 零破坏、可观测 | 死配置仍在；F2 缺口未关 |
| C | 删除（仅 `config.py`，`config_v2` 冻结例外） | 字段面干净 | **破坏旧 JSON/CLI 配置构造**；无测试兜底；违反 P-046a D-3 先例 |

### 6.2 证据锚点

- **仓内先例**：P-046a DESIGN **D-3** 明确「死配置字段不删除，仅加 deprecated 注释并登记归属」，理由含「删除会破坏既有 JSON 反序列化与 `test_config_v2`」（[DESIGN_p046 L125](DESIGN_p046_portfolio_optimization.md)）；本仓 `BacktestConfig` 为 dataclass（config.py L397-L398）**无 `to_dict`**、core 内无生产 dict 回灌链路（Step 2b 复审修正 F-R2b-3：原引 [config.py L584](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L584) 的 `to_dict` 实属 `MarginConfig`）；「不删除」仍由外部 JSON→`**kwargs` 回灌风险 + config_v2 FROZEN schema 分叉 + U9=A 接线使删除失效三支柱支撑。
- **配置体系**：`config_v2.py` 为 FROZEN（生产零引用，[L13](file:///f:/Coding/Factor_Trading_v3.0/core/config_v2.py#L13)），同名字段 L128；删除 `config.py` 字段会造成两套 schema 永久分叉。
- **Pydantic 2.13.4**：`Field(deprecated=True)` **可用**（本轮探针实测），若走选项 B 可在 `config_v2` 标注；但生产 `config.py` 是 dataclass，只能用 `warnings.warn(DeprecationWarning)`（Python 3.12；**PEP 702 `typing.deprecated` 是 3.13**，本仓不可用）。
- **规范锚点（B 级）**：Semantic Versioning 2.0.0（破坏性变更需主版本号）；Google AIP-180「Backwards compatibility」（字段先 deprecated、后移除）；Hyrum's Law（可观测行为会被依赖）；PEP 702（`typing.deprecated`，3.13）。
- **测试面**：`tests/*.py` 对 `industry_max_weight` **零引用**（本轮扫描 0 命中）——删除不会红测试，**缺少安全网**，更应保守。

### 6.3 建议

- **首选 A（保字段 + 接线）**：与 B4d 绑定，U9 从「删除/弃用二选一」变为「**字段获得真实消费**」，死配置问题消失。
- 若 U7 最终裁决为「行业上限延后」→ **选 B**（deprecated + warning + P-046d 指针），**不选 C**。
- 若走 B，`OptimizerConfig.__post_init__` 可补 `industry_max_weight <= max_weight` 校验（与 [config_v2 L143](file:///f:/Coding/Factor_Trading_v3.0/core/config_v2.py#L143) 对齐），但须评估既有配置兼容性（U）。

---

## 7. 决策矩阵汇总

| 裁决 | 推荐 | 备选 | 不推荐 |
|---|---|---|---|
| U7 行业上限 | **B4d：本批引擎级严格投影** | A：延后 P-046d（保守） | C：本批 in-solver（scope 大） |
| U7 换手 L1 | **延后 P-046d** | 本批仅 cvxpy 优化器（语义不统一） | 后处理启发式 |
| U7 跟踪误差 | **延后 P-046d/P-058** | —（无基准数据） | 本批空转 |
| U9 `industry_max_weight` | **A：保字段 + 接线** | B：deprecated + warning | C：删除 |

> **用户裁决（2026-11-23）**：**U7 = B4d**（行业上限本批引擎级严格投影；换手 L1 / TE 延后 P-046d）；**U9 = A**（保字段 + 接线消费）。**U7/U9 关闭**，进入 Step 3 DESIGN。

---

## 8. 对 Step 2 结论的修订登记

| ID | 修订 | 依据 |
|---|---|---|
| **F-R2-U7-1** | Step 2「B4b 三项全部延后」→ **B4d：行业上限本批（引擎级投影），换手/TE 延后** | §2 输入可得性差异；§3 社区实现；E8/E12 成本 |
| **F-R2-U9-1** | Step 2「删除或 deprecated 二选一」→ **保字段 + 接线（首选）**；不删除 | P-046a D-3 先例；config_v2 FROZEN；测试零引用无安全网；SemVer/AIP-180 |
| 观察 O-U7-1 | B4d 的行业缺失/期货 sleeve/现金残差语义需 Step 3 精化 | §5.2 |
| 观察 O-U9-1 | 若走 B，`industry_max_weight` 校验与旧配置兼容需 Step 3 裁决 | §6.3 |

> **流程建议**：本文件修订了 Step 2 复审认可的方向，按 RULE-5 建议做一次 **Step 2b 定点复审**（reviewer ≠ 本文作者），再并入 Step 3；或由用户直接裁决 U7/U9 后进入 Step 3。

---

## 9. 状态链

- **2026-11-23**：Step 2 异构复审 PASS（[REVIEW_p046c_step2](REVIEW_p046c_step2_research.md)）；U7 建议全延后、U9 删除/弃用二选一。
- **2026-11-23**：**U7/U9 补充调研（本文）**——输入可得性（行业可得 / prev weights 引擎可得 / benchmark 不可得）；社区锚点 pypfopt `add_sector_constraints` L366-L403、skfolio `groups` L392-L401 + `previous_weights` L301 + `BenchmarkTracker` L24-L58、riskfolio `assets_constraints` L34-L70 + `hrp_constraints` L1595 + `turnover` L113-L115/L3005-L3009；数值 E8-E12（严格投影 500 资产 0.022s 精确；朴素后处理 +0.0709 违反；换手 λ 效果；TE 精确）；**修订建议 U7→B4d（行业上限本批、换手/TE 延后）、U9→保字段接线**；登记 F-R2-U7-1/F-R2-U9-1 + 2 观察。零代码变更 / 未提交。
- **2026-11-23**：**用户裁决**：U7 = **B4d**（行业上限本批引擎级严格投影；换手/TE 延后 P-046d）；U9 = **保字段 + 接线**；U7/U9 关闭。
- **2026-11-23**：**Step 2b 定点复审 PASS**（[REVIEW_p046c_step2b](REVIEW_p046c_step2b_u7u9.md)，GLM-5.3-Flash ≠ 作者）：E8/E11/E12 独立重写重放逐位/精确命中（E8 dev=L2 口径与 rng 流锁定）；社区锚点对 wheel 12/13 + 1 名称修正；pydantic deprecated / PEP 702 / 本仓 3.12.11 实测确认；裁决登记一致性 + 范围守卫通过；**0 P1/P2 + 3 P3 当轮全修**（F-R2b-1 E9/E10 点值构造补注 / F-R2b-2 `kindbench` 命名 / F-R2b-3 `to_dict` 引用）+ 1 观察（O-R2b-1）；**裁决维持有效**。
- **2026-11-23**：**Step 3 DESIGN 完成**（[DESIGN_p046c_f2_closeout](DESIGN_p046c_f2_closeout.md)）：B4d 落为 `project_industry_cap` 纯函数（引擎级严格投影，D12-D16）；NaN/0 未分类、期货列固定、未绑定逐位不变、不可行 `InfeasibleConstraintError`；U9=A 落为字段校验 `0<x≤1` + 引擎接线（D17）。
- **下一步**：Step 4 DESIGN 异构复审（reviewer ≠ DeepSeek-V4.1-Flash）。

---

## 10. 附：探针原始读数（可重放）

```
E8 N=100 G=10 cap=0.12 w0_max_group=0.5500
   proj status=optimal time=0.014s sum=1.000000000 max_group=0.120000 dev=0.1522
   naive max_group=0.210526 violation=+0.090526
E8 N=500 G=20 cap=0.08 w0_max_group=0.5500
   proj status=optimal time=0.022s sum=1.000000000 max_group=0.080000 dev=0.1244
   naive max_group=0.150943 violation=+0.070943
E9 N=50 G=8 cap=0.20: 0.019s max_group=0.167305
E9 N=200 G=12 cap=0.15: 0.073s max_group=0.134408
E10 lambda=0.000 turnover=0.6650 ret=0.0629 vol=0.1254
E10 lambda=0.001 turnover=0.6276 ret=0.0626 vol=0.1234
E10 lambda=0.010 turnover=0.4636 ret=0.0608 vol=0.1209
E11 target_te=0.02 actual=0.020000; target_te=0.05 actual=0.050000
E12 optimizer definitions=7 (Base + 6 具体类); engine-level insertion=1
```

构造：N 资产随机 SPD（`m@m.T/N + 0.02I`，seed=300+N/200+N/999）；行业分组 `arange(N)%G` 后 shuffle；`w0` 为 Dirichlet 后将 55% 集中到行业 0；投影 QP 用 cvxpy 默认求解器。构造与种子已明示，可重放；临时脚本不入库。

> **Step 2b 复审重放口径（F-R2b-1 补登，GLM-5.3-Flash 独立重写，2026-11-23）**：rng 流顺序 **m(SPD) → groups shuffle → dirichlet → 55% 集中**；E8 `dev` = **‖w−w0‖₂**（L2 范数；两情形逐位复现 0.1522/0.1244；L1 口径为 0.8600/0.9400）；E8 naive = **逐组缩至 cap 后整体归一**（解析可复现 0.12/0.57、0.08/0.53，与 w0 随机性无关）；E11/E12 逐位/精确复现。**E9/E10 点值依赖未记录的 mu 分布与目标系数**——reviewer 最近族 `mu~N(0.05,0.02), δ=0.5` → E10 λ=0 为 turnover 0.676/ret 0.0632/vol 0.1274（λ=0.010 端点 0.4614 vs 文档 0.4636 命中），该两点值**降级为量级/方向参照**，决策不依赖（B4d 核心证据为 E8 + E12 + 输入可得性，全部独立复现）。
