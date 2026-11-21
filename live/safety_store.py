"""安全状态落盘：临时文件 + ``os.replace`` 原子写；读失败返回 ``None``。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class SafetyStateStore:
    """kill/熔断/台账状态的最小持久化（单写者，风险表第 4 行）。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def save(self, data: dict[str, Any]) -> None:
        """原子写：同目录临时文件 → fsync → ``os.replace``。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".safety-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def load(self) -> dict[str, Any] | None:
        """不存在/损坏/非 dict → ``None``（不抛，交由调用方回落默认）。"""
        if not self.path.exists():
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None
