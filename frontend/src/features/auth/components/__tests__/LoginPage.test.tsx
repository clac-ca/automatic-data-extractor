import { describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { queryKeys } from '../../../../shared/api/query-keys'
import { createTestQueryClient, renderWithQueryClient } from '../../../../test/test-utils'
import { LoginPage } from '../LoginPage'

describe('LoginPage', () => {
  it('validates email and password inputs', async () => {
    const client = createTestQueryClient()
    client.setQueryData(queryKeys.session, null)
    client.setQueryData(queryKeys.providers, { providers: [], force_sso: false })
    client.setQueryData(queryKeys.setupStatus, {
      requires_setup: false,
      completed_at: null,
    })

    renderWithQueryClient(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>,
      client,
    )

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Enter a valid email')).toBeInTheDocument()
    expect(screen.getByText('Password is required')).toBeInTheDocument()
  })

  it('hides the credential form when SSO is required', () => {
    const client = createTestQueryClient()
    client.setQueryData(queryKeys.session, null)
    client.setQueryData(queryKeys.setupStatus, {
      requires_setup: false,
      completed_at: null,
    })
    client.setQueryData(queryKeys.providers, {
      force_sso: true,
      providers: [
        { id: 'entra', label: 'Entra ID', start_url: '/login/entra', icon_url: null },
      ],
    })

    renderWithQueryClient(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>,
      client,
    )

    expect(screen.getByText(/single sign-on required/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Entra ID' })).toHaveAttribute(
      'href',
      '/login/entra',
    )
  })
})
