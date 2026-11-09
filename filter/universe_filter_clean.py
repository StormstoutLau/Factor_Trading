#!/usr/bin/env python3
"""
股票池过滤器 - 清理版本
整合了所有过滤功能，采用向量化操作，代码结构清晰
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Literal
from dataclasses import dataclass, field
import logging
import warnings

from filter.limit_rules import build_limit_prices, special_no_limit_mask

logger = logging.getLogger(__name__)

# 涨跌停价比较容差（半分钱；P-012 D4）
EPS_PRICE = 0.005


@dataclass
class UniverseFilterConfig:
    """股票池过滤配置"""

    # 基础过滤
    exclude_suspended: bool = True
    exclude_limit_up: bool = True
    exclude_limit_down: bool = True
    exclude_st: bool = True
    # 旧字段：True→oracle / False→ignored；None 时读 next_day_tradable_mode（P-012 D4）
    check_next_day_tradable: bool | None = None
    next_day_tradable_mode: Literal["ignored", "oracle"] = "ignored"
    limit_check_price: Literal["open", "close"] = "open"

    # 涨跌停阈值
    limit_up_threshold: float = 0.095
    limit_down_threshold: float = -0.095
    st_limit_up_threshold: float = 0.048
    st_limit_down_threshold: float = -0.048

    # 扩展过滤
    exclude_na_factors: bool = False
    na_factor_names: List[str] = field(default_factory=lambda: ["factor_value"])
    na_threshold: float = 0.3

    exclude_stock_prefixes: bool = False
    excluded_prefixes: List[str] = field(default_factory=lambda: ["300", "688"])

    exclude_by_market_cap: bool = False
    min_market_cap: float = 1e9
    max_market_cap: float = 5e11

    exclude_industries: bool = False
    excluded_industries: List[str] = field(default_factory=list)

    enable_custom_filters: bool = False
    custom_filter_configs: Dict[str, Any] = field(default_factory=dict)


class UniverseFilter:
    """股票池过滤器 - 清理版本"""

    def __init__(self, data_manager, config: UniverseFilterConfig):
        """初始化过滤器

        Args:
            data_manager: 数据管理器
            config: 过滤配置
        """
        self.dm = data_manager
        self.cfg = config

        # 预计算信息
        self._prefix_info = {}
        self._next_day_mode = self._resolve_next_day_mode(emit_warning=False)

        # 过滤掩码
        self._suspend_mask: Optional[pd.DataFrame] = None
        self._limit_up_mask: Optional[pd.DataFrame] = None
        self._limit_down_mask: Optional[pd.DataFrame] = None
        self._st_mask: Optional[pd.DataFrame] = None
        self._next_day_tradable_mask: Optional[pd.DataFrame] = None
        self._na_factor_mask: Optional[pd.DataFrame] = None
        self._stock_prefix_mask: Optional[pd.DataFrame] = None
        self._market_cap_mask: Optional[pd.DataFrame] = None
        self._industry_mask: Optional[pd.DataFrame] = None
        self._custom_masks: Dict[str, pd.DataFrame] = {}

        # 最终掩码
        self._buyable_mask: Optional[pd.DataFrame] = None
        self._sellable_mask: Optional[pd.DataFrame] = None
        self._tradable_mask: Optional[pd.DataFrame] = None

        logger.info("股票池过滤器初始化完成")

    def build_masks(self):
        """构建所有过滤掩码"""
        logger.info("开始构建股票池过滤掩码...")
        self._warn_deprecated_thresholds()
        self._next_day_mode = self._resolve_next_day_mode(emit_warning=True)

        # 预计算基础信息
        self._precompute_basic_info()

        # 构建基础掩码
        self._build_suspend_mask()
        self._build_limit_masks()
        self._build_st_mask()

        # 构建扩展掩码
        if self._next_day_mode == "oracle":
            self._build_next_day_tradable_mask()

        if self.cfg.exclude_na_factors:
            self._build_na_factor_mask()

        if self.cfg.exclude_stock_prefixes:
            self._build_stock_prefix_mask()

        if self.cfg.exclude_by_market_cap:
            self._build_market_cap_mask()

        if self.cfg.exclude_industries:
            self._build_industry_mask()

        if self.cfg.enable_custom_filters:
            self._build_custom_masks()

        # 构建最终掩码
        self._build_final_masks()

        logger.info("股票池过滤掩码构建完成")

    def _precompute_basic_info(self):
        """预计算基础信息"""
        if self.cfg.exclude_stock_prefixes:
            self._prefix_info = {}
            for stock_code in self.dm.stock_codes:
                self._prefix_info[stock_code] = any(
                    stock_code.startswith(prefix) for prefix in self.cfg.excluded_prefixes
                )

    def _build_suspend_mask(self):
        """构建停牌掩码"""
        if self.dm.suspend is not None:
            self._suspend_mask = self.dm.suspend == 0
        else:
            self._suspend_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )
            logger.warning("未找到停牌数据，假设所有股票都可交易")

    def _build_limit_masks(self):
        """构建涨跌停掩码（价格法；P-012 D4 / T-7）。

        判定：``open >= limit_up - EPS`` → 当日不可买；``open <= limit_down + EPS``
        → 当日不可卖。``limit = ref_price * (1 ± ratio)``，``ref_price`` 为除权参考价，
        首行无 prev_close 与 NaN 一律按「不限制」处理。
        """
        dates = self.dm.trade_dates
        codes = self.dm.stock_codes

        try:
            close = self.dm.close
            adj = self.dm.adj_factor
            check = (
                self.dm.open if getattr(self.cfg, "limit_check_price", "open") == "open" else close
            )
        except (FileNotFoundError, ValueError, KeyError) as exc:
            logger.warning(f"缺少 close/adj_factor/open 数据，跳过涨跌停过滤: {exc}")
            self._limit_up_mask = pd.DataFrame(True, index=dates, columns=codes, dtype=bool)
            self._limit_down_mask = pd.DataFrame(True, index=dates, columns=codes, dtype=bool)
            return

        limit_up, limit_down = build_limit_prices(close, adj, self.dm.st, dates)
        limit_up = limit_up.reindex(index=dates, columns=codes)
        limit_down = limit_down.reindex(index=dates, columns=codes)
        check = check.reindex(index=dates, columns=codes)

        self._limit_up_mask = ~(check >= limit_up - EPS_PRICE)
        self._limit_down_mask = ~(check <= limit_down + EPS_PRICE)

        # IPO 前 5 个交易日不适用涨跌停限制（T-3 要点 6；快照缺失时不生效）
        snap = getattr(self.dm, "universe", None)
        if snap is not None:
            no_limit = special_no_limit_mask(dates, codes, snap)
            self._limit_up_mask |= no_limit
            self._limit_down_mask |= no_limit

    def _resolve_next_day_mode(self, emit_warning: bool) -> str:
        """解析 next-day 可交易性模式；旧 bool 字段优先并弃用告警（T-7）。"""
        legacy = self.cfg.check_next_day_tradable
        if legacy is not None:
            if emit_warning:
                warnings.warn(
                    "UniverseFilterConfig.check_next_day_tradable 已弃用；"
                    "请改用 next_day_tradable_mode='oracle'|'ignored'（P-012 D4）",
                    DeprecationWarning,
                    stacklevel=3,
                )
            return "oracle" if legacy else "ignored"
        return getattr(self.cfg, "next_day_tradable_mode", "ignored")

    @property
    def next_day_tradable_mode(self) -> str:
        """当前生效的 next-day 模式（报告字段）。"""
        return self._next_day_mode

    def _warn_deprecated_thresholds(self) -> None:
        """4 个旧阈值字段已弃用（每次 build_masks 一次，不逐行）。"""
        warnings.warn(
            "UniverseFilterConfig 的 limit_up_threshold/limit_down_threshold/"
            "st_limit_up_threshold/st_limit_down_threshold 已弃用；"
            "涨跌停阈值改由 filter.limit_rules 规则表解析（P-012 D3）",
            DeprecationWarning,
            stacklevel=3,
        )

    def _build_st_mask(self):
        """构建ST股票掩码"""
        if self.dm.st is not None:
            if self.cfg.exclude_st:
                self._st_mask = self.dm.st == 0
            else:
                self._st_mask = pd.DataFrame(
                    True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
                )
        else:
            self._st_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )

    def _build_next_day_tradable_mask(self):
        """构建下一交易日可交易性掩码"""
        if self.dm.suspend is not None:
            suspend_shifted = self.dm.suspend.shift(-1)
            self._next_day_tradable_mask = suspend_shifted == 0

            # 最后一天设为False
            if len(self._next_day_tradable_mask) > 0:
                self._next_day_tradable_mask.iloc[-1] = False
        else:
            self._next_day_tradable_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )

    def _build_na_factor_mask(self):
        """构建因子NA过滤掩码"""
        na_mask = pd.DataFrame(
            True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
        )

        for factor_name in self.cfg.na_factor_names:
            if hasattr(self.dm, factor_name):
                factor_data = getattr(self.dm, factor_name)

                # 向量化计算NA比例
                na_ratios = factor_data.isna().mean(axis=1)
                high_na_dates = na_ratios > self.cfg.na_threshold

                # 设置掩码
                na_mask.loc[high_na_dates] = False

                logger.debug(f"因子 {factor_name} NA过滤: {high_na_dates.sum()} 个日期被过滤")

        self._na_factor_mask = na_mask

    def _build_stock_prefix_mask(self):
        """构建股票代码前缀过滤掩码"""
        if hasattr(self, "_prefix_info"):
            # 使用预计算信息
            prefix_data = [not self._prefix_info.get(stock, False) for stock in self.dm.stock_codes]
            prefix_array = np.tile(prefix_data, (len(self.dm.trade_dates), 1))
            self._stock_prefix_mask = pd.DataFrame(
                prefix_array, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )
        else:
            # 备选方案
            self._stock_prefix_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )

            for prefix in self.cfg.excluded_prefixes:
                excluded_stocks = [
                    stock for stock in self.dm.stock_codes if stock.startswith(prefix)
                ]
                if excluded_stocks:
                    self._stock_prefix_mask[excluded_stocks] = False

    def _build_market_cap_mask(self):
        """构建市值过滤掩码"""
        if self.dm.mktcap is not None:
            self._market_cap_mask = (self.dm.mktcap >= self.cfg.min_market_cap) & (
                self.dm.mktcap <= self.cfg.max_market_cap
            )
        else:
            logger.warning("未找到市值数据，跳过市值过滤")
            self._market_cap_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )

    def _build_industry_mask(self):
        """构建行业过滤掩码"""
        if self.dm.industry is not None:
            industry_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )

            for industry in self.cfg.excluded_industries:
                industry_mask &= self.dm.industry != industry

            self._industry_mask = industry_mask
        else:
            logger.warning("未找到行业数据，跳过行业过滤")
            self._industry_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )

    def _build_custom_masks(self):
        """构建自定义过滤掩码"""
        for filter_name, filter_config in self.cfg.custom_filter_configs.items():
            try:
                mask = self._apply_custom_filter(filter_name, filter_config)
                self._custom_masks[filter_name] = mask
                logger.info(f"自定义过滤 {filter_name} 构建完成")
            except Exception as e:
                logger.error(f"构建自定义过滤 {filter_name} 失败: {e}")

    def _apply_custom_filter(self, filter_name: str, filter_config: Dict[str, Any]) -> pd.DataFrame:
        """应用自定义过滤条件"""
        filter_type = filter_config.get("type", "simple")

        if filter_type == "simple":
            data_source = filter_config["data_source"]
            condition = filter_config["condition"]

            if hasattr(self.dm, data_source):
                data = getattr(self.dm, data_source)
                return eval(f"data {condition}")

        elif filter_type == "function":
            func = filter_config["function"]
            return func(self.dm)

        # 默认返回全True
        return pd.DataFrame(
            True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
        )

    def _build_final_masks(self):
        """构建最终的可交易掩码"""
        # 收集买入掩码
        buyable_masks = []

        if self.cfg.exclude_suspended and self._suspend_mask is not None:
            buyable_masks.append(self._suspend_mask)

        if self.cfg.exclude_limit_up and self._limit_up_mask is not None:
            buyable_masks.append(self._limit_up_mask)

        if self.cfg.exclude_st and self._st_mask is not None:
            buyable_masks.append(self._st_mask)

        if self.cfg.exclude_na_factors and self._na_factor_mask is not None:
            buyable_masks.append(self._na_factor_mask)

        if self.cfg.exclude_stock_prefixes and self._stock_prefix_mask is not None:
            buyable_masks.append(self._stock_prefix_mask)

        if self.cfg.exclude_by_market_cap and self._market_cap_mask is not None:
            buyable_masks.append(self._market_cap_mask)

        if self.cfg.exclude_industries and self._industry_mask is not None:
            buyable_masks.append(self._industry_mask)

        # 添加自定义掩码
        for mask in self._custom_masks.values():
            buyable_masks.append(mask)

        # 构建买入掩码
        if buyable_masks:
            self._buyable_mask = buyable_masks[0].copy()
            for mask in buyable_masks[1:]:
                self._buyable_mask &= mask
        else:
            self._buyable_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )

        # 构建卖出掩码
        sellable_masks = []

        if self.cfg.exclude_suspended and self._suspend_mask is not None:
            sellable_masks.append(self._suspend_mask)

        if self.cfg.exclude_limit_down and self._limit_down_mask is not None:
            sellable_masks.append(self._limit_down_mask)

        if self.cfg.exclude_st and self._st_mask is not None:
            sellable_masks.append(self._st_mask)

        if self.cfg.exclude_na_factors and self._na_factor_mask is not None:
            sellable_masks.append(self._na_factor_mask)

        if self.cfg.exclude_stock_prefixes and self._stock_prefix_mask is not None:
            sellable_masks.append(self._stock_prefix_mask)

        if self.cfg.exclude_by_market_cap and self._market_cap_mask is not None:
            sellable_masks.append(self._market_cap_mask)

        if self.cfg.exclude_industries and self._industry_mask is not None:
            sellable_masks.append(self._industry_mask)

        # 添加自定义掩码
        for mask in self._custom_masks.values():
            sellable_masks.append(mask)

        # 构建卖出掩码
        if sellable_masks:
            self._sellable_mask = sellable_masks[0].copy()
            for mask in sellable_masks[1:]:
                self._sellable_mask &= mask
        else:
            self._sellable_mask = pd.DataFrame(
                True, index=self.dm.trade_dates, columns=self.dm.stock_codes, dtype=bool
            )

        # 构建可交易掩码
        self._tradable_mask = self._buyable_mask & self._sellable_mask

        # 下一交易日可交易性检查（仅 oracle 模式；默认 ignored 不构建该掩码）
        if self._next_day_mode == "oracle" and self._next_day_tradable_mask is not None:
            self._buyable_mask &= self._next_day_tradable_mask
            self._tradable_mask = self._buyable_mask & self._sellable_mask

    def filter_stocks(
        self, date: str, stocks: List[str], filter_type: str = "tradable"
    ) -> List[str]:
        """过滤股票列表

        Args:
            date: 日期
            stocks: 股票列表
            filter_type: 过滤类型 ('buyable', 'sellable', 'tradable')

        Returns:
            过滤后的股票列表
        """
        if self._tradable_mask is None:
            self.build_masks()

        mask_map = {
            "buyable": self._buyable_mask,
            "sellable": self._sellable_mask,
            "tradable": self._tradable_mask,
        }

        mask = mask_map.get(filter_type, self._tradable_mask)

        if date not in mask.index:
            logger.warning(f"日期 {date} 不在掩码索引中")
            return stocks

        date_mask = mask.loc[date]
        filtered_stocks = [
            stock for stock in stocks if stock in date_mask.index and date_mask[stock]
        ]

        return filtered_stocks

    def get_universe_stats(self, date: str) -> Dict[str, Any]:
        """获取股票池统计信息

        Args:
            date: 日期

        Returns:
            统计信息字典
        """
        if self._tradable_mask is None:
            self.build_masks()

        if date not in self._tradable_mask.index:
            return {}

        stats = {
            "total_stocks": len(self.dm.stock_codes),
            "buyable": self._buyable_mask.loc[date].sum(),
            "sellable": self._sellable_mask.loc[date].sum(),
            "tradable": self._tradable_mask.loc[date].sum(),
        }

        stats["buyable_ratio"] = stats["buyable"] / stats["total_stocks"]
        stats["sellable_ratio"] = stats["sellable"] / stats["total_stocks"]
        stats["tradable_ratio"] = stats["tradable"] / stats["total_stocks"]

        return stats

    def get_mask_summary(self) -> Dict[str, Any]:
        """获取掩码汇总信息"""
        if self._tradable_mask is None:
            self.build_masks()

        summary = {
            "buyable_coverage": self._buyable_mask.mean().mean(),
            "sellable_coverage": self._sellable_mask.mean().mean(),
            "tradable_coverage": self._tradable_mask.mean().mean(),
            "memory_usage_mb": {
                "buyable": self._buyable_mask.memory_usage(deep=True).sum() / 1024 / 1024,
                "sellable": self._sellable_mask.memory_usage(deep=True).sum() / 1024 / 1024,
                "tradable": self._tradable_mask.memory_usage(deep=True).sum() / 1024 / 1024,
            },
        }

        return summary

    def get_layer_masks(
        self, date: pd.Timestamp
    ) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """返回当日 L1（停牌+涨跌停）与 L2（最终可交易）四个掩码 Series。

        L1: can_buy = suspend & limit_up；can_sell = suspend & limit_down。
        L2: 最终 buyable / sellable。未构建的掩码按全 True 处理。
        """
        if self._buyable_mask is None or self._sellable_mask is None:
            self.build_masks()

        all_true = pd.Series(True, index=self.dm.stock_codes)

        def _row(mask: Optional[pd.DataFrame]) -> pd.Series:
            if mask is None or date not in mask.index:
                return all_true.copy()
            return mask.loc[date].astype(bool)

        suspend = _row(self._suspend_mask)
        limit_up = _row(self._limit_up_mask)
        limit_down = _row(self._limit_down_mask)
        return (
            suspend & limit_up,
            suspend & limit_down,
            _row(self._buyable_mask),
            _row(self._sellable_mask),
        )

    @property
    def buyable(self) -> pd.DataFrame:
        """可开仓掩码（可买入）"""
        if self._buyable_mask is None:
            self.build_masks()
        return self._buyable_mask

    @property
    def sellable(self) -> pd.DataFrame:
        """可平仓掩码（可卖出）"""
        if self._sellable_mask is None:
            self.build_masks()
        return self._sellable_mask

    @property
    def tradable(self) -> pd.DataFrame:
        """可交易掩码（可买入和卖出）"""
        if self._tradable_mask is None:
            self.build_masks()
        return self._tradable_mask


# 便捷函数
def create_universe_filter(data_manager, **kwargs) -> UniverseFilter:
    """创建股票池过滤器的便捷函数

    Args:
        data_manager: 数据管理器
        **kwargs: 配置参数

    Returns:
        股票池过滤器实例
    """
    config = UniverseFilterConfig(**kwargs)
    return UniverseFilter(data_manager, config)


# 预定义配置
def get_conservative_config() -> UniverseFilterConfig:
    """获取保守配置（严格过滤）"""
    return UniverseFilterConfig(
        exclude_suspended=True,
        exclude_limit_up=True,
        exclude_limit_down=True,
        exclude_st=True,
        check_next_day_tradable=True,
        exclude_na_factors=True,
        na_threshold=0.2,
        exclude_stock_prefixes=True,
        excluded_prefixes=["300", "688"],
        exclude_by_market_cap=True,
        min_market_cap=5e9,
        max_market_cap=1e11,
        exclude_industries=True,
        excluded_industries=["房地产", "钢铁", "煤炭"],
    )


def get_aggressive_config() -> UniverseFilterConfig:
    """获取激进配置（宽松过滤）"""
    return UniverseFilterConfig(
        exclude_suspended=True,
        exclude_limit_up=False,
        exclude_limit_down=False,
        exclude_st=False,
        check_next_day_tradable=False,
        exclude_na_factors=False,
        exclude_stock_prefixes=False,
        exclude_by_market_cap=False,
        exclude_industries=False,
    )


def get_balanced_config() -> UniverseFilterConfig:
    """获取平衡配置（适中过滤）"""
    return UniverseFilterConfig(
        exclude_suspended=True,
        exclude_limit_up=True,
        exclude_limit_down=True,
        exclude_st=True,
        check_next_day_tradable=True,
        exclude_na_factors=True,
        na_threshold=0.3,
        exclude_stock_prefixes=False,
        exclude_by_market_cap=True,
        min_market_cap=1e9,
        max_market_cap=5e11,
        exclude_industries=False,
    )
