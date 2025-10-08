import { Navigate } from 'react-router-dom'

import { Alert } from '../../../shared/components/Alert'
import { Spinner } from '../../../shared/components/Spinner'
import { useSessionQuery } from '../../auth/hooks/useSessionQuery'
import { useWorkspacesQuery } from '../hooks/useWorkspaces'

export function WorkspaceRedirect(): JSX.Element {
  const session = useSessionQuery()
  const workspaces = useWorkspacesQuery()

  if (session.isLoading || workspaces.isLoading) {
    return <Spinner label="Loading workspaces" />
  }

  if (session.isError || workspaces.isError) {
    return (
      <Alert variant="error" title="Unable to load workspaces">
        Please refresh the page and try again.
      </Alert>
    )
  }

  const preferredId = session.data?.user.preferred_workspace_id
  const available = workspaces.data ?? []
  const defaultWorkspace =
    available.find((workspace) => workspace.workspace_id === preferredId)?.workspace_id ??
    available[0]?.workspace_id

  if (!defaultWorkspace) {
    return (
      <Alert variant="info" title="No workspace assignments">
        You are not assigned to any workspaces yet. Contact an administrator for
        access.
      </Alert>
    )
  }

  return <Navigate to={`/workspaces/${defaultWorkspace}`} replace />
}
