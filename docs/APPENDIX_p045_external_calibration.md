# 附录：P-045 外部对拍校准（vectorbt 1.2.0）

> **批次**: P-045（timing + stops）· **执行载体**: `scripts/external_benchmark/verify_p045.py`
> **环境**: 隔离 venv `.venv-vbt`（`vectorbt==1.2.0` / `pandas==3.1.1`）· **输入**: `tests/golden/p045/P045_S1.json`
> **口径**: 触发判定序列逐值（DESIGN I3，F-S2-P045-1 收窄；F-S6-P045-1 落点）；成交/NAV 差异闭式声明（P-015 恒等式方法论）

## 1. 读数

| 侧 | (date, code, reason/price) |
|----|----------------------------|
| 本仓 `apply_stops` | `2024-01-03` / `C` / `stop_loss` |
| 本仓 `apply_stops` | `2024-01-04` / `A` / `stop_loss` |
| 本仓 `apply_stops` | `2024-01-05` / `B` / `trailing_stop` |
| vbt `from_signals` | `2024-01-04` / `A` / exit_price `90.0`（无 reason 列） |
| vbt `from_signals` | `2024-01-05` / `B` / exit_price `47.7`（无 reason 列） |
| vbt `from_signals` | `2024-01-03` / `C` / exit_price `90.0`（无 reason 列） |

## 2. 断言与豁免

| ID | 项 | 状态 | 读数 |
|----|----|------|------|
| C1 | 本仓触发序列 == 规格锁定期望（输入自校验） | ✅ PASS | repo=[('2024-01-03', 'C', 'stop_loss'), ('2024-01-04', 'A', 'stop_loss'), ('2024-01-05', 'B', 'trailing_stop')] |
| C2.A | vbt 恰一笔平仓（A） | ✅ PASS | exit_date=2024-01-04 exit_price=90.0000 rows=ok |
| C2.B | vbt 恰一笔平仓（B） | ✅ PASS | exit_date=2024-01-05 exit_price=47.7000 rows=ok |
| C2.C | vbt 恰一笔平仓（C） | ✅ PASS | exit_date=2024-01-03 exit_price=90.0000 rows=ok |
| C3 | 触发判定序列（date, code）逐值一致（按 date, code 规范化排序） | ✅ PASS | repo=[('2024-01-03', 'C'), ('2024-01-04', 'A'), ('2024-01-05', 'B')] vbt=[('2024-01-03', 'C'), ('2024-01-04', 'A'), ('2024-01-05', 'B')] |
| C4 | C 的 vbt 退出价 = SL 触发价 90（非 TP 120）→ SL 优先于 TP 与 vbt 一致 | ✅ PASS | C exit_price=90.0 |
| C5 | A 的 vbt 退出价 = SL 触发价 90 | ✅ PASS | A exit_price=90.0 |
| W1 | reason 字段对拍 | — 豁免（非断言） | vbt 免费版 trades/orders 无止损类型列（实测） |
| W2 | 成交价 / NAV 对拍 | — 豁免（非断言） | vbt 触发价成交 vs 本仓 T+1 开盘（I3 收窄，F-S2-P045-1） |
| W3 | trailing 幅度 0.08 vs 0.10 | — 豁免（非断言） | vbt sl_trail 复用 sl_stop；本 case 触发日同（B 01-05） |
| W4 | trailing 激活阈值 0.05 | — 豁免（非断言） | 免费版无 tsl_th（F-D3-P045-4）；本 case 无触发日差异 |

**汇总**: 7 项断言（失败 0）+ 4 项豁免登记；退出码 **0**。

## 3. 差异闭式声明（waiver 展开）

| # | 差异 | 闭式说明 |
|---|------|----------|
| 1 | `reason` 不可比 | vbt 1.2.0 免费版 `trades` / `orders` 记录均无止损类型字段（实测列：`id/col/size/entry_idx/...`）；本仓 reason 由 V5/V6 单测与 G1/G2 golden 锁定 |
| 2 | 成交价模型 | vbt 在触发 bar 以**触发价**成交（C 实测 90.0，而非当日 close 100.0）；本仓 `exit_price_ref` 记触发日 close 仅作审计，真实成交由既有链 T+1 开盘完成（无前视，I5） |
| 3 | trailing 幅度 | vbt `sl_trail=True` 将 `sl_stop=0.10` 复用为跟踪幅度（B 实测退出价 47.7 = 53×0.9）；本仓 `trailing_stop_pct=0.08`（阈值 48.76）。本 case 两侧触发日相同（01-05） |
| 4 | 激活阈值 | 免费版无 `tsl_th`（PRO 专有），`trailing_activate_pct=0.05` 不参与对拍（F-D3-P045-4）；本 case 未产生触发日差异 |
| 5 | 重建行为 | vbt 单次 entry 信号 → 止损后不再重建；本仓 `targets>0` 次日重建（S1 期望 weights 反映）。本对拍只取**首次触发**（各标的 1 次），重建语义由 G1/G2 锁定 |

## 4. 命令

```powershell
.\.venv-vbt\Scripts\python.exe scripts\external_benchmark\verify_p045.py
```
