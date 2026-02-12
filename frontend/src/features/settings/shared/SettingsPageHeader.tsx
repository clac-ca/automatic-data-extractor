import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

export interface SettingsBreadcrumbItem {
  readonly label: string;
  readonly href?: string;
}

export function SettingsPageHeader({
  title,
  subtitle,
  actions,
  metadata,
  breadcrumbs,
  className,
  autoFocusTitle = true,
}: {
  readonly title: string;
  readonly subtitle?: string;
  readonly actions?: ReactNode;
  readonly metadata?: ReactNode;
  readonly breadcrumbs?: readonly SettingsBreadcrumbItem[];
  readonly className?: string;
  readonly autoFocusTitle?: boolean;
}) {
  const titleRef = useRef<HTMLHeadingElement | null>(null);
  const focusKey = useMemo(
    () => [title, ...(breadcrumbs ?? []).map((item) => item.label)].join("|"),
    [breadcrumbs, title],
  );

  useEffect(() => {
    if (!autoFocusTitle) {
      return;
    }
    const raf = window.requestAnimationFrame(() => {
      titleRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(raf);
  }, [autoFocusTitle, focusKey]);

  return (
    <header className={cn("space-y-4 border-b border-border/60 bg-background px-6 py-5", className)}>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
          {breadcrumbs.map((item, index) => (
            <span key={`${item.label}-${index}`} className="inline-flex items-center gap-1.5">
              {item.href ? (
                <Link to={item.href} className="hover:text-foreground">
                  {item.label}
                </Link>
              ) : (
                <span className="text-foreground">{item.label}</span>
              )}
              {index < breadcrumbs.length - 1 ? <ChevronRight className="h-3.5 w-3.5" /> : null}
            </span>
          ))}
        </nav>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 ref={titleRef} tabIndex={-1} className="text-2xl font-semibold tracking-tight text-foreground outline-none">
            {title}
          </h1>
          {subtitle ? <p className="max-w-3xl text-sm text-muted-foreground">{subtitle}</p> : null}
          {metadata ? <div className="pt-1 text-xs text-muted-foreground">{metadata}</div> : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}
