import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeProvider } from "../ThemeProvider";
import { useTheme } from "../useTheme";
import { MODE_STORAGE_KEY } from "../themeStorage";
import { runModeTransition } from "../modeTransition";

const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

vi.mock("../modeTransition", async () => {
  const actual = await vi.importActual<typeof import("../modeTransition")>("../modeTransition");
  return {
    ...actual,
    runModeTransition: vi.fn(async (options: { apply: () => void }) => {
      options.apply();
    }),
    findModeTransitionOrigin: vi.fn(() => ({ x: 120, y: 80 })),
  };
});

function installMatchMedia(initialDarkMode = false) {
  let prefersDark = initialDarkMode;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string): MediaQueryList => ({
      matches: query === DARK_MODE_QUERY ? prefersDark : false,
      media: query,
      onchange: null,
      addEventListener: (type: string, listener: EventListenerOrEventListenerObject) => {
        if (query !== DARK_MODE_QUERY || type !== "change") {
          return;
        }
        const callback = listener as (event: MediaQueryListEvent) => void;
        listeners.add(callback);
      },
      removeEventListener: (type: string, listener: EventListenerOrEventListenerObject) => {
        if (query !== DARK_MODE_QUERY || type !== "change") {
          return;
        }
        const callback = listener as (event: MediaQueryListEvent) => void;
        listeners.delete(callback);
      },
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });

  return {
    setDarkMode(next: boolean) {
      prefersDark = next;
      for (const listener of listeners) {
        listener({ matches: next, media: DARK_MODE_QUERY } as MediaQueryListEvent);
      }
    },
  };
}

function ThemeProbe() {
  const { modePreference, resolvedMode } = useTheme();
  return (
    <div>
      <span data-testid="mode-preference">{modePreference}</span>
      <span data-testid="resolved-mode">{resolvedMode}</span>
    </div>
  );
}

describe("ThemeProvider mode transitions", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("defaults to light mode when storage is empty", () => {
    installMatchMedia(false);

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("mode-preference")).toHaveTextContent("light");
    expect(screen.getByTestId("resolved-mode")).toHaveTextContent("light");
  });

  it("preserves existing mode preference from storage", () => {
    installMatchMedia(false);
    localStorage.setItem(MODE_STORAGE_KEY, JSON.stringify("dark"));

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("mode-preference")).toHaveTextContent("dark");
    expect(screen.getByTestId("resolved-mode")).toHaveTextContent("dark");
  });

  it("animates system-mode OS changes through runModeTransition", async () => {
    const media = installMatchMedia(false);
    localStorage.setItem(MODE_STORAGE_KEY, JSON.stringify("system"));

    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    act(() => {
      media.setDarkMode(true);
    });

    await waitFor(() => {
      expect(runModeTransition).toHaveBeenCalledTimes(1);
    });

    expect(runModeTransition).toHaveBeenCalledWith(
      expect.objectContaining({
        from: "light",
        to: "dark",
        animate: true,
      }),
    );
    expect(screen.getByTestId("resolved-mode")).toHaveTextContent("dark");
  });
});
