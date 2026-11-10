# P-012 偏差防护与接口锁定 · 设计文档

> **文档编号**: DESIGN_p012_bias_interface
> **阶段**: Phase 1 - 设计（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: Step 3 完稿；**Step 4 Review 通过**（2026-11-10，§9；P1×1 + P2×2 + P3×4 全部回写）；可进入 Step 5；**Step 6 回写**（2026-11-10，格式/口径 4 处同步，见 [IMPL §8](IMPL_p012_bias_interface.md)）
> **上游**: [RESEARCH_bias_interface.md](RESEARCH_bias_interface.md)（Step 2 Review 通过；U-1~U-9 已裁决，见 §11.0 / §12.5）
> **下游**: IMPL_p012_bias_interface → CHECKLIST_p012_bias_interface
> **证据时点**: 本仓读数 @ `05af52f`（2026-11-10）；Python 3.12.10；测试基线 `516 passed`
> **档位**: T1（触及 `core/data.py`、`core/engine_v2.py`、`core/config.py`、`core/interfaces.py`、`filter/`、`scripts/`、`tests/`）
> **关联 ADR**: [ADR-017](DECISIONS.md)（复权口径校正与三口径分离，📋 已规划）

---

## 1. 决策总览

| ID | 决策项 | 决定 | 对应 |
|----|--------|------|------|
| **D1** | 批次切分 | 拆为 **B1-B6 六组、共 7 个独立提交**：B1 观测网（零行为）→ B2 ST 规则表 → **B3a 复权命名（零数值）+ B3b 口径分离（行为）** → B4 掩码时点（行为）→ B5 退市能力（行为）→ B6 接口治理（零数值） | U-2 / U-8 / U-7 / U-1 / U-5 |
| **D2** | 复权语义与配置 | `get_adj_price` 改 `mode ∈ {raw, hfq, qfq}`；`forward→hfq`、`backward→qfq`、`none→raw` 旧名保留 ≥2 minor 并发 `DeprecationWarning`；新增 `PriceModeConfig`，成交/估值=`raw`、信号/收益=`hfq` | U-3 / U-7（ADR-017） |
| **D3** | 涨跌停规则表 | 新增 `filter/limit_rules.py`：不可变 `LimitRule` 表 + `(board, is_st, t)` **恰好 1 条** fail-fast；板块由代码前缀推断；ST 判定统一用**当日**状态 | U-4（R-A） |
| **D4** | 掩码时点 | 涨跌停判定由「t 日复权收益阈值」改为「**t 日开盘价 vs 涨跌停价**」（除权参考价还原）；`next_day_tradable` 默认 `ignored`，保留 `oracle` 模式并显式上报。**不采纳 RESEARCH §6.2 L-A 的 `shift(1)` 备选**：昨日停牌状态 ≠ 今日可交易（停牌股常复牌），`shift(1)` 只消除时间前视、不解决语义错误；`ignored` + 报告字段是更诚实的降级 | U-2 |
| **D5** | 退市与动态池 | 新增 `list_date` / `delist` / `manifest` 数据契约 + `UniverseSnapshot` + 上市/退市掩码；缺失走**显式降级**（warning + 报告字段），不静默 | U-1 / U-6（D-A） |
| **D6** | 六层归因 | 引擎可选落 `layers/` 六层 dump（默认关）；`scripts/change_report.py` 产出 `change_report.json`：层间集合差分 + NAV 重算残差 < 1e-8 + `attribution_complete` 门 | U-2 |
| **D7** | 接口治理 | 协议**收窄**（删零消费方成员 `process_single`/`combine_single`）+ `execute_order` 形参对齐（**方向：以实现签名为准修订协议**——协议是契约，须命名真实形参 `open_price`/`close_price` 等，删除 `**kwargs`）+ 契约符合性测试 + `__api_version__`；新增 `DataProvider` 端口 + `PklDataProvider`（不接线） | U-5a / U-5b（B-A） |
| **D8** | 夹具与测试网 | `prepare_test_fixture.py` 增 `--profile {baseline,biased}`；baseline 不变（保 27 项既有数据测试），biased 提供非 1 复权/ST/板块/退市/停牌样本 | P22 |
| **D9** | 范围边界 | **不做** P-011 的 golden/统计规范/外部对拍；**不做** P-004 的消费方迁移；**不改** V3 引擎取价与掩码（V3 不使用 `UniverseFilter`）；**不引入** 网络依赖 | — |
| **D10** | 配置与报告字段 | 新增字段一律带默认值；4 个旧阈值字段保留但 `DeprecationWarning`；报告新增 `adjustment_mode`/`survivorship`/`ruleset_version`/`next_day_tradable_mode` 等（含 `unknown_board_codes`，Step 9 F-S9-7 补）；配置含 `limit_check_price: Literal["open","close"]="open"`（IMPL T-7；`"close"` 仅诊断，不进默认路径，F-A1 补列名） | — |
| **D11** | 配置双定义（Step 4 补录） | 新增 `UniverseFilterConfig.from_universe_config(cfg: UniverseConfig) -> UniverseFilterConfig` 类方法：21 字段逐字段映射 + 字段级单测断言无默认值漂移；`exclude_stock_prefixes` 须 `bool(cfg.exclude_stock_prefixes)`（源 `list[str]` vs 目标 `bool`，前缀列表在 `excluded_prefixes`）；`engine_v2.py:195` 改为经转换传入 | §11.5 P0 / P15 |

**总量核对**：行为变更批次 = **B2 / B3b / B4 / B5**（4 个，各自独立 `change_report.json`）；零行为批次 = **B1 / B3a / B6**。与 §3.14「每次行为变更单独批次」逐条对应，无一批含两类变更。D11 归入 B6（接口治理，零行为——仅转换函数 + 单测）。

---

## 2. 设计依据

### 2.1 调研结论 → 设计决策映射

| 调研结论 | 设计决策 | 引用 |
|----------|----------|------|
| `forward = price×adj` 实为 hfq、`backward = price×adj/adj[-1]` 实为 qfq（A17 Tushare 官方公式） | D2 命名校正 + 旧名别名 | RESEARCH §11.3 / ADR-017 |
| 引擎 8 次取价（7 个位置）全部走 `get_adj_price`（P8 / F-I2）；成交/估值在复权价体系下失真 | D2 成交/估值切 `raw`；`legacy_adjustment` 复现旧值 | RESEARCH P8 / ADR-017 |
| `returns` 由 `adjustment_type` 派生、又被涨跌停掩码复用（P21） | D2 口径分离 + D4 判定改价格法 | RESEARCH §11.3、P21 |
| 主板 ST 5%→10%（2026-07-06）、创业板 20%（2020-08-24 起）、北交所 30%（A20/A21/A22） | D3 规则表 + 日期段 | RESEARCH §11.4、§12.3 |
| 无 ST 文件夹具 → ST 路径零覆盖（P22） | D8 biased profile | RESEARCH P22 |
| 涨跌停掩码用 t 日收益、次日开盘执行（P5）；`suspend.shift(-1)`（P6） | D4 价格法 + `next_day_tradable` 降级 | RESEARCH P5/P6 |
| 无退市/上市字段，股票池为静态列集合（P1/P2）；Tushare 官方建议本地快照（A24） | D5 数据契约 + 本地快照 + 降级 | RESEARCH §11.1、§12.1 |
| 协议 3 项不通过、配置双定义 2 处漂移（§11.5 E2） | D7 协议收窄/对齐 + 契约测试；**D11 配置转换** | RESEARCH §11.5、§12.4 |
| Qlib 股票池 = 列表 + 日期区间（A28）；Zipline 退市资产显式异常（A29） | D5 上市/退市掩码 + 显式失败 | RESEARCH §12.1 |
| SR 26-02 独立验证 + 回测对照（A23）；六层归因（§11.2） | D6 change_report | P-011 §11.2、RESEARCH §11.2 |

### 2.2 相关 ADR

| ADR | 决策 | 对本设计的影响 |
|-----|------|--------------|
| [ADR-017](DECISIONS.md) | 复权命名校正 + 口径分离 + 兼容开关 | D2 的全部字段与迁移语义；**字段映射**：ADR 的 `trade_price_mode` → `PriceModeConfig.trade`、`signal_price_mode` → `.signal`、`return_price_mode` → `.returns`；`limit_price_mode` 由 D4 价格法取代（见 §4.2） |
| ADR-003 | 依赖注入 + `core/interfaces.py` 定义全部 Protocol | D7 契约收敛在该文件内完成 |
| ADR-005 | T+1 执行（pending queue + 次日开盘） | D4 的判定时点必须与「开盘成交」对齐 |
| ADR-006 | Walk-Forward 训练/验证/测试分离 | 本批不改，D5 的动态池对其透明 |
| ADR-016 | 空 `__init__`、显式导入 | D7 的 `__api_version__` 只写元数据，不恢复重导出 |

### 2.3 职责边界

**职责内**：复权语义与取价口径、涨跌停规则与判定时点、退市/上市可见性与动态池、六层归因报告、接口契约唯一化、测试夹具扩展。

**职责外**：golden 回归与统计规范（P-011）、外部框架对拍（P-011 U-4）、`DataManager`↔`DataLoaderV3` 合并与消费方迁移（P-004）、V3 向量引擎的取价与掩码（无 `UniverseFilter` 依赖，另行评估）、退市整理期逐日行情拟合（本批只做末日结算）。

---

## 3. 架构设计

### 3.1 整体架构

```text
                    ┌─────────────────────────────┐
   data/universe/   │  UniverseSnapshot (D5)      │
   list_date.csv    │  list_date / delist /       │
   delist.csv       │  manifest / source          │
   manifest.json    └──────────┬──────────────────┘
                               │ listing_mask
   pkl 行情 ──► DataManager ───┼──► UniverseFilter ──► buyable/sellable
                  │            │        ▲
                  │            │        │ LimitRule 表 (D3)
                  │            │        │ 开盘价 vs 涨跌停价 (D4)
                  │            │        │
                  │     get_adj_price(mode) (D2)
                  │            │
                  └──► EngineV2 ──► 订单 ──► 成交 ──► tracker/NAV
                               │
                               └──► LayerDump (D6, 可选) ──► change_report.py
```

### 3.2 模块划分

| 模块 | 职责 | 输入 | 输出 | 依赖 |
|------|------|------|------|------|
| `core/data.py`（改） | 复权三口径 + 收益口径 + `UniverseSnapshot` 入口 | pkl 行情、universe 文件 | `get_adj_price` / `returns` / `.universe` | D2/D5 |
| `filter/limit_rules.py`（新） | 规则表、板块推断、限价计算、fail-fast 查找 | code/st/date/adj | `LimitRule`、limit prices | D3 |
| `filter/universe_filter_clean.py`（改） | 上市/退市掩码 + 价格法涨跌停 + next-day 模式 | dm、规则表 | `buyable`/`sellable`/`tradable` | D3/D4/D5 |
| `core/universe_data.py`（新） | 加载/校验/降级 `list_date`+`delist`+`manifest` | `data/universe/` | `UniverseSnapshot` | D5 |
| `core/config.py`（改） | `PriceModeConfig` + 新配置字段 | — | dataclass | D2/D10 |
| `core/engine_v2.py`（改） | 取价统一、退市结算、层 dump 钩子 | dm/universe/executor | NAV/报告 | D2/D5/D6 |
| `core/change_report.py`（新） | 报告数据结构与残差校验 | layers/、NAV | `change_report.json` | D6 |
| `scripts/change_report.py`（新） | CLI：两次运行目录差分 | before/after 目录 | JSON | D6 |
| `core/interfaces.py`（改） | 协议收窄 + 签名对齐 | — | Protocol | D7 |
| `core/data_provider.py`（新） | `DataProvider` 端口 + `PklDataProvider` | 数据目录 | DataFrame | D7 |
| `scripts/prepare_test_fixture.py`（改） | 双 profile 夹具 | `--profile` | pkl/csv | D8 |
| `scripts/fetch_universe.py`（新） | 拉取 `stock_basic(list_status)` 并落 `data/universe/`（本地快照，`--refresh` 显式刷新） | Tushare/AKShare token | `list_date.csv`/`delist.csv`/`manifest.json` | D5（§12.1 D-A） |

### 3.3 数据流

1. **运行时**：`DataManager` 读 pkl → `UniverseFilter.build_masks()` 依次构建 `listing_mask`(D5) → `suspend`(当日) → `limit via price`(D3/D4) → `st`(当日) → 其他扩展 → `buyable/sellable/tradable`。
2. **取价**：引擎 `_exec_price(kind)` 统一返回 `get_adj_price(kind, "raw")`（新口径）或 `get_adj_price(kind, cfg.adjustment_type)`（`legacy_adjustment=True`）。
3. **归因**：开启 `dump_layers_dir` 时，每日在 L1/L2/L3/L4/L5/L6 各写一份快照；`change_report.py` 对两个目录做差分。

### 3.4 控制流

```text
setup(): 加载 universe → 构建掩码 → 打印/记录 ruleset_version 与 survivorship 状态
run():  for each date:
          _settle_delisted(date)            # D5 退市结算（先于订单）
          _process_pending_orders(date)     # D4 用当日开盘价判定可成交
          _execute_rebalance(date)          # 生成目标 → 订单
          update_market_values(date)        # D2 raw 估值
          _dump_layers(date)                # D6 可选
```

---

## 4. 接口定义

### 4.1 复权取价（D2，`core/data.py`）

```python
PriceMode = Literal["raw", "hfq", "qfq"]

def get_adj_price(self, price_type: str = "close", adjustment_type: str = "hfq") -> pd.DataFrame:
    """获取指定口径的价格。

    mode:
      - "raw"             : 原始价（成交/估值/限价）
      - "hfq"             : 后复权 = price * adj_factor
      - "qfq"             : 前复权 = price * adj_factor / adj_factor.iloc[-1]
      - "forward"/"backward"/"none"（deprecated）: 分别映射 hfq/qfq/raw，发 DeprecationWarning

    Raises:
      ValueError: mode 不在允许集合
    """
```

```python
@dataclass
class PriceModeConfig:
    trade: Literal["raw", "hfq", "qfq"] = "raw"
    valuation: Literal["raw", "hfq", "qfq"] = "raw"
    signal: Literal["raw", "hfq", "qfq"] = "hfq"
    returns: Literal["raw", "hfq", "qfq"] = "hfq"
```

### 4.2 规则表（D3，`filter/limit_rules.py`）

```python
@dataclass(frozen=True)
class LimitRule:
    board: str                          # main / gem / star / bse
    is_st: bool
    effective_from: pd.Timestamp
    effective_to: pd.Timestamp | None   # None = 至今
    up: float
    down: float


RULESET_VERSION = "cn_a_2026_07"


def infer_board(code: str) -> str:
    """按代码前缀推断板块：300/301→gem；688/689→star；8/4 开头→bse；其余 main。"""


def resolve_limit(board: str, is_st: bool, date: pd.Timestamp) -> LimitRule:
    """按 (board, is_st, date) 查唯一规则。

    Raises:
        LimitRuleError: 命中 0 条或多条（禁止回落默认值）
    """


def build_limit_prices(
    close: pd.DataFrame,
    adj_factor: pd.DataFrame,
    st: pd.DataFrame,
    dates: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回 (limit_up_price, limit_down_price)，均为 raw 价格口径。

    ref_price(t) = close(t-1) * adj(t-1) / adj(t)      # 除权参考价
    limit_up(t)  = ref_price(t) * (1 + rule.up)
    limit_down(t)= ref_price(t) * (1 + rule.down)
    """


def special_no_limit_mask(
    dates: pd.DatetimeIndex, codes: pd.Index, snap: "UniverseSnapshot"
) -> pd.DataFrame:
    """True = 当日不适用涨跌停限制（IPO 前 5 个交易日）。

    退市整理期首日依赖 `delist_start_date`；字段缺失时返回全 False 并在报告标注
    `delist_period_handled=false`（U-D2）。
    """
```

### 4.3 Universe 快照（D5，`core/universe_data.py`）

```python
@dataclass
class UniverseSnapshot:
    list_date: pd.Series               # index=stock, value=Timestamp
    delist: pd.DataFrame               # stock, delist_date, delist_return?, delist_reason?
    manifest: dict | None              # source/fetched_at/rows/sha256/schema_version
    status: str                        # "corrected" | "uncorrected"


def load_universe_snapshot(data_dir: Path, universe_dir: Path | None) -> UniverseSnapshot:
    """加载 list_date / delist / manifest；任一缺失 → status='uncorrected' + warning。

    默认目录为 `data_dir / "universe"`（随 data_dir 解析，不读仓库固定路径）。
    """


def listing_mask(
    dates: pd.DatetimeIndex, codes: pd.Index, snap: UniverseSnapshot
) -> pd.DataFrame:
    """True = 当日已上市且未退市。缺失字段按「不限制」处理并在 status 中标注。"""
```

### 4.4 归因报告（D6，`core/change_report.py`）

```python
@dataclass
class LayerDiff:
    layer: str                  # L1_limit_mask ... L6_nav
    changed: int
    added: list[str]
    removed: list[str]


@dataclass
class ChangeReport:
    before_run: str
    after_run: str
    nav_before: float
    nav_after: float
    layers: list[LayerDiff]
    nav_recomputed: float
    residual: float             # |nav_recomputed - nav_after|，要求 < 1e-8
    attribution_complete: bool  # 若 L6 有差异则 L5 必须有差异、L5 有差异则 L4 必须有差异；
                                # 逐层向上回溯任一断裂 → False（下游吸收不算断裂）
```

### 4.5 数据端口（D7，`core/data_provider.py`）

```python
class DataProvider(Protocol):
    def load_price(self, kind: str) -> pd.DataFrame: ...
    def load_aux(self, kind: str) -> pd.DataFrame | None: ...
    def load_universe(self) -> UniverseSnapshot | None: ...


class PklDataProvider:
    """现有 pkl 目录的适配器；本批不接入 DataManager 调用路径（P-004 负责迁移）。"""
```

---

## 5. 替代方案与代价

### 5.1 方案 A：价格法涨跌停 + 规则表（选择）

- **描述**：D3 + D4，判定改为「t 日开盘价 vs 除权参考价×限幅」；ST/板块/日期段由规则表解析。
- **优点**：无前视（开盘即可观测）；对除权、四舍五入、ST 规则切换稳健；与交易所定义同构。
- **缺点**：需要 `adj_factor` 与 `st` 完整；规则表漏板块会失败（设计为 fail-fast，暴露而非静默）。
- **选择理由**：RESEARCH §6.4 推荐 U-A+U-B；A8/A19-A22 的官方口径均以「限价」定义，不以收益阈值定义。

### 5.2 方案 B：收益阈值 + `shift(1)`（否决）

- **描述**：保留 `returns >= 0.095` 判定，只把 returns 后移一天。
- **优点**：改动最小（1 行）。
- **缺点**：除权日仍会产生假涨跌停；ST 5%/10% 切换与板块 20%/30% 无法表达；P21 的口径耦合未解。
- **否决理由**：只消除时间前视，未消除口径错误（RESEARCH §11.4 明确指出阈值法对除权不稳健）。

### 5.3 方案 C：直接引入 Qlib/Pandas-ta 规则（否决）

- **描述**：用第三方库的涨跌停/复权实现替换本仓逻辑。
- **优点**：少写代码。
- **缺点**：A 股 ST/板块/日期段规则不在通用库内；引入新依赖；版本漂移；与本仓 pkl 契约不匹配。
- **否决理由**：RESEARCH §6.3/§12 已论证外部框架默认口径不可直接对拍（A27/A28），替换会把不确定性引入核心路径。

### 5.4 方案 D：退市数据运行时接 Tushare（否决）

- **描述**：`DataManager` 启动时在线拉取 `stock_basic`。
- **优点**：数据总是最新。
- **缺点**：离线不可复现、token/限频依赖、同一 commit 两次回测可能不同。
- **否决理由**：A24 官方建议本地存储；§12.5 已裁决 D-A 本地快照 + 显式 `--refresh`。

---

## 6. 数据结构

### 6.1 六层归因的层定义

| 层 | 文件 | 内容 | 产生位置 |
|----|------|------|----------|
| L1 | `L1_limit_mask.csv` | bool 矩阵：当日是否因涨跌停/停牌/**上市状态**不可买/卖 | `UniverseFilter` |
| L2 | `L2_tradable.csv` | bool 矩阵：最终 buyable/sellable | `UniverseFilter` |
| L3 | `L3_target_positions.json` | `{date: [stock,...]}` | `_execute_rebalance` |
| L4 | `L4_orders.json` | `{date: [{stock, side, qty, reason}]}` | 订单生成 |
| L5 | `L5_fills.json` | `{date: [{stock, side, qty, price, cost}]}` | `ExecutionSimulator` |
| L6 | `L6_nav.csv` | `date, cash, market_value, total_value` | `tracker` |

### 6.2 `change_report.json` 契约

```json
{
  "schema_version": "1.0",
  "before_run": "runs/base",
  "after_run": "runs/after",
  "nav": {"before": 1000000.0, "after": 998000.0, "diff": -2000.0},
  "layers": [
    {"layer": "L1_limit_mask", "changed": 120, "added": ["000001"], "removed": []},
    {"layer": "L2_tradable", "changed": 118, "added": [], "removed": ["000001"]},
    {"layer": "L3_target_positions", "changed": 40, "added": [], "removed": ["000001"]},
    {"layer": "L4_orders", "changed": 41, "added": [], "removed": ["000001"]},
    {"layer": "L5_fills", "changed": 39, "added": [], "removed": ["000001"]},
    {"layer": "L6_nav", "changed": 1, "added": [], "removed": []}
  ],
  "nav_recomputed": 998000.0,
  "residual": 0.0,
  "attribution_complete": true
}
```

> **Step 9 回写（F-S9-3/F-S9-4，2026-11-10）**：实现采用的实际归因链为 `L6→L5`、`L5→L4`、`L3→L2`、`L2→L1` 四段，**不对 `L4→L3` 做硬判定**——L3 只记录「目标股票集合」（见 §6.1），订单数量随净值/现金变化，且同一目标集合可因资金变化出现买卖方向不同的订单，硬链会误报断链。L1 的定义包含上市状态（listing），以保证 B5 的 L2 变化有上游解释。

---

## 7. 错误处理

| 场景 | 处理 | 用户可见信息 |
|------|------|--------------|
| `get_adj_price` 收到未知 mode | `ValueError` | `未知复权口径: {mode}；允许 raw/hfq/qfq（forward/backward/none 已弃用）` |
| 使用 `forward`/`backward`/`none` 旧名 | `DeprecationWarning` + 正常返回 | `forward→hfq；backward→qfq；none→raw；将于下个 major 移除` |
| 规则表 `(board,is_st,t)` 命中 0 条 | `LimitRuleError`（中断） | `无匹配涨跌停规则: board=gem, is_st=True, date=2021-01-04` |
| 规则表命中多条（区间重叠） | `LimitRuleError`（中断） | `涨跌停规则区间重叠: ...` |
| 代码前缀无法识别板块 | 归入 `main` + **一次性** warning 计数 | 报告 `unknown_board_codes: N` |
| `list_date`/`delist` 缺失 | 不中断；`status="uncorrected"` + warning | 报告 `survivorship: "uncorrected"`、`n_unknown_list`、`n_unknown_delist` |
| `manifest.json` 缺失 | 不中断 | 报告 `data_version: "unknown"` |
| 退市日无可用行情且无 `delist_return` | 按 `last_close` 结算 + warning | 报告 `delist_return_source: "last_close"` |
| 层 dump 目录未提供 | 完全跳过，不产生 I/O | — |
| `change_report` 残差 ≥ 1e-8 | 退出码 1 + `attribution_complete=false` | `净值重算残差 {residual} 超过 1e-8` |

---

## 8. 不变式（Invariants）

1. 新口径（`legacy_adjustment=False`）下，**任何成交价与估值价都不含 `adj_factor`**（E1：`get_adj_price(..., "raw")` 唯一来源）。
2. 掩码第 `t` 行只依赖 **≤ t 日开盘**可得的输入：停牌 t、ST t、上市状态 t、开盘价 t、`close ≤ t-1`；`ref_price(t)` 中的 `adj(t)` 为**当日生效的除权因子**，除权日盘前已由交易所公告确定（除权参考价本身即盘前公布），不构成前视。未来数据扰动不得改变该行。
3. 规则表查找对任意 `(board, is_st, t)` **恰好 1 条**命中；0 或多条一律异常，禁止默认值回落。
4. 退市/上市数据缺失时**不得静默**：必须出现 `survivorship` 与 `n_unknown_*` 报告字段。
5. `legacy_adjustment=True` 时与切换前**冻结基线逐值相等**（`rtol=0`，含 NaN 位置）。
6. 每次行为变更批次独立提交，且其 `change_report.json` 满足 `residual < 1e-8` 与 `attribution_complete=true`。
7. 同一能力只有一个 Protocol；所有登记实现（含 Mock）通过同一套契约符合性测试。
8. 层 dump 默认关闭；关闭时零额外 I/O，且结果与开启时**逐值相等**。
9. `DataProvider` 端口本批**零接线**：无任何生产代码 import `core.data_provider`（E1 可查：`Grep 'from core.data_provider|from core import data_provider' -- '*.py'` 仅命中契约测试）；`PklDataProvider` 仅被契约符合性测试与 Mock 对照引用。

---

## 9. 幻觉抑制审查（Step 4 Review，独立 pass 2026-11-10）

- **执行时点**: DESIGN 完稿后单独执行；与设计写入不同会话、不同模型基座（RULE-1 / RULE-4 / RULE-5 异构复审口径）
- **审查方式**: E1/E3 重验代码事实 + D1-D11 逐项可追溯性 + 不变式自洽检查 + 与 RESEARCH/ADR-017 交叉核对，不依赖设计自报

**E1/E3 验证**:

| 断言 | 命令/位置 | 结果 |
|------|-----------|------|
| `process_single`/`combine_single` 零消费方（D7 收窄依据） | `Grep` 全仓（含 tests/examples/tools） | 仅 `interfaces.py:142/164` 定义 + 文档，**0 个调用方** ✅ |
| `execute_order` 签名不兼容（D7 对齐依据） | `interfaces.py:214-235` vs `execution.py:250-261` | 协议 `price, **kwargs` vs 实现 `open_price + OHLC 可选参` ✅ |
| `UniverseFilter(self.dm, self.cfg.universe)` 传参错配（D11 依据） | `engine_v2.py:195` | `UniverseConfig` 传入期望 `UniverseFilterConfig` 的构造器 ✅ |
| `prepare_test_fixture.py` 存在（D8 前提） | `Glob scripts/prepare_test_fixture.py` | ✅ |
| 证据 commit | `git diff --stat 05af52f 2c34283 -- core filter tests` | 零 diff，E3 绑定有效 ✅ |
| `fetch_universe` 现状 | `Grep fetch_universe` | 仅 RESEARCH 文档 1 处 → 证实设计初稿缺该交付物（F-D3） |

**可追溯性核对**: D1→§3.14/§11.2、D2→§11.3/ADR-017、D3→§11.4/§12.3、D4→§6.2/P5/P6、D5→§11.1/§12.1、D6→§11.2、D7→§11.5/§12.4、D8→P22、D9→§12.4 边界表、D10→D2/D3 衍生、D11→§11.5 P0——**11/11 可追溯，无未验证假设**。

**不变式自洽**: I1-I9 逐条与 §4 接口定义对照——发现 I2 与 `ref_price` 公式、I9 与行为批次范围的表述矛盾（F-D4/F-D2），已修正；其余 7 条自洽。

**发现 7 项（全部回写）**:

| ID | 等级 | 发现 | 修复 |
|----|------|------|------|
| **F-D1** | **P1** | **RESEARCH §11.5 标记为 P0 的「`UniverseConfig`/`UniverseFilterConfig` 双定义 + 默认值漂移」未纳入任何设计决策**——D7 只覆盖协议，D10 只保留旧字段；若不修，B6 完成后配置错配依旧存在（P-007 盲区残差来源之一未闭合） | 新增 **D11**：`from_universe_config()` 转换 + 21 字段级单测 + `engine_v2.py:195` 改经转换；归入 B6；§2.1 映射同步 |
| **F-D2** | P2 | 不变式 9 原文「`core/data.py`/`data_v3.py` 现有调用路径 diff 为 0」与 B3b/B4/B5 修改 data.py **直接矛盾** | 重写为可机械验证口径：「无任何生产代码 import `core.data_provider`；`PklDataProvider` 仅被契约测试引用」 |
| **F-D3** | P2 | **§3.2 模块表缺 `scripts/fetch_universe.py`**（RESEARCH §12.1.3 D-A 的组成部分）；且 `data/` 被 `.gitignore:62` 忽略（P-009 根因），快照不入库的事实未声明 → CI 无法获得退市数据 | 模块表补该脚本（B5 交付物）；§10.1 新增约束 8（不入库 + biased profile 生成样本） |
| **F-D4** | P3 | 不变式 2 原文「`close/adj ≤ t-1`」与 `ref_price(t) = close(t-1)×adj(t-1)/adj(t)` **用到 `adj(t)`** 自相矛盾 | 修正：`adj(t)` 为当日生效除权因子，除权参考价盘前由交易所公告确定，不构成前视（补论证） |
| **F-D5** | P3 | D4 偏离 RESEARCH §6.2 L-A 的 `shift(1)` 建议但未说明理由 | D4 补不采纳理由：昨日停牌 ≠ 今日可交易，`shift(1)` 只消除时间前视不解决语义错误 |
| **F-D6** | P3 | ① RESEARCH P15 引 `engine_v2.py:191`（实为注入分支），构造调用在 **:195**；② §2.1 ST 规则行引 A19-A22 不精确（A19 是退市整理期锚点） | ① RESEARCH P15 已改 ：195 并注记；② 改引 A20/A21/A22 |
| **F-D7** | P3 | D7「`execute_order` 形参对齐」未指明方向（协议改还是实现改） | 注明**以实现签名为准修订协议**（协议是契约，须命名真实形参，删除 `**kwargs`） |

**§9.1-9.3 模板自查**:

- [x] 9.1 所有设计决策可追溯到 RESEARCH.md（11/11 映射表）；无未经验证的假设（E1/E3 重验）；无论证驱动的归因扭曲（F-D4 反向修正：设计服从公式，而非改公式迁就表述）
- [x] 9.2 替代方案 ≥2（§5 共 4 个：1 选择 + 3 否决，均有否决理由）；D4 对 L-A 备选的偏离已补理由（F-D5）
- [x] 9.3 职责边界清晰（§2.3 与 P-011/P-004 的边界表 + D9 明确不做清单）；不越界吞并其他批次

**结论**: **P1 = 1（F-D1，已修复）、P2 = 2（F-D2/F-D3，已修复）、P3 = 4（F-D4~F-D7，已修复）**；11/11 可追溯，不变式自洽（修正后）。**P-012 Step 4 Review 通过**，可进入 Step 5 实施规划。

---

## 10. 对实施的输入

### 10.1 关键工程约束

1. **B3a 与 B3b 必须分两次提交**：命名校正零数值变化（可用冻结基线证明 `rtol=0`）；口径分离才改变结果。
2. **B2/B3b/B4/B5 各自一次提交**，每次提交必须附 `change_report.json`（由 `scripts/change_report.py` 生成）。
3. `filter/universe_filter_clean.py` 的 `UniverseFilterConfig` 4 个阈值字段**保留但弃用**，不得删除（外部可能直接构造该 dataclass）。
4. `legacy_adjustment` 只影响取价与收益口径（`_exec_price` + `_calculate_returns`），不影响规则表/掩码/退市逻辑（避免兼容开关扩散）。
5. 夹具 `baseline` profile **逐字节不变**（27 项数据测试依赖 `adj≡1`/`suspend≡0`/全 `000`）。
6. 新测试一律使用 `biased` profile；禁止读 `data/test_ashare`（本地 gitignore，CI 不可用）。
7. 不引入新运行时依赖（`pandera`/`hypothesis` 仅可作测试可选依赖，且 CI 必须能跳过）；夹具/快照/层 dump 统一 **CSV + JSON**（`pyarrow` 未在 `pyproject.toml` 声明，见 IMPL F-I3）。
8. `data/` 被 `.gitignore:62` 忽略（P-009 根因）：`data/universe/` 快照**不入库**，由 `scripts/fetch_universe.py` 本地生成；CI 与新测试的退市/上市样本一律由 `prepare_test_fixture.py --profile biased` 生成，禁止依赖本地手放文件。

### 10.2 风险与缓解

| 风险 | 缓解 |
|------|------|
| 成交/估值切 raw 后，费用、手数、现金与旧报告不可比 | B3b 单独批次 + `change_report` + CHANGELOG 明示「行为变更」 |
| 退市结算需要 tracker 新接口（`close_position` 语义） | 复用 `_force_liquidation` 路径，先加参数化入口；若 tracker 无对应 API，在 IMPL 中以最小方法补齐并加单测 |
| 规则表板块推断边界（689 CDR / 4xx 北交所） | 单测覆盖 `300/301/688/689/8xxxxx/4xxxxx/000/600` 七类前缀 |
| 双 profile 夹具导致测试选错 profile | 新测试统一 fixture 工厂 `biased_dm()`；`conftest.py` 断言 profile 标记 |
| `change_report` 需要两次运行，CI 成本上升 | 仅行为变更批次运行；CI 只跑 1 个小样本（20 日×10 股） |
| 旧阈值字段弃用后仍被外部使用 | 保留字段 + `DeprecationWarning`，不删除；下个 major 再移除 |

---

## 11. 未决项登记（四元块）与决策矩阵

**11.1 未决项登记**：

- **U-D1 退市结算的价格来源优先级**
  - **判据**：`delist_return` 存在时用其结算、否则用最后收盘价；两者都缺则跳过该持仓并计入 `unclosed_positions`
  - **触发条件**：B5 实施前，用真实退市样本验证
  - **当前倾向**：`delist_return` > `last_close` > 跳过并告警
  - **证据等级**：E3（RESEARCH §11.1）+ A19（退市整理期 15 日）

- **U-D2 退市整理期首日无涨跌幅的数据表达**
  - **判据**：数据契约是否提供 `delist_start_date`；提供则纳入规则白名单，不提供则报告 `delist_period_handled: false`
  - **触发条件**：B2/B5 设计确认时
  - **当前倾向**：本批不处理整理期首日（缺字段），在报告中显式声明
  - **证据等级**：E1（`delist.csv` 字段设计）

- **U-D3 规则表 `bse` 是否设 ST 标识**
  - **判据**：交易所规则确认；未确认前保留 `is_st=True` 行（同 30%）保证查找闭合
  - **触发条件**：出现北交所 ST 样本
  - **当前倾向**：保留闭合行，不视为独立规则
  - **证据等级**：T1（A20/A22）待逐条核对

- **U-D4 `limit_rules` 的维护者与发布方式**
  - **判据**：是否出现非开发者修改需求；出现则升级为 YAML（R-B）
  - **触发条件**：规则变更频率 > 2 次/年，或维护者非开发
  - **当前倾向**：内置常量（R-A，已裁决）
  - **证据等级**：E3

**11.2 决策矩阵**：不启用。本批决策均为**可逆（Type-2）**——`legacy_adjustment` 开关、规则表可替换、`DataProvider` 未接线、夹具双 profile 均可低成本回退。

---

## 12. 回退点

| 批次 | 回退方式 | 影响 |
|------|----------|------|
| B1 观测网 | 删除新增测试/脚本，`dump_layers` 默认关 | 零生产影响 |
| B2 ST 规则表 | `git revert` 单提交 | 恢复 4.8%/9.5% 常数 |
| B3a 命名 | `git revert` 单提交 | 恢复 `forward/backward` |
| B3b 口径分离 | `legacy_adjustment=True` 即可复现旧值；或 `git revert` | 报告数值回到旧口径 |
| B4 掩码时点 | `next_day_tradable_mode="oracle"` + `git revert` | 恢复旧掩码 |
| B5 退市 | 删除 `data/universe/` 即走降级；或 `git revert` | 回到静态池 |
| B6 接口 | `git revert` 单提交 | 协议回到旧定义 |

---

**Review 签字**: _________ 日期: _________
