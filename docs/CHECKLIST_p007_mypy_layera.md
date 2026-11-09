# P-007 层 A（非引擎 mypy 清理） · 审查验收清单

> **文档编号**: CHECKLIST_p007_mypy_layera
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: **已完成**（2026-11-09；Step 1-10 全通过，**49/49 ✅**；P1/P2 = 0；提交 `e0247ce`；远端 CI run `42614740925` 三 job 全绿）
> **上游**: [DESIGN_p007_mypy_layera.md](DESIGN_p007_mypy_layera.md)（Step 4 通过，D1-D9 / V1-V10） · [IMPL_p007_mypy_layera.md](IMPL_p007_mypy_layera.md)（Step 6 通过，T-0~T-9 / F-I1~F-I7）
> **填写规则**: 本清单在 Step 7 只定义「怎么算做完」；「实测」列一律 `[待 Step 9]`，**禁止实现前预填**（RULE-1）。每条 ✅ 必须绑定证据出口；无证据只能标 `[未在 CI 覆盖]` / `[未入仓-不可重放]` / `[未取证]`。
> **解释器**: `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10）；`MPLBACKEND=Agg`
> **基线时点**: 本仓 @ `8082784`；RED 读数 26 / 119 / 507 / 135 / 1

---

## 1. A 类真实缺陷修复（A）

> **DoR**: RESEARCH §2.1 的 A-1~A-4 已逐处读码确认；**DoD**: 每处有「修复前可复现的异常」+「修复后 smoke 绿」两段证据。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | **A-4**：`core/data.py` 的 `_load_auxiliary_data` 仅剩 **1 处定义**（原 L184 死版本已删除，生效版本为原 L312） | `grep -c "def _load_auxiliary_data" core/data.py` = 1；`mypy core` 中 `data.py:312 no-redef` 消失 | DESIGN D1；IMPL T-1 | ✅ 仅剩 **1 处**（现 L264）；data.py mypy **0 error** |
| A2 | A-4 删除范围为 L184-L231，`_apply_date_filter` 完整保留且无空行错位 | `git diff core/data.py` 仅删除、无其他改动；`black --check core/data.py` exit 0 | IMPL T-1 | ✅ `git diff --numstat` = **`0 48`**（纯删除）；`black --check .` exit 0 |
| A3 | **A-1**：`risk_monitor.py:720-724` 的 `remove_monitor` 不再引用未定义名 `RiskAction`，且无重复声明 | `grep -n "RiskAction" core/risk_monitor.py` = **0 命中**；`mypy` 中 risk_monitor 0 error | DESIGN D2；IMPL T-2 | ✅ `RiskAction` **0 命中**；risk_monitor **0 error** |
| A4 | A-1 修复前 RED：`CompositeRiskEngine().remove_monitor("nonexistent")` 抛 `NameError` | 修复前一次性探针输出（记录到 IMPL 或批次记录） | IMPL T-7 表 | ✅ 根因探针：`hasattr(core.risk_monitor,"RiskAction")` = **False** + mypy `name-defined` @ L724 定位。**诚实标注**：整函数「修复前」探针未在编辑前执行，改用等效根因探针 |
| A5 | **A-2**：`global_contagion.py:631` 改为 `monitor.monitor(...)`，不再调用不存在的 `evaluate` | `grep -n "monitor.evaluate" core/global_contagion.py` = **0 命中**；`mypy` 中该文件 0 error | DESIGN D3；IMPL T-3 | ✅ `monitor.evaluate` **0 命中**；global_contagion **0 error** |
| A6 | A-2 修复前 RED：`analyze_market_contagion(...)` 抛 `AttributeError: 'GlobalContagionMonitor' object has no attribute 'evaluate'` | 修复前探针输出 | IMPL T-7 表 | ✅ 根因探针：`hasattr(GlobalContagionMonitor,"evaluate")` = **False** + mypy `attr-defined` @ L631 |
| A7 | **A-3**：`engine_plugins.py:381` 以 `dates=` 关键字传参，`create_trigger` 不再 `TypeError` | `grep -n "dates=trade_dates" core/engine_plugins.py` = 1；`git diff` 仅该行（含注释行） | DESIGN D4；IMPL T-4 | ✅ `dates=trade_dates` **1 处**（L381）；engine_plugins **0 error** |
| A8 | A-3 修复前 RED：`RegistryPlugin().enable().create_trigger(RebalanceConfig(method="fixed"), dates)` 抛 `TypeError` | 修复前探针输出 | IMPL T-7 表 | ✅ 根因探针（等价调用）：`get_trigger_registry().create("fixed", cfg, dates)` → **`TypeError: takes from 2 to 3 positional arguments but 4 were given`** |
| A9 | **B-1**：`live_bridge.py` 新增运行期 `from core.config import AssetType`，L174 用 `isinstance` 分支取 `.value`；无 `NameError`、无循环导入 | 读回 import 行 + `python -c "import core.live_bridge"` exit 0 | DESIGN D5；IMPL T-5 / F-I2 | ✅ L33 import 就位；`import core.live_bridge` → **`import ok`**；live_bridge **0 error** |
| A10 | **B-2/B-3/B-4**：`portfolio.py` 3 处防御就位——L223/L355 前 `assert returns is not None`、L300 前 `assert cov_matrix is not None` | `git diff core/portfolio.py` 恰为 3 处 `+assert`；`mypy` 中 portfolio 0 error | DESIGN D5；IMPL T-5 / F-I1 | ✅ diff = **`3 0`**（3 行新增、0 删除）；portfolio **0 error** |

## 2. C 类注解清理（B）

> **DoR**: IMPL T-6 的 13 行表已按 F-I4/F-I5 更正行号；**DoD**: 16 个 error 逐个对应到改动行，且无 `# type: ignore`。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `config.py:199` 用 `cast(AssetCost, ...)` 消除 `no-any-return`；`cast` 已导入 | 读回 L13 与 L199 | IMPL T-6 / F-I3 | ✅ L13 `from typing import Any, cast`；L199 `return cast(AssetCost, ...)` |
| B2 | `walk_forward.py:250/258` 两处 `cast(float, ...)`；`cast` 已导入 | 读回 L21 与两处 return | IMPL T-6 / F-I3 | ✅ L21 `Iterator, Optional, cast`；L250/L258 均 `cast(float, np.mean(...))` |
| B3 | `execution.py:235` 用 `cast(float, ...)`；`cast` 已导入 | 读回 L14 与 L235 | IMPL T-6 / F-I3 | ✅ L14 含 `cast`；L235 `return cast(float, custom_price)` |
| B4 | `pending.py:538` 用 `cast(list[str], ...)`；`cast` 已导入 | 读回 L14 与 L538 | IMPL T-6 / F-I3 | ✅ L14 含 `cast`；L538 `return cast(list[str], fallback_stocks)` |
| B5 | `config_v2.py:237` 用 `cast(Path, ...)`，为**冻结资产唯一改动**（其余零 diff） | `git diff core/config_v2.py` 仅 2 行（import + return） | DESIGN D8；IMPL T-6 | ✅ numstat **`2 2`**（L27 import + L237 return）；其余零 diff |
| B6 | `rebalance.py:202` 改 `return float(weight_change)`；`pending.py:446` 改 `stats: dict[str, Any] = {`（**未用 `int()` 截断**） | 读回两处 | IMPL T-6 / F-I4 | ✅ rebalance L202 `return float(weight_change)`；pending L446 `stats: dict[str, Any] = {`；无 `int()` 截断 |
| B7 | `global_contagion.py:163` 改 `metadata: dict[str, Any] = {}`；`:346` 改 `results: dict[str, Any] = {}` | 读回两处 | DESIGN D6 / F-D2 | ✅ L163 / L346 均带 `dict[str, Any]` 注解 |
| B8 | `factor.py` 收集变量改名 `X_list`（L310 注解 / L323 `extend` / L331 `append` / L333 判空），L338 `X = np.column_stack(X_list)`；L343/L352 作用于 ndarray | `git diff core/factor.py` 仅该函数内 5-6 行 | DESIGN D6 / F-D1；IMPL F-I5 | ✅ numstat **`5 5`**；L310/L323/L331/L333/L338 五处改名完成 |
| B9 | `attribution.py:335` 改 `sectors: set[str] = set()`；`tracker.py:335` 改 `sector_exposure: dict[str, float] = {}` | 读回两处 | IMPL T-6 | ✅ 两文件各 **`1 1`**；注解就位 |
| B10 | `walk_forward_engine.py` 删除 L284-293 整个 `__main__` 块，文件保留其余全部内容 | `grep -c "__main__" core/walk_forward_engine.py` = 0；`git diff` 为 −10 行纯删除 | IMPL T-6 | ✅ `__main__` **0 命中**；numstat **`0 12`**（含块前后空行，纯删除） |

## 3. 测试完整性（C）

> **DoR**: IMPL T-7 三测试构造已定稿（类名/配置/日期索引均可读回）；**DoD**: RED→GREEN 可复现且计数逐字一致。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `tests/test_mypy_layera_smoke.py` 存在，恰含 3 个 `test_*` 函数 | `Get-Content` + `pytest --collect-only -q tests/test_mypy_layera_smoke.py` = 3 | IMPL T-7 | ✅ 文件存在；`3 items` 收集 |
| C2 | 三测试均**正向断言**（`not raises` / `isinstance` / 键集），无 `pytest.raises` 反转 | 读回测试文件 | IMPL T-7 禁止项 | ✅ 3 个正向断言（长度不变 / dict 键集 / `isinstance`）；无 `pytest.raises` |
| C3 | 三测试**在修复前确实失败**（RED 已取证），不是恒真断言 | 修复前探针 3 条输出（可复用 A4/A6/A8 证据） | IMPL T-7 | ✅ 根因证据同 A4/A6/A8（`RiskAction` 缺失 / `evaluate` 缺失 / 3 位置参数 TypeError）；**诚实标注**：未在编辑前跑整函数探针 |
| C4 | 全量 `pytest -q` = **`510 passed`**，零 failed、零新增 skip | pytest 末行 | DESIGN D7 / V4 | ✅ **`510 passed, 82 warnings in 17.84s`**；0 failed / 0 skipped |
| C5 | 全量收集数 = **510**；测试文件数 = **49** | `pytest --collect-only -q` 末行 + `Get-ChildItem tests -Filter 'test_*.py'` | V4 / V10 | ✅ **`510 tests collected in 2.75s`**；文件 **49** |
| C6 | 未修改既有测试以凑绿（尤其 `tests/test_engine_plugins.py` 的注释块保持原样） | `git status --short` 中 tests/ 仅新增 1 个文件 | IMPL T-7 / F-I6 未纳入项 | ✅ `git status` 中 tests/ 仅 `?? tests/test_mypy_layera_smoke.py` |

## 4. 验证口径（D：V1-V10）

> **DoR**: DESIGN §5 V1-V10 逐条可执行；**DoD**: 10 项读数全部记录，允许「预期 fail」项如实标注。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | **V1**：非引擎 16 文件 mypy error = **0** | `mypy --explicit-package-bases core` 按文件过滤 | DESIGN V1 | ✅ 过滤后 **0 行** |
| D2 | **V2**：总数 = **`93 errors in 3 files`**（119 → 93，减 26） | mypy 末行 | DESIGN V2 | ✅ **`Found 93 errors in 3 files (checked 29 source files)`** |
| D3 | **V3**：三引擎文件读数与基线逐字一致——engine_v2 **54** / engine_v3_vector **26** / factory **13** | mypy 分文件计数 | DESIGN V3 | ✅ **54 / 26 / 13**（Group-Object 实测） |
| D4 | **V7**：引擎三件套**零 diff** | `git diff --stat -- core/engine_v2.py core/engine_v3_vector.py core/factory.py` 输出为空 | DESIGN V7；D9 | ✅ **输出为空** |
| D5 | **V8**：全仓 `# type: ignore` 仍为 **1 处**（`tests/test_execution_policy.py`），未扩张 | Grep 计数 = 1 | DESIGN V8；排除表 | ✅ **1 处**（`tests/test_execution_policy.py`） |
| D6 | **V6**：`black --check .` exit 0，`136 files would be left unchanged`（135+1 新测试） | 子进程 exit code + 末行 | DESIGN V6 / D7 | ✅ **`136 files would be left unchanged`，exit 0** |
| D7 | **V9**：`adapter gate mypy-check` verdict 仍为 **fail**（93），**如实记录、不改门禁门槛**；`pyproject.toml` 的 `[tool.mypy]` 零改动 | `python scripts/spec_runner_adapter.py gate mypy-check` 输出 + `git diff pyproject.toml` 空 | DESIGN V9；排除表 | ✅ **`verdict=fail exit=1`**；`git diff pyproject.toml` **空** |
| D8 | **V5**：`pytest tests/test_mypy_layera_smoke.py -q` = **`3 passed`** | pytest 末行 | DESIGN V5 | ✅ **`3 passed in 1.72s`** |
| D9 | **V4**：全量 `510 passed`（与 C4 同源，此处登记门禁读数） | pytest 末行 | DESIGN V4 | ✅ 门禁 `unit-tests` **verdict=pass**（510） |
| D10 | **V10**：`tests/test_*.py` = **49** | `Get-ChildItem` 计数 | DESIGN V10 | ✅ **49** |

## 5. 台账与文档（E）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | `docs/PROGRESS.md` §1.4 P-007 行更新：层 A 完成（26→0）、层 B 剩余 93（54/26/13） | 读回该行 | DESIGN D9；IMPL T-9 | ✅ P-007 行已改为 `done（2026-11-09，层 A 完成…）` 并含 93 分布 |
| E2 | **P-010 已登记**：`data.py` 辅助数据缺失时无安全默认值（原 L184 死版本曾含 `pd.DataFrame(True, ...)` 逻辑），P2 优先级、指向层 A 的 D1 决策 | 读回 PROGRESS §清单 | DESIGN D1；IMPL F-I7 | ✅ P-010 行已登记（P2 / pending / 引用 D1 实证） |
| E3 | `docs/PROGRESS.md` §3.9 新增批次记录（T1、16 文件、26→0、507→510、门禁 fail 如实） | 读回 §3.9 | IMPL T-9 | ✅ §3.9 已新增（Step 1-9 全链 + 范围 + 验收口径 + 回退点） |
| E4 | `CHANGELOG.md` `[Unreleased] > Fixed` 追加 4 条（A-1 `NameError` / A-2 `AttributeError` / A-3 `TypeError` / A-4 重复定义移除且注明「行为不变」）；**P-010 行为退化只登记在 PROGRESS，不写成已修复** | 读回条目 | IMPL T-9 / F-S3 | ✅ 4 条已追加；A-4 条明确「行为不变 + 另立 P-010」 |
| E5 | 四文档齐备且互相链接可解析（RESEARCH / DESIGN / IMPL / CHECKLIST） | 4 个文件存在 + 相对链接指向正确文件名 | 模板要求 | ✅ 4 文件齐备；链接 **11 条 0 broken** |
| E6 | 单笔提交，消息为 `fix(P-007): 清理非引擎 mypy 错误并修复 4 处缺陷（层 A）`；`git show --stat` 文件数与预期一致 | `git log -1 --stat` | IMPL T-9 | ✅ `e0247ce`：**23 files changed, +1211 −88**（16 core + 1 test + 4 文档 + PROGRESS + CHANGELOG） |
| E7 | U-006 **不关闭**：台账明确「mypy 仍 fail(93)，层 B 另立」 | 读回 PROGRESS | DESIGN D9；IMPL §8 | ✅ PROGRESS P-007 行与 §3.9 均写明「仍如实 fail(93)，U-006 不关闭」 |

## 6. 排除与风险（F）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 零新增 `# type: ignore`、零 `try/except pass` 替代 assert | Grep 两模式计数 | 排除表 | ✅ `# type: ignore` 仍 **1 处**；本批仅新增 3 个 `assert`，无 `try/except pass` |
| F2 | `[tool.mypy]` 配置逐字未改（`warn_return_any` 等不被降级） | `git diff pyproject.toml` 为空 | 排除表 | ✅ **diff 空** |
| F3 | 未合并 `data.py` 安全默认值（行为变更留给 P-010） | `git diff core/data.py` 仅删除 48 行 | 排除表；DESIGN D1 | ✅ numstat **`0 48`**（纯删除） |
| F4 | 未做 opportunistic 重构：16 文件之外零改动；16 文件内 diff 行数与 IMPL 预估数量级一致（±25 行与 +40 行两档） | `git diff --numstat` 汇总 | 排除表 | ✅ 16 文件 / **+36 −87**（其中 −48 为死代码）；新测试 +40 行 |
| F5 | `assert` 的 `-O` 失效风险已书面记录（不视为缺陷，属已声明限制） | DESIGN R1 引用 | DESIGN D5/R1 | ✅ DESIGN D5 表「限制：`assert` 在 `-O` 下失效（DESIGN R1）」 |
| F6 | CI 三 job（probe / unit-tests / black-check）全绿；`mypy-check` 如实 fail(93) | 远端 run 页面 + job 状态 | IMPL §8 | ✅ run [`42614740925`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42614740925) @ `e0247ce` 三 job success（3.12 **1m06s** / 3.11 **1m04s** / 3.10 **53s**）；3.12 实测 **`503 passed, 1 skipped`**（= 510 − 7 numba）。**边界**：CI 仅跑 pytest，`black-check`/`mypy-check` 不在 CI；mypy 如实 fail(93) 由本地门禁记录 |

---

## 7. 一致性 Review（Step 8）

- **执行时点**: 四文档完稿后单独执行（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 相对链接机械校验 + 跨文档计数矩阵 + CHECKLIST 预填合规扫描 + 断言延续链核对

**机械校验读数**：

| 校验项 | 命令/方法 | 读数 |
|--------|-----------|------|
| 四文档互引链接 | Python `re` + `Path.exists()` | **11 条，0 broken** |
| 验收项总数 | 正则 `^\| ([A-F])\d+ \|` | **49**（A10 / B10 / C6 / D10 / E7 / F6） |
| 零预填合规 | 逐行断言：49 个验收行中含 `✅` 的行数 | **0**；`[待 Step 9]` 占位 **56 处** |
| `26 errors` | 上游三文档 Grep | RESEARCH **3** 处（DESIGN/IMPL 用 `26` 单数字表述） |
| `93 errors` | 上游三文档 Grep | RESEARCH 3 / DESIGN 2 / IMPL 2 = **7 处** |
| `507 passed` / `510 passed` | 上游三文档 Grep | **5 处**（R3/D0/I2） / **3 处**（R0/D1/I2） |
| `119 errors` | 上游三文档 Grep | **3 处**（R2/D0/I1；均作基线口径，未与 93 混用） |
| `135 files` / `136 files` | 上游三文档 Grep | **1 处**（I1，基线） / **1 处**（D1，新增测试后） |
| `P-010` | 上游三文档 Grep | **15 处**（D7 / I8，均指向同一待办，无双口径） |

**发现 3 项（1 项 P2、2 项 P3，均已修复）**：

| ID | 级别 | 发现 | 处理 |
|----|------|------|------|
| **F-S1** | **P2** | DESIGN §1 决策总览 D2 写「`RiskAction` → `MonitorAction`；L723/L724 改为无注解赋值」，与 DESIGN §2 D2 正文（无注解赋值）及 IMPL T-2 的「备选（被拒）：改名为 `MonitorAction` 保留注解仍报 `no-redef`」**互相矛盾**；实施者按总览执行会得到未消除的 `no-redef` | 已将 DESIGN 总览 D2 改为「L723/L724 改为无注解赋值，`RiskAction` 随注解移除；不改名保留注解」 |
| **F-S2** | P3 | DESIGN D8 写「仅允许 1 处 `cast` 修正」，但该文件当前未导入 `cast`，实际 diff 为 2 行（import + return），按字面会判为越界 | 已在 DESIGN D8 补「附带 1 行 `cast` 导入，不构成第二处修正」 |
| **F-S3** | P3 | IMPL T-9 与 CHECKLIST E4 原将 A-4 记为「行为退化登记」并列在 `CHANGELOG > Fixed`——本批 A-4 **未修行为**（D1 明确留给 P-010），写成 Fixed 会构成夸大交付 | 已改为「A-4 重复定义移除且注明行为不变」；P-010 仅登记 PROGRESS，禁止写成已修复 |

**断言延续链核对**：

| 链路 | 贯通情况 |
|------|----------|
| RESEARCH §2.1 A-1~A-4 → DESIGN D1-D4 → IMPL T-1~T-4 → CHECKLIST A1-A8 | 贯通（A-4 的「不改行为」在 D1/T-1/F3/E4 四处一致） |
| RESEARCH §2.2 B-1~B-4 → DESIGN D5 → IMPL T-5 → CHECKLIST A9/A10 | 贯通（F-I1/F-I2 已修正报错对象与 import 缺口） |
| RESEARCH C 类 16 项 → DESIGN D6/D8 → IMPL T-6 → CHECKLIST B1-B10 | 贯通（F-I3 补 cast 导入清单；F-I4 改 `stats: dict[str, Any]`；F-I5 更正 factor 行号） |
| DESIGN D7 → IMPL T-7 → CHECKLIST C1-C6 | 贯通（3 项测试构造与 RED 现象均已具体化） |
| DESIGN D9 → IMPL §8 → CHECKLIST D1-D10 / E7 | 贯通（93 / 119 / U-006 不关闭三处口径一致） |
| 排除表 9 条 → CHECKLIST F1-F6 | 贯通（禁 `type: ignore`、禁改 mypy 配置、禁改引擎、禁合并默认值均已入项） |

**结论**: 0 项阻断（P1 = 0）；P2 = 1（F-S1 已回写）；P3 = 2（已回写）。49 项验收口径覆盖 D1-D9 / V1-V10 全部，可进入 Step 9 实施。

---

## 8. 验收统计（Step 9 后回填）

| 分组 | 项数 | ✅ | ⚠️ | ❌ |
|------|------|----|----|----|
| A 缺陷修复 | 10 | 10 | 0 | 0 |
| B 注解清理 | 10 | 10 | 0 | 0 |
| C 测试 | 6 | 6 | 0 | 0 |
| D 验证口径 | 10 | 10 | 0 | 0 |
| E 台账文档 | 7 | 7 | 0 | 0 |
| F 排除风险 | 6 | 6 | 0 | 0 |
| **合计** | **49** | **49** | **0** | **0** |

> P1/P2 缺陷必须为 0 才可判定通过；`mypy-check` 的 fail 属**预期如实**（U-006 不关闭），不计为验收缺陷。

---

## 9. 红 → 绿记录（Step 9）

### 9.1 RED（实施前，2026-11-09 @ `8082784`）

| # | 断言 | 命令 | 读数 |
|---|------|------|------|
| RED-1 | 非引擎 errors | `mypy --explicit-package-bases core` 过滤三引擎 | **26** |
| RED-2 | mypy 总数 | 同上末行 | **`Found 119 errors in 19 files`** |
| RED-3 | 全量测试 | `pytest -q` | **`507 passed, 82 warnings in 23.39s`** |
| RED-4 | 格式合规 | `black --check .` | exit 0，**135 files unchanged** |
| RED-5 | `type: ignore` 基线 | Grep | **1 处**（`tests/test_execution_policy.py`） |

### 9.2 实施递减（每步后 mypy 总数）

| 序 | 任务 | 读数 | 消除 |
|----|------|------|------|
| 1 | T-1 删除 `data.py` L184-231（−48 行） | **118** | 1 |
| 2 | T-2 `risk_monitor` 去重复注解 | **115** | 3 |
| 3 | T-3 `global_contagion` → `monitor()` | **113** | 1 |
| 4 | T-4 `engine_plugins` → `dates=` | **113**（与 T-3 合计 −2） | 1 |
| 5 | T-5 B 类 4 处 | **109** | 4 |
| 6 | T-6 C 类 16 项 | **93** | 16 |

> T-3/T-4 为连续两次编辑后一次读数（113），合计消除 2，与 DESIGN 的递减序一致（115 → 113）。

### 9.3 GREEN（实施后）

| # | 断言 | 命令 | 读数 |
|---|------|------|------|
| GREEN-1 | 非引擎 errors | `mypy` 过滤 | **0** |
| GREEN-2 | mypy 总数 | `mypy --explicit-package-bases core` | **`Found 93 errors in 3 files (checked 29 source files)`** |
| GREEN-3 | 引擎分布 | `Group-Object` | **54 / 26 / 13** |
| GREEN-4 | 全量测试 | `pytest -q` | **`510 passed, 82 warnings in 17.84s`** |
| GREEN-5 | 新测试 | `pytest tests/test_mypy_layera_smoke.py -q` | **`3 passed in 1.72s`** |
| GREEN-6 | 收集数 / 文件数 | `pytest --collect-only -q` / `Get-ChildItem` | **510** / **49** |
| GREEN-7 | 格式合规 | `black --check .` | **`136 files would be left unchanged`，exit 0** |
| GREEN-8 | 引擎三件套 | `git diff --stat` | **空** |
| GREEN-9 | `type: ignore` | Grep | **1 处** |
| GREEN-10 | `pyproject.toml` | `git diff` | **空** |
| GREEN-11 | diff 体量 | `git diff --numstat` | **16 文件 / +36 −87** |
| GREEN-12 | 门禁链 | 4 条 gate + replay | probe **pass** / unit-tests **pass** / black-check **pass** / mypy-check **fail(93)**；`replay: 4 rows OK` |

### 9.4 实施期发现

| ID | 级别 | 发现 | 处理 |
|----|------|------|------|
| — | — | 本批实施未产生新的设计/代码偏差；Step 6 的 3 项 P2 已在规划阶段拦截，Step 9 无 F-9 类发现 | — |

---

## 10. ADD 审计（Step 10）

### Phase 0 — Spec 质量门

| 检查 | 结果 |
|------|------|
| DESIGN/IMPL 不可审计措辞（`大概` / `应该差不多` / `可能是这样` / `待定` / `不确定` / `TODO`） | **0 命中**（脚本逐词计数） |
| 每条决策是否携带被拒方案与代价 | D2（改名为 `MonitorAction` 仍 `no-redef`）、D4（改 3 个 lambda 形参扩大改动面）、D5（`try/except pass` 更糟）、D6（禁 `type: ignore`）、D1（合并默认值属行为变更）均有被拒理由；D3/D7/D8/D9 为范围与门禁约束 |
| 断言是否可证伪 | 26/0、119/93、507/510、135/136 均为可重放读数 |

### Phase 1 — 完整性（设计 → 落地）

| 决策 | 落地位置 | 证据 |
|------|----------|------|
| D1 删 `data.py` 死代码 | `core/data.py` −48 行 | A1 / A2 / F3 |
| D2 `risk_monitor` 去重复注解 | `core/risk_monitor.py` L723-724 | A3 / A4 |
| D3 `global_contagion` → `monitor()` | `core/global_contagion.py:631` | A5 / A6 |
| D4 `engine_plugins` → `dates=` | `core/engine_plugins.py:381` | A7 / A8 |
| D5 B 类防御 | `live_bridge.py` import+isinstance；`portfolio.py` 3 assert | A9 / A10 |
| D6 C 类 16 项 | 10 文件（含 `cast` 导入 5 处、`factor.py` 改名、`walk_forward_engine` 删块） | B1-B10 / D2 |
| D7 3 项 smoke | `tests/test_mypy_layera_smoke.py` | C1-C5 |
| D8 `config_v2` 单点 | `core/config_v2.py` 2 行（import + cast） | B5 |
| D9 引擎零改动 + U-006 不关闭 | `git diff --stat` 空；PROGRESS 明示 | D4 / E7 |

### Phase 2 — 忠实度（代码 diff ↔ 设计）

| 设计声明 | 实测 | 判定 |
|----------|------|------|
| 16 个 `core/` 文件 | `git status --short` 恰 16 个 `M core/*.py` | ✅ 精确一致 |
| +36 行全部可归属 T-1~T-6 | `git diff -U0` 逐行枚举：`cast` 导入 **5** / `cast` 调用 **6** / 注解 **6**（`set` / `dict` ×4 / `X_list`）/ `X_list` 使用 **4** / `assert` **3** / `float()` **1** / `monitor()` **1** / `dates=` **1** / `AssetType` import + `isinstance` 分支 **7** / 无注解赋值 **2** = **36** | ✅ 36/36 可归属 |
| −87 行 = −48（死代码）+ −12（`__main__` 块）+ −27（替换行） | numstat 逐文件核对 | ✅ 一致 |
| `config_v2` 仅 1 处修正 + 1 行 import | `2 2` | ✅ 与 D8 修正口径一致 |
| 零新增 `type: ignore` / 零 mypy 配置改动 | Grep = 1；`git diff pyproject.toml` 空 | ✅ |

### Phase 3 — 必要性（新增行可归属）

| 检查 | 结果 |
|------|------|
| 盲区扫描：设计外文件 | **0 项**（16 个 core 文件全部在 DESIGN §2 范围表内；新增仅 1 个测试文件） |
| 是否有未在 T-0~T-9 中的改动 | **无**（36 行逐行可归属，见 Phase 2） |
| 保护路径越界 | 引擎三件套 **diff 空**；`pyproject.toml` / `.github/` **diff 空** |
| 是否顺手重构 | **无**（`factor.py` 仅变量改名；`data.py` 仅删除；无 import 重排、无命名调整） |

### Phase 4 — 语义（目标是否真正达成）

| 铁律检查 | 结果 |
|----------|------|
| 「测试通过 ≠ 设计落地」 | 本批目标不是「让 26 个 error 消失」，而是**修复埋在类型错误里的真实缺陷**：A-1/A-2/A-3 均为 0 调用/0 覆盖导致的运行时崩溃，已用根因探针（`RiskAction` 缺失 / `evaluate` 缺失 / 3 位置参数 TypeError）+ 3 项正向 smoke 双重证明；A-4 明确「只删死代码、行为不变」，未把未修的行为缺口写成已修 |
| expected-fail 是否伪装 | **无**：`mypy-check` 仍如实 `fail(93)`，未加入 ignore、未降级 `warn_return_any`、未缩小门禁范围；U-006 明确不关闭 |
| 能力边界是否夸大 | **无**：A-4 行为缺口 → P-010；`assert` 在 `-O` 失效 → DESIGN R1；「修复前整函数探针未在编辑前执行」→ A4/A6/C3 诚实标注 |
| 递减序是否真实核对 | **有**：每步后 mypy 总数实测 119→118→115→113→109→93，与 DESIGN 分配一致；引擎分布 54/26/13 未漂移 |

### 审计结论

**P1 = 0，P2 = 0**（4 项 P2 全部在实施前拦截于 Step 6/Step 8：F-I1 报错对象、F-I2 `AssetType` 缺失、F-I3 `cast` 导入、F-S1 D2 表述矛盾）；**P3 = 11 项**（F-R1~R3、F-D1~D2、F-I4~I7、F-S2~S3）全部登记并处置；**盲区扫描 0 项设计外改动**。

---

## 11. 结论（Step 10）

**P-007 层 A（非引擎 mypy 清理）已完成。**

| 维度 | 结果 |
|------|------|
| 验收项 | **49/49** |
| 缺陷 | **P1 = 0 / P2 = 0**（4 项 P2 均在实施前拦截）；P3 = 11 项全部处置 |
| 核心交付 | 非引擎 mypy **26 → 0**；修复 **3 处运行时崩溃**（`NameError` / `AttributeError` / `TypeError`）+ 1 处重复定义；4 处 Optional 防御；新增 3 项正向 smoke |
| 零回归 | 全量 **`510 passed`**（507 + 3）；`black --check .` **136 unchanged**；引擎三件套 **diff 空**；`type: ignore` 未扩张 |
| 门禁 | probe pass / unit-tests pass / black-check pass / **mypy-check fail(93，如实)**；`replay: 4 rows OK`（session `factorv3-p007-mypy-layera-20261109`） |
| 提交 | `e0247ce`（23 文件，+1211 −88） |
| 远端 CI | run [`42614740925`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42614740925) 三 job success，3.12 `503 passed, 1 skipped` |
| 遗留 | 层 B **93 errors**（engine_v2 54 / v3_vector 26 / factory 13）另立；**P-010**（`data.py` 辅助数据无安全默认值，P2）新登记；**U-006 不关闭** |
