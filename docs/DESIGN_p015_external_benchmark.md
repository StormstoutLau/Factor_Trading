# DESIGN：P-015 外部框架对拍校准（VectorBT ↔ V3 首例）

> **批次**: P-015 · T1
> **上游**: [RESEARCH_p015_external_benchmark.md](RESEARCH_p015_external_benchmark.md)（框架裁决 V-A + O-A，用户确认 2026-11-10）；[BACKTEST_CALIBER_MAPPING.md](BACKTEST_CALIBER_MAPPING.md) §2.1（V3 语义列）/§4（恒等式纪律）/§5.3（启用前置）
> **下游**: [IMPL_p015_external_benchmark.md](IMPL_p015_external_benchmark.md)；[CHECKLIST_p015_external_benchmark.md](CHECKLIST_p015_external_benchmark.md)
> **代码证据时点**: HEAD `607f1c3`（E1 2026-11-10）
> **状态**: Step 3 完稿 + Step 4 Review 通过（§10）

---

## 1. 目标与边界

**目标**：用 VectorBT 1.2.0（隔离 venv）对 V3 `VectorBacktestEngine` 做一次性准确性校准——把「信号 → 成交 → 账目」共同核心的每一层残差写成**可证伪恒等式**并配阴性对照；不可解释的残差即缺陷（A28 原则）。

**职责外（不回答）**：
- V2 对拍（Backtrader 第二例，U-P015-1）；Qlib 对外声明（U-4 原判据，不在本批）；
- 选股逻辑的「优劣」评价（对拍只问「是否与声明规格一致」，不问「策略好不好」）；
- vectorbt 自身正确性背书（它是参照物，不是被验收对象）。

**能力边界（回答不了）**：
- vectorbt 权威默认签名在 venv 建成前无法落 E1（U-P015-3，T-1 任务补齐）；
- 浮点一致性受两侧求值顺序影响，恒等式用 rtol=1e-12 + money_atol=1e-6（golden 容差先例 `_golden_cases.py:34`），不做逐位比较。

---

## 2. 设计决策表（D1-D6）

> 每项含被拒方案 + 拒绝理由 + 代价（品味可审查化）。

| # | 决策 | 被拒方案 | 拒绝理由 | 代价 |
|---|------|----------|----------|------|
| D1 | 首例框架 **VectorBT ↔ V3**；产物 **隔离 venv + CSV 文件交换** | Backtrader↔V2 首例 / 三库并行；主环境直装 / tests 常驻 skip | RESEARCH §5 已裁决（残差最少原则 + A2 依赖冲突 + P7 纪律） | 本批不覆盖 V2（第二例登记 U-P015-1） |
| D2 | 对拍**分层**：L0 记账 → L1 规模语义 → L2 费用 → L3 多期累积，每层一个独立 case | 端到端全功能单 case 对拍 | A30①（把共性拆到最小、逐项对齐）；单 case 残差混合多概念不可归因 | case 数量 4-5 个（可接受） |
| D3 | **每侧对自己的声明规格断言**，规格之间差异写成恒等式 | 直接互比两侧输出（A 依赖 B 的输出） | 互比会把实现差异伪装成规格差异；规格先行才能把残差归因到具体语义 | driver 需实现规格解析器（约 60 行） |
| D4 | V3 走**公共 API 端到端**（构造因子使选择确定），不注入 targets、不直调内核 | 直调 `_rebalance_kernel` / 注入目标仓位 | 绕过公共 API 测不到真实路径；内核直调仅留作调试手段 | 因子需精心构造（正号、无并列、翻转日无同值） |
| D5 | vectorbt 双入口：**from_orders 显式订单**（L0/L2/L3 记账层）+ **targetpercent 规模再平衡**（L1 规模层） | 只用 from_signals(entries/exits) | 信号进出语义与 V3「目标权重再平衡」语义不同构；targetpercent 才对应权重语义 | 两种入口都要在 T-1 核签名（U-P015-3） |
| D6 | venv 落仓根 `.venv-vbt/` + `.gitignore`；版本钉 `requirements-vectorbt.txt`（安装后回填实测版本，F2） | pyproject optional-dependencies / uv 临时环境 | P7 纪律：外部框架不进主环境声明面；optional-deps 会被误装 | venv 需重建脚本化（requirements 可重现） |

---

## 3. 对拍分层与恒等式（B1-B5）

### 3.0 共享案例规格

- **标的与资金**：L0-L2 用 2 标的（`n_stocks=2 <= top_n=2` → V3 内核走 `signal > 0` 分支，`engine_v3_vector.py:112-113@607f1c3`），L3 用 4 标的 + `top_n=2`（argpartition 分支 `:116-118`）。
- **因子构造（D4）**：L0-L2 因子取正常数（如 `[[1, 2]]×T`，两标的恒入选）；L3 因子取互异正值且在预定翻转日**变序不变值域**（杜绝 `abs >= threshold` 并列超选）。
- **定价**：确定性函数（sin 波动 / 常量），无随机数；`initial_capital=1e7`；`cost_rate` 按 layer 取 0 或 0.001。
- **日期**：`rebalance_freq=1` → V3 在 `i=1..T-1` 逐日再平衡（首日只估值不交易，`:313-316`）。

### 3.1 B1（L0）记账恒等——零费用、常量价

三方可比对象：**目标持仓 qty、现金 cash、逐日净值 pv**。

规格（两侧共享的声明式定义）：
```
qty_spec[i, j] = pv[i-1] / (n_selected × P[i, j])      # V3 内核 :128-135 逐字翻译
cash_spec[i]   = cash[i-1] − Σ_j (qty_spec[i,j] − qty[i-1,j]) × P[i,j]   # 费用=0
pv_spec[i]     = cash_spec[i] + Σ_j qty_spec[i,j] × P[i,j]
```

**I1**：`qty_v3 == qty_vbt == qty_spec`（rtol=1e-12）；`pv_v3 == pv_vbt == 1e7`（money_atol=1e-6）。
阴性预期：若一侧把「比例费用」误作用于零费用 case，pv 即偏离 1e7 → I1 破。

### 3.2 B2（L1）规模语义差分——变动价、零费用

V3 规模参考值 = **前一日组合价值** `last_pv`（`:128`）；vectorbt `targetpercent` = **当日盯市值**。两规格的差异写成恒等式：

```
qty_v3_spec[i,j]     = pv[i-1] / (n × P[i,j])
qty_vbt_spec[i,j]    = V_cur[i]  / (n × P[i,j])，  V_cur = cash[i-1] + Σ_k qty[i-1,k]×P[i,k]
                                   = pv[i-1] + Σ_k qty[i-1,k]×(P[i,k] − P[i-1,k])
⇒ I2a: qty_v3[i,j] − qty_v3_spec[i,j] == 0                （V3 对自己规格）
  I2b: qty_vbt[i,j] − qty_vbt_spec[i,j] == 0              （vectorbt 对自己规格）
  I2c: qty_vbt_spec[i,j] − qty_v3_spec[i,j]
       == [Σ_k qty[i-1,k]×(P[i,k] − P[i-1,k])] / (n × P[i,j])   （声明差异，闭式可算）
```

> I2c 即本批第一个**口径映射实测产出**：V3 的 `last_pv` 定规模与 vectorbt 的 current-value 定规模之差，逐日可算。BACKTEST_CALIBER_MAPPING §2.2 的「外部默认值表」自此开始有实测列。

### 3.3 B3（L2）费用恒等——比例费用、含费用再平衡

**I3**：两侧各自费用 == 闭式 `Σ_j |trade_j| × P[j] × cost_rate`（V3 `:146-148` / vectorbt `fees` 按订单名义值）；首日 `pv == 1e7 × (1 − cost_rate)`（money_atol=1e-6）。

### 3.4 B4（L3）多期累积——4 标的、选股翻转、零费用

driver 按声明规格复算选股（`abs(signal)` top-2，逐日）、规格 qty 与逐日 cash/pv，vectorbt 以 from_orders 执行同一规格订单序列。

**I4**：T=6 日内**逐日** `qty / cash / pv` 三量恒等（rtol=1e-12）；覆盖「卖出旧选股 + 买入新选股」的现金过桥。

### 3.5 B5 阴性对照——测试灵敏度自证

取 B3 case，仅 vectorbt 侧 `fees += 0.001`：
**I5**：`pv_vbt − pv_v3 == −1e7 × 0.001`（money_atol=1e-6）。
> 若扰动后读数不等于声明偏移，说明恒等式框架不敏感——本批测试**必须**能检出（否则全部 I1-I4 的「绿」不可信）。

---

## 4. 产物形态与数据流（O-A）

```
scripts/external_benchmark/
├── requirements-vectorbt.txt   # venv 钉版（安装后回填实测版本号，F2）
├── export_case.py              # [主环境] 构造 case → 跑 V3 → 写 case 目录
├── run_vectorbt.py             # [.venv-vbt] 读 case → vectorbt 对拍 → 写 vbt_results.csv
└── verify_p015.py              # [主环境] 读两侧 → 断言 I1-I5 → 写报告

case 目录（.tmp 外部产物，不入库）:
  meta.json / close.csv / factor.csv / spec_orders.csv / v3_results.csv
  → run_vectorbt.py 追加 vbt_results.csv / vbt_orders.csv
  → verify_p015.py 产出 docs/APPENDIX_p015_external_calibration.md + .json
```

- **venv**：`.venv-vbt/`（`.gitignore` 追加一行）；主环境只跑 export/verify，venv 只跑 run_vectorbt（D3 CSV 交换隔离 pandas 2.2.3 ↔ 3.0.3）。
- **报告**：`docs/APPENDIX_p015_external_calibration.md` 为**生成物入库**（恒等式逐条读数）；BACKTEST_CALIBER_MAPPING §2.2 同提交增补实测列（变更纪律 §5.4）。
- **不进 CI / 不进 tests/**（P7 纪律）；脚本可独立重放（E1）。

## 5. vectorbt 调用规格（T-1 核验后固化）

| 层 | 入口 | 关键参数（待 U-P015-3 核验签名后固化） |
|----|------|----------------------------------------|
| L0/L2/L3 | `Portfolio.from_orders` | `close=close.csv`、`size=qty 数组`、`size_type='amount'`、`price=close`、`fees=cost_rate`、`init_cash=1e7`、`cash_sharing=True, group_by=True` |
| L1 | `Portfolio.from_signals` | `entries=再平衡日掩码`、`size=1/n`、`size_type='targetpercent'`、`call_seq='auto'`（先卖后买，防现金不足拒单）、`fees=0` |

已知风险预案（T-1 核验时按实测修正）：① targetpercent 对 group 的 call_seq 语义；② 订单现金不足时的拒单行为（V3 内核**无现金约束**，`:151` 直接净额扣减，可能出现瞬时负现金——vectorbt 侧需对齐此语义，必要时改用 from_orders 净额单）；③ `size_granularity` 默认 nan（无整手）与 V3 连续股数同构，无需设置。

## 6. 不变量汇总（I1-I5）

见 §3 各层；验证形态 = `verify_p015.py` 退出码 + 报告逐条读数（E1 可重放）。

## 7. 接口签名

```python
# export_case.py [主环境]
python scripts/external_benchmark/export_case.py --case B1 --out-dir <case_dir>
# 内部复用 tests/_synth_fixture 的构造惯例 + DataLoaderV3.from_pandas_dataframes + VectorBacktestEngine（_golden_cases.py:160-175 先例）

# run_vectorbt.py [venv]
.venv-vbt/Scripts/python.exe scripts/external_benchmark/run_vectorbt.py --case-dir <case_dir>

# verify_p015.py [主环境]
python scripts/external_benchmark/verify_p015.py --case-dir <case_dir> --report docs/APPENDIX_p015_external_calibration.md
```

`meta.json` schema：`{"case": "B1", "layer": "L0", "spec_version": "1.0", "T": int, "n_stocks": int, "top_n": int, "rebalance_freq": 1, "cost_rate": float, "init_cash": 10000000.0, "entry_mode": "orders"|"targetpercent"}`。

## 8. V3 语义锚点（规格翻译依据，E3 @`607f1c3`）

| 锚点 | 语义 | 对规格的影响 |
|------|------|--------------|
| `engine_v3_vector.py:112-113` | `n_stocks <= top_n` → `signal > 0` 入选 | L0-L2 因子必须全正 |
| `:116-118` | argpartition 取 `abs >= threshold`，并列超选 | L3 因子值域互异 |
| `:128` | 目标值 = `last_pv × 1/n_selected` | 规模参考值 = 前一日 pv（B2 核心） |
| `:132` | `prices > 0` 才生成目标仓 | 价格恒正 |
| `:138-140` | 非 sellable 持仓目标清零 | 本批 cases 全 sellable（掩码不进首例范围） |
| `:146-151` | 费用 = Σ\|trade\|×P×rate；现金无约束净额扣减 | B3 闭式；瞬时负现金预案（§5 ②） |
| `:313-323` | 首日只估值；`i % freq == 0` 再平衡 | 首笔交易在 i=1 |

## 9. 实施批次预告（供 IMPL 展开）

- **T-1** venv 建立 + `inspect.signature` 权威读数（U-P015-3）+ requirements 回填
- **T-2** export_case / run_vectorbt / verify_p015 三脚本（B1 case 先行，F5 红→绿从 I1 开始）
- **T-3** B2-B5 cases 逐层转绿 + 阴性对照
- **T-4** 报告落档 + BACKTEST_CALIBER_MAPPING §2.2 实测列增补（同提交）

## 10. Step 4 Review（设计文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明：本 Review 与正文同会话，无第二视角；RULE-5 异构复审留待实施收尾（P-013/P-014 先例）。

- [x] 设计基于已验证的调研结论（V-A/O-A 裁决 + A1-A6 证据 + V3 语义锚点 E3 逐条绑定）
- [x] 无未经验证的假设——vectorbt 签名细节**显式未验证**，以 U-P015-3 + §5「待核验后固化」标注，不作为已证结论使用
- [x] 无论证驱动的归因扭曲（未裁剪 A27/A28 的多因结论：成交模型只是第一根因，本批分层设计保留了费用/规模/累积三个独立差异源）
- [x] 替代方案已列并被否决（D1-D6 六项，各含理由 + 代价）
- [x] 职责边界清晰（§1 职责外 3 项 / 能力边界 2 项，两类分开声明）

**Step 4 Review 结论：通过**。可进入 Step 5 IMPL。
