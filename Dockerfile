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