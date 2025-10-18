import { index, layout, route, type RouteConfig } from "@react-router/dev/routes";

// NOTE: The project relies on file-based routes under src/app/routes/**.
// This manifest mirrors that structure so the React Router plugin can
// evaluate the tree without reintroducing legacy AppRouter components.
export default [
  route("login", "routes/login/route.tsx"),
  route("setup", "routes/setup/route.tsx"),
  route("auth/callback", "routes/auth/callback/route.tsx"),
  layout("routes/app/route.tsx", [
    index("routes/_index/route.tsx"),
    route("workspaces", "routes/workspaces/route.tsx", [
      index("routes/workspaces/_index/route.tsx"),
      route("new", "routes/workspaces/new/route.tsx"),
      route(":workspaceId", "routes/workspaces/$workspaceId/route.tsx", [
        index("routes/workspaces/$workspaceId/_index/route.tsx"),
        route("documents", "routes/workspaces/$workspaceId/documents/route.tsx", [
          index("routes/workspaces/$workspaceId/documents/_index/route.tsx"),
          route(":documentId", "routes/workspaces/$workspaceId/documents/$documentId/route.tsx"),
        ]),
        route("configurations", "routes/workspaces/$workspaceId/configurations/_index/route.tsx"),
        route("jobs", "routes/workspaces/$workspaceId/jobs/_index/route.tsx"),
        route("settings", "routes/workspaces/$workspaceId/settings/_index/route.tsx"),
      ]),
    ]),
  ]),
  route("*", "routes/not-found/route.tsx"),
] satisfies RouteConfig;

