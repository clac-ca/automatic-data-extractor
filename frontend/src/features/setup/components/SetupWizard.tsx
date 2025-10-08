import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { ApiError } from '../../../shared/api/client'
import { queryKeys } from '../../../shared/api/query-keys'
import { Alert } from '../../../shared/components/Alert'
import { Button } from '../../../shared/components/Button'
import { Card } from '../../../shared/components/Card'
import { FormField } from '../../../shared/components/FormField'
import { Input } from '../../../shared/components/Input'
import { Spinner } from '../../../shared/components/Spinner'
import { SetupRequest, SessionEnvelope } from '../../../shared/api/types'
import { useAuthProviders } from '../../auth/hooks/useAuthProviders'
import { setSessionQueryData } from '../../auth/hooks/useSessionQuery'
import { fetchSetupStatus, submitSetup } from '../api'
import { useSetupStatusQuery } from '../hooks/useSetupStatusQuery'

const adminSchema = z
  .object({
    displayName: z.string().min(1, 'Display name is required'),
    email: z.string().email('Enter a valid email'),
    password: z
      .string()
      .min(12, 'Password must be at least 12 characters')
      .regex(/\d/, 'Password must include a number')
      .regex(/[A-Z]/, 'Password must include an uppercase letter'),
    confirmPassword: z.string().min(1, 'Confirm your password'),
  })
  .refine((value) => value.password === value.confirmPassword, {
    path: ['confirmPassword'],
    message: 'Passwords must match',
  })

type AdminFormValues = z.infer<typeof adminSchema>

type SetupStep = 'welcome' | 'administrator' | 'confirmation'

export function SetupWizard(): JSX.Element {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const setupStatus = useSetupStatusQuery()
  const providersQuery = useAuthProviders()
  const [step, setStep] = useState<SetupStep>('welcome')
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<AdminFormValues>({
    defaultValues: {
      displayName: '',
      email: '',
      password: '',
      confirmPassword: '',
    },
  })

  useEffect(() => {
    if (!setupStatus.data?.requires_setup && step !== 'confirmation') {
      navigate('/login', { replace: true })
    }
  }, [navigate, setupStatus.data?.requires_setup, step])

  const setupMutation = useMutation<SessionEnvelope, ApiError, SetupRequest>({
    mutationFn: (payload) => submitSetup(payload),
    onSuccess: (session) => {
      setSessionQueryData(queryClient, session)
      queryClient.setQueryData(queryKeys.setupStatus, {
        requires_setup: false,
        completed_at: new Date().toISOString(),
      })
      setStep('confirmation')
      setFormError(null)
    },
    onError: async (error) => {
      if (error.status === 409) {
        await queryClient.fetchQuery(queryKeys.setupStatus, fetchSetupStatus)
        setFormError('Setup is already complete. Please sign in instead.')
        setStep('welcome')
        return
      }
      if (error.problem?.errors) {
        Object.entries(error.problem.errors).forEach(([field, messages]) => {
          const key = field as keyof AdminFormValues
          form.setError(key, {
            type: 'server',
            message: messages.join(', '),
          })
        })
      }
      setFormError(
        error.problem?.detail ||
          'We could not create the administrator. Please try again.',
      )
    },
  })

  const forceSso = providersQuery.data?.force_sso ?? false

  const providerCount = providersQuery.data?.providers.length ?? 0

  const welcomeCopy = useMemo(() => {
    if (forceSso && providerCount > 0) {
      return (
        <p className="text-sm text-slate-600">
          Configure the first administrator using a break-glass credential.
          Afterwards team members will authenticate with SSO.
        </p>
      )
    }
    return (
      <p className="text-sm text-slate-600">
        We just need an administrator to finish provisioning ADE. You can add
        more users once setup is complete.
      </p>
    )
  }, [forceSso, providerCount])

  if (setupStatus.isLoading) {
    return <Spinner label="Checking setup status" />
  }

  if (setupStatus.isError) {
    return (
      <div className="mx-auto max-w-lg py-12">
        <Alert variant="error" title="Unable to determine setup state">
          <p className="mb-4 text-sm">
            {setupStatus.error instanceof Error
              ? setupStatus.error.message
              : 'Please retry in a moment.'}
          </p>
          <Button onClick={() => setupStatus.refetch()}>Retry</Button>
        </Alert>
      </div>
    )
  }

  if (!setupStatus.data?.requires_setup && step !== 'confirmation') {
    return <Spinner label="Redirecting to login" />
  }

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    const parsed = adminSchema.safeParse(values)
    if (!parsed.success) {
      form.clearErrors()
      parsed.error.issues.forEach((issue) => {
        const field = issue.path[0] as keyof AdminFormValues
        form.setError(field, {
          type: 'validation',
          message: issue.message,
        })
      })
      return
    }

    const payload: SetupRequest = {
      email: parsed.data.email,
      password: parsed.data.password,
      display_name: parsed.data.displayName,
    }

    setupMutation.mutate(payload)
  })

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 py-12">
      <header className="space-y-2 text-center">
        <h1 className="text-3xl font-semibold text-slate-900">ADE setup</h1>
        <p className="text-sm text-slate-600">
          Step {step === 'welcome' ? 1 : step === 'administrator' ? 2 : 3} of 3
        </p>
      </header>

      {formError && <Alert variant="error">{formError}</Alert>}

      {step === 'welcome' && (
        <Card title="Welcome" description="Prepare your administrator">
          {welcomeCopy}
          <div className="mt-6 flex justify-end">
            <Button onClick={() => setStep('administrator')}>Begin setup</Button>
          </div>
        </Card>
      )}

      {step === 'administrator' && (
        <Card
          title="Administrator"
          description="Create credentials for the first administrator"
        >
          {forceSso && (
            <Alert variant="info" title="SSO will be enforced after setup">
              During setup you will create a single break-glass account. Once
              complete, everyone will sign in using your SSO provider.
            </Alert>
          )}
          <form
            className="mt-6 space-y-6"
            noValidate
            onSubmit={onSubmit}
          >
            <FormField
              label="Display name"
              htmlFor="displayName"
              required
              error={form.formState.errors.displayName?.message ?? null}
            >
              <Input
                id="displayName"
                autoFocus
                {...form.register('displayName')}
                error={form.formState.errors.displayName?.message ?? null}
              />
            </FormField>

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
              description="Minimum 12 characters including a number and uppercase letter"
              error={form.formState.errors.password?.message ?? null}
            >
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                {...form.register('password')}
                error={form.formState.errors.password?.message ?? null}
              />
            </FormField>

            <FormField
              label="Confirm password"
              htmlFor="confirmPassword"
              required
              error={
                form.formState.errors.confirmPassword?.message ?? null
              }
            >
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                {...form.register('confirmPassword')}
                error={form.formState.errors.confirmPassword?.message ?? null}
              />
            </FormField>

            <div className="flex justify-between">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setStep('welcome')}
              >
                Back
              </Button>
              <Button type="submit" isLoading={setupMutation.isPending}>
                Create administrator
              </Button>
            </div>
          </form>
        </Card>
      )}

      {step === 'confirmation' && (
        <Card
          title="You're all set"
          description="Your administrator account is ready."
        >
          <p className="text-sm text-slate-600">
            We sent you to the workspace hub. Use the navigation to invite your
            team and start processing documents.
          </p>
          <div className="mt-6 flex justify-end">
            <Button onClick={() => navigate('/workspaces')}>Enter ADE</Button>
          </div>
        </Card>
      )}
    </div>
  )
}
