# APPENDIX：P-015 外部对拍校准报告（VectorBT 1.2.0 ↔ V3）

> 生成物：`verify_p015.py` 自动产出（P-015 · T-4）。复放命令见 §4。
> 口径（P-016 D1）：§2 共 **28 项断言 + 1 项豁免登记**——「— 豁免（非断言）」行只保留可见性，不计入断言数、不参与通过/失败判定（F-R5-P015-2）。

## 1. vectorbt 权威签名核验（U-P015-3，E1 @venv `.venv-vbt`，2026-11-10；P-016 现场重放）

```
== settings.portfolio defaults ==
fees = 0.0          slippage = 0.0
init_cash = 100.0   size = inf     call_seq = 'default'
== from_orders / from_signals 关键参数 ==
均接受 size / size_type / price / fees / init_cash / cash_sharing / group_by /
call_seq / allow_partial / min_size / size_granularity / direction（默认 None →
运行时从 settings 解析）；from_orders 无 upto（PRO 专属）。
== 实测裁决（本批使用口径）==
- from_signals 不支持 TargetPercent（nb.py:1771 仅 Amount/Value/Percent）
  → B2 走 from_orders(targetpercent)（F-S9-P015-1）
- settings 无 allow_negative（仅 lock_cash / allow_partial）
  → V3「费用透支现金」语义无法参数化对齐（F-S9-P015-2）
- 无 asset_qty API → 逐日持仓 = cumsum(asset_flow)（F-S9-P015-3）
- pf.cash 为方法（非属性）
```

**U-P015-3 关闭**：RESEARCH A5（T2 片段「fees=0.0 / slippage=0.0」）升级为 E1 实测命中。

> **本节回填状态（P-016 F-S9-P016-1）**：本段与 §3/§4 属**人工维护章节**。P-015 曾因最终全链复放 `--report` 指向本文件而被占位模板覆盖一次；P-016 已加入生成器保护（命中人工标记时改写 `.generated.md`）并重新回填本节。

## 2. 恒等式逐条读数

| ID | case | 断言 | 结果 | 读数 |
|----|------|------|------|------|
| G1.qty | B1 | V3 逐日持仓 == 规格（rtol=1e-12） | ✅ PASS | max|Δ|=0.000e+00 |
| G1.cash | B1 | V3 逐日现金 == 规格（money_atol=1e-6） | ✅ PASS | max|Δ|=0.000e+00 |
| G1.pv | B1 | V3 逐日净值 == 规格 | ✅ PASS | max|Δ|=0.000e+00 |
| G2.qty | B1 | vectorbt 逐日持仓 == 规格 | ✅ PASS | max|Δ|=0.000e+00 |
| G2.cash | B1 | vectorbt 逐日现金 == 规格 | ✅ PASS | max|Δ|=0.000e+00 |
| G2.pv | B1 | vectorbt 逐日净值 == 规格 | ✅ PASS | max|Δ|=0.000e+00 |
| I3.fees | B1 | 零费用 case 费用合计 == 0 | ✅ PASS | fees=0.000000 |
| G1.qty | B2 | V3 逐日持仓 == 规格（rtol=1e-12） | ✅ PASS | max|Δ|=1.746e-10 |
| G1.cash | B2 | V3 逐日现金 == 规格（money_atol=1e-6） | ✅ PASS | max|Δ|=2.605e-09 |
| G1.pv | B2 | V3 逐日净值 == 规格 | ✅ PASS | max|Δ|=1.863e-09 |
| I2b.qty | B2 | vectorbt 逐日持仓 == current-NAV 规格 | ✅ PASS | max|Δ|=1.164e-10 |
| I2b.pv | B2 | vectorbt 逐日净值 == current-NAV 规格 | ✅ PASS | max|Δ|=1.863e-09 |
| I2c.diff | B2 | qty_vbt − qty_v3 == 声明闭式（last_pv vs current-NAV 规模差） | ✅ PASS | max|Δ|=2.021e-10 |
| G1.qty | B3 | V3 逐日持仓 == 规格（rtol=1e-12） | ✅ PASS | max|Δ|=1.746e-10 |
| G1.cash | B3 | V3 逐日现金 == 规格（money_atol=1e-6） | ✅ PASS | max|Δ|=1.171e-09 |
| G1.pv | B3 | V3 逐日净值 == 规格 | ✅ PASS | max|Δ|=1.863e-09 |
| I3.fees | B3 | vectorbt 费用 == Σ|executed|×P×rate（费用模型一致性） | ✅ PASS | executed_value=10033870.9127 fees_vbt=10033.870913 |
| G1.qty | B4 | V3 逐日持仓 == 规格（rtol=1e-12） | ✅ PASS | max|Δ|=5.821e-11 |
| G1.cash | B4 | V3 逐日现金 == 规格（money_atol=1e-6） | ✅ PASS | max|Δ|=0.000e+00 |
| G1.pv | B4 | V3 逐日净值 == 规格 | ✅ PASS | max|Δ|=0.000e+00 |
| G2.qty | B4 | vectorbt 逐日持仓 == 规格 | ✅ PASS | max|Δ|=5.821e-11 |
| G2.cash | B4 | vectorbt 逐日现金 == 规格 | ✅ PASS | max|Δ|=0.000e+00 |
| G2.pv | B4 | vectorbt 逐日净值 == 规格 | ✅ PASS | max|Δ|=0.000e+00 |
| I3.fees | B4 | 零费用 case 费用合计 == 0 | ✅ PASS | fees=0.000000 |
| G1.qty | B5 | V3 逐日持仓 == 规格（rtol=1e-12） | ✅ PASS | max|Δ|=0.000e+00 |
| G1.cash | B5 | V3 逐日现金 == 规格（money_atol=1e-6） | ✅ PASS | max|Δ|=2.776e-17 |
| G1.pv | B5 | V3 逐日净值 == 规格 | ✅ PASS | max|Δ|=0.000e+00 |
| G2 | B5 | vectorbt 侧按 meta 豁免（v3_only：F-S9-P015-5 现金约束语义差） | — 豁免（非断言） | I5 阴性对照移至 V3 侧（跨 case 断言） |
| I5.negctl | B3×B5 | V3 费用扰动偏移 == −init_cash×perturb（灵敏度自证） | ✅ PASS | offset=-10000.000000 expected=-10000.000000 |

## 3. 口径映射实测结论

| # | 实测结论 | 证据 |
|---|----------|------|
| M1 | **vectorbt 记账核心与声明规格全等**：零费用下逐日 qty/cash/pv 与闭式规格零残差（B1 全零 / B4 5.8e-11，含选股翻转与现金过桥） | §2 B1/B4 G1+G2 |
| M2 | **规模语义差异（V3 last_pv vs vectorbt current-NAV）**：两侧各自对其规格零残差，且差异逐日精确等于声明闭式（max\|Δ\|=2.0e-10）——A28「可逐美元解释」在规模层成立 | §2 B2 I2b/I2c |
| M3 | **vectorbt 费用模型 = 名义值比例制**：Σ\|executed\|×P×rate == ΣFees（money_atol 内）；无下限、无单边税——与 V3 `cost_rate` 同构 | §2 B3 I3.fees |
| M4 | **V3 无现金约束（费用透支）是结构性口径差异**：rate>0 时 V3 首日现金即 −10000；vectorbt 现金不足部分成交 → 请求 vs 执行价值缺口 38658.94，`allow_negative` 不存在于 1.2.0 免费版 → vbt↔spec 全等在 rate>0 时结构性不可达；对拍断言改为「费用模型一致性 + 缺口登记」 | §2 B3 缺口登记；§1 实测裁决 |
| M5 | **阴性对照灵敏度自证通过**：V3 费率扰动 0.001 → pv 偏移 −10000.000000 精确命中声明值（否则 M1-M4 的「绿」不可信） | §2 B3×B5 I5 |

**准确性结论（对应本批目的）**：V3 的「信号 → 成交 → 账目」核心会计在共同核心域内与 vectorbt **零不可解释残差**；两处结构性语义差异（M2 规模参考值 / M4 现金约束）均已写成恒等式或缺口登记，无未归因残差——**「准确计算、实现回测机制设计意图」的准确性校准通过**。

## 4. 复放命令（实跑路径 @`f:\Coding\Factor_Trading_v3.0`，2026-11-10）

```bash
# venv 重建（一次性；PyPI 直连超时时用清华镜像——实装记录见 requirements-vectorbt.txt）
python -m venv .venv-vbt
.venv-vbt/Scripts/python.exe -m pip install -r scripts/external_benchmark/requirements-vectorbt.txt

# 签名核验（U-P015-3）
.venv-vbt/Scripts/python.exe scripts/external_benchmark/audit_signatures.py

# case 全链（逐 case B1-B5；B5 为 v3_only，run_vectorbt 自动跳过）
python scripts/external_benchmark/export_case.py --case B1 --out-dir .tmp_p015_cases/B1
.venv-vbt/Scripts/python.exe scripts/external_benchmark/run_vectorbt.py --case-dir .tmp_p015_cases/B1

# 全量恒等式断言（本报告 §2 的生成命令）
python scripts/external_benchmark/verify_p015.py --case-dir .tmp_p015_cases/B1 .tmp_p015_cases/B2 .tmp_p015_cases/B3 .tmp_p015_cases/B4 .tmp_p015_cases/B5 --report docs/APPENDIX_p015_external_calibration.md
```

> **报告保护（P-016 D2 / F-S9-P016-1）**：本文件含人工章节（§1/§3/§4），上述 `--report` 会**自动改写** `docs/APPENDIX_p015_external_calibration.generated.md` 并打印 `[保护]` 提示，原文件不被覆盖；请比对 `.generated.md` 的 §2 后人工合并。
>
> 环境实测：Python 3.12.10；venv 依赖 vectorbt==1.2.0 / pandas==3.1.1 / numba==0.68.1 / numpy==2.5.4（清华镜像安装，主环境 pandas 2.2.3 / numba 0.65.1 零污染）。
