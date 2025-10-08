import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { queryKeys } from '../../../../shared/api/query-keys'
import { SessionEnvelope } from '../../../../shared/api/types'
import { createTestQueryClient, renderWithQueryClient } from '../../../../test/test-utils'
import * as setupApi from '../../api'
import { SetupWizard } from '../SetupWizard'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('SetupWizard', () => {
  it('validates administrator form fields', async () => {
    const client = createTestQueryClient()
    client.setQueryData(queryKeys.setupStatus, {
      requires_setup: true,
      completed_at: null,
    })
    client.setQueryData(queryKeys.providers, { providers: [], force_sso: false })

    renderWithQueryClient(
      <MemoryRouter initialEntries={['/setup']}>
        <Routes>
          <Route path="/setup" element={<SetupWizard />} />
        </Routes>
      </MemoryRouter>,
      client,
    )

    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /begin setup/i }))
    await user.click(
      screen.getByRole('button', { name: /create administrator/i }),
    )

    expect(await screen.findByText('Display name is required')).toBeInTheDocument()
  })

  it('completes setup and shows confirmation on success', async () => {
    const client = createTestQueryClient()
    client.setQueryData(queryKeys.setupStatus, {
      requires_setup: true,
      completed_at: null,
    })
    client.setQueryData(queryKeys.providers, { providers: [], force_sso: false })

    const session: SessionEnvelope = {
      user: {
        user_id: 'admin-1',
        email: 'admin@example.com',
        role: 'admin',
        is_active: true,
        is_service_account: false,
      },
      expires_at: null,
      refresh_expires_at: null,
    }

    vi.spyOn(setupApi, 'submitSetup').mockResolvedValue(session)

    renderWithQueryClient(
      <MemoryRouter initialEntries={['/setup']}>
        <Routes>
          <Route path="/setup" element={<SetupWizard />} />
        </Routes>
      </MemoryRouter>,
      client,
    )

    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /begin setup/i }))

    await user.type(screen.getByLabelText(/display name/i), 'Administrator')
    await user.type(screen.getByLabelText(/email/i), 'admin@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'Password1234')
    await user.type(screen.getByLabelText(/confirm password/i), 'Password1234')

    await user.click(
      screen.getByRole('button', { name: /create administrator/i }),
    )

    await waitFor(() => {
      expect(
        screen.getByText("You're all set", { exact: false }),
      ).toBeInTheDocument()
    })

    expect(client.getQueryData(queryKeys.session)).toEqual(session)
  })
})
