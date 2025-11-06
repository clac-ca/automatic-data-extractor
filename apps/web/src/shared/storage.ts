export function createScopedStorage(key: string) {
  return {
    get<T>(): T | null {
      if (typeof window === "undefined") {
        return null;
      }
      try {
        const raw = window.localStorage.getItem(key);
        return raw ? (JSON.parse(raw) as T) : null;
      } catch (error) {
        console.warn("Failed to read from storage", error);
        return null;
      }
    },
    set<T>(value: T) {
      if (typeof window === "undefined") {
        return;
      }
      try {
        window.localStorage.setItem(key, JSON.stringify(value));
      } catch (error) {
        console.warn("Failed to write to storage", error);
      }
    },
    clear() {
      if (typeof window === "undefined") {
        return;
      }
      window.localStorage.removeItem(key);
    },
  };
}
