# IMPL：P-041 infer_board 号段表补齐（U-P040-2）

> **批次**: P-041 · **Step 5 实施规划** · 日期 2026-11-17
> **判档**: **T1**（Layer-1：`tests/`；生产面 `filter/limit_rules.py`）
> **上游**: [DESIGN_p041](DESIGN_p041_infer_board_segments.md)（D1-D4 / I1-I7 / §7 Step 4 复审 pass：1 P2 + 2 P3）
> **代码证据时点**: HEAD `24688ab`

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 代码 1 | `filter/limit_rules.py`：模块 docstring L5 + 前缀元组两行 + 版本行（实测 **+4/−4**；初稿「约 +3/−2」按 4 行变更订正，见 F-S9-P041-2） |
| 测试 1 | `tests/test_p041_board_segments.py`（新建，7 用例） |
| 测试订正 | `tests/test_p040_bse_limit_rule_gap.py` **两行**（L40 docstring + L41 断言）；DESIGN §1 记「一行」为笔误，F-S6-P041-1 订正 |
| 零改动面 | `RULES` / `resolve_limit` / `build_limit_prices` / `universe_filter_clean.py` / `core/**` / `tests/_synth_fixture.py` / `tests/golden/**` / `tests/test_limit_rules.py` / `pyproject.toml` / `uv.lock` / 门禁双载体 |
| 门禁 | pytest **771 → 778** / golden 13 零重录 / mypy 12 面 0（103 files）/ black **124**（全仓 **191**）/ AST **22** / `tests/*.py` **87** / `uv lock` exit 0 |

**四条前提**：① 三公开签名零变更；② 不新增 `except` / `raise` / `# type: ignore`；③ `RULES` 13 条逐字不动；④ 不清理 `_RULE_INDEX`（O-P040-5）。

---

## 2. 精确变更规格

### 2.1 `filter/limit_rules.py` L5（模块 docstring）

**改前**：`- 板块由代码前缀推断：300/301→gem；688/689→star；8/4 开头→bse；其余→main。`
**改后**：`- 板块由代码前缀推断：300/301/302→gem；688/689→star；8/4/920 开头→bse；其余→main。`

### 2.2 `filter/limit_rules.py` L85 / L89（前缀元组）

**改前**：

```python
    if prefix.startswith(("300", "301")):
        return "gem"
    if prefix.startswith(("688", "689")):
        return "star"
    if prefix.startswith(("8", "4")):
        return "bse"
```

**改后**：

```python
    if prefix.startswith(("300", "301", "302")):
        return "gem"
    if prefix.startswith(("688", "689")):
        return "star"
    if prefix.startswith(("8", "4", "920")):
        return "bse"
```

### 2.3 `filter/limit_rules.py` L19

**改前**: `RULESET_VERSION = "cn_a_2026_11"`
**改后**: `RULESET_VERSION = "cn_a_2026_11b"`

### 2.4 `tests/test_p040_bse_limit_rule_gap.py` L40-41（两行）

```python
# 改前
    """V3：北交所期维持 30%；C2 版本口径为 cn_a_2026_11。"""
    assert RULESET_VERSION == "cn_a_2026_11"
# 改后
    """V3：北交所期维持 30%；C2 版本口径为 cn_a_2026_11b。"""
    assert RULESET_VERSION == "cn_a_2026_11b"
```

### 2.5 `tests/test_p041_board_segments.py`（新建，完整代码）

```python
"""P-041 infer_board 号段表补齐回归测试（U-P040-2）。

覆盖：920→bse / 302→gem / 既有前缀非回归 / 920 跨制度期价格 /
302 跨注册制边界 / 版本与未识别计数 / 带后缀代码。
"""

from __future__ import annotations

import pandas as pd
import pytest

from filter.limit_rules import (
    RULESET_VERSION,
    build_limit_prices,
    infer_board,
    unknown_board_count,
)


def test_v1_920_maps_to_bse():
    """V1：北交所 920 号段 → bse。"""
    for code in ("920000", "920493", "920931"):
        assert infer_board(code) == "bse"


def test_v2_302_maps_to_gem():
    """V2：创业板 302 号段 → gem。"""
    assert infer_board("302132") == "gem"


def test_v3_existing_prefixes_unchanged():
    """V3：既有前缀映射零变更（含未知前缀回落 main）。"""
    cases = {
        "300001": "gem",
        "301001": "gem",
        "688001": "star",
        "689001": "star",
        "830001": "bse",
        "430001": "bse",
        "000001": "main",
        "001001": "main",
        "002001": "main",
        "003001": "main",
        "600001": "main",
        "601001": "main",
        "603001": "main",
        "605001": "main",
        "700001": "main",
    }
    for code, board in cases.items():
        assert infer_board(code) == board


def test_v4_920_limit_prices_across_regimes():
    """V4：920 在集合竞价段 20/5、精选层段 13/7（flat 10、adj=1）。"""
    dates = pd.DatetimeIndex(["2020-07-22", "2020-07-23", "2020-07-24", "2020-07-27", "2020-07-28"])
    close = pd.DataFrame({"920493": [10.0] * 5}, index=dates)
    adj = pd.DataFrame({"920493": [1.0] * 5}, index=dates)

    up, down = build_limit_prices(close, adj, None, dates)

    for d in (dates[1], dates[2]):
        assert up.loc[d, "920493"] == pytest.approx(20.0)
        assert down.loc[d, "920493"] == pytest.approx(5.0)
    for d in (dates[3], dates[4]):
        assert up.loc[d, "920493"] == pytest.approx(13.0)
        assert down.loc[d, "920493"] == pytest.approx(7.0)


def test_v5_302_limit_prices_across_gem_regime():
    """V5：302 在 2020-08-24 前后分别为 10% / 20%（flat 10、adj=1）。"""
    dates = pd.DatetimeIndex(["2020-08-20", "2020-08-21", "2020-08-24"])
    close = pd.DataFrame({"302132": [10.0] * 3}, index=dates)
    adj = pd.DataFrame({"302132": [1.0] * 3}, index=dates)

    up, down = build_limit_prices(close, adj, None, dates)

    assert up.loc[dates[1], "302132"] == pytest.approx(11.0)
    assert down.loc[dates[1], "302132"] == pytest.approx(9.0)
    assert up.loc[dates[2], "302132"] == pytest.approx(12.0)
    assert down.loc[dates[2], "302132"] == pytest.approx(8.0)


def test_v6_version_and_unknown_counting():
    """V6：版本口径 cn_a_2026_11b；920/302 不再计入未识别前缀。"""
    assert RULESET_VERSION == "cn_a_2026_11b"
    before = unknown_board_count()
    assert infer_board("920493") == "bse"
    assert infer_board("302132") == "gem"
    assert unknown_board_count() == before


def test_v7_suffixed_codes():
    """V7：带交易所后缀的代码按点号前主干判定。"""
    assert infer_board("920493.BJ") == "bse"
    assert infer_board("302132.SZ") == "gem"
```

---

## 3. 红态（修复前实测预期）

| 用例 | 修复前 | 预期 |
|------|--------|------|
| V1 | `infer_board("920000") == "main"` | **FAIL** |
| V2 | `infer_board("302132") == "main"` | **FAIL** |
| V3 | 既有前缀不受影响 | **PASS**（回归保护） |
| V4 | main 10% → 07-23 `11/9`（期望 `20/5`） | **FAIL**（首段首个断言） |
| V5 | 08-21 `11/9` **通过**；08-24 仍 `11/9`（期望 `12/8`） | **FAIL**（第二段断言，F-S6-P041-3 精确化） |
| V6 | 版本断言失败（旧 `cn_a_2026_11`） | **FAIL** |
| V7 | 后缀代码同落 `main` | **FAIL** |

**预期红态**: `6 failed, 1 passed`（V1/V2/V4/V5/V6/V7 FAIL；V3 PASS）。

---

## 4. 门禁终态（Step 9 目标）

| 项 | 目标 |
|----|------|
| pytest | **778 passed**（771 + 7） |
| golden | **13 passed, 758 deselected**；`tests/golden/` 干净 |
| mypy 12 面 | `Success: no issues found in 103 source files` |
| black | `124`（core tests）/ `191`（全仓）unchanged |
| AST `except Exception` | **22** |
| `tests/*.py` | **87** |
| `uv lock --check` | exit **0** |
| 新增 `except` / `raise` / `# type: ignore` | 0 / 0 / 0；`^[+-]\s*def ` = 0 |
| 代码变更面 | `filter/limit_rules.py` 1 文件（约 +3/−2） + 2 个测试文件 |

---

## 5. 回退点

单提交 revert → 294 只回落 `main`、版本回到 `cn_a_2026_11`；无跨批依赖。

---

## 6. Step 6 实施 Review 记录（同基座独立视角，2026-11-17）

> **基座披露（RULE-4）**: 自报 DeepSeek-V4.1-Flash → 同源，RULE-5 不成立；U-P041-1 累计第 3 轮。

### 6.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | 2.1-2.3 与 DESIGN-D1/D2 逐字 | docstring / 两元组 / 版本行一致 | ✅ |
| A | 元组无前缀吞并 | `302` 不在 `_MAIN_PREFIXES`；`920` 与 `8`/`4` 无交集 | ✅ |
| B | V4 数值链 | ref=10 → 20/5（集合竞价）；13/7（精选层） | ✅ |
| B | V5 数值链 | ref=10 → 11/9（10%）；12/8（20%） | ✅ |
| C | 红态可复现性 | V1/V2/V4/V5(第二段)/V6/V7 均红；V3 绿 | ✅（6F/1P） |
| D | 版本耦合 | P-040 **两行**（docstring + 断言），非一行 | ✅（F-S6-P041-1 订正） |
| E | 计数 | 771+7=778；123+1=124；190+1=191；86+1=87 | ✅ |

### 6.2 发现与当轮处置（1 P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S6-P041-1** | **P2** | DESIGN §1/§7 记 P-040 测试耦合为「仅一行」，实际为 **两行**（L40 docstring 亦含 `cn_a_2026_11`）→ 若只改断言会留下陈旧 docstring | 本文件 §1/§2.4 按两行执行；DESIGN §1 当轮订正为「两行」 |
| F-S6-P041-2 | P3 | V4/V5 迷你帧首行 `ref` 为 NaN 未断言（既有契约） | 保持（P-040 V6 已覆盖首行 NaN 语义） |
| F-S6-P041-3 | P3 | §3 红态表初稿把 V5 记为「首个断言失败」——实际 08-21 在 main 下也是 `11/9` 通过，失败点在 08-24 | 已精确为「第二段断言」 |

### 6.3 结论

**Step 6 Review pass（1 P2 + 2 P3 当轮回写）**——规格与 DESIGN 逐字一致、红态可复现、计数自洽；**准予进入 Step 7 CHECKLIST**。
**RULE-5**：第 3 轮同基座 → U-P041-1 pending。

---

## 7. Step 9 实施记录（2026-11-17）

| 项 | 读数 |
|----|------|
| 落码 | [limit_rules.py:5](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L5) docstring + [L85](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L85)/[L89](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L89) 两元组 + [L19](file:///f:/Coding/Factor_Trading_v3.0/filter/limit_rules.py#L19) 版本；**+4/−4** |
| 测试 | [tests/test_p041_board_segments.py](file:///f:/Coding/Factor_Trading_v3.0/tests/test_p041_board_segments.py) 新建（7 用例）；P-040 两行订正（L40/L41） |
| 红态 | **`6 failed, 1 passed in 0.73s`**（V1/V2/V4/V5-第二段/V6/V7 FAIL；V3 PASS） |
| 绿态 | **`13 passed in 0.66s`**（7 新 + P-040 6）；单跑新文件 `7 passed` |
| 门禁 | pytest **778 passed**（90.61s）/ golden **13·765**（目录净）/ black **124·191** / mypy 12 面 **103 files 0** / AST **22** / `tests/*.py` **87** / uv exit **0** / `^[+-]\s*def `=0 / 新增 `except|raise|ignore`=0 |
| 真实数据（D4/D5/D6） | `infer_board`：`920000→bse`、`302132→gem`；920×**293** / 302×**1** / 总列 **5,688**；`len(RULES)=13`；全列遍历后 `unknown_board_count=0`；掩码 `920 @main 2072/1163 → @bse 319/164`、`302132 @main 10/1 → @gem 7/1` → 翻转 **2,755**；`setup()` 推进到 U-P038-1 `FileNotFoundError`（`trade_dates=1460`） |

### 7.1 实施期发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P041-1 | P3 | black（行宽 120）把 V4 的 `DatetimeIndex` 多行合并为单行，与 IMPL §2.5 代码块不一致 | §2.5 已同步为 black 终态；语义零变化 |
| F-S9-P041-2 | P3 | §1「约 +3/−2」偏小：docstring + 两元组 + 版本行实为 **+4/−4** | §1 按实测订正 |

**结论**: **Step 9 pass**——7 用例绿、九项门禁全绿、真实数据 D4-D6 达标；主缺陷 U-P040-2 修复完成。
