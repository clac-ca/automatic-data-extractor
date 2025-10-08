# Next Core Frontend Milestone: Workspace Top Bar

## Objective
Deliver the shared top bar defined in the frontend spec so every authenticated view exposes product identity, workspace switching, and session controls. The current `WorkspaceLayout` renders only a navigation rail and page header, leaving the top bar absent from the shell experience. 【F:agents/FRONTEND_DESIGN.md†L46-L48】【F:frontend/src/features/workspaces/components/WorkspaceLayout.tsx†L40-L120】

## Deliverables
1. **Structural layout** — Compose a `TopBar` child component within `WorkspaceLayout` that renders the product logo/name, workspace selector, user menu trigger, and connection status indicator using the existing Tailwind utility patterns. 【F:agents/FRONTEND_DESIGN.md†L46-L48】
2. **Workspace selector** — Bind a standard select/listbox UI to `useWorkspacesQuery`, defaulting to the active workspace and navigating to the chosen workspace route on change. Keep server state in TanStack Query and avoid bespoke global stores. 【F:agents/FRONTEND_DESIGN.md†L70-L83】
3. **Session menu** — Surface a keyboard-accessible menu driven by `useSessionQuery` that exposes profile details and a sign-out control wired to the `/logout` route. Reuse shared button/menu primitives where available to stay consistent with the rest of the app. 【F:agents/FRONTEND_DESIGN.md†L52-L56】
4. **Connectivity indicator** — Reflect online/offline status using React Query's `onlineManager` or the browser `navigator.onLine` API so operators immediately see connectivity changes. 【F:agents/FRONTEND_DESIGN.md†L46-L48】
5. **Interaction tests** — Add React Testing Library coverage for workspace switching, menu focus management, and connectivity badge rendering inside `features/workspaces/components/__tests__`.

## Implementation Approach
- Encapsulate top bar concerns in `features/workspaces/components/TopBar.tsx` plus focused subcomponents (`TopBarWorkspaceSelect`, `TopBarSessionMenu`) so logic stays co-located with the workspace feature.
- Lean on existing hooks (`useSessionQuery`, `useWorkspacesQuery`) and React Router navigation to respect established data flow patterns.
- Use semantic elements (`header`, `nav`, `button`) with ARIA attributes for accessibility, following the app's existing Tailwind-first styling conventions.
- Keep side effects minimal: local component state only for transient UI concerns (menu visibility) and delegate persistence to existing query caches.
- Update `WorkspaceLayout` tests if they assume the previous structure, ensuring snapshots or queries target role-based selectors rather than implementation details.
