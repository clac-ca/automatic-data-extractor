import { useEffect, useMemo, useRef } from "react";

import { cn } from "@/lib/utils";

import type { SettingsFormErrorSummaryModel } from "./types";

export function SettingsFormErrorSummary({
  summary,
  className,
}: {
  readonly summary: SettingsFormErrorSummaryModel | null;
  readonly className?: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  const summaryKey = useMemo(
    () => summary?.items.map((item) => `${item.key}:${item.message}`).join("|") ?? "",
    [summary],
  );

  useEffect(() => {
    if (!summary || summary.items.length === 0) {
      return;
    }
    containerRef.current?.focus();
  }, [summaryKey, summary]);

  if (!summary || summary.items.length === 0) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      tabIndex={-1}
      role="alert"
      className={cn(
        "rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive outline-none",
        className,
      )}
    >
      <p className="font-semibold">{summary.title ?? "Review the highlighted fields."}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {summary.items.map((item) => (
          <li key={`${item.key}-${item.message}`}>
            {item.fieldId ? (
              <a className="underline underline-offset-2" href={`#${item.fieldId}`}>
                {item.label}: {item.message}
              </a>
            ) : (
              <span>
                {item.label}: {item.message}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
