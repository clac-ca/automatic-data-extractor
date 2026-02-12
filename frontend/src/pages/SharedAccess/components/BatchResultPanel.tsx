import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface BatchResultFailure {
  readonly id: string;
  readonly label: string;
  readonly status: number;
  readonly message: string;
}

export interface BatchResultSummary {
  readonly requested: number;
  readonly succeeded: number;
  readonly failed: readonly BatchResultFailure[];
}

interface BatchResultPanelProps {
  readonly result: BatchResultSummary;
  readonly onDismiss: () => void;
  readonly onRetryFailed?: () => void | Promise<void>;
  readonly isRetrying?: boolean;
}

export function BatchResultPanel({
  result,
  onDismiss,
  onRetryFailed,
  isRetrying = false,
}: BatchResultPanelProps) {
  const failedCount = result.failed.length;
  const successCount = result.succeeded;
  const tone = failedCount > 0 ? "warning" : "success";

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4">
      <Alert tone={tone}>
        {failedCount > 0
          ? `${successCount} of ${result.requested} operations completed. ${failedCount} failed.`
          : `${successCount} operations completed successfully.`}
      </Alert>

      {failedCount > 0 ? (
        <ul className="space-y-2 rounded-lg border border-border bg-background p-3 text-sm">
          {result.failed.map((failure) => (
            <li key={failure.id} className="space-y-0.5">
              <p className="font-medium text-foreground">{failure.label}</p>
              <p className="text-xs text-muted-foreground">
                HTTP {failure.status}: {failure.message}
              </p>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onDismiss}>
          Dismiss
        </Button>
        {failedCount > 0 && onRetryFailed ? (
          <Button type="button" size="sm" onClick={onRetryFailed} disabled={isRetrying}>
            {isRetrying ? "Retrying..." : "Retry failed only"}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

