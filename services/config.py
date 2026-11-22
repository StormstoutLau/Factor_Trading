"""服务层配置：env 前缀 ``P054_``，``extra="forbid"``（DESIGN §3.8）。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator, model_validator


class ServiceSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    redis_url: str = "redis://127.0.0.1:6379/0"
    sqlite_path: Path = Path("live_ledger.db")
    api_key: SecretStr
    operator_api_key: SecretStr | None = None
    admin_api_key: SecretStr | None = None
    cors_origins: tuple[str, ...] = ()
    metrics_require_auth: bool = True

    ws_ticket_ttl_seconds: int = 30
    ws_orders_queue_max: int = 1000
    ws_market_queue_max: int = 200
    ws_slow_consumer_seconds: float = 5.0
    ws_snapshot_orders_limit: int = 200

    heartbeat_interval_seconds: float = 1.0
    heartbeat_ttl_seconds: int = 10
    ready_staleness_seconds: float = 3.0

    outbox_batch_size: int = 100
    outbox_poll_interval_seconds: float = 0.2
    outbox_retention_days: int = 7
    outbox_publish_timeout_seconds: float = 2.0

    orders_stream_key: str = "p054:orders"
    orders_channel: str = "p054:orders:events"
    market_channel: str = "p054:market"
    admin_channel: str = "p054:admin"
    consumer_group: str = "p054-relay"
    consumer_name: str = "trading-1"
    autoclaim_idle_ms: int = 60_000

    market_source: Literal["synthetic", "none"] = "synthetic"
    market_tick_hz: float = 2.0
    market_symbols: tuple[str, ...] = ()

    tls_ciphers: str = "ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!RC4:!3DES"
    tls_certfile: Path | None = None
    tls_keyfile: Path | None = None
    tls_ca_certs: Path | None = None
    tls_require_client_cert: bool = False
    allow_plaintext_loopback: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8054

    @field_validator("api_key", "operator_api_key", "admin_api_key")
    @classmethod
    def _key_length(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 16:
            raise ValueError("api key must be at least 16 characters")
        return value

    @model_validator(mode="after")
    def _tls_consistency(self) -> "ServiceSettings":
        if (self.tls_certfile is None) != (self.tls_keyfile is None):
            raise ValueError("tls_certfile and tls_keyfile must be provided together")
        if self.allow_plaintext_loopback and self.api_host != "127.0.0.1":
            raise ValueError("plaintext is only allowed on 127.0.0.1")
        return self

    @classmethod
    def from_env(cls, prefix: str = "P054_") -> "ServiceSettings":
        data: dict[str, object] = {}
        for field in cls.model_fields:
            env_key = prefix + field.upper()
            if env_key not in os.environ:
                continue
            raw = os.environ[env_key]
            if field in ("cors_origins", "market_symbols"):
                data[field] = tuple(x.strip() for x in raw.split(",") if x.strip())
            else:
                data[field] = raw
        return cls(**data)  # type: ignore[arg-type]
