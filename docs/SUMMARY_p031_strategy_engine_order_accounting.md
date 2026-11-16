# P-031 `StrategyEngine` 订单簿与估值时序 · 批次总结报告（十步终态）

> **批次**: P-031 · `agents/multi_strategy_engine.py` 单文件四项账目缺陷修复 + 中性空头腿显式降级（承接 U-P029-2）· **T1**
> **状态**: **Step 1-10 全通过 + RULE-5 异构终审 pass，批次关闭**（2026-11-16）
> **审计基线**: 审计对象 `6a7771e..780197c`（6 提交，代码面集中于 `750674e`）· 终态 HEAD `ce56c52` · **异构终审基座**: GLM-5.3-Flash（≠ 四文档作者 DeepSeek-V4.1-Flash）· **评分 99/A**
> **配套文档**: [RESEARCH](RESEARCH_p031_strategy_engine_order_accounting.md) / [DESIGN](DESIGN_p031_strategy_engine_order_accounting.md) / [IMPL](IMPL_p031_strategy_engine_order_accounting.md) / [CHECKLIST](CHECKLIST_p031_strategy_engine_order_accounting.md)

---

## 1. 一页速览

| 维度 | 结果 |
|------|------|
| **治理对象** | `StrategyEngine`（多策略引擎单策略载体）的四项账目缺陷：R2 目标外持仓不生成卖出单（P1）/ R4 超卖成交入账致现金虚增（P1）/ R1 再平衡 NAV 漏计当日成交致自激换手（P2）/ R3 失败单重复累积（P2） |
| **核心手段** | **P-014 三层防线下沉 `agents/`**——对齐 `core/` 已验证语义：`compute_portfolio_value` + `build_target_positions`（D1）/ `_clamp_sell_quantity` 同形复刻（D3）/ 双载体撤销 + `is_expired`（D4）；**`core/` 零改动** |
| **显式降级** | `direction="both"` 的空头腿禁用（D2）：账目模型无负持仓结算（探针 8 日 cash 10M→90M 幻影现金），改半仓多头 + 三重披露（init WARNING / 计数 / `additional_info`） |
| **代码规模** | `agents/multi_strategy_engine.py` **+133/−83** + 新测试 **+272 行**；全区间 8 文件 **+714/−98** |
| **行为变更** | **4 处语义修正 + 1 处显式降级**；零 fail-fast（新增 `raise` = 0）、公开签名零变更、`except Exception` 恒 **22**、新增日志仅 1 条 init WARNING |
| **测试** | **722 → 731 passed**（+9 实例 / 8 函数）；测试文件 **81 → 82** |
| **门禁** | black **118 → 119**；mypy **37 files 0 error**；golden **13 passed 零重录**；`except Exception` 恒 **22** |
| **质量结论** | 十步全过；**5 P2 + 10 P3 全部当轮处置**（P2 全部在实施前回写 DESIGN）；异构终审 99/A |

一句话：**把 `core/` 已经验证过的「估值、目标持仓、卖量夹紧、订单簿生命周期」四层防线原样下沉到多策略引擎，让 `StrategyEngine` 的账目与 V2 引擎对齐同一条正确性基准——而不是保留另一套自洽的错误实现。**

---

## 2. 背景：为什么修这一批

### 2.1 四项缺陷与危害（Step 1 探针实证）

| 缺陷 | 级别 | 触发条件 | 危害读数 |
|------|------|----------|----------|
| **R2** 目标外持仓不生成卖出单 | **P1** | 默认 `equal_weight` 即触发 | 标的被剔除后永久滞留，组合永不换出 |
| **R4** 超卖成交仍入账 | **P1** | 多头需超卖单；中性（both）**常态触发** | 3 笔 SELL×100 对 100 股持仓 → cash +3,000（应 +1,000）、NAV 虚增 2,000 |
| **R1** 再平衡 NAV 漏计当日成交 | **P2** | `frequency="daily"` | 1 股恒定 100% 目标 → **9 笔**自激换手（应 1 笔） |
| **R3** `_next_day_orders` 无过期/无撤销 | **P2** | 价格缺失/不可成交 | 失败单跨再平衡重复累积，无界重试 |

根因：`StrategyEngine` 与 `core/engine_v2` 是两套并行实现；P-014 修停牌账目时在 V2 落了三层防线（执行侧夹紧 / 再平衡刷新订单簿 / 次日订单过期），**未下沉 `agents/`**。

### 2.2 治理谱系

| 批次 | 范围 | 结论 |
|------|------|------|
| P-013 | golden 基线固化，实施期发现 **F-S9-G1（P1 停牌账目缺陷）** | 完成 |
| P-014 | V2 三层防线 + 8 项性质测试 + golden G7 | 完成 |
| P-029 | `agents/` 9 处静默计量（只加计数、零语义变更），发现 **U-P029-2**：三层防线未下沉 | 完成 |
| P-030 | 台账收口，U-P029-2 立项跟踪 | 完成 |
| **P-031（本批）** | **防线本体下沉 + 四项缺陷修复 + 中性腿显式降级** | **完成 / 关闭** |

### 2.3 Step 2 异构 Review 两项新证

GLM-5.3-Flash 独立复核在四缺陷之外追加两项实证：① 中性空头腿幻影现金（8 日 cash 10M→90M）；② `build_target_positions` 对负权重抛 `ValueError`（M-A 方案不兼容）——后者直接改写了 D2 的设计空间。

---

## 3. 设计口径

### 3.1 六条不可越界前提（IMPL §1）

| # | 前提 | 理由 |
|---|------|------|
| 1 | **`core/` 零改动** | `compute_portfolio_value` / `build_target_positions` / `cancel_orders` / `is_expired` 全部只读复用（I6 / D7） |
| 2 | **修复落在被调函数内部** | `_execute_next_day_orders` / `_process_pending_orders` / `_execute_rebalance` 各有两条调用路径（`_process_trading_day` 与 `MultiStrategyEngine` 自建循环），在调用方打补丁必漏（F-D3-P031-1） |
| 3 | **双路径夹紧** | 次日路径 + 队列路径同形——队列路径是**默认主路径**（`enable_pending_orders=True`），不修则 R4 默认可达（F-S4-P031-1） |
| 4 | **双载体撤销** | `_next_day_orders` keep/drop + `pending_queue.cancel_orders`（F-S4-P031-1） |
| 5 | **nav 守卫先于 `build_target_positions`** | 该函数对 `total_value<=0` 抛 `ValueError`，而多策略循环 L751/L882 **无 try**——不守卫则杀死整个回测（F-S4-P031-2） |
| 6 | **中性不重归一化** | `long_weights * long_weight` 半仓原样缩放，拒绝静默放大 2 倍风险敞口（F-S4-P031-4 裁决 (a)） |

### 3.2 四项必答裁决

| 裁决 | 内容 | 备选与取舍 |
|------|------|------------|
| **D1** | `_generate_orders` 改 `compute_portfolio_value`（价格重算 NAV）+ `build_target_positions`（目标 ∪ 当前并集） | 对齐 V2 L953-990 已验证语义；`value_buffer=0.985` 沿用默认（口径统一，买入量 −1.5% 属可解释代价） |
| **D2** | 中性空头腿**显式禁用**而非 fail-fast | fail-fast 会使 `MultiStrategyEngine`（固定构造三腿）整体不可用；完整做空需改 `core/tracker.py`（超出 T1，登记 U-P031-1） |
| **D3** | 执行侧卖量夹紧，`core/tracker.py` 零改动 | 拒改 tracker 的真实依据是 **T1 范围纪律** + 防御纵深层次（V2 夹紧后 golden 路径超卖不可达，非「必然破坏 golden」——Step 4 理由精化） |
| **D4** | 再平衡双载体撤销 + 复用 `is_expired`（BUY 5 / SELL 10 自然日，含半衰期 3） | 与 V2 L911-917 / P-014 同源；域外在途单保留（同口径） |

D5（O1 空头盯市 + `direction="short"` 语义）不并入本批；D6 六计数键 + `additional_info` 出口；D7 九面零改动。

### 3.3 六计数键定稿

`oversell_blocked` / `oversell_trimmed` / `next_day_orders_cancelled` / `next_day_orders_expired` / `neutral_short_leg_skipped` / `rebalance_nav_invalid`（Step 4 由 5 键扩为 6 键）

---

## 4. 实施明细：五个落点 + 一个新方法

| 落点 | 决策 | 行为前 | 行为后 |
|------|------|--------|--------|
| `_generate_orders`（L325） | D1 | 遍历 `target_weights` 自算目标量，NAV 用现金+市值快照 | 价格重算 NAV + nav 守卫 + 目标并集（目标外持仓 → SELL 清仓） |
| `_generate_rebalance_orders`（L361） | D1 | 单循环混合买卖 | 签名改 `dict[str, TargetPosition]`，**先 SELL 后 BUY** 两轮 |
| `_execute_neutral_rebalance`（L282） | D2 | 多头腿 + 空头腿合并（空头 SELL 无持仓 → 幻影现金） | 删 `short_optimizer`，仅多头腿 × `long_weight` 半仓 + 计数 |
| `_clamp_sell_quantity`（L385，新增） | D3 | —（无夹紧） | BUY 早退；SELL 取 `min(订单量, 可卖持仓)`，无持仓返回 0 |
| `_execute_next_day_orders`（L396） | D3+D4 | 直接按 `order.quantity` 执行；陈旧单无限重试 | 过期过滤（切片后，F-I-P031-1）+ 夹紧 + `execute_order(..., qty, ...)` |
| `_process_pending_orders`（L478） | D3 | 走 `execute_pending_order`（固定 `order.quantity`） | 同形夹紧 + blocked 调 `cancel_order` + 直调 `execute_order(..., qty, ..., close_price)`（F-I-P031-2） |
| `_execute_rebalance`（L212） | D4 | 在途单跨再平衡残留 | 信号索引早退后、`daily_signal` 前双载体撤销（计数计「发生次数」） |
| `_generate_results`（L530） | D2/D6 | 无中性标记 | `additional_info.neutral_short_leg = "unsupported" / "not_applicable"`（多策略两循环直调面覆盖） |
| `__init__`（L113） | D2 | — | `both` 构造期 1 条 WARNING（含 `unsupported` 文案） |

**队列路径语义保全**：`mark_executed` 仍对原订单对象（队列簿记无孤儿）；被夹紧订单 `quantity` 不就地改写，`filled_qty` 与 V2 同期口径。

---

## 5. 变更面与代码规模

### 5.1 逐文件读数（全区间 `6a7771e..780197c`）

| 文件 | 性质 | numstat |
|------|------|---------|
| `agents/multi_strategy_engine.py` | D1-D4 全部落点（唯一代码变更文件） | **+133 / −83** |
| `tests/test_p031_strategy_engine_accounting.py` | 新建，8 函数 9 实例 | **+272 / −0** |
| 6 份文档 | CHECKLIST（+198）/ IMPL（+69/−9）/ PROGRESS（+36/−1）/ README（4/4）/ ARCHITECTURE（1/1）/ CHANGELOG（+1） | 合计 |

**全区间 8 文件 +714 / −98**；代码 diff **11 hunk** 逐一归因 IMPL §4.1-4.9，零游离行。

### 5.2 关键纪律的落地证据（Step 10 审计复核）

| 纪律 | 证据 |
|------|------|
| `core/` 零改动 | 区间 8 文件名单不含 `core/`；`git status --short core tests/golden` 空 |
| 公开签名零变更 | `^-\s*def ` 唯一 `_generate_rebalance_orders`（私有，IMPL §8 允许项） |
| 零 fail-fast | 区间 diff `^\+.*\braise\b` = **0** |
| 日志最小面 | `logger.` 行仅 **+1**（init WARNING，D6 口径）；D1 用 typed `except (KeyError, IndexError)` 不入 I1 口径 |
| 顺序敏感五项 | 撤销块（早退后 / `daily_signal` 前）· 过期过滤（切片后）· 计数（optimize 成功后）· nav 守卫（`build_target_positions` 前）· B1 先于 B2——逐项行号留证 |
| 行号漂移闭环 | IMPL §11.3 漂移表 11 项 vs 实测 def 行号全命中（L74/L155/L212/L282/L325/L361/L385/L396/L478/L530/L130） |

---

## 6. 验证体系

### 6.1 测试规格（8 函数 / 9 实例，fixture 独立）

| 用例 | 函数 | 实例 | 断言要点 |
|------|------|------|----------|
| V5 | `test_neutral_short_leg_unsupported` | 1 | both → 构造期恰 1 条 WARNING（含 `unsupported`）；`neutral_short_leg_skipped == 1`；零 SELL 成交；买入名义 ≈ `capital × 0.5 × 0.985`（**半仓不重归一化**）；long 分支零 WARNING + `not_applicable` |
| V1 | `test_exit_order_for_dropped_holding` | 1 | 持仓 A=1000、目标仅 B → 恰 1 张 `SELL A 1000`；执行后 A=0、B>0（旧实现 sells=0） |
| V2 | `test_nav_timing_single_trade` | 1 | 1 股常量价 + `daily` + 恒定 100% → **恰 1 笔**（旧实现 9 笔）；NAV 恒 10M（rel 1e-12） |
| V2b | `test_nav_guard_on_zero_equity` | 1 | nav=0 → **不抛异常**、`rebalance_nav_invalid == 1`、零订单 |
| V3 | `test_oversell_clamped` | 2（next_day / queue 参数化） | 100 股 + 3×SELL100 → 成交 **1 笔 100 股**、`oversell_blocked == 2`、cash 恰 **+1,000** |
| V4 | `test_stale_orders_cancelled_on_rebalance` / `test_stale_orders_expired` | 2 | ① 域内撤销（`== 1`）、域外 Z 保留；② BUY 单 7 自然日 ≥ 5 → `next_day_orders_expired == 1`、不再执行 |
| V6 | `test_normal_path_zero_new_counters` | 1 | 全链路 `run()` → 6 新键全 0；既有键（`orders_missing_price` / `next_day_open_price`）零误报 |

设计要点：fixture 独立复制（**不修改** `test_p027` / `test_p029` / `test_rebalance_exits`）；零 `unittest.mock`；V2/V3 零成本配置隔离估值时序与费用摩擦（F-I-P031-7）。

### 6.2 四批红绿（严格逐批取证）

| 批次 | 用例 | 红态 | 绿态 |
|------|------|------|------|
| B1（D2 中性禁用） | V5 | **1 failed**（0 条 WARNING + KeyError） | 1 passed |
| B2（D1 估值/目标持仓） | V1/V2/V2b | **3 failed**（V1 `sells 0 == 1`；V2 **9 笔**，与 RESEARCH R1 逐字一致；V2b 计数缺失） | 4 passed |
| B3（D3 双路径夹紧） | V3×2 | **2 failed**（两路径各 `assert 3 == 1`） | 6 passed |
| B4（D4 撤销/过期） | V4×2/V6 | **2 failed**（陈旧单在簿 / `KeyError: next_day_orders_expired`）——**V6 红态即通过**（回归保护，显式标注不伪造红态） | **9 passed** |

### 6.3 门禁前后对比

| 门禁 | 基线（Step 7 @`6a7771e`） | 终态 | 判定 |
|------|---------------------------|------|------|
| `pytest -q` | 722 passed | **731 passed**（172 warnings） | ✅ +9 |
| 测试文件数 | 81 | **82** | ✅ +1 |
| `black --check core tests` | 118 unchanged | **119 unchanged** | ✅ +1 |
| `mypy --explicit-package-bases core` | 37 files 0 error | **37 files 0 error** | ✅ 持平 |
| golden G1-G7 | 13 passed | **13 passed，`tests/golden/` 零改动** | ✅ 零重录 |
| P-027 + P-029 回归面 | 24 + 11 | **48 passed**（13+24+11 口径精确） | ✅ 不回归 |
| I1 `except Exception`（十文件 AST） | 22 | **22** | ✅ 恒等 |
| I5 公开签名 | 零变更 | **零变更** | ✅ |

### 6.4 盲区与回归面（Step 10 复扫）

- `agents/` ExceptHandler=22，严格启发 silent=2——均为**早于本批且已登记**的点（`research_team_v2.py:27` 可选依赖降级 / `agent_framework.py:1543` demo 入口 print+traceback，P-027 零改动面行号漂移）；P-031 **零新增静默路径**（6 新计数站点全带 `_record_failure`）。
- P-029 V4（`_MissingPriceFrame` 注入）在**新入口**仍命中（`-k order_missing_price` 2 passed，B8）；V5 占位单用例经 F-I-P031-1 顺序调整后回归面零改动。

---

## 7. 质量过程：十步管线 + 双基座异构

### 7.1 时间线

| Step | 产出 | 基座 | 结论 | CI run |
|------|------|------|------|--------|
| 1 RESEARCH | 四项缺陷探针实证 + 复现矩阵 + 方案矩阵 M-A/M-B/M-C | DeepSeek-V4.1-Flash | 完成 | `43846628720` |
| 2 Review | E1 十锚点 + E2 六组读数复现 + 两项新证 | **GLM-5.3-Flash** | pass（**2 P2 当轮回写**） | `43848605214` |
| 3 DESIGN | D1-D7 / I1-I8 / V1-V6 + B1-B5 切分 | DeepSeek-V4.1-Flash | 完成 | `43849761573` |
| 4 Review | E1 五锚点 + E2 两探针（Q1 queue 无夹紧实锤） | **GLM-5.3-Flash** | pass（**3 P2 + 1 P3 当轮回写**） | `43853333069` |
| 5 IMPL | B1-B5 + 逐函数锚点规格 + 7 项实施期发现 | DeepSeek-V4.1-Flash | 完成 | `43854958855` |
| 6 Review | 十二锚点 + 门禁基线复测 + 探针（nav 守卫 / is_expired 阈值） | **GLM-5.3-Flash** | pass（1 P3 回写 + 3 观察） | `43858051695` |
| 7 CHECKLIST | 六组 **46 项**零预填 + 基线四项实测 | DeepSeek-V4.1-Flash | 完成 | `43859690027` |
| 8 Review | 机械五项 + 对齐矩阵七项 | **GLM-5.3-Flash** | pass（3 P3 当轮处置 + 3 观察） | `43861365698` |
| 9 TDD | 四批红→绿 + 门禁 + 46/46 回填 | DeepSeek-V4.1-Flash | 全绿（731/82/119/37/golden 13/22） | `43864133531` |
| 10 ADD + 终审 | Phase 0-4 + E1-E5 独立复跑 + 盲区复扫 | **GLM-5.3-Flash** | **pass 99/A，批次关闭** | `43867147356` |

**RULE-5 异构性**：四份文档作者均为 DeepSeek-V4.1-Flash，五轮复审（Step 2/4/6/8/10）均为 GLM-5.3-Flash，异构条件全程成立；Step 10 审计与终审合并为一轮（同 P-029 先例）。

### 7.2 发现台账（5 P2 + 10 P3，全部当轮处置）

| 来源 | ID | 级别 | 内容 | 处置 |
|------|----|------|------|------|
| Step 2 | F-S2-P031-1 | P2 | M-A（目标持仓并集）与中性负权重不兼容 | 回写 DESIGN → D2 中性腿禁用 |
| Step 2 | F-S2-P031-2 | P2 | 中性空头腿常态触发幻影现金（cash 10M→90M） | 回写 DESIGN → D2 |
| Step 4 | F-S4-P031-1 | P2 | D3/D4 仅覆盖次日路径——默认主路径 queue 无夹紧无撤销（Q1 实证 cash 虚增 2,000） | 回写 DESIGN：双路径夹紧 + 双载体撤销 + 新增 §4.7 |
| Step 4 | F-S4-P031-2 | P2 | D1 未定义 nav≤0——`ValueError` × 多策略循环无 try = 杀死整个回测 | 回写 DESIGN：nav 守卫 + 第 6 键 |
| Step 4 | F-S4-P031-4 | P2 | D2 未定义禁用后资金部署（50% 现金闲置未披露） | 回写 DESIGN：裁决 (a) 半仓 + 双重披露 + U-P031-4 |
| Step 4 | F-S4-P031-3 | P3 | `orders_missing_price` 触发面变更（逐股 → 日期切片） | 注记 + Step 9 实证（B8） |
| Step 5 | F-I-P031-1 | P3 | 过期过滤前置会撞 P-029 V5 占位单（AttributeError） | 移至切片后（回归面零改动） |
| Step 5 | F-I-P031-2 | P3 | `execute_pending_order` 固定 `order.quantity` 无法夹紧 | queue 路径直调 `execute_order(qty)` |
| Step 5 | F-I-P031-7 | P3 | DESIGN V2「成交 1 笔」在默认成本下不可达（费用摩擦） | V2/V3 改零成本口径（判别力保留） |
| Step 6 | F-S6-P031-1 | P3 | V4② 未指定订单方向——SELL 6 日不过期（vitality 0.25 > 0.125）会假红 | 显式 BUY 单（≥6 日） |
| Step 8 | F-S8-P031-1 | P3 | A2/A6 要求半仓断言但 IMPL §5 V5 未列 | 回写 IMPL §5 V5 |
| Step 8 | F-S8-P031-2 | P3 | E5 引用 AST 扫描但 IMPL 无命令定义 | 回写 IMPL §11（复用 P-029 十文件命令） |
| Step 8 | F-S8-P031-3 | P3 | B4 锚点「V2 语义」违反 DESIGN-V* 前缀规则 | 改 DESIGN-V2 |
| Step 9 | F-S9-P031-1 | P3 | D4 判据「`mark_expired` 仅 1 处」失实（实为 2 调用 + 1 注释） | 当轮修正 CHECKLIST D4 |
| Step 10 | F-R5-P031-1 | P3 | IMPL §11.2 测试行数「+270（未计入 numstat）」与提交后实测 **+272** 不符且前提失效 | 当轮修正该单元格 |

观察 15 项（O-S4-P031-1/2/3、F-I-P031-3/4/5/6、O-S6-P031-1/2/3、O-S8-P031-1/2/3、F-S9-P031-2/3、O-R5-P031-1/2）全部登记，零丢弃。

### 7.3 最具价值的三项修正

1. **F-S4-P031-1（默认主路径盲区，P2）**——若按 DESIGN 初稿只修次日路径，四项缺陷中 R4/R3 在**默认配置（`enable_pending_orders=True`）下依然存在**：「修完了，但没修到用户实际跑的路径上」。Step 4 独立探针 Q1 用 3 张 SELL 全成交 + cash 虚增 2,000 的实测读数逼出双路径/双载体改造，是全批影响最大的发现。

2. **F-S4-P031-2（nav 守卫，P2）**——`build_target_positions` 对 `nav<=0` 抛 `ValueError`，而 `MultiStrategyEngine` 两条循环调用点**无 try**：不守卫则一次坏 NAV 不只是跳过一次调仓，而是**杀死整个多策略回测**。守卫从「防御性编程」升级为「生产存活条件」，并连带产出第 6 计数键。

3. **F-I-P031-1（回归面优先，P3）**——DESIGN 要求过期过滤在开盘价切片**之前**，但 P-029 V5 fixture 用 `object()` 占位订单会在 `.side` 上 `AttributeError`。实施移到切片**之后**，以「整日无开盘价的退化日推迟一天过期」这一有界且不可观测的代价，换既有回归面零改动——设计稿锚点与真实 fixture 冲突时，回归面稳定优先。

### 7.4 终审取证（Step 10）

| 项 | 读数 |
|----|------|
| Phase 0 spec 质量门 | **5/5 = Tier A** |
| Phase 1 完整性 | 8 文件 +714/−98；6 键 8 站点、logger +1、raise 0、九面零命中 |
| Phase 2 保真度 | 九函数独立读码 pass；漂移表 11 项全命中；签名零变更 |
| Phase 3 必要性 | 11 hunk 逐一归因 D1-D7 / IMPL §4，零游离行 |
| Phase 4 语义 | 超卖纵深防御 / 撤销先于生成 / 过期有界 / NAV 守卫拦截 nan/±inf/0/负 / 中性三重披露 |
| 门禁独立复跑 | 731 / 119 / 37 / 48 / 82 / 22 全绿（不采信 Step 9 自报） |
| 盲区复扫 | agents/ 零新增静默 |
| 评分 | `100 − 1×1 = **99/A**` |

---

## 8. 提交链与 CI

### 8.1 提交链（`a97ba1b` → `ce56c52`，20 提交）

| 阶段 | 提交 |
|------|------|
| Step 1 RESEARCH | `a97ba1b` → 回填 `fae43ce` |
| Step 2 Review | `ef5438e` → 回填 `bf4a71b` |
| Step 3 DESIGN | `af198bc` → 回填 `d0ae37b` |
| Step 4 Review | `f879d67` → 回填 `96bed8d` |
| Step 5 IMPL | `0219047` → 回填 `4278179` |
| Step 6 Review | `8d26530` → 回填 `6a7771e` |
| Step 7 CHECKLIST | `c913243` → 回填 `a126379` |
| Step 8 Review | `3c2e3de` → 回填 `6eb016d` |
| Step 9 TDD | `750674e`（代码+文档一体）→ 回填 `780197c` |
| Step 10 | `c1fed32`（审计记录）→ 回填 `ce56c52` |

### 8.2 CI 回收（11 run 全 success，零红灯遗留）

| run | 对应 | 结果 |
|-----|------|------|
| `43846628720` | Step 1 | success |
| `43848605214` | Step 2 | success |
| `43849761573` | Step 3 | success |
| `43853333069` | Step 4 | success |
| `43854958855` | Step 5 | success |
| `43858051695` | Step 6 | success |
| `43859690027` | Step 7 | success |
| `43861365698` | Step 8 | success |
| `43864133531` | **Step 9 代码落地** | success |
| `43867147356` | **Step 10 审计记录** | success |
| `43867502402` | Step 10 回填（终态） | success |

---

## 9. 边界、未决与后续

### 9.1 本批明确不做

| 项 | 原因 |
|----|------|
| 完整做空（负持仓 + 保证金 + 负市值盯市） | 需改 `core/tracker.py` / `core/execution.py`，波及 V2/V3/golden（U-P031-1） |
| `direction="both"` fail-fast | 会使 `MultiStrategyEngine`（固定三腿）整体不可用——采纳显式降级 C 案 |
| BUY 侧现金夹紧 | 与 U-P014-3 同列（U-P031-2） |
| `direction="short"` 语义（买低分 vs 真做空） | 产品定义未决，本批保持现状（U-P031-3） |
| `core/tracker.py` 现金入账守卫 | T1 范围纪律（O-P031-1） |
| `MultiStrategyEngine` 动态资金分配直写 `tracker.cash`（实施后 L968，原登记 L918） | 超出本批（O-P031-2） |
| queue 路径价格有效性校验（NaN/非正透传） | **既有行为**，本批前后一致（O-S6-P031-3，候选后续批） |

### 9.2 遗留台账

| ID | 内容 | 状态 |
|----|------|------|
| U-P031-1 | 中性策略负持仓账目模型 | pending（触发：需要真正市场中性） |
| U-P031-2 | BUY 侧现金夹紧 | pending（与 U-P014-3 同列） |
| U-P031-3 | `direction="short"` 语义 | pending |
| U-P031-4 | 中性资金部署产品化（满仓单边 vs 半仓+现金） | pending（现裁决：满仓需求显式改用 `direction="long"`） |
| O-P031-1 / O-P031-2 / O-P031-3 | tracker 守卫 / L968 直写 cash / README `register_agent` 幻觉（候选 T3） | 登记不改 |
| R-P031-1~4 | 0.985 口径差异 / 先卖后买现金序 / 撤销仅限信号域 / 半衰期 sell≈9 日 | 接受（与 V2 同口径，已披露） |
| O-R5-P031-1/2 | PROGRESS 行数约数 / 盲区 silent 读数定义依赖对账 | 登记不改 |

### 9.3 对后续批次的启示

1. **修复落点必须先枚举全部调用路径**——F-D3-P031-1 与 F-S4-P031-1 是两次同型盲区（多策略自建循环、queue 默认主路径），都靠「先枚举调用面再选落点」才堵住；补丁打在调用方 = 必漏。
2. **纵深防御两层各自独立正确**——生成侧（目标持仓并集）天然不超卖，执行侧夹紧兜底「昨日簿残留」这类跨层形态；单看任一层都成立，合起来覆盖全部可达形态。
3. **账目缺陷优先对齐已验证实现而非重写**——本批全部修复是对 `core/` 同名函数的只读复用，0 行新账目逻辑；「另一套自洽的错误实现」正是这类缺陷的根源，下沉优于重写。

---

## 10. 结论

P-031 以 **单文件 +133/−83、零 fail-fast、`core/` 零改动、golden 零重录** 的代价，把四项账目缺陷（两项 P1 + 两项 P2）全部闭环，并让中性策略的不可实现半边从「静默幻影现金」转为「显式降级 + 三重披露」：

- **正确性**：目标外持仓必清仓、现金严格守恒（+1,000 而非 +3,000）、daily 自激换手 9 笔 → 1 笔、在途单有界（撤销 + 过期）；
- **安全性**：nav 守卫阻断「一次坏 NAV 杀死整个多策略回测」；公开签名零变更；`except Exception` 恒 22；731 项测试与 13 条 golden 基线零重录；
- **过程质量**：十步管线全部通过，五轮异构复审 0 漏检 P1/P2；5 P2 全部在实施前回写 DESIGN、10 P3 全部当轮处置，终审 99/A；
- **可追溯**：四文档 + 本总结 + 20 提交链 + 11 次 CI 全绿，任一处可独立复跑。

**批次关闭。**
