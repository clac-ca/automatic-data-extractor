interface FormAlertProps {
  message: string | null;
}

export function FormAlert({ message }: FormAlertProps) {
  if (!message) {
    return null;
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200"
    >
      {message}
    </div>
  );
}
