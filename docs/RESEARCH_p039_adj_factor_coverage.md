# RESEARCH：P-039 adj_factor 日期覆盖缺陷修复（U-P038-2 承接）

> **批次**: P-039 · **Step 1 调研** · 日期 2026-11-17 · 来源日期 2026-11-17（读取日）
> **判档**: **T1**（Layer-1：改动落 `core/data.py`；判档规则 1 —— 路径 ∩ `{scripts, tests, tools, .github, .pre-commit-config}` ≠ ∅）
> **作者基座**: DeepSeek-V4.1-Flash（Step 2 Review 须异构，RULE-5；复审会话须先自报基座，无法证实则登记 U-P039-x 而非默认异构）
> **上游台账**: U-P038-2（P-038 实跑发现，P1）
> **代码证据时点**: HEAD `f5ea333`
> **前置批次**: [P-038](../docs/PROGRESS.md) §3.43（7 脚本实跑矩阵，附带发现本缺陷）

---

## 1. 批次目标与取证问题

| # | 问题 | 出口 |
|---|------|------|
| Q1 | 现网失败的确切形态与影响链？ | §3（E1 实跑）+ §4（影响面） |
| Q2 | `adj_factor` 的日期覆盖实况是什么？缺失是随机还是结构性？ | §2（E1 探针，五种 price type 对照） |
| Q3 | 缺失日应当如何填充？ffill / bfill / NaN / 不填充 各自的后果？ | §5（E2 探针四方对比） |
| Q4 | 修复边界应只覆盖 `adj_factor` 还是全部 price type？ | §6（方案矩阵 + 被拒理由） |
| Q5 | 修复会不会改变既有基线（golden / 760 测试）？ | §7（夹具覆盖核查） |

---

## 2. 数据实况（E1，`%TEMP%\p039_coverage_probe.py` / `p039_probe2.py` / `p039_probe3.py`）

### 2.1 五种 price type 的日期与列覆盖

| kind | shape | index | 与 `close` 日期差集 | 列覆盖 |
|------|-------|-------|--------------------|--------|
| `close` | (1475, 5688) | object(str) | —（基准） | — |
| `open` | (1475, 5688) | object(str) | **0** | 一致 |
| `high` | (1475, 5688) | object(str) | **0** | 一致 |
| `low` | (1475, 5688) | object(str) | **0** | 一致 |
| **`adj_factor`** | **(1394, 5691)** | object(str) | **缺 81 日**、多 0 日 | adj ⊃ close（缺列 **0**，多 3 列） |

**结论**：只有 `adj_factor` 存在日期缺口；`open/high/low` 与 `close` 完全同源（这也解释了为何 `.loc` 在其他四个 kind 上从不失败）。

### 2.2 81 个缺失日的分布（RULE-2 统计溯源）

按年份：2020 **9** / 2021 **8** / 2022 **10** / 2023 **16** / 2024 **31** / 2025 **7** = **81** ✅

首 5 日：`2020-01-10` / `2020-02-03` / `2020-02-19` / `2020-02-20` / `2020-02-25`
末 5 日：`2025-02-12` / `2025-02-18` / `2025-03-12` / `2025-04-07` / `2025-04-10`

**形态**：**随机分散**（非连续段落、非集中在数据首尾）→ 属上游导出时逐日缺失，不是「窗口截断」问题。
交易窗口 `2020-01-23..2026-02-09` 内 **80** 日（剔除 `2020-01-10`，早于窗口起点）。

### 2.3 复权因子的数值语义（决定填充方式的唯一依据）

| 列 | 值变化次数 / 行数 |
|----|------------------|
| `000001` | **12 / 1394** |
| `000002` | **8 / 1394** |
| `000004` | **3 / 1394** |

复权因子是**累计比率**，仅在除权除息日跳变，日间恒定 → **缺失日应前向填充（ffill）**，这与除权语义严格一致（无除权日则因子不变）。

### 2.4 NaN 结构（决定 ffill 是否会污染未上市期）

| 指标 | 读数 |
|------|------|
| `close` 全表 NaN 比例 | **14.1%**（未上市 / 已退市） |
| `adj` reindex 到 close 轴后：全 NaN 行 | **81** |
| 同上：NaN 单元格 | 1,463,481 |
| **`adj` 缺失但 `close` 有值** | **403,853（4.81%）** ← 真实影响面 |
| `ffill` 后：全 NaN 行 | **0** |
| `ffill` 后：NaN 单元格 | 931,013（全部与 `close` 同步的未上市期） |
| **`ffill` 后「adj 缺但 close 有值」** | **0** ← ffill 完全修复 |
| `ffill+bfill` 后：NaN 单元格 | 0（**但 bfill 会把上市首日因子回填到上市前 → 污染，禁止**） |

**结论**：`ffill` 是唯一同时满足「补齐 4.81% 真实缺口」与「不污染未上市期」的填充方式。

---

## 3. 现网失败链（E1，实跑逐字）

```
examples/run_single_backtest.py L60  engine.setup()
  → core/engine_v2.py L242        self._precompute_factors()
  → core/engine_v2.py L220        self.universe.build_masks()
  → filter/universe_filter_clean.py L210  close / adj_factor / open
  → core/data.py L156             self._load_price_data("adj_factor")
  → core/data.py L302             data = data.loc[self._trade_dates]
  → KeyError: "None of [DatetimeIndex([...])] are in the [index]"
  → logger.error("加载adj_factor数据失败: ...")  →  raise
  → filter/universe_filter_clean.py  except → 返回**全 True 掩码**
  → **涨跌停过滤静默跳过**（回测允许涨跌停日成交）
```

**双重损坏**：
1. **涨跌停掩码失效**（本批主症状）：`_build_limit_masks` 的 `except (FileNotFoundError, ValueError, KeyError)` 把 KeyError 当作「数据缺失」降级为不限制；
2. **复权价路径同时不可用**：`get_adj_price`（L503 → L517 `price_data * self.adj_factor`）走同一加载器，任何 `hfq/qfq` 口径都会抛 KeyError。

---

## 4. 影响面（E1，调用图）

| 层 | 位置 | 说明 |
|----|------|------|
| 加载器 | `core/data.py:302` | **唯一缺陷点**（`.loc` 严格索引） |
| 价格属性 | `core/data.py:136/141/146/151/156` | 五个 property 共用该加载器 |
| 复权计算 | `core/data.py:503`（`get_adj_price`）/ `:673` | `price * adj` 路径 |
| 引擎 V2 | `core/engine_v2.py:391-392` | `get_adj_price(kind, adjustment_type)` |
| 引擎（多智能体） | `agents/agent_framework.py:972/1339-1342/1440` | 4 处 `get_adj_price` |
| 策略引擎 | `agents/multi_strategy_engine.py:209` | 1 处 |
| 涨跌停掩码 | `filter/universe_filter_clean.py:210`（经 `build_limit_prices`） | 下游容错已具备（见 §5.2） |

**触发条件**：任何 `adj_factor` 日期覆盖 < `close` 日期覆盖的数据集（当前真实数据 100% 触发）。合成夹具（全 1.0 全日期）不触发。

---

## 5. 下游容错现状（决定修复范围）

### 5.1 `build_limit_prices` 已是 reindex 口径

[filter/limit_rules.py:145](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L145-L148)：

```python
adj = adj_factor.reindex(index=close.index, columns=close.columns)
safe_adj = adj.replace(0, np.nan)
ref = close.shift(1) * adj.shift(1) / safe_adj
ref = ref.fillna(close.shift(1))
```

→ 下游**已按 reindex 语义编写**，且 NaN 时回退 `close.shift(1)`（不限制）。**上游只要不抛异常并返回对齐的 adj 即可**，无需改动 filter。

### 5.2 `_load_and_align_data` 已有同类安全写法

[core/data.py:437-458](file:///f:/Coding/Factor_Trading_v3.0/core/data.py#L437-L458) 注释逐字：「使用 reindex 而不是 loc，避免 KeyError」「价格数据用 0 填充，因子数据保持 NaN 以区分缺失」。

→ 同文件内已有**明确的口径先例**；`_load_price_data` 是唯一未遵循者（缺陷性质：实现漂移，非设计分歧）。

---

## 6. 方案矩阵

| 方案 | 内容 | 代价 | 裁决 |
|------|------|------|------|
| **M-A 只修 `adj_factor`（reindex + ffill）** | `_load_price_data` 内：`adj_factor` 走 `reindex` + `ffill`，其余 kind 保持 `.loc` | 1 处分支 + 3 行 | **推荐**（见 §6.1） |
| M-B 全 kind 改 `reindex` | 五个 kind 统一 `data.reindex(self._trade_dates)` | 1 行 | **拒绝**：close 缺日将从「显式 KeyError」变「静默 NaN」，引入新静默路径（违反 P-025/P-026 治理纪律）；且 `open/high/low` 实测 0 缺口，无收益 |
| M-C 只在 `UniverseFilter` 容错 | 在 filter 侧吞掉 KeyError 并用 reindex | 1 处 | **拒绝**：`get_adj_price` 仍抛 KeyError（复权路径损坏未修）；治标不治本 |
| M-D reindex 不填充 | 只换 `.loc` → `reindex` | 1 行 | **拒绝**：4.81% 真实缺口变 NaN → `hfq` 价格 NaN → `_calculate_returns` 出现 NaN 段 → 优化器协方差污染（比现状更糟） |
| M-E reindex + ffill + bfill | 双向填充 | 2 行 | **拒绝**：bfill 把上市首日因子回填至上市前 → 未上市期出现虚假复权价（污染 14.1% 的 NaN 结构） |
| M-F 数据侧重导出 | 由用户在数据源补齐 `stock_adj.pkl` | 0 代码 | **拒绝为本批方案**（不在仓内、不可复现、不解决通用性）；但可作为并行建议登记 |

### 6.1 推荐方案 M-A 的精确语义（**Step 1 自查订正，见 §12**）

```python
if self._trade_dates is not None:
    if price_type == "adj_factor":
        # 复权因子在除权日之间恒定（探针：000001 仅 12 次跳变 / 1394 行）。
        # 三段式：并集对齐（创建缺失行）→ ffill（含窗口外前值）→ 回裁窗口
        window = self._trade_dates
        data = data.reindex(data.index.union(window)).ffill().reindex(window)
    else:
        data = data.loc[self._trade_dates]
```

**四条硬约束**：
1. **三段式顺序不可简化为两段**（F-S1-P039-1 实测）：`ffill()` 只对**已存在的行**填充、不创建缺失行；`reindex→ffill` 与 `ffill→reindex` 在窗口首日缺口时**均为 NaN**，只有 `reindex(union) → ffill → reindex(window)` 能取到窗口外前值（实测 `[1.0, 1.1, 1.2]` vs 两者 `[NaN, 1.1, 1.2]`）；
2. 只对 `adj_factor` 生效，其余 kind 保持 `.loc`（不引入新静默路径）；
3. **不加 `bfill`**（会污染未上市期，§2.4）；
4. 补偿天数须**可观测**（`logger.info` 记录实际填充行数），符合 P-026/P-029 静默失败治理纪律。

---

## 7. 基线影响（E1 读码）

| 面 | 结论 |
|----|------|
| golden 13 | **零影响**：夹具 [tests/_synth_fixture.py:74](file:///f:/Coding/Factor_Trading_v3.0/tests/_synth_fixture.py#L74) 生成**全日期全覆盖**的 `stock_adj.pkl`（`np.full((n_dates, n_stocks), adj)`），无缺日 |
| pytest 760 | 预期不变（无测试构造缺日 adj）；**须实测确认** |
| mypy 12 面 | 预期 0 新增（分支为 `price_type` 字符串比较，`data` 仍 `pd.DataFrame`） |
| black 121 | 预期不变 |
| 公开签名 | `_load_price_data` 为私有方法，签名零变更 |

---

## 8. 行为变更清单（预计 1 项）

| # | 位置 | 现网 | 修复后 | 性质 |
|---|------|------|--------|------|
| **C1** | `core/data.py:302` | `adj_factor` 缺日 → `KeyError` → 加载失败 → **涨跌停过滤跳过 + 复权价不可用** | `adj_factor` 缺日 → ffill 补齐 → 加载成功 → **涨跌停过滤生效 + 复权价正常** | **缺陷修复（P1）**：恢复 P-012 D4 掩码语义；对合成数据（无缺日）**逐值等价** |

**零行为变更面**：`close/open/high/low` 四个 kind 路径逐字不变（同一 `.loc` 分支）；合成夹具下 `ffill().reindex()` 与 `.loc` 结果逐值相等（无缺日时 ffill 是恒等变换）。

---

## 9. 风险、未决与观察

| ID | 类型 | 内容 | 处置 |
|----|------|------|------|
| **R-P039-1** | 风险 | `ffill` 对 `object` 索引数据是否生效需实测（`data.index` 在 reindex 前为 str，ffill 按行序，与索引类型无关） | Step 9 探针留证 |
| **R-P039-2** | 风险 | 若窗口首日落在缺失日且窗口外无前值（数据首日即缺），三段式后仍 NaN | 实测数据首日 `2020-01-02` 存在、窗口首日 `2020-01-23` 也存在；极端场景留 NaN，下游 `build_limit_prices` L148 已回退 prev_close |
| **R-P039-3** | 风险 | 内存与耗时：三段式 `reindex(union)` 产生全量索引副本 | **实测（Step 2 复审）**：窗口 1460 日 `shape=(1460, 5691)`、全 NaN 行 **0**、耗时 **0.18s**、内存 **≈66 MB** → 可接受 |
| **R-P039-4** | 风险 | 真实数据上 `<NA>` 与 `np.nan` 混用可能导致 `ffill` 不填充 | 实测 dtype 为 float64（非 nullable），无此问题 |
| U-P039-1 | 未决 | 上游 `stock_adj.pkl` 81 日缺失的生成原因（数据导出链路） | 登记；修复后在本仓内**不再可见**（ffill 吸收），但数据源仍缺 |
| **U-P039-2** | 未决 | **列维度同型严格索引**：[core/data.py:306](file:///f:/Coding/Factor_Trading_v3.0/core/data.py) `data = data[self._stock_codes]` 在 adj 缺 close 列时同样 KeyError（Step 2 复审实测 `KeyError: "['000001'] not in index"`）；当前真实数据 adj 缺列 **0** 故未触发 | 登记（条件触发：出现缺列数据集）；本批不扩做（改列对齐会引入缺列→NaN 的新静默路径） |
| O-P039-1 | 观察 | `open/high/low` 与 `close` 日期完全一致（同批次导出），故只有 adj 暴露问题 | 登记 |
| O-P039-2 | 观察 | `adj_factor` property 不主动触发 `_load_basic_data`；首次调用若 `_trade_dates is None` 则跳过对齐（修复前后一致，`build_limit_prices` 内部会再对齐） | 登记（不改，避免初始化顺序副作用） |

---

## 10. 可重放命令（E1）

```powershell
# 1) 五 kind 覆盖对照
& $py -c "import pandas as pd; MD=r'E:\Ashare_data\market_data'; c=pd.read_pickle(MD+r'\stock_close.pkl'); a=pd.read_pickle(MD+r'\stock_adj.pkl'); ci=pd.DatetimeIndex(pd.to_datetime(c.index)); ai=pd.DatetimeIndex(pd.to_datetime(a.index)); print(c.shape, a.shape, len(ci.difference(ai)))"

# 2) 现网失败复现（须在 examples 真实数据脚本上）
& 'C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe' examples\run_single_backtest.py

# 3) 修复后等价性（合成数据无缺日 → ffill 恒等）
& $py -c "import pandas as pd,numpy as np; i=pd.date_range('2024-01-02',periods=5); d=pd.DataFrame({'a':[1.0,1.1,1.1,1.1,1.2]},index=i); print(d.ffill().reindex(i).equals(d.loc[i]))"

# 4) 门禁
& $py -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
& $py -m pytest tests -q
```

---

## 11. Step 2 交接事项

1. **异构复审（RULE-5）**：作者 DeepSeek-V4.1-Flash → 须异构基座；核验重点：① 81 日缺失与 4.81% 影响面的重放（§2.4）；② ffill 语义的独立性（§2.3 变化次数）；③ M-A 与 M-B/M-D/M-E 的裁决是否成立（§6）；④ 修复范围「只改 adj_factor」是否漏掉其他 kind 的同类风险。
2. **判档确认**：`core/data.py` 属 Layer-1 → **T1**（不可降档）。
3. **顺序敏感**：必须 `reindex(data.index.union(window)) → ffill → reindex(window)` 三段式（F-S1-P039-1：任何两段式在窗口首日缺口时均留 NaN）；`logger.info` 计数须在 reindex 前后各取一次 `isna().all(axis=1).sum()` 差值。
4. **红态纪律**：Step 9 首跑须出示修复前读数（`FileNotFoundError` / KeyError 逐字）+ 真实数据场景。

---

## 12. Step 1 自查记录（F-S1-P039-1，P2）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S1-P039-1** | **P2** | 本文件初稿 §6.1 推荐「先 `ffill()` 后 `reindex()`」，声称可取得窗口外前值——**实测不成立**：`ffill` 只填充已存在的行、不创建缺失行，窗口首日缺口在两种两段式写法下**均为 NaN**（`A=[NaN,1.1,1.2]` / `B=[NaN,1.1,1.2]`），仅三段式 `reindex(union) → ffill → reindex(window)` 得 `[1.0,1.1,1.2]` | §6.1 代码改写为三段式；硬约束 1 重写；R-P039-2 / §11.3 同步订正 |

> 该发现属「规格可行性」缺陷——若按初稿实施，当前真实数据（窗口首日 `2020-01-23` 存在）恰好不会暴露，但一旦用户自定义 `start_date` 落在缺失日即静默留 NaN。三段式是唯一同时满足「补齐缺口 + 不污染未上市期 + 取窗口外前值」的写法，实测无缺日时与 `.loc` 逐值等价（`True`）。

---

## 13. Step 2 复审记录（同基座独立上下文，2026-11-17）

> **基座披露（RULE-5 诚实声明）**：复审会话 system prompt 逐字自报 `You are powered by the model named DeepSeek-V4.1-Flash.`——**与作者同源 → 异构不成立**（同基座独立上下文复审，RULE-4 披露）；登记 **U-P039-3**（异构终审预留，先例 U-P036-6 / U-P037-3）。
> **复审方式**：独立探针 `%TEMP%\p039_s2_review.py`（不复用 Step 1 三个探针）+ 真实数据端到端重放；复审时点 HEAD `377b26a`。

### 13.1 复核读数（全部与原文一致）

| 项 | 复审实测 | 原文 | 判定 |
|----|---------|------|------|
| `adj 缺且 close 有值` | **403,853 / 8,389,800 = 4.814%** | 4.81% | ✅ |
| `ffill` 后该口径 | **0** | 0 | ✅ |
| 窗口 `2020-01-23..2026-02-09` | **1460** 日 | 1460 | ✅ |
| 三段式端到端 | `shape=(1460, 5691)`、全 NaN 行 **0**、**0.18s**、**66 MB** | 未测 | ✅（回填 R-P039-3） |
| 现网 `.loc[window]` | **KeyError**（复现） | KeyError | ✅ |
| 无缺日等价性 | **True** | True | ✅ |
| 81 日分布（9/8/10/16/31/7） | 与 Step 1 探针一致 | 一致 | ✅ |

### 13.2 发现与当轮处置（0 P1/P2 + 3 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S2-P039-1** | P3 | **列维度同型严格索引**：L306 `data = data[self._stock_codes]` 在 adj 缺 close 列时同样 KeyError（实测 `KeyError: "['000001'] not in index"`）；Step 1 仅登记了「当前缺列 0」但未建未决项 | 新增 **U-P039-1 → U-P039-2** 建行；本批**不扩做**（改列对齐 = 缺列→NaN 新静默路径，违反 M-B 拒绝理由） |
| F-S2-P039-2 | P3 | R-P039-3 内存/耗时只写「可接受」，无实测数字 | 回填实测 66 MB / 0.18s |
| F-S2-P039-3 | P3 | 「4.81%」四舍五入与精确值 4.814% 混用风险 | §2.4 保留 4.81%（分母 8,389,800 已在 §13.1 写全） |

### 13.3 结论

**复审结论**：**pass（0 P1/P2 + 3 P3 当轮处置）**——数据读数、方案裁决、范围边界全部可复现；M-A 三段式在真实数据端到端验证通过（0 全 NaN 行 / 0.18s / 66 MB），**准予进入 Step 3 DESIGN**。
**RULE-5**：本轮同基座 → **U-P039-3 跟踪**（Step 4/6/8/10 同样须先自报基座；无法证实异构时一律登记而非默认为异构）。

