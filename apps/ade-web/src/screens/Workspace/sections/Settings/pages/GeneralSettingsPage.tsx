import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useSetDefaultWorkspaceMutation, useUpdateWorkspaceMutation } from "@shared/workspaces";
import { SettingsSectionHeader } from "../components/SettingsSectionHeader";
import { UnsavedChangesPrompt } from "../components/UnsavedChangesPrompt";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { Alert } from "@ui/Alert";
import { SaveBar } from "../components/SaveBar";
import { Button } from "@ui/Button";

const generalSchema = z.object({
  name: z.string().min(1, "Workspace name is required.").max(255, "Keep the name under 255 characters."),
  slug: z
    .string()
    .min(1, "Workspace slug is required.")
    .max(100, "Keep the slug under 100 characters.")
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase letters, numbers, and dashes."),
});

type GeneralSettingsFormValues = z.infer<typeof generalSchema>;

export function GeneralSettingsPage() {
  const { workspace } = useWorkspaceContext();
  const updateWorkspace = useUpdateWorkspaceMutation(workspace.id);
  const setDefaultWorkspace = useSetDefaultWorkspaceMutation();
  const [feedback, setFeedback] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

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

  const submit = handleSubmit((values) => {
    setFeedback(null);
    updateWorkspace.mutate(
      {
        name: values.name.trim(),
        slug: values.slug.trim(),
      },
      {
        onSuccess: () => {
          setFeedback({ tone: "success", message: "Workspace details saved." });
        },
        onError: (error) => {
          const message = error instanceof Error ? error.message : "Unable to save workspace details.";
          setFeedback({ tone: "danger", message });
        },
      },
    );
  });

  const isDefault = workspace.is_default;
  const isSettingDefault = setDefaultWorkspace.isPending;

  return (
    <div className="space-y-6">
      <UnsavedChangesPrompt when={isDirty && !updateWorkspace.isPending} />
      <SettingsSectionHeader
        title="General"
        description="Manage the workspace identity and your default workspace preference."
      />

      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      <form
        className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-soft"
        onSubmit={submit}
        noValidate
      >
        <div className="space-y-6 p-6">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold text-slate-900">Workspace identity</h3>
            <p className="text-sm text-slate-500">
              Update the name and slug. Changes apply immediately across navigation and shared links.
            </p>
          </div>

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

          {updateWorkspace.isError ? (
            <Alert tone="danger">
              {updateWorkspace.error instanceof Error
                ? updateWorkspace.error.message
                : "Unable to save workspace details."}
            </Alert>
          ) : null}
        </div>

        <SaveBar
          isDirty={isDirty}
          isSaving={updateWorkspace.isPending}
          onCancel={() => {
            reset();
            setFeedback(null);
          }}
          onSave={submit}
        >
          Changes apply to everyone who can access this workspace.
        </SaveBar>
      </form>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold text-slate-900">Default workspace</h3>
            <p className="text-sm text-slate-500">
              Choose the workspace you land on first after signing in. This only affects your account.
            </p>
          </div>
          <Button
            type="button"
            variant={isDefault ? "secondary" : "primary"}
            onClick={() => {
              setFeedback(null);
              setDefaultWorkspace.mutate(workspace.id, {
                onSuccess: () => setFeedback({ tone: "success", message: "Workspace set as your default." }),
                onError: (error) => {
                  const message =
                    error instanceof Error ? error.message : "Unable to set the default workspace right now.";
                  setFeedback({ tone: "danger", message });
                },
              });
            }}
            disabled={isDefault || isSettingDefault}
            isLoading={isSettingDefault}
          >
            {isDefault ? "Default workspace" : "Make default"}
          </Button>
        </div>
        <p className="mt-3 text-sm text-slate-600">
          {isDefault
            ? "This workspace is already your default."
            : "You can switch the default workspace at any time."}
        </p>
      </div>
    </div>
  );
}
