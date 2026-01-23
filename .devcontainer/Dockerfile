# syntax=docker/dockerfile:1.6
#
# ADE devcontainer image
# - Fast + light: based on python:3.12-slim-bookworm
# - Installs Microsoft ODBC Driver 18 for SQL Server (msodbcsql18)
# - Includes unixODBC headers for pyodbc builds (unixodbc-dev)
# - Includes mssql-tools18 (sqlcmd) for local DB troubleshooting / scripts
#
# Notes:
# - We intentionally DO NOT install Node by default to keep the image lean.
#   If you work on apps/ade-web, run: scripts/dev/setup.sh --web
#
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps (minimal)
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
    && rm -rf /var/lib/apt/lists/*

# Add Microsoft package feed (Debian 12 / bookworm) + install ODBC driver/tools
RUN set -eux; \
    curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb; \
    dpkg -i /tmp/packages-microsoft-prod.deb; \
    rm /tmp/packages-microsoft-prod.deb; \
    apt-get update; \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 mssql-tools18 unixodbc; \
    rm -rf /var/lib/apt/lists/*

# sqlcmd path (mssql-tools18)
ENV PATH="$PATH:/opt/mssql-tools18/bin"

# Create a non-root user for VS Code / devcontainers
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} -s /bin/bash \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

WORKDIR /workspaces/automatic-data-extractor

USER ${USERNAME}
