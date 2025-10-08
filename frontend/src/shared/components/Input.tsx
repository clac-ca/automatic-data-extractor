import { forwardRef } from 'react'
import { clsx } from 'clsx'

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string | null
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, ...rest }, ref) => (
    <input
      ref={ref}
      className={clsx(
        'flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60',
        error && 'border-red-500 focus-visible:outline-red-500',
        className,
      )}
      aria-invalid={Boolean(error)}
      {...rest}
    />
  ),
)

Input.displayName = 'Input'
