ARG PYTHON_IMAGE=python:3.14.2-slim-bookworm

# Build image:
#   docker build -t <image>:latest .

# ============================================================
# BASE (shared env defaults for all stages)
# ============================================================
FROM ${PYTHON_IMAGE} AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ============================================================
# BUILD STAGE (build deps here so the final image stays small)
# ============================================================
# outputs /opt/venv
FROM python-base AS build
WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/* \
  && python -m venv /opt/venv \
  && /opt/venv/bin/pip install --upgrade pip

# git is required to install ade-engine from GitHub until it is published.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
  && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH"

COPY apps/ade-api/ /src/apps/ade-api/
COPY apps/ade-worker/ /src/apps/ade-worker/
RUN pip install /src/apps/ade-api /src/apps/ade-worker

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
    nginx \
  && rm -rf /var/lib/apt/lists/*

# Create non-root runtime user.
RUN useradd -m -u 10001 appuser

# Copy Python deps and set PATH.
COPY --from=build /opt/venv /opt/venv
COPY --from=web-build /web/dist /app/web/dist
ENV PATH="/opt/venv/bin:$PATH"

# Ensure runtime data dir exists and is owned by appuser.
RUN mkdir -p /app/data /app/web && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
# Run API + worker + web (nginx) in a single container by default.
CMD ["ade", "start"]
