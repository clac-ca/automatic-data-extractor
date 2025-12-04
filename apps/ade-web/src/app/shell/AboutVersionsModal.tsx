import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { ADE_WEB_VERSION } from "@shared/version";
import { useSystemVersions } from "@shared/system";
import { Alert } from "@ui/Alert";
import { Button } from "@ui/Button";

interface AboutVersionsModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
}

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
      className="fixed inset-0 z-[95] flex items-center justify-center bg-slate-900/60 px-4"
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
        className="w-full max-w-xl rounded-2xl border border-slate-200/80 bg-white p-6 shadow-2xl"
      >
        <header className="mb-6 flex items-start justify-between gap-4">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">About</p>
            <h2 id="about-versions-heading" className="text-xl font-semibold text-slate-900">
              ADE versions
            </h2>
            <p className="text-sm text-slate-500">
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
    <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
      <div className="flex flex-col">
        <span className="text-sm font-semibold text-slate-900">{label}</span>
        <span className="text-xs text-slate-500">{hint}</span>
      </div>
      <div className="flex items-center gap-2">
        <code className="rounded bg-slate-900/90 px-2.5 py-1 text-xs font-mono text-white shadow-sm">{value}</code>
      </div>
    </div>
  );
}
