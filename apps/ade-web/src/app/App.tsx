import { NavProvider, useLocation } from "@app/navigation/history";
import { normalizePathname } from "@app/navigation/paths";

import { AppProviders } from "@app/providers/AppProviders";
import { RequireSession } from "@components/providers/auth/RequireSession";
import HomeScreen from "@pages/Home";
import LoginScreen from "@pages/Login";
import AuthCallbackScreen from "@pages/AuthCallback";
import SetupScreen from "@pages/Setup";
import WorkspacesScreen from "@pages/Workspaces";
import WorkspaceCreateScreen from "@pages/Workspaces/New";
import WorkspaceScreen from "@pages/Workspace";
import LogoutScreen from "@pages/Logout";
import NotFoundScreen from "@pages/NotFound";

export function App() {
  return (
    <NavProvider>
      <AppProviders>
        <ScreenSwitch />
      </AppProviders>
    </NavProvider>
  );
}

export function ScreenSwitch() {
  const location = useLocation();
  const normalized = normalizePathname(location.pathname);
  const match = resolveRoute(normalized);

  if (!match.requiresSession) {
    return match.element;
  }

  return <RequireSession>{match.element}</RequireSession>;
}

type RouteMatch = {
  readonly element: JSX.Element;
  readonly requiresSession: boolean;
};

function resolveRoute(pathname: string): RouteMatch {
  const segments = pathname.split("/").filter(Boolean);
  const [first, second] = segments;

  if (segments.length === 0) {
    return { element: <HomeScreen />, requiresSession: true };
  }

  switch (first) {
    case "login":
      return { element: <LoginScreen />, requiresSession: false };
    case "logout":
      return { element: <LogoutScreen />, requiresSession: false };
    case "auth":
      if (second === "callback") {
        return { element: <AuthCallbackScreen />, requiresSession: false };
      }
      break;
    case "setup":
      return { element: <SetupScreen />, requiresSession: false };
    case "workspaces":
      if (!second) {
        return { element: <WorkspacesScreen />, requiresSession: true };
      }
      if (second === "new") {
        return { element: <WorkspaceCreateScreen />, requiresSession: true };
      }
      return { element: <WorkspaceScreen />, requiresSession: true };
    default:
      break;
  }

  return { element: <NotFoundScreen />, requiresSession: true };
}

export default App;
