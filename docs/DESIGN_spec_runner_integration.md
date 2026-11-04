# Spec_Runner 接入 · 设计文档

> **文档编号**: DESIGN_spec_runner_integration
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-04
> **状态**: 已完成（Step 4 Review 通过）
> **上游**: [RESEARCH_spec_runner_integration.md](RESEARCH_spec_runner_integration.md)
> **下游**: [IMPL_spec_runner_integration.md](IMPL_spec_runner_integration.md) → [CHECKLIST_spec_runner_integration.md](CHECKLIST_spec_runner_integration.md)
> **权威源**: `F:\Spec_Runner\README.md`、`spec_runner.py` v1.0.0 @ `60ab3e3`、`SPEC_RUNNER_DESIGN.md` v1.0 @ `bf83e48`

---

## 1. 设计目标

1. 让本项目的流程门禁可通过 `Spec_Runner` 执行，并把 `verdict / exit / stdout_tail` 落入 append-only 事件流。
2. 保持与上游模板**零逻辑复制**：只改配置区四处（`RUNNER / PREFIX / CWD / GATES`），编排代码原样保留。
3. 新增代码可测试：配置与命令装配能被单元测试覆盖，且测试不产生外部副作用。
4. 明确已知红基线：`black-check` 与 `mypy-check` 注册为预期 fail，读数写入清单，不伪装成 pass。

### 1.1 量化目标

| 目标 | 验收标准 |
|------|----------|
| 配置文件 | 恰好新增 1 个脚本：`scripts/spec_runner_adapter.py` |
| 编排代码改动 | 相对官方模板 v1.0，配置区以外 **0 行改动** |
| 单元测试 | 新增 ≥5 项，全部通过；不执行真实 subprocess |
| 门禁覆盖 | `gates` 列出 4 项：`probe / unit-tests / black-check / mypy-check` |
| 证据链 | 至少 1 条 session 可 `replay` 通过；`probe` verdict=pass |
| 回归 | 全量测试由 503 → **509 passed**（新增 6 项） |

## 2. 架构设计

```
┌──────────────────────────────────────────────────────────┐
│ scripts/spec_runner_adapter.py（编排壳，官方模板 v1.0）  │
│  ┌──────────── 配置区（唯一改动面） ────────────┐        │
│  │ RUNNER = F:\Spec_Runner\spec_runner.py       │        │
│  │ PREFIX = factorv3                             │        │
│  │ CWD    = None → 仓库根                        │        │
│  │ GATES  = probe / unit-tests / black-check     │        │
│  │          / mypy-check                         │        │
│  └───────────────────────────────────────────────┘        │
│  _build_gate_cmd ──► [runner, gate, --name, --cmd,        │
│                       --session {PREFIX}-{gate}-{date},   │
│                       --cwd {repo root}]                   │
└───────────────────────┬──────────────────────────────────┘
                        │ subprocess（exit 透传）
                        ▼
┌──────────────────────────────────────────────────────────┐
│ F:\Spec_Runner\spec_runner.py v1.0.0                     │
│  gate: shell=True → 捕获 exit + stdout_tail(≤2000)        │
│         → append sessions/<sid>.jsonl → verdict 机械映射  │
│  replay: seq 单调 + 行可解析 + llm_request 载荷完整       │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ▼
        F:\Spec_Runner\sessions\factorv3-<gate>-<yyyymmdd>.jsonl
```

**职责边界**：

| 组件 | 负责 | 不负责 |
|------|------|--------|
| adapter | 命令装配、session 命名、cwd 注入、exit 透传 | 不执行判据、不解析测试结果、不改 gate 语义 |
| runner | 执行命令、写事件流、seq 保证、replay 校验 | 不判断测试质量、不内置本仓路径 |
| 本仓测试 | 验证配置与命令装配形态 | 不启动真实 gate（由 Step 9 门禁链实测覆盖） |

## 2A. 方案对比矩阵（Type-1 决策必填）

**本轮判定：Type-2（可逆）**，不启用 7 维矩阵（`docs/SPEC_STANDARD.md` §11.8.1）。判据：删除新增脚本与测试即可回退，无常驻副作用、不改变真值源或契约。候选 A/B/C 的拒绝理由与代价已记录于 [RESEARCH](RESEARCH_spec_runner_integration.md) §3.2。

## 3. 接口定义

### 3.1 CLI 子命令（与官方模板一致）

| 子命令 | 参数 | 行为 | 退出码 |
|--------|------|------|--------|
| `gates` | 无 | 打印 GATES 表 | 0 |
| `gate <name> [--session S]` | 门禁名 | 装配 runner gate 命令并执行 | 透传 runner/命令 exit；未知门禁 2 |
| `run --task T [...]` | task/session/prompt/require-gate | 透传 runner `run` | 透传（缺端点 2 / 不可达 1 / gate 未过 3） |
| `status [--session S]` | 可选 session | 透传 runner `status` | 0/1 |
| `replay --session S` | session | 透传 runner `replay` | 0（校验通过）/1 |
| `fork --session S --seq N --new N2` | 参数 | 透传 runner `fork` | 0/1 |
| `probe` | 无 | 执行 `probe` 门禁 | 透传 |
| `dry-run <inner...>` | 内层子命令 | 只打印将执行命令 | 0 |

### 3.2 配置常量

| 常量 | 值 | 来源 / 理由 |
|------|-----|-------------|
| `RUNNER` | `F:\Spec_Runner\spec_runner.py` | 官方 README 指定执行器绝对路径 |
| `PREFIX` | `factorv3` | session 前缀；满足 `^[a-z0-9-]{1,64}$` |
| `CWD` | `None` | 模板语义：取脚本父目录的父目录 = 仓库根 |
| `ENDPOINT/MODEL/PROVIDER` | `SR_*` 环境变量 | 运行时注入，不硬编码 |

### 3.3 GATES 表

| name | 命令 | 预期 verdict | 依据 |
|------|------|--------------|------|
| `probe` | `echo Spec_Runner OK` | pass | 官方接入自检（README L83-L84） |
| `unit-tests` | `set MPLBACKEND=Agg&& "<Python312>" -m pytest tests -q` | pass | 基线 503 passed（P3）；固定解释器规避 U-005 |
| `black-check` | `"<Python312>" -m black --check core tests 2>&1` | **fail（预期）** | 基线 75 files reformatted（P4），TD-9 未完成；`2>&1` 因 runner 只捕获 stdout（源码 L123），black 报告写 stderr |
| `mypy-check` | `"<Python312>" -m mypy --explicit-package-bases core` | **fail（预期）** | 基线 168 errors / 20 files（P5）；无该旗标时目录名含点直接报错 |

`<Python312>` = `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`。

## 4. 依赖分析

| 类型 | 内容 |
|------|------|
| 运行时依赖 | Python ≥3.8 stdlib（`argparse/os/subprocess/sys/datetime/pathlib`）；无 pip 依赖 |
| 外部依赖 | `F:\Spec_Runner\spec_runner.py` v1.0.0（手工安装，非 pip） |
| 内部依赖 | 仅 `pyproject.toml` 的 `requires-python >=3.10`；不 import 任何项目模块 |
| 生产影响 | 零：无运行时模块 import adapter；脚本仅手动/CI 调用 |

## 5. 性能与资源

- adapter 自身：解析参数 + 拼命令，常数级开销。
- 门禁耗时由被调命令决定：`unit-tests` 基线约 19 秒（P3）；`black-check`/`mypy-check` 为静态扫描，实测读数记入 Step 9。
- 事件流：每次 gate 一行 JSON（stdout 截断 ≤2000 字符），磁盘增量可忽略。
- 无网络调用（`run` 子命令除外，且需显式端点）。

## 6. 错误处理

| 场景 | 行为 | 退出码 | 证据 |
|------|------|--------|------|
| 未知门禁名 | stderr 提示可用门禁，`sys.exit(2)` | 2 | 模板 L91-L93 |
| RUNNER 不存在 | `_exec` 捕获 `FileNotFoundError`，提示检查 RUNNER | 127 | 模板 L200-L202 |
| 门禁命令失败 | 原样透传 fail exit | 非零 | runner L118-L132 |
| session 复用 | gate 为 append-only，允许追加；`run` 无 `--resume` 拒绝 | 0 / 2 | runner L203-L205 |
| `--require-gate` 未通过 | runner 拒绝启动 | 3 | runner L206-L209 |
| 端点不可达 | 写 `endpoint_unreachable` 事件后退出 | 1 | runner L215-L219 |

## 7. 回退点

- 删除 `scripts/spec_runner_adapter.py` 与 `tests/test_spec_runner_adapter.py`；
- 还原 `docs/` 四文档与台账行；
- 运行态：`F:\Spec_Runner\sessions\factorv3-*.jsonl` 为 append-only 证据，可保留（不影响本仓运行）。

## 8. 决策 / 拒绝方案表（Step 3 要求）

| 决策 | 选择 | 拒绝的替代方案 | 拒绝理由 | 代价 |
|------|------|----------------|----------|------|
| 接入形态 | 官方 adapter | 自研封装 | 双实现漂移，违背模板边界 | 失去定制灵活性 |
| 门禁解释器 | 固定 Python312 | 用 `python` | 当前 `python`=Anaconda 3.13.5 缺 cvxpy | 换机需改配置区 |
| session 落盘 | 用 runner 默认目录 | 覆盖 `SR_SESSIONS_DIR` 到本仓 | 偏离 README 默认形态；模板不支持该配置项 | 证据在外部仓，需用绝对路径引用 |
| 红基线门禁 | 注册并标预期 fail | 不注册 black/mypy | 用户已指定四项门禁；隐藏基线等于失真 | 门禁链 2 pass / 2 fail |

## 9. Review 记录（Step 4）

- **时点**：2026-11-04，设计完稿后单独执行。
- **审查项与结果**：

| 检查项 | 结果 |
|--------|------|
| 接口完整性 | 8 个子命令均有参数、行为、退出码 |
| 依赖真实性 | stdlib + 外部 runner v1.0.0，均已在 RESEARCH 验证 |
| 兼容性 | 不 import 生产模块、不改公开 API、不改依赖清单 |
| 性能估算 | 有来源读数（P3），无编造 |
| 降级策略 | RUNNER 缺失返回 127；未知门禁 2 |
| 回退点 | 删除 2 个新文件 + 还原文档 |
| 决策表 | 4 项决策均写被拒方案与代价 |

- **发现并修复**：
  1. 初稿未区分“参考仓只读”与“执行器状态目录”，易被误读为修改外部参考仓；已在 RESEARCH §2.3 与本文 §3.2 显式区分。
  2. 初稿漏写 mypy 无 `--explicit-package-bases` 时的直接报错前提；已补入 GATES 依据。
- **结论**：无阻断项，通过 Step 4 闸门。
