# APPENDIX：P-015 外部对拍校准报告（VectorBT 1.2.0 ↔ V3）

> 生成物：`verify_p015.py` 自动产出（P-015 · T-4）。复放命令见 §4。

## 1. vectorbt 权威签名核验（U-P015-3）

```
（T-1.4 读数回填区：inspect.signature 读数，venv 建成后立即执行）
```

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
| G2 | B5 | vectorbt 侧按 meta 豁免（v3_only：F-S9-P015-5 现金约束语义差） | ✅ PASS | I5 阴性对照移至 V3 侧（跨 case 断言） |
| I5.negctl | B3×B5 | V3 费用扰动偏移 == −init_cash×perturb（灵敏度自证） | ✅ PASS | offset=-10000.000000 expected=-10000.000000 |

## 3. 口径映射实测结论

（T-4 回填区：I2c 语义差异 → BACKTEST_CALIBER_MAPPING §2.2 实测列）

## 4. 复放命令

```bash
# venv 重建（一次性）
python -m venv .venv-vbt
.venv-vbt/Scripts/python.exe -m pip install -r scripts/external_benchmark/requirements-vectorbt.txt
# case 全链复放
# python scripts/external_benchmark/export_case.py --case B1 --out-dir .tmp_p015_cases/B1  （逐 case）
# .venv-vbt/Scripts/python.exe scripts/external_benchmark/run_vectorbt.py --case-dir .tmp_p015_cases/B1
# python scripts/external_benchmark/verify_p015.py --case-dir .tmp_p015_cases/B1 ...
```
