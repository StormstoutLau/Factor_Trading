# P-012 偏差防护与接口锁定 · 专项调研

> **文档编号**: RESEARCH_bias_interface
> **阶段**: Phase 1 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 1 + §11 + §12 补充调研完稿；Step 2 Review 通过（§10）；**Step 3 DESIGN 完稿（2026-11-10）→ [DESIGN_p012_bias_interface.md](DESIGN_p012_bias_interface.md)**；待 Step 4 Review
> **上游**: [RESEARCH_backtest_validation.md](RESEARCH_backtest_validation.md)（P-011）；[PROGRESS.md](PROGRESS.md) §1.4 P-012 立项
> **证据时点**: 本仓读数 @ `05af52f`（2026-11-10）；§11 E2 探针同日、同 commit（脚本见 §11.11）
> **档位**: T1（若实施将触及 `core/data.py`、`filter/`、`core/interfaces.py`、`tests/`）

---

## 0. 口径声明（先于结论）

用户所指「**接口锁定**」在本批按以下口径取证：

> **接口锁定 = 接口契约是否被锁定为唯一真源**：同一能力是否只有一个权威契约、实现能否无静默破坏地替换、版本演进是否有兼容性验证。

据此拆成三问：①契约是否唯一（Protocol / ABC / 双 dataclass）；②实现是否可替换且有符合性证明；③版本演进是否可验证（N/N-1）。

**U-5 裁决（2026-11-10）**：用户明确为**两件事**——**5a 接口契约稳定性**（本口径，见 §11.5）与 **5b 供应商接口锁定**（pkl 字段/目录结构/供应商切换成本，见 §11.6，对应 P16-P18）。

---

## 1. 调研目标

| ID | 核心问题 | 本批判据 |
|----|----------|----------|
| **B-1** | 是否具备**幸存者偏差**处理能力？ | 存在退市股、上市/退市日期、退市收益，且股票池按日期动态 |
| **B-2** | 是否具备**前视偏差**防护？ | 决策时点可知性可审计；掩码/因子/成交价均不引用未来数据 |
| **B-3** | 是否具备**复权**正确处理？ | 前/后复权定义与实现一致；信号用复权价、成交用不复权价 |
| **B-4** | 是否具备 **ST / 停牌**处理？ | 掩码齐全、阈值现行有效、缺失时 fail-safe |
| **B-5** | 是否存在**接口锁定**问题？ | 契约唯一、实现可替换、版本兼容可验证 |

**范围边界**：只做调研，不改代码；不重复 P-011 已覆盖的「准确性四层判据」与「外部框架对拍」。

---

## 2. 调研方法

| 工具 | 用途 | 范围 |
|------|------|------|
| Read / Grep / Glob | 本仓读码 | `core/data.py`、`core/factor.py`、`filter/universe_filter_clean.py`、`core/interfaces.py`、`core/config.py`、`core/engine_v2.py` |
| Select-String / Grep 计数 | 机械事实 | 退市字段、Protocol/ABC 数量、配置双定义、阈值默认值 |
| WebSearch / WebFetch | 外部锚点 | 幸存者偏差、前视偏差、复权口径、ST 新规、接口契约；U-6~U-9 的数据来源、弃用政策、规则表、端口-适配器 |

**证据分级**：E1 可重放命令；E2 运行时（本批未新增探针）；E3 静态读码（绑 `@05af52f`）；E4 盲区扫描（声明范围）；E5 不用于结论。

---

## 3. 外部锚点

### 3.1 偏差类

#### A1 Qlib · Point-in-Time 数据库（T1，官方文档）

- **原文**: 「If we only use the latest version for historical backtesting, data leakage will happen.」；PIT 保证「online trading and historical backtesting the same」
- **用途**: B-1/B-2 的终极标准：数据版本轴 + 决策时点可复现

#### A2 Shumway (1997) / Shumway & Warther (1999) · 退市偏差（T2 二手转述）

- **原文要点**（经行业文章转述）：CRSP 中因业绩退市公司的**终止收益常缺失**；把缺失当作 0 会显著高估小盘/价值策略收益；作者估计 NYSE/AMEX 约 **−30%**
- **验证状态**: ⚠️ 未直取原文（付费墙）；两篇独立行业文章交叉一致
- **用途**: B-1 的「退市收益不能记 0」依据

#### A3 CRSP 退市收益的三种处理（T2，行业实践）

- **原文要点**: ①zero approach（破产记 0，保守但可辩护）；②CRSP 标准化退市收益（研究界事实标准）；③OTC 延续交易
- **用途**: B-1 方案选项（S-B）

#### A4 Point-in-Time 指数成分（T2，行业实践）

- **原文要点**: 「Do not use today's membership applied retroactively」；应使用每个时点的历史成分
- **用途**: B-1 股票池按日期动态的依据

### 3.2 前视偏差

#### A5 标准化只用训练期统计量（T3，arXiv 实证）

- **原文要点**: 「standardization is performed for each study period using only the training data to calculate mean and standard deviation」
- **用途**: B-2 的「统计量时点」判据；本仓 `_standardize` 用 `axis=1`（当日截面），已满足该判据（见 P6）

#### A6 时间序列不得随机切分（T3，行业文章）

- **原文要点**: 对时序数据使用 `train_test_split(shuffle=True)` 属方法错误，会训练到未来数据
- **用途**: B-2 的样本切分判据；本仓 `walk_forward` 已有 purge（P-011 P11）

### 3.3 复权

#### A7 前复权 / 后复权定义（T2 财经媒体，与交易所口径一致）

- **原文要点**:
  - 前复权：「保持现有价位不变，将以前的价格经权息调整后变为现有价格水平下的可比价格」
  - 后复权：「保持先前的某一时点价格不变，将该时点以后的价格经权息调整后变为该时点价格水平下的可比价格」
  - 方向：前复权用**该 K 线之后**的事件；后复权用**该 K 线及之前**的事件
- **用途**: B-3 判定 `forward`/`backward` 实现是否颠倒（见 P10）

#### A8 成交价必须用不复权价（T2 行业实践）

- **原文要点**: 「不复权：真实成交价……成交价格、成交金额、手数、涨跌停都必须用它」
- **用途**: B-3 的核心判据：复权价只用于信号/收益，不用于成交

#### A9 Qlib 复权口径（T1，官方文档）

- **原文**: 「Qlib normalize the price on first trading day of each stock to 1 when adjusting them.」
- **用途**: B-3 的跨框架对齐（与 P-011 A2 一致）

### 3.4 ST / 停牌

#### A10 上交所交易规则（2026 修订）（T1，官方）

- **原文要点**: 涨跌幅限制的例外情形（IPO 前 5 日、退市整理首日、重新上市首日等）；交易所可调整比例
- **用途**: B-4 的「阈值不是常数」依据

#### A11 证监会风险警示股票规则（T1，官方）

- **原文要点**: 风险警示股票涨跌幅限制 **5%**（A 股前收盘 ≤ 0.1 元时为 0.01 元）；退市整理股票 10%
- **用途**: B-4 历史阈值来源

#### A12 沪深主板 ST 涨跌幅调整为 10%（2026-07-06 起）（T1，官方媒体）

- **原文要点**: 「7 月 6 日起，沪深主板 ST、*ST 股涨跌幅限制由 5% 调整至 10%，与主板普通股票保持一致」（新华网）；中国证券网同题报道
- **用途**: **B-4 的关键时效性事实**：本仓默认 ST 阈值 4.8% 对 2026-07-06 之后的数据已失效（见 P13）

### 3.5 接口契约

#### A13 PEP 544 · Protocols（T1，官方）

- **原文要点**: Protocol 是结构化子类型，不要求显式继承；与 Java interface 不同，可提供默认实现与状态
- **用途**: B-5 的契约形态选择

#### A14 ABC vs Protocol 的取舍（T2，Real Python）

- **原文要点**: 需要**继承 + 实例化时强制**时用 ABC；需要**不依赖继承的静态检查**时用 Protocol
- **用途**: B-5 的「双轨并存」是否合理

#### A15 Pact · 消费者驱动契约测试（T1，官方文档）

- **原文要点**: 「As long as all your contract tests pass, you should be able to deploy changes without versioning the API」；破坏性变更用 **expand and contract** 模式
- **用途**: B-5 的「实现符合性测试」方案（I-B）

#### A16 N / N-1 兼容（T2，行业实践）

- **原文要点**: 滚动部署期间新旧版本共存，变更必须同时兼容当前与上一版本；契约变更应「additive、optional 安全；删除/重命名/改类型是破坏性」
- **用途**: B-5 的版本兼容判据（I-D）

---

## 4. 本仓事实

| ID | 事实 | 证据 |
|----|------|------|
| **P1** | **无退市数据**：全仓无 `list_date` / `delist_date` / `delisting_return` 字段；`stock_codes` 直接取 `close.pkl` 的列（当前仍存在的股票），无上市/退市日期轴 | E4 扫描 `core/`+`filter/`+`tests/`（`Grep 'list_date|delist|退市'` 命中 9 文件，逐个人工确认：全部为文档/测试文案，无数据字段）；E3 `data.py:167-171` |
| **P2** | 股票池是**静态全样本**：`UniverseFilter` 只做「当日是否可交易」的掩码，不做「当日是否已上市/已退市」的动态成分判定 | E3 `universe_filter_clean.py:87-121`；E4 扫描 `_build_.*mask` 无 list/delist 维度 |
| **P3** | 因子文件对齐**有未来防护**：月度因子按「≤ 交易日的最近日期」向前对齐，早期无数据填 NaN（注释明确「避免未来信息泄露」） | E3 `data.py:490-508` |
| **P4** | 因子处理**无跨期泄漏**：`_neutralize` 逐日截面回归；`_standardize` 用 `mean(axis=1)` / `std(axis=1)`（当日截面） | E3 `factor.py:296-307`、`:402-407` |
| **P5** | **涨跌停掩码使用当日收益**：`_limit_up_mask = ~(returns >= threshold)`，`returns` 为当日复权收盘 `pct_change`；该掩码在**次日开盘执行**时以执行日索引使用（`universe.buyable.loc[date]`） | E3 `universe_filter_clean.py:154-182`、`:181-182`；`engine_v2.py:441`；`data.py:396-407` |
| **P6** | **`next_day_tradable` 使用未来停牌**：`suspend.shift(-1)` 后并入 `buyable`，即 t 日行包含 t+1 日停牌状态；`check_next_day_tradable` 默认 **True** | E3 `universe_filter_clean.py:203-215`、`:402-404`；`config.py:230` |
| **P7** | **复权方向疑似颠倒**：`forward`（默认）= `price * adj_factor`；`backward` = `price * adj_factor / adj_factor.iloc[-1]`。按 A7 定义，前者是「以上市首日为基准」（后复权），后者是「以最新为基准」（前复权） | E3 `data.py:444-456` |
| **P8** | **成交价使用复权价**：`_force_liquidation` / `_process_pending_orders` / `_execute_next_day_orders` 均调用 `get_adj_price("open"/"close", cfg.adjustment_type)` 作为成交价；`_calculate_returns` 也用复权价 | E3 `engine_v2.py:387/434-436/755`、`data.py:396-407` |
| **P9** | 复权恒等式测试**只验证测试数据 adj≡1**，未覆盖非 1 因子下的方向与成交价语义 | E3 `test_real_ashare_strict_validation.py:116-125` |
| **P10** | ST / 停牌 / 涨跌停掩码**齐全**，缺失数据有 fail-safe（停牌/ST 缺失 → 全 True + warning；P-010 改为 `0=正常` 默认帧） | E3 `universe_filter_clean.py:132-140`、`:189-201`；P-010 CHECKLIST |
| **P11** | **ST 阈值已过时**：`st_limit_up_threshold = 0.048` / `-0.048`（≈5% 板），但沪深主板 ST 自 **2026-07-06** 起为 10%；普通股阈值 0.095（10% 板留 0.5% 容差） | E3 `config.py:231-234`、`universe_filter_clean.py:28-31`；A12 |
| **P12** | ST 阈值判定用 `st.shift(1)`（昨日 ST 状态），与当日 ST 状态（`_st_mask` 用当日）**不一致** | E3 `universe_filter_clean.py:158-172`、`:189-197` |
| **P13** | 无「退市整理期」「IPO 前 5 日无涨跌幅限制」「复牌首日」特殊处理 | E4 扫描 `filter/`（`Grep '退市整理|IPO|复牌'` 0 命中） |
| **P14** | **契约双轨**：`core/interfaces.py` 同时有 **14 个 Protocol** 与 **7 个 ABC**（`AbstractDataManager` 等），同一能力两套契约 | E1：`Grep 'class .*Protocol'` = 14；`Grep '@abstractmethod'` = 7；E3 `interfaces.py:25-491` |
| **P15** | **配置双定义**：`core/config.py` 的 `UniverseConfig` 与 `filter/universe_filter_clean.py` 的 `UniverseFilterConfig` 字段同名但为不同类；`engine_v2.py:195` 直接把前者传给期望后者的 `UniverseFilter(...)`，仅靠鸭子类型工作（*Step 4 Review F-D6 修正：原引 ：191 为注入分支，构造调用实为 ：195*） | E3 `engine_v2.py:195`；`config.py:217-234`；`universe_filter_clean.py:16-49`；该处是 `--check-untyped-defs` 残差 8 之一（P-007 层 B V3） |
| **P16** | **数据层双实现**：`DataManager`（V2 生产路径）与 `DataLoaderV3`（仅 V3 引擎 + `tools/benchmark.py` + 测试使用）并存；P-004 已登记为技术债 | E1 `Grep 'from core.data_v3 import'` = 16 行（生产仅 `engine_v3_vector.py:67`、`tools/benchmark.py:65`） |
| **P17** | **配置双版本**：`core/config.py`（在用）与 `core/config_v2.py`（已冻结，零生产引用，TD-2/ADR-016） | E3 `config_v2.py` 冻结声明；PROGRESS P-002 |
| **P18** | `core/__init__.py` **无导出**（空包，ADR-016）：包级 API 未锁定，外部只能深路径导入；好处是内部重构不破坏包级 API，坏处是无统一契约入口 | E3 `core/__init__.py:1-12` |
| **P19** | **无契约测试**：无「同一套协议断言跑所有实现」的测试；`mypy` 只做静态结构检查，且 `--check-untyped-defs` 残差 8 未纳入门禁 | E4 扫描 `tests/`（无 `conformance` / `contract` 命名与断言）；P-007 层 B V3 |
| **P20** | 无版本化声明：`core/` 无 `__api_version__` / SemVer，无 N/N-1 兼容验证 | E4 扫描 `core/`（`Grep '__version__|__api_version__'` 0 命中） |

---

## 5. 五问逐项诊断

### 5.1 B-1 幸存者偏差

| 判据 | 现状 | 结论 |
|------|------|------|
| 退市股是否在池 | ❌ 无退市数据，股票池 = 现存股票 | **不具备** |
| 上市/退市日期 | ❌ 无字段 | 不具备 |
| 退市收益 | ❌ 无 | 不具备 |
| 股票池按日期动态 | ❌ 静态列集合 | 不具备 |

**风险等级：高**。当前任何「长期、小盘、价值」类回测都会系统性高估收益（A2/A3）。若只跑 2024 年后的短样本且池为大盘股，偏差较小，但不可声明「无幸存者偏差」。

### 5.2 B-2 前视偏差

| 判据 | 现状 | 结论 |
|------|------|------|
| 信号 → 成交时序 | V2：t 日收盘生成、t+1 开盘成交 ✅；V3：当日 close 成交（定位为筛选器，已声明） | V2 合规 |
| 因子对齐 | ✅ `≤ trade_date` 向前对齐 | 合规 |
| 因子统计量 | ✅ 当日截面 `axis=1` | 合规 |
| 涨跌停掩码 | ❌ 用**执行日收盘收益**判断执行日开盘可买 | **疑似前视** |
| 次日可交易性 | ❌ `suspend.shift(-1)` 把 t+1 停牌并入 t 日 buyable | **疑似前视** |
| 未来信息测试 | ❌ `test_08` 只查 NaN 形状，不查时间方向（P-011 P3） | 覆盖不足 |

**风险等级：高**。P5/P6 两处若经 E2 探针证实，会系统性放宽/收紧可交易集合，方向取决于涨跌分布；这属于「程序性前视」，与数据源无关，必须修。

### 5.3 B-3 复权

| 判据 | 现状 | 结论 |
|------|------|------|
| 前/后复权定义 | ❌ 命名与公式颠倒（P7） | **已证实**：Tushare 官方公式比对，见 §11.3（夹具 adj≡1 无法做数值验证） |
| 信号/收益用复权价 | ✅ | 合规 |
| 成交用不复权价 | ❌ 用复权价成交（P8） | **不合规** |
| 恒等式测试 | ❌ 仅 adj≡1 测试数据（P9） | 覆盖不足 |
| 跨源口径 | ❌ 无（Qlib 首日归一 vs 本仓乘积） | 不可比 |

**风险等级：高**（若 P7 证实）。复权方向颠倒 + 成交价用复权价，会使股数、现金、成本、涨跌停判断同时失真。

### 5.4 B-4 ST / 停牌

| 判据 | 现状 | 结论 |
|------|------|------|
| 停牌掩码 | ✅ 当日 `suspend==0` | 具备 |
| ST 掩码 | ✅ 当日 `st==0` | 具备 |
| 涨跌停掩码 | ⚠️ 有，但时点可疑（P5） | 部分具备 |
| 阈值现行性 | ❌ ST 4.8% 对 2026-07-06 后失效（P11） | **过时** |
| ST 状态时点一致 | ❌ 阈值用 `shift(1)`、掩码用当日（P12） | 不一致 |
| 特殊情形 | ❌ 无退市整理/IPO 前 5 日/复牌首日（P13） | 不具备 |
| 缺失 fail-safe | ✅ 全 True + warning（P-010） | 具备（偏乐观） |

**风险等级：中-高**。ST 阈值过时会产生**假涨停**（把 5%-10% 的正常波动误判为涨停 → 不可买），在 2026-07-06 之后的数据上直接扭曲回测。

### 5.5 B-5 接口锁定

| 判据 | 现状 | 结论 |
|------|------|------|
| 契约唯一 | ❌ 14 Protocol + 7 ABC 双轨；配置双定义（P14/P15） | **未锁定** |
| 实现可替换 | ⚠️ 结构上可替换，但无符合性证明（P19） | 部分 |
| 版本兼容可验证 | ❌ 无 SemVer / N-1 测试（P20） | 不具备 |
| 包级 API | ⚠️ `core/__init__.py` 空（P18） | 有意为之，但无契约入口 |
| 双实现/双配置 | ⚠️ DataManager vs DataLoaderV3；config vs config_v2（P16/P17） | 技术债 |

**风险等级：中**。它不直接产生错误结果，但会让「替换数据源/替换执行器」时出现静默不兼容——P-007 层 B 已遇到一次（`UniverseConfig` vs `UniverseFilterConfig` 的 `arg-type`）。

---

## 6. 方案候选与比较矩阵

### 6.1 B-1 幸存者偏差

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **S-A 数据契约 + 动态池（默认路径）**（推荐） | **默认按「有退市数据」实现**：新增 `list_date` / `delist_date` / `delisting_return` 契约（必需字段），`stock_codes` 按日期求「已上市 ∩ 未退市」；数据缺失时进入 S-C 降级 | 中 | 高 | 低 | 中（数据契约升级） | 高 | 3-5 天 | 长期 |
| S-B 退市收益规则 | 退市日按 0 / −30% / 自定义三选一，配置化；A 股可按退市整理期实际跌幅 | 低 | 中 | 低 | 高 | 中 | 1 天 | 长期 |
| **S-C 数据缺失降级**（推荐配套） | 无退市数据时：显式 warning + 报告标注「未校正幸存者偏差」+ 方向性声明（高估）+ 敏感性分析（剔除小盘/低价股复跑） | 低 | 中 | 低 | 高 | 中 | 1 天 | 长期 |

**推荐**：**S-A 为默认实现路径**（数据契约要求退市字段），S-B 配置化退市收益，S-C 仅在数据缺失时启用降级。降级必须**显式**（warning + 报告字段 + 方向性声明），不静默假装已处理。

### 6.2 B-2 前视偏差

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **L-A 掩码时点修正**（推荐） | 涨跌停判定改用「上一交易日收益」或「开盘价 vs 涨停价」；`next_day_tradable` 改用当日已知信息（如 `suspend.shift(1)`） | 低-中 | 高 | 低 | **中（回测结果会变）** | 高 | 2-3 天 | 长期 |
| **L-B 前视自检测试**（推荐） | ①t 与 t+k 因子相关性衰减检查；②未来数据扰动（把 t+1 之后数据置 NaN，断言 t 日决策不变）；③`test_08` 重写为时间方向断言 | 低 | 高 | 低 | 高 | 高 | 2 天 | 长期 |
| L-C 维持现状 | 依赖 V2 的 T+1 主流程 | 0 | 低 | — | — | — | 0 | 风险累积 |

**推荐**：L-B 先行（先证明问题存在/不存在），L-A 随后（行为变更需单独披露与基线刷新）。

### 6.3 B-3 复权

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **A-A 口径校正**（推荐） | ①按 A7 校正 `forward`/`backward` 命名与公式；②成交价改用 `adjustment="none"`，信号/收益保留复权价；③配置项显式区分 `signal_adjustment` 与 `trade_price` | 中 | 高 | 低 | **中（结果会变）** | 高 | 3-4 天 | 长期 |
| **A-B 复权恒等式测试**（推荐） | 构造含分红/送股的 3 日样本，逐日断言前/后复权与手工计算一致；断言成交金额用不复权价 | 低 | 高 | 低 | 高 | 高 | 1-2 天 | 长期 |
| A-C 仅文档 | 声明当前口径 | 0 | 低 | — | — | — | 0 | 不可接受（若 P7 证实） |

**推荐**：A-B 先做（用真实因子样本证实或证伪 P7），再 A-A。

### 6.4 B-4 ST / 停牌

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **U-A 阈值按日期段生效**（推荐） | 配置改为「日期 → 阈值」表：1998-2026-07-05 主板 ST=5%，2026-07-06 起=10%；普通股 10%，创业板/科创板 20%（按板块） | 中 | 高 | 中（规则会变） | 中 | 高 | 3 天 | 长期 |
| U-B 涨跌停价判定 | 用「前收盘 × (1±比例)」与当日开盘/最高/最低比较，而非收益阈值 | 中 | 高 | 低 | 中 | 高 | 3 天 | 长期 |
| U-C 特殊情形补充 | 退市整理期、IPO 前 5 日、复牌首日掩码 | 中 | 中 | 中 | 高 | 中 | 2-3 天 | 长期 |
| U-D 仅调默认值 | 把 4.8% 改成 9.5%，不做日期段 | 低 | 中 | 低 | 中 | 低 | 0.5 天 | 历史样本仍错 |

**推荐**：U-A + U-B；U-C 按数据可得性决定。

### 6.5 B-5 接口锁定

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **I-A 契约唯一真源**（推荐） | 以 `Protocol` 为唯一契约；ABC 降为「可选 adapter 基类」或删除；配置双定义合并为「一个 dataclass + 转换函数」 | 中 | 高 | 低 | 中 | 高 | 3-5 天 | 长期 |
| **I-B 契约符合性测试**（推荐） | 每个 Protocol 一套断言，对全部实现（含 Mock）参数化跑 | 中 | 高 | 低 | 高 | 高 | 3-5 天 | 长期 |
| I-C 版本化 | `core/__api_version__` + SemVer + N/N-1 兼容测试 | 中 | 中 | 中 | 高 | 中 | 2-3 天 | 长期 |
| I-D 维持 | 依赖 mypy 静态检查 | 0 | 低 | — | — | — | 0 | 静默不兼容累积 |

**推荐**：I-A + I-B；I-C 在对外发布 API 时再做。

---

## 7. 建议路线（供 DESIGN 参考）

| 阶段 | 内容 | 前置 | 说明 |
|------|------|------|------|
| **L0 证实/证伪（2-3 天）** | 复权方向 E2 探针（真实分红样本）+ 前视两处 E2 探针（未来数据扰动） | 无 | **先证实问题，再改代码**；避免基于静态推断做行为变更 |
| **L1 低风险修复（3-5 天）** | `test_08` 重写 + 复权恒等式测试 + 契约符合性测试（I-B） | L0 | 测试先行，不改生产行为 |
| **L2 行为变更（1-2 周）** | 复权口径校正（A-A）+ 掩码时点修正（L-A）+ ST 阈值日期段（U-A） | L1 | 每项单独批次、单独披露、刷新基线 |
| **L3 数据能力（默认路径）** | 退市数据契约（S-A/S-B）+ 动态股票池；数据缺失时走 S-C 降级 | 数据契约定义 | **默认按有退市数据实现**，不是「按需」 |
| **L4 接口治理（按需）** | 契约唯一化（I-A）+ 版本化（I-C） | — | 可独立于偏差批次 |

**不建议**：把 L2 的多项行为变更塞进同一批；它们会同时改变回测结果，无法归因。

---

## 8. 未决项登记（四元块）

> **状态（2026-11-10）**：U-1~U-5 已由用户裁决，落地见 **§11.0 裁决记录**；本节保留 Step 1 结束时的待裁决原貌（U-2~U-5 的「待 E2」项已被 §11 取代：U-2 → §11.2、U-3 → §11.3、U-4 → §11.4、U-5 → §11.5/§11.6）。新增 U-6~U-9 见 §11.9。

- **U-1 幸存者偏差：默认实现，缺失才降级**（2026-11-10 用户裁决）
  - **裁决**：**默认按「有退市数据」执行实现**（动态股票池 + 退市收益契约）；只有在数据确实缺失时才进入降级路径
  - **判据**：有数据 → 动态池 + 退市收益生效，回测报告含「已校正」标记；无数据 → 降级路径被显式触发（warning + 报告标注 + 方向性声明）
  - **触发条件**：B-1 实施启动时检查数据契约；降级路径的触发条件为「`list_date`/`delist_date`/`delisting_return` 任一缺失」
  - **当前倾向**：S-A 默认 + S-B 配置化 + S-C 降级
  - **证据等级**：E1（本仓无退市文件，P1）+ A2/A3/A4

- **U-2 前视掩码是否修正**
  - **判据**：E2 探针证实 P5/P6 确为前视；确认修正后的结果变化方向可解释
  - **触发条件**：L0 探针完成
  - **当前倾向**：修正（L-A），但单独批次
  - **证据等级**：E3（P5/P6），待 E2

- **U-3 复权方向是否颠倒**
  - **判据**：用非 1 复权因子的真实样本，手工计算前/后复权并与 `get_adj_price` 比对
  - **触发条件**：L0 探针
  - **当前倾向**：按 A7 定义推断为颠倒，待 E2 证实
  - **证据等级**：E3（P7），待 E2

- **U-4 ST 阈值新规生效范围**
  - **判据**：确认数据覆盖期与板块（主板/创业板/科创板），以及 2026-07-06 前后是否需分段
  - **触发条件**：B-4 实施前
  - **当前倾向**：按日期段配置（U-A）
  - **证据等级**：E1（A12 官方媒体 + 本仓默认值）

- **U-5 「接口锁定」口径确认**
  - **判据**：用户确认是指「接口契约稳定性」还是「数据供应商接口锁定」
  - **触发条件**：Step 2 Review
  - **当前倾向**：前者（§0 口径）；后者已在 P16-P18 覆盖
  - **证据等级**：——

---

## 9. 参考文献

1. Shumway, T. (1997). *The Delisting Bias in CRSP Data*. Journal of Finance.（经行业文章转述，未直取原文）
2. Shumway, T., & Warther, V. A. (1999). *The Delisting Bias in CRSP's Nasdaq Data*. Journal of Finance.（同上）
3. Microsoft Qlib. *Point-in-Time Database*；*Data Layer*.
4. 上海证券交易所. *上海证券交易所交易规则（2026 年修订）*.
5. 中国证券监督管理委员会. *风险警示股票交易规则*（涨跌幅 5%）.
6. 新华网（2026-07-06）. *A 股交易新规今起实施：沪深主板风险警示股票涨跌幅限制由 5% 调整至 10%*.
7. 中国证券网. *股票涨跌幅 / 前复权与后复权定义*.
8. PEP 544. *Protocols: Structural subtyping (static duck typing)*.
9. Real Python. *Implementing Interfaces in Python: ABCs and Protocols*.
10. Pact. *Consumer-Driven Contract Testing — FAQ*.
11. 行业实践. *Contract Testing and Version Compatibility（N/N-1）*.
12. 行业实践. *Survivorship Bias in Backtesting / Point-in-Time Membership*.
13. arXiv（T3）. *Cross-Sectional Heterogeneity in LSTM Networks for Financial Time Series*（训练期统计量）.

---

## 10. Step 2 Review（独立 pass，2026-11-10）

- **执行时点**: Step 1 + §11 + §12 补充调研完稿、ADR-017 登记之后单独执行；与正文写入不同会话、不同模型基座（RULE-1 / RULE-4 / RULE-5 异构复审口径）
- **审查方式**: 重跑 E1 命令 + 重放 E2 探针 + 逐条 E3 抽检 + 计数矩阵 + 跨节一致性，不依赖正文自报

**E1 复核**:

| 断言 | 命令 | 结果 |
|------|------|------|
| 证据 commit 有效性 | `git rev-parse HEAD`；`git diff --stat 05af52f 2c34283 -- core filter tests` | HEAD=`2c34283`（docs-only 回填）；core/filter/tests **零 diff**，E3 引用绑 `@05af52f` 仍有效 |
| 工作区 | `git status --short` | 仅本批 4 个 docs 文件，无代码变更 |

**E2 探针重放（§11.11 三脚本，Python312 + `MPLBACKEND=Agg`）**:

| 探针 | 记载读数 | 重放读数 | 判定 |
|------|----------|----------|------|
| A 复权夹具 | `adj nunique=1`、min/max=1.0、0 列变动 | 同（shape 100×50） | ✅ |
| B 配置双定义 | 21/21 同名、0 独占、2 处默认漂移（`exclude_na_factors` True/False、`exclude_stock_prefixes` MISSING/False） | 同 | ✅ |
| C 协议符合性 | 8[] / 5[] / 8[] / 2[`process_single`] / 2[`combine_single`] / 4[`trade_log`] | 同 | ✅ |

**E3 抽检（7 处全部命中）**: `config.py:231-234`（0.095/0.048 阈值）、`universe_filter_clean.py:154-182`（当日 returns 判涨跌停）、`:164`（`st.shift(1)`，P12）、`:203-215`（`suspend.shift(-1)`，P6）、`engine_v2.py` 7 处 `get_adj_price`（346/391/438/529/608/669/757）、`data.py:444-456`（forward/backward 公式）、`config_v2.py:185`。

**计数矩阵**:

| 项 | 计数 | 位置 |
|----|------|------|
| 外部锚点 | A1-A16（§3）+ A17-A23（§11.0.1）+ A24-A41（§12.0）= **41** | ✅（F-R1 修复后） |
| 本仓事实 | P1-P20（§4）+ P21-P25（§11.7）= **25** | ✅ |
| 参考文献 | 1-13（§9）+ 14-23（§11.10）+ 24-41（§12.6）= **41**，连续无缺号 | ✅（F-R2 修复后） |
| 内部链接 | `RESEARCH_backtest_validation.md` / `PROGRESS.md` / `DECISIONS.md` 均存在 | ✅ |

**跨节一致性**: U-1「默认有退市数据实现 / 缺失才降级」在 §6.1 / §7 L3 / §8 / §11.1 四处口径一致；P21（口径耦合修正后）与 ADR-017「明确不做」一致；§11.4 与 §12.3.3 的创业板日期段修复后一致；§12.5 实施顺序（U-8→U-9→U-7→U-6）与 §3.14 执行顺序（P2 ST → P3/P4 复权 → P6 退市 → P7 接口）不冲突。

**发现 3 项（均已修复回写）**:

| ID | 等级 | 发现 | 修复 |
|----|------|------|------|
| **F-R1** | P2 | **锚点 A17-A23 悬空**：正文引用 A19（§11.7 P25）、A20/A21（§11.9 U-8），但全文档无定义（编号 A16 直跳 A24），断言链断裂 | 新增 §11.0.1 表补齐 7 个锚点定义（含文献映射）；F-R1 修复后计数矩阵 A=41 成立 |
| **F-R2** | P3 | **参考文献缺 14 号**（§9 止于 13、§11.10 起于 15）；且 §12.3.3 新引入的「创业板 2020-08-24 注册制 20%」制度日期无文献支撑 | §11.10 补录文献 14（深交所创业板注册制实施方案），并在 §12.3.3 注记引用（文献 14/17） |
| **F-R3** | P3 | **§11.4 规则矩阵创业板行缺日期段**（写为无条件 20%/20%），与 §12.3.3（10%/5% → 2020-08-24 起 20%）不一致 | §11.4 创业板行补「10%（2009-10-30 开市）→ 20%（2020-08-24 注册制起）」+ ST 侧 5%→20% |

**结论**: **P1 = 0；P2 = 1（F-R1）、P3 = 2（F-R2/F-R3），均已回写**；E1/E2/E3 复核全命中，计数连续，跨节口径一致。**P-012 Step 2 Review 通过**，进入 P0 决策门剩余项（U-6~U-9 确认、合并判定）。

---

## 11. Step 2 补充调研（2026-11-10 用户裁决后）

### 11.0 裁决记录

| ID | 用户裁决 | 实施含义 |
|----|----------|----------|
| **U-1** | **默认按「有退市数据」执行实现；没有才降级** | 动态股票池 + 退市收益为**默认路径**；数据缺失是异常分支，走显式降级 |
| **U-2** | 接受回测结果变化，**需显式拆解变化原因** | 修正必须附「分层归因报告」，净值差异 100% 可追溯到掩码/订单/成交 |
| **U-3** | 复权方向**深入调研**（社区案例、实务） | 本节 §11.3 给出 T1 官方公式与本仓比对结论 |
| **U-4** | ST 阈值**需要修正**（社区案例、解法） | 改为「板块 × ST × 日期段」规则表（§11.4） |
| **U-5** | 拆为两件事：**5a 契约稳定性排查** + **5b 供应商接口锁定** | §11.5 / §11.6 分别给出排查结果与方案 |

#### 11.0.1 补充外部锚点（A17-A23，2026-11-10 Step 2 Review 补定义）

> Step 2 补充调研引用了 A19 / A20 / A21 但未落定义（Step 2 Review F-R1）；本表补齐。编号按**引用时点语义**分配，与文献序号非严格一一对应（映射见「文献」列）。

| ID | 来源 | 等级 | 原文要点 | 文献 |
|----|------|------|----------|------|
| **A17** | Tushare 复权因子文档 | T1 | 前复权（qfq）= `当日收盘价 × 当日复权因子 / 最新复权因子`；后复权（hfq）= `当日收盘价 × 当日复权因子` | 15 |
| **A18** | Tushare 终止上市列表 | T1 | `get_terminated()` 返回 `code/name/oDate/tDate`，仅覆盖上交所 | 16 |
| **A19** | 证券时报（*ST鹏博 公告） | T1 | A 股退市整理期 **15 个交易日**；首日无涨跌幅限制，此后 10% | 22 |
| **A20** | 中国证监会上海监管局 | T1 | 2026-07-06 起：主板 ST 5%→10%；创业板/科创板 ST 20%；北交所 30% | 18 |
| **A21** | 央视网（2026-07-06） | T1 | A 股交易规则三大修订（与 A20 交叉印证） | 19 |
| **A22** | 深交所创业板规定 + 北交所交易规则 | T1 | 创业板 20%（2020-08-24 注册制起，此前 10%/ST 5%）；北交所 30% | 17 / 14 / 20 |
| **A23** | 深交所（英文）Trading Overview | T1 | ST 5%；IPO 首日无涨跌幅限制 | 21 |

### 11.1 U-1：退市数据与降级方案

**数据可得性**：

| 来源 | 字段 | 等级 |
|------|------|------|
| Tushare `get_terminated()` | `code` / `name` / `oDate`（上市日期）/ `tDate`（终止上市日期） | T1（官方文档） |
| Tushare Pro `stock_basic` | `list_date` / `delist_date` | T1（官方文档，字段名以实际接口为准） |
| 本仓本地 | **无任何退市/上市文件**（`data/test_ashare` 仅 7 个 pkl，`data/` 仅 `events.jsonl`） | E1/E2 |

**默认实现契约**（与 U-1 裁决一致）：

```text
list_date.pkl      # 列: stock, list_date
delist.pkl         # 列: stock, delist_date, delist_return(可选), delist_reason(可选)
```

- `stock_codes(t) = {s | list_date[s] <= t < delist_date[s]（或未退市）}`
- 退市当日/次日：按 `delist_return` 计入组合（A 股取退市整理期末收盘相对前收盘的收益；无该字段时按配置规则：`zero` / `last_close` / `custom`）
- 报告字段：`survivorship: "corrected"` + `n_delisted` + `n_listed`

**A 股退市实务锚点**：

- 退市整理期 **15 个交易日**；**首个交易日无涨跌幅限制**，此后 **10%**（`*ST鹏博` 公告、`*ST创兴` 公告）
- 退市整理期在风险警示板交易；摘牌后转老三板（流动性骤降）
- 因此 A 股不应照搬 CRSP 的 −30% 假设，应用**整理期实际跌幅**或保守的 `zero`

**无数据降级方案（S-C，仅异常分支）**：

1. **显式 warning**（不是 debug 日志）：`未找到 list_date/delist 数据，幸存者偏差未校正`
2. 报告字段：`survivorship: "uncorrected"` + `bias_direction: "overstated"`
3. **敏感性分析**（低成本、可执行）：剔除小盘/低价股复跑、缩短样本至近 3 年复跑、与「仅现存股票」基线对比
4. **禁止**：静默返回「已校正」；禁止用当前成分股冒充历史成分

### 11.2 U-2：回测结果变化的显式拆解

接受结果变化，但要求「变化可解释」。方法为**六层归因链**，每层输出差异集合与方向：

| 层 | 差异对象 | 度量 | 归因到 |
|----|----------|------|--------|
| L1 | `buyable` / `sellable` 掩码 | 变化单元格数、按日期/股票分布 | 规则/时点修正 |
| L2 | 可交易股票集合 | 每日入选/剔除列表 | L1 |
| L3 | 目标持仓 | 目标股数差、权重差 | L2 + 优化器 |
| L4 | 订单 | 新增/取消/数量变化 | L3 |
| L5 | 成交 | 成交价差 × 股数、未成交机会成本 | L4 + 撮合 |
| L6 | 净值 | 逐日净值差、总收益差、回撤差 | L1-L5 求和校验 |

**产物**：`change_report.json`（修正前/后逐日 diff + 归因摘要）+ 一页纸说明（每个变化点对应的规则条款）。

**凭证要求**：L6 的净值差异必须能被 L1-L5 解释（残差 < 1e-8）；不能解释的部分视为**未归因**，必须继续追查。

**外部参照**：LEAN 的 Statistics Comparator（逐统计对比期望值）提供了「哪些统计变了」；本方案在其上补「为什么变」。

### 11.3 U-3：复权方向深入调研

**E2 本地探针结果**：`data/test_ashare/stock_adj.pkl` 全为 **1.0**（`nunique=1`），**无法验证方向**；同时 `suspend≡0`、`industry≡1`、股票全 `000` 前缀 → 复权/停牌/行业/板块路径在夹具中**零覆盖**（P22）。

**T1 官方公式（Tushare 复权文档）**：

| 类型 | 公式 |
|------|------|
| 前复权（qfq） | `当日收盘价 × 当日复权因子 / 最新复权因子` |
| 后复权（hfq） | `当日收盘价 × 当日复权因子` |

- 复权因子为「**累计后复权因子**」（Tushare 文档转述）
- 美股接口文档另称 `close * adj_factor = 前复权收盘价`——说明**不同市场/数据源定义相反**，必须显式声明

**与本仓比对**：

| 本仓分支 | 实现 | 按 A 股定义实际是 | 结论 |
|----------|------|------------------|------|
| `forward`（默认） | `price * adj_factor` | **后复权（hfq）** | 名称与语义**颠倒** |
| `backward` | `price * adj_factor / adj_factor.iloc[-1]` | **前复权（qfq）** | 名称与语义**颠倒** |

**社区实务共识**：

1. **信号/指标/收益率**用**后复权**（历史数值不被新除权事件改写，可复现）
2. **成交价/成交金额/手数/涨跌停价**用**不复权**（真实可成交价格）；涨跌停**判定**以除权参考价为基准，复权收益是其近似
3. **前复权**仅用于展示（最新价不变、历史价被压缩），且会随新事件整体漂移

**本仓的连带问题（P21，2026-11-10 复核修正）**：`returns` 由 `cfg.adjustment_type`（默认 `forward`，实为后复权）计算（`data.py:396-407`），同时被 `_build_limit_masks` 用于涨跌停判定（`universe_filter_clean.py:154-182`）。**按「除权参考价」的定义，用复权收益判涨跌停本身是正确的**——除权日的复权收益已对齐除权参考价；真正的缺陷是**口径耦合**：同一个 `adjustment_type` 同时控制成交价、绩效收益与涨跌停判定，任一改动会静默改变三处语义。若按「收益改用不复权」修正，反而会在除权日（尤其 ST 5% 阈值）产生**假涨跌停**。

**修正方案（A-A′）**：

1. 重命名并校正：`forward` → `hfq`（`price*adj`）、`backward` → `qfq`（`price*adj/latest`）；保留旧名 **≥2 个 minor** 兼容期（`DeprecationWarning`，对齐 PDEP-17）
   - **Step 6 回写（2026-11-10，IMPL F-I1）**：`none` 亦作为旧名保留并映射 `raw`（`none → raw`）——本仓基线 `tests/test_adjustment.py` 有 9 处 `"none"` 用法，且本条修正方案第 2 点本就用 `adjustment="none"` 表示不复权；DESIGN §4.1/§7 已同步
2. 成交、估值、费用、手数统一走 `adjustment="none"`（新增 `trade_price_mode="raw"`，估值同口径）
3. 三处口径显式声明并**解耦**：`trade_price_mode="raw"`、`signal_price_mode="hfq"`、`return_price_mode="hfq"`、`limit_price_mode="hfq"`；**禁止**把收益/涨跌停口径设为 `raw`
4. 迁移期提供 `legacy_adjustment=True` 开关（恢复「复权价成交」旧路径），默认新口径

**验证（A-B′）**：构造 3 日含 10 送 10 的样本，断言：①`qfq` 末值 = 原始末值；②`hfq` 首值 = 原始首值；③`qfq/hfq` 比值恒定；④不复权收益在除权日出现 −50% 跳空、复权收益平滑；⑤**反例测试**：用不复权收益跑涨跌停掩码会在除权日产生假涨跌停，锁死不得回落 `raw`。

### 11.4 U-4：ST / 涨跌停阈值修正

**现行规则矩阵（T1 官方）**：

| 板块 | 普通股 | ST / *ST | 特殊 |
|------|--------|----------|------|
| 沪深主板 | 10% | **5%（≤2026-07-05）→ 10%（≥2026-07-06）** | IPO 首日无限制（主板首日 −36%~+44%） |
| 创业板 | **10%（2009-10-30 开市）→ 20%（2020-08-24 注册制起）** | **5%（≤2020-08-23）→ 20%（≥2020-08-24）** | IPO 前 5 日无限制（文献 14/17；Step 2 Review F-R3 补日期段） |
| 科创板 | 20% | **20%** | IPO 前 5 日无限制 |
| 北交所 | 30% | **30%** | IPO 首日无限制 |
| 退市整理期 | — | — | **首日无限制，此后 10%** |

**本仓现状与差距**：

- 默认 `0.095 / 0.048 / -0.095 / -0.048`，无板块、无日期段（P11）
- `st.shift(1)` 判阈值、当日 `st` 判掩码（P12）
- 无 IPO 前 5 日 / 退市整理期 / 复牌首日（P13）
- 夹具全 `000` 主板、`suspend≡0` → 20%/30%/5% 路径零覆盖（P22）

**社区解法（实务）**：

1. **规则表**而非常数：`(effective_from, effective_to, board, is_st) → ratio`；启动时校验区间不重叠、无空洞
2. **涨跌停价判定**：`limit_up_price = prev_close × (1 + ratio)`，用当日 `open/high/low` 与限价比较；避免用收盘收益阈值（对除权、四舍五入、ST 切换更稳健）
3. **ST 状态用当日**（盘前公告可知），不用 `shift(1)`
4. **特殊情形**用掩码白名单：IPO 前 5 日、退市整理首日、复牌首日 → 不应用涨跌停过滤

**修正方案（U-A′）**：

- 新增 `LimitRule` 表（默认内置上表），`UniverseFilterConfig` 移除 4 个常数阈值（或降为 deprecated）
- 板块由股票代码前缀推断：`300/301` 创业板、`688/689` 科创板、`8xx/4xx` 北交所、其余主板
- 单测覆盖：主板 ST 2026-07-05 / 2026-07-06 两侧、创业板 ST 20%、北交所 30%、IPO 前 5 日、退市整理首日

### 11.5 U-5a：接口契约稳定性排查

**E2 探针结果（2026-11-10，脚本见 §11.11，可重放）**：

| 协议 | 实现 | 协议成员数 | 类级缺失成员 | 判定 |
|------|------|-----------|--------------|------|
| `IDataManager` | `DataManager` | 8 | 无 | ✅ 符合 |
| `IUniverseFilter` | `UniverseFilter` | 5 | 无 | ✅ 符合 |
| `IPositionTracker` | `PositionTracker` | 8 | 无 | ✅ 符合（P-007 层 B 修复后） |
| `IFactorPipeline` | `FactorPipeline` | 2 | **`process_single`** | ❌ 不符合 |
| `IFactorCombiner` | `FactorCombiner` | 2 | **`combine_single`** | ❌ 不符合 |
| `IExecutionSimulator` | `ExecutionSimulator` | 4 | 类级无 `trade_log`（实例属性）；`execute_order` 签名不兼容 | ❌ 部分（V10 探针） |

> 探针按**类级成员名**扫描，不检查签名与实例属性；`ExecutionSimulator.trade_log` 为实例属性，mypy 可识别，但 P-007 层 B V10 已证实其 `execute_order` 签名与协议不兼容。

**配置双定义（E2）**：

| 项 | 结果 |
|----|------|
| 字段总数 | 两类的 21 个字段**全部同名** |
| 仅 A / 仅 B | 0 / 0 |
| 默认值漂移 | `exclude_na_factors`：`UniverseConfig=True` vs `UniverseFilterConfig=False`；`exclude_stock_prefixes`：前者无默认、后者 `False` |
| 影响 | `engine_v2.py:191` 直接把 `UniverseConfig` 传给期望 `UniverseFilterConfig` 的构造器；行为取决于**传入实例**的字段值，而不是接收类默认值——一旦某字段未显式赋值，两套默认值会给出不同结果 |

**契约双轨**：14 个 Protocol + 7 个 ABC（P14）；无 `@runtime_checkable`；无契约符合性测试（P19）。

**排查优先级**：

| 优先级 | 问题 | 证据 | 处置 |
|--------|------|------|------|
| **P0** | `UniverseConfig` / `UniverseFilterConfig` 双定义 + 默认值漂移 | E2 | 合并为单一 dataclass（或加 `from_backtest_config()` 转换 + 字段级单测） |
| **P0** | `FactorPipeline` / `FactorCombiner` 缺协议成员 | E2 | 补齐方法或收窄协议（`process_single`/`combine_single` 若无消费方则删除协议成员） |
| **P1** | `ExecutionSimulator.execute_order` 签名不兼容 | P-007 V10 | 统一签名（`side: OrderSide` vs `Any`） |
| **P1** | 无契约符合性测试 | E4 | 每个协议一套参数化断言，跑全部实现 + Mock |
| **P2** | 14 Protocol + 7 ABC 双轨 | E1 | Protocol 为唯一契约；ABC 降为 adapter 或删除 |
| **P2** | 无版本化 | E4 | `core/__api_version__` + SemVer + N/N-1 测试 |

### 11.6 U-5b：供应商接口锁定

**现状（P16-P18）**：

- 数据入口固定为「目录 + 文件名」：`close.pkl` / `open.pkl` / `high.pkl` / `low.pkl` / `stock_adj.pkl` / `suspend.pkl` / `industry.pkl`
- 字段 = DataFrame 列名；无 schema 版本、无 checksum、无数据来源元数据
- `DataManager`（V2）与 `DataLoaderV3`（V3）双实现，各自解析同一批 pkl

**社区实践**：

1. **Qlib**：`Data Handler` 基类 + `Data Loader`（`QlibDataLoader` / `QdbDataLoader` 共享字段解析），上层只依赖基类接口
2. **LEAN**：`IDataProvider` 抽象数据源，本地/云端实现可替换
3. **通用**：Provider / Adapter 模式 + schema 校验（pandera 式）+ 数据 manifest（来源/日期/checksum）

**方案（I-B′）**：

1. 新增 `DataProvider` Protocol：`load_price(kind) -> DataFrame`、`load_aux(kind) -> DataFrame | None`、`load_universe() -> UniverseSnapshot`
2. 现有 pkl 目录实现为 `PklDataProvider`；未来 Tushare/AKShare 实现为 `TushareDataProvider` / `AkshareDataProvider`
3. `schema_version` 与 `manifest.json`（source / fetched_at / rows / sha256）；缺失时 warning + 报告标注「数据版本未知」
4. `DataManager` 与 `DataLoaderV3` 都改为消费 `DataProvider`（消除双实现解析逻辑）

**降级**：无 manifest 时不能声明「可复现」，报告字段 `data_version: "unknown"`。

### 11.7 补充发现汇总（P21-P25）

| ID | 发现 | 证据 | 影响 |
|----|------|------|------|
| **P21** | 口径耦合：`returns` 由 `adjustment_type` 派生，同一开关同时控制成交价/绩效收益/涨跌停判定；**用复权收益判涨跌停本身正确**（除权日已对齐除权参考价），风险在于未来改成 `raw` 会在除权日产生假涨跌停 | E3 `data.py:396-407` + `universe_filter_clean.py:154-182`（@`05af52f`） | 中-高（P8 修复时必须同时锁定 `limit_price_mode=hfq`） |
| **P22** | 测试夹具复权/停牌/行业/板块零覆盖：`adj≡1`、`suspend≡0`、`industry≡1`、全 `000` 前缀 | E2（本次探针） | 高（修正后无回归网） |
| **P23** | 无板块感知：阈值不区分主板/创业板/科创板/北交所 | E3 `config.py:231-234` | 中-高 |
| **P24** | `st` 为 0/1 快照，无生效日期段，无法表达 2026-07-06 规则切换 | E3 `_build_st_mask` | 中 |
| **P25** | 无退市整理期处理（15 日、首日无涨跌幅、此后 10%） | E3 + A19/A26 | 中（与 U-1 联动） |

### 11.8 修订后的路线

| 阶段 | 内容 | 对应 |
|------|------|------|
| **L0 证实（2-3 天）** | 用**真实分红样本**验证复权方向（当前夹具 adj≡1 不可用）；前视两处未来数据扰动探针 | U-3 / U-2 |
| **L1 测试网（3-5 天）** | 夹具扩展（非 1 复权、停牌、ST、创业板/科创板/北交所代码）；复权恒等式、涨跌停规则表、契约符合性测试 | P22 / U-4 / U-5a |
| **L2 复权与掩码（1-2 周）** | A-A′ 复权校正 + L-A 掩码时点 + P21 价格口径分离；每项附六层归因报告 | U-2 / U-3 |
| **L3 ST 规则表（3-5 天）** | U-A′ 规则表 + 板块推断 + 特殊情形白名单 | U-4 |
| **L4 退市能力（默认路径）** | S-A/S-B 数据契约 + 动态池；缺失走 S-C 降级 | U-1 |
| **L5 接口治理（3-5 天）** | I-A/I-B 契约唯一化 + 符合性测试；I-B′ `DataProvider` 抽象 | U-5a / U-5b |

### 11.9 新增未决项

> **2026-11-10 补充**：以下四项已完成专项补充调研（外部锚点 A24-A41），结论与方案比较见 **§12**；`§12.5` 给出统一建议与实施顺序。**用户已按 §12.5 推荐确认通过（D-A / C-A / R-A / B-A）**。

- **U-6 退市数据落地形式**：本地 pkl（离线可复现）vs 运行时接 Tushare（依赖网络/token）
  - 判据：明确数据获取方式与更新频率；触发条件：L4 启动；当前倾向：本地 pkl + `scripts/` 生成脚本；证据等级：E1
  - **→ §12.1 结论**：D-A 本地快照（parquet + manifest）；依据 A24（Tushare 官方建议本地存储）
- **U-7 复权切换兼容期**：是否保留 `legacy_adjustment` 开关及期限
  - 判据：确认是否有外部消费方依赖旧口径；触发条件：L2 设计前；当前倾向：保留一个 minor 版本；证据等级：E3
  - **→ §12.2 结论**：C-A 双轨 ≥2 个 minor + 冻结基线对拍；依据 A32/A33/A34（三份官方弃用政策的下限）
- **U-8 ST 规则表维护方式**：内置常量 vs 配置文件 vs 数据文件
  - 判据：规则变更频率与谁维护；触发条件：L3 设计前；当前倾向：内置默认表 + 可覆盖配置文件；证据等级：E1（A20/A21）
  - **→ §12.3 结论**：R-A 内置不可变规则表 + `(board, is_st, t)` 唯一命中 fail-fast；依据 A36/A37/A38
- **U-9 `DataProvider` 抽象是否纳入本批**：与 P-004（数据层统一）重叠
  - 判据：与 P-004 的边界划分；触发条件：L5 设计前；当前倾向：先在 P-012 做 `DataProvider` 接口，具体数据源适配留给 P-004；证据等级：E3
  - **→ §12.4 结论**：B-A 只做端口 + 1 个适配器 + 契约测试，消费方迁移归 P-004；依据 A39/A40/A41

### 11.10 新增参考文献

14. 深圳证券交易所. *创业板改革并试点注册制实施方案*（2020-08-24 起涨跌幅限制 10% → 20%，含 ST；Step 2 Review F-R2 补录）.
15. Tushare. *复权因子与复权行情（qfq/hfq 公式）*.
16. Tushare. *终止上市股票列表（code/name/oDate/tDate）*.
17. 深圳证券交易所. *创业板交易特别规定*（20%；IPO 前 5 日无限制）.
18. 中国证监会上海监管局. *A 股交易新规 7 月 6 日起施行*（主板 ST 5%→10%；创业板/科创板 ST 20%；北交所 30%）.
19. 央视网（2026-07-06）. *A 股交易规则三大修订*.
20. 北京证券交易所. *北京证券交易所交易规则*（30%）.
21. 深圳证券交易所（英文）. *Trading Overview*（ST 5%；IPO 首日无限制）.
22. 证券时报. *退市整理期 15 个交易日、首日无涨跌幅、此后 10%*（*ST鹏博 公告）.
23. Microsoft Qlib. *Data Handler / Data Loader 基类与接口*.

### 11.11 E2 探针脚本（可重放）

运行口径：`cd f:\Coding\Factor_Trading_v3.0`；
`C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe <脚本>`

**A. 探测一：复权因子夹具覆盖（§11.3 / P22）**

```python
import numpy as np
import pandas as pd

close = pd.read_pickle(r"data/test_ashare/close.pkl")
adj = pd.read_pickle(r"data/test_ashare/stock_adj.pkl")

print("shape", close.shape, adj.shape)
print("adj nunique", int(adj.stack().nunique()))
print("adj min/max", float(adj.stack().min()), float(adj.stack().max()))

changed = (adj.diff().abs() > 1e-12).any()
print("columns with adj changes", int(changed.sum()))
if changed.any():
    col = adj.columns[np.argmax(changed.values)]
    s = adj[col].dropna()
    c = close[col].dropna()
    prod = (close[col] * adj[col]).dropna()
    print("close*adj ratio last", float((prod / prod.iloc[0]).iloc[-1]))
```

**B. 探测二：契约符合性与配置双定义（§11.5）**

```python
import dataclasses
import sys

sys.path.insert(0, r"f:\Coding\Factor_Trading_v3.0")

import pandas as pd

from core.config import UniverseConfig
from filter.universe_filter_clean import UniverseFilterConfig

a = {f.name: (f.type, f.default) for f in dataclasses.fields(UniverseConfig)}
b = {f.name: (f.type, f.default) for f in dataclasses.fields(UniverseFilterConfig)}

print("fields", len(a), len(b))
print("only UniverseConfig", sorted(set(a) - set(b)))
print("only UniverseFilterConfig", sorted(set(b) - set(a)))
diff_default = [
    (k, a[k][1], b[k][1]) for k in sorted(set(a) & set(b)) if repr(a[k][1]) != repr(b[k][1])
]
print("default differs", diff_default)

close = pd.read_pickle(r"data/test_ashare/close.pkl")
print("prefix counts", pd.Series([c[:3] for c in close.columns]).value_counts().to_dict())
print("suspend unique", pd.read_pickle(r"data/test_ashare/suspend.pkl").stack().unique()[:5])
print("industry unique", pd.read_pickle(r"data/test_ashare/industry.pkl").stack().unique()[:5])
```

> 探测二 B 只比配置；协议成员扫描见下 C（2026-11-10 复跑读数：8/8/8/2/2/4 全量吻合）。

**C. 探测三：协议成员符合性（§11.5 表）**

```python
import sys

sys.path.insert(0, r"f:\Coding\Factor_Trading_v3.0")

from core import interfaces as I
from core.data import DataManager
from core.tracker import PositionTracker
from core.execution import ExecutionSimulator
from core.factor import FactorPipeline, FactorCombiner
from filter.universe_filter_clean import UniverseFilter

pairs = [
    ("IDataManager", I.IDataManager, DataManager),
    ("IUniverseFilter", I.IUniverseFilter, UniverseFilter),
    ("IPositionTracker", I.IPositionTracker, PositionTracker),
    ("IFactorPipeline", I.IFactorPipeline, FactorPipeline),
    ("IFactorCombiner", I.IFactorCombiner, FactorCombiner),
    ("IExecutionSimulator", I.IExecutionSimulator, ExecutionSimulator),
]

for pname, proto, impl in pairs:
    members = [n for n in vars(proto) if not n.startswith("_")]
    missing = [m for m in members if m not in vars(impl)]
    print(pname, "|", impl.__name__, "|", len(members), "|", missing)
```

> 该扫描为**类级成员名**比对，不校验签名与实例属性：`ExecutionSimulator.trade_log` 为实例属性（mypy 可识别），`execute_order` 签名不兼容由 P-007 层 B V10 结论提供（见 §11.5 注）。

---

## 12. U-6~U-9 补充调研（2026-11-10）

> 本节回答 §11.9 的四个未决项。方法：外部检索以**官方文档/规范**优先（T1），工程实践次之（T2）；本仓事实沿用 §4 / §11.7，未新增探针、未改代码。

### 12.0 新增外部锚点（A24-A41）

| ID | 来源 | 等级 | 原文要点 | 用于 |
|----|------|------|----------|------|
| **A24** | Tushare `stock_basic` 文档（文献 24） | T1 | 输入 `list_status` 取 `L上市/D退市/P暂停上市/G过会未交易/UN未上市`；输出含 `list_date`、`delist_date`；单次上限 6000 行、2000 积分、50 次/分；官方明确「调取一次就可以拉取完，**建议保存到本地存储后使用**」 | U-6 |
| **A25** | Tushare `get_terminated()`（文献 25） | T1 | 返回 `code/name/oDate/tDate`，但「目前只有在上海证券交易所交易被终止的股票」——**覆盖不全** | U-6 |
| **A26** | AKShare 退市接口（文献 26） | T1 | `stock_info_sh_delist` / `stock_info_sz_delist` 直接取沪深交易所终止（暂停）上市名单 | U-6 |
| **A27** | AKShare 更新日志（文献 27） | T1 | 修复 `stock_zh_a_daily` 查询已退市股票（如 `sh600001`）报错：新浪仍提供其历史行情，`outstanding_share`/`turnover` 为空并告警 | U-6 |
| **A28** | Qlib Data Layer（文献 28） | T1 | 「Qlib defines **stock pool as stock list and their date ranges**」；`list_instruments` 返回带**时间跨度**的 dict | U-6 |
| **A29** | Zipline / norgatedata（文献 29） | T1 | 股票 `auto_close_date` 自动设为**最后报价日**；对已退市资产下单抛 `CannotOrderDelistedAsset`；bundle 宣称「**Survivorship bias-free** bundles」 | U-6 |
| **A30** | DVC 数据版本（文献 30） | T2 | 每个数据版本对应 Git tag + DVC 提交；`git checkout <tag> && dvc pull` 恢复**完全一致**的数据；内容寻址哈希 | U-6 |
| **A31** | Python `pickle` 文档（文献 31） | T1 | 「The `pickle` module **is not secure**. Only unpickle data you trust.」；恶意 pickle 可在反序列化时**执行任意代码**；建议改用 json 等安全格式 | U-6 |
| **A32** | PDEP-17（pandas，文献 32） | T1 | 弃用功能**至少保留 2 个 minor** 不变；首版 `DeprecationWarning`，最后 minor 升级 `FutureWarning`，下一 major 移除 | U-7 |
| **A33** | PEP 387（Python，文献 33） | T1 | 不兼容变更必须走弃用流程；按年发布 → 弃用期**至少 2 年** | U-7 |
| **A34** | NEP 23（NumPy，文献 34） | T1 | 不兼容 API 变更需**至少 2 个 release** 的弃用警告；警告须含弃用版本号与替代方案 | U-7 |
| **A35** | SemVer 2.0.0（文献 35） | T1 | 不兼容 API 变更**升 MAJOR**；向后兼容的新增升 MINOR | U-7 |
| **A36** | OMG DMN 1.5（文献 36） | T1 规范页 + T2 版本日期转述 | 决策表（decision table）作为**外部化、可版本化**的规则表达标准；DMN 1.0 于 2015 采用，1.5 于 2024-08 正式发布 | U-8 |
| **A37** | SCD Type 2 / PIT 存储（文献 37） | T2 | 每次变更**新增一行**而非覆盖，含 `effective_start_date` / `effective_end_date`；PIT 查询为 `start ≤ t AND (end IS NULL OR end > t)` 的**半开区间** | U-8 |
| **A38** | 规则版本不可变（文献 38） | T2 | 规则版本以**不可变记录**保存：进行中的评估继续用旧版本，新评估用新版本；保留执行日志与审计轨迹 | U-8 |
| **A39** | Cockburn · Hexagonal Architecture（文献 39） | T1 | 「Allow an application to equally be driven by users, programs, automated test or batch scripts, and to be developed and tested **in isolation from its eventual run-time devices and databases**」 | U-9 |
| **A40** | Qlib `DataLoader` 抽象（文献 40） | T1 | `load(instruments, start_time=None, end_time=None) -> DataFrame` 为抽象方法；DataHandler + Processor 负责加工，Dataset 负责组装 | U-9 |
| **A41** | QuantConnect LEAN（文献 41） | T1 | 引擎模块化，`config.json` 的 environments 切换插件与数据源；流式推进下「you can't access price data beyond the **Time Frontier**」 | U-9 |

---

### 12.1 U-6 退市数据落地形式

**问题拆解**：①数据从哪来；②以什么格式入仓；③多久刷新；④如何证明「同一 commit 可复现」。

#### 12.1.1 数据来源对比（全部 T1）

| 来源 | 覆盖范围 | 可用字段 | 限制 | 结论 |
|------|----------|----------|------|------|
| Tushare `stock_basic(list_status='D')` | 全市场 A 股（含退市） | `ts_code/symbol/name/market/list_date/delist_date/list_status` | 2000 积分；50 次/分；单次 ≤6000 行 | **首选**（字段最全，含 `market` 可分板块） |
| Tushare `get_terminated()` | **仅上交所** | `code/name/oDate/tDate` | 覆盖不全 | 仅作交叉校验 |
| AKShare `stock_info_sh_delist` / `stock_info_sz_delist` | 沪深两所 | 代码/名称/上市/终止日期 | 交易所页面结构变更风险 | **免 token 备选** |
| AKShare `stock_zh_a_daily` | 已退市个股历史行情（如 `sh600001`） | OHLCV | 无股本/换手数据 | 补**退市整理期价格** |

**两个关键事实**：

1. **退市名单 ≠ 退市收益**。`delist_date` 只回答「何时退出」；退市整理期的实际跌幅需从行情源补（A27 证明已退市个股行情仍可取）。取不到时，§11.1 的 `delist_return` 只能按 `zero` / `last_close` 规则兜底，并在报告标注 `delist_return_source: "rule"`。
2. **官方建议离线快照**。A24 原文「调取一次就可以拉取完，建议保存到本地存储后使用」——这是「本地产物 + 生成脚本」最直接的外部依据，而非运行时拉取。

#### 12.1.2 社区与框架做法

| 项目 | 做法 | 对本案的启示 |
|------|------|--------------|
| Qlib（A28） | 股票池 = 股票列表 + **日期区间**；`list_instruments` 返回带时间跨度的结构 | 退市股票天然以 `end_date` 表达，**不需要**在选股逻辑里写「退市特殊判断」 |
| Zipline（A29） | `auto_close_date` = 最后报价日；下单已退市资产直接抛异常 | 失败要**显式**（异常/告警），不能静默跳过 |
| norgatedata（A29） | bundle 以「survivorship bias-free」为卖点 | 数据契约本身就是能力声明 |
| DVC（A30） | Git tag ↔ 数据提交，内容寻址哈希 | 回测报告应记录数据 manifest 的 sha256，而非路径 |
| pickle（A31） | 官方声明不安全、可执行任意代码 | 新增数据格式**不用 pickle**；历史 pkl 保留只读兼容 |

#### 12.1.3 方案比较（7 维）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **D-A 本地快照 + 生成脚本（推荐）** | `scripts/fetch_universe.py` 产出 `list_date.parquet` / `delist.parquet` + `manifest.json`（source / fetched_at / rows / sha256 / schema_version）；回测**只读本地** | 低（1 天） | 高 | 低（定期重跑） | 高（纯增量文件） | 高 | 1 天 | 长期 |
| D-B 运行时接 Tushare | 回测启动时在线拉取 | 低 | 中 | 中（token/限频/网络） | **低**（离线不可复现、结果随拉取时点漂移） | 低 | 0.5 天 | 不可复现 |
| D-C 混合：本地为真源 + `--refresh` | 默认读本地；刷新是**显式命令** | 中（1.5 天） | 高 | 中 | 高 | 高 | 1.5 天 | 长期 |

**推荐**：**D-A**，并把 D-C 的在线分支收敛为「显式 `--refresh`」——**永不隐式联网**，否则同一 commit 的两次回测可能不同。

#### 12.1.4 契约与验收

承接 §11.1 的 `list_date.pkl` / `delist.pkl`，本节细化落盘格式：

```text
data/universe/
  list_date.parquet    # stock, list_date
  delist.parquet       # stock, delist_date, delist_return(可选), delist_reason(可选)
  manifest.json        # source, fetched_at, rows, sha256, schema_version
```

> **Step 8 回写（2026-11-10，IMPL F-I3）**：DESIGN/IMPL 将落盘格式定为 **CSV + JSON**（`list_date.csv` / `delist.csv` / `manifest.json`）——`pyarrow` 未在 `pyproject.toml` 的 `dependencies`/`dev` 声明，parquet 读写会使 CI 失败；字段语义不变，仅编码变化。§11.1 的 `.pkl` 与本节 `.parquet` 均为同一契约的早期表述，以 DESIGN §3.1/§6.1 为准。

**缺失语义（必须非静默）**：

| 缺失项 | 行为 | 报告字段 |
|--------|------|----------|
| `delist_date` 缺失 | 该股视为「截至样本末日未退市」 | `n_unknown_delist` |
| `list_date` 缺失 | 视为「样本首日已上市」 | `n_unknown_list` |
| `manifest.json` 缺失 | 允许运行，但不得声明可复现 | `data_version: "unknown"` |
| 退市收益缺失 | 按 `zero` / `last_close` 规则兜底 | `delist_return_source: "rule"` |

**验收 3 条**（可机械检查）：
1. 同一 commit + 同一 manifest，两台机器产出的文件 sha256 一致；
2. 退市股票在 `delist_date` 之后**不再**出现在 `stock_codes(t)`；
3. `manifest.json` 缺失时，报告必须出现 `data_version:"unknown"`（不得为空）。

---

### 12.2 U-7 复权切换兼容期

**问题拆解**：改口径必然改结果（用户已接受，U-2），但「旧调用方」需要一个可预期的过渡窗口；窗口多长、如何告警、何时移除。

#### 12.2.1 弃用期规范对比（全部 T1）

| 规范 | 弃用期长度 | 警告升级路径 | 移除时机 |
|------|-----------|--------------|----------|
| PEP 387（A33） | **≥ 2 年**（按年发布节奏推导） | `DeprecationWarning` | 弃用期结束后 |
| NEP 23（A34） | **≥ 2 个 release** | 警告须含「弃用版本号 + 替代方案」 | 下一 major |
| PDEP-17（A32） | **≥ 2 个 minor** | 首版 `DeprecationWarning` → 最后 minor 升 `FutureWarning` | 下一 major |
| SemVer（A35） | — | — | 不兼容变更**升 MAJOR** |

三份独立规范收敛到同一量级：**「至少两个发布周期」是行业下限**，「保留 3 个月」这类无事件锚定的表述不可验证。

#### 12.2.2 方案比较（7 维）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **C-A 双轨一个 minor 周期（推荐）** | 默认新口径；`legacy_adjustment=True` 走旧公式；发 `DeprecationWarning`；下一 minor 升 `FutureWarning` 后移除 | 低-中（2 天） | 高 | 低 | 高 | 高 | 2 天 | 长期 |
| C-B 无兼容期直接切换 | 立即改默认 | 低（0.5 天） | 中 | 低 | **低**（下游静默出错） | 低 | 省事 | 隐性回归 |
| C-C 长期双轨 | 永久保留两套口径 | 中 | 低 | **高**（双份测试/文档/报告口径） | 高 | 低 | 2 天 | 技术债累积 |

**推荐**：**C-A**。理由：① 与 A32-A34 的下限一致；② 本仓是库形态（`core.data.get_adj_price` 被引擎/因子/过滤多处调用），静默改语义的风险高于多维护一个分支。

#### 12.2.3 兼容期的四条硬约束

1. **默认值**：`legacy_adjustment=False`（新口径默认），旧口径必须显式打开；
2. **告警文案**：含弃用版本、替代参数名、计划移除版本（对齐 A34 的「弃用版本号 + 替代方案」）；
3. **旧路径等价性**：`legacy_adjustment=True` 的输出必须与切换前的**冻结基线逐值相等**（含 NaN 位置，`rtol=0`）——否则「兼容」只是名义；
4. **报告可审计**：回测报告写入 `adjustment_mode`（`qfq`/`hfq`/`raw`/`legacy`）与 `legacy_adjustment` 布尔值。

> 兼容期长度按**版本事件**计（minor 数），不按自然月计。本项目 `pyproject.toml` 已声明 `version = "3.0.0"`（E1），但尚无发布节奏与 tag 策略；故以「P-012 之后的两个批次（minor）」折算，并在 DESIGN 中写明终止条件。

---

### 12.3 U-8 ST 规则表维护方式

**问题拆解**：A 股涨跌停规则随板块、ST 状态、日期段变化（§11.4 矩阵），规则本体放在哪里、谁维护、如何防止「漏板块静默回落默认值」。

#### 12.3.1 规则表达四案

| 方案 | 形态 | 变更成本 | 可审计性 | 适用场景 |
|------|------|----------|----------|----------|
| **R-A 内置不可变规则表（推荐）** | Python 常量元组：`Rule(board, is_st, effective_from, effective_to, up, down)` | 改代码 + 单测 + 评审 | **强**（随 Git diff/PR） | 规则条目少、年变更 ~1 次 |
| R-B 外部 YAML/TOML | 启动加载 + schema 校验 + 版本号 | 改配置（免发版） | 中（需校验与来源记录） | 非开发者需维护 |
| R-C 数据文件（parquet/csv） | 与行情同目录管理 | 改数据 | **弱**（易被刷新脚本误覆盖、无 diff） | 规则极多（逐股/逐日） |
| R-D 规则引擎 / DMN | OMG DMN 决策表（A36） | 高（引入引擎） | 强 | 多市场、多产品线 |

**外部依据**：
- DMN 1.5（A36）证明「决策表外部化 + 版本化」是成熟标准，但其收益随规则规模增长；本仓当前规则 <10 条，**引入 DMN 属过度设计**；
- SCD Type 2（A37）给出正确的**时间表达**：半开区间 `[effective_from, effective_to)`，PIT 查询 `start ≤ t AND (end IS NULL OR end > t)`；
- 规则版本以**不可变记录**保存（A38）：历史回测用旧版本，新回测用新版本，二者可并存。

#### 12.3.2 方案比较（7 维）

| 方案 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|
| **R-A（推荐）** | 低（1 天） | 高 | 低 | 高 | 高 | 1 天 | 长期 |
| R-B | 中（2 天） | 中 | 中 | 高 | 中 | 2 天 | 需守护配置漂移 |
| R-C | 中 | 低 | 高 | 中 | 低 | 2 天 | 数据/规则混管 |
| R-D | 高（1 周+） | 中 | 中 | 低（新依赖） | 中 | 1 周 | 过度设计 |

#### 12.3.3 推荐结构（R-A）

```python
RULESET_VERSION = "cn_a_2026_07"

# (board, is_st, effective_from, effective_to, limit_up, limit_down)
LIMIT_RULES = (
    ("main", False, "1996-12-16", None,         0.10, -0.10),
    ("main", True,  "1998-04-22", "2026-07-05", 0.05, -0.05),
    ("main", True,  "2026-07-06", None,         0.10, -0.10),
    ("gem",  False, "2009-10-30", "2020-08-23", 0.10, -0.10),
    ("gem",  False, "2020-08-24", None,         0.20, -0.20),
    ("gem",  True,  "2009-10-30", "2020-08-23", 0.05, -0.05),
    ("gem",  True,  "2020-08-24", None,         0.20, -0.20),
    ("star", False, "2019-07-22", None,         0.20, -0.20),
    ("star", True,  "2019-07-22", None,         0.20, -0.20),
    ("bse",  False, "2021-11-15", None,         0.30, -0.30),
    ("bse",  True,  "2021-11-15", None,         0.30, -0.30),
)
```

> 表内 `effective_from` 取制度生效日：主板涨跌停 1996-12-16、ST 特别处理 1998-04-22、创业板开市 2009-10-30、创业板注册制 20% 自 2020-08-24（文献 14/17）、科创板开市 2019-07-22、北交所开市 2021-11-15。`star`/`bse` 的 `is_st=True` 行用于保证查找闭合（两板是否设 ST 标识以交易所规则为准），不代表独立规则。

**查找规则**：按 `(board, is_st, t)` 过滤，命中数必须 **恰好 1**；命中 0 或多条 → **fail-fast 抛异常**，禁止回落到 10% 默认值（这正是当前 P11/P23 的失效模式）。

**维护流程**：
1. 规则变更 = 新增一条 `Rule` + 修改上一条的 `effective_to`（**不覆盖历史**）；
2. `RULESET_VERSION` 递增，并写入回测报告与 `change_report.json`；
3. 单测覆盖每条规则的 `effective_from - 1 / effective_from / effective_to / effective_to + 1` 四个边界日；
4. 特殊情形（IPO 前 5 日、退市整理首日、复牌首日）以**显式白名单**表达，不塞进主表。

**何时升级到 R-B/R-D**：出现「非开发者维护规则」或「多市场（港股/美股）并行」时再升级；升级前 R-A 的元组可直接导出为 YAML，迁移成本可控。

---

### 12.4 U-9 `DataProvider` 与 P-004 边界

**问题拆解**：§11.6 提出 `DataProvider` Protocol，但 P-004（TD-1 数据层统一）已覆盖「DataManager → DataLoaderV3 / Provider」。同一块地，两批都做会重复且互相冲突。

#### 12.4.1 外部锚点

- **端口-适配器（A39）**：应用核心只依赖**端口**，运行时设备/数据库由**适配器**注入；核心可脱离真实数据库做自动化回归测试。这正是 `DataProvider` 的定位。
- **Qlib（A40）**：`DataLoader.load(instruments, start_time, end_time) -> DataFrame` 是抽象；`DataHandler`/`Processor`/`Dataset` 分层，数据源与加工解耦。
- **LEAN（A41）**：引擎完全模块化，`config.json` 的 environments 切换数据源；流式推进保证「不能访问 Time Frontier 之后的数据」——与本批前视修正同源。

#### 12.4.2 方案比较（7 维）

| 方案 | 内容 | 成本 | 收益 | 维护 | 兼容 | 升级 | 短期 | 长期 |
|------|------|------|------|------|------|------|------|------|
| **B-A 只做端口 + 1 个适配器（推荐）** | P-012 定义 `DataProvider` Protocol + `PklDataProvider` + 契约测试；**不迁移** DataManager/DataLoaderV3 的消费方 | 低（2 天） | 中-高 | 低 | **高**（纯增量） | 高 | 2 天 | 长期 |
| B-B 本批完成数据层统一 | 两套实现都改为消费 provider，删除重复解析 | 高（2 周+） | 高 | 中 | **低**（大面积改动） | 中 | 2 周+ | 与 P-004 重复 |
| B-C 全部留给 P-004 | 本批只记录缺口 | 0 | 低 | — | 高 | 低 | 0 | 退回原状 |

**推荐**：**B-A**。理由：P-012 的目标是「契约可锁定、实现可替换、可验证」，端口 + 一个适配器 + 契约测试即可达成；真正的消费方迁移属于 P-004，混入本批会让偏差修正的**结果差异无法归因**（与 §11.2 六层归因直接冲突）。

#### 12.4.3 边界规则（写入 DESIGN，避免两批打架）

| 事项 | P-012 | P-004 |
|------|-------|-------|
| `DataProvider` Protocol 定义 | ✅ 唯一真源 | 只消费，不重定义 |
| `PklDataProvider` 适配器 | ✅ | 可保留或替换为其他实现 |
| `manifest` / `schema_version` 契约 | ✅ | 继承 |
| `DataManager` ↔ `DataLoaderV3` 合并 | ❌ | ✅ |
| 消费方迁移（engine / factor / filter） | ❌ | ✅ |
| 删除旧实现 | ❌ | ✅ |

**验收**：`DataProvider` 的契约测试对 `PklDataProvider` 与一个 `MockDataProvider` 同时通过；不触碰 `core/data.py` 与 `core/data_v3.py` 的现有调用路径。

---

### 12.5 统一建议与实施顺序

> **裁决（2026-11-10 用户确认）**：U-6→D-A、U-7→C-A、U-8→R-A、U-9→B-A **全部通过**；进入 [DESIGN_p012_bias_interface.md](DESIGN_p012_bias_interface.md)。

| 未决项 | 推荐 | 依赖 | 工作量 | 判断错误的后果 |
|--------|------|------|--------|----------------|
| **U-6** | D-A 本地快照 + 生成脚本 + manifest | 无（可与 L4 并行） | 1 天 | 若选修运行时拉取 → 回测不可复现 |
| **U-7** | C-A 双轨一个周期 + 冻结基线对拍 | U-3 复权修正 | 2 天 | 若选无兼容期 → 下游静默用错口径 |
| **U-8** | R-A 内置不可变规则表 + fail-fast 查找 | U-4 规则矩阵 | 1 天 | 若选数据文件 → 被行情刷新覆盖 |
| **U-9** | B-A 端口 + 1 适配器 + 契约测试 | 无 | 2 天 | 若选 B-B → 与 P-004 重复且归因失效 |

**实施顺序**：**U-8 → U-9 → U-7 → U-6**。
- U-8 无数据依赖、可立即做，且能消除 P11/P23 的失效模式；
- U-9 纯增量，不改变任何现有结果；
- U-7 依赖 U-3 的复权修正落地（否则没有「旧口径」可兼容）；
- U-6 依赖数据获取脚本，放在最后避免阻塞其余三项。

**共性设计约束**（横跨四项）：
1. 一切「缺失」必须**显式可见**（报告字段 / warning / fail-fast），禁止静默默认值；
2. 一切「时点相关」表达用**半开区间** `[from, to)`，禁止闭区间（A37）；
3. 一切「版本相关」产物写入报告（`RULESET_VERSION` / `data_version` / `adjustment_mode`），使回测结果可追溯到规则与数据版本。

---

### 12.6 新增参考文献（24-41）

24. Tushare. *股票基础信息 `stock_basic`（list_status / list_date / delist_date）*. https://tushare.pro/document/2?doc_id=25
25. Tushare（旧版）. *终止上市股票列表 `get_terminated`（仅上交所）*. http://tushare.org/classifying.html
26. AKShare. *股票数据：终止（暂停）上市 `stock_info_sh_delist` / `stock_info_sz_delist`*. https://akshare.akfamily.xyz/data/stock/stock.html
27. AKShare. *更新日志：`stock_zh_a_daily` 支持查询已退市股票*. https://akshare.akfamily.xyz/changelog.html
28. Microsoft Qlib. *Data Layer：股票池 = 股票列表 + 日期区间*. https://qlib.readthedocs.io/en/latest/component/data.html
29. zipline-norgatedata. *Survivorship bias-free bundles / `auto_close_date`*. https://pypi.org/project/zipline-norgatedata/1.1.35/
30. DVC. *End-to-end lineage：数据版本与 Git tag 绑定、内容寻址*. https://dvc.org/blog/end-to-end-lineage-with-dvc-and-amazon-sagemaker-ai-mlflow-apps/
31. Python Software Foundation. *`pickle` — Python object serialization（安全警告）*. https://docs.python.org/3/library/pickle.html
32. pandas. *PDEP-17：Backwards compatibility and deprecation policy*. https://pandas.pydata.org/pdeps/0017-backwards-compatibility-and-deprecation-policy.html
33. Python Software Foundation. *PEP 387 — Backwards Compatibility Policy*. https://peps.python.org/pep-0387/
34. NumPy. *NEP 23 — Backwards compatibility and deprecation policy*. https://numpy.org/neps/nep-0023-backwards-compatibility.html
35. SemVer. *Semantic Versioning 2.0.0*. https://semver.org/
36. OMG. *Decision Model and Notation (DMN) 1.5*. https://www.omg.org/spec/DMN/
37. Swoopr. *Point-in-Time Storage and Historical Replay（SCD Type 2 半开区间查询）*. https://www.getswoopr.com/trading-technology/market-data-engineering/point-in-time-storage-and-historical-replay/
38. Nected. *Rule Engine Design Pattern：规则版本不可变 + 审计轨迹*. https://www.nected.ai/blog/rules-engine-design-pattern
39. A. Cockburn. *Hexagonal Architecture (Ports and Adapters)*. https://alistair.cockburn.us/hexagonal-architecture
40. Microsoft Qlib. *DataLoader 抽象接口 `load(instruments, start_time, end_time)`*. https://qlib.readthedocs.io/en/latest/component/data.html
41. QuantConnect. *LEAN Algorithm Engine（模块化 + Time Frontier）*. https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/algorithm-engine

