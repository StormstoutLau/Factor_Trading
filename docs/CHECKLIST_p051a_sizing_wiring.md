# CHECKLIST：P-051a 策略接线底座（vol/ATR 波动原语 + `apply_sizing` 引擎接线）

> **批次**: P-051a · **Step 7** · 日期 2026-11-20 · **判档 T1**
> **上游**: [IMPL_p051a](IMPL_p051a_sizing_wiring.md)（§2 逐处代码 / §3 B1-B16 / §9 Step 6 pass：0 P1 / 0 P2 / 5 P3 F-I1..F-I5）；[DESIGN_p051a](DESIGN_p051a_sizing_wiring.md)（D1-D9 / I1-I13 / §10 Step 4：0 P1 / 1 P2 F-D1 已收敛）；[RESEARCH_p051a](RESEARCH_p051a_sizing_wiring.md)（§15 Step 2：0 P1 / 1 P2 F-R1 已收敛）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待 Step 10]`；**禁止预填**
> **状态**: **批次关闭（2026-11-21）**：A7+B16+C4+I13 = **40/40 ✅**；实测 **1040 passed / golden 22 零重录 / mypy 113 files 0 / black 157**；提交 **`ca459e6`** / CI run **`44770811527`** 四 job 全绿（lock-check + 3.10/3.11/3.12）
> **基线读数（@`95a6f6c`）**: pytest **1024** / `-k golden` **22** / mypy **112 files 0** / black `core tests` **155** / `tests/*.py` **111** / `core/*.py` **44**
> **目标读数**: pytest **1040** / golden **22（零重录）** / mypy **113 files 0** / black **157** / `tests/*.py` **112** / `core/*.py` **45**

---

## 1. A 组：代码变更（7 项）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| A1 | `core/volatility.py` 新建：`__all__` 三项、`TRADING_DAYS=252`；`estimate_volatility` 与 `atr` 参数类型/默认值与 IMPL §2.1 逐字一致 | 无（新模块） | 读码 + B1-B4 | ✅ `volatility.py` L22 `__all__` / L24 `TRADING_DAYS`；B1-B4 全绿 |
| A2 | `estimate_volatility`：`rolling(lookback, min_periods=lookback).std(ddof=1)`，`count()==lookback` 才保留；`annualize` → `×√periods`；Series→Series、DataFrame→DataFrame | A1 | B1/B2 | ✅ `rolling.std(ddof=1).where(rolling.count()==lookback)` + `×np.sqrt(periods)`（实现无 skipna）；B1/B2 全绿 |
| A3 | `atr`：`TR[0]=H−L`、`TR[t]=max(H−L,\|H−C_prev\|,\|L−C_prev\|)`；seed `mean(TR[0..period−1])` **skipna=False**；Wilder 递推；前 `period−1` 为 NaN；形状/索引/类型不一致 → `ValueError` | A1 | B3/B4 | ✅ `np.maximum` 三路 + `tr[0]=hl[0]` + numpy mean + 递推；B3 = 0.9/0.8333333/0.8222222、B4 三类 `ValueError` 全绿 |
| A4 | `core/config.py`：TYPE_CHECKING 增 `SizingConfig`；`BacktestConfig` 增 `sizing: "SizingConfig \| None" = None`（L424 `risk_overlay` 之后） | 无 | 读码 | ✅ config.py L17 / L428（`risk_overlay` L423-424 之后） |
| A5 | `setup()` 两处：**(a)** method 子集 fail-fast + 双 vol 告警 + `min_weight>0` fail-fast；**(b)** `_build_contract_specs()` 之后短仓/期货告警 | A4 | B11/B14/B16 | ✅ engine_v2.py L254-275（三条校验）/ L333-335（短仓告警）；B11/B14/B16 全绿 |
| A6 | `_execute_rebalance`：只迁移 L1398-1406 + L1413-1425 至 overlay 前（截断块 L1407-1412 原位）；sizing 块按 IMPL §2.6 逐字（`finite_prices` / `× TRADING_DAYS` / `none` 也调用 / 四类告警） | A1/A2/A4 | 读码 + B5-B10/B13 + `git diff` | ✅ engine_v2.py L1377-1400（迁移段）/ L1425-1482（sizing 块）；B5-B10/B13 全绿 |
| A7 | `core/sizing.py` 零 diff；`core/risk_overlay.py` 零 diff；`core/engine_v2.py` 改动仅限 imports + setup 两段 + 迁移段 + sizing 块 | A6 | `git diff --stat` | ✅ `git diff --stat core/sizing.py core/risk_overlay.py` 输出为空；engine_v2 `+102/−24`，删除行逐行核对 = 迁移段 22 行 + 旧 import 1 行 |

---

## 2. B 组：测试（16 项，`tests/test_p051a_sizing_wiring.py`）

| ID | 验收项（DoD） | DoR | 证据出口 | 实测 |
|----|---------------|-----|----------|------|
| B1 | `estimate_volatility` 闭式：`[0.01,-0.01]` lookback=2 → **0.2244994**；`[0.01,-0.01,0.02,-0.02]` lookback=4 → **0.2898271**（abs=1e-6） | A2 | pytest | ✅ `test_b1_volatility_closed_form`（实测 0.2244994 / 0.2898275） |
| B2 | **F-I2 钉死**：`[0.01,-0.01,0.03,0.01]` lookback=2 年化 → `[nan, 0.2244994432, 0.4489988864, 0.2244994432]`；未年化 → `[nan, 0.0141421356, 0.0282842712, 0.0141421356]`；`[0.01,nan,0.02,0.01]` → `[nan,nan,nan,0.1122497216]`（abs=1e-9） | A2 | pytest | ✅ `test_b2_volatility_nan_and_unannualized` |
| B3 | `atr` period=3 五 bar → `[nan, nan, 0.9, 0.8333333, 0.8222222]`（abs=1e-7） | A3 | pytest | ✅ `test_b3_atr_standard_wilder` |
| B4 | 形状不一致 / `period=0` / Series 与 DataFrame 混用 → `ValueError`；`period=1` → `out[0]=H[0]−L[0]` | A3 | pytest | ✅ `test_b4_atr_invalid_inputs` |
| B5 | **F-I1 钉死**：同 fixture `sizing=None` vs `SizingConfig(method="none")` 全默认 → `_last_targets` 逐值相同、无 sizing 告警（**不得依赖 git 状态**） | A6 | pytest | ✅ `test_b5_sizing_none_is_zero_behavior`（4 日逐值相等；`core.engine_v2` 无 sizing 日志） |
| B6 | `SizingConfig(method="none", max_weight=0.2)`：输入 {A:0.3, B:0.2} → {A:0.2, B:0.2}，和 0.4 ≤ 1 不缩放 | A6 | pytest | ✅ `test_b6_none_method_applies_constraints`（qty 比 0.39-0.41、单标的权重 ≤0.2） |
| B7 | **F-I5 钉死**：`vol_target` + `vol_lookback=2`，取首个 `date_index>=2` 的再平衡日；`cov_method="sample"`；Σ 独立重算 ×252 → `scale`，断言 `0.4<scale<0.7` + `qty比≈scale` | A6 | pytest | ✅ `test_b7_vol_target_annualized_scale`（实测 scale≈0.6299，qty 比 rel<2e-3） |
| B8 | `vol_lookback=60` 于 6 日 fixture → 权重原样 + caplog 含 `insufficient_history` | A6 | pytest | ✅ `test_b8_insufficient_history_skips` |
| B9 | `_returns_matrix` 全 0 → 权重原样 + caplog 含 `zero_vol` | A6 | pytest | ✅ `test_b9_zero_vol_keeps_weights` |
| B10 | **F-I3 钉死（Step 9 改法）**：`allow_negative_stock_positions=True` + `method="none", max_weight=0.2` → `_last_targets` 与基线**完全相同**（sizing 整段跳过） | A6 | pytest | ✅ `test_b10_short_path_skips_sizing`（ratio==1） |
| B11 | `method="kelly"` / `"risk_parity"` → `setup()` `ValueError`，message 含 `P-051a` | A5 | pytest | ✅ `test_b11_method_subset_fail_fast`（两方法逐案） |
| B12 | `SizingState(100.0, 100.0, 1)` → `asdict` → `json.dumps/loads` → 重构相等 | 无 | pytest | ✅ `test_b12_sizing_state_json_roundtrip` |
| B13 | **F-I4 钉死**：monkeypatch `_exec_price` 注入 NaN → 整日跳过 + caplog 含 `sizing_skipped_bad_price` | A6 | pytest | ✅ `test_b13_nan_price_skips_sizing` |
| B14 | sizing.vol_target + `RiskOverlayConfig(enabled=True, target_vol=0.2)` → `setup()` warning 计数 == 1 | A5 | pytest | ✅ `test_b14_dual_vol_warning_once`（命中 1 条） |
| B15 | `-k golden` = **22**；`tests/golden/**` 无新增目录 | A6 | pytest + git | ✅ `22 passed, 1018 deselected`；`test_b15_no_new_reference_dir`（**Step 9 改名**：原名含 "golden" 会污染 `-k` 选择，曾误得 23） |
| B16 | `SizingConfig(method="none", min_weight=0.1)` → `setup()` `ValueError`，message 含 `P-051a` 与 `F-D1` | A5 | pytest | ✅ `test_b16_min_weight_fail_fast` |

---

## 3. C 组：门禁（4 项）

| ID | 门禁 | 命令 | 目标 | 实测 |
|----|------|------|------|------|
| C1 | pytest 全量 | `.\.venv\Scripts\python.exe -m pytest -q`（`$env:MPLBACKEND='Agg'`） | **1040 passed** | ✅ `1040 passed, 238 warnings in 107.26s` |
| C2 | golden | `.\.venv\Scripts\python.exe -m pytest -q -k golden` | **22 passed** | ✅ `22 passed, 1018 deselected in 15.32s` |
| C3 | mypy | `-m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples` | **113 files，0 error** | ✅ `Success: no issues found in 113 source files` |
| C4 | black | `-m black --check core tests` | **157 files would be left unchanged** | ✅ `157 files would be left unchanged`（engine_v2 首轮需格式化，已 `black` 应用后复检通过） |

---

## 4. I 组：不变式（13 项）

| ID | 不变式 | 证据出口 | 实测 |
|----|--------|----------|------|
| I1 | `sizing=None` ⇒ 22 条 golden 逐值不变 | B15 / C2 | ✅ C2 = 22 passed，零重录 |
| I2 | 短仓/期货 ⇒ sizing 零作用 | B10 + A5(b) | ✅ B10 ratio==1；A5(b) L333-335 |
| I3 | sizing 后 `sum(weights) <= 1 + 1e-12` | B6/B7 | ✅ B6 单标的 ≤0.2 且 qty 比 <0.41；B7 qty 比 ≈ scale |
| I4 | 引擎 Σ 已年化（`×252`），与 `target_vol` 同口径 | B7 | ✅ B7 区间断言 0.4<scale<0.7（漏年化则被夹 1.0） |
| I5 | 历史不足 / 无有限价格 ⇒ 跳过 + 告警，不抛异常、权重原样 | B8/B13 | ✅ B8/B13 |
| I6 | `σ_p==0` ⇒ `scale=1.0` + `zero_vol` | B9 | ✅ B9 |
| I7 | 双 vol 并存 ⇒ 乘积 + 一次 warning | B14 | ✅ B14 命中 1 条 |
| I8 | `kelly`/`risk_parity` ⇒ `setup()` `ValueError` | B11 | ✅ B11 |
| I9 | `core/volatility.py` 无 I/O / logger / 随机 / 全局写 | grep `open(\|requests\.\|logging` + AST | ✅ grep 仅命中 1 处 docstring 声明（L6），**代码零命中**；imports 仅 numpy/pandas |
| I10 | `SizingState` JSON 往返相等 | B12 | ✅ B12 |
| I11 | golden 仍 22；无新 golden 目录 | B15/C2 | ✅ B15 + C2 |
| I12 | `core/sizing.py` 零 diff | `git diff --stat core/sizing.py` 为空 | ✅ 输出为空 |
| I13 | `min_weight>0` ⇒ `setup()` `ValueError` | B16 | ✅ B16 |

---

## 5. Step 9 执行顺序（TDD）

1. **先落 2 个红态模块骨架**：`core/volatility.py`（函数体 `raise NotImplementedError`）+ `tests/test_p051a_sizing_wiring.py` 的 B1-B4 → 跑红；
2. 实现 `volatility.py` → B1-B4 转绿（B3 闭式 0.9/0.8333333/0.8222222 逐个核对）；
3. `config.py` 字段 + `engine_v2.py` imports/setup 两段 → B11/B14/B16 转绿；
4. `engine_v2.py` 迁移段 + sizing 块 → B5-B10/B13 转绿（B5 必须 `sizing=None` 与 `method="none"` 对照，禁止录 golden）；
5. 全量门禁 C1-C4 + A7 零 diff 核验；
6. 失败即停：任何一项红灯不得进入 Step 8。

**命令**：

```powershell
$env:MPLBACKEND='Agg'
.\.venv\Scripts\python.exe -m pytest tests/test_p051a_sizing_wiring.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q -k golden
.\.venv\Scripts\python.exe -m mypy --explicit-package-bases --check-untyped-defs core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy web factor_library tools examples
.\.venv\Scripts\python.exe -m black --check core tests
git diff --stat core/sizing.py core/risk_overlay.py
```

---

## 6. Step 10 退出条件

| # | 条件 |
|---|------|
| 1 | A7/B16/C4/I13 全部 `✅`；C1 = 1040、C2 = 22、C3 = 113/0、C4 = 157 |
| 2 | `git status` 仅含：`core/volatility.py`（新）、`core/config.py`、`core/engine_v2.py`、`tests/test_p051a_sizing_wiring.py`（新）、四份 docs、`docs/PROGRESS.md` |
| 3 | PROGRESS §1.4：P-051a 行状态回填；`O-P051a-2` 行回填（仍 pending）；新增 `O-P051a-3`（窗口口径，P-051b 对齐） |
| 4 | 四文档 `状态` 行标注「批次关闭 + CI run id」；**用户明确授权后**才 commit/push |
| 5 | CI 四 job（lock-check + 3.10/3.11/3.12）全绿 |

---

## 7. 计数口径与规则

- 所有计数以实际收集数为准；`-k golden` 通过数须等于 22（**零重录**）；
- B 组 16 项与 DESIGN §4 / IMPL §3 一一对应，F-I1..F-I5 的钉死值直接采用 IMPL §9.2（Step 7 重算后的数值）；
- 实测列禁止预填；Step 9 每完成一项立即回填 `✅ + 证据`（测试名 / 文件行 / 命令输出摘要）。

---

## 8. Step 8 一致性检查记录（检查方 GLM-5.3-Flash，2026-11-20）

> **检查身份**: GLM-5.3-Flash（≠ Step 5/7 作者 DeepSeek-V4.1-Flash）。四文档 ↔ 代码锚点 ↔ 计数口径三方交叉核对，全部锚点于 HEAD `95a6f6c` 实读终验。

### 8.1 锚点终验（全部实读）

| 锚点 | 文档声称 | 终验 | 结果 |
|------|----------|------|------|
| 迁移段起点 `try:` | DESIGN D6「L1399」/ IMPL §2.5「L1398」 | **L1398**（L1397 注释、L1398 `try:`、L1399 prices、L1404-1406 positions/stock_short/allow_short、L1407-1412 截断块、L1413-1417+L1418-1425、L1426 起 build） | **DESIGN 差一行 → F-C3 已修** |
| setup 插入点 | 「L250 之后、t0 之前」 | L244-250 校验块、L251 `t0 = time.perf_counter()` | ✅ |
| `_build_contract_specs()` | 「L310 之后」 | **L310** | ✅ |
| sizing.py 裁剪抬升 | 「L322-324」 | `elif weight < config.min_weight: base[code] = config.min_weight` | ✅（F-D1 引用成立） |
| sizing.py min_size drop | 「L336-339」 | `dropped_min_size → base[code] = 0.0` | ✅（F-D2 引用成立） |
| config.py 插入点 | 「L424 `risk_overlay` 之后」 | L423-424 `risk_overlay` 字段 | ✅ |
| B14 字段名 | `RiskOverlayConfig(enabled=True, target_vol=0.2)` | risk_overlay.py L51-52 `enabled` / `target_vol` | ✅ |
| engine assert 风格 | IMPL §2.6 `assert returns_matrix is not None` | engine_v2.py 已有 6 处 assert（L363/436/501/573/727/728） | ✅ 合惯例 |

### 8.2 发现与处置（0 P1 / 0 P2 / 5 P3，全部已修/已钉死）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-C3** | P3（危害最高） | DESIGN D6 两处迁移段行号写「L1399-1406」「L1399-1425」，漏掉 L1398 `try:` 行——照此实施会**语法错误** | DESIGN D6 两处已订正为 **L1398**；唯一真值源 = IMPL §2.5 |
| F-C1 | P3 | IMPL §3.1 `_make_engine(*, sizing=None, allow_short=False)` 的 `allow_short` 形参未接线 cfg，属死参数 | 已删除该形参 + 加 F-C1 注释；B10 按 F-I3 自建 cfg + `set_signal` |
| F-C2 | P3 | IMPL §2.2(b) 注释模板「18 条 golden 不受影响」为 P-048 旧数（当前 22），照抄会把过时数字写进代码注释 | 已改「22 条」 |
| F-C4 | P3 | IMPL §3.2 B2 / §3.3 B5/B7/B10/B13 五行保留 Step 6 前旧表述，与 §9.2 钉死值双口径并存 | 五行均加「→ 实施以 §9.2 F-Ix 钉死值为准」指针（保留复审时点原貌，消除歧义）；DESIGN §4 B5 同加指针 |
| F-C5 | P3 | DESIGN D5 与 IMPL §2.4 的 fail-fast message 文本微差（「抬升」vs「抬升至 min_weight」） | 指定 IMPL §2.4 为唯一真值源；CHECKLIST B16 断言只查 `P-051a`/`F-D1` 子串，不受影响 |

### 8.3 计数矩阵三文档核对（全部一致）

| 口径 | DESIGN | IMPL | CHECKLIST | 一致 |
|------|--------|------|-----------|------|
| pytest | 1024+16 | 1024+16=1040 | **1040** | ✅ |
| golden | 22 | 22 | **22（零重录）** | ✅ |
| mypy | 113 files 0 | 113 files 0 | **113 files，0 error** | ✅ |
| black | 157 | 157 | **157** | ✅ |
| tests / core 计数 | — | — | 111→112 / 44→45 | ✅ |
| B 组 16 / I 组 13 / A 组 7 | §4/§3/§5.1 | §3/§4/§1 | §2/§4/§1 | ✅ |
| B3 闭式 | 0.9/0.8333333/0.8222222 | 同 | 同 | ✅ |
| B7 scale | 公式（无数值） | **0.4454353901** | **0.4454353901** | ✅ |
| B2 数值 | 原始 std 公式 | §9.2 F-I2 重算值 | 重算值 | ✅ |

### 8.4 闭环链核对（全部成立）

- Step 2 `F-R1..F-R6` → DESIGN §0 全收敛；Step 4 `F-D1..F-D5` → DESIGN §0.1+正文全收敛；Step 6 `F-I1..F-I5` → IMPL §9.2 → CHECKLIST B 组钉死值全落位；
- 观察项：`O-P051a-2`（PROGRESS L196，pending）/ `O-P051a-3`（DESIGN D2 注记，CHECKLIST §6.3 待建行）/ `O-P051a-1`（RESEARCH，归 P-051c）三链一致；
- 判档 T1、基线 `95a6f6c`、四文档命名、Step 9 红态顺序、Step 10 退出条件五条——四文档交叉一致。

### 8.5 结论

**一致性通过**。5 项 P3 全部当场修复/钉死，无遗留；实施唯一真值源链 = **IMPL §2 代码 → IMPL §9.2 钉死值 → CHECKLIST A/B/C/I 实测列**。可进 Step 9 TDD。

---

## 9. Step 9 实施记录（2026-11-20）

### 9.1 落地清单

| 文件 | 内容 |
|------|------|
| `core/volatility.py`（新，106 行） | `TRADING_DAYS` / `estimate_volatility` / `atr` |
| `core/config.py` | TYPE_CHECKING `SizingConfig`（L17）+ `sizing` 字段（L428） |
| `core/engine_v2.py`（+102/−24） | imports；`setup()` L254-275 + L333-335；`_execute_rebalance` 迁移段 L1377-1400 + sizing 块 L1425-1482 |
| `tests/test_p051a_sizing_wiring.py`（新，332 行） | B1-B16 = 16 用例 |

### 9.2 实施中发现（3 项，全部为规格偏差，实现本体无缺陷）

| ID | 发现 | 处置 |
|----|------|------|
| **F-S9-1** | B15 用例名 `test_b15_no_new_golden_dir` 含 "golden"，被 `-k golden` 选中 → 误报 **23**（基线 22） | 改名 `test_b15_no_new_reference_dir`，`-k golden` 回落 **22** |
| **F-S9-2** | F-I3 预设的「`set_signal` 注入负权重」不可行：`set_signal` 明确拒绝负权重（P-050 约束，改架构超出本批） | B10 改为 `allow_negative_stock_positions=True` + `method="none", max_weight=0.2`，断言与基线**逐值相同**（max_weight 未生效 = sizing 整段被跳过） |
| **F-S9-3** | 默认 `cov_method="ledoit_wolf"` 在 2 行样本上收缩，闭式不可手算；`_cov_sample` 为 ddof=0 口径（非 IMPL 初稿假设的 ddof=1） | B7 显式 `cov_method="sample"`；测试内用 `estimate_cov(..., method="sample")` 独立重算 Σ 后 ×252，断言 `0.4<scale<0.7` 与 `qty比≈scale`（漏年化/漏 Σ 时 scale 被夹 1.0 必失败）；IMPL §3.3 B7 闭式已同步改写 |

> F-I2 数值同步校准：年化 `0.2244994432` / `0.4489988864`，NaN 末位 `0.1122497216`（原稿 7 位小数在 `abs=1e-9` 下不成立）；IMPL §9.2 已改。

### 9.3 门禁实测（`$env:MPLBACKEND='Agg'`）

| 门禁 | 结果 |
|------|------|
| 新增用例 | **16 passed**（2.85s） |
| 全量 | **1040 passed**（107.26s） |
| golden | **22 passed, 1018 deselected**（零重录） |
| mypy | **113 source files，0 issues** |
| black | **157 files would be left unchanged**（engine_v2 首轮需格式化，已应用后复检） |
| 零 diff 边界 | `core/sizing.py` / `core/risk_overlay.py` diff 为空；engine_v2 删除行逐行核对 = 迁移段 22 行 + 旧 import |

### 9.4 与目标的偏差

| 口径 | 目标 | 实测 | 偏差 |
|------|------|------|------|
| pytest | 1040 | 1040 | 0 |
| golden | 22 | 22 | 0 |
| mypy | 113·0 | 113·0 | 0 |
| black | 157 | 157 | 0 |

**Step 9 通过**。待 Step 10：PROGRESS 回填（P-051a 状态 + `O-P051a-3` 建行 + `O-P051a-2` 仍 pending）+ 用户授权后提交 + CI 四 job。
