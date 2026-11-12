# CHECKLIST：P-024 CI 门禁对齐（mypy 假门禁 + README uv extras）

> **批次**: P-024 · **T1**
> **上游**: [IMPL_p024_ci_gate_alignment.md](IMPL_p024_ci_gate_alignment.md)（T-0~T-9 / V1-V10）；[DESIGN_p024_ci_gate_alignment.md](DESIGN_p024_ci_gate_alignment.md)（D1-D7 / I1-I7）
> **状态**: Step 10 ADD 通过（**29/29 ✅**；CI run `43196177149` 三 job success；RULE-5 待独立会话）
> **实测列规则（RULE-1）**: 仅允许 `✅ + 证据` / `❌ + 证据` / `[待 Step 9]` / `[待回填]`（仅用于远端 CI 行）

---

## 1. A 组：CI 门禁恢复阻塞（T-1）

> **DoR**: D1 命令串已定稿（DESIGN §3 D1）。**DoD**: 每条有可重放命令 + 读数；先红后绿两读数齐备。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `tests.yml` 的 mypy 步骤命令**逐字**为 `python -m mypy --explicit-package-bases --check-untyped-defs core` | `Select-String -Path ".github/workflows/tests.yml" -Pattern "run: python -m mypy"` 命中 1 行且与目标串相等 | D1 / T-1 | ✅ L46 逐字命中（`e360436`） |
| A2 | workflow 全文无 `mypy ... \|\| true` | `Select-String "mypy[^\r\n]*\|\|\s*true"` on `.github/` = **0 命中** | I3 / V8 | ✅ **0 命中** |
| A3 | CI 以 `python -m mypy` 调用（非裸 `mypy`），与本地 adapter 同形 | 读码 A1 命中行含 `python -m mypy` | D1 / I1 | ✅ L46 为 `python -m mypy` |
| A4 | 步骤名保持 `Type check (mypy)`（守卫定位依赖） | 读回 L45 `- name: Type check (mypy)` | D4-A / R5 | ✅ L45 未变 |
| A5 | **先红**：注入 `core/_p024_probe.py`（`x: int = "s"`）后运行新 CI 命令 → exit 1 | 命令输出含 `Incompatible types in assignment`；exit code = 1 | V1 / F5 | ✅ **exit 1** / `Found 1 error in 1 file (checked 37 source files)` |
| A6 | **假门禁对照**：A5 同命令追加 `\|\| true` → 内部 `exit=0` | `sh -c "<新命令> \|\| true"; echo exit=$?` → `exit=0` | V2 / P13 | ✅ **`V2_EXIT=0`**；同命令无 `\|\| true` → **`V2_RAW_EXIT=1`** |

---

## 2. B 组：本地门禁同形 + 漂移守卫（T-2 / T-3）

> **DoR**: adapter L67 目标串与 3 条断言已定稿（IMPL §4.2/§4.3）。**DoD**: 两侧命令同形可机械判定。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `mypy-check` 含 `--explicit-package-bases` **与** `--check-untyped-defs`，且仍 pin Python312 | 读码 L67；`pytest tests/test_spec_runner_adapter.py::test_u6_heavy_gates_pin_python312 -q` = passed | D2 / I1 | ✅ L67 两旗标齐备；该用例在 6 passed 内 |
| B2 | 守卫断言 A：两侧 normalize 后**旗标序列 + target 相等** | `test_ci_mypy_flags_match_local_gate` = passed | D4-A / I1 | ✅ **passed** |
| B3 | 守卫断言 B：CI 步骤不含 `\|\| true` 且全文无短路形态 | `test_ci_mypy_step_is_blocking` = passed | D4-B / I3 | ✅ **passed** |
| B4 | 守卫断言 C：README `### uv` 段含 `uv sync --all-extras` | `test_readme_uv_uses_all_extras` = passed | D4-C / D3 | ✅ **passed** |
| B5 | 新测试文件恰含 **3** 个 `test_*` 且全绿 | `pytest tests/test_p024_ci_gate_alignment.py -q` 末行 `3 passed` | T-3 | ✅ 与 adapter 合跑 **9 passed in 0.07s**（3 + 6） |
| B6 | 既有 adapter 测试 6 项零回归 | `pytest tests/test_spec_runner_adapter.py -q` 末行 `6 passed` | R5 | ✅ **6 passed** |

---

## 3. C 组：README uv 与依赖真值（T-4）

> **DoR**: D3 命令行已定稿。**DoD**: 文档命令可执行且不改依赖面。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `### uv` 代码块命令为 `uv sync --all-extras`（无第二变体） | 读回 README L217-L221 | D3 / P8 | ✅ L220 `uv sync --all-extras`，段内仅一条命令 |
| C2 | README 其余安装段（Pip 三行 / Docker 两行 / Requirements 列表）**零改动** | `git diff -U0 -- README.md` 仅 1 行变更 | D3 变更面 | ✅ `ac2a3d6` **+1/−1** |
| C3 | 依赖面零变化：`uv lock --check` exit 0；`pyproject.toml` diff 空 | `uv lock --check`；`git diff --name-only -- pyproject.toml uv.lock` = 空 | I5 / D6 | ✅ `--check` **exit 0**（`Resolved 148 packages`）；两文件 diff **空** |

---

## 4. D 组：回归与门禁终态（V4-V8）

> **DoR**: 基线 651 / 179 / 36 files 已记录（RESEARCH P10）。**DoD**: 计数逐字一致。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | 全量回归 **654 passed**（651 + 3 新断言） | `pytest -q` 末行 `654 passed` | I4 / V5 | ✅ **654 passed, 152 warnings in 52.13s** |
| D2 | black **180 files** unchanged（179 + 1 新文件） | `black --check .` 末行 `180 files would be left unchanged` | I6 / V6 | ✅ **180 files would be left unchanged** |
| D3 | 门禁口径 mypy 0 errors | `mypy --explicit-package-bases --check-untyped-defs core` → `Success: no issues found in 36 source files` | I2 / V4 | ✅ **exit 0 / 36 files 0** |
| D4 | 删除探针后同一命令 exit 0（**后绿**） | 退出码 0 + 末行 `Success` | I2 / V3 | ✅ **exit 0** / `Success: no issues found in 36 source files` |
| D5 | 生产代码零改动 | `git diff --name-only -- core/ agents/ web/ factor_library/ cli.py` = 空 | I6 | ✅ **空** |
| D6 | 无临时文件残留 | `git status --short` 空输出 + `Test-Path core/_p024_probe.py` = False | R3 / V7 | ✅ 探针已删（V3 复跑统计为 **36 files**，不含探针）；`git status` 仅 P-024 文档 |
| D7 | 远端 CI 三 job success，mypy step 日志含 `36 source files` | `gh run view 43196177149` | V9 / I7 | ✅ run [`43196177149`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43196177149) **success**：3.10 / 3.11 / 3.12 三 job 全绿（1m58s / 1m27s / 1m47s） |
| D8 | **（追加）越界声明**：`pyproject.toml` 含 `[[tool.mypy.overrides]] module = ["filter.*"] ignore_errors = true`；CI 依赖集下门禁 0 errors | 读回 pyproject L112-L117；X1（无声明，pandas 3.1.1）**21 errors** vs X2（有声明）**0**；X3（mypy 2.4.1 + 声明）**0** | D6（修订）/ V10 | ✅ pyproject L112-L117（+8 行）；X1/X2/X3 三读数齐备；`mypy>=1.5.0` 维持（钉版已撤回） |

---

## 5. E 组：台账与文档（T-5 / T-6 / T-7）

> **DoR**: 落位清单已定稿（DESIGN D5）。**DoD**: 行存在、引用可解析、ID 闭环。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 四文档齐备且互链 | `docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_p024_ci_gate_alignment.md` 存在；相对链接 0 broken | T-7 | ✅ 四文档存在；Step 8 机械校验 45 处链接 **0 broken** |
| E2 | §1.4 新增 **U-P023-1~4** 四行（补齐 P-023 遗漏） | 读回 §1.4，`Select-String "^\| U-P023-"` = 4 行 | P11 / D5 | ✅ **4 行**（L89-L92） |
| E3 | §1.4 新增 **U-P024-1~3** 三行 | `Select-String "^\| U-P024-"` = 3 行 | RESEARCH §6 | ✅ **3 行**（L93-L95） |
| E4 | §2 U-006 行补 P-024 注记 + 关闭注含 **U-006 / U-P023-2 / U-P023-4** 三 ID | 读回 §2 L127 与关闭注区 | D5 | ✅ 注记落 L127；关闭注 L142 三 ID 齐备 |
| E5 | §3.28 新增 P-024 执行记录；CHANGELOG 含 P-024 条目 | 读回 `Grep "3.28\|P-024"` 两文件 | D5 | ✅ PROGRESS §3.28（L723-L731）+ CHANGELOG `### CI` 首条 |
| E6 | 台账单来源：U-P024-1~3 的四元块不重复展开 | `Select-String "U-P024-1"` **命中文件数 = 3**（RESEARCH §6 / PROGRESS §1.4+§3.28 / CHECKLIST E3） | 未决项纪律 | ✅ 文件数 **3**，无第四处 |

---

## 6. 预填检查（RULE-1）

| 项 | 读数 |
|----|------|
| 验收项总数 | **29**（A 6 + B 6 + C 3 + D 8 + E 6，机械计数；D8 为 Step 9 追加） |
| 实测列 `[待 Step 9]` 数（Step 7 时点） | 28 处（28 验收单元格；§6 规则行不含该标记；D8 为 Step 9 追加项，不在 Step 7 计数内） |
| Step 9 回填后剩余 | **0 处 `[待 Step 9]`**；**0 处 `[待回填]`**（D7 与 §8.1 已回填） |

---

## 7. Step 8 一致性 Review（独立 pass）

> **执行方式**：四文档完稿后独立机械校验 + 人工对齐（RULE-1 时序独立；RULE-4 单 Agent「自查·单视角」）。机械脚本 `%TEMP%\p024_consistency.py`（链接 / ID / 计数 / 零预填四项）。

### 7.1 机械读数

| # | 校验 | 读数 |
|---|------|------|
| 1 | 相对链接 | RESEARCH **23** / DESIGN **10** / IMPL **10** / CHECKLIST **2**（共 45）→ **0 broken** |
| 2 | ID 闭环 | RESEARCH **P1-P13** 连续 ✅；DESIGN **D1-D7 / I1-I7** ✅；IMPL **T-0~T-8** ✅ |
| 3 | 验收计数 | A 6 + B 6 + C 3 + D 8（Step 9 追加 D8）+ E 6 = **29**（与表体逐行一致） |
| 4 | 零预填 | 验收行 **29**，实测列 `[待 Step 9]` **0** 处、`[待回填]` **0** 处 |

### 7.2 对齐矩阵

| 上游 → 下游 | 检查 | 结论 |
|-------------|------|------|
| RESEARCH P1-P13 → DESIGN D1-D7 | F1→D1 / F2→D1+D2 / F3→D3 / F4→D5 / P12→D5 关闭 U-P023-4 | 一致 |
| DESIGN I1-I6(+I7) → IMPL §5 验证矩阵 | I1→V5(守卫生效前为 T-1/T-2 对照)、I2→V3/V4、I3→V1/V2/V8、I4→V5、I5→V7、I6→V6、I7→V9 | 一致（I7 由 §7.3 F-S8-P024-2 补） |
| DESIGN D1-D7 → IMPL T-1~T-8 | D1→T-1 / D2→T-2 / D3→T-4 / D4→T-3 / D5→T-5,T-6 / D6,D7→「不改」 | 一致 |
| IMPL T-1~T-8 → CHECKLIST A-E | T-1→A1-A6、T-2→B1、T-3→B2-B6、T-4→C1-C3、T-5/T-6→E2-E6、T-7→E1、T-8→§10 | 一致 |
| DESIGN D5 → E2/E3/E4/E5 | 七行补登 + U-006 注记 + 关闭注 + §3.28 + CHANGELOG 均落到验收项 | 一致 |
| RESEARCH §6 出界项 → DESIGN D6/D7 | 版本上限 / 检查面扩展两项未被设计偷偷纳入 | 一致 |

### 7.3 发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S8-P024-1** | P3 | DESIGN/IMPL 共 3 处相对链接指向 `tests/test_p024_ci_gate_alignment.py`，该文件 Step 9 才创建 → 机械校验 3 broken | 已改为代码字面量（非链接）；复跑 **0 broken** |
| **F-S8-P024-2** | P3 | CHECKLIST D7 与 IMPL V9 引用 **I7**，但 DESIGN §5 只定义 I1-I6（悬空 ID） | DESIGN §5 补 **I7**（远端 CI 与本地同口径），ID 闭环恢复 |
| **F-S8-P024-3** | P3 | RESEARCH P7 初稿把 CI 矩阵位置记为 `pyproject.toml` L15-L16（实为 `tests.yml` L15-L16） | 已订正为双来源分列（Step 2 已记录 F-S2-P024-1，此处为一致性命中复现） |

### 7.4 结论

**通过**——0 P1 / 0 P2 / **3 P3（均已回写）**；Step 7 口径 28 项 + Step 9 追加 D8 = **29 项**，覆盖 D1-D7 / I1-I7 / V1-V10 / T-0~T-9；链接 0 broken、ID 闭环、零预填合规。可进入 Step 9 实施。

---

## 8. Step 9 实测回填

### 8.1 提交链

| 提交 | 内容 | numstat |
|------|------|---------|
| `e360436` | B1：`tests.yml` L46 + adapter L67 + 守卫测试 3 断言 | 3 文件 **+77/−2** |
| `ac2a3d6` | B2：README uv 段 → `--all-extras` | 1 文件 +1/−1 |
| `c1c67b2` | B3：PROGRESS + CHANGELOG + 四文档 | 6 文件 **+871/−1** |
| `f8cb9ba` | B4：`pyproject.toml` 追加 `[[tool.mypy.overrides]] filter.*`（+8 行，撤回钉版） | 8 文件 **+59/−34**（含文档更正） |
| `[待回填]` | B5：回填 CI run `43196177149` + Step 10 ADD | `[待回填]` |

### 8.2 红 → 绿读数（F5）

| 读数 | 值 |
|------|----|
| V1 先红（注入类型错误 + 新 CI 命令） | **exit 1** / `core\_p024_probe.py:7: error: Incompatible types in assignment (expression has type "str", variable has type "int")` / `Found 1 error in 1 file (checked 37 source files)` |
| V2 假门禁对照（+ `\|\| true`） | **`V2_EXIT=0`**；同命令去掉 `\|\| true` → **`V2_RAW_EXIT=1`** |
| V3 后绿（删除探针 + 新 CI 命令） | **exit 0** / `Success: no issues found in 36 source files` |

### 8.3 门禁终态

| 项 | 读数 |
|----|------|
| 全量 | **654 passed, 152 warnings in 52.13s** |
| 新测试 | 与 adapter 合跑 **9 passed in 0.07s**（3 + 6） |
| mypy 门禁 / 盲区 | 36 files **0** / **0**（同一命令两侧同形） |
| black | **180 files would be left unchanged** |
| 依赖面 | `uv lock --check` **exit 0**（148 packages）；`pyproject.toml` / `uv.lock`：仅新增 `filter.*` override 块（钉版与锁改动已撤回） |
| 保护面 | `core/` `agents/` `web/` `factor_library/` `cli.py` diff **空**；`mypy.*\|\| true` grep **0** |
| 远端 CI | run [`43196177149`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43196177149) 三 job **success** |

### 8.4 实施发现

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-S9-P024-4** | **P2** | **CI 首跑红**：推送 `c1c67b2` 后 run `43193963200` → 3.10 **failure**（3.11/3.12 canceled），**21 errors / 7 files 全在 `filter/*`**，`core/` 0 条。归因 X1-X4 定位为 **pandas 3.1.1 类型桩**（`pandas>=2.0.0` 无上限；CI 3.1.1 vs 本地 2.2.3），`core` 经 `engine_v2` L61-62 / `factory` L31 导入 `filter` 后被 follow | 新增 `[[tool.mypy.overrides]] filter.* ignore_errors`（D6 修订，B4）；X2/X3 验证跨 mypy 版本均 0；`filter/` 21 条登记 U-P024-4 |
| **F-S9-P024-5** | **P2** | **误诊与撤回**：首轮判为「mypy 2.4.1 vs 2.1.0 版本漂移」并提交 `745e2b7`（`mypy~=2.1.0`）。复核发现该读数来自 `uv run --no-project` **缺 pydantic/pandas** 的环境（`ignore_missing_imports=true` → pydantic 成 `Any` → `config_v2.py` 3 条伪影） | 撤回钉版（`pyproject` 恢复 `mypy>=1.5.0`、`uv.lock` 复原）；改以越界声明收口；U-P024-1 的「已触发」判定撤回 |
| F-S9-P024-1 | P3 | `shutil.which("bash")` 在 Windows 解析到 `C:\Windows\system32\bash.EXE`（WSL 存根，恒返回 0），首轮探针 A-D 全 `exit=0` → 假阴性 | 改用 Git bash 绝对路径；读数恢复正常（3/0/2/0） |
| F-S9-P024-2 | P3 | `git commit` 提示 `LF will be replaced by CRLF`（autocrlf=true） | 与既有行为一致，无处置 |
| F-S9-P024-3 | P3 | Step 8 改为代码字面量的 3 处测试文件链接，Step 9 后未恢复为链接 | 有意保留（E1 以文件存在性单独验收） |

---

## 9. Step 10 ADD 审计

### 9.1 变更面

| 类别 | 文件 | 规模 |
|------|------|------|
| CI | `.github/workflows/tests.yml` | −1/+1 |
| 门禁配置 | `scripts/spec_runner_adapter.py` | −1/+1 |
| 类型配置 | `pyproject.toml`（`filter.*` override） | +8 |
| 文档 | `README.md` | −1/+1 |
| 测试 | `tests/test_p024_ci_gate_alignment.py`（新增） | +64 |
| 台账 | `docs/PROGRESS.md`、`CHANGELOG.md` | +~40 / +1 |
| 四文档 | `docs/*_p024_ci_gate_alignment.md` | 新增 |

**生产代码零改动**：`core/` / `agents/` / `web/` / `factor_library/` / `cli.py` diff 空（D5 ✅）。**依赖面**：`uv.lock` 与最终 `pyproject` 的 `mypy` specifier 均回到批前值（钉版撤回）。

### 9.2 问题闭环

| 来源 | 发现 | 级别 | 闭环 |
|------|------|------|------|
| Step 1 | CI mypy 假门禁（`\|\| true` 恒吞退出码） | P1 | B1 修复 + D4-B 守卫 |
| Step 1 | 双口径不可互换（CI 参数本地 exit 2） | P2 | D1/D2 统一命令 |
| Step 9 | CI 首跑红：`filter/*` 21 errors（pandas 3.1.1 桩） | P2 | D6 override + U-P024-4 |
| Step 9 | 首轮误诊为 mypy 版本漂移并提交钉版 | P2 | 撤回 `745e2b7`，`f8cb9ba` 更正 + 文档留痕 |
| Step 1-8 | 5 个 P3（来源误记 / 守卫规范化 / 悬空链接 / I7 / 输入规范化） | P3 | 全部回写 |

### 9.3 判据复核

| 项 | 结论 |
|----|------|
| 29 项验收 | **29/29 ✅**（D7 已回填） |
| 门禁 | `654 passed` / black `180 unchanged` / mypy `36 files 0` / `uv lock --check` exit 0 |
| 远端 | run `43196177149` 三 job success |
| Iron Law（生产代码零改动） | ✅ |
| 零预填 | ✅（§6 读数一致） |

**结论**：ADD 审计通过（0 P1 / 0 P2 遗留；2 个 P2 已闭环并有撤回留痕）。

---

## 10. 签字表

| 角色 | 结论 | 依据 |
|------|------|------|
| 作者（DeepSeek-V4.1-Flash）· Step 2 调研 Review | **pass**（0 P1/P2，1 P3 F-S2-P024-1） | RESEARCH §8 |
| 作者 · Step 4 设计 Review | **pass**（0 P1/P2，2 P3 F-D4-P024-1/2） | DESIGN §9 |
| 作者 · Step 6 实施规划 Review | **pass**（0 P1/P2，2 P3 F-I1-P024-1/2） | IMPL §6 |
| 作者 · Step 8 一致性 Review | **pass**（0 P1/P2，3 P3 F-S8-P024-1~3） | CHECKLIST §7 |
| 作者 · Step 9 实施 | **done**（29/29 ✅；先红 → 对照 → 后绿三读数齐备；P2×2 F-S9-P024-4/5 已闭环并留撤回记录） | CHECKLIST §8 |
| **RULE-5 异构基座复审** | `[待独立会话]` | §11 |
| CI run | ✅ [`43196177149`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/43196177149) 三 job success | §8.3 |

---

## 11. RULE-5 异构复审（独立会话）

`[待独立会话]`
