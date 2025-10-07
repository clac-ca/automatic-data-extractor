import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FormEvent, ReactElement } from 'react'

import type { InitialSetupPayload } from '../api/types'
import type { ApiError } from '../api/errors'
import { useAuth } from '../context/AuthContext'

type AuthView = 'loading' | 'setup' | 'login'

type LoginFieldErrors = {
  email?: string
  password?: string
}

type SetupFieldErrors = LoginFieldErrors & {
  confirmPassword?: string
}

function validateEmail(value: string): string | undefined {
  const trimmed = value.trim()
  if (!trimmed) {
    return 'Email is required.'
  }
  const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!pattern.test(trimmed)) {
    return 'Enter a valid email address.'
  }
  return undefined
}

function validatePassword(value: string): string | undefined {
  if (!value.trim()) {
    return 'Password is required.'
  }
  return undefined
}

function validatePasswordConfirmation(password: string, confirmation: string): string | undefined {
  if (!confirmation.trim()) {
    return 'Confirm the password to continue.'
  }
  if (password !== confirmation) {
    return 'Passwords must match.'
  }
  return undefined
}

interface LockoutDetails {
  lockedUntil: string
  failedAttempts: number
  retryAfterSeconds?: number
}

function formatLockoutTimestamp(value: string): string {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) {
    return value
  }
  return timestamp.toLocaleString()
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return 'a few moments'
  }
  if (seconds < 60) {
    return `${seconds} second${seconds === 1 ? '' : 's'}`
  }
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? '' : 's'}`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `${hours} hour${hours === 1 ? '' : 's'}`
  }
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'}`
}

interface InitialSetupFormProps {
  onSubmit: (payload: InitialSetupPayload) => Promise<void>
  onAlreadyConfigured: () => void
}

function InitialSetupForm({ onSubmit, onAlreadyConfigured }: InitialSetupFormProps): ReactElement {
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState<SetupFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const errors: SetupFieldErrors = {
      email: validateEmail(email),
      password: validatePassword(password),
      confirmPassword: validatePasswordConfirmation(password, confirmPassword),
    }

    setFieldErrors(errors)
    if (errors.email || errors.password || errors.confirmPassword) {
      return
    }

    setIsSubmitting(true)
    setFormError(null)
    const payload: InitialSetupPayload = {
      email: email.trim(),
      password,
    }
    const cleanedDisplayName = displayName.trim()
    if (cleanedDisplayName) {
      payload.displayName = cleanedDisplayName
    }

    try {
      await onSubmit(payload)
    } catch (error) {
      const problem = error as ApiError
      if (problem.status === 409) {
        onAlreadyConfigured()
        return
      }
      const message = problem.message?.trim() || 'Unable to create the administrator account.'
      setFormError(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="form-field">
        <label htmlFor="setup-email">Email</label>
        <input
          id="setup-email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? 'setup-email-error' : undefined}
          required
        />
        {fieldErrors.email ? (
          <p className="field-error" id="setup-email-error" role="alert">
            {fieldErrors.email}
          </p>
        ) : null}
      </div>

      <div className="form-field">
        <label htmlFor="display-name">Display name (optional)</label>
        <input
          id="display-name"
          name="displayName"
          type="text"
          autoComplete="name"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />
      </div>

      <div className="form-field">
        <label htmlFor="setup-password">Password</label>
        <input
          id="setup-password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={Boolean(fieldErrors.password)}
          aria-describedby={fieldErrors.password ? 'setup-password-error' : undefined}
          required
        />
        {fieldErrors.password ? (
          <p className="field-error" id="setup-password-error" role="alert">
            {fieldErrors.password}
          </p>
        ) : null}
      </div>

      <div className="form-field">
        <label htmlFor="setup-password-confirm">Confirm password</label>
        <input
          id="setup-password-confirm"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          aria-invalid={Boolean(fieldErrors.confirmPassword)}
          aria-describedby={fieldErrors.confirmPassword ? 'setup-confirm-error' : undefined}
          required
        />
        {fieldErrors.confirmPassword ? (
          <p className="field-error" id="setup-confirm-error" role="alert">
            {fieldErrors.confirmPassword}
          </p>
        ) : null}
      </div>

      {formError ? (
        <div className="form-error" role="alert" aria-live="assertive">
          {formError}
        </div>
      ) : null}

      <button className="auth-submit" type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Creating account...' : 'Create administrator'}
      </button>
    </form>
  )
}

export default function LoginPage(): ReactElement {
  const navigate = useNavigate()
  const {
    login,
    completeInitialSetup,
    checkInitialSetupStatus,
  } = useAuth()

  const [view, setView] = useState<AuthView>('loading')
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginFieldErrors, setLoginFieldErrors] = useState<LoginFieldErrors>({})
  const [loginFormError, setLoginFormError] = useState<string | null>(null)
  const [lockoutDetails, setLockoutDetails] = useState<LockoutDetails | null>(null)
  const [loginSubmitting, setLoginSubmitting] = useState(false)

  const isMountedRef = useRef(true)
  useEffect(() => () => {
    isMountedRef.current = false
  }, [])

  const refreshSetupStatus = useCallback(
    async (options?: { preserveMessage?: boolean }) => {
      try {
        const required = await checkInitialSetupStatus()
        if (!isMountedRef.current) {
          return required
        }
        setView(required ? 'setup' : 'login')
        if (!options?.preserveMessage) {
          setStatusMessage(null)
        }
        return required
      } catch (error) {
        if (!isMountedRef.current) {
          throw error
        }
        if (!options?.preserveMessage) {
          setStatusMessage('Unable to determine setup status. Please try signing in.')
        }
        setView('login')
        throw error
      }
    },
    [checkInitialSetupStatus],
  )

  useEffect(() => {
    void refreshSetupStatus().catch(() => undefined)
  }, [refreshSetupStatus])

  const handleLoginSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const errors: LoginFieldErrors = {
      email: validateEmail(loginEmail),
      password: validatePassword(loginPassword),
    }
    setLoginFieldErrors(errors)
    if (errors.email || errors.password) {
      return
    }

    setLoginSubmitting(true)
    setLoginFormError(null)
    setLockoutDetails(null)
    try {
      await login(loginEmail.trim(), loginPassword)
      navigate('/', { replace: true })
    } catch (error) {
      const problem = error as ApiError
      setLoginFormError(problem.message || 'Unexpected error while signing in.')
      if (
        problem.status === 403 &&
        typeof problem.lockedUntil === 'string' &&
        typeof problem.failedAttempts === 'number'
      ) {
        setLockoutDetails({
          lockedUntil: problem.lockedUntil,
          failedAttempts: problem.failedAttempts,
          retryAfterSeconds:
            typeof problem.retryAfterSeconds === 'number'
              ? Math.max(Math.trunc(problem.retryAfterSeconds), 0)
              : undefined,
        })
      } else {
        setLockoutDetails(null)
      }
    } finally {
      setLoginSubmitting(false)
    }
  }

  const handleInitialSetupSubmit = useCallback(
    async (payload: InitialSetupPayload) => {
      await completeInitialSetup(payload)
      navigate('/', { replace: true })
    },
    [completeInitialSetup, navigate],
  )

  const handleInitialSetupAlreadyConfigured = useCallback(() => {
    void refreshSetupStatus({ preserveMessage: true }).catch(() => undefined)
    if (isMountedRef.current) {
      setStatusMessage('Initial setup is already complete. Please sign in.')
    }
  }, [refreshSetupStatus])

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <header className="auth-header">
          <h1>Automatic Data Extractor</h1>
          <p className="auth-subtitle">Sign in to manage your document pipeline.</p>
        </header>

        {view === 'loading' ? (
          <div className="auth-loading" role="status" aria-live="polite">
            Checking system status...
          </div>
        ) : (
          <>
            {statusMessage ? (
              <div className="form-error" role="alert" aria-live="assertive">
                {statusMessage}
              </div>
            ) : null}

            {view === 'setup' ? (
              <InitialSetupForm
                onSubmit={handleInitialSetupSubmit}
                onAlreadyConfigured={handleInitialSetupAlreadyConfigured}
              />
            ) : (
              <form className="auth-form" onSubmit={handleLoginSubmit} noValidate>
                <div className="form-field">
                  <label htmlFor="email">Email</label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    value={loginEmail}
                    onChange={(event) => setLoginEmail(event.target.value)}
                    aria-invalid={Boolean(loginFieldErrors.email)}
                    aria-describedby={loginFieldErrors.email ? 'email-error' : undefined}
                    required
                  />
                  {loginFieldErrors.email ? (
                    <p className="field-error" id="email-error" role="alert">
                      {loginFieldErrors.email}
                    </p>
                  ) : null}
                </div>

                <div className="form-field">
                  <label htmlFor="password">Password</label>
                  <input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    value={loginPassword}
                    onChange={(event) => setLoginPassword(event.target.value)}
                    aria-invalid={Boolean(loginFieldErrors.password)}
                    aria-describedby={loginFieldErrors.password ? 'password-error' : undefined}
                    required
                  />
                  {loginFieldErrors.password ? (
                    <p className="field-error" id="password-error" role="alert">
                      {loginFieldErrors.password}
                    </p>
                  ) : null}
                </div>

                {loginFormError ? (
                  <div className="form-error" role="alert" aria-live="assertive">
                    {loginFormError}
                  </div>
                ) : null}

                {lockoutDetails ? (
                  <div className="form-hint" role="note" aria-live="polite">
                    <p>
                      Account unlocks at{' '}
                      <strong>{formatLockoutTimestamp(lockoutDetails.lockedUntil)}</strong>.
                    </p>
                    <p>Failed attempts recorded: {lockoutDetails.failedAttempts}.</p>
                    {typeof lockoutDetails.retryAfterSeconds === 'number' ? (
                      <p>
                        Please wait about {formatDuration(lockoutDetails.retryAfterSeconds)} before trying again.
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <button className="auth-submit" type="submit" disabled={loginSubmitting}>
                  {loginSubmitting ? 'Signing in...' : 'Sign in'}
                </button>
              </form>
            )}
          </>
        )}
      </section>
    </main>
  )
}
