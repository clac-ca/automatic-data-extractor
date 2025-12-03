# Create and activate virtual environment (Python 3.14)
python -m venv .venv
source .venv/bin/activate

# Install backend packages
pip install -U pip setuptools wheel
pip install -e 'apps/ade-cli[dev]'  # include dev extras for pytest/etc.
pip install -e 'apps/ade-api[dev]'  # include dev extras for pytest/etc.
pip install -e apps/ade-engine

# Install frontend dependencies
(cd apps/ade-web && npm install)

# Verify CLI
ade --help
