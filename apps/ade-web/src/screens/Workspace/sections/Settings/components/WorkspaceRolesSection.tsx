import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";
import {
  useCreateWorkspaceRoleMutation,
  useDeleteWorkspaceRoleMutation,
  usePermissionsQuery,
  useUpdateWorkspaceRoleMutation,
  useWorkspaceRolesQuery,
} from "../hooks/useWorkspaceRoles";
import type { RoleDefinition, PermissionDefinition } from "@features/Workspace/api/workspaces-api";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { Input } from "@ui/Input";

const roleFormSchema = z.object({
  name: z.string().min(1, "Role name is required.").max(150, "Keep the name under 150 characters."),
  slug: z
    .string()
    .max(100, "Keep the slug under 100 characters.")
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase letters, numbers, and dashes.")
    .optional()
    .or(z.literal("")),
  description: z.string().max(500, "Keep the description concise.").optional().or(z.literal("")),
  permissions: z.array(z.string()),
});

type RoleFormValues = z.infer<typeof roleFormSchema>;

export function WorkspaceRolesSection() {
  const { workspace, hasPermission } = useWorkspaceContext();
  const canManageRoles = hasPermission("workspace.roles.manage");

  const rolesQuery = useWorkspaceRolesQuery(workspace.id);
  const permissionsQuery = usePermissionsQuery();

  const createRole = useCreateWorkspaceRoleMutation(workspace.id);
  const updateRole = useUpdateWorkspaceRoleMutation(workspace.id);
  const deleteRole = useDeleteWorkspaceRoleMutation(workspace.id);

  const [showCreate, setShowCreate] = useState(false);
  const [editingRoleId, setEditingRoleId] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  const permissions = useMemo(() => {
    return (permissionsQuery.data?.items ?? []).filter((permission) => permission.scope_type === "workspace");
  }, [permissionsQuery.data]);

  const permissionLookup = useMemo(() => {
    const map = new Map<string, PermissionDefinition>();
    for (const permission of permissions) {
      map.set(permission.key, permission);
    }
    return map;
  }, [permissions]);

  const roles = rolesQuery.data?.items ?? [];

  const openCreateForm = () => {
    setFeedbackMessage(null);
    setShowCreate(true);
    setEditingRoleId(null);
  };

  const closeCreateForm = () => {
    setShowCreate(false);
  };

  const startEditingRole = (role: RoleDefinition) => {
    setFeedbackMessage(null);
    setEditingRoleId(role.id);
    setShowCreate(false);
  };

  const cancelEditing = () => {
    setEditingRoleId(null);
  };

  const handleDeleteRole = (role: RoleDefinition) => {
    if (!canManageRoles || role.is_system || !role.is_editable) {
      return;
    }
    const confirmed = window.confirm(`Delete the role "${role.name}"? This action cannot be undone.`);
    if (!confirmed) {
      return;
    }
    setFeedbackMessage(null);
    deleteRole.mutate(role.id, {
      onSuccess: () => {
        setFeedbackMessage({ tone: "success", message: "Role deleted." });
      },
      onError: (error) => {
        const message = error instanceof Error ? error.message : "Unable to delete role.";
        setFeedbackMessage({ tone: "danger", message });
      },
    });
  };

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {rolesQuery.isError ? (
        <Alert tone="danger">
          {rolesQuery.error instanceof Error ? rolesQuery.error.message : "Unable to load workspace roles."}
        </Alert>
      ) : null}
      {permissionsQuery.isError ? (
        <Alert tone="warning">
          {permissionsQuery.error instanceof Error ? permissionsQuery.error.message : "Unable to load permission catalog."}
        </Alert>
      ) : null}

      {canManageRoles ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Create role</h2>
              <p className="text-sm text-slate-500">Compose a custom role by selecting workspace permissions.</p>
            </div>
            <Button
              type="button"
              variant={showCreate ? "ghost" : "primary"}
              onClick={() => (showCreate ? closeCreateForm() : openCreateForm())}
            >
              {showCreate ? "Hide form" : "New role"}
            </Button>
          </div>

          {showCreate ? (
            <div className="mt-4">
              <WorkspaceRoleForm
                key="create-role"
                availablePermissions={permissions}
                allowSlugEdit
                onCancel={closeCreateForm}
                onSubmit={(values) => {
                  setFeedbackMessage(null);
                  createRole.mutate(
                    {
                      name: values.name.trim(),
                      slug: values.slug ? values.slug.trim() : undefined,
                      description: values.description?.trim() ? values.description.trim() : undefined,
                      permissions: values.permissions,
                    },
                    {
                      onSuccess: () => {
                        setFeedbackMessage({ tone: "success", message: "Role created." });
                        closeCreateForm();
                      },
                      onError: (error) => {
                        const message = error instanceof Error ? error.message : "Unable to create role.";
                        setFeedbackMessage({ tone: "danger", message });
                      },
                    },
                  );
                }}
                isSubmitting={createRole.isPending}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Workspace roles</h2>
            <p className="text-sm text-slate-500">
              {rolesQuery.isLoading ? "Loading roles…" : `${roles.length} role${roles.length === 1 ? "" : "s"}`}
            </p>
          </div>
        </header>

        {rolesQuery.isLoading ? (
          <p className="text-sm text-slate-600">Loading roles…</p>
        ) : roles.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            No workspace roles yet. Create one to tailor permissions for your team.
          </p>
        ) : (
          <ul className="space-y-4" role="list">
            {roles.map((role) => {
              const isEditing = editingRoleId === role.id;
              const permissionLabels = role.permissions.map(
                (permission) => permissionLookup.get(permission)?.label ?? permission,
              );
              return (
                <li key={role.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-semibold text-slate-900">{role.name}</h3>
                        {role.is_system ? (
                          <span className="inline-flex items-center rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                            System
                          </span>
                        ) : null}
                        {!role.is_editable ? (
                          <span className="inline-flex items-center rounded-full bg-warning-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-warning-700">
                            Locked
                          </span>
                        ) : null}
                      </div>
                      <p className="text-sm text-slate-500">Slug: {role.slug}</p>
                      {role.description ? (
                        <p className="text-sm text-slate-600">{role.description}</p>
                      ) : null}
                    </div>
                    {canManageRoles && role.is_editable ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => (isEditing ? cancelEditing() : startEditingRole(role))}
                          disabled={updateRole.isPending || deleteRole.isPending}
                        >
                          {isEditing ? "Cancel" : "Edit"}
                        </Button>
                        {!role.is_system ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteRole(role)}
                            disabled={deleteRole.isPending || role.is_system || !role.is_editable}
                          >
                            Delete
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {permissionLabels.length > 0 ? (
                      permissionLabels.map((label) => (
                        <span
                          key={`${role.id}-${label}`}
                          className="inline-flex items-center rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm"
                        >
                          {label}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">No permissions assigned.</span>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="mt-4">
                      <WorkspaceRoleForm
                        key={role.id}
                        availablePermissions={permissions}
                        initialValues={{
                          name: role.name,
                          slug: role.slug,
                          description: role.description ?? "",
                          permissions: role.permissions,
                        }}
                        allowSlugEdit={false}
                        onCancel={cancelEditing}
                        onSubmit={(values) => {
                          setFeedbackMessage(null);
                          updateRole.mutate(
                            {
                              roleId: role.id,
                              payload: {
                                name: values.name.trim(),
                                description: values.description?.trim() ? values.description.trim() : undefined,
                                permissions: values.permissions,
                              },
                            },
                            {
                              onSuccess: () => {
                                setFeedbackMessage({ tone: "success", message: "Role updated." });
                                cancelEditing();
                              },
                              onError: (error) => {
                                const message =
                                  error instanceof Error ? error.message : "Unable to update role.";
                                setFeedbackMessage({ tone: "danger", message });
                              },
                            },
                          );
                        }}
                        isSubmitting={updateRole.isPending}
                      />
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}


interface WorkspaceRoleFormProps {
  readonly availablePermissions: readonly PermissionDefinition[];
  readonly initialValues?: RoleFormValues;
  readonly onSubmit: (values: RoleFormValues) => void;
  readonly onCancel?: () => void;
  readonly isSubmitting: boolean;
  readonly allowSlugEdit?: boolean;
}

function WorkspaceRoleForm({
  availablePermissions,
  initialValues,
  onSubmit,
  onCancel,
  isSubmitting,
  allowSlugEdit = true,
}: WorkspaceRoleFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
    reset,
  } = useForm<RoleFormValues, undefined, RoleFormValues>({
    resolver: zodResolver(roleFormSchema),
    defaultValues: initialValues ?? {
      name: "",
      slug: "",
      description: "",
      permissions: [],
    },
  });

  useEffect(() => {
    if (initialValues) {
      reset(initialValues);
    }
  }, [initialValues, reset]);

  const selectedPermissions = watch("permissions");

  const togglePermission = (permissionKey: string, selected: boolean) => {
    setValue(
      "permissions",
      selected
        ? Array.from(new Set([...(selectedPermissions ?? []), permissionKey]))
        : (selectedPermissions ?? []).filter((key) => key !== permissionKey),
    );
  };

  const submit = handleSubmit((values) => {
    const payload: RoleFormValues = {
      name: values.name.trim(),
      slug: allowSlugEdit ? values.slug?.trim() ?? "" : initialValues?.slug ?? "",
      description: values.description?.trim() ?? "",
      permissions: values.permissions ?? [],
    };
    onSubmit(payload);
  });

  return (
    <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-4" onSubmit={submit} noValidate>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm font-medium text-slate-700">
          Role name
          <Input
            {...register("name")}
            placeholder="Data reviewer"
            invalid={Boolean(errors.name)}
            disabled={isSubmitting}
          />
          {errors.name ? (
            <span className="block text-xs font-semibold text-danger-600">{errors.name.message}</span>
          ) : null}
        </label>
        {allowSlugEdit ? (
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Role slug
            <Input
              {...register("slug")}
              placeholder="data-reviewer"
              invalid={Boolean(errors.slug)}
              disabled={isSubmitting}
            />
            <span className="block text-xs text-slate-500">Optional. Leave blank to auto-generate from the name.</span>
            {errors.slug ? (
              <span className="block text-xs font-semibold text-danger-600">{errors.slug.message}</span>
            ) : null}
          </label>
        ) : null}
      </div>

      <label className="space-y-2 text-sm font-medium text-slate-700">
        Description
        <Input
          {...register("description")}
          placeholder="What does this role control?"
          invalid={Boolean(errors.description)}
          disabled={isSubmitting}
        />
        {errors.description ? (
          <span className="block text-xs font-semibold text-danger-600">{errors.description.message}</span>
        ) : null}
      </label>

      <fieldset className="space-y-3">
        <legend className="text-sm font-semibold text-slate-700">Permissions</legend>
        <div className="flex flex-wrap gap-2">
          {availablePermissions.length === 0 ? (
            <p className="text-xs text-slate-500">No workspace permissions available.</p>
          ) : (
            availablePermissions.map((permission) => (
              <label
                key={permission.key}
                className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
              >
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300"
                  checked={selectedPermissions?.includes(permission.key) ?? false}
                  onChange={(event) => togglePermission(permission.key, event.target.checked)}
                  disabled={isSubmitting}
                />
                <span>
                  <span className="block font-semibold">{permission.label}</span>
                  <span className="block text-xs text-slate-500">{permission.description}</span>
                </span>
              </label>
            ))
          )}
        </div>
      </fieldset>

      <div className="flex justify-end gap-2">
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" isLoading={isSubmitting}>
          Save role
        </Button>
      </div>
    </form>
  );
}
