import { useMutation, useQueryClient } from '@tanstack/react-query'

import { ApiError } from '../../../shared/api/client'
import { queryKeys } from '../../../shared/api/query-keys'
import type { LoginRequest, SessionEnvelope } from '../../../shared/api/types'
import { createSession } from '../api'

export function useLoginMutation() {
  const queryClient = useQueryClient()

  return useMutation<SessionEnvelope, ApiError, LoginRequest>({
    mutationFn: (payload) => createSession(payload),
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.session, session)
    },
  })
}
