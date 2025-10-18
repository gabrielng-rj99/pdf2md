# Multi-stage Dockerfile for PDF-to-Markdown-with-Images (FastAPI)
# - Builder stage compiles/wheels/install Python deps
# - Final stage is minimal runtime image that runs Gunicorn + Uvicorn workers
#
# This Dockerfile targets Python 3.13.7 (builder + runtime) to match project requirement.
# The app listens on 0.0.0.0:8000 internally; a reverse proxy (nginx/traefik) should
# terminate TLS on ports 80/443 and forward to this container.
#
# -----------------------------------------------------------------------------

####################
# Builder stage
####################
FROM python:3.13.7-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Install build-time system deps required to build binary wheels (e.g. Pillow, PyMuPDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Upgrade pip/setuptools/wheel and install dependencies into a local prefix
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt gunicorn

####################
# Runtime stage
####################
FROM python:3.13.7-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime libraries (smaller set than builder)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    libfreetype6 \
    liblcms2-2 \
    libopenjp2-7 \
    libtiff-dev \
    libwebp-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from builder
# pip --prefix installs packages under /install/lib/... and scripts under /install/bin
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create non-root user and set permissions
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

# Expose the internal port the app listens on (internal only).
EXPOSE 8000

# Default command: use Gunicorn with Uvicorn workers.
# Use environment variables (GUNICORN_WORKERS) to tune workers at runtime via docker-compose.
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "--bind", "0.0.0.0:8000", "app.main:app"]
