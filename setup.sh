# =============================================================================
# Prerequisites / One-time setup (Windows / macOS / Linux)
# -----------------------------------------------------------------------------
# You’ll need:
#   - Git
#   - Python 3.14+ (pip + venv)
#   - Node.js (LTS recommended) — npm comes with Node.js
#
# --- Windows (PowerShell) ---
#   # Git
#   winget install --id Git.Git -e --source winget
#
#   # Python (recommended: Python Install Manager)
#   winget install 9NQ7512CXL7T -e
#   py install 3.14
#
#   # Node.js LTS (includes npm)
#   winget install --id OpenJS.NodeJS.LTS -e
#
#   # Verify (open a NEW terminal first so PATH updates):
#   git --version
#   py -3.14 --version
#   node --version
#   npm --version
#
#   # Running the commands below on Windows:
#   #   - Use Git Bash or WSL for the bash commands, OR translate these two lines:
#   #       py -3.14 -m venv .venv
#   #       .\.venv\Scripts\Activate.ps1
#
# --- macOS (Homebrew) ---
#   # Install Homebrew (if needed): https://brew.sh/
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#   brew install git python@3.14 node
#   git --version && python3 --version && node --version && npm --version
#   # If python3 isn’t 3.14.x, use python3.14 when creating the venv.
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
#   # Optional: Python 3.14 via pyenv (if your distro doesn’t ship 3.14 yet)
#   #   Build deps (Ubuntu/Debian/Mint example):
#   sudo apt update; sudo apt install -y make build-essential libssl-dev zlib1g-dev \
#     libbz2-dev libreadline-dev libsqlite3-dev curl git libncursesw5-dev xz-utils tk-dev \
#     libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev libzstd-dev
#   curl -fsSL https://pyenv.run | bash
#   # Follow pyenv init instructions, then:
#   pyenv install 3.14
#   pyenv local 3.14
# =============================================================================

# Create and activate virtual environment (Python 3.14)
python3 -m venv .venv
source .venv/bin/activate

# Install backend packages
pip install -U pip setuptools wheel
pip install -e 'apps/ade-cli[dev]'
pip install -e 'apps/ade-api[dev]'
pip install -e apps/ade-engine

# Install frontend dependencies
(cd apps/ade-web && npm install)

# Verify CLI
ade --help