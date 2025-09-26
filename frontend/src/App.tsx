import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { RequireAuth } from "./components/RequireAuth";
import { WorkspaceDocumentsPage } from "./pages/WorkspaceDocumentsPage";
import { WorkspaceListPage } from "./pages/WorkspaceListPage";
import { WorkspaceOverviewPage } from "./pages/WorkspaceOverviewPage";
import { SignInPage } from "./pages/SignInPage";

function ProtectedRoutes() {
  return (
    <RequireAuth>
      <Outlet />
    </RequireAuth>
  );
}

export function App() {
  return (
    <AppLayout>
      <Routes>
        <Route element={<ProtectedRoutes />}>
          <Route path="/" element={<Navigate to="/workspaces" replace />} />
          <Route path="/workspaces" element={<WorkspaceListPage />} />
          <Route
            path="/workspaces/:workspaceId"
            element={<WorkspaceOverviewPage />}
          />
          <Route
            path="/workspaces/:workspaceId/documents"
            element={<WorkspaceDocumentsPage />}
          />
        </Route>
        <Route path="/sign-in" element={<SignInPage />} />
        <Route path="*" element={<Navigate to="/workspaces" replace />} />
      </Routes>
    </AppLayout>
  );
}
