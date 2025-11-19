import { useMemo } from "react";

import type { BannerOptions, ToastOptions } from "./types";
import { useNotificationsContext } from "./NotificationsProvider";

export function useNotifications() {
  const context = useNotificationsContext();

  return useMemo(
    () => ({
      notifyToast: (options: ToastOptions) => context.pushToast(options),
      notifyBanner: (options: BannerOptions) => context.pushBanner(options),
      dismissNotification: (id: string) => context.dismiss(id),
      dismissScope: (scope: string, kind?: "toast" | "banner") => context.clearScope(scope, kind),
    }),
    [context],
  );
}

