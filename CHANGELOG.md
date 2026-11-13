# Changelog

All notable changes to Factor Trading v3.0 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **P-015 外部框架对拍校准（VectorBT ↔ V3 首例）**: 新增 `scripts/external_benchmark/`（`_spec.py` 声明式规格层 + `export_case.py`/`run_vectorbt.py`/`verify_p015.py` 三脚本 + `audit_signatures.py` 签名核验 + `requirements-vectorbt.txt` 钉版）；隔离 venv `.venv-vbt/`（.gitignore 豁免，vectorbt==1.2.0 / pandas==3.1.1 / numba==0.68.1——与主环境冲突故零接线零 CI）；新增 [APPENDIX_p015_external_calibration.md](docs/APPENDIX_p015_external_calibration.md) 校准报告（29 项恒等式断言 0 失败：零费用记账全零残差 / 规模语义差异逐日闭式 / 费用模型一致性 / 选股翻转全等 / 阴性对照精确命中）；[BACKTEST_CALIBER_MAPPING.md](docs/BACKTEST_CALIBER_MAPPING.md) §2.2 获首个外部实测列；实锤两处结构性口径差异（V3 `last_pv` 规模参考值 vs vectorbt current-NAV；V3 费用透支现金 vs vectorbt 部分成交）并写成恒等式/缺口登记——主环境零污染（pandas 2.2.3 / numba 0.65.1 不变）、`core/` `tests/` 零改动、635 passed 保持
- **P-014 停牌账目回归锁**: 新增 `tests/golden/G7.json`（V2 停牌场景：停牌 2 日后恢复，I2 零违规）与 `tests/test_p014_suspension_accounting.py`（8 项性质测试：I1-I5、队列/次日两条路径的无持仓卖单作废分支、双路径净值一致性）；新增 `PendingOrderQueue.cancel_order` 单订单取消 API 与 `IPendingOrderQueue` 协议声明；golden 由 6 条扩至 **7 条**；测试 **626 → 635 passed**、测试文件 70 → 71
- **P-013 Golden 基线固化（L4 判据）**: 新增 `tests/golden/G1..G6.json`（6 条「当前行为」基线：V2 baseline/cost/mask/delisting + V3 baseline/cost，覆盖 T+1 开盘、整手与 0.985 缓冲、四项费用、涨跌停掩码、退市动态池、同日收盘与对称成本）；新增 `scripts/record_golden.py`（工作区干净检查 `U-G2=A`、`CI=true` 拒录、逐 case 摘要供人工核对、含非有限值拒写）；新增 `tests/_golden_cases.py` 作为录制与断言的**唯一 case 构造器**（防「录制用夹具 A、断言跑夹具 B」漂移）；新增 `tests/test_golden_baseline.py`（8 用例：6 case + 集合完整性 + schema/容差上限）与 `tests/test_synth_fixture.py`（9 用例）；`tests/_synth_fixture.py` 扩展独立 OHLC 与矩阵 `suspend`/`st`（默认参数保持 P-011 行为不变）并新增 `write_universe`；分字段容差（金额 `rtol=1e-9`/`atol=1e-6`，比率 `1e-9`，计数精确）以同时兼容本地 `@njit` 与 CI `py_func` 两条路径；基线连续两次录制 SHA256 完全一致（逐字节可重现）；测试 **609 → 626 passed**、测试文件 **68 → 70**
- **P-011 回测准确性验证与可复现（不变量 / 参考差分 / 声明 / manifest / trace）**: 新增 `core/invariants.py`（I1-I7 纯函数 + `check_all`，`BacktestConfig.invariant_mode` 默认 `"report"`，结果落 `additional_info.invariant_report`，`"off"` 零计算）；新增 `tests/_reference_impl.py` 四参考函数 + `tests/_synth_fixture.py` 合成夹具，覆盖 V3 内核 / V2 目标持仓 / 成本 / NAV 四组差分（njit 路径比特一致，`py_func` 回退末位 ≤1 ulp）；新增 [BACKTEST_CALIBER_MAPPING.md](docs/BACKTEST_CALIBER_MAPPING.md)（与 Qlib / Backtrader / VectorBT 的口径映射与残差恒等式，仅声明「可解释差异」）；新增 `core/metrics.py` 指标单一实现（含 `METRICS_METHOD` 口径声明，随结果落 `additional_info["metrics_method"]` / V3 `results["metrics_method"]`）；新增 `core/validation.py` 偏差声明（PIT / 多重检验 / benchmark / walk-forward 能力常量 + 5 条 `known_limitations`）；新增 `core/manifest.py` run manifest（git commit/dirty、config 全字段、数据 sha256、环境、`input_fingerprint`，落 `output_dir/manifest.json`，`write_manifest=False` 可关闭）；`python cli.py run --trace-dir` 输出六层逐日快照 + `manifest.json`；测试 **550 → 609 passed**、测试文件 **60 → 68**
- **P-012 偏差防护与接口锁定（观测网 / 规则表 / 动态池）**: 新增 `core/change_report.py`（六层归因 dump + 两次运行差分，`residual < 1e-8` 与 `attribution_complete` 双门）与 `scripts/change_report.py`；新增 `filter/limit_rules.py` A 股涨跌停规则表（`RULESET_VERSION="cn_a_2026_07"`，11 条规则，`(board,is_st,t)` 恰好 1 条 fail-fast，未知前缀一次性告警 + `unknown_board_codes`）；新增 `core/universe_data.py` 动态股票池（`list_date`/`delist`/`manifest`，缺失显式降级 `survivorship="uncorrected"`）；新增 `scripts/fetch_universe.py`（默认离线，`--refresh` 才联网）；新增 `core/data_provider.py` `DataProvider` 端口（零接线）；夹具支持 `--profile {baseline,biased}`（baseline 逐字节不变）；测试 **516 → 550 passed**、测试文件 51 → 60；`__api_version__="3.1.0"`
- **Spec_Runner 接入**: 新增 `scripts/spec_runner_adapter.py`（官方模板 v1.0 + 本项目配置：`PREFIX=factorv3`，门禁 `probe / unit-tests / black-check / mypy-check`）与 `tests/test_spec_runner_adapter.py`（6 项）；门禁 verdict/exit/stdout_tail 以 append-only JSONL 落在 `F:\Spec_Runner\sessions\`，可用 `replay` 重放。全量测试 503 → 509 passed；`black-check`（75 files）与 `mypy-check`（168 errors）已登记为已知基线

### Fixed
- **P-022 Factor_DB 四项实现缺陷（U-P005-2）**: ① **写后重开崩溃**——`metadata.json` 的 `created_at`/`updated_at` 以 `isoformat()` 写入，重开时 `FactorMetadata(**meta_dict)` 读成 `str`，任何再次 `add_factor`/`update_stats`/双因子 `delete_factor` 都触发 `AttributeError`；改为加载期 `datetime.fromisoformat` 显式还原。② **静默覆盖**——`add_factor` 的 `overwrite` 守卫只查内存 `_factors`（重开后为空），已持久化因子可被无提示覆盖；守卫扩展为「metadata ∪ 内存 ∪ parquet 文件 ∪ csv 文件」。③ **删除复活**——`delete_factor` 只 `unlink` parquet，CSV 回退产物残留并被 `get_factor` 重新加载；改为同时删除两种格式。④ **双份存储**——parquet 写入成功不清理旧 csv（反向亦然）；改为写入成功后删除另一种格式。新增 `tests/test_p022_factor_db_defects.py` **11 项**回归测试；7 个公开方法与 `FactorMetadata` 字段签名不变；`batch_backtest` 零改动；门禁 **647 passed** / black 112 unchanged / mypy 36 files 0
- **P-005 Factor_DB 文档与依赖对齐（DuckDB → Parquet 真实现状）**: README 架构图 `DuckDB`→`Parquet`（同列另两 token `Macro/News`→`Metadata`、`Alternative`→`Lineage` 一并纠正）；Factor_DB 章节整节重写为 `metadata.json` + 每因子 `.parquet`（`pyarrow`/`fastparquet` 缺失降级 `.csv`）+ 四行能力表（存取/检索/血缘/统计）+ 能力边界，删除五类虚构表与五个 `*Query` 类；Requirements 由 `Database: duckdb` 改为 `Storage: JSON metadata + Parquet per factor (...)`；web Overview 架构框改 `Factor_DB(Parquet)`；ARCHITECTURE 依赖表删除 `duckdb` 行并在表后注明「查询层为规划方向；Parquet 需 pyarrow/fastparquet（未声明）」；`pyproject.toml` 移除 `duckdb>=0.10.0`、`cli.py info` Key deps 去掉 `duckdb`、`uv.lock` 同步移除 duckdb 包块与两处引用；`DECISIONS` ADR-001 补「实施状态: 未实施」。不迁移 DuckDB（零数据 + 单消费方 `BatchBacktestEngine` + 可直读 Parquet），登记 U-P005-1。门禁 `636 passed`（`MPLBACKEND=Agg`）/ black 111 unchanged / mypy 36 files 0 / 四表面 `Grep -i duckdb` 6 → 0
- **P-004 数据层统一（零行为重构，B1→B3 三批）**: `DataManager` 新增可选 `provider: DataProvider` 注入（缺省 `_build_provider` 由 `BacktestConfig` 生成映射、`aux_files` 过滤 falsy——`mktcap_file=None` 不再回落 `mktcap.pkl`），价格/辅助/股票池读取收敛为单一 I/O 路径（`_PRICE_KINDS` 单一来源；`_load_and_align_data(data, label)` 不再自行读盘），移除 `_load_price_data`/`_load_basic_data` 的 `exists()` 守卫与重复 `file_map`；删除死 API `DataLoaderV3.from_data_manager`/`_load_from_data_manager`/`to_data_manager_compatible`/`__init__(from_hdf5=)` 与 `interfaces.AbstractDataManager`；`IDataManager` 协议以实现签名为准（`get_adj_price(price_type, adjustment_type)`、`load_factor(factor_file)`）并纳入 `universe_status`，契约测试新增 `EXPECTED_SIGNATURES` 四签名与 `_MockProvider` DI 用例（PEP 544 运行时擦除、mypy 不检查形参名）。门禁 `636 passed`（`MPLBACKEND=Agg`，B1 635 / B2 634 / B3 636）/ black 110 unchanged / mypy 36 files 0 / 死 API grep 0 命中 / 外部对拍 28 断言 + 1 豁免 exit 0
- **P-019 报告写入父目录缺失修正（F-R5-P018-1）**: `verify_p015.py` 的 `write_report` 在 `write_text` 前新增 `target.parent.mkdir(parents=True, exist_ok=True)`——此前 `--report` 指向父目录不存在的路径会抛未捕获的 `FileNotFoundError`（traceback + exit 1）；现支持父目录缺失与多级父目录自动创建，权限类失败（`PermissionError`）仍照常抛出、不吞异常。同时更正 P-018 探针 ⑥ 的覆盖声明（该探针实际预建了父目录，未覆盖「父目录不存在」形态）。插入位置在 `:272` 之后，`:254/:268/:272` 锚点零位移。门禁 `635 passed`（`MPLBACKEND=Agg`）/ black 5 unchanged / 全链 `28 断言 + 1 豁免` exit 0
- **P-018 P-017 复审 E4 两项 P3 修正（F-R5-P017-1~2）**: ① **生成物守卫边界修正**——`_resolve_report_target` 的判定由 `path.stem.endswith(".generated")` 改为 `path.name.endswith(...) or path.stem.endswith(...)`：无扩展名目标 `X.generated` 的 `stem` 会剥离后缀（`Path("X.generated").stem == "X"`），旧判定失效导致二次运行仍产出 `X.generated.generated`；新版并判 `name` 后两种形态均命中，且与 P-017 的 `X.generated.md` 行为一致（单行 1:1 替换，`:254/:268/:272` 行号零位移）② **取证归因更正**——P-017 曾称分支 1（目标不存在→原地新建）由探针 A①/C/D 覆盖，实际三探针的传入目标在运行前均已存在（走分支 3/3/4）；本批保留原句并追加 P-018 更正注，同时以新增探针取得 `FRESH_EXISTS=True` 的真实读数。门禁 `635 passed`（`MPLBACKEND=Agg`）/ black 5 unchanged / 全链 `28 断言 + 1 豁免` exit 0
- **P-017 P-016 复审 E4 四项 P3 修正（F-R5-P016-1~4）**: ① `verify_p015.py` 新增 **生成物命名空间守卫**（`GENERATED_SUFFIX = ".generated"`）——`_resolve_report_target` 现为四分支，目标本身是生成物时**原地重写**，消除旧行为把 `X.generated.md` 再改写为 `X.generated.generated.md` 的级联污染（F-R5-P016-3）；人工策展版（含 §1/§3 标记）仍改名保护、原文件零改动。② PROGRESS §3.17.1 与 §1.4 两处「29 项断言」**保留原句**并追加 P-017 口径更正注（= 28 断言 + 1 项豁免登记），不改冻结点数（F-R5-P016-1）。③ `IMPL_p015` §8.5 的「回填区」占位回填为门禁读数表（pytest 635 / black 5 unchanged / 主环境无 vectorbt）+「T-4 原始读数未保全」声明（F-R5-P016-2）。④ `CHECKLIST_p016` E-1 变更面计数更正为「scripts 2 + docs 9 + CHANGELOG 1 = 12 文件」，B-3 精确化四分支覆盖（F-R5-P016-4）。门禁 `635 passed` / black 0 / 全链 `28 断言 + 1 豁免` exit 0；占位真实残留归零
- **P-016 P-015 复审 P3 修正（F-R5-P015-1~3 + 报告覆盖缺陷）**: ① `verify_p015.py` 引入**三态检查词表**（`pass / fail / waiver`）——`waiver` 为豁免登记，不计入断言数、不参与通过/失败判定，报告渲染为「— 豁免（非断言）」，消除 B5 豁免行的「恒真即 PASS」形式张力（F-R5-P015-2）；口径由「29 项断言」更正为「**28 断言 + 1 豁免**」，28 条读数逐行不变。② **报告人工章节保护**：`write_report` 检测目标是否含人工章节标记（§1/§3），命中则改写 `<stem>.generated.md` 并打印 `[保护]`，不再静默覆盖（F-S9-P016-1）。③ `_spec.simulate_vbt_spec` 对 `cost_rate > 0` **fail-fast**（`NotImplementedError`）——current-NAV 规格的费用语义未定义，拒绝静默产出（F-R5-P015-3 / U-P016-1）。④ I2a ↔ `G1 组三行` 命名映射补入 CHECKLIST C-2 / DESIGN §3.2（F-R5-P015-1）；U-P015-1 增「rate>0 规格费用语义」前置。**并修复既成数据丢失**：`git show HEAD` 证实 P-015 入库的 `APPENDIX_p015_external_calibration.md` §1/§3/§4 已被 black 后的最终全链复放覆盖为占位模板，本批按 E1 现场重放重新回填。门禁 `635 passed` / black 0 / 主环境零污染
- **P-014 V2 停牌路径账目缺陷（P1，行为变更）**: 次日开盘路径（`enable_pending_orders=False`）在停牌期每天重复生成清仓单（目标持仓基于「当前持仓」而非「扣除在途订单后的有效持仓」），恢复日一次性全部成交，导致**负持仓 + 5 项 I2 违规**（复现：`SELL 113600 + SELL 338600 ×2`、收盘持仓 `-113600`）。修复为三层防线：① 执行侧 SELL 按可卖持仓夹紧（`_clamp_sell_quantity`，无持仓即作废订单，两条执行路径共用）；② 次日路径在每次再平衡开始时撤销信号域内在途订单（`_cancel_next_day_orders`，与队列路径 `cancel_orders` 语义对齐）；③ 次日订单复用 `PendingOrder.is_expired`（买 5 / 卖 10 自然日）过期，陈旧订单不再无限重试。**已知边界**：停牌持仓是否应保持目标权重而非强制清仓（U-P014-1）、买侧现金夹紧（U-P014-3）不在本批
- **P-011 不变量观测网实施期发现（Step 9）**: `PositionTracker._take_snapshot` 浅拷贝导致历史快照与实时持仓共享 `Position` 对象（后续调仓/盯市/强平改写历史），引擎实跑报 **53 项 I1/I2 违规**；改为逐 Position `replace()`（NAV 标量序列与指标零影响）。I2 对「同日多快照」日期跳过（末日强平在收盘快照后追加第二快照，配对存在歧义），并补 ambiguous 用例；参考实现按 numba 顺序累加语义显式 `_seq_sum`；trace 自差分容差统一为 `RESIDUAL_TOL=1e-8`
- **P-012 归因链与夹具修正（T-13 取证）**: L6 末行在末日强平后刷新为终值；L1 纳入 listing（上市状态）；删除 L4→L3 硬链（L3 仅记目标集合，订单量随净值变化）；`_cash_flow` 首日现金流去重；层 CSV 的股票代码按字符串读取（避免 `000001`→`1`）；biased 夹具除权日 OHLC 缩放到除权后尺度并新增真实涨停开盘样本（`2024-02-27:000001`）；manifest 补 `fetched_at`
- **`IPositionTracker.get_snapshots` 契约失实（P-007 层 B）**: 协议声明 `list[dict]` 与 `PositionTracker` 实际返回 `list[PortfolioSnapshot]` 不符，改为真实类型（`TYPE_CHECKING` 导入，零运行时开销）
- **`IExecutionSimulator` 缺失 `trade_log` 声明（P-007 层 B）**: 引擎在结果生成中访问 `executor.trade_log.get_trades_df()`，协议未声明该成员；新增 `ITradeLog` 最小协议（仅 `get_trades_df`）并以只读 `@property` 暴露（PEP 544 协议属性不变性要求）
- **`DataManager` 辅助数据重复读盘 + 类型契约（P-010）**: `_load_auxiliary_data` 增加幂等 guard，可选文件缺失时不再每次属性访问都重读已存在文件（实测 `.industry` 3 次访问的读盘次数 **3 → 1**；100 次 `.st` 访问的读盘次数由 **206 次**降至首次加载后 0 次）；`suspend`/`st` 缺失时按配置约定 `0=正常` 提供全 0 默认帧（旧版被覆盖实现的 `True` 默认值与 `1=停牌` 语义相反，已弃用）；`industry` 注解修正为 `Optional[pd.DataFrame]`，缺失时由消费方跳过过滤/中性化；新增 4 项测试（510 → **514 passed**）
- **`CompositeRiskEngine.remove_monitor` 崩溃（P-007 层 A）**: `core/risk_monitor.py` 引用了未定义名 `RiskAction` 且与类内已声明的 `_signal_history`/`_action_history` 重复注解；调用 `remove_monitor()` 即 `NameError`。改为无注解赋值（类型仍由 L713/L714 提供），并补 smoke 测试
- **`analyze_market_contagion` 崩溃（P-007 层 A）**: `core/global_contagion.py` 调用了 `GlobalContagionMonitor` 上不存在的 `evaluate()`；调用便捷函数即 `AttributeError`。改为 `monitor.monitor(...)` 单值返回
- **`RegistryPlugin.create_trigger` 崩溃（P-007 层 A）**: 以 3 个位置参数调用只接受 `(name, config, **kwargs)` 的 `PluginRegistry.create`，调用即 `TypeError`。改为 `dates=trade_dates` 关键字传参（与三个 trigger 工厂的 `(cfg, dates)` 契约一致）
- **`DataManager._load_auxiliary_data` 重复定义（P-007 层 A，行为不变）**: 删除被同名方法覆盖的 48 行死代码，唯一实现保持原状；「辅助数据缺失时无安全默认值」的行为缺口**未在本条修复**，另立 P-010 跟踪
- **CRITICAL 再平衡修复（行为变更）**: 调出组合的标的现在会生成清仓卖单（此前永不卖出），同一次调仓中卖单先于买单；`results` 新增 `unclosed_positions` 诊断；新增 `core/target_positions.py` 统一 V1/V2 目标持仓，并以价格重算组合价值，修复开盘成交后组合价值虚高导致的超额买入
- **ARCHITECTURE.md 文档幻觉**: Factor_DB 存储由 "DuckDB" 改为 "JSON 元数据 + Parquet（DuckDB 为规划方向）"，架构图/模块表/缺口表/依赖表同步；Data V3 由 "多源 (AKShare, YFinance)" 改为 "Qlib 风格向量化加载器"；Config V2 由 "✅ 活跃/推荐" 改为 "⚠️ 冻结（零生产引用）"
- **demo_data 复权文件缺失**: `examples/demo.py` 生成器改为输出 `stock_adj.pkl`（与配置默认一致），修复旧布局导入与硬编码路径；本地补齐 `demo_data/stock_adj.pkl`

### CI
- **P-024 CI 门禁对齐（mypy 假门禁 + README uv extras）**: `tests.yml` 的 mypy 步骤由 `mypy core/ --ignore-missing-imports --no-error-summary || true` 改为 `python -m mypy --explicit-package-bases --check-untyped-defs core`——`|| true` 使该步骤**退出码恒 0**（自初版 `c7a0f29` 起，类型错误从不阻塞 CI），现恢复真实阻塞；`--explicit-package-bases` 消除「本地目录名含点号 → exit 2」的环境差异，`--check-untyped-defs` 覆盖无注解函数体（`core` 残差 0），`--ignore-missing-imports` 与 `[tool.mypy]` 全局配置重复故移除。本地门禁 `scripts/spec_runner_adapter.py` 同步加 `--check-untyped-defs`，两侧命令同形（仅解释器前缀不同）；新增 `tests/test_p024_ci_gate_alignment.py` 3 项漂移守卫（口径同形 / 无 `|| true` / README extras）。README uv 段 `uv sync` → `uv sync --all-extras`（`uv sync` 默认不同步 extras，照 Quick Start 执行会缺 pytest/mypy/black）。先红 exit 1（`Incompatible types in assignment`）→ 同命令加 `|| true` 对照 exit 0 → 删探针后 exit 0；门禁 **654 passed** / black 180 unchanged / mypy 双口径 36 files 0 / `uv lock --check` exit 0；**U-006 / U-P023-2 / U-P023-4 关闭**。**Step 9 追加**：CI 首跑暴露门禁口径越界——`core` 经 `engine_v2`/`factory` 导入 `filter`，follow 后把该包在 **pandas 3.1.1** 类型桩下的 **21 errors / 7 files** 计入门禁（`core/` 0 条；本地 pandas 2.2.3 为 0，`pandas>=2.0.0` 无上限）。处置：`pyproject.toml` 新增 `[[tool.mypy.overrides]] module = ["filter.*"] ignore_errors = true`（解析类型但不向门禁报错，X1-X3 验证 mypy 2.1.0/2.4.1 均 0）；`filter/` 21 条登记 U-P024-4。首轮「mypy 版本漂移」判定已证伪并撤回（`mypy>=1.5.0` 维持）

### Changed
- **P-026 静默失败治理第二批（五处静默路径显形，零 fail-fast）**: ① **因子中性化**——`FactorPipeline` 新增 `set_error_sink(sink)` / `neutralize_skip_counts` 属性（`degenerate_columns` / `regression` 双原因分桶）；去常数列失败由 `except Exception: continue`（零日志）改为 `warning` + 计数 + 旁路上报，回归失败分支同步计数上报；旁路调用自身失败仅 `debug` 并忽略，不影响主流程。② **setup 期异常入库**——`engine_v2` 在 `FactorCombiner` 之后、`_precompute_factors()` **之前**注入 sink（顺序是正确性条件，否则 setup 期因子异常全部漏采），异常经 `DayErrorCollector.record` 进入 `additional_info["run_diagnostics"]`；`STAGES` 追加 `"factor"`，`classify_day_error` 新增 factor 分支（`LinAlgError→solver`，`KeyError/FileNotFoundError/ValueError→data`，其余 `internal`，retryable 全 `False`）。③ **插件层**——`EventLogPlugin._log` 失败由 `debug` 升 `warning` 并计入新增 `get_stats()["error_count"]`（原默认配置下完全不可见）；`GuardPlugin` 检查异常补计数与「已放行」文案，`get_stats()` 追加 `error_count` 键，**fail-open 行为不变**。④ **传染分析**——`ContagionNetwork` 新增 `degraded_components`（中心性 / MST 兜底从零日志改为 `warning` + 标记）；`compute_granger_causality` 三路径统一带 `failed` 键（样本不足与计算异常此前不可区分）。⑤ **EventLog / Walk-Forward**——新增 `EventLog.stats()` 三计数器（`read_failures` / `write_failures` / `skipped_lines`，只读拷贝、不加锁、不改 `read`/`query` 返回形态）；`WalkForwardResult` 新增 `agent_period_failures`，`run()` 开头重置（原窗口以错误期间模式运行且无字段标记）。新增 `tests/test_p026_silent_exception_governance.py` **12 函数 / 16 实例**；门禁 **687 passed**（671 + 16）/ black 116 unchanged / mypy 37 files 0 / golden G1-G7 零重录
- **P-025 日级异常可观测（三项行为变更）**: ① **`mean_variance` 真正生效**——`build_optimizer` 的 `optimizer_map` 此前只有 `mvo` 键，而 CLI `--optimizer` 与 `config_v2` 的 Literal 提供 `mean_variance`，选该项实际静默降级为**等权**（探针实测与 `equal_weight` 读数完全相同：64 笔 / sharpe −1.4611384945695667）；现补 `mean_variance` 别名。② **未知 method fail-closed**——此前任意未知字符串静默降级等权，现抛 `ValueError`（消息列出 5 个合法值）；调用点为 `engine.setup()` 与 `factory.create_optimizer()`，均早于 `run()`。③ **短历史协方差方法 setup fail-fast**——`min_variance`/`mean_variance`/`mvo`/`risk_parity` 在 `len(trade_dates) <= cov_lookback` 时，此前每次调仓静默 `ValueError` 被吞、返回 0 成交 / `sharpe=0.0` 的**假成功结果**；现 `setup()` 抛 `RuntimeError`（消息含「必然失败」）。④ 结果字典 `additional_info` 新增 **`run_diagnostics`** 键（只增，既有 10 键不变）：`{mode, degraded, counts, samples(≤50), truncated}`，三处（日循环 / 组合优化 / 订单执行）统一汇入 `core/diagnostics.py`；新增 `BacktestConfig.day_error_mode: Literal["off","report","raise"] = "report"`（与 `invariant_mode` 同形，`off` 时零分配、`raise` 时首个 data/internal 错误即抛 `ExceptionGroup`）；新增 `tests/test_p025_day_error_diagnostics.py` **10 函数 / 17 实例**；门禁 **671 passed**（654 + 17）/ black 116+182 unchanged / mypy 37 files 0 / golden G1-G7 无重录
- **P-023 两项行为变更（F-A1 静默空回测清零）**: ① **`run()` 信号就绪守卫**——注入 `factor_pipeline`/`factor_combiner` 且 `factor_files` 为空时，此前 `setup()` 放行、`_precompute_factors()` 仅 warning 返回、逐日 `except Exception: continue` 吞掉 `assert signal_df is not None`，最终返回**完整结果字典**（0 快照 / 0 交易 / 每日一条空消息 ERROR）；现 `run()` 入口在 `_composite_signal is None` 时抛 `RuntimeError`（消息含「信号未就绪」+ 修复指引）。② **`_generate_results()` 空快照守卫**——零快照时此前仍生成空报告，现抛 `RuntimeError`（消息含「快照」）。`setup()` 守卫与逐日循环体**逐字不变**（13 个既有注入式用例「setup 后手工注入信号」不受影响，两文件 27 passed）；新增 `tests/test_p023_quality_guardrails.py` 4 项；同时 `U-006-R` 清零（`mypy --check-untyped-defs core` 4 errors 2 files → 0：`DataLoaderV3._build_maps` 别名+assert、`FactorPipeline(cast(DataManager, ...))`、`_precompute_factors` 别名+assert）；门禁 **651 passed** / black 113 unchanged / mypy 36 files 0
- **P-021 依赖与锁维护**: `uv.lock` 以 plain `uv lock` 重建（`+1207/−2`）——补齐 `[web]` extra 与 streamlit 传递闭包（120 → 148 包，新增 19），根包 `provides-extras` `["dev"] → ["dev","web"]`；既有 pin **零升级**（numpy / pandas / scipy / scikit-learn / cvxpy 同名版本集合相等，duckdb 保持 0），并修正锁元数据中 black specifier `>=23.0.0 → ~=26.0`（与 `pyproject.toml` 对齐）。`ARCHITECTURE §9.2` 由「可选依赖」改为「可选与未声明依赖」：删除误列为可选的 `ta`/`tushare`/`akshare`（实为核心 `dependencies`），补 `numba`（未声明，缺失降级 `py_func`）与 `pyarrow`/`fastparquet`（未声明，缺失降级 CSV），并写明三条纪律——改依赖须 `uv lock` 并提交锁、CI 使用 pip 不校验锁、`uv sync` 默认不同步 extras（需 `--extra web` 或 `--all-extras`）。`uv lock --check` exit 1 → 0；`uv export --frozen` exit 0；`636 passed` / black 111 unchanged / mypy 36 files 0；`pyproject.toml` 零改动
- **P-014 golden 基线重录（A20/D10）**: G3 由 `56` 笔成交变为 `55` 笔、`final_value 10286486.93 → 10286475.48`（rel `1.11e-6`）——涨停日被掩码阻断的买单不再于次日无条件重试，改由当日再平衡重新决策，与队列路径（生产默认）语义一致；G1/G2/G4/G5/G6 复录后 `metrics/nav/trades` 三项**逐值不变**
- **P-011 B3 指标口径统一（行为变更，仅报告层）**: 新增 `core/metrics.py` 单一口径（年化 `252/N`；`Sharpe=(annual_return-rf)/annual_vol`，默认 `rf=0.03`；`max_drawdown` 统一非负量级）；V2 `annual_volatility` 改用 N−1 个差分收益（31×60 夹具 `0.08122845 → 0.08189931`）、`sharpe_ratio` 随 vol 变化（`−1.45492 → −1.44300`）；V3 `sharpe_ratio` 由 rf=0 改为 `cfg.risk_free_rate`（`0.93900 → 0.59117`）、`max_drawdown` 补初始锚点并输出正值量级（`−0.02965 → +0.02965`）、结果新增 `risk_free_rate` 键；NAV / trades / 六层 dump **逐值不变**（`change_report residual 0.0`）
- **P-012 四项行为变更（各自独立批次 + `change_report.json` 双门）**:
  - **B3b 成交/估值切 raw（行为变更）**: 新口径 `PriceModeConfig(trade=raw, valuation=raw, signal=hfq, returns=hfq)`；`legacy_adjustment=True` 恢复旧路径并与改前基线 `rtol=0` 逐值相等；change_report `1,155,172.33 → 832,682.77`
  - **B4 涨跌停价格法 + next-day 默认 ignored（行为变更）**: 判定改为「当日开盘价 vs 除权参考价 `×(1±ratio)`」（EPS=0.005），ST 用当日状态；旧 `check_next_day_tradable` True→`oracle` / False→`ignored` 并弃用；change_report `832,682.77 → 831,073.02`
  - **B2 涨跌停规则表（行为变更）**: 主板 10%；主板 ST 5%（≤2026-07-05）→10%（≥2026-07-06）；创业板 10%→20%（2020-08-24）、ST 5%→20%；科创板 20%；北交所 30%；4 个旧阈值字段保留但 `DeprecationWarning`
  - **B5 动态股票池与退市结算（行为变更）**: 上市前/退市后不可交易；退市结算 `last_close×(1+delist_return)` → `last_close` → 计入 `unclosed_positions`；报告 `survivorship`/`n_unknown_*`/`n_delisted_closed`；change_report `831,073.02 → 787,609.76`
- **P-012 B3a 复权命名校正（零数值）**: `forward→hfq`、`backward→qfq`、`none→raw`，旧名保留并发 `DeprecationWarning`
- **空 `factor_files` fail-fast（P-007 层 B，行为变更）**: `BacktestEngineV2.setup()` 在「未注入因子管道/合成器且 `factor_files` 为空」时抛 `ValueError`（此前静默空回测：逐日 `TypeError` 被 `except Exception` 吞掉，100 条 ERROR 后返回空结果）；注入 `factor_pipeline`/`factor_combiner` 的手工信号工作流不受影响；新增 2 项 smoke（**514 → 516 passed**）
- **`_generate_results` 未 setup 守卫（P-007 层 B，行为变更）**: 未 `setup()` 直接调用 `_generate_results()` 由 `AttributeError` 改为 `RuntimeError("请先调用setup()方法")`，与 `run()` 守卫文案一致
- **引擎 mypy 清零（P-007 层 B）**: `engine_v2` 54 / `engine_v3_vector` 26 / `factory` 13 共 **93 errors → 0**（局部别名窄化 + factory `cast` 白名单，无 `type: ignore`）；`mypy-check` 门禁自接入以来首次 verdict=pass；盲区口径（`--check-untyped-defs`）102 → 8（另批评估）
- **停牌数据缺失时的末日可交易性（P-010，行为变更）**: 停牌数据缺失时改为提供 `0=正常` 默认帧，`universe_filter_clean` 的 next-day 可交易掩码因此走「有数据」路径，**最后一天由可交易变为不可交易**（末日无次日，语义更正确）；其余日期与其余掩码数值不变。仓库测试夹具含 `suspend.pkl`，全量回归不受影响（510 → 514 passed）
- **CLI 默认引擎**: `python cli.py run` 从已弃用的 V1 `BacktestEngine` 切换至 `core.factory.create_default_engine()`（V2）。V2 会执行 `FactorPipeline`，`--winsorize/--standardize/--fill/--neutralize` 参数自此真实生效（此前在 V1 下被忽略），默认结果随之变化；R-1 受控对比确认关闭因子处理后两引擎逐日净值完全一致（最大差异 0.000000）
- **README**: Quick Start 增加 `python examples/demo.py` 数据生成步骤；测试统计更新为 503 passed / 49 files
- **CODE_WIKI**: 数据格式表复权因子文件名改为 `stock_adj.pkl`
- **仓库卫生**: `memory/` 加入 `.gitignore` 并移出版本跟踪（本地 8 个 JSON 保留）；`conversation/` 7 个文件归档至 `docs/archive/conversation/`，`archive/` 忽略规则收窄为根级 `/archive/`
- **代码格式基线（TD-9 / P-003）**: `black` 全量重排 **126 个 Python 文件**（`core/`、`tests/`、`examples/`、`agents/`、`filter/`、`web/` 等 14 路径），纯格式变更——125 个文件经 AST 等价性机械验证（唯一差异为 docstring 行尾空白清理，`__doc__` 相关断言均为子串匹配不受影响），全量 `507 passed` 零回归；`black` 版本由 `>=23.0.0` 锁定为 `~=26.0`（black 官方同年度格式稳定性政策）；`black-check` 门禁命令由 `black --check core tests` 扩展为 `black --check .` 并**首次转绿**；新增 `.git-blame-ignore-revs` 保持历史 blame 可追溯（需本地 `git config blame.ignoreRevsFile .git-blame-ignore-revs` 启用）。**已知未覆盖**：CI 仍未加入格式校验步骤

### Removed
- **P-012 协议收窄（零数值）**: 删除 `IFactorPipeline.process_single` / `IFactorCombiner.combine_single`（全仓 0 实现 0 调用）；`IExecutionSimulator.execute_order` 形参以实现为准（`open_price` + 可选 OHLC/volume），删除 `price`/`**kwargs`
- **旧版过滤器**: 移除 `filter/universe.py`（生产零引用，`filter/__init__.py` 早已导出 clean 版）；2 个测试的导入迁移至 `filter.universe_filter_clean`
- **TD-3 Stage 3 / P-001 — 移除 Engine V1**: 删除 `core/engine.py`（724 行，`BacktestEngine`），删除仅诊断 V1 且 0 收集的 `tests/test_visual_trace.py` 与 `tests/test_visual_trace_v2.py`，删除 `tests/test_rebalance_exits.py` 中 g2/g3 两个 V1 专用用例（等价性证据保留在本文 R-1 受控对比与 `docs/DIFF_REPORT_2026-10-23.md`）；6 个 `examples/` 脚本迁移至 `core.factory.create_default_engine()`（`full_backtest_2020_2026_simple.py` 改为手工装配 `BacktestEngineV2`，并顺带修复其 5 个不存在模块的导入）；本地测试 509 → 507 passed、测试文件 50 → 48。**行为说明**：`examples/demo.py` 改由 V2 执行 `FactorPipeline`，合成数据的数值输出随之变化（无 golden 断言，属预期）

### Docs
- **P-012 文档与决策**: 新增 `docs/RESEARCH_bias_interface.md` / `DESIGN_p012_bias_interface.md` / `IMPL_p012_bias_interface.md` / `CHECKLIST_p012_bias_interface.md`（74 项验收 73/74，G7 待远端 CI）；ADR-017 状态 📋 → ✅ 已实施；`PROGRESS.md` §3.13 回填 Step 9 读数与 F-S9-1~F-S9-9
- **台账校正**: `docs/PROGRESS.md` 快照刷新至 `df652f9`（Agg `509 passed`、black `75/5`、默认后端 Tk 失效读数）；关闭 U-004；`CHECKLIST_spec_runner_integration.md` §8 静态读码证据升级为 E3 @`df652f9`
- **进度台账**: 新增 `docs/PROGRESS.md` 与 `docs/dev-log/DEV-LOG-001-progress-baseline-20261104.md`，按 `Spec_Workflow` v1.7.1 登记 T1/T3 档位、证据等级与未决项；`docs/SPEC_STANDARD.md` 标注外部权威源
- **Spec 规则增补**: `docs/SPEC_STANDARD.md` v1.1.0 新增 §十一，规定设计/实施/验收/TDD 阶段的搜索工具调用与外部案例锚点（T1-T4 分级、降级链、反模式、环境态工具映射）
- **方案对比矩阵规则**: 同文件 §11.8 规定 Type-1 决策的 7 维矩阵（成本 / 收益 / 兼容 / 维护 / 升级潜力 / 短期 / 长期）逐格取证，每方案 ≥2 个外部 T1/T2 锚点覆盖 ≥3 维、每维度行至少一个外部锚点；前置声明时间口径与 Type-1/2 判定；接入 Phase 0 §3、Phase 0/1 Review 与 Design §2A；新增 `docs/dev-log/DEV-LOG-003-comparison-matrix-anchors-20261104.md`
- 技术债调研 Phase 0 归档（TD-1~TD-9）；H-1/H-2/H-3 修正状态回填；新增 TD-9 black 格式化基线

---

## [3.2.0] — 2026-06

### Added
- **Spec Standard**: 5-phase spec-driven development workflow (Research → Design → Implementation → Checklist → TDD → Archive)
- **Architecture Doc**: Authoritative `ARCHITECTURE.md` consolidating all architecture analysis
- **DevLog**: `DEVLOG.md` tracking all major changes since v3.0.0
- **Decision Records**: `DECISIONS.md` with 13 ADRs covering architecture, tooling, and process decisions
- **LLM Risk Doc**: `LLM_PREDICTION_AS_TRUTH_RISK.md` with 6-round discussion archive and P0-P5 action plan
- **UI Redesign**: Anthropic Terminal Fusion theme (deep charcoal, amber, terracotta, sage green)
- **Real A-share Validation**: 18 strict validation tests covering data/factor/engine/cost/metrics layers
- **Numba JIT**: @njit acceleration for Engine V3 (0.10ms/5000 stocks, 0.006s for 500×500)

### Changed
- **Architecture cleanup**: Removed all 18 root-level re-export bridge files
- **Import paths unified**: All imports now use `from core.xxx` / `from agents.xxx` consistently
- **`core/__init__.py`**: Rewritten with explicit public API exports (22 entities)
- **`pyproject.toml`**: Consolidated all dependencies; removed `requirements.txt`

### Fixed
- 28+ files updated with corrected import paths after root-file removal
- Test suite updated to reflect new architecture (no stale import tests)
- `core/engine_plugins.py` lazy imports corrected to absolute paths

### Added
- `.github/workflows/tests.yml` — CI pipeline (Python 3.10/3.11/3.12, pytest + mypy)
- `README.md` — Complete rewrite with TradingAgents/Qlib style: badges, architecture diagram, quick start, feature tables, project structure tree, citation template

### Removed
- `_redundant/` directory
- `requirements.txt` (merged into `pyproject.toml`)
- 18 root-level bridge files: `config.py`, `data.py`, `factor.py`, `execution.py`, `portfolio.py`, `rebalance.py`, `tracker.py`, `pending.py`, `analytics.py`, `engine.py`, `agent_framework.py`, `guru_agent_v2.py`, `research_team_v2.py`, `sentiment_framework.py`, `multi_strategy_engine.py`, `style_drift_analysis.py`, `adaptive_agent.py`, `hierarchical_bayesian_agent.py`

---

## [3.1.0] — 2026-05

### Added
- **EventLog**: JSONL persistence + in-memory ring buffer + subscription/query API
- **Guard Pipeline**: Pre-trade safety checks chain (position limit / drawdown / cooldown / turnover / concentration)
- **Plugin System**: Registry + Factory + auto-registration decorators
- **Style Reflection Engine**: Style-aware reflection + anchoring evaluation for Agent strategies
- **Distillation Isolation Audit**: Cross-agent knowledge distillation with safety isolation
- **Dependency Injection (DI)**: `BacktestEngineV2` supports Mock testing via DI
- **Pydantic Config**: `config_v2.py` with schema validation, JSON serialization, hot-reload

### Changed
- **Engine**: `BacktestEngineV2` promoted as primary engine; V1 marked deprecated
- **Risk Monitor**: Five-dimensional engine upgraded with composite scoring and LLM agent integration
- **Agent Framework**: Refactored with belief/signal/reflection base classes

---

## [3.0.0] — 2026-01

### Added
- **Modular architecture**: Refactored from `Backtest_Opus_2.0` monolith
- **Core Engine**: `BacktestEngine` with config-driven setup/run cycle
- **Factor Pipeline**: Winsorize → Fill Missing → Neutralize → Standardize → Combine
- **Portfolio Optimizer**: EqualWeight, MinVar, MeanVar, RiskParity
- **Execution Simulator**: VWAP, TWAP, Close price execution
- **Multi-Agent System**: Guru Agents (Buffett/Soros/Munger/Dalio), Research Team (6 roles), Bayesian Agent
- **Walk-Forward Analysis**: Rolling/Expanding + Purge Gap + Multi-Window
- **Brinson Attribution**: Industry Allocation + Stock Selection + Interaction decomposition
- **Global Contagion**: Cross-market correlation + Volatility spillover + CoVaR + Granger causality
- **Risk Monitor**: Five-dimensional framework (Fundamental / Industry / Macro / CapitalFlow / Sentiment)
- **Stock Filter**: Universe filter with industry, market cap, ST, suspended, limit-up/down
- **Factor_DB**: DuckDB-based multi-source data storage (Price / Factor / Macro / Sentiment / Alternative)
- **Configuration System**: Dataclass-based config with nested validation
- **Batch Backtest**: Multi-factor batch engine with result comparison
- **Strategy Evaluation**: Performance metrics, ranking, and visualization

### Migration
- This is a complete rewrite of `Backtest_Opus_2.0`. No migration path is provided.