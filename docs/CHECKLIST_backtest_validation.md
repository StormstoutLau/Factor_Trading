# P-011 回测准确性验证、学术规范与基准比较 · 审查验收清单

> **文档编号**: CHECKLIST_backtest_validation
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: **Step 1-10 全部通过；Step 11 审计总结完成**（2026-11-10；Step 9 实测 **609 passed / black 167 / mypy 0（36 files）/ 盲区 4 errors 2 files / 68 测试文件**，B3 Δ 表 + `change_report residual 0.0` 双证，远端 CI run `42768525717` 三 job 全绿；Step 10 ADD 审计全过——CHECKLIST §9：Phase 0-4 全过、**P1=0 / P2=1 F-A1 已修复 `a754a2d`** / P3=2 已回写、`replay: 10 rows OK`、实测列 **76/76**、终态远端 run `42771058634` 三 job success；Step 11 交叉总结见 [AUDIT_SUMMARY_backtest_validation.md](AUDIT_SUMMARY_backtest_validation.md)，无新发现；RULE-5 异构复审留待独立会话）
> **上游**: [DESIGN_backtest_validation.md](DESIGN_backtest_validation.md)（Step 4 通过；D1-D9 / 不变式 I1-I10；F-R1~F-R4 已回写；Step 9 回写 F-S9-2~F-S9-4） · [IMPL_backtest_validation.md](IMPL_backtest_validation.md)（Step 6 通过；T-0~T-14 / V1-V16；F-I1~F-I5 已回写；**§9 Step 9 实施记录已追加**）
> **填写规则**: 「实测」列只写 Step 9 实施后的实测证据（RULE-1，禁止预填）；无证据只能标 `[未在 CI 覆盖]` / `[未入仓-不可重放]` / `[未取证]`
> **解释器**: `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10）；测试命令加 `MPLBACKEND=Agg`
> **门禁**: session `factorv3-p011-backtest-validation-20261110`；链 `probe → unit-tests → black-check → mypy-check` + replay
> **基线时点**: 本仓 @ `dc71c1a`；RED 读数 **550 passed / black 153 unchanged / mypy 0 / 盲区 4 errors 2 files / 550 collected / 60 测试文件 / 7 pkl**
> **目标末态（实测）**: **609 passed**（550 + 59，逐文件 11/9/8/5/9/4/9/4）/ black **167** / mypy 0（36 files）/ 盲区 **4 errors 2 files**（不劣化）/ **68** 测试文件。原预测 602/52 的偏差来源见 [IMPL §9.2](IMPL_backtest_validation.md)（参数化展开 + F-S9-3 补测），**无为凑数增删测试**

---

## 1. A 不变量体系（B1：T-1/T-3，零数值）

> **DoR**: DESIGN §4.1 签名 + IMPL T-1 已定义；`get_trades`/`get_execution_stats` 已由 Step 6 E1 核实。**DoD**: 每条不变量有正例 + 反例（篡改必报）；引擎接入有结果字段证据。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | 实施前复录 R1-R10 与 IMPL §3.1 一致：550 passed / black 153 unchanged / mypy 0 / 盲区 4 errors 2 files / 550 collected / 60 测试文件 / 7 pkl / R6 指标探针 / `git status` 仅 docs | 逐命令输出抄录 | IMPL §3.1 | ✅ 复录一致：550 / 153 / 0 / 4 errors 2 files / 550 / 60 / `data/test_ashare` 7 pkl；R6 探针 V2 mdd=+0.19、V3 mdd=−0.1；R10 仅 docs |
| A2 | `core/invariants.py` 存在：`InvariantMode` / `Violation` / `InvariantReport`（含 `ok`/`to_dict`）/ `InvariantViolationError` / I1-I7 七个 `check_*` / `check_all` | `Grep '^def check_\|^class ' core/invariants.py` 逐项命中 | DESIGN §4.1 / IMPL T-1 | ✅ 逐项命中：`InvariantMode` / `InvariantViolationError` / `Violation` / `InvariantReport` / `check_nav_identity` / `check_position_identity` / `check_cost_identity` / `check_return_identity` / `check_v3_nav_identity` / `check_v3_static_positions` / `check_v3_cost_identity` / `check_all` |
| A3 | I1 NAV 恒等：正例 0 违规；篡改 `total_value` 1 元 → 1 条 I1 违规（code/date 正确） | `pytest tests/test_invariants.py -k nav_identity -q` = 2 passed | T-3 #1/#2 / DESIGN I1 | ✅ `2 passed, 9 deselected` |
| A4 | I2 持仓恒等：买入 100/卖出 40 → 持仓 60 → 0 违规；无 trade 直接改仓位 → I2 违规 | `pytest ... -k position_identity -q` = 2 passed | T-3 #3/#4 / DESIGN I2 | ✅ `3 passed, 8 deselected`（新增 `..._skips_ambiguous_same_day_snapshots`，F-S9-3） |
| A5 | I3 成本恒等：2 笔成本合计 == `stats["total_cost"]` → 0 违规；`cost<0` → I3 违规；`net_amount` 买卖符号正确 | `pytest ... -k cost_identity -q` = 2 passed | T-3 #5/#6 / DESIGN I3 | ✅ `2 passed, 9 deselected` |
| A6 | I4 收益恒等：手工递推一致 → 0 违规；篡改 `daily_return` → I4 违规；首日基准 = `initial_capital` | `pytest ... -k return_identity -q` = 2 passed | T-3 #7/#8 / DESIGN I4 | ✅ `2 passed, 9 deselected` |
| A7 | `check_all` `report` 模式聚合违规不抛、`checked` 计数正确；`raise` 模式抛 `InvariantViolationError`（首条） | `pytest ... -k check_all -q` = 1 passed + 读码 | T-3 #9 / IMPL T-1 要点 6 | ✅ `1 passed, 10 deselected`；读码：`mode=="raise"` 且非 ok 时抛 `violations[0]` |
| A8 | 引擎接入：`BacktestConfig.invariant_mode` 默认 `"report"`；小样本 V2 结果含 `additional_info["invariant_report"]` 且 `ok=True`；`"off"` 时该键不存在（零计算） | `pytest ... -k engine_emits_invariant_report -q` + 读码 | T-3 #10 / IMPL T-1 接线 | ✅ `1 passed, 608 deselected`；读码默认值 `"report"`、`"off"` 分支整体跳过 |

---

## 2. B 参考差分与跨引擎等价（B1/B2：T-2~T-6，零数值）

> **DoR**: `_reference_impl` 四函数已定义；T-5 夹具数字已按 F-D2 构造（整手无损）。**DoD**: 纯函数**比特一致**（njit 路径；`py_func` 允许 1 ulp，F-S9-2）；事件等价含阴性对照；文档不越界声明。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `tests/_reference_impl.py` 存在 4 函数（`ref_rebalance_kernel` / `ref_build_target_positions` / `ref_calculate_cost` / `ref_v3_nav`），且**不 import** `core.engine_v3_vector` / `core.target_positions` / `core.execution` 的实现函数 | `Grep 'from core.engine_v3_vector\|from core.target_positions\|from core.execution' tests/_reference_impl.py` = 0 | IMPL T-2 要点 5 | ✅ `Grep = 0`；4 函数齐备 |
| B2 | V3 `_rebalance_kernel` 与参考在 32 组参数网格上**比特一致**：仓位 `np.array_equal`、现金 `==` | `pytest tests/test_reference_diff.py -k matches_reference -q` = 1 passed | T-3 #1 / DESIGN D3 | ✅ `4 passed, 5 deselected`（32 组网格拆 4 个用例组）；JIT 活跃时现金比特一致，CI 无 numba / 禁用 JIT 时退化 `rtol=1e-12`（F-S9-2 远端补正，`NUMBA_DISABLE_JIT=1` 复跑 9 passed） |
| B3 | numba 路径与 `py_func` 回退路径同参考对拍（`getattr(fn,"py_func",fn)`；无 numba 环境退化为同一函数仍通过） | `pytest ... -k python_fallback -q` = 1 passed | T-3 #2 / ADR-007 | ✅ `1 passed, 8 deselected`；`py_func` 末位 1 ulp → `rtol=1e-12`（F-S9-2） |
| B4 | 内核边界：全 NaN 信号 → 持仓/现金原样返回；零价 → 不可建仓但可清仓 | `pytest ... -k 'all_nan_signal or zero_price' -q` = 2 passed | T-3 #3/#4 | ✅ `2 passed, 7 deselected` |
| B5 | `build_target_positions` 与参考一致：覆盖 `round_lot=True/False`、`value_buffer=0.985`、权重≤0 清仓、价格缺失维持 四分支 | `pytest ... -k target_positions -q` = 2 passed | T-3 #5 / T-4 #1/#2 | ✅ `6 passed`（参考差分 1 + V2 组件 5：四分支 + 整手边界参数化） |
| B6 | `_calculate_cost` 与参考一致：佣金下限绑定（`amount*rate<5` → 5）、印花税仅卖出、滑点全向 | `pytest tests/test_v2_components.py -k cost -q` = 2 passed | T-4 #3/#4 | ✅ `2 passed, 6 deselected` |
| B7 | 单笔成交字段：`amount == qty*price`、`cost == 参考`、`net_amount` 买卖符号正确 | `pytest ... -k execute_order_trade_fields -q` = 1 passed | T-4 #5 | ✅ `1 passed, 7 deselected` |
| B8 | **事件级等价五断言**：V2 `[492500,197000]` / V3 `[500000,200000]` / NAV 三日均 `10_000_000`（`rtol=0`）/ cash 差 `150_000` / 阴性对照 `[7500,3000]` | `pytest tests/test_cross_engine_equivalence.py -q` = 5 passed | T-5 / DESIGN §4.5 | ✅ `5 passed`；阴性对照实测 `[7_500.0, 3_000.0]`（F-S9-4 修正原 3_750 笔误） |
| B9 | 蜕变属性：同输入两次完全一致（V2 快照 + V3 pv）；价格×2（零费用）→ 仓位 /2、现金不变、NAV 不变 | `pytest tests/test_reference_diff.py -k metamorphic -q` = 2 passed | T-3 #8/#9 / A13 | ✅ `2 passed, 7 deselected` |
| B10 | `docs/BACKTEST_CALIBER_MAPPING.md` 五章齐备（映射理由 / 五框架口径表 / 本仓声明差异 / 等价测试与残差 / 不声称一致）；无「与 Qlib 一致」类越界声明 | 文档读回 + `Grep '一致'` 人工判定 | T-6 / RESEARCH §11.4 | ✅ 5 章齐备（§1 映射理由 / §2 口径矩阵 / §3 声明差异 / §4 等价测试与残差 / §5 声明边界）；`Grep '与 Qlib 一致\|完全一致'` = 0 |

---

## 3. C 报告口径统一（B3：T-7~T-10，**行为批次**）

> **DoR**: 分母 `252/N` 与回撤量级约定已由 Step 4 E2 实证；消费方清单已盘点（F-R4）。**DoD**: V2/V3 指标 Δ 逐字段实测；NAV 与六层 dump 零变化；唯一需更新的既有断言已披露。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `core/metrics.py` 公式与 DESIGN §4.2 逐项一致：`returns=np.diff/pv[:-1]`、`cumulative=pv/pv0`（含锚点 1.0）、`annual_return**(252/N)`、`vol=std(ddof=0)*sqrt(252)`、`sharpe=(annual-rf)/vol`、`mdd=max((cummax-cum)/cummax)` | 读码 + `test_metrics_single_source` 断言 | T-7 / DESIGN §4.2 | ✅ 读码逐项一致；`test_metrics_single_source` 9 passed |
| C2 | `compute_metrics(len(pv)<2)` → `ValueError`；`sharpe_ratio(vol<=0)` → `0.0`；无其他静默兜底 | `pytest ... -k 'empty_and_single' -q` = 1 passed + 读码 | T-7 边界 / T-10 #6 | ✅ `2 passed, 7 deselected`（empty / single 参数化）；读码：`vol<=0` 返回 0.0 |
| C3 | V2 `analytics` 委托：5 个口径字段（total/annual/vol/sharpe/mdd）取自 `compute_metrics`；新增 `risk_free_rate` 键；`win_rate`/`sortino`/`calmar`/`drawdown_duration` 保留原口径 | 读码 + `test_compute_metrics_matches_analytics` | T-8 / IMPL T-8 要点 2 | ✅ `test_compute_metrics_matches_analytics` 绿；读码：5 字段委托 + `risk_free_rate` 键，其余键保留 |
| C4 | **V2 指标 Δ**：`total_return`/`annual_return`/`max_drawdown` 不变（≤1e-12）；`annual_volatility` 按 N−1 样本变化、`sharpe_ratio` 随 vol 变化——逐字段实测 Δ 已列 | R7 before/after + `%TEMP%\p011_b3_delta.py` 输出 | T-8 / DESIGN §7.3 | ✅ 31×60 夹具：`annual_volatility 0.08122845→0.08189931`（+6.709e-4）、`sharpe −1.45492→−1.44300`；`total_return` 1 ulp（6.9e-18）；`annual_return`/`max_drawdown` Δ=0（IMPL §9.3） |
| C5 | V3 `_metrics_kernel(pv, risk_free_rate=0.03)` 新签名可被 numba 编译；单参旧调用不破 | `pytest` 全量 + E2 探针复核 | T-9 / IMPL §2.2（F-S8-2 修正锚点） | ✅ 全量 609 passed（含 numba 内核用例）；Step 6 E2 已证默认参数编译 OK |
| C6 | V3 回撤补初始锚点：`pv=[100,90,81]` → kernel `mdd == -0.19`（改前 -0.1），且仍 ∈[-1,0] | `pytest ... -k drawdown_includes_initial_anchor -q` = 1 passed | T-9 / T-10 #4 / F-R1 | ✅ `1 passed, 608 deselected`；kernel `mdd=−0.19`，范围断言 `-1<=mdd<=0` 保持 |
| C7 | V3 results 层量级：`max_drawdown == 0.19`（正值）、`risk_free_rate` 键存在；kernel 内部保持负值原语 | 读码 + 断言 | T-9 要点 2 | ✅ 读码：`_generate_results` 输出 `-float(mdd)` + `risk_free_rate`；`test_v3_engine_integration` 断言 `0<=mdd<=1` 通过 |
| C8 | **I9 三口径一致**：同一 pv 经 `compute_metrics` / `analytics` / V3 报告层，5 指标 `rtol=1e-12`；`trading_days == len(pv)` | `pytest tests/test_metrics_single_source.py -q` = 8 passed | T-10 / DESIGN I9 | ✅ `9 passed`（8 函数，`empty_and_single` 参数化 2） |
| C9 | **B3 归因**：`change_report.json` 六层全零、`residual == 0`、`attribution_complete == true`（证明未触碰执行路径）；NAV 与 trades 逐值不变 | before/after 两目录 + `scripts/change_report.py` 输出 | T-10 / DESIGN §7.3 | ✅ `residual 0.0` / `attribution_complete true` / L1-L6 `changed` 全 0；NAV 与 trades 逐值不变 |
| C10 | 既有断言更新已披露：`test_v3_engine_integration.py:217` 改 `0<=mdd<=1`；`test_numba_jit_performance.py:178/:280` 范围断言**不变**且仍通过 | `pytest tests/test_v3_engine_integration.py tests/test_numba_jit_performance.py -q` 全绿 + `git diff` 读码 | T-9 要点 4 / F-R4 | ✅ 两文件全绿；`:217` 为唯一更新断言（`0<=mdd<=1`），`:178` 保持 `-1<=mdd<=0`、`:280` 引擎级改 `0<=mdd<=1`（负值原语→报告量级，已披露） |

---

## 4. D 偏差声明（B4：T-11，零数值）

> **DoR**: DESIGN §4.3 字段结构已定；能力常量与 `universe_report` 来源已核实。**DoD**: 每个字段由状态/常量派生，缺省 false，禁止写入未计算的 True。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | `core/validation.py` 存在：`SCHEMA_VERSION` + 能力常量 5 项（`PIT_SUPPORTED`/`MULTIPLE_TESTING_SUPPORTED`/`BENCHMARK_SUPPORTED`/`WALK_FORWARD_AVAILABLE`）+ `build_validation_declaration` | `Grep '^[A-Z_]+ = \|^def build_validation_declaration' core/validation.py` 命中 | DESIGN §4.3 / T-11 | ✅ 命中 `SCHEMA_VERSION` / 4 能力常量 / `KNOWN_LIMITATIONS` / `build_validation_declaration` |
| D2 | 声明字段齐备：`multiple_testing{corrected,n_trials}` / `survivorship{corrected,source}` / `pit_data` / `benchmark{configured,comparable}` / `out_of_sample{walk_forward_available,used_in_this_run}` / `risk_free_rate` / `sharpe_method` / `execution_timing` / `known_limitations`（5 条） | `pytest tests/test_validation_declaration.py -q` = 4 passed + JSON 读回 | T-11 要点 1-4 | ✅ `4 passed`；`test_declaration_present` 逐键断言 |
| D3 | 字段派生正确：`survivorship.corrected == (report["survivorship"]=="corrected")`；`benchmark.configured == (cfg.benchmark is not None)`；`risk_free_rate == cfg.risk_free_rate`；`execution_timing == "next_open"`；无来源的字段一律 false/null | 单测参数化（4 组 universe_report/cfg） | T-11 / DESIGN §4.3 | ✅ `test_survivorship_derived_from_universe_report` + `test_rf_and_benchmark_passed_through` + `test_capability_flags_are_false` 全绿 |
| D4 | 接线：V2 结果 `additional_info["validation_declaration"]` 存在且 JSON 可序列化 | 小样本运行 + `json.dumps` 断言 | T-11 要点 5 | ✅ `test_declaration_present`（小样本运行取 `additional_info`，`json.dumps` 成功） |
| D5 | `known_limitations` 5 条与能力常量/false 字段一一对应，无「未实现却声称」的条目 | 文档-代码双向读码 | T-11 要点 4 | ✅ 5 条逐项对应：无多重检验校正 / 无 PIT 版本轴 / benchmark 占位 / V2 整数股 + 0.985 / V3 筛选器定位 |

---

## 5. E 运行清单（B5：T-12，零数值）

> **DoR**: 序列化白名单与指纹定义已定；`__api_version__`/`RULESET_VERSION` 取值已核实。**DoD**: 字段齐备、哈希可复算、指纹确定、config 键集无损。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | `output_dir/manifest.json` 写入成功；`write_manifest=False` 时**不写** | `pytest tests/test_manifest.py -k written -q` = 1 passed + 文件存在性断言 | T-12 要点 8 | ✅ `1 passed`（`test_manifest_written`）+ `test_write_manifest_flag_disables` 绿 |
| E2 | 字段齐备：`schema_version`/`run_id`/`input_fingerprint`/`git{commit,dirty}`/`config`/`data{dir,files[]}`/`environment`/`caliber`/`timestamps`/`outputs` | JSON 读回逐键断言 | DESIGN §5.2 / T-12 | ✅ `test_manifest_fields` 逐键断言（10 组） |
| E3 | 数据 `sha256` 与 `hashlib` 独立复算一致；缺失文件 `{exists:false, sha256:null}` 且不抛 | 单测 `hashlib.sha256(f.read_bytes())` 对照 | T-12 要点 2 | ✅ `test_sha256_matches_hashlib` + `test_missing_file_marked_absent` 绿 |
| E4 | 指纹确定性：同 `git.commit`/数据/配置两次 `build_manifest` → `input_fingerprint` 相同；`run_id` 可不同；指纹不含时间戳/uuid | 两次调用 + 正则断言 | T-12 要点 4 | ✅ `test_fingerprint_stable` 绿；指纹输入仅 git/数据 sha256/配置 |
| E5 | **I8**：`manifest["config"]` 键集 == `BacktestConfig` dataclass 顶层字段集（无静默丢字段） | `dataclasses.fields` 集合相等断言 | DESIGN I8 / T-12 要点 9 | ✅ `test_config_keys_match_dataclass` 绿 |
| E6 | 序列化：`Path`→str、`Enum`→value、dataclass 递归、callable→`"<callable>"`、未知类型不抛；`json.dumps(manifest)` 成功 | 单测 + 读码 | T-12 要点 1 | ✅ `test_callable_serialized` + `test_manifest_fields`（`json.dumps`）绿 |
| E7 | git 不可用（非仓库/超时）→ `commit=null`、`dirty=null` + warning，**不阻断回测**；7 项 manifest 测试全绿 | monkeypatch `subprocess.run` 抛 `OSError` + `pytest tests/test_manifest.py -q` = 9 passed | T-12 要点 3 / DESIGN §8 | ✅ `test_git_unavailable_returns_null` 绿；文件 **9 passed**（7 计划 + E1 开关 + E7，补丁 `d270511`） |

---

## 6. F 逐日 trace 接线（B6：T-13，零数值）

> **DoR**: P-012 `LayerDumper` 六层格式未变；`--trace-dir` 映射点已定。**DoD**: CLI 可用、六层齐备、行数对齐、`compare_runs` 可自消费。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | `python cli.py run --help` exit 0 且含 `--trace-dir`；传 `--trace-dir` 时映射为 `dump_layers_dir` | 子进程 `$LASTEXITCODE` + 输出读回 | T-13 要点 1/2 | ✅ help 含 `--trace-dir`，exit 0；读码 `dump_layers_dir=Path(args.trace_dir) if args.trace_dir else None` |
| F2 | trace 目录六层文件齐备（`LAYER_FILES` 6 项）；`L6_nav.csv` 行数 == `len(dm.trade_dates)` | `pytest tests/test_trace_completeness.py -k 'six_layers or l6_rows' -q` = 2 passed | T-13 要点 4 / DESIGN I10 | ✅ `2 passed, 2 deselected`（`test_all_six_layers_present` + `test_l6_rows_equal_trade_dates`） |
| F3 | `L1_limit_mask.csv`/`L2_tradable.csv` 列名分别为 `date,stock,can_buy,can_sell` / `date,stock,buyable,sellable`（长表） | `pd.read_csv().columns` 断言 | T-13 要点 4 | ✅ `test_l1_l2_long_format_columns` 绿（全可交易 0 行 + 全停牌全行） |
| F4 | `compare_runs(trace_dir, trace_dir)` → `residual == 0`、`attribution_complete is True`；trace 目录含 `manifest.json`（T-12 同写） | 单测 + 文件清单 | T-13 要点 3/4 | ✅ `test_self_diff_consumable` 绿；`residual 1.16e-10 < RESIDUAL_TOL(1e-8)`（CSV round-trip 噪声，F-S9-5）；六层 `changed` 全 0、`manifest.json` 存在 |

---

## 7. G / INV / RL / DOC：测试、不变式、红线与台账

### 7.1 G 测试与验证 — 8 项

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| G1 | 全量 `609 passed`（550 + 59），0 failed / 0 新增 skip；**逐文件核对**新增用例数（RULE-2） | `pytest tests -q` 末行 + 逐文件 `-q` 计数 | IMPL §5 V1 / §9.2 | ✅ `609 passed, 138 warnings`；逐文件 11/9/8/5/9/4/9/4 = 59 |
| G2 | `black --check .` → `167 files would be left unchanged` | black 输出末行 | V2 | ✅ `167 files would be left unchanged` |
| G3 | `mypy --explicit-package-bases core` → `Success: no issues found` | mypy 输出 | V3 | ✅ `Success: no issues found in 36 source files` |
| G4 | `mypy --check-untyped-defs core` → `4 errors in 2 files`（**不劣化**；4 个新 core 模块 0 error） | mypy 输出 + `--show-error-codes` | V4 | ✅ `Found 4 errors in 2 files (checked 36 source files)` |
| G5 | `--collect-only -q` == `609 tests collected` | collect 输出 | V5 | ✅ `609 tests collected in 3.18s` |
| G6 | 分文件绿：`test_reference_diff` 9 / `test_v2_components` 8 / `test_cross_engine_equivalence` 5 / `test_metrics_single_source` 9 / `test_validation_declaration` 4 / `test_manifest` 9 / `test_trace_completeness` 4 / `test_invariants` 11 | 8 次 `pytest <file> -q` 末行 | V6/V7/V8/V14 | ✅ 9 / 8 / 5 / 9 / 4 / 9 / 4 / 11（原预测 9/5/5/8/4/7/4/10，偏差见 IMPL §9.2） |
| G7 | 远端 CI：`.github/workflows/tests.yml` 三 job（3.10/3.11/3.12）全绿，记录 run id | `gh run view <id>` / Actions 页面 | V16 | ✅ run [`42768525717`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42768525717) @ `7bcdd57`：3.10/3.11/3.12 **全 success**；3.10 `602 passed, 1 skipped`（本地 609 − 7 为 numba 相关 `importorskip`，与既有基线同构；首跑 `42768109104` 的 1 失败已由 `7bcdd57` 修复） |
| G8 | 无新运行时依赖（`git diff pyproject.toml` 空；`pyarrow\|hypothesis\|pandera` 新增代码 0 命中）；8 个新测试文件 `data/test_ashare` 0 命中 | `git diff` + `Grep` 双检 | V12 | ✅ `git diff pyproject.toml` 空；新增 14 文件 4 关键词 0 命中 |

### 7.2 INV 不变式（DESIGN §6，I1-I10）— 10 项

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| INV1 | I1 NAV 恒等：逐快照 `total_value == cash + Σ market_value` | `test_invariants.py`（A3） | DESIGN I1 | ✅ A3 `2 passed` |
| INV2 | I2 持仓恒等：持仓数量 == 截至该日成交累计（含退市/强平 trade） | A4 + 读码 | DESIGN I2 | ✅ A4 `3 passed`（同日多快照日期跳过，F-S9-3） |
| INV3 | I3 成本恒等：`Σ cost == stats`、`cost>=0`、`net_amount` 符号 | A5 | DESIGN I3 | ✅ A5 `2 passed` |
| INV4 | I4 收益恒等：`daily_return`/`cumulative_return` 与 NAV 递推一致 | A6 | DESIGN I4 | ✅ A6 `2 passed` |
| INV5 | I5 V3 NAV 恒等：`pv[t] == cash[t] + Σ positions[t]*close[t]` | `test_reference_diff -k v3_nav`（B2/B9） | DESIGN I5 | ✅ `1 passed`（`test_v3_nav_matches_reference`）+ `check_v3_nav_identity` 读码 |
| INV6 | I6 V3 静态持仓：非调仓日 `positions[t]==positions[t-1]` | 读码 + 测试（B9） | DESIGN I6 | ✅ 32 组内核网格（非调仓日持仓保持）+ `check_v3_static_positions` 读码 |
| INV7 | I7 V3 成本恒等：`cash` 变化 == `-ΣΔqty*price - Σ\|Δqty\|*price*rate` | 读码 + 测试（B2） | DESIGN I7 | ✅ 内核现金差分（B2 `matches_reference`）+ `check_v3_cost_identity` 读码 |
| INV8 | I8 manifest 可恢复：config 键集无损、无非 JSON 化对象 | E5/E6 | DESIGN I8 | ✅ E5/E6 绿 |
| INV9 | I9 口径唯一：三方 5 指标 `rtol=1e-12` | C8 | DESIGN I9 | ✅ C8 `9 passed` |
| INV10 | I10 trace 完备：六层齐备、L6 行数 == 交易日数 | F2 | DESIGN I10 | ✅ F2 `2 passed` |

### 7.3 RL 排除与红线（IMPL §1.4 + §2.4 + DESIGN §10.1）— 9 项

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| RL1 | B1/B2/B4/B5/B6 **零数值**：批次前后指标/NAV 逐字段一致（或 `change_report` 全零） | 各批 before/after 对拍 | IMPL §1.4 原则 2 | ✅ 五批 diff 不含 NAV/指标/执行路径（`core/execution.py`、`core/data.py`、`filter/` 0 改动）；全量 609 绿 |
| RL2 | B3 为**唯一行为批次**；NAV 与六层 dump 零变化 | C9 | DESIGN D1 | ✅ C9 `residual 0.0` / 六层 `changed` 全 0 / NAV 逐值不变 |
| RL3 | 默认路径不变：`invariant_mode="report"` / `write_manifest=True` / `risk_free_rate=0.03` / `dump_layers_dir=None` | `git diff core/config.py` 读码 | DESIGN §10.1-2 | ✅ 读码四项默认值均如约定 |
| RL4 | 零新增运行时依赖；测试不引入 `hypothesis`/`pandera`/`pyarrow` | G8 | DESIGN §10.1-3 | ✅ 同 G8 |
| RL5 | 不改 P-012 契约：六层文件名/列名/CSV 编码/`compare_runs` 语义 | `git diff core/change_report.py` = 空 | DESIGN §10.1-6 | ✅ `git diff --stat dc71c1a..HEAD -- core/change_report.py` 空 |
| RL6 | 不改 V2/V3 成交时点、掩码、取价、退市逻辑 | `git diff` 限定文件读码 | DESIGN D9 | ✅ 25 文件 diff 均在 `core/` 新增模块 / `tests/` / `cli.py` / `docs/`；执行与数据层 0 改动 |
| RL7 | 默认 rf=0.03 保持 V2 现值；V3 指标变化已披露（CHANGELOG + Δ 表） | C4/C7 + CHANGELOG 读回 | DESIGN §7.3 | ✅ V2 rf 0.03 不变；CHANGELOG「P-011 B3 指标口径统一」+ IMPL §9.3 Δ 表 |
| RL8 | 每批单提交；消息 UTF-8 无 BOM（`[System.IO.File]::WriteAllText` + `git commit -F`） | `git log --oneline` + `Format-Hex` 首字节非 `EF BB BF` | IMPL §7 提交纪律 | ✅ 7 提交单批单提交；首字符 `0x66`（`f`）非 BOM |
| RL9 | 回退演练：`git revert --no-commit <B3>` 仅回退 B3 文件，`--abort` 可复原 | V15 输出 | IMPL §6 | ✅ worktree 演练：B3 的 8 文件回退，`config.py` 1 处行相邻冲突（保留 B5 行即解）→ 净 7 文件；主工作区零影响（F-S9-6） |

### 7.4 DOC 台账与文档 — 5 项

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| DOC1 | 四文档齐备且互链：RESEARCH / DESIGN / IMPL / CHECKLIST（相对链接可解析） | 链接检查（12+ 条 0 broken） | SPEC §文档目录 | ✅ 四文档齐备；13 条互链 0 broken（Step 8 机械校验；Step 9 未改链接结构） |
| DOC2 | PROGRESS §1.4 P-011 行、§3.12 记录、§3.14 状态更新行同步至最终状态 | 读回 | IMPL T-14 | ✅ 三处均已更新至 Step 9 完成（六批 hash + 609/167/0 + F-S9-*） |
| DOC3 | CHANGELOG：B3 行为变更（V2 vol/sharpe、V3 sharpe/mdd）+ B5 新增 `manifest.json` 已明示 | 读回 | DESIGN §10.1-2 | ✅ `[Unreleased]` 三节：Added（P-011 全套）/ Changed（B3 口径）/ Fixed（F-S9-1 等） |
| DOC4 | DECISIONS：本批不新增 ADR（口径决策属 DESIGN D5），如需登记则说明理由 | 读回 | DESIGN §2.2 | ✅ 无新增 ADR；口径决策记录于 DESIGN §4.2/§5.4 与 CHANGELOG |
| DOC5 | 提交链与 CI run id 记录在 §10.0 与 PROGRESS | `git log` + Actions | IMPL T-14 | ✅ 提交链 8 个 hash 已记 §10.0 与 PROGRESS §3.12；CI run `42768525717` 已回填（G7） |

### 7.5 错误处理映射（DESIGN §8，8 场景；验收以对应功能项为准，不重复计数）

| 场景 | 预期 | 对应验收项 |
|------|------|-----------|
| 不变量违规（report） | 聚合不中断 | A7 |
| 不变量违规（raise） | 抛首条 | A7 |
| `pv` 长度 < 2 | `ValueError` | C2 |
| git 失败 | null + warning 不阻断 | E7 |
| 数据文件缺失 | `exists=false` | E3 |
| 配置含 callable | `"<callable>"` | E6 |
| trace 目录不可写 | `OSError` fail-fast | F1/F2 |
| 声明字段无来源 | false/null | D3 |

---

## 8. 一致性 Review（Step 8，独立 pass，2026-11-10）

- **执行时点**: 四份文档（RESEARCH / DESIGN / IMPL / CHECKLIST）全部完稿后的独立 pass；**审查基座 GLM-5.3-Flash ≠ 各文档作者基座 DeepSeek-V4.1-Flash**（RULE-5 异构满足）；本节与正文非同一次写入（RULE-1）
- **审查方式**: E1 机械校验（链接 / ID 序列 / 计数）+ E3 读码（互引锚点、术语、断言延续）+ 与 Step 4/6 审计记录交叉核对

### 8.1 机械校验读数

| 检查 | 命令/方式 | 结果 |
|------|-----------|------|
| 四文档 markdown 链接 | PS 正则提取 `\[\](target)` 逐个 `Test-Path` | **13 条 0 broken**（互引 + RESEARCH 外链 ARCHITECTURE.md / DIFF_REPORT_2026-10-23.md 均存在） |
| 清单 ID 序列 | `^\| ([A-Z]+[0-9]+) \|` 提取 | **76 个连续无缺号无重复**：A1-A8 / B1-B10 / C1-C10 / D1-D5 / E1-E7 / F1-F4 / G1-G8 / INV1-INV10 / RL1-RL9 / DOC1-DOC5 |
| 0 预填 | `Grep '[待 Step 9]'` = **78**；表格行 = **76**；`✅` 字面 = **2**（均在说明性文本 L8/L190，实测列 = 0） | ✅ 78 = 76 + 2 自洽 |
| 分母算术 | 8+10+10+5+7+4+8+10+9+5 | **= 76** ✅（与 ID 计数一致） |
| 未闭合断言标记 | `Grep 'STEP_GAP\|CONFLICT\|FALSIFIED\|单源-待二核'` 四文档 | **0 命中** |

### 8.2 预登记 5 项核对

- [x] **双向引用完整**：四文档互引 13/13 可达；DESIGN 引用的 ADR-002/003/005/007/012/017 在 [DECISIONS.md](DECISIONS.md) 均存在（§2.2 表逐行核对；存在性判定口径见本节预登记）
- [x] **0 预填**：见 8.1（76 行全 `[待 Step 9]`；实测列 `✅` = 0）
- [x] **断言延续**：四文档 **0 个** STEP_GAP / CONFLICT / FALSIFIED / 单源-待二核标记——RESEARCH 的 U-1~U-4 与合并判定已在 §11.8 全部裁决闭合，无 B 类未决断言需要携带；18 条 P 事实均绑 `@05af52f`（P-012 收官后 `2c34283`..`dc71c1a` 对 core/filter/tests 零 diff，绑定仍有效）
- [x] **术语一致（7 组）**：不变量（invariants I1-I10）/ 事件级等价（DESIGN 12 · IMPL 3 · CHECKLIST 2）/ 口径映射 / 量级约定（DESIGN 12 · IMPL 2 · CHECKLIST 2）/ 参考实现差分 / 偏差声明 / run manifest——无同义漂移；golden 用法统一（仅指延后的 L4 方案，不与本批「参考实现差分」混用）
- [x] **文档间无矛盾**：① D→I 签名一致（`check_return_identity` 已含 `initial_capital`，F-I5 回写后核对）；② 批次↔任务（B1=T-0~T-3 / B2=T-4~T-6 / B3=T-7~T-10 / B4=T-11 / B5=T-12 / B6=T-13 / docs=T-14，清单分组头与之对齐）；③ V↔G 计数（V1-V5→G1-G5、V6/V7/V8/V14→G6、V9→C4、V10→C9、V11→E4、V12→G8、V13→F1、V15→RL9、V16→G7——16 项全有归宿）；④ 目标末态三文档一致（Step 9 实测 609/167/68，原预测 602 已由 IMPL §9.2 修正）

### 8.3 发现项（3 项 P3，全部已回写）

| ID | 等级 | 发现 | 修复 |
|----|------|------|------|
| **F-S8-1** | P3 | §1 A 组头注「（B1：T-1/T-2/T-3）」含 **T-2**——但 T-2（参考实现）的全部验收项在 §2 B 组，A 组无 T-2 锚点 | 头注改「（B1：T-1/T-3）」 |
| **F-S8-2** | P3 | C5 锚点「DESIGN §2.2」指向错误文档——numba 默认参数兼容声明位于 **IMPL §2.2** 兼容性表（DESIGN §2.2 是 ADR 表） | 锚点改「T-9 / IMPL §2.2」并注记 |
| **F-S8-3** | P3 | §8.1 预填判据不够精确：全文 `✅` 字面 = 2（L8 填写规则、核对点自述），若 Step 10 机械检查按「全文 ✅ == 0」判定会误报 | 核对点 2 改为「实测列 `✅` = 0（全文 = 2，位置 L8/L190）」并勾选 |

### 8.4 派生需求登记（预检）

实施期派生需求见 §10.0（F-S9-1~F-S9-7，其中 F-S9-1 为 P1 缺陷修复）。**完整派生需求清点在 Step 10 ADD 审计 Phase 3 执行**（code → design 方向）。

### 8.5 Review 结论

**P1 = 0；P2 = 0；P3 = 3（F-S8-1/F-S8-2/F-S8-3，已回写）**。机械校验全过（13 链接 0 broken / 76 ID 连续 / 0 预填 / 分母 76 自洽 / 0 未闭合断言）；预登记 5/5 通过；术语 7 组贯通；文档间无矛盾。**P-011 Step 8 一致性 Review 通过**，可进入 Step 9 实施（B1→B6 六提交 + T-14）。

---

## 9. ADD 审计（Step 10，已执行 2026-11-10）

- **时点**: 2026-11-10，实施（Step 9）与推送/CI 完成后独立执行（RULE-1）
- **审查者**: 单 Agent 自查（RULE-4）；**同基座限定**：审计与实施会话同为 DeepSeek-V4.1-Flash，RULE-5 异构第二会话复审**未执行**（Step 4/6/8 文档 Review 为 GLM-5.3-Flash），留待独立会话（见 §9.4）
- **取证方式**: 门禁链（session `factorv3-p011-backtest-validation-20261110`，终态 `replay: 10 rows OK`）+ `git diff dc71c1a..b9c7d75` 24 个代码/测试文件全文盲区扫描 + E3 读码绑 `@a754a2d` + 审计时点复跑

### 9.1 四阶段

#### Phase 0: Spec 质量门

- [x] DESIGN/IMPL 无「合理处理 / 适当时机 / 酌情 / 视情况 / 尽量 / 按需 / 尽可能 / 大概 / 大约 / 必要时」类不可审计措辞——两文档逐词扫描 **0 命中**
- [x] D1-D9 → 验收出口可追溯（Step 8 §8.4 V↔G 16 项全有归宿）；**但发现 D5 的 `metrics_method` 交付物在 CHECKLIST 无对应验收行**（C1-C8 只覆盖公式与委托）——Phase 0 漏洞即 F-A1 根因，Step 6/8 双 Review 均未拦截

#### Phase 1: 完整性（design → code，E3 @`a754a2d`）

- [x] **D1 批次切分**: `git log dc71c1a..HEAD` = 6 行为/零数值批次提交（`cd6d619`..`b6bcee3`）+ 4 补丁 + 3 docs，与 §1.2 映射一致；B3 唯一行为批隔离
- [x] **D2 不变量**: 七个 `check_*` + `check_all` @`core/invariants.py:88/113/170/216/254/281/305/336`；`invariant_mode` @`config.py:344`；接线 @`engine_v2:1066-1076`（`"off"` 分支整体跳过）
- [x] **D3 参考差分**: `tests/_reference_impl.py` 4 函数（`_seq_sum` 顺序累加对齐 njit）；4 组差分 @`test_reference_diff.py`（267 行）
- [x] **D4 事件级等价**: `test_cross_engine_equivalence.py` 158 行——五断言 + 阴性对照 `[7_500.0, 3_000.0]` @`:158`
- [x] **D5 口径统一**: `core/metrics.py:16-18/22-29/46`（常量 + `METRICS_METHOD` + `compute_metrics`）；analytics 委托 @`analytics.py:84`；V3 kernel rf @`engine_v3:156`、锚点 @`:178-183`、量级 @`:416`；`metrics_method` V2 @`engine_v2:1092` / V3 @`engine_v3:419`（F-A1 补）
- [x] **D6 偏差声明**: `core/validation.py:13-21/30`；接线 @`engine_v2:1084-1089`
- [x] **D7 manifest**: `core/manifest.py:29-186`（`_fingerprint:119-125` 只含 git/数据 sha256/config）；接线 @`engine_v2:1121-1166`（`write_manifest:1140` 开关、`OSError` 仅 warning）
- [x] **D8 trace**: `--trace-dir` @`cli.py:316/:71`；复用 `LayerDumper`（`core/change_report.py` diff **0**）
- [x] **D9 范围边界**: `pyproject.toml` / `.github/` / `core/execution.py` / `core/data.py` / `filter/` diff 全 **0**；golden/DSR/Qlib 依赖均未引入

#### Phase 2: 忠实度（双向对照）

- [x] numstat 对账：代码/测试 **24 文件**，与 IMPL §2.3 的 19 文件清单逐文件吻合 + 3 个既有测试修改有归属（`test_decoupled_engine` +7 → F-I1 协议扩展涟漪；`test_numba_jit_performance` 2/1 与 `test_v3_engine_integration` 2/1 → C10/F-R4 预登记）+ F-A1 修复 5 文件（`a754a2d`）
- [x] 关键公式逐字对照：回撤锚点 `cumulative[0]=1.0` 递推（`engine_v3:178-183`）；结果量级 `-float(max_drawdown)`（`:416`）；`sharpe=(annual-rf)/vol`（`metrics.py` §4.2 同文）；指纹不含时间戳/uuid（`manifest:119-125`）——实现与条文一致
- [x] 阴性对照精确值 `[7_500, 3_000]`（F-S9-4 修正后）与 DESIGN §4.5 回写一致
- [x] 偏差登记闭环：F-S9-1~F-S9-7（Step 9）+ F-A1~F-A3（Step 10）全部回写 IMPL §9.5 / DESIGN（F-S9-2~4、F-A2）/ CHECKLIST §10.0，无未登记静默偏离

#### Phase 3: 必要性（code → design，盲区扫描）

- [x] **扫描范围（E4）**: 24 个代码/测试文件 `dc71c1a..b9c7d75` diff 全文（核心 7 文件逐 hunk）+ 3 个新文档 + 2 个台账 diff——**发现 3 项**（§9.2 F-A1/F-A2/F-A3），**0 项无依据代码行为**
- [x] 新增行归属：`engine_v2.py` +96 行全归属 D2/D5/D6/D7；`analytics.py` 32/30 全归属 D5；`engine_v3_vector.py` 22/12 全归属 D5；`tracker.py` 4/3 = F-S9-1；`interfaces.py` +4 = F-I1；`cli.py` +4 = D8；`config.py` +3 = D2/D5/D7
- [x] 既有测试仅 3 处修改且均有归属（Phase 2 对账）；既有 27 项数据测试与 P-012 层测试零改动（全量 609 绿佐证）
- [x] 保护路径：`pyproject.toml` / `.github/` / `core/change_report.py` / `core/execution.py` / `core/data.py` / `filter/` / baseline 夹具（`data/` gitignore 不入 diff）——diff 均符合预期

#### Phase 4: 语义 + Iron Law

- [x] **Iron Law 核对**: `609 passed` ≠ 设计落地——以 B3 双门（Δ 表逐字段 + `change_report residual 0.0`）+ D1-D9 映射 + numstat 对账 + 门禁链 replay 补足；**F-A1 即反例**：测试全绿但 D5 交付物缺失，由审计而非测试捕获——审计必要性实证
- [x] B3 行为变更已披露：CHANGELOG [Unreleased] Changed 节明示 V2/V3 受影响字段与数值；非「仅重构」
- [x] 语义抽查：`check_all` 仅 `invariant_mode != "off" and snapshots` 时执行（`engine_v2:1066`，零数值路径）；manifest 失败 `except OSError` 仅 warning 不阻断回测（`engine_v2:1174`）；`_fingerprint` 输入经 `_canonical_json` 排序键（确定性）
- [x] 门禁复跑（审计时点，修复 `a754a2d` 后）: unit-tests / black-check / mypy-check **3 pass** + 修复前 probe **4/4**；`replay: 10 rows OK`；远端 run `42768525717`（`7bcdd57`）与 `42771058634`（`955f06a`，含 F-A1 修复远端首跑）**各三 job success**

### 9.2 审计发现

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-A1 | **P2** | D5/DESIGN §5.4 承诺的 `additional_info["metrics_method"]` **未落地**（代码 0 命中；仅 `validation_declaration.sharpe_method` 部分覆盖）——Step 9 实现遗漏，且 CHECKLIST 无对应验收行（Phase 0 缺口），Step 6/8 双 Review 未拦截 | **已修复** `a754a2d`：`core.metrics.METRICS_METHOD` 常量 + V2 `additional_info` / V3 results 接线（rf 运行时覆盖）；断言并入 `test_declaration_present`（V2）与 `test_v3_results_use_config_rf`（V3），609 passed 不变；黑名单措辞/门禁/mypy 复跑全绿 |
| F-A2 | P3 | `build_manifest` 实际签名含 `benchmark`/`repo_root` 可选参数、输出含 `"benchmark"` 键，DESIGN §4.4 签名与 §5.2 JSON 未列 | DESIGN §4.4/§5.2 已补注（本批回写）；功能合理（manifest 保留原始 benchmark 便于复现） |
| F-A3 | P3 | `analytics.calculate_performance_metrics` 对 `len(total_values) < 2` 由「算出部分指标」改为返回 `{}`（配合 `compute_metrics` 的 N>=2 契约）——边界路径行为变化，IMPL T-8 未预登记 | 代码注释 + `test_compute_metrics_empty_and_single` 固化；登记于 IMPL §9.5 |

### 9.3 取证矩阵（E1-E5）

| 手段 | 证据（节选） | 覆盖 |
|------|--------------|------|
| E1 可重放命令 | `pytest 609 passed`（审计时点复跑）/ `black 167 unchanged` / `mypy Success 36 files` / `--collect-only 609` / 门禁 session `10 rows OK` / `git log dc71c1a..HEAD` / `git diff --numstat`（24 文件）/ Grep 计数（不可审计措辞 0、`metrics_method` 修复前后 0→9、保护路径 diff 0）/ `gh run view 42768525717` 三 job success | G1-G8、A1-A8 证据出口、RL5/RL6/RL8、D9、Phase 0 |
| E2 运行时脚本 | Step 9 期 `%TEMP%\p011_b3_delta.py`（Δ 表）+ `p011_v10\` before/after dump + `scripts/change_report.py`（residual 0.0）——`[未入仓-不可重放]`；场景选择理由：R7 夹具 31 股×60 日含停牌/ST/整手边界事件 | C4/C9、RL1/RL2、§10.0 Δ 表 |
| E3 静态读码 | `@a754a2d`：`invariants.py:88/113/170/216/254/281/305/336`（I1-I7+check_all）、`metrics.py:16-29/46`、`validation.py:13-30`、`manifest.py:119-186`、`engine_v2:1066-1095/1121-1167`、`engine_v3:156/178-183/400-419`、`analytics:84`、`cli:71/316`、`tracker:261`、`interfaces:201` | D2-D8 全部、INV1-INV10、A2/A8、C1/C3/C5/C7、E5/E6 |
| E4 盲区扫描/判断 | 24 文件 diff 全文「发现 3 项」；Iron Law 反例（F-A1）；RULE-5 同基座限定声明；`check_all`/manifest 失败语义评估 | Phase 0/3/4、§9.2 |
| E5 推测/未执行 | trace 目录不可写 OSError 场景、`check_v3_*` 直接单测 | **仅列于 §9.4，不进结论** |

### 9.4 未覆盖项与限定

| 项 | 状态 | 说明 |
|----|------|------|
| RULE-5 异构第二会话复审 | `待执行` | 本审计与实施同基座（DeepSeek-V4.1-Flash）；Step 4/6/8 文档 Review 为 GLM-5.3-Flash；Step 9/10 的实施+审计异构复审留待独立会话（P-012 同款限定） |
| trace 目录不可写 → `OSError` fail-fast | `[未在 CI 覆盖]` | CHECKLIST §7.5 场景 7 的设计预期（P-012 LayerDumper 既有语义），本批未构造取证 |
| `check_v3_{nav_identity,static_positions,cost_identity}` 直接单测 | `[未在 CI 覆盖]` | F-S9-7 已披露：公共诊断 API，I5-I7 由参考差分覆盖（B2/B9） |
| CI 无 numba ≡ `NUMBA_DISABLE_JIT=1` 的完全等效性 | `[未取证]` | 本地双跑 9 passed + CI 3.10 无 numba 实测（run `42768525717`）覆盖主路径；其他 numba 相关 7 项 skip 的 CI 语义与既有基线同构 |

### 9.5 审计结论

| 项 | 结论 |
|----|------|
| Phase 0-4 | **全过**（0 项退回重写 / 0 项静默偏离——3 项发现全部登记回写 / 0 项无依据行为 / 0 项意图错位） |
| P1 阻断 / P2 应修 / P3 提示 | **0 / 1（F-A1，已修复 `a754a2d`）/ 2**（F-A2/F-A3，文档与登记粒度，已当场处置） |
| 门禁链 | unit-tests / black-check / mypy-check + probe **4 pass**；`replay: 10 rows OK` |
| 证据绑定 | §9.3 矩阵五类手段覆盖 76 项；无 E5 进入结论；4 项限定已声明 |
| Iron Law | 通过——B3 双门 + D1-D9 映射 + numstat 对账三层补足；**F-A1 反例实证审计价值**（测试全绿仍有设计交付物缺失） |

---

## 10. 验收结论

### 10.0 Step 9 实施记录（2026-11-10）

| 批次 | 提交 | 行为 | 关键读数 |
|------|------|------|----------|
| B1 | `cd6d619` | 零数值 | `test_invariants` 11 + `test_reference_diff` 9；`tracker` 快照逐 Position 复制（F-S9-1） |
| B2 | `26929c6` | 零数值 | `test_v2_components` 8 + `test_cross_engine_equivalence` 5；`BACKTEST_CALIBER_MAPPING.md` 5 章 |
| B3 | `9ec9f7d` | **行为（报告指标）** | Δ 表见下；`change_report residual 0.0` / 六层 `changed` 全 0 |
| B4 | `e59dee2` | 零数值 | `test_validation_declaration` 4；`additional_info.validation_declaration` |
| B5 | `beaa3a1` | 零数值 | `test_manifest` 7→9（补丁后）；`manifest.json` 落盘 |
| B6 | `b6bcee3` | 零数值 | `test_trace_completeness` 4；`--trace-dir` exit 0 |
| 补丁 | `d270511` | 零数值 | E1 `write_manifest=False` + E7 git `OSError` |
| 补丁 | `7bcdd57` | 零数值 | 参考差分主用例兼容无 numba 环境（F-S9-2 远端补正） |
| Step 10 | `a754a2d` | 零数值 | ADD 审计 F-A1（P2）修复：`metrics_method` 声明落地（METRICS_METHOD + V2/V3 接线，断言并入既有 2 用例） |

**B3 Δ（31 股 × 60 日，before `@cd6d619`）**：V2 `annual_volatility 0.08122845→0.08189931`、`sharpe −1.45492→−1.44300`、`total_return` 1 ulp；V3 `max_drawdown −0.02965091→+0.02965091`、`sharpe 0.93900→0.59117`（== rf/vol）；其余字段 0；NAV / trades / 六层逐值不变。完整表见 [IMPL §9.3](IMPL_backtest_validation.md)。

**失败与修正（F-S9-*，详见 IMPL §9.5）**：
- **F-S9-1（P1）**：`_take_snapshot` 浅拷贝共享 `Position` → 引擎实跑 53 项 I1/I2 违规；改逐 Position `replace()`，NAV 标量不变
- **F-S9-2（P2）**：numba `np.sum` 顺序累加 vs NumPy pairwise（200 组中 100 组末位差 1 ulp）；参考实现改 `_seq_sum`，`py_func` 用例 `rtol=1e-12`
- **F-S9-3（P2）**：末日强平追加同日第二快照 → I2 跳过同日多快照日期，补 ambiguous 用例
- **F-S9-4（P3）**：阴性对照 `3_750` → `3_000`（`P[1]=25` 精确值）
- **F-S9-5（P3）**：trace 自差分 residual 1.16e-10 → 断言 `< RESIDUAL_TOL(1e-8)`
- **F-S9-6（P3）**：B3 单提交回退在 `config.py` 1 处行相邻冲突（保留 B5 行即解），净回退 7 文件
- **F-S9-7（P3）**：V3 三个 `check_*` 为公共诊断 API，无直接单测；I5-I7 由参考差分覆盖
- **F-A1（P2，Step 10 审计）**：D5/§5.4 的 `metrics_method` 未落地 → 已修复 `a754a2d`
- **F-A2/F-A3（P3，Step 10 审计）**：manifest `benchmark` 键设计补注；analytics `<2` 快照返回 `{}` 边界披露（详见 §9.2）

**机械验证 V1-V16**：V1 609 passed / V2 167 unchanged / V3 Success 36 files / V4 4 errors 2 files / V5 609 collected / V6 9（JIT 与 `NUMBA_DISABLE_JIT=1` 双跑）/ V7 5 / V8 9 / V9 Δ 表 / V10 residual 0.0 / V11 指纹稳定 / V12 零新依赖 / V13 CLI exit 0 / V14 4 passed（residual 1.16e-10 < 1e-8）/ V15 净 7 文件回退 / V16 本地干净 + 远端 run `42768525717` 三 job 全绿。

### 10.1 验收统计

| 类别 | 总数 | 通过 | 失败 | 待办 |
|------|------|------|------|------|
| A 不变量体系（B1） | 8 | 8 | 0 | 0 |
| B 参考差分与跨引擎等价（B1/B2） | 10 | 10 | 0 | 0 |
| C 报告口径统一（B3） | 10 | 10 | 0 | 0 |
| D 偏差声明（B4） | 5 | 5 | 0 | 0 |
| E 运行清单（B5） | 7 | 7 | 0 | 0 |
| F 逐日 trace（B6） | 4 | 4 | 0 | 0 |
| G 测试与验证 | 8 | 8 | 0 | 0 |
| INV 不变式 | 10 | 10 | 0 | 0 |
| RL 排除与红线 | 9 | 9 | 0 | 0 |
| DOC 台账与文档 | 5 | 5 | 0 | 0 |
| **总计** | **76** | **76** | **0** | **0** |

> **统计口径（RULE-2）**：逐行回填，每行 `总数 = 通过 + 失败 + 待办` 成立；总计行按列求和成立（8+10+10+5+7+4+8+10+9+5 = 76；76+0+0 = 76）。§7.5 为锚点表，不重复计数。
> **通过门槛**：P1/P2 = 0；B3 附 `change_report.json` 且 residual / attribution 双门通过；60 → 68 测试文件；G7 以远端实测为准（Step 10）。

### 10.2 验收决定

- [x] **验收通过**：76/76 通过；P1=0（实施期唯一 P1 F-S9-1 已修复并披露）；远端 CI run `42768525717` 三 job 全绿
- [ ] **有条件通过**：<条件>
- [ ] **验收失败**：<原因>

### 10.3 签字

| 角色 | 签字 | 日期 |
|------|------|------|
| 实施者 | 单 Agent 自查（DeepSeek-V4.1-Flash） | 2026-11-10 |
| 审查者 | ADD 审计单 Agent 自查（DeepSeek-V4.1-Flash，同基座限定见 §9.4）；异构复审待独立会话 | 2026-11-10 |

---

## 11. 后续行动

| 行动 | 责任人 | 期限 | 状态 |
|------|--------|------|------|
| Step 8 一致性 Review（独立 pass；5 项预登记核对点 + 机械校验） | 单 Agent 自查（RULE-4） | Step 8 | done（2026-11-10，§8） |
| Step 9 实施（B1→B2→B3→B4→B5→B6 六提交 + T-14） | 单 Agent 自查 | Step 9 | done（2026-11-10，8 提交；76/76，远端 CI `42768525717` 全绿） |
| Step 10 ADD 审计 + 提交推送 + 远端 CI（G7 回填） | 单 Agent 自查 | Step 10 | done（2026-11-10，§9 四阶段全过；P1=0/P2=1 F-A1 已修复 `a754a2d`/P3=2；RULE-5 异构复审留待独立会话） |
| Step 11 审计总结（用户指令扩展步，SPEC_PROCESS 十步之外） | 单 Agent 自查 | Step 11 | done（2026-11-10，[AUDIT_SUMMARY_backtest_validation.md](AUDIT_SUMMARY_backtest_validation.md)；28 项发现归并、U-D4 标注实际闭合、2 项 P3 注记，无新发现） |
