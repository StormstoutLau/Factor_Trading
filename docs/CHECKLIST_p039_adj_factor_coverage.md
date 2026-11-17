# CHECKLIST：P-039 adj_factor 日期覆盖缺陷修复

> **批次**: P-039 · **T1**（Layer-1：`core/data.py` + `tests/`）
> **上游**: [IMPL_p039](IMPL_p039_adj_factor_coverage.md)（§3 精确规格 / §4 红态实测 / §8 Step 6 复审 pass：1 P2 + 2 P3）；[DESIGN_p039](DESIGN_p039_adj_factor_coverage.md)（D1-D4 / I1-I6 / V1-V6 / §8 Step 4 复审 pass：1 P2 + 2 P3）；[RESEARCH_p039](RESEARCH_p039_adj_factor_coverage.md)（§6 M-A / §12 / §13）
> **状态**: **Step 9 完成（24/25），待提交回填 D4**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；禁止与正文同一次写入时打勾
> **基线读数（@`377b26a`，Step 7 实测）**: pytest **760 passed** / golden **13 passed, 747 deselected** / black `core tests` **121**（全仓 `.` **188**）/ mypy 12 面 `Success ... 103 source files` / AST `except Exception` **22** / `tests/*.py` **84** / `uv lock --check` exit **0**
> **目标读数**: pytest **765** / golden 13 零重录 / black `core tests` **122**（全仓 **189**）/ mypy 12 面 **0** / AST **22** / `uv lock` exit 0
> **代码证据时点**: HEAD `377b26a`

---

## 1. A 组：代码修复 B1（IMPL §3.1）

> **DoR**: 1 处分支改（**+12/−1**，F-S9-P039-1）；三段式顺序固定；无新增 `except` / `# type: ignore`。**DoD**: 真实数据 adj 缺日加载成功；`close/open/high/low` 分支逐字不变。

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| A1 | `_load_price_data` 新增 `if price_type == "adj_factor":` 分支，内容与 IMPL §3.1 **逐字一致**（`window` / `n_missing` / 三段式 / 条件 logger） | 读码 + `git diff` | ✅ 落码 L302-313，逐行比对一致（`git diff --numstat` = `12 1`） |
| A2 | 三段式顺序 = `reindex(data.index.union(window))` → `ffill()` → `reindex(window)`（不可简化） | 读码逐字 | ✅ L310 单行链式，顺序逐字 |
| A3 | `logger.info` 仅在 `n_missing > 0` 输出，文案含实际日数 | 读码 + V6b 日志 | ✅ L311-312 `if n_missing:` 守卫 + f-string `{n_missing} 日`；V6b stderr 不可见（脚本未 `basicConfig`）→ 出口改探针（F-S9-P039-2） |
| A4 | `else: data = data.loc[self._trade_dates]` 保留，四 kind 路径逐字不变 | `git diff -U3` | ✅ L312-313 原 `.loc` 语句移入 `else`，语义逐字；`close/open/high/low` 走同一 `else` |
| A5 | L304-315（列裁剪 / 缓存 / `_prices`）逐字不动 | `git diff` | ✅ 实测 L315 起（`# 确保列顺序一致`）无任何 diff 行 |
| A6 | 新增 `except` = 0；新增 `# type: ignore` = 0 | `-CaseSensitive` 正则 + Grep | ✅ `git diff -U0 core/data.py` 过滤 `^\+.*except` / `^\+.*# type: ignore` / `^\+.*raise ` 均 **0** |

## 2. B 组：测试 B2（IMPL §3.2，V1-V5）

> **DoR**: 1 新文件 5 用例；`from _synth_fixture import ...`（F-S6-P039-1）。**DoD**: 红态 `2 failed / 3 passed` → 绿 `5 passed`。

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| B1 | V1 缺日补齐：drop 1 日 → 值 = 前值（1.1），无缺日值不变（1.3） | 用例 | ✅ PASS（`5 passed` 全绿，V1 两断言均命中） |
| B2 | V2 无缺日等价：与 `read_pickle`（按 `dm.stock_codes` 对齐）`assert_frame_equal` | 用例 | ✅ PASS（无缺日路径与原始 pkl 逐值相等） |
| B3 | V3 窗口首日缺口：`start_date` 截断 + drop 首日 → 取窗口外前值 1.1 | 用例 | ✅ PASS（三段式唯一性成立；两段式在此用例为 NaN） |
| B4 | V4 不 bfill：首日置 NaN → 仍 NaN；次日 = 1.1 | 用例 | ✅ PASS（无前值期保持 NaN） |
| B5 | V5 修复范围：drop `open` 一日 → `pytest.raises(KeyError, match="not in index")` | 用例 | ✅ PASS（`open` 仍严格索引） |
| B6 | 红态留证 `2 failed, 3 passed`（V1/V3 FAIL）→ 绿 `5 passed` | pytest 输出逐字 | ✅ 红态 Step 6 预跑 `2 failed, 3 passed in 1.01s`（IMPL §4）；绿态 Step 9 `5 passed in 0.57s` |

## 3. C 组：不变式 I1-I6（DESIGN §3）

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| C1 | **I1** golden **13 零重录**；`tests/golden/` 无改动 | `pytest -k golden` + `git status --short tests/golden/` | ✅ `13 passed, 752 deselected`；`git status` 空 |
| C2 | **I2** pytest **765**（760 + 5）；既有 760 零失败 | 全量 `pytest -q` 末行 | ✅ `765 passed, 172 warnings in 42.05s` |
| C3 | **I3** mypy 12 面 **0**；新增 ignore 0 | 门禁命令 + Grep | ✅ `Success: no issues found in 103 source files`；新增 ignore **0** |
| C4 | **I4** 公开签名零变更（`_load_price_data` 私有；`DataManager` 公开方法未动） | `git diff` 逐行 | ✅ diff 中 `^[+-]\s*def ` = **0** |
| C5 | **I5** AST `except Exception` 恒 **22**；`^\+.*except` = 0（`-CaseSensitive`） | AST 命令 + 正则 | ✅ AST **22**（P-029 十文件口径）；`^\+.*except` **0** |
| C6 | **I6** `close/open/high/low` 四分支零改动（V5 用例 + diff） | 用例 + `git diff` | ✅ V5 PASS；diff 仅 1 处新增分支，四 kind 无改动行 |

## 4. D 组：门禁、边界与文档

> **DoR**: 门禁双载体零改动；单提交原子。**DoD**: 四 job 全绿；文档回填；V6b 日志留证。

| ID | 验收项 | 证据出口 | 实测 |
|----|--------|---------|------|
| D1 | black `core tests` **122**（+1 新测试文件）/ 全仓 **189** | `black --check` 两口径 | ✅ `122 files would be left unchanged` / `189 files would be left unchanged` |
| D2 | `uv lock --check` exit **0**；`pyproject.toml` / `uv.lock` 零改动 | 命令 + `git diff` | ✅ exit **0**（`Resolved 148 packages`）；两文件 `git diff` 空 |
| D3 | 门禁双载体（`tests.yml` L46 / adapter L67）零改动 | `git diff --numstat` | ✅ `tests.yml` / `spec_runner_adapter.py` diff 均空 |
| D4 | 单提交原子（`core/data.py` + 新测试）；CI 四 job 全绿 | `git show --stat` + `gh run view` | [待 Step 9] |
| D5 | **V6b 真实数据证据**（F-S9-P039-3 改写）：修复生效 = `adj.shape=(1460, 5688)` / 全 NaN 行 **0** / 「adj 缺且 close 有值」**0**；「加载adj_factor数据失败」消失，链路推进至 `LimitRuleError(board=bse, 2020-01-23)`（新 P1 = U-P039-4，不属本批） | `DataManager` 直接探针（INFO 日志不可见，F-S9-P039-2）+ 早期 `run_single_backtest.py` stderr 摘录 | ✅ 探针四项读数全中；`LimitRuleError` 原文见 IMPL §9.3 |
| D6 | 文档回填：IMPL §9 / PROGRESS §3.44.1 + §1.4 / CHANGELOG / U-P038-2 → done | 读回 | ✅ IMPL §9 九项读数 + PROGRESS §3.44.1 + CHANGELOG Fixed 条目；U-P038-2 → done |
| D7 | 未决登记：U-P039-1（上游缺日）/ U-P039-2（列维度）/ U-P039-3（异构终审）/ **U-P039-4（bse 规则缺口，P1）** / O-P039-1/-2 | 读回 §1.4 | ✅ 六项均已建行（U-P039-4 为 Step 9 新增） |

---

## 5. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **25**（A 6 + B 6 + C 6 + D 7 = 25，机械计数） |
| 实测列回填 | **24/25**（仅 D4 待提交回填；其余 24 项均 `✅ + 证据`） |

> **RULE-2 统计溯源**：25 = 6 + 6 + 6 + 7（逐表行数，非估计）。
> **RULE-5 声明**：Step 2/4/6 复审均自报 DeepSeek-V4.1-Flash（与作者同源）→ **异构三轮未成立**；U-P039-3 跟踪。

---

## 6. Step 7 → Step 8 交接

1. 核四文档口径：红态 `2 failed / 3 passed`（IMPL §4 / 本文件 B6 一致）；25 项计数自洽。
2. 核 ID 不混用：DESIGN 决策 `D1-D4` vs 本文件 **D 组**（门禁文档）——引用一律 `DESIGN-D*`。
3. 核 black 口径：基线 121/188 → 目标 **122/189**（新增 1 测试文件）。
4. 核零预填：`[待 Step 9]` 计数 = 25 单元格。

---

## 7. Step 8 一致性 Review 记录（同基座独立上下文，2026-11-17）

> **基座披露**：复审会话 system prompt 逐字自报 `You are powered by the model named DeepSeek-V4.1-Flash.` → **同源，RULE-5 不成立**（RULE-4 披露）；U-P039-3 累计第 4 轮异构未证实。

### 7.1 机械五项

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 链接校验 | 四文档相对链接全部存在；`file:///` 为绝对锚点不参与相对校验 | ✅ 0 broken |
| 2 | ID 闭环 | 表行 **25**；A1-A6 / B1-B6 / C1-C6 / D1-D7 连续无跳号 | ✅ |
| 3 | 计数自洽 | 25 = 6 + 6 + 6 + 7 ✅ | ✅ |
| 4 | 零预填 | `[待 Step 9]` = **25**（全部单元格）；无 `✅` / `❌` 预填 | ✅ |
| 5 | U-P039-3 | RESEARCH / DESIGN / IMPL / 本文件 各 ≥1 处 | ✅ |

### 7.2 对齐矩阵五项

| # | 项 | 判定 | 证据 |
|---|----|------|------|
| 1 | 红态口径 | ✅ | IMPL §4「2 failed / 3 passed」与 B6 逐字一致 |
| 2 | 三段式 | ✅ | DESIGN-D1 / IMPL §3.1 / 本文件 A2 三处一致 |
| 3 | 五用例 | ✅ | DESIGN-D4 / IMPL §3.2 / B1-B5 一一对应 |
| 4 | 门禁目标 | ✅ | DESIGN-I1-I6 / 本文件 C1-C6 + D1-D2 一致（765 / 122 / 189 / 22） |
| 5 | 边界声明 | ✅ | V6b 的 U-P038-1 豁免在 DESIGN §4 / 本文件 D5 两处一致 |

### 7.3 发现与当轮处置（0 P1/P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P039-1 | P3 | 本文件 §7 交接项 4 写「`[待 Step 9]` 计数 = 25 单元格」，但未含规则行（与 P-037 口径不同：P-037 把规则行计入 42） | 保持「仅单元格」口径并显式声明（规则行不计入，避免双重计数） |
| F-S8-P039-2 | P3 | `tests/*.py` 基线 84 未在目标中更新（新增 1 文件 → 85） | 目标读数补 `tests/*.py` **85**（D 组外，登记于 §7.3） |

### 7.4 结论

**复审结论**：**pass（0 P1/P2 + 2 P3 当轮处置）**——25 项可执行、四文档口径闭环，**准予进入 Step 9 TDD 实施**。
**RULE-5**：第 4 轮同基座 → U-P039-3 维持 pending。
