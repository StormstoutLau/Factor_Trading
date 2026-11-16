# P-029 静默失败治理第四批 · 批次总结报告（十步终态）

> **批次**: P-029 · `agents/` 9 处计量（承接 U-P027-1）· **T1**
> **状态**: **Step 1-10 全通过 + RULE-5 异构终审 pass，批次关闭**（2026-11-16）
> **审计基线**: 审计对象 `2080784..e8578c2`（5 提交）· 终态 HEAD `75c7d10` · **异构终审基座**: GLM-5.3-Flash（≠ 四文档作者 DeepSeek-V4.1-Flash）· **评分 99/A**
> **配套文档**: [RESEARCH](RESEARCH_p029_silent_exception_governance_phase4.md) / [DESIGN](DESIGN_p029_silent_exception_governance_phase4.md) / [IMPL](IMPL_p029_silent_exception_governance_phase4.md) / [CHECKLIST](CHECKLIST_p029_silent_exception_governance_phase4.md)

---

## 1. 一页速览

| 维度 | 结果 |
|------|------|
| **治理对象** | `agents/` 3 文件中的 9 处静默失败路径（8 个 `except` 处理器 + 1 个缺失 `else` 分支） |
| **核心手段** | 统一「三件套」计量：`_failure_counts: dict[str,int]` + `_record_failure(key)` + `get_failure_stats()`（只读拷贝） |
| **代码规模** | 3 代码文件 **+20/−5**（净 +15）+ 新测试 258 行；全区间 10 文件 **+398/−65** |
| **行为变更** | **零**——零 fail-fast、零返回值语义变更、零既有文案改写、**零新增日志**、零捕获类型变更 |
| **测试** | **711 → 722 passed**（+11 实例 / 7 函数）；测试文件 **80 → 81** |
| **门禁** | black **117 → 118**；mypy **37 files 0 error**；golden **13 passed 零重录**；`except Exception` 恒 **22** |
| **盲区收敛** | `agents/` 零可观测处理器 **9 → 1**（唯一残留为显式 import 降级） |
| **质量结论** | 十步 0 P1 / 0 P2；**12 项 P3 全部当轮修正**；异构终审 99/A |

一句话：**让 9 类「捕获了但什么都不说」的分支在运行期留下可对拍的数字，而不改变任何一条业务路径的返回结果。**

---

## 2. 背景：为什么要治这一批

### 2.1 静默失败的定义与危害

本项目把「异常被捕获、但既不抛出、不记录日志、也不留下任何计数」的路径定义为**静默失败**。其危害不在崩溃，而在于**结果异常却无任何信号**：

- 数据缺失导致因子为空 → 回测照常输出净值曲线，看起来「跑成功了」；
- 缓存损坏导致行业/市值矩阵为 `None` → 轮动分析器静默跳过，组合退化为单策略；
- 协方差矩阵奇异导致求逆失败 → 用伪逆顶替，权重数值路径已改变但无人知晓。

这类故障在监控上表现为**零告警 + 合理但错误的输出**，事后无法归因。

### 2.2 治理谱系

| 批次 | 范围 | 计量数 | 结论 |
|------|------|--------|------|
| P-026 | `core/` 静默面（8 文件，四批实施） | 16 项测试 / 45 项验收 | 完成 |
| P-027 | `core/` 以外 22 处（`agents/` / `filter/` / `strategy_evaluation/` / `scripts/` / `batch_backtest/` / `cli.py`） | 16 计量 + 6 零改动 | 完成 |
| **P-029（本批）** | P-027 E4 扫描遗留的 `agents/` 同型站点（不属于 `except Exception` 口径：bare `except:` + 窄类型） | **9 计量 + 1 零改动** | **完成 / 关闭** |

P-027 的盲区扫描发现 `agents/` 尚有 9 处零可观测处理器未被 `except Exception` 口径覆盖，登记为 **U-P027-1**；本批即该项的落地。

### 2.3 取证结论（Step 1）

8 处站点全部通过 E2 探针复现：**注入异常 → 返回默认值/继续执行 + 0 条日志 + 0 计量 + 不抛出**。分类为 **B 7（应有计量）+ 待裁决 1（S8）+ 观察 1（S3b）**。

---

## 3. 设计口径

### 3.1 六条硬约束

| # | 约束 | 理由 |
|---|------|------|
| 1 | 零 fail-fast（不新增 `raise`） | 本批为「可观测化」，不是「严格化」；严格化须独立批次评估兼容性 |
| 2 | 零返回值语义变更 | 缓存仍为 `None`、`continue` / `return` 逐字保留、pinv 权重域不变 |
| 3 | 零既有文案改写 | 既有注释（如「如果奇异，使用伪逆」）逐字保留 |
| 4 | **零新增日志** | 避免与 U-P026-4 的日志限流关切冲突；计数走结构化出口 |
| 5 | 零捕获类型变更 | 4 处 bare `except:` 保持 bare（改写会改变 `except Exception` 口径与 I1 读数） |
| 6 | 九面零改动 | `filter/` / `core/` / `strategy_evaluation/` / `scripts/` / `batch_backtest/` / `cli.py` / `pyproject.toml` / `.github/` / `tests/golden/*.json` |

### 3.2 载体策略（M-A 决策）

| 文件 | 载体状态 | 策略 |
|------|----------|------|
| `agents/agent_framework.py` | P-027 已在 L882/L891-893/L895-897 落地三件套 | **复用**，仅补 5 处调用 |
| `agents/multi_strategy_engine.py` | P-027 已落地（含 `run()` 出口 `failure_counts`） | **复用**，仅补 3 处调用 |
| `agents/strategy_allocator.py` | 无载体 | **新建**（仅 `MeanVarianceAllocator` 实例级） |

**M-A 决策：不下沉 `BaseAllocator`。** Step 4 实证 5 个子类（Hedge / FTRL / UCB / Thompson / MeanVariance）均有自有 `__init__`，下沉需改 5 处 `super()` 调用链且引入跨层依赖，收益与风险不成比例；仅在需要计量的 `MeanVarianceAllocator` 自备三件套。

### 3.3 九键名定稿

`price_cache` / `industry_cache` / `mktcap_cache` / `rotation_analyzer_skipped` / `performance_summary_team_report` / `orders_missing_price` / `next_day_open_price` / `pending_open_price` / `pinv_fallback`

---

## 4. 实施明细：9 个计量站点

| # | 键名 | 文件 | 实施后行 | 触发条件 | 原行为 | 治理后 |
|---|------|------|----------|----------|--------|--------|
| S1 | `price_cache` | `agent_framework.py` | L974 | 价格缓存 pkl 损坏，`pickle.load` 抛错（bare except） | `pass` → `_price_data = None` | 计数 +1，载体仍 `None` |
| S2 | `industry_cache` | 同上 | L984 | 行业缓存损坏（bare except） | `pass` → `None` | 计数 +1 |
| S3 | `mktcap_cache` | 同上 | L994 | 市值缓存损坏（bare except） | `pass` → `None` | 计数 +1 |
| S3b | `rotation_analyzer_skipped` | 同上 | L938 | `_init_research_team` 前置条件不满足，**原本无 `else` 分支** | 静默不建轮动分析器 | 新增 `else` 挂 L928 的 `if`，计数 +1（**不加 warning**） |
| S4 | `performance_summary_team_report` | 同上 | L1160 | `fund_manager.get_team_report()` 抛错（bare except） | `pass` → `team_report` 键缺失 | 计数 +1；**`failure_counts` 快照下移至 try/except 之后**（L1162），同调可见 |
| S5 | `orders_missing_price` | `multi_strategy_engine.py` | L331 | 信号缺价格列 / 缺日期（`KeyError`/`IndexError`，合法分支走 L328-329 `continue` 不计数） | 静默 `continue` | 计数 +1，`continue` 保留 |
| S6 | `next_day_open_price` | 同上 | L392 | 次日开盘价缺失（`KeyError`） | 静默 `return` | 计数 +1，`return` 保留 |
| S7 | `pending_open_price` | 同上 | L455 | 挂单开盘价缺失（`KeyError`） | 静默 `return` | 计数 +1，`return` 保留 |
| S8 | `pinv_fallback` | `strategy_allocator.py` | L638 | 协方差矩阵奇异，`np.linalg.inv` 抛 `LinAlgError` | 静默改走伪逆（仅行内注释说明） | 计数 +1，伪逆路径与权重归一不变 |

**零改动 1 处**：`agents/research_team_v2.py:25-28` 模块级 `except ImportError` 静默置 `None`——属显式可选依赖降级，且主路径经 L914 直连 import、失败时 L843-845 有 `logger.warning` 兜底，下游可观测，维持只登记。

---

## 5. 变更面与代码规模

### 5.1 逐文件读数

| 文件 | 性质 | numstat |
|------|------|---------|
| `agents/agent_framework.py` | 5 计量（S1-S3 + S3b + S4）+ 快照下移 | **+7 / −5**（净 +2） |
| `agents/multi_strategy_engine.py` | 3 计量（S5-S7），各有 `except` 块首行 | **+3 / −0** |
| `agents/strategy_allocator.py` | 三件套 9 行 + 1 计量 | **+10 / −0** |
| `tests/test_p029_silent_exception_governance.py` | 新建，7 函数 11 实例 | **+258 / −0** |
| 6 份文档 | CHANGELOG / README / ARCHITECTURE / IMPL / CHECKLIST / PROGRESS | 合计 |

**全区间 `2080784..e8578c2`：10 文件 +398 / −65。**

### 5.2 关键纪律的落地证据

| 纪律 | 证据 |
|------|------|
| bare `except:` 零改写 | diff 中 4 处 `except:` 行零变更（S1/S2/S3/S4） |
| 签名零变更 | `^-\s*def ` = **0**；`def get_performance_summary` 仍 2 处（L336 BaseAgent 未动 / L1151） |
| 日志零变更 | `agents/` 区间 diff 中 `logger.` 行 **0 增 0 删**（唯一命中为上下文行） |
| 注释逐字 | 「如果奇异，使用伪逆」L639 无 `-` 行 |
| `else` 归属正确 | AST 实证 `If L928 orelse=['Expr']`、无 `Try.orelse`（挂错会误计「创建成功」） |
| 零新增 raise | `agents/` 生产面 `^+.*raise ` = **0** |

---

## 6. 验证体系

### 6.1 测试规格（7 函数 / 11 实例）

| 用例 | 函数 | 实例 | 断言要点 |
|------|------|------|----------|
| V1 | `test_cache_failure_counts` | 3（price / industry / mktcap 参数化） | 各计数恰为 `{key: 1}`（**损坏 pkl 按 case 分别写入**）；对应缓存 `None`；caplog WARNING+ 零记录 |
| V2 | `test_rotation_analyzer_skipped` | 1 | `sys.modules` 双注入 + `_research_team_available=True`；计数 1 且无 `rotation_analyzer_init` 键 |
| V3 | `test_team_report_failure` | 1 | `team_report` 不在 summary；`failure_counts` **同调**含该键（验证 L1162 下移） |
| V4 | `test_order_missing_price` | 2（合法 / 异常） | 合法分支计数 **0**、异常分支计数 1，两例均不产生订单 |
| V5 | `test_open_price_failures` | 2（next_day / pending） | 计数 1；`_next_day_orders` / `pending_queue` 长度不变 |
| V6 | `test_pinv_fallback` | 1 | `patch np.linalg.inv` 抛 `LinAlgError` → 计数 1；权重和 ≈ 1.0；getter 返回拷贝（改写返回值不影响内部） |
| V7 | `test_normal_path_zero_counts` | 1 | 正常求逆 → `{}`；engine no-op 日处理后 `run()["failure_counts"] == {}` |

设计要点：**只计异常，不计合法分支**（V4 双参数）、**getter 只读**（V6 拷贝断言）、**正常路径零误报**（V7）。测试统一使用 `monkeypatch`，零 `unittest.mock`。

### 6.2 三批红绿（严格隔离取证）

| 批次 | 提交 | 红态 | 绿态 |
|------|------|------|------|
| B1 `agent_framework.py` | `e86b09d` | **5 failed** | 5 passed |
| B2 `multi_strategy_engine.py` | `7cf6718` | **3 failed, 6 passed** | 9 passed |
| B3 `strategy_allocator.py` | `58954bd` | **2 failed, 9 passed**（`AttributeError: get_failure_stats`） | **11 passed** |

豁免说明：V4 合法参数集与 V7 engine 侧在红态即通过，属预期（被测语义本就正确），已在 IMPL §11.2 与 CHECKLIST E2 标注，防误判「红态不完整」。

### 6.3 门禁前后对比

| 门禁 | 基线（Step 4 @`23132cb`） | 终态 | 判定 |
|------|---------------------------|------|------|
| `pytest -q` | 711 passed | **722 passed** | ✅ +11 |
| 测试文件数 | 80 | **81** | ✅ +1 |
| `black --check core tests` | 117 unchanged | **118 unchanged** | ✅ +1 |
| `mypy --explicit-package-bases --check-untyped-defs core` | 37 files 0 error | **37 files 0 error** | ✅ 持平（`agents/` 不在门禁路径） |
| golden G1-G7 | 13 passed | **13 passed，`tests/golden/` 零改动** | ✅ 零重录 |
| I1 `except Exception`（十文件 AST） | 22 | **22** | ✅ 恒等 |
| I2 新增 `raise` | — | 生产面 **0**（测试探针 5 处豁免登记） | ✅ |
| I5 `^-\s*def ` | — | **0** | ✅ |
| I6 `logger.` 行 | — | **0 增 0 删** | ✅ |

### 6.4 盲区收敛

同口径 AST 扫描（`%TEMP%\p029_step4_scan.py`，仓库外脚本）：

```
实施前： agents/ ExceptHandler = 22，silent = 9
实施后： agents/ ExceptHandler = 22，silent = 1
         唯一残留 → research_team_v2.py:27（ImportError → 显式降级）
```

即 **8/9 的静默路径转为可观测**，剩余 1 处为设计声明面、非缺陷。

---

## 7. 质量过程：十步管线 + 双基座异构

### 7.1 时间线

| Step | 产出 | 基座 | 结论 |
|------|------|------|------|
| 1 RESEARCH | 8 处取证 + 分类 + 方案矩阵 | DeepSeek-V4.1-Flash | 完成 |
| 2 Review | E1/E2/E4 全复现 + 两项裁决 | **GLM-5.3-Flash** | pass（1 P3 + 2 观察） |
| 3 DESIGN | D1-D7 / I1-I8 / V1-V5 | DeepSeek-V4.1-Flash | 完成 |
| 4 Review | 13 项机械复核 + 五子类继承实证 | **GLM-5.3-Flash** | PASS（3 P3 + 2 观察） |
| 5 IMPL | B1-B4 拆解 + 逐锚点规格 + 7 组注入实证 | DeepSeek-V4.1-Flash | 完成 |
| 6 Review | 11 项实施文档检查 | **GLM-5.3-Flash** | pass（5 P3） |
| 7 CHECKLIST | 六组 38 项零预填 | DeepSeek-V4.1-Flash | 完成 |
| 8 Review | 机械五项 + 对齐矩阵 | **GLM-5.3-Flash** | pass（1 P3 + 1 观察） |
| 9 TDD | 三批红绿 + 门禁 + B4 回填 | DeepSeek-V4.1-Flash | 38/38 全 ✅ |
| 10 ADD + 终审 | Phase 0-4 + E1-E5 + 盲区复扫 | **GLM-5.3-Flash** | **pass 99/A，批次关闭** |

**RULE-5 异构性**：四份文档作者均为 DeepSeek-V4.1-Flash，Step 10 审计/终审为 GLM-5.3-Flash，异构条件天然成立，故审计与终审合并为一轮（区别于 P-027 的两段式）。

### 7.2 发现台账（12 项 P3，全部当轮修正）

| 来源 | ID | 内容 | 处置 |
|------|----|------|------|
| Step 2 | F-S2-P029-1 | U-P029-1 形态：建议 warning → 改为计量键（防合法缺失刷屏） | 回写 RESEARCH §8 |
| Step 4 | F-S4-P029-1 | **S4 同调出口滞后**：`failure_counts` 快照位于 try/except 之前，同调失败不可见 | 回写 DESIGN：L1152 下移 |
| Step 4 | F-S4-P029-2 | V1 触发面歧义：文件不存在时不进 except，须用**存在但损坏**的 pkl | 回写 DESIGN §4.2 |
| Step 4 | F-S4-P029-3 | 静默面清点缺口：「零改动 0 处」→ 实为 1 处（import 降级） | 回写 DESIGN §1 |
| Step 6 | F-S6-P029-1 | V1 损坏 pkl 未限定 **per-case**（三例共用 tmp_path 会互相污染） | 回写 IMPL §5 |
| Step 6 | F-S6-P029-2 | `import pickle` 未使用 | 回写 IMPL §4.4 |
| Step 6 | F-S6-P029-3 | `MultiStrategyEngine` 行号 L487 为 P-027 前旧号，实测 **L502** | 回写 IMPL §4.2 |
| Step 6 | F-S6-P029-4 | DESIGN 契约 V1-V5 与测试 V1-V7 **ID 空间重叠** | 回写 DESIGN §6 注记 |
| Step 6 | F-S6-P029-5 | Step 9 记录落点错写 §10（已被 Step 6 占用）→ 应为 §11 | 回写 IMPL §2/§3/§9.3 |
| Step 8 | F-S8-P029-1 | **A ID 双套**：CHECKLIST 验收项 A1-A6 与 IMPL 注意项 A1-A7 同名异义 | 统一加 `IMPL§7-` 前缀（13 处） |
| Step 9 | F-S9-P029-1 | 新测试文件首版未过 black（import 位序 + 超长行） | 仅格式化新增文件，代码零改动 |
| Step 10 | F-R5-P029-1 | CHECKLIST D2 实测列「测试辅助无 raise」表述失实（实含 5 处异常探针） | 当轮改写为「生产面 0 + 探针豁免登记」 |

### 7.3 最具价值的两项修正

1. **F-S4-P029-1（S4 同调入口滞后）**——若未在 Step 4 发现，S4 的计量虽写入内部字典，但**本次调用的返回值看不到**，只能等下一次调用才出现；测试 V3 的「同调断言」根本无法成立，且生产上归因窗口被推迟一个调用周期。这是设计复审直接改变实现形态的典型案例。

2. **F-S8-P029-1（A ID 双套）**——文档内两套同名不同义的 A1-A7 编号，Step 9 执行者极可能按错误的表落测试，属于「文档歧义 → 实施错位」的高危面，以 `IMPL§7-` 前缀机械消除。

### 7.4 终审取证（Step 10）

| 项 | 读数 |
|----|------|
| Phase 0 spec 质量门 | **5/5 = Tier A** |
| Phase 1 完整性 | 9 计量站点逐一命中，P-027 遗留 5 处零混淆；九面零命中 |
| Phase 2 保真度 | S1-S8 七锚点独立读码全 pass |
| Phase 3 必要性 | 生产面 raise = 0、日志 0 增 0 删、无越界文件、无顺手重构 |
| Phase 4 语义 | 出口同调 / 只计异常 / getter 拷贝 / 正常路径零计数 / 继承谱系零污染 |
| 门禁独立复跑 | 722 / 37 / 118 / 13 / 22 全绿 |
| 盲区复扫 | silent **9 → 1** |
| 评分 | `100 − 1×1 = **99/A**` |

---

## 8. 提交链与 CI

### 8.1 提交链（`9422a42` → `75c7d10`）

| 阶段 | 提交 |
|------|------|
| Step 1 RESEARCH | `9422a42` → 回填 `eeec92b` |
| Step 2 Review | `7fc094b` → `7045001` |
| Step 3 DESIGN | `0afcfec` → `f802bbe` |
| Step 4 Review | `ce5911c` → `23132cb` |
| Step 5 IMPL | `e6daa05` → `50f3a01` |
| Step 6 Review | `9614ba4` → `285d952` |
| Step 7 CHECKLIST | `2a67a59` → `b2014aa` |
| Step 8 Review | `1f2f7b4` → `2080784` |
| Step 9 TDD | `e86b09d`（B1）/ `7cf6718`（B2）/ `58954bd`（B3）/ `596e325`（B4）→ `e8578c2` |
| Step 10 | `1c68f5f`（审计记录）→ `75c7d10`（CI 回填） |

### 8.2 CI 回收

| 关键 run | 对应 | 结果 |
|----------|------|------|
| `43824569283` | Step 9 三批代码 | success（3.10 / 3.11 / 3.12） |
| `43825106609` | B4 文档回填 | success |
| `43825410759` | Step 9 回填 | success |
| `43827468599` | **Step 10 审计记录** | **success** |
| `43827751222` | Step 10 回填 | success |

全程每一次提交均回收 CI，零红灯遗留。

---

## 9. 边界、未决与后续

### 9.1 本批明确不做

| 项 | 原因 |
|----|------|
| `research_team_v2.py:27` import 降级计量 | 显式可选依赖设计，下游有 warning 兜底，可观测 |
| S6/S7 队列**重试语义**调整 | 属行为变更（U-P029-2），须独立批次 |
| 非异常静默回退（如 `sum(weights) <= 0 → 等权`） | 不在 except 判据范围（O-S4-P029-1），后续批次候选 |
| `agents/` 以外模块 | 本批范围外 |

### 9.2 遗留台账

| ID | 内容 | 状态 |
|----|------|------|
| **U-P029-2** | S6/S7 的 `return` 是否应改为队列重试 | **pending**（独立批次） |
| O-S4-P029-1 | `MeanVarianceAllocator` 等权回退为非异常静默降级 | 登记（判据扩展候选） |
| O-S4-P029-2 | 「测试文件数」口径（`tests/` 全部 .py） | 已按同口径在 CHECKLIST 注记 |
| O-S10-P029-1 | import 降级为唯一残留静默点 | 登记不改 |
| O-S10-P029-2 | U-P029-2 维持 pending | 登记 |

### 9.3 对后续批次的启示

1. **「有注释 ≠ 可观测」**：S8 的伪逆路径行内注释说明了「为什么这么做」，但不说明「这次是否发生」。治理判据应以运行期可对拍为准。
2. **出口同调是易漏点**：把计数写进字典与让计数出现在**本次**返回值是两件事，涉及快照时序时必须在设计期显式核对。
3. **文档 ID 空间需唯一**：同名不同义的编号表会在实施期直接造成错位，前缀化是低成本解法。

---

## 10. 结论

P-029 以 **9 处计量、3 个文件、零行为变更** 的代价，把 `agents/` 的静默失败面从 9 收敛到 1，并让每一处失败都能在既有 `failure_counts` 出口上被对拍：

- **可观测性**：+9 键、+1 只读 getter，全部走既有出口，无新增日志噪声；
- **安全性**：零 fail-fast、零返回语义变更、bare except 与既有文案逐字保留，722 项测试与 13 条 golden 基线零重录；
- **过程质量**：十步管线全部通过，双基座异构复审 0 P1/P2，12 项 P3 全部当轮修正；
- **可追溯**：四文档 + 本总结 + 完整提交链 + 全程 CI 全绿，任一处可独立复跑。

**批次关闭。**
