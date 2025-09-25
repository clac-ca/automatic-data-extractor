# Configurations API – Route Additions

Design the configuration module as if we were shipping it for the first time. No compatibility constraints apply; only add the routes we actually need for a clean CRUD + activation flow.

## Resource Model
Each configuration is scoped to a workspace and document type.

Common fields:
- `id` (UUID)
- `workspace_id` (UUID)
- `document_type` (string)
- `version` (integer, monotonically increasing per document type)
- `title` (string)
- `payload` (JSON object)
- `is_active` (boolean)
- `activated_at` (datetime or null)
- `created_at` / `updated_at` (datetimes)

## Endpoint Matrix
| Method | Path | Purpose | Notes |
|--------|------|---------|-------|
| `GET` | `/workspaces/{workspace_id}/configurations` | List configurations in the workspace (filterable by `document_type`, `is_active`). | Serves as the canonical browse endpoint. |
| `POST` | `/workspaces/{workspace_id}/configurations` | Create a configuration for a document type. | Payload supplies `document_type`, `title`, `payload`, optional `set_active`. Auto-assign version. |
| `GET` | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Retrieve a single configuration. | Primary read endpoint. |
| `PUT` | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Replace a configuration’s metadata and payload. | Reject `document_type` or `version` changes; clients create a new configuration instead. |
| `PATCH` | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Partial update for title/payload flags. | Same validation rules as `PUT`. |
| `DELETE` | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Remove a configuration. | Hard delete; allowed because there are no legacy consumers. |
| `POST` | `/workspaces/{workspace_id}/configurations/{configuration_id}/activate` | Set the configuration active for its document type. | Deactivate any previously active configuration of the same document type. |
| `GET` | `/workspaces/{workspace_id}/configurations/active` | Fetch the currently active configuration for each document type. | Optional `document_type` query parameter to narrow to one type. |
| `GET` | `/workspaces/{workspace_id}/configurations/{configuration_id}/events` | View lifecycle events for a configuration. | Mirrors the existing event feed pattern across modules. |

## Request/Response Shapes (high-level)
- **Create / Replace (`POST`, `PUT`)**
  ```json
  {
    "document_type": "invoice",
    "title": "Invoice v3",
    "payload": { "steps": [...] },
    "set_active": true
  }
  ```
- **Partial Update (`PATCH`)** – send only the fields to modify (`title`, `payload`, `set_active`).
- **Activate (`POST .../activate`)** – empty body; activation driven by URL.

## Permissions
- `workspace:configurations:read` → all `GET` routes.
- `workspace:configurations:write` → `POST`, `PUT`, `PATCH`, `DELETE`, activation route.

These endpoints provide everything required for the agents to implement a clean configuration lifecycle without legacy baggage.
