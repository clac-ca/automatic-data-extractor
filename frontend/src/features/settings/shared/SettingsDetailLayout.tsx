import { useEffect, type ReactNode } from "react";

import { SettingsPageHeader, type SettingsBreadcrumbItem } from "./SettingsPageHeader";
import { useOptionalSettingsSectionContext } from "./SettingsSectionContext";
import type { SettingsSectionSpec } from "./types";

export function SettingsDetailLayout({
  title,
  subtitle,
  breadcrumbs,
  actions,
  sections: _sections = [],
  defaultSectionId: _defaultSectionId,
  children,
}: {
  readonly title: string;
  readonly subtitle?: string;
  readonly breadcrumbs?: readonly SettingsBreadcrumbItem[];
  readonly actions?: ReactNode;
  readonly sections?: readonly SettingsSectionSpec[];
  readonly defaultSectionId?: string;
  readonly children: ReactNode;
}) {
  const sectionContext = useOptionalSettingsSectionContext();

  useEffect(() => {
    if (!sectionContext) {
      return;
    }
    sectionContext.setEntityLabel(title);
    return () => sectionContext.setEntityLabel(null);
  }, [sectionContext, title]);

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border/60 bg-background shadow-sm">
      <SettingsPageHeader
        title={title}
        subtitle={subtitle}
        breadcrumbs={breadcrumbs}
        actions={actions}
      />
      <div className="min-h-0 flex-1 overflow-auto p-6">
        <div className="mx-auto w-full max-w-5xl space-y-8">{children}</div>
      </div>
    </section>
  );
}

export function SettingsDetailSection({
  id,
  title,
  description,
  children,
  tone = "default",
}: {
  readonly id?: string;
  readonly title: string;
  readonly description?: string;
  readonly children: ReactNode;
  readonly tone?: "default" | "danger";
}) {
  return (
    <section
      id={id}
      tabIndex={-1}
      className={
        tone === "danger"
          ? "rounded-xl border border-destructive/30 bg-destructive/5 p-5"
          : "rounded-xl border border-border/70 bg-background p-5"
      }
    >
      <div className="space-y-1">
        <h2 className={tone === "danger" ? "text-base font-semibold text-destructive" : "text-base font-semibold text-foreground"}>
          {title}
        </h2>
        {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}
