# Configurations API – clean-slate routes

We are starting fresh: document only the routes the service must expose. Implementation details, payload structure, and storage decisions are left to the agents.

## Routes to add

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| `GET` | `/workspaces/{workspace_id}/configurations` | Browse configurations for the workspace. | Support optional filters via query params: `document_type`, `is_active`. |
| `POST` | `/workspaces/{workspace_id}/configurations` | Create a configuration record. | Server is responsible for versioning and default flags. |
| `GET` | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Fetch a specific configuration. | Straightforward read; no expansion or embedding required. |
| `PUT` | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Replace a configuration’s mutable fields. | Use for full updates; reject attempts to move across document types. |
| `DELETE` | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Delete a configuration. | Hard delete is acceptable because there are no legacy consumers. |
| `POST` | `/workspaces/{workspace_id}/configurations/{configuration_id}/activate` | Mark the configuration as active for its document type. | Activation should automatically deactivate any previously active configuration for the same document type. |
| `GET` | `/workspaces/{workspace_id}/configurations/active` | Return the current active configuration per document type. | Accept an optional `document_type` filter to focus on a single type. |

## Permissions

- `workspace:configurations:read` → required for any `GET` route.
- `workspace:configurations:write` → required for the `POST`, `PUT`, `DELETE`, and activation routes.

That’s the entire surface area we need for launch; everything else can evolve once we have real usage data.
