import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { InitialSetupPayload, UserProfile } from '../../api/types'
import LoginPage from '../LoginPage'

const mockLogin = vi.fn<Promise<UserProfile>, [string, string]>()
const mockCompleteInitialSetup = vi.fn<Promise<UserProfile>, [InitialSetupPayload]>()
const mockNavigate = vi.fn()
const mockCheckInitialSetupStatus = vi.fn<Promise<boolean>, []>()

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    error: null,
    login: mockLogin,
    logout: vi.fn(),
    completeInitialSetup: mockCompleteInitialSetup,
    checkInitialSetupStatus: mockCheckInitialSetupStatus,
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('LoginPage', () => {
  beforeEach(() => {
    mockLogin.mockReset()
    mockCompleteInitialSetup.mockReset()
    mockNavigate.mockReset()
    mockCheckInitialSetupStatus.mockReset()
    mockCheckInitialSetupStatus.mockResolvedValue(false)
  })

  it('validates required form fields before attempting login', async () => {
    const user = userEvent.setup()
    render(<LoginPage />)

    await screen.findByRole('button', { name: /sign in/i })

    const submitButton = screen.getByRole('button', { name: /sign in/i })
    await user.click(submitButton)

    expect(screen.getByText('Email is required.')).toBeInTheDocument()
    expect(screen.getByText('Password is required.')).toBeInTheDocument()
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('surfaces server errors when login fails', async () => {
    const user = userEvent.setup()
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'))

    render(<LoginPage />)

    await screen.findByRole('button', { name: /sign in/i })

    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Password'), 'Password123!')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Invalid credentials')).toBeInTheDocument()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('trims email input before sending credentials and navigates on success', async () => {
    const user = userEvent.setup()
    mockLogin.mockResolvedValueOnce({
      user_id: '123',
      email: 'user@example.com',
      role: 'admin',
      is_active: true,
    })

    render(<LoginPage />)

    await screen.findByRole('button', { name: /sign in/i })

    await user.type(screen.getByLabelText('Email'), '  user@example.com  ')
    await user.type(screen.getByLabelText('Password'), 'Password123!')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(mockLogin).toHaveBeenCalledWith('user@example.com', 'Password123!')
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('renders the initial setup form when setup is required and submits values', async () => {
    const user = userEvent.setup()
    mockCheckInitialSetupStatus.mockResolvedValueOnce(true)
    mockCompleteInitialSetup.mockResolvedValueOnce({
      user_id: 'abc',
      email: 'owner@example.com',
      role: 'admin',
      is_active: true,
    })

    render(<LoginPage />)

    await screen.findByRole('button', { name: /create administrator/i })

    await user.type(screen.getByLabelText('Email'), 'owner@example.com')
    await user.type(screen.getByLabelText('Display name (optional)'), 'Owner  ')
    await user.type(screen.getByLabelText('Password'), 'Password123!')
    await user.type(screen.getByLabelText('Confirm password'), 'Password123!')
    await user.click(screen.getByRole('button', { name: /create administrator/i }))

    expect(mockCompleteInitialSetup).toHaveBeenCalledWith({
      email: 'owner@example.com',
      password: 'Password123!',
      displayName: 'Owner',
    })
    expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('falls back to the login form when setup completion returns a conflict', async () => {
    const user = userEvent.setup()
    mockCheckInitialSetupStatus.mockResolvedValueOnce(true)
    const conflictError = Object.assign(new Error('Already configured'), { status: 409 })
    mockCompleteInitialSetup.mockRejectedValueOnce(conflictError)

    render(<LoginPage />)

    await screen.findByRole('button', { name: /create administrator/i })

    await user.type(screen.getByLabelText('Email'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'Password123!')
    await user.type(screen.getByLabelText('Confirm password'), 'Password123!')
    await user.click(screen.getByRole('button', { name: /create administrator/i }))

    expect(await screen.findByText('Initial setup is already complete. Please sign in.')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows a status message when setup status cannot be loaded', async () => {
    mockCheckInitialSetupStatus.mockRejectedValueOnce(new Error('status failed'))

    render(<LoginPage />)

    expect(
      await screen.findByText('Unable to determine setup status. Please try signing in.'),
    ).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })
})
