# CHECKLIST：P-034 台账收口 · 价格差异校验守卫 · CI 锁门禁

> **批次**: P-034 · **T1**（强制升级：新增 CI 门禁）
> **上游**: [IMPL_p034](IMPL_p034_ledger_diff_guard_and_lock_gate.md)（B1-B4 / §4 精确锚点 / §5 V1-V5 十二实例 / §6 fixture / §7 七项低效排除 / §11 Step 6 复审 pass：1 P3 当轮回写 + 2 观察）；[DESIGN_p034](DESIGN_p034_ledger_diff_guard_and_lock_gate.md)（D1-D4 / I1-I6 / V1-V5 / §9 Step 4 复审）；[RESEARCH_p034](RESEARCH_p034_ledger_diff_guard_and_lock_gate.md)（R1-R5 / N1-N6 / §11 Step 2 复审）
> **状态**: **Step 7 完成**（2026-11-17，基线 HEAD `8f65170`；Step 8 一致性 Review 待执行）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**禁止与正文同一次写入时打勾**
> **基线读数（Step 6 实测 @`05778d1` 代码面，Step 7 对拍）**: 全量 `pytest -q` **748 passed**（172 warnings，49.67s）/ `tests/` .py **83**（**口径 = 全部 `.py`**，含辅助模块；`test_*.py` = 80）/ `black --check core tests` **120 unchanged** / `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error** / golden **13 用例**（7 份 json）/ `except Exception`（P-029 十文件口径）**22**
> **目标读数（Step 9）**: **760 passed** / `tests/` .py **84**（`test_*.py` 81）/ black **121** / mypy **37 files 0** / golden **13 零重录** / `except Exception` 恒 **22**
> **代码证据时点**: 实施前 HEAD `8f65170`（代码面与 `a0db635` 一致，仅 docs 变更）

---

## 1. A 组：B1 差异校验守卫（DESIGN-D1 → 测试 V1 / V3 / V4 / V5）

> **DoR**: `core/execution.py` L316-324 差异校验结构与 L153-161 `is_valid_price` 已在 Step 6 E1 冻结。**DoD**: 无效 close 六形态全部跳过且成交正常；合法 close 告警逐字不变。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | L317 条件改为 `if close_price is not None and is_valid_price(close_price):`（**不得省略 `is not None`**——mypy 窄化必需，Step 4 E2 正反例证据） | 读码 L317；`git diff core/execution.py` 该行为 `+` | DESIGN-D1 / IMPL §4.1 / F-S4 裁决 #4 | [待 Step 9] |
| A2 | L316 注释行改为含「P-034 D1」与「close 无效时跳过」语义的单行注释 | 读码 L316 | IMPL §4.1 / F-I-P034-1 | [待 Step 9] |
| A3 | L318-324（`price_diff_ratio` 计算 / `> 0.1` 阈值 / warning 三行文案含 `{:.2%}`）**逐字不变** | `git diff core/execution.py` 无该区间 hunk | DESIGN-D1 I1 / IMPL §4.6 | [待 Step 9] |
| A4 | 零新增 `except` / 零新增 `raise`；`except Exception`（P-029 十文件口径）恒 **22**；`core/` 侧 `git diff` 中 `^\+.*\bexcept\b` = **0** | AST 命令 + `git diff core/` 限文件命令 | I3 / F-S8-P033-5 口径 | [待 Step 9] |
| A5 | V1 绿（参数 6：`0.0` / `np.float64(0)` / `nan` / `-5.0` / `inf` / `-inf`）：每例 `success is True`、`trade.price == 10.0`、`trade_log` 恰 1 笔、caplog **零**「差异过大」、**零**「交易执行失败」 | `pytest -q -k "v1_invalid_close"` = **6 passed** | V1 / IMPL §5 | [待 Step 9] |
| A6 | V3 绿（`close=None`）：`success is True`、零「差异过大」、`trade.price == 10.0`（原行为不变） | `pytest -q -k "v3_none_close"` = **1 passed** | V3 | [待 Step 9] |
| A7 | V4 绿（R1 吞单）：`open=10.0` / `close=0.0`（均 Python float）→ `success is True`、`trade_log` 1 笔、**零**「交易执行失败」（**红态：`success=False` + 1 条 error**） | `pytest -q -k "v4_zero_close"` = **1 passed** | V4 / R1 | [待 Step 9] |
| A8 | V5 绿（P-033 交互）：`open=nan` / `close=0.0` → `success is False`、`trade is None`、caplog 恰 **1** 条「执行价格无效」、零「差异过大」（守卫先行不变） | `pytest -q -k "v5_guard_interaction"` = **1 passed** | V5 / P-033 D1 | [待 Step 9] |

---

## 2. B 组：B2 CI `lock-check`（DESIGN-D2）

> **DoR**: `tests.yml` 当前仅 `test` job（L9-46）；`uv lock --check` 本地 exit 0（`uv 0.11.14`，148 packages）。**DoD**: 新增独立 job 且失败即红；`test` job 零改动。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | 新增独立 job `lock-check`（`runs-on: ubuntu-latest`，**不进 matrix**），位于 `test` job 之后同级缩进 | 读码 `tests.yml`；YAML 可解析 | DESIGN-D2 / IMPL §4.2 | [待 Step 9] |
| B2 | `uses: astral-sh/setup-uv@v10.3.3`（**精确钉，非 `@v6`**）+ `with: version: "0.11.14"`；**省略 `enable-cache`** | 读码；`Select-String "setup-uv@"` = 1 | F-S4-P034-1 / O-S4-P034-1 | [待 Step 9] |
| B3 | `run: uv lock --check` 为**独立 step**，文件内 **零** `\|\| true` / 零 `continue-on-error`（门禁真实可红） | `Select-String "\|\| true\|continue-on-error"` = **0** | DESIGN-D2 / P-024 教训 / C4 实证 | [待 Step 9] |
| B4 | `test` job **逐行零改动**（`Install dependencies` 仍 `pip install ".[dev]"`；`Run tests` / `Type check` 不变） | `git diff tests.yml` 仅含新增 hunk | I5 / IMPL §4.6 | [待 Step 9] |
| B5 | 本地 `uv lock --check` **exit 0**（锁与 pyproject 一致，新增 job 首跑即绿） | `uv lock --check; $LASTEXITCODE` = 0 | DESIGN-D2 / U-P024-2 | [待 Step 9] |

---

## 3. C 组：B3 台账 8 处 + 同步文档（DESIGN-D3）

> **DoR**: §1.4 P-034 行（L81）/ U-P031-2（L75）/ 旧表 U-008（L158）位置已冻结。**DoD**: 8 处全部落地且合并关系单一跟踪。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | §1.4 新增 **7 行**：U-P033-1（**done**，P-034 承接）/ U-P033-2（已合并至 U-P031-2）/ U-P033-3（**已裁决不采纳**）/ U-P014-1（pending）/ U-P014-3（已合并至 U-P031-2）/ U-P015-1（pending）/ U-P016-1（pending） | 读回 §1.4；`Grep "^\| U-P033"` = 3 / `U-P014` = 2 / `U-P015-1` = 1 / `U-P016-1` = 1 | DESIGN-D3 / IMPL §4.3 | [待 Step 9] |
| C2 | U-P031-2 行尾补注「U-P014-3 与 U-P033-2 同源已并入本行，本行为**单一跟踪源**」 | 读回 L75 行 | DESIGN-D3 / P-028 先例 | [待 Step 9] |
| C3 | 旧表 U-008 行尾补注「与 §1.4 U-P021-2 同源，统一由后者单一跟踪」 | 读回旧表行 | DESIGN-D3 / P-028 先例 | [待 Step 9] |
| C4 | 7 行均 **5 列齐备**（ID / 事项 / 依据 / 状态 / 优先级），无空单元格；新行 ID 与既有表 **零重复** | 机械计数（列数 / ID 去重） | RULE-2 统计溯源 | [待 Step 9] |
| C5 | `CHANGELOG [Unreleased] Changed` 首条为 P-034 条目（含「748 → 760」与 `uv lock --check`） | 读回 CHANGELOG | IMPL §4.4 / 台账惯例 | [待 Step 9] |
| C6 | `ARCHITECTURE §9.2` L335「CI 使用 pip，不校验锁」已订正为「`lock-check` job 以 `uv lock --check` 校验（失败即红）」 | 读回 L335；`Grep "不校验锁"` = **0** | IMPL §4.5 | [待 Step 9] |
| C7 | PROGRESS §1.4 P-034 行状态更新为 **done**；§3.39.4 记录中「批次关闭动作清单」纪律一项在位 | 读回 §1.4 与 §3.39.x | D3 附则 / 三次同型教训 | [待 Step 9] |

---

## 4. D 组：不变式 I1-I6

> **DoR**: 六条不变式见 DESIGN §3。**DoD**: 断言组合成立或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | I1：合法 close（有限正数）路径 `price_diff_ratio` 与告警输出**逐位不变** | A3 + A6 + V2 三参数（`8.0`→`25.00%`、`7.0`→`42.86%`、`10.5`→零）+ golden 13 零重录 | I1 / V2 / E4 | [待 Step 9] |
| D2 | I2：无效 close（`None` / `0` / `NaN` / `±inf` / 负）→ 不计算 ratio、不打「差异过大」、**不改变成交结果** | A5（六参数）+ A6 + A7 | I2 / V1 / V3 / V4 | [待 Step 9] |
| D3 | I3：零新增 `except` / `raise`；AST 恒 22；`core/` 新增 except = 0 | A4 | I3 | [待 Step 9] |
| D4 | I4：公开签名零变更（`execute_order` / `is_valid_price`） | `git diff \| Select-String '^-\s*def '` = **0** | I4 | [待 Step 9] |
| D5 | I5：`lock-check` 失败即红（无 `\|\| true`）；`test` job 零改动 | B3 + B4 | I5 | [待 Step 9] |
| D6 | I6：台账 8 处全部有落点；U-P033-1 done / U-P033-3 不采纳 / U-P033-2·U-P014-3 → U-P031-2 / U-008 → U-P021-2 | C1-C4 | I6 | [待 Step 9] |

---

## 5. E 组：测试 / 门禁 / 治理

> **DoR**: 门禁基线四项已在 Step 6 §11.2 实测。**DoD**: 读数逐一相等或差值可机械推出。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 新测试文件 `tests/test_p034_price_diff_guard.py` 恰含 **12 实例**（V1 6 + V2 3 + V3 1 + V4 1 + V5 1）；`^def test_` = **5** | `pytest --collect-only -q <file>` 末行 **12 tests collected**；`Select-String '^def test_'` = 5 | V1-V5 / IMPL §5 | [待 Step 9] |
| E2 | 红态纪律（批内逐实例）：B1t 首跑 **3 failed / 9 passed** = `V1[python-0.0]` + `V1[np-0]` + `V4[close=0.0]`；**回归保护 9 例**（V1 `nan`/`neg`/`inf`/`neg_inf` + V2×3 + V3 + V5）显式标注，**不得**把四例「静默」误报为红态 | 红态输出留档 + IMPL §11 记录 | IMPL §3 / §11.3 / F-S8-P033-2 口径 | [待 Step 9] |
| E3 | 新测试 **12 passed** | `pytest tests/test_p034_price_diff_guard.py -q` 末行 | V1-V5 | [待 Step 9] |
| E4 | 全量回归 **760 passed**（748 基线 + 12） | `MPLBACKEND=Agg pytest -q` 末行 | I1 / 门禁目标 | [待 Step 9] |
| E5 | black `--check core tests` **121 unchanged**；mypy `--explicit-package-bases --check-untyped-defs core` **37 files 0 error** | 两条门禁命令末行 | 门禁目标 / F-S6-P034-1 口径 | [待 Step 9] |
| E6 | golden **13 passed** 且 `tests/golden/*.json` 零改动（零重录）；零改动面 `git status --short` 全空（`core/engine_v2.py` / `core/tracker.py` / `core/pending.py` / `core/interfaces.py` / `agents/` / `filter/` / `scripts/` / `cli.py` / `pyproject.toml` / `uv.lock` / `tests/test_p029_*.py` / `tests/test_p031_*.py` / `tests/test_p033_*.py`） | `pytest -q -k golden`；`git status --short` | I1 / IMPL §1 | [待 Step 9] |
| E7 | 测试零 `unittest.mock`；fixture F1-F4 全部落在新文件内，**不修改**既有 `test_p029*` / `test_p031*` / `test_p033*` | `Select-String "unittest.mock"` = 0；`git diff --name-only tests/` 仅新增 1 文件 | IMPL §6 | [待 Step 9] |
| E8 | 受影响面快速回归：`-k "golden or p027 or p029 or p031 or p033 or p034"` **≥ 74 passed / 0 failed / 0 error** | 该子集输出末行 | 回归面 | [待 Step 9] |
| E9 | 远端 CI **四 job**（3.10 / 3.11 / 3.12 + `lock-check`）全 success | `gh run view <id> --json conclusion,jobs` | B 组交付纪律 | [待 Step 9] |
| E10 | 四文档互链 0 broken；P-034 行状态 done；CHANGELOG 条目在位 | 机械校验链接数 / broken 数；读回 | 台账惯例 | [待 Step 9] |
| E11 | 观察/未决登记完整：`R-P034-1~3` / `U-P034-1~3` / `O-P034-1~3`（含 `O-P034-3`）/ `F-D3-P034-1~2` / `F-I-P034-1~2` + `O-I-P034-1` / `F-S2-P034-1` + `O-S2-P034-1~4` / `F-S4-P034-1` + `O-S4-P034-1~3` / `F-S6-P034-1` + `O-S6-P034-1~2` 全部有落点 | 读回 DESIGN §5 / IMPL §9 / §11.5 / RESEARCH §11.5 | 治理惯例 | [待 Step 9] |

---

## 6. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **37**（A 8 + B 5 + C 7 + D 6 + E 11 = 37，机械计数） |
| 实测列 `[待 Step 9]` 数 | **37**（A8 + B5 + C7 + D6 + E11，逐表机械相加） |

> **RULE-2 统计溯源**：37 由 §1-§5 五张表逐行机械计数得出（A1-A8 = 8 / B1-B5 = 5 / C1-C7 = 7 / D1-D6 = 6 / E1-E11 = 11），非估计值。12 实例由 IMPL §2 计数口径（V1 6 + V2 3 + V3 1 + V4 1 + V5 1）机械相加得出。
>
> **`[待 Step 9]` 字面账目（F-S8-P034-1 当轮补注）**：全文机械匹配 **39** = **37 单元格** + 头部规则行 1 处 + 本节标签行 1 处；**37 单元格零预填不变**。
>
> **本文件作者基座**: DeepSeek-V4.1-Flash（与四文档同源）→ **Step 8 一致性 Review 须由异构基座执行**（RULE-5；若同基座则披露 + 记入 U-P034-3）。

---

## 7. Step 7 → Step 8 交接事项

1. **Step 8 一致性 Review（异构基座优先）**：核四文档口径——
   - **12 实例**（V1 6 / V2 3 / V3 1 / V4 1 / V5 1）在 DESIGN §4 / IMPL §2+§5 / 本文件 E1+§6 三处一致；
   - **门禁链** 748→**760** / 83→**84** / 120→**121** / 37 不变 / golden 13 零重录 / AST 22 在 DESIGN §4 / IMPL §1 / 本文件头 + D3 + E4-E5 三处一致；
   - **台账 8 处**（7 行新增 + 2 处补注）在 DESIGN-D3 / IMPL §4.3 / 本文件 C1-C3 一致；
   - **红态 3F/9P** 与四例回归保护在 IMPL §3+§11.3 / 本文件 E2 一致。
2. **两套 ID 不得混用**：DESIGN 决策 `D1-D4` 与本文件 **D 组**（不变式）同字母——凡引用决策一律标 `DESIGN-D*`（P-033 F-S8-P033-3 教训）。
3. **顺序敏感核验（Step 9 必做）**：① 守卫必须在 L316 注释之后、L318 ratio **之前**；② `is not None` 必须在 `and` 左侧（mypy 窄化）；③ CI job 在 `test` job 之后且同级缩进；④ 台账行插在 P-034 行之后、U-D1 行之前。
4. **红态豁免标注**：四例「静默」（`nan` / `-5` / `inf` / `-inf`）+ V2/V3/V5 共 9 例红态即通过属预期，E2 留档须显式标注，防误判为「红态不成立」。
5. **`.py` 计数口径**：`tests/` .py 83→84 指**全部 `.py`**（含辅助模块），`test_*.py` 为 80→81（F-S6-P034-1）。
6. **black 先行**：新测试文件首轮须先跑 `black` 再进门禁（O-I-P034-1）。
7. **CI action 版本**：`@v10.3.3` 已由 Step 4 `gh api` 核验；若实施时发现不可解析，降级 `pip install uv==0.11.14`（U-P034-1）。

---

## 8. 签字表

| 角色 | 基座 | 结论 | 日期 |
|------|------|------|------|
| Step 7 验收清单作者 | DeepSeek-V4.1-Flash | 37 项完稿，零预填 | 2026-11-17 |
| Step 8 一致性 Review | DeepSeek-V4.1-Flash（= Step 7 作者同源，**同基座独立复审**；RULE-5 不成立，异构终审记 U-P034-3） | pass：机械五项全过 + 对齐矩阵 A-G 全过；1 P3 当轮修正（F-S8-P034-1）+ 2 观察，见 §9 | 2026-11-17 |
| Step 9 TDD 执行 | （待执行） | —— | —— |
| Step 10 ADD 审计 + 终审 | （待执行；RULE-5 异构优先，否则记入 U-P034-3） | —— | —— |

---

## 9. Step 8 一致性 Review（2026-11-17）

> **基座**: **DeepSeek-V4.1-Flash**——与本文件作者**同源** → RULE-5 异构不成立，本轮为**同基座独立复审**（RULE-4 披露）；异构终审由 **U-P034-3** 跟踪。
> **复审对象**: `0285f25`（CHECKLIST_p034 提交版）；复审时点 HEAD `0285f25`
> **方法**: 独立机械脚本（`%TEMP%\p034_step8_check.py`）五项 + 对齐矩阵七项（§7 交接逐条裁决）

### 9.1 E1 机械校验五项

| # | 检查项 | 读数 | 结果 |
|---|--------|------|------|
| M1 | 相对链接 | 3 条 / 3 unique / **0 broken** | ✅ |
| M2 | ID 闭环 | **37 行 / 37 唯一 / 无重复**；分组 **A8 + B5 + C7 + D6 + E11** 与 §6 声称精确一致 | ✅ |
| M3 | 计数一致性 | `37`×9 / `12 实例`×3 / `748`×4 / `760`×4 / `84`×3 / `121`×3 / `37 files 0`×3 / `22`×5 / `3 failed / 9 passed` + `3F/9P` 各 1 | ✅ |
| M4 | 零预填合规 | `[待 Step 9]` 机械匹配 **39** = 37 单元格 + 头部规则行 1 + §6 标签行 1——**37 单元格零预填不变** | ✅（F-S8-P034-1 当轮补注账目） |
| M5 | 签字表 | 四行齐备（Step 7 已落；Step 8/9/10 占位） | ✅ |

### 9.2 E2 对齐矩阵七项（§7 交接逐条裁决）

| # | 对拍项 | 落点 | 结果 |
|---|--------|------|------|
| A | **12 实例** | DESIGN §4（V1 6 / V2 3 / V3 1 / V4 1 / V5 1）× IMPL §2 计数行 + §5 五行 × 本文件 E1 + §6 —— 三处一致 | ✅ |
| B | **门禁链 748→760 / 83→84 / 120→121 / 37 / 13 / 22** | DESIGN §4 门禁目标 × IMPL §1 门禁口径（含 `.py` 全量口径注）× 本文件头 + D3 + E4-E5 | ✅ |
| C | **台账 8 处（7 行 + 2 补注）** | DESIGN-D3 八行表 × IMPL §4.3 逐行文本 × 本文件 C1-C3 | ✅ 三处一致 |
| D | **红态 3F/9P + 四例回归保护** | IMPL §3 红态预算 + §11.3 E3 实测 × 本文件 E2 —— 失败三例逐一对应（`V1[python-0.0]` / `V1[np-0]` / `V4[close=0.0]`） | ✅ |
| E | **两套 ID 不混用** | 组标题全部 `DESIGN-D*`（A/B/C 三处）；D 组为不变式 ID，无裸引用 | ✅（P-033 F-S8-P033-3 教训已吸取） |
| F | **顺序敏感四项** | ① 守卫在 L316 注释后 / L318 前→A1+A2 ② `is not None` 在 `and` 左侧→A1 ③ CI job 在 `test` 后同级→B1 ④ 台账行位置→C1 | ✅ |
| G | **基线引用链** | 本文件头 @`8f65170`：pytest 748 引 Step 6 §11.2 实测（@`05778d1` 代码面）；`05778d1..8f65170` 为 docs-only → 代码面一致，已注明来源 | ✅ |

### 9.3 发现与分级

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P034-1 | P3 | §6 零预填检查仅声明「37 处」，未列明全文字面 **39** 的构成（37 单元格 + 规则行 1 + 标签行 1）——机械校验会误判为「预填不合规」 | **当轮补注** §6 字面账目（已加） |
| O-S8-P034-1 | 观察 | 本文件「红态 3F/9P」同时存在 `3 failed / 9 passed`（E2）与 `3F/9P`（多处）两种写法——语义一致，不影响判据 | 登记 |
| O-S8-P034-2 | 观察 | 签字表 Step 8 行在提交时仍为占位（本轮回填） | 登记（本轮已回填） |

### 9.4 结论与 Step 9 前置条件

**结论**: **pass**（机械五项全过 + 对齐矩阵 A-G 全过 / **0 P0/P1/P2** / **1 P3 当轮修正** / 2 观察）——四文档口径闭环，37 项验收可执行，准予进入 Step 9 TDD。
**RULE-5 声明**: 同基座独立复审（作者=复审=DeepSeek-V4.1-Flash），异构终审登记 **U-P034-3** 不变。

**Step 9 前置条件**:
1. 红态按 **批内逐实例** 口径执行：B1t 首跑 **3 failed / 9 passed**，失败三例逐一留证（F5 红读数）；九例回归保护显式标注；
2. 顺序敏感四项逐项留证（§7.3）；
3. 台账 8 处与 CHANGELOG / ARCHITECTURE 在 B3 落地后回填 C1-C7；
4. 新测试文件首轮先 `black`（O-I-P034-1）；CI `lock-check` 首跑须为 success（E9 四 job）。
