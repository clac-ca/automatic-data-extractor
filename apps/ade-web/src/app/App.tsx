import { NavProvider, useLocation } from "@app/nav/history";

import { AppProviders } from "./AppProviders";
import HomeScreen from "@screens/Home";
import LoginScreen from "@screens/Login";
import AuthCallbackScreen from "@screens/AuthCallback";
import SetupScreen from "@screens/Setup";
import WorkspacesScreen from "@screens/Workspaces";
import WorkspaceCreateScreen from "@screens/Workspaces/New";
import WorkspaceScreen from "@screens/Workspace";
import DocumentsV3Screen from "@screens/DocumentsV3";
import DocumentsV4Screen from "@screens/DocumentsV4";
import DocumentsV5Screen from "@screens/DocumentsV5";
import DocumentsV6Screen from "@screens/DocumentsV6";
import DocumentsV7Screen from "@screens/DocumentsV7";
import DocumentsV8Screen from "@screens/DocumentsV8";
import DocumentsV9Screen from "@screens/DocumentsV9";
import DocumentsV10Screen from "@screens/DocumentsV10";
import LogoutScreen from "@screens/Logout";
import NotFoundScreen from "@screens/NotFound";

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
    case "documents-v3":
      return <DocumentsV3Screen />;
    case "documents-v4":
      return <DocumentsV4Screen />;
    case "documents-v5":
      return <DocumentsV5Screen />;
    case "documents-v6":
      return <DocumentsV6Screen />;
    case "documents-v7":
      return <DocumentsV7Screen />;
    case "documents-v8":
      return <DocumentsV8Screen />;
    case "documents-v9":
      return <DocumentsV9Screen />;
    case "documents-v10":
      return <DocumentsV10Screen />;
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
