import { useState } from 'react'
import type { ReactElement } from 'react'

import { useAuth } from '../context/AuthContext'

export default function DashboardPage(): ReactElement {
  const { user, logout } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [isSigningOut, setIsSigningOut] = useState(false)

  if (!user) {
    return <main className="auth-screen" />
  }

  const handleSignOut = async () => {
    setIsSigningOut(true)
    setError(null)
    try {
      await logout()
    } catch (exception) {
      if (exception instanceof Error) {
        setError(exception.message)
      } else {
        setError('Unexpected error while signing out.')
      }
    } finally {
      setIsSigningOut(false)
    }
  }

  return (
    <main className="dashboard">
      <section className="dashboard-card">
        <h1>Welcome back</h1>
        <p className="dashboard-copy">
          Signed in as <span className="dashboard-email">{user.email}</span>
        </p>
        <dl className="dashboard-details">
          <div>
            <dt>User ID</dt>
            <dd>{user.user_id}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{user.role}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{user.is_active ? 'Active' : 'Disabled'}</dd>
          </div>
        </dl>
        {error ? (
          <div className="form-error" role="alert" aria-live="assertive">
            {error}
          </div>
        ) : null}
        <button className="auth-submit" type="button" onClick={handleSignOut} disabled={isSigningOut}>
          {isSigningOut ? 'Signing out...' : 'Sign out'}
        </button>
      </section>
    </main>
  )
}
