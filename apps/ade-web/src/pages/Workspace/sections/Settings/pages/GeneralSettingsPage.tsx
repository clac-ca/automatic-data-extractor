import clsx from "clsx";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { useSetDefaultWorkspaceMutation, useUpdateWorkspaceMutation } from "@hooks/workspaces";
import { UnsavedChangesPrompt } from "../components/UnsavedChangesPrompt";
import { MODE_OPTIONS, useTheme } from "@components/providers/theme";
import { ThemeSelect } from "@components/ui/theme-select";
import { FormField } from "@components/ui/form-field";
import { Input } from "@components/tablecn/ui/input";
import { Alert } from "@components/ui/alert";
import { Button } from "@components/tablecn/ui/button";
import { SettingsSection } from "../components/SettingsSection";
import { CheckIcon } from "@components/icons";

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
  const { modePreference, setModePreference, theme, setTheme } = useTheme();
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
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      <form onSubmit={submit} noValidate className="space-y-6">
        <SettingsSection
          title="Workspace identity"
          description="Update the name and slug. Changes apply immediately across navigation and shared links."
        >
          <div className="space-y-4">
            <FormField label="Workspace name" required error={errors.name?.message}>
              <Input {...register("name")} placeholder="Finance Operations" disabled={updateWorkspace.isPending} />
            </FormField>
            <FormField
              label="Workspace slug"
              hint="Lowercase, URL-friendly identifier."
              required
              error={errors.slug?.message}
            >
              <Input {...register("slug")} placeholder="finance-ops" disabled={updateWorkspace.isPending} />
            </FormField>
          </div>

          {updateWorkspace.isError ? (
            <Alert tone="danger">
              {updateWorkspace.error instanceof Error
                ? updateWorkspace.error.message
                : "Unable to save workspace details."}
            </Alert>
          ) : null}

          {isDirty ? (
            <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-4">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  reset();
                  setFeedback(null);
                }}
                disabled={updateWorkspace.isPending}
              >
                Discard
              </Button>
              <Button type="submit" size="sm" disabled={updateWorkspace.isPending}>
                {updateWorkspace.isPending ? "Saving..." : "Save changes"}
              </Button>
            </div>
          ) : null}
        </SettingsSection>
      </form>

      <SettingsSection
        title="Appearance"
        description="Choose a color mode and workspace theme."
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">Color mode</p>
            <div role="radiogroup" aria-label="Color mode" className="grid gap-2">
              {MODE_OPTIONS.map((option) => {
                const isSelected = option.value === modePreference;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => setModePreference(option.value)}
                    className={clsx(
                      "flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-sm font-medium transition",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                      isSelected
                        ? "border-brand-400 bg-muted text-foreground shadow-sm"
                        : "border-border bg-card text-foreground hover:border-border-strong hover:bg-muted",
                    )}
                  >
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-sm font-semibold">{option.label}</span>
                      <span className="truncate text-xs text-muted-foreground">{option.description}</span>
                    </span>
                    {isSelected ? <CheckIcon className="h-4 w-4 text-brand-500" /> : null}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">Theme</p>
            <ThemeSelect theme={theme} onThemeChange={setTheme} label="Theme" />
          </div>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Default workspace"
        description="Choose the workspace you land on first after signing in. This only affects your account."
        actions={
          <Button
            type="button"
            variant={isDefault ? "secondary" : "default"}
            size="sm"
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
          >
            {isSettingDefault ? "Updating..." : isDefault ? "Default workspace" : "Make default"}
          </Button>
        }
      >
        <p className="text-sm text-muted-foreground">
          {isDefault
            ? "This workspace is already your default."
            : "You can switch the default workspace at any time."}
        </p>
      </SettingsSection>
    </div>
  );
}
