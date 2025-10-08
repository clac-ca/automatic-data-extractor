import { clsx } from 'clsx'
import type { JSX, ReactNode } from 'react'

interface AlertProps {
  variant?: 'info' | 'warning' | 'error' | 'success'
  title?: string
  children?: ReactNode
}

const variantStyles: Record<Required<AlertProps>['variant'], string> = {
  info: 'border-blue-200 bg-blue-50 text-blue-900',
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
  error: 'border-red-200 bg-red-50 text-red-900',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
}

export function Alert({
  variant = 'info',
  title,
  children,
}: AlertProps): JSX.Element {
  return (
    <div
      className={clsx(
        'rounded-lg border px-4 py-3 text-sm shadow-sm',
        variantStyles[variant],
      )}
      role={variant === 'error' ? 'alert' : 'status'}
    >
      {title && <h4 className="font-semibold">{title}</h4>}
      {children && <div className="mt-2 text-sm leading-5">{children}</div>}
    </div>
  )
}
