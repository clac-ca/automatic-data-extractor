import { useCallback, useEffect } from "react";

import { useLocation, useNavigationBlocker } from "@app/nav/history";

const DEFAULT_PROMPT = "You have unsaved changes in the config editor. Are you sure you want to leave?";

type ConfirmFn = (message: string) => boolean;

interface UseUnsavedChangesGuardOptions {
  readonly isDirty: boolean;
  readonly confirm?: ConfirmFn;
  readonly message?: string;
  readonly shouldBypassNavigation?: () => boolean;
}

export function useUnsavedChangesGuard({
  isDirty,
  confirm = window.confirm,
  message = DEFAULT_PROMPT,
  shouldBypassNavigation,
}: UseUnsavedChangesGuardOptions) {
  const location = useLocation();

  const blocker = useCallback<Parameters<typeof useNavigationBlocker>[0]>(
    (intent) => {
      if (!isDirty) {
        return true;
      }

      if (shouldBypassNavigation?.()) {
        return true;
      }

      if (intent.location.pathname === location.pathname) {
        return true;
      }

      return confirm(message);
    },
    [confirm, isDirty, location.pathname, message, shouldBypassNavigation],
  );

  useNavigationBlocker(blocker, isDirty);

  useEffect(() => {
    if (!isDirty) {
      return;
    }

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
      return message;
    };

    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [isDirty, message]);
}

export { DEFAULT_PROMPT as UNSAVED_CHANGES_PROMPT };
