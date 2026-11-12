# DESIGN：P-024 CI 门禁对齐（mypy 假门禁 + README uv extras）

> **批次**: P-024 · **T1**
> **上游**: [RESEARCH_p024_ci_gate_alignment.md](RESEARCH_p024_ci_gate_alignment.md)（P1-P13 / E1-E5 / M-A 采用）
> **下游**: [IMPL_p024_ci_gate_alignment.md](IMPL_p024_ci_gate_alignment.md) → [CHECKLIST_p024_ci_gate_alignment.md](CHECKLIST_p024_ci_gate_alignment.md)
> **代码证据时点**: HEAD `6ed74d0`
> **状态**: Step 3 设计完稿

---

## 1. 决策总览

| ID | 决策 | 依据 |
|----|------|------|
| **D1** | CI mypy 步骤改为 **`python -m mypy --explicit-package-bases --check-untyped-defs core`**，删除 `\|\| true` | RESEARCH §4 M-A；P1/P2/P4/P5/P6 |
| **D2** | 本地门禁 `mypy-check` 同步加 `--check-untyped-defs`，形成与 CI **逐字同形**的命令（仅解释器前缀不同） | P3/P6；U-006 判据 |
| **D3** | README `### uv` 段 `uv sync` → `uv sync --all-extras` | P8/P9；ARCHITECTURE L332 |
| **D4** | 新增**门禁漂移守卫**测试 1 文件 3 断言（CI 命令形状 / `\|\| true` 缺席 / README extras） | 防 D1-D3 被静默改回；规则 3 fail-closed |
| **D5** | 台账补登：§1.4 新增 U-P023-1~4 与 U-P024-1~3 七行；§2 U-006 行补注 + 关闭注；§3.28 执行记录；CHANGELOG | P11；未决项单来源纪律 |
| **D6** | **不改** `pyproject.toml`（`mypy>=1.5.0` 维持无上限） | RESEARCH §6 U-P024-1（出界） |
| **D7** | **不扩** mypy 检查面（仍为 `core`，不加 `cli.py`/`agents`/`web`/`scripts`） | RESEARCH §6 U-P024-3（出界） |

---

## 2. 调研结论 → 设计映射

| 调研事实 | 设计落点 |
|----------|----------|
| P1/P2 `\|\| true` 自初版存在、恒吞退出码 | D1 删除；D4 断言其不得回归 |
| P4 CI 参数在本地 exit 2（目录名含点号） | D1/D2 两侧统一带 `--explicit-package-bases` |
| P5 `--ignore-missing-imports` 与 `[tool.mypy]` 重复 | D1 删除该旗标（配置已全局开启，行为不变） |
| P5 `--no-error-summary` 仅影响输出 | D1 删除，保留 `Success: no issues found in 36 source files` 作为可读证据 |
| P6 `--check-untyped-defs` 当前 0 残差 | D1/D2 纳入；U-006 / U-P023-2 判据达成 |
| P8 README 只有 `uv sync` | D3 改 `--all-extras`（覆盖 dev + web） |
| P11 台账缺 U-P023-1~4 | D5 补登七行 + 关闭注 |
| P12 v3 无同形缺陷 | D5 中关闭 U-P023-4 |

---

## 3. 决策详述

### D1 CI mypy 步骤

**变更前**（[tests.yml](../.github/workflows/tests.yml) L45-L46）：

```yaml
      - name: Type check (mypy)
        run: mypy core/ --ignore-missing-imports --no-error-summary || true
```

**变更后**：

```yaml
      - name: Type check (mypy)
        run: python -m mypy --explicit-package-bases --check-untyped-defs core
```

**理由逐条**：
1. **去 `|| true`**：E5（PEP 20「不得静默」）+ P13 实证（同一失败命令由 `exit=2` 变 `exit=0`）。workflow 中无任何注释声明这是有意豁免，属**隐式**静默。
2. **`mypy` → `python -m mypy`**：与本地 adapter（`{_PY312} -m mypy ...`）同形；避免 PATH 上的其他 `mypy` 抢占（本仓历史教训：PATH `python` 指向 Anaconda，见 U-005）。
3. **加 `--explicit-package-bases`**：P4 证明本地缺它直接 exit 2；CI 当前目录名 `Factor_Trading` 合法故不触发，但带上后**仓库改名不再敏感**（本地目录已叫 `Factor_Trading_v3.0`）。E1 定义支持该旗标「only useful in the absence of `__init__.py`」——本仓 `core/` 有 `__init__.py`，故对模块名解析零副作用。
4. **加 `--check-untyped-defs`**：E3 定义「type checks the body of every function, regardless of whether it has type annotations」；P6 实测 0 errors → 零成本扩大检查面，同时关闭 U-006/U-P023-2。
5. **去 `--ignore-missing-imports`**：P5 + E2——该选项「may only be set in the global section」，`[tool.mypy]` 已设 `ignore_missing_imports = true`，CLI 重复不改变行为。
6. **去 `--no-error-summary`**：读数 E 证明它只抑制汇总行；保留汇总行让 CI 日志出现 `36 source files` 计数，便于复审核对检查面。

### D2 本地门禁同步

**[spec_runner_adapter.py](../scripts/spec_runner_adapter.py) L67**：

```python
"mypy-check": f"{_PY312} -m mypy --explicit-package-bases --check-untyped-defs core",
```

**为何同时改本地**：U-006 的判据原文是「收紧 `mypy-check` 命令口径（如 `--check-untyped-defs`）」；只改 CI 则本地门禁仍停在旧口径，两侧再次分叉。D1+D2 后两侧命令**除解释器前缀外逐字相同**。

**既有测试影响**：[test_spec_runner_adapter.py](../tests/test_spec_runner_adapter.py) L31-L37 只断言门禁名集合，L81-L83 只断言含 `Python312`——加旗标不破坏任何断言（已读码确认，无需改测试）。

### D3 README uv 段

**变更前**（[README.md](../README.md) L217-L221）：

```bash
uv sync
```

**变更后**：

```bash
uv sync --all-extras
```

**选 `--all-extras` 而非 `--extra web`**：Quick Start 在安装后依次要求 `python cli.py test`（需 `dev`）与 `python cli.py dashboard`（需 `web`），`--all-extras` 一步覆盖；`--extra web` 会留下缺 pytest 的环境。依据 P9 的 extras 真值 + P8 的 CLI 原文。

### D4 门禁漂移守卫

新增 `tests/test_p024_ci_gate_alignment.py`，仅 3 个断言，零生产代码：

| 断言 | 内容 | 失败含义 |
|------|------|----------|
| A | 从 `tests.yml` 取 `Type check (mypy)` 步骤的 `run` 行，规范化解释器前缀后，与 `adapter.GATES["mypy-check"]` 的**旗标序列与 target** 完全相等 | 两侧口径再次分叉 |
| B | 该 `run` 行不含 `\|\| true` 且 `workflow` 全文无 `mypy.*\|\| true` | 假门禁回归 |
| C | README 的 `### uv` 代码块含 `--all-extras` | 文档纪律回归 |

**实现约束**：不引入 PyYAML（非依赖）；用逐行定位 `- name: Type check (mypy)` 后取第一条 `run:` 行。断言失败消息须含实际命令，便于定位。

**为何值得加**：本批修的正是「两处命令静默漂移」这一**结构性**缺陷；只改现值不加守卫，下一次改动仍可无声分叉。三条断言成本 < 1 个测试文件，覆盖 D1-D3 三个决策的**回归面**。

### D5 台账

| 位置 | 动作 |
|------|------|
| §1.4 表尾 | 新增 **U-P023-1 / U-P023-2 / U-P023-3 / U-P023-4** 四行（补齐 P-023 遗漏），状态与倾向照 RESEARCH_p023 §6 原文 |
| §1.4 表尾 | 新增 **U-P024-1 / U-P024-2 / U-P024-3** 三行（本批新增，见 RESEARCH §6） |
| §1.4 表尾 | 新增 **P-024** 主行（done 后回填） |
| §2 U-006 行 | 「当前倾向」追加 P-024 注记：口径已收紧为 `--check-untyped-defs` 并双侧对齐 |
| §2 关闭注区 | 追加「已关闭（2026-11-12，P-024）：U-006 / U-P023-2 / U-P023-4」及判据 |
| §3.28 | 新增 P-024 执行记录（立项 / 批次 / 红绿读数 / 收口） |
| CHANGELOG | 新增 P-024 条目（类型：chore/ci，可见行为：CI 类型检查开始真实阻塞） |

### D6/D7 不做的两件事

- **不钉 mypy 上限**：fail-closed 优先——版本漂移导致的红是**可见**的；钉上限会冻结新检查能力，且 `python_version = "3.10"` 已使三腿目标一致（P7）。
- **不扩检查面**：`core` 之外未做基线治理，扩面会引入未知量级错误，属独立批次（U-P024-3）。

---

## 4. 实现规格

### 4.1 变更面（4 个文件）

| 文件 | 变更 | 规模 |
|------|------|------|
| [.github/workflows/tests.yml](../.github/workflows/tests.yml) | L46 一行替换 | −1/+1 |
| [scripts/spec_runner_adapter.py](../scripts/spec_runner_adapter.py) | L67 一行追加旗标 | −1/+1 |
| [README.md](../README.md) | L220 一行替换 | −1/+1 |
| `tests/test_p024_ci_gate_alignment.py` | 新增（3 断言） | +~55 |

文档面：4 份 P-024 文档 + PROGRESS + CHANGELOG。

### 4.2 测试规格（D4 三断言）

```
A. ci_mypy_flags_match_local_gate
   - 解析 tests.yml 得到 ("--explicit-package-bases", "--check-untyped-defs", "core")
   - 解析 adapter.GATES["mypy-check"] 得到同三元组
   - 相等则通过
B. ci_mypy_step_is_blocking
   - 该 run 行不含 "|| true"
   - tests.yml 全文不匹配 r"mypy[^\n]*\|\|\s*true"
C. readme_uv_uses_all_extras
   - README "### uv" 之后的第一个 ```bash 代码块含 "uv sync --all-extras"
```

### 4.3 文案约定

- CI 步骤名保持 `Type check (mypy)`（不 churn；D4 断言依赖该名称定位）。
- README 不新增解释性长句，只改命令行。
- 台账关闭注统一句式：「已关闭（2026-11-12，P-024）：<ID> —— <判据达成事实>；详见 §3.28」。

---

## 5. 不变式

| ID | 不变式 | 判据 |
|----|--------|------|
| **I1** | 两侧 mypy 命令除解释器前缀外逐字同形 | D4-A 断言通过 |
| **I2** | `core` 在门禁口径与盲区口径下均 0 errors | 两条命令各 exit 0 / 36 files |
| **I3** | workflow 内不存在 `mypy ... \|\| true` | `Grep` 0 命中 + D4-B |
| **I4** | 既有 651 项测试零回归 | `pytest -q` = **654 passed**（651+3 新断言） |
| **I5** | 依赖面零变化 | `uv lock --check` exit 0；`pyproject.toml` 零改动 |
| **I6** | 生产代码零改动 | `git diff --stat` 仅 4 文件（3 配置/文档 + 1 测试） |
| **I7** | 远端 CI 与本地同口径 | 三 job success，且 mypy step 日志含 `Success: no issues found in 36 source files` |

---

## 6. 验证契约

| # | 类型 | 步骤 | 期望 |
|---|------|------|------|
| **T-1** | **红** | 临时写 `core/_p024_probe.py`（`x: int = "s"`），运行**新 CI 命令** | exit 1，输出含 `Incompatible types in assignment` |
| **T-2** | **红（对照）** | 同命令 + `\|\| true` | 内部 `exit=0`（复现假门禁）→ 证明 T-1 的判别力来自 D1 |
| **T-3** | **绿** | 删除探针，同命令复跑 | exit 0，`Success: no issues found in 36 source files` |
| **T-4** | 绿 | `pytest -q` | **654 passed** |
| **T-5** | 绿 | `black --check .` | `180 files would be left unchanged`（179+1 新文件） |
| **T-6** | 绿 | `uv lock --check` | exit 0 |
| **T-7** | 绿（远端） | push 后 CI | 三 job success；mypy step 日志含 `36 source files` |

> **F5（先失败记录）**：T-1/T-2 为 Step 9 的**先红**读数；T-3~T-6 为**后绿**读数。RESEARCH §5 已给出 Step 1 的同型读数（C: exit 2 / D: 0 errors / G: `\|\| true` 吞码）。

---

## 7. 风险登记

| ID | 风险 | 概率 | 影响 | 处置 |
|----|------|------|------|------|
| **R1** | 三 leg 解析到不同 mypy 版本，某 leg 报新错 → CI 红 | 中 | 中（可见红灯，非静默） | 若发生：登记 U-P024-1 升级并在该 leg 观察；不改代码掩盖 |
| **R2** | `--check-untyped-defs` 在旧版 mypy（3.10 leg）行为差异 | 低 | 中 | 同 R1；先看 CI 实际读数再定 |
| **R3** | T-1 注入的探针文件残留进提交 | 低 | 高 | T-1 后立即删除 + `git status --short` 空输出校验（Step 9 硬门） |
| **R4** | README 改 `--all-extras` 与锁真值不符 | 低 | 低 | I5：`uv lock --check` exit 0 |
| **R5** | D4 断言依赖 `Type check (mypy)` 步骤名，未来改名即失效 | 低 | 低 | 断言失败信息含实际读取到的步骤名，改名时立刻暴露 |

---

## 8. 回退点

单提交可回退：`git revert <P-024 提交>` 恢复 4 文件；CI 回到旧口径（含假门禁）。无数据面、无依赖面变更，回退零副作用。

---

## 9. Step 4 Review（独立 pass）

### 9.1 检查表

| # | 审查项 | 结论 |
|---|--------|------|
| R1 | 设计与 RESEARCH 的 M-A 是否一一对应 | ✅ D1-D3 = M-A 三要素；D6/D7 = 出界项 |
| R2 | 是否引入未登记的新依赖/新工具 | ✅ 无（D4 不引 PyYAML） |
| R3 | 每条决策是否可被单一命令验证 | ✅ 映射 I1-I6 / T-1~T-7 |
| R4 | 是否有「超出用户裁决」的改动 | ⚠️ D4 为新增测试（用户未点名）——判定：属「对齐」的**回归保障**，非新功能；规模 1 文件 3 断言，已在 §3 D4 给出必要性论证 |
| R5 | 既有测试是否会被破坏 | ✅ 已读 `test_spec_runner_adapter.py` L31-L37 / L81-L83，加旗标不破坏断言 |
| R6 | 门禁自身是否可能「假绿」 | ✅ D4-B 直接断言 `\|\| true` 缺席；T-1 先红证明判别力 |
| R7 | 是否覆盖「回退后不可用」风险 | ✅ §8 单提交回退 |
| R8 | 不变式是否可机械判定 | ✅ I1-I6 全部对应命令/断言 |
| R9 | 文案是否与既有文档术语一致 | ✅ 「门禁 / 口径 / 盲区」沿用 P-007/P-023 |
| R10 | 是否存在零预填 | ✅ §6 期望值为**推演值**（654 / 180），标注为期望而非实测 |

### 9.2 发现

- **F-D4-P024-1（P3）**：D4-A 若直接字符串比较两侧命令，会因解释器前缀（`"C:\...\python.exe" -m mypy ...` vs `python -m mypy ...`）必然不等。→ 已修订为**规范化后比较旗标序列 + target**（§4.2），并在 IMPL 中给出规范化函数签名 `_normalize_mypy_cmd(cmd: str) -> tuple[str, ...]`。
- **F-D4-P024-2（P3）**：D4-B 正则 `mypy[^\n]*\|\|\s*true` 需转义，且应限定在 workflow 文件内。→ 已在 §4.2 写成原始正则字符串，IMPL 中固定为 `r"mypy[^\n]*\|\|\s*true"`。

### 9.3 结论

**0 个 P1/P2，2 个 P3 已回写**。设计可进入 Step 5 IMPL。
