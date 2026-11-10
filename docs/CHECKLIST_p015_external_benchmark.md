# CHECKLIST：P-015 外部框架对拍校准（VectorBT ↔ V3 首例）

> **批次**: P-015 · T1
> **上游**: [IMPL_p015_external_benchmark.md](IMPL_p015_external_benchmark.md)（T-1~T-4 / V1-V10）；[DESIGN_p015_external_benchmark.md](DESIGN_p015_external_benchmark.md)（I1-I5 / D1-D6）
> **实测列规则（RULE-1）**: 「实测」列只允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` 三态，禁止无证据勾选
> **状态**: Step 9/10 完稿（2026-11-10）；Step 8 见 §8；Step 10 审计见 §9

---

## 1. 验收项总表

### A 组：venv 与环境（3 项）

| ID | 验收项 | DoR | DoD | 实测 |
|----|--------|-----|-----|------|
| A-1 | `.venv-vbt` 建立且 vectorbt 可导入 | T-1.1/T-1.2 执行 | venv 内 `import vectorbt` 输出 `1.2.0`（exit 0） | ✅ E1：venv 安装 exit 0（清华镜像，官方源两次 ReadTimeout 降级）；`audit_signatures.py` 成功导入并输出 settings（[IMPL §8.1](IMPL_p015_external_benchmark.md)） |
| A-2 | requirements 钉版回填（F2） | T-1.3 执行 | `requirements-vectorbt.txt` 含 `vectorbt==1.2.0` 与传递依赖实测版本 | ✅ E1：`pip freeze` 落盘——vectorbt==1.2.0 / pandas==3.1.1 / numba==0.68.1 / numpy==2.5.4 / llvmlite==0.50.0 |
| A-3 | venv 不入 git | T-1.5 执行 | `.gitignore` 含 `.venv-vbt/`；`git status --short` 无 venv 条目 | ✅ E1：`.gitignore:28` 落地；`git status` 干净（无 venv 条目） |

### B 组：三脚本与数据交换（4 项）

| ID | 验收项 | DoR | DoD | 实测 |
|----|--------|-----|-----|------|
| B-1 | export_case 逐 case 导出成功 | T-2.1 完成 | B1-B5 五个 case 目录五件套齐全，exit 0 | ✅ E1：五 case 全部「五件套落盘」+ 现金派生自检 ≤ 5.1e-10；checksum 与设计一致（B1/B5=175，B4=384） |
| B-2 | run_vectorbt 逐 case 运行成功（venv） | T-1 + T-2.2 完成 | vbt_results/vbt_orders 落盘，exit 0 | ✅ E1：B1-B4 全部 exit 0（orders=2/10/6/6，rejected=0）；**B5 按 meta `v3_only` 豁免**（F-S9-P015-5，设计内行为） |
| B-3 | 跨 pandas CSV 往返自检通过（U-P015-2） | B-2 运行 | run_vectorbt 启动自检读数「逐元素一致」落 stdout | ✅ E1：五 case「读回自检 shape ok，checksum = …」读数与导出侧一致（pandas 2.2.3 写 → 3.1.1 读） |
| B-4 | verify_p015 全 case exit 0 | B-1~B-3 完成 | 五 case 断言全过，逐条读数输出 | ✅ E1：**28 项断言 0 失败 + 1 项豁免登记，exit 0**（P-016 D1 更正计数口径：原记 29 项含 B5 恒真豁免行；读数见 [APPENDIX §2](APPENDIX_p015_external_calibration.md)） |

### C 组：恒等式（5 项，对应 I1-I5）

| ID | 验收项 | 判据（可证伪恒等式） | 实测 |
|----|--------|----------------------|------|
| C-1 | I1 记账恒等（B1） | `qty_v3==qty_vbt==qty_spec`（rtol=1e-12）；`pv==1e7`（money_atol=1e-6） | ✅ E1：六项 max\|Δ\|=**0.000e+00**（双侧 vs 规格全零） |
| C-2 | I2 规模语义差分（B2） | **I2a（= G1 组三行 `G1.qty/cash/pv`，verify 无独立命名行——P-016 D4 / F-R5-P015-1）** + I2b/I2c 各侧对规格零残差；I2c 差 == 闭式（rtol=1e-12） | ✅ E1：I2b qty max\|Δ\|=1.164e-10；I2c（一般式，F-S9-P015-4）max\|Δ\|=**2.021e-10**；I2a 读数见同 case G1 三行 |
| C-3 | I3 费用恒等（B3，实施重定义见 DESIGN §3.3） | vectorbt 费用 == `Σ\|executed\|×P×rate`；缺口登记 | ✅ E1：10033.870913 == Σ\|executed\|×0.001（money_atol 内）；缺口 38658.94 登记（V3 费用透支不可复现部分） |
| C-4 | I4 多期逐日恒等（B4） | T=6 逐日 qty/cash/pv 三量恒等（rtol=1e-12） | ✅ E1：max\|Δ\|=**5.821e-11**（含翻转日现金过桥）；qty 终态 [625000, 416666.67, 0, 0] |
| C-5 | I5 阴性对照（B5→V3 侧，实施重定义见 DESIGN §3.5） | V3 费率扰动 0.001 → 偏移 == `−1e7×0.001`（money_atol=1e-6） | ✅ E1：offset = **−10000.000000** == expected（B3×B5 跨 case 断言） |

### D 组：文档与口径映射（3 项）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| D-1 | 附录报告入库 | `docs/APPENDIX_p015_external_calibration.md` §1-§4 齐，恒等式逐条有读数 | ✅ E1：四节齐备（签名核验 / 29 项读数表 / M1-M5 结论 / 实跑复放命令） |
| D-2 | 口径映射实测列（同一提交） | [BACKTEST_CALIBER_MAPPING.md](BACKTEST_CALIBER_MAPPING.md) §2.2 增补 vectorbt 实测列 | ✅ E1：§2.2 标题改「VectorBT 已实测」+ 实测更新块（M1-M4 口径）；与本批脚本同提交 |
| D-3 | U-P015-3 关闭 | from_orders/from_signals 签名 + defaults E1 读数落附录 §1 | ✅ E1：`audit_signatures.py` 读数落档；A5（T2）升级 E1 命中（fees=0.0/slippage=0.0） |

### E 组：纪律面（2 项）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| E-1 | 不进 CI / 不进 tests / 主环境零污染 | 主环境 `pip list` pandas 仍 2.2.3、numba 仍 0.65.1；新增文件仅 `scripts/external_benchmark/` + docs | ✅ E1：主环境 pip list pandas 2.2.3 / numba 0.65.1 / vectorbt·backtrader **零安装**；新增面 = scripts/external_benchmark×5 + docs×5 + .gitignore×1 |
| E-2 | 全量回归不劣化 | 主环境 `pytest tests` 仍 `635 passed`；`black --check` 新脚本 0 变更 | ✅ E1：`635 passed, 152 warnings in 85.68s`（MPLBACKEND=Agg）；black `5 files would be left unchanged`（格式化后复检 exit 0） |

### F 组：可重放性（2 项）

| ID | 验收项 | DoD | 实测 |
|----|--------|-----|------|
| F-1 | 复放命令留痕 | 附录 §4 含 venv 重建 + 五 case 全链复放命令（含实跑路径） | ✅ E1：附录 §4 含实跑路径 + 镜像降级说明 + 终态依赖版本 |
| F-2 | F5 红→绿记录 | IMPL §8 含红（命令+非零退出+失败行）与绿（命令+exit 0+用例计数）两读数 | ✅ E1：红 exit 1（G2 FAIL 缺 vbt 侧）→ 绿 exit 0（7 项 0 失败），见 [IMPL §8.2](IMPL_p015_external_benchmark.md) |

---

## 2. 统计

- 总数：**19 项**（A3 / B4 / C5 / D3 / E2 / F2）
- 状态（Step 10 时点）：**19/19 ✅**（逐项绑 E1 证据，RULE-2 逐项核对，非总数推算）
- **口径更正（P-016 D1）**：§9.2 取证矩阵中的「29 断言」按 P-015 时点口径（豁免行计入断言）；P-016 起为 **28 断言 + 1 豁免登记**，语义与读数不变。
- 判定：P1 = 0 / P2 = 0（实施期 5 项发现 P1×1 + P2×3 + P3×1 已全部修复并回写 DESIGN/IMPL，见 [IMPL §8.3](IMPL_p015_external_benchmark.md)）

## 8. Step 8 一致性 Review

**执行时点**: 四文档（RESEARCH / DESIGN / IMPL / CHECKLIST）完稿后的独立 pass（RULE-1）；**[RULE-4] 自查（单视角）**，异构复审留待收尾。

### 8.1 机械校验读数（2026-11-10）

| 校验项 | 命令/方法 | 读数 |
|--------|-----------|------|
| 链接存在性 | 逐个 `Test-Path` | 6/6 OK（四文档 + BACKTEST_CALIBER_MAPPING + RESEARCH_backtest_validation），0 broken |
| 预填检查（RULE-1） | `Select-String '✅\|❌'` | **1 命中 = L5 规则声明行本身**（合法），19 项实测列全 `[待 Step 9]` |
| ID 引用闭环 | 逐 ID 跨四文档计数 | U-P015-1(5)/U-P015-2(3)/U-P015-3(12)；I1(10)/I2(8)/I3(4)/I4(5)/I5(9)；T-1(22)/T-2(8)/T-3(3)/T-4(5)；V10(3)——全部双文档以上出现，无孤引 |

### 8.2 一致性发现与修复

| ID | 发现 | 处置 |
|----|------|------|
| F-S8-P015-1 | CHECKLIST 组项 ID（A1/B1...F2）与对拍 case 编号（B1-B5）撞名，跨文档引用歧义 | 组项 ID 全部改连字符形态（A-1~F-2）；DoR 引用同步（B-3 ← B-2 运行；B-4 ← B-1~B-3） |
| F-S8-P015-2 | IMPL T-3 B3 行「两次再平衡」与 freq=1 语义不符（T=4 → i=1..3 三次） | 改为「i=1..3 逐日再平衡」 |

### 8.3 对齐矩阵

| 上游 → 下游 | 对齐结果 |
|-------------|----------|
| RESEARCH U-P015-1/2/3 → DESIGN D1/D5、§5、T-1.4 → IMPL T-1/CHECKLIST D-3、B-3 | 全部有落点 |
| DESIGN B1-B5 / I1-I5 → IMPL T-2/T-3 / V3-V8 → CHECKLIST C-1~C-5 | 一一映射 |
| DESIGN §4 数据流 → IMPL T-2 产物 → CHECKLIST B 组 | 一致（三脚本 + case 五件套 + vbt 两件） |
| DESIGN D6（venv 纪律）→ IMPL T-1.5 → CHECKLIST A-3/E-1 | 一致 |

**Step 8 结论：通过**（P1=P2=0；P3×2 已当场回写）。

> **Step 9/10 追加一致性说明**：实施期 F-S9-P015-1/2/4/5 导致 DESIGN §3.2/§3.3/§3.5/§5 与 CHECKLIST C-3/C-5 判据重定义、B4 数据重构——四文档已在同一提交内同步回写（变更纪律 DESIGN §4 / mapping §5.4），C 组判据以 DESIGN 实施修正版为准。

## 9. Step 10 ADD 审计

### 9.1 审计四阶段

| 阶段 | 审计项 | 结果 |
|------|--------|------|
| Phase 0 规格质量 | DESIGN 判据可证伪（恒等式 + 阴性对照 + 容差常量）；决策表含被拒方案 | ✅ 六决策各含「拒绝理由 + 代价」；I1-I5 逐条可证伪 |
| Phase 1 完整性 | DESIGN D1-D6 / B1-B5 / I1-I5 在实施中有对应物 | ✅ D1→venv+VectorBT / D2→5 case / D3→`_spec.py` 规格层 / D4→公共 API（`DataLoaderV3`+`VectorBacktestEngine`）/ D5→双入口（orders + targetpercent 均走 from_orders，含 F-S9-P015-1 修正）/ D6→`.venv-vbt`+`.gitignore`+requirements |
| Phase 2 忠实度 | 实现与设计一致（双向对照） | ✅ T-1~T-4 逐项落物；规格模拟器逐字翻译 V3 内核锚点（G1 全零残差即忠实度实证）；偏差全部显式登记（F-S9-P015-1~5） |
| Phase 3 必要性 | 代码每个行为有设计依据 | ✅ I2c 一般式 = F-S9-P015-4 登记修正；B4 常量价 = F-S9-P015-2 处置；`v3_only` 豁免 = F-S9-P015-5 处置——无未登记派生行为 |
| Phase 4 语义 | 机械合规之外是否解决问题意图 | ✅ 本批意图 =「准确性基准 + 设计意图落地验证」：M1-M5 结论（零不可解释残差 + 两处结构性语义差异可解释）直接回答；阴性对照自证测试灵敏度（防全绿表演） |

### 9.2 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| verify_p015 全链读数（E1，29 断言 exit 0） | C-1~C-5 / B-4 | ✅ 全过；black 后终态复放确认 |
| pytest 全量（E1） | E-2 | ✅ 635 passed |
| black --check（E1） | E-2 | ✅ 5 files unchanged |
| pip list 主环境（E1） | E-1 | ✅ 零污染 |
| audit_signatures venv 读数（E1） | A-1/A-2/D-3 | ✅ defaults + API 漂移实锤 |
| git status（E1） | A-3 | ✅ venv 不入 git |
| 五 case 导出 + checksum（E1/E2，场景自选声明：case 覆盖常量价/变动价/含费/翻转/扰动五类边界） | B-1~B-3 | ✅ checksum 逐 case 复现 |
| 缺口登记读数（E2） | C-3 | ✅ 38658.94 可复现 |
| 设计-代码双向对照（E3 @本批提交） | Phase 1/2 | ✅ 见 §9.1 |
| 盲区扫描（E4，范围：规格模拟器 `_spec._simulate` 与 V3 内核逐行对照 + 未覆盖分支） | I1-I5 全部 | **发现 0 项**（降级重扫：换「未覆盖分支」角度——`n_stocks<=top_n` 且含非正因子分支未覆盖（B1-B5 全正因子）；该分支属 V3 选股语义，G1 规格已逐字翻译，风险登记为低，不阻断） |
| E5 推测 | — | 无（结论未使用推测级证据） |

### 9.3 审计结论

**P1 = 0 / P2 = 0 / P3 = 0**；E4 零发现（扫描范围已声明，一次降级重扫确认）。ADD 通过。

### 9.4 RULE-5 异构复审（2026-11-10，独立会话）

> **复审基座**: GLM-5.3-Flash（≠ 作者基座 DeepSeek-V4.1-Flash，异构性成立）
> **复审纪律**: 不信任作者结论、E1-E5 独立重放、输出只标记问题（单向权限）、P1/P2/P3 分级
> **复审对象**: P-015 全链（RESEARCH/DESIGN/IMPL/CHECKLIST 四文档 + `scripts/external_benchmark/` 五脚本 + 校准报告 @`eab4594`）

#### E1 可重放命令（独立重放 9 项）

| # | 命令 | 作者声明 | 复审实测 |
|---|------|----------|----------|
| 1 | `git rev-parse HEAD origin/master` | 同步 | ✅ 均 `eab4594`，工作区干净 |
| 2 | `pytest tests -q`（MPLBACKEND=Agg） | 635 passed | ✅ `635 passed, 152 warnings in 38.80s` |
| 3 | `black --check scripts/external_benchmark/` | 0 变更 | ✅ `5 files would be left unchanged` |
| 4 | 主环境 `pip list` | pandas 2.2.3 / numba 0.65.1 / 无 vectorbt | ✅ 同读数，零污染 |
| 5 | `git status --ignored` | venv/tmp 被豁免 | ✅ `!! .tmp_p015_cases/`、`!! .venv-vbt/` |
| 6 | `gh run list` | 两 run success | ✅ `42809038823`/`42809138807` 均 completed success |
| 7 | F5 红读数构造性重放（复制 B1 case 删 vbt 产物 → verify） | 红 exit 1 | ✅ exit 1 + `G2 [B1] FAIL — vbt_results.csv 缺失` 同形态 |
| 8 | E2-1 全链独立复放（export×5 → run×4 → verify） | 29 断言 0 失败 | ✅ `REPLAY_EXIT=0`，I5 offset −10000.000000 |
| 9 | E2-2 对抗探针 A：B5 单跑 verify | 豁免后跨 case 断言应 FAIL | ✅ `I5.negctl FAIL — B3/B5 case 未齐`，exit 1 |

#### E2 运行时取证（场景自选理由：覆盖「豁免逻辑负路径」与「规格翻译独立性」两个作者未自证的角度）

| # | 探针 | 结果 |
|---|------|------|
| 1 | 全链复放（上表 #8） | ✅ |
| 2 | 探针 A：B5 单跑 → I5 应 FAIL（case 未齐） | ✅ FAIL + exit 1——豁免登记不掩盖跨 case 断言（非恒真） |
| 3 | 探针 B：**独立重写规格模拟器**（不复用 `_spec.py`，按 DESIGN §3.2 手写 last_pv/current-NAV 两模拟 + I2c 一般式）核算 B2 | ✅ G1/G2 pv maxdiff = 1.86e-9；I2c maxdiff = **2.021e-10**（与作者读数一致）——规格翻译与闭式独立复核命中 |

#### E3 静态读码（绑 @`eab4594`，6 组锚点）

| # | 锚点 | 核对 |
|---|------|------|
| 1 | `_spec.py:97-103` select_top（`s>0` :101 / argpartition `:103`）↔ 内核 `engine_v3_vector.py:112-118` | ✅ 逐字翻译 |
| 2 | `_spec.py:129`（last_pv 规模）↔ 内核 `:128` | ✅ |
| 3 | `_spec.py:138-139`（`Σ|trade|×P×rate` + 现金净额）↔ 内核 `:146-151` | ✅（含无现金约束语义） |
| 4 | `run_vectorbt.py:47/62/66/68/79/83/85`（fees=rate+perturb、amount、cash_sharing、call_seq='auto'、targetpercent）↔ DESIGN §5 表 | ✅ 一致（含 F-S9-P015-1 修正后形态） |
| 5 | `_spec.py:157-172` i2c 一般式 ↔ DESIGN §3.2 修正公式 | ✅ 一致 |
| 6 | `requirements-vectorbt.txt` 钉版（vectorbt==1.2.0/pandas==3.1.1/numba==0.68.1/numpy==2.5.4）↔ IMPL §8.1 | ✅ |

#### E4 盲区扫描（发现 3 项，均 P3；按单向权限仅标记）

| ID | 级别 | 发现 | 建议处置 |
|----|------|------|----------|
| F-R5-P015-1 | P3 | CHECKLIST C-2 判据列写「I2a/I2b/I2c」三断言，但 verify 输出中 I2a 由 G1 组覆盖、无独立命名行——判据与读数行的命名映射未在文档写明 | C-2 判据列补注「I2a = G1 组三行」 |
| F-R5-P015-2 | P3 | B5 的 G2 豁免行（`checks.add(..., True, ...)`）形式上是**恒真行**——虽语义为豁免登记且探针 A 证明负路径真实存在（单跑即 FAIL），但与「禁止恒真断言」的纪律在形式上有张力 | 注释或报告标注「豁免登记，非断言」 |
| F-R5-P015-3 | P3 | `simulate_vbt_spec`（current-NAV 规格）的 cost 交互仅在 rate=0 下验证（B2）；未来若扩展 rate>0 的 targetpercent case，规格侧费用语义未定义 | U-P015-1（Backtrader 第二例）立项时顺带定义 |

#### E5 核查

复审结论未使用推测级证据；「作者基座 DeepSeek-V4.1-Flash」表述沿 P-013/P-014 复审先例引用（本仓台账登记），非本会话可直接重放项。

#### 复审结论

**P1 = 0 / P2 = 0 / P3 = 3（F-R5-P015-1~3，均不阻断验收，登记待后续批次）**。E1 九项、E2 三探针、E3 六组锚点全部独立命中，作者声明与实测**零偏差**；RULE-5 异构复审 **pass**。

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | RESEARCH §8（RULE-4 自查·单视角） | 2026-11-10 |
| Step 3-4 设计 + Review | 通过 | DESIGN §10（RULE-4 自查·单视角） | 2026-11-10 |
| Step 5-6 实施规划 + Review | 通过 | IMPL §7（RULE-4 自查·单视角） | 2026-11-10 |
| Step 7-8 验收清单 + 一致性 | 通过 | CHECKLIST §8（RULE-4 自查·单视角；P3×2 回写） | 2026-11-10 |
| Step 9 TDD 实施 | 完成 | F5 红→绿两读数（IMPL §8.2） | 2026-11-10 |
| Step 10 ADD 审计 | 通过 | CHECKLIST §9（取证矩阵 E1-E5） | 2026-11-10 |
| RULE-5 异构复审 | **pass** | **GLM-5.3-Flash**（≠ 作者基座，§9.4：E1 九项 / E2 三探针 / E3 六组锚点独立命中，P3×3 登记） | 2026-11-10 |
