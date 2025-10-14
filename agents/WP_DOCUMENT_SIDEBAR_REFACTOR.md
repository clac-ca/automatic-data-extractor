# Work Package: Document Sidebar Refactor

## Status
- **Owner:** Frontend Experience Squad
- **Last Reviewed:** 2025-10-15
- **State:** _Discovery_
- **Notes:** Planning package for the document rail revamp; aligns the workspace shell with the Vercel-inspired hover/collapse behaviours shared by product. Use this as the single source of truth for the sidebar refactor.

## Objective
Deliver a responsive, accessible document sidebar that feels fast to use, keeps recent and pinned documents close at hand, and matches the navigation guardrails defined in `AGENTS.md` and `agents/FRONTEND_DESIGN.md`. The refactor should stabilise the current `WorkspaceDocumentRail`/`DocumentDrawer` pair, smooth out interactions around collapse, hover, and peek states, and create space for near-term enhancements such as document presence indicators and activity signals.

## Background
- The current rail (`frontend/src/features/documents/components/WorkspaceDocumentRail.tsx` and `DocumentDrawer.tsx`) already exposes collapse/pin/search flows but the experience is rigid, mixes layout and data logic, and lacks a lightweight hover-preview state when collapsed.
- The prototype shared by the product team mirrors Vercel's sidebar: a narrow rail anchors to the left, clicking toggles a fully hidden state, and hovering over a trigger temporarily slides the full panel into view.
- We need to incorporate that sense of immediacy while staying faithful to our design baselines (Tailwind tokens, focus visibility, keyboard control) and keeping interactions deterministic for automated testing.

## Reference Pattern: VercelSidebar

### How the example works
- Tracks a local `isOn` boolean that toggles between a docked rail (`false`) and an off-canvas state (`true`) by applying negative margins (`-ml-[272px]`).
- Uses `twMerge` to compose Tailwind utility strings intelligently, preventing duplicate or conflicting classes across state transitions.
- Wraps the content in a `group` container and relies on Tailwind's `group-has[...]` variant (`:has()` under the hood) so hovering the `.sidebar-icon-trigger` or the floating overlay `.sidebar-wrapper` temporarily slides the panel into view.
- Separates the always-visible base rail from a floating hover overlay. The overlay only receives interactive styles when the rail is off-canvas and relevant group hover conditions are met.

### Techniques worth reusing
- Deterministic Tailwind class composition via a utility (`twMerge`, `clsx`, or our own helper) to avoid bloated class strings when toggling states.
- Layering: keep a slim base rail that anchors layout while a richer overlay provides the peek experience.
- Treat hover peek as additive to explicit collapse toggles; the button remains the primary control.

### Constraints for ADE
- `:has()` support is improving but not universal (Safari ≥ 15.4, Chromium ≥ 105, Firefox ≥ 121). We cannot rely on hover alone or break keyboard parity.
- Hover-only affordances fail accessibility expectations. All behaviour must be reachable through buttons and focus interactions with `aria-*` attributes.
- Styling should align with ADE tokens and primitives rather than bespoke utility strings. Long arbitrary-value Tailwind classes increase maintenance overhead.

### Recommended adaptation
- Keep explicit `collapsed` state persisted per workspace (as today) and add a transient `peek` state that mirrors both hover and focus events.
- Drive animations through `data-state="collapsed|expanded|peek"` attributes and Tailwind variants; optionally add `:has()` rules as progressive enhancement.
- Introduce a presentational `DocumentSidebar` component fed by dedicated hooks (`useDocumentSidebarState`, `useDocumentPins`) so logic stays testable and deterministic.
- Maintain deterministic behaviour for automated tests: treat peek as non-blocking (no focus trap, no fancy timers) and ensure transitions respect `prefers-reduced-motion`.

### Alternative approaches
- **CSS-only `:has()` hover peek**
  - Pros: minimal React code, purely declarative styling.
  - Cons: inconsistent browser support, difficult to mirror for keyboard users, and tricky focus management.
- **Event-driven peek (recommended)**
  - Pros: predictable, accessible, trivial to test, easy to disable with a feature flag.
  - Cons: adds a few handlers and additional state wiring.
- **Status quo (no peek)**
  - Pros: zero implementation risk.
  - Cons: misses product requirement for quick preview interactions.

## Desired Outcomes
- Reduce navigation friction so users can switch documents with minimal pointer travel or keyboard steps.
- Preserve explicit collapse/expand controls with `aria-expanded` semantics and per-workspace persistence.
- Add an optional hover/focus peek that reveals the full panel without breaking keyboard control or degrading accessibility.
- Keep presentation components focused on layout while data shaping, storage, and side effects live in hooks or services.

## Current ADE Sidebar Snapshot
- `WorkspaceDocumentRail.tsx` hands API shaping, pin persistence (`createScopedStorage`), and exposes props to the drawer.
- `DocumentDrawer.tsx` renders collapsed/expanded modes, search, pinning, error/loading states, and the collapse toggle.
- `WorkspaceLayout.tsx` owns the `drawerCollapsed` boolean and feeds it to `AppShell.sidebar`, which defines `width`/`collapsedWidth`.

### Observations
- Current interactions are deterministic, accessible, and JS-light—good foundations for the peek layer.
- Collapsed mode demands a click to expand; we must add peek without removing the explicit toggle.
- CSS transitions are already responsible for animation; keep the peek overlay CSS-driven to avoid layout jank.

## Recommended Architecture & Plan

### Implementation blueprint
1. **Extract state logic**
   - Add `useDocumentSidebarState(workspaceId)` to manage pins, query state, filters, `collapsed`, and the transient `peek` flag.
2. **Presentational component**
   - Create `frontend/src/features/documents/components/DocumentSidebar.tsx` with props for `collapsed`, `peekEnabled`, `peek`, handlers, and document collections. Render a base rail plus optional overlay using `data-state` attributes.
3. **Trigger semantics**
   - Provide an explicit toggle button with `aria-controls`/`aria-expanded` and clear copy (`Expand documents panel` / `Collapse documents panel`).
   - Use a hover/focus trigger zone that sets `peek=true` on enter/focus and resets on leave/blur so keyboard users receive the same preview.
4. **Styling**
   - Use ADE spacing/typography tokens. Sync widths with `AppShell.sidebar`. Respect `prefers-reduced-motion` by disabling transitions when requested.
5. **Fallbacks and flags**
   - Gate the hover preview behind a `peekEnabled` prop or feature flag. Optionally layer `:has()` selectors as progressive enhancement atop the event-driven approach.

### Implementation considerations
- Keep document data sourced through `useWorkspaceDocumentsQuery`; memoise shaping logic in the new hook.
- Extract pin persistence into `useDocumentPins(workspaceId)` to isolate storage concerns and simplify tests.
- Compose class names through a small helper (e.g., wrap `clsx` + `twMerge`) to avoid conflicts when toggling `data-state`.
- Use CSS feature detection or layered styles so `:has()` enhances but never replaces the event-based peek.
- Reuse shared UI primitives (inputs, buttons, badges) to stay aligned with `agents/FRONTEND_DESIGN.md`.
- Guard against focus traps: overlays should not capture focus unless they contain actionable controls.
- Update Vitest/RTL tests to cover filtering, pin toggles, collapse persistence, and hover/focus peek toggles. Expand Playwright coverage once the workspace shell suite lands.

## Example skeleton
```tsx
// frontend/src/features/documents/components/DocumentSidebar.tsx
import { useId } from "react";

export interface DocumentSidebarProps {
  collapsed: boolean;
  peekEnabled?: boolean;
  peek: boolean;
  onPeekChange: (value: boolean) => void;
  onToggleCollapse: () => void;
  // documents, handlers, loading/error flags passed through from the state hook
}

export function DocumentSidebar({
  collapsed,
  peekEnabled = true,
  peek,
  onPeekChange,
  onToggleCollapse,
}: DocumentSidebarProps) {
  const railId = useId();
  const state = collapsed ? (peek ? "peek" : "collapsed") : "expanded";

  return (
    <aside
      id={railId}
      aria-expanded={!collapsed}
      data-state={state}
      className="relative h-full"
    >
      {/* Base rail */}
      <div className="h-full transition-all data-[state=collapsed]:w-[72px] data-[state=expanded]:w-[280px]">
        <button
          type="button"
          aria-controls={railId}
          aria-expanded={!collapsed}
          onClick={onToggleCollapse}
          className="focus-ring"
        >
          <span className="sr-only">
            {collapsed ? "Expand documents panel" : "Collapse documents panel"}
          </span>
          {/* icon */}
        </button>
        {/* collapsed or expanded content */}
      </div>

      {/* Peek overlay (only when collapsed && peekEnabled) */}
      {peekEnabled && collapsed ? (
        <div
          role="dialog"
          aria-label="Documents"
          data-peek={peek}
          onMouseEnter={() => onPeekChange(true)}
          onMouseLeave={() => onPeekChange(false)}
          onFocus={() => onPeekChange(true)}
          onBlur={() => onPeekChange(false)}
          className="pointer-events-auto absolute left-0 top-0 z-20 h-full w-[280px] translate-x-[-8px] rounded-xl border bg-white shadow-lg transition-all data-[peek=false]:pointer-events-none data-[peek=false]:opacity-0 motion-reduce:transition-none"
        >
          {/* replicate expanded list content */}
        </div>
      ) : null}
    </aside>
  );
}
```

Wiring: `WorkspaceLayout` continues to own `collapsed` and persists it. The new state hook exposes `peek` setters that the trigger/overlay call. No backend changes required.

## Risks & Mitigations
- Hover-only affordance might hinder keyboard users → keep explicit collapse/expand button and mirror peek on focus.
- `:has()` variance across browsers → treat it as progressive enhancement; rely on event-driven peek for determinism.
- Focus loss when leaving overlay → ensure `onMouseLeave`/`onBlur` close peek and avoid trapping focus unless necessary.
- Conflicting state transitions → derive a single `data-state` source of truth to avoid divergence between collapse and peek.

## Guiding Goals
- Preserve the collapsible rail with existing localStorage persistence while introducing an optional hover preview.
- Separate presentation from data wiring: hooks manage state, a presentational component handles layout/animation, primitives provide consistent styling.
- Improve keyboard and screen-reader affordances (aria labels, role semantics, focus management).
- Keep styling deterministic and CSS-driven; avoid brittle timing hacks in JavaScript.
- Leave room for future enhancements (document presence, activity status) without rewrites.

## Acceptance Criteria
- **Accessibility**
  - Collapse/expand operable via keyboard with `aria-expanded`/`aria-controls`.
  - Hover peek mirrors with focus; the overlay never traps focus unintentionally.
  - Respects `prefers-reduced-motion`.
- **Behaviour**
  - Collapsed, expanded, and peek states render without layout shift; transitions are smooth and deterministic.
  - Collapse preference persists per workspace and hydrates on load.
  - Search/filter, pin/unpin, error/loading/empty states behave identically in peek and expanded modes.
- **Quality**
  - Unit tests cover pin persistence, filtering, collapse hydration, and peek toggles.
  - No new frontend dependencies without following the dependency protocol.
  - Basic cross-browser verification (latest Chrome, Firefox, Safari).

## Deliverables
- Refactored `WorkspaceDocumentRail` (state layer) plus a presentational sidebar component with hover-preview support.
- Updated CSS/Tailwind utilities or helper functions for deterministic class merging.
- Storybook/MDX demos (if available) for collapsed, expanded, hover-preview, loading, error, and empty states.
- Unit tests covering pin persistence, filtering, hover-preview toggles, and collapse state hydration.
- Developer notes in `frontend/README.md` documenting behaviour, accessibility expectations, and testing checklist.

## Milestones & Tasks
### M0 – Discovery & Alignment
1. Capture current UX gaps and constraints in this work package or `frontend/README.md` (collapsed flow, keyboard gaps, hover limitations).
2. Validate requirements with `agents/FRONTEND_DESIGN.md` and product stakeholders; confirm hover preview supplements explicit toggles.
3. Document minimum browser versions and plan fallbacks for missing `:has()` support.

### M1 – Structural Refactor
1. Extract data shaping into `useDocumentSidebarState(workspaceId)` returning documents, pins, loading/error flags, and handlers.
2. Split rendering into an accessible presentational component (`DocumentSidebar`) while keeping storage/query logic in hooks.
3. Add aria attributes, focus management, and keyboard controls; ensure the toggle honours `Space/Enter` and updates `aria-expanded`.

### M2 – Interaction Enhancements
1. Implement hover preview using the event-driven approach (with optional `group-has` progressive enhancement); expose a prop/flag to disable it.
2. Restore deterministic collapse persistence via scoped storage and hydrate state on load; guard against storage corruption.
3. Layer in reduced-motion handling and `:focus-visible` friendly outlines.

### M3 – Styling & Polish
1. Align spacing, typography, and colour tokens with Tailwind config; remove bespoke arbitrary utilities.
2. Add (or stub) status badges for documents (idle/processing/error) once metadata is available; gate behind a feature flag if data is pending.
3. Validate responsive behaviour (desktop baseline, tablet collapse, hidden on mobile) and document breakpoints.

### M4 – Testing & Documentation
1. Extend unit tests for pins, filters, collapse persistence, hover preview toggles, and error states.
2. Add interaction stories or visual regression coverage once the Storybook pipeline is available.
3. Update `frontend/README.md` (and this work package) with implementation notes, follow-ups, and QA checklists.

## Open Questions
- Should hover preview be enabled by default or controlled by a user preference?
- Do we need real-time presence indicators in the first iteration, or can we reserve space for future data?
- Can we reuse sidebar primitives for other features (configurations, jobs) to avoid duplicating interaction logic?

## Definition of Done
- Sidebar supports collapsed, expanded, and hover-preview modes with consistent keyboard and screen-reader behaviour.
- Document pins persist per workspace, survive reloads, and stay in sync with metadata when available.
- Filter/search, loading, error, and empty states are covered by Vitest, and manual QA confirms deterministic behaviour without layout shift.
- Design tokens and accessibility expectations in `agents/FRONTEND_DESIGN.md` remain satisfied; deviations are documented and approved.
- Work package updated with final notes and, once shipped, rotated into `agents/PREVIOUS_TASK.md`.
