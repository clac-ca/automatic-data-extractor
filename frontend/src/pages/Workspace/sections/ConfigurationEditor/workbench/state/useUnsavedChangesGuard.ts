import { useCallback, useEffect } from "react";

import { useBlocker, type BlockerFunction } from "react-router-dom";

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
  const shouldBlock = useCallback<BlockerFunction>(
    ({ currentLocation, nextLocation }) => {
      if (!isDirty) {
        return false;
      }

      if (shouldBypassNavigation?.()) {
        return false;
      }

      if (currentLocation.pathname === nextLocation.pathname) {
        return false;
      }

      return true;
    },
    [isDirty, shouldBypassNavigation],
  );

  const blocker = useBlocker(shouldBlock);

  useEffect(() => {
    if (blocker.state !== "blocked") {
      return;
    }

    if (confirm(message)) {
      blocker.proceed();
    } else {
      blocker.reset();
    }
  }, [blocker, confirm, message]);

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
