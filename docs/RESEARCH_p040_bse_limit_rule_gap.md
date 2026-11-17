# RESEARCH：P-040 bse 规则表日期维度补齐（U-P039-4）

> **批次**: P-040 · **Step 1 调研** · 日期 2026-11-17
> **判档**: **T1**（Layer-1：`tests/`；生产面 `filter/limit_rules.py` 行为变更）
> **上游**: P-039 [U-P039-4](PROGRESS.md)（§1.4）/ [IMPL_p039 §9.3](IMPL_p039_adj_factor_coverage.md)（崩溃原文）/ [CHECKLIST_p039 §9](CHECKLIST_p039_adj_factor_coverage.md)（异构终审复现）
> **代码证据时点**: HEAD `18141a4`（P-039 批次关闭）
> **基座**: DeepSeek-V4.1-Flash（Step 2 Review 须自报基座；同源时登记 U-P040-1）

---

## 1. 触发与题干

- **触发**: 用户「立项 P-040 修复 U-P039-4」。U-P039-4 为 P-039 Step 9 真实数据端到端暴露的 **P1**（P-012 遗留，被 adj 加载失败掩盖）。
- **现象**: 真实数据（`start_date=2020-01-23`）`engine.setup()` 抛
  `filter.limit_rules.LimitRuleError: 无匹配涨跌停规则: board=bse, is_st=False, date=2020-01-23`。
- **题干收窄（不扩做）**:
  1. 消除该 `LimitRuleError` 崩溃；
  2. 为 `8`/`4` 前缀代码补齐**符合监管事实**的历史涨跌停规则；
  3. 保留既有不变式：`(board, is_st, date)` 恰好 1 条命中，缺口仍 fail-fast；
  4. **不改** `infer_board` 的公开行为（`830001`/`430001` → `bse` 的既有契约与测试不动）；
  5. **不改** `universe_filter_clean.py` 的 try 范围（不引入捕获式降级——P-039 刚修复的正是同型静默降级）。

---

## 2. 代码事实基线（E3 读码 @`18141a4`）

| 锚点 | 内容 | 现状 |
|------|------|------|
| [limit_rules.py:19](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L19) | `RULESET_VERSION = "cn_a_2026_07"` | 版本口径随规则内容变化须同步 |
| [limit_rules.py:53-70](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L53-L70) | `RULES` 共 **11 条** | `bse` 仅 L68-69 两行，`effective_from=2021-11-15` |
| [limit_rules.py:78-95](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L78-L95) | `infer_board(code)` **无日期维度**；`8`/`4` → `bse` | `830001`/`430001` → `bse`（`test_infer_board_prefixes` 锁定） |
| [limit_rules.py:103-126](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L103-L126) | `resolve_limit` 命中数 ≠1 抛 `LimitRuleError`（`ValueError` 子类，L27） | 禁止回落默认值 |
| [limit_rules.py:150-174](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L150-L174) | `board_columns` **静态**分组一次；逐日 `resolve_limit(board, False/True, date)` | 每个窗口日在场 board 都必须可解析 |
| [universe_filter_clean.py:208-220](file:///f:/Coding/Factor_Trading_v3.0/filter/universe_filter_clean.py#L208-L220) | try 只包三条取数（L208-213）；`build_limit_prices` 在 L220 **try 之外** | 规则异常不被捕获（且 `LimitRuleError` 是 `ValueError` 子类，即便入 try 也会被吞成静默降级） |

---

## 3. 真实数据实况（E1/E2 探针）

**探针脚本**: `%TEMP%\p040_probe1.py` ~ `p040_probe5.py`（本机 `E:\Ashare_data\market_data`）。

### 3.1 `8`/`4` 前缀代码清点

| 项 | 读数 |
|----|------|
| 全量代码 | **5688** 只；`8`/`4` 前缀 **3** 只：`832317` / `833874` / `833994`（无 `4xxxx`） |
| 覆盖区间 | `2020-01-02` ~ `2021-10-20`（374 日）/ `2021-11-05`（371 日）/ `2021-11-03`（371 日） |
| 2021-11-15 之后 | **无数据**（三只均为精选层转板标的，数据在新代码下延续） |
| OHLC | 四种 kind 覆盖完全一致（同源导出，O-P039-1 同型） |

### 3.2 停牌缺口与「首日不设涨跌幅」的天然覆盖

| 代码 | 停牌前最后有效值 | 复牌首日（2020-07-27） | 首日相对收益 |
|------|------------------|------------------------|--------------|
| 832317 | 2020-04-27 / 16.58 | 13.35 | −19.48% |
| 833874 | 2020-05-18 / 18.76 | 13.00 | **−30.70%** |
| 833994 | 2020-05-06 / 49.20 | 40.20 | −18.29% |

- `833874` 首日 −30.70% **超出 ±30%** → 若以「停牌前最后有效前收」机械套用 30%，会被误标为跌停。
- 实测机制：[limit_rules.py:147-148](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L147-L148) 的 `ref` 由 `close.shift(1)` 构造，停牌期前收为 `NaN` → `limit_up/down` 为 `NaN` → 掩码 `check >= NaN` 为 False → **当日不限制**（与「精选层成交首日不设涨跌幅」一致，无需额外代码）。

### 3.3 分段涨跌幅分布（raw close，`pct_change(fill_method=None)`）

| 段 | 832317 | 833874 | 833994 |
|----|--------|--------|--------|
| `2020-01-23..2020-07-26`（创新层/基础层） | +14.57% / −4.50% | +8.71% / −9.74% | +21.75% / −9.34% |
| `2020-07-27..2021-11-14`（精选层） | +24.03% / −33.00% | +18.01% / −36.11% | +12.49% / −46.00% |

> 精选层段存在 < −30% 的日收益（如 −46.00%）——**成因未逐日归因**（可能为除权、复牌口径或数据口径差异），仅作为数据实况记录，**不作为「规则应更宽」的证据**（推测不入结论）。

### 3.4 缺口量化

| 口径 | 读数 |
|------|------|
| 交易窗口（2020-01-23 起） | **1460** 日 |
| 现状下 `bse` 不可解析日 | **436** 日（`2020-01-23` ~ `2021-11-12`） |
| 拟议案 M-A 下不可解析日 | **0**（探针 [E]） |

### 3.5 掩码影响量化（拟议 M-A vs 全段 30%）

> **口径**: `EPS = 0.005`，与生产 [universe_filter_clean.py:20](file:///f:/Coding/Factor_Trading_v3.0/filter/universe_filter_clean.py#L20) `EPS_PRICE` 一致。

| 方案 | limit_up 命中 | limit_down 命中 | 可交易单元格 |
|------|---------------|-----------------|--------------|
| M-A（两段） | **0** | **0** | 4380 / 4380 |
| M-C（全段 30%） | **0** | **0** | 4380 / 4380 |
| 分段（M-A） | pre 120 日 0/0；sel 316 日 0/0 | — | — |

> **关键结论**: 两种方案在该数据集上**可观测掩码差异为 0**（3 只标的从未在开盘触及 ±30%）——因此**必须以监管事实而非数据拟合来裁决**；本批的收益是「不崩溃 + 语义正确」，不是「拦截某日交易」。

### 3.6 修复后失败位置（探针 [A]）

拟议规则下 `engine.setup()` **通过** `build_masks()`，推进到 `_precompute_factors()` →
`FileNotFoundError: 因子文件不存在: E:\Ashare_data\market_data\UTR_turnover_new.pkl`（**U-P038-1，P2，不属本批**）。

---

## 4. 监管事实（E1 外部取证）

| 制度期 | 板块 | 涨跌幅 | 生效/开市 | 首日 | 来源 |
|--------|------|--------|-----------|------|------|
| 2018-01-15 起 | 新三板 创新层/基础层（**集合竞价**） | **涨幅 +100% / 跌幅 −50%** | 《全国中小企业股份转让系统股票转让细则》2018-01-15 施行 | 成交首日不设 | [中证网](https://www.cs.com.cn/ssgs/ssb/xsbtt/201801/t20180124_5681039.html) / [股转问答](https://www.neeq.com.cn/m/hot_qa/200008753.html) |
| 同上 | 新三板 **做市交易** | **不设涨跌幅** | 同上 | — | [股转投资者手册](https://www.neeq.com.cn/uploads/1/file/public/202006/20200605104834_4kiddpghe7.pdf) |
| 2020-07-27 起 | 新三板 **精选层**（连续竞价） | **±30%** | 精选层开市（首批 32 家） | 成交首日不设 | [股转问答](https://www.neeq.com.cn/hot_qa/200008764.html) / [央视网](http://m.news.cctv.com/2020/07/27/ARTIrUXV59b3KLvTxTA4ZFSg200727.shtml) |
| 2021-11-15 起 | **北交所** | **±30%** | 北交所开市（首批 81 家） | 新股首日不设 | [新华网](http://www.news.cn/2021-11/15/c_1128067032.htm) / [中证网](https://www.cs.com.cn/zhzq/bjsgs/szr/tt/202111/t20211113_6219861.html) |

**结论**: `8`/`4` 前缀代码不是「一直是北交所」，而是经历 **新三板（集合竞价 +100/−50，或做市不设）→ 精选层（±30）→ 北交所（±30）** 三个制度期。现状规则表把第一段错记为「无规则」，第二段错记为「北交所」。

---

## 5. 失败链（逐字）

`examples/run_single_backtest.py:60 engine.setup()`
→ [engine_v2.py:220](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L220) `self.universe.build_masks()`
→ [universe_filter_clean.py:151](file:///f:/Coding/Factor_Trading_v3.0/filter/universe_filter_clean.py#L151) `self._build_limit_masks()`
→ [universe_filter_clean.py:220](file:///f:/Coding/Factor_Trading_v3.0/filter/universe_filter_clean.py#L220) `build_limit_prices(...)`（**try 之外**）
→ [limit_rules.py:161](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L161) `resolve_limit("bse", False, 2020-01-23)`
→ [limit_rules.py:119](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L119) `raise LimitRuleError`

---

## 6. 影响面

| 面 | 影响 |
|----|------|
| 真实数据回测 | 任何 `start_date < 2021-11-15` 且 `8`/`4` 前缀代码在列 → `setup()` 崩溃（当前数据 3 只，436 日不可解析） |
| examples 脚本 | 5 个真实数据脚本默认 `start_date=2020-01-23` → 全部命中（P-039 V6b 已证） |
| 合成夹具 | `_synth_fixture` 默认代码 `000001/000002/600001/...`；`430001`/`830001` 仅用于 2024 日期（`test_universe_delisting.py:20` `bdate_range("2024-01-02")`）→ **零影响** |
| golden | `tests/golden/*.json` 无 `8`/`4` 代码 → **零重录** |
| 规则报告 | `additional_info.caliber.ruleset_version` 值变化（见 §9 C2） |
| 其他 board | main/gem/star 规则零改动 |

---

## 7. 方案矩阵

| 方案 | 内容 | 判定 |
|------|------|------|
| **M-A（推荐）** | `RULES` 为 `bse` 增补两段：`2018-01-15..2020-07-27`（+100%/−50%）+ `2020-07-27..None`（±30%）；`is_st` 两态同参；`RULESET_VERSION` bump | ✅ 改动仅规则常量（1 文件约 +8 行）；`infer_board` 契约不变；缺口 436 → 0；fail-fast 保留 |
| M-B | `infer_board(code, date)` 引入 `neeq` 板块 + 新规则 | ❌ 签名变更（2 调用点 + 测试）；`board_columns` 静态分组需改为按日重算；`board` 报告字段新增枚举；改动面与风险远大于收益 |
| M-C | `bse` 单段前移至 2018-01-15（或窗口起点），仍 ±30% | ❌ **事实错误**（创新层集合竞价为 +100/−50）；若取「窗口起点」则窗口前移会再次崩 |
| M-D | `_build_limit_masks` 捕获 `LimitRuleError` 并降级全 True | ❌ **静默降级**，与 P-039 修复的缺陷同型；且吞掉「规则区间重叠」等真错误 |
| M-E | 涨跌停计算剔除 `8`/`4` 前缀代码 | ❌ 2020-07-27 后精选层 ±30% 失效（涨停日可成交）；语义失真 |
| M-F | 数据侧删除 3 只标的 / 改数据导出 | ❌ 不解决通用性；删真实可交易标的不可接受 |
| M-G | 在 `special_no_limit_mask` 追加「新三板期不设涨跌停」 | ❌ `resolve_limit` 在掩码之前调用，仍会抛 `LimitRuleError`（不解决崩溃）；且事实错误（集合竞价为 +100/−50 而非不设限） |

**裁决**: **M-A**。理由：唯一同时满足「最小改动 / 事实正确 / fail-fast 保留 / 零公开契约变更」的方案；M-A 与 M-C 的数据可观测差异为 0（§3.5），故**正确性只能由监管事实裁决**，不能以「跑通」代替。

---

## 8. 精确语义（实施规格输入）

```python
# RULES 中 bse 段（替换现有 L68-69 两行）
# 北交所（含前身）：新三板创新层/基础层集合竞价（涨幅 100% / 跌幅 50%，2018-01-15 起）
# → 精选层 ±30%（2020-07-27 开市）→ 北交所 ±30%（2021-11-15 开市，同一 30% 段延续）
LimitRule("bse", False, pd.Timestamp("2018-01-15"), pd.Timestamp("2020-07-27"), 1.00, -0.50),
LimitRule("bse", False, pd.Timestamp("2020-07-27"), None, 0.30, -0.30),
LimitRule("bse", True, pd.Timestamp("2018-01-15"), pd.Timestamp("2020-07-27"), 1.00, -0.50),
LimitRule("bse", True, pd.Timestamp("2020-07-27"), None, 0.30, -0.30),
```

| # | 语义 | 说明 |
|---|------|------|
| S1 | 区间半开 | `matches` 用 `date >= effective_from` 且 `date < effective_to` → `2020-07-27` 归第二段 |
| S2 | 恰好 1 条 | 2018-01-15 起 `bse` × 两态均恒 1 条（探针 [E] 实测 0 缺口） |
| S3 | fail-fast 保留 | 早于 2018-01-15 仍抛 `LimitRuleError`（不回落默认值） |
| S4 | 首日不设涨跌幅 | 由「前收 `NaN` → `ref` `NaN` → 不限制」天然覆盖（§3.2 实测 `833874` −30.70%）；快照可用时由 `special_no_limit_mask` 覆盖 |
| S5 | 做市不设涨跌幅 | 代码前缀与行情数据无法区分做市/集合竞价 → 统一按集合竞价上限（+100/−50）处理（宽松上界，不产生伪拦截） |
| S6 | 其余 board 逐字不变 | main/gem/star 9 条零改动 |
| S7 | 版本口径 | `RULESET_VERSION` "cn_a_2026_07" → "cn_a_2026_11"（规则集修订标记） |

---

## 9. 行为变更

| ID | 变更 | 证据 |
|----|------|------|
| **C1** | 真实数据 `engine.setup()`：`LimitRuleError` 崩溃 → 通过 `build_masks()` 并推进到 `U-P038-1` 的 `FileNotFoundError`（因子文件缺失，P2，不属本批） | E2 探针 [A] |
| **C2** | `RULESET_VERSION` "cn_a_2026_07" → "cn_a_2026_11"（结果 `additional_info.caliber.ruleset_version` 值变化） | 读码 L19 + [engine_v2.py:1213](file:///f:/Coding/Factor_Trading_v3.0/core/engine_v2.py#L1213) |

其余零行为变更：合成夹具与 golden 无 `8`/`4` 代码（§6）。

---

## 10. 未决与观察

| ID | 内容 | 处置 |
|----|------|------|
| U-P040-1 | P-040 的 RULE-5 异构终审预留 | 作者 DeepSeek-V4.1-Flash；Step 2/4/6/8 同基座时累计，待异构基座会话终审 |
| O-P040-1 | 做市交易不设涨跌幅无法从代码前缀/行情区分 | 观察（统一按集合竞价上界，不产生伪拦截；数据实测无 >100% 日收益） |
| O-P040-2 | 精选层/北交所「成交首日不设涨跌幅」依赖快照或前收 NaN | 观察（本数据 3 只均停牌至 2020-07-27，前收 NaN 天然覆盖；若未来数据连续，需快照 `list_date` 扩展语义） |
| O-P040-3 | `4xxxx` 老三板（退市股）与 `8xxxx` 新三板共用前缀判定 | 观察（当前数据无 `4xxxx`；若引入需独立取证） |
| O-P040-4 | 数据中无 `8`/`4` 代码在 2021-11-15 后交易 → **北交所期**的规则未被数据行使 | 观察（M-A 把精选层与北交所合并为同一 ±30% 段；规则保留以备未来数据） |
| O-P040-5 | `_RULE_INDEX`（L72-75）构建后从未被读取（`resolve_limit` 直接过滤 `table`） | 观察（P-012 遗留死代码；本批不动，避免扩做） |

---

## 11. 可重放命令

```powershell
$py = 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe'
# E1 数据清点 / 缺口 / 规则可解析性
& $py 'C:\Users\Peng\AppData\Local\Temp\p040_probe1.py'
& $py 'C:\Users\Peng\AppData\Local\Temp\p040_probe2.py'
# E2 首日序列 / 掩码影响 / setup 失败位置
& $py 'C:\Users\Peng\AppData\Local\Temp\p040_probe3.py'
& $py 'C:\Users\Peng\AppData\Local\Temp\p040_probe4.py'
& $py 'C:\Users\Peng\AppData\Local\Temp\p040_probe5.py'
```

> 探针为临时脚本（`%TEMP%`），不入仓。

---

## 12. Step 1 自查（RULE-4）

| # | 自查项 | 结论 |
|---|--------|------|
| 1 | 题干 = U-P039-4，未扩做 | ✅ 五项收窄见 §1 |
| 2 | 事实与推测分离 | ✅ §3 数据读数（E1/E2）与 §4 监管事实（外部来源）分别标注；E5 推测未入结论 |
| 3 | 「首日豁免」是否被误当成已实现 | ✅ 明确：当前靠前收 `NaN` 天然覆盖（§3.2 实测），未新增代码；局限登记 O-P040-2 |
| 4 | M-A vs M-C 的可观测差异 | ✅ 实测均为 0 命中（§3.5）→ 裁决依据写明「监管事实」而非「跑通」 |
| 5 | 是否触碰 `infer_board` / try 范围 | ✅ 均不动；`830001`/`430001` 既有测试保持 |
| 6 | 版本口径 | ✅ C2 显式登记 |
| 7 | 探针可复现 | ✅ 脚本路径与命令见 §11 |

---

## 13. 判档

**T1**——变更面含 `tests/`（Layer-1）与 `filter/limit_rules.py` 生产行为；按判档规则 1 直接命中 T1。

---

## 14. Step 2 调研 Review 记录（同基座独立视角，2026-11-17）

> **基座披露（RULE-4）**: 复审会话自报 `You are powered by the model named DeepSeek-V4.1-Flash.` → 与作者**同源**，RULE-5 不成立；U-P040-1 跟踪。

### 14.1 机械复核

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 代码锚点 | L19 / L53-70 / L78-95 / L103-126 / L147-148 / L150-174 / L161 / L119 / L220 / L151 / L1213 实查命中 | ✅ |
| 2 | `RULES` 计数 | main 3 + gem 4 + star 2 + bse 2 = **11** | ✅ |
| 3 | 缺口复算 | 窗口 1460 日 / bse 不可解析 **436** 日 | ✅ |
| 4 | 首日收益复算 | 13.35/16.58−1 = −19.48%；13.00/18.76−1 = −30.70%；40.20/49.20−1 = −18.29% | ✅ |
| 5 | 方案矩阵完整性 | M-A~M-G 七案，各含拒绝理由 | ✅（M-G 为复审补入） |

### 14.2 发现与当轮处置（2 P2 + 3 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S2-P040-1** | **P2** | §3.5 掩码量化未声明 `EPS` 口径，初算用 `1e-4` 而生产 `EPS_PRICE=0.005`（更宽松 → 命中可能更多） | 按生产口径 `0.005` 复跑：M-A / M-C 仍 **0/0**，分段 pre 120 日 0/0、sel 316 日 0/0；§3.5 补口径注 |
| **F-S2-P040-2** | **P2** | §3.3 把「精选层段 < −30% 日收益」归因为「首日不设涨跌幅/除权/复牌」——未取证（E5 推测入结论） | 改为「成因未逐日归因，仅作数据实况，不作规则宽度证据」 |
| F-S2-P040-3 | P3 | M-C 被描述为「前移至 2020-01-23」，是弱化靶子（公平对照应为 2018-01-15 全段 30%） | M-C 改为「2018-01-15 或窗口起点」双口径，拒绝理由归位到「事实错误」 |
| F-S2-P040-4 | P3 | 方案矩阵缺「`special_no_limit_mask` 扩展」案（M-G），无法证明已穷举 | 补 M-G 行并给出双重拒绝理由（不解决崩溃 + 事实错误） |
| F-S2-P040-5 | P3 | O-P040-4 称「北交所段」而 M-A 将精选层与北交所合并为同一 ±30% 段 | 措辞改为「北交所期规则未被数据行使」 |

**观察（新建）**: **O-P040-5**——`_RULE_INDEX`（L72-75）构建后从未被读取（死代码，P-012 遗留）；本批不动。

### 14.3 结论

**Step 2 Review pass（2 P2 + 3 P3 当轮回写）**——数据读数可复算、事实与推测分离、方案矩阵穷举、M-A 裁决依据成立；**准予进入 Step 3 DESIGN**。
**RULE-5**：第 1 轮同基座 → U-P040-1 pending。
