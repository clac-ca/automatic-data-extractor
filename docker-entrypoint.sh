#!/usr/bin/env sh
set -eu

# Standard container flow:
# 1) Render nginx config templates (envsubst).
# 2) Fix data directory ownership if running as root.
# 3) Drop to the unprivileged runtime user and exec the real process.

DATA_DIR="${ADE_DATA_DIR:-/app/data}"
APP_USER="${APP_USER:-adeuser}"
DEFAULT_INTERNAL_API_URL="http://localhost:8001"

render_nginx_config() {
  template="/etc/nginx/templates/default.conf.tmpl"
  conf_dir="/etc/nginx/conf.d"

  [ -f "$template" ] || return 0
  [ -d "$conf_dir" ] || return 0

  if ! command -v envsubst >/dev/null 2>&1; then
    echo "error: envsubst not found (install gettext-base to render nginx templates)." >&2
    exit 1
  fi

  # Use the same default as the CLI. Only substitute ADE_INTERNAL_API_URL so
  # nginx runtime variables like $http_upgrade remain intact.
  if [ -z "${ADE_INTERNAL_API_URL:-}" ]; then
    export ADE_INTERNAL_API_URL="$DEFAULT_INTERNAL_API_URL"
  fi

  envsubst '$ADE_INTERNAL_API_URL' < "$template" > "$conf_dir/default.conf"
}

render_nginx_config

# Docker named volumes are root-owned by default. Start as root so we can fix
# ownership, then drop to the unprivileged runtime user (official image pattern).
if [ "$(id -u)" = "0" ]; then
  # Ensure the mount exists even on first boot.
  mkdir -p "$DATA_DIR"

  if ! id "$APP_USER" >/dev/null 2>&1; then
    echo "error: runtime user '$APP_USER' not found." >&2
    exit 1
  fi

  # Resolve runtime uid/gid from the username (safer than hard-coding).
  APP_UID="$(id -u "$APP_USER")"
  APP_GID="$(id -g "$APP_USER")"

  # Only chown when needed to avoid slow recursive chowns on every boot.
  if [ "$(stat -c '%u:%g' "$DATA_DIR")" != "${APP_UID}:${APP_GID}" ]; then
    chown -R "${APP_UID}:${APP_GID}" "$DATA_DIR"
  else
    # Root dir owner matches. Probe once for nested uid/gid drift.
    MISMATCH_PATH="$(
      find "$DATA_DIR" -mindepth 1 \( -not -uid "$APP_UID" -o -not -gid "$APP_GID" \) -print -quit
    )"
    if [ -n "$MISMATCH_PATH" ]; then
      chown -R "${APP_UID}:${APP_GID}" "$DATA_DIR"
    fi
  fi

  exec gosu "$APP_USER" "$@"
fi

# Already running unprivileged.
exec "$@"
