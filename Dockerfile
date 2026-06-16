# =============================================================================
# GNONE — Multi-Stage Production Dockerfile
# =============================================================================

# ── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/gnone/.local/bin:$PATH"

# Create non-root user
RUN groupadd -g 1000 gnone && \
    useradd -u 1000 -g gnone -m -s /bin/bash gnone && \
    mkdir -p /app /data/chroma /tmp && \
    chown -R gnone:gnone /app /data/chroma /tmp

WORKDIR /app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get purge -y --auto-remove gcc g++ \
    && find /usr/lib -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# Copy wheels from builder and install
COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY --chown=gnone:gnone app/ ./app/
COPY --chown=gnone:gnone scripts/ ./scripts/
COPY --chown=gnone:gnone migrations/ ./migrations/
COPY --chown=gnone:gnone main.py .
COPY --chown=gnone:gnone pyproject.toml .

# Set proper ownership
RUN chown -R gnone:gnone /app

# Switch to non-root user
USER gnone

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/admin/health || exit 1

# Run with uvicorn and uvicorn workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
