import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { ApiError } from '../../../shared/api/client'
import { queryKeys } from '../../../shared/api/query-keys'
import { Alert } from '../../../shared/components/Alert'
import { Button } from '../../../shared/components/Button'
import { Card } from '../../../shared/components/Card'
import { FormField } from '../../../shared/components/FormField'
import { Input } from '../../../shared/components/Input'
import { Spinner } from '../../../shared/components/Spinner'
import { useSetupStatusQuery } from '../../setup/hooks/useSetupStatusQuery'
import { useAuthProviders } from '../hooks/useAuthProviders'
import { useLoginMutation } from '../hooks/useLoginMutation'
import { useSessionQuery } from '../hooks/useSessionQuery'

const loginSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

type LoginFormValues = z.infer<typeof loginSchema>

export function LoginPage(): JSX.Element {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const redirectTo = useMemo(() => {
    const state = location.state as { from?: string } | undefined
    return state?.from ?? '/workspaces'
  }, [location.state])

  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<LoginFormValues>({
    defaultValues: { email: '', password: '' },
  })

  const sessionQuery = useSessionQuery()
  const providersQuery = useAuthProviders()
  const setupStatus = useSetupStatusQuery()
  const loginMutation = useLoginMutation()

  useEffect(() => {
    if (setupStatus.data?.requires_setup) {
      navigate('/setup', { replace: true })
    }
  }, [navigate, setupStatus.data?.requires_setup])

  useEffect(() => {
    if (sessionQuery.data) {
      navigate(redirectTo, { replace: true })
    }
  }, [navigate, redirectTo, sessionQuery.data])

  const forceSso = providersQuery.data?.force_sso ?? false

  const handleSubmit = form.handleSubmit((values) => {
    setFormError(null)
    const parsed = loginSchema.safeParse(values)
    if (!parsed.success) {
      form.clearErrors()
      parsed.error.issues.forEach((issue) => {
        const field = issue.path[0] as keyof LoginFormValues
        form.setError(field, {
          type: 'validation',
          message: issue.message,
        })
      })
      return
    }

    loginMutation.mutate(parsed.data, {
      onSuccess: () => {
        queryClient.invalidateQueries(queryKeys.providers)
        navigate(redirectTo, { replace: true })
      },
      onError: (error: ApiError) => {
        if (error.problem?.errors) {
          Object.entries(error.problem.errors).forEach(([field, messages]) => {
            const key = field as keyof LoginFormValues
            form.setError(key, {
              type: 'server',
              message: messages.join(', '),
            })
          })
        }
        setFormError(
          error.problem?.detail ||
            'We could not sign you in. Check your credentials and try again.',
        )
      },
    })
  })

  if (setupStatus.isLoading || sessionQuery.isLoading) {
    return <Spinner label="Preparing login" />
  }

  if (sessionQuery.data) {
    return <Spinner label="Redirecting" />
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-8 py-16">
      <header className="text-center">
        <h1 className="text-3xl font-semibold text-slate-900">Sign in</h1>
        <p className="mt-2 text-sm text-slate-600">
          Access your workspaces and monitor document processing.
        </p>
      </header>

      {formError && <Alert variant="error">{formError}</Alert>}

      <Card title="Use your credentials">
        {forceSso ? (
          <div className="space-y-4">
            <Alert variant="info" title="Single sign-on required">
              Your organisation enforces SSO for sign in. Continue to your
              identity provider to begin.
            </Alert>
            <div className="grid gap-3 sm:grid-cols-2">
              {providersQuery.data?.providers.map((provider) => (
                <a
                  key={provider.id}
                  href={provider.start_url}
                  className="flex items-center justify-center rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-900 shadow-sm transition hover:border-primary hover:text-primary"
                >
                  {provider.label}
                </a>
              ))}
            </div>
            <p className="text-xs text-slate-500">
              Need help? Contact your administrator.
            </p>
          </div>
        ) : (
          <form className="space-y-6" noValidate onSubmit={handleSubmit}>
            <FormField
              label="Email"
              htmlFor="email"
              required
              error={form.formState.errors.email?.message ?? null}
            >
              <Input
                id="email"
                type="email"
                autoComplete="email"
                {...form.register('email')}
                error={form.formState.errors.email?.message ?? null}
              />
            </FormField>

            <FormField
              label="Password"
              htmlFor="password"
              required
              error={form.formState.errors.password?.message ?? null}
            >
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...form.register('password')}
                error={form.formState.errors.password?.message ?? null}
              />
            </FormField>

            <Button type="submit" isLoading={loginMutation.isPending}>
              Sign in
            </Button>
          </form>
        )}
      </Card>

      {!forceSso && providersQuery.data?.providers.length ? (
        <Card title="Or continue with SSO">
          <div className="grid gap-3 sm:grid-cols-2">
            {providersQuery.data.providers.map((provider) => (
              <a
                key={provider.id}
                href={provider.start_url}
                className="flex items-center justify-center rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-900 shadow-sm transition hover:border-primary hover:text-primary"
              >
                {provider.label}
              </a>
            ))}
          </div>
        </Card>
      ) : null}

      <div className="text-center text-xs text-slate-500">
        Having trouble? <Link to="mailto:support@example.com">Contact support</Link>
      </div>
    </div>
  )
}
