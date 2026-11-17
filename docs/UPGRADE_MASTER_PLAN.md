# 升级总纲：回测框架 → 回测/实盘一体化量化平台

> **文档定位**: 跨批次升级总纲（pre-batch master plan），**不是**单个 SPEC 批次。每个子项目按 `F:\Spec_Workflow\SPEC_PROCESS.md` 十步流程独立立项（P-042 起），本总纲提供架构约束、模块边界、批次序列与验收口径。
> **日期**: 2026-11-17 · **基线**: 初稿 HEAD `646f40e`（P-041 关闭后）· **架构权威**: [ARCHITECTURE.md](ARCHITECTURE.md) · **独立复审**: §10（复审 + 盲区扫描，2026-11-17）
> **调研方式**: 4 个 subagent 并行深入调研（内部扩展点盘点 + vectorbt 择时/组合优化 + QMT/CTP/FastAPI 实时架构 + 风险/舆情/策略生命周期），结论与来源见 §8。
> **取代关系**: 本总纲整合并取代 `BACKTEST_ENGINE_UPGRADE_PLAN.md` / `architecture_upgrade_plan.md` / `INTEGRATION_PROPOSAL.md` 三份旧提案（保留为历史存档）。

---

## 0. 五大架构原则与机械保障

| 原则 | 含义 | 机械保障（可审计） |
|------|------|--------------------|
| **高内聚** | 每个模块单一职责，纯计算与 I/O 分离 | 计算核为纯函数（无 I/O、无全局态）；I/O 集中在适配器层；模块行数/职责纳入 ARCHITECTURE 矩阵 |
| **低耦合** | 依赖单向、面向 Protocol 编程 | 依赖方向 `services → live → strategies → core` 与 `services → strategies/core`（完整边集见 §2.1），`core` 零上行依赖；跨层只经 `core/interfaces.py` Protocol；引入 `import-linter` 契约门禁 |
| **高性能** | 向量化 + JIT + 异步 I/O + 进程隔离 | 重计算走 NumPy/`@njit` 内核（沿用 V3）；实时路径事件循环只做「解析+入队」，重计算独立进程；orjson/msgpack 序列化 |
| **可追溯** | 功能模块 ↔ SPEC 批次 ↔ 代码 ↔ 版本 | 插件注册表（`core/registry.py` + `core/engine_plugins.py`）+ 策略注册表（ID+语义化版本+参数快照+代码 hash）；每模块绑定 P-0XX 批次与 manifest |
| **可单独验证审计** | 任一计算结果可独立复算、对账 | 纯函数核 + golden 基线（`tests/golden/`）+ 不变量（`invariants.py`）+ run manifest（`manifest.py`）+ 差分报告（`change_report.py`）；实盘 event sourcing append-only 账本 + 幂等 order_id + 盘后对账 |

> **铁律（沿用 ADD）**: 测试通过 ≠ 设计落地。每个新模块必须有「独立可重放的验证出口」（E1 命令 / E2 探针 / golden），不允许仅以「跑通」代替正确性。

---

## 1. 现状盘点

### 1.1 分层架构现状（四层，详见 ARCHITECTURE.md §二）

- **APPLICATION**: `cli.py`（5 子命令）+ `web/streamlit_app/`（5 页面）+ `web/server.py`（**仅静态文件服务器，非 FastAPI**）。
- **ANALYTICS & AGENTS**: `agents/`（13 模块：`agent_framework` 基类 + 4 Guru + 6 角色 ResearchTeam + 分层贝叶斯 + 情绪框架 + 多策略引擎 + 策略分配器 + 风格漂移 + 风格画像 + 风格反思 + 自动参数优化 + 自适应 + 假设监控）；Walk-Forward；Brinson 归因。
- **CORE ENGINE**: V2 事件驱动主引擎（DI + 插拔 + T+1 + 待执行订单 + 止损/盯市）；V3 向量化预筛选（`@njit`，5000股×2500天 ~0.006s）；Factor Pipeline；**4 优化器（EqualW/MinVar/MVO/RiskPar）**；Execution（VWAP/TWAP/Close）；**五维风控（基本面/行业/宏观/资金流/情绪）**；Guard Pipeline（**6 类**：单票上限/冷却/回撤/白名单/换手/最小现金）；Tracker；目标持仓计算（`target_positions.py`）；Plugin Registry（`registry.py` + `engine_plugins.py` 集成层）；EventLog（JSONL+环形缓冲+订阅）；**Live Bridge（骨架）**。
- **DATA**: DataManager（批量 pkl 懒加载）+ Data V3（NumPy）+ Factor_DB（Parquet+JSON 元数据）+ Stock Filter（10 种过滤器 + 可交易性掩码）。

### 1.2 能力矩阵：7 大目标 × 现状

| # | 目标能力 | 现状 | 现有资产（文件） | 核心缺口 |
|---|----------|------|------------------|----------|
| 1 | 持仓风险监控 + 实时数据 + 外部舆情 → 仓位决策 | **部分** | `risk_monitor.py`（五维+综合评分+LLM）、`risk_manager.py`（止损/盯市）、`guard_pipeline.py`、`agents/sentiment_framework.py`、`global_contagion.py`（CoVaR） | 风控是**回测内日频**，无盘中实时；舆情框架无**外部数据接入**；风险信号未闭环到**目标仓位调整** |
| 2 | 组合优化 | **部分（强）** | `portfolio.py`（EqualW/MinVar/MVO/RiskPar + 协方差估计 sample/ledoit_wolf/ewma，L26-30 + `round_lot_optimize` L394）、`target_positions.py`（整手/清仓项）、cvxpy 已在依赖 | 缺 Black-Litterman/HRP/最大夏普；缺**换手/行业/跟踪误差约束的优化器内联合建模**（整手取整已存在，见 `round_lot_optimize`/`build_target_positions`） |
| 3 | 资金仓位管理 | **部分** | `tracker.py`（持仓/现金）、`guard_pipeline.py`（仓位限）、`rebalance.py`、`pending.py`、`target_positions.py`（权重→目标数量） | 缺 **vol-targeting / 分数凯利 / 风险预算 / 金字塔加减仓**等科学仓位方法；缺统一 Sizing 层 |
| 4 | 量化择时（对标 vectorbt） | **部分** | `engine_v3_vector.py:78-153`（信号→目标仓位内核）、`execution_policy.py`（SignalTranslator）、Factor Pipeline | 缺 **entry/exit 信号掩码 + 交叉检测 + 冲突仲裁**；缺**逐持仓止损止盈状态机**；缺 size_type/目标→信号转换 |
| 5 | 策略注入与全生命周期管理 | **部分** | `core/registry.py`（PluginEntry：name/factory/config_schema/metadata）+ `engine_plugins.py`（集成插件）、`agents/multi_strategy_engine.py`、`strategy_allocator.py`、`auto_parameter_optimizer.py`、`style_drift_analysis.py`、`walk_forward_engine.py`、`attribution.py` | 缺**统一策略接口 + 模板库**（网格/趋势/截面多空/月差）；缺**版本化注册→晋级门→实盘监控→regime 自适应→退役**流水线；缺**多策略共享账户的资金分配/虚拟子账户** |
| 6 | QMT/CTP 柜台对接 + 微服务 | **骨架** | `live_bridge.py`：`LiveTradingBridge` ABC L69-128（place_intents/cancel_orders/sync_positions/query_order_status）、`LiveOrder` L46、`MockLiveBridge` L144-242，已接 `OrderIntent` | 缺 **QMT/CTP 具体子类**；缺异步事件驱动适配、断线重连、对账、公司行为/交易日历、网关事前风控；缺微服务拆分 |
| 7 | FastAPI + WebSocket 毫秒级推送 | **空白** | 无（全仓 0 处 FastAPI/WebSocket/uvicorn）；`web/server.py` 仅静态服务 | 全部新建：行情网关、消息总线、WS 扇出、snapshot+delta 重连 |

### 1.3 关键扩展点（已验证锚点）

| 扩展点 | 锚点 | 承载能力 |
|--------|------|----------|
| `IDataManager` 数据契约 | `core/interfaces.py:25-95` | 实时/流式数据适配器对齐此契约（F1/F7） |
| `IOptimizer` / `IExecutionSimulator` | `core/interfaces.py:179-260` | 新优化器/执行适配器插拔（F2/F4） |
| V2 主循环 | `core/engine_v2.py:341-441` | 风控/仓位/再平衡联动挂钩点（F1/F3） |
| V3 信号→仓位内核 | `core/engine_v3_vector.py:78-153` | 择时/仓位缩放向量化（F4） |
| 协方差估计器注册表 | `core/portfolio.py:25-30` | 风险模型复用（F2） |
| `LiveTradingBridge` ABC | `core/live_bridge.py:69-128` | **QMT/CTP 子类直接实现此接口**（F6） |
| Plugin Registry | `core/registry.py`（`PluginEntry`）+ `core/engine_plugins.py`（EventLog/Guard/Registry 集成） | 优化器/触发器/Guard 注册与元数据（F5；注册为显式调用，**无自动注册装饰器**） |
| 目标持仓纯计算层 | `core/target_positions.py`（`build_target_positions`） | 目标权重→目标数量（整手/清空项），F3/F4 直接复用 |
| 数据端口（已定义未接线） | `core/data_provider.py`（`DataProvider` Protocol + `PklDataProvider`）+ `core/universe_data.py` | P-042 数据契约收敛对象（F1/F7） |
| EventLog（JSONL+订阅） | `core/event_log.py` | 升级为统一事件总线（F6/F7，承接 U-P025-1） |
| 审计基建 | `invariants.py`/`manifest.py`/`change_report.py`/`validation.py`/`metrics.py` + `tests/golden/` | 所有新模块的独立验证出口（横切） |

### 1.4 与升级相关的剩余待办（PROGRESS §1.4）

| 待办 | 级别 | 与升级的关系 |
|------|------|--------------|
| **U-P031-1** 中性策略负持仓账目（保证金/借券/负市值盯市） | P2 | **F5 截面多空 / F4 做空择时的前置**；需改 `tracker.py`/`execution.py`，波及 V2/V3/golden |
| **U-P025-1** EventLog 接入引擎作为统一事件通道 | P3 | **F6/F7 事件总线的前置** |
| **U-P005-1** Factor_DB DuckDB 迁移 | P3 | F1 舆情因子 / F5 策略参数存储的查询层 |
| `data.py` vs `data_v3.py` 双数据加载器 | 技术债 | **F1/F7 流式数据契约统一的前置** |
| `config.py` vs `config_v2.py` 双配置 | 技术债 | F5 策略参数 schema 可借 Pydantic V2 |
| Live Bridge 骨架 | 缺口 | F6 直接承接 |
| U-P031-2 BUY 侧现金夹紧 / U-P031-3 short 语义 | P3 | F3 资金管理 / F5 多空语义需先裁决 |

### 1.5 实盘化的最大架构障碍

1. **数据是批量 pkl/NumPy 矩阵，非流式**：`IDataManager` 面向「整段历史矩阵」，实盘需「增量 tick/bar + 最新快照」契约 → 需新增流式适配器而非改坏回测契约。
2. **引擎是逐日 bar 循环，非事件 tick**：V2 主循环按 `trade_dates` 推进；实盘需事件驱动（on_tick/on_bar）→ 用**适配器模式**让同一策略接口在「历史回放」与「实时事件」两种驱动下运行，而非重写引擎。
3. **同步阻塞 I/O**：回测无网络；实盘柜台回调在独立线程、WS 需异步 → I/O 隔离到 `live/` 与 `services/`，`core/` 保持纯计算。
4. **做空账目缺失（U-P031-1）**：截面多空/月差套利依赖负持仓与保证金盯市。
5. **QMT 仅 Windows + 客户端依赖**：实盘网关进程须跑在 Windows 宿主机，与 Linux 服务层跨进程通信；`xtquant` 为 Windows-only wheel，须走可选 extra + 独立 venv，主包与 Linux CI 不依赖。
6. **实盘安全/合规空白**：全仓无 kill switch、网关事前风控、鉴权、程序化交易报告（§3.0 补）。
7. **交易日历/公司行为缺失**：日期来自数据文件，无交易所日历/时段/时区；实盘分红送转/配股/退市未纳入账本（F6 补）。
8. **实时数据质量无定义**：stale/乱序/缺口/源切换未建模（F1/F7 补）。

---

## 2. 目标架构

### 2.1 分层目标架构（回测/实盘一体化）

```
┌────────────────────────────────────────────────────────────────────────────┐
│ SERVICES 层 (services/，新建)                                                │
│  FastAPI + uvicorn(uvloop)  ·  WebSocket Hub(snapshot+delta/seq/心跳)        │
│  REST: 策略管理/回测触发/风险查询/对账报表（管理面可写） · WS: 行情/账目只读扇出    │
│  （不含下单/撤单等交易执行逻辑）                                              │
├────────────────────────────────────────────────────────────────────────────┤
│ LIVE 层 (live/，新建)                                                        │
│  行情网关(xtdata/CTP MdApi)  ·  交易网关(xttrader/CTP TdApi，每账户单写者)    │
│  事件总线(Redis Streams)  ·  账本(event sourcing)  ·  对账  ·  流式数据适配器 │
├────────────────────────────────────────────────────────────────────────────┤
│ CORE 层 (core/，扩展；纯计算，零上行依赖)                                     │
│  Strategy Protocol  ·  Timing(信号原语)  ·  Stops(止损状态机)  ·  Sizing(仓位)│
│  RiskOverlay(风险→目标权重)  ·  Optimizer(扩展 BL/HRP/约束)  ·  Sentiment 因子│
│  ── 既有 ──  V2/V3 引擎  ·  Factor  ·  Tracker  ·  Guard  ·  RiskMonitor     │
│             Plugin Registry  ·  EventLog  ·  Invariants/Manifest/ChangeReport│
├────────────────────────────────────────────────────────────────────────────┤
│ STRATEGIES 层 (strategies/，新建；实现 Strategy Protocol)                     │
│  网格  ·  趋势跟踪  ·  时序动量  ·  截面多空  ·  月差套利  ·  均值回归         │
│  参数 schema + 版本号 + 状态可序列化                                          │
├────────────────────────────────────────────────────────────────────────────┤
│ DATA 层 (统一契约)                                                           │
│  IDataManager(回测批量)  ⇄  IStreamingFeed(实盘增量)  ·  Factor_DB  ·  Filter │
└────────────────────────────────────────────────────────────────────────────┘
        依赖方向: services → live → strategies → core；services → strategies/core；core 不依赖任何上层；strategies 不依赖 live/services
```

### 2.2 核心抽象：统一策略接口 + 双适配器

**策略只产信号/目标权重，不碰 I/O**（高内聚）；回测与实盘共用同一策略代码，仅数据源与执行适配器不同（低耦合）：

```python
# core/strategy.py（新建，Protocol）
class Strategy(Protocol):
    meta: StrategyMeta                      # id + 语义化版本 + 参数 schema + 代码 hash
    def generate_signals(self, data: MarketView, state: StrategyState) -> TargetWeights: ...
    # 纯函数式：输入行情视图+可序列化状态 → 目标权重；无副作用、可独立复算

# 驱动适配器（live/ 与 core/ 各一）
class BacktestAdapter:   # 历史矩阵回放 + ExecutionSimulator 模拟撮合（复用 V2/V3）
class LiveAdapter:       # 实时事件(on_tick/on_bar) + LiveTradingBridge 真实下单
# 二者实现同一 EventBus/Broker 接口；策略代码零改动切换回测/paper/实盘
```

> 参考 vnpy 事件引擎 + CtaTemplate 回测/实盘双模（§8 来源）。**目标权重 → 订单**经 `execution_policy.SignalTranslator`（已有）+ 新增「目标→信号转换」使止损可叠加在目标权重策略上（vectorbt `order_mode` 范式）。

### 2.3 数据流：回测路径 vs 实盘路径

```
回测: 历史pkl → IDataManager → Strategy.generate_signals → RiskOverlay → Optimizer
      → SignalTranslator → ExecutionSimulator → Tracker → Invariants/Manifest → 报告

实盘: xtdata/CTP → 行情网关 → Redis Streams → 流式适配器(IStreamingFeed)
      → Strategy.generate_signals → RiskOverlay → 安全闸门(事前风控/kill switch) → 交易网关(单写者)
      → 柜台 → 成交回报 → 账本(event sourcing) → 对账 → WS Hub → 前端
```

---

## 3. 七大功能 → 模块映射

> 每个模块给出：边界 / 接口 / 复用 / 依赖 / 独立验证审计出口。新模块均须注册到 Plugin Registry 并绑定 SPEC 批次。

### 3.0 实盘安全与合规基线（P0，所有实盘批次的前置）

> 以下为**硬约束**，不是可选增强。任何 `live/` 代码合入前，对应条目必须已有机械验证出口；对应批次为 **P-052 实盘安全闸门**（§5）。

| # | 约束 | 落地要求 | 验证出口 |
|---|------|----------|----------|
| S1 | **平台级 kill switch** | 全局/账户/策略三级急停：停止新开仓、可选一键撤单与平仓；状态持久化，重启后保持 | 状态机单测 + 断线/崩溃恢复演练 |
| S2 | **网关事前风控** | 每笔订单发柜台前校验：单笔金额上限、价格带（复用 `filter/limit_rules.py` 涨跌停价）、单票/行业暴露、日下单笔数与撤单率上限、自成交拦截 | 拒绝路径单测 + 审计日志字段完整 |
| S3 | **账户级熔断** | 日亏损/回撤/连续拒单超阈值 → 自动降级（只平不开）并告警 | 阈值触发演练 + 告警送达 |
| S4 | **合规报告** | 程序化交易报告（账户/策略/频率）、高频交易额外报告、异常交易监控（瞬时申报速率/频繁撤单/自成交）；**具体阈值与报备主体以交易所细则为准，须在 P-052 RESEARCH 阶段取证** | 报告字段清单 + 台账 |
| S5 | **鉴权与传输安全** | REST/WS 鉴权（API Key/JWT）、TLS 终止、最小权限、CORS 白名单；密钥经环境/密钥库注入，禁止入库 | 未授权 401/403 测试 |
| S6 | **审计留痕** | 意图/风控决策/下单/回报/撤单/对账全链路 append-only，含操作者与时间源 | 事件可重放 + 字段完整性测试 |
| S7 | **故障处置** | 断线（行情/交易）、拒单、部分成交、柜台重启的处置策略与人工接管流程（runbook） | 故障注入演练记录 |

> **合规边界（待用户裁决，见 §7.9）**: 本框架定位为「自用交易工具」还是「对外提供服务」，将决定报备主体、投资者适当性与网络安全等级保护要求。

### F1 持仓风险监控 + 实时数据 + 外部舆情 → 仓位决策
- **新模块**: `core/risk_overlay.py`（风险→目标权重 overlay）、`core/sentiment_feed.py`（舆情因子化）、`live/streaming_feed.py`（实时数据适配）。
- **复用**: `risk_monitor.py`（五维评分）、`global_contagion.py`（CoVaR）、`agents/sentiment_framework.py`（打分）、`guard_pipeline.py`（事前闸门）。
- **范式**: **vol-targeting × 回撤闸门 × 暴露上限**三层叠加，输出**目标权重**而非直接下单（`w = min(1, σ目标/σ实测)`；DD>8% 减半、>12% 转防御；单票/行业/流动性上限；负面舆情→降权/黑名单）。
- **舆情落地**: 先**巨潮公告 + Tushare 新闻/研报**（合规、PIT 易），词典→中文 FinBERT→LLM 事件抽取；按股×日聚合，**用发布时间戳滞后到次日开盘**防前视；含退市股防幸存者偏差。社交（股吧/雪球）后置（合规/噪声）。
- **A股约束**: T+1 下盘中以「监控+次日决策」为主，当日仅可卖存量。
- **数据质量闸门**: 行情 seq 单调、时间戳滞后阈值、缺口检测、停牌标记、主备源切换；异常数据不得进入信号计算（详见 F7 与 §3.0 S6）。
- **模型可审计**: FinBERT/LLM 版本固定并缓存推理结果，事件抽取输出带模型版本与 prompt hash。
- **验证审计**: 风险指标纯函数 + golden；舆情因子 PIT 不变量（`invariants.py` 扩展）；overlay 输出权重可独立复算。

### F2 组合优化
- **扩展**: `core/portfolio.py` 增 Black-Litterman / HRP / 最大夏普 / 约束优化（换手 L1、个股/行业上限、跟踪误差）。
- **选型**: **PyPortfolioOpt**（MIT、pandas 原生、MVO/BL/HRP/ERC/收缩齐全，核心依赖 cvxpy+sklearn+scipy 已在栈）；自定义约束→cvxpy；整手/基数→`scipy.optimize.milp`（HiGHS，零新增依赖）。riskfolio-lib 依赖重且 pin 死，仅作接口参考。
- **复用**: 协方差估计器注册表（`portfolio.py:25-30`）、`IOptimizer` Protocol、Plugin Registry。
- **A股适配**: T+1/涨跌停/停牌属**执行层**而非优化器——优化在可交易域上进行，停牌股冻结现权重，整手事后取整。
- **验证审计**: 优化器纯函数 + 权重约束不变量（和为1/上限/换手）+ golden；与 PyPortfolioOpt 参考解对拍。

### F3 资金仓位管理
- **新模块**: `core/sizing.py`（统一 Sizing 层）。
- **方法**: 分数凯利（1/4~1/2 Kelly）、波动率目标仓位（风险预算/(k·ATR)）、风险预算（边际风险贡献分配）、金字塔加减仓（**只浮盈加仓且递减，禁摊亏**）、max/min_size、granularity=100。
- **复用**: `tracker.py`（现金/持仓）、`guard_pipeline.py`（仓位限）、`pending.py`、`target_positions.py`（sizing 输出的目标权重统一经 `build_target_positions` 落到整手与清仓项）。
- **前置**: U-P031-2（BUY 侧现金夹紧）需先裁决。
- **验证审计**: sizing 纯函数 + 现金守恒不变量 + golden；T+1 持仓龄约束单测。

### F4 量化择时（对标 vectorbt）
- **新模块**: `core/timing.py`（信号原语）、`core/stops.py`（止损止盈状态机）。
- **需补原语**（§8 vectorbt 调研）:
  1. **信号层**: long/short entry/exit 四掩码 + 交叉检测（crossed_above/below）+ 冲突仲裁 + accumulate。
  2. **订单层**: size_type 枚举（TargetPercent/ValuePercent 重点）+ 目标→信号转换（止损叠加目标权重）+ 先卖后买 call_seq + 共享现金账户。
  3. **止损层**: 逐持仓状态机（入场价/最高水位）+ OHLC bar 内触发顺序（open→盘中→close，同段 SL 优先）+ 移动/时间止损 + 分批退出 + 动态调整钩子（保本/ATR）。
  4. **缩放层**: 金字塔/部分减仓 + granularity=100。
- **复用**: V3 内核（`engine_v3_vector.py:78-153`）向量化、`execution_policy.SignalTranslator`、`target_positions.build_target_positions`（目标→数量）、`filter/limit_rules.build_limit_prices`（涨跌停价，实盘价格带同源）、可交易性掩码（`filter/`）。
- **A股执行**: 涨停禁买/跌停禁卖/停牌/ST 掩码；**T+1 按笔记录持仓龄**；nextopen 撮合防前视；止损按次日开盘/VWAP 成交价而非触发价。
- **验证审计**: 信号/止损纯函数 + 与 vectorbt 隔离 venv（`.venv-vbt`，固定 vectorbt 版本并写入验收记录）对拍（沿用 P-015 方法论，`scripts/external_benchmark/`）+ golden。

### F5 策略注入与全生命周期管理
- **新模块**: `core/strategy.py`（Strategy Protocol + StrategyMeta）、`strategies/`（模板库）、`core/strategy_registry.py`（版本化注册）、`core/lifecycle.py`（晋级门/监控/退役）。
- **模板**: 网格（ATR 间距，震荡 ETF）、趋势跟踪/时序动量（N日突破/均线符号 + vol-target + ATR 跟踪）、截面多空（因子分位 + 股指期货对冲，**依赖 U-P031-1**）、月差套利（近远月价差 z-score，±2σ进/0.5σ出/3.5σ止损，期货/ETF）、均值回归（超跌 z-score + 时间止损）。
- **生命周期流水线**: 注册表（ID+语义化版本+参数快照+代码hash）→ **晋级门**（walk-forward 回测→paper≥1月→小资金灰度→全量，各设准入/退出/kill criteria）→ 实盘监控（滑点vs假设/成交率/滚动IC衰减/成本漂移）→ 月度归因（alpha/beta/行业/成本/择时，复用 `attribution.py`）→ **regime 识别**（HMM 2-4态，BIC选态+样本外验证，**按态切换参数集而非在线学习**）→ 退役（IC 持续低于阈值/回撤超限→降paper→归档可复现）。
- **复用**: `core/registry.py` + `engine_plugins.py`、`multi_strategy_engine.py`、`strategy_allocator.py`、`auto_parameter_optimizer.py`、`style_drift_analysis.py`、`walk_forward_engine.py`。
- **多策略资金分配**: 共享账户下每策略维护**虚拟子账户**（虚拟现金/持仓），按 allocator 权重预留资金；下单前校验资金占用，冲突按优先级+公平队列仲裁；策略退役时虚拟账户清零并归档。
- **验证审计**: 策略状态可序列化→任意时点可重放复算；注册表代码hash+参数快照→可追溯；晋级门判据机械化。

### F6 交易柜台对接 + 微服务
- **新模块**: `live/qmt_bridge.py`、`live/ctp_bridge.py`（实现 `LiveTradingBridge` ABC）、`live/event_bus.py`、`live/ledger.py`、`live/reconcile.py`、`live/session_calendar.py`（交易日历/时段/时区）、`live/corporate_actions.py`（分红/送转/配股/退市）、`live/execution_algo.py`（TWAP/POV/冰山）。
- **QMT 调用链**: `XtQuantTrader(path, session_id)`→`register_callback`→`start`→`connect`→`subscribe(account)`→`order_stock`→`cancel_order_stock`→`query_stock_asset/orders/trades/positions`→`run_forever`。回调（独立线程）：`on_stock_order/on_stock_trade/on_order_error/on_disconnected`。**回调内禁同步查询**（卡死），持仓同步=主推驱动+定时对账。**仅 Windows + 本机 QMT 客户端（miniQMT）**。
- **CTP 边界**: **只覆盖期货/期货期权**（股票期权另有柜台）；**A股现货/两融不走 CTP**（走 QMT/恒生/华锐）。MdApi/TdApi 分离，重连由 C++ API 内部完成。封装选 vnpy_ctp / openctp（含 TTS 仿真）。
- **微服务边界**: 行情服务 / 策略引擎（只产信号）/ 风控服务（事前同步闸门）/ **交易网关（唯一对接柜台、每账户单写者）** / 持仓账户服务（成交驱动账本+对账）/ API+WS（只读扇出）。事件用 Redis Streams/NATS；下单路径风控用 gRPC 或进程内调用（路径尽量短）。
- **公司行为与交易日历**: 分红/送转/配股/退市由柜台回报或数据源事件驱动，账本记 `corporate_action` 事件；对账时持仓数量差异须先归因公司行为再判异常。`session_calendar` 提供交易所日历、集合竞价/连续竞价/收盘竞价时段、`Asia/Shanghai` 时区与期货夜盘状态机。
- **依赖与部署**: `xtquant`/`vnpy_ctp` 为可选 extra（`[qmt]`/`[ctp]`），仅 Windows gateway venv 安装并独立 pin Python（以 wheel 支持范围为准）；主包与 Linux CI 不依赖。QMT `session_id` 须单实例唯一，禁止重复登录；miniQMT 客户端升级后须跑回归。
- **执行算法**: 大单走 `live/execution_algo.py`（TWAP/POV/冰山），参数与回测 `execution.py` 同口径，偏差进 parity 报告。
- **验证审计**: **event sourcing**（意图/确认/成交/撤单/持仓快照/公司行为 append-only，单调 seq+时间戳，更正即新事件，状态由重放导出）；**幂等** client_order_id（UUID，网络调用前生成，网关去重）+ trade_id 去重；**对账**（盘中增量+盘后全量，query 对比本地账本，差异超阈值告警，阈值见 §4）。MockLiveBridge 已有→实盘子类用同一接口测试。

### F7 FastAPI + WebSocket 毫秒级推送
- **新模块**: `services/api.py`（FastAPI）、`services/ws_hub.py`、`services/market_gateway.py`。
- **拓扑**: 行情网关进程（xtdata/CTP）→ **Redis Streams** 总线 → 快照聚合器（Redis 存最新态）→ FastAPI+uvicorn(**uvloop**) 多 worker WS 扇出。
- **背压**: 每连接 bounded asyncio.Queue，满则丢旧 tick/合并（**行情可丢、订单不可丢**）；订单/成交走 Streams 消费组+ack 可靠通道。
- **重连**: snapshot+delta，消息带 seq，断线取快照再按 seq 补增量；ping/pong 心跳+客户端指数退避。
- **延迟现实（必须向用户澄清）**: GIL 下事件循环只做「解析+入队」，重计算独立进程；机内总线亚毫秒~几ms，到浏览器端到端典型 **5–50ms**；**A股 Level-1 快照本身 3s 一笔**，「毫秒级」只优化内部新鲜度，非行情源频率。Python 不适合亚毫秒下单路径。
- **安全**: REST/WS 鉴权（API Key/JWT）+ TLS 终止 + 最小权限 + CORS 白名单；密钥经环境变量/密钥库注入，禁止入库（详见 §3.0 S5）。
- **可观测性**: Prometheus 指标（下单延迟/拒单率/事件积压/WS 连接数/推送延迟分位）+ 结构化日志 + 告警规则；P-054 交付延迟基准报告。
- **多 worker**: 每个 worker 独立订阅 Redis，连接/订阅状态存 Redis，禁止依赖进程内状态。
- **验证审计**: WS 消息 seq 连续性测试；snapshot+delta 重放一致性；未授权 401/403；REST 管理面可写但不含下单/撤单交易逻辑（耦合门禁）。

---

## 4. 横切基建：可追溯 + 可单独验证审计

| 机制 | 现有资产 | 升级扩展 |
|------|----------|----------|
| **纯函数计算核** | V3 `@njit` 内核、metrics/invariants | 所有新模块（timing/stops/sizing/risk_overlay/optimizer）计算核纯函数化，I/O 隔离到适配器 |
| **golden 基线** | `tests/golden/`（**G1-G7 七份 JSON 基线**；`-k golden` 收集 13 项）+ `scripts/record_golden.py` | 新模块各建 golden case；策略状态重放逐字节可重现 |
| **不变量** | `invariants.py`（I1-I7） | 扩展：现金守恒/权重约束/PIT/持仓龄/T+1/seq 连续 |
| **run manifest** | `manifest.py`（git commit/config/数据sha256/环境） | 策略版本+参数快照+代码hash 纳入 manifest |
| **差分审计** | `change_report.py`（六层归因+residual双门） | 回测↔paper↔实盘同策略差分对拍；日频 parity 判据：EOD 持仓数量差 **0**（公司行为除外）、目标权重 L1 **≤1e-6**、成交均价差 **≤10bps**、现金差 **≤1 元**（阈值在 P-053 立项时按账户规模校准并写入验收） |
| **事件溯源账本** | `event_log.py`（JSONL+订阅） | 升级为实盘 append-only 账本（U-P025-1）+ 幂等 + 对账 |
| **模块追溯** | `core/registry.py`（PluginEntry）+ `core/engine_plugins.py` | 策略注册表（ID+版本+参数+hash）↔ SPEC 批次 ↔ ARCHITECTURE 矩阵 |
| **外部对拍** | `scripts/external_benchmark/`（vectorbt 隔离 venv `.venv-vbt`） | 择时/优化与 vectorbt/PyPortfolioOpt 参考解对拍（固定对方版本） |
| **安全合规** | 无 | kill switch/网关事前风控/账户熔断/鉴权/审计台账（§3.0 S1-S7）各自建单测与故障注入用例 |

---

## 5. 分阶段路线图（批次序列）

> 每批次按 SPEC_PROCESS 十步（RESEARCH→…→Step10 ADD + 异构终审）。判档：触及 `core/`/`tests/`/新服务 → T1。依赖前置必须先关闭。

| 阶段 | 批次（建议） | 内容 | 前置 | 验收口径 |
|------|--------------|------|------|----------|
| **0 地基** | P-042 数据契约统一 | `IDataManager`/`DataProvider`/`IStreamingFeed` 三契约收敛；`data.py`/`data_v3.py`/`data_provider.py` 归并 | — | golden **默认零重录**（如需重录须显式裁决并记录）；流式适配器契约测试 |
| | P-043 事件总线 | EventLog 接入引擎（U-P025-1）→ 统一事件通道（seq/重放） | P-042 | 事件 seq 连续；订阅/重放测试 |
| | P-044 策略接口抽象 | `core/strategy.py` Protocol + BacktestAdapter | P-042 | 既有策略迁移零行为变更；状态可序列化重放 |
| **1 回测增强** | P-045 择时原语 | timing + stops（F4），复用 `target_positions`/`limit_rules` | P-044 | 与 vectorbt 对拍；止损状态机 golden |
| | P-046 组合优化扩展 | BL/HRP/约束（F2，PyPortfolioOpt） | §7.7 裁决 | 权重约束不变量；参考解对拍 |
| | P-047 仓位管理 | sizing（F3）+ U-P031-2 裁决 | P-044 | 现金守恒；分数凯利/vol-target golden |
| **2 风险、账目与策略** | P-048 风险 overlay | risk_overlay（F1 决策闭环） | P-047 | 风险→权重纯函数 golden |
| | P-049 舆情接入 | sentiment_feed（F1，公告/新闻） | P-042 + §7.5 裁决 | PIT 不变量；因子化可复算 |
| | **P-050 做空账目** | U-P031-1（负持仓/保证金/盯市/强平） | 无代码前置（本批即 U-P031-1 题干） | 多空账目 golden；纯多头既有 golden 不受影响 |
| | P-051 策略模板+生命周期 | `strategies/`（网格/趋势/时序动量/均值回归）+ registry + lifecycle（F5） | P-044/045/047/050 | 晋级门机械化；regime 切换样本外验证 |
| **3 实盘网关** | **P-052 实盘安全闸门** | kill switch/网关事前风控/账户熔断/合规报告/审计（§3.0 S1-S7） | P-043 | S1-S7 每项有机械验证出口；拒绝路径全覆盖 |
| | P-053 QMT 网关 | qmt_bridge + ledger + reconcile + session_calendar + corporate_actions（F6） | P-043/044/050/052 | Mock→实盘同接口；幂等/对账/公司行为测试；paper 跑通 |
| **4 服务层** | P-054 FastAPI+WS | `services/`（F7，含鉴权/TLS/观测） | P-053 + §7.9 | snapshot+delta 重放一致；背压/重连/401 测试 |
| | P-055 微服务拆分 | 进程边界 + Redis Streams + 部署 | P-054 | 依赖方向门禁；端到端延迟基准 |
| **5 高级** | P-056 CTP 期货/月差 | ctp_bridge（F6） | P-050/053 | 期货账目；换月/保证金/限仓 |
| | P-057 regime 自适应深化 | HMM + 参数集切换 | P-051 | 样本外验证；防过拟合 |
| | P-058 截面多空/月差模板 | `strategies/` 扩展（依赖做空与期货账目） | P-050/051/056 | 多空账目 + 期货合约口径对拍 |

> **关键路径**: P-042→043→044→045/046/047→048→050→051→052→053→054→055。做空账目（**P-050**）是截面多空（P-058）/月差（P-056/P-058）的硬前置。
> **编号说明**: 本表为复审后修订顺序（初稿→修订稿映射见 §10.5）；初稿的 P-050 策略模板→P-051、P-051 做空账目→P-050、P-052 QMT→P-053、P-053 FastAPI→P-054、P-054 微服务→P-055、P-055 CTP→P-056、P-056 regime→P-057；新增 P-052（实盘安全闸门）与 P-058（多空/月差模板）。

---

## 6. 架构原则的机械门禁（新增 CI 契约）

| 门禁 | 工具 | 规则 |
|------|------|------|
| 依赖方向 | `import-linter` | **允许边**: `services→live/strategies/core`、`live→strategies/core`、`strategies→core`；**禁止边**: `core→live/services/strategies`、`strategies→live/services`、`live→services`；`services` 禁含交易逻辑 |
| 纯函数核 | AST 扫描 | 计算核模块禁 I/O（open/network/global write） |
| 策略可追溯 | 注册表校验 | 每策略必有 id+版本+参数schema+代码hash |
| 计算可审计 | golden + invariants | 每新模块 ≥1 golden case + 不变量 |
| 实盘幂等 | 账本测试 | 重复 order_id/trade_id 应用为 no-op |
| 安全合规 | 单测 + 故障注入 | §3.0 S1-S7 每项至少 1 个机械用例 |
| 既有门禁 | pytest/mypy/black/AST/uv lock | 沿用（778 passed 基线，只增不减） |
| **门禁落地** | CI / pyproject | mypy 靶加入 `live services strategies`；black 目标同步；新增 CI job 跑 `import-linter`；新增依赖按 extra 分档（`[dev]`：import-linter/PyPortfolioOpt/orjson；`[qmt]`：xtquant；`[ctp]`：vnpy_ctp；FastAPI/uvicorn 视部署进 `[services]`）并 `uv lock`；**仓库当前无 `.pre-commit-config.yaml`，不得假设 pre-commit 存在**；新 job 不得依赖 Windows |

---

## 7. 风险与开放问题（需用户裁决）

1. **QMT 仅 Windows + 客户端依赖**：实盘网关须 Windows 宿主；服务层 Linux 跨进程通信拓扑需确认部署环境。
2. **「毫秒级」预期管理**：A股 Level-1 源 3s 一笔，端到端 5–50ms 是现实上限；是否接受「内部新鲜度毫秒级、行情源 3s」口径？
3. **做空账目（U-P031-1）**：截面多空/月差需负持仓+保证金盯市，波及 V2/V3/golden，是否本升级周期内做？
4. **CTP 范围**：A股现货不走 CTP；是否仅期货/期权子项目用 CTP？股票现货锁定 QMT？
5. **舆情数据合规与成本**：Tushare 积分制付费、社交爬虫合规风险；先公告/新闻是否足够？
6. **数据源统一**：data.py/data_v3.py 收敛可能波及 golden，需重录裁决。
7. **PyPortfolioOpt 新依赖**：引入需 `uv lock` + CI lock-check；是否接受（vs 纯 scipy 自研 HRP 零依赖路线）？
8. **regime 自适应防过拟合**：HMM 按态切换参数集需严格样本外验证，避免数据窥探（沿用 walk-forward purge gap）。
9. **合规定位与报备（S4）**：本框架是自用工具还是对外服务？若涉及程序化交易报告/高频报告，报备主体与账户范围如何界定？API/WS 是否仅内网或本机（决定鉴权与 TLS 强度）？
10. **parity 阈值**：§4 的持仓差 0 / 权重 L1≤1e-6 / 均价≤10bps / 现金≤1 元是否接受？需按账户规模与标的流动性校准。
11. **多策略共享账户**：是否需要虚拟子账户与资金预留？策略冲突仲裁用优先级还是公平队列？
12. **公司行为/交易日历数据源**：分红送转/配股/退市事件与交易所日历取自柜台、Tushare 还是交易所公告？缺失时如何降级与告警？
13. **可观测性栈**：Prometheus+Grafana 全栈，还是最小「结构化日志+邮件/IM 告警」？决定 P-055 部署复杂度。
14. **QMT Python 版本与 extra 隔离**：gateway venv 独立 pin（以 xtquant wheel 支持为准）且可能低于主包 3.12，是否接受？Windows 网关与 Linux 服务的通信方式（REST/gRPC/Redis）需确认。

---

## 8. 调研来源（subagent 联网检索）

**vectorbt 择时 / 组合优化**:
- [vectorbt.pro Signal backtesting](https://vectorbt.pro/features/backtesting/signal-backtesting/) · [Stop loss & take profit](https://vectorbt.pro/features/backtesting/stop-loss-and-take-profit/) · [Portfolio accounting](https://vectorbt.pro/features/backtesting/portfolio-accounting/) · [PFO tutorial](https://vectorbt.pro/tutorials/portfolio-optimization/)
- [vectorbt Portfolio API](https://vectorbt.dev/api/portfolio/base/) · [Signals accessors](https://vectorbt.dev/api/signals/accessors/)
- [PyPortfolioOpt](https://raw.githubusercontent.com/PyPortfolio/PyPortfolioOpt/main/pyproject.toml) · [riskfolio-lib](https://pypi.org/project/riskfolio-lib/) · [skfolio](https://skfolio.org/)
- [Ricequant 优化器约束](https://www.ricequant.com/doc/rqoptimize/api/optimizer) · [HRP/BL/NCO 对比](https://marketmaker.cc/nl/blog/post/portfolio-optimization-algorithms-compared/)

**QMT / CTP / FastAPI 实时架构**:
- [XtQuant 交易模块](https://dict.thinktrader.net/nativeApi/xttrader.html) · [行情模块](http://dict.thinktrader.net/nativeApi/xtdata.html) · [QMT 50ms 主推](http://docs.thinktrader.net/vip/pages/cc95b6/) · [miniQMT 差异](https://miniqmt.com/pages/home.html)
- [openctp CTPAPI](http://openctp.cn/CTPAPI.html) · [VeighNa 接口分类](https://www.vnpy.com/docs/cn/community/info/gateway.html)
- [WebSocket with FastAPI](https://websocket.org/guides/frameworks/fastapi/) · [Redis 低延迟 WS 流](https://zerotwosolutions.com/blogs/real-time-websocket-streaming-with-redis-stack-low-latency-platform) · [Event Sourcing 风控引擎](https://nordvarg.com/blog/event-sourcing-the-risk-engine-a-practical-guide)

**风险 / 舆情 / 策略生命周期**:
- [vol targeting 风险管理](https://docs.skelfresearch.com/sigc/quant-guide/06-risk/) · [Target VaR/CVaR (GARP)](http://garpsalesforcepublic.s3.amazonaws.com/Content__c/a1Z1W000003mRmtUAE/a2r1W0000015Rx0QAE_Whitepaper.TailRisk.Oct19.pdf)
- [A股 T+1/涨跌停可成交性](https://www.zpyztech.com/a-share-t1-limit-up-tradability-constraints-deep-dive/) · [上交所交易规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml)
- [Tushare 新闻/公告/研报](https://tushare.pro/document/1?doc_id=473) · [FinBERT](https://finbert.org/zh) · [LLM+GNN 新闻情绪 A股实证](https://stcn.com/article/detail/2633906.html)
- [策略晋级流水线](https://targethit.ai/learn/discovery-to-production) · [IC衰减与策略退役 (KDD 2026)](https://zenodo.org/records/19425661/files/AQAA_KDD2026_v4.pdf?download=1) · [HMM Regime 自适应](https://www.marketmaker.cc/en/blog/post/regime-detection-hmm-adaptive-trading/) · [Fractional Kelly](https://pruviq.com/blog/risk-management-101/)

---

## 9. 下一步

1. 用户裁决 §7 开放问题（**优先 9-14 新增项**：合规定位、parity 阈值、多策略资金、公司行为/日历数据源、观测栈、QMT Python/extra；以及 1-8 既有项）。
2. 按 §5 修订路线图从 **P-042（数据契约统一）** 起逐批立项，每批走 SPEC_PROCESS 十步 + 异构终审；P-042 立项前先确认 §6「门禁落地」（CI job/extra/uv lock）。
3. 每批完成后回写本总纲 §1.2 能力矩阵与 §5 路线图状态，保持总纲↔批次↔代码可追溯。

---

## 10. 独立复审与盲区扫描记录（2026-11-17）

> **复审对象**: 本文件初稿（commit `646f40e`，306 行）· **复审基座**: DeepSeek-V4.1-Flash
> **RULE-5 披露**: 初稿由 Qwen4-Max 基座生成（上一会话记录），本次复审为 DeepSeek-V4.1-Flash → **异构成立**；复审为只读核验 + 文档修订，不改代码。
> **流程依据**: `F:\Spec_Workflow\SPEC_PROCESS.md`（RULE-1~6 / E1-E5 / ADD 四阶段）

### 10.1 证据矩阵（E1-E5）

| 证据级 | 方法（可重放） | 结果 |
|--------|----------------|------|
| **E1** | `grep -ri "fastapi\|uvicorn\|websocket" --include=*.py .`（排除 `.venv*`） | **0 命中** → F7「空白」成立 |
| **E1** | `os.path.isdir('live'/'services'/'strategies')` | 三者均 **False** → 「新建」成立 |
| **E1** | 读 `pyproject.toml` 依赖段 | `redis>=4.5.0`(L45)、`sqlalchemy>=2.0.0`(L42)、`scipy`(L31)、`cvxpy`(L34)、`scikit-learn`(L39)、`pydantic>=2.0.0`(L35) **已声明**；`fastapi/uvicorn/xtquant/vnpy_ctp/import-linter/PyPortfolioOpt/orjson` **未声明** |
| **E1** | 读 `.github/workflows/tests.yml` L46 | mypy 靶 = `core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples`，**不含新目录**；CI 无 black/AST/import-linter 步骤；仓库**无 `.pre-commit-config.yaml`** |
| **E1** | `pytest tests -k golden --collect-only` | **13 项**（G1-G7 参数化 7 + schema 2 + 名称匹配 4）；`tests/golden/` 实际 **7 份 JSON（G1-G7）** |
| **E1** | `len(glob('tests/*.py'))` | **87**（与 P-041 CHECKLIST 目标一致）；P-041 关闭 CI `44101454276` 四 job 全绿 |
| **E2** | 运行时探针 | **N/A**：本次复审对象为文档，无运行时行为；不伪造探针 |
| **E3** | 读 `core/portfolio.py` L26-30/L394/L426 | 4 优化器 + 3 协方差估计器（sample/ledoit_wolf/ewma）+ `round_lot_optimize` 成立 |
| **E3** | 读 `core/interfaces.py` | 14 个 Protocol（IDataManager L25-95 / IOptimizer L179 / IExecutionSimulator L217-261）+ 4 个 Abstract ABC |
| **E3** | 读 `core/engine_v2.py` L341-441 / `core/engine_v3_vector.py` L78-153 | `run()` 与 `_rebalance_kernel` 锚点**逐字成立** |
| **E3** | 读 `core/live_bridge.py` | ABC L69-128 / `LiveOrder` L46 / `MockLiveBridge` L144-242 |
| **E3** | 读 `core/risk_monitor.py` | 五维监控器（Fundamental/Industry/Macro/CapitalFlow/Sentiment）+ `CompositeRiskEngine` + `LLMRiskAgent` 成立 |
| **E3** | 读 `core/guard_pipeline.py` | **6 类 Guard**：MaxPosition/Cooldown/Drawdown/SymbolWhitelist/Turnover/MinCash（初稿枚举有误） |
| **E3** | 读 `core/execution_policy.py` L402 | `SignalTranslator` 成立 |
| **E3** | 读 `core/target_positions.py` / `core/data_provider.py` / `core/registry.py` | 三个既有资产初稿未纳入（F-R5/R6/R18） |
| **E4** | 关键词扫描 `kill_switch\|emergency\|circuit_breaker\|fat_finger\|auth\|token\|jwt\|secret`（`core/**/*.py`） | **0 命中** → 实盘安全/鉴权空白 |
| **E4** | 关键词扫描 `交易日历\|trade_calendar\|is_trading_day\|集合竞价` | 无日历模块（日期来自数据文件）；仅 demo/测试有日历生成 |
| **E4** | 文档关键词扫描 `合规\|报备\|TLS\|密钥\|公司行为\|分红\|时区\|parity\|多策略.*资金\|监控告警` | 初稿均 **0 命中** |
| **E5** | 推测 | 未使用；监管阈值与 xtquant Python 支持范围统一标注「待 RESEARCH 取证」 |

### 10.2 发现清单（3 P1 + 12 P2 + 12 P3，全部当轮处置）

#### P1（阻断：不修不得启动实盘相关批次）

| ID | 发现 | 处置 |
|----|------|------|
| F-R1-P1 | 实盘安全与合规硬约束整体缺失（kill switch/网关事前风控/账户熔断/程序化交易报告/异常交易监控全仓 0 命中） | 新增 **§3.0 S1-S7**；新增 **P-052 实盘安全闸门**前置于 QMT 网关 |
| F-R2-P1 | 路线图顺序矛盾：初稿 P-050（含截面多空模板）早于其硬前置 P-051（做空账目） | **做空账目前移为 P-050**；模板移 P-051 并拆出 **P-058**（依赖 P-050/051/056）；§5 重排 + §10.5 映射 |
| F-R3-P1 | 分层依赖图缺 `live/services → strategies` 边，LiveAdapter 无法调用策略 | §2.1 改为完整边集；§6 给出允许/禁止边矩阵 |

#### P2（须在对应批次 RESEARCH 前修复）

| ID | 发现 | 处置 |
|----|------|------|
| F-R4-P2 | 新目录未纳入 mypy/black/CI 靶；`import-linter` 无依赖与 CI job；仓库无 pre-commit 配置 | §6「门禁落地」行：mypy 靶扩展 + 新 CI job + extra 分档 + uv lock |
| F-R5-P2 | P-042 漏 `core/data_provider.py`（DataProvider Protocol）与 `universe_data.py` | §5 P-042 改为三契约收敛 |
| F-R6-P2 | `core/target_positions.py`（目标权重→整手数量/清仓项）未纳入复用 | §1.2 F2/F3、§1.3、F3/F4 复用列 + P-045/P-047 验收 |
| F-R7-P2 | P-042「golden 零重录」与 §7.6「可能需重录裁决」矛盾 | 统一为「默认零重录；如需重录须显式裁决并记录」 |
| F-R8-P2 | 公司行为（分红/送转/配股/退市）未纳入实盘账本与对账 | F6 增 `corporate_actions` 事件与对账归因 |
| F-R9-P2 | 交易日历/交易时段/时区缺失 | F6 增 `live/session_calendar.py`；P-053 验收加时段状态机 |
| F-R10-P2 | 实时数据质量与源切换未定义（stale/乱序/缺口/停牌） | F1 增「数据质量闸门」；F7/P-053 验收 |
| F-R11-P2 | QMT/CTP 依赖与 Linux CI/3.12 冲突（xtquant 仅 Windows wheel） | F6 明确可选 extra + 独立 venv；§7.14 开放问题 |
| F-R12-P2 | 回测↔paper↔实盘 parity 无量化判据 | §4 差分审计行给出阈值；P-053 验收引用 |
| F-R13-P2 | 多策略共享账户资金竞争未定义 | F5 增虚拟子账户/资金预留/冲突仲裁 |
| F-R14-P2 | API 鉴权/TLS/密钥管理缺失 | §3.0 S5 + F7；P-054 验收加 401 |
| F-R15-P2 | 实盘可观测性（指标/告警）缺失 | F7 增 Prometheus/结构化日志/告警；§7.13 |

#### P3（当轮订正）

| ID | 发现 | 处置 |
|----|------|------|
| F-R16-P3 | Guard Pipeline 枚举错误（实际 6 类，非「仓位/回撤/冷却/换手/集中度」） | §1.1 订正 |
| F-R17-P3 | `agents/` 清单漏 `agent_framework`/`style_profile`/`style_reflection_engine` | §1.1 订正为 13 模块 |
| F-R18-P3 | Plugin Registry 锚点应为 `core/registry.py`；`engine_plugins.py` 无自动注册装饰器 | §1.1/§1.3/§4 订正 |
| F-R19-P3 | F2「缺整手约束」不准确（`round_lot_optimize`/`build_target_positions` 已有） | §1.2 F2 订正 |
| F-R20-P3 | §4「golden 13 条」口径混用（7 份基线 / 13 项收集） | §4 订正 |
| F-R21-P3 | `live_bridge.py:69-128` 未覆盖 `LiveOrder`/`MockLiveBridge` | §1.2 F6 补行号 |
| F-R22-P3 | 未注明 redis/sqlalchemy 已是现成依赖；新增依赖清单不完整 | §6 门禁落地 + §7.7 扩展 |
| F-R23-P3 | QMT `session_id` 冲突/客户端升级未纳入运维约束 | F6 依赖与部署补充 |
| F-R24-P3 | P-049 舆情前置漏 PIT 不变量扩展 | §5 P-049 验收补 |
| F-R25-P3 | vectorbt 对拍未固定版本/venv | F4 验收补 `.venv-vbt` + 版本记录 |
| F-R26-P3 | LLM/FinBERT 模型版本固定与缓存未纳入可审计 | F1 增「模型可审计」 |
| F-R27-P3 | §2.1 SERVICES 同时写「策略管理/回测触发」与「只读扇出」自相矛盾 | §2.1 改为管理面可写/交易面只读；F7 门禁口径同步 |

### 10.3 盲区扫描清单（处置结果）

| 类别 | 盲区 | 处置 |
|------|------|------|
| 安全 | kill switch、事前风控、账户熔断、自成交拦截、撤单率限制 | 已入 §3.0 S1-S3/S6 |
| 合规 | 程序化交易报告、高频报告、异常交易监控、投资者适当性 | 已入 §3.0 S4；范围待 §7.9 裁决 |
| 安全 | API 鉴权/TLS/密钥/最小权限 | 已入 §3.0 S5 |
| 数据 | stale/乱序/缺口/源切换/停牌 | 已入 F1/F7 |
| 时间 | 交易日历/时段/时区/期货夜盘 | 已入 F6 + §7.12 |
| 账目 | 公司行为、出入金、费用税、多策略虚拟子账户 | 已入 F6/F5 + §7.11/§7.12 |
| 执行 | 实盘执行算法（TWAP/POV/冰山）、价格带、涨跌停挂单、部分成交 | §3.0 S2 + F6 |
| 运维 | runbook、故障注入、崩溃恢复、QMT 客户端升级 | 已入 §3.0 S1/S7 + F6 |
| 观测 | 指标/日志/告警/延迟基准 | 已入 F7 + §7.13 |
| 版本 | xtquant Python 版本/Windows 隔离/可选 extra | 已入 F6 + §7.14 |
| 审计 | 模型版本固定（FinBERT/LLM）、策略代码 hash 口径 | F1 补充；hash 口径留 P-051 RESEARCH |
| 范围 | FastAPI 是否对外、多用户权限 | §7.9 |
| 观察项 | `tests/test_golden_baseline.py::test_all_cases_present` docstring 写「G1-G6」但实际基线 G1-G7（注释漂移） | 转 **O-R1** 观察项，不阻断 |
| 观察项 | 数据供应商合约/授权、舆情爬虫合规、LLM 调用成本 | §7.5（已有）+ P-049 RESEARCH |
| 未纳入本轮 | 出入金/费用税明细口径、策略参数快照 schema 迁移、事件 schema 版本化 | 各批次 RESEARCH 阶段展开，不阻塞总纲 |

### 10.4 复审结论

- **P1 3 项、P2 12 项、P3 12 项全部当轮处置**；修订后 §1-§7 与代码事实一致，路线图顺序自洽，实盘安全/合规/数据质量/运维边界补齐。
- **准予作为 pre-batch 总纲**：用户裁决 §7 后，按修订后 §5 从 **P-042** 起逐批立项；每批仍走 SPEC_PROCESS 十步 + 异构终审。
- **本次仅文档修订**，不改代码；代码门禁沿用 P-041 关闭基线（pytest 778 / golden 13·765 / black 124·191 / mypy 103 files 0 / AST 22 / tests 87 / uv 0；CI `44101454276` 四 job 全绿），未重跑。

### 10.5 批次编号映射（初稿 → 修订稿）

| 初稿 | 修订稿 | 说明 |
|------|--------|------|
| P-050 策略模板+生命周期 | **P-051** | 去掉截面多空/月差模板（拆至 P-058）；前置补 P-050 |
| P-051 做空账目 | **P-050** | 前移，作为截面多空/月差硬前置 |
| — | **P-052 实盘安全闸门** | 新增（§3.0 S1-S7） |
| P-052 QMT 网关 | **P-053** | 前置改为 P-043/P-050/P-052 |
| P-053 FastAPI+WS | **P-054** | 前置 P-053 + §7.9 |
| P-054 微服务拆分 | **P-055** | — |
| P-055 CTP 期货/月差 | **P-056** | 月差模板部分移至 P-058 |
| P-056 regime 自适应 | **P-057** | — |
| — | **P-058 截面多空/月差模板** | 新增（依赖 P-050/P-051/P-056） |

### 10.6 未决观察项

- **O-R1（P3）**: `test_all_cases_present` docstring 的「G1-G6」与 `tests/golden/` 实有 G1-G7 不一致（注释漂移，非测试逻辑缺陷）；建议下次触及该文件时一并订正。
- **O-R2（P2）**: xtquant 支持的 Python 版本范围与 Linux 不可安装性需在 P-053 RESEARCH 阶段用 `pip index versions xtquant`/官方文档取证；当前仅按公开资料标注为约束。
- **O-R3（P2）**: 程序化交易报告/高频认定的具体阈值须在 P-052 RESEARCH 阶段引用交易所细则原文取证；总纲不对数值作断言。
