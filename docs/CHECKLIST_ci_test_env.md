# CI 测试环境缺失（P-009） · 审查验收清单

> **文档编号**: CHECKLIST_ci_test_env
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-05
> **状态**: 已完成（Step 10 审计通过；39/39 验收项达成；待提交，提交后补绑 E3 hash 并观测远端 CI）
> **上游**: [DESIGN_ci_test_env.md](DESIGN_ci_test_env.md)（Step 4 通过，含 C-1/C-2 修正） · [IMPL_ci_test_env.md](IMPL_ci_test_env.md)（Step 6 通过）
> **填写规则**: 本清单在 Step 7 只定义「怎么算做完」；「实测」列一律为 `[待 Step 9]`，**禁止实现前预填**（RULE-1）。每条 ✅ 必须绑定证据出口；无证据只能标 `[未在远端执行]` / `[未入仓-不可重放]` / `[未取证]`。

---

## 1. 功能完整性

> **DoR**：DESIGN §3 契约 + IMPL §2.3 接口定义均已复核；**DoD**：每项有 E1/E2 读数或诚实降级标注。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | `scripts/prepare_test_fixture.py` 存在；`--help` exit 0；argparse 默认值符合契约（`out_dir=DEFAULT_OUT_DIR` / `n_stocks=50` / `n_days=100` / `seed=42` / `start="2024-01-02"` / `force=False`） | `--help` 输出 + importlib 读取 `parser` defaults | DESIGN §3.1 | ✅ `help_exit=0`；6 个参数默认值经 importlib 读取全部符合契约 |
| A2 | 生成 7 个 pkl 且契约达标：`(100,50)`、0 NaN、`adj≡1.0`、`suspend≡0`、`industry≡1`、OHLC 违规 0、`max_abs_ret ≤ 0.05`、总字节 266–326 KB | V1 脚本 stdout | DESIGN §3.2；S11/S12 | ✅ 7×`(100,50)`、0 NaN、`adj=[1.]`/`suspend=[0]`/`industry=[1]`、OHLC 违规 0/0/0、收益 −0.0488~0.0513、**296037 B** |
| A3 | 覆盖保护：默认路径（已有真实夹具）无 `--force` → **exit 2**，且 7 个 pkl 的 `Length` 与 `LastWriteTime` 均不变（基线：各 42419 B / `2026-11-05 13:31:40`） | V2 脚本：`$LASTEXITCODE` + 前后快照比对 | DESIGN §3.1（R8/P14） | ✅ `GOTEXIT=2`；`UNCHANGED=True`；stderr 列出 7 个已存在文件 |
| A4 | 参数下限：`--n-stocks 30` 与 `--n-days 50` 均 **exit 1**，目标目录不产生文件 | V1b 脚本：两次子进程调用 + 目录列表 | DESIGN §3.1 | ✅ 两次均 exit 1；`low_dir_exists=False` |
| A5 | `--out-dir` 相对路径按 `REPO_ROOT` 解析（非 cwd）：`_resolve_out_dir("tmp/x")` == `REPO_ROOT/"tmp/x"` | importlib 加载模块后直接调用断言 | DESIGN §3.1；S3 | ✅ `tmp/x` → `F:\...\tmp\x`；绝对路径原样；`TARGET_FILES=7` |
| A6 | 27 项数据测试在合成夹具上全过且**零 skip** | cwd = `%TEMP%\p009_green` 跑两文件 → `27 passed` | RESEARCH P13；IMPL §2.5 V2b | ✅ `27 passed in 9.05s`（black 修正后复跑 `8.53s`），0 skip |
| A7 | 5 处硬编码全部替换：`F:\Coding\...\gurus` 命中 **0**；`GURU_DIR` 定义 1 处、引用 5 处；`test_distillation_isolation.py` **19 passed** | Grep 计数 + pytest 输出 | DESIGN D3；S3 | ✅ `hardcoded_paths=0`；`guru_dir_hits=6`（1 定义 + 5 引用）；`19 passed in 0.84s` |
| A8 | numba 文件模块级 `pytest.importorskip("numba")` 位于 `sys.path.insert` 之后、首个 `def` 之前；本地 `7 passed` | 静态行号断言 + pytest 输出 | DESIGN D4；S1/S10 | ✅ `importorskip_hits=1`（L24；`sys.path.insert` L21 之后、`def` L27 之前）；`7 passed, 7 warnings in 9.18s` |
| A9 | CI YAML：`len(steps)==7`；新增 step 索引 **4**（`Install dependencies` 之后、`Run tests` 之前）；`name=="Prepare test fixture"`；`run=="python scripts/prepare_test_fixture.py"`；`Run tests`(索引 5) 与 `mypy`(索引 6) 逐字不变 | V5 PyYAML 断言脚本 | DESIGN §3.3 D | ✅ V5 PASS：索引 4/5/6 = Prepare/Run/mypy；`env` 单键；matrix 与 mypy `\|\| true` 不变 |
| A10 | 零改动面：`core/` `filter/` `tools/` `examples/` `pyproject.toml` `.gitignore` `README.md` `scripts/prepare_test_data.py` 全部 diff 空；CI step 无 `if` / `continue-on-error` / `\|\| true` | `git diff --stat` + V5 否定断言 | DESIGN §2 职责表；R9 | ✅ 保护路径 `git diff --stat` 空输出；V5 无 `if`/`continue-on-error`/step 级 `env` |

## 2. 测试完整性

> **DoR**：IMPL §2.5 的 V0-V7 已定义；**DoD**：RED/GREEN 读数可复现，正反例均有记录。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | V0 RED（数据）：空目录（无 `data/test_ashare`）跑两数据测试文件 → **`9 failed, 18 errors`** | pytest 输出（E1） | RESEARCH P12；CI run `41970636863` | ✅ `9 failed, 18 errors in 8.01s`（18 errors 全部 `FileNotFoundError: 价格文件不存在: data\test_ashare\close.pkl`） |
| B2 | V0b RED（静态）：硬编码 **5 处**；numba 文件无 `importorskip`；`tests.yml` 无 `Prepare test fixture` | Grep + Select-String 输出 | IMPL §2.6 | ✅ `hardcoded_paths=5` / `importorskip_hits=0` / `fixture_step_hits=0` |
| B3 | V1 GREEN：A2 全部断言通过 | 脚本 stdout + exit 0 | IMPL V1 | ✅ 0 项失败（A2 读数，`total bytes: 296037`） |
| B4 | V2b GREEN：A6 `27 passed`（不得 skip） | pytest 输出 | IMPL V2b | ✅ `27 passed in 9.05s`（复跑 `8.53s`） |
| B5 | V3/V4/V5 GREEN：A7/A8/A9 全部通过 | 三个断言脚本 stdout + exit 0 | IMPL V3-V5 | ✅ V3/V4/V5 全 PASS |
| B6 | 全量回归 `509 passed`（Agg + Python312，末尾仅 1 次） | pytest 输出 | RESEARCH P14 基线 | ✅ `509 passed, 82 warnings in 21.45s`（直接）/ `23.06s`（gate seq 7） |
| B7 | 红→绿记录完整：RED ≥4 条失败读数、GREEN ≥5 条通过读数 | §10 表逐条读数 | SPEC_PROCESS Step 9 | ✅ §10：RED 4 条 + GREEN 6 条 |
| B8 | 不新增仓内测试文件；测试总数仍 509（本地）/ CI 502 passed + 1 skipped | `git status --short` 无 `tests/test_*.py` 新增；pytest 计数 | DESIGN §1.1 | ✅ 仅 2 个既有测试文件 M；本地总数 509 不变 |

## 3. 性能验收

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | 单个夹具生成耗时 < 5s | 脚本内 `time.perf_counter()` 打印 | IMPL §5 | ✅ `0.006s` |
| C2 | 27 项数据测试耗时 ≤ 20s（规划期预演 12.06s） | pytest 末行 | E1 预演 | ✅ `9.05s` / 复跑 `8.53s` |
| C3 | 全量 pytest 耗时 ≤ 45s（基线 30.18s / 32.97s） | pytest 末行 | E1 | ✅ `21.45s` |
| C4 | 夹具体积 266–326 KB（预演 296037 B） | 脚本打印 `files bytes` | E1 预演 | ✅ `296037` B（≈289 KB） |

## 4. 文档一致性

> **DoR**：四文档完稿；**DoD**：机械比对 + 链接可解析。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | 四文档无冲突值；真值载体 DESIGN/IMPL/CHECKLIST 对 `502 passed` / `1 skipped` / `27 passed` / `509 passed` / `7 个 pkl` 逐值命中 | `Select-String` 键值矩阵 | Step 8 一致性表 | ✅ Step 8 §9 矩阵无冲突值（`502 passed` D4/I2/C2/P1；`1 skipped` D5/I5/C3/P2；`27 passed` 五文档全命中） |
| D2 | 四文档 + PROGRESS 相对链接全部可解析 | Python 正则 + `Path.exists()` | Phase 3 检查点 | ✅ 五文档互引 **32 条全部可解析，0 broken** |
| D3 | C-1/C-2 修正口径一致：`1 skipped` 在 DESIGN §1.1 / §3.3 / §3.4 / §6 / §11 五处一致；`exc_type=ImportError` 语义在 DESIGN §6 与 IMPL §2.7 一致 | 读回比对 | C-1 / C-2 | ✅ DESIGN 恰 5 处；DESIGN §6 与 IMPL §2.7 语义一致（F-S1 修复后） |
| D4 | PROGRESS §3.6 记录 Step 1-10 全序与状态 | 读回执行序 | PROGRESS | ✅ Step 1-9 全行登记（Step 10 行由 Step 10 补写） |
| D5 | 依赖版本引用与 `pyproject.toml` 一致（L10 / L54 / L62 / L100）；无新增依赖 | 读回 + `git diff pyproject.toml` 空 | Phase 2 检查点 | ✅ `git diff pyproject.toml` 空；L10/L54/L62/L100 未变 |
| D6 | 远端项一律标 `[未在远端执行]`，不写成 ✅ | 四文档计数核对 | R6 / RULE-6 | ✅ 远端项计数 DESIGN 4 / IMPL 2 / CHECKLIST 4；无 ✅ 冒充 |

## 5. 兼容性

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | `pyproject.toml` 零改动（依赖 / `testpaths` / `addopts` / black line-length） | `git diff --stat pyproject.toml` 空 | DESIGN §3.4 | ✅ diff 空 |
| E2 | 生产代码与模块 import 零改动 | `git diff --stat core filter tools examples` 空 | DESIGN §3.4 | ✅ diff 空（含 `examples/`） |
| E3 | 本地有 numba 时行为不变（7 passed）；无 numba 时整模块 skip 且**只计 1 个 skipped** | 本地 pytest + `%TEMP%\p009_skip_probe` 复跑 | C-1；S10 | ✅ 本地 `7 passed`；模块级 skip 探针实测「3 测试模块 → 1 skipped」（C-1） |
| E4 | CI 矩阵 3.10/3.11/3.12 未改；3.10/3.11 运行结果标 `[未在远端执行]` | V5 + 声明 | S13 | ✅ V5 断言 matrix 未改；3.10/3.11 `[未在远端执行]` |
| E5 | 无新增 Action / pip 依赖 | `git diff tests.yml` 仅 1 step；`pyproject.toml` 空 diff | DESIGN §4 | ✅ `tests.yml` +3/-0；`pyproject.toml` 空 diff |

## 6. 代码质量

> **DoR**：本批唯一新增代码为脚本；**DoD**：机器可判。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 无新增 `TODO` / `FIXME` 标记（排除本清单 F1 规则行自身与文档中对这些字样的引用） | 本批五文档 `Select-String` 逐行排除 | Phase 3 模板 | ✅ 命中 1 处 = 本行规则文本自身；其余四文档与新脚本 0 |
| F2 | `scripts/prepare_test_fixture.py` 满足 `black --check`（line-length 100）；`gate black-check` 基线 75 不漂移 | 单独 `black --check scripts/...` + `gate black-check` 读数 | DESIGN §1.1 注记 | ✅ `1 file would be left unchanged` exit 0（1 处三行调用合并，F-9-3）；gate 基线 75 无漂移 |
| F3 | 脚本 UTF-8、无行尾空白（`Select-String "  $"` 空输出） | 机械检索 | 文档卫生 | ✅ 行尾空白 0；UTF-8 无 BOM |
| F4 | 无临时脚本 / 探针残留：`%TEMP%\p009_*` 已删除；`git status --short` 无未跟踪临时文件 | 目录列表 + `git status` | IMPL §3 | ✅ `p009*` 残留 0；`git status` 仅 4 个目标文件 + 五文档 |
| F5 | 无 `[未取证]` 项被写成 ✅；门禁 expected-fail 如实标注 | §8 取证矩阵逐行核对 | RULE-6 | ✅ C4/远端/black/mypy 如实标注；无未取证 ✅ |
| F6 | 脚本无网络调用、无 `subprocess`、无外部数据源（仅 stdlib + numpy + pandas） | 静态读码（E3，绑 commit hash） | DESIGN §3.1 | ✅ import 仅 `argparse/sys/time/pathlib/numpy/pandas`；无网络/`subprocess` |

## 7. 门禁链验收（Step 10）

| 门禁 | 命令 | 预期 verdict | 实测 verdict | 证据 |
|------|------|--------------|--------------|------|
| probe | `echo Spec_Runner OK` | pass | **pass（exit 0）** | session `factorv3-probe-20261105`（Step 10 复跑） |
| unit-tests | `set MPLBACKEND=Agg&& <PY312> -m pytest tests -q` | **pass**（本批核心） | **pass（exit 0）** | seq 7：`509 passed, 82 warnings in 23.06s` |
| black-check | `<PY312> -m black --check core tests 2>&1` | **fail（预期基线 75）** | **fail（exit 1）** | seq 8 + 复跑 seq 10：`75 files would be reformatted, 5 files would be left unchanged`（与基线一致） |
| mypy-check | `<PY312> -m mypy --explicit-package-bases core` | **fail（预期基线 168）** | **fail（exit 1）** | seq 9 + 复跑 seq 11：`Found 168 errors in 20 files (checked 30 source files)`（与基线一致） |

> `black-check` / `mypy-check` 的 fail 属既有技术债（P-003 / P-007），**不得**改写为 ✅；Step 10 只核对读数与基线一致。

## 8. 取证矩阵（E1-E5）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| 断言脚本 V1/V1b/V2/V3/V4/V5（E2；`%TEMP%`，不入仓） | A1-A5、A7-A9、B3、B5、B8、C1、C4 | ✅ 六脚本全 PASS；读数见 §1/§2；⚠️ 已按 IMPL §2.6 删除，**`[未入仓-不可重放]`**，读数以 §10 为准 |
| `pytest` 定向输出（E1） | A6、A7、A8、B1、B4、B8、C2 | ✅ V0 `9 failed, 18 errors in 8.01s`；V2b `27 passed 9.05s`；distillation `19 passed 0.84s`；numba `7 passed 9.18s` |
| `pytest` 全量输出（E1） | B6、B8、C3、E3 | ✅ `509 passed, 82 warnings in 21.45s`（直接）/ `23.06s`（gate seq 7） |
| `git diff` / `git status` / `git ls-files`（E1） | A10、B8、E1、E2、E5、F4 | ✅ numstat：tests.yml `3 0`、distillation `9 5`、numba `4 0`；保护路径 diff 空；`p009*` 残留 0 |
| `Select-String` / `Grep` 机械检索（E1） | A7、A10、B2、D1、D3、D6、F1、F3 | ✅ 硬编码 5→0；`GURU_DIR` 6；F1 仅规则行；行尾空白 0 |
| 静态读码（E3，须绑 commit hash） | A8 位置、F2、F6 | ⚠️ 工作树未提交（HEAD `17e6f26`）；A8 位置 / F2 black / F6 import 清单已读；**提交后补绑 hash** |
| 文件快照比对（E1） | A3（pkl `Length` + `LastWriteTime`） | ✅ `UNCHANGED=True`（7×42419 B / mtime 未变） |
| 门禁 session + `replay`（E1） | §7 四行 | ✅ unit-tests **pass**（seq 7）/ black **fail**（seq 8、10）/ mypy **fail**（seq 9、11）/ probe **pass**；`replay: 11 rows OK` |
| 盲区扫描（E4，范围：脚本全文 + 2 个测试文件 diff + `tests.yml` 全部键） | 无设计外改动 | ✅ 三文件 diff 全文 + 脚本全文读码（§11 Phase 2/3）：**0 项设计外改动**；保护路径 diff 空 |
| 远端 CI（需 push） | U-007 / U-001 远端判据 | `[未在远端执行]` |

## 9. Step 8 一致性 Review

- **时点**：2026-11-05，四文档（RESEARCH / DESIGN / IMPL / CHECKLIST）全部完稿后独立执行（RULE-1）；未预填结论
- **审查者**：单 Agent 自查（单视角）（RULE-4）
- **审查方式**：机械校验（Python 正则提取 + 键值计数矩阵）贴读数 + 旧值残留逐行判定 + 读回比对

**一致性表**：

| 检查对 | 核对内容 | 结果 |
|--------|----------|------|
| RESEARCH ↔ DESIGN | A1/B1/C1 裁决 ↔ D1/D3/D4；R9（不动 gitignore）↔ §2 职责表 + A10；P13 → A1′ 显式携带 | 一致 |
| DESIGN ↔ IMPL | §3.1 CLI/退出码契约 ↔ §2.3.2；§3.3 精确 diff ↔ §2.2/§2.3.3；C-1/C-2 修正 ↔ §2.7（F-S1 修复后同步列表一致） | 一致 |
| IMPL ↔ CHECKLIST | T-1→A1-A6；T-2→A7；T-3→A8；T-4→A9/A10；T-0→B1/B2；T-5→B6+C3+§7；回退→F4；V 系列逐段映射 A/B 组 | 一一对应 |
| 全部 ↔ 外部锚点 | S1-S15 在 DESIGN §9 / IMPL §4 锚点表均标验证状态；S10-S15 为 IMPL 新增实施层锚点 | 可解析 |
| 断言延续 | U-007→U-007′、U-008→U-008′、U-001→U-001′（DESIGN §10）；「27 项不得 skip」五处同口径（机械校验第 5 项）；C-1 `1 skipped` 五处一致（CHECKLIST D3 判据与机械读数 5 吻合） | 一致 |

**机械校验读数（2026-11-05，`%TEMP%\p009_consistency_check.py`）**：

| 断言 | 方式 | 读数 |
|------|------|------|
| 相对链接可解析 | 正则提取 + `Path.exists()` | 五文档互引 **32 条全部可解析，0 broken** |
| 键值计数矩阵（R/D/I/C/P） | `str.count` | `502 passed` 0/4/2/2/1；`1 skipped` 0/5/5/3/2；`27 passed` 3/2/7/3/2；`509 passed` 4/4/1/3/9；`prepare_test_fixture` 2/8/6/3/1；`prepare_test_data` 5/6/2/1/1；`importorskip` 5/6/15/2/5；`GURU_DIR` 1/9/3/1/**0**；`未在远端执行` 0/4/2/4/0 |
| `7 skipped` 残留判定 | 逐行读上下文 | 4 处（DESIGN L356 F-D3 历史发现 / DESIGN L387 C-1 修正记录 / IMPL L223 C-1 记录 / PROGRESS L171 Step 5 行）**全部为修正或历史记录上下文，无一处作为当前预期值** |
| 退出码契约 | 字面检索 | DESIGN 以表格定义 0/1/2；IMPL/CHECKLIST 用 `exit N` 措辞——形式不同、语义一致（角色分工说明，见 D-R2） |
| `27 项不得 skip` 口径 | 逐行定位 | RESEARCH §5 / DESIGN §1.1 / IMPL V2b / CHECKLIST B4 / PROGRESS 验收口径，**5 处同口径** |
| `GURU_DIR` 在 PROGRESS 为 0 | 读回 | 台账不承载代码符号名，属角色分工，非矛盾（P-008「`50 files` 为 0」同型先例） |
| `未在远端执行` 在 RESEARCH 为 0 | 读回 | RESEARCH 为调研层，无远端断言义务；远端声明载体为 DESIGN §10 / IMPL §2.6 / CHECKLIST §8 |

**派生需求登记（SPEC_PROCESS Step 8）**：

| ID | 派生需求 | 产生处 | 验收出口 |
|----|----------|--------|----------|
| D-R1 | V2 覆盖保护比对的夹具基线数值以 CHECKLIST A3 快照为权威载体（7×42419 B / `2026-11-05 13:31:40`）；IMPL V2 只定义「不变」语义 | A3（Step 7 新增快照基线） | A3 实测 |
| D-R2 | 计数 0 的判定规则：`GURU_DIR` / `未在远端执行` 等在非真值载体文档计 0 属角色分工，不按「四方全覆盖」解读 | 本轮机械矩阵 | D1 措辞（「真值载体逐值命中」） |

**发现并修复（1 项，P3）**：

| ID | 发现 | 修复 |
|----|------|------|
| F-S1 | IMPL §2.7 C-1 行写「已同步 DESIGN §1.1 / §3.3 C / §3.4 / §6」四处，实际同步了**五处**（漏列 §11 计数推演行）；DESIGN §11 C-1 行同样只列四处。与 CHECKLIST D3「五处一致」判据的口径差 1 | IMPL §2.7 与 DESIGN §11 的 C-1 同步列表均补列 §11 |

**结论**：无 P1/P2 矛盾；1 项 P3 已修复；2 项派生需求已登记且各有验收出口；32 条链接全可解析；旧值 `7 skipped` 无当前预期残留。通过 Step 8 门禁，可进入 Step 9 实施。

> **门禁记录（2026-11-05）**：session `factorv3-p009-ci-env-20261105`，`step-consistency` pass（门禁命令用 ASCII 模式串，规避 P-008 §4 R7 findstr 中文陷阱）。

## 10. Step 9 红→绿记录

- **执行序**：T-0 RED（数据 + 静态）→ T-1 脚本（V1/V2/V2b/V1b/A5）→ T-2/T-3/T-4（V3/V4/V5）→ 全量回归 → 门禁 → 清理（IMPL §2.6）
- **脚本位置**：`%TEMP%\p009_red`、`p009_green`、`p009_v5_yaml.py`、`p009_a5_resolve.py`（全部未入仓，执行后删除）

| 阶段 | 命令 | 读数 |
|------|------|------|
| RED（数据） | cwd=`%TEMP%\p009_red`（空目录），pytest 两数据测试文件 | `9 failed, 18 errors in 8.01s`；18 errors 全部 `FileNotFoundError: 价格文件不存在: data\test_ashare\close.pkl` |
| RED（静态） | `Select-String -SimpleMatch` 三项 | `hardcoded_paths=5`；`importorskip_hits=0`；`fixture_step_hits=0` |
| GREEN-1a（T-1 生成） | `prepare_test_fixture.py --out-dir %TEMP%\p009_green\data\test_ashare` | `0.006s`；7×`(100,50)`；`total bytes: 296037` |
| GREEN-1b（覆盖保护） | 仓库根 `prepare_test_fixture.py`（默认路径，无 `--force`） | `GOTEXIT=2`；`UNCHANGED=True`；stderr 列出 7 个已存在文件 |
| GREEN-1c（数据测试） | cwd=`%TEMP%\p009_green`，pytest 两数据测试文件 | `27 passed in 9.05s`（black 修正后复跑 `8.53s`） |
| GREEN-1d（参数/路径） | `--n-stocks 30` / `--n-days 50`；importlib `_resolve_out_dir` | `exit_a=1` / `exit_b=1` / `low_dir_exists=False`；A5 PASS |
| GREEN-2a（路径修复） | `Select-String -SimpleMatch` + pytest distillation | `hardcoded_paths=0`；`guru_dir_hits=6`；`19 passed in 0.84s` |
| GREEN-2b（numba skip） | `Select-String -SimpleMatch` + pytest numba | `importorskip_hits=1`（L24）；`7 passed, 7 warnings in 9.18s` |
| GREEN-2c（CI YAML） | V5 PyYAML 断言 | `V5 YAML: PASS (0 项)`；steps 索引 `0-6`，`4=Prepare test fixture` |
| 回归 | `$env:MPLBACKEND='Agg'` + Python312 `-m pytest tests -q` | `509 passed, 82 warnings in 21.45s` |
| 门禁 | adapter `gate unit-tests` / `black-check` / `mypy-check` | seq 7 **pass**（`509 passed, 23.06s`）；seq 8 **fail**（`75 files would be reformatted, 5 unchanged` = 基线）；seq 9 **fail**（`Found 168 errors in 20 files` = 基线） |
| 清理 | `Remove-Item` + `Get-ChildItem -Filter p009*` | 残留 `count=0`；`git status` 仅 4 个目标文件 + 五文档 |

**变更实测（与 IMPL 预估对比）**：

| 文件 | 预估 | 实测（`git diff --numstat`） | 说明 |
|------|------|------------------------------|------|
| `.github/workflows/tests.yml` | +3 / -0 | `3 0` | 一致 |
| `tests/test_distillation_isolation.py` | +4 / -5 | `9 5` | 一致（4 行常量块 + 5 处替换；见 F-9-1） |
| `tests/test_numba_jit_performance.py` | +4 / -0 | `4 0` | 一致 |
| `scripts/prepare_test_fixture.py` | ~95 行 | **137 行** | 高于预估（F-9-2） |

**发现并修复（4 项，均 P3）**：

| ID | 发现 | 处理 |
|----|------|------|
| F-9-1 | DESIGN §3.3 B / IMPL §2.2 预估「新增 3 行」，实测新增块为 **4 行**（1 空行 + 注释 + 常量 + 1 空行）；numstat `+9/-5` = 4 + 5 处替换 | 两文档改为「新增 4 行」/「+4 / -5（实测 +9/-5）」 |
| F-9-2 | 脚本实测 **137 行**，IMPL §2.2 预估 ~95 行（因 docstring 边界说明 + argparse help + 4 个校验分支） | IMPL 新增清单标注「137 行（实测）」 |
| F-9-3 | 脚本 black 不合规 1 处：`generate_fixture(...)` 三行调用可合并为 95 字符单行 | 合并；`black --check` → `1 file would be left unchanged` exit 0；重跑 V1 `total bytes: 296037` 不变 |
| F-9-4 | CHECKLIST A2 规则文本 `max|ret|` 中的 `\|` 会被 markdown 解析为列分隔 | 改为 `max_abs_ret` |

**结论**：RED 4 条失败读数 → GREEN 6 条通过读数；全量 `509 passed` 与门禁读数达标（black/mypy 如实 fail 且与基线一致）；4 项 P3 已处理。Step 9 完成，可进入 Step 10 ADD 审计。

## 11. ADD 审计（Step 10）

- **时点**：2026-11-05，实施完成后独立执行（RULE-1）
- **审查者**：单 Agent 自查（单视角）（RULE-4）
- **取证方式**：门禁链复跑 + `git diff` 全文盲区扫描 + 读码，证据绑 §8 矩阵

### Phase 0: Spec 质量门

- [x] DESIGN/IMPL 无「合理处理 / 适当时机 / 酌情 / 视情况 / 尽量 / 按需」类不可审计措辞（`Select-String` 扫描命中 **0**）
- [x] 每个设计元素可对应到实现或验证：D1→A1-A6（脚本）、D3→A7、D4→A8、D5→A9、D6→A10；C-1→E3/B8、C-2→E3（§8）

### Phase 1: 完整性（design → code）

- [x] DESIGN §3.1 CLI 契约（6 参数 / 退出码 0-1-2 / `REPO_ROOT` 解析）→ 脚本全实现（A1/A3/A4/A5）
- [x] DESIGN §3.2 数据契约（7 pkl / `(100,50)` / 恒等列 / 收益 clip）→ 生成算法落地（A2 全读数）
- [x] DESIGN §3.3 精确变更面 → 三文件 diff 逐行吻合 + 1 个新脚本（A7/A8/A9）
- [x] DESIGN §6 九类错误场景 → 覆盖保护（A3）、参数校验（A4）、涨停 clip（A2）、远端声明（D6）均有对应验证

### Phase 2: 忠实度（双向对照）

- [x] IMPL §2.3.3 算法 ↔ `scripts/prepare_test_fixture.py` `generate_fixture` **逐字一致**（frames 顺序 / rng 调用序 / clip ±0.05 / dtype）
- [x] `tests.yml` diff 全文 = DESIGN §3.3 D 的 3 行（`- name` / `- run` / 空行），无多余键
- [x] numba 文件 diff 全文 = `import pytest` + 注释 + `importorskip` 3 行，位置契约成立（L21 `sys.path.insert` → L24）
- [x] numstat 对账：tests.yml `3 0`、distillation `9 5`、numba `4 0`、新脚本 137 行——与 §10 变更实测一致

### Phase 3: 必要性（code → design）

- [x] `tests.yml` 每行改动 ↔ D5（step 位置与无参数调用）
- [x] `GURU_DIR` 常量块 ↔ D3；5 处替换 ↔ B1 方案；`importorskip` ↔ D4/C1
- [x] 脚本 137 行每段可归属：docstring 边界（R2）/ `TARGET_FILES`（A3）/ `MIN_*`（A4）/ `existing_targets`（A3）/ `generate_fixture`（A2）/ `main` 校验链（A3/A4）
- [x] 盲区扫描：`git diff` 三文件全文 + 脚本全文读码——**0 项设计外改动**；保护路径（`core/` `filter/` `tools/` `examples/` `pyproject.toml` `.gitignore` `README.md`）diff 空输出

### Phase 4: 语义

- [x] 目标未降级：不是「脚本能跑」，而是「RED 复现 CI 红（`9 failed, 18 errors`）→ 全链 GREEN（27/19/7/509）+ 覆盖保护实证（exit 2 + UNCHANGED）+ 门禁入流」五层证据
- [x] 已知 fail 未被伪装：black-check / mypy-check 复跑如实 fail 且读数与基线一致（seq 10/11 = seq 8/9）；远端项全部 `[未在远端执行]`；断言脚本 `[未入仓-不可重放]`
- [x] Iron Law 核对：测试通过 ≠ 设计落地——以 §8 取证矩阵（10 类手段）双向映射补足；A3 用文件快照把「覆盖保护」从声明变成机械比对

## 12. 最终结论

- **P1/P2 阻断项**：0
- **P3 项**：累计 13 项（F-D1~F-D5、C-1/C-2、F-I1~F-I3、F-S1、F-9-1~F-9-4），全部已处理并留痕；其中 F-I1（P2 级路径错位）为最高级别发现，其余均 P3
- **门禁链**：**7 pass**（step-research / step-review×2 / design-review / step-implement-review / step-consistency / unit-tests / probe）+ 2 expected-fail（black-check 基线 75、mypy-check 基线 168，复跑 seq 10/11 无漂移）；`replay: 11 rows OK`
- **验收组**：A1-A10 / B1-B8 / C1-C4 / D1-D6 / E1-E5 / F1-F6 共 **39 项，39 项 ✅**（E3/D6/E4 等含 `[未在远端执行]` 限定的项均按限定口径达成）；静态读码 E3 绑 hash 待提交后补
- **U-007（CI 三版本全绿）**：本地等价证据齐备（夹具生成 + 27 项 passed + 路径修复 + skip 语义）；**远端未达成**，待 push 后观测，预期每版 `502 passed, 1 skipped`（C-1 推演）
- **U-008（numba CI 覆盖）**：维持「暂不新增 optional job」；CI 上 numba 降级路径不再被执行，已登记为该判据的一部分
- **U-001（远端判据部分）**：本地 Agg `509 passed` 保持；远端全绿依赖本批
- **状态**：实施完成，待提交；提交后需 ① 补绑 E3 hash ② push 触发远端 CI ③ 按 C-1 推演核对 `502 passed, 1 skipped` 后判定 U-007/U-001
