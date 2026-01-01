# ADE API Route Inventory (Workpackage: ade-api-refactor)

Generated via:

```
ADE_LOGGING_LEVEL=CRITICAL PYTHONPATH=apps/ade-api/src python -m ade_api.scripts.api_routes --format text
```

Note: `ade routes` was not available in this environment, so the underlying module command was used.

## Before (pre-refactor)

```
/api/v1/auth/cookie/login
  POST   Auth:Cookie.Login  [status 200; public; fastapi_users.router.auth:get_auth_router.<locals>.login]

/api/v1/auth/cookie/logout
  POST   Auth:Cookie.Logout  [status 200; public; fastapi_users.router.auth:get_auth_router.<locals>.logout]

/api/v1/auth/jwt/login
  POST   Auth:Jwt.Login  [status 200; public; fastapi_users.router.auth:get_auth_router.<locals>.login]

/api/v1/auth/jwt/logout
  POST   Auth:Jwt.Logout  [status 200; public; fastapi_users.router.auth:get_auth_router.<locals>.logout]

/api/v1/auth/oidc/{provider}/authorize
  GET    Authorize Oidc  [status 200; public; ade_api.features.auth.oidc_router:authorize_oidc]

/api/v1/auth/oidc/{provider}/callback
  GET    Callback Oidc  [status 200; public; ade_api.features.auth.oidc_router:callback_oidc]

/api/v1/auth/providers
  GET    Return configured authentication providers  [status 200; public; ade_api.features.auth.router:create_auth_router.<locals>.list_auth_providers]

/api/v1/auth/register
  POST   Register:Register  [status 201; public; fastapi_users.router.register:get_register_router.<locals>.register]

/api/v1/auth/setup
  GET    Return setup status for the first admin user  [status 200; public; ade_api.features.auth.router:create_auth_router.<locals>.get_setup_status]
  POST   Create the first admin user and log them in  [status 204; public; ade_api.features.auth.router:create_auth_router.<locals>.complete_setup]

/api/v1/builds/{build_id}
  GET    Get Build Endpoint  [status 200; ade_api.features.builds.router:get_build_endpoint]

/api/v1/builds/{build_id}/events
  GET    List Build Events Endpoint  [status 200; ade_api.features.builds.router:list_build_events_endpoint]

/api/v1/builds/{build_id}/events/stream
  GET    Stream Build Events Endpoint  [status 200; ade_api.features.builds.router:stream_build_events_endpoint]

/api/v1/configurations/{configuration_id}/runs
  GET    List Configuration Runs Endpoint  [status 200; ade_api.features.runs.router:list_configuration_runs_endpoint]
  POST   Create Run Endpoint  [status 201; ade_api.features.runs.router:create_run_endpoint]

/api/v1/configurations/{configuration_id}/runs/batch
  POST   Create Runs Batch Endpoint  [status 201; ade_api.features.runs.router:create_runs_batch_endpoint]

/api/v1/health
  GET    Service health status  [status 200; public; ade_api.features.health.router:read_health]

/api/v1/me
  GET    Return the authenticated user's profile  [status 200; ade_api.features.me.router:get_me]

/api/v1/me/bootstrap
  GET    Bootstrap the session with profile, roles, permissions, and workspaces  [status 200; ade_api.features.me.router:get_me_bootstrap]

/api/v1/me/permissions
  GET    Return the caller's effective global and workspace permissions  [status 200; ade_api.features.me.router:get_me_permissions]

/api/v1/me/permissions/check
  POST   Check whether the caller has specific permissions  [status 200; ade_api.features.me.router:check_permissions]

/api/v1/meta/versions
  GET    Installed ADE versions  [status 200; ade_api.meta.router:read_versions]

/api/v1/rbac/permissions
  GET    List permissions  [status 200; ade_api.features.rbac.router:list_permissions]

/api/v1/rbac/roleAssignments
  GET    List role assignments (admin view)  [status 200; ade_api.features.rbac.router:list_assignments]

/api/v1/rbac/roles
  GET    List role definitions  [status 200; ade_api.features.rbac.router:list_roles]
  POST   Create a role  [status 201; ade_api.features.rbac.router:create_role]

/api/v1/rbac/roles/{role_id}
  GET    Retrieve a role definition  [status 200; ade_api.features.rbac.router:read_role]
  PATCH  Update an existing role  [status 200; ade_api.features.rbac.router:update_role]
  DELETE Delete a role  [status 204; ade_api.features.rbac.router:delete_role]

/api/v1/runs/{run_id}
  GET    Get Run Endpoint  [status 200; ade_api.features.runs.router:get_run_endpoint]

/api/v1/runs/{run_id}/columns
  GET    List Run Columns Endpoint  [status 200; ade_api.features.runs.router:list_run_columns_endpoint]

/api/v1/runs/{run_id}/events
  GET    Get Run Events Endpoint  [status 200; ade_api.features.runs.router:get_run_events_endpoint]

/api/v1/runs/{run_id}/events/download
  GET    Download run events (NDJSON log)  [status 200; ade_api.features.runs.router:download_run_events_file_endpoint]

/api/v1/runs/{run_id}/events/stream
  GET    Stream Run Events Endpoint  [status 200; ade_api.features.runs.router:stream_run_events_endpoint]

/api/v1/runs/{run_id}/fields
  GET    List Run Fields Endpoint  [status 200; ade_api.features.runs.router:list_run_fields_endpoint]

/api/v1/runs/{run_id}/input
  GET    Get run input metadata  [status 200; ade_api.features.runs.router:get_run_input_endpoint]

/api/v1/runs/{run_id}/input/download
  GET    Download run input file  [status 200; ade_api.features.runs.router:download_run_input_endpoint]

/api/v1/runs/{run_id}/metrics
  GET    Get Run Metrics Endpoint  [status 200; ade_api.features.runs.router:get_run_metrics_endpoint]

/api/v1/runs/{run_id}/output
  GET    Get run output metadata  [status 200; ade_api.features.runs.router:get_run_output_metadata_endpoint]

/api/v1/runs/{run_id}/output/download
  GET    Download run output file  [status 200; ade_api.features.runs.router:download_run_output_endpoint]

/api/v1/system/safeMode
  GET    Read ADE safe mode status  [status 200; ade_api.features.system_settings.router:read_safe_mode]
  PUT    Toggle ADE safe mode  [status 204; ade_api.features.system_settings.router:update_safe_mode]

/api/v1/users
  GET    List all users (administrator only)  [status 200; ade_api.features.users.router:list_users]

/api/v1/users/me/apiKeys
  GET    List API keys for the current user  [status 200; ade_api.features.api_keys.router:list_my_api_keys]
  POST   Create an API key for the current user  [status 201; ade_api.features.api_keys.router:create_my_api_key]

/api/v1/users/me/apiKeys/{api_key_id}
  DELETE Revoke one of the current user's API keys  [status 204; ade_api.features.api_keys.router:revoke_my_api_key]

/api/v1/users/{user_id}
  GET    Retrieve a user (administrator only)  [status 200; ade_api.features.users.router:get_user]
  PATCH  Update a user (administrator only)  [status 200; ade_api.features.users.router:update_user]

/api/v1/users/{user_id}/apiKeys
  GET    List API keys for a specific user (admin)  [status 200; ade_api.features.api_keys.router:list_user_api_keys]
  POST   Create an API key for a specific user (admin)  [status 201; ade_api.features.api_keys.router:create_user_api_key]

/api/v1/users/{user_id}/apiKeys/{api_key_id}
  DELETE Revoke an API key for a specific user (admin)  [status 204; ade_api.features.api_keys.router:revoke_user_api_key]

/api/v1/users/{user_id}/deactivate
  POST   Deactivate a user and revoke their API keys (administrator only)  [status 200; ade_api.features.users.router:deactivate_user]

/api/v1/users/{user_id}/roles
  GET    List global roles assigned to a user  [status 200; ade_api.features.rbac.router:list_user_roles]

/api/v1/users/{user_id}/roles/{role_id}
  PUT    Assign a global role to a user (idempotent)  [status 200; ade_api.features.rbac.router:assign_user_role]
  DELETE Remove a global role from a user  [status 204; ade_api.features.rbac.router:remove_user_role]

/api/v1/workspaces
  GET    List workspaces for the authenticated user  [status 200; ade_api.features.workspaces.router:list_workspaces]
  POST   Create a new workspace  [status 201; ade_api.features.workspaces.router:create_workspace]

/api/v1/workspaces/{workspace_id}
  GET    Retrieve workspace context by identifier  [status 200; ade_api.features.workspaces.router:read_workspace]
  PATCH  Update workspace metadata  [status 200; ade_api.features.workspaces.router:update_workspace]
  DELETE Delete a workspace  [status 204; ade_api.features.workspaces.router:delete_workspace]

/api/v1/workspaces/{workspace_id}/configurations
  GET    List configurations for a workspace  [status 200; ade_api.features.configs.endpoints.configurations:list_configurations]
  POST   Create a configuration from a template or clone  [status 201; ade_api.features.configs.endpoints.configurations:create_configuration]

/api/v1/workspaces/{workspace_id}/configurations/import
  POST   Create a configuration from an uploaded archive  [status 201; ade_api.features.configs.endpoints.configurations:import_configuration]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}
  GET    Retrieve configuration metadata  [status 200; ade_api.features.configs.endpoints.configurations:read_configuration]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/archive
  POST   Archive the active configuration  [status 200; ade_api.features.configs.endpoints.configurations:archive_configuration_endpoint]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds
  GET    List Builds Endpoint  [status 200; ade_api.features.builds.router:list_builds_endpoint]
  POST   Create Build Endpoint  [status 201; ade_api.features.builds.router:create_build_endpoint]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}
  PUT    Create Config Directory  [status 200]
  DELETE Delete Config Directory  [status 204]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/export
  GET    Export Config  [status 200; ade_api.features.configs.endpoints.configurations:export_config]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files
  GET    List editable files and directories  [status 200; ade_api.features.configs.endpoints.files:list_config_files]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}
  GET    Read Config File  [status 200]
  PUT    Upsert Config File  [status 200]
  PATCH  Rename or move a file  [status 200]
  DELETE Delete Config File  [status 204]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/import
  PUT    Replace a draft configuration from an uploaded archive  [status 200; ade_api.features.configs.endpoints.configurations:replace_configuration_from_archive]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/publish
  POST   Make a draft configuration active  [status 200; ade_api.features.configs.endpoints.configurations:publish_configuration_endpoint]

/api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate
  POST   Validate the configuration on disk  [status 200; ade_api.features.configs.endpoints.configurations:validate_configuration]

/api/v1/workspaces/{workspace_id}/default
  PUT    Mark a workspace as the caller's default  [status 204; ade_api.features.workspaces.router:set_default_workspace]

/api/v1/workspaces/{workspace_id}/documents
  GET    List documents  [status 200; ade_api.features.documents.router:list_documents]
  POST   Upload a document  [status 201; ade_api.features.documents.router:upload_document]

/api/v1/workspaces/{workspace_id}/documents/batch/archive
  POST   Archive multiple documents  [status 200; ade_api.features.documents.router:archive_documents_batch_endpoint]

/api/v1/workspaces/{workspace_id}/documents/batch/delete
  POST   Soft delete multiple documents  [status 200; ade_api.features.documents.router:delete_documents_batch]

/api/v1/workspaces/{workspace_id}/documents/batch/restore
  POST   Restore multiple documents from the archive  [status 200; ade_api.features.documents.router:restore_documents_batch_endpoint]

/api/v1/workspaces/{workspace_id}/documents/batch/tags
  POST   Update tags on multiple documents  [status 200; ade_api.features.documents.router:patch_document_tags_batch]

/api/v1/workspaces/{workspace_id}/documents/changes
  GET    List document changes  [status 200; ade_api.features.documents.router:list_document_changes]

/api/v1/workspaces/{workspace_id}/documents/changes/stream
  GET    Stream Document Changes  [status 200; ade_api.features.documents.router:stream_document_changes]

/api/v1/workspaces/{workspace_id}/documents/uploadSessions
  POST   Create a resumable upload session  [status 201; ade_api.features.documents.router:create_upload_session]

/api/v1/workspaces/{workspace_id}/documents/uploadSessions/{upload_session_id}
  GET    Get upload session status  [status 200; ade_api.features.documents.router:get_upload_session_status]
  PUT    Upload a byte range to a session  [status 202; ade_api.features.documents.router:upload_session_range]
  DELETE Cancel an upload session  [status 204; ade_api.features.documents.router:cancel_upload_session]

/api/v1/workspaces/{workspace_id}/documents/uploadSessions/{upload_session_id}/commit
  POST   Commit an upload session  [status 201; ade_api.features.documents.router:commit_upload_session]

/api/v1/workspaces/{workspace_id}/documents/{document_id}
  GET    Retrieve document metadata  [status 200; ade_api.features.documents.router:read_document]
  PATCH  Update document metadata or assignment  [status 200; ade_api.features.documents.router:update_document]
  DELETE Soft delete a document  [status 204; ade_api.features.documents.router:delete_document]

/api/v1/workspaces/{workspace_id}/documents/{document_id}/archive
  POST   Archive a document  [status 200; ade_api.features.documents.router:archive_document_endpoint]

/api/v1/workspaces/{workspace_id}/documents/{document_id}/download
  GET    Download a stored document  [status 200; ade_api.features.documents.router:download_document]

/api/v1/workspaces/{workspace_id}/documents/{document_id}/listRow
  GET    Retrieve document list row  [status 200; ade_api.features.documents.router:read_document_list_row]

/api/v1/workspaces/{workspace_id}/documents/{document_id}/restore
  POST   Restore a document from the archive  [status 200; ade_api.features.documents.router:restore_document_endpoint]

/api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets
  GET    List worksheets for a document  [status 200; ade_api.features.documents.router:list_document_sheets_endpoint]

/api/v1/workspaces/{workspace_id}/documents/{document_id}/tags
  PUT    Replace document tags  [status 200; ade_api.features.documents.router:replace_document_tags]
  PATCH  Update document tags  [status 200; ade_api.features.documents.router:patch_document_tags]

/api/v1/workspaces/{workspace_id}/members
  GET    List workspace members with their roles  [status 200; ade_api.features.workspaces.members:list_workspace_members]
  POST   Add a workspace member with roles  [status 201; ade_api.features.workspaces.members:add_workspace_member]

/api/v1/workspaces/{workspace_id}/members/{user_id}
  PUT    Replace workspace member roles  [status 200; ade_api.features.workspaces.members:update_workspace_member]
  DELETE Remove a workspace member  [status 204; ade_api.features.workspaces.members:remove_workspace_member]

/api/v1/workspaces/{workspace_id}/runs
  GET    List Workspace Runs Endpoint  [status 200; ade_api.features.runs.router:list_workspace_runs_endpoint]
  POST   Create Workspace Run Endpoint  [status 201; ade_api.features.runs.router:create_workspace_run_endpoint]

/api/v1/workspaces/{workspace_id}/runs/batch
  POST   Create Workspace Runs Batch Endpoint  [status 201; ade_api.features.runs.router:create_workspace_runs_batch_endpoint]

/api/v1/workspaces/{workspace_id}/tags
  GET    List document tags  [status 200; ade_api.features.documents.router:list_document_tags]
```

## After (post-refactor)

```
/api/v1/auth/cookie/login
  POST   Auth:Cookie.Login  [status 200; public; fastapi_users.router.auth:get_auth_router.<locals>.login]

/api/v1/auth/cookie/logout
  POST   Auth:Cookie.Logout  [status 200; fastapi_users.router.auth:get_auth_router.<locals>.logout]

/api/v1/auth/jwt/login
  POST   Auth:Jwt.Login  [status 200; public; fastapi_users.router.auth:get_auth_router.<locals>.login]

/api/v1/auth/jwt/logout
  POST   Auth:Jwt.Logout  [status 200; fastapi_users.router.auth:get_auth_router.<locals>.logout]

/api/v1/auth/oidc/{provider}/authorize
  GET    Authorize Oidc  [status 200; public; ade_api.features.auth.oidc_router:authorize_oidc]

/api/v1/auth/oidc/{provider}/callback
  GET    Callback Oidc  [status 200; public; ade_api.features.auth.oidc_router:callback_oidc]

/api/v1/auth/providers
  GET    Return configured authentication providers  [status 200; public; ade_api.features.auth.router:create_auth_router.<locals>.list_auth_providers]

/api/v1/auth/register
  POST   Register:Register  [status 201; public; fastapi_users.router.register:get_register_router.<locals>.register]

/api/v1/auth/setup
  GET    Return setup status for the first admin user  [status 200; public; ade_api.features.auth.router:create_auth_router.<locals>.get_setup_status]
  POST   Create the first admin user and log them in  [status 204; public; ade_api.features.auth.router:create_auth_router.<locals>.complete_setup]

/api/v1/builds/{buildId}
  GET    Get Build Endpoint  [status 200; ade_api.features.builds.router:get_build_endpoint]

/api/v1/builds/{buildId}/events
  GET    List Build Events Endpoint  [status 200; ade_api.features.builds.router:list_build_events_endpoint]

/api/v1/builds/{buildId}/events/stream
  GET    Stream Build Events Endpoint  [status 200; ade_api.features.builds.router:stream_build_events_endpoint]

/api/v1/configurations/{configurationId}/runs
  GET    List Configuration Runs Endpoint  [status 200; ade_api.features.runs.router:list_configuration_runs_endpoint]
  POST   Create Run Endpoint  [status 201; ade_api.features.runs.router:create_run_endpoint]

/api/v1/configurations/{configurationId}/runs/batch
  POST   Create Runs Batch Endpoint  [status 201; ade_api.features.runs.router:create_runs_batch_endpoint]

/api/v1/health
  GET    Service health status  [status 200; public; ade_api.features.health.router:read_health]

/api/v1/me
  GET    Return the authenticated user's profile  [status 200; ade_api.features.me.router:get_me]

/api/v1/me/bootstrap
  GET    Bootstrap the session with profile, roles, permissions, and workspaces  [status 200; ade_api.features.me.router:get_me_bootstrap]

/api/v1/me/permissions
  GET    Return the caller's effective global and workspace permissions  [status 200; ade_api.features.me.router:get_me_permissions]

/api/v1/me/permissions/check
  POST   Check whether the caller has specific permissions  [status 200; ade_api.features.me.router:check_permissions]

/api/v1/meta/versions
  GET    Installed ADE versions  [status 200; ade_api.meta.router:read_versions]

/api/v1/permissions
  GET    List permissions  [status 200; ade_api.features.rbac.router:list_permissions]

/api/v1/roleassignments
  GET    List role assignments (admin view)  [status 200; ade_api.features.rbac.router:list_assignments]

/api/v1/roles
  GET    List role definitions  [status 200; ade_api.features.rbac.router:list_roles]
  POST   Create a role  [status 201; ade_api.features.rbac.router:create_role]

/api/v1/roles/{roleId}
  GET    Retrieve a role definition  [status 200; ade_api.features.rbac.router:read_role]
  PATCH  Update an existing role  [status 200; ade_api.features.rbac.router:update_role]
  DELETE Delete a role  [status 204; ade_api.features.rbac.router:delete_role]

/api/v1/runs/{runId}
  GET    Get Run Endpoint  [status 200; ade_api.features.runs.router:get_run_endpoint]

/api/v1/runs/{runId}/columns
  GET    List Run Columns Endpoint  [status 200; ade_api.features.runs.router:list_run_columns_endpoint]

/api/v1/runs/{runId}/events
  GET    Get Run Events Endpoint  [status 200; ade_api.features.runs.router:get_run_events_endpoint]

/api/v1/runs/{runId}/events/download
  GET    Download run events (NDJSON log)  [status 200; ade_api.features.runs.router:download_run_events_file_endpoint]

/api/v1/runs/{runId}/events/stream
  GET    Stream Run Events Endpoint  [status 200; ade_api.features.runs.router:stream_run_events_endpoint]

/api/v1/runs/{runId}/fields
  GET    List Run Fields Endpoint  [status 200; ade_api.features.runs.router:list_run_fields_endpoint]

/api/v1/runs/{runId}/input
  GET    Get run input metadata  [status 200; ade_api.features.runs.router:get_run_input_endpoint]

/api/v1/runs/{runId}/input/download
  GET    Download run input file  [status 200; ade_api.features.runs.router:download_run_input_endpoint]

/api/v1/runs/{runId}/metrics
  GET    Get Run Metrics Endpoint  [status 200; ade_api.features.runs.router:get_run_metrics_endpoint]

/api/v1/runs/{runId}/output
  GET    Get run output metadata  [status 200; ade_api.features.runs.router:get_run_output_metadata_endpoint]

/api/v1/runs/{runId}/output/download
  GET    Download run output file  [status 200; ade_api.features.runs.router:download_run_output_endpoint]

/api/v1/runs/{runId}/output/preview
  GET    Preview run output workbook  [status 200; ade_api.features.runs.router:preview_run_output_endpoint]

/api/v1/system/safemode
  GET    Read ADE safe mode status  [status 200; ade_api.features.system_settings.router:read_safe_mode]
  PUT    Toggle ADE safe mode  [status 204; ade_api.features.system_settings.router:update_safe_mode]

/api/v1/users
  GET    List all users (administrator only)  [status 200; ade_api.features.users.router:list_users]

/api/v1/users/me/apikeys
  GET    List API keys for the current user  [status 200; ade_api.features.api_keys.router:list_my_api_keys]
  POST   Create an API key for the current user  [status 201; ade_api.features.api_keys.router:create_my_api_key]

/api/v1/users/me/apikeys/{apiKeyId}
  DELETE Revoke one of the current user's API keys  [status 204; ade_api.features.api_keys.router:revoke_my_api_key]

/api/v1/users/{userId}
  GET    Retrieve a user (administrator only)  [status 200; ade_api.features.users.router:get_user]
  PATCH  Update a user (administrator only)  [status 200; ade_api.features.users.router:update_user]

/api/v1/users/{userId}/apikeys
  GET    List API keys for a specific user (admin)  [status 200; ade_api.features.api_keys.router:list_user_api_keys]
  POST   Create an API key for a specific user (admin)  [status 201; ade_api.features.api_keys.router:create_user_api_key]

/api/v1/users/{userId}/apikeys/{apiKeyId}
  DELETE Revoke an API key for a specific user (admin)  [status 204; ade_api.features.api_keys.router:revoke_user_api_key]

/api/v1/users/{userId}/deactivate
  POST   Deactivate a user and revoke their API keys (administrator only)  [status 200; ade_api.features.users.router:deactivate_user]

/api/v1/users/{userId}/roles
  GET    List global roles assigned to a user  [status 200; ade_api.features.rbac.router:list_user_roles]

/api/v1/users/{userId}/roles/{roleId}
  PUT    Assign a global role to a user (idempotent)  [status 200; ade_api.features.rbac.router:assign_user_role]
  DELETE Remove a global role from a user  [status 204; ade_api.features.rbac.router:remove_user_role]

/api/v1/workspaces
  GET    List workspaces for the authenticated user  [status 200; ade_api.features.workspaces.router:list_workspaces]
  POST   Create a new workspace  [status 201; ade_api.features.workspaces.router:create_workspace]

/api/v1/workspaces/{workspaceId}
  GET    Retrieve workspace context by identifier  [status 200; ade_api.features.workspaces.router:read_workspace]
  PATCH  Update workspace metadata  [status 200; ade_api.features.workspaces.router:update_workspace]
  DELETE Delete a workspace  [status 204; ade_api.features.workspaces.router:delete_workspace]

/api/v1/workspaces/{workspaceId}/configurations
  GET    List configurations for a workspace  [status 200; ade_api.features.configs.endpoints.configurations:list_configurations]
  POST   Create a configuration from a template or clone  [status 201; ade_api.features.configs.endpoints.configurations:create_configuration]

/api/v1/workspaces/{workspaceId}/configurations/import
  POST   Create a configuration from an uploaded archive  [status 201; ade_api.features.configs.endpoints.configurations:import_configuration]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}
  GET    Retrieve configuration metadata  [status 200; ade_api.features.configs.endpoints.configurations:read_configuration]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/archive
  POST   Archive the active configuration  [status 200; ade_api.features.configs.endpoints.configurations:archive_configuration_endpoint]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/builds
  GET    List Builds Endpoint  [status 200; ade_api.features.builds.router:list_builds_endpoint]
  POST   Create Build Endpoint  [status 201; ade_api.features.builds.router:create_build_endpoint]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}
  PUT    Create Config Directory  [status 200]
  DELETE Delete Config Directory  [status 204]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/export
  GET    Export Config  [status 200; ade_api.features.configs.endpoints.configurations:export_config]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files
  GET    List editable files and directories  [status 200; ade_api.features.configs.endpoints.files:list_config_files]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}
  GET    Read Config File  [status 200]
  PUT    Upsert Config File  [status 200]
  PATCH  Rename or move a file  [status 200]
  DELETE Delete Config File  [status 204]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/import
  PUT    Replace a draft configuration from an uploaded archive  [status 200; ade_api.features.configs.endpoints.configurations:replace_configuration_from_archive]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/publish
  POST   Make a draft configuration active  [status 200; ade_api.features.configs.endpoints.configurations:publish_configuration_endpoint]

/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/validate
  POST   Validate the configuration on disk  [status 200; ade_api.features.configs.endpoints.configurations:validate_configuration]

/api/v1/workspaces/{workspaceId}/default
  PUT    Mark a workspace as the caller's default  [status 204; ade_api.features.workspaces.router:set_default_workspace]

/api/v1/workspaces/{workspaceId}/documents
  GET    List documents  [status 200; ade_api.features.documents.router:list_documents]
  POST   Upload a document  [status 201; ade_api.features.documents.router:upload_document]

/api/v1/workspaces/{workspaceId}/documents/batch/archive
  POST   Archive multiple documents  [status 200; ade_api.features.documents.router:archive_documents_batch_endpoint]

/api/v1/workspaces/{workspaceId}/documents/batch/delete
  POST   Soft delete multiple documents  [status 200; ade_api.features.documents.router:delete_documents_batch]

/api/v1/workspaces/{workspaceId}/documents/batch/restore
  POST   Restore multiple documents from the archive  [status 200; ade_api.features.documents.router:restore_documents_batch_endpoint]

/api/v1/workspaces/{workspaceId}/documents/batch/tags
  POST   Update tags on multiple documents  [status 200; ade_api.features.documents.router:patch_document_tags_batch]

/api/v1/workspaces/{workspaceId}/documents/changes
  GET    List document changes  [status 200; ade_api.features.documents.router:list_document_changes]

/api/v1/workspaces/{workspaceId}/documents/changes/stream
  GET    Stream Document Changes  [status 200; ade_api.features.documents.router:stream_document_changes]

/api/v1/workspaces/{workspaceId}/documents/tags
  GET    List document tags  [status 200; ade_api.features.documents.router:list_document_tags]

/api/v1/workspaces/{workspaceId}/documents/uploadsessions
  POST   Create a resumable upload session  [status 201; ade_api.features.documents.router:create_upload_session]

/api/v1/workspaces/{workspaceId}/documents/uploadsessions/{uploadSessionId}
  GET    Get upload session status  [status 200; ade_api.features.documents.router:get_upload_session_status]
  PUT    Upload a byte range to a session  [status 202; ade_api.features.documents.router:upload_session_range]
  DELETE Cancel an upload session  [status 204; ade_api.features.documents.router:cancel_upload_session]

/api/v1/workspaces/{workspaceId}/documents/uploadsessions/{uploadSessionId}/commit
  POST   Commit an upload session  [status 201; ade_api.features.documents.router:commit_upload_session]

/api/v1/workspaces/{workspaceId}/documents/{documentId}
  GET    Retrieve document metadata  [status 200; ade_api.features.documents.router:read_document]
  PATCH  Update document metadata or assignment  [status 200; ade_api.features.documents.router:update_document]
  DELETE Soft delete a document  [status 204; ade_api.features.documents.router:delete_document]

/api/v1/workspaces/{workspaceId}/documents/{documentId}/archive
  POST   Archive a document  [status 200; ade_api.features.documents.router:archive_document_endpoint]

/api/v1/workspaces/{workspaceId}/documents/{documentId}/download
  GET    Download a stored document  [status 200; ade_api.features.documents.router:download_document]

/api/v1/workspaces/{workspaceId}/documents/{documentId}/listrow
  GET    Retrieve document list row  [status 200; ade_api.features.documents.router:read_document_list_row]

/api/v1/workspaces/{workspaceId}/documents/{documentId}/preview
  GET    Preview a document workbook  [status 200; ade_api.features.documents.router:preview_document]

/api/v1/workspaces/{workspaceId}/documents/{documentId}/restore
  POST   Restore a document from the archive  [status 200; ade_api.features.documents.router:restore_document_endpoint]

/api/v1/workspaces/{workspaceId}/documents/{documentId}/sheets
  GET    List worksheets for a document  [status 200; ade_api.features.documents.router:list_document_sheets_endpoint]

/api/v1/workspaces/{workspaceId}/documents/{documentId}/tags
  PUT    Replace document tags  [status 200; ade_api.features.documents.router:replace_document_tags]
  PATCH  Update document tags  [status 200; ade_api.features.documents.router:patch_document_tags]

/api/v1/workspaces/{workspaceId}/members
  GET    List workspace members with their roles  [status 200; ade_api.features.workspaces.members:list_workspace_members]
  POST   Add a workspace member with roles  [status 201; ade_api.features.workspaces.members:add_workspace_member]

/api/v1/workspaces/{workspaceId}/members/{userId}
  PUT    Replace workspace member roles  [status 200; ade_api.features.workspaces.members:update_workspace_member]
  DELETE Remove a workspace member  [status 204; ade_api.features.workspaces.members:remove_workspace_member]

/api/v1/workspaces/{workspaceId}/runs
  GET    List Workspace Runs Endpoint  [status 200; ade_api.features.runs.router:list_workspace_runs_endpoint]
  POST   Create Workspace Run Endpoint  [status 201; ade_api.features.runs.router:create_workspace_run_endpoint]

/api/v1/workspaces/{workspaceId}/runs/batch
  POST   Create Workspace Runs Batch Endpoint  [status 201; ade_api.features.runs.router:create_workspace_runs_batch_endpoint]
```
