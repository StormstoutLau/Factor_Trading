# Spec_Runner 接入 · 审查验收清单

> **文档编号**: CHECKLIST_spec_runner_integration
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-04
> **状态**: 已完成（Step 9/10 读数已回填）
> **上游**: [DESIGN_spec_runner_integration.md](DESIGN_spec_runner_integration.md) · [IMPL_spec_runner_integration.md](IMPL_spec_runner_integration.md)

---

## 1. 功能完整性（DoR：设计接口已定义；DoD：逐项有证据）

- [x] `scripts/spec_runner_adapter.py` 存在，配置区为：`RUNNER=F:\Spec_Runner\spec_runner.py`、`PREFIX=factorv3`、`CWD=None`
- [x] 配置区以外代码与官方模板 `templates/spec_runner_adapter.py` v1.0 **逐行一致**（`git diff --no-index` 仅 3 处配置差异）
- [x] `gates` 输出恰好 4 项：`probe`、`unit-tests`、`black-check`、`mypy-check`
- [x] `probe` 门禁 verdict=`pass`，exit=0
- [x] `unit-tests` 门禁 verdict=`pass`，exit=0，输出含 `509 passed`
- [x] `black-check` 门禁 verdict=`fail`，exit=1，输出含 `75 files would be reformatted, 5 files would be left unchanged`（**预期基线**）
- [x] `mypy-check` 门禁 verdict=`fail`，exit=1，输出含 `168 errors in 20 files`（**预期基线**）
- [x] 2 条 session 通过 `replay`：`probe` 1 行、`black-check` 2 行（同日重跑追加）
- [x] `status` 显示 4 个 `factorv3-*` session 的 gate verdict

## 2. 测试完整性

- [x] U1：GATES 键集合正确（6 passed）
- [x] U2：PREFIX 与 DEFAULT_CWD 正确
- [x] U3：`_build_gate_cmd` 装配正确（name/cmd/session/cwd）
- [x] U4：未知门禁 `SystemExit(2)`
- [x] U5：`dry-run` 返回 0 且不执行 `_exec`
- [x] U6：三条重命令均固定 Python312 路径
- [x] 红→绿记录：RED `6 errors`（adapter 未实现）；GREEN `6 passed in 0.04s`
- [x] 全量回归：`503 + 6` → **509 passed, 82 warnings in 20.02s**

## 3. 门禁链验收（Step 10）

| 门禁 | 命令 | 预期 verdict | 实测 verdict | 证据 |
|------|------|--------------|--------------|------|
| probe | `echo Spec_Runner OK` | pass | **pass（exit 0）** | `F:\Spec_Runner\sessions\factorv3-probe-20261104.jsonl`（1 行，SHA256 `48E5C049…`） |
| unit-tests | pytest（Agg + Python312） | pass | **pass（exit 0）** | `factorv3-unit-tests-20261104.jsonl`（`509 passed, 82 warnings in 33.84s`，SHA256 `99162437…`） |
| black-check | `black --check core tests 2>&1` | fail（基线 75） | **fail（exit 1）** | `factorv3-black-check-20261104.jsonl`（seq 2，`75 files would be reformatted, 5 unchanged`，SHA256 `7C15721F…`） |
| mypy-check | `mypy --explicit-package-bases core` | fail（基线 168） | **fail（exit 1）** | `factorv3-mypy-check-20261104.jsonl`（`168 errors in 20 files`，SHA256 `997E21A4…`） |

> 说明：`black-check` / `mypy-check` 的 fail 是**已知技术债基线**（TD-9 与 mypy 清理未完成），不是本次接入引入的回归；清单如实记录 fail，不将其改写为 ✅。

## 4. 文档一致性

- [x] RESEARCH → DESIGN → IMPL → CHECKLIST 四文档的配置值、门禁名、预期 verdict 完全一致（含 `2>&1` 修正）
- [x] 四文档互相链接可解析（`Test-Path` 全部 True）
- [x] 外部来源版本（runner 1.0.0 / 模板 v1.0 / 设计 v1.0）与原文一致
- [x] `PROGRESS.md` 新增行含档位、依据、状态
- [x] `DEVLOG.md` 与 `CHANGELOG.md` 有本批条目

## 5. 兼容性

- [x] 未新增 pip 依赖（`pyproject.toml` 零改动）
- [x] 生产代码零 import：全仓 `.py` 检索 `spec_runner_adapter` 仅命中脚本自身 docstring 与测试文件
- [x] 不改变公开 API、配置文件、真值源
- [x] `git status` 变更范围仅限：2 个新增代码文件 + 4 个 Spec 文档 + 台账/日志

## 6. 代码质量

- [x] `python -m py_compile scripts/spec_runner_adapter.py tests/test_spec_runner_adapter.py` 通过（exit 0）
- [x] `black --check tests/test_spec_runner_adapter.py` 通过（`1 file would be left unchanged`）
- [x] **有意偏离**：`scripts/spec_runner_adapter.py` 保持官方模板原格式，不参与项目 black 重排（项目 black 会改写编排代码，破坏“配置区以外逐行一致”）；该偏离已记录于 §10 发现 F-2
- [x] 无 `TODO` / `FIXME`（`Select-String` 空输出）
- [x] 新增测试无真实 subprocess、无网络、无文件写入（仅 import + 纯函数调用）

## 7. ADD 审计（Step 10）

### Phase 0: Spec 质量门

- [x] DESIGN 无“合理处理 / 适当时机”等不可审计措辞
- [x] 每个设计元素可对应到实现或测试

### Phase 1: 完整性（design → code）

- [x] DESIGN §3.1 的 8 个子命令均在 adapter 中存在（继承模板）
- [x] DESIGN §3.3 的 4 个门禁均在 `GATES` 中存在
- [x] DESIGN §6 的 6 条错误路径均有实现或框架保证（模板 L91-L93、L200-L202；runner L203-L219）

### Phase 2: 忠实度（双向对照）

- [x] 配置区值与 DESIGN §3.2/§3.3 完全一致（`_PY312` 只在配置区）
- [x] 编排代码未被“等价改写”（`git diff --no-index` 仅配置区 3 处）
- [x] 未新增模板之外的函数或参数

### Phase 3: 必要性（code → design）

- [x] adapter 的每项行为均有 DESIGN 依据（命令面来自 README/模板，未自造）
- [x] 测试的每项断言均有 IMPL §2.5 编号依据（U1-U6）

### Phase 4: 语义

- [x] 目标仍是“门禁可执行 + 证据可重放”，未被简化为“脚本能跑”（4 gate + replay + status 全部实测）
- [x] 未把已知 fail 基线伪装为 pass（black/mypy 如实记 fail）

## 8. 取证矩阵（E1-E5）

| 取证手段（等级） | 覆盖项 | 结果 |
|------------------|--------|------|
| `pytest` 红/绿/全量输出（E1） | 测试完整性 / 回归 | RED 6 errors；GREEN 6 passed；全量 509 passed（日志 SHA256 `D262199F…`） |
| `gates` + `dry-run` 输出（E1） | 门禁命令装配 | 4 项列出；dry-run 命令含 runner/session/cwd |
| 4 次 gate 运行 + session jsonl（E1） | 门禁链验收 | pass / pass / fail / fail，exit 与 verdict 一致 |
| `replay` 输出（E1） | 事件流可重放 | probe 1 行 OK；black-check 2 行 OK |
| `git diff --no-index` 模板对照（E1） | 编排代码零改动 | 仅 `PREFIX` 与 `GATES` 配置区差异 |
| 静态读码（E2，新增文件未提交，无法绑 commit） | 8 命令 / 6 错误路径 | 全部存在，无自造逻辑（待提交后补 E3 @commit） |
| 盲区扫描（E4，范围：模板全部函数 + 6 条测试断言） | 无设计外行为 | **发现 2 项**（F-1、F-2，均 P3 并已处理） |

## 9. Step 8 一致性 Review

- [x] 检查 RESEARCH ↔ DESIGN：方案 A 与配置值一致
- [x] 检查 DESIGN ↔ IMPL：接口、门禁、版本一致
- [x] 检查 IMPL ↔ CHECKLIST：Task 与检查项一一对应
- [x] 检查全部 ↔ 外部来源：版本与路径可解析

**Review 记录（Step 8，2026-11-04）**：

| 检查对 | 核对方式 | 结果 |
|--------|----------|------|
| RESEARCH ↔ DESIGN | 比对 A 方案配置（RUNNER/PREFIX/CWD/GATES） | 一致 |
| DESIGN ↔ IMPL | 比对 §3.1 八命令、§3.3 四门禁、版本表 | 一致 |
| IMPL ↔ CHECKLIST | T-1~T-5 与 §1/§2/§3 检查项 | 一一对应 |
| 全部 ↔ 外部来源 | `Test-Path` 四文档；`Select-String` 关键值；源码与 README 读回 | 四文档存在；关键值均命中；来源可解析 |
| 文档链接 | 相对链接目标存在 | 通过 |

**结论**：无矛盾项；通过 Step 8 门禁。

## 10. Step 9 TDD 记录

| 阶段 | 命令 | 读数 |
|------|------|------|
| RED | `pytest tests/test_spec_runner_adapter.py -q` | `6 errors in 0.09s`：adapter 未实现 |
| GREEN | 同上（创建 adapter 后） | `6 passed in 0.04s` |
| REFACTOR | `black tests/test_spec_runner_adapter.py` | `1 file reformatted`，随后 `6 passed` |
| 回归 | `MPLBACKEND=Agg python312 -m pytest tests -q` | `509 passed, 82 warnings in 20.02s` |

**发现并修复（Step 9）**：

1. **F-1（P3）**：`black` 报告写 stderr，runner 只捕获 stdout（`spec_runner.py` L123），首轮 `black-check` 的 `stdout_tail` 为空。修复：门禁命令追加 `2>&1`，重跑后 seq 2 捕获 `75 files would be reformatted`。
2. **F-2（P3）**：项目 black（line-length 100）会重排上游模板编排代码，与“配置区以外逐行一致”冲突。处理：adapter 保持模板原格式；仅新增测试文件执行 black；在 §6 如实记录偏离。
3. **F-3（P3）**：`mypy core` 在本仓目录名（含点）下直接报“not a valid Python package name”；改用 `--explicit-package-bases`，基线 `168 errors in 20 files`。

## 11. 最终结论

- **P1/P2 阻断项**：0
- **P3 项**：3 项（F-1 已修复并复跑；F-2/F-3 已记录为有意处理/基线）
- **门禁链**：2 pass（probe、unit-tests）+ 2 expected-fail（black-check、mypy-check）
- **状态**：done；残余技术债登记为 P-007（mypy 168 errors）与 U-006（mypy 门禁转绿条件）
