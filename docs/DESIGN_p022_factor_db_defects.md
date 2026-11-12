# DESIGN：P-022 Factor_DB 四项实现缺陷修复

> **批次**: P-022 · **T1**
> **上游**: [RESEARCH_p022_factor_db_defects.md](RESEARCH_p022_factor_db_defects.md)（Step 2 Review 通过；M-A 判定；缺陷③升级 P1）
> **下游**: IMPL_p022_factor_db_defects → CHECKLIST_p022_factor_db_defects
> **代码证据时点**: HEAD `cc3214c`（2026-11-12）
> **状态**: Step 3-4 完稿（§7 Step 4 Review 通过）

---

## 1. 目标与边界

**目标**：按 P4-P7 四条实证缺陷逐项修复，每项一组红绿测试，公开签名不变。

| 批次 | 内容 | 对应缺陷 |
|------|------|----------|
| **B1** | 重开加载时解析 `created_at`/`updated_at` ISO 字符串 | ③（P6，P1 崩溃） |
| **B2** | `add_factor` 覆盖守卫覆盖已持久化因子 | ①（P4，P2 静默覆盖） |
| **B3** | `delete_factor` 删除 parquet 与 csv 两种格式 | ②（P5，P2 删除复活） |
| **B4** | 写入成功后清理另一种格式（双向） | ④（P7，P3 双份存储） |

**不覆盖（明确出界）**：
- `_save_metadata` 原子写 / 并发（U-P022-1）；
- `get_factor` 返回副本（U-P022-2）；
- 非 `ImportError` 写入失败清理（U-P022-3）；
- DuckDB 迁移 / SQL 查询层 / 多源表（U-P005-1）；
- `FactorMetadata` 字段增删或类型变更（保持 `datetime` 注解）。

**能力边界**：本批只保证「单进程、通过 API 的增删改查」在重开后行为正确；不保证并发安全、不保证磁盘写中断后的 JSON 完整性。

---

## 2. 设计决策（D1-D6）

| # | 决策 | 被拒方案 | 拒绝理由 | 代价 |
|---|------|----------|----------|------|
| **D1** | **加载时显式解析 ISO 字符串**：对 `created_at`/`updated_at` 为 `str` 的字段调用 `datetime.fromisoformat`，已是 `datetime` 的原样保留 | ① 把字段注解改为 `str`；② 依赖 dataclass 自动转换 | ① 语义倒退，`updated_at` 失去时间运算能力；② E2 明确运行时**不执行**类型注解，dataclass 不会转换 | 加载期一次解析（O(1)/条） |
| **D2** | **覆盖守卫 = `_metadata` ∪ `_factors` ∪ 两种数据文件存在性** | 只查 `_metadata`；只查文件 | 只查 metadata 漏掉「metadata 丢失但文件在」的孤儿；只查文件漏掉「metadata 在但文件被手工删除」 | 守卫多两次 `exists()` |
| **D3** | **`delete_factor` 删除 parquet 与 csv 两种格式** | 只删 parquet；按 metadata 记录的格式删 | 只删 parquet 是 P5 复活根因；metadata 不记录格式，按记录删不可行 | 多一次 `exists()` |
| **D4** | **写入成功后清理另一种格式**（parquet 成功→删 csv；CSV 回退→删 parquet） | 保留双份、读取时按 mtime 选择 | 按 mtime 引入时间语义与平台差异；陈旧文件仍占空间，且外部工具可能读错格式 | 多一次 `exists()` |
| **D5** | **公开签名与参数不变**，不新增 `strict`/`cleanup` 开关 | 新增可选参数控制行为 | 本批目标是把默认行为修正为「安全」，加开关等于延续不安全默认；过度设计 | 无 |
| **D6** | **不做原子写与返回副本** | 顺手加 `tmp + os.replace` / `return data.copy()` | 与四项缺陷不同源；会扩大行为面与性能影响；登记 U-P022-1/2 | 无 |

---

## 3. 不变量（I1-I6）

| ID | 不变量 | 判据 |
|----|--------|------|
| **I1** | 重开后写入不崩溃 | 重开 `FactorDatabase` 后 `add_factor` / `update_stats` / 双因子 `delete_factor` 均正常返回 |
| **I2** | 覆盖守卫覆盖持久化因子 | 重开后同名 `add_factor`（`overwrite=False`）抛 `ValueError`；`overwrite=True` 成功 |
| **I3** | 删除彻底 | `delete_factor` 后 parquet 与 csv 均不存在；`get_factor` 抛 `KeyError`（不复活） |
| **I4** | 单一格式 | 写入成功后仅存一种格式；`get_factor` 返回值与最后写入一致 |
| **I5** | 接口与消费方不变 | 7 个方法签名不变；`batch_backtest/engine.py` 零改动；`query`/`get_lineage`/`update_stats` 语义不变 |
| **I6** | 回归门禁 | 全量 **636 + 新增测试** 全绿；black / mypy 不劣化 |

---

## 4. 实现规格

### 4.1 B1：加载期 datetime 解析（缺陷③）

```python
def _load_existing_factors(self):
    meta_path = self.db_path / "metadata.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for name, meta_dict in data.items():
            self._metadata[name] = self._build_metadata(name, meta_dict)

def _build_metadata(self, name: str, meta_dict: dict) -> FactorMetadata:
    payload = dict(meta_dict)
    for key in ("created_at", "updated_at"):
        value = payload.get(key)
        if isinstance(value, str):
            try:
                payload[key] = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(
                    f"metadata.json 中 {name}.{key} 不是 ISO 8601 时间: {value!r}"
                ) from exc
    return FactorMetadata(**payload)
```

> 解析失败时给出带因子名/字段名的 `ValueError`，不静默保留 `str`（否则后续写入仍会崩溃且更难定位）。

### 4.2 B2：覆盖守卫（缺陷①）

```python
data_path = self.db_path / f"{name}.parquet"
csv_path = self.db_path / f"{name}.csv"

exists = (
    name in self._metadata
    or name in self._factors
    or data_path.exists()
    or csv_path.exists()
)
if exists and not overwrite:
    raise ValueError(f"因子 {name} 已存在，设置 overwrite=True 覆盖")
```

> 路径计算前置到守卫之前；`overwrite=True` 时继续执行写入与清理（B4）。

### 4.3 B3：删除两种格式（缺陷②）

```python
for data_path in (self.db_path / f"{name}.parquet", self.db_path / f"{name}.csv"):
    if data_path.exists():
        data_path.unlink()
```

> 保持「删除不存在的因子不抛错」的现有语义（不新增 `KeyError`）。

### 4.4 B4：写入后清理另一种格式（缺陷④）

```python
try:
    data.to_parquet(data_path)
except ImportError:
    data.to_csv(csv_path)
    if data_path.exists():
        data_path.unlink()
else:
    if csv_path.exists():
        csv_path.unlink()
```

> 只在写入成功后清理；写入抛非 `ImportError` 异常时不做任何清理（U-P022-3 出界）。

---

## 5. 验证项（V1-V6）

| # | 验证项 | 判据 |
|---|--------|------|
| V1 | 写后重开 | 重开后 `add_factor` / `update_stats` / 双因子 `delete_factor` 均成功；`type(created_at) is datetime` |
| V2 | 覆盖守卫 | 重开后同名写入 `ValueError`；`overwrite=True` 后读回新值 |
| V3 | 删除彻底 | csv-only 因子删除后文件不存在，`get_factor` `KeyError` |
| V4 | 单一格式 | parquet 成功后无 csv；CSV 回退后无 parquet；读回值等于最后写入 |
| V5 | 兼容 | 7 个公开方法签名不变；`batch_backtest/engine.py` diff 空 |
| V6 | 回归 | 全量测试全绿（636 + 新增）；black / mypy 不劣化 |

---

## 6. 风险与回退

| 风险 | 预案 |
|------|------|
| 外部旧 `metadata.json` 含非 ISO 时间串 → `ValueError` | 仓内零数据（P3）；错误信息带因子名/字段名；如需容忍另立迁移批 |
| 孤儿文件（无 metadata）现在会阻止写入 | 属安全行为；`overwrite=True` 可显式覆盖；在测试中固定该语义 |
| 清理旧格式误删用户手工放置的同名文件 | 该文件本就会被 `get_factor` 优先读取，清理是正确性要求；文档注明 |
| 反向清理（CSV 回退删 parquet）在引擎临时故障时丢旧数据 | `ImportError` 仅在引擎缺失时发生；写入前已确认可写 csv；风险低于读到陈旧 parquet |
| 四项改动互相耦合 | B1 为硬前置；B2-B4 各自独立提交，可单独 `git revert` |

**回退点**：B1 / B2 / B3 / B4 四个提交，文件面均为 `factor_library/database.py`（可逐笔 revert）；测试文件随批次新增。

---

## 7. Step 4 Review（设计幻觉抑制）

**[RULE-4] 自查（单视角）**声明。

- [x] 设计基于已验证事实：四个缺陷均有 E2 探针读数（RESEARCH §5 B-E），非推测
- [x] 无未经验证假设：`datetime.fromisoformat` 对 `isoformat()` 输出的可解析性由 E1 支撑；E2 支撑「注解不转换」
- [x] 依赖真实存在：不新增依赖；`datetime` 为标准库；`pyarrow` 已在本机（P-005 P6）
- [x] 接口/签名可实现：7 个公开方法签名不变；新增 `_build_metadata` 为私有辅助
- [x] 边界清晰：原子写/返回副本/非 ImportError 清理均有 U 项归属
- [x] 回退点：B1-B4 四提交，单文件面
- [x] 低效操作排除：不做存储层重写、不加开关、不改 `FactorMetadata` 字段类型

**Step 4 Review 结论：通过**（0 P1/P2；1 项设计期强化：B2 守卫从「只查 metadata」扩展为「metadata ∪ 内存 ∪ 两种文件」，防止孤儿文件被静默覆盖）。可进入 Step 5 IMPL。
