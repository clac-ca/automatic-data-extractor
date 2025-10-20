import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useWorkspaceContext } from "../workspaces.$workspaceId/WorkspaceContext";
import { useUpdateWorkspaceMutation } from "./useUpdateWorkspaceMutation";
import { Alert } from "@ui/alert";
import { Button } from "@ui/button";
import { FormField } from "@ui/form-field";
import { Input } from "@ui/input";
import { WorkspaceMembersSection } from "./WorkspaceMembersSection";
import { WorkspaceRolesSection } from "./WorkspaceRolesSection";

export const handle = { workspaceSectionId: "settings" } as const;

const SETTINGS_VIEWS = [
  { id: "general", label: "General" },
  { id: "members", label: "Members" },
  { id: "roles", label: "Roles" },
] as const;

type SettingsViewId = typeof SETTINGS_VIEWS[number]["id"];

export default function WorkspaceSettingsRoute() {
  useWorkspaceContext();
  const [searchParams, setSearchParams] = useSearchParams();

  const currentView = (searchParams.get("view") as SettingsViewId | null) ?? "general";

  useEffect(() => {
    if (!SETTINGS_VIEWS.some((view) => view.id === currentView)) {
      const next = new URLSearchParams(searchParams);
      next.set("view", "general");
      setSearchParams(next, { replace: true });
    }
  }, [currentView, searchParams, setSearchParams]);

  const handleChangeView = (viewId: SettingsViewId) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", viewId);
    setSearchParams(next, { replace: true });
  };

  const content = useMemo(() => {
    switch (currentView) {
      case "general":
        return <WorkspaceGeneralSettings />;
      case "members":
        return <WorkspaceMembersSection />;
      case "roles":
        return <WorkspaceRolesSection />;
      default:
        return null;
    }
  }, [currentView]);

  return (
    <div className="space-y-6">
      <nav className="flex gap-2 rounded-full border border-slate-200 bg-white p-1 shadow-soft">
        {SETTINGS_VIEWS.map((option) => {
          const isActive = option.id === currentView;
          return (
            <Button
              key={option.id}
              variant={isActive ? "primary" : "ghost"}
              size="sm"
              onClick={() => handleChangeView(option.id)}
            >
              {option.label}
            </Button>
          );
        })}
      </nav>

      <section aria-live="polite">{content}</section>
    </div>
  );
}

const generalSchema = z.object({
  name: z.string().min(1, "Workspace name is required.").max(255, "Keep the name under 255 characters."),
  slug: z
    .string()
    .min(1, "Workspace slug is required.")
    .max(100, "Keep the slug under 100 characters.")
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase letters, numbers, and dashes."),
});

type GeneralSettingsFormValues = z.infer<typeof generalSchema>;

function WorkspaceGeneralSettings() {
  const { workspace } = useWorkspaceContext();
  const updateWorkspace = useUpdateWorkspaceMutation(workspace.id);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
    reset,
  } = useForm<GeneralSettingsFormValues>({
    resolver: zodResolver(generalSchema),
    defaultValues: {
      name: workspace.name,
      slug: workspace.slug,
    },
  });

  useEffect(() => {
    reset({
      name: workspace.name,
      slug: workspace.slug,
    });
  }, [reset, workspace.name, workspace.slug]);

  const onSubmit = handleSubmit((values) => {
    setSuccessMessage(null);
    updateWorkspace.mutate(
      {
        name: values.name.trim(),
        slug: values.slug.trim(),
      },
      {
        onSuccess: () => {
          setSuccessMessage("Workspace details saved.");
        },
      },
    );
  });

  return (
    <form
      className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-soft"
      onSubmit={onSubmit}
      noValidate
    >
      <header className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-900">Workspace identity</h2>
        <p className="text-sm text-slate-500">
          Update the name and slug. Changes apply immediately across navigation and shared links.
        </p>
      </header>

      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      {updateWorkspace.isError ? (
        <Alert tone="danger">
          {updateWorkspace.error instanceof Error ? updateWorkspace.error.message : "Unable to save workspace details."}
        </Alert>
      ) : null}

      <div className="grid gap-6 md:grid-cols-2">
        <FormField label="Workspace name" required error={errors.name?.message}>
          <Input
            {...register("name")}
            placeholder="Finance Operations"
            invalid={Boolean(errors.name)}
            disabled={updateWorkspace.isPending}
          />
        </FormField>
        <FormField
          label="Workspace slug"
          hint="Lowercase, URL-friendly identifier."
          required
          error={errors.slug?.message}
        >
          <Input
            {...register("slug")}
            placeholder="finance-ops"
            invalid={Boolean(errors.slug)}
            disabled={updateWorkspace.isPending}
          />
        </FormField>
      </div>

      <div className="flex items-center justify-end gap-2">
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            reset();
            setSuccessMessage(null);
          }}
          disabled={updateWorkspace.isPending || !isDirty}
        >
          Reset
        </Button>
        <Button type="submit" isLoading={updateWorkspace.isPending} disabled={!isDirty}>
          Save changes
        </Button>
      </div>
    </form>
  );
}
