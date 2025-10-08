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
      <label
        htmlFor={htmlFor}
        className="text-sm font-medium text-slate-900"
      >
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
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
