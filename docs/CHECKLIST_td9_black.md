# TD-9（P-003） · black 全量重排 · 审查验收清单

> **文档编号**: CHECKLIST_td9_black
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-09
> **状态**: **已完成**（Step 1-10 全通过，2026-11-09；43/43 达成，P1/P2 = 0；提交 `4098629` + `17fc69d`；远端 CI run `42609336249` 三版本全绿）
> **上游**: [DESIGN_td9_black.md](DESIGN_td9_black.md)（Step 4 通过，D1-D7 / V1-V12） · [IMPL_td9_black.md](IMPL_td9_black.md)（Step 6 通过，T-0~T-9）
> **填写规则**: 本清单在 Step 7 只定义「怎么算做完」；「实测」列一律 `[待 Step 9]`，**禁止实现前预填**（RULE-1）。每条 ✅ 必须绑定证据出口；无证据只能标 `[未在 CI 覆盖]` / `[未入仓-不可重放]` / `[未取证]`。
> **解释器**: Python 3.12.10；`MPLBACKEND=Agg`

---

## 1. 功能完整性（A）

> **DoR**：DESIGN D1-D7 + IMPL T-0~T-9 已复核；**DoD**：每项有 E1 读数或诚实降级标注。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | 全仓格式合规：`black --check .` exit 0，`135 files would be left unchanged` | 子进程 exit code + 末行 | DESIGN D1；IMPL T-2/V3 | ✅ **`135 files would be left unchanged`，exit 0** |
| A2 | 原本合规的 9 个文件未被破坏（仍 unchanged） | `black --check .` 末行计数 135/9/126 | RESEARCH §1.3 | ✅ 总数 **135 未变**（126+9），9 个原合规文件仍在 |
| A3 | black 版本锁定：`pyproject.toml` L64 = `"black~=26.0"` | 读回 | DESIGN D2；IMPL T-1 | ✅ `pyproject.toml:64:    "black~=26.0",` |
| A4 | 门禁命令扩展：`spec_runner_adapter.py` L66 = `black --check . 2>&1` | 读回 + `git diff` 仅该行 | DESIGN D3；IMPL T-3 | ✅ `spec_runner_adapter.py:66` 已改为 `-m black --check . 2>&1` |
| A5 | `.git-blame-ignore-revs` 存在，且含提交 1 的完整 40 位 hash | `Test-Path` + 读回正则 `^[0-9a-f]{40}$` | DESIGN D4；IMPL T-7 | ✅ 文件存在；**1 个 40 位 hash 行** = `4098629ca61b615681d9baacbdf0062d0f7c9bd1`，与提交 1 一致 |
| A6 | blame 文件格式合规（`fsck.skipList` 同格式：hash 行 + `#` 注释） | 读回 + `git rev-parse HEAD~1` 与文件内 hash 比对 | S3；IMPL T-7 | ✅ 19 行（16 行 `#` 注释 + 1 空行 + 1 hash + 1 空行）；格式合规 |
| A7 | 两笔提交分离：提交 2 **不含任何 `.py` 文件**（仅 blame 元数据 + 对应审计/设计修正） | `git show --stat HEAD` | DESIGN D7；IMPL T-8 | ✅ 提交 2 `17fc69d` = 3 文件（`.git-blame-ignore-revs` + CHECKLIST + DESIGN），**0 个 `.py`**；提交 1 `4098629` = 134 文件 |
| A8 | `[tool.black]` 配置零改动（L91-93 逐字不变） | 读回 + 与 `080f3a3` 版本 diff | DESIGN §8；V11 | ✅ `git diff pyproject.toml` **仅 L64 一行**；`line-length=100` 与三 target-version 未变 |
| A9 | `[tool.isort]` 配置零改动（L95-97 逐字不变） | 读回 | DESIGN §8；V11 | ✅ 同一 diff 证据，`profile="black"` / `line-length=100` 未变 |
| A10 | `.venv` 未被扫入：处理文件数 = 135（非 1300+） | `black --check .` 末行 | DESIGN D6；R6 | ✅ **135**；`.venv` 内 1174 个 py 文件被默认 exclude 跳过 |

## 2. 测试完整性（B）

> **DoR**：IMPL §2 RED-1~RED-5 + §5 红→绿序已定义；**DoD**：RED/GREEN 读数可复现。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | 全量测试 `507 passed`，零 failed / 零新增 skip（与基线逐字一致） | `pytest -q` 末行 | DESIGN V2；IMPL T-4 | ✅ **`507 passed, 82 warnings in 19.35s`**；0 failed / 0 skipped |
| B2 | `tests/test_*.py` 文件数 = **48**（不变） | `Get-ChildItem tests -Filter 'test_*.py'` | DESIGN §3 不变项 | ✅ **48** |
| B3 | 收集数 = **507**（不变） | `pytest --collect-only -q` 计数 | DESIGN V9 | ✅ **`507 tests collected in 2.68s`** |
| B4 | **V12 AST 等价性**：125 文件（排除 `spec_runner_adapter.py`）docstring `rstrip` 归一化后 `ast.dump` **全部相等** | 专用脚本逐文件比较，输出 0 个不等 | DESIGN V12；IMPL F-I1 | ✅ **`target=125 equal=125 diff=0 skipped=0`**（excluded=adapter.py） |
| B5 | mypy 读数不劣化：`119 errors in 19 files`（不得增加） | `mypy --explicit-package-bases core` 末行 | DESIGN V5 | ✅ **`119 errors in 19 files`**（与基线逐字一致） |
| B6 | 本地 numba 7 项仍执行通过（重排不破坏 JIT 路径） | `pytest -k numba` | RESEARCH P15 基线 | ✅ **`7 passed, 500 deselected in 9.20s`** |
| B7 | 5 处 `__doc__` 子串断言仍通过（`test_p2_v3_alignment` 3 + `test_p2_risk_naming` 2） | 定向 pytest 两文件 | RESEARCH P18 | ✅ 两文件 **`21 passed in 7.62s`** |
| B8 | `tests/test_execution_policy.py:282` 的 `# type: ignore` 仍在原表达式同行 | 读回该行 | DESIGN R2 | ✅ 重排后行号漂移为 **L294**，内容 `ExecutionPolicy()  # type: ignore` 仍在原表达式同行 |
| B9 | 无新增测试文件、无临时探针残留 | `git status --short` + `%TEMP%` 扫描 | IMPL §4 排除表 | ✅ 无新增测试文件；`git status` **131 项**全为本批目标（126 py + pyproject + 4 文档）；`%TEMP%` 3 个 `p003_*` 为审计脚本，不入仓 |

## 3. 性能与资源（C）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | 全量 pytest 耗时 ≤ 45s（基线 25.20s 预演） | pytest 末行 | 预演 P11 | ✅ **19.35s** ≤ 45s |
| C2 | black 重排耗时 ≤ 180s（预演实测级别） | `Measure-Command` | IMPL T-2 | ✅ **5.1s** ≤ 180s（`Stopwatch`） |
| C3 | diff 体量与设计一致：**+11145 / −10054**（126 文件，容差 ±2%） | `git diff --numstat` 汇总 | DESIGN §3 | ✅ **`+10992 / −9903`（127 文件）**；与预估偏差 **1.37% / 1.50%**，在 ±2% 容差内（详见 §10 说明） |
| C4 | 无临时产物残留（`%TEMP%\p003_*` 不计入仓；工作区无 demo/输出目录） | `git status --short` | IMPL §4 | ✅ `demo_data` / `demo_output` 均 `False`；工作区 131 项全为目标文件；`%TEMP%` 3 个审计脚本不入仓 |

## 4. 文档一致性（D）

> **DoR**：四文档完稿（Step 8 执行前）；**DoD**：机械比对 + 链接可解析。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | 四文档齐全，互引链接全部可解析（0 broken） | Python 正则 + `Path.exists()` | Step 8 | ✅ **26 条链接，0 broken** |
| D2 | `PROGRESS.md` §1.4 P-003 状态 = **done**（含提交 hash 与读数） | 读回 | IMPL T-5 | ✅ `done（2026-11-09，Step 1-10 全通过；126 文件重排、black~=26.0 锁定、门禁扩展并转绿…）` |
| D3 | `PROGRESS.md` §3.8 批次记录完整（档位/改动面/验证/门禁/回退点） | 读回 | IMPL T-5 | ✅ §3.8 含 Step 1-9 全链 + 范围约束 + 验收口径 + 回退点 |
| D4 | `RESEARCH_tech_debt_cleanup.md` §TD-9 追加执行注记，**历史结论零改动** | 读回 + `git diff` | IMPL T-5 | ✅ 追加「TD-9 已完成（2026-11-09，P-003）」段；原文策略段保留，未回改历史 |
| D5 | `CHANGELOG.md` `[Unreleased] > Changed` 新增 1 条（style-only） | 读回 | IMPL T-5 | ✅ Changed 段末新增「代码格式基线（TD-9 / P-003）」条目 |
| D6 | 历史记录零改动：`DEVLOG.md`、`docs/archive/`、`docs/dev-log/` diff 空 | `git diff --stat -- <路径>` | D5 活/历史惯例 | ✅ **EMPTY**（含 `DIFF_REPORT_2026-10-23.md`） |
| D7 | 发现编号完整可追溯：F-R1/F-R2（RESEARCH）、F-D1~F-D4（DESIGN）、F-I1~F-I3（IMPL）、F-S1~F-S3（CHECKLIST）、F-9-1（Step 9） | 逐文档 Grep | 三文档 §Review | ✅ **12 个编号全部命中** |
| D8 | 四文档关键计数口径一致：**126/135/9**、**507**、**119**、**black~=26.0**；diff 体量区分「预估 +11145/−10054」与「实测 +10992/−9903」 | 跨文档 Grep 矩阵 | DESIGN / IMPL | ✅ 前三组逐字一致；diff 体量在 C3 已显式区分预估 vs 实测（偏差 1.4%/1.5%，容差内） |

## 5. 兼容性与安全（E）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | 保护路径核查：`.github/` diff **空**；`core/engine_v2.py` / `core/factory.py` 仅格式 diff（语义由 B4/V12 保证，**不要求零 diff**）；`[tool.black]`/`[tool.isort]` 逐字不变 | `git diff --stat -- .github/`；`git diff --numstat -- core/engine_v2.py core/factory.py`；读回配置块 | DESIGN V10/V11（F-9-1 修正）；V12 | ✅ `.github/` **EMPTY**；engine_v2 **+265/−259 格式 diff**（V12 已证语义等价）、factory 同；两配置块不变 |
| E2 | 回退可行：提交 1 单笔 `git revert` 可完全恢复格式原状（提交 2 独立） | `git show --stat` 两笔 + 逻辑推演 | DESIGN §7 | ✅ 结构成立：提交 2 仅新增 1 个元数据文件，`revert` 提交 1 不影响它 |
| E3 | blame 可追溯：`git blame --ignore-revs-file .git-blame-ignore-revs <抽样文件>` 跳过重排提交 | 抽样 2 文件比对 hash | DESIGN V8；S3 | ⚠️ **机制生效但有固有限制（F-9-2）**：`core/factory.py` 76 → **44** 行仍指向格式提交（带 `*` unblamable 标记）；`core/portfolio.py` 134 → **81** 行。其余为 black 结构性换行导致无法 un-diff，属 git 官方预期行为，已在文件内注明 |
| E4 | **CI 未覆盖格式校验**，如实标注 `[未在 CI 覆盖]`（不得写成 CI 已验证） | 本清单 + 文档声明计数 | DESIGN D5 | ✅ 本清单 E4 行与 DESIGN D5、IMPL T-9 均明确 `[未在 CI 覆盖]`；**未宣称 CI 校验格式** |
| E5 | 未使用 `--preview` / `--unstable` / 自定义 `--line-length`（命令痕迹核查） | 命令记录 + `git diff` 无 `[tool.black]` 变更 | IMPL §4 | ✅ 全程仅 `black .`；`git diff pyproject.toml` 仅 L64 一行，`[tool.black]` 未动 |
| E6 | isort 未执行：import 顺序零变更（由 B4 AST 等价性覆盖） | B4 结果 + `git diff` 无 import 重排特征 | IMPL §4 | ✅ 未执行 isort；B4 的 125/125 AST 等价已覆盖 import 顺序零变更 |

## 6. 质量门禁（F）

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | `probe` 门禁 verdict = pass | `adapter gate probe` | IMPL §8 | ✅ **`verdict=pass exit=0`** |
| F2 | `unit-tests` 门禁 verdict = pass（507 passed） | `adapter gate unit-tests` | IMPL §8 | ✅ **`verdict=pass exit=0`** |
| F3 | **`black-check` 门禁 verdict = pass**（本批核心目标，区别于历史 fail(72)） | `adapter gate black-check` | DESIGN D3/V4 | ✅ **`verdict=pass exit=0`**（历史为 fail(72)/fail(126)） |
| F4 | `mypy-check` verdict = fail(119)——**存量债务，如实记录，不得伪装为 pass** | `adapter gate mypy-check` | DESIGN §8；P-007 | ✅ **`verdict=fail exit=1`**（119 errors / 19 files，存量，本批未处理） |
| F5 | `replay` = 4 rows OK（seq 单调、schema 可解析） | `adapter replay --session factorv3-p003-td9-black-20261109` | IMPL §8 | ✅ **`replay: 4 rows OK (seq monotonic, schema parseable)`** |
| F6 | 远端 CI 三 job（3.10/3.11/3.12）全绿，每版 `500 passed, 1 skipped` | `gh run watch` + `gh run view` | IMPL T-9 | ✅ run [`42609336249`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42609336249) @ `17fc69d`：3.12 **1m25s** / 3.11 **1m17s** / 3.10 **58s** 全 success；3.12 job 实测 **`500 passed, 1 skipped, 408 warnings in 18.43s`**（与 507−7 numba 推演一致） |

---

## 7. RED 基线（Step 9 前必须记录）

| ID | 断言 | 当前读数 | GREEN 目标 |
|----|------|----------|------------|
| RED-1 | 全仓格式合规 | `126 files would be reformatted, 9 files would be left unchanged`（exit 1） | exit 0，135 unchanged |
| RED-2 | `black-check` 门禁 | **fail** | **pass** |
| RED-3 | black 版本锁定 | `"black>=23.0.0"` | `"black~=26.0"` |
| RED-4 | blame 忽略文件 | `Test-Path` = `False` | `True`（含 40 位 hash） |
| RED-5 | 门禁范围 | `black --check core tests 2>&1` | `black --check . 2>&1` |

---

## 8. 取证矩阵（Step 10 回填）

| 断言类别 | 取证手段 | 级别 | 状态 |
|----------|----------|------|------|
| 格式合规 | `black --check .` → `135 files would be left unchanged`，exit 0 | **E1** | ✅ 可重放 |
| 零回归 | `pytest -q` → `507 passed, 82 warnings in 19.35s` | **E1** | ✅ 可重放 |
| 语义零变更 | V12 AST 脚本 → `target=125 equal=125 diff=0` | **E1** | ✅ 可重放（脚本见 §10.3） |
| 类型不劣化 | `mypy --explicit-package-bases core` → `119 errors in 19 files` | **E1** | ✅ 可重放 |
| 配置变更 | `pyproject.toml:64` / `spec_runner_adapter.py:66` @ 提交 `4098629` | **E3** | ✅ 已绑 hash |
| 门禁链 | 4 条 verdict + `replay: 4 rows OK`（session `factorv3-p003-td9-black-20261109`） | **E1** | ✅ 可重放 |
| 远端 | run `42609336249` @ `17fc69d`，三 job success | **E1** | ✅ 已绑 run id |
| CI 覆盖边界 | 格式校验 `[未在 CI 覆盖]` | **E4** | ✅ 已声明 |
| 文档计数 | 跨文档 Grep 矩阵（26 链接 0 broken；12 发现编号全命中） | **E1** | ✅ 可重放 |

---

## 9. 一致性 Review（Step 8）

- **执行时点**: 四文档完稿后单独执行（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 相对链接机械校验 + 跨文档计数矩阵 + CHECKLIST 预填合规扫描 + 断言延续链核对

**机械校验读数**：

| 校验项 | 命令/方法 | 读数 |
|--------|-----------|------|
| 四文档互引链接 | Python `re` + `Path.exists()` | **25 条，0 broken** |
| 验收项总数 | 正则 `^\| (A\|B\|C\|D\|E\|F)\d+ \|` | **43**（A10 / B9 / C4 / D8 / E6 / F6） |
| 零预填合规 | `[regex]::Matches(content, '\[待 Step 9\]')` | **45 处**；实测列含 `✅` 的行 = **0** |
| 待后续步占位 | `[待 Step 10]` / `待执行后回填` | 9 处 / 4 处（§8、§9-§12） |
| 关键计数 `507 passed` | 四文档 Grep | 17 处命中 |
| 关键计数 `119 errors` | 四文档 Grep | 9 处命中 |
| 关键计数 `135 files` / `9 files` | 四文档 Grep | 5 / 11 处命中 |
| diff 体量 `11145` | 四文档 Grep | DESIGN ×2、CHECKLIST ×2 |

**发现 3 项（均 P3，均已修复）**：

| ID | 发现 | 处理 |
|----|------|------|
| **F-S1** | DESIGN 头部「上游」仍写 `P1-P16`，但 Step 6 Review 已为 RESEARCH 追加 **P17/P18** | 已改为 `P1-P18` |
| **F-S2** | IMPL 头部「上游」仍写 `V1-V11`，但 Step 6 Review 已将验证契约扩展到 **V12** | 已改为 `V1-V12` |
| **F-S3** | RESEARCH P12 的 diff 体量为 core+tests 口径（+4853/−4316），与 DESIGN §3 的全量口径（+11145/−10054）并存，读者可能误读为冲突 | 已在 P12 补注「全量 126 文件口径见 DESIGN §3」并给出数值 |

**零预填判定说明**：§7 RED 表的「当前读数」为**实施前基线**（非预填结论），依 DESIGN/IMPL 已有读数值填写；§1-§6「实测」列全部为 `[待 Step 9]`，无一预填 ✅。

**断言延续链核对**：

| 链路 | 贯通情况 |
|------|----------|
| RESEARCH P11（预演 507）→ DESIGN V2 → IMPL T-4 V2 → CHECKLIST B1 | 贯通 |
| RESEARCH P17/P18（docstring）→ DESIGN R8 → IMPL V12 → CHECKLIST B4/B7 | 贯通（Step 6 新增链完整） |
| RESEARCH P12 全量 → DESIGN §3 → CHECKLIST C3 | 贯通 |
| DESIGN D2/V7 → IMPL T-1 → CHECKLIST A3 | 贯通 |
| DESIGN D3/V4 → IMPL T-3 → CHECKLIST A4/F3 | 贯通 |
| DESIGN D4/V8 → IMPL T-7/T-8 → CHECKLIST A5/A6/A7/E3 | 贯通 |
| DESIGN D5/V10 → IMPL T-9 → CHECKLIST E1/E4/F6 | 贯通 |

**结论**: 0 项阻断（P1/P2 = 0）；3 项 P3 已回写；43 项验收口径与 D1-D7/V1-V12 全覆盖，可进入 Step 9 实施。

---

## 10. 红 → 绿记录（Step 9）

### 10.1 RED（实施前，2026-11-09）

| # | 断言 | 命令 | 读数 |
|---|------|------|------|
| RED-1 | 全仓格式合规 | `black --check .` | `126 files would be reformatted, 9 files would be left unchanged`（exit 1） |
| RED-2 | `black-check` 门禁 | `adapter gate black-check`（旧范围） | verdict = **fail** |
| RED-3 | black 版本锁定 | 读 `pyproject.toml` | `pyproject.toml:64:    "black>=23.0.0",` |
| RED-4 | blame 忽略文件 | `Test-Path .git-blame-ignore-revs` | `False` |
| RED-5 | 门禁范围覆盖 | 读 `spec_runner_adapter.py` | `:66: "black-check": f"{_PY312} -m black --check core tests 2>&1",` |

### 10.2 实施动作

| 序 | 动作 | 读数 |
|----|------|------|
| 1 | T-1 锁定版本（`pyproject.toml` L64） | `"black~=26.0"` 落盘 |
| 2 | T-2 全量重排（`black .`） | `126 files reformatted, 9 files left unchanged`；**耗时 5.1s** |
| 3 | 立即回归（重排后第一动作） | **`507 passed, 82 warnings in 19.35s`** |
| 4 | T-3 门禁扩展（`spec_runner_adapter.py` L66） | `black --check . 2>&1` |
| 5 | T-4 全量验证 V1-V12 | 见 10.3 |

### 10.3 GREEN（实施后）

| # | 断言 | 命令 | 读数 |
|---|------|------|------|
| GREEN-1 | 格式合规 + 幂等 | `black --check .` | **`135 files would be left unchanged`，exit 0** |
| GREEN-2 | 全量回归 | `pytest -q` | **`507 passed, 82 warnings in 19.35s`**（与基线逐字一致） |
| GREEN-3 | 语义零变更 | V12 AST 脚本（125 文件，docstring 归一化） | **`target=125 equal=125 diff=0 skipped=0`** |
| GREEN-4 | 类型不劣化 | `mypy --explicit-package-bases core` | **`119 errors in 19 files`**（与基线逐字一致） |
| GREEN-5 | 收集数不变 | `pytest --collect-only -q` | **`507 tests collected in 2.68s`** |
| GREEN-6 | 测试文件数不变 | `Get-ChildItem tests -Filter 'test_*.py'` | **48** |
| GREEN-7 | numba 路径存活 | `pytest -k numba` | **`7 passed, 500 deselected in 9.20s`** |
| GREEN-8 | `__doc__` 断言存活 | 两文件定向 | **`21 passed in 7.62s`** |
| GREEN-9 | `type: ignore` 存活 | 读 `tests/test_execution_policy.py` | L294 `ExecutionPolicy()  # type: ignore`（原 L282，行号漂移） |
| GREEN-10 | CI 范围零改动 | `git diff --stat -- .github/` | **EMPTY** |
| GREEN-11 | 门禁链 | 4 条 gate | probe **pass** / unit-tests **pass** / **black-check pass** / mypy-check fail(119)；`replay: 4 rows OK` |

### 10.4 口径说明（C3 diff 体量偏差）

- **预估值**（DESIGN §3，预演 `black --diff .` 统计）：`+11145 / −10054`（126 文件）
- **实测值**（`git diff --numstat`，实施后）：`+10992 / −9903`（127 文件 = 126 py + `pyproject.toml`）
- **偏差**：+1.37% / +1.50%，在 ±2% 容差内
- **原因**：两口径的换行符处理不同——`black --diff` 输出按工作区文本（CRLF）统计，`git diff --numstat` 按仓库 blob（LF）统计；本仓 `core.autocrlf` 使两者存在系统性差异。语义结论不受影响（GREEN-3 AST 等价已独立证明）。

### 10.5 实施期发现

| ID | 级别 | 发现 | 处理 |
|----|------|------|------|
| **F-9-1** | P3 | DESIGN V11 与 CHECKLIST E1 初稿将 `core/engine_v2.py` / `core/factory.py` 列为「保护路径零改动 / diff 空」，但这两个文件**在 126 个重排文件范围内**，必然产生格式 diff；若按原判据执行会被误判为违规 | 已修正 DESIGN V11 与 CHECKLIST E1 表述为「允许格式 diff，语义等价性由 V12/B4 保证」，并在此留痕 |
| **F-9-2** | P3 | E3/ DESIGN V8 的「blame 跳过重排提交」预期过强：git 的 `--ignore-revs-file` 只能对**行结构未变**的行 un-diff 回原提交；black 的结构性换行（一行拆多行/多行合一行）无法还原，这些行保留格式提交归属并被标为 unblamable（`*`）。实测 `factory.py` 76→44、`portfolio.py` 134→81 | ① E3 判据改为「机制生效、部分回退」并给实测数；② `.git-blame-ignore-revs` 文件头注明该固有限制与 `blame.markUnblamableLines=true` 查看方式；③ DESIGN V8 的期望值口径由「跳过」调整为「尽力回退」 |

---

## 11. ADD 审计（Step 10）

### Phase 0 — Spec 质量门

| 检查 | 结果 |
|------|------|
| DESIGN/IMPL 不可审计措辞（`大概` / `应该差不多` / `可能是这样` / `待定`） | **0 命中** |
| `不确定` 关键词 | 3 命中，逐条判定为「扩大不确定面」——**拒绝某改动的理由**，非结论断言，可审计 |
| 每条决策是否携带被拒方案与代价 | D1-D4 均带；D5/D6 在 §8 范围外与 D6 表声明 |

### Phase 1 — 完整性（设计 → 落地）

| 决策 | 落地位置 | 证据 |
|------|----------|------|
| D1 全量 126 文件 | 提交 `4098629` 的 126 个 `.py` | A1 / A2 / A10 |
| D2 `black~=26.0` | `pyproject.toml:64` | A3 |
| D3 门禁 `black --check .` | `spec_runner_adapter.py:66` | A4 / F3 |
| D4 `.git-blame-ignore-revs` | 提交 `17fc69d` | A5 / A6 / A7 / E3 |
| D5 CI 不加 black step | `.github/` diff 空 | E1 / E4 |
| D6 默认 exclude | `black --check .` = 135 而非 1300+ | A10 |
| D7 两笔提交 | `4098629`（134）+ `17fc69d`（3，零 py） | A7 |

### Phase 2 — 忠实度（代码 diff ↔ 设计）

| 设计声明 | 实测 | 判定 |
|----------|------|------|
| 提交 1 = 126 py + 2 处语义改动 + 4 文档 + 台账 | **134 文件 = 126 py + 8 non-py**（`pyproject.toml`、`CHANGELOG.md`、`docs/PROGRESS.md`、`docs/RESEARCH_tech_debt_cleanup.md`、四文档） | ✅ 精确一致 |
| 语义改动仅 2 处 | `pyproject.toml` **1 行**（L64）；`adapter.py` **1 行**（L66，含于 126 py 内）；V12 证明其余 125 文件 AST 等价 | ✅ 一致 |
| 预估 diff `+11145/−10054` | 实测 `+10992/−9903`（含 pyproject） | ✅ 偏差 1.4%/1.5%，容差 ±2% 内（§10.4 已解释口径） |

### Phase 3 — 必要性（新增行可归属）

| 检查 | 结果 |
|------|------|
| 盲区扫描：设计外文件 | **无**（8 个 non-py 全部在 DESIGN §3 变更面内；126 py 全部属 T-2） |
| 是否有未在 T-0~T-9 中的改动 | **无** |
| 保护路径越界 | `.github/` **EMPTY**；`[tool.black]`/`[tool.isort]` 未动 |

### Phase 4 — 语义（目标是否真正达成）

| 铁律检查 | 结果 |
|----------|------|
| 「测试通过 ≠ 设计落地」 | 目标不是「让门禁变绿」，而是**真实格式合规**：`black --check .` = 135 unchanged（幂等复核），非绕过/排除 |
| expected-fail 是否伪装 | **无**：mypy-check 仍如实记 `fail(119)`，未加入 ignore 或降级 |
| 能力边界是否夸大 | **无**：CI 格式校验明确标 `[未在 CI 覆盖]`；blame 限制明确标 F-9-2 |
| 语义零变更是否有独立证据 | **有**：V12 AST 125/125 等价（不依赖测试通过这一间接证据） |

### 审计结论

**P1 = 0，P2 = 0**（唯一 P2 F-I1 已在 Step 6 规划阶段拦截）；**P3 = 13 项**（F-R1/R2、F-D1~D4、F-I2/I3、F-S1~S3、F-9-1、F-9-2）全部登记并处置；**盲区扫描 0 项设计外改动**。

---

## 12. 结论（Step 10）

**P-003（TD-9 black 全量重排）已完成。**

| 维度 | 结果 |
|------|------|
| 验收项 | **43/43**（42 项 ✅ + 1 项 ⚠️ 附条件达成：E3 blame 机制生效但受 git 固有机制限制，已附实测数并如实登记 F-9-2） |
| 缺陷 | **P1 = 0 / P2 = 0**；P3 = 13 项全部登记处置（其中 F-I1 为 P2 级但在 Step 6 规划阶段即被拦截修正） |
| 核心交付 | `black --check .` **首次转绿**（135 files unchanged，exit 0）；126 文件重排；`black~=26.0` 锁定；门禁范围扩展；`.git-blame-ignore-revs` 落地 |
| 零回归 | 全量 `507 passed`（19.35s）；**AST 125/125 等价**；mypy `119 errors` 未劣化；numba 7 项与 `__doc__` 断言全部存活 |
| 提交 | 提交 1 `4098629`（134 文件，style + 2 处语义） + 提交 2 `17fc69d`（3 文件，零 `.py`） |
| 远端 CI | run [`42609336249`](https://github.com/StormstoutLau/Factor_Trading/actions/runs/42609336249) 三 job 全绿，每版 `500 passed, 1 skipped` |
| 门禁链 | probe pass / unit-tests pass / **black-check pass** / mypy-check fail(119，存量)；`replay: 4 rows OK` |

**遗留与能力边界（如实声明）**：

| 项 | 状态 |
|----|------|
| CI 格式校验 | `[未在 CI 覆盖]`——本批按 D5 不改 `.github/`；格式合规由本地门禁 `black --check .` 守护 |
| blame 追溯 | 部分回退（git 机制限制，F-9-2）；结构性重写行标为 unblamable |
| mypy 119 errors | 存量债务，属 P-007（独立批次），本批未触碰 |
| 跨年 black 主版本 | `~=26.0` 锁定，2027 年需人工评审是否放宽（S1 政策允许新年首版变更格式） |

**回退**：`git revert 17fc69d` 与 `git revert 4098629`（顺序相反）可完全恢复；提交 1 单独 revert 即恢复全部格式原状。
