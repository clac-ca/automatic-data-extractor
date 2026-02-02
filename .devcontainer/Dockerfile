ARG PYTHON_IMAGE=python:3.14.2-slim-bookworm
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Prefer the backend venv for all container processes (including VS Code + extensions like Codex).
# Docker-Compose can't reliably prepend to PATH using the existing value, so we do it here.
ENV VIRTUAL_ENV=/workspaces/automatic-data-extractor/backend/.venv \
    PATH="/workspaces/automatic-data-extractor/backend/.venv/bin:${PATH}"

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    curl \
    git \
    libpq-dev \
    sudo \
  && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
  && apt-get install -y --no-install-recommends nodejs \
  && curl -LsSf https://astral.sh/uv/install.sh | sh \
  && mv /root/.local/bin/uv /usr/local/bin/uv \
  && mv /root/.local/bin/uvx /usr/local/bin/uvx \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd --gid "${USER_GID}" "${USERNAME}" \
  && useradd  --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}" \
  && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
  && chmod 0440 "/etc/sudoers.d/${USERNAME}"

WORKDIR /workspaces/automatic-data-extractor
