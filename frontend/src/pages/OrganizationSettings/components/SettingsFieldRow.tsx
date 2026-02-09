import clsx from "clsx";
import type { ReactNode } from "react";

import type { RuntimeSettingFieldMeta } from "./runtimeSettingsUtils";
import { SettingsLockHint } from "./SettingsLockHint";

export function SettingsFieldRow({
  label,
  description,
  meta,
  error,
  hint,
  children,
  className,
}: {
  readonly label: string;
  readonly description?: string;
  readonly meta?: RuntimeSettingFieldMeta;
  readonly error?: string;
  readonly hint?: string;
  readonly children: ReactNode;
  readonly className?: string;
}) {
  return (
    <div className={clsx("rounded-xl border border-border/60 bg-background px-4 py-3.5", className)}>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      </div>
      <div className="mt-2.5">{children}</div>
      {hint ? <p className="mt-2 text-sm text-muted-foreground">{hint}</p> : null}
      <SettingsLockHint meta={meta} className="mt-2" />
      {error ? <p className="mt-2 text-sm font-medium text-destructive">{error}</p> : null}
    </div>
  );
}
