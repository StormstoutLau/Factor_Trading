# P-007 层 B（引擎 mypy 93 errors 清理） · 审查验收清单

> **文档编号**: CHECKLIST_p007_mypy_layerb
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: **Step 1-10 全通过**（2026-11-10；**54/54 ✅**；P1/P2 = 0；主提交 `05af52f`；远端 CI run `42666962752` 三 job 全绿）
> **上游**: [DESIGN_p007_mypy_layerb.md](DESIGN_p007_mypy_layerb.md)（Step 4 通过，D1-D9 / V1-V12） · [IMPL_p007_mypy_layerb.md](IMPL_p007_mypy_layerb.md)（Step 6 通过，T-0~T-8 / F-I1~F-I4）
> **填写规则**: 本清单在 Step 7 只定义「怎么算做完」；**「实测」列一律 `[待 Step 9]`，禁止实现前预填**（RULE-1）。每条 ✅ 必须绑定证据出口；无证据只能标 `[未在 CI 覆盖]` / `[未入仓-不可重放]` / `[未取证]`。
> **解释器**: `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10）；测试命令加 `MPLBACKEND=Agg`
> **基线时点**: 本仓 @ `762ff5f`；RED 读数 **93（54/26/13）/ 102 / 514 / 50 / 1**；Step 9 末态 **0 / 8 / 516 / 51 / 1**

---

## 1. 行为变更与真实缺陷（A）

> **DoR**: RESEARCH §3.1 的 A-1/A-2 已由 E2 探针取证；DESIGN D1/D3 的行为契约明确。**DoD**: 每条都有「修复前可复现」+「修复后测试绿」两段证据，且行为变更已披露。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | **D1**：`BacktestConfig(factor_files=[])` + `setup()` 抛 `ValueError`，消息含 `factor_files`；且守卫位于**任何组件创建之前** | `pytest tests/test_mypy_layerb_smoke.py::test_empty_factor_files_raises_value_error -q` = 1 passed；读回 `engine_v2.py` 中 `if not self.cfg.factor_files` 在 `t0 = time.perf_counter()` 之前 | DESIGN D1；IMPL T-1 | ✅ 1 passed；守卫在 docstring 后、`t0` 前。**实施偏离 F-S9-1**：条件加 `_injected_pipeline/_injected_combiner` 均 None 限定（见 §10.0） |
| A2 | 空因子不再进入逐日循环：`setup()` 失败后 `engine.dm is None`（无部分初始化），`run()` 的 `dm` 守卫仍有效 | 同一测试内的 `assert engine.dm is None`；读回 `run():277-278` 守卫未改 | DESIGN D1「位置选择」；P34/P35 | ✅ `assert engine.dm is None` 通过；`run()` 守卫保留（`请先调用setup()方法`） |
| A3 | 修复前 RED 已取证：空因子 → 逐日 `TypeError` 被 `except Exception` 吞 → 100 条 ERROR + 空回测 | RESEARCH §3.1 PROBE-1~7 原始读数（`%TEMP%` 探针，`[未入仓-不可重放]`）；Step 9 实施前不得再跑该路径 | RESEARCH §5.3 / §13.2；A-1 | ✅ RESEARCH PROBE-1~7 `[未入仓-不可重放]`；Step 9 的 RED 复现形态另记于 §10.0 |
| A4 | **D3**：未 setup 直接调 `_generate_results()` 抛 `RuntimeError`（而非 `AttributeError`），消息含 `setup` | `pytest tests/test_mypy_layerb_smoke.py::test_generate_results_requires_setup -q` = 1 passed | DESIGN D3；IMPL T-3；A-2 | ✅ 1 passed（`RuntimeError`，消息含 `setup`） |
| A5 | 守卫文案与 `run()` 一致：`engine_v2.py` 中 `请先调用setup()方法` 恰 **2 处**（`run` + `_generate_results`） | Grep `请先调用setup()方法` in `core/engine_v2.py` = 2 | DESIGN D3「一致性」 | ✅ 2 处 |
| A6 | 正常路径零回归：既有引擎集成测试（`test_decoupled_engine` / `test_rebalance_exits` / `test_real_ashare_*`）全绿 | V4 全量 `516 passed`；`git status --short tests/` 无既有测试修改 | DESIGN D8；IMPL T-7 | ✅ `516 passed`；`tests/` 仅新增 1 文件 |
| A7 | 行为变更已披露：CHANGELOG 记录 D1（空因子 fail-fast）与 D3（未 setup 守卫），未写成「仅类型修正」 | 读回 `CHANGELOG.md` `[Unreleased] > Changed` 条目 | DESIGN §2 D1/D3；IMPL T-8 | ✅ `Changed` 前两条：空因子 fail-fast（行为变更）+ `_generate_results` 未 setup 守卫（行为变更）；另 `引擎 mypy 清零` 一条 |

## 2. 接口契约（B）

> **DoR**: DESIGN D2 的两处契约与 Step 4 F-D1 的 property 修法已定稿。**DoD**: 契约文本、运行时导入、实现方/Mock 兼容四项均有独立证据。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `IPositionTracker.get_snapshots` 返回 `list[PortfolioSnapshot]`（无引号，`__future__ annotations` 下惰性求值） | 读回 `interfaces.py:271` 区域；Grep `def get_snapshots` 在 interfaces = 1 | DESIGN D2 决定 1；A22/A23 | ✅ `interfaces.py:287`；Grep = 1 |
| B2 | `PortfolioSnapshot` 是 dataclass 且**不是** dict 子类（协议原声明 `list[dict]` 不成立的前提） | `python -c "from core.tracker import PortfolioSnapshot; import dataclasses; print(dataclasses.is_dataclass(PortfolioSnapshot), issubclass(PortfolioSnapshot, dict))"` → `True False` | RESEARCH §13.3.2；E3 `tracker.py:133-135` | ✅ `True False` |
| B3 | `ITradeLog` 协议存在，且仅含 `get_trades_df() -> pd.DataFrame`（最小契约，不扩面） | 读回 `interfaces.py` 新增类；Grep `class ITradeLog` = 1；`def get_trades_df` in ITradeLog = 1 | DESIGN D2 决定 2；A22 | ✅ `class ITradeLog` = 1；`def get_trades_df` = 1 |
| B4 | `IExecutionSimulator.trade_log` 是**只读 property**（`@property def trade_log(self) -> ITradeLog`），**不是**可变属性声明 `trade_log: ITradeLog` | 读回 `interfaces.py` IExecutionSimulator 区域；Grep `trade_log:` = 0（变量声明形态不应出现） | Step 4 F-D1；A31 | ✅ `trade_log:` 0 命中；只读 property（L251-254） |
| B5 | `TYPE_CHECKING` 导入不产生运行时导入：`core.interfaces` 导入后 `core.tracker` **不在** `sys.modules` | `python -c "import core.interfaces, sys; print('core.tracker' in sys.modules)"` → `False` | DESIGN D2「运行时」；T-2 | ✅ `False` |
| B6 | `PositionTracker` 结构满足 `IPositionTracker`：协议一致性探针由 **4 errors 降为 3**（`PositionTracker` 转通过） | `mypy --explicit-package-bases %TEMP%\p007b_proto_conform.py`（`[未入仓-不可重放]`）；剩余 3 条为 `execute_order` 名不符 + 2 个 Q2-C 成员 | DESIGN V10；U-2 判据 | ✅ 4 → 3（`[未入仓-不可重放]`） |
| B7 | Mock 兼容：`MockPositionTracker.get_snapshots() -> list` 与 `MockExecutionSimulator.trade_log = self` 均不受协议修正影响 | 读回 `tests/test_decoupled_engine.py:148/172/239`；全量测试含 Mock 路径全绿（A6） | RESEARCH P29；DESIGN D2「兼容」 | ✅ Mock 未改；`516 passed` 覆盖 |

## 3. 窄化与注解（C）

> **DoR**: IMPL T-4/T-5/T-6 的逐方法别名清单与引用计数已由 AST 统计（48 / 27 处）。**DoD**: 每类 error 清零可归因，且无「用 cast/ignore 换清零」。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | **D4**：`engine_v2` 8 方法窄化完成（`_process_trading_day` / `_force_liquidation` / `_process_pending_orders` / `_try_fallback_order` / `_execute_rebalance` / `_generate_orders_via_policy` / `_execute_next_day_orders` / `_generate_results`），C-1 **43 条**清零 | V2 分文件 engine_v2 = **0**；读回 8 处方法首部（或守卫后）别名 + 合并 assert | DESIGN D4；IMPL T-4 | ✅ engine_v2 = 0（V1 单文件全绿）；8 处别名 + assert 就位 |
| C2 | **A-1 的 7 条**由 `signal_df` 别名消除（3 个方法：`_process_trading_day` / `_try_fallback_order` / `_execute_rebalance`） | Grep `signal_df` in `engine_v2.py` ≥ 7；V1 = 0 | DESIGN D5；IMPL T-4 | ✅ `signal_df` 12 处（赋值/断言/使用） |
| C3 | **C-2/C-3**：`returns_matrix` 别名 + `all_orders: list[PendingOrder]` + `PendingOrder` 导入 | Grep `all_orders: list[PendingOrder] = []` = 1；Grep `    PendingOrder,` in `from core.pending import` 块 = 1 | DESIGN D5；IMPL T-4 | ✅ 注解 1 处；`PendingOrder` 导入 1 处 |
| C4 | **D6**：`engine_v3_vector` 3 方法窄化（5 + 9 + 12 = **26 条**），别名 `signal_matrix` 避免与行向量 `signal` 混淆 | V2 分文件 v3 = **0**；Grep `signal_matrix` = 3（赋值 / assert / 使用）；读回 `run()` 的 `dl` 4 处引用未替换 | DESIGN D6；IMPL T-5；F-I3 | ✅ v3 = 0；`signal_matrix` 3 处；`run()` 内 `self.dl` 4 处未替换 |
| C5 | **D7**：factory **13 条**清零——`Callable[..., Any]` 1 处、9 个包装方法 `cast`、`TYPE_CHECKING` 导入 `BacktestEngineV2` 2 处返回注解去引号 | V2 分文件 factory = **0**；Grep `cast(` = **9**；Grep `Callable[..., Any]` = 1；Grep `if TYPE_CHECKING` = 1 | DESIGN D7；IMPL T-6 | ✅ factory = 0；`cast(` = 9 / `Callable` = 1 / `TYPE_CHECKING` = 1 |
| C6 | 被别名的方法内无 `self.<field>` 残留（保留项除外：`_execute_rebalance` 的 `self._execution_policy` 守卫、`_generate_results` 的 `dm`/`universe`/`pending_queue` 真值分支、`pending_queue` 守卫） | AST 脚本逐方法统计 `[未入仓-不可重放]`；`git diff -U0 core/engine_v2.py core/engine_v3_vector.py` 人工核对 | DESIGN D4「要点 1」；IMPL T-4 | ✅ diff 人工核对：保留项符合；无残留引用 |
| C7 | 未用 `cast` 替代窄化：`engine_v2.py` / `engine_v3_vector.py` 新增 `cast(` = **0**；factory 的 9 处为唯一白名单 | Grep `cast(` 两文件 = 0；factory = 9（同 C5） | DESIGN D4「被拒方案」；A32 | ✅ 两文件 `cast(` = 0 |

## 4. 测试完整性（D）

> **DoR**: 2 项 smoke 的构造（`BacktestConfig()` 默认可用、无需数据目录）已在 IMPL T-0/D8 定稿。**DoD**: RED→GREEN 可复现、计数逐字一致、既有测试零修改。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | `tests/test_mypy_layerb_smoke.py` 存在，恰含 **2** 个 `test_*` 函数 | `pytest --collect-only -q tests/test_mypy_layerb_smoke.py` 末行 = `2 tests collected` | IMPL D8 / T-0 | ✅ 2 项（`pytest` 收集 2 items） |
| D2 | **RED 已取证**：实现前逐条 `DID NOT RAISE`（`ValueError` / `RuntimeError`），非恒真断言 | Step 9 实施前记录 `2 failed, 514 passed`；失败原因逐条抄录 | IMPL §3 RED 测试；RULE-1 | ✅ `2 failed` 已录，但失败形态与预期不同：① `FileNotFoundError: 收盘价文件不存在: data\close.pkl`（setup 先撞数据加载，未到断言）；② `AttributeError: 'NoneType' object has no attribute 'get_snapshots'`。按实际记录（见 §10.0） |
| D3 | **GREEN**：`pytest tests/test_mypy_layerb_smoke.py -q` = `2 passed` | pytest 末行 | DESIGN V5 | ✅ `2 passed` |
| D4 | 全量 `pytest tests -q` = **`516 passed`**（514 + 2），零 failed、零新增 skip | pytest 末行 | DESIGN V4；IMPL §6 | ✅ `516 passed, 82 warnings in 17.83s` |
| D5 | 测试文件数 = **51**（50 + 1） | `(Get-ChildItem tests -Filter 'test_*.py').Count` = 51 | DESIGN V12 | ✅ 51 |
| D6 | 未修改既有测试以凑绿：`tests/` 下仅新增 1 个文件 | `git status --short tests/` 恰 `?? tests/test_mypy_layerb_smoke.py` | IMPL §2.5 排除表 | ✅ 恰 1 个新增文件 |

## 5. 验证口径（E：V1-V12）

> **DoR**: DESIGN §4 的 V1-V12 逐条可执行；V3 已按 Step 6 F-I1 修正为 **8**（L231 随 T-2 转过）。**DoD**: 12 项读数全部记录；允许 `[未入仓-不可重放]` 标注，禁止改断言凑绿。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | **V1**：`mypy --explicit-package-bases core` = `Success: no issues found in 29 source files`，exit 0 | mypy 末行 + exit code | DESIGN V1 | ✅ `Success: no issues found in 29 source files`（exit 0） |
| E2 | **V2**：分文件 engine_v2 **0** / v3 **0** / factory **0** | mypy 按文件计数 | DESIGN V2 | ✅ 0 / 0 / 0（V1 全绿 + 递减末态） |
| E3 | **V3**：`--check-untyped-defs core` = **`8 errors in 2 files`**（engine_v2 6 + data_v3 2） | mypy 末行 + 分文件计数 | DESIGN V3（F-I1 修正）；RESEARCH U-3 注记 | ✅ `Found 8 errors in 2 files`（engine_v2 6 + data_v3 2） |
| E4 | **V4**：全量 `516 passed` | pytest 末行 | DESIGN V4 | ✅ `516 passed` |
| E5 | **V5**：新测试 `2 passed`（同 D3） | pytest 末行 | DESIGN V5 | ✅ `2 passed` |
| E6 | **V6**：`black --check .` exit 0，0 reformatted | 子进程 exit code + 末行 | DESIGN V6 | ✅ `138 files would be left unchanged`（首轮 reformat engine_v2 1 处已按 black 修正） |
| E7 | **V7**：全仓 `# type: ignore` 仍 **1 处**（`tests/test_execution_policy.py:294`） | Grep 计数 = 1 | DESIGN V7；排除表 | ✅ 1 |
| E8 | **V8**：`.github/workflows/tests.yml` 零 diff | `git diff --stat -- .github/workflows/tests.yml` 输出为空 | DESIGN V8；D9 | ✅ 空 |
| E9 | **V9**：`adapter gate mypy-check` verdict = **pass**（exit 0）；**U-006 仍不关闭**（Q4=B），台账不得写成已关闭 | 门禁输出；读回 PROGRESS §2 U-006 行 | DESIGN V9；Q4=B | ✅ `gate[mypy-check] verdict=pass exit=0` |
| E10 | **V10**：协议一致性探针 **4 → 3**（`PositionTracker` 通过；余 `ExecutionSimulator.execute_order` + 2 个 Q2-C 成员） | `mypy %TEMP%\p007b_proto_conform.py` 输出 `[未入仓-不可重放]` | DESIGN V10；U-2 判据 | ✅ 3 errors（ExecutionSimulator + FactorPipeline + FactorCombiner），`PositionTracker` 已通过 |
| E11 | **V11**：改动面 = 4 个 core 文件 + 1 个新测试文件 | `git diff --stat -- core/ tests/` + `git status --short` | DESIGN V11；IMPL T-8 | ✅ 4 core 文件（`251 insertions(+), 128 deletions(-)`）+ 1 新测试 |
| E12 | **V12**：测试文件数 = **51**（同 D5） | `Get-ChildItem` 计数 | DESIGN V12 | ✅ 51 |

## 6. 台账与文档（F）

> **DoR**: 本批四文档齐备；PROGRESS §3.11 已有 Step 1-6 记录。**DoD**: 台账状态与门禁读数同源，措辞不夸大交付。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | `docs/PROGRESS.md` §1.4 P-007 行更新：层 B 完成（93 → 0，三文件 0/0/0）；P3 优先级与 done 状态一致 | 读回该行 | DESIGN D9；IMPL T-8 | ✅ P-007 行已更新：层 A + 层 B 全量收口（93 → 0、盲区 102 → 8、门禁 pass、U-006 按 Q4=B 挂起） |
| F2 | `docs/PROGRESS.md` §3.11 追加 Step 7-10 记录（本文档、Step 8 一致性、Step 9 RED/GREEN、Step 10 审计） | 读回 §3.11 | IMPL T-8 | ✅ Step 7/8/9/10 四行齐备（Step 10 = ADD 审计四阶段 + 取证矩阵 + F-A1/F-A2） |
| F3 | **U-006 仍挂起**：§2 行保留「门禁保持如实 fail」语义并注明「Q4=B 裁决（2026-11-09）；门禁已机械转 pass，但本项不关闭，下一批次重评」 | 读回 PROGRESS §2 U-006 | Q4=B；DESIGN D9 | ✅ §2 U-006 已注记：门禁机械转 pass 但不关闭，口径收紧（残差 8）下一批次重评 |
| F4 | `CHANGELOG.md` `[Unreleased] > Changed` 追加 2 条（D1 fail-fast / D3 守卫）；`Fixed` 追加 2 条（`get_snapshots` 契约 / `trade_log` 缺失声明） | 读回条目 | IMPL T-8；A7 | ✅ `Changed` 3 条（含引擎清零）/ `Fixed` 2 条，全部带（P-007 层 B）标注 |
| F5 | 四文档（RESEARCH / DESIGN / IMPL / CHECKLIST）齐备，相对链接全部可解析 | 4 文件存在；链接校验 0 broken | 模板 §9；Step 8 | ✅ 4 文件存在；Step 8 校验 12 链接 0 broken |
| F6 | 单笔提交，消息为 `fix(P-007): 清理引擎 mypy 93 errors（层 B）`；`git show --stat` 文件数与 E11 一致 | `git log -1 --stat` | IMPL T-8 | ✅ 主提交 **`05af52f`**（11 files，`+2362/−130`：4 core + 1 测试 + 4 文档 + PROGRESS + CHANGELOG，与 E11 一致） |
| F7 | 远端 CI 三 job（3.10 / 3.11 / 3.12）全绿；pytest 读数与本地差异仅来自既有环境差异（层 A 先例：本地 510 → CI 503 passed + 1 skipped），按实际记录 | 远端 run 页面 + job 状态 + 末行 | IMPL §8 | ✅ run [`42666962752`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42666962752) @ `05af52f` **三 job success**：3.10 `509 passed, 1 skipped`（12.96s）/ 3.11 同（15.00s）/ 3.12 同（16.18s）；本地 516 − CI 510 = 6 项差与层 A/P-010 恒定差同构（numba 模块本地 7 项执行、CI `importorskip` 计 1 skip → 净差 6），本批 2 项 smoke 在 CI 真实执行（509 = 507 + 2） |

## 7. 排除与风险（G）

> **DoR**: IMPL §2.5 排除表 8 条。**DoD**: 每条有机械计数或书面引用，红线项零越界。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| G1 | 零新增 `# type: ignore`、零 `try/except pass` 替代 assert | `# type: ignore` = 1（E7）；Grep `except Exception:\s*pass` = 0 | IMPL §2.5；DESIGN D9 | ✅ `type: ignore` = 1；`except Exception: pass` = 0 |
| G2 | `pyproject.toml` 的 `[tool.mypy]` 逐字未改 | `git diff pyproject.toml` 输出为空 | IMPL §2.5；D9 | ✅ 空 |
| G3 | CI workflow 零改动（mypy 步骤仍带短路兜底，不借本批收紧） | 同 E8 | IMPL §2.5；P31 | ✅ 同 E8（空 diff） |
| G4 | **未给 `setup()` 加 `-> None`**（Q3=A；否则会把盲区增量带进本批） | Grep `def setup(self)` in `engine_v2.py` = 1 且**无** `-> None` | Q3=A；DESIGN D9 | ✅ `def setup(self)` = 1；`def setup(self) -> None` = 0 |
| G5 | 未删除 `except Exception: continue`（A-1 的症状放大器，属独立批次） | 读回 `engine_v2.py:292-294` 原样存在 | DESIGN §7；IMPL §2.5 | ✅ 保留（`except Exception as e: ... continue` 原样） |
| G6 | 无 opportunistic 重构：4 个 core 文件之外零改动；文件内无 import 重排 / 命名调整 / 格式重排 | `git diff --stat -- core/` 仅 4 文件；`git diff -U0` 逐行可归属 T-1~T-6 | IMPL §1.3 / §2.5 | ✅ 仅 4 core 文件；diff 逐行归属 T-1~T-6 |
| G7 | `assert` 在 `python -O` 下失效的限制已书面声明（不视为缺陷） | 读回 DESIGN R1 + 本条 | DESIGN R1 | ✅ DESIGN R1 在 |
| G8 | `ITradeLog` 的结构一致性只在「有注解的赋值点」受检的限制已书面声明（当前不新增静态保证） | 读回 DESIGN D2「诚实限制」行 | DESIGN D2；Step 4 F-D1 | ✅ DESIGN D2 在 |

---

## 8. 一致性 Review（Step 8）

- **执行时点**: 四文档完稿后单独执行（2026-11-10，RULE-1）；与各正文非同一次写入
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 机械校验脚本（`p007b_step8_check.py`，`[未入仓-不可重放]`）+ 跨文档计数矩阵 + 零预填扫描 + 断言延续链人工核对

**机械校验读数**：

| 校验项 | 命令/方法 | 读数 |
|--------|-----------|------|
| 四文档互引链接 | 正则提取 + `Path.exists()` | **12 条，0 broken** |
| 验收项总数 | 正则锚定组行（管道 + 组号 + 序号形态） | **54**（A7 / B7 / C7 / D6 / E12 / F7 / G8） |
| 零预填合规 | 54 个验收行中含 `✅` 的行数 | **0**；`[待 Step 9]` 占位 **64 处** |
| `9 errors in 2 files` | 四文档 Grep | IMPL **1** 处——为 §10 F-I1 对旧文本的引用（合法历史引用，非现行口径） |
| `8 errors in 2 files` | 四文档 Grep | DESIGN 1 / IMPL 2 / CHECKLIST 1 = **4 处**（V3 现行口径一致） |
| `仍 9`（修复前） | 四文档 Grep | DESIGN 1（D9 残留 → F-S1）+ IMPL 1（`mypy 仍 93` 子串误匹配，合法）；**修复后 DESIGN = 0**，CHECKLIST 3 处为本节对发现项的自引 |
| `102 − 93 = 9` | 四文档 Grep | RESEARCH **2** 处（U-3 差值指标原始定义；§13.5 处已带 Step 6 注记「批后残差 = 8」，§12.8 为历史收敛出口且已声明「以 §13.5 为最新」） |
| `signal_matrix` | 四文档 Grep | DESIGN 4 / IMPL 7 / CHECKLIST 2；`signals` 旧名 **0** 处残留（F-I3 对齐完成） |
| `L231` | 四文档 Grep | RESEARCH 2 / DESIGN 1 / IMPL 8 / CHECKLIST 1（F-I1 修正链贯通） |
| `516 passed` / `514 passed` | 四文档 Grep | 516：DESIGN 1 / IMPL 7 / CHECKLIST 3；514：均为基线引用 |
| `ITradeLog` / `Q4=B` | 四文档 Grep | 37 / 15 处，无双口径 |
| DESIGN D1-D9 / IMPL T-1~T-8 锚点 | 正则逐条 | **全部存在**（T-0 为 `## 3. T-0：RED 基线` 形态，正则锚定差异，非缺失） |

**发现 1 项（P3，已修复）**：

| ID | 级别 | 发现 | 处理 |
|----|------|------|------|
| **F-S1** | P3 | DESIGN §1 决策总览 **D9 行写「`--check-untyped-defs` 仍 9」**，与同文档 V3（Step 6 F-I1 修正后 = **8 errors in 2 files**）矛盾——Step 6 只修正了 V3/RED-3/T-2 表，漏改 D9 汇总行；验收者按 D9 预期 9 会误判 E3 失败 | 已将 D9 行改为「批后残差 **8**，见 V3」 |

**断言延续链核对**：

| 链路 | 贯通情况 |
|------|----------|
| RESEARCH Q1=A/Q2=A/Q3=A/Q4=B（§13.5 裁决） → DESIGN D1/D2/D9 → IMPL T-1/T-2/§2.5 → CHECKLIST A1-A3/B1-B7/G4 | 贯通（Q4=B 在四处均为「不关闭」，无双口径） |
| RESEARCH A-1（7 条）/ A-2 → DESIGN D1/D3/D5 → IMPL T-1/T-3/T-4 → CHECKLIST A1-A5/C2 | 贯通（fail-fast 位置差异已在 D1「与 RESEARCH 的差异」行披露） |
| RESEARCH B-1/B-2 + Step 4 F-D1（property 形态） → DESIGN D2 → IMPL T-2 → CHECKLIST B1-B7 | 贯通（`trade_log:` 可变属性形态在 CHECKLIST B4 作为**禁止项**出现） |
| RESEARCH C-1~C-5（93 归因） → DESIGN D4-D7 → IMPL T-3~T-6 → CHECKLIST C1-C7 | 贯通（递减算术 93→91→86→39→13→0 与 54/26/13 分文件一致） |
| RESEARCH U-3 判据（9 + Step 6 注记 8） → DESIGN V3 → IMPL V3/RED-3 → CHECKLIST E3 | 贯通（F-I1 修正后四处均为 8；RESEARCH 保留 9 为原始差值定义并注记） |
| DESIGN D8（2 项 smoke） → IMPL T-0/D8 → CHECKLIST D1-D6 | 贯通（RED 现象、GREEN 计数、文件数 51 一致） |
| DESIGN D9（范围边界） → IMPL §8（门禁预期 pass(0)） → CHECKLIST E9/F3（U-006 不关闭） | 贯通（F-S1 修复后无残留学生口径） |
| IMPL §2.5 排除表 8 条 → CHECKLIST G1-G8 | 贯通（红线逐条有机械出口） |

**术语一致性**：

| 术语 | RESEARCH | DESIGN | IMPL | CHECKLIST | 一致 |
|------|----------|--------|------|-----------|------|
| fail-fast | Q1=A 表述 | D1 | T-1 | A1 | ✅ |
| 最小真实化 + `ITradeLog` property | §13.3/§13.5 | D2 | T-2 | B3/B4 | ✅ |
| 批后盲区残差 | 8（注记） | 8（V3/D9） | 8（V3/RED-3） | 8（E3） | ✅ |
| 行为变更数 | — | 2 项（D1/D3） | 2 项 | A 组 + A7 | ✅ |
| 别名 `signal_matrix` | — | D6 | T-5 | C4 | ✅ |

**结论**: 0 项阻断（P1/P2 = 0）；P3 = 1（F-S1 已回写 DESIGN）。54 项验收口径覆盖 D1-D9 / V1-V12 / T-0~T-8 全部，链接 0 broken、零预填合规，可进入 Step 9 实施。

---

## 9. ADD 审计（Step 10）

- **执行时点**: 2026-11-10，Step 9 实施完成后独立执行（RULE-1）；与 Step 9 非同一次写入
- **审查者**: 单 Agent 自查（单视角）（RULE-4）；未引入第二会话/异构基座
- **Iron Law 对账**: `516 passed` 只证明代码做了*某件事*；本节用四阶段证明代码做的是*设计要求的那件事*

### 9.1 四阶段结论

| 阶段 | 审什么（本批） | 结论 | 依据 |
|------|----------------|------|------|
| **Phase 0: Spec 质量门** | DESIGN D1-D9 行为契约 | ✅ 可审计 | D1 守卫条件、D2 协议签名、D3 异常类型与消息、D4-D6 别名与放置规则（含守卫相对位置）、D7 cast 边界、D8 测试构造、D9 范围边界均为可机械核验的条文；V1-V12 全部带命令与期望读数；无「合理处理/适当时机」类模糊词 |
| **Phase 1: 完整性**（design → code） | 每个设计元素在代码中有实现吗 | ✅ 全实现 | D1→[engine_v2.py:169-177]（F-S9-1 收紧条件）；D2→[interfaces.py] TYPE_CHECKING L17-18 / ITradeLog L200-205 / trade_log property L251-254 / get_snapshots L287；D3→engine_v2 L766-771 守卫 + L769-770 别名；D4/D5→8 方法别名（engine_v2 L313-318 / L374-377 / L421-426 / L499-509 / L552-563 / L655-659 / L745-750）；D6→v3 三方法（L259-260 / L288-291 / L337-348）；D7→factory Callable L98 / 9 cast / TYPE_CHECKING L33-34；D8→2 项 smoke；D9→变更面恰 4 core + 1 test（E1） |
| **Phase 2: 忠实度**（双向对照） | 实现与设计一致吗 | ✅ 无静默偏离 | 递减表 6 步逐格命中（§10.0）；接口先真后窄的顺序（T-2→T-3）按 IMPL §1.3 执行；V1-V12 全部按原文执行且读数达标。**2 项偏离均已登记回写**：F-S9-1（守卫条件收紧，DESIGN D1 + IMPL T-1 双写）、F-S9-2（black 折行，F-I4 预案内）——非实现者自作主张 |
| **Phase 3: 忠实度逆查**（code → design） | 代码每个行为都有设计依据吗 | ✅ 0 项设计外 | E4 盲区扫描：379 改动行（251+/128−）逐一归属——engine_v2 29 个 hunk 全部映射 T-1/T-3/T-4/F-S9-1/F-S9-2；v3 6 个 hunk → T-5；factory 7 个 hunk → T-6；interfaces 5 个 hunk → T-2。无派生需求产生（Step 8 登记闭环保持 0） |
| **Phase 4: 语义** | 机械合规但意图错位吗 | ✅ 意图达成（1 项已知限制） | D1 意图 = 阻断 P34/P35「默认构造 + 直接 setup() → 静默空回测」；F-S9-1 豁免的仅是「注入 pipeline+combiner（自带信号源）」的工作流，P34 缺陷面仍 fail-fast，T-B1 为证。**已知限制（P3）**：注入豁免路径若调用方忘记注入 `_composite_signal`，仍会静默空回测——守卫对此不可见；与 U-3（`--check-untyped-defs` 残差 8）并列，留待下一批次评估，不阻断本批 |

### 9.2 取证矩阵（RULE-6）

| 取证手段（等级） | 覆盖项 | 结果 |
|---|---|---|
| mypy 递减 6 步分文件读数（E1） | Phase 2 全部 + C1-C5/E1-E3 | ✅ 93→91→86→39→13→0，逐格命中（§10.0 表） |
| 门禁链统一 session `factorv3-p007-mypy-layerb-20261110`（E1） | V9 + IMPL §8 | ✅ probe / unit-tests / black-check / mypy-check 4 gate 全 pass；`replay: 4 rows OK (seq monotonic, schema parseable)` |
| pytest 全量 + smoke（E1） | A4/A6/D3/D4/E4/E5 | ✅ `516 passed, 82 warnings`；smoke `2 passed` |
| pytest 既有用例（豁免路径行为，E1） | A6 + F-S9-1 语义 | ✅ `test_real_ashare_backtest` / `test_real_ashare_strict_validation` 全绿（13 用例恢复） |
| git diff --numstat / --porcelain（E1） | D9/E11/G6/Phase 3 | ✅ 4 core（251+/128−）+ 1 新测试 + 5 docs；无其他路径改动 |
| git diff hunk 头归属扫描（E4，扫描范围：全部 47 个 hunk / 379 改动行） | Phase 3 必要性 | **发现 0 项设计外改动**（47/47 可归属 T-1~T-6 + F-S9-1/S9-2） |
| 静态读码行号（E3 @`05af52f`，行号随主提交冻结） | Phase 1 的 D1-D9 → 代码映射 | ✅ 见 9.1 Phase 1 行号列（如 `engine_v2.py:169-177@05af52f`） |
| 黑盒异常行为验证（E2，场景=守卫两端：默认路径抛错 / 注入路径豁免） | A1/A2/D2 + F-S9-1 | ✅ T-B1（默认路径 `ValueError` 含 `factor_files`、`dm` 保持 None）+ 13 既有用例（豁免路径）双端验证；场景覆盖守卫正反两面，无场景选择偏差 |
| 盲区口径复扫（E4，扫描范围：`--check-untyped-defs` 残差构成） | E3/V3 | ✅ 8 = engine_v2 6 + data_v3 2，与 F-I1 修正后预期一致；无新盲区进入门禁口径 |
| 推测/未执行（E5） | —— | 无（本节结论不含 E5 证据） |

### 9.3 发现项

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-A1 | P3 | **豁免路径残留盲区**：注入 `factor_pipeline` + `factor_combiner` 的调用方若忘记注入 `_composite_signal`，`run()` 仍会静默空回测（守卫设计上只看 `factor_files` 与注入组件，不看信号是否就绪） | 不阻断（P34/P35 缺陷面已封口，豁免面属注入式工作流的自我责任）；登记为已知限制，与 U-3 残差 8 一并留待下一批次评估（§11） |
| F-A2 | P3 | 发现记录核查：F-S9-1（守卫过宽 vs 注入式测试工作流）与层 A/P-010 的失效模式不同类（非「Grep 静默空匹配」类工具陷阱、非「默认值语义」类数据缺口），**不构成跨批次复发模式**，不新增 `docs/discoveries/` 条目 | 书面声明，闭环 |

### 9.4 审计结论

- **P1: 0；P2: 0；P3: 2**（F-A1 已知限制、F-A2 闭环声明）
- Iron Law 对账：四阶段均通过——代码做的正是 DESIGN 要求的事，且仅有 2 项已披露的行为变更（D1/D3）
- **Step 10 ADD 审计通过**，可进入提交与远端复核

---

## 10. 验收结论（Step 9 后回填）

### 10.0 Step 9 实施记录

- **执行时点**: 2026-11-10；解释器 3.12.10 / mypy 2.1.0 / pytest 9.0.3 / black 26.5.0（E1）
- **执行顺序**: T-0 RED → T-1 → T-2 → T-3 → T-4 → T-5 → T-6 → T-7 全量验证（与 IMPL §1.2 一致，未调序）

**T-0 RED（实施前）**：

| 项 | 读数 |
|----|------|
| mypy 门禁口径 | `Found 93 errors in 3 files`（engine_v2 54 / v3 26 / factory 13） |
| mypy 盲区口径 | `Found 102 errors in 4 files` |
| 新 smoke 测试 | `2 failed`：① `FileNotFoundError: 收盘价文件不存在: data\close.pkl`（默认 `./data` 无 pkl，setup 在守卫前先撞数据加载）；② `AttributeError: 'NoneType' object has no attribute 'get_snapshots'`。**与 IMPL §3 预期「DID NOT RAISE」形态不同，按实测记录** |
| 全量测试 | `514 passed`（未含新测试时；含新测试为 2 failed, 514 passed） |
| 测试文件数 / `type: ignore` | 50 / 1 |

**递减实测（与 IMPL §6 逐格比对）**：

| 序 | 动作 | 期望总数 | 实测总数 | 分文件（engine_v2 / v3 / factory） |
|----|------|----------|----------|-----------------------------------|
| 1 | T-1 D1 fail-fast | 93 | **93** | 54 / 26 / 13 |
| 2 | T-2 D2 接口 | 91 | **91** | 52 / 26 / 13 |
| 3 | T-3 D3 守卫 | 86 | **86** | 47 / 26 / 13 |
| 4 | T-4 engine_v2 其余 | 39 | **39** | 0 / 26 / 13 |
| 5 | T-5 v3 | 13 | **13** | 0 / 0 / 13 |
| 6 | T-6 factory | 0 | **0** | 0 / 0 / 0 |

**实施发现**：

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S9-1** | **P2** | **D1 守卫范围过宽**：无条件 `not factor_files → ValueError` 使 13 个既有用例失败（`test_real_ashare_backtest` 4 failed + `test_real_ashare_strict_validation` 9 errors）——这些用例注入 `factor_pipeline` + `factor_combiner`、以空 `factor_files` 调 `setup()`，随后手工注入 `_composite_signal` | 守卫条件收紧为「`factor_files` 为空 **且** 未注入 pipeline **且** 未注入 combiner」；默认路径缺陷（P34）仍 fail-fast，T-B1 仍绿，13 个用例恢复。已回写 DESIGN D1（含实施注记）与 IMPL T-1 |
| F-S9-2 | P3 | black 要求 `execute_pending_order(...)` 调用折为单行（别名后行宽收敛） | 按 black 实测调整；V6 复检 `138 files would be left unchanged` |

**GREEN（Step 9 末态）**：mypy `Success: no issues found in 29 source files`；盲区 `8 errors in 2 files`；`516 passed, 82 warnings`；black 0 reformatted；`type: ignore` 1；测试文件 51；门禁 `verdict=pass`。

### 10.1 验收统计

| 类别 | 总数 | 通过 | 失败 | 待办 |
|------|------|------|------|------|
| A 行为变更与真实缺陷 | 7 | 7 | 0 | 0 |
| B 接口契约 | 7 | 7 | 0 | 0 |
| C 窄化与注解 | 7 | 7 | 0 | 0 |
| D 测试完整性 | 6 | 6 | 0 | 0 |
| E 验证口径 | 12 | 12 | 0 | 0 |
| F 台账与文档 | 7 | 7 | 0 | 0 |
| G 排除与风险 | 8 | 8 | 0 | 0 |
| **总计** | **54** | **54** | **0** | **0** |

> **统计口径（RULE-2）**：上表来自本文件逐项独立核对（54 行逐行标记），非事后汇总推算；逐行 `总数 = 通过 + 失败 + 待办` 成立，总计行按列求和成立（7+7+7+6+12+7+8 = 54；7+7+7+6+12+7+8 = 54）。F7 已于 docs 回填提交前随远端 run `42666962752` 三 job success 闭环。
> **通过门槛**：P1/P2 = 0 ✅（Step 1-10 累计：P1 1 项 / P2 2 项 / P3 11 项全部修复或闭环）；`mypy-check` 转 pass 属**预期**，但 U-006 仍按 Q4=B 挂起，不计为验收缺陷，也不写成「U-006 已关闭」。

### 10.2 验收决定

- [x] **验收通过**：所有 P1 项通过，无阻塞性问题（**54/54 全 ✅**；远端 CI run `42666962752` 三 job success 已闭环）

### 10.3 签字

| 角色 | 签字 | 日期 |
|------|------|------|
| 实施者 | 单 Agent 自查（RULE-4） | 2026-11-10 |
| 审查者 | 单 Agent 自查（ADD 审计，§9；RULE-4） | 2026-11-10 |

---

## 11. 后续行动

| 行动 | 责任人 | 期限 | 状态 |
|------|--------|------|------|
| Step 8 一致性 Review（独立 pass） | 单 Agent 自查 | Step 8 | ✅ 已完成（F-S1 已回写） |
| Step 9 实施（T-0~T-8，含 RED/GREEN） | 单 Agent 自查 | Step 9 | ✅ 已完成（mypy 0 / 516 passed / black 绿 / 门禁 pass） |
| Step 10 ADD 审计 + 台账 + 提交推送 CI | 单 Agent 自查 | Step 10 | ✅ 全部完成（审计 + 台账 + 主提交 `05af52f` + CI `42666962752` 三 job 绿 + docs 回填） |
| U-006 重评（Q4=B：下一批次启动时） | — | 下一批次 | `[挂起]`（含 U-3 残差 8 与 F-A1 豁免路径盲区一并评估） |
| U-3 `setup()` 盲区（残差 8，另立批次） | — | 下一批次 | `[挂起]` |
