import { Lock } from "lucide-react";

import type { RuntimeSettingFieldMeta } from "./runtimeSettingsUtils";

export function SettingsLockHint({
  meta,
  className,
}: {
  readonly meta?: RuntimeSettingFieldMeta;
  readonly className?: string;
}) {
  if (!meta?.lockedByEnv) {
    return null;
  }

  return (
    <p className={["flex items-center gap-1.5 text-xs text-muted-foreground", className].filter(Boolean).join(" ")}>
      <Lock className="h-3.5 w-3.5" />
      {meta.envVar ? `${meta.envVar} is managing this setting.` : "Managed by environment variable."}
      {meta.restartRequired ? " Restart required to apply environment changes." : ""}
    </p>
  );
}
