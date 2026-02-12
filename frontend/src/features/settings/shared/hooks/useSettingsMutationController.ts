import { useCallback, useState } from "react";

import type { SettingsMutationState } from "../types";

export function useSettingsMutationController(initialMessage: string | null = null) {
  const [state, setState] = useState<SettingsMutationState>({
    status: "idle",
    message: initialMessage,
  });

  const reset = useCallback(() => {
    setState({ status: "idle", message: null });
  }, []);

  const start = useCallback((message: string | null = null) => {
    setState({ status: "pending", message });
  }, []);

  const succeed = useCallback((message: string) => {
    setState({ status: "success", message });
  }, []);

  const fail = useCallback((message: string) => {
    setState({ status: "error", message });
  }, []);

  const run = useCallback(
    async <T>(
      operation: () => Promise<T>,
      options: {
        readonly pendingMessage?: string;
        readonly successMessage: string;
        readonly getErrorMessage?: (error: unknown) => string;
      },
    ) => {
      start(options.pendingMessage ?? null);
      try {
        const result = await operation();
        succeed(options.successMessage);
        return result;
      } catch (error) {
        const message = options.getErrorMessage
          ? options.getErrorMessage(error)
          : error instanceof Error
            ? error.message
            : "Unable to complete the requested action.";
        fail(message);
        throw error;
      }
    },
    [fail, start, succeed],
  );

  return {
    state,
    start,
    succeed,
    fail,
    reset,
    run,
  };
}
