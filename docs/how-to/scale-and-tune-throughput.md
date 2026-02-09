# Scale and Tune Throughput

## Goal

Increase ADE processing capacity on Azure Container Apps without destabilizing production.

## Quick Definitions

- **Throughput**: number of runs completed per time window.
- **Latency**: time for one run to complete.
- **Replica**: one running copy of your container app.

## Main Controls (Single-Container Topology)

| Control | Effect |
| --- | --- |
| `ADE_WORKER_RUN_CONCURRENCY` | run parallelism inside each replica |
| `ADE_API_PROCESSES` | API processes inside each replica |
| app `min/max replicas` | horizontal scale for API, worker, and web together |

For split topology (`docker-compose.prod.split.yaml` style), scale worker containers first, then tune
`ADE_WORKER_RUN_CONCURRENCY` per container.

## Safe Tuning Process

1. Measure baseline: queue delay, run duration, CPU, memory, failure rate.
2. Change one setting at a time.
3. Increase `ADE_WORKER_RUN_CONCURRENCY` in small steps first.
4. If queue delay is still high, scale worker containers (split topology) or increase app replicas (single-container topology).
5. Increase `ADE_API_PROCESSES` only when API saturation is visible.

## Example Changes

Increase worker concurrency:

```bash
az containerapp update \
  --name ade-app \
  --resource-group <resource-group> \
  --set-env-vars ADE_WORKER_RUN_CONCURRENCY=6
```

Increase replica range:

```bash
az containerapp update \
  --name ade-app \
  --resource-group <resource-group> \
  --min-replicas 1 \
  --max-replicas 4
```

Adjust API process count:

```bash
az containerapp update \
  --name ade-app \
  --resource-group <resource-group> \
  --set-env-vars ADE_API_PROCESSES=2
```

## Important Tradeoff

In this topology, every replica runs API + worker + web. Scaling out increases all three together.

If API and worker need independent scaling, move to the split topology from [System Architecture](../explanation/system-architecture.md).

## Verify After Every Change

- queue delay improves or stays stable
- failure/retry rates do not increase
- CPU/memory stay within limits
- user-facing latency remains acceptable

## If Something Fails

1. Revert to last known-good settings.
2. Check logs:

```bash
az containerapp logs show --name ade-app --resource-group <resource-group> --tail 200
```

3. Continue with [Operate Runs](operate-runs.md) and [Triage Playbook](../troubleshooting/triage-playbook.md).

## Azure Reference

- [Azure Container Apps scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app)
