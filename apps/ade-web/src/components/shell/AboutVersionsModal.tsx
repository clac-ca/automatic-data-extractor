import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { useSystemVersions } from "@hooks/system";
import { Alert } from "@components/ui/alert";
import { Button } from "@components/ui/button";

interface AboutVersionsModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
}

const ADE_WEB_VERSION =
  (typeof import.meta.env.VITE_APP_VERSION === "string" ? import.meta.env.VITE_APP_VERSION : "") ||
  (typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "") ||
  "unknown";

export function AboutVersionsModal({ open, onClose }: AboutVersionsModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const versionsQuery = useSystemVersions({ enabled: open });
  const isError = versionsQuery.isError;
  const apiVersion = versionsQuery.data?.ade_api ?? (versionsQuery.isPending ? "Loading..." : "unknown");
  const engineVersion = versionsQuery.data?.ade_engine ?? (versionsQuery.isPending ? "Loading..." : "unknown");

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const { body } = document;
    const previousOverflow = body.style.overflow;
    body.style.overflow = "hidden";
    return () => {
      body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (open) {
      closeButtonRef.current?.focus({ preventScroll: true });
    }
  }, [open]);

  if (typeof document === "undefined" || !open) {
    return null;
  }

  const content = (
    <div
      className="fixed inset-0 z-[95] flex items-center justify-center bg-overlay/60 px-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="about-versions-heading"
        className="w-full max-w-xl rounded-2xl border border-border/80 bg-card p-6 shadow-2xl"
      >
        <header className="mb-6 flex items-start justify-between gap-4">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">About</p>
            <h2 id="about-versions-heading" className="text-xl font-semibold text-foreground">
              ADE versions
            </h2>
            <p className="text-sm text-muted-foreground">
              Installed versions for this ADE deployment across the web UI and backend runtime.
            </p>
          </div>
          <Button ref={closeButtonRef} variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </header>

        <div className="space-y-2">
          <VersionRow label="ade-web" value={ADE_WEB_VERSION} hint="Frontend build" />
          <VersionRow label="ade-api" value={apiVersion} hint="Backend service" />
          <VersionRow label="ade-engine" value={engineVersion} hint="Engine runtime" />
        </div>

        {isError ? (
          <div className="mt-4 space-y-3">
            <Alert tone="warning" heading="Backend versions unavailable">
              Could not load backend versions. Check connectivity and try again.
            </Alert>
            <Button size="sm" variant="secondary" onClick={() => versionsQuery.refetch()}>
              Retry
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );

  return createPortal(content, document.body);
}

function VersionRow({
  label,
  value,
  hint,
}: {
  readonly label: string;
  readonly value: string;
  readonly hint: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border/70 bg-muted px-4 py-3">
      <div className="flex flex-col">
        <span className="text-sm font-semibold text-foreground">{label}</span>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </div>
      <div className="flex items-center gap-2">
        <code className="rounded bg-foreground px-2.5 py-1 text-xs font-mono text-background shadow-sm">{value}</code>
      </div>
    </div>
  );
}
