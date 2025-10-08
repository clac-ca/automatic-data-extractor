import { forwardRef } from 'react'
import { clsx } from 'clsx'

type ButtonVariant = 'primary' | 'secondary' | 'ghost'

type ButtonSize = 'md' | 'sm'

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  isLoading?: boolean
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:outline-primary',
  secondary:
    'bg-white text-slate-950 border border-slate-200 hover:bg-slate-100 focus-visible:outline-slate-400',
  ghost:
    'bg-transparent text-primary hover:bg-primary/10 focus-visible:outline-primary/50',
}

const sizeClasses: Record<ButtonSize, string> = {
  md: 'h-10 px-4 py-2 text-sm font-medium',
  sm: 'h-8 px-3 py-1 text-xs font-medium',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({
    className,
    children,
    variant = 'primary',
    size = 'md',
    isLoading = false,
    disabled,
    ...rest
  }, ref) => (
    <button
      ref={ref}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-md transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      disabled={disabled ?? isLoading}
      {...rest}
    >
      {isLoading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  ),
)

Button.displayName = 'Button'
