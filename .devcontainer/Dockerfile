# .devcontainer/Dockerfile
FROM python:3.12-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Minimal dev tooling + build deps for pyodbc + git deps
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
      unixodbc-dev \
      unixodbc \
      procps \
 && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 18 for SQL Server (same approach as your production Dockerfile)
RUN set -eux; \
  apt-get update; \
  curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb; \
  dpkg -i /tmp/packages-microsoft-prod.deb; \
  rm /tmp/packages-microsoft-prod.deb; \
  apt-get update; \
  ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18; \
  rm -rf /var/lib/apt/lists/*

# Create a non-root dev user (VS Code devcontainer convention)
RUN set -eux; \
  groupadd --gid "${USER_GID}" "${USERNAME}"; \
  useradd  --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}"; \
  echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}"; \
  chmod 0440 "/etc/sudoers.d/${USERNAME}"

WORKDIR /workspaces/automatic-data-extractor
# Note: intentionally not setting USER here; Compose/devcontainer config controls runtime user.
