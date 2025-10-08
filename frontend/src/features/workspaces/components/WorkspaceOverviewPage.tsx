import { useMemo } from 'react'
import type { JSX } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Alert } from '../../../shared/components/Alert'
import { Button } from '../../../shared/components/Button'
import { Card } from '../../../shared/components/Card'
import { Spinner } from '../../../shared/components/Spinner'
import { useWorkspacesQuery, useWorkspaceQuery } from '../hooks/useWorkspaces'

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function WorkspaceOverviewPage(): JSX.Element {
  const navigate = useNavigate()
  const { workspaceId } = useParams()
  const workspacesQuery = useWorkspacesQuery()
  const workspaceQuery = useWorkspaceQuery(workspaceId)

  const documentTypes = useMemo(
    () => workspaceQuery.data?.document_types ?? [],
    [workspaceQuery.data?.document_types],
  )

  if (workspaceQuery.isLoading || workspacesQuery.isLoading) {
    return <Spinner label="Loading workspace" />
  }

  if (workspaceQuery.isError || !workspaceQuery.data) {
    return (
      <Alert variant="error" title="Workspace unavailable">
        We could not load the workspace details. Please refresh the page.
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      <Card
        title="Workspace summary"
        description="Latest activity and membership info"
      >
        <dl className="grid gap-6 sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Workspace name
            </dt>
            <dd className="mt-1 text-sm font-semibold text-slate-900">
              {workspaceQuery.data.name}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Your role
            </dt>
            <dd className="mt-1 text-sm font-semibold text-slate-900">
              {workspaceQuery.data.role}
            </dd>
          </div>
        </dl>
      </Card>

      <Card
        title="Document types"
        description="Monitor extraction health and access configurations"
      >
        {documentTypes.length === 0 ? (
          <Alert variant="info" title="No document types yet">
            Publish a document type configuration to see it here.
          </Alert>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {documentTypes.map((doc) => (
              <div
                key={doc.id}
                className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-slate-900">
                      {doc.display_name}
                    </h3>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      Status: {doc.status}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                    {doc.pending_jobs ?? 0} pending
                  </span>
                </div>
                <dl className="mt-4 space-y-2 text-sm text-slate-600">
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-slate-500">
                      Last run
                    </dt>
                    <dd className="mt-1">
                      {doc.last_run_at
                        ? dateFormatter.format(new Date(doc.last_run_at))
                        : 'No runs yet'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-slate-500">
                      Success rate (7d)
                    </dt>
                    <dd className="mt-1">
                      {typeof doc.success_rate_7d === 'number'
                        ? `${Math.round(doc.success_rate_7d * 100)}%`
                        : 'Not enough data'}
                    </dd>
                  </div>
                </dl>
                <div className="mt-4 flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() =>
                      navigate(
                        `/workspaces/${workspaceId}/document-types/${doc.id}`,
                      )
                    }
                  >
                    View details
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
