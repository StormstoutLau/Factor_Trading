# REVIEW（Step 2b 定点复审）：P-046c U7/U9 补充调研

> **批次**: P-046c · **Step 2b 定点复审**（RULE-5：reviewer ≠ 作者）
> **被审物**: [RESEARCH_p046c_u7_u9_supplement](RESEARCH_p046c_u7_u9_supplement.md)（作者 DeepSeek-V4.1-Flash，2026-11-23 落盘）
> **复审者**: GLM-5.3-Flash（≠ 作者；与 Step 2 复审同人，对被审物内容无作者关系）
> **基线**: @`3495683`；被审物**零代码变更**，门禁不复跑、引用 [REVIEW_p046c_step2 §4](REVIEW_p046c_step2_research.md)
> **复审日期**: 2026-11-23
> **结论**: **PASS —— 0 P1/P2 + 3 P3（当轮全修）+ 1 观察**；**用户裁决（U7=B4d、U9=保字段接线）维持有效**，可进入 Step 3 DESIGN

---

## 1. 复审范围与方法

**范围**：定点复审只覆盖补充调研相对主调研的**新增内容**——§2 输入可得性、§3 社区锚点、§4 E8-E12、§5/§6 方案重估、§7 裁决块、§8 修订登记、§9 状态链、§10 探针读数。主调研 E1-E7 / C1-C20 / 门禁已由 [Step 2 复审](REVIEW_p046c_step2_research.md)覆盖，不重复。

**方法**（四线独立验证）：

1. **代码事实抽查**：对 §2/§5.2/§6.2 引用的仓内行号逐一 Read 核对。
2. **E8-E12 独立重写重放**：reviewer 按被审物 §10 构造说明**自写探针**（`%TEMP%\p046c_step2b_probe.py` 等，不入库；cvxpy 1.9.1 / numpy 2.4.6 / Python 3.12.11，项目 `.venv`），非复用作者脚本。
3. **社区锚点 A 级**：对 `%TEMP%\p046b_pkgs` 三包 wheel 源码逐行号 Read/Grep 核对。
4. **U9 规范锚点实测**：pydantic `Field(deprecated=True)` 行为探针、PEP 702/Python 版本、tests 零引用扫描。

---

## 2. 核验矩阵

### 2.1 代码事实（§2 输入可得性 / §5.2 / §6.2）

| 主张 | 复审 | 判定 |
|---|---|---|
| 行业标签可得：[data.py L164-L169](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L164-L169) `industry` property + L383 加载 | 逐位命中 | ✓ |
| engine 内 `dm = self.dm`（L420/L524）与 `dm.trade_dates`（L1356） | 命中 | ✓ |
| 上期权重引擎侧可得：`build_target_positions` 调用点 [engine L1508-L1517](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1508-L1517)（`current_positions`/`prices`/`total_value` 在作用域） | 命中 | ✓ |
| benchmark 不可得：[config.py L455](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L455)「基准指数（暂留接口）」占位、无加载链路 | 命中 | ✓ |
| `industry_max_weight` 字段（[config.py L325](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L325)；config_v2 L128 FROZEN）+ 零消费 | 命中 | ✓ |
| 插入点唯一性：overlay（L1498-L1500）→ 股票负权截断（L1502-L1507）→ `build_target_positions`（L1508），**L1507 后 / L1508 前**为唯一自然插入点 | 命中 | ✓ |
| P-046a DESIGN D-3 先例（[DESIGN_p046 L125](DESIGN_p046_portfolio_optimization.md)） | 引文逐字命中 | ✓ |
| config_v2 L143-L144 既有 `industry_max_weight <= max_weight` 校验 | 命中 | ✓ |
| tests 对 `industry_max_weight` **零引用** | grep 0 命中 | ✓ |

### 2.2 数值证据 E8-E12（独立重写重放）

| 探针 | 文档读数 | 复审重放 | 判定 |
|---|---|---|---|
| **E8 naive** | max_group 0.210526 / 0.150943（违反 +0.090526 / +0.070943） | **逐位命中**；且解析可复现（0.12/0.57=0.210526、0.08/0.53=0.150943，与 w0 随机性无关——朴素法对任何 55% 集中都违反同值） | ✓ 强 |
| **E8 proj** | status=optimal、sum=1、max_group 恰为 cap（0.120000/0.080000）、time 0.014s/0.022s | max_group/sum/status **精确命中**；time 0.015s/0.021s 同量级 | ✓ |
| **E8 dev** | 0.1522 / 0.1244 | **逐位复现**——reviewer 锁定口径：`dev = ‖w−w0‖₂`（L2 范数）、rng 流 **m(SPD) → groups shuffle → dirichlet → 55% 集中**（L1 口径为 0.8600/0.9400 = 2×移出质量，非文档值） | ✓（口径经 F-R2b-1 补登） |
| **E9 in-solver** | N=50: 0.019s / 0.167305；N=200: 0.073s / 0.134408（均 interior） | 约束 respected（binding 0.200000/0.150000 或 interior 均观测到）+ time 0.011-0.032s 同量级；**点值不可精确重放**（mu 分布/目标系数未记录，最近族 `mu~N(0.05,0.02), δ=0.5` → 0.200000/0.127057） | △ F-R2b-1 |
| **E10 换手** | λ=0/0.001/0.010 → turnover 0.6650/0.6276/0.4636，ret 0.0629/0.0626/0.0608，vol 0.1254/0.1234/0.1209 | **方向单调全命中**（λ↑ → turnover↓/ret 微降/vol↓）；λ=0.010 端点 **0.4614 vs 0.4636** 命中；λ=0 点值最近族 0.676/0.0632/0.1274 接近不逐位 | △ F-R2b-1 |
| **E11 TE** | target 0.02 → actual 0.020000；0.05 → 0.050000 | **逐位命中**（约束 binding 至求解器精度，构造无关的稳健结论） | ✓ 强 |
| **E12 改动面** | `optimize_with_diagnostics` 定义 7（Base+6）+ engine 插入点 1 | **精确命中**：portfolio.py L393/L468/L592/L656/L688/L720/L800 = 7 处定义；engine 插入点 1（§2.1 已核） | ✓ |

**对决策的影响评估**：E9/E10 点值虽不可逐位重放，但两探针支撑的**决策性结论**（in-solver 可行且快；换手 λ 单调有效、需 prev weights 进目标函数）在 reviewer 独立构造下全部成立。**裁决（U7=B4d、U9=A）不依赖任何不可重放点值**——B4d 的成本-收益核心证据是 E8（全复现）+ E12（精确命中）+ 输入可得性（全命中）。

### 2.3 社区锚点 A 级（对 wheel 源码）

| 包/锚点 | 文档行号 | 复审 | 判定 |
|---|---|---|---|
| pypfopt `add_sector_constraints` | base_optimizer.py L366-L403，in-solver `cp.sum(w[is_sector]) <= upper` | 函数体 L366-L403 逐位命中 | ✓ |
| pypfopt `transaction_cost` | objective_functions.py L168-L183，`k·‖w−w_prev‖₁` | 逐位命中 | ✓ |
| pypfopt ex-ante / ex-post TE | L186-L202 / L205-L226 | 逐位命中（`benchmark_weights` / `benchmark_returns` 两输入形态） | ✓ |
| pypfopt hierarchical_portfolio 无 sector 接口 | 文档 L49 主张 | grep `sector|group|class_|constraint` **0 命中** | ✓ |
| skfolio `groups` / `Aw≤b` / 组名线性约束 | _base.py L392-L401 / L403-L409 / L359-L366 | 逐位命中 | ✓ |
| skfolio `transaction_costs` 公式 | _base.py L224-L243（`Σc_i·|w_i−w_prev_i|`） | 逐位命中 | ✓ |
| skfolio `previous_weights` | _base.py L301-L312 | 逐位命中 | ✓ |
| skfolio `BenchmarkTracker` | _benchmark_tracker.py L24-L58，超额收益 `X−y` + 强制 `budget=1` | 逐位命中（class L24、budget=1 论证 L44-L58） | ✓ |
| riskfolio `assets_constraints` | ConstraintsFunctions.py L34-L70，`Aw≤B` | 逐位命中 | ✓ |
| riskfolio `hrp_constraints` | ConstraintsFunctions.py L1595 | 逐位命中（HRP 单独接口，与社区「凸优化器 in-solver / HRP 单独」分野一致） | ✓ |
| riskfolio `turnover` / `TO_1` | Portfolio.py L113-L115 / L299 / L439 / L3005-L3009 | 逐位命中（docstring L112-L115、签名默认 L299、赋值 L439、`TO_1 <= self.turnover * k * 1000` L3004-L3009） | ✓ |
| riskfolio 基准参数名 | 文档记 `benchmark_is_weights`（L110-L111） | **参数不存在**；实际为 **`kindbench`**（L109-L111：True=基准为权重组合 / False=指数；语义与文档主张一致，**名称错误**） | ✗ F-R2b-2 |

### 2.4 U9 规范锚点

| 锚点 | 文档主张 | 复审 | 判定 |
|---|---|---|---|
| pydantic 2.13.4 `Field(deprecated=True)` | 「可用（本轮探针实测）」 | 实测：构造不报错 + JSON schema `deprecated: true` + **属性访问发 DeprecationWarning（构造时静默）**——「可用」成立，warning 时机为访问时（O-R2b-1 口径注记） | ✓ |
| PEP 702 `typing.deprecated` 属 Python 3.13 | 本仓不可用 | 本仓 `.venv` = **3.12.11** → 不可用，主张成立 | ✓ |
| tests 零引用 → 删除无安全网 | 「0 命中」 | grep 0 命中 | ✓ |
| config_v2 FROZEN + L128 同名字段 | schema 分叉风险 | L12-L17 FROZEN 声明 + L128 命中 | ✓ |
| 「`BacktestConfig.to_dict` 存在（config.py L584），旧 dict 回灌是现实路径」 | — | **引用错误**：L584 `to_dict` 属 `MarginConfig`（class L550）；`BacktestConfig`（dataclass，L397-L398）**无 to_dict**；repo 全域无生产 dict 回灌链路（仅 2 处测试 `BacktestConfig(**kwargs)`）。结论「不删除」仍由 D-3 先例 + config_v2 FROZEN 分叉 + 外部 `**kwargs` 回灌风险 + U9=A 接线使删除失效支撑 | ✗ F-R2b-3 |

### 2.5 裁决登记一致性 + 范围守卫

| 项 | 复审 | 判定 |
|---|---|---|
| §0 结论先行 / §1 修订表 / §7 决策矩阵 / §8 F-R2-U7-1、F-R2-U9-1 / §9 状态链（含裁决行）内部一致 | 逐项对读，无矛盾 | ✓ |
| 与主 [RESEARCH §6.4/§10/§14](RESEARCH_p046c_f2_closeout.md)（B4d 修订 + 裁决 L310/L312/L376）同步 | 命中 | ✓ |
| 与 [PROGRESS 主行 / §3.99](PROGRESS.md) 同步 | 命中 | ✓ |
| 范围守卫：零代码变更；§5.2 明示「设计输入，非最终设计」；门禁引用不复跑 | 成立 | ✓ |
| DoD/裁决未被 E9/E10 点值缺口动摇（§2.2 影响评估） | 成立 | ✓ |

---

## 3. 发现与当轮修复

| ID | 级别 | 位置 | 内容 | 修复 |
|---|---|---|---|---|
| **F-R2b-1** | P3 | 被审物 §10 | **构造注记不完整**：`dev` 未定义度量（实测 = ‖w−w0‖₂，L1 口径为 0.8600/0.9400）；rng 流顺序未写明（实测 m→groups→w0）；E9 mu 分布/目标系数、E10 mu/目标系数未记录 → **E9/E10 点值不可精确重放**（reviewer 最近族 `mu~N(0.05,0.02), δ=0.5` → turnover 0.676/ret 0.0632/vol 0.1274，λ=0.01 端点命中）。「构造与种子已明示，可重放」表述过强。决策内容不受影响（§2.2 影响评估） | **当轮补登**：§10 追加 reviewer 重放口径块（流顺序 / dev=L2 / naive 定义 / E9-E10 点值降级为量级参照） |
| **F-R2b-2** | P3 | 被审物 §3.3 | riskfolio 锚点参数名错误：`benchmark_is_weights` 在 riskfolio-lib 7.4.1 中**不存在**，实际为 `kindbench`（Portfolio.py L109-L111）。语义（基准权重组合 vs 指数）与行号语义段正确，仅名称错 | **当轮修正**：§3.3 改为 `kindbench` 并标注修正来源 |
| **F-R2b-3** | P3 | 被审物 §6.2 | 「`BacktestConfig.to_dict` 存在（config.py L584）」引用错误：L584 `to_dict` 属 `MarginConfig`（L550）；`BacktestConfig` 无 to_dict、无生产 dict 回灌链路（repo 全域仅 2 处测试 kwargs 构造）。「不删除」结论不受影响（其余三支柱独立成立） | **当轮改写**：§6.2 该句替换为准确论据（D-3 先例 + config_v2 FROZEN 分叉 + 外部 `**kwargs` 回灌风险 + U9=A 使删除失效） |
| **O-R2b-1** | 观察 | 被审物 §6.2 | pydantic `Field(deprecated=True)` 实测口径：JSON schema 标注 `deprecated: true` + **属性访问**时发 DeprecationWarning、构造静默。若未来任何路线需要 deprecation 语义，warning 时机为访问时；本批 U9=A 不消费该锚点，无行动项 | 登记不修 |

---

## 4. 结论

- **判定**：**PASS**。0 P1 / 0 P2；3 P3 全部当轮修复（reviewer 直接修订被审物 §3.3 / §6.2 / §10，并同步 §9 状态链与头部状态行）；1 观察登记。
- **核心证据链**：E8（naive 解析复现 + proj 精确 + dev 逐位）+ E11（精确）+ E12（精确）+ 代码事实 9/9 + 社区锚点 12/13（1 处名称修正）+ U9 锚点实测——**B4d 与 U9=A 的裁决依据全部独立成立**。
- **裁决维持**：用户裁决（2026-11-23）**U7=B4d（行业上限本批引擎级严格投影；换手 L1 / TE 延后 P-046d）、U9=保字段 + 接线消费**维持有效，U7/U9 关闭。
- **下一步**：Step 3 DESIGN（B1a ERC 修复 / B2a KellyOptimizer / B3a MaxSharpe / B4d 行业投影 / U9 接线；O-U7-1 行业缺失·期货 sleeve·现金残差语义、O-U9-1、U2 混合归一规则、I4 正权重闭式限定、kelly/budget 命名消歧在设计中精化）。
