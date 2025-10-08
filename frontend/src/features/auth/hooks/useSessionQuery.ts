import { QueryClient, useQuery } from '@tanstack/react-query'

import { ApiError } from '../../../shared/api/client'
import { queryKeys } from '../../../shared/api/query-keys'
import { SessionEnvelope } from '../../../shared/api/types'
import { fetchSession } from '../api'

export function useSessionQuery() {
  return useQuery<SessionEnvelope | null>({
    queryKey: queryKeys.session,
    queryFn: async () => {
      try {
        return await fetchSession()
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          return null
        }
        throw error
      }
    },
    staleTime: 60_000,
  })
}

export function setSessionQueryData(
  client: QueryClient,
  session: SessionEnvelope | null,
) {
  client.setQueryData(queryKeys.session, session)
}
