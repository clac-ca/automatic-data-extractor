FROM node:20-alpine AS web-build
WORKDIR /app/web
COPY apps/web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ .
RUN npm run build

FROM python:3.12-slim AS backend-build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential git \
 && rm -rf /var/lib/apt/lists/*
COPY README.md ./
COPY apps/api/pyproject.toml apps/api/
COPY apps ./apps
COPY packages ./packages
RUN python -m pip install -U pip \
 && pip install --no-cache-dir --prefix=/install ./apps/api

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
WORKDIR /app
COPY --from=backend-build /install /usr/local
COPY apps ./apps
COPY packages ./packages
COPY --from=web-build /app/web/dist ./apps/api/app/web/static
RUN mkdir -p /app/data/db /app/data/documents
VOLUME ["/app/data"]
EXPOSE 8000
ENV ADE_SERVER_HOST=0.0.0.0 ADE_SERVER_PORT=8000
CMD ["uvicorn","apps.api.app.main:create_app","--factory","--host","0.0.0.0","--port","8000"]
