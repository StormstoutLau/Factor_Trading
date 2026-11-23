# Factor Trading v3.2 — Docker Image
# Multi-stage build for a compact, production-ready image
#
# Usage:
#   docker build -t factor-trading .
#   docker compose run --rm factor-trading
#
# Options:
#   --build-arg PYTHON_VERSION=3.12   (default: 3.11)

ARG PYTHON_VERSION=3.11

# ──────────────────────────── Builder Stage ────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./

# Install dependencies into a venv (no root pip pollution)
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "setuptools>=61.0" && \
    pip install --no-cache-dir -e ".[dev]"

# ──────────────────────────── Runtime Stage ────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm

# Runtime-only deps (no build tools)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

# Inherit venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . .

# Pre-create writable directories
RUN mkdir -p /app/data /app/demo_data && chmod 777 /app/data /app/demo_data

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default: run tests (override for other entrypoints)
CMD ["python", "-m", "pytest", "tests/", "-q", "--tb=short"]

# ──────────────────────────── Services Stage (P-055) ────────────────────────────
# 部署化模块化单体：4 类进程共用本镜像，非 root（uid 10001）。
FROM python:${PYTHON_VERSION}-slim-bookworm AS services

RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "fastapi>=0.115.0" "uvicorn>=0.30.0" \
        "prometheus-client>=0.20.0" "redis>=4.5.0" "pydantic>=2.9.0"
COPY . .
# D-7：打包发现失败时回退为纯源码复制（镜像变大，功能不受影响）
RUN pip install --no-cache-dir --no-deps -e . || true

RUN mkdir -p /app/run /app/data && chown -R appuser:appgroup /app/run /app/data

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
USER appuser

CMD ["python", "-m", "services.trading_worker"]