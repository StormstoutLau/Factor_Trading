# P-034 台账收口 · 价格差异校验守卫 · CI 锁门禁 · 批次总结报告（十步终态）

> **批次**: P-034 · `core/execution.py` 差异校验守卫 + `.github/workflows/tests.yml` 新增 `lock-check` job + PROGRESS §1.4 台账 8 处收口（三件合批）· **T1**（**强制升级**：用户初判 T3「零行为风险」，但新增 CI 门禁触发判档规则 2 fail-closed）
> **状态**: **Step 1-10 全通过（同基座）+ U-P034-3 异构终审 pass，批次关闭**（2026-11-17）
> **审计基线**: 审计对象 `fbed072..4b6eef0`（14 提交，代码面集中于 `de0268d`）· 终态 HEAD `4b6eef0` · 四文档作者与五轮复审（Step 2/4/6/8/10）均为 DeepSeek-V4.1-Flash（同基座，RULE-5 不成立 → U-P034-3 预留）· **异构终审基座**: GLM-5.3-Flash（异构成立，RULE-5 机制补做）
> **配套文档**: [RESEARCH](RESEARCH_p034_ledger_diff_guard_and_lock_gate.md) / [DESIGN](DESIGN_p034_ledger_diff_guard_and_lock_gate.md) / [IMPL](IMPL_p034_ledger_diff_guard_and_lock_gate.md) / [CHECKLIST](CHECKLIST_p034_ledger_diff_guard_and_lock_gate.md)

---

## 1. 一页速览

| 维度 | 结果 |
|------|------|
| **治理对象** | ① 差异校验守卫——`close` 无效时三形态缺陷：**R1**（P3 结构性隐患）`close=0.0`（Python float）→ `ZeroDivisionError` 被 except 捕获 → **合法价订单 `success=False`（诊断吞单）** / **R2** `np.float64(0)` → `差异=inf%` 告警噪声 / **R3** `close` NaN·负 → 比值无效校验**静默失效**；② 台账 8 处缺口（P-030/P-032 同型第三次复发）；③ CI 锁门禁缺失——`uv lock --check` 本地 exit 0 而 CI 零 uv 步骤 |
| **核心手段** | **M-A 条件替换 + 单一判定来源复用**——差异校验条件改 `if close_price is not None and is_valid_price(close_price):`（复用 P-033 `is_valid_price`，**1 定义 + 4 调用**）；`is not None` 仅为 mypy 类型窄化（`bool` 非 `TypeGuard`，Step 4 正反例实证：省略则 2 errors）；**独立 `lock-check` job**（`@v10.3.3` 精确钉 + `version: "0.11.14"`、省略 `enable-cache`、无 `\|\| true`、失败即红） |
| **行为变更** | **1 处守卫条件 + 1 个 CI job**；无效 close 由「抛异常吞单 / 噪声 / 静默」统一为「**安静跳过**」——诊断与决策解耦，**不改变成交结果**；合法价 25% / 42.86% 告警逐字保留；零 fail-fast、公开签名零变更、`except Exception` 恒 **22** |
| **代码规模** | 代码面 3 文件 **+152/−3**（execution **+2/−2** / tests.yml **+14/−1** / 新测试 **+136**）；文档 7 文件 +1426/−4；全区间 10 文件 **+1578/−7** |
| **测试** | **748 → 760 passed**（+12 实例 / 5 函数）；测试文件 **83 → 84**（`test_*.py` 81）；红态 **3F/9P**（九例回归保护如实归档，不伪造红态） |
| **门禁** | black **120 → 121**；mypy **37 files 0 error**；golden **13 passed 零重录**；AST `except Exception` 恒 **22**；`uv lock --check` **exit 0**（新增 CI job 首跑即绿）；C4 实证门禁可红（改约束 → exit 1） |
| **质量结论** | 十步全过（五轮同基座复审）+ 异构终审 pass；**0 P0/P1 + 1 P2 + 7 P3 全部当轮处置 + 23 项观察全部登记**；**异构复审实锤 2 P3（同基座终审漏检）**——RULE-5 机制价值的直接例证 |

一句话：**「价格合理性校验是诊断不是判决」——无效 close 只应让告警闭嘴，而不是让合法订单陪葬（R1 吞单根因 = 把诊断失败当决策失败）；同时给 CI 装上「锁与 pyproject 不一致即红」的门禁，并把三次同型的台账散落一并收口。**

---

## 2. 背景：为什么修这一批

### 2.1 三件治理对象（Step 1 探针实证）

| 对象 | 级别 | 形态与读数 |
|------|------|-----------|
| **A 差异校验守卫（U-P033-1 承接）** | P3 三形态 | **R1** `close=0.0`（Python float）→ `price_diff_ratio` 除零抛 `ZeroDivisionError` → 被 L359 `except Exception` 捕获 → `success=False`、零入账——**合法价订单被诊断异常误杀**（结构性隐患）；**R2** `close=np.float64(0)` → numpy 除零语义 → ratio=`inf` → 「差异=inf%」告警噪声；**R3** `close=NaN` / 负 → 比值 NaN / 负 → `> 0.1` 判定失效 → **无告警成交**（校验静默失效） |
| **A 精化（Step 2 C2 新证）** | — | R1 可达性**对取值写法敏感**：pandas `to_dict()` / `dict(items())` 取值产生 Python `float`（R1 形态可达）；现 8 生产调用点全为 Series 索引取值（`np.float64`）→ **生产不可达**，但属外部调用面（U-P034-2 跟踪） |
| **B CI 锁门禁（U-P024-2 单一跟踪源）** | 门禁盲区 | `uv 0.11.14` 本地 `uv lock --check` exit 0，而 CI 零 uv 步骤——`pyproject.toml` 改约束不更新锁时 CI 依旧全绿；**C4 实证可红**：临时目录改 numpy 约束 → exit 1（「The lockfile at 'uv.lock' needs to be updated, but '--check' was provided」） |
| **C 台账 8 处缺口** | 治理债 | U-P033-1~3（P-033 关闭后未建行）/ U-P014-3（DESIGN_p014 非目标）/ 旧表 U-008——散落正文不建行同型问题第三次（P-030 / P-032 之后） |

### 2.2 治理谱系

| 批次 | 范围 | 结论 |
|------|------|------|
| P-024 | 假门禁教训（`\|\| true` 使门禁恒绿）→ U-P024-2 登记 uv lock 门禁 | 完成 |
| P-030 / P-032 | 台账收口两轮（散落正文建行先例） | 完成 |
| P-033 | `is_valid_price` 单点守卫落地；遗留 U-P033-1（R3 告警文案）等三项 | 完成 |
| 待办优先级分析 | 盘点 §1.4 全表 26 项 pending（0 P0/P1、1 P2、25 P3）→ 建议三件合批 P-034 | 完成 |
| **P-034（本批）** | **守卫条件 + CI 门禁 + 台账收口（三件合批 T1）** | **完成 / 关闭** |

### 2.3 判档修正（诚实披露）

用户初判三件为「T3 零行为风险档」，但**任务 C 新增 CI 门禁**触发 SPEC_PROCESS 判档规则 2（新增/删除/弱化任何门禁 → 一律 T1）——**强制升级 T1**，RESEARCH §1 显式记录该偏差。「零行为风险」≠「零过程风险」：CI 红绿语义本身就是行为。

---

## 3. 设计口径

### 3.1 M-A：条件替换 + 单一判定来源复用

| 问题 | 裁决 | 依据 |
|------|------|------|
| 三形态如何一次覆盖 | **共同前提收窄**——R1（Python float 除零抛）/ R2（numpy 除零 `inf`）/ R3（NaN·负比值无效）的前提都是 **close 不是「有限正数」**；判定前移后三种形态同路径跳过 | DESIGN D1「为什么一次覆盖三形态」 |
| 判定函数从哪来 | **复用 P-033 `is_valid_price`**（判据完全相同：有限正数）；新增 `is_valid_close` = 第二来源 = 漂移入口（低效排除 1） | 单一判定来源纪律 |
| `is not None` 保留还是省略 | **保留**——`is_valid_price` 返回 `bool` 而非 `TypeGuard[float]`，mypy 不窄化 `Optional[float]`，`abs(float - Optional[float])` 报错；**仅用于类型窄化**，语义被 `is_valid_price` 完全覆盖 | Step 4 mypy 正反例：good 写法 0 error / bad（省略 `is not None`）**2 errors**；`TypeGuard` 改造拒绝（需改 P-033 已验收签名，O-S2-P034-4） |
| 无效 close 处置 | **静默跳过**（不计算 ratio / 不告警 / **不改成交结果**）——数据质量监控属掩码层职责；打提示 = 新噪声（R2 教训） | 诊断与决策解耦；R-P034-1 披露监控信号变化 |
| 告警文案 / 阈值 | **逐字不变**（`{:.2%}` / `> 0.1`）；L318-324 零改动 | I1 合法价路径逐位不变 |

### 3.2 四项设计决策（D1-D4）

| 决策 | 内容 | 备选与取舍 |
|------|------|------------|
| **D1** | 差异校验前置 close 有效性判定：`if close_price is not None and is_valid_price(close_price):`（L316 注释含「P-034 D1」与三形态语义） | M 方案对比后一次覆盖三形态；守卫条件收窄而非新增拒绝分支 |
| **D2** | CI 独立 `lock-check` job（**不进 matrix**——uv 与 Python 版本无关，matrix 内重复 3 次）：`@v10.3.3` 精确钉 + `version: "0.11.14"`（与 `uv.lock` revision 同源）、**省略 `enable-cache`**（v10 语义 `'auto'`，只读 `--check` 缓存收益可忽略）、**无 `\|\| true`**（P-024 教训）、降级链 `pip install uv==0.11.14`（U-P034-1）、测试 job 零改动（仍 `pip install ".[dev]"`） | **F-S4-P034-1（P2）当轮修正**：设计稿 `@v6` 过时四个大版本，`gh api` 实测 latest = v10.3.3 |
| **D3** | 台账 8 处收口：U-P033-1 → **done**（D1 承接）/ U-P033-2、U-P014-3 → **已合并 U-P031-2**（单一跟踪源，P-028 先例）/ U-P033-3 → **已裁决不采纳**（P-025-4 先例）/ U-P014-1、U-P015-1、U-P016-1 → **建行 pending**（条件触发）/ 旧表 U-008 → **已合并 U-P021-2**；**D5 派生纪律成文**——批次关闭动作清单新增「本批新增 U-\*/O-\* 是否已在 §1.4 建行」 | P-030 / P-032 / P-028 / P-025-4 四类先例；不造门禁（遵守「不为判断造门禁」） |
| **D4** | 不改项五项：`TypeGuard` 改造 / 阈值 `0.1` 可配置化 / 告警文案格式 / `uv export --frozen`·`uv sync` / §1.4 全表重构 | 各有明确不改理由（O-P034-1~2 / O-S2-P034-4 / 低效排除 4/5 / O-R5-P031-1） |

### 3.3 不变式与门禁预测

- **I1-I6**：合法 close 逐位不变（V2/V3/golden）/ 无效 close 不改成交（V1/V4）/ 零新增 except·raise 且 AST 恒 22 / 公开签名零变更 / CI 失败即红 + 测试 job 零改动 / 台账 8 处全部有落点。
- 门禁预测：748 → **760**（12 实例）/ 测试文件 **84** / black **121** / mypy 37 不变 / golden 13 零重录——Step 6 预览与 Step 9 实测逐项命中。

---

## 4. 实施明细：两处代码落点 + 一处文档面

| 落点 | 决策 | 行为前 | 行为后 |
|------|------|--------|--------|
| `core/execution.py` L316-317 | D1 | `if close_price is not None:`（仅判 None——R1/R2/R3 全部穿透） | 条件替换为 `close_price is not None and is_valid_price(close_price)`；L318-324（ratio 计算 / 阈值 / warning 三行）**逐字未动**；P-033 守卫 L308-314 在前形成两道防线 |
| `.github/workflows/tests.yml` L48-59 | D2 | 仅 `test` job（L9-46），CI 无 uv 步骤 | 新增独立 `lock-check` job（`@v10.3.3` + `0.11.14`、无 `enable-cache`、`uv lock --check` 独立 step）；`test` job 四 step 逐行未动 |
| 台账 8 处 + CHANGELOG + ARCHITECTURE §9.2 | D3 | 8 项散落正文 / ARCHITECTURE 记「CI 使用 pip，不校验锁」 | §1.4 七行 + U-P031-2/旧表补注；ARCHITECTURE §9.2 L335 改「`lock-check` job 以 `uv lock --check` 校验锁与 pyproject 一致（失败即红，无 `\|\| true`），测试 job 仍用 pip 安装」；CHANGELOG `[Unreleased] Changed` 首条 |

**关键纪律**：`is_valid_price` 全仓 **1 定义（L153-161）+ 4 调用**（P-033 三处 + 本批 L317），零第二套判定；两处代码 hunk（`execution.py @@ -313,8 +313,8` / `tests.yml @@ -43,4 +43,17`）全部归因 D1/D2，**零游离行**（Step 10 Phase 3）；Step 10 E2 实测代码面新增 `raise` / `except` / `logger.` 全 **0**、公开签名删除 **0**。

---

## 5. 变更面与代码规模

### 5.1 逐文件读数（全区间 `fbed072..4b6eef0`，14 提交）

| 文件 | 性质 | numstat |
|------|------|---------|
| `core/execution.py` | D1 全落点（注释 + 条件替换） | **+2 / −2** |
| `.github/workflows/tests.yml` | D2 全落点（新增 job） | **+14 / −1** |
| `tests/test_p034_price_diff_guard.py` | 新建，5 函数 12 实例 | **+136 / −0** |
| 4 份批次文档 | RESEARCH +330 / DESIGN +251 / IMPL +347 / CHECKLIST +358 | 合计 **+1286** |
| 台账与同步 | PROGRESS +137/−2 / CHANGELOG +2/−1 / ARCHITECTURE +1/−1 | 合计 +140/−4 |

**全区间 10 文件 +1578 / −7**（提交后区间实测，`git diff --numstat`）；代码 diff **2 hunk** 逐一归因 D1/D2，零游离行。

### 5.2 关键纪律的落地证据（Step 10 + 异构终审双重复核）

| 纪律 | 证据 |
|------|------|
| 单一判定来源 | `is_valid_price` 全仓 1 定义 + 4 调用（AST 实证）；零第二套 `pd.isna` 组合 |
| 零 fail-fast / 零新增 except | 区间 diff 三条正则（`raise` / `except` / `logger.`）全 0；AST `except Exception` 恒 **22**；守卫为前置 `if`，不进异常漏斗 |
| 公开签名零变更 | `^-\s*def ` 全仓 **0**；`execute_order` / `is_valid_price` 均未动 |
| 合法价路径不变 | L318-324 零 hunk；golden **13 零重录**；既有 748 全绿 |
| 门禁真实可红 | C4 实证 exit 1；`tests.yml` 文件内 `\|\| true` / `continue-on-error` 零命中 |
| 零改动面 | tracker / pending / interfaces / agents / filter / scripts / cli / pyproject / uv.lock / golden——10 面名单核实零命中（`uv.lock` 未动 = 锁与 pyproject 一致性由 CI 门禁守护而非手工同步） |

---

## 6. 验证体系

### 6.1 测试规格（5 函数 / 12 实例，fixture 独立、零 `unittest.mock`）

| 用例 | 函数 | 实例 | 断言要点 |
|------|------|------|----------|
| V1 无效 close 六形态 | `test_v1_invalid_close_skips_diff_check` | 6（参数化） | `close ∈ {0.0, np.float64(0), nan, -5.0, inf, -inf}`：每例 `success is True` + `trade.price == 10.0` + `trade_log` 恰 1 笔 + caplog **零**「差异过大」**零**「交易执行失败」 |
| V2 合法价告警保留 | `test_v2_valid_close_keeps_warning` | 3（参数化） | `8.0` → **恰 1 条**含 `25.00%`；`7.0` → 1 条含 `42.86%`；`10.5` → **零告警**；三例均成交 |
| V3 `None` 回归 | `test_v3_none_close_unchanged` | 1 | `success is True`、零「差异过大」（原行为不变） |
| V4 R1 吞单直判 | `test_v4_zero_close_not_swallowed` | 1 | `open=10.0` / `close=0.0`（均 Python float）→ `success is True` + 1 笔 + 零 error（**红态：`success=False`**——R1 最直接读数） |
| V5 P-033 交互 | `test_v5_guard_interaction` | 1 | `open=NaN` / `close=0.0` → P-033 守卫先行：`success is False`、恰 1 条「执行价格无效」、零差异校验 |

### 6.2 红态精确口径（批次级机械相加，P-033 F-S8-P033-2 教训先行应用）

| 用例 | 实例 | 红态 | 说明 |
|------|------|------|------|
| V1 | 6 | **2 红**（`0.0` 抛异常吞单 / `np.float64(0)` 产生 `inf%` 告警） | 其余 4 例（nan / -5 / inf / -inf）**现状即无告警**——R3「静默失效」从外部与「跳过」不可区分，**如实归为回归保护**，不伪造红态 |
| V2 / V3 / V5 | 3+1+1 | 0 红 | 合法价告警 / None 回归 / P-033 交互均为回归保护 |
| V4 | 1 | **1 红** | R1 吞单的最直接读数 |
| **全批** | **12** | **3F / 9P** | 与 Step 6 红态预览探针逐项吻合；Step 9 实测 **3 failed / 9 passed → 12 passed** |

### 6.3 门禁前后对比

| 门禁 | 基线 | 终态 | 判定 |
|------|------|------|------|
| `pytest -q` | 748 passed | **760 passed**（172 warnings） | ✅ +12 |
| 测试文件数 | 83（全部 .py，含辅助模块） | **84**（`test_*.py` 81） | ✅ +1（口径补注 F-S6-P034-1） |
| `black --check core tests` | 120 unchanged | **121 unchanged**（新测试首轮重排 1 文件，O-I-P034-1 预判成立） | ✅ +1 |
| `mypy --explicit-package-bases --check-untyped-defs core` | 37 files 0 error | **37 files 0 error** | ✅ 持平 |
| golden G1-G7 | 13 passed | **13 passed，`tests/golden/` 零改动** | ✅ 零重录 |
| 回归子集 | `-k "golden or p027 or p029 or p031 or p033"` **74 passed** | 加 `p034` 后 **86 passed**（13+24+11+9+17+12） | ✅ 不回归（E8 判据 F-S9-P034-1 修正为精确等值） |
| I1 `except Exception`（十文件 AST） | 22 | **22** | ✅ 恒等 |
| `uv lock --check`（新增） | 本地 exit 0 / CI 无此步 | **exit 0**；CI `lock-check` job 四跑全绿；C4 实证可红 | ✅ 门禁闭合 |

### 6.4 盲区与回归面（Step 10 + 异构终审复扫）

- **本批新增面**（execution L316-324 前置 `if` / 新测试文件 / workflow 非 Python）严格启发 **0 命中**——零新增静默路径；既有浮出无新增（P-029/P-033 已登记项未变化）。
- **运行期复验（异构终审 E4，独立探针 7/7 PASS）**：本基座独立编写探针（非复用 Step 9 测试集）——R1 吞单修复（`success=True trades=1 errors=0`）/ R2 噪声消除（`diff_warns=0`）/ R3 静默跳过 / 合法价 25.00% 告警保留 / None 回归 / P-033 守卫交互 / `is_valid_price` 语义 8/8。

---

## 7. 质量过程：十步管线 + 异构终审补做

### 7.1 时间线

| Step | 产出 | 基座 | 结论 | CI run |
|------|------|------|------|--------|
| 1 RESEARCH | 判档修正 T1 + R3 三形态探针 + 台账 8 处取证 + uv 基线 + 方案矩阵 M-A + 六项低效排除 | DeepSeek-V4.1-Flash | 完成 | `43920327393` |
| 2 Review | E1-E3 复核 + **C1-C4 四项新证**（C2 取值写法敏感性 / C4 门禁可红实证） | DeepSeek-V4.1-Flash（**同基座独立复审**，RULE-5 不成立） | pass（1 P3 当轮回写 + 4 观察） | `43920705582` |
| 3 DESIGN | D1-D4 / I1-I6 / V1-V5 12 实例 / 红态精确口径 3F/9P | DeepSeek-V4.1-Flash | 完成 | `43920931702` |
| 4 Review | mypy 正反例（`is not None` 窄化必要性）+ `gh api` 版本机械核验 | DeepSeek-V4.1-Flash | pass（**1 P2 当轮回写 F-S4-P034-1** + 3 观察） | `43921206602` |
| 5 IMPL | B1-B4 + 逐文件精确锚点 + 台账 8 处定稿 + 七项低效排除 | DeepSeek-V4.1-Flash | 完成 | `43921422946` |
| 6 Review | 红态预览探针（3F/9P 逐项吻合）+ 门禁四项一致 | DeepSeek-V4.1-Flash | pass（1 P3 当轮回写 + 2 观察） | `43921931185` |
| 7 CHECKLIST | 五组 **37 项**零预填（A 8 / B 5 / C 7 / D 6 / E 11）+ 基线对拍 | DeepSeek-V4.1-Flash | 完成 | `43922094588` |
| 8 Review | 机械五项 + 对齐矩阵 A-G 全过 | DeepSeek-V4.1-Flash | pass（1 P3 当轮修正 + 2 观察） | `43922282542` |
| 9 TDD | 红 **3F/9P**（与预览逐项吻合）→ 绿 **12 passed**；门禁 760/84/121/37/13/22 + uv exit 0 | DeepSeek-V4.1-Flash | 全绿（1 P3 判据修正 + 1 观察） | `43923154391` / `43923862362`（回填） |
| 10 ADD + 终审 | Phase 0-4 + E1-E5 独立复跑 + 盲区复扫 | DeepSeek-V4.1-Flash | **pass，批次关闭**（1 P3 + 2 观察） | `43924423589` / `43925230603`（回填） |
| **U-P034-3 异构终审** | E1-E5 五项独立复核 + 运行期复验探针 **7/7** | **GLM-5.3-Flash（≠ 作者，异构成立）** | **pass（2 P3 当轮修正 + 1 观察），过程链全闭合** | `43929524333` / `43930053306`（回填） |

**RULE-5 异构性（与 P-033 相反的形态）**：P-034 作者与五轮复审者（Step 2/4/6/8/10）**全部为 DeepSeek-V4.1-Flash**——异构条件全程不成立，按 P-032 先例登记 U-P034-3 预留；2026-11-17 由 GLM-5.3-Flash 补做异构终审 pass。**同基座复审 + 异构终审两级形态在本仓均有完整先例（P-033 正向 / P-034 补做式）。**

### 7.2 发现台账（0 P0/P1 + 1 P2 + 7 P3，全部当轮处置；23 项观察全部登记）

| 来源 | ID | 级别 | 内容 | 处置 |
|------|----|------|------|------|
| Step 2 | F-S2-P034-1 | P3 | R1 可达性认知精化——pandas `to_dict()` / `dict(items())` 取值产生 Python `float`，R1 形态可达性**对取值写法敏感**（现 8 生产调用点全 `np.float64` 索引取值 → 不可达） | 当轮回写 RESEARCH §2.2 |
| Step 4 | **F-S4-P034-1** | **P2** | 设计稿 `setup-uv@v6` 过时四个大版本——`gh api .../releases/latest` 实测 **v10.3.3**；且 v10 `enable-cache` 输入语义为 `'auto'`（仅 GitHub-hosted 且非 release/tag/push 事件启用） | 当轮回写 D2：`@v10.3.3` + 省略 `enable-cache` |
| Step 6 | F-S6-P034-1 | P3 | 测试文件口径补注——「tests .py 84」为全部 `.py` 口径（含辅助模块），`test_*.py` 80 → 81 | 当轮回写头部基线注 |
| Step 8 | F-S8-P034-1 | P3 | 「`[待 Step 9]`」字面 39 未列构成（37 单元格 + 头部规则行 1 + §6 标签行 1）——机械校验会误判为预填不合规 | 当轮补注 §6 字面账目 |
| Step 9 | F-S9-P034-1 | P3 | E8 回归子集下限判据「≥ 74 passed」**无法检出 P-034 12 例漏跑**（86 = 74 + 12） | 当轮修正「86 passed」精确等值 |
| Step 10 | F-R5-P034-1 | P3 | **`O-P034-3` 引用幻觉**——从未定义（`1e-9` 边界实际 ID 是 `O-S4-P034-3`）；DESIGN §9.3/§9.4 两处 + CHECKLIST E11 一处 | 三处当轮修正 |
| U-P034-3 | **F-U3-P034-1** | P3 | **审计区间记录口径混用**——§11.2 记「9 提交 / −6」但其证据命令 `git log fbed072..f2e719b` 实测 **10 提交 / +1425/−7**；「9」仅与内容链 `fbed072..de0268d` 吻合（计数按内容链、diff 按区间端点两口径混写，同基座终审漏检） | 当轮补正 §11.2 + PROGRESS §3.39.9 |
| U-P034-3 | **F-U3-P034-2** | P3 | **D5 派生纪律执行缺口**——本批自立「新增 U-\*/O-\* 须在 §1.4 建行」，但 U-P034-1/2/3 仅散落 §3.39.9 正文未建行（散落正文同型第四次） | 当轮建三行（U-P034-1/2 pending、U-P034-3 done） |

观察 23 项：设计/规划期（R-P034-1 无效 close 监控信号变化**有意披露** / R-P034-2 CI 新增外部 action 钉版+降级链 / R-P034-3 `--check` 冷缓存偶发网络失败可重跑 / O-P034-1~2 阈值硬编码·文案不改 / F-D3-P034-1 `1e-9` 极小正价 `True` 与定义一致 / F-D3-P034-2 close 全 0 数据源无日志信号由掩码层承担 / F-I-P034-1 注释三形态追溯 / F-I-P034-2 `np.float64(0)` pandas-free 复现 inf / O-I-P034-1 新测试首轮 black）、Step 2（O-S2-P034-1 本机 `RUST_LOG=info` 使输出 131KB——CI 不受影响 / -2 action 版本核验移交 Step 4 / -3 外部 Python float 调用面 → U-P034-2 / -4 `bool` 非 `TypeGuard` 不改签名）、Step 4（O-S4-P034-1~3 `quiet` 输入 / `version-file` / `1e-9` 边界登记）、Step 6（O-S6-P034-1~2 V1/V4 断言重叠保留 / 红态 `RuntimeWarning` 修复后消失）、Step 9（F-S9-P034-2 black 重排 1 文件——O-I-P034-1 预判成立 / O-S9-P034-1 C7 行等 Step 10 关闭）、Step 10（O-R5-P034-1 `tests.yml` 无末尾换行与原文件一致非回归 / O-R5-P034-2 五轮同基座 → U-P034-3）、异构终审（O-U3-P034-1 终审区间 > 审计区间差额 2 流程提交正常时序）——全部登记，零丢弃。

### 7.3 最具价值的三项工作

1. **Step 1 探针把「R3 文案改进」升格为「三形态守卫」**——立项时 U-P033-1 只是「`inf%` 告警文案」改进（T3 候选）；Step 1 探针实证 **R1 `ZeroDivisionError` 被 except 捕获后合法价订单 `success=False`**（诊断吞单）——问题性质从「文案噪声」变为「守卫条件缺陷」。修复以**一个条件替换**同时消除三形态（吞单 / 噪声 / 静默失效），且合法价告警逐字保留——这是「诊断与决策解耦」裁决的直接产物：修复面是**收窄告警的适用条件**，而不是**扩大拒绝面**。
2. **Step 4 双机械核验（mypy 正反例 + `gh api` 版本实测）**——`is not None` 从「看似冗余」实证为「mypy 窄化必需」（省略则 `abs(float - Optional[float])` 2 errors；`TypeGuard` 改造因需动 P-033 已验收签名被拒）；F-S4-P034-1（全批唯一 P2）由 `gh api` 机械核验揪出 `@v6` 过时四个大版本——**外部事实不凭记忆写**，设计稿里所有「版本号 / API 形态」都须当轮实测。
3. **异构终审实锤同基座盲区（F-U3-P034-1 / F-U3-P034-2）**——同基座五轮复审 + ADD 审计全 pass 之后，异构复审仍以实测揪出两处 P3 记录缺陷（审计区间两口径混写 / 自立纪律自身漏执行）：RULE-5 不是仪式而是实测机制；**审计自产读数（区间计数 / 行数）同样必须给出可重放命令并独立复测**——「估算必错」教训的第四次先例（P-033 F-R5-P031-1 / P-034 净行数两次 / 本批审计区间）。

### 7.4 终审取证（Step 10 同基座 + U-P034-3 异构，两轮）

| 项 | Step 10（DeepSeek，同基座） | U-P034-3（GLM，异构） |
|----|------------------------------|------------------------|
| Phase 0 spec 质量门 | **5/5 = Tier A** | —（E1 锚点重放代之） |
| 完整性 / 保真度 | 10 文件 +1425/−7；2 hunk 零游离；IMPL §4 逐字吻合 | 12 提交区间对账吻合；E1 全锚点一致 |
| E1-E5 门禁独立复跑 | 760 / 121 / 37 / 86 / uv exit 0 / CI 四 job 全绿 | 760 / 121 / 37 / 86 / 12 / uv exit 0 / CI `43925230603` 四 job |
| 运行期复验 | —（由 12 实例测试集覆盖） | **独立探针 7/7 PASS**（非复用测试集） |
| 盲区复扫 | 零新增静默 | 零改动面零命中 + 台账落位核验 |
| 发现 | 0 P0-P2 + 1 P3 当轮修正 + 2 观察 | 0 P0-P2 + **2 P3 当轮修正** + 1 观察 |

---

## 8. 提交链与 CI

### 8.1 提交链（`279c86a` → `4b6eef0`，14 提交；Step 1-8 每 Step 一主提交，Step 9-10 与异构终审各含一 CI 回填）

| 阶段 | 提交（→ 回填） |
|------|----------------|
| Step 1 RESEARCH | `279c86a` |
| Step 2 Review | `47b7430` |
| Step 3 DESIGN | `8f7f05a` |
| Step 4 Review | `a0db635` |
| Step 5 IMPL | `05778d1` |
| Step 6 Review | `8f65170` |
| Step 7 CHECKLIST | `0285f25` |
| Step 8 Review | `642ec60` |
| Step 9 TDD（代码+文档一体） | `de0268d` → `f2e719b`（回填 CI + 净行数区间实测更正） |
| Step 10 ADD 审计 + 终审 | `499524e` → `7082c7a`（回填） |
| U-P034-3 异构终审 | `cf13f98` → `4b6eef0`（回填） |

### 8.2 CI 回收（14 run 全 success，零红灯遗留）

| run | 对应 | 结果 |
|-----|------|------|
| `43920327393` | Step 1 | success |
| `43920705582` | Step 2 | success |
| `43920931702` | Step 3 | success |
| `43921206602` | Step 4 | success |
| `43921422946` | Step 5 | success |
| `43921931185` | Step 6 | success |
| `43922094588` | Step 7 | success |
| `43922282542` | Step 8 | success |
| `43923154391` | **Step 9 代码落地（`lock-check` job 首跑）** | success |
| `43923862362` | Step 9 回填 | success |
| `43924423589` | Step 10 审计记录 | success |
| `43925230603` | Step 10 回填 | success |
| `43929524333` | **U-P034-3 异构终审记录** | success |
| `43930053306` | U-P034-3 回填（终态） | success |

每个提交各触发一次 run 且全部 success——无 docs-only 未登记缺口；全区间每个代码面均至少一次 success run 覆盖。

---

## 9. 边界、未决与后续

### 9.1 本批明确不做（七项低效排除 + D4 五项不改）

| 项 | 原因 |
|----|------|
| 为 close 新写 `is_valid_close` | 判据与 `is_valid_price` 完全相同 → 第二来源 = 漂移入口 |
| 差异校验降为 debug 级 | 丢失合法价 25% 差异告警（既有诊断能力） |
| 无效 close 打提示日志 | 变成新噪声（R2 教训）；监控归掩码层（R-P034-1 披露） |
| CI 增加 `uv export --frozen` | 超出 U-P024-2 单一判据 |
| CI 改 `uv sync` 安装依赖 | 切换安装路径风险高，非本批目标（测试 job 零改动 I5） |
| `TypeGuard` 改造 | 需改 P-033 已验收公共签名 + 调用点（O-S2-P034-4） |
| 台账全表重构 | 只补缺口，历史行不改（O-R5-P031-1 先例） |

### 9.2 遗留台账

| ID | 内容 | 状态 |
|----|------|------|
| U-P034-1 | `setup-uv` action 长期维护 vs `pip install uv` 降级链 | pending（触发：action 主版本升级 / 不可用时重验） |
| U-P034-2 | 外部调用方同时传 Python float 的 R1 面 | pending（触发：真实外部调用报告；现 8 调用点全 `np.float64` 不可达） |
| U-P034-3 | RULE-5 异构终审预留 | **done（2026-11-17，GLM-5.3-Flash 承接，pass）** |
| U-P033-2 / U-P014-3 | BUY 侧现金夹紧 | 已合并 **U-P031-2** 单一跟踪 |
| U-P031-2 | BUY 侧现金夹紧（队列路径） | pending（条件触发） |
| R-P034-1~3 | 监控信号变化 / 外部 action / `--check` 冷缓存 | 接受（各自披露 / 钉版 / 可重跑） |
| O-U3-P034-1 | 终审区间 > 审计区间差额 2 提交 | 登记不改（正常时序） |

### 9.3 对后续批次的启示

1. **判档规则 2 fail-closed 的实证**——「零行为风险」≠「零过程风险」：新增 CI 门禁改变的是 CI 的红绿语义（过程行为），强制 T1 是正确的；若按 T3 轻批走，D2 的 action 版本核验、C4 可红实证、B4 测试 job 零改动断言都不会存在。
2. **诊断与决策解耦**——差异校验是「诊断告警」不是「成交判定」；R1 吞单的根因是把诊断失败（除零异常）当成了决策失败（订单不成立）。修复方式是**收窄诊断的适用条件**，而不是给执行路径再加一道拒绝——后者会把「数据质量差」升级成「业务拒绝」，语义错位。
3. **门禁新增 = 外部事实密集区**——action 版本、输入语义、uv 二进制行为全部须机械核验（`gh api` / `action.yml` 实读）；「失败即红 + 无 `\|\| true` + 可红实证（C4）」三件套缺一不可（P-024 假门禁教训的完整落地）。
4. **类型窄化与业务判定分离**——`is not None` 服务 mypy（`bool` 非 `TypeGuard` 的现实约束），业务判定单一来源 `is_valid_price`；两者写在同一条件里但职责不同，审计时须分开归因（A1 锚点即如此）。
5. **台账纪律需要自指执行**——D5 派生纪律成文于本批，本批自身的 U-P034-1/2/3 仍漏建行（散落正文第四次同型）；「批次关闭动作清单」应把该检查固化为机械步骤，异构终审是最后一道兜底。
6. **同基座复审的自产读数盲区**——审计自己产出的区间计数 / 行数读数，五轮同基座复审无一质疑，异构终审以 `git rev-list --count` 机械复测才揪出；所有区间/计数类读数必须附**可重放命令**，且复审者应至少重放一条（而非只读结论）。

---

## 10. 结论

P-034 以 **代码 3 文件 +152/−3（其中 `execution.py` 仅 +2/−2）、零 fail-fast、零新增 except、公开签名零变更、golden 零重录** 的代价，把三件治理对象全部闭环：

- **正确性**：无效 close（None / 0 / NaN / ±inf / 负）由「抛异常吞单 / inf 噪声 / 静默失效」统一为「安静跳过」——合法价订单不再被诊断异常误杀（R1）、告警不再有 `inf` 读数（R2）、NaN 静默失效形态消除（R3）；合法价 25% / 42.86% 告警逐字保留（I1）；成交结果零改变（I2）；
- **复用**：复用 P-033 `is_valid_price` 单一判定来源（1 定义 + 4 调用），零第二套判据；`is not None` 仅为 mypy 窄化（正反例实证），与 P-033 已验收签名零冲突；
- **门禁**：CI 新增独立 `lock-check` job（`@v10.3.3` 精确钉 + `0.11.14` 同源钉、失败即红、无 `\|\| true`、C4 实证可红）——「pyproject 与锁不一致」由 CI 盲区变为红灯；ARCHITECTURE §9.2 同步订正；
- **台账**：8 处缺口全部有落点（1 done / 3 合并 / 1 不采纳 / 3 建行）；D5 派生纪律成文，异构终审补齐其自身执行缺口；
- **过程质量**：十步管线全部通过（五轮同基座复审 **0 漏检 P0/P1/P2**）+ 异构终审补做 pass（**1 P2 + 7 P3 全部当轮处置、23 项观察全部登记**；异构复审再实锤 2 P3 同基座漏检——记录口径类缺陷）；
- **可追溯**：四文档 + 本总结 + 14 提交链 + 14 次 CI 全绿 + 运行期复验探针 7/7，任一处可独立复跑。

**批次关闭。**
