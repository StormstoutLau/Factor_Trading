"""准备真实A股测试数据子集"""
import pickle
import pandas as pd
import numpy as np
from pathlib import Path

data_dir = Path(r'E:\Ashare_data\market_data')
test_dir = Path('data/test_ashare')
test_dir.mkdir(parents=True, exist_ok=True)

# 1. 加载核心数据
close = pd.read_pickle(data_dir / 'stock_close.pkl')
open_ = pd.read_pickle(data_dir / 'stock_open.pkl')
high = pd.read_pickle(data_dir / 'stock_high.pkl')
low = pd.read_pickle(data_dir / 'stock_low.pkl')

print(f"close: {close.shape}")
print(f"open:  {open_.shape}")

# 2. 筛选 2024 年 (取前 100 个交易日做精简测试)
mask_2024 = [str(x).startswith('2024') for x in close.index]
close_2024 = close.loc[mask_2024].iloc[:100]
open_2024 = open_.loc[mask_2024].iloc[:100]
high_2024 = high.loc[mask_2024].iloc[:100]
low_2024 = low.loc[mask_2024].iloc[:100]

print(f"2024 前100天: {close_2024.shape}")

# 3. 筛选 50 只数据完整的股票
valid_counts = close_2024.notna().sum()
good_stocks = valid_counts[valid_counts >= 95].index[:50]  # 95%以上有数据
print(f"筛选 {len(good_stocks)} 只股票")

close_sub = close_2024[good_stocks]
open_sub = open_2024[good_stocks]
high_sub = high_2024[good_stocks]
low_sub = low_2024[good_stocks]

# 4. 构造辅助数据
adj_sub = pd.DataFrame(np.ones(close_sub.shape), index=close_sub.index, columns=good_stocks)
susp_sub = pd.DataFrame(0, index=close_sub.index, columns=good_stocks)
ind_sub = pd.DataFrame(1, index=close_sub.index, columns=good_stocks)  # 行业 1

# 5. 保存
close_sub.to_pickle(test_dir / 'close.pkl')
open_sub.to_pickle(test_dir / 'open.pkl')
high_sub.to_pickle(test_dir / 'high.pkl')
low_sub.to_pickle(test_dir / 'low.pkl')
adj_sub.to_pickle(test_dir / 'stock_adj.pkl')
susp_sub.to_pickle(test_dir / 'suspend.pkl')
ind_sub.to_pickle(test_dir / 'industry.pkl')

print(f"\n已保存到 {test_dir}:")
for f in sorted(test_dir.glob('*.pkl')):
    df = pd.read_pickle(f)
    print(f"  {f.name}: {df.shape}")
print(f"\n日期范围: {close_sub.index[0]} ~ {close_sub.index[-1]}")
print(f"股票样例: {list(good_stocks[:5])}")