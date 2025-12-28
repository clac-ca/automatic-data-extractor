import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactElement } from "react";

import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";
import { useQueryClient } from "@tanstack/react-query";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useWorkspacesQuery, workspacesKeys, WORKSPACE_LIST_DEFAULT_PARAMS, writePreferredWorkspaceId, type WorkspaceProfile } from "@shared/workspaces";
import { WorkspaceProvider } from "@screens/Workspace/context/WorkspaceContext";
import { WorkbenchWindowProvider, useWorkbenchWindow } from "@screens/Workspace/context/WorkbenchWindowContext";
import { createScopedStorage } from "@shared/storage";
import { GlobalTopBar } from "@app/shell/GlobalTopBar";
import { ProfileDropdown } from "@app/shell/ProfileDropdown";
import { AboutVersionsModal } from "@app/shell/AboutVersionsModal";
import { WorkspaceNav, WorkspaceNavList } from "@screens/Workspace/components/WorkspaceNav";
import { defaultWorkspaceSection, getWorkspacePrimaryNavigation } from "@screens/Workspace/components/workspace-navigation";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import { Alert } from "@ui/Alert";
import { PageState } from "@ui/PageState";
import { useShortcutHint } from "@shared/hooks/useShortcutHint";
import type { GlobalSearchSuggestion } from "@app/shell/GlobalTopBar";
import { NotificationsProvider } from "@shared/notifications";

import WorkspaceOverviewRoute from "@screens/Workspace/sections/Overview";
import WorkspaceDocumentsRoute from "@screens/Workspace/sections/Documents";
import WorkspaceDocumentsV2Route from "@screens/Workspace/sections/DocumentsV2";
import WorkspaceDocumentsV3Route from "@screens/Workspace/sections/DocumentsV3";
import WorkspaceDocumentsV4Route from "@screens/Workspace/sections/DocumentsV4";
import WorkspaceDocumentsV5Route from "@screens/Workspace/sections/DocumentsV5";
import WorkspaceDocumentsV6Route from "@screens/Workspace/sections/DocumentsV6";
import WorkspaceDocumentsV7Route from "@screens/Workspace/sections/DocumentsV7";
import WorkspaceDocumentsV8Route from "@screens/Workspace/sections/DocumentsV8";
import WorkspaceDocumentsV9Route from "@screens/Workspace/sections/DocumentsV9";
import WorkspaceDocumentsV10Route from "@screens/Workspace/sections/DocumentsV10";
import DocumentDetailRoute from "@screens/Workspace/sections/Documents/components/DocumentDetail";
import WorkspaceRunsRoute from "@screens/Workspace/sections/Runs";
import WorkspaceConfigsIndexRoute from "@screens/Workspace/sections/ConfigBuilder";
import WorkspaceConfigRoute from "@screens/Workspace/sections/ConfigBuilder/detail";
import ConfigEditorWorkbenchRoute from "@screens/Workspace/sections/ConfigBuilder/workbench";
import WorkspaceSettingsRoute from "@screens/Workspace/sections/Settings";

type WorkspaceSectionRender =
  | { readonly kind: "redirect"; readonly to: string }
  | { readonly kind: "content"; readonly key: string; readonly element: ReactElement; readonly fullHeight?: boolean };

export default function WorkspaceScreen() {
  return (
    <RequireSession>
      <WorkspaceContent />
    </RequireSession>
  );
}

function WorkspaceContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces = useMemo(
    () => workspacesQuery.data?.items ?? [],
    [workspacesQuery.data?.items],
  );
  const identifier = extractWorkspaceIdentifier(location.pathname);
  const workspace = useMemo(() => findWorkspace(workspaces, identifier), [workspaces, identifier]);

  useEffect(() => {
    if (workspacesQuery.data) {
      queryClient.setQueryData(
        workspacesKeys.list(WORKSPACE_LIST_DEFAULT_PARAMS),
        workspacesQuery.data,
      );
    }
  }, [queryClient, workspacesQuery.data]);

  useEffect(() => {
    if (!workspacesQuery.isLoading && !workspacesQuery.isError && workspaces.length === 0) {
      navigate("/workspaces", { replace: true });
    }
  }, [workspacesQuery.isLoading, workspacesQuery.isError, workspaces.length, navigate]);

  useEffect(() => {
    if (workspace && !identifier) {
      navigate(`/workspaces/${workspace.id}/${defaultWorkspaceSection.path}${location.search}${location.hash}`, {
        replace: true,
      });
    }
  }, [workspace, identifier, location.search, location.hash, navigate]);

  useEffect(() => {
    if (!workspace || !identifier) {
      return;
    }

    if (identifier !== workspace.id) {
      const canonical = buildCanonicalPath(location.pathname, location.search, workspace.id, identifier);
      if (canonical !== location.pathname + location.search) {
        navigate(canonical + location.hash, { replace: true });
      }
    }
  }, [workspace, identifier, location.pathname, location.search, location.hash, navigate]);

  useEffect(() => {
    if (workspace) {
      writePreferredWorkspaceId(workspace.id);
    }
  }, [workspace]);


  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <PageState title="Loading workspace" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <PageState
          title="Unable to load workspace"
          description="We were unable to fetch workspace information. Refresh the page to try again."
          variant="error"
        />
        <button
          type="button"
          className="focus-ring rounded-lg border border-border-strong bg-card px-4 py-2 text-sm font-semibold text-muted-foreground hover:bg-muted"
          onClick={() => workspacesQuery.refetch()}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!workspace) {
    return null;
  }

  return (
    <WorkspaceProvider workspace={workspace} workspaces={workspaces}>
      <WorkspaceShell workspace={workspace} />
    </WorkspaceProvider>
  );
}

interface WorkspaceShellProps {
  readonly workspace: WorkspaceProfile;
}

function WorkspaceShell({ workspace }: WorkspaceShellProps) {
  return (
    <NotificationsProvider>
      <WorkbenchWindowProvider workspaceId={workspace.id}>
        <WorkspaceShellLayout workspace={workspace} />
      </WorkbenchWindowProvider>
    </NotificationsProvider>
  );
}

function WorkspaceShellLayout({ workspace }: WorkspaceShellProps) {
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const { session: workbenchSession, windowState } = useWorkbenchWindow();
  const safeMode = useSafeModeStatus();
  const safeModeEnabled = safeMode.data?.enabled ?? false;
  const safeModeDetail = safeMode.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;
  const shortcutHint = useShortcutHint();
  const [topBarHeight, setTopBarHeight] = useState(0);
  const topBarRef = useRef<HTMLDivElement | null>(null);
  const workspaceNavItems = useMemo(
    () => getWorkspacePrimaryNavigation(workspace),
    [workspace],
  );
  const [workspaceSearchQuery, setWorkspaceSearchQuery] = useState("");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false);
  const workspaceSearchNormalized = workspaceSearchQuery.trim().toLowerCase();
  const immersiveWorkbenchActive = Boolean(workbenchSession && windowState === "maximized");
  const workspaceSearchSuggestions = useMemo(
    () =>
      workspaceNavItems.map((item) => ({
        id: item.id,
        label: item.label,
        description: `Jump to ${item.label}`,
        icon: <item.icon className="h-4 w-4 text-muted-foreground" aria-hidden />,
      })),
    [workspaceNavItems],
  );

  const navPinnedStorage = useMemo(
    () => createScopedStorage(`ade.ui.workspace.${workspace.id}.navPinned`),
    [workspace.id],
  );
  const navCollapsedStorage = useMemo(
    () => createScopedStorage(`ade.ui.workspace.${workspace.id}.navCollapsed`),
    [workspace.id],
  );
  const [isNavPinned, setIsNavPinned] = useState(() => {
    const pinned = navPinnedStorage.get<boolean>();
    if (typeof pinned === "boolean") {
      return pinned;
    }
    const collapsed = navCollapsedStorage.get<boolean>();
    if (typeof collapsed === "boolean") {
      return !collapsed;
    }
    return false;
  });

  useEffect(() => {
    const pinned = navPinnedStorage.get<boolean>();
    if (typeof pinned === "boolean") {
      setIsNavPinned(pinned);
      return;
    }
    const collapsed = navCollapsedStorage.get<boolean>();
    if (typeof collapsed === "boolean") {
      setIsNavPinned(!collapsed);
    } else {
      setIsNavPinned(false);
    }
  }, [navPinnedStorage, navCollapsedStorage]);

  useEffect(() => {
    navPinnedStorage.set(isNavPinned);
  }, [isNavPinned, navPinnedStorage]);

  useEffect(() => {
    setWorkspaceSearchQuery("");
  }, [workspace.id]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setIsMobileNavOpen(false);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    const originalOverflow = document.body.style.overflow;
    if (isMobileNavOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = originalOverflow || "";
    }
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isMobileNavOpen]);

  useEffect(() => {
    if (immersiveWorkbenchActive) {
      setIsMobileNavOpen(false);
    }
  }, [immersiveWorkbenchActive]);

  useLayoutEffect(() => {
    if (immersiveWorkbenchActive) {
      setTopBarHeight(0);
      return;
    }
    const node = topBarRef.current;
    if (!node) return;

    const update = () => {
      const next = Math.round(node.getBoundingClientRect().height);
      setTopBarHeight((prev) => (prev === next ? prev : next));
    };

    update();

    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const observer = new ResizeObserver(() => update());
    observer.observe(node);
    return () => observer.disconnect();
  }, [immersiveWorkbenchActive]);

  const handleWorkspaceSearchSubmit = useCallback(() => {
    if (!workspaceSearchNormalized) {
      return;
    }
    const match =
      workspaceNavItems.find((item) => item.label.toLowerCase().includes(workspaceSearchNormalized)) ??
      workspaceNavItems.find((item) => item.id.toLowerCase().includes(workspaceSearchNormalized));
    if (match) {
      navigate(match.href);
    }
  }, [workspaceSearchNormalized, workspaceNavItems, navigate]);
  const handleWorkspaceSuggestionSelect = useCallback(
    (suggestion: GlobalSearchSuggestion) => {
      const match = workspaceNavItems.find((item) => item.id === suggestion.id);
      if (match) {
        navigate(match.href);
        setWorkspaceSearchQuery("");
      }
    },
    [workspaceNavItems, navigate],
  );

  const openMobileNav = useCallback(() => setIsMobileNavOpen(true), []);
  const closeMobileNav = useCallback(() => setIsMobileNavOpen(false), []);

  const workspaceSwitcherLabel = `Switch workspace: ${workspace.name}`;
  const workspaceInitials = getWorkspaceInitials(workspace.name);

  const topBarBrand = (
    <div className="flex min-w-0 items-center gap-3">
      <button
        type="button"
        onClick={openMobileNav}
        className="focus-ring inline-flex h-11 w-11 items-center justify-center rounded-xl border border-border/80 bg-card text-muted-foreground shadow-sm lg:hidden"
        aria-label="Open workspace navigation"
      >
        <MenuIcon />
      </button>
      <button
        type="button"
        onClick={() => navigate("/workspaces")}
        aria-label={workspaceSwitcherLabel}
        title={workspaceSwitcherLabel}
        className={clsx(
          "group inline-flex min-w-0 items-center gap-3 rounded-xl border border-border/80 bg-card px-3 py-2 text-left shadow-sm transition",
          "hover:border-border-strong hover:bg-background",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        )}
      >
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-xs font-semibold uppercase text-white shadow-sm transition-colors group-hover:bg-brand-600">
          {workspaceInitials}
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-semibold text-foreground">{workspace.name}</span>
          <span className="hidden text-xs text-muted-foreground sm:block">Switch workspace</span>
        </span>
        <span className="hidden text-muted-foreground sm:inline-flex" aria-hidden>
          <ChevronDownIcon />
        </span>
      </button>
    </div>
  );

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const topBarTrailing = (
    <div className="flex items-center gap-2">
      <ProfileDropdown
        displayName={displayName}
        email={email}
        actions={[
          {
            id: "about-versions",
            label: "About / Versions",
            description: "ade-web, ade-api, ade-engine",
            onSelect: () => setIsVersionsModalOpen(true),
          },
        ]}
      />
    </div>
  );
  const workspaceSearch = {
    value: workspaceSearchQuery,
    onChange: setWorkspaceSearchQuery,
    onSubmit: handleWorkspaceSearchSubmit,
    placeholder: `Search ${workspace.name} or jump to a section`,
    shortcutHint,
    scopeLabel: workspace.name,
    suggestions: workspaceSearchSuggestions,
    onSelectSuggestion: handleWorkspaceSuggestionSelect,
  };

  const segments = extractSectionSegments(location.pathname, workspace.id);
  const section = resolveWorkspaceSection(workspace.id, segments, location.search, location.hash);
  const isDocumentsSection = section?.kind === "content" && section.key.startsWith("documents");
  const isDocumentsV2 = section?.kind === "content" && section.key === "documents-v2";
  const isDocumentsV3 = section?.kind === "content" && section.key === "documents-v3";
  const isDocumentsV4 = section?.kind === "content" && section.key === "documents-v4";
  const isDocumentsV6 = section?.kind === "content" && section.key === "documents-v6";
  const isDocumentsV7 = section?.kind === "content" && section.key === "documents-v7";
  const isDocumentsV8 = section?.kind === "content" && section.key === "documents-v8";
  const isDocumentsV9 = section?.kind === "content" && section.key === "documents-v9";
  const documentSearchValue = isDocumentsSection ? new URLSearchParams(location.search).get("q") ?? "" : "";
  const handleDocumentSearchChange = useCallback(
    (nextValue: string) => {
      if (!isDocumentsSection) {
        return;
      }
      const params = new URLSearchParams(location.search);
      if (nextValue) {
        params.set("q", nextValue);
      } else {
        params.delete("q");
      }
      const searchParams = params.toString();
      navigate(
        `${location.pathname}${searchParams ? `?${searchParams}` : ""}${location.hash}`,
        { replace: true },
      );
    },
    [isDocumentsSection, location.hash, location.pathname, location.search, navigate],
  );
  const handleDocumentSearchSubmit = useCallback(
    (value: string) => {
      handleDocumentSearchChange(value);
    },
    [handleDocumentSearchChange],
  );
  const handleDocumentSearchClear = useCallback(() => {
    handleDocumentSearchChange("");
  }, [handleDocumentSearchChange]);
  const documentsSearch = isDocumentsSection
    ? {
        value: documentSearchValue,
        onChange: handleDocumentSearchChange,
        onSubmit: handleDocumentSearchSubmit,
        onClear: handleDocumentSearchClear,
        placeholder: "Search documents",
        shortcutHint,
        scopeLabel: "Documents",
        enableShortcut: true,
      }
    : undefined;
  const topBarSearch =
    isDocumentsV2 || isDocumentsV3 || isDocumentsV4 || isDocumentsV6 || isDocumentsV7 || isDocumentsV8 || isDocumentsV9
      ? undefined
      : documentsSearch ?? workspaceSearch;

  useEffect(() => {
    if (section?.kind === "redirect") {
      navigate(section.to, { replace: true });
    }
  }, [section, navigate]);

  if (!section || section.kind === "redirect") {
    return null;
  }

  const fullHeightLayout = section.fullHeight ?? false;

  return (
    <>
      <AboutVersionsModal open={isVersionsModalOpen} onClose={() => setIsVersionsModalOpen(false)} />
      <div
        className={clsx(
          "flex min-w-0 flex-col bg-background text-foreground",
          fullHeightLayout ? "h-screen overflow-hidden" : "min-h-screen",
        )}
        style={{ "--workspace-topbar-height": `${topBarHeight}px` } as CSSProperties}
      >
        {!immersiveWorkbenchActive ? (
          <div ref={topBarRef}>
            <GlobalTopBar brand={topBarBrand} trailing={topBarTrailing} search={topBarSearch} />
          </div>
        ) : null}
        <div className={clsx("relative flex min-w-0 flex-1", fullHeightLayout ? "min-h-0" : "")}>
          {!immersiveWorkbenchActive ? (
            <WorkspaceNav
              workspace={workspace}
              items={workspaceNavItems}
              isPinned={isNavPinned}
              onTogglePinned={() => setIsNavPinned((current) => !current)}
            />
          ) : null}
          <div className="flex flex-1 min-w-0 flex-col">
            {!immersiveWorkbenchActive && isMobileNavOpen ? (
              <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
                <button
                  type="button"
                  className="absolute inset-0 bg-overlay/40 backdrop-blur-sm"
                  onClick={closeMobileNav}
                  aria-label="Close navigation"
                />
                <div className="absolute inset-y-0 left-0 flex h-full w-[min(20rem,85vw)] max-w-xs flex-col rounded-r-3xl border-r border-border/70 bg-gradient-to-b from-card via-background to-card/95 shadow-[0_45px_90px_-50px_rgb(var(--color-shadow)/0.85)]">
                  <div className="flex items-center justify-between border-b border-border px-4 py-3">
                    <div className="flex flex-col leading-tight">
                      <span className="text-sm font-semibold text-foreground">{workspace.name}</span>
                      <span className="text-xs text-muted-foreground">Workspace navigation</span>
                    </div>
                    <button
                      type="button"
                      onClick={closeMobileNav}
                      className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border/80 bg-card text-muted-foreground"
                      aria-label="Close navigation"
                    >
                      <CloseIcon />
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto px-3 py-4">
                    <WorkspaceNavList items={workspaceNavItems} onNavigate={closeMobileNav} showHeading={false} />
                  </div>
                </div>
              </div>
            ) : null}
            <div className="relative flex flex-1 min-w-0 overflow-hidden" key={`section-${section.key}`}>
              <main
                id="main-content"
                tabIndex={-1}
                className={clsx(
                  "relative flex-1 min-w-0",
                  fullHeightLayout ? "flex min-h-0 flex-col overflow-hidden" : "overflow-y-auto",
                )}
              >
                <div
                  className={clsx(
                    fullHeightLayout
                      ? "flex w-full flex-1 min-h-0 flex-col px-0 py-0"
                      : "mx-auto flex w-full max-w-7xl flex-col px-4 py-6",
                  )}
                >
                  {safeModeEnabled ? (
                    <div className={clsx("mb-4", fullHeightLayout ? "px-6 pt-4" : "")}>
                      <Alert tone="warning" heading="Safe mode active">
                        {safeModeDetail}
                      </Alert>
                    </div>
                  ) : null}
                  <div
                    className={clsx(
                      fullHeightLayout ? "flex min-h-0 min-w-0 flex-1 flex-col" : "flex min-w-0 flex-1 flex-col",
                    )}
                  >
                    {section.element}
                  </div>
                </div>
              </main>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function extractWorkspaceIdentifier(pathname: string) {
  const match = pathname.match(/^\/workspaces\/([^/]+)/);
  return match?.[1] ?? null;
}

function extractSectionSegments(pathname: string, workspaceId: string) {
  const base = `/workspaces/${workspaceId}`;
  if (!pathname.startsWith(base)) {
    return [];
  }
  const remainder = pathname.slice(base.length);
  return remainder
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);
}

function findWorkspace(workspaces: WorkspaceProfile[], identifier: string | null) {
  if (!identifier) {
    return workspaces[0] ?? null;
  }
  return (
    workspaces.find((workspace) => workspace.id === identifier) ??
    workspaces.find((workspace) => workspace.slug === identifier) ??
    workspaces[0] ??
    null
  );
}

function buildCanonicalPath(pathname: string, search: string, resolvedId: string, currentId: string) {
  const base = `/workspaces/${currentId}`;
  const trailing = pathname.startsWith(base) ? pathname.slice(base.length) : "";
  const normalized = trailing && trailing !== "/" ? trailing : `/${defaultWorkspaceSection.path}`;
  return `/workspaces/${resolvedId}${normalized}${search}`;
}

function getWorkspaceInitials(name: string) {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "WS";
  const initials = parts.slice(0, 2).map((part) => part[0] ?? "");
  return initials.join("").toUpperCase();
}

function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7}>
      <path d="m6 8 4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M4 6h12" strokeLinecap="round" />
      <path d="M4 10h12" strokeLinecap="round" />
      <path d="M4 14h8" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 6l8 8" strokeLinecap="round" />
      <path d="M14 6l-8 8" strokeLinecap="round" />
    </svg>
  );
}

export function resolveWorkspaceSection(
  workspaceId: string,
  segments: string[],
  search: string,
  hash: string,
): WorkspaceSectionRender | null {
  const suffix = `${search}${hash}`;

  if (segments.length === 0) {
    return {
      kind: "redirect",
      to: `/workspaces/${workspaceId}/${defaultWorkspaceSection.path}${suffix}`,
    };
  }

  const [first, second, third] = segments;
  switch (first) {
    case "overview":
      return { kind: "content", key: "overview", element: <WorkspaceOverviewRoute /> };
    case defaultWorkspaceSection.path:
    case "documents": {
      if (!second) {
        return { kind: "content", key: "documents", element: <WorkspaceDocumentsRoute /> };
      }
      return {
        kind: "content",
        key: `documents:${second}`,
        element: <DocumentDetailRoute params={{ documentId: decodeURIComponent(second) }} />,
      };
    }
    case "documents-v4":
      return {
        kind: "content",
        key: "documents-v4",
        element: <WorkspaceDocumentsV4Route />,
        fullHeight: true,
      };
    case "documents-v2":
      return {
        kind: "content",
        key: "documents-v2",
        element: <WorkspaceDocumentsV2Route />,
        fullHeight: true,
      };
    case "documents-v3":
      return {
        kind: "content",
        key: "documents-v3",
        element: <WorkspaceDocumentsV3Route />,
        fullHeight: true,
      };
    case "documents-v5":
      return {
        kind: "content",
        key: "documents-v5",
        element: <WorkspaceDocumentsV5Route />,
        fullHeight: true,
      };
    case "documents-v6":
      return {
        kind: "content",
        key: "documents-v6",
        element: <WorkspaceDocumentsV6Route />,
        fullHeight: true,
      };
    case "documents-v7":
      return {
        kind: "content",
        key: "documents-v7",
        element: <WorkspaceDocumentsV7Route />,
        fullHeight: true,
      };
    case "documents-v8":
      return {
        kind: "content",
        key: "documents-v8",
        element: <WorkspaceDocumentsV8Route />,
        fullHeight: true,
      };
    case "documents-v9":
      return {
        kind: "content",
        key: "documents-v9",
        element: <WorkspaceDocumentsV9Route />,
        fullHeight: true,
      };
    case "documents-v10":
      return {
        kind: "content",
        key: "documents-v10",
        element: <WorkspaceDocumentsV10Route />,
        fullHeight: true,
      };
    case "runs":
      return { kind: "content", key: "runs", element: <WorkspaceRunsRoute /> };
    case "config-builder": {
      if (!second) {
        return { kind: "content", key: "config-builder", element: <WorkspaceConfigsIndexRoute /> };
      }
      if (third === "editor") {
        return {
          kind: "content",
          key: `config-builder:${second}:editor`,
          element: <ConfigEditorWorkbenchRouteWithParams configId={decodeURIComponent(second)} />,
          fullHeight: true,
        };
      }
      return {
        kind: "content",
        key: `config-builder:${second}`,
        element: <WorkspaceConfigRoute params={{ configId: decodeURIComponent(second) }} />,
      };
    }
    case "settings": {
      const remaining = segments.slice(1);
      const normalized = remaining.length > 0 ? remaining : [];
      const key = `settings:${normalized.length > 0 ? normalized.join(":") : "general"}`;
      return { kind: "content", key, element: <WorkspaceSettingsRoute sectionSegments={normalized} /> };
    }
    default:
      return {
        kind: "content",
        key: `not-found:${segments.join("/")}`,
        element: (
          <PageState
            title="Section not found"
            description="The requested workspace section could not be located."
            variant="error"
          />
        ),
      };
  }
}
function ConfigEditorWorkbenchRouteWithParams({ configId }: { readonly configId: string }) {
  return <ConfigEditorWorkbenchRoute params={{ configId }} />;
}
