import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '../../../shared/api/query-keys'
import { ProviderDiscoveryResponse } from '../../../shared/api/types'
import { fetchAuthProviders } from '../api'

export function useAuthProviders() {
  return useQuery<ProviderDiscoveryResponse>({
    queryKey: queryKeys.providers,
    queryFn: fetchAuthProviders,
    staleTime: 5 * 60_000,
  })
}
