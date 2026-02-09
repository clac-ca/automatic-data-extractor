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
export const ORGANIC_STYLE_VERSION = "v2-orbital-shear";
const REVEAL_PHASE_OFFSETS = [0, 0.22, 0.72, 1] as const;
const REVEAL_PHASE_TARGETS = [0, 0.3, 0.92, 1] as const;

export const MOTION_PROFILE = {
  revealPhases: {
    offsets: REVEAL_PHASE_OFFSETS,
    targets: REVEAL_PHASE_TARGETS,
  },
  toDark: {
    minDurationMs: 760,
    maxDurationMs: 920,
    easing: "linear",
    featherPx: 22,
    haloPx: 18,
    startRadiusPx: 6,
  },
  toLight: {
    minDurationMs: 700,
    maxDurationMs: 860,
    easing: "linear",
    featherPx: 18,
    haloPx: 12,
    startRadiusPx: 6,
  },
  buttonPress: {
    durationMs: 120,
    leadInMs: 12,
  },
  fallback: {
    featherBoostPx: 2,
  },
  organic: {
    shearMaxPx: 7,
    shearFrameMultipliers: [0, 1, 0.35, 0] as const,
    penumbraLagPxDark: 12,
    penumbraLagPxLight: 10,
    secondaryShadowStrengthDark: [0.11, 0.16, 0.07, 0.03] as const,
    secondaryShadowStrengthLight: [0.09, 0.13, 0.06, 0.02] as const,
  },
} as const;

export const DEFAULT_MODE_TRANSITION_DURATION_MS = Math.round(
  (MOTION_PROFILE.toDark.minDurationMs + MOTION_PROFILE.toDark.maxDurationMs) / 2,
);

const MODE_TRANSITION_ATTR = "data-mode-transition";
const MODE_TRANSITION_ORIGIN_X = "--mode-transition-origin-x";
const MODE_TRANSITION_ORIGIN_Y = "--mode-transition-origin-y";
const MODE_TRANSITION_RADIUS = "--mode-transition-radius";
const MODE_TRANSITION_FEATHER = "--mode-transition-feather";
const FALLBACK_OVERLAY_ATTR = "data-mode-transition-overlay";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

type TransitionState =
  | "reveal-dark"
  | "reveal-light"
  | "fallback-dark"
  | "fallback-light";

type ActiveTransition = {
  cancel: () => void;
};

type DirectionalMotionProfile =
  | (typeof MOTION_PROFILE)["toDark"]
  | (typeof MOTION_PROFILE)["toLight"];

type TransitionAttributes = {
  featherPx: number;
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

function resolveDurationMs(
  profile: DirectionalMotionProfile,
  radius: number,
  explicitDurationMs?: number,
): number {
  if (typeof explicitDurationMs === "number") {
    return Math.max(0, Math.round(explicitDurationMs));
  }

  if (typeof window === "undefined") {
    return Math.round((profile.minDurationMs + profile.maxDurationMs) / 2);
  }

  const viewportDiagonal = Math.hypot(window.innerWidth, window.innerHeight);
  const normalizedRadius = viewportDiagonal > 0 ? Math.min(1, Math.max(0, radius / viewportDiagonal)) : 1;
  const duration = profile.minDurationMs + (profile.maxDurationMs - profile.minDurationMs) * normalizedRadius;

  return Math.round(duration);
}

function setTransitionAttributes(
  state: TransitionState,
  origin: TransitionOrigin,
  radius: number,
  attributes: TransitionAttributes,
): void {
  const root = document.documentElement;
  root.setAttribute(MODE_TRANSITION_ATTR, state);
  root.style.setProperty(MODE_TRANSITION_ORIGIN_X, `${origin.x}px`);
  root.style.setProperty(MODE_TRANSITION_ORIGIN_Y, `${origin.y}px`);
  root.style.setProperty(MODE_TRANSITION_RADIUS, `${radius}px`);
  root.style.setProperty(MODE_TRANSITION_FEATHER, `${attributes.featherPx}px`);
}

function clearTransitionAttributes(): void {
  const root = document.documentElement;
  root.removeAttribute(MODE_TRANSITION_ATTR);
  root.style.removeProperty(MODE_TRANSITION_ORIGIN_X);
  root.style.removeProperty(MODE_TRANSITION_ORIGIN_Y);
  root.style.removeProperty(MODE_TRANSITION_RADIUS);
  root.style.removeProperty(MODE_TRANSITION_FEATHER);
}

function buildClipPath(radiusPx: number, origin: TransitionOrigin): string {
  return `circle(${Math.max(0, radiusPx)}px at ${origin.x}px ${origin.y}px)`;
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

function mapStagedProgress(rawProgress: number): number {
  if (rawProgress <= 0) {
    return 0;
  }
  if (rawProgress >= 1) {
    return 1;
  }

  const offsets = MOTION_PROFILE.revealPhases.offsets;
  const targets = MOTION_PROFILE.revealPhases.targets;

  // Piecewise interpolation gives us explicit engage/carry/settle velocity changes.
  for (let index = 1; index < offsets.length; index += 1) {
    const previousOffset = offsets[index - 1];
    const nextOffset = offsets[index];
    if (rawProgress > nextOffset) {
      continue;
    }

    const range = Math.max(1e-6, nextOffset - previousOffset);
    const localProgress = (rawProgress - previousOffset) / range;
    const previousTarget = targets[index - 1];
    const nextTarget = targets[index];
    return previousTarget + (nextTarget - previousTarget) * localProgress;
  }

  return 1;
}

function resolveIntentAngleDeg(origin: TransitionOrigin): number {
  if (typeof document !== "undefined") {
    const cssAngle = Number.parseFloat(document.documentElement.style.getPropertyValue("--mode-intent-angle"));
    if (Number.isFinite(cssAngle)) {
      return cssAngle;
    }
  }

  const viewportCenter = getViewportCenter();
  const deltaX = viewportCenter.x - origin.x;
  const deltaY = viewportCenter.y - origin.y;
  if (deltaX === 0 && deltaY === 0) {
    return 90;
  }
  return (Math.atan2(deltaY, deltaX) * 180) / Math.PI;
}

function applyFallbackMask(
  overlay: HTMLDivElement,
  origin: TransitionOrigin,
  radius: number,
  featherPx: number,
  trailingLagPx: number,
  stagedProgress: number,
): void {
  const inner = Math.max(0, radius - featherPx);
  const trailingRadius = Math.max(radius + 0.001, radius + trailingLagPx * stagedProgress);
  const trailingOuter = Math.max(trailingRadius + 0.001, trailingRadius + featherPx * 1.18);
  const edgeAlpha = 0.72;
  const trailingAlpha = 0.26;

  const gradient = `radial-gradient(circle at ${origin.x}px ${origin.y}px, transparent ${inner}px, rgb(0 0 0 / ${edgeAlpha}) ${radius}px, rgb(0 0 0 / ${trailingAlpha}) ${trailingRadius}px, rgb(0 0 0) ${trailingOuter}px)`;

  overlay.style.maskImage = gradient;
  overlay.style.webkitMaskImage = gradient;
}

function resolveMotionProfile(targetMode: ResolvedMode): DirectionalMotionProfile {
  return targetMode === "dark" ? MOTION_PROFILE.toDark : MOTION_PROFILE.toLight;
}

function resolveRevealFilter(
  profile: DirectionalMotionProfile,
  targetMode: ResolvedMode,
  phaseIndex: number,
  shearAngleDeg: number,
): string {
  const spreads = targetMode === "dark" ? [1.5, 1.95, 1.1, 0.7] : [1.3, 1.7, 0.95, 0.35];
  const alphas = targetMode === "dark" ? [0.16, 0.22, 0.1, 0.05] : [0.14, 0.18, 0.08, 0];
  const secondaryStrengths =
    targetMode === "dark"
      ? MOTION_PROFILE.organic.secondaryShadowStrengthDark
      : MOTION_PROFILE.organic.secondaryShadowStrengthLight;
  const lagPx = targetMode === "dark" ? MOTION_PROFILE.organic.penumbraLagPxDark : MOTION_PROFILE.organic.penumbraLagPxLight;

  const spread = spreads[Math.min(phaseIndex, spreads.length - 1)];
  const primaryAlpha = alphas[Math.min(phaseIndex, alphas.length - 1)];
  const secondaryAlpha = secondaryStrengths[Math.min(phaseIndex, secondaryStrengths.length - 1)];
  if (primaryAlpha <= 0 && secondaryAlpha <= 0) {
    return "drop-shadow(0 0 0 rgba(0, 0, 0, 0))";
  }

  const angleRad = (shearAngleDeg * Math.PI) / 180;
  const secondaryOffsetScale = 0.34;
  const secondaryOffsetX = Math.cos(angleRad) * lagPx * secondaryOffsetScale;
  const secondaryOffsetY = Math.sin(angleRad) * lagPx * secondaryOffsetScale;
  const primaryBlur = Math.round(profile.haloPx * spread);
  const secondaryBlur = Math.round(primaryBlur + lagPx * 0.42);
  const primaryShadow = `drop-shadow(0 0 ${primaryBlur}px rgba(0, 0, 0, ${Math.max(0, primaryAlpha).toFixed(3)}))`;
  const secondaryShadow = `drop-shadow(${secondaryOffsetX.toFixed(2)}px ${secondaryOffsetY.toFixed(2)}px ${secondaryBlur}px rgba(0, 0, 0, ${Math.max(0, secondaryAlpha).toFixed(3)}))`;

  return `${primaryShadow} ${secondaryShadow}`;
}

function resolveStagedRevealKeyframes(
  profile: DirectionalMotionProfile,
  targetMode: ResolvedMode,
  origin: TransitionOrigin,
  radius: number,
): Keyframe[] {
  const phases = MOTION_PROFILE.revealPhases;
  const travel = Math.max(0, radius - profile.startRadiusPx);
  const intentAngleDeg = resolveIntentAngleDeg(origin);
  const intentAngleRad = (intentAngleDeg * Math.PI) / 180;

  return phases.targets.map((phaseTarget, index) => {
    const clipRadius = profile.startRadiusPx + travel * phaseTarget + profile.featherPx;
    const shearMagnitude =
      MOTION_PROFILE.organic.shearMaxPx *
      MOTION_PROFILE.organic.shearFrameMultipliers[Math.min(index, MOTION_PROFILE.organic.shearFrameMultipliers.length - 1)];
    // Offset the center slightly during early/mid phases so the wavefront feels less mechanically uniform.
    const shearedOrigin = {
      x: origin.x + Math.cos(intentAngleRad) * shearMagnitude,
      y: origin.y + Math.sin(intentAngleRad) * shearMagnitude,
    };

    return {
      offset: phases.offsets[index],
      clipPath: buildClipPath(clipRadius, shearedOrigin),
      filter: resolveRevealFilter(profile, targetMode, index, intentAngleDeg),
    };
  });
}

async function runViewRevealTransition({
  to,
  apply,
  origin: explicitOrigin,
  durationMs,
}: Omit<RunModeTransitionOptions, "animate">): Promise<void> {
  const origin = explicitOrigin ?? getViewportCenter();
  const radius = distanceToFarthestCorner(origin);
  const targetMode: ResolvedMode = to;
  const transitionState: TransitionState = targetMode === "dark" ? "reveal-dark" : "reveal-light";
  const profile = resolveMotionProfile(targetMode);
  const pseudoElement = "::view-transition-new(root)";
  const transitionDurationMs = resolveDurationMs(profile, radius, durationMs);
  const keyframes = resolveStagedRevealKeyframes(profile, targetMode, origin, radius);

  let hasApplied = false;
  let isCanceled = false;
  let revealAnimation: Animation | null = null;

  const active: ActiveTransition = {
    cancel: () => {
      isCanceled = true;
      revealAnimation?.cancel();
      clearTransitionAttributes();
      removeFallbackOverlays();
    },
  };

  setActiveTransition(active);
  setTransitionAttributes(transitionState, origin, radius, {
    featherPx: profile.featherPx,
  });

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

    revealAnimation = document.documentElement.animate(keyframes, {
      duration: transitionDurationMs,
      easing: profile.easing,
      fill: "both",
      pseudoElement,
    });

    await Promise.allSettled([
      revealAnimation.finished.catch(() => null),
      transition.finished.catch(() => null),
    ]);
  } catch (error) {
    if (!hasApplied) {
      throw error;
    }
  } finally {
    clearActiveTransition(active);
    clearTransitionAttributes();
  }
}

async function runFallbackRevealTransition({
  to,
  apply,
  origin: explicitOrigin,
  durationMs,
}: Omit<RunModeTransitionOptions, "animate">): Promise<void> {
  const origin = explicitOrigin ?? getViewportCenter();
  const radius = distanceToFarthestCorner(origin);
  const targetMode: ResolvedMode = to;
  const transitionState: TransitionState = targetMode === "dark" ? "fallback-dark" : "fallback-light";
  const profile = resolveMotionProfile(targetMode);

  const duration = resolveDurationMs(profile, radius, durationMs);
  const feather = profile.featherPx + MOTION_PROFILE.fallback.featherBoostPx;
  const trailingLagPx =
    targetMode === "dark" ? MOTION_PROFILE.organic.penumbraLagPxDark : MOTION_PROFILE.organic.penumbraLagPxLight;
  const startRadius = 0;
  const endRadius = radius;

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
  setTransitionAttributes(transitionState, origin, radius, {
    featherPx: feather,
  });

  overlay.setAttribute(FALLBACK_OVERLAY_ATTR, "true");
  overlay.style.position = "fixed";
  overlay.style.inset = "0";
  overlay.style.pointerEvents = "none";
  overlay.style.zIndex = "calc(var(--app-z-modal) + 1)";
  overlay.style.backgroundColor = overlayColor;
  overlay.style.willChange = "mask-image, -webkit-mask-image";
  overlay.style.contain = "strict";
  document.body.appendChild(overlay);

  apply();

  const startedAt = performance.now();

  const frame = (now: number) => {
    if (isCanceled) {
      return;
    }

    const elapsed = Math.max(0, now - startedAt);
    const rawProgress = Math.min(1, elapsed / duration);
    const stagedProgress = mapStagedProgress(rawProgress);
    const currentRadius = startRadius + (endRadius - startRadius) * stagedProgress;

    applyFallbackMask(overlay, origin, currentRadius, feather, trailingLagPx, stagedProgress);

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
    applyFallbackMask(overlay, origin, startRadius, feather, trailingLagPx, 0);
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
    await runFallbackRevealTransition({ from, to, apply, origin, durationMs });
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
