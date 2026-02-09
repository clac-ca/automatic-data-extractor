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
      types: new Set<string>() as ViewTransitionTypeSet,
    };
  });

  Object.defineProperty(document, "startViewTransition", {
    configurable: true,
    writable: true,
    value: startViewTransition,
  });

  return startViewTransition;
}

function extractClipRadius(clipPath: string): number {
  const match = /circle\(([\d.]+)px/.exec(clipPath);
  return match ? Number(match[1]) : Number.NaN;
}

function extractClipOrigin(clipPath: string): { x: number; y: number } {
  const match = /at ([\d.-]+)px ([\d.-]+)px/.exec(clipPath);
  return {
    x: match ? Number(match[1]) : Number.NaN,
    y: match ? Number(match[2]) : Number.NaN,
  };
}

function extractMaskPxValues(maskImage: string): number[] {
  return Array.from(maskImage.matchAll(/([\d.]+)px/g)).map((entry) => Number(entry[1]));
}

function extractMaskWaveRadius(maskImage: string): number {
  const pxValues = extractMaskPxValues(maskImage);
  if (pxValues.length < 4) {
    return Number.NaN;
  }
  return pxValues[pxValues.length - 2];
}

describe("modeTransition", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    document.documentElement.removeAttribute("data-mode-transition");
    document.documentElement.style.removeProperty("--mode-transition-origin-x");
    document.documentElement.style.removeProperty("--mode-transition-origin-y");
    document.documentElement.style.removeProperty("--mode-transition-radius");
    document.documentElement.style.removeProperty("--mode-transition-feather");
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
    const firstCall = animate.mock.calls.at(0);
    expect(firstCall).toBeDefined();
    const [frames, options] = firstCall as unknown as [
      Array<{ clipPath: string; filter?: string; offset?: number }>,
      KeyframeAnimationOptions,
    ];
    expect(frames).toHaveLength(4);
    expect(frames.map((frame) => frame.offset)).toEqual([0, 0.22, 0.72, 1]);
    expect(frames[0].clipPath).toContain(
      `circle(${MOTION_PROFILE.toDark.startRadiusPx + MOTION_PROFILE.toDark.featherPx}px at 120px 80px)`,
    );
    expect(frames[0].filter).toContain("drop-shadow");
    const radii = frames.map((frame) => extractClipRadius(frame.clipPath));
    expect(radii[1]).toBeGreaterThan(radii[0]);
    expect(radii[2]).toBeGreaterThan(radii[1]);
    expect(radii[3]).toBeGreaterThan(radii[2]);
    const origins = frames.map((frame) => extractClipOrigin(frame.clipPath));
    expect(origins[0]).toEqual({ x: 120, y: 80 });
    expect(
      origins.some((originPoint, index) => index > 0 && (originPoint.x !== 120 || originPoint.y !== 80)),
    ).toBe(true);
    expect((frames[1].filter?.match(/drop-shadow\(/g) ?? []).length).toBe(2);
    expect(options.pseudoElement).toBe("::view-transition-new(root)");
    expect(Number(options.duration)).toBeGreaterThanOrEqual(MOTION_PROFILE.toDark.minDurationMs);
    expect(Number(options.duration)).toBeLessThanOrEqual(MOTION_PROFILE.toDark.maxDurationMs);
    expect(options.easing).toBe(MOTION_PROFILE.toDark.easing);
    expect(document.documentElement).not.toHaveAttribute("data-mode-transition");
    expect(document.documentElement.style.getPropertyValue("--mode-transition-feather")).toBe("");
  });

  it("uses outward reveal when exiting dark mode", async () => {
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
    expect(animate).toHaveBeenCalledTimes(1);
    const firstCall = animate.mock.calls.at(0);
    expect(firstCall).toBeDefined();
    const [frames, options] = firstCall as unknown as [
      Array<{ clipPath: string; filter?: string; offset?: number }>,
      KeyframeAnimationOptions,
    ];
    expect(frames).toHaveLength(4);
    expect(frames.map((frame) => frame.offset)).toEqual([0, 0.22, 0.72, 1]);
    expect(frames[0].clipPath).toContain(
      `circle(${MOTION_PROFILE.toLight.startRadiusPx + MOTION_PROFILE.toLight.featherPx}px at 12px 18px)`,
    );
    const radii = frames.map((frame) => extractClipRadius(frame.clipPath));
    expect(radii[1]).toBeGreaterThan(radii[0]);
    expect(radii[2]).toBeGreaterThan(radii[1]);
    expect(radii[3]).toBeGreaterThan(radii[2]);
    expect((frames[1].filter?.match(/drop-shadow\(/g) ?? []).length).toBe(2);
    expect(options.pseudoElement).toBe("::view-transition-new(root)");
    expect(Number(options.duration)).toBeGreaterThanOrEqual(MOTION_PROFILE.toLight.minDurationMs);
    expect(Number(options.duration)).toBeLessThanOrEqual(MOTION_PROFILE.toLight.maxDurationMs);
    expect(options.easing).toBe(MOTION_PROFILE.toLight.easing);
  });

  it("uses fallback mask when view transitions are unavailable", async () => {
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
    const initialStops = extractMaskPxValues(overlay?.style.maskImage ?? "");
    expect(initialStops.length).toBeGreaterThanOrEqual(6);
    const primaryRadiusStop = initialStops.at(-3);
    const trailingRadiusStop = initialStops.at(-2);
    expect(primaryRadiusStop).toBeDefined();
    expect(trailingRadiusStop).toBeDefined();
    expect(trailingRadiusStop!).toBeGreaterThan(primaryRadiusStop!);

    const fullRadius = Math.max(
      Math.hypot(0 - 30, 0 - 40),
      Math.hypot(window.innerWidth - 30, 0 - 40),
      Math.hypot(0 - 30, window.innerHeight - 40),
      Math.hypot(window.innerWidth - 30, window.innerHeight - 40),
    );
    raf.step(Math.round(MOTION_PROFILE.toDark.maxDurationMs * 0.22));
    const stagedRadius = extractMaskWaveRadius(overlay?.style.maskImage ?? "");
    expect(stagedRadius).toBeGreaterThan(fullRadius * 0.25);
    expect(stagedRadius).toBeLessThan(fullRadius);

    raf.flush(MOTION_PROFILE.toDark.maxDurationMs + 80);
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
    raf.flush(Math.max(MOTION_PROFILE.toDark.maxDurationMs, MOTION_PROFILE.toLight.maxDurationMs) + 80);

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
