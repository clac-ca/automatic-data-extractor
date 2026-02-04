#!/usr/bin/env sh
set -eu

DATA_DIR="${ADE_DATA_DIR:-/app/data}"
APP_USER="${APP_USER:-appuser}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"

  APP_UID="$(id -u "$APP_USER")"
  APP_GID="$(id -g "$APP_USER")"

  if [ "$(stat -c '%u:%g' "$DATA_DIR")" != "${APP_UID}:${APP_GID}" ]; then
    chown -R "${APP_UID}:${APP_GID}" "$DATA_DIR"
  fi

  exec gosu "$APP_USER" "$@"
fi

exec "$@"
