import clsx from "clsx";

import { RUN_STATUS_META } from "../../../constants";
import type { RunRecord } from "../../../types";

export function RunStatusCell({ status }: { status: RunRecord["status"] }) {
  const meta = RUN_STATUS_META[status];

  return (
    <div className="inline-flex items-center gap-2 text-xs font-semibold text-foreground">
      <span className={clsx("h-2.5 w-2.5 rounded-full", meta.dotClass)} />
      {meta.label}
    </div>
  );
}
