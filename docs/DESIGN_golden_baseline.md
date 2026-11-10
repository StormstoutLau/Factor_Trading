# P-013 Golden 基线固化（L4 判据）· 设计（Step 3）

> **文档编号**: DESIGN_golden_baseline
> **阶段**: Phase 2 - 设计（T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 3 完稿，待 Step 4 Review
> **上游**: [RESEARCH_golden_baseline.md](RESEARCH_golden_baseline.md)（P1-P10 事实 / 约束 1-5 / 方案 A-A-A / U-G1~U-G4）
> **下游**: IMPL（T 任务）· CHECKLIST（验收项）
> **证据时点**: `6f583fc`；Python 3.12.10
> **档位**: T1

---

## 1. 设计目标与非目标

**目标**：为 6 条代表性回测场景固化「当前行为」基线，使任何未预期的行为漂移在本地与 CI（3.10/3.11/3.12）同时可被发现。

**非目标**（A20 边界，写入文档与测试 docstring）：
- 不证明正确性——正确性由 P-011 的 L1-L3（不变量 / 参考实现差分 / 事件级等价）承担；
- 不与外部框架对拍（U-4 / X-B 另行立项）；
- 不改任何 `core/` 生产代码；
- 不引入运行时依赖（仅标准库 `json` + 已有 `numpy`/`pandas`）。

## 2. D1 不变式（I1-I6）

| ID | 不变式 | 校验方式 |
|----|--------|----------|
| **I1** | 基线 JSON 必须严格可解析且不含 `NaN`/`Infinity`（非标准 JSON） | 读回 `json.loads` + 递归检查有限性 |
| **I2** | 同 commit + 同夹具重跑 → 各字段在容差内一致（可重现） | 连续两次录制 diff 为 0（E2） |
| **I3** | 容差不得宽于本设计表（`rtol ≤ 1e-9`） | 测试断言 `baseline["tolerance"]["rtol"] <= 1e-9` |
| **I4** | 测试**只读**基线，绝不写回 | 测试目录以只读方式打开；CI 中基线文件 mtime 不变 |
| **I5** | 6 条 case（G1-G6）必须齐全，缺任一即 fail | 测试收集 `golden/*.json` 并比对 case_id 集合 |
| **I6** | 每份基线必须内嵌 `schema_version` 与 `git_commit` | 逐文件字段断言 |

## 3. D2 基线 JSON Schema（v1.0）

```json
{
  "schema_version": "1.0",
  "case_id": "G1",
  "engine": "v2",
  "scenario": "baseline",
  "description": "V2 基础：常量价、零费用、5 日 × 2 股",
  "recorded_at": "2026-11-10T12:00:00+08:00",
  "git_commit": "6f583fc",
  "python_version": "3.12.10",
  "numba_available": true,
  "tolerance": { "rtol": 1e-9, "atol": 1e-12, "money_atol": 1e-6 },
  "config_fingerprint": "<sha256 of canonical config json>",
  "metrics": {
    "total_return": 0.0,
    "annual_return": 0.0,
    "annual_volatility": 0.0,
    "sharpe_ratio": 0.0,
    "max_drawdown": 0.0,
    "final_value": 10000000.0
  },
  "nav": { "length": 5, "first": 10000000.0, "last": 10000000.0, "min": 10000000.0, "max": 10000000.0 },
  "trades": { "count": 2, "total_amount": 0.0, "total_cost": 0.0 }
}
```

- `engine` ∈ `{v2, v3}`；`scenario` ∈ `{baseline, cost, mask, delisting}`。
- `config_fingerprint` / `data_fingerprint` 采用 `core.manifest._canonical_json` + sha256 口径，**只记录不硬比对**（U-G4=B），用于失败时人工判断「是代码变了还是配置变了」。
- `numba_available` 仅记录（本地 true / CI false），**不参与断言**。

## 4. D3 容差表（U-G1 分字段）

| 字段类别 | rtol | atol | 依据 |
|----------|------|------|------|
| 金额（`nav.*`、`final_value`、`trades.total_amount/cost`） | `1e-9` | `1e-6` | 1e7 量级 × 1e-9 = 0.01 元；覆盖 numba/py_func 末位差（F-S9-2 实测 ≈1e-10 相对） |
| 收益率/比率（`total_return`/`annual_*`/`sharpe`/`mdd`） | `1e-9` | `1e-12` | 无整数约束 |
| 计数（`nav.length`、`trades.count`） | 0（精确） | 0 | 结构性字段，不容忍漂移 |
| `metrics_method` / `risk_free_rate` | 精确 / `1e-12` | — | 口径声明不得悄悄变化 |

> **禁止**：为让测试变绿而放宽 `rtol`——I3 强制上限。若某字段确实需要更宽容差，须在 DESIGN 中登记理由并升级 `schema_version`。

## 5. D4 六条 case 定义

所有夹具均为**代码构造 + 写入 `tmp_path`**，零外部数据。

| ID | 引擎 | scenario | 规模 | 价格构造 | 关键配置 | 覆盖的口径 |
|----|------|----------|------|----------|----------|-----------|
| **G1** | V2 | baseline | 5 日 × 2 股 | 常量 `[[10, 25]]` | 四项费用全 0、`enable_pending_orders=False`、`round_lot=True`、`target_count=2` | T+1 开盘 + 整手 + 0.985 缓冲 |
| **G2** | V2 | cost | 20 日 × 3 股 | 确定性公式（`10 + 0.1*sin(i)`，逐股偏移） | 佣金万 3/下限 5、印花税 0.1% 单边、滑点 0.1% | 费用四项 + 整手 |
| **G3** | V2 | mask | 20 日 × 3 股 | 第 10 日某股整段上移至 `close(9) × 1.10`，使 `open == close(9) × 1.10`（真实涨停且价格连续） | `exclude_limit_up=True`、`limit_check_price="open"` | 涨跌停掩码（**停牌场景不在本批**：实施期发现 V2 停牌路径账目缺陷，见 F-S9-G1） |
| **G4** | V3 | baseline | 5 日 × 2 股 | 同 G1 | `top_n=2`、`rebalance_freq=1`、`cost_rate=0` | 同日收盘 + 无缓冲 |
| **G5** | V3 | cost | 20 日 × 3 股 | 同 G2 | `cost_rate=0.001` | 对称成本 |
| **G6** | V2 | delisting | 20 日 × 3 股 | 同 G2 + universe CSV | `universe/{list_date,delist}`：某股 `delist_date` = 第 15 日 | 动态池移除（P-012 B5） |

> G4 与 G1 的 NAV 在常量价 + 零费用下应逐日相等——这是**已知结论的回归锁**，不是新断言。
> **口径修正（F-S9-G4）**：V2 末日强平会追加同日第二次快照（既有行为 F-S9-3），故 `nav.length` 为 6 而 V3 为 5；跨引擎比较口径为 **`first/last/min/max` 相等**，不含长度。
> **停牌场景撤出（F-S9-G1，P1）**：G3 初版含停牌，实测触发 5 项 I2 违规（停牌日仍成交 + 恢复日重复记账致负持仓 -109500）。该缺陷不在本批修复范围，G3 仅保留涨停掩码，缺陷另立批次。

## 6. D5 夹具能力扩展（`tests/_synth_fixture.py`）

**D5.1 独立 OHLC（向后兼容）**

```python
def write_price_fixture(
    out_dir, dates, codes, prices, *,
    open_prices=None, high_prices=None, low_prices=None,   # 新增，默认 None → 复用 prices
    adj=1.0, suspend=0, st=0, with_industry=True,
) -> Path: ...
```

- 默认行为与现状**完全一致**（现有 4 处调用零改动）；
- `suspend` / `st` 由标量升级为可接受 `int | Sequence[int] | np.ndarray`（复用 `_as_matrix` 的容错逻辑，仅整型化），默认标量→现状不变。

**D5.2 universe 写入**

```python
def write_universe(out_dir, list_rows, delist_rows, *, manifest=True) -> Path: ...
```

- 格式严格对齐 `core/universe_data.load_universe_snapshot`：`universe/list_date.csv`（`stock,list_date`）、`universe/delist.csv`（`stock,delist_date,delist_return`）、`universe/manifest.json`。

## 7. D6 录制脚本（`scripts/record_golden.py`）

```
python scripts/record_golden.py [--case G1 ...] [--force]
```

- 默认**要求工作区干净**（U-G2=A）：`git status --porcelain` 非空则拒绝，`--force` 可覆盖（并在 JSON 里记 `dirty=True`）；
- 拒绝在 `CI=true` 环境录制（防止用 CI 的 `py_func` 结果覆盖本地）；
- 输出到 `tests/golden/{case_id}.json`，并对每个 case 打印 `metrics`/`nav`/`trades` 摘要供人工核对（防误录）；
- 退出码：0 成功 / 1 前置失败 / 2 录制结果含非有限值。

## 8. D7 测试（`tests/test_golden_baseline.py`）

- `pytest.mark.parametrize` 覆盖 6 个 `case_id`，另加 1 个「集合完整性」用例（I5）与 1 个「schema 合法性」用例（I1/I6）；
- 失败信息格式（U-G3=A）：
  `[G2] metrics.sharpe_ratio: expected=-1.443001234 got=-1.443102345 rel_err=7.0e-05 (rtol=1e-09)`
- 读基线为**只读**（I4）；
- **case 构造器单一来源**：6 个 case 的夹具与引擎调用统一放在 `tests/_golden_cases.py`，由录制脚本与断言测试**共同 import**。测试不得 import `scripts/*`（保持测试不依赖脚本目录），脚本可以 import `tests/_golden_cases.py`。此约束防止「录制用夹具 A、断言跑夹具 B」的静默漂移。

## 9. D8 CI 集成

- **不改 workflow**：`pytest tests` 会自然收集新测试；JSON 随 checkout 入仓；
- CI 走 `py_func`、本地走 `@njit`，同一份基线由容差（D3）吸收差异；
- 若 CI 红而本地绿，README/注释指引：先看 `numba_available` 字段，再按 D7 报错格式定位字段。

## 10. D9 批次划分

| 批次 | 内容 | 行为变更 | 提交 |
|------|------|----------|------|
| **B1** | 夹具能力扩展（D5）+ 6 项夹具单测（含向后兼容用例） | 否（仅测试辅助新增能力） | 1 |
| **B2** | 录制脚本（D6）+ 6 基线 JSON（D4）+ 测试（D7） | 否（生产代码零改动） | 1 |

## 11. D10 范围与风险

| 项 | 处置 |
|----|------|
| 基线误录（把错误行为固化） | 录制需工作区干净 + 打印摘要 + 人工核对；文档声明 golden 不证正确性（A20） |
| 数据/配置漂移导致假失败 | 合成夹具（无外部数据）+ 指纹只记录不比对（U-G4=B） |
| numba 双路径差异 | 分字段容差（D3），并由 CI 三版本实测验证 |
| 基线随实现漂移被悄悄更新 | 基线变更必须在 commit message 与 PROGRESS 登记；`git diff tests/golden/` 是 review 重点 |
| 未来引擎行为变更 | 变更方必须**先**说明基线 diff 的合理性，再更新基线（与 P-011 §7.2 建议一致） |

## 12. Step 4 设计 Review 结论（2026-11-10）

**审查基座**: 本会话 DeepSeek-V4.1-Flash（同基座；异构 RULE-5 留待独立会话）

| 待验设计假设 | 方法 | 结果 |
|--------------|------|------|
| G3 涨跌停可触发 | E3 读 `universe_filter_clean.py:215` + `limit_rules.py:130-148` | ✅ `limit_up = close(t-1) × adj(t-1)/adj(t) × 1.10`，`adj=1` 时即 `close(t-1)×1.10`；判定 `open >= limit_up - EPS_PRICE`，`EPS_PRICE=0.005` 足以兜住浮点边界 |
| G6 退市可触发 | E3 读 `data.py:165-174` + `universe_filter_clean.py:268-276` | ✅ `DataManager.universe` 懒加载 `load_universe_snapshot(data_dir, cfg.universe_dir)`，默认 `data_dir/universe`；夹具写入 `tmp_path/universe/` 即可生效 |
| V2 执行入口 | E3 读 `engine_v2.py:309` | ✅ `run() -> dict[str, Any]`，`setup()` @`:182` |
| 夹具扩展向后兼容 | E3 读 `_synth_fixture.py:32-66` | ✅ 新增参数均默认 `None`，现有 4 处调用（`test_cross_engine_equivalence.py` 等）零改动 |
| 涨跌停判定取价口径 | E3 读 `UniverseFilterConfig:35` | ✅ `limit_check_price: Literal["open","close"]="open"`（P-012 D4 价格法） |

**发现（1 项 P3，已回写）**

| ID | 等级 | 发现 | 处置 |
|----|------|------|------|
| F-D-G1 | P3 | §5 D4 中 G3 的价格构造未写明限价公式与 `EPS_PRICE` 容差，实施时可能因浮点边界导致「差 1 ulp 未触发」 | 已在 §12 记录精确条件：`open = close(t-1) × 1.10`（`adj=1`），判定阈为 `limit_up - 0.005`，构造无需额外放大 |

**结论**：P1=0 / P2=0 / P3=1（已回写）；设计可落地，**可进入 Step 5 IMPL**。
