# IMPL：P-004 数据层统一（B1 端口注入 / B2 死 API 删除 / B3 协议对齐）

> **批次**: P-004 · **T1**（Layer-1：`core/data.py`、`core/data_v3.py`、`core/interfaces.py`、`tests/test_contract_conformance.py`、`tests/test_data_v3_compatibility.py`）
> **上游**: [DESIGN_p004_data_layer_unification.md](DESIGN_p004_data_layer_unification.md)（D1-D6 / I1-I6 / §4 实现规格 / §9 RULE-5 复审 1 P2 已修）
> **下游**: CHECKLIST_p004_data_layer_unification
> **代码证据时点**: HEAD `c4aad0b`（2026-11-11，工作区干净）
> **状态**: Step 5 完稿 + Step 6 Review 通过（§7）；Step 9 记录待回填（§8）

---

## 1. 外部锚点与验证（F1-F4）

### 1.1 降级链（F3）

`mcp_english-search_search_web / search_academic` → **HTTP 522**（4 次查询全部失败）→ 切换内置 `WebSearch`（3 组查询成功）→ 读到锚点 E1-E7；`cosmicpython.com` 章节页 `WebFetch` 返回空（本地抓取器）→ 该条标记**未验证**，正文不用于结论。

### 1.2 锚点清单（F1/F2；读取日均为 2026-11-11）

| ID | 来源 | 发布日 | 版本 / 形态 |
|----|------|--------|-------------|
| **E1** | Cockburn, *Hexagonal Architecture (Ports & Adapters)* | 2005-09-04 | HaT Technical Report 2005.02（v0.9） |
| **E2** | PEP 544 *Protocols: Structural subtyping* | 2017-03-05 | Status **Final**；Python 3.8+ |
| **E3** | Fowler, *Strangler Fig* | 2024-08-22（原文 2004-06-29） | bliki 页面 |
| **E4** | Feathers, *Testing Effectively With Legacy Code*（节选） | 2005-01-21 | 书 2004 版；InformIT 文章页 3 |
| **E5** | Microsoft Qlib, *Data Layer: Data Framework & Usage* | 读取日页面 | 文档 stable（search 索引标 0.9.7） |
| **E6** | Nunkesser, *Using Hexagonal Architecture for Mobile Applications* | 2022 | ICSOFT 2022, pp. 113-120；DOI `10.5220/0011075100003266` |
| **E7** | Python 标准库 `inspect`（`inspect.signature`） | 读取日页面 | docs 3.15；签名语义自 3.3 稳定，运行时 3.12 |
| E8 | *Architecture Patterns with Python*（ch.13 Dependency Injection） | 未验证 | **未验证**：章节页抓取为空，仅搜索摘要，不用于结论 |

### 1.3 引用验证表（F4）

| 引用 | ID | 验证方式 | 状态 | 命中 / 差异 |
|------|----|----------|------|-------------|
| E1 | `alistair.cockburn.us/hexagonal-architecture` | WebFetch 正文 | ✅ | 命中：HaT TR 2005.02、2005-09-04、「application … tested in isolation from … devices and databases」 |
| E2 | `peps.python.org/pep-0544/` | WebFetch 正文 | ✅ | 命中：Status Final / Created 05-Mar-2017 / Python-Version 3.8 / structural subtyping |
| E3 | `martinfowler.com/bliki/StranglerFigApplication.html` | WebFetch 正文 | ✅ | 命中：22 August 2024；含「seams」「gradual … move bits of behavior」 |
| E4 | `informit.com/articles/article.aspx?p=359417&seqNum=3` | WebFetch 正文 | ✅ | 命中：Michael Feathers / Jan 21, 2005 / Seam 定义「alter behavior … without editing in that place」 |
| E5 | `qlib.readthedocs.io/en/stable/component/data.html` | WebFetch 正文 | ✅ | 命中：Data Loader → Data Handler → Dataset 分层；存储/加工/模型数据集解耦 |
| E6 | `pdfs.semanticscholar.org/c0dd/…pdf` | WebFetch 正文（首页） | ✅ | 命中：Nunkesser；ICSOFT 2022；DOI `10.5220/0011075100003266`；pp. 113-120 |
| E7 | `docs.python.org/3/library/inspect.html` | WebFetch 正文 | ✅ | 命中：`inspect.signature` 用于内省可调用对象签名 |
| E8 | `cosmicpython.com/book/chapter_13_dependency_injection.html` | WebFetch | **未验证** | 空返回（本地抓取器）；不作为依据 |

### 1.4 锚点 → 工艺映射

| 锚点 | 落入本批的工程决策 |
|------|--------------------|
| E1 / E6 端口-适配器 | `DataProvider`（端口）+ `PklDataProvider`（适配器）；应用核心只依赖端口，测试用 `_MockProvider` 注入（T-1/T-7） |
| E5 Qlib 数据层分级 | 存储读取（provider）与业务语义（对齐/缓存/默认值/复权）分离——本批只合并前者的重复实现（T-2~T-4） |
| E3 Strangler Fig | 不删 `DataManager` 类，保留门面、逐批迁移（B1→B3），避免一次性替换的规格不可知风险 |
| E4 Seam | 构造函数注入 `provider` 即 object seam：不改调用点即可替换行为，支撑零行为回归与 DI 测试 |
| E2 Protocol | `IDataManager` 为结构化协议；**协议在运行时擦除**，签名一致性不会被 mypy 检查形参名捕获——必须显式契约测试（T-7） |
| E7 `inspect.signature` | 契约测试用 `inspect.signature` 比对协议与实现的形参名序列（T-7） |

---

## 2. 任务分解（T-1 ~ T-7）

### T-1 provider 构造与 kind 白名单（B1 / D1 / D2 / DESIGN §9 观察 1）

文件：`core/data.py`

| 位置 | 改动 |
|------|------|
| 模块级（`logger = logging.getLogger(__name__)` 之后） | 新增 `_PRICE_KINDS = ("close", "open", "high", "low", "adj_factor")` |
| 导入区（`from core.config import …` 之后） | 新增 `from core.data_provider import DataProvider, PklDataProvider` |
| `__init__`（L35-73） | 签名改 `(self, config: BacktestConfig, provider: Optional[DataProvider] = None)`；新增 `self._provider = provider if provider is not None else self._build_provider(config)` |
| 类内新增 `@staticmethod _build_provider` | `price_map` 由 `_PRICE_KINDS` + cfg 字段生成；`aux_map` 由 `suspend/industry/st/mktcap` 过滤 **falsy** 生成；`universe_dir=getattr(config, "universe_dir", None)` |

```python
_PRICE_KINDS = ("close", "open", "high", "low", "adj_factor")

@staticmethod
def _build_provider(config: BacktestConfig) -> PklDataProvider:
    price_map = {
        "close": config.close_file, "open": config.open_file,
        "high": config.high_file, "low": config.low_file,
        "adj_factor": config.adj_factor_file,
    }
    aux_map = {
        kind: name
        for kind, name in {
            "suspend": config.suspend_file, "industry": config.industry_file,
            "st": config.st_file, "mktcap": config.mktcap_file,  # 默认 None → 过滤
        }.items()
        if name
    }
    return PklDataProvider(
        config.data_dir, file_map=price_map, aux_files=aux_map,
        universe_dir=getattr(config, "universe_dir", None),
    )
```

> `aux_map` 过滤 falsy 是 **F-D-R5-P004-1（P2）** 的修正前提：若不过滤，provider 会回落到默认 `mktcap.pkl`；过滤后则**门面必须**保留 cfg-falsy 守卫（T-3），否则 `load_aux` 会 `raise ValueError`。

### T-2 价格读取路径（B1 / D2）

| 方法 | 改动 |
|------|------|
| `_load_basic_data`（L207-231） | 删除 `close_path` / `exists()` / `pd.read_pickle`，改 `close_data = self._provider.load_price("close")` |
| `_load_price_data`（L253-311） | 删除 `file_map` 重建与 `exists()`；白名单校验置于 provider 调用**之前**（保留原 `ValueError` 文案），随后 `data = self._provider.load_price(price_type)` |
| `preload_data`（L649-666） | `for price_type in _PRICE_KINDS:`（消除第三处硬编码） |

保留不变：`DatetimeIndex` 归一化、`data.loc[self._trade_dates]`、列序 `data[self._stock_codes]`、`_cache` 写入、异常日志包装。

### T-3 辅助数据路径（B1 / D2 / F-D-R5-P004-1）

| kind | 守卫 | 读取 | 缺失语义（不变） |
|------|------|------|------------------|
| suspend | `if self.cfg.suspend_file:` | `load_aux("suspend")` | warning + 全 0 DataFrame |
| industry | `if self.cfg.industry_file:`（**新增**） | `load_aux("industry")` | warning + 保持 `None` |
| st | `if self.cfg.st_file:` | `load_aux("st")` | warning + 全 0 DataFrame |
| mktcap | `if self.cfg.mktcap_file:` | `load_aux("mktcap")` | warning + 保持 `None` |

```python
if self.cfg.suspend_file:
    raw = self._provider.load_aux("suspend")
    if raw is None:
        logger.warning(
            f"停牌数据文件不存在: {self.data_dir / self.cfg.suspend_file}，按 0=正常 处理"
        )
        self._suspend_data = pd.DataFrame(
            0, index=self._trade_dates, columns=self._stock_codes
        )
    else:
        self._suspend_data = self._load_and_align_data(raw, "suspend")
```

> 必须保留 `if self.cfg.{kind}_file:`：`aux_map` 已过滤 falsy 键，对 falsy kind 调 `load_aux` 会命中 `PklDataProvider` 的 `raise ValueError("未知辅助数据类型")`；`mktcap_file` 默认 `None`，默认配置必触发。

### T-4 归一化与股票池（B1）

| 对象 | 改动 |
|------|------|
| `_load_and_align_data`（L372-443） | 签名 `(self, data, label: str = "aux")`；删除 `pd.read_pickle(file_path)`；dict/Series 归一化、日期交集、列对齐逐行保留；warning 用 `label` 替代 `file_path` |
| `tests/test_data_aux_defaults.py`（L61-63） | monkeypatch wrapper 由 `def counted(path)` 改为 `def counted(data, label="aux")`（**一行适配**，用例数与断言不变）——否则门面以两参调用会 TypeError |
| `universe`（L164-174） | `self._universe = self._provider.load_universe()`；`_build_universe_status` 不动 |

> 保留方法名与首个位置参数，`tests/test_data_aux_defaults.py:59-65` 的 monkeypatch 语义（计数读盘次数）不变；`label` 默认值保证单参调用仍可用。

### T-5 V3 死 API + `AbstractDataManager` 删除（B2 / D3）

| 文件 | 删除对象 | 行锚 |
|------|----------|------|
| `core/data_v3.py` | `__init__` 的 `from_hdf5` 形参、docstring 行、`self._from_hdf5` | L30 / L35 / L38 |
| `core/data_v3.py` | `from_data_manager` | L58-70 |
| `core/data_v3.py` | `_load_from_data_manager` | L103-128 |
| `core/data_v3.py` | `to_data_manager_compatible` | L210-222 |
| `core/interfaces.py` | `AbstractDataManager`（含类 docstring） | L437-457 |
| `tests/test_data_v3_compatibility.py` | `test_to_data_manager_compatible` | L78-85 |

删除后核对：`pickle` 仍被 `save/load` 使用；`pd` 仍被 `from_pandas_dataframes/save` 使用；`Optional` 仍被 `__init__/get_date_index` 使用。`DataLoaderV3.load()` 用 `cls()` 无参构造（L254），删 `from_hdf5` 无形参连锁。

### T-6 协议签名对齐 + `universe_status`（B3 / D4）

文件：`core/interfaces.py`

| 位置 | 改动 |
|------|------|
| `IDataManager.get_adj_price`（L51） | `(self, price_type: str = "close", adjustment_type: str = "hfq")`；docstring 同步 |
| `IDataManager.load_factor`（L63） | `(self, name: str)` → `(self, factor_file: str)` |
| `IDataManager` 属性区（`n_stocks` 后） | 新增 `universe_status -> dict[str, Any]` 属性 |

> 以实现签名为准（同 P-012 D7 `execute_order` 先例）；实现侧 `data.py:455` 存在全仓唯一 `adjustment_type=` 关键字自调用，反向改协议名会直接破环。

### T-7 契约测试（B3 / D4）

文件：`tests/test_contract_conformance.py`

| 改动 | 内容 |
|------|------|
| `EXPECTED_MEMBERS[IDataManager]` | 增 `"universe_status"` |
| 新增 `EXPECTED_SIGNATURES` | `get_adj_price: [self, price_type, adjustment_type]`；`load_factor: [self, factor_file]`；`get_data_info: [self]`；`get_asset_info: [self, symbol]` |
| 新增 `test_protocol_signatures` | 逐名 `inspect.signature(protocol)` 与 `inspect.signature(impl)` 的 `parameters` 序列等价 |
| 新增 `_MockProvider` + `test_data_manager_accepts_injected_provider` | 注入两列 close → `list(dm.stock_codes) == ["A", "B"]` |

预计测试数：**635 − 1（T-5）+ 2（T-7）= 636**。

---

## 3. 实施顺序与提交切分

| 提交 | 内容 | 测试面变化（Step 9 实读，不预填） |
|------|------|--------------------------------------|
| **B1** | T-1~T-4（`core/data.py`） | 不改测试 → 计数应持平（基线 635） |
| **B2** | T-5（`data_v3.py` / `interfaces.py` / 删除 1 个兼容测试） | −1 |
| **B3** | T-6~T-7（协议 + 新增 2 个契约测试） | +2 ⇒ 终态 636 |

> 每批独立 `git revert`；B1 与 B3 无编译期耦合，但 B3 的 `universe_status` 依赖 B2 删除后的 `interfaces.py` 行位（删除后行号下移，需重新锚定）。

---

## 4. 验证项（V1-V8，与 DESIGN §5 同编号同义）

| # | 验证项 | 判据 |
|---|--------|------|
| V1 | 全量测试（终态） | **636 passed**，`MPLBACKEND=Agg`，项目解释器 3.12.10 |
| V2 | golden | `tests/test_golden_baseline.py` 参数化 **G1-G7** 全过 |
| V3 | P-010 默认值 | `test_data_aux_defaults` 4 项全过；`dm.mktcap is None`；幂等计数 = 1 |
| V4 | 复权口径 | `test_adjustment`(11) + `test_adjustment_semantics`(2) 全过 |
| V5 | 门禁 | `mypy --explicit-package-bases core` = 0 errors；`black --check core tests` 无变更 |
| V6 | 死 API 归零 | `Grep 'from_data_manager\|_load_from_data_manager\|to_data_manager_compatible\|from_hdf5\|AbstractDataManager'` = 0 代码命中 |
| V7 | 契约 | `test_protocol_members` / `test_protocol_signatures` / `test_execute_order_signature` 全过 |
| V8 | 消费者回归（可选） | `verify_p015.py` 五 case `28 断言（失败 0）+ 豁免 1`，exit 0 |

> **Step 8 更正（F-S8-P004-1）**：初稿曾将契约编为 V5、门禁拆 V7/V8、外部对拍编 V9，与 DESIGN §5 同 ID 异义；已按 DESIGN 权威编号重排（V5 门禁 / V7 契约 / V8 对拍），CHECKLIST 引用同步。

---

## 5. 风险与回退

| 风险 | 预案 |
|------|------|
| cfg-falsy 守卫遗漏（P2 复发） | T-3 逐 kind 守卫；V3 `dm.mktcap is None` 兜底 |
| `aux_map` 过滤后 provider 对未知 kind raise | 门面只在 cfg truthy 时调用；异常不再泄露到默认路径 |
| `industry_file` falsy 异常路径漂移 | 现状 `IsADirectoryError` → B1 后静默 None；无测试/现实覆盖，normal 配置不变（DESIGN §4.1 已声明） |
| `_load_and_align_data` 签名变化破坏 monkeypatch | 保留方法名 + 首位置参数 + `label` 默认值；同步一行适配 wrapper（T-4）；V3 实测 |
| 价格异常文案变化 | 类型仍 `FileNotFoundError`；全仓 0 断言；Step 9 记录原文 |
| 删除死 API 留下未使用导入 | `black` + `mypy` + V6 三重兜底 |
| B2 行号下移影响 B3 锚点 | B3 实施前重新 `Read` `interfaces.py` 定位，不沿用旧行号 |
| 测试数预测偏差 | 不预填；Step 9 按实读回填（RULE-1） |

---

## 6. 排除的低效操作

- 不引入 DI 容器、不新增 `DataProvider.from_config()`（一次性构造）；
- 不重构 `_load_and_align_data` 的 dict/Series 归一化逻辑；
- 不改 `PklDataProvider` 三个方法签名与异常语义；
- 不做 agents `data_dir` 迁移与端口扩全（B4 / D5）；
- 不动 filter/ 孤儿模块（TD-5）；
- 不为异常文案变化新增测试；不为 `AbstractDataManager` 保留 deprecation 壳。

---

## 7. Step 6 Review（实施文档幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 依赖版本：无新增第三方依赖；`core.data_provider` 为仓内模块（P-012 已落地）
- [x] stdlib API 下限：`pathlib` / `inspect.signature`（3.3+）/ `typing.Protocol`（3.8+），运行时 3.12 可用
- [x] API 签名可实现：`DataManager.__init__` 仅新增可选 `provider`；`_load_and_align_data` 私有方法，唯一调用方 4 处 + 1 处 monkeypatch 已逐一核对（wrapper 一行适配已列入 T-4，不计入用例增减）
- [x] 兼容性：6 个生产构造点（factory / engine_v2 / agents ×2 / examples ×2）均位置传 `config`，不破；B3 协议改名无关键字调用点
- [x] 锚点可解析：E1-E7 全部 WebFetch 正文验证；E8 标未验证且不用于结论（§1.3）
- [x] 低效操作已排除（§6）；回退点按 B1/B2/B3 三提交切分
- [x] F5 声明：Step 5 无先行失败记录 → **N/A**；Step 9 按两读数块（红：非零退出 + 失败行；绿：exit 0 + 用例计数）回填，不预填

**Step 6 Review 结论：通过**。可进入 Step 7 CHECKLIST。

---

## 8. Step 9 实施记录（待回填）

> [RULE-1] 零预填：本节的 F5 红/绿读数、探针读数、终态计数均在 Step 9 执行后按实读写入，本稿不预写任何数字。
