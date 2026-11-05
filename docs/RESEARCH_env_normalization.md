# 环境规范化（U-001 + U-005） · 调研文档

> **文档编号**: RESEARCH_env_normalization
> **阶段**: Phase 0 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-04
> **状态**: 已完成（Step 2 Review 通过）
> **上游**: 用户指令（2026-11-04「P0 环境规范化：U-001 + U-005；（零代码/文档 + CI 约定）」）；`docs/PROGRESS.md` §2 U-001/U-005
> **下游**: [DESIGN_env_normalization.md](DESIGN_env_normalization.md) → [IMPL_env_normalization.md](IMPL_env_normalization.md) → [CHECKLIST_env_normalization.md](CHECKLIST_env_normalization.md)
> **档位**: T1（改动路径含 `.github/workflows/`，按 `F:\Spec_Workflow\SPEC_PROCESS.md` L561 属 Layer-1）

---

## 1. 问题定义

### 1.1 U-001：默认 matplotlib 后端下测试不稳定

**现象（E1，2026-11-04 复测）**

| 场景 | 读数 | 说明 |
|------|------|------|
| 默认后端全量 `pytest tests -q` | `1 failed, 508 passed, 82 warnings in 20.92s` | 失败项 `TestRealAshareBacktest.test_09_trades_generated` |
| 同一失败项单独运行 | `1 passed in 4.19s` | 单独运行时通过 |
| 上一轮默认后端全量（同批早先） | `1 failed, 505 passed, 3 errors` | 失败/错误项在不同测试间漂移 |
| `MPLBACKEND=Agg` 全量 | `509 passed, 82 warnings in 20.02s` | 无头后端稳定通过 |

**触发链（E1 调用栈原文）**

```
tests/test_real_ashare_backtest.py:202  results = engine.run()
core/engine_v2.py:763                   report_data = generate_report(...)
core/analytics.py:346                   self.generate_monthly_returns_heatmap(...)
core/analytics.py:262                   plt.figure(figsize=(12, 8))
matplotlib/backends/_backend_tk.py:535  window = tk.Tk(className="matplotlib")
tkinter/__init__.py:2346                self.tk = _tkinter.create(...)
_tkinter.TclError: Can't find a usable tk.tcl ...
```

> 行号读数 @ `116426e`（本仓 4 个文件）；`matplotlib/backends/_backend_tk.py:535`、`tkinter/__init__.py:2346` 来自本机 site-packages（Python 3.12.10）。

**根因边界（不把“Tk 未安装”写成结论）**

- 直接 `python312 -c "import tkinter; tkinter.Tk()"` → `Tk OK`（E1）。
- `tcl\tk8.6\tk.tcl`（24,322 B）与 `tcl\tk8.6\panedwindow.tcl`（5,370 B）均存在且可读（E1 `Get-Item`）。
- 但全量 pytest 进程内，Tcl 仍报 `panedwindow.tcl: no such file or directory`（E1 日志）。
- 结论：**触发链确定**（matplotlib 自动选择 TkAgg → `tk.Tk()`），但“为何仅在该进程内失败”**尚未定位**；因此方案不得依赖“修好 Tk”这一未证实前提。

### 1.2 U-005：本地 `python` 解释器漂移

| 断言 | 读数 | 证据 |
|------|------|------|
| 默认 `python` | `C:\ProgramData\Anaconda3\python.exe`，3.13.5，缺 `cvxpy` | `Get-Command python`；pytest 收集报 `ModuleNotFoundError: No module named 'cvxpy'` |
| 基线解释器 | `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`，3.12.10 | `python312 -c "import sys; print(sys.version)"` |
| 可用版本 | `py -0p` 同时列出 3.12（默认标记）与 3.11.15 | E1 |
| CI 侧 | `.github/workflows/tests.yml` 矩阵固定 3.10/3.11/3.12 | E1 |

结论：U-005 是**本地执行口径**问题；CI 已按矩阵固定版本，不受影响。需要文档化“测试用哪个解释器”，而不是修改代码。

### 1.3 影响范围

| 范围 | 内容 |
|------|------|
| `.github/workflows/tests.yml` | 增加无头后端环境变量；测试调用改为 `python -m pytest` |
| `README.md` | 新增/补全 Testing 小节：解释器选择 + `MPLBACKEND=Agg` |
| `docs/PROGRESS.md` | P-008 立项、§3.5 执行序、完成后回写 |
| 生产代码 | **零改动**（`core/`、`scripts/`、`tests/` 不动） |

---

## 2. 来源调研

### 2.1 外部来源（T1 一手 / T3 反例）

| ID | 来源 | 版本 / 日期 | 关键事实 | 可解析 ID |
|----|------|-------------|----------|-----------|
| S1 | Matplotlib 官方文档《Backends》 | 访问 2026-11-04 | 未显式设置时按 `MacOSX → QtAgg → GTK4Agg → Gtk3Agg → TkAgg → WxAgg → Agg` 自动选择；**Agg 是非交互后端，只能写文件**；`MPLBACKEND` 可覆盖任何 matplotlibrc；**全局设置（.bashrc/.profile）被官方劝阻** | https://matplotlib.org/stable/users/explain/backends.html |
| S2 | Python 3.12 官方文档《Using Python on Windows》 | 3.12 文档，访问 2026-11-04 | 安装选项 `Include_tcltk = Install Tcl/Tk support and IDLE`（默认 1）；`Repair` 会“验证应安装文件并替换被移除或修改的文件”；`Modify` 可增删功能 | https://docs.python.org/3.12/using/windows.html （§4.1.3 选项表、§4.1.5 Modifying an install） |
| S3 | pytest 官方文档《How to invoke pytest》 | 访问 2026-11-04 | `python -m pytest` 与直接 `pytest` 几乎等价，额外把当前目录加入 `sys.path` | https://docs.pytest.org/en/stable/how-to/usage.html |
| S4 | `actions/setup-python` 官方 README | 访问 2026-11-04（v7 文档） | 建议**始终显式设置** `python-version`（或用 `python-version-file`），不要依赖 runner 默认；支持 `cache: pip` | https://github.com/actions/setup-python |
| S5 | GitHub Docs《Store information in variables》 | 访问 2026-11-04 | `env` 可定义在 workflow / `jobs.<job_id>.env` / `jobs.<job_id>.steps[*].env` 三个作用域 | https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables |
| S6 | Python 官方文档（Windows） | 访问 2026-11-04 | 推荐每个项目使用 virtual environment；多版本场景推荐 `py` 命令选择版本 | https://docs.python.org/3/using/windows.html （venv 段、`py` 段）；3.12 文档 §4.8 Python Launcher |
| S7 | Python tracker 讨论（T3 社区） | 2018-2020 | 有用户用 `TK_LIBRARY` 指向 tk.tcl 所在目录规避同类报错；仅作**工程陷阱线索**，未被本仓采纳为标准做法 | https://bugs.python.org/msg319861 |

### 2.2 本仓事实（E1）

| ID | 断言 | 证据 |
|----|------|------|
| P1 | CI 已存在，`ubuntu-latest` + 3.10/3.11/3.12 矩阵；测试命令为 `pytest tests/ --tb=short -q`；未设置 `MPLBACKEND` | `.github/workflows/tests.yml` L1-L42 @ `116426e`（E3） |
| P2 | README 有安装/使用段，但**无 Testing 小节** | `README.md` L201-L229 @ `116426e`（E3）；`Select-String "pytest"` 无命中 |
| P3 | 默认后端全量 `1 failed, 508 passed`；失败栈指向 `_backend_tk.py → tk.Tk` | `%TEMP%\pytest_default_backend_retest_20261104.log` |
| P4 | 同测试单独运行通过；直接 `tkinter.Tk()` 通过 | 命令读数（见 §1.1） |
| P5 | `tk.tcl` / `panedwindow.tcl` 在磁盘存在且非空 | `Get-Item` 读 Length |
| P6 | 默认 `python` = Anaconda 3.13.5 缺 `cvxpy`；Python312 = 3.12.10 | `Get-Command python`；`python312 -c ...` |
| P7 | `py -0p` 可见 3.12 与 3.11.15 | E1 |
| P8 | `MPLBACKEND=Agg` 下 509 passed | 日志 SHA256 `D262199F…`；T3 session `step-verify` |

---

## 3. 方案对比

### 3.1 Type-1 / Type-2 判定

| 类别 | 判据 | 本轮判定 |
|------|------|----------|
| Type-2（可逆） | 有回退点 / 无常驻副作用 | **✅**：还原 `tests.yml` 与 README 即完全回退；不改运行时、公开接口、真值源 |
| Type-1（不可逆） | 无回退点 / 变更真值源或契约 | ☐ |

> 按 `docs/SPEC_STANDARD.md` §11.8.1，Type-2 不启用 7 维矩阵；以下记录候选、拒绝理由与代价。

### 3.2 候选与裁决

| 候选 | 描述 | 优点 | 缺点 / 代价 | 裁决 |
|------|------|------|-------------|------|
| **A. CI 固定无头后端 + README 测试口径** | `tests.yml` 加 `env: MPLBACKEND: Agg`；测试改 `python -m pytest`；README 增 Testing 小节（venv/`py -3.12` + 临时 `MPLBACKEND=Agg`） | 改动最小；CI 行为可复现；不依赖修复 Tk；符合 S1“不要全局设置”的边界 | 本地默认后端仍可能失败，需按文档用 Agg | **采纳** |
| B. 仅修本机 Tk（Repair 安装） | 用 Windows 安装器 Repair 替换 Tcl/Tk 文件 | 可能根治本机 GUI | 非仓内可复现；CI/他人机器无效；且当前文件已存在，无法保证 Repair 解决 | 拒绝为唯一方案；可作为本地可选动作 |
| C. `tests/conftest.py` 强制 Agg | 在测试会话启动时 `matplotlib.use("Agg")` | 本地不需设环境变量 | 属代码改动（违反“零代码”约束）；隐藏 GUI 后端差异；改变测试语义 | 拒绝 |
| D. 全局设置 `MPLBACKEND=Agg` | 写系统环境变量/`.bashrc` | 一劳永逸 | S1 明确劝阻全局覆盖；影响所有 matplotlib 使用场景（含交互探索） | 拒绝 |
| E. 新增 `.python-version` 固定 3.12 | pyenv/uv 读取 | 自动选版本 | 与项目支持 3.10+、CI 3.10-3.12 矩阵冲突；会误导用户以为仅支持 3.12 | 拒绝 |

**被拒方案代价**：B = 不可复现且可能无效；C = 引入代码变更并改变测试语义；D = 影响交互式使用；E = 收窄支持面。

---

## 4. 风险识别

| 风险 | 触发条件 | 缓解策略 |
|------|----------|----------|
| R1 CI 通过但本地默认后端仍失败 | 开发者直接 `pytest` | README 明确本地命令；不承诺“修复 Tk” |
| R2 CI 环境变量作用域过大 | `env` 放在 workflow 顶层 | 放在 job 级（仅 test job）；S5 支持该作用域 |
| R3 CI 无法本地实测 | 无 GitHub runner / 无 `act` | Step 9 用 YAML 解析 + diff 审查；远端运行结果标 `[未在远端执行]`，不伪造 ✅ |
| R4 Tk 根因未完全定位 | 后续仍偶发 | 以 Agg 作为稳定路径；U-001 判据改为“测试在固定 Agg 下全绿”，不宣称 Tk 已修复 |
| R5 解释器文档写成“只支持 3.12” | README 措辞过窄 | 写成“项目支持 3.10+；测试基线用 3.12；Windows 可用 `py -3.12` 显式选择” |
| R6 `python -m pytest` 改变 `sys.path` | CI 依赖安装布局 | S3 说明会加入 cwd；本项目在仓库根运行，符合预期；回归验证 509 |
| R7 门禁命令含中文匹配串 | Spec_Runner `gate` 用 `findstr` 匹配 UTF-8 中文 | 实测本机 cp65001 下 `findstr /c:中文` 失配（E1，2026-11-05）；门禁命令一律用 ASCII 模式串 |

---

## 5. 调研结论

1. **采纳方案 A**：只改 CI 与文档，零生产代码。
2. **U-001 收敛口径**：以“测试固定 `MPLBACKEND=Agg`”为判据；不把“修复 Tk”作为验收前提。
3. **U-005 收敛口径**：文档写明测试解释器选择方式（venv 或 `py -3.12`），CI 保持 3.10-3.12 矩阵。
4. **关键假设**：
   - A1：GitHub Actions `ubuntu-latest` 无显示环境，Agg 可正常 `savefig`（项目报告只写文件）；
   - A2：job 级 `env` 对该 job 所有 step 生效（S5）；
   - A3：现有 CI 的 3.10/3.11/3.12 矩阵不需改动版本。
5. **下一步**：Step 3 设计（CI diff、README 段落、回退点）。

---

## 6. 来源验证表（Step 2 Review）

| 引用 | ID / 路径 | 验证方式 | 状态 |
|------|-----------|----------|------|
| S1 | Matplotlib Backends | WebFetch 读回；确认 `MPLBACKEND`、Agg 定义、全局劝阻原文 | 已验证（T1） |
| S2 | Python 3.12 Windows 文档 | WebFetch 读回 §4.1.3 选项表与 §4.1.5 Repair 原文 | 已验证（T1） |
| S3 | pytest usage | WebFetch 读回 `python -m pytest` 段 | 已验证（T1） |
| S4 | setup-python README | WebFetch 读回“始终显式设置 python-version”原文 | 已验证（T1） |
| S5 | GitHub Actions variables | WebFetch 读回 env 三作用域 | 已验证（T1） |
| S6 | Python Windows 文档（venv / py） | WebFetch 读回 | 已验证（T1） |
| S7 | Python tracker msg319861 | WebSearch 命中；仅作 T3 线索，不进入结论 | 已验证（T3） |
| P1-P8 | 本仓/本机命令 | 逐条 E1 重跑 | 已验证（E1） |

**Review 发现与修正（Step 2）**

1. **初稿曾写“Tk 安装不完整”**：与 P4/P5 矛盾（直接 `tkinter.Tk()` 成功、文件存在）。已改为“触发链确定、根因未完全定位”，并禁止把“修复 Tk”作为方案前提。
2. **初稿考虑全局 `MPLBACKEND`**：S1 明确劝阻全局设置；已改为 job 级 env + 本地按命令临时设置。
3. **初稿考虑 `.python-version`**：与 3.10+ 支持面和 CI 矩阵冲突；已列入拒绝方案 E。

**结论**：7 个外部来源可解析、8 条本仓事实有 E1 读数；无虚构版本或结论；通过 Step 2 闸门。

### 6.1 独立复核 pass（2026-11-05）

- **执行时点**: 正文与 [PROGRESS.md](PROGRESS.md) 更新完稿后单独执行；未与正文同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座
- **审查方式**: 重跑 E1 命令 + 逐条读回文件 + 行号核对（`Grep -n`）

**发现 2 项（均已修复）**：

| ID | 发现 | 修复 |
|----|------|------|
| F-R1 | §2.2 P1/P2 的行号证据未绑定 commit hash，不满足 RULE-6 对 E3 的约束 | 补 `@ 116426e`；§1.1 触发链补行号绑定说明 |
| F-R2 | [PROGRESS.md](PROGRESS.md) §1.2 写「本机 Tk 缺 `tk.tcl` / Tk 安装不完整」，与 P4/P5 矛盾（`tkinter.Tk()` 成功、`tk.tcl` 与 `panedwindow.tcl` 存在且非空） | 改为中性表述：记录 Tcl 报错原文，注明「文件实际存在，根因未完全定位」，结论句改为「TkAgg 初始化失败触发，非代码回归」 |

**复核结果**：

| 断言 | 复核方式 | 结果 |
|------|----------|------|
| tests.yml 未设 `MPLBACKEND` | `Select-String` | 空输出（断言成立） |
| README 无 Testing 小节 | `Select-String "^#+.*[Tt]esting"` | 空输出（断言成立） |
| 触发链行号 | `Grep -n`：`engine_v2.py:763`、`analytics.py:262/346/478`、`test_real_ashare_backtest.py:202` | 全部命中 |
| HEAD 绑定 | `git rev-parse --short HEAD` = `116426e` | 与 E3 绑定一致 |
| RESEARCH 存在且链接可解析 | `Test-Path docs/RESEARCH_env_normalization.md` | True |
| 外部来源（S1-S7） | 2026-11-04 已 WebFetch 读回并记录原文要点 | 无需重复抓取；本轮只核对本仓一致性 |

**结论**：无 P1/P2；2 项发现已修复；Step 2 复核通过，可进入 Step 3 设计。

> **门禁记录（2026-11-05）**: session `factorv3-p008-env-norm-20261105`，`step-review` pass（seq 2；seq 1 为首次运行 fail——`findstr /c:独立复核` 在本机 cp65001 下无法匹配 UTF-8 中文，改用 ASCII 模式 `findstr F-R1` 后通过。**工程陷阱**：Spec_Runner 门禁命令避免以中文作 findstr 匹配串，已回写 §4 R7）。
