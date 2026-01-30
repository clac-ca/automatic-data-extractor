ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG NODE_IMAGE=node:24-bookworm-slim

# Dev image:
#   docker build --target development -t <image>:dev .
# Prod image (final stage by default):
#   docker build -t <image>:latest .

# ============================================================
# BASE (shared env defaults for all stages)
# ============================================================
FROM ${PYTHON_IMAGE} AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ============================================================
# DEVELOPMENT (devcontainer only; source is bind-mounted)
# ============================================================
FROM python-base AS development
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    git \
    libpq-dev \
    sudo \
  && rm -rf /var/lib/apt/lists/* \
  && python -m pip install --upgrade pip \
  && groupadd --gid "${USER_GID}" "${USERNAME}" \
  && useradd  --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}" \
  && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
  && chmod 0440 "/etc/sudoers.d/${USERNAME}"

WORKDIR /workspaces/automatic-data-extractor
USER ${USERNAME}

# ============================================================
# BUILD ARTIFACTS (production only)
# ============================================================
# python-builder outputs /opt/venv
FROM python-base AS python-builder
WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    git \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/* \
  && python -m venv /opt/venv \
  && /opt/venv/bin/pip install --upgrade pip

ENV PATH="/opt/venv/bin:$PATH"

COPY apps/ade-api/ /src/apps/ade-api/
COPY apps/ade-worker/ /src/apps/ade-worker/
COPY apps/ade-cli/ /src/apps/ade-cli/
RUN pip install /src/apps/ade-api /src/apps/ade-worker /src/apps/ade-cli

# web-builder outputs dist/
FROM ${NODE_IMAGE} AS web-builder
WORKDIR /src/apps/ade-web

COPY apps/ade-web/package.json apps/ade-web/package-lock.json ./
RUN npm ci

COPY apps/ade-web/ ./
RUN npm run build

# ============================================================
# PRODUCTION (copies venv + dist)
# ============================================================
FROM python-base AS production
WORKDIR /app

# Runtime deps only.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libpq5 \
  && rm -rf /var/lib/apt/lists/*

# Create non-root runtime user.
RUN useradd -m -u 10001 appuser

# Copy Python deps and set PATH.
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built web assets.
COPY --from=web-builder /src/apps/ade-web/dist /app/web/dist
ENV ADE_FRONTEND_DIST_DIR="/app/web/dist"

# Ensure runtime data dir exists and is owned by appuser.
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
# Run `ade start` by default.
CMD ["ade", "start"]
