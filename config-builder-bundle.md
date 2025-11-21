# Logical module layout (source -> sections below):
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/detail/index.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/index.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/ActivityBar.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/BottomPanel.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/EditorArea.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Explorer.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Inspector.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/PanelResizeHandle.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/__tests__/EditorArea.test.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/defaultConfig.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/index.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/seed/stubWorkbenchData.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/__tests__/useUnsavedChangesGuard.test.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/__tests__/useWorkbenchFiles.test.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/activityModel.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useEditorThemePreference.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useUnsavedChangesGuard.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchActivities.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchFiles.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchUrlState.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/types.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/__tests__/console.test.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/__tests__/tree.test.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/drag.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/tree.ts

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/detail/index.tsx
```tsx
import { useMemo } from "react";

import { useNavigate } from "@app/nav/history";

import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";

import { useConfigsQuery } from "@shared/configs";

interface WorkspaceConfigRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function WorkspaceConfigRoute({ params }: WorkspaceConfigRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const configId = params?.configId;

  const configsQuery = useConfigsQuery({ workspaceId: workspace.id });

  const config = useMemo(
    () => configsQuery.data?.items.find((item) => item.config_id === configId),
    [configsQuery.data, configId],
  );

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Configuration not found"
        description="Pick a configuration from the list to view its details."
      />
    );
  }

  if (configsQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration"
        description="Fetching configuration details."
      />
    );
  }

  if (!config) {
    return (
      <PageState
        variant="error"
        title="Configuration unavailable"
        description="The selected configuration could not be found. It may have been deleted."
      />
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Configuration</p>
            <h1 className="text-xl font-semibold text-slate-900">{config.display_name}</h1>
          </div>
          <Button
            variant="secondary"
            onClick={() =>
              navigate(`/workspaces/${workspace.id}/config-builder/${encodeURIComponent(config.config_id)}/editor`)
            }
          >
            Open editor
          </Button>
        </header>
        <dl className="grid gap-4 md:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Config ID</dt>
            <dd className="text-sm text-slate-700">{config.config_id}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</dt>
            <dd className="text-sm capitalize text-slate-700">{config.status.toLowerCase()}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Updated</dt>
            <dd className="text-sm text-slate-700">{new Date(config.updated_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Active version</dt>
            <dd className="text-sm text-slate-700">
              {("active_version" in config ? (config as { active_version?: number | null }).active_version : null) ??
                config.config_version ??
                "—"}
            </dd>
          </div>
        </dl>
      </section>
      <section className="flex-1 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6">
        <h2 className="text-base font-semibold text-slate-800">Overview</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          The refreshed config workbench will eventually surface manifest summaries, validation history, and deployment metrics
          here. For now this page offers a quick launch point into the editor while we rebuild the experience.
        </p>
      </section>
    </div>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/index.tsx
```tsx
import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { useNavigate } from "@app/nav/history";

import { Button } from "@ui/Button";
import { FormField } from "@ui/FormField";
import { Input } from "@ui/Input";
import { PageState } from "@ui/PageState";
import { Select } from "@ui/Select";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useConfigsQuery, useCreateConfigMutation } from "@shared/configs";
import { createScopedStorage } from "@shared/storage";

const TEMPLATE_OPTIONS = [{ value: "default", label: "Default template" }] as const;

const buildStorageKey = (workspaceId: string) => `ade.ui.workspace.${workspaceId}.config-builder.last`;
const buildConfigDetailPath = (workspaceId: string, configId: string) =>
  `/workspaces/${workspaceId}/config-builder/${encodeURIComponent(configId)}`;

type LastSelection = { readonly configId?: string | null } | null;

export const handle = { workspaceSectionId: "config-builder" } as const;

export default function WorkspaceConfigsIndexRoute() {
  const { workspace } = useWorkspaceContext();
  const navigate = useNavigate();
  const storage = useMemo(() => createScopedStorage(buildStorageKey(workspace.id)), [workspace.id]);
  const configsQuery = useConfigsQuery({ workspaceId: workspace.id });
  const createConfig = useCreateConfigMutation(workspace.id);

  const [displayName, setDisplayName] = useState(() => `${workspace.name} Config`);
  const [templateId, setTemplateId] = useState<string>(TEMPLATE_OPTIONS[0]?.value ?? "default");
  const [validationError, setValidationError] = useState<string | null>(null);

  const configs = useMemo(
    () =>
      (configsQuery.data?.items ?? []).filter((config) => !("deleted_at" in config && (config as { deleted_at?: string | null }).deleted_at)),
    [configsQuery.data],
  );
  const lastSelection = useMemo(() => storage.get<LastSelection>(), [storage]);

  const handleOpenConfig = (configId: string) => {
    storage.set<LastSelection>({ configId });
    navigate(buildConfigDetailPath(workspace.id, configId));
  };

  const handleOpenEditor = (configId: string) => {
    storage.set<LastSelection>({ configId });
    navigate(`${buildConfigDetailPath(workspace.id, configId)}/editor`);
  };

  const handleCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = displayName.trim();
    if (!trimmed) {
      setValidationError("Enter a display name for the configuration.");
      return;
    }
    setValidationError(null);
    createConfig.mutate(
      {
        displayName: trimmed,
        source: { type: "template", templateId },
      },
      {
        onSuccess(record) {
          storage.set<LastSelection>({ configId: record.config_id });
          navigate(buildConfigDetailPath(workspace.id, record.config_id));
        },
      },
    );
  };

  const creationError = validationError ?? (createConfig.error instanceof Error ? createConfig.error.message : null);
  const canSubmit = displayName.trim().length > 0 && !createConfig.isPending;

  if (configsQuery.isLoading) {
    return <PageState variant="loading" title="Loading configurations" description="Fetching workspace configurations…" />;
  }

  if (configsQuery.isError) {
    return <PageState variant="error" title="Unable to load configurations" description="Try refreshing the page." />;
  }

  if (configs.length === 0) {
    return (
      <PageState
        className="mx-auto w-full max-w-xl"
        title="Create your first configuration"
        description="Copy a starter template into this workspace to begin editing detectors, hooks, and manifests."
        action={
          <form onSubmit={handleCreate} className="space-y-4 text-left">
            <FormField label="Configuration name" required>
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Membership normalization"
                disabled={createConfig.isPending}
                autoFocus
              />
            </FormField>
            <FormField label="Template">
              <Select
                value={templateId}
                onChange={(event) => setTemplateId(event.target.value)}
                disabled={createConfig.isPending}
              >
                {TEMPLATE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </FormField>
            {creationError ? <p className="text-sm font-medium text-danger-600">{creationError}</p> : null}
            <Button type="submit" className="w-full" disabled={!canSubmit} isLoading={createConfig.isPending}>
              Create from template
            </Button>
          </form>
        }
      />
    );
  }

  return (
    <div className="grid gap-6 p-4 lg:grid-cols-[minmax(0,2fr),minmax(0,1fr)]">
      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Configurations</h1>
            <p className="text-sm text-slate-500">
              Open an existing configuration to view manifest summaries, run validation, or launch the editor.
            </p>
          </div>
          {lastSelection?.configId ? (
            <Button variant="ghost" size="sm" onClick={() => handleOpenConfig(lastSelection.configId!)}>
              Resume last opened
            </Button>
          ) : null}
        </header>
        <div className="divide-y divide-slate-200 rounded-xl border border-slate-200">
          {configs.map((config) => (
            <article key={config.config_id} className="grid gap-3 p-4 md:grid-cols-[minmax(0,2fr),auto] md:items-center">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold text-slate-900">{config.display_name}</h2>
                  <StatusPill status={config.status} />
                  {lastSelection?.configId === config.config_id ? (
                    <span className="text-xs font-medium uppercase tracking-wide text-brand-600">Last opened</span>
                  ) : null}
                </div>
                <p className="text-sm text-slate-500">
                  Updated {new Date(config.updated_at).toLocaleString()} · Active version{" "}
                  {("active_version" in config ? (config as { active_version?: number | null }).active_version : null) ??
                    config.config_version ??
                    "—"}
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <Button size="sm" variant="secondary" onClick={() => handleOpenConfig(config.config_id)}>
                  View details
                </Button>
                <Button size="sm" variant="ghost" onClick={() => handleOpenEditor(config.config_id)}>
                  Open editor
                </Button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <aside className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-slate-900">New configuration</h2>
          <p className="text-sm text-slate-500">Copy the starter template to begin editing detectors, hooks, and manifests.</p>
        </div>
        <form onSubmit={handleCreate} className="space-y-4">
          <FormField label="Configuration name" required>
            <Input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Membership normalization"
              disabled={createConfig.isPending}
            />
          </FormField>
          <FormField label="Template">
            <Select
              value={templateId}
              onChange={(event) => setTemplateId(event.target.value)}
              disabled={createConfig.isPending}
            >
              {TEMPLATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </FormField>
          {creationError ? <p className="text-sm font-medium text-danger-600">{creationError}</p> : null}
          <Button type="submit" className="w-full" disabled={!canSubmit} isLoading={createConfig.isPending}>
            Create from template
          </Button>
        </form>
      </aside>
    </div>
  );
}

function StatusPill({ status }: { readonly status: string }) {
  const normalized = status.toLowerCase();
  const styles =
    normalized === "active"
      ? "bg-emerald-100 text-emerald-700"
      : normalized === "draft"
        ? "bg-amber-100 text-amber-700"
        : "bg-slate-200 text-slate-700";
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${styles}`}>{status}</span>;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx
```tsx
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import clsx from "clsx";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPortal } from "react-dom";

import { ActivityBar, type ActivityBarView } from "./components/ActivityBar";
import { BottomPanel } from "./components/BottomPanel";
import { EditorArea } from "./components/EditorArea";
import { Explorer } from "./components/Explorer";
import { Inspector } from "./components/Inspector";
import { PanelResizeHandle } from "./components/PanelResizeHandle";
import { useWorkbenchFiles } from "./state/useWorkbenchFiles";
import { useWorkbenchUrlState } from "./state/useWorkbenchUrlState";
import { useUnsavedChangesGuard } from "./state/useUnsavedChangesGuard";
import { useEditorThemePreference } from "./state/useEditorThemePreference";
import type { EditorThemePreference } from "./state/useEditorThemePreference";
import { useWorkbenchActivities } from "./state/useWorkbenchActivities";
import type { Activity, ActivityKind, ValidationIssue } from "./state/activityModel";
import type { WorkbenchConsoleLine, WorkbenchDataSeed, WorkbenchValidationState } from "./types";
import { clamp, trackPointerDrag } from "./utils/drag";
import { createWorkbenchTreeFromListing } from "./utils/tree";

import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { SplitButton } from "@ui/SplitButton";
import { PageState } from "@ui/PageState";

import { useConfigFilesQuery, useSaveConfigFileMutation } from "@shared/configs/hooks/useConfigFiles";
import { configsKeys } from "@shared/configs/keys";
import { readConfigFileJson } from "@shared/configs/api";
import type { FileReadJson } from "@shared/configs/types";
import { useValidateConfigurationMutation } from "@shared/configs/hooks/useValidateConfiguration";
import { createScopedStorage } from "@shared/storage";
import type { ConfigBuilderConsole } from "@app/nav/urlState";
import { ApiError } from "@shared/api";
import { streamBuild } from "@shared/builds/api";
import { fetchRunOutputs, streamRun, type RunStreamOptions } from "@shared/runs/api";
import { isTelemetryEnvelope } from "@shared/runs/types";
import type { components } from "@schema";
import { fetchDocumentSheets, type DocumentSheet } from "@shared/documents";
import { client } from "@shared/api/client";
import { describeBuildEvent, describeRunEvent, formatConsoleTimestamp } from "./utils/console";
import { useNotifications, type NotificationIntent } from "@shared/notifications";
import { Select } from "@ui/Select";
import { Button } from "@ui/Button";
import { Alert } from "@ui/Alert";

const EXPLORER_LIMITS = { min: 200, max: 420 } as const;
const INSPECTOR_LIMITS = { min: 260, max: 420 } as const;
const OUTPUT_LIMITS = { min: 140, max: 420 } as const;
const MIN_EDITOR_HEIGHT = 320;
const MIN_CONSOLE_HEIGHT = 140;
const DEFAULT_CONSOLE_HEIGHT = 220;
const OUTPUT_HANDLE_THICKNESS = 4; // matches h-1 Tailwind utility on PanelResizeHandle
const ACTIVITY_BAR_WIDTH = 56; // w-14
const CONSOLE_COLLAPSE_MESSAGE =
  "Console closed to keep the editor readable on this screen size. Resize the window or collapse other panes to reopen it.";
const buildTabStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.tabs`;
const buildConsoleStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.console`;
const buildEditorThemeStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.editor-theme`;

const THEME_MENU_OPTIONS: Array<{ value: EditorThemePreference; label: string }> = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const ACTIVITY_LABELS: Record<ActivityBarView, string> = {
  explorer: "",
  search: "Search coming soon",
  scm: "Source Control coming soon",
  extensions: "Extensions coming soon",
};

interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;
  readonly state: ConfigBuilderConsole;
}

type SideBounds = {
  readonly minPx: number;
  readonly maxPx: number;
  readonly minFrac: number;
  readonly maxFrac: number;
};

type BuildTriggerOptions = {
  readonly force?: boolean;
  readonly wait?: boolean;
  readonly source?: "button" | "menu" | "shortcut";
};

type WorkbenchWindowState = "restored" | "maximized";

type DocumentRecord = components["schemas"]["DocumentOut"];

interface RunStreamMetadata {
  readonly mode: "validation" | "extraction";
  readonly documentId?: string;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
}

type PreflightItemState = "ok" | "action" | "running";

interface PreflightItem {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
  readonly state: PreflightItemState;
  readonly actionLabel?: string;
  readonly onAction?: () => void;
  readonly disabled?: boolean;
}

interface WorkbenchProps {
  readonly workspaceId: string;
  readonly configId: string;
  readonly configName: string;
  readonly seed?: WorkbenchDataSeed;
  readonly windowState: WorkbenchWindowState;
  readonly onMinimizeWindow: () => void;
  readonly onMaximizeWindow: () => void;
  readonly onRestoreWindow: () => void;
  readonly onCloseWorkbench: () => void;
  readonly shouldBypassUnsavedGuard?: () => boolean;
}

export function Workbench({
  workspaceId,
  configId,
  configName,
  seed,
  windowState,
  onMinimizeWindow,
  onMaximizeWindow,
  onRestoreWindow,
  onCloseWorkbench,
  shouldBypassUnsavedGuard,
}: WorkbenchProps) {
  const queryClient = useQueryClient();
  const {
    fileId,
    pane,
    console: consoleState,
    consoleExplicit,
    setFileId,
    setPane,
    setConsole,
  } = useWorkbenchUrlState();

  const usingSeed = Boolean(seed);
  const filesQuery = useConfigFilesQuery({
    workspaceId,
    configId,
    depth: "infinity",
    sort: "path",
    order: "asc",
    enabled: !usingSeed,
  });

  const tree = useMemo(() => {
    if (seed) {
      return seed.tree;
    }
    if (!filesQuery.data) {
      return null;
    }
    return createWorkbenchTreeFromListing(filesQuery.data);
  }, [seed, filesQuery.data]);

  const consoleStreamRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  const {
    state: activityState,
    selectedActivity,
    selectedActivityId,
    selectActivity,
    startActivity,
    appendLog: appendActivityLog,
    appendIssues: appendActivityIssues,
    completeActivity,
    patchActivity,
    setLiveActivityId,
    resolveActivityId,
    runningByKind,
    latestByKind,
  } = useWorkbenchActivities();

  const appendConsoleLine = useCallback(
    (line: WorkbenchConsoleLine, targetActivityId?: string | null) => {
      if (!isMountedRef.current) {
        return;
      }
      const activityId = resolveActivityId(targetActivityId);
      if (!activityId) {
        return;
      }
      appendActivityLog(activityId, line);
    },
    [appendActivityLog, resolveActivityId],
  );

  const [validationState, setValidationState] = useState<WorkbenchValidationState>(() => ({
    status: seed?.validation?.length ? "success" : "idle",
    messages: seed?.validation ?? [],
    lastRunAt: seed?.validation?.length ? new Date().toISOString() : undefined,
    error: null,
    digest: null,
  }));

  const seededActivityRef = useRef(false);
  useEffect(() => {
    if (seededActivityRef.current || !seed) {
      return;
    }
    seededActivityRef.current = true;
    const issues: ValidationIssue[] = (seed.validation ?? []).map((item) => ({
      level: item.level,
      message: item.message,
      path: item.path,
    }));
    const seedActivityKind: ActivityKind = issues.length > 0 ? "validation" : "build";
    startActivity(seedActivityKind, {
      status: "succeeded",
      label: "Seed session",
      logs: seed.console ?? [],
      issues,
      errorCount: issues.filter((entry) => entry.level === "error").length,
      warningCount: issues.filter((entry) => entry.level === "warning").length,
    });
  }, [startActivity, seed]);
  const [runDialogOpen, setRunDialogOpen] = useState(false);

  useEffect(() => {
    if (seed?.validation) {
      setValidationState({
        status: "success",
        messages: seed.validation,
        lastRunAt: new Date().toISOString(),
        error: null,
        digest: null,
      });
    }
  }, [seed?.validation]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      consoleStreamRef.current?.abort();
    };
  }, []);

  const validateConfiguration = useValidateConfigurationMutation(workspaceId, configId);

  const tabPersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildTabStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const consolePersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildConsoleStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const initialConsolePrefsRef = useRef<ConsolePanelPreferences | Record<string, unknown> | null>(null);
  if (!initialConsolePrefsRef.current && consolePersistence) {
    initialConsolePrefsRef.current =
      (consolePersistence.get<unknown>() as ConsolePanelPreferences | Record<string, unknown> | null) ?? null;
  }
  const editorTheme = useEditorThemePreference(buildEditorThemeStorageKey(workspaceId, configId));
  const menuAppearance = editorTheme.resolvedTheme === "vs-light" ? "light" : "dark";
  const latestValidationActivity = latestByKind.validation;
  const validationLabel = latestValidationActivity
    ? `Last validation: ${latestValidationActivity.errorCount ?? 0} errors, ${latestValidationActivity.warningCount ?? 0} warnings`
    : validationState.lastRunAt
      ? `Last run ${formatRelative(validationState.lastRunAt)}`
      : undefined;
  const latestBuildActivity = latestByKind.build;
  const environmentLabel =
    latestBuildActivity?.status === "succeeded"
      ? "Environment up to date"
      : latestBuildActivity?.status
        ? `Env ${latestBuildActivity.status}`
        : undefined;

  const [explorer, setExplorer] = useState({ collapsed: false, fraction: 280 / 1200 });
  const [inspector, setInspector] = useState({ collapsed: false, fraction: 300 / 1200 });
  const [consoleFraction, setConsoleFraction] = useState<number | null>(null);
  const [hasHydratedConsoleState, setHasHydratedConsoleState] = useState(false);
  const [layoutSize, setLayoutSize] = useState({ width: 0, height: 0 });
  const [paneAreaEl, setPaneAreaEl] = useState<HTMLDivElement | null>(null);
  const [activityView, setActivityView] = useState<ActivityBarView>("explorer");
  const [preflightOpen, setPreflightOpen] = useState(false);
  const [settingsMenu, setSettingsMenu] = useState<{ x: number; y: number } | null>(null);
  const [buildMenu, setBuildMenu] = useState<{ x: number; y: number } | null>(null);
  const [forceNextBuild, setForceNextBuild] = useState(false);
  const [forceModifierActive, setForceModifierActive] = useState(false);
  const [isResizingConsole, setIsResizingConsole] = useState(false);
  const { notifyBanner, dismissScope } = useNotifications();
  const consoleBannerScope = useMemo(
    () => `workbench-console:${workspaceId}:${configId}`,
    [workspaceId, configId],
  );
  const showConsoleBanner = useCallback(
    (message: string, options?: { intent?: NotificationIntent; duration?: number | null }) => {
      notifyBanner({
        title: message,
        intent: options?.intent ?? "info",
        duration: options?.duration ?? 6000,
        dismissible: true,
        scope: consoleBannerScope,
        persistKey: consoleBannerScope,
      });
    },
    [notifyBanner, consoleBannerScope],
  );
  const clearConsoleBanners = useCallback(() => {
    dismissScope(consoleBannerScope, "banner");
  }, [dismissScope, consoleBannerScope]);

  const pushConsoleError = useCallback(
    (error: unknown) => {
      if (!isMountedRef.current) {
        return;
      }
      const message = describeError(error);
      appendConsoleLine({ level: "error", message, timestamp: formatConsoleTimestamp(new Date()) });
      showConsoleBanner(message, { intent: "danger", duration: null });
    },
    [appendConsoleLine, showConsoleBanner],
  );

  const isMaximized = windowState === "maximized";
  const isMacPlatform = typeof navigator !== "undefined" ? /mac/i.test(navigator.platform) : false;
  const handleCloseWorkbench = useCallback(() => {
    onCloseWorkbench();
  }, [onCloseWorkbench]);
  const openBuildMenu = useCallback((position: { x: number; y: number }) => {
    setBuildMenu(position);
  }, []);
  const closeBuildMenu = useCallback(() => setBuildMenu(null), []);
  const showExplorerPane = !explorer.collapsed;

  const loadFile = useCallback(
    async (path: string) => {
      if (seed) {
        return { content: seed.content[path] ?? "", etag: null };
      }
      const payload = await queryClient.fetchQuery({
        queryKey: configsKeys.file(workspaceId, configId, path),
        queryFn: ({ signal }) => readConfigFileJson(workspaceId, configId, path, signal),
      });
      if (!payload) {
        throw new Error("File could not be loaded.");
      }
      return { content: decodeFileContent(payload), etag: payload.etag ?? null };
    },
    [seed, queryClient, workspaceId, configId],
  );

  const files = useWorkbenchFiles({
    tree,
    initialActiveFileId: fileId,
    loadFile,
    persistence: tabPersistence ?? undefined,
  });
  const saveConfigFile = useSaveConfigFileMutation(workspaceId, configId);
  const reloadFileFromServer = useCallback(
    async (fileId: string) => {
      if (usingSeed) {
        return null;
      }
      const payload = await queryClient.fetchQuery({
        queryKey: configsKeys.file(workspaceId, configId, fileId),
        queryFn: ({ signal }) => readConfigFileJson(workspaceId, configId, fileId, signal),
      });
      const content = decodeFileContent(payload);
      files.replaceTabContent(fileId, {
        content,
        etag: payload.etag ?? null,
        metadata: {
          size: payload.size ?? null,
          modifiedAt: payload.mtime ?? null,
          contentType:
            payload.content_type ??
            files.tabs.find((tab) => tab.id === fileId)?.metadata?.contentType ??
            null,
          etag: payload.etag ?? null,
        },
      });
      return payload;
    },
    [usingSeed, queryClient, workspaceId, configId, files],
  );

  useUnsavedChangesGuard({
    isDirty: files.isDirty,
    shouldBypassNavigation: shouldBypassUnsavedGuard,
  });

  const handleMinimizeWindow = useCallback(() => {
    onMinimizeWindow();
  }, [onMinimizeWindow]);

  const handleToggleMaximize = useCallback(() => {
    if (isMaximized) {
      onRestoreWindow();
    } else {
      onMaximizeWindow();
    }
  }, [isMaximized, onMaximizeWindow, onRestoreWindow]);

  const handleToggleForceNextBuild = useCallback(() => {
    setForceNextBuild((current) => !current);
  }, []);
  const outputCollapsed = consoleState !== "open";
  const dirtyTabs = useMemo(
    () => files.tabs.filter((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [files.tabs],
  );
  const isSavingTabs = files.tabs.some((tab) => tab.saving);
  const canSaveFiles = !usingSeed && dirtyTabs.length > 0;

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event("ade:workbench-layout"));
    });
  }, [explorer.collapsed, explorer.fraction, inspector.collapsed, inspector.fraction, outputCollapsed, consoleFraction, isMaximized]);

  const saveTab = useCallback(
    async (tabId: string): Promise<boolean> => {
      if (usingSeed) {
        return false;
      }
      const tab = files.tabs.find((entry) => entry.id === tabId);
      if (!tab || tab.status !== "ready") {
        return false;
      }
      if (tab.content === tab.initialContent || tab.saving) {
        return false;
      }
      files.beginSavingTab(tabId);
      try {
        const response = await saveConfigFile.mutateAsync({
          path: tab.id,
          content: tab.content,
          etag: tab.etag ?? undefined,
          create: !tab.etag,
          parents: true,
        });
        const metadata = {
          size: response.size ?? tab.metadata?.size ?? null,
          modifiedAt: response.mtime ?? tab.metadata?.modifiedAt ?? null,
          contentType: tab.metadata?.contentType ?? null,
          etag: response.etag ?? tab.metadata?.etag ?? null,
        };
        files.completeSavingTab(tabId, {
          etag: response.etag ?? tab.etag ?? null,
          metadata,
        });
        showConsoleBanner(`Saved ${tab.name}`, { intent: "success", duration: 4000 });
        return true;
      } catch (error) {
        const isConcurrencyError = error instanceof ApiError && error.status === 412;
        const failure = isConcurrencyError
          ? new Error("Save blocked because this file changed on the server. Reloading latest version.")
          : error;
        files.failSavingTab(tabId, failure instanceof Error ? failure.message : String(failure));
        if (isConcurrencyError) {
          try {
            await reloadFileFromServer(tabId);
            showConsoleBanner("File reloaded with the latest version from the server. Review before saving again.", {
              intent: "warning",
              duration: 6000,
            });
          } catch (reloadError) {
            pushConsoleError(reloadError);
          }
        }
        pushConsoleError(failure);
        return false;
      }
    },
    [usingSeed, files, saveConfigFile, showConsoleBanner, reloadFileFromServer, pushConsoleError],
  );

  const saveTabsSequentially = useCallback(
    async (tabIds: readonly string[]) => {
      const saved: string[] = [];
      for (const id of tabIds) {
        const result = await saveTab(id);
        if (result) {
          saved.push(id);
        }
      }
      return saved;
    },
    [saveTab],
  );

  const handleSaveTabShortcut = useCallback(
    (tabId: string) => {
      void saveTab(tabId);
    },
    [saveTab],
  );

  const handleSaveActiveTab = useCallback(() => {
    if (!files.activeTab) {
      return;
    }
    void saveTab(files.activeTab.id);
  }, [files.activeTab, saveTab]);

  const handleSaveAllTabs = useCallback(() => {
    if (!canSaveFiles) {
      return;
    }
    const ids = dirtyTabs.map((tab) => tab.id);
    void (async () => {
      const saved = await saveTabsSequentially(ids);
      if (saved.length > 1) {
        showConsoleBanner(`Saved ${saved.length} files`, { intent: "success", duration: 5000 });
      }
    })();
  }, [canSaveFiles, dirtyTabs, saveTabsSequentially, showConsoleBanner]);

  useEffect(() => {
    const node = paneAreaEl;
    if (!node || typeof window === "undefined") {
      return;
    }

    const measure = () => {
      const rect = node.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      setLayoutSize({
        width,
        height,
      });
      window.dispatchEvent(new Event("ade:workbench-layout"));
    };

    measure();

    if (typeof window.ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }

    const observer = new window.ResizeObserver(() => measure());
    observer.observe(node);
    return () => observer.disconnect();
  }, [paneAreaEl]);

  const consoleLimits = useMemo(() => {
    const container = Math.max(0, layoutSize.height);
    const maxPx = Math.min(OUTPUT_LIMITS.max, Math.max(0, container - MIN_EDITOR_HEIGHT - OUTPUT_HANDLE_THICKNESS));
    const minPx = Math.min(MIN_CONSOLE_HEIGHT, maxPx);
    return { container, minPx, maxPx };
  }, [layoutSize.height]);

  const clampConsoleHeight = useCallback(
    (height: number, limits = consoleLimits) => clamp(height, limits.minPx, limits.maxPx),
    [consoleLimits],
  );

  const resolveInitialConsoleFraction = useCallback(() => {
    const stored = initialConsolePrefsRef.current;
    if (stored && "version" in stored && stored.version === 2 && typeof stored.fraction === "number") {
      return clamp(stored.fraction, 0, 1);
    }
    if (stored && "height" in stored && typeof stored.height === "number" && consoleLimits.container > 0) {
      return clamp(stored.height / consoleLimits.container, 0, 1);
    }
    return 0.25;
  }, [consoleLimits.container]);

  useEffect(() => {
    if (consoleFraction === null && consoleLimits.container > 0) {
      setConsoleFraction(resolveInitialConsoleFraction());
    }
  }, [consoleFraction, consoleLimits.container, resolveInitialConsoleFraction]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const updateModifierState = (event: KeyboardEvent) => {
      setForceModifierActive(event.shiftKey || event.altKey);
    };
    const resetModifiers = () => setForceModifierActive(false);
    window.addEventListener("keydown", updateModifierState);
    window.addEventListener("keyup", updateModifierState);
    window.addEventListener("blur", resetModifiers);
    return () => {
      window.removeEventListener("keydown", updateModifierState);
      window.removeEventListener("keyup", updateModifierState);
      window.removeEventListener("blur", resetModifiers);
    };
  }, []);

  const openConsole = useCallback(() => {
    if (consoleLimits.container > 0 && consoleLimits.maxPx < MIN_CONSOLE_HEIGHT) {
      setConsole("closed");
      showConsoleBanner(CONSOLE_COLLAPSE_MESSAGE, { intent: "warning", duration: 10000 });
      return false;
    }
    clearConsoleBanners();
    setConsole("open");
    setConsoleFraction((current) => {
      if (current !== null) {
        return clamp(current, 0, 1);
      }
      return resolveInitialConsoleFraction();
    });
    return true;
  }, [consoleLimits, setConsole, showConsoleBanner, clearConsoleBanners, resolveInitialConsoleFraction]);

  const closeConsole = useCallback(() => {
    setConsole("closed");
    clearConsoleBanners();
  }, [setConsole, clearConsoleBanners]);

  useEffect(() => {
    if (hasHydratedConsoleState) {
      return;
    }
    const storedState = initialConsolePrefsRef.current?.state;
    if (consoleExplicit || !storedState) {
      setHasHydratedConsoleState(true);
      return;
    }
    if (storedState === "open" || storedState === "closed") {
      if (storedState !== consoleState) {
        setConsole(storedState);
      }
    }
    setHasHydratedConsoleState(true);
  }, [consoleExplicit, consoleState, setConsole, hasHydratedConsoleState]);

  useEffect(() => {
    if (!consolePersistence || isResizingConsole || consoleFraction === null) {
      return;
    }
    consolePersistence.set<ConsolePanelPreferences>({
      version: 2,
      fraction: clamp(consoleFraction, 0, 1),
      state: consoleState,
    });
  }, [consolePersistence, consoleFraction, consoleState, isResizingConsole]);

  useEffect(() => {
    if (consoleState !== "open" || !consoleLimits.container) {
      return;
    }
    if (consoleLimits.maxPx < MIN_CONSOLE_HEIGHT) {
      setConsole("closed");
      showConsoleBanner(CONSOLE_COLLAPSE_MESSAGE, { intent: "warning", duration: 10000 });
      return;
    }
    setConsoleFraction((current) => {
      if (current === null) {
        return resolveInitialConsoleFraction();
      }
      return clamp(current, 0, 1);
    });
  }, [consoleState, consoleLimits, setConsole, showConsoleBanner, resolveInitialConsoleFraction]);

  const deriveSideBounds = useCallback(
    (availableWidth: number, limits: { min: number; max: number }): SideBounds => {
      if (availableWidth <= 0) {
        return { minPx: limits.min, maxPx: limits.max, minFrac: 0, maxFrac: 1 };
      }
      const minPx = Math.min(limits.min, availableWidth);
      const maxPx = Math.min(limits.max, availableWidth);
      return {
        minPx,
        maxPx,
        minFrac: minPx / availableWidth,
        maxFrac: maxPx / availableWidth,
      };
    },
    [],
  );

  const contentWidth = Math.max(0, layoutSize.width - ACTIVITY_BAR_WIDTH);
  const explorerBounds = useMemo(() => deriveSideBounds(contentWidth, EXPLORER_LIMITS), [contentWidth, deriveSideBounds]);
  const inspectorBounds = useMemo(
    () => deriveSideBounds(contentWidth, INSPECTOR_LIMITS),
    [contentWidth, deriveSideBounds],
  );

  const clampSideFraction = useCallback((fraction: number, bounds: SideBounds) => clamp(fraction, bounds.minFrac, bounds.maxFrac), []);

  useEffect(() => {
    if (contentWidth <= 0) {
      return;
    }
    setExplorer((prev) => {
      if (prev.collapsed) {
        return prev;
      }
      const next = clampSideFraction(prev.fraction, explorerBounds);
      return next === prev.fraction ? prev : { ...prev, fraction: next };
    });
    setInspector((prev) => {
      if (prev.collapsed) {
        return prev;
      }
      const next = clampSideFraction(prev.fraction, inspectorBounds);
      return next === prev.fraction ? prev : { ...prev, fraction: next };
    });
  }, [contentWidth, explorerBounds, inspectorBounds, clampSideFraction]);

  const inspectorVisible = !inspector.collapsed && Boolean(files.activeTab);
  const rawExplorerWidth = explorer.collapsed
    ? 0
    : clamp(explorer.fraction, explorerBounds.minFrac, explorerBounds.maxFrac) * contentWidth;
  const rawInspectorWidth = inspectorVisible
    ? clamp(inspector.fraction, inspectorBounds.minFrac, inspectorBounds.maxFrac) * contentWidth
    : 0;
  let explorerWidth = rawExplorerWidth;
  let inspectorWidth = rawInspectorWidth;
  if (contentWidth > 0) {
    const handleBudget =
      (showExplorerPane ? OUTPUT_HANDLE_THICKNESS : 0) + (inspectorVisible ? OUTPUT_HANDLE_THICKNESS : 0);
    const occupied = rawExplorerWidth + rawInspectorWidth + handleBudget;
    if (occupied > contentWidth) {
      const overflow = occupied - contentWidth;
      const inspectorShrink = Math.min(overflow, Math.max(0, rawInspectorWidth - inspectorBounds.minPx));
      inspectorWidth = rawInspectorWidth - inspectorShrink;
      const remaining = overflow - inspectorShrink;
      if (remaining > 0) {
        const explorerShrink = Math.min(remaining, Math.max(0, rawExplorerWidth - explorerBounds.minPx));
        explorerWidth = rawExplorerWidth - explorerShrink;
      }
    }
  }
  const paneHeight = Math.max(0, consoleLimits.container);
  const defaultFraction = 0.25;
  const desiredFraction =
    consoleFraction ??
    (paneHeight > 0 ? clamp(DEFAULT_CONSOLE_HEIGHT / paneHeight, 0, 1) : defaultFraction);
  const desiredHeight = outputCollapsed ? 0 : desiredFraction * paneHeight;
  const consoleHeight = outputCollapsed
    ? 0
    : paneHeight > 0
      ? clampConsoleHeight(desiredHeight)
      : 0;
  const editorHeight =
    paneHeight > 0
      ? Math.max(MIN_EDITOR_HEIGHT, paneHeight - OUTPUT_HANDLE_THICKNESS - consoleHeight)
      : MIN_EDITOR_HEIGHT;

  useEffect(() => {
    const activeId = files.activeTabId;
    if (!activeId) {
      setFileId(undefined);
      return;
    }
    setFileId(activeId);
  }, [files.activeTabId, setFileId]);

  const startRunStream = useCallback(
    (
      options: RunStreamOptions,
      metadata: RunStreamMetadata,
    ): { readonly startedAt: string; readonly activityId: string } | null => {
      if (
        usingSeed ||
        !tree ||
        filesQuery.isLoading ||
        filesQuery.isError ||
        runningByKind.build ||
        runningByKind.validation ||
        runningByKind.extraction
      ) {
        return null;
      }
      if (metadata.mode === "validation" && validateConfiguration.isPending) {
        return null;
      }
      if (!openConsole()) {
        return null;
      }

      const startedAt = new Date();
      const startedIso = startedAt.toISOString();
      const activityKind: ActivityKind = metadata.mode === "validation" ? "validation" : "extraction";
      const initialLine =
        metadata.mode === "validation"
          ? "Starting ADE run (validate-only)…"
          : "Starting ADE extraction…";
      const { id: activityId } = startActivity(
        activityKind,
        {
          startedAt: startedIso,
          label: metadata.mode === "validation" ? "Validation run" : "Extraction run",
          metadata: {
            documentId: metadata.documentId,
            documentName: metadata.documentName,
            sheetNames: metadata.sheetNames,
          },
          logs: [{ level: "info", message: initialLine, timestamp: formatConsoleTimestamp(startedAt) }],
        },
        { select: true, live: true },
      );
      setLiveActivityId(activityId);
      setPane("console");
      selectActivity(activityId);
      if (metadata.mode === "validation") {
        setValidationState((prev) => ({
          ...prev,
          status: "running",
          lastRunAt: startedIso,
          error: null,
        }));
      }

      const controller = new AbortController();
      consoleStreamRef.current?.abort();
      consoleStreamRef.current = controller;

      void (async () => {
        let currentRunId: string | null = null;
        try {
          for await (const event of streamRun(configId, options, controller.signal)) {
            appendConsoleLine(describeRunEvent(event), activityId);
            if (!isMountedRef.current) {
              return;
            }
            if (isTelemetryEnvelope(event)) {
              continue;
            }
            if (event.type === "run.created") {
              currentRunId = event.run_id;
              patchActivity(activityId, {
                metadata: { ...metadata, runId: event.run_id },
              });
            }
            if (event.type === "run.completed") {
              const notice =
                event.status === "succeeded"
                  ? "ADE run completed successfully."
                  : event.status === "canceled"
                    ? "ADE run canceled."
                    : event.error_message?.trim() || "ADE run failed.";
              const intent: NotificationIntent =
                event.status === "succeeded"
                  ? "success"
                  : event.status === "canceled"
                    ? "info"
                    : "danger";
              showConsoleBanner(notice, { intent });
              completeActivity(
                activityId,
                event.status === "succeeded" ? "succeeded" : event.status === "canceled" ? "canceled" : "failed",
                {
                  finishedAt: new Date().toISOString(),
                  errorMessage: event.error_message ?? null,
                },
              );

              if (metadata.mode === "extraction" && currentRunId) {
                const downloadBase = `/api/v1/runs/${encodeURIComponent(currentRunId)}`;
                patchActivity(activityId, {
                  metadata: { ...metadata, runId: currentRunId },
                  outputLinks: [
                    { label: "Artifact", href: `${downloadBase}/artifact` },
                    { label: "Logs", href: `${downloadBase}/logfile` },
                  ],
                  outputsLoaded: false,
                });
                try {
                  const listing = await fetchRunOutputs(currentRunId);
                  const files = Array.isArray(listing.files) ? listing.files : [];
                  patchActivity(activityId, {
                    outputs: files,
                    outputsLoaded: true,
                  });
                } catch (error) {
                  const message =
                    error instanceof Error ? error.message : "Unable to load run outputs.";
                  patchActivity(activityId, {
                    outputsLoaded: true,
                    errorMessage: message,
                  });
                }
              }
            }
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          pushConsoleError(error);
          completeActivity(activityId, "failed", {
            finishedAt: new Date().toISOString(),
            errorMessage: describeError(error),
          });
        } finally {
          if (consoleStreamRef.current === controller) {
            consoleStreamRef.current = null;
          }
          setLiveActivityId(null);
        }
      })();

      return { startedAt: startedIso, activityId };
    },
    [
      usingSeed,
      tree,
      filesQuery.isLoading,
      filesQuery.isError,
      runningByKind.build,
      runningByKind.validation,
      runningByKind.extraction,
      validateConfiguration.isPending,
      openConsole,
      startActivity,
      setLiveActivityId,
      setPane,
      selectActivity,
      setValidationState,
      configId,
      appendConsoleLine,
      showConsoleBanner,
      completeActivity,
      patchActivity,
      pushConsoleError,
    ],
  );

  const handleRunValidation = useCallback(() => {
    const started = startRunStream({ validate_only: true }, { mode: "validation" });
    if (!started) {
      return;
    }
    const { startedAt, activityId } = started;
    validateConfiguration.mutate(undefined, {
      onSuccess(result) {
        const issues = result.issues ?? [];
        const messages = issues.map((issue) => ({
          level: "error" as const,
          message: issue.message,
          path: issue.path,
        }));
        const activityIssues: ValidationIssue[] = issues.map((issue) => ({
          level: "error",
          message: issue.message,
          path: issue.path,
        }));
        appendActivityIssues(activityId, activityIssues);
        patchActivity(activityId, {
          metadata: { configDigest: result.content_digest ?? null },
          errorCount: activityIssues.length,
        });
        setValidationState({
          status: "success",
          messages,
          lastRunAt: startedAt,
          error: null,
          digest: result.content_digest ?? null,
        });
      },
      onError(error) {
        const message = error instanceof Error ? error.message : "Validation failed.";
        appendActivityIssues(activityId, [{ level: "error", message }]);
        setValidationState({
          status: "error",
          messages: [{ level: "error", message }],
          lastRunAt: startedAt,
          error: message,
          digest: null,
        });
      },
    });
  }, [startRunStream, validateConfiguration, appendActivityIssues, patchActivity, setValidationState]);

  const handleRunExtraction = useCallback(
    (selection: { documentId: string; documentName: string; sheetNames?: readonly string[] }) => {
      const worksheetList = Array.from(new Set((selection.sheetNames ?? []).filter(Boolean)));
      const started = startRunStream(
        {
          input_document_id: selection.documentId,
          input_sheet_names: worksheetList.length ? worksheetList : undefined,
          input_sheet_name: worksheetList.length === 1 ? worksheetList[0] : undefined,
        },
        {
          mode: "extraction",
          documentId: selection.documentId,
          documentName: selection.documentName,
          sheetNames: worksheetList,
        },
      );
      if (started) {
        setRunDialogOpen(false);
      }
    },
    [startRunStream],
  );

  const triggerBuild = useCallback(
    (options?: BuildTriggerOptions) => {
      closeBuildMenu();
      if (
        usingSeed ||
        !tree ||
        filesQuery.isLoading ||
        filesQuery.isError ||
        runningByKind.build ||
        runningByKind.validation ||
        runningByKind.extraction
      ) {
        return;
      }
      if (!openConsole()) {
        return;
      }

      const resolvedForce = typeof options?.force === "boolean" ? options.force : forceModifierActive;
      const resolvedWait = Boolean(options?.wait);

      const startedAt = new Date();
      const startedIso = startedAt.toISOString();
      const { id: activityId } = startActivity(
        "build",
        {
          startedAt: startedIso,
          label: resolvedForce ? "Force rebuild" : "Build environment",
          metadata: { force: resolvedForce, wait: resolvedWait },
          logs: [
            {
              level: resolvedForce ? "warning" : "info",
              message: resolvedForce ? "Force rebuilding environment…" : "Starting configuration build…",
              timestamp: formatConsoleTimestamp(startedAt),
            },
          ],
        },
        { select: true, live: true },
      );
      setLiveActivityId(activityId);
      setPane("console");
      selectActivity(activityId);

      const nowTimestamp = formatConsoleTimestamp(new Date());
      if (resolvedForce) {
        appendConsoleLine({
          level: "warning",
          message: "Force rebuild requested. ADE will recreate the environment from scratch.",
          timestamp: nowTimestamp,
        });
      } else if (resolvedWait) {
        appendConsoleLine({
          level: "info",
          message: "Waiting for any running build to finish before starting.",
          timestamp: nowTimestamp,
        });
      }

      const controller = new AbortController();
      consoleStreamRef.current?.abort();
      consoleStreamRef.current = controller;

      void (async () => {
        try {
          for await (const event of streamBuild(
            workspaceId,
            configId,
            { force: resolvedForce, wait: resolvedWait },
            controller.signal,
          )) {
            appendConsoleLine(describeBuildEvent(event), activityId);
            if (!isMountedRef.current) {
              return;
            }
            if (event.type === "build.created") {
              patchActivity(activityId, {
                metadata: { force: resolvedForce, wait: resolvedWait, buildId: event.build_id },
              });
            }
            if (event.type === "build.completed") {
              const summary = event.summary?.trim();
              const status: Activity["status"] =
                event.status === "active"
                  ? "succeeded"
                  : event.status === "canceled"
                    ? "canceled"
                    : event.status === "failed"
                      ? "failed"
                      : "running";
              if (summary && /reused/i.test(summary)) {
                appendConsoleLine({
                  level: "info",
                  message: "Environment reused. Hold Shift or open the build menu to force a rebuild.",
                  timestamp: formatConsoleTimestamp(new Date()),
                });
                showConsoleBanner(
                  "Environment already up to date. Hold Shift or use the menu to force rebuild.",
                  { intent: "info" },
                );
              } else {
                const notice =
                  event.status === "active"
                    ? summary || "Build completed successfully."
                    : event.status === "canceled"
                      ? "Build canceled."
                      : event.error_message?.trim() || "Build failed.";
                  const intent: NotificationIntent =
                    event.status === "active"
                      ? "success"
                      : event.status === "canceled"
                        ? "info"
                        : "danger";
                showConsoleBanner(notice, { intent });
              }
              completeActivity(activityId, status, {
                finishedAt: new Date().toISOString(),
                summary: event.summary ?? null,
                errorMessage: event.error_message ?? null,
              });
            }
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          pushConsoleError(error);
          completeActivity(activityId, "failed", {
            finishedAt: new Date().toISOString(),
            errorMessage: describeError(error),
          });
        } finally {
          if (consoleStreamRef.current === controller) {
            consoleStreamRef.current = null;
          }
          setLiveActivityId(null);
        }
      })();
    },
    [
      usingSeed,
      tree,
      filesQuery.isLoading,
      filesQuery.isError,
      runningByKind.build,
      runningByKind.validation,
      runningByKind.extraction,
      closeBuildMenu,
      openConsole,
      forceModifierActive,
      startActivity,
      setLiveActivityId,
      setPane,
      selectActivity,
      appendConsoleLine,
      workspaceId,
      configId,
      pushConsoleError,
      patchActivity,
      completeActivity,
      showConsoleBanner,
    ],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      const usesPrimary = isMacPlatform ? event.metaKey : event.ctrlKey;
      if (!usesPrimary || event.altKey) {
        return;
      }
      if (event.key.toLowerCase() !== "b") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          (target as HTMLElement).isContentEditable
        ) {
          return;
        }
      }
      event.preventDefault();
      triggerBuild({ force: event.shiftKey, source: "shortcut" });
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [triggerBuild, isMacPlatform]);

  const handleRerunActivity = useCallback(
    (activity: Activity) => {
      if (activity.kind === "build") {
        if (!canBuildEnvironment) {
          return;
        }
        triggerBuild({ force: activity.metadata?.force });
        return;
      }
      if (activity.kind === "validation") {
        if (!canRunValidation) {
          return;
        }
        handleRunValidation();
        return;
      }
      if (activity.kind === "extraction") {
        const meta = activity.metadata;
        if (!meta?.documentId || !canRunExtraction) {
          return;
        }
        handleRunExtraction({
          documentId: meta.documentId,
          documentName: meta.documentName ?? "Document",
          sheetNames: meta.sheetNames,
        });
      }
    },
    [canBuildEnvironment, canRunValidation, canRunExtraction, triggerBuild, handleRunValidation, handleRunExtraction],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      const usesPrimary = isMacPlatform ? event.metaKey : event.ctrlKey;
      if (!usesPrimary || event.altKey) {
        return;
      }
      if (event.key.toLowerCase() !== "s") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable) {
          return;
        }
      }
      if (!canSaveFiles) {
        return;
      }
      event.preventDefault();
      handleSaveActiveTab();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isMacPlatform, canSaveFiles, handleSaveActiveTab]);

  const runningBuild = runningByKind.build;
  const runningValidation = runningByKind.validation;
  const runningExtraction = runningByKind.extraction;

  const isStreamingBuild = Boolean(runningBuild);
  const isStreamingValidationRun = Boolean(runningValidation);
  const isStreamingExtraction = Boolean(runningExtraction);
  const isStreamingRun = isStreamingValidationRun || isStreamingExtraction;
  const isStreamingAny = isStreamingRun || isStreamingBuild;

  const isRunningValidation =
    validationState.status === "running" || validateConfiguration.isPending || isStreamingValidationRun;
  const canRunValidation =
    !usingSeed &&
    Boolean(tree) &&
    !filesQuery.isLoading &&
    !filesQuery.isError &&
    !isStreamingAny &&
    !validateConfiguration.isPending &&
    validationState.status !== "running";

  const isRunningExtraction = isStreamingExtraction;
  const canRunExtraction =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !isStreamingAny;

  const isBuildingEnvironment = isStreamingBuild;
  const canBuildEnvironment =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !isStreamingAny;

  const preflightItems = useMemo<PreflightItem[]>(() => {
    const items: PreflightItem[] = [];
    if (canSaveFiles) {
      items.push({
        id: "unsaved",
        label: `${dirtyTabs.length.toLocaleString()} file${dirtyTabs.length === 1 ? "" : "s"} have unsaved changes`,
        hint: "Save before running validation or extraction",
        state: isSavingTabs ? "running" : "action",
        actionLabel: "Save all",
        onAction: handleSaveAllTabs,
      });
    } else {
      items.push({
        id: "unsaved",
        label: "All changes saved",
        hint: "Editor files are up to date",
        state: "ok",
      });
    }

    const lastBuildStatus = latestBuildActivity?.status;
    const buildState: PreflightItemState =
      isBuildingEnvironment ? "running" : lastBuildStatus === "succeeded" ? "ok" : "action";
    items.push({
      id: "environment",
      label: lastBuildStatus === "succeeded" ? "Environment is ready" : "Build required",
      hint:
        lastBuildStatus === "succeeded"
          ? latestBuildActivity?.summary ?? "Ready to validate or extract"
          : "Build to refresh the ADE environment.",
      state: buildState,
      actionLabel: buildState === "ok" ? undefined : "Build environment",
      onAction: buildState === "ok" ? undefined : () => triggerBuild({ force: forceNextBuild || forceModifierActive }),
      disabled: !canBuildEnvironment || isBuildingEnvironment,
    });

    return items;
  }, [
    canSaveFiles,
    dirtyTabs.length,
    isSavingTabs,
    handleSaveAllTabs,
    latestBuildActivity?.status,
    latestBuildActivity?.summary,
    isBuildingEnvironment,
    triggerBuild,
    forceNextBuild,
    forceModifierActive,
    canBuildEnvironment,
  ]);

  useEffect(() => {
    const needsAttention = preflightItems.some((item) => item.state === "action");
    if (needsAttention) {
      setPreflightOpen(true);
    }
  }, [preflightItems]);

  const primaryPreflightAction = preflightItems.find((item) => item.state === "action");

  const handleSelectActivityView = useCallback((view: ActivityBarView) => {
    setActivityView(view);
    if (view === "explorer") {
      setExplorer((prev) => ({ ...prev, collapsed: false }));
    }
  }, []);

  const handleOpenSettingsMenu = useCallback((event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    setSettingsMenu({ x: rect.right + 8, y: rect.top });
  }, []);

  const closeSettingsMenu = useCallback(() => setSettingsMenu(null), []);

  const handleToggleOutput = useCallback(() => {
    if (outputCollapsed) {
      void openConsole();
    } else {
      closeConsole();
    }
  }, [outputCollapsed, openConsole, closeConsole]);

  const handleToggleExplorer = useCallback(() => {
    setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed }));
  }, []);

  const handleHideExplorer = useCallback(() => {
    setExplorer((prev) => ({ ...prev, collapsed: true }));
  }, []);

  const handleToggleInspectorVisibility = useCallback(() => {
    setInspector((prev) => ({ ...prev, collapsed: !prev.collapsed }));
  }, []);

  const settingsMenuItems = useMemo<ContextMenuItem[]>(() => {
    const blankIcon = <span className="inline-block h-4 w-4 opacity-0" />;
    const items: ContextMenuItem[] = THEME_MENU_OPTIONS.map((option) => ({
      id: `theme-${option.value}`,
      label: `${option.label} theme`,
      icon: editorTheme.preference === option.value ? <MenuIconCheck /> : blankIcon,
      onSelect: () => editorTheme.setPreference(option.value),
    }));
    items.push(
      {
        id: "toggle-explorer",
        label: explorer.collapsed ? "Show Explorer" : "Hide Explorer",
        dividerAbove: true,
        icon: explorer.collapsed ? blankIcon : <MenuIconCheck />,
        onSelect: () => setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed })),
      },
      {
        id: "toggle-inspector",
        label: inspector.collapsed ? "Show Inspector" : "Hide Inspector",
        icon: inspector.collapsed ? blankIcon : <MenuIconCheck />,
        onSelect: () => setInspector((prev) => ({ ...prev, collapsed: !prev.collapsed })),
      },
      {
        id: "toggle-console",
        label: outputCollapsed ? "Show Console" : "Hide Console",
        icon: outputCollapsed ? blankIcon : <MenuIconCheck />,
        onSelect: handleToggleOutput,
      },
    );
    return items;
  }, [
    editorTheme,
    explorer.collapsed,
    inspector.collapsed,
    outputCollapsed,
    handleToggleOutput,
  ]);

  useEffect(() => {
    if (typeof document === "undefined" || !isMaximized) {
      return;
    }
    const previous = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.documentElement.style.overflow = previous || "";
    };
  }, [isMaximized]);

  const workspaceLabel = formatWorkspaceLabel(workspaceId);
  const saveShortcutLabel = isMacPlatform ? "⌘S" : "Ctrl+S";
  const buildShortcutLabel = isMacPlatform ? "⌘B" : "Ctrl+B";
  const forceShortcutLabel = isMacPlatform ? "⇧⌘B" : "Ctrl+Shift+B";
  const buildMenuItems = useMemo<ContextMenuItem[]>(() => {
    const disabled = !canBuildEnvironment;
    return [
      {
        id: "build-default",
        label: "Build / reuse environment",
        shortcut: buildShortcutLabel,
        disabled,
        onSelect: () => triggerBuild(),
      },
      {
        id: "build-force",
        label: "Force rebuild now",
        shortcut: forceShortcutLabel,
        disabled,
        onSelect: () => triggerBuild({ force: true }),
      },
      {
        id: "build-force-wait",
        label: "Force rebuild after current build",
        disabled,
        onSelect: () => triggerBuild({ force: true, wait: true }),
      },
    ];
  }, [buildShortcutLabel, forceShortcutLabel, canBuildEnvironment, triggerBuild]);

  if (!seed && filesQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration files"
        description="Fetching workspace configuration files for the workbench."
      />
    );
  }

  if (!seed && filesQuery.isError) {
    return (
      <PageState
        variant="error"
        title="Unable to load configuration files"
        description="Try reloading the page or check your connection."
      />
    );
  }

  if (!tree) {
    return (
      <PageState
        variant="empty"
        title="No configuration files found"
        description="Create files in the ADE configuration package to begin editing."
      />
    );
  }
  const rootSurfaceClass = isMaximized
    ? menuAppearance === "dark"
      ? "bg-[#0f111a] text-white"
      : "bg-slate-50 text-slate-900"
    : menuAppearance === "dark"
      ? "bg-transparent text-white"
      : "bg-transparent text-slate-900";
  const editorSurface = menuAppearance === "dark" ? "#1b1f27" : "#ffffff";
  const editorText = menuAppearance === "dark" ? "#f5f6fb" : "#0f172a";
  const windowFrameClass = isMaximized
    ? clsx(
        "fixed inset-0 z-[90] flex flex-col",
        menuAppearance === "dark" ? "bg-[#0f111a] text-white" : "bg-white text-slate-900",
      )
    : clsx(
        "flex w-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
        menuAppearance === "dark" ? "bg-[#101322] text-white" : "bg-white text-slate-900",
      );

  return (
    <div className={clsx("flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden", rootSurfaceClass)}>
      {isMaximized ? <div className="fixed inset-0 z-40 bg-slate-900/60" /> : null}
      <div className={windowFrameClass}>
        <WorkbenchChrome
        configName={configName}
        workspaceLabel={workspaceLabel}
        validationLabel={validationLabel}
        environmentLabel={environmentLabel}
        canSaveFiles={canSaveFiles}
        isSavingFiles={isSavingTabs}
        onSaveFile={handleSaveActiveTab}
        saveShortcutLabel={saveShortcutLabel}
        canBuildEnvironment={canBuildEnvironment}
        isBuildingEnvironment={isBuildingEnvironment}
        onBuildEnvironment={triggerBuild}
        onOpenBuildMenu={openBuildMenu}
        forceModifierActive={forceModifierActive}
        buildShortcutLabel={buildShortcutLabel}
        forceShortcutLabel={forceShortcutLabel}
        canRunValidation={canRunValidation}
        isRunningValidation={isRunningValidation}
        onRunValidation={handleRunValidation}
        canRunExtraction={canRunExtraction}
        isRunningExtraction={isRunningExtraction}
        onRunExtraction={() => {
          if (!canRunExtraction) {
            return;
          }
          setRunDialogOpen(true);
        }}
        explorerVisible={showExplorerPane}
        onToggleExplorer={handleToggleExplorer}
        consoleOpen={!outputCollapsed}
        onToggleConsole={handleToggleOutput}
        inspectorCollapsed={inspector.collapsed}
        onToggleInspector={handleToggleInspectorVisibility}
        appearance={menuAppearance}
        forceNextBuild={forceNextBuild}
        onToggleForceNextBuild={handleToggleForceNextBuild}
        windowState={windowState}
        onMinimizeWindow={handleMinimizeWindow}
        onToggleMaximize={handleToggleMaximize}
        onCloseWindow={handleCloseWorkbench}
      />
        <div ref={setPaneAreaEl} className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
          <ActivityBar
            activeView={activityView}
            onSelectView={handleSelectActivityView}
            onOpenSettings={handleOpenSettingsMenu}
            appearance={menuAppearance}
          />
          {showExplorerPane ? (
            <>
              <div className="flex min-h-0" style={{ width: explorerWidth }}>
                {activityView === "explorer" && files.tree ? (
                  <Explorer
                    width={explorerWidth}
                    tree={files.tree}
                    activeFileId={files.activeTab?.id ?? ""}
                    openFileIds={files.tabs.map((tab) => tab.id)}
                    onSelectFile={(fileId) => {
                      files.openFile(fileId);
                      setFileId(fileId);
                    }}
                    theme={menuAppearance}
                    onCloseFile={files.closeTab}
                    onCloseOtherFiles={files.closeOtherTabs}
                    onCloseTabsToRight={files.closeTabsToRight}
                    onCloseAllFiles={files.closeAllTabs}
                    onHide={handleHideExplorer}
                  />
                ) : (
                  <SidePanelPlaceholder width={explorerWidth} view={activityView} />
                )}
              </div>
              <PanelResizeHandle
                orientation="vertical"
                onPointerDown={(event) => {
                  const startX = event.clientX;
                  const startWidth = explorerWidth;
                  trackPointerDrag(event, {
                    cursor: "col-resize",
                    onMove: (move) => {
                      const delta = move.clientX - startX;
                      const nextWidth = clamp(startWidth + delta, explorerBounds.minPx, explorerBounds.maxPx);
                      setExplorer((prev) =>
                        prev.collapsed || contentWidth <= 0
                          ? prev
                          : { ...prev, fraction: clampSideFraction(nextWidth / contentWidth, explorerBounds) },
                      );
                    },
                  });
                }}
              />
            </>
          ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col" style={{ backgroundColor: editorSurface, color: editorText }}>
          {outputCollapsed ? (
            <EditorArea
              tabs={files.tabs}
              activeTabId={files.activeTab?.id ?? ""}
              onSelectTab={(tabId) => {
                files.selectTab(tabId);
                setFileId(tabId);
              }}
              onCloseTab={files.closeTab}
              onCloseOtherTabs={files.closeOtherTabs}
              onCloseTabsToRight={files.closeTabsToRight}
              onCloseAllTabs={files.closeAllTabs}
              onContentChange={files.updateContent}
              onSaveTab={handleSaveTabShortcut}
              onSaveAllTabs={handleSaveAllTabs}
              onMoveTab={files.moveTab}
              onPinTab={files.pinTab}
              onUnpinTab={files.unpinTab}
              onSelectRecentTab={files.selectRecentTab}
              editorTheme={editorTheme.resolvedTheme}
              menuAppearance={menuAppearance}
              canSaveFiles={canSaveFiles}
              minHeight={MIN_EDITOR_HEIGHT}
            />
          ) : (
            <div
                className="grid min-h-0 min-w-0 flex-1"
                style={{
                height: paneHeight > 0 ? `${paneHeight}px` : undefined,
                gridTemplateRows: `${Math.max(MIN_EDITOR_HEIGHT, editorHeight)}px ${OUTPUT_HANDLE_THICKNESS}px ${Math.max(
                  0,
                  consoleHeight,
                )}px`,
              }}
            >
              <EditorArea
                tabs={files.tabs}
                activeTabId={files.activeTab?.id ?? ""}
                onSelectTab={(tabId) => {
                  files.selectTab(tabId);
                  setFileId(tabId);
                }}
                onCloseTab={files.closeTab}
                onCloseOtherTabs={files.closeOtherTabs}
                onCloseTabsToRight={files.closeTabsToRight}
                onCloseAllTabs={files.closeAllTabs}
                onContentChange={files.updateContent}
                onSaveTab={handleSaveTabShortcut}
                onSaveAllTabs={handleSaveAllTabs}
                onMoveTab={files.moveTab}
                onPinTab={files.pinTab}
                onUnpinTab={files.unpinTab}
                onSelectRecentTab={files.selectRecentTab}
                editorTheme={editorTheme.resolvedTheme}
                menuAppearance={menuAppearance}
                canSaveFiles={canSaveFiles}
                minHeight={MIN_EDITOR_HEIGHT}
              />
              <PanelResizeHandle
                orientation="horizontal"
                onPointerDown={(event) => {
                  setIsResizingConsole(true);
                  const startY = event.clientY;
                  const startHeight = consoleHeight;
                  trackPointerDrag(event, {
                    cursor: "row-resize",
                    onMove: (move) => {
                      if (consoleLimits.maxPx <= 0 || paneHeight <= 0) {
                        return;
                      }
                      const delta = startY - move.clientY;
                      const nextHeight = clamp(startHeight + delta, consoleLimits.minPx, consoleLimits.maxPx);
                      setConsoleFraction(clamp(nextHeight / paneHeight, 0, 1));
                    },
                    onEnd: () => {
                      setIsResizingConsole(false);
                    },
                  });
                }}
              />
              <BottomPanel
                height={Math.max(0, consoleHeight)}
                activities={activityState.activities}
                selectedActivityId={selectedActivityId}
                activePane={pane}
                onPaneChange={setPane}
                onSelectActivity={(activityId) => selectActivity(activityId)}
                onRerunActivity={handleRerunActivity}
                onRunValidation={canRunValidation ? handleRunValidation : undefined}
                onRunExtraction={canRunExtraction ? () => setRunDialogOpen(true) : undefined}
                validationFallback={validationState}
              />
            </div>
          )}
        </div>

        {inspectorVisible ? (
          <>
            <PanelResizeHandle
              orientation="vertical"
              onPointerDown={(event) => {
                const startX = event.clientX;
                const startWidth = inspectorWidth;
                trackPointerDrag(event, {
                  cursor: "col-resize",
                  onMove: (move) => {
                    const delta = startX - move.clientX;
                    const nextWidth = clamp(startWidth + delta, inspectorBounds.minPx, inspectorBounds.maxPx);
                    setInspector((prev) =>
                      prev.collapsed || contentWidth <= 0
                        ? prev
                        : { ...prev, fraction: clampSideFraction(nextWidth / contentWidth, inspectorBounds) },
                    );
                  },
                });
              }}
            />
                    <Inspector width={inspectorWidth} file={files.activeTab ?? null} />
          </>
        ) : null}
      </div>
      </div>
      {runDialogOpen ? (
        <RunExtractionDialog
          open={runDialogOpen}
          workspaceId={workspaceId}
          onClose={() => setRunDialogOpen(false)}
          onRun={handleRunExtraction}
        />
      ) : null}
      <ContextMenu
        open={Boolean(buildMenu)}
        position={buildMenu}
        onClose={closeBuildMenu}
        items={buildMenuItems}
        appearance={menuAppearance}
      />
      <ContextMenu
        open={Boolean(settingsMenu)}
        position={settingsMenu}
        onClose={closeSettingsMenu}
        items={settingsMenuItems}
        appearance={menuAppearance}
      />
    </div>
  );
}

interface SidePanelPlaceholderProps {
  readonly width: number;
  readonly view: ActivityBarView;
}

function SidePanelPlaceholder({ width, view }: SidePanelPlaceholderProps) {
  const label = ACTIVITY_LABELS[view] || "Coming soon";
  return (
    <div
      className="flex h-full min-h-0 flex-col items-center justify-center border-r border-[#111111] bg-[#1e1e1e] px-4 text-center text-[11px] uppercase tracking-wide text-slate-400"
      style={{ width }}
      aria-live="polite"
    >
      {label}
    </div>
  );
}

function MenuIconCheck() {
  return (
    <svg className="h-4 w-4 text-[#4fc1ff]" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 8l3 3 5-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function WorkbenchChrome({
  configName,
  workspaceLabel,
  validationLabel,
  environmentLabel,
  canSaveFiles,
  isSavingFiles,
  onSaveFile,
  saveShortcutLabel,
  canBuildEnvironment,
  isBuildingEnvironment,
  onBuildEnvironment,
  onOpenBuildMenu,
  forceNextBuild,
  forceModifierActive,
  buildShortcutLabel,
  forceShortcutLabel,
  canRunValidation,
  isRunningValidation,
  onRunValidation,
  canRunExtraction,
  isRunningExtraction,
  onRunExtraction,
  explorerVisible,
  onToggleExplorer,
  consoleOpen,
  onToggleConsole,
  inspectorCollapsed,
  onToggleInspector,
  appearance,
  onToggleForceNextBuild,
  windowState,
  onMinimizeWindow,
  onToggleMaximize,
  onCloseWindow,
}: {
  readonly configName: string;
  readonly workspaceLabel: string;
  readonly validationLabel?: string;
  readonly environmentLabel?: string;
  readonly canSaveFiles: boolean;
  readonly isSavingFiles: boolean;
  readonly onSaveFile: () => void;
  readonly saveShortcutLabel: string;
  readonly canBuildEnvironment: boolean;
  readonly isBuildingEnvironment: boolean;
  readonly onBuildEnvironment: (options?: BuildTriggerOptions) => void;
  readonly onOpenBuildMenu: (position: { x: number; y: number }) => void;
  readonly forceNextBuild: boolean;
  readonly forceModifierActive: boolean;
  readonly buildShortcutLabel: string;
  readonly forceShortcutLabel: string;
  readonly canRunValidation: boolean;
  readonly isRunningValidation: boolean;
  readonly onRunValidation: () => void;
  readonly canRunExtraction: boolean;
  readonly isRunningExtraction: boolean;
  readonly onRunExtraction: () => void;
  readonly explorerVisible: boolean;
  readonly onToggleExplorer: () => void;
  readonly consoleOpen: boolean;
  readonly onToggleConsole: () => void;
  readonly inspectorCollapsed: boolean;
  readonly onToggleInspector: () => void;
  readonly appearance: "light" | "dark";
  readonly onToggleForceNextBuild: () => void;
  readonly windowState: WorkbenchWindowState;
  readonly onMinimizeWindow: () => void;
  readonly onToggleMaximize: () => void;
  readonly onCloseWindow: () => void;
}) {
  const dark = appearance === "dark";
  const surfaceClass = dark
    ? "border-white/10 bg-[#151821] text-white"
    : "border-slate-200 bg-white text-slate-900";
  const metaTextClass = dark ? "text-white/60" : "text-slate-500";
  const buildButtonClass = dark
    ? "bg-white/10 text-white hover:bg-white/20 disabled:bg-white/10 disabled:text-white/40"
    : "bg-slate-100 text-slate-900 hover:bg-slate-200 disabled:bg-slate-50 disabled:text-slate-400";
  const saveButtonClass = dark
    ? "bg-emerald-400/20 text-emerald-50 hover:bg-emerald-400/30 disabled:bg-white/10 disabled:text-white/30"
    : "bg-emerald-500 text-white hover:bg-emerald-400 disabled:bg-slate-200 disabled:text-slate-500";
  const runButtonClass = dark
    ? "bg-brand-500 text-white hover:bg-brand-400 disabled:bg-white/20 disabled:text-white/40"
    : "bg-brand-600 text-white hover:bg-brand-500 disabled:bg-slate-200 disabled:text-slate-500";
  const isMaximized = windowState === "maximized";
  const forceIntentActive = forceNextBuild || forceModifierActive;
  const buildButtonLabel = isBuildingEnvironment
    ? "Building…"
    : forceIntentActive
      ? "Force rebuild"
      : "Build environment";
  const buildButtonTitle = forceIntentActive
    ? `Force rebuild (Shift+Click · ${forceShortcutLabel})`
    : `Build environment (${buildShortcutLabel})`;

  return (
    <div className={clsx("flex items-center justify-between border-b px-4 py-2", surfaceClass)}>
      <div className="flex min-w-0 items-center gap-3">
        <WorkbenchBadgeIcon />
        <div className="min-w-0 leading-tight">
          <div className={clsx("text-[10px] font-semibold uppercase tracking-[0.35em]", metaTextClass)}>
            Config Workbench
          </div>
          <div className="truncate text-sm font-semibold" title={configName}>
            {configName}
          </div>
          <div className={clsx("text-[11px]", metaTextClass)} title={workspaceLabel}>
            Workspace · {workspaceLabel}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {environmentLabel ? <span className={clsx("text-xs", metaTextClass)}>{environmentLabel}</span> : null}
        {validationLabel ? <span className={clsx("text-xs", metaTextClass)}>{validationLabel}</span> : null}
        <button
          type="button"
          onClick={onSaveFile}
          disabled={!canSaveFiles}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            saveButtonClass,
          )}
          title={`Save (${saveShortcutLabel})`}
        >
          {isSavingFiles ? <SpinnerIcon /> : <SaveIcon />}
          {isSavingFiles ? "Saving…" : "Save"}
        </button>
        <SplitButton
          label={buildButtonLabel}
          icon={isBuildingEnvironment ? <SpinnerIcon /> : <BuildIcon />}
          disabled={!canBuildEnvironment}
          isLoading={isBuildingEnvironment}
          highlight={forceIntentActive && !isBuildingEnvironment}
          title={buildButtonTitle}
          primaryClassName={clsx(
            buildButtonClass,
            "rounded-r-none focus-visible:ring-offset-0",
          )}
          menuClassName={clsx(
            buildButtonClass,
            "rounded-l-none px-2",
            dark ? "border-white/20" : "border-slate-300",
          )}
          menuAriaLabel="Open build options"
          onPrimaryClick={(event) =>
            onBuildEnvironment({
              force: event.shiftKey || event.altKey || forceModifierActive,
            })
          }
          onOpenMenu={(position) => onOpenBuildMenu({ x: position.x, y: position.y })}
          onContextMenu={(event) => {
            event.preventDefault();
            onOpenBuildMenu({ x: event.clientX, y: event.clientY });
          }}
        />
        <button
          type="button"
          onClick={onRunValidation}
          disabled={!canRunValidation}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
        >
          {isRunningValidation ? <SpinnerIcon /> : <RunIcon />}
          {isRunningValidation ? "Running…" : "Run validation"}
        </button>
        <button
          type="button"
          onClick={onRunExtraction}
          disabled={!canRunExtraction}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
        >
          {isRunningExtraction ? <SpinnerIcon /> : <RunIcon />}
          {isRunningExtraction ? "Running…" : "Run extraction"}
        </button>
        <ChromeIconButton
          ariaLabel={forceNextBuild ? "Force rebuild enabled for next run" : "Force next rebuild"}
          onClick={onToggleForceNextBuild}
          appearance={appearance}
          active={forceNextBuild}
          icon={<BuildIcon />}
        />
        <div className="flex items-center gap-1">
          <ChromeIconButton
            ariaLabel={explorerVisible ? "Hide explorer" : "Show explorer"}
            onClick={onToggleExplorer}
            appearance={appearance}
            active={explorerVisible}
            icon={<SidebarIcon active={explorerVisible} />}
          />
          <ChromeIconButton
            ariaLabel={inspectorCollapsed ? "Show inspector" : "Hide inspector"}
            onClick={onToggleInspector}
            appearance={appearance}
            active={!inspectorCollapsed}
            icon={<InspectorIcon />}
          />
          <ChromeIconButton
            ariaLabel={consoleOpen ? "Hide console" : "Show console"}
            onClick={onToggleConsole}
            appearance={appearance}
            active={consoleOpen}
            icon={<ConsoleIcon />}
          />
        </div>
        <div
          className={clsx(
            "flex items-center gap-2 border-l pl-3",
            appearance === "dark" ? "border-white/20" : "border-slate-200/70",
          )}
        >
          <ChromeIconButton
            ariaLabel="Minimize workbench"
            onClick={onMinimizeWindow}
            appearance={appearance}
            icon={<MinimizeIcon />}
          />
          <ChromeIconButton
            ariaLabel={isMaximized ? "Restore workbench" : "Maximize workbench"}
            onClick={onToggleMaximize}
            appearance={appearance}
            active={isMaximized}
            icon={isMaximized ? <WindowRestoreIcon /> : <WindowMaximizeIcon />}
          />
          <ChromeIconButton
            ariaLabel="Close workbench"
            onClick={onCloseWindow}
            appearance={appearance}
            icon={<CloseIcon />}
          />
        </div>
      </div>
    </div>
  );
}

interface RunExtractionDialogProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly onClose: () => void;
  readonly onRun: (selection: {
    documentId: string;
    documentName: string;
    sheetNames?: readonly string[];
  }) => void;
}

function RunExtractionDialog({ open, workspaceId, onClose, onRun }: RunExtractionDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const documentsQuery = useQuery<DocumentRecord[]>({
    queryKey: ["builder-documents", workspaceId],
    queryFn: ({ signal }) => fetchRecentDocuments(workspaceId, signal),
    staleTime: 60_000,
  });
  const documents = useMemo(
    () => documentsQuery.data ?? [],
    [documentsQuery.data],
  );
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  useEffect(() => {
    if (!documents.length) {
      setSelectedDocumentId("");
      return;
    }
    setSelectedDocumentId((current) => {
      if (current && documents.some((doc) => doc.id === current)) {
        return current;
      }
      return documents[0]?.id ?? "";
    });
  }, [documents]);

  const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId) ?? null;
  const sheetQuery = useQuery<DocumentSheet[]>({
    queryKey: ["builder-document-sheets", workspaceId, selectedDocumentId],
    queryFn: ({ signal }) => fetchDocumentSheets(workspaceId, selectedDocumentId, signal),
    enabled: Boolean(selectedDocumentId),
    staleTime: 60_000,
  });
  const sheetOptions = useMemo(
    () => sheetQuery.data ?? [],
    [sheetQuery.data],
  );
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  useEffect(() => {
    if (!sheetOptions.length) {
      setSelectedSheets([]);
      return;
    }
    setSelectedSheets((current) =>
      current.filter((name) => sheetOptions.some((sheet) => sheet.name === name)),
    );
  }, [sheetOptions]);

  const normalizedSheetSelection = useMemo(
    () =>
      Array.from(
        new Set(selectedSheets.filter((name) => sheetOptions.some((sheet) => sheet.name === name))),
      ),
    [selectedSheets, sheetOptions],
  );

  const toggleWorksheet = useCallback((name: string) => {
    setSelectedSheets((current) =>
      current.includes(name) ? current.filter((sheet) => sheet !== name) : [...current, name],
    );
  }, []);

  if (!open) {
    return null;
  }

  const runDisabled = !selectedDocument || documentsQuery.isLoading || documentsQuery.isError;
  const sheetsAvailable = sheetOptions.length > 0;

  const content = (
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-slate-900/60 px-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-2xl"
      >
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Select a document</h2>
            <p className="text-sm text-slate-500">
              Choose a workspace document and optional worksheet before running the extractor.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </header>

        {documentsQuery.isError ? (
          <Alert tone="danger">Unable to load documents. Try again later.</Alert>
        ) : documentsQuery.isLoading ? (
          <p className="text-sm text-slate-500">Loading documents…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-slate-500">Upload a document in the workspace to run the extractor.</p>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="builder-run-document-select">
                Document
              </label>
              <Select
                id="builder-run-document-select"
                value={selectedDocumentId}
                onChange={(event) => setSelectedDocumentId(event.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {documents.map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.name}
                  </option>
                ))}
              </Select>
              {selectedDocument ? (
                <p className="text-xs text-slate-500">
                  Uploaded {formatDocumentTimestamp(selectedDocument.created_at)} ·{" "}
                  {(selectedDocument.byte_size ?? 0).toLocaleString()} bytes
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">Worksheet</p>
              {sheetQuery.isLoading ? (
                <p className="text-sm text-slate-500">Loading worksheets…</p>
              ) : sheetQuery.isError ? (
                <Alert tone="warning">
                  <div className="space-y-2">
                    <p className="text-sm text-slate-700">
                      Worksheet metadata is temporarily unavailable. The run will process the entire file unless you retry and
                      pick specific sheets.
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => sheetQuery.refetch()}
                        disabled={sheetQuery.isFetching}
                      >
                        Retry loading
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                        Use all worksheets
                      </Button>
                    </div>
                  </div>
                </Alert>
              ) : sheetsAvailable ? (
                <div className="space-y-3 rounded-lg border border-slate-200 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-slate-700">Worksheets</p>
                      <p className="text-xs text-slate-500">
                        {normalizedSheetSelection.length === 0
                          ? "All worksheets will be processed by default. Select specific sheets to narrow the run."
                          : `${normalizedSheetSelection.length.toLocaleString()} worksheet${
                              normalizedSheetSelection.length === 1 ? "" : "s"
                            } selected.`}
                      </p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                      Use all worksheets
                    </Button>
                  </div>

                  <div className="max-h-48 space-y-2 overflow-auto rounded-md border border-slate-200 p-2">
                    {sheetOptions.map((sheet) => {
                      const checked = normalizedSheetSelection.includes(sheet.name);
                      return (
                        <label
                          key={`${sheet.index}-${sheet.name}`}
                          className="flex items-center gap-2 rounded px-2 py-1 text-sm text-slate-700 hover:bg-slate-100"
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                            checked={checked}
                            onChange={() => toggleWorksheet(sheet.name)}
                          />
                          <span className="flex-1 truncate">
                            {sheet.name}
                            {sheet.is_active ? " (active)" : ""}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500">This file will be ingested directly.</p>
              )}
            </div>
          </div>
        )}

        <footer className="mt-6 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
              onClick={() => {
                if (!selectedDocument) {
                  return;
                }
                onRun({
                  documentId: selectedDocument.id,
                  documentName: selectedDocument.name,
                  sheetNames:
                    normalizedSheetSelection.length > 0 ? normalizedSheetSelection : undefined,
                });
              }}
              disabled={runDisabled}
            >
              Run extraction
          </Button>
        </footer>
      </div>
    </div>
  );

  return typeof document === "undefined" ? null : createPortal(content, document.body);
}

async function fetchRecentDocuments(workspaceId: string, signal?: AbortSignal): Promise<DocumentRecord[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query: { sort: "-created_at", page_size: 50 } },
    signal,
  });
  return ((data as components["schemas"]["DocumentPage"] | undefined)?.items ?? []) as DocumentRecord[];
}

function formatDocumentTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function ChromeIconButton({
  ariaLabel,
  onClick,
  icon,
  appearance,
  active = false,
}: {
  readonly ariaLabel: string;
  readonly onClick: () => void;
  readonly icon: ReactNode;
  readonly appearance: "light" | "dark";
  readonly active?: boolean;
}) {
  const dark = appearance === "dark";
  const baseClass = dark
    ? "text-white/70 hover:text-white hover:bg-white/5 hover:border-white/20 focus-visible:ring-white/40"
    : "text-slate-500 hover:text-slate-900 hover:bg-slate-100 hover:border-slate-300 focus-visible:ring-slate-400/40";
  const activeClass = dark ? "text-white border-white/30 bg-white/10" : "text-slate-900 border-slate-300 bg-slate-200/70";
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      className={clsx(
        "flex h-7 w-7 items-center justify-center rounded-[4px] border border-transparent text-sm transition focus-visible:outline-none focus-visible:ring-2",
        baseClass,
        active && activeClass,
      )}
      title={ariaLabel}
    >
      {icon}
    </button>
  );
}

function WorkbenchBadgeIcon() {
  return (
    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#4fc1ff] via-[#2d7dff] to-[#7c4dff] text-white shadow-lg shadow-[#10121f]">
      <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="9" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="2" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="9" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    </span>
  );
}

function SidebarIcon({ active }: { readonly active: boolean }) {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect
        x="3"
        y="4"
        width="14"
        height="12"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.4"
        opacity={active ? 1 : 0.6}
      />
      <path d="M7 4v12" stroke="currentColor" strokeWidth="1.4" opacity={active ? 1 : 0.6} />
    </svg>
  );
}

function ConsoleIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M3 10.5h10" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function InspectorIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M10 3v10" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function WindowMaximizeIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function WindowRestoreIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4.5 5.5h6v6h-6z" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 4h6v6" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function MinimizeIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 11h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M5 5l6 6M11 5l-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" opacity="0.35" />
      <path d="M20 12a8 8 0 0 0-8-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function BuildIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M11 2.5a2.5 2.5 0 0 0-2.62 3.04L4 9.92 6.08 12l4.58-4.38A2.5 2.5 0 0 0 13.5 5 2.5 2.5 0 0 0 11 2.5Z"
        fill="currentColor"
      />
      <path d="M4 10l2 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function RunIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4.5 3.5v9l7-4.5-7-4.5Z" fill="currentColor" />
    </svg>
  );
}

function SaveIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M4 2.5h7.25L13.5 4.8v8.7H4z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 2.5v4h4v-4" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 11h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return "Operation canceled.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatRelative(timestamp?: string): string {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

function formatWorkspaceLabel(workspaceId: string): string {
  if (workspaceId.length <= 12) {
    return workspaceId;
  }
  return `${workspaceId.slice(0, 6)}…${workspaceId.slice(-4)}`;
}

function decodeFileContent(payload: FileReadJson): string {
  if (payload.encoding === "base64") {
    if (typeof atob === "function") {
      return atob(payload.content);
    }
    const buffer = (globalThis as { Buffer?: { from: (data: string, encoding: string) => { toString: (encoding: string) => string } } }).Buffer;
    if (buffer) {
      return buffer.from(payload.content, "base64").toString("utf-8");
    }
  }
  return payload.content;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/ActivityBar.tsx
```tsx
import React from "react";
import clsx from "clsx";

export type ActivityBarView = "explorer" | "search" | "scm" | "extensions";

interface ActivityBarProps {
  readonly activeView: ActivityBarView;
  readonly onSelectView: (view: ActivityBarView) => void;
  readonly onOpenSettings: (event: React.MouseEvent<HTMLButtonElement>) => void;
  readonly appearance: "light" | "dark";
}

const ITEMS: Array<{ id: ActivityBarView; label: string; icon: React.ReactNode }> = [
  { id: "explorer", label: "Explorer", icon: <ExplorerIcon /> },
  { id: "search", label: "Search", icon: <SearchIcon /> },
  { id: "scm", label: "Source Control", icon: <SourceControlIcon /> },
  { id: "extensions", label: "Extensions", icon: <ExtensionsIcon /> },
];

export function ActivityBar({ activeView, onSelectView, onOpenSettings, appearance }: ActivityBarProps) {
  const theme =
    appearance === "dark"
      ? {
          bg: "bg-[#1b1b1f]",
          border: "border-[#111111]",
          iconIdle: "text-slate-400",
          iconActive: "text-[#4fc1ff]",
          hover: "hover:text-white hover:bg-white/5 focus-visible:text-white",
          indicator: "bg-[#4fc1ff]",
        }
      : {
          bg: "bg-[#f3f3f3]",
          border: "border-[#d0d0d0]",
          iconIdle: "text-slate-500",
          iconActive: "text-[#005fb8]",
          hover: "hover:text-[#0f172a] hover:bg-black/5 focus-visible:text-[#0f172a]",
          indicator: "bg-[#005fb8]",
        };

  return (
    <aside
      className={clsx(
        "flex h-full w-14 flex-col items-center justify-between border-r",
        theme.bg,
        theme.border,
        theme.iconIdle,
      )}
      aria-label="Workbench navigation"
    >
      <div className="flex flex-col items-center gap-1 py-3">
        {ITEMS.map((item) => {
          const active = activeView === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectView(item.id)}
              className={clsx(
                "relative flex h-10 w-10 items-center justify-center rounded-lg text-base transition",
                active ? theme.iconActive : clsx(theme.iconIdle, theme.hover),
              )}
              aria-label={item.label}
              aria-pressed={active}
            >
              {active ? (
                <span className={clsx("absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded", theme.indicator)} />
              ) : null}
              {item.icon}
            </button>
          );
        })}
      </div>
      <div className="flex flex-col items-center gap-3 pb-3">
        <button
          type="button"
          onClick={onOpenSettings}
          className={clsx(
            "flex h-10 w-10 items-center justify-center rounded-lg text-base transition",
            theme.iconIdle,
            theme.hover,
          )}
          aria-label="Open settings"
        >
          <GearIcon />
        </button>
      </div>
    </aside>
  );
}

function ExplorerIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect x="4" y="4" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4 8.25h12" stroke="currentColor" strokeWidth="1.2" />
      <path d="M8.25 4v12" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <circle cx="9" cy="9" r="4.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12.7 12.7l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function SourceControlIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6.5 4a1.75 1.75 0 1 1-1.5 0v12m9-8a1.75 1.75 0 1 1-1.5 0v8"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path d="M5 9.5h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function ExtensionsIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6 4.5h4l4 4v6.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.3"
      />
      <path d="M10 4.5v4h4" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M10 6.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M3 10h2m10 0h2M10 3v2m0 10v2M5.2 5.2l1.4 1.4m7 7 1.4 1.4M14.8 5.2l-1.4 1.4m-7 7-1.4 1.4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/BottomPanel.tsx
```tsx
import clsx from "clsx";

import type { ConfigBuilderPane } from "@app/nav/urlState";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";
import { Button } from "@ui/Button";

import type { Activity, ValidationIssue } from "../state/activityModel";
import type { WorkbenchConsoleLine, WorkbenchValidationState } from "../types";
import { formatConsoleTimestamp } from "../utils/console";

interface BottomPanelProps {
  readonly height: number;
  readonly activities: readonly Activity[];
  readonly selectedActivityId: string | null;
  readonly activePane: ConfigBuilderPane;
  readonly onPaneChange: (pane: ConfigBuilderPane) => void;
  readonly onSelectActivity: (activityId: string) => void;
  readonly onRerunActivity?: (activity: Activity) => void;
  readonly onRunValidation?: () => void;
  readonly onRunExtraction?: () => void;
  readonly validationFallback?: WorkbenchValidationState;
}

export function BottomPanel({
  height,
  activities,
  selectedActivityId,
  activePane,
  onPaneChange,
  onSelectActivity,
  onRerunActivity,
  onRunValidation,
  onRunExtraction,
  validationFallback,
}: BottomPanelProps) {
  const selectedActivity = activities.find((item) => item.id === selectedActivityId) ?? activities[0] ?? null;
  const safePane: ConfigBuilderPane =
    activePane === "console" || activePane === "issues" || activePane === "timeline" ? activePane : "timeline";
  const issues = selectedActivity?.issues ?? [];
  const fallbackIssues: ValidationIssue[] =
    issues.length === 0 && validationFallback
      ? validationFallback.messages.map((message) => ({
          level: message.level,
          message: message.message,
          path: message.path,
        }))
      : [];
  const timeline = activities;
  const consoleLines = selectedActivity?.logs ?? [];

  return (
    <section className="flex min-h-0 flex-col overflow-hidden border-t border-slate-200 bg-slate-50" style={{ height }}>
      <TabsRoot value={safePane} onValueChange={(value) => onPaneChange(value as ConfigBuilderPane)}>
        <div className="flex flex-none items-center justify-between border-b border-slate-200 px-3 py-2">
          <TabsList className="flex items-center gap-2">
            <TabsTrigger value="timeline" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Timeline
            </TabsTrigger>
            <TabsTrigger value="issues" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Issues
            </TabsTrigger>
            <TabsTrigger value="console" className="rounded px-2 py-1 text-xs uppercase tracking-wide">
              Console
            </TabsTrigger>
          </TabsList>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            {selectedActivity ? (
              <span>
                Selected: <strong className="text-slate-800">{formatActivityLabel(selectedActivity)}</strong>
              </span>
            ) : (
              <span>No activity selected</span>
            )}
          </div>
        </div>

        <TabsContent value="timeline" className="flex min-h-0 flex-1 flex-col overflow-auto">
          {timeline.length === 0 ? (
            <EmptyState
              title="No activity yet"
              body="Builds, validations, and extractions will appear here as you run them."
              actionLabel={onRunValidation ? "Run validation" : undefined}
              onAction={onRunValidation}
            />
          ) : (
            <ul className="divide-y divide-slate-200">
              {timeline.map((activity) => (
                <li
                  key={activity.id}
                  className={clsx(
                    "cursor-pointer bg-white px-4 py-3 transition hover:bg-slate-50",
                    activity.id === selectedActivityId ? "ring-1 ring-brand-500/60" : "",
                  )}
                  onClick={() => onSelectActivity(activity.id)}
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <StatusBadge kind={activity.kind} status={activity.status} />
                      <div>
                        <div className="text-sm font-semibold text-slate-900">{formatActivityLabel(activity)}</div>
                        <div className="text-xs text-slate-500">
                          {activity.startedAt ? new Date(activity.startedAt).toLocaleString() : "Just now"}
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                      {activity.metadata?.documentName ? <span>Doc: {activity.metadata.documentName}</span> : null}
                      {activity.metadata?.sheetNames?.length ? (
                        <span>Sheets: {activity.metadata.sheetNames.join(", ")}</span>
                      ) : null}
                      {typeof activity.errorCount === "number" ? (
                        <span className="text-danger-600">{activity.errorCount} errors</span>
                      ) : null}
                      {typeof activity.warningCount === "number" ? (
                        <span className="text-amber-600">{activity.warningCount} warnings</span>
                      ) : null}
                      {activity.summary ? <span className="text-slate-500">{activity.summary}</span> : null}
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-slate-500">
                      <span>{statusLabel(activity.status)}</span>
                      {activity.finishedAt ? <span>· Finished {formatRelative(activity.finishedAt)}</span> : null}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {activity.outputLinks?.map((link) => (
                        <a
                          key={link.href}
                          href={link.href}
                          onClick={(event) => event.stopPropagation()}
                          className="rounded border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                        >
                          {link.label}
                        </a>
                      ))}
                      {onRerunActivity && activity.status !== "running" ? (
                        <Button
                          size="xs"
                          variant="secondary"
                          onClick={(event) => {
                            event.stopPropagation();
                            onRerunActivity(activity);
                          }}
                        >
                          Re-run
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </TabsContent>

        <TabsContent value="issues" className="flex min-h-0 flex-1 flex-col overflow-auto px-3 py-2 text-sm">
          <IssuesPanel
            issues={issues.length > 0 ? issues : fallbackIssues}
            lastRunAt={selectedActivity?.finishedAt ?? validationFallback?.lastRunAt}
            onRunValidation={onRunValidation}
          />
        </TabsContent>

        <TabsContent value="console" className="flex min-h-0 flex-1 flex-col">
          <ConsolePanel activity={selectedActivity} consoleLines={consoleLines} onRunExtraction={onRunExtraction} />
        </TabsContent>
      </TabsRoot>
    </section>
  );
}

function ConsolePanel({
  activity,
  consoleLines,
  onRunExtraction,
}: {
  readonly activity: Activity | null;
  readonly consoleLines: readonly WorkbenchConsoleLine[];
  readonly onRunExtraction?: () => void;
}) {
  const hasConsoleLines = consoleLines.length > 0;
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-slate-900/80 bg-slate-950 font-mono text-[13px] leading-relaxed text-slate-100 shadow-inner shadow-black/30">
      <div className="flex flex-none items-center justify-between gap-3 border-b border-white/5 bg-slate-950/80 px-4 py-2 text-[11px] uppercase tracking-[0.35em] text-slate-500">
        <div className="flex items-center gap-2">
          <span className="font-semibold tracking-[0.45em] text-slate-200">{activity ? activity.kind : "Terminal"}</span>
          <span className="text-[10px] tracking-[0.45em] text-emerald-400">live</span>
        </div>
        {activity?.outputs?.length ? (
          <div className="flex items-center gap-2 text-[11px] text-slate-300">
            {activity.outputLinks?.map((link) => (
              <a key={link.href} href={link.href} className="underline decoration-dotted underline-offset-4">
                {link.label}
              </a>
            ))}
          </div>
        ) : null}
      </div>
      <div className="flex-1 overflow-auto">
        {activity?.outputs?.length ? <RunSummary outputs={activity.outputs} /> : null}
        {hasConsoleLines ? (
          <ul className="divide-y divide-white/5">
            {consoleLines.map((line, index) => (
              <li
                key={`${line.timestamp ?? index}-${line.message}`}
                className="grid grid-cols-[auto_auto_1fr] items-baseline gap-4 px-4 py-2"
              >
                <span className="text-[11px] text-slate-500 tabular-nums whitespace-nowrap">
                  {formatConsoleTimestamp(line.timestamp)}
                </span>
                <span className={clsx("text-[11px] uppercase tracking-[0.3em]", consoleLevelClass(line.level))}>
                  {consoleLevelLabel(line.level)}
                </span>
                <span className="flex flex-wrap items-baseline gap-2 text-[13px] text-slate-100">
                  <span className={clsx("text-sm", consolePromptClass(line.level))}>$</span>
                  <span className={clsx("flex-1 whitespace-pre-wrap break-words", consoleLineClass(line.level))}>
                    {line.message}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-8 text-center text-[13px] text-slate-500">
            <p className="tracking-wide text-slate-300">Waiting for ADE output…</p>
            <p className="text-[12px] leading-relaxed text-slate-500">
              Start a build or run validation to stream live logs in this terminal window.
            </p>
            {onRunExtraction ? (
              <Button size="xs" variant="secondary" onClick={onRunExtraction}>
                Run extraction
              </Button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

function IssuesPanel({
  issues,
  lastRunAt,
  onRunValidation,
}: {
  readonly issues: readonly ValidationIssue[];
  readonly lastRunAt?: string;
  readonly onRunValidation?: () => void;
}) {
  const errorCount = issues.filter((issue) => issue.level === "error").length;
  const warningCount = issues.filter((issue) => issue.level === "warning").length;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>
          {errorCount} errors • {warningCount} warnings
        </span>
        {lastRunAt ? <span>Last run {formatRelative(lastRunAt)}</span> : null}
      </div>
      {issues.length > 0 ? (
        <ul className="space-y-2">
          {issues.map((item, index) => {
            const key = `${item.level}-${item.path ?? index}-${index}`;
            return (
              <li key={key} className={clsx("rounded-md border px-3 py-2", issueMessageClass(item.level))}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {item.path ?? "General"}
                    </div>
                    <div className="text-sm text-slate-800">{item.message}</div>
                  </div>
                  {item.ruleId ? <span className="text-[11px] uppercase text-slate-500">{item.ruleId}</span> : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState
          title="No issues found"
          body="Run validation to check this configuration."
          actionLabel={onRunValidation ? "Run validation" : undefined}
          onAction={onRunValidation}
        />
      )}
    </div>
  );
}

function RunSummary({ outputs }: { readonly outputs: readonly { path: string; byte_size: number }[] }) {
  return (
    <div className="border-b border-white/5 bg-slate-900/60 px-4 py-3 text-[13px] text-slate-100">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-slate-300">Outputs</p>
      </div>
      {outputs.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs text-slate-100">
          {outputs.map((file) => (
            <li key={file.path} className="flex items-center justify-between gap-2 break-all rounded border border-white/10 px-2 py-1">
              <span className="text-emerald-300">{file.path}</span>
              <span className="text-[11px] text-slate-400">{file.byte_size.toLocaleString()} bytes</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-slate-400">No output files were generated.</p>
      )}
    </div>
  );
}

function StatusBadge({ kind, status }: { readonly kind: Activity["kind"]; readonly status: Activity["status"] }) {
  const tone = statusTone(status);
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold uppercase tracking-wide",
        tone.background,
        tone.text,
      )}
    >
      <span className="h-2 w-2 rounded-full bg-current opacity-70" />
      {kindLabel(kind)} · {statusLabel(status)}
    </span>
  );
}

function EmptyState({
  title,
  body,
  actionLabel,
  onAction,
}: {
  readonly title: string;
  readonly body: string;
  readonly actionLabel?: string;
  readonly onAction?: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-10 text-center text-sm text-slate-500">
      <p className="text-base font-semibold text-slate-700">{title}</p>
      <p className="max-w-xl text-slate-500">{body}</p>
      {actionLabel && onAction ? (
        <Button size="sm" onClick={onAction} variant="secondary">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

const CONSOLE_PROMPTS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-[#569cd6]",
  warning: "text-[#dcdcaa]",
  error: "text-[#f48771]",
  success: "text-[#89d185]",
};

const CONSOLE_LINES: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-slate-100",
  warning: "text-amber-100",
  error: "text-rose-100",
  success: "text-emerald-100",
};

const CONSOLE_LEVELS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "text-slate-400",
  warning: "text-amber-400",
  error: "text-rose-400",
  success: "text-emerald-300",
};

const CONSOLE_LEVEL_LABELS: Record<WorkbenchConsoleLine["level"], string> = {
  info: "INFO",
  warning: "WARN",
  error: "ERROR",
  success: "DONE",
};

function consolePromptClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_PROMPTS[level] ?? CONSOLE_PROMPTS.info;
}

function consoleLineClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LINES[level] ?? CONSOLE_LINES.info;
}

function consoleLevelClass(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LEVELS[level] ?? CONSOLE_LEVELS.info;
}

function consoleLevelLabel(level: WorkbenchConsoleLine["level"]) {
  return CONSOLE_LEVEL_LABELS[level] ?? CONSOLE_LEVEL_LABELS.info;
}

function issueMessageClass(level: ValidationIssue["level"]) {
  switch (level) {
    case "error":
      return "border-danger-200 bg-danger-50 text-danger-700";
    case "warning":
      return "border-amber-200 bg-amber-50 text-amber-700";
    default:
      return "border-slate-200 bg-slate-50 text-slate-700";
  }
}

function statusTone(status: Activity["status"]) {
  switch (status) {
    case "running":
      return { background: "bg-brand-50", text: "text-brand-700" };
    case "succeeded":
      return { background: "bg-emerald-50", text: "text-emerald-700" };
    case "failed":
      return { background: "bg-danger-50", text: "text-danger-700" };
    case "canceled":
      return { background: "bg-slate-100", text: "text-slate-700" };
    default:
      return { background: "bg-slate-100", text: "text-slate-700" };
  }
}

function formatActivityLabel(activity: Activity) {
  const base = kindLabel(activity.kind);
  if (activity.metadata?.documentName && activity.kind === "extraction") {
    return `${base} · ${activity.metadata.documentName}`;
  }
  return activity.label ?? base;
}

function kindLabel(kind: Activity["kind"]) {
  switch (kind) {
    case "build":
      return "Build";
    case "validation":
      return "Validation";
    case "extraction":
      return "Extraction";
    default:
      return "Activity";
  }
}

function statusLabel(status: Activity["status"]) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatRelative(timestamp?: string): string {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

function describeValidationStatus(validation: WorkbenchValidationState): string {
  switch (validation.status) {
    case "running":
      return "Running validation...";
    case "success": {
      if (validation.messages.length === 0) {
        return "Validation completed with no issues.";
      }
      const count = validation.messages.length;
      return `Validation completed with ${count} ${count === 1 ? "issue" : "issues"}.`;
    }
    case "error":
      return validation.error ?? "Validation failed.";
    default:
      return "No validation run yet.";
  }
}

function describeValidationFallback(validation: WorkbenchValidationState): string {
  if (validation.status === "running") {
    return "Validation in progress...";
  }
  if (validation.status === "success") {
    return "No validation issues detected.";
  }
  if (validation.status === "error") {
    return validation.error ?? "Validation failed.";
  }
  return "Trigger validation from the workbench header to see ADE parsing results and manifest issues.";
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/EditorArea.tsx
```tsx
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";

import clsx from "clsx";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, useSortable, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { CodeEditor } from "@ui/CodeEditor";
import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { WorkbenchFileTab } from "../types";

type WorkbenchTabZone = "pinned" | "regular";

const SCROLL_STEP = 220;
const AUTO_SCROLL_THRESHOLD = 64;
const AUTO_SCROLL_SPEED = 14;

interface EditorAreaProps {
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly onSelectTab: (tabId: string) => void;
  readonly onCloseTab: (tabId: string) => void;
  readonly onCloseOtherTabs: (tabId: string) => void;
  readonly onCloseTabsToRight: (tabId: string) => void;
  readonly onCloseAllTabs: () => void;
  readonly onMoveTab: (tabId: string, targetIndex: number, options?: { zone?: WorkbenchTabZone }) => void;
  readonly onPinTab: (tabId: string) => void;
  readonly onUnpinTab: (tabId: string) => void;
  readonly onContentChange: (tabId: string, value: string) => void;
  readonly onSaveTab?: (tabId: string) => void;
  readonly onSaveAllTabs?: () => void;
  readonly onSelectRecentTab: (direction: "forward" | "backward") => void;
  readonly editorTheme: string;
  readonly menuAppearance: "light" | "dark";
  readonly canSaveFiles?: boolean;
  readonly minHeight?: number;
}

export function EditorArea({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onCloseOtherTabs,
  onCloseTabsToRight,
  onCloseAllTabs,
  onMoveTab,
  onPinTab,
  onUnpinTab,
  onContentChange,
  onSaveTab,
  onSaveAllTabs,
  onSelectRecentTab,
  editorTheme,
  menuAppearance,
  canSaveFiles = false,
  minHeight,
}: EditorAreaProps) {
  const hasTabs = tabs.length > 0;
  const [contextMenu, setContextMenu] = useState<{ tabId: string; x: number; y: number } | null>(null);
  const [tabCatalogMenu, setTabCatalogMenu] = useState<{ x: number; y: number } | null>(null);
  const [draggingTabId, setDraggingTabId] = useState<string | null>(null);
  const [scrollShadow, setScrollShadow] = useState({ left: false, right: false });
  const [autoScrollDirection, setAutoScrollDirection] = useState<0 | -1 | 1>(0);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const overflowButtonRef = useRef<HTMLButtonElement | null>(null);

  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0] ?? null,
    [tabs, activeTabId],
  );

  const pinnedTabs = useMemo(() => tabs.filter((tab) => tab.pinned), [tabs]);
  const regularTabs = useMemo(() => tabs.filter((tab) => !tab.pinned), [tabs]);
  const contentTabs = useMemo(() => tabs.slice().sort((a, b) => a.id.localeCompare(b.id)), [tabs]);
  const dirtyTabs = useMemo(
    () => tabs.filter((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [tabs],
  );
  const hasDirtyTabs = dirtyTabs.length > 0;

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    }),
  );

  useEffect(() => {
    if (!hasTabs) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }

      if (event.key.toLowerCase() === "w") {
        if (!activeTabId) {
          return;
        }
        event.preventDefault();
        onCloseTab(activeTabId);
        return;
      }

      if (event.key === "Tab") {
        if (tabs.length < 2) {
          return;
        }
        event.preventDefault();
        onSelectRecentTab(event.shiftKey ? "backward" : "forward");
        return;
      }

      const cycleVisual = (delta: number) => {
        if (tabs.length < 2) {
          return;
        }
        const currentIndex = tabs.findIndex((tab) => tab.id === activeTabId);
        const safeIndex = currentIndex >= 0 ? currentIndex : 0;
        const nextIndex = (safeIndex + delta + tabs.length) % tabs.length;
        const nextTab = tabs[nextIndex];
        if (nextTab) {
          onSelectTab(nextTab.id);
        }
      };

      if (event.key === "PageUp") {
        event.preventDefault();
        cycleVisual(-1);
        return;
      }

      if (event.key === "PageDown") {
        event.preventDefault();
        cycleVisual(1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [hasTabs, tabs, activeTabId, onCloseTab, onSelectTab, onSelectRecentTab]);

  useEffect(() => {
    if (!contextMenu) {
      return;
    }
    if (!tabs.some((tab) => tab.id === contextMenu.tabId)) {
      setContextMenu(null);
    }
  }, [contextMenu, tabs]);

  const handleDragStart = (event: DragStartEvent) => {
    setDraggingTabId(String(event.active.id));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const activeId = event.active.id;
    const overId = event.over?.id;
    if (!overId) {
      setDraggingTabId(null);
      return;
    }
    if (activeId !== overId) {
      const activeIndex = tabs.findIndex((tab) => tab.id === activeId);
      const overIndex = tabs.findIndex((tab) => tab.id === overId);
      if (activeIndex !== -1 && overIndex !== -1) {
        const insertIndex = activeIndex < overIndex ? overIndex + 1 : overIndex;
        const overTab = tabs[overIndex];
        const zone: WorkbenchTabZone = overTab?.pinned ? "pinned" : "regular";
        onMoveTab(String(activeId), insertIndex, { zone });
      }
    }
    setDraggingTabId(null);
  };

  const handleDragCancel = () => {
    setDraggingTabId(null);
  };

  const updateScrollIndicators = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      setScrollShadow({ left: false, right: false });
      return;
    }
    const { scrollLeft, scrollWidth, clientWidth } = container;
    setScrollShadow({
      left: scrollLeft > 2,
      right: scrollLeft + clientWidth < scrollWidth - 2,
    });
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      setScrollShadow({ left: false, right: false });
      return;
    }
    updateScrollIndicators();
    const handleScroll = () => updateScrollIndicators();
    container.addEventListener("scroll", handleScroll);
    window.addEventListener("resize", updateScrollIndicators);
    const observer =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateScrollIndicators) : null;
    observer?.observe(container);
    return () => {
      container.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", updateScrollIndicators);
      observer?.disconnect();
    };
  }, [tabs.length, updateScrollIndicators]);

  useEffect(() => {
    if (!draggingTabId) {
      setAutoScrollDirection(0);
      return;
    }
    const handlePointerMove = (event: PointerEvent) => {
      const container = scrollContainerRef.current;
      if (!container) {
        setAutoScrollDirection(0);
        return;
      }
      const bounds = container.getBoundingClientRect();
      if (event.clientX < bounds.left + AUTO_SCROLL_THRESHOLD) {
        setAutoScrollDirection(-1);
      } else if (event.clientX > bounds.right - AUTO_SCROLL_THRESHOLD) {
        setAutoScrollDirection(1);
      } else {
        setAutoScrollDirection(0);
      }
    };
    window.addEventListener("pointermove", handlePointerMove);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      setAutoScrollDirection(0);
    };
  }, [draggingTabId]);

  useEffect(() => {
    if (!draggingTabId || autoScrollDirection === 0) {
      return;
    }
    let frame: number;
    const step = () => {
      const container = scrollContainerRef.current;
      if (!container) {
        return;
      }
      container.scrollBy({ left: autoScrollDirection * AUTO_SCROLL_SPEED });
      frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [autoScrollDirection, draggingTabId]);

  useEffect(() => {
    if (!activeTabId) {
      return;
    }
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }
    const selector = `[data-tab-id="${escapeAttributeValue(activeTabId)}"]`;
    const target = container.querySelector<HTMLElement>(selector);
    target?.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
  }, [activeTabId, tabs.length]);

  const tabContextItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const currentTab = tabs.find((tab) => tab.id === contextMenu.tabId);
    if (!currentTab) {
      return [];
    }
    const tabIndex = tabs.findIndex((tab) => tab.id === contextMenu.tabId);
    const hasTabsToRight = tabIndex >= 0 && tabIndex < tabs.length - 1;
    const hasMultipleTabs = tabs.length > 1;
    const isDirty = currentTab.status === "ready" && currentTab.content !== currentTab.initialContent;
    const canSaveCurrent = Boolean(onSaveTab) && canSaveFiles && isDirty && !currentTab.saving;
    const canSaveAny = Boolean(onSaveAllTabs) && canSaveFiles && hasDirtyTabs;
    const shortcuts = {
      save: "Ctrl+S",
      saveAll: "Ctrl+Shift+S",
      close: "Ctrl+W",
      closeOthers: "Ctrl+K Ctrl+O",
      closeRight: "Ctrl+K Ctrl+Right",
      closeAll: "Ctrl+K Ctrl+W",
    };
    return [
      {
        id: "save",
        label: currentTab.saving ? "Saving…" : "Save",
        icon: <MenuIconSave />,
        disabled: !canSaveCurrent,
        shortcut: shortcuts.save,
        onSelect: () => onSaveTab?.(currentTab.id),
      },
      {
        id: "save-all",
        label: "Save All",
        icon: <MenuIconSaveAll />,
        disabled: !canSaveAny,
        shortcut: shortcuts.saveAll,
        onSelect: () => onSaveAllTabs?.(),
      },
      {
        id: "pin",
        label: currentTab.pinned ? "Unpin" : "Pin",
        icon: currentTab.pinned ? <MenuIconUnpin /> : <MenuIconPin />,
        dividerAbove: true,
        onSelect: () => (currentTab.pinned ? onUnpinTab(currentTab.id) : onPinTab(currentTab.id)),
      },
      {
        id: "close",
        label: "Close",
        icon: <MenuIconClose />,
        dividerAbove: true,
        shortcut: shortcuts.close,
        onSelect: () => onCloseTab(currentTab.id),
      },
      {
        id: "close-others",
        label: "Close Others",
        icon: <MenuIconCloseOthers />,
        disabled: !hasMultipleTabs,
        shortcut: shortcuts.closeOthers,
        onSelect: () => onCloseOtherTabs(currentTab.id),
      },
      {
        id: "close-right",
        label: "Close Tabs to the Right",
        icon: <MenuIconCloseRight />,
        disabled: !hasTabsToRight,
        shortcut: shortcuts.closeRight,
        onSelect: () => onCloseTabsToRight(currentTab.id),
      },
      {
        id: "close-all",
        label: "Close All",
        icon: <MenuIconCloseAll />,
        dividerAbove: true,
        disabled: tabs.length === 0,
        shortcut: shortcuts.closeAll,
        onSelect: () => onCloseAllTabs(),
      },
    ];
  }, [
    contextMenu,
    tabs,
    hasDirtyTabs,
    canSaveFiles,
    onPinTab,
    onUnpinTab,
    onCloseTab,
    onCloseOtherTabs,
    onCloseTabsToRight,
    onCloseAllTabs,
    onSaveTab,
    onSaveAllTabs,
  ]);

  const tabCatalogItems: ContextMenuItem[] = useMemo(() => {
    if (!hasTabs) {
      return [
        {
          id: "empty",
          label: "No open editors",
          onSelect: () => undefined,
          disabled: true,
        },
      ];
    }
    const items: ContextMenuItem[] = [];
    const appendItem = (tab: WorkbenchFileTab, dividerAbove: boolean) => {
      items.push({
        id: `switch-${tab.id}`,
        label: tab.name,
        icon: tab.pinned ? <MenuIconPin /> : <MenuIconFile />,
        shortcut: tab.id === activeTabId ? "Active" : undefined,
        dividerAbove,
        onSelect: () => onSelectTab(tab.id),
      });
    };
    pinnedTabs.forEach((tab) => appendItem(tab, false));
    regularTabs.forEach((tab, index) => appendItem(tab, index === 0 && pinnedTabs.length > 0));
    return items;
  }, [hasTabs, pinnedTabs, regularTabs, activeTabId, onSelectTab]);

  const scrollTabs = (delta: number) => {
    scrollContainerRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  };

  const openTabListMenu = () => {
    if (typeof window === "undefined") {
      return;
    }
    const anchor = overflowButtonRef.current?.getBoundingClientRect();
    if (!anchor) {
      return;
    }
    setTabCatalogMenu({ x: anchor.left, y: anchor.bottom + 6 });
  };

  if (!hasTabs || !activeTab) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
        Select a file from the explorer to begin editing.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col" style={minHeight ? { minHeight } : undefined}>
      <TabsRoot value={activeTab.id} onValueChange={onSelectTab}>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <SortableContext items={tabs.map((tab) => tab.id)} strategy={horizontalListSortingStrategy}>
            <div className="flex items-center gap-1 border-b border-slate-200 bg-slate-900/5 px-1">
              <ScrollButton
                direction="left"
                disabled={!scrollShadow.left}
                onClick={() => scrollTabs(-SCROLL_STEP)}
              />
              <div className="relative flex min-w-0 flex-1 items-stretch">
                {scrollShadow.left ? <ScrollGradient position="left" /> : null}
                {scrollShadow.right ? <ScrollGradient position="right" /> : null}
                <div
                  ref={scrollContainerRef}
                  className="flex min-w-0 flex-1 overflow-x-auto pb-1"
                  onWheel={(event) => {
                    if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
                      event.preventDefault();
                      scrollContainerRef.current?.scrollBy({ left: event.deltaY });
                    }
                  }}
                >
                  <TabsList className="flex min-h-[2.75rem] flex-1 items-end gap-0 px-1">
                    {tabs.map((tab) => {
                      const isDirty = tab.status === "ready" && tab.content !== tab.initialContent;
                      const isActive = tab.id === activeTab.id;
                      return (
                        <SortableTab
                          key={tab.id}
                          tab={tab}
                          isActive={isActive}
                          isDirty={isDirty}
                          draggingId={draggingTabId}
                          onContextMenu={(event) => {
                            event.preventDefault();
                            setContextMenu({ tabId: tab.id, x: event.clientX, y: event.clientY });
                          }}
                          onCloseTab={onCloseTab}
                        />
                      );
                    })}
                  </TabsList>
                </div>
              </div>
              <ScrollButton
                direction="right"
                disabled={!scrollShadow.right}
                onClick={() => scrollTabs(SCROLL_STEP)}
              />
              <button
                ref={overflowButtonRef}
                type="button"
                className="mx-1 flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition hover:bg-white hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                aria-label="Open editors list"
                onClick={openTabListMenu}
              >
                <ChevronDownIcon />
              </button>
            </div>
          </SortableContext>
        </DndContext>

        {contentTabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="flex min-h-0 min-w-0 flex-1">
            {tab.status === "loading" ? (
              <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
                Loading {tab.name}…
              </div>
            ) : tab.status === "error" ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-sm text-slate-500">
                <p>{tab.error ?? "Unable to load the file."}</p>
                <button
                  type="button"
                  className="rounded bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-500"
                  onClick={() => onSelectTab(tab.id)}
                >
                  Retry loading
                </button>
              </div>
            ) : (
              <div
                className={clsx(
                  "flex min-h-0 min-w-0 flex-1",
                  draggingTabId && "pointer-events-none select-none",
                )}
              >
                <CodeEditor
                  value={tab.content}
                  language={tab.language ?? "plaintext"}
                  path={tab.id}
                  theme={editorTheme}
                  onChange={(value) => onContentChange(tab.id, value ?? "")}
                  onSaveShortcut={() => {
                    if (!canSaveFiles) {
                      return;
                    }
                    onSaveTab?.(tab.id);
                  }}
                />
              </div>
            )}
          </TabsContent>
        ))}
      </TabsRoot>
      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu && { x: contextMenu.x, y: contextMenu.y }}
        onClose={() => setContextMenu(null)}
        items={tabContextItems}
        appearance={menuAppearance}
      />
      <ContextMenu
        open={Boolean(tabCatalogMenu)}
        position={tabCatalogMenu}
        onClose={() => setTabCatalogMenu(null)}
        items={tabCatalogItems}
        appearance={menuAppearance}
      />
    </div>
  );
}

interface SortableTabProps {
  readonly tab: WorkbenchFileTab;
  readonly isActive: boolean;
  readonly isDirty: boolean;
  readonly draggingId: string | null;
  readonly onContextMenu: (event: ReactMouseEvent<HTMLDivElement>) => void;
  readonly onCloseTab: (tabId: string) => void;
}

function SortableTab({ tab, isActive, isDirty, draggingId, onContextMenu, onCloseTab }: SortableTabProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: tab.id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  const showingDrag = isDragging || draggingId === tab.id;
  const isPinned = Boolean(tab.pinned);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={clsx(
        "group relative mr-1 flex min-w-0 items-stretch",
        showingDrag && "opacity-60",
      )}
      data-editor-tab="true"
      onContextMenu={onContextMenu}
      onMouseDown={(event) => {
        if (event.button === 1) {
          event.preventDefault();
          onCloseTab(tab.id);
        }
      }}
      {...attributes}
      {...listeners}
    >
      <TabsTrigger
        value={tab.id}
        data-tab-id={tab.id}
        title={tab.id}
        className={clsx(
          "relative flex min-w-[3rem] max-w-[16rem] items-center gap-2 overflow-hidden rounded-t-lg border px-2 py-1.5 pr-8 text-sm font-medium transition-[background-color,border-color,color] duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50",
          isActive
            ? "border-slate-200 border-b-white bg-white text-slate-900 shadow-[0_1px_0_rgba(15,23,42,0.08)]"
            : "border-transparent border-b-slate-200 text-slate-500 hover:border-slate-200 hover:bg-white/70 hover:text-slate-900",
          isPinned ? "min-w-[4rem] max-w-[8rem] justify-center" : "min-w-[9rem] justify-start px-3",
        )}
      >
        {isPinned ? (
          <span className="flex-none text-[12px]" aria-label="Pinned">
            <PinGlyph filled={isActive} />
          </span>
        ) : null}
        <span className="block min-w-0 flex-1 truncate text-left">{tab.name}</span>
        {tab.status === "loading" ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-slate-400"
            aria-label="Loading"
          >
            ●
          </span>
        ) : null}
        {tab.status === "error" ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-danger-600"
            aria-label="Load failed"
          >
            !
          </span>
        ) : null}
        {tab.saving ? (
          <span className="flex-none" aria-label="Saving" title="Saving changes…">
            <TabSavingSpinner />
          </span>
        ) : null}
        {tab.saveError ? (
          <span
            className="flex-none text-[10px] font-semibold uppercase tracking-wide text-danger-600"
            aria-label="Save failed"
            title={tab.saveError}
          >
            !
          </span>
        ) : null}
        {isDirty ? <span className="flex-none text-xs leading-none text-brand-600">●</span> : null}
      </TabsTrigger>
      <button
        type="button"
        className={clsx(
          "absolute right-1 top-1/2 -translate-y-1/2 rounded p-0.5 text-xs transition focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 focus-visible:ring-offset-white",
          isActive
            ? "text-slate-500 hover:bg-slate-200 hover:text-slate-900"
            : "text-slate-400 opacity-0 group-hover:opacity-100 hover:bg-slate-200 hover:text-slate-700",
        )}
        onClick={(event) => {
          event.stopPropagation();
          onCloseTab(tab.id);
        }}
        aria-label={`Close ${tab.name}`}
      >
        ×
      </button>
    </div>
  );
}

interface ScrollButtonProps {
  readonly direction: "left" | "right";
  readonly disabled: boolean;
  readonly onClick: () => void;
}

function ScrollButton({ direction, disabled, onClick }: ScrollButtonProps) {
  return (
    <button
      type="button"
      className={clsx(
        "flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
        disabled
          ? "cursor-default opacity-30"
          : "hover:bg-white hover:text-slate-900 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900/5",
      )}
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === "left" ? "Scroll tabs left" : "Scroll tabs right"}
    >
      {direction === "left" ? <ChevronLeftIcon /> : <ChevronRightIcon />}
    </button>
  );
}

interface ScrollGradientProps {
  readonly position: "left" | "right";
}

function ScrollGradient({ position }: ScrollGradientProps) {
  return (
    <div
      className={clsx(
        "pointer-events-none absolute top-0 bottom-0 w-8",
        position === "left"
          ? "left-0 bg-gradient-to-r from-slate-100 via-slate-100/70 to-transparent"
          : "right-0 bg-gradient-to-l from-slate-100 via-slate-100/70 to-transparent",
      )}
    />
  );
}

function PinGlyph({ filled }: { readonly filled: boolean }) {
  return filled ? (
    <svg className="h-3 w-3" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6.5 2.5h3l.5 4h2v1.5h-4V13l-1-.5V8H4V6.5h2z"
        fill="currentColor"
        className="text-slate-500"
      />
    </svg>
  ) : (
    <svg className="h-3 w-3" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6.5 2.5h3l.5 4h2v1.5h-4V13l-1-.5V8H4V6.5h2z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        className="text-slate-400"
      />
    </svg>
  );
}

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

function TabSavingSpinner() {
  return (
    <svg className="h-3 w-3 animate-spin text-brand-500" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
      <path
        d="M14 8a6 6 0 0 0-6-6"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MenuIconSave() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M4 2.5h7.5L13.5 5v8.5H4z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 2.5v4h4v-4" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 11h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconSaveAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 3.5h6l3 3v5.5h-9z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 3.5v3.5h3.5v-3.5" stroke="currentColor" strokeWidth="1.2" />
      <path d="M5 11h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path
        d="M6.5 6.5h6l1.5 1.5v4"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        opacity="0.6"
      />
    </svg>
  );
}

function MenuIconClose() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M4 4l8 8m0-8l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseOthers() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <rect x="2.5" y="3" width="8" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.2" fill="none" />
      <path d="M7 7l5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseRight() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 3v10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M7 5l5 3-5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 4h3a1 1 0 0 1 1 1v7.5M12.5 12h-3a1 1 0 0 1-1-1V3.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path d="M5 6l6 6m0-6-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconPin() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M5.5 2.5h5l.5 4h2v1.5h-4V13l-1-.5V8h-3V6.5h3z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function MenuIconUnpin() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 3.5l9 9M5.5 2.5h5l.5 4h2v1.5H10M8 8v4.5L7 12.5V8H4V6.5h1"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function MenuIconFile() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M5 2.5h4l2.5 2.5V13.5H5z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function escapeAttributeValue(value: string) {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Explorer.tsx
```tsx
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import clsx from "clsx";

import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";

import type { WorkbenchFileNode } from "../types";

type ExplorerTheme = "light" | "dark";

interface ExplorerThemeTokens {
  readonly surface: string;
  readonly border: string;
  readonly heading: string;
  readonly label: string;
  readonly textPrimary: string;
  readonly textMuted: string;
  readonly rowHover: string;
  readonly folderActiveBg: string;
  readonly selectionBg: string;
  readonly selectionText: string;
  readonly badgeActive: string;
  readonly badgeOpen: string;
  readonly folderIcon: string;
  readonly folderIconActive: string;
  readonly chevronIdle: string;
  readonly chevronActive: string;
}

const EXPLORER_THEME_TOKENS: Record<ExplorerTheme, ExplorerThemeTokens> = {
  dark: {
    surface: "#1e1e1e",
    border: "#252526",
    heading: "#cccccc",
    label: "#999999",
    textPrimary: "#f3f3f3",
    textMuted: "#c5c5c5",
    rowHover: "#2a2d2e",
    folderActiveBg: "transparent",
    selectionBg: "#2f3136",
    selectionText: "#f8f8f8",
    badgeActive: "#4fc1ff",
    badgeOpen: "#858585",
    folderIcon: "#c8ae7d",
    folderIconActive: "#e0c08e",
    chevronIdle: "#7a7a7a",
    chevronActive: "#d4d4d4",
  },
  light: {
    surface: "#f3f3f3",
    border: "#d4d4d4",
    heading: "#616161",
    label: "#8a8a8a",
    textPrimary: "#1e1e1e",
    textMuted: "#555555",
    rowHover: "#e8e8e8",
    folderActiveBg: "transparent",
    selectionBg: "#dcdcdc",
    selectionText: "#0f172a",
    badgeActive: "#0e639c",
    badgeOpen: "#6b6b6b",
    folderIcon: "#c0933a",
    folderIconActive: "#a67c32",
    chevronIdle: "#7a7a7a",
    chevronActive: "#3c3c3c",
  },
};

const FOCUS_RING_CLASS: Record<ExplorerTheme, string> = {
  dark: "focus-visible:ring-2 focus-visible:ring-[#007acc] focus-visible:ring-offset-2 focus-visible:ring-offset-[#252526]",
  light: "focus-visible:ring-2 focus-visible:ring-[#007acc] focus-visible:ring-offset-2 focus-visible:ring-offset-white",
};

function collectExpandedFolderIds(root: WorkbenchFileNode): Set<string> {
  const expanded = new Set<string>();
  const visit = (node: WorkbenchFileNode) => {
    expanded.add(node.id);
    node.children?.forEach((child) => {
      if (child.kind === "folder") {
        visit(child);
      }
    });
  };
  visit(root);
  return expanded;
}

interface ExplorerProps {
  readonly width: number;
  readonly tree: WorkbenchFileNode;
  readonly activeFileId: string;
  readonly openFileIds: readonly string[];
  readonly onSelectFile: (fileId: string) => void;
  readonly theme: ExplorerTheme;
  readonly onCloseFile: (fileId: string) => void;
  readonly onCloseOtherFiles: (fileId: string) => void;
  readonly onCloseTabsToRight: (fileId: string) => void;
  readonly onCloseAllFiles: () => void;
  readonly onHide: () => void;
}

export function Explorer({
  width,
  tree,
  activeFileId,
  openFileIds,
  onSelectFile,
  theme,
  onCloseFile,
  onCloseOtherFiles,
  onCloseTabsToRight,
  onCloseAllFiles,
  onHide,
}: ExplorerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => collectExpandedFolderIds(tree));
  const [contextMenu, setContextMenu] = useState<{
    readonly node: WorkbenchFileNode;
    readonly position: { readonly x: number; readonly y: number };
  } | null>(null);

  useEffect(() => {
    setExpanded(collectExpandedFolderIds(tree));
  }, [tree]);

  const toggleFolder = useCallback((nodeId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const setFolderExpanded = useCallback(
    (nodeId: string, nextExpanded: boolean) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (nextExpanded) {
          next.add(nodeId);
        } else if (nodeId !== tree.id) {
          next.delete(nodeId);
        }
        if (!next.has(tree.id)) {
          next.add(tree.id);
        }
        return next;
      });
    },
    [tree.id],
  );

  const collapseAll = useCallback(() => {
    setExpanded(new Set([tree.id]));
  }, [tree.id]);

  const rootChildren = useMemo(() => tree.children ?? [], [tree]);
  const menuAppearance = theme === "dark" ? "dark" : "light";

  const handleNodeContextMenu = useCallback((event: React.MouseEvent, node: WorkbenchFileNode) => {
    event.preventDefault();
    setContextMenu({ node, position: { x: event.clientX, y: event.clientY } });
  }, []);

  const handleCopyPath = useCallback(async (path: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(path);
        return;
      } catch {
        // fall through to manual copy
      }
    }
    if (typeof document === "undefined") {
      return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = path;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "absolute";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  }, []);

  const explorerMenuItems: ContextMenuItem[] = useMemo(() => {
    if (!contextMenu) {
      return [];
    }
    const node = contextMenu.node;
    const shortcuts = {
      open: "Enter",
      close: "Ctrl+W",
      closeOthers: "Ctrl+K Ctrl+O",
      closeRight: "Ctrl+K Ctrl+Right",
      closeAll: "Ctrl+K Ctrl+W",
      copyPath: "Ctrl+K Ctrl+C",
      collapseAll: "Ctrl+K Ctrl+0",
    };
    if (node.kind === "file") {
      const isOpen = openFileIds.includes(node.id);
      const openCount = openFileIds.length;
      const tabIndex = openFileIds.indexOf(node.id);
      const hasTabsToRight = tabIndex >= 0 && tabIndex < openCount - 1;
      return [
        { id: "open-file", label: "Open", icon: <MenuIconOpenFile />, shortcut: shortcuts.open, onSelect: () => onSelectFile(node.id) },
        {
          id: "close-file",
          label: "Close",
          icon: <MenuIconClose />,
          disabled: !isOpen,
          shortcut: shortcuts.close,
          onSelect: () => onCloseFile(node.id),
        },
        {
          id: "close-file-others",
          label: "Close Others",
          icon: <MenuIconCloseOthers />,
          disabled: !isOpen || openCount <= 1,
          shortcut: shortcuts.closeOthers,
          onSelect: () => onCloseOtherFiles(node.id),
        },
        {
          id: "close-file-right",
          label: "Close Tabs to the Right",
          icon: <MenuIconCloseRight />,
          disabled: !isOpen || !hasTabsToRight,
          shortcut: shortcuts.closeRight,
          onSelect: () => onCloseTabsToRight(node.id),
        },
        {
          id: "close-file-all",
          label: "Close All",
          dividerAbove: true,
          disabled: openCount === 0,
          icon: <MenuIconCloseAll />,
          shortcut: shortcuts.closeAll,
          onSelect: () => onCloseAllFiles(),
        },
        {
          id: "copy-path",
          label: "Copy Path",
          dividerAbove: true,
          icon: <MenuIconCopyPath />,
          shortcut: shortcuts.copyPath,
          onSelect: () => {
            void handleCopyPath(node.id);
          },
        },
      ];
    }
    const isExpanded = expanded.has(node.id);
    return [
      {
        id: "toggle-folder",
        label: isExpanded ? "Collapse Folder" : "Expand Folder",
        icon: isExpanded ? <MenuIconCollapse /> : <MenuIconExpand />,
        onSelect: () => setFolderExpanded(node.id, !isExpanded),
      },
      {
        id: "collapse-all",
        label: "Collapse All",
        icon: <MenuIconCollapseAll />,
        shortcut: shortcuts.collapseAll,
        dividerAbove: true,
        onSelect: () => collapseAll(),
      },
      {
        id: "copy-path",
        label: "Copy Path",
        dividerAbove: true,
        icon: <MenuIconCopyPath />,
        shortcut: shortcuts.copyPath,
        onSelect: () => {
          void handleCopyPath(node.id);
        },
      },
    ];
  }, [
    contextMenu,
    openFileIds,
    onSelectFile,
    onCloseFile,
    onCloseOtherFiles,
    onCloseTabsToRight,
    onCloseAllFiles,
    handleCopyPath,
    expanded,
    setFolderExpanded,
    collapseAll,
  ]);
  const tokens = EXPLORER_THEME_TOKENS[theme];
  const focusRingClass = FOCUS_RING_CLASS[theme];

  return (
    <>
      <aside
        className="flex h-full min-h-0 flex-col border-r text-[13px]"
        style={{
          width,
          backgroundColor: tokens.surface,
          borderColor: tokens.border,
          color: tokens.textPrimary,
        }}
        aria-label="Config files explorer"
      >
        <div
          className="flex items-center justify-between border-b px-3 py-2"
          style={{ borderColor: tokens.border, backgroundColor: theme === "dark" ? "#181818" : "#ececec" }}
        >
          <div className="text-[11px] font-semibold uppercase tracking-[0.3em]" style={{ color: tokens.heading }}>
            Explorer
          </div>
          <button
            type="button"
            onClick={onHide}
            aria-label="Hide explorer"
            className={clsx(
              "flex h-7 w-7 items-center justify-center rounded-md transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#007acc]",
              theme === "dark"
                ? "text-slate-300 hover:bg-white/10 hover:text-white"
                : "text-slate-600 hover:bg-black/10 hover:text-slate-900",
            )}
          >
            <HideSidebarIcon />
          </button>
        </div>
        <nav className="flex-1 overflow-auto px-2 py-2" aria-label="Workspace files tree">
          <ul className="space-y-0.5">
            {rootChildren.map((node) => (
              <ExplorerNode
                key={node.id}
                node={node}
                depth={0}
                expanded={expanded}
                activeFileId={activeFileId}
                openFileIds={openFileIds}
                onToggleFolder={toggleFolder}
                onSelectFile={onSelectFile}
                tokens={tokens}
                focusRingClass={focusRingClass}
                onContextMenu={handleNodeContextMenu}
              />
            ))}
          </ul>
        </nav>
      </aside>
      <ContextMenu
        open={Boolean(contextMenu)}
        position={contextMenu && contextMenu.position}
        onClose={() => setContextMenu(null)}
        items={explorerMenuItems}
        appearance={menuAppearance}
      />
    </>
  );
}

interface ExplorerNodeProps {
  readonly node: WorkbenchFileNode;
  readonly depth: number;
  readonly expanded: ReadonlySet<string>;
  readonly activeFileId: string;
  readonly openFileIds: readonly string[];
  readonly onToggleFolder: (nodeId: string) => void;
  readonly onSelectFile: (fileId: string) => void;
  readonly tokens: ExplorerThemeTokens;
  readonly focusRingClass: string;
  readonly onContextMenu: (event: React.MouseEvent, node: WorkbenchFileNode) => void;
}

function ExplorerNode({
  node,
  depth,
  expanded,
  activeFileId,
  openFileIds,
  onToggleFolder,
  onSelectFile,
  tokens,
  focusRingClass,
  onContextMenu,
}: ExplorerNodeProps) {
  const paddingLeft = 8 + depth * 16;
  const baseStyle: CSSProperties & { ["--tree-hover-bg"]?: string } = {
    paddingLeft,
    ["--tree-hover-bg"]: tokens.rowHover,
  };

  if (node.kind === "folder") {
    const isOpen = expanded.has(node.id);
    const folderStyle: CSSProperties = {
      ...baseStyle,
      color: isOpen ? tokens.textPrimary : tokens.textMuted,
    };
    if (isOpen && tokens.folderActiveBg !== "transparent") {
      folderStyle.backgroundColor = tokens.folderActiveBg;
    }

    return (
      <li className="relative">
        <button
          type="button"
          onClick={() => onToggleFolder(node.id)}
          onContextMenu={(event) => onContextMenu(event, node)}
          className={clsx(
            "group flex w-full items-center gap-2 rounded-md px-2 py-1 text-left font-medium transition hover:bg-[var(--tree-hover-bg)]",
            focusRingClass,
          )}
          style={folderStyle}
          aria-expanded={isOpen}
        >
          <ChevronIcon open={isOpen} tokens={tokens} />
          <FolderIcon open={isOpen} tokens={tokens} />
          <span className="truncate">{node.name}</span>
        </button>
        {isOpen && node.children?.length ? (
          <ul className="mt-0.5 space-y-0.5">
            {node.children.map((child) => (
              <ExplorerNode
                key={child.id}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              activeFileId={activeFileId}
              openFileIds={openFileIds}
              onToggleFolder={onToggleFolder}
              onSelectFile={onSelectFile}
              tokens={tokens}
              focusRingClass={focusRingClass}
              onContextMenu={onContextMenu}
            />
            ))}
          </ul>
        ) : null}
      </li>
    );
  }

  const isActive = activeFileId === node.id;
  const isOpen = openFileIds.includes(node.id);
  const fileAccent = getFileAccent(node.name, node.language);
  const fileStyle: CSSProperties = { ...baseStyle, color: tokens.textPrimary };
  if (isActive) {
    fileStyle.backgroundColor = tokens.selectionBg;
    fileStyle.color = tokens.selectionText;
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelectFile(node.id)}
        onContextMenu={(event) => onContextMenu(event, node)}
        className={clsx(
          "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left transition hover:bg-[var(--tree-hover-bg)]",
          focusRingClass,
          isActive && "shadow-inner shadow-[#00000033]",
        )}
        style={fileStyle}
      >
        <span className="inline-flex w-4 justify-center">
          <FileIcon className={fileAccent} />
        </span>
        <span className="flex-1 truncate">{node.name}</span>
        {isActive ? (
          <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: tokens.badgeActive }}>
            Active
          </span>
        ) : isOpen ? (
          <span className="text-[9px] uppercase tracking-wide" style={{ color: tokens.badgeOpen }}>
            Open
          </span>
        ) : null}
      </button>
    </li>
  );
}

const FILE_ICON_COLORS: Record<string, string> = {
  json: "text-[#f1d06b]",
  py: "text-[#519aba]",
  ts: "text-[#519aba]",
  tsx: "text-[#519aba]",
  js: "text-[#f4d13d]",
  jsx: "text-[#519aba]",
  md: "text-[#4ec9b0]",
  env: "text-[#b5cea8]",
  txt: "text-[#9cdcfe]",
  lock: "text-[#c586c0]",
};

function getFileAccent(name: string, language?: string) {
  if (language === "python") {
    return "text-sky-300";
  }
  const segments = name.toLowerCase().split(".");
  const extension = segments.length > 1 ? segments.pop() ?? "" : "";
  if (extension && FILE_ICON_COLORS[extension]) {
    return FILE_ICON_COLORS[extension];
  }
  return "text-slate-400";
}

function ChevronIcon({ open, tokens }: { readonly open: boolean; readonly tokens: ExplorerThemeTokens }) {
  return (
    <svg
      className={clsx(
        "h-3 w-3 flex-shrink-0 transition-transform duration-150",
        open ? "rotate-90" : undefined,
      )}
      viewBox="0 0 10 10"
      aria-hidden
    >
      <path
        d="M3 1l4 4-4 4"
        stroke={open ? tokens.chevronActive : tokens.chevronIdle}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FolderIcon({ open, tokens }: { readonly open: boolean; readonly tokens: ExplorerThemeTokens }) {
  return (
    <svg className="h-4 w-4 flex-shrink-0 transition-colors" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M3.5 5.5h4l1.5 1.5H16a1 1 0 0 1 1 1V15a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6.5a1 1 0 0 1 1-1Z"
        stroke={open ? tokens.folderIconActive : tokens.folderIcon}
        strokeWidth={1.4}
        strokeLinejoin="round"
        fill={open ? tokens.folderIconActive : "none"}
        opacity={open ? 0.25 : 1}
      />
    </svg>
  );
}

function FileIcon({ className }: { readonly className?: string }) {
  return (
    <svg className={clsx("h-4 w-4 flex-shrink-0", className)} viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M6 3h4l4 4v9a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth={1.3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 3v4h4" stroke="currentColor" strokeWidth={1.3} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HideSidebarIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M3 3h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 13h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 8h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M11 5l2 3-2 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

function MenuIconOpenFile() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3 4.5h3l1 1H13a1 1 0 0 1 1 1V12.5a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.2"
        fill="none"
      />
    </svg>
  );
}

function MenuIconCopyPath() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6 4.5h5.5a1 1 0 0 1 1 1V13"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
      <rect x="3.5" y="2.5" width="6" height="9" rx="1" stroke="currentColor" strokeWidth="1.1" fill="none" />
    </svg>
  );
}

function MenuIconCollapse() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 6l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIconExpand() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 10l3-3 3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIconCollapseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M3 5h10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 8h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M3 11h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconClose() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M4 4l8 8m0-8l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseOthers() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <rect x="2.5" y="3" width="8" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.2" fill="none" />
      <path d="M7 7l5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseRight() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 3v10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M7 5l5 3-5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function MenuIconCloseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 4.5h3.5a1 1 0 0 1 1 1V13M12.5 11.5h-3.5a1 1 0 0 1-1-1V3"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
      <path d="M4.5 6.5l7 7m0-7-7 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/Inspector.tsx
```tsx
import type { WorkbenchFileTab } from "../types";

interface InspectorProps {
  readonly width: number;
  readonly file: WorkbenchFileTab | null;
}

export function Inspector({ width, file }: InspectorProps) {
  if (!file) {
    return null;
  }
  const isDirty = file.status === "ready" && file.content !== file.initialContent;
  const metadata = file.metadata;

  return (
    <aside className="flex h-full min-h-0 flex-shrink-0 flex-col border-l border-slate-200 bg-slate-50" style={{ width }}>
      <header className="border-b border-slate-200 px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Inspector</h2>
      </header>
      <div className="flex-1 space-y-4 overflow-auto px-3 py-4 text-sm text-slate-600">
        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">File</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Name</dt>
              <dd className="text-slate-700">{file.name}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Path</dt>
              <dd className="break-words text-slate-700">{file.id}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Language</dt>
              <dd className="text-slate-700">{file.language ?? "plain text"}</dd>
            </div>
          </dl>
        </section>

        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">Metadata</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Size</dt>
              <dd className="text-slate-700">{formatFileSize(metadata?.size)}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Last modified</dt>
              <dd className="text-slate-700">{formatTimestamp(metadata?.modifiedAt)}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Content type</dt>
              <dd className="text-slate-700">{metadata?.contentType ?? "—"}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">ETag</dt>
              <dd className="break-words text-slate-700">{metadata?.etag ?? "—"}</dd>
            </div>
          </dl>
        </section>

        <section className="space-y-2 text-xs">
          <h3 className="text-[0.7rem] font-semibold uppercase tracking-wide text-slate-500">Editor</h3>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-slate-500">Load status</dt>
              <dd className="text-slate-700 capitalize">{file.status}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Dirty</dt>
              <dd className="text-slate-700">{isDirty ? "Yes" : "No"}</dd>
            </div>
          </dl>
        </section>

        <p className="text-xs leading-relaxed text-slate-500">
          The inspector stays in sync with the active tab. Future work can hydrate this panel with schema-aware helpers and
          quick actions without reworking the layout.
        </p>
      </div>
    </aside>
  );
}

function formatFileSize(size: number | null | undefined): string {
  if (size == null) {
    return "—";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  const units = ["KB", "MB", "GB"];
  let value = size / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`;
}

function formatTimestamp(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "—";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/PanelResizeHandle.tsx
```tsx
import type { PointerEventHandler } from "react";

interface PanelResizeHandleProps {
  readonly orientation: "horizontal" | "vertical";
  readonly onPointerDown: PointerEventHandler<HTMLDivElement>;
}

export function PanelResizeHandle({ orientation, onPointerDown }: PanelResizeHandleProps) {
  const isVertical = orientation === "vertical";
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={
        isVertical
          ? "w-1 cursor-col-resize select-none bg-transparent"
          : "h-1 cursor-row-resize select-none bg-transparent"
      }
      style={{ touchAction: "none" }}
      onPointerDown={onPointerDown}
    >
      <span className="sr-only">Resize panel</span>
    </div>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/components/__tests__/EditorArea.test.tsx
```tsx
import { fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@ui/CodeEditor", () => ({
  CodeEditor: ({
    value,
    onChange,
  }: {
    value: string;
    onChange?: (value: string | undefined) => void;
    theme?: string;
  }) => (
    <textarea
      data-testid="code-editor"
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

import type { WorkbenchFileTab } from "../../types";
import { EditorArea } from "../EditorArea";

const tabs: WorkbenchFileTab[] = [
  {
    id: "manifest.json",
    name: "manifest.json",
    language: "json",
    initialContent: "{}",
    content: "{}",
    status: "ready",
    error: null,
    etag: null,
  },
  {
    id: "src/data.py",
    name: "data.py",
    language: "python",
    initialContent: "print('hello')\n",
    content: "print('hello')\n",
    status: "ready",
    error: null,
    etag: null,
  },
];

afterEach(() => {
  vi.clearAllMocks();
});

describe("EditorArea keyboard shortcuts", () => {
  it("cycles to the next tab with Ctrl+Tab", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="manifest.json"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    fireEvent.keyDown(window, { key: "Tab", ctrlKey: true });
    expect(onSelectRecentTab).toHaveBeenCalledWith("forward");

    unmount();
  });

  it("cycles to the previous tab with Ctrl+Shift+Tab", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="src/data.py"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    fireEvent.keyDown(window, { key: "Tab", ctrlKey: true, shiftKey: true });
    expect(onSelectRecentTab).toHaveBeenCalledWith("backward");

    unmount();
  });

  it("cycles visually with Ctrl+PageDown", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="manifest.json"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    fireEvent.keyDown(window, { key: "PageDown", ctrlKey: true });
    expect(onSelectTab).toHaveBeenCalledWith("src/data.py");

    unmount();
  });

  it("cycles visually backwards with Ctrl+PageUp", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="src/data.py"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    fireEvent.keyDown(window, { key: "PageUp", ctrlKey: true });
    expect(onSelectTab).toHaveBeenCalledWith("manifest.json");

    unmount();
  });

  it("closes the active tab with Ctrl+W", () => {
    const onSelectTab = vi.fn();
    const onCloseTab = vi.fn();
    const onCloseOthers = vi.fn();
    const onCloseRight = vi.fn();
    const onCloseAll = vi.fn();
    const onMoveTab = vi.fn();
    const onContentChange = vi.fn();
    const onPinTab = vi.fn();
    const onUnpinTab = vi.fn();
    const onSelectRecentTab = vi.fn();

    const { unmount } = render(
      <EditorArea
        tabs={tabs}
        activeTabId="manifest.json"
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        onCloseOtherTabs={onCloseOthers}
        onCloseTabsToRight={onCloseRight}
        onCloseAllTabs={onCloseAll}
        onMoveTab={onMoveTab}
        onPinTab={onPinTab}
        onUnpinTab={onUnpinTab}
        onContentChange={onContentChange}
        onSelectRecentTab={onSelectRecentTab}
        editorTheme="ade-dark"
        menuAppearance="dark"
      />,
    );

    fireEvent.keyDown(window, { key: "w", ctrlKey: true });
    expect(onCloseTab).toHaveBeenCalledWith("manifest.json");

    unmount();
  });
});
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/defaultConfig.ts
```typescript
export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileNode {
  readonly id: string;
  readonly name: string;
  readonly kind: WorkbenchFileKind;
  readonly language?: string;
  readonly children?: readonly WorkbenchFileNode[];
}

export const DEFAULT_FILE_TREE: WorkbenchFileNode = {
  id: "ade_config",
  name: "ade_config",
  kind: "folder",
  children: [
    { id: "ade_config/manifest.json", name: "manifest.json", kind: "file", language: "json" },
    { id: "ade_config/config.env", name: "config.env", kind: "file", language: "dotenv" },
    {
      id: "ade_config/header.py",
      name: "header.py",
      kind: "file",
      language: "python",
    },
    {
      id: "ade_config/detectors",
      name: "detectors",
      kind: "folder",
      children: [
        {
          id: "ade_config/detectors/membership.py",
          name: "membership.py",
          kind: "file",
          language: "python",
        },
        {
          id: "ade_config/detectors/duplicates.py",
          name: "duplicates.py",
          kind: "file",
          language: "python",
        },
      ],
    },
    {
      id: "ade_config/hooks",
      name: "hooks",
      kind: "folder",
      children: [
        {
          id: "ade_config/hooks/normalize.py",
          name: "normalize.py",
          kind: "file",
          language: "python",
        },
      ],
    },
    {
      id: "ade_config/tests",
      name: "tests",
      kind: "folder",
      children: [
        {
          id: "ade_config/tests/test_membership.py",
          name: "test_membership.py",
          kind: "file",
          language: "python",
        },
      ],
    },
  ],
};

export const DEFAULT_FILE_CONTENT: Record<string, string> = {
  "ade_config/manifest.json": `{
  "name": "membership-normalization",
  "version": "0.1.0",
  "description": "Normalize membership exports into ADE schema",
  "entry": {
    "module": "ade_config.detectors.membership",
    "callable": "build_pipeline"
  }
}`,
  "ade_config/config.env": `# Environment variables required to run this configuration
ADE_ENV=development
`,
  "ade_config/header.py": `"""Shared header helpers for ADE configuration."""

from ade_engine import ConfigContext

def build_header(context: ConfigContext) -> dict[str, str]:
    """Return metadata for ADE jobs."""
    return {
        "workspace": context.workspace_id,
        "generated_at": context.generated_at.isoformat(),
    }
`,
  "ade_config/detectors/membership.py": `"""Membership detector."""

def build_pipeline():
    return [
        {"step": "clean"},
        {"step": "validate"},
    ]
`,
  "ade_config/detectors/duplicates.py": `"""Duplicate row detector."""

def build_pipeline():
    return [
        {"step": "detect-duplicates"},
    ]
`,
  "ade_config/hooks/normalize.py": `def normalize(record: dict[str, str]) -> dict[str, str]:
    return {
        "first_name": record.get("First Name", "").title(),
        "last_name": record.get("Last Name", "").title(),
    }
`,
  "ade_config/tests/test_membership.py": `from ade_engine.testing import ConfigTest


def test_membership_happy_path(snapshot: ConfigTest):
    result = snapshot.run_job("membership", input_path="./fixtures/membership.csv")
    assert result.errors == []
`,
};

export function findFileNode(root: WorkbenchFileNode, id: string): WorkbenchFileNode | null {
  if (root.id === id) {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const match = findFileNode(child, id);
    if (match) {
      return match;
    }
  }
  return null;
}

export function findFirstFile(root: WorkbenchFileNode): WorkbenchFileNode | null {
  if (root.kind === "file") {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const file = findFirstFile(child);
    if (file) {
      return file;
    }
  }
  return null;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/index.tsx
```tsx
import { useEffect } from "react";

import { PageState } from "@ui/PageState";

import { useWorkspaceContext } from "@screens/Workspace/context/WorkspaceContext";
import { useWorkbenchWindow } from "@screens/Workspace/context/WorkbenchWindowContext";
import { useConfigQuery } from "@shared/configs/hooks/useConfigsQuery";

import { Workbench } from "./Workbench";

interface ConfigEditorWorkbenchRouteProps {
  readonly params?: { readonly configId?: string };
}

export default function ConfigEditorWorkbenchRoute({ params }: ConfigEditorWorkbenchRouteProps = {}) {
  const { workspace } = useWorkspaceContext();
  const {
    session,
    windowState,
    openSession,
    closeSession,
    minimizeWindow,
    maximizeWindow,
    restoreWindow,
    shouldBypassUnsavedGuard,
  } = useWorkbenchWindow();
  const configId = params?.configId;
  const configQuery = useConfigQuery({ workspaceId: workspace.id, configId });

  useEffect(() => {
    if (configId) {
      return;
    }
    closeSession();
  }, [configId, closeSession]);

  useEffect(() => {
    if (!configId) {
      return;
    }
    const resolvedName = configQuery.data?.display_name ?? configId;
    openSession({
      workspaceId: workspace.id,
      configId,
      configName: `${workspace.name} · ${resolvedName}`,
    });
  }, [configId, configQuery.data?.display_name, workspace.id, workspace.name, openSession]);

  if (!configId) {
    return (
      <PageState
        variant="error"
        title="Select a configuration"
        description="Choose a configuration from the list to open the workbench."
      />
    );
  }

  const activeSession = session && session.configId === configId ? session : null;
  const isDocked = Boolean(activeSession && windowState === "minimized");
  const showWorkbenchInline = Boolean(activeSession && windowState === "restored");
  const showMaximizedNotice = Boolean(activeSession && windowState === "maximized");

  if (showWorkbenchInline && activeSession) {
    return (
      <div className="flex h-full min-h-0 flex-1 flex-col">
        <Workbench
          workspaceId={workspace.id}
          configId={activeSession.configId}
          configName={activeSession.configName}
          windowState="restored"
          onMinimizeWindow={minimizeWindow}
          onMaximizeWindow={maximizeWindow}
          onRestoreWindow={restoreWindow}
          onCloseWorkbench={closeSession}
          shouldBypassUnsavedGuard={shouldBypassUnsavedGuard}
        />
      </div>
    );
  }

  if (showMaximizedNotice) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
        <PageState
          variant="empty"
          title="Immersive focus active"
          description="Exit immersive mode from the workbench focus menu to return here."
        />
      </div>
    );
  }

  if (isDocked) {
    return (
      <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
        <PageState
          variant="empty"
          title="Workbench docked"
          description="Use the dock at the bottom of the screen to resume editing."
        />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-1 items-center justify-center px-6 py-8">
      <PageState
        variant="loading"
        title="Launching config workbench"
        description="If the editor does not appear, refresh the page."
      />
    </div>
  );
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/seed/stubWorkbenchData.ts
```typescript
import type {
  WorkbenchConsoleLine,
  WorkbenchDataSeed,
  WorkbenchFileNode,
  WorkbenchValidationMessage,
} from "../types";

const tree: WorkbenchFileNode = {
  id: "ade_config",
  name: "ade_config",
  kind: "folder",
  children: [
    { id: "ade_config/manifest.json", name: "manifest.json", kind: "file", language: "json" },
    { id: "ade_config/config.env", name: "config.env", kind: "file", language: "dotenv" },
    {
      id: "ade_config/header.py",
      name: "header.py",
      kind: "file",
      language: "python",
    },
    {
      id: "ade_config/detectors",
      name: "detectors",
      kind: "folder",
      children: [
        {
          id: "ade_config/detectors/membership.py",
          name: "membership.py",
          kind: "file",
          language: "python",
        },
        {
          id: "ade_config/detectors/duplicates.py",
          name: "duplicates.py",
          kind: "file",
          language: "python",
        },
      ],
    },
    {
      id: "ade_config/hooks",
      name: "hooks",
      kind: "folder",
      children: [
        {
          id: "ade_config/hooks/normalize.py",
          name: "normalize.py",
          kind: "file",
          language: "python",
        },
      ],
    },
    {
      id: "ade_config/tests",
      name: "tests",
      kind: "folder",
      children: [
        {
          id: "ade_config/tests/test_membership.py",
          name: "test_membership.py",
          kind: "file",
          language: "python",
        },
      ],
    },
  ],
};

const content: Record<string, string> = {
  "ade_config/manifest.json": `{
  "name": "membership-normalization",
  "version": "0.1.0",
  "description": "Normalize membership exports into ADE schema",
  "entry": {
    "module": "ade_config.detectors.membership",
    "callable": "build_pipeline"
  }
}`,
  "ade_config/config.env": `# Environment variables required to run this configuration
ADE_ENV=development
`,
  "ade_config/header.py": `"""Shared header helpers for ADE configuration."""

from ade_engine import ConfigContext

def build_header(context: ConfigContext) -> dict[str, str]:
    """Return metadata for ADE jobs."""
    return {
        "workspace": context.workspace_id,
        "generated_at": context.generated_at.isoformat(),
    }
`,
  "ade_config/detectors/membership.py": `"""Membership detector."""

def build_pipeline():
    return [
        {"step": "clean"},
        {"step": "validate"},
    ]
`,
  "ade_config/detectors/duplicates.py": `"""Duplicate row detector."""

def build_pipeline():
    return [
        {"step": "detect-duplicates"},
    ]
`,
  "ade_config/hooks/normalize.py": `def normalize(record: dict[str, str]) -> dict[str, str]:
    return {
        "first_name": record.get("First Name", "").title(),
        "last_name": record.get("Last Name", "").title(),
    }
`,
  "ade_config/tests/test_membership.py": `from ade_engine.testing import ConfigTest


def test_membership_happy_path(snapshot: ConfigTest):
    result = snapshot.run_job("membership", input_path="./fixtures/membership.csv")
    assert result.errors == []
`,
};

const console: WorkbenchConsoleLine[] = [
  {
    level: "info",
    message: "Config workbench ready. Open a file to begin editing.",
    timestamp: "12:00:01",
  },
  {
    level: "success",
    message: "Loaded local ADE runtime stub.",
    timestamp: "12:00:02",
  },
];

const validation: WorkbenchValidationMessage[] = [
  {
    level: "warning",
    message: "Manifest description is short. Consider elaborating on the configuration purpose.",
  },
  {
    level: "info",
    message: "Detector membership.py compiled successfully.",
  },
];

export function createStubWorkbenchData(): WorkbenchDataSeed {
  return {
    tree,
    content,
    console,
    validation,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/__tests__/useUnsavedChangesGuard.test.tsx
```tsx
import React from "react";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@test/test-utils";
import { describe, expect, it, vi } from "vitest";

import { useNavigate } from "@app/nav/history";

import { useUnsavedChangesGuard, UNSAVED_CHANGES_PROMPT } from "../useUnsavedChangesGuard";

function GuardHarness({ confirm }: { readonly confirm: (message: string) => boolean }) {
  const [dirty, setDirty] = React.useState(false);
  const navigate = useNavigate();

  useUnsavedChangesGuard({ isDirty: dirty, confirm });

  return (
    <div>
      <button type="button" onClick={() => setDirty(true)}>
        mark-dirty
      </button>
      <button type="button" onClick={() => navigate("/other")}>
        navigate-away
      </button>
      <button type="button" onClick={() => navigate(`${window.location.pathname}?file=foo`, { replace: true })}>
        update-query
      </button>
    </div>
  );
}

describe("useUnsavedChangesGuard", () => {
  it("blocks navigation when the user cancels and wires beforeunload", async () => {
    window.history.replaceState(null, "", "/workspaces/acme/config-builder/foo/editor");

    const confirmMock = vi.fn().mockReturnValue(false);
    render(<GuardHarness confirm={confirmMock} />);

    await userEvent.click(screen.getByRole("button", { name: "mark-dirty" }));
    await userEvent.click(screen.getByRole("button", { name: "navigate-away" }));

    expect(confirmMock).toHaveBeenCalledWith(UNSAVED_CHANGES_PROMPT);
    expect(window.location.pathname).toBe("/workspaces/acme/config-builder/foo/editor");

    const event = new Event("beforeunload", { cancelable: true });
    Object.defineProperty(event, "returnValue", { writable: true, value: undefined });
    window.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    expect(event.returnValue).toBe(UNSAVED_CHANGES_PROMPT);
  });

  it("allows navigation when confirmed and ignores internal query updates", async () => {
    window.history.replaceState(null, "", "/workspaces/acme/config-builder/foo/editor");

    const confirmMock = vi.fn().mockReturnValue(true);
    render(<GuardHarness confirm={confirmMock} />);

    await userEvent.click(screen.getByRole("button", { name: "mark-dirty" }));
    await userEvent.click(screen.getByRole("button", { name: "update-query" }));

    expect(confirmMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "navigate-away" }));

    expect(confirmMock).toHaveBeenCalledWith(UNSAVED_CHANGES_PROMPT);
    expect(window.location.pathname).toBe("/other");
  });
});
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/__tests__/useWorkbenchFiles.test.tsx
```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { WorkbenchFileNode } from "../../types";
import { useWorkbenchFiles } from "../useWorkbenchFiles";

type PersistedState =
  | {
      openTabs: Array<string | { id: string; pinned?: boolean }>;
      activeTabId?: string | null;
      mru?: string[];
    }
  | null;

const tree: WorkbenchFileNode = {
  id: "root",
  name: "ade_config",
  kind: "folder",
  children: [
    { id: "manifest.json", name: "manifest.json", kind: "file", language: "json" },
    { id: "src/data.py", name: "data.py", kind: "file", language: "python" },
  ],
};

function createStorageStub(initial: PersistedState) {
  let current = initial;
  const getMock = vi.fn(() => current);
  const setMock = vi.fn((value: PersistedState) => {
    current = value ?? null;
  });
  const clearMock = vi.fn(() => {
    current = null;
  });

  const persistence = {
    get: getMock as unknown as <T>() => T | null,
    set: setMock as unknown as <T>(value: T) => void,
    clear: clearMock as () => void,
  };

  return { persistence, getMock, setMock, clearMock, snapshot: () => current };
}

interface HarnessProps {
  readonly tree: WorkbenchFileNode | null;
  readonly loadFile: (fileId: string) => Promise<{ content: string; etag?: string | null }>;
  readonly persistence?: {
    get<T>(): T | null;
    set<T>(value: T): void;
    clear(): void;
  } | null;
}

function Harness({ tree, loadFile, persistence }: HarnessProps) {
  const files = useWorkbenchFiles({ tree, loadFile, persistence: persistence ?? undefined });

  return (
    <div>
      <div data-testid="active-tab">{files.activeTabId}</div>
      <div data-testid="open-tabs">{files.tabs.map((tab) => tab.id).join(",")}</div>
      <div data-testid="tab-statuses">{files.tabs.map((tab) => tab.status).join(",")}</div>
      <button type="button" onClick={() => files.openFile("manifest.json")}>Open manifest</button>
      <button type="button" onClick={() => files.openFile("src/data.py")}>Open data</button>
      <button type="button" onClick={() => files.selectTab("manifest.json")}>Select manifest</button>
      <button type="button" onClick={() => files.closeTab(files.activeTabId)} disabled={!files.activeTabId}>
        Close active
      </button>
    </div>
  );
}

describe("useWorkbenchFiles", () => {
  it("hydrates persisted tabs from storage", async () => {
    const storage = createStorageStub({ openTabs: ["manifest.json", "src/data.py"], activeTabId: "src/data.py" });
    const loadFile = vi.fn(async (id: string) => ({ content: `content:${id}`, etag: null }));

    render(<Harness tree={tree} loadFile={loadFile} persistence={storage.persistence} />);

    await waitFor(() => expect(screen.getByTestId("open-tabs").textContent).toBe("manifest.json,src/data.py"));
    expect(screen.getByTestId("active-tab").textContent).toBe("src/data.py");
    await waitFor(() => expect(loadFile).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByTestId("tab-statuses").textContent).toBe("ready,ready"));
  });

  it("persists tab mutations to storage", async () => {
    const storage = createStorageStub(null);
    const loadFile = vi.fn(async (id: string) => ({ content: `content:${id}`, etag: null }));

    render(<Harness tree={tree} loadFile={loadFile} persistence={storage.persistence} />);

    fireEvent.click(screen.getByText("Open manifest"));
    await waitFor(() => expect(screen.getByTestId("tab-statuses").textContent).toContain("loading"));
    await waitFor(() => {
      const lastCall = storage.setMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        openTabs: [{ id: "manifest.json", pinned: false }],
        activeTabId: "manifest.json",
        mru: ["manifest.json"],
      });
    });

    fireEvent.click(screen.getByText("Open data"));
    await waitFor(() => expect(screen.getByTestId("tab-statuses").textContent).toContain("loading"));
    await waitFor(() => {
      const lastCall = storage.setMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        openTabs: [
          { id: "manifest.json", pinned: false },
          { id: "src/data.py", pinned: false },
        ],
        activeTabId: "src/data.py",
        mru: ["src/data.py", "manifest.json"],
      });
    });

    fireEvent.click(screen.getByText("Close active"));
    await waitFor(() => {
      const lastCall = storage.setMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        openTabs: [{ id: "manifest.json", pinned: false }],
        activeTabId: "manifest.json",
        mru: ["manifest.json"],
      });
    });

    fireEvent.click(screen.getByText("Close active"));
    await waitFor(() => {
      const lastCall = storage.setMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        openTabs: [],
        activeTabId: null,
        mru: [],
      });
    });
  });

  it("loads file content when opening a tab", async () => {
    const loadFile = vi.fn(async (id: string) => ({ content: `content:${id}`, etag: null }));
    render(<Harness tree={tree} loadFile={loadFile} />);

    fireEvent.click(screen.getByText("Open manifest"));
    await waitFor(() => expect(loadFile).toHaveBeenCalledWith("manifest.json"));
  });

  it("retries loading when a tab errors and is re-selected", async () => {
    const loadFile = vi
      .fn()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue({ content: "new content", etag: null });

    render(<Harness tree={tree} loadFile={loadFile} />);

    fireEvent.click(screen.getByText("Open manifest"));
    await waitFor(() => expect(loadFile).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("tab-statuses").textContent).toContain("error"));

    fireEvent.click(screen.getByText("Select manifest"));
    await waitFor(() => expect(loadFile).toHaveBeenCalledTimes(2));
  });
});
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/activityModel.ts
```typescript
import type { WorkbenchConsoleLine } from "../types";

export type ActivityKind = "build" | "validation" | "extraction";
export type ActivityStatus = "idle" | "queued" | "running" | "succeeded" | "failed" | "canceled";

export interface ValidationIssue {
  readonly level: "info" | "warning" | "error";
  readonly message: string;
  readonly path?: string | null;
  readonly file?: string | null;
  readonly line?: number | null;
  readonly column?: number | null;
  readonly ruleId?: string | null;
}

export interface ActivityMetadata {
  readonly environmentDigest?: string | null;
  readonly configDigest?: string | null;
  readonly documentId?: string | null;
  readonly documentName?: string | null;
  readonly sheetNames?: readonly string[];
  readonly runId?: string | null;
  readonly buildId?: string | null;
  readonly force?: boolean;
  readonly wait?: boolean;
}

export interface ActivityOutputLink {
  readonly label: string;
  readonly href: string;
}

export interface Activity {
  readonly id: string;
  readonly kind: ActivityKind;
  readonly status: ActivityStatus;
  readonly startedAt?: string;
  readonly finishedAt?: string;
  readonly label?: string;
  readonly metadata?: ActivityMetadata;
  readonly summary?: string | null;
  readonly errorMessage?: string | null;
  readonly outputLinks?: readonly ActivityOutputLink[];
  readonly outputs?: readonly { path: string; byte_size: number }[];
  readonly outputsLoaded?: boolean;
  readonly logs: readonly WorkbenchConsoleLine[];
  readonly issues: readonly ValidationIssue[];
  readonly errorCount?: number;
  readonly warningCount?: number;
}

export interface ActivityState {
  readonly activities: readonly Activity[];
  readonly selectedActivityId: string | null;
}

export const initialActivityState: ActivityState = {
  activities: [],
  selectedActivityId: null,
};

type ActivityAction =
  | { readonly type: "start"; readonly activity: Activity; readonly select?: boolean }
  | { readonly type: "append-log"; readonly id: string; readonly line: WorkbenchConsoleLine }
  | { readonly type: "append-issues"; readonly id: string; readonly issues: readonly ValidationIssue[] }
  | { readonly type: "patch"; readonly id: string; readonly patch: Partial<Activity> }
  | { readonly type: "complete"; readonly id: string; readonly status: ActivityStatus; readonly finishedAt?: string; readonly summary?: string | null; readonly errorMessage?: string | null }
  | { readonly type: "select"; readonly id: string | null };

const MAX_LOG_LINES = 400;

export function activityReducer(state: ActivityState, action: ActivityAction): ActivityState {
  switch (action.type) {
    case "start": {
      const nextActivities = [action.activity, ...state.activities.filter((item) => item.id !== action.activity.id)];
      const selectedActivityId = action.select !== false ? action.activity.id : state.selectedActivityId ?? action.activity.id;
      return { activities: nextActivities, selectedActivityId };
    }
    case "append-log": {
      return {
        ...state,
        activities: state.activities.map((activity) => {
          if (activity.id !== action.id) {
            return activity;
          }
          const nextLogs = [...activity.logs, action.line];
          const boundedLogs =
            nextLogs.length > MAX_LOG_LINES ? nextLogs.slice(nextLogs.length - MAX_LOG_LINES) : nextLogs;
          return { ...activity, logs: boundedLogs };
        }),
      };
    }
    case "append-issues": {
      return {
        ...state,
        activities: state.activities.map((activity) => {
          if (activity.id !== action.id) {
            return activity;
          }
          const nextIssues = [...activity.issues, ...action.issues];
          const errorCount = nextIssues.filter((issue) => issue.level === "error").length;
          const warningCount = nextIssues.filter((issue) => issue.level === "warning").length;
          return { ...activity, issues: nextIssues, errorCount, warningCount };
        }),
      };
    }
    case "patch": {
      return {
        ...state,
        activities: state.activities.map((activity) =>
          activity.id === action.id ? { ...activity, ...action.patch } : activity,
        ),
      };
    }
    case "complete": {
      return {
        ...state,
        activities: state.activities.map((activity) =>
          activity.id === action.id
            ? {
                ...activity,
                status: action.status,
                finishedAt: action.finishedAt ?? activity.finishedAt,
                summary: action.summary ?? activity.summary,
                errorMessage: action.errorMessage ?? activity.errorMessage,
              }
            : activity,
        ),
      };
    }
    case "select": {
      const fallback = state.activities[0]?.id ?? null;
      return { ...state, selectedActivityId: action.id ?? fallback };
    }
    default:
      return state;
  }
}

export function createActivityId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `activity-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useEditorThemePreference.ts
```typescript
import { useCallback, useEffect, useMemo, useState } from "react";

import { createScopedStorage } from "@shared/storage";

export type EditorThemePreference = "system" | "light" | "dark";
export type EditorThemeId = "ade-dark" | "vs-light";

const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

function coercePreference(value: unknown): EditorThemePreference {
  if (value === "light" || value === "dark" || value === "system") {
    return value;
  }
  return "system";
}

function resolveTheme(preference: EditorThemePreference, systemPrefersDark: boolean): EditorThemeId {
  return preference === "dark" || (preference === "system" && systemPrefersDark) ? "ade-dark" : "vs-light";
}

export function useEditorThemePreference(storageKey: string) {
  const storage = useMemo(() => createScopedStorage(storageKey), [storageKey]);

  const [preference, setPreferenceState] = useState<EditorThemePreference>(() => {
    const stored = storage.get<EditorThemePreference>();
    return coercePreference(stored);
  });

  const [systemPrefersDark, setSystemPrefersDark] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.matchMedia(DARK_MODE_QUERY).matches;
  });

  useEffect(() => {
    const next = coercePreference(storage.get<EditorThemePreference>());
    setPreferenceState((current) => (current === next ? current : next));
  }, [storage]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const media = window.matchMedia(DARK_MODE_QUERY);
    const handleChange = (event: MediaQueryListEvent) => {
      setSystemPrefersDark(event.matches);
    };

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", handleChange);
    } else if (typeof media.addListener === "function") {
      media.addListener(handleChange);
    }

    setSystemPrefersDark(media.matches);

    return () => {
      if (typeof media.removeEventListener === "function") {
        media.removeEventListener("change", handleChange);
      } else if (typeof media.removeListener === "function") {
        media.removeListener(handleChange);
      }
    };
  }, []);

  useEffect(() => {
    storage.set(preference);
  }, [preference, storage]);

  const resolvedTheme = useMemo(() => resolveTheme(preference, systemPrefersDark), [preference, systemPrefersDark]);

  const setPreference = useCallback((next: EditorThemePreference) => {
    setPreferenceState(next);
  }, []);

  return {
    preference,
    resolvedTheme,
    setPreference,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useUnsavedChangesGuard.ts
```typescript
import { useCallback, useEffect } from "react";

import { useLocation, useNavigationBlocker } from "@app/nav/history";

const DEFAULT_PROMPT = "You have unsaved changes in the config editor. Are you sure you want to leave?";

type ConfirmFn = (message: string) => boolean;

interface UseUnsavedChangesGuardOptions {
  readonly isDirty: boolean;
  readonly confirm?: ConfirmFn;
  readonly message?: string;
  readonly shouldBypassNavigation?: () => boolean;
}

export function useUnsavedChangesGuard({
  isDirty,
  confirm = window.confirm,
  message = DEFAULT_PROMPT,
  shouldBypassNavigation,
}: UseUnsavedChangesGuardOptions) {
  const location = useLocation();

  const blocker = useCallback<Parameters<typeof useNavigationBlocker>[0]>(
    (intent) => {
      if (!isDirty) {
        return true;
      }

      if (shouldBypassNavigation?.()) {
        return true;
      }

      if (intent.location.pathname === location.pathname) {
        return true;
      }

      return confirm(message);
    },
    [confirm, isDirty, location.pathname, message, shouldBypassNavigation],
  );

  useNavigationBlocker(blocker, isDirty);

  useEffect(() => {
    if (!isDirty) {
      return;
    }

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };

    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [isDirty, message]);
}

export { DEFAULT_PROMPT as UNSAVED_CHANGES_PROMPT };
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchActivities.ts
```typescript
import { useCallback, useMemo, useReducer, useRef } from "react";

import {
  activityReducer,
  createActivityId,
  initialActivityState,
  type Activity,
  type ActivityKind,
  type ActivityStatus,
  type ValidationIssue,
} from "./activityModel";
import type { WorkbenchConsoleLine } from "../types";

const DEFAULT_LABELS: Record<ActivityKind, string> = {
  build: "Build environment",
  validation: "Validation",
  extraction: "Extraction",
};

interface StartActivityOptions {
  readonly select?: boolean;
  readonly live?: boolean;
}

/**
 * Centralizes activity state for the workbench. Any build/validation/run stream
 * should register itself here so the rest of the UI (timeline, console, chips)
 * can derive status from a single source of truth.
 */
export function useWorkbenchActivities() {
  const [state, dispatch] = useReducer(activityReducer, initialActivityState);
  const liveActivityIdRef = useRef<string | null>(null);

  const selectedActivity = useMemo(
    () =>
      state.activities.find((item) => item.id === state.selectedActivityId) ??
      state.activities[0] ??
      null,
    [state.activities, state.selectedActivityId],
  );
  const selectedActivityId = selectedActivity?.id ?? null;

  const selectActivity = useCallback((id: string | null) => {
    dispatch({ type: "select", id });
  }, []);

  const startActivity = useCallback(
    (kind: ActivityKind, init?: Partial<Activity>, options?: StartActivityOptions) => {
      const id = init?.id ?? createActivityId();
      const startedAt = init?.startedAt ?? new Date().toISOString();
      const status: ActivityStatus = init?.status ?? "running";
      const activity: Activity = {
        id,
        kind,
        status,
        startedAt,
        finishedAt: init?.finishedAt,
        label: init?.label ?? DEFAULT_LABELS[kind],
        metadata: init?.metadata,
        summary: init?.summary,
        errorMessage: init?.errorMessage,
        outputLinks: init?.outputLinks,
        outputs: init?.outputs,
        outputsLoaded: init?.outputsLoaded,
        logs: init?.logs ?? [],
        issues: init?.issues ?? [],
        errorCount: init?.errorCount,
        warningCount: init?.warningCount,
      };
      dispatch({ type: "start", activity, select: options?.select });
      if (options?.live ?? status === "running") {
        liveActivityIdRef.current = id;
      }
      return { id, startedAt };
    },
    [],
  );

  const appendLog = useCallback(
    (id: string | null, line: WorkbenchConsoleLine) => {
      if (!id) {
        return;
      }
      dispatch({ type: "append-log", id, line });
    },
    [],
  );

  const appendIssues = useCallback(
    (id: string | null, issues: ValidationIssue[]) => {
      if (!id || issues.length === 0) {
        return;
      }
      dispatch({ type: "append-issues", id, issues });
    },
    [],
  );

  const patchActivity = useCallback(
    (id: string | null, patch: Partial<Activity>) => {
      if (!id) {
        return;
      }
      dispatch({ type: "patch", id, patch });
    },
    [],
  );

  const completeActivity = useCallback(
    (
      id: string | null,
      status: ActivityStatus,
      patch?: { readonly finishedAt?: string; readonly summary?: string | null; readonly errorMessage?: string | null },
    ) => {
      if (!id) {
        return;
      }
      dispatch({
        type: "complete",
        id,
        status,
        finishedAt: patch?.finishedAt,
        summary: patch?.summary,
        errorMessage: patch?.errorMessage,
      });
      if (liveActivityIdRef.current === id) {
        liveActivityIdRef.current = null;
      }
    },
    [],
  );

  const setLiveActivityId = useCallback((id: string | null) => {
    liveActivityIdRef.current = id;
  }, []);

  const resolveActivityId = useCallback(
    (preferredId?: string | null) => {
      if (preferredId) {
        return preferredId;
      }
      const liveId = liveActivityIdRef.current;
      if (liveId && state.activities.some((item) => item.id === liveId)) {
        return liveId;
      }
      if (state.selectedActivityId && state.activities.some((item) => item.id === state.selectedActivityId)) {
        return state.selectedActivityId;
      }
      return state.activities[0]?.id ?? null;
    },
    [state.activities, state.selectedActivityId],
  );

  const runningByKind = useMemo(
    () => ({
      build:
        state.activities.find((item) => item.kind === "build" && item.status === "running") ??
        null,
      validation:
        state.activities.find((item) => item.kind === "validation" && item.status === "running") ??
        null,
      extraction:
        state.activities.find((item) => item.kind === "extraction" && item.status === "running") ??
        null,
    }),
    [state.activities],
  );

  const latestByKind = useMemo(
    () => ({
      build: state.activities.find((item) => item.kind === "build") ?? null,
      validation: state.activities.find((item) => item.kind === "validation") ?? null,
      extraction: state.activities.find((item) => item.kind === "extraction") ?? null,
    }),
    [state.activities],
  );

  return {
    state,
    selectedActivity,
    selectedActivityId,
    selectActivity,
    startActivity,
    appendLog,
    appendIssues,
    completeActivity,
    patchActivity,
    setLiveActivityId,
    resolveActivityId,
    runningByKind,
    latestByKind,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchFiles.ts
```typescript
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { WorkbenchFileMetadata, WorkbenchFileNode, WorkbenchFileTab } from "../types";
import { findFileNode, findFirstFile } from "../utils/tree";

interface WorkbenchFilesPersistence {
  readonly get: <T>() => T | null;
  readonly set: <T>(value: T) => void;
  readonly clear: () => void;
}

interface PersistedWorkbenchTabEntry {
  readonly id: string;
  readonly pinned?: boolean;
}

interface PersistedWorkbenchTabs {
  readonly openTabs: readonly (string | PersistedWorkbenchTabEntry)[];
  readonly activeTabId?: string | null;
  readonly mru?: readonly string[];
}

interface UseWorkbenchFilesOptions {
  readonly tree: WorkbenchFileNode | null;
  readonly initialActiveFileId?: string;
  readonly loadFile: (fileId: string) => Promise<{ content: string; etag?: string | null }>;
  readonly persistence?: WorkbenchFilesPersistence | null;
}

type WorkbenchTabZone = "pinned" | "regular";

interface MoveTabOptions {
  readonly zone?: WorkbenchTabZone;
}

interface WorkbenchFilesApi {
  readonly tree: WorkbenchFileNode | null;
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly activeTab: WorkbenchFileTab | null;
  readonly openFile: (fileId: string) => void;
  readonly selectTab: (fileId: string) => void;
  readonly closeTab: (fileId: string) => void;
  readonly closeOtherTabs: (fileId: string) => void;
  readonly closeTabsToRight: (fileId: string) => void;
  readonly closeAllTabs: () => void;
  readonly moveTab: (fileId: string, targetIndex: number, options?: MoveTabOptions) => void;
  readonly pinTab: (fileId: string) => void;
  readonly unpinTab: (fileId: string) => void;
  readonly toggleTabPin: (fileId: string, pinned: boolean) => void;
  readonly selectRecentTab: (direction: "forward" | "backward") => void;
  readonly updateContent: (fileId: string, content: string) => void;
  readonly beginSavingTab: (fileId: string) => void;
  readonly completeSavingTab: (
    fileId: string,
    options?: { metadata?: WorkbenchFileMetadata; etag?: string | null },
  ) => void;
  readonly failSavingTab: (fileId: string, message: string) => void;
  readonly replaceTabContent: (
    fileId: string,
    payload: { content: string; metadata?: WorkbenchFileMetadata; etag?: string | null },
  ) => void;
  readonly isDirty: boolean;
}

export function useWorkbenchFiles({
  tree,
  initialActiveFileId,
  loadFile,
  persistence,
}: UseWorkbenchFilesOptions): WorkbenchFilesApi {
  const [tabs, setTabs] = useState<WorkbenchFileTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string>("");
  const [recentOrder, setRecentOrder] = useState<string[]>([]);
  const [hasHydratedPersistence, setHasHydratedPersistence] = useState(() => !persistence);
  const [hasOpenedInitialTab, setHasOpenedInitialTab] = useState(false);
  const pendingLoadsRef = useRef<Set<string>>(new Set());
  const tabsRef = useRef<WorkbenchFileTab[]>([]);
  const activeTabIdRef = useRef<string>("");
  const recentOrderRef = useRef<string[]>([]);

  const setActiveTab = useCallback((nextActiveId: string) => {
    setActiveTabId((prev) => (prev === nextActiveId ? prev : nextActiveId));
    setRecentOrder((current) => {
      const sanitized = current.filter((id) => tabsRef.current.some((tab) => tab.id === id));
      if (!nextActiveId) {
        return sanitized;
      }
      const withoutNext = sanitized.filter((id) => id !== nextActiveId);
      return [nextActiveId, ...withoutNext];
    });
  }, []);

  useEffect(() => {
    activeTabIdRef.current = activeTabId;
  }, [activeTabId]);

  useEffect(() => {
    recentOrderRef.current = recentOrder;
  }, [recentOrder]);

  useEffect(() => {
    if (!tree) {
      setTabs([]);
      setActiveTabId("");
      setRecentOrder([]);
      return;
    }
    setTabs((current) =>
      current
        .filter((tab) => Boolean(findFileNode(tree, tab.id)))
        .map((tab) => {
          const node = findFileNode(tree, tab.id);
          if (!node || node.kind !== "file") {
            return tab;
          }
          return {
            ...tab,
            name: node.name,
            language: node.language,
            metadata: node.metadata,
          };
        }),
    );
    const prevActive = activeTabIdRef.current;
    if (!prevActive || !findFileNode(tree, prevActive)) {
      setActiveTab("");
    }
  }, [tree, setActiveTab]);

  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0] ?? null,
    [activeTabId, tabs],
  );

  const loadIntoTab = useCallback(
    async (fileId: string) => {
      if (!tabsRef.current.some((tab) => tab.id === fileId)) {
        return;
      }
      let alreadyReady = false;
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          if (tab.status === "ready") {
            alreadyReady = true;
            return tab;
          }
          return { ...tab, status: "loading", error: null };
        }),
      );

      if (alreadyReady) {
        return;
      }

      try {
        const payload = await loadFile(fileId);
        setTabs((current) =>
          current.map((tab) =>
            tab.id === fileId
              ? {
                  ...tab,
                  initialContent: payload.content,
                  content: payload.content,
                  status: "ready",
                  error: null,
                  etag: payload.etag ?? null,
                  saving: false,
                  saveError: null,
                }
              : tab,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to load file.";
        setTabs((current) =>
          current.map((tab) => (tab.id === fileId ? { ...tab, status: "error", error: message } : tab)),
        );
      }
    },
    [loadFile],
  );

  const ensureFileOpen = useCallback(
    (fileId: string, options?: { activate?: boolean }) => {
      if (!tree) {
        return;
      }
      const node = findFileNode(tree, fileId);
      if (!node || node.kind !== "file") {
        return;
      }
      setTabs((current) => {
        if (current.some((tab) => tab.id === fileId)) {
          return current;
        }
        const nextTab: WorkbenchFileTab = {
          id: node.id,
          name: node.name,
          language: node.language,
          initialContent: "",
          content: "",
          status: "loading",
          error: null,
          etag: null,
          metadata: node.metadata,
          pinned: false,
          saving: false,
          saveError: null,
          lastSavedAt: null,
        };
        return [...current, nextTab];
      });
      if (options?.activate ?? true) {
        setActiveTab(fileId);
      }
    },
    [tree, setActiveTab],
  );

  useEffect(() => {
    if (hasHydratedPersistence || !persistence || !tree) {
      if (!persistence) {
        setHasHydratedPersistence(true);
      }
      return;
    }

    const snapshot = persistence.get<PersistedWorkbenchTabs>();
    const candidateEntries = snapshot?.openTabs ?? [];
    const normalizedEntries = candidateEntries
      .map((entry) => (typeof entry === "string" ? { id: entry, pinned: false } : entry))
      .filter((entry): entry is PersistedWorkbenchTabEntry => Boolean(entry && entry.id));

    if (normalizedEntries.length > 0) {
      const nextTabs: WorkbenchFileTab[] = [];

      for (const entry of normalizedEntries) {
        const node = findFileNode(tree, entry.id);
        if (!node || node.kind !== "file") {
          continue;
        }
        nextTabs.push({
          id: node.id,
          name: node.name,
          language: node.language,
          initialContent: "",
          content: "",
          status: "loading",
          error: null,
          etag: null,
          metadata: node.metadata,
          pinned: Boolean(entry.pinned),
          saving: false,
          saveError: null,
          lastSavedAt: null,
        });
      }

      if (nextTabs.length > 0) {
        setTabs(nextTabs);
        const preferredActiveId =
          (snapshot?.activeTabId && nextTabs.some((tab) => tab.id === snapshot.activeTabId)
            ? snapshot.activeTabId
            : nextTabs[0]?.id) ?? "";
        setActiveTabId(preferredActiveId);
        const preferredMru =
          snapshot?.mru && snapshot.mru.length > 0 ? snapshot.mru : nextTabs.map((tab) => tab.id);
        const normalizedMru = preferredMru.filter((id) => nextTabs.some((tab) => tab.id === id));
        setRecentOrder(normalizedMru);
        setHasOpenedInitialTab(true);
      }
    }

    setHasHydratedPersistence(true);
  }, [hasHydratedPersistence, persistence, tree]);

  useEffect(() => {
    if (!tree || !hasHydratedPersistence) {
      return;
    }
    if (tabs.length > 0) {
      if (!hasOpenedInitialTab) {
        setHasOpenedInitialTab(true);
      }
      return;
    }
    if (hasOpenedInitialTab) {
      return;
    }
    const preferred = (initialActiveFileId && findFileNode(tree, initialActiveFileId)) || findFirstFile(tree);
    if (!preferred) {
      setHasOpenedInitialTab(true);
      return;
    }
    ensureFileOpen(preferred.id);
    setHasOpenedInitialTab(true);
  }, [
    tree,
    initialActiveFileId,
    ensureFileOpen,
    hasHydratedPersistence,
    tabs.length,
    hasOpenedInitialTab,
  ]);

  const openFile = useCallback(
    (fileId: string) => {
      ensureFileOpen(fileId);
    },
    [ensureFileOpen],
  );

  const selectTab = useCallback(
    (fileId: string) => {
      setActiveTab(fileId);
      setTabs((current) =>
        current.map((tab) =>
          tab.id === fileId && tab.status === "error" ? { ...tab, status: "loading", error: null } : tab,
        ),
      );
    },
    [setActiveTab],
  );

  const closeTab = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        const remaining = current.filter((tab) => tab.id !== fileId);
        const prevActive = activeTabIdRef.current;
        const nextActiveId =
          prevActive === fileId
            ? remaining[remaining.length - 1]?.id ?? ""
            : remaining.some((tab) => tab.id === prevActive)
              ? prevActive
              : remaining[remaining.length - 1]?.id ?? "";
        setActiveTab(nextActiveId);
        return remaining;
      });
    },
    [setActiveTab],
  );

  const closeOtherTabs = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        if (!current.some((tab) => tab.id === fileId) || current.length <= 1) {
          return current;
        }
        setActiveTab(fileId);
        return current.filter((tab) => tab.id === fileId);
      });
    },
    [setActiveTab],
  );

  const closeTabsToRight = useCallback(
    (fileId: string) => {
      setTabs((current) => {
        const targetIndex = current.findIndex((tab) => tab.id === fileId);
        if (targetIndex === -1 || targetIndex === current.length - 1) {
          return current;
        }
        const next = current.slice(0, targetIndex + 1);
        const nextActiveId = next.some((tab) => tab.id === activeTabIdRef.current)
          ? activeTabIdRef.current
          : fileId;
        setActiveTab(nextActiveId);
        return next;
      });
    },
    [setActiveTab],
  );

  const closeAllTabs = useCallback(() => {
    setTabs([]);
    setActiveTabId("");
    setRecentOrder([]);
  }, []);

  const moveTab = useCallback(
    (fileId: string, targetIndex: number, options?: MoveTabOptions) => {
      setTabs((current) => {
        if (current.length <= 1) {
          return current;
        }
        const fromIndex = current.findIndex((tab) => tab.id === fileId);
        if (fromIndex === -1) {
          return current;
        }
        const boundedTarget = Math.max(0, Math.min(targetIndex, current.length));
        let insertIndex = boundedTarget;
        if (fromIndex < boundedTarget) {
          insertIndex -= 1;
        }
        const pinned: WorkbenchFileTab[] = [];
        const regular: WorkbenchFileTab[] = [];
        let moving: WorkbenchFileTab | null = null;
        current.forEach((tab, index) => {
          if (index === fromIndex) {
            moving = tab;
            return;
          }
          if (tab.pinned) {
            pinned.push(tab);
          } else {
            regular.push(tab);
          }
        });
        if (!moving) {
          return current;
        }
        const zone: WorkbenchTabZone =
          options?.zone ?? (insertIndex <= pinned.length ? "pinned" : "regular");
        if (zone === "pinned") {
          const clampedIndex = Math.max(0, Math.min(insertIndex, pinned.length));
          pinned.splice(clampedIndex, 0, { ...moving, pinned: true });
        } else {
          const relativeIndex = Math.max(0, Math.min(insertIndex - pinned.length, regular.length));
          regular.splice(relativeIndex, 0, { ...moving, pinned: false });
        }
        return [...pinned, ...regular];
      });
    },
    [],
  );

  const pinTab = useCallback((fileId: string) => {
    setTabs((current) => {
      const pinned: WorkbenchFileTab[] = [];
      const regular: WorkbenchFileTab[] = [];
      let target: WorkbenchFileTab | null = null;
      for (const tab of current) {
        if (tab.id === fileId) {
          target = tab;
          continue;
        }
        if (tab.pinned) {
          pinned.push(tab);
        } else {
          regular.push(tab);
        }
      }
      if (!target || target.pinned) {
        return current;
      }
      const updated = { ...target, pinned: true };
      return [...pinned, updated, ...regular];
    });
  }, []);

  const unpinTab = useCallback((fileId: string) => {
    setTabs((current) => {
      const pinned: WorkbenchFileTab[] = [];
      const regular: WorkbenchFileTab[] = [];
      let target: WorkbenchFileTab | null = null;
      for (const tab of current) {
        if (tab.id === fileId) {
          target = tab;
          continue;
        }
        if (tab.pinned) {
          pinned.push(tab);
        } else {
          regular.push(tab);
        }
      }
      if (!target || !target.pinned) {
        return current;
      }
      const updated = { ...target, pinned: false };
      return [...pinned, updated, ...regular];
    });
  }, []);

  const toggleTabPin = useCallback(
    (fileId: string, pinned: boolean) => {
      if (pinned) {
        pinTab(fileId);
      } else {
        unpinTab(fileId);
      }
    },
    [pinTab, unpinTab],
  );

  const selectRecentTab = useCallback(
    (direction: "forward" | "backward") => {
      const ordered = recentOrderRef.current.filter((id) =>
        tabsRef.current.some((tab) => tab.id === id),
      );
      if (ordered.length <= 1) {
        return;
      }
      const activeId = activeTabIdRef.current || ordered[0];
      const currentIndex = ordered.indexOf(activeId);
      const safeIndex = currentIndex >= 0 ? currentIndex : 0;
      const delta = direction === "forward" ? 1 : -1;
      const nextIndex = (safeIndex + delta + ordered.length) % ordered.length;
      const nextId = ordered[nextIndex];
      if (nextId && nextId !== activeId) {
        setActiveTab(nextId);
      }
    },
    [setActiveTab],
  );

  const updateContent = useCallback((fileId: string, content: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              content,
              status: tab.status === "ready" ? tab.status : "ready",
              error: null,
              saveError: null,
            }
          : tab,
      ),
    );
  }, []);

  const beginSavingTab = useCallback((fileId: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              saving: true,
              saveError: null,
            }
          : tab,
      ),
    );
  }, []);

  const completeSavingTab = useCallback(
    (fileId: string, options?: { metadata?: WorkbenchFileMetadata; etag?: string | null }) => {
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          const resolvedMetadata = options?.metadata ?? tab.metadata ?? null;
          const resolvedEtag = options?.etag ?? tab.etag ?? null;
          return {
            ...tab,
            saving: false,
            saveError: null,
            initialContent: tab.content,
            etag: resolvedEtag,
            metadata: resolvedMetadata
              ? {
                  ...resolvedMetadata,
                  etag: resolvedMetadata.etag ?? resolvedEtag ?? null,
                }
              : resolvedMetadata,
            lastSavedAt: new Date().toISOString(),
          };
        }),
      );
    },
    [],
  );

  const failSavingTab = useCallback((fileId: string, message: string) => {
    setTabs((current) =>
      current.map((tab) =>
        tab.id === fileId
          ? {
              ...tab,
              saving: false,
              saveError: message,
            }
          : tab,
      ),
    );
  }, []);

  const replaceTabContent = useCallback(
    (fileId: string, payload: { content: string; metadata?: WorkbenchFileMetadata; etag?: string | null }) => {
      setTabs((current) =>
        current.map((tab) => {
          if (tab.id !== fileId) {
            return tab;
          }
          return {
            ...tab,
            content: payload.content,
            initialContent: payload.content,
            status: "ready",
            error: null,
            saving: false,
            saveError: null,
            etag: payload.etag ?? tab.etag ?? null,
            metadata: payload.metadata ?? tab.metadata,
          };
        }),
      );
    },
    [],
  );

  const isDirty = useMemo(
    () => tabs.some((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [tabs],
  );

  useEffect(() => {
    tabsRef.current = tabs;
  }, [tabs]);

  useEffect(() => {
    setRecentOrder((current) => {
      const filtered = current.filter((id) => tabs.some((tab) => tab.id === id));
      return filtered.length === current.length ? current : filtered;
    });
  }, [tabs]);

  useEffect(() => {
    const visibleTabIds = new Set(tabs.map((tab) => tab.id));
    for (const pendingId of pendingLoadsRef.current) {
      if (!visibleTabIds.has(pendingId)) {
        pendingLoadsRef.current.delete(pendingId);
      }
    }
    for (const tab of tabs) {
      if (tab.status !== "loading" || pendingLoadsRef.current.has(tab.id)) {
        continue;
      }
      pendingLoadsRef.current.add(tab.id);
      const pending = loadIntoTab(tab.id);
      pending.finally(() => {
        pendingLoadsRef.current.delete(tab.id);
      });
    }
  }, [tabs, loadIntoTab]);

  useEffect(() => {
    if (!persistence || !hasHydratedPersistence) {
      return;
    }
    const orderedRecentTabs = [activeTabId, ...recentOrder]
      .filter((id): id is string => Boolean(id))
      .filter((id, index, array) => array.indexOf(id) === index)
      .filter((id) => tabs.some((tab) => tab.id === id));
    persistence.set<PersistedWorkbenchTabs>({
      openTabs: tabs.map((tab) => ({ id: tab.id, pinned: Boolean(tab.pinned) })),
      activeTabId: activeTabId || null,
      mru: orderedRecentTabs,
    });
  }, [persistence, tabs, activeTabId, recentOrder, hasHydratedPersistence]);

  return {
    tree,
    tabs,
    activeTabId,
    activeTab,
    openFile,
    selectTab,
    closeTab,
    closeOtherTabs,
    closeTabsToRight,
    closeAllTabs,
    moveTab,
    pinTab,
    unpinTab,
    toggleTabPin,
    selectRecentTab,
    updateContent,
    beginSavingTab,
    completeSavingTab,
    failSavingTab,
    replaceTabContent,
    isDirty,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchUrlState.ts
```typescript
import { useCallback, useMemo } from "react";

import {
  DEFAULT_CONFIG_BUILDER_SEARCH,
  mergeConfigBuilderSearch,
  readConfigBuilderSearch,
  useSearchParams,
} from "@app/nav/urlState";
import type { ConfigBuilderConsole, ConfigBuilderPane } from "@app/nav/urlState";

interface WorkbenchUrlState {
  readonly fileId?: string;
  readonly pane: ConfigBuilderPane;
  readonly console: ConfigBuilderConsole;
  readonly consoleExplicit: boolean;
  readonly setFileId: (fileId: string | undefined) => void;
  readonly setPane: (pane: ConfigBuilderPane) => void;
  readonly setConsole: (console: ConfigBuilderConsole) => void;
}

export function useWorkbenchUrlState(): WorkbenchUrlState {
  const [params, setSearchParams] = useSearchParams();
  const snapshot = useMemo(() => readConfigBuilderSearch(params), [params]);

  const setFileId = useCallback(
    (fileId: string | undefined) => {
      if (snapshot.file === fileId || (!fileId && !snapshot.present.file)) {
        return;
      }
      setSearchParams((current) => mergeConfigBuilderSearch(current, { file: fileId ?? undefined }), {
        replace: true,
      });
    },
    [setSearchParams, snapshot.file, snapshot.present.file],
  );

  const setPane = useCallback(
    (pane: ConfigBuilderPane) => {
      if (snapshot.pane === pane) {
        return;
      }
      setSearchParams((current) => mergeConfigBuilderSearch(current, { pane }), { replace: true });
    },
    [setSearchParams, snapshot.pane],
  );

  const setConsole = useCallback(
    (console: ConfigBuilderConsole) => {
      if (snapshot.console === console) {
        return;
      }
      setSearchParams((current) => mergeConfigBuilderSearch(current, { console }), { replace: true });
    },
    [setSearchParams, snapshot.console],
  );

  return {
    fileId: snapshot.file ?? DEFAULT_CONFIG_BUILDER_SEARCH.file,
    pane: snapshot.pane,
    console: snapshot.console,
    consoleExplicit: snapshot.present.console,
    setFileId,
    setPane,
    setConsole,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState.ts
```typescript
export function getWorkbenchReturnPathStorageKey(workspaceId: string) {
  return `ade.ui.workspace.${workspaceId}.workbench.returnPath`;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/types.ts
```typescript
export type WorkbenchFileKind = "file" | "folder";

export interface WorkbenchFileMetadata {
  size?: number | null;
  modifiedAt?: string | null;
  contentType?: string | null;
  etag?: string | null;
}

export interface WorkbenchFileNode {
  id: string;
  name: string;
  kind: WorkbenchFileKind;
  language?: string;
  children?: WorkbenchFileNode[];
  metadata?: WorkbenchFileMetadata | null;
}

export type WorkbenchFileTabStatus = "loading" | "ready" | "error";

export interface WorkbenchFileTab {
  id: string;
  name: string;
  language?: string;
  initialContent: string;
  content: string;
  status: WorkbenchFileTabStatus;
  error?: string | null;
  etag?: string | null;
  metadata?: WorkbenchFileMetadata | null;
  pinned?: boolean;
  saving?: boolean;
  saveError?: string | null;
  lastSavedAt?: string | null;
}

export type WorkbenchConsoleLevel = "info" | "success" | "warning" | "error";

export interface WorkbenchConsoleLine {
  readonly level: WorkbenchConsoleLevel;
  readonly message: string;
  readonly timestamp?: string;
}

export interface WorkbenchValidationMessage {
  readonly level: "info" | "warning" | "error";
  readonly message: string;
  readonly path?: string;
}

export interface WorkbenchDataSeed {
  readonly tree: WorkbenchFileNode;
  readonly content: Record<string, string>;
  readonly console?: readonly WorkbenchConsoleLine[];
  readonly validation?: readonly WorkbenchValidationMessage[];
}

export interface WorkbenchValidationState {
  readonly status: "idle" | "running" | "success" | "error";
  readonly messages: readonly WorkbenchValidationMessage[];
  readonly lastRunAt?: string;
  readonly error?: string | null;
  readonly digest?: string | null;
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/__tests__/console.test.ts
```typescript
import { describe, expect, it } from "vitest";

import type { BuildCompletedEvent, BuildLogEvent, BuildStepEvent } from "@shared/builds/types";
import type { RunCompletedEvent, RunLogEvent } from "@shared/runs/types";
import type { TelemetryEnvelope } from "@schema/adeTelemetry";

import { describeBuildEvent, describeRunEvent, formatConsoleTimestamp } from "../console";

describe("formatConsoleTimestamp", () => {
  it("formats epoch seconds", () => {
    const label = formatConsoleTimestamp(1_700_000_000);
    expect(label).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });

  it("handles invalid date", () => {
    expect(formatConsoleTimestamp(new Date("invalid"))).toBe("");
  });
});

describe("describeBuildEvent", () => {
  it("formats build step events", () => {
    const event: BuildStepEvent = {
      object: "ade.build.event",
      build_id: "build_123",
      created: 1_700_000_001,
      type: "build.step",
      step: "install_engine",
      message: null,
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("info");
    expect(line.message).toContain("ade_engine");
  });

  it("promotes stderr logs to warnings", () => {
    const event: BuildLogEvent = {
      object: "ade.build.event",
      build_id: "build_123",
      created: 1_700_000_002,
      type: "build.log",
      stream: "stderr",
      message: "pip install failed",
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toBe("pip install failed");
  });

  it("marks successful completion as success", () => {
    const event: BuildCompletedEvent = {
      object: "ade.build.event",
      build_id: "build_123",
      created: 1_700_000_010,
      type: "build.completed",
      status: "active",
      exit_code: 0,
      error_message: null,
      summary: "ready",
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toBe("ready");
  });
});

describe("describeRunEvent", () => {
  it("treats stderr logs as warnings", () => {
    const event: RunLogEvent = {
      object: "ade.run.event",
      run_id: "run_123",
      created: 1_700_000_020,
      type: "run.log",
      stream: "stderr",
      message: "warning: detector failed",
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("detector failed");
  });

  it("marks failed completion as error", () => {
    const event: RunCompletedEvent = {
      object: "ade.run.event",
      run_id: "run_123",
      created: 1_700_000_030,
      type: "run.completed",
      status: "failed",
      exit_code: 2,
      error_message: "Runtime error",
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("Runtime error");
    expect(line.message).toContain("exit code 2");
  });

  it("formats telemetry envelopes", () => {
    const event: TelemetryEnvelope = {
      schema: "ade.telemetry/run-event.v1",
      version: "1.0.0",
      job_id: "job_1",
      run_id: "run_123",
      timestamp: new Date().toISOString(),
      event: {
        event: "pipeline_transition",
        level: "warning",
        phase: "mapping",
      },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("pipeline_transition");
    expect(line.message).toContain("phase");
  });
});
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/__tests__/tree.test.ts
```typescript
import { describe, expect, it } from "vitest";

import { createWorkbenchTreeFromListing } from "../tree";

import type { FileListing } from "@shared/configs/types";

const ISO = "2024-01-01T00:00:00.000Z";

function createListing(): FileListing {
  return {
    workspace_id: "workspace-1",
    config_id: "config-1",
    status: "active" as FileListing["status"],
    capabilities: { editable: true, can_create: true, can_delete: true, can_rename: true },
    root: "ade_config",
    prefix: "",
    depth: "infinity",
    generated_at: ISO,
    fileset_hash: "hash",
    summary: { files: 2, directories: 2 },
    limits: { code_max_bytes: 1024, asset_max_bytes: 2048 },
    count: 4,
    next_token: null,
    entries: [
      {
        path: "ade_config",
        name: "ade_config",
        parent: "",
        kind: "dir",
        depth: 0,
        size: null,
        mtime: ISO,
        etag: "root",
        content_type: "inode/directory",
        has_children: true,
      },
      {
        path: "ade_config/manifest.json",
        name: "manifest.json",
        parent: "ade_config",
        kind: "file",
        depth: 1,
        size: 100,
        mtime: ISO,
        etag: "manifest",
        content_type: "application/json",
        has_children: false,
      },
      {
        path: "ade_config/hooks",
        name: "hooks",
        parent: "ade_config",
        kind: "dir",
        depth: 1,
        size: null,
        mtime: ISO,
        etag: "hooks",
        content_type: "inode/directory",
        has_children: true,
      },
      {
        path: "ade_config/hooks/normalize.py",
        name: "normalize.py",
        parent: "ade_config/hooks",
        kind: "file",
        depth: 2,
        size: 120,
        mtime: ISO,
        etag: "normalize",
        content_type: "text/x-python",
        has_children: false,
      },
    ],
  };
}

describe("createWorkbenchTreeFromListing", () => {
  it("builds a nested tree with inferred languages", () => {
    const listing = createListing();
    const tree = createWorkbenchTreeFromListing(listing);

    expect(tree).not.toBeNull();
    expect(tree?.id).toBe("ade_config");
    expect(tree?.children?.map((node) => node.name)).toEqual(["hooks", "manifest.json"]);

    const hooks = tree?.children?.find((node) => node.name === "hooks");
    expect(hooks?.kind).toBe("folder");
    expect(hooks?.children?.[0]?.name).toBe("normalize.py");
    expect(hooks?.children?.[0]?.language).toBe("python");
    expect(hooks?.children?.[0]?.metadata).toEqual({
      size: 120,
      modifiedAt: ISO,
      contentType: "text/x-python",
      etag: "normalize",
    });

    const manifest = tree?.children?.find((node) => node.name === "manifest.json");
    expect(manifest?.language).toBe("json");
    expect(manifest?.metadata).toEqual({
      size: 100,
      modifiedAt: ISO,
      contentType: "application/json",
      etag: "manifest",
    });
  });

  it("creates a virtual root when listing root is empty", () => {
    const listing = createListing();
    listing.root = "";
    listing.prefix = "";

    const tree = createWorkbenchTreeFromListing(listing);
    expect(tree).not.toBeNull();
    expect(tree?.id).toBe("");
    expect(tree?.children?.[0]?.name).toBe("ade_config");
  });

  it("represents canonical directory parents without trailing slashes", () => {
    const listing = createListing();
    listing.root = "";
    listing.prefix = "";
    listing.entries = [
      {
        path: "src",
        name: "src",
        parent: "",
        kind: "dir",
        depth: 0,
        size: null,
        mtime: ISO,
        etag: "src",
        content_type: "inode/directory",
        has_children: true,
      },
      {
        path: "src/ade_config",
        name: "ade_config",
        parent: "src",
        kind: "dir",
        depth: 1,
        size: null,
        mtime: ISO,
        etag: "ade-config",
        content_type: "inode/directory",
        has_children: true,
      },
      {
        path: "src/ade_config/hooks",
        name: "hooks",
        parent: "src/ade_config",
        kind: "dir",
        depth: 2,
        size: null,
        mtime: ISO,
        etag: "hooks",
        content_type: "inode/directory",
        has_children: true,
      },
      {
        path: "src/ade_config/manifest.json",
        name: "manifest.json",
        parent: "src/ade_config",
        kind: "file",
        depth: 2,
        size: 120,
        mtime: ISO,
        etag: "manifest",
        content_type: "application/json",
        has_children: false,
      },
    ];

    const tree = createWorkbenchTreeFromListing(listing);
    expect(tree?.children?.map((node) => node.id)).toEqual(["src"]);
    const src = tree?.children?.[0];
    expect(src?.children?.map((node) => node.id)).toEqual(["src/ade_config"]);
    const adeConfig = src?.children?.[0];
    expect(adeConfig?.children?.map((node) => node.id).sort()).toEqual([
      "src/ade_config/hooks",
      "src/ade_config/manifest.json",
    ]);
  });
});
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts
```typescript
import type { BuildEvent, BuildCompletedEvent, BuildLogEvent, BuildStepEvent } from "@shared/builds/types";
import { isTelemetryEnvelope } from "@shared/runs/types";
import type { RunCompletedEvent, RunLogEvent, RunStreamEvent } from "@shared/runs/types";
import type { TelemetryEnvelope } from "@schema/adeTelemetry";

import type { WorkbenchConsoleLine } from "../types";

const TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
};

export function formatConsoleTimestamp(value: number | Date): string {
  const date = typeof value === "number" ? new Date(value * 1000) : value;
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString([], TIME_OPTIONS);
}

export function describeBuildEvent(event: BuildEvent): WorkbenchConsoleLine {
  switch (event.type) {
    case "build.created":
      return {
        level: "info",
        message: `Build ${event.build_id} created (status: ${event.status}).`,
        timestamp: formatConsoleTimestamp(event.created),
      };
    case "build.step":
      return formatBuildStep(event);
    case "build.log":
      return formatBuildLog(event);
    case "build.completed":
      return formatBuildCompletion(event);
    default:
      return {
        level: "info",
        message: JSON.stringify(event),
        timestamp: formatConsoleTimestamp(event.created),
      };
  }
}

export function describeRunEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (isTelemetryEnvelope(event)) {
    return formatTelemetry(event);
  }
  switch (event.type) {
    case "run.created":
      return {
        level: "info",
        message: `Run ${event.run_id} created (status: ${event.status}).`,
        timestamp: formatConsoleTimestamp(event.created),
      };
    case "run.started":
      return {
        level: "info",
        message: "Run started.",
        timestamp: formatConsoleTimestamp(event.created),
      };
    case "run.log":
      return formatRunLog(event);
    case "run.completed":
      return formatRunCompletion(event);
    default: {
      const neverEvent: never = event;
      return {
        level: "info",
        message: JSON.stringify(neverEvent),
        timestamp: "",
      };
    }
  }
}

function formatTelemetry(event: TelemetryEnvelope): WorkbenchConsoleLine {
  const { event: payload, timestamp } = event;
  const { event: name, level, ...rest } = payload;
  const normalizedLevel = telemetryToConsoleLevel(level);
  const extras = Object.keys(rest).length > 0 ? ` ${JSON.stringify(rest)}` : "";
  return {
    level: normalizedLevel,
    message: extras ? `Telemetry: ${name}${extras}` : `Telemetry: ${name}`,
    timestamp: formatConsoleTimestamp(new Date(timestamp)),
  };
}

function telemetryToConsoleLevel(level: TelemetryEnvelope["event"]["level"]): WorkbenchConsoleLine["level"] {
  switch (level) {
    case "warning":
      return "warning";
    case "error":
    case "critical":
      return "error";
    default:
      return "info";
  }
}

function formatBuildStep(event: BuildStepEvent): WorkbenchConsoleLine {
  const friendly = buildStepDescriptions[event.step] ?? event.step.replaceAll("_", " ");
  const message = event.message?.trim() ? event.message : friendly;
  return {
    level: "info",
    message,
    timestamp: formatConsoleTimestamp(event.created),
  };
}

const buildStepDescriptions: Record<BuildStepEvent["step"], string> = {
  create_venv: "Creating virtual environment…",
  upgrade_pip: "Upgrading pip inside the build environment…",
  install_engine: "Installing ade_engine package…",
  install_config: "Installing configuration package…",
  verify_imports: "Verifying ADE imports…",
  collect_metadata: "Collecting build metadata…",
};

function formatBuildLog(event: BuildLogEvent): WorkbenchConsoleLine {
  return {
    level: event.stream === "stderr" ? "warning" : "info",
    message: event.message,
    timestamp: formatConsoleTimestamp(event.created),
  };
}

function formatBuildCompletion(event: BuildCompletedEvent): WorkbenchConsoleLine {
  const timestamp = formatConsoleTimestamp(event.created);
  if (event.status === "active") {
    return {
      level: "success",
      message: event.summary?.trim() || "Build completed successfully.",
      timestamp,
    };
  }
  if (event.status === "canceled") {
    return {
      level: "warning",
      message: "Build was canceled before completion.",
      timestamp,
    };
  }
  const error = event.error_message?.trim() || "Build failed.";
  const exit = typeof event.exit_code === "number" ? ` (exit code ${event.exit_code})` : "";
  return {
    level: "error",
    message: `${error}${exit}`,
    timestamp,
  };
}

function formatRunLog(event: RunLogEvent): WorkbenchConsoleLine {
  return {
    level: event.stream === "stderr" ? "warning" : "info",
    message: event.message,
    timestamp: formatConsoleTimestamp(event.created),
  };
}

function formatRunCompletion(event: RunCompletedEvent): WorkbenchConsoleLine {
  const timestamp = formatConsoleTimestamp(event.created);
  if (event.status === "succeeded") {
    const exit = typeof event.exit_code === "number" ? ` (exit code ${event.exit_code})` : "";
    return {
      level: "success",
      message: `Run completed successfully${exit}.`,
      timestamp,
    };
  }
  if (event.status === "canceled") {
    return {
      level: "warning",
      message: "Run was canceled before completion.",
      timestamp,
    };
  }
  const error = event.error_message?.trim() || "Run failed.";
  const exit = typeof event.exit_code === "number" ? ` (exit code ${event.exit_code})` : "";
  return {
    level: "error",
    message: `${error}${exit}`,
    timestamp,
  };
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/drag.ts
```typescript
import type { PointerEvent as ReactPointerEvent } from "react";

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

interface PointerDragOptions {
  readonly onMove: (moveEvent: PointerEvent) => void;
  readonly onEnd?: (moveEvent: PointerEvent) => void;
  readonly cursor?: "col-resize" | "row-resize";
}

export function trackPointerDrag(event: ReactPointerEvent, options: PointerDragOptions) {
  const { onMove, onEnd, cursor } = options;

  if (typeof window === "undefined") {
    return;
  }

  event.preventDefault();

  const pointerId = event.pointerId;
  const target = event.currentTarget as HTMLElement;
  const previousCursor = document.body.style.cursor;
  const previousUserSelect = document.body.style.userSelect;
  let animationFrame: number | null = null;
  let lastMoveEvent: PointerEvent | null = null;
  let active = true;

  const cleanup = (finalEvent: PointerEvent) => {
    if (!active) {
      return;
    }
    active = false;
    if (animationFrame !== null) {
      cancelAnimationFrame(animationFrame);
      animationFrame = null;
    }
    document.body.style.cursor = previousCursor;
    document.body.style.userSelect = previousUserSelect;
    window.removeEventListener("pointermove", handleMove);
    window.removeEventListener("pointerup", handleUpOrCancel);
    window.removeEventListener("pointercancel", handleUpOrCancel);
    target.removeEventListener("lostpointercapture", handleLostCapture);
    if (target.hasPointerCapture?.(pointerId)) {
      try {
        target.releasePointerCapture(pointerId);
      } catch {
        // ignore release failures caused by stale handles
      }
    }
    if (onEnd) {
      onEnd(finalEvent);
    }
  };

  const handleMove = (moveEvent: PointerEvent) => {
    if (!active || moveEvent.pointerId !== pointerId) {
      return;
    }
    lastMoveEvent = moveEvent;
    if (animationFrame !== null) {
      return;
    }
    animationFrame = window.requestAnimationFrame(() => {
      animationFrame = null;
      if (lastMoveEvent) {
        onMove(lastMoveEvent);
      }
    });
  };

  const handleUpOrCancel = (pointerEvent: PointerEvent) => {
    if (pointerEvent.pointerId !== pointerId) {
      return;
    }
    cleanup(pointerEvent);
  };

  const handleLostCapture = (pointerEvent: PointerEvent) => {
    if (pointerEvent.pointerId !== pointerId) {
      return;
    }
    cleanup(pointerEvent);
  };

  if (cursor) {
    document.body.style.cursor = cursor;
  }
  document.body.style.userSelect = "none";

  try {
    target.setPointerCapture(pointerId);
  } catch {
    // Pointer capture is not critical; ignore failures (e.g., when ref is gone)
  }

  window.addEventListener("pointermove", handleMove);
  window.addEventListener("pointerup", handleUpOrCancel);
  window.addEventListener("pointercancel", handleUpOrCancel);
  target.addEventListener("lostpointercapture", handleLostCapture);
}
```

# apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/tree.ts
```typescript
import type { FileListing } from "@shared/configs/types";

import type { WorkbenchFileNode } from "../types";

const LANGUAGE_BY_EXTENSION: Record<string, string> = {
  json: "json",
  py: "python",
  ts: "typescript",
  tsx: "typescriptreact",
  js: "javascript",
  jsx: "javascriptreact",
  env: "dotenv",
  md: "markdown",
  yml: "yaml",
  yaml: "yaml",
  toml: "toml",
};

export function createWorkbenchTreeFromListing(listing: FileListing): WorkbenchFileNode | null {
  const rootId = listing.root || listing.prefix || listing.entries[0]?.parent || "";
  const hasEntries = listing.entries.length > 0;

  if (!rootId && !hasEntries) {
    return null;
  }

  const canonicalRootId = canonicalizePath(rootId);

  const rootNode: WorkbenchFileNode = {
    id: rootId,
    name: extractName(rootId),
    kind: "folder",
    children: [],
  };

  const nodes = new Map<string, WorkbenchFileNode>([[rootId, rootNode]]);

  const ensureFolder = (path: string): WorkbenchFileNode => {
    if (path.length === 0) {
      return rootNode;
    }
    const normalizedPath = canonicalizePath(path);
    const nodeId = normalizedPath === canonicalRootId ? rootId : normalizedPath;
    const existing = nodes.get(nodeId);
    if (existing) {
      return existing;
    }
    const folder: WorkbenchFileNode = {
      id: nodeId,
      name: extractName(nodeId),
      kind: "folder",
      children: [],
    };
    nodes.set(nodeId, folder);
    const parentPath = nodeId === rootId ? "" : deriveParent(nodeId) ?? rootId;
    const parentNode = ensureFolder(parentPath);
    addChild(parentNode, folder);
    return folder;
  };

  const sortedEntries = [...listing.entries].sort((a, b) => {
    if (a.depth !== b.depth) {
      return a.depth - b.depth;
    }
    return a.path.localeCompare(b.path);
  });

  for (const entry of sortedEntries) {
    const parentPath = entry.parent && entry.parent.length > 0 ? canonicalizePath(entry.parent) : rootId;
    const parentNode = ensureFolder(parentPath);

    if (entry.kind === "dir") {
      const folder = ensureFolder(entry.path);
      folder.name = entry.name;
      folder.metadata = {
        size: entry.size ?? null,
        modifiedAt: entry.mtime,
        contentType: entry.content_type,
        etag: entry.etag,
      };
      if (folder !== parentNode) {
        addChild(parentNode, folder);
      }
      continue;
    }

    const fileNode: WorkbenchFileNode = {
      id: entry.path,
      name: entry.name,
      kind: "file",
      language: inferLanguage(entry.path),
      metadata: {
        size: entry.size ?? null,
        modifiedAt: entry.mtime,
        contentType: entry.content_type,
        etag: entry.etag,
      },
    };
    nodes.set(entry.path, fileNode);
    addChild(parentNode, fileNode);
  }

  return rootNode;
}

function addChild(parent: WorkbenchFileNode, child: WorkbenchFileNode) {
  const existing = parent.children ?? [];
  const next = existing.some((node) => node.id === child.id)
    ? existing.map((node) => (node.id === child.id ? child : node))
    : [...existing, child];
  parent.children = next.sort(compareNodes);
}

function compareNodes(a: WorkbenchFileNode, b: WorkbenchFileNode): number {
  if (a.kind !== b.kind) {
    return a.kind === "folder" ? -1 : 1;
  }
  return a.name.localeCompare(b.name);
}

function inferLanguage(path: string): string | undefined {
  const normalized = path.toLowerCase();
  const extensionIndex = normalized.lastIndexOf(".");
  if (extensionIndex === -1) {
    return undefined;
  }
  const extension = normalized.slice(extensionIndex + 1);
  return LANGUAGE_BY_EXTENSION[extension];
}

function extractName(path: string): string {
  const normalized = canonicalizePath(path);
  if (!normalized) {
    return "";
  }
  const index = normalized.lastIndexOf("/");
  return index >= 0 ? normalized.slice(index + 1) : normalized;
}

function deriveParent(path: string): string | undefined {
  const normalized = canonicalizePath(path);
  if (!normalized) {
    return undefined;
  }
  const index = normalized.lastIndexOf("/");
  if (index === -1) {
    return "";
  }
  return normalized.slice(0, index);
}

function canonicalizePath(path: string): string {
  if (!path) {
    return "";
  }
  return path.replace(/\/+$/, "");
}

export function findFileNode(root: WorkbenchFileNode, id: string): WorkbenchFileNode | null {
  if (root.id === id) {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const match = findFileNode(child, id);
    if (match) {
      return match;
    }
  }
  return null;
}

export function findFirstFile(root: WorkbenchFileNode): WorkbenchFileNode | null {
  if (root.kind === "file") {
    return root;
  }
  if (!root.children) {
    return null;
  }
  for (const child of root.children) {
    const file = findFirstFile(child);
    if (file) {
      return file;
    }
  }
  return null;
}
```
