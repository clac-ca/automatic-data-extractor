import { useEffect, useMemo } from "react";
import { useNavigate } from "react-router";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { ApiError } from "@shared/api";
import type { components } from "@openapi";
import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useCreateWorkspaceMutation } from "./useCreateWorkspaceMutation";
import { useWorkspacesQuery, type WorkspaceProfile } from "../workspaces/workspaces-api";
import { useUsersQuery } from "@shared/users/hooks/useUsersQuery";
import { WorkspaceDirectoryLayout } from "../workspaces/WorkspaceDirectoryLayout";
import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { Input } from "@ui/input";

const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const workspaceSchema = z.object({
  name: z.string().min(1, "Workspace name is required.").max(100, "Keep the name under 100 characters."),
  slug: z
    .string()
    .min(1, "Workspace slug is required.")
    .max(100, "Keep the slug under 100 characters.")
    .regex(slugPattern, "Use lowercase letters, numbers, and dashes."),
  ownerUserId: z.string().optional(),
});

type WorkspaceFormValues = z.infer<typeof workspaceSchema>;

export default function WorkspaceCreateRoute() {
  return (
    <RequireSession>
      <WorkspaceCreateContent />
    </RequireSession>
  );
}

function WorkspaceCreateContent() {
  const navigate = useNavigate();
  const session = useSession();
  const workspacesQuery = useWorkspacesQuery();
  const createWorkspace = useCreateWorkspaceMutation();

  const canSelectOwner = session.user.permissions?.includes("Users.Read.All") ?? false;
  const usersQuery = useUsersQuery({ enabled: canSelectOwner });
  const ownerOptions = useMemo<UserSummary[]>(() => usersQuery.data ?? [], [usersQuery.data]);
  const filteredOwnerOptions = useMemo(() => {
    if (!session.user.user_id) {
      return ownerOptions;
    }
    return ownerOptions.filter((user) => user.user_id !== session.user.user_id);
  }, [ownerOptions, session.user.user_id]);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    setError,
    clearErrors,
    formState: { errors, dirtyFields },
  } = useForm<WorkspaceFormValues>({
    resolver: zodResolver(workspaceSchema),
    defaultValues: {
      name: "",
      slug: "",
      ownerUserId: session.user.user_id ?? "",
    },
  });

  const nameValue = watch("name");
  const slugValue = watch("slug");

  useEffect(() => {
    if (dirtyFields.slug) {
      return;
    }
    const generated = slugify(nameValue);
    if (generated !== slugValue) {
      setValue("slug", generated, { shouldValidate: Boolean(generated) });
    }
  }, [dirtyFields.slug, nameValue, setValue, slugValue]);

  useEffect(() => {
    if (!canSelectOwner && session.user.user_id) {
      setValue("ownerUserId", session.user.user_id, { shouldDirty: false });
    }
  }, [canSelectOwner, session.user.user_id, setValue]);

  const isSubmitting = createWorkspace.isPending;
  const ownerSelectDisabled = isSubmitting || usersQuery.isLoading || !canSelectOwner;
  const currentUserLabel = session.user.display_name
    ? `${session.user.display_name} (you)`
    : `${session.user.email ?? "Current user"} (you)`;
  const ownerField = register("ownerUserId");

  const onSubmit = handleSubmit((values) => {
    clearErrors("root");

    if (canSelectOwner && !values.ownerUserId) {
      setError("ownerUserId", { type: "manual", message: "Select a workspace owner." });
      return;
    }

    createWorkspace.mutate(
      {
        name: values.name.trim(),
        slug: values.slug.trim(),
        owner_user_id: canSelectOwner ? values.ownerUserId || undefined : undefined,
      },
      {
        onSuccess(workspace: WorkspaceProfile) {
          workspacesQuery.refetch();
          navigate(`/workspaces/${workspace.id}`);
        },
        onError(error: unknown) {
          if (error instanceof ApiError) {
            const detail = error.problem?.detail ?? error.message;
            const fieldErrors = error.problem?.errors ?? {};
            setError("root", { type: "server", message: detail });
            if (fieldErrors.name?.[0]) {
              setError("name", { type: "server", message: fieldErrors.name[0] });
            }
            if (fieldErrors.slug?.[0]) {
              setError("slug", { type: "server", message: fieldErrors.slug[0] });
            }
            if (fieldErrors.owner_user_id?.[0]) {
              setError("ownerUserId", { type: "server", message: fieldErrors.owner_user_id[0] });
            }
            return;
          }
          setError("root", {
            type: "server",
            message: error instanceof Error ? error.message : "Workspace creation failed.",
          });
        },
      },
    );
  });

  return (
    <WorkspaceDirectoryLayout>
      <div className="space-y-6">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold text-slate-900">Create a workspace</h1>
          <p className="text-sm text-slate-600">
            Name the workspace and choose who should own it. You can adjust settings and permissions after the workspace
            is created.
          </p>
        </header>

        <form className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft" onSubmit={onSubmit}>
          <div className="grid gap-5 md:grid-cols-2">
            <FormField label="Workspace name" required error={errors.name?.message}>
              <Input
                id="workspaceName"
                placeholder="Finance Operations"
                {...register("name")}
                invalid={Boolean(errors.name)}
                disabled={isSubmitting}
              />
            </FormField>

            <FormField
              label="Workspace slug"
              hint="Lowercase, URL-friendly identifier"
              required
              error={errors.slug?.message}
            >
              <Input
                id="workspaceSlug"
                placeholder="finance-ops"
                {...register("slug")}
                invalid={Boolean(errors.slug)}
                disabled={isSubmitting}
              />
            </FormField>
          </div>

          {canSelectOwner ? (
            <FormField
              label="Workspace owner"
              hint="Owner receives workspace-level permissions immediately."
              error={errors.ownerUserId?.message}
            >
              <select
                id="workspaceOwner"
                {...ownerField}
                onChange={(event) => {
                  ownerField.onChange(event);
                  clearErrors("ownerUserId");
                }}
                disabled={ownerSelectDisabled}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
              >
                <option value={session.user.user_id ?? ""}>{currentUserLabel}</option>
                {filteredOwnerOptions.map((user) => (
                  <option key={user.user_id} value={user.user_id}>
                    {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                  </option>
                ))}
              </select>
            </FormField>
          ) : null}

          {errors.root ? <Alert tone="danger">{errors.root.message}</Alert> : null}
          {canSelectOwner && usersQuery.isError ? (
            <Alert tone="warning">
              Unable to load the user list. Continue with yourself as the workspace owner or try again later.
            </Alert>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button type="button" variant="secondary" onClick={() => navigate(-1)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSubmitting}>
              {isSubmitting ? "Creating workspace…" : "Create workspace"}
            </Button>
          </div>
        </form>
      </div>
    </WorkspaceDirectoryLayout>
  );
}

type UserSummary = components["schemas"]["UserSummary"];

function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}
