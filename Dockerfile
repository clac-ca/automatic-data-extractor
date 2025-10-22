FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim AS backend-build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY backend ./backend
RUN python -m pip install -U pip \
 && pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
WORKDIR /app
COPY --from=backend-build /install /usr/local
COPY backend ./backend
COPY alembic.ini .
COPY --from=frontend-build /frontend/build/client ./backend/app/web/static
RUN mkdir -p /app/data/db /app/data/documents
VOLUME ["/app/data"]
EXPOSE 8000
ENV ADE_SERVER_HOST=0.0.0.0 ADE_SERVER_PORT=8000
CMD ["uvicorn","backend.app.main:create_app","--factory","--host","0.0.0.0","--port","8000"]
