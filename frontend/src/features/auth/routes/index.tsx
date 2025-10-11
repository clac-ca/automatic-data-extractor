import type { RouteObject } from "react-router-dom";
import { LoginRoute } from "./LoginRoute";
import { LogoutRoute } from "./LogoutRoute";
import { SsoCallbackRoute } from "./SsoCallbackRoute";
import { RequireNoSession, RequireSetupComplete } from "../../../app/guards";

const loginPending = (
  <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
    Preparing sign-in…
  </div>
);

export const authRoutes: RouteObject[] = [
  {
    path: "/login",
    element: (
      <RequireSetupComplete pending={loginPending}>
        <RequireNoSession pending={loginPending} />
      </RequireSetupComplete>
    ),
    children: [{ index: true, element: <LoginRoute /> }],
  },
  { path: "/logout", element: <LogoutRoute /> },
  { path: "/auth/callback", element: <SsoCallbackRoute /> },
];
