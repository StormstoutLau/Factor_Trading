# RESEARCH：P-060 模块级模拟数据验证扩面（unit → integration → full）

> **批次（建议）**: **P-060**（编号待 U-P060-2 裁决；P-042..P-059 已占用）
> **预计档位**: **T1**（实现落在 `tests/`、可能含 `scripts/` 与少量生产 seam；按 P-059 先例判 T1）
> **上游**: 用户 2026-11-23 指令「使用模拟数据针对已实现的模块进行单元测试-集成测试-全量测试，充分检查模块计算、意图实现、边界与异常条件处理的准确性」；[P-059 调研](RESEARCH_p059_data_validation.md) / [DESIGN_p059](DESIGN_p059_data_validation.md) / [CHECKLIST_p059](CHECKLIST_p059_data_validation.md)；[PROGRESS §3.53](PROGRESS.md)
> **基线**: `b1afe29`（O-P051a-2 收口）；collect **1503**（1502 passed + 1 skipped）/ golden **22** / `-k p059` **63** / mypy **160·0** / black **325** / `tests/*.py` **161**
> **作者**: DeepSeek-V4.1-Flash（Step 2 必须 reviewer ≠ 作者，RULE-5）
> **状态**: Step 1 调研完成；**U-P060-1..6 全部闭合**（1/2/3 用户 2026-11-23；4/5/6 用户 2026-11-24 按 §9.1 建议裁定）；**Step 2 异构复审 PASS**（2026-11-24，[REVIEW_p060_step2](REVIEW_p060_step2.md)，4 处修订已落本文）；**Step 3 DESIGN 完成**（[DESIGN_p060](DESIGN_p060_module_verification.md)）；**Step 4 设计复审 PASS-WITH-COMMENTS**（[REVIEW_p060_step4](REVIEW_p060_step4.md)，F-11..F-17 已闭合）；**Step 5 实施文档完成**（[IMPL_p060a](IMPL_p060a_implementation.md)，X1-X29 外部源码锚点，54 例）→ 待落地实现

---

## 1. 问题定义

### 1.1 题干拆解

用户要求以既有「模拟数据测试排查」能力（P-059 场景库 + trace + `verify_scenario.py`）为基础，对**已实现模块**执行三层验证：

| 层 | 验证对象 | 核心问题 |
|---|---|---|
| **单元（unit）** | 单个模块/纯函数/类方法 | 公式是否算对？声明语义是否实现？边界/异常是否显式？ |
| **集成（integration）** | 2-5 个模块的组合缝 | 数据契约、口径、状态机、账目在跨模块处是否一致？ |
| **全量（full）** | 全仓测试资产 | 既有 1502 用例 + golden 22 + 场景 18 + 不变量 + 变质关系是否零漂移？ |

### 1.2 为什么现在

1. 关键路径批次（P-042..P-055）全部关闭，新增模块密集；但验证多为**批次内闭环**，跨批缺统一模块级视图。
2. P-059 只定义**场景层**（L1-L7）——验证「引擎按规则行为」，不验证「每个模块的公式、边界与异常契约」。
3. 覆盖率此前从未系统采集（CI 无 cov 步骤）；本次首测：**生产四包 85.80%**，但 **filter+agents 44.07%**，加权 **72.53%**（§3.1）。
4. 用户明确要求「计算 / 意图 / 边界与异常」四维度的准确性核查，需要把「场景抽查」升级为「模块矩阵」。

### 1.3 范围与口径

- **模块规模**：实现模块 **106** 个（core 50 / live 17 / services 12 / strategies 5 / filter 9 / agents 13；均不含 `__init__`）。
- **模拟数据** = 确定性合成数据：`tests/_synth_fixture.py`、`tests/_synthetic_data.py`、`scripts/prepare_test_fixture.py`、`tests/_scenarios_cases.py`；禁真实行情 / 网络 / 当前时间 / 随机种子漂移。
- **三层不新建目录**：unit 复用既有 `tests/test_*.py`；integration 复用 `_scenarios_builder.build_scenario`；full 复用全量门禁。
- **不改变既有口径**：golden 22 零重录；不引入 Hypothesis、不引入第三方回测框架（沿 P-059 D5/D11）。

---

## 2. 现有资产盘点（E3）

| # | 资产 | 位置 | 已证明 | 未覆盖（本批缺口来源） |
|---|---|---|---|---|
| 1 | P-059 场景库 | [_scenarios_cases.py](../tests/_scenarios_cases.py)（18 条）、[_scenarios_spec.py](../tests/_scenarios_spec.py)、[_scenarios_builder.py](../tests/_scenarios_builder.py)、[_scenarios_trace.py](../tests/_scenarios_trace.py) | 引擎级 7 层行为、逐日 trace、10 断言原语、3 条变质关系、8 键能力边界；`-k p059` **63** | 场景级抽样，**非模块级**；未覆盖可选配置分支与公共 API 分支 |
| 2 | 统一排查入口 | [verify_scenario.py](../scripts/verify_scenario.py) | `--list` / `--scenario` / `--day` / `--json` / `--boundaries`；失败可定位到日桶 | 只能跑已注册场景；模块级失败需 pytest/覆盖率定位 |
| 3 | golden 基线 | `tests/golden/`（22 case）、[_golden_cases.py](../tests/_golden_cases.py)、[record_golden.py](../scripts/record_golden.py) | 端到端末值回归（`rtol=1e-9`、`money_atol=1e-6`） | 只有末值；**仅行为锁定，不能证明正确性**（P-059 X8） |
| 4 | 合成夹具四套 | [_synth_fixture.py](../tests/_synth_fixture.py)、[_synthetic_data.py](../tests/_synthetic_data.py)、[prepare_test_fixture.py](../scripts/prepare_test_fixture.py)、`examples/demo.py::generate_synthetic_data` | 价格/OHLC/复权/停牌/ST/行业/市值/因子；P-042 最小数据集；baseline/biased 两套 profile | 四套口径并存、无统一入口；`open/high/low` 缺省复用 `close`（G3） |
| 5 | 参考实现对拍 | [_reference_impl.py](../tests/_reference_impl.py) + [test_reference_diff.py](../tests/test_reference_diff.py)（9 例） | V2 调仓内核 / 目标持仓的独立重算 | 仅指标层（9 例），不覆盖执行成本、因子、触发器等 |
| 6 | 不变量 | [invariants.py](../core/invariants.py)（I1-I7）+ [test_invariants.py](../tests/test_invariants.py)（11 例） | NAV/成本/持仓/收益恒等 | 只验「账目自洽」，不验「规则是否按意图执行」 |
| 7 | 契约符合性 | [test_contract_conformance.py](../tests/test_contract_conformance.py) + [interfaces.py](../core/interfaces.py) | `IDataManager`/`IUniverseFilter`/`IPositionTracker` 等成员集 | 只到成员存在性，不含行为契约 |
| 8 | 异常治理 | `test_p026/p027/p029_silent_exception_governance.py` + AST 扫描 | `except Exception` 定位（core 外 **22** · core **30**） | 只治理「静默吞异常」，不系统验证「文档声明的 raise 路径」 |
| 9 | 诊断/归因 | [diagnostics.py](../core/diagnostics.py)、[event_log.py](../core/event_log.py)、[change_report.py](../core/change_report.py) | 日级错误分类、事件流、六层归因 diff | 无「覆盖率快照 / 模块 gap」维度 |

**结论**：机制齐备、锚点扎实；缺口不在「有没有工具」，而在「**模块级三层矩阵 + oracle 选择规则 + 覆盖率基线**」。

---

## 3. E1 取证（@`b1afe29`，2026-11-23）

### 3.1 全量 + 覆盖率（本轮实测）

| 读数 | 命令 | 结果 |
|---|---|---|
| 全量（无覆盖率） | `.venv\Scripts\python -m pytest tests/ -q` | **1502 passed, 1 skipped**（collect 1503；基线记录 132.76s） |
| 覆盖率 A（生产四包） | `--cov=core --cov=live --cov=services --cov=strategies --cov-report=json` | **85.80%**（10437/12165）；**198.95s**；1502 passed + 1 skipped |
| 覆盖率 B（filter+agents） | `--cov=filter --cov=agents --cov-report=json` | **44.07%**（2499/5670）；**193.57s**；1502 passed + 1 skipped |
| 加权全模块 | A+B 合并（非单次运行） | **72.53%**（12936/17835） |
| 分支覆盖 | `--cov-branch` | **未采集**（0/0）→ 列入 U-P060-6 |

**包级**：core **86.52%**（9117 stmts）/ live **87.95%**（1693）/ services **74.54%**（1092）/ strategies **93.54%**（263）/ filter **44.44%**（1330）/ agents **43.96%**（4340）。

> **Step 2 重放差异（F-14）**：2026-11-24 重放 covA 得 **10432/12165（85.80%）**，core **7883/9117（86.46%）**，与本表首次采集差 **5 行**（0.04pp），其余三包与 9 个抽查文件逐位一致。覆盖率基线以**重放 JSON**（`source=step2-replay`）为准，见 [DESIGN_p060 §7](DESIGN_p060_module_verification.md)。

### 3.2 静态模块 → 测试映射

- 扫描 **102** 个模块（live 仅顶层 13 个，4 个 adapters 另计）、**150** 个 `test_*.py`；**11** 个模块**无直接测试引用**。
- **口径警示**：零引用 ≠ 零覆盖（`services/ws_routes.py` 无直接 import，但被 app 间接执行，覆盖 73.8%）；相对导入（`filter/base.py` 被 `from .base import`）也不计入「直接引用」。

| 零引用模块 | 覆盖率 | 生产调用方 | 定性 | 处置建议 |
|---|---|---|---|---|
| `services/market_gateway.py` | **0.0%** | `services/trading_worker.py` | **生产可达、零验证**（P1） | 集成层补测（B2） |
| `services/ws_routes.py` | 73.8% | `services/api.py` | 间接覆盖（经 app） | 补端点分支（B2） |
| `filter/base.py` | 36.6% | `filter/*` 6 子模块 | 公共库基类 | 与子模块合并补测（U-P060-1） |
| `filter/extended.py` | 20.7% | 仅 `filter/__init__` 导出 | 未接引擎的公共库 | 分类后决定（U-P060-1） |
| `filter/industry.py` | 20.5% | 仅导出 | 同上 | 同上 |
| `filter/market_cap.py` | 23.3% | 仅导出 | 同上 | 同上 |
| `filter/na_factor.py` | 23.8% | 仅导出 | 同上 | 同上 |
| `filter/prefix.py` | 25.4% | 仅导出 | 同上 | 同上 |
| `agents/adaptive_agent.py` | **0.0%** | 0 | 研究型、未接线 | 不测，声明 legacy（B4） |
| `agents/sentiment_framework.py` | **0.0%** | 0 | 研究型、未接线（P-049 邻域） | 不测，声明 legacy |
| `agents/style_drift_analysis.py` | **0.0%** | 0 | 研究型、未接线 | 不测，声明 legacy |

> **Step 2 修订（F-3/F-4/F-5）**：① `market_gateway`「测试零引用」成立——[test_p055_entrypoint.py](../tests/test_p055_entrypoint.py#L76-L79) 仅 `read_text` 断言 `__main__` 守卫，**不 import**（覆盖 0% 一致）；② agents 三模块非严格「全仓零调用」：仅 `test_compatibility.py:43-46` **字符串清单**引用 + `style_drift_analysis.py:528` 包内 `from adaptive_agent import AdaptiveAgent`（顶层绝对导入、函数内死路径），无功能调用；③ filter 5 子模块 + `base` 经 tests 全文搜索确认零 import ✓。

### 3.3 生产四包低覆盖清单（<80%）

| 文件 | 语句 | 未覆盖 | 覆盖率 | 读码定性 |
|---|---|---|---|---|
| `core/rebalance.py` | 153 | 100 | **34.6%** | 默认引擎路径仅选择 `FixedIntervalTrigger`；`Conditional/HybridTrigger` 虽经 [engine_plugins.py](../core/engine_plugins.py#L361-L383) 注册工厂但从未被选中执行；`RebalanceCalendar` 全仓无生产引用（Step 2 修订 F-3） |
| `services/bus.py` | 157 | 57 | 63.7% | 真实 Redis Streams 路径仅部分执行（测试多用 fake） |
| `services/trading_worker.py` | 91 | 33 | 63.7% | 运行循环/组装路径部分执行 |
| `core/factor.py` | 275 | 97 | 64.7% | `reverse/winsorize/fill/neutralize/standardize` 可选分支未全测 |
| `core/registry.py` | 115 | 38 | 67.0% | 插件注册/反注册/错误路径 |
| `services/ws_routes.py` | 130 | 34 | 73.8% | 鉴权失败分支、慢消费者分片分支 |
| `services/api.py` | 172 | 41 | 76.2% | 非主路径端点 |
| `core/global_contagion.py` | 285 | 62 | 78.2% | **0 生产调用方** → legacy |
| `core/diagnostics.py` | 132 | 28 | 78.8% | 错误分类分支 |
| `core/tracker.py` | 350 | 74 | 78.9% | `get_position_weights`/`get_sector_exposure`/期货公共 API |
| `core/event_log.py` | 205 | 43 | 79.0% | 事件类型与轮转分支 |

### 3.4 filter / agents 覆盖（本轮补测）

| 包 | 语句 | 未覆盖 | 覆盖率 |
|---|---|---|---|
| filter | 1330 | 739 | **44.44%** |
| agents | 4340 | 2432 | **43.96%** |

低覆盖代表（读码定性）：`filter/industry` 20.5% / `extended` 20.7% / `market_cap` 23.3% / `na_factor` 23.8% / `prefix` 25.4% / `base` 36.6%——均为**未接引擎的公共过滤器 API**；`filter/universe_filter_clean.py`（引擎路径）68.3%——**生产可达但覆盖不足**。
`agents/hierarchical_bayesian_agent` 26.8% / `auto_parameter_optimizer` 33.7% / `agent_framework` 41.4% / `research_team_v2` 42.9%——研究型/未接线。

### 3.5 未覆盖段读码定性（示例）

- [execution.py](../core/execution.py)：`_calculate_cost` L378-423 的**佣金下限 / 印花税（仅卖出）/ 滑点**无独立闭式断言（现有仅 `test_sell_cost_calculation` 1 例）；未覆盖 L371-376（异常旁路）、L511-522（价格合法性）、L538-548（市场冲击，未被引擎调用）。
- [factor.py](../core/factor.py)：`process` L65-100 的 5 个可选开关（reverse/winsorize/fill/neutralize/standardize）未逐一锁定；未覆盖 L62-63（错误旁路）。
- [rebalance.py](../core/rebalance.py)：4 类触发器仅固定间隔被引擎默认路径执行；条件触发/波动触发无场景。
- [tracker.py](../core/tracker.py)：L474-520（权重/行业暴露）与 L571-607、L702-741（期货/公共 API）未执行；资金核心路径主流程覆盖良好。
- [universe_filter_clean.py](../filter/universe_filter_clean.py)：68.3%，掩码合成主路径之外的分支（分层/摘要/边界）未测。

### 3.6 异常测试密度（静态上界：引用测试文件内 `pytest.raises` 次数）

| 模块 | `raise` 数 | `pytest.raises` | 判定 |
|---|---|---|---|
| `core/portfolio.py` | 41 | 47 | 强 |
| `core/lifecycle.py` | 29 | 24 | 强 |
| `core/sizing.py` | 18 | 8 | 中 |
| `core/risk_overlay.py` | 8 | 16 | 强 |
| `core/config_v2.py` | 8 | **0** | **缺口（FROZEN，须契约测试或声明）** |
| `core/data.py` | 6 | 3 | 部分 |
| `core/factor.py` | 1 | **0** | **缺口** |
| `core/rebalance.py` | 1 | **0** | **缺口** |
| `services/market_gateway.py` | 0 | 0 | 无异常契约（0% 覆盖） |
| `services/trading_worker.py` | 0（3 `except`） | 0 | 失败注入未测 |

### 3.7 排查入口实跑

- `verify_scenario.py --list`：**18 条 / 7 层全覆盖**（S01-S14 + E01-E03 + S15）。
- `verify_scenario.py --scenario S09 --json`：**exit 0**；`ohlc_synthetic=true`；`fills=[]`；`order_states={retry:3, dropped:1}`；`final_cash=1004.0`；stderr 明确「需要=1006.00 可用=1004.00」→ 最低佣金拒绝路径可复现。
- **结论**：场景级排查可用；但**模块级**失败仍需 pytest 断言 + 未覆盖行/覆盖率定位，这正是本批要补的层。

### 3.8 三层现状判定

| 层 | 现状 | 证据 |
|---|---|---|
| 单元 | **不均衡**：资金核心（portfolio/sizing/stops/overlay）强；可选分支（factor/rebalance）与公共 API（tracker/execution helpers）弱 | §3.3/§3.5 |
| 集成 | **引擎强、服务层弱**：engine→optimizer→execution→tracker 有场景/不变量；services（market_gateway/trading_worker/bus/ws_routes）低覆盖 | §3.1/§3.3 |
| 全量 | **强**：1502 + golden 22 + p059 63 + 不变量 + 变质 + 能力边界 | §3.1/§3.7；P-059 §8 |

---

## 4. 缺口清单（G-P060-1..12）

| ID | 缺口 | 证据 | 影响 | 层 | 优先级 |
|---|---|---|---|---|---|
| **G-P060-1** | unit/integration/full **三层与 oracle 规则未成文** | P-059 仅场景层；本仓无测试分层规范（SPEC_STANDARD 只有 80% 一句） | 后续补测无统一验收 | 方法 | **P1** |
| **G-P060-2** | 覆盖率**无基线、无 CI 采集、无棘轮** | §3.1（本轮手工采集）；[tests.yml](../.github/workflows/tests.yml) 无 cov 步骤 | 覆盖漂移不可见 | full | P2 |
| **G-P060-3** | 生产模块 **0% 覆盖**：`services/market_gateway.py` | §3.1/§3.2（63 stmts，0%） | 行情源行为无回归保护 | integration | **P1** |
| **G-P060-4** | **可选配置分支**低覆盖：`rebalance` 34.6% / `factor` 64.7% | §3.3/§3.5 | 用户启用非默认配置时行为不可回归 | unit | **P1** |
| **G-P060-5** | 资金路径**公共 API 分支**未覆盖：`tracker` 78.9% / `execution` 84.8% | §3.3/§3.5 | 权重/行业暴露/价格合法性/市场冲击无锁 | unit | P2 |
| **G-P060-6** | **services 集成层**低覆盖：`bus` 63.7% / `trading_worker` 63.7% / `ws_routes` 73.8% / `api` 76.2% | §3.3 | 运行时组装与真实 IO 路径风险 | integration | **P1** |
| **G-P060-7** | **异常契约未系统验证**：`config_v2` 8 raise/0 测试；`factor`/`rebalance` 1/0；`data` 6/3 | §3.6 | 文档声明的失败路径可能是死代码 | unit | P2 |
| **G-P060-8** | **数值 oracle 缺口**：execution 成本（买/最低佣金/滑点）无独立闭式；rebalance 触发边界；factor 退化输入 | §3.5/§3.6 | 算错时只能靠 golden 末值兜底 | unit | **P1** |
| **G-P060-9** | **意图追溯无统一矩阵**：55 份 CHECKLIST 各自闭环，D/I/AC→test 无跨批索引 | `docs/CHECKLIST_*.md` 55 份 | 「意图实现」无法机械核查 | 方法 | P2 |
| **G-P060-10** | **测试数据生成器碎片化**：5 套口径（`_synth_fixture`/`_synthetic_data`/`prepare_test_fixture`/`demo`/`scenarios`） | §2-4 | 新测试选型成本高、口径漂移 | 方法 | P2 |
| **G-P060-11** | **遗留/研究模块未分类**：agents 3 个 0%（无功能调用，仅字符串清单引用）；`global_contagion`→`risk_monitor` 链 0 生产调用；`walk_forward_engine`/`engine_plugins` 0 调用；filter 6 子模块未接引擎；`ctp`/`broker_api` 0%；`RebalanceCalendar` 无生产引用 | §3.2/§3.4；`risk_scan` 生产调用方列 | 补测预算可能浪费在死代码 | 方法 | P3 |
| **G-P060-12** | **P-059 登记项未闭环**：F-S6-P059-4（`assert_target_deviation` 未接线）/ -5（trace BUY 兜底死代码）/ -6（末日桶幂等不完整）；能力边界（退市整理期/盘中临停/集合竞价） | [DESIGN_p059 §17.2.4](DESIGN_p059_data_validation.md) | 排查工具自身残留 | full/工具 | P3 |

> **计数**：12 项 = P1 **5**（1/3/4/6/8）+ P2 **5**（2/5/7/9/10）+ P3 **2**（11/12）✓。

---

## 5. 方案对比

### 5.1 候选方案

| 方案 | 内容 | 优点 | 缺点 |
|---|---|---|---|
| **M-A 分层验证矩阵**（推荐） | 定义 unit/integration/full 三层 + oracle 阶梯 + 缺口驱动补测；复用 P-059 harness，不新建体系 | 与 P-059 同源；按缺口分配预算；测试侧为主 | 需先固化规则与基线 |
| M-B 覆盖率门禁驱动 | CI 设 85% 门禁，逐文件补齐至阈值 | 执行简单、短期见效 | 覆盖率高≠断言强（A4/A5）；可能诱导空断言 |
| M-C 全模块 1:1 补齐 | 106 模块逐一建 unit 文件 | 纸面完整 | 成本极高；死代码浪费；维护膨胀（A8） |
| M-D 仅处置 0%/遗留 | 只补 `market_gateway` 与 0% adapters | 成本最低 | 可选分支/异常契约仍空白（G-P060-4/7/8） |

### 5.2 七维矩阵（非 trivial 决策）

| 维度 | M-A（推荐） | M-B | M-C | M-D |
|---|---|---|---|---|
| 成本 | 中（分 3 批，A1/A2） | 低-中（工具+门禁，A5） | 极高（A8/A1） | 低（A7） |
| 收益 | 高（计算+意图+边界，A2/A3） | 中（仅行覆盖，A4） | 高（理论） | 低（A6 仅边界值） |
| 兼容 | 高（测试侧为主） | 高 | 中（大量新文件） | 高 |
| 维护 | 高（复用同一 harness，A1） | 中（门禁噪声/flaky） | 低（重复膨胀，A8） | 高 |
| 升级潜力 | 高（变质关系可扩展，A3/A9） | 低 | 低 | 低 |
| 短期 | 中 | **高** | 低 | 中 |
| 长期 | **高** | 低-中 | 中 | 低 |

### 5.3 外部锚点

| ID | 来源 | 关键结论 | 用途 | 置信度 |
|---|---|---|---|---|
| A1 | Fowler, *The Practical Test Pyramid*, 2018, https://martinfowler.com/articles/practical-test-pyramid.html | 分层组合（unit 多、integration 中、e2e 少），integration 慢但给跨部件信心 | M-A 分层依据 | 高（T1 实践） |
| A2 | Barr et al., *The Oracle Problem in Software Testing: A Survey*, IEEE TSE 41(5):507-525, 2015, https://dl.acm.org/doi/abs/10.1109/TSE.2014.2372785 | 无 oracle 时测试自动化受阻；需系统性 oracle 选择 | oracle 阶梯 | 高（T1 论文） |
| A3 | Chen et al., *Metamorphic Testing: A Review of Challenges and Opportunities*, ACM CSUR 51(1), Art.4, 2018（online 2018-01-04 / print 2019-01，Crossref 核验）, https://dl.acm.org/doi/10.1145/3143561 | 变质关系可在无 oracle 时检出故障 | 复用 P-059 三条关系并扩展 | 高（T1 论文） |
| A4 | Inozemtseva & Holmes, *Coverage is Not Strongly Correlated with Test Suite Effectiveness*, ICSE 2014:435-445, https://dl.acm.org/doi/10.1145/2568225.2568271 | 覆盖率与故障检出相关性弱（受测试规模影响） | 覆盖率只作诊断/棘轮，不作唯一目标 | 高（T1 论文） |
| A5 | Google Testing Blog, *Code Coverage Best Practices*, 2020, https://testing.googleblog.com/2020/08/code-coverage-best-practices.html | 覆盖率是工具不是目标；关注 diff coverage | 覆盖率落地方式 | 高（T2 工业） |
| A6 | Myers, *The Art of Software Testing*（边界值分析） | 边界值是最经济的高缺陷密度区域 | 边界表设计 | 高（T1 书目） |
| A7 | ISTQB CTFL Syllabus（风险驱动测试） | 按风险分配测试预算 | 遗留模块分类 | 高（T2 标准） |
| A8 | Meszaros, *xUnit Test Patterns*, 2007, http://xunitpatterns.com/ | 测试替身/固定装置成本与维护 | 拒绝 M-C 的依据 | 高（T1 书目） |
| A9 | P-059 §3.2 X6-X9（Referential Labs 变质关系 / Susan Potter 属性测试 / Feathers 特征测试 / Bailey-López de Prado） | 回测无外部 oracle；行为锁定≠正确性 | 与 A2/A3 互补 | 高（P-059 Step 2 已复核） |

> A1-A9 为**方法论**锚点（为什么分层、为什么覆盖率只做诊断）。**裁定级**的社区案例/Q&A/行业政策锚点见 **§9.1（A10-A38）**，专供 U-P060-4/5/6 拍板。

### 5.4 裁决

**采纳 M-A，覆盖率按 A4/A5 只做「诊断 + 棘轮」**（每批快照不得下降），不设一次性硬门禁；拒绝 M-C（成本不成比例）、M-D（覆盖面不足）。M-B 的 CI 采集部分纳入 full 层（B3），阈值待两批稳定后由用户裁决（U-P060-3）。
被拒代价：M-B 可能产生「为覆盖而断言」；M-C 预计新增 100+ 文件、维护成本高；M-D 放任 `rebalance/factor` 可选分支与异常契约空白。

---

## 6. 规格（S1-S12）

| ID | 规格 |
|---|---|
| **S1** | **三层归属**：unit = 单模块直接调用（无引擎/无文件 IO，`tmp_path` 除外）；integration = 2-5 模块组合（可用 `build_scenario`）；full = 全量门禁集合 |
| **S2** | **oracle 阶梯**：闭式公式 > 独立参考实现 > 不变量 > 变质关系 > golden；**golden 不得作为唯一 oracle**（A2/A9） |
| **S3** | unit 用例**确定性**：无 `random`/当前时间/网络；同用例重复 3 次结果逐字节一致 |
| **S4** | unit **计算类**用例必须给出手算或闭式期望，禁止「先跑后录」 |
| **S5** | **边界分类**：数值（NaN/±0/Inf/舍入/极值）、集合（空/单元素/重复/乱序/长度不匹配）、状态（空仓/满仓/停牌/涨跌停/T+1）、IO（缺文件/损坏/锁/超时）、配置（非法组合） |
| **S6** | **异常契约**：断言异常类型 + 消息关键词 + **状态不变**（fail-closed）+ 诊断落账；文档声明的 raise 路径必须有测试或标注「不可达」 |
| **S7** | **意图追溯**：每批 DESIGN 的 D/I/AC 项映射到测试 ID；映射缺失即登记缺口（G-P060-9） |
| **S8** | **全量层命令固定**：全量 pytest + `-k golden` + `-k p059` + 不变量 + 变质；覆盖率 JSON 入 CI artifact（先诊断，不门禁） |
| **S9** | **覆盖率棘轮**：每批快照相对基线下降 >0.5pp 即失败；新增文件不得引入 0% 覆盖的生产模块 |
| **S10** | **模块分类**：`production` / `library` / `legacy-research` 三标签；legacy 只做契约/能力边界，不追求覆盖率 |
| **S11** | **数据复用**：引擎集成用 `_synth_fixture` + `_scenarios_cases`；契约测试用 `_synthetic_data`；unit 用内存数组；**不新增第五套生成器**（G-P060-10） |
| **S12** | **零新依赖**：不引入 Hypothesis / 第三方回测框架 / 覆盖率 SaaS；pytest-cov 已在 `pyproject.toml` dev 依赖 |

---

## 7. 批次拆分（B1-B4，建议）

| 块 | 范围 | 交付物 | 验收（估算，Step 3 定稿） |
|---|---|---|---|
| **B0 基线** | 本文 + Step 2 复审 + 覆盖率命令固化 | `RESEARCH_p060` / `REVIEW_p060_step2`；coverage JSON 快照 | E1 复现 1502+1 / 85.80% / 63 / 22 |
| **B1 单元层（core）** | `execution` 成本闭式；`rebalance` 四类触发器；`factor` 五个可选开关 + 退化输入；`tracker` 公共 API；`registry` 错误路径；`config_v2/factor/rebalance` 异常契约 | `tests/test_p060_*.py`（约 35-45 例） | core ≥ **88%**；p060 全绿；零 golden 重录 |
| **B2 集成层（services/live）** | `market_gateway`（0%→≥80%）；`trading_worker`；`bus` 真实路径（有 Redis 则真跑，无则协议级 fake）；`ws_routes` 失败分支；`ctp`/`broker_api` 录制帧映射（不触网） | 约 30-40 例 | services ≥ **85%**；live ≥ **90%**；full 绿 |
| **B3 全量层** | 覆盖率 JSON artifact + 棘轮检查；`-k p060` 门禁；能力边界更新 | 1 脚本 + 1 测试 + 文档 | 全量绿；覆盖率不降；运行 ≤ 300s |
| **B4 遗留分类** | agents/filter/legacy 三标签清单；`validation.py` 能力常量复核；P-059 F-S6 登记项处置 | 文档 + 0-3 例 | 分类 100% 覆盖 106 模块 |

> 估算为量级，不作为承诺；Step 3 DESIGN 逐项定稿测试数与门禁。

---

## 8. 不变式（I1-I10）

| ID | 不变式 |
|---|---|
| I1 | golden **22 零重录**（本批不新增 golden） |
| I2 | 全量 pytest 绿；collect 只增不减；skip 不增加 |
| I3 | P-059 **18 场景**脚本与断言零改动 |
| I4 | 每个 `production` 模块至少 **1 个非 golden oracle**（S2） |
| I5 | 文档声明的 raise 路径：有测试或标「不可达」，二者必居其一 |
| I6 | 零新运行时依赖（`pyproject.toml`/`uv.lock` 零 diff） |
| I7 | unit 确定性：重复 3 次逐字节一致 |
| I8 | 覆盖率棘轮：本批快照 ≥ 基线 − 0.5pp |
| I9 | legacy 清单变更须显式裁决，不静默纳入/剔除 |
| I10 | 单轮全量（含行覆盖率）运行 ≤ **300s**（Step 2 重放 183.49s）；分支覆盖独立轮单独计时，同为诊断不门禁（U-P060-6，Step 2 澄清 F-7） |

---

## 9. 裁定（U-P060-1..6，全部闭合）

| ID | 事项 | 选项 | 裁定 |
|---|---|---|---|
| **U-P060-1** | 范围 | A) core/live/services/strategies（生产四包）；B) + filter；C) + agents；D) 全部 106 | **已闭合：A（生产四包）**（用户 2026-11-23） |
| **U-P060-2** | 批次形态 | A) P-060a/b/c 三批；B) 单批四波；C) 只做 B1 | **已闭合：A（三批 a/b/c）**（用户 2026-11-23） |
| **U-P060-3** | 覆盖率角色 | A) 诊断+棘轮；B) CI 硬门禁 85%；C) 不采集 | **已闭合：A（诊断+棘轮）**（用户 2026-11-23） |
| **U-P060-4** | 缺陷处置 | A) 当批修复 P1/P2；B) 只登记；C) 单独立项 | **已闭合：A**（P1/P2 当批修，但须**独立 commit** + 复现用例 + PROGRESS 条目；P3 登记；用户 2026-11-24） |
| **U-P060-5** | 生产 seam | A) 默认不改，先测试侧；B) 允许注入 clock/RNG/transport 小改 | **已闭合：A 默认 + B 白名单**（仅 Clock/RNG/Transport/Humble Object，四条准入见 §9.1.2；用户 2026-11-24） |
| **U-P060-6** | 分支覆盖 | A) 本轮补 `--cov-branch` 快照；B) 仅行覆盖 | **已闭合：A**（独立命令、informational、不 blocking；用户 2026-11-24） |

---

## 9.1 裁定项的证据补强（社区案例 / 问答 / 行业政策，A10-A38）

> 用途：U-P060-4/5/6 已于 2026-11-24 按本节证据闭合；证据链保留，供 Step 2 复审与日后追溯。下表 URL 均于 2026-11-23 由研究代理实际打开核对；同源内容只保留官方原文（Google 覆盖率博文沿用 §5.3 A5，不重复计）。**每条均标注是否支持建议选项**，反向证据一并列出。
>
> **可达性核验**：本机 curl（2026-11-23）：A10 / A12 / A13 / A18 / A27 / A28 / A34 返回 **200**；GitHub 类（A11 / A36 / A37 / A38）直连超时。Step 2 联网复审（2026-11-24，独立代理）：A2-A4 经 **Crossref DOI 元数据**核验属实；A11 / A12 / A15 / A19 / A27 / A36 / A38 原文核实；**A5 两次抓取异常、A11 raw 两次空返回、A16 CAPTCHA 拦截 → unreachable（引用时注明，Step 3 不依赖其原文细节）**。A27 原表述有误，已修正（见该行）。

### 9.1.1 U-P060-4 缺陷处置 → 已裁定 A（P1/P2 当批修、P3 登记）

| ID | 锚点（类型） | 核心主张 | 倾向 |
|---|---|---|---|
| A10 | [Google eng-practices · Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)（官方规范） | "It's usually best to do refactorings in a separate CL from feature changes or bug fixes." | 中：支持**独立提交**，不直接判级 |
| A11 | [Kubernetes pull-requests 指南](https://github.com/kubernetes/community/blob/master/contributors/guide/pull-requests.md)（官方规范） | 范围外问题"You absolutely should fix those things (or at least file issues) — but not in the same pull request." | **强**：修或登记，但不得混入本批改动 |
| A12 | [PagerDuty · Severity Levels](https://response.pagerduty.com/before/severity_levels/)（行业政策） | SEV-1/2 立即响应；SEV-5 外观类"Create a JIRA ticket and assign to owner" | **强**：分级处置正是 A |
| A13 | [Atlassian Bug Fixing Policy](https://confluence.atlassian.com/conf90/bug-fixing-policy-1425053888.html)（厂商政策） | 关键功能/安全缺陷在全部受支持版本修复；非关键缺陷按排期 | **强** |
| A14 | [SE #414466](https://softwareengineering.stackexchange.com/questions/414466)（高票问答） | 范围外改动"separate branch"；另一答案"I usually like to create an issue so it isn't forgotten" | 中：非阻塞则登记 |
| A15 | [Fowler · Opportunistic Refactoring](https://martinfowler.com/bliki/OpportunisticRefactoring.html)（**反向**） | "take the opportunity to fix it right there and then"；"another day often doesn't come" | 反向：反对**推迟**，但谈的是重构，不反对分级 |
| A16 | [SE #156266](https://softwareengineering.stackexchange.com/questions/156266)（**反向**） | 小改进也值得单独提交；"don't want a crashing bug fix to be mixed up with 500 comment/typo changes" | 反向/条件：仍要求**分离提交** |

**裁定（用户 2026-11-24 确认；下列为约束条款）**：A，但「当批修」必须落为 **独立 commit**（K8s/Google 均禁止混入本批改动），并同时交付：① 复现用例（先红后绿）；② PROGRESS 缺陷条目（含 P 级与影响面）；③ 若修复触及 `core/` 资金路径，走 T1 复审。P3（文档/日志文案/死分支）只登记，不打断批次。反向证据（A15/A16）只反对「无限推迟」，与「按严重度分级」不冲突——故不采纳 B。

### 9.1.2 U-P060-5 生产 seam → 已裁定「A 为默认 + B 白名单」

| ID | 锚点（类型） | 核心主张 | 倾向 |
|---|---|---|---|
| A17 | [Feathers · Seam（书摘）](https://www.informit.com/articles/article.aspx?p=359417&seqNum=2)（T1 书目） | "A seam is a place where you can alter behavior in your program without editing in that place." | B（seam 的定义即最小改造依据） |
| A18 | [Fowler · Humble Object](https://martinfowler.com/bliki/HumbleObject.html)（模式） | "move as much logic as possible out of the hard-to-test element" | B：优先抽纯逻辑，而非改外壳 |
| A19 | [DHH · Test-induced design damage (2014)](https://dhh.dk/2014/test-induced-design-damage.html)（**反向**） | "Code that is warped out of shape solely to accomodate testing objectives." | 反 C：反对为测试重排架构 |
| A20 | [Uncle Bob 反驳 DHH](https://blog.cleancoder.com/uncle-bob/2017/03/03/TDD-Harms-Architecture.html)（**反向之反**） | "it is not TDD that creates bad designs… It's you." | B（有纪律的 DI 可接受）/ 反 C |
| A21 | [pytest · monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)（官方文档） | 用于"code which cannot be easily tested such as network access" | A：测试侧替身优先 |
| A22 | [SE #386266](https://softwareengineering.stackexchange.com/questions/386266)（高票问答） | 采纳答"making code testable is an essential part"；次答"changing the code without a good business reason is not a good idea" | A-B 折中 |
| A23 | [SO #13073281](https://stackoverflow.com/questions/13073281)（高票问答） | 如何 mock `datetime.now()`（社区标准做法是测试侧替换） | A |
| A24 | [java.time.Clock](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/time/Clock.html)（官方 API） | "primary purpose … allow alternate clocks to be plugged in … This can simplify testing." | B：可接受 seam 的工业范本 |
| A25 | [time-machine · Comparison](https://time-machine.readthedocs.io/en/latest/comparison.html)（工具文档） | mock 时间"only affects the import location the mock targets"，跨层即脆弱 | A 的局限：跨模块时需 B |
| A26 | [Kent Beck · Test Desiderata](https://kentbeck.github.io/TestDesiderata/)（工程博客） | "Structure-insensitive — tests should not change their result if the structure … changes." | 约束：seam 不得让测试绑定实现细节 |

**裁定（用户 2026-11-24 确认；下列为约束条款）**：默认 **A**（monkeypatch / freezegun / time-machine / fake transport 在测试侧先做）；仅当满足下列**全部**条件才升 **B**：① 该依赖有真实生产语义（Clock / RNG seed / WS-Redis 端口），默认仍走真实实现；② 测试侧替换会跨模块、跨 import 位置失效（A25）；③ 改动 ≤ 接口参数注入，不新增纯测试开关、不为 mock 造 wrapper、不重排架构（A19/A26）；④ 单列 U 项 + T1 复审。反 C，直接引 A19。

### 9.1.3 U-P060-6 分支覆盖 → 已裁定 A（只做诊断快照，不做门禁）

| ID | 锚点（类型） | 核心主张 | 倾向 |
|---|---|---|---|
| A27 | [coverage.py · Branch coverage](https://coverage.readthedocs.io/en/latest/branch.html)（官方文档） | 统计每个分支去向并标 `partial branch`；`while True:` / `if 0:` 属结构性 partial，工具**自动识别不标记**；生成器表达式与条件循环（如 `while i < N:`）才需 `# pragma: no branch`（Step 2 修正） | A（需配套误报处理） |
| A28 | [pytest-cov · 配置项](https://pytest-cov.readthedocs.io/en/latest/config.html)（工具文档） | `--cov-branch` 开启分支；**命令行选项会覆盖 `.coveragerc`** | A（落地须独立命令） |
| A29 | [SO #8229236](https://stackoverflow.com/questions/8229236)（高票问答） | 行覆盖只看语句是否执行；分支覆盖检查条件真假两侧；100% 行覆盖仍可漏分支 | **A 的核心论据** |
| A30 | [Google · Code Coverage Best Practices (2020)](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html)（同 A5） | 无「理想覆盖率数字」；"stay away from broad top-down mandates" | A / 反 C |
| A31 | [JaCoCo · Coverage counters](https://www.jacoco.org/jacoco/trunk/doc/counters.html)（工具文档） | 分支覆盖统计 if/switch；异常处理不计为分支 | A（口径参照） |
| A32 | [SonarQube · Metrics 定义](https://docs.sonarsource.com/sonarqube-server/2025.1/user-guide/code-metrics/metrics-definition/)（工具文档） | Coverage = 行覆盖 + 条件覆盖混合；质量门只卡"New code ≥80%" | A / 反 C（门禁只对新代码） |
| A33 | [nyc/Istanbul](https://github.com/istanbuljs/nyc)（工具文档） | 分支/行/函数低于 80% 即失败 | 反 C 的成本参照（本项目不设硬门禁） |
| A34 | [Inozemtseva & Holmes, ICSE 2014](https://www.cs.ubc.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf)（T1 论文） | "stronger forms of coverage do not provide greater insight into the effectiveness of the suite… should not be used as a quality target." | A / 反 C |
| A35 | [MC/DC（DO-178C / ISO 26262）](https://en.wikipedia.org/wiki/Modified_condition/decision_coverage)（标准） | 安全关键软件要求 100% MC/DC | 仅作「分支覆盖的上界用途」，本项目不适用 |
| A36 | [pip · pyproject.toml](https://github.com/pypa/pip/blob/main/pyproject.toml)（真实项目） | `[tool.coverage.run] branch = true`，无 `fail_under` | **A 的工业先例** |
| A37 | [pydantic · pyproject.toml](https://github.com/pydantic/pydantic/blob/main/pyproject.toml)（真实项目） | 同样 `branch = true` | **A** |
| A38 | [requests · .coveragerc](https://github.com/psf/requests/.coveragerc)（**反例/B 型**） | 仅 `omit`，未启用 branch | B 的存在证明（非少数派） |

**裁定（用户 2026-11-24 确认；下列 4 条为落地规则）**：A，并限定 4 条落地规则：① **独立命令 / 独立 job** 跑 `--cov-branch`，不写 `addopts`（A28：会覆盖 `.coveragerc`）；② 产物为 **informational artifact**（JSON 入构建存档 + 趋势），不 blocking；③ 误报处理：`while True:` 类结构性 partial 无需处理；生成器表达式 / 条件循环用 `# pragma: no branch`；若配置 `[report] partial_branches` 必须同时保留 `pragma: no branch` 正则，否则原 pragma 失效（A27，Step 2 修正 F-1）；④ 未来若设硬门禁，只对**行覆盖 + 新增代码（diff）**，参照 Sonar 的 80% 新增代码口径（A32），不做全仓阈值（A30/A34）。

---

## 10. 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 补测退化为行为锁定 | 中 | 高 | S2 oracle 阶梯；golden 不得唯一；复审抽查断言 |
| 覆盖率高但断言弱 | 中 | 高 | A4/A5；diff coverage + 断言审计（删断言应红） |
| 全量运行时间膨胀 | 中 | 中 | unit 内存化；integration 复用场景；I10 预算 |
| 生产 seam 改动引入回归 | 低 | 高 | U-P060-5 默认 A；仅 §9.1.2 白名单（Clock/RNG/Transport/Humble Object）+ T1 复审 |
| 死模块浪费预算 | 高 | 中 | S10 分类先行；B4 显式清单 |
| 覆盖率口径漂移（包范围/命令不同） | 中 | 中 | S8 固定命令；JSON 快照入提交说明 |
| 未知：覆盖率下 flaky | 中 | 中 | 3 次重复（I7）；`--lf` 定位 |
| 未知：Redis 环境差异 | 中 | 中 | 有 Redis 真跑、无 Redis 协议 fake；skip 显式标注 |

---

## 11. 可重放命令

```powershell
$env:MPLBACKEND = "Agg"

# 全量
.venv\Scripts\python -m pytest tests/ -q

# 既有门禁
.venv\Scripts\python -m pytest tests/ -q -k golden
.venv\Scripts\python -m pytest tests/ -q -k p059

# 覆盖率 A（生产四包）
.venv\Scripts\python -m pytest tests/ -q --cov=core --cov=live --cov=services --cov=strategies `
  --cov-report=json:cov_prod.json --cov-report=term

# 覆盖率 B（filter+agents）
.venv\Scripts\python -m pytest tests/ -q --cov=filter --cov=agents `
  --cov-report=json:cov_ext.json --cov-report=term

# 场景排查
.venv\Scripts\python scripts/verify_scenario.py --list
.venv\Scripts\python scripts/verify_scenario.py --scenario S09 --json
```

> 覆盖率 JSON 为本地取证，不入仓（`cov_*.json` 应加入忽略或输出到 `%TEMP%`）。

---

## 12. Step 2 复审输入（reviewer ≠ 作者）

> **复审已完成（2026-11-24，PASS）**：执行记录与发现清单见 [REVIEW_p060_step2](REVIEW_p060_step2.md)；下列 7 项输入全部核查完毕，F-1/F-3/F-4/F-7 修订已落入本文。

1. **E1 重放**：全量 1502+1；覆盖率 A 85.80% / B 44.07%（各 3 分钟量级）；`-k p059` 63；golden 22。
2. **静态映射复核**：11 个零引用模块逐一核对「生产调用方」与「间接覆盖」（注意相对导入与 app 挂载）。
3. **缺口定性复核**：G-P060-1..12 的严重度与层归属；确认无与 P-059 重复计数。
4. **外部锚点复核**：A1-A5 链接/DOI 可达性；A9 沿用 P-059 已核验结论；**§9.1 的 A10-A38 抽检 8 条**（建议优先抽官方规范/政策/工具文档各 2 条，反向证据 A15/A16/A19/A38 全核）。
5. **裁定复核**：U-P060-4 的「独立 commit」是否与「当批修」冲突；U-P060-5 白名单四条准入是否可执行；U-P060-6 的 `--cov-branch` 独立命令是否与 I10 300s 预算相容。
6. **范围守卫**：本调研零代码变更；不触碰 `core/` / `tests/` / golden / lock。
7. **门禁算术**：1503 collect + 预计新增用例 = 终态 collect；覆盖率目标按 B1/B2 估算复核。

---

## 13. 结论

1. **能力已有、层次缺失**：P-059 的场景库/trace/CLI 足以支撑集成与全量层；缺的是 unit 层规则与模块矩阵。
2. **覆盖现状两极**：生产四包 85.80% 良好，但 filter/agents 44.07%、`market_gateway` 0%、`rebalance` 34.6%、`factor` 64.7% 是明确短板。
3. **最大风险不是覆盖率，而是 oracle 质量**：golden 只能防回归；计算正确性需闭式/参考实现/不变量（A2/A3/A9）。
4. **推荐 M-A**：三批（B1 core 单元 / B2 services 集成 / B3-B4 全量与遗留），覆盖率仅诊断+棘轮。
5. **下一步**：U-P060-1..6 已全部闭合（4/5/6 的证据与约束条款见 §9.1，A10-A38）→ **Step 2 异构复审** → Step 3 DESIGN 定稿测试清单与门禁。
