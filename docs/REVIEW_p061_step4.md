# REVIEW：P-061 Step 4 DESIGN 异构复审（DESIGN_p061_observability_traceability）

> **复审人**：GLM-5.3-Flash（≠ DESIGN 作者 DeepSeek-V4.1-Flash，RULE-5 异构成立）
> **对象**：[DESIGN_p061](DESIGN_p061_observability_traceability.md)（DD1-DD12 / S1-S8 / 37 例 / G1-G14）
> **基线**：`4367775`
> **结论**：**PASS-WITH-COMMENTS** —— 0×P0/P1 / **3×P2 / 3×P3**，全部当轮修订落回 DESIGN（§18 修订记录 F-10..F-15）；文档级修订，零代码变更。
> **方法**：① 逐条核验 DD/S 引用的行号与语义；② 以「订单状态机终态」为轴穷举 `_process_pending_orders` / `_execute_next_day_orders` / run 末尾三条路径；③ 对齐公式代入期货四方向（P-050）做符号演算；④ 复核 `pending.py` 全部 public API 的状态过滤语义。

---

## 1. 核验确认项

| 项 | 复核结果 |
|---|---|
| DD4 命名冲突 | ✅ [cli.py](../cli.py#L317-L319) `--trace-dir` 确已绑定 `dump_layers_dir`，`audit_*` 避让必要 |
| DD5 fingerprint | ✅ [manifest.py](../core/manifest.py#L160-L162) `_jsonable(cfg)` 全字段入哈希，新增字段必然漂移；[test_manifest.py](../tests/test_manifest.py#L130-L132) 键集断言按 `dataclasses.fields` 自适应，T-B15 不会误报 |
| DD6 14 拒单点 | ✅ 队列 7（L1171/L1175/L1184/L1193/L1198/L1209/L1221）+ 次日 7（L1750/L1757+L1761/L1765/L1771/L1784/L1789），逐一在源码确认 |
| DD7 5 注册位 | ✅ [L526](../core/engine_v2.py#L526)/[L1297](../core/engine_v2.py#L1297)/[L1686](../core/engine_v2.py#L1686)/policy [L1649-L1652](../core/engine_v2.py#L1649-L1652)（fallback 原单为回写非创建） |
| S8 早退位置 | ✅ [L859-L864](../core/engine_v2.py#L859-L864) 首个 `if` 即 `dumper.enabled` 早退，trace 覆写须前置的判断正确 |
| §16-Q2 同日过期 | ✅ **默认配置下不可能**：`max_pending_days_buy/sell = 5/10`（[config.py](../core/config.py#L489-L490)），`is_expired` 需 `days_pending >= max`（[pending.py](../core/pending.py#L219)）；且队列路径 `mark_expired`（L1259）先于当日 `_execute_rebalance` 执行，当日创建的订单不在过期扫描范围；`_queue_urgent_order` 订单豁免（L1122-1124）。**唯一例外是 run 末尾的 `mark_expired`（L721-722）可令末日创建的订单当日过期 → 见 F-10** |
| §16-Q6 T-B03 独立性 | ✅ `TraceRecorder` 以 proxy 包装组件（attach 替换 `engine.executor/tracker`），seam 为引擎原生打点，二者机制独立可共存；作为对照 oracle 成立（不同机制、同一真相） |
| PARTIAL 语义 | ✅ `get_pending_orders` 返回 `PENDING + PARTIAL`（[pending.py](../core/pending.py#L331)）；`cancel_orders/cancel_order` 仅取消 PENDING（L451/L368）→ PARTIAL 订单跨再平衡存活，差分按「仍活跃 → retry」处理，DD11 兼容 |
| 对齐公式基础 | ✅ 末日强平默认 `update_market_values=True`（[L956-L957](../core/engine_v2.py#L956-L957)）→ 追加第二次快照，`snapshots.iloc[-1]` 为强平后值，与 trace 末行一致（P-059「二次调用」已证） |

## 2. 发现清单

### F-10（P2）run 结束时仍 pending 的订单无终态：collector 缺最终清点

- **证据**：run 主循环在末日 `DAY_END`（最后一次 `on_day_end`）**之后**执行 `pending_queue.mark_expired(last_date)`（[L721-L722](../core/engine_v2.py#L721-L722)）；此后不再有日末差分。此时仍 PENDING 的订单（含末日再平衡新建的订单——它们在 run 末被统一过期）在 `trace_order` 中将**永远停留在 `retry`**。
- **影响**：B2 产物的订单终态不完整，`counts.orders` 与状态分布对不上，违反 S4 状态机闭环。
- **处置**（已落 §5.1/§6）：`finalize` 增加最终清点入参 `remaining_orders`，引擎在 run 末 `mark_expired` **之后**调用；collector 对剩余订单读存储的 `order.status` 定终态（`EXPIRED→expired` / `CANCELLED→cancelled` / 其余→`dropped`），并明确差分终态解析同用此机制、`reject_reason` 为**后写覆盖**（最后一次尝试原因）。

### F-11（P2）T-B01/G12 现表述为同义反复，且 DoD#3 不可执行

- **证据**：T-B01 写「`audit_trace_dir=None` 与『不设该字段』两次运行」——本批后该字段**始终存在**，两种说法是同一配置，跑两次只能证明引擎确定性，**证明不了 seam 零行为**。DoD#3「与 `4367775` 产物 sha256 一致」缺乏存档基线，机械上不可执行。
- **处置**（已落 §11/§12/§15）：T-B01/G12 改为**同 cfg 对跑**——`audit_trace_dir=None` vs `=<tmp_path>`，比较 `trades.csv`/`portfolio_snapshots.csv`/`pending_order_events.csv` 三者 sha256；`input_fingerprint` 必然不同（DD5 已声明），**产物必须相同**。DoD#3 改为「同 commit 内关闭/开启对跑 sha256 一致」。

### F-12（P3）G6 black 计数算术错误

- **证据**：330 基线 + 2 源（`core/trace.py`、`scripts/trace_report.py`）+ 4 测试 = **336**，DESIGN 写 334。
- **处置**：G6 改 330 → **336**。

### F-13（P2）alignment 残差公式忽略期货/融券方向（SELL_SHORT / BUY_TO_COVER）

- **证据**：§8 `qty_by_side` 只有 `{"BUY","SELL"}` 两键；残差式 `|Σ(BUY.qty) − Σ(SELL.qty) − Δ持仓|` 的符号约定只对纯股票多头成立。本项目期货为一等公民（P-050：`SELL_SHORT` 开空、`BUY_TO_COVER` 平空，`OrderSide` 四方向），且 `Trade.side` 直接继承 `OrderSide`。
- **影响**：含空头/期货的 run 中 residual 恒非零 → G13 必假失败，或被迫放宽阈值破坏 I9。
- **处置**（已落 §8）：`qty_by_side` 扩为四方向；残差改为**逐标的带符号流量恒等式**——`signed(qty) = +qty`（BUY / BUY_TO_COVER）、`−qty`（SELL / SELL_SHORT），`max_stock |Σ signed fill.qty − Δposition.qty| < 1e-8`（直接成交计入；期货 quantity 合约数两侧同单位，乘数已在 amount 内）。

### F-14（P3）S1 只记录 triggered=True，「为什么这天没调仓」不可答

- **证据**：S1 挂在 `if should_rebalance:` 体内，非触发日零记录；RESEARCH §13.1 第 4 跳的排查问句包含触发原因。
- **处置**（已落 §6/§11）：S1 前移到 `should_trigger` 调用之后、`if` 之前，**每日**记录 `{date, trigger 类名, triggered, kwargs 摘要}`（成本 ≤ 1 行/日）；T-B04 相应改为「触发日与非触发日均有记录，类名正确」。

### F-15（P3）文件清单笔误：Streamlit 页面 glob 错误

- **证据**：`web/streamlit_app/pages/` 为 `01_Overview.py` ... `05_Performance.py`，无 `00_*.py`。
- **处置**：§3 改为「`web/streamlit_app/pages/0*_.py`（B3 逐页加 demo 标注）」。

## 3. §16 复审问题逐条回答

| # | 问题 | 回答 |
|---|---|---|
| Q1 | `order_seq` 全运行递增是否足够？ | **足够**。5 个注册位覆盖全部创建路径（含 policy 与 fallback）；全运行递增 + 按 `(date, stock, side, seq)` 排序保证 I4；fallback 双登记不产生新 seq 冲突（替补单走同一分配器）。前提是注册调用点与创建点一一对应（DD7 已列全）。 |
| Q2 | 日末差分是否漏「当日创建当日过期」？ | **默认配置不漏**（见 §1 核验）：max_days 5/10 > 0、队列 `mark_expired` 先于当日再平衡、urgent 订单豁免。**唯一例外是 run 末 `mark_expired`**——由 F-10 的最终清点闭合。若用户配 `max_pending_days_*=0`，则当日过期经日末差分照常捕获（订单从活跃集消失且 `status=EXPIRED`）。 |
| Q3 | `audit_trace_dir` 命名 | **支持**。`trace_dir` 已被 CLI 占用是实证约束；`audit_*` 前缀同时传达「审计用途」并与 `AUDIT_*` 事件语义呼应。 |
| Q4 | fingerprint 漂移 | **声明 + T-B15 足够**。漂移只影响 `manifest.json` 内容（键集断言自适应），golden 与对账均不依赖指纹跨版本稳定。需在 DD5 补一句「关闭/开启对跑时指纹必不同，属预期」（已随 F-11 落）。 |
| Q5 | `classify_reject` 入参覆盖 14 点？ | **覆盖**，但有两点收紧：① L1184/L1193（BTC 无持仓、夹紧）走 `cancel_order` 终态而非跳过保留，分类器需允许「终态=cancelled + reason」并存；② `expired` 入参在 14 点中不出现（过期是批量 `mark_expired`），仅终态解析使用——建议从分类器签名中移除，避免死参数（已落）。 |
| Q6 | T-B03 对照 oracle 独立性 | **成立**（见 §1）。注意事项：两机制不得共享代码路径（TraceRecorder 是 proxy 包装、seam 是引擎内联），断言只比较产物。 |
| Q7 | G12 机械证明 | **同 cfg 对跑 + 三 CSV sha256**（F-11 修订后）。不得比较 `manifest.json`（指纹必异）。 |

## 4. U-P061-8/9/10 复审意见

| ID | 复审意见 |
|---|---|
| U-P061-8 | **支持采纳** `audit_trace_dir`/`audit_trace_full`（实证冲突） |
| U-P061-9 | **支持 B1 先独立合并**：零生产改动、可独立回滚，且为 B2 提供报告侧对账骨架 |
| U-P061-10 | **支持不引入** Lightweight Charts：35kB vendoring 需第三方资产登记流程，V1 内联 SVG 已满足 §9.2 四块需求 |

（三项仍待用户裁决，本复审仅提供依据。）

## 5. 修订落点（已全部落回 DESIGN §18）

| 发现 | 落点 |
|---|---|
| F-10 | §5.1 finalize 增 `remaining_orders` 终扫 + 终态解析机制；§6 增「终扫调用」段 |
| F-11 | §11 T-B01 重写、§12 G12 措辞、§15 DoD#3 改同 commit 对跑 |
| F-12 | §12 G6 330 → 336 |
| F-13 | §8 四方向 + 逐标的带符号恒等式 |
| F-14 | §6 S1 前移、§11 T-B04 修订 |
| F-15 | §3 文件清单 glob 修正 |

## 6. 下一步

Step 4 复审闭合后：用户裁决 U-P061-8..10 → **Step 5 IMPL**（按 §10 批次：B1 报告 → B2 seam+产物 → B3 视图）。
