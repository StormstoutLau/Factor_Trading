"""uvicorn 入口与 TLS factory（D15/I14；top-level 可 pickle）。"""

from __future__ import annotations

import os
import ssl

DEFAULT_CIPHERS = "ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!RC4:!3DES"


def build_ssl_context(
    certfile: str | None = None,
    keyfile: str | None = None,
    *,
    ciphers: str = DEFAULT_CIPHERS,
    ca_certs: str | None = None,
    require_client_cert: bool = False,
) -> ssl.SSLContext:
    """显式 ``minimum_version=TLSv1_2`` + AEAD 优先 cipher（Q16/S68-S72）。"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
    context.set_ciphers(ciphers)
    if ca_certs:
        context.load_verify_locations(cafile=ca_certs)
    if require_client_cert:
        context.verify_mode = ssl.CERT_REQUIRED
    if certfile and keyfile:
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def tls_context_factory() -> ssl.SSLContext:
    """uvicorn 的 ``ssl_context_factory``（无参、top-level、可 pickle）。"""
    return build_ssl_context(
        os.environ.get("P054_TLS_CERTFILE"),
        os.environ.get("P054_TLS_KEYFILE"),
        ciphers=os.environ.get("P054_TLS_CIPHERS", DEFAULT_CIPHERS),
        ca_certs=os.environ.get("P054_TLS_CA_CERTS"),
        require_client_cert=os.environ.get("P054_TLS_REQUIRE_CLIENT_CERT") == "1",
    )


def main() -> None:  # pragma: no cover - 进程入口
    import uvicorn

    from services.api import create_app
    from services.config import ServiceSettings

    settings = ServiceSettings.from_env()
    app = create_app(settings=settings)
    kwargs: dict = {
        "factory": True,
        "host": settings.api_host,
        "port": settings.api_port,
        "workers": int(os.environ.get("P054_WORKERS", "1")),
    }
    if settings.tls_certfile is not None and settings.tls_keyfile is not None:
        kwargs["ssl_context_factory"] = tls_context_factory
    elif not settings.allow_plaintext_loopback:
        raise SystemExit("TLS required: set P054_TLS_CERTFILE/P054_TLS_KEYFILE")
    uvicorn.run(app, **kwargs)


if __name__ == "__main__":  # pragma: no cover
    main()
