$WithInfra = $false
$Force = $false

foreach ($arg in $args) {
    switch ($arg) {
        "--with-infra" { $WithInfra = $true }
        "--force" { $Force = $true }
        "-h" {
            Write-Host "Usage: ./setup.ps1 [--with-infra] [--force]  # --with-infra runs `ade infra up -d`"
            exit 0
        }
        "--help" {
            Write-Host "Usage: ./setup.ps1 [--with-infra] [--force]  # --with-infra runs `ade infra up -d`"
            exit 0
        }
        default {
            throw "Unknown option: $arg"
        }
    }
}

if ($Force -and -not $WithInfra) {
    throw "--force requires --with-infra"
}

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

if ($WithInfra) {
    Write-Host "Starting local infrastructure..."
    Push-Location $BackendDir
    try {
        if ($Force) {
            uv run ade infra up --force -d
        }
        else {
            uv run ade infra up -d
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Try:"
Write-Host "  cd backend"
Write-Host "  uv run ade --help"
Write-Host "  uv run ade dev"
