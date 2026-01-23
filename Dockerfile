# Base versions (override at build time if needed)
ARG PYTHON_VERSION=3.12
# =============================================================================
# Stage 1: Backend build (install Python packages)
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS backend-build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

# Build deps (kept out of final image).
# - unixodbc-dev: build pyodbc if needed
# - libssl-dev/libffi-dev: common for azure-identity/crypto deps when wheels lag
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        cargo \
        git \
        rustc \
        unixodbc-dev \
        pkg-config \
        libssl-dev \
        libffi-dev \
    ; \
    rm -rf /var/lib/apt/lists/*

COPY README.md ./
COPY apps/ade-cli/pyproject.toml    apps/ade-cli/
COPY apps/ade-api/pyproject.toml    apps/ade-api/
COPY apps/ade-worker/pyproject.toml apps/ade-worker/

RUN python -m pip install -U pip

COPY apps ./apps

RUN python -m pip install --prefix=/install \
        ./apps/ade-cli \
        ./apps/ade-api \
        ./apps/ade-worker

# =============================================================================
# Stage 1b: Frontend build (Vite)
# =============================================================================
FROM node:20-bookworm AS web-build

WORKDIR /app/apps/ade-web

COPY apps/ade-web/package.json apps/ade-web/package-lock.json ./
RUN npm ci

COPY apps/ade-web ./
RUN npm run build

# =============================================================================
# Stage 2: Runtime image
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ACCEPT_EULA=Y

WORKDIR /app

# -----------------------------------------------------------------------------
# SQL Server / Azure SQL ODBC driver (msodbcsql18) + unixODBC manager
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
    # Optional but robust EULA acceptance method (ODBC 18.4+)
    mkdir -p /opt/microsoft/msodbcsql18; \
    touch /opt/microsoft/msodbcsql18/ACCEPT_EULA; \
    rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="automatic-data-extractor" \
      org.opencontainers.image.description="ADE — Automatic Data Extractor" \
      org.opencontainers.image.source="https://github.com/clac-ca/automatic-data-extractor"

COPY --from=backend-build /install /usr/local
COPY apps ./apps
COPY --from=web-build /app/apps/ade-web/dist ./apps/ade-web/dist

RUN set -eux; \
    groupadd -r ade; \
    useradd -r -g ade ade; \
    mkdir -p /app/data/db /app/data/documents; \
    chown -R ade:ade /app

VOLUME ["/app/data"]
EXPOSE 8000

USER ade

CMD ["ade", "start"]
