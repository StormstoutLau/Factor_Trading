"""
全局配置管理系统 v2 — 基于 Pydantic 验证 + 热重载

借鉴 OpenAlice 的 Config 设计:
- Schema 验证: 每个字段有类型约束、范围限制、默认值
- 热重载: 支持从文件/字典动态更新配置
- 配置迁移: 旧格式自动转换为新格式
- 向后兼容: 保留 dataclass 接口

依赖: pydantic >= 2.0
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# ==================== 基础配置模型 ====================


class CostConfig(BaseModel):
    """交易成本模型配置 (Pydantic 验证版)"""

    commission_rate: float = Field(default=0.0003, ge=0, le=0.1, description="佣金率")
    commission_min: float = Field(default=5.0, ge=0, description="最低佣金")
    stamp_tax_rate: float = Field(default=0.001, ge=0, le=0.1, description="印花税率")
    slippage_pct: float = Field(default=0.001, ge=0, le=0.1, description="滑点")

    @field_validator("commission_rate", "stamp_tax_rate", "slippage_pct")
    @classmethod
    def validate_rate(cls, v: float) -> float:
        if v > 0.05:
            logger.warning(f"交易费率 {v} 较高，请确认配置正确")
        return v


class UniverseConfig(BaseModel):
    """股票池过滤配置 (Pydantic 验证版)"""

    exclude_suspended: bool = True
    exclude_limit_up: bool = True
    exclude_limit_down: bool = True
    exclude_stock_prefixes: list[str] = Field(default_factory=list)
    excluded_prefixes: list[str] = Field(default_factory=list)
    exclude_st: bool = True
    exclude_na_factors: bool = True
    na_factor_names: list[str] = Field(default_factory=list)
    na_threshold: float = Field(default=0.3, ge=0, le=1)
    exclude_by_market_cap: bool = False
    min_market_cap: float = Field(default=1e9, ge=0)
    max_market_cap: float = Field(default=5e11, ge=0)
    exclude_industries: bool = False
    excluded_industries: list[str] = Field(default_factory=list)
    enable_custom_filters: bool = False
    custom_filter_configs: dict = Field(default_factory=dict)
    check_next_day_tradable: bool = True
    limit_up_threshold: float = Field(default=0.095, ge=0, le=0.5)
    limit_down_threshold: float = Field(default=-0.095, ge=-0.5, le=0)
    st_limit_up_threshold: float = Field(default=0.048, ge=0, le=0.5)
    st_limit_down_threshold: float = Field(default=-0.048, ge=-0.5, le=0)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.limit_up_threshold <= abs(self.limit_down_threshold):
            logger.warning("涨停阈值应大于跌停阈值绝对值")
        return self


class FactorConfig(BaseModel):
    """因子处理管道配置 (Pydantic 验证版)"""

    winsorize_method: Literal["mad", "percentile", "sigma", "none"] = "mad"
    winsorize_n: float = Field(default=5.0, ge=0)
    winsorize_pct: tuple[float, float] = (0.01, 0.99)
    reverse_factor: bool = False
    neutralize: bool = False
    neutralize_industry: bool = True
    neutralize_mktcap: bool = True
    standardize_method: Literal["zscore", "rank", "minmax", "none"] = "zscore"
    fill_method: Literal["median", "mean", "zero", "none"] = "median"
    factor_weights: dict[str, float] = Field(default_factory=dict)
    combine_method: Literal["weighted_sum", "rank_weighted"] = "weighted_sum"

    @field_validator("winsorize_pct")
    @classmethod
    def validate_pct(cls, v: tuple[float, float]) -> tuple[float, float]:
        low, high = v
        if not (0 <= low < high <= 1):
            raise ValueError(f"百分位范围无效: ({low}, {high})")
        return v

    @field_validator("factor_weights")
    @classmethod
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        if v:
            total = sum(v.values())
            if abs(total - 1.0) > 1e-6:
                logger.warning(f"因子权重总和={total}，建议归一化到1.0")
        return v


class OptimizerConfig(BaseModel):
    """组合优化器配置 (Pydantic 验证版)"""

    method: Literal[
        "equal_weight",
        "min_variance",
        "mean_variance",
        "risk_parity",
    ] = "equal_weight"
    max_weight: float = Field(default=0.10, gt=0, le=1)
    min_weight: float = Field(default=0.0, ge=0)
    industry_max_weight: Optional[float] = None
    round_lot: bool = True
    target_count: int = Field(default=50, ge=1)
    select_top: bool = True
    risk_aversion: float = Field(default=1.0, ge=0)
    risk_parity_tol: float = Field(default=1e-6, gt=0)
    risk_parity_max_iter: int = Field(default=500, ge=1)
    cov_method: Literal["ledoit_wolf", "sample", "shrunk"] = "ledoit_wolf"
    cov_lookback: int = Field(default=60, ge=5)
    cov_shrinkage: float = Field(default=0.1, ge=0, le=1)

    @model_validator(mode="after")
    def validate_weights(self):
        if self.min_weight >= self.max_weight:
            raise ValueError("min_weight 必须小于 max_weight")
        if self.industry_max_weight is not None and self.industry_max_weight > self.max_weight:
            raise ValueError("industry_max_weight 不应大于 max_weight")
        return self


class RebalanceConfig(BaseModel):
    """再平衡触发配置 (Pydantic 验证版)"""

    method: Literal["fixed", "conditional", "hybrid"] = "fixed"
    frequency: Literal["daily", "weekly", "monthly", "N_days"] = "monthly"
    n_days: int = Field(default=20, ge=1)
    signal_change_threshold: float = Field(default=0.3, ge=0, le=1)
    drawdown_trigger: Optional[float] = None
    volatility_trigger: Optional[float] = None
    hybrid_min_days: int = Field(default=5, ge=1)
    hybrid_max_days: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def validate_hybrid(self):
        if self.method == "hybrid" and self.hybrid_min_days >= self.hybrid_max_days:
            raise ValueError("hybrid_min_days 必须小于 hybrid_max_days")
        return self


# ==================== 主配置模型 ====================


class BacktestConfig(BaseModel):
    """回测系统总配置 (Pydantic 验证版)"""

    model_config = {"arbitrary_types_allowed": True, "validate_assignment": True}

    # 数据路径配置
    data_dir: Path = Field(default_factory=lambda: Path("./data"))
    output_dir: Path = Field(default_factory=lambda: Path("./output"))

    # 数据文件配置
    close_file: str = "close.pkl"
    open_file: str = "open.pkl"
    high_file: str = "high.pkl"
    low_file: str = "low.pkl"
    adj_factor_file: str = "stock_adj.pkl"
    adjustment_type: Literal["forward", "backward"] = "forward"
    suspend_file: str = "suspend.pkl"
    industry_file: str = "industry.pkl"
    st_file: str = "st.pkl"
    mktcap_file: Optional[str] = None

    # 因子文件配置
    factor_files: list[str] = Field(default_factory=list)
    factor_weights: dict[str, float] = Field(default_factory=dict)

    # 子系统配置
    cost: CostConfig = Field(default_factory=CostConfig)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    factor: FactorConfig = Field(default_factory=FactorConfig)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    rebalance: RebalanceConfig = Field(default_factory=RebalanceConfig)

    # 待执行订单管理配置
    enable_pending_orders: bool = True
    max_pending_days_buy: int = Field(default=5, ge=1)
    max_pending_days_sell: int = Field(default=10, ge=1)
    enable_fallback: bool = True
    max_fallback_depth: int = Field(default=10, ge=1)
    fallback_weight_factor: float = Field(default=1.2, ge=0)

    # 回测基本参数
    initial_capital: float = Field(default=10_000_000.0, gt=0)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    benchmark: Optional[str] = None

    # 性能优化配置
    enable_parallel: bool = True
    max_workers: int = Field(default=4, ge=1)
    enable_cache: bool = True
    cache_size_mb: int = Field(default=1000, ge=0)

    # 日志和调试配置
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    save_intermediate: bool = False
    debug_mode: bool = False

    # ========== 验证器 ==========

    @field_validator("data_dir", "output_dir", mode="before")
    @classmethod
    def parse_path(cls, v: Any) -> Path:
        if isinstance(v, str):
            return Path(v)
        # Handle WindowsPath/PosixPath serialized as dict (from JSON)
        if isinstance(v, dict) and v.get("__path__"):
            return Path(v["__path__"])
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            from datetime import datetime

            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式应为 YYYY-MM-DD: {v}")
        return v

    @field_validator("factor_files")
    @classmethod
    def validate_factor_files(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("至少需要指定一个因子文件")
        return v

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date 不能晚于 end_date")
        return self

    # ========== 便捷方法 ==========

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（Path 转为 str）"""
        d = self.model_dump()
        # Convert Path objects to strings for JSON serialization
        if isinstance(d.get("data_dir"), Path):
            d["data_dir"] = str(d["data_dir"])
        elif hasattr(d.get("data_dir"), "__fspath__"):
            d["data_dir"] = str(d["data_dir"])
        if isinstance(d.get("output_dir"), Path):
            d["output_dir"] = str(d["output_dir"])
        elif hasattr(d.get("output_dir"), "__fspath__"):
            d["output_dir"] = str(d["output_dir"])
        return d

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def save_to_file(self, path: str | Path) -> None:
        """保存到 JSON 文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        logger.info(f"配置已保存: {path}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BacktestConfig:
        """从字典创建配置"""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> BacktestConfig:
        """从 JSON 字符串创建配置"""
        import json
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: str | Path) -> BacktestConfig:
        """从 JSON 文件加载配置"""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = cls.model_validate(data)
        logger.info(f"配置已加载: {path}")
        return config

    def validate_legacy(self) -> list[str]:
        """兼容旧版 validate() 接口"""
        errors = []
        try:
            self.model_validate(self.model_dump())
        except Exception as e:
            errors.append(str(e))
        return errors


# ==================== 热重载管理器 ====================


class ConfigHotReloader:
    """
    配置热重载管理器

    借鉴 OpenAlice 设计:
    - 监视配置文件变化
    - 变化时自动重新加载
    - 支持回调通知
    """

    def __init__(
        self,
        config_path: str | Path,
        check_interval: float = 5.0,
        auto_reload: bool = True,
    ):
        self.config_path = Path(config_path)
        self.check_interval = check_interval
        self.auto_reload = auto_reload

        self._config: Optional[BacktestConfig] = None
        self._last_mtime: float = 0.0
        self._lock = threading.RLock()
        self._callbacks: list[Callable[[BacktestConfig], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Initial load
        self._load()

    @property
    def config(self) -> BacktestConfig:
        """获取当前配置"""
        with self._lock:
            if self._config is None:
                raise RuntimeError("配置未加载")
            return self._config

    def _load(self) -> bool:
        """加载配置，返回是否成功"""
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            return False

        try:
            new_config = BacktestConfig.from_file(self.config_path)
            with self._lock:
                self._config = new_config
                self._last_mtime = self.config_path.stat().st_mtime
            logger.info(f"配置已加载: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return False

    def check_and_reload(self) -> bool:
        """检查并重新加载配置"""
        if not self.config_path.exists():
            return False

        current_mtime = self.config_path.stat().st_mtime
        if current_mtime <= self._last_mtime:
            return False

        if self._load():
            self._notify_callbacks()
            return True
        return False

    def force_reload(self) -> bool:
        """强制重新加载"""
        return self._load()

    def on_change(self, callback: Callable[[BacktestConfig], None]) -> Callable[[], None]:
        """
        注册配置变化回调

        Returns:
            取消注册函数
        """
        self._callbacks.append(callback)

        def unsubscribe():
            if callback in self._callbacks:
                self._callbacks.remove(callback)

        return unsubscribe

    def _notify_callbacks(self) -> None:
        """通知所有回调"""
        if self._config is None:
            return
        for cb in self._callbacks:
            try:
                cb(self._config)
            except Exception as e:
                logger.warning(f"配置变化回调错误: {e}")

    def start_watching(self) -> None:
        """启动后台监视线程"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"配置热重载已启动: {self.config_path}")

    def stop_watching(self) -> None:
        """停止后台监视"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("配置热重载已停止")

    def _watch_loop(self) -> None:
        """后台监视循环"""
        while self._running:
            time.sleep(self.check_interval)
            if not self._running:
                break
            self.check_and_reload()

    def __enter__(self) -> ConfigHotReloader:
        self.start_watching()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop_watching()


# ==================== 便捷函数 ====================


def create_default_config() -> BacktestConfig:
    """创建默认配置"""
    return BacktestConfig()


def load_config(path: str | Path) -> BacktestConfig:
    """从文件加载配置"""
    return BacktestConfig.from_file(path)


def save_config(config: BacktestConfig, path: str | Path) -> None:
    """保存配置到文件"""
    config.save_to_file(path)
