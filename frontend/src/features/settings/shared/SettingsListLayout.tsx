import type { ReactNode } from "react";

import { SettingsPageHeader, type SettingsBreadcrumbItem } from "./SettingsPageHeader";

export function SettingsListLayout({
  title,
  subtitle,
  breadcrumbs,
  actions,
  commandBar,
  children,
}: {
  readonly title: string;
  readonly subtitle?: string;
  readonly breadcrumbs?: readonly SettingsBreadcrumbItem[];
  readonly actions?: ReactNode;
  readonly commandBar?: ReactNode;
  readonly children: ReactNode;
}) {
  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border/60 bg-background shadow-sm">
      <SettingsPageHeader
        title={title}
        subtitle={subtitle}
        breadcrumbs={breadcrumbs}
        actions={actions}
      />
      {commandBar ? (
        <div className="border-b border-border/60 bg-muted/30 px-6 py-3">{commandBar}</div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-auto p-6">{children}</div>
    </section>
  );
}
