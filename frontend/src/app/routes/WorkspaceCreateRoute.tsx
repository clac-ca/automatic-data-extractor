import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../shared/api/client";
import { useSessionQuery } from "../../features/auth/hooks/useSessionQuery";
import { useCreateWorkspaceMutation } from "../../features/workspaces/hooks/useCreateWorkspaceMutation";
import { useWorkspacesQuery } from "../../features/workspaces/hooks/useWorkspacesQuery";
import { useUsersQuery } from "../../features/users/hooks/useUsersQuery";
import { Alert, Button, FormField, Input } from "../../ui";

interface WorkspaceFormState {
  name: string;
  slug: string;
  ownerUserId: string;
}

export function WorkspaceCreateRoute() {
  const navigate = useNavigate();
  const workspacesQuery = useWorkspacesQuery();
  const createWorkspace = useCreateWorkspaceMutation();
  const { session } = useSessionQuery();

  const canSelectOwner = session?.user.permissions?.includes("Users.Read.All") ?? false;
  const usersQuery = useUsersQuery({ enabled: canSelectOwner });
  const ownerOptions = useMemo(() => usersQuery.data ?? [], [usersQuery.data]);
  const filteredOwnerOptions = useMemo(() => {
    if (!session?.user.user_id) {
      return ownerOptions;
    }
    return ownerOptions.filter((user) => user.user_id !== session.user.user_id);
  }, [ownerOptions, session?.user.user_id]);

  const [form, setForm] = useState<WorkspaceFormState>({
    name: "",
    slug: "",
    ownerUserId: session?.user.user_id ?? "",
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof WorkspaceFormState, string>>>(
    {},
  );

  const isSubmitting = createWorkspace.isPending;
  const ownerSelectDisabled = isSubmitting || usersQuery.isLoading;
  const currentUserLabel = session?.user.display_name
    ? `${session.user.display_name} (you)`
    : `${session?.user.email ?? "Current user"} (you)`;

  useEffect(() => {
    if (session?.user.user_id) {
      setForm((current) => ({
        ...current,
        ownerUserId: current.ownerUserId || session.user.user_id,
      }));
    }
  }, [session?.user.user_id]);

  function handleChange(key: keyof WorkspaceFormState) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value;
      setFieldErrors((current) => ({ ...current, [key]: undefined }));

      if (key === "name") {
        const generated = slugify(value);
        setForm((current) => ({
          ...current,
          name: value,
          slug: current.slug ? current.slug : generated,
        }));
        return;
      }

      if (key === "slug") {
        setForm((current) => ({ ...current, slug: slugify(value) }));
        return;
      }

      setForm((current) => ({ ...current, [key]: value }));
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});

    if (!form.name.trim()) {
      setFormError("Workspace name is required.");
      setFieldErrors((current) => ({ ...current, name: "Workspace name is required." }));
      return;
    }

    if (!form.slug.trim()) {
      setFormError("Workspace slug is required.");
      setFieldErrors((current) => ({ ...current, slug: "Workspace slug is required." }));
      return;
    }

    createWorkspace.mutate(
      {
        name: form.name.trim(),
        slug: form.slug.trim(),
        owner_user_id: canSelectOwner && form.ownerUserId ? form.ownerUserId : undefined,
      },
      {
        onSuccess(workspace) {
          workspacesQuery.refetch();
          navigate(`/workspaces/${workspace.id}`);
        },
        onError(error) {
          if (error instanceof ApiError) {
            const detail = error.problem?.detail ?? error.message;
            const errors = error.problem?.errors ?? {};
            setFormError(detail);
            const updated: Partial<Record<keyof WorkspaceFormState, string>> = {};
            if (errors.name?.length) {
              updated.name = errors.name[0];
            }
            if (errors.slug?.length) {
              updated.slug = errors.slug[0];
            }
            if (errors.owner_user_id?.length) {
              updated.ownerUserId = errors.owner_user_id[0];
            }
            setFieldErrors(updated);
            return;
          }
          setFormError(error instanceof Error ? error.message : "Workspace creation failed.");
        },
      },
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">Create a workspace</h1>
        <p className="text-sm text-slate-600">
          Name the workspace and choose who should own it. You can adjust settings and permissions after the
          workspace is created.
        </p>
      </header>

      <form
        className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft"
        onSubmit={handleSubmit}
      >
        <div className="grid gap-5 md:grid-cols-2">
          <FormField label="Workspace name" required error={fieldErrors.name}>
            <Input
              id="workspaceName"
              placeholder="Finance Operations"
              value={form.name}
              onChange={handleChange("name")}
              disabled={isSubmitting}
            />
          </FormField>

          <FormField
            label="Workspace slug"
            hint="Lowercase, URL-friendly identifier"
            required
            error={fieldErrors.slug}
          >
            <Input
              id="workspaceSlug"
              placeholder="finance-ops"
              value={form.slug}
              onChange={handleChange("slug")}
              disabled={isSubmitting}
            />
          </FormField>
        </div>

        {canSelectOwner ? (
          <FormField
            label="Workspace owner"
            hint="Owner receives workspace-level permissions immediately."
            error={fieldErrors.ownerUserId}
          >
            <select
              id="workspaceOwner"
              value={form.ownerUserId}
              onChange={(event) => {
                setFieldErrors((current) => ({ ...current, ownerUserId: undefined }));
                setForm((current) => ({ ...current, ownerUserId: event.target.value }));
              }}
              disabled={ownerSelectDisabled}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
            >
              <option value={session?.user.user_id ?? ""}>{currentUserLabel}</option>
              {filteredOwnerOptions.map((user) => (
                <option key={user.user_id} value={user.user_id}>
                  {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                </option>
              ))}
            </select>
          </FormField>
        ) : null}

        {formError ? <Alert tone="danger">{formError}</Alert> : null}
        {canSelectOwner && usersQuery.isError ? (
          <Alert tone="warning">
            Unable to load the user list. Continue with yourself as the workspace owner or try again later.
          </Alert>
        ) : null}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button
            type="button"
            variant="secondary"
            onClick={() => navigate(-1)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button type="submit" isLoading={isSubmitting}>
            {isSubmitting ? "Creating workspace…" : "Create workspace"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}
