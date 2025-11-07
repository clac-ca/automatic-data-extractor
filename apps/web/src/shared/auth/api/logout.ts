import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";

interface PerformLogoutOptions {
  readonly signal?: AbortSignal;
}

export async function performLogout({ signal }: PerformLogoutOptions = {}) {
  try {
    await client.DELETE("/api/v1/auth/session", { signal });
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return;
    }
    if (import.meta.env.DEV) {
      const reason = error instanceof Error ? error : new Error(String(error));
      console.warn("Failed to terminate session", reason);
    }
  }
}

