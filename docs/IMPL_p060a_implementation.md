# IMPL：P-060a 单元层实施文档（core，T-A01..A23）

> **批次**: **P-060a**（三批中的第一批；P-060b/c 另行出文档）
> **上游**: [RESEARCH_p060](RESEARCH_p060_module_verification.md)（S1-S12 / I1-I10）· [DESIGN_p060](DESIGN_p060_module_verification.md)（DD1-DD10 / §4 / §7 / §8 / §17）· [REVIEW_p060_step4](REVIEW_p060_step4.md)（PASS-WITH-COMMENTS，F-11..F-17 已闭合）
> **作者**: DeepSeek-V4.1-Flash（Step 6 必须 reviewer ≠ 作者）
> **状态**: Step 5-7 完成（54 例落码 + G1-G10 PASS + CHECKLIST）
> **硬约束**: 零生产改动（DD9）· 零新依赖（S12）· 不新增第五套夹具（DD1）· 不重录 golden（I1）

---

## 1. 范围与交付

| 项 | 内容 |
|---|---|
| 交付 | 5 个测试文件、**54 例**（T-A01..A23 组；DESIGN 的 42 为组级估算，Step 5 按参数化拆分细化，覆盖目标不变） |
| 被测模块 | `core/execution.py`、`core/factor.py`、`core/rebalance.py`、`core/tracker.py`、`core/registry.py`、`core/diagnostics.py`、`core/event_log.py` |
| 不交付 | 任何生产改动、脚本、文档分类（属 P-060c） |
| 门禁 | G1-G10（DESIGN §8）；`-k p060` 子集 = 54 |

### 1.1 文件与用例分布

| 文件 | 组 | 例数 |
|---|---|---|
| `tests/test_p060a_execution_cost.py` | T-A01..A05 | 10 |
| `tests/test_p060a_factor_branches.py` | T-A06..A10 | 16 |
| `tests/test_p060a_rebalance_triggers.py` | T-A11..A15 | 17 |
| `tests/test_p060a_tracker_api.py` | T-A16..A19 | 7 |
| `tests/test_p060a_registry_diagnostics.py` | T-A20..A23 | 4 |

> 命名与 docstring 首行格式遵循 DESIGN DD2：`T-A01 | oracle=closed-form`。

---

## 2. 外部源码案例锚点（X1-X29）

> 全部于 2026-11-24 由独立取证代理实际打开核对；GitHub 均用 `raw.githubusercontent.com`。**用途仅为方案对照**，不引入任何依赖。

### 2.1 交易成本与执行（X1-X8）

| X | 项目 / 函数 | 可借鉴规则 | URL |
|---|---|---|---|
| X1 | vectorbt `Portfolio.from_orders` | 费用 = 成交额 × 费率；无最低佣金、无分侧税费 | https://raw.githubusercontent.com/polakowo/vectorbt/master/vectorbt/portfolio/base.py |
| X2 | backtrader `CommInfoBase._getcommission` | `COMM_PERC: abs(size)*commission*price`；`COMM_FIXED: abs(size)*commission` | https://raw.githubusercontent.com/mementum/backtrader/master/backtrader/comminfo.py |
| X3 | backtrader `BrokerBase.setcommission` | 逐标的注册 `CommInfoBase`，`percabs=True` 表示百分比 | https://raw.githubusercontent.com/mementum/backtrader/master/backtrader/broker.py |
| X4 | zipline-reloaded `PerShare/PerTrade/PerContract` | `min_trade_cost` 最低佣金；`PerContract` 含 exchange_fee | https://raw.githubusercontent.com/stefan-jansen/zipline-reloaded/main/src/zipline/finance/commission.py |
| X5 | zipline-reloaded `VolumeShareSlippage` | `price_impact * volume_share² * sign`，单 bar 成交量上限 2.5% | https://raw.githubusercontent.com/stefan-jansen/zipline-reloaded/main/src/zipline/finance/slippage.py |
| X6 | qlib `Exchange.__init__` | `open_cost=0.0015` / `close_cost=0.0025`（卖出更贵 → 印花税）、`min_cost=5.0`、`impact_cost` | https://raw.githubusercontent.com/microsoft/qlib/main/qlib/backtest/exchange.py |
| X7 | rqalpha `PriceRatioSlippage.get_trade_price` | `price*(1±rate)` 后**夹逼涨跌停** | https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/mod/rqalpha_mod_sys_simulation/slippage.py |
| X8 | electronic-trading `sqrt_law_cost_bps` | `1e4*Y*daily_vol*sqrt(Q/ADV)`；α=1/2 平方根律，α=1 线性 | https://raw.githubusercontent.com/AshJha0/electronic-trading/main/python/src/etrade/impact.py |

### 2.3 因子处理（X9-X18）

| X | 项目 / 函数 | 可借鉴规则 | URL |
|---|---|---|---|
| X9 | scipy `mstats.winsorize` | `limits` 为比例；超界值替换为分位值（**硬截断**，不删样本） | https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mstats.winsorize.html |
| X10 | JoinQuant `jqfactor_analyzer.winsorize` | 界 `μ±scale·σ`，`np.where` 硬截断；`qrange` 走 scipy | https://raw.githubusercontent.com/JoinQuant/jqfactor_analyzer/master/jqfactor_analyzer/preprocess.py |
| X11 | 同上 `winsorize_med` | 界 `med±scale·MAD`，**不乘 1.4826**，硬截断 | 同 X10 |
| X12 | 同上 `standardlize` | `(x−μ)/σ`，`np.nanmean/np.nanstd`（**ddof=0**） | 同 X10 |
| X13 | scipy `zscore` | 默认 ddof=0；ddof=1 才是样本标准差 | https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.zscore.html |
| X14 | 同 X10 `neutralize` | 因子 ~ 行业哑变量 + ln_mktcap 的 **OLS 残差**；`add_constant=False` | 同 X10 |
| X15 | pandas `GroupBy.transform` | 返回与原索引对齐、可广播的标量（行业均值填充模板） | https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.DataFrameGroupBy.transform.html |
| X16 | R `stats::mad` / NIST EDA 1.3.5.6 | `1.4826 = 1/Φ⁻¹(0.75)`，使 MAD 在正态下无偏于 σ | https://stat.ethz.ch/R-manual/R-devel/library/stats/html/mad.html · https://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm |
| X17 | pandas `DataFrame.rank` | `ascending=False` / `method='average'`；取负后 rank 与反向排序等价 | https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rank.html |
| X18 | Alphalens `utils.py` | 目标函数位于 350 行后，抓取被截断 → **unreachable，不作锚点** | https://raw.githubusercontent.com/quantopian/alphalens/master/alphalens/utils.py |

### 2.5 再平衡、组合暴露与插件（X19-X29）

| X | 项目 / 函数 | 可借鉴规则 | URL |
|---|---|---|---|
| X19 | zipline `utils/events.py` `NDaysBeforeLastTradingDayOfMonth` | n=0 即「月内最后交易日」；周规则同构 | https://raw.githubusercontent.com/stefan-jansen/zipline-reloaded/main/src/zipline/utils/events.py |
| X20 | zipline `api.py` `schedule_function` | `date_rules/time_rules/calendars` 入口 | https://raw.githubusercontent.com/stefan-jansen/zipline-reloaded/main/src/zipline/api.py |
| X21 | bt `RunPeriod/RunMonthly/RunWeekly` | `run_on_end_of_period=True` 时与下一根 bar 比较（前瞻式期末） | https://raw.githubusercontent.com/pmorissette/bt/master/bt/algos.py |
| X22 | bt `RunEveryNPeriods(n, offset)` | `idx=n-offset-1` 轮转；同一时点去重 | 同 X21 |
| X23 | bt `RunIfOutOfBounds(tolerance)` | 权重偏离目标 > tolerance 即触发（可 `Or` 组合） | 同 X21 |
| X24 | pyfolio `pos.get_sector_exposures` | `groupby(map, axis=1).sum()`；未映射标的告警剔除；权重按行和归一 | https://raw.githubusercontent.com/quantopian/pyfolio/master/pyfolio/pos.py |
| X25 | empyrical `max_drawdown` | 用**历史峰值** `np.fmax.accumulate`，`(cum−peak)/peak` 取最小 | https://raw.githubusercontent.com/quantopian/empyrical/master/empyrical/stats.py |
| X26 | empyrical `periods/annual_volatility` | `APPROX_BDAYS_PER_YEAR=252`；年化用 `nanstd(ddof=1)` | https://raw.githubusercontent.com/quantopian/empyrical/master/empyrical/periods.py |
| X27 | quantstats `comp` | 累计收益 `(1+r).prod()-1`（复利） | https://raw.githubusercontent.com/ranaroussi/quantstats/main/quantstats/stats.py |
| X28 | pluggy `PluginManager.register` | 同名已注册 → `ValueError("Plugin name already registered")` | https://raw.githubusercontent.com/pytest-dev/pluggy/main/src/pluggy/_manager.py |
| X29 | stevedore `ExtensionManager` | 同 group 同名默认 warning 后**后者覆盖**；`error_on_conflict` 可改为报错 | https://raw.githubusercontent.com/openstack/stevedore/master/stevedore/extension.py |

---

## 3. 与社区实现的语义分歧登记（锁定现状，不改实现）

| ID | 本仓语义 | 社区主流 | 处置 |
|---|---|---|---|
| **D-01** | 去极值用 `tanh` **软截断**（界内也被压缩） | scipy/jqfactor 均为**硬截断**（X9-X11） | 测试只断言「界 + 单调不减」；**登记 P3 提案**（若要对齐硬截断，单独立项，不在本批改） |
| **D-02** | MAD 界 `med ± n·MAD`，未乘 1.4826 | R/NIST 用 1.4826 作正态一致性（X16）；jqfactor 同样不乘（X11） | 按配置 `n` 直接推导；**不引入 1.4826** |
| **D-03** | 回撤触发 `(上期净值−当前净值)/上期净值` | empyrical 用**历史峰值**（X25）；社区回撤触发多用峰值 | 锁定现状；**登记 P3 语义提案**（Step 6 裁决） |
| **D-04** | 年化波动 `np.std(ddof=0)·√252` | empyrical `nanstd(ddof=1)`（X26） | 断言 ddof=0 现状；**登记 P3** |
| **D-05** | `PluginRegistry.register` 重名 **覆盖 + warning** | stevedore 覆盖（X29）；pluggy 报错（X28） | 锁定现状（与 X29 同构），不改为报错 |
| **D-06** | 周/月「最后交易日」用 `weekday` 递减 / 月份变化判断 | zipline 用交易日历定位最后交易日（X19） | **语义一致**；用手算日历（X19 口径）做 oracle |

> D-01/D-03/D-04 属「实现与主流不同但非必然错误」，按 DESIGN DD9 **零生产改动**；若 Step 6 判定应改，走 DD8 独立 commit + 回归用例。

---

## 4. 实施卡（逐用例）

### 4.1 `test_p060a_execution_cost.py`（10 例）

| T-ID | 构造 | 期望（闭式） | oracle |
|---|---|---|---|
| T-A01a | `amount=1000, rate=0.0003, min=5, slippage=0.001` | 佣金 5 + 滑点 1 = **6.0** | closed-form |
| T-A01b | `amount=1e6` 同费率 | 佣金 300 + 滑点 1000 = **1300.0**（下限不生效） | closed-form |
| T-A02a | 买入 `amount=10000`（费率 0.0003/滑点 0.001/印花税 0.001） | `5+10=15` | closed-form |
| T-A02b | 卖出同额 | `5+10+10=25`；买卖差 = 印花税 10 | cross-check |
| T-A02c | 期货 SELL（`stamp_tax_rate>0` 配置） | 印花税**不计**；`exchange_fee>0` 计入 | closed-form |
| T-A03a | `execute` 注入抛错的下游（fake tracker） | 返回 `(False, None)`；sink 收到 `("execution", exc)` | contract |
| T-A03b | `execute_pending_order` 四个未覆盖分支（L267-268/277-278/443，读码确认后逐分支） | 与主路径同口径；拒绝时返回明确状态 | contract |
| T-A04 | `_calculate_cost(0)` | **5.0**（仅公式一致性，`pending-semantics`，见 U-P060-8） | closed-form(pending) |
| T-A05a | `_validate_execution_price`：ref 0/-1/偏差 0.19/0.20/0.21 | False/False/True/**True**/False（严格 `>0.2`） | boundary |
| T-A05b | `simulate_market_impact`：adv 0、qty 1000/adv 10000、qty 1e6/adv 1e4 | 0 / 0.001 / **0.05（cap）** | closed-form |

> `_calculate_cost` 公式（[execution.py:391-423](../core/execution.py#L391-L423)）：佣金 `max(amount·rate, min)` → 交易所费 `amount·fee` → 印花税（SELL 且非 FUTURE 且 rate>0）`amount·rate` → 滑点 `amount·slippage`。锚点 X4（最低佣金）/X6（卖出更贵）。

**骨架（T-A02）**

```python
@pytest.mark.parametrize(
    ("side", "expected"),
    [(OrderSide.BUY, 15.0), (OrderSide.SELL, 25.0)],
)
def test_p060a_a02_stamp_tax_sell_only(side, expected):
    """T-A02 | oracle=closed-form：佣金下限 5 + 滑点 10 + 卖出印花税 10"""
    executor = make_executor(commission_rate=0.0003, commission_min=5.0,
                             stamp_tax_rate=0.001, slippage_pct=0.001)
    assert executor._calculate_cost(10_000.0, side) == pytest.approx(expected)
```

### 4.2 `test_p060a_factor_branches.py`（16 例，Step 5 参数化细化）

| T-ID | 构造 | 期望 | oracle |
|---|---|---|---|
| T-A06a | MAD：行 `[1,2,3,100]`、n=3 | median 2.5 / MAD 1.0 / 界 `[-0.5,5.5]`；输出全在界内 | cross-check |
| T-A06b | 同上 | 输出**单调不减**（软截断会压缩界内值，禁止断言原值保持） | invariant |
| T-A07 | 百分位：0..9、pct=(0.05,0.95) | 界 `[0.45,8.55]`；输出在界内 | cross-check |
| T-A08a | sigma：`std==0` 行 | 原行返回（逐值相等） | boundary |
| T-A08b | 正常行 | 界 `mean±n·std` | closed-form |
| T-A09a | `_fill_missing` median + DataFrame mask | 仅「可交易且 NaN」被填为当日可交易中位数 | closed-form |
| T-A09b | Series mask（列广播） | 与 DataFrame 同列 mask 结果一致 | cross-check |
| T-A09c | `mask=None` 三种 fill（median/mean/zero） | 全表按行统计填充；zero → 0 | closed-form |
| T-A09d | 不可交易 NaN | **保持 NaN**（不得被填） | invariant |
| T-A10a | 中性化：9 只股票（<10） | 原值返回（不做回归） | boundary |
| T-A10b | 中性化：12 只 + 行业 + mktcap | 残差均值≈0、与行业哑变量相关性≈0；`neutralize_skip_counts` 全 0 | invariant |
| T-A10c | 故障注入：monkeypatch `np.linalg.lstsq` 抛 `LinAlgError` | `regression` 桶 +1、sink 收到、该日原值保留 | contract |
| T-A10d | 故障注入：monkeypatch `np.std` 首次调用抛错 | `degenerate_columns` 桶 +1、sink 收到 | contract |
| T-A10e | `_reverse` | 输出 = `-input`；`spearmanr(in, out) = -1` | closed-form |
| T-A10f | `_standardize` zscore / rank / minmax | zscore 行均值≈0、`std(ddof=1)`≈1；rank **NaN 保持 NaN**；minmax ∈ [0,1] | invariant |
| T-A10g | `_standardize` 全零行 | zscore/minmax → 0（`std=0 → NaN → fillna(0)`） | boundary |

> 事实（[factor.py:304-470](../core/factor.py#L304-L470)）：`<10` 样本直接跳过；常数列**静默剔除**不计数；只有 `np.std`/`lstsq` 异常才进桶。故 T-A10c/d 用故障注入覆盖 I5/I6，正常退化列走 T-A10a/b。
> 分歧 D-01/D-02 在 T-A06 卡片显式注明，不改实现。

**骨架（T-A10c）**

```python
def test_p060a_a10c_lstsq_failure_keeps_values(monkeypatch):
    """T-A10c | oracle=contract：回归异常 → regression 桶 +1 且该日原值保留"""
    def boom(*args, **kwargs):
        raise np.linalg.LinAlgError("singular")

    monkeypatch.setattr(np.linalg, "lstsq", boom)
    pipe = make_pipeline(neutralize_industry=True, neutralize_mktcap=True)
    errors = []
    pipe.set_error_sink(lambda d, k, e: errors.append((d, k, type(e))))
    out = pipe._neutralize(make_factor_frame(n_stocks=12))
    assert pipe.neutralize_skip_counts["regression"] == 1
    assert errors and errors[0][1] == "factor"
    pd.testing.assert_frame_equal(out, make_factor_frame(n_stocks=12))
```

### 4.3 `test_p060a_rebalance_triggers.py`（17 例，含 T-A11f 独立日历对拍组）

| T-ID | 构造 | 期望 | oracle |
|---|---|---|---|
| T-A11a | 20 日连续索引（含周末跳空）、`daily` | 全部日期触发 | closed-form |
| T-A11b | 同上、`weekly` | 每周末最后交易日触发（X19 口径） | manual-calendar |
| T-A11c | 跨 3 个月、`monthly` | 每月最后交易日触发 | manual-calendar |
| T-A11d | `N_days=5` | 索引 0/5/10/15 触发 | closed-form |
| T-A11e | 空索引 / 单元素索引 | 空集 / 单日触发 | boundary |
| T-A12a | `signal_change_threshold=0.1`，signal `[1,0]→[0,1]` | L2=√2≥0.1 → 触发 | closed-form |
| T-A12b | 首次调用（无 last） | **不触发**，但状态被写入 | state |
| T-A12c | `drawdown_trigger=0.05`，上次 100 → 现 94 | 触发（`(100−94)/100=0.06`）；现 96 不触发 | closed-form |
| T-A12d | `volatility_trigger=0.2`，vol=0.25 | 触发 | closed-form |
| T-A12e | 三触发同时满足 | signal 优先（短路径返回） | priority |
| T-A13 | `_calculate_signal_change`：无交集/相同/正交 | 1.0 / 0.0 / √2 | closed-form |
| T-A14a | Hybrid：`min_days=5`，距上次 3 天 | 抑制（False） | state |
| T-A14b | Hybrid：fixed 命中 | 触发且记录 last 日期 | state |
| T-A14c | Hybrid：`last=None` + fixed 未命中 | 跳过间隔判断，走 conditional | state |
| T-A14d | Hybrid：`max_days=30` 且 31 天未触发 | 兜底触发 | state |
| T-A15 | `build_trigger` 未知 method；`RebalanceCalendar` 空/非空 | 回退 Fixed + warning；dates/stats/next 正确 | boundary |
| T-A11f | 周/月手算日历与实现集合**逐日对拍**（原 T-A16，避免与 tracker T-A16 重号） | 集合相等 | cross-check(X19) |

> D-03：`ConditionalTrigger` 回撤用**上期净值**（[rebalance.py:155-157](../core/rebalance.py#L155-L157)），与 X25 峰值口径不同，卡片注明「锁定现状」。

**骨架（T-A14c）**

```python
def test_p060a_a14c_hybrid_skips_interval_when_no_last():
    """T-A14c | oracle=state：last=None 时不判 min_days，直接走条件触发"""
    cfg = RebalanceConfig(method="hybrid", hybrid_min_days=5, drawdown_trigger=0.05)
    trig = HybridTrigger(cfg, TRADE_DATES)
    assert trig.should_trigger(TRADE_DATES[0], portfolio_value=100.0) is False
    hit = trig.should_trigger(TRADE_DATES[1], portfolio_value=90.0)
    assert hit is True
```

### 4.4 `test_p060a_tracker_api.py`（7 例，T-A18 含 proxy/无效回退价两额外分支）

| T-ID | 构造 | 期望 | oracle |
|---|---|---|---|
| T-A16a | 空仓 / `total<=0` | `pd.Series()` 空 | boundary |
| T-A16b | 多头 A/B + 期货 C | `market_value/total`；C 用 `notional_value/total`；和≤1 | closed-form |
| T-A16c | `allow_negative_stock=True` + 负股 | 负股权重计入（负值） | state |
| T-A17 | 行业映射缺一只、期货 0 持仓、同行业两只 | 缺映射 skip；0 持仓 skip；同行业权重相加 | closed-form(X24) |
| T-A18 | 期货结算：无 specs / 无期货 / 有持仓 / proxy 回退 / 无效回退价 | 前两者 `None`；有持仓返回 `SettlementResult`；proxy 回退价生效；无效回退价→0 | contract |
| T-A19a | `validate_positions` 五类错误 | 现金负 / 期货权益不符 / 负持仓 / 市值不符 / 平均成本异常 各自出现在列表 | contract |
| T-A19b | `get_performance_metrics` 空 / 3 日快照 / `reset` | `{}`；`annual_return=(1+r)^(252/n)−1`、`vol=np.std(ddof=0)√252`、`sharpe=ann/vol`、回撤用历史峰值；reset 后净值=初始 | closed-form(X25/X26) |

> D-04：`np.std` 默认 ddof=0（[tracker.py:589](../core/tracker.py#L589)），与 X26 的 ddof=1 不同；断言现状并在卡片注明。

### 4.5 `test_p060a_registry_diagnostics.py`（4 例，T-A23 诊断+事件日志合并，不含 change_report）

| T-ID | 构造 | 期望 | oracle |
|---|---|---|---|
| T-A20 | register 重名 / unregister 缺失 / get 未注册 / create 缺失 / 工厂抛错 | 覆盖 + warning；False；None；`KeyError` 且消息含可用名；异常透传 | contract(X29) |
| T-A21 | `create_or_default` 注册/未注册 | 注册走注册项；未注册走 default；config 透传 | contract |
| T-A22 | 六类装饰器重复注册 + inventory | 幂等；`get_inventory` 字段（name/category? 读码确认） | contract |
| T-A23 | `diagnostics` 分类分支（ValueError/KeyError/其他）+ `event_log` 轮转/上限/订阅/重置（`change_report` 属 P-060c，见 F-S7-P060a-5） | 按 [diagnostics.py](../core/diagnostics.py) 未覆盖区间 71/141-144/152-165/180/194/197/204-206/226/228/239 与 [event_log.py](../core/event_log.py) 210/217/226/230-232/264-267/270-272/274/293-303/370-371/378-379/392/431-434/458-460/473-478 逐分支 | branch |

---

## 5. 实施顺序与门禁

| 步 | 内容 | 完成判定 |
|---|---|---|
| S5-1 | `execution_cost`（10 例） | 新文件全绿；`-k p060a` = 10 |
| S5-2 | `factor_branches`（16 例） | 全绿；`neutralize_skip_counts` 两桶各 ≥1 |
| S5-3 | `rebalance_triggers`（17 例） | 全绿；四频率日历手算对拍通过 |
| S5-4 | `tracker_api`（7 例） | 全绿；期货结算返回字段断言通过 |
| S5-5 | `registry_diagnostics`（4 例） | 全绿 |
| S5-6 | 门禁 G1-G10 | 全绿；covA core ≥88%；`black` **330（本批 325+5，337 为 P-060 全量）**；`mypy` **160（本批，161 为 P-060c 加脚本后）** |

每步结束跑：`pytest -q -k p060a` → `pytest -q -k golden`（22）→ `pytest -q -k p059`（63）。**不跑覆盖率**（P-060a 只记行覆盖快照，分支留 P-060c，F-17）。

> **执行状态（2026-11-24）**
> - **S5-1 完成**：`tests/test_p060a_execution_cost.py` **10/10 绿**（0.60s）；golden **22** / p059 **63** 通过。
> - 目标分支全部命中：L267-268（自定义价无效回退）、L277-278（未知类型回退）、L371-376（异常旁路）、L443（待执行单委托）、L511-522（价格校验）、L538-548（市场冲击）。单文件运行时 `core/execution.py` 44 行未覆盖（主为 TradeLog/CLOSE/VWAP/清算路径，属既有其他测试域）。
> - **S5-2 完成**：`tests/test_p060a_factor_branches.py` **16/16 绿**（1.36s）；golden **22** / p059 **63** 通过。
> - 覆盖命中：`_neutralize` **304-397 全段**（含 `regression` / `degenerate_columns` 两桶故障注入）、`_reverse`、`_standardize` 三方法（zscore/rank/minmax）；`_fill_missing` 的 DataFrame/Series/None 三路与 `zero` 保 NaN。
> - 观测（支持 D-01）：`tanh` 对 100 饱和到上界 5.5（非 4.x），故 T-A06b 断言「4.5 < out ≤ 5.5」而非严格小于。
> - **S5-3 完成**：`tests/test_p060a_rebalance_triggers.py` **17/17 绿**（0.99s）；golden **22** / p059 **63** 通过。
> - **`core/rebalance.py` 单文件即 100%（153/153）**，超 DESIGN 目标（≥80%）；覆盖 `BaseTrigger` 抽象 raise、`build_trigger` 四 method、空日历 stats、四频率日历、三条件触发、Hybrid min/max 兜底。
> - **S5-4 完成**：`tests/test_p060a_tracker_api.py` **7/7 绿**（1.11s）；golden **22** / p059 **63** 通过。
> - 覆盖命中：权重（期货 notional、负股开关）、行业暴露（缺映射/零持仓/负股跳过）、`settle` 四分支（无 specs / 无期货 / proxy 回退 / 无效回退价）、`validate_positions` 五类错误、绩效指标（ddof=0 口径）、`reset`、`update_market_values` 四条跳过分支。单文件运行 64%（余为交易执行路径，属既有其他测试域）。
> - **S5-5 完成**：`tests/test_p060a_registry_diagnostics.py` **4/4 绿**（0.44s）；`-k p060a` 聚合 **54 passed**（与计划一致）；golden **22** / p059 **63** 通过。
> - 覆盖命中：注册表 CRUD/重名覆盖/未注册 `KeyError`/工厂异常透传、`create_or_default` 双分支、六类装饰器 + inventory、诊断分类/去重/降级/`ExceptionGroup` raise/off、事件日志双写/ring buffer/类型过滤/订阅与退订/close/reset。**实测事实**：`raise_if_needed` 抛 `ExceptionGroup`（非 `RuntimeError`），断言已按实际类型。
> - **S5-6 完成（全门禁 G1-G10，2026-11-24）**

| 门禁 | 命令 | 实测读数 | 判定 |
|---|---|---|---|
| G1 全量 | `pytest tests/ -q`（本轮附带 `--cov=core --cov=live --cov=services --cov=strategies`，G1 与 covA 合并） | **1556 passed, 1 skipped**（collect **1557**）；带覆盖 **321.10s** / 无覆盖 **138.03s** | PASS（≥1503） |
| G2 golden | `pytest -q -k golden` | **22 passed**（1535 deselected，24.40s） | PASS（零重录） |
| G3 P-059 | `pytest -q -k p059` | **63 passed**（1494 deselected，75.11s） | PASS（场景零改动） |
| G4 P-060 聚合 | `pytest -q -k p060` | **54 passed**（1503 deselected，3.40s） | PASS（= 计划 54） |
| G5 类型 | CI 同款 mypy（不含 tests） | **Success: no issues found in 160 source files** | PASS（161 为 P-060c 加脚本后目标） |
| G6 格式 | `black --check .` | **330 files would be left unchanged** | PASS（325+5；337 为 P-060 全量目标） |
| G7 覆盖率 | covA JSON（脚本未落，手工等价判定） | 四包 **10714/12165 = 88.07%**；core 8165/9117 = **89.56%** | PASS（O1 阈值 10705；每包 ≥ 基线−0.5pp） |
| G8 不变式 | `pytest tests/test_invariants.py` | **11 passed**（4.02s） | PASS |
| G9 契约 | `pytest tests/test_contract_conformance.py` | **6 passed**（1.56s） | PASS |
| G10 场景入口 | `python scripts/verify_scenario.py --list` | **18 条 / 7 层** | PASS |
| 范围守卫 | `git diff --stat -- core live services strategies filter agents` | 空 | PASS（DD9 零生产改动） |

> - **covA 逐包**：core **89.56%**（miss 952）· live **87.95%**（miss 204，与基线相同）· services **74.54%**（miss 278，与基线相同）· strategies **93.54%**（miss 17，与基线相同）。相对基线（core 86.46% / 四包 85.80%）净增 **+282 行**；DESIGN §7 计划 +315 → 88.34%，实际低 33 行，但**超 O1 阈值 9 行**（10714 vs 10705）。
> - **单文件**：`rebalance` **100%**（153/153，目标 ≥80% 达成）· `tracker` 99% · `execution` 99% · `registry` 99% · `event_log` 86% · `diagnostics` 79% · **`factor` 76.7%（211/275，目标 ≥80% 未达，差 9 行）**。factor 缺口主体为 `FactorCombiner.combine`（L514-566，53 行，不在 T-A06..A10 卡片范围），其余为零散分支（62-63/83-84/115-116/142/162/192/209/259/263/272-291/301-302/323-324/356/373/414-427/453-454）。按 **F-15 / U-P060-9 登记残余缺口 G-P060-13**，不放宽标准，也不临时加例（避免破坏 G4「收集数 = 计划数」）。
> - **G7 执行口径**：`scripts/coverage_snapshot.py` 属 P-060c 尚未落码；本批以 covA JSON 手工等价判定，四包均 ≥ 基线−0.5pp。
> - **I10 口径**：321.10s 为**带覆盖率诊断轮**（G1 与 covA 合并跑）；无覆盖率全量 **138.03s**。I10「单轮 ≤300s」应按无覆盖率轮计量，带覆盖率轮的超预算属工具开销，定义口径留 Step 6 复核。
> - **残余（属 P-060b/c，不计入本批判定）**：`services/market_gateway` **0%**（O2 目标 ≥75%）、services 74.54%（目标 ≥85%）、live 87.95%（目标 ≥90%）。

---

## 6. 风险与回退

| 风险 | 缓解 |
|---|---|
| 软截断（D-01）被误写为「原值保持」 | T-A06b 只断言界 + 单调；docstring 引 X9-X11 说明差异 |
| 故障注入（T-A10c/d）污染全局 numpy | `monkeypatch` 自动回滚；只在该用例内替换；不并发 |
| 期货结算测试依赖 `ContractSpec` 真实字段 | 先读 [futures_accounting.py](../core/futures_accounting.py#L39) 的 `ContractSpec` 定义再构造；缺失字段用 UNKNOWN 标注，不猜 |
| 手算日历跨月/周末出错 | T-A11f 用 X19 口径二次对拍：独立写 `expected_last_trading_days()` 纯函数 |
| T-A23 面太宽导致断言弱 | 只覆盖未覆盖行区间对应分支，每分支 1 断言；不做全类快照 |

**回退**：5 个文件整体删除即回退；零生产 diff、零依赖 diff。

---

## 7. 验收清单（对应 DESIGN §13）

- [ ] 54 例全绿，全部带 `T-Axx | oracle=` 首行
- [ ] G1 全量绿（collect ≥1557）
- [ ] G2 golden 22 / G3 p059 63 零变化
- [ ] G5 mypy **160 files / 0 error**（本批，161 为 P-060c）
- [ ] G6 black **330**（本批 325+5，337 为 P-060 全量）
- [ ] covA core ≥88.0%（单文件 `factor` ≥80%、`rebalance` ≥80%）
- [ ] `git diff core/ live/ services/ strategies/ filter/ agents/` 为空
- [ ] D-01/D-02/D-03/D-04 分歧已在 docstring 注明，未改生产代码

---

## 8. 待 Step 6 复审输入

1. T-A04 `pending-semantics` 是否应升级 P3 缺陷（U-P060-8）。
2. T-A10c/d 故障注入是否越界（是否算「测试侧替身」而非 seam）。
3. D-01/D-03/D-04 三项语义分歧是否应在本批改（建议：不改，登记）。
4. 54 例是否覆盖 DESIGN §4 全部 T-ID，有无遗漏或重复。
5. 外部锚点 X1-X29 是否被正确引用（仅对照，不引入依赖）。
6. **S5-1 实测发现（P3 候选，U-P060-10）**：`execution_price_type` 为非枚举值时，`_get_execution_price` 正确回退开盘价（L277-278），但 `execute_order` 成功日志读取 `.value` 抛 `AttributeError` → 订单最终 `(False, None)`。属类型契约外的误配置路径；本批只在解析层断言回退、**不锁定**该缺陷，待 Step 6 裁决是否登记 P3。
