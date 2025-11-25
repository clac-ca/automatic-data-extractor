# 10. UI components, accessibility, and testing

This document describes the UI component layer in `ade-web`: what lives in `src/ui`, how components are designed, the accessibility and keyboard conventions they follow, how user preferences are persisted, and how we test UI behaviour.

It assumes you’ve read:

* [`01-domain-model-and-naming.md`](./01-domain-model-and-naming.md) for terminology (e.g. *run*, *document*, *workspace*).
* [`06-workspace-layout-and-sections.md`](./06-workspace-layout-and-sections.md) for the high‑level layout.

---

## 1. Scope of the UI layer

All reusable UI components live in `src/ui`. The layer has a narrow, intentional scope:

* **Responsibilities**

  * Provide **presentational primitives** (buttons, form controls, alerts, layout scaffolding).
  * Provide **composite widgets** that are UI‑heavy but domain‑agnostic (tabs, context menus, top bar, search field, code editor wrapper).
  * Encode **accessibility and keyboard patterns** so features don’t have to re‑implement them.
  * Offer **stable, predictable APIs** for feature code to compose.

* **Non‑responsibilities**

  * No HTTP or React Query calls.
  * No knowledge of ADE concepts (no runs/documents/workspaces inside `src/ui`).
  * No permission checks or business rules.
  * No direct `localStorage` or routing logic.

If a component needs to know *which* run to start, *who* the user is, or *whether* an action is allowed, that logic belongs in `src/features`, not `src/ui`.

---

## 2. Structure of `src/ui`

The UI library is organised by function, not by domain:

```text
src/ui/
  button/
    Button.tsx
    SplitButton.tsx
  form/
    Input.tsx
    TextArea.tsx
    Select.tsx
    FormField.tsx
  feedback/
    Alert.tsx
  identity/
    Avatar.tsx
    ProfileDropdown.tsx
  navigation/
    TabsRoot.tsx
    TabsList.tsx
    TabsTrigger.tsx
    TabsContent.tsx
    ContextMenu.tsx
  shell/
    GlobalTopBar.tsx
    GlobalSearchField.tsx
  code-editor/
    CodeEditor.tsx
  ...
```

Conventions:

* One **main component per file** (e.g. `Button.tsx` exports `Button`).
* Optional small helper components may live next to the main one if they are tightly coupled.
* Barrels (`index.ts`) are allowed but not required; they should not hide important component names.

### 2.1 Design constraints

All `src/ui` components follow a few design rules:

* **Presentational**
  They receive data and callbacks via props; they don’t fetch or derive it from global state.

* **Minimal internal state**
  Local state is used only for UI concerns (open/closed, focus, hover), never for domain state.

* **Tailwind for styling**
  Styling is implemented with Tailwind classes. Shared class helpers are fine where they improve reuse.

* **Theme‑agnostic**
  Components derive colours from Tailwind theme tokens rather than hard‑coding values so a light/dark app‑wide theme remains possible without refactors.

* **Predictable APIs**

  * Components are PascalCase (`Button`, `GlobalTopBar`).
  * Boolean props are `isX`/`hasX` (e.g. `isLoading`).
  * Event handlers are `onX` (e.g. `onClick`, `onSelect`).

---

## 3. Component categories

This section summarises the main component families and their expected usage patterns.

### 3.1 Buttons

#### `Button`

Generic clickable action.

* **Variants**

  * `"primary"` – main call‑to‑action in a view (e.g. “Start run”, “Upload document”).
  * `"secondary"` – important but secondary actions (e.g. “Cancel”, “Back”).
  * `"ghost"` – low‑emphasis actions (e.g. “View logs”, “More details”).
  * `"danger"` – destructive actions (e.g. “Delete configuration”).

* **Sizes**
  `"sm"`, `"md"`, `"lg"` (default is `"md"`).

* **Loading state**

  * `isLoading` disables the button and shows an inline spinner.
  * Clicks are ignored while `isLoading` is true.

Example:

```tsx
<Button variant="primary" isLoading={isSubmitting} onClick={handleStartRun}>
  Start run
</Button>
```

#### `SplitButton`

Primary action plus a small dropdown of related actions. The canonical example is the Configuration Builder **Test** control (primary “Test”, menu “Force build and test”).

* Left segment: calls `onPrimaryClick` (e.g. “Test” with environment reuse).
* Right segment: opens a dropdown (often backed by `ContextMenu`) with secondary options (e.g. “Force build and test”).

Guidelines:

* Use when there is **one obvious default** and 1–3 related expert options.
* The primary action should correspond to the “safe, common” behaviour.

---

### 3.2 Form controls

#### `Input`

Single‑line text input.

* Props: `value`, `onChange`, `type`, `placeholder`, etc.
* `invalid` prop applies error styling and sets `aria-invalid="true"`.

#### `TextArea`

Multi‑line text input.

* Shares styling and error handling with `Input`.

#### `Select`

Styled wrapper around a native `<select>`.

* Visual alignment with `Input` and `TextArea`.
* Optional disabled placeholder option for “no selection”.

#### `FormField`

Wrapper that connects a control to a label, hint, and error message.

* Props:

  * `label: string`
  * `hint?: string`
  * `error?: string`
  * `fieldId?: string`
  * `children: ReactNode` (exactly one form control)

Behaviour:

* Ensures a `<label>` is associated with the control (`htmlFor` / `id`).
* Sets `aria-describedby` to hint and/or error elements.
* Sets `aria-invalid` when `error` is present.

Example:

```tsx
<FormField label="Workspace name" hint="Shown in the sidebar" error={errors.name}>
  <Input
    value={name}
    onChange={e => setName(e.target.value)}
    invalid={Boolean(errors.name)}
  />
</FormField>
```

---

### 3.3 Feedback

#### `Alert`

Inline, non‑modal message.

* Props:

  * `tone: "info" | "success" | "warning" | "danger"`
  * Optional `heading`
  * Optional icon (chosen based on tone)

Usage:

* Section‑level issues or guidance.
* Long‑lived success messages (“This configuration is now active.”).
* Local warnings (“This run used an older configuration version.”).

Global banners and toasts are composed using `Alert` styles at higher layers (see § 5).

---

### 3.4 Identity

#### `Avatar`

Text‑based avatar.

* Derives initials from `name` (preferred) or `email`.
* Sizes: `"sm"`, `"md"`, `"lg"`.

Used for:

* Users in the top bar and member lists.
* Workspaces in nav and cards (workspaces may use first letter or initials of their name).

#### `ProfileDropdown`

User menu in the top bar.

* Shows:

  * Display name.
  * Email address.
* Offers actions such as:

  * “Sign out”
  * Links to profile/account settings (if present).

Behaviour:

* Opens on click.
* Closes on:

  * Outside click.
  * Escape key.
  * Selecting an item.
* Manages focus so keyboard users can open, move within, and close the menu without getting “lost”.

---

### 3.5 Navigation widgets

#### Tabs (`TabsRoot`, `TabsList`, `TabsTrigger`, `TabsContent`)

Accessible tab system:

* `TabsRoot` owns state (selected tab).
* `TabsList` wraps triggers, sets `role="tablist"`.
* `TabsTrigger` is a `<button>` with `role="tab"`, `aria-selected`, and `aria-controls`.
* `TabsContent` is a container with `role="tabpanel"` and `aria-labelledby`.

Keyboard:

* `ArrowLeft` / `ArrowRight` move between tabs.
* `Home` / `End` jump to first / last.
* Focus and selection behaviour matches ARIA authoring practices.

Tabs are used for:

* Splitting views within a section (e.g. “Console” vs “Validation” in the workbench).
* Settings sub‑sections where URL state isn’t required.

#### `ContextMenu`

Right‑click / kebab‑menu popup:

* Takes a list of items:

  * `label`
  * Optional `icon`
  * Optional `shortcut` string (visual only)
  * `onSelect`
  * `danger?: boolean`
  * `disabled?: boolean`

* Positions itself within the viewport to avoid overflow.

* Keyboard:

  * `ArrowUp` / `ArrowDown` to move.
  * `Enter` / `Space` to select.
  * `Esc` to close.

Used for:

* Workbench file tree (file/folder actions).
* Workbench tabs (close, close others, etc.).
* Any context‑sensitive menu where right‑click behaviour helps.

---

### 3.6 Top bar and search

#### `GlobalTopBar`

Shell‑level horizontal bar used in both the Workspace directory and Workspace shell.

Slots:

* `brand` – product or workspace directory branding.
* `leading` – breadcrumbs or current context (workspace name, environment label).
* `actions` – top‑level actions (e.g. “Start run”, “Upload”).
* `trailing` – typically `ProfileDropdown`.
* `secondaryContent` – optional row for filters, breadcrumbs, or hints.

Responsive behaviour:

* On narrow viewports, the bar collapses to prioritise brand, search, and profile.

#### `GlobalSearchField`

Search field embedded into `GlobalTopBar`.

Capabilities:

* Optional scope label (e.g. “Within workspace”).

* Controlled/uncontrolled mode.

* Global shortcut:

  * `⌘K` on macOS.
  * `Ctrl+K` on Windows/Linux.

* Suggestions dropdown:

  * Arrow keys to navigate.
  * Enter to select.
  * Esc to close.

The field itself remains generic; feature code decides:

* Which suggestions to show.
* How to handle “submit” and “select” actions (e.g. navigate to a run, filter documents).

---

### 3.7 Code editor wrapper

#### `CodeEditor`

A thin wrapper for Monaco, used by the Configuration Builder workbench.

Responsibilities:

* Manage Monaco’s lifecycle and lazy loading.

* Expose a `ref` with:

  * `focus()`
  * `revealLine(lineNumber: number)`

* Handle:

  * `language` (string ID, e.g. `"python"`, `"json"`).
  * `path` (virtual file path for Monaco’s model).
  * `theme` (`"ade-dark"` or `"vs-light"`).
  * `value` / `onChange`.
  * `readOnly`.
  * `onSaveShortcut` (wired to `⌘S` / `Ctrl+S`).

It does **not** know about ADE script semantics; those are configured by the workbench layer (see [`09-workbench-editor-and-scripting.md`](./09-workbench-editor-and-scripting.md)).

---

## 4. Accessibility patterns

Accessibility is a core requirement. UI components are responsible for exposing correct semantics; features only provide content.

### 4.1 Semantic roles and labels

* Use semantic elements wherever possible:

  * Buttons are `<button>`, links are `<a>`, lists are `<ul>/<li>`.

* When semantics require ARIA:

  * Tabs, menus, toolbars, and context menus use ARIA roles (`role="tab"`, `role="menu"`, etc.).
  * `Alert` uses `role="status"` or `role="alert"` where appropriate.

* Labels:

  * Icon‑only buttons must have `aria-label` or `aria-labelledby`.
  * `FormField` ensures text labels are linked to inputs via `for`/`id`.

### 4.2 Focus behaviour

Patterns:

* **Dropdowns/menus** (`ProfileDropdown`, `ContextMenu`):

  * When opened via keyboard, focus moves into the menu.
  * Tab/Shift+Tab cycle within the menu.
  * Esc closes the menu and returns focus to the trigger.

* **Overlays** (maximised workbench, future modals):

  * Background content is visually de‑emphasised and not focusable.
  * Focus is trapped within the overlay.
  * Esc closes or restores (subject to unsaved‑changes handling) and returns focus.

* **Tab order**:

  * Interactive elements must be reachable via Tab in a logical order.
  * Avoid `tabIndex` except where needed to support composite widgets (tabs, menus).

### 4.3 Keyboard interactions

For each widget:

* **Buttons and triggers**:

  * React to `Enter` and `Space`.
  * Visually indicate focus.

* **Tabs**:

  * Left/Right/Home/End manage focus and selection as per ARIA guidelines.

* **Menus**:

  * Arrow keys move between items.
  * Enter/Space selects.
  * Esc cancels.

### 4.4 Automated a11y checks

We treat automated accessibility tooling (e.g. axe) as a source of truth where practical. Violations reported in tests are expected to fail the suite until resolved or explicitly justified.

Shortcuts (below) build on top of these primitives.

---

## 5. Keyboard shortcuts

Keyboard shortcuts are implemented centrally (e.g. in `src/shared/keyboard`). UI components may display shortcut hints, but they do not bind global listeners themselves.

### 5.1 Global shortcuts

* `⌘K` / `Ctrl+K`
  Focus the `GlobalSearchField` or open a workspace search overlay.

* `⌘U` / `Ctrl+U`
  Open the document upload flow in the Documents section (when available).

Rules:

* Global shortcuts **must not** override browser behaviour when focus is in:

  * Text inputs.
  * Textareas.
  * Content‑editable regions.

* If a screen does not support a shortcut (e.g. `⌘U` on the Configuration Builder), the handler must no‑op.

### 5.2 Workbench shortcuts

Scoped to the Configuration Builder workbench:

* `⌘S` / `Ctrl+S` – Save active file in `CodeEditor`.
* `⌘B` / `Ctrl+B` – Build / reuse environment.
* `⇧⌘B` / `Ctrl+Shift+B` – Force rebuild.
* `⌘W` / `Ctrl+W` – Close active editor tab.
* `⌘Tab` / `Ctrl+Tab` – Switch to most recently used tab (forward).
* `⇧⌘Tab` / `Shift+Ctrl+Tab` – Switch MRU backward.
* `Ctrl+PageUp` / `Ctrl+PageDown` – Cycle tabs by visual order.

Guidelines:

* Implemented in the workbench container, not in `CodeEditor` or tab components directly.
* Use `preventDefault()` only when a shortcut is actually handled.
* Shortcuts should be disabled while modal dialogs in the workbench are open, unless they are explicitly designed to work there.

---

## 6. Notifications

Notifications are built from the same primitives (`Alert`, top‑bar/banners) but rendered at different scopes.

### 6.1 Toasts

Short‑lived messages that appear in a corner overlay.

Use for:

* Fast, non‑blocking feedback:

  * “Run queued.”
  * “File saved.”
  * “Document uploaded.”

Behaviour:

* Auto‑dismiss after a short duration.
* Accessible via a status region so screen readers receive updates.

### 6.2 Banners

Persistent messages at the top of a workspace or section.

Use for:

* Safe mode notifications.
* Connectivity problems.
* Important system‑level warnings.

Behaviour:

* Rendered under `GlobalTopBar` in the Workspace shell.
* Remain visible until the underlying condition changes or a user closes them (if dismissible).

### 6.3 Inline alerts

Local to a panel or form:

* Validation summary at the top of a form.
* Warning about a specific run or configuration.
* Guidance in an empty state.

These use `Alert` directly within the layout.

---

## 7. State persistence and user preferences

UI state and preferences are stored in `localStorage` via helpers in `src/shared/storage`. Components in `src/ui` are written to work cleanly whether preferences are present or absent.

### 7.1 Key naming convention

All preference keys follow:

```text
ade.ui.workspace.<workspaceId>.<suffix>
```

Examples:

* `ade.ui.workspace.<workspaceId>.nav.collapsed`
* `ade.ui.workspace.<workspaceId>.workbench.returnPath`
* `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.tabs`
* `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.console`
* `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.editor-theme`
* `ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences`

Rules:

* Keys are **per user**, **per workspace**, and optionally **per configuration** or **per document**.
* Only non‑sensitive data is stored; clearing storage should never break server state.
* No tokens, secrets, or PII beyond IDs that are already visible in the UI.

### 7.2 Persisted preferences

Current preferences include:

* **Workspace nav collapsed state**

  * Suffix: `nav.collapsed` (boolean).

* **Workbench return path**

  * Suffix: `workbench.returnPath` (string URL).
  * Used when exiting the workbench to navigate back to where the user came from.

* **Workbench open tabs**

  * Suffix: `configuration.<configurationId>.tabs`.
  * Value: `PersistedWorkbenchTabs` (open tab IDs, active ID, MRU list).

* **Workbench console state**

  * Suffix: `configuration.<configurationId>.console`.
  * Value: `ConsolePanelPreferences` (open/closed + height fraction).

* **Editor theme preference**

  * Suffix: `configuration.<configurationId>.editor-theme`.
  * Value: `"system" | "light" | "dark"`.

* **Per‑document run preferences**

  * Suffix: `document.<documentId>.run-preferences`.
  * Value: last used configuration, configuration version, sheet selections, optional run flags.

### 7.3 Access patterns

All storage access goes through helpers such as:

* `getPreference(workspaceId, suffix, defaultValue?)`
* `setPreference(workspaceId, suffix, value)`
* `clearWorkspacePreferences(workspaceId)`

Feature code (not `src/ui`) calls these helpers. Components simply receive the derived state via props.

---

## 8. Testing and quality

UI behaviour is validated with Vitest and React Testing Library. The goal is to test real user‑visible behaviour, not implementation details.

### 8.1 Test environment

Configuration (see `vitest.config.ts`):

* `environment: "jsdom"`
* `setupFiles: "./src/test/setup.ts"`
* `globals: true`
* `coverage.provider: "v8"`

`src/test/setup.ts` is responsible for:

* Installing DOM polyfills as needed.
* Configuring React Testing Library defaults.
* Optionally mocking `window.matchMedia` and similar browser APIs.

### 8.2 Testing `src/ui` components

For each component, prefer small, focused tests:

* **Buttons**

  * Click invokes `onClick`.
  * `isLoading` disables the button and renders a spinner.
  * Correct classes for variants and sizes.

* **Form controls / `FormField`**

  * `FormField` wires label, hint, and error via `for`/`id` and `aria-describedby`.
  * `invalid` sets `aria-invalid`.

* **Tabs**

  * Correct ARIA roles and attributes.
  * Arrow keys change focus and selection.
  * Only the active panel is visible.

* **ContextMenu**

  * Opens on trigger.
  * Items can be navigated by keyboard.
  * Calls `onSelect` and closes on selection or Esc.

* **ProfileDropdown**

  * Opens/closes with click and Esc.
  * Focus returns to trigger on close.

Tests should focus on:

* **What** the user sees and can do.
* Not **how** the component is implemented internally.

### 8.3 Testing keyboard shortcuts

Shortcuts are tested at the feature level, but they rely on UI components behaving correctly.

Examples:

* Global search:

  * Simulate `Ctrl+K`.
  * Assert that `GlobalSearchField` is focused.
  * Assert no action when a text input has focus.

* Workbench shortcuts:

  * Render workbench with `CodeEditor` and tabs.
  * Simulate `Ctrl+S` and assert the save handler is called.
  * Simulate `Ctrl+W` and assert the active tab closes.

These tests live under `src/features/.../__tests__/` and treat `src/ui` components as black boxes.

### 8.4 Testing state persistence

Test the storage helpers and features that rely on them:

* Storage helpers:

  * Correct key computation given workspace/configuration/document IDs.
  * Graceful handling of missing/malformed data.

* Workbench:

  * Hydrates tabs from persisted state.
  * Writes updated state when tabs open/close.

* Preferences:

  * Editor theme, console state, nav collapse.

UI components are not tested against `localStorage` directly; they assume their props are already configured.

### 8.5 Quality conventions

To keep the UI layer maintainable:

* **No direct globals**

  * Don’t call `window.location` or `localStorage` directly in `src/ui`.
  * Don’t attach global event listeners from `src/ui` without a clear cleanup path.

* **Linting & formatting**

  * Components must pass ESLint and Prettier checks enforced by the repo.

* **Keep docs in sync**

  * When adding a new UI component, shortcut, or preference:

    * Update this document.
    * If behaviour affects workbench or layout, update the relevant docs (`06`, `09`).

### 8.6 Selecting elements in tests

Prefer semantic queries in React Testing Library (`getByRole`, `getByLabelText`, visible text) so tests match user behaviour. Use `data-testid` only when no suitable semantic selector exists, and declare them in `src/ui` components to keep selectors stable for feature tests.

This keeps the UI layer small, predictable, and easy for both humans and AI agents to understand and extend.
