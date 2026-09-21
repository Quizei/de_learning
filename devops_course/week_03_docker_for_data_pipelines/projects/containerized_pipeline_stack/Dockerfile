# ──────────────────────────────────────────────────────────────
# Dockerfile — Containerized Pipeline Stack
# ──────────────────────────────────────────────────────────────
# This Dockerfile demonstrates production-quality best practices:
#   - Pinned Python version (reproducible builds)
#   - Layer cache optimization (requirements before code)
#   - --no-cache-dir (smaller image)
#   - Non-root user (security)
#   - PYTHONUNBUFFERED (see logs immediately in docker-compose logs)
#   - No secrets in the image (all passed via --env-file at runtime)
# ──────────────────────────────────────────────────────────────

# Pin to a specific version for reproducibility.
# 3.11-slim = Debian Bookworm base, Python 3.11, no build tools.
# Most pip packages (including binary wheels) work fine on slim.
FROM python:3.11-slim

# ── Metadata ──────────────────────────────────────────────────
LABEL description="Demo ETL pipeline: connects to Postgres, writes run records"
LABEL python="3.11-slim"

# ── OS dependencies ───────────────────────────────────────────
# psycopg2-binary bundles its own libpq — no need to install libpq-dev.
# ca-certificates: needed for HTTPS connections (S3, APIs, etc.)
# Clean up apt cache in the SAME RUN to avoid inflating the layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────
WORKDIR /app

# ── Non-root user ─────────────────────────────────────────────
# Running as root inside a container is a security risk.
# Create a dedicated user before copying application code.
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

# ── Python dependencies — BEFORE copying source code ──────────
# This is the critical layer cache optimization:
#   - requirements.txt changes infrequently
#   - Source code changes constantly
# By installing packages FIRST, 'pip install' is cached until
# requirements.txt actually changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source code ───────────────────────────────────
# Copied AFTER pip install so code changes don't invalidate the
# package install layer.
COPY . .

# ── Ownership ─────────────────────────────────────────────────
# Ensure the non-root user can read/write the app directory.
RUN chown -R appuser:appuser /app

# ── Runtime environment ───────────────────────────────────────
# PYTHONUNBUFFERED=1: flush stdout immediately.
#   Without this: print() output gets buffered and may not appear
#   in 'docker-compose logs' until the buffer flushes or the app exits.
#   For pipelines, you want to see progress as it happens.
# PYTHONDONTWRITEBYTECODE=1: don't create .pyc files in the container.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ── Switch to non-root user ───────────────────────────────────
USER appuser

# ── Default command ───────────────────────────────────────────
# Can be overridden: docker run my_pipeline python other_script.py
CMD ["python", "pipeline.py"]
