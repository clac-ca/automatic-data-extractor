import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '../../../shared/api/query-keys'
import { fetchSetupStatus } from '../api'

export function useSetupStatusQuery() {
  return useQuery({
    queryKey: queryKeys.setupStatus,
    queryFn: fetchSetupStatus,
    staleTime: 30_000,
  })
}
