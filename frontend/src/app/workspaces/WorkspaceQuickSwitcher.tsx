import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";

import type { WorkspaceProfile } from "../../shared/types/workspaces";

type WorkspaceQuickSwitcherSize = "regular" | "compact";
type WorkspaceQuickSwitcherTone = "solid" | "ghost";
type WorkspaceQuickSwitcherVariant = "default" | "brand";

interface WorkspaceQuickSwitcherProps {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: readonly WorkspaceProfile[];
  readonly onSelectWorkspace: (workspaceId: string) => void;
  readonly onCreateWorkspace?: () => void;
  readonly onManageWorkspace?: () => void;
  readonly size?: WorkspaceQuickSwitcherSize;
  readonly tone?: WorkspaceQuickSwitcherTone;
  readonly className?: string;
  readonly variant?: WorkspaceQuickSwitcherVariant;
  readonly glyphOverride?: string;
  readonly title?: string;
  readonly subtitle?: string;
  readonly showSlug?: boolean;
}

export function WorkspaceQuickSwitcher({
  workspace,
  workspaces,
  onSelectWorkspace,
  onCreateWorkspace,
  onManageWorkspace,
  size = "regular",
  tone = "solid",
  className,
  variant = "default",
  glyphOverride,
  title,
  subtitle,
  showSlug = true,
}: WorkspaceQuickSwitcherProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleClickOutside = (event: MouseEvent) => {
      if (!containerRef.current) {
        return;
      }
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", handleClickOutside);
    return () => window.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const otherWorkspaces = useMemo(
    () => workspaces.filter((candidate) => candidate.id !== workspace.id),
    [workspace.id, workspaces],
  );

  const isCompact = size === "compact";
  const isGhost = tone === "ghost";
  const isBrand = variant === "brand";

  const glyph = glyphOverride ?? deriveGlyph(workspace.name);

  return (
    <div
      ref={containerRef}
      className={clsx("relative", className)}
      onBlur={(event) => {
        if (!containerRef.current) {
          return;
        }
        if (!containerRef.current.contains(event.relatedTarget as Node)) {
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={clsx(
          "focus-ring inline-flex items-center gap-3 text-sm font-semibold transition",
          isBrand
            ? "rounded-xl border border-transparent bg-white px-3 py-2 shadow-sm hover:bg-slate-100"
            : clsx(
                "rounded-xl",
                isCompact ? "h-10 px-2.5 py-1.5" : "px-3 py-3 shadow-sm",
                isGhost
                  ? "border border-transparent bg-transparent text-slate-600 hover:bg-white/80 hover:text-slate-900"
                  : "border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:text-slate-900",
              ),
        )}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={variant === "brand" ? `Workspace selector. Current workspace ${workspace.name}` : `Workspace: ${workspace.name}`}
      >
        <span
          className={clsx(
            "inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border text-sm font-semibold",
            isBrand
              ? "border-transparent bg-brand-600 text-white"
              : "border-brand-100 bg-brand-50 text-brand-700",
          )}
        >
          {glyph}
        </span>
        <span className="flex min-w-0 flex-col text-left">
          <span className="truncate text-sm font-semibold text-slate-900">
            {isBrand ? title ?? "Automatic Data Extractor" : workspace.name}
          </span>
          <span className="truncate text-xs text-slate-400">
            {isBrand
              ? subtitle ?? workspace.name
              : showSlug
                ? workspace.slug
                  ? `/${workspace.slug}`
                  : "Active workspace"
                : undefined}
          </span>
        </span>
        <span className={clsx("text-slate-400 transition-transform", open && "rotate-180")}>▾</span>
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute z-30 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-3 text-sm shadow-xl"
        >
          <ul className="space-y-1">
            {onManageWorkspace ? (
              <li>
                <MenuButton
                  label="Workspace settings"
                  description="Members, permissions, integrations"
                  icon="⚙️"
                  onClick={() => {
                    setOpen(false);
                    onManageWorkspace();
                  }}
                />
              </li>
            ) : null}
            {onCreateWorkspace ? (
              <li>
                <MenuButton
                  label="Create workspace"
                  description="Spin up a new workspace"
                  icon="＋"
                  onClick={() => {
                    setOpen(false);
                    onCreateWorkspace();
                  }}
                />
              </li>
            ) : null}
          </ul>
          {otherWorkspaces.length > 0 ? (
            <div className="mt-4 space-y-2">
              <p className="px-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Switch workspace</p>
              <ul className="space-y-1">
                {otherWorkspaces.map((candidate) => (
                  <li key={candidate.id}>
                    <MenuButton
                      label={candidate.name}
                      description={candidate.slug ? `/${candidate.slug}` : undefined}
                      icon={deriveGlyph(candidate.name)}
                      onClick={() => {
                        setOpen(false);
                        onSelectWorkspace(candidate.id);
                      }}
                    />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function MenuButton({
  label,
  description,
  icon,
  onClick,
}: {
  readonly label: string;
  readonly description?: string;
  readonly icon: string;
  readonly onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-700 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
      onClick={onClick}
    >
      <span className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-600">
        {icon}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="truncate">{label}</span>
        {description ? <span className="truncate text-xs font-normal text-slate-400">{description}</span> : null}
      </span>
    </button>
  );
}

function deriveGlyph(name: string) {
  const [first = "", second = ""] = name
    .split(" ")
    .map((segment) => segment.trim())
    .filter(Boolean);
  return `${first.charAt(0)}${second.charAt(0)}`.toUpperCase() || name.charAt(0).toUpperCase() || "•";
}
