import {
  Navigate,
  Outlet,
  RouterProvider,
  createBrowserRouter,
} from 'react-router-dom'

import { LoginPage } from '../features/auth/components/LoginPage'
import { LogoutRoute } from '../features/auth/components/LogoutRoute'
import { RequireSession } from '../features/auth/components/RequireSession'
import { SetupWizard } from '../features/setup/components/SetupWizard'
import { DocumentTypePage } from '../features/workspaces/components/DocumentTypePage'
import { WorkspaceLayout } from '../features/workspaces/components/WorkspaceLayout'
import { WorkspaceOverviewPage } from '../features/workspaces/components/WorkspaceOverviewPage'
import { WorkspaceRedirect } from '../features/workspaces/components/WorkspaceRedirect'

function RootLayout(): JSX.Element {
  return <Outlet />
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <Navigate to="/workspaces" replace /> },
      { path: 'setup', element: <SetupWizard /> },
      { path: 'login', element: <LoginPage /> },
      {
        path: 'workspaces',
        element: <RequireSession />,
        children: [
          { index: true, element: <WorkspaceRedirect /> },
          {
            path: ':workspaceId',
            element: <WorkspaceLayout />,
            children: [
              { index: true, element: <WorkspaceOverviewPage /> },
              {
                path: 'document-types/:documentTypeId',
                element: <DocumentTypePage />,
              },
            ],
          },
        ],
      },
      { path: 'logout', element: <LogoutRoute /> },
      { path: '*', element: <Navigate to="/workspaces" replace /> },
    ],
  },
])

export function AppRouter(): JSX.Element {
  return <RouterProvider router={router} />
}
