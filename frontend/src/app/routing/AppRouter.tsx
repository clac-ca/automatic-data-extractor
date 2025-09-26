import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@app/layout/AppLayout";
import { RequireAuth } from "@app/routing/RequireAuth";
import { NotFoundPage } from "@pages/NotFoundPage";
import { SignInPage } from "@pages/SignInPage";
import { WorkspaceConfigurationsPage } from "@pages/WorkspaceConfigurationsPage";
import { WorkspaceDocumentsPage } from "@pages/WorkspaceDocumentsPage";
import { WorkspaceJobsPage } from "@pages/WorkspaceJobsPage";
import { WorkspaceOverviewPage } from "@pages/WorkspaceOverviewPage";
import { WorkspaceResultsPage } from "@pages/WorkspaceResultsPage";
import { WorkspaceSettingsPage } from "@pages/WorkspaceSettingsPage";
import { WorkspacesPage } from "@pages/WorkspacesPage";

export function AppRouter(): JSX.Element {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignInPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/workspaces" replace />} />
          <Route path="workspaces" element={<WorkspacesPage />} />
          <Route path="workspaces/:workspaceId/overview" element={<WorkspaceOverviewPage />} />
          <Route path="workspaces/:workspaceId/documents" element={<WorkspaceDocumentsPage />} />
          <Route path="workspaces/:workspaceId/jobs" element={<WorkspaceJobsPage />} />
          <Route path="workspaces/:workspaceId/results" element={<WorkspaceResultsPage />} />
          <Route path="workspaces/:workspaceId/configurations" element={<WorkspaceConfigurationsPage />} />
          <Route path="workspaces/:workspaceId/settings" element={<WorkspaceSettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
