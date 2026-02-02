ARG PYTHON_IMAGE=python:3.14.2-slim-bookworm

# Build image:
#   docker build -t <image>:latest .

# ============================================================
# BASE (shared env defaults for all stages)
# ============================================================
FROM ${PYTHON_IMAGE} AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ============================================================
# BUILD STAGE (build deps here so the final image stays small)
# ============================================================
# outputs /opt/venv
FROM python-base AS build
WORKDIR /src

# git is required to install ade-engine from GitHub until it is published.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    git \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv

COPY apps/ade-api/ /src/apps/ade-api/
COPY apps/ade-worker/ /src/apps/ade-worker/
RUN uv --project /src/apps/ade-api sync --frozen --no-dev --no-editable
# Preserve ade-api install while adding ade-worker dependencies.
RUN uv --project /src/apps/ade-worker sync --frozen --no-dev --no-editable --inexact

# ============================================================
# WEB BUILD STAGE (build frontend assets)
# ============================================================
FROM node:20-bookworm-slim AS web-build
WORKDIR /web
COPY apps/ade-web/package*.json /web/
RUN npm ci
COPY apps/ade-web/ /web/
RUN npm run build

# ============================================================
# FINAL STAGE (small runtime image)
# ============================================================
FROM python-base AS final
WORKDIR /app

# Runtime deps only.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libpq5 \
    gettext-base \
    nginx \
  && rm -rf /var/lib/apt/lists/*
RUN sed -i 's|pid /run/nginx.pid;|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf

# Create non-root runtime user.
RUN useradd -m -u 10001 appuser

# Copy Python deps and set PATH.
COPY --from=build /opt/venv /opt/venv
COPY --from=web-build /web/dist /usr/share/nginx/html
COPY apps/ade-web/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY apps/ade-web/nginx/entrypoint.sh /usr/local/bin/ade-web-entrypoint
ENV PATH="/opt/venv/bin:$PATH"

# Ensure runtime dirs are owned by appuser.
RUN mkdir -p /app/data /var/cache/nginx /var/run/nginx /var/lib/nginx /var/log/nginx \
  && chown -R appuser:appuser /app /usr/share/nginx/html /etc/nginx/conf.d /etc/nginx/templates /var/cache/nginx /var/run/nginx /var/lib/nginx /var/log/nginx
USER appuser

EXPOSE 8080 8000
# Default to the API service; override per container/compose role.
CMD ["ade-api", "start"]
