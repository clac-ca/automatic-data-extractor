import clsx from "clsx";
import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";

const BASE_CLASS =
  "block w-full rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground";

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, ...props }, ref) => (
    <select ref={ref} className={clsx(BASE_CLASS, className)} {...props} />
  ),
);

Select.displayName = "Select";
