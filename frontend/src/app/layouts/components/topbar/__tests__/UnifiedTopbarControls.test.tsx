import userEvent from "@testing-library/user-event";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { UnifiedTopbarControls } from "@/app/layouts/components/topbar/UnifiedTopbarControls";

const mockSetModePreference = vi.fn();
const mockSetPreviewTheme = vi.fn();
const mockSetTheme = vi.fn();
const mockUseTheme = vi.fn();
const mockNavigate = vi.fn();

vi.mock("@/providers/auth/SessionContext", () => ({
  useSession: () => ({
    user: {
      display_name: "Test User",
      email: "test@example.com",
    },
  }),
}));

vi.mock("@/hooks/auth/useGlobalPermissions", () => ({
  useGlobalPermissions: () => ({
    canAccessOrganizationSettings: true,
  }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/providers/theme", () => ({
  BUILTIN_THEMES: [{ id: "default", label: "Default", description: "Default theme" }],
  MODE_OPTIONS: [
    { value: "system", label: "System", description: "Match your device" },
    { value: "light", label: "Light", description: "Bright and clear" },
    { value: "dark", label: "Dark", description: "Low-light friendly" },
  ],
  WORKSPACE_THEME_MODE_ANCHOR: "workspace-topbar-mode-toggle",
  useTheme: () => mockUseTheme(),
}));

vi.mock("@/providers/theme/modeTransition", () => ({
  MOTION_PROFILE: {
    buttonPress: {
      durationMs: 120,
      leadInMs: 12,
    },
  },
}));

vi.mock("@/hooks/system", () => ({
  useSystemVersions: () => ({
    data: { backend: "1.0.0", engine: "1.0.0", web: "1.0.0" },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  }),
}));

function mockMatchMedia(overrides: Partial<Record<string, boolean>> = {}) {
  const implementation = vi.fn((query: string): MediaQueryList => ({
    matches: overrides[query] ?? false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: implementation,
  });
}

describe("UnifiedTopbarControls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMatchMedia();
    mockNavigate.mockReset();
    mockUseTheme.mockReturnValue({
      theme: "default",
      modePreference: "light",
      resolvedMode: "light",
      setModePreference: mockSetModePreference,
      setPreviewTheme: mockSetPreviewTheme,
      setTheme: mockSetTheme,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    document.documentElement.removeAttribute("data-mode-intent-active");
    document.documentElement.removeAttribute("data-mode-intent-target");
    document.documentElement.style.removeProperty("--mode-intent-x");
    document.documentElement.style.removeProperty("--mode-intent-y");
    document.documentElement.style.removeProperty("--mode-intent-strength");
    document.documentElement.style.removeProperty("--mode-intent-angle");
    document.documentElement.style.removeProperty("--mode-intent-distance");
  });

  it("toggles between light and dark from the primary mode button", async () => {
    vi.useFakeTimers();
    render(<UnifiedTopbarControls />);

    const toggleButton = screen.getByRole("button", { name: "Switch to dark mode" });
    vi.spyOn(toggleButton, "getBoundingClientRect").mockReturnValue({
      left: 10,
      top: 20,
      width: 30,
      height: 40,
      right: 40,
      bottom: 60,
      x: 10,
      y: 20,
      toJSON: () => "",
    } as DOMRect);

    fireEvent.click(toggleButton);
    const iconDrift = toggleButton.querySelector<HTMLElement>("[data-mode-icon-drift]");

    expect(toggleButton).toHaveAttribute("data-pressing", "true");
    expect(iconDrift).toHaveAttribute("data-drift", "to-dark");
    expect(mockSetModePreference).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(11);
    });
    expect(mockSetModePreference).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(mockSetModePreference).toHaveBeenCalledWith(
      "dark",
      expect.objectContaining({
        animate: true,
        source: "user",
        origin: { x: 25, y: 40 },
      }),
    );

    act(() => {
      vi.advanceTimersByTime(108);
    });
    expect(toggleButton).toHaveAttribute("data-pressing", "false");
    expect(iconDrift).toHaveAttribute("data-drift", "idle");
  });

  it("applies pointer-proximity intent cue near the mode button", () => {
    const rafSpy = vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    const cancelRafSpy = vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
    render(<UnifiedTopbarControls />);

    const toggleButton = screen.getByRole("button", { name: "Switch to dark mode" });
    vi.spyOn(toggleButton, "getBoundingClientRect").mockReturnValue({
      left: 10,
      top: 20,
      width: 30,
      height: 40,
      right: 40,
      bottom: 60,
      x: 10,
      y: 20,
      toJSON: () => "",
    } as DOMRect);

    fireEvent.pointerEnter(toggleButton, { clientX: 26, clientY: 42 });
    fireEvent.pointerMove(window, { clientX: 26, clientY: 42 });

    expect(document.documentElement).toHaveAttribute("data-mode-intent-active", "true");
    expect(document.documentElement).toHaveAttribute("data-mode-intent-target", "dark");
    expect(document.documentElement.style.getPropertyValue("--mode-intent-x")).toBe("25px");
    expect(document.documentElement.style.getPropertyValue("--mode-intent-y")).toBe("40px");
    expect(Number(document.documentElement.style.getPropertyValue("--mode-intent-strength"))).toBeGreaterThan(0);
    expect(document.documentElement.style.getPropertyValue("--mode-intent-angle")).toContain("deg");
    expect(document.documentElement.style.getPropertyValue("--mode-intent-distance")).toContain("px");
    expect(toggleButton.style.getPropertyValue("--mode-button-intent")).not.toBe("0");
    expect(Number(toggleButton.style.getPropertyValue("--mode-button-limb"))).toBeGreaterThan(0);

    rafSpy.mockRestore();
    cancelRafSpy.mockRestore();
  });

  it("runs a focus pulse intent cue and clears it", () => {
    vi.useFakeTimers();
    render(<UnifiedTopbarControls />);

    const toggleButton = screen.getByRole("button", { name: "Switch to dark mode" });
    vi.spyOn(toggleButton, "getBoundingClientRect").mockReturnValue({
      left: 10,
      top: 20,
      width: 30,
      height: 40,
      right: 40,
      bottom: 60,
      x: 10,
      y: 20,
      toJSON: () => "",
    } as DOMRect);

    fireEvent.focus(toggleButton);
    expect(document.documentElement).toHaveAttribute("data-mode-intent-active", "true");
    expect(document.documentElement.style.getPropertyValue("--mode-intent-strength")).toBe("0.320");
    expect(toggleButton.style.getPropertyValue("--mode-button-intent")).toBe("0.516");
    expect(Number(toggleButton.style.getPropertyValue("--mode-button-limb"))).toBeGreaterThan(0);

    act(() => {
      vi.advanceTimersByTime(260);
    });
    expect(document.documentElement.style.getPropertyValue("--mode-intent-strength")).toBe("0");

    act(() => {
      vi.advanceTimersByTime(260);
    });
    expect(document.documentElement).not.toHaveAttribute("data-mode-intent-active");
  });

  it("disables proximity intent cue for coarse pointers but keeps keyboard focus pulse", () => {
    mockMatchMedia({
      "(pointer: coarse)": true,
    });

    const rafSpy = vi.spyOn(window, "requestAnimationFrame");
    render(<UnifiedTopbarControls />);

    const toggleButton = screen.getByRole("button", { name: "Switch to dark mode" });
    vi.spyOn(toggleButton, "getBoundingClientRect").mockReturnValue({
      left: 10,
      top: 20,
      width: 30,
      height: 40,
      right: 40,
      bottom: 60,
      x: 10,
      y: 20,
      toJSON: () => "",
    } as DOMRect);

    fireEvent.pointerMove(window, { clientX: 26, clientY: 42 });
    expect(rafSpy).not.toHaveBeenCalled();
    expect(document.documentElement).not.toHaveAttribute("data-mode-intent-active");

    fireEvent.focus(toggleButton);
    expect(document.documentElement).toHaveAttribute("data-mode-intent-active", "true");
    expect(document.documentElement.style.getPropertyValue("--mode-intent-strength")).toBe("0.320");
  });

  it("disables proximity for reduced motion and uses a short focus intent fade", () => {
    vi.useFakeTimers();
    mockMatchMedia({
      "(prefers-reduced-motion: reduce)": true,
    });

    const rafSpy = vi.spyOn(window, "requestAnimationFrame");
    render(<UnifiedTopbarControls />);

    const toggleButton = screen.getByRole("button", { name: "Switch to dark mode" });
    vi.spyOn(toggleButton, "getBoundingClientRect").mockReturnValue({
      left: 10,
      top: 20,
      width: 30,
      height: 40,
      right: 40,
      bottom: 60,
      x: 10,
      y: 20,
      toJSON: () => "",
    } as DOMRect);

    fireEvent.pointerMove(window, { clientX: 26, clientY: 42 });
    expect(rafSpy).not.toHaveBeenCalled();
    expect(document.documentElement).not.toHaveAttribute("data-mode-intent-active");

    fireEvent.focus(toggleButton);
    expect(document.documentElement.style.getPropertyValue("--mode-intent-strength")).toBe("0.224");

    act(() => {
      vi.advanceTimersByTime(120);
    });
    expect(document.documentElement.style.getPropertyValue("--mode-intent-strength")).toBe("0");

    act(() => {
      vi.advanceTimersByTime(120);
    });
    expect(document.documentElement).not.toHaveAttribute("data-mode-intent-active");
  });

  it("exposes Light, Dark, and System options in the mode menu", async () => {
    const user = userEvent.setup();
    render(<UnifiedTopbarControls />);

    await user.click(screen.getByRole("button", { name: "Select color mode" }));

    expect(screen.getByText("System")).toBeInTheDocument();
    expect(screen.getByText("Light")).toBeInTheDocument();
    expect(screen.getByText("Dark")).toBeInTheDocument();
    expect(screen.getByText("Match your device")).toBeInTheDocument();
    expect(screen.getByText("Bright and clear")).toBeInTheDocument();
    expect(screen.getByText("Low-light friendly")).toBeInTheDocument();
  });

  it("maps icon drift direction for dark and light transitions", async () => {
    const user = userEvent.setup();
    mockUseTheme.mockReturnValueOnce({
      theme: "default",
      modePreference: "dark",
      resolvedMode: "dark",
      setModePreference: mockSetModePreference,
      setPreviewTheme: mockSetPreviewTheme,
      setTheme: mockSetTheme,
    });

    render(<UnifiedTopbarControls />);
    const toggleButton = screen.getByRole("button", { name: "Switch to light mode" });
    await user.click(toggleButton);
    const iconDrift = toggleButton.querySelector<HTMLElement>("[data-mode-icon-drift]");

    expect(iconDrift).toHaveAttribute("data-drift", "to-light");
  });

  it("sends animated mode options with origin coordinates when selecting from menu", async () => {
    const user = userEvent.setup();
    render(<UnifiedTopbarControls />);

    const toggleButton = screen.getByRole("button", { name: "Switch to dark mode" });
    vi.spyOn(toggleButton, "getBoundingClientRect").mockReturnValue({
      left: 30,
      top: 40,
      width: 20,
      height: 30,
      right: 50,
      bottom: 70,
      x: 30,
      y: 40,
      toJSON: () => "",
    } as DOMRect);

    await user.click(screen.getByRole("button", { name: "Select color mode" }));
    await user.click(screen.getByRole("menuitem", { name: /System/i }));

    expect(mockSetModePreference).toHaveBeenCalledWith(
      "system",
      expect.objectContaining({
        animate: true,
        source: "user",
        origin: { x: 40, y: 55 },
      }),
    );
  });

  it("navigates to account settings from the profile menu", async () => {
    const user = userEvent.setup();
    render(<UnifiedTopbarControls />);

    await user.click(screen.getByRole("button", { name: "Open profile menu" }));
    await user.click(screen.getByRole("menuitem", { name: /Account Settings/i }));

    expect(mockNavigate).toHaveBeenCalledWith("/account");
  });
});
