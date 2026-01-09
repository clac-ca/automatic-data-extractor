import type { WorkbenchValidationState } from "../types";

export function ProblemsTab({ validation }: { readonly validation: WorkbenchValidationState }) {
  const statusLabel = describeValidationStatus(validation);
  const fallbackMessage = describeValidationFallback(validation);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>{statusLabel}</span>
        {validation.lastRunAt ? <span>Last run {formatRelative(validation.lastRunAt)}</span> : null}
      </div>
      {validation.messages.length > 0 ? (
        <ul className="space-y-1.5">
          {validation.messages.map((item, index) => (
            <li key={`${item.level}-${item.path ?? index}-${index}`} className={validationMessageClass(item.level)}>
              {item.path ? (
                <span className="block text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  {item.path}
                </span>
              ) : null}
              <span className="text-[13px]">{item.message}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs leading-relaxed text-muted-foreground">{fallbackMessage}</p>
      )}
    </div>
  );
}

function validationMessageClass(level: WorkbenchValidationState["messages"][number]["level"]) {
  switch (level) {
    case "error":
      return "text-destructive";
    case "warning":
      return "text-amber-600 dark:text-amber-300";
    default:
      return "text-muted-foreground";
  }
}

function describeValidationStatus(validation: WorkbenchValidationState): string {
  switch (validation.status) {
    case "running":
      return "Running validation...";
    case "success": {
      if (validation.messages.length === 0) {
        return "Validation completed with no issues.";
      }
      const count = validation.messages.length;
      return `Validation completed with ${count} ${count === 1 ? "issue" : "issues"}.`;
    }
    case "error":
      return validation.error ?? "Validation failed.";
    default:
      return "No validation run yet.";
  }
}

function describeValidationFallback(validation: WorkbenchValidationState): string {
  if (validation.status === "running") {
    return "Validation in progress...";
  }
  if (validation.status === "success") {
    return "No validation issues detected.";
  }
  if (validation.status === "error") {
    return validation.error ?? "Validation failed.";
  }
  return "Trigger validation from the workbench header to see ADE parsing results and manifest issues.";
}

function formatRelative(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}
