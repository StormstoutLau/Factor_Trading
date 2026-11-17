# CHECKLIST：P-039 adj_factor 日期覆盖缺陷修复

> **批次**: P-039 · **T1**（Layer-1：`core/data.py` + `tests/`）
> **上游**: [IMPL_p039](IMPL_p039_adj_factor_coverage.md)（§3 精确规格 / §4 红态实测 / §8 Step 6 复审 pass：1 P2 + 2 P3）；[DESIGN_p039](DESIGN_p039_adj_factor_coverage.md)（D1-D4 / I1-I6 / V1-V6 / §8 Step 4 复审 pass：1 P2 + 2 P3）；[RESEARCH_p039](RESEARCH_p039_adj_factor_coverage.md)（§6 M-A / §12 / §13）
> **状态**: **Step 1-10 完成（25/25）+ U-P039-3 异构终审 pass（GLM-5.3-Flash），批次关闭**
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`；禁止与正文同一次写入时打勾
> **基线读数（@`377b26a`，Step 7 实测）**: pytest **760 passed** / golden **13 passed, 747 deselected** / black `core tests` **121**（全仓 `.` **188**）/ mypy 12 面 `Success ... 103 source files` / AST `except Exception` **22** / `tests/*.py` **84** / `uv lock --check` exit **0**
> **目标读数**: pytest **765** / golden 13 零重录 / black `core tests` **122**（全仓 **189**）/ mypy 12 面 **0** / AST **22** / `tests/*.py` **85** / `uv lock` exit 0
> **代码证据时点**: HEAD `377b26a`（Step 1-8 基线）；Step 9 实测时点 = 提交 `7d96547`

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
| D4 | 单提交原子（`core/data.py` + 新测试）；CI 四 job 全绿 | `git show --stat` + `gh run view` | ✅ 提交 `7d96547`（8 文件 **+802/−4**）；CI run [`44061765966`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/44061765966) **success**（`lock-check` 8s + 3.10 1m43s + 3.11 1m59s + 3.12 1m30s） |
| D5 | **V6b 真实数据证据**（F-S9-P039-3 改写）：修复生效 = `adj.shape=(1460, 5688)` / 全 NaN 行 **0** / 「adj 缺且 close 有值」**0**；「加载adj_factor数据失败」消失，链路推进至 `LimitRuleError(board=bse, 2020-01-23)`（新 P1 = U-P039-4，不属本批） | `DataManager` 直接探针（INFO 日志不可见，F-S9-P039-2）+ 早期 `run_single_backtest.py` stderr 摘录 | ✅ 探针四项读数全中；`LimitRuleError` 原文见 IMPL §9.3 |
| D6 | 文档回填：IMPL §9 / PROGRESS §3.44.1 + §1.4 / CHANGELOG / U-P038-2 → done | 读回 | ✅ IMPL §9 九项读数 + PROGRESS §3.44.1 + CHANGELOG Fixed 条目；U-P038-2 → done |
| D7 | 未决登记：U-P039-1（上游缺日）/ U-P039-2（列维度）/ U-P039-3（异构终审）/ **U-P039-4（bse 规则缺口，P1）** / O-P039-1/-2 | 读回 §1.4 | ✅ 六项均已建行（U-P039-4 为 Step 9 新增） |

---

## 5. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **25**（A 6 + B 6 + C 6 + D 7 = 25，机械计数） |
| 实测列回填 | **25/25**（A 6 / B 6 / C 6 / D 7 全 `✅ + 证据`） |

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

---

## 8. Step 10 ADD 审计（同基座独立视角，2026-11-17）

> **审计基线**: `377b26a..cbb7d0b`（2 提交 / 8 文件 **+803/−4**；代码面 = `7d96547`，`cbb7d0b` 为 docs-only 回填）。
> **基座披露（RULE-4）**: 作者与审计均为 DeepSeek-V4.1-Flash → **同基座，RULE-5 不成立**；U-P039-3 维持 pending。
> **审计方式**: 不复用 Step 9 自报，独立读回 diff / 测试全文 + 门禁复跑（pytest 765 / golden 13·752 / mypy 103 files 0 / black 122·189 / AST 22 / uv exit 0）。

### 8.1 Phase 0：spec 质量门

| # | 项 | 读数 | 判定 |
|---|----|------|------|
| 1 | 四文档齐全且链接可解析 | RESEARCH / DESIGN / IMPL / CHECKLIST 均在库，相对链接 0 broken | ✅ |
| 2 | 决策可机械核验 | D1 分支位置 / D2 计数口径 / D3 五项不扩做 / D4 五用例 | ✅ 4/4 |
| 3 | 不变式可判定 | I1 golden 零重录 / I2 765 / I3 mypy 0 / I4 签名 / I5 AST 22 / I6 四 kind 不改 | ✅ 6/6 |
| 4 | 验收项预填合规 | 25 项首轮零预填 → Step 9 回填 25/25（分两次写入） | ✅ |
| 5 | 复审留痕 | Step 2/4/6/8 各有独立记录与 P 级处置 | ✅ 4/4 |

### 8.2 Phase 1：完整性

| 项 | 声称 | 实测 | 判定 |
|----|------|------|------|
| 代码变更面 | 1 文件 1 处 | `core/data.py` +12/−1（`git diff --numstat`）；无其他 `.py` | ✅ |
| 测试变更面 | 1 新文件 5 用例 | 104 行 / 5 个 `def test_` | ✅ |
| 文档变更面 | 四文档 + PROGRESS + CHANGELOG | 8 文件 +803/−4 全归属 | ✅ |
| 零改动面 | `filter/**` / 夹具 / 门禁双载体 / `pyproject` / `uv.lock` / `agents/**` | diff 全空 | ✅ |

### 8.3 Phase 2：保真度（逐行读码）

| # | 核验点 | 实测 | 判定 |
|---|--------|------|------|
| 1 | 分支内容 = IMPL §3.1 | 逐行一致（4 注释 + 8 代码） | ✅ |
| 2 | 三段式顺序 | `reindex(union) → ffill() → reindex(window)` 单行链式 | ✅ |
| 3 | 计数口径 | `len(window.difference(data.index))`（日期差集，非 NaN 行数） | ✅ |
| 4 | logger 条件 | `if n_missing:` + f-string 原子 | ✅ |
| 5 | 四 kind 回退 | `else: data = data.loc[self._trade_dates]` 逐字 | ✅ |
| 6 | 缓存/列裁剪 | L315 起无 diff | ✅ |

### 8.4 Phase 3：必要性（零游离）

`git diff` 的 12 行新增全部可归属于 DESIGN-D1/D2 的三项（三段式 / 计数 / 日志）；无顺带重构、无格式噪声、无新增 `except` / `raise` / `# type: ignore`。✅

### 8.5 Phase 4：语义达成

- **目标语义**：`adj_factor` 缺日 → 前值补齐；未上市/退市期保持 NaN；其余 kind 行为不变。**V1-V5 全绿** + 真实数据「adj 缺且 close 有值」**403,853 → 0**。
- **是否换成另一种静默**：否——`n_missing > 0` 时 INFO 计数；无 try/except 包裹（fail-fast 保留）；V5 证明其他 kind 未被波及。
- **口径映射（审计补记）**：RESEARCH §2 的「81 日」= adj（1394 行）对 close **全量**（1475 行）；窗口口径（1460 日，起点 2020-01-23）为 **80 日**（差 1 日 = **2020-01-10** 落在窗口起点前；~~2020-01-02~~ 初稿误归因——其乃 raw adj 首行并不缺失，F-U3-P039-2 订正）。✅

### 8.6 E1-E5 取证矩阵

| 级 | 项 | 读数 |
|----|----|------|
| E1 | 可重放命令 | `pytest tests -q` → `765 passed`；`pytest -k golden` → `13 passed, 752 deselected`；`mypy <12 面>` → `103 source files` 0；`black --check core tests` → 122；`black --check .` → 189；P-029 AST 命令 → 22；`uv lock --check` → exit 0 |
| E2 | 运行时探针 | 真实数据 `DataManager` 探针：`adj (1460, 5688)` / 全 NaN 行 0 / 交叉 NaN 0 / `cols_equal=True`；`engine.setup()` 推进至 `LimitRuleError(board=bse, 2020-01-23)` |
| E3 | 静态读码 | `core/data.py:302-313`（@`7d96547`）与 IMPL §3.1 逐字；测试 5 用例断言与 DESIGN §D4 一一对应 |
| E4 | 盲区扫描 | 新测试无死参数（`drop_adj`/`drop_open`/`adj_na` 均被使用）；无弱断言（V2 `assert_frame_equal`、V5 `raises(match=...)`）；无新增静默路径 |
| E5 | 推测（禁入结论） | 无——全部结论均有 E1-E4 支撑 |

### 8.7 发现与分级（0 P1/P2 + 2 P3 当轮处置）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S10-P039-1 | P3 | IMPL §1「门禁口径」仍写 black **121**（新增 1 测试文件后应为 **122** / 全仓 189） | 当轮改为 **122（全仓 189）** |
| F-S10-P039-2 | P3 | F-S8-P039-2 的处置称「目标读数补 `tests/*.py` **85**」，但 CHECKLIST 头部目标读数未落实（仅 IMPL §5 有） | 头部目标读数补 `tests/*.py` **85** |

**观察（不立项）**：
- O-S10-P039-1：V3 未复用 `_prepare`（需自定义 `start_date`），存在 8 行夹具构造重复——DESIGN-D4 已声明，测试可读性优先。
- O-S10-P039-2：真实数据 INFO 日志（`adj_factor 日期补齐`）在本机不可观测（脚本未配置 logging）——已由探针替代（F-S9-P039-2），不改脚本（属 U-P038-1 范围）。

### 8.8 结论

**Step 10 ADD 审计 pass（0 P1/P2 + 2 P3 当轮处置 + 2 观察）**——diff 零游离、四文档口径闭环、E1-E5 全有实证；批次可关闭（U-P038-2 → done，U-P039-4 独立跟踪）。
**残留**：U-P039-3 异构终审（需用户启动异构基座会话承接）。

---

## 9. U-P039-3 RULE-5 异构终审（2026-11-17）

> **基座披露（RULE-4）**: 终审会话 system prompt 逐字自报 `You are powered by the model named GLM-5.3-Flash.` ≠ 四文档/实施/审计作者 DeepSeek-V4.1-Flash → **异构条件成立**（P-039 五轮复审中首次）。
> **终审方式**: 不复用作者自报，独立编写探针与命令；终审基线 = `377b26a..d1cf545`（代码面 = `7d96547`，`cbb7d0b`/`d1cf545` docs-only）。

### 9.1 E1-E5 五项

| 级 | 项 | 独立复跑读数 | 判定 |
|----|----|--------------|------|
| E1 | 七项门禁 | pytest **765 passed**（88.18s）/ golden **13 passed, 752 deselected** / mypy 12 面 `Success: no issues found in 103 source files` / black `core tests` **122**、全仓 **189** / AST `except Exception` **22**（P-029 原命令）/ `tests/*.py` **85** / `uv lock --check` exit **0** | ✅ |
| E2 | 真实数据探针（终审独立编写） | ① 修复面：`adj.shape=(1460, 5688)`、`cols_equal=True`、全 NaN 行 **0**、交叉 NaN **0**；② **81/80 口径精确核算**：全量 close 1475 / adj 1394 → 缺 **81**（逐年 2020:9 / 2021:8 / 2022:10 / 2023:16 / 2024:31 / 2025:7，与 RESEARCH §2 **逐字一致**）；窗口起点（2020-01-23）前缺 **1 日（2020-01-10）** → 窗口缺 **80**（§8.5 口径补记实证）；③ U-P039-4 根因定向：bse 前缀 **3** 只、`infer_board('832317')='bse'`、close 2020-01-23 有值 3/3、`resolve_limit("bse", False, 2020-01-23)` 抛 `LimitRuleError`（文案逐字）；④ `engine.setup()`（`data_dir=Path`）复现 `LimitRuleError(board=bse, is_st=False, date=2020-01-23)`（非 FileNotFoundError，IMPL §9.3 崩点证实）；⑤ INFO 压制证实（`core.data` effective level=30） | ✅ |
| E3 | 静态读码 @`7d96547` | `git show 7d96547 -- core/data.py` 与 IMPL §3.1 **逐字一致**（4 注释 + 8 代码）；HEAD 实码 L302-313、列裁剪 L315 起、缓存段零 diff；`git diff 377b26a..HEAD` 零改动面（`tests/golden/` / 门禁双载体 / `tests/_synth_fixture.py` / `pyproject.toml` / `uv.lock` / `filter/` / `agents/`）**全空**；numstat `12 1` | ✅ |
| E4 | 盲区扫描 | CHECKLIST 25 行全 `✅`（余 4 处 `[待 Step 9]` 均为规则/复审记录字面引用，非未回填单元格）；台账 U-P039-1/-2/-3/-4 + O-P039-1/-2 六行齐备；新测试无死参数（`drop_adj`/`drop_open`/`adj_na` 全部被用例消费）、无弱断言（`approx` / `assert_frame_equal` / `raises(match=)`）；零新增静默路径（AST 恒 22）；四文档无 TODO/占位残留 | ✅ |
| E5 | 推测禁入 | 无——全部结论均有 E1-E4 支撑 | ✅ |

### 9.2 终审期发现与处置（0 P1/P2 + 2 P3 当轮处置）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-U3-P039-1 | P3 | 头部状态行停留在「Step 9 完成（25/25）」，未反映 Step 10 审计与本终审结论 | 当轮更新为「Step 1-10 完成（25/25）+ U-P039-3 异构终审 pass，批次关闭」 |
| F-U3-P039-2 | P3 | §8.5 与 PROGRESS §3.44.2 的口径补记把「窗口差 1 日」误归因为「2020-01-02 在窗口外」——探针实证 2020-01-02 **在** raw adj 中（首行，不缺失）；真正的窗口前缺失日 = **2020-01-10**（全量 81 日中唯一落在 2020-01-23 之前者） | 当轮订正两处（计数 80 不变，归因日改 2020-01-10） |
| （披露） | — | 终审探针两处**自纠**（非仓库缺陷）：① `data_dir` 传 str 违反 [config.py:341](../core/config.py) 的 `Path` 注解 → suspend 告警消息构造 `TypeError`（改用 `Path` 后复现预期 `LimitRuleError`）；② 「全量缺失」首算误用窗口化 close（1460）得 66 → 改读全量 `stock_close.pkl`（1475）重算得 81 | 记录备查（RULE-4 诚实披露） |

### 9.3 结论

**U-P039-3 异构终审 pass**——E1-E5 五项全过 + 0 P1/P2 + 2 P3 当轮处置（F-U3-P039-1/-2）。
**P-039 批次关闭**：U-P038-2 → done；U-P039-1 / U-P039-2 pending（条件触发）、**U-P039-4（P1）独立跟踪**待立项；O-P039-1/-2 观察归档。
