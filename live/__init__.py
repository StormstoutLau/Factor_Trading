"""实盘适配层（P-052 最小实现）。

仅含 S1/S3 状态持久化与安全闸门；真实交易通道（QMT/券商 API/CTP）归 P-053。
依赖方向：``live → core``（总纲 L114/L286）；不 import ``filter``/``services``。
"""
