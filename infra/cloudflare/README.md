# ADE Cloudflare + Azure Container Apps

`infra/cloudflare` contains a Bash-first runbook and helper scripts for putting an existing Azure Container App behind Cloudflare with a custom subdomain and BYO certificate.

## Why BYO Certificate

This flow intentionally uses **bring your own certificate** (for example, Cloudflare Origin CA) instead of Azure managed certificates.

- Azure managed certificate issuance/renewal for subdomains requires a CNAME that points directly to the Container App FQDN.
- Azure explicitly calls out intermediate CNAME services (for example, Cloudflare) as blockers for managed certificate issuance/renewal.
- BYO certificate avoids that coupling and works with Cloudflare proxied traffic when Cloudflare SSL mode is `Full (strict)`.

References:

- https://learn.microsoft.com/en-us/azure/container-apps/custom-domains-managed-certificates
- https://learn.microsoft.com/en-us/azure/container-apps/custom-domains-certificates
- https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/
- https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/

## Scope

This package is v1 by design:

- Subdomain only (for example, `app.example.com`)
- Single hostname per script run
- Bash only
- Azure side scripted
- Cloudflare dashboard configuration documented (not scripted)

## Files

- `infra/cloudflare/deploy.sh.example`: Azure custom-domain bind automation for one hostname.
- `infra/cloudflare/scripts/prepare-origin-cert-pfx.sh`: converts PEM cert+key to PFX for Azure upload.
- `infra/cloudflare/validate.sh`: shell syntax checks for Cloudflare infra scripts.

## Prerequisites

- Azure CLI (`az`) authenticated and authorized for the target subscription/resource group.
- Existing Azure Container App and Container Apps environment.
- Container App ingress enabled and external/public.
- Cloudflare zone for your domain.
- Cloudflare Origin CA certificate (or other compatible BYO cert) and private key.
- `openssl` for PEM -> PFX conversion.
- `dig` (recommended) or `nslookup` if using DNS polling in deploy script.

## Quick Start

1. Copy the deploy template:

   ```bash
   cp infra/cloudflare/deploy.sh.example infra/cloudflare/deploy.sh
   chmod +x infra/cloudflare/deploy.sh
   ```

1. Create a Cloudflare Origin CA cert manually in Cloudflare:
   - Cloudflare dashboard -> `SSL/TLS` -> `Origin Server` -> `Create Certificate`
   - Include the exact hostname you will bind (or an approved wildcard policy)
   - Save cert and private key securely

1. Convert cert material to PFX for Azure:

   ```bash
   chmod +x infra/cloudflare/scripts/prepare-origin-cert-pfx.sh
   infra/cloudflare/scripts/prepare-origin-cert-pfx.sh \
     ./certs/app.example.com.crt.pem \
     ./certs/app.example.com.key.pem \
     ./certs/app.example.com.pfx \
     '<PFX_PASSWORD>'
   ```

1. Edit `infra/cloudflare/deploy.sh` inputs.

1. Run deployment:

   ```bash
   ./infra/cloudflare/deploy.sh
   ```

1. Follow post-bind Cloudflare cutover instructions printed by the script:
   - Toggle CNAME from DNS-only to Proxied (orange cloud)
   - Set SSL/TLS mode to `Full (strict)`

## Input Contract (`deploy.sh.example`)

| Input | Required | Purpose |
| --- | --- | --- |
| `subscription_id` | yes | Azure subscription ID |
| `resource_group_name` | yes | Resource group containing Container App |
| `container_app_name` | yes | Container App name |
| `container_apps_environment_name` | yes | Container Apps environment name |
| `domain_name` | yes | Subdomain FQDN to bind (for example `app.example.com`) |
| `certificate_name` | yes | Environment-scoped certificate name used by bind |
| `certificate_file` | yes | Local path to certificate (`.pfx` preferred, `.pem` supported) |
| `certificate_password` | depends | Password for `certificate_file` if encrypted/required |
| `wait_for_dns` | yes | `true` to poll DNS before bind, `false` for manual wait |
| `dns_poll_seconds` | yes | DNS poll interval in seconds |

Additional default:

- `dns_timeout_seconds`: max wait duration for DNS polling.

## End-to-End Runbook

1. Prepare origin certificate in Cloudflare.
1. Convert PEM materials to PFX (`prepare-origin-cert-pfx.sh`).
1. Run `deploy.sh` and note the DNS instructions:
   - CNAME: `<subdomain>` -> `<container-app-fqdn>`
   - TXT: `asuid.<subdomain>`
1. In Cloudflare DNS, create required records:
   - Keep CNAME **DNS-only** (gray cloud) while Azure hostname add/bind is being validated.
   - Confirm external resolvers can see a CNAME response to the Container App FQDN and the TXT `asuid.*` value.
1. Let script complete:
   - `az containerapp hostname add`
   - `az containerapp env certificate upload`
   - `az containerapp hostname bind --validation-method CNAME`
1. After successful bind:
   - Toggle CNAME to **Proxied** (orange cloud)
   - Set Cloudflare SSL/TLS mode to `Full (strict)`
   - Verify HTTPS path

## Validation and Test Scenarios

Use this checklist after implementation:

1. Happy path:
   - New subdomain with DNS-only CNAME + TXT
   - Script succeeds
   - Proxied toggle works
1. Idempotent rerun:
   - Re-running script does not perform destructive changes
1. DNS lag:
   - Polling waits and times out with actionable guidance if records are not visible
1. Invalid certificate:
   - Upload/bind fails with actionable next steps
1. Wrong proxy timing:
   - Bind fails when CNAME is proxied too early; resolved by switching to DNS-only and retrying
1. Post-cutover verification:
   - `az containerapp hostname list` includes hostname
   - `curl -I https://<domain>` returns HTTPS response through Cloudflare

## Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `hostname bind` fails validation | CNAME proxied (orange cloud) during validation | Set CNAME to DNS-only, verify CNAME/TXT, rerun |
| `hostname bind` fails but CNAME looks configured in dashboard | CNAME flattening behavior prevents resolvers from returning a CNAME answer | Verify `dig +short CNAME <domain>` returns the Container App FQDN during validation window |
| Script times out waiting for DNS | DNS propagation delay or wrong record values | Check `dig` outputs for CNAME/TXT and correct them |
| Certificate upload fails | Wrong file format/password | Recreate `.pfx` and verify password |
| `526` at Cloudflare edge | Cloudflare strict validation failing against origin cert | Ensure cert hostname coverage and unexpired cert; keep SSL mode `Full (strict)` |
| Custom domain not listed as secured in Azure | Bind command failed or partial bind state | Check `az containerapp hostname list`, fix DNS/cert, rerun bind |

## Security Notes

- Never commit private keys, certificate passwords, or generated `.pfx` files.
- Keep certificate material in a secure local path or secret store.
- Cloudflare Origin CA certificates are intended for Cloudflare-to-origin encryption; if proxying is disabled, browsers may not trust origin certs.

## Validation Command

```bash
bash infra/cloudflare/validate.sh
```
