import clsx from "clsx";
import { Fragment, useMemo } from "react";

import type { components } from "@openapi";
import { Button } from "@ui/button";

interface ConfigurationSidebarProps {
  readonly configurations: readonly ConfigurationRecord[] | undefined;
  readonly selectedId: string | null;
  readonly onSelect: (configurationId: string) => void;
  readonly onCreateFromActive: () => void;
  readonly onCreateBlank: () => void;
  readonly onActivate: (configurationId: string) => void;
  readonly isCreating?: boolean;
  readonly isActivating?: boolean;
}

export function ConfigurationSidebar({
  configurations,
  selectedId,
  onSelect,
  onCreateFromActive,
  onCreateBlank,
  onActivate,
  isCreating = false,
  isActivating = false,
}: ConfigurationSidebarProps) {
  const sorted = useMemo(() => {
    return [...(configurations ?? [])].sort((a, b) => {
      if (a.is_active && !b.is_active) {
        return -1;
      }
      if (!a.is_active && b.is_active) {
        return 1;
      }
      return b.version - a.version;
    });
  }, [configurations]);

  return (
    <aside className="w-full max-w-md space-y-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-soft lg:w-80">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Configurations</h2>
          <span className="text-xs text-slate-400">{sorted.length} total</span>
        </div>
        <p className="text-sm text-slate-600">
          Manage workspace configuration versions. Create drafts, review metadata, and activate when ready.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={onCreateFromActive}
          isLoading={isCreating}
          disabled={isCreating}
        >
          New version from active
        </Button>
        <Button variant="secondary" size="sm" onClick={onCreateBlank} disabled={isCreating}>
          New blank configuration
        </Button>
      </div>

      <nav aria-label="Configuration versions" className="space-y-1">
        {sorted.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
            No configurations yet. Create a draft to get started.
          </p>
        ) : (
          sorted.map((configuration) => {
            const isActive = configuration.is_active;
            const isSelected = configuration.configuration_id === selectedId;
            const statusLabel = isActive ? "Active" : "Draft";
            const activatedLabel = configuration.activated_at
              ? `Activated ${formatRelative(configuration.activated_at)}`
              : `Updated ${formatRelative(configuration.updated_at)}`;
            return (
              <Fragment key={configuration.configuration_id}>
                <button
                  type="button"
                  onClick={() => onSelect(configuration.configuration_id)}
                  className={clsx(
                    "w-full rounded-xl border p-4 text-left transition",
                    isSelected
                      ? "border-brand-400 bg-brand-50 shadow-sm"
                      : "border-slate-200 bg-white hover:border-brand-300 hover:bg-brand-50/60",
                  )}
                  aria-current={isSelected ? "page" : undefined}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{configuration.title}</p>
                      <p className="text-xs text-slate-500">Version {configuration.version}</p>
                    </div>
                    <span
                      className={clsx(
                        "inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold",
                        isActive ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-700",
                      )}
                    >
                      {statusLabel}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">{activatedLabel}</p>
                </button>
                {!isActive ? (
                  <div className="flex justify-end pb-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onActivate(configuration.configuration_id)}
                      disabled={isActivating}
                      className="text-brand-700 hover:text-brand-800"
                    >
                      Activate
                    </Button>
                  </div>
                ) : null}
              </Fragment>
            );
          })
        )}
      </nav>
    </aside>
  );
}

type ConfigurationRecord = components["schemas"]["ConfigurationRecord"];

function formatRelative(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(
    Math.round((date.getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
    "day",
  );
}
