# 环境规范化（U-001 + U-005） · 审查验收清单

> **文档编号**: CHECKLIST_env_normalization
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-05
> **状态**: 已完成（Step 10 审计通过；`06e9e11` 已推送，远端复核 2026-11-05：CI 红基线为既有环境缺失，登记 P-009）
> **上游**: [DESIGN_env_normalization.md](DESIGN_env_normalization.md)（Step 4 通过） · [IMPL_env_normalization.md](IMPL_env_normalization.md)（Step 6 通过）
> **填写规则**: 本清单在 Step 7 只定义「怎么算做完」；所有 `[ ]` 由 Step 9/10 按实测读数勾选，**禁止实现前预填**（RULE-1）。每条 ✅ 必须绑定证据出口，无证据只能标 `[未在远端执行]` / `[未取证]`。

---

## 1. 功能完整性

> **DoR**：DESIGN §3 契约已定义且经 Step 4 复核；**DoD**：每项有 E1/E2 读数或 `[未在远端执行]` 声明。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测（2026-11-05） |
|----|--------|--------------|------|---------------------|
| A1 | `jobs.test.env` 恰为 `{"MPLBACKEND": "Agg"}`（仅 1 键） | V1 脚本打印键值 + `git diff` | S5（T1） | ✅ `{'MPLBACKEND': 'Agg'}`（V1 PASS） |
| A2 | `Run tests` 命令 == `python -m pytest tests/ --tb=short -q` | V1 精确字符串比对 | S3（T1） | ✅ 精确命中（V1 PASS） |
| A3 | `env` 未出现在 workflow 顶层与 step 级 | V1 断言 `"env" not in d` 与 `"env" not in s`（逐 step） | DESIGN D1 | ✅ 顶层与 6 个 step 均无 `env` |
| A4 | `steps[5].run` 与基线逐字相同；matrix 三版本不变；`len(steps) == 6` | V1 与 `116426e` 基线字符串比对 | DESIGN §3.2 | ✅ mypy 逐字同 / matrix 同 / `len(steps)=6` |
| A5 | README 存在 `## 🧪 Testing` 且仅 1 次 | V2 计数 + 行号 | DESIGN §3.3 | ✅ 1 次，L233；位于 Installation(L199) 与 Usage(L270) 之间 |
| A6 | 新节含 5 要素：`MPLBACKEND`、`py -0p`、`py -3.12`、`509 passed`、`cli.py test` 提醒 | V2 逐要素计数 ≥1 | S1 / S6（T1） | ✅ 5/5 命中（V2 PASS） |
| A7 | README 3 处计数：徽章 `509%20passed`、Quick Start `509 passed ✓`、结构注释 `509 tests, 50 files` | V2 + `Select-String "503"` 空输出 | E1（509 passed / 50 files） | ✅ 3 精确串命中；`503` 计数 0 |
| A8 | `core/`、`tests/`、`scripts/`、`pyproject.toml`、`cli.py` 零改动 | `git status --short` 与 `git diff --stat` | DESIGN §1.1 | ✅ `git diff --stat` 仅 tests.yml / README / PROGRESS |
| A9 | 回退路径可用：两目标文件均为 git 跟踪文件 | `git ls-files` 命中 2 文件 | IMPL §3 | ✅ 两文件均命中 |

## 2. 测试完整性

> **DoR**：IMPL §2.5 的 V1-V4 已定义；**DoD**：断言脚本输出可重放，正例与反例均有读数。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测（2026-11-05） |
|----|--------|--------------|------|---------------------|
| B1 | V1 YAML 断言 GREEN（A1-A4 全部通过） | 脚本 stdout（E2）+ 退出码 0 | S5 / S3（T1） | ✅ `V1 YAML: PASS (0 项)`，exit 0 |
| B2 | V2 README 断言 GREEN（A5-A7 全部通过） | 脚本 stdout（E2）+ 退出码 0 | E1 | ✅ `V2 README: PASS (0 项)`，exit 0 |
| B3 | 反例可被拦截：构造「env 放错层级 / 命令缺 `-m` / 计数只改徽章 / `49 files`」四种坏样本，断言均 fail | 脚本对坏样本输出 `FAIL` 的读数（E2） | IMPL §2.5 边界表 | ✅ **5/5 拦截**（YAML 3：step 级 env / 缺 `-m` / mypy 被改；README 2：`49 files` / 残留 503） |
| B4 | 全量回归 `509 passed`（Agg + Python312，末尾仅 1 次） | pytest 输出（E1） | RESEARCH P8 | ✅ `509 passed, 82 warnings in 30.18s`（直接）/ `32.23s`（gate seq 9） |
| B5 | 不新增仓内测试文件（零代码约束） | `git status --short` 无 `tests/` 路径 | DESIGN D3 | ✅ `git status` 无 `tests/` 路径 |
| B6 | 红→绿记录：RED 至少 3 条失败读数、GREEN 4 条通过读数 | §10 表逐条读数 | SPEC_PROCESS Step 9 | ✅ §10 记录 RED 3 / GREEN 4 |

## 3. 性能验收

> **DoR**：设计性能目标为「不变」；**DoD**：与基线读数对比，无新增步骤。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测（2026-11-05） |
|----|--------|--------------|------|---------------------|
| C1 | V1+V2 断言脚本总耗时 < 2s | 脚本内 `time.perf_counter()` 打印 | IMPL §2.4 | ✅ `0.002s` |
| C2 | 全量 pytest 耗时 ≤ 40s（基线 31.99s @ Step 4 复跑） | pytest 输出末行 | E1 | ✅ `30.18s` |
| C3 | CI step 数仍为 6，无新增 step | V1 `len(steps) == 6` | DESIGN §1.1 | ✅ `6` |
| C4 | 断言脚本无网络调用、无外部进程 | 脚本源码静态读码（E3） | IMPL §2.4 | ⚠️ 执行前读码确认（仅 `copy/sys/time/pathlib/yaml`）；脚本未入仓且已删除，**不可重放** → 标 `[未入仓-不可重放]`，不写 ✅ |

## 4. 文档一致性

> **DoR**：四文档完稿；**DoD**：机械比对 + 链接可解析。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测（2026-11-05） |
|----|--------|--------------|------|---------------------|
| D1 | 四文档无冲突值；真值载体 DESIGN/IMPL/CHECKLIST 对 `MPLBACKEND=Agg`、`python -m pytest tests/ --tb=short -q`、`509 passed`、`50 files` 逐值命中（RESEARCH/PROGRESS 为证据层与台账，不要求全覆盖） | `Select-String` 关键值命中表 | Step 8 一致性表 | ✅ §9 键值矩阵无冲突值 |
| D2 | 四文档相对链接全部可解析 | `Test-Path` 逐链接 | Phase 3 检查点 | ✅ 17/17 `True`（§9） |
| D3 | "Tk 未修复"口径一致（RESEARCH §1.1 / DESIGN §10 / PROGRESS §3.5 / README 新节） | 四处读回比对 | RESEARCH §1.1 | ✅ README `Tk` 计数 0，未宣称修复；余三处口径一致 |
| D4 | PROGRESS §3.5 记录 Step 1-10 全序与状态 | 读回执行序 | PROGRESS | ✅ Step 1-10 全行登记（§3.5） |
| D5 | 依赖版本引用与 `pyproject.toml` 一致；无新增依赖 | 读回 `requires-python`、dev extras | Phase 2 检查点 | ✅ `>=3.10` 未变；`pyproject.toml` diff 空 |
| D6 | README 三处计数无残留 `503` | `Select-String "503"` 空输出 | A7 | ✅ 计数 0 |

## 5. 兼容性

> **DoR**：DESIGN §3.4 声明已复核；**DoD**：逐面读回或断言。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测（2026-11-05） |
|----|--------|--------------|------|---------------------|
| E1 | `pyproject.toml` 零改动（含 `testpaths` / `addopts` / black line-length） | `git diff --stat pyproject.toml` 空 | S3 | ✅ diff 空 |
| E2 | 公开 API / 模块 import 零改动 | `git diff --stat core tests scripts` 空 | DESIGN §3.4 | ✅ diff 空（含 `cli.py`） |
| E3 | 本地默认后端行为未被改变，文档不宣称修复 Tk | README 新节措辞读回 | RESEARCH §1.1 / R4 | ✅ README `Tk` 计数 0；新节只说明用 Agg |
| E4 | CI 矩阵 3.10/3.11/3.12 未改；三版本未本地实测的部分标 `[未在远端执行]` | V1 + 声明 | S4（T1） | ✅ matrix 未改；3.10/3.11 运行结果 `[未在远端执行]` |
| E5 | 无新增 Action / pip 依赖 | `git diff` 仅 `env` 与命令；`pyproject.toml` 空 diff | DESIGN §4 | ✅ diff 仅 `env` 2 行 + 命令 1 行 |

## 6. 代码质量

> **DoR**：零代码批次，质量面收敛到配置格式与文档卫生；**DoD**：机器可判。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测（2026-11-05） |
|----|--------|--------------|------|---------------------|
| F1 | 无新增 `TODO` / `FIXME`（除本清单 F1 规则文本自身） | 本批四文档 `Select-String`，排除自身规则行 | Phase 3 模板 | ✅ 命中 1 处 = 本行规则文本自身，无残留标记（见 F-9-2） |
| F2 | YAML 缩进 2 空格、键序最小化（`env` 紧随 `runs-on`） | `git diff` 审查 + PyYAML 解析 | DESIGN §3.3 | ✅ 缩进 2 空格；解析通过 |
| F3 | README 新增段无行尾空白 | `Select-String "  $"` 空输出 | 文档卫生 | ✅ 计数 0 |
| F4 | 无临时脚本 / 断言产物残留 | `%TEMP%` 删除记录 + `git status` 无新增 | IMPL §2.6 | ✅ `p008_verify.py` 已删除；`git status` 无新增文件 |
| F5 | 无 `[未取证]` 项被写成 ✅ | §8 取证矩阵逐行核对 | RULE-6 | ✅ 逐行核对：C4 标 `[未入仓-不可重放]`、远端 CI 标 `[未在远端执行]`、black/mypy 如实 fail——无未取证项标 ✅ |

## 7. 门禁链验收（Step 10）

| 门禁 | 命令 | 预期 verdict | 实测 verdict | 证据 |
|------|------|--------------|--------------|------|
| probe | `echo Spec_Runner OK` | pass | **pass（exit 0）** | adapter `probe` 自检，session `factorv3-probe-20261105`（该子命令固定命名，不接 `--session`） |
| unit-tests | `set MPLBACKEND=Agg&& <PY312> -m pytest tests -q` | **pass**（本批核心门禁） | **pass（exit 0）** | session `factorv3-p008-env-norm-20261105` seq 9：`509 passed, 82 warnings in 32.23s` |
| black-check | `<PY312> -m black --check core tests 2>&1` | **fail（预期基线 75）** | **fail（exit 1）** | seq 11：`75 files would be reformatted, 5 files would be left unchanged.`（与基线一致，无漂移） |
| mypy-check | `<PY312> -m mypy --explicit-package-bases core` | **fail（预期基线 168）** | **fail（exit 1）** | seq 12：`Found 168 errors in 20 files (checked 30 source files)`（与基线一致，无漂移） |

> 本批零代码，`black-check` / `mypy-check` 的 fail 属既有技术债（P-003 / P-007），不是本批回归；Step 10 重跑以确认无漂移，不将其改写为 ✅。

## 8. 取证矩阵（E1-E5）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| PyYAML 结构断言脚本（E2） | A1-A4、B1、B3、C1、C3 | ✅ V1 三轮读数（RED 2 项 → GREEN 0 项）；反例 YAML 3/3 拦截；C1 `0.002s`；`len(steps)=6`。脚本未入仓，读数以 §10 记录为准（见 C4） |
| README 断言脚本（E2） | A5-A7、B2、D6 | ✅ V2 三轮读数（RED 1 项 → GREEN 0 项）；反例 2/2 拦截；`503` 计数 0；5 要素命中 |
| `pytest` 全量输出（E1） | B4、C2、E2 | ✅ `509 passed, 82 warnings in 30.18s`（2026-11-05，Agg + Python312） |
| `git diff` / `git status`（E1） | A8、A9、E1、E2、E5、F2、F4 | ✅ `--numstat`：tests.yml `3 1`、README `40 3`；`core/ tests/ scripts/ pyproject.toml cli.py` diff 空；临时脚本已删、无新增未跟踪脚本 |
| `Select-String` 机械检索（E1） | D1、D3、F1、F3 | ✅ README `503`=0、`Tk`=0、行尾空白=0；四文档 TODO/FIXME 仅 F1 规则行自身 |
| 静态读码（E3，须绑 commit hash） | C4、D5、E3 | ⚠️ C4 = `[未入仓-不可重放]`（执行前读码：仅 `copy/sys/time/pathlib/yaml`）；D5/E3 读回 `pyproject.toml`、README `06e9e11`（E3） |
| 门禁 session + `replay`（E1） | §7 四行 | ✅ probe **pass**（session `factorv3-probe-20261105`）；unit-tests **pass**（seq 9，`509 passed, 32.23s`）；black-check **fail**（seq 11，`75 files would be reformatted, 5 unchanged` = 基线）；mypy-check **fail**（seq 12，`Found 168 errors in 20 files` = 基线）；`replay: 12 rows OK` |
| 盲区扫描（E4，范围：README 新节全文 + `tests.yml` 全部键） | 无设计外改动 | ✅ `git diff` 全文仅 `env` 块 +2 与命令 1 行；README 新节（L231-L268）与 IMPL §2.3.3 逐字一致；**发现 0 项设计外改动**；文件末尾 no-newline 为 `tests.yml` 既有状态（diff 上下文侧） |
| 远端 CI（已执行，2026-11-05） | E4 三版本 / U-001 远端判据 | ⚠️ run `41970636863` @ `06e9e11` = **failure**：3.10 `14 failed, 477 passed, 18 errors`（7.05s）；3.11/3.12 因 3.10 失败被 fail-fast 取消。根因**非后端配置**：① `data/test_ashare/close.pkl` 被 `.gitignore:62`（`data/`）忽略 → **9 failed + 18 errors**（27 项数据测试）；② `tests/test_distillation_isolation.py:255-327` 硬编码 `F:\Coding\...\gurus` → 4 failed；③ `numba` 不在 `pyproject.toml` → 1 failed。历史两次运行（`df652f9`、`116426e`）同样 `failure`（`gh run list`），即既有红基线，非本批 diff 引入 |

## 9. Step 8 一致性 Review

- **时点**：2026-11-05，四文档（RESEARCH / DESIGN / IMPL / CHECKLIST）全部完稿后独立执行（RULE-1）；未预填结论
- **审查者**：单 Agent 自查（单视角）（RULE-4）
- **审查方式**：机械校验（Python 正则提取 + 键值计数）贴读数 + Grep 定位 + 读回比对

**一致性表**：

| 检查对 | 核对内容 | 结果 |
|--------|----------|------|
| RESEARCH ↔ DESIGN | A 方案三要素（job 级 `env` / `python -m pytest` / README Testing）与 DESIGN §3.2/§3.3 逐项对应；A1-A3 假设经 DESIGN §3.5 显式携带 | 一致 |
| DESIGN ↔ IMPL | §3.1-§3.4 契约 ↔ IMPL §2.3.1-§2.3.4（env 仅 1 键、命令精确串、matrix/mypy 不变、插入点 L229/L231、3 处计数、README 节全文） | 一致 |
| IMPL ↔ CHECKLIST | T-1/T-2→A1-A4；T-3/T-4→A5-A7；T-0→B6；T-5→B4+§7 门禁；回退→A9 | 一一对应 |
| 全部 ↔ 外部来源 | S1/S3/S4/S5/S6 锚点表（DESIGN §9、IMPL §4）均标 RESEARCH §6 已验证 | 可解析 |
| 断言延续 | U-001→DESIGN U-001′（固定 Agg 全绿）；U-005→U-005′（README 解释器口径）；「不宣称修复 Tk」RESEARCH R4 / DESIGN §6 / CHECKLIST E3 三处同口径 | 一致 |

**机械校验读数（2026-11-05）**：

| 断言 | 方式 | 读数 |
|------|------|------|
| 相对链接可解析 | 正则提取 + `Path.exists()` | 四文档 + PROGRESS 互引 **17 条全部 True** |
| 键值计数矩阵 | `str.count`（顺序 RESEARCH/DESIGN/IMPL/CHECKLIST/PROGRESS） | `MPLBACKEND` 12/17/12/4/7；`python -m pytest` 5/8/8/2/0；`509 passed` 2/9/7/5/6；`Agg` 23/25/12/4/8；`未在远端执行` 1/5/1/4/0 |
| `python -m pytest` 在 PROGRESS 为 0 | 读回 §3.5 | 台账不承载命令真值，属角色分工，非矛盾 |
| `50 files` 在 RESEARCH/PROGRESS 为 0 | 读回 | RESEARCH 只记 509 passed 证据、无文件数断言；真值载体 DESIGN(4)/IMPL(3)/CHECKLIST(3) 命中，无冲突值 |
| 命令两种形态 | 读回比对 | CI `python -m pytest tests/ --tb=short -q`（IMPL §2.3.1）vs adapter 门禁 `... -m pytest tests -q`（CHECKLIST §7，与 DESIGN_spec_runner §3.3 一致）——载体不同、各自上游一致，非矛盾 |
| Agg 耗时读数漂移 | 读回 | 20.02s（2026-11-04 日志，RESEARCH/DESIGN 引）与 31.99s（2026-11-05 Step 4/6 复跑）为同一断言两次 E1 读数；CHECKLIST C2 阈值 ≤40s 覆盖，非矛盾 |
| Tk 字样分布 | `count` | IMPL 为 0——IMPL 不回答 Tk 问题（DESIGN §10「职责外」），README 新节措辞亦未宣称修复，无冲突 |

**派生需求登记（SPEC_PROCESS Step 8）**：

| ID | 派生需求 | 产生处 | 验收出口 |
|----|----------|--------|----------|
| D-R1 | README 提醒注释含 `py -3.12 -m pytest` 前缀写法 | F-I1 修正（DESIGN §3.3 要素 4 未显式含） | A6 + V2 |
| D-R2 | V1/V2 断言脚本总耗时 < 2s 定量阈值 | C1（IMPL §2.4 仅定性「毫秒级」） | C1 实测 |
| D-R3 | README 新增段无行尾空白 | F3（IMPL 未列） | F3 `Select-String "  $"` |
| D-R4 | 四类反例坏样本构造并确认断言拦截 | B3（IMPL §2.5 边界表的执行细化） | B3 读数 |

**发现并修复（1 项，P3）**：

| ID | 发现 | 修复 |
|----|------|------|
| F-S1 | §4 D1 原文「四方值一致」，机械矩阵显示 RESEARCH/PROGRESS 不含 `50 files`、PROGRESS 不含 `python -m pytest`——按「四方全覆盖」解读 D1 无法达成 | D1 措辞改为「四文档无冲突值；真值载体 DESIGN/IMPL/CHECKLIST 逐值命中」，与实际口径一致 |

**结论**：无 P1/P2 矛盾；1 项 P3 已修复；4 项派生需求已登记且各有验收出口；通过 Step 8 门禁，可进入 Step 9 实施。

> **门禁记录（2026-11-05）**：session `factorv3-p008-env-norm-20261105`，`step-consistency` pass（门禁命令用 ASCII 模式串，规避 R7）。

## 10. Step 9 红→绿记录

- **执行序**：T-0 临时脚本 → RED → T-1/T-2（CI）→ V1 GREEN → T-3/T-4（README）→ V2 GREEN → 全量回归 → 清理 → 门禁（IMPL §2.6）
- **脚本位置**：`C:\Users\Peng\AppData\Local\Temp\p008_verify.py`（未入仓，执行后删除）

| 阶段 | 命令 | 读数 |
|------|------|------|
| RED | Python312 `p008_verify.py` | `V1 YAML: FAIL (2 项)`（A1 env=None、A2 命令缺 `-m`）；`V2 README: FAIL (1 项)`（A5 节缺失）；`RESULT: RED (3 项失败)`，exit 1 |
| GREEN-1（仅 CI 改后） | 同上 | `V1 YAML: PASS (0 项)`；`V2 README: FAIL (1 项)`；`RESULT: RED (1 项失败)`，exit 1 |
| GREEN-2（README 改后） | 同上 | `V1 YAML: PASS (0 项)`；`V2 README: PASS (0 项)`；`RESULT: GREEN (0 项失败)`，exit 0 |
| 反例（贯穿三轮） | 同上 | B3 `5/5 拦截`（YAML：step 级 env / 缺 `-m` / mypy 被改；README：`49 files` / 残留 503） |
| 回归 | `$env:MPLBACKEND='Agg'` + Python312 `-m pytest tests -q` | `509 passed, 82 warnings in 30.18s` |
| 门禁 | adapter `gate unit-tests` | `verdict=pass exit=0`；seq 9 `509 passed, 82 warnings in 32.23s` |
| 清理 | `Remove-Item` 临时脚本 + `git status` | 脚本已删；工作区无新增未跟踪脚本 |

**变更实测（与 IMPL 预估对比）**：

| 文件 | 预估 | 实测（`git diff --numstat`） | 说明 |
|------|------|------------------------------|------|
| `.github/workflows/tests.yml` | +2 / ~1 | `3 1`（+3/-1） | 与预估等价（env 2 行 + 命令 1 行） |
| `README.md` | +35 / -3 | `40 3`（+40/-3） | 高于预估 5 行（见 F-9-1） |
| `docs/PROGRESS.md` | +2 / ~1 | 本批跨多步累计（Step 1-10 记录） | 台账增量随步骤增长，非单次改动 |

**发现并修复（2 项，均 P3）**：

| ID | 发现 | 处理 |
|----|------|------|
| F-9-1 | README 实际新增 40 行，超过 IMPL §2.2 预估的 35 行（多出 5 行为空行分隔与提醒注释折行） | 保留正文（内容完整优先）；IMPL §2.2 预估改为「+40 / -3（实测；计划 +35）」，偏差在此登记 |
| F-9-2 | F1 的 DoD 写「`Select-String` 空输出」，实测命中 1 处——为 CHECKLIST 自身 F1 规则文本中的 `TODO`/`FIXME` 字样，非代码残留 | F1 定义改为「排除本清单 F1 规则文本自身」；实测按 0 残留判定 |

**结论**：RED 3 项失败 → GREEN 0 项失败；反例 5/5 持续拦截；509 回归与门禁 pass；2 项 P3 已处理。Step 9 完成，可进入 Step 10 ADD 审计。

## 11. ADD 审计（Step 10）

- **时点**：2026-11-05，实施完成后独立执行（RULE-1）
- **审查者**：单 Agent 自查（单视角）（RULE-4）
- **取证方式**：门禁链重跑 + `git diff` 全文盲区扫描 + 读码，证据绑 §8 矩阵

### Phase 0: Spec 质量门

- [x] DESIGN 无「合理处理 / 适当时机 / 酌情」类不可审计措辞（`Grep` 命中 0）
- [x] 每个设计元素可对应到实现或测试：D1→env 断言、D2→命令断言、D3→README 断言、D4→计数断言、D5→范围断言（§8）

### Phase 1: 完整性（design → code）

- [x] DESIGN §3.1 环境变量契约 → `jobs.test.env` 存在且仅 1 键（A1）
- [x] DESIGN §3.2 五字段（runs-on / matrix / env / steps[4] / steps[5]）→ 全部落地且未动字段逐字保持（A2-A4）
- [x] DESIGN §3.3 README 变更面 → 新节 + 3 处计数精确串（A5-A7）
- [x] DESIGN §6 六类错误场景 → 处置声明均有对应验证（YAML 解析阻断 / 如实 red / `[未在远端执行]`）

### Phase 2: 忠实度（双向对照）

- [x] IMPL §2.3.1 契约表 6 行 ↔ `tests.yml` 逐键一致（V1 精确串）
- [x] IMPL §2.3.3 README 节全文 ↔ README L231-L268 **逐字一致**（盲区扫描 E4）
- [x] 3 处计数精确串逐一命中，无多余改动（`git diff --numstat` 40/3 对账）
- [x] 未新增 IMPL 契约之外的 CI 键或 README 段落

### Phase 3: 必要性（code → design）

- [x] `tests.yml` 每处改动均有 DESIGN 决策依据（`env`=D1、`python -m pytest`=D2）
- [x] README 新节每段均对应 DESIGN §3.3 要素 1-4（含 D-R1 前缀提醒）
- [x] 盲区扫描发现 **0 项设计外改动**（§8 E4 行）

### Phase 4: 语义

- [x] 目标未被降级：不是「YAML 能解析」，而是「U-001 本地收敛 + 反例拦截 + 509 回归 + 门禁入流」四层证据
- [x] 已知 fail 未被伪装：black-check / mypy-check 重跑如实 fail 且读数与基线一致（§7）；C4 如实标 `[未入仓-不可重放]`
- [x] Iron Law 核对：测试通过 ≠ 设计落地——以 §8 取证矩阵双向映射补足（9 项验收组 ↔ 9 类证据手段）

## 12. 最终结论

- **P1/P2 阻断项**：0
- **P3 项**：累计 9 项（F-D1/F-D2、F-I1/F-I2/F-I3、F-S1、F-9-1/F-9-2）+ 1 项证据注记（C4 不可重放），全部已处理或如实标注
- **门禁链**：3 pass（probe、unit-tests、step-implement 内嵌 unit-tests）+ 2 expected-fail（black-check 基线 75、mypy-check 基线 168，均无漂移）
- **验收组**：A1-A9 / B1-B6 / C1-C4 / D1-D6 / E1-E5 / F1-F5 共 30 项，29 项 ✅ 绑证据，1 项（C4）`[未入仓-不可重放]`；远端 CI = failure（根因非本批，见 §8）
- **U-001**：本地达成（Agg `509 passed`，E1 × 3）；**远端未达成**——run `41970636863` 的三类失败根因均指向测试环境缺失（数据夹具被忽略 / 测试硬编码 Windows 路径 / 缺 `numba`），**本批改动仅为 `tests.yml` 的 env 与命令 + README**，不含 `tests/` 或数据；故 U-001 **不关闭**，待 P-009 修复后重跑远端再判
- **U-005**：**已关闭**——收敛口径（RESEARCH §5.3）「README 写明测试解释器选择方式」达成（V2 断言 PASS + CI 矩阵显式版本）
- **状态**：done（提交 `06e9e11` 已推送）；远端复核发现既有红基线，登记 P-009 / U-007（见 [PROGRESS](PROGRESS.md)）
