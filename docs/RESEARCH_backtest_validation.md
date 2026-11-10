# P-011 回测准确性验证、学术规范与基准比较 · 调研

> **文档编号**: RESEARCH_backtest_validation
> **阶段**: Phase 1 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 1 完稿；Step 2 Review 通过（§10）；**§11 P0 决策门补充调研完稿（A17-A30 / 文献 15-28，U-1~U-4 + 合并判定均附 7 维矩阵与推荐）**；待 U-1~U-4 与合并判定确认（P0 决策门）
> **上游**: [PROGRESS.md](PROGRESS.md) §1.4 P-011 立项；[ARCHITECTURE.md](ARCHITECTURE.md)；[DIFF_REPORT_2026-10-23.md](DIFF_REPORT_2026-10-23.md)
> **证据时点**: 本仓读数 @ `05af52f`（2026-11-10）；Python 3.12.10 / pytest 9.0.3
> **档位**: T1（后续若实施将触及 `tests/`、`core/`、`scripts/`、CI；本批当前仅 Step 1 调研）

---

## 1. 调研目标

用户提出四问，本批逐条作答并给出可裁决的方案：

| ID | 核心问题 | 期望产出 |
|----|----------|----------|
| **Q-A** | 如何判断当前框架的**回测准确性**？ | 准确性判据分层（组件级 → 引擎级 → 统计级），以及每层的可执行验证手段 |
| **Q-B** | 如何验证**建模、求解、程序编写、数据处理**是正确的、符合**学术规范**？ | 学术可接受性检查清单（偏差、多重检验、样本外、报告口径）与本仓差距 |
| **Q-C** | 当前程序是否具备类似**断点排查**功能，能诊断**模型 / 程序 / 数据 bug**？ | 断点排查能力盘点（日志、事件日志、诊断出口、可复现性），及缺口 |
| **Q-D** | 是否需要 **Qlib / Backtrader / VectorBT** 作为基准比较？如何处理？ | 基准策略分层（内核差分 → 统计容差 → 外部对拍）与口径映射方案 |

**范围边界**：本批只做调研与方案比较，**不改代码、不改测试、不改 CI**；Step 2 Review 后再决定是否进入 DESIGN。

---

## 2. 调研方法

### 2.1 工具与查询

| 工具 | 用途 | 查询/范围 |
|------|------|-----------|
| WebSearch | 外部锚点 | Qlib / Backtrader / VectorBT / LEAN / NautilusTrader 的测试与回归机制；回测过拟合与多重检验；蜕变测试；数据校验 |
| WebFetch | 官方文档直取 | `qlib.readthedocs.io` Data Layer；Qlib PIT 文档 RST 源 |
| Grep / Glob / Read | 本仓事实 | `core/`、`tests/`、`tools/`、`scripts/`、`docs/` 逐点读码（E3） |
| pytest / Get-ChildItem / Select-String | 机械计数 | 测试文件数、用例数、数值断言数、日志调用数、外部框架引用数（E1） |

### 2.2 证据分级（沿用 PROGRESS 口径）

- **E1** 可重放命令（`git` / `pytest` / `Grep` 计数 / `Select-String`）
- **E2** 运行时脚本取证（本批未新增探针；引用历史 `[RUN]` 读数时标注来源）
- **E3** 静态读码（**强制绑定 `@05af52f`**）
- **E4** 盲区扫描 / 判断陈述（声明扫描范围，零发现也须报范围）
- **E5** 推测——**不用于任何结论**

### 2.3 调研范围

- 时间：2014-2026（PBO/DSR 2014 起，Qlib/LEAN 现行文档截至 2026-11）
- 领域：量化回测工程、软件测试（oracle problem / 蜕变测试 / 差分测试）、实证资产定价规范、数据校验
- 排除：实盘交易执行、券商对接、高频撮合微观结构

---

## 3. 外部锚点

### 3.1 回测框架的验证与回归实践

#### A1 Qlib · Point-in-Time 数据库（T1，官方文档）

- **来源**: Qlib 官方文档 `advanced/PIT.rst`（`qlib.readthedocs.io/en/latest/_sources/advanced/PIT.rst.txt`）
- **验证状态**: ✅ 已直取原文
- **原文要点**:
  - 「If we only use the latest version for historical backtesting, data leakage will happen.」
  - 「Point-in-time database is designed for solving this problem to make sure user get the right version of data at any historical timestamp. It will keep the performance of online trading and historical backtesting the same.」
- **对本批的相关性**: 数据正确性的最高标准是 **PIT 版本化**；本仓数据层用当期 pkl 快照，无版本轴（P14）。这决定了「数据 bug」诊断的上限。

#### A2 Qlib · Data Layer 复权口径（T1，官方文档）

- **来源**: `qlib.readthedocs.io/en/stable/component/data.html`
- **验证状态**: ✅ 已直取原文
- **原文要点**: 「Qlib normalize the price on first trading day of each stock to 1 when adjusting them.」
- **相关性**: 复权口径必须在跨框架对拍前**显式对齐**；本仓有 `adj_factor` 恒等式测试（P2），但口径与 Qlib 不同（本仓 forward/backward，Qlib 首日归一）。

#### A3 Qlib · CI 与测试（T1/T2）

- **来源**: Qlib 官方 `code_standard_and_dev_guide`（T1）+ DeepWiki `11-development-and-cicd`（T2 二手）
- **验证状态**: ✅ 官方页面原文（flake8 + GitHub Actions 多 OS/Python）；⚠️ 二手页面的具体矩阵数字未逐项核验
- **原文要点**: flake8 代码风格检查；CI 在多个操作系统与 Python 版本上运行 `tests/`
- **相关性**: 「有测试」不等于「有回测准确性回归」；Qlib 的 CI 主要是单元/集成测试，**未见公开的逐回测 golden 统计对比**（这是 Qlib 与 LEAN 的分野）。

#### A4 Backtrader · Testing Guide（T1，官方文档）

- **来源**: `backtrader.readthedocs.io/en/latest/developer-guide/testing.html`
- **验证状态**: ✅ 已检索到官方原文片段
- **原文要点**: 使用 `pytest` + `pytest-cov` + `pytest-xdist`；单元测试应「Use mock data (no external...)」
- **相关性**: 与 LEAN 的「回测级回归」不同，Backtrader 采**组件级 pytest + mock 数据**路线；说明「框架基准」本身没有统一标准，需自建。

#### A5 VectorBT · Contributing / Repository internals（T1，官方文档）

- **来源**: `vectorbt.dev/getting-started/contributing/`（T1）+ `vectorbt.pro/documentation/internals/`（T1）
- **验证状态**: ✅ 官方文档
- **原文要点**: Python 侧 `pytest` 全量；Rust 侧 `cargo test`；`tests/` 按子包组织，`benchmarks/` 存放基准报告与缓存
- **相关性**: VectorBT 的 `benchmarks/` 是**性能**基准而非正确性基准；其正确性依赖单元测试与 pandas 对照（官方 Features 页示例：`assert_frame_equal(pandas_zscore(), vectorbt_zscore())`）——这正是**参考实现差分测试**的形态。

#### A6 LEAN · Regression Testing（T2，DeepWiki 二手；官方仓库结构佐证）

- **来源**: DeepWiki `QuantConnect/Lean 9.3/10.3-regression-testing`
- **验证状态**: ⚠️ 二手（未直取 LEAN 源码）；关键机制与开源仓库 `Tests/` 目录结构一致
- **原文要点**: 「It executes algorithms with predefined parameters and compares the results against expected values」；组件含 **Test Runner**、**Statistics Comparator**、`IRegressionAlgorithmDefinition`（ExpectedStatistics / DataPoints / AlgorithmHistoryDataPoints / AlgorithmStatus）；CI 有专门的 140+ 资源密集型回归算法 workflow
- **相关性**: 这是**回测级 golden 回归**的工业样板：每个算法一份「期望统计字典 + 容差」，任何引擎改动导致统计漂移即失败。本仓完全没有该层（P15）。

#### A7 NautilusTrader · Research-to-live parity（T1/T2，官方博客）

- **来源**: `nautilustrader.io/blog/why-nautilustrader-exists/`
- **验证状态**: ✅ 官方博客原文
- **原文要点**: 「The `NautilusKernel` is core to both `BacktestEngine` and `LiveNode`, sharing common machinery for messaging, data handling, risk, execution, portfolio state, and caching」
- **相关性**: 准确性的终极判据是**回测-实盘同构**；本仓 V2/V3 双引擎、V3 无执行策略（P4），不具备该性质。可作为长期方向而非本批目标。

### 3.2 学术规范：回测可信性

#### A8 Arnott, Harvey & Markowitz (2019) · A Backtesting Protocol in the Era of Machine Learning（T1，期刊）

- **来源**: *The Journal of Financial Data Science*, 2019；Duke Scholars 与 Cambridge Associates 摘要佐证
- **验证状态**: ✅ 期刊元数据与摘要核实；⚠️ 22 问全文未逐条直取（付费墙）
- **原文要点**: 提出 **7 个部分、22 个问题**的回测研究协议，用于限制 false discoveries、识别真实策略
- **相关性**: 这是 Q-B 的**主协议骨架**：数据（PIT、幸存者偏差）、假设、多重检验、样本外、报告口径均可映射为检查项。

#### A9 Bailey, Borwein, López de Prado & Zhu · The Probability of Backtest Overfitting（T1）

- **来源**: *Journal of Computational Finance*（2017）；eScholarship 全文 PDF
- **验证状态**: ✅ 全文 PDF 直取
- **原文要点**: 提出 **PBO** 框架与 **CSCV**（combinatorially symmetric cross-validation）实现；指出 hold-out 在回测语境下不可靠
- **相关性**: Q-B 需要「试验次数」与「选择偏差」的量化；PBO/ CSCV 是可选实现（成本中高）。

#### A10 Bailey & López de Prado (2014) · The Deflated Sharpe Ratio（T1）

- **来源**: *Journal of Portfolio Management* 40(5)
- **验证状态**: ✅ 摘要与定义多处交叉核实
- **原文要点**: DSR 校正两类绩效膨胀——**多重检验下的选择偏差**与**非正态收益**
- **相关性**: 本仓 `sharpe_ratio` 是未校正点估计（P9）；DSR 可作为报告层的低成本增强。

#### A11 Harvey, Liu & Zhu (2016) · …and the Cross-Section of Expected Returns（T1，RFS）

- **来源**: *Review of Financial Studies* 29(1), 5-68（Oxford Academic 摘要）
- **验证状态**: ✅ 摘要原文
- **原文要点**: 目录化 **316 个**已发表预测变量；新因子应通过 **t > 3.0** 的更高门槛（而非传统 2.0）
- **相关性**: 因子筛选类回测（本仓 V3 的定位）若声明「显著」，必须记录试验次数并抬高门槛；否则属学术不规范。

#### A12 Chen & Zimmermann · Open Source Asset Pricing（T1）

- **来源**: *Critical Finance Review* 27(2), 207-264（2022）；`openassetpricing.com`
- **验证状态**: ✅ 期刊信息与官网数据说明
- **原文要点**: 对 180 个在原文中明确显著的预测变量，**98%** 的复现得到 t > 1.96；开放数据与代码
- **相关性**: 「可复现性」是可被第三方验证的硬指标；为本仓「数据 + 代码 + 种子」三件套提供外部依据。

#### A13 Chen, Cheung & Yiu (2018) · Metamorphic Testing: A Review（T1，ACM CSUR）

- **来源**: *ACM Computing Surveys* 51(1), Article 4；DOI `10.1145/3143561`
- **验证状态**: ✅ DOI 与摘要页
- **原文要点**: MT 通过**蜕变关系（MR）**缓解 oracle problem；MR 的系统化识别与选择仍是挑战
- **相关性**: 回测引擎没有「正确答案」可作 oracle，MT 是最贴合的理论工具（Q-A 的核心方法之一）。

### 3.3 数据与可复现性工程

#### A14 pandera · Statistical Data Validation（T1，官方文档 + SciPy 2019 论文）

- **来源**: `pandera.readthedocs.io`；SciPy 2019 论文《pandera: Statistical Data Validation of Pandas Dataframes》
- **验证状态**: ✅ 官方文档与论文摘要
- **原文要点**: 用 schema 在**运行时**校验 dataframe 的 dtype、范围、唯一性、统计假设；校验失败抛 `SchemaError`
- **相关性**: 数据 bug 的第一道闸门；本仓当前只有 `FileNotFoundError` 与列/索引对齐，无值域与分布校验（P14）。

#### A15 可复现研究三条件（T3，行业博客，降级）

- **来源**: Swoopr《Reproducible Trading Research》
- **验证状态**: ⚠️ T3 二手；与 A12 的官方实践方向一致，仅作辅助
- **原文要点**: ①代码版本化并记录 commit；②数据记录来源、下载日期与 checksum；③随机过程使用固定种子
- **相关性**: 本仓已有 commit 纪律与固定 seed（P18），缺数据 checksum 与 run manifest。

#### A16 确定性 replay（T3，arXiv 二手，未精确验证）

- **来源**: arXiv `2606.27570`（审计 AI 投资建议）、`2602.00133`（Prediction MarketBench）
- **验证状态**: ⚠️ 未精确验证（搜索摘要级）
- **原文要点**: 「a replay test feeds the same input tuple twice and checks that orders, exclusions, and ranked candidates are byte-identical」；事件驱动引擎的确定性回放需要事件哈希与不变量检查
- **相关性**: Q-C 的「断点排查」理想形态；本仓 `EventLog` 已有 append-only 基础（P12），但回测主循环未接入。

---

## 4. 本仓事实

> 全部事实绑定 `@05af52f`；E1 = 机械计数，E3 = 读码，E4 = 扫描。

| ID | 事实 | 证据 |
|----|------|------|
| **P1** | 测试规模：**51** 个测试文件、**516** 个用例；数值断言（`assertAlmostEqual` / `pytest.approx` / `abs(...) < 1e-*`）**101 处**，分布在 **18** 个文件 | E1：`Get-ChildItem tests -Filter 'test_*.py'`；`pytest --collect-only -q` → `516 tests collected`；`Grep` 计数 |
| **P2** | 已有 **18 项严格验证**（`test_real_ashare_strict_validation.py`）：OHLC 一致性、跨文件日期/列对齐、复权恒等式、收益率定义与首日 NaN、zscore 截面均值/标准差、winsorize 效果、形状与 NaN 不变、组合价值对账、信号→持仓映射、持仓跟踪一致性、逐笔成本、总成本、净额、总收益、最大回撤 | E3 @`05af52f`（`test_01`~`test_18`） |
| **P3** | `test_08_no_future_info_leakage` **名不副实**：只断言「原始有值 → 处理后不为 NaN」，**不检查时间轴方向**（无 t 与 t+k 的统计量比较），无法发现 look-ahead | E3 `test_real_ashare_strict_validation.py:248-264` |
| **P4** | **V2 与 V3 成交假设不同**：V2 通过 pending queue 在**次日开盘**成交（`_process_pending_orders` 用 open 价）；V3 `_rebalance_kernel` 用**当日 close** 定价并成交，且用当日信号 | E3 `engine_v2.py:416-495`、`engine_v3_vector.py:77-152` |
| **P5** | `test_v3_engine_integration.py` 文件头声称「V3 引擎与 V1/V2 结果可比性」，但 **4 个 test 函数中 0 个做跨引擎数值对比**（只有独立运行与结构断言） | E1：`Grep '^def test_'` = 4；E3 通读 |
| **P6** | 确定性已有覆盖：`test_engine_v3.py::test_results_consistency` 对同输入两次运行断言 `total_return`/`sharpe_ratio` 10 位小数一致 | E3 `test_engine_v3.py:154-166` |
| **P7** | 历史上有一次**一次性**跨引擎受控对比：R-1（关闭因子处理后 V1/V2 逐日净值完全一致，最大绝对差异 **0.000000**），但**未固化为测试** | E2/历史：`docs/DIFF_REPORT_2026-10-23.md:36` |
| **P8** | `BacktestConfig.benchmark` 仅「暂留接口」（`str | None = None`），全仓无基准指数数据、无相对收益 / Alpha / Beta / 信息比率 | E3 `config.py:371`；E4 扫描 `core/`（无 `benchmark_return` 计算） |
| **P9** | **Sharpe 双口径**：`analytics` 用 rf=**3%** 硬编码、`(annual_return - rf)/annual_vol`；V3 `_metrics_kernel` 用 **rf=0**、`annual_return/vol`。两处不可直接比较 | E3 `analytics.py:88-92`、`engine_v3_vector.py:170-174` |
| **P10** | 无多重检验校正：全仓无 PSR / DSR / PBO / 试验次数记录 | E4 扫描范围 `core/`+`agents/`+`tools/`（`Grep 'deflat|PBO|multiple.test|trials'` 0 命中） |
| **P11** | 样本外框架存在：`walk_forward.py` 支持 rolling/expanding 窗口 + **Purge Gap**（文件头引用 López de Prado《Advances in Financial Machine Learning》），`test_walk_forward.py` 覆盖 | E3 `walk_forward.py:1-14`、`:37-60` |
| **P12** | 断点排查现状（正向）：**176 处** `logger.*`（15 个文件）；`EventLog` 为 append-only JSONL + 内存 ring buffer（双写、seq 恢复）；pending queue 有事件日志 CSV；四个诊断出口：`unclosed_positions`、`get_execution_stats()`、`get_mask_summary()`、`get_data_info()` | E1 `Grep logger` 计数；E3 `event_log.py:1-80`、`engine_v2.py` 各出口 |
| **P13** | 断点排查缺口：全仓**无** `pdb` / `breakpoint()` / `--debug` 开关；**无逐日中间态 dump**（快照只落最终 CSV）；`EventLog` 未被回测主循环写入（仅作为通用组件存在） | E4 扫描 `core/`、`tests/`、`scripts/`、`tools/`（`Grep 'breakpoint\\(|import pdb'` 0 命中）；E3 `engine_v2.py` 无 `event_log` 引用 |
| **P14** | 数据层：pkl 读盘（`pd.read_pickle`）+ 列/索引对齐（`_load_and_align_data`）；**无 schema/值域校验、无数据 checksum、无 PIT 版本轴**；停牌/ST 缺失按 `0=正常` 默认（P-010） | E3 `data.py:120-167`、`:288-301` |
| **P15** | **无 golden / 回归期望文件**：仓库内无 `*golden*` / `*baseline*` / `*expected*` 数据文件（唯一命中是 `docs/dev-log/DEV-LOG-001-...` 文件名）；无「期望统计字典 + 容差」机制 | E4 扫描全仓（`Get-ChildItem -Recurse -Include '*golden*','*baseline*','*expected*'`） |
| **P16** | **无外部回测框架依赖**：全仓无 `import qlib` / `backtrader` / `vectorbt`（`vectorbt` 仅出现在测试名「vbt 风格信号」与注释） | E1 `Grep 'qlib|backtrader|vectorbt'` 13 文件，逐个确认为注释/配置/无关词 |
| **P17** | `tools/benchmark.py` 仅**性能**基准（计时不同引擎），不是准确性基准 | E3 `tools/benchmark.py:1-80` |
| **P18** | 测试数据：本地 `data/test_ashare`（2024-01-02 ~ 2024-06-04）；CI 用 `scripts/prepare_test_fixture.py` 生成合成夹具；合成数据全部固定 `seed`（如 42） | E1/E3 `tests/*` 的 `np.random.seed`；`scripts/prepare_test_fixture.py` |

---

## 5. 现状诊断（逐问作答）

### 5.1 Q-A 回测准确性如何判断

准确性不是一个布尔值，而是**四层判据**。本仓逐层成熟度：

| 层 | 判据 | 本仓现状 | 成熟度 |
|----|------|----------|--------|
| **L1 组件级** | 每个模块对已知输入给出解析解/闭式解 | Brinson 归因（小样本逐项解析）、成本公式、复权恒等式、zscore 统计量 | **强**（P2） |
| **L2 引擎级（内部一致性）** | 不变量恒成立：`cash + Σmarket_value = total_value`；持仓 = 成交累计；订单状态机可审计 | 组合价值对账、持仓跟踪、信号→持仓映射、逐笔成本对账、`unclosed_positions` | **强**（P2/P12） |
| **L3 引擎级（跨实现一致性）** | 同一策略、同一数据、同一成交假设下，两套实现结果一致（差分测试） | 仅一次历史 R-1 对比未固化；V3 与 V2 成交假设不同（P4/P5/P7） | **弱** |
| **L4 统计级（结果可信性）** | 样本外、多重检验、基准比较、报告口径统一 | walk-forward + purge 有；基准、DSR/PBO、口径统一缺（P8/P9/P10） | **弱-中** |

**结论（Q-A）**：当前框架的「准确性」在 L1/L2 有实质保障，**L3 缺失**，L4 只有一半。判断准确性的最小可行闭环应为：

1. **不变量对账**（已有，固化为每引擎必跑）；
2. **参考实现差分**（新）：V3 的 `_rebalance_kernel` vs 纯 Python 逐股循环参考实现；numba 路径 vs `_NUMBA_AVAILABLE=False` 回退路径；
3. **跨引擎差分**（新）：在「关闭 V2 的 T+1/费用/风控，使其与 V3 假设等价」的受控配置下，逐日净值对齐（容差 0）；
4. **统计级回归**（新）：LEAN 式期望统计 + 容差。

### 5.2 Q-B 建模/求解/程序/数据是否正确、是否学术规范

按 A8 的 22 问协议映射到本仓：

| 维度 | 检查项 | 本仓现状 | 证据 |
|------|--------|----------|------|
| 数据 | PIT / 版本 | **缺** | P14；A1 |
| 数据 | 幸存者偏差 | **未知**：股票池由 pkl 快照决定，无退市股信息（*Step 2 Review F-R4 注：P-012 U-1 已裁决为「默认按有退市数据实现动态池校正」，见 [RESEARCH_bias_interface.md](RESEARCH_bias_interface.md) §11.1；本表保留 Step 1 时点原貌*） | P14 |
| 数据 | 复权口径 | 有恒等式，无跨源校验 | P2 |
| 程序 | look-ahead | 弱：`test_08` 不检查时间方向；V3 当日 close 成交（定位为筛选器） | P3/P4 |
| 程序 | 未来函数（信号→成交时序） | V2 正确（T+1）；V3 明确不支持 | P4 |
| 求解 | 优化器约束/可行性 | 有 `max_weight`/`round_lot` 等断言；无「约束违反率」统计 | P2 |
| 统计 | 多重检验 | **缺**（无试验次数、无 DSR/PBO） | P10；A9/A10/A11 |
| 统计 | 样本外 | walk-forward + purge 有，但无「样本外绩效衰减」报告 | P11 |
| 报告 | Sharpe/回撤口径 | **双口径不一致**、rf 硬编码、无置信区间 | P9 |
| 可复现 | 代码/数据/种子 | 代码有 commit；种子固定；数据无 checksum、无 run manifest | P18；A15 |

**结论（Q-B）**：程序层面「算得对」的证据较强；**学术规范层面缺口集中在数据偏差（PIT/幸存者）、多重检验、报告口径三处**。这三处不需要重写引擎，属于「验证与报告层」增补。

### 5.3 Q-C 是否具备断点排查能力

| 能力 | 现状 | 判定 |
|------|------|------|
| 运行日志 | 176 处 logger，覆盖引擎/数据/执行/风控；有 INFO/WARNING/ERROR 分级 | ✅ 可用 |
| 事件溯源 | `EventLog` 双写 JSONL + ring buffer，seq 可恢复；pending 订单有事件 CSV | ✅ 组件级可用，**但未接入回测主循环** |
| 状态诊断 | 4 个出口（未平仓残留、执行统计、掩码摘要、数据摘要）+ 快照 CSV + 交易 CSV | ✅ 事后可查 |
| 逐日 trace | 无。定位「第 N 天某只股票为何没成交」需要重跑 + 加日志 | ❌ 缺 |
| 交互式断点 | 无 `pdb`/`breakpoint`/调试开关；可行但需改代码 | ❌ 缺（低优先） |
| 数据 bug 诊断 | 无 schema/值域/分布校验；异常数据靠下游 `KeyError`/NaN 断言暴露 | ❌ 缺 |
| 模型 bug 诊断 | 无「信号-订单-成交-持仓」全链路 trace id | ❌ 缺 |
| 确定性复现 | V3 有同输入两次一致性测试；V2 无；无 run manifest（commit+数据哈希+配置） | ⚠️ 部分 |

**结论（Q-C）**：当前具备**事后诊断**（日志 + 4 出口 + CSV + EventLog 组件），不具备**过程诊断**（逐日 trace、断点、数据契约）。用一句话概括：**能回答「结果是什么、哪里异常」，不能回答「第几天、哪笔单、哪条数据导致了异常」**。

### 5.4 Q-D 与 Qlib / Backtrader / VectorBT 基准比较

先给出「不能直接比」的原因（这是本调研最重要的判断）：

| 差异项 | 本仓 V2 | 本仓 V3 | Qlib | Backtrader | VectorBT |
|--------|---------|---------|------|------------|----------|
| 成交时点 | 次日开盘（T+1） | **当日收盘** | 可配置（通常次日/收盘） | 可配置（默认 next bar open） | 默认次 bar open，可配置 |
| 复权 | forward/backward pkl | 同左 | 首日归一化 | 数据原样 | 数据原样 |
| 费用 | 佣金+印花税+滑点 | 单一 `cost_rate` | 可配置 | 可配置 | 可配置 |
| 股票池/停牌 | UniverseFilter | 无（定位为筛选器） | PIT + 表达式引擎 | 无内置 | 无内置 |
| 输出 | 快照+交易+报告 | 组合价值+指标 | 信号+组合分析 | 经纪商模拟 | 组合对象 |

**因此，「用 Qlib 跑同一策略比净值」在默认配置下必然不等**，差异来自成交时点、复权、费用、股票池四个口径，而不是「谁更准」。可行的基准比较只能分三层：

| 层 | 做法 | 比对对象 | 容差 | 成本 |
|----|------|----------|------|------|
| **B1 内核级** | 同一份价格矩阵 + 同一份信号 + 相同的「次日开盘、等权、单边费率」假设，跑 V2 / V3 / 外部框架，只比**单日组合价值递推** | 全部框架的「执行内核」 | 1e-8（浮点） | 低-中 |
| **B2 统计级** | 同一策略、同一数据，比**总收益/波动/最大回撤/换手**，并出具**差异归因表** | Qlib/Backtrader/VectorBT | 分项容差（如总收益 ±0.5pp） | 中 |
| **B3 口径文档级** | 不跑数值，只映射口径（成交时点、复权、费用、停牌），写入 `docs/` | 文档 | — | 低 |

**结论（Q-D）**：需要基准，但**不是「接入 Qlib 当标准答案」**，而是「**B1 内核差分 + B3 口径映射**为主，B2 作为一次性校准」。此外，本仓内部已有两个天然基准（V2 vs V3、numba vs 纯 Python），成本远低于引入外部框架，应优先做。

---

## 6. 方案候选与比较矩阵

> 按 `DECISION_MATRIX_TEMPLATE.md` 七维；每方案至少 2 个外部锚点覆盖 ≥3 维。

### 6.1 Q1：准确性验证体系

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级潜力 | 短期 | 长期 |
|------|------|------|------|------|------|----------|------|------|
| **V-A 内部对账 + 差分**（推荐） | 固化不变量对账；新增 V3 内核 vs 纯 Python 参考实现、numba vs 回退、V2 受控配置 vs V3 三层差分 | 低-中 | 高（覆盖 L2/L3） | 低 | 无依赖 | 高 | 2-3 天 | 持续有效 |
| V-B Golden 回归（LEAN 式） | 为 3-5 个代表策略生成期望统计 JSON + 容差，CI 比对 | 中 | 高（防回归） | 中（数据/环境漂移需维护） | 无依赖 | 高 | 3-5 天 | 需定期刷新 baseline |
| V-C 外部框架对拍 | 引入 Qlib/Backtrader/VectorBT 跑同策略比净值 | 高 | 中（受口径差异干扰） | 高（多依赖、多版本） | 引入重依赖 | 中 | 1-2 周 | 高维护 |
| V-D 维持现状 | 只用现有 101 处数值断言 | 0 | 低（L3/L4 空白） | 低 | — | 低 | 0 | 风险累积 |

**推荐**：**V-A 为主 + V-B 为辅**；V-C 仅在需要对外声明「与某框架一致」时做一次性 B1/B2 校准（锚点 A4/A5/A6 均表明各框架自身也没有统一标准）。

### 6.2 Q2：学术规范

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级潜力 | 短期 | 长期 |
|------|------|------|------|------|------|----------|------|------|
| **S-A 报告口径统一 + 偏差声明**（推荐） | 统一 Sharpe/回撤/年化口径（rf 可配置）；报告增加「样本内外对比、试验次数、偏差声明」字段 | 低 | 高（合规底线） | 低 | 高 | 中 | 1-2 天 | 长期 |
| S-B 多重检验工具 | 增加 DSR / PBO(CSCV) 计算模块与报告字段 | 中 | 中-高 | 中 | 高 | 高 | 3-5 天 | 长期 |
| S-C 完整 22 问协议清单化 | 把 A8 的 22 问做成 `docs/` 检查表并逐项签字 | 低 | 中（形式合规） | 低 | 高 | 中 | 1 天 | 需人工维护 |
| S-D 维持现状 | — | 0 | 低（Sharpe 双口径、无多重检验） | — | — | — | 0 | 学术声明不可用 |

**推荐**：**S-A + S-C 立即可做，S-B 视是否对外发布因子结论而定**。

### 6.3 Q3：断点排查

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级潜力 | 短期 | 长期 |
|------|------|------|------|------|------|----------|------|------|
| **D-A 数据契约（轻量 schema）**（推荐） | 在 `DataManager` 加载后做 dtype/索引/值域/NaN 比例断言，失败即 fail-fast | 低 | 高（数据 bug 前置） | 低 | 高 | 高 | 1-2 天 | 长期 |
| **D-B 逐日 trace + run manifest**（推荐） | 回测接入 `EventLog`，记录 signal→order→fill→position 四类事件与 `run_id`；输出 manifest（commit/数据哈希/配置/seed） | 中 | 高（过程诊断） | 中 | 高 | 高 | 3-5 天 | 长期 |
| D-C 交互式调试开关 | `--debug` / 环境变量开启 `pdb`/单日断点 | 低 | 低-中（开发者自用） | 低 | 高 | 低 | 0.5 天 | 低 |
| D-D 维持现状 | 日志 + 4 出口 | 0 | 中（事后可查） | — | — | — | 0 | 缺口累积 |

**推荐**：**D-A + D-B**；D-C 可选。

### 6.4 Q4：外部框架基准

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级潜力 | 短期 | 长期 |
|------|------|------|------|------|------|----------|------|------|
| **X-A 口径映射文档 + 内核差分**（推荐） | 先写口径映射表（B3），再做 B1 内核级对拍（V3 vs 纯 Python 参考实现；必要时 Qlib 单因子） | 低-中 | 高 | 低 | 高 | 高 | 2-4 天 | 长期 |
| X-B 全面对拍 B2 | 同一策略在 Qlib/Backtrader/VectorBT 重跑，统计级比对 + 归因 | 高 | 中（受口径噪声影响） | 高 | 中 | 中 | 1-2 周 | 高维护 |
| X-C 仅文档对标 | 只写「我们不比」的口径说明 | 低 | 低 | 低 | 高 | 低 | 0.5 天 | 低 |
| X-D 引入某框架替换自研 | 迁移到 Qlib | 极高 | 不确定 | 高 | 低 | 中 | 数月 | 高 |

**推荐**：**X-A**；X-B 仅在对外需要「第三方一致性」声明时执行一次。

---

## 7. 建议路线（供 DESIGN 参考，不在本批实施）

| 阶段 | 内容 | 对应方案 | 依赖 |
|------|------|----------|------|
| **L0 立即（1-2 天）** | 口径映射表 + 报告口径统一（rf 可配置、双引擎 Sharpe 对齐）+ 22 问偏差声明 | X-A(文档) / S-A / S-C | 无 |
| **L1 短期（3-5 天）** | 数据契约断言 + V3 内核参考实现差分 + V2 受控 vs V3 差分 | D-A / V-A | L0 |
| **L2 中期（按需）** | Golden 回归 3-5 策略 + DSR 报告字段 + 逐日 trace / run manifest | V-B / S-B / D-B | L1 |
| **L3 可选** | B2 外部框架统计级对拍（一次性校准，不常驻 CI） | X-B | L1 |

**不建议**：把 Qlib/Backtrader/VectorBT 作为常驻 CI 依赖；三者的默认成交/复权/费用口径与本仓不同，会制造大量「假阳性差异」。

---

## 8. 未决项登记（四元块）

> **状态（2026-11-10）**：U-1~U-4 已完成补充调研（**§11**，锚点 A17-A30，各附 7 维矩阵与推荐）；本节保留 Step 1 时点原貌。推荐结论：U-1=V-A（L1/L2 先行）、U-2=S-A+S-C 首批/S-B 挂起、U-3=D-A+D-B、U-4=X-A；合并判定=独立两个 DESIGN、P-012 先行（§11.5）。

- **U-1 准确性验证的优先范围**
  - **判据**：用户明确「先做 L1 内部差分，还是直接上 L4 统计级/Golden」
  - **触发条件**：进入 Step 3 DESIGN 前必须裁决
  - **当前倾向**：L1（V-A）优先，L2（V-B）随后
  - **证据等级**：E1（P1-P7）

- **U-2 学术规范深度**
  - **判据**：是否需要在对外报告中声明 DSR/PBO；若不需要，S-B 可不出现在首批
  - **触发条件**：出现「对外发布因子/策略结论」需求时重审
  - **当前倾向**：先做 S-A（口径统一）+ S-C（偏差声明），S-B 挂起
  - **证据等级**：E3（P9/P10）+ A8-A11

- **U-3 断点排查的形态**
  - **判据**：过程诊断是「逐日 trace + run manifest」还是「交互式调试」；前者可入 CI，后者只服务开发
  - **触发条件**：出现一次「无法用现有日志定位的回测异常」时升级
  - **当前倾向**：D-A + D-B（trace），D-C 可选
  - **证据等级**：E3/E4（P12/P13）

- **U-4 外部框架对拍的范围**
  - **判据**：是否需要「与 Qlib 一致」的对外声明；若仅内部校准，X-A 足够
  - **触发条件**：用户/评审要求第三方框架对照时
  - **当前倾向**：X-A（口径映射 + 内核差分），X-B 一次性
  - **证据等级**：E3（P4/P16）+ A1-A7

---

## 9. 参考文献

1. Arnott, R., Harvey, C. R., & Markowitz, H. (2019). *A Backtesting Protocol in the Era of Machine Learning*. The Journal of Financial Data Science.
2. Bailey, D. H., Borwein, J., López de Prado, M., & Zhu, Q. J. (2017). *The Probability of Backtest Overfitting*. Journal of Computational Finance. eScholarship: `qt4w1110bb`.
3. Bailey, D. H., & López de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality*. Journal of Portfolio Management, 40(5).
4. Chen, A. Y., & Zimmermann, T. (2022). *Open Source Cross-Sectional Asset Pricing*. Critical Finance Review, 27(2), 207-264. `openassetpricing.com`.
5. Chen, T. Y., Cheung, S. C., & Yiu, S. M. (2018). *Metamorphic Testing: A Review of Challenges and Opportunities*. ACM Computing Surveys, 51(1), Article 4. DOI `10.1145/3143561`.
6. Harvey, C. R., Liu, Y., & Zhu, H. (2016). *…and the Cross-Section of Expected Returns*. Review of Financial Studies, 29(1), 5-68.
7. Microsoft Qlib. *Data Layer: Data Framework & Usage*；*Point-in-Time Database*（`advanced/PIT.rst`）；*Code Standard*.
8. Backtrader. *Testing Guide*（`backtrader.readthedocs.io/en/latest/developer-guide/testing.html`）。
9. VectorBT. *Contributing*；*Repository internals*。
10. QuantConnect LEAN. *Regression Testing*（DeepWiki 9.3/10.3；T2 二手）。
11. NautilusTrader. *Why NautilusTrader Exists*（research-to-live parity）。
12. pandera. *Statistical Data Validation of Pandas Dataframes*（SciPy 2019）；官方文档。
13. Swoopr. *Reproducible Trading Research*（T3，辅助）。
14. arXiv `2606.27570` / `2602.00133`（确定性 replay，T3 未精确验证）。

---

## 10. Step 2 Review（独立 pass，2026-11-10）

- **执行时点**: Step 1 正文完稿、P-012 §12 补充调研与 ADR-017 登记之后单独执行；与正文写入不同会话、不同模型基座（RULE-1 / RULE-4 / RULE-5 异构复审口径）
- **审查方式**: E1 复核 + E3 抽检 + 计数矩阵 + 与 P-012 结论交叉核对，不依赖正文自报

**E1 复核**:

| 断言 | 命令 | 结果 |
|------|------|------|
| 证据 commit 有效性 | `git diff --stat 05af52f 2c34283 -- core filter tests` | 零 diff，E3 引用绑 `@05af52f` 仍有效 |
| 测试文件数（P1） | `Glob tests/test_*.py` | **51** 个文件 ✅ |
| 516 用例（P1） | P-007 层 B GREEN（2026-11-10，E1） | `516 passed` 旁证，未重跑 collect |
| 断点排查缺口（P13） | `Grep 'breakpoint\(|import pdb'`（core/） | **0 命中** ✅ |

**E3 抽检（5 处全部命中）**:

| 断言 | 位置 | 结果 |
|------|------|------|
| Sharpe rf=3% 硬编码（P9） | `analytics.py:88-92`（L89 `risk_free_rate = 0.03`） | ✅ |
| V3 Sharpe rf=0（P9） | `engine_v3_vector.py:170-174`（L174 `annual_return / volatility`） | ✅ |
| benchmark 暂留接口（P8） | `config.py:371`（`benchmark: str \| None = None  # 基准指数（暂留接口）`） | ✅ |
| `test_08` 只查 NaN 形状（P3） | `test_real_ashare_strict_validation.py::test_08_no_future_info_leakage`（断言 `raw_has_value & proc_is_nan == 0`，无时间方向检查） | ✅ |
| V3 当日 close 成交（P4） | `engine_v3_vector.py` `_rebalance_kernel` 语义 | ✅ |

**计数矩阵**: 外部锚点 A1-A16 = **16** ✅（§3 逐条标题核对）；本仓事实 P1-P18 = **18** ✅；参考文献 1-14 = **14**，连续无缺号 ✅。

**与 P-012 交叉核对**: 本文档 P3（look-ahead 弱）、P14（无 PIT/checksum）与 [RESEARCH_bias_interface.md](RESEARCH_bias_interface.md) B-2/P14 口径一致；本文档 P4（V2 次日开盘 vs V3 当日 close 不可比）与 §3.14 硬约束⑤一致；本文档「幸存者偏差未知」（§5.2）已被 P-012 U-1 裁决升级为「具备校正能力（默认路径）」——**不构成本文档缺陷**（两批发布时序所致，DESIGN 阶段以 P-012 §11.1 为准）。

**发现（1 项 P3 已回写 + 1 项误报核销）**:

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| **F-R4** | P3 | §5.2 表「幸存者偏差 = 未知」未标注与 P-012 U-1 裁决的联动，读者可能据旧结论设计 | 行尾补注「P-012 U-1 已裁决为默认路径校正（§11.1），本表保留 Step 1 时点原貌」 |
| **F-R5** | — | 初判「A16 锚点等级与文献 14 标注不一致」 | **误报核销**：读回 §3 A16（已标 T3 未精确验证）与文献 14（T3 未精确验证）完全一致，无缺陷 |

**结论**: **P1 = 0；P2 = 0；P3 = 1（F-R4，已回写）+ F-R5 误报核销**；E1/E3 复核全命中，计数连续。**P-011 Step 2 Review 通过**；下一步为 U-1~U-4 裁决（P0 决策门剩余）。

---

## 11. P0 决策门补充调研（2026-11-10，Step 2 Review 后）

> 本节针对 P0 决策门剩余项做补充调研：**U-1~U-4 + 合并判定**（合并判定为 §3.14 ⑤①）。U-6~U-9 已由 P-012 §12 充分覆盖，本节仅交叉引用（§11.6），不重复。
> **编号声明**：新锚点 **A17-A30**、新文献 **15-28**，均在本批文档命名空间内（与 P-012 的 A17-A23/A24-A41 无关）。
> 检索以官方文档/监管文本/期刊-受控实验优先（T1/T2），工程实践次之（T3）。

### 11.0 新增外部锚点（A17-A30）

| ID | 来源 | 等级 | 原文要点 | 用于 |
|----|------|------|----------|------|
| **A17** | SciPy 2020 论文集（property-based testing 章节） | T1（会议论文集） | 「Running the same input through your code and through a trusted—or simply different—implementation is another widely applicable property: any difference in the outputs indicates that at least one of them has a bug」——**差分测试是 SciPy 生态公认的通用 property** | U-1 |
| **A18** | Barr et al. (2015) · The Oracle Problem in Software Testing: A Survey（T2 转述，1063 引用） | T2 | 测试 oracle 问题无通用解；oracle 分四类，各有成本-收益权衡 | U-1 |
| **A19** | arXiv 2105.01407 · Oracle Issues in Machine Learning | T2 | ML 场景 oracle 更难形式化；**metamorphic relations 是缓解 oracle 问题的主要 pseudo-oracle** | U-1 |
| **A20** | Golden Master / Characterization Testing（Feathers 术语，工程实践） | T3 | 「You don't assert what the code should do. You assert what it currently does」——golden master 只锁**当前行为**，重构防护用，**不证明正确性** | U-1 |
| **A21** | OSTI 报告 · Testing of Scientific Software（美国能源部） | T2 | 科学软件推荐回归测试套件 + 分层测试组织策略（单元/回归/系统） | U-1 |
| **A22** | 美联储 SR 11-7 · Guidance on Model Risk Management（官方 PDF） | T1 | 模型验证须有**独立性**（开发/使用者之外）；须做 **outcomes analysis 与 back-testing**（对照实际结果、测预测精度、支持再校准）；vendor 模型同标准 | U-2 |
| **A23** | 美联储 SR 26-02（官方 PDF，2026） | T1 | **取代 SR 11-7**；重申 Model Validation and Monitoring + vendor/第三方产品验证要求 | U-2 |
| **A24** | Baker (2016) · 1,500 Scientists Lift the Lid on Reproducibility（Nature 533:452） | T1（期刊） | 1,576 名研究者调查：**70% 曾未能复现他人实验**；>50% 认同存在显著可复现性危机 | U-2 / U-3 |
| **A25** | NautilusTrader · DST（Deterministic Simulation Testing）官方契约 | T1 | 种子受控运行时下的**可复现性保证**：定义保证成立的条件、enforce 契约的 source seams 与 checks、确定性终止的路径；「users and auditors can check the contract against the code」 | U-3 |
| **A26** | MLflow · Experiment Tracking Best Practices（官方） | T1 | 每次 run 记录 **git commit hash + 冻结的 resolved 配置（非模板）+ 环境快照（容器 digest）**；自动检测 Git 脏状态并存 diff | U-3 |
| **A27** | QuantEngines · backtrader vs vectorbt — Do They Agree? (Measured) | T3（实测文章） | 两库**默认参数下同策略结果差异巨大**；一致是「manufactured」——需钉死 3 项默认值后相对差才为 0；「a backtest result is a property of the harness as much as of the strategy」 | U-4 |
| **A28** | FeedsMonitor · 同一策略跑 10 年数据三库对比 | T3（实测文章） | Backtrader/vectorbt/Backtesting.py **开箱默认下同策略差 5.5%**；对齐各自规则后差距缩至 $45 且每一美元可解释 | U-4 |
| **A29** | BacktestScore · Execution Realism in Backtesting；QuantConnect 论坛 fill model 讨论 | T3 | 两套回测对同一策略收益不一致的常见根因：**成交模型假设**（信号价 vs 加滑点/延迟/缺口保护）；QC 默认 ImmediateFillModel 对 limit 单不加滑点 | U-4 |
| **A30** | INSPIRE · Cross-Validation of Open-Source Quantum Network Simulators；arXiv 1805.10978 · change-decomposition 受控实验 | T2（学术） | ①quisp 与 sequencer 两独立模拟器**在基础网络任务上交叉验证**以保一致性；②受控实验（28 名开发者）：**untangled changes**（按概念拆分提交）→ 更少误报缺陷、更多改进建议、评审时长不变——「committing changes belonging to different concepts separately should be an adopted best practice」 | U-4 / 合并 |

---

### 11.1 U-1 准确性验证的优先范围

**问题重述**：先做 L1（参考实现差分 + 不变量固化）还是直接上 L4（统计级 golden 回归）？

**外部证据**：

1. **没有参考实现，golden 只能锁现状**（A20）：golden master「断言代码当前做什么，而非应该做什么」——直接把现有引擎输出固化为期望值，**只能防回归、不能证正确**；若现状有错（P-012 已证实复权命名颠倒、涨跌停时点两处疑似），golden 会把错误焊死为「真值」。
2. **oracle 问题**（A18/A19）：统计级指标（Sharpe/回撤）没有独立 oracle；学术界的替代方案是 **metamorphic relations / 差分测试**——而 A17（SciPy 官方论文集）把「同一输入跑两个实现、任何输出差异即 bug」列为生态内最通用的 property。
3. **科学软件分层**（A21）：能源部报告推荐「单元 → 回归 → 系统」分层组织，回归套件用于「不丢失既有能力」，正确性论证靠更底层的不变量与解析解——与本仓 L1/L2 已强、L3/L4 弱的格局一致。
4. **工具链成熟**：Hypothesis 提供 pandas DataFrame 策略、pandera 支持基于 schema 的数据合成（SciPy 论文），参考实现差分可低成本属性化。

**方案比较（7 维）**：

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **V-A L1/L2 先行（推荐）** | 参考实现差分（V3 kernel vs 纯 Python 逐股循环；numba vs 回退路径）+ 不变量对账固化 + metamorphic 属性（确定性/口径恒等式） | 中（3-5 天） | 高（不依赖 oracle、能发现实现 bug） | 低 | 高 | 高 | 3-5 天 | 长期 |
| V-B 直接 L4 golden | 冻结当前统计输出 + 容差 | 低（1-2 天） | 低-中（只防回归；**会把 P-012 已证实的口径缺陷焊死为基线**） | 中（每次口径修正都要重录） | 低（与 ADR-017 行为变更冲突） | 低 | 快 | 负资产 |
| V-C 并行推进 | L1 与 L4 同批 | 高 | 中 | 高 | 低 | 低 | 慢 | 归因困难 |

**推荐**：**U-1 = V-A**。L4 golden 必须等 P-012 L2/L4 口径修正落地后录制（§3.14 硬约束①），否则基线作废或固化错误。证据等级：T1/T2/A17-A21 + 本仓 P3/P15。

### 11.2 U-2 学术规范深度

**问题重述**：是否需要对外报告声明 DSR/PBO？S-B 是否出首批？

**外部证据**：

1. **监管级要求已经落地**（A22/A23）：美联储 SR 11-7（2011）已要求模型验证含「outcomes analysis 与 back-testing」，**SR 26-02（2026）取代之并重申**；validation 必须独立于开发。含义：即使不对外发布，**口径统一（S-A）+ 偏差声明（S-C）也已是合规基线**，而非可选项。
2. **可复现性危机**（A24）：Nature 调查 70% 研究者未能复现他人结果——口径不一致（本仓 Sharpe 双口径 P9）正是复现失败的典型成因。
3. **DSR/PBO 的适用边界**（A9/A10/A11 已有锚点）：DSR/PBO 回答「回测收益有多少是选优偏差制造」——只在**存在多次试验记录**的场景可计算；本仓当前无试验登记（P10），S-B 强行上马会先变成「无数据可算」。

**方案比较（7 维）**：

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **S-A 口径统一（推荐，首批）** | Sharpe rf 单一口径 + 报告字段声明 rf | 低（1 天） | 高（消除 P9 双口径） | 低 | 高 | 高 | 1 天 | 长期 |
| **S-C 偏差声明（推荐，首批）** | 报告声明「未做多选校正 / 未含幸存者校正」 | 低（0.5 天） | 中-高（对齐 SR 26-02 独立验证精神） | 低 | 高 | 高 | 0.5 天 | 长期 |
| S-B DSR/PBO 计算 | 试验登记表 + CSCV/PBO + DSR | 中-高（1-2 周） | 高（仅对外发布场景） | 中 | 高 | 中 | 慢 | 待触发 |

**推荐**：**U-2 = S-A + S-C 首批，S-B 挂起至「对外发布因子/策略结论」需求出现**（触发时试验登记先行——没有 trials log 就没有 DSR/PBO）。证据等级：T1（A22/A23 官方 PDF）+ A24 + 本仓 P9/P10。

### 11.3 U-3 断点排查的形态

**问题重述**：「逐日 trace + run manifest」还是「交互式调试」？

**外部证据**：

1. **确定性是可审计契约**（A25）：NautilusTrader 把 DST 写成正式文档——种子受控运行时、保证条件、**enforce 契约的 source seams 与 checks**、确定性终止路径，且「auditors can check the contract against the code」。启示：trace/manifest 不是日志装饰，而是**与代码同审的契约**。
2. **manifest 三件套**（A26）：MLflow 官方实践 = **git commit hash + 执行时冻结的 resolved 配置 + 环境快照**；自动检测 Git 脏状态并保存 diff。与本仓「代码有 commit、数据无 checksum、无 run manifest」（P14/P18）差距明确。
3. **交互式调试不可入 CI**（A18 oracle 问题 + 本仓 P13）：`pdb`/`breakpoint()` 无可重放产物，无法满足「无法复现的异常用现有日志定位」之外的诉求；本仓 176 处日志 + 4 诊断出口已是「事后可查」底座，缺的是**过程态**。

**方案比较（7 维）**：

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **D-A 逐日 trace（推荐）** | `--trace-dir` 开关：逐日 dump 掩码/订单/成交/净值中间态（parquet），默认关闭 | 中（2-3 天） | 高（过程可查、可与 change_report 联动） | 低 | 高 | 高 | 2-3 天 | 长期 |
| **D-B run manifest（推荐）** | 每次 run 落 `manifest.json`：git commit + resolved config + 数据 sha256 + RULESET_VERSION/adjustment_mode（对齐 ADR-017/U-6） | 低（1-2 天） | 高（可复现三条件补齐两项） | 低 | 高 | 高 | 1-2 天 | 长期 |
| D-C 交互式调试 | debug 开关 + REPL 钩子 | 中 | 低（不可 CI、不可重放） | 中 | 中 | 低 | — | 不采纳 |

**推荐**：**U-3 = D-A + D-B**；trace 与 P-012 §11.2 六层归因共用同一套 dump（避免两套过程态）；D-C 不做。证据等级：T1（A25/A26）+ A24 + 本仓 P12/P13。

### 11.4 U-4 外部框架对拍的范围

**问题重述**：是否需要「与 Qlib 一致」的对外声明？

**外部证据**：

1. **默认参数下对拍必然失败**（A27/A28）：两库同策略「开箱」差 5.5%（A28）；quantengines 实测「一致」需要钉死 3 项默认值，且结论是「回测结果是 harness 的属性，不只是策略的属性」（A27）。
2. **不一致的第一根因是成交模型**（A29）：信号价成交 vs 滑点/延迟/缺口保护——正是本仓 P4（V2 次日开盘 vs V3 当日 close）与 P-012 P8（复权价成交）的同源问题；**先做口径映射再对拍**是社区唯一可行路径。
3. **交叉验证的学术形态**（A30①）：quisp vs sequencer 的做法是「**基础网络任务**上交叉验证」——不是端到端对拍，而是把共性任务拆到最小、逐项对齐。与本仓 X-A（口径映射 + 内核差分）同构。
4. **对外声明成本**（A27）：一旦声明「与 X 框架一致」，就承担其版本演进、默认值变更的联动维护——本仓无此人力。

**方案比较（7 维）**：

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **X-A 口径映射 + 内核差分（推荐）** | 文档化 V2/V3/Qlib 三方口径表；受控配置下 V2↔V3 差分（内部校准），不对外声明 | 中（3-5 天） | 高（消除 P4/P5 不可比） | 低 | 高 | 高 | 3-5 天 | 长期 |
| X-B 完整对拍 + 对外声明 | CI 固定 Qlib 版本跑对拍 + 发布声明 | 高（2 周+ 持续） | 低（仅声誉） | **高**（跟随 Qlib 版本） | 低 | 低 | 慢 | 长期负担 |
| X-C 不做 | 维持现状 | 0 | 低 | — | — | — | 0 | P4/P5 持续 |

**推荐**：**U-4 = X-A**；X-B 仅在「用户/评审明确要求第三方对照」时重审。证据等级：T3 实测（A27/A28/A29）+ T2（A30①）+ 本仓 P4/P5/P16/P17。

### 11.5 合并判定：P-011 与 P-012 一个 DESIGN 还是两个

**外部证据**：

1. **受控实验**（A30②）：变更分解实验（28 名开发者）——按概念拆分的变更组**更少误报缺陷、更多改进建议、评审时长不变**；结论明确支持「不同概念的变更分开提交」。
2. **行为变更归因**（P-012 §11.2 用户裁决）：六层归因链要求「每次行为变更单独批次 + `change_report.json`」——P-011 的 L4 golden 与 P-012 的 L2 口径修正是**不同概念**，合并 DESIGN 会让归因链跨批失效。
3. **本仓流程成本**（RULE/SPEC 流程）：单批 = 10 步 × 多道独立 Review；合并批的 CHECKLIST/ADD 审计要同时覆盖两类验收口径（偏差修正 vs 验证基建），Step 8 一致性 Review 的键值计数矩阵会跨两套基线。

**方案比较（7 维）**：

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **两个独立 DESIGN，P-012 先行（推荐）** | P-012 先 DESIGN/实施（偏差与口径）；P-011 的 L4 golden/统计规范在 P-012 L2/L4 落地后启动；两者共享 §3.14 依赖链 | 各批 10 步 | 高（每批可归因、可回退） | 低 | 高 | 高 | 中 | 长期 |
| 合并为一个 DESIGN | 单文档覆盖两批范围 | 文档量翻倍 | 低 | 高（跨概念基线） | 低（Step 8 计数矩阵跨基线） | 低 | 慢 | 归因失效 |
| 部分合并 | 共享「数据与口径契约」章节，其余独立 | 中 | 中 | 中 | 中 | 中 | 中 | 边界易漂移 |

**推荐**：**独立两个 DESIGN，P-012 先行**；P-011 DESIGN 中显式引用 P-012 的 §11.1 数据契约与 ADR-017 口径字段，避免第二套定义。证据等级：T2 受控实验（A30②）+ 本仓流程事实。

### 11.6 U-6~U-9 确认状态（交叉引用，不重复）

P-012 §12 已完成充分调研（锚点 A24-A41 + 7 维矩阵 + 验收标准），本节**不重复**；确认所需证据已足：

| 项 | P-012 推荐 | 本批交叉验证 |
|----|-----------|--------------|
| U-6 | D-A 本地快照 + manifest | 与本批 D-B（run manifest）字段兼容：`manifest.json` 增 `data_version` 即可衔接 |
| U-7 | C-A ≥2 minor 双轨 | ADR-017 已按此口径登记 |
| U-8 | R-A 不可变规则表 + fail-fast | 与本批 U-2（S-C 偏差声明）无冲突 |
| U-9 | B-A 端口 + 1 适配器 | 与本批 D-A trace 无耦合；P-004 边界表已固化 |

### 11.7 新增参考文献（15-28）

15. Proceedings of the 19th Python in Science Conference (SciPy 2020). *Property-Based Testing 章节（差分作为通用 property）*. https://conference.scipy.org/proceedings/scipy2020/
16. Barr, E. T., Harman, M., McMinn, P., Shahbaz, M., & Yoo, S. (2015). *The Oracle Problem in Software Testing: A Survey*. IEEE TSE. https://scispace.com/papers/the-oracle-problem-in-software-testing-a-survey-45arxvh6yl
17. Ricca, F., et al. (2021). *A Review on Oracle Issues in Machine Learning*. arXiv:2105.01407. https://arxiv.org/pdf/2105.01407
18. StackPractices. *Golden Master Testing: Characterize Legacy Code Safely*（Feathers 术语转述）. https://stackpractices.com/patterns/golden-master-testing-pattern/
19. Dubey, P., et al. *Testing of Scientific Software: Impacts on Research Credibility...*. OSTI 1347665. https://www.osti.gov/servlets/purl/1347665
20. Board of Governors of the Federal Reserve System (2011). *SR 11-7: Guidance on Model Risk Management*. https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107.pdf
21. Board of Governors of the Federal Reserve System (2026). *SR 26-02（取代 SR 11-7）*. https://www.federalreserve.gov/supervisionreg/srletters/SR2602.pdf
22. Baker, M. (2016). *1,500 Scientists Lift the Lid on Reproducibility*. Nature 533:452.
23. NautilusTrader. *DST: Deterministic Simulation Testing（官方契约文档）*. https://nautilustrader.io/docs/latest/concepts/dst/
24. MLflow. *LLM Experiment Tracking Best Practices（git commit + resolved config + 环境快照）*. https://www.mlflow.org/articles/llm-experiment-tracking-best-practices/
25. QuantEngines. *backtrader vs vectorbt — Do They Agree? (Measured)*. https://www.quantengines.com/backtrader-vs-vectorbt
26. FeedsMonitor. *Backtrader vs vectorbt vs Backtesting.py: I Ran the Same Strategy on 10 Years of Data*. https://feedsmonitor.com/article/backtrader-vs-vectorbt-vs-backtesting-py-i-ran-the-same-strategy-on-12477e82b8
27. BacktestScore. *Execution Realism in Backtesting: Fills and Slippage*；QuantConnect Forum. *Realistic backtesting question*. https://www.backtestscore.com/execution-realism-in-backtests
28. Paixão, K. S., et al. (2018). *The effects of change-decomposition on code review — A Controlled Experiment*. arXiv:1805.10978. https://arxiv.org/pdf/1805.10978v1

### 11.8 裁决记录（2026-11-10 用户确认）

| ID | 推荐 | 裁决 |
|----|------|------|
| U-1 | V-A L1/L2 先行 | ✅ **通过** |
| U-2 | S-A + S-C 首批；S-B 挂起 | ✅ **通过** |
| U-3 | D-A 逐日 trace + D-B run manifest | ✅ **通过** |
| U-4 | X-A 口径映射 + 内核差分 | ✅ **通过** |
| 合并判定 | 独立两个 DESIGN，P-012 先行 | ✅ **通过** |

> 结论：P-011 的 DESIGN 在 P-012 L2/L4 落地后启动；U-1~U-4 与合并判定全部闭合。P-012 进入 Step 3（[DESIGN_p012_bias_interface.md](DESIGN_p012_bias_interface.md)）；P-011 的 D-A/D-B（trace + manifest）中**层 dump 部分**由 P-012 D5 先行实现，P-011 复用不重写。
