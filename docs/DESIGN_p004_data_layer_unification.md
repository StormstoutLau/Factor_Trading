# DESIGN：P-004 数据层统一（门面保留 + 端口注入）

> **批次**: P-004 · **T1**（Layer-1：`core/data.py`、`core/data_v3.py`、`core/interfaces.py`、`tests/test_contract_conformance.py`）
> **上游**: [RESEARCH_p004_data_layer_unification.md](RESEARCH_p004_data_layer_unification.md)（Step 2 Review 通过；§9 RULE-5 复审 pass，3 P3 已回写 + 3 观察）
> **下游**: IMPL_p004_data_layer_unification → CHECKLIST_p004_data_layer_unification
> **代码证据时点**: HEAD `8f5e277`（E1 2026-11-11；调研基线 `3af285a`，其间仅 docs 变更）
> **状态**: Step 3-4 完稿 + Step 4 Review 通过（§8）+ **RULE-5 异构复审 pass**（§9：0 P1，1 P2 已修入 §4.1，1 P3 已更正，3 观察）；待进 Step 5

---

## 1. 目标与边界

**目标**（三个零行为批次）：

| 批次 | 目标 |
|------|------|
| **B1** | `DataManager` 注入 `DataProvider`，价格/辅助/股票池读取收敛为单一 I/O 路径；归一化/缓存/安全默认值留在门面 |
| **B2** | 删除死 API：`DataLoaderV3` 的 `from_data_manager` / `_load_from_data_manager` / `to_data_manager_compatible` / `from_hdf5`；`interfaces.AbstractDataManager` |
| **B3** | 协议治理：`get_adj_price` 形参名以实现为准；纳入 `universe_status`；契约测试从「成员集合」升级为「成员 + 签名」 |

**不覆盖**（明确出界）：

- **B4 端口扩全**（`returns`/`get_adj_price` 等派生进入端口）——U-P004-2 未裁决，且会改变端口语义；
- **agents `data_dir` 直读迁移**（`agent_framework.py:967/977`）——`_industry_data` 现为**原样 pickle 对象**（注解 `pd.DataFrame` 但实际未归一化），改走 `dm.industry` 会引入对齐语义，非零行为；留 B4 单独取证（RESEARCH B2 建议在本设计中**主动收窄**，理由见 D5）；
- filter/ 非 clean 孤儿模块（TD-5 范畴）；V3 引擎取价/掩码；P-005 DuckDB；
- **RESEARCH §6 B3 的两个扩展子项**：「多资产成员按是否接线决定去留」「消费方类型标注迁移到协议」——本批 B3（D4）收敛为两处形参对齐 + `universe_status` + 契约测试升级，上述两子项本批不裁决，留 B4 单独取证（**Step 8 补登**，F-S8-P004-2）。

**能力边界**：不引入第二真实数据源；适配器可替换性只由 `MockDataProvider` 注入测试证明。

---

## 2. 设计决策（D1-D6）

| # | 决策 | 被拒方案 | 拒绝理由 | 代价 |
|---|------|----------|----------|------|
| **D1** | **门面保留 + 端口注入**：`DataManager.__init__(config, provider: DataProvider \| None = None)`；缺省构造 `PklDataProvider` | M-B 端口扩全替换门面 / M-C V3 取代 | M-B 改 6 生产 + 19 测试、归因不可分离；M-C 能力缺口（24 vs 10 公开成员、`from_data_manager` 零调用） | 类不删除（登记 U-P004-1） |
| **D2** | **映射单一来源**：`file_map`/`aux_files` 由 `BacktestConfig` 字段生成，不再在 `_load_price_data` 内重建；`aux_files` **过滤 falsy 值**（`mktcap_file=None` 不得回落到默认 `mktcap.pkl`） | 复用 `PklDataProvider` 默认映射 | 默认映射与 cfg 可配置文件名可能不一致（`mktcap_file` 默认 None），会产生新读取行为 | — |
| **D3** | **B2 删除清单**：V3 四个死 API + `AbstractDataManager`（RULE-5 观察 1）；同步删除 `test_to_data_manager_compatible` | 保留并标 `@deprecated` | 零调用代码无兼容价值；本仓无外部消费者 | 测试数 −1 |
| **D4** | **协议以实现为准**（两处不一致）：`get_adj_price(price_type: str = "close", adjustment_type: str = "hfq")`、`load_factor(factor_file: str)`；新增 `universe_status` 属性；契约测试新增 `EXPECTED_SIGNATURES` | 改实现形参为协议名（`adjustment` / `name`） | 实现有 **15 处**生产 `get_adj_price` 消费调用（engine_v2 2 + agents 13）+ **1 处实现内部关键字自调用** `self.get_adj_price("close", adjustment_type=adj_type)`（data.py:455，全仓唯一 `adjustment_type=` 关键字用法——实现形参名的既有真实依赖）；`load_factor` **9 处**生产调用（engine_v2 1 + agents 5 + multi_strategy 1 + examples 2，**R5 复审更正**：初稿 7 处漏 examples）。协议 0 处关键字调用。改实现属行为面扩散（同 P-012 D7 `execute_order` 先例：以真实签名为准修订协议） | 协议面 +1 成员、2 处形参改名 |
| **D5** | **agents 直读移出本批**（RESEARCH B2 建议收窄） | 按 RESEARCH B2 一并改走 `provider.load_aux` | `_industry_data` 实际保存**未归一化** pickle 对象（`:970`），而 `dm.industry` 是**对齐后的 DataFrame**（P-010 语义）；替换会改变 `:1128` 的 `.loc[date]` 行为，不满足零行为 | B4 承接 |
| **D6** | **golden 口径更正**：现为 **7 份（G1-G7）**，RESEARCH P9 的「6 份（G1-G6）」为笔误，已回写 | 沿用 6 份 | 事实错误（P-014 已增 G7）；`tests/golden/G7.json` 存在 | 文档更正 |

---

## 3. 不变量（I1-I6，本批自证）

| ID | 不变量 | 判据 |
|----|--------|------|
| **I1** | 全量测试 **636 passed**（635 − 删除 1 + 新增 2，见 §5） | `pytest tests`（Agg） |
| **I2** | `DataManager` 公开 API 零变化（仅 `__init__` 新增可选 `provider`），既有 6 个构造点零改动 | `Grep` + 契约测试 |
| **I3** | P-010 安全默认值语义不变：suspend/st 缺失→全 0；industry/mktcap 缺失→None；幂等 guard 不变 | `tests/test_data_aux_defaults.py` 4 项 |
| **I4** | 复权三口径与弃用告警不变（raw/hfq/qfq + forward/backward/none 映射） | `tests/test_adjustment*.py` 13 项 |
| **I5** | golden **G1-G7** 数值不变（分字段容差、计数精确） | `tests/test_golden_baseline.py` 参数化 7 项 |
| **I6** | 死 API 引用归零；协议签名测试通过 | `Grep` = 0；新增契约测试 |

---

## 4. 实现规格

### 4.1 B1：端口注入（`core/data.py`）

```python
from core.data_provider import DataProvider, PklDataProvider

class DataManager:
    def __init__(self, config: BacktestConfig, provider: Optional[DataProvider] = None):
        self.cfg = config
        self.data_dir = config.data_dir
        self._provider = provider if provider is not None else self._build_provider(config)
        # ...既有字段不变...

    @staticmethod
    def _build_provider(config: BacktestConfig) -> PklDataProvider:
        price_map = {
            "close": config.close_file,
            "open": config.open_file,
            "high": config.high_file,
            "low": config.low_file,
            "adj_factor": config.adj_factor_file,
        }
        aux_map = {
            kind: name
            for kind, name in {
                "suspend": config.suspend_file,
                "industry": config.industry_file,
                "st": config.st_file,
                "mktcap": config.mktcap_file,   # 默认 None → 被过滤
            }.items()
            if name
        }
        return PklDataProvider(
            config.data_dir,
            file_map=price_map,
            aux_files=aux_map,
            universe_dir=getattr(config, "universe_dir", None),
        )
```

| 方法 | 改后读取 | 保留在门面 |
|------|----------|------------|
| `_load_basic_data` | `self._provider.load_price("close")`；**删除**显式 `close_path.exists()` 守卫 | 异常包装日志、日期索引、`_apply_date_filter` |
| `_load_price_data` | 先按白名单校验 kind（保留原 `ValueError` 文案）→ `self._provider.load_price(kind)`；**删除** `file_map` 重建与 `exists()` 守卫 | DatetimeIndex、日期过滤、列序对齐、`_cache` |
| `_load_auxiliary_data` | **保留 cfg-falsy 守卫**（R5 复审修正）：`if self.cfg.{kind}_file:` 才调 `self._provider.load_aux(kind)`；返回 `None`（文件缺失）→ 原 warning + 默认值。**禁止**对 cfg-falsy 的 kind 调 `load_aux`——`aux_files` 已过滤该键，provider 会 `raise ValueError("未知辅助数据类型")`（`mktcap_file` 默认 `None`，默认配置下必触发） | suspend/st→全 0；industry/mktcap→None；`_aux_loaded` 幂等 |
| `_load_and_align_data` | 形参由 `file_path` 改为 `data`，**删除** `pd.read_pickle` | dict/Series 归一化、日期交集、列对齐（逐行等价） |
| `universe` | `self._provider.load_universe()` | `_build_universe_status` 全部逻辑 |

**行为等价性**：正常路径逐分支等价；异常路径两处漂移（均无测试/现实覆盖，已在 §6 登记）——① 价格文件缺失：自定义「价格文件不存在: …」→ pandas 原生 `FileNotFoundError`（类型不变）；② `industry_file` 配置为 falsy（现存怪相）：现状 `data_dir / ""` = 目录自身 → `read_pickle` 抛 `IsADirectoryError`，B1 后 aux_map 过滤该键 → 门面按 falsy 守卫跳过（industry 保持 `None`，不再抛）——**异常路径收敛为更合理语义**，正常配置（truthy）行为不变。

> kind 白名单现状三处硬编码（`_load_price_data` 内 file_map、`preload_data` 循环 L654、`_build_provider` price_map）：IMPL 以模块级常量 `_PRICE_KINDS` 收敛为单一来源（D2 延伸，R5 复审观察 1）。

### 4.2 B2：死 API 删除

| 文件 | 删除对象 | 行锚 |
|------|----------|------|
| `core/data_v3.py` | `__init__` 的 `from_hdf5` 形参 / docstring / `self._from_hdf5` | L30、L35、L38 |
| `core/data_v3.py` | `from_data_manager`（classmethod） | L58-70 |
| `core/data_v3.py` | `_load_from_data_manager` | L103-128 |
| `core/data_v3.py` | `to_data_manager_compatible` | L210-222 |
| `core/interfaces.py` | `AbstractDataManager`（零子类/零实例化） | L437-457 |
| `tests/test_data_v3_compatibility.py` | `test_to_data_manager_compatible` | L78-85 |

> 删除后由 `black`/`mypy`/未使用导入检查兜底（`pickle` 仍用于 `save/load`，`pd` 仍用于 `from_pandas_dataframes`）。

### 4.3 B3：协议对齐（`core/interfaces.py` + 契约测试）

```python
class IDataManager(Protocol):
    # ...既有 7 成员...

    @property
    def universe_status(self) -> dict[str, Any]:
        """股票池快照状态（报告字段；缺失时降级，P-012 D5）。"""
        ...

    def get_adj_price(self, price_type: str = "close", adjustment_type: str = "hfq") -> pd.DataFrame:
        """获取复权价格（raw/hfq/qfq；旧名 forward/backward/none 已弃用）。"""
        ...

    def load_factor(self, factor_file: str) -> pd.DataFrame:
        """加载因子数据。"""
        ...
```

契约测试新增（`tests/test_contract_conformance.py`）：

```python
EXPECTED_SIGNATURES: dict[str, list[str]] = {
    "get_adj_price": ["self", "price_type", "adjustment_type"],
    "load_factor": ["self", "factor_file"],
    "get_data_info": ["self"],
    "get_asset_info": ["self", "symbol"],
}

def test_protocol_signatures():
    for name, expected in EXPECTED_SIGNATURES.items():
        assert list(inspect.signature(getattr(IDataManager, name)).parameters) == expected
        assert list(inspect.signature(getattr(DataManager, name)).parameters) == expected
```

DI 注入测试（同文件，避免新增文件）：

```python
class _MockProvider:
    def __init__(self, close: pd.DataFrame) -> None:
        self._close = close

    def load_price(self, kind: str) -> pd.DataFrame:
        return self._close

    def load_aux(self, kind: str):
        return None

    def load_universe(self):
        return None

def test_data_manager_accepts_injected_provider():
    close = pd.DataFrame(
        {"A": [1.0, 2.0], "B": [3.0, 4.0]},
        index=pd.date_range("2020-01-01", periods=2),
    )
    dm = DataManager(BacktestConfig(), provider=_MockProvider(close))
    assert list(dm.stock_codes) == ["A", "B"]
```

> `EXPECTED_MEMBERS[IDataManager]` 增 `"universe_status"`。

---

## 5. 验证项（V1-V8）

| # | 验证项 | 判据 |
|---|--------|------|
| V1 | 全量测试 | **636 passed**（635 − `test_to_data_manager_compatible` + `test_protocol_signatures` + `test_data_manager_accepts_injected_provider`），`MPLBACKEND=Agg` |
| V2 | golden | **G1-G7** 7 项参数化全过（数值/计数） |
| V3 | P-010 默认值 | `test_data_aux_defaults` 4 项全过（含幂等计数 =1） |
| V4 | 复权口径 | `test_adjustment`(11) + `test_adjustment_semantics`(4，Step 9 实读更正：原写 2) 全过 |
| V5 | 门禁 | `mypy core` 0 errors；`black --check` 无变更 |
| V6 | 死 API 归零 | `Grep 'from_data_manager\|_load_from_data_manager\|to_data_manager_compatible\|from_hdf5\|AbstractDataManager'` = 仅 0 处代码命中 |
| V7 | 契约 | `test_protocol_members` + `test_protocol_signatures` + `test_execute_order_signature` 全过 |
| V8 | 消费者回归（可选） | `verify_p015.py` 五 case `28 断言（失败 0）+ 豁免 1`，exit 0 |

---

## 6. 风险与回退

| 风险 | 预案 |
|------|------|
| `aux_files` 未过滤 `mktcap_file=None` → 意外读取默认 `mktcap.pkl`，改变过滤/中性化行为 | D2 显式过滤；V3 断言 `dm.mktcap is None` |
| 价格异常文案变化被下游捕获依赖 | 全仓 0 断言（RESEARCH P9）；异常类型保持 `FileNotFoundError`；列入 IMPL 记录 |
| `_load_and_align_data` 形参语义变化破坏 `test_data_aux_defaults` 的 monkeypatch | 保留方法名与位置参数；测试 wrapper 传参透传，V3 实测 |
| 删除 `AbstractDataManager` 影响未知外部导入 | 全仓 `Grep` = 1（仅定义）；`mypy core` + `pytest` 兜底 |
| B3 协议改动导致 mypy 报 `MockDataManager` 缺 `universe_status` | mypy 门禁范围 = `core`；`tests/` 不在门禁；运行时鸭子类型不受影响 |
| 单批三类改动混杂、归因困难 | B1/B2/B3 各自独立提交；每批均可单独 `git revert` |
| **cfg-falsy 分支遗漏 → 默认配置 `dm.mktcap` ValueError**（R5 复审 P2，已修入 §4.1） | `aux_files` 过滤后 provider `.get(kind)` 为 None 即 raise；门面必须保留 `if self.cfg.{kind}_file:` 守卫；V3 断言 `dm.mktcap is None` 兜底 |
| `industry_file` falsy 异常路径漂移（`IsADirectoryError` → 静默 None，R5 复审观察 2） | 无测试/现实覆盖；正常配置行为不变；登记于行为等价性声明，B4 统一异常语义 |

---

## 7. 排除的低效操作

- 不新增 `DataProvider.from_config()` 类方法（一次性构造，避免过度抽象）；
- 不引入 DI 容器 / 组件注册；
- 不改 `_load_and_align_data` 的 dict 归一化逻辑（逐行保留）；
- 不做 agents `data_dir` 迁移与端口扩全（B4）；
- 不动 filter/ 孤儿模块（TD-5）；
- 不为「文档文案」新增测试；异常文案变化由现有门禁承担。

---

## 8. Step 4 Review（设计文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 每个决策均可追溯到 RESEARCH 事实（D1↔P1/P2/P3；D2↔P6；D3↔P2/观察 1；D4↔P7/F-R5-P004-2；D5↔P5 复核；D6↔P9 更正）
- [x] 无未经验证的假设：`PklDataProvider` 的 3 方法与 cfg 字段映射已逐行读码；`_load_and_align_data` 唯一调用方（4 处）与 monkeypatch 依赖已核实；`AbstractDataManager` 零消费方已 `Grep`；**D4 的 4 个签名断言已逐项读码核对**（`get_adj_price` / `load_factor` / `get_data_info` / `get_asset_info`），并据此发现第二处不一致（`load_factor`），已回写 RESEARCH P7
- [x] 被拒方案均给出理由与代价（M-B/M-C、DEPRECATED、改实现形参）
- [x] 职责边界清晰（§1 列 B4 与 TD-5 出界，D5 说明收窄依据）
- [x] 零行为可判：I3/I4/I5 为既有测试，I6 为新增契约测试；不预填读数（Step 9 回填）
- [x] 回退点：三批各自独立提交，单批 `git revert` 可退

**Step 4 Review 结论：通过**。可进入 Step 5 IMPL。

---

## 9. RULE-5 异构复审（用户指派 2026-11-11）

**复审基座声明**：复审方 GLM-5.3-Flash ≠ 设计作者 DeepSeek-V4.1-Flash（异构性成立）。复审权限单向：只标记问题，不改判作者结论。复审对象 = 本文档 Step 3-4 稿（基线 HEAD `8f5e277`，复审时点工作区含本文档未提交稿）。

### 9.1 E1 独立重放（签名与调用计数）

| # | 项 | 读数 | 与初稿 |
|---|----|------|--------|
| 1 | `get_adj_price` 四签名 | 协议 `adjustment`（interfaces L51）≠ 实现 `adjustment_type`（data L465-466）；ABC 沿协议名（L452） | ✅ 复现 |
| 2 | `load_factor` 四签名 | 协议 `name`（interfaces L63）≠ 实现 `factor_file`（data L521）；`get_data_info(self)` L591 / `get_asset_info(self, symbol)` L619 | ✅ 复现（设计期补核的第二处不一致成立） |
| 3 | `get_adj_price` 生产调用 | **15 处消费调用**（engine_v2 2 + agents 13）+ **1 处实现内部关键字自调用** `adjustment_type=`（data.py:455，全仓唯一关键字用法） | ✅ 复现 + 补强论据（观察 3） |
| 4 | `load_factor` 生产调用 | **9 处**（engine_v2 1 + agents 5 + multi_strategy 1 + **examples 2**：demo:319、simple:77） | ❌ 初稿 7 处漏 examples → 已更正（F-D-R5-P004-2） |
| 5 | `DataLoaderV3.load()` 连锁 | `cls()` 无参构造（L254），删 `from_hdf5` 形参无连锁 | ✅ 设计成立 |
| 6 | B2 删除清单行锚 | data_v3 L30/35/38、L58-70、L103-128、L210-222；interfaces L437-457；test L78-85 | ✅ 全部命中 |
| 7 | D5 行为差异证据 | agent_framework L970 `pickle.load`（原样对象）vs `dm.industry`→`_load_and_align_data`（L349 对齐）；消费点 L1128 `.loc[date]` | ✅ 收窄决策成立 |

### 9.2 E2 规格推演（cfg-falsy 分支）

`mktcap_file: str | None = None`（config.py L360）为**默认 falsy** → `_build_provider` 的 `aux_files` 过滤该键 → `PklDataProvider.load_aux("mktcap")` 走 `self.aux_files.get(kind)` = None → `raise ValueError("未知辅助数据类型")`（data_provider.py L66-69 行为）。初稿 §4.1 `_load_auxiliary_data` 规格只写「`load_aux(kind)`；`None` → warning + 默认值」——**照规格实现，默认配置下任何 `dm.mktcap` 访问必 ValueError**（现状语义 = cfg falsy 跳过、保持 `None`；端口协议未暴露 `aux_files`，门面无法查 provider 内部映射）。

### 9.3 E4 结论（0 P1 / 1 P2 已修 / 1 P3 已更正 / 3 观察）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| **F-D-R5-P004-1** | **P2** | §4.1 `_load_auxiliary_data` 规格缺 **cfg-falsy 守卫分支**——`mktcap_file` 默认 `None`，照初稿实现默认配置必崩（`ValueError`）；与现状「跳过保持 None」语义不符 | ✅ **已修入 §4.1**（保留 `if self.cfg.{kind}_file:` 守卫）+ §6 风险表登记；V3 断言 `dm.mktcap is None` 兜底 |
| **F-D-R5-P004-2** | P3 | D4 被拒理由 `load_factor`「7 处」漏 examples 2 处，实为 **9 处** | ✅ 已更正 D4 |
| （观察 1） | — | **kind 白名单三处硬编码**（`_load_price_data` file_map / `preload_data` L654 / `_build_provider` price_map）——D2「单一来源」未覆盖 kind 列表 | ✅ 已写入 §4.1：IMPL 以 `_PRICE_KINDS` 常量收敛 |
| （观察 2） | — | `industry` 分支无 cfg 守卫为**现存怪相**（`industry_file` falsy → `data_dir / ""` = 目录 → `IsADirectoryError`）；B1 后收敛为 falsy 守卫跳过——异常路径漂移 | ✅ 已登记于 §4.1 行为等价性 + §6；正常配置行为不变，B4 统一异常语义 |
| （观察 3） | — | data.py:455 `self.get_adj_price("close", adjustment_type=adj_type)` 为全仓唯一 `adjustment_type=` **关键字自调用**——实现形参名的既有真实依赖，D4「以实现为准」的最强论据（初稿未引用） | ✅ 已补入 D4 理由列 |

> 复核确认：D1-D6 六项决策、I1-I6 不变量、V1-V8 验证项、§4.2/§4.3 代码规格经独立重放全部成立；Step 4 自查声明与实况一致。P2 为规格完备性缺陷（有测试护栏兜底但照稿实现必红），已在 Step 5 开工前修正；无 P1。

### 9.4 复审结论

**pass（0 P1 / 1 P2 已修入 §4.1 / 1 P3 已更正 / 3 观察已吸收）**。设计主结构（D1 门面保留 + 端口注入、B1→B2→B3 三批、零行为判据）经独立推演成立。Step 5 IMPL 必须按修正后规格实现：`_load_auxiliary_data` 保留 cfg-falsy 守卫；`_PRICE_KINDS` 单一来源；B2 清单含 `AbstractDataManager`；B3 契约测试含 `EXPECTED_SIGNATURES` 四签名。
