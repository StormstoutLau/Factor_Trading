# P-050 Step 1 调研：期货保证金账目 / 逐日结算 / 强平 / 换月 + 股票负持仓研究模式

> **文档定位**: SPEC 十步流程 Step 1 调研产出（只出文档，不改代码、不提交）。**不是** Design、**不是** IMPL。
> **基线**: `c6f172d`（P-046a 关闭后、台账回补未提交状态）· **作者**: DeepSeek-V4.1-Flash · **复审**: GLM-5.3-Flash 已通过（2026-11-20，见 §14.1；R2/R4/R5/R6/R7 已改，R3 并入裁决 N-1）
> **上游**: `docs/UPGRADE_MASTER_PLAN.md` L267（P-050 题干）/ L273·L275（P-056/P-058 依赖）/ L325（D3 裁决）；`docs/PROGRESS.md` §1.4 `U-P031-1`
> **档位**: T1（改 `core/tracker.py` / `core/execution.py`，波及 V2/V3/golden）
> **纪律**: RULE-1 零预填（本文所有「推荐」均标注为待裁决项）/ RULE-2 统计溯源（每个计数给出机械分解）/ A5 期望值闭式手算 / E1-E5 取证分级

---

## 0. 一句话结论

现框架的账目是**「股票现货 + 只做多」**口径：`Position.market_value = |qty| × price`、现金只在 `BUY/SELL` 两侧变动、空头永不盯市且被 `quantity > 0` 过滤器整体排除。因此**期货在现状下不是"少一个保证金字段"，而是三条账目恒等式同时失效**（名义价值缺乘数、空头现金流缺失、逐日结算缺失）。P-050 的实质是把「一个标量 `market_value`」升级为「现金 / 保证金 / 盯市」三账，且必须保证**未启用期货时既有 12 个 golden 零重录**。

---

## 1. 题干还原

### 1.1 逐字题干（总纲 L267）

| 字段 | 原文 |
|------|------|
| 主题 | 期货保证金/逐日结算/强平/换月优先；股票负持仓降为研究模式（U-P031-1） |
| 前置 | 无代码前置；已裁决（D3） |
| 验收 | 期货账目 synthetic golden；纯多头既有 golden 不受影响 |

### 1.2 D3 裁决（总纲 L325，逐字）

> **D3** | Q3 做空路线 | 期货账目优先，股票融券仅研究 | P-050 期货保证金/逐日结算/强平/换月优先；股票负持仓仅研究模式；P-058 默认股指期货对冲

### 1.3 上下游（总纲 L273/L275/L277）

- P-056（CTP 对接）与 P-058（截面多空）**均以 P-050 为硬前置**；P-050 只做**回测账目**，不碰柜台。
- 本批**不含**：CTP/QMT 实盘、下单协议、交割实物流程、期权、融券费用模型、多币种。

### 1.4 三层可验收语义（本文拆解，待 Step 2 确认）

| 层 | 语义 | 验收载体 |
|----|------|----------|
| L1 合约名义 | `名义价值 = 数量 × 价格 × 合约乘数`；保证金 = 名义 × 保证金率 | 闭式单测 + golden |
| L2 逐日结算 | 每日按结算价把盈亏**净额划入现金**，并重算保证金占用 | synthetic golden |
| L3 强平/换月 | 结算后可用资金 < 0 → 强平；到期前移仓 | synthetic golden + 不变量 |
| L4 股票负持仓 | 研究模式开关，默认关；关闭时行为与现状**逐位一致** | 既有 golden 零重录 |

---

## 2. 代码事实基线（E3，全部绑 `c6f172d`）

### 2.1 持仓账目 `core/tracker.py`（493 行）

| 锚点 | 事实 | 对本批的含义 |
|------|------|--------------|
| L28-45 | `Position` 字段：`quantity: float`（有符号）、`avg_cost`、`market_value`、`unrealized_pnl`、`realized_pnl`、`margin_used: float = 0.0` | `margin_used` **已存在但仅声明** |
| L47-58 | `direction` 按 ±1e-10 判多/空/无 | 空头语义在半层已就绪 |
| L62-71 | `update_market_value`: `market_value = abs(quantity) * price`；`unrealized_pnl = quantity * (price - avg_cost)` | **市值取绝对值**；但 E2 实测：`update_market_values` 的 `>0` 过滤使空头永不进入该函数，故空头 `mv/upnl` **恒 0**（不是"虚增"，是"缺失"） |
| L58-60 | `exposure` = `abs(q) * market_value / abs(q)`，化简即 `market_value` | 代数上恒等于 `market_value`；E2 实测空头与未盯市多头均为 0 → 风险暴露监控失效（G-16） |
| L73-116 | `execute_trade`: `BUY` 加多、`SELL` 减多、`SELL_SHORT` 仅在 `quantity <= 0` 时加空、`BUY_TO_COVER` 仅在 `< 0` 时平空 | **无越量守卫**（E2 实测）：`SELL` 越量 → 翻负且均价不重置；`BUY_TO_COVER` 越量 → 翻多；生产 `SELL` 另有 `_clamp_sell_quantity` 兜底，回补无兜底（G-15） |
| L118-130 | `to_dict` 输出 `direction` / `total_pnl` | 可作为对账出口 |
| L150 / L154 | `PortfolioSnapshot.to_dict` 只序列化 `quantity > 0` 的持仓；`position_count` 同样只数多头 | **空头在快照序列化层消失** |
| L192-221 | `PositionTracker.execute_trade`：现金仅 `BUY` 减、`SELL` 加（L201-204） | `SELL_SHORT` / `BUY_TO_COVER` **现金零变动** |
| L223-239 | `update_market_values` 只对 `quantity > 0` 更新（L231），且不产生现金变动 | 空头**永不盯市**；多空都**不做逐日结算** |
| L241-269 | `_take_snapshot` 深拷贝全部持仓（含空头） | 快照可承载空头，仅 `to_dict` 过滤 |
| L282-288 | `get_all_positions` 过滤 `quantity > 0` | 风控/调仓/强平**看不到空头** |
| L290-297 | `get_total_value = cash + Σ market_value` | 期货/空头 NAV **恒等式错误** |
| L307-325 | `get_position_weights` 只用 `quantity > 0` | 空头权重恒 0 |
| L449-479 | `validate_positions`：`_cash < 0` 记错误（L460-462）、`quantity < -1e-10` 记错误（L466-467） | 期货"可用为负"是待强平的合法中间态；负持仓被当作**数据错误**而非合法状态 |

### 2.2 成交与成本 `core/execution.py`（532 行）

| 锚点 | 事实 | 含义 |
|------|------|------|
| L24-47 | `Trade(date, stock, side, quantity: int, price, amount, cost, net_amount)` | 无 `multiplier` / `asset_type` 字段 |
| L273-364 | `execute_order`：`amount = quantity * execution_price`（L327） | **缺合约乘数**，期货名义 = 点数而非金额 |
| L332-335 | `net_amount = amount + cost`（BUY）否则 `amount - cost` | 空头收款/回补口径可复用，但 tracker 未接 |
| L366-407 | `_calculate_cost`：`max(rate*amount, commission_min)` **对所有方向**生效（L390-392）；交易所费按 `asset_cost.exchange_fee > 0` 计提（L395-396）；印花税仅 `SELL`（L399-401）；滑点全方向（L404-405）；调用处**未传 `asset_type`**（L330） | 空单会计佣金（含最低 5 元）与滑点，但 `SELL_SHORT` 免印花；期货 `exchange_fee` 分支因 `asset_type` 缺省为 `STOCK` 而**永不生效**；无平今/平昨、无按手收费 |
| L436-459 | `calculate_liquidation_value` 同样 `quantity * price` 无乘数 | 期末估值同缺乘数 |

### 2.3 订单语义 `core/pending.py` / `core/execution_policy.py`

| 锚点 | 事实 |
|------|------|
| `pending.py` L34-40 | `OrderSide` 四值：`BUY/SELL/SELL_SHORT/BUY_TO_COVER`（语义齐全） |
| `execution_policy.py` L88-105 | `OrderIntent.action` 由「目标数量 vs 当前数量」推导，支持 `BUY/SELL/SELL_SHORT/BUY_TO_COVER/HOLD`（**意图层已有多空语义**） |
| `execution_policy.py` L235-236 | `T1StockPolicy` 显式拒绝 `SELL_SHORT` / `BUY_TO_COVER` |
| `execution_policy.py` L259-394 | `T0FuturesPolicy` **已实现**（T+0 当日回转） |
| 全仓 grep | `T0FuturesPolicy` **生产代码零调用点**（仅测试引用）；引擎 `execution_policy` 为可选注入（`engine_v2.py` L1209-1212），缺省走旧路径，**未实例化任何 Policy** |
| `execution_policy.py` L411-466 | `SignalTranslator.from_weights` 仅对 `target_w > 0` 生成目标（L444-451）；负权重 → 目标 0 |
| `execution_policy.py` L468+ | `from_signals`（含 `short`）已存在但**引擎未使用** |

### 2.4 引擎 `core/engine_v2.py`

| 锚点 | 事实 | 含义 |
|------|------|------|
| L144 / L180 | `risk_manager` 为可选注入，缺省 `None` | 保证金风控非默认路径 |
| L556-557 | 每日收盘仅 `tracker.update_market_values` | 无 `settle` 钩子 |
| L571-578 | 风控动作（含 `force_liquidation`）**仅写日志** | 风控不改变仓位 |
| L692-694 | `_force_liquidation`：`if position.quantity <= 0: continue` | **强平只平多** |
| L748-750 | `_settle_delisted`：`if pos.quantity <= 0: continue` | 退市结算同样跳过空头 |
| L811-828 | `_clamp_sell_quantity` 仅夹 `SELL`；`SELL_SHORT` 原样通过 | 空单能过数量闸门 |
| L955-968 | 待执行队列：仅 `OrderSide.BUY` 用 `estimate_buy_cash` 与 `tracker.get_cash()` 比较 | 卖出/开空**无保证金检查** |
| L1093 | `target_weights = daily_signal.clip(lower=0.0)` | **权重层硬性截断负权重** |
| L1251-1257 | policy 路径 `SignalTranslator.from_weights(..., asset_type="stock")` **硬编码**（L1256）；`_calculate_cost` 调用处亦未传 `asset_type`（`execution.py` L330） | 期货无接线；交易所费分支永不生效 |
| L1366-1377 / L1379-1383 | 次日开盘成交：同样只对 `BUY` 做现金闸门；`_clamp_sell_quantity` 后 `qty <= 0` 即丢弃，注释写明「**避免负持仓（P-014 D2/D6）**」 | 开空无资金/保证金约束；长仓唯一是**显式设计选择**而非疏漏 |
| `engine_v3_vector.py` L21 / L34 | 文档串自陈「无止损/保证金/盯市」 | V3 明确不支持，需显式拒绝而非静默错误 |

### 2.5 配置与死路径

| 锚点 | 事实 |
|------|------|
| `config.py` L150-170 | `AssetInfo` 已有 `multiplier` / `margin_ratio` / `expiry_date` |
| `config.py` L488-526 | `MarginConfig` 已有 `initial_margin_ratio=0.10` / `maintenance_margin_ratio=0.08` / `force_liquidation_ratio=0.05`，含校验（L514-519） |
| 全仓 grep | `multiplier` 在 `core/` 内**除声明外零消费点**；`expiry_date` 仅测试引用；`MarginConfig` 仅测试与 `risk_manager` 引用 |
| `risk_manager.py` L161-188 | 保证金检查以 `margin_used > 0` 为门（L162）；生产代码**从不赋值** `margin_used`（grep 仅测试）→ **保证金分支为死代码** |
| 测试面 | `test_phase2_multi_asset.py` L393+、`test_p2_risk_naming.py` L97+、`test_p0_engine_integration.py` L198+ 直接构造 `MarginConfig`；Step 5 改动需逐一复核（本文未读其断言内容） |
| `target_positions.py` L79-80 | 负权重**主动 raise** `ValueError` |
| `target_positions.py` L174 | 估值时按 `qty <= 0` 跳过 |

### 2.6 不变量 `core/invariants.py`

| 锚点 | 事实 | 冲突点 |
|------|------|--------|
| L88-110 | I1：`total_value == cash + Σ market_value` | 期货下 NAV ≠ 现金 + 名义 |
| L113-167 | I2：快照持仓 == 成交累计（`_BUY_SIDES` 含 `BUY_TO_COVER`、`_SELL_SIDES` 含 `SELL_SHORT`，按符号累加；同日多次快照跳过） | 空头语义在**不变量层已支持**，可作 P-050 现成 oracle；强平在收盘快照后追加同日快照 → 该日 I2 无定义 |
| L170-213 | I3：`Σcost == stats.total_cost`、`cost >= 0`、净额符号正确（按 `_BUY_SIDES`） | 净额符号口径必须与 tracker 四侧分支统一，否则空单先炸 |
| L216-251 | I4：`daily_return` / `cumulative_return` 与 `total_value` 一致 | 期货 NAV 重定义后 I4 自动跟随，无需改公式本体 |

> **重要推论**：不变量层对空头是**符号正确**的（I2/L26-27），唯一硬冲突是 I1 的 NAV 定义（`cash + Σ market_value`，L88-110）。因此 P-050 的不变量改造应**只重定义 I1 并新增结算/保证金恒等式**，I2 保持零改动即可复用于空头 golden。

### 2.7 golden 覆盖面（机械分解）

- `tests/golden/` 共 **12 个 json**：根目录 `G1..G7`（7）+ `p045/P045_S1,P045_S2`（2）+ `p047/P047_S1..S3`（3）。
- PROGRESS §3.52（L188）记「golden **15 → 18**」；P-047 新增 **3** 个文件、用例口径 +3 → 元测试恒为 **6** 条。故「golden 18」= **12 文件 + 6 条集合/模式守卫**（本文按此记账，来源为 PROGRESS 差分，属 E4 推导，非 E1 重跑）。
- 全部 12 例均为**股票/ETF 多头**场景（`p047` 三例为 sizing 场景）；**无期货、无空头、无保证金**用例。
- **断言面（P-050 补充调研，E3）**：golden 只比较 `portfolio_value` 序列（`tests/_golden_cases.py` L198-206）、metrics 六项（L209-217）与 `trades.count`；**不比较 `cash`、`positions`、`margin`** → 账目内部重构只要 NAV 序列不变即可零重录。

---

## 3. 缺口清单（G-P050-*）

> 严重度：**S0** 账目错误 / **S1** 功能缺失 / **S2** 语义/口径 / **S3** 文档与拒绝路径

| ID | 严重度 | 缺口 | 证据 | 影响 |
|----|--------|------|------|------|
| G-01 | S0 | 成交金额缺合约乘数 | `execution.py` L327 / L436-459 | 期货按"点数"结算，误差 = 乘数倍（IH 为 300×） |
| G-02 | S0 | `margin_used` 生产永不赋值 | `tracker.py` L45；grep 零消费 | 保证金/杠杆完全不存在 |
| G-03 | S0 | 无逐日结算：MTM 只改字段不入现金 | `tracker.py` L223-239；`engine_v2.py` L556-557 | 期货浮盈不落袋，复利/强平判定失真 |
| G-04 | S0 | 空头现金流缺失 | `tracker.py` L201-204 | 开空不收、回补不付；I2 只校验数量，故不会发现，错误全部沉入 NAV |
| G-05 | S0 | 空头市值用 `abs` | `tracker.py` L70 | 空头名义被记为资产；只放开 MTM 时开仓日即虚增 `q·P0`（见 §4.2 推导 1） |
| G-06 | S1 | 负持仓被整体过滤 | `tracker.py` L231 / L288 / L313 / L154 / L466-467 | 空头对风控、调仓、快照、权重不可见 |
| G-07 | S1 | 权重层禁止负权重 | `engine_v2.py` L1093；`target_positions.py` L79-80；`execution_policy.py` L444-451 | 空头信号在到达订单前被截断为 0 |
| G-08 | S1 | 强平只平多 | `engine_v2.py` L692-694 / L748-750 | 空头穿仓无法处置 |
| G-09 | S1 | 换月/到期缺失 | `AssetInfo.expiry_date` 零消费 | 只能持有单一合约到期末 |
| G-10 | S2 | 期货成本口径错误 | `execution.py` L390-405 | `SELL_SHORT` 免印花（与融券规则是否一致未取证）；交易所费永不生效；无平今/平昨；最低佣金按"每笔金额" |
| G-11 | S2 | 风控不闭环 | `engine_v2.py` L571-578 | 即便算出保证金不足也不动作 |
| G-12 | S2 | I1 与期货账目定义冲突 | `invariants.py` L88-110 | 期货 golden 无法通过 I1 |
| G-13 | S3 | V3 无保证金且无拒绝 | `engine_v3_vector.py` L21 / L34 | 期货配置走 V3 会静默错算 |
| G-14 | S3 | `T0FuturesPolicy` 死代码 | `execution_policy.py` L259-394；零调用点 | 实现存在但未接线，易被误判为"已支持" |
| G-15 | S2 | 反手/越量无守卫（**双向**） | `tracker.py` L86-116；E2 实测：买 100 卖 150 → qty=−50、avg_cost 仍 10、realized 按 150 股计；空 100 回补 150 → qty=+50、现金未付 | 穿仓翻转不会被拒（生产 `SELL` 有 `_clamp_sell_quantity` 兜底、**回补越量无兜底**）；均价与已实现盈亏错算，错误状态进入快照 |
| G-16 | S2 | `Position.exposure` 恒等于 `market_value` | `tracker.py` L58-60（代数化简）；E2 实测空头/未盯市多头均为 0 | 风险暴露监控（含 overlay、报表）对空头与未盯市持仓完全失效 |

---

## 4. 取证

### 4.1 E3 静态读码

见 §2 全表（15 个文件锚点，全部绑 `c6f172d`）。

### 4.2 E4/A5 闭式推导（不依赖运行）

**推导 1（股票空头研究模式，零费用）**：设开空 `q>0` 股、开仓价 `P0`、现价 `P`、初始现金 `C`。
- 应有：开空收款 `q·P0`、负债 `q·P` → `NAV = C + q(P0 − P)`。
- 现状（不入现金 + 不更新市值）：`NAV = C`，**误差 = −q(P0 − P)**（空头盈亏永不体现，开仓日误差为 0）。
- 若只放开 L231 的盯市而保留 L70 的 `abs`：`NAV = C + qP`，**误差 = q(2P − P0)**（开仓日即虚增 `q·P0`）。
- 若只补现金（L201-204）**且盯市已放开**而保留 `abs`：**误差 = +2qP**（虚增 2 倍空头名义市值。复审 R2：该式隐含盯市前提——若 L231 过滤未放开，空头 `market_value` 恒 0（`execute_trade` 开空不赋值），误差为 `q·P`）。

**推导 2（期货多头，零费用）**：1 手 IH，乘数 `m=300`，保证金率 `r=10%`，开仓/现价 `P0=3500`、`P`。
- 应有：占用保证金 `P0·m·r=105,000`；`NAV = C + (P−P0)·m`。
- 现状：`amount = 1×P0 = 3,500`、`cash = C−3,500`、`market_value = P` → `NAV = C + (P−P0)`；**每点盈亏被缩小为 1/m（1/300）**。
- 杠杆：现状下开 `n` 手仅需 `n·P` 现金，而应有 `n·P·m·r`；**允许手数被放大 `m·r = 30` 倍**。

**推导 3（期货空头，逐日结算）**：IH 空 1 手，D1 开 3500、D1 结算 3480、D2 结算 3550。
- 当日盈亏 D1 = `(3500−3480)×300 = +6,000`；D2 = `(3480−3550)×300 = −21,000`（中金所公式，见 §4.3）。
- 应有：D1 现金 `C+6,000`、保证金 `3480×300×10%=104,400`；D2 累计现金 `C−15,000`、保证金 `106,500`。
- 现状：现金恒 `C`（G-04）、保证金恒 0（G-02）→ 两日后 NAV 与真值差 `15,000`，且随行情持续累积、永不收敛。

### 4.3 外部规则证据（分级）

| 编号 | 断言 | 来源 | 等级 | 取证方式 |
|------|------|------|------|----------|
| F1 | 「交易所实行当日无负债结算制度……按照当日结算价对结算会员所有合约的盈亏、交易保证金……进行清算，对应收应付的款项实行净额一次划转」（第二十三条） | 中金所《结算规则》2026-04-10 | **A** | 全文抓取逐字 |
| F2 | 「保证金分为结算准备金和交易保证金。结算准备金是指未被合约占用的保证金；交易保证金是指已被合约占用的保证金」（第十五条/第十六条） | 中金所《结算规则》2026-04-10 | **A** | 全文抓取逐字 |
| F3 | 「结算准备金余额……小于规定的最低余额，不得开仓；若结算准备金余额小于零，交易所可以按照规定对其采取强行平仓等风险控制措施」（第二十四条）；最低余额 200 万元（第三十六条） | 中金所《结算规则》2026-04-10 | **A** | 全文抓取逐字 |
| F4 | 「期货合约到期时，买卖双方应当通过实物交割或者现金交割，了结到期未平仓合约」（第二十七条） | 中金所《结算规则》2026-04-10 | **A** | 全文抓取逐字 |
| F5 | 「当日无负债结算制度（又称逐日盯市）……按当日结算价结算所有合约的盈亏、交易保证金及手续费……净额一次划转」（第三十六条） | 上期所《结算管理办法》2024-09-03 | **A** | 全文抓取逐字 |
| F6 | 「保证金分为结算准备金和交易保证金」（第九条）；「结算准备金余额低于……最低余额的，应当追加保证金或者自行平仓」（第十八条） | 上期所《结算规则》2026-06-12 | **A** | 全文抓取逐字 |
| F7 | 合约乘数「每点人民币 300 元」；「合约价值为股指期货指数点乘以合约乘数」（第五条）；「最低交易保证金标准为合约价值的 8%」（第十八条）；最后交易日 = 到期月第三个周五（第九条） | 中金所《上证50股指期货合约交易细则》2018-12-28 | **A** | 全文抓取逐字 |
| F8 | 「当日结算价为合约最后一小时成交价格按照成交量的加权平均价」（第十二条）；当日盈亏公式含期末乘数（第十三条） | 中金所《上证50股指期货合约交易细则》 | **A** | 全文抓取逐字 |
| F9 | 「合约价值 = 合约价格 ×（合约面值/100 元）」；最低保证金 2%，「自交割月份之前的两个交易日结算时起……3%」（第十七/十八条） | 中金所《10年期国债期货合约交易细则》2020-06-12 | **A** | 全文抓取逐字 |
| F10 | 「强行平仓……价格通过市场交易形成……无法在规定时限内完成全部强行平仓的，剩余持仓顺延至下一交易日」 | 上期所投教「风控」页 | **B（官方投教页，非规则条文——复审 R4 降级）** | 全文抓取逐字 |
| F11 | 展期 = 「对现有头寸平仓，同时建立下个月份头寸」；移仓需先平近月再开远月 | CME Group 投教 / 大商所套利问答（SP 展期指令） | **B** | 二手说明/品种业务问答，非结算规则条文 |
| F12 | 交易所规则中**无「换月」定义**（仅有到期交割与交割月保证金上调） | 对 F1-F9 全文的检索结果 | **B（负结果）** | 检索未见 → 只能证明"未见"，不能证明"不存在" |

> 证据不足项：**F13（未取到）**「交易保证金 = 合约价值 × 保证金比例」的结算规则**逐字**表述；目前只能由 F7/F9 的「最低交易保证金标准为合约价值的 X%」+ F1「交易保证金参与清算」合成（B 级合成，不作 A 级断言）。
> **不得引用清单**：搜索摘要中的「20×杠杆」「保证金 12%」等无版本号片段；任何未标注生效日期的交易所页面；论坛/自媒体对强平线的解释（C 级，仅可用于提出假设）。

### 4.4 E2 探针（已补跑，2026-11-20，用户授权）

**环境**：Python 3.13.5 / pandas 2.2.3。脚本 [p050_e2_probe.py](file:///C:/Users/Peng/AppData/Local/Temp/p050_e2_probe.py) 置于 `%TEMP%`（只读、不改仓库）；`sys.path` 指工作区，`logging.disable(CRITICAL)`。命令：`python %TEMP%\p050_e2_probe.py`。

**原始读数（全部场景，未筛选）**

| 场景 | 输入 | 实测 |
|------|------|------|
| A 开空 | `SELL_SHORT 100@10`，初始 100,000 | cash=100000、NAV=100000、qty=−100、avg_cost=10、**mv=0、upnl=0、exposure=0**；`get_all_positions()={}`；weights={}；validate=`["X持仓数量为负: -100"]` |
| A 盯市 | 8 元、12 元各一次 | 两次均 cash=100000、NAV=100000、mv=0、upnl=0 |
| A 快照 | 8 元日 `to_dict()` | position_count=0、positions={}、daily_return=0 |
| B 越量卖出 | 买 100@10 后 `SELL 150@11` | cash=100650、qty=**−50**、avg_cost=**10**（未重置）、realized=**150**（按 150 股计）、mv=0 |
| B 越量后盯市 | 11 元 | NAV=100650 不变，qty=−50 仍不盯市 |
| C 越量回补 | 空 100@10 后 `BUY_TO_COVER 150@9` | cash=**100000**（未付款）、qty=**+50**、avg_cost=10、realized=100 |
| D 正常平仓 | 买 100@10 后卖 100@12 | cash=100200、qty=0、avg_cost=0、realized=200 |
| E 空头加空 | 空 100@10 再空 100@8 | qty=−200、avg_cost=**9.0**、realized=0 |
| F 风险配置 | `MarkToMarketPolicy()` 默认构造 | `margin_config` 类型 = `MarginConfig` |

**对 DESIGN 的硬约束（E2 级）**
1. 空头 `market_value` / `unrealized_pnl` / `exposure` 在现状下**恒 0**（不是"取绝对值后虚增"——`update_market_values` 的 `>0` 过滤根本没让它跑到 `abs`）。`exposure`（L58-60）是 `market_value` 的代数别名，未盯市的多头也为 0 → P-050 必须改公式本体，不能只放开过滤条件。
2. `Position.execute_trade` 对**双向越量均无守卫**：`SELL` 越量 → 负数量 + 均价不重置 + realized 按超量计；`BUY_TO_COVER` 越量 → 静默翻多。故 U-P050-7 不能只靠"先平后开"的订单拆分，tracker 层需要 fail-fast。
3. 空头加权均价公式（场景 E）**正确**，可直接复用，无需重写。
4. `MarginConfig` 默认构造确实会创建对象，但生产路径不实例化（E3）→ U-P050-6 的"兜底容器"结论成立。

**降级链闭合**：首轮因工作区未信任按 F3 降级为 E3+E4；本次经用户明确授权补跑 E2，历史降级已撤销，原"未取证 2 项"（反手是否抛异常、`MarginConfig` 是否实例化）均由实测回答（①无异常、静默；②默认构造创建、生产无调用点）。

---

## 5. 方案矩阵（全部为待裁决，非预填）

### 5.1 账目模型（U-P050-1）

| 方案 | NAV 定义 | 优点 | 缺点 | 对既有 golden 的影响 |
|------|----------|------|------|----------------------|
| A1 单账 | `cash` 即权益，`margin_used` 仅备忘 | 改动最小 | 无法区分"可用 vs 占用"，强平条件不可判 | 零 |
| A2 双账 | `cash`=可用结算准备金，`margin` 单列 | 强平条件 = `cash < 0`，与 F3/F6 同构 | 多头股票下 `margin=0`，须保证快照/权重不回归 | 需回归验证 |
| **A3 三账**（§10.1 补充调研后推荐 **A3′**） | `NAV = cash_available + margin_locked + Σ mtm` | 与 F2/F6 同构；股票退化为 `margin=0, mtm=market_value`，天然兼容 | 需改 `get_total_value` / I1 / 快照 | 需 golden 零重录验证 |

> A3′ 的落地要点：把 `Position.market_value` 定义为**持仓权益**（股票=市值；期货=保证金+逐日MTM），`cash` 定义为**可用资金**。这样 `get_total_value() = cash + Σ market_value` 公式不变，股票零保证金时与现状逐位一致。**关键新证据**：golden 只断言 `portfolio_value` 序列与 metrics，不读 `cash`/`positions`（`tests/_golden_cases.py` L198-217）→ 内部账目重构不触碰 golden 结构（详见 §10.1 U-P050-1）。

### 5.2 逐日结算（U-P050-2）

| 方案 | 语义 | 与规则一致性 |
|------|------|--------------|
| B1 收盘按结算价结算，盈亏入 `cash`，重置持仓结算基准 | 与 F1/F5 逐字一致 | **A** |
| B2 仅更新 `unrealized_pnl` 字段 | 现状 | 与 F5「净额划转」不符 |

结论（可作结论，因有 A 级证据）：**必须 B1**；B2 只能作为"股票模式"的既有行为保留。

### 5.3 强平（U-P050-3）

| 方案 | 触发 | 价格 | 备注 |
|------|------|------|------|
| C1 | 结算后 `cash_available < 0` | 次一交易日开盘价（或结算价） | 与 F3 第二十四条「小于零 → 强行平仓」逐字同构；可实现、可 golden |
| C2 | 风险度 `margin_locked / NAV` 超过维持线 | 同上 | 预警口径，比 C1 更早 |
| C3 | bar 内 low/high 触发 | bar 内价 | 需分钟数据，超出现有日频数据契约 |

推荐供裁决：**C1 为强平动作 + C2 为诊断信号**，C3 明确不做（数据契约不支持，且属 P-056 实时域）。

### 5.4 换月（U-P050-4）

| 方案 | 触发 | 依赖 |
|------|------|------|
| D1 到期前 N 日自动 roll | `expiry - N` | 需合约元数据（乘数/到期/保证金率） |
| D2 显式 roll 指令（策略/配置层） | 人工指定 | 无 |
| D3 不自动 roll，仅到期校验 + 报警 | `expiry` | 无 |

题干「换月优先」→ 推荐供裁决：**D1 为主 + D3 兜底（无远月元数据时拒绝而非静默持有到期）**；D2 作为研究模式。

**补充调研后的硬约束（§10.1 U-P050-4）**：持仓**不得进入交割月**；依据为 F9（国债期货交割月前两个交易日保证金 2%→3%）、F13（螺纹钢交割月前第一月最后交易日收盘前须调为 30 手整倍数）、F14（镍临近交割月额度窗口截止于交割月前第一月最后交易日）。`roll_days_before_expiry` 仅作为品种级参数，不把"提前 N 日"写成事实断言（F12 负结果）。

### 5.5 股票负持仓（U-P050-5，D3 已定范围，仅剩开关形态）

推荐供裁决：`allow_negative_stock_positions: bool = False`（默认关）；开启后**不计保证金、不计融券费**，仅支持 `NAV = cash + Σ signed qty×price`，并在报告标注「研究模式」。关闭时四条账目路径必须与 `c6f172d` **逐位一致**。

### 5.6 乘数与成本（U-P050-6）

| 方案 | 载体 |
|------|------|
| M1 | `Trade` 增加 `multiplier`（默认 1.0）/ `asset_type`（默认 `STOCK`） |
| M2 | 全局 `BacktestConfig.asset_type` + 合约表 |

推荐供裁决：**M1**（逐笔可追溯、对既有调用零影响，默认值保证 golden 零重录）。

---

## 6. 任务拆分（T1-T9，Step 3 细化为 IMPL；T9 由 §10.5 审计新增）

| 任务 | 内容 | 回退点 |
|------|------|--------|
| T1 | `Trade` / `Position` 增 `multiplier` / `asset_type` / `settlement_price` / `notional_value`，全部带默认值 | R1：加字段后全量 golden 必须零重录 |
| T2 | 三账落地：`cash_available` / `margin_locked` / `mtm`；`get_total_value` 重定义 | R2：股票多头 golden 零重录 |
| T3 | `settle()`：按结算价结算盈亏、重算保证金、更新持仓基准 | — |
| T4 | 强平：`_force_liquidation` 支持双向 + C1 触发 | R3：空头穿仓 golden |
| T5 | 换月：合约元数据 + `roll` 路径 | — |
| T6 | 成本：乘数、平今/平昨、按手佣金 | — |
| T7 | 不变量：I1' 三账恒等；新增 I5（结算恒等）、I6（乘数恒等） | — |
| T8 | synthetic golden（多/空/强平/换月）+ 文档（DESIGN/IMPL/CHANGELOG/PROGRESS） | — |
| T9 | 契约兼容层：`settle` 可选能力探测 + `AbstractPositionTracker` 非抽象 no-op + `__api_version__` 升 minor；V3 对期货/负持仓显式 raise（§10.5 N-2/N-8） | R4：注入式 Mock tracker 测试全绿 |

---

## 7. 不变式（Step 7 实现口径）

| ID | 断言 | 现状 |
|----|------|------|
| I-P050-1 | `NAV_t = cash_available + margin_locked + Σ mtm`（股票：`margin=0`，`mtm=market_value`） | 与 I1 冲突（G-12） |
| I-P050-2 | `cash_t = cash_{t-1} + Σ 当日盈亏 − 费用`（净额一次划转） | 不存在（G-03） |
| I-P050-3 | `margin = Σ abs(qty) × settle × multiplier × margin_ratio` | 不存在（G-01/G-02） |
| I-P050-4 | 多空对称：`q → −q` 时 NAV 恒等号保持（费用除外） | 不成立（G-04/G-05） |
| I-P050-5 | 强平单调：`cash_available < 0` 的次一交易日收盘后该合约持仓 = 0 | 不成立（G-08） |
| I-P050-6 | 换月守恒：`roll` 前后 `qty × multiplier` 风险敞口相等（允许价差成本） | 不存在（G-09） |
| I-P050-7 | 未启用期货/负持仓时，全部输出与 `c6f172d` **逐位一致** | 待验证 |
| I-P050-8 | V3 + 期货/负持仓组合必须**显式抛错** | 不成立（G-13） |
| I-P050-9 | `execute_trade` 双向越量（含回补越量）必须 raise，禁止静默跨零 | 不成立（G-15，E2 实测静默） |
| I-P050-10 | `exposure = abs(qty) × price × multiplier`（未盯市时也非 0） | 不成立（G-16，E2 实测恒 0） |

---

## 8. DoD（可机械验收）

| # | 验收项 | 判定 |
|---|--------|------|
| A1 | 期货 synthetic golden ≥ 4 例：多头盈亏、空头盈亏、逐日结算、强平 | 文件 + 测试函数 |
| A2 | 既有 12 个 golden **零重录**（12/12 通过，diff 为空） | `git diff tests/golden/` = 空 |
| A3 | 乘数恒等：`amount == qty × price × multiplier` | 单测 |
| A4 | 结算恒等：`cash_t − cash_{t-1} == ΣPnL − fee`（闭式手算） | 单测 |
| A5 | 强平后持仓为 0 且 `cash_available >= 0`（或标记穿仓） | 单测 |
| A6 | 股票负持仓默认关闭；开启路径有独立测试 | 单测 |
| A7 | V3 + 期货/负持仓抛错 | 单测 |
| A8 | 门禁：pytest ≥ 987 passed / golden 18 / mypy 0 / black clean | CI |
| A9 | 文档同步：DESIGN/IMPL/CHANGELOG/PROGRESS + 台账 | 文件 diff |
| A10 | 回退点 R1/R2/R3 均通过 | 提交记录 |

---

## 9. 基线读数与目标（E5 标注）

| 指标 | `c6f172d` 读数 | 来源 | 本步状态 |
|------|----------------|------|----------|
| pytest | 987 passed | P-046a 关闭读数（继承） | **未重跑**（E5，不作结论依据） |
| golden | 18（12 文件 + 6 元测试） | PROGRESS §3.52 差分 + 文件盘点（E4） | 已机械分解 |
| mypy | 111 files, 0 error | 继承 | 未重跑 |
| black | `152·221`（沿用 PROGRESS 记法） | 继承 | 未重跑 |
| `tests/*.py` | 109 | 继承 | 未重跑 |

目标：A2 成立前提下 `passed ≥ 987 + 新增用例数`，golden 18 → 18+新例，mypy/black 不劣化。

---

## 10. 待裁决（Step 2 前必须收敛）

### 10.0 裁决记录（2026-11-20，用户确认）

- **U-P050-1..7**：全部按 §10.1 推荐落定（A3′ / 引擎内 `settle`+收盘价代理 / C1+次日开盘 / D1+交割月硬约束 / `allow_negative_stock_positions=False` / `get_asset_info` 优先+`MarginConfig` 兜底 / 先平后开两笔）。
- **N-1**：采纳「`Position` 增 `notional_value` + `risk_manager` 保证金分支重定义」；复审 R3 补充：L165 比较方向（`<` 触发 FORCE_CLOSE）与阈值语义须在 DESIGN 一并重推导，不得沿用死代码方向。
- **N-2**：同意 `__api_version__` 升 minor（3.1.0 → 3.2.0）。
- **N-5**：同意单一全局默认 `roll_days_before_expiry` + `AssetInfo` 逐合约可选覆盖，不内置品种表。

| ID | 问题 | 候选 | 推荐（依据 §10.1） | 影响面 |
|----|------|------|--------------------|--------|
| U-P050-1 | 账目模型 A1/A2/A3 | A3 | **A3′**（三账，`market_value` 改为"持仓权益"；须同步 `risk_manager` 口径，见 §10.5 N-1） | `get_total_value` / I1 / 快照 / `compute_portfolio_value` / `risk_manager` |
| U-P050-2 | 逐日结算入口与结算价来源 | 引擎内 / tracker 自管 | **引擎内 `tracker.settle()`，收盘价代理**（+ 可选 `settlement_file`） | V2 主循环 L540-557 |
| U-P050-3 | 强平触发时点与价格 | C1/C2/C3 | **C1 触发 + 次日开盘成交**（期末保留当日收盘） | golden 判定值 |
| U-P050-4 | 换月自动化程度 | D1/D2/D3 | **D1 + 硬约束"不进入交割月" + 缺元数据抛错**；roll 窗口用全局默认 + `AssetInfo` 逐合约覆盖，**不内置品种表**（§10.5 N-5） | 合约元数据依赖 |
| U-P050-5 | 股票负持仓开关 | 开关形态 | `BacktestConfig.allow_negative_stock_positions=False` | 6 个闸门 |
| U-P050-6 | 保证金率来源 | 静态/元数据/阶段表 | **`IDataManager.get_asset_info` 优先 + `MarginConfig` 兜底 + `expiry` 派生上调** | 配置结构 |
| U-P050-7 | 反手语义 | 先平后开 / 单笔反手 | **先平后开两笔** | 成交笔数/成本/现金中间态 |

### 10.1 补充调研：每项裁决的机械判据（2026-11-20）

#### U-P050-1 账目模型 → A3′

**新证据（E3）**
- golden 断言面只有 `portfolio_value` 序列（`length/first/last/min/max`）与 metrics、`trades.count`（`tests/_golden_cases.py` L198-217、L209-217），**完全不读 `cash` / `positions`** → 账目内部重构不影响 golden 的结构，只需 NAV 序列不变。
- `BacktestConfig.risk_overlay`（`config.py` L421-422）证明"新增可选字段 + 默认关闭 = 零行为变更"是仓内既有范式，可直接复用。
- `compute_portfolio_value`（`target_positions.py` L148-188）用 `cash + Σ qty×price`，且 **L174 `if qty <= 0: continue`** 直接跳过空头；`engine_v2.py` L1175-1186 传入的 `current_positions` 也先过滤 `>0` → 期货/空头调仓估值会系统性漏掉空头腿。

**推荐形态 A3′**
- `cash` = **可用资金**；`Position.market_value` = **持仓权益**：股票 `qty×price`，期货 `margin_locked + 逐日MTM`；`margin_used` = 已占用保证金（备忘+风控）。
- 于是 `get_total_value() = cash + Σ market_value`（`tracker.py` L290-297）**公式不变**：股票 `margin=0` 时逐位等价于现状 → A2 零重录可满足；期货 `(cash−margin) + (margin+MTM) = cash+MTM`。

**残余风险**
- `get_cash()` 语义由"总现金"变"可用"，波及 BUY 闸门（`engine_v2.py` L955-968 / L1366-1377）与调仓估值（L1182）；股票不受影响，期货更紧属正确方向，但必须用 golden 零重录 + 期货双向 case 双验。
- `validate_positions` 把 `cash < 0` 记为错误（`tracker.py` L460-462）；期货"可用为负"是待强平的合法中间态 → 需按模式分支，不能直接放宽（否则掩盖股票现金错误）。
- **E2 实测追加**：空头 `mv/upnl/exposure` 恒 0，根因是 `update_market_values` 的 `>0` 过滤先于 `abs` → A3′ **不能只改 `market_value` 公式**，必须同时改过滤与赋值两处；否则期货空头腿（以及回补越量产生的多头）在权益中整体消失。

#### U-P050-2 结算入口与结算价 → 引擎内 + 收盘价代理

**新证据（E3）**
- `ExecutionPriceType` 只有 `OPEN/VWAP/CLOSE/CUSTOM`（`config.py` L19-25）；`_exec_price` 只从数据层取对应 `kind` 的复权价（`engine_v2.py` L505-509）→ **仓内不存在"结算价"字段**，新增真实结算价需扩数据契约。
- `update_market_values` 内部 `_take_snapshot`（`tracker.py` L241-269）用当前 `cash` 生成快照 → **settle 必须早于 L557**，否则当日快照的现金是未结算值。
- 主循环顺序：待执行订单（L541-542）→ 触发判定（L545-549）→ 再平衡（L551-553）→ 收盘盯市/快照（L556-557）→ overlay NAV（L562）→ 风控（L572-578）。

**推荐**
- 在 `_process_trading_day` 内、**L545 触发判定之前**调用 `tracker.settle(date, settlement_prices, specs)`（期货未启用时 no-op）；理由：让触发判定、overlay NAV、快照三者看到同一口径的"已结算 NAV"，避免同一天两套 NAV。
- 结算价优先级：`settlement_file`（可选新增数据键）> 收盘价代理（默认，warning 一次）。golden 用合成数据显式给"结算价"列，可精确控制。
- 子问题 **U-P050-2b**：settle 放在触发前（推荐）还是触发后；若选"触发后"，期货首日的再平衡判定将使用未结算 NAV，需在 DESIGN 明示。

#### U-P050-3 强平 → C1 + 次日开盘

**新证据（E3）**
- `_force_liquidation`（`engine_v2.py` L650-718）：只发 `OrderSide.SELL`（L706-708）、`quantity <= 0` 直接跳过（L692-694）、价格取当日收盘或 `price_override`（L683-704）→ 现成载体可扩展为双向，但价格语义是"当日收盘"。
- `_next_day_orders` 机制（L1303-1311）已提供"次日开盘执行"通道，可直接复用为强平执行。

**推荐**
- 触发：结算后 `cash_available < 0`（对齐 F3 第二十四条）；先预警 `margin_locked/NAV` 超维持线（C2，仅诊断）。
- 执行：**次一交易日开盘价**、`BUY_TO_COVER` 平空 / `SELL` 平多；无价则顺延（对齐 F10「剩余持仓顺延至下一交易日」）。
- 期末（universe 最后一日）无"次日" → 保留 `_force_liquidation` 当日收盘路径，两套入口在 DESIGN 合并为同一函数的不同 price source。

**残余风险**：连续同向停板时无法成交，须记录"未完成强平"状态并在次日重试；golden 需 1 例顺延。

#### U-P050-4 换月 → D1 + 交割月硬约束

**新证据**
- A 级：中金所 10Y 国债「自交割月份之前的两个交易日结算时起」保证金 2%→3%（F9）；IH 最后交易日=到期月第三个周五（F7）；到期须交割了结（F4）。
- B 级：上期所螺纹钢「交割月前第一月的最后一个交易日收盘前」一般持仓须调整为 30 手整倍数（F13）；镍「临近交割月份套保/套利额度申请」窗口截止于交割月前第一月最后一个交易日（F14）。
- 负结果（B）：交易所规则中**无"换月"定义**（F12），"提前 N 日"属行业惯例，不能作事实断言。

**推荐**
- `roll_days_before_expiry` 可配（默认按品种设置），并加**硬约束**：持仓不得进入交割月；到期前未 roll → 抛错而非静默持有到期。
- roll 拆两笔：平近月 + 开远月（与 U-P050-7 同口径），成交价沿用 `execution_price_type`。
- 无远月合约元数据（`AssetInfo.expiry_date` 为空或缺远月）→ 显式拒绝并报错。

**残余风险**：整倍数/额度等品种级规则不在 P-050 实现（避免品种规则引擎），列入 P-056/后续。

#### U-P050-5 股票负持仓开关

**新证据**：需同时贯穿 6 个硬闸门——权重截断（`engine_v2.py` L1093）、权重→目标（`execution_policy.py` L444-451）、目标构建（`target_positions.py` L79-80、L101-111）、持仓可见性（`tracker.py` L288）、盯市范围（L231）、校验（L466-467）。

**推荐**：`BacktestConfig.allow_negative_stock_positions: bool = False`；关闭时全部闸门走早退分支，**不进入任何新代码路径**（bit-identical）。开启后仍不计保证金/融券费（D3），报告与 `snapshot.to_dict` 需标注"研究模式"（当前 L150/L154 只序列化多头，需显式补空头字段）。

**残余风险**：`position_count` 语义（只数多头）会误导；建议新增 `short_position_count` 而非改旧字段。

#### U-P050-6 保证金率与合约元数据来源

**新证据（E3）**
- `IDataManager.get_asset_info(symbol)` 契约已存在（`interfaces.py` L136-143）；`DataManager.configure_assets`（`data.py` L712-718）与 `DataLoaderV3.configure_asset`（`data_v3.py` L233-240）均已实现注入；未知代码回退 `AssetInfo(asset_type=STOCK)`（`data.py` L699-701）。
- `MarginConfig`（`config.py` L488-526）已定义三档比例与校验，但无生产消费点 → 可直接作为缺省值容器。

**推荐**：优先级 `AssetInfo.margin_ratio`（逐合约）> `MarginConfig.initial_margin_ratio`（全局兜底）；分阶段上调用 `expiry` 派生（如 F9 的"交割月前两个交易日"规则），**不内置品种表**；`AssetInfo` 通过显式 `configure_assets` 注入（golden fixture 直接构造），不新增配置文件格式。

**残余风险**：仓内无 AssetInfo 文件加载器 → 实盘/批量场景需在 P-056 补数据源；P-050 仅保证 API 可用。

#### U-P050-7 反手语义 → 先平后开

**新证据（E3）**
- legacy 订单生成（`engine_v2.py` L1287-1295）只发 `SELL`（差额为负时）与 `BUY`，**永不发 `SELL_SHORT`**；次日执行对 `qty <= 0` 直接丢弃，注释写明"避免负持仓（P-014 D2/D6）"（L1379-1383）。
- `OrderIntent.action` 已支持四侧（`execution_policy.py` L88-105）；`T0FuturesPolicy` 已实现（L259-394）但零调用点。
- `build_target_positions` 对负权重 raise（`target_positions.py` L79-80）。

**推荐**：目标由正转负时拆两笔——先 `SELL` 平多、再 `SELL_SHORT` 开空，顺序固定；成本按两笔计（与交易所撮合一致）。拒绝"单笔反手"：`OrderSide` 无此值，且成交记录/费用/保证金释放都必须可分笔审计。

**残余风险**：同日两笔的现金中间态（先平释放资金）会影响 BUY 闸门与强平判定顺序 → golden 必须断言两笔之间的 `cash`。**E2 实测追加**：tracker 层对越量**双向静默**（卖 150/持 100 → −50；回补 150/空 100 → +50），故"先平后开"必须在 tracker 增加 fail-fast，订单拆分只是必要条件、不是充分条件。

### 10.2 裁决对门禁的机械影响

| 裁决 | 触及文件 | 对既有 golden 的影响 | 验证 |
|------|----------|----------------------|------|
| U-P050-1 | `tracker.py` / `target_positions.py` / `engine_v2.py` / `risk_manager.py` | 股票 `margin=0` → NAV 序列不变，**零重录** | 12/12 diff 空 + 期货双向 case + 股票 `margin_used==0` 不变量 |
| U-P050-2 | `engine_v2.py` L540-557 / `tracker.py` | 期货专用，股票 no-op | 期货结算恒等单测 |
| U-P050-3 | `engine_v2.py` L650-718 / `execution.py` 价格解析 | 期货专用 | 强平 golden + 顺延 case + `execution_price_type` 三档对照 |
| U-P050-4 | `tracker.py` / 元数据注入 | 期货专用 | roll 守恒单测 |
| U-P050-5 | 6 个闸门 | 默认关闭 → 零影响 | 开/关对照测试 |
| U-P050-6 | `config.py` / `data*.py` 消费侧 | 无（只读元数据） | 缺元数据抛错测试 |
| U-P050-7 | `engine_v2.py` L1287-1295 / `tracker.py` L86-116 | 期货/空头专用 | 两笔现金中间态断言 + 越量 fail-fast 单测（E2 实测为静默） |

### 10.3 建议裁决顺序

`U-P050-1 → 6 → 2 → 7 → 3 → 5 → 4`（账目定义决定其余全部；元数据决定结算与换月可行性；反手语义决定成交量与现金顺序；强平依赖结算；股票开关倒数第二，因其与 D3 已定且可独立早退；换月最后，因其依赖元数据来源（6）与反手/强平顺序（7/3）——复审 R6 勘误）。

### 10.4 若推荐被推翻

- 选 A1/A2：`settle` 与 `get_total_value` 的改动面收窄，但"可用 vs 占用"不可判 → C1 强平条件需换定义，且 F3 对齐度下降。
- 选 C3（盘中强平）：需分钟级数据契约，超出当前 `IDataManager` 批量日频能力 → 直接阻塞，不可在本批实现。
- 选 D2（仅手动 roll）：题干"换月优先"无法验收，建议至少保留 D1 的配置与 golden。

### 10.5 三原则符合性审计（可兼容 / 可升级 / 易插拔，2026-11-20）

**审计口径**（按仓内既有约定定义，非外部理论）：
- **可兼容**：期货/负持仓未启用时行为逐位不变；不破坏既有注入式组件契约（`core/interfaces.py` 的 `Protocol` 与 `Abstract*` 基类）。
- **可升级**：新能力以"可选字段 + 默认关闭"或元数据驱动扩展，不内置品种/交易所规则表。
- **易插拔**：能力走既有插槽（`IDataManager` / `IExecutionSimulator` / `ExecutionPolicy` / `CostConfig` / 构造注入），不新增并行旁路。

**符合项（5 条）**

| # | 判据 |
|---|------|
| C-1 | 默认关闭范式有仓内先例：`BacktestConfig.risk_overlay: "RiskOverlayConfig \| None" = None`（`config.py` L421-422） |
| C-2 | 元数据插槽现成：`IDataManager.get_asset_info`（`interfaces.py` L136-145）+ `DataManager.configure_assets`（`data.py` L712-718）→ U-P050-6 属"接线"而非"改契约" |
| C-3 | 成本插槽现成：`CostConfig.asset_costs` / `get_asset_cost`（`config.py` L194-203），且 `_calculate_cost(..., asset_type=AssetType.STOCK)` 已有向后兼容默认值（`execution.py` L367-382）→ 期货费率只需在调用处传参（`execution.py` L330、`engine_v2.py` L1256） |
| C-4 | A3′ **不改** `get_total_value` 公式（`tracker.py` L290-297）→ I1、报告、overlay、golden 的 NAV 读取路径零改动 |
| C-5 | 强平执行通道复用 `_next_day_orders`（`engine_v2.py` L1303-1311），不新建队列 |

**不符合项 / 需修正（N-1..N-9）**

| ID | 违反原则 | 事实（E3） | 修正（不改变裁决本身） |
|----|----------|------------|------------------------|
| N-1 | 可兼容 | A3′ 下 `market_value` = 保证金 + MTM，而 `MarkToMarketPolicy.check_position` 用 `margin_used / market_value` 作保证金率（`risk_manager.py` L162-163）→ 口径由"保证金/名义"变成"保证金/权益"；§10.2 影响面原表漏列该文件 | `Position` 增 `notional_value`（期货 = 数量×价格×乘数），`risk_manager` 改用 `margin_used / notional_value`；§10.2 已补。**复审 R3**：L165 比较方向（`margin_ratio < force_liquidation_ratio` → FORCE_CLOSE）在两种分母下语义均不自洽（风险度应大者触发；保证金比例低不应强平），DESIGN 须重定义方向与阈值——该分支现为死代码，属重定义非兼容 |
| N-2 | 易插拔 | `IPositionTracker` 无 `settle`（`interfaces.py` L324-360）；引擎无条件调用会打断任何注入 tracker（含测试 Mock），且 `AbstractPositionTracker`（L538-549）只有 2 个抽象方法 | 引擎用 `getattr(tracker, "settle", None)` 探测（仓内范式：`pipeline.set_error_sink` 探测）；`AbstractPositionTracker` 加**非抽象** no-op；`__api_version__` 由 `3.1.0` 升 minor |
| N-3 | 可升级 | "`settlement_file` 新数据键"绕过 `get_adj_price` 契约（`interfaces.py` L107-119），其他 `IDataManager` 实现不会提供 → 隐性耦合 | 结算价改为**可选能力**（`get_settlement_prices()` 或注入 provider），缺省回退收盘价且只 warning 一次 |
| N-4 | 易插拔 | `_force_liquidation` 直接用当日 close / `price_override`（`engine_v2.py` L683-704），绕过 `IExecutionSimulator` 的 `execution_price_type` 解析（`execution.py` L219-271）→ 强平不可配 VWAP/CUSTOM | 强平单走正常执行管线；期末"当日收盘"用 `price_override` 表达 |
| N-5 | 可升级（内部矛盾） | U-P050-4 原文"默认按品种设置"隐含内置品种表，与 U-P050-6"不内置品种表"直接冲突 | 单一全局默认 `roll_days_before_expiry` + `AssetInfo` 逐合约可选覆盖；交割月约束只由 `expiry_date` 判定 |
| N-6 | 可升级/可维护 | U-P050-5 的同一布尔散落 6 个闸门（权重截断、from_weights、build_target_positions、get_all_positions、盯市、validate），新增同类闸门极易漏 | 收敛为单一判定入口（`tracker.allows_short()` 或 `SidePolicy`），6 处只调用它；`build_target_positions` 默认 raise 语义不变 |
| N-7 | 易插拔 | 若把"两笔反手"写进 legacy `_generate_rebalance_orders`（`engine_v2.py` L1274-1301），等于加厚旧双轨路径，与"注入 policy 优先"方向相反；同时 `T0FuturesPolicy` 仍零调用点（G-14） | 拆单下沉到意图层（`SignalTranslator` / 新增 `ReversalRule`）；期货执行优先接 `T0FuturesPolicy`（注入通道已存在，`engine_v2.py` L1209-1212） |
| N-8 | 可兼容 | `engine_v3_vector` 自陈无保证金/盯市（L18-24）；期货配置交给 V3 会**静默错算**而非报错 | V3 在 setup 对 futures / `allow_negative_stock_positions=True` 显式 raise（新增拒绝，不改变既有股票行为） |
| N-9 | 可兼容（语义漂移） | A3′ 使 `get_cash()` 语义从"账面现金"变"可用资金"；股票 `margin=0` 时数值相同，但外部报告/监控的含义变了 | 新增 `get_available_cash()` / `get_total_cash()`；`get_cash()` 保留并显式文档化。golden 不读 cash，故不影响零重录 |

**结论**：7 项推荐**方向全部成立**，但 N-1 / N-2 / N-4 属硬伤（会在 Step 4 直接造成口径错误或破坏注入契约），N-5 / N-6 / N-7 属内部不一致，N-3 / N-8 / N-9 属扩展方式不够"插拔"。修正只改落地细节与影响面清单，**不改变 U-P050-1..7 的裁决结论**；须在写 SPEC 前把 N-1..N-9 落成独立任务项（建议并入 T1/T3/T4/T7，并新增 T9「V3 显式拒绝」）。

---

## 11. 与既有批次的边界

| 批次 | 边界 |
|------|------|
| P-045 止损 | 止损作用于**权重/信号**层，不涉及现金；P-050 不修改 `core/stops.py` |
| P-047 Sizing | `apply_sizing` 的 `total_weight ≤ 1` 是**多头**约束；P-050 不修改其语义，期货敞口另立约束 |
| P-048 Risk Overlay | overlay 输出目标权重；P-050 只改账目，不改 overlay |
| P-058 截面多空 | 依赖 P-050 的负持仓/保证金；P-050 不实现策略模板 |
| P-056 CTP | 实盘网关，依赖 P-050 账目；P-050 不实现任何柜台适配 |
| U-P031-2/3 | 已在 P-047 关闭（BUY 现金夹紧）；short 语义由本批承接 |

---

## 12. 十步路线（本批，编号对齐权威源 `SPEC_PROCESS.md` v1.7.2）

> **订正（2026-11-20）**：原表把"Step 2 = 写 `SPEC_p050.md`"列为独立产物，与权威源不符——权威源 Step 2 = **Review 形成调研文档**（产物即本文 RESEARCH），Step 3 = 设计文档；且仓内 `docs/` 有 44 个 `DESIGN_*`、**0 个 `SPEC_p0xx`**，无 SPEC 独立文件先例（`SPEC_STANDARD.md` 的 Phase 0/1 亦只定义 RESEARCH/DESIGN）。故删除"SPEC 独立文件"一环，改为下表的权威映射。

| Step | 产出（本仓落地物） | 门禁 |
|------|--------------------|------|
| 1 | 调研取证（E1-E5）：本文 §2-§4 | 证据分级 + 行号绑定 |
| 2 | **本文**（RESEARCH + 异构 Review §14.1） | 复审通过 + 裁决收敛（均已满足，2026-11-20） |
| 3 | `DESIGN_p050.md`（三账模型、接口签名、R3 判据重定义） | 用户对 DESIGN 确认 |
| 4 | DESIGN Review（异构自检） | 无未验证假设 |
| 5 | `IMPL_p050.md`（实施文档：T1-T9 细化 + 依赖/兼容性） | 接口签名可实现 |
| 6 | IMPL Review | 与 DESIGN 逐条对齐 |
| 7 | `CHECKLIST_p050.md` | 每项可测、有明确通过条件 |
| 8 | 文档一致性 Review（RESEARCH↔DESIGN↔IMPL↔CHECKLIST） | 四文档对齐 |
| 9 | TDD 实现（T1-T9）+ 全量门禁 | 红→绿两读数；≥987 passed（Step 3 重新基线化——复审 R7）/ 12 golden 零重录 |
| 10 | 验收 + 收口（PROGRESS/CHANGELOG/提交） | CI 四 job |

> 若用户仍需要一份独立的"需求规格"文件（区别于 RESEARCH/DESIGN），需显式裁决——该形态在本仓无先例，且会新增一个无模板、无门禁的文档类型。

---

## 13. 外部证据登记

| 编号 | 标题 | 版本/日期 | URL | 等级 |
|------|------|-----------|-----|------|
| F1-F4 | 中国金融期货交易所结算规则 | 2026-04-10 | http://www.cffex.com/cn/gzjygz/20260410/47570.html | A |
| F5 | 上海期货交易所结算管理办法 | 2024-09-03 | https://www.shfe.com.cn/regulation/exchangerules/historicalversion/202409/t20240903_802236.html | A |
| F6 | 上海期货交易所结算规则 | 2026-06-12 | https://www.shfe.com.cn/regulation/exchangerules/rules/202606/t20260603_831935.html | A |
| F7-F8 | 中金所上证50股指期货合约交易细则 | 2018-12-28（2019-01-02 实施） | http://www.cffex.com.cn/cn/ssxz/20181228/43094.html | A |
| F9 | 中金所10年期国债期货合约交易细则 | 2020-06-12（2020-07-20 实施） | http://www.cffex.com.cn/cn/ssxz/20200612/43096.html | A |
| F10 | 上期所投教「风控」 | 抓取日 2026-11-20 | https://www.shfe.com.cn/specialtopic/investor/risk_control/ | B（复审 R4 降级：投教页非规则条文） |
| F11 | CME「到期与展期」/ 大商所套利问答 | 抓取日 2026-11-20 | https://www.cmegroup.com/cn-s/education/courses/introduction-to-futures/understanding-futures-expiration-contract-roll.html ; http://www.dce.com.cn/dalianshangpin/ywfw/ywzy/jyywzy/498201/1500377/index.html | B |
| F12 | 交易所规则「换月」负结果 | 检索日 2026-11-20 | F1-F9 全文检索未见 | B（负结果） |
| F13 | 上期所螺纹钢期货业务细则（交割月前第一月最后交易日收盘前，一般持仓须调为 30 手整倍数） | 2025-12-31 | https://www.shfe.com.cn/regulation/exchangerules/productrules/202512/t20251231_829962.html | B（官方页检索片段，未抓全文） |
| F14 | 上期所镍期货业务细则（临近交割月套保/套利额度申请窗口截止于交割月前第一月最后交易日） | 2026-03-27 | https://www.shfe.com.cn/regulation/exchangerules/productrules/202603/t20260327_830916.html | B（官方页检索片段，未抓全文） |
| F15 | 本仓 E2 探针（9 场景：空头/盯市/越量/回补/加空/风险配置） | 2026-11-20 | 本地 `python %TEMP%\p050_e2_probe.py`（原始输出见 §4.4） | **E2**（运行取证；环境 Python 3.13.5 / pandas 2.2.3） |

### 13.1 检索覆盖度自评

- 查询轮次：**4 轮**（保证金/结算、强平、换月、移仓时点与交割月约束），抓取 **5 个规则页全文**（中金所结算规则 / 上期所结算办法 / 上期所结算规则 / 中金所两份合约细则）+ **1 个官方投教页**（F10，复审 R5 勘误计数）+ 2 条品种细则检索片段（F13/F14）。
- 覆盖：中金所结算规则、上期所结算规则/办法、两个合约细则、上期所投教、上期所两个品种业务细则（片段）。
- **未覆盖**：证监会《期货交易管理条例》原文（未抓取，不作引用）、各品种保证金率现行表（会随市场调整，不入 golden 常量）、交割细则、品种持仓限额/整倍数规则全文。
- 结论可用性：F1-F9 可支撑"逐日结算/三账/强平条件/乘数与合约价值"的**机制性**结论；F10（投教页，B）仅支撑"强平顺延"的方向性描述；F13/F14 仅作为"交割月前必须调整持仓"的**方向性**佐证（B 级，不单独作结论）；**具体保证金率与提前天数不得写死**，只能作为 golden 的**假设输入**并显式标注。

---

## 14. 本步自检

- [x] 题干逐字回引（L267/L325/L273/L275）
- [x] 代码事实全部带行号 + 基线 commit
- [x] 外部证据分级，A 级均规则原文全文逐字（复审 R4 将 F10 投教页降为 B）；B 级（F11-F14）不单独作结论
- [x] 期望值闭式手算（§4.2），无录制、无拟合
- [x] 统计可溯源（golden 18 = 12 + 6，给出差分来源）
- [x] 零预填：所有方案均标"推荐供裁决"，未代替用户拍板
- [x] E2 已补跑（2026-11-20，用户授权）：9 个场景实测入档，原 2 项未取证已闭合，并订正 G-15、新增 G-16
- [x] 待裁决 7 项均有 §10.1 机械判据 + 推荐 + 残余风险 + 推翻预案
- [x] 补充调研新增证据全部带行号/来源等级（golden 断言面、`compute_portfolio_value`、`_generate_rebalance_orders`、`get_asset_info` 通道）
- [x] 异构复审（GLM-5.3-Flash，2026-11-20）——**通过**（发现 R1-R7，全部处置，见 §14.1）

### 14.1 异构复审记录（复审方 GLM-5.3-Flash，2026-11-20）

**复审方式**：复审方独立重读承重锚点与重算推导，不信任作者转述。

**抽查一致（无幻觉）**
- 代码锚点（14 处）：`tracker.py` L62-71（`abs`/盯市公式）、L73-116（四侧分支；**开空不赋 `market_value`**）、L118-130、L144-156、L282-288、L290-297、L299-305；`execution.py` L327/L330/L332-335、L367-382（`asset_type` 默认 STOCK）；`config.py` L151-166（`AssetInfo`）/L179-203（`asset_costs`）/L488-527（`MarginConfig`）；`risk_manager.py` L162-188；`invariants.py` L26-27（`_BUY_SIDES`/`_SELL_SIDES` 与 §2.6 逐字一致）；`interfaces.py`（`IPositionTracker` 确无 `settle`、`AbstractPositionTracker` 两抽象方法）；`engine_v3_vector.py` L18-24；`core/__init__.py` L14（`__api_version__="3.1.0"`）；`multiplier` 全仓 grep = 声明/文档串 3 处、**零消费点**（与 §2.5 一致）。
- 闭式推导重算：推导 1 场景 1/2、推导 2（1/300 缩小、30× 杠杆）、推导 3（+6,000 / −21,000 / 累计 −15,000 / 保证金 104,400 / 106,500）全部一致。
- 内部一致性：§0 ↔ G-01/G-03/G-04；§5.1 A3′ ↔ §7 I-P050-1 ↔ §10.1 U-P050-1 口径互恰；golden 计数 12 = 7+2+3 算术正确。

**未复核项（转 Step 9 独立复审覆盖）**：`engine_v2.py` 长文件锚点（L955-968 / L1093 / L1287-1295 / L1366-1383）仅由作者 E3 给出，复审未逐一重读；测试文件断言内容（§2.5 已声明未读）。

**发现与处置**

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| R1 | 通过 | 上述承重锚点与推导复核一致，未发现幻觉 | 无需修改 |
| R2 | minor | §4.2 场景 3 的 `+2qP` 隐含"盯市已放开"前提；字面"只补现金"读法下误差为 `q·P`（开空不赋 `market_value`） | 已在 §4.2 注明前提 |
| R3 | **major** | `risk_manager.py` L165 比较方向（`margin_ratio < force_liquidation_ratio` → FORCE_CLOSE）在"保证金/名义"与"保证金/权益"两种分母下语义均不自洽（风险度应大者触发；保证金比例低不应强平）——N-1 只换分母不够 | 已并入裁决 N-1：DESIGN 须重定义方向与阈值；现为死代码，属重定义非兼容 |
| R4 | minor | F10 为官方投教页非规则条文，按本文 A 级标准（规则原文全文逐字）应降 B | §4.3 / §13 / §13.1 / §14 已改 |
| R5 | minor | §13.1 "4 个交易所页面全文" 与 §13 登记页数不符（实为 5 规则页 + 1 投教页 + 2 片段） | 已改 |
| R6 | minor | §10.3 "股票开关最后" 与顺序 `…5 → 4` 矛盾 | 已改（换月最后并补理由） |
| R7 | minor | §12 Step 8 "≥987 passed" 未给来源 | 已加注：Step 2 重新基线化 |

**复审结论**：事实层**通过**；R3 为唯一 major，属设计层遗留而非事实错误，已并入裁决 N-1 约束。Step 1 门禁（复审通过 + 裁决收敛）满足，可进入 Step 2（写 `SPEC_p050.md`）。
