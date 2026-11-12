# CHECKLIST：P-023 质量护栏（F-A1 静默空回测 + U-006-R mypy 盲区）

> **批次**: P-023 · **T1**
> **上游**: [IMPL_p023_quality_guardrails.md](IMPL_p023_quality_guardrails.md)（T-1~T-5 / V1-V7）；[DESIGN_p023_quality_guardrails.md](DESIGN_p023_quality_guardrails.md)（D1-D6 / I1-I6）
> **状态**: Step 7 完稿（**25 项**零预填；Step 8 计数更正）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]`

---

## 1. A 组：F-A1 行为守卫（T-1 / T-2）

> **DoR**: DESIGN D1/D2 的位置与文案已定稿（§3）。**DoD**: 每条有可重放命令 + 读数。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `run()` 在 `_composite_signal is None` 时抛 `RuntimeError`，消息含 `信号未就绪` | `pytest tests/test_p023_quality_guardrails.py::test_run_without_signal_raises -q` = 1 passed | D1 / T1 | ✅ **1 passed**（4 passed 之一；实现前为 `DID NOT RAISE`） |
| A2 | `setup()` 守卫条件、异常类型、文案逐字不变 | `git diff -U0 <base>..HEAD -- core/engine_v2.py` 中 `factor_files 不能为空` 行数为 0（未增删） | I1 / C1 | ✅ diff 中该行 **0 处变更** |
| A3 | setup 后手工注入信号 → `run()` 正常返回 dict（13 用例形态不破） | `test_run_after_manual_signal_injection` = 1 passed | D1 / T2 / I2 | ✅ **1 passed** |
| A4 | `_generate_results()` 零快照抛 `RuntimeError`，消息含 `快照` | `test_generate_results_empty_snapshots_raises` = 1 passed | D2 / T3 | ✅ **1 passed**（实现前为 `DID NOT RAISE`） |
| A5 | 正常注入 + 非空 `factor_files` → 回测完整（`portfolio_value` 非空） | `test_normal_injected_backtest_still_works` = 1 passed | D2 / T4 / I3 | ✅ **1 passed**（`len(portfolio_value) > 0`） |
| A6 | 两项守卫异常类型均为 `RuntimeError`（非 ValueError/AssertionError） | 读码：两处 `raise RuntimeError`；`grep -c "raise ValueError"` 在 run/_generate_results 区段 = 0 | D1/D2 §4.3 文案约定 | ✅ `engine_v2.py` L317 / L1149 均 `raise RuntimeError`；两区段 0 处 `ValueError` |

---

## 2. B 组：U-006-R 盲区清零（T-3）

> **DoR**: 四条 error 的行号与修法已定稿（DESIGN D3/D4）。**DoD**: 盲区命令 exit 0 且门禁口径不劣化。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `mypy --check-untyped-defs core` 由 4 → **0 errors** | `mypy --explicit-package-bases --check-untyped-defs core` 末行 `Success: no issues found in 36 source files` | D3/D4 / V4 | ✅ **exit 0 / 36 files 0**（由 `Found 4 errors in 2 files` 清零） |
| B2 | `data_v3._build_maps` 局部别名 + 单 assert 双窄化 | 读码：`dates = self.dates` / `stocks = self.stocks` / `assert dates is not None and stocks is not None` | D3 / P13 | ✅ `data_v3.py` L130-L134 逐字命中 |
| B3 | `engine_v2` L224 使用 `cast(DataManager, self.dm)` | 读码 + `grep -c "cast(DataManager, self.dm)"` = 1 | D4 / P12 / E3 | ✅ L224 命中，Grep = 1 |
| B4 | `engine_v2._precompute_factors` 用局部 `dm` 别名 + assert | 读码：`dm = self.dm` / `assert dm is not None` / `raw = dm.load_factor(fname)` | D4 / P11④ | ✅ L293-L295 逐字命中 |
| B5 | 门禁口径 `mypy --explicit-package-bases core` 仍 0 errors | 末行 `Success: no issues found in 36 source files` | I6 / V3 | ✅ **exit 0 / 36 files 0**（不劣化） |

---

## 3. C 组：保护面与不变式（I1-I6）

> **DoR**: 保护面清单已定稿（DESIGN D6 / V7）。**DoD**: diff 空或仅预期文件。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | 逐日循环体与 `except Exception: continue` 逐字不变 | `git diff -U0 <base>..HEAD -- core/engine_v2.py` 中该段 0 行变更 | I4 / D6 | ✅ diff 未触及 `run()` 的逐日 try/except 区段 |
| C2 | `FactorPipeline` / `IDataManager` / `DataLoaderV3.__init__` 签名与注解零改动 | `git diff --name-only <base>..HEAD -- core/factor.py core/interfaces.py` = 空；`git diff -U0 core/data_v3.py` 不含 `def __init__` 区段 | I5 | ✅ 两文件 diff **空**；data_v3 改动仅在 `_build_maps`（+3/−2） |
| C3 | `pyproject.toml` / `.github/` 零改动 | `git diff --name-only <base>..HEAD -- pyproject.toml .github/` = 空 | V7 / D6 | ✅ **空** |
| C4 | 注入式两文件回归 27 passed | `pytest tests/test_real_ashare_backtest.py tests/test_real_ashare_strict_validation.py -q` 末行 `27 passed` | I2 / V6 | ✅ **27 passed, 21 warnings in 9.13s** |
| C5 | 零新增 `isinstance` 运行时校验（防注入契约变更） | `git diff -U0 <base>..HEAD \| grep -c "isinstance"` 在 core 两文件 = 0 | D6 | ✅ diff 中 **0 处**新增 `isinstance` |

---

## 4. D 组：测试与门禁（V1-V5）

> **DoR**: 4 项测试夹具与期望已定稿（IMPL §4.4 / §5）。**DoD**: 计数逐字一致。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | 新增测试文件恰含 4 个 `test_*` 函数 | `pytest --collect-only -q tests/test_p023_quality_guardrails.py` 末行 `4 tests collected` | V1 / T1-T4 | ✅ **4 tests collected** |
| D2 | 新增 4 项全绿 | `pytest tests/test_p023_quality_guardrails.py -q` = `4 passed` | V1 | ✅ **4 passed in 2.52s** |
| D3 | 全量回归 651 passed（647 + 4） | `pytest -q` 末行 `651 passed` | V2 | ✅ **651 passed, 152 warnings in 39.91s** |
| D4 | black 113 files unchanged（112 + 新测试文件） | `black --check core tests cli.py` 末行 `113 files would be left unchanged` | V5 | ✅ **113 files would be left unchanged** |
| D5 | 红态取证：T1/T3 在实现前 `DID NOT RAISE`，T2/T4 为对照绿 | Step 9 实施前逐条记录 pytest 读数（不预填结论） | F5 / IMPL §6.1 #7 | ✅ B1 红 **1 failed 1 passed**（`DID NOT RAISE` + 4 条空 ERROR）；B2 红 **1 failed 3 passed**（`DID NOT RAISE`）；T2/T4 对照绿 |

---

## 5. E 组：治理与台账（T-4 / T-5）

> **DoR**: 文档落位清单已定稿。**DoD**: 行存在且引用可解析。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 四文档齐备且互链 | `docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_p023_quality_guardrails.md` 存在；链接 0 broken | T-4 | ✅ 四文档存在；Step 8 机械校验 14 处链接 **0 broken** |
| E2 | PROGRESS §1.4 新增 P-023 行（含档位/四文档/CI） | 读回 §1.4 | T-4 | ✅ §1.4 L65 P-023 行（done，T1，四文档链接） |
| E3 | **U-006-R 关闭** + **F-A1(P-012) 关闭**，并在关闭注中记录 F-A1 来源订正（P-012 §11 → P-007 §9.3，编号撞车） | 读回 §1.4 两行 + 关闭注 | P2 / F-S2-P023-1 | ✅ 关闭注 L133（含「P-012 `F-A1` 为同名另一发现，权威源 P-007 §9.3 L210」） |
| E4 | CHANGELOG `Changed` 新增 2 条行为变更（run 信号守卫 / `_generate_results` 空快照守卫） | 读回 `CHANGELOG.md` `[Unreleased] > Changed` 首 2 条 | D1/D2 / R1 | ✅ `Changed` 首条 P-023（①② 两项行为变更 + U-006-R 清零） |

---

## 6. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **25**（A 6 + B 5 + C 5 + D 5 + E 4，机械计数） |
| 实测列 `[待 Step 9]` 数（Step 7 时点） | 28 处 = 25 验收单元格 + 3 处合法（§6 规则/统计行） |
| Step 9 回填后剩余 | **0 处**（25 项全部转 ✅，见 §8） |

---

## 7. Step 8 一致性 Review（独立 pass）

> **执行方式**：四文档全部完稿后独立机械校验 + 人工对齐（RULE-1 时序独立；RULE-4 单 Agent「自查·单视角」）。机械脚本 `%TEMP%\p023_consistency.py`（链接 / ID / 计数 / 角色引用四项）。

### 7.1 机械读数

| # | 校验 | 读数 |
|---|------|------|
| 1 | 相对链接 | RESEARCH **10** / DESIGN 1 / IMPL 1 / CHECKLIST 2 → **0 broken** |
| 2 | ID 闭环 | RESEARCH P1-P13 ✅；DESIGN D1-D6 / I1-I6 / V1-V7 ✅；IMPL T-1~T-5 ✅ |
| 3 | 验收计数 | 分组 A6+B5+C5+D5+E4 = **25**（与表体逐行一致） |
| 4 | 零预填 | `[待 Step 9]` **28 处** = 25 单元格 + 3 处合法（§6 规则/统计行） |
| 5 | 文档角色引用 | 修正前 RESEARCH 0 处 → 已补下游链（**1 处**含 3 文档） |

### 7.2 对齐矩阵

| 上游 → 下游 | 检查 | 结论 |
|-------------|------|------|
| RESEARCH P6/P7/P9 → DESIGN D1/D2 | 探针场景 A/C/E 与两守卫一一对应 | 一致 |
| RESEARCH P11/P12/P13 → DESIGN D3/D4 | 四条 error 与四处窄化逐条对应 | 一致 |
| DESIGN D1-D6 → IMPL T-1~T-4 | T-3 合并 D3+D4（同文件同批次），其余 1:1 | 一致 |
| DESIGN V1-V7 → CHECKLIST B1/C4/D1-D4 | V1→D1/D2、V2→D3、V3→B5、V4→B1、V5→D4、V6→C4、V7→C3 | 一致 |
| IMPL T-1~T-5 → CHECKLIST A/B/C/D/E | T-1→A1-A3、T-2→A4-A5、T-3→B1-B5、T-4→E1-E4、T-5→签字表 CI 行 | 一致 |
| DESIGN §3 文案约定 → CHECKLIST A6 | `RuntimeError` + 必含子串 | 一致 |
| U-P023-1~4 → 出界声明 | 三文档一致（RESEARCH §6 / DESIGN D6 / IMPL §1） | 一致 |

### 7.3 发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S8-P023-1 | P3 | CHECKLIST 标题与 §6 初稿写「24 项」，机械计数为 **25 项**（A6+B5+C5+D5+E4） | 已统一为 25，§6 表同时补「28 处 `[待 Step 9]`」构成说明 |
| F-S8-P023-2 | P3 | RESEARCH 头部缺「下游」行 → 角色引用机械检查 0 处（四文档互链不完整） | 已补下游行（DESIGN → IMPL → CHECKLIST） |

### 7.4 结论

**通过**——0 P1 / 0 P2 / 2 P3（均已回写）；25 项验收口径覆盖 D1-D6 / I1-I6 / V1-V7 / T-1~T-5 全部；链接 0 broken、ID 闭环、零预填合规。可进入 Step 9 实施。

---

## 8. Step 9 实测回填

### 8.1 提交链

| 提交 | 内容 | numstat |
|------|------|---------|
| `a5b95bb` | B1-B3：双守卫 + 四项窄化 + 4 项测试 | 3 文件 **+222/−5**（`data_v3.py` +5/−2、`engine_v2.py` +14/−3、新测试 +203） |

### 8.2 红 → 绿逐批读数（F5）

| 批次 | 红 | 绿 |
|------|----|----|
| B1 | `1 failed, 1 passed`；`test_run_without_signal_raises` = `Failed: DID NOT RAISE`；日志 **4 条空消息 ERROR** + `没有快照数据` WARNING×2 | `2 passed` |
| B2 | 追加 T3/T4 后 `1 failed, 3 passed`；`test_generate_results_empty_snapshots_raises` = `Failed: DID NOT RAISE` | `4 passed` |
| B3 | `mypy --check-untyped-defs core` → exit 1，`Found 4 errors in 2 files (checked 36 source files)` | exit 0，`Success: no issues found in 36 source files` |

### 8.3 门禁终态

| 项 | 读数 |
|----|------|
| 全量 | **651 passed, 152 warnings in 39.91s** |
| 新增 | **4 passed in 2.52s** |
| mypy 门禁 / 盲区 | 36 files **0** / **0** |
| black | **113 files would be left unchanged** |
| 注入式 | **27 passed, 21 warnings in 9.13s** |
| 保护面 | `pyproject.toml` / `.github/` / `core/interfaces.py` / `core/factor.py` diff **空** |

---

## 9. Step 10 ADD 审计

### 9.1 四阶段

| 阶段 | 检查 | 结论 |
|------|------|------|
| **Phase 0: Spec 质量门** | DESIGN D1-D6 可机械核验（位置 / 异常类型 / 必含子串 / 窄化形态 / 范围边界） | ✅ 无「合理处理」类模糊词 |
| **Phase 1: 完整性** | D1→L313-L317、D2→L1145-L1148、D3→`data_v3` L130-L134、D4→L224 + L293-L295 | ✅ 4/4 落地 |
| **Phase 2: 忠实度** | diff 逐行对照：无静默偏离；唯一偏离为「B1-B3 合批提交」（IMPL §7.1 已记录） | ✅ 1 项已登记 |
| **Phase 3: 必要性** | 新增 19 行归属：D1 6 行 / D2 4 行 / D3 5 行 / D4 4 行（import 行共享）；0 行无设计依据 | ✅ |
| **Phase 4: 语义** | 守卫意图 = 「假成功 → 明确失败」，与 DESIGN §1 目标一致；未把「静默」改成「另一个静默」 | ✅ |

### 9.2 取证矩阵（E1-E5）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| pytest 全量 / 新增 / 注入式（E1） | D2/D3/C4/A1-A5 | ✅ `651 passed` / `4 passed` / `27 passed` |
| mypy 双口径（E1） | B1/B5 | ✅ 均 exit 0，36 files 0 |
| black（E1） | D4 | ✅ 113 unchanged |
| git diff numstat + 保护面（E1） | C1-C3/C5/A2 | ✅ +222/−5；保护面空；0 新增 isinstance；setup 守卫 0 变更 |
| 探针复跑（E2，场景 A/C/E/D 四组） | D1/D2 行为语义 | ✅ A/C/E 转抛 RuntimeError；D 对照不变 |
| 静态读码 @`a5b95bb`（E3） | A6/B2-B4 | ✅ L224 cast / L294 assert / L317 / L1149 / data_v3 L132 |
| 盲区扫描（E4，范围 = 2 代码文件 diff + 1 测试文件 + 四文档 + PROGRESS/CHANGELOG） | 全部 | **发现 1 项**（§9.3 F-S10-P023-1） |

### 9.3 E4 盲区扫描结果

| # | 发现 | 等级 | 处置 |
|---|------|------|------|
| F-S10-P023-1 | B1-B3 合并为单提交 `a5b95bb`，与 DESIGN §3「保持两个提交边界」的偏好不一致 | P3 | **登记**（同文件交错编辑所致；回退能力由 DESIGN §8 三档保留，无功能影响） |
| 观察 1 | `test_run_after_manual_signal_injection` 的 `_FakeCombiner.combine` 未被引擎调用（夹具冗余） | 观察 | 已在 IMPL F-S9-P023-2 登记，不改 |
| 观察 2 | `_generate_results` 空快照守卫对「零交易日」形态一并 fail-fast（原因不区分） | 观察 | 已登记 U-P023-3（条件触发） |
| 观察 3 | 盲区口径未纳入 CI，未来无注解函数增多可能回潮 | 观察 | 已登记 U-P023-2（条件触发） |

### 9.4 审计结论

**P1 = 0 / P2 = 0 / P3 = 1（F-S10-P023-1 登记）+ 3 观察**；25/25 ✅；V1-V7 全过；ADD 通过。

> **RULE-5 状态**：本批**未执行**异构复审——实施与审计同基座（DeepSeek-V4.1-Flash），不满足异质性约束；需另起异构基座会话对本批全批复审。

---

## 10. 签字表

| 环节 | 状态 | 主体 | 日期 |
|------|------|------|------|
| Step 1-2 调研 + Review | 通过 | [RESEARCH §8](RESEARCH_p023_quality_guardrails.md)（RULE-4 自查·单视角；0 P1/P2；1 P3 修正） | 2026-11-12 |
| Step 3-4 设计 + Review | 通过 | [DESIGN §9](DESIGN_p023_quality_guardrails.md)（RULE-4 自查·单视角；2 P3） | 2026-11-12 |
| Step 5-6 实施规划 + Review | 通过 | [IMPL §6](IMPL_p023_quality_guardrails.md)（RULE-4 自查·单视角；1 P3） | 2026-11-12 |
| Step 7 验收清单 | 通过（零预填 25 项） | §1-§5 | 2026-11-12 |
| Step 8 一致性 Review | 通过 | §7（链接 0 broken；ID 闭环；计数 25；2 P3 回写） | 2026-11-12 |
| Step 9 TDD 实施 | 完成 | [IMPL §7](IMPL_p023_quality_guardrails.md)（三批红绿；`a5b95bb`；25/25 ✅） | 2026-11-12 |
| Step 10 ADD 审计 | 通过 | §9（Phase 0-4 + 取证矩阵 7 类；P3×1 登记 + 3 观察） | 2026-11-12 |
| RULE-5 异构复审 | **未执行** | 本会话即作者（DeepSeek-V4.1-Flash）；待异构基座独立会话全批复审 | — |
| CI 回收 | [待推送] | 提交推送后回填 run 号与三 job 结论 | — |
