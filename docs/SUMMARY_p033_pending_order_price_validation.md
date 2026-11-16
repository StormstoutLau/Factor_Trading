# P-033 待执行订单价格有效性 · 批次总结报告（十步终态）

> **批次**: P-033 · `core/execution.py` + `core/engine_v2.py` + `agents/multi_strategy_engine.py` 三文件价格有效性守卫 + 新增账目测试（承接 O-S6-P031-3）· **T1**
> **状态**: **Step 1-10 全通过 + RULE-5 异构终审 pass，批次关闭**（2026-11-17）
> **审计基线**: 审计对象 `e53f560..c0cef1c`（2 提交，代码面集中于 `31c5d36`）· 终态 HEAD `f031db6` · **异构终审基座**: GLM-5.3-Flash（≠ 四文档作者 DeepSeek-V4.1-Flash）
> **配套文档**: [RESEARCH](RESEARCH_p033_pending_order_price_validation.md) / [DESIGN](DESIGN_p033_pending_order_price_validation.md) / [IMPL](IMPL_p033_pending_order_price_validation.md) / [CHECKLIST](CHECKLIST_p033_pending_order_price_validation.md)

---

## 1. 一页速览

| 维度 | 结果 |
|------|------|
| **治理对象** | queue 主路径（agents L505 / V2 L799）仅做 `order.stock not in open_prices` 成员检查，`NaN` / `±inf` / `≤0` 开盘价透传 `execute_order` 成交入账：R1（**P1**）cash 永久 NaN（BUY 与 SELL 双侧，SELL 还静默清零持仓）/ R2（**P2**）免费持仓与幻影现金 / R3（P3）`close=0` 告警噪声 |
| **核心手段** | **M-A 守卫单点**——模块级纯函数 `is_valid_price`（None/NaN/±inf/≤0 → False，**1 定义 + 3 调用单一判定来源**）+ `execute_order` **解析后**守卫（覆盖 OPEN / CLOSE / VWAP / CUSTOM / 未知回退五分支，含 VWAP 聚合第二 NaN 入口）+ 两引擎 queue 前置过滤；`tracker` / `pending` / `interfaces` 零改动 |
| **双层防线** | **D1 安全层**（6 直接调用点 + 委托链 + 未来调用方 + VWAP）+ **D2 可观测层**（agents 新键 `pending_invalid_price` / V2 复用 `skipped_price` 名单零新键）；B3t 红态实证 D1 先行兜底 |
| **代码规模** | `core/execution.py` **+21/−1** + `agents` **+6/−1** + `engine_v2` **+6/−1** + 新测试 **+259 行**；代码面 4 文件 **+292/−3**；全区间 12 文件 **+1703/−9** |
| **行为变更** | **1 处语义修正 + 1 个新计数键**；零 fail-fast（新增 `raise` = 0）、公开签名零变更、`except Exception` 恒 **22**、新增日志仅 1 条（executor 守卫 warning） |
| **测试** | **731 → 748 passed**（+17 实例 / 8 函数）；测试文件 **82 → 83** |
| **门禁** | black **119 → 120**；mypy **37 files 0 error**；golden **13 passed 零重录**；`except Exception` 恒 **22** |
| **质量结论** | 十步全过；**0 P0/P1/P2 + 13 P3 全部当轮处置 + 19 项观察全部登记**；异构终审 pass（批次关闭） |

一句话：**把「价格不可用 = 不成交、不入账、订单保留重试」这一唯一正确语义下沉到账目唯一入口 `execute_order`，用解析后单点守卫封住五条价格分支（含 VWAP 聚合），并让两引擎的 queue 拒绝可归因——而不是让一次数据缺口把现金污染成 NaN 或凭空创造持仓。**

---

## 2. 背景：为什么修这一批

### 2.1 缺陷与危害（Step 1 探针 10 场景实证）

| 缺陷 | 级别 | 触发条件 | 危害读数（探针原文） |
|------|------|----------|----------------------|
| **R1** 开盘价 `NaN` / `±inf` → cash 永久 NaN | **P1** | 价格数据缺口 / 新股 / 退市边界（**默认主路径即可达**） | A1 agents queue open=NaN：`n_trades=1, price=NaN, amount=NaN, cash=NaN, avg_cost=NaN`——`Trade → tracker.execute_trade: cash -= NaN` 后**无逆运算恢复**；NAV 全 NaN → P-031 nav 守卫逐日 `rebalance_nav_invalid`、组合静默冻结、指标 NaN |
| **R1 新形态**（Step 2 B2 新证） | **P1** | 有持仓时 SELL 单遇 `open=NaN` | `cash=NaN, qty=0`——现金污染与 BUY 对称，且**持仓被静默清零**（realized_pnl=NaN），比 BUY 侧更隐蔽 |
| **R2** 开盘价 `≤0` → 免费持仓 / 幻影现金 | **P2** | 停牌日价格写 0 且 `suspend` 缺失（P-010 约定掩码默认 `0=正常`）；负值脏数据 | A2 零成本：0 元购 100 股；A2b 默认成本：仅扣 `commission_min=5` 获 100 股；A3 open=-5：**cash +500**（BUY 负价反向入账）、`avg_cost=-5` 幻影浮盈 1,500 |
| **R3** 收盘价 `0` → 告警噪声 | P3 | `close=0` | numpy 除零语义返回 `inf`，仅打「差异=inf%」告警、成交照常——无账目污染，登记不改（U-P033-1） |

根因：queue 主路径与 next-day 路径是两套并行的价格处理——次日路径两引擎**均已完整防护**（`None / pd.isna / <= 0` → 保留重试），queue 路径**无任何有效性校验**；账目唯一入口 `execute_order` 全文 `isfinite`/`isna` **零命中**（N1 负向发现：缺陷严格限于 queue 路径 + executor 无契约，决定修复面）。

### 2.2 治理谱系

| 批次 | 范围 | 结论 |
|------|------|------|
| P-013/P-014 | golden 基线 + V2 三层防线（执行侧夹紧 / 再平衡刷新 / 次日过期）——价格有效性未覆盖 queue | 完成 |
| P-029 | `agents/` 9 处静默计量（`pending_open_price` 只覆盖日期切片缺失） | 完成 |
| P-031 | 防线下沉 `agents/` + 超卖夹紧；Step 6 登记 **O-S6-P031-3**（queue 价格无校验，V2 同构） | 完成 |
| P-032 | 台账收口；待办分析将 O-S6-P031-3 列为下一 T1 候选（U-P032-1 异构终审随本批 Step 1 提交顺带关闭） | 完成 |
| **P-033（本批）** | **queue 价格有效性守卫 + 计量（缺陷本体修复）** | **完成 / 关闭** |

### 2.3 触发可达性与破坏面

- **可达性**：`enable_pending_orders=True` 为默认（config L375）→ queue 是主路径；`create_default_engine` → V2。NaN = 数据缺口常态；0 = 停牌日写 0 且掩码不兜底；负值 = 脏数据。
- **测试破坏面 = 0**：全仓 `execute_order` 调用 **37 处**，`0.0` / `nan` / 负价入参**零命中**（grep 实证 + Step 2 独立复核）→ 守卫对既有测试零破坏；golden 13 条全为合法价。
- **调用点全表（Step 2 F-S2-P033-1 回写定稿）**：**6 直接调用 + 1 委托链**——有守卫 3（V2 强平 L563 / 两 next-day L451·L1140）/ 无守卫 3（V2 queue L815 / agents queue L520 / agent_framework L1420，其上游 L1340 亦仅成员检查）/ 委托链 `execute_pending_order` → `execute_order`。

---

## 3. 设计口径

### 3.1 M-A：守卫单点 + 双层防线

| 问题 | 裁决 | 依据 |
|------|------|------|
| 守卫放在哪 | **`_get_execution_price` 返回值（解析后）**，而非入参 `open_price` | 五分支各有「入参合法、解析价无效」形态：CLOSE 对 `NaN` **不回退**（L222 仅判 None，Step 4 C1 实锤）/ VWAP `sum/len` 聚合含 NaN 即 NaN（L238，Step 2 B1 实锤）/ CUSTOM 仅判 `>0` 不判有限（L246，C2 实锤）。守卫只认最终入账价 → **一个判定覆盖五分支与未来新增分支** |
| 为什么不放 `tracker.execute_trade` | 账目层堵漏掩盖上游数据错误，且 V3 共用该层（U-P033-3 归档） | 执行入口是「成交是否成立」的正确判定层 |
| 为什么引擎层还要过滤（D1 已兜底） | **可归因**（D1 只打 warning，无法进 `failure_counts` / skipped 名单聚合）+ **路径对称**（next-day 已按 `open_price` 拒绝，queue 同口径后两路径行为对称）+ **不重复实现**（共用 `is_valid_price`，无 P-031 F-S4 型同形漂移） | P-026~P-029 治理口径 |

### 3.2 六项设计决策（D1-D6）

| 决策 | 内容 | 备选与取舍 |
|------|------|------------|
| **D1** | `execute_order` 解析价守卫：`not is_valid_price(execution_price)` → 单条 warning（消息两段拼接）+ `return False, None`，早于 `amount` / `Trade` / `add_trade` → 零入账；`try` 内前置 `if`，**零新增 except** | M-B（仅引擎双处守卫）有两份同形判定漂移风险且 VWAP 裸奔（B1 实锤）；M-C 无归因 |
| **D2** | 两引擎 queue 前置过滤：agents 3 行（`_record_failure("pending_invalid_price")` + `continue`）；V2 3 行（`skipped_price.append` + `continue`，复用既有 L780 名单 + L836-839 汇总日志零新键零新日志语句） | V2 无 `_failure_counts` 基础设施，强行对齐 = API 扩张（Step 2 裁决 #4） |
| **D3** | 两引擎 next-day（L451/L1140）与 V2 强平（L563）三处 inline 判定**不重构**（O-D-P033-1） | D1 在其下游兜底形成双保险；改则触及 golden 敏感路径，收益仅代码复用 |
| **D4** | 七调用点 `False` 分支语义逐一核对——**无一处依赖「无效价必成交」** | V2 queue 留队 / next-day 入 `failed_orders` / 强平 `if success and trade` / agents 两路径不 `mark_executed` / agent_framework 优雅跳过 / fallback 委托 |
| **D5** | 不新增降噪机制 | Step 2 B3 实测：全程无效价下 `mark_expired` 半衰期 + `max_pending_days` 约 **4 交易日排空**（bounded）——每订单 ≤4 条 guard warning 可接受 |
| **D6** | R3（`close=0` 告警 `inf%`）仅登记不改判定（U-P033-1）；`agent_framework` 上游不加计量（O-D-P033-2） | 无账目污染；D1 单点已覆盖 |

### 3.3 单一判定来源与门禁预测

- `is_valid_price` **1 定义**（`core/execution.py` `TradeLog` 与 `ExecutionSimulator` 之间）+ **3 调用**（executor L309 / agents L512 / V2 L811），全仓零第二套 `pd.isna` 组合；模块级函数不进 `interfaces.py` 协议（零 API 扩张）。
- 门禁预测（DESIGN I7）：731 → **748**（V1 6 + V2 2 + V3 2 + V4 1 + V5 1 + V6 2 + V7 1 + V8 2 = **17 实例**）/ 测试文件 82 → **83** / black 119 → **120** / mypy **37 files 0** / golden **13 零重录**——Step 4 复核推算全对，Step 9 实测逐项命中。

---

## 4. 实施明细：三处落点 + 一个新函数

| 落点 | 决策 | 行为前 | 行为后 |
|------|------|--------|--------|
| `is_valid_price`（execution L153-161 新增） | D1 | —（无该函数） | 纯函数 9 行：`None → False`；`bool(np.isfinite(price) and price > 0)`；零日志零异常 |
| `execute_order` 守卫（L308-315） | D1 | 无守卫，NaN/±inf/0/负价**成交入账**（A1-A4 实证） | 解析 L304-306 → 守卫 L308-315 → 告警 L316；`return False, None` 早于 `amount` L327 与 `add_trade` L350；docstring 契约句 L298-300 |
| agents queue 过滤（L511-514） | D2 | 成员检查后直接 `execute_order`（L520） | `close_price` L509 → 过滤块 → clamp L517；`pending_invalid_price` 计数 + `continue` 保留（零 `cancel_order` 零 `mark_executed`） |
| V2 queue 过滤（L810-813） | D2 | 同上（L815） | `close_price` L804-808 → 过滤块 → clamp 告警 L815 → `execute_order` L820；`skipped_price` 归因（汇总日志 L841-844 文案逐字未改） |

**顺序敏感五项全部留证**（IMPL §11.3）：① 守卫在解析后、差异告警前；② 守卫 < `amount` < `add_trade`；③ agents 过滤在 L509 后 / clamp L517 前；④ V2 过滤在 L808 后 / clamp 告警 L815 前；⑤ B1（`is_valid_price`）先于 B2/B3 落地（导入依赖）。

**行号漂移闭环**：IMPL §11.4 漂移表 **9 行 18 项**（实施前锚点 `013c4d3` → 实施后），Step 10 独立实测逐项吻合（`ExecutionSimulator` L153→L164 / `_get_execution_price` L191-260→L202-271 / `execute_order` except L339→L359 等）。

---

## 5. 变更面与代码规模

### 5.1 逐文件读数（全区间 `8d66787..f031db6`，20 提交）

| 文件 | 性质 | numstat |
|------|------|---------|
| `core/execution.py` | B1 全落点（守卫 + 函数 + docstring） | **+21 / −1** |
| `agents/multi_strategy_engine.py` | B2（导入 + 过滤块） | **+6 / −1** |
| `core/engine_v2.py` | B3（导入 + 过滤块） | **+6 / −1** |
| `tests/test_p033_order_price_validation.py` | 新建，8 函数 17 实例 | **+259 / −0** |
| 4 份批次文档 | RESEARCH +294 / DESIGN +307 / IMPL +385 / CHECKLIST +293 | 合计 **+1279** |
| 台账与同步 | PROGRESS +126/−1 / CHANGELOG +1 / README 4/4 / ARCHITECTURE 1/1 | 合计 +132/−6 |

**全区间 12 文件 +1703 / −9**；代码 diff **7 hunk**（execution 3 / agents 2 / engine_v2 2）逐一归因 IMPL §4.1-4.4，**零游离行**（Step 10 Phase 3）。

### 5.2 关键纪律的落地证据（Step 10 审计复核）

| 纪律 | 证据 |
|------|------|
| 单一判定来源 | `is_valid_price` 全仓 1 定义（L153）+ 3 调用（L309/L512/L811）；零第二套 `pd.isna` 组合 |
| 零 fail-fast / 零新增 except | 区间 diff `^\+.*\braise\b` = 0、`^\+.*\bexcept\b` = 0；AST `except Exception` 恒 **22**（守卫与过滤块均为前置 `if`，不进异常漏斗） |
| 日志最小面 | `logger.` 仅 **+1**（executor 守卫 warning，A3 预期面）；V2 零新增（C3 口径，限文件命令 F-S8-P033-4） |
| 公开签名零变更 | `^-\s*def ` 全仓 **0**；`is_valid_price` 为模块级新增，非公开 API 变更 |
| 合法价路径不变 | `_get_execution_price` 零 hunk（漂移 +11 行仅位置）；golden **13 零重录**；既有 731 全绿 |
| 零改动面（11 面） | `tracker` / `pending` / `interfaces` / `target_positions` / `golden` / `filter/` / `scripts/` / `cli.py` / `pyproject.toml` / `test_p029*` / `test_p031*`——区间 12 文件名单零命中 |

---

## 6. 验证体系

### 6.1 测试规格（8 函数 / 17 实例，fixture F1-F6 独立、零 `unittest.mock`）

| 用例 | 函数 | 实例 | 断言要点 |
|------|------|------|----------|
| V1 守卫矩阵 | `test_v1_price_guard_matrix` | 6（参数化） | `open_price ∈ {None, NaN, inf, -inf, 0.0, -5.0}` 全 `(False, None)`、`trade_log == []`、无异常；**红态 5F/1P 豁免**（None 经 TypeError 漏斗 L339） |
| V7 VWAP NaN | `test_v7_vwap_nan_blocked` | 1 | VWAP + open/close=10 合法、high/low/volume=NaN → `(False, None)`（**第二入口回归锁**，B1） |
| V2 agents queue | `test_v2_agents_queue_invalid_open` | 2（NaN/0） | 零成交、`cash == 10_000_000`、队列长 1、`pending_invalid_price == 1` |
| V3 负价 | `test_v3_agents_queue_negative_open` | 2（-5/-inf） | 覆盖 R2「现金 +500」 |
| V4 SELL NaN | `test_v4_agents_queue_sell_nan_keeps_position` | 1 | 持仓 `qty == 100` **不清零**、`avg_cost == 10.0`（O-S2-P033-1 回归锁） |
| V5 重试 bounded | `test_v5_invalid_price_retry_bounded` | 1 | 8 日全程 NaN → 总成交 0、期末队空、`0 < count <= 5`（**区间断言**，F-I-P033-2） |
| V6 V2 queue | `test_v6_v2_queue_invalid_open` | 2（NaN/0） | 零成交、`caplog` 捕「缺少价格数据订单」+ 股票代码（`skipped_price` 无 getter → caplog 断言，F-S4-P033-2） |
| V8 正常路径 | `test_v8_normal_path_no_false_positive` | 2（agents/V2） | 合法价成交恰 1 笔 `price == 10`；零误报计数 / 零误报日志；**红态即通过显式标注**（回归保护） |

### 6.2 三批红绿（批次级口径，F-S8-P033-2 修正后）

| 批次 | 用例 | 红态 | 绿态 |
|------|------|------|------|
| B1t（D1 守卫） | V1×6 + V7 | **6 failed / 1 passed**（V1 五例 NaN/inf/-inf/0/-5 成交入账 + V7 成交；None 经 TypeError 漏斗**红态即通过豁免**） | 7 passed |
| B2t（D2 agents） | V2-V5 + V8a | **6 failed / 1 passed**（六例仍成交且无新键；V8a 豁免） | 14 passed（累计） |
| B3t（D2 V2） | V6×2 + V8b | **2 failed / 1 passed**（V6 零成交但缺汇总日志——**D1 已兜底、D2 未落地**，O-S9-P033-1 反向印证双层防线；V8b 豁免） | 17 passed |

全批红态 **14 failed / 3 passed**（6+6+2=14F；1+1+1=3P），与 Step 8 修正口径**逐项吻合**；豁免三例（V1-None / V8a / V8b）显式标注。B3t 首跑因新测试缺 `import logging` 异常（3 failed），当轮修复（F-S9-P033-2）后回到 2F/1P。

### 6.3 门禁前后对比

| 门禁 | 基线（Step 7 @`204b15f`，代码面同 §13.3 @`b837d5f`） | 终态 | 判定 |
|------|-----------------------------------|------|------|
| `pytest -q` | 731 passed | **748 passed**（172 warnings） | ✅ +17 |
| 测试文件数 | 82 | **83** | ✅ +1 |
| `black --check core tests` | 119 unchanged | **120 unchanged** | ✅ +1 |
| `mypy --explicit-package-bases core` | 37 files 0 error | **37 files 0 error** | ✅ 持平 |
| golden G1-G7 | 13 passed | **13 passed，`tests/golden/` 零改动** | ✅ 零重录 |
| 回归子集 | `-k "golden or p027 or p029 or p031"` **57 passed** | 加 `p033` 后 **74 passed**（13+24+11+9+17 口径精确） | ✅ 不回归 |
| I1 `except Exception`（十文件 AST） | 22 | **22** | ✅ 恒等 |
| `core/` 新增 except（F-S8-P033-5 补命令） | — | **0** | ✅ |
| I5 公开签名 | 零变更 | **零变更** | ✅ |

### 6.4 盲区与回归面（Step 10 复扫）

- **本批新增面**（agents / execution / 新测试文件）严格启发（body 无 log / 无 raise / 无 call 的 ExceptHandler）**0 命中**——守卫与过滤块均为前置 `if`，零新增静默路径。
- **既有浮出（非本批）**：`core/engine_v2.py` 两处 typed except（L597 退市结算 close 降级 / L1028 次日路径收盘价早退）——早于本批、非 `except Exception` 口径、显式降级语义，登记对账不处置（O-R5-P033-1）。
- P-029 V4（`_MissingPriceFrame` 注入）与 V5 占位单用例：P-031 沉下的回归面在本批 **零改动**（`test_p029*` / `test_p031*` 零触碰）。

---

## 7. 质量过程：十步管线 + 双基座异构

### 7.1 时间线

| Step | 产出 | 基座 | 结论 | CI run |
|------|------|------|------|--------|
| 1 RESEARCH | 探针 10 场景 + 负向发现 6 项 + 方案矩阵 M-A/M-B/M-C | DeepSeek-V4.1-Flash | 完成 | `43887581920` |
| 2 Review | E1 七锚点重放 + E2 探针逐字重放 + E3 **四项新证**（B1-B4） | **GLM-5.3-Flash** | pass（2 P3 当轮回写 + 2 观察） | `43890214980` |
| 3 DESIGN | D1-D6 / I1-I7 / V1-V8 / B1-B4 回退点 | DeepSeek-V4.1-Flash | 完成 | `43893100625` |
| 4 Review | E1 十锚点复核 + E2 探针 **C1-C5**（CLOSE NaN / CUSTOM inf 实锤） | **GLM-5.3-Flash** | pass（2 P3 当轮回写 + 3 观察） | `43897106641` |
| 5 IMPL | B1-B4 + 逐文件精确锚点 + 八项低效排除 | DeepSeek-V4.1-Flash | 完成 | `43900441923` |
| 6 Review | 十锚点 + 门禁基线复测 + **红态行为探针**（V1 六值实测） | **GLM-5.3-Flash** | pass（1 P3 当轮回写 + 2 观察） | `43902539354` |
| 7 CHECKLIST | 五组 **39 项**零预填 + 基线实测 | DeepSeek-V4.1-Flash | 完成 | `43905254341` |
| 8 Review | 机械五项 + 对齐矩阵七项（**F-S8-P033-2 红态批次口径更正**） | **GLM-5.3-Flash** | pass（6 P3 当轮修正 + 2 观察） | `43908389016` |
| 9 TDD | 三批红→绿（6F/1P → 6F/1P → 2F/1P）+ 门禁 + 39/39 回填 | DeepSeek-V4.1-Flash | 全绿（748/83/120/37/13/22） | `43911402921` |
| 10 ADD + 终审 | Phase 0-4 + E1-E5 独立复跑 + 盲区复扫 | **GLM-5.3-Flash** | **pass，批次关闭** | `43913759781` |

**RULE-5 异构性**：四份文档作者均为 DeepSeek-V4.1-Flash，五轮复审（Step 2/4/6/8/10）均为 GLM-5.3-Flash，异构条件全程成立；Step 10 审计与终审合并为一轮（P-029/P-031 先例）。

### 7.2 发现台账（0 P0/P1/P2 + 13 P3，全部当轮处置；19 项观察全部登记）

| 来源 | ID | 级别 | 内容 | 处置 |
|------|----|------|------|------|
| Step 2 | F-S2-P033-1 | P3 | §6 调用点盘点失准——实为 6 直接调用 + 1 委托链（漏列 `engine_v2.py:1161`），守卫面 3 有 / 3 无 | 当轮回写 §6 调用点全表 |
| Step 2 | F-S2-P033-2 | P3 | VWAP 第二 NaN 入口仅文字提及未实证——B1 实锤 `success=True, price=NaN` | 当轮回写 §7（强化「M-B 则 VWAP 裸奔」） |
| Step 4 | F-S4-P033-1 | P3 | 三处插入锚点不精确（`TradeLog` 占 L52-150 / agents L509-L511 / V2 L808-L810） | 当轮回写 §4.1-4.3 |
| Step 4 | F-S4-P033-2 | P3 | V6 断言「`skipped_price` 含该股」不可直接断言——局部列表无 getter | 当轮回写 §6（改 caplog） |
| Step 6 | F-S6-P033-1 | P3 | B1t 红态「V1 全 6 例失败」失实——None 经 TypeError 漏斗 L339 红态即通过（实际 5F/1P） | 当轮回写 IMPL §3 + §5 |
| Step 8 | F-S8-P033-1 | P3 | E10 引用节号过时（§3.38.6 已被 Step 7 记录占用） | 当轮修正 E10 |
| Step 8 | **F-S8-P033-2** | P3 | **红态批次口径失准**：「B1t 5F/1P」为 V1 矩阵级读数误作批次级（批次 = V1 6 实例 + V7 1 实例 → **6F/1P**）；E2 行内 5+6+2=13F ≠ 14F 自相矛盾 | 当轮修正 E2 + 回写 IMPL 三处（全批 14F/3P 不变；PROGRESS 历史记录不回改，O-R5-P031-1 先例） |
| Step 8 | F-S8-P033-3 | P3 | 四处裸引用 DESIGN 决策 D1/D2/D3 与 D 组不变式 ID 同字母碰撞（P-031 F-S8-P031-3 同型） | 当轮标 `DESIGN-D*` + 映射消除区间重叠 |
| Step 8 | F-S8-P033-4 | P3 | C3 证据命令未限定文件且 `^+` 未转义 | 当轮改限文件命令 |
| Step 8 | F-S8-P033-5 | P3 | `core/` 侧「零新增 except」无机械校验命令（AST 十文件口径不含 core/） | 当轮补 `git diff core/` 命令（Step 9/10 均已执行留证 =0） |
| Step 8 | F-S8-P033-6 | P3 | A2「两段 warning」歧义（实为单条调用、消息两段拼接） | 当轮修正表述 |
| Step 9 | F-S9-P033-2 | P3 | B3t 首跑红态异常——新测试缺 `import logging` → `caplog.set_level` NameError 致 3 failed | 当轮修复后重跑回到 2F/1P |
| Step 10 | F-R5-P033-1 | P3 | 测试文件净行数 +203（`Measure-Object -Line` 非空行计数偏差）vs numstat **+259**（P-031 F-R5-P031-1 同型） | 当轮修正 IMPL §11.2 + PROGRESS §3.38.8 |

观察 19 项：设计/规划期（F-D3-P033-1 CLOSE-NaN 不回退 / F-D3-P033-2 协议零扩 / O-D-P033-1 inline 判定未统一 / O-D-P033-2 agent_framework 上游 / F-I-P033-1~4 + O-I-P033-1 black 先行）、Step 2（O-S2-P033-1 SELL 清零形态 / O-S2-P033-2 bounded）、Step 4（O-S4-P033-1 非 OPEN 保守收窄 / O-S4-P033-2 R3 无测试锚点 / O-S4-P033-3 未知类型 quirk）、Step 6（O-S6-P033-1 None 行为兼容 / O-S6-P033-2 `!r` 形态）、Step 8（O-S8-P033-1 基线引用链 / O-S8-P033-2 历史不回改）、Step 9（F-S9-P033-1 black 重排 / O-S9-P033-1 D1 先行兜底）、Step 10（O-R5-P033-1 typed except 对账）——全部登记，零丢弃。

### 7.3 最具价值的三项工作

1. **Step 2 异构复审四项新证（B1-B4）**——在 RESEARCH 十场景之外把缺陷面认知扩了一圈：① **VWAP 聚合 NaN 实锤**使「仅修引擎层」的 M-B 方案被证伪（VWAP 分支裸奔）；② **SELL 侧 NaN 持仓静默清零**比 BUY 侧更隐蔽（R1 框架内新形态，直接催生 V4 回归锁）；③ **bounded 重试实证**（约 4 交易日排空）消除了「0 价拒绝后长期重试噪声」的立项疑虑，使 D5「不降噪」有据。三项新证各对应一个测试用例（V7/V4/V5），异构复审直接改写了测试规格。

2. **守卫位置「解析后」的必要性实证（Step 4 C1/C2）**——CLOSE 对 `NaN` 不回退（L222 仅判 None）与 CUSTOM 仅判 `>0` 不判有限（L246）两探针实锤了「入参合法、解析价无效」形态的存在：**入参守卫必漏，解析后单点守卫是唯一无遗漏解**。这与 Step 2 B1（VWAP）构成三类实锤，把 D1 从「设计偏好」升级为「实证必要」。

3. **F-S8-P033-2 红态批次口径更正（P3，Step 8 最重发现）**——「B1t 5F/1P」是 V1 矩阵级读数误作批次级：B1t 批次含 V1（6 实例）+ V7（1 实例），V7 红态必败，故批次级为 **6F/1P**；暴露点是 E2 行内 5+6+2=13F ≠ 14F 的自相矛盾。修正后 Step 9 实测 **6F/1P → 6F/1P → 2F/1P** 与预测逐项吻合——红态预测必须按「参数化展开 + 批次内全部用例」的批次级口径机械相加，矩阵级读数不得混用。

### 7.4 终审取证（Step 10）

| 项 | 读数 |
|----|------|
| Phase 0 spec 质量门 | **5/5 = Tier A**（可测试约束 / 模块映射 / 接口契约 / 修正项 / 跨模块契约全 1 分） |
| Phase 1 完整性 | 12 文件 +1703/−9（Step 9 区间 10 文件 +419/−52）；代码 7 hunk；计量键 agents 1 / V2 0；logger +1 / raise 0 / except 0；零改动面零命中 |
| Phase 2 保真度 | IMPL §4 四规格独立读码逐字吻合；漂移表 18 项逐项复核；签名零变更（脚本「order ok False」正则伪影已手工核验排除） |
| Phase 3 必要性 | 7 hunk 逐一归因 §4.1/§4.2/§4.3①②/§4.4①②，零游离行 |
| Phase 4 语义 | 守卫语义（五分支覆盖）/ 重试生命周期（V5 实证 8 日排空）/ 计量不对称有据 / 合法价不变 / 双层防线（B3t 实证 D1 先行兜底）——五面裁决成立 |
| E1-E5 门禁独立复跑 | **748 / 17 / 120 / 37 / 74 / 83 / 22 / core except 0** 全绿（不采信 Step 9 自报） |
| 盲区复扫 | 新增面零静默；engine_v2 两处既有 typed except 良性登记 |
| 发现 | 0 P0/P1/P2 + 1 P3 当轮修正（F-R5-P033-1）+ 1 观察 |

---

## 8. 提交链与 CI

### 8.1 提交链（`8d66787` → `f031db6`，20 提交，每 Step 一主提交 + 一 CI 回填）

| 阶段 | 提交 → 回填 |
|------|-------------|
| Step 1 RESEARCH | `839f5b5` → `0615a6c` |
| Step 2 Review | `c233846` → `d9f821b` |
| Step 3 DESIGN | `9d3e4d7` → `470efea` |
| Step 4 Review | `5c8962b` → `013c4d3` |
| Step 5 IMPL | `ca78f5f` → `b837d5f` |
| Step 6 Review | `ae86506` → `204b15f` |
| Step 7 CHECKLIST | `e0aba52` → `7723bfe` |
| Step 8 Review | `0f9adff` → `e53f560` |
| Step 9 TDD | `31c5d36`（代码+文档一体）→ `c0cef1c` |
| Step 10 | `61e8f97`（审计记录）→ `f031db6` |

### 8.2 CI 回收（已登记 13 run 全 success，零红灯遗留）

| run | 对应 | 结果 |
|-----|------|------|
| `43887581920` | Step 1 | success |
| `43890214980` | Step 2 | success |
| `43893100625` | Step 3 | success |
| `43897106641` | Step 4 | success |
| `43900441923` | Step 5 | success |
| `43902539354` | Step 6 | success |
| `43905254341` | Step 7 | success |
| `43908389016` | Step 8 | success |
| `43908937329` | Step 8 回填 | success |
| `43911402921` | **Step 9 代码落地** | success |
| `43911897185` | Step 9 回填 | success |
| `43913759781` | **Step 10 审计记录** | success |
| `43914340347` | Step 10 回填（终态） | success |

注：Step 1-7 的回填提交（`0615a6c` 等 7 个）各自触发 CI run，未在台账逐一登记（docs-only，与主提交同一代码面）；全区间每个代码面均至少有一次 success run 覆盖。

---

## 9. 边界、未决与后续

### 9.1 本批明确不做（八项低效排除）

| 项 | 原因 |
|----|------|
| `_get_execution_price` 五分支各自加校验 | 五处重复判定，新增分支即漏；解析后单点等价且更小 |
| `tracker.execute_trade` 加守卫 | 账目层堵漏掩盖上游错误，且 V3 共用（U-P033-3 归档） |
| 引擎层 type-aware 过滤（按执行价格类型） | 引擎↔executor 配置耦合，收益边际（O-S4-P033-1） |
| 统一三处 next-day/强平 inline 判定为 `is_valid_price` | 无行为收益，触及 golden 敏感路径（O-D-P033-1） |
| 为 V2 新建 `_failure_counts` 对齐 agents | API 扩张超出 T1 |
| 无效价订单 `cancel_order` 立即作废 | 改变重试语义（与 next-day 不一致）；`mark_expired` 已 bounded |
| 新增 warning 限流 | B3 实测 ≤4 交易日排空 |
| 修 R3（`close=0` 告警 `inf%` 文案） | 无账目污染，独立 T3 候选（U-P033-1） |

### 9.2 遗留台账

| ID | 内容 | 状态 |
|----|------|------|
| U-P033-1 | R3 `close=0` 告警文案（`inf%`）改进 | pending（触发：T3 文案治理批；实施时须补测试锚点，O-S4-P033-2） |
| U-P033-2 | BUY 侧现金夹紧 | pending（与 U-P031-2 / U-P014-3 同列） |
| U-P033-3 | 账目层（`tracker.execute_trade`）价格守卫 | 归档（D1 裁决不采纳——掩盖上游错误且 V3 共用） |
| R-P033-1 | 引擎预过滤按 `open_price` 判定（非 OPEN 下「open 无效但 close 有效」由成交变拒绝） | 接受（与 next-day 对称的有意收窄，已披露） |
| R-P033-2 | V2 `skipped_price` 语义扩展为「成员缺失 ∪ 价格无效」 | 接受（汇总日志文案仍适用） |
| R-P033-3 | guard warning 频次 | 接受（bounded ≤4 交易日） |
| O-D-P033-1 / O-D-P033-2 | 三处 inline 判定未统一 / `agent_framework:1420` 上游仅成员检查 | 登记不改（D1 单点覆盖） |
| O-R5-P033-1 | `engine_v2.py` 两处既有 typed except（L597 / L1028） | 登记对账（良性，早于本批） |

### 9.3 对后续批次的启示

1. **账目入口守卫必须放在「解析后」而非「入参」**——CLOSE 不回退 / CUSTOM 不判有限 / VWAP 聚合三类「入参合法、解析价无效」形态被 C1/C2/B1 三探针实锤；任何「在调用方查入参」的方案都存在结构性遗漏面。未来新增执行价格类型或新调用方时，守卫自动生效（无需调用方自觉）。
2. **安全层与可观测层职责分离，两层共用单一判定来源**——D1（executor 守卫）兜底全部调用方与未来调用方，D2（引擎过滤）让 queue 拒绝可归因；B3t 红态实证 D1 先行兜底（即使 D2 未落地，零成交断言已成立），证明两层不是冗余而是纵深。判定函数单一定义（1 定义 + 3 调用）杜绝了 P-031 F-S4 型「两份同形判定漂移」。
3. **计量形态由既有基础设施决定，不强求跨引擎对称**——agents 有 `_record_failure` 即新增键；V2 无该基础设施即复用 `skipped_price` 局部名单 + 既有汇总日志（零新键零新日志语句）。强行对齐意味着 API 扩张（Step 2 裁决 #4）——「一致性」的目标是判定口径一致（同一 `is_valid_price`），而非计数容器形式一致。
4. **红态预测必须按批次级口径机械相加**——F-S8-P033-2 的教训：矩阵级读数（V1 内 5F/1P）误作批次级（B1t = V1 + V7 共 7 实例 → 6F/1P），靠行内加和自相矛盾（13F ≠ 14F）才暴露。红态预测应遍历批次内全部收集实例（含参数化展开）逐一判定豁免。

---

## 10. 结论

P-033 以 **3 文件 +33/−3、零 fail-fast、零新增 except、公开签名零变更、golden 零重录** 的代价，把 queue 主路径的价格有效性缺陷（R1 P1 + R2 P2）全部闭环：

- **正确性**：无效价（None / NaN / ±inf / ≤0）由「静默成交污染账目」转为「拒绝 + 计量 + 保留重试」——cash 不再被污染为 NaN、不再凭空产生免费持仓与幻影现金；`Trade.price` 恒为有限正数（I1 后置条件由 V1/V7 锁定）；
- **覆盖完备**：解析后单点守卫覆盖 OPEN / CLOSE / VWAP / CUSTOM / 未知回退五分支 + 6 直接调用点 + 委托链 + 未来调用方；VWAP 聚合第二 NaN 入口（B1 实锤）同批封堵；
- **可观测**：agents `pending_invalid_price` 新键 + V2 既有 `skipped_price` 链路，queue 拒绝可归因；拒绝订单保留重试有界（≤4 交易日排空）；
- **过程质量**：十步管线全部通过，五轮异构复审 **0 漏检 P0/P1/P2**；13 P3 全部当轮处置、19 项观察全部登记；终审 Phase 0 5/5 Tier A + 四相全过 + 门禁独立复跑全绿；
- **可追溯**：四文档 + 本总结 + 20 提交链 + 13 次 CI 全绿，任一处可独立复跑。

**批次关闭。**
