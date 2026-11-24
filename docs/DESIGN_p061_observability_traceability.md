# DESIGN：P-061 全周期可追溯性与可视化审计（B1-B3）

> **批次**：**P-061**（U-P061-1 闭合）｜**档位 T1**（新增 `core/trace.py` 与 `scripts/trace_report.py`，并在 `engine_v2` 加默认关闭的只读 seam；实现落 `tests/` + 生产 seam + 脚本）
> **上游**：[RESEARCH_p061](RESEARCH_p061_observability_traceability.md)（含 §13 详细方案、§14 复审修订）· [REVIEW_p061_step2](REVIEW_p061_step2.md)（PASS-WITH-COMMENTS，F-01..F-09 全闭合）
> **裁决**：U-P061-1..7 全部闭合（M-B 三期 / 允许最小 seam / stop 接入独立批次）
> **基线**：`4367775`；collect **1557**（1556 passed + 1 skipped）/ golden **22** / `-k p059` **63** / mypy **160·0** / black **330**
> **作者**：DeepSeek-V4.1-Flash（Step 4 复审须 reviewer ≠ 作者，RULE-5）
> **状态**：Step 3 DESIGN 完成；Step 4 异构复审 PASS-WITH-COMMENTS（[REVIEW_p061_step4](REVIEW_p061_step4.md)，F-10..F-15 闭合，§18）；Step 5 实施方案完成（[IMPL_p061](IMPL_p061_traceability.md)）；Step 6 IMPL 复审 PASS-WITH-COMMENTS（[REVIEW_p061_step6](REVIEW_p061_step6.md)，F-16..F-21 闭合，§19）；**Step 7 CHECKLIST 冻结**（[CHECKLIST_p061](CHECKLIST_p061_traceability.md)，64 项 / 37 例）；**Step 8 一致性复审完成**（F-S8-P061-3：§11.3 T-C03 补两级产物显式化，CHECKLIST §10）；**Step 9 落码完成**（37 例全绿 / collect 1594 / 四包 89.82·87.95·74.54·93.54 / trace.py 94.53%，commit `7bf6b38`/`64552d6`/`cc36422`）；**批次关闭（F3 64/64，2026-11-24）**；U-P061-8..10 按复审建议列执行

---

## 1. 目标与非目标

### 1.1 目标（可验收）

| # | 目标 | 验收读数 |
|---|---|---|
| O1 | 一次回测可回答 §1.3 五问（为什么买/卖、订单卡在哪、NAV 差异、可否复现） | T-D01 用固定 scenario 逐问断言 |
| O2 | `trace_fill` ↔ `trades.csv` ↔ `snapshots` 三源守恒 | `alignment.residual < 1e-8`（G13） |
| O3 | 追溯默认关闭时**零行为** | 关闭/开启两次运行的 `trades.csv`/`snapshots` sha256 相同（G12） |
| O4 | 单文件离线 HTML 可看「日 × 标的」与单票时间轴 | `trace.html` 无 `http://`/`https://` 引用（T-C04） |
| O5 | 与既有六层归因/事件总线**并存不冲突** | T-B13 + G3/G9 |
| O6 | 零新增依赖 | `pyproject.toml`/`uv.lock` 零 diff（G14） |

### 1.2 非目标（明确不做）

1. **不接 P-045 stops**（U-P061-7）：`stop_loss/trailing_stop/take_profit/time_stop` 本批不出现在产物中。
2. **不改 `Trade`/`PendingOrder` 数据结构**（F-02/F-03 结论：以 fill 为事实源）。
3. **不改 `pending.py`**：只使用既有 public API（`get_pending_orders` / `is_expired`）。
4. **不引入 SQLite/Datasette/Lightweight Charts**（M-C/V2 留 B3 可选，默认不启用）。
5. **不改 Streamlit 的业务逻辑**：仅加「demo 数据」标注（U-P061-5）。
6. **不改 CI workflows**、不新增 CI job（U-P061-6 三期后再议）。
7. **不覆盖 `engine_v3_vector`**（无订单/成交，不可追溯）。

---

## 2. 设计决策（DD1-DD12）

| ID | 决策 | 依据 |
|---|---|---|
| **DD1** | **主键**：`trace_id = "{YYYY-MM-DD}|{stock}"`；`order_ref = "{trace_id}|{side}|{order_seq:05d}"`；`fill_ref = "{order_ref}|{fill_seq}"`；`order_seq` 为**全运行递增**（避免同日同票多单撞键）。run 级关联只进 `alignment.json` | RESEARCH §13.4.1；`manifest.run_id` 运行结束才生成（[manifest.py](../core/manifest.py#L160-L162)） |
| **DD2** | **事实源原则**：金额/股数以 **fill** 为准；订单行 `status/filled_qty/execute_*` 只作过程记录，执行字段由 fill 派生 | F-02（次日路径不 `mark_executed`，[L1799-L1805](../core/engine_v2.py#L1799-L1805)） |
| **DD3** | **seam 形态**：`TraceCollector` 由构造函数注入（优先级高于 cfg，仿 `event_bus`）；所有 seam 统一 `if self._trace is None: return`，不改任何分支条件/返回值 | 仿 [engine_v2.py](../core/engine_v2.py#L409-L417) 的 `event_bus` 先例；I1/I11 |
| **DD4** | **配置命名避让**：新增 `audit_trace_dir` / `audit_trace_full` 两个字段，**不复用** `trace_dir` 名称——`cli.py --trace-dir` 已绑定 `dump_layers_dir`（[cli.py](../cli.py#L317-L319)）。CLI 新增 `--audit-trace-dir` / `--audit-trace-full` | 命名冲突实证 |
| **DD5** | **fingerprint 漂移声明**：新增 cfg 字段必然改变 `input_fingerprint`（`_jsonable(cfg)` 全字段入哈希）；golden 不依赖该值，`test_manifest` 的键集断言按 `dataclasses.fields` 自适应（[test_manifest.py](../tests/test_manifest.py#L130-L132)）。**不重录 golden**，但需在 T-B15 断言「同版本两次构建指纹相同」 | I2 / manifest 契约 |
| **DD6** | **双路径覆盖 + 共享分类器**：队列路径（7 点）与次日路径（7 点）共 **14 个拒单点**；分类逻辑抽为 `core.trace.classify_reject(...)` 纯函数，两条路径传同一组入参 | F-05；避免词表漂移 |
| **DD7** | **订单注册 5 位**：`_queue_urgent_order`、`_generate_rebalance_orders`、`_try_fallback_order`、`_generate_orders_via_policy`（policy 创建后统一注册）、以及 fallback 原单回写 | F-01 + policy 路径（[L1649-L1652](../core/engine_v2.py#L1649-L1652)） |
| **DD8** | **fallback 双登记**：fill 记 `replaces_order_ref`；替补单正常 `filled`，原单记 `executed_by_fallback` + `fallback_stock` | F-03（[L1302-L1307](../core/engine_v2.py#L1302-L1307)） |
| **DD9** | **直接成交哨兵**：`_force_liquidation`/退市结算不创建订单，`trace_fill.order_ref = "direct"`；`orders ≠ fills` 合法，差额记 `direct_fills` | F-08（[L947-L954](../core/engine_v2.py#L947-L954)） |
| **DD10** | **末日覆写**：在 `_refresh_last_nav` 同位覆写 `trace_day` 最后一行（持仓/现金/NAV），与 `LayerDumper.update_last_nav` 语义一致（[L859-L869](../core/engine_v2.py#L859-L869)） | F-04 |
| **DD11** | **状态对账在日末完成**：不在 `pending.py` 内部打点；每日末用活跃订单集合差分推导 `filled / retry / expired / cancelled`（复用 P-059 `TraceRecorder` 已验证的做法） | 零 `pending.py` 改动；[L1169-L1259](../core/engine_v2.py#L1169-L1259) |
| **DD12** | **失败不影响回测**：`finalize()` 的 `OSError` 只 `logger.warning`，与 manifest 写入同策略（[L1979-L1983](../core/engine_v2.py#L1979-L1983)） | I12 |

---

## 3. 文件布局

```
core/trace.py                        # 新增：collector + 闭集 + alignment（无 engine import）
scripts/trace_report.py              # 新增：CLI + 单文件 HTML（读 trace/output 目录）
tests/test_p061_trace_collector.py   # T-A01..A10（纯单元，2s）
tests/test_p061_trace_seams.py       # T-B01..B15（真实 engine + 合成数据）
tests/test_p061_trace_report.py      # T-C01..C08（CLI/HTML/边界）
tests/test_p061_trace_e2e.py         # T-D01..D04（端到端/确定性/依赖/性能）
docs/IMPL_p061_traceability.md       # Step 5 产出
docs/CHECKLIST_p061_traceability.md  # Step 7 产出
```

改动文件（生产）：`core/config.py`（+2 字段）、`core/engine_v2.py`（seam 与注入）、`cli.py`（+2 参数）、`web/streamlit_app/pages/0*.py`（B3 逐页加 demo 标注；实际为 `01_*`..`05_*`，无 `00_*`，F-15 修正）。

> 预计 **37 例**（T-A 10 / T-B 15 / T-C 8 / T-D 4，Step 5 可按实测微调并登记 F 号）。

---

## 4. 架构与数据流

```
              ┌─────────────────────────────── engine_v2.run() ───────────────────────────────┐
 触发 ──S1──▶ │ trigger.should_trigger ──▶ _execute_rebalance ──S2──▶ targets/weights           │
              │                                        │                                        │
              │                                  创建订单 S3（5 注册位）                          │
              │                                        ▼                                        │
              │            队列路径 _process_pending_orders ──S4(7)──▶ 成交 S5 ──▶ tracker         │
              │            次日路径 _execute_next_day_orders ──S4(7)──▶ 成交 S5 ──▶ tracker        │
              │                                        │                                        │
 平仓 ──S6──▶ │ _force_liquidation / _settle_delisted（direct fill）                             │
              │                                        ▼                                        │
 日末 ──S7──▶ │ update_market_values ──▶ DAY_END ──▶ S7 对账（活跃集合差分）                      │
 末日 ──S8──▶ │ _refresh_last_nav ──▶ 覆写 trace_day 末行                                        │
              └─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼  audit_trace_dir/
                         trace_day.csv · trace_order.csv · trace_fill.csv · alignment.json
                                         │
                                         ▼  scripts/trace_report.py
                              trace.html（单文件离线）+ missing.json
```

---

## 5. `core/trace.py` 设计

### 5.1 公开契约

```python
TRACE_SCHEMA_VERSION = "1.0"

REJECT_REASONS: frozenset[str]  # limit_up|limit_down|suspended|st_blocked|
                                # invalid_price|cash_short|no_position|expired|unknown
CLOSE_REASONS: frozenset[str]   # rebalance|final_liquidation|delisted|unknown
                                # stop_* 为保留值，本批不产生（U-P061-7）

@dataclass(frozen=True)
class TraceConfig:
    out_dir: Path | None        # None → collector.enabled=False（F-19，与 cfg.audit_trace_dir=None 对齐）
    full: bool = False          # False=仅「有动作」行；True=目标∪持仓全量

class TraceCollector:
    enabled: bool
    def on_trigger(self, date, trigger, triggered: bool) -> None
    def on_targets(self, date, rows: Sequence[Mapping[str, Any]]) -> None
    def on_order_created(self, order: Any) -> str
    def on_order_rejected(self, order: Any, reason: str) -> None
    def on_fill(self, trade: Any, order: Any | None, *,
                direct: bool = False, replaces_order_ref: str | None = None) -> None
    def on_close(self, date, stock: str, reason: str) -> None
    def on_day_end(self, date, active_orders: Sequence[Any],
                   positions: Mapping[str, tuple[int, float]],
                   cash: float, nav: float) -> None
    def overwrite_last_day(self, date, positions, cash: float, nav: float) -> None
    def finalize(self, trades_df: pd.DataFrame | None = None,
                 remaining_orders: Sequence[Any] = ()) -> list[Path]

def classify_reject(*, side: str, buyable: bool, sellable: bool, suspended: bool,
                    is_st: bool, exclude_st: bool, has_price: bool,
                    cash_short: bool, has_position: bool) -> str
```

- `on_order_created` 以 `id(order)` 建内存映射并分配 `order_seq`（按创建顺序，确定性）；不修改 order 对象。
- `on_day_end` 做活跃集合差分：上次活跃∩今日成交→`filled`；仍在活跃→`retry`；消失→按**存储的 `order.status` 解析终态**（`EXPIRED→expired` / `CANCELLED→cancelled` / 其余→`dropped`；[pending.py](../core/pending.py#L331) 确认活跃集含 PARTIAL，PARTIAL 跨再平衡存活按 retry 处理）。`reject_reason` 为**后写覆盖**（保留最后一次尝试原因）。
- **终扫（F-10）**：run 末 `pending_queue.mark_expired`（[L721-L722](../core/engine_v2.py#L721-L722)）**之后**，引擎以剩余活跃订单调用 `finalize(remaining_orders=...)`； collector 对这些订单按同一 `order.status` 解析机制落终态（含末日创建当日过期的订单）。差分与终扫共用解析逻辑，避免两套词表。
- `finalize` 依次写 4 个文件；`trades_df` 仅用于 alignment 内存对账；任何 `OSError` 向外抛由 engine 捕获（DD12）。

### 5.2 内部状态

| 状态 | 用途 |
|---|---|
| `_orders: dict[int, dict]` | `id(order)` → 行（`order_ref/side/qty/...`） |
| `_active_prev: set[int]` | 上一日活跃订单集合（差分用） |
| `_fills: list[dict]` | `trace_fill` 行 |
| `_day_rows: dict[(date, stock), dict]` | `trace_day` 行（末日可覆写） |
| `_pending_trigger` | S1 记录，S2 消费 |
| `_unknown_reasons: Counter` | 闭集外值计数（I6） |

### 5.3 排序与确定性

- 行按 `(date, stock, side, order_seq)` 稳定排序后落盘；不含任何当前时间/随机值。
- `alignment.json` 不含时间戳；`run_id` 只在报告侧从 `manifest.json` 读取（缺失则 `null`）。

---

## 6. `engine_v2` seam 清单（S1-S8）

| ID | 位置 | 传入 | 行为影响 |
|---|---|---|---|
| **S1** | `should_trigger` 调用后、`if should_rebalance:` **之前**（[L784-L792](../core/engine_v2.py#L784-L792)，F-14 前移） | 每日 `{date, trigger 类名, triggered(bool), kwargs 摘要}` | 无（≤1 行/日；非触发日也有记录，可答「为什么这天没调仓」） |
| **S2** | `_last_target_stocks` 之后（[L1566-L1571](../core/engine_v2.py#L1566-L1571)） | 每目标一行：`signal/target_weight/target_qty/current_qty/is_exit/tradable/buyable/sellable`；`full=True` 时额外传当日 `signal_row` 与三张掩码（生成全 universe 行） | 无 |
| **S3** | 5 个注册位：`_queue_urgent_order` [L526](../core/engine_v2.py#L526)、`_try_fallback_order` [L1297](../core/engine_v2.py#L1297)、`_generate_rebalance_orders` [L1686](../core/engine_v2.py#L1686)、policy 订单 [L1649-L1652](../core/engine_v2.py#L1649-L1652) | `order` | 无（返回 `order_ref` 由 collector 保存） |
| **S4** | 14 个拒单点（队列 7：L1171/L1175/L1184/L1193/L1198/L1209/L1221；次日 7：L1750/L1757/L1761/L1765/L1771/L1784/L1789） | `order, classify_reject(...)` | 无（`continue` 前追加） |
| **S5** | 队列成交 [L1237-L1240](../core/engine_v2.py#L1237-L1240)、次日成交 [L1799-L1803](../core/engine_v2.py#L1799-L1803)、fallback [L1302-L1307](../core/engine_v2.py#L1302-L1307)、直接成交 [L947-L954](../core/engine_v2.py#L947-L954) | `trade, order/direct` | 无 |
| **S6** | `_force_liquidation` 循环内 [L931-L954](../core/engine_v2.py#L931-L954) | `date, stock, reason`（`stocks` 入参 / `final_liquidation`） | 无 |
| **S7** | `DAY_END` 发射后 [L802-L808](../core/engine_v2.py#L802-L808) | `active_orders`（`get_pending_orders()` + `_next_day_orders`）、`{stock: (qty, market_value)}`、`cash`、`nav` | 无 |
| **S8** | `_refresh_last_nav` 内（[L859-L869](../core/engine_v2.py#L859-L869)） | 同上 | 无。**注意**：该函数首行 `if not dumper.enabled: return`——trace 覆写分支必须插在**早退之前**（默认 `dump_layers_dir=None` 时仍生效），不得挂在 dumper 分支内 |

**取消标记**：再平衡刷新前，对 `cancel_orders` 覆盖的股票逐单 `on_order_cancelled`（读 `get_pending_orders(stock=...)`，[L1330-L1335](../core/engine_v2.py#L1330-L1335)）；次日路径在 `_cancel_next_day_orders` 内标 `cancelled`（[L1093](../core/engine_v2.py#L1093)）。**不改 `pending.py`**。注意 `cancel_*` 仅作用于 PENDING（[pending.py](../core/pending.py#L451)），PARTIAL 订单跨再平衡存活、按 retry 继续跟踪。

**终扫调用（F-10）**：`run()` 中 `mark_expired(last_date)`（[L721-L722](../core/engine_v2.py#L721-L722)）之后、`_trace.finalize` 调用处，传入 `remaining_orders=self._trace 之外的剩余活跃订单`（队列 `get_pending_orders()` + `_next_day_orders`，此时应已为空或全为豁免单；非空则按 `order.status` 落终态）。

**注入与开关**（仿 `event_bus`）：

```python
# __init__(..., event_bus=None, trace_collector=None)
# setup():
if self._injected_trace is not None:
    self._trace = self._injected_trace
elif self.cfg.audit_trace_dir is not None:
    self._trace = TraceCollector(TraceConfig(self.cfg.audit_trace_dir, self.cfg.audit_trace_full))
else:
    self._trace = None
```

`run()` 末尾在 `_layer_dumper.finalize` 同位调用 `self._trace.finalize(trades_df)`，包 `try/except OSError`。

---

## 7. 数据契约

### 7.1 文件与列（列序固定，UTF-8）

| 文件 | 列 |
|---|---|
| `trace_day.csv` | `date, stock, trace_id, signal, target_weight, target_qty, current_qty, is_exit, tradable, buyable, sellable, position_qty, position_value, close_reason, nav` |
| `trace_order.csv` | `order_ref, trace_id, date, stock, side, qty, filled_qty, status, reject_reason, retry_count, create_date, execute_date, execute_price, fallback_stock` |
| `trace_fill.csv` | `fill_ref, order_ref, replaces_order_ref, date, stock, side, qty, price, amount, cost, net_amount, multiplier` |
| `alignment.json` | §8 |

- `status ∈ {created, retry, filled, executed_by_fallback, cancelled, expired, dropped}`。
- `filled_qty/execute_date/execute_price` 由 fill 派生（DD2），无 fill 时为 `0/""/""`。
- `retry_count` = **collector 自计数**（每次 `on_order_rejected` +1，成交不改；F-20 修订：引擎 `order.retry_count` 仅成交路径递增——`mark_partial`/`mark_executed_full`/队列 `mark_executed`，未成交场景恒 0，不可作事实源）。
- **过滤**：`full=False` 只写「目标 ∪ 持仓 ∪ 订单 ∪ 成交 ∪ 拒单」行；`full=True` 追加全 universe 的 `signal/tradable` 行（研究用）。

### 7.2 闭集

| 集合 | 值 |
|---|---|
| `REJECT_REASONS` | `limit_up, limit_down, suspended, st_blocked, invalid_price, cash_short, no_position, expired, unknown` |
| `CLOSE_REASONS` | `rebalance, final_liquidation, delisted, unknown`（`stop_*` 保留，本批不产生） |

闭集外值 → `unknown` + `_unknown_reasons` 计数（I6）。

### 7.3 体量

默认过滤下约 **3-8 万行/年**（5-15 MB）；`full=True` 为全市场全量（约 125 万行/年），仅研究用。

---

## 8. 对齐算法（`alignment.json`）

```
counts      = {orders, fills, direct_fills}
qty_by_side = Σ fill.qty 按 side（四方向：BUY / SELL / SELL_SHORT / BUY_TO_COVER，F-13）
amount_sum  = Σ fill.amount
cost_sum    = Σ fill.cost
trades_amount_sum = Σ trades_df.amount（内存；报告侧再与 trades.csv 比对）
final_nav   = 最后一行 trace_day.nav
signed(qty) = +qty（BUY / BUY_TO_COVER）；−qty（SELL / SELL_SHORT）
residual    = max(|amount_sum - trades_amount_sum|,
                  |final_nav - snapshots.total_value.iloc[-1]|,
                  max_stock |Σ signed fill.qty(stock) − Δposition.qty(stock)| )
```

- 容差 `1e-8`，与 `change_report.RESIDUAL_TOL` 同源（I9）。
- 第三项为**逐标的带符号流量恒等式**（F-13 修订）：四方向符号统一后，期货/融券与股票多头共用同一公式；`Trade.quantity` 与 `Position.quantity` 同为合约/股数单位（乘数只进 amount），直接成交计入求和。
- `orders ≠ fills` 合法：差额 = `direct_fills` + fallback 双登记（DD8/DD9）。
- `missing[]`：`manifest.json` / `trades.csv` / `snapshots` 缺失项（报告侧填充，不阻断退出码 0）。

---

## 9. 报告与视图

### 9.1 CLI

```bash
python scripts/trace_report.py --run-dir output/ [--out DIR] [--check]
```

- `--run-dir`：读 `audit_trace_dir` 或 `output_dir`（含 trace 文件）。
- `--check`：只做对齐校验，退出码 **0/1**（与 `change_report` 一致，S9/F-06）。**两级产物（F-18）**：核心产物（`trace_*.csv` + `alignment.json`）缺失 → exit 1；辅助产物（manifest/snapshots/L1-L6/pending_events）缺失 → `missing[]` 记录且 exit 0，残差不可算项标 `degraded`。
- 产物：`trace.html`（单文件）+ `missing.json`。

### 9.2 HTML（V1，零依赖）

四块：

1. **对齐摘要**：`counts / residual / missing`，非 0 残差标红。
2. **日历热力**：按日成交额/拒单数着色，点击进入日视图。
3. **日视图表**：`trace_day` 全列 + 链接到订单。
4. **单票时间轴**：`signal → target_weight → order(status) → fill → close_reason` 纵向时间线（内联 SVG）。

**硬约束**：无 CDN/远程字体/网络请求；生成器只读产物，不写回 trace 目录（除非 `--out` 显式指定）。

### 9.3 Streamlit（B3）

在 5 页顶部加一行「演示数据（demo），真实追溯请用 `trace.html`」；不改数据逻辑。

---

## 10. 批次拆分

| 批 | 内容 | 交付 | 依赖 |
|---|---|---|---|
| **B1** | `scripts/trace_report.py` 读既有 5 类产物 → HTML + `missing.json`（无 trace 文件也能出骨架，并标注缺失列） | T-C01..C08 大部分 | 无生产改动 |
| **B2** | `core/trace.py` + S1-S8 seam + 4 产物 + `alignment.json` + `cli.py` 参数 + `config` 字段 | T-A/T-B 全部，T-C 完整 | B1 |
| **B3** | 单票时间轴 drill-down + Streamlit 标注 +（可选）`--sqlite` | T-D01..D04 | B2 |

每批独立 commit；B2 为唯一触碰生产 seam 的批次。

---

## 11. 测试设计（37 例）

### 11.1 T-A：`core/trace.py` 单元（10）

| ID | 断言 | oracle |
|---|---|---|
| T-A01 | `out_dir=None`/未启用 → 零文件、`enabled=False`、调用全部无害 | contract |
| T-A02 | `order_seq` 在同日同票多单下唯一且稳定 | closed-form |
| T-A03 | `classify_reject` 10 组输入 → 闭集内确定值 | cross-check（与 `_scenarios_trace` 词表逐项对拍） |
| T-A04 | 日末差分：filled / retry / expired 三态 | state |
| T-A05 | fallback 双登记 + `replaces_order_ref` | state |
| T-A06 | direct fill 哨兵与 `orders≠fills` | boundary |
| T-A07 | 末日覆写：末行 = 传入终值 | boundary |
| T-A08 | `finalize` 写 4 文件、列序/表头精确 | contract |
| T-A09 | alignment 残差闭式构造（含 0/非 0 两例） | closed-form |
| T-A10 | `full=False/True` 行集差异 | boundary |

### 11.2 T-B：seam 集成（15）

| ID | 断言 |
|---|---|
| T-B01 | **同 cfg 对跑**（F-11 修订）：`audit_trace_dir=None` vs `=<tmp_path>` 各跑一次——`trades.csv`/`portfolio_snapshots.csv`/`pending_order_events.csv` 三者 sha256 一致（零行为），`input_fingerprint` 必然不同（DD5 预期），且开启 run 产生 4 个 trace 文件、关闭 run 不产生 |
| T-B02 | 启用后 `trace_fill` 与 `trades.csv` 逐笔数量/金额一致 |
| T-B03 | 与 P-059 `TraceRecorder` 对拍：日桶 positions/nav/fills 一致 |
| T-B04 | S1 每日均有记录（触发日与非触发日，F-14），trigger 类名与 `triggered` 布尔正确 |
| T-B05 | `limit_up` / `suspended` / `st_blocked` 三因可区分 |
| T-B06 | `cash_short` 订单保持 pending → 次日 `retry` |
| T-B07 | 卖出无持仓 → `no_position`（或按路径 `cancelled`） |
| T-B08 | 超过 `max_pending_days_*` → `expired` |
| T-B09 | `enable_fallback=True` → 双登记 |
| T-B10 | 末日强平 → `order_ref="direct"` + `close_reason=final_liquidation` |
| T-B11 | 退市结算 → `close_reason=delisted` |
| T-B12 | 末日 trace_day 行（S8 覆写后）= tracker 强平后状态 = snapshots 末日**末行**（末日存在两次快照时取末行，见 §1 复审核验） |
| T-B13 | `event_log_path` + `audit_trace_dir` 同时开启互不干扰 |
| T-B14 | 零成交 run → 4 文件仍生成（仅表头/空数组） |
| T-B15 | manifest config 键集含新字段；同版本两次构建 `input_fingerprint` 相同（DD5） |

### 11.3 T-C：报告/CLI（8）

| ID | 断言 |
|---|---|
| T-C01 | 对齐目录 → exit 0 + `trace.html` + `missing.json` |
| T-C02 | 篡改 1 行金额 → exit 1 |
| T-C03 | 缺 `manifest.json`（**辅助产物**，F-18 两级）→ `missing[]` 记录、exit 0、不崩；对照组：缺任一**核心产物**（`trace_*.csv` / `alignment.json`）→ exit 1 |
| T-C04 | HTML 无 `http://`/`https://` 外链，单文件可开 |
| T-C05 | 日视图含目标/订单/成交/平仓四段，缺列为空并标注 |
| T-C06 | 有 L1-L6 时交叉校验；无则跳过且 `missing[]` 说明 |
| T-C07 | `--check` 不写 HTML |
| T-C08 | 同输入两次生成 HTML 字节相同（无时间戳） |

### 11.4 T-D：端到端（4）

| ID | 断言 |
|---|---|
| T-D01 | 固定 scenario 五问逐条可答（读 trace 文件而非内存） |
| T-D02 | 同输入两次运行 trace 三表字节相同 |
| T-D03 | `lint-imports` 通过（`core.trace` 只依赖 stdlib/pandas） |
| T-D04 | trace 开启的增量耗时 < 基线 10%（同一 scenario 计时） |

---

## 12. 门禁（G1-G14）

| # | 门禁 | 通过条件 |
|---|---|---|
| G1 | 全量 `pytest tests/ -q` | 全绿；collect ≥ 1557 + 37 |
| G2 | `pytest -q -k golden` | **22**，零重录 |
| G3 | `pytest -q -k p059` | **63**，场景文件零改动 |
| G4 | `pytest -q -k p061` | 收集数 = 计划 37（Step 5 若调整须登记 F 号） |
| G5 | mypy（CI 同款，含 `scripts`） | 0 error；files **160 → 162**（+`core/trace.py`、`+scripts/trace_report.py`） |
| G6 | `black --check .` | 全绿；**330 → 336**（+2 源 + 4 测试 = 6 文件，F-12 修正） |
| G7 | 覆盖率 | 四包（含新增 `core/trace.py`）逐包 ≥ 基线 −0.5pp |
| G8 | `pytest -q tests/test_invariants.py` | 全绿 |
| G9 | `pytest -q tests/test_contract_conformance.py` | 全绿 |
| G10 | `python scripts/verify_scenario.py --list` | 18 条 / 7 层 |
| G11 | `lint-imports` | C1/C2/C3 全绿（`core.trace` 不引入上层） |
| G12 | 零行为 sha256 | **同 cfg 对跑**（`audit_trace_dir=None` vs `=<tmp>`，F-11 修订）：`trades.csv`/`portfolio_snapshots.csv`/`pending_order_events.csv` sha256 一致；`input_fingerprint` 必异属预期（DD5） |
| G13 | 对齐 | 样例 run `alignment.residual < 1e-8` |
| G14 | 依赖 | `pyproject.toml` / `uv.lock` 零 diff |

---

## 13. 不变式（I1-I12）

| I | 约束 | 验证 |
|---|---|---|
| I1 | 默认关闭、零 I/O | T-A01 / G12 |
| I2 | 关闭时既有产物字节级不变 | G12 |
| I3 | 不改 `Trade`/`PendingOrder` 字段；不改 `pending.py` | `git diff` 守卫 + T-B02 |
| I4 | 同输入 → 同 trace_id 序列与同文件字节 | T-D02 / T-C08 |
| I5 | 只追加；仅末日末行允许覆写（显式设计） | T-A07 |
| I6 | 拒单原因闭集，越界记 `unknown` | T-A03 |
| I7 | 平仓原因闭集（本批 3 值 + `unknown`） | T-B10/B11 |
| I8 | 视图只读、离线、无网络 | T-C04 |
| I9 | 残差阈值 `1e-8` 同源 | T-A09 / G13 |
| I10 | 零新增依赖 | G14 |
| I11 | seam 不改控制流/返回值 | G1-G3 + T-B01 |
| I12 | trace 写入失败不影响回测 | 注入只读目录的 `OSError` 用例（T-B14 变体） |

---

## 14. 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| seam 引入行为漂移 | 中 | 高 | 全部只读追加；G12 sha256 双重跑；Step 6 逐点复核 |
| 主键撞键（同日同票多单） | 低 | 中 | 全运行 `order_seq`（DD1）+ T-A02 |
| fingerprint 漂移被误判为回归 | 高 | 低 | DD5 显式声明；golden 不含指纹；T-B15 |
| trace 体量超预期 | 中 | 中 | 默认过滤（§7.3）；`full` 仅研究 |
| 与 P-060c 覆盖率基线冲突 | 中 | 中 | 新增模块自带 T-A/T-B；P-060c 完成后重采基线 |
| HTML 变成「第二真相」 | 中 | 中 | 只渲染产物、不重算指标；数字带来源标注 |
| `cli.py --trace-dir` 命名误解 | 中 | 低 | `audit_*` 前缀 + help 文案区分（DD4） |

**回滚**：B1 删脚本即回退；B2 关 `audit_trace_dir` 即零行为，删 `core/trace.py` + revert seam commit 完全回退；B3 删视图产物即可。

---

## 15. DoD（Step 10 验收口径）

1. G1-G14 全绿，读数写入 CHECKLIST。
2. T-A/B/C/D 共 37 例全绿，`-k p061` 计数一致。
3. 同 commit 内关闭/开启对跑：`trades.csv`/`snapshots`/`pending_order_events.csv` sha256 一致（G12，F-11 修订）。
4. 样例 run 的 `alignment.residual < 1e-8`，五问全部可答。
5. `core/trace.py` 覆盖率 ≥80%（新增模块自身），四包不低 0.5pp。
6. 生产改动仅限 `config.py`/`engine_v2.py`/`cli.py`（+B3 `web/` 文案），其余零 diff。

---

## 16. Step 4 设计复审输入（reviewer ≠ 作者）

1. **DD1 主键**：`order_seq` 全运行递增是否足以覆盖「同日同票多单 + fallback 双登记」？
2. **DD3/DD11**：日末差分推导 `expired/cancelled` 是否会漏掉「当日创建当日过期」的订单？
3. **DD4 命名**：`audit_trace_dir` 是否可接受，还是坚持复用 `trace_dir` 并改 CLI 旧参数？
4. **DD5**：新增 cfg 字段导致 fingerprint 漂移，是否需要额外迁移说明或版本标记？
5. **S4 分类器**：`classify_reject` 的入参是否覆盖两条路径的全部 14 点（尤其次日路径 `failed_orders` 复用）？
6. **T-B03**：以测试侧 `TraceRecorder` 作为生产 collector 的对照 oracle 是否独立成立？
7. **G12**：如何机械证明「关闭时字节级不变」（建议固定 fixture + sha256 + 两次运行）？

---

## 17. 待裁决（Step 4 前）

| ID | 问题 | 建议 |
|---|---|---|
| **U-P061-8** | 新字段命名 `audit_trace_dir`/`audit_trace_full`（避让既有 `--trace-dir`） | 采纳 `audit_*` |
| **U-P061-9** | B1 是否先独立合并（无生产改动），再开 B2 | 是（降低风险） |
| **U-P061-10** | B3 视图是否引入 Lightweight Charts（35kB vendoring） | 否，V1 内联 SVG 为准 |

---

## 18. Step 4 复审修订记录（F-10..F-15 全闭合，2026-11-24）

> 复审人 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash（RULE-5）；证据与 §16 七问回答详见 [REVIEW_p061_step4](REVIEW_p061_step4.md)。

| ID | 级别 | 发现（证据） | 修订落点 |
|---|---|---|---|
| **F-10** | P2 | run 末 `mark_expired`（L721-722）在最后一次日末差分**之后**执行，仍 pending 订单（含末日新建）在 trace_order 中永停 `retry` | §5.1 `finalize` 增 `remaining_orders` 终扫 + `order.status` 终态解析机制 + `reject_reason` 后写覆盖；§6 增「终扫调用」 |
| **F-11** | P2 | T-B01/G12 原表述为同义反复（两次 None 证明不了 seam 零行为）；DoD#3「与 4367775 产物对比」不可执行 | T-B01/G12 改**同 cfg 对跑**（None vs `<tmp>`，三 CSV sha256，指纹必异属预期）；DoD#3 改同 commit 对跑 |
| **F-12** | P3 | G6 计数算术错误：330+2源+4测试=**336**，原文写 334 | §12 G6 |
| **F-13** | P2 | alignment `qty_by_side` 仅 BUY/SELL、残差符号约定只对纯多头成立——期货/融券（P-050，`SELL_SHORT`/`BUY_TO_COVER`）下 residual 恒非零 → G13 假失败 | §8 改**逐标的带符号流量恒等式**（四方向统一符号） |
| **F-14** | P3 | S1 挂在 `if should_rebalance:` 体内，非触发日零记录，「为什么这天没调仓」不可答 | §6 S1 前移至 `if` 之前（每日记录）；T-B04 修订 |
| **F-15** | P3 | 文件清单 `pages/00_*.py` 不存在（实际 `01_*`..`05_*`） | §3 修正 |

**复审确认的关键语义**（写入 §1 核验表，作为 IMPL 依据）：`max_pending_days=5/10` 且队列 `mark_expired` 先于当日再平衡 → 同日创建过期不可能（run 末除外，由 F-10 闭合）；活跃集含 PARTIAL；`cancel_*` 仅作用 PENDING；末日强平默认追加第二次快照 → `snapshots.iloc[-1]` 为强平后值。

---

## 19. Step 6 复审修订记录（F-16..F-21 全闭合，2026-11-24）

> 复审人 GLM-5.3-Flash ≠ IMPL 作者 DeepSeek-V4.1-Flash（RULE-5）；证据、任务卡逐卡核验与七问回答见 [REVIEW_p061_step6](REVIEW_p061_step6.md)。37 例总数不变。

| ID | 级别 | 发现（证据） | 修订落点 |
|---|---|---|---|
| **F-16** | P3 | IMPL §2 标题 X1-X13 ≠ 实表 X1-X14 | IMPL §2 标题 |
| **F-17** | P2 | F-10 终扫无专属验收断言（T-B14 无存活订单、T-B08 过期在中段） | IMPL T-B14 扩展「cash_short 存活订单 → 终扫 expired」 |
| **F-18** | P2 | S9「缺产物→1」与 T-C03「manifest 缺失→0」矛盾 | **两级产物规则**（本文件 S9/§9.1 + RESEARCH §6 S9 同步）；IMPL T-C03 补对照组、T-B01 补 `enable_pending_orders` |
| **F-19** | P3 | `TraceConfig.out_dir: Path` 必填 vs T-A01 `out_dir=None` | 本文件 §5.1 改 `Path \| None` |
| **F-20** | P2 | 引擎 `retry_count` 仅成交路径递增（pending.py L169/L182/L390）→ 未成交场景恒 0；IMPL T-B08 原断言必败 | 本文件 §7.1 事实源改 collector 自计数；IMPL T-B08 断言重写 |
| **F-21** | P3 | T-B04 未指定 method；T-B01 缺 pending 注记 | IMPL T-B04 明确 `N_days=5`（触发日 1/6/11/16）；T-B01 注记 |
