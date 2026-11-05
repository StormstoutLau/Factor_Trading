# CI 测试环境缺失（P-009） · 实施文档

> **文档编号**: IMPL_ci_test_env
> **阶段**: Phase 2 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-05
> **状态**: 已完成（Step 6 Review 通过）
> **上游**: [DESIGN_ci_test_env.md](DESIGN_ci_test_env.md)（Step 4 Review 通过）；[RESEARCH_ci_test_env.md](RESEARCH_ci_test_env.md)
> **下游**: [CHECKLIST_ci_test_env.md](CHECKLIST_ci_test_env.md)
> **证据时点**: 本仓读数 @ `17e6f26`；本机环境读数 2026-11-05；规划期预演于 `%TEMP%` 隔离目录

---

## 1. 任务分解

| Task | 内容 | 文件 | 验证 | 规模 |
|------|------|------|------|------|
| T-0 | 准备 RED 证据：在空目录复现 CI 红（27 项 9 failed + 18 errors）+ 静态断言脚本（不入仓） | `%TEMP%\p009_*` | 自身（RED 读数） | ~50 行临时 |
| T-1 | 新增夹具生成脚本：`generate_fixture()` + CLI + exit 2 覆盖保护 | `scripts/prepare_test_fixture.py` | V1/V2（探针目录 27 passed；默认路径 exit 2） | 新增 ~95 行 |
| T-2 | 5 处绝对路径改 `GURU_DIR` | `tests/test_distillation_isolation.py` | V3 静态断言 + 该文件测试通过 | +3 / -5 |
| T-3 | 模块级 `pytest.importorskip("numba")` | `tests/test_numba_jit_performance.py` | V4 静态断言 + 本地 7 passed | +4 |
| T-4 | CI 增加 `Prepare test fixture` step | `.github/workflows/tests.yml` | V5 YAML 结构断言 | +3 |
| T-5 | 全量回归 + 门禁入流 | 无新文件 | V6 / `gate unit-tests` / `black-check` / `mypy-check` | — |
| T-6 | 台账回写 + 临时文件清理 | `docs/PROGRESS.md` | 读回 + `git status` 无残留 | +1 |

**依赖顺序**：T-0 → T-1 →（V1/V2 GREEN）→ T-2 / T-3 / T-4（互不依赖，可连续编辑）→（V3/V4/V5 GREEN）→ T-5 → T-6。

## 2. 工程细节

### 2.1 版本约束（实测）

| 组件 | 版本 | 证据 |
|------|------|------|
| 本机基线解释器 | Python 3.12.10 | E1 2026-11-05 |
| 项目 Python 下界 | `>=3.10`（CI 矩阵 3.10/3.11/3.12） | `pyproject.toml:10`；`tests.yml:16` |
| pytest（本机） | **9.0.3** | E1 |
| pytest（项目声明下限） | `>=7.4.0` | `pyproject.toml:54`、`:62` |
| numpy | 2.4.6 | E1 |
| pandas | 2.2.3 | E1 |
| PyYAML（仅本地校验） | 6.0.3 | E1 |
| numba（仅本地，CI 不装） | 0.65.1 | RESEARCH P11 |

**`pytest.importorskip(..., reason=)` 的版本门槛**：`reason` 参数由 pytest **4.6.0**（issue #4599）引入（S10），远低于本项目 `>=7.4.0` 下限，故 T-3 可直接使用 `reason`，**无需**调整 `pyproject.toml`。

**不新增任何 pip / Action / 系统依赖**；脚本只用 stdlib + numpy + pandas。

### 2.2 文件结构

**修改**

| 文件 | 改动 | 行数 |
|------|------|------|
| `tests/test_distillation_isolation.py` | 新增 `GURU_DIR` 常量；5 处替换 | +4 / -5（实测 +9/-5：4 行常量块 + 5 处替换） |
| `tests/test_numba_jit_performance.py` | `import pytest` + 模块级 `importorskip` | +4 |
| `.github/workflows/tests.yml` | 安装后、测试前插入 1 个 step | +3 |
| `docs/PROGRESS.md` | §3.6 执行序回写（Step 9 / Step 10 行） | +1~2 |
| `docs/DESIGN_ci_test_env.md` | Step 5 规划期修正（C-1/C-2，见 §2.7） | 注记 |

**新增**

- `scripts/prepare_test_fixture.py`（本批唯一新增代码，137 行实测）
- `docs/{RESEARCH,DESIGN,IMPL,CHECKLIST}_ci_test_env.md`（四文档）

**零改动（交付前断言）**：`core/`、`filter/`、`tools/`、`examples/`、`pyproject.toml`、`.gitignore`、`README.md`、`scripts/prepare_test_data.py`。

### 2.3 接口签名与实施细节

#### 2.3.1 函数契约

| 符号 | 签名 | 职责 | 约束 |
|------|------|------|------|
| `REPO_ROOT` | `Path` | `Path(__file__).resolve().parents[1]` | 模块常量；不依赖 cwd（S3） |
| `DEFAULT_OUT_DIR` | `Path` | `REPO_ROOT / "data" / "test_ashare"` | 默认输出目录 |
| `TARGET_FILES` | `tuple[str, ...]` | `("close.pkl","open.pkl","high.pkl","low.pkl","stock_adj.pkl","suspend.pkl","industry.pkl")` | 顺序固定，供覆盖检查与输出打印 |
| `_resolve_out_dir(raw: str) -> Path` | 相对路径按 `REPO_ROOT` 解析，绝对路径原样 | 避免 cwd 耦合 | — |
| `existing_targets(out_dir: Path) -> list[Path]` | 返回已存在的目标 pkl | 覆盖保护检测 | 只读，不写 |
| `generate_fixture(out_dir, n_stocks=50, n_days=100, seed=42, start="2024-01-02") -> list[Path]` | 生成并写入 7 个 pkl，返回写入路径列表 | 纯生成 | 不含覆盖检查（由 `main` 负责） |
| `main(argv: list[str] \| None = None) -> int` | 解析参数 → 校验 → 覆盖检查 → 生成 → 打印 | CLI 唯一入口 | 退出码 0/1/2（见下） |

#### 2.3.2 CLI 与退出码

| 参数 | 默认 | 校验 |
|------|------|------|
| `--out-dir` | `DEFAULT_OUT_DIR` | 相对路径按 `REPO_ROOT` 解析 |
| `--n-stocks` | 50 | `< 31` → exit 1 |
| `--n-days` | 100 | `< 51` → exit 1 |
| `--seed` | 42 | int |
| `--start` | `2024-01-02` | `pd.bdate_range` 可解析 |
| `--force` | False | flag；缺省时已有目标 pkl → exit 2 |

**退出码**：`0` 成功；`1` 参数非法；`2` 目标已存在且未 `--force`（打印清单，**不写任何文件**）。

> 注（F-I2）：argparse 自身的 usage 错误（如 `--n-stocks abc`）也以 exit 2 终止（Python 标准行为），与覆盖保护同码；两者输出可区分（argparse 打印 `usage:` 到 stderr）。CI 为固定无参调用，不受影响。

#### 2.3.3 生成算法（规划期已在 `%TEMP%` 预演，27 项全过）

以下代码为 T-1 的逐字实现（探针 `gen_probe.py` 已验证，见 §2.5 V1）：

```python
def generate_fixture(out_dir, n_stocks=50, n_days=100, seed=42, start="2024-01-02"):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n_days)
    codes = [f"{i:06d}" for i in range(1, n_stocks + 1)]

    # 价格：GBM 对数收益，clip ±5%（< limit_up_threshold 0.095）
    mu = rng.uniform(0.0, 0.0008, n_stocks)
    sigma = rng.uniform(0.012, 0.030, n_stocks)
    log_ret = rng.normal(mu, sigma, (n_days, n_stocks))
    log_ret = np.clip(log_ret, -0.05, 0.05)
    log_ret[0] = 0.0
    p0 = rng.uniform(8.0, 60.0, n_stocks)
    close = p0 * np.exp(np.cumsum(log_ret, axis=0))

    # OHLC 自洽（high ≥ max(o,c)，low ≤ min(o,c)）
    noise = rng.uniform(0.995, 1.005, (n_days, n_stocks))
    open_ = np.roll(close, 1, axis=0) * noise
    open_[0] = close[0] * rng.uniform(0.995, 1.005, n_stocks)
    high = np.maximum(open_, close) * rng.uniform(1.0, 1.02, (n_days, n_stocks))
    low = np.minimum(open_, close) * rng.uniform(0.98, 1.0, (n_days, n_stocks))

    frames = {
        "close.pkl": close,
        "open.pkl": open_,
        "high.pkl": high,
        "low.pkl": low,
        "stock_adj.pkl": np.ones_like(close),
        "suspend.pkl": np.zeros((n_days, n_stocks), dtype=int),
        "industry.pkl": np.ones((n_days, n_stocks), dtype=int),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, arr in frames.items():
        path = out_dir / name
        pd.DataFrame(arr, index=dates, columns=codes).to_pickle(path)
        written.append(path)
    return written
```

**预演读数（E1，`%TEMP%\p009_algo_probe`）**：7 个 `(100, 50)`、索引 `2024-01-02 ~ 2024-05-20`、0 NaN、列 `000001`；价格 7.6411–74.9879；收益 −0.0488–0.0513；OHLC 违规 0/0/0；`adj=[1.]`、`suspend=[0]`、`industry=[1]`；合计 296037 B。**隔离目录跑 27 项 → `27 passed in 12.06s`**。

**顺序敏感**：`rng` 调用顺序决定数值。Step 9 不得重排调用（如把 `noise` 提到 `close` 之前），否则预演结论失效。

#### 2.3.4 数据契约（与断言映射）

| 文件 | 形状 | 值约束 | 被覆盖断言 |
|------|------|--------|------------|
| `close.pkl` | `100×50` | 正值 GBM，日收益 ∈ [−0.05, 0.05] | strict 01/02/04；backtest 02/03 |
| `open.pkl` | 同上 | `roll(close,1)·U(0.995,1.005)`，首行为 `close[0]·U` | strict 01 |
| `high.pkl` | 同上 | `max(o,c)·U(1.0,1.02)` | strict 01 |
| `low.pkl` | 同上 | `min(o,c)·U(0.98,1.0)` | strict 01 |
| `stock_adj.pkl` | 同上 | 恒等 `1.0`（float64） | strict 03（容差 1e-6） |
| `suspend.pkl` | 同上 | 恒等 `0`（int） | `UniverseFilter` 全可买 |
| `industry.pkl` | 同上 | 恒等 `1`（int） | `neutralize=False`，不参与 |

### 2.4 性能注意事项与低效排除表

| 禁止的操作模式 | 原因 | 替代做法 |
|----------------|------|----------|
| 在仓库 `data/test_ashare` 上直接跑默认路径生成 | 覆盖本地真实夹具（P14 事故重演，R8） | Step 9 一律用 `--out-dir %TEMP%\...`；默认路径**只验证 exit 2**（不写入） |
| 把合成 pkl 提交 / 缓存 / 跨环境复用 | pandas 官方：`read_pickle` 仅保证当前与上一大版本兼容（S12） | CI 每次 job 内生成即读（同环境，零风险）；不入库、不做 cache |
| 在断言中写合成数据的具体数值 | NumPy `Generator` 仅在「同 build / 同环境 / 同机器」保证流一致（S11） | 只断言结构恒等与统计阈值（现行 27 项断言均属此类，已核） |
| 为跨机逐字节复现改用 `RandomState` | 旧 API，无必要 | 本批不依赖逐字节一致；若未来需要再评估 |
| 在 `tests/conftest.py` 自动生成夹具 | 隐藏副作用、本地静默覆盖（DESIGN D2 被拒③） | 显式 CI step + 显式脚本 |
| 给 CI step 加 `\|\| true` / `continue-on-error` | 掩盖失败 | 如实 red |
| 用 `git add -f` 提交 pkl | 破坏 `data/` 约定 + 触发 gitignore 负模式陷阱（RESEARCH R9） | CI 生成 |
| 每次编辑后跑全量 pytest | 单次约 33 秒 | 编辑期只跑 V1-V5 毫秒级断言；全量仅 T-5 一次 |
| 用 `findstr` 匹配中文 | 本机 cp65001 下失配（P-008 R7） | 断言脚本用 Python `open(encoding="utf-8")` |
| 反复在 `%TEMP%` 与仓库间切换 cwd | 易误判路径解析 | 探针脚本内绝对路径；仓库命令显式 `cwd` |

### 2.5 测试策略与验证断言

| 编号 | 类型 | 断言 | 时点 |
|------|------|------|------|
| V0 | RED（数据） | 空目录（无 `data/test_ashare`）跑两个数据测试文件 → `9 failed, 18 errors`（与 CI run `41970636863` 同型） | T-0 |
| V0b | RED（静态） | `Grep "F:.Coding.Factor_Trading_v3.0.gurus" tests/test_distillation_isolation.py` → **5 处**；`test_numba_jit_performance.py` 无 `importorskip`；`tests.yml` 无 `Prepare test fixture` | T-0 |
| V1 | 生成契约 | `--out-dir %TEMP%\p009_green\data\test_ashare` 生成 → 7 文件 `(100,50)`、0 NaN、`adj≡1`/`suspend≡0`/`industry≡1`、OHLC 违规 0、收益 ∈ ±0.05、总字节 ≈296 KB（`data` 子目录层级不可省，F-I1） | T-1 |
| V2 | 覆盖保护 | 仓库根跑 `python scripts/prepare_test_fixture.py`（默认路径已有真实夹具）→ **exit 2**，且 `data/test_ashare` 各 pkl 的 `LastWriteTime`/长度不变 | T-1 |
| V2b | 数据测试 | cwd = `%TEMP%\p009_green`（其下须有 `data/test_ashare`，由 V1 的 out-dir 保证——`data_dir=Path("data/test_ashare")` 按 cwd 解析）跑两个数据测试文件 → `27 passed`（不得 skip） | T-1 |
| V3 | 路径静态断言 | `Grep "F:.Coding.Factor_Trading_v3.0.gurus"` → **0 处**；`GURU_DIR` 定义 1 处、引用 5 处；`python -m pytest tests/test_distillation_isolation.py -q` → 全 passed | T-2 |
| V4 | numba 静态+行为 | 文件含 `pytest.importorskip("numba")` 且位于 `sys.path.insert` 之后；本地 `pytest tests/test_numba_jit_performance.py -q` → `7 passed`；模块级 skip 语义由探针证明（3 测试模块 → `1 skipped`） | T-3 |
| V5 | CI YAML | `yaml.safe_load`：`steps` 长度 6→7；新增 step 索引为 `Run tests` 之前；`name == "Prepare test fixture"`；`run == "python scripts/prepare_test_fixture.py"`；`env.MPLBACKEND` 与 `Run tests` 命令逐字不变 | T-4 |
| V6 | 全量回归 | `$env:MPLBACKEND='Agg'` + Python312 `-m pytest tests -q` → `509 passed`（本地有 numba） | T-5 |
| V7 | 远端 | **不执行**；结论标 `[未在远端执行]` | — |

**边界与反例覆盖**

| 边界 | 反例形态 | 拦截断言 |
|------|----------|----------|
| 覆盖本地夹具 | 无 `--force` 却静默写入 | V2（exit 2 + mtime 不变） |
| 参数过小 | `--n-stocks 10` | exit 1；V1 只测默认 |
| 夹具缺字段 | 只生成 close/open | V1 断言 7 个文件名齐全 |
| adj 非恒等 | 复用 `demo.py` 的除权逻辑 | V1 `np.unique(adj)==[1.]` |
| 收益超涨停阈值 | 未 clip 或 sigma 过大 | V1 `max|returns| ≤ 0.05`；V2b `27 passed` |
| 路径仍硬编码 | 只改 3 处 | V3 计数 0 |
| importorskip 位置错误 | 写在函数内 | V4 断言位于 `sys.path.insert` 后、首个 def 前 |
| CI step 顺序错 | 放在 `Run tests` 之后 | V5 索引顺序 |
| 顺手改 mypy step | 删 `\|\| true` | V5 逐字比对 |

### 2.6 红→绿执行序（Step 9）

1. **T-0 RED**：
   - 建 `%TEMP%\p009_red`（空目录），cwd 指向它，跑两个数据测试文件 → 记录 `9 failed, 18 errors`（V0）；
   - 跑 V0b 静态断言 → 记录 `5 处硬编码 / 无 importorskip / 无 fixture step`。
2. **T-1**：创建 `scripts/prepare_test_fixture.py`；
   - `--out-dir %TEMP%\p009_green\data\test_ashare` → V1 GREEN（`data` 子目录层级不可省，F-I1）；
   - cwd = `%TEMP%\p009_green` 跑两个数据测试文件 → V2b `27 passed` GREEN；
   - 仓库根跑默认命令 → V2 `exit 2`，并比对 `data/test_ashare` 未被改写（**R8 防护正面验证**）。
3. **T-2 / T-3 / T-4**：连续编辑三文件 → V3 / V4 / V5 GREEN。
4. **T-5**：全量 V6 + `gate unit-tests`（pass 入流）+ `black-check` / `mypy-check`（核对基线 75 / 168 不漂移）。
5. **T-6**：回写 PROGRESS；删除 `%TEMP%` 探针目录；`git status --short` 确认仅 4 个目标文件变更。

**本地不可复现项（诚实标注）**：

| 项 | 原因 | 替代证据 |
|----|------|----------|
| 5 处硬编码路径的**运行时** RED | Windows 本地该路径存在，测试通过 | V0b 静态计数（5 → 0） |
| numba 缺失的**运行时** skip | 本地已装 numba 0.65.1 | 探针实测模块级 skip 语义（`1 skipped`）+ 远端 CI 读数 `[未在远端执行]` |
| CI `Prepare test fixture` 的真实执行 | 未 push | V5 YAML 结构断言 + V1/V2b 本地等价执行 |

### 2.7 对 DESIGN 的规划期修正

| ID | 修正 | 依据 |
|----|------|------|
| C-1 | CI 预期由 `502 passed, 7 skipped` 改为 **`502 passed, 1 skipped`**：模块级 `importorskip` 是 collection 级 skip，整个模块只计 **1 个 skipped**（模块内 7 项不单独计数）。已同步 DESIGN §1.1 / §3.3 C / §3.4 / §6 / §11（F-S1 补列 §11） | E1 探针（pytest 9.0.3：3 测试模块 → `1 passed, 1 skipped`） |
| C-2 | DESIGN §6「numba 损坏（非 ImportError）不兜底」表述不成立：`pytest.importorskip` 默认 `exc_type=ImportError`，numba 因 NumPy 版本不匹配抛 `ImportError` 时**亦会 skip**。已改为「已知语义边界；区分需 `exc_type=ModuleNotFoundError`（pytest ≥8.2）或手写 try，本批不做，归 U-008」 | S1（pytest 文档）+ S5（numba Discourse 同型 ImportError 案例，T2）+ S10（`exc_type` 由 8.2 引入） |

## 3. 回退点

| 层级 | 动作 |
|------|------|
| 单 Task | `git restore tests/test_distillation_isolation.py` / `tests/test_numba_jit_performance.py` / `.github/workflows/tests.yml`；T-1 删除 `scripts/prepare_test_fixture.py` |
| 整批（提交前） | 上述 restore + 删除新增脚本与四文档 + 还原 PROGRESS |
| 整批（提交后） | `git revert <commit>` |
| 运行态 | 无残留：脚本不写环境变量/缓存；本地真实夹具从未被改写（V2 证明）；`%TEMP%` 探针在 Step 9 末删除（Step 5-6 期间保留作预演证据） |

## 4. 锚点表（§11.3 Step 5 要求）

> 本批新增外部检索（S10-S15），用于**实施层**契约；设计层锚点（S1-S9）沿用 [RESEARCH](RESEARCH_ci_test_env.md)。T3/T4 只作实践佐证，机制依据仍为 T1。

| 契约项 | 锚点 | 等级 | 版本 / 日期 | 适用性 |
|--------|------|------|-------------|--------|
| `importorskip(reason=)` 可用性 | S10 pytest changelog #4599 | T1 | 4.6.0；访问 2026-11-05 | 项目下限 `>=7.4` 安全；本机 9.0.3 实测可用 |
| 模块级 skip 计数语义 | E1 探针 | E1 | pytest 9.0.3；2026-11-05 | 3 测试模块 → `1 skipped`；C-1 依据 |
| 默认 `exc_type` | S1 pytest skipping + S5 numba Discourse | T1 / T2 | 访问 2026-11-05 | 默认捕获 `ImportError`；numba/NumPy 不匹配案例属 S5（T2 单源） |
| `Generator` 流兼容边界 | S11 NumPy Compatibility policy | T1 | 访问 2026-11-05 | 仅同 build/环境/机器保证；故断言不写具体数值 |
| pickle 跨版本兼容 | S12 pandas `read_pickle` | T1 | 3.1.0；访问 2026-11-05 | 仅保证当前与上一大版本；CI 同环境生成即读，零风险 |
| CI step 默认工作目录 | S13 GitHub Actions Variables reference | T1 | 访问 2026-11-05 | `GITHUB_WORKSPACE` 为 steps 默认 cwd = 仓库根；脚本 `REPO_ROOT` 双保险 |
| 可选依赖用 `importorskip` 保绿 | S14 Custos CONTRIBUTING | T3 | 访问 2026-11-05 | 「`importorskip`-guarded so the suite stays green in a runtime-only install」——同型实践，仅线索 |
| CI 中先造合成数据再跑集成测试 | S15 fakeforge / dev.to 合成数据 CI 指南 | T4 | 访问 2026-11-05 | 思路与 A1 同型；该案例用 cache 复用数据集，本仓**不采纳**（单次生成更简单）。已回溯 S13（cwd）+ E1（V1/V2b 实测） |

**社区案例锚点小结**：S14 支撑「可选依赖不应让整套件变红」的实践共识；S15 支撑「CI 内生成测试数据再跑集成测试」的可行性，但其 cache 复用方案与本仓 gitignore/pickle 兼容边界冲突，故只取思路不取实现。所有 T3/T4 均未单独作为结论依据。

## 5. Review 记录（Step 6）

- **时点**：2026-11-05，本文档完稿（Step 5）之后的独立 pass；未与正文同一次写入（RULE-1）
- **审查者**：单 Agent 自查（单视角）（RULE-4）；本批未引入第二会话或异构基座
- **审查方式**：重跑 E1 版本 / 行号读数 + 读回 [DESIGN](DESIGN_ci_test_env.md) / [RESEARCH](RESEARCH_ci_test_env.md) 交叉核对 + 对照 `F:\Spec_Workflow\SPEC_PROCESS.md` Step 6 检查单与 `docs/SPEC_STANDARD.md` Phase 2 检查点

**检查项与结果**：

| 检查项（来源） | 结果 |
|----------------|------|
| 依赖版本真实存在（Step 6） | 通过：Python 3.12.10 / pytest 9.0.3 / numpy 2.4.6 / pandas 2.2.3 / PyYAML 6.0.3 / numba 0.65.1 重跑确认（E1） |
| stdlib API 下限（Step 6） | 通过：`inspect.signature(pytest.importorskip)` 运行时证实含 `reason` / `exc_type`（本机 9.0.3）；S10 锚点 4.6.0 ≪ 项目下限 7.4 |
| API 签名可实现（Step 6） | 通过：§2.3.1 七个符号均可实现；§2.3.3 算法已在探针逐字验证（27 passed in 12.06s） |
| 无虚构的库或函数（Step 6） | 通过：仅 numpy / pandas / pytest / argparse / pathlib；无新增 pip 依赖 |
| 兼容性声明已验证（Step 6） | 通过：S12 pickle 边界转化为「CI 同环境生成即读」约束；`pyproject.toml` / `.gitignore` / `prepare_test_data.py` 零改动 |
| 低效操作已排除（Step 6 / Phase 2） | 通过：§2.4 十条禁止模式，非空且含本仓特化项（P14 覆盖、findstr 中文、rng 顺序） |
| 文件路径存在或计划创建（Phase 2） | 通过：三个目标文件均存在；`scripts/` 目录存在 |
| 每 Task 有文件 + 验证 + 行数（Phase 2） | 修复后通过：F-I3（PROGRESS 行数标注 +1 → +1~2） |
| 测试覆盖（Phase 2） | 通过：V0-V7 八段断言 + 边界反例 9 项 |
| **断言可重放**（Phase 2） | 修复后通过：F-I1 揭示 V1/V2b 路径错位——照原文执行 V2b 将得 `9 failed, 18 errors` 而非 `27 passed`；已修正 |

**发现并修复（3 项：1 项 P2 + 2 项 P3）**：

| ID | 级别 | 发现 | 修复 |
|----|------|------|------|
| F-I1 | **P2** | §2.5 V1 写 `--out-dir %TEMP%\p009_green`，而 V2b 又以 `%TEMP%\p009_green` 为 cwd——两个数据测试文件的 `data_dir=Path("data/test_ashare")` 按 **cwd** 解析，照原文执行会在 cwd 下找 `data/test_ashare`（不存在）→ 得到 `9 failed, 18 errors`，V2b 断言必然失败。规划期探针实际生成路径为 `p009_algo_probe\data\test_ashare`（E1：`%TEMP%` 探针目录现存结构证实，含 `output\` 运行痕迹），文档字面与实际执行不符 | V1 / V2b / §2.6 step 2 三处统一为 `--out-dir %TEMP%\p009_green\data\test_ashare`，并注明 `data` 子目录层级不可省 |
| F-I2 | P3 | 退出码 2（覆盖保护）与 argparse usage 错误的默认退出码 2 **撞码**（Python 标准行为）；§2.3.2 未声明 | 退出码表加注：两者输出可区分（argparse 打印 `usage:` 到 stderr）；CI 为固定无参调用，不受影响 |
| F-I3 | P3 | §2.2 PROGRESS 行数标 `+1` 不准：Step 5 已回写 1 行，Step 9 还将回写 Step 9/10 行 | 改为 `+1~2` |

**复核结果（E1 重跑，2026-11-05）**：

| 断言 | 复核命令 | 结果 |
|------|----------|------|
| pyproject pytest 行号 | `Select-String "requires-python\|pytest"` | L10 / L54（dependencies）/ L62（dev extras）（与 §2.1 一致） |
| 版本六元组 | Python312 `-c "import sys, numba, pytest, ..."` | `3.12.10 / 0.65.1 / 9.0.3 / 2.4.6 / 2.2.3 / 6.0.3`（与 §2.1 一致） |
| `importorskip` 签名 | `inspect.signature(pytest.importorskip)` | `['modname', 'minversion', 'reason', 'exc_type']`（S10 + C-2 运行时证实） |
| 规划期算法探针留存 | `%TEMP%\p009_algo_probe` 列目录 | `gen_probe.py` + `data/test_ashare/` 7 pkl + `output/` 7 产物（27 项运行痕迹；F-I1 路径结构证据） |
| 模块级 skip 探针留存 | `%TEMP%\p009_skip_probe` 列文件 | `test_skip_mod.py` + `test_normal.py`（C-1 依据留存） |
| §2.3.3 与 `gen_probe.py` 一致性 | 逐行比对 | 一致（frames 顺序、rng 调用序、clip ±0.05、ones/zeros dtype） |
| V5 steps 计数前提 | 读回 `tests.yml` | 现存 6 steps（checkout/setup-python/cache/install/Run tests/mypy），+1 = 7（与 §2.5 V5 一致） |

**结论**：无 P1；1 项 P2 + 2 项 P3 已修复；Step 6 闸门通过，可进入 Step 7 验收清单。

> **门禁记录（2026-11-05）**：session `factorv3-p009-ci-env-20261105`，`step-implement-review` pass（门禁命令用 ASCII 模式串，规避 P-008 §4 R7 findstr 中文陷阱）。
