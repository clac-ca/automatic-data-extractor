# .devcontainer/Dockerfile
FROM python:3.12-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Minimal dev tooling + build deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash \
      ca-certificates \
      curl \
      gnupg \
      git \
      openssh-client \
      sudo \
      build-essential \
      libpq-dev \
      procps \
 && rm -rf /var/lib/apt/lists/*

# Install uv for repo tooling and scripts.
RUN python -m pip install --upgrade pip \
 && python -m pip install --no-cache-dir uv

# Create a non-root dev user (VS Code devcontainer convention)
RUN set -eux; \
  groupadd --gid "${USER_GID}" "${USERNAME}"; \
  useradd  --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}"; \
  echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}"; \
  chmod 0440 "/etc/sudoers.d/${USERNAME}"

WORKDIR /workspaces/automatic-data-extractor
# Note: intentionally not setting USER here; Compose/devcontainer config controls runtime user.
