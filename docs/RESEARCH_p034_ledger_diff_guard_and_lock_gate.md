# RESEARCH：P-034 台账收口 · 价格差异校验守卫 · CI 锁门禁

> **批次**: P-034 · **T1**（**强制升级**：任务 C 新增 CI 门禁，命中 SPEC_PROCESS §批次档位 判档规则 2「新增 / 删除 / 弱化任何门禁 → 一律 T1」，覆盖路径判定）
> **状态**: **Step 1 完成**（2026-11-17，基线 HEAD `fbed072`；P-033 批次关闭态）
> **作者基座**: DeepSeek-V4.1-Flash（Step 2 复审须异构，RULE-5）
> **上游**: ① 待办分析（2026-11-17，用户裁决「三件合批走完十步」）；② **U-P033-1**（R3 `close=0` 告警文案）；③ **U-P024-2**（CI 增加 `uv lock --check` 门禁，**单一跟踪源**，承接已合并的 U-P021-1）；④ PROGRESS §1.4 台账三缺口（P-030 / P-032 同型第三次）
> **取证脚本**: `%TEMP%\p034_step1_probe.py`（R3 差异校验六形态 + P-033 守卫交互，仓库外运行；Python312 + `MPLBACKEND=Agg`）

---

## 0. 结论摘要（TL;DR）

| 项 | 结论 |
|----|------|
| **判档** | **T1**——不是 T3。任务 C 改 `.github/workflows/tests.yml` 且新增门禁判据，判档规则 2 强制升级；三件不再拆分（用户裁决合批） |
| **任务 A 台账** | **8 处缺口**：U-P033-1~3 未建行（P-030/P-032 同型第三次）+ U-P014-1 / U-P014-3 / U-P015-1 / U-P016-1 仅存在于批次文档 + U-008 与 U-P021-2 双源同项 |
| **任务 B R3** | 原描述只覆盖「`np.float64(0)` → `inf%` 告警噪声」；本批探针实证出**三种形态**：R2 `inf%` 噪声（生产可达）/ **R1 诊断代码吞单**（Python float `0.0` → `ZeroDivisionError` → 合法价订单 `success=False`）/ R3 `close` 为 NaN 或负 → 校验静默失效 |
| **R1 定级** | **P3**（结构性隐患）：诊断代码可改变交易结果，属「观测影响被测」反模式；但生产三引擎路径 `close_price` 全来自 `.loc[date]`（`np.float64`）→ 当前**不可达**，诚实降级为 P3 |
| **任务 C uv lock** | `uv 0.11.14` + `uv lock --check` 本地 **exit 0**（148 packages / 25ms）；CI `tests.yml` **零 uv 步骤**（`pip install ".[dev]"`）→ 锁漂移当前无任何拦截 |
| **修复形态** | 一个前置判定复用 `is_valid_price(close_price)`（P-033 单一判定来源，1 定义 3 调用 → 4 调用），一次覆盖 R1/R2/R3 |
| **测试破坏面** | **0**——全仓 `tests/` 无 `close_price=0` / `close=0` 用例（grep 零命中）；golden 13 条全为有效 close |
| **门禁影响** | 本地 pytest **748 → 748+n**（新增测试）；tests 文件 **83 → 84**；black **120 → 121**；mypy **37 files 0** 不变；golden **13 零重录**；CI 新增 **1 job**（`lock-check`，不进三版本 matrix） |

一句话：**把一个「诊断检查」从「可能改变交易结果并产生噪声告警」修成「价格无效时安静跳过」——顺手把三次同型的台账漏建行收口，并给已经归零的 `uv lock --check` 补上 CI 拦截。**

---

## 1. 判档依据（T1，不可降档）

| 判据 | 实测 | 结论 |
|------|------|------|
| 判档规则 1（路径集） | 改动路径含 `.github/workflows/tests.yml`（∈ Layer-1 集合） | Layer-1 |
| 判档规则 2（强制升级） | 任务 C = **新增 CI 门禁判据**（`uv lock --check` 失败即 job 失败） | **一律 T1** |
| 判档规则 3（fail-closed） | 任务 B 改 `core/execution.py`（运行时日志面 + 异常路径） | 不适用降档 |
| 裁剪 | **无**——四文档 + 8 道 Review 全量 | —— |

> **与上轮建议的偏差（诚实记录）**：待办分析中把本批称作「T3 台账收口 + R3 文案 + uv lock 门禁（零行为风险档）」。按 §批次档位 判档规则 2，**含新增门禁的批次不存在 T3 选项**；本轮 Step 1 修正为 T1。任务 A 单独成批仍可为 T3，但用户裁决合批，故整批 T1。

---

## 2. 三件任务的取证

### 2.1 任务 A：台账缺口（8 处，E1 grep 取证）

| # | 缺口 | 证据 | 处置 |
|---|------|------|------|
| A1 | **U-P033-1**（R3 `close=0` 告警文案）未建行 | `Grep "U-P033"` 仅命中 PROGRESS §3.38.9 正文与 DESIGN_p033 §7，§1.4 主表**零行** | 本批 **B 组修复后关闭**，建行标 done |
| A2 | **U-P033-2**（BUY 侧现金夹紧）未建行，且与 U-P031-2 / U-P014-3 **三源同项** | U-P031-2 行已注「与 U-P014-3 同列」；U-P033-2 仅见 DESIGN_p033 §7 | **三源合并为 U-P031-2 单一跟踪源**（P-028 先例：保留历史行不删，标注「已合并」） |
| A3 | **U-P033-3**（账目层守卫，已裁决不采纳）未建行 | DESIGN_p033 §7「与 O-P031-1 同列，不采纳（D1 理由）」 | 建行标「**已裁决不采纳**」（非 pending，防误判为待办） |
| A4 | **U-P014-1**（停牌 / 涨跌停掩码语义变更）未建行 | DESIGN_p014 §1「不改变掩码语义（U-P014-1）」；仅 CHECKLIST_p014 提及 | 建行 pending（条件触发） |
| A5 | **U-P014-3**（队列路径买侧现金校验）未建行 | DESIGN_p014 §1「不为队列路径补买侧现金校验（U-P014-3）」+ §2 拒绝方案 | 并入 A2（同一事项） |
| A6 | **U-P015-1**（Backtrader ↔ V2 第二例对拍）未建行 | RESEARCH_p015 §6 四元块完整存在，但 §1.4 无行 | 建行 pending（四元块照录） |
| A7 | **U-P016-1**（current-NAV 规格费用语义 rate>0）未建行 | RESEARCH_p016 §6 四元块 + 「触发条件 = U-P015-1 立项时」 | 建行 pending（依赖 A6） |
| A8 | **U-008** 与 **U-P021-2** 双源同项（numba 依赖 / JIT 覆盖） | 旧表 U-008「numba JIT 路径在 CI 有覆盖」；§1.4 U-P021-2「`numba` 依赖声明」均指向同一缺口 | U-008 标「**已合并至 U-P021-2**」（保留历史行） |

> **同型复发（第三次）**：P-030（U-P029-2 未建行）→ P-032（U-P031-1~4 未建行）→ **P-034（U-P033-1~3 + 四项散落）**。三次的共同成因是「批次关闭时只写 §3.x 正文、不建 §1.4 行」。本批 Step 9 须在 PROCESS 层留一条纪律（见 §7 方案 M-A 的 D5）：**批次关闭动作清单包含「U-* 建行」一项**。

### 2.2 任务 B：R3 差异校验的三形态（探针实证）

代码位置：`core/execution.py` L316-324（`# 价格合理性检查` 段），在 P-033 守卫（L308-315）**之后**、`amount`（L327）**之前**。

```python
            # 价格合理性检查
            if close_price is not None:
                price_diff_ratio = abs(execution_price - close_price) / close_price
                if price_diff_ratio > 0.1:  # 10%阈值
                    logger.warning(...)
```

| 形态 | 构造 | 实测读数 | 判定 |
|------|------|----------|------|
| **R1 诊断吞单** | `close_price=0.0`（Python `float`） | **`success=False`**、`trade=None`、零告警——`abs(10.0-0.0)/0.0` 抛 `ZeroDivisionError` → 被 L359 `except Exception` 捕获 → `logger.error("交易执行失败")` → 返回 `(False, None)` | **P3**（结构性隐患；合法价订单因诊断失败） |
| **R2 噪声告警** | `close_price=np.float64(0)`（pandas 来源） | `success=True`、`ratio=np.float64(inf)`、**1 条告警 `差异=inf%`** | **P3**（U-P033-1 原范围；日志噪声） |
| **R3 校验静默失效** | `close_price=NaN` / `-5.0` | `success=True`、`ratio=nan` / `-3.0` → `> 0.1` 恒 `False` → **零告警** | **P3**（新形态；观测盲区，无账目影响） |
| 正常路径（对照） | `close=10.0`（同价） / `close=8.0`（真实 25% 差） | `ratio=0.0` 零告警 / `ratio=0.25` **1 条告警** | ✅ 合法价路径逐字正确 |
| P-033 守卫交互 | `open=NaN, close=0` | 仅 1 条「执行价格无效」告警，**未进入差异校验** | ✅ 守卫先行成立（P-033 双层防线不受影响） |

**为什么 R1 只判 P3（诚实降级）**：`close_price` 在生产三引擎的全部 8 个调用点均来自 pandas 横截面 `.loc[date]`，元素类型为 `np.float64`——numpy 除零返回 `inf` 而非抛异常，故 R1 **当前不可达**。R1 的可达条件 =「`execution_price` 与 `close_price` 同时为 Python `float` 且 close 为 0」，仅出现在外部直接调用 / 未来新调用方 / 手工注入场景。

> **Step 2 精化（F-S2-P034-1，C2 实证）**：R1 的可达性对**取值写法**敏感——`row[stock]`（Series 索引）→ `np.float64`；**`row.to_dict()[stock]` 与 `dict(row.items())[stock]` → Python `float`**。故「生产不可达」的准确表述是「**当前 8 个调用点采用 Series 索引写法**故不可达」；一旦有人把取价改为 `to_dict()`（常见重构），R1 立即可达。这使修复理由从「纯理论」变为「防一次常规重构引入吞单」，但当前定级仍为 P3（按现行代码可达性）。

> **但修复不因此降级**：R1 揭示的是「**诊断代码可以改变交易结果**」——观测逻辑不应有副作用。修复成本 = 1 个前置判定，与 R2/R3 同一个判定，无额外代价（IMPL §7 低效排除已核）。

### 2.3 任务 C：uv lock 门禁现状

| 项 | 实测 | 证据 |
|----|------|------|
| uv 版本 | **0.11.14**（`3fdfdc7d4 2026-05-12`） | `uv --version` |
| 锁文件 | `uv.lock` 存在，`version = 1` / `revision = 3` / `requires-python = ">=3.10"` | `Get-Content uv.lock -TotalCount 5` |
| `uv lock --check` | **exit 0**（`Resolved 148 packages in 25ms`） | `uv lock --check` |
| CI 现状 | 单个 job `test`，matrix 3.10/3.11/3.12；依赖安装为 `pip install ".[dev]"`；**零 uv 步骤** | `.github/workflows/tests.yml` L9-46 |
| 门禁缺口 | 锁漂移（pyproject 变更后未重锁）当前**无任何 CI 拦截**；本地 `--check` 归零但不约束提交 | 同左 |
| `[tool.uv]` 段 | pyproject **无** `[tool.uv]` 段（不涉及 uv 安装路径） | `Grep "tool.uv" pyproject.toml` 零命中 |

> **门禁放置**：`uv lock --check` 与 Python 版本无关（uv 是独立二进制）→ 应设**独立 job**（`lock-check`），不进三版本 matrix，避免同一检查跑 3 次。

---

## 3. 缺陷与任务清单

| ID | 级别 | 内容 | 出口 |
|----|------|------|------|
| **R1** | P3 | `close_price=0.0`（Python `float`）→ `ZeroDivisionError` → 合法价订单 `success=False`（诊断吞单） | B 组守卫（同一判定覆盖） |
| **R2** | P3 | `close_price=np.float64(0)` → `inf` → 「差异=inf%」告警噪声（U-P033-1 原文） | B 组守卫 |
| **R3** | P3 | `close_price` 为 NaN / 负 → 比值 NaN / 负 → 差异校验静默失效（零告警） | B 组守卫 |
| **R4** | —— | 台账 8 处缺口（§2.1 A1-A8） | A 组（纯文档） |
| **R5** | —— | 锁漂移无 CI 拦截（U-P024-2） | C 组（CI job） |

**负向发现（N 系列，已排除的猜测）**：

| ID | 猜测 | 结论 |
|----|------|------|
| N1 | 「R3 只是文案噪声，无功能影响」 | **部分不成立**——`np.float64` 形态仅噪声；**Python float 形态会吞单**（R1） |
| N2 | 「生产路径可能触发 R1」 | **不成立**——三引擎 8 调用点 `close_price` 全为 `np.float64`（`.loc[date]`）；`_force_liquidation` 的 `float(price)` 只用于 `open_price` 位，close 传 `None` |
| N3 | 「P-033 守卫已覆盖 close 无效」 | **不成立**——P-033 守卫判的是**解析后的执行价**，`close_price` 仅参与诊断；`close=0` 时执行价（open）合法 → 守卫放行 → 进入差异校验 |
| N4 | 「既有测试依赖 `close=0` 的告警/吞单行为」 | **不成立**——`tests/` 中 `close_price=0` / `close=0` **零命中**；golden 13 条全为有效 close |
| N5 | 「CI 加 uv 会改变安装路径 / 影响测试 job」 | **不成立**——独立 job，不改 `Install dependencies`；测试 job 仍 `pip install ".[dev]"` |
| N6 | 「`uv lock --check` 会因 Python 版本差异误报」 | **不成立**——锁文件声明 `requires-python = ">=3.10"`，检查与解释器无关；风险仅在 uv 二进制版本（钉 `0.11.14` 规避） |

---

## 4. 复现矩阵

| # | 任务 | 构造 | 期望行为 | 实测（现状） | 判定 |
|---|------|------|----------|--------------|------|
| B1 | R1 | `close_price=0.0`（py float），open=10 | 成交（close 无效仅跳过诊断） | **`success=False`**（吞单） | ❌ R1 |
| B2 | R2 | `close_price=np.float64(0)`，open=10 | 成交 + 零差异告警 | 成交 + **`inf%` 告警** | ❌ R2 |
| B3 | R3a | `close_price=NaN`，open=10 | 成交 + 零差异告警 | 成交 + 零告警（**比值 NaN，静默**） | ❌ R3（静默） |
| B4 | R3b | `close_price=-5.0`，open=10 | 成交 + 零差异告警 | 成交 + 零告警（比值 -3.0） | ❌ R3（静默） |
| B5 | 回归 | `close_price=8.0`（25% 差） | 成交 + **1 条告警（25.00%）** | 成交 + 1 条告警 | ✅ 不得回归 |
| B6 | 回归 | `close_price=None` | 成交 + 零告警 | 成交 + 零告警 | ✅ 不得回归 |
| B7 | 交互 | `open=NaN, close=0` | P-033 守卫先返回，零差异校验 | 仅「执行价格无效」1 条 | ✅ 不得回归 |
| C1 | 锁门禁 | `uv lock --check` | exit 0 | **exit 0**（148 packages） | ✅ 基线 |
| C2 | 锁漂移 | 模拟 pyproject 与 lock 不一致 | job **失败**（非 `\|\| true`） | 无门禁（不可观测） | ❌ R5 |

---

## 5. 探针原文（关键读数逐字）

```
f:\Coding\Factor_Trading_v3.0\core\execution.py:318: RuntimeWarning: divide by zero encountered in scalar divide
  price_diff_ratio = abs(execution_price - close_price) / close_price
=== R3 差异校验四形态 ===
[close=0（R3 原形态）] close=0.0 | success=False | ratio=RAISED ZeroDivisionError: float division by zero | ratio>0.1=None | warn_count=0 | warn=[]
[close=NaN] close=nan | success=True | ratio=nan | ratio>0.1=False | warn_count=0 | warn=[]
[close=-5] close=-5.0 | success=True | ratio=-3.0 | ratio>0.1=False | warn_count=0 | warn=[]
[close=10（正常同价）] close=10.0 | success=True | ratio=0.0 | ratio>0.1=False | warn_count=0 | warn=[]
[close=8（真实 25% 差异）] close=8.0 | success=True | ratio=0.25 | ratio>0.1=True | warn_count=1 | warn=['A在2024-01-02 00:00:00执行价格与收盘价差异过大: 执行价=10.00, 收盘价=8.00, 差异=25.00%']
[close=np.float64(0)] close=np.float64(0.0) | success=True | ratio=np.float64(inf) | ratio>0.1=True | warn_count=1 | warn=['A在2024-01-02 00:00:00执行价格与收盘价差异过大: 执行价=10.00, 收盘价=0.00, 差异=inf%']

=== P-033 守卫与差异校验的先后 ===
[open=NaN, close=0] success=False trade=None msgs=['A在2024-01-02 00:00:00执行价格无效: nan，订单未成交（P-033 价格守卫）']
```

> 探针中 `close=0.0` 的 `success=False` 正是 L359 `except Exception` 捕获 `ZeroDivisionError` 的结果；`warn=[]` 是因为过滤条件只筛「差异 / 无效」，异常日志文案为「交易执行失败」。

---

## 6. 影响面

### 6.1 `close_price` 生产类型链（R1 可达性判定依据）

| 引擎 / 调用点 | `close_prices` 来源 | 元素类型 |
|---------------|---------------------|----------|
| V2 `_process_pending_orders`（L815 调用 / L804-808 取价） | `self._exec_price(dm, "close").loc[date]`（L770-771） | `np.float64` |
| V2 next-day（L1166） | 未传 close（仅 open） | —— |
| V2 强平（L566） | 未传 close（`float(price)` 只进 open 位） | —— |
| V2 fallback（L884 → `execute_pending_order`） | 继承调用方 | `np.float64` |
| agents queue（L525 / L509） | `self.dm.get_adj_price("close", ...).loc[date]`（L489） | `np.float64` |
| agents next-day（L463） | 同左（L402 派生） | `np.float64` |
| `agent_framework._execute_trade`（L1420 / L1345） | `adj_close.loc[date, stock]` | `np.float64` |
| 外部 / 测试直接调用 | 任意（可传 Python `float`） | **可能 `float`** ← R1 |

### 6.2 零改动面

`core/tracker.py` / `core/pending.py` / `core/interfaces.py` / `core/target_positions.py` / `core/engine_v2.py` / `agents/` / `tests/golden/*.json` / `filter/` / `scripts/` / `cli.py` / `pyproject.toml`（任务 C 不改依赖集，只在 CI 安装 uv 二进制）。

**变更面**：`core/execution.py`（差异校验守卫）+ `tests/test_p034_*.py`（新增）+ `.github/workflows/tests.yml`（新增 job）+ 文档（四文档 + PROGRESS + CHANGELOG + ARCHITECTURE §9.2）。

### 6.3 测试与门禁基线（P-033 终态，Step 7 复测确认）

pytest **748 passed** / `tests/` .py **83** / black `--check core tests` **120** / mypy `--explicit-package-bases core` **37 files 0 error** / golden **13 passed 零重录** / `except Exception`（P-029 十文件口径）**22**。

---

## 7. 方案矩阵

### 7.1 任务 B（R1/R2/R3 三合一）

| 维度 | **M-A（推荐）** | M-B | M-C |
|------|-----------------|-----|-----|
| 形态 | `if close_price is not None and is_valid_price(close_price):` 包裹差异校验 | 只处理 `inf`：`if not math.isfinite(ratio): 跳过` | 移除差异校验（纯诊断，无账目作用） |
| 覆盖 | R1 + R2 + R3 **全部** | 仅 R2（R1 仍吞单、R3 仍静默） | 全部（但丢失合法价差异告警能力） |
| 复用 | 复用 P-033 `is_valid_price`（1 定义 **3 → 4** 调用，单一来源） | 引入第二套判定（漂移风险） | —— |
| 合法价路径 | 逐字不变（V5/V6 回归锁） | 不变 | **丢失** 25% 差异告警（既有诊断能力退化） |
| mypy | `is not None` 保留窄化 → 零问题 | 需 `math` 导入 | —— |
| 判定 | **采纳** | 拒绝（覆盖不全） | 拒绝（删诊断能力） |

> **为什么保留 `close_price is not None`**：`is_valid_price` 返回 `bool` 而非 `TypeGuard[float]`，mypy 不会据此窄化 `Optional[float]`，`abs(float - Optional[float])` 会报错。保留 `is not None` 只用于类型窄化，语义上被 `is_valid_price` 完全覆盖（无冗余行为）。

### 7.2 任务 C（CI 锁门禁）

| 维度 | **M-A（推荐）** | M-B |
|------|-----------------|-----|
| 形态 | 独立 job `lock-check`：`astral-sh/setup-uv@v6`（`version: "0.11.14"`）+ `uv lock --check` | 并入现有 test job 首个 step |
| 轮次成本 | **1 次** | 3 次（matrix 3.10/3.11/3.12 重复） |
| 失败可见性 | 独立 red job，归因清晰 | 与测试失败混在同一 job |
| 判定 | **采纳** | 拒绝 |

**门禁纪律（P-024 教训）**：**禁止 `|| true`**；失败即 job 失败。uv 版本钉 `0.11.14`（与锁文件 `revision = 3` 同源，避版本漂移误报）。

### 7.3 任务 A（台账收口）

**M-A**：8 处缺口逐项处置（§2.1 表），PROGRESS §1.4 主表新增 6 行（U-P033-1 done / U-P033-3 不采纳 / U-P014-1 / U-P015-1 / U-P016-1 + U-008 合并标注），U-P031-2 行补「合并 U-P014-3 / U-P033-2」注记。

**D5 派生纪律（本批新登记）**：批次关闭动作清单新增一项——**「本批新增的 U-* / O-* 是否已在 §1.4 建行」**，写入 PROGRESS §3.x 记录；三次同型（P-030 / P-032 / P-034）后不再靠事后补。

**低效排除**：

| # | 候选 | 排除理由 |
|---|------|----------|
| 1 | 为 close 新增独立判定函数 | 与 `is_valid_price` 判据完全相同（有限正数），第二来源 = 漂移入口 |
| 2 | 差异校验改为 debug 级日志 | 丢失合法价 25% 差异告警（既有诊断能力） |
| 3 | R1 升级为 P2 | 生产不可达（N2 实证），定级按可达性而非理论形态 |
| 4 | CI 也跑 `uv export --frozen` | 本批只补 `--check`（U-P024-2 单一判据），export 属新门禁 = 越界 |
| 5 | 在 CI 里 `uv sync` 安装依赖 | 改变安装路径（pip → uv），超出 U-P024-2 范围，风险高 |
| 6 | 一次性重构 §1.4 全表 | 台账收口只补缺口，不做格式重构（历史行不改，O-R5-P031-1 先例） |

---

## 8. 风险四元块

| ID | 类型 | 内容 | 处置 |
|----|------|------|------|
| R-P034-1 | 风险 | 差异校验跳过条件由 `close is not None` 扩为 `is_valid_price(close)`：`close=0` / NaN / 负 从「告警或抛异常」变为「静默跳过」——若有人依赖该告警做数据质量监控，会失去信号 | 有意（R2 噪声 / R3 静默本身不可用）；数据质量监控应由掩码层（P-010/P-012）承担；文档披露 |
| R-P034-2 | 风险 | CI 新增 `lock-check` job 引入外部 action（`astral-sh/setup-uv`） | 钉版本 `0.11.14`；失败即红（零容忍）；若 action 不可用则降级为 `pip install uv==0.11.14`（降级链 F3） |
| R-P034-3 | 风险 | `uv lock --check` 在 CI 冷缓存下需网络解析，可能受索引波动影响而偶发红 | 只读检查（不改锁）；偶发失败可通过重跑排除；不接受 `|| true` |
| U-P034-1 | 未决 | `setup-uv` action 版本的长期维护（是否改 `pip install uv`） | 触发：action 主版本升级或不可用；倾向用 action（有缓存） |
| U-P034-2 | 未决 | R1 的外部调用面（是否有本仓外脚本直接调 `execute_order`） | 触发：出现真实外部调用报告；本批修复已使该形态安全，故仅登记 |
| O-P034-1 | 观察 | `price_diff_ratio` 阈值 0.1（10%）为硬编码，无可配置入口 | 不改（既有行为，无需求） |
| O-P034-2 | 观察 | 差异告警文案格式 `{:.2%}` 对 inf 输出 `inf%`（R2 现象的另一面） | 本批跳过路径已消除，无需改格式 |

---

## 9. 负向发现汇总

见 §3 N1-N6 表（六项均已实证排除，其中 N2/N3 是本批最关键的两次可达性判定）。

---

## 10. 下一 Step

**Step 2 独立 Review（RULE-5 要求异构基座）**——本文件作者 DeepSeek-V4.1-Flash。复核重点：

1. **判档**：T1 强制升级的认定是否成立（任务 C 是否确实构成「新增门禁」）；三件合批是否应拆；
2. **R1 定级**：P3（生产不可达）是否成立，还是应升 P2；
3. **修复形态 M-A**：`is_valid_price(close_price)` 前置是否会在合法价路径产生任何行为差异（尤其 `close` 为 `np.float64` 正数时的类型分派）；
4. **保留 `is not None` 的理由**（mypy 窄化）是否成立，是否应改用 `TypeGuard`；
5. **CI 门禁**：独立 job + `setup-uv` 钉版是否是最小面；是否存在 `--check` 的已知误报形态；
6. **台账**：8 处缺口的处置（合并 / 建行 / 标不采纳）是否符合 P-028 / P-030 / P-032 先例。

---

## 11. Step 2 独立 Review 记录（2026-11-17）

> **基座**: **DeepSeek-V4.1-Flash**——与本文作者**同源** → **RULE-5 异构条件不成立**，本轮按 P-032 先例执行**同基座独立复审**（RULE-4 单视角披露），异构终审登记 **U-P034-3**（须非 DeepSeek 基座承接）。
> **复审对象**: `279c86a`（RESEARCH_p034 提交版）；复审时点 HEAD `279c86a`
> **方法**: E1 锚点重放（读码）+ E2 探针原样重放 + E3 独立探针四项新证（`%TEMP%\p034_step2_review_probe.py` C1-C3 + 临时目录锁漂移模拟 C4）

### 11.1 E1 锚点重放（十二项）

| # | RESEARCH 声称 | 实查 | 结果 |
|---|---------------|------|------|
| A1 | 差异校验 `core/execution.py` L316-324（`# 价格合理性检查` / `if close_price is not None` / ratio / `> 0.1` / warning） | 读码 L316-324 逐行命中 | ✅ |
| A2 | P-033 守卫 L308-315 在差异校验**之前** | 读码 L308-315 → L316 | ✅ |
| A3 | `except Exception` L359 覆盖差异校验（R1 吞单路径） | 读码 L302 `try` / L359 `except` 包围 L316-324 | ✅ |
| A4 | `_get_execution_price` OPEN 直接 `return open_price`（无 `float()` 转换） | L229-230 | ✅（类型随入参） |
| A5 | VWAP `sum(prices)/len(prices)` | L249 | ✅ |
| A6 | CUSTOM 仅判 `> 0`、`cast(float, ...)` 运行期不转换 | L257-258 | ✅（回调返回 Python float 时保持 float） |
| A7 | V2 `close_prices = self._exec_price(dm, "close").loc[date]` | L770-773 | ✅（Series） |
| A8 | V2 queue 传 close（L804-808 → L820） | 读码 | ✅ |
| A9 | agents `close_prices = ...get_adj_price("close", ...).loc[date]`（L489）→ L509 → L525 | 读码 | ✅ |
| A10 | `agent_framework` L1345 `adj_close.loc[date, stock]` → L1420 | 读码 | ✅ |
| A11 | CI `tests.yml` 单 job + matrix 3.10/3.11/3.12 + `pip install ".[dev]"`，零 uv | L9-46 逐行 | ✅ |
| A12 | `uv.lock` `version = 1` / `revision = 3` / `requires-python = ">=3.10"` | 头部 5 行 | ✅ |

### 11.2 E2 探针重放

`%TEMP%\p034_step1_probe.py` 原样重跑：六形态读数与 §5 原文**逐字一致**（`close=0.0` → `success=False` / `np.float64(0)` → `inf` + 1 条告警 / NaN·负 → 零告警 / `close=8.0` → 25.00% 告警 / `open=NaN, close=0` → 守卫先行）。

### 11.3 E3 独立探针（四项新证）

| 探针 | 构造 | 读数 | 结论 |
|------|------|------|------|
| **C1** `is_valid_price` 语义表 | 12 值（None / py·np 的 0·负·正 / nan / ±inf / 1e-9） | 无效 8 值全 `False`、合法 4 值全 `True`（**含 `1e-9`**） | **零误伤**——极小正价仍放行；作为 close 判定同样正确 |
| **C2** pandas 取值形态 → 类型 | `df.loc[date]` / `row[stock]` / `row.to_dict()` / `dict(row.items())` | Series → `np.float64`；**`to_dict` / `items` → Python `float`**；`np.float64 / Python 0.0` = **`inf`（不抛）**；`Python / Python 0.0` = `ZeroDivisionError` | **R1 可达性对取值写法敏感** → F-S2-P034-1 当轮回写 §2.2 |
| **C3** M-A 等价性 | 合法 close（8.0 / 10.0 / 10.5）vs 无效（0 / NaN / -5 / np0） | 合法三例 `old == new` **逐位一致**、告警判定一致；无效四例 `SKIPPED` | M-A **零合法价行为差异** |
| **C4** 锁漂移检出（临时目录，不动工作区） | 复制 pyproject + uv.lock → 改 `numpy>=1.23.0`→`>=1.24.0` → `uv lock --check` | **exit 1** + `The lockfile at 'uv.lock' needs to be updated, but '--check' was provided.`（基线未改副本 exit 0） | **门禁可真实变红**（P-024「假门禁」教训的正面实证） |

### 11.4 E4 六项复核重点裁决（对应 §10）

| # | 复核点 | 裁决 |
|---|--------|------|
| 1 | 判档 T1 | **成立**——判档规则 2 明列「新增 / 删除 / 弱化任何门禁（hook / CI / 校验器判据）」；任务 C 新增 CI job 判据 → 强制 T1。三件合批不拆（拆批需二次立项 + 二次台账收口，收益为负） |
| 2 | R1 定级 | **维持 P3**——C2 证实「不可达」依赖 Series 索引写法；按现行代码可达性定级（P2 门槛是生产可触发）。同时在 §2.2 精化披露「改 `to_dict()` 即触发」，使修复理由可审计 |
| 3 | M-A 行为差异 | **零差异**——C3 逐位一致；无效 close 由「抛异常 / 噪声 / 静默」统一为「跳过」，是本批唯一有意行为变更（限诊断告警面，不触账目） |
| 4 | `is not None` 保留 vs `TypeGuard` | **保留成立**——`is_valid_price` 返回 `bool`，mypy 不窄化 `Optional[float]`，`is not None` 用于类型窄化（非冗余判定）；改 `TypeGuard[float]` 需修改 P-033 已验收的公共签名与 3 个调用点，收益仅少写半个条件 → **拒绝**（O-S2-P034-4） |
| 5 | CI 最小面 | **成立**——独立 job（1 次 vs matrix 3 次）；钉 `0.11.14`；禁 `\|\| true`；C4 已证可红。`setup-uv` action 版本真实性交 **Step 6** 核验（U-P034-1） |
| 6 | 台账处置 | **符合先例**——U-P033-2/U-P014-3 并入 U-P031-2（P-028 合并 + 保留历史行）；U-P033-3 用「已裁决不采纳」（P-025-4 先例）；其余建行（P-030/P-032 惯例）；U-008 标「已合并至 U-P021-2」 |

### 11.5 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S2-P034-1 | P3 | §2.2「R1 生产不可达」表述失准——不可达的前提是**Series 索引写法**；`to_dict()` / `dict(items())` 产生 Python `float`，改写法即可达（C2 实证） | **当轮回写 §2.2**（已补精化段） |
| O-S2-P034-1 | 观察 | 本机 `RUST_LOG=info` 使 `uv lock --check` 输出 **131 KB / 1554 行** INFO 日志（CI 无该变量，判据不受影响） | 登记；CI 命令可加 `-q` 收敛日志（不影响退出码） |
| O-S2-P034-2 | 观察 | `astral-sh/setup-uv` action 的主版本 / `0.11.14` 可解析性未在本轮核验 | 移交 Step 6（U-P034-1 已登记降级链 `pip install uv==0.11.14`） |
| O-S2-P034-3 | 观察 | R1 修复后仍存在「`execution_price` 为 Python float + close 为 Python float 0」的**外部**调用面（本仓已安全） | U-P034-2 跟踪 |
| O-S2-P034-4 | 观察 | `is_valid_price` 返回 `bool` 而非 `TypeGuard[float]`，调用方需自行 `is not None` 窄化 | 不改（避免动 P-033 已验收签名） |

### 11.6 结论与 Step 3 前置条件

**结论**: **pass**（0 P0/P1/P2 / **1 P3 当轮回写** / 4 观察）——判档 T1 成立、R1 定级经 C2 精化后维持、M-A 零合法价差异、CI 门禁经 C4 实证可红、台账处置合先例。
**RULE-5 声明**: 本轮为**同基座独立复审**（作者与复审均为 DeepSeek-V4.1-Flash），异构条件不成立；**U-P034-3 登记异构终审预留**（须非 DeepSeek 基座）。

**Step 3 DESIGN 前置条件**:
1. 修复按 **M-A**：`if close_price is not None and is_valid_price(close_price):` 包裹差异校验（保留 `is not None` 仅为 mypy 窄化）；
2. CI 采用**独立 job** `lock-check`：`astral-sh/setup-uv@v6`（`version: "0.11.14"`）+ `uv lock --check`，**禁 `|| true`**；Step 6 须给出 action 版本核验证据或降级为 `pip install uv==0.11.14`；
3. 测试规格须覆盖 C1 语义表（合法 `1e-9` 与六类无效值）、C3 合法性等价、R1 吞单（红态）、R2 噪声（红态）、R3 静默（红态）、V8 回归（合法 25% 差异仍告警）；C4 属 CI job，不进 pytest；
4. 台账 8 处按 §2.1 处置执行，Step 9 一并落地并在 §3.39 记录。
