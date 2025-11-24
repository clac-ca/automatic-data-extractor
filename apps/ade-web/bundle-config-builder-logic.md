# Logical module layout (source -> sections below):
# - apps/ade-web/README.md - ADE Web
# - apps/ade-web/src/app/App.tsx
# - apps/ade-web/src/app/AppProviders.tsx
# - apps/ade-web/src/app/nav/Link.tsx
# - apps/ade-web/src/app/nav/history.tsx
# - apps/ade-web/src/app/nav/urlState.ts
# - apps/ade-web/src/main.tsx
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/defaultConfig.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/seed/stubWorkbenchData.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useEditorThemePreference.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useUnsavedChangesGuard.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchFiles.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/useWorkbenchUrlState.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/types.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/drag.ts
# - apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/tree.ts
# - apps/ade-web/vite.config.ts
# - apps/ade-web/vitest.config.ts

# apps/ade-web/README.md
```markdown
# ADE Web

ADE Web is the browser-based front-end for the Automatic Data Extractor (ADE) platform.

It gives two main personas a single place to work:

- **Workspace owners / engineers** – create and evolve config packages (Python packages) that define how documents are processed, manage safe mode, and administer membership and SSO.
- **End users / analysts** – upload documents, kick off extractions, monitor progress, inspect logs, and download structured outputs.

This document focuses on **what** the ADE Web application does and the concepts it exposes, not on the current backend wiring. Treat it as the product-level description for how the UI should behave in an ideal implementation.

---

## Core concepts

### Workspace

A **workspace** is the primary unit of organisation in ADE:

- Isolates **documents**, **runs**, **config packages**, and **access control**.
- Has a **name** and stable **slug/ID** that appear in the UI and URLs.
- Has exactly one **active config package version** at any point in time.
- Is governed by **workspace-level safe mode** and **role-based access control (RBAC)**.

Users sign in, then select a workspace to begin working.

---

### Documents

A **document** is any input you feed into ADE (for example, a spreadsheet, CSV export, or other supported file type) that you want to extract structured data from.

Per workspace:

- Documents are **uploaded** and owned by that workspace.
- Each document has:
  - A **name** (usually the filename),
  - **Type** (e.g., Excel, CSV),
  - Optional **tags** (e.g., client name, reporting period),
  - A history of **runs** associated with it.
- Documents are **immutable inputs**; runs refer back to the original upload. If you upload a new version, it becomes a new document.

---

### Runs (jobs)

A **run** is a single execution of ADE against a document using a particular config package version.

Conceptually:

- Runs are always **scoped to a document** and **belong to a workspace**.
- Each run tracks:
  - **Status** (queued → running → succeeded / failed / cancelled),
  - **Timestamps** (created / started / completed),
  - **Who** triggered it,
  - The **config version** used,
  - Links to **structured output artifacts** (CSV/JSON/other),
  - **Telemetry and logs** (streamed as NDJSON events from the backend).
- Runs are visible:
  - Inline on the **Documents** screen (per-document focus),
  - On the **Jobs** screen (workspace-wide view and auditing).

In the ideal backend, ADE exposes runs via a **streaming API** (NDJSON), and the UI subscribes to updates so progress and logs appear in real time.

---

### Config packages & config versions

A **config package** is a Python package that defines how ADE should interpret, validate, and extract data from documents for a given workspace.

Conceptually:

- Each workspace has one **config package** (a directory tree of Python modules and configuration files).
- The package is versioned into **config versions**, each of which is immutable once activated.
- A config version has a **status**:
  - **Draft**
    - The default state when a version is created or cloned.
    - Fully editable in the Config Builder (files, metadata, etc.).
    - Can be validated and used for **test runs**.
    - Not used for standard end-user runs until activated.
  - **Active**
    - Exactly **one active config version per workspace**.
    - Read-only in the UI (to ensure reproducibility).
    - Used for all new regular document runs in that workspace.
  - **Inactive**
    - Previously active versions.
    - Remain visible for **history, audits, and rollback**.

#### Version lifecycle (ideal behaviour)

- Start with a **Draft**:
  - Create a new draft version from scratch or by cloning an existing version.
  - Edit code and configuration freely.
  - Run **builds, validations, and test runs** against sample documents.
- When ready, **Activate**:
  - Marks the draft as the **single Active** version for its workspace.
  - Automatically moves the previously active version (if any) to **Inactive**.
  - New document runs use this active version.
- To **evolve** behaviour:
  - Clone the active (or an older inactive) version into a **new Draft**.
  - Make changes, validate, and activate.
- To **rollback**:
  - Identify the previously working inactive version.
  - Clone it into a new draft, optionally make adjustments.
  - Activate the new draft; the current active version becomes inactive.

This lifecycle gives you a clear, audit-friendly history while enforcing a single source of truth per workspace.

---

### Safe mode

ADE includes a **safe mode** mechanism that acts as a kill switch for write/execution operations:

- When **safe mode is enabled**, new runs and build/test executions are disabled, while read-only operations (viewing documents, logs, outputs) continue to work.
- Safe mode is controlled by:
  - **System-level** status (set by platform operators),
  - Optional **workspace-level overrides** (for workspace owners), where allowed.
- The UI surfaces safe mode in multiple places:
  - A **banner** or status strip so it’s always visible when enabled,
  - Disabled actions (Run, Build, Test Run) with explanatory tooltips,
  - Controls in **Workspace Settings** (for authorised roles).

---

### Roles & permissions

ADE Web is designed around workspace-level RBAC:

- Users are assigned roles in each workspace (for example: Owner, Maintainer, Member/Runner, Viewer).
- Roles control what the UI enables:
  - Who can toggle **safe mode**,
  - Who can edit and activate **config versions**,
  - Who can **invite** members and change roles,
  - Who can run **builds/test runs** and **document runs**,
  - Who has **read-only** access.

The UI assumes the backend enforces these permissions; the front-end mirrors them by disabling or hiding actions accordingly.

---

### Authentication & SSO

Authentication is handled centrally by ADE’s API:

- Supports:
  - Standard login (for local or simple deployments).
  - **Single Sign-On (SSO)** via an identity provider (e.g., Azure AD, Okta) when configured.
- ADE Web:
  - Redirects unauthenticated users to the login/SSO entry point.
  - Handles the **auth callback** and stores the session.
  - Reads the current user’s profile and accessible workspaces.
- For local development, ADE can be configured to **bypass authentication** (e.g., via environment flags) to speed up frontend and workflow development.

---

## Application overview

At a high level, ADE Web is structured as:

1. **Sign-in & workspace selection**
   - User signs in (directly or via SSO).
   - They see a list of workspaces they belong to and choose one.

2. **Workspace shell**
   - Once inside a workspace, they see a full-screen layout with:
     - **Top area**: workspace name, environment, optional system status banners and safe mode alerts.
     - **Sidebar navigation**: links to the key sections:
       - Overview (optional, high-level workspace summary),
       - **Documents**,
       - **Jobs**,
       - **Config Builder**,
       - **Settings**.

3. **Section content**
   - The main content area changes based on the current section, but always uses a consistent design language (spacing, typography, and components) to keep the experience coherent.

---

## Documents section

The **Documents** section is where end users spend most of their time.

### Document list

- Shows a **paginated, filterable table** of all documents in the workspace.
- Example columns:
  - Name / filename,
  - Type (e.g., XLSX, CSV),
  - Tags or categories,
  - Last run status and timestamp,
  - Who last ran it.
- Filtering and search:
  - By **text** (name),
  - By **type** or **tags**,
  - By last run status or timeframe (ideal behaviour).

### Uploading documents

- The UI provides an **“Upload”** action (button and/or drag-and-drop area).
- Users can:
  - Upload one or more new files.
  - See upload progress and any validation errors (unsupported file type, size limits, etc.).
- Once an upload completes, the new document appears in the table and is ready to be run.

### Document details panel

Selecting a document opens a **details panel** (often in a side pane):

- Shows document metadata:
  - Name, type, size, uploaded by, uploaded at.
- Shows **tags** and other editable metadata (where permitted).
- Shows the **most recent run**:
  - Status, duration,
  - Which config version was used,
  - Quick links to output artifacts.
- Includes primary actions:
  - **Run** – start a new extraction run,
  - **View runs** – open the full run history drawer.

When safe mode is enabled, the **Run** button is disabled and explains why.

### Running a document

When the user starts a run:

- The UI asks for required parameters:
  - Which **config version** to use (defaults to active),
  - Any specific options (worksheet selection, scenario, etc., depending on backend capabilities).
- The run transitions to **queued**, then **running**:
  - Status updates are streamed from the backend.
  - The document’s row and details panel reflect live progress.

### Document Runs Drawer

The **Document Runs Drawer** is a per-document run history:

- Opens from the document details (“View runs” or similar).
- Shows a list of runs for that document, newest first.
- For each run:
  - Status, timestamps, user, config version.
- The drawer:
  - Defaults to the **latest run** so users immediately see the most relevant results.
  - Shows:
    - **Logs/console output**, streamed from the backend,
    - **Telemetry** (e.g., row counts, warnings, errors),
    - Links to **artifacts/output files** for download.

This drawer turns ADE Web into an end-to-end console for that document: you can start a job, watch it finish, inspect issues, and download results without leaving the screen.

---

## Jobs section

The **Jobs** section provides a workspace-wide view of all runs (jobs), regardless of which document they came from.

### Jobs list

- Presents a **chronological table** of runs:
  - Run/job identifier,
  - Document,
  - Status,
  - Started / completed times,
  - Duration,
  - Triggered by,
  - Config version used.
- Supports filtering by:
  - Status (running, succeeded, failed),
  - Date/time window,
  - Document or config version,
  - User.

This view is designed for **operators and advanced users** who need to monitor the whole workspace, not just one document at a time.

### Job details & logs

Selecting a job:

- Opens a detailed view or drawer:
  - The same **streamed logs** the engine produces (via NDJSON event stream),
  - Structured telemetry (counters, timings, warnings),
  - Output artifacts and result downloads.
- Helps with:
  - Debugging failures,
  - Auditing who ran what and when,
  - Generating evidence for incident reports.

The Jobs section may also offer **CSV export** or similar so operations teams can slice and analyse job histories outside ADE.

---

## Config Builder

The **Config Builder** is a first-class part of ADE Web. It is designed to feel like a slim, browser-based **VS Code** experience focused on config packages.

### Goals

- Make it obvious that a **config package is just a Python package**.
- Let workspace owners modify config packages with minimal context switching from their usual IDE.
- Provide an integrated environment to:
  - Edit code and configuration,
  - Run builds/validations,
  - Kick off test runs,
  - Watch logs and telemetry inline.

### Layout: VS Code–inspired workbench

The Config Builder uses a multi-panel workbench:

1. **Explorer (left)**
   - Shows the config package as a **filesystem-like tree**:
     - Python modules (`__init__.py`, `models.py`, etc.),
     - Configuration files (YAML/JSON),
     - Supporting assets.
   - Supports:
     - Creating, renaming, and deleting files and folders (for drafts),
     - Switching between config versions.

2. **Editor (center)**
   - A code editor that behaves like a modern IDE:
     - Multiple open tabs,
     - Keyboard shortcuts for navigation and save,
     - Syntax highlighting and sensible defaults for Python and config formats.
   - Editing is allowed only for **draft** versions.
   - Tabs are persisted so that refreshing the page does not lose the current editing context.

3. **Inspector (right)**
   - Shows metadata about the selected config version:
     - Name, version identifier,
     - Status (draft/active/inactive),
     - Created / activated timestamps,
     - Who created/activated it.
   - Includes actions:
     - **Activate** (when viewing a draft),
     - **Clone** (when viewing active or inactive versions),
     - **Delete** (where allowed).

4. **Console / Terminal (bottom)**
   - A terminal-like panel that receives **streamed events** from the backend:
     - Build and validation logs,
     - Test-run output,
     - Errors and warnings.
   - Feels like a VS Code integrated terminal:
     -Separate tabs (e.g., “Build”, “Test run”, possibly a raw “Terminal”-style log).
     - Messages appear incrementally as ADE streams NDJSON events.

### Working with config versions

From the Config Builder, workspace owners can:

- **Create drafts**
  - “New config version” (empty or from template),
  - “Clone from current active” or from an older inactive version (for regression or rollback tweaks).

- **Edit drafts**
  - Modify Python modules, config files, and metadata.
  - Perform refactorings just as they would in a local IDE.

- **Validate and test**
  - Trigger **builds/validations**:
    - The console shows streaming output (success, tracebacks, validation errors).
  - Trigger **test runs** against sample documents:
    - Use the same run plumbing as the main Documents tab.
    - Provide a quick loop: edit → test → adjust → test again.

- **Activate**
  - When a draft is ready, owners activate it:
    - The draft becomes the new **Active** version.
    - The previous active becomes **Inactive**.
  - The rest of ADE Web (Documents and Jobs) automatically routes new runs through this active version.

This creates a tight, IDE-like workflow inside the browser, so workspace owners can stay within ADE Web for most of their config work.

---

## Workspace Settings

The **Settings** section is where workspace owners and admins configure and operate the workspace.

Typical subsections:

### General settings

- Workspace name and slug.
- Environment indicators (e.g., production vs test).
- Read-only IDs useful for automation or API clients.

### Authentication & SSO (workspace-facing)

While the core SSO setup lives on the backend/admin side, the workspace settings may surface:

- Which identity provider is used (when relevant),
- SSO connection status indicators,
- Helpful links or information (e.g., “Use your corporate SSO to sign in”).

### Safe mode controls

For authorised roles, workspace settings provide:

- **Safe mode toggles**:
  - View current system-wide safe mode state.
  - Optionally override or confirm workspace-level safe mode.
- Clear messaging about the impact:
  - When enabled: new runs, builds, and test runs are blocked across the workspace.
  - Existing jobs continue to be visible but not restartable.

### Members & roles

An admin-focused subsection to manage workspace membership:

- List of members:
  - Name, email, role, last activity.
- Actions:
  - **Invite** user by email (sends an invite, which on acceptance grants access).
  - **Change role** for existing members.
  - **Remove** user from the workspace.
- Visual cues to clarify what each role can do (e.g., who can toggle safe mode, who can edit configs, who can only view).

---

## Typical user journeys

### 1. Analyst running an extraction

1. Sign in (via SSO or standard login).
2. Select the appropriate workspace.
3. Go to **Documents**.
4. Upload a new spreadsheet or select an existing one.
5. Click **Run**, confirm options (if any), and start the run.
6. Watch progress in the **Document Runs Drawer**:
   - Observe logs and telemetry.
   - Wait for status to reach “Succeeded” or investigate on “Failed”.
7. Download output artifacts (e.g., CSV/JSON) from the drawer.

### 2. Workspace owner rolling out a config change

1. Sign in and open the workspace.
2. Go to **Config Builder**.
3. Clone the current active config into a **new Draft** version.
4. Edit Python modules and config files in the **editor**.
5. Run **builds/validations** and **test runs** from the integrated console until everything passes.
6. Activate the draft:
   - It becomes the only **Active** config version.
   - The previous active moves to **Inactive**.
7. Optionally inform end users that they can now rerun documents, or watch new runs in **Jobs**.

### 3. Responding to an incident / doing a rollback

1. Notice repeated failures or issues in the **Jobs** view.
2. Use **Jobs** and **Document Runs** to inspect logs and confirm that the problem is caused by a recent config change.
3. Go to **Config Builder**, identify a previous working **Inactive** version.
4. Clone it into a **new Draft**, optionally apply a minimal fix.
5. Validate and run tests.
6. Activate this fixed draft to restore a working configuration.
7. Optionally use **safe mode** to temporarily block new runs while the investigation is ongoing.

---

## Backend expectations (high-level)

While this README is intentionally backend-agnostic, ADE Web assumes that the backend provides:

- HTTP APIs for:
  - Authentication and user identity,
  - Workspace listing and membership,
  - Document upload, listing, and metadata,
  - Run/job creation, querying, and artifact download,
  - Config package/version management (draft/active/inactive),
  - Safe mode status and toggles.
- **Streaming endpoints** (e.g., NDJSON) for:
  - Run/job logs and telemetry,
  - Build/validation/test-run logs from Config Builder.
- Strict enforcement of **roles and permissions** that the front-end can reflect in its UI.

When the backend is reimplemented, keeping these conceptual contracts intact will let ADE Web continue to behave as described here.
```

# apps/ade-web/src/app/App.tsx
```tsx
import { NavProvider, useLocation } from "@app/nav/history";

import { AppProviders } from "./AppProviders";
import HomeScreen from "@screens/Home";
import LoginScreen from "@screens/Login";
import AuthCallbackScreen from "@screens/AuthCallback";
import SetupScreen from "@screens/Setup";
import WorkspacesScreen from "@screens/Workspaces";
import WorkspaceCreateScreen from "@screens/Workspaces/New";
import WorkspaceScreen from "@screens/Workspace";
import LogoutScreen from "@screens/Logout";
import NotFoundScreen from "@screens/NotFound";

export function App() {
  return (
    <NavProvider>
      <AppProviders>
        <ScreenSwitch />
      </AppProviders>
    </NavProvider>
  );
}

export function ScreenSwitch() {
  const location = useLocation();
  const normalized = normalizePathname(location.pathname);
  const segments = normalized.split("/").filter(Boolean);

  if (segments.length === 0) {
    return <HomeScreen />;
  }

  const [first, second] = segments;

  switch (first) {
    case "login":
      return <LoginScreen />;
    case "logout":
      return <LogoutScreen />;
    case "auth":
      if (second === "callback") {
        return <AuthCallbackScreen />;
      }
      break;
    case "setup":
      return <SetupScreen />;
    case "workspaces":
      if (!second) {
        return <WorkspacesScreen />;
      }
      if (second === "new") {
        return <WorkspaceCreateScreen />;
      }
      return <WorkspaceScreen />;
    default:
      break;
  }

  return <NotFoundScreen />;
}

export function normalizePathname(pathname: string) {
  if (!pathname || pathname === "/") {
    return "/";
  }
  return pathname.endsWith("/") && pathname.length > 1 ? pathname.slice(0, -1) : pathname;
}

export default App;
```

# apps/ade-web/src/app/AppProviders.tsx
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import type { ReactNode } from "react";
import { useState } from "react";

interface AppProvidersProps {
  readonly children: ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV ? (
        <ReactQueryDevtools initialIsOpen={false} />
      ) : null}
    </QueryClientProvider>
  );
}
```

# apps/ade-web/src/app/nav/Link.tsx
```tsx
import React from "react";
import { useNavigate, useLocation } from "./history";

type LinkProps = React.PropsWithChildren<{
  to: string;
  replace?: boolean;
  className?: string;
  title?: string;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
}>;

export function Link({ to, replace, className, title, children, onClick }: LinkProps) {
  const navigate = useNavigate();
  return (
    <a
      href={to}
      className={className}
      title={title}
      onClick={(event) => {
        onClick?.(event);
        if (
          event.defaultPrevented ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        navigate(to, { replace });
      }}
    >
      {children}
    </a>
  );
}

type NavLinkRenderArgs = { isActive: boolean };
type NavLinkClassName = string | ((args: NavLinkRenderArgs) => string);
type Renderable = React.ReactNode | ((args: NavLinkRenderArgs) => React.ReactNode);
type NavLinkProps = {
  to: string;
  end?: boolean;
  className?: NavLinkClassName;
  title?: string;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
  children: Renderable;
};

export function NavLink({ to, end, className, children, title, onClick }: NavLinkProps) {
  const { pathname } = useLocation();
  const isActive = end
    ? pathname === to
    : pathname === to || pathname.startsWith(`${to}/`);
  const computedClassName =
    typeof className === "function" ? className({ isActive }) : className;
  const renderedChildren =
    typeof children === "function" ? children({ isActive }) : children;

  return (
    <Link to={to} className={computedClassName} title={title} onClick={onClick}>
      {renderedChildren}
    </Link>
  );
}
```

# apps/ade-web/src/app/nav/history.tsx
```tsx
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export type LocationLike = { pathname: string; search: string; hash: string };
type NavigateOptions = { replace?: boolean };

export type NavigationIntent = {
  readonly to: string;
  readonly location: LocationLike;
  readonly kind: "push" | "replace" | "pop";
};

export type NavigationBlocker = (intent: NavigationIntent) => boolean;

type NavContextValue = {
  location: LocationLike;
  navigate: (to: string, opts?: NavigateOptions) => void;
  registerBlocker: (blocker: NavigationBlocker) => () => void;
};

const NavCtx = createContext<NavContextValue | null>(null);

export function NavProvider({ children }: { children: React.ReactNode }) {
  const [loc, setLoc] = useState<LocationLike>(() => ({
    pathname: window.location.pathname,
    search: window.location.search,
    hash: window.location.hash,
  }));
  const blockersRef = useRef(new Set<NavigationBlocker>());
  const latestLocationRef = useRef<LocationLike>(loc);

  useEffect(() => {
    latestLocationRef.current = loc;
  }, [loc]);

  const runBlockers = useCallback(
    (intent: NavigationIntent) => {
      for (const blocker of blockersRef.current) {
        if (blocker(intent) === false) {
          return false;
        }
      }
      return true;
    },
    [],
  );

  useEffect(() => {
    const onPop = () => {
      const nextLocation: LocationLike = {
        pathname: window.location.pathname,
        search: window.location.search,
        hash: window.location.hash,
      };
      const target = `${nextLocation.pathname}${nextLocation.search}${nextLocation.hash}`;
      const allowed = runBlockers({ kind: "pop", to: target, location: nextLocation });
      if (!allowed) {
        const current = latestLocationRef.current;
        window.history.pushState(null, "", `${current.pathname}${current.search}${current.hash}`);
        return;
      }
      setLoc(nextLocation);
    };

    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [runBlockers]);

  const registerBlocker = useCallback((blocker: NavigationBlocker) => {
    blockersRef.current.add(blocker);
    return () => {
      blockersRef.current.delete(blocker);
    };
  }, []);

  const navigate = useCallback(
    (to: string, opts?: NavigateOptions) => {
      const url = new URL(to, window.location.origin);
      const nextLocation: LocationLike = {
        pathname: url.pathname,
        search: url.search,
        hash: url.hash,
      };
      const target = `${nextLocation.pathname}${nextLocation.search}${nextLocation.hash}`;
      const kind: NavigationIntent["kind"] = opts?.replace ? "replace" : "push";
      const allowed = runBlockers({ kind, to: target, location: nextLocation });
      if (!allowed) {
        return;
      }
      if (opts?.replace) {
        window.history.replaceState(null, "", target);
      } else {
        window.history.pushState(null, "", target);
      }
      window.dispatchEvent(new PopStateEvent("popstate"));
    },
    [runBlockers],
  );

  const value = useMemo(
    () => ({
      location: loc,
      navigate,
      registerBlocker,
    }),
    [loc, navigate, registerBlocker],
  );

  return <NavCtx.Provider value={value}>{children}</NavCtx.Provider>;
}

export function useLocation() {
  const ctx = useContext(NavCtx);
  if (!ctx) {
    throw new Error("useLocation must be used within NavProvider");
  }
  return ctx.location;
}

export function useNavigate() {
  const ctx = useContext(NavCtx);
  if (!ctx) {
    throw new Error("useNavigate must be used within NavProvider");
  }
  return ctx.navigate;
}

export function useNavigationBlocker(blocker: NavigationBlocker, when = true) {
  const ctx = useContext(NavCtx);
  if (!ctx) {
    throw new Error("useNavigationBlocker must be used within NavProvider");
  }

  useEffect(() => {
    if (!when) {
      return;
    }
    return ctx.registerBlocker(blocker);
  }, [blocker, ctx, when]);
}
```

# apps/ade-web/src/app/nav/urlState.ts
```typescript
import { createContext, createElement, useCallback, useContext, useMemo, type ReactNode } from "react";

import { useLocation, useNavigate } from "./history";

type SearchParamPrimitive = string | number | boolean;
type SearchParamsRecordValue =
  | SearchParamPrimitive
  | readonly SearchParamPrimitive[]
  | null
  | undefined;
type SearchParamsRecord = Record<string, SearchParamsRecordValue>;

export type SearchParamsInit =
  | string
  | string[][]
  | URLSearchParams
  | SearchParamsRecord;

export function toURLSearchParams(init: SearchParamsInit): URLSearchParams {
  if (init instanceof URLSearchParams) {
    return new URLSearchParams(init);
  }

  if (typeof init === "string" || Array.isArray(init)) {
    return new URLSearchParams(init as string | string[][]);
  }

  const params = new URLSearchParams();

  for (const [key, rawValue] of Object.entries(init)) {
    if (rawValue == null) {
      continue;
    }

    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    for (const value of values) {
      if (value == null) {
        continue;
      }
      params.append(key, String(value));
    }
  }

  return params;
}

export function getParam(search: string, key: string) {
  return new URLSearchParams(search).get(key) ?? undefined;
}

type ParamPatchValue = string | number | boolean | null | undefined;

export function setParams(url: URL, patch: Record<string, ParamPatchValue>) {
  const next = new URL(url.toString());
  const query = new URLSearchParams(next.search);

  for (const [paramKey, value] of Object.entries(patch)) {
    if (value == null || value === "") {
      query.delete(paramKey);
    } else {
      query.set(paramKey, String(value));
    }
  }

  next.search = query.toString() ? `?${query}` : "";
  return `${next.pathname}${next.search}${next.hash}`;
}

export type SetSearchParamsInit = SearchParamsInit | ((prev: URLSearchParams) => SearchParamsInit);
export type SetSearchParamsOptions = { replace?: boolean };

interface SearchParamsOverrideValue {
  readonly params: URLSearchParams;
  readonly setSearchParams: (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => void;
}

const SearchParamsOverrideContext = createContext<SearchParamsOverrideValue | null>(null);

export function SearchParamsOverrideProvider({
  value,
  children,
}: {
  readonly value: SearchParamsOverrideValue | null;
  readonly children: ReactNode;
}) {
  return createElement(SearchParamsOverrideContext.Provider, { value }, children);
}

export function useSearchParams(): [URLSearchParams, (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => void] {
  const override = useContext(SearchParamsOverrideContext);
  const location = useLocation();
  const navigate = useNavigate();

  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);

  const setSearchParams = useCallback(
    (init: SetSearchParamsInit, options?: SetSearchParamsOptions) => {
      const nextInit = typeof init === "function" ? init(new URLSearchParams(params)) : init;
      const next = toURLSearchParams(nextInit);
      const search = next.toString();
      const target = `${location.pathname}${search ? `?${search}` : ""}${location.hash}`;
      navigate(target, { replace: options?.replace });
    },
    [location.hash, location.pathname, navigate, params],
  );

  return [override?.params ?? params, override?.setSearchParams ?? setSearchParams];
}

export type ConfigBuilderTab = "editor";
export type ConfigBuilderPane = "console" | "validation";
export type ConfigBuilderConsole = "open" | "closed";
export type ConfigBuilderView = "editor" | "split" | "zen";

export interface ConfigBuilderSearchState {
  readonly tab: ConfigBuilderTab;
  readonly pane: ConfigBuilderPane;
  readonly console: ConfigBuilderConsole;
  readonly view: ConfigBuilderView;
  readonly file?: string;
}

export interface ConfigBuilderSearchSnapshot extends ConfigBuilderSearchState {
  readonly present: {
    readonly tab: boolean;
    readonly pane: boolean;
    readonly console: boolean;
    readonly view: boolean;
    readonly file: boolean;
  };
}

export const DEFAULT_CONFIG_BUILDER_SEARCH: ConfigBuilderSearchState = {
  tab: "editor",
  pane: "console",
  console: "closed",
  view: "editor",
};

const CONFIG_BUILDER_KEYS = ["tab", "pane", "console", "view", "file", "path"] as const;

function normalizeConsole(value: string | null): ConfigBuilderConsole {
  return value === "open" ? "open" : "closed";
}

function normalizePane(value: string | null): ConfigBuilderPane {
  if (value === "validation" || value === "problems") {
    return "validation";
  }
  return "console";
}

function normalizeView(value: string | null): ConfigBuilderView {
  return value === "split" || value === "zen" ? value : "editor";
}

export function readConfigBuilderSearch(
  source: URLSearchParams | string,
): ConfigBuilderSearchSnapshot {
  const params = source instanceof URLSearchParams ? source : new URLSearchParams(source);
  const tabRaw = params.get("tab");
  const paneRaw = params.get("pane");
  const consoleRaw = params.get("console");
  const viewRaw = params.get("view");
  const fileRaw = params.get("file") ?? params.get("path");

  const state: ConfigBuilderSearchState = {
    tab: tabRaw === "editor" ? "editor" : DEFAULT_CONFIG_BUILDER_SEARCH.tab,
    pane: normalizePane(paneRaw),
    console: normalizeConsole(consoleRaw),
    view: normalizeView(viewRaw),
    file: fileRaw ?? undefined,
  };

  return {
    ...state,
    present: {
      tab: params.has("tab"),
      pane: params.has("pane"),
      console: params.has("console"),
      view: params.has("view"),
      file: params.has("file") || params.has("path"),
    },
  };
}

export function mergeConfigBuilderSearch(
  current: URLSearchParams,
  patch: Partial<ConfigBuilderSearchState>,
): URLSearchParams {
  const existing = readConfigBuilderSearch(current);
  const nextState: ConfigBuilderSearchState = {
    ...DEFAULT_CONFIG_BUILDER_SEARCH,
    ...existing,
    ...patch,
  };

  const next = new URLSearchParams(current);
  for (const key of CONFIG_BUILDER_KEYS) {
    next.delete(key);
  }

  if (nextState.tab !== DEFAULT_CONFIG_BUILDER_SEARCH.tab) {
    next.set("tab", nextState.tab);
  }
  if (nextState.pane !== DEFAULT_CONFIG_BUILDER_SEARCH.pane) {
    next.set("pane", nextState.pane);
  }
  if (nextState.console !== DEFAULT_CONFIG_BUILDER_SEARCH.console) {
    next.set("console", nextState.console);
  }
  if (nextState.view !== DEFAULT_CONFIG_BUILDER_SEARCH.view) {
    next.set("view", nextState.view);
  }
  if (nextState.file && nextState.file.length > 0) {
    next.set("file", nextState.file);
  }

  return next;
}
```

# apps/ade-web/src/main.tsx
```tsx
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "@app/App";
import "@app/app.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
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

# apps/ade-web/vite.config.ts
```typescript
import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";
import react from "@vitejs/plugin-react";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));
const resolveSrc = (relativePath: string) => path.resolve(projectRoot, "src", relativePath);

const frontendPort = Number.parseInt(process.env.DEV_FRONTEND_PORT ?? "8000", 10);
const backendPort = process.env.DEV_BACKEND_PORT ?? "8000";

export default defineConfig({
  plugins: [tailwindcss(), react(), tsconfigPaths()],
  resolve: {
    alias: {
      "@app": resolveSrc("app"),
      "@screens": resolveSrc("screens"),
      "@ui": resolveSrc("ui"),
      "@shared": resolveSrc("shared"),
      "@schema": resolveSrc("schema"),
      "@generated-types": resolveSrc("generated-types"),
      "@test": resolveSrc("test"),
    },
  },
  server: {
    port: Number.isNaN(frontendPort) ? 8000 : frontendPort,
    host: process.env.DEV_FRONTEND_HOST ?? "0.0.0.0",
    proxy: {
      "/api": {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
});
```

# apps/ade-web/vitest.config.ts
```typescript
import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@app": fileURLToPath(new URL("./src/app", import.meta.url)),
      "@screens": fileURLToPath(new URL("./src/screens", import.meta.url)),
      "@shared": fileURLToPath(new URL("./src/shared", import.meta.url)),
      "@ui": fileURLToPath(new URL("./src/ui", import.meta.url)),
      "@schema": fileURLToPath(new URL("./src/schema", import.meta.url)),
      "@generated-types": fileURLToPath(new URL("./src/generated-types", import.meta.url)),
      "@test": fileURLToPath(new URL("./src/test", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    coverage: {
      provider: "v8",
    },
  },
  esbuild: {
    jsx: "automatic",
  },
});
```
