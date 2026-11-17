# CHECKLIST：P-041 infer_board 号段表补齐（U-P040-2）

> **批次**: P-041 · **T1**（Layer-1：`tests/`；生产面 `filter/limit_rules.py`）
> **上游**: [IMPL_p041](IMPL_p041_infer_board_segments.md)（§2 精确规格 / §3 红态 / §6 Step 6 复审 pass：1 P2 + 2 P3）；[DESIGN_p041](DESIGN_p041_infer_board_segments.md)（D1-D4 / I1-I7 / §7 Step 4 复审 pass：1 P2 + 2 P3）；[RESEARCH_p041](RESEARCH_p041_infer_board_segments.md)（§7 M-A / §8 S1-S7 / §14）
> **状态**: **Step 10 审计完成（P1=0 / P2=0），CI 全绿，待 U-P041-1 异构终审**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`
> **基线读数（@`24688ab`）**: pytest **771 passed** / golden **13 passed, 758 deselected** / black `core tests` **123**（全仓 **190**）/ mypy 12 面 `Success ... 103 source files` / AST `except Exception` **22** / `tests/*.py` **86** / `uv lock --check` exit **0**
> **目标读数**: pytest **778** / golden 13 零重录 / black **124**（全仓 **191**）/ mypy 12 面 **0** / AST **22** / `tests/*.py` **87**

---

## 1. A 组：代码变更（DESIGN-D1/D2，IMPL §2.1-2.3）

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| A1 | 模块 docstring L5 更新为「300/301/302→gem；688/689→star；8/4/920 开头→bse」 | 读码 + `git diff` | ✅ L5 逐字一致 |
| A2 | gem 前缀元组 = `("300", "301", "302")` | 读码逐字 | ✅ L85 |
| A3 | bse 前缀元组 = `("8", "4", "920")` | 读码逐字 | ✅ L89 |
| A4 | `RULESET_VERSION` = `"cn_a_2026_11b"` | 读码 L19 | ✅ `cn_a_2026_11b` |
| A5 | `RULES` 13 条 / `resolve_limit` / `build_limit_prices` 逐字不动；`^[+-]\s*def ` = 0 | `git diff` 仅 3 处（docstring / 两元组 / 版本行） | ✅ `4 4`（4 行）；def 变更 **0** |
| A6 | 新增 `except` / `raise` / `# type: ignore` 均 **0**；`_RULE_INDEX` 不动 | `git diff -U0` 正则 | ✅ 三类均 0；L75-78 未动 |

## 2. B 组：测试（IMPL §2.4-2.5，V1-V7 + 2 取证项）

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| B1 | V1 `920000/920493/920931` → `bse` | 用例 | ✅ PASS |
| B2 | V2 `302132` → `gem` | 用例 | ✅ PASS |
| B3 | V3 既有前缀矩阵 15 项非回归（含 `700001→main`） | 用例 | ✅ PASS（15/15） |
| B4 | V4 920 跨制度期：`07-23/07-24` `20/5`、`07-27/07-28` `13/7` | 用例 | ✅ PASS |
| B5 | V5 302 跨注册制：`08-21` `11/9`、`08-24` `12/8` | 用例 | ✅ PASS |
| B6 | V6 版本 `cn_a_2026_11b` + `unknown_board_count()` 调用前后不变 | 用例 | ✅ PASS |
| B7 | V7 带后缀 `920493.BJ`→bse、`302132.SZ`→gem | 用例 | ✅ PASS |
| B8 | 红态留证 `6 failed, 1 passed`（V3 唯一 PASS） | pytest 输出逐字 | ✅ 红 `6 failed, 1 passed in 0.73s` |
| B9 | P-040 文件两行订正后 `6 passed`（含 V3 新版本断言） | pytest 输出 | ✅ P-040 `6 passed`；两文件合计 `13 passed in 0.66s` |

## 3. C 组：不变式（DESIGN §3）

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| C1 | **I1** golden **13 零重录**；`tests/golden/` 无改动 | `pytest -k golden` + `git status` | ✅ `13 passed, 765 deselected`；目录净 |
| C2 | **I2** pytest **778**（771 + 7）；既有 771 零失败 | 全量末行 | ✅ `778 passed, 172 warnings in 90.61s` |
| C3 | **I3** mypy 12 面 0；新增 ignore 0 | CI 逐字命令 | ✅ `Success: no issues found in 103 source files`；ignore **0** |
| C4 | **I4** 公开签名零变更（`infer_board` / `resolve_limit` / `build_limit_prices` / `RULES` 类型） | `git diff` 中 `^[+-]\s*def ` = 0 | ✅ **0** |
| C5 | **I5** AST `except Exception` 恒 **22**；新增 `except` / `raise` = 0 | AST 命令 + 正则 | ✅ AST **22**；两类新增 0 |
| C6 | **I6** `RULES` 13 条零改动 | `git diff` | ✅ 13 条零改动（`len(RULES)=13`） |
| C7 | **I7** 既有测试仅 P-040 两行；`test_limit_rules.py` 7 用例零改动 | `git diff --stat tests/` | ✅ P-040 `2 2`；`test_limit_rules.py` diff 空 |

## 4. D 组：门禁、真实数据与文档

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| D1 | black `core tests` **124** / 全仓 **191** | `black --check` 两口径 | ✅ `124` / `191` unchanged |
| D2 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零改动 | 命令 + `git diff` | ✅ exit 0；两文件 diff 空 |
| D3 | 门禁双载体零改动；单提交原子（生产代码 + 2 测试文件 + 文档） | `git diff --numstat` + `git show --stat` | ✅ 双载体 diff 空；提交 `0196e24`（9 文件 +934/−7）；CI run `44091229154` 四 job 全绿（lock-check 6s / 3.10 2m5s / 3.11 1m41s / 3.12 1m22s） |
| D4 | **真实数据**：`infer_board("920000")=="bse"`、`("302132")=="gem"`；**全 5,688 列遍历后** `unknown_board_count()==0`；`len(RULES)==13` | E2 探针 | ✅ 2/2 映射正确；920=293 / 302=1 / 总列 5,688；`len(RULES)=13`；`unknown=0` |
| D5 | **真实数据**：掩码翻转 **2,755**（920：2,752；302132：3）；@bse `319/164`、@gem `7/1`（口径：`EPS=0.005`、`open`、`is_st=False`，`st.pkl` 缺失） | E2 探针 | ✅ `2072/1163 → 319/164` 与 `10/1 → 7/1`；翻转 **2,755** |
| D6 | **真实数据**：`engine.setup()` 仍推进到 U-P038-1 `FileNotFoundError`（`UTR_turnover_new.pkl`），不抛 `LimitRuleError` | `BacktestEngineV2(cfg).setup()` 探针 | ✅ `[D6] PASS`；`trade_dates=1460` |
| D7 | 文档回填：IMPL §7 / PROGRESS §3.46.x / CHANGELOG / CHECKLIST 实测列 / U-P040-2 → done | 读回 | ✅ IMPL §7 + PROGRESS + CHANGELOG + 30/30；U-P040-2 → done |
| D8 | 未决登记：U-P041-1（异构终审）/ O-P041-1~4 | 读回 §1.4 | ✅ 五行登记 |

---

## 5. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **30**（A 6 + B 9 + C 7 + D 8 = 30，机械计数；B8/B9 为取证项非新用例） |
| 实测列回填 | **30/30**（A 6 / B 9 / C 7 / D 8 全 `✅ + 证据`；D3 hash/CI 已回填） |

> **RULE-2 统计溯源**：30 = 6 + 9 + 7 + 8（逐表行数，非估计）。
> **RULE-5 声明**：Step 2/4/6/8 复审均自报 DeepSeek-V4.1-Flash（同源）→ 异构未成立；U-P041-1 跟踪。

---

## 6. Step 7 → Step 8 交接

1. 核红态口径：IMPL §3 `6 failed, 1 passed` 与 B8 逐字一致。
2. 核计数链：771 + 7 = **778**；123 + 1 = **124**；190 + 1 = **191**；86 + 1 = **87**。
3. 核零预填：`[待 Step 9]` = **30** 单元格。
4. 核 ID 不混用：DESIGN 决策 `D1-D4` vs 本文件 **D 组**；引用一律 `DESIGN-D*`。

---

## 7. Step 8 一致性 Review 记录（同基座独立视角，2026-11-17）

> **基座披露（RULE-4）**: 自报 DeepSeek-V4.1-Flash → 同源，RULE-5 不成立；U-P041-1 累计第 4 轮。

### 7.1 机械五项

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 链接校验 | 四文档相对链接存在；四文档互链完整 | ✅ 0 broken |
| 2 | ID 闭环 | A1-A6 / B1-B9 / C1-C7 / D1-D8 连续无跳号；表行 **30** | ✅ |
| 3 | 计数自洽 | 30 = 6 + 9 + 7 + 8 | ✅ |
| 4 | 零预填 | `[待 Step 9]` = **30**（全部单元格）；无 `✅` / `❌` | ✅ |
| 5 | U-P041-1 | RESEARCH §10 / DESIGN §7 / IMPL §6 / 本文件 §5 各 ≥1 处 | ✅ |

### 7.2 对齐矩阵

| # | 项 | 判定 | 证据 |
|---|----|------|------|
| 1 | 红态口径 | ✅ | IMPL §3「6 failed, 1 passed」与 B8 逐字一致 |
| 2 | 前缀元组 | ✅ | DESIGN-D1 / IMPL §2.2 / A2-A3 三处一致 |
| 3 | 版本口径 | ✅ | DESIGN-D2 / IMPL §2.3/§2.4 / A4 / B6 / B9 一致（两行耦合） |
| 4 | 门禁目标 | ✅ | DESIGN §1 / IMPL §4 / 本文件头部一致（778 / 124 / 191 / 22 / 87） |
| 5 | 真实数据判据 | ✅ | DESIGN §4 / D4-D6 一致（全列 unknown=0 / 翻转 2,755 / setup 推进） |

### 7.3 发现与当轮处置（0 P1/P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P041-1 | P3 | B 组标题写「测试（V1-V7）」，但 B 组实有 9 行（B8/B9 为取证项）→ 易被读成 9 个用例 | 标题改为「测试（V1-V7 + 2 取证项）」 |
| F-S8-P041-2 | P3 | D5 的掩码口径（`EPS=0.005`、`open`、`is_st=False`、`st.pkl` 缺失）只在本文件，DESIGN §4 未写 → 复核者按 DESIGN 复现时口径不全 | DESIGN §4 真实数据验收第 3 项补口径 |

### 7.4 结论

**Step 8 Review pass（0 P1/P2 + 2 P3 当轮处置）**——30 项可执行、四文档口径闭环；**准予进入 Step 9 TDD 实施**。
**RULE-5**：第 4 轮同基座 → U-P041-1 pending。

---

## 8. Step 10 ADD 审计记录（2026-11-17）

> **审计基线**: 代码提交 `0196e24`（E3 行号绑此 hash）；审计者自报 DeepSeek-V4.1-Flash（同源）→ RULE-5 不成立；U-P041-1 第 5 轮。

### 8.1 四阶段结论

| 阶段 | 审什么 | 判定 | 关键证据 |
|------|--------|------|---------|
| **Phase 0** | Spec 质量门 | ✅ pass | 四文档模糊词扫描（`合理处理/适当时机/尽量/视情况/酌情`）**0 命中**；D1 前缀元组、D2 版本、D4 七用例均可机械核验 |
| **Phase 1** | 完整性（design → code） | ✅ pass | D1-D4 全落地：两元组 + docstring + 版本行 + 7 用例 + 2 文件订正（E1 `git show` + E3 读码） |
| **Phase 2** | 忠实度（双向） | ✅ pass | 生产面 diff 与 IMPL §2.1-2.3 **逐字一致**；测试文件 96 行与 IMPL §2.5 **逐字一致**（含 F-S9-P041-1 black 单行）；P-040 两行与 IMPL §2.4 一致 |
| **Phase 3** | 必要性（code → design） | ✅ pass | 提交 9 文件中生产面仅 `filter/limit_rules.py` **+4/−4**；无越界；`^[+-]\s*def `=0；无新增 `except`/`raise`/`type: ignore` |
| **Phase 4** | 语义（意图层） | ✅ pass（附 1 项范围外观察） | 5,222,448 次解析 **0 缺口**；边界 `bse 2018-01-15 (1.0,−0.5)` / `gem 2020-08-24 (0.2,−0.2)`；真实数据 302132 `08-21 15.466/12.654`（10%）→ `08-24 17.112/11.408`（20%）、920493 `2021-11-15 54.639/29.421`（30%）；unknown 294→0 |

### 8.2 发现与处置（0 P1 + 0 P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S10-P041-1 | P3 | **E4 盲区扫描**：辅助数据含 2 个非标准标签——`list_date_df.pkl` 索引 `TS0018`、`stock_name.pkl` 列 `T00018`（疑似导出工件；**不在** `close`/`adj`/`return` 三价格矩阵中）。运行期 `DataManager.stock_codes` 取自 `close` → 当前零影响；若未来以 `list_date` 全索引构建股票池，二者各计 1 个 unknown 并回落 main | 登记 **O-P041-5**（观察，不立项） |
| F-S10-P041-2 | P3 | D4「全 5,688 列 unknown=0」的判据范围需写明：`adj` 5,691 列亦 **0**，`list_date` 5,797 → **1**（`TS0018`）、`stock_name` 6,053 → **1**（`T00018`）——即「unknown=0」仅对**价格矩阵**成立 | 本行显式并列四源读数；D4 判据限定为 engine 实际 `close.columns` |

### 8.3 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|---|---|---|
| `pytest tests/test_p041... tests/test_p040... -q`（E1） | B1-B9 | ✅ `13 passed in 0.58s` |
| `git show --stat 0196e24` + 生产面 diff（E1） | A1-A6 / C4 / C6 / D3 / Phase 2-3 | ✅ 9 文件；生产面 `+4/−4` 逐字；`def` 变更 0 |
| 旧版本字面量扫描（E1，`tests/*.py` + `filter/core *.py`） | A4 / B9 | ✅ `"cn_a_2026_11"` 精确命中 **0**（文档历史记载除外） |
| 规格模糊词扫描（E1，四文档） | Phase 0 | ✅ 0 命中 |
| black 双口径 / AST / 测试文件数（E1） | C3 / C5 / D1 | ✅ `124`·`191` / AST **22** / `tests/*.py` **87** |
| CI run `44091229154`（E1） | 全量 pytest 三版本 + lock-check | ✅ 四 job success（lock-check 6s / 3.10 2m5s / 3.11 1m41s / 3.12 1m22s） |
| 全量解析覆盖（E2，对抗性：非 main 全代码 × 有效日 × 两态） | S4/S5 | ✅ 5,222,448 次、**0** 缺口 |
| 边界 + 真实限价抽样（E2，含负例） | S1-S5 | ✅ `2018-01-14`/`2009-10-29` RAISE；10%→20%→30% 分段抽样吻合 |
| 全数据源前缀扫描（E2/E4，扫描范围：`close`/`adj`/`return`/`list_date`/`stock_name` 五源） | 全部 | **发现 2 个非标准标签**（`TS0018`/`T00018`）→ O-P041-5 |
| 静态读码（E3 @`0196e24`） | A2/A3 / D3 | ✅ L19 `cn_a_2026_11b`、L85/L89 两元组 |
| E5 推测 | — | 无（未覆盖项：无） |

### 8.4 结论

**Step 10 ADD 审计 pass**——Phase 0-4 全过；**P1 = 0 / P2 = 0**；P3 = 2（1 项登记 O-P041-5、1 项口径并列）。U-P040-2 修复的设计落地经 E1/E2/E3 三重取证确认；**批次仍 in-progress，待 U-P041-1 异构终审**。
