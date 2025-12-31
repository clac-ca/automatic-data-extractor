import { Button } from "@components/ui/button";
import { AlertTriangleIcon } from "@components/icons";

export function ProcessingPausedBanner({
  canManageSettings,
  onOpenSettings,
  configMissing,
}: {
  canManageSettings: boolean;
  onOpenSettings?: () => void;
  configMissing?: boolean;
}) {
  const description = configMissing
    ? "Uploads are stored, but runs will not start until processing is resumed and a configuration is active."
    : "Uploads are stored, but runs will not start until processing is resumed.";
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-warning-200 bg-warning-50 px-4 py-3 text-xs text-warning-900">
      <div className="flex min-w-0 items-start gap-3">
        <AlertTriangleIcon className="mt-0.5 h-4 w-4 text-warning-600" aria-hidden />
        <div className="min-w-0">
          <p className="font-semibold">Processing paused</p>
          <p className="text-[11px] text-warning-800">{description}</p>
        </div>
      </div>
      {canManageSettings && onOpenSettings ? (
        <Button type="button" size="sm" onClick={onOpenSettings} className="h-7 px-3 text-xs">
          Open processing settings
        </Button>
      ) : (
        <span className="text-[11px] font-medium text-warning-800">Ask an admin to resume processing.</span>
      )}
    </div>
  );
}
