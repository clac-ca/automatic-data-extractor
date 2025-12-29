# syntax=docker/dockerfile:1.6

# Base versions (override at build time if needed)
ARG PYTHON_VERSION=3.14
ARG NODE_VERSION=20

# =============================================================================
# Stage 1: Frontend build (Vite SPA)
# =============================================================================
FROM node:${NODE_VERSION}-alpine AS frontend-build

WORKDIR /app/apps/ade-web

ARG FRONTEND_BUILD_SHA=dev

COPY apps/ade-web/package*.json ./
RUN if [ ! -x /usr/bin/npm ]; then ln -s "$(command -v npm)" /usr/bin/npm; fi
RUN --mount=type=cache,target=/root/.npm \
    /usr/bin/npm ci --no-audit --no-fund

COPY apps/ade-web/ ./
RUN --mount=type=cache,target=/root/.npm \
    echo "frontend build ${FRONTEND_BUILD_SHA}" >/dev/null && \
    /usr/bin/npm run build

# =============================================================================
# Stage 2: Backend build (install Python packages)
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS backend-build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

# Build deps (kept out of final image). pyodbc builds need unixodbc-dev.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        cargo \
        git \
        rustc \
        unixodbc-dev \
        pkg-config \
    ; \
    rm -rf /var/lib/apt/lists/*

# Copy minimal metadata first to maximize layer cache reuse
COPY README.md ./
COPY apps/ade-cli/pyproject.toml    apps/ade-cli/
COPY apps/ade-engine/pyproject.toml apps/ade-engine/
COPY apps/ade-api/pyproject.toml    apps/ade-api/

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -U pip

# Now copy full sources
COPY apps ./apps
COPY --from=frontend-build /app/apps/ade-web/dist \
    ./apps/ade-api/src/ade_api/web/static

# Install CLI, engine, and API into an isolated prefix (/install)
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --prefix=/install \
        ./apps/ade-cli \
        ./apps/ade-engine \
        ./apps/ade-api

# =============================================================================
# Stage 3: Runtime image (what actually runs in prod)
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    API_ROOT=/app/apps/ade-api \
    ALEMBIC_INI_PATH=/app/apps/ade-api/alembic.ini \
    ALEMBIC_MIGRATIONS_DIR=/app/apps/ade-api/migrations \
    ACCEPT_EULA=Y

WORKDIR /app

# -----------------------------------------------------------------------------
# SQL Server / Azure SQL ODBC driver (msodbcsql18) + unixODBC manager
# Use Microsoft's repo bootstrap package (stable on Debian slim)
# -----------------------------------------------------------------------------
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    curl -sSL -O https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb; \
    dpkg -i packages-microsoft-prod.deb; \
    rm -f packages-microsoft-prod.deb; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        unixodbc \
        msodbcsql18 \
        libgssapi-krb5-2 \
    ; \
    rm -rf /var/lib/apt/lists/*

# OCI labels
LABEL org.opencontainers.image.title="automatic-data-extractor" \
      org.opencontainers.image.description="ADE — Automatic Data Extractor" \
      org.opencontainers.image.source="https://github.com/clac-ca/automatic-data-extractor"

# Bring in installed Python packages + console scripts
COPY --from=backend-build /install /usr/local

# Copy app source tree (migrations, templates, etc.)
COPY apps ./apps

# Copy built SPA into FastAPI's static directory
COPY --from=frontend-build /app/apps/ade-web/dist \
    ./apps/ade-api/src/ade_api/web/static

# Non-root user + persistent data dir
RUN set -eux; \
    groupadd -r ade; \
    useradd -r -g ade ade; \
    mkdir -p /app/data/db /app/data/documents; \
    chown -R ade:ade /app

VOLUME ["/app/data"]
EXPOSE 8000

USER ade

CMD ["uvicorn", "ade_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
