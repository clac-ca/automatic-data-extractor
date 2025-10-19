export interface PermissionDefinition {
  key: string;
  resource: string;
  action: string;
  scope_type: "global" | "workspace";
  label: string;
  description: string;
}

export interface RoleDefinition {
  role_id: string;
  slug: string;
  name: string;
  description: string | null;
  scope_type: "global" | "workspace";
  scope_id: string | null;
  permissions: string[];
  built_in: boolean;
  editable: boolean;
}

export interface RoleCreatePayload {
  name: string;
  slug?: string | null;
  description?: string | null;
  permissions: string[];
}

export interface RoleUpdatePayload {
  name: string;
  description?: string | null;
  permissions: string[];
}
