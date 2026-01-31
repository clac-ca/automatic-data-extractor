import type { ReactNode } from "react";

import { EyeIcon, LogsIcon, OutputIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";

import type { RunRecord } from "../../../types";

export function RunActionsCell({
  run,
  isActive,
  onTogglePreview,
}: {
  run: RunRecord;
  isActive: boolean;
  onTogglePreview: () => void;
}) {
  const logsHref = run.raw.links?.logs ?? null;
  const outputHref = run.raw.output?.ready
    ? run.raw.links?.output_download ?? run.raw.links?.output ?? null
    : null;

  return (
    <div className="flex items-center justify-end gap-2">
      <IconButton
        label={isActive ? "Close details" : "View details"}
        onClick={onTogglePreview}
        variant={isActive ? "secondary" : "ghost"}
      >
        <EyeIcon className="h-4 w-4" />
      </IconButton>
      <LinkButton label="View logs" href={logsHref}>
        <LogsIcon className="h-4 w-4" />
      </LinkButton>
      <LinkButton label={outputHref ? "Open output" : "Output not ready"} href={outputHref}>
        <OutputIcon className="h-4 w-4" />
      </LinkButton>
    </div>
  );
}

function IconButton({
  label,
  onClick,
  children,
  variant = "ghost",
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  variant?: "ghost" | "secondary";
}) {
  return (
    <Button
      type="button"
      variant={variant}
      size="icon"
      className="h-8 w-8"
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      {children}
    </Button>
  );
}

function LinkButton({
  label,
  href,
  children,
}: {
  label: string;
  href: string | null;
  children: ReactNode;
}) {
  if (href) {
    return (
      <Button asChild variant="outline" size="icon" className="h-8 w-8" aria-label={label} title={label}>
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      </Button>
    );
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className="h-8 w-8"
      disabled
      aria-label={label}
      title={label}
    >
      {children}
    </Button>
  );
}
