# RESEARCH：P-036 mypy 检查面扩展（U-P024-3 / U-P024-4 / U-P024-1 取证）

> **批次**: P-036 · **Step 1 调研** · 日期 2026-11-17 · 来源日期 2026-11-17（读取日）
> **判档**: **T1**（SPEC_PROCESS 判档规则 2 强制升级：扩面 = 变更 CI 门禁判据；即使取证结论为「不扩面」，评估过程已触达门禁真值面，禁止降 T3）
> **作者基座**: DeepSeek-V4.1-Flash（Step 2 Review 须异构，RULE-5）
> **上游台账**: U-P024-3（mypy 检查面扩展）/ U-P024-4（`filter/` 21 errors）/ U-P024-1（mypy 版本上限）
> **代码证据时点**: HEAD `6e052c3`

---

## 1. 批次目标与取证问题

用户指令：启动 U-P024-3「mypy 检查面扩展」取证批。本 Step 只做机械取证，不做实现，回答四问：

| # | 问题 | 本 Step 的回答出口 |
|---|------|-------------------|
| Q1 | 门禁现状口径是什么，CI 实际跑哪个版本？ | §3.2 + §4.1（保真校验） |
| Q2 | 各候选模块在 **CI 等价口径** 下的 mypy 错误数是多少？ | §4.2（B/C 两方案读数） |
| Q3 | 这些错误是「真实缺陷面」还是「类型桩噪声」？ | §5（R1-R2 机制实锤）+ §6（分级） |
| Q4 | 扩面的代价与分批方式？ | §7（方案矩阵 + 低效排除） |

---

## 2. 治理对象与现状

### 2.1 CI 门禁现状（E1 读码）

```yaml
# .github/workflows/tests.yml
- name: Type check (mypy)
  run: python -m mypy --explicit-package-bases --check-untyped-defs core
```

- **target = `core` 单目录**；`agents/` / `filter/` / `scripts/` / `batch_backtest/` / `strategy_evaluation/` / `cli.py` **不在门禁面**。
- `pyproject.toml` 声明 `[[tool.mypy.overrides]] module = ["filter.*"] ignore_errors = true`（P-024 `f8cb9ba` 引入），注释写明「解析类型、但不报告错误，使门禁结果只反映 core」。
- 依赖声明 `mypy>=1.5.0`，**无上限**（U-P024-1 维持「倾向不钉」）。

### 2.2 三条关联台账项

| ID | 原描述 | 本 Step 的处置 |
|----|--------|---------------|
| U-P024-3 | mypy 检查面扩展（`cli.py`/`agents`/`web`/`scripts`） | 本批主体；读数见 §4 |
| U-P024-4 | `filter/` 在 pandas 3.x 下的 21 errors | **前提需重写**（R2/R3：与 pandas 版本无关） |
| U-P024-1 | mypy 版本上限（倾向不钉） | **新增实证支撑**（R1：2.1.0 与 2.4.1 行为不同） |

---

## 3. 取证环境与保真校验

### 3.1 环境矩阵（E1）

| 环境 | mypy | pandas | numpy | pydantic | Python |
|------|------|--------|-------|----------|--------|
| 本机主环境 | **2.1.0** | 2.2.3 | 2.4.6 | 2.14.3 | 3.12.10 |
| CI（run `43934945348` 安装日志实证） | **2.4.1** | **3.1.1** | 2.4.6 | 2.14.3 | 3.10 / 3.11 / 3.12 |
| 隔离复刻 venv `%TEMP%\p036ci2`（`pip install -e ".[dev]"`） | 2.4.1 | 3.1.1 | 2.5.5 | 2.14.3 | 3.12.10 |

CI 版本取证命令：`gh run view 43934945348 --log | Select-String "mypy-2\."` → `Using cached mypy-2.4.1-...whl`；`Successfully installed ... mypy-2.4.1 ... pandas-3.1.1 ... pydantic-2.14.3`。

### 3.2 保真校验（关键，防「环境不齐导致读数失真」）

在隔离 venv 中原样复刻 CI 命令：

```
mypy --explicit-package-bases --check-untyped-defs core
```

**读数：`Success: no issues found in 37 source files`** —— 与 CI 日志逐字一致。**复刻环境可信**，其扩面读数可作 CI 口径依据。

> **降级链（F3）**：先试 `pip install -e ".[dev]"` 于预钉 `pandas==3.1.1` 的旧 venv → **ResolutionImpossible**（numpy 预钉 2.5.5 与 scipy/cvxpy 闭包冲突）→ 改用**全新 venv 不预钉**、直接装 `.[dev]` → 成功，版本与 CI 一致。无静默跳过。

---

## 4. 读数

### 4.1 单模块读数（CI 等价口径，mypy 2.4.1）

| target | errors | 含错误文件 / 检查文件 | 说明 |
|--------|--------|----------------------|------|
| `core` | **0** | 0 / 37 | 现状门禁面，绿 |
| `agents` | **94** | 11 / 14 | 最大面 |
| `filter` | **21** | 7 / 10 | 与 P-024 记录数字相同（但归因不同，见 R2） |
| `scripts` | 5 | 2 / 11 | 含 `external_benchmark/verify_p015.py` 3 条 |
| `cli.py` | 3 | 1 / 1 | 根目录单文件 |
| `strategy_evaluation` | 3 | 2 / 3 | |
| `order_strategy` | 2 | 1 / 3 | 非 U-P024-3 原列面，作为候选补测 |
| `batch_backtest` | 1 | 1 / 2 | |
| `web` | **0** | 0 / 9 | 零负担 |
| `factor_library` | **0** | 0 / 2 | 零负担 |

### 4.2 合并读数（两种门禁设计）

| 方案 | target 集 | 读数 |
|------|-----------|------|
| **B（filter 不豁免）** | `core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy` | **129 errors / 25 files**（检查 81 source files） |
| **C（保留 `filter.*` 豁免）** | 同上减去 `filter` | **108 errors / 18 files**（检查 71 source files） |

### 4.3 错误码分布（B 方案，129 条）

| 错误码 | 数量 | 性质判断（§6 详述） |
|--------|------|-------------------|
| `union-attr` | **50** | **高价值**：潜在运行时 `AttributeError` |
| `no-any-return` | 34 | 低：注解卫生（`warn_return_any`） |
| `var-annotated` | 11 | 低：缺注解 |
| `assignment` | 8 | 中：类型契约不一致 |
| `arg-type` | 6 | 中 |
| `call-overload` | 4 | 中 |
| `return-value` | 3 | 中 |
| `attr-defined` | 3 | 中 |
| `index` | 3 | 中 |
| `list-item` | 3 | 中 |
| `call-arg` / `operator` / `func-returns-value` / `misc` | 1 / 1 / 1 / 1 | 低-中 |

### 4.4 错误集中度（B 方案 Top 12）

| 文件 | errors |
|------|--------|
| `agents/guru_agent_v2.py` | 26 |
| `agents/agent_framework.py` | 17 |
| `filter/universe_filter_clean.py` | 13 |
| `agents/strategy_allocator.py` | 8 |
| `agents/assumption_monitor.py` | 8 |
| `agents/auto_parameter_optimizer.py` | 8 |
| `agents/style_reflection_engine.py` | 8 |
| `agents/multi_strategy_engine.py` | 6 |
| `agents/style_drift_analysis.py` | 5 |
| `agents/sentiment_framework.py` | 5 |
| `scripts/external_benchmark/verify_p015.py` | 3 |
| `cli.py` | 3 |

**集中度**：Top 3 文件占 56/129（43%）；`agents/` 单目录占 **94/129（73%）**。

---

## 5. 关键发现

### R1（机制实锤）：根因是 **mypy 版本行为差异**，不是 pandas 类型桩

决定性对照实验（同一 config，仅换 mypy 版本）：

| mypy | 命令 | 读数 |
|------|------|------|
| **2.1.0**（主环境） | `mypy --config-file <无 override> core` | `Success: no issues found in 37 source files` |
| **2.4.1**（CI 同版本） | `mypy --config-file <无 override> core` | **`Found 21 errors in 7 files (checked 37 source files)`** |

即：同一份代码、同一份配置、同一 pandas（3.1.1 / 2.2.3 均**无** `py.typed`），**mypy 2.4.1 会把被 follow 的 `filter/` 模块错误计入 `core` 的检查结果，2.1.0 不报**。

**pandas 类型桩假设被直接证伪**：`pandas 2.2.3` 与 `pandas 3.1.1` 的 `py.typed` 检测均为 `False`（`os.path.exists(pandas.__path__[0]+'/py.typed')`），且 `dev` extras 未声明 `pandas-stubs` → 两版本下 pandas 都是 `Any`，不可能产生 `union-attr` 这类需要具体类型的错误。

### R2（P-024 归因失实）：原「X1-X4 验证 mypy 2.1.0/2.4.1 均 0」不成立

- P-024 记录（[CHANGELOG](../CHANGELOG.md) `### CI` 条目 / `PROGRESS §3.28`）称：Step 9 首跑 CI 报 `filter/*` 21 errors，经 X1-X4 隔离实验判定「根因 pandas 3.1.1 类型桩，非 mypy 版本；mypy 2.1.0 / 2.4.1 均 0」。
- 本轮实测：**mypy 2.4.1 无 override 时 `core` = 21 errors**，与 P-024 的 CI 读数完全一致；mypy 2.1.0 = 0。**结论方向相反**。
- 影响：`filter.* ignore_errors` 的注释理由（「pandas 3.1.1 类型桩」）与事实不符；该 override 事实上掩盖的是 **`filter/` 自身的 21 条代码级类型错误**，而这些错误在 pandas 2.2.3 本地、2.1.0 下**把 filter 作为直接目标**即可复现（`mypy filter` = 21 errors）。

### R3（U-P024-4 前提需重写）

| 原前提 | 实测 |
|--------|------|
| 「`filter/` 在 pandas 3.x 下的 21 errors」 | 21 errors 与 pandas 版本**无关**：pandas 2.2.3 下 `mypy filter` 同为 **21 errors / 7 files**；成因是 mypy 2.4.x 的 follow 行为 + filter 自身类型缺陷 |
| 「`core/` 0 条；本地 pandas 2.2.3 为 0」 | 仅当使用 mypy 2.1.0 时成立；CI 的 2.4.1 下 `core` 门禁之所以仍绿，**完全依赖** `filter.* ignore_errors` |

### R4（真实缺陷面）：50 条 `union-attr` 是潜在 `AttributeError`

样本（CI 等价口径原文）：

```
agents\style_drift_analysis.py:250: Item "None" of "dict[str, Any] | None" has no attribute "get"
agents\style_reflection_engine.py:222: Item "bool" / "dict" / "str" of "list[Any] | bool | dict[Any, Any] | str" has no attribute "append"
agents\agent_framework.py:1292: Item "None" of "UniverseFilter | None" has no attribute "tradable"
agents\agent_framework.py:1334: Item "None" of "DataManager | None" has no attribute "get_adj_price"
agents\agent_framework.py:1335-1337 / 1434: 同上（5 处同形）
```

`agents/agent_framework.py` 的 6 处 `DataManager | None → .get_adj_price` 与 `UniverseFilter | None → .tradable` 正是 P-029/P-031 批次反复出缺陷的同型面（Optional 未守卫）。**这类错误不是注解洁癖，是运行期崩溃候选**。

### R5（零负担面）

`core/`（37 files）、`web/`（9 files）、`factor_library/`（2 files）在 CI 等价口径下均为 **0 errors**——扩面不需要在这些目录付出修复成本。

### N1-N3（负向发现）

| ID | 内容 |
|----|------|
| N1 | **不是 pandas 问题**：见 R1；两版本 pandas 均无 `py.typed`，`dev` extras 无 `pandas-stubs` |
| N2 | **不是目录名含点号问题**：`--explicit-package-bases` 在 INI 配置（`explicit_package_bases = True`）与 CLI 旗标下等价，均无 exit 2 |
| N3 | **`filter` 确实被 follow**：`mypy -v core` 输出 `Parsing ...\filter\universe_filter_clean.py (filter.universe_filter_clean)` / `filter\limit_rules.py` / `filter\__init__.py` / `filter\base.py` 等——排除「filter 未被解析」的替代解释 |

---

## 6. 错误分级（供设计阶段取舍，不预设结论）

| 级别 | 判据 | 错误码 | 数量（B 方案） | 建议 |
|------|------|--------|--------------|------|
| **A 运行期风险** | `Optional` / `Union` 未守卫的解引用，可致 `AttributeError` | `union-attr` | **50** | 逐条修（可能有真实 bug） |
| **B 契约不一致** | 类型声明与实现/调用不匹配 | `assignment` / `arg-type` / `call-overload` / `return-value` / `attr-defined` / `index` / `list-item` / `call-arg` / `operator` / `misc` | **30** | 逐条修，可能暴露接口误用 |
| **C 注解卫生** | 只影响类型信息质量，无运行期风险 | `no-any-return` / `var-annotated` / `func-returns-value` | **46** | 机械批量修（`cast` / 显式注解 / `Any` 收敛） |
| 其他 | — | — | 3 | 归入 B/C |

> 合计 50 + 30 + 46 + 3 = **129**。分级依据 = 错误码语义 + §5 R4 样本人工判定；**具体到行仍需 Step 3 设计阶段逐条读码**（本 Step 不做逐行定性，避免把取证写成结论）。

---

## 7. 方案矩阵与低效排除

### 7.1 方案矩阵

| 方案 | 内容 | 代价 | 风险 | 收益 |
|------|------|------|------|------|
| **M-A 全量一次到位** | target 一次性扩至 8 个面，修完 129 条（filter 也去豁免） | 大（129 条 + 可能多处行为修正） | 高（大批量行为变更 + golden 敏感） | 一次解决 |
| **M-B 两级分批（推荐）** | **B1**：`core` + 小模块（`scripts` 5 / `cli.py` 3 / `strategy_evaluation` 3 / `order_strategy` 2 / `batch_backtest` 1，共 **14**）+ 保留 filter 豁免；**B2**：`agents` **94** 独立批；**B3**：`filter` **21** + 去豁免 | 中（可分段验收） | 中（B2 独立可回退） | 每批门禁即刻生效，风险隔离 |
| **M-C 仅钉版本不扩面** | 只加 `mypy~=2.4` 上界，target 不变 | 极小 | 极低 | 消除「CI 隐性升级」风险，但不增覆盖 |
| **M-D 扩面但保留 filter 豁免** | target 扩至 7 面，filter 继续 `ignore_errors` | 中（108 条） | 中 | 覆盖 agents 但不正视 filter 缺陷 |

**推荐 M-B**：`agents/` 占 73% 且含 50 条 A 级风险，单独立批便于独立验收与回退；小模块 14 条可先落以验证「扩面 + 门禁变绿」的完整链路。**M-C 应作为 M-B 的前置子项**（版本不钉会让门禁在任意 CI 日静默改变读数——R1 已实证 2.1.0→2.4.1 会从 0 变 21）。

### 7.2 低效排除

| # | 候选 | 排除理由 |
|---|------|----------|
| 1 | 用 `--follow-imports=silent` 让 `core` 门禁不受 filter 影响 | 治标：错误仍在，且 silent 会连带屏蔽未来真实的 core→filter 契约问题 |
| 2 | 直接删掉 `filter.* ignore_errors` 并让门禁红 | 门禁不能长红；须「修到绿」再扩面，否则日常提交全红 |
| 3 | 对 `agents/` 加 `ignore_errors` 而非修复 | 复制 P-024 的错误（掩盖 50 条 A 级风险），且 agents 是缺陷高发区 |
| 4 | 为 129 条统一加 `# type: ignore` | 把门禁变成装饰；且 `warn_unused_ignores` 关闭时无法回收 |
| 5 | 只扩 `web/`、`factor_library/` | 两者本就 0 errors，扩面零收益（但可低成本纳入以锁定未来回归） |
| 6 | 在本批顺手统一 mypy 全仓 `strict = true` | 远超题干；会引入数百条新错误，无分批可验收性 |
| 7 | 把 `tools/` / `examples/` / `demo/` 一并纳入 | 非生产运行路径，且未测；应作为 U-* 另议（未覆盖项，§8） |

---

## 8. 风险与未决（四元块）

| ID | 判据 | 触发条件 | 当前倾向 | 证据等级 |
|----|------|----------|----------|----------|
| **U-P036-1** | `pyproject.toml` 是否出现 mypy 上界（如 `mypy>=1.5.0,<3` 或 `~=2.4`），且 CI 读数可复现 | 本批 DESIGN 阶段 | **倾向钉上界**（R1 实证版本行为差异会改变门禁读数） | E1 |
| **U-P036-2** | `filter.* ignore_errors` 是否移除，且 `mypy filter` = 0 | B3 批立项 | 倾向移除（21 条为真实代码错误，R3） | E1 |
| **U-P036-3** | 50 条 `union-attr` 是否全部修复（而非 `assert`/`cast` 掩盖） | B2 批 Step 3 逐条读码 | 无倾向（须逐条判定是否为真实可达） | E2（样本已复现） |
| **U-P036-4** | `tools/` / `examples/` / `demo/` / `memory/` 是否纳入 | 任一目录出现生产调用 | 不纳入（本批未测，显式未覆盖） | 未验证 |
| **R-P036-1** | 扩面后门禁在 3.10/3.11/3.12 三版本 mypy 读数一致 | 每次 CI | 接受（mypy 单版本二进制，Python 版本只影响 target 解析） | 待 Step 9 实测 |
| **R-P036-2** | 修复 50 条 union-attr 可能改变运行期行为（新增 `None` 早退） | B2 实施 | 需 DESIGN 阶段显式裁决「守卫 vs 保持原崩溃」 | 未验证 |

---

## 9. 复现命令（E1，可原样重放）

```powershell
# 0) 隔离环境（CI 等价）
$py = "C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe"
$v2 = "$env:TEMP\p036ci2"
& $py -m venv $v2
& "$v2\Scripts\python.exe" -m pip install -q -e ".[dev]"

# 1) 保真校验（期望：Success: no issues found in 37 source files）
& "$v2\Scripts\python.exe" -m mypy --explicit-package-bases --check-untyped-defs core

# 2) 全候选扩面（期望：Found 129 errors in 25 files）
& "$v2\Scripts\python.exe" -m mypy --config-file <无 override 的 ini> `
    core agents filter scripts batch_backtest strategy_evaluation cli.py order_strategy

# 3) 机制对照（mypy 版本差异）
& "$v2\Scripts\python.exe" -m mypy --config-file <无 override 的 ini> core   # 2.4.1 → 21 errors
python -m mypy --config-file <无 override 的 ini> core                        # 2.1.0 → Success

# 4) pandas 类型桩检测（期望：两版本均 False）
python -c "import pandas,os;print(os.path.exists(os.path.join(os.path.dirname(pandas.__file__),'py.typed')))"
```

**未覆盖项（E5 清单，不入结论）**：`tools/` / `examples/` / `demo/` / `memory/` / `gurus/` 未测；`tests/` 不在治理面。

---

## 10. 下一 Step

**Step 2 Review（须异构基座）**：核验本文件全部读数的可重放性（§9 命令）、R1/R2 的对照实验是否成立、错误分级是否越界成结论、U-P036-1~4 四元块是否齐全。Review 通过后进入 Step 3 DESIGN（决定 M-B 分批边界、mypy 版本上界、filter 豁免处置）。

---

## 11. B0 子项裁决与实施记录（mypy 版本上界，2026-11-17）

> 用户裁决「先钉 mypy 上界」→ 采纳 §7 **M-C 作为 M-B 的前置子项**独立落地；依赖真值源变更 → T1。本节即 B0 的设计取舍 + 实施 + 验证记录（Step 3/5/9/10 的 B0 面合并记录，整批其余子项仍走完整管线）。

### 11.1 裁决与被拒方案

| 方案 | 约束 | 裁决 | 理由 |
|------|------|------|------|
| A | `mypy>=1.5.0,<3.0` | **拒绝** | 只挡 3.0；2.5/2.6 仍可漂移——而 R1 已实证 **2.1→2.4 就改变门禁读数（0 → 21）**，等于没解决 |
| **B（采纳）** | **`mypy~=2.4.1`**（`>=2.4.1,<2.5`） | **采纳** | 钉到 patch 系列：行为变化概率最低、安全补丁仍可进；升级须显式提交（可审查） |
| C | `mypy==2.4.1` | 拒绝 | 冻结补丁修复；锁/本地任何 2.4.x 差异都要人工改，收益边际 |
| D | 维持 `>=1.5.0` | 拒绝 | R1 实证门禁读数随 CI 解析漂移（CI 已装 2.4.1，本机仍 2.1.0） |

### 11.2 变更清单

| # | 对象 | 变更 |
|---|------|------|
| 1 | `pyproject.toml` `[project.optional-dependencies].dev` | `"mypy>=1.5.0"` → **`"mypy~=2.4.1"`** + 三行注释（含 R1 锚点与「升级须显式提交」） |
| 2 | `pyproject.toml` `[[tool.mypy.overrides]] filter.*` 注释 | 更正 P-024 归因：21 条是 **filter 自身类型错误**（`mypy filter` 在 pandas 2.2.3 下同样复现），非「pandas 3.1.1 类型桩」；**B3 修完后移除本 override** |
| 3 | `uv.lock` | `uv lock`：**mypy 2.1.0 → 2.4.1**；传递依赖 `ast-serialize 0.5.0→0.13.1` / `librt 0.11.0→0.16.1`；numstat **+240/−163** |
| 4 | 本机 Python312 主环境 | `pip install "mypy~=2.4.1"` → **2.4.1**（与锁、CI 三方一致） |

### 11.3 验证读数

| 项 | 命令 | 读数 |
|----|------|------|
| 锁一致性 | `uv lock --check` | **exit 0**（Resolved 148 packages） |
| 本地版本 | `mypy --version` | **2.4.1** |
| 门禁口径 | `mypy --explicit-package-bases --check-untyped-defs core` | **0 errors / 37 files** |
| 反证（override 是绿的唯一原因） | 同上 + 无 override 配置，target = `filter` | **21 errors / 7 files** |
| 格式 | `black --check core tests` | **121 unchanged** |
| 全量测试 | `pytest -q` | **760 passed**（172 warnings，56.55s） |

### 11.4 影响与后续

- **副作用（已披露）**：本地开发者 `pip install -e ".[dev]"` 会升到 2.4.x，无法再停留在 2.1.0；若有本地脚本依赖旧版 mypy 行为，需显式降级（不受本约束保护）。
- **未改变（显式）**：门禁 target 仍为 `core`；`filter.*` 仍豁免（B3 处置）；`agents/` 等 129 条错误未触碰。
- **台账**：`U-P024-1` → done；`U-P036-1` → done；`U-P036-2~4` 仍 pending。
- **残余风险**：2.4.x 内部补丁升级仍可能微调诊断（概率低）；若发生，`uv lock` + CI 会在同一次提交内暴露，不会静默漂移。
