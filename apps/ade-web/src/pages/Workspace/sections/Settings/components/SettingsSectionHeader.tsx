import type { ReactNode } from "react";

interface SettingsSectionHeaderProps {
  readonly title: string;
  readonly description?: string;
  readonly actions?: ReactNode;
}

export function SettingsSectionHeader({ title, description, actions }: SettingsSectionHeaderProps) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="space-y-1">
        <h2 className="text-xl font-semibold text-foreground">{title}</h2>
        {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}
