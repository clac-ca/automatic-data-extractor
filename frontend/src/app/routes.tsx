import { Suspense, lazy, type ReactElement } from "react";
import type { RouteObject } from "react-router-dom";

import { LoadingState } from "@/components/layout";
import { AppShell, ProtectedLayout } from "@/app/layouts/AppShell";
import { AuthenticatedLayout } from "@/app/layouts/AuthenticatedLayout";
import { PublicLayout } from "@/app/layouts/PublicLayout";

const HomeScreen = lazy(() => import("@/pages/Home"));
const LoginScreen = lazy(() => import("@/pages/Login"));
const LogoutScreen = lazy(() => import("@/pages/Logout"));
const NotFoundScreen = lazy(() => import("@/pages/NotFound"));
const SetupScreen = lazy(() => import("@/pages/Setup"));
const WorkspaceScreen = lazy(() => import("@/pages/Workspace"));
const WorkspaceCreateScreen = lazy(() => import("@/pages/Workspaces/New"));
const WorkspacesScreen = lazy(() => import("@/pages/Workspaces"));

function withRouteSuspense(element: ReactElement) {
  return (
    <Suspense
      fallback={<LoadingState title="Loading page" className="min-h-full bg-background" />}
    >
      {element}
    </Suspense>
  );
}

export const appRoutes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { path: "login", element: withRouteSuspense(<LoginScreen />) },
          { path: "logout", element: withRouteSuspense(<LogoutScreen />) },
          { path: "setup", element: withRouteSuspense(<SetupScreen />) },
        ],
      },
      {
        element: <ProtectedLayout />,
        children: [
          {
            element: <AuthenticatedLayout />,
            children: [
              { index: true, element: withRouteSuspense(<HomeScreen />) },
              { path: "workspaces", element: withRouteSuspense(<WorkspacesScreen />) },
              { path: "workspaces/new", element: withRouteSuspense(<WorkspaceCreateScreen />) },
              { path: "*", element: withRouteSuspense(<NotFoundScreen />) },
            ],
          },
          { path: "workspaces/:workspaceId/*", element: withRouteSuspense(<WorkspaceScreen />) },
        ],
      },
    ],
  },
];
