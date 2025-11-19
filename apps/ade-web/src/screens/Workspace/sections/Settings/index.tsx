import { useEffect, useState } from "react";

import { useSearchParams } from "@app/nav/urlState";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useUpdateWorkspaceMutation } from "./hooks/useUpdateWorkspaceMutation";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";
import { WorkspaceMembersSection } from "./components/WorkspaceMembersSection";
import { WorkspaceRolesSection } from "./components/WorkspaceRolesSection";

export const handle = { workspaceSectionId: "settings" } as const;

const SETTINGS_VIEWS = [
  { id: "general", label: "General" },
  { id: "members", label: "Members" },
  { id: "roles", label: "Roles" },
] as const;

type SettingsViewId = typeof SETTINGS_VIEWS[number]["id"];

const SETTINGS_VIEW_IDS = new Set<SettingsViewId>(SETTINGS_VIEWS.map((view) => view.id));

const isSettingsViewId = (value: string | null): value is SettingsViewId =>
  Boolean(value && SETTINGS_VIEW_IDS.has(value as SettingsViewId));

export default function WorkspaceSettingsRoute() {
  useWorkspaceContext();
  const [searchParams, setSearchParams] = useSearchParams();

  const rawViewParam = searchParams.get("view");
  const currentView: SettingsViewId = isSettingsViewId(rawViewParam) ? rawViewParam : "general";

  useEffect(() => {
    if (rawViewParam && !isSettingsViewId(rawViewParam)) {
      const next = new URLSearchParams(searchParams);
      next.set("view", "general");
      setSearchParams(next, { replace: true });
    }
  }, [rawViewParam, searchParams, setSearchParams]);

  const handleChangeView = (viewId: string) => {
    if (!isSettingsViewId(viewId)) {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set("view", viewId);
    setSearchParams(next, { replace: true });
  };

  return (
    <TabsRoot value={currentView} onValueChange={handleChangeView}>
      <div className="space-y-6">
        <TabsList className="flex gap-2 rounded-full border border-slate-200 bg-white p-1 shadow-soft" aria-label="Workspace settings views">
          {SETTINGS_VIEWS.map((option) => {
            const isActive = option.id === currentView;
            return (
              <TabsTrigger
                key={option.id}
                value={option.id}
                className={`rounded-full px-4 py-1 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 ${
                  isActive ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {option.label}
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value="general" aria-live="polite">
          {currentView === "general" ? <WorkspaceGeneralSettings /> : null}
        </TabsContent>
        <TabsContent value="members" aria-live="polite">
          {currentView === "members" ? <WorkspaceMembersSection /> : null}
        </TabsContent>
        <TabsContent value="roles" aria-live="polite">
          {currentView === "roles" ? <WorkspaceRolesSection /> : null}
        </TabsContent>
      </div>
    </TabsRoot>
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
