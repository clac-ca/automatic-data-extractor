import clsx from "clsx";

type ConfigurationStatus = "draft" | "active" | "archived" | (string & {});

export function StatusPill({ status }: { readonly status: ConfigurationStatus }) {
  const normalized = status.toLowerCase() as ConfigurationStatus;
  const label =
    normalized === "active"
      ? "Active"
      : normalized === "draft"
        ? "Draft"
        : normalized === "archived"
          ? "Archived"
          : status;
  const styles =
    normalized === "active"
      ? "bg-primary/10 text-primary"
      : normalized === "draft"
        ? "bg-accent text-accent-foreground"
        : "bg-secondary text-secondary-foreground";
  return (
    <span
      className={clsx(
        "rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide",
        styles,
      )}
      title={label}
    >
      {label}
    </span>
  );
}
