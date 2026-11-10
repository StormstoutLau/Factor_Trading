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

### Changed
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