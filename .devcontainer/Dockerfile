ARG PYTHON_VARIANT=3.12-bookworm
FROM mcr.microsoft.com/devcontainers/python:1-${PYTHON_VARIANT}

# Install Microsoft ODBC Driver 18 + optional sqlcmd tools (Debian-based)
RUN set -eux; \
  apt-get update; \
  apt-get install -y --no-install-recommends curl ca-certificates gnupg; \
  curl -sSL -O https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb; \
  dpkg -i packages-microsoft-prod.deb; \
  rm packages-microsoft-prod.deb; \
  apt-get update; \
  ACCEPT_EULA=Y apt-get install -y msodbcsql18; \
  ACCEPT_EULA=Y apt-get install -y mssql-tools18; \
  apt-get install -y unixodbc-dev; \
  echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' > /etc/profile.d/mssql-tools.sh; \
  apt-get clean; \
  rm -rf /var/lib/apt/lists/*
