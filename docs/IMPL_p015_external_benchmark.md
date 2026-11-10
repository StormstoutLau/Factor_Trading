# IMPL：P-015 外部框架对拍校准（VectorBT ↔ V3 首例）

> **批次**: P-015 · T1
> **上游**: [DESIGN_p015_external_benchmark.md](DESIGN_p015_external_benchmark.md)（D1-D6 / B1-B5 / I1-I5 / §4 数据流）；[RESEARCH_p015_external_benchmark.md](RESEARCH_p015_external_benchmark.md)（U-P015-1~3）
> **下游**: [CHECKLIST_p015_external_benchmark.md](CHECKLIST_p015_external_benchmark.md)
> **状态**: Step 5 完稿 + Step 6 Review 通过（§7）；Step 9 实施记录见 §8

---

## 1. 任务分解（T-1 ~ T-4）

### T-1 venv 建立与权威签名核验（U-P015-3）

| 步骤 | 命令/产物 | 验收 |
|------|-----------|------|
| T-1.1 | `python -m venv .venv-vbt`（主解释器 3.12.10 创建） | venv 目录就绪，python 可用 |
| T-1.2 | `.venv-vbt/Scripts/python.exe -m pip install "vectorbt==1.2.0"` | 安装成功（exit 0） |
| T-1.3 | `.venv-vbt/Scripts/python.exe -m pip freeze > scripts/external_benchmark/requirements-vectorbt.txt`（**回填实测版本，F2**） | 文件含 `vectorbt==1.2.0` 及传递依赖实测版本 |
| T-1.4 | venv 内 `inspect.signature(Portfolio.from_orders / from_signals)` + defaults 读数 → 落 `docs/APPENDIX_p015_external_calibration.md` §1 | DESIGN §5 三个待核点（targetpercent / call_seq / 拒单行为）有 E1 读数 |
| T-1.5 | `.gitignore` 追加 `.venv-vbt/` | `git status` 不出现 venv |

**回退点**：venv 损坏 → 删除目录重建（T-1.1~T-1.2 可重放）；签名与 DESIGN §5 预期不符 → 按 T-1.4 实测修正 §5 并回写 DESIGN（同一提交）。

### T-2 三脚本 + B1 case（L0）

| 步骤 | 产物 | 要点 |
|------|------|------|
| T-2.1 | `scripts/external_benchmark/export_case.py` | 构造 B1（2 标的、常量价 `[[10,25]]×T`、因子 `[[1,2]]×T`、T=5、freq=1、cost_rate=0）；跑 V3 公共 API（`DataLoaderV3.from_pandas_dataframes` + `VectorBacktestEngine`，先例 `_golden_cases.py:160-175`）；导出 meta/close/factor/spec_orders/v3_results 五件；规格解析器逐字实现 DESIGN §3.1 `qty_spec/cash_spec/pv_spec` |
| T-2.2 | `scripts/external_benchmark/run_vectorbt.py` | 读 case → `Portfolio.from_orders(size=qty, size_type='amount', price=close, fees=cost_rate, init_cash=1e7, cash_sharing=True, group_by=True)` → 导出 vbt_results/vbt_orders；pandas 3.0.3 读 CSV（U-P015-2 兼容性在此实证） |
| T-2.3 | `scripts/external_benchmark/verify_p015.py` | 断言组 G1（`qty_v3==qty_spec`、`pv_v3==1e7`）/ G2（`qty_vbt==qty_spec`、`pv_vbt==1e7`）；rtol=1e-12、money_atol=1e-6；输出逐条读数 |
| T-2.4 | **F5 红→绿** | 红：`verify_p015 --case B1` FAIL（vbt 侧缺失/不齐）→ 实现 T-2.2 并真实运行 → 绿：exit 0 + 读数落 stdout |

### T-3 B2-B5 逐层转绿

| case | 层 | 入口 | 断言 |
|------|----|------|------|
| B2 | L1 规模语义 | from_signals + targetpercent（sin 变动价，T=6） | I2a/I2b/I2c（DESIGN §3.2 闭式） |
| B3 | L2 费用 | from_orders，cost_rate=0.001，T=4（i=1..3 逐日再平衡） | I3 闭式费用 + 首日 pv |
| B4 | L3 多期累积 | 4 标的 top_n=2，翻转日 i=3，T=6，cost_rate=0 | I4 逐日三量恒等 |
| B5 | 阴性对照 | B1 数据（常量价单笔建仓），cost_rate=0.001 双侧基线 + vbt 侧 fees_perturb=0.001 | I5 偏移量精确等于 −1e7×0.001 |

### T-4 报告与口径映射回写（同提交纪律）

- `docs/APPENDIX_p015_external_calibration.md`：§1 签名核验读数 / §2 各 case 恒等式读数表 / §3 口径映射实测结论 / §4 复放命令
- [BACKTEST_CALIBER_MAPPING.md](BACKTEST_CALIBER_MAPPING.md) §2.2 增补「vectorbt 实测列」（同一提交，变更纪律 §5.4）
- PROGRESS §1.4 / §3.17 状态推进；CHANGELOG 增补

## 2. 验证项（V1-V10）

| # | 验证项 | 判据 |
|----|--------|------|
| V1 | meta.json 校验 | export_case 对非法 case 名 / 缺参数 fail-fast（exit ≠ 0） |
| V2 | 跨 pandas CSV 往返 | run_vectorbt 读入值与 case 导出值逐元素一致（run_vectorbt 启动自检，读数落 stdout） |
| V3 | G1 组恒等 | 每 case `verify_p015` 中 v3==spec 全过 |
| V4 | G2 组恒等 | 每 case vbt==spec 全过 |
| V5 | I2c 声明差异 | B2 的 vbt−v3 差与闭式恒等式读数一致（rtol=1e-12） |
| V6 | I3 闭式费用 | B3 两侧费用与 `Σ\|trade\|×P×rate` 一致（money_atol=1e-6） |
| V7 | I4 逐日恒等 | B4 T=6 全部日期三量恒等（不是只比终态） |
| V8 | I5 阴性对照 | B5 偏移量 == −1e7×0.001（money_atol=1e-6） |
| V9 | 报告完整 | 附录含 §1-§4 且每条恒等式有读数；mapping §2.2 实测列已增补 |
| V10 | 纪律面 | `.venv-vbt` 不入 git；主环境 pandas 仍 2.2.3；全量 `pytest` 仍 635 passed；`black --check` 新脚本 0 变更；脚本不在 tests/、不在 CI |

## 3. 风险与预案

| 风险 | 预案 |
|------|------|
| vectorbt 安装失败（Windows / 依赖链） | 降级：钉旧版（0.28.x 系，pandas 2.x 兼容）或改 Backtrader 首例（触发 D1 重裁，登记发现） |
| from_orders 现金不足拒单（V3 无现金约束语义差） | §5 预案②：改用净额订单或 `call_seq='auto'`；实测读数定案 |
| pandas 3.0.3 CSV 语义差异（如 dtype 推断） | V2 自检拦截；必要时显式 dtype 参数 |
| targetpercent 分组语义与预期不符 | 降级：L1 改「两侧各自对闭式规格断言」（DESIGN §3.2 已按此结构，降级不动恒等式形态） |

## 4. 排除的低效操作

- 不为 L1 再造 vectorbt 侧 from_orders 版（I2c 已覆盖声明差异）
- 不做 golden 化（对拍是一次性校准，报告入库即可，不进基线测试）
- 不包装 CLI 框架（三个平铺脚本 + argparse 即可）

## 5. 门禁影响预估

- `core/` `tests/` **零改动** → 全量 pytest 基线不变（635 passed）
- 新增 `scripts/external_benchmark/*.py` → black 检查纳入（black --check .）
- mypy 门禁范围 `core` 不变

## 6. F5 取证形态（契约字段）

- **红**：`python scripts/external_benchmark/verify_p015.py --case-dir <B1> --self-check-only` → 非零退出 + 关键失败行（vbt 侧缺文件 / 恒等式未闭合）
- **绿**：同命令 exit 0 + 各恒等式读数（逐条贴入 §8）

## 7. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本真实存在：vectorbt 1.2.0（A1/A2 T1）；venv 内传递依赖版本以 T-1.3 实测回填为准，不预填
- [x] stdlib API 下限：仅用 argparse/csv/inspect/json/pathlib/subprocess——3.12 全可用；venv 侧同样 3.12
- [x] API 签名可实现：V3 公共 API 有 `_golden_cases.py:160-175` 在仓先例；vectorbt 入口签名标注「T-1 核验后固化」（U-P015-3），无虚构声明
- [x] 兼容性声明已验证：跨 pandas CSV 往返有 V2 自检项兜底
- [x] 低效操作已排除（§4 四项）
- [x] 回退点齐备（T-1 venv 重建 / T-3 case 级重跑 / T-4 同提交回写）

**Step 6 Review 结论：通过**。可进入 Step 7 CHECKLIST。

---

## 8. Step 9 实施记录（2026-11-10 回填）

### 8.1 T-1 venv 与签名核验

- `.venv-vbt` 建立（Python 3.12.10）；`pip install vectorbt==1.2.0`：PyPI 官方源两次 `ReadTimeoutError`（网络超时）→ **降级链**：切清华镜像（`-i https://pypi.tuna.tsinghua.edu.cn/simple`）安装成功
- 钉版回填（T-1.3）：`requirements-vectorbt.txt`——**vectorbt==1.2.0 / pandas==3.1.1 / numba==0.68.1 / numpy==2.5.4 / llvmlite==0.50.0** 等全量传递依赖
- 签名核验（T-1.4，`audit_signatures.py` E1 读数）：settings defaults `fees=0.0 / slippage=0.0 / init_cash=100 / size=inf / call_seq='default'`；**from_signals 不支持 TargetPercent**（nb.py:1771）；**无 allow_negative**；无 `asset_qty` API（→ `cumsum(asset_flow)`）；`pf.cash` 是方法。**U-P015-3 关闭**（A5 T2 → E1）
- `.gitignore` 追加 `.venv-vbt/`（T-1.5）

### 8.2 F5 红→绿两读数

- **红**：`python scripts/external_benchmark/verify_p015.py --case-dir .tmp_p015_cases\B1` → **exit 1**，关键失败行 `[verify] G2 [B1] FAIL — vbt_results.csv 缺失（venv 侧未运行）`（同轮 G1 三项已 PASS：V3==规格 max|Δ|=0.000e+00，规格翻译先证正确）
- **绿**：修复 `pf.cash()` 方法调用 + `asset_flow` 累计持仓后重跑 → **exit 0，7 项断言 0 失败**（B1：G1×3 + G2×3 + I3.fees，全零残差）

### 8.3 实施期发现 5 项（全部回写）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P015-1 | P2 | vectorbt 1.2.0 免费版 `from_signals` **不支持 TargetPercent**（ValueError: Only Amount/Value/Percent supported，nb.py:1771） | B2 改 `from_orders(targetpercent)`（venv 探针实测支持）；DESIGN §5 回写 |
| F-S9-P015-2 | P1→已修 | B4 初版（变动价）出现**负持仓**（-1564/-1319）：V3 内核无现金约束（`:151` 净额扣减），规格在 01-04 产生超现金补仓；vectorbt 现金不足拒单 → 次日卖单超实际持仓。`allow_negative` 不存在 → 语义无法参数化对齐 | B4 重构为**常量价翻转**（消除病理，保留多期+翻转覆盖）；DESIGN §3.3/§5 回写；语义差异登记口径映射（M4） |
| F-S9-P015-3 | P3 | 1.2.0 API 漂移：`pf.cash` 为方法非属性；无 `asset_qty`（0.x 时代 API） | `pf.cash()` + `cumsum(pf.asset_flow())` |
| F-S9-P015-4 | P2 | **I2c 闭式缺陷**：原推导隐含「两侧路径重合」，分叉后现金抵消不成立（初测 max\|Δ\|=25.8） | 闭式一般式：`Δ_j[i] = (V_cur_vbt[i] − pv_v3[i-1])/(n·P[i,j])`；修正后 max\|Δ\|=2.0e-10；DESIGN §3.2 回写 |
| F-S9-P015-5 | P2 | **B3/B5 fees>0 时 vbt↔spec 全等结构性不可达**（V3 费用透支 vs vbt 部分成交；B3 实测 fees_vbt=10033.87 < 闭式 10072.53） | B3 断言重定义为「vbt 费用模型一致性 Σ\|executed\|×P×rate == ΣFees」+ 缺口登记 38658.94；B5 阴性对照移至 **V3 侧**（cost_rate 0.001→0.002）；DESIGN §3.3/§3.5 回写 |

### 8.4 终态恒等式读数（29 项断言 0 失败，exit 0）

| 层 | case | 关键读数 |
|----|------|----------|
| I1 记账 | B1 | 两侧 vs 规格全零残差；pv==1e7 |
| I2 规模语义 | B2 | I2b/I2c 闭式差 max\|Δ\|=2.0e-10；G1 ≤ 2.6e-9 |
| I3 费用 | B3 | vbt 费用模型一致性 PASS；缺口 38658.94 登记 |
| I4 多期翻转 | B4 | 全等（含现金过桥）max\|Δ\|=5.8e-11；qty 终态 [625000, 416666.67, 0, 0] |
| I5 阴性对照 | B3×B5 | offset = **−10000.000000** == expected（灵敏度自证） |

详见 [APPENDIX_p015_external_calibration.md](APPENDIX_p015_external_calibration.md)。

### 8.5 门禁实测（T-4 时点）

| 项 | 读数 | 出口 |
|----|------|------|
| `pytest tests` | `635 passed` | CHECKLIST_p015 E-2 |
| `black --check scripts/external_benchmark/` | `5 files would be left unchanged` | CHECKLIST_p015 E-3 |
| 主环境 pip list | pandas 2.2.3 / numba 0.65.1，无 vectorbt | CHECKLIST_p015 E-1；PROGRESS §3.17.1 Step 10 |

> **P-017 说明（F-R5-P016-2）**：T-4 时点（本批 Step 9）的原始门禁读数未单独保全，上表为同批终态口径的读数出口指向，不冒称 T-4 时点证据。此前本节为「回填区」占位，已按 P-017 D2 回填。
