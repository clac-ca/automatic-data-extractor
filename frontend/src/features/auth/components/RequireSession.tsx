import type { JSX } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { Alert } from '../../../shared/components/Alert'
import { Button } from '../../../shared/components/Button'
import { Spinner } from '../../../shared/components/Spinner'
import { useSessionQuery } from '../hooks/useSessionQuery'

export function RequireSession(): JSX.Element {
  const location = useLocation()
  const sessionQuery = useSessionQuery()

  if (sessionQuery.isLoading || sessionQuery.isFetching) {
    return <Spinner label="Checking your session" />
  }

  if (sessionQuery.isError) {
    return (
      <div className="mx-auto max-w-lg py-12">
        <Alert variant="error" title="We hit a snag loading your session">
          <p className="mb-4 text-sm">
            {sessionQuery.error instanceof Error
              ? sessionQuery.error.message
              : 'Please retry or contact support if this continues.'}
          </p>
          <Button onClick={() => sessionQuery.refetch()}>Try again</Button>
        </Alert>
      </div>
    )
  }

  if (!sessionQuery.data) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    )
  }

  return <Outlet />
}
