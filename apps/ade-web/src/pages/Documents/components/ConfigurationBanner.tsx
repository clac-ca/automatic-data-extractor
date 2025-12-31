import { Button } from "@components/Button";
import { AlertTriangleIcon } from "@components/Icons";

export function ConfigurationBanner({
  canManageConfigurations,
  onOpenConfigBuilder,
}: {
  canManageConfigurations: boolean;
  onOpenConfigBuilder?: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-warning-200 bg-warning-50 px-4 py-3 text-xs text-warning-900">
      <div className="flex min-w-0 items-start gap-3">
        <AlertTriangleIcon className="mt-0.5 h-4 w-4 text-warning-600" aria-hidden />
        <div className="min-w-0">
          <p className="font-semibold">No active configuration</p>
          <p className="text-[11px] text-warning-800">
            Uploads are stored, but runs will not start until a configuration is active.
          </p>
        </div>
      </div>
      {canManageConfigurations && onOpenConfigBuilder ? (
        <Button type="button" size="sm" onClick={onOpenConfigBuilder} className="h-7 px-3 text-xs">
          Open Config Builder
        </Button>
      ) : (
        <span className="text-[11px] font-medium text-warning-800">Ask an admin to activate a configuration.</span>
      )}
    </div>
  );
}
