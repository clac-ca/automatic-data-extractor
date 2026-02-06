# ADE Documentation

ADE (Automatic Data Extractor) processes spreadsheet files (`.xlsx`, `.csv`) into standardized output files.

This documentation is written for people who operate ADE in production and contributors who build it.

## Quick Definitions

- **Azure Container Apps (ACA)**: Azure service that runs containers without managing VMs directly.
- **API**: backend service used by the web app and automation.
- **Worker**: background process that executes extraction runs.
- **Run**: one processing job for one input file.
- **Environment variable**: `NAME=value` setting that controls behavior.
- **Migration**: database schema update.

## Start Here

### Operator Path

1. [Local Quickstart](tutorials/local-quickstart.md)
2. [Production Bootstrap (Azure Container Apps, Single Container)](tutorials/production-bootstrap.md)
3. [Deploy to Production](how-to/deploy-production.md)
4. [Operate Runs](how-to/operate-runs.md)
5. [Triage Playbook](troubleshooting/triage-playbook.md)

### Contributor Path

1. [Developer Setup (Fast Path)](tutorials/developer-setup.md)
2. [Run Local Dev Loop](how-to/run-local-dev-loop.md)
3. [CLI Reference](reference/cli-reference.md)
4. [Backend Service Module Contract](reference/backend-service-module-contract.md)
5. [System Architecture](explanation/system-architecture.md)
6. [Documentation Maintenance](standards/documentation-maintenance.md)

## I Need To

| Task | Go To |
| --- | --- |
| Run ADE locally | [Local Quickstart](tutorials/local-quickstart.md) |
| Set up first production deployment in Azure | [Production Bootstrap](tutorials/production-bootstrap.md) |
| Deploy or update production safely | [Deploy to Production](how-to/deploy-production.md) |
| Improve processing capacity | [Scale and Tune Throughput](how-to/scale-and-tune-throughput.md) |
| Run migrations or resets safely | [Run Migrations and Resets](how-to/run-migrations-and-resets.md) |
| Manage users and permissions | [Manage Users and Access](how-to/manage-users-and-access.md) |
| Understand run states and retries | [Runtime Lifecycle](reference/runtime-lifecycle.md) |
| Troubleshoot quickly | [Triage Playbook](troubleshooting/triage-playbook.md) |
| See exact command syntax | [CLI Reference](reference/cli-reference.md) |
| See required settings | [Environment Variables](reference/environment-variables.md) |
| Compare code defaults vs compose defaults | [Defaults Matrix](reference/defaults-matrix.md) |

## Navigation

- Tutorials
  - [Developer Setup (Fast Path)](tutorials/developer-setup.md)
  - [Local Quickstart](tutorials/local-quickstart.md)
  - [Production Bootstrap](tutorials/production-bootstrap.md)
- How-to
  - [Run Local Dev Loop](how-to/run-local-dev-loop.md)
  - [Deploy to Production](how-to/deploy-production.md)
  - [Scale and Tune Throughput](how-to/scale-and-tune-throughput.md)
  - [Run Migrations and Resets](how-to/run-migrations-and-resets.md)
  - [Manage Users and Access](how-to/manage-users-and-access.md)
  - [Operate Runs](how-to/operate-runs.md)
- Troubleshooting
  - [Triage Playbook](troubleshooting/triage-playbook.md)
  - [Common Failures](troubleshooting/common-failures.md)
- Reference
  - [CLI Reference](reference/cli-reference.md)
  - [Backend Service Module Contract](reference/backend-service-module-contract.md)
  - [Environment Variables](reference/environment-variables.md)
  - [API Capability Map](reference/api-capability-map.md)
  - [Defaults Matrix](reference/defaults-matrix.md)
  - [Runtime Lifecycle](reference/runtime-lifecycle.md)
  - [Release Process](reference/release-process.md)
- Explanation
  - [System Architecture](explanation/system-architecture.md)
  - [Reliability and Failure Model](explanation/reliability-and-failure-model.md)
  - [Security and Authentication](explanation/security-and-authentication.md)
- Standards
  - [Documentation Style Guide](standards/documentation-style-guide.md)
  - [Documentation Maintenance](standards/documentation-maintenance.md)
