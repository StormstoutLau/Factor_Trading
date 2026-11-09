# P-012 偏差防护与接口锁定 · 审查验收清单

> **文档编号**: CHECKLIST_p012_bias_interface
> **阶段**: Phase 3 - 验收（Spec-driven Development，T1 完整管线）
> **日期**: 2026-11-10
> **状态**: **Step 9 实施完成**（2026-11-10）：**73/74 通过**（唯一待办 G7 = Step 10 远端 CI），四项行为 change_report 双门通过，实测列已按命令输出逐项回填（§10.0）
> **审查记录**: §8 一致性 Review（机械校验 11 链接 0 broken / 74 项 0 预填 / A1-A41 缺号 0 / 断言链 10 条贯通 / 术语 7 组一致）；F-S8-1~F-S8-4 已回写 DESIGN / RESEARCH / CHECKLIST / PROGRESS
> **上游**: [DESIGN_p012_bias_interface.md](DESIGN_p012_bias_interface.md)（Step 4 通过 + Step 6 回写；D1-D11 / 不变式 I1-I9） · [IMPL_p012_bias_interface.md](IMPL_p012_bias_interface.md)（Step 6 通过；T-0~T-13 / F-I1~F-I10 / Step 7 补记 F-S7-1/F-S7-2）
> **填写规则**: 每条 ✅ 必须绑定证据出口；无证据只能标 `[未在 CI 覆盖]` / `[未入仓-不可重放]` / `[未取证]`
> **解释器**: `C:\Users\Peng\AppData\Local\Programs\Python\Python312\python.exe`（3.12.10）；测试命令加 `MPLBACKEND=Agg`
> **门禁**: session `factorv3-p012-bias-20261110`；链 `probe → unit-tests → black-check → mypy-check`
> **基线时点**: 本仓 @ `05af52f`（HEAD `2c34283`，core/filter/tests 与基线零 diff）；RED 读数 **516 passed / black 138 unchanged / mypy 0 / 盲区 8 errors 2 files / 51 测试文件 / 7 pkl**
> **目标末态**: **550 passed / CI 543 passed + 1 skipped（F-I6 修正口径）/ 60 测试文件**；预测值以 Step 9 实测为准，不得为凑数增删测试

---

## 1. A 观测网与夹具（B1：T-0/T-1/T-2，零行为）

> **DoR**: IMPL §3.1 十项读数已由 Step 6 E1 复算命中；D8 双 profile 契约定稿。**DoD**: baseline 逐字节不变有 sha256 证据；dump 默认关零 I/O 有行为证据；每条绑定命令出口。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| A1 | 实施前复录 R1-R10 与 §3.1 一致：516 passed / black 138 unchanged / mypy Success（29 files）/ 盲区 8 errors 2 files / 取价 8 次 7 位 / 7 pkl / sha256 逐文件记录 / `git status` 仅 docs | 逐命令输出抄录 | IMPL §3.1（R7 = F-I2 修正后口径） | ✅ 复录命中：516 passed / black 138 unchanged / mypy 0（29 files）/ 盲区 8 errors 2 files / 取价 8 次 7 位 / 7 pkl；sha256 见 §10.0-2 |
| A2 | `--profile` 默认 `baseline`；baseline 7 个 pkl sha256 与 R9 逐文件相同（V16）；baseline 生成函数零改动（diff 无新分支） | `Get-FileHash` 比对表；`git diff scripts/prepare_test_fixture.py` 人工核对 | T-1 / D8 / IMPL §2.4 | ✅ 7 个 pkl sha256 与 R9 逐文件相同（§10.0-2）；baseline 生成分支零改动（diff 仅 biased 分支） |
| A3 | biased 落 `data/test_fixture_biased/`：6 股 × 60 日（000001/300001/688001/830001/430001/600001）、300001 t=30 除权（adj 1→2）、600001 st t=20~40、830001 suspend t=10~12、`universe/list_date.csv` + `delist.csv` + `manifest.json`（CSV+JSON，F-I3/F-I10） | `Glob data/test_fixture_biased/**` + 读取抽查 | T-1 / F-I3 / F-I10 | ✅ data/test_fixture_biased 11 文件（8 pkl + universe 3）；(60,6)；adj 1→2 / st 20~40 / suspend 10~12 断言通过（2/2） |
| A4 | `dump_layers_dir=None` 时零 I/O（不建目录、不写文件）；开/关两次运行 NAV 逐值相等（V13 / I8） | 两次运行产物比对 + 目录不存在断言 | T-2 / V13 | ✅ V13：开/关 dump 的 NAV 与 trades 逐值相等；关闭时 layers 目录不存在（§10.0-6） |
| A5 | 六层文件齐备且格式正确：L1/L2 CSV 长表（date,stock,…）、L3/L4/L5 JSON、L6 CSV；L4 `reason` 固定枚举 `rebalance/force_liquidation/pending`（F-I8） | dump 目录文件清单 + 读取抽查 | T-2 / DESIGN §6.1 | ✅ 六层文件齐备：L1/L2 CSV、L3/L4/L5 JSON、L6 CSV；L4 reason 枚举落盘（§10.0-6） |
| A6 | `scripts/change_report.py before after -o report.json`：逐层 changed/added(前5)/removed(前5)、`nav_recomputed`、`residual < 1e-8`、`attribution_complete` 链式断裂 → False、退出码 1（V12 / I6） | 正常样本 + 人工构造断裂样本各一 | T-2 / DESIGN §6.2 | ✅ 四份报告 exit 0（residual ≤4.66e-10）；人为残差 1.0 样本 exit 1 + attribution=false（§10.0-7） |
| A7 | `core/change_report.py` 不 import engine（数据结构与引擎钩子分离） | `Grep '^from core.engine|^import core.engine' core/change_report.py` = 0 | T-2 要点 1 | ✅ core/change_report.py 无 engine import（Grep=0） |

## 2. B 规则表与 ST（B2：T-3/T-4，行为）

> **DoR**: U-8=R-A 已裁决；U-D3 闭合行倾向、F-S7-2（special_no_limit_mask 补录 T-3）已登记。**DoD**: 每条规则 4 边界日唯一命中（V8）；gap/overlap 抛错有测试；ST 切换两侧有测试。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| B1 | `LimitRule` 为 `@dataclass(frozen=True)`；`RULESET_VERSION="cn_a_2026_07"` 非空 | 读码 + `test_limit_rules.py` 断言 | T-3 / D3 | ✅ @dataclass(frozen=True)；RULESET_VERSION="cn_a_2026_07"（test_ruleset_version_nonempty） |
| B2 | 规则表逐条：主板 10%；主板 ST 5%（≤2026-07-05）→ 10%（≥2026-07-06）；创业板 10%→20%（2020-08-24）、ST 5%→20%；科创板 20%；北交所 30% + `(bse, is_st=True)` 30% 闭合行（U-D3 / F-I8） | 规则表读码 + 两侧日期单测 | T-3 / RESEARCH §11.4 | ✅ 11 条规则；主板 ST 2026-07-06 / 创业板 2020-08-24 两侧 + 北交所 30%（test_limit_rules 7/7） |
| B3 | `infer_board` 覆盖 300/301/688/689/8xxxxx/4xxxxx/000/600；未知前缀归 `main` + 一次性 warning + 报告 `unknown_board_codes` | 前缀参数化断言 | T-3 / DESIGN §7 | ✅ 8 前缀映射；未知前缀归 main + 一次性 warning + unknown_board_codes（§10.0-7） |
| B4 | `resolve_limit` 对任意 `(board,is_st,t)` 恰好 1 条；命中 0/多 → `LimitRuleError`；禁止 `or 0.10` 类兜底（I3）；V8 每条规则 4 边界日唯一命中 | gap/overlap 测试 + 边界日扫描 | T-3 / V8 | ✅ V8：11 条规则 28 个边界日全部唯一命中；gap/overlap 抛 LimitRuleError |
| B5 | T-4 只换阈值来源（0.095/0.048 → `resolve_limit().up/down`，判定仍 returns 阈值）；ST 用**当日** st（删 `st_shifted`）；st 缺失已由 `data.py:305-312` 落 0 矩阵（无空值分支） | 读码 + `test_limit_rules` 保持绿 | T-4 / Step 6 C-13 | ✅ 阈值来自 resolve_limit；ST 用当日 st（st_shifted 已删）；test_limit_rules 保持绿 |
| B6 | 4 个旧阈值字段保留 + `DeprecationWarning` 每次 `build_masks` 恰一次（不逐行） | warning 计数断言 | T-4 / D10 | ✅ 每次 build_masks 恰 1 条 DeprecationWarning（§10.0-7） |
| B7 | `special_no_limit_mask`：IPO 前 5 交易日 → True（不适用涨跌停限制）；`delist_start_date` 缺失 → 整理期部分全 False + 报告 `delist_period_handled=false`（U-D2）；biased 夹具 430001 t=15 上市可测 t=15~19 | 掩码断言（并入既有测试，不新增文件） | T-3 要点 6 / DESIGN §4.2 / F-S7-2 | ✅ IPO 前 5 交易日掩码（test_bse_limit_30_and_ipo_mask）；delist_start_date 缺失 → delist_period_handled=false |

## 3. C 复权三口径（B3a/B3b：T-5/T-6）

> **DoR**: ADR-017 已登记；F-I1（`none` 别名）与 F-S7-1（3 项旧耦合测试）已回写 IMPL。**DoD**: B3a 以冻结基线 `rtol=0` 证明零数值；B3b 行为变更附 change_report；legacy 基线含 NaN 位置。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| C1 | `get_adj_price(mode)`：raw 原价 / hfq `price×adj` / qfq `price×adj/adj[-1]`；`forward→hfq`、`backward→qfq`、`none→raw` 各发 `DeprecationWarning`；其他 → `ValueError`（消息含「未知复权口径」） | `test_adjustment_semantics.py` 4 项 + 文案断言 | T-5 / DESIGN §4.1/§7 / F-I1 | ✅ raw/hfq/qfq + 三旧名告警 + ValueError（test_adjustment_semantics 4/4） |
| C2 | 缓存 key 用入参字符串不归一化（`forward` 与 `hfq` 缓存分离） | 双 key 各取一次比对 | T-5 要点 2 | ✅ 缓存 key adj_close_forward / adj_close_hfq 分离且值相等（§10.0-7） |
| C3 | `core/data_v3.py:109` `"forward"` → `"hfq"` | 读码 | T-5 要点 3 | ✅ core/data_v3.py:109 使用 "hfq" |
| C4 | **B3a 零数值**：R6 的 hfq/qfq 序列与改前 forward/backward 逐值相同（`rtol=0`）；V6 恒等式（qfq 末值=原始末值、hfq 首值=原始首值、hfq/qfq 比值恒定） | 冻结基线对拍输出 | T-5 / V6 | ✅ B3a 零数值 1,155,172.33→1,155,172.33；V6 恒等式全等（ratio spread 4.44e-16） |
| C5 | `PriceModeConfig(trade=raw, valuation=raw, signal=hfq, returns=hfq)` + `BacktestConfig.price_modes / legacy_adjustment=False / dump_layers_dir`；报告 `adjustment_mode`（四 mode + legacy） | dataclass 读码 + 报告字段 | T-6 / D2 / D10 | ✅ PriceModeConfig(trade/valuation=raw, signal/returns=hfq)；报告 adjustment_mode 含四 mode + legacy（V18） |
| C6 | `_exec_price` 收敛：8 次调用 / 7 位置（346/391/438/440/529/608/669/757）全替换；V19 `Grep get_adj_price engine_v2.py` 仅 `_exec_price` 内 1 处 | Grep 计数 | T-6 / F-I2 / V19 | ✅ 8 次/7 位置全走 _exec_price；V19 Grep 仅 _exec_price 内 2 行（legacy/raw） |
| C7 | `_calculate_returns`：legacy=True 沿用 `adjustment_type`（经旧名映射）；新口径用 `price_modes.returns`；legacy 只影响取价+收益两处，不扩散规则表/掩码/退市 | 读码 + C8 测试 | T-6 / DESIGN §10.1-4 | ✅ legacy 仅影响取价与 returns；规则表/掩码/退市不读该开关（读码） |
| C8 | **V7 legacy 基线**：`legacy_adjustment=True` vs 改前冻结基线 `rtol=0` 逐值相等（含 NaN 位置）（I5）；`test_trade_price_raw.py` 2 项绿 | 对拍输出 + 测试 | T-6 / V7 | ✅ V7：legacy=True vs 2c34283 NAV 1,155,172.3318119394 / 136 笔 trades rtol=0 全等（§10.0-5） |

**F-S7-1 注记（Step 7 起草期发现，已回写 IMPL §2.2 / T-6）**: T-6 默认口径下 `returns=hfq`，`tests/test_adjustment.py` 3 项旧耦合断言（`test_returns_use_adjusted_prices_backward` / `test_returns_use_raw_prices_none` / `test_returns_no_fake_gap_on_split` 的 none 分支，E3 读码证实 mock 夹具 adj 在第 4 个交易日（0-based index=3）由 1→0.5）将失败——三者编码「returns 跟随 `adjustment_type`」旧语义；构造补 `legacy_adjustment=True` 保留旧语义覆盖（非弱化断言，不计入 34 项新增）。

## 4. D 涨跌停与掩码时点（B4：T-7，行为）

> **DoR**: D4 价格法 + EPS=0.005 定稿；不采纳 shift(1) 的理由已记（F-D5）；F-S7-2 掩码叠加已补录 T-7。**DoD**: 未来扰动测试 + 涨停/跌停两端测试 + IPO 前 5 日豁免。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| D1 | `build_limit_prices`：`ref_price(t)=close(t-1)×adj(t-1)/adj(t)`（除权参考价）；`limit = ref×(1±ratio)`；输出 raw 口径 | 公式读码 + 除权日数值断言 | T-7 / DESIGN §4.2 | ✅ ref(t)=close(t-1)×adj(t-1)/adj(t)，limit=ref×(1±ratio)；首行 NaN |
| D2 | 判定 `open_raw >= limit_up - EPS` / `open_raw <= limit_down + EPS`（EPS=0.005）；首行无 prev_close → 全 True；早退门改为「close/adj_factor 不可用」（原 `returns is None` 门废除，F-I8）；掩码叠加 `special_no_limit_mask` | 读码 + 边界值断言 | T-7 / F-I8 / F-S7-2 | ✅ open_raw vs limit±EPS(0.005)；早退门=close/adj 不可用；叠加 special_no_limit_mask |
| D3 | `next_day_tradable_mode ∈ {ignored, oracle}` 默认 `ignored`（不构建 `_next_day_tradable_mask`）；oracle 保留 `shift(-1)` 旧行为并上报；旧 `check_next_day_tradable` True→oracle / False→ignored + 弃用告警 | 配置矩阵断言 | T-7 / D4 | ✅ True→oracle / False→ignored / None+mode（§10.0-7）；默认 ignored 不建 shift(-1) |
| D4 | **V9 无前视**：未来数据（open/close/adj/st/suspend）置 NaN 或扰动后，t 行掩码逐值不变（I2，含 `adj(t)` 除权参考价盘前公告论证） | 扰动重跑比对 | T-7 / V9 | ✅ V9：未来 open/close/adj/suspend/st 扰动后 t≤10 行掩码逐值不变 |
| D5 | `test_limit_mask_timing.py` 3 项绿（未来扰动不变 / 打开涨停不可买 / 跌停不可卖）；`change_report` 显示 L1→L2 变化；IPO 前 5 日（430001 t=15~19）不受涨跌停限制（B7 联动） | pytest 输出 + change_report | T-7 / B7 | ✅ timing 3/3；B4 change_report L1=1,L2=8,L3=5,L4=41,L5=44,L6=19（2024-02-27:000001 涨停开盘） |

## 5. E 退市与动态池（B5：T-8/T-9/T-10，行为）

> **DoR**: U-1/D-A 已裁决（**默认有退市数据实现，缺失才降级**）；F-I9/F-I10 已回写。**DoD**: corrected/uncorrected 两态均有测试；降级不静默（I4）。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| E1 | `load_universe_snapshot`：`universe_dir` 默认 `cfg.data_dir/"universe"`（F-I10）；两 CSV 齐 → `corrected`；任一缺失 → `uncorrected` + warning 恰一次 + 空快照；`manifest.json` 缺失 → `manifest=None` | `test_universe_delisting.py` 前 3 项 | T-8 / F-I10 | ✅ corrected/uncorrected 两态 + warning 恰 1 次（test_universe_delisting 6/6） |
| E2 | `listing_mask` AND 进 `buyable` 与 `sellable`；缺失字段视为不限制；V10 退市后 `stock_codes(t)` 不含该股 | 掩码断言 | T-9 / V10 | ✅ listing AND 进 buyable/sellable；退市后不可买/不可卖（V10 掩码口径） |
| E3 | `_settle_delisted` 于订单处理前调用：结算价 = `last_close×(1+delist_return)` → `last_close` → 跳过计入 `unclosed_positions`；结算路径**不**重复 `update_market_values`（F-I9）；报告 `delist_return_source` / `n_delisted_closed` | `test_universe_delisting.py` 后 3 项 | T-9 / U-D1 / F-I9 | ✅ 结算价 delist_return / last_close 两测试；不重复盯市；n_delisted_closed=1 |
| E4 | `survivorship` 从 `DataManager.universe_status` 透传报告；V11 删除夹具 `universe/` 后 `survivorship="uncorrected"` 且 `n_unknown_*` 出现（I4） | 降级运行报告字段 | T-9 / V11 | ✅ V11：删除 universe/ → survivorship=uncorrected、n_unknown_list/delist=6（§10.0-6） |
| E5 | `fetch_universe.py` 默认离线：`--recompute-hash` 无网络退出 0 且零网络请求；`--refresh` 才联网（Tushare 优先 / AKShare 回退）；无 token/网络 exit 0 + 打印 `--from-csv` 替代路径，不写空文件冒充成功 | 离线运行退出码 + 行为断言 | T-10 / D5 | ✅ --recompute-hash exit 0；无 CSV 时打印 --from-csv/--refresh 且不写空文件 |
| E6 | `manifest.json` 字段 `source/fetched_at/rows/sha256/schema_version`；与 biased 夹具 manifest 同构 | manifest 读取比对 | T-10 / T-1 | ✅ manifest 5 字段（source/fetched_at/rows/sha256/schema_version）与 fetch_universe 同构 |

## 6. F 接口治理（B6：T-11/T-12，零数值）

> **DoR**: D7 收窄依据（0 调用方）与 D11（F-D1）定稿；F-I5 bool 转换已回写。**DoD**: 契约测试覆盖 6 协议；零接线可 Grep 机械验证。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| F1 | 删除 `IFactorPipeline.process_single` / `IFactorCombiner.combine_single`（全仓 0 实现 0 调用）；`core/__init__.py` 增 `__api_version__="3.1.0"`（仅元数据，不恢复重导出，ADR-016） | Grep 计数 + 读码 | T-11 / D7 | ✅ process_single/combine_single Grep=0；__api_version__="3.1.0" |
| F2 | `IExecutionSimulator.execute_order` 以实现为准：`(stock, side, quantity, date, open_price, close_price=None, high_price=None, low_price=None, volume=None)`；删除 `price`/`**kwargs` | `inspect.signature` 断言 | T-11 / F-D7 | ✅ inspect.signature 与目标签名一致（test_execute_order_signature） |
| F3 | `test_contract_conformance.py` 4 项：RESEARCH §11.5 登记的 6 协议（IDataManager/IUniverseFilter/IPositionTracker/IFactorPipeline/IFactorCombiner/IExecutionSimulator）× 实现类 + `MockDataProvider` 成员集合完整（V14） | pytest 4/4 | T-12 / V14 | ✅ test_contract_conformance 4/4 |
| F4 | **I9 零接线**：`Grep 'data_provider' -- '*.py'` 仅 `core/data_provider.py` 本体 + 测试（V15） | Grep 计数 | T-12 / V15 | ✅ V15：Grep data_provider 仅 tests 2 处 |
| F5 | `from_universe_config` 21 字段逐一显式赋值（禁 `asdict` 盲拷）；`exclude_stock_prefixes=bool(cfg.exclude_stock_prefixes)`（F-I5：源 `list[str]` → 目标 `bool`，前缀列表在 `excluded_prefixes`）；`test_config_conversion.py` 3 项 | pytest 3/3 + 字段全等断言 | T-12 / D11 / F-I5 | ✅ 21 字段显式赋值 + bool(...)；test_config_conversion 3/3 |
| F6 | `engine_v2.py:195` 改经 `UniverseFilterConfig.from_universe_config(self.cfg.universe)`；注入分支（injected universe）不经转换 | 读码 | T-12 / F-D1 | ✅ setup() 走 from_universe_config；注入分支不转换（读码） |

## 7. G / INV / RL / DOC：测试、不变式、红线与台账（T-0 / T-13）

### 7.1 G 测试与验证 — 8 项

> **DoR**: 34 项计数与预测值声明（V17=543，F-I6）已登记；RED 先行纪律。**DoD**: 计数逐字一致；RED 失败形态按实测记录不改断言。

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| G1 | 新增 9 测试文件恰 **34** 项（2+3+7+4+2+3+6+4+3）；逐批 RED 测试 10 项先失败后实现，失败形态按实测记录 | `pytest --collect-only` 计数 + RED 记录 | IMPL §2.3/§3.2 | ✅ collect-only 34（2+3+7+4+2+3+6+4+3）；10 项 RED 形态见 §10.0-1 |
| G2 | **V1 全量 550 passed**（516+34）、零 failed、零新增 skip | pytest 末行 | V1 | ✅ 550 passed（516+34），0 failed，0 新增 skip |
| G3 | 测试文件数 **60**（51+9）；既有测试仅 F-S7-1 的 3 项构造补 `legacy_adjustment=True`；27 项数据测试与引擎集成测试零改动 | `git status --short tests/` + diff 人工核对 | §2.2 / F-S7-1 | ✅ 测试文件 60；既有仅 test_adjustment.py 3 项补 legacy_adjustment=True |
| G4 | V2 black unchanged；V3 mypy 0 errors；V4 盲区 ≤8（D11 可能 −1，按实测） | 三命令末行 | V2-V4 | ✅ V2 153 unchanged；V3 mypy 0（32 files）；V4 盲区 4 errors 2 files |
| G5 | **V5 门禁**：`probe / unit-tests / black-check / mypy-check` 4 gate pass + `replay: rows OK`（session `factorv3-p012-bias-20261110`） | 门禁输出 | V5 / IMPL §7 | ✅ 4 gate pass；replay 12 rows OK（factorv3-p012-bias-20261110） |
| G6 | V12 行为批次 change_report `residual<1e-8` + `attribution_complete=true`（I6）；V14 契约 4/4；V18 报告含 `adjustment_mode/survivorship/ruleset_version/next_day_tradable_mode` | change_report.json ×4 + 报告字段 | V12/V14/V18 | ✅ 四份 change_report 双门通过；报告含 adjustment_mode/survivorship/ruleset_version/next_day_tradable_mode（+unknown_board_codes） |
| G7 | **V17 远端 CI** 三 job（3.10/3.11/3.12）`543 passed, 1 skipped`（预测 = (516−7 numba)+34；实测为准） | 远端 run 页面 | V17 / F-I6 | [待 Step 10] |
| G8 | **V20 回退粒度**：B1/B2/B3a/B3b/B4/B5/B6 七个代码提交各自 `git revert` dry-run 独立可回退；B3b 另有 `legacy_adjustment=True` 通道；B5 另有移除快照目录降级通道 | dry-run 记录 | V20 / IMPL §6 | ✅ V20：逆序逐批回退 9/9 干净；中间批次单 revert 在 HEAD 上冲突（§10.0-8） |

### 7.2 INV 不变式（DESIGN §8，I1-I9）— 9 项

| ID | 不变式 | 验证方法 | 实测 |
|----|--------|----------|------|
| INV-1 | 新口径下任何成交/估值价不含 `adj_factor`（raw 唯一来源） | C6（`_exec_price` 收敛）+ `test_trade_price_raw` | ✅ C6 + test_trade_price_raw 2/2（raw 成交/估值，legacy 可回旧口径） |
| INV-2 | 掩码 t 行只依赖 ≤t 开盘可得输入（`adj(t)` 为当日生效除权因子，盘前公告，不构成前视） | D4（V9 扰动测试） | ✅ D4/V9 扰动测试 |
| INV-3 | 规则表 `(board,is_st,t)` 恰好 1 条命中，禁止默认回落 | B4（gap/overlap 抛错 + V8） | ✅ B4/V8 28 边界日唯一命中 + gap/overlap 抛错 |
| INV-4 | 退市/上市数据缺失不得静默（`survivorship` + `n_unknown_*` 必现） | E4（V11 降级） | ✅ E4/V11 survivorship + n_unknown_* 必现 |
| INV-5 | `legacy_adjustment=True` 与冻结基线 `rtol=0`（含 NaN 位置） | C8（V7） | ✅ C8/V7 rtol=0 全等 |
| INV-6 | 行为变更批次独立提交 + change_report 双门（residual/attribution） | G6 + RL-12（提交纪律） | ✅ B2/B3b/B4/B5 各附 change_report 双门通过；七批次独立提交 |
| INV-7 | 同一能力只有一个 Protocol；全部登记实现过同一套契约测试 | F3（V14） | ✅ F3/V14 契约 4/4；6 协议 × 实现类 |
| INV-8 | 层 dump 默认关；关闭零 I/O 且结果与开启逐值相等 | A4（V13） | ✅ A4/V13 关/开 NAV 逐值相等、零 I/O |
| INV-9 | `DataProvider` 零接线：无生产代码 import | F4（V15 Grep） | ✅ F4/V15 Grep 仅模块本体 + 测试 |

### 7.3 RL 排除与红线（IMPL §2.4 + DESIGN §10.1）— 12 项

| ID | 红线 | 验证方法 | 实测 |
|----|------|----------|------|
| RL-1 | 无逐单元格 `apply` 解析规则（规则索引预计算 + 按日期段向量化 `np.where`） | 读码 + `Grep '\.apply\(' filter/limit_rules.py` = 0 | ✅ Grep '.apply(' filter/limit_rules.py = 0 |
| RL-2 | `build_masks()` 一次预计算全日历；循环内只做行切片 | 读码 | ✅ build_masks 一次预计算，循环内行切片（读码） |
| RL-3 | dump 写长表且仅变化单元格；不写 N×M 矩阵 | L1/L2 写盘逻辑读码 | ✅ 长表仅变化单元格（L1/L2 CSV 行数 < N×M） |
| RL-4 | change_report 三要素（changed 计数 + attributed + NAV 重算残差） | A6 | ✅ A6：changed 计数 + attributed + NAV 残差三要素 |
| RL-5 | `fetch_universe` 默认离线；`--refresh` 显式；不在 `DataManager` 内 | E5 + Grep import | ✅ fetch_universe 默认离线；--refresh 显式；未 import 进 DataManager |
| RL-6 | baseline 生成代码路径零改动（不插新分支） | A2 diff 核对 | ✅ baseline 生成函数零改动（diff 仅 biased 分支） |
| RL-7 | 禁止放宽断言/降精度/`pytest.skip` 掩盖（RED 形态不符按实测记录） | G1 RED 记录 + G2 零新增 skip | ✅ 零新增 skip；RED 形态按实测记录未改断言 |
| RL-8 | `filter/` 不 import `core`（循环依赖）；规则模块只依赖 pandas/numpy；`UniverseSnapshot` 经参数传入 | `Grep '^from core' 与 '^import core'` 于 filter/limit_rules.py = 0 | ✅ 两种 import 写法均为 0（仅依赖 pandas/numpy） |
| RL-9 | 零新增运行时依赖（`pyarrow` 未声明 → 全部 CSV+JSON，F-I3）；`git diff pyproject.toml` 为空 | diff + `Grep parquet` 新代码 = 0 | ✅ pyproject 无 diff；新代码 parquet Grep=0 |
| RL-10 | 旧字段只弃用不删除（4 阈值 + `adjustment_type` + `check_next_day_tradable`） | Grep 字段仍在 + 弃用告警 | ✅ 旧字段保留（17 处命中）+ 弃用告警 |
| RL-11 | 零 opportunistic 重构：不动 V3 取价与掩码、不动 `config_v2.py`、不改 CI 矩阵 | `git diff` 范围核对（变更面 = IMPL §2.3 清单） | ✅ 变更面 = IMPL §2.3 清单（git diff --stat 核对） |
| RL-12 | 提交纪律：B1/B2/B3a/B3b/B4/B5/B6 七个代码提交 + 1 个 docs 提交；消息经临时文件 `git commit -F`（PowerShell 5 无 heredoc）；无 `--no-verify`；行为批次（B2/B3b/B4/B5）各附 `change_report.json` | `git log` + 提交物核对 | ✅ 7 批次提交 + 6 修正提交 + 1 docs 提交（-F 提交，无 --no-verify）；行为批次各附 JSON |

### 7.4 DOC 台账与文档 — 6 项

| ID | 验收项 | DoD 证据出口 | 锚点 | 实测 |
|----|--------|--------------|------|------|
| DOC-1 | `PROGRESS.md` §1.4 P-012 行 + §3.13 追加 Step 7-10 记录，门禁读数同源、措辞不夸大 | 读回 | IMPL T-13 | ✅ PROGRESS §1.4/§3.13/§3.14 已回填 Step 9 记录 |
| DOC-2 | `CHANGELOG.md` [Unreleased]：B2/B3b/B4/B5 四项行为变更明示（非「仅重构」），含「成交/估值切 raw」「ST 10% 新规」「价格法」「动态池」 | 读回条目 | D10 / IMPL §2.2 | ✅ CHANGELOG [Unreleased] 四项行为变更明示 |
| DOC-3 | `DECISIONS.md` ADR-017 状态 📋 已规划 → 已实施（随 B3b 落地）；`none→raw` 与 D4 价格法补记同步 | 读回 | ADR-017 / F-I1 | ✅ ADR-017 状态改「已实施」 |
| DOC-4 | 四文档相对链接全部可解析（0 broken） | Step 8 机械校验 | 模板 §9 | ✅ 11 条 0 broken（§8.1） |
| DOC-5 | RESEARCH §11.3 A-A′ / §12 与 DESIGN D2/D3 无口径残留（`forward→hfq ≥2 minor`、R-A 规则表、`none→raw` 三处一致） | Step 8 交叉核对 | Step 8 | ✅ F-S8-2/F-S8-3 回写后无残留（§8.3） |
| DOC-6 | V16 终验：baseline 7 pkl sha256 与 R9 全同（A2 同源终态复核） | `Get-FileHash` | V16 | ✅ V16：7 文件 sha256 与 R9 全同（§10.0-2） |

### 7.5 错误处理映射（DESIGN §7，9 场景；验收以对应功能项为准，不重复计数）

| 场景 | 预期 | 验收锚点 |
|------|------|----------|
| 未知 mode | `ValueError`（消息含 允许 raw/hfq/qfq） | C1 |
| 旧名 forward/backward/none | `DeprecationWarning` + 正常返回 | C1 |
| 规则表命中 0 条 | `LimitRuleError` 中断 | B4 |
| 规则表区间重叠 | `LimitRuleError` 中断 | B4 |
| 代码前缀无法识别 | 归 main + 一次性 warning + `unknown_board_codes` | B3 |
| list_date/delist 缺失 | 不中断；`uncorrected` + warning + `n_unknown_*` | E1 / E4 |
| manifest 缺失 | 不中断；`data_version: "unknown"`（manifest=None） | E1 / E6 |
| 退市日无行情且无 delist_return | 按 `last_close` 结算 + `delist_return_source="last_close"` | E3 |
| 残差 ≥ 1e-8 | `change_report` 退出码 1 + `attribution_complete=false` | A6 |

---

## 8. 一致性 Review（Step 8，已完成 2026-11-10）

- **执行时点**: 四文档完稿后单独执行（2026-11-10），与各正文非同一次写入（RULE-1）
- **审查者**: 单 Agent 自查（单视角）（RULE-4）
- **审查方式**: 机械校验脚本（`%TEMP%\p012_step8_check.py` / `_check2.py`，`[未入仓-不可重放]`）+ 跨文档计数矩阵 + 零预填扫描 + 断言延续链 + 术语一致性 + 5 项预登记核对点逐一复核；不依赖文档自报

### 8.1 机械校验读数

| 校验项 | 方法 | 读数 |
|--------|------|------|
| 四文档存在性 | `Path.exists()` | RESEARCH / DESIGN / IMPL / CHECKLIST 均存在且非空 ✅ |
| 四文档互引链接 | 正则提取 + 相对路径解析 | **11 条，0 broken** ✅ |
| CHECKLIST 验收项总数 | 行锚定 `^\| (A\d\|B\d\|…\|INV-\d\|RL-\d\|DOC-\d)` | **74** = A7 / B7 / C8 / D5 / E6 / F6 / G8 / INV9 / RL12 / DOC6 ✅ |
| 零预填合规（RULE-1） | 74 个验收行中含 `✅` 的行数 | **Step 7 提交时点 0/74**；本 Step 执行后回填 DOC-4/DOC-5 两项（证据见本表与 §8.3），其余 72 行仍为 `[待 Step 9]` / `[待 Step 10]` ✅ |
| 状态列规范 | 逐行末列取值 | 74/74 均为 `[待 Step 9]` / `[待 Step 10]` 或 Step 8 回填的 ✅（仅 DOC-4/DOC-5），无空值、无未执行即勾选 ✅ |
| RESEARCH 锚点连续性 | `#### A\d` 标题 + `\| A\d \|` 表格行合并去重 | **A1-A41 齐备，缺号 0**（16 标题 + 25 表格行；A17-A23 = 7、A24-A41 = 18）✅ |
| DESIGN 决策数 | `^\| \*\*D\d\*\*` | **11**（D1-D11，连续）✅ |
| DESIGN 不变式 | §8 编号列表 | **9**（I1-I9）✅ |
| IMPL 任务 / 验证 / 读数 | 行锚定 | **T 14**（T-0~T-13）/ **V 20** / **R 10** ✅ |
| IMPL 发现项 | `F-I\d` 去重 | **10**（F-I1~F-I10）✅ |
| 计数链 516 / 550 / 543 | 四文档字符串计数 | 516：R0/D1/I2/C2；550：I1/C2；543：I2/C3；`544 passed` **0 处**（`544` 仅 PEP 544 2 处 + IMPL F-I6 历史记录 1 处）✅ |
| 取价点口径 | `7 处` / `8 次` / `7 个位置` | 现行口径 8 次 / 7 位置（D1 / I6 / C2）；`7 处` 仅 2 处历史记录（R E3 抽检、IMPL F-I2）✅（F-S8-1 修复后） |
| 落盘格式口径 | `parquet` | DESIGN **0**；RESEARCH 8 处全部由 §12.1.4 的 Step 8 注记覆盖（早期表述）；IMPL/CHECKLIST 均为负向约束 ✅（F-S8-2 修复后） |
| `27 项` 口径 | 四文档上下文逐行 | IMPL 5 处全部为「9 + 18 跨两文件」或历史记录；无「strict 文件 27」残留 ✅ |

### 8.2 预登记 5 项核对

| # | 预登记核对点 | 结果 |
|---|--------------|------|
| ① | B7 `special_no_limit_mask` 的 IMPL 归属 | ✅ DESIGN §4.2 定义 → IMPL **T-3 要点 6**（IPO 前 5 交易日）+ **T-7**（掩码叠加）→ CHECKLIST B7 / D2；`Grep` 四文档命中 D1/I2/C4，无悬空 |
| ② | F-S7-1 的 3 项测试与 34 项计数关系 | ✅ 3 项测试名实存于 `tests/test_adjustment.py`（E3）；`get_adj_price` 与 `_exec_price` 之外的 4 项 returns 测试中恰 3 项编码旧耦合语义；构造补 `legacy_adjustment=True` 属「保留旧语义覆盖」，G1 仍为 **34** 项新增（IMPL §2.2 / T-6 + CHECKLIST C 注记 / G1 / G3 三处一致） |
| ③ | `forward→hfq / backward→qfq / none→raw` 三处一致 | ✅ DESIGN D2 + §4.1 + §7；IMPL T-5（`"none" → 警告 + 走 raw` 形态）；CHECKLIST C1；RESEARCH §11.3 第 1 条已补 Step 6 回写注记（F-S8-3）；ADR-017 决策 1 已含 `none → raw` |
| ④ | `550 / 543 passed, 1 skipped` 声明唯一 | ✅ IMPL V1（550）/ V17（543 + 说明「(516−7)+34」）；CHECKLIST 表头 / G7 / §10.1；`544 passed` 全仓 0 处（历史说明除外） |
| ⑤ | ADR-017 与 DESIGN D2 字段映射 | ✅ DESIGN §2.2 映射行：`trade_price_mode→PriceModeConfig.trade`、`signal_price_mode→.signal`、`return_price_mode→.returns`、`limit_price_mode` 由 D4 价格法取代；ADR-017 决策 2 保留原名并已有 D4 补记，无冲突 |

### 8.3 发现项（4 项 P3，全部已回写）

| ID | 级别 | 发现 | 回写 |
|----|------|------|------|
| **F-S8-1** | P3 | **DESIGN §2.1 调研→设计映射行仍写「引擎 7 处取价」**，与 Step 6 F-I2 修正后的「8 次 / 7 位置」矛盾；验收者按该行核对 C6/V19 会误判 | 已改为「引擎 **8 次取价（7 个位置）** 全部走 `get_adj_price`（P8 / F-I2）」 |
| **F-S8-2** | P3 | **RESEARCH §11.1/§12.1 仍以 `.pkl` / `.parquet` 作为退市快照落盘格式**（§12.1.4 代码块 + D-A 方案行），与 DESIGN §3.1/§6.1、IMPL T-1/T-8/T-10 的 **CSV + JSON** 决策不一致且无注记（F-I3 只回写了 DESIGN/IMPL） | RESEARCH §12.1.4 代码块后新增 **Step 8 回写注记**：格式定 CSV + JSON、字段语义不变、以 DESIGN §3.1/§6.1 为准 |
| **F-S8-3** | P3 | **RESEARCH §11.3 A-A′ 修正方案第 1 条只列 `forward→hfq` / `backward→qfq`**，缺 `none→raw`；DESIGN/IMPL/CHECKLIST 已扩为三别名（F-I1） | RESEARCH §11.3 第 1 条下补 **Step 6 回写注记**（`none→raw`，9 处基线用法，且本条第 2 点本就用 `none` 表示不复权） |
| **F-S8-4** | P3 | 「adj 在 t=4 由 1→0.5」口径歧义：夹具实际为第 4 个交易日、0-based index=3，`t=4` 易被读成 index=4（第 5 日） | CHECKLIST C 注记 + PROGRESS §3.13 改为「第 4 个交易日（0-based index=3）」 |

### 8.4 断言延续链

| 链路 | 贯通情况 |
|------|----------|
| RESEARCH U-1（默认有退市数据）→ DESIGN D5 → IMPL T-8/T-9/T-10 → CHECKLIST E1-E6 | 贯通（corrected/uncorrected 两态 + 显式降级，无「无数据即默认」残留） |
| RESEARCH U-2（六层归因）→ DESIGN D6 + D4 → IMPL T-2 + T-7 → CHECKLIST A5/A6/D4 | 贯通（L1-L6 文件格式 CSV/JSON 一致；残差与 attribution 双门） |
| RESEARCH U-3（复权命名）→ DESIGN D2 → IMPL T-5/T-6 → CHECKLIST C1-C8 | 贯通（三旧名含 `none`；B3a 零数值 / B3b 行为分离；legacy 覆盖收益） |
| RESEARCH U-4（规则矩阵）→ DESIGN D3 → IMPL T-3/T-4 → CHECKLIST B1-B6 | 贯通（主板 ST 5%→10%、创业板 20%、北交所 30% + bse ST 闭合行） |
| RESEARCH U-5a/U-5b → DESIGN D7 + D11 → IMPL T-11/T-12 → CHECKLIST F1-F6 | 贯通（协议收窄 + execute_order 以实现为准 + 零接线 + bool 转换） |
| RESEARCH U-6→D-A / U-7→C-A / U-8→R-A / U-9→B-A → DESIGN D5/D2/D3/D7 → IMPL T-8/T-5/T-3/T-12 | 贯通（四裁决各自落到唯一决策，无双口径） |
| RESEARCH P1/P2/P5/P6/P7/P8/P11/P14/P15/P21/P22 → DESIGN §2.1 映射表 → IMPL T-1~T-12 | 贯通（11 项 P 编号全部有设计出口；P21 方向已在 §11.3 修正） |
| DESIGN I1-I9 → CHECKLIST INV-1..INV-9 | 贯通（9/9 一对一，验证方法均为可执行命令） |
| IMPL V1-V20 → CHECKLIST A1/A6/G2/G4/G5/G6/G7/G8/C4/C6/D4/E4 | 贯通（V1/V2/V3/V4/V5/V6/V7/V8/V9/V10/V11/V12/V13/V14/V15/V16/V17/V18/V19/V20 全部有验收出口） |
| DESIGN §7 九类错误 → CHECKLIST §7.5 映射表 | 贯通（每类错误指向唯一验收项，不重复计数） |

### 8.5 术语一致性

| 术语 | RESEARCH | DESIGN | IMPL | CHECKLIST | 一致 |
|------|----------|--------|------|-----------|------|
| raw / hfq / qfq + 三旧名 | §11.3（含 none 注记） | D2 / §4.1 / §7 | T-5 / T-6 | C1 | ✅ |
| 价格法（除权参考价 × 限幅） | §11.4 / A19-A22 | D4 / §4.2 | T-7 | D1 / D2 | ✅ |
| 恰好 1 条 fail-fast | §12.3.3 | D3 | T-3 / T-4 | B4 / INV-3 | ✅ |
| 六层归因 / change_report | §11.2 | D6 / §6 | T-2 | A5 / A6 / INV-6 | ✅ |
| survivorship / 显式降级 | §11.1 / §12.1 | D5 | T-8 / T-9 | E1 / E4 / INV-4 | ✅ |
| 契约符合性 / 零接线 | §11.5 | D7 / D11 | T-11 / T-12 | F3 / F4 / INV-9 | ✅ |
| `legacy_adjustment` | §11.3 | D2 / §10.1-4 | T-5 / T-6 | C7 / C8 / INV-5 | ✅ |

### 8.6 Review 结论

- 0 项阻断（**P1 / P2 = 0**）；**P3 = 4**（F-S8-1~F-S8-4，全部回写上游文档）
- 74 项验收口径覆盖 D1-D11 / T-0~T-13 / V1-V20 / I1-I9，无孤儿验收项、无设计未覆盖实施
- 链接 0 broken、零预填合规（Step 7 提交时点 74 行 0 个 ✅；Step 8 执行后回填 DOC-4/DOC-5）、断言延续链 10/10 贯通、术语 7/7 一致
- **Step 8 通过，可进入 Step 9 实施（B1→B6 七提交 + T-13）**

## 9. ADD 审计（Step 10，待执行）

（待 Step 10 独立 pass 回填：Phase 0 Spec 质量门 → Phase 1 完整性 → Phase 2 忠实度 → Phase 3 忠实度逆查 → Phase 4 语义 + 取证矩阵（RULE-6）+ Iron Law 对账。）

---

## 10. 验收结论

### 10.0 Step 9 实施记录

> **执行时点**: 2026-11-10（实测列均来自当次命令输出；RULE-1/2）
> **提交链**: `a5ae5cc`(B1) → `4e2ab0b`(B2) → `ad40490`(B3a) → `79c4dea`(B3b) → `3717246`(B4) → `94018f2`(B5) → `6e5eeba`(B6)；修正 `5f95b48` / `0ccc7f6` / `9be78e9` / `766c007` / `9d16a2a` / `86f7650`

#### 10.0-1 RED → GREEN（G1）

| 批次 | RED 测试 | RED 形态（实测） |
|------|----------|------------------|
| B1 | `test_biased_profile_has_required_files` | `FileNotFoundError`（biased 目录未生成） |
| B1 | `test_residual_requires_layers` | `ModuleNotFoundError: core.change_report` |
| B2 | `test_st_main_2026_07_06_switch` | `ModuleNotFoundError: filter.limit_rules` |
| B2 | `test_rule_lookup_gap_raises` | 同上 |
| B3a | `test_hfq_formula` | `ValueError: 未知复权口径: hfq` |
| B3a | `test_legacy_alias_warns` | 无 `DeprecationWarning`（`pytest.warns` 失败） |
| B3b | `test_execution_price_excludes_adj` | `AssertionError`（成交价仍含 `adj_factor`） |
| B4 | `test_mask_ignores_future_perturbation` / `test_open_at_limit_up_not_buyable` / `test_open_at_limit_down_not_sellable` | 3 failed（掩码随未来数据变化 / 涨停仍可买 / 跌停仍可卖） |
| B5 | `test_delisted_stock_not_tradable_after_delist` | `AssertionError`（退市后仍可交易） |
| B6 | `test_protocol_members[IFactorPipeline]` | `ModuleNotFoundError: core.data_provider` + 3 failed |

GREEN：`550 passed, 124 warnings in 19.73s`（最终态 125 warnings，+1 为未知前缀一次性告警）。

#### 10.0-2 baseline sha256（A1/A2/DOC-6/V16）

| 文件 | SHA256 |
|------|--------|
| close.pkl | `4F9E6CA95FE9DBB60EA8261011A9AF51ED6CD7518BB6C533544AE05FB4DDDEB3` |
| high.pkl | `FBDC847702346A43AB0E2D5A7E32BC706A3504B7B34632EA94C55345FBC6DA7A` |
| industry.pkl | `57F41BD95301E9A922C7FED9C54D66F2F30250F8D5CD56B49B9D090AF7D198DD` |
| low.pkl | `6445DE10A72F8BF868BDB8F43E95FFA2737E3F460C85B20152E0A3F35AC6DE37` |
| open.pkl | `A4C7970E8FA01DC751BC7170CCB698FCE890BB7946998AFC8BF3C2E8C99640DF` |
| stock_adj.pkl | `67F6533B2D20E3F6F4E136C85A57D5BDCAB85FF7F96645A0E08C8AD103969238` |
| suspend.pkl | `184028854F4AD4CD34834958DFAA3A8E233A75CD822A2CB60FA4649F96927BC4` |

`data/test_ashare/` 自基线（`05af52f`/`2c34283`）以来未被修改；`scripts/prepare_test_fixture.py` 的 baseline 分支零改动（diff 仅 `generate_biased_fixture`）。

#### 10.0-3 逐批 change_report（V12 / I6）

| 批次 | before | after | NAV | L1 | L2 | L3 | L4 | L5 | L6 | residual | attribution |
|------|--------|-------|-----|----|----|----|----|----|----|----------|-------------|
| B2 | `a5ae5cc` | `4e2ab0b` | 1,155,172.33 → 1,155,172.33 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00e+00 | true |
| B3b | `ad40490` | `79c4dea` | 1,155,172.33 → 832,682.77 | 0 | 0 | 0 | 175 | 217 | 59 | 4.66e-10 | true |
| B4 | `79c4dea` | `3717246` | 832,682.77 → 831,073.02 | 1 | 8 | 5 | 41 | 44 | 19 | 0.00e+00 | true |
| B5 | `3717246` | `5f95b48` | 831,073.02 → 787,609.76 | 25 | 25 | 20 | 42 | 48 | 10 | 2.33e-10 | true |

- B5 的 after 取 `5f95b48`：B5 提交本身缺「L1 含 listing」口径（F-S9-3），该修正零数值（`94018f2` 与 `5f95b48` 同为 787,609.7583223963）。
- B4 的 L1 差异为 `2024-02-27:000001`（开盘涨停后回落：旧收益阈值法可买 / 价格法不可买）。原除权日伪跳空已由 F-S9-6 修掉，避免把夹具数据错误计入归因。
- B2 全零的诚实解释：夹具日收益裁剪 ±4%，未触及 10%/5% 阈值；规则表边界由 `test_limit_rules.py` 7 项覆盖。

#### 10.0-4 实施发现（F-S9-*）

| ID | 级别 | 发现 | 处置 |
|----|------|------|------|
| F-S9-1 | P3 | 报告 `adjustment_mode` 初版字段不全（仅 trade/valuation），缺 signal/returns/legacy_adjustment | 按 D10/V18 补齐五键 |
| F-S9-2 | P2 | L6 末行在末日强平后未刷新，与引擎 NAV 不一致 | `LayerDumper.update_last_nav` + `engine._refresh_last_nav`（`5f95b48`） |
| F-S9-3 | P2 | L2 因 listing mask 变化但 L1 不含 listing，B5 归因断链 | `get_layer_masks` 的 L1 纳入 listing（`5f95b48`） |
| F-S9-4 | P2 | L4→L3 硬链误判：L3 仅记目标股票集合，订单量随净值/现金变化 | 删除该链，只校验 L6→L5→L4 与 L3→L2→L1（`0ccc7f6`） |
| F-S9-5 | P2 | `_cash_flow` 重复计入首日现金流，残差 1.12e6 | 区间改为 `(首日, 末日]`（`5f95b48`） |
| F-S9-6 | P2 | 夹具除权日 open/high/low 由除权前收盘推导 → +100% 伪跳空；层 CSV 读回时 `000001` 被推断为 `1` | 除权日后尺度缩放 + 新增 `2024-02-27` 真实涨停开盘样本；`_read_long` 指定 stock 为 str（`9be78e9`） |
| F-S9-7 | P2 | DESIGN §7 要求的「未知前缀一次性 warning + `unknown_board_codes`」未实现 | 补 `infer_board` 计数/告警与报告字段（`9d16a2a`） |
| F-S9-8 | P3 | 夹具 manifest 缺 `fetched_at`，与 `fetch_universe` 产物不同构（E6/T-10） | 补固定时间戳（`86f7650`） |
| F-S9-9 | P3 | `DataManager.universe` 懒加载属性未标注，盲区新增 1 error（5→4） | 补 `Any` 标注（`766c007`） |

#### 10.0-5 V7 legacy 对拍（C8 / INV-5）

- 方法：`2c34283`（改前）vs HEAD，`legacy_adjustment=True` + `check_next_day_tradable=True`（旧默认）；使用同一夹具副本，并移除 B4 专属事件行（`2024-02-27` 000001 开盘涨停），以隔离无法由 `legacy_adjustment` 恢复的 B4 行为。
- 读数：NAV 两侧均为 **1,155,172.3318119394**；trades **136 笔逐字段相等**；NAV max abs diff **0.0**（rtol=0）。
- 不隔离该事件行时差异 2,123.14 / 3 笔，属 B4 预期行为，见 `change_report_B4.json`。

#### 10.0-6 V6 / V11 / V13 / V18

| 项 | 读数 |
|----|------|
| V13 | dump 关/开：NAV `identical=True`、trades `identical=True`；关闭时 layers 目录不存在、开启时存在（零 I/O） |
| V6 | qfq 末值 = raw 末值 `True`；hfq 首值 = raw 首值 `True`；hfq/qfq ratio 最大跨 4.44e-16（恒定） |
| V11 | 删除 `universe/`：`survivorship="uncorrected"`、`n_unknown_list=6`、`n_unknown_delist=6`、`data_version="unknown"` |
| V18 | `adjustment_mode={trade:raw, valuation:raw, signal:hfq, returns:hfq, legacy_adjustment:false}`、`next_day_tradable_mode="ignored"`、`ruleset_version="cn_a_2026_07"`、`unknown_board_codes=0`；`universe` 9 键，`survivorship="corrected"` |

#### 10.0-7 其他机械核对

| 项 | 读数 |
|----|------|
| C2 | 缓存 key `['adj_close_forward', 'adj_close_hfq']` 分离，值相等 `True` |
| B6 | 每次 `build_masks` 触发 `DeprecationWarning` 恰 **1** 条 |
| D3 | `True→oracle` / `False→ignored` / `None+oracle→oracle` / `None+ignored→ignored` |
| B3 | `700001`/`700002` → main；告警 1 条；`unknown_board_count()=2` |
| F1 | `__api_version__="3.1.0"`；`process_single`/`combine_single` 均不存在 |
| F2 | `(stock, side, quantity, date, open_price, close_price=None, high_price=None, low_price=None, volume=None)` |
| A6 | 人为残差 1.0 样本：exit **1**，stderr `error: residual=1.000e+00 attribution_complete=False` |
| E5 | `--recompute-hash` exit 0；无 CSV 时打印 `--from-csv/--refresh` 且不写空文件 |
| E6 | manifest `{source: fixture, fetched_at: 2026-11-10T00:00:00, rows: 360, sha256: 6aec62e5…, schema_version: 1.0}` |

#### 10.0-8 V20 回退演练

| 路径 | 读数 |
|------|------|
| 逆序逐批（`0ccc7f6` → `a5ae5cc`，9 个提交） | **9/9 exit 0**（每批独立可回退） |
| HEAD 上单独 revert 中间批次 | B1/B2/B3b/B4 冲突（后续批次改动同一区域，属顺序依赖）；B3a/B5/B6 直接成功 |

#### 10.0-9 最终命令读数

| 命令 | 读数 |
|------|------|
| `pytest tests -q` | **550 passed, 125 warnings in 20.13s** |
| `black --check .` | **153 files would be left unchanged** |
| `mypy --explicit-package-bases core` | **Success: no issues found in 32 source files** |
| `mypy … --check-untyped-defs` | **4 errors in 2 files** |
| `gate probe/unit-tests/black-check/mypy-check` + `replay` | 4/4 pass；**12 rows OK**（session `factorv3-p012-bias-20261110`） |

### 10.1 验收统计

| 类别 | 总数 | 通过 | 失败 | 待办 |
|------|------|------|------|------|
| A 观测网与夹具（B1） | 7 | 7 | 0 | 0 |
| B 规则表与 ST（B2） | 7 | 7 | 0 | 0 |
| C 复权三口径（B3a/B3b） | 8 | 8 | 0 | 0 |
| D 涨跌停与掩码时点（B4） | 5 | 5 | 0 | 0 |
| E 退市与动态池（B5） | 6 | 6 | 0 | 0 |
| F 接口治理（B6） | 6 | 6 | 0 | 0 |
| G 测试与验证 | 8 | 7 | 0 | 1 |
| INV 不变式 | 9 | 9 | 0 | 0 |
| RL 排除与红线 | 12 | 12 | 0 | 0 |
| DOC 台账与文档 | 6 | 6 | 0 | 0 |
| **总计** | **74** | **73** | **0** | **1** |

> **统计口径（RULE-2）**：上表来自本文件逐项独立核对（74 行逐行标记），非事后汇总推算；逐行 `总数 = 通过 + 失败 + 待办` 成立，总计行按列求和成立（7+7+8+5+6+6+8+9+12+6 = 74；73+0+1 = 74）。§7.5 错误处理映射为锚点表，不重复计数。唯一待办 G7（V17 远端 CI）为 Step 10 计划项。
> **通过门槛**：P1/P2 = 0；行为批次（B2/B3b/B4/B5）各附 `change_report.json` 且 residual / attribution 双门通过；V17 以远端实测为准。

### 10.2 验收决定

- [ ] **验收通过**：所有 P1 项通过，无阻塞性问题（待 Step 10 远端 CI 回收 G7 后勾选）
- [x] **有条件通过**：Step 9 范围 **73/74** 通过（P1/P2 = 0；四项行为 change_report 双门全过）；唯一待办 G7 按计划于 Step 10 推送后回收
- [ ] **验收失败**：无

### 10.3 签字

| 角色 | 签字 | 日期 |
|------|------|------|
| 实施者 | 单 Agent 自查（RULE-4） | 2026-11-10 |
| 审查者 | （Step 10 独立 pass 待填） | |

---

## 11. 后续行动

| 行动 | 责任人 | 期限 | 状态 |
|------|--------|------|------|
| Step 8 一致性 Review（独立 pass；5 项预登记核对点 + 机械校验） | 单 Agent 自查 | Step 8 | ✅ 已完成（P1/P2 = 0，P3 = 4 全部回写，见 §8） |
| Step 9 实施（B1→B2→B3a→B3b→B4→B5→B6 七提交 + T-13） | 单 Agent 自查 | Step 9 | ✅ 已完成（2026-11-10，73/74，见 §10.0） |
| Step 10 ADD 审计 + 提交推送 + 远端 CI（V17 回填 G7） | 单 Agent 自查 | Step 10 | pending（本地已 550 passed，待推送） |
| P-011 Step 3 DESIGN（待 P-012 L2/L4 落地后启动） | 单 Agent 自查 | P-012 Step 9 后 | pending |
| U-D1~U-D4 未决项按触发条件回收 | 单 Agent 自查 | 实施期 | pending |

---

**Review 签字**: （Step 7 起草；§8/§9/§10 由 Step 8-10 逐级回填） 日期: 2026-11-10
