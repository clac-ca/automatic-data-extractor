import type { ReactElement } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider, useAuth } from './context/AuthContext'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import './App.css'

function ProtectedRoute({ children }: { children: ReactElement }): ReactElement {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return children
}

function PublicRoute({ children }: { children: ReactElement }): ReactElement {
  const { user } = useAuth()
  if (user) {
    return <Navigate to="/" replace />
  }
  return children
}

function AppRoutes(): ReactElement {
  const { loading, error } = useAuth()

  if (loading) {
    return (
      <div className="app-loading" role="status" aria-live="polite">
        Checking session...
      </div>
    )
  }

  if (error) {
    return (
      <div className="app-error" role="alert" aria-live="assertive">
        {error}
      </div>
    )
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App(): ReactElement {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
