# Workspace API Route Rewrite

Design a clean workspace administration API under the `/workspaces` namespace. The routes below assume the existing FastAPI conventions in this project (async endpoints, Pydantic schemas, UUID identifiers).

## Roles & Authorization Expectations
- **Global admin** – Can create workspaces and perform any workspace operation across the installation.
- **Workspace owner** – Full control over their workspace (metadata, membership, deletion, integrations, defaults, etc.).
- **Workspace member** – Can upload documents and collaborate inside the workspace but cannot change configurations, settings, or membership.

## Workspace Collection
| Method | Path | Description | Authorization | Request Body | Response |
| --- | --- | --- | --- | --- | --- |
| POST | `/workspaces` | Create a new workspace and optionally assign an initial owner | Global admin | `{ "name": str, "slug?": str, "owner_user_id?": UUID }` | Workspace profile |
| GET | `/workspaces` | List workspaces visible to the caller (global admins see all, others see memberships) | Authenticated user | – | `[Workspace profile]` |

## Workspace Resource
| Method | Path | Description | Authorization | Request Body | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/workspaces/{workspace_id}` | Retrieve workspace details/context | Workspace member or global admin | – | Workspace context |
| PATCH | `/workspaces/{workspace_id}` | Update workspace metadata (name, slug, settings) | Workspace owner or global admin | `{ "name?": str, "slug?": str, "settings?": dict }` | Workspace profile |
| DELETE | `/workspaces/{workspace_id}` | Permanently remove the workspace and its data | Workspace owner or global admin | – | `{ "status": "deleted" }` |

## Workspace Membership Collection
| Method | Path | Description | Authorization | Request Body | Response |
| --- | --- | --- | --- | --- | --- |
| GET | `/workspaces/{workspace_id}/members` | List memberships within the workspace | Workspace member or global admin | Query params for pagination/filtering | `[Workspace member]` |
| POST | `/workspaces/{workspace_id}/members` | Add or invite a user to the workspace with a role | Workspace owner or global admin | `{ "user_id": UUID, "role": Literal["owner","member"] }` | Workspace member |

## Workspace Membership Resource
| Method | Path | Description | Authorization | Request Body | Response |
| --- | --- | --- | --- | --- | --- |
| PATCH | `/workspaces/{workspace_id}/members/{membership_id}` | Update a member's role | Workspace owner or global admin | `{ "role": Literal["owner","member"] }` | Workspace member |
| DELETE | `/workspaces/{workspace_id}/members/{membership_id}` | Remove a user from the workspace | Workspace owner or global admin | – | `{ "status": "removed" }` |

## Default Workspace Convenience Route
| Method | Path | Description | Authorization | Request Body | Response |
| --- | --- | --- | --- | --- | --- |
| POST | `/workspaces/{workspace_id}/default` | Mark the workspace as the caller's default selection | Workspace member | – | `{ "workspace_id": UUID, "is_default": true }` |

## Notes
- All identifiers are UUIDs and responses use the existing schema shapes (`Workspace profile`, `Workspace context`, `Workspace member`).
- Auditing, notifications, and background jobs (e.g., cascading deletes) should be handled by service layers; routes simply orchestrate the request/response contracts above.
