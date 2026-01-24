# syntax=docker/dockerfile:1.6

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
# Node is only needed to build the React frontend. We keep it out of the runtime image.
# Pin to a major LTS line for stability + security updates.
ARG NODE_IMAGE=node:24-bookworm-slim

FROM ${PYTHON_IMAGE} AS py-builder
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src

# git required for ade-engine install via git+https for now
RUN apt-get update \
  && apt-get install -y --no-install-recommends git ca-certificates build-essential unixodbc-dev \
  && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
  && python -m pip install --no-cache-dir uv

RUN uv venv /opt/venv --python python
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/ade-api/ /src/apps/ade-api/
COPY apps/ade-worker/ /src/apps/ade-worker/
COPY apps/ade-cli/ /src/apps/ade-cli/

RUN uv pip install --python /opt/venv/bin/python \
       /src/apps/ade-api \
       /src/apps/ade-worker \
       /src/apps/ade-cli

FROM ${NODE_IMAGE} AS web-builder
WORKDIR /src/apps/ade-web
COPY apps/ade-web/ /src/apps/ade-web/
RUN set -eux; \
  corepack enable || true; \
  if [ -f pnpm-lock.yaml ]; then \
    corepack pnpm install --frozen-lockfile; \
    corepack pnpm run build; \
  elif [ -f yarn.lock ]; then \
    corepack yarn install --frozen-lockfile; \
    corepack yarn run build; \
  elif [ -f package-lock.json ]; then \
    npm ci; \
    npm run build; \
  else \
    npm install; \
    npm run build; \
  fi

FROM ${PYTHON_IMAGE} AS runtime
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# ODBC Driver 18 runtime deps
RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends ca-certificates curl gnupg; \
  curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb; \
  dpkg -i /tmp/packages-microsoft-prod.deb; \
  rm /tmp/packages-microsoft-prod.deb; \
  apt-get update; \
  ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc; \
  apt-get purge -y --auto-remove curl gnupg; \
  rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 appuser

COPY --from=py-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --from=web-builder /src/apps/ade-web/dist /app/apps/ade-web/dist
COPY apps /app/apps

RUN mkdir -p /app/data \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# CLI-style image: "docker run image" behaves like running the `ade` binary.
ENTRYPOINT ["ade"]
CMD ["start"]
