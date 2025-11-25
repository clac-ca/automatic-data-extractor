# 10. UI components, accessibility, and testing

This document describes the `src/ui` component library, how it is structured, and how we keep it accessible and well‑tested.

It is written for developers adding or modifying UI components and for anyone wiring those components into features under `src/features`.

> **Key principles**
>
> - `src/ui` is **presentational**: no business logic, no data fetching.
> - Components are **accessible by default**: ARIA, keyboard, and focus are first‑class.
> - Behaviour is **predictable**: consistent props, naming, and interaction patterns.
> - Components are **tested**: new components ship with tests that exercise user‑visible behaviour.

---

## 1. Scope and responsibilities of `src/ui`

The `src/ui` folder is the app‑specific component library for ADE Web.

Responsibilities:

- Provide reusable **visual primitives** (buttons, inputs, alerts, layout scaffolding).
- Provide **composite widgets** that are UI‑heavy but domain‑agnostic (tabs, context menus, top bar, profile dropdown, search field, editor shell).
- Establish **accessibility and keyboard conventions** that features can rely on.
- Expose **stable APIs** so features can be refactored without rewriting UI.

Non‑responsibilities:

- No HTTP calls or React Query hooks.
- No business/domain logic (workspaces, documents, jobs, configs, roles).
- No direct `localStorage` access (persistence is handled in `src/shared`).
- No routing/navigation logic beyond what is required to render links.

If you find yourself needing domain data or making decisions based on permissions, that logic belongs in a feature component under `src/features`, not in `src/ui`.

---

## 2. UI architecture and patterns

### 2.1 Folder structure

Typical layout:

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
    Tabs.tsx
    ContextMenu.tsx
  shell/
    GlobalTopBar.tsx
    GlobalSearchField.tsx
  code-editor/
    CodeEditor.tsx
````

We group components by **function** (button, form, feedback, navigation, etc.), not by feature.

When adding a new component:

1. Place it in the appropriate folder (or create a new one if it clearly doesn’t fit).
2. Keep **one main component per file**.
3. Export from that file; optional barrel files (`index.ts`) are okay but not required.

### 2.2 Component design constraints

All UI components follow these constraints:

* **Tailwind first**
  Styling is implemented using Tailwind utility classes with a small number of shared class helpers where needed.

* **Controlled vs uncontrolled**
  Inputs (`Input`, `TextArea`, `Select`) are capable of being controlled; they may expose `defaultValue` as a convenience, but external state is the source of truth.

* **No ambient singletons**
  Components do not reach into global state (no hidden contexts); any configuration comes via props.

* **Stateless where possible**
  Components should be as stateless as reasonable. If local state is required (e.g. open/close state for menus), it should not encode domain semantics.

### 2.3 Props and naming conventions

* Component names are **PascalCase** (`Button`, `SplitButton`, `GlobalTopBar`).
* Boolean props start with **`is`** or **`has`** (e.g. `isLoading`, `hasError`).
* Event handlers follow React conventions (`onClick`, `onSelect`, `onClose`).
* Variant‑style props are usually `variant: "primary" | "secondary" | ...`.

Example:

```tsx
<Button
  variant="primary"
  size="md"
  isLoading={isSubmitting}
  onClick={handleSubmit}
>
  Save changes
</Button>
```

---

## 3. Core primitives

This section summarises the major UI components and the patterns they implement. For detailed prop signatures, see the component source.

### 3.1 Buttons

#### `Button`

* **Variants**: `primary`, `secondary`, `ghost`, `danger`.
* **Sizes**: `sm`, `md`, `lg`.
* **Loading state**: `isLoading` disables the button and shows a spinner, but still renders children for layout stability.

Usage guidelines:

* Use `primary` for the main action in a view.
* Use `secondary` for inline actions that are still important but not primary.
* Use `ghost` for low‑emphasis actions (e.g. “Cancel”).
* Use `danger` for destructive actions; pair with a confirmation pattern at the feature level.

#### `SplitButton`

Combined primary action + dropdown menu.

* Left part: main action (e.g. “Build / reuse environment”).
* Right part: toggle menu (e.g. “Force rebuild now”, “Force rebuild after current build”).

Usage guidelines:

* Use when there is a **single most common** action and 2–3 related variations.
* The primary click should match the most common action (respecting user expectations and safe defaults).

### 3.2 Forms

#### `Input`, `TextArea`, `Select`

* Share consistent padding, border, and focus rings.
* Accept an `invalid` prop that triggers error styling and sets `aria-invalid`.

They do *not* render labels or errors themselves; that is handled by `FormField`.

#### `FormField`

Wraps a label + control + hint + error:

* Props: `label`, `hint`, `error`, and `fieldId` for the underlying control.
* Automatically wires:

  * `<label htmlFor={fieldId}>`
  * `aria-describedby` on the control (hint/error).
  * `aria-invalid` when `error` is present.

Usage:

```tsx
<FormField
  label="Workspace name"
  hint="Shown in the sidebar and top bar."
  error={errors.name}
  fieldId="workspace-name"
>
  <Input
    id="workspace-name"
    value={name}
    onChange={handleChange}
/>
</FormField>
```

### 3.3 Feedback

#### `Alert`

* Prop: `tone: "info" | "success" | "warning" | "danger"`.
* May render an optional `heading` and an icon appropriate to the tone.
* Used for inline, persistent messages (at section or panel level).

Usage guidelines:

* Use `info` for neutral announcements.
* Use `success` for “sticky” success messages that should remain visible.
* Use `warning` for recoverable issues.
* Use `danger` for critical issues or destructive confirmation contexts.

Global toasts and banners are composed from `Alert` plus positioning logic at a higher level.

### 3.4 Identity & profile

#### `Avatar`

* Derives initials from `name` or `email`.
* Supports `sm`, `md`, `lg` sizes.
* Can optionally display a small presence indicator if needed in the future.

#### `ProfileDropdown`

* Shows current user name/email and a menu of actions.
* Handles:

  * Click to open/close.
  * Outside click to close.
  * Escape key to close.
  * Focus management between trigger and menu items.

Feature code is responsible for wiring the menu actions, including sign‑out.

### 3.5 Navigation components

#### Tabs (`TabsRoot`, `TabsList`, `TabsTrigger`, `TabsContent`)

* Implements an accessible tablist:

  * `role="tablist"` on `TabsList`.
  * `role="tab"` and `aria-selected` on `TabsTrigger`.
  * `role="tabpanel"` and `aria-labelledby` on `TabsContent`.

* Keyboard behaviour:

  * `Left`/`Right` arrow to move between tabs.
  * `Home` moves to first tab, `End` to last.
  * Tab selection can be decoupled from focus when needed.

#### `ContextMenu`

* Right‑click or keyboard‑invoked context menu.
* Positions itself within the viewport to avoid clipping.
* Keyboard behaviour:

  * `ArrowUp`/`ArrowDown` to navigate items.
  * `Enter`/`Space` to activate.
  * `Esc` to close.

Features provide the item list (labels, actions, optional icons and danger flags).

### 3.6 Top bar and search

#### `GlobalTopBar`

* Top‑level layout for:

  * Product/brand.
  * Workspace context (breadcrumbs, environment label).
  * Actions (buttons).
  * Profile menu.
  * `secondaryContent` for filters, breadcrumbs, or extra context.

#### `GlobalSearchField`

* Composed inside `GlobalTopBar` when search is available.

* Supports:

  * Controlled or uncontrolled value.
  * Optional scope label (e.g. “Within workspace”).
  * Keyboard shortcut (`⌘K` / `Ctrl+K`) to focus.
  * Suggestion dropdown with keyboard navigation:

    * `ArrowUp`/`ArrowDown` to move.
    * `Enter` to select.
    * `Esc` to close.

* Feature code supplies the suggestion list, loading state, and what happens when a suggestion is selected.

### 3.7 Code editor shell (`CodeEditor`)

`CodeEditor` wraps Monaco and hides its loading and configuration details.

* Props include:

  * `language` (e.g. `python`, `json`).
  * `path` (virtual file path; used for Monaco models).
  * `theme` (`ade-dark` or `vs-light`).
  * `readOnly`.
  * `onChange` and `onSaveShortcut`.

* Provides an imperative handle:

  * `focus()` to focus the editor.
  * `revealLine(lineNumber)` to scroll to a line.

All ADE‑specific editor behaviour (script helpers, diagnostics, decorations) is configured at the workbench level, not inside `CodeEditor`.

---

## 4. Accessibility guidelines

Accessibility (a11y) is not optional. Any new or modified component in `src/ui` must respect these guidelines.

### 4.1 Roles, labels, and relationships

* All interactive components must have:

  * A semantic element (`button`, `a`, `input`, etc.), or
  * An appropriate ARIA role (e.g. `role="menuitem"`).

* Labels:

  * Inputs should be associated with `<label>` elements whenever visible.
  * Icon‑only buttons should have `aria-label` or `aria-labelledby`.

* Relationships:

  * `FormField` manages `aria-describedby` to connect hints/errors to inputs.
  * Tabs and panels use `aria-controls`/`aria-labelledby` appropriately.

### 4.2 Keyboard accessibility

* All interactive elements must be reachable with `Tab` and operable with keyboard.

* Patterns:

  * Buttons and menu items respond to `Enter` and `Space`.
  * Menus and dropdowns trap focus while open and close on `Esc`.
  * Tabs respond to arrow keys as described above.

* When introducing a new interactive widget, copy keyboard behaviour from an existing one (e.g. `ContextMenu` for menus, Tabs for tablists) where appropriate.

### 4.3 Focus management

* **Modals and overlays** (e.g. maximised workbench, dialogs):

  * Trap focus within the overlay while open.
  * Return focus to the trigger element when closed.
  * Close on `Esc`.

* **Dropdowns and menus**:

  * When opened via keyboard, focus the first item.
  * Keep focus inside until the user selects or closes.

* Avoid manual `document.activeElement` manipulations where React focus management suffices.

### 4.4 Announcing changes

* Use `role="status"` or `role="alert"` for important messages:

  * For global banners (safe mode, connectivity issues), `role="status"` with polite announcements.
  * For destructive errors, consider `role="alert"`.

* Toasts should be announced as status updates when they represent critical feedback.

### 4.5 Reduced motion and animations

* If you add animations:

  * Respect `prefers-reduced-motion` where relevant.
  * Prefer subtle transitions for state changes; avoid large parallax or continuous movement.

---

## 5. Keyboard shortcuts

Keyboard shortcuts are part of the UI design. They must be consistent and scoped.

### 5.1 Global shortcuts

* `⌘K` / `Ctrl+K` – Focus the global search field (directory or shell).
* `⌘U` / `Ctrl+U` – Open document upload (when a documents view is active).

Guidelines:

* Only active on screens where the action makes sense.
* Do not override browser shortcuts on generic inputs (if a text field is focused, do nothing).

### 5.2 Workbench shortcuts

Inside the Config Builder workbench:

* `⌘S` / `Ctrl+S` – Save active editor file.
* `⌘B` / `Ctrl+B` – Build / reuse environment.
* `⇧⌘B` / `Ctrl+Shift+B` – Force rebuild.
* `⌘W` / `Ctrl+W` – Close active editor tab.
* `⌘Tab` / `Ctrl+Tab` – Move forward by most‑recently‑used tab order.
* `⇧⌘Tab` / `Shift+Ctrl+Tab` – Move backward by MRU.
* `Ctrl+PageUp/PageDown` – Move left/right by visual tab order.

Guidelines:

* Shortcuts are registered at the workbench level, not inside `CodeEditor`.
* They should be disabled when focus is in generic inputs not related to code (e.g. search fields) to avoid surprising behaviour.

### 5.3 Implementing shortcuts

Shortcut handlers typically live in feature code (e.g. workbench container), not in `src/ui`. Components in `src/ui` may expose hooks or utilities to make binding easier (e.g. `useKeybinding`), but they do not make assumptions about domain actions.

---

## 6. Notifications and messaging patterns

ADE Web has three primary notification surfaces:

1. **Toasts** – transient feedback for quick operations.
2. **Banners** – persistent messages at the top of a workspace or section.
3. **Inline alerts** – local to a panel or form.

### 6.1 Toasts

* Built from an `Alert`‑like primitive, rendered in a global layer.

* Use for:

  * Success feedback on saves.
  * Minor errors that don’t block the entire page.

* Should auto‑dismiss after a short time, with an accessible reading window.

### 6.2 Banners

* Rendered inside the workspace shell, above section content.

* Use for:

  * Safe mode messages.
  * Connectivity warnings.
  * Major environment‑level issues.

* Should remain visible until the underlying condition changes or a user action dismisses them (if appropriate).

### 6.3 Inline alerts

* Use `Alert` directly inside sections or panels.
* Appropriate for:

  * Form validation summaries at the top of the form.
  * Resource‑specific issues (e.g. a particular job or config failed to load).

---

## 7. State persistence and user preferences

State persistence is implemented in `src/shared/storage` and *used* by features, but the UI library is designed with these patterns in mind.

### 7.1 Key naming convention

All persisted UI state keys follow the pattern:

```text
ade.ui.workspace.<workspaceId>.<scope>
```

Examples:

* `ade.ui.workspace.<ws>.nav.collapsed`
* `ade.ui.workspace.<ws>.workbench.returnPath`
* `ade.ui.workspace.<ws>.config.<configId>.tabs`
* `ade.ui.workspace.<ws>.config.<configId>.console`
* `ade.ui.workspace.<ws>.config.<configId>.editor-theme`
* `ade.ui.workspace.<ws>.document.<documentId>.run-preferences`

Guidelines:

* Keys are **per‑user** and **per‑workspace**; never encode secrets or auth data.
* Clearing localStorage must leave the app in a safe, usable state.

### 7.2 Preferences that involve `src/ui` components

Relevant examples:

* **Left nav collapsed state**
  Affects the navigation shell components (not in `src/ui`, but the pattern is shared).

* **Workbench tabs and MRU list**
  Drives which files are opened when the editor mounts; `Tabs` components must handle initial selection gracefully.

* **Console open/closed state and height**
  Determines initial layout; resizing logic should read defaults and then honour user adjustments.

* **Editor theme preference**
  Controls `CodeEditor`’s `theme` prop.

* **Per‑document run preferences**
  Affect initial values in run dialogs; `FormField` etc. should render these as “just state”.

Components themselves remain decoupled; they simply render state passed from feature code.

---

## 8. UI testing and quality

UI testing ensures that components behave correctly across refactors and prevent regressions in keyboard/a11y behaviour.

### 8.1 Testing stack

* **Test runner**: Vitest.
* **Environment**: `jsdom` for browser‑like APIs.
* **Setup**: `src/test/setup.ts` for global configuration and polyfills.
* **Coverage**: v8 coverage configuration is enabled.

### 8.2 What to test in `src/ui`

For each component, tests should verify:

* **Rendering**:

  * Renders expected DOM structure given props.
  * Applies correct classes for variants and states.

* **Interaction**:

  * Click interactions call the appropriate callbacks.
  * Keyboard interactions behave as documented (e.g. Tabs arrow keys, ContextMenu navigation).

* **Accessibility**:

  * ARIA attributes are present and correctly wired (`aria-invalid`, `aria-selected`, `role="tab"`, etc.).
  * Focus management behaves as expected (particularly for dropdowns/menus).

Example categories:

* `Button`: loading state disables click, renders spinner.
* `Tabs`: keyboard navigation, ARIA attributes, tab selection vs focus.
* `ProfileDropdown`: open/close on click, outside click and `Esc`, focus returns to trigger.
* `GlobalSearchField`: shortcut focusing, suggestion navigation.

### 8.3 Integration tests at feature level

Not strictly part of `src/ui`, but important for overall behaviour:

* Navigation flows (route changes) using `Link` and `NavLink`.
* Workbench state (tabs, console, URL state) using `CodeEditor`, tabs, and layout panels.
* Documents/jobs flows with actual components composed together.

These tests live in `src/features/**/__tests__` and exercise multiple components in concert.

### 8.4 Adding or changing a component

When adding a new component or changing behaviour:

1. Update the component implementation under `src/ui`.

2. Add or update tests:

   * Component tests under `src/ui/**/__tests__`.
   * Integration tests if behaviour changes at feature level.

3. Verify keyboard and screen‑reader behaviour locally (tab through, try world‑without‑mouse).

4. If props or behaviour changes are significant, update this document and any references in other docs (e.g. Config Builder docs if it affects the workbench).

---

By following these patterns, `src/ui` remains a small but powerful library: predictable to use, accessible out of the box, and safe to evolve as the rest of ADE Web grows.