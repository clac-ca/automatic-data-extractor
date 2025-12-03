# ADE Web – Design System

> This document defines the visual language, tokens, and UI primitives for the **new** `apps/ade-web`.  
> It is the reference for how we design and implement UI across Workspace, Documents, Run Detail, and Config Builder.

---

## 1. Purpose & Scope

The design system exists to ensure that:

- ADE Web feels **cohesive** across all screens (Workspace, Documents, Config Builder, Run Detail).
- We can build **fast and safely**, using shared primitives instead of ad‑hoc styling.
- Streaming-heavy views (logs, timelines, validation) remain **readable and calm**, even under load.

It covers:

- Design principles.
- Tokens (colors, typography, spacing, radii, elevation).
- Core components (buttons, inputs, layout primitives).
- ADE‑specific components (status chips, timelines, console, upload panel).
- Implementation and accessibility guidelines.

Implementation lives under `apps/ade-web/src/ui` in the new app.

---

## 2. Design Principles

### 2.1 Clarity over cleverness

- Prioritize legibility: clear hierarchy, obvious actions, predictable behavior.
- Use color and motion sparingly and purposefully (status, feedback, not decoration).

### 2.2 Calm data UX

- We show a lot of information (logs, phases, tables) – the UI should reduce noise:
  - Plenty of whitespace and consistent spacing.
  - Subtle dividers instead of heavy chrome.
  - Avoid loud colors except for status and errors.

### 2.3 Consistency & reuse

- Same patterns and components for:
  - Buttons, forms, tabs, dialogs, toasts.
  - Status chips for runs and documents.
  - Headers and cards across screens.
- No screen-specific “one-off” styles for things that can be generalized.

### 2.4 Streaming-aware

- Live updates must **not** feel jittery or overwhelming:
  - Logs append smoothly; users can pause scrolling.
  - Status updates are clear but not blinking or animating constantly.
  - Replay and deep links use the same visual language as live mode.

### 2.5 Accessible by default

- Keyboard-first navigation is possible everywhere.
- Color choices meet contrast requirements.
- Screen readers can understand structure and status.

---

## 3. Tokens & Theming

We expose design tokens as CSS variables, with a light/dark theme applied via a top-level theme class (e.g. `.theme-light`, `.theme-dark`).

### 3.1 Color System

We define **semantic** tokens (not raw palette names):

#### Base

- `--color-bg` – base page background.
- `--color-surface` – cards, panels.
- `--color-surface-strong` – headers, emphasis surfaces.
- `--color-border-subtle` – table/section dividers.
- `--color-border-strong` – strong outlines (errors, focus).
- `--color-text-primary`
- `--color-text-muted`
- `--color-text-inverse` – for content on dark surfaces.

#### Brand & Accent

- `--color-accent` – primary action/text highlight.
- `--color-accent-soft` – subtle background for accent.
- `--color-accent-border` – border for focused/accent elements.

#### Status

Used for runs, documents, validation states:

- Info / neutral:
  - `--color-info`
  - `--color-info-soft`
- Success:
  - `--color-success`
  - `--color-success-soft`
- Warning:
  - `--color-warning`
  - `--color-warning-soft`
- Error:
  - `--color-danger`
  - `--color-danger-soft`

**Mapping (recommended):**

- **Run / document statuses:**
  - `queued` → info.
  - `running` → info (stronger).
  - `succeeded` → success.
  - `completed_with_warnings` → warning.
  - `failed` → danger.
  - `cancelled` → neutral (muted).

- **Validation:**
  - OK → success.
  - Warnings → warning.
  - Errors → danger.

### 3.2 Typography

Base:

- `--font-sans`: system sans stack or chosen font.
- `--font-mono`: monospace stack (for console/logs).

Sizes (example scale):

- `--text-xs`: ~11px
- `--text-sm`: ~13px
- `--text-md`: ~14–15px
- `--text-lg`: ~18px
- `--text-xl`: ~22px

Usage:

- Page title: `--text-xl`, semi-bold.
- Section header: `--text-lg` or `--text-md`, medium.
- Body: `--text-sm` or `--text-md`.
- Console: `--font-mono`, `--text-sm`.

Line height tokens:

- `--line-tight`, `--line-normal`, `--line-relaxed`.

### 3.3 Spacing & Layout

Spacing scale (example):

- `--space-1`: 4px
- `--space-2`: 8px
- `--space-3`: 12px
- `--space-4`: 16px
- `--space-5`: 24px
- `--space-6`: 32px

Usage guidelines:

- Page padding: `--space-5` or `--space-6`.
- Gaps between stacked elements: `--space-3` or `--space-4`.
- Intra-component padding (button, pill): `--space-2` vertical, `--space-3` horizontal.

### 3.4 Radii & Elevation

Radii:

- `--radius-sm`: 3–4px (chips, pills).
- `--radius-md`: 6–8px (cards, panels).
- `--radius-lg`: 9999px (fully rounded pills/buttons).

Elevation:

- Flat design by default; elevation only for overlays:
  - `--shadow-sm`: subtle card shadow.
  - `--shadow-md`: dialogs, dropdowns.
  - `--shadow-lg`: important modals (rare).

---

## 4. Interaction Guidelines

### 4.1 States

Every interactive component supports:

- **Default**
- **Hover**
- **Active/Pressed**
- **Focus-visible** (keyboard focus)
- **Disabled**

Guidelines:

- Disable through visual + semantic means (attribute + reduced opacity).
- Focus state must be clearly visible and **not** rely solely on color.

### 4.2 Motion

- Keep motions subtle:
  - Short fade/slide for dialogs.
  - Micro-transitions for button hover/press.
- Avoid continuous animations for streaming (no flashing status).

---

## 5. Core Components

All core components live under `src/ui/components` and use tokens defined above.

### 5.1 Button / IconButton

**Props (high-level):**

- `variant`: `'primary' | 'secondary' | 'ghost' | 'danger'`.
- `size`: `'sm' | 'md' | 'lg'`.
- `iconBefore` / `iconAfter` (optional).
- `isLoading` (optional).

Guidelines:

- Use `primary` for one main action per view (e.g., “Start run”).
- Use `secondary` for supporting actions (e.g., “Download logs”).
- Use `ghost` for inline actions or within cards.
- Use `danger` only for destructive actions (e.g., delete document).

### 5.2 Input, Textarea, Select

Shared behavior:

- Full-width by default.
- Label component (`FormField`) to pair label, description, and error text.

States:

- Normal / Hover / Focus (accent border) / Error (danger border + text).

### 5.3 Checkbox, Radio, Switch

- Checkbox: multi-select / toggling options.
- Radio: single-choice group.
- Switch: on/off settings, not for one-off actions.

### 5.4 Tabs

Used for:

- Tabs in RunDetail (Console / Timeline / Validation).
- Tabs in Document detail (Overview / Runs / Outputs).

Behavior:

- Keyboard nav: left/right arrow moves tabs; Enter/Space activates.
- ARIA roles: `tablist`, `tab`, `tabpanel`.

### 5.5 Dialog & Drawer

Used for:

- Confirmations.
- Secondary flows (maybe config or document meta editing).

Requirements:

- Trap focus inside dialog.
- Close via Esc + overlay click (unless destructive or long-running action).

### 5.6 Tooltip

- Used for status chips, truncated text, timeline phases.
- Show on hover/focus.
- No critical information should be tooltip-only.

### 5.7 Toast

- Used for transient status messages (run start, download errors, etc.).
- Position: top-right or bottom-right.
- Types: info, success, warning, error.

---

## 6. Layout Components & Page Templates

Layout components live under `src/ui/layout`.

### 6.1 Page & PageHeader

- `Page`:
  - Provides consistent outer padding and max width.
- `PageHeader`:
  - Title + optional subtitle.
  - Primary and secondary actions.
  - Optional breadcrumb-like context (workspace / document / run).

Usage examples:

- Documents:
  - Title: “Documents”.
  - Primary: “Upload documents”.
- Run Detail:
  - Title: `Run #123`.
  - Subtitle: `workspace-name · document.csv`.
  - Primary: “Download normalized data”.

### 6.2 SplitPane & Panel

Used for:

- Documents (list on left, detail on right).
- Config Builder (navigation, editor, bottom run panel).

`SplitPane`:

- Responsive behavior:
  - Desktop: side-by-side.
  - Narrow: stacked with toggles if needed.

`Panel`:

- Reusable card container with header, optional actions, and body.

### 6.3 Table & EmptyState

**Table:**

- Used for Documents list, Runs list, Validation rows.
- Standard header, zebra rows (optional), subtle borders.

**EmptyState:**

- Icon + title + body text + CTA.
- Used when:
  - No documents.
  - No runs for a document.
  - No validation issues.

---

## 7. ADE-Specific Components

These live in `features/*/components` but follow design-system rules.

### 7.1 StatusPill

Used to show run/document/validation status.

Props (conceptual):

```ts
type StatusKind = 'run' | 'document' | 'validation';

interface StatusPillProps {
  kind: StatusKind;
  status: 'queued' | 'running' | 'succeeded' | 'warning' | 'failed' | 'cancelled';
  size?: 'sm' | 'md';
}
````

Mapping to color tokens:

* `queued` → `--color-info-soft` + `--color-info`.
* `running` → slightly stronger info treatment.
* `succeeded` → `--color-success-soft` + `--color-success`.
* `warning` → `--color-warning-soft` + `--color-warning`.
* `failed` → `--color-danger-soft` + `--color-danger`.

Usage:

* Document list statuses.
* Runs list statuses.
* Run detail header.

### 7.2 RunTimeline

Component that shows build + run phases in sequence.

Visual:

* Horizontal bar segmented by phase.
* Each segment:

  * Label (`build`, `normalize`, `validate`).
  * Color based on phase status.
  * Width proportional to duration (or approximate if partial).

States:

* When run is in progress:

  * Spinner or pulsing indicator on current phase.
* When run completed:

  * Final colors (success/failure) per phase.

In UI:

* Appears in RunDetail and Config Builder run panel.
* Minimally in Documents “Live run” card.

### 7.3 RunConsole

Log viewer component.

Behavior:

* Monospace font, small line height for density but still readable.
* Each line shows:

  * Timestamp.
  * Level (INFO/WARN/ERROR).
  * Origin (build/run).
  * Phase (if applicable).
  * Message.
* Filters:

  * Level (multi-select).
  * Origin.
  * Free text search.

Special behavior:

* “Follow tail” toggle:

  * When on, auto-scroll to bottom on new messages.
  * When user scrolls manually, auto-follow pauses until re-enabled.
* Error-first:

  * When run fails, highlight first error and allow one-click jump.

Accessibility:

* Should be scrollable with keyboard.
* ARIA labels describing current view (e.g., number of lines filtered).

### 7.4 ValidationSummary & TableCards

Shows validation results:

* Overall summary bar:

  * Ratio of passed/warning/error.
* Per-table cards:

  * Table name.
  * #rows, mapped/unmapped columns.
  * Error/warning counts with severity markers.

Clicking:

* Should filter RunConsole to relevant events.
* Should link back to config or document context when available.

### 7.5 UploadPanel

Used in Documents screen.

States:

* Idle:

  * Drag-and-drop area with icon and short description.
  * “Upload documents” button.
* Drag-over:

  * Highlighted border and background.
* Uploading:

  * Progress rows for each file.
* Error:

  * Inline error messages and retry affordance.

---

## 8. Page Layouts (Canonical Patterns)

### 8.1 Documents

Layout:

* `PageHeader`:

  * Title “Documents”.
  * Primary action “Upload documents”.
* `SplitPane`:

  * Left: `DocumentList`.
  * Right:

    * If nothing selected: helpful empty state.
    * If document selected:

      * `PageHeader`‑like section with document name + StatusPill.
      * Tabs: Overview / Runs / Outputs.
      * Within tabs, use `Panel` and feature components.

### 8.2 Run Detail

Layout:

* `PageHeader` with run ID, status, and main actions.
* Main content:

  * Top row:

    * Left: `RunTimeline`.
    * Right: `RunSummaryPanel`.
  * Bottom:

    * `RunConsole` with replay controls above.

### 8.3 Config Builder

Layout:

* Top: `PageHeader` with config name.
* Main:

  * `SplitPane`:

    * Left: config navigation.
    * Center: editor.
  * Bottom docked: run panel (`RunTimeline` + `RunConsole` tabs).

---

## 9. Implementation Guidelines

### 9.1 File Organization

* `src/ui/theme/tokens.css` – defines CSS variables.
* `src/ui/theme/ThemeProvider.tsx` – theme switching, including dark mode.
* `src/ui/components` – generic components (no ADE domain knowledge).
* `src/ui/layout` – layout primitives.

Feature-specific components (like `RunTimeline`) live under `features/runs/components`, but must:

* Use tokens (no hard-coded colors/sizes).
* Use core components where appropriate (Buttons, Tabs, etc.).

### 9.2 Props & API Conventions

* Prefer clear, descriptive prop names (e.g. `variant`, `size`, `tone`).
* Avoid passing through arbitrary `className` from screens; instead, expose purposeful props for variations.
* For layout, prefer composition over complex boolean props.

### 9.3 Don’ts

* Don’t use raw `#RRGGBB` colors in components; use CSS variables.
* Don’t depend on screen-specific selectors or “hacks” to style shared components.
* Don’t add new visual styles without updating this document and tokens if needed.

---

## 10. Accessibility Guidelines

* All interactive elements:

  * Keyboard operable.
  * Visible focus outline.
* Screen reader:

  * Status announcements for long-running tasks (e.g., run started/completed) via ARIA live regions in toasts.
  * Descriptive `aria-label` on icons without text.
* Color:

  * Ensure text has >= 4.5:1 contrast ratio where possible.
  * Don’t use color alone to indicate status; combine with text and/or icon.

---

## 11. Change Management

* **Minor styling tweaks** (spacing, color fine-tuning) can be made within the existing token structure.
* **New components or major variations**:

  * Add them here first (section under Components or ADE-specific).
  * Agree on design + props.
  * Then implement under `src/ui` or the appropriate `features/*/components` folder.

This design system is a living document; update it in lockstep with the implementation so future work doesn’t fall back to ad‑hoc UI.