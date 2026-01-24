# .devcontainer/Dockerfile
#
# Devcontainer image for ADE:
# - Python 3.12 (slim) on Debian Bookworm
# - Microsoft ODBC Driver 18 (msodbcsql18) for SQL Server
# - Minimal baseline tooling needed for editable installs + git deps
#
# Node is installed via a Dev Container Feature (see devcontainer.json) so it can be
# version-pinned and updated independently of this image./Users/justinkropp/Downloads/ade-devcontainer-github-workflows-final-v2/.env.example

FROM python:3.12-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Base tooling for dev + building Python packages (pyodbc/greenlet wheels may not exist for all arch)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      gnupg \
      git \
      openssh-client \
      sudo \
      build-essential \
      unixodbc-dev \
      xz-utils \
      procps \
 && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 18 for SQL Server (multi-arch packages available for Debian 12)
RUN set -eux; \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list; \
    apt-get update; \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18; \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user (VS Code Dev Containers convention)
RUN set -eux; \
    groupadd --gid ${USER_GID} ${USERNAME}; \
    useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME}; \
    echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME}; \
    chmod 0440 /etc/sudoers.d/${USERNAME}

WORKDIR /workspaces/automatic-data-extractor

USER ${USERNAME}
