import type { RouteObject } from "react-router-dom";

import { AppShell, ProtectedLayout } from "@/app/layouts/AppShell";
import { AuthenticatedLayout } from "@/app/layouts/AuthenticatedLayout";
import { PublicLayout } from "@/app/layouts/PublicLayout";
import HomeScreen from "@/pages/Home";
import LoginScreen from "@/pages/Login";
import SetupScreen from "@/pages/Setup";
import WorkspacesScreen from "@/pages/Workspaces";
import WorkspaceCreateScreen from "@/pages/Workspaces/New";
import WorkspaceScreen from "@/pages/Workspace";
import LogoutScreen from "@/pages/Logout";
import NotFoundScreen from "@/pages/NotFound";

export const appRoutes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { path: "login", element: <LoginScreen /> },
          { path: "logout", element: <LogoutScreen /> },
          { path: "setup", element: <SetupScreen /> },
        ],
      },
      {
        element: <ProtectedLayout />,
        children: [
          {
            element: <AuthenticatedLayout />,
            children: [
              { index: true, element: <HomeScreen /> },
              { path: "workspaces", element: <WorkspacesScreen /> },
              { path: "workspaces/new", element: <WorkspaceCreateScreen /> },
              { path: "*", element: <NotFoundScreen /> },
            ],
          },
          { path: "workspaces/:workspaceId/*", element: <WorkspaceScreen /> },
        ],
      },
    ],
  },
];
