FROM node:20-alpine AS web-build
WORKDIR /app

# Install web dependencies
COPY apps/ade-web/package*.json apps/ade-web/
RUN npm ci --prefix apps/ade-web --no-audit --no-fund

# Build the SPA (requires ade-schemas JSON during bundling)
COPY apps/ade-web apps/ade-web
COPY packages packages
RUN npm run build --prefix apps/ade-web

FROM python:3.12-slim AS backend-build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential git \
 && rm -rf /var/lib/apt/lists/*
COPY README.md ./
COPY apps/ade-api/pyproject.toml apps/ade-api/
COPY apps ./apps
COPY packages ./packages
RUN python -m pip install -U pip \
 && pip install --no-cache-dir --prefix=/install ./packages/ade-schemas ./apps/ade-engine ./apps/ade-api

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
WORKDIR /app
COPY --from=backend-build /install /usr/local
COPY apps ./apps
COPY packages ./packages
COPY --from=web-build /app/apps/ade-web/dist ./apps/ade-api/src/ade_api/web/static
RUN mkdir -p /app/data/db /app/data/documents
VOLUME ["/app/data"]
EXPOSE 8000
ENV ADE_SERVER_HOST=0.0.0.0 ADE_SERVER_PORT=8000
CMD ["uvicorn","ade_api.main:create_app","--factory","--host","0.0.0.0","--port","8000"]
