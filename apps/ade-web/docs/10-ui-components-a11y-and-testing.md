# 10-ui-components-a11y-and-testing

**Purpose:** Document reusable UI components, accessibility patterns, keyboard shortcuts, and testing strategy. Also centralise state persistence key patterns.

### 1. Overview

* `src/ui` as app-specific component library.
* Target: consistent look/feel and accessible defaults.

### 2. Design tokens & theming (lightweight)

* Briefly describe:

  * Tailwind as the utility layer.
  * Any global CSS variables (spacing, typography, colours) if you have them.

* Editor theme vs overall app theme (if relevant).

### 3. Core components

Group and briefly describe patterns, not every prop:

* **Buttons**

  * `Button` variants (`primary`, `secondary`, `ghost`, `danger`), sizes, `isLoading`.
  * `SplitButton` for build control: primary action + menu.

* **Forms**

  * `Input`, `TextArea`, `Select`.

  * Error states via `invalid` and `aria-invalid`.

  * `FormField`: label, hint, error; wiring `id`/`aria-describedby`.

* **Feedback**

  * `Alert` (`info`, `success`, `warning`, `danger`).
  * When to use alert vs banner vs toast.

* **Identity**

  * `Avatar` (initials, sizes).
  * `ProfileDropdown` (actions, sign-out behaviour).

* **Navigation**

  * Tabs components (`TabsRoot`, `TabsList`, `TabsTrigger`, `TabsContent`).
  * `ContextMenu` for explorer, tabs, etc.

* **Search & top bar**

  * `GlobalSearchField`: behaviour, keyboard shortcut, suggestions.
  * `GlobalTopBar`: general usage.

* **Code editor**

  * `CodeEditor`: cross-link to 09 for advanced details.

### 4. Accessibility patterns

* **Tabs**

  * ARIA roles and keyboard navigation (`Left/Right`, `Home/End`).

* **Menus and dropdowns**

  * Focus trapping, `Esc` behaviour, arrow navigation.

* **Alerts and banners**

  * Use of `role="status"` or `role="alert"` where appropriate.

* **Forms**

  * `aria-invalid`, `aria-describedby` integration via `FormField`.

* **Modals and overlays**

  * Focus management for maximised workbench and dialogs.

### 5. Keyboard shortcuts

* **Global**

  * `⌘K` / `Ctrl+K`: open search.
  * `⌘U` / `Ctrl+U`: document upload (where enabled).

* **Workbench**

  * `⌘S` / `Ctrl+S`: save active editor file.
  * `⌘B` / `Ctrl+B`: build/reuse environment.
  * `⇧⌘B` / `Ctrl+Shift+B`: force rebuild.
  * `⌘W` / `Ctrl+W`: close active tab.
  * `⌘Tab` / `Ctrl+Tab`: recent-tab forward.
  * `⇧⌘Tab` / `Shift+Ctrl+Tab`: backward.
  * `Ctrl+PageUp/PageDown`: cycle by visual tab order.

* Scope rules:

  * Shortcuts only active when relevant area is focused.
  * Avoid overriding browser basics on generic inputs.

### 6. Notifications

* **Toasts**

  * Transient success/warning messages (saves, small errors).

* **Banners**

  * Cross-section warnings: safe mode, connectivity issues.
  * How they are composed from `Alert` + higher-level plumbing.

### 7. State persistence & user preferences (central summary)

* Prefix convention:

  * `ade.ui.workspace.<workspaceId>...`.

* Key patterns:

  * `...nav.collapsed`
  * `...workbench.returnPath`
  * `...config.<configId>.tabs`
  * `...config.<configId>.console`
  * `...config.<configId>.editor-theme`
  * `...document.<documentId>.run-preferences`

* Rules:

  * Preferences are per-user, per-workspace.
  * Data stored is non-sensitive and safe to clear.
  * Clearing localStorage should not corrupt server state.

* Cross-links:

  * Back to docs 07 and 09 where each preference is introduced in context.

### 8. Dev & testing workflow

* **Vite dev server**

  * Host/port env vars.
  * `/api` proxy behaviour.

* **Vitest configuration**

  * JSDOM environment.
  * `setup.ts` for mocks/polyfills.
  * Coverage via v8.

* **Testing strategy**

  * Utils in `shared/`: unit tests.
  * UI components in `ui/`: component tests.
  * Feature flows in `features/`: integration tests (navigation, streams, RBAC behaviours).
