import { describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { screen } from '@testing-library/react'

import { queryKeys } from '../../../../shared/api/query-keys'
import { createTestQueryClient, renderWithQueryClient } from '../../../../test/test-utils'
import { RequireSession } from '../RequireSession'

function renderWithRoutes(initialPath: string, session: unknown) {
  const client = createTestQueryClient()
  client.setQueryData(queryKeys.session, session)
  const wrapper = (
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<RequireSession />}>
          <Route path="/secure" element={<div>Secure</div>} />
        </Route>
        <Route path="/login" element={<div>Login</div>} />
      </Routes>
    </MemoryRouter>
  )

  return renderWithQueryClient(wrapper, client)
}

describe('RequireSession', () => {
  it('redirects to login when no session is present', () => {
    renderWithRoutes('/secure', null)
    expect(screen.getByText('Login')).toBeInTheDocument()
  })

  it('renders child routes when a session exists', () => {
    renderWithRoutes('/secure', {
      user: {
        user_id: 'u1',
        email: 'user@example.com',
        role: 'admin',
        is_active: true,
        is_service_account: false,
      },
      expires_at: null,
      refresh_expires_at: null,
    })

    expect(screen.getByText('Secure')).toBeInTheDocument()
  })
})
