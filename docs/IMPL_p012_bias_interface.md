# P-012 偏差防护与接口锁定 · 实施规划

> **文档编号**: IMPL_p012_bias_interface
> **阶段**: Phase 1 - 实施规划（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 5 完稿；**Step 6 Review 通过**（2026-11-10，独立 pass；2 P1 + 3 P2 + 5 P3 全部回写，见 §8）；**Step 7 起草期补记 F-S7-1/F-S7-2**（见 §2.2 / T-3 / T-6）；可进入 Step 7 CHECKLIST
> **上游**: [DESIGN_p012_bias_interface.md](DESIGN_p012_bias_interface.md)（Step 4 通过；D1-D11 / 不变式 I1-I9）
> **下游**: CHECKLIST_p012_bias_interface
> **证据时点**: 本仓读数 @ `05af52f`；HEAD `2c34283`；Python 3.12.10 / pytest 9.0.3 / black 26.5.0 / mypy 2.1.0
> **档位**: T1（`core/` 9 文件 = 3 新 + 6 改、`filter/` 2 文件、`scripts/` 3 文件、`tests/` 9 新文件）

---

## 1. 执行总览

### 1.1 任务分解

| ID | 任务 | 依赖 | 产出 | 批次 |
|----|------|------|------|------|
| T-0 | RED 基线（10 项读数）+ B1 测试 | — | §3.1 读数表 + `test_change_report.py` / `test_fixture_profile.py` | B1 |
| T-1 | 夹具双 profile（`--profile {baseline,biased}`） | T-0 | `scripts/prepare_test_fixture.py` | B1 |
| T-2 | 层 dump + `change_report`（引擎钩子 + 核心 + CLI） | T-1 | `core/change_report.py`、`scripts/change_report.py`、`engine_v2` 钩子 | B1 |
| T-3 | 规则表 `filter/limit_rules.py` | T-2 | 新模块 + `test_limit_rules.py` | B2 |
| T-4 | `UniverseFilter` 接入规则表 + ST 当日判定 | T-3 | `universe_filter_clean.py` | B2 |
| T-5 | 复权三口径 + 旧名别名 | T-4 | `data.py` `get_adj_price`、`data_v3.py:109` | B3a |
| T-6 | `PriceModeConfig` + 引擎取价切 raw + returns 口径 | T-5 | `config.py`、`engine_v2.py`（8 次 / 7 位置）、`data.py:_calculate_returns` | B3b |
| T-7 | 涨跌停价格法 + `next_day_tradable_mode` | T-6 | `universe_filter_clean.py`、`engine_v2.py` | B4 |
| T-8 | `UniverseSnapshot` 加载/降级 | T-7 | `core/universe_data.py` | B5 |
| T-9 | 上市/退市掩码 + 退市结算 | T-8 | `universe_filter_clean.py`、`engine_v2.py` | B5 |
| T-10 | `scripts/fetch_universe.py` 本地快照脚本 | T-9 | 新脚本（离线，`--refresh` 显式） | B5 |
| T-11 | 协议收窄 + `execute_order` 对齐 + `__api_version__` | T-10 | `interfaces.py`、`core/__init__.py` | B6 |
| T-12 | 契约测试 + `DataProvider` + D11 配置转换 | T-11 | `core/data_provider.py`、`test_contract_conformance.py`、`test_config_conversion.py` | B6 |
| T-13 | 全量验证 + 四文档 + 台账 + 提交 + CI | T-12 | — | — |

### 1.2 提交与批次映射

| 提交 | 任务 | 行为 | 归因要求 |
|------|------|------|----------|
| **B1** | T-0 + T-1 + T-2 | 零行为（dump 默认关） | 无 |
| **B2** | T-3 + T-4 | **行为**（ST 5%→10%、板块 20%/30%、ST 当日） | `change_report.json` |
| **B3a** | T-5 | **零数值**（同一公式改名） | 冻结基线 `rtol=0` |
| **B3b** | T-6 | **行为**（成交/估值切 raw） | `change_report.json` |
| **B4** | T-7 | **行为**（涨跌停价格法 + next-day 默认 ignored） | `change_report.json` |
| **B5** | T-8 + T-9 + T-10 | **行为**（动态池 + 退市结算） | `change_report.json` |
| **B6** | T-11 + T-12 | 零数值（契约/转换） | 无 |
| **docs** | T-13 | 零代码 | — |

### 1.3 执行顺序

```text
T-0 RED 基线（10 读数 + B1 测试）
  │
  └─► T-1 夹具 ─► T-2 dump/报告 ────────────────►【B1 提交】
                        │
                        └─► T-3 规则表 ─► T-4 接入 ─►【B2 提交 + 报告】
                                              │
                                              └─► T-5 命名 ─►【B3a 提交 + 基线对拍】
                                                       │
                                                       └─► T-6 口径分离 ─►【B3b 提交 + 报告】
                                                                 │
                                                                 └─► T-7 掩码时点 ─►【B4 提交 + 报告】
                                                                           │
                                                                           └─► T-8 快照 ─► T-9 掩码/结算 ─► T-10 脚本 ─►【B5 提交 + 报告】
                                                                                                       │
                                                                                                       └─► T-11 协议 ─► T-12 契约/端口 ─►【B6 提交】
                                                                                                                                              │
                                                                                                                                              └─► T-13 全量+文档+CI
```

**任一批次的行为变更与预测不符（层 dump 无差异、NAV 差异无法归因）→ 停止并回退该批次**，不跨批次修补。

### 1.4 关键原则

| 原则 | 说明 |
|------|------|
| 先观测、后变更 | B1 必须先把层 dump 与 `change_report` 跑通，B2 起才有归因能力 |
| 命名与口径分离 | B3a 只改名字（`rtol=0` 证明零数值），B3b 才动取价；合并会使归因无法区分 |
| 夹具不破既有 | `baseline` profile 逐字节不变（sha256 记录），27 项数据测试零改动 |
| 规则表 fail-fast | 命中 0/多一律抛异常；禁止 `or 0.10` 类兜底 |
| 缺失不静默 | 退市/上市/清单缺失必须落报告字段，禁止 warning-only |
| 零 opportunistic 重构 | 不动 V3 取价、不动 `config_v2.py`、不删旧字段、不改 CI 矩阵 |
| 旧字段只弃用不删除 | 4 个阈值字段与 `adjustment_type` 保留，发 `DeprecationWarning` |

---

## 2. 工程细节

### 2.1 技术栈与版本（E1）

| 组件 | 版本 | 验证 |
|------|------|------|
| Python | 3.12.10（本地）/ 3.10-3.12（CI） | `pyproject.toml` 已有矩阵 |
| pandas | 既有版本（不新增约束） | 现有 516 测试通过 |
| numpy | 既有版本 | 同上 |
| pytest / black / mypy | 9.0.3 / 26.5.0 / 2.1.0 | P-007 层 B 已锁定 |
| **新增运行时依赖** | **无** | 显式约束（DESIGN §10.1-7） |
| 新增测试依赖 | 无（不引入 `pandera`/`hypothesis`） | 用纯 pandas 断言 |
| 数据文件格式 | **CSV + JSON**，不用 parquet | `pyarrow` 未在 `pyproject.toml` 的 `dependencies`/`dev` 声明（本地 24.0.0 由 streamlit/openml 等无关包带入），CI `pip install ".[dev]"` 不保证安装（F-I3） |

### 2.2 兼容性

| 项 | 处理 |
|----|------|
| Python 3.10 | 使用 `from __future__ import annotations`；不用 3.11+ 语法（`Self`/`StrEnum`） |
| `get_adj_price(forward/backward)` | 保留映射 + `DeprecationWarning`，返回与旧实现逐值相同 |
| `UniverseFilterConfig` 4 阈值字段 | 保留字段，读取时忽略并告警 |
| `UniverseConfig.adjustment_type` | 保留；`legacy_adjustment=True` 时仍生效 |
| `engine_v2` 公开行为 | B3b/B4/B5 会改变回测数值，CHANGELOG 明示 |
| 27 项数据测试（`test_real_ashare_backtest` 9 + `test_real_ashare_strict_validation` 18） | 用 `baseline` profile，零改动 |
| `test_adjustment.py` 3 项旧耦合断言（**F-S7-1**，Step 7 补记） | T-6 默认口径下 `returns=hfq`，`test_returns_use_adjusted_prices_backward` / `test_returns_use_raw_prices_none` / `test_returns_no_fake_gap_on_split`（none 分支）将失败——三者编码「returns 跟随 `adjustment_type`」旧语义；构造补 `legacy_adjustment=True` 保留旧语义覆盖（非弱化断言，不计入 34 项新增） |

### 2.3 文件结构（新增/修改）

```text
core/
├── config.py                     # 改：PriceModeConfig + 新字段
├── data.py                       # 改：get_adj_price 三口径 / returns 口径 / .universe
├── data_v3.py                    # 改：1 行 "forward" → "hfq"
├── universe_data.py              # 新：UniverseSnapshot + listing_mask + 降级
├── data_provider.py              # 新：DataProvider Protocol + PklDataProvider
├── change_report.py              # 新：LayerDiff / ChangeReport / 残差校验
├── interfaces.py                 # 改：收窄 2 成员 / execute_order 签名
├── engine_v2.py                  # 改：_exec_price / 退市结算 / 层 dump 钩子
└── __init__.py                   # 改：__api_version__

filter/
├── limit_rules.py                # 新：LimitRule / 规则表 / infer_board / build_limit_prices
└── universe_filter_clean.py      # 改：规则表接入 / 价格法 / 上市掩码 / next-day 模式 / from_universe_config

scripts/
├── prepare_test_fixture.py       # 改：--profile
├── fetch_universe.py             # 新：本地快照生成（离线优先）
└── change_report.py              # 新：两次运行目录差分 CLI

tests/
├── test_fixture_profile.py       # 新（B1，2）
├── test_change_report.py         # 新（B1，3）
├── test_limit_rules.py           # 新（B2，7）
├── test_adjustment_semantics.py  # 新（B3a，4）
├── test_trade_price_raw.py       # 新（B3b，2）
├── test_limit_mask_timing.py     # 新（B4，3）
├── test_universe_delisting.py    # 新（B5，6）
├── test_contract_conformance.py  # 新（B6，4）
└── test_config_conversion.py     # 新（B6，3）
```

### 2.4 低效/危险操作排除

| 潜在低效/危险 | 排除措施 |
|---------------|----------|
| 逐单元格 `apply` 解析规则 | 预计算 `(board, is_st)` → 规则索引；按日期段向量化 `np.where` |
| 每日循环内重复查规则/构建掩码 | `build_masks()` 一次预计算全日历，循环内只做行切片 |
| 层 dump 全量写盘 | 仅当 `dump_layers_dir` 非空；`L1/L2` 仅写**发生变化**的单元格（长表），不写 N×M 矩阵 |
| `change_report` 仅比较字符串样例 | 同时算 `changed` 计数 + `attributed` 布尔 + NAV 重算残差 |
| 运行时联网 | `fetch_universe.py` 默认读本地；`--refresh` 才联网，且不在 `DataManager` 内 |
| 改 `baseline` 夹具 | 新逻辑只读 `biased`；`baseline` 生成代码路径不进入新分支 |
| 为过测试放宽断言 | 禁止 `assertAlmostEqual` 降精度、禁止 `pytest.skip` 掩盖 |
| 在 `filter/` 内 import `core.data`（循环依赖） | 规则模块只依赖 pandas/numpy；数据经参数传入 |

---

## 3. RED 基线（T-0，实施前必录）

### 3.1 十项读数

| # | 读数 | 命令 | 预期（@`05af52f`） |
|---|------|------|-------------------|
| R1 | 全量测试 | `MPLBACKEND=Agg python -m pytest tests -q` | `516 passed` |
| R2 | black | `python -m black --check .` | `138 files would be left unchanged` |
| R3 | mypy 门禁口径 | `python -m mypy --explicit-package-bases core` | `Success: no issues found` |
| R4 | mypy 盲区口径 | 追加 `--check-untyped-defs` | `8 errors in 2 files`（U-006 残差） |
| R5 | 协议符合性 | `pytest tests/test_contract_conformance.py`（B6 前不存在） | — |
| R6 | `get_adj_price` 数值 | 用 `biased` 前的手工 3 日样本算 hfq/qfq | 记录 `hfq/qfq` 比值序列 |
| R7 | 引擎取价调用点 | `Grep 'get_adj_price' core/engine_v2.py` | **8 次调用 / 7 个位置**（346/391/438/**440**/529/608/669/757；438 与 440 为同段两次调用） |
| R8 | 夹具内容 | `Glob data/test_ashare/*.pkl` | **7 个**，无 `st/list_date/delist` |
| R9 | 基线夹具哈希 | `Get-FileHash data/test_ashare/*.pkl -Algorithm SHA256` | 逐文件记录（B1 后复核不变） |
| R10 | 工作区 | `git status --short` | 仅 docs 变更 |

### 3.2 各批次 RED 测试（先写失败测试，再实现）

| 批次 | 失败测试 | 预期失败形态 |
|------|----------|--------------|
| B1 | `test_fixture_profile.py::test_biased_profile_has_required_files` | `FileNotFoundError`（biased 目录未生成） |
| B1 | `test_change_report.py::test_residual_requires_layers` | `ImportError`（`core.change_report` 不存在） |
| B2 | `test_limit_rules.py::test_st_main_2026_07_06_switch` | `ImportError`（`filter.limit_rules` 不存在） |
| B2 | `test_limit_rules.py::test_rule_lookup_gap_raises` | 同上 |
| B3a | `test_adjustment_semantics.py::test_hfq_formula` | `ValueError: 未知复权口径: hfq` |
| B3a | `test_adjustment_semantics.py::test_legacy_alias_warns` | 无 `DeprecationWarning` |
| B3b | `test_trade_price_raw.py::test_execution_price_excludes_adj` | 成交价仍含 `adj_factor`（断言失败） |
| B4 | `test_limit_mask_timing.py::test_future_perturbation_does_not_change_today` | 掩码随未来数据变化（断言失败） |
| B5 | `test_universe_delisting.py::test_delisted_stock_not_in_universe` | 退市后仍可交易（断言失败） |
| B6 | `test_contract_conformance.py::test_protocol_members[IFactorPipeline]` | `process_single` 缺失（当前 3 项失败） |

> 每批次的 RED 测试必须**先于**该批实现提交；失败形态按实测记录，若与预期不同（如 `ImportError` 变 `AttributeError`），**按实测记录不改断言**。

---

## 4. 逐任务实施要点

### T-1 夹具双 profile（D8）

**文件**: `scripts/prepare_test_fixture.py`

**要点**：
1. 新增 `--profile {baseline,biased}`，默认 `baseline`（保持现有输出路径与字节不变）。
2. `biased` 输出到 `data/test_fixture_biased/`，内容：
   - `close/open/high/low`：6 只股票 × 60 交易日，代码覆盖 `000001/300001/688001/830001/430001/600001`；
   - `stock_adj`：`000001` 恒定 1；`300001` 在 t=30 除权（adj 由 1 → 2）；`688001` 逐日递增；
   - `st`：`600001` 在 t=20~40 为 1（其余 0）；
   - `suspend`：`830001` 在 t=10~12 为 1；
   - `universe/list_date.csv`：`430001` 上市日 = t=15；
   - `universe/delist.csv`：`000001` 退市日 = t=50，`delist_return=-0.10`；
   - `universe/manifest.json`：`source="fixture"`, `rows`, `sha256`, `schema_version="1.0"`。
3. `baseline` 生成函数**零改动**（不在其中插入新分支）。
4. 快照落 `universe/` 子目录，与 `DataManager.cfg.data_dir` 同层级解析（F-I10）：测试传 `data_dir=data/test_fixture_biased` 即可命中，不读真实 `data/universe`。

**验收**: `test_fixture_profile.py` 2 项通过；`baseline` 目录 7 个 pkl 的 sha256 与 R9 逐文件相同。

### T-2 层 dump + change_report（D6）

**文件**: `core/change_report.py`（新）、`scripts/change_report.py`（新）、`core/engine_v2.py`（钩子）

**要点**：
1. `core/change_report.py` 只做数据结构与校验，**不 import engine**。
2. 引擎 `setup()` 读取 `cfg.dump_layers_dir`；非空则创建目录，`_process_trading_day` 末尾调用 `_dump_layers(date)`。
3. dump 内容（长表，非矩阵）：
   - `L1_limit_mask.csv`: `date, stock, can_buy, can_sell`
   - `L2_tradable.csv`: `date, stock, buyable, sellable`
   - `L3_target_positions.json`: `{date: [stock...]}`
   - `L4_orders.json`: `{date: [{stock, side, qty, reason}]}`（`reason` 取固定枚举 `rebalance` / `force_liquidation` / `pending`；引擎当前无独立原因来源，不新增）
   - `L5_fills.json`: `{date: [{stock, side, qty, price, cost}]}`
   - `L6_nav.csv`: `date, cash, market_value, total_value`
4. `scripts/change_report.py before/ after/ -o report.json`：
   - 逐层集合差分（`changed`、`added` 前 5 个、`removed` 前 5 个）；
   - `nav_recomputed` 由 L5 成交 + L6 行情重算；`residual = abs(nav_recomputed - nav_after)`；
   - `attribution_complete`：若 `L6.changed > 0` 则 `L5.changed > 0` 必须成立，依此类推到 L4；任一断裂 → False；
   - 退出码：`residual >= 1e-8` 或 `attribution_complete=false` → 1。
5. 关闭 `dump_layers_dir` 时**零 I/O**（不创建目录、不调用 dump）。

**验收**: `test_change_report.py` 3 项通过（残差计算、断裂检测、关闭零 I/O）。

### T-3 规则表（D3）

**文件**: `filter/limit_rules.py`（新）

**要点**：
1. `LimitRule` 为 `@dataclass(frozen=True)`；`RULESET_VERSION = "cn_a_2026_07"`。
2. 规则表按 §11.4/§12.3.3 落地（主板 10%；主板 ST 5%→10%；创业板 10%→20%、ST 5%→20%；科创板 20%；北交所 30%，并保留 `(bse, is_st=True)` 同 30% 闭合行，U-D3）。
3. `infer_board`：`300/301`→gem；`688/689`→star；`8`/`4` 开头→bse；其余 main。
4. `resolve_limit`：先按 `(board, is_st)` 过滤，再按 `effective_from <= t < effective_to` 取唯一；命中数 ≠ 1 → `LimitRuleError`。
5. 规则索引在模块加载时建一次（`dict[(board,is_st)] -> tuple[LimitRule,...]`），查找 O(规则数)。
6. `special_no_limit_mask`（DESIGN §4.2，**F-S7-2**，Step 7 补录）：`list_date ≤ t < list_date + 5 交易日` → True（IPO 前5日不适用涨跌停限制）；`delist_start_date` 字段缺失 → 整理期部分全 False + 报告 `delist_period_handled=false`（U-D2）；`UniverseSnapshot` 经参数传入（不 import `core`，符合 §2.4）。断言并入既有测试（不新增文件，34 项计数不变）。

**验收**: `test_limit_rules.py` 7 项通过（ST 切换两侧、创业板 2020-08-24 两侧、北交所、板块推断、gap 抛错、overlap 抛错、`RULESET_VERSION` 非空）。

### T-4 接入规则表（D3，行为）

**文件**: `filter/universe_filter_clean.py`

**要点**：
1. `_build_limit_masks` 改为调用 `build_limit_prices`（T-3）→ 该任务只接 ST 阈值部分，**涨跌停判定仍在 T-7 切换**。为避免同批两处行为，T-4 只替换阈值来源（0.095/0.048 → `resolve_limit().up/down`），判定仍用 `returns` 阈值。
2. ST 状态统一用**当日** `self.dm.st`（删除 `st_shifted`）。
3. 4 个旧阈值字段：读取时 `DeprecationWarning`（每次 `build_masks` 一次，不逐行）。

**验收**: ST 主板 2026-07-06 前后掩码差异可在 `change_report` 中看到；`test_limit_rules.py` 保持绿。

### T-5 复权三口径 + 别名（D2，零数值）

**文件**: `core/data.py`、`core/data_v3.py`

**要点**：
1. `get_adj_price(price_type, adjustment_type="hfq")`：
   - `"raw"` → 原价；
   - `"hfq"` → `price * adj`；
   - `"qfq"` → `price * adj / adj.iloc[-1]`；
   - `"forward"` → `warnings.warn(..., DeprecationWarning)` + 走 `hfq`；
   - `"backward"` → 警告 + 走 `qfq`；
   - `"none"` → 警告 + 走 `raw`（基线 9 处既有用法，见 F-I1）；
   - 其他 → `ValueError`。
2. 缓存 key 继续用入参字符串（不归一化），避免 `forward` 与 `hfq` 命中同一 key 后行为不可辨；两者数值相同但缓存分离。
3. `core/data_v3.py:109` `"forward"` → `"hfq"`（消除内部弃用告警）。
4. **不改** `_calculate_returns`（留到 T-6）。

**验收**: `test_adjustment_semantics.py` 4 项通过（`test_legacy_alias_warns` 内覆盖 `forward`/`backward`/`none` 三个旧名，不新增测试函数）；R6 的 hfq/qfq 序列与改前 `forward/backward` 逐值相同（`rtol=0`）。

### T-6 口径分离（D2，行为）

**文件**: `core/config.py`、`core/data.py`、`core/engine_v2.py`

**要点**：
1. `config.py` 新增：
   ```python
   @dataclass
   class PriceModeConfig:
       trade: str = "raw"
       valuation: str = "raw"
       signal: str = "hfq"
       returns: str = "hfq"

   # BacktestConfig
   price_modes: PriceModeConfig = field(default_factory=PriceModeConfig)
   legacy_adjustment: bool = False
   dump_layers_dir: Path | None = None
   ```
2. `engine_v2` 新增私有方法：
   ```python
   def _exec_price(self, dm, kind: str):
       mode = self.cfg.adjustment_type if self.cfg.legacy_adjustment else "raw"
       return dm.get_adj_price(kind, mode)
   ```
   8 次调用（7 个位置；438/440 为同段两次）全部替换为 `self._exec_price(dm, "open"/"close")`。
3. `_calculate_returns`：`legacy_adjustment=True` 时沿用 `adjustment_type`（经旧名映射），保证 I5/V7 的 `rtol=0`；否则用 `self.cfg.price_modes.returns`（默认 `hfq`）。legacy 只扩展取价与收益两处，不扩散到规则表/掩码/退市（F-I2/F-I3）。既有 `test_adjustment.py` 3 项旧耦合断言构造补 `legacy_adjustment=True`（**F-S7-1**，见 §2.2）。
4. 报告新增 `adjustment_mode`（含四个 mode + `legacy_adjustment`）。

**验收**: `test_trade_price_raw.py` 2 项通过（成交价不含 adj；`legacy_adjustment=True` 逐值复现 R6 旧值）。

### T-7 涨跌停价格法（D4，行为）

**文件**: `filter/universe_filter_clean.py`、`core/engine_v2.py`

**要点**：
1. `_build_limit_masks` 改：
   ```python
   limit_up, limit_down = build_limit_prices(close_raw, adj_factor, st, dates)
   self._limit_up_mask = ~(open_raw >= limit_up - EPS)
   self._limit_down_mask = ~(open_raw <= limit_down + EPS)
   ```
   `EPS = 0.005`（半分钱容差）；首行无 `prev_close` → 全 True；原 `_build_limit_masks` 的早退条件 `self.dm.returns is None` 改为「`close`/`adj_factor` 不可用」，否则无 returns 的数据集会被误判为全可交易（F-I8）；掩码叠加 `special_no_limit_mask`（T-3 要点 6，IPO 前 5 日不适用涨跌停限制）。
2. 新增 `limit_check_price: Literal["open","close"] = "open"`；`"close"` 仅用于诊断对比，不进默认路径。
3. `next_day_tradable_mode: Literal["ignored","oracle"] = "ignored"`：
   - `ignored`：不构建 `_next_day_tradable_mask`，`buyable` 不含该约束；
   - `oracle`：保留旧 `shift(-1)` 行为，报告 `next_day_tradable_mode="oracle"`。
4. 旧 `check_next_day_tradable: bool` 保留：`True` 映射 `oracle`、`False` 映射 `ignored`，并发弃用告警。
5. `_force_liquidation` 与 `_process_pending_orders` 的 `buyable/sellable` 语义不变（仍读掩码行）。

**验收**: `test_limit_mask_timing.py` 3 项通过（未来扰动不变 / 打开涨停不可买 / 跌停不可卖）；`change_report` 显示 L1→L2 变化。

### T-8 UniverseSnapshot（D5）

**文件**: `core/universe_data.py`（新）、`core/data.py`

**要点**：
1. `load_universe_snapshot(data_dir, universe_dir)`：
   - 优先 `universe_dir`，默认 `cfg.data_dir / "universe"`（不是仓库固定 `data/universe`，否则 biased 夹具会读到真实目录，F-I10）；
   - `list_date.csv` / `delist.csv` 存在 → `status="corrected"`；
   - 任一缺失 → `status="uncorrected"` + `logger.warning`（**一次**）+ 返回空快照；
   - `manifest.json` 缺失 → `manifest=None`。
2. `listing_mask(dates, codes, snap)`：
   - `~delisted & listed`，缺失字段视为「不限制」；
   - 返回 bool DataFrame（dates × codes）。
3. `DataManager` 新增 `.universe` 属性（懒加载、幂等 guard）与 `.universe_status` 字典。

**验收**: `test_universe_delisting.py` 前 3 项通过（上市前不可买、退市后不可买、缺失降级）。

### T-9 掩码接入 + 退市结算（D5，行为）

**文件**: `filter/universe_filter_clean.py`、`core/engine_v2.py`

**要点**：
1. `_build_listing_mask()` 结果 AND 进 `buyable` 与 `sellable`（上市前/退市后都不可交易）。
2. 引擎 `_process_trading_day` 在订单处理前调用 `_settle_delisted(date)`：
   - 对 `delist_date == date` 的持仓，结算价 = `last_close × (1 + delist_return)`（有 `delist_return` 时）→ 否则 `last_close` → 两者都缺则跳过并计入 `unclosed_positions`；
   - 复用 `_force_liquidation` 的私有路径，新增参数 `stocks: dict[str, str]` 与 `price_override`；结算路径**不**重复调用 `tracker.update_market_values`（当日收盘后 `_process_trading_day` 已统一盯市，重复调用会用退市日价格覆盖其它持仓，F-I9）；
   - 报告 `delist_return_source`、`n_delisted_closed`。
3. `survivorship` 状态从 `DataManager.universe_status` 透传到报告。

**验收**: `test_universe_delisting.py` 后 3 项通过（退市结算价、来源标记、报告字段）。

### T-10 `fetch_universe.py`（D5）

**文件**: `scripts/fetch_universe.py`（新）

**要点**：
1. 默认**离线**：读本地已有 CSV 并重写 manifest（`--recompute-hash`）。
2. `--refresh` 才联网：优先 Tushare `stock_basic(list_status in L/D/P/UN)`，缺 token 时回退 AKShare `stock_info_{sh,sz}_delist`。
3. 写 `manifest.json`：`source / fetched_at / rows / sha256 / schema_version`。
4. 无网络/无 token 时退出码 0 并打印替代路径（`--from-csv`），**不得**写空文件冒充成功。

**验收**: 无网络环境下 `python scripts/fetch_universe.py --recompute-hash` 退出 0；不产生网络请求。

### T-11 协议收窄 + 签名对齐（D7，零数值）

**文件**: `core/interfaces.py`、`core/__init__.py`

**要点**：
1. 删除 `IFactorPipeline.process_single`、`IFactorCombiner.combine_single`（E1：全仓 0 调用方）。
2. `IExecutionSimulator.execute_order` 以实现为准：
   ```python
   def execute_order(
       self, stock: str, side: Any, quantity: int, date: pd.Timestamp,
       open_price: float, close_price: float | None = None,
       high_price: float | None = None, low_price: float | None = None,
       volume: float | None = None,
   ) -> tuple[bool, Any | None]: ...
   ```
   删除 `**kwargs` 与 `price`。
3. `core/__init__.py` 增 `__api_version__ = "3.1.0"`（仅元数据，不恢复重导出）。

**验收**: `pytest tests -q` 零回归；mypy 0 不变。

### T-12 契约测试 + DataProvider + D11 转换（D7/D11）

**文件**: `core/data_provider.py`、`filter/universe_filter_clean.py`、`core/engine_v2.py`、新增 2 测试文件

**要点**：
1. `test_contract_conformance.py`：RESEARCH §11.5 登记的 6 个协议（`IDataManager` / `IUniverseFilter` / `IPositionTracker` / `IFactorPipeline` / `IFactorCombiner` / `IExecutionSimulator`）× 实现类 + `MockDataProvider`，断言成员集合完整；`execute_order` 用 `inspect.signature` 断言形参名与个数。
2. `DataProvider` Protocol + `PklDataProvider`；**不接线**（无生产 import）。
3. `UniverseFilterConfig.from_universe_config(cfg)`：21 字段逐一显式赋值（禁止 `asdict` 盲拷，避免漏字段）；其中 `exclude_stock_prefixes` 必须 `bool(cfg.exclude_stock_prefixes)`——源类型 `list[str]` vs 目标 `bool`，直拷会把 list 塞进 bool 字段，前缀列表在 `excluded_prefixes`（F-I5）。
4. `engine_v2.py:195` 改 `UniverseFilter(self.dm, UniverseFilterConfig.from_universe_config(self.cfg.universe))`。
5. `test_config_conversion.py`：3 项（字段全等 / 默认值漂移被显式覆盖 / 未知字段不丢失）。

**验收**: 3 项原不符合协议转绿；`Grep 'data_provider' -- '*.py'` 仅命中 `core/data_provider.py` 与测试。

---

## 5. 验证清单（V1-V20）

| ID | 验证 | 命令/方式 | 预期 |
|----|------|-----------|------|
| V1 | 全量测试 | `MPLBACKEND=Agg python -m pytest tests -q` | **550 passed**（预测：516 + 34 新增） |
| V2 | black | `python -m black --check .` | `unchanged` |
| V3 | mypy | `python -m mypy --explicit-package-bases core` | 0 errors |
| V4 | 盲区 | 追加 `--check-untyped-defs` | ≤ 8（D11 可能再降 1，按实测） |
| V5 | 门禁 | `gate probe / unit-tests / black-check / mypy-check` | 4 pass + replay OK |
| V6 | 复权恒等式 | `qfq` 末值 = 原始末值、`hfq` 首值 = 原始首值、比值恒定 | 全等 |
| V7 | 兼容基线 | `legacy_adjustment=True` vs 改前快照 | `rtol=0` 逐值相等 |
| V8 | 规则表边界 | 每条规则 4 个边界日 | 唯一命中 |
| V9 | 无前视 | 未来数据置 NaN 后重跑，t 行掩码不变 | 逐值相等 |
| V10 | 退市掩码 | 退市后 `stock_codes(t)` 不含该股 | True |
| V11 | 降级字段 | 删除 `data/universe/` 后运行 | `survivorship="uncorrected"` |
| V12 | 归因 | `scripts/change_report.py before after` | `residual < 1e-8` |
| V13 | dump 零影响 | 开/关 `dump_layers_dir` 两次运行 | NAV 逐值相等 |
| V14 | 契约 | `pytest tests/test_contract_conformance.py` | 4/4 |
| V15 | 零接线 | `Grep 'data_provider' -- '*.py'` | 仅模块本体 + 测试 |
| V16 | 夹具不破 | `baseline` 7 个 pkl sha256 vs R9 | 全同 |
| V17 | CI | 推送后三 job | `543 passed, 1 skipped`（预测 = (516 − 7 numba) + 34；numba 模块级 skip 计 1，F-I6） |
| V18 | 报告字段 | 一次运行产物 | 含 `adjustment_mode/survivorship/ruleset_version/next_day_tradable_mode` |
| V19 | 取价收敛 | `Grep 'get_adj_price' core/engine_v2.py` | 仅 `_exec_price` 内 1 处 |
| V20 | 回退粒度 | 逐批 `git revert` 演练（dry-run） | 每批独立可回退 |

> **预测值声明**：V1/V17 的 550/543 基于 §2.3 的测试计数（2+3+7+4+2+3+6+4+3=34）与 CI「本地 − 7 numba」口径；Step 9 以实测为准，**不得为凑数增删测试**。

---

## 6. 回退点

| 批次 | 回退动作 | 副作用 |
|------|----------|--------|
| B1 | `git revert <B1>` | 无（dump 默认关、脚本不参与运行） |
| B2 | `git revert <B2>` | 恢复 4.8%/9.5% 常数与 `st.shift(1)` |
| B3a | `git revert <B3a>` | 恢复旧命名；`forward/backward` 行为不变 |
| B3b | `legacy_adjustment=True` 或 revert | 数值回到旧口径 |
| B4 | `next_day_tradable_mode="oracle"` + revert | 恢复收益阈值掩码 |
| B5 | 移除 `data/universe/` 或 revert | 回静态池（报告标注未校正） |
| B6 | `git revert <B6>` | 协议回到旧定义（不影响数值） |

---

## 7. 会话与门禁

| 项 | 值 |
|----|-----|
| 门禁 session | `factorv3-p012-bias-20261110` |
| 门禁链 | `probe` → `unit-tests` → `black-check` → `mypy-check` |
| 解释器 | `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe` |
| 环境变量 | `MPLBACKEND=Agg` |
| 提交纪律 | 每批次一个提交；消息经临时文件 + `git commit -F`（PowerShell 5 无 heredoc） |
| 禁止 | `--no-verify`、跳过 hook、把多个批次合并为一个提交 |

---

## 8. Step 6 Review（独立 pass，2026-11-10）

- **执行时点**: 正文完稿后的单独 pass，与正文写入分离（RULE-1）
- **审查者**: 单 Agent 自查（RULE-4）
- **审查方式**: E1 命令复算（pytest / black / mypy / Grep / Glob）+ E3 读码（`@2c34283`，`core`/`filter`/`tests` 与 `05af52f` 零 diff）+ D1-D11 ↔ T 双向覆盖 + 算术复核；不依赖正文自报

### 8.1 事实核实

| ID | 核实项 | 方式 | 结果 |
|----|--------|------|------|
| C-1 | R1 全量测试 | `MPLBACKEND=Agg pytest tests -q` | **516 passed** ✅ |
| C-2 | R2 格式 | `black --check .` | **138 files unchanged** ✅ |
| C-3 | R3 门禁 mypy | `mypy --explicit-package-bases core` | **Success（29 source files）** ✅ |
| C-4 | R4 盲区 | 追加 `--check-untyped-defs` | **8 errors in 2 files**（engine_v2 6 + data_v3 2）✅ |
| C-5 | R7 取价点 | `Grep get_adj_price core/engine_v2.py` | **8 次调用 / 7 个位置**（346/391/438/**440**/529/608/669/757）；正文写 7 处 → **F-I2** |
| C-6 | R8 夹具 | `Glob data/test_ashare/*` | 7 pkl（close/high/industry/low/open/stock_adj/suspend）+ `output/`；无 st/list_date/delist ✅ |
| C-7 | R10 工作区 | `git status --short` | 仅 docs 变更（2 M + 4 untracked）；HEAD `2c34283` 与证据时点一致 ✅ |
| C-8 | `"none"` 既有用法 | `Grep 'adjustment_type="none"|get_adj_price(...,"none")'` | **9 处**（`tests/test_adjustment.py`，含 `BacktestConfig(adjustment_type="none")` 2 处）；`config.py:338` 文档声明 `'none'=不复权` → **F-I1** |
| C-9 | parquet 依赖 | `pyproject.toml:28-68` + `pip show pyarrow` | **未声明**；本地 24.0.0 的 `Required-by` 为 factor-db/getfactormodels/glum/openassetpricing/openml/streamlit（均非本项目依赖）→ **F-I3** |
| C-10 | `exclude_stock_prefixes` 类型 | `config.py:217` vs `universe_filter_clean.py:38` | **`list[str]` vs `bool`**；filter 侧按 bool 使用（L106/125/337/375）→ **F-I5** |
| C-11 | `process_single`/`combine_single` | `Grep 'def process_single|def combine_single'` 全仓 | 仅 `interfaces.py:142/164` 定义，**0 实现、0 调用** ✅ |
| C-12 | `execute_order` 对齐目标 | `execution.py:250-261` vs `interfaces.py:214-235` | 实现为 `open_price + OHLC 可选`，协议为 `price + **kwargs` → T-11「以实现为准」可实现 ✅ |
| C-13 | `st` 缺失行为 | `data.py:305-312` | 缺失落 0 矩阵（非 None）→ T-4 当日 ST 判定无空值分支 ✅ |
| C-14 | 夹具脚本现状 | `scripts/prepare_test_fixture.py` | 无 `--profile`；默认 7 pkl + `--force` 覆盖保护 ✅ |
| C-15 | 27 项数据测试范围 | `pytest tests/test_real_ashare_strict_validation.py -q` = **18 passed**；`DESIGN_ci_test_env §1.1` 为 9 + 18 | 正文把 27 项全归 strict 文件（实为 18）→ **F-I4** |
| C-16 | CI 计数链 | `CHECKLIST_p010 D6`「507 = 514 − 7 numba」+ 本次 516 | CI 基线 509 passed + 1 skipped；+34 → **543 + 1**，正文 V17 写 544 → **F-I6** |
| C-17 | 文件数口径 | 正文头部 vs §2.3 | `core/` 实为 9（3 新 + 6 改）、`scripts/` 3、`tests/` 9 新 → **F-I7** |
| C-18 | `_build_limit_masks` 早退门 | `universe_filter_clean.py:142-152` | 以 `dm.returns is None` 为门；价格法下语义错位 → **F-I8** |
| C-19 | `_force_liquidation` 复用面 | `engine_v2.py:376-418` | 末端 `tracker.update_market_values(date, close_prices)`；T-9 复用需避免覆盖当日盯市 → **F-I9** |
| C-20 | `universe_dir` 来源 | 全仓 Grep | 无该配置字段；T-8 默认 `data/universe` 与 biased 夹具目录不一致 → **F-I10** |

### 8.2 发现项（全部回写）

| ID | 级别 | 发现 | 回写 |
|----|------|------|------|
| **F-I1** | **P1** | **T-5 丢失 `"none"` 口径**：新 mode 集合只含 raw/hfq/qfq + forward/backward，其他一律 `ValueError`；但基线 `tests/test_adjustment.py` 有 9 处 `"none"`，且 `config.py:338` 声明 `'none'=不复权`。照原文实施会使 516 基线出现 9 处失败，V1 的 550 无法达成 | T-5 增 `"none" → raw` + DeprecationWarning；`test_legacy_alias_warns` 覆盖 3 个旧名（不新增测试函数，34 项计数不变）；DESIGN §4.1/§7 同步 |
| **F-I2** | P2 | **R7/T-6 取价点少计 1**：`engine_v2.py` 实为 **8 次调用**（346/391/438/**440**/529/608/669/757）；照「7 处」实施会漏 440，V19「仅 1 处」不成立 | §3.1 R7、T-6 改为 8 次 / 7 位置 |
| **F-I3** | **P1** | **`.parquet` 引入未声明依赖**：`pyproject.toml` 的 `dependencies`/`dev` 均无 `pyarrow`；CI `pip install ".[dev]"` 不保证安装，任一 parquet 读写即失败。违反 §2.1「新增运行时依赖 无」与 DESIGN §10.1-7 | 夹具/快照/层 dump 全部改 **CSV + JSON**；§2.1 增「数据文件格式」行；DESIGN §3.1/§6.1 文件名同步 |
| **F-I4** | P3 | 「27 项数据测试」跨两文件（`test_real_ashare_backtest` 9 + `test_real_ashare_strict_validation` 18），正文 §2.2 全归 strict 文件（实为 18） | §2.2 改为两文件并列 |
| **F-I5** | P2 | **T-12 的 21 字段直拷类型错配**：`exclude_stock_prefixes` 在 `UniverseConfig` 是 `list[str]`、在 `UniverseFilterConfig` 是 `bool`；直拷让 bool 字段持有 list，「字段全等」单测用 `==` 也会失败 | T-12 明确 `bool(cfg.exclude_stock_prefixes)`；单测断言默认 `False` / 非空列表 `True`；DESIGN D11 补类型映射 |
| **F-I6** | P3 | **V17 CI 预测差 1**：CI = 本地 − 7 numba（模块级 skip 计 1）；516 → 509 + 1 skipped，+34 → **543 passed, 1 skipped** | V17 与预测声明改 543 |
| **F-I7** | P3 | 头部文件数口径错：`core/` 实为 9（3 新 + 6 改）、`scripts/` 3、`tests/` 9 新，正文写 5/2/7 | 头部改为实际值 |
| **F-I8** | P3 | T-7 未替换 `_build_limit_masks` 的早退门（`dm.returns is None`）；价格法下会以错误依据放行「全可交易」。另 T-3 未写 U-D3 的 `(bse, is_st=True)` 闭合行、T-2 的 L4 `reason` 无数据来源 | T-7 补早退门改判；T-3 补 bse ST 闭合行；T-2 固定 `reason` 枚举 |
| **F-I9** | P3 | T-9 未写 `delist_return` → 结算价公式；且 `_force_liquidation` 末端会 `update_market_values`，在日内在 `_settle_delisted` 调用会用退市日价格重估全部持仓 | T-9 写 `settle = last_close × (1 + delist_return)`，并注明结算路径不重复盯市 |
| **F-I10** | P2 | **`universe_dir` 解析未定义**：`DataManager` 无该配置，T-8 默认仓库级 `data/universe`，而 T-1 的 biased 夹具在 `data/test_fixture_biased/` 下生成；测试会读真实目录或直接失败 | T-8 默认 `cfg.data_dir / "universe"`；T-1 写入 `universe/` 子目录；DESIGN §4.3 同步 |

> 分级口径：P1 = 照原文实施会直接导致基线/CI 红或违反硬约束；P2 = 实施前必须定口径（否则行为不可验证）；P3 = 文档/计数修正。

### 8.3 覆盖与算术核对

| 核对项 | 结果 |
|--------|------|
| D1-D11 → T | D1→§1.2/§1.3；D2→T-5/T-6；D3→T-3/T-4；D4→T-7；D5→T-8/T-9/T-10；D6→T-2；D7→T-11/T-12；D8→T-1；D9→§1.4/§2.3；D10→§2.2/V18；D11→T-12 —— **11/11 全覆盖** ✅ |
| T → D（反向） | T-0→D1/D6/D8；T-1→D8；T-2→D6；T-3/T-4→D3；T-5/T-6→D2；T-7→D4；T-8/T-9/T-10→D5；T-11/T-12→D7/D11；T-13→流程 —— **无孤儿任务** ✅ |
| 测试算术 | 2+3+7+4+2+3+6+4+3 = **34**；516 + 34 = **550** ✅ |
| CI 算术 | (516 − 7) + 34 = **543** + 1 skipped（F-I6 修正后） ✅ |
| 不变式覆盖 | I1←T-6 测试；I2←V9；I3←V8；I4←V11；I5←V7；I6←V12；I7←V14；I8←V13；I9←V15 —— **9/9** ✅ |
| 回退独立性 | B1-B6 七个提交各自 `git revert` 互不依赖；B3b 另有 `legacy_adjustment=True` 非 revert 通道；B5 另有「移除快照目录」降级通道 ✅ |

### 8.4 Review 结论

- P0：**0**
- P1：**2**（F-I1 / F-I3，已回写）
- P2：**3**（F-I2 / F-I5 / F-I10，已回写）
- P3：**5**（F-I4 / F-I6 / F-I7 / F-I8 / F-I9，已回写）
- 判定：任务粒度满足「可实施 + 可机械核验 + 可独立回退」；**Step 6 通过，可进入 Step 7（CHECKLIST）**

---

**Review 签字**: 单 Agent 自查（RULE-4） 日期: 2026-11-10

---

## 9. Step 9 实施回写（F-S9-*，2026-11-10）

> 逐批实施与 T-13 取证期间的发现；详细读数见 [CHECKLIST_p012_bias_interface.md](CHECKLIST_p012_bias_interface.md) §10.0。

| ID | 级别 | 发现 | 处置（提交） |
|----|------|------|--------------|
| F-S9-1 | P3 | 报告 `adjustment_mode` 初版仅 trade/valuation，缺 signal/returns/legacy_adjustment | 补齐五键（B3b 内） |
| F-S9-2 | P2 | 末日强平后 L6 末行未刷新，归因 NAV 与引擎终值不一致 | `LayerDumper.update_last_nav` + `engine._refresh_last_nav`（`5f95b48`） |
| F-S9-3 | P2 | L1 未含 listing，B5 的 L2 变化在归因链上无上游解释 | `get_layer_masks` L1 = suspend & limit & listing（`5f95b48`） |
| F-S9-4 | P2 | L4→L3 硬链误判：L3 只记目标股票集合，订单量随净值变化（同日买卖方向亦可能互换） | 删除该链，保留 L6→L5→L4 与 L3→L2→L1（`0ccc7f6`） |
| F-S9-5 | P2 | `_cash_flow` 把首日现金流重复计入首行现金，残差 1.12e6 | 区间改 `(首日, 末日]`（`5f95b48`） |
| F-S9-6 | P2 | biased 夹具除权日 open/high/low 由除权前收盘推导 → +100% 伪跳空；层 CSV 读回 `000001` 变 `1` | 除权日后尺度缩放 + 新增 `2024-02-27` 真实涨停开盘样本；`_read_long` 指定 stock=str（`9be78e9`） |
| F-S9-7 | P2 | DESIGN §7 的「未知前缀一次性 warning + `unknown_board_codes`」未实现 | `infer_board` 计数/告警 + `unknown_board_count()` + 报告字段（`9d16a2a`） |
| F-S9-8 | P3 | 夹具 manifest 缺 `fetched_at`，与 `fetch_universe` 五字段产物不同构（E6/T-10） | 补固定时间戳（`86f7650`） |
| F-S9-9 | P3 | `DataManager.universe` 懒加载属性未标注，盲区 +1 error | 补 `Any` 标注，盲区回到 4 errors / 2 files（`766c007`） |

### 9.1 T-13 验证读数（摘要）

| 项 | 读数 |
|----|------|
| V1 | 550 passed（516 + 34），0 failed |
| V2 / V3 / V4 | black 153 unchanged / mypy 0（32 files）/ 盲区 4 errors 2 files |
| V5 | 4 gate pass + replay 16 rows OK（session `factorv3-p012-bias-20261110`） |
| V6 / V7 | 恒等式全等（ratio spread 4.44e-16）/ legacy rtol=0（NAV 1,155,172.3318119394，136 笔 trades 全等） |
| V8 / V9 / V10 / V11 | 28 边界日唯一命中 / 扰动不变 / 退市后不可交易 / `survivorship="uncorrected"` + `n_unknown_*` |
| V12 | 四份 change_report 双门通过（residual ≤ 4.66e-10；attribution=true） |
| V13 / V14 / V15 / V16 | dump 零影响 / 契约 4/4 / `data_provider` 仅测试 2 处 / baseline sha256 全同 |
| V18 / V19 | 报告含四字段（+unknown_board_codes）/ 取价仅 `_exec_price` 内 2 行 |
| V20 | 逆序逐批回退 9/9 干净；中间批次单 revert 有顺序依赖冲突 |
| V17 | 远端 run `42694945888`：3.10/3.11/3.12 三 job success，各 543 passed, 1 skipped |
