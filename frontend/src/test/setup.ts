import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn();
}

if (typeof window !== "undefined") {
  if (typeof globalThis.fetch === "function") {
    Object.defineProperty(window, "fetch", {
      value: globalThis.fetch.bind(globalThis),
      configurable: true,
      writable: true,
    });
    Object.defineProperty(window, "Request", {
      value: globalThis.Request,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(window, "Response", {
      value: globalThis.Response,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(window, "Headers", {
      value: globalThis.Headers,
      configurable: true,
      writable: true,
    });
  }

  if (typeof globalThis.AbortController === "function") {
    Object.defineProperty(window, "AbortController", {
      value: globalThis.AbortController,
      configurable: true,
      writable: true,
    });
  }
  if (typeof globalThis.AbortSignal === "function") {
    Object.defineProperty(window, "AbortSignal", {
      value: globalThis.AbortSignal,
      configurable: true,
      writable: true,
    });
  }

  if (typeof globalThis.Request === "function") {
    const BaseRequest = globalThis.Request;
    class PatchedRequest extends BaseRequest {
      constructor(input: RequestInfo | URL, init?: RequestInit) {
        const nextInit = init?.signal ? { ...init, signal: undefined } : init;
        super(input, nextInit);
      }
    }

    Object.defineProperty(globalThis, "Request", {
      value: PatchedRequest,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(window, "Request", {
      value: PatchedRequest,
      configurable: true,
      writable: true,
    });
  }

  const missingLocalStorage =
    !window.localStorage ||
    typeof window.localStorage.clear !== "function" ||
    typeof window.localStorage.getItem !== "function" ||
    typeof window.localStorage.setItem !== "function";

  if (missingLocalStorage) {
    const store = new Map<string, string>();
    const storage: Storage = {
      get length() {
        return store.size;
      },
      clear() {
        store.clear();
      },
      getItem(key: string) {
        return store.has(key) ? store.get(key)! : null;
      },
      key(index: number) {
        return Array.from(store.keys())[index] ?? null;
      },
      removeItem(key: string) {
        store.delete(key);
      },
      setItem(key: string, value: string) {
        store.set(key, value);
      },
    };

    Object.defineProperty(window, "localStorage", {
      value: storage,
      configurable: true,
      writable: true,
    });
  }

  if (typeof window.matchMedia !== "function") {
    window.matchMedia = (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });
  }

  if (typeof window.ResizeObserver !== "function") {
    class ResizeObserverMock implements ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    }

    Object.defineProperty(window, "ResizeObserver", {
      value: ResizeObserverMock,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(globalThis, "ResizeObserver", {
      value: ResizeObserverMock,
      configurable: true,
      writable: true,
    });
  }
}

afterEach(() => {
  cleanup();
});
