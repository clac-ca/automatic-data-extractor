import { useEffect } from 'react'
import type { JSX } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { queryKeys } from '../../../shared/api/query-keys'
import { Spinner } from '../../../shared/components/Spinner'
import { deleteSession } from '../api'

export function LogoutRoute(): JSX.Element {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  useEffect(() => {
    const performLogout = async () => {
      try {
        await deleteSession()
      } catch (error) {
        console.warn('Failed to delete session', error)
      } finally {
        queryClient.setQueryData(queryKeys.session, null)
        navigate('/login', { replace: true })
      }
    }

    void performLogout()
  }, [navigate, queryClient])

  return <Spinner label="Signing you out" />
}
