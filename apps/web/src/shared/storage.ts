function normalizeError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

export function createScopedStorage(key: string) {
  return {
    get<T>(): T | null {
      if (typeof window === "undefined") {
        return null;
      }
      try {
        const raw = window.localStorage.getItem(key);
        return raw ? (JSON.parse(raw) as T) : null;
      } catch (error: unknown) {
        console.warn("Failed to read from storage", normalizeError(error));
        return null;
      }
    },
    set<T>(value: T) {
      if (typeof window === "undefined") {
        return;
      }
      try {
        window.localStorage.setItem(key, JSON.stringify(value));
      } catch (error: unknown) {
        console.warn("Failed to write to storage", normalizeError(error));
      }
    },
    clear() {
      if (typeof window === "undefined") {
        return;
      }
      try {
        window.localStorage.removeItem(key);
      } catch (error: unknown) {
        console.warn("Failed to clear storage", normalizeError(error));
      }
    },
  };
}
