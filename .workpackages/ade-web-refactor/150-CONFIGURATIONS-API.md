# 150-CONFIGURATIONS-API.md  
**ADE Web – Configurations, File Trees, Builds & Validation**

---

## 0. Purpose

This doc describes the **configuration**-related API surface used by the new ade‑web:

- Workspace configurations (list/read/create)
- Configuration versions
- Config file tree & file operations
- Validation
- Builds & build status

It complements:

- `100-CONFIG-BUILDER-EDITOR.md` – UX and layout for the editor.
- `020-ARCHITECTURE.md` – where config features live in the frontend.
- `050-RUN-STREAMING-SPEC.md` / `140-RUNS-AND-OUTPUTS.md` – how runs execute on a configuration.

---

## 1. Core Types (from OpenAPI)

### 1.1 Configuration listing & metadata

```ts
/**
 * ConfigurationRecord
 * @description Serialized configuration metadata.
 */
ConfigurationRecord: {
  id: string;                     // ULID
  workspace_id: string;           // ULID
  display_name: string;
  status: ConfigurationStatus;    // see below
  configuration_version: number;
  content_digest?: string | null;
  created_at: string;             // date-time
  updated_at: string;             // date-time
  activated_at?: string | null;
};

/**
 * ConfigurationStatus
 * @description Lifecycle states for workspace configuration packages.
 */
ConfigurationStatus: "draft" | "published" | "active" | "inactive";
````

Envelope for listing:

```ts
ConfigurationPage: {
  items: ConfigurationRecord[];
  page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
  total?: number | null;
};
```

**UI usage:**

* Config picker dropdown / list:

  * `display_name`, `status`, `configuration_version` as key info.
* Config detail header (within Config Builder):

  * Show status chip (Draft/Published/Active/Inactive).
  * Show current version number.

---

### 1.2 Configuration creation

```ts
/**
 * ConfigurationCreate
 * @description Payload for creating a configuration.
 */
ConfigurationCreate: {
  display_name: string;
  source: ConfigSourceTemplate | ConfigSourceClone;
};

/**
 * ConfigSourceClone
 * @description Reference to an existing workspace config.
 */
ConfigSourceClone: {
  type: "clone";
  configuration_id: string;
};

/**
 * ConfigSourceTemplate
 * @description Reference to a bundled template.
 */
ConfigSourceTemplate: {
  type: "template";
  template_id: string;
};
```

**UX:**

* “New configuration” dialog:

  * Name (maps to `display_name`).
  * Source:

    * Template (template list from backend or static).
    * Clone existing configuration.

---

### 1.3 Configuration versions

```ts
/**
 * ConfigVersionRecord
 * @description Serialized configuration version metadata.
 */
ConfigVersionRecord: {
  configuration_version_id: string;
  configuration_id: string;
  workspace_id: string;
  status: ConfigurationStatus;
  semver?: string | null;
  content_digest?: string | null;
  created_at: string;
  updated_at: string;
  activated_at?: string | null;
  deleted_at?: string | null;
};
```

Used by `GET /configurations/{id}/versions`.

UI:

* “Versions” tab in Config Builder:

  * Show list of versions, their status (published, active, etc.), semver tag, created/activated timestamps.

---

### 1.4 Config validation

```ts
/**
 * ConfigValidationIssue
 * @description Description of a validation issue found on disk.
 */
ConfigValidationIssue: {
  path: string;
  message: string;
};

/**
 * ConfigurationValidateResponse
 * @description Result of running validation.
 */
ConfigurationValidateResponse: {
  id: string;               // configuration id
  workspace_id: string;
  status: ConfigurationStatus;
  content_digest?: string | null;
  issues: ConfigValidationIssue[];
};
```

UI:

* “Validate” button in Config Builder:

  * Calls validate endpoint, then shows issues in a “Problems” panel.
  * Each `path` should be clickable to open the file at the relevant location (if possible).

---

### 1.5 File tree & files

```ts
/** FileCapabilities */
FileCapabilities: {
  editable: boolean;
  can_create: boolean;
  can_delete: boolean;
  can_rename: boolean;
};

/** FileEntry */
FileEntry: {
  path: string;
  name: string;
  parent: string;
  kind: "file" | "dir";
  depth: number;
  size?: number | null;
  mtime: string;          // date-time
  etag: string;
  content_type: string;
  has_children: boolean;
};

/** FileListing */
FileListing: {
  workspace_id: string;
  configuration_id: string;
  status: ConfigurationStatus;
  capabilities: FileCapabilities;
  root: string;
  prefix: string;
  depth: "0" | "1" | "infinity";
  generated_at: string;   // date-time
  fileset_hash: string;
  summary: FileListingSummary;
  limits: FileSizeLimits;
  count: number;
  next_token?: string | null;
  entries: FileEntry[];
};

/** FileListingSummary */
FileListingSummary: {
  files: number;
  directories: number;
};
```

(The `FileSizeLimits` type exists but is mainly relevant to upload limits; we treat it as informational.)

**UI usage (Config Builder file tree):**

* Use `FileListing.entries` to drive virtualized tree view (grouped by parent).
* Use `FileCapabilities` to enable/disable:

  * Create file/directory, delete, rename.
* `next_token` supports incremental listing for large trees; we can start with simple “no more pages” assumption and iterate later if needed.

---

### 1.6 Builds

```ts
/**
 * BuildCreateOptions
 * @description Options controlling build orchestration.
 */
BuildCreateOptions: {
  force: boolean;   // force rebuild even if fingerprints match
  wait: boolean;    // wait for in-progress builds before starting new
};

/**
 * BuildCreateRequest
 * @description Request body for POST /builds.
 */
BuildCreateRequest: {
  stream: boolean;
  options?: BuildCreateOptions;
};

/**
 * BuildResource
 * @description API representation of a build row.
 */
BuildResource: {
  id: string;
  object: "ade.build";
  workspace_id: string;
  configuration_id: string;
  status: "queued" | "building" | "active" | "failed" | "canceled";
  created: number;    // unix timestamp
  started?: number | null;
  finished?: number | null;
  exit_code?: number | null;
  summary?: string | null;
  error_message?: string | null;
};
```

UI:

* Build status chip in Config Builder header (or a small build history panel).
* Option to “Force rebuild” with `force: true`.

---

## 2. Configuration Endpoints

All are workspace-scoped: `/api/v1/workspaces/{workspace_id}/configurations...`.

### 2.1 List configurations

**Path:** `GET /api/v1/workspaces/{workspace_id}/configurations`
**Op:** `list_configurations_api_v1_workspaces__workspace_id__configurations_get`

Params:

```ts
query?: {
  page?: number;
  page_size?: number;
  include_total?: boolean;
};
path: { workspace_id: string };
```

Response: `ConfigurationPage`.

**Wrapper:**

```ts
listConfigurations(workspaceId, options?): Promise<ConfigurationPage>;
```

Used by:

* Workspace Home “Configurations” list.
* Config selector in Config Builder / Documents.

---

### 2.2 Create configuration

**Path:** `POST /api/v1/workspaces/{workspace_id}/configurations`
**Op:** `create_configuration_api_v1_workspaces__workspace_id__configurations_post`

Request body: `ConfigurationCreate`.

Response: `201: ConfigurationRecord`.

**Wrapper:**

```ts
createConfiguration(
  workspaceId: string,
  payload: ConfigurationCreate
): Promise<ConfigurationRecord>;
```

UX:

* “New configuration” dialog; after success, navigate directly to Config Builder for the new configuration.

---

### 2.3 Read configuration

**Path:** `GET /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}`
**Op:** `read_configuration_api_v1_workspaces__workspace_id__configurations__configuration_id__get`

Response: `ConfigurationRecord`.

**Wrapper:**

```ts
getConfiguration(workspaceId: string, configurationId: string): Promise<ConfigurationRecord>;
```

Used to drive header state + config metadata in Config Builder.

---

### 2.4 Activate / deactivate configuration

**Activate**

* Path: `POST /.../configurations/{configuration_id}/activate`
* Op: `activate_configuration_endpoint_api_v1_workspaces__workspace_id__configurations__configuration_id__activate_post`
* Request: optional `ConfigurationActivateRequest` (`ensure_build: boolean`)
* Response: updated `ConfigurationRecord`.

**Deactivate**

* Path: `POST /.../configurations/{configuration_id}/deactivate`
* Op: `deactivate_configuration_endpoint_api_v1_workspaces__workspace_id__configurations__configuration_id__deactivate_post`
* No request body.
* Response: updated `ConfigurationRecord`.

**UX:**

* Surface as **Publish & Activate** actions:

  * “Activate” might treat `ensure_build` as true if we want to guarantee a build.
* Deactivate might be behind a “Archive / Deactivate” action with warning.

---

### 2.5 Publish configuration draft

**Path:** `POST /.../configurations/{configuration_id}/publish`
**Op:** `publish_configuration_endpoint_api_v1_workspaces__workspace_id__configurations__configuration_id__publish_post`

* Likely no request body.
* Response: updated `ConfigurationRecord` or version data (see OpenAPI; treat as metadata update).

Frontend:

* “Publish” button in Config Builder once validation passes.

---

### 2.6 Validate configuration

**Path:** `POST /.../configurations/{configuration_id}/validate`
**Op:** `validate_configuration_api_v1_workspaces__workspace_id__configurations__configuration_id__validate_post`

* Response: `ConfigurationValidateResponse`.

**Wrapper:**

```ts
validateConfiguration(
  workspaceId: string,
  configurationId: string
): Promise<ConfigurationValidateResponse>;
```

UX:

* “Validate” triggers:

  * Show spinner.
  * Display `issues` in “Problems” pane (group by file path).
  * Link each issue path to open file; if line/column info is not present, just open file.

---

### 2.7 List configuration versions

**Path:** `GET /.../configurations/{configuration_id}/versions`
**Op:** `list_configuration_versions_endpoint_api_v1_workspaces__workspace_id__configurations__configuration_id__versions_get`

Response: `ConfigVersionRecord[]`.

**Wrapper:**

```ts
listConfigurationVersions(
  workspaceId: string,
  configurationId: string
): Promise<ConfigVersionRecord[]>;
```

UI:

* “Versions” tab showing table with semver, status, created, activated.

---

### 2.8 Export configuration

**Path:** `GET /.../configurations/{configuration_id}/export`
**Op:** `export_config_api_v1_workspaces__workspace_id__configurations__configuration_id__export_get`

Query:

```ts
query?: { format?: string };
```

Response:

* `200` with `"application/json": unknown` and/or other content types (likely a file archive).

Frontend:

* Treat as **file download**:

  * “Export configuration” button in Config Builder; uses blob or `window.location`.

---

### 2.9 List config files

**Path:** `GET /.../configurations/{configuration_id}/files`
**Op:** `list_config_files_api_v1_workspaces__workspace_id__configurations__configuration_id__files_get`

Query:

```ts
query?: {
  prefix?: string;
  depth?: "0" | "1" | "infinity";
  include?: string[] | null;
  exclude?: string[] | null;
  limit?: number;
  page_token?: string | null;
  sort?: "path" | "name" | "mtime" | "size";
  order?: "asc" | "desc";
};
```

Response: `FileListing`.

**Wrapper:**

```ts
listConfigFiles(
  workspaceId: string,
  configurationId: string,
  options?: {
    prefix?: string;
    depth?: "0" | "1" | "infinity";
    include?: string[];
    exclude?: string[];
    limit?: number;
    pageToken?: string | null;
    sort?: "path" | "name" | "mtime" | "size";
    order?: "asc" | "desc";
  }
): Promise<FileListing>;
```

UX:

* Initial render:

  * `prefix = ""`, `depth = "1"` for root-level listing.
* Tree navigation:

  * When expanding directories, adjust `prefix` & `depth`.
* For first version, we can assume single listing (`next_token` unused) and expand later if needed.

---

### 2.10 File CRUD

**Read file**

* Path: `GET /.../files/{file_path}`
* Op: `read_config_file_api_v1_workspaces__workspace_id__configurations__configuration_id__files__file_path__get`
* Response: likely plain text / JSON payload.

**Upsert file**

* Path: `PUT /.../files/{file_path}`
* Op: `upsert_config_file_api_v1_workspaces__workspace_id__configurations__configuration_id__files__file_path__put`
* Request body: file content (OpenAPI describes the actual shape; treat as text payload).
* Response: maybe updated FileEntry or success marker.

**Move/rename file**

* Path: `PATCH /.../files/{file_path}`
* Op: `move_config_file_api_v1_workspaces__workspace_id__configurations__configuration_id__files__file_path__patch`
* Request: rename/move options (OpenAPI contains details; we wrap with clear TS types).

**Delete file**

* Path: `DELETE /.../files/{file_path}`
* Op: `delete_config_file_api_v1_workspaces__workspace_id__configurations__configuration_id__files__file_path__delete`
* Response: `204`.

**Directories**

* Create dir:

  * `POST /.../directories/{directory_path}`
* Delete dir:

  * `DELETE /.../directories/{directory_path}`

UX:

* File tree:

  * New file / folder actions -> upsert/dir create.
  * Rename file -> PATCH.
  * Delete file / folder -> DELETE.
* Editor:

  * On save -> PUT file content.
  * Reconcile file tree (refresh listing or update in cache).

---

## 3. Frontend Architecture (Configs)

Under `features/configs/api`:

* `listConfigurations`
* `createConfiguration`
* `getConfiguration`
* `activateConfiguration`
* `deactivateConfiguration`
* `publishConfiguration`
* `validateConfiguration`
* `listConfigurationVersions`
* `exportConfiguration`
* `listConfigFiles`
* `readConfigFile`
* `upsertConfigFile`
* `moveConfigFile`
* `deleteConfigFile`
* `createConfigDirectory`
* `deleteConfigDirectory`

Under `features/configs/hooks`:

* `useConfigurationList(workspaceId)`
* `useConfiguration(workspaceId, configurationId)`
* `useConfigFiles(workspaceId, configurationId, prefix, depth)`
* `useConfigFileEditor(workspaceId, configurationId, path)` – encapsulates read/save logic.
* `useValidateConfiguration`, `usePublishConfiguration`, `useActivateConfiguration`

Config Builder (`100-CONFIG-BUILDER-EDITOR.md`) sits on top of these.

---

## 4. Definition of Done – Configs & Files

Configs are “done enough” when:

1. The new Config Builder can:

   * List configurations, open one, and show proper metadata.
   * Show a navigable file tree based on `FileListing`.
   * Read and save files via config file endpoints.
   * Run validation and surface issues in UI.
2. Activation/publish actions are wired to the actual endpoints.
3. All types come from `openapi.d.ts` via `schema/` re-exports.