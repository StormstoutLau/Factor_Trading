# RESEARCH：P-026 静默失败治理第二批（core/ 剩余 except 分级显形）

> **批次**: P-026 · **T1**（`core/` 行为契约变更 + 结果/返回值新增可观测字段；判档规则 1 Layer-1 + 规则 2「行为契约变更」强制升级）
> **上游**: [PROGRESS §1.4](PROGRESS.md) U-P025-3；[RESEARCH_p025 §1](RESEARCH_p025_daily_loop_exception_semantics.md)（出界段列明 22 处构成）
> **下游**: DESIGN_p026 → IMPL_p026 → CHECKLIST_p026
> **代码证据时点**: HEAD `7ff7a4d`（2026-11-13，工作区干净）
> **状态**: Step 1 调研完稿（待 Step 2 独立 Review）

---

## 1. 问题定义

**核心问题**：P-025 已把回测主链路的**三层**静默（日循环 / 优化 / 执行）接入统一采集器并暴露 `run_diagnostics`，但 `core/` 内仍有 **18 处** catch-all 以「零日志 / debug 级 / 无计量 / 语义混淆」形态吞掉异常——其中 3 处位于**结果正确性受影响**的路径（因子中性化、风控 Guard、多窗口 Agent 期间设置）。

**为什么现在**：U-P025-3 的触发条件写作「其中任一处产生可复现的静默错误」。本批 Step 1 读码证明条件**已成立且不需要事故**：

- [factor.py L344](../core/factor.py#L341-L345)：`except Exception: continue`——**连日志都没有**；去常数列失败 → 该交易日因子整体跳过 → 信号缺失
- [engine_plugins.py L235](../core/engine_plugins.py#L235-L237)：Guard 检查异常 → `return True, []`（**fail-open**）——风控链失效时无声放行，仅 `warning` 且异常不计入 `_blocked_count` / `_warning_count`
- [walk_forward_engine.py L185](../core/walk_forward_engine.py#L179-L186)：`agent.set_period` 失败 → `warning` 后继续——该窗口以**错误期间模式**运行，窗口结果失真且无字段标记

**影响范围**：`core/factor.py`（信号链路）、`core/engine_plugins.py`（风控）、`core/walk_forward_engine.py`（多窗口）、`core/event_log.py`（审计链）、`core/global_contagion.py`（分析模块）。

**目标**：① 对 22 处候选逐点产出「保持 / 升级诊断 / fail-fast」三态裁决（**本批不含 fail-fast**，见 §4 选型）；② 10 处升级为「可观测」——计数或返回值字段显形，不改变正常路径控制流；③ 既有 671 项测试零回归、golden G1-G7 数值不变。

**出界（不回答）**：`config_v2.py` 3 处（已冻结模块，形态正确）；`execution.py` L251 自定义价格回调（P-025 观察-2 已裁正确降级）；core 外 **22 处**（`agents/` 11 / `filter/` 5 / `cli.py` 1 / `scripts/` 2 / `batch_backtest/` 2 / `strategy_evaluation/` 1）；异常对绩效指标的定量影响建模；EventLog 的生产接线（U-P025-1 仍待触发）。

---

## 2. 本仓事实（P1-P12）

| # | 事实 | 证据 |
|---|------|------|
| **P1** | **候选池实测**：全仓 `except Exception` **49 处**——`core/` 27、`agents/` 11、`filter/` 5、`scripts/` 2、`batch_backtest/` 2、`strategy_evaluation/` 1、`cli.py` 1 | E1 `Select-String -Path <dir>\*.py -Pattern "except Exception"` @`7ff7a4d` |
| **P2** | **core/ 27 处构成**：已埋点 3（engine_v2 L360 日循环 / L943 优化 / execution L339 执行）+ 采集器自身兜底 2（diagnostics L121 / L152，I3 契约要求）+ **待评估 22** | E3 [engine_v2.py](../core/engine_v2.py)、[execution.py](../core/execution.py)、[diagnostics.py](../core/diagnostics.py) |
| **P3** | **22 处逐文件分布**：`event_log` 6 / `data` 3 / `config_v2` 3 / `global_contagion` 3 / `factor` 2 / `engine_plugins` 2 / `walk_forward_engine` 2 / `execution` 1，与 [RESEARCH_p025 §1 出界段](RESEARCH_p025_daily_loop_exception_semantics.md) 逐项吻合 | E1 grep + E3 对照 |
| **P4** | **最严重形态（零日志）**：`factor.py` L344 `except Exception: continue`——去常数列（`np.std(X, axis=0)`）失败时**无日志、无计数**，该日中性化整体跳过；同函数 L366 有 `warning` 但同样无计数 | E3 [factor.py](../core/factor.py) L296-L370 |
| **P5** | **fail-open 形态**：`GuardPlugin.check_trade` 异常 → `logger.warning` + `return True, []`（注释自述「异常时允许执行，避免阻断正常交易」）；类内已有 `_blocked_count` / `_warning_count`，**异常无独立计数** | E3 [engine_plugins.py](../core/engine_plugins.py) L179-L237 |
| **P6** | **debug 级静默**：`EnginePlugin._log` 的 `except Exception: logger.debug(...)`——Python 官方文档明确 **root logger 默认级别为 WARNING**（§3 A3），故未显式配置时该行**完全不输出** | E3 engine_plugins.py L157-L162；E1 官方文档直读 |
| **P7** | **结果失真形态**：`WalkForwardEngine._set_agent_period` 在 `hasattr(agent,"set_period")` 通过后调用失败 → `warning` 后继续，该窗口 Agent 沿用上一期间模式；`WalkForwardResult` 无失败字段 | E3 [walk_forward_engine.py](../core/walk_forward_engine.py) L173-L215 |
| **P8** | **丢弃式读取**：`EventLog.read` / `query` 的 `except Exception: logger.warning` 后返回**空/部分列表**——调用方无法区分「无事件」与「读失败」 | E3 [event_log.py](../core/event_log.py) L140-L163 |
| **P9** | **审计链写入**：`_append_to_disk` 写失败 → `logger.error` 后**静默丢弃**（内存环形缓冲保留、磁盘 JSONL 缺失）；无失败计数 | E3 event_log.py L264-L270 |
| **P10** | **分析模块静默兜底**：`global_contagion` 特征向量中心性失败 → **零日志**等权兜底（L433）；MST 失败 → **零日志**空边（L447）；Granger 失败 → `warning` + 返回 `causal=False`（L589，与「真无因果」不可区分） | E3 [global_contagion.py](../core/global_contagion.py) L424-L448、L582-L591 |
| **P11** | **正确形态（零改动）**：`data.py` 三处均为 `logger.error + raise`（记录后重抛，不吞）；`event_log` 的 listener 隔离（L278/L286）、恢复失败 warning（L313）、快捷函数 `log_event`（L383）、`walk_forward` 回调失败（L214）属有意容错 | E3 逐点读码 |
| **P12** | **静默路径测试覆盖近零**：9 个代表性 except 路径关键词在 `tests/*.py` 中 **7 项 0 命中**（仅「中性化失败」「自定义价格回调失败」各 1 处） | E1 `Select-String -Path tests\*.py -Pattern <关键词>` |

**严重度重估**：

| 项 | 原级别 | 新级别 | 依据 |
|----|--------|--------|------|
| P4（factor 零日志跳过日） | P3 | **P2** | 信号链路；该日因子全空 → 权重缺失，结果层面不可见 |
| P5（Guard fail-open 无计量） | P3 | **P2** | 风控链失效时静默放行，与 P-023/P-025「假成功」同级 |
| P7（窗口期间失真） | P3 | **P2** | 多窗口结论建立在错误期间模式上，无字段可辨 |
| 其余 7 处升级项 | P3 | P3 | 结果层可观测性缺口，不影响正常路径正确性 |

---

## 3. 外部锚点（A1-A4）

| ID | 来源 | 发布/版本 | 读取日 | 验证 | 命中要点（引文） |
|----|------|-----------|--------|------|------------------|
| **A1** | [PEP 20 – The Zen of Python](https://peps.python.org/pep-0020/) | Status: Active；Created 19-Aug-2004 | 2026-11-13 | **已验证（T1 命中）**，peps.python.org 直读 | 「Errors should never pass silently. / **Unless explicitly silenced.**」——后句是本批三态裁决的合法性来源：显式静默（K 类）合规，未声明的静默（D 类）不合规 |
| **A2** | [CWE-390: Detection of Error Condition Without Action](https://cwe.mitre.org/data/definitions/390.html) | Weakness ID 390；Abstraction: Base | 2026-11-13 | **已验证（T1 命中）**，mitre.org 直读 | 「The product detects a specific error, but **takes no actions to handle the error**.」——精确描述 `factor.py` L344 与 `global_contagion` L433/L447（捕获后无动作） |
| **A3** | [Python 官方 logging 文档](https://docs.python.org/3/library/logging.html) | Python 3.x（docs.python.org/3） | 2026-11-13 | **已验证（T1 命中）**，docs.python.org 直读 | 「Note that **the root logger is created with level WARNING**.」——证明 `logger.debug` 在默认配置下不可见（P6）；同章 `Logger.exception` 语义为「记录 ERROR + traceback，且只应在 except 处理器内调用」 |
| **A4** | [AWS Builders' Library: Avoiding fallback in distributed systems](https://aws.amazon.com/builders-library/avoiding-fallback-in-distributed-systems/) | Amazon Builders' Library（ARCHITECTURE LEVEL 300） | 2026-11-13 | **已验证（T1/T2 官方）**，aws.amazon.com 直读 | 故障处理四策略 Retry / Proactive retry / Failover / **Fallback**；「Given these pitfalls we encountered in distributed fallback, we now **almost always prefer alternatives to fallback**.」——降级（fallback）不是默认选项，**必须显式声明并计量** |

**锚点→维度映射**：A1 → 兼容+收益（默认 report 是「显式静默」的合法形态）；A2 → 收益（消除无动作捕获）；A3 → 维护（debug 级升级为 warning/error 的依据）；A4 → 长期（降级需计量与可退出）。

---

## 4. 方案矩阵（7 维）

> 时间窗声明：短期 = 本批（单批次可完成）；长期 = 一个季度内的消费方兼容成本。

| 方案 | 成本 | 收益 | 兼容 | 维护 | 升级潜力 | 短期 | 长期 |
|------|------|------|------|------|----------|------|------|
| **M-A 逐点三态裁决 + 分级显形（推荐）**<br>18 处逐点分为 K（保持 8）/ D（升级诊断 10），复用 `DayErrorCollector` 语义 + 各模块自有计数/字段；**不含 fail-fast** | 5 文件 + ≈120 行 + 10-12 测试 | 三处 P2 路径显形；审计链失败可辨；分析模块降级可见 | 高：只增计数/字段，正常路径零控制流变更 | 中：sink 注入（factor）+ 自有计数（其余） | 高：后续可统一汇入 EventLog（U-P025-1） | 1 批（4 提交） | 消费方无需改 |
| M-B 仅提升日志级别（debug→warning、零日志补 warning） | 4 文件 + ≈20 行 | 中：日志可见，但**无计量、无结果字段** | 最高 | 低 | 低：仍是单点日志 | 1 批（1 提交） | 需二次改造为计量 |
| M-C 新建 `core/degraded.py` 全局注册表 | 1 新文件 + 5 文件 + ≈180 行 | 高：统一降级清单 | 中：引入**全局可变状态**，测试隔离复杂 | 中 | 高 | 1 批 | 多实例/并发场景需加锁 |
| M-D 全量 fail-fast | 5 文件 + ≈60 行 | 理论最高 | **低**：真实脏数据/缺 set_period 的 Agent 会中断 | 低 | 低 | 1 批 | 用户包 try 绕过 → 退化为无计量 |
| M-E 维持现状 | 0 | 0 | — | 0 | 0 | — | 三处 P2 路径持续静默 |

**选型**：**M-A**。理由：① 延续 P-025 已建立的「显式静默（K）/ 未声明静默（D）」判据（A1）；② 不引入全局状态（M-C 的主要风险），采用 P-025 D5 已验证的 **sink 注入**模式（`getattr` 探测，fake 对象零破坏）；③ 不含 fail-fast（M-D）——`hasattr` 守卫已过滤「不支持 set_period 的 Agent」，失败属真实异常，但中断整个 walk-forward 的价值低于显形；④ M-B 无法满足「结果层可辨」目标（P8 的「无事件 vs 读失败」仍不可区分）。

**被拒方案代价**：M-B 交付后仍需二次改造（无计量）；M-C 引入全局状态与测试隔离成本，且与 P-025 已选路径不一致；M-D 会让真实数据质量问题中断回测，与 P-010/P-012「缺失数据安全降级」纪律冲突。

---

## 5. 逐点裁决表（22 处）

> 三态定义：**K** 保持（形态正确或已显式声明，零改动）/ **D** 升级诊断（静默降级 → 计数或字段显形）/ **F** fail-fast（本批 **0 项**，见 §4）。

| # | 位置 | 当前形态 | 态 | 处置要点 |
|---|------|----------|----|----------|
| 1 | `data.py` L250 | `logger.error + raise` | **K** | 记录后重抛，正确 |
| 2 | `data.py` L317 | `logger.error + raise` | **K** | 同上 |
| 3 | `data.py` L605 | `logger.error + raise` | **K** | 同上（因子加载） |
| 4 | `factor.py` L344 | `except Exception: continue`（**零日志**） | **D** | 至少 `warning` + `neutralize_skipped_days` 计数；经 sink 进 `run_diagnostics`（stage 新增 `factor`） |
| 5 | `factor.py` L366 | `warning + continue` | **D** | 同上计数（与 #4 合并为同一计数器，区分 `degenerate` / `regression` 原因） |
| 6 | `event_log.py` L160 | `warning` + 返回部分结果 | **D** | `stats()` 加 `read_failures`；`read/query` 返回值区分（或加 `last_read_error`） |
| 7 | `event_log.py` L269 | `error` + 静默丢盘 | **D** | `stats()` 加 `write_failures`（审计链可辨） |
| 8 | `event_log.py` L278 | `warning` + listener 隔离 | **K** | 有意容错（单 listener 不影响其他） |
| 9 | `event_log.py` L286 | `warning` + type-listener 隔离 | **K** | 同上 |
| 10 | `event_log.py` L313 | `warning` + 恢复失败置空 | **K** | 有日志且语义明确（首启/损坏可辨） |
| 11 | `event_log.py` L383 | `warning + return None` | **K** | 快捷函数有意容错（日志不得影响主流程） |
| 12 | `engine_plugins.py` L161 | **`debug`** + 丢弃 | **D** | 升级为 `warning`；`_error_count` 计数 |
| 13 | `engine_plugins.py` L235 | `warning` + **fail-open** | **D** | `_error_count` 独立计数（区分 blocked/warning/error）+ 升级日志语义；**保持 fail-open**（风控可用性优先） |
| 14 | `global_contagion.py` L433 | **零日志** + 等权兜底 | **D** | `warning` + `degraded_components` 标记 |
| 15 | `global_contagion.py` L447 | **零日志** + 空边 | **D** | 同上 |
| 16 | `global_contagion.py` L589 | `warning` + `causal=False` | **D** | 返回值加 `failed: True`（区分「无因果」与「检验失败」） |
| 17 | `walk_forward_engine.py` L185 | `warning` + 期间失真 | **D** | `WalkForwardResult` 加 `agent_period_failures` 计数 |
| 18 | `walk_forward_engine.py` L214 | `warning` + 回调失败 | **K** | 用户代码回调，隔离正确 |
| — | `config_v2.py` L321/L380/L424 | 错误收集 / error+False / warning | **排除** | 冻结模块且形态正确 |
| — | `execution.py` L251 | `error` + 回退开盘价 | **排除** | P-025 观察-2 已裁正确降级 |

**汇总**：K **8** / D **10** / F **0** / 排除 **4** = 22。

---

## 6. 风险识别

| # | 风险 | 类型 | 缓解 |
|---|------|------|------|
| R1 | 新增计数字段改变结果/返回值形状，破坏消费方 | 已知 | 只**新增**字段、不改既有键；`EventLog.stats()` / `WalkForwardResult` / `ContagionNetwork` 消费方在 DESIGN 逐个核对 |
| R2 | 日志级别提升导致既有测试断言失败（部分测试可能计数 warning） | 未知 | Step 9 先红后绿；`pytest -q` 全量对比 671 基线；逐个检查受影响测试 |
| R3 | `factor` sink 注入破坏 fake pipeline（测试中的替身对象） | 已知 | 复刻 P-025 D5：`getattr(obj, "set_error_sink", None)` 探测，无该方法则静默跳过 |
| R4 | 全局状态引入（若选 M-C） | 已规避 | 选 M-A，零全局状态 |
| R5 | 过度治理：把有意容错（listener 隔离 / 快捷函数）改成显形，反而放大日志噪声 | 已知 | K 类 8 处明确不动；D 类中 `event_log` L383 等保守保留 |
| R6 | golden G1-G7 漂移 | 已知 | 正常路径零控制流变更；Step 9 复跑 golden 逐字节对比 |
| R7 | `_error_count` 等计数字段在多次 run 时累积（P-025 观察-1 同级） | 未知 | DESIGN 明确「计数生命周期 = 实例生命周期」，与 `run_diagnostics` 现有语义一致 |

---

## 7. 未决项登记（四元块）

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| **U-P026-1** | `EventLog` 写盘失败是否 fail-fast 或重试 | 审计完整性成为合规要求，或出现写盘失败导致审计断裂的真实案例 | 不 fail-fast（保持可用性），只计量（D 类 #7） | E3 P9 |
| **U-P026-2** | `global_contagion` 是否需独立 `degraded` 字段 vs 仅日志+计数 | 消费方（web 面板 / 报告）需要区分「计算失败」与「结果为空」 | 本批只加 `degraded_components` 标记 | E3 P10 |
| **U-P026-3** | core 外 22 处后续分批 | 任一模块出现「静默错误」可复现实例 | `agents/` 11 与 `filter/` 5 优先（业务影响面） | E1 P1 |
| **U-P026-4** | listener 类隔离容错是否需限流/告警 | listener 频繁抛错导致日志刷屏 | 不做（K 类保持） | E3 P11 |
| **U-P026-5** | 是否引入跨模块统一采集器（替代 sink 注入） | 出现第三个需要 sink 注入的模块 | 本批用 sink 注入（P-025 先例），不建全局 | E3 P2 |

---

## 8. 批次切分建议

| 批 | 内容 | 交付判据 |
|----|------|----------|
| **B1** | `factor.py` 2 处（D #4/#5）：sink 注入 + 跳过计数 + `STAGES` 增 `factor` | 注入回归异常 → `run_diagnostics.counts["factor"] ≥ 1`，正常路径 counts 为空 |
| **B2** | `engine_plugins.py` 2 处（D #12/#13）：debug→warning、`_error_count` 独立计数 | Guard 异常 → `_error_count == 1` 且 override 语义不变（仍放行） |
| **B3** | `global_contagion.py` 3 处（D #14/#15/#16）：warning + `degraded_components` + `failed` 标记 | 强制数值异常 → 标记为 True 且结果结构不变 |
| **B4** | `event_log.py` 2 处 + `walk_forward_engine.py` 1 处（D #6/#7/#17）：`stats()` 计数 + `agent_period_failures` | 写盘失败 → `stats()["write_failures"] ≥ 1`；set_period 异常 → 计数字段 ≥ 1 |
| **B5** | 文档与回归：README/ARCHITECTURE 可观测节、671 测试 + golden 复跑 | 全量 passed、golden 逐字节不变、门禁 37 files 0 |

---

## 9. 调研结论

**推荐方案**：M-A（逐点三态裁决 + 分级显形），按 B1-B5 五批实施；**本批 0 项 fail-fast**。

**关键假设**（可在 DESIGN/IMPL 验证）：
1. 三处 P2 路径（factor / Guard / walk-forward）的显形不改变正常路径控制流 → 671 测试与 golden 零重录。
2. sink 注入模式对 fake 对象零破坏（P-025 D5 已验证同类形态）。
3. `EventLog.stats()` / `WalkForwardResult` / `ContagionNetwork` 的消费方均为只读且容忍新增字段。

**下一步**：Step 2 独立 Review（异构基座）→ DESIGN_p026（D/I/T 三层 + 验证矩阵）。
