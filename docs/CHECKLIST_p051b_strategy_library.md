# CHECKLIST：P-051b 策略模板库（`strategies/` 四模板 + registry 接线）

> **批次**: P-051b · **Step 7** · 日期 2026-11-21 · **判档 T1**
> **上游**: [IMPL_p051b](IMPL_p051b_strategy_library.md)（§3 逐处代码 / §4 45 条用例 / §9 Step 6 收敛 3 P1+3 P2+6 P3；6b 复验 5 项全过）；[DESIGN_p051b](DESIGN_p051b_strategy_library.md)（D1-D11 / I1-I12 / §0.3 收敛表）；[RESEARCH_p051b](RESEARCH_p051b_strategy_templates.md)（§18 三缺口闭环）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；**禁止预填**
> **状态**: **Step 9 已执行（2026-11-21）**：A10 + B7 + C5 + I12 = **34 项全部 ✅**；实测读数见 §7
> **基线读数（@`9c914df`）**: pytest **1040** / `-k golden` **22** / mypy **113 files 0** / black `--check .` **226** / `tests/*.py` **112** / `core/*.py` **45**
> **实测读数（Step 9）**: pytest **1091**（+51）/ golden **22（零重录）** / mypy **119 files 0** / black **240 unchanged** / `tests/*.py` **120**（+8）/ `core/*.py` **45** / `strategies/` **6**

---

## 1. A 组：代码变更（10 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `core/strategy.py` `MarketView` **末位**加 `history: Optional[dict[str, pd.DataFrame]] = None`（带 docstring）；前 5 字段顺序/类型零变；`dataclasses.fields` 5→6 | 无 | 读码 + V1/V2 | ✅ |
| A2 | `views_from_data` 末位加 `history_window: int = 0`；`history_window>0` 时预载 `close/high/low` 三面板（`reindex(index=dates, columns=dm.stock_codes)`），`i>=W` 才切片 `iloc[i-W:i]`；`=0` 时 `panels` 空、`history` 恒 `None` | A1 | 读码 + V3/V4/V5/V6/V7 | ✅ |
| A3 | `strategies/base.py` 新建：`StrategyConfigError(ValueError)` + `require_keys`/`require_history`/`equal_weight`/`scale_to_one`/`build_config`，签名与 IMPL §3.2 逐字一致；`__all__` 六项 | 无 | 读码 + C 组 | ✅ |
| A4 | `strategies/grid.py`：`GridATRConfig.base_price: Mapping \| None = None` + `__post_init__` 判 None/空→失败；`atr` 用 `cast(pd.DataFrame, ...)`；`generate_signals` 按 `floor((base−price)/(k·ATR))` clip 0..levels 后 `scale_to_one` | A3 | 读码 + G1-G7 | ✅ |
| A5 | `strategies/trend.py`：`TrendBreakoutConfig(entry_n=20, exit_n=10, ma_n=60)`（**无 atr_period**）；`max/min/mean(skipna=False)`；持仓查 `lower`、未持仓查 `upper+ma` | A3 | 读码 + T1-T5 | ✅ |
| A6 | `strategies/momentum.py`：`TSMomentumConfig(lookbacks=(20,60,120), min_votes=2)`；`close.iloc[-lb]`（**非 −1−lb**）；`ratio.fillna(0)`；票数 `>= min_votes` | A3 | 读码 + M1-M8 | ✅ |
| A7 | `strategies/mean_reversion.py`：`MeanReversionConfig(lookback=20, z_entry=2.0, z_exit=0.5)`；`std(ddof=1)`；`mask(std==0, 0.0)`；入场 `z<=-z_entry`、持仓 `z>=-z_exit` 才出场 | A3 | 读码 + R1-R7 | ✅ |
| A8 | `strategies/__init__.py`：四文件集中 import 触发注册；顺序 grid→trend→momentum→mean_reversion（DESIGN §2.3）；`__all__` 12 项 | A4-A7 | 读码 + C1 | ✅ |
| A9 | `.github/workflows/tests.yml` 的 mypy 命令行在 `strategy_evaluation` 后插入 `strategies`，`--explicit-package-bases --check-untyped-defs` 原样保留 | A3-A8 | 读码 + C3 | ✅ |
| A10 | **零改动**：`core/sizing.py`、`core/engine_v2.py`、`core/stops.py`、`core/volatility.py`、`core/registry.py`、`tests/_golden_cases.py`、`scripts/record_golden.py` 全部零 diff；`core/strategy.py` 改动仅 A1/A2 两处 | A2 | `git diff --stat` | ✅ |

---

## 2. B 组：测试（7 文件 / 45 条 / 参数化 +48）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | `tests/_p051b_common.py`（下划线前缀，**不被收集**）+ `tests/test_p051b_views_history.py`：V1-V7 全绿（5 位置参数可用 / hash TypeError / `==` ValueError / 三面板键集与列序 / `=0` 零行为 / `i<W` 为 None / 与 returns 同窗 / `iloc[-1]`=t−1 价） | A1/A2 | pytest | ✅ |
| B2 | `tests/test_p051b_ts_momentum.py`：M1-M8 全绿；**M1 按 §18.3.1 原表**（A 100/60/80/90→2 票、B 50/60/70/80→3 票、C 100/80/70/75→1 票）→ `{A:0.5, B:0.5}`；M8 行数 `max(lookbacks)−1` → `StrategyConfigError` | A6 | pytest | ✅ |
| B3 | `tests/test_p051b_mean_reversion.py`：R1-R7 全绿；**统一条款「末 k 行=L」**（R1 k=3→−2.3202 / R2 k=4→−1.9494 / R3 k=1→−4.2485 / R4 k=16→−0.4873 出场 / R5 k=15→−0.5627 保持 / R6 恒定价 / R7 纯函数） | A7 | pytest | ✅ |
| B4 | `tests/test_p051b_trend_breakout.py`：T1-T5 全绿；T1 high=10（upper=10）prices=11 入场；**T2 自建 high=11**（upper=11）prices=10.5 拒绝；T3 prices=8.5 持仓出场；T4 prices=9.5 持仓保持 | A5 | pytest | ✅ |
| B5 | `tests/test_p051b_grid_atr.py`：G1-G7 全绿；G1 ATR=1.0 与 seed 无关；G2 价位 10/9/8/7/6 → 0/⅓/⅔/1/1；G3 缩放 `{A:0.25, B:0.75}`；G4 三入口 fail-fast；G5 缺键→0；G6 单标的 NaN→0 | A4 | pytest | ✅ |
| B6 | `tests/test_p051b_strategy_contract.py`：C1-C7 全绿（四 id 注册 / 协议 isinstance / 12 hex / 工厂三形态等价 / 重复注册 warning / param_schema 键集 / 未知键拒绝 / history=None 四模板 fail-fast）；**C2_grid 无参数化** | A8 | pytest | ✅ |
| B7 | `tests/test_p051b_end_to_end.py`：E1-E4 全绿；**E1 三步协议**（30 行夹具 / WINDOW=15 / `views[15:]` / 头部补零 concat / index 与 dates 全等）；E2 自建 `10→10→7.5` 止损触发；E3 行和 ≤1+1e-9；E4 两次 `assert_frame_equal` | A4-A8/A9 | pytest | ✅ |

---

## 3. C 组：门禁（5 项）

| ID | 门禁 | 命令 | 目标 | 实测 |
|----|------|------|------|------|
| C1 | pytest 全量 | `.\.venv\Scripts\python.exe -m pytest -q`（`$env:MPLBACKEND='Agg'`） | **1091 passed** | ✅ |
| C2 | golden | `.\.venv\Scripts\python.exe -m pytest -q -k golden` | **22 passed**（零重录） | ✅ |
| C3 | mypy | `-m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation strategies cli.py order_strategy web factor_library tools examples` | **119 files，0 error** | ✅ |
| C4 | black | `-m black --check .` | **240 files unchanged** | ✅ |
| C5 | 无新增 golden 目录 | `git status --porcelain tests/golden` | 输出为空 | ✅ |

---

## 4. I 组：不变式（12 项）

| ID | 不变式 | 证据出口 | 实测 |
|----|--------|----------|------|
| I1 | `history_window=0` / `history=None` ⇒ 默认路径零行为变更 | V4 / C1（1040 既有全绿） | ✅ |
| I2 | 策略只产出目标权重，不接触订单/执行/账目 | C1（`isinstance(strategy, Strategy)`）+ 读码 | ✅ |
| I3 | 四模板 `generate_signals` 为纯函数：不写 `state.extras`、无类级可变状态 | M6/R7/T5/G7/E4 | ✅ |
| I4 | `meta.param_schema` 键集 == 配置 dataclass 字段集，且反映全部生效参数 | C5 + C2 | ✅ |
| I5 | 输出权重非负、行和 `<= 1 + 1e-9` | M5 / E3 | ✅ |
| I6 | `get_strategy_registry().get(id)` 四 id 均非 None 且实现 `Strategy` 协议 | C1 | ✅ |
| I7 | `meta.code_hash` 12 hex（复用 P-044 `code_hash`） | C1 | ✅ |
| I8 | **零新增 golden、22 条零重录** | C2 / C5 / B* | ✅ |
| I9 | `strategies/` 无 I/O、无 logger、无随机、无全局写 | grep `open(\|requests\.\|logging\|random\.` | ✅ |
| I10 | 契约不满足一律 `StrategyConfigError`（缺失 history / 缺键 / 行数不足 / 空 base_price / 未知键 / 非法参数） | C7 / G4 / M8 / C6 | ✅ |
| I11 | `history_window=0` 时 P-044 全部既有用例（含 V5 weights 等价）不变 | A2 + C1 | ✅ |
| I12 | **前视零容忍**：当日决策只读 `[t−W, t−1]` 历史与当日 `prices`；改 t−1 值结果变、改当日 prices 不变 | M7 / R7 / T5 | ✅ |

---

## 5. Step 9 执行顺序（TDD）

1. **先改 `core/strategy.py` 两处 additive** → 立即跑 `pytest -q` 确认 **1040 全绿**（I11 零退化闸门，未过不得继续）；
2. 写 `tests/test_p051b_views_history.py`（V1-V7）红态 → `strategies/` 尚不存在但 V 组只依赖 `core` → 实现后转绿；
3. 新建 `strategies/base.py` + `tests/_p051b_common.py`；
4. 逐模板「先测后码」，顺序 **M → R → T → G**（M1 必须先按 §18.3.1 表逐值构造再实现）；
5. `strategies/__init__.py` → C 组（C1-C7）转绿；
6. E 组端到端（E1 三步协议必须完整，缺 ① 或 ② 必挂）；
7. 全量门禁 C1-C5 + A10 零 diff 核验；
8. **失败即停**：任何一项红灯不得进入 Step 8。

**命令**（PowerShell）：

```powershell
$env:MPLBACKEND='Agg'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q -k golden
.\.venv\Scripts\python.exe -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation strategies cli.py order_strategy web factor_library tools examples
.\.venv\Scripts\python.exe -m black --check core tests strategies
git diff --stat core/sizing.py core/engine_v2.py core/stops.py core/volatility.py core/registry.py tests/_golden_cases.py scripts/record_golden.py
```

---

## 6. 计数自检

| 项 | 加总 | 值 |
|----|------|-----|
| 用例 | C 10（C7 参数化 4）+ V 7 + M 8 + R 7 + T 5 + G 7 + E 7（E1 参数化 4） | 51 |
| pytest | 1040 + 51 | **1091** |
| tests 文件 | 112 + 7 个 `test_p051b_*.py` + 1 个 `_p051b_common.py` | **120** |
| mypy 文件 | 113 + 6（strategies 包）| **119** |
| black 文件 | 基线 226 + 14 新文件 | **240** |

---

## 7. Step 9 实测结果与偏差记录

**执行结果（2026-11-21）**

| 门禁 | 命令 | 实测 | 判定 |
|------|------|------|------|
| pytest | `python -m pytest -q` | **1091 passed**，108.13s | ✅ |
| golden | `python -m pytest -q -k golden` | **22 passed, 1069 deselected** | ✅ 零重录 |
| mypy | `mypy --explicit-package-bases --check-untyped-defs ... strategies ...` | **Success: no issues found in 119 source files** | ✅ |
| black | `black --check .` | **240 files would be left unchanged** | ✅ |
| 零改动 | `git diff --stat core/sizing.py … scripts/record_golden.py` | 输出为空 | ✅ |
| golden 目录 | `git status --porcelain tests/golden` | 输出为空 | ✅ |

**偏差与解释（2 项，均为预估口径差异，非缺陷）**

1. **pytest 1088 → 1091（+3）**：DESIGN 的 +48 只把 C7 参数化（+3）计入，**E1 参数化 4 例未计**（45 条名义里 E1 按 1 条算）。E1 实际展开 4 个用例 → 额外 +3，故 1040+45+3+3 = **1091**。逐文件实测：contract 10 / views 7 / momentum 8 / mean_reversion 7 / trend 5 / grid 7 / end_to_end 7 = 51。
2. **black 170 → 240**：真实门禁是 `black --check .`（[spec_runner_adapter.py](file:///f:/Coding/Factor_Trading_v3.0/scripts/spec_runner_adapter.py#L66) L66），覆盖全仓 .py，不是 `core tests strategies`。基线 226 + 14 个新文件 = 240。

**Step 9 实施中新发现并修复的问题（6 项，均为 IMPL 转录缺陷）**

| ID | 问题 | 修复 |
|----|------|------|
| S9-1 | `momentum.py` 用 `np.sign(ratio)` 累加 → **负收益记 −1 票**，与 §18.3.1「负收益记 0 票」冲突，M1 得 1 票而非 2 票 | 改 `(ratio > 0).astype(int)` |
| S9-2 | `_p051b_common.make_view` 的 `codes or CODES` 把空列表当 falsy 回退 → M4 shape 报错 | 改 `CODES if codes is None else codes` |
| S9-3 | contract `test_c3` 用真实 id `ts_momentum` 重复注册 → registry **覆盖**真实工厂，后续用例全挂 | 改独立探针 id `_p051b_dup_probe` + `unregister` |
| S9-4 | contract `test_c7` 缺 `import numpy as np` | 补 import |
| S9-5 | G6 断言 `.empty`，但 grid 保留显式 0 权重（非空 Series） | 改断言 `weights.get(...) == 0` 且 `sum()==0` |
| S9-6 | 改 CI mypy 命令后 `test_p024_ci_gate_alignment` 报 CI/本地口径不一致 | 同步 `scripts/spec_runner_adapter.py` GATES 加 `strategies` |

**I12 前视验证**：M7 用「改 t−1 值结果变 / 改当日 prices 结果不变」实证；V7 断言 `history["close"].iloc[-1]` 严格等于 `dates[i−1]` 原始收盘。✅
