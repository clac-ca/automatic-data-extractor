import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";

interface PerformLogoutOptions {
  readonly signal?: AbortSignal;
}

export async function performLogout({ signal }: PerformLogoutOptions = {}) {
  try {
    await client.DELETE("/api/v1/auth/session", { signal });
  } catch (error) {
    if (!(error instanceof ApiError && (error.status === 401 || error.status === 403))) {
      if (import.meta.env.DEV) {
        console.warn("Failed to terminate session", error);
      }
    }
  }
}

