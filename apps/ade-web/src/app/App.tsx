import { NavProvider, useLocation } from "@app/nav/history";

import { AppProviders } from "./AppProviders";
import HomeScreen from "@pages/Home";
import LoginScreen from "@pages/Login";
import AuthCallbackScreen from "@pages/AuthCallback";
import SetupScreen from "@pages/Setup";
import WorkspacesScreen from "@pages/Workspaces";
import WorkspaceCreateScreen from "@pages/Workspaces/New";
import WorkspaceScreen from "@pages/Workspace";
import DocumentsScreen from "@pages/Documents";
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
  const segments = normalized.split("/").filter(Boolean);

  if (segments.length === 0) {
    return <HomeScreen />;
  }

  const [first, second] = segments;

  switch (first) {
    case "login":
      return <LoginScreen />;
    case "logout":
      return <LogoutScreen />;
    case "auth":
      if (second === "callback") {
        return <AuthCallbackScreen />;
      }
      break;
    case "setup":
      return <SetupScreen />;
    case "workspaces":
      if (!second) {
        return <WorkspacesScreen />;
      }
      if (second === "new") {
        return <WorkspaceCreateScreen />;
      }
      return <WorkspaceScreen />;
    case "documents":
      return <DocumentsScreen />;
    default:
      break;
  }

  return <NotFoundScreen />;
}

export function normalizePathname(pathname: string) {
  if (!pathname || pathname === "/") {
    return "/";
  }
  return pathname.endsWith("/") && pathname.length > 1 ? pathname.slice(0, -1) : pathname;
}

export default App;
