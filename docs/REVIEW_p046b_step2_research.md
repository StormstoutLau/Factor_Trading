# REVIEW：P-046b Step 2 调研异构复审（BL / HRP）

> **批次**: P-046b · **Step 2 异构复审** · 日期 2026-11-23 · **复审基座 GLM-5.3-Flash（≠ 落码/调研基座 DeepSeek-V4.1-Flash → 异构成立）**
> **复审对象**: [RESEARCH_p046b_bl_hrp](RESEARCH_p046b_bl_hrp.md)（Step 1 调研，代码事实 @`8f8b912`）
> **复审方法**: ① 12 组代码事实逐行号读码核对；② 数值探针独立重写重放（E1 论文距离链 / E2 后验恒等式·τ 消去·极限 + **新增随机 Σ 一般性探针**）；③ 外部锚点 A1-A6 与已取全文逐字比对；④ 遗留四项与 AST 口径复核；⑤ 范围控制检查（无 P-046c/D3/策略层夹带）
> **范围声明（RULE-5 单向）**: 复审者标记问题并执行修复（同轮回写 RESEARCH）；不改写作者原始记录的历史小节

---

## 1. 独立事实核验（代码面）

| # | 核对对象（RESEARCH §2 引用） | 复核方式 | 结论 |
|---|---|---|---|
| 1 | `build_optimizer` 词表 5 项（L610-629） | 读码 | ✅ `equal_weight/min_variance/mean_variance/mvo/risk_parity`；未知 method 抛 `ValueError` |
| 2 | 四优化器类（L315-575） | 读码 | ✅ EqualWeight/MinVariance/MeanVariance/RiskParity |
| 3 | `_apply_constraints` 投影语义（L278-294）/ `_apply_constraints_legacy` 禁用标注（L296-300） | 读码 | ✅ 上限型只截断；legacy 「生产禁用」逐字在位 |
| 4 | `_cov_for` 注入优先（L302-312） | 读码 | ✅ `cov_matrix.loc[selected, selected]` / 否则 `estimate_cov` |
| 5 | MVO 目标 `μᵀw − risk_aversion·wᵀΣw`（L472-492） | 读码 | ✅ `cp.Maximize(portfolio_return - risk_aversion * quad_form)` |
| 6 | RiskParity 零方差 `break` 且 `message=""`（L527-542） | 读码 | ✅ 与 F-S10-P046-1 描述一致 |
| 7 | `OptimizerConfig` 字段集 + `__post_init__` 四校验（L271-315） | 读码 | ✅ 字段清单逐项命中；无 BL/HRP 专有字段（Grep 佐证） |
| 8 | 引擎 3 参位置调用（L78-100 / L316-320 / L1362-1368 / L1370-1384） | 读码 | ✅ `_optimize_with_diagnostics(optimizer, tradable_stocks, returns_data, cov_matrix)`；先 `estimate_cov` 再调用；诊断按 `infeasible_kind/message` 落账 |
| 9 | `IOptimizer` Protocol 仅 2 参 `optimize`（L231-240） | 读码 | ✅ |
| 10 | `DataManager.mktcap` 可选（`data.py` L179-183）+ 因子中性化消费（`factor.py` L349-353）+ 优化调用面无市值输入 | 读码 + Grep | ✅ 仅 `cfg.mktcap_file` 非空才加载；BL 市值先验需新增通道的判断成立 |
| 11 | `-k p046` collect **55** / 全量 collect **1441** | `pytest --collect-only -q`（本次） | ✅ `55/1441 tests collected (1386 deselected)` |
| 12 | `pypfopt` 未装；`scipy 1.17.1 / numpy 2.4.6 / pandas 3.0.3` | 运行时实测（本次） | ✅ 与 §2.5 一致 |

**死配置/死函数（§11.1）**：`Grep` 复核——`industry_max_weight` 零生产消费（仅 `config.py` L285 定义 + `config_v2` L128/L143-144 冻结模块内校验）；`cov_shrinkage` 零消费（`config.py` L300 已标废弃 + `config_v2` L137）；`round_lot_optimize` 零引用；`round_lot` 由 `target_positions.py` L49/L131/L165 消费。四项判断全部属实。

---

## 2. 数值探针复核（复审独立重写，非复用作者脚本）

### 2.1 E1：HRP 论文距离链（Example 1-2）

| 项 | 论文值（SSRN 2708678，§14.8 转录） | 复审实测 | 结论 |
|---|---|---|---|
| `d = sqrt(½(1−ρ))` 上三角 | `0.3873 / 0.6325 / 0.7746` | PASS（`atol=1e-4`） | ✅ |
| `d̃` 列向欧氏 | `0.5659 / 0.9747 / 1.1225` | PASS | ✅ |
| `linkage(single)` 合并表 | `{0,1}@0.5659 → {2,3}@0.9747` | PASS | ✅ |
| `leaves_list` | `[2,0,1]`（确定性） | PASS | ✅ |

### 2.2 E2：BL 后验

| 项 | 复审实测 | 结论 |
|---|---|---|
| 主恒等式 `post = Π + τΣPᵀ(τPΣPᵀ+Ω)⁻¹(Q−PΠ)` | τ=0.05 / 0.5 双点 PASS（`atol=1e-12`） | ✅ |
| τ 消去（Ω=τPΣPᵀ 重算） | 0.05 与 0.5 后验逐位相同 | ✅ |
| `Ω→0` | 观点资产 → Q=0.10 | ✅ |
| `Ω→∞` | 后验 → Π | ✅ |

### 2.3 新增探针（复审发现 F-R2 的证据）：单观点倾斜的一般性

随机 5×5 PSD Σ（300 obs 样本协方差，seed=42）、单绝对观点（资产 2）、默认 `Ω=τPΣPᵀ`：

```
non-view |tilt|max = 8.88e-16（机器精度，即恰好为零）
view tilt          = 42.77（显著非零）
```

**推导**：`Ω=τPΣPᵀ` 时 `post = Π + ½ΣPᵀ(PΣPᵀ)⁻¹(Q−PΠ)`（τ 消去）→ `w = w_mkt + (1/(2δ))·Pᵀ(PΣPᵀ)⁻¹(Q−PΠ)`；单绝对观点 `P=eᵢ` 时 `Pᵀ(PΣPᵀ)⁻¹ = eᵢ/Σᵢᵢ`，倾斜向量**仅在 i 列非零**。→ 这是**一般性质**，非作者所注「该 Σ 与 P 的特殊性」（详见 F-R2）。

---

## 3. 外部锚点对码（A1-A6）

| ID | RESEARCH 主张 | 复核依据 | 结论 |
|---|---|---|---|
| A1 | 后验公式 `E[R]=[(τΣ)⁻¹+PᵀΩ⁻¹P]⁻¹[(τΣ)⁻¹Π+PᵀΩ⁻¹Q]`；先验 `Π=λΣw_mkt`；绝对/相对观点 | Idzorek 2004 PDF 全文（Formula 1NL / Formula 1 / §2.2）逐字比对 | ✅ |
| A2 | `Π=δΣw_mkt`、`w*=(δΣ)⁻¹μ`、δ=25 示例 | RESEARCH_p046 E11（He-Litterman 1999 白皮书已归档） | ✅ 未改写 |
| A3 | `tau=0.05`（0,1]）；`omega=None/"default"` → `diag(diag(τPΣPᵀ))`；`pi="equal"→1/N`、`pi=None→零向量+warning`、`pi="market"` 需 market_caps；`risk_aversion=1` | pypfopt 官方文档 + `black_litterman` 源码页（`_set_tau` / `default_omega` / `_set_pi` / `_set_risk_aversion`）逐字比对 | ✅ 全部命中 |
| A4 | 两级距离 / single linkage / 保序二分 α 拆分 | RESEARCH_p046 §14.8 逐字锚点未改动 | ✅ |
| A5 | `method="single"` = `min(dist(u[i],v[j]))`（Nearest Point）；condensed 输入 | scipy `hierarchy.linkage` 官方文档 | ✅ |
| A6 | BL 1992 仅书目（B 级），正文不逐字引用 | RESEARCH_p046 E12 扫描件结论 | ✅ 全文仅出现在「不得引用清单」，无违规引用 |

---

## 4. 复审发现（1 P2 + 3 P3，当轮全修）

| ID | 级别 | 发现 | 修复 |
|---|---|---|---|
| **F-R1-P046b-1** | **P2** | §11.1 建议删除 `cov_shrinkage`，但**未声明冻结例外**：`config_v2.py` L137 含同名字段（L128 亦含 `industry_max_weight`），且该模块 FROZEN/TD-2。若 Step 5 按字面「零残留」执行，存在误改冻结模块的陷阱（P-046a C-4 已确立「不得为对齐而修改冻结模块」先例） | §11.1 删除范围限定 `core/config.py` + 显式冻结例外；DoD「零残留」同步声明 |
| **F-R2-P046b-2** | P3 | §4.2 E2 表把「单观点仅倾斜观点资产」标注为「该 Σ 与 P 的特殊性，不能当通用不变式」——**数学上不成立**：默认 Ω 下为一般性质（§2.3 推导 + 随机 Σ 探针复算 non-view 倾斜 ≈ 8.9e-16）。原标注使一个可用的闭式不变式被丢弃 | §4.2 订正为一般性质并给出推导；建议 Step 3 将其纳入 BL 闭式测试 |
| **F-R3-P046b-3** | P3 | §7 I-P046b-3「叶序变化不影响『同一棵树』的权重」表述过宽：HRP 权重依赖保序二分的切分，任意叶置换会改变切分（3 资产树 `{2}\|{0,1}` 下叶序 `[0,1,2]` 的二分 `{0}\|{1,2}` 已不对应同一棵树）；仅**保持簇内相邻性的叶序变体**性质成立 | I-P046b-3 口径收窄：叶序由 `linkage`+`leaves_list` 确定性给出；不变式断言限于簇保序变体 / 同叶序重排一致性 |
| **F-R4-P046b-4** | P3 | §4.1 注「禁止硬编码上表权重（A5）」的 **A5 引用歧义**（外部锚 A5=scipy vs RESEARCH_p046 §8 A5 禁录制 vs 本文 DoD A-P046b-5） | 订正为显式指认「RESEARCH_p046 §8 A5 禁录制规则」 |

**范围控制（无夹带）**：✅ 无 P-046c（凯利/预算）设计内容；D3 仅以 U-P046b-1 待裁决项出现（未擅自延后定案）；无策略层/overlay/golden 数值改动。

---

## 5. 结论

**判定：Step 2 异构复审 PASS（0 P1；1 P2 + 3 P3 已当轮全修并回写 RESEARCH）。**

- 12 组代码事实全部命中 @`8f8b912`；E1/E2 数值链独立重放全过；外部锚 A1-A6 逐字一致；AST 口径未混用（P-029 口径 = **22**）；`-k p046` = **55** 复核一致。
- 遗留四项消化方案可执行：F-S9-P046-2（AST 唯一基线）/ F-S10-P046-1（zero_vol 需连带引擎 `error_type` 分流——RESEARCH 已识别 engine L1370-1384 误标风险）/ F-S10-P046-2/3 处置路径清晰。
- F-R1（冻结例外）为 DESIGN 前必须继承的约束；F-R2 修订后的「单观点倾斜一般性」可提升 BL 测试强度（闭式断言替代宽松数值断言）。

**下一步**：Step 3 DESIGN（继承 U-P046b-1..17 裁决结论 + 上述 4 项修订口径）。

> **补充调研后记（2026-11-23）**：复审后作者追加 [RESEARCH §14 架构与性能补充调研](RESEARCH_p046b_bl_hrp.md)（G-P046b-12..17 / U-P046b-12..17），并将外部锚扩至 **A7-A19**（Meucci 2010 / Boyd 2017 / Parnas 1972 / Cockburn 2005 / pluggy / Riskfolio-Lib / skfolio 等）。该补充**不改变本次复审的事实性结论**（A1-A6、代码事实、数值链均未变动）；**A7-A19 为复审后新增，未经本次逐条复审**，其分级（A/B）与引用范围由作者标注，交 Step 3/后续复审抽查；架构/性能项为 Step 3 设计输入。Step 3 需继承 U-P046b-1..17 + F-R1..F-R4。

---

## 6. A7-A19 定点复审（2026-11-23，同基座 GLM-5.3-Flash ≠ 作者 DeepSeek）

> 复审方法：① 逐条比对本轮/前轮直抓文本与 RESEARCH 断言；② 补抓注册时缺失的两个来源（scipy `pdist`、Riskfolio `portfolio.html`）；③ A18 的推断性主张升级为数值探针（E 级）。

### 6.1 逐条核验（13/13）

| ID | 断言要点 | 核验方式与结果 | 结论 |
|---|---|---|---|
| A7 | Meucci eq.(16)-(21) 后验、(20) 稳定表示、τ≈1/T (8)、Ω=(1/c)PΣPᵀ (12)、λ≈1.2、17 页 | PDF 全文直抓（interactiveadvisors 镜像，Oct 12 2010 版）——(16)-(21)/(8)/(12)/λ≈1.2 全部逐字命中；「p.5」页码未在文本层核验 → F-R6 | ✅（页码精化） |
| A8 | Walters 2014，SSRN 1314585，B 级 | SSRN 元数据 ✓；两处全文镜像抓取失败 → 维持 B 级、未引逐字，诚实 | ✅ |
| A9 | CVXPY 底座；HRP/HERC 37 risk measures；NCO；BL/Bayesian BL/Augmented BL；`Portfolio.model` ∈ {Classic, BL, FM, BLFM} | index.html 直抓 ✓（底座/37 measures/NCO 逐字）；**`model` 四取值来自官方文档搜索摘要（v7.3），latest 直抓因页面截断未达参数段** → F-R7 | ✅（口径标注） |
| A10 | Prior 与 optimization 分离；`ReturnDistribution`；BL 属 Bayesian prior；HRP 属 optimization；scikit-learn fit API | prior.html + optimization.html + arXiv 2507.04176 三处直抓，全部逐字命中 | ✅ |
| A11 | HERC，SSRN 3237540，B 级 | SSRN 摘要 ✓；未引公式，诚实 | ✅ |
| A12 | NCO，SSRN 3469961，B 级 | SSRN 作者页/摘要 ✓；未引公式，诚实 | ✅ |
| A13 | 单期/多期凸优化；holding/trading/soft constraints（§4.4-4.6）；多期只执行第一步；FnT 3(1):1-76 | arXiv 全文直抓 ✓（目录 §4.4/4.5/4.6、摘要 "only the first one executed"）；**正式版 1-76（Stanford 官方页）vs arXiv v1 页眉 1-74** → F-R5 | ✅（版本注） |
| A14 | Parnas 1972，CACM 15(12):1053-1058，模块化准则 | 全文直抓（UBC 镜像）✓ | ✅ |
| A15 | Cockburn 2005，HaT TR 2005.02，Ports & Adapters | 原文页直抓 ✓（v0.9, 2005-09-04） | ✅ |
| A16 | pluggy = pytest 插件管理核心，1400+ 插件 | 官方文档直抓 ✓ | ✅ |
| A17 | `pdist` 返回 condensed distance matrix | **本轮直抓**（注册时仅由 A5 linkage 页间接佐证）✓ → F-R7 闭合 | ✅ |
| A18 | sklearn LW 收缩强度依赖全截面 → 子集化改变数值；sample/EWMA 列向等价 | 仓内 E2（P-046a 已核，A 级）+ **本轮数值探针升级为 E 级**：LW `shrinkage` full=**0.9248** vs 子集=**1.0**，子矩阵 max\|diff\|=**4.1e-5**；sample/EWMA 子集==全矩阵子块（`atol=1e-15`） | ✅（探针升级） |
| A19 | `HRPOpt` 独立于 `EfficientFrontier`；四步概述 | 官方文档直抓（Step 1）✓ | ✅ |

### 6.2 发现（0 P1 / 0 P2 / 3 P3，当轮精化回写）

| ID | 级别 | 内容 | 处置 |
|---|---|---|---|
| F-R5-P046b-5 | P3 | A13 页数口径：正式版 FnT 3(1):1-**76**（Stanford 官方页）与 arXiv v1 页眉 1-**74** 不一致；RESEARCH 引正式版口径正确，但未标注 preprint 差异 | A13 行补注「arXiv v1 页眉 1-74」 |
| F-R6-P046b-6 | P3 | A7「p.5」页码未在抽取文本层核验（内容本身已逐字核验） | 去页码，改「Allocation 段」 |
| F-R7-P046b-7 | P3 | ① A9 `model` 参数枚举引自官方文档搜索摘要（v7.3），latest 直抓截断未达参数段；② A17 注册时未直抓（由 A5 间接佐证） | A9 行标注口径；A17 标注「定点复审直抓」闭合 |

### 6.3 定点复审结论

**判定：A7-A19 定点复审 PASS。** 13/13 锚点全部核验（A9 部分核验 + 口径标注；A8/A11/A12 维持 B 级且未越界引用）；分级（A=12 / B=3）与实际取证状态一致；「不得引用清单」无违规。3 项 P3 引用精化当轮回写 RESEARCH。A18 主张由推断升级为数值探针证据，§14.4 硬结论 1 的可信度增强。REVIEW 范围外的 §14 设计推演不属本节判定对象（Step 3/4 审）。
