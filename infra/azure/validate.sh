#!/usr/bin/env bash
set -euo pipefail

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI ('az') is required for infra validation." >&2
  exit 1
fi

main_template="infra/azure/main.bicep"
mapfile -t module_templates < <(rg --files infra/azure/modules -g '*.bicep' | sort)

for template in "$main_template" "${module_templates[@]}"; do
  echo "[build] $template"
  az bicep build --file "$template" --stdout >/dev/null
  echo "[lint]  $template"
  az bicep lint --file "$template"
done

echo "[shell] infra/azure/deploy.sh.example"
bash -n infra/azure/deploy.sh.example

echo "[shell] infra/azure/scripts/postgresql-entra-bootstrap.sh"
bash -n infra/azure/scripts/postgresql-entra-bootstrap.sh

if command -v pwsh >/dev/null 2>&1; then
  echo "[powershell] infra/azure/deploy.ps1.example"
  pwsh -NoLogo -NoProfile -Command "$errors = @(); [void][System.Management.Automation.Language.Parser]::ParseFile('infra/azure/deploy.ps1.example', [ref]$null, [ref]$errors); if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
fi

echo "Infra Azure validation passed."
