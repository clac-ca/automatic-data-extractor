import { Button } from "@ui/Button";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-slate-200 bg-white px-8 py-12 text-center">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <p className="text-sm text-slate-500">{description}</p>
      {action ? (
        <Button type="button" onClick={action.onClick} size="sm">
          {action.label}
        </Button>
      ) : null}
    </div>
  );
}
