# CHECKLIST：P-034 台账收口 · 价格差异校验守卫 · CI 锁门禁

> **批次**: P-034 · **T1**（强制升级：新增 CI 门禁）
> **上游**: [IMPL_p034](IMPL_p034_ledger_diff_guard_and_lock_gate.md)（B1-B4 / §4 精确锚点 / §5 V1-V5 十二实例 / §6 fixture / §7 七项低效排除 / §11 Step 6 复审 pass：1 P3 当轮回写 + 2 观察）；[DESIGN_p034](DESIGN_p034_ledger_diff_guard_and_lock_gate.md)（D1-D4 / I1-I6 / V1-V5 / §9 Step 4 复审）；[RESEARCH_p034](RESEARCH_p034_ledger_diff_guard_and_lock_gate.md)（R1-R5 / N1-N6 / §11 Step 2 复审）
> **状态**: **Step 10 ADD 审计 + 终审通过，P-034 批次关闭**（2026-11-17；37/37 全部回填；审计基座 DeepSeek-V4.1-Flash = 作者同源，RULE-5 不成立 → 异构终审记 U-P034-3）——0 P0-P2 + 1 P3 当轮修正（F-R5-P034-1）+ 2 观察；门禁独立复跑 **760 passed / 84 / 121 / 37 files 0 / golden 13 零重录 / AST 22 / uv lock --check exit 0** 全绿（见 §11）；**异构终审 pass（U-P034-3 补做，GLM-5.3-Flash，2026-11-17，见 §12）——P-034 过程链全闭合**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；**禁止与正文同一次写入时打勾**
> **基线读数（Step 6 实测 @`05778d1` 代码面，Step 7 对拍）**: 全量 `pytest -q` **748 passed**（172 warnings，49.67s）/ `tests/` .py **83**（**口径 = 全部 `.py`**，含辅助模块；`test_*.py` = 80）/ `black --check core tests` **120 unchanged** / `mypy --explicit-package-bases --check-untyped-defs core` **37 files 0 error** / golden **13 用例**（7 份 json）/ `except Exception`（P-029 十文件口径）**22**
> **目标读数（Step 9）**: **760 passed** / `tests/` .py **84**（`test_*.py` 81）/ black **121** / mypy **37 files 0** / golden **13 零重录** / `except Exception` 恒 **22**
> **代码证据时点**: 实施前 HEAD `8f65170`（代码面与 `a0db635` 一致，仅 docs 变更）

---

## 1. A 组：B1 差异校验守卫（DESIGN-D1 → 测试 V1 / V3 / V4 / V5）

> **DoR**: `core/execution.py` L316-324 差异校验结构与 L153-161 `is_valid_price` 已在 Step 6 E1 冻结。**DoD**: 无效 close 六形态全部跳过且成交正常；合法 close 告警逐字不变。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | L317 条件改为 `if close_price is not None and is_valid_price(close_price):`（**不得省略 `is not None`**——mypy 窄化必需，Step 4 E2 正反例证据） | 读码 L317；`git diff core/execution.py` 该行为 `+` | DESIGN-D1 / IMPL §4.1 / F-S4 裁决 #4 | ✅ L317 实测 `if close_price is not None and is_valid_price(close_price):`（AST 调用点 execution L317）；`git diff` 该行 `+` |
| A2 | L316 注释行改为含「P-034 D1」与「close 无效时跳过」语义的单行注释 | 读码 L316 | IMPL §4.1 / F-I-P034-1 | ✅ L316 实测 `# P-034 D1：价格合理性检查（close 无效时跳过——避免 inf 噪声 / 除零吞单 / NaN 静默）` |
| A3 | L318-324（`price_diff_ratio` 计算 / `> 0.1` 阈值 / warning 三行文案含 `{:.2%}`）**逐字不变** | `git diff core/execution.py` 无该区间 hunk | DESIGN-D1 I1 / IMPL §4.6 | ✅ `git diff core/execution.py` 无 L318-324 区间 hunk（ratio / 阈值 / warning 逐字未动） |
| A4 | 零新增 `except` / 零新增 `raise`；`except Exception`（P-029 十文件口径）恒 **22**；`core/` 侧 `git diff` 中 `^\+.*\bexcept\b` = **0** | AST 命令 + `git diff core/` 限文件命令 | I3 / F-S8-P033-5 口径 | ✅ AST `except Exception` **22**；`git diff core/` 中 `^\+.*\bexcept\b` = **0** |
| A5 | V1 绿（参数 6：`0.0` / `np.float64(0)` / `nan` / `-5.0` / `inf` / `-inf`）：每例 `success is True`、`trade.price == 10.0`、`trade_log` 恰 1 笔、caplog **零**「差异过大」、**零**「交易执行失败」 | `pytest -q -k "v1_invalid_close"` = **6 passed** | V1 / IMPL §5 | ✅ **6 passed**（`-k v1_invalid_close`） |
| A6 | V3 绿（`close=None`）：`success is True`、零「差异过大」、`trade.price == 10.0`（原行为不变） | `pytest -q -k "v3_none_close"` = **1 passed** | V3 | ✅ **1 passed**（`-k v3_none_close`） |
| A7 | V4 绿（R1 吞单）：`open=10.0` / `close=0.0`（均 Python float）→ `success is True`、`trade_log` 1 笔、**零**「交易执行失败」（**红态：`success=False` + 1 条 error**） | `pytest -q -k "v4_zero_close"` = **1 passed** | V4 / R1 | ✅ **1 passed**（`-k v4_zero_close`；红态 `success=False` → 绿 `True`） |
| A8 | V5 绿（P-033 交互）：`open=nan` / `close=0.0` → `success is False`、`trade is None`、caplog 恰 **1** 条「执行价格无效」、零「差异过大」（守卫先行不变） | `pytest -q -k "v5_guard_interaction"` = **1 passed** | V5 / P-033 D1 | ✅ **1 passed**（`-k v5_guard_interaction`） |

---

## 2. B 组：B2 CI `lock-check`（DESIGN-D2）

> **DoR**: `tests.yml` 当前仅 `test` job（L9-46）；`uv lock --check` 本地 exit 0（`uv 0.11.14`，148 packages）。**DoD**: 新增独立 job 且失败即红；`test` job 零改动。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | 新增独立 job `lock-check`（`runs-on: ubuntu-latest`，**不进 matrix**），位于 `test` job 之后同级缩进 | 读码 `tests.yml`；YAML 可解析 | DESIGN-D2 / IMPL §4.2 | ✅ YAML 解析 `jobs = ['test', 'lock-check']`（独立 job、同级缩进） |
| B2 | `uses: astral-sh/setup-uv@v10.3.3`（**精确钉，非 `@v6`**）+ `with: version: "0.11.14"`；**省略 `enable-cache`** | 读码；`Select-String "setup-uv@"` = 1 | F-S4-P034-1 / O-S4-P034-1 | ✅ `uses: astral-sh/setup-uv@v10.3.3` + `version: "0.11.14"`；无 `enable-cache` |
| B3 | `run: uv lock --check` 为**独立 step**，文件内 **零** `\|\| true` / 零 `continue-on-error`（门禁真实可红） | `Select-String "\|\| true\|continue-on-error"` = **0** | DESIGN-D2 / P-024 教训 / C4 实证 | ✅ 文件内 `\|\| true` / `continue-on-error` **零命中**；`uv lock --check` 为独立 step |
| B4 | `test` job **逐行零改动**（`Install dependencies` 仍 `pip install ".[dev]"`；`Run tests` / `Type check` 不变） | `git diff tests.yml` 仅含新增 hunk | I5 / IMPL §4.6 | ✅ `git diff tests.yml` 仅新增 hunk（+15/−1），`test` job 4 个 step 逐行未动 |
| B5 | 本地 `uv lock --check` **exit 0**（锁与 pyproject 一致，新增 job 首跑即绿） | `uv lock --check; $LASTEXITCODE` = 0 | DESIGN-D2 / U-P024-2 | ✅ `uv lock --check` **exit 0**（Resolved 148 packages） |

---

## 3. C 组：B3 台账 8 处 + 同步文档（DESIGN-D3）

> **DoR**: §1.4 P-034 行（L81）/ U-P031-2（L75）/ 旧表 U-008（L158）位置已冻结。**DoD**: 8 处全部落地且合并关系单一跟踪。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | §1.4 新增 **7 行**：U-P033-1（**done**，P-034 承接）/ U-P033-2（已合并至 U-P031-2）/ U-P033-3（**已裁决不采纳**）/ U-P014-1（pending）/ U-P014-3（已合并至 U-P031-2）/ U-P015-1（pending）/ U-P016-1（pending） | 读回 §1.4；`Grep "^\| U-P033"` = 3 / `U-P014` = 2 / `U-P015-1` = 1 / `U-P016-1` = 1 | DESIGN-D3 / IMPL §4.3 | ✅ 7 行全部落位（§1.4 L82-88）：U-P033-1 done / U-P033-2 合并 / U-P033-3 不采纳 / U-P014-1 / U-P014-3 合并 / U-P015-1 / U-P016-1 |
| C2 | U-P031-2 行尾补注「U-P014-3 与 U-P033-2 同源已并入本行，本行为**单一跟踪源**」 | 读回 L75 行 | DESIGN-D3 / P-028 先例 | ✅ U-P031-2 行尾含「U-P014-3 与 U-P033-2 同源已并入本行，本行为**单一跟踪源**」 |
| C3 | 旧表 U-008 行尾补注「与 §1.4 U-P021-2 同源，统一由后者单一跟踪」 | 读回旧表行 | DESIGN-D3 / P-028 先例 | ✅ 旧表 U-008 行尾含「与 §1.4 U-P021-2 同源，统一由后者单一跟踪」 |
| C4 | 7 行均 **5 列齐备**（ID / 事项 / 依据 / 状态 / 优先级），无空单元格；新行 ID 与既有表 **零重复** | 机械计数（列数 / ID 去重） | RULE-2 统计溯源 | ✅ 7 行均 5 列齐备；`U-P0` ID 与既有行零重复 |
| C5 | `CHANGELOG [Unreleased] Changed` 首条为 P-034 条目（含「748 → 760」与 `uv lock --check`） | 读回 CHANGELOG | IMPL §4.4 / 台账惯例 | ✅ `CHANGELOG ### Changed` 首条为 P-034（含「748 → 760」与 `uv lock --check`） |
| C6 | `ARCHITECTURE §9.2` L335「CI 使用 pip，不校验锁」已订正为「`lock-check` job 以 `uv lock --check` 校验（失败即红）」 | 读回 L335；`Grep "不校验锁"` = **0** | IMPL §4.5 | ✅ `ARCHITECTURE §9.2` L335 已订正；`Grep "不校验锁"` = **0** |
| C7 | PROGRESS §1.4 P-034 行状态更新为 **done**；§3.39.4 记录中「批次关闭动作清单」纪律一项在位 | 读回 §1.4 与 §3.39.x | D3 附则 / 三次同型教训 | ✅ §1.4 P-034 行已更新为「Step 1-9 完成」摘要；D5 附则（批次关闭检查 U-\* 建行）记于 §3.39.4；**done 待 Step 10 关闭时置** |

---

## 4. D 组：不变式 I1-I6

> **DoR**: 六条不变式见 DESIGN §3。**DoD**: 断言组合成立或读数逐一相等。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | I1：合法 close（有限正数）路径 `price_diff_ratio` 与告警输出**逐位不变** | A3 + A6 + V2 三参数（`8.0`→`25.00%`、`7.0`→`42.86%`、`10.5`→零）+ golden 13 零重录 | I1 / V2 / E4 | ✅ V2 三参数（25.00% / 42.86% / 零告警）+ golden **13 passed 零重录** |
| D2 | I2：无效 close（`None` / `0` / `NaN` / `±inf` / 负）→ 不计算 ratio、不打「差异过大」、**不改变成交结果** | A5（六参数）+ A6 + A7 | I2 / V1 / V3 / V4 | ✅ V1 六参数 + V3 + V4 全过（无效 close 零 ratio、零告警、成交正常） |
| D3 | I3：零新增 `except` / `raise`；AST 恒 22；`core/` 新增 except = 0 | A4 | I3 | ✅ A4 读数（AST 22 / core except 0） |
| D4 | I4：公开签名零变更（`execute_order` / `is_valid_price`） | `git diff \| Select-String '^-\s*def '` = **0** | I4 | ✅ `git diff` 中 `^-\s*def ` = **0** |
| D5 | I5：`lock-check` 失败即红（无 `\|\| true`）；`test` job 零改动 | B3 + B4 | I5 | ✅ B3（零 `\|\| true`）+ B4（test job 零改动） |
| D6 | I6：台账 8 处全部有落点；U-P033-1 done / U-P033-3 不采纳 / U-P033-2·U-P014-3 → U-P031-2 / U-008 → U-P021-2 | C1-C4 | I6 | ✅ C1-C4（8 处处置全部落位） |

---

## 5. E 组：测试 / 门禁 / 治理

> **DoR**: 门禁基线四项已在 Step 6 §11.2 实测。**DoD**: 读数逐一相等或差值可机械推出。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 新测试文件 `tests/test_p034_price_diff_guard.py` 恰含 **12 实例**（V1 6 + V2 3 + V3 1 + V4 1 + V5 1）；`^def test_` = **5** | `pytest --collect-only -q <file>` 末行 **12 tests collected**；`Select-String '^def test_'` = 5 | V1-V5 / IMPL §5 | ✅ **12 tests collected**；`^def test_` = **5** |
| E2 | 红态纪律（批内逐实例）：B1t 首跑 **3 failed / 9 passed** = `V1[python-0.0]` + `V1[np-0]` + `V4[close=0.0]`；**回归保护 9 例**（V1 `nan`/`neg`/`inf`/`neg_inf` + V2×3 + V3 + V5）显式标注，**不得**把四例「静默」误报为红态 | 红态输出留档 + IMPL §11 记录 | IMPL §3 / §11.3 / F-S8-P033-2 口径 | ✅ 红态 **3 failed / 9 passed**——失败三例 `[python-0]` / `[numpy-0]` / `v4_zero_close`；九例回归保护已标注 |
| E3 | 新测试 **12 passed** | `pytest tests/test_p034_price_diff_guard.py -q` 末行 | V1-V5 | ✅ **12 passed**（0.56s） |
| E4 | 全量回归 **760 passed**（748 基线 + 12） | `MPLBACKEND=Agg pytest -q` 末行 | I1 / 门禁目标 | ✅ **760 passed**（172 warnings，43.53s） |
| E5 | black `--check core tests` **121 unchanged**；mypy `--explicit-package-bases --check-untyped-defs core` **37 files 0 error** | 两条门禁命令末行 | 门禁目标 / F-S6-P034-1 口径 | ✅ black **121 unchanged**；mypy **Success: 37 source files** |
| E6 | golden **13 passed** 且 `tests/golden/*.json` 零改动（零重录）；零改动面 `git status --short` 全空（`core/engine_v2.py` / `core/tracker.py` / `core/pending.py` / `core/interfaces.py` / `agents/` / `filter/` / `scripts/` / `cli.py` / `pyproject.toml` / `uv.lock` / `tests/test_p029_*.py` / `tests/test_p031_*.py` / `tests/test_p033_*.py`） | `pytest -q -k golden`；`git status --short` | I1 / IMPL §1 | ✅ golden **13 passed / 747 deselected**；`git status` 仅 5 M + 1 新文件，零改动面全空 |
| E7 | 测试零 `unittest.mock`；fixture F1-F4 全部落在新文件内，**不修改**既有 `test_p029*` / `test_p031*` / `test_p033*` | `Select-String "unittest.mock"` = 0；`git diff --name-only tests/` 仅新增 1 文件 | IMPL §6 | ✅ `unittest.mock` **0**；`tests/` 仅新增 `test_p034_price_diff_guard.py` |
| E8 | 受影响面快速回归：`-k "golden or p027 or p029 or p031 or p033 or p034"` **86 passed / 0 failed / 0 error**（判据为精确等值，F-S9-P034-1 修正） | 该子集输出末行 | 回归面 | ✅ **86 passed, 674 deselected**（13+24+11+9+17+12 口径精确） |
| E9 | 远端 CI **四 job**（3.10 / 3.11 / 3.12 + `lock-check`）全 success | `gh run view <id> --json conclusion,jobs` | B 组交付纪律 | ✅ CI run `43923154391` **success**——jobs = `lock-check` + `test (3.10)` + `test (3.11)` + `test (3.12)` 全绿 |
| E10 | 四文档互链 0 broken；P-034 行状态 done；CHANGELOG 条目在位 | 机械校验链接数 / broken 数；读回 | 台账惯例 | ✅ 四文档互链 3 条 0 broken；P-034 行已更新；CHANGELOG 首条在位 |
| E11 | 观察/未决登记完整：`R-P034-1~3` / `U-P034-1~3` / `O-P034-1~2` / `F-D3-P034-1~2` / `F-I-P034-1~2` + `O-I-P034-1` / `F-S2-P034-1` + `O-S2-P034-1~4` / `F-S4-P034-1` + `O-S4-P034-1~3`（含 `O-S4-P034-3`）/ `F-S6-P034-1` + `O-S6-P034-1~2` / `F-S9-P034-1~2` + `O-S9-P034-1` 全部有落点 | 读回 DESIGN §5 / IMPL §9 / §11.5 / §12.4 / RESEARCH §11.5 | 治理惯例 | ✅ 全部有落点；`O-P034-3` 引用幻觉已由 Step 10 **F-R5-P034-1** 当轮修正为 `O-S4-P034-3` |

---

## 6. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **37**（A 8 + B 5 + C 7 + D 6 + E 11 = 37，机械计数） |
| 实测列回填 | **36/37 已回填**（Step 9）；**E9 待 CI 回收后回填**（唯一剩余） |

> **RULE-2 统计溯源**：37 由 §1-§5 五张表逐行机械计数得出（A1-A8 = 8 / B1-B5 = 5 / C1-C7 = 7 / D1-D6 = 6 / E1-E11 = 11），非估计值。12 实例由 IMPL §2 计数口径（V1 6 + V2 3 + V3 1 + V4 1 + V5 1）机械相加得出。
>
> **`[待 Step 9]` 字面账目（F-S8-P034-1 当轮补注）**：Step 7 编制时全文机械匹配 **39** = **37 单元格** + 头部规则行 1 处 + 本节标签行 1 处；**37 单元格零预填不变**。Step 9 回填 36 项后，剩余 `[待 Step 9]` 仅 **E9 一处**（CI 回收后回填）。
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
| Step 9 TDD 执行 | DeepSeek-V4.1-Flash（与上游同源） | pass：红态 **3 failed / 9 passed**（三例与 IMPL §11.3 逐项一致）→ 绿 **12 passed**；门禁 **760 / 84 / 121 / 37 / golden 13 零重录 / AST 22** 全绿；1 P3 当轮修正（F-S9-P034-1）+ 2 观察，见 §10 | 2026-11-17 |
| Step 10 ADD 审计 + 终审 | DeepSeek-V4.1-Flash（= 四文档作者同源，**同基座审计 + 同基座终审**；RULE-5 不成立，记 U-P034-3） | pass：Phase 0 **5/5 Tier A** + Phase 1-4 全过（2 hunk 零游离）+ E1-E5 独立复跑全绿；**0 P0-P2 + 1 P3 当轮修正（F-R5-P034-1 `O-P034-3` 引用幻觉）+ 2 观察**，见 §11 | 2026-11-17 |
| U-P034-3 异构终审 | GLM-5.3-Flash（≠ 作者与五轮复审者 DeepSeek-V4.1-Flash，**异构成立**） | pass：E1-E5 五项独立复核全过（E4 运行期复验 **7/7 PASS**）+ **2 P3 当轮修正（F-U3-P034-1 审计区间口径 / F-U3-P034-2 台账建行缺口）** + 1 观察，见 §12 | 2026-11-17 |

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

---

## 10. Step 9 TDD 实施记录（2026-11-17）

> **执行基座**: DeepSeek-V4.1-Flash；基线 HEAD `642ec60`；Python312 + `MPLBACKEND=Agg`。

### 10.1 红→绿（F5 两读数）

| 阶段 | 命令 | 读数 |
|------|------|------|
| **红** | `pytest tests/test_p034_price_diff_guard.py -q`（B1 代码未改） | **3 failed, 9 passed, 1 warning**（exit 1）——`[python-0]` `assert False is True` / `[numpy-0]` `差异=inf%` 告警残留 / `v4_zero_close_not_swallowed` `assert False is True` |
| **绿** | 同命令（B1 落地后） | **12 passed in 0.56s**（exit 0） |

红态三例与 IMPL §11.3 E3 预览**逐项一致**；九例回归保护（V1 四例 + V2 三例 + V3 + V5）红态即通过属预期，未伪造红态。

### 10.2 门禁复跑（Step 9 实施后）

| 门禁 | 目标 | 实测 |
|------|------|------|
| 全量 pytest | 760 | ✅ **760 passed**（172 warnings，43.53s） |
| 新测试收集 | 12 实例 / 5 函数 | ✅ **12 tests collected**；`^def test_` = **5** |
| 新测试绿 | 12 passed | ✅ **12 passed** |
| black `--check core tests` | 121 | ✅ **121 files would be left unchanged**（新测试首轮重排 1 文件，O-I-P034-1 预判） |
| mypy `--explicit-package-bases --check-untyped-defs core` | 37 files 0 | ✅ **Success: no issues found in 37 source files** |
| golden | 13 零重录 | ✅ **13 passed, 747 deselected**；`tests/golden/` 零改动 |
| `tests/` .py 数 | 84 | ✅ **84**（`test_*.py` **81**） |
| 回归子集 `-k "golden or p027 or p029 or p031 or p033 or p034"` | 86 | ✅ **86 passed, 674 deselected**（13+24+11+9+17+12 口径精确） |
| AST `except Exception`（十文件口径） | 22 | ✅ **22** |
| `core/` 新增 `except` | 0 | ✅ `git diff core/` 中 `^\+.*\bexcept\b` = **0** |
| 公开签名删除 | 0 | ✅ `git diff` 中 `^-\s*def ` = **0** |
| `uv lock --check` | exit 0 | ✅ **exit 0**（Resolved 148 packages） |
| 零改动面 | 空 | ✅ `git status --short` 仅 5 M + 1 新测试文件 |

### 10.3 顺序敏感四项与单一来源

| # | 约束 | 实测 | 结果 |
|---|------|------|------|
| ① | 守卫在 L316 注释后、L318 ratio 前 | L316 注释 → **L317 条件** → L318 ratio | ✅ |
| ② | `is not None` 在 `and` 左侧（mypy 窄化） | L317 `close_price is not None and is_valid_price(close_price)` | ✅ |
| ③ | CI job 在 `test` 之后同级缩进 | YAML 解析 `jobs = ['test', 'lock-check']` | ✅ |
| ④ | 台账行插在 P-034 之后、U-D1 之前 | §1.4 L82-88 | ✅ |

**单一来源**: `is_valid_price` 全仓 **1 定义**（`core/execution.py:153`）+ **4 调用**（execution L309 守卫 / execution L317 差异校验 / agents L512 / engine_v2 L811）——AST 实测。

### 10.4 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P034-1 | P3 | E8 判据写「**≥ 74 passed**」——下限判据无法检出「p034 未纳入子集」的漂移（74 在漏掉 12 例时仍成立）；实测 **86**（74 + 12） | **当轮修正** E8 判据为「**86 passed / 0 failed / 0 error**」 |
| F-S9-P034-2 | 观察 | 新测试文件首轮被 `black` 重排（1 文件）——O-I-P034-1 预判成立，非缺陷 | 已格式化，门禁 121 unchanged |
| O-S9-P034-1 | 观察 | C7 的「P-034 行 done」须等 Step 10 关闭后置；Step 9 阶段为「in-progress（Step 1-9 完成）」 | 登记（Step 10 复核） |

---

## 11. Step 10 ADD 审计 + 终审（2026-11-17）

> **基座**: **DeepSeek-V4.1-Flash**——与四文档作者**同源** → **RULE-5 异构条件不成立**，本轮为**同基座 ADD 审计 + 同基座终审**（RULE-4 披露）；异构终审由 **U-P034-3** 跟踪（P-032 / U-P032-1 先例）。
> **审计对象**: 区间 `fbed072..f2e719b`（9 提交）；代码面集中于 `de0268d`；审计时点 HEAD `f2e719b`；Python312 + `MPLBACKEND=Agg`。
> **方法**: Phase 0 spec 质量门 → Phase 1 完整性盘点 → Phase 2 保真度（IMPL §4 独立读码 + hunk 逐字比对）→ Phase 3 必要性（逐 hunk 归因）→ Phase 4 语义 → E1-E5 门禁独立复跑 + 盲区扫描；不采信任何未经本轮复现的读数。

### 11.1 Phase 0 spec 质量门（DESIGN_p034）

| 维度 | 得分 | 依据 |
|------|------|------|
| 可测试约束 | 1 | V1-V5 每条断言可机械判定（`success` / `trade.price` / `trade_log` 长度 / caplog 关键字与条数）；红态口径逐实例列明 |
| 模块映射 | 1 | D1→execution §4.1 / D2→workflow §4.2 / D3→PROGRESS §4.3 / D4→不改项 §7 —— 1:1 |
| 接口契约 | 1 | 条件行与 YAML job 逐字给出；`is_valid_price` 复用（不改签名）；§8 回退点 4 项 |
| 修正项 | 1 | F-S2-P034-1 / F-S4-P034-1 / F-S6-P034-1 / F-S8-P034-1 / F-S9-P034-1 全枚举且有回写落点 |
| 跨模块契约 | 1 | I1-I6 + R-P034-1~3 + U-P034-1~3 + O-P034-1~2 + IMPL §1 零改动面清单 |
| **合计** | **5/5 = Tier A** | 无 B 档封顶 |

### 11.2 Phase 1 完整性盘点

| 设计元素 | 应有 | 实测 | 证据 |
|----------|------|------|------|
| 审计区间 | 9 提交 | **10**（区间端点 `fbed072..f2e719b` 实测；原记 9 与内容链 `fbed072..de0268d` 吻合——计数与 diff 两口径混用，U-P034-3 **F-U3-P034-1** 当轮更正，见 §12.2） | `git rev-list --count fbed072..f2e719b` |
| 全区间 diff | — | **10 文件 +1425 / −7**（原记 −6，U-P034-3 实测更正，见 §12.2） | `git diff --shortstat fbed072..f2e719b`（代码 2 + 测试 +136 + 文档 7） |
| 代码 hunk | — | **2** | `tests.yml @@ -43,4 +43,17`（新增 job）/ `execution.py @@ -313,8 +313,8`（条件替换） |
| 新增 `raise` / `except` / `logger.`（代码面） | 0 / 0 / 0 | **0 / 0 / 0** | `git diff ... -- core/ .github/ tests/` 三条正则零命中 |
| 公开签名删除 | 0 | **0** | `^-\s*def ` 零命中 |
| 零改动面 | tracker / pending / interfaces / agents / filter / scripts / cli / pyproject / uv.lock / golden | **零命中** | 10 文件名单核实 |
| 计量 | 零新键（本批无引擎改动） | **0** | 无 `_record_failure` / `skipped_price` 变更 |

### 11.3 Phase 2 保真度（对照 IMPL §4，独立读码）

| 锚点 | 结论 | 证据 |
|------|------|------|
| §4.1 差异校验条件 | **pass** | hunk `-  # 价格合理性检查` / `-  if close_price is not None:` → `+  # P-034 D1：…` / `+  if close_price is not None and is_valid_price(close_price):`，L318-324 **零改动** |
| §4.2 CI job | **pass** | hunk `@@ -43,4 +43,17 @@`：`test` job 4 step 逐行未动；新增 `lock-check`（`@v10.3.3` / `version: "0.11.14"` / 无 `enable-cache` / 无 `\|\| true`） |
| §4.3 台账 8 处 | **pass** | §1.4 L82-88 七行 + U-P031-2（L75）与旧表 U-008 补注 |
| §4.4 CHANGELOG | **pass** | `### Changed` 首条为 P-034 |
| §4.5 ARCHITECTURE §9.2 | **pass** | L335「CI 使用 pip，不校验锁」→「`lock-check` job 以 `uv lock --check` 校验（失败即红）」 |
| 签名零变更 | **pass** | `execute_order` / `is_valid_price` 均未动 |
| 净行数 | **pass** | §12.2 表与 `git diff --numstat 642ec60..de0268d` 逐文件吻合（+316/−48） |

### 11.4 Phase 3 必要性（逐 hunk 归因）

| hunk | 归因 |
|------|------|
| `execution.py @@ -313,8 +313,8`（+2/−2） | §4.1 D1 守卫条件（含注释） |
| `tests.yml @@ -43,4 +43,17`（+13/−0，末尾换行差异计 −1） | §4.2 D2 新增 `lock-check` job |

**零游离行**——两处 hunk 全部可追溯到 DESIGN-D1 / DESIGN-D2。

### 11.5 Phase 4 语义

| 面 | 裁决 |
|----|------|
| 守卫语义 | `is_valid_price` 判「有限正数」→ 无效 close（None/0/NaN/±inf/负）统一跳过；**不改变成交结果**（诊断与决策解耦，修复 R1 的根因） |
| 观测语义 | 合法 close 的 25% / 42.86% 告警逐字保留；无效 close 从「抛异常 / 噪声 / 静默」统一为「安静跳过」——R-P034-1 已披露监控信号变化 |
| 门禁语义 | `lock-check` 失败即 job 失败（C4 实证 exit 1）；测试 job 零改动 → 不改变既有安装与测试路径 |
| 台账语义 | 三源同项（U-P014-3 / U-P031-2 / U-P033-2）收敛为单一跟踪；U-P033-3 标「已裁决不采纳」防误判为待办；U-008 并入 U-P021-2 |
| 复用语义 | `is_valid_price` 1 定义 **4** 调用（含新增 L317），无第二套判定 |

### 11.6 E1-E5 门禁独立复跑（本基座全量重跑）

| 门禁 | 目标 | 实测 |
|------|------|------|
| 全量 pytest | 760 | ✅ **760 passed**（172 warnings，68.17s） |
| black `--check core tests` | 121 | ✅ **121 files would be left unchanged** |
| mypy `--explicit-package-bases --check-untyped-defs core` | 37 files 0 | ✅ **Success: no issues found in 37 source files** |
| golden + P-027/029/031/033/034 回归面 | 86 | ✅ **86 passed, 674 deselected**（13+24+11+9+17+12） |
| `uv lock --check` | exit 0 | ✅ **exit 0** |
| CI（Step 9 两跑） | success | ✅ run `43923154391`（四 job：`lock-check` + 三版本） |

### 11.7 盲区扫描

- **本批新增面**：`core/execution.py` L316-324（前置 `if`，**零 except**）/ `tests/test_p034_price_diff_guard.py`（无 except）/ `.github/workflows/tests.yml`（非 Python）——**零新增静默路径**。
- **既有浮出**：无新增（P-029/P-033 已登记项未变化；AST 十文件口径恒 22）。

### 11.8 发现分级与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-R5-P034-1** | **P3** | **引用幻觉**：DESIGN §9.3 裁决 6 与 §9.4 引「`O-P034-3`」、CHECKLIST E11 声称「`O-P034-1~3`（含 `O-P034-3`）」——但 `O-P034-3` **从未定义**（`1e-9` 边界的实际 ID 是 **`O-S4-P034-3`**，其属 Step 4 观察序列） | **当轮修正**：DESIGN 两处改 `O-S4-P034-3`；CHECKLIST E11 改 `O-P034-1~2` 并注记修正来源 |
| O-R5-P034-1 | 观察 | `tests.yml` 改动后仍无文件末尾换行（`\ No newline at end of file`）——原文件同样无，**非本批回归**；YAML 解析已验证通过 | 登记不改 |
| O-R5-P034-2 | 观察 | 本批 Step 2/4/6/8/10 全部为同基座复审（作者=复审=DeepSeek-V4.1-Flash），RULE-5 全程未满足 | U-P034-3 单一跟踪 |

### 11.9 结论

**结论**: **pass**（Phase 0 **5/5 Tier A** + Phase 1-4 全过 + E1-E5 门禁独立复跑全绿 + 盲区零新增静默；**0 P0/P1/P2 + 1 P3 当轮修正 + 2 观察**）——DESIGN D1-D4 / IMPL §4 与提交代码**语义与文本双闭环**，两处代码 hunk 零游离，**P-034 批次关闭**。
**RULE-5 声明**: 同基座审计与终审（异构不成立）；**U-P034-3 为唯一未闭合过程项**，随批归档、触发条件 = 非 DeepSeek 基座可用时。→ **2026-11-17 已由 GLM-5.3-Flash 补做 pass（见 §12）**。

**提交与 CI**: 本节记录提交 `499524e`（3 文件 **+113/−6**，docs-only，含 F-R5-P034-1 当轮修正）→ CI run `43924423589` **success**（`lock-check` + 3.10 / 3.11 / 3.12 四 job 全绿，EXIT=0）。

---

## 12. U-P034-3 异构终审记录（GLM-5.3-Flash，2026-11-17）

> **基座披露**: 复审基座 **GLM-5.3-Flash ≠ 四文档作者与五轮复审者（Step 2/4/6/8/10）DeepSeek-V4.1-Flash** → **RULE-5 异构条件成立**，本节即 U-P034-3 预留的补做终审（先例 U-P032-1 同型）——P-034 全程首个异构审查，过程链最后一项未决随本节闭合。复审区间 `fbed072..7082c7a`（**12 提交**，`git rev-list --count` 实测）；复审时点 HEAD `7082c7a`。

### 12.1 五项独立复核

| ID | 复核项 | 结论 | 证据 |
|----|--------|------|------|
| E1 | 代码锚点重放 | ✅ | [execution.py](../core/execution.py) L316-317 条件 `if close_price is not None and is_valid_price(close_price):`（`is not None` 在 `and` 左侧，mypy 窄化保留）；L318-324 逐字未动；P-033 守卫 L308-314 在前；`is_valid_price` 定义 L153-161 未动。[tests.yml](../.github/workflows/tests.yml) `lock-check` job：`@v10.3.3` + `version: "0.11.14"`、无 `enable-cache`、无 `\|\| true`；`test` job L9-46 逐行未动 |
| E2 | diff 面核验 | ✅（1 记录口径缺陷当轮修正） | 区间 **12 提交**（`git rev-list --count fbed072..7082c7a`）；代码面新增 `raise` / `except` / `logger.` 全 **0**；`^-\s*def ` 公开签名删除 **0**；零改动面（tracker / pending / interfaces / agents / filter / scripts / cli / pyproject / uv.lock / golden）零命中。**发现 F-U3-P034-1**：§11.2「9 提交 / −6」与区间端点实测不符（10 提交 / −7；9 与内容链 `fbed072..de0268d` 吻合——计数与 diff 两口径混用），§11.2 当轮补正 |
| E3 | 门禁独立复跑 | ✅ | pytest **760 passed** / black **121 unchanged** / mypy **37 files 0** / 回归子集 `-k "golden or p027 or p029 or p031 or p033 or p034"` **86 passed** / P-034 套件 **12 passed** / `uv lock --check` **exit 0**；CI run `43925230603`（`7082c7a`）四 job（`lock-check` + 3.10 / 3.11 / 3.12）全 success |
| E4 | 运行期复验（独立探针） | ✅ **7/7 PASS** | 本基座独立编写 `%TEMP%\p034_u_p0343_probe.py`（非复用 Step 9 测试集）：R1 吞单修复（`success=True trades=1 errors=0`）/ R2 噪声消除（`diff_warns=0`）/ R3 无效 close 静默跳过（nan / neg 均跳过）/ 合法价 25.00% 告警保留（`warns=1 text=True`）/ None 回归（`success=True`）/ P-033 守卫交互（`success=False guard=1`）/ `is_valid_price` 语义 **8/8** |
| E5 | F-R5-P034-1 修正到位 | ✅ | `O-P034-3` 现存 5 处命中（本文 E11 行 / 签字表 Step 10 行 / §11.8 F-R5-P034-1 行、PROGRESS P-034 行 / §3.39.9 发现分级行）全部为「修正历史」合法引用；DESIGN §9.3 / §9.4 裸引用已清零（均改 `O-S4-P034-3`） |

### 12.2 发现分级与当轮处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-U3-P034-1** | **P3** | **审计区间记录口径混用**：§11.2 记「审计区间 9 提交（证据 `git log fbed072..f2e719b`）/ 全区间 +1425/−6」——实测 `fbed072..f2e719b` = **10 提交、+1425/−7**；「9」仅与内容链 `fbed072..de0268d`（代码提交链终点）吻合，即计数按内容链、diff 按区间端点两口径被混写（同基座终审漏检，异构复审实测揪出） | **当轮修正**：§11.2 两行按区间端点实测值更正（10 提交 / −7）并注记内容链口径；PROGRESS §3.39.9 同步补正 |
| **F-U3-P034-2** | **P3** | **D5 派生纪律执行缺口**：P-034 自立纪律「本批新增 U-\*/O-\* 是否已在 §1.4 建行」，但 U-P034-1（`setup-uv` 维护）/ U-P034-2（外部调用面）/ U-P034-3（异构终审预留）仅散落 §3.39.9 正文，未建 §1.4 行——散落正文同型问题第四次出现（P-030 / P-032 / P-034 台账收口之后，本批自身收尾仍漏） | **当轮修正**：PROGRESS §1.4 建三行（U-P034-1 pending / U-P034-2 pending / **U-P034-3 done**） |
| O-U3-P034-1 | 观察 | 终审区间（12 提交）> 审计区间（10 提交）：差额 2 提交 = 终审记录（`499524e`）与 CI 回填（`7082c7a`）——审计后追加的流程提交，正常时序非矛盾 | 登记不改 |

### 12.3 结论

**结论**: **pass**（E1-E5 五项独立复核全过 + 运行期复验 **7/7**；**0 P0/P1/P2 + 2 P3 当轮修正 + 1 观察**）——**U-P034-3 关闭**，P-034 过程链（Step 1-10 + 五轮同基座复审 + 同基座终审 + 异构终审）**全闭合**；两项 P3 均为文档记录缺陷（零代码影响），批次维持关闭。

**提交与 CI**: 本节记录提交后回填（占位）。
