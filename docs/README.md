# ADE Documentation

Contributor-first documentation for operating, extending, and troubleshooting
ADE in production.

Use section `README.md` pages as stable landing points for GitHub navigation.

## Start Here by Role

| Role | Start path |
| --- | --- |
| New contributor | [Developer Setup](tutorials/developer-setup.md) -> [Run Local Dev Loop](how-to/run-local-dev-loop.md) -> [CLI Reference](reference/cli-reference.md) |
| Platform operator | [Local Quickstart](tutorials/local-quickstart.md) -> [Deploy Azure Infra (Bicep)](how-to/deploy-azure-bicep-scenarios.md) -> [Deploy to Production](how-to/deploy-production.md) -> [Operate Runs](how-to/operate-runs.md) |
| API integrator | [API Reference](reference/api/README.md) -> [Authenticate with API Key](how-to/api-authenticate-with-api-key.md) -> [Create and Monitor Runs](how-to/api-create-and-monitor-runs.md) |

## Product Surfaces

### Configuration workbench (hero)

![Configuration workbench with ADE config package files](assets/readme/configuration-workbench-hero.png)

Code-first authoring surface for extraction logic, validation, and publish-ready
configuration drafts.

### Workspace directory

![Workspace directory for remittance operations](assets/readme/workspaces-directory.png)

Operational workspace model for intake, exception handling, and reconciliation.

### Documents ledger

![Documents ledger with staged remittance files](assets/readme/documents-ledger-remittance.png)

Document queue with assignees, status context, and run lifecycle visibility.

## Most Used Docs

- [Run Local Dev Loop](how-to/run-local-dev-loop.md)
- [Deploy to Production](how-to/deploy-production.md)
- [Manage Users and Access](how-to/manage-users-and-access.md)
- [Manage Runtime Settings](how-to/manage-runtime-settings.md)
- [Access Reference](reference/access/README.md)
- [Environment Variables](reference/environment-variables.md)
- [Runtime Lifecycle](reference/runtime-lifecycle.md)
- [Triage Playbook](troubleshooting/triage-playbook.md)

## Documentation Sections

- [Tutorials](tutorials/README.md)
- [How-To Guides](how-to/README.md)
- [Reference](reference/README.md)
- [Explanation](explanation/README.md)
- [Troubleshooting](troubleshooting/README.md)
- [Standards](standards/README.md)

<details>
<summary>Full navigation map</summary>

### Tutorials

- [Developer Setup](tutorials/developer-setup.md)
- [Local Quickstart](tutorials/local-quickstart.md)
- [Production Bootstrap](tutorials/production-bootstrap.md)

### How-To

- [Deploy Azure Infra (Bicep)](how-to/deploy-azure-bicep-scenarios.md)
- [Run Local Dev Loop](how-to/run-local-dev-loop.md)
- [Deploy to Production](how-to/deploy-production.md)
- [Operate Runs](how-to/operate-runs.md)
- [Run Migrations and Resets](how-to/run-migrations-and-resets.md)
- [Scale and Tune Throughput](how-to/scale-and-tune-throughput.md)
- [Manage Users and Access](how-to/manage-users-and-access.md)
- [Manage Runtime Settings](how-to/manage-runtime-settings.md)
- [Auth Operations](how-to/auth-operations.md)
- [Auth Rollout and Smoke Checklist](how-to/auth-rollout-and-smoke-checklist.md)
- [Authenticate with API Key](how-to/api-authenticate-with-api-key.md)
- [Manage Configurations via API](how-to/api-manage-configurations.md)
- [Upload a Document and Queue Runs](how-to/api-upload-and-queue-runs.md)
- [Create and Monitor Runs via API](how-to/api-create-and-monitor-runs.md)

### Reference

- [CLI Reference](reference/cli-reference.md)
- [Environment Variables](reference/environment-variables.md)
- [Defaults Matrix](reference/defaults-matrix.md)
- [Runtime Lifecycle](reference/runtime-lifecycle.md)
- [Release Process](reference/release-process.md)
- [Backend Service Module Contract](reference/backend-service-module-contract.md)
- [Auth Architecture](reference/auth-architecture.md)
- [Access Reference](reference/access/README.md)
- [API Capability Map](reference/api-capability-map.md)
- [Azure Infra Bicep Reference](reference/azure-bicep-parameters-and-naming.md)
- [API Reference](reference/api/README.md)
- [Service Reference](reference/services/README.md)

### Explanation

- [System Architecture](explanation/system-architecture.md)
- [Reliability and Failure Model](explanation/reliability-and-failure-model.md)
- [Security and Authentication](explanation/security-and-authentication.md)
- [Access Management Model](explanation/access-management-model.md)

### Troubleshooting

- [Triage Playbook](troubleshooting/triage-playbook.md)
- [Common Failures](troubleshooting/common-failures.md)
- [Auth Incident Runbook](troubleshooting/auth-incident-runbook.md)
- [Access Management Incident Runbook](troubleshooting/access-management-incident-runbook.md)

### Standards

- [Documentation Style Guide](standards/documentation-style-guide.md)
- [Documentation Maintenance](standards/documentation-maintenance.md)

</details>
