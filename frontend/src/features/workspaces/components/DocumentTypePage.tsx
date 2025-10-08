import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { Alert } from '../../../shared/components/Alert'
import { Button } from '../../../shared/components/Button'
import { Card } from '../../../shared/components/Card'
import { Drawer } from '../../../shared/components/Drawer'
import { Spinner } from '../../../shared/components/Spinner'
import {
  useConfigurationQuery,
  useDocumentTypeQuery,
} from '../hooks/useWorkspaces'

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function DocumentTypePage(): JSX.Element {
  const { workspaceId, documentTypeId } = useParams()
  const [isDrawerOpen, setDrawerOpen] = useState(false)
  const documentTypeQuery = useDocumentTypeQuery(workspaceId, documentTypeId)
  const activeConfigurationId = documentTypeQuery.data?.active_configuration_id
  const configurationQuery = useConfigurationQuery(
    isDrawerOpen ? activeConfigurationId ?? undefined : undefined,
  )

  useEffect(() => {
    if (isDrawerOpen && activeConfigurationId) {
      void configurationQuery.refetch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDrawerOpen, activeConfigurationId])

  const alertSummary = useMemo(() => {
    return documentTypeQuery.data?.recent_alerts ?? []
  }, [documentTypeQuery.data?.recent_alerts])

  if (documentTypeQuery.isLoading) {
    return <Spinner label="Loading document type" />
  }

  if (documentTypeQuery.isError || !documentTypeQuery.data) {
    return (
      <Alert variant="error" title="Document type unavailable">
        We could not find the document type you selected.
      </Alert>
    )
  }

  const documentType = documentTypeQuery.data

  return (
    <div className="space-y-6">
      <Card title={documentType.display_name}>
        <dl className="grid gap-6 sm:grid-cols-3">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Status
            </dt>
            <dd className="mt-1 text-sm font-semibold text-slate-900">
              {documentType.status}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Last run
            </dt>
            <dd className="mt-1 text-sm font-semibold text-slate-900">
              {documentType.last_run_at
                ? dateFormatter.format(new Date(documentType.last_run_at))
                : 'No runs yet'}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Pending jobs
            </dt>
            <dd className="mt-1 text-sm font-semibold text-slate-900">
              {documentType.pending_jobs ?? 0}
            </dd>
          </div>
        </dl>
        <div className="mt-6 flex items-center gap-3">
          <Button onClick={() => setDrawerOpen(true)}>Review configuration</Button>
          <Button variant="ghost">View history</Button>
        </div>
      </Card>

      <Card title="Alerts" description="Recent notices requiring attention">
        {alertSummary.length === 0 ? (
          <p className="text-sm text-slate-600">No alerts in the last 7 days.</p>
        ) : (
          <ul className="space-y-3">
            {alertSummary.map((alert) => (
              <li key={alert.id} className="rounded-md border border-slate-200 p-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-900">
                    {alert.title}
                  </h3>
                  <span className="text-xs uppercase tracking-wide text-slate-500">
                    {alert.level}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  {dateFormatter.format(new Date(alert.occurred_at))}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Drawer
        title="Configuration overview"
        isOpen={isDrawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {configurationQuery.isLoading ? (
          <Spinner label="Loading configuration" />
        ) : configurationQuery.data ? (
          <div className="space-y-6">
            <section>
              <h3 className="text-sm font-semibold text-slate-900">Overview</h3>
              <p className="mt-2 text-sm text-slate-600">
                Version {configurationQuery.data.version}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Published by {configurationQuery.data.published_by ?? 'Unknown'} on{' '}
                {configurationQuery.data.published_at
                  ? dateFormatter.format(
                      new Date(configurationQuery.data.published_at),
                    )
                  : 'Not published'}
              </p>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-slate-900">Inputs</h3>
              {configurationQuery.data.inputs?.length ? (
                <ul className="mt-2 space-y-2 text-sm text-slate-600">
                  {configurationQuery.data.inputs.map((input) => (
                    <li
                      key={input.name}
                      className="rounded-md border border-slate-200 px-3 py-2"
                    >
                      <p className="font-medium text-slate-900">{input.name}</p>
                      <p className="text-xs uppercase tracking-wide text-slate-500">
                        {input.type}
                      </p>
                      {input.description && (
                        <p className="mt-1 text-xs text-slate-500">
                          {input.description}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-slate-600">
                  No inputs defined for this configuration.
                </p>
              )}
            </section>
          </div>
        ) : (
          <Alert variant="warning">Configuration details not available.</Alert>
        )}
      </Drawer>
    </div>
  )
}
