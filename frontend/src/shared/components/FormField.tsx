import { clsx } from 'clsx'

interface FormFieldProps {
  label: string
  htmlFor: string
  required?: boolean
  description?: string
  error?: string | null
  children: React.ReactNode
}

export function FormField({
  label,
  htmlFor,
  required,
  description,
  error,
  children,
}: FormFieldProps): JSX.Element {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1">
        <label htmlFor={htmlFor} className="text-sm font-medium text-slate-900">
          {label}
        </label>
        {required && (
          <span aria-hidden="true" className="text-sm font-medium text-red-500">
            *
          </span>
        )}
      </div>
      {description && (
        <p className="text-xs text-slate-500" id={`${htmlFor}-description`}>
          {description}
        </p>
      )}
      {children}
      {error && (
        <p
          className={clsx(
            'text-sm text-red-600',
            description && '-mt-1',
          )}
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  )
}
