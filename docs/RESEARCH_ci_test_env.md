# CI 测试环境缺失（P-009） · 调研文档

> **文档编号**: RESEARCH_ci_test_env
> **阶段**: Phase 0 - 调研（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-05
> **状态**: Step 1-2 完成（含社区锚点补充 S4-S9）；待 Step 3 设计
> **上游**: 用户指令（2026-11-05「P-009 立项与调研」）；`docs/PROGRESS.md` §1.4 P-009、§2 U-007
> **下游**: [DESIGN_ci_test_env.md](DESIGN_ci_test_env.md) → [IMPL_ci_test_env.md](IMPL_ci_test_env.md) → [CHECKLIST_ci_test_env.md](CHECKLIST_ci_test_env.md)
> **档位**: T1（改动路径含 `tests/` 与 `.github/workflows/`，Layer-1）
> **证据时点**: 本仓读数 @ `17e6f26`；远端 CI run `41970636863`（`06e9e11`）、`41972980708`（`17e6f26`）

---

## 1. 问题定义

P-009 的目标是让 CI 的 `Run tests` 在 3.10 / 3.11 / 3.12 上全绿。当前失败由**三类测试环境缺失**构成，均与生产代码无关。

### 1.1 A：测试数据夹具被 git 忽略

| 断言 | 读数 | 证据 |
|------|------|------|
| `.gitignore` 忽略整个 `data/`（仅保留 `!data/.gitkeep`），且全局忽略 `*.pkl` | `data/`（L62）、`*.pkl`（L67） | `.gitignore` @ `17e6f26`（E3） |
| `data/` 下无任何被跟踪文件 | `git ls-files data` = 0 | E1 2026-11-05 |
| 本地夹具存在且为真实数据子集 | `close.pkl` 100 行 × 50 列，`2024-01-02 ~ 2024-06-04`，列样例 `000001` | E1（`pd.read_pickle`） |
| 依赖该夹具的测试 | `test_real_ashare_backtest.py` 9 项 + `test_real_ashare_strict_validation.py` 18 项 = **27 项** | E1（本地 27 passed） |
| CI 失败数 | **9 failed + 18 errors**（全部属这 27 项） | CI run `41970636863` / `41972980708` 日志（E1） |
| 现有生成脚本不可用于 CI | `scripts/prepare_test_data.py` 读取 `E:\Ashare_data\market_data`（L7） | E3 @ `17e6f26` |

### 1.2 B：测试硬编码 Windows 绝对路径

| 断言 | 读数 | 证据 |
|------|------|------|
| 5 处硬编码 `F:\Coding\Factor_Trading_v3.0\gurus` | L255、L269、L280、L298、L327 | `tests/test_distillation_isolation.py` @ `17e6f26`（E3） |
| CI 失败数 | **4 failed**：`test_buffett_json_has_distillation`、`test_soros_json_has_distillation`、`test_audit_guru_json`、`test_audit_all_gurus` | CI 日志（E1） |
| 第 5 处不失败的原因 | `test_all_gurus_have_distillation` 对目录 `glob`，Linux 下路径无效 → 空迭代 → **真空通过** | E3 L280-L286 + 日志无该项失败（E1） |
| 目标文件本身已入库 | `git ls-files gurus` = 4（buffett/dalio/munger/soros） | E1 |
| 结论 | 缺的不是文件，而是**可移植路径解析** | — |

### 1.3 C：numba 为可选依赖，但测试断言其必须存在

| 断言 | 读数 | 证据 |
|------|------|------|
| 项目将 numba 定位为可选（不可用时降级） | `docs/ARCHITECTURE.md:329`；`docs/DECISIONS.md:85-87` | E3 |
| `pyproject.toml` 无 numba（含 dev extras） | `Select-String "numba"` = 0 | E1 |
| 测试直接 `import numba` 且失败时 `raise` | `tests/test_numba_jit_performance.py:39-49` | E3 @ `17e6f26` |
| CI 失败数 | **1 failed**（`test_numba_available`） | CI 日志（E1） |
| 本地可用 | numba `0.65.1`、numpy `2.4.6`、Python `3.12.10` | E1 |

### 1.4 影响范围

| 范围 | 内容 |
|------|------|
| `tests/` | 3 个文件：路径相对化（5 处）、numba 可选处理、数据测试保留不 skip |
| `scripts/` | 新增合成夹具生成脚本（CI 与本地可复现） |
| `.github/workflows/tests.yml` | 安装后、测试前增加夹具生成 step |
| 生产代码 | **零改动**（`core/` 不动） |
| `docs/` | 本批四文档 + `PROGRESS.md` |

## 2. 来源调研

### 2.1 外部来源（T1）

| ID | 来源 | 版本 / 日期 | 关键事实 | 可解析 ID |
|----|------|-------------|----------|-----------|
| S1 | pytest 官方文档《How to use skip and xfail》 | 访问 2026-11-05 | `pytest.importorskip("mod")` 可在模块级/测试内/`setup` 中使用；不可导入时该测试记为 skip；支持 `minversion` | https://docs.pytest.org/en/stable/how-to/skipping.html |
| S2 | Numba 官方文档《Installation · Version support》 | 访问 2026-11-05 | `0.65.1`（2026-04-23）支持 Python `3.10.x <= version < 3.15`、NumPy `1.22–<1.27` 或 `2.0–<2.5`、llvmlite 0.47.x | https://numba.readthedocs.io/en/stable/user/installing.html |
| S3 | Python 官方文档 `pathlib` | 访问 2026-11-05 | `Path.resolve()` 解析符号链接并消除 `".."`；官方建议「向上遍历任意路径前先 `resolve()`」 | https://docs.python.org/3/library/pathlib.html |

### 2.1B 外部社区案例锚点（T2/T3/T4，2026-11-05 补充）

> **用法约束**（`SPEC_STANDARD.md` §11.2）：T2 作「事实状态」锚点；T3 只用于发现反例与工程陷阱，不得作为唯一最佳实践依据（最佳实践由 S1-S4 承担）；T4 只能作线索，数字与结论已回溯 T1/T2。检索通道：stackexchange API 配额异常（`quota_remaining: -1`）→ 按降级链切换 WebSearch。

| ID | 来源 | 等级 | 版本 / 日期 | 关键事实 | 适用性（外部 vs 本仓差异） |
|----|------|------|-------------|----------|----------------------------|
| S4 | git 官方文档 `gitignore`（last updated 2.55.0） | T1 | 访问 2026-11-05 | ①「Files already tracked by Git are not affected」；②「**It is not possible to re-include a file if a parent directory of that file is excluded**. Git doesn't list excluded directories for performance reasons」 | 解释 A 类机制：本地 pkl 未跟踪 → gitignore 生效 → CI fresh clone 无文件。**新陷阱**：本仓 `data/`（目录排除）+ `!data/.gitkeep` 的负模式组合，按 ② 语义 **re-include 无效**（除非改 `data/*` + `!data/.gitkeep`）；`data/.gitkeep` 实际不存在（E1 `Get-ChildItem data -Force`）→ 该规则为死规则。设计不得走 gitignore 负模式放行夹具（→ §4 R9） |
| S5 | numba Discourse《ImportError installing via PIP》 | T2 | 2022-02；访问 2026-11-05 | 维护者（esc）答复：「This usually means that our wheels were compiled against the wrong version of Numpy」，回溯上游 issue [numba#7747](https://github.com/numba/numba/issues/7747)（`numba==0.55.0` + `numpy==1.19.5` 完整复现 ImportError） | 支撑 C1 裁决：C2（CI 加装 numba）需精确版本约束且存在 wheel/NumPy API 不匹配的历史案例；印证「可选依赖宜 `importorskip`」 |
| S6 | numba Discourse《Pip install: asks for LLVMConfig.cmake》 | T2 | 2025-12；访问 2026-11-05 | llvmlite 版本不匹配 workaround（先装 `llvmlite==0.46.0b1`）；社区指出「package should do version check of Python and flag the mismatch」 | 佐证 numba/llvmlite/Python 三方版本耦合是**持续性**问题（2022→2025）；若未来采纳 C2 需复核 S2 版本表。仅作陷阱线索 |
| S7 | buglyst / adhdecode / nieva.team / cmt.de 等 CI 排障指南聚合 | T4 | 访问 2026-11-05 | 「Check if any test relies on a file that is `.gitignore`d. CI gets a fresh clone — it will not have those files」——本地绿/CI 红的高频归纳 | 线索已回溯 T1：S4（gitignore 语义）+ 本仓 `git ls-files data`=0 机械证实；不作独立依据 |
| S8 | nieva.team / dev.to / py4u 等测试可移植性文章 | T4 | 访问 2026-11-05 | 硬编码绝对路径「在作者机器上通过」（该目录在作者机器存在）；解法归纳为「用 pathlib 动态计算路径，跨 IDE/环境一致」 | 线索已回溯 T1：S3（`resolve()` 官方建议）；对应本仓 B 类 4 failed 的同型反例 |
| S9 | Python Discourse《FileNotFoundError: [Errno 2] No such file or directory》 | T3 | 访问 2026-11-05 | 相对路径相对**当前工作目录**解析；Windows 下 `r"\Dummy"` 相对当前盘符——cwd 混淆是高频陷阱 | 支撑 B1 拒绝 B3（cwd 相对路径）：`Path("gurus")` 与 cwd 耦合，社区有同型混淆案例；与 S3（仓库锚定路径）形成对照 |

**社区锚点小结**：A 类陷阱（gitignore/fresh clone）由 S4 的 T1 语义 + S7 的 T4 高频归纳共同支撑；B 类由 S3 T1 + S8 T4 线索 + S9 T3 对照支撑；C 类由 S2 T1 版本表 + S5/S6 T2 维护者答复支撑。无单源结论；T4 均已回溯。

### 2.2 本仓事实

| ID | 断言 | 证据 |
|----|------|------|
| P1 | `.gitignore` 忽略 `data/`（L62，`!data/.gitkeep` L63）与 `*.pkl`（L67）；`data/` 零跟踪 | E3 @ `17e6f26` + E1 `git ls-files data` = 0 |
| P2 | 本地夹具 100×50、`2024-01-02 ~ 2024-06-04`、7 个 pkl 合计约 297 KB、`adj` 全 1.0、`industry` 全 1 | E1（读回 DataFrame） |
| P3 | `test_03_adj_factor_identity` 要求 **adj 全为 1.0**（容差 1e-6） | E3 L102-L111 @ `17e6f26` |
| P4 | `examples/demo.py::generate_synthetic_data` 产生**变动的复权因子**（除权事件后归一，L69-L78）→ 直接复用会违反 P3 | E3 @ `17e6f26` |
| P5 | 该生成器日期起点固定 `2022-01-04`（L42），500 个工作日覆盖不到测试区间 `2024-01-02 ~ 2024-06-04` | E3 |
| P6 | `scripts/prepare_test_data.py` 依赖 `E:\Ashare_data\market_data`（本机存在，CI 不存在） | E3 L7；E1 `Test-Path` = True |
| P7 | `gurus/*.json` 4 个文件已入库 | E1 |
| P8 | `tests/test_distillation_isolation.py` 5 处绝对路径 | E3 `17e6f26` |
| P9 | numba 定位为可选、可降级 | E3 `ARCHITECTURE.md:329`、`DECISIONS.md:85-87` |
| P10 | `pyproject.toml` 无 numba；dev extras 未含 | E1 `Select-String` = 0；E3 L61-L66 |
| P11 | 本地 numba 0.65.1 / numpy 2.4.6 | E1 |
| P12 | CI 两次运行（`06e9e11`、`17e6f26`）均 failure；计数 `14 failed, 477 passed, 18 errors`（3.10 与 3.11 读数一致） | E1 `gh run view --log-failed` |
| P13 | **可行性探测**：50 股 × 100 日合成数据（`adj=1`、`industry=1`、`suspend=0`、seed 42、起点 `2024-01-02`）→ 27 项真实数据测试 **全通过**（`27 passed in 9.08s`） | E1 2026-11-05（已执行）`[未入仓-不可重放]`——探测脚本未入仓，实施后由正式 `scripts/prepare_test_fixture.py` 重放并升级证据 |
| P14 | 探测过程中本地夹具被临时脚本覆盖；已用 `scripts/prepare_test_data.py` 从 `E:` 重建（100×50、同日期区间、列样例 `000001`），全量回归 `509 passed in 32.97s` | E1 2026-11-05（事故与恢复记录，见 §4 R8） |

## 3. 方案对比

### 3.1 Type-1 / Type-2 判定

| 类别 | 判据 | 本轮判定 |
|------|------|----------|
| Type-2（可逆） | 有回退点 / 无常驻副作用 | **✅**：git revert 即回退；不改公开 API、真值源或依赖契约 |
| Type-1（不可逆） | 无回退点 / 变更真值源或契约 | ☐ |

> 按 `docs/SPEC_STANDARD.md` §11.8.1，Type-2 不启用 7 维矩阵；以下记录候选、拒绝理由与代价。

### 3.2 候选与裁决

**A. 数据夹具**

| 候选 | 描述 | 优点 | 缺点 / 代价 | 裁决 |
|------|------|------|-------------|------|
| **A1 新增合成夹具生成脚本 + CI step** | `scripts/prepare_test_fixture.py` 生成 7 个 pkl（50×100，`adj=1`、`industry=1`、`suspend=0`，seed 固定，起点 2024-01-02）；CI 在安装后执行 | 无二进制入库；可复现；不依赖 `E:`；P13 已实测 27 项全过 | 生成逻辑与 `demo.py` 部分重复（边界明确：仅测试最小字段） | **采纳** |
| A2 强制提交 7 个 pkl | `git add -f data/test_ashare/*.pkl`（约 297 KB） | 零生成逻辑；与本地完全一致 | 二进制入库；破坏 `data/` 运行时生成约定；需 `.gitignore` 例外规则；更新成本高 | 拒绝 |
| A3 缺文件时 skip | `pytest.mark.skipif(not path.exists())` | 改动最小 | 27 项真实数据测试在 CI 全部失去覆盖；RULE-3 要求 Owner/Deadline 等四要素，维护负担更大 | 拒绝 |
| A4 CI 下载真实数据 | 从外部数据源拉取 | 数据真实 | 无凭证/网络/来源不可控；CI 不可重复 | 拒绝 |

**B. 路径解析**

| 候选 | 描述 | 优点 | 缺点 / 代价 | 裁决 |
|------|------|------|-------------|------|
| **B1 仓库相对路径** | `Path(__file__).resolve().parents[1] / "gurus"`（5 处替换） | 跨平台；与 cwd 无关；S3 官方推荐的 `resolve()` 用法 | 需 5 处定点修改 | **采纳** |
| B2 环境变量 `GURU_DIR` | 由 CI/本地注入 | 可配置 | 新增配置面；默认值仍需回退；测试复杂度上升 | 拒绝 |
| B3 cwd 相对路径 `Path("gurus")` | 依赖 pytest 从仓库根运行 | 改动最小 | 从其他目录调用即失效；隐式耦合 cwd | 拒绝 |

**C. numba 可选依赖**

| 候选 | 描述 | 优点 | 缺点 / 代价 | 裁决 |
|------|------|------|-------------|------|
| **C1 模块级 `pytest.importorskip("numba")`** | 文件顶部跳过缺失 numba | 与「可选依赖可降级」定位一致（P9）；S1 官方支持；本地有 numba 时照常执行 | CI 失去 JIT 路径覆盖（记为 U-008） | **采纳** |
| C2 加入 dev extras `numba>=0.65.1` | CI 安装 numba | CI 覆盖 JIT | 引入 llvmlite/LLVM 重量依赖；需维护 NumPy 上限（S2：`<2.5`）；与可选依赖定位冲突 | 拒绝（可作后续可选 job） |
| C3 删除 numba 测试 | — | 立即变绿 | 丢失性能回归保护 | 拒绝 |

**被拒方案代价**：A2 = 二进制入库与约定破坏；A3 = 覆盖缺失 + RULE-3 维护负担；A4 = 不可复现；B2/B3 = 配置面或 cwd 耦合；C2 = 依赖重量与版本约束；C3 = 保护缺失。

## 4. 风险识别

| 风险 | 触发条件 | 缓解策略 |
|------|----------|----------|
| R1 合成夹具与真实分布不同 | 后续新增依赖真实市场特征的断言 | 生成器仅承诺满足现行 27 项校验（P13 已实测）；新增断言须同步更新生成器并在批次内验证 |
| R2 与 `examples/demo.py` 逻辑重复 | 两处生成器漂移 | 新脚本只生成测试最小字段（7 个 pkl），文件头注明与 `demo.py` 的边界；不修改 demo 默认行为 |
| R3 日期窗口硬编码 | 测试配置改日期 | 生成脚本参数与测试配置注释互指；改动时两处同步 |
| R4 CI 无 JIT 覆盖 | numba 缺失 | 登记 U-008（是否新增 optional job）；本地保留 numba 执行 |
| R5 依赖版本漂移 | 若改走 C2 | 本轮不采用 C2；若未来采纳，需按 S2 约束 NumPy |
| R6 修完后仍有其他 CI 失败 | 远端环境差异 | 修复后重跑远端；任何新失败单独登记，不并入 P-009 |
| R7 本地夹具依赖 `E:` 源 | 换机/CI | 新生成脚本不依赖外部源；`prepare_test_data.py` 仍保留为真实数据重建路径 |
| R8 夹具被误覆盖 | 本地脚本直接写 `data/test_ashare` | **本次探测已发生**：P14 已恢复；实施时先备份（`Copy-Item` 到 `%TEMP%`）再生成，或先写入临时目录再替换 |
| R9 gitignore 负模式 re-include 陷阱 | 若设计改走「`!data/test_ashare/**` 放行夹具」路线 | S4（T1）：父目录被排除时 re-include 无效；本仓 `git check-ignore -v data/.gitkeep` 实测 `!data/.gitkeep` **未生效**（被 L62 `data/` 命中，E1）。设计若需放行夹具必须改 `data/*` + 负模式结构；本批走 A1（CI 生成），不动 gitignore |

## 5. 调研结论

1. **采纳 A1 + B1 + C1**：CI 生成合成夹具；测试路径仓库相对化；numba 缺失时 `importorskip`。
2. **验收判据**：CI 三版本 `Run tests` 全绿（numba 文件允许 skip）；本地全量保持 `509 passed`；27 项真实数据测试在 CI **不得 skip**。
3. **关键假设**：
   - A1′：合成夹具满足现行严格校验（P13，E1 实测 27 passed）；
   - A2′：CI runner 可执行生成脚本（纯 numpy/pandas，无外部依赖）；
   - A3′：numba 保持可选依赖定位（P9），不以 CI 加装依赖换取覆盖。
4. **未决项**：U-008 —— numba JIT 路径是否单开 optional CI job（判据：CI 出现 numba 相关回归而无法拦截；当前倾向：暂不新增）。
5. **下一步**：Step 2 Review（来源可解析性、P13 可重放性、事故记录完整性），通过后进入 Step 3 设计。

---

## 6. 来源验证表（Step 2 Review）

| 引用 | ID / 路径 | 验证方式 | 状态 |
|------|-----------|----------|------|
| S1 | pytest skipping（`importorskip`） | WebFetch 读回：「skip tests on a missing import … at module level, within a test, or test setup function」原文命中 | 已验证（T1） |
| S2 | Numba Installation · Version support | WebFetch 读回版本表：`0.65.1 \| 2026-04-23 \| 3.10.x <= v < 3.15 \| 1.22–<1.27 ; 2.0–<2.5 \| 0.47.x` 与 §2.1 记录逐字一致 | 已验证（T1） |
| S3 | Python `pathlib` | WebFetch 读回：`resolve()` 解析符号链接/消除 `..`，官方建议向上遍历前先 `resolve()` | 已验证（T1） |
| S4 | git `gitignore`（2.55.0） | WebFetch 读回：「Files already tracked … are not affected」+「not possible to re-include … if a parent directory … excluded」原文命中；本仓 `git check-ignore -v data/.gitkeep` E1 证实负模式未生效 | 已验证（T1） |
| S5 | numba Discourse t/1203 | WebFetch 读回：维护者 esc 答复原文 + 上游 numba#7747 链接与复现细节 | 已验证（T2） |
| S6 | numba Discourse t/3094 | WebSearch 命中（维护者/社区答复，llvmlite workaround）；仅作陷阱线索 | 已验证（T2，单源标注 [单源-待二核] 用于任何结论） |
| S7 | CI 排障聚合（buglyst 等 4 站） | WebSearch 命中；T4 线索，已回溯 S4 T1 | 已验证（T4→T1 回溯） |
| S8 | 测试可移植性文章（nieva 等 3 站） | WebSearch 命中；T4 线索，已回溯 S3 T1 | 已验证（T4→T1 回溯） |
| S9 | Python Discourse t/3549 | WebSearch 命中（T3）；用于 cwd 陷阱对照，不作为最佳实践依据 | 已验证（T3） |
| P1-P12 | 本仓/本机/CI | E1/E3 重跑（见 §6.1 复核结果） | 已验证 |
| P13 | 合成夹具探测 | E1 已执行；`[未入仓-不可重放]`，实施后正式重放 | 已执行（降级注记） |
| P14 | 夹具事故与恢复 | E1（`509 passed in 32.97s`） | 已验证 |

**Review 发现与修正（Step 2）**

1. 初稿将 `*.pkl` 的 `.gitignore` 行号写为 L64（`data/` L62 正确）；实测 `Select-String` 为 **L67**（L63 = `!data/.gitkeep`）。已修正 §1.1 与 P1。
2. P13 证据等级标 E1（定义为「可重放命令」）但注明「临时脚本，未入仓」——自相矛盾。已改为「E1（已执行）`[未入仓-不可重放]`」，与 P-008 C4 处理先例一致；实施后由正式脚本重放升级。

**结论**：4 个外部来源 T1（S1-S4）均已读回命中；T2 锚点 2 个（S5/S6，S6 标注 `[单源-待二核]`）；T3/T4 仅作反例线索且已回溯 T1/T2；14 条本仓事实重跑核对（1 处行号修正、1 处证据等级修正）；无虚构引用；通过 Step 2 闸门。

### 6.1 独立复核 pass（2026-11-05）

- **执行时点**: 正文完稿后单独执行；未与正文同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座
- **审查方式**: 重跑 E1/E3 命令 + 读回文件 + 行号核对（`Select-String -LineNumber` / `Grep -n`）

**发现 2 项（均已修复）**：

| ID | 发现 | 修复 |
|----|------|------|
| F-R1 | §1.1 与 P1 写 `*.pkl` 在 `.gitignore` L64；实测 **L67**（L62=`data/`、L63=`!data/.gitkeep`） | 两处行号改为 L67 |
| F-R2 | P13 标 E1（要求可重放）但探测脚本未入仓已删除，等级声明自相矛盾 | 改为「E1（已执行）`[未入仓-不可重放]`」+ 实施后正式重放承诺 |

**复核结果**：

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| HEAD 绑定 | `git rev-parse --short HEAD` | `17e6f26`（与 E3 引用一致） |
| `.gitignore` 行号 | `Select-String "data\|pkl" -LineNumber` | L53 注释 / L62 `data/` / L63 `!data/.gitkeep` / L67 `*.pkl` |
| `data/` 零跟踪 | `git ls-files data` | 0 |
| `gurus` 跟踪数 | `git ls-files gurus` | 4 |
| 硬编码路径 5 处 | `Grep "F:\\Coding\\Factor_Trading_v3\.0\\gurus"` | L255 / L269 / L280 / L298 / L327 全部命中 |
| numba 在 pyproject | `Select-String "numba"` | 0 |
| numba 可选定位行号 | `Select-String` ARCHITECTURE / DECISIONS | L329 / L85、L87 命中 |
| demo.py 引用行号 | `Select-String` | L42（2022-01-04）/ L69、L78（adj 生成与归一）命中 |
| prepare_test_data.py L7 | `Select-String "E:\\Ashare_data"` | L7 命中 |
| CI 计数一致性 | `gh run view 41970636863 / 41972980708 --log-failed` | 两 run 均为 `14 failed, 477 passed, 18 errors`（3.10 / 3.11） |
| 本地夹具恢复 | `pd.read_pickle` + 全量回归 | `(100, 50) 2024-01-02 ~ 2024-06-04`，列 `000001`；`509 passed in 32.97s` |

**结论**：无 P1/P2；2 项 P3 已修复；Step 2 复核通过，可进入 Step 3 设计。

**社区锚点补充复核（2026-11-05）**

> §2.1B（S4-S9）正文写入后单独执行的复核 pass（RULE-1 分离）；审查方式：重跑 E1 命令 + 读回 §2.1B/§4 R9/§6 表核对锚点一致性。

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| HEAD 绑定 | `git rev-parse --short HEAD` | `17e6f26`（与 §2.1B E3 引用一致） |
| S4 负模式陷阱 | `git check-ignore -v data/.gitkeep` | `.gitignore:62:data/` → `data/.gitkeep`——`!data/.gitkeep` **未生效**，被 L62 `data/` 命中（R9 的 E1 证实） |
| S4 死规则 | `Test-Path data/.gitkeep` | `False`（S4 行「`data/.gitkeep` 实际不存在」证实） |
| `data/` 零跟踪 | `git ls-files data` | 0 |
| `.gitignore` 行号 | `Select-String "data\|pkl" -LineNumber` | L53 / L62 `data/` / L63 `!data/.gitkeep` / L67 `*.pkl`（R9「被 L62 命中」成立） |

**发现 2 项（均已修复）**：

| ID | 发现 | 修复 |
|----|------|------|
| F-S1 | 头部状态行仍为「Step 2 Review 待执行」，与 §6.1 复核记录矛盾 | 更新为「Step 1-2 完成（含社区锚点补充 S4-S9）」 |
| F-S2 | §6 结论行「3 个外部来源 T1」未随 S4（T1）补充同步 | 更正为「4 个外部来源 T1（S1-S4）」并补 T2/T3/T4 锚点计数 |

**结论**：S4-S9 六行锚点与 §6 验证表逐行对应；S6 保持 `[单源-待二核]`；S7/S8（T4）均标注已回溯；E1 复核 5/5 命中。补充复核通过，维持「可进入 Step 3 设计」。

> **门禁记录（2026-11-05）**: session `factorv3-p009-ci-env-20261105`，`step-review` pass（门禁命令用 ASCII 模式串，规避 P-008 §4 R7 陷阱）；社区锚点补充后重跑 `step-review` seq 3 pass（S4/R9/F-S1 锚点命中）、`replay: 3 rows OK`。
