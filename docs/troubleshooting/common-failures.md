# Common Failures

Use this table to map symptoms to fixes quickly.

| Symptom | Likely Cause | Immediate Action |
| --- | --- | --- |
| App fails to start after deploy | required env vars or secrets missing | verify env/secrets and redeploy |
| Deploy completed but behavior did not change | traffic still routed to older revision | list revisions and route traffic to target revision |
| Runs stay `queued` | worker path unhealthy or concurrency/replicas too low | verify app health, raise `ADE_WORKER_RUN_CONCURRENCY`, check replicas |
| DB connection denied from app | ACA outbound IPs are not in PostgreSQL firewall rules | list app outbound IPs and add/update firewall rules |
| DB connectivity broke after hardening | temporary `0.0.0.0` bootstrap rule removed before exact rules added | add explicit app/operator rules first, then remove bootstrap rule |
| Blob auth fails with managed identity | missing blob RBAC or wrong `ADE_BLOB_ACCOUNT_URL` | assign `Storage Blob Data Contributor` and verify account URL |
| Storage requests fail with `Deny` | Storage firewall default deny but missing IP/VNet rule | add required IP rule (operator/CI) and subnet rule (ACA) |
| Storage access still too open | relying on IP rules only for same-region Azure traffic | enforce VNet rule + service endpoint for ACA subnet |
| Private endpoint deployment cannot resolve storage host | private DNS zone/link is missing | validate private DNS zones and VNet links |
| Data disappears after restart | `/backend/data` not mounted | verify ACA volumes + volumeMounts for Azure Files |
| Login behavior is incorrect | `ADE_PUBLIC_WEB_URL` or auth settings mismatch | correct values and redeploy |

## Fast Commands

```bash
az containerapp show --name ade-app --resource-group <resource-group>
az containerapp logs show --name ade-app --resource-group <resource-group> --tail 200
az containerapp revision list --name ade-app --resource-group <resource-group> -o table
az containerapp show --name ade-app --resource-group <resource-group> --query properties.outboundIpAddresses -o tsv
az postgres flexible-server firewall-rule list --resource-group <resource-group> --name <pg-server> --output table
az storage account network-rule list --resource-group <resource-group> --account-name <storage-account> -o json
```

## Escalate When

- issue persists after config and revision corrections
- data integrity may be impacted
- authentication/authorization controls are bypassed or failing
