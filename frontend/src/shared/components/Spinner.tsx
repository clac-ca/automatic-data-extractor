export function Spinner({ label }: { label?: string }): JSX.Element {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12" role="status">
      <span className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      {label && <span className="text-sm text-slate-600">{label}</span>}
      <span className="sr-only">Loading</span>
    </div>
  )
}
