import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import DashboardPage from '../DashboardPage'

const mockLogout = vi.fn<Promise<void>, []>()

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      user_id: 'user-1',
      email: 'user@example.com',
      role: 'admin',
      is_active: true,
    },
    logout: mockLogout,
  }),
}))

describe('DashboardPage', () => {
  beforeEach(() => {
    mockLogout.mockReset()
  })

  it('renders the authenticated user details', () => {
    render(<DashboardPage />)

    expect(screen.getByText('Welcome back')).toBeInTheDocument()
    expect(screen.getByText('user@example.com')).toBeInTheDocument()
    expect(screen.getByText('user-1')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('attempts to sign out when the button is pressed', async () => {
    const user = userEvent.setup()
    mockLogout.mockResolvedValueOnce()

    render(<DashboardPage />)

    await user.click(screen.getByRole('button', { name: /sign out/i }))
    expect(mockLogout).toHaveBeenCalled()
  })

  it('displays an error when sign out fails', async () => {
    const user = userEvent.setup()
    mockLogout.mockRejectedValueOnce(new Error('Logout failed'))

    render(<DashboardPage />)

    await user.click(screen.getByRole('button', { name: /sign out/i }))

    expect(await screen.findByText('Logout failed')).toBeInTheDocument()
  })
})
