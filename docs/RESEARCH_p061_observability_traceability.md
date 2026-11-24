# RESEARCH：P-061 全周期可追溯性与可视化审计（策略 → 标的 → 执行 → 调仓 → 平仓）

> **批次（建议）**：**P-061**（`grep -r "P-061|P061"` 全仓零占用，编号可用）
> **预计档位**：**待裁决**（建议 **T2**：新增 `scripts/` + `web/` 只读视图，**不触碰 core 交易路径**；若采纳「core 内加 trace seam」则升 T1 口径严格执行）
> **上游**：用户 2026-11-24 指令「分析当前框架是否有日志机制与可视化追溯功能，能够可视化追溯策略-标的-执行-调仓-平仓等全周期动作，实现与验证结果对齐，方便后续排查；进行详细调研，可以使用社区相关类似轻量开源框架」
> **基线**：`4367775`（P-060a 已关闭并推送；collect **1557** = 1556 passed + 1 skipped / golden **22** / `-k p059` **63** / mypy 160·0 / black 330）
> **作者**：DeepSeek-V4.1-Flash（Step 2 复审须 reviewer ≠ 作者，RULE-5）
> **状态**：Step 1 调研 + Step 1.5 方案分析（§13）+ Step 3 DESIGN + Step 5 IMPL（X1-X14）完成；**U-P061-1..7 闭合**；Step 2/4/6 三次异构复审均 PASS-WITH-COMMENTS（F-01..F-09 / F-10..F-15 / F-16..F-21 当轮闭合，共 21 项）；**Step 8 一致性复审完成**（F-S8-P061-4/5：本文 §13.4.2 retry_count 与 §13.4.3 qty_by_side 两处残留已修复，见 CHECKLIST §10）；**Step 9 落码完成**（37 例全绿，见 CHECKLIST §11）

---

## 0. 结论先行

| 问题 | 结论 | 判据 |
|---|---|---|
| 有没有日志机制？ | **有，但分散且默认全关** | `event_log.py` 双写总线、六层 dump、pending 事件 CSV、实盘 outbox/ledger、manifest、Prometheus 指标；`cfg.event_log_path=None`、`cfg.dump_layers_dir=None` 默认关闭 |
| 能否串起策略→标的→执行→调仓→平仓？ | **不能** | 全仓无 `correlation_id/trace_id`（仅 manifest 有 `run_id`）；`REBALANCE` 事件只带 `date + n_targets`；`Trade` 无 `reason` 字段；`core/stops.py` 未接入 `engine_v2` |
| 有没有可视化追溯？ | **没有** | `web/streamlit_app/` 5 页为**硬编码假数据**；`web/server.py` 只是 9000 端口的静态文件服务器；`change_report` 只有 CLI + JSON，无 UI |
| 能否与验证结果对齐？ | **部分能，且仅为事后差分** | 六层 dump + `compare_runs` 残差 1e-8；manifest 的 `input_fingerprint`；无 trace↔NAV↔golden 的机械对齐报告 |
| 建议 | **M-B（事件溯源增强 + 只读可视化）分三期**；M-A 作为第 1 期，M-D 明确不做 | §5 |

一句话：**框架目前具备「分散的日志零件 + 事后分层快照」，缺的是「贯穿全周期的追溯主键 + 可对齐验证结果的只读视图」。**

---

## 1. 问题定义

### 1.1 题干拆解：8 跳链条

| # | 跳 | 排查要回答的问题 | 需要的最小证据 |
|---|---|---|---|
| 1 | **策略选择** | 这次跑的是哪个策略/哪版参数/哪份因子？ | 策略名 + 注册版本 + 参数快照 + code hash |
| 2 | **标的** | 为什么是这只票进入候选池？因子值多少？ | 当日因子值/合成分 + 排名 + 过滤原因 |
| 3 | **目标** | 目标权重/目标数量怎么算出来的？ | 目标权重 + 目标股数 + 优化器输入输出 |
| 4 | **调仓触发** | 为什么今天调仓？触发条件命中哪一条？ | trigger 类型（calendar/condition/hybrid）+ 触发参数 |
| 5 | **执行** | 订单为什么没成交/被拒/重试？ | order_id + 生命周期四态 + 拒绝原因闭集 |
| 6 | **成交** | 成交价、费用、滑点是多少？ | fill 记录 + 成本分解 |
| 7 | **持仓/平仓** | 为什么卖了？止损/止盈/时间止损/换仓/强平？ | `reason` 闭集 + 触发阈值 + 持仓区间 |
| 8 | **验证对齐** | 这条链能否对上 NAV、trades、归因残差、golden？ | trace ↔ NAV 逐日闭合 + 残差 + 门禁快照 |

### 1.2 「对齐验证结果」的三种口径

| 口径 | 现有能力 | 本次要求 |
|---|---|---|
| **数值对齐** | `trades.csv` / `portfolio_snapshots.csv` / `performance_metrics.csv` | trace 汇总后与三者**逐日/逐笔守恒**（数量、金额、现金） |
| **归因对齐** | 六层 dump + `compare_runs`（`residual < 1e-8` 且 `attribution_complete`） | trace 的订单/成交分层计数与 L4/L5 一致 |
| **行为对齐** | golden 22 / 场景 18 条 7 层 / 不变式 11 / 契约 6 | trace 产物可被门禁复核，且**关闭时字节级不变** |

### 1.3 五个典型排查问句（验收锚点）

1. 「2024-03-15 为什么买了 600519、而 000001 没买？」→ 需 1→2→3→4→5 全链。
2. 「这笔卖出是止损还是再平衡？」→ 需第 7 跳 `reason`。
3. 「为什么 NAV 和上次跑差 0.3%？」→ 需 `compare_runs` + trace 差分。
4. 「订单挂 3 天没成交，卡在哪？」→ 需第 5 跳状态机 + 拒绝原因。
5. 「这条结论能复现吗？」→ 需 manifest `input_fingerprint` + trace 确定性。

### 1.4 范围与不做

- **做**：回测主链（`core/engine_v2`）的追溯补全与只读可视化；实盘事件的**口径对齐评估**（不改造实盘）。
- **不做**：不引入 Grafana/Loki/Tempo 全栈（沿 `UPGRADE_MASTER_PLAN.md` §7.13 的悬置结论）；不改交易逻辑；不重录 golden；不新增第五套夹具。

---

## 2. 现有资产盘点（证据级）

### 2.1 资产总表

| 载体 | 位置（证据） | 粒度 | 关键字段 | 默认状态 | 能否定位到「单标的单动作」 |
|---|---|---|---|---|---|
| **EventLog** 事件总线 | [event_log.py](file:///f:/Coding/Factor_Trading_v3.0/core/event_log.py#L104-L149) | 运行/日/调仓事件 | `seq/ts/type/payload/source` | **关闭**（`event_log_path=None`） | 否（payload 过薄，见 §2.3） |
| **引擎域事件 5 类** | [event_log.py](file:///f:/Coding/Factor_Trading_v3.0/core/event_log.py#L53-L57) | run/day | RUN_STARTED / REBALANCE / DAY_END / ERROR / RUN_FINISHED | 随总线 | 否 |
| **AUDIT 8 类** | [event_log.py](file:///f:/Coding/Factor_Trading_v3.0/core/event_log.py#L60-L70) | 实盘审计 | INTENT/RISK_DECISION/ORDER/FILL/CANCEL/RECONCILE/KILL/CIRCUIT | 回测**不发射** | 实盘侧是 |
| **六层归因 dump** | [change_report.py](file:///f:/Coding/Factor_Trading_v3.0/core/change_report.py) | 日 × 6 层 | L1 涨跌停掩码 / L2 可交易 / L3 目标代码 / L4 订单 / L5 成交 / L6 NAV | **关闭**（`dump_layers_dir=None`） | 部分（L4/L5 有 stock+side+qty） |
| **pending 事件 CSV** | [pending.py](file:///f:/Coding/Factor_Trading_v3.0/core/pending.py#L494-L514) | 订单状态 | `date/event_type/stock/description`，4 类：ADDED/CANCELLED/EXECUTED/EXPIRED | 有 `pending_queue` 即写 | 部分（无 order_id、无价格、无拒绝码） |
| **trades.csv** | [execution.py](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L26-L40) | 逐笔成交 | `date/stock/side/quantity/price/amount/cost/net_amount` | **开启** | 是，但**无 reason** |
| **portfolio_snapshots.csv** | [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1905-L1920) | 日末 | 持仓/现金/净值/收益 | **开启** | 否（无持仓来源） |
| **manifest.json** | [manifest.py](file:///f:/Coding/Factor_Trading_v3.0/core/manifest.py) | run 级 | git commit/dirty、数据 sha256、config、`input_fingerprint` | 开启（`write_manifest=True`） | 否（run 级） |
| **实盘 outbox** | [events.py](file:///f:/Coding/Factor_Trading_v3.0/live/events.py#L16-L30) | 订单/成交事件 | `event_id`（`order:{coid}:accepted:v{n}`）、`aggregate_id`、canonical JSON | 实盘 | **是（当前最强）** |
| **SQLite ledger** | [ledger_store.py](file:///f:/Coding/Factor_Trading_v3.0/live/ledger_store.py) | 账本/outbox/inbox | WAL + FULL + 单写者锁 | 实盘 | 是 |
| **Prometheus 指标** | [metrics.py](file:///f:/Coding/Factor_Trading_v3.0/services/metrics.py) | 服务级 | 四黄金信号 + `p054_*` 领域指标 | 服务 | 否（聚合量） |
| **TraceRecorder（测试）** | [\_scenarios_trace.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_trace.py#L35-L60) | 日桶 + 订单状态 | `target_weight/buyable/sellable/orders/filled/rejected/cash/nav/positions` + `state_events` + 拒绝原因闭集 | **仅测试** | **是（最接近目标）** |
| **Streamlit 5 页** | [streamlit_app](file:///f:/Coding/Factor_Trading_v3.0/web/streamlit_app/pages/01_Overview.py) | 页面 | 硬编码数字 + `np.random.seed(42)` 净值 | — | **否（假数据）** |

### 2.2 三个关键细节

1. **EventLog 设计是可用的地基**：append-only JSONL + 内存 ring buffer（500）+ `read/replay/query/recent/last_seq/subscribe/subscribe_type`，并有 `IEventBus` Protocol（[event_log.py](file:///f:/Coding/Factor_Trading_v3.0/core/event_log.py#L85-L101)）。缺的是**事件语义**，不是管道。
2. **六层 dump 是「事后分层快照」而非「逐动作事件流」**：`LayerDumper` 只记录当日状态集合；L4 行仅 `stock/side/qty/reason`（`reason` 缺省 `"rebalance"`，见 [change_report.py](file:///f:/Coding/Factor_Trading_v3.0/core/change_report.py)），L5 行仅 `stock/side/qty/price/cost`，**无订单 ID、无生命周期、无策略/因子来源**。
3. **测试侧已有最强追溯原型**：`TraceRecorder` 以 proxy 包装 `executor/tracker/optimizer`，产出日桶 + `state_events`（filled/retry/dropped）+ 拒绝原因（`limit_up/suspended/st_blocked/invalid_price/cash_short/limit_down/no_position/expired`）。**这份数据结构可以直接升格为生产 trace 契约**，代价最小。

### 2.3 关键否定证据（本次调研新发现）

| # | 证据 | 影响 |
|---|---|---|
| E1 | `REBALANCE` payload 只有 `{"date", "n_targets"}`（[engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1572-L1578)） | 无法回答「为什么买这只」 |
| E2 | `DAY_END` payload 只有 `{"date", "total_value"}`（[engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L802-L808)） | 无持仓/现金，无法逐日对账 |
| E3 | `Trade` 无 `reason` 字段（[execution.py](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L26-L40)） | 平仓原因不可区分（止损 vs 再平衡 vs 强平） |
| E4 | `core/stops.py` 在 `engine_v2` **零引用**（全仓仅 `tests/`、`docs/`、`scripts/external_benchmark/verify_p045.py` 引用） | 止损引擎的 `StopDecision.reason` 在回测主链**计算后丢弃** |
| E5 | 全仓 `correlation_id|trace_id` **零命中**；`run_id` 仅出现于 `manifest.py`/`test_manifest.py` | 无跨层主键 |
| E6 | 回测路径不发射任何 `AUDIT_*`（grep `EventType.AUDIT` 在 `engine_v2.py` 无命中） | 回测与实盘审计口径断层 |
| E7 | `web/server.py` 是 `SimpleHTTPRequestHandler` 静态服务器（[server.py](file:///f:/Coding/Factor_Trading_v3.0/web/server.py#L1-L12)） | 不存在 HTTP API 层可接 |
| E8 | `web/streamlit_app/pages/01_Overview.py` 的「Tests Passing: 245」等为硬编码 | 可视化入口**不可信**，不可用于排查 |
| E9 | `cfg.event_log_path=None` 且 `cfg.dump_layers_dir=None`（[config.py](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L454-L460)） | **开箱默认不可追溯** |

---

## 3. 差距矩阵

| 跳 | 现有载体 | 可回答 | 不能回答 | 缺口 |
|---|---|---|---|---|
| 1 策略 | manifest `git.commit` + cfg | 「哪份代码/配置」 | 策略名、注册版本、参数快照、因子组合定义 | G-10 |
| 2 标的/因子 | 无 | — | 当日因子值、排名、过滤原因 | G-03 |
| 3 目标 | L3 目标代码集合 | 目标有哪些票 | 目标权重/目标数量/优化器输入输出 | G-03 |
| 4 调仓触发 | `REBALANCE` 事件 | 哪一天调了、几只 | trigger 类型与命中条件 | G-02 |
| 5 执行/订单 | `pending_order_events.csv` + L4 | 状态事件与方向数量 | order_id、重试次数、拒单码、跨日关联 | G-04 |
| 6 成交 | `trades.csv` + L5 | 价格/费用/数量 | 对应哪张订单、哪次调仓 | G-01/G-05 |
| 7 持仓/平仓 | snapshots + L6 | 日末持仓与净值 | 卖出原因、止损触发阈值 | G-05/G-06 |
| 8 验证对齐 | `compare_runs` + manifest | 两次运行的层差异与残差 | trace↔NAV↔golden 的机械对齐报告 | G-11 |

### 3.1 缺口清单（G-P061-01..12）

| ID | 缺口 | 严重度 | 证据 |
|---|---|---|---|
| **G-01** | 无统一追溯主键（`correlation_id/trace_id`）串联 策略→因子→目标→订单→成交→持仓→平仓 | **P1** | E5 |
| **G-02** | `REBALANCE` 事件载荷过薄（无 trigger 类型/参数/目标权重） | **P1** | E1 |
| **G-03** | 目标持仓只存代码集合，不存权重/数量/来源因子 | **P1** | §2.2-2 |
| **G-04** | 订单无稳定 ID、无生命周期聚合；拒绝原因只在测试侧 | **P1** | §2.2-3 |
| **G-05** | `Trade` 无 `reason`，平仓/止损/再平衡/强平不可区分 | **P1** | E3 |
| **G-06** | `core/stops.py` 未接入回测主链，止损原因计算后丢弃 | **P1** | E4 |
| **G-07** | 回测不发射 `AUDIT_*`，与实盘 `live/events.py` 口径断层 | P2 | E6 |
| **G-08** | 六层 dump 仅支持目录级差分，无跨层时间轴/UI | P2 | §2.2-2 |
| **G-09** | Streamlit 5 页为假数据，不能作为追溯入口 | P2 | E8 |
| **G-10** | manifest 无 strategy/params 显式快照（仅 commit + cfg + 数据哈希） | P2 | §2.1 |
| **G-11** | 无「验证对齐」机械报告（trace ↔ trades/NAV/残差/golden） | P2 | §1.2 |
| **G-12** | 追溯能力默认全关，开箱不可用 | P2 | E9 |

> 严重度口径：**P1 = 不补则无法完成用户要求的全周期追溯**；P2 = 影响排查效率或可信度。

---

## 4. 社区锚点（轻量可借鉴）

| 项目 | 机制 | 可借鉴 | 不采纳 |
|---|---|---|---|
| **NautilusTrader** | message bus + correlation ID 响应处理器 + event sourcing（durable event store、replay、run manifests、verification） | **「事件信封 + 主键 + run manifest」三件套**；订单事件与成交事件用同一 aggregate id | 不引入其 Rust/Cython 内核与完整架构 |
| **Freqtrade** | backtest report 表 + `sell_reason` recap + SQLite + `--breakdown` | **`sell_reason` 单列即可回答第 7 跳**；按交易对 breakdown | 不引入其 bot/交易所网关 |
| **OpenLineage + Marquez** | run / job / dataset 三元组对象模型；current lineage 视图 | **对象模型命名**（run/job/dataset ↔ run/strategy/instrument） | 不部署 Marquez 服务端 |
| **Datasette（含 Lite）** | SQLite 只读 Web UI + JSON API；Lite 为 WASM 单页 | **M-C 可选适配器**：trace 落 SQLite 即得过滤/钻取 UI，零后端 | 不作为默认依赖（需 Python 包） |
| **FINOS Perspective** | C++/WASM 流式透视表组件 | 大数据量前端表格/透视的性能上限参考 | 不引入 WASM 资产（体积/构建复杂） |
| **TradingView Lightweight Charts** | v5 base bundle 约 **35kB**，Apache-2.0 | **M-B 静态时间轴**的图表层候选 | 若坚持零前端依赖，用内联 SVG 自绘 |
| **QuantStats / pyfolio** | HTML tearsheet（单文件、离线可看） | **「单文件 HTML 报告」交付形态** | 不引入其指标口径（本项目已有 `core.metrics` 单一口径） |
| **zipline blotter / LEAN report** | blotter 记录订单生命周期；LEAN 生成统计报告 | 订单状态机四态命名 | 不引入框架 |

**结论**：不需要引入任何框架。只需借三件事——**① 统一事件信封与主键；② `sell_reason` 式闭集原因；③ 单文件只读视图**。这与本项目「零新依赖（S12）」约束兼容。

---

## 5. 方案对比

### 5.1 四个方案

| 方案 | 内容 | 交付物 |
|---|---|---|
| **M-A 最小增强** | 脚本汇总现有 `trades.csv / snapshots / pending_order_events / manifest / L1-L6` → 单文件静态 HTML | `scripts/trace_report.py` + `trace.html` |
| **M-B 事件溯源增强**（推荐） | 在 M-A 之上补「追溯主键 + 宽表 + 原因闭集 + 对齐报告」；`trace_day/trace_order/trace_fill` 三张表；静态时间轴 | 上述 + `trace.jsonl` + `trace_orders.csv` + `alignment.json` + HTML 时间轴 |
| **M-C SQLite + Datasette** | trace 落 SQLite，用 Datasette 只读浏览/过滤/JSON API | M-B 产物 + `trace.db` + Datasette 启动脚本 |
| **M-D 完整可观测栈** | Prometheus + Grafana + Loki/Tempo + OTel | 部署清单 |

### 5.2 七维对比

| 维度 | M-A | M-B | M-C | M-D |
|---|---|---|---|---|
| 追溯粒度 | 日/笔（无因果链） | **逐动作 + 因果链** | 同 M-B | 同 M-B + 运行时 |
| 改动面 | 仅 `scripts/` | `scripts/` + 可选 core seam（默认关） | + 依赖 | 大 |
| 新依赖 | 0 | **0**（stdlib + 已有 pandas） | `datasette`（Python 包） | 多个服务 |
| 复用现有资产 | 高 | **最高**（EventLog/六层/TraceRecorder 词表） | 高 | 低 |
| 验证对齐 | 弱（仅汇总） | **强（残差 + 守恒 + 门禁快照）** | 强 | 强 |
| 排查效率 | 中 | **高** | 最高（交互过滤） | 高（但需运维） |
| 风险 | 低 | **中低**（主键设计需一次定对） | 中（依赖治理） | 高（部署复杂度） |

### 5.3 推荐：M-B 分三期

| 期 | 内容 | 验收 |
|---|---|---|
| **M-B1** | 只读汇总 + 单文件 HTML（=M-A）：从现有 5 类产物生成「日 × 标的」表，标注哪些列缺失 | 对任意既有 `output/` 目录可生成；HTML 离线可开 |
| **M-B2** | 追溯主键 + 三张宽表 + 原因闭集（订单拒绝 8 值、平仓 6 值）；`alignment.json` 做 trace↔trades↔NAV 守恒 | 守恒残差 `< 1e-8`；样例 run 可回答 §1.3 五问 |
| **M-B3** | 静态时间轴视图（内联 SVG 或 35kB Lightweight Charts；二选一由 U-P061-5 裁决） | 单票 drill-down：因子→目标→订单→成交→平仓一屏 |

M-C 作为**可选导出**（`--sqlite` flag），不进默认依赖；M-D 明确不做。

---

## 6. 规格草案（S1-S10）

| ID | 规格 | 约束 |
|---|---|---|
| **S1** | **追溯主键**（F-09 修订，对齐 §13.4.1）：`trace_id = f"{date}|{stock}"`（运行内唯一）；`order_ref = f"{trace_id}|{side}|{order_seq:05d}"`；`fill_ref = f"{order_ref}|{fill_seq}"`；run 级关联（`manifest.run_id` / `input_fingerprint`）写入 `alignment.json`（`run_id` 运行结束才生成，不能作前缀）。仅在**新产物**中出现 | 不修改 `Trade`/`PendingOrder` 数据结构（等价 DD9） |
| **S2** | **统一事件信封**：`{ts, run_id, trace_id, hop, action, reason, payload}`；`hop ∈ {strategy,factor,target,rebalance,order,fill,position,close}` | 可映射到 `EventLogEntry`（`type=hop.action`，`payload` 含其余字段） |
| **S3** | **三张宽表**：`trace_day`（日 × 标的：因子值/目标权重/是否可买可卖/成交/持仓/NAV 贡献）、`trace_order`（订单生命周期）、`trace_fill`（成交 + 费用分解） | CSV 为默认；`--sqlite` 可选 |
| **S4** | **订单状态机四态**：`created → filled | retry → dropped`，另加 `cancelled/expired`；拒绝原因闭集沿用 `_scenarios_trace` 8 值 + `cash_short` | 闭集外值 → 记 `unknown` 并计数。补注（F-07）：`_kind ∈ {liquidation, roll}` 订单**永不**进入 `cancelled/expired`（[engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1089-L1091)/[L1122-L1124](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1122-L1124)）；再平衡日 `cancelled` 批量发生（`cancel_orders` L1330-1335） |
| **S5** | **平仓原因闭集（6 值）**：`rebalance / stop_loss / trailing_stop / take_profit / time_stop / final_liquidation`（+`delisted`） | 与 `core/stops.py` 的 `StopDecision.reason` 词表对齐；**`stop_*` 在 P-045 接入主链前不会出现**（§13.8） |
| **S6** | **归因链 JSON**：单票单日 `factor_value → target_weight → order → fill → pnl`，允许 `null` 但必须显式 | 缺失原因写入 `missing[]` |
| **S7** | **只读视图**：单文件 HTML（无服务端、无 CDN、离线可开），含「日历热力 + 单票时间轴 + 订单表 + 对齐摘要」 | 不得写回任何产物 |
| **S8** | **对齐报告**：`alignment.json` 含 `n_orders/n_fills/Σqty/Σamount/Σcost/cash/nav` 三源对账 + 残差 | 残差阈值沿用 `1e-8` |
| **S9** | **CLI**：`python scripts/trace_report.py --run-dir output/xxx [--event-log ...] [--sqlite]`；**0=对齐，1=残差超限或缺核心产物**（F-06/F-18 修订，**两级产物**：核心 = `trace_*.csv` + `alignment.json`，缺失 → exit 1；辅助 = manifest/snapshots/L1-L6/pending_events，缺失 → `missing[]` 记录且 exit 0，残差不可算项标 `degraded`；`scripts/change_report.py` 实际仅 0/1，不引入 2） | 退出码与 `scripts/change_report.py` 一致（0/1） |
| **S10** | **默认关闭、零行为**：不启用时 `trades.csv`/`snapshots`/golden 22/场景 63 **字节级不变** | I2 硬约束 |

---

## 7. 不变式（I1-I10）

| ID | 不变式 |
|---|---|
| **I1** | 追溯默认关闭；关闭时零 I/O、零新文件 |
| **I2** | 关闭时既有产物与门禁**零漂移**（golden 22 / `-k p059` 63 / trades.csv 字节级一致） |
| **I3** | 不修改 `Trade`/`PendingOrder`/`EventLogEntry` 既有字段；新增信息只进新产物或 `payload` |
| **I4** | 同一输入（同 `input_fingerprint`）→ 同一 `trace_id` 序列与同一 `alignment.json`（不含时间戳） |
| **I5** | 事件与宽表 **append-only**；不得回写历史行 |
| **I6** | 订单拒绝原因取值必须在闭集内（S4），闭集外计数并降级为 `unknown` |
| **I7** | 平仓原因取值必须在闭集内（S5） |
| **I8** | 视图只读、离线、无网络请求（禁止 CDN/远程字体） |
| **I9** | 对齐残差阈值 `1e-8`，与 `change_report.RESIDUAL_TOL` 同源 |
| **I10** | 零新增运行时依赖；SQLite/Datasette 仅可选路径 |

---

## 8. 裁定项（U-P061-1..6）

| ID | 问题 | 选项 | 建议 |
|---|---|---|---|
| **U-P061-1** | 批次号 | P-061 / 其他 | **P-061**（全仓零占用） |
| **U-P061-2** | 方案 | M-A / **M-B** / M-C / M-D | **M-B 分三期**（M-A = B1） |
| **U-P061-3** | 范围 | 仅回测 / **回测优先 + 实盘口径对齐评估** | 后者（实盘 outbox 已强，先评估不改） |
| **U-P061-4** | 是否允许 core 内加 trace seam（默认关，如 `cfg.trace_dir`） | 允许 / 全部放 `scripts/` 外部汇总 | **允许最小 seam**（否则第 7 跳 `reason` 无法取得）；若拒绝则降至「只能回答 1/3/5/6 跳」 |
| **U-P061-5** | Streamlit 处置 | 接真数据 / **显式标注 demo + 新视图独立** / 暂不动 | 标注 demo（G-09 不小改大） |
| **U-P061-6** | 是否在 CI 增加 trace 自检（非阻断） | 加 / 不加 | 三期后再议（沿 U-P060-7 先例） |
| **U-P061-7** | 是否把 P-045 `core/stops.py` 接入回测主链（**行为变更**） | 本批不接 / 独立批次 / 本批接 | **独立批次**；不接则 stop 类平仓原因永不出现（§13.8） |

**U-P061-4 是关键分叉**：若不接受 core seam，则 `core/stops.py` 的 `reason` 与订单拒绝码无法进入产物，M-B 只能做「事后推断」而非「原生记录」，G-05/G-06 无法闭合。

**裁决（用户 2026-11-24「按这个方案来」→ 全部按建议列闭合）**：
- **U-P061-1**：批次号 **P-061** ✅
- **U-P061-2**：方案 **M-B 分三期** ✅
- **U-P061-3**：范围 **回测优先 + 实盘口径对齐评估**（实盘只评估不改） ✅
- **U-P061-4**：**允许最小 seam**（SEAM-1..7，默认关、零 I/O） ✅
- **U-P061-5**：Streamlit **显式标注 demo + 新视图独立** ✅
- **U-P061-6**：CI trace 自检 **三期后再议** ✅
- **U-P061-7**：P-045 stops 接入主链 → **独立批次**，本批不做（stop 类原因在本批产物中不出现） ✅

---

## 9. 风险

| ID | 风险 | 缓解 |
|---|---|---|
| R1 | trace 体积膨胀（全市场 × 全历史 × 逐日） | 默认仅记录「有动作」的行；日表按标的过滤（目标/持仓/成交/拒单之一） |
| R2 | 主键设计一次定错导致返工 | S1 先做 1 个样例 run 的 PoC，再冻结 |
| R3 | 与 P-060b/P-060c 覆盖率批次争抢工时 | 排期串行；trace 自检不进 CI |
| R4 | 视图成为「第二套真相」 | 视图只读产物，禁止独立计算指标；所有数字标注来源文件 |
| R5 | Streamlit 假数据继续误导 | U-P061-5 显式标注，必要时关页 |
| R6 | 依赖膨胀 | I10 硬约束；SQLite/Datasette 仅 `--sqlite` 可选 |

---

## 10. 可重放命令（证据复核）

```bash
# E5：确认无 trace/correlation 主键
rg -n "correlation_id|trace_id" --glob "*.py"

# E4：确认 stops 未接入引擎
rg -n "from core\.stops|StopEngine|apply_stops" core/ scripts/ strategies/

# E1/E2：确认事件载荷
rg -n "EventType.REBALANCE|EventType.DAY_END" -A 8 core/engine_v2.py

# E8：确认 Streamlit 假数据
rg -n "np.random.seed|Tests Passing|硬编码" web/streamlit_app/

# 现状基线（不执行任何改动）
.\.venv\Scripts\python.exe -m pytest -q -k "p059 or golden"
```

---

## 11. Step 2 复审输入（reviewer ≠ 作者）

请重点挑战：

1. **G-01 主键设计**：`run_id:date:stock` 是否足够？订单级是否需要 `seq`（同票同日多单）？
2. **U-P061-4 的必要性**：不做 core seam 时，能否仅凭 `pending_order_events.csv` + `trades.csv` 还原第 5/7 跳？请给出反例。
3. **S3 宽表字段是否过宽**：是否存在不可获得的字段（如因子值在 `engine_v2` 内是否可达）？
4. **I2 可验证性**：如何机械证明「关闭时字节级不变」（建议对样例 `output/` 做 sha256 对比）。
5. **与 `change_report` 的边界**：trace 是否应复用 L1-L6 而非另起一套（避免双真相）？

---

## 12. 结论

1. **有日志，无追溯**：EventLog/六层/outbox/ledger 各自成立，但缺统一主键与因果链。
2. **有验证，无对齐**：`compare_runs` 能证明「两次运行的层差异可解释」，但不能证明「这条链上的每个动作都对得上」。
3. **有页面，无真相**：Streamlit 为演示壳，`web/server.py` 仅静态托管。
4. **最优路径**：**M-B 分三期**，第 1 期零依赖、零 core 改动即可交付（M-A），第 2 期再决定是否加 trace seam（U-P061-4）。
5. **不引入框架**：NautilusTrader/Freqtrade/OpenLineage 只借对象模型与原因闭集；Datasette 仅可选。

**下一步**：用户裁决 U-P061-1..7 → Step 2 异构复审 → Step 3 DESIGN。

---

## 13. 详细方案分析（Step 1.5，2026-11-24 追加）

> 本节回答「先落详细方案分析」：逐跳核对**钩点是否真的能拿到数据**、两条执行路径的覆盖、主键与表结构的字段级设计、视图三选一、与 `change_report` 的边界、以及一个**必须提前说明的能力上限**（§13.8：stop 类平仓原因在现有引擎中不存在）。本节仍未写代码。

### 13.1 钩点可行性地图（逐跳）

| 跳 | 钩点（文件 · 行） | 作用域内**已有** | **缺失** | 采集方式 |
|---|---|---|---|---|
| 1 策略 | [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1836-L1861) `additional_info` + [L1954-L1981](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1954-L1981) manifest | git commit/dirty、cfg、`factor_files`、`input_fingerprint` | 策略名/注册版本/参数快照 | B1：由调用方传 `--strategy` 元数据；B2 可选加 `cfg.trace_labels` |
| 2 标的/因子 | [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1338-L1342) `daily_signal` + [L1341](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1341) `tradable_mask` | 当日合成分值、可交易掩码 | 排名、被过滤原因 | 对「目标 ∪ 持仓 ∪ 成交 ∪ 拒单」标的记录信号值 |
| 3 目标 | [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1556-L1571) `targets` / `target_weights` / `_last_targets` | `weight / current_quantity / target_quantity / is_exit`（[target_positions.py](file:///f:/Coding/Factor_Trading_v3.0/core/target_positions.py#L22-L40)） | — | 直接落 `trace_day`，零推导 |
| 4 触发 | [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L784-L792) `should_trigger(...)` | 返回 `bool` + trigger 实例 + 入参 | **命中的具体条件**（日历/信号变化/回撤/波动率） | 记录 `type(trigger).__name__` + cfg；分支靠离线复算或 `ConditionalTrigger` 加只读 `last_reason` |
| 5 订单 | [engine_v2.py](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1169-L1247)（队列路径）/ [L1741-L1807](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1741-L1807)（次日路径） | order 对象、masks、现金、价格 | 稳定 ID、拒绝码持久化 | 运行期 `order_seq` + 分支打点（见 §13.3） |
| 6 成交 | [L1233-L1240](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1233-L1240) / [L1799-L1803](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1799-L1803) + [execution.py](file:///f:/Coding/Factor_Trading_v3.0/core/execution.py#L280-L369) | `Trade` 全字段、调用点持有 order | order→fill 关联 | 同一 `order_ref` 关联 |
| 7 持仓/平仓 | [L889-L905](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L889-L905)（`stocks={stock: reason}`）+ [tracker.py](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L398-L409) | `delisted` / `final_liquidation` 可传；内存快照含逐股持仓 | stop 类原因（引擎未接 stops）；CSV 丢弃逐股明细 | 落日持仓表；§13.8 |
| 8 对齐 | `compare_runs` + manifest | 残差 1e-8、指纹 | trace↔NAV↔门禁 | `alignment.json`（§13.4.3） |

**两条执行路径必须同时覆盖**：`enable_pending_orders=True` 走 `_process_pending_orders`；否则走 `_execute_order_next_open` → `_execute_next_day_orders`。两条路径的跳过/拒单分支**各自独立实现**（L1171-1226 vs L1747-1797），trace 需要在一个共享的只读分类器中复用判定，避免两套词表漂移。

**不在范围**：`engine_v3_vector.py` 只输出净值/指标（[L409-L437](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v3_vector.py#L409-L437)），无订单与成交，无法追溯，本批不覆盖。

### 13.2 数据可用性核查

| 数据项 | 可用 | 证据 | 备注 |
|---|---|---|---|
| 因子/合成分值 | ✅ | `_composite_signal` DataFrame；`daily_signal`（L1338） | weights 模式下即目标权重 |
| 目标权重 | ✅ | L1556-1565 `target_weights` | 优化器输出 |
| 目标股数/退出标记 | ✅ | `TargetPosition.weight/target_quantity/is_exit` | 无需反推 |
| 可买/可卖 | ✅ | L1162-1163、L1341 | 布尔掩码 |
| 停牌/ST 区分 | ✅ | `dm.suspend` / `dm.st` + `cfg.universe.exclude_st`；测试侧已验证（[\_scenarios_trace.py](file:///f:/Coding/Factor_Trading_v3.0/tests/_scenarios_trace.py#L230-L271)） | 需只读访问 |
| 触发分支原因 | ❌ | `should_trigger` 三处 `return True`（[rebalance.py](file:///f:/Coding/Factor_Trading_v3.0/core/rebalance.py#L137-L173)），只写 `logger.info` | 需离线复算或加只读字段 |
| 订单稳定 ID | ❌ | `PendingOrder` 无 id（[pending.py](file:///f:/Coding/Factor_Trading_v3.0/core/pending.py#L77-L95)）；有 `status/retry_count/execute_date` | 运行期 seq 补齐 |
| 拒单原因 | ⚠️ | 引擎分支可知（L1171/L1175/L1184/L1193/L1198/L1209/L1221/L1243），未落盘 | 打点即得 |
| 成交上下文 | ✅ | 调用点持有 order（L1233/L1799） | 可关联 |
| 逐日逐股持仓 | ⚠️ | 内存快照 `positions`（tracker L404），CSV 只写 `position_count`（[L548-L563](file:///f:/Coding/Factor_Trading_v3.0/core/tracker.py#L548-L563)） | 需新增导出 |
| 策略身份 | ⚠️ | 仅 git commit + `factor_files`（[config.py](file:///f:/Coding/Factor_Trading_v3.0/core/config.py#L477)） | 外部注入 |
| 平仓原因 | ⚠️ | `delisted`（L1006）与 `final_liquidation`（L701）可传；stop 类不存在 | §13.8 |

### 13.3 最小 seam 清单（按侵入度）

| ID | 位置 | 动作 | 控制流影响 | 关闭时 | 侵入度 |
|---|---|---|---|---|---|
| **SEAM-1** | `_process_trading_day` L790-792 | 记录 `triggered`、trigger 类名、入参摘要 | 无 | 无 collector 即 return | 极小 |
| **SEAM-2** | `_execute_rebalance` L1566-1571 | 记录 targets/weights/信号值 | 无 | 同上 | 极小 |
| **SEAM-3** | **4 处订单创建位**（F-01 修订）：再平衡 [L1686-L1698](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1686-L1698)；强平/换月 `_queue_urgent_order`（[L515-L531](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L515-L531)，`_kind` 豁免）；fallback `_try_fallback_order`（[L1297-L1302](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1297-L1302)，立即成交） | 给 order 分配 `order_seq`（`id(order)` → seq 的**内存映射**，按创建顺序） | 无 | 无 collector 即 return | 小 |
| **SEAM-4** | **14 处** `continue`/丢弃 前（F-05 修订）：队列路径 7 处（L1171/L1175/L1184/L1193/L1198/L1209/L1221）+ 次日路径 7 处（L1750/L1757/L1761/L1765/L1771/L1784/L1789） | 记录拒单码（共享只读分类器） | 无 | 同上 | 中（点位多） |
| **SEAM-5** | L1237-1240 / L1801-1803 + fallback [L1302-L1307](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1302-L1307) | 成交与 `order_ref` 关联（F-03 修订：fallback **双登记**——fallback_order 行 + 原单 `executed_by_fallback`，fill 记 `replaces_order_ref`） | 无 | 同上 | 小 |
| **SEAM-6** | `_force_liquidation` L931-990 | 记录 `reason`（`stocks` 入参 / `final_liquidation`） | 无 | 同上 | 小 |
| **SEAM-7** | L795-808 日末 | 导出逐股持仓（读 `tracker.get_all_positions()`） | 无 | 同上 | 小 |

**设计要点**：所有 seam 只做「读变量 + 追加到 collector」，不改任何返回值/分支条件；collector 为 `None` 时每个 seam 是一次 `if self._trace is None: return`。这是 I2「关闭时产物字节级不变」的机械保证。

**末行覆写（F-04 修订）**：末日时序为 `_process_trading_day`（含 DAY_END）→ `_snapshot_unclosed_positions` → `_force_liquidation`（直接成交、无订单对象）→ `_refresh_last_nav`（[L859-L869](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L859-L869)，仅刷 L6）。SEAM-7 若只挂 DAY_END，末行持仓/NAV 不含强平。trace 须在 `_refresh_last_nav` 同位**覆写 trace_day 末行**（持仓/现金/NAV），与 `LayerDumper.update_last_nav` 语义对齐。

**不做的事**：不改 `execute_order` 签名（返回值已够用）；不给 `PendingOrder` 加字段；不给 `Trade` 加 `reason`（改用 `trace_fill` 关联表）。

### 13.4 主键与表结构（字段级）

#### 13.4.1 主键（对 S1 的修订）

详细分析发现：`manifest.run_id` 在**运行结束时**才由 `uuid.uuid4()` 生成（[manifest.py](file:///f:/Coding/Factor_Trading_v3.0/core/manifest.py#L160-L162)），运行期 trace 无法预先知道。因此：

- `trace_id = f"{date}|{stock}"`（运行内唯一）
- `order_ref = f"{trace_id}|{side}|{order_seq:05d}"`
- `fill_ref = f"{order_ref}|{fill_seq}"`
- **run 级关联**放到 `alignment.json`：`{manifest_run_id, manifest_input_fingerprint, trace_file_sha256}`

这样既满足 I4 确定性（同输入 → 同序列），又不引入「先写占位再回填」的 append-only 违规。**S1 原文的 `run_id` 前缀据此修订。**

#### 13.4.2 三张宽表

**`trace_day.csv`**（日 × 标的，仅「有动作」行）

| 列 | 类型 | 来源 |
|---|---|---|
| `date` / `stock` / `trace_id` | str | — |
| `signal` | float? | `daily_signal[stock]` |
| `target_weight` / `target_qty` / `current_qty` / `is_exit` | float/int/bool | `TargetPosition` |
| `tradable` / `buyable` / `sellable` | bool | universe 掩码 |
| `position_qty` / `position_value` | int/float | tracker 日末 |
| `close_reason` | str? | SEAM-6（仅平仓日） |
| `nav` | float | tracker 日末 |

**`trace_order.csv`**

| 列 | 类型 | 来源 |
|---|---|---|
| `order_ref` / `trace_id` / `date` / `stock` / `side` | str | SEAM-3 |
| `qty` | int | order |
| `status` | str | `created → filled / executed_by_fallback / retry / dropped / cancelled / expired`；终态以 SEAM-5/SEAM-4 事件为准 |
| `reject_reason` | str? | SEAM-4 闭集 |
| `retry_count` / `create_date` | int/str | `create_date` 取 order；`retry_count` 为 **collector 自计数**（每次 `on_order_rejected` +1；引擎字段仅成交路径递增，F-20 修订） |
| `fallback_stock` | str? | 原单被替补成交时回写（[L1307](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1307)） |

> **F-02 修订（事实源）**：`filled_qty / execute_date / execute_price` **不得**取自 order 对象——次日路径成交后从不调 `mark_executed`（[L1799-L1805](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1799-L1805)，`status` 停留 `PENDING`、字段保持 `None`），仅队列路径（L1239）可信。三者一律由 **SEAM-5 成交关联**（fill）派生回填。

**`trace_fill.csv`**

| 列 | 类型 | 来源 |
|---|---|---|
| `fill_ref` / `date` / `stock` / `side` | str | SEAM-5 |
| `order_ref` | str | 关联订单；**`"direct"` 哨兵**表示无订单的直接成交（F-08：`_force_liquidation`/退市结算直接 `execute_order`，不创建 `PendingOrder`，[L947-L949](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L947-L949)） |
| `replaces_order_ref` | str? | fallback 成交所替代的原单（F-03） |
| `qty` / `price` / `amount` / `cost` / `net_amount` / `multiplier` | int/float | `Trade` |

#### 13.4.3 `alignment.json`（验证对齐）

```json
{
  "schema_version": "1.0",
  "manifest": {"run_id": "...", "input_fingerprint": "sha256:..."},
  "counts": {"orders": 0, "fills": 0, "direct_fills": 0},
  "reconcile": {
    "qty_by_side": {"BUY": 0, "SELL": 0, "SELL_SHORT": 0, "BUY_TO_COVER": 0},
    "amount_sum": 0.0, "cost_sum": 0.0,
    "trades_csv_amount_sum": 0.0, "snapshots_final_nav": 0.0,
    "residual": 0.0
  },
  "gates": {"golden": "not_run", "p059": "not_run"},
  "missing": []
}
```

- `residual` 判定沿用 `RESIDUAL_TOL = 1e-8`（同源 [change_report.py](file:///f:/Coding/Factor_Trading_v3.0/core/change_report.py)）。
- `gates` 只记录**调用方传入**的门禁快照，不在报告内跑测试（避免重入）。
- **对账规则（F-08 修订）**：`counts.orders` 与 `counts.fills` **不必相等**——差额 = `direct_fills`（强平/退市无订单）+ fallback 双登记；对账以「Σfill.amount = trades.csv Σamount」「fill 股数守恒」为准，订单仅作过程记录。
- **残差公式（F-13 同步，与 DESIGN §8 一致）**：`signed(qty)` 对 `BUY`/`BUY_TO_COVER` 取 `+qty`、对 `SELL`/`SELL_SHORT` 取 `−qty`；`residual` 第三项为**逐标的带符号流量恒等式** `max_stock |Σ signed fill.qty(stock) − Δposition.qty(stock)|`——四方向统一符号后，期货/融券（P-050）与股票多头共用同一公式。

#### 13.4.4 行数估算与默认过滤

| 口径 | 行数/年 | 体积/年 | 结论 |
|---|---|---|---|
| 全市场 × 全历史（5000 × 250） | 125 万 | 约 200 MB | **不可默认** |
| 仅「持仓 ∪ 目标 ∪ 订单 ∪ 成交 ∪ 拒单」 | 约 3-8 万 | 约 5-15 MB | **默认** |
| 单票全周期（drill-down） | ≤ 数万 | < 5 MB | 视图按需 |

默认过滤规则写入 S3；`--full` 供研究用。

### 13.5 视图三选一

| 方案 | 依赖 | 交互 | 体积 | 许可/维护 | 建议 |
|---|---|---|---|---|---|
| **V1 内联 SVG/HTML 自绘** | 0 | 点击日期/标的切换（vanilla JS） | 生成器 ~300 行；产物 < 2 MB | 自维护 | **B1/B3 默认** |
| **V2 Lightweight Charts** | 35 kB JS（vendoring） | 缩放/十字光标 | +35 kB | Apache-2.0，需登记第三方资产 | 可选，需 U-P061-5 批准 |
| **V3 Datasette** | `datasette` Python 包 | 最强（SQL 过滤/钻取） | 依赖安装 | 外部包 | 仅 `--sqlite` 可选 |

### 13.6 与 `change_report` 的边界

| 维度 | `change_report` | P-061 trace |
|---|---|---|
| 目的 | 两次运行的**层差异**是否可解释 | 单次运行的**因果链** |
| 输入 | 两份 `L1-L6` 目录 | 运行期事件 + 产物 |
| 输出 | `ChangeReport`（residual/attribution_complete） | `trace_*.csv` + `alignment.json` + HTML |
| 复用 | — | **只读复用** L1/L2 掩码语义、L4/L5 字段名、`RESIDUAL_TOL` |
| 禁止 | — | 不重算掩码、不另立第二套指标口径 |

`trace_report.py` 在检测到同目录存在 L1-L6 时，做一次**交叉校验**（订单/成交条数与 L4/L5 对齐），否则在 `missing[]` 标注并跳过。

### 13.7 分期、验收与回退

| 期 | 交付 | 验收 | 回退 |
|---|---|---|---|
| **B1（=M-A）** | `scripts/trace_report.py` 读现有 5 类产物 → 单文件 HTML + `missing.json` | 对任意既有 `output/` 可生成；离线可开；不写回 | 删脚本即回退 |
| **B2** | SEAM-1..7（默认关）+ 三宽表 + `alignment.json` | 残差 `<1e-8`；五问（§1.3）中 1/2/3/5/6 可答；I2 字节级不变；**末日 trace_day 行含强平后终值**（F-04，仿 `update_last_nav`） | 关 `trace_dir` 即回退 |
| **B3** | 单票时间轴视图（V1 或 V2）+ drill-down | 一屏看完 factor→target→order→fill→close；纯离线 | 视图为只读产物 |

### 13.8 能力上限（必须提前说明）

1. **stop 类平仓原因在现有引擎中不存在**：`core/stops.py` 只在测试与 `scripts/external_benchmark/verify_p045.py` 中被调用，`engine_v2` 零引用。策略若在上游调用 `apply_stops`，其结果只是「目标权重变 0」，到达引擎时已与普通再平衡无差别。**因此 `stop_loss/trailing_stop/take_profit/time_stop` 四个值在 B2 中不会出现**，除非把 P-045 接入主链（行为变更，见 U-P061-7）。
2. **B2 实际可回答的平仓原因**：`rebalance`、`final_liquidation`、`delisted`。若策略侧自愿通过 `cfg.trace_labels` 传原因，可扩展。
3. **触发分支原因**：不加只读字段时，只能记录「trigger 类名 + 配置」，具体命中哪一条需用同一份数据离线复算；复算脚本本身属 B2 交付。
4. **策略身份**：`cfg` 无 strategy 字段，B1/B2 由调用方显式传 `--strategy name@version`；否则只能靠 git commit + `factor_files` 推断。

### 13.9 附带观察（非本批范围，建议单独登记）

| # | 观察 | 影响 |
|---|---|---|
| O1 | `engine_v2` 调 `should_trigger` 只传 `signal`/`portfolio_value`，**从不传 `volatility`**（L784-788） | `ConditionalTrigger` 的波动率分支（rebalance.py L166-173）在回测中**永不命中** |
| O2 | `PendingOrder` 无 `reason` 字段，`LayerDumper.record_orders` 的 `getattr(order, "reason", "rebalance")` 恒取默认值 | 六层 L4 的 `reason` 列为常量，不具信息量 |
| O3 | `trades.csv` 样例（`output/`）头为 `stock,side,quantity,price,date,amount,cost`，缺 `net_amount` | 与当前 `TradeLog.get_trades_df` 列集不一致，疑为旧产物；对账时需按列名存在性处理 |
| O4 | 逐日逐股持仓只存在于内存快照，CSV 只写 `position_count` | 第 7 跳与 NAV 逐股归因必须依赖 B2 新表 |

### 13.10 决策树（U-P061-2 × U-P061-4）

| 组合 | 可回答的跳 | 结论 |
|---|---|---|
| M-A + 不加 seam | 1（弱）/3（弱）/5（弱）/6 | 只能「看已有产物」，回答不了为什么买/卖 |
| **M-B + 允许 seam** | **1-6 全量；7 限 rebalance/final_liquidation/delisted；8 对齐** | **推荐** |
| M-B + 不加 seam | 1/2/3/5（弱）/6；4 需复算；7 仅 final_liquidation | 结论可信度下降，G-05/G-06 不闭合 |
| M-C | 同 M-B + 交互过滤 | 依赖治理成本上升 |
| M-D | 同 M-B + 运行时指标 | 部署复杂度与项目约束冲突 |

---

## 14. Step 2 复审修订记录（F-01..F-08 全闭合，2026-11-24）

> 复审人 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash（RULE-5）；证据与处置详见 [REVIEW_p061_step2](REVIEW_p061_step2.md)。

| ID | 级别 | 发现（证据） | 修订落点 |
|---|---|---|---|
| **F-01** | P2 | SEAM-3 漏计 2 处订单创建位：`_queue_urgent_order`（强平/换月，L515-531）与 `_try_fallback_order`（L1297-1302，立即成交）均 `create_pending_order` → 实际 **4 处** | §13.3 SEAM-3 |
| **F-02** | P2 | **执行字段事实源错误**：次日路径成交后从不 `mark_executed`（L1799-1805，`status` 停留 `PENDING`、`execute_date/execute_price=None`），仅队列路径可信 | §13.4.2 trace_order：执行字段一律由 SEAM-5 fill 派生回填 |
| **F-03** | P2 | **fallback 跨标的成交**：fill 属 `fallback_stock`，但 `mark_executed(original_order)`（L1302-1307）——一 fill 两 order_ref | §13.4.2 trace_fill 增 `replaces_order_ref`；SEAM-5 双登记；状态机增 `executed_by_fallback` |
| **F-04** | P2 | **末日时序**：DAY_END（SEAM-7 挂点）早于 `_force_liquidation`/`_refresh_last_nav`（run 循环 L695-702）→ 末行持仓/NAV 不含强平 | §13.3 增「末行覆写」（仿 `update_last_nav`，挂 `_refresh_last_nav` 同位）；§13.7 B2 验收补此项 |
| **F-05** | P3 | SEAM-4 打点计数 12 → **14**（队列 7 + 次日 7） | §13.3 SEAM-4 |
| **F-06** | P3 | S9 退出码「2=缺产物」与 `change_report` 实际（仅 0/1，缺层抛 `MissingLayerError`）不符 | §6 S9 改 0/1 对齐 |
| **F-07** | P3 | `_kind ∈ {liquidation, roll}` 订单豁免取消/过期（L1089-1091 / L1122-1124）；再平衡日 `cancelled` 批量发生 | §6 S4 状态机补注 |
| **F-08** | P3 | `_force_liquidation` 直接 `execute_order` 无订单对象（L947-954）→ `trace_fill.order_ref` 需 `"direct"` 哨兵；`orders ≠ fills` 属合法态 | §13.4.2 + §13.4.3 对账规则（`direct_fills` 计数） |
| **F-09** | P3 | 落修订时自查发现：§6 S1 仍写旧主键 `run_id:{date}:{stock}`，与 §13.4.1 修订（`{date}|{stock}` + alignment 关联）矛盾 | §6 S1 已对齐 §13.4.1 |

**设计原则修正（F-02/F-03/F-08 共同指向，作为 DESIGN 输入）**：**以成交为事实源、订单为过程记录**——金额/股数对账只认 fill ↔ `trades.csv` ↔ NAV 三源，订单行的执行字段一律由 fill 派生。

