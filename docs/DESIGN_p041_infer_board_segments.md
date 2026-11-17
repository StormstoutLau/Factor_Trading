# DESIGN：P-041 infer_board 号段表补齐（U-P040-2）

> **批次**: P-041 · **Step 3 设计** · 日期 2026-11-17
> **判档**: **T1**（Layer-1：`tests/`；生产面 `filter/limit_rules.py` 行为变更）
> **上游**: [RESEARCH_p041](RESEARCH_p041_infer_board_segments.md)（§3 数据实况 / §4 号段归属 / §7 M-A 裁决 / §8 S1-S7 / §14 Step 2 复审 pass：1 P2 + 4 P3）
> **代码证据时点**: HEAD `24688ab`

---

## 1. 范围

| 项 | 内容 |
|----|------|
| 变更文件（代码 1） | `filter/limit_rules.py`：`infer_board` 前缀表（gem 增 `302`、bse 增 `920`）+ 模块 docstring + `RULESET_VERSION` |
| 变更文件（测试 1 新建） | `tests/test_p041_board_segments.py`（**新建**，7 用例） |
| 变更文件（测试 1 订正） | [tests/test_p040_bse_limit_rule_gap.py:40-41](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p040_bse_limit_rule_gap.py#L40-L41)：版本字面量 `cn_a_2026_11` → `cn_a_2026_11b`（**两行**：docstring + 断言；D2 的必然耦合；F-S6-P041-1 订正） |
| 变更文件（文档） | 本文件 / `docs/IMPL_p041_*` / `docs/CHECKLIST_p041_*` / `docs/PROGRESS.md` / `CHANGELOG.md` |
| 零改动面 | `RULES` 13 条 / `resolve_limit` / `build_limit_prices` / `universe_filter_clean.py` / `core/**` / `tests/_synth_fixture.py` / `tests/golden/**` / `tests/test_limit_rules.py` / `pyproject.toml` / `uv.lock` / 门禁双载体 |
| 门禁口径 | pytest **771 → 778** / golden **13 零重录** / mypy 12 面 **0**（103 files）/ black **123 → 124**（全仓 **190 → 191**）/ AST `except Exception` 恒 **22** / `tests/*.py` **86 → 87** / `uv lock` exit 0 |

---

## 2. 设计决策

### D1 前缀表变更（唯一生产逻辑改动点）

[limit_rules.py:81-98](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L81-L98)：

```python
    if prefix.startswith(("300", "301", "302")):
        return "gem"
    if prefix.startswith(("688", "689")):
        return "star"
    if prefix.startswith(("8", "4", "920")):
        return "bse"
```

- `_MAIN_PREFIXES`（L22）零改动；顺序零改动（`302` 不在 main 前缀内、`920` 不与 `8`/`4` 冲突）。
- 模块 docstring L5 同步：「300/301/302→gem；688/689→star；8/4/920 开头→bse；其余→main」。
- **不改** `RULES`（13 条）、`resolve_limit`、`build_limit_prices`。

### D2 版本口径：`cn_a_2026_11` → `cn_a_2026_11b`（bump）

| 项 | 裁决 |
|----|------|
| 是否 bump | **bump**。映射变更使 **2,755** 单元格的生效规则改变 → 同一 `ruleset_version` 会掩盖结果差异（caliber 漂移） |
| 命名 | `cn_a_2026_11b`；**约定**：同月二次修订追加小写字母后缀（首次同月修订为 `b`），避免与跨月版本混淆（本约定首次确立，见 F-S4-P041-3） |
| 必然后果 | [P-040 V3 断言](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p040_bse_limit_rule_gap.py#L41) 一行同步修改；`caliber.ruleset_version` 报告值变化 |
| 备选（拒绝） | ① 不 bump：零耦合，但两种结果同版本号；② 用 `cn_a_2026_12`：以未来月份命名会造成时间错位 |

### D3 精确语义（与 RESEARCH §8 一致）

| # | 语义 |
|---|------|
| S1 | `302` → `gem`；`300/301` 零变更 |
| S2 | `920` → `bse`；`8`/`4` 零变更 |
| S3 | 其余前缀、未知前缀 warning、`unknown_board_count()` 计数语义零变更（`700001` 仍 `main` + 计数） |
| S4 | `920` 在数据窗口（`2020-01-02` 起）全部日期 × 两态可解析（bse 规则自 `2018-01-15`） |
| S5 | `302` 在 `2020-01-02` 起可解析；`2020-08-24` 前后分别为 10% / 20%（gem 既有分段） |
| S6 | `RULES` 13 条零改动 |
| S7 | `RULESET_VERSION` = `cn_a_2026_11b`（D2） |

### D4 测试策略（7 用例，纯函数级，无夹具）

| ID | 用例 | 断言 |
|----|------|------|
| V1 | `920` 号段映射 | `infer_board("920000"/"920493"/"920931") == "bse"` |
| V2 | `302` 号段映射 | `infer_board("302132") == "gem"` |
| V3 | 既有前缀非回归矩阵 | `300/301→gem`、`688/689→star`、`8/4→bse`、`000/001/002/003/600/601/603/605→main`、`700001→main` |
| V4 | `920` 跨制度期价格 | 5 日迷你帧（`2020-07-22..07-28`，flat 10，adj=1）：`07-23/07-24` → `20/5`；`07-27/07-28` → `13/7` |
| V5 | `302` 跨注册制边界 | 3 日迷你帧（`2020-08-20/21/24`，flat 10）：`08-21` → `11/9`；`08-24` → `12/8` |
| V6 | 版本 + 未识别计数 | `RULESET_VERSION == "cn_a_2026_11b"`；调用 `infer_board("920493")` / `("302132")` 后 `unknown_board_count()` 不变 |
| V7 | 带后缀代码 | `infer_board("920493.BJ") == "bse"`、`infer_board("302132.SZ") == "gem"`（`split(".")` 契约） |

**红态预期**（修复前）：V1/V2/V4/V5/V6/V7 **FAIL**（`920`/`302` 均返回 `main`；V6 版本断言失败）；V3 **PASS**（非回归保护）。合计 **`6 failed, 1 passed`**。

---

## 3. 不变式

| ID | 不变式 | 判据 |
|----|--------|------|
| I1 | golden **13 零重录**（无 `920`/`302` 代码） | `pytest -k golden` + `git status --short tests/golden/` |
| I2 | pytest **771 → 778**（+7） | 全量末行 |
| I3 | mypy 12 面 **0**；新增 `# type: ignore` **0** | CI 逐字命令 |
| I4 | 公开签名零变更（`infer_board` / `resolve_limit` / `build_limit_prices` / `RULES` 类型） | `git diff` 中 `^[+-]\s*def ` = 0 |
| I5 | AST `except Exception` 恒 **22**；新增 `except` / `raise` **0** | P-029 十文件命令 + `git diff -U0` |
| I6 | `RULES` 13 条逐字不动 | `git diff` 仅 docstring / 前缀元组 / 版本行 |
| I7 | 既有测试仅 P-040 V3 一行字面量订正；`test_limit_rules.py` 7 用例零改动 | `git diff --stat tests/` |

---

## 4. 边界与回退

- **回退点**：单提交 revert → 回到 294 只回落 `main`、版本 `cn_a_2026_11`；无跨批依赖。
- **失败模式**：若映射后出现 `LimitRuleError`（理论上不会：bse 自 2018-01-15、gem 自 2009-10-30，数据自 2020-01-02）→ 以真实数据探针为准回填并升级处置。
- **真实数据验收（D4）**：
  1. `infer_board` 对 `920000`/`302132` 的返回值；
  2. **全 5,688 列遍历后** `unknown_board_count() == 0`（C3 完整判据）；
  3. 掩码翻转复算 **2,755**（920：2,752；302132：3；口径：`EPS=0.005`、`open`、`is_st=False`，`st.pkl` 缺失）；
  4. `len(RULES) == 13`；
  5. `engine.setup()` 仍推进到 U-P038-1 `FileNotFoundError`（不因映射变更崩溃）。
  不作为 CI 测试（依赖 `E:\Ashare_data`）。

---

## 5. 已知局限（承接 RESEARCH §10）

O-P041-1（逐股制度期近似）/ O-P041-2（302 当前仅 1 只）/ O-P041-3（新号段无机械发现机制）/ O-P041-4（旧段与新段并存）。

---

## 6. Step 3 自查

| # | 项 | 结论 |
|---|----|------|
| 1 | 决策可机械核验 | ✅ D1 前缀元组逐字；D4 七用例一一对应；D2 一行耦合点已列链接 |
| 2 | 失败注入可观测 | ✅ V1/V2/V4/V5/V6/V7 红态均为「归 main」或版本断言失败 |
| 3 | 低效排除 | ✅ 无新增循环/I/O；`board_columns` 分组数不变（4 组），组内代码数增加 |
| 4 | 零依赖新增 | ✅ 仅字符串常量 |
| 5 | 测试破坏面 | ✅ 仅 P-040 V3 一行（D2 必然耦合）；`test_limit_rules` 不受影响 |
| 6 | 版本口径 | ✅ D2 显式裁决 + 命名约定 + 备选拒绝理由 |

---

## 7. Step 4 设计 Review 记录（同基座独立视角，2026-11-17）

> **基座披露（RULE-4）**: 自报 DeepSeek-V4.1-Flash → 同源，RULE-5 不成立；U-P041-1 累计第 2 轮。

### 7.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | D1 与 RESEARCH §8 S1/S2 一致 | 元组 `("300","301","302")` / `("8","4","920")` | ✅ |
| A | `_MAIN_PREFIXES` 无交集 | `302`/`920` 均不在 L22 元组 | ✅ |
| B | V4 数值可解析 | flat 10、adj=1：ref 恒 10 → 07-24 `20/5`、07-27 `13/7` | ✅ |
| B | V5 数值可解析 | 08-21 ref=10 → `11/9`；08-24 ref=10 → `12/8` | ✅ |
| C | I2 计数 | 771 + 7 = **778** | ✅ |
| C | black 计数 | 123 + 1 = **124**；190 + 1 = **191**；`tests/*.py` 86 + 1 = **87** | ✅ |
| D | 版本耦合面 | `RULESET_VERSION` 精确断言仅 P-040 V3 一处；实际涉及**两行**（docstring + 断言，F-S6-P041-1 订正） | ✅ |
| E | 既有测试破坏面 | `test_limit_rules.py` 与 P-040 其余 5 用例不涉 `920/302` | ✅ |

### 7.2 发现与当轮处置（1 P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S4-P041-1** | **P2** | §4 D4 初稿仅验「`infer_board("920000")`/`("302132")` 返回值」，未覆盖 C3 的完整判据「全 5,688 列遍历后 `unknown=0`」——单点断言无法证明 294 只全部消除 | D4 增加第 2 项全列遍历判据 + 第 4 项 `len(RULES)==13` |
| F-S4-P041-2 | P3 | V6 合并「版本」与「未识别计数」两项断言，失败定位不直观 | 保留合并（避免第 8 用例），docstring 写明双重目的（沿用 P-040 F-S6-P040-2 先例） |
| F-S4-P041-3 | P3 | 版本后缀 `b` 无先例，未声明命名规则 | D2 补「同月二次修订追加小写字母后缀」约定 |

### 7.3 结论

**Step 4 Review pass（1 P2 + 2 P3 当轮回写）**——设计可机械核验、红态可观测、计数自洽、版本耦合面封闭；**准予进入 Step 5 IMPL**。
**RULE-5**：第 2 轮同基座 → U-P041-1 pending。
