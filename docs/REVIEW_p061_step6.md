# REVIEW：P-061 Step 6 IMPL 异构复审（IMPL_p061_traceability）

> **复审人**：GLM-5.3-Flash（≠ IMPL 作者 DeepSeek-V4.1-Flash，RULE-5 异构成立）
> **对象**：[IMPL_p061](IMPL_p061_traceability.md)（X1-X14 锚点 / D-01..D-06 分歧 / 37 例任务卡 / S5-1..S5-5）
> **基线**：`4367775`（未落码；本复审为落码前方案复审）
> **结论**：**PASS-WITH-COMMENTS** —— 0×P0/P1 / **3×P2 / 3×P3**，全部当轮修订落回 IMPL（§9）与 DESIGN（§18 追加 F-16..F-21）；37 例总数不变。
> **方法**：① X 锚点逐条对照本会话一手抓取的源码/规范文本；② 任务卡逐卡代入 `engine_v2` / `pending.py` / `rebalance.py` 实测语义（retry_count 递增位点、FixedInterval 首日触发、cancel/clamp 分支终态）；③ 跨文档一致性（IMPL ↔ DESIGN S9/§5.1/§7.1 ↔ RESEARCH S9）。

---

## 1. 核验确认项

| 项 | 复核结果 |
|---|---|
| X1/X2 Nautilus 三层身份 | ✅ 抓取原文：「`correlation_id`: the logical workflow or chain / `causation_id`: the direct parent / `command_id·event_id·report_id`: the identity of this specific message」；「seq orders replay… do not override seq」；「Fail-stop does not interrupt the run」 |
| X3 event-store README | ✅ 「Entries keyed by monotonic seq」「A manifest written at run start and sealed at run end」、Verifier 校验 entry hash / seq 缺口 |
| X4/X5/X6 zipline | ✅ `ORDER_STATUS = OPEN/FILLED/CANCELLED/REJECTED/HELD`；`reject(reason)`/`hold(reason)` 同写 `self.reason`；`make_id → uuid.uuid4().hex`（反例成立） |
| X7 backtrader | ✅ 9 态 `Created/Submitted/Accepted/Partial/Completed/Canceled/Expired/Margin/Rejected`；`refbasis = itertools.count(1)` |
| X8/X9 Freqtrade | ✅ Exit Reason Stats 分组表（roi/exit_signal/force_exit/stop_loss）；`exit_reason` 7 值闭集 |
| X10-X12 | ✅ OpenLineage runId/UUIDv7/`outputStatistics`；W3C「trace-id = 32HEXDIGLC ; 16 bytes…All zeroes forbidden」；QuantStats `tpl.replace("{{…}}")` + `b64encode` 单文件 |
| X13/X14 | ✅ `uuid4` 随机；pandas `lineterminator` 默认 `os.linesep`（Windows `\r\n`）→ 固定 `\n` 必要 |
| D-01..D-06 分歧表述 | ✅ 与源码事实一致（D-02 的 HELD、D-06 的 run 开始写 manifest 均有原文支撑） |
| T-A02/A06/A07/A09/A10 | ✅ 闭式/边界构造可成立（含 signed-flow residual：BUY 100、SELL 40 → Δpos=+60） |
| T-B02/B03 可行性 | ✅ `TraceRecorder` proxy 与引擎原生 seam 机制独立可共存；`build_scenario` 经 `_apply_overrides` 可注入 `audit_trace_dir` |
| T-B07 终态 | ✅ 队列路径 clamp→`cancel_order`（L1193）；次日路径 clamp→丢弃（L1789，不入 `failed_orders`）→ differential 按存储 `status=PENDING` 解析为 `dropped`，与 DESIGN §5.1 一致 |
| T-B10/B11/B12 | ✅ 强平/退市金额公式与 [execution.py](../../core/execution.py#L337)（amount=qty×price×multiplier）、[L999-L1005](../../core/engine_v2.py#L999-L1005)（delist_return）一致；末日第二次快照使 `snapshots.iloc[-1]` 为强平后值 |
| T-B15 | ✅ manifest config 键集按 `dataclasses.fields` 自适应 |
| T-C01/C02/C04/C07/C08 | ✅ 与 S9（0/1）、I8（无外链）、I4（无时间戳）一致 |
| S5-1..S5-5 计数 | ✅ 8/18/33/37 递进正确；每步独立 commit |

## 2. 发现清单

### F-16（P3）§2 标题计数错误：X1-X13 → X1-X14

- **证据**：IMPL §2 标题为「外部源码案例锚点（X1-X13）」，但 §2.5 覆盖 X13-X14，全表到 X14；PROGRESS 登记亦写 X1-X14。
- **处置**：标题改 X1-X14。

### F-17（P2）F-10 终扫无专属验收断言：37 例中没有任何一卡验证 run 末清点

- **证据**：DESIGN §18 F-10 要求 `finalize(remaining_orders=...)` 终扫，IMPL §4.2 落码要点也列了「终扫在 run 末 `mark_expired` 之后」，但 T-A/T-B 各卡均未覆盖：T-B14 是「零成交、无调仓」（无存活订单），T-B08 的过期发生在 run 中段（`_process_pending_orders` 内），都不经过 run 末路径。
- **影响**：终扫是 F-10 修复的核心行为，无机械验证则 Step 9 无法判定其存在与正确性（订单可能永停 retry 而测试全绿）。
- **处置**：**扩展 T-B14**——场景改为「零成交 run，但含 1 张 `cash_short` 存活订单（未到期）」：断言追加「终扫后该订单终态 = `expired`（status 由 run 末 `mark_expired` 置位）」。37 例总数不变。

### F-18（P2）退出码契约矛盾：DESIGN S9「1=…或缺产物」vs T-C03「manifest 缺失 → exit 0」

- **证据**：S9（F-06 修订）写「1=残差超限**或缺产物**」；T-C03 断言「删除 `manifest.json` → exit 0、`missing[]` 记录」。二者直接冲突——按 S9 字面实现则 T-C03 必败，反之 S9 被违反。
- **处置**：引入**两级产物**规则（DESIGN S9 + IMPL T-C03 同步）：
  - **核心产物**（`trace_day.csv` / `trace_order.csv` / `trace_fill.csv` / `alignment.json`）缺失 → exit 1；
  - **辅助产物**（`manifest.json` / `portfolio_snapshots.csv` / L1-L6 / `pending_order_events.csv`）缺失 → 写入 `missing[]`、残差可算则 exit 0；残差因缺失无法计算（如 snapshots 缺失）→ 退化项不计入 residual 并在 `missing[]` 标注 `degraded`。
- 同时在 T-B01 卡片补注：场景须 `enable_pending_orders=True`，否则 `pending_order_events.csv` 不生成（引擎仅在有队列时写出，[engine_v2.py](../../core/engine_v2.py#L1916-L1920)），三 CSV 退化为二。

### F-19（P3）禁用形态矛盾：`TraceConfig.out_dir: Path`（必填）vs T-A01「TraceConfig(out_dir=None)」

- **证据**：DESIGN §5.1 `TraceConfig.out_dir: Path` 为必填；T-A01 以 `out_dir=None` 构造禁用态。类型不符。
- **处置**：`TraceConfig.out_dir: Path | None`，`None → enabled=False`（与 `cfg.audit_trace_dir=None` 语义对齐）；DESIGN §5.1 注解同步。

### F-20（P2）`retry_count` 事实源错误：引擎只在成交时递增，未成交场景恒为 0

- **证据**：全仓 `retry_count` 递增点仅 3 处，且全部在**成交路径**——`mark_partial`（[pending.py](../../core/pending.py#L169)）、`mark_executed_full`（L182）、队列 `mark_executed`（L390）。跳过/拒单（T-B05..B08 的 14 个点）**不递增**；次日路径成交也从不调用（F-02 已证）。
- **影响**：① DESIGN §7.1 `trace_order.retry_count` 来源标 "order" → 对「未成交即过期」（最典型重试场景）恒为 0，列语义失真；② T-B08 断言「连续 3 日不可买 → retry_count 递增」**必然失败**（该订单从未成交，`order.retry_count==0`）。
- **处置**：`trace_order.retry_count` 事实源改为 **collector 侧自计数**——每次 `on_order_rejected` +1（成交不改），语义 =「被拒/跳过的尝试次数」；DESIGN §7.1 source 修正；T-B08 断言改为「collector 计数 = 2（第 1、2 日被拒）且第 3 日终态 `expired`」。这与 DD2「以 fill/collector 为过程事实源」一致，也规避了队列成交 +1（L390）与语义混淆。

### F-21（P3）T-B04/T-B01 配置精确化

- **证据**：① T-B04 写「固定频率 5 日」未指定 method——`FixedIntervalTrigger` 仅在 `frequency="N_days"` 下按 `range(0, len, n_days)` 取**首日 + 每 5 日**（[rebalance.py](../../core/rebalance.py#L93-L95)），weekly/monthly 是周期末日语义，凑不出确定的「4 日」；② T-B01 缺 `enable_pending_orders` 注记（见 F-18）。
- **处置**：T-B04 明确 `method="N_days", n_days=5`、20 交易日 → 触发日 = 第 1/6/11/16 交易日（首日即触发，已核验）；T-B01 补 pending 队列开启注记。

## 3. IMPL §8 复审输入七问逐条回答

| # | 问题 | 回答 |
|---|---|---|
| 1 | S1-S8 是否全为只读追加、S7/S8 与 `update_market_values` 顺序 | 是。S7 挂 `DAY_END` 后（盯市已发生），S8 挂 `_refresh_last_nav` 内早退前（强平后）——时序正确且无顺序依赖；全部 hook 仅读变量+追加。 |
| 2 | S4 14 点一一对应？`failed_orders` 是否重复计数 | 一一对应（逐行号核验）。`failed_orders` 是次日路径的**重试容器**（保留订单），不入 reject 计数；重复 reject 由后写覆盖 + F-20 计数器表达，无重复行。 |
| 3 | 三 CSV sha256 是否足够 | 足够。`performance_metrics.csv` 完全由 snapshots 派生（`generate_report` 同源），无独立信息量；可加但不必要。`manifest.json` 必异（DD5）不参与比较。 |
| 4 | 原因闭集 9 值覆盖？`cancelled`/`dropped` 边界 | 覆盖。边界已明确：引擎主动 `cancel_*` → `cancelled`；clamp 丢弃/消失且 status 仍 PENDING → `dropped`；`mark_expired`（含 run 末）→ `expired`。 |
| 5 | order_seq 是否受 dict/set 遍历顺序影响 | 不受。seq 在**创建调用点**即时分配（单线程顺序执行），不依赖任何集合遍历；落盘排序键显式 `(date, stock, side, seq)`。 |
| 6 | D-01..D-06 取舍 | 同意。补充：D-01（确定性 seq）现有了强证据——X6/X13 反例 + 引擎 `retry_count` 语义缺陷（F-20）进一步说明不能依赖 order 对象做过程记录。 |
| 7 | HTML 第二真相风险 | 需页面顶部固定标注「数据来源：trace_*.csv / alignment.json / manifest.json（只读渲染）」——已并入 T-C05 断言（修订后）。 |

## 4. 修订落点（已全部落回）

| 发现 | 落点 |
|---|---|
| F-16 | IMPL §2 标题 X1-X14 |
| F-17 | IMPL T-B14 扩展（终扫断言） |
| F-18 | DESIGN S9 两级产物规则；IMPL T-C03/T-B01 同步 |
| F-19 | DESIGN §5.1 `TraceConfig.out_dir: Path \| None`；IMPL T-A01 保持 |
| F-20 | DESIGN §7.1 retry_count source → collector 计数；IMPL T-B08 断言重写 |
| F-21 | IMPL T-B04 配置精确化（N_days=5）；T-B01 pending 注记 |

## 5. 下一步

Step 6 闭合 → **S5-1 落码**（B1：`scripts/trace_report.py` + T-C 8 例，零生产改动，独立 commit）。
