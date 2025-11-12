import type { ReactNode } from "react";

interface EmptyStateProps {
  readonly title: string;
  readonly description: string;
  readonly action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 rounded-2xl border border-slate-800/40 bg-slate-900/60 p-10 text-center text-slate-200">
      <div>
        <p className="text-lg font-semibold text-white">{title}</p>
        <p className="mt-2 max-w-md text-sm text-slate-300">{description}</p>
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}
