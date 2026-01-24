# .devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

ARG DEBIAN_FRONTEND=noninteractive

# The devcontainers/python image already includes a non-root `vscode` user with sudo.
# Make sure we're root for apt installs.
USER root

# Build deps for pyodbc + tooling needed to add the Microsoft repo key
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl \
      gnupg \
      build-essential \
      unixodbc-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 18 for SQL Server (Debian 12 / bookworm)
RUN set -eux; \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list; \
    apt-get update; \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces/automatic-data-extractor

# Go back to the normal dev user
USER vscode
