import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import clsx from "clsx";
import { useNavigate } from "react-router-dom";
import { Laptop, Moon, Palette, Sun } from "lucide-react";

import { useSession } from "@/providers/auth/SessionContext";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { BUILTIN_THEMES, MODE_OPTIONS, WORKSPACE_THEME_MODE_ANCHOR, useTheme } from "@/providers/theme";
import { MOTION_PROFILE } from "@/providers/theme/modeTransition";
import { openReleaseNotes } from "@/config/release-notes";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useSystemVersions } from "@/hooks/system";
import { CheckIcon, ChevronDownIcon } from "@/components/icons";
import { getInitials } from "@/lib/format";

const WEB_VERSION_FALLBACK =
  (typeof import.meta.env.VITE_APP_VERSION === "string" ? import.meta.env.VITE_APP_VERSION : "") ||
  (typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "") ||
  "unknown";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const COARSE_POINTER_QUERY = "(pointer: coarse)";
const MODE_INTENT_ACTIVE_ATTR = "data-mode-intent-active";
const MODE_INTENT_TARGET_ATTR = "data-mode-intent-target";
const MODE_INTENT_X_VAR = "--mode-intent-x";
const MODE_INTENT_Y_VAR = "--mode-intent-y";
const MODE_INTENT_STRENGTH_VAR = "--mode-intent-strength";
const MODE_INTENT_ANGLE_VAR = "--mode-intent-angle";
const MODE_INTENT_DISTANCE_VAR = "--mode-intent-distance";
const MODE_BUTTON_INTENT_VAR = "--mode-button-intent";
const MODE_BUTTON_PARALLAX_VAR = "--mode-button-parallax";
const MODE_BUTTON_LIMB_VAR = "--mode-button-limb";

const INTENT_NEAR_FIELD_PX = 76;
const INTENT_HOVER_FLOOR = 0.26;
const INTENT_MAX = 0.62;
const INTENT_EASE_OUT_MS = 180;
const INTENT_FOCUS_PULSE_MS = 260;
const INTENT_FOCUS_PULSE_STRENGTH = 0.32;
const INTENT_REDUCED_MOTION_FADE_MS = 120;

function mediaQueryMatches(query: string): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(query).matches;
}

export function UnifiedTopbarControls() {
  const session = useSession();
  const navigate = useNavigate();
  const { canAccessOrganizationSettings } = useGlobalPermissions();
  const [versionsOpen, setVersionsOpen] = useState(false);
  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  return (
    <>
      <VersionsDialog open={versionsOpen} onOpenChange={setVersionsOpen} />
      <div className="flex min-w-0 flex-nowrap items-center gap-2">
        <div className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-background/80 p-0.5 shadow-sm backdrop-blur-sm">
          <ModeControl />
          <span className="h-5 w-px bg-border/70" aria-hidden />
          <ThemeMenu />
        </div>
        <ProfileMenu
          displayName={displayName}
          email={email}
          canAccessOrganizationSettings={canAccessOrganizationSettings}
          onOpenAccountSettings={() => navigate("/account")}
          onOpenOrganizationSettings={() => navigate("/organization")}
          onOpenVersions={() => setVersionsOpen(true)}
        />
      </div>
    </>
  );
}

function ModeControl() {
  const { modePreference, resolvedMode, setModePreference } = useTheme();
  const [open, setOpen] = useState(false);
  const [isPressing, setIsPressing] = useState(false);
  const [iconDrift, setIconDrift] = useState<"to-dark" | "to-light" | null>(null);
  const toggleButtonRef = useRef<HTMLButtonElement | null>(null);
  const applyTimeoutRef = useRef<number | null>(null);
  const pressTimeoutRef = useRef<number | null>(null);
  const intentClearTimeoutRef = useRef<number | null>(null);
  const intentFocusTimeoutRef = useRef<number | null>(null);
  const pointerRafRef = useRef<number | null>(null);
  const centerMeasureRafRef = useRef<number | null>(null);
  const lastPointerRef = useRef<{ x: number; y: number } | null>(null);
  const buttonCenterRef = useRef<{ x: number; y: number } | null>(null);
  const isHoveringRef = useRef(false);
  const isDark = resolvedMode === "dark";
  const targetMode: "dark" | "light" = isDark ? "light" : "dark";

  const prefersReducedMotion = () => mediaQueryMatches(REDUCED_MOTION_QUERY);
  const isCoarsePointer = () => mediaQueryMatches(COARSE_POINTER_QUERY);
  const canUseProximityCue = () => !prefersReducedMotion() && !isCoarsePointer();

  const setButtonIntentVisuals = (strength: number, angleDeg: number) => {
    if (!toggleButtonRef.current) {
      return;
    }
    const normalizedIntent = Math.min(1, Math.max(0, strength / INTENT_MAX));
    const parallax = Math.max(-6, Math.min(6, (angleDeg - 90) * 0.055 * normalizedIntent));
    const limb = normalizedIntent <= 0 ? 0 : Math.min(0.55, normalizedIntent * 0.55);
    toggleButtonRef.current.style.setProperty(MODE_BUTTON_INTENT_VAR, normalizedIntent.toFixed(3));
    toggleButtonRef.current.style.setProperty(MODE_BUTTON_PARALLAX_VAR, `${parallax.toFixed(2)}deg`);
    toggleButtonRef.current.style.setProperty(MODE_BUTTON_LIMB_VAR, limb.toFixed(3));
  };

  const measureButtonCenter = () => {
    if (!toggleButtonRef.current) {
      buttonCenterRef.current = null;
      return undefined;
    }

    const rect = toggleButtonRef.current.getBoundingClientRect();
    const center = {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    };
    buttonCenterRef.current = center;
    return center;
  };

  const scheduleButtonCenterMeasure = () => {
    if (centerMeasureRafRef.current !== null) {
      return;
    }
    centerMeasureRafRef.current = window.requestAnimationFrame(() => {
      centerMeasureRafRef.current = null;
      measureButtonCenter();
    });
  };

  const clearIntentCueImmediately = () => {
    if (typeof document === "undefined") {
      return;
    }
    const root = document.documentElement;
    root.removeAttribute(MODE_INTENT_ACTIVE_ATTR);
    root.removeAttribute(MODE_INTENT_TARGET_ATTR);
    root.style.removeProperty(MODE_INTENT_X_VAR);
    root.style.removeProperty(MODE_INTENT_Y_VAR);
    root.style.removeProperty(MODE_INTENT_STRENGTH_VAR);
    root.style.removeProperty(MODE_INTENT_ANGLE_VAR);
    root.style.removeProperty(MODE_INTENT_DISTANCE_VAR);
    setButtonIntentVisuals(0, 90);
  };

  const clearIntentCue = (immediate = false, fadeMs = INTENT_EASE_OUT_MS) => {
    if (typeof document === "undefined") {
      return;
    }
    if (intentClearTimeoutRef.current !== null) {
      window.clearTimeout(intentClearTimeoutRef.current);
      intentClearTimeoutRef.current = null;
    }

    if (immediate) {
      clearIntentCueImmediately();
      return;
    }

    const root = document.documentElement;
    if (!root.hasAttribute(MODE_INTENT_ACTIVE_ATTR)) {
      clearIntentCueImmediately();
      return;
    }

    root.style.setProperty(MODE_INTENT_STRENGTH_VAR, "0");
    setButtonIntentVisuals(0, 90);
    intentClearTimeoutRef.current = window.setTimeout(() => {
      clearIntentCueImmediately();
      intentClearTimeoutRef.current = null;
    }, fadeMs);
  };

  const setIntentCue = (
    origin: { x: number; y: number },
    strength: number,
    nextTargetMode: "dark" | "light",
    pointerAngleDeg = 90,
    pointerDistancePx = 0,
  ) => {
    if (typeof document === "undefined") {
      return;
    }

    if (intentClearTimeoutRef.current !== null) {
      window.clearTimeout(intentClearTimeoutRef.current);
      intentClearTimeoutRef.current = null;
    }

    const normalizedStrength = Math.min(INTENT_MAX, Math.max(0, strength));
    if (normalizedStrength <= 0) {
      clearIntentCue();
      return;
    }

    const root = document.documentElement;
    root.setAttribute(MODE_INTENT_ACTIVE_ATTR, "true");
    root.setAttribute(MODE_INTENT_TARGET_ATTR, nextTargetMode);
    root.style.setProperty(MODE_INTENT_X_VAR, `${origin.x}px`);
    root.style.setProperty(MODE_INTENT_Y_VAR, `${origin.y}px`);
    root.style.setProperty(MODE_INTENT_STRENGTH_VAR, normalizedStrength.toFixed(3));
    root.style.setProperty(MODE_INTENT_ANGLE_VAR, `${pointerAngleDeg.toFixed(2)}deg`);
    root.style.setProperty(MODE_INTENT_DISTANCE_VAR, `${pointerDistancePx.toFixed(2)}px`);
    setButtonIntentVisuals(normalizedStrength, pointerAngleDeg);
  };

  const clearButtonTimers = () => {
    if (applyTimeoutRef.current !== null) {
      window.clearTimeout(applyTimeoutRef.current);
      applyTimeoutRef.current = null;
    }
    if (pressTimeoutRef.current !== null) {
      window.clearTimeout(pressTimeoutRef.current);
      pressTimeoutRef.current = null;
    }
  };

  useEffect(() => {
    measureButtonCenter();

    const handlePointerMove = (event: PointerEvent) => {
      if (!canUseProximityCue()) {
        return;
      }
      lastPointerRef.current = {
        x: event.clientX,
        y: event.clientY,
      };

      if (pointerRafRef.current !== null) {
        return;
      }

      pointerRafRef.current = window.requestAnimationFrame(() => {
        pointerRafRef.current = null;
        if (!lastPointerRef.current) {
          return;
        }

        const geometry = resolveIntentGeometry(lastPointerRef.current);
        if (!geometry) {
          return;
        }

        const { distance, angleDeg } = geometry;
        const proximity = Math.max(0, 1 - distance / INTENT_NEAR_FIELD_PX);
        let strength = proximity * INTENT_MAX;

        if (isHoveringRef.current) {
          strength = Math.max(strength, INTENT_HOVER_FLOOR);
        }

        if (strength <= 0) {
          clearIntentCue();
          return;
        }

        setIntentCue(geometry.center, strength, targetMode, angleDeg, distance);
      });
    };

    const handleViewportChange = () => {
      scheduleButtonCenterMeasure();
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("resize", handleViewportChange, { passive: true });
    window.addEventListener("scroll", handleViewportChange, true);

    return () => {
      if (applyTimeoutRef.current !== null) {
        window.clearTimeout(applyTimeoutRef.current);
      }
      if (pressTimeoutRef.current !== null) {
        window.clearTimeout(pressTimeoutRef.current);
      }
      if (intentClearTimeoutRef.current !== null) {
        window.clearTimeout(intentClearTimeoutRef.current);
      }
      if (intentFocusTimeoutRef.current !== null) {
        window.clearTimeout(intentFocusTimeoutRef.current);
      }
      if (pointerRafRef.current !== null) {
        window.cancelAnimationFrame(pointerRafRef.current);
      }
      if (centerMeasureRafRef.current !== null) {
        window.cancelAnimationFrame(centerMeasureRafRef.current);
      }

      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
      clearIntentCueImmediately();
    };
  }, [targetMode]);

  const resolveOrigin = () => {
    return buttonCenterRef.current ?? measureButtonCenter();
  };

  const resolveIntentGeometry = (point: { x: number; y: number }) => {
    const center = resolveOrigin();
    if (!center) {
      return undefined;
    }

    const dx = point.x - center.x;
    const dy = point.y - center.y;
    const distance = Math.hypot(dx, dy);
    const angleDeg = (Math.atan2(dy, dx) * 180) / Math.PI;
    return {
      center,
      distance,
      angleDeg,
    };
  };

  const setAnimatedMode = (next: "light" | "dark" | "system") => {
    const origin = measureButtonCenter() ?? resolveOrigin();
    setModePreference(next, {
      animate: true,
      origin,
      source: "user",
    });
  };

  const freezeIntentAtCenter = (nextTargetMode: "dark" | "light") => {
    const origin = measureButtonCenter() ?? resolveOrigin();
    if (!origin) {
      return;
    }

    const reducedMotion = prefersReducedMotion();
    const strength = reducedMotion
      ? Math.min(INTENT_HOVER_FLOOR, INTENT_FOCUS_PULSE_STRENGTH * 0.7)
      : Math.max(INTENT_HOVER_FLOOR, INTENT_FOCUS_PULSE_STRENGTH);

    setIntentCue(origin, strength, nextTargetMode, 90, 0);

    if (reducedMotion) {
      clearIntentCue(false, INTENT_REDUCED_MOTION_FADE_MS);
    }
  };

  const handlePrimaryToggle = () => {
    const next: "dark" | "light" = isDark ? "light" : "dark";
    clearButtonTimers();
    setIsPressing(true);
    setIconDrift(next === "dark" ? "to-dark" : "to-light");
    freezeIntentAtCenter(next);

    applyTimeoutRef.current = window.setTimeout(() => {
      setAnimatedMode(next);
      clearIntentCue(false, prefersReducedMotion() ? INTENT_REDUCED_MOTION_FADE_MS : INTENT_EASE_OUT_MS);
      applyTimeoutRef.current = null;
    }, MOTION_PROFILE.buttonPress.leadInMs);

    pressTimeoutRef.current = window.setTimeout(() => {
      setIsPressing(false);
      setIconDrift(null);
      pressTimeoutRef.current = null;
    }, MOTION_PROFILE.buttonPress.durationMs);
  };

  const handlePointerEnter = (event: ReactPointerEvent<HTMLButtonElement>) => {
    isHoveringRef.current = true;
    measureButtonCenter();
    if (!canUseProximityCue()) {
      return;
    }

    const geometry = resolveIntentGeometry({
      x: event.clientX,
      y: event.clientY,
    });
    const center = geometry?.center ?? resolveOrigin() ?? { x: event.clientX, y: event.clientY };
    const angle = geometry?.angleDeg ?? 90;
    const distance = geometry?.distance ?? 0;

    setIntentCue(
      center,
      INTENT_HOVER_FLOOR,
      targetMode,
      angle,
      distance,
    );
  };

  const handlePointerLeave = (event: ReactPointerEvent<HTMLButtonElement>) => {
    isHoveringRef.current = false;
    if (!canUseProximityCue()) {
      clearIntentCue(true);
      return;
    }

    const geometry = resolveIntentGeometry({
      x: event.clientX,
      y: event.clientY,
    });
    if (!geometry) {
      clearIntentCue();
      return;
    }

    const origin = geometry.center;
    const { distance, angleDeg } = geometry;
    const proximity = Math.max(0, 1 - distance / INTENT_NEAR_FIELD_PX);
    const strength = proximity * INTENT_MAX;

    if (strength <= 0) {
      clearIntentCue();
      return;
    }

    setIntentCue(origin, strength, targetMode, angleDeg, distance);
  };

  const handlePointerDown = () => {
    freezeIntentAtCenter(targetMode);
  };

  const handleFocus = () => {
    measureButtonCenter();
    const origin = resolveOrigin();
    if (!origin) {
      return;
    }

    if (intentFocusTimeoutRef.current !== null) {
      window.clearTimeout(intentFocusTimeoutRef.current);
      intentFocusTimeoutRef.current = null;
    }

    const reducedMotion = prefersReducedMotion();
    const strength = reducedMotion ? INTENT_FOCUS_PULSE_STRENGTH * 0.7 : INTENT_FOCUS_PULSE_STRENGTH;
    const fadeMs = reducedMotion ? INTENT_REDUCED_MOTION_FADE_MS : INTENT_FOCUS_PULSE_MS;

    setIntentCue(origin, strength, targetMode, 90, 0);
    intentFocusTimeoutRef.current = window.setTimeout(() => {
      clearIntentCue(false, fadeMs);
      intentFocusTimeoutRef.current = null;
    }, fadeMs);
  };

  const handleBlur = () => {
    if (intentFocusTimeoutRef.current !== null) {
      window.clearTimeout(intentFocusTimeoutRef.current);
      intentFocusTimeoutRef.current = null;
    }
    clearIntentCue(false, prefersReducedMotion() ? INTENT_REDUCED_MOTION_FADE_MS : INTENT_EASE_OUT_MS);
  };

  const getModeIcon = (mode: "light" | "dark" | "system") => {
    if (mode === "light") {
      return Sun;
    }
    if (mode === "dark") {
      return Moon;
    }
    return Laptop;
  };

  return (
    <div className="inline-flex items-center">
      <button
        ref={toggleButtonRef}
        type="button"
        data-theme-mode-anchor={WORKSPACE_THEME_MODE_ANCHOR}
        data-pressing={isPressing}
        onPointerEnter={handlePointerEnter}
        onPointerLeave={handlePointerLeave}
        onPointerDown={handlePointerDown}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onClick={handlePrimaryToggle}
        aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        className={clsx(
          "inline-flex h-8 w-8 items-center justify-center rounded-l-full rounded-r-sm text-foreground transition",
          "data-[pressing=true]:animate-[theme-toggle-press_120ms_ease-out]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        )}
      >
        <span
          data-mode-icon
          className={clsx(
            "inline-flex items-center justify-center transition-transform duration-180",
            iconDrift === "to-dark" && "rotate-[6deg]",
            iconDrift === "to-light" && "-rotate-[6deg]",
          )}
        >
          <span
            data-mode-icon-drift
            data-drift={iconDrift ?? "idle"}
            className={clsx(
              "inline-flex items-center justify-center",
              "data-[drift=to-dark]:animate-[theme-icon-drift_80ms_ease-out]",
              "data-[drift=to-light]:animate-[theme-icon-drift_80ms_ease-out]",
            )}
          >
            <span data-mode-celestial-core className="relative inline-flex h-[15px] w-[15px] items-center justify-center">
              <span aria-hidden data-mode-icon-orbit />
              <span aria-hidden data-mode-icon-limb />
              <span aria-hidden data-mode-icon-arc />
              <Sun
                data-mode-sun
                aria-hidden
                className={clsx(
                  "absolute h-[15px] w-[15px] transition-all duration-200 ease-[cubic-bezier(0.22,1,0.36,1)]",
                  isDark ? "rotate-0 scale-100 opacity-100" : "-rotate-45 scale-75 opacity-0",
                )}
              />
              <Moon
                data-mode-moon
                aria-hidden
                className={clsx(
                  "absolute h-[15px] w-[15px] transition-all duration-200 ease-[cubic-bezier(0.22,1,0.36,1)]",
                  isDark ? "rotate-45 scale-75 opacity-0" : "rotate-0 scale-100 opacity-100",
                )}
              />
            </span>
          </span>
        </span>
      </button>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label="Select color mode"
            className={clsx(
              "inline-flex h-8 w-5 items-center justify-center rounded-l-sm rounded-r-full text-foreground/95 transition",
              "hover:bg-foreground/10 hover:text-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              open && "bg-foreground/12 text-foreground",
            )}
          >
            <ChevronDownIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} />
            <span className="sr-only">Color mode options</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          sideOffset={8}
          className="w-56 rounded-xl border-border/70 bg-popover/95 p-1.5 shadow-lg backdrop-blur-sm"
        >
          <DropdownMenuLabel className="px-2.5 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/90">
            Color mode
          </DropdownMenuLabel>
          <DropdownMenuGroup>
            {MODE_OPTIONS.map((option) => {
              const ModeIcon = getModeIcon(option.value);
              const isSelected = modePreference === option.value;
              return (
                <DropdownMenuItem
                  key={option.value}
                  onSelect={() => setAnimatedMode(option.value)}
                  className={clsx(
                    "group gap-3 rounded-lg px-2.5 py-2 transition-colors",
                    isSelected && "bg-accent/70 text-accent-foreground",
                  )}
                >
                  <span
                    className={clsx(
                      "inline-flex h-4 w-4 items-center justify-center text-muted-foreground transition-colors",
                      isSelected && "text-foreground",
                    )}
                  >
                    <ModeIcon className="h-[15px] w-[15px]" />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col leading-tight">
                    <span className="text-[0.95rem] font-medium">{option.label}</span>
                    <span className="text-[11px] text-muted-foreground group-focus:text-accent-foreground/85">
                      {option.description}
                    </span>
                  </span>
                  <span className="inline-flex h-4 w-4 items-center justify-center">
                    {isSelected ? <CheckIcon className="h-3.5 w-3.5 text-foreground" /> : null}
                  </span>
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function ProfileMenu({
  displayName,
  email,
  canAccessOrganizationSettings,
  onOpenAccountSettings,
  onOpenOrganizationSettings,
  onOpenVersions,
}: {
  readonly displayName: string;
  readonly email: string;
  readonly canAccessOrganizationSettings: boolean;
  readonly onOpenAccountSettings: () => void;
  readonly onOpenOrganizationSettings: () => void;
  readonly onOpenVersions: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const navigate = useNavigate();
  const initials = getInitials(displayName, email);

  const handleSignOut = () => {
    if (isSigningOut) return;
    setIsSigningOut(true);
    navigate("/logout", { replace: true });
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={clsx(
            "inline-flex h-9 w-9 items-center justify-center rounded-full border text-sm font-semibold transition",
            "border-border/60 bg-background/80 text-foreground shadow-sm backdrop-blur-sm hover:border-border/90 hover:bg-accent hover:text-accent-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "border-ring bg-accent text-accent-foreground ring-2 ring-ring/30",
          )}
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label="Open profile menu"
        >
          <Avatar className="h-6 w-6 rounded-full border border-border/70 shadow-sm">
            <AvatarFallback className="rounded-full bg-primary text-[10px] font-semibold uppercase text-primary-foreground">
              {initials}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72 p-2">
        <DropdownMenuLabel className="px-2 py-1.5">
          <div className="space-y-0.5">
            <p className="text-sm font-semibold text-foreground">Signed in as</p>
            <p className="truncate text-xs text-muted-foreground">{email}</p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onSelect={onOpenAccountSettings} className="gap-2">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[0.6rem] font-semibold text-muted-foreground">
              A
            </span>
            <span>Account Settings</span>
          </DropdownMenuItem>
          {canAccessOrganizationSettings ? (
            <DropdownMenuItem onSelect={onOpenOrganizationSettings} className="gap-2">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[0.6rem] font-semibold text-muted-foreground">
                O
              </span>
              <span>Organization Settings</span>
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem onSelect={() => openReleaseNotes()} className="gap-2">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[0.6rem] font-semibold text-muted-foreground">
              R
            </span>
            <span>Release notes</span>
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onOpenVersions} className="gap-2">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-sm bg-muted text-[0.6rem] font-semibold text-muted-foreground">
              i
            </span>
            <span>About / Versions</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={handleSignOut}
          disabled={isSigningOut}
          variant="destructive"
          className="justify-between"
        >
          <span>Sign out</span>
          {isSigningOut ? <span className="text-xs text-muted-foreground">...</span> : null}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ThemeMenu() {
  const { theme, setPreviewTheme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      setPreviewTheme(null);
    }
  };

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label="Select theme"
          className={clsx(
            "inline-flex h-8 items-center gap-2 rounded-full px-2 text-xs font-semibold text-foreground transition",
            "hover:bg-accent hover:text-accent-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            open && "bg-accent text-accent-foreground",
          )}
        >
          <Palette className="h-[15px] w-[15px] text-current" aria-hidden />
          <ChevronDownIcon className={clsx("h-3.5 w-3.5 transition", open && "rotate-180")} />
          <span className="sr-only">Theme</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="w-56"
        onPointerLeave={() => setPreviewTheme(null)}
      >
        <DropdownMenuLabel className="text-xs uppercase tracking-wide text-muted-foreground">
          Theme
        </DropdownMenuLabel>
        <DropdownMenuGroup>
          {BUILTIN_THEMES.map((entry) => (
            <DropdownMenuItem
              key={entry.id}
              onSelect={() => setTheme(entry.id)}
              onPointerMove={() => setPreviewTheme(entry.id)}
              onFocus={() => setPreviewTheme(entry.id)}
              className="gap-3"
            >
              <span className="flex h-4 w-4 items-center justify-center">
                {theme === entry.id ? <CheckIcon className="h-4 w-4 text-foreground" /> : null}
              </span>
              <span className="flex-1">{entry.label}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function VersionsDialog({
  open,
  onOpenChange,
}: {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}) {
  const versionsQuery = useSystemVersions({ enabled: open });
  const backendVersion = versionsQuery.data?.backend ?? (versionsQuery.isPending ? "Loading..." : "unknown");
  const engineVersion = versionsQuery.data?.engine ?? (versionsQuery.isPending ? "Loading..." : "unknown");
  const webVersion = versionsQuery.data?.web ?? WEB_VERSION_FALLBACK;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Versions</DialogTitle>
          <DialogDescription>Build details for this ADE deployment.</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <VersionRow label="web" value={webVersion} hint="Frontend build" />
          <VersionRow label="backend" value={backendVersion} hint="Backend distribution" />
          <VersionRow label="engine" value={engineVersion} hint="Engine runtime" />
        </div>

        {versionsQuery.isError ? (
          <div className="mt-4 space-y-3">
            <Alert tone="warning">Could not load backend versions. Check connectivity and try again.</Alert>
            <Button size="sm" variant="secondary" onClick={() => versionsQuery.refetch()}>
              Retry
            </Button>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function VersionRow({
  label,
  value,
  hint,
}: {
  readonly label: string;
  readonly value: string;
  readonly hint: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border/70 bg-muted px-4 py-3">
      <div className="flex flex-col">
        <span className="text-sm font-semibold text-foreground">{label}</span>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </div>
      <code className="rounded bg-foreground px-2.5 py-1 text-xs font-mono text-background shadow-sm">
        {value}
      </code>
    </div>
  );
}
