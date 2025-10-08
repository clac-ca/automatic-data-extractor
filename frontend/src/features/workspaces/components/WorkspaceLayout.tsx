import { useMemo } from 'react'
import { Link, NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { clsx } from 'clsx'

import { Button } from '../../../shared/components/Button'
import { Spinner } from '../../../shared/components/Spinner'
import { useLocalStorage } from '../../../shared/hooks/useLocalStorage'
import { useSessionQuery } from '../../auth/hooks/useSessionQuery'
import { useWorkspacesQuery } from '../hooks/useWorkspaces'

export function WorkspaceLayout(): JSX.Element {
  const { workspaceId, documentTypeId } = useParams()
  const navigate = useNavigate()
  const session = useSessionQuery()
  const workspacesQuery = useWorkspacesQuery()
  const [isCollapsed, setIsCollapsed] = useLocalStorage('ade-nav-collapsed', false)

  const currentWorkspace = useMemo(() => {
    return workspacesQuery.data?.find(
      (workspace) => workspace.workspace_id === workspaceId,
    )
  }, [workspaceId, workspacesQuery.data])

  if (workspacesQuery.isLoading) {
    return <Spinner label="Loading workspaces" />
  }

  if (workspacesQuery.isError) {
    return (
      <div className="p-8">
        <p className="text-sm text-red-600">
          We were unable to load your workspaces. Please refresh the page.
        </p>
      </div>
    )
  }

  const workspaces = workspacesQuery.data ?? []

  if (!workspaces.length) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50">
        <h1 className="text-2xl font-semibold text-slate-900">
          No workspaces yet
        </h1>
        <p className="max-w-md text-center text-sm text-slate-600">
          Contact an administrator to be assigned to a workspace or create one
          using the ADE CLI.
        </p>
        <Button onClick={() => navigate('/logout')} variant="secondary">
          Sign out
        </Button>
      </div>
    )
  }

  const documentTypes = currentWorkspace?.document_types ?? []

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside
        className={clsx(
          'flex flex-col border-r border-slate-200 bg-white transition-all duration-200',
          isCollapsed ? 'w-20' : 'w-72',
        )}
      >
        <div className="flex items-center justify-between px-4 py-4">
          <Link to="/workspaces" className="text-sm font-semibold tracking-wide">
            ADE Console
          </Link>
          <button
            type="button"
            className="rounded-md p-2 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            {isCollapsed ? '»' : '«'}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-6">
          <p className="px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Workspaces
          </p>
          <nav className="mt-2 space-y-1">
            {workspaces.map((workspace) => (
              <NavLink
                key={workspace.workspace_id}
                to={`/workspaces/${workspace.workspace_id}`}
                className={({ isActive }) =>
                  clsx(
                    'block rounded-md px-3 py-2 text-sm font-medium transition',
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900',
                  )
                }
              >
                {workspace.name}
              </NavLink>
            ))}
          </nav>

          {documentTypes.length > 0 && (
            <div className="mt-8">
              <p className="px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Document types
              </p>
              <nav className="mt-2 space-y-1">
                {documentTypes.map((doc) => (
                  <NavLink
                    key={doc.id}
                    to={`/workspaces/${workspaceId}/document-types/${doc.id}`}
                    className={({ isActive }) =>
                      clsx(
                        'block rounded-md px-3 py-2 text-sm transition',
                        isActive
                          ? 'bg-slate-900 text-white'
                          : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900',
                      )
                    }
                  >
                    {doc.display_name}
                  </NavLink>
                ))}
              </nav>
            </div>
          )}
        </div>
        <div className="border-t border-slate-200 px-4 py-4 text-xs text-slate-500">
          Signed in as
          <p className="truncate text-sm font-medium text-slate-900">
            {session.data?.user.email}
          </p>
          <Link
            to="/logout"
            className="mt-2 inline-flex text-xs font-semibold text-primary hover:underline"
          >
            Sign out
          </Link>
        </div>
      </aside>

      <main className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-5">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">
              Workspace
            </p>
            <h1 className="text-xl font-semibold text-slate-900">
              {currentWorkspace?.name ?? 'Workspace'}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="secondary" size="sm" onClick={() => navigate('/workspaces')}>
              Overview
            </Button>
            {documentTypeId && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate(`/workspaces/${workspaceId}`)}
              >
                Back to workspace
              </Button>
            )}
          </div>
        </header>
        <section className="flex-1 overflow-y-auto px-8 py-8">
          <Outlet />
        </section>
      </main>
    </div>
  )
}
