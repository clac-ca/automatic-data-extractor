import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FormEvent, ReactElement } from 'react'

import { useAuth } from '../context/AuthContext'

interface FieldErrors {
  email?: string
  password?: string
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

export default function LoginPage(): ReactElement {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const errors: FieldErrors = {
      email: validateEmail(email),
      password: validatePassword(password),
    }

    setFieldErrors(errors)
    if (errors.email || errors.password) {
      return
    }

    setIsSubmitting(true)
    setFormError(null)
    try {
      await login(email.trim(), password)
      navigate('/', { replace: true })
    } catch (error) {
      if (error instanceof Error) {
        setFormError(error.message)
      } else {
        setFormError('Unexpected error while signing in.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <header className="auth-header">
          <h1>Automatic Data Extractor</h1>
          <p className="auth-subtitle">Sign in to manage your document pipeline.</p>
        </header>
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="form-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              aria-invalid={Boolean(fieldErrors.email)}
              aria-describedby={fieldErrors.email ? 'email-error' : undefined}
              required
            />
            {fieldErrors.email ? (
              <p className="field-error" id="email-error" role="alert">
                {fieldErrors.email}
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
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby={fieldErrors.password ? 'password-error' : undefined}
              required
            />
            {fieldErrors.password ? (
              <p className="field-error" id="password-error" role="alert">
                {fieldErrors.password}
              </p>
            ) : null}
          </div>

          {formError ? (
            <div className="form-error" role="alert" aria-live="assertive">
              {formError}
            </div>
          ) : null}

          <button className="auth-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  )
}
