# RESEARCH：P-027 静默失败治理第三批（core 外 22 处）

> **批次**: P-027 · **T1**（`agents/` / `filter/` / `scripts/` / `batch_backtest/` / `strategy_evaluation/` / `cli.py` 的 except 可观测性治理；零 fail-fast、零正常路径行为变更）
> **上游**: [RESEARCH_p026 §5 / §7](RESEARCH_p026_silent_exception_governance.md)（U-P026-3 触发判据与 22 处清单）；[PROGRESS §1.4](../PROGRESS.md)（U-P026-3 / U-P024-4）
> **Step**: **Step 1 取证**（RULE-1：本步只取证与判定，零代码改动）
> **日期**: 2026-11-15 · **基线 HEAD**: `10e0553`（台账补登后，工作区干净）
> **取证基座**: DeepSeek-V4.1-Flash

---

## 0. 结论摘要（TL;DR）

| 项 | 结论 |
|----|------|
| 触发条件「任一模块出现静默错误可复现实例」 | **成立**（C 类 2 处已 E2 探针复现：返回默认值 + 0 条日志） |
| 22 处分布 | 与 RESEARCH_p026 记载**逐项一致**：`agents/` 11 / `filter/` 5 / `scripts/` 2 / `batch_backtest/` 2 / `strategy_evaluation/` 1 / `cli.py` 1 |
| 与 U-P024-4 合并取证 | **不可合并**。当前环境 pandas **2.2.3**，`mypy --explicit-package-bases filter` = **10 source files, 0 error**；U-P024-4 触发条件（pandas 3.x）未成立，维持 pending |
| 建议 T1 范围 | C 类 2 处（补日志 + 计量）+ B 类中级别过低 1 处（`debug` → `warning`）；其余 B 类只补计量；E 类 4 处排除 |

---

## 1. 触发判据（来源 U-P026-3）

判据原文：「任一模块出现『静默错误』可复现实例」。本步将其拆为两个可判定要件：

| 要件 | 判定方式 | 通过条件 |
|------|----------|----------|
| 静态要件 | 读码：except 块内无 `logger.*`、无计数自增、无可读降级说明 | 三个特征同时缺失 |
| 动态要件 | 注入异常后观察返回值与 root logger 记录数 | 返回默认值 且 记录数 = 0 |

两要件同时满足 → 静默错误可复现 → 触发成立。

---

## 2. 取证方法

| 级别 | 手段 | 覆盖 |
|------|------|------|
| E1 | `Grep` 按目录逐文件计数（`except Exception`）+ 定位 | 22 处位置与分布 |
| E2 | `%TEMP%\p027_probe.py`：`logging.Handler` 捕获 + `monkeypatch` 注入异常 | C 类 2 处运行时复现 |
| E3 | 读码归类（绑定 commit `10e0553`） | 22 处形态分类 |
| E4 | `mypy filter` + `pandas.__version__` | U-P024-4 合并可行性 |

E2 探针要点：先 attach **DEBUG 级**捕获 Handler（确保低级别日志也会被计入），导入模块后清空记录，再对目标函数注入 `RuntimeError`，最后对比返回值与记录数。

---

## 3. 22 处全量清单

| # | 位置 | except 形态 | 分类 |
|---|------|-------------|------|
| 1 | `agents/agent_framework.py:924` | `warning` + 降级 `rotation_analyzer = None` | B |
| 2 | `agents/agent_framework.py:1074` | **`debug`** + `continue` | B−（级别过低） |
| 3 | `agents/agent_framework.py:1529` | `print` + `traceback`（脚本入口） | E |
| 4 | `agents/auto_parameter_optimizer.py:807` | `warning` | B |
| 5 | `agents/assumption_monitor.py:201` | **静默** `return 0.0, 1.0` | **C** |
| 6 | `agents/guru_agent_v2.py:72` | `error` | B |
| 7 | `agents/guru_agent_v2.py:491` | `error` | B |
| 8 | `agents/multi_strategy_engine.py:148` | `error` + `continue`（日级隔离） | B |
| 9 | `agents/multi_strategy_engine.py:233` | `error` + `return` | B |
| 10 | `agents/multi_strategy_engine.py:290` | `error` + `return` | B |
| 11 | `agents/research_team_v2.py:825` | `warning` | B |
| 12 | `filter/custom.py:71` | `error` + fail-open 全 True | B |
| 13 | `filter/custom.py:141` | `error` + fail-open 全 True | B |
| 14 | `filter/custom.py:269` | `error` + fail-open 全 True | B |
| 15 | `filter/custom.py:327` | `error` + fail-open 全 True | B |
| 16 | `filter/universe_filter_clean.py:371` | `error`（构建失败即无 mask） | B |
| 17 | `scripts/fetch_universe.py:100` | `print` warn + 回退 | E |
| 18 | `scripts/fetch_universe.py:118` | `print` skip + 指引 | E |
| 19 | `batch_backtest/engine.py:107` | `error` + `results[name] = {"error": ...}` | **A** |
| 20 | `batch_backtest/engine.py:167` | `error` + `results[param_id] = {"error": ...}` | **A** |
| 21 | `strategy_evaluation/stats.py:139` | **静默** `return np.nan` | **C** |
| 22 | `cli.py:136` | `print` + `sys.exit(1)` | E |

---

## 4. 分类统计

| 类 | 定义 | 处数 | 处置方向 |
|----|------|------|----------|
| **A** | 日志 + 结构化错误输出（调用方可读） | **2** | 保持，作为本批参照范式 |
| **B** | 有日志但无计量（不可统计故障频次）；含 1 处级别过低 | **14** | 只补计量（不新增日志、不改文案） |
| **C** | 完全静默：无日志、无计量、返回默认值 | **2** | **本批核心治理对象** |
| **E** | 进程/脚本边界：`print` + `exit`/回退指引 | **4** | 排除（面向人，非程序消费） |
| 合计 | — | **22** | — |

**关键判断**：`filter/custom.py` 4 处虽为 fail-open（返回全 True 掩码），但有 `error` 日志 —— 其风险不是"看不见"，而是**不可统计**（无法回答"本轮回测有多少只票因过滤函数异常而被放行"）。这决定了 B 类只需计量、不需改语义。

---

## 5. E2 复现结果（C 类 2 处）

探针 `%TEMP%\p027_probe.py` 输出（原文）：

```json
{
  "stats_calculate_half_life": { "return": "nan", "log_records": 0, "logs": [] },
  "assumption_kpss_test":   { "return": [0.0, 1.0], "log_records": 0, "logs": [] }
}
```

| 站点 | 注入 | 返回值 | 日志记录 | 判定 |
|------|------|--------|----------|------|
| `strategy_evaluation/stats.py:139` | `np.corrcoef` 抛 `RuntimeError` | `nan` | **0** | 静默可复现 |
| `agents/assumption_monitor.py:201` | `np.var` 抛 `RuntimeError` | `(0.0, 1.0)` | **0** | 静默可复现 |

补充语义风险（E3 读码）：
- `stats.py:139` 的 `np.nan` 与上游 3 处**合法早退**（样本不足 `L124` / `L131`、`rho` 越界 `L136`）返回同值 —— 调用方无法区分「样本不足」与「计算异常」，与本批 D8「位置 + 后果」口径冲突。
- `assumption_monitor.py:201` 的 `(0.0, 1.0)` 表示"平稳且不拒绝原假设"，是**乐观默认值**：计算失败会被误读为"假设成立"，属于假阴性方向的静默失败。

---

## 6. U-P024-4 合并取证（结论：不可合并）

| 项 | 实测 | 说明 |
|----|------|------|
| `pandas.__version__` | **2.2.3** | U-P024-4 触发条件为「升级 pandas 3.x」 |
| `mypy --explicit-package-bases filter` | **Success: no issues found in 10 source files** | 21 errors / 7 files 不可复现 |
| 结论 | **维持 pending，不并入 P-027** | 两者轴不同（类型检查 vs 可观测性），且当前环境无 error |

修订：此前「可与 U-P024-4 合并取证」的判断**撤回**（依据不足，实测不符）。

---

## 7. 治理建议（供 Step 3 DESIGN 使用）

1. **C 类 2 处**（必做）：补 `logger.warning`（中文「位置 + 后果」）+ 计量字段，且**返回值语义不变**（仍 `nan` / `(0.0, 1.0)`），避免调用方分支变更。
2. **B 类 14 处**：仅补计量（模块级计数器或 `get_stats()`），文案与级别一律不动；`agent_framework.py:1074` 由 `debug` 提升为 `warning`（该处 `continue` 会静默丢一只票的投研结论）。
3. **A 类 2 处**：作为范式保留，零改动（可作为 DESIGN 的对照样例）。
4. **E 类 4 处**：排除，不做治理（面向人工诊断）。
5. **纪律**：本批**不引入 fail-fast**、不改任何既有返回值/掩码语义、不动 `core/`。

---

## 8. 风险与未决项

| ID | 风险 / 未决 | 处置 |
|----|-------------|------|
| R-P027-1 | `filter/custom.py` fail-open 全 True 掩码本身可能是设计缺陷（异常时反而放行全部标的） | 本批不改语义，登记观察 |
| R-P027-2 | 计量字段命名若与 `core/` 的 `_stats` 风格不一致，将增加认知成本 | Step 3 DESIGN 统一命名（`*_failures` 后缀） |
| R-P027-3 | 探针依赖 monkeypatch 全局 `np.*`，并发执行可能互相干扰 | 探针仅用于取证；Step 9 单测改用 `monkeypatch` fixture 局部替换 |

---

## 9. 下一 Step

Step 2 Review（本文件的证据可重放性、分类归属、U-P024-4 结论）→ 通过后进入 Step 3 DESIGN。
