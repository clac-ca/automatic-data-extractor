import clsx from "clsx";
import { cloneElement, isValidElement, useId } from "react";
import type { ReactElement, ReactNode } from "react";

export type ControlProps = {
  id?: string;
  required?: boolean;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean | "true" | "false";
};

export type ControlElement = ReactElement<ControlProps>;

export interface FormFieldProps {
  readonly label?: ReactNode;
  readonly hint?: ReactNode;
  readonly error?: ReactNode;
  readonly required?: boolean;
  readonly children: ControlElement;
  readonly className?: string;
}

export function FormField({
  label,
  hint,
  error,
  required = false,
  children,
  className,
}: FormFieldProps) {
  const generatedId = useId();
  const childProps = children.props ?? {};
  const controlId = childProps.id ?? generatedId;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [hintId, errorId, childProps["aria-describedby"]]
    .filter(Boolean)
    .join(" ") || undefined;

  return (
    <div className={clsx("space-y-2", className)}>
      {label ? (
        <label
          htmlFor={controlId}
          className="text-sm font-medium text-slate-700"
          aria-required={required || undefined}
        >
          {label}
          {required ? (
            <span className="ml-1 text-danger-600" aria-hidden="true">
              *
            </span>
          ) : null}
        </label>
      ) : null}
      {isValidElement(children)
        ? cloneElement(children, {
            id: controlId,
            required: required || childProps.required,
            "aria-describedby": describedBy,
            "aria-invalid": error ? true : childProps["aria-invalid"],
          })
        : children}
      {hint ? (
        <p id={hintId} className="text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs font-medium text-danger-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}
