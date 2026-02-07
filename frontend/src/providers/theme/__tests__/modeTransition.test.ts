import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  MOTION_PROFILE,
  THEME_MODE_ANCHOR_ATTR,
  WORKSPACE_THEME_MODE_ANCHOR,
  findModeTransitionOrigin,
  runModeTransition,
} from "../modeTransition";

function mockAnimate() {
  const animate = vi.fn(() => ({ finished: Promise.resolve() } as unknown as Animation));
  Object.defineProperty(document.documentElement, "animate", {
    configurable: true,
    writable: true,
    value: animate,
  });
  return animate;
}

function mockMatchMedia(prefersReducedMotion: boolean) {
  const implementation = vi.fn((query: string): MediaQueryList => ({
    matches: query === "(prefers-reduced-motion: reduce)" ? prefersReducedMotion : false,
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

function installRafController() {
  let now = 0;
  let nextId = 0;
  const callbacks = new Map<number, FrameRequestCallback>();
  const requestSpy = vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback: FrameRequestCallback) => {
    const id = ++nextId;
    callbacks.set(id, callback);
    return id;
  });
  const cancelSpy = vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id: number) => {
    callbacks.delete(id);
  });
  const nowSpy = vi.spyOn(performance, "now").mockImplementation(() => now);

  const step = (ms: number) => {
    now += ms;
    const pending = Array.from(callbacks.entries());
    callbacks.clear();
    pending.forEach(([, callback]) => callback(now));
  };

  const flush = (durationMs: number, frameMs = 16) => {
    const steps = Math.ceil(durationMs / frameMs) + 2;
    for (let index = 0; index < steps; index += 1) {
      step(frameMs);
      if (callbacks.size === 0) {
        break;
      }
    }
  };

  return {
    step,
    flush,
    cancelSpy,
    restore() {
      requestSpy.mockRestore();
      cancelSpy.mockRestore();
      nowSpy.mockRestore();
    },
  };
}

function mockStartViewTransition(callbackImpl?: (callback: () => void) => void) {
  const startViewTransition = vi.fn((callback: () => void): ViewTransition => {
    if (callbackImpl) {
      callbackImpl(callback);
    } else {
      callback();
    }

    return {
      ready: Promise.resolve(),
      finished: Promise.resolve(),
      updateCallbackDone: Promise.resolve(),
    };
  });

  Object.defineProperty(document, "startViewTransition", {
    configurable: true,
    writable: true,
    value: startViewTransition,
  });

  return startViewTransition;
}

describe("modeTransition", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.documentElement.removeAttribute("data-mode-transition");
    document.documentElement.style.removeProperty("--mode-transition-origin-x");
    document.documentElement.style.removeProperty("--mode-transition-origin-y");
    document.documentElement.style.removeProperty("--mode-transition-radius");
    mockMatchMedia(false);
  });

  it("uses view transition reveal when supported and entering dark mode", async () => {
    const apply = vi.fn();
    const startViewTransition = mockStartViewTransition();
    const animate = mockAnimate();

    await runModeTransition({
      from: "light",
      to: "dark",
      apply,
      animate: true,
      origin: { x: 120, y: 80 },
    });

    expect(startViewTransition).toHaveBeenCalledTimes(1);
    expect(apply).toHaveBeenCalledTimes(1);
    expect(animate).toHaveBeenCalledTimes(1);
    const [frames, options] = animate.mock.calls[0] as [
      Array<{ clipPath: string }>,
      KeyframeAnimationOptions,
    ];
    expect(frames[0].clipPath).toContain(`circle(${MOTION_PROFILE.revealExpand.startRadiusPx}px at 120px 80px)`);
    expect(frames[0].filter).toContain("drop-shadow");
    expect(options.pseudoElement).toBe("::view-transition-new(root)");
    expect(options.duration).toBe(MOTION_PROFILE.revealExpand.durationMs);
    expect(options.easing).toBe(MOTION_PROFILE.revealExpand.easing);
    expect(document.documentElement).not.toHaveAttribute("data-mode-transition");
  });

  it("uses collapse direction when exiting dark mode", async () => {
    const apply = vi.fn();
    mockStartViewTransition();
    const animate = mockAnimate();

    await runModeTransition({
      from: "dark",
      to: "light",
      apply,
      animate: true,
      origin: { x: 12, y: 18 },
    });

    expect(apply).toHaveBeenCalledTimes(1);
    const [frames, options] = animate.mock.calls[0] as [
      Array<{ clipPath: string }>,
      KeyframeAnimationOptions,
    ];
    expect(frames[1].clipPath).toContain(`circle(${MOTION_PROFILE.revealCollapse.endRadiusPx}px at 12px 18px)`);
    expect(options.pseudoElement).toBe("::view-transition-old(root)");
    expect(options.duration).toBe(MOTION_PROFILE.revealCollapse.durationMs);
    expect(options.easing).toBe(MOTION_PROFILE.revealCollapse.easing);
  });

  it("uses directional fallback mask when view transitions are unavailable", async () => {
    const apply = vi.fn();
    const raf = installRafController();
    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      writable: true,
      value: undefined,
    });

    const transition = runModeTransition({
      from: "light",
      to: "dark",
      apply,
      animate: true,
      origin: { x: 30, y: 40 },
    });

    expect(apply).toHaveBeenCalledTimes(1);
    const overlay = document.querySelector<HTMLElement>("[data-mode-transition-overlay]");
    expect(overlay).not.toBeNull();
    expect(overlay?.style.maskImage).toContain("30px 40px");

    raf.flush(MOTION_PROFILE.fallbackDirectional.durationMs);
    await transition;
    raf.restore();

    expect(document.querySelector("[data-mode-transition-overlay]")).toBeNull();
    expect(document.documentElement).not.toHaveAttribute("data-mode-transition");
  });

  it("skips animation when reduced motion is enabled", async () => {
    const apply = vi.fn();
    const startViewTransition = mockStartViewTransition();
    mockAnimate();
    mockMatchMedia(true);

    await runModeTransition({
      from: "light",
      to: "dark",
      apply,
      animate: true,
      origin: { x: 10, y: 20 },
    });

    expect(startViewTransition).not.toHaveBeenCalled();
    expect(apply).toHaveBeenCalledTimes(1);
  });

  it("falls back to immediate apply when view transition throws", async () => {
    const apply = vi.fn();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      writable: true,
      value: vi.fn(() => {
        throw new Error("boom");
      }),
    });
    const animate = mockAnimate();

    await runModeTransition({
      from: "light",
      to: "dark",
      apply,
      animate: true,
      origin: { x: 10, y: 20 },
    });

    expect(apply).toHaveBeenCalledTimes(1);
    expect(animate).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalled();
  });

  it("cancels in-flight fallback transitions when a new toggle occurs", async () => {
    const raf = installRafController();
    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      writable: true,
      value: undefined,
    });
    const firstApply = vi.fn();
    const secondApply = vi.fn();

    const firstTransition = runModeTransition({
      from: "light",
      to: "dark",
      apply: firstApply,
      animate: true,
      origin: { x: 10, y: 20 },
    });
    raf.step(100);

    const secondTransition = runModeTransition({
      from: "dark",
      to: "light",
      apply: secondApply,
      animate: true,
      origin: { x: 20, y: 30 },
    });
    raf.flush(MOTION_PROFILE.fallbackDirectional.durationMs);

    await Promise.all([firstTransition, secondTransition]);
    raf.restore();

    expect(firstApply).toHaveBeenCalledTimes(1);
    expect(secondApply).toHaveBeenCalledTimes(1);
    expect(document.querySelectorAll("[data-mode-transition-overlay]").length).toBe(0);
  });

  it("skips animation when tab visibility is hidden", async () => {
    const apply = vi.fn();
    const startViewTransition = mockStartViewTransition();
    const visibilitySpy = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");

    await runModeTransition({
      from: "light",
      to: "dark",
      apply,
      animate: true,
      origin: { x: 10, y: 20 },
    });

    expect(startViewTransition).not.toHaveBeenCalled();
    expect(apply).toHaveBeenCalledTimes(1);
    visibilitySpy.mockRestore();
  });

  it("resolves transition origin from the mode toggle anchor", () => {
    const anchor = document.createElement("button");
    anchor.setAttribute(THEME_MODE_ANCHOR_ATTR, WORKSPACE_THEME_MODE_ANCHOR);
    anchor.getBoundingClientRect = () =>
      ({
        left: 40,
        top: 20,
        width: 30,
        height: 10,
      }) as DOMRect;
    document.body.appendChild(anchor);

    const origin = findModeTransitionOrigin();
    expect(origin).toEqual({ x: 55, y: 25 });

    anchor.remove();
  });
});
