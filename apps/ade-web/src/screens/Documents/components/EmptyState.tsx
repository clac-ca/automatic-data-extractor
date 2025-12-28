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
    <div className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-card px-8 py-12 text-center">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="text-sm text-muted-foreground">{description}</p>
      {action ? (
        <Button type="button" onClick={action.onClick} size="sm">
          {action.label}
        </Button>
      ) : null}
    </div>
  );
}
