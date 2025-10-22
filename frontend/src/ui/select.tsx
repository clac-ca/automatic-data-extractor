import clsx from "clsx";
import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";

const BASE_CLASS =
  "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, ...props }, ref) => (
    <select ref={ref} className={clsx(BASE_CLASS, className)} {...props} />
  ),
);

Select.displayName = "Select";
