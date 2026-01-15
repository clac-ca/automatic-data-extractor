import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { Outlet, useNavigate } from "react-router-dom";

import { GlobalTopBar } from "@/components/navigation/GlobalTopBar";
import { AppTopBarControls } from "@/components/navigation/AppTopBarControls";
import { DirectoryIcon } from "@/components/icons";
import { SidebarProvider } from "@/components/ui/sidebar";

interface AppTopBarConfig {
  readonly hidden?: boolean;
  readonly brand?: ReactNode;
  readonly leading?: ReactNode;
  readonly actions?: ReactNode;
  readonly trailing?: ReactNode;
  readonly search?: ReactNode;
  readonly secondaryContent?: ReactNode;
}

interface AppTopBarContextValue {
  readonly setConfig: (config: AppTopBarConfig | null) => void;
}

const AppTopBarContext = createContext<AppTopBarContextValue | null>(null);

export function AppLayout() {
  const navigate = useNavigate();
  const [topBarConfig, setTopBarConfig] = useState<AppTopBarConfig | null>(null);
  const [scrollContainer, setScrollContainer] = useState<HTMLElement | null>(null);
  const handleScrollContainerRef = useCallback((node: HTMLElement | null) => {
    setScrollContainer(node);
  }, []);

  const defaultBrand = useMemo(
    () => (
      <button
        type="button"
        onClick={() => navigate("/workspaces")}
        className="inline-flex items-center gap-3 rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-left text-sm font-semibold text-foreground transition hover:border-border/70 hover:bg-background/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm">
          <DirectoryIcon className="h-5 w-5" aria-hidden />
        </span>
        <span className="flex flex-col leading-tight">
          <span className="text-sm font-semibold text-foreground">Workspace directory</span>
          <span className="text-xs text-muted-foreground">Automatic Data Extractor</span>
        </span>
      </button>
    ),
    [navigate],
  );

  const mergedTopBarConfig = useMemo(
    () => ({
      hidden: topBarConfig?.hidden ?? false,
      brand: topBarConfig?.brand ?? defaultBrand,
      leading: topBarConfig?.leading,
      actions: topBarConfig?.actions,
      trailing: topBarConfig?.trailing ?? <AppTopBarControls />,
      search: topBarConfig?.search,
      secondaryContent: topBarConfig?.secondaryContent,
    }),
    [defaultBrand, topBarConfig],
  );
  const sidebarStyle = useMemo<CSSProperties>(
    () => ({
      "--sidebar-width": "var(--app-shell-sidebar-width)",
      "--sidebar-width-icon": "var(--app-shell-sidebar-collapsed-width)",
    }),
    [],
  );

  const contextValue = useMemo<AppTopBarContextValue>(
    () => ({ setConfig: setTopBarConfig }),
    [setTopBarConfig],
  );

  return (
    <AppTopBarContext.Provider value={contextValue}>
      <SidebarProvider
        className="flex min-h-svh flex-col bg-background text-foreground"
        style={sidebarStyle}
      >
        {!mergedTopBarConfig.hidden ? (
          <GlobalTopBar
            brand={mergedTopBarConfig.brand}
            leading={mergedTopBarConfig.leading}
            actions={mergedTopBarConfig.actions}
            trailing={mergedTopBarConfig.trailing}
            search={mergedTopBarConfig.search}
            secondaryContent={mergedTopBarConfig.secondaryContent}
            scrollContainer={scrollContainer}
          />
        ) : null}
        <main
          id="main-content"
          tabIndex={-1}
          className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto"
          ref={handleScrollContainerRef}
        >
          <Outlet />
        </main>
      </SidebarProvider>
    </AppTopBarContext.Provider>
  );
}

export function useAppTopBar(config: AppTopBarConfig | null) {
  const context = useContext(AppTopBarContext);
  if (!context) {
    throw new Error("useAppTopBar must be used within AppLayout.");
  }

  useEffect(() => {
    context.setConfig(config);
    return () => context.setConfig(null);
  }, [config, context]);
}
