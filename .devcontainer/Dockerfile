ARG PYTHON_IMAGE=python:3.14.2-slim-bookworm
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Prefer the workspace venv for python/pip once it exists.
ENV VIRTUAL_ENV=/workspaces/automatic-data-extractor/.venv \
    PATH="/workspaces/automatic-data-extractor/.venv/bin:${PATH}"

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    libpq-dev \
    sudo \
  && rm -rf /var/lib/apt/lists/* \
  && groupadd --gid "${USER_GID}" "${USERNAME}" \
  && useradd  --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}" \
  && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
  && chmod 0440 "/etc/sudoers.d/${USERNAME}"

WORKDIR /workspaces/automatic-data-extractor
