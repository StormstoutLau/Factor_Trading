# IMPL：P-061 全周期可追溯性与可视化审计（B1-B3 实施方案）

> **批次**：P-061 ｜ **档位 T1**
> **上游**：[RESEARCH_p061](RESEARCH_p061_observability_traceability.md)（§13/§14）· [DESIGN_p061](DESIGN_p061_observability_traceability.md)（DD1-DD12 / S1-S8 / §18）· [REVIEW_p061_step2](REVIEW_p061_step2.md) · [REVIEW_p061_step4](REVIEW_p061_step4.md)
> **裁决**：U-P061-1..7 闭合；U-P061-8..10 按复审建议列执行（`audit_*` 命名 / B1 先独立合并 / 不引入 Lightweight Charts）
> **作者**：DeepSeek-V4.1-Flash（Step 6 必须 reviewer ≠ 作者）
> **状态**：Step 5 实施方案完成；Step 6 异构复审 PASS-WITH-COMMENTS（[REVIEW_p061_step6](REVIEW_p061_step6.md)，F-16..F-21 闭合，§9）；**Step 7 CHECKLIST 冻结**（[CHECKLIST_p061](CHECKLIST_p061_traceability.md)，64 项 / 37 例，零预填）；**Step 8 一致性复审完成**（F-S8-P061-1：§4.3/§5 落「B1 临时常量 + S5-2 强制收敛」决策，CHECKLIST §10）；**Step 9 TDD 落码完成**（S5-1..S5-5：37 例全绿 / collect 1594 / mypy 162·0 / black 336；CHECKLIST §11，commit `7bf6b38`/`64552d6`/`cc36422`）；**批次关闭（F3 64/64，2026-11-24）**
> **硬约束**：默认关闭零行为（I1/I2）· 不改 `Trade`/`PendingOrder`/`pending.py`（I3）· 零新依赖（I10）· 不重录 golden（G2）

---

## 1. 范围与交付

| 项 | 内容 |
|---|---|
| 交付 | `core/trace.py`、`scripts/trace_report.py`、4 个测试文件（**37 例**）、`config`/`engine_v2`/`cli` 最小 seam |
| 产物 | `trace_day.csv` / `trace_order.csv` / `trace_fill.csv` / `alignment.json` / `trace.html` / `missing.json` |
| 批次 | B1 报告（零行为）→ B2 seam+采集 → B3 视图与标注 |
| 不交付 | P-045 stops 接入（U-P061-7 独立批次）、SQLite/Datasette、CI 改动、Streamlit 业务改造 |

### 1.1 文件与用例分布

| 文件 | 类型 | 例数 | 批次 |
|---|---|---|---|
| `core/trace.py` | 新增（~320 行） | — | B2 |
| `scripts/trace_report.py` | 新增（~380 行） | — | B1 |
| `tests/test_p061_trace_collector.py` | 新增 | T-A01..A10 = **10** | B2 |
| `tests/test_p061_trace_seams.py` | 新增 | T-B01..B15 = **15** | B2 |
| `tests/test_p061_trace_report.py` | 新增 | T-C01..C08 = **8** | B1 |
| `tests/test_p061_trace_e2e.py` | 新增 | T-D01..D04 = **4** | B3 |

生产改动：`core/config.py`（+2 字段）、`core/engine_v2.py`（S1-S8）、`cli.py`（+2 参数）、`web/streamlit_app/pages/01..05`（B3 各 +1 行标注）。

---

## 2. 外部源码案例锚点（X1-X14）

> 2026-11-24 实际打开核对；GitHub 用 `raw.githubusercontent.com`，文档用官方站点。**仅作方案对照，不复制代码、不引入依赖**。

### 2.1 身份、事件与重放（X1-X3）

| X | 来源 / 位置 | 可借鉴规则 | URL |
|---|---|---|---|
| **X1** | NautilusTrader《Event Sourcing》Correlation model | **三层身份**：`correlation_id`（整条工作流）/ `causation_id`（直接父消息）/ `command_id·event_id·report_id`（本条消息）；`seq` 是**唯一重放顺序权威**，时间戳只辅助解释 | https://nautilustrader.io/docs/latest/concepts/event_sourcing/ |
| **X2** | 同上 Entry model / Capture flow | 每条 entry 含 `seq / topic / payload_type / payload / headers / entry_hash`；**重复派发按消息身份在有界窗口去重**；**fail-stop 不中断运行**（tap 失败只停止记录） | 同 X1 |
| **X3** | `nautilus-event-store` README（Rust crate） | 存储模型：entries 按单调 `seq`，二级索引 `client_order_id`/`venue_order_id`，**run 开始写 manifest、结束时 seal**；`Durability::Immediate`；Verifier 校验 entry hash、seq 缺口、manifest 状态 | https://raw.githubusercontent.com/nautechsystems/nautilus_trader/master/crates/event_store/README.md |

**对本项目**：DD1 的「业务主键 + 全运行 `order_seq`」与 X1 的 correlation/seq 分层同构；X2 的「fail-stop 不中断」直接支撑 DD12；X3 的「manifest 始末」对应既有 `manifest.json` + 新增 `alignment.json` 的分工。

### 2.2 订单状态机与原因闭集（X4-X8）

| X | 来源 / 位置 | 可借鉴规则 | URL |
|---|---|---|---|
| **X4** | zipline `finance/order.py` `ORDER_STATUS` | 状态枚举 `OPEN / FILLED / CANCELLED / REJECTED / HELD`；`status` 为属性：`open_amount == 0 → FILLED` | https://raw.githubusercontent.com/quantopian/zipline/master/zipline/finance/order.py |
| **X5** | 同上 `Order.reject/hold` | **原因随状态一起落库**：`reject(reason)` / `hold(reason)` 同时写 `self.reason`；`to_dict()` 输出 `status` | 同 X4 |
| **X6** | 同上 `Order.make_id` | `id = uuid.uuid4().hex`——**随机主键不可复现**（反例；本项目改用确定性 `order_seq`） | 同 X4 |
| **X7** | backtrader `order.py` | 9 态 `Created/Submitted/Accepted/Partial/Completed/Canceled/Expired/Margin/Rejected`；`refbasis = itertools.count(1)` 提供**单调唯一 ref** | https://raw.githubusercontent.com/mementum/backtrader/master/backtrader/order.py |
| **X8** | Freqtrade 回测报告 Exit Reason Stats | 按 `roi / exit_signal / force_exit / stop_loss` **分组统计**（Exits / Avg Profit% / Tot Profit / Duration） | https://docs.freqtrade.io/en/2026.5/backtesting/ |

**对本项目**：S4 的 `created→filled/retry→expired/cancelled` 与 X4/X7 同层级；X7 的计数式 ref 正是 DD1 的做法；X8 证明「原因分组」是排查的第一视图，对应 HTML 的日视图与 `close_reason` 汇总。

### 2.3 原因词表（X9）

| X | 来源 | 可借鉴规则 | URL |
|---|---|---|---|
| **X9** | Freqtrade Strategy Callbacks `confirm_trade_exit` | `exit_reason` 闭集：`roi / stop_loss / stoploss_on_exchange / trailing_stop_loss / exit_signal / force_exit / emergency_exit` | https://docs.freqtrade.io/en/2026.5/strategy-callbacks/ |

**对本项目**：S5 的 `CLOSE_REASONS` 同构；差异是 Freqtrade 面向单笔交易退出，本项目把 `reject_reason`（订单未成）与 `close_reason`（持仓退出）拆开（D-03）。

### 2.4 表结构与只读视图（X10-X12）

| X | 来源 | 可借鉴规则 | URL |
|---|---|---|---|
| **X10** | OpenLineage Object Model | Run 的 `runId` 由客户端生成 UUID（建议 UUIDv7）；`RunFacets.parent` 表达父子；`outputStatistics` 记录**行数/字节数**；多次更新是**追加式** | https://openlineage.io/docs/next/spec/object-model/ |
| **X11** | W3C Trace Context §3.2.2.3 | `trace-id` = **16 字节 / 32 hex**，全零非法；`parent-id` = 8 字节；另有唯一性与随机性专门章节 | https://www.w3.org/TR/2020/REC-trace-context-1-20200206/ |
| **X12** | QuantStats `reports.py` `html()` | 读模板 `report.html` → `tpl.replace("{{...}}", ...)` 逐项填充 → 图片 base64 内联 → **单文件 HTML**；`template_path` 可替换 | https://raw.githubusercontent.com/ranaroussi/quantstats/main/quantstats/reports.py |

**对本项目**：X10 支撑 `alignment.json` 的 `counts + outputStatistics` 形态；X11 用于约束 `trace_id` 非空/非零（业务键天然满足，不做随机化）；X12 是 V1 视图的直接范式（模板占位符 + 内联资产，零 CDN）。

### 2.5 确定性与写入（X13-X14）

| X | 来源 | 可借鉴规则 | URL |
|---|---|---|---|
| **X13** | Python `uuid` 文档 | `uuid4()` 为随机 UUID——**不可作为可复现主键** | https://docs.python.org/3/library/uuid.html |
| **X14** | pandas `DataFrame.to_csv` | `lineterminator` **默认 `os.linesep`**（Windows `\r\n` / Linux `\n`）→ 跨平台字节不同；`float_format` 可选；`na_rep` 默认空串 | https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html |

**对本项目**：I4「同输入同字节」限定在**同一平台**（CI 为 Linux，本地 Windows）；`trace` 落盘固定 `lineterminator="\n"`、`encoding="utf-8"`、`index=False`，避免操作系统差异。

---

## 3. 与社区实现的语义分歧登记（锁定现状，Step 6 复核）

| ID | 分歧 | 本项目选择 | 依据 |
|---|---|---|---|
| **D-01** | zipline 用随机 `uuid4` 作订单 ID | **确定性 `order_seq`**（全运行递增） | X6/X13 反例；I4 要求可复现 |
| **D-02** | zipline 有 `HELD`（挂起）态 | 不引入；用 `retry`（仍在活跃集）表达 | 本引擎无 hold 语义；避免新增状态 |
| **D-03** | Freqtrade 单一 `exit_reason` | **拆两列**：`reject_reason`（订单未成交）/ `close_reason`（持仓退出） | 本引擎订单与持仓解耦；统一词表会混淆 |
| **D-04** | Nautilus 存二进制 payload + entry_hash | 存人读 CSV，无哈希链 | 目标是事后排查，不是重放引擎；体积可控 |
| **D-05** | OpenLineage/W3C 用随机 ID | 业务键 `{date}|{stock}` + 确定性 seq | I4；run 关联靠 `alignment.json` |
| **D-06** | Nautilus 在 run 开始写 manifest | 沿用既有 P-011「run 结束写 manifest」，trace 独立落盘，事后由报告侧 join | 不改既有 manifest 契约 |

---

## 4. 实施卡（逐用例）

> 命名与 docstring 首行沿用 DESIGN DD2：`T-A01 | oracle=closed-form`。oracle 词表：`closed-form / cross-check / invariant / contract / boundary / state / manual`。

### 4.1 `core/trace.py`（B2，T-A01..A10）

**落码要点**：`TraceConfig(out_dir, full)`；`TraceCollector` 纯内存追加，`finalize()` 统一写 4 文件；`classify_reject()` 为纯函数；所有方法首行 `if not self.enabled: return`；落盘固定 `lineterminator="\n"`（X14）；`OSError` 上抛由引擎捕获（DD12）。

| T-ID | 场景 / 步骤 | 断言 | oracle |
|---|---|---|---|
| T-A01 | 构造 `TraceConfig(out_dir=None)`/collector 禁用，依次调用全部 hook + finalize | 无目录、无文件；`enabled=False`；无异常 | contract |
| T-A02 | 同日同票连续创建 3 单（同 side/qty），第 4 单换 side | 4 个 `order_ref` 互不相同且顺序稳定；重复构造两次结果相同 | closed-form |
| T-A03 | `classify_reject` 遍历 8 组分支入参（涨停/跌停/停牌/ST/无价/现金不足/无持仓/默认） | 输出 ∈ `REJECT_REASONS`；逐项与预期值相等 | cross-check（对照 `_scenarios_trace` 词表） |
| T-A04 | 模拟两日活跃集：A 成交、B 仍活跃、C 消失且 status=EXPIRED | 状态分别为 `filled / retry / expired` | state |
| T-A05 | fallback：替补单成交 + 原单标 `executed_by_fallback` | fill 行 `replaces_order_ref` 指向原单；原单行 `fallback_stock` 正确 | state |
| T-A06 | 直接成交（order=None, direct=True） | `trace_fill.order_ref == "direct"`；`counts.direct_fills` +1；`orders != fills` 不报错 | boundary |
| T-A07 | 先 `on_day_end` 写末日行，再 `overwrite_last_day` 传新持仓/NAV | 文件仅一行（覆盖非追加），值等于后传值 | boundary |
| T-A08 | `finalize()` 后检查 4 文件 | 文件名/列序/表头与 DESIGN §7.1 完全一致；`alignment.schema_version == "1.0"` | contract |
| T-A09 | 构造 fills：BUY 100@10、SELL 40@12；trades_df 同值；终值 NAV 与快照一致 | `residual == 0`；篡改 SELL 金额 +1 → `residual > 1e-8` | closed-form |
| T-A10 | `full=False` vs `full=True`，传入 1 个目标 + 1 个非目标 signal | 前者 1 行、后者 2 行（含非目标 `target_qty=0`） | boundary |

**边界**：`date` 统一 `pd.Timestamp` → `%Y-%m-%d`；`signal` NaN 写空串（`na_rep=""`）；`positions` 为 `{stock: (qty, market_value)}`。

### 4.2 `engine_v2` seam（B2，T-B01..B15）

**落码要点**（严格按 DESIGN §6）：S1 在 `should_trigger` 之后、`if` 之前；S2 在 `_last_target_stocks` 之后；S3 覆盖 5 个注册位；S4 为 14 个 `continue` 前调用；S5 覆盖队列/次日/fallback/直接成交；S6 在强平循环内；S7 在 `DAY_END` 后；S8 插在 `_refresh_last_nav` 的 `dumper.enabled` 早退**之前**；终扫在 run 末 `mark_expired` 之后。注入优先级：`trace_collector` 参数 > `cfg.audit_trace_dir` > `None`。

| T-ID | 场景 | 断言 |
|---|---|---|
| T-B01 | 同 cfg 对跑：`audit_trace_dir=None` vs `=<tmp>` | 三 CSV sha256 相同；后者产 4 文件、前者不产；`input_fingerprint` 不同（预期）。**场景须 `enable_pending_orders=True`**（否则 `pending_order_events.csv` 不生成，三 CSV 退化为二；F-18/F-21） |
| T-B02 | 开启 trace 的标准 scenario | `trace_fill` 行数/金额和 == `trades.csv` |
| T-B03 | 同一 run 同时挂 `TraceRecorder`（P-059）与生产 collector | 日桶 positions/nav/fills 逐日一致（≤1e-9） |
| T-B04 | `method="N_days", n_days=5` × 20 交易日（F-21 精确化） | 每日 1 条 S1 记录（F-14）；`triggered=True` 恰 4 日（第 1/6/11/16 交易日；首日即触发已核验）；类名 `FixedIntervalTrigger` |
| T-B05 | 构造涨停/停牌/ST 三标的不可买 | `reject_reason` 分别 `limit_up / suspended / st_blocked` |
| T-B06 | 现金不足一日后补足 | 首日 `cash_short` 且仍活跃；次日成交 `filled`；`retry` 记录存在 |
| T-B07 | 卖出订单持仓已被清空 | 队列路径 `cancelled`（`cancel_order`）或 `no_position`；次日路径 `dropped` |
| T-B08 | `max_pending_days_buy=2`，连续 3 日不可买 | 第 3 日终态 `expired`；**collector 侧 `retry_count` = 2**（第 1、2 日被拒；F-20：引擎 `order.retry_count` 仅成交时递增，未成交恒 0，不可作事实源） |
| T-B09 | `enable_fallback=True` + 首选涨停 | 替补成交 fill `replaces_order_ref` 非空；原单 `executed_by_fallback` |
| T-B10 | 末日强平 | `close_reason=final_liquidation`；强平 fill `order_ref="direct"` |
| T-B11 | 退市结算 | `close_reason=delisted`；金额 = `last_close×(1+delist_return)×qty` |
| T-B12 | 末日 S8 覆写 | trace_day 末行 NAV == `snapshots.total_value.iloc[-1]`；持仓 == tracker 终态 |
| T-B13 | `event_log_path` + `audit_trace_dir` 同开 | 事件总线 seq 连续；trace 文件完整；两者互不影响 |
| T-B14 | 零成交 run，但含 **1 张 `cash_short` 存活订单**（未到期；F-17 终扫断言） | 4 文件均生成；`trace_fill` 仅表头；`alignment.fills == 0`；**run 末终扫后该订单终态 = `expired`**（run 末 `mark_expired` 置位 → `finalize(remaining_orders)` 落终态，验证 DESIGN F-10） |
| T-B15 | manifest 契约 | `manifest["config"]` 键集含 `audit_trace_dir/audit_trace_full`；同版本两次构建指纹相同 |

**边界**：T-B06 需构造「首日现金 < 所需」；T-B08 的 `is_expired` 含半衰期逻辑（`days_pending >= max` 先判），断言只取确定分支。

### 4.3 `scripts/trace_report.py`（B1，T-C01..C08）

**落码要点**：只用 stdlib（`argparse/json/pathlib/html`）+ pandas；模板字符串常量内联；退出码 0/1；`--check` 不写 HTML；缺失输入写 `missing.json` 不崩。**schema 常量（F-S8-P061-1）**：B1 落码时 `core/trace.py` 尚不存在，列名/闭集常量**临时自带于本脚本**；S5-2 交付 `core/trace.py` 后**必须收敛为 `from core.trace import`**（单一来源），收敛列入 S5-2 验收。

| T-ID | 场景 | 断言 |
|---|---|---|
| T-C01 | 构造对齐的 trace 目录 + manifest | exit 0；生成 `trace.html` + `missing.json` |
| T-C02 | 篡改 `trace_fill` 一行 amount | exit 1；stderr 含 residual |
| T-C03 | 删除 `manifest.json`（**辅助产物**，F-18 分级） | exit 0；`missing[]` 含 `manifest.json`；对照组：删除任一**核心产物**（`trace_*.csv` / `alignment.json`）→ exit 1 |
| T-C04 | 打开生成的 HTML，扫描文本 | 无 `http://`/`https://`；`<script>` 无 `src`；单文件可离线渲染 |
| T-C05 | 日视图渲染 | 含 targets/orders/fills/close 四段；缺列标 `—` 不抛异常；**页面顶部标注数据来源**（`trace_*.csv / alignment.json / manifest.json，只读渲染`，Step 6 Q7） |
| T-C06 | 同目录有 L1-L6 | 交叉校验计数写入 `missing.json` 的 `cross_check`；无 L1-L6 时该键为 `skipped` |
| T-C07 | `--check` | 不写 `trace.html`；只输出 JSON/退出码 |
| T-C08 | 同一输入生成两次 | 两文件字节相同（无时间戳/随机顺序） |

### 4.4 端到端（B3，T-D01..D04）

| T-ID | 场景 | 断言 |
|---|---|---|
| T-D01 | 固定 scenario 全链 run → 报告 | 五问逐条可答：①有目标无成交的单 → `reject_reason`；②卖出单 → `close_reason`；③同日 NAV 差异 → `alignment`；④挂起单 → `retry/expired`；⑤指纹+commit → 可复现 |
| T-D02 | 同输入两次 run | `trace_day/order/fill` 三文件字节相同 |
| T-D03 | `lint-imports` | C1/C2/C3 全绿；`core/trace.py` 仅 import stdlib+pandas |
| T-D04 | 计时：trace 开/关各跑同一 scenario | 增量 < 10%（取 3 次中位数） |

---

## 5. 实施顺序与门禁

| 步 | 动作 | 验收 |
|---|---|---|
| S5-1 | **B1**：`scripts/trace_report.py` + `test_p061_trace_report.py`（8 例） | `-k p061` = 8；G1/G5/G6 通过；无生产改动 |
| S5-2 | **B2**：`core/trace.py` + T-A（10 例） | `-k p061` = 18；`core/trace.py` 单文件 ≥80%；**`trace_report.py` schema 常量收敛为 `from core.trace import`**（F-S8-P061-1） |
| S5-3 | **B2**：`config` + `engine_v2` seam + `cli` + T-B（15 例） | `-k p061` = 33；G1-G3、G11、G12 通过 |
| S5-4 | **B3**：视图时间轴 + Streamlit 标注 + T-D（4 例） | `-k p061` = 37；G4/G13/G14 通过 |
| S5-5 | 全门禁 G1-G14 + covA 读数 | CHECKLIST 预填 |

**每步独立 commit**；B2 的 seam commit 单独一次，便于逐点复核与回滚。

---

## 6. 风险与回退

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| seam 误改控制流 | 中 | 高 | 每个 seam 仅「if + 调用 + return」；T-B01 三 CSV sha256；Step 6 逐点 diff |
| 14 个拒单点漏改/错序 | 中 | 中 | T-B05..B08 覆盖 4 类主因；Step 6 按行号清单核对 |
| `classify_reject` 与引擎判定漂移 | 中 | 中 | 纯函数 + 单测 T-A03；引擎只传布尔，不重算 |
| 末日两次快照导致末行错位 | 低 | 中 | T-B12 直接对比 `snapshots.iloc[-1]` |
| 跨平台 CSV 字节不同 | 中 | 低 | 固定 `lineterminator="\n"`（X14）；I4 限定同平台 |
| HTML 体积/性能 | 低 | 低 | 默认过滤 + 分日渲染；不内嵌原始 CSV |
| `audit_*` 与 `--trace-dir` 混淆 | 中 | 低 | help 文案明确「六层快照」vs「审计追溯」 |

**回退**：B1 删脚本；B2 关 `audit_trace_dir` + revert seam commit；B3 删视图产物。均不影响既有产物。

---

## 7. 验收清单（对应 DESIGN §15）

- [ ] G1-G14 全绿；`-k p061` = **37**
- [ ] 关闭/开启对跑：`trades.csv`/`snapshots`/`pending_order_events.csv` sha256 一致
- [ ] 样例 run `alignment.residual < 1e-8`
- [ ] T-D01 五问全部可答
- [ ] `core/trace.py` ≥80%；四包不低 0.5pp
- [ ] 生产 diff 仅 `config.py`/`engine_v2.py`/`cli.py`（+B3 文案）

---

## 8. Step 6 复审输入（已闭合，2026-11-24）

七问已由 [REVIEW_p061_step6](REVIEW_p061_step6.md) §3 逐条回答（GLM-5.3-Flash ≠ 作者）：① S1-S8 全为只读追加、S7/S8 时序正确；② S4 14 点一一对应，`failed_orders` 为重试容器不重复计数；③ 三 CSV sha256 足够（`performance_metrics.csv` 为 snapshots 派生量）；④ 闭集边界明确（cancel→cancelled / 消失且 PENDING→dropped / mark_expired→expired）；⑤ `order_seq` 在创建调用点即时分配，不受集合遍历影响；⑥ D-01..D-06 同意，且 F-20 补强了 D-01；⑦ HTML 须标注数据来源（并入 T-C05）。

---

## 9. Step 6 复审修订记录（F-16..F-21 全闭合，2026-11-24）

> 复审人 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash（RULE-5）；证据与七问回答见 [REVIEW_p061_step6](REVIEW_p061_step6.md)。**37 例总数不变**。

| ID | 级别 | 发现（证据） | 修订落点 |
|---|---|---|---|
| **F-16** | P3 | §2 标题写 X1-X13，实表覆盖 X1-X14 | §2 标题改 X1-X14 |
| **F-17** | P2 | F-10 终扫无专属验收断言：T-B14 无存活订单、T-B08 过期发生在 run 中段，均不经 run 末路径 | T-B14 扩展为「零成交 + 1 张 `cash_short` 存活订单 → 终扫 `expired`」 |
| **F-18** | P2 | DESIGN S9「1=…**或缺产物**」与 T-C03「manifest 缺失 → exit 0」直接矛盾 | **两级产物规则**：核心产物（trace_*.csv / alignment.json）缺失 → exit 1；辅助产物（manifest/snapshots/L1-L6/pending_events）缺失 → `missing[]` + exit 0（残差不可算则标 `degraded`）；DESIGN S9 同步；T-C03 补对照组 |
| **F-19** | P3 | `TraceConfig.out_dir: Path` 必填 vs T-A01「`TraceConfig(out_dir=None)`」类型矛盾 | DESIGN §5.1 改 `out_dir: Path \| None`（None → `enabled=False`） |
| **F-20** | P2 | 引擎 `retry_count` **仅在成交时递增**（`mark_partial`/`mark_executed_full`/队列 `mark_executed`，pending.py L169/L182/L390）；14 个拒单点与次日路径均不递增 → DESIGN §7.1 该列来源标 "order" 对「未成交即过期」恒为 0，T-B08 原断言「递增」必败 | 事实源改 **collector 自计数**（每次 `on_order_rejected` +1）；DESIGN §7.1 source 修正；T-B08 断言改「collector 计数 = 2 且终态 expired」 |
| **F-21** | P3 | T-B04「固定频率 5 日」未指定 method（weekly/monthly 凑不出确定 4 日）；T-B01 缺 `enable_pending_orders` 注记 | T-B04 明确 `N_days=5`（触发日 1/6/11/16，首日即触发已核验）；T-B01 补注记 |
