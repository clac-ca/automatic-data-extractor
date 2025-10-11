import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

interface WorkspaceChromeContextValue {
  isDesktop: boolean;
  isRailCollapsed: boolean;
  toggleRail: () => void;
  setRailCollapsed: (collapsed: boolean) => void;
  isOverlayOpen: boolean;
  openOverlay: () => void;
  closeOverlay: () => void;
}

const WorkspaceChromeContext = createContext<WorkspaceChromeContextValue | undefined>(undefined);

const COLLAPSE_STORAGE_KEY = "ade:workspace-rail-collapsed";
const DESKTOP_QUERY = "(min-width: 1024px)";
const WIDE_DESKTOP_QUERY = "(min-width: 1280px)";

function readStoredCollapsePreference(): boolean | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const stored = window.localStorage.getItem(COLLAPSE_STORAGE_KEY);
    if (stored === "true" || stored === "false") {
      return stored === "true";
    }
  } catch (error) {
    console.warn("Unable to read workspace rail preference", error);
  }

  return null;
}

function writeStoredCollapsePreference(collapsed: boolean) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(COLLAPSE_STORAGE_KEY, String(collapsed));
  } catch (error) {
    console.warn("Unable to persist workspace rail preference", error);
  }
}

function getDefaultCollapsed(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  return !window.matchMedia(WIDE_DESKTOP_QUERY).matches;
}

interface WorkspaceChromeProviderProps {
  children: ReactNode;
}

export function WorkspaceChromeProvider({ children }: WorkspaceChromeProviderProps) {
  const hasExplicitPreferenceRef = useRef(false);
  const [isDesktop, setIsDesktop] = useState(() => {
    if (typeof window === "undefined") {
      return true;
    }

    return window.matchMedia(DESKTOP_QUERY).matches;
  });
  const [isOverlayOpen, setIsOverlayOpen] = useState(false);
  const [isRailCollapsed, setIsRailCollapsed] = useState(() => {
    const stored = readStoredCollapsePreference();
    if (stored !== null) {
      hasExplicitPreferenceRef.current = true;
      return stored;
    }

    return getDefaultCollapsed();
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const desktopMedia = window.matchMedia(DESKTOP_QUERY);
    const handleDesktopChange = (event: MediaQueryListEvent) => {
      setIsDesktop(event.matches);
    };

    const wideDesktopMedia = window.matchMedia(WIDE_DESKTOP_QUERY);
    const handleWideDesktopChange = (event: MediaQueryListEvent) => {
      if (hasExplicitPreferenceRef.current) {
        return;
      }

      setIsRailCollapsed(!event.matches);
    };

    setIsDesktop(desktopMedia.matches);
    if (!hasExplicitPreferenceRef.current) {
      setIsRailCollapsed(!wideDesktopMedia.matches);
    }

    desktopMedia.addEventListener("change", handleDesktopChange);
    wideDesktopMedia.addEventListener("change", handleWideDesktopChange);

    return () => {
      desktopMedia.removeEventListener("change", handleDesktopChange);
      wideDesktopMedia.removeEventListener("change", handleWideDesktopChange);
    };
  }, []);

  useEffect(() => {
    if (isDesktop) {
      setIsOverlayOpen(false);
    }
  }, [isDesktop]);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    if (!isDesktop && isOverlayOpen) {
      const previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = previousOverflow;
      };
    }

    return;
  }, [isDesktop, isOverlayOpen]);

  const setRailCollapsed = useCallback(
    (collapsed: boolean) => {
      hasExplicitPreferenceRef.current = true;
      setIsRailCollapsed(collapsed);
      writeStoredCollapsePreference(collapsed);
    },
    [],
  );

  const toggleRail = useCallback(() => {
    if (!isDesktop) {
      setIsOverlayOpen((previous) => !previous);
      return;
    }

    setRailCollapsed(!isRailCollapsed);
  }, [isDesktop, isRailCollapsed, setRailCollapsed]);

  const openOverlay = useCallback(() => {
    if (isDesktop) {
      setRailCollapsed(false);
      return;
    }

    setIsOverlayOpen(true);
  }, [isDesktop, setRailCollapsed]);

  const closeOverlay = useCallback(() => {
    if (isDesktop) {
      return;
    }

    setIsOverlayOpen(false);
  }, [isDesktop]);

  const value = useMemo<WorkspaceChromeContextValue>(
    () => ({
      isDesktop,
      isRailCollapsed,
      toggleRail,
      setRailCollapsed,
      isOverlayOpen,
      openOverlay,
      closeOverlay,
    }),
    [isDesktop, isRailCollapsed, toggleRail, setRailCollapsed, isOverlayOpen, openOverlay, closeOverlay],
  );

  return <WorkspaceChromeContext.Provider value={value}>{children}</WorkspaceChromeContext.Provider>;
}

export function useWorkspaceChrome() {
  const context = useContext(WorkspaceChromeContext);
  if (!context) {
    throw new Error("useWorkspaceChrome must be used within a WorkspaceChromeProvider");
  }

  return context;
}
