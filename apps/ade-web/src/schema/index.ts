// Curated, app-facing types re-exported from the generated OpenAPI definitions.
// Prefer importing from this module instead of referencing the raw generated file.
import type {
  components as GeneratedComponents,
  paths as GeneratedPaths,
  operations as GeneratedOperations,
} from "@generated-types/openapi";

// Base OpenAPI maps. Useful when you need to index into components or paths directly.
export type components = GeneratedComponents;
export type paths = GeneratedPaths;
export type operations = GeneratedOperations;

// Frequently used schema fragments. Extend this list as new app-level contracts emerge.
export type AuthLoginRequest = GeneratedComponents["schemas"]["AuthLoginRequest"];
export type AuthRefreshRequest = GeneratedComponents["schemas"]["AuthRefreshRequest"];
export type AuthTokensResponse = GeneratedComponents["schemas"]["AuthTokensResponse"];
export type AuthSetupStatus = GeneratedComponents["schemas"]["AuthSetupStatusResponse"];
export type AuthSetupRequest = GeneratedComponents["schemas"]["AuthSetupRequest"];
export type AuthProviderListResponse = GeneratedComponents["schemas"]["AuthProviderListResponse"];
export type MeContext = GeneratedComponents["schemas"]["MeContext"];
export type MeProfile = GeneratedComponents["schemas"]["MeProfile"];
export type User = GeneratedComponents["schemas"]["UserOut"];
export type UserPage = GeneratedComponents["schemas"]["UserPage"];
export type RunResource = GeneratedComponents["schemas"]["RunResource"];
export type RunStatus = RunResource["status"];
export type RunCreateOptions = GeneratedComponents["schemas"]["RunCreateOptions"];
export type { RunSummaryV1 } from "./runSummary";

// RBAC and workspace types
export type ScopeType = GeneratedComponents["schemas"]["ScopeType"];
export type RoleOut = GeneratedComponents["schemas"]["RoleOut"];
export type RolePage = GeneratedComponents["schemas"]["RolePage"];
export type RoleCreate = GeneratedComponents["schemas"]["RoleCreate"];
export type RoleUpdate = GeneratedComponents["schemas"]["RoleUpdate"];
export type PermissionOut = GeneratedComponents["schemas"]["PermissionOut"];
export type PermissionPage = GeneratedComponents["schemas"]["PermissionPage"];
export type WorkspaceOut = GeneratedComponents["schemas"]["WorkspaceOut"];
export type WorkspacePage = GeneratedComponents["schemas"]["WorkspacePage"];
export type WorkspaceCreate = GeneratedComponents["schemas"]["WorkspaceCreate"];
export type WorkspaceUpdate = GeneratedComponents["schemas"]["WorkspaceUpdate"];
export type WorkspaceMemberOut = GeneratedComponents["schemas"]["WorkspaceMemberOut"];
export type WorkspaceMemberPage = GeneratedComponents["schemas"]["WorkspaceMemberPage"];
export type WorkspaceMemberCreate = GeneratedComponents["schemas"]["WorkspaceMemberCreate"];
export type WorkspaceMemberUpdate = GeneratedComponents["schemas"]["WorkspaceMemberUpdate"];

// API key types
export type ApiKeySummary = GeneratedComponents["schemas"]["ApiKeySummary"];
export type ApiKeyPage = GeneratedComponents["schemas"]["ApiKeyPage"];
export type ApiKeyCreateRequest = GeneratedComponents["schemas"]["ApiKeyCreateRequest"];
export type ApiKeyIssueRequest = GeneratedComponents["schemas"]["ApiKeyIssueRequest"];
export type ApiKeyCreateResponse = GeneratedComponents["schemas"]["ApiKeyCreateResponse"];
