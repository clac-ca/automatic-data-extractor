#!/usr/bin/env bash
set -euo pipefail

# scripts/db/wait-for-sql.sh
#
# Compatibility wrapper (kept for existing docs/scripts).
# The canonical implementation is now Python-based to avoid requiring `sqlcmd`
# (mssql-tools18 has had intermittent install issues in CI and dev images).
#
# See: scripts/db/wait-for-sql.py

python scripts/db/wait-for-sql.py
