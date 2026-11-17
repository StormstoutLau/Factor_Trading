# CHECKLIST：P-040 bse 规则表日期维度补齐

> **批次**: P-040 · **T1**（Layer-1：`tests/`；生产面 `filter/limit_rules.py`）
> **上游**: [IMPL_p040](IMPL_p040_bse_limit_rule_gap.md)（§2 精确规格 / §3 红态 / §6 Step 6 复审 pass：1 P2 + 1 P3）；[DESIGN_p040](DESIGN_p040_bse_limit_rule_gap.md)（D1-D4 / I1-I6 / §7 Step 4 复审 pass：1 P2 + 2 P3）；[RESEARCH_p040](RESEARCH_p040_bse_limit_rule_gap.md)（§7 M-A / §8 / §14）
> **状态**: **Step 9 完成（25/25），待提交回填 D3**
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
| D3 | 门禁双载体零改动；单提交原子（`filter/limit_rules.py` + 新测试） | `git diff --numstat` + `git show --stat` | ✅ 双载体 diff 空；单提交（hash/CI 待回填） |
| D4 | **真实数据**：`setup()` 不再抛 `LimitRuleError`，推进到 U-P038-1 `FileNotFoundError`（`UTR_turnover_new.pkl`） | `BacktestEngineV2(cfg).setup()` 探针 | ✅ `[A] PASS: advanced to FileNotFoundError`；边界两读 `(1.00,−0.50)` / `(0.30,−0.30)` |
| D5 | 文档回填：IMPL §7 / PROGRESS §3.45 / CHANGELOG / CHECKLIST 实测列 / U-P039-4 → done | 读回 | ✅ IMPL §4/§7 + PROGRESS + CHANGELOG + 25/25；U-P039-4 → done |
| D6 | 未决登记：U-P040-1（异构终审）/ O-P040-1~5 | 读回 §1.4 | ✅ 六项建行 |

---

## 5. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **25**（A 6 + B 7 + C 6 + D 6 = 25，机械计数；其中 B7 为红态留证项） |
| 实测列回填 | **25/25**（A 6 / B 7 / C 6 / D 6 全 `✅ + 证据`；D3 的 hash/CI 待提交回填） |

> **RULE-2 统计溯源**：25 = 6 + 7 + 6 + 6（逐表行数，非估计）。
> **RULE-5 声明**：Step 2/4/6/8 复审均自报 DeepSeek-V4.1-Flash（同源）→ 异构四轮未成立；U-P040-1 跟踪。

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