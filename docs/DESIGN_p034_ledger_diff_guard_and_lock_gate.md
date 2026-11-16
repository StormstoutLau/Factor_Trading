# DESIGN：P-034 台账收口 · 价格差异校验守卫 · CI 锁门禁

> **批次**: P-034 · **T1**（强制升级：任务 C 新增 CI 门禁）
> **状态**: **Step 3 完成**（2026-11-17，基线 HEAD `47b7430`）
> **作者基座**: DeepSeek-V4.1-Flash（Step 4 复审须异构，RULE-5；若同基座则披露 + 预留 U-P034-3）
> **上游**: [RESEARCH_p034](RESEARCH_p034_ledger_diff_guard_and_lock_gate.md)（§2.2 三形态 / §6.1 类型链 / §7 三组 M-A / §11 Step 2 复审 pass：0 P0-P2 + 1 P3 当轮回写 + 4 观察）
> **设计对象**: `core/execution.py` 差异校验守卫 + `.github/workflows/tests.yml` 新增 `lock-check` job + `docs/PROGRESS.md` §1.4 台账 8 处收口

---

## 1. 设计目标

| 来源 | 缺陷 / 任务 | 设计出口 |
|------|-------------|----------|
| R1（P3） | `close_price=0.0`（Python `float`）→ `ZeroDivisionError` → 合法价订单 `success=False`（诊断吞单） | **D1** close 有效性守卫（同一判定覆盖） |
| R2（P3） | `close_price=np.float64(0)` → `inf` → 「差异=inf%」告警噪声（U-P033-1） | **D1** |
| R3（P3） | `close` 为 NaN / 负 → 比值 NaN / 负 → 校验静默失效 | **D1** |
| R4 | 台账 8 处缺口 | **D3** |
| R5 | 锁漂移无 CI 拦截（U-P024-2） | **D2** |

**约束**：合法 close 路径**逐位不变**（golden 13 零重录）；公开签名零变更；新增 `except` / `raise` 均为 **0**；测试 job 行为不变（仍 `pip install ".[dev]"`）。

---

## 2. 决策详述

### D1（修 R1/R2/R3）：差异校验前置 close 有效性判定

**决策**：`core/execution.py` 差异校验（L316-324）的判定条件由 `if close_price is not None:` 改为：

```python
            # 价格合理性检查（P-034：close 无效时跳过——避免 inf 噪声 / 除零吞单 / NaN 静默）
            if close_price is not None and is_valid_price(close_price):
                price_diff_ratio = abs(execution_price - close_price) / close_price
                if price_diff_ratio > 0.1:  # 10%阈值
                    logger.warning(...)   # 原文逐字不变
```

| 要素 | 决策 | 依据 |
|------|------|------|
| 判定函数 | **复用 `is_valid_price`**（P-033 单一判定来源） | 判据完全相同（有限正数）；新增函数 = 第二来源 = 漂移入口（§7 低效排除 1） |
| 保留 `close_price is not None` | **保留** | `is_valid_price` 返回 `bool` 而非 `TypeGuard[float]` → mypy 不窄化 `Optional[float]`，`abs(float - Optional[float])` 报错。**仅用于类型窄化**，语义被 `is_valid_price` 完全覆盖 |
| 无效 close 的处置 | **静默跳过**（不计算 ratio / 不告警 / 不改成交结果） | ① 数据质量监控属掩码层职责（P-010/P-012）；② 打提示会变成新噪声（R2 的教训） |
| 告警文案 / 阈值 | **逐字不变**（`{:.2%}` / `> 0.1`） | 合法价路径零改动（I1） |

**为什么一次覆盖三形态**：R1（除法在 Python float 下抛）、R2（numpy 下产生 `inf`）、R3（NaN / 负产生无效比值）的共同前提都是 **close 不是「有限正数」**；判定前移后三种形态同路径跳过。

### D2（修 R5）：CI 独立 `lock-check` job

**决策**：`.github/workflows/tests.yml` 新增独立 job（不进 matrix）：

```yaml
  lock-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up uv
        uses: astral-sh/setup-uv@v10.3.3
        with:
          version: "0.11.14"
      - name: Check lockfile is up to date
        run: uv lock --check
```

| 要素 | 决策 | 依据 |
|------|------|------|
| 独立 job | **是** | 与 Python 版本无关（uv 是独立二进制）→ matrix 内会重复 3 次；独立 red 归因清晰 |
| action 版本 | **`@v10.3.3`（精确钉）** | **Step 4 修正（F-S4-P034-1）**：`gh api repos/astral-sh/setup-uv/releases/latest` 实测最新 **v10.3.3**；原稿 `@v6` 为过时主版本 |
| uv 版本 | **钉 `0.11.14`** | 与 `uv.lock` `revision = 3` 同源；避免 uv 二进制升级导致 `--check` 语义漂移（U-P021-3 锁升级节奏另行触发）；`gh api repos/astral-sh/uv/releases/tags/0.11.14` 命中 |
| `enable-cache` | **省略** | v10 `action.yml` 中该输入语义为 `'auto'`（仅 GitHub-hosted runner 且非 release/tag/push 事件启用），本 job 只做只读 `--check`，缓存收益可忽略 → 最小面 |
| 失败语义 | **失败即 job 失败，禁 `|| true`** | P-024 教训：`|| true` 使门禁恒绿（假门禁） |
| 降级链（F3） | `astral-sh/setup-uv@v10.3.3` 不可用 → `pip install uv==0.11.14` + `uv lock --check` | U-P034-1 跟踪 |
| 不改测试 job | 仍 `pip install ".[dev]"` | 本批只补门禁，不切安装路径（§7 低效排除 5） |

**门禁有效性已在 Step 2 C4 实证**：临时目录改 `numpy` 约束 → `uv lock --check` exit 1（文案「The lockfile at 'uv.lock' needs to be updated, but '--check' was provided」）。

### D3（修 R4）：台账 8 处收口

| # | 对象 | 处置 | 先例 |
|---|------|------|------|
| 1 | **U-P033-1**（R3 告警文案） | 建行，状态 **done**（本批 D1 承接） | P-030 / P-032 |
| 2 | **U-P033-2**（BUY 侧现金夹紧） | 建行，状态「**已合并至 U-P031-2**」，不单独触发 | P-028（U-P021-1 → U-P024-2） |
| 3 | **U-P033-3**（账目层守卫，不采纳） | 建行，状态「**已裁决不采纳**」 | P-025-4（U-P025-4 已裁决不做） |
| 4 | **U-P014-1**（停牌 / 涨跌停掩码语义变更） | 建行，**pending**（条件触发） | P-030 |
| 5 | **U-P014-3**（队列路径买侧现金校验） | 建行，状态「**已合并至 U-P031-2**」 | P-028 |
| 6 | **U-P015-1**（Backtrader ↔ V2 第二例对拍） | 建行，**pending**（四元块照录 RESEARCH_p015 §6） | P-030 |
| 7 | **U-P016-1**（current-NAV 规格费用语义 rate>0） | 建行，**pending**（触发条件 = U-P015-1 立项） | P-030 |
| 8 | **U-008**（numba JIT CI 覆盖） | 旧表行标「**已合并至 U-P021-2**」，保留历史 | P-028 |

**D3 附则（D5 派生纪律）**：PROGRESS §3.39 记录须新增一条「**批次关闭动作清单**」——本批新增的 U-\* / O-\* 必须在 §1.4 建行后方可宣告关闭。三次同型（P-030 / P-032 / P-034）后以文字纪律收口（不造门禁，遵守「不为判断造门禁」）。

> **P-035 扩展注（2026-11-17，原句保留）**：本纪律被待办分析发现仍不完整——本批任务 B 的实现项 **U-P024-2**（CI `uv lock --check` 门禁）未随批转 done（D3 八处清单只含「新增 / 合并 / 不采纳」项，未含「本批实现/承接的既有项」），同型缺口第 5 次。P-035 将批次关闭动作清单扩为**两项**：**(a)** 本批新增 U-\* / O-\* 是否已在 §1.4 建行；**(b)** 本批实现/承接的既有台账项是否已转 done / 已合并。见 [PROGRESS §3.40](PROGRESS.md)。

### D4（不改项）

| 项 | 不改理由 |
|----|----------|
| `is_valid_price` → `TypeGuard[float]` | 需改 P-033 已验收公共签名 + 3 调用点，收益仅少写半个条件（O-S2-P034-4） |
| 阈值 `0.1` 可配置化 | 无需求（O-P034-1） |
| 差异告警文案格式 | 跳过路径已消除 `inf%`（O-P034-2） |
| CI 增加 `uv export --frozen` / `uv sync` | 超出 U-P024-2 单一判据；切换安装路径风险高（§7 低效排除 4/5） |
| §1.4 全表格式重构 | 台账只补缺口，历史行不改（O-R5-P031-1 先例） |

---

## 3. 不变式 I1-I6

| ID | 不变式 | 验证出口 |
|----|--------|----------|
| I1 | 合法 close（有限正数）路径：`price_diff_ratio` 与告警输出**逐位不变** | V2 / V3 / golden 13 零重录 |
| I2 | 无效 close（`None` / `0` / `NaN` / `±inf` / 负）→ 不计算 ratio、不打「差异过大」、**不改变成交结果** | V1 / V4 |
| I3 | 零新增 `except` / 零新增 `raise`；`except Exception`（P-029 十文件口径）恒 **22**；`core/` 新增 except = 0 | 门禁 + `git diff` |
| I4 | 公开签名零变更（`execute_order` / `is_valid_price` 均不动） | `git diff \| Select-String '^-\s*def '` = 0 |
| I5 | CI：`lock-check` 失败即红（无 `|| true`）；测试 job（安装 / fixture / pytest / mypy）**零改动** | workflow diff + C4 实证 |
| I6 | 台账 8 处缺口全部有落点；U-P033-1 = done / U-P033-3 = 不采纳 / U-P033-2·U-P014-3 → U-P031-2 / U-008 → U-P021-2 | 读回 §1.4 |

---

## 4. 验证契约 V1-V5（12 实例）

| ID | 用例 | 构造 | 断言 |
|----|------|------|------|
| V1 | 无效 close 六形态（参数 6） | 零成本 `ExecutionSimulator(OPEN)`；`open=10.0`（Python float）；`close ∈ {0.0, np.float64(0), nan, -5.0, inf, -inf}` | 每例 `success=True` 且 `trade.price == 10.0`；**零「差异过大」告警**；**零 `ZeroDivisionError` / 零「交易执行失败」**；`trade_log` 恰 1 笔 |
| V2 | 合法 close 差异告警保留（参数 3） | `close ∈ {8.0, 7.0, 10.5}`，`open=10.0` | `8.0` → **1 条**告警且含 `25.00%`；`7.0` → 1 条含 `42.86%`；`10.5` → **零告警**；三例均 `success=True` |
| V3 | `close=None` 回归 | `close=None` | `success=True`、零「差异过大」告警（原行为不变） |
| V4 | R1 吞单红态 | `open=10.0` / `close=0.0`（均 Python float） | `success=True`；`trade_log` 1 笔；无 `logger.error`（**红态：`success=False`**） |
| V5 | P-033 守卫交互回归 | `open=NaN`, `close=0.0` | P-033 守卫先行：`success=False`、`trade=None`、仅 1 条「执行价格无效」、**零差异校验** |

**红态精确口径（批次级，P-033 F-S8-P033-2 教训）**：

| 用例 | 实例 | 红态 | 说明 |
|------|------|------|------|
| V1 | 6 | **2 红**（`0.0` 抛异常吞单 / `np.float64(0)` 产生 `inf%` 告警） | 其余 4 例（`nan` / `-5.0` / `inf` / `-inf`）**现状即无告警**——R3 的「静默失效」无法从外部与「跳过」区分，属**回归保护**而非红态验证 |
| V2 | 3 | 0 红（全部通过） | 合法价告警能力不得回归 |
| V3 | 1 | 0 红 | `None` 原行为即跳过 |
| V4 | 1 | **1 红**（`success=False` / 零入账） | R1 吞单的最直接读数 |
| V5 | 1 | 0 红 | P-033 守卫交互回归保护 |
| **全批** | **12** | **3 红 / 9 通过** | 红态 = 2 + 0 + 0 + 1 + 0 = 3 |

> **为何不把 R3 判为红**：修复前后「无告警 + 成交」这两个外部可观测读数完全一致；差异只在「是否执行除法」这一内部行为。无 mock 条件下不可断言（项目零 `unittest.mock` 纪律），故如实归为回归保护，不伪造红态（P-031 F-S9-P031-3 先例）。

**门禁目标**：pytest **748 → 760**（+12）；tests 文件 **83 → 84**；black **120 → 121**；mypy **37 files 0** 不变；golden **13 零重录**；AST `except Exception` 恒 **22**。

---

## 5. 风险、未决与观察

| ID | 类型 | 内容 | 处置 |
|----|------|------|------|
| R-P034-1 | 风险 | `close=0` / NaN / 负 从「告警或抛异常」变为「静默跳过」——若有人依赖该告警做监控会失信号 | 有意（R2 噪声 / R3 静默本身不可用）；监控归掩码层；文档披露 |
| R-P034-2 | 风险 | CI 新增外部 action | 钉 `0.11.14` + 降级链；失败即红零容忍 |
| R-P034-3 | 风险 | `--check` 需解析索引（CI 冷缓存） | 只读检查不改锁；偶发网络失败可重跑，不接受 `|| true` |
| U-P034-1 | 未决 | `setup-uv` action 长期维护 vs `pip install uv` | 触发：action 主版本升级 / 不可用 |
| U-P034-2 | 未决 | 外部调用方同时传 Python float 的 R1 面 | 触发：真实外部调用报告 |
| U-P034-3 | 未决 | **本批 RULE-5 异构终审预留**（Step 2 复审为同基座） | 触发：非 DeepSeek 基座可用时 |
| O-P034-1 / O-P034-2 | 观察 | 阈值硬编码 / 文案 `{:.2%}` | 不改 |
| O-S2-P034-1~4 | 观察 | `RUST_LOG=info` 输出膨胀 / `setup-uv` 待核验 / 外部调用面 / `bool` vs `TypeGuard` | 登记 |

---

## 6. 批量切分与回退点

| 批 | 内容 | 回退 |
|----|------|------|
| **B1** | `core/execution.py` D1 守卫 + 新测试 `tests/test_p034_price_diff_guard.py`（V1-V5 / 12 实例） | 单行条件回退（`is_valid_price` 判定删除即还原） |
| **B2** | `.github/workflows/tests.yml` 新增 `lock-check` job | 删 job（4 步） |
| **B3** | `docs/PROGRESS.md` §1.4 台账 8 处 + CHANGELOG + ARCHITECTURE §9.2 补 CI 门禁说明 | docs |
| **B4** | 全量门禁 + IMPL/CHECKLIST/PROGRESS 回填 | —— |

B1 与 B2 相互独立；B3 依赖 B1（U-P033-1 关闭）与 B2（门禁说明）。

---

## 7. 设计期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-D3-P034-1 | 观察 | `is_valid_price` 对 `1e-9` 返回 `True`（C1）——极小正价被视为可成交；不是本批引入，且与「有限正数」定义一致 | 不改（`O-S4-P034-3` 登记） |
| F-D3-P034-2 | 观察 | 无效 close 静默跳过意味着「close 全为 0 的数据源」不再有任何日志信号 | 由掩码层 + 数据质量检查承担；R-P034-1 已披露 |

---

## 8. 下一 Step

**Step 4 独立 Review（RULE-5 要求异构基座）**——复核重点：

1. D1 条件写法（`is not None and is_valid_price`）是否等价于规格，mypy 能否通过；
2. D2 CI job 形态：`setup-uv@v6` + `version: 0.11.14` 是否可解析（版本真实性），`enable-cache` 语义；
3. D3 台账处置是否合先例、是否有遗漏的散落项；
4. V1-V5 是否覆盖 R1/R2/R3 三形态与 P-033 交互，红态豁免（V3 / V5）是否标注；
5. 门禁推算（748+12=760 / 84 / 121 / 37 / 13 / 22）是否正确；
6. 是否存在「无效 close 静默」导致的观测缺口（R-P034-1 是否已充分披露）。

---

## 9. Step 4 独立 Review 记录（2026-11-17）

> **基座**: **DeepSeek-V4.1-Flash**——与本文作者**同源** → **RULE-5 异构条件不成立**，本轮为**同基座独立复审**（RULE-4 披露）；异构终审仍由 **U-P034-3** 跟踪。
> **复审对象**: `8f7f05a`（DESIGN_p034 提交版）；复审时点 HEAD `8f7f05a`
> **方法**: E1 锚点机械复核 + E2 外部事实核验（`gh api` 版本查询 + mypy 窄化正反例）+ E3 六项裁决

### 9.1 E1 锚点机械复核（八项）

| # | DESIGN 声称 | 实查 | 结果 |
|---|-------------|------|------|
| A1 | 差异校验 L316-324、守卫插入条件 | 读码 L316 `# 价格合理性检查` / L317 `if close_price is not None:` / L320-324 warning | ✅ |
| A2 | P-033 守卫 L308-315 在前 | 读码 | ✅ |
| A3 | `is_valid_price` 定义位置（L153-161）与签名 `Optional[float] -> bool` | 读码 | ✅ |
| A4 | `execute_order` 签名含 `close_price: Optional[float] = None` | 读码 L280 | ✅ |
| A5 | CI 现有单 job `test` + matrix + `pip install ".[dev]"` | `tests.yml` L9-46 | ✅ |
| A6 | `uv.lock` `version = 1` / `revision = 3` | 头部 | ✅ |
| A7 | §1.4 台账 8 处缺口位置（P-033 行 / U-P031-2 行 / 旧表 U-008） | 读码 L75/L80/L158 | ✅ |
| A8 | 红态口径表（V1 2 红 / V4 1 红 / 其余通过 = 3 红 9 通过） | 按 §4 构造逐例推演，与 §4 表格自洽 | ✅ |

### 9.2 E2 外部事实核验（三项）

| 项 | 方法 | 读数 | 结论 |
|----|------|------|------|
| **mypy 窄化必要性** | `%TEMP%\p034_mypy_probe.py`：`good` = `is not None and is_valid_price(...)`；`bad` = 仅 `is_valid_price(...)` | `good` **0 error**；`bad` **2 errors**（`Unsupported operand types for / ("float" and "None")` + 同 for `-`） | **D1 保留 `is not None` 是必需而非冗余**（机械证据） |
| **`setup-uv` 主版本** | `gh api repos/astral-sh/setup-uv/releases/latest --jq .tag_name` | **`v10.3.3`** | 原稿 `@v6` **过时** → **F-S4-P034-1 当轮回写** |
| **uv `0.11.14` 存在性** | `gh api repos/astral-sh/uv/releases/tags/0.11.14 --jq .tag_name` | **`0.11.14`** 命中 | 钉版可解析 |
| **v10 inputs 语义** | `gh api ".../contents/action.yml?ref=v10.3.3"` + base64 解码 | `version`（uv 版本）存在；`enable-cache` 描述为 `'auto' enables caching on GitHub-hosted runners except …` | `enable-cache: true` 语义已变 → **省略该输入**（最小面） |

### 9.3 E3 六项裁决（对应 §8）

| # | 复核点 | 裁决 |
|---|--------|------|
| 1 | D1 条件写法与 mypy | **成立且必要**——E2 正反例机械证明 `is not None` 承担类型窄化；语义等价性由 Step 2 C3 逐位一致保证 |
| 2 | D2 action 版本 | **原稿错误已修正**——`@v6` → `@v10.3.3`（精确钉）；`enable-cache` 省略；降级链保留 |
| 3 | D3 台账处置完整性 | **成立**——8 处与 Step 1 §2.1 一一对应；无新增散落项（复扫 `U-P0` 前缀行全部有主行） |
| 4 | V1-V5 覆盖与红态豁免 | **成立**——R1（V4 直判）/ R2（V1-`np0`）/ R3（V1 四例，诚实标注为回归保护）/ 合法价（V2 ×3）/ `None`（V3）/ P-033 交互（V5）；红态 3 / 通过 9 与批次口径自洽 |
| 5 | 门禁推算 | **全部正确**——748 + 12 = **760**；83 + 1 = **84**；120 + 1 = **121**；mypy 37（无新源文件，测试文件不入门禁）；golden 13 零重录；AST 22（D1 为前置 `if`，零新增 except） |
| 6 | 静默观测缺口 | **已充分披露**——R-P034-1 明写「若有人依赖该告警做监控会失信号」，并指向掩码层职责；`O-S4-P034-3` 登记 `1e-9` 边界 |

### 9.4 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S4-P034-1** | **P2** | D2 的 `astral-sh/setup-uv@v6` **过时**（实测最新 **v10.3.3**），且 v10 中 `enable-cache` 语义为 `'auto'`——照原稿落地会引用旧主版本并使用语义已变的输入 | **当轮回写 D2**（`@v10.3.3` + 省略 `enable-cache`，已改） |
| O-S4-P034-1 | 观察 | `setup-uv` 提供 `quiet` 输入可抑制 info 级日志（本批 CI 无 `RUST_LOG`，不需要） | 登记 |
| O-S4-P034-2 | 观察 | `version-file` 输入可自动从 `uv.toml` / `pyproject.toml` 读取 uv 版本；本批无 `uv.toml` → 仍显式 `version` | 登记 |
| O-S4-P034-3 | 观察 | `is_valid_price` 对 `1e-9` 放行（极小正价）——语义一致的边界，非缺陷 | 登记（F-D3-P034-1 同源） |

### 9.5 结论与 Step 5 前置条件

**结论**: **pass**（0 P0/P1 / **1 P2 当轮回写** / 3 观察）——D1 经 mypy 正反例证明写法必要、D2 版本与输入语义经外部 API 核验并修正、D3 与 V1-V5 覆盖完备、门禁推算全对。
**RULE-5 声明**: 同基座独立复审（作者=复审=DeepSeek-V4.1-Flash），异构终审登记 **U-P034-3** 不变。

**Step 5 IMPL 前置条件**:
1. D1 按 `if close_price is not None and is_valid_price(close_price):` 落地，**不得**省略 `is not None`；
2. D2 按 `@v10.3.3` + `version: "0.11.14"` 落地，**省略** `enable-cache`，**禁 `|| true`**；
3. 测试 12 实例按 §4 与红态口径表执行：B1 红态预期 **3 failed / 9 passed**（V1-2 + V4），逐批留证（F5 两读数）；
4. 台账 8 处与 CHANGELOG / ARCHITECTURE §9.2 在 B3 一并回写。
