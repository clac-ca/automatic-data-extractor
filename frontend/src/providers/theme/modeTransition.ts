import type { ResolvedMode } from "./index";

export type ModeTransitionSource = "user" | "system";

export type TransitionOrigin = {
  x: number;
  y: number;
};

export type SetModePreferenceOptions = {
  animate?: boolean;
  origin?: TransitionOrigin;
  source?: ModeTransitionSource;
};

type RunModeTransitionOptions = {
  from: ResolvedMode;
  to: ResolvedMode;
  apply: () => void;
  animate: boolean;
  origin?: TransitionOrigin;
  durationMs?: number;
};

export const THEME_MODE_ANCHOR_ATTR = "data-theme-mode-anchor";
export const WORKSPACE_THEME_MODE_ANCHOR = "workspace-topbar-mode-toggle";
export const MOTION_PROFILE = {
  revealExpand: {
    durationMs: 760,
    easing: "cubic-bezier(0.16, 1, 0.3, 1)",
    featherPx: 12,
    startRadiusPx: 6,
  },
  revealCollapse: {
    durationMs: 520,
    easing: "cubic-bezier(0.4, 0, 0.2, 1)",
    featherPx: 10,
    endRadiusPx: 4,
  },
  buttonPress: {
    durationMs: 120,
    leadInMs: 40,
  },
  fallbackDirectional: {
    durationMs: 420,
    easing: "cubic-bezier(0.22, 1, 0.36, 1)",
    bezier: [0.22, 1, 0.36, 1] as const,
    featherPx: 14,
  },
} as const;

export const DEFAULT_MODE_TRANSITION_DURATION_MS = MOTION_PROFILE.revealExpand.durationMs;

const MODE_TRANSITION_ATTR = "data-mode-transition";
const MODE_TRANSITION_ORIGIN_X = "--mode-transition-origin-x";
const MODE_TRANSITION_ORIGIN_Y = "--mode-transition-origin-y";
const MODE_TRANSITION_RADIUS = "--mode-transition-radius";
const MODE_TRANSITION_FEATHER = "--mode-transition-feather";
const FALLBACK_OVERLAY_ATTR = "data-mode-transition-overlay";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

type TransitionState =
  | "reveal-expand"
  | "reveal-collapse"
  | "fallback-expand"
  | "fallback-collapse";

type ActiveTransition = {
  cancel: () => void;
};

let activeTransition: ActiveTransition | null = null;

function supportsViewTransition(): boolean {
  return typeof document !== "undefined" && typeof document.startViewTransition === "function";
}

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

function shouldSkipAnimation(): boolean {
  if (typeof document === "undefined") {
    return true;
  }
  if (document.visibilityState !== "visible") {
    return true;
  }
  return false;
}

function getViewportCenter(): TransitionOrigin {
  if (typeof window === "undefined") {
    return { x: 0, y: 0 };
  }
  return {
    x: window.innerWidth / 2,
    y: window.innerHeight / 2,
  };
}

function distanceToFarthestCorner(origin: TransitionOrigin): number {
  if (typeof window === "undefined") {
    return 0;
  }
  const corners: Array<[number, number]> = [
    [0, 0],
    [window.innerWidth, 0],
    [0, window.innerHeight],
    [window.innerWidth, window.innerHeight],
  ];

  return corners.reduce((max, [x, y]) => {
    const dx = x - origin.x;
    const dy = y - origin.y;
    const distance = Math.hypot(dx, dy);
    return Math.max(max, distance);
  }, 0);
}

function setTransitionAttributes(state: TransitionState, origin: TransitionOrigin, radius: number): void {
  const root = document.documentElement;
  const feather =
    state === "reveal-expand"
      ? MOTION_PROFILE.revealExpand.featherPx
      : state === "reveal-collapse"
        ? MOTION_PROFILE.revealCollapse.featherPx
        : MOTION_PROFILE.fallbackDirectional.featherPx;
  root.setAttribute(MODE_TRANSITION_ATTR, state);
  root.style.setProperty(MODE_TRANSITION_ORIGIN_X, `${origin.x}px`);
  root.style.setProperty(MODE_TRANSITION_ORIGIN_Y, `${origin.y}px`);
  root.style.setProperty(MODE_TRANSITION_RADIUS, `${radius}px`);
  root.style.setProperty(MODE_TRANSITION_FEATHER, `${feather}px`);
}

function clearTransitionAttributes(): void {
  const root = document.documentElement;
  root.removeAttribute(MODE_TRANSITION_ATTR);
  root.style.removeProperty(MODE_TRANSITION_ORIGIN_X);
  root.style.removeProperty(MODE_TRANSITION_ORIGIN_Y);
  root.style.removeProperty(MODE_TRANSITION_RADIUS);
  root.style.removeProperty(MODE_TRANSITION_FEATHER);
}

function buildClipPath(radius: number, origin: TransitionOrigin): string {
  return `circle(${radius}px at ${origin.x}px ${origin.y}px)`;
}

function removeFallbackOverlays(): void {
  if (typeof document === "undefined") {
    return;
  }
  const overlays = document.querySelectorAll(`[${FALLBACK_OVERLAY_ATTR}]`);
  overlays.forEach((overlay) => overlay.remove());
}

function cancelInFlightTransition(): void {
  if (activeTransition) {
    activeTransition.cancel();
    activeTransition = null;
  }
  clearTransitionAttributes();
  removeFallbackOverlays();
}

function setActiveTransition(next: ActiveTransition): void {
  cancelInFlightTransition();
  activeTransition = next;
}

function clearActiveTransition(next: ActiveTransition): void {
  if (activeTransition === next) {
    activeTransition = null;
  }
}

function sampleCurve(t: number, p0: number, p1: number, p2: number, p3: number): number {
  const invT = 1 - t;
  return invT ** 3 * p0 + 3 * invT ** 2 * t * p1 + 3 * invT * t ** 2 * p2 + t ** 3 * p3;
}

function sampleCurveDerivative(t: number, p0: number, p1: number, p2: number, p3: number): number {
  const invT = 1 - t;
  return 3 * invT ** 2 * (p1 - p0) + 6 * invT * t * (p2 - p1) + 3 * t ** 2 * (p3 - p2);
}

function cubicBezierProgress(
  progress: number,
  bezier: readonly [number, number, number, number],
): number {
  if (progress <= 0 || progress >= 1) {
    return progress;
  }

  const [x1, y1, x2, y2] = bezier;
  let t = progress;
  for (let index = 0; index < 5; index += 1) {
    const estimate = sampleCurve(t, 0, x1, x2, 1) - progress;
    const derivative = sampleCurveDerivative(t, 0, x1, x2, 1);
    if (Math.abs(derivative) < 1e-6) {
      break;
    }
    t -= estimate / derivative;
    t = Math.min(1, Math.max(0, t));
  }

  return sampleCurve(t, 0, y1, y2, 1);
}

function applyFallbackMask(
  overlay: HTMLDivElement,
  direction: "expand" | "collapse",
  origin: TransitionOrigin,
  radius: number,
  featherPx: number,
): void {
  const inner = Math.max(0, radius - featherPx);
  const outer = Math.max(inner + 0.001, radius + featherPx);
  const gradient =
    direction === "expand"
      ? `radial-gradient(circle at ${origin.x}px ${origin.y}px, transparent ${inner}px, rgb(0 0 0) ${outer}px)`
      : `radial-gradient(circle at ${origin.x}px ${origin.y}px, rgb(0 0 0) ${inner}px, transparent ${outer}px)`;

  overlay.style.maskImage = gradient;
  overlay.style.webkitMaskImage = gradient;
}

async function runViewRevealTransition({
  from,
  to,
  apply,
  origin: explicitOrigin,
  durationMs,
}: Omit<RunModeTransitionOptions, "animate">): Promise<void> {
  const origin = explicitOrigin ?? getViewportCenter();
  const radius = distanceToFarthestCorner(origin);
  const isEnteringDark = from === "light" && to === "dark";
  const transitionState: TransitionState = isEnteringDark ? "reveal-expand" : "reveal-collapse";
  const profile = isEnteringDark ? MOTION_PROFILE.revealExpand : MOTION_PROFILE.revealCollapse;
  const revealProfile = MOTION_PROFILE.revealExpand;
  const collapseProfile = MOTION_PROFILE.revealCollapse;
  const pseudoElement = isEnteringDark ? "::view-transition-new(root)" : "::view-transition-old(root)";
  const startingRadius = isEnteringDark ? revealProfile.startRadiusPx : radius;
  const endingRadius = isEnteringDark ? radius : collapseProfile.endRadiusPx;
  let hasApplied = false;
  let isCanceled = false;
  let animation: Animation | null = null;
  const active: ActiveTransition = {
    cancel: () => {
      isCanceled = true;
      animation?.cancel();
      clearTransitionAttributes();
      removeFallbackOverlays();
    },
  };

  setActiveTransition(active);
  setTransitionAttributes(transitionState, origin, radius);

  try {
    const transition = document.startViewTransition?.(() => {
      hasApplied = true;
      apply();
    });

    if (!transition) {
      hasApplied = true;
      apply();
      return;
    }

    await transition.ready;
    if (isCanceled) {
      return;
    }

    const dropShadowFrom = isEnteringDark
      ? `drop-shadow(0 0 ${Math.round(profile.featherPx * 1.5)}px rgba(0, 0, 0, 0.22))`
      : `drop-shadow(0 0 ${profile.featherPx}px rgba(0, 0, 0, 0.14))`;
    const dropShadowTo = isEnteringDark
      ? `drop-shadow(0 0 ${profile.featherPx}px rgba(0, 0, 0, 0.1))`
      : `drop-shadow(0 0 ${profile.featherPx}px rgba(0, 0, 0, 0.14))`;

    animation = document.documentElement.animate(
      [
        { clipPath: buildClipPath(startingRadius, origin), filter: dropShadowFrom },
        { clipPath: buildClipPath(endingRadius, origin), filter: dropShadowTo },
      ],
      {
        duration: durationMs ?? profile.durationMs,
        easing: profile.easing,
        fill: "both",
        pseudoElement,
      },
    );

    await Promise.allSettled([animation.finished.catch(() => null), transition.finished.catch(() => null)]);
  } catch (error) {
    if (!hasApplied) {
      throw error;
    }
  } finally {
    clearActiveTransition(active);
    clearTransitionAttributes();
  }
}

async function runDirectionalFallbackTransition({
  from,
  to,
  apply,
  origin: explicitOrigin,
  durationMs,
}: Omit<RunModeTransitionOptions, "animate">): Promise<void> {
  const origin = explicitOrigin ?? getViewportCenter();
  const radius = distanceToFarthestCorner(origin);
  const isEnteringDark = from === "light" && to === "dark";
  const transitionState: TransitionState = isEnteringDark ? "fallback-expand" : "fallback-collapse";
  const direction = isEnteringDark ? "expand" : "collapse";
  const fallbackProfile = MOTION_PROFILE.fallbackDirectional;
  const duration = durationMs ?? fallbackProfile.durationMs;
  const feather = fallbackProfile.featherPx;
  const startRadius = isEnteringDark ? 0 : radius;
  const endRadius = isEnteringDark ? radius : 0;
  const root = document.documentElement;
  const overlay = document.createElement("div");
  const bodyColor = getComputedStyle(document.body).backgroundColor;
  const rootColor = getComputedStyle(document.documentElement).backgroundColor;
  const overlayColor = bodyColor || rootColor || "rgb(255, 255, 255)";
  let rafId = 0;
  let isCanceled = false;
  let resolveTransition: (() => void) | null = null;
  const transitionPromise = new Promise<void>((resolve) => {
    resolveTransition = resolve;
  });
  const active: ActiveTransition = {
    cancel: () => {
      isCanceled = true;
      if (rafId) {
        cancelAnimationFrame(rafId);
      }
      overlay.remove();
      clearTransitionAttributes();
      removeFallbackOverlays();
      resolveTransition?.();
    },
  };

  setActiveTransition(active);
  setTransitionAttributes(transitionState, origin, radius);

  overlay.setAttribute(FALLBACK_OVERLAY_ATTR, "true");
  overlay.style.position = "fixed";
  overlay.style.inset = "0";
  overlay.style.pointerEvents = "none";
  overlay.style.zIndex = "var(--app-z-tooltip)";
  overlay.style.backgroundColor = overlayColor;
  overlay.style.willChange = "mask-image, -webkit-mask-image";
  overlay.style.contain = "strict";
  document.body.appendChild(overlay);

  apply();

  const easing = fallbackProfile.bezier;
  const startedAt = performance.now();

  const frame = (now: number) => {
    if (isCanceled) {
      return;
    }

    const elapsed = Math.max(0, now - startedAt);
    const rawProgress = Math.min(1, elapsed / duration);
    const easedProgress = cubicBezierProgress(rawProgress, easing);
    const currentRadius = startRadius + (endRadius - startRadius) * easedProgress;

    applyFallbackMask(overlay, direction, origin, currentRadius, feather);

    if (rawProgress >= 1) {
      overlay.remove();
      clearTransitionAttributes();
      clearActiveTransition(active);
      resolveTransition?.();
      return;
    }

    rafId = requestAnimationFrame(frame);
  };

  try {
    applyFallbackMask(overlay, direction, origin, startRadius, feather);
    rafId = requestAnimationFrame(frame);
    await transitionPromise;
  } finally {
    overlay.remove();
    clearTransitionAttributes();
    clearActiveTransition(active);
    if (root.getAttribute(MODE_TRANSITION_ATTR)?.startsWith("fallback")) {
      root.removeAttribute(MODE_TRANSITION_ATTR);
    }
  }
}

export async function runModeTransition(options: RunModeTransitionOptions): Promise<void> {
  const { from, to, apply, animate, origin, durationMs } = options;

  if (typeof document === "undefined" || from === to) {
    apply();
    return;
  }

  if (!animate || prefersReducedMotion() || shouldSkipAnimation()) {
    apply();
    return;
  }

  cancelInFlightTransition();

  if (!supportsViewTransition()) {
    await runDirectionalFallbackTransition({ from, to, apply, origin, durationMs });
    return;
  }

  try {
    await runViewRevealTransition({ from, to, apply, origin, durationMs });
  } catch (error) {
    console.warn("Failed to run mode transition animation", error);
    clearTransitionAttributes();
    apply();
  }
}

export function findModeTransitionOrigin(anchorName = WORKSPACE_THEME_MODE_ANCHOR): TransitionOrigin | undefined {
  if (typeof document === "undefined") {
    return undefined;
  }

  const anchor = document.querySelector<HTMLElement>(`[${THEME_MODE_ANCHOR_ATTR}="${anchorName}"]`);
  if (!anchor) {
    return undefined;
  }

  const rect = anchor.getBoundingClientRect();
  return {
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2,
  };
}
