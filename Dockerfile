# syntax=docker/dockerfile:1

FROM node:20.18.0-bookworm AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/. ./
RUN npm run build

FROM python:3.11.10-slim-bookworm AS python-builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md alembic.ini ./
COPY ade/ ./ade/
RUN python -m venv "$VIRTUAL_ENV"
RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

FROM python:3.11.10-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    ADE_SERVER_HOST=0.0.0.0 \
    ADE_STORAGE_DATA_DIR=/var/lib/ade
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python-builder /opt/venv /opt/venv
COPY --from=python-builder /app/alembic.ini ./
COPY --from=python-builder /app/ade ./ade
COPY --from=frontend-builder /frontend/dist ./ade/web/static
RUN addgroup --system ade \
    && adduser --system --ingroup ade --home /home/ade ade \
    && mkdir -p /var/lib/ade/documents \
    && chown -R ade:ade /app /var/lib/ade
USER ade
EXPOSE 8000
CMD ["uvicorn", "ade.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
