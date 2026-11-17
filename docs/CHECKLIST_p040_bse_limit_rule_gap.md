# CHECKLIST：P-040 bse 规则表日期维度补齐

> **批次**: P-040 · **T1**（Layer-1：`tests/`；生产面 `filter/limit_rules.py`）
> **上游**: [IMPL_p040](IMPL_p040_bse_limit_rule_gap.md)（§2 精确规格 / §3 红态 / §6 Step 6 复审 pass：1 P2 + 1 P3）；[DESIGN_p040](DESIGN_p040_bse_limit_rule_gap.md)（D1-D4 / I1-I6 / §7 Step 4 复审 pass：1 P2 + 2 P3）；[RESEARCH_p040](RESEARCH_p040_bse_limit_rule_gap.md)（§7 M-A / §8 / §14）
> **状态**: **批次关闭（2026-11-17）：25/25 + Step 10 审计 pass + U-P040-1 异构终审 pass（GLM-5.3-Flash，0 P1/P2 + 1 P3）**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **基线读数（@`fb32ac0`）**: pytest **765 passed** / golden **13 passed, 752 deselected** / black `core tests` **122**（全仓 **189**）/ mypy 12 面 `Success ... 103 source files` / AST `except Exception` **22** / `tests/*.py` **85** / `uv lock --check` exit **0**
> **目标读数**: pytest **771** / golden 13 零重录 / black **123**（全仓 **190**）/ mypy 12 面 **0** / AST **22** / `tests/*.py` **86**

---

## 1. A 组：规则表变更（IMPL §2.1-2.2）

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| A1 | bse 段由 2 条替换为 4 条，内容与 IMPL §2.1 **逐字一致** | 读码 + `git diff` | ✅ L67-72 四段 + 2 行注释，逐字一致（`7 4`） |
| A2 | 首段 `2018-01-15..2020-07-27`，`up=1.00` / `down=-0.50`（False/True 两态） | 读码逐字 | ✅ L69 / L71 |
| A3 | 次段 `2020-07-27..None`，`up=0.30` / `down=-0.30`（两态） | 读码逐字 | ✅ L70 / L72 |
| A4 | `RULESET_VERSION` = `"cn_a_2026_11"` | 读码 L19 | ✅ `cn_a_2026_11` |
| A5 | 其余 9 条规则（main 3 / gem 4 / star 2）逐字不动；`infer_board` / `resolve_limit` / `build_limit_prices` 签名不动 | `git diff` 仅 bse 段 + 版本行 | ✅ diff 仅 2 处；`^[+-]\s*def ` = **0** |
| A6 | 新增 `except` / `raise` / `# type: ignore` 均 **0**；`_RULE_INDEX` 不动 | `git diff -U0` 正则 | ✅ 三类均 0；L75-78 未动 |

## 2. B 组：测试（IMPL §2.3，V1-V6）

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| B1 | V1 `2020-07-26` 两态 `(1.00, -0.50)` | 用例 | ✅ PASS |
| B2 | V2 `2020-07-27` 两态 `(0.30, -0.30)`（半开边界） | 用例 | ✅ PASS |
| B3 | V3 北交所期 30% + `RULESET_VERSION == "cn_a_2026_11"` | 用例 | ✅ PASS |
| B4 | V4 `2018-01-12` 抛 `LimitRuleError`（fail-fast 保留） | 用例 | ✅ PASS |
| B5 | V5 `bdate_range("2020-01-23","2021-11-12")` 逐日 × 两态不抛 | 用例 | ✅ PASS（436 日缺口 → 0） |
| B6 | V6 `build_limit_prices` 不抛；集合竞价段 `10 → 20/5`；复牌日前收 NaN → `up/down` NaN | 用例 | ✅ PASS |
| B7 | 红态留证 `5 failed, 1 passed`（V1/V2/V3/V5/V6 FAIL；V4 PASS）→ 绿 `6 passed` | pytest 输出逐字 | ✅ 红 `5 failed, 1 passed in 0.85s` → 绿 `6 passed in 0.58s`（F-S9-P040-1 订正） |

## 3. C 组：不变式（DESIGN §3）

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| C1 | **I1** golden **13 零重录**；`tests/golden/` 无改动 | `pytest -k golden` + `git status` | ✅ `13 passed, 758 deselected`；目录空 |
| C2 | **I2** pytest **771**（765 + 6）；既有 765 零失败 | 全量末行 | ✅ `771 passed, 172 warnings in 85.24s` |
| C3 | **I3** mypy 12 面 0；新增 ignore 0 | 门禁命令 | ✅ `Success: no issues found in 103 source files` |
| C4 | **I4** 公开签名零变更（`infer_board` / `resolve_limit` / `build_limit_prices`） | `git diff` 中 `^[+-]\s*def ` = 0 | ✅ 0 |
| C5 | **I5** AST `except Exception` 恒 **22**；`^\+.*except` / `^\+.*raise ` = 0 | AST 命令 + 正则 | ✅ AST **22**；两类新增 0 |
| C6 | **I6** 其余 board 规则 9 条零改动（diff 仅 bse 段 + 版本行） | `git diff` | ✅ 9 条零改动 |

## 4. D 组：门禁、真实数据与文档

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| D1 | black `core tests` **123** / 全仓 **190** | `black --check` 两口径 | ✅ `123` / `190` unchanged |
| D2 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零改动 | 命令 + `git diff` | ✅ exit 0；两文件 diff 空 |
| D3 | 门禁双载体零改动；单提交原子（`filter/limit_rules.py` + 新测试） | `git diff --numstat` + `git show --stat` | ✅ 双载体 diff 空；提交 `5adab76`（7 文件 +573/−6）；CI run `44081519166` 四 job 全绿（lock-check 9s / 3.10 2m1s / 3.11 2m6s / 3.12 2m1s） |
| D4 | **真实数据**：`setup()` 不再抛 `LimitRuleError`，推进到 U-P038-1 `FileNotFoundError`（`UTR_turnover_new.pkl`） | `BacktestEngineV2(cfg).setup()` 探针 | ✅ `[A] PASS: advanced to FileNotFoundError`；边界两读 `(1.00,−0.50)` / `(0.30,−0.30)` |
| D5 | 文档回填：IMPL §7 / PROGRESS §3.45 / CHANGELOG / CHECKLIST 实测列 / U-P039-4 → done | 读回 | ✅ IMPL §4/§7 + PROGRESS + CHANGELOG + 25/25；U-P039-4 → done |
| D6 | 未决登记：U-P040-1（异构终审）/ O-P040-1~5 | 读回 §1.4 | ✅ 六项建行 |

---

## 5. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **25**（A 6 + B 7 + C 6 + D 6 = 25，机械计数；其中 B7 为红态留证项） |
| 实测列回填 | **25/25**（A 6 / B 7 / C 6 / D 6 全 `✅ + 证据`；D3 hash/CI 已回填） |

> **RULE-2 统计溯源**：25 = 6 + 7 + 6 + 6（逐表行数，非估计）。
> **RULE-5 声明**：Step 2/4/6/8 复审均自报 DeepSeek-V4.1-Flash（同源）→ 异构四轮未成立；U-P040-1 跟踪（→ §9 异构终审已由 GLM-5.3-Flash 补齐，pass）。

---

## 6. Step 7 → Step 8 交接

1. 核红态口径：IMPL §3 `4 failed, 2 passed` 与 B7 逐字一致。
2. 核计数链：765 + 6 = **771**；122 + 1 = **123**；189 + 1 = **190**；85 + 1 = **86**。
3. 核零预填：`[待 Step 9]` = **25** 单元格。
4. 核 ID 不混用：DESIGN 决策 `D1-D4` vs 本文件 **D 组**；引用一律 `DESIGN-D*`。

---

## 7. Step 8 一致性 Review 记录（同基座独立视角，2026-11-17）

> **基座披露（RULE-4）**: 自报 DeepSeek-V4.1-Flash → 同源，RULE-5 不成立；U-P040-1 累计第 4 轮。

### 7.1 机械五项

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 链接校验 | 四文档相对链接存在；`file:///` 绝对锚点不参与相对校验 | ✅ 0 broken |
| 2 | ID 闭环 | A1-A6 / B1-B7 / C1-C6 / D1-D6 连续无跳号；表行 **25** | ✅ |
| 3 | 计数自洽 | 25 = 6 + 7 + 6 + 6 | ✅ |
| 4 | 零预填 | `[待 Step 9]` = **25**（全部单元格）；无 `✅` / `❌` | ✅ |
| 5 | U-P040-1 | RESEARCH §10 / §14、DESIGN §7、IMPL §6、本文件 §5 各 ≥1 处 | ✅ |

### 7.2 对齐矩阵

| # | 项 | 判定 | 证据 |
|---|----|------|------|
| 1 | 红态口径 | ✅ | IMPL §3「4 failed, 2 passed」与 B7 逐字一致 |
| 2 | 规则四行 | ✅ | DESIGN-D1 / IMPL §2.1 / A1-A3 三处一致 |
| 3 | 六用例 | ✅ | DESIGN-D4 / IMPL §2.3 / B1-B6 一一对应 |
| 4 | 门禁目标 | ✅ | DESIGN §1 / IMPL §4 / 本文件 D1-D2 一致（771 / 123 / 190 / 22） |
| 5 | 边界声明 | ✅ | 「首日不设涨跌幅由前收 NaN 覆盖」在 RESEARCH §3.2 / DESIGN-S4 / V6 三处一致 |

### 7.3 发现与当轮处置（0 P1/P2 + 1 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P040-1 | P3 | 本文件 B 组 7 项而 DESIGN D4 标题写「6 用例」（B7 为红态留证项，非用例） | §5 计数显式标注「6 用例 + 1 红态项 = B 组 7 行」 |

### 7.4 结论

**Step 8 Review pass（0 P1/P2 + 1 P3 当轮处置）**——25 项可执行、四文档口径闭环；**准予进入 Step 9 TDD 实施**。
**RULE-5**：第 4 轮同基座 → U-P040-1 pending。

---

## 8. Step 10 ADD 审计记录（2026-11-17）

> **审计基线**: 代码提交 `5adab76`；文档 HEAD `da2890f`（E3 行号绑 `5adab76`）。
> **审计者（RULE-4）**: 自报 DeepSeek-V4.1-Flash（同源）→ RULE-5 不成立；U-P040-1 累计第 5 轮。

### 8.1 四阶段结论

| 阶段 | 审什么 | 判定 | 关键证据 |
|------|--------|------|---------|
| **Phase 0** | Spec 质量门 | ✅ pass | 四文档模糊词扫描（`合理处理/适当时机/尽量/视情况/酌情`）**0 命中**（E1）；D1 日期/值/行数、D4 六用例、A/B/C/D 25 项均可机械核验 |
| **Phase 1** | 完整性（design → code） | ✅ pass | D1-D4 全部落地：4 条 bse 规则 + 版本行 + 6 用例 + 三不变式（E1 `git show` + E3 读码） |
| **Phase 2** | 忠实度（双向） | ✅ pass | 生产面 diff 与 IMPL §2.1/2.2 **逐字一致**；测试文件 76 行与 IMPL §2.3 **逐字一致**（6 个 `test_v*` 函数，E1 `--collect-only` = 6） |
| **Phase 3** | 必要性（code → design） | ✅ pass | 提交 7 文件中生产面仅 `filter/limit_rules.py` **+7/−4**；新增行全部归属 DESIGN-D1；`^[+-]\s*def ` = 0；`_RULE_INDEX` 未动；无新增 `except`/`raise`/`type: ignore` |
| **Phase 4** | 语义（意图层） | ✅ pass（附 1 项范围外发现） | 崩溃消除（E2 11,800 次覆盖 0 缺口 + D4 `setup()` 推进）；半开边界正确（`2018-01-15` 命中 / `01-14` 抛）；ST 两态均解析；真实数据掩码 0 误判；号段盲区见 F-S10-P040-4 |

### 8.2 发现与处置（0 P1 + 1 P2 + 3 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S10-P040-4** | **P2** | **范围外发现（E4 盲区扫描）**：真实数据 5,688 列中 **294 个代码未被 `infer_board` 识别**，回落 `main`——`920` 号段 **293 只**（北交所新号段）+ `302` 号段 **1 只**（`302132`，创业板）。E2 实锤：`302132` 2023-02-02..02-10 连续 +20.00%~+20.04% 收盘（主板 10% 物理不可能）；`920` 段 **9,494** 个 `\|ret\|>10.5%` 单元格、最高 **100%**（新三板集合竞价特征）。掩码量化：920 按 main = 涨停 **2,072** / 跌停 **1,163** 命中，按 bse = **319 / 164** → 约 **2,752** 单元格误判；`302132` main **10/1** vs gem **7/1** → 3 处误判 | **登记 U-P040-2（P2）**，建议立项 P-041（`infer_board` 增 `920→bse`、`302→gem`；P-040 已使 bse 规则自 2018-01-15 可覆盖，修复不再有崩溃风险）；本批不扩做 |
| F-S10-P040-1 | P3 | `2018-01-15` 含端点无 CI 断言（V4 只测 `2018-01-12` fail-fast；V1 测段内 `2020-07-26`）→ 若误改为 `2018-01-16`，6 用例仍全绿 | E2 S-3 已运行期证实（`2018-01-15` 两态命中 `(1.0, -0.5)`；`01-14` 抛）；登记 **O-P040-6**（测试加固，不阻断） |
| F-S10-P040-2 | P3 | V5 docstring「436 日缺口 → 0」与 `bdate_range` 实测 **472** 个工作日口径混用：472 = 测试覆盖的非交易日含入工作日集合 ⊇ 436 = 真实缺口交易日 | 接受不改：两数各有出处，本行显式并列（断言有效性不受影响） |
| F-S10-P040-3 | P3 | 「4380 单元格」为 3 代码 × 1460 交易日（含 `open`/`ref` NaN 的停牌行）；审计 E2 有效单元格（双侧有限）为 **1,080**，0 命中 | 接受：口径差异不改变「0 误判」结论；本行并列两口径 |

### 8.3 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|---|---|---|
| `pytest tests/test_p040_... -q`（E1） | B1-B7 / D4 | ✅ `collected 6 items / 6 passed in 0.54s` |
| `git show --stat 5adab76` + `git show -- filter/limit_rules.py`（E1） | A1-A6 / C4 / C6 / D3 / Phase 2-3 | ✅ 7 文件；生产面 `+7/−4` 与 IMPL §2.1 逐字；`def` 变更 0 |
| `RULESET_VERSION` 全仓扫描（E1，9 处） | A4 / B3 | ✅ 无旧值 `cn_a_2026_07` 残留 |
| 规格模糊词扫描（E1，四文档） | Phase 0 | ✅ 0 命中 |
| 真实数据覆盖矩阵（E2，对抗性：全板块 × 全日期 × 两态） | D2-S2/S3 / Phase 4 | ✅ 11,800 次解析、**0** 缺口 |
| 板块数据首日 vs 规则起（E2，防「同型缺口」被动场景） | Phase 4 / E4 | ✅ main/gem/star/bse 4/4 `covered=True`（数据首日 2020-01-02） |
| 半开边界双探针（E2，含负例） | D2-S1/S3 | ✅ `2018-01-15` 命中；`2018-01-14` 两态均 `LimitRuleError` |
| 真实 bse 掩码命中（E2，生产 EPS/open 口径） | D2-S4 / D4 | ✅ 1,080 有效单元格、涨停 0 / 跌停 0（与 RESEARCH 4380 口径并列见 F-S10-P040-3） |
| 号段盲区扫描（E2/E4，扫描范围：`stock_close.pkl` 全 5,688 列前缀） | Phase 4 / 全表 | **发现 2 个号段 / 294 只**（`920`×293、`302`×1）→ U-P040-2 |
| 静态读码（E3 @`5adab76`） | A2/A3/I6 / D3 | ✅ L19 版本行、L67-72 四段与 IMPL 逐字 |
| E5 推测 | — | 无（未覆盖项：无） |

### 8.4 结论

**Step 10 ADD 审计 pass**——Phase 0-4 全过；**P1 = 0**；P2 = 1（F-S10-P040-4 为范围外发现，已登记 U-P040-2，不阻断本批）；P3 = 3（1 项登记 O-P040-6，2 项接受并列口径）。主缺陷 U-P039-4 修复的设计落地经 E1/E2/E3 三重取证确认；**批次仍 in-progress，待 U-P040-1 异构终审**。

> **审计记录提交**: `96f499b`；CI run **`44082820020`** 四 job 全绿（lock-check 8s / 3.10 1m41s / 3.11 1m11s / 3.12 1m20s）。

---

## 9. U-P040-1 异构终审记录（GLM-5.3-Flash，2026-11-17）

> **基座披露（RULE-4/RULE-5）**: 终审会话自报 `GLM-5.3-Flash` ≠ 作者 DeepSeek-V4.1-Flash → **异构终审成立**（作者 + Step 2/4/6/8/10 五轮均同源）。
> **终审范围**: 四文档 + Step 9 取证 + Step 10 审计 + 门禁；E3 行号绑 `5adab76`（`git log -1 -- filter/limit_rules.py` 与 `-- tests/test_p040_bse_limit_rule_gap.py` 均 = `5adab76`；终审时 HEAD `a9bf891`）。

### 9.1 E1 门禁七项独立复跑（全部命中）

| # | 门禁 | 口径 | 实测 |
|---|------|------|------|
| 1 | pytest 全量 | `pytest tests/ --tb=short -q -p no:cacheprovider` | ✅ `771 passed, 172 warnings in 64.62s` |
| 2 | golden | `pytest -k golden` + `git status --short tests/golden/` | ✅ `13 passed, 758 deselected`；目录干净 |
| 3 | black 双口径 | `black --check core tests` / `black --check .` | ✅ `123` / `190` unchanged |
| 4 | mypy 12 面 | CI 逐字命令（tests.yml L46） | ✅ `Success: no issues found in 103 source files` |
| 5 | AST `except Exception` | [IMPL_p029 §6](IMPL_p029_silent_exception_governance_phase4.md) 单行命令 | ✅ **22** |
| 6 | `tests/*.py` | 顶层计数 | ✅ **86** |
| 7 | `uv lock --check` | 本地 uv | ✅ exit **0** |

### 9.2 E2 运行时探针（独立编写，5 项 + 1 对抗探针全过）

| # | 探针 | 读数 | 判定 |
|---|------|------|------|
| 1 | **红态内存复现**（`RULES`→旧 2 条 + 版本→`cn_a_2026_07`，importlib 按路径加载 6 用例逐个执行，仓库零改动） | `{v1: FAIL(LimitRuleError), v2: FAIL(LimitRuleError), v3: FAIL(AssertionError), v4: PASS, v5: FAIL(LimitRuleError), v6: FAIL(LimitRuleError)}` = **5F/1P** | ✅ 与 B7 红态逐字一致 |
| 2 | 边界语义 + 区间不相交 | `2018-01-12/14` 两态 RAISE；`01-15` 命中 `(1.0,−0.5)`；`2020-07-26 / 07-27 / 2021-11-15 / 2023-06-01` 分段正确；四组 `(board,is_st)` 零重叠 | ✅ |
| 3 | 真实数据量化 | 窗口 **1460**（首 `2020-01-23`）/ 缺口 **436**（`2020-01-23..2021-11-12`）/ 3 只 `first=2020-01-02`、`n=374/371/371`、末日 `2021-10-20/11-05/11-03` / 复牌首日收益 **−19.4813% / −30.7036% / −18.2927%** / 窗口掩码 **0 涨停 / 0 跌停**（gross 4380，有效 1052） | ✅ RESEARCH §3.1-3.5 全部复算成立 |
| 4 | 号段盲区复核（U-P040-2） | `920`×**293** + `302`×**1** = 294（补识别后未识别归 **0**）；`302132` 2023-02-02..02-13 连续 **8 日 ≈+20.0%**；`920` 段 `\|ret\|>10.5%` = **9494**、max **100.00%**；掩码 @main `248957/2072/1163` vs @bse `248957/319/164`，误判差 **2752** | ✅ Step 10 F-S10-P040-4 量化逐位吻合 |
| 5 | `engine.setup()` 真实数据 | 推进到 `FileNotFoundError: 因子文件不存在: ...UTR_turnover_new.pkl`（U-P038-1）；`trade_dates=1460, first=2020-01-23, last=2026-01-30`；`LimitRuleError` 消失 | ✅ C1 复现 |
| 6 | 对抗探针：真实数据「首日不设涨跌幅」 | `2020-07-24`（停牌）与 `2020-07-27`（复牌首日）三只 `limit_up/down` **全 NaN**；`2020-07-28` = 复牌收盘 ×(1±30%)（up 17.36/16.90/52.26，down 9.34/9.10/28.14） | ✅ S4 机制端到端成立 |

### 9.3 E3 静态读码（@`5adab76`）

- [limit_rules.py:19](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L19) `RULESET_VERSION = "cn_a_2026_11"` 与 [L67-72](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L67-L72) bse 四段 + 两行注释——与 IMPL §2.1/2.2、DESIGN-D1 **逐字一致**。
- [tests/test_p040_bse_limit_rule_gap.py](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p040_bse_limit_rule_gap.py) 76 行——与 IMPL §2.3 **逐字一致**。
- `len(RULES)` = **13**（main 3 + gem 4 + star 2 + bse 4）。

### 9.4 E4 盲区扫描（发现 1 项）

| # | 扫描范围 | 结果 |
|---|----------|------|
| 1 | `cn_a_2026_07` 全仓 15 处 | ✅ 均为历史记载（P-012 文档 / DESIGN_backtest_validation 示例 / 本批改前记录），无「现值」误写 |
| 2 | golden JSON 是否嵌入版本号 | ✅ `tests/golden/` 无 `ruleset_version` 字段 → 版本 bump 与 golden 零耦合（13 通过的机制解释） |
| 3 | `*.py` 中散落 bse 日期魔数（`2021-11-15` 等） | ✅ 仅 RULES 定义处与 V3 测试常量 |
| 4 | `len(RULES)` 条数口径 | **发现 1 项**：DESIGN §6/§7.1 写「11 → **15**（+4）」，实测 **11 → 13** → F-U3-P040-1 |
| 5 | CI run 复核 | ✅ `44082016579` / `44082820020` / `44083231213`（至 HEAD `a9bf891`）三 run 四 job 全 success |

### 9.5 发现与当轮处置（0 P1/P2 + 1 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-U3-P040-1 | P3 | [DESIGN_p040](DESIGN_p040_bse_limit_rule_gap.md) §6 L104「线性过滤（11 → 15 条）」与 §7.1 L120「条数 11 → **15**（+4）」算术错误：旧表 11 条、bse 2→4 为**替换**（−2+4），净 **+2** → 实测 13；五轮同源复核均未拦住（条数核对缺独立可重放命令） | 两处当轮订正并注记终审来源；机械口径以 E2 `RULES=13 条` 为准 |

### 9.6 结论

**U-P040-1 异构终审 pass（GLM-5.3-Flash，RULE-5 成立）**——E1 七门禁 / E2 六探针 / E3 静态读码 / E4 盲区扫描（1 P3 当轮订正）/ E5 无推测入结论；**0 P1/P2**。
**批次 P-040 关闭**：主缺陷 U-P039-4 修复经异构独立复核确认；U-P040-2（P2，920/302 号段，约 2752 单元格掩码误判）待立项。