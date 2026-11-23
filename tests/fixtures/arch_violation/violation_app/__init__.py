"""负例包：``core`` 反向 import ``upper``（供 import-linter 契约失败断言）。"""

from violation_app.core import VALUE

__all__ = ["VALUE"]
