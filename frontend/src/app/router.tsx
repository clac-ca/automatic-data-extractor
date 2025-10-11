import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router-dom";

import { AppErrorPage } from "./AppErrorPage";
import { NotFoundRoute } from "./NotFoundRoute";
import { RootRoute } from "./RootRoute";
import { rootLoader } from "./loaders/rootLoader";
import { adminRoutes } from "../features/admin/routes";
import { authRoutes } from "../features/auth/routes";
import { setupRoutes } from "../features/setup/routes";
import { workspaceRoutes } from "../features/workspaces/routes";

function withDefaultErrorElement(route: RouteObject): RouteObject {
  const next: RouteObject = {
    ...route,
    errorElement: route.errorElement ?? <AppErrorPage />,
  };

  if (route.children) {
    next.children = route.children.map(withDefaultErrorElement);
  }

  return next;
}

export function createAppRouter() {
  const routes: RouteObject[] = [
    { path: "/", element: <RootRoute />, loader: rootLoader },
    ...setupRoutes,
    ...authRoutes,
    ...adminRoutes,
    ...workspaceRoutes,
    { path: "*", element: <NotFoundRoute /> },
  ].map(withDefaultErrorElement);

  return createBrowserRouter(routes);
}

const router = createAppRouter();

export function AppRouter() {
  return <RouterProvider router={router} />;
}
