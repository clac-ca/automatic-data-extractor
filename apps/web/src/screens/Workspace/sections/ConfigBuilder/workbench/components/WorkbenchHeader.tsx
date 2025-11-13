import { Button } from "@ui/Button";

import type { EditorThemePreference } from "../state/useEditorThemePreference";

interface WorkbenchHeaderProps {
  readonly configName: string;
  readonly explorerCollapsed: boolean;
  readonly inspectorCollapsed: boolean;
  readonly outputCollapsed: boolean;
  readonly onToggleExplorer: () => void;
  readonly onToggleInspector: () => void;
  readonly onToggleOutput: () => void;
  readonly onValidate: () => void;
  readonly canValidate: boolean;
  readonly isValidating: boolean;
  readonly lastValidatedAt?: string;
  readonly editorThemePreference: EditorThemePreference;
  readonly onChangeEditorThemePreference: (preference: EditorThemePreference) => void;
}

export function WorkbenchHeader({
  configName,
  explorerCollapsed,
  inspectorCollapsed,
  outputCollapsed,
  onToggleExplorer,
  onToggleInspector,
  onToggleOutput,
  onValidate,
  canValidate,
  isValidating,
  lastValidatedAt,
  editorThemePreference,
  onChangeEditorThemePreference,
}: WorkbenchHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Config Workbench</p>
        <h1 className="text-lg font-semibold text-slate-900">{configName}</h1>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end sm:gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={onValidate} isLoading={isValidating} disabled={!canValidate}>
            Run validation
          </Button>
          {lastValidatedAt ? (
            <span className="text-xs text-slate-500">Last run {formatRelative(lastValidatedAt)}</span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onToggleExplorer}>
            {explorerCollapsed ? "Show Explorer" : "Hide Explorer"}
          </Button>
          <Button variant="ghost" size="sm" onClick={onToggleOutput}>
            {outputCollapsed ? "Show Output" : "Hide Output"}
          </Button>
          <Button variant="ghost" size="sm" onClick={onToggleInspector}>
            {inspectorCollapsed ? "Show Inspector" : "Hide Inspector"}
          </Button>
        </div>
        <div className="flex flex-col gap-1 text-left sm:text-right">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Editor theme</span>
          <div
            role="radiogroup"
            aria-label="Editor theme"
            className="inline-flex rounded-full border border-slate-200 bg-white p-0.5 shadow-inner"
          >
            {THEME_OPTIONS.map((option) => {
              const isActive = editorThemePreference === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                    isActive ? "bg-slate-900 text-white shadow" : "text-slate-600 hover:text-slate-900"
                  }`}
                  onClick={() => {
                    if (!isActive) {
                      onChangeEditorThemePreference(option.value);
                    }
                  }}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </header>
  );
}

function formatRelative(timestamp?: string): string {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

const THEME_OPTIONS: Array<{ value: EditorThemePreference; label: string }> = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];
