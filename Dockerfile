# ==============================================================================
# ovirt-mcp - Enterprise Model Context Protocol Server Container
# Multi-Stage Build: Minimal Attack Surface & Strict Non-Root Execution
# ==============================================================================

# ── Stage 1: Build & Compile C Extensions ─────────────────────────────────────
FROM python:3.12-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install C compiler and development headers needed for ovirt-engine-sdk-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libcurl4-openssl-dev \
    libxml2-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Build into an isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copy dependency specifications first to leverage Docker layer caching
COPY pyproject.toml requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and install ovirt-mcp
COPY src/ ./src/
COPY README.md ./

RUN pip install --no-cache-dir --no-deps .


# ── Stage 2: Final Runtime Image ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install ONLY the runtime shared libraries (no gcc, no dev headers!)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4 \
    libxml2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-compiled virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create an unprivileged non-root user (UID 1000) for secure container execution
RUN useradd -m -u 1000 -s /bin/bash appuser

USER appuser
WORKDIR /home/appuser

# MCP servers communicate via standard input/output (stdio JSON-RPC)
ENTRYPOINT ["ovirt-mcp"]
