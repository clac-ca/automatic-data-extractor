import { useId, type InputHTMLAttributes } from "react";

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "name" | "className"> {
  name: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  description?: string;
  containerClassName?: string;
  inputClassName?: string;
}

export function TextField({
  name,
  label,
  value,
  onChange,
  error,
  description,
  containerClassName,
  inputClassName,
  id,
  ...inputProps
}: TextFieldProps) {
  const generatedId = useId();
  const fieldId = id ?? `${name}-${generatedId}`;
  const descriptionId = description ? `${fieldId}-description` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={`space-y-1 ${containerClassName ?? ""}`.trim()}>
      <label htmlFor={fieldId} className="text-sm font-medium text-slate-200">
        {label}
      </label>
      <input
        id={fieldId}
        name={name}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400 disabled:opacity-60 ${
          inputClassName ?? ""
        }`.trim()}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        {...inputProps}
      />
      {description && (
        <p id={descriptionId} className="text-xs text-slate-500">
          {description}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-xs text-rose-300">
          {error}
        </p>
      )}
    </div>
  );
}
