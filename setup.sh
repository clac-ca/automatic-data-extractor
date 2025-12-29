#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Prerequisites / One-time setup (Windows / macOS / Linux)
# -----------------------------------------------------------------------------
# You’ll need:
#   - Git
#   - Python 3.11+ (pip + venv)
#   - Node.js (LTS recommended) — npm comes with Node.js
#
# --- Windows (PowerShell) ---
#   # Git
#   winget install --id Git.Git -e --source winget
#
#   # Python (recommended: Python Install Manager)
#   winget install 9NQ7512CXL7T -e
#   py install 3.11
#
#   # Node.js LTS (includes npm)
#   winget install --id OpenJS.NodeJS.LTS -e
#
#   # Verify (open a NEW terminal first so PATH updates):
#   git --version
#   py -3.11 --version
#   node --version
#   npm --version
#
#   # Running the commands below on Windows:
#   #   - Use Git Bash or WSL for the bash commands, OR translate these two lines:
#   #       py -3.11 -m venv .venv
#   #       .\.venv\Scripts\Activate.ps1
#
# --- macOS (Homebrew) ---
#   # Install Homebrew (if needed): https://brew.sh/
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#   brew install git python@3.11 node
#   git --version && python3 --version && node --version && npm --version
#   # If python3 isn’t 3.11.x, use python3.11 when creating the venv.
#
# --- Linux ---
#   # Debian/Ubuntu/Mint (distro packages)
#   sudo apt update
#   sudo apt install -y git python3 python3-venv python3-pip nodejs npm
#
#   # Fedora
#   sudo dnf install -y git python3 python3-pip nodejs npm
#
#   # Arch
#   sudo pacman -S --needed git python python-pip nodejs npm
#
#   # Optional: Node via nvm (handy if npm/node from your distro is too old)
#   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
#   . "$HOME/.nvm/nvm.sh"
#   nvm install --lts
#
#   # Optional: Python 3.11 via pyenv (if your distro doesn’t ship 3.11 yet)
#   #   Build deps (Ubuntu/Debian/Mint example):
#   sudo apt update; sudo apt install -y make build-essential libssl-dev zlib1g-dev \
#     libbz2-dev libreadline-dev libsqlite3-dev curl git libncursesw5-dev xz-utils tk-dev \
#     libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev libzstd-dev
#   curl -fsSL https://pyenv.run | bash
#   # Follow pyenv init instructions, then:
#   pyenv install 3.11
#   pyenv local 3.11
# =============================================================================

# Create and activate virtual environment (Python 3.11+)
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Install backend packages
python -m pip install -U pip setuptools wheel

# Install local packages (engine first so the API can resolve `ade-engine`)
python -m pip install -e apps/ade-engine
python -m pip install -e 'apps/ade-api[dev]'
python -m pip install -e 'apps/ade-cli[dev]'

# Install frontend dependencies
if [[ -f apps/ade-web/package-lock.json ]]; then
  (cd apps/ade-web && npm ci)
else
  (cd apps/ade-web && npm install)
fi

# Verify CLI
ade --help
