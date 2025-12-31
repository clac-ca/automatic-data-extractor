import { useEffect, useMemo } from "react";

import { useNavigate } from "@app/nav/history";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { ApiError } from "@api";
import type { UserSummary } from "@api/users/api";
import { RequireSession } from "@components/auth/RequireSession";
import { useSession } from "@components/auth/SessionContext";
import { useCreateWorkspaceMutation } from "@hooks/workspaces";
import { getDefaultWorkspacePath } from "@utils/workspaces";
import { useUsersQuery } from "@hooks/users/useUsersQuery";
import { WorkspaceDirectoryLayout } from "@pages/Workspaces/components/WorkspaceDirectoryLayout";
import { Alert } from "@components/Alert";
import { Button } from "@components/Button";
import { FormField } from "@components/FormField";
import { Input } from "@components/Input";

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

export default function WorkspaceCreateScreen() {
  return (
    <RequireSession>
      <WorkspaceCreateContent />
    </RequireSession>
  );
}

function WorkspaceCreateContent() {
  const navigate = useNavigate();
  const session = useSession();
  const createWorkspace = useCreateWorkspaceMutation();

  const normalizedPermissions = useMemo(
    () => (session.user.permissions ?? []).map((key) => key.toLowerCase()),
    [session.user.permissions],
  );
  const canSelectOwner = normalizedPermissions.includes("users.read_all");
  const usersQuery = useUsersQuery({ enabled: canSelectOwner, pageSize: 50 });
  const ownerOptions = useMemo<UserSummary[]>(() => usersQuery.users, [usersQuery.users]);
  const filteredOwnerOptions = useMemo(() => {
    if (!session.user.id) {
      return ownerOptions;
    }
    return ownerOptions.filter((user) => user.id !== session.user.id);
  }, [ownerOptions, session.user.id]);

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
      ownerUserId: session.user.id ?? "",
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
    if (!canSelectOwner && session.user.id) {
      setValue("ownerUserId", session.user.id, { shouldDirty: false });
    }
  }, [canSelectOwner, session.user.id, setValue]);

  const isSubmitting = createWorkspace.isPending;
  const usersLoading = usersQuery.isPending && usersQuery.users.length === 0;
  const ownerSelectDisabled = isSubmitting || usersLoading || !canSelectOwner;
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
        onSuccess(workspace) {
          navigate(getDefaultWorkspacePath(workspace.id));
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
          <h1 className="text-2xl font-semibold text-foreground">Create a workspace</h1>
          <p className="text-sm text-muted-foreground">
            Name the workspace and choose who should own it. You can adjust settings and permissions after the workspace
            is created.
          </p>
        </header>

        <form className="space-y-6 rounded-2xl border border-border bg-card p-6 shadow-soft" onSubmit={onSubmit}>
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
                className="rounded-lg border border-border-strong bg-card px-3 py-2 text-sm text-foreground shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
              >
                <option value={session.user.id ?? ""}>{currentUserLabel}</option>
                {filteredOwnerOptions.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.display_name ? `${user.display_name} (${user.email})` : user.email}
                  </option>
                ))}
              </select>
              {usersQuery.hasNextPage ? (
                <div className="pt-2">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => usersQuery.fetchNextPage()}
                    disabled={usersQuery.isFetchingNextPage}
                  >
                    {usersQuery.isFetchingNextPage ? "Loading more users…" : "Load more users"}
                  </Button>
                </div>
              ) : null}
            </FormField>
          ) : null}

          {errors.root ? <Alert tone="danger">{errors.root.message}</Alert> : null}
          {canSelectOwner && usersQuery.isError ? (
            <Alert tone="warning">
              Unable to load the user list. Continue with yourself as the workspace owner or try again later.
            </Alert>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button type="button" variant="secondary" onClick={() => navigate("/workspaces")} disabled={isSubmitting}>
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


function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}
