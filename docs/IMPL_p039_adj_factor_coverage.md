# IMPL：P-039 adj_factor 日期覆盖缺陷修复

> **批次**: P-039 · **Step 5 实施规划** · 日期 2026-11-17
> **判档**: **T1**（Layer-1：`core/data.py` + `tests/`）
> **上游**: [DESIGN_p039](DESIGN_p039_adj_factor_coverage.md)（D1-D4 / I1-I6 / V1-V6 / §8 Step 4 复审 pass：1 P2 + 2 P3 当轮回写）；[RESEARCH_p039](RESEARCH_p039_adj_factor_coverage.md)（§6 M-A / §12 F-S1-P039-1 / §13 Step 2 复审 pass）
> **代码证据时点**: HEAD `377b26a`
> **基座**: DeepSeek-V4.1-Flash（Step 6 Review 须自报基座；同源时登记 U-P039-3）

---

## 1. 范围与约束

| 项 | 内容 |
|----|------|
| 变更文件（代码 1） | `core/data.py`（`_load_price_data` 的 `adj_factor` 分支，**1 处**） |
| 变更文件（测试 1） | `tests/test_p039_adj_factor_coverage.py`（**新建**，5 用例） |
| 变更文件（文档） | 本文件 / `docs/PROGRESS.md`（§1.4 + §3.44.x）/ `CHANGELOG.md` |
| 零改动面 | `filter/**`（下游已 reindex）/ `tests/_synth_fixture.py` / `pyproject.toml` / `tests/golden/**` / `agents/**` / 门禁双载体 |
| 门禁口径 | pytest **760 → 765** / golden **13 零重录** / mypy 12 面 **0** / black **121** / AST `except Exception` 恒 **22** / `uv lock` exit 0 / 新增 `# type: ignore` **0** |

**四条不可越界的前提**：

1. **只改 `adj_factor` 分支**：`close/open/high/low` 的 `.loc` 逐字不变；
2. **三段式顺序固定**：`reindex(data.index.union(window)) → ffill → reindex(window)`（F-S1-P039-1）；
3. **不加 `bfill`**、不加 `try/except`（保持 fail-fast）、不改公开签名（`_load_price_data` 为私有）；
4. **不改共享夹具**：测试用局部后处理改写 `stock_adj.pkl`。

---

## 2. 任务拆解

| ID | 任务 | 对应 | 规模 |
|----|------|------|------|
| **B1** | 改 `core/data.py` 的 `adj_factor` 分支（含 `logger.info` 计数） | DESIGN-D1/D2 | 1 处（~~+9/−1~~ → **+12/−1**，F-S9-P039-1） |
| **B2** | 新建 `tests/test_p039_adj_factor_coverage.py`（V1-V5） | DESIGN-D4 | 1 文件 5 用例 |
| **DOC1** | 文档回填（本文件 §9 / PROGRESS / CHANGELOG / CHECKLIST） | — | — |

**计数**：1 代码改动点 + 5 测试用例；无新增依赖、无门禁变更。

---

## 3. 精确变更规格

### 3.1 `core/data.py`（L300-302 → 9 行）

**改前**（`_load_price_data` 内）：

```python
            # 应用日期过滤
            if self._trade_dates is not None:
                data = data.loc[self._trade_dates]
```

**改后**：

```python
            # 应用日期过滤
            if self._trade_dates is not None:
                if price_type == "adj_factor":
                    # 复权因子在除权日之间恒定（P-039），缺失日按前值填充；
                    # 未上市/退市期保持 NaN（与 close 同步）。三段式：并集对齐创建
                    # 缺失行 → ffill 取前值（含窗口外）→ 回裁窗口。两段式在窗口首日
                    # 缺口时留 NaN（F-S1-P039-1 实测），不可简化。
                    window = self._trade_dates
                    n_missing = len(window.difference(data.index))
                    data = data.reindex(data.index.union(window)).ffill().reindex(window)
                    if n_missing:
                        logger.info(f"adj_factor 日期补齐: {n_missing} 日（ffill 前值填充）")
                else:
                    data = data.loc[self._trade_dates]
```

**约束**：L304-315（列裁剪 / 缓存 / `_prices`）逐字不动；`data.index` 在 L297-298 已转 `DatetimeIndex`，`union` 结果为单调 `DatetimeIndex`。

### 3.2 `tests/test_p039_adj_factor_coverage.py`（新建）

```python
"""P-039 adj_factor 日期覆盖缺陷回归测试（U-P038-2）。

覆盖：缺日补齐 / 无缺日等价 / 窗口首日缺口 / 不污染无前值期 / 修复范围仅 adj。
夹具复用 ``tests/_synth_fixture.write_price_fixture``（全日期覆盖），
再用局部后处理改写 ``stock_adj.pkl``——**不修改共享夹具**（DESIGN-D3）。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.config import BacktestConfig
from core.data import DataManager
from _synth_fixture import write_price_fixture  # tests/ 无 __init__.py，沿既有 6 个测试的导入方式（F-S6-P039-1）

DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]
CODES = ["000001", "000002"]
ADJ_BY_DATE = {
    "2024-01-02": 1.0,
    "2024-01-03": 1.1,
    "2024-01-04": 1.2,
    "2024-01-05": 1.3,
    "2024-01-08": 1.4,
}


def _prepare(tmp_path: Path, *, drop_adj=(), drop_open=(), adj_na=()) -> DataManager:
    """写完整夹具 → 后处理 → 返回已加载 basic data 的 DataManager。"""
    write_price_fixture(tmp_path, DATES, CODES, prices=10.0)

    adj_path = tmp_path / "stock_adj.pkl"
    adj = pd.read_pickle(adj_path)
    for d, v in ADJ_BY_DATE.items():
        adj.loc[pd.Timestamp(d), :] = v
    for d in adj_na:  # 该日全列置 NaN（模拟「无前值」）
        adj.loc[pd.Timestamp(d), :] = np.nan
    if drop_adj:
        adj = adj.drop(index=[pd.Timestamp(d) for d in drop_adj])
    adj.to_pickle(adj_path)

    if drop_open:
        open_path = tmp_path / "open.pkl"
        o = pd.read_pickle(open_path)
        o = o.drop(index=[pd.Timestamp(d) for d in drop_open])
        o.to_pickle(open_path)

    cfg = BacktestConfig(data_dir=tmp_path, write_manifest=False)
    dm = DataManager(cfg)
    _ = dm.trade_dates  # 触发 _load_basic_data，使 _trade_dates 非 None
    return dm


def test_v1_missing_day_ffilled(tmp_path):
    """V1：缺日补齐为前值。"""
    dm = _prepare(tmp_path, drop_adj=["2024-01-04"])
    adj = dm.adj_factor
    assert len(adj) == len(DATES)
    assert adj.loc[pd.Timestamp("2024-01-04"), "000001"] == pytest.approx(1.1)
    assert adj.loc[pd.Timestamp("2024-01-05"), "000001"] == pytest.approx(1.3)


def test_v2_no_gap_equivalence(tmp_path):
    """V2：无缺日时与直接读取逐值相等（回归保护）。"""
    dm = _prepare(tmp_path)
    adj = dm.adj_factor
    raw = pd.read_pickle(tmp_path / "stock_adj.pkl")
    raw = raw.reindex(columns=dm.stock_codes)  # F-S4-P039-2：显式列对齐
    pd.testing.assert_frame_equal(adj, raw)


def test_v3_window_first_day_gap_uses_outside_prev(tmp_path):
    """V3：窗口首日缺口 → 取窗口外前值（三段式唯一性）。"""
    write_price_fixture(tmp_path, DATES, CODES, prices=10.0)
    adj_path = tmp_path / "stock_adj.pkl"
    adj = pd.read_pickle(adj_path)
    for d, v in ADJ_BY_DATE.items():
        adj.loc[pd.Timestamp(d), :] = v
    adj = adj.drop(index=[pd.Timestamp("2024-01-04")])
    adj.to_pickle(adj_path)

    cfg = BacktestConfig(data_dir=tmp_path, start_date="2024-01-04", write_manifest=False)
    dm = DataManager(cfg)
    _ = dm.trade_dates
    got = dm.adj_factor.loc[pd.Timestamp("2024-01-04"), "000001"]
    assert got == pytest.approx(1.1)  # 2024-01-03（窗口外）的值


def test_v4_no_bfill_before_first_value(tmp_path):
    """V4：无前值时保持 NaN（禁止 bfill 污染）。"""
    dm = _prepare(tmp_path, adj_na=("2024-01-02",))
    adj = dm.adj_factor
    assert np.isnan(adj.loc[pd.Timestamp("2024-01-02"), "000001"])
    assert adj.loc[pd.Timestamp("2024-01-03"), "000001"] == pytest.approx(1.1)


def test_v5_other_kinds_still_strict(tmp_path):
    """V5：修复范围仅 adj_factor——open 缺日仍按现网 KeyError（拜占庭边界）。"""
    dm = _prepare(tmp_path, drop_open=["2024-01-04"])
    with pytest.raises(KeyError, match="not in index"):  # F-S4-P039-3
        _ = dm.open
```

---

## 4. 红态（Step 9 必须出示）

| 用例 | 修复前预期 | 实测（Step 6 预跑，F-S6-P039-2 订正） |
|------|-----------|------------------------------------|
| V1 | `KeyError: "['2024-01-04'] not in index"` | **FAIL**：`KeyError: "[Timestamp('2024-01-04 00:00:00')] not in index"` ✅ |
| V2 | **通过**（回归保护，红态即通过） | **PASS** ✅ |
| V3 | `KeyError`（窗口首日缺口） | **FAIL**：同形 KeyError ✅ |
| V4 | ~~`KeyError`（同根）~~ → **通过**（本用例不 drop 行，仅置 NaN，日期完整） | **PASS**（回归保护）✅ |
| V5 | **通过**（红态即通过，边界保护） | **PASS** ✅ |

> **预跑读数**：`2 failed, 3 passed in 1.01s`（`%TEMP%\p039_proto_test.py`，`PYTHONPATH=<repo>;<repo>\tests`）。

---

## 5. 门禁终态（Step 9 实测）

| 项 | 读数 | 实测 |
|----|------|------|
| pytest | **765 passed**（760 + 5） | ✅ `765 passed, 172 warnings in 42.05s` |
| golden | **13 passed, 752 deselected**；`tests/golden/` 零改动 | ✅ `13 passed, 752 deselected`；`git status --short tests/golden/` 空 |
| mypy 12 面 | `Success: no issues found in 103 source files` | ✅ 同文（`core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples`） |
| black | `core tests` **122**（121 unchanged + 1 新文件）/ 全仓 `.` **189** | ✅ `122 files would be left unchanged` / `189 files would be left unchanged` |
| AST | `except Exception` 恒 **22**（P-029 十文件口径） | ✅ **22**（IMPL_p029 L410 原命令复跑） |
| `uv lock --check` | exit 0 | ✅ exit 0（`Resolved 148 packages`） |
| 新增 `# type: ignore` | 0 | ✅ 0（`git diff -U0` 正则 + AST 计数）；新增 `except` / `raise` 亦 **0** |
| `tests/*.py` | **85**（84 + 1） | ✅ 85 |
| 代码变更面 | 1 代码文件 | ✅ `12 1 core/data.py`（F-S9-P039-1） |

---

## 6. 回退点

- 单提交 revert → 回到 `.loc` 行为；无跨批依赖。
- 若 V1/V3 意外失败 → 先核 `dm.trade_dates` 是否触发（O-P039-2：`adj_factor` property 不自动加载 basic data）。

---

## 7. Step 6 交接

1. **复审须自报基座**（RULE-5）。
2. 核 ① 3.1 的 9 行代码与 DESIGN-D1/D2 逐字一致；② 5 个用例的红/绿可执行性（尤其 V3 的窗口截断与 V4 的无前值构造）；③ `_prepare` 中 `_ = dm.trade_dates` 的必要性；④ black 口径 122/189。
3. **版本存在性**：无新依赖，无需 PyPI 核验。

---

## 8. Step 6 实施 Review 记录（同基座独立上下文，2026-11-17）

> **基座披露**：复审会话 system prompt 逐字自报 `You are powered by the model named DeepSeek-V4.1-Flash.` → **与作者同源，RULE-5 不成立**（RULE-4 披露）；U-P039-3 累计第 3 轮异构未证实。
> **复审方式**：读码核对 + **测试原型预跑**（`%TEMP%\p039_proto_test.py`，`PYTHONPATH=<repo>;<repo>\tests`，修复前）；复审时点 HEAD `377b26a`（代码未改动）。

### 8.1 复核读数

| 组 | 项 | 实测 | 判定 |
|----|----|------|------|
| A | 3.1 的 9 行与 DESIGN-D1/D2 | 逐字一致（`window` / `n_missing` / 三段式 / logger 条件） | ✅ |
| A | `logger` 可用性 | `core/data.py` L25 已定义 | ✅ |
| B | **测试导入方式** | `tests/` **无 `__init__.py`**；既有 6 个测试均为 `from _synth_fixture import ...` | ❌ **F-S6-P039-1** |
| B | `_ = dm.trade_dates` 必要性 | O-P039-2 确认：`adj_factor` property 不触发 `_load_basic_data`，不访问则 `_trade_dates is None` → 跳过对齐 | ✅ 必须保留 |
| C | 夹具文件名字段 | `BacktestConfig` 默认 `close.pkl` / `stock_adj.pkl` / `suspend.pkl` / `st.pkl` / `industry.pkl` 与 `write_price_fixture` 输出**逐一匹配** | ✅ |
| D | **红态预跑** | `2 failed, 3 passed`：V1/V3 FAIL（KeyError）、V2/V4/V5 PASS | ⚠️ **F-S6-P039-2**（V4 预期错） |
| E | black 口径 | 新增 1 测试文件 → `core tests` **122**、全仓 **189** | ✅（F-I-P039-1 已写） |

### 8.2 发现与当轮处置（1 P2 + 2 P3）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S6-P039-1** | **P2** | §3.2 写 `from tests._synth_fixture import ...`，但 `tests/` **无 `__init__.py`** → 运行期 `ModuleNotFoundError`；既有 6 个测试全用 `from _synth_fixture import ...` | §3.2 import 改为 `from _synth_fixture import write_price_fixture` 并加注出处 |
| F-S6-P039-2 | P3 | §4 红态表把 V4 预期写为 `KeyError`——实际 V4 **不 drop 行、只置 NaN**，日期完整 → 红态即通过（预跑证实） | 红态表按「预期 / 实测」双列重写；V4 标 **PASS（回归保护）** |
| F-S6-P039-3 | P3 | 预跑需 `PYTHONPATH` 双路径（repo + tests），文档未写明，Step 9 易卡 | §4 补预跑命令与读数 |

### 8.3 结论

**复审结论**：**pass（1 P2 + 2 P3 全部当轮回写）**——代码规格与 DESIGN 一致、夹具契约匹配、红态 `2 failed / 3 passed` 可复现；P2 修正后测试可落地，**准予进入 Step 7 CHECKLIST**。
**RULE-5**：第 3 轮同基座 → U-P039-3 维持 pending。

---

## 9. Step 9 实施记录（2026-11-17）

### 9.1 落码与红绿

| 项 | 读数 |
|----|------|
| 代码 | [core/data.py](../core/data.py) L302-313 新增 `adj_factor` 分支（**+12/−1**），与 §3.1 逐字一致；`else` 保留 `.loc`，L315 起列裁剪 / 缓存零改动 |
| 测试 | [tests/test_p039_adj_factor_coverage.py](../tests/test_p039_adj_factor_coverage.py) 新建（**104** 行），`from _synth_fixture import ...`（F-S6-P039-1 修正版） |
| 红态 | Step 6 预跑 `2 failed, 3 passed in 1.01s`（V1/V3 FAIL：`KeyError: "[Timestamp('2024-01-04 00:00:00')] not in index"`；V2/V4/V5 红态即通过） |
| 绿态 | `5 passed in 0.57s`（Step 9 本步实测） |

### 9.2 真实数据端到端（V6b）

> **口径订正**：DESIGN §4 原写「修复后 setup 仍因 U-P038-1 抛 `FileNotFoundError`（`_precompute_factors`）」——实测**未推进到该点**：`build_masks()` L151 先于 `_precompute_factors()` L242 执行，崩在 `_build_limit_masks` L220（详见 9.3）。故 V6b 不以日志为唯一出口，改用 `DataManager` 直接探针（F-S9-P039-2）。

**探针读数**（`BacktestConfig(data_dir=E:\Ashare_data\market_data, close_file=stock_close.pkl, open_file=stock_open.pkl, adj_factor_file=stock_adj.pkl, start_date=2020-01-23, end_date=2026-02-09)`）：

| # | 读数 | 含义 |
|---|------|------|
| A | `trade_dates=1460  2020-01-23 .. 2026-01-30` | 窗口与 P-038 一致 |
| B | `adj.shape=(1460, 5688)  close.shape=(1460, 5688)  cols_equal=True` | **缺日 0 / 列对齐 True**（修复前 81 日缺失 → `.loc` KeyError） |
| C | `adj all-NaN rows=0` | 无整行 NaN |
| D | `adj NaN but close non-NaN cells=0` | RESEARCH §2.4 的 **403,853（4.814%）→ 0** 在真实数据上复现 |
| E-F | bse 前缀 **3** 只（`832317/833874/833994`），2020-01-23 均**有值** | 见 9.3 |

**结论**：C1 行为变更生效——`adj_factor` 由「加载失败 → 涨跌停过滤静默跳过」变为「ffill 补齐 → 形状与 close 对齐」。

### 9.3 实施期新发现 U-P039-4（P1，不属本批题干）

- **现象**：探针同一配置跑 `engine.setup()` → `filter.limit_rules.LimitRuleError: 无匹配涨跌停规则: board=bse, is_st=False, date=2020-01-23`。
- **根因**：[filter/limit_rules.py:86-87](../filter/limit_rules.py) `infer_board` 把 `8`/`4` 前缀判为 `bse`（无日期维度）；`RULES` 的 bse 两行 `effective_from=2021-11-15` → 2020 年 0 命中 → [L161-162](../filter/limit_rules.py) `resolve_limit` 抛错。
- **未被兜住**：[filter/universe_filter_clean.py:214](../filter/universe_filter_clean.py#L214) 的 `except (FileNotFoundError, ValueError, KeyError)` 只包住三条 `dm.*` 取数（L208-213），`build_limit_prices` 在 L220 的 **try 之外**；且 `LimitRuleError(ValueError)` 即使入 try 也会被吞成「跳过涨跌停过滤」（静默降级）。
- **暴露关系**：修复前 `dm.adj_factor` 在 L210 抛 KeyError 被 L214 捕获 → 提前降级返回，`build_limit_prices` 从未执行；P-039 修复后该路径打通才暴露——**P-012 遗留缺口，被 adj 失败掩盖**。
- **影响**：任何 `start_date < 2021-11-15` 且启用 `exclude_limit_up/down`（examples 默认）的真实数据回测在 `setup()` 直接崩溃（fail-fast，非静默）。台账见 PROGRESS §1.4 **U-P039-4（P1）**；**本批不扩做**（题干为 adj_factor 日期覆盖，改规则表需独立数据取证与裁决）。

### 9.4 实施期发现与处置

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-P039-1 | P3 | §2 规模写「+9/−1」，实际 `git diff --numstat` = **12 1**（4 行注释 + 8 行代码，含 `else:` 与 `data.loc` 重排）= 12 增 | §2 与 §5 按实测订正为 +12/−1 |
| F-S9-P039-2 | P3 | V6b 原设计以 `logger.info` 日志为出口，但 `examples/run_single_backtest.py` 未 `basicConfig`、root logger 默认 WARNING → INFO 不可见 | 改用 `DataManager` 直接探针（9.2 表），断言形状 / 全 NaN 行 / 交叉 NaN 三口径 |
| F-S9-P039-3 | P3 | DESIGN §4 与 CHECKLIST D5 的「后续 U-P038-1 FileNotFoundError」预期被实施证伪（更早的 LimitRuleError 先触发） | 9.2 口径订正 + 新登记 U-P039-4；CHECKLIST D5 同步改写为「修复生效证据 + 推进至 LimitRuleError」 |

### 9.5 结论

**Step 9 pass**——5 用例绿、九项门禁全绿、真实数据 1460×5688 零缺口；主缺陷（U-P038-2）**已关闭**，实施期另挖 1 个 **P1**（U-P039-4，P-012 遗留）并如实登记、本批不扩做。
