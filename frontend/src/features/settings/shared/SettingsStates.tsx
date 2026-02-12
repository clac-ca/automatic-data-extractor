import type { ReactNode } from "react";

import { PageState } from "@/components/layout";

export function SettingsErrorState({
  title = "Unable to load settings",
  message,
}: {
  readonly title?: string;
  readonly message: string;
}) {
  return <PageState variant="error" title={title} description={message} className="min-h-[260px]" />;
}

export function SettingsEmptyState({
  title,
  description,
  action,
}: {
  readonly title: string;
  readonly description: string;
  readonly action?: ReactNode;
}) {
  return <PageState variant="empty" title={title} description={description} action={action} className="min-h-[260px]" />;
}
