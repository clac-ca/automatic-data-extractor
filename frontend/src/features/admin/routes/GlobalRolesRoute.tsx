import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../../shared/api/client";
import type { PermissionDefinition, RoleDefinition } from "../../../shared/api/types";
import { useGlobalRolesQuery } from "../hooks/useGlobalRolesQuery";
import { usePermissionsQuery } from "../hooks/usePermissionsQuery";
import {
  useCreateGlobalRoleMutation,
  useDeleteRoleMutation,
  useUpdateRoleMutation,
} from "../hooks/useRoleMutations";

export function GlobalRolesRoute() {
  const rolesQuery = useGlobalRolesQuery();
  const permissionsQuery = usePermissionsQuery();
  const createRoleMutation = useCreateGlobalRoleMutation();
  const deleteRoleMutation = useDeleteRoleMutation();
  const updateRoleMutation = useUpdateRoleMutation();
  const [editingRole, setEditingRole] = useState<RoleDefinition | null>(null);
  const [isCreateDialogOpen, setCreateDialogOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const globalPermissions = useMemo(() => {
    return (permissionsQuery.data ?? []).filter((permission) => permission.scope_type === "global");
  }, [permissionsQuery.data]);

  const handleDelete = async (role: RoleDefinition) => {
    setActionError(null);
    try {
      await deleteRoleMutation.mutateAsync(role.id);
    } catch (error) {
      const message = error instanceof ApiError ? error.problem?.detail ?? error.message : "Unable to delete role.";
      setActionError(message);
    }
  };

  if (rolesQuery.isLoading || permissionsQuery.isLoading) {
    return <p className="text-sm text-slate-300">Loading global roles…</p>;
  }

  if (rolesQuery.error) {
    return (
      <p className="text-sm text-rose-200">
        We were unable to load global roles. Try refreshing the page.
      </p>
    );
  }

  const roles = rolesQuery.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Global roles</h2>
          <p className="text-sm text-slate-400">Roles defined at the tenant scope. Built-in roles cannot be deleted.</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setActionError(null);
            setCreateDialogOpen(true);
          }}
          className="inline-flex items-center rounded bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
        >
          + Create role
        </button>
      </div>

      {roles.length === 0 ? (
        <p className="text-sm text-slate-300">No global roles are defined yet.</p>
      ) : (
        <div className="overflow-hidden rounded border border-slate-800">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead className="bg-slate-900/70 text-left text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-3 font-semibold">Role</th>
                <th className="px-4 py-3 font-semibold">Slug</th>
                <th className="px-4 py-3 font-semibold">Permissions</th>
                <th className="px-4 py-3 font-semibold">Metadata</th>
                <th className="px-4 py-3 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-900 bg-slate-950/60 text-slate-200">
              {roles.map((role) => (
                <tr key={role.id}>
                  <td className="px-4 py-3 align-top">
                    <div className="font-semibold text-slate-100">{role.name}</div>
                    {role.description && <p className="text-xs text-slate-400">{role.description}</p>}
                  </td>
                  <td className="px-4 py-3 align-top text-xs text-slate-400">{role.slug}</td>
                  <td className="px-4 py-3 align-top">
                    {role.permissions.length === 0 ? (
                      <span className="text-xs text-slate-500">No permissions assigned.</span>
                    ) : (
                      <PermissionList permissions={role.permissions} lookup={permissionsQuery.data ?? []} />
                    )}
                  </td>
                  <td className="px-4 py-3 align-top text-xs text-slate-300">
                    <div className="space-y-1">
                      <div>
                        <span className="font-medium">Built-in:</span> {role.built_in ? "Yes" : "No"}
                      </div>
                      <div>
                        <span className="font-medium">Editable:</span> {role.editable ? "Yes" : "No"}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 align-top text-right text-xs">
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setActionError(null);
                          setEditingRole(role);
                        }}
                        disabled={!role.editable}
                        className="rounded border border-slate-700 px-2 py-1 font-medium text-slate-200 transition hover:border-slate-500 hover:text-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(role)}
                        disabled={role.built_in || deleteRoleMutation.isPending}
                        className="rounded border border-transparent px-2 py-1 font-medium text-rose-200 transition hover:text-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {actionError && <p className="text-sm text-rose-200" role="alert">{actionError}</p>}

      {isCreateDialogOpen && (
        <RoleDialog
          title="Create global role"
          permissions={globalPermissions}
          onDismiss={() => {
            setCreateDialogOpen(false);
          }}
          onSubmit={async (payload) => {
            setActionError(null);
            try {
              await createRoleMutation.mutateAsync(payload);
              setCreateDialogOpen(false);
            } catch (error) {
              const message = error instanceof ApiError ? error.problem?.detail ?? error.message : "Unable to create role.";
              setActionError(message);
              throw error;
            }
          }}
        />
      )}

      {editingRole && (
        <RoleDialog
          title="Edit global role"
          permissions={globalPermissions}
          role={editingRole}
          onDismiss={() => setEditingRole(null)}
          onSubmit={async ({ name, description, permissions }) => {
            setActionError(null);
            try {
              await updateRoleMutation.mutateAsync({
                roleId: editingRole.id,
                payload: { name, description, permissions },
              });
              setEditingRole(null);
            } catch (error) {
              const message = error instanceof ApiError ? error.problem?.detail ?? error.message : "Unable to update role.";
              setActionError(message);
              throw error;
            }
          }}
        />
      )}
    </div>
  );
}

function PermissionList({ permissions, lookup }: { permissions: string[]; lookup: PermissionDefinition[] }) {
  const labels = new Map(lookup.map((permission) => [permission.key, permission.label]));
  return (
    <ul className="flex flex-wrap gap-2 text-xs text-slate-200">
      {permissions.map((key) => (
        <li key={key} className="rounded border border-slate-800 bg-slate-900 px-2 py-1">
          <span className="font-medium text-slate-100">{labels.get(key) ?? key}</span>
          <span className="ml-2 text-slate-500">{key}</span>
        </li>
      ))}
    </ul>
  );
}

interface RoleDialogProps {
  title: string;
  permissions: PermissionDefinition[];
  role?: RoleDefinition | null;
  onDismiss: () => void;
  onSubmit: (payload: { name: string; slug?: string; description: string | null; permissions: string[] }) => Promise<void>;
}

function RoleDialog({ title, permissions, role, onDismiss, onSubmit }: RoleDialogProps) {
  const [name, setName] = useState(role?.name ?? "");
  const [slug, setSlug] = useState(role?.slug ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>(role?.permissions ?? []);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!name.trim()) {
      setError("Enter a role name.");
      return;
    }
    const payload = {
      name: name.trim(),
      slug: role ? role.slug : slug.trim() || undefined,
      description: description.trim() || null,
      permissions: selectedPermissions,
    };
    try {
      await onSubmit(payload);
    } catch (submissionError) {
      const message =
        submissionError instanceof ApiError
          ? submissionError.problem?.detail ?? submissionError.message
          : "Unable to save role.";
      setError(message);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-xl space-y-4 rounded border border-slate-900 bg-slate-950 p-6 text-slate-100 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">{title}</h2>
            <p className="mt-1 text-sm text-slate-400">
              Assign permissions to define what members granted this role can perform.
            </p>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Close role dialog"
            className="rounded border border-transparent p-1 text-slate-400 transition hover:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950"
          >
            <span aria-hidden>×</span>
          </button>
        </div>
        <div className="space-y-3 text-sm">
          <div>
            <label htmlFor="role-name" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
              Role name
            </label>
            <input
              id="role-name"
              type="text"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                if (error) setError(null);
              }}
              className="mt-2 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
              data-autofocus
            />
          </div>
          {!role && (
            <div>
              <label htmlFor="role-slug" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
                Role slug
              </label>
              <input
                id="role-slug"
                type="text"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                className="mt-2 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
                placeholder="global-reviewer"
              />
              <p className="mt-1 text-xs text-slate-500">Leave empty to auto-generate from the name.</p>
            </div>
          )}
          <div>
            <label htmlFor="role-description" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
              Description
            </label>
            <textarea
              id="role-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="mt-2 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
            />
          </div>
          <fieldset className="space-y-2">
            <legend className="text-xs font-semibold uppercase tracking-wide text-slate-400">Permissions</legend>
            {permissions.map((permission) => {
              const checked = selectedPermissions.includes(permission.key);
              return (
                <label key={permission.key} className="flex items-start gap-3 text-sm text-slate-200">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-slate-700 bg-slate-950 text-sky-500 focus:ring-sky-500"
                    checked={checked}
                    onChange={(event) => {
                      if (event.target.checked) {
                        setSelectedPermissions((current) => [...current, permission.key]);
                      } else {
                        setSelectedPermissions((current) => current.filter((key) => key !== permission.key));
                      }
                    }}
                  />
                  <span>
                    <span className="font-medium text-slate-100">{permission.label}</span>
                    <span className="ml-2 text-xs text-slate-500">{permission.key}</span>
                    <span className="block text-xs text-slate-500">{permission.description}</span>
                  </span>
                </label>
              );
            })}
            {permissions.length === 0 && <p className="text-xs text-slate-500">Permissions are loading.</p>}
          </fieldset>
        </div>
        {error && <p className="text-sm text-rose-200" role="alert">{error}</p>}
        <div className="flex justify-end gap-3 text-sm">
          <button
            type="button"
            onClick={onDismiss}
            className="rounded border border-slate-700 px-3 py-2 font-medium text-slate-300 hover:border-slate-500 hover:text-slate-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rounded bg-sky-500 px-4 py-2 font-semibold text-slate-950 transition hover:bg-sky-400"
          >
            Save role
          </button>
        </div>
      </form>
    </div>
  );
}
