# IMPL：P-034 台账收口 · 价格差异校验守卫 · CI 锁门禁

> **批次**: P-034 · **T1**（强制升级：新增 CI 门禁）
> **上游**: [DESIGN_p034](DESIGN_p034_ledger_diff_guard_and_lock_gate.md)（D1-D4 / I1-I6 / V1-V5 / §9 Step 4 复审 pass：1 P2 当轮回写 + 3 观察）
> **状态**: **Step 5 实施规划**（2026-11-17，基线 HEAD `a0db635`）
> **代码证据时点**: 实施前 HEAD `a0db635`；§4 全部锚点为**实施前行号**

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（代码 / 配置） | `core/execution.py`（1 个条件行 + 1 行注释）、`.github/workflows/tests.yml`（新增 10 行 job） |
| 变更文件（测试） | `tests/test_p034_price_diff_guard.py`（新增，5 函数 / 12 实例） |
| 变更文件（文档） | 本文件 / `docs/PROGRESS.md`（§1.4 台账 8 处 + §3.39.x）/ `CHANGELOG.md` / `docs/ARCHITECTURE.md`（§9.2 一句） |
| 零改动面 | `core/engine_v2.py` / `core/tracker.py` / `core/pending.py` / `core/interfaces.py` / `agents/` / `filter/` / `scripts/` / `cli.py` / `pyproject.toml` / `uv.lock` / `tests/golden/*.json` / `tests/test_p029_*.py` / `tests/test_p031_*.py` / `tests/test_p033_*.py` |
| 行为变更 | **1 处（仅诊断面）**：`close_price` 无效时差异校验跳过（不再产生 `inf%` 告警 / 不再抛 `ZeroDivisionError` / 不再静默计算 NaN 比值）；账目与成交结果**不变** |
| 门禁口径 | `MPLBACKEND=Agg` + Python312：pytest **748 → 760**（+12）；`tests/` .py **83 → 84**（**口径 = `tests/` 下全部 `.py`**，含 `_golden_cases.py` / `_synth_fixture.py` / `_reference_impl.py` 等辅助模块；`test_*.py` 为 **80 → 81**——F-S6-P034-1）；black `--check core tests` **120 → 121**；mypy `core` **37 files 0**（不变）；golden G1-G7 **13 零重录**；`except Exception` 恒 **22** |

**四条不可越界的前提**：

1. **合法 close 逐位不变**：有限正数 close 的 `price_diff_ratio` 计算式与告警文案（含 `{:.2%}`）零改动。
2. **`is not None` 不可省略**：mypy 窄化必需（Step 4 E2 正反例机械证据：`bad` 2 errors）。
3. **`is_valid_price` 单一判定来源**：全仓 1 定义 + **3 → 4 调用**（新增 L317）；禁止为 close 新写判定。
4. **CI 门禁禁 `|| true`**：失败即 job 失败（P-024 假门禁教训）。

---

## 2. 任务拆解

| ID | 批次 | 任务 | 对应 | 产出 |
|----|------|------|------|------|
| **B1** | 代码 | `core/execution.py`：差异校验条件改 `close_price is not None and is_valid_price(close_price)` + 注释行 | D1 | 1 文件 **+2/−1**（估） |
| **B1t** | 测试 | V1（无效 close 6）+ V2（合法 3）+ V3（None）+ V4（R1 吞单）+ V5（P-033 交互） | V1-V5 | +12 实例 |
| **B2** | CI | `.github/workflows/tests.yml` 新增独立 `lock-check` job | D2 | 1 文件 **+12/−0**（估） |
| **B3** | 文档 | §1.4 台账 8 处 + `CHANGELOG` + `ARCHITECTURE §9.2` | D3 | docs |
| **B4** | 文档 | 全量门禁 + 本文件 §11 实测回填 + PROGRESS §3.39.4 + Step 7 CHECKLIST 前置 | —— | docs |

**计数**：12 实例 = V1 6 + V2 3 + V3 1 + V4 1 + V5 1 → `748 + 12 = 760`。

---

## 3. 实施顺序与依赖

```text
B1（守卫条件）──→ B1t（V1-V5 红→绿）
B2（CI job）  ── 独立（不依赖 B1）
B1t + B2 ──→ B3（台账 8 处 + CHANGELOG + ARCHITECTURE）
B3 ──→ B4（全量门禁 + 回填）
```

- **B1 先于 B1t**：测试红态需在改代码前采集。
- **B2 独立**：workflow 改动不影响 pytest。
- **B3 依赖 B1 + B2**：U-P033-1 的 done 需 D1 落地；ARCHITECTURE 措辞需 `lock-check` 已存在。

**红态预算（批内逐实例，DESIGN §4 口径）**：B1t 首跑预期 **3 failed / 9 passed**——V1 中 `0.0`（吞单）与 `np.float64(0)`（`inf%` 告警）两例失败，V4 一例失败；其余 9 例通过（含 V1 `nan`/`-5`/`inf`/`-inf` 四例与 V2/V3/V5，均为回归保护）。**不得**把 4 例「静默」误报为红态失败。

---

## 4. 精确变更规格

> 锚点为实施前 HEAD `a0db635`；净行数以 `git diff --numstat` 为准（B4 回填）。

### 4.1 `core/execution.py` —— 差异校验条件（L316-317）

**位置**：L316 `# 价格合理性检查` 注释行 + L317 `if close_price is not None:`。

**改前**：

```python
            # 价格合理性检查
            if close_price is not None:
```

**改后**：

```python
            # P-034 D1：价格合理性检查（close 无效时跳过——避免 inf 噪声 / 除零吞单 / NaN 静默）
            if close_price is not None and is_valid_price(close_price):
```

**约束**：L318-324（ratio 计算 / 阈值 / warning）**逐字不动**；不新增 `except`；不新增函数。

### 4.2 `.github/workflows/tests.yml` —— 新增 `lock-check` job

**位置**：文件末尾（`test` job 之后，同级缩进 2 空格）。

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

**约束**：禁止 `|| true` / `continue-on-error`；不改 `test` job 任何行；不新增 `[tool.uv]`。

### 4.3 `docs/PROGRESS.md` §1.4 —— 台账 8 处

**① 新增 7 行**（插在 P-034 行之后、`| U-D1(P-011) |` 之前）：

```markdown
| U-P033-1 | R3 `close=0` 差异告警文案（`inf%`） | [DESIGN_p033 §7](DESIGN_p033_pending_order_price_validation.md) D6；无账目污染，仅告警噪声 | **done（2026-11-17 由 P-034 承接）**：D1 close 有效性守卫——无效 close 静默跳过（同时消除 `ZeroDivisionError` 吞单与 NaN 静默），见 §3.39.4 | P3 |
| U-P033-2 | BUY 侧现金夹紧 | [DESIGN_p033 §7](DESIGN_p033_pending_order_price_validation.md)；与 U-P031-2 / U-P014-3 同源 | **已合并（2026-11-17，P-034 台账收口）**：统一由 **U-P031-2** 单一跟踪 | P3 |
| U-P033-3 | 账目层（`tracker.execute_trade`）价格守卫 | [DESIGN_p033 §7](DESIGN_p033_pending_order_price_validation.md)；账目层堵漏会掩盖上游数据错误且 V3 共用该层 | **已裁决不采纳**（同 O-P031-1 口径），2026-11-17 P-034 建行归档 | P3 |
| U-P014-1 | 停牌 / 涨跌停掩码语义变更 | [DESIGN_p014 §1](DESIGN_p014_suspension_accounting.md)（非目标）；P-014 不改变掩码语义 | pending（条件触发：需要变更停牌/涨跌停判定口径） | P3 |
| U-P014-3 | 队列路径买侧现金校验 | [DESIGN_p014 §1](DESIGN_p014_suspension_accounting.md)（非目标）；P-031 D3 仅修 SELL 侧 | **已合并（2026-11-17，P-034 台账收口）**：统一由 **U-P031-2** 单一跟踪 | P3 |
| U-P015-1 | Backtrader ↔ V2 第二例对拍 | [RESEARCH_p015 §6](RESEARCH_p015_external_benchmark.md) 四元块；判据 = 首例方法论闭环报告落档；附加前置 = U-P016-1 费用语义 | pending（条件触发：需要第二框架对照） | P3 |
| U-P016-1 | current-NAV 规格的费用语义（`cost_rate>0`） | [RESEARCH_p016 §6](RESEARCH_p016_p015_review_fixes.md) 四元块；现 `simulate_vbt_spec` 对 `rate>0` fail-fast | pending（触发：U-P015-1 立项时一并定义） | P3 |
```

**② 补注 U-P031-2 行尾**（追加到「状态」列）：

```
；**2026-11-17 注记（P-034 台账收口）**：U-P014-3 与 U-P033-2 同源已并入本行，本行为**单一跟踪源**
```

**③ 补注旧表 U-008 行尾**（追加到「当前倾向」列）：

```
。**2026-11-17 注记（P-034）**：与 §1.4 U-P021-2 同源，统一由后者**单一跟踪**，本行不再单独触发
```

### 4.4 `CHANGELOG.md` —— `[Unreleased]` 条目

在 `### Changed` 首条之前插入：

```markdown
- **P-034 价格差异校验守卫 + CI 锁门禁**: `execute_order` 的价格合理性检查在 `close_price` 无效（`None` / `0` / `NaN` / `±inf` / `≤0`）时跳过——消除 `close=0` 时 `ZeroDivisionError` 吞单（Python `float` 形态）、`inf%` 告警噪声（numpy 形态）与 NaN/负值下校验静默失效；合法 close 路径逐字不变（golden 13 零重录）。CI 新增独立 `lock-check` job（`astral-sh/setup-uv@v10.3.3` + `uv lock --check`，禁 `|| true`）拦截锁漂移；测试 **748 → 760 passed**、测试文件 83 → 84
```

### 4.5 `docs/ARCHITECTURE.md` §9.2 —— 锁纪律句订正（L335）

**改前**：`…修改 [project].dependencies 或 extras 后须运行 uv lock 并提交 uv.lock；CI 使用 pip，不校验锁。…`

**改后**：`…修改 [project].dependencies 或 extras 后须运行 uv lock 并提交 uv.lock；**CI 的 lock-check job 以 `uv lock --check` 校验锁与 pyproject 一致（失败即红）**，测试 job 仍用 pip 安装。…`

### 4.6 不改动清单（复核留证）

| 位置 | 状态 |
|------|------|
| L318-324（ratio / 阈值 / warning 文案） | 逐字不动 |
| L308-315（P-033 守卫） | 不动 |
| L153-161（`is_valid_price`） | 不动（签名与实现均不改） |
| `test` job（L9-46） | 逐行不动 |
| `pyproject.toml` / `uv.lock` | 不动 |

---

## 5. 测试规格（`tests/test_p034_price_diff_guard.py`）

| ID | 用例 | 构造 | 断言 |
|----|------|------|------|
| V1 | 无效 close 六形态（参数 6） | 零成本 `ExecutionSimulator(CostConfig(0,0,0,0), execution_price_type=ExecutionPriceType.OPEN)`；`open_price=10.0`（Python float）；`close ∈ {0.0, np.float64(0.0), np.nan, -5.0, np.inf, -np.inf}`；BUY 100 | `success is True`；`trade is not None`；`trade.price == 10.0`；`len(trade_log.get_trades()) == 1`；caplog **零**「差异过大」；caplog **零**「交易执行失败」 |
| V2 | 合法 close 告警保留（参数 3） | `close ∈ {8.0, 7.0, 10.5}`，`open=10.0` | `success is True`；`8.0` → 恰 **1** 条「差异过大」且含 `25.00%`；`7.0` → 恰 1 条含 `42.86%`；`10.5` → **零**条 |
| V3 | `close=None` 回归 | `close=None` | `success is True`；零「差异过大」；`trade.price == 10.0` |
| V4 | R1 吞单红态 | `open=10.0` / `close=0.0`（均 Python float） | `success is True`；`trade_log` 1 笔；caplog **零**「交易执行失败」（红态：`success=False` + 1 条 error） |
| V5 | P-033 守卫交互回归 | `open=np.nan`, `close=0.0` | `success is False`；`trade is None`；caplog 恰 **1** 条「执行价格无效」；零「差异过大」 |

**红态纪律**：B1t 首跑预期 **3 failed / 9 passed**（V1 的 `0.0` 与 `np.float64(0)` 两例 + V4 一例）；其余 9 例红态即通过（回归保护），须在 §11 显式标注。

---

## 6. fixture 表

| ID | 名称 | 内容 | 说明 |
|----|------|------|------|
| F1 | `_ZERO_COST` | `CostConfig(commission_rate=0.0, commission_min=0.0, stamp_tax_rate=0.0, slippage_pct=0.0)` | 零成本便于精确断言 |
| F2 | `_sim()` | `ExecutionSimulator(_ZERO_COST, execution_price_type=ExecutionPriceType.OPEN)` | 每例新建（隔离 `trade_log`） |
| F3 | `_run(sim, close, open_=10.0)` | 调用 `execute_order("A", OrderSide.BUY, 100, DATES[0], open_, close)` 并返回 `(success, trade)` | 统一调用形态 |
| F4 | `_warnings(caplog)` | 过滤 `record.levelno >= logging.WARNING` 且含「差异过大」/「交易执行失败」/「执行价格无效」的消息 | 三类计数分离 |

**约束**：全部落在新文件内；零 `unittest.mock`；不改 `test_p033_*`（复用其 fixture 思路但独立复制）。

---

## 7. 低效排除

| # | 候选 | 排除理由 |
|---|------|----------|
| 1 | 为 close 新写 `is_valid_close` | 判据与 `is_valid_price` 完全相同 → 第二来源 = 漂移入口 |
| 2 | 差异校验降为 debug 级 | 丢失合法价 25% 差异告警（既有诊断能力） |
| 3 | 无效 close 打提示日志 | 变成新噪声（R2 教训）；监控归掩码层 |
| 4 | CI 增加 `uv export --frozen` | 超出 U-P024-2 单一判据 |
| 5 | CI 改 `uv sync` 安装依赖 | 切换安装路径风险高，非本批目标 |
| 6 | `TypeGuard` 改造 | 需改 P-033 已验收公共签名（O-S2-P034-4） |
| 7 | 台账全表重构 | 只补缺口，历史行不改（O-R5-P031-1） |

---

## 8. 接口签名与回退点

| 对象 | 签名变化 | 回退点 |
|------|----------|--------|
| `ExecutionSimulator.execute_order` | **无**（仅内部条件） | B1 还原 1 行条件 |
| `core.execution.is_valid_price` | **无**（不改实现） | —— |
| `tests.yml` `lock-check` | 新增 job（非接口） | 删 10 行 job |
| `PROGRESS` / `CHANGELOG` / `ARCHITECTURE` | 文档 | docs 回退 |

---

## 9. 实施期裁决与发现

| ID | 级别 | 内容 | 处置 |
|----|------|------|------|
| F-I-P034-1 | 观察 | 注释行同时记录三种形态（噪声 / 吞单 / 静默），便于后续追溯 | 采纳 |
| F-I-P034-2 | 观察 | V1 的 `np.float64(0)` 参数在 pandas-free 构造下仍可复现 `inf`（numpy 分派） | 采纳（无需构造 DataFrame） |
| O-I-P034-1 | 观察 | 新测试文件首轮需 `black`（P-029/P-031/P-033 三次先例） | B4 门禁前先跑 |

---

## 10. 下一 Step 复核重点（Step 6 实施 Review）

1. **守卫条件**：L317 是否严格为 `close_price is not None and is_valid_price(close_price)`；L318-324 是否零改动；
2. **单一来源**：`is_valid_price` 全仓仍 1 定义，调用点 3 → **4**；
3. **CI job**：`@v10.3.3` / `version: "0.11.14"` / 无 `enable-cache` / 无 `|| true`；`test` job 零改动；
4. **台账**：8 处是否全部落地，U-P031-2 / U-008 合并注记是否在位；
5. **门禁预测**：760 / 84 / 121 / 37 / 13 / 22 是否可由 12 实例机械推出；
6. **红态**：3F/9P 口径是否与 §3 一致，四例「静默」是否被如实标为回归保护。

---

## 11. Step 6 实施 Review 记录（2026-11-17）

> **基座**: **DeepSeek-V4.1-Flash**——与本文作者**同源** → RULE-5 异构不成立，**同基座独立复审**（RULE-4 披露）；异构终审由 **U-P034-3** 跟踪。
> **复审对象**: `05778d1`（IMPL_p034 提交版）；复审时点 HEAD `05778d1`
> **方法**: E1 锚点机械复核 + E2 门禁基线独立复测 + E3 红态预览探针（`%TEMP%\p034_step6_red_probe.py`，不改代码模拟 12 实例断言）+ E4 六项裁决

### 11.1 E1 锚点机械复核（十项）

| # | IMPL 声称 | 实查 | 结果 |
|---|-----------|------|------|
| A1 | `core/execution.py` L316 `# 价格合理性检查` / L317 `if close_price is not None:` | 读码 | ✅ |
| A2 | L318-324（ratio / 阈值 / warning）逐字 | 读码 | ✅ |
| A3 | `is_valid_price` L153-161 签名 `Optional[float] -> bool` | 读码 | ✅ |
| A4 | `execute_order` L273 def / L280 `close_price: Optional[float] = None` | 读码 | ✅ |
| A5 | `tests.yml` L9-46 单 job + matrix + pip，零 uv | 读码 | ✅ |
| A6 | `uv.lock` `version = 1` / `revision = 3` | 头部 | ✅ |
| A7 | §1.4 P-034（L81）/ U-P031-2（L75）/ 旧表 U-008（L158） | 读码 | ✅ |
| A8 | `CHANGELOG` `### Changed` 首条可插入位置 | 读码 | ✅ |
| A9 | `ARCHITECTURE §9.2` L335 锁纪律句 | 读码 | ✅ |
| A10 | golden 目录 7 份 json（13 用例）未变 | 读码 | ✅ |

### 11.2 E2 门禁基线独立复测（四项，Python312 + `MPLBACKEND=Agg`）

| 门禁 | IMPL 声称 | 实测 | 结果 |
|------|-----------|------|------|
| 全量 pytest | 748 | **748 passed, 172 warnings**（49.67s） | ✅ |
| black `--check core tests` | 120 | **120 files would be left unchanged** | ✅ |
| mypy `--explicit-package-bases --check-untyped-defs core` | 37 files 0 | **Success: no issues found in 37 source files** | ✅ |
| `tests/` .py 数 | 83 | **83**（`*.py` 全量）/ **80**（`test_*.py`） | ✅（口径见 F-S6-P034-1） |

### 11.3 E3 红态预览（12 实例模拟，不改代码）

| 用例 | 结果 | 读数 |
|------|------|------|
| V1[python-0.0] | **FAIL** | `success=False` / `trades=0` / `errors=1`（R1 吞单） |
| V1[np-0] | **FAIL** | `success=True` 但 `diff_warns=1`（R2 `inf%`） |
| V1[nan] / V1[neg] / V1[inf] / V1[neg_inf] | PASS | 四例现状即无告警（回归保护，如实标注） |
| V2[8.0] / V2[7.0] / V2[10.5] | PASS | 1 条 `25.00%` / 1 条 `42.86%` / 0 条 |
| V3[None] | PASS | 零告警 |
| V4[close=0.0] | **FAIL** | `success=False` / `trades=0` / `errors=1` |
| V5[open=nan,close=0] | PASS | `success=False` / `guard=1` / `diff_warns=0` |
| **汇总** | **3 failed / 9 passed** | 与 §3 红态预算**逐项吻合** |

### 11.4 E4 六项裁决（对应 §10）

| # | 复核点 | 裁决 |
|---|--------|------|
| 1 | 守卫条件 | **规格精确**——L317 完整条件含 `is not None`；L318-324 零改动要求已列入 §4.6 |
| 2 | 单一来源 | **成立**——`is_valid_price` 保持 1 定义；实施后调用点 3 → 4 |
| 3 | CI job | **规格成立**——`@v10.3.3` / `version: "0.11.14"` / 无 `enable-cache` / 无 `|| true`；`test` job 零改动 |
| 4 | 台账 8 处 | **规格完整**——7 行新增 + 2 处补注；行文本可直接落地 |
| 5 | 门禁推算 | **全部正确**——748 + 12 = 760；83 + 1 = 84；120 + 1 = 121；37 不变；golden 13；AST 22 |
| 6 | 红态 3F/9P | **E3 实测逐项吻合**；四例「静默」如实归为回归保护，未伪造红态 |

### 11.5 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S6-P034-1 | P3 | §1 门禁口径「`tests/` .py 83 → 84」**未注明计数口径**——实测 `*.py`（含 `_golden_cases.py` / `_synth_fixture.py` / `_reference_impl.py` 等辅助）= **83**，而 `test_*.py` = **80**；若按后者核对会误判「83 失真」 | **当轮补注口径**（§1 已加「口径 = `tests/` 下全部 `.py`（含辅助模块）」） |
| O-S6-P034-1 | 观察 | V1[python-0.0] 与 V4 断言重叠（同一行为两种断言） | 保留（V4 提供最直接读数，冗余无害） |
| O-S6-P034-2 | 观察 | V1[np-0] 现状向 stderr 输出 `RuntimeWarning: divide by zero`（不影响断言）；修复后应消失 | 登记（非断言项） |

### 11.6 结论与 Step 7 前置条件

**结论**: **pass**（0 P0/P1/P2 / **1 P3 当轮回写** / 2 观察）——锚点十项全命中、门禁基线四项一致、红态预览与预测逐项吻合、六项裁决全过。
**RULE-5 声明**: 同基座独立复审，异构终审登记 **U-P034-3** 不变。

**Step 7 前置条件**:
1. CHECKLIST 按 V1-V5（12 实例）口径编制，**红态 3F/9P** 与四例回归保护显式登记；
2. 门禁实测列引用 §11.2 读数（748 / 120 / 37 / 83），并注明 `.py` 全量口径（F-S6-P034-1）；
3. Step 9 红绿留证须含 E3 的三例失败读数（F5 两读数），并与本节逐项对拍。

---

## 12. Step 9 实施记录（TDD 红→绿 + 门禁，2026-11-17）

> **执行基座**: DeepSeek-V4.1-Flash；基线 HEAD `642ec60`；Python312 + `MPLBACKEND=Agg`。

### 12.1 红→绿（F5 两读数）

| 阶段 | 读数 |
|------|------|
| **红**（B1 未改） | **3 failed, 9 passed, 1 warning**——`[python-0]` `assert False is True` / `[numpy-0]` `assert [<LogRecord 差异=inf%>] == []` / `v4_zero_close_not_swallowed` `assert False is True` |
| **绿**（B1 落地后） | **12 passed in 0.56s** |

红态三例与 §11.3 E3 预览**逐项一致**。

### 12.2 净行数（`git diff --numstat 642ec60..de0268d` 实测，提交后复核）

| 文件 | numstat |
|------|---------|
| `core/execution.py` | **+2 / −2** |
| `.github/workflows/tests.yml` | **+14 / −1** |
| `tests/test_p034_price_diff_guard.py` | **+136 / −0** |
| `CHANGELOG.md` | **+2 / −1** |
| `docs/ARCHITECTURE.md` | **+1 / −1** |
| `docs/PROGRESS.md` | **+24 / −3** |
| `docs/CHECKLIST_p034_ledger_diff_guard_and_lock_gate.md` | **+92 / −40** |
| `docs/IMPL_p034_ledger_diff_guard_and_lock_gate.md` | **+45 / −0** |
| **合计（8 文件）** | **+316 / −48** |

> 代码面（3 文件 + 测试）= execution `+2/−2` + workflow `+14/−1` + 测试 `+136/−0` = **+152/−3**；文档面 5 文件 **+164/−45**。
> **两次读数说明（F-R5 教训的当轮应用）**：提交前检查时点为 `+290/−48`（PROGRESS `+10/−3` / IMPL `+33/−0`，尚未含 §3.39.8 与本节）；提交后实测 `+316/−48`。**以提交后区间读数为准**。

### 12.3 门禁与单一来源

- 门禁：**760 passed**（43.53s）/ `tests/` .py **84**（`test_*.py` 81）/ black **121 unchanged** / mypy **37 files 0** / golden **13 零重录** / AST **22** / `core/` 新增 except **0** / `uv lock --check` **exit 0** / 回归子集 **86 passed**（13+24+11+9+17+12）。
- 单一来源：`is_valid_price` **1 定义**（execution L153）+ **4 调用**（execution L309 / **L317 新增** / agents L512 / engine_v2 L811）。
- 顺序敏感四项：L316 注释 → L317 条件 → L318 ratio；`is not None` 在 `and` 左侧；YAML `jobs = ['test','lock-check']`；台账 §1.4 L82-88。

### 12.4 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P034-1 | P3 | CHECKLIST E8 判据写「**≥ 74 passed**」——下限判据在 p034 的 12 例漏跑时仍成立，无法检出漂移 | **当轮修正**为「**86 passed**」精确等值（CHECKLIST E8 已改） |
| F-S9-P034-2 | 观察 | 新测试文件首轮被 `black` 重排 1 文件（O-I-P034-1 预判成立） | 已格式化 |
| O-S9-P034-1 | 观察 | `P-034` 行 `done` 待 Step 10 关闭后置 | Step 10 复核 |
