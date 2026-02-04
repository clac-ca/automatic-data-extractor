#!/usr/bin/env sh
set -eu

# Docker named volumes are root-owned by default. Start as root so we can fix
# ownership, then drop to the unprivileged runtime user. This mirrors the
# standard pattern used by official images (Postgres/MySQL/Redis).

DATA_DIR="${ADE_DATA_DIR:-/app/backend/data}"
APP_USER="${APP_USER:-adeuser}"

if [ "$(id -u)" = "0" ]; then
  # Ensure the mount exists even on first boot.
  mkdir -p "$DATA_DIR"

  # Resolve runtime uid/gid from the username (safer than hard-coding).
  APP_UID="$(id -u "$APP_USER")"
  APP_GID="$(id -g "$APP_USER")"

  # Only chown when needed to avoid slow recursive chowns on every boot.
  if [ "$(stat -c '%u:%g' "$DATA_DIR")" != "${APP_UID}:${APP_GID}" ]; then
    chown -R "${APP_UID}:${APP_GID}" "$DATA_DIR"
  fi

  # Drop privileges and exec the real process.
  exec gosu "$APP_USER" "$@"
fi

# Already running unprivileged.
exec "$@"
