# RESEARCH：P-025 日循环异常分类与 retry 语义

> **批次**: P-025 · **T1**（`core/engine_v2.py` + `core/execution.py` 行为契约变更 + 结果字典新增字段；判档规则 1 Layer-1 + 规则 2「行为契约变更」强制升级）
> **上游**: [PROGRESS §1.4](PROGRESS.md) U-P023-1；[RESEARCH_p023 §6](RESEARCH_p023_quality_guardrails.md)（该项登记来源）
> **下游**: DESIGN_p025 → IMPL_p025 → CHECKLIST_p025
> **代码证据时点**: HEAD `a29b39c`（2026-11-12，工作区干净）
> **状态**: Step 1 调研完稿 + **Step 2 独立 Review 通过**（复审基座 GLM-5.3-Flash ≠ 作者 DeepSeek-V4.1-Flash；0 P1/P2，2 P3 回写 + 2 观察，见 §10）

---

## 1. 问题定义

**核心问题**：`BacktestEngineV2.run()` 的日循环以 `except Exception: log + continue` 收口（[engine_v2.py L327-L337](../core/engine_v2.py#L327-L337)），叠加两级内层静默（优化失败、执行失败），使「某日处理失败」在结果层面**不可见**——回测照常跑完并返回完整结果字典。

**为什么现在**：U-P023-1 的触发条件写作「出现第二例被 catch-all 吞掉的确定性缺陷」，属**事故驱动**。本批 Step 1 取证证明条件已成立且不需要事故：`optimizer.method="min_variance"` + `cov_lookback=60` 在 20 个交易日的数据上运行，**每一次调仓都失败**，最终产出 `sharpe=0.0 / total_return=0.0 / 0 成交` 且结果字典中**零错误字段**（探针 B2，§5）。这与 P-023 已修的 F-A1（静默空回测）同属「假成功结果」类别，但入口不同：F-A1 是信号未就绪，本项是**日级异常被吞**。

**影响范围**：`core/engine_v2.py`（日循环 + 优化调用）、`core/execution.py`（成交异常）、结果消费方（`cli.py` / `web/` / 批处理脚本读取 `results["performance_metrics"]`）。

**目标**：① 建立日级异常分类（数据 / 执行 / 内部缺陷 / 外部求解器）；② 明确 retry 语义——哪些可重试、重试有无上界、重试是否可见；③ 在结果字典中暴露运行诊断；④ 既有 654 项测试零回归、golden G1-G7 数值不变。

**出界（不回答）**：非引擎模块的其余 22 处 `except Exception`（`data.py` 3 / `factor.py` 2 / `event_log.py` 6 / `config_v2.py` 3 / `engine_plugins.py` 2 / `walk_forward_engine.py` 2 / `execution.py` 自定义价格回调 1 / `global_contagion.py` 3）；`EngineV3Vector`（向量化单次求值，无日循环）；pending 队列自身的半衰期与过期天数策略；异常对绩效指标的定量影响建模。

---

## 2. 本仓事实（P1-P14）

| # | 事实 | 证据 |
|---|------|------|
| **P1** | **立项来源**：U-P023-1「`run()` 逐日 `except Exception: continue` 的 retry 语义」，原触发条件=「出现第二例被 catch-all 吞掉的确定性缺陷」 | E3 [PROGRESS.md](PROGRESS.md) §1.4 L89 @`a29b39c` |
| **P2** | **日循环吞没点**：`run()` 循环体 `try: _process_trading_day(...) + 末日三连 / except Exception as e: logger.error(f"处理交易日 {date} 时发生错误: {e}"); continue`。循环覆盖 8 个阶段：退市结算 / 次日订单 / 待执行订单 / 再平衡触发 / 再平衡执行 / 盯市 / 风控检查 / 归因落盘 | E3 [engine_v2.py](../core/engine_v2.py) L326-L337、`_process_trading_day` L361-L408 |
| **P3** | **第二级静默（优化）**：`_execute_rebalance` 内 `except Exception: logger.error("组合优化失败") + return`——异常**不会**冒泡到 P2 的日循环，故日循环计数也看不到它 | E3 engine_v2.py L898-L917；E2 探针 B（4 次失败日志） |
| **P4** | **第三级静默（执行）**：`ExecutionSimulator._execute` 的 `except Exception: logger.error("交易执行失败") + return (False, None)` → 调用方视为「未成交」，订单留在队列次日再试 | E3 [execution.py](../core/execution.py) L327-L329；E2 探针 C（3 次注入 → 3 次被吞） |
| **P5** | **探针 A/A2（注入日级异常）**：20 个交易日、在第 6 日注入 `RuntimeError` → **无异常上抛**、`_process_trading_day` 仍被调用 20 次、results 正常返回；快照 **20 条但仅 19 个不同日期**（注入日缺席，末日 `_force_liquidation` 补采一次导致末日重复），`portfolio_value` 同为 20 行且不含注入日 | E2 `%TEMP%\p025_probe.py` 探针 A / `%TEMP%\p025_probe_a2.py` |
| **P6** | **探针 B（优化器全失败）**：`optimizer.optimize` 注入异常 → 4 次调仓时机全部"组合优化失败"、**0 成交**、results 完整返回、`additional_info` 无任何 error/skip 字段 | E2 `%TEMP%\p025_probe.py` 探针 B |
| **P7** | **探针 B2（配置可达的假成功，关键）**：`method="min_variance"` + `cov_lookback=60`、交易日仅 20 → 每次优化抛「最小方差优化需要收益率数据或协方差矩阵」→ **0 成交 / sharpe=0.0 / total_return=0.0 / 零诊断**；同数据 `mean_variance` 成功 13 笔（对照组），说明失败来自方法分支而非数据不足 | E2 `%TEMP%\p025_probe_b2.py` |
| **P8** | **探针 C（执行层异常）**：连续 3 日注入执行异常 → 全部被吞，订单隐式保留、第 4 个交易日全部成交（9 单 9 成），`pending_order_stats.avg_retry_count=1.0` 来自队列 `mark_executed` 的**成交自增**（每单成交 +1，9 单全成 → 均值 1.0），与异常重试无关 | E2 `%TEMP%\p025_probe.py` 探针 C |
| **P9** | **retry 语义现状（双轨、均无计量）**：① pending 队列——订单留在队列逐日重试，`max_pending_days_buy=5` / `sell=10` 到期作废，`retry_count` 三处自增：`PendingOrder.mark_partial`（L169）/ `mark_executed_full`（L182）/ `PendingOrderQueue.mark_executed`（L390，**每次成交 +1**）；② next-day 列表——失败订单进 `failed_orders` 保留，由 `_expire_next_day_orders` 定期清理，**无原因、无尝试计数** | E3 [pending.py](../core/pending.py) L157-L182、L381-L390；engine_v2.py L1085-L1135、[config.py](../core/config.py) L374-L377 |
| **P10** | **测试面为零**：全仓 `tests/*.py` 对 `_process_trading_day` / `_execute_rebalance` / 日循环异常路径 **0 处引用**（`Select-String` 空命中） | E1 `Select-String -Path tests/*.py -Pattern "_process_trading_day|处理交易日|_execute_rebalance|组合优化失败"` → 0 |
| **P11** | **结果字典无诊断位**：`additional_info` 实际 10 键（config / data_info / execution_stats / input_fingerprint / invariant_report / metrics_method / pending_order_stats / universe / universe_summary / validation_declaration）；`invariant_report` 是唯一带校验语义的字段，且只校验**已生成**的快照 | E2 探针 D；E3 engine_v2.py L1160-L1218 |
| **P12** | **三态策略先例**：`invariant_mode: Literal["off","report","raise"] = "report"`（P-011 D2），默认 report 并把结果写入 `invariant_report`，`raise` 时抛 `InvariantViolationError` | E3 [config.py](../core/config.py) L344；engine_v2.py L1186-L1198 |
| **P13** | **上报通道现状**：`EventLog` 已实现（JSONL + 环形缓冲 + 订阅）但**未接入引擎**——全仓仅 `engine_plugins.py` L56 实例化一次；引擎全部可观测性走 stdlib `logging` | E1 `Select-String "EventLog\("` → 2 处（定义与插件）；E3 [event_log.py](../core/event_log.py) L84-L120 |
| **P14** | **负向发现（缩小触发面）**：`DataManager.load_factor` 对因子做**逐交易日前向对齐**（PIT 语义，L564-L582），故 `signal_df.loc[date]` 不会 KeyError；「因子缺日 → 日循环抛错」路径**不成立**（探针 A3：因子缺中间一日 → 净值序列仍含该日、无异常，仅当日因子为空权重） | E3 [data.py](../core/data.py) L564-L582；E2 `%TEMP%\p025_probe_a3.py` |

**严重度重估**：

| 项 | 原级别 | 新级别 | 依据 |
|----|--------|--------|------|
| P6/P7（优化/执行失败无计量 → 假成功结果） | P3 | **P1** | 探针 B2 证明**零代码缺陷、纯配置**即可产出 `sharpe=0` 的"成功"回测；与 P-023 F-A1 同级 |
| P2（日循环 catch-all） | P3 | **P2** | 探针 A2 证明后果是净值序列缺日 + 末日重复；但 P14 排除最可能的触发路径，实际触发面为内部缺陷 |
| P9（retry 无上界计量） | — | **P2** | 探针 C 证明确定性错误会逐日重试直到过期，日志刷屏但无计数、无告警 |
| 其余 22 处 catch-all | — | P3 | 出界，另行登记 U-P025-3 |

---

## 3. 外部锚点（F1-F4）

### 3.1 有效锚点清单

| ID | 来源 | 发布/版本 | 读取日 | 验证 | 命中要点（引文） |
|----|------|-----------|--------|------|------------------|
| **E1** | PEP 654 *Exception Groups and except\** | Final（Created 2021-02-22），Python 3.11 | 2026-11-12 | ✅ 正文 | "proposes language extensions that allow programs to raise and handle **multiple unrelated exceptions simultaneously**"；`except*` 逐类分流 → 支撑「一次运行聚合多日异常」的形态选择 |
| **E2** | Amazon Builders' Library *Timeouts, retries, and backoff with jitter* | 在线版（AWS 官方，LEVEL 200） | 2026-11-12 | ✅ 正文 | "Retries allow clients to survive these random **partial or transient** failures"；"It's not always safe to retry… some remote calls have **side effects**"；"We **stop retrying when the retries are not helping**" → 支撑「确定性错误不得重试」 |
| **E3** | Google SRE Book ch.6 *Monitoring Distributed Systems* | 2016 版在线全文 | 2026-11-12 | ✅ 正文 | 四黄金信号 "latency, traffic, **errors**, saturation"；"white-box monitoring… allows detection of imminent problems, **failures masked by retries**" → 支撑「重试必须可计数」 |
| **E4** | PEP 20 *The Zen of Python* | Active | 2026-11-12 | ✅ 正文 | "Errors should never pass silently. / Unless explicitly silenced."（沿用 P-023 E1，非本批新增锚点） |

> **F1/F2**：每条锚点带发布版本与读取日。**F3 降级链**：无需降级（3 条新锚点均命中正文；`martinfowler.com/bliki/FailFast.html` 实测 **404**，已弃用不列入）。**F4**：有效外部锚点 **3 条新增（E1-E3）+ 1 条沿用（E4）** ≥3。**F5**：Step 1 已取得 5 组红灯读数（§5 P2-P8），Step 9 以同探针转绿回填。

---

## 4. 方案矩阵（7 维 × 外部锚点）

> 时间窗声明：短期 = 本批（单批次可完成）；长期 = 一个季度内的消费方兼容成本。

| 方案 | 成本 | 收益 | 兼容 | 维护 | 升级潜力 | 短期 | 长期 |
|------|------|------|------|------|----------|------|------|
| **M-A 三态策略 + 计量（推荐）**<br>`day_error_mode: off\|report\|raise`（默认 `report`）+ 统一 `_record_day_error` 采集器 + 优化/执行内层接入 + `additional_info["run_diagnostics"]` | E1 3 文件 + ≈120 行 + 8-10 测试 | 假成功结果转可见（E3 四黄金信号之 errors）；`raise` 模式供 CI/pytest 用 | 高：默认 `report` 保持现状控制流，仅**新增**字典键；`off` 保留完全旧行为（E2 "stop retrying when not helping" 对应 `off`） | 中：新增 1 个 dataclass + 1 个采集器 + 3 个注入点 | 高：`run_diagnostics` 可直接被 EventLog/Prometheus 消费（P13） | 1 批（3 提交） | 消费方无需改；`off` 可作退出闸 |
| M-B 仅加计数，不改控制流 | E1 1 文件 +≈60 行 | 中：有计数，但 `raise` 能力缺失 | 最高 | 低 | 低：仍是单点逻辑 | 1 批 | 需二次改造 |
| M-C 全量 fail-fast（默认 `raise`） | E1 3 文件 +≈80 行 | 理论最高（E4 "never pass silently"） | **低**：真实脏数据会中断整轮回测；654 测试与 golden 需重录 | 低 | 低 | 1 批 | 用户会自行包 try 绕过 → 退化为无计量 |
| M-D 以 EventLog 为唯一通道 | E1 3 文件 +≈150 行 + 引擎接线 | 高：统一事件流（P13） | 中：引入 I/O 与文件生命周期 | 高：EventLog 目前零生产接线，需先补 lifecycle | 最高 | 2 批 | 需运维文件轮转 |
| M-E 维持现状 | 0 | 0 | — | 0 | 0 | — | 探针 B2 的假成功持续存在 |

**选型**：**M-A**。理由：① 与仓内既有的 `invariant_mode` 三态同形（P12），消费方认知成本最低；② 默认 `report` 保证 654 测试与 golden 零回归，同时让 P7 类假成功在结果中显形；③ `raise` 提供严格模式而不强制；④ M-D 的 EventLog 收益真实但当前零接线（P13），作为 U-P025-1 单列，不阻塞本批。

**被拒方案代价**：M-B 无法满足「CI 严格模式」（无 `raise`），后续需二次改造；M-C 会让真实脏数据中断回测，与 P-010/P-012 建立的「缺失数据安全降级」纪律冲突；M-D 把本批工期翻倍且引入未验证的 I/O 面。

**每个方案的锚点覆盖（锚点→维度）**：M-A — E3→收益（errors 可见）、E2→兼容+长期（`off` 退出闸 / 停止无效重试）、E4→收益（消除静默），覆盖 收益/兼容/长期 ≥3 维；M-B — E3→收益、E4→收益、E2→长期（仅计数不设闸，无效重试持续，需二次改造）；M-C — E4→收益、E1→兼容+长期（聚合多异常后统一抛出，`ExceptionGroup` 跨 3.10/3.11 形态）；M-D — E3→收益+维护（white-box 内检）、E2→长期（重试纪律与运维）。

---

## 5. 取证读数（Step 1）

| 探针 | 构造 | 读数 | 结论 |
|------|------|------|------|
| **A** | 20 日、第 6 日注入 `RuntimeError` | 无上抛；调用 20/20；results 完整；`additional_info` 10 键无诊断位 | 日级异常完全静默 |
| **A2** | 同 A，比对日期序列 | 快照 20 条 / **19 个不同日期**；注入日缺席；末日（2024-01-29）**重复**；`portfolio_value` 20 行、不含注入日 | 净值序列缺日 + 末日重复 → 日收益口径失真 |
| **A3** | 因子文件缺中间一日（真实形态） | 无异常；净值含该日；当日「没有有效的因子得分，返回空权重」 | **负向**：数据层 PIT 对齐（P14）已排除该路径 |
| **B** | `optimizer.optimize` 注入异常 | 4 次「组合优化失败」；0 成交；零诊断字段 | 优化失败不进日循环，双重静默 |
| **B2** | `min_variance` + `cov_lookback=60`（20 日） | 0 成交 / `sharpe=0.0` / `total_return=0.0` / 零诊断；对照 `mean_variance` 13 笔 | **配置可达的假成功（P1）** |
| **C** | 连续 3 日注入执行异常 | 全吞；订单保留；第 4 日 9 单全成；`avg_retry_count=1.0`（队列 `mark_executed` 成交自增，非异常重试计数） | 隐式重试无计数、无上界告警 |
| **D** | 正常跑 | `additional_info` 10 键（P11）；`results` 6 键 | 无诊断位，需新增 |

---

## 6. 风险识别

| # | 风险 | 类型 | 缓解 |
|---|------|------|------|
| R1 | 分类错误把「数据脏」误判为「内部缺陷」，在 `raise` 模式下中断真实回测 | 已知 | 分类表按异常类型 + 阶段双重判定；默认 `report` 不中断；`raise` 仅在显式配置下启用 |
| R2 | 新增 `run_diagnostics` 键改变结果字典形状，破坏外部消费方 | 已知 | 仅**新增**键、不改既有键；在 DESIGN 中列消费方清单并逐个验证（`cli.py` / web / 批处理） |
| R3 | golden G1-G7 数值漂移 | 已知 | 正常路径零控制流变更（`report` 只记录不改变执行），Step 9 复跑 golden 逐字节对比 |
| R4 | 采集器本身抛错（如 dataclass 字段类型不匹配）导致二次故障 | 未知 | 采集器内部 `try/except` 兜底并降级为 `logger.error`；设计期加"采集器不得抛错"约束 |
| R5 | 多日异常在 `raise` 模式下只抛首个，丢失其余 | 未知 | 按 E1 用 `ExceptionGroup` 聚合（Python 3.11+），3.10 走链式 `raise ... from` + 诊断字典兜底；版本分支在 DESIGN 定 |
| R6 | 日级重试次数无上界导致日志膨胀 | 已知 | 采集器按 `(date, stage, error_type)` 去重计数，日志每类每运行至多 N 条 |

---

## 7. 未决项登记（四元块）

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| **U-P025-1** | `EventLog` 接入引擎作为统一事件通道 | `run_diagnostics` 已落地且有第二个消费方（web/批处理）需要事件流 | 不接入；本批只做结果字典暴露 | E3 P13 |
| **U-P025-2** | `EngineV3Vector` 是否需要同形诊断 | V3 出现「静默空结果」实例 | 暂不做（V3 单次向量求值，无日循环） | E3 |
| **U-P025-3** | 其余 22 处 `except Exception` 治理 | 其中任一处产生可复现的静默错误 | 本批出界，按模块分批登记 | E1 grep 25 处 − 本批 3 处 |
| **U-P025-4** | 优化失败时退化为等权（而非跳过调仓） | 真实回测中出现优化失败且用户明确要求降级继续 | 不做：静默降级会掩盖配置错误（正是 P7 的成因） | E2 探针 B2 |
| **U-P025-5** | `ExceptionGroup`（`raise` 模式）与 `raise ... from`（3.10）的分支实现 | DESIGN 阶段确认项目最低版本 3.10 的兼容策略 | 3.11+ 用 `ExceptionGroup`，3.10 用首异常 + 诊断字典 | E1 PEP 654 |

---

## 8. 批次切分建议

| 批 | 内容 | 交付判据 |
|----|------|----------|
| **B1** | 配置字段 `day_error_mode` + `DayErrorRecord` + `_record_day_error` 采集器 + 8 项单测 | 采集器零抛错；三态行为可机械断言 |
| **B2** | 日循环改造：异常分类表 + 计量 + `run_diagnostics` 入结果 | 探针 A2 转绿：缺失日出现在诊断中，`degraded=True` |
| **B3** | 内层接入：`_execute_rebalance` 优化失败、`execution._execute` 成交失败 → 同一采集器 | 探针 B/B2 转绿：`failed_rebalances ≥ 1` 且 sharpe=0 时 `degraded=True` |
| **B4** | 文档与回归：README 结果字段说明、ARCHITECTURE 诊断节、654 测试 + golden G1-G7 复跑 | 全量 passed、golden 逐字节不变 |

---

## 9. 调研结论

**推荐方案**：M-A（三态 `day_error_mode` + 统一采集器 + `run_diagnostics`），按 B1-B4 四批实施。

**关键假设**（可在 DESIGN/IMPL 验证）：
1. 消费方只读取 `results` 既有键，新增键不破坏兼容（DESIGN 阶段逐个核对 3 个消费方）。
2. `report` 模式下控制流与现状完全一致 → 654 测试与 golden 无需重录。
3. 异常分类表可覆盖 ≥95% 的日级异常类型（以 654 测试运行的日志为语料核对）。

**下一步**：~~Step 2 独立 Review（异构基座）~~（已完成，见 §10）→ DESIGN_p025（D/I/T 三层 + 验证矩阵）。

---

## 10. Step 2 Review（独立 pass）

> **执行方式**：RESEARCH 完稿（`221ed64`）后独立执行；复审基座 **GLM-5.3-Flash ≠ 作者基座 DeepSeek-V4.1-Flash**（异构成立）。机械复核含：四探针脚本独立重跑、代码锚点行号逐条比对、外部锚点引文逐句核对（对照 Step 1 抓取的原文存档）、相对链接与台账登记复检。不复用作者结论，只对照原文与重跑读数。

### 10.1 机械复核

| # | 校验 | 读数 |
|---|------|------|
| 1 | 探针 A/B/C/D 重跑（`%TEMP%\p025_probe.py`） | A：无上抛 / 调用 20/20 / results 完整 / 快照 20；B：4 次「组合优化失败」/ 0 成交 / 零诊断字段；C：3 次注入全吞 / 第 4 交易日 9 单全成 / `avg_retry_count=1.0`；D：`additional_info` 10 键 / `results` 6 键——**与 §5 逐项一致** |
| 2 | 探针 A2/A3 重跑 | A2：快照 20 / 重复日 [2024-01-29] / 注入日缺席 / `portfolio_value` 20 行不含注入日；A3：21 快照 / 20 去重日 / 净值含缺失日——**一致** |
| 3 | 探针 B2 重跑 | `min_variance`：0 成交 / sharpe 0.0 / total_return 0.0 / 零诊断；`mean_variance` 对照 13 笔 / sharpe 4.1908——**一致** |
| 4 | 代码锚点行号 | engine_v2 L327-L337 / L361-L408 / L898-L917 / L1085-L1135 / L1160-L1218 / L1186-L1198；execution L327-L329；config L344 / L374-L377；data L564-L582；pending L157-L182 / L381-L390——**全部逐字命中**（`221ed64` 代码与 `a29b39c` 相同，纯文档提交） |
| 5 | 外部锚点引文 | PEP 654「multiple unrelated exceptions simultaneously」/ AWS「partial or transient failures」「not always safe to retry」「stop retrying when the retries are not helping」/ SRE「failures masked by retries」「latency, traffic, errors, and saturation」——**逐句对照原文存档命中** |
| 6 | P10 / P13 复查 | tests 对异常路径引用 **0**；`EventLog\(` 全仓 **2** 处（定义 + engine_plugins L56）——**一致** |
| 7 | 相对链接与台账 | RESEARCH 11 处链接 **0 broken**；PROGRESS §1.4 P-025 行 + U-P023-1 改判行落位复核一致 |

### 10.2 门禁四项（SPEC_PROCESS Step 2 门禁）

| 检查项 | 结论 |
|--------|------|
| 幻觉排除 | **通过**——3 条新增锚点引文与原文存档逐句命中；martinfowler `FailFast.html` 404 弃用注属实（作者实测 404，未列入锚点表） |
| 方案完整性 | **通过（附 1 P3 订正）**——5 方案 ≥2；7 维矩阵齐（成本/收益/兼容/维护/升级潜力/短期/长期）；选型理由与被拒代价齐；锚点覆盖维度标注缺失见 F-S2-P025-2（已回写） |
| 风险覆盖 | **通过**——6 项风险（R1-R6）均带缓解，≥3 |
| 假设明确 | **通过**——3 项关键假设显式声明且可验证 |

### 10.3 发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S2-P025-1** | P3 | P9 原文「`retry_count` **仅**在 `mark_partial` / `mark_executed_full` 自增」与同行证据列「pending.py …L390」自相矛盾——L390 是**第三处自增点** `PendingOrderQueue.mark_executed`（每次成交 +1，[pending.py L381-L390](../core/pending.py#L381-L390)）；§5 探针 C 行「`avg_retry_count=1.0`（部分成交口径）」归因随之失准（实为队列成交自增：9 单全成 → 均值 1.0） | **已回写**：P9 正文改三处自增 + 证据列 L381-L390；P8 与 §5 C 行归因订正 |
| **F-S2-P025-2** | P3 | §4 锚点覆盖行仅 M-A 声明「覆盖 ≥3 维」且未映射维度，M-B/M-C/M-D 只列锚点 ID——不满足门禁「每方案 ≥2 锚点覆盖 ≥3 维」的举证格式 | **已回写**：逐案标注 锚点→维度 映射（§4） |
| 观察 O1 | — | **末日重复快照为既有行为，非日循环吞没所致**：探针 A3 正常回测（无注入）同样 21 快照 / 20 去重日；A2 的重复日 [2024-01-29] 在无注入时同样出现。golden G1-G7 已编码该行为——本批 `run_diagnostics` **不得顺带「修复」重复快照**（会破坏 golden）；如需治理应另行登记独立项 | 不处置；转 DESIGN 注记 |
| 观察 O2 | — | 可静态判定的配置错误（如 `cov_lookback` > 交易日数且 method 依赖协方差）可在 `setup()` 预检 fail-fast（与 P-023 setup 守卫同形），比运行期诊断更早暴露探针 B2 类假成功 | 不处置；由 DESIGN 裁决是否纳入 B1 |

### 10.4 结论

**通过**——0 P1 / 0 P2 / **2 P3（均已回写）** + 2 观察；门禁四项全过；机械复核 7 项全命中（探针读数逐项复现、代码锚点零漂移、引文零幻觉）。严重度重估（P6/P7→P1）理由成立：B2 为纯配置可达的假成功结果，与 P-023 F-A1 同类。可进入 Step 3 DESIGN（纳入 O1/O2 裁决）。
