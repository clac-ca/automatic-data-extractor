import { Link } from "react-router-dom";

import { PageState } from "@/components/layout";
import { Button } from "@/components/ui/button";

export function SettingsAccessDenied({
  title = "Access denied",
  description = "You do not have permission to open this settings page.",
  returnHref = "/settings",
}: {
  readonly title?: string;
  readonly description?: string;
  readonly returnHref?: string;
}) {
  return (
    <PageState
      variant="error"
      title={title}
      description={description}
      action={
        <Button asChild size="sm">
          <Link to={returnHref}>Back to Settings</Link>
        </Button>
      }
      className="min-h-[360px]"
    />
  );
}
