$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required: https://astral.sh/uv"
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required (Node.js >=20,<23)."
}

Write-Host "Installing web dependencies (frontend/node_modules)..."
npm ci --prefix $FrontendDir

Write-Host "Installing backend dependencies (backend/.venv)..."
Push-Location $BackendDir
try {
    uv sync
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Try:"
Write-Host "  cd backend"
Write-Host "  uv run ade --help"
Write-Host "  uv run ade dev"
