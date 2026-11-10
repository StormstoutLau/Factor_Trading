# RESEARCH：P-015 外部框架对拍校准（U-4 触发 · 单框架打通）

> **批次**: P-015「外部框架对拍校准——先单框架打通方法论」
> **上游**: [RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md) §6/§8（方案矩阵 X-A/X-B + U-4 四元块）；[BACKTEST_CALIBER_MAPPING.md](BACKTEST_CALIBER_MAPPING.md) §2.2/§5（外部默认值表 + 启用前置）；PROGRESS §1.4 P-011 收尾（L428 排序声明）
> **用户裁决（2026-11-10）**: ① 正式立项，走 spec 流程；② **先一个框架打通**，再扩展其余
> **代码证据时点**: HEAD `607f1c3`（工作区干净，E1 2026-11-10）；Python 3.12.10
> **档位**: T1（产物落 `scripts/external_benchmark/`，Layer-1）
> **状态**: Step 1 完稿 + Step 2 Review 通过（§8）；待框架选择确认后进 Step 3

---

## 1. 背景与目的

**用户意图（2026-11-10 原话归纳）**：外部框架 Qlib / Backtrader / VectorBT 作为**准确性基准**——当前框架确实实现了更复杂的功能，但问题排查链路也复杂，所以需要外部框架进行对比；**首要目的是准确计算，验证回测机制设计意图真正落地**。

三个边界声明（防目标漂移）：

1. **对拍 ≠ 功能对齐**：外部框架不实现本仓的停牌掩码 / 涨跌停规则 / 退市结算等，对拍只在「信号 → 成交 → 账目」共同核心上进行。
2. **对拍 ≠ 数值一致声明**：A28 原则（P-011 锚点）——差异本身不是缺陷，**不可解释的差异才是缺陷**。产出形态是「残差逐项归因闭合」，不是「结果相同」。
3. **对拍 ≠ 常驻 CI**：台账纪律（RESEARCH_backtest_validation §7）——外部框架仅做**一次性统计校准**，不进主环境、不进 CI 常驻依赖。

**触发确认**：U-4 四元块的触发条件「用户/评审要求第三方框架对照时」——用户 2026-11-10 的说明构成该触发，本批为 U-4 的正式激活与收口。

---

## 2. 本仓事实（P1-P8）

| # | 事实 | 证据 |
|---|------|------|
| P1 | 口径映射文档已存在，但外部三库默认值列明确标注「**仅作对照，本仓未实测**」（U-4 = X-B 未启用） | E3 @`607f1c3` [BACKTEST_CALIBER_MAPPING.md](BACKTEST_CALIBER_MAPPING.md) §2.2、§5.2 |
| P2 | 内部等价基线当前为绿：`test_cross_engine_equivalence.py` **5 passed** | E1 `pytest tests/test_cross_engine_equivalence.py -q`（2026-11-10 @`607f1c3`，退出 0） |
| P3 | 主环境读数：Python 3.12.10 / numpy 2.4.6 / pandas 2.2.3 / numba 0.65.1 / llvmlite 0.47.0；**vectorbt / backtrader / pyqlib 零安装** | E1 `python -m pip list` 过滤读数（2026-11-10） |
| P4 | 本仓依赖松钉（`numpy>=1.23.0` / `pandas>=2.0.0`）；numba **非必需依赖**——CI 无 numba 时 JIT 性能测试 importorskip，V3 内核走 `py_func` 回退 | E1 [pyproject.toml](../pyproject.toml) L28-30；E3 @`607f1c3` [test_numba_jit_performance.py](../tests/test_numba_jit_performance.py) L24、[engine_v3_vector.py](../core/engine_v3_vector.py) L50-56 |
| P5 | V3 内核语义锚点：`@njit` 再平衡内核、`cost_rate` 比例费用（`abs(trade)×price×cost_rate`，默认 0.001）、同日 `close[i]` 成交 | E3 @`607f1c3` engine_v3_vector.py L78/L88/L148/L389；[BACKTEST_CALIBER_MAPPING.md](BACKTEST_CALIBER_MAPPING.md) §2.1 |
| P6 | 残差恒等式 + 阴性对照纪律已立（内部 V2↔V3 已闭环；外部侧无对应物） | E3 @`607f1c3` BACKTEST_CALIBER_MAPPING.md §4 |
| P7 | 纪律：外部框架一次性校准、不常驻 CI（避免口径映射维护成本，project memory L88 + RESEARCH_backtest_validation §7 L343） | E3 @`607f1c3` |
| P8 | U-4 原判据：「是否需要『与 Qlib 一致』的对外声明；若仅内部校准，X-A 足够」；本批触发后范围**收窄**为「准确性校准」而非「对外声明」 | E3 @`607f1c3` [RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md) §8 |

> P8 是关键裁决输入：U-4 原倾向 X-A（映射文档 + 内核差分）即 P-011 已交付的部分；本批补的是 X-B 的**最小形态**——单框架一次性校准。Qlib 级别的「对外声明」仍不在本批范围。

---

## 3. 外部证据

### 3.1 来源清单（F1 来源日期 / F2 版本 / Layer）

| # | 来源 | Layer | 版本 | 读取日 | 形态 |
|---|------|-------|------|--------|------|
| A1 | [PyPI: vectorbt](https://pypi.org/project/vectorbt/) | T1 | 1.2.0（发布 2026-10-19） | 2026-11-10（读取日） | WebFetch 全页 |
| A2 | [vectorbt pyproject.toml @master](https://raw.githubusercontent.com/polakowo/vectorbt/master/pyproject.toml) | T1 | master（对应 1.2.0） | 2026-11-10（读取日） | WebFetch 原文 |
| A3 | [PyPI: backtrader](https://pypi.org/project/backtrader/) | T1 | 1.9.78.123（发布 2023-04-19） | 2026-11-10（读取日） | WebFetch 全页 |
| A4 | [PyPI: pyqlib](https://pypi.org/project/pyqlib/) | T1 | 0.9.7（发布日期页未渲染，**未回查**） | 2026-11-10（读取日） | WebFetch（截断） |
| A5 | vectorbt 官方 docs 域（nb 签名页，经检索片段） | T2 | 1.2.0 对应 docs | 2026-11-10（读取日） | WebSearch 片段 |
| A6 | P-011 锚点 A27/A28/A29（QuantEngines / FeedsMonitor 实测文章转引） | T4→T1 回溯件 | — | P-011 批内已回溯 | 转引（见 RESEARCH_backtest_validation §11） |

**降级链（F3）**：vectorbt.dev 文档页 JS 渲染 → WebFetch 空内容（第一跳失败）→ 降级 raw.githubusercontent 源码 → 文件过大截断（15.6KB / 全文件约数百 KB，未达 `from_signals` 签名区）→ 降级 docs rst 源文件 → 路径不存在（1.2.0 文档栈迁移）→ 降级 WebSearch 官方域片段（A5，T2）。**权威核验移至实现期**：venv 建成后以 `inspect.signature(Portfolio.from_signals)` 本地读数（E1）为准，登记为 U-P015-3。

### 3.2 关键发现

| # | 发现 | 来源 | 对本批的含义 |
|---|------|------|--------------|
| F1 | vectorbt 1.2.0 支持 py3.11-3.14（`requires-python >=3.11,<3.15`），2026-10-19 发布（活跃维护） | A1 | ✅ 可用 |
| F2 | **vectorbt 1.2.0 依赖 `pandas>=3.0.3,<4.0`、`numba>=0.66`、`numpy>=2.4.6`**——与主环境（pandas 2.2.3 / numba 0.65.1）冲突 | A2 | ❌ 主环境直接安装必然破坏本仓依赖 → 必须隔离 venv |
| F3 | backtrader 1.9.78.123：纯 Python、**零外部依赖**、`py2.py3-none-any` wheel → 任何环境可装；但最后发布 2023-04-19（3.5 年停滞），classifiers 仅到 py3.7（元数据滞后） | A3 | ✅ 可用；维护停滞风险已知 |
| F4 | pyqlib 0.9.7 官方安装表 3.8-3.12 全 ✔️（conda 建议）；依赖链重（cython 构建 / lightgbm 等），Windows 非 conda 环境安装失败先例多 | A4 | ⚠️ 工程成本最高 |
| F5 | vectorbt 订单成本默认：`fees=0.0` / `fixed_fees=0.0` / `slippage=0.0`（比例制、无下限、双边对称） | A5（T2）+ A2（T1 佐证结构） | 与 V3 `cost_rate` 模型同构——**残差项最少的对拍对象** |
| F6 | 一致性须先钉默认值；对齐规则后差异可逐美元解释；不一致第一根因是成交模型（信号价 vs 延迟/滑点） | A6 | 对拍方法论与本仓 §4 恒等式纪律同源 |

---

## 4. 框架选择矩阵

| 维度 | **vectorbt 1.2.0** | backtrader 1.9.78.123 | pyqlib 0.9.7 |
|------|--------------------|------------------------|--------------|
| Python 3.12 | ✅（>=3.11,<3.15） | ✅（纯 py 零依赖） | ✅（官方表） |
| 主环境兼容 | ❌ pandas/numba 冲突（F2）→ 隔离 venv | ✅ 零依赖 | ⚠️ 依赖链重（F4） |
| 维护状态 | 活跃（2026-10） | 停滞（2023-04） | 活跃（microsoft） |
| 语义映射 | **V3 同构**（向量化 / close 成交 / 比例费用） | **V2 同构**（事件驱动 / 次 bar 开盘 / 佣金 scheme） | 平台级（TopkDropout / close 成交） |
| 首例残差项 | **最少**：比例费用单参数，无下限/印花税不对称/整手/缓冲 | 多：佣金下限 + 印花税单边 + 整手 + 0.985 缓冲 + 末日强平 | 最多（平台级 + 数据形态转换） |
| 许可 | Apache-2.0 + Commons Clause（内部使用 OK） | GPLv3+（内部使用 OK） | MIT |

---

## 5. 方案矩阵

### 5.1 框架路线

| 方案 | 内容 | 判定 |
|------|------|------|
| **V-A VectorBT ↔ V3 首例** | 先在残差项最少的配对上打通「最小共同任务 → 残差恒等式 → 阴性对照」方法论；Backtrader↔V2、Qlib 登记后续 | **推荐**——符合用户「先一个框架打通」裁决；首例难度最低（§4）；环境冲突有明确解法（隔离 venv） |
| V-B Backtrader ↔ V2 首例 | 首例即对拍生产默认引擎 V2 | 否决——首例残差项五项并存（§4），方法论未立时无法区分「框架差异」与「实现缺陷」，违背 A28 原则 |
| V-C 三库并行 | 本批一次收口三框架 | 否决——工作量与安装风险叠加（F4），且违背用户「先一个框架打通」裁决 |

### 5.2 产物形态

| 方案 | 内容 | 判定 |
|------|------|------|
| **O-A 隔离 venv + 文件交换** | `scripts/external_benchmark/`：独立 venv（vectorbt 1.2.0 自带 pandas 3.x）+ 对拍脚本经 CSV/Parquet 交换数据 + 对拍报告（JSON/MD）落 docs 附录 + 口径映射文档增补实测列 | **推荐**——尊重 F2 冲突事实与 P7 纪律；主环境零污染 |
| O-B 主环境直接安装 | pip install vectorbt 进主环境 | 否决——F2：pandas>=3.0.3 会覆盖主环境 pandas 2.2.3，破坏全仓测试基线 |
| O-C tests/ 常驻 + skip 标记 | 对拍测试进 tests/，无外部依赖时 skip | 否决——违反 P7 纪律（不常驻 CI）；CI 无 numba/pandas3，skip-and-forget 反模式（RULE-3） |

---

## 6. 未决项登记（四元块）

- **U-P015-1 第二例（Backtrader ↔ V2）是否纳入后续批次**
  - 判据：首例方法论闭环（残差恒等式全绿 + 阴性对照通过）的报告产出
  - 触发条件：P-015 首例对拍报告落档之时
  - 当前倾向：本批不做；Backtrader↔V2 的残差项清单（佣金下限 / 印花税单边 / 整手 / 缓冲 / 强平）已在 §4 预登记
  - 证据等级：E3（§4 矩阵）
- **U-P015-2 隔离 venv 数据交换兼容性**（pandas 2.2.3 写 → pandas 3.0.3 读）
  - 判据：venv 内端到端读通本仓导出的对拍数据
  - 触发条件：Step 5 实施首日
  - 当前倾向：CSV 即可；若浮点精度不足再升 Parquet
  - 证据等级：待核（E5→实现期 E1）
- **U-P015-3 vectorbt 权威默认值签名核验**
  - 判据：`inspect.signature(Portfolio.from_signals)` 与 `defaults` 配置读数落档（含 price/fees/slippage/size/init_cash）
  - 触发条件：venv 建成后第一时间
  - 当前倾向：与 A5 片段一致（fees/slippage 默认 0）
  - 证据等级：A5 为 T2 片段（待 E1 升级）

---

## 7. 建议路线（供 Step 3 DESIGN 参考）

1. **最小共同任务分层**（每层残差必须闭合到恒等式）：
   - L0 零费用零滑点 + 常量价：仓位逐日相等，恒等式 `qty_vbt == qty_v3`（rtol=0）
   - L1 + 比例费用（cost_rate = fees）：NAV 差 = `Σ|trade|×price×cost_rate` 的逐日恒等式
   - L2 变动价 + 再平衡频率对齐：引入成交时点语义声明（两者同日 close，理论零差异——若不闭合即为本仓或对方缺陷，进入排查）
2. **通过判据**（区别于「数值一致」）：每一层残差写成**可证伪恒等式** + **阴性对照**（如人为改 cost_rate，恒等式必须随之移动且幅度精确等于声明值）。
3. **产物落点**：`scripts/external_benchmark/`（venv 要求文件 + 驱动脚本）+ 报告 `docs/APPENDIX_p015_external_calibration.md`（或并入 BACKTEST_CALIBER_MAPPING 附录）+ 口径映射文档 §2.2 增补「实测列」。
4. **变更纪律延续**：BACKTEST_CALIBER_MAPPING §5.4——任何影响口径表的改动须同一提交内更新文档 + 脚本。

---

## 8. Step 2 Review（调研文档幻觉抑制）

### 8.1 引用验证表（F4：外部引用 ≥3 条 ⇒ 必须建表）

| 引用 | ID | 验证方式 | 状态 |
|------|----|----------|------|
| vectorbt PyPI 页 | `https://pypi.org/project/vectorbt/` | WebFetch 全页命中（版本号 + Released 日期 + requires-python 三字段齐） | ✅ 已验证（T1 命中） |
| vectorbt pyproject.toml | `raw.githubusercontent.com/polakowo/vectorbt/master/pyproject.toml` | WebFetch 原文命中（dependencies 数组逐行） | ✅ 已验证（T1 命中） |
| backtrader PyPI 页 | `https://pypi.org/project/backtrader/` | WebFetch 全页命中（版本 + 发布日 + wheel 标签） | ✅ 已验证（T1 命中） |
| pyqlib PyPI 页 | `https://pypi.org/project/pyqlib/` | WebFetch 命中但**发布日期区块未渲染**（页尾截断） | ⚠️ 部分验证——版本/安装表已验证，**发布日期未验证**（标注于 A4，不作结论依据） |
| vectorbt 默认费用口径 | `vectorbt.dev/api/portfolio/nb/`（经检索） | WebSearch 官方域片段（T2）；未逐字读原页 | ⚠️ T2——已按 F3 降级链登记，权威核验移交 U-P015-3（E1） |
| A27/A28/A29 | P-011 RESEARCH §11（文献 15-28） | P-011 批内已按当时流程回溯 | ✅ 沿用 P-011 验证结论（转引） |

### 8.2 门禁四项（v1.4）

- [x] (a) FALSIFIED 断言：**无**（本批无先前断言被证伪；P1 的「未实测」状态如实保留）
- [x] (b) CONFLICT / STEP_GAP_OPEN：**无**——U-4 四元块与本批触发一致，无新旧结论冲突
- [x] (c) 阻断性断言双源：关键断言 F2（vectorbt 依赖冲突）**双源**（A1 PyPI requires 区 + A2 pyproject 依赖数组，均 T1）；F5（默认费用）为**单源 T2**——已标 [单源-待二核] 并移交 U-P015-3，不作为 Step 3 方向性依据（方向性依据是「同构性」这一结构性判断，由 A2+P5 双源支撑）
- [x] (d) 假设区：三条假设已全部转未决项四元块（U-P015-1/2/3，§6）

### 8.3 Review 独立性声明

**[RULE-4] 自查（单视角）**：本 Review 由调研作者同一会话完成，无第二视角复核；RULE-5 异构复审按批次惯例留待实施完成后执行（P-013/P-014 先例：收尾时独立会话复审）。

**Step 2 Review 结论：通过**。可进入 Step 3 DESIGN（框架选择按推荐 V-A + O-A，待用户确认）。
