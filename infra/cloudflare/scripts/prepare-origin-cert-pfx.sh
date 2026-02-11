#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  prepare-origin-cert-pfx.sh <origin-cert.pem> <origin-key.pem> <output.pfx> <pfx-password>

Example:
  prepare-origin-cert-pfx.sh \
    ./certs/app.example.com.crt.pem \
    ./certs/app.example.com.key.pem \
    ./certs/app.example.com.pfx \
    'StrongPassword123!'
EOF
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    fail "Required command not found: $command_name"
  fi
}

if [ "$#" -ne 4 ]; then
  usage
  exit 1
fi

origin_certificate_pem="$1"
origin_private_key_pem="$2"
output_pfx_path="$3"
pfx_password="$4"

require_command openssl

[ -f "$origin_certificate_pem" ] || fail "Origin certificate file not found: $origin_certificate_pem"
[ -f "$origin_private_key_pem" ] || fail "Origin private key file not found: $origin_private_key_pem"
[ -n "$pfx_password" ] || fail "PFX password cannot be empty."

mkdir -p "$(dirname "$output_pfx_path")"
umask 077

tmp_output="${output_pfx_path}.tmp"
cleanup() {
  rm -f "$tmp_output"
}
trap cleanup EXIT

openssl pkcs12 -export \
  -out "$tmp_output" \
  -inkey "$origin_private_key_pem" \
  -in "$origin_certificate_pem" \
  -passout "pass:${pfx_password}"

mv "$tmp_output" "$output_pfx_path"
chmod 600 "$output_pfx_path"

echo "Wrote PFX certificate: $output_pfx_path"
