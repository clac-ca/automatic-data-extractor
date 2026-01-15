"use client"

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { Menu } from "lucide-react"

import { useIsMobile } from "@/hooks/use-mobile"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const TOPBAR_COOKIE_NAME = "topbar_state"
const TOPBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7

const TOPBAR_HEIGHT = "3.5rem" // 56px
const TOPBAR_HEIGHT_COMPACT = "3rem" // 48px
const TOPBAR_HEIGHT_MOBILE = "3.5rem"

// Keyboard shortcut: cmd/ctrl + shift + m
const TOPBAR_KEYBOARD_SHORTCUT = "m"

type TopbarMode = "expanded" | "compact"

type TopbarContextProps = {
  state: TopbarMode
  mode: TopbarMode
  setMode: (mode: TopbarMode | ((mode: TopbarMode) => TopbarMode)) => void
  openMobile: boolean
  setOpenMobile: (open: boolean) => void
  isMobile: boolean
  toggleMode: () => void
  toggleMobile: () => void
  toggleTopbar: () => void
}

const TopbarContext = React.createContext<TopbarContextProps | null>(null)

function useTopbar() {
  const context = React.useContext(TopbarContext)
  if (!context) {
    throw new Error("useTopbar must be used within a TopbarProvider.")
  }

  return context
}

const TopbarProvider = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    defaultMode?: TopbarMode
    mode?: TopbarMode
    onModeChange?: (mode: TopbarMode) => void
    defaultOpenMobile?: boolean
    openMobile?: boolean
    onOpenMobileChange?: (open: boolean) => void
  }
>(
  (
    {
      defaultMode = "expanded",
      mode: modeProp,
      onModeChange: setModeProp,
      defaultOpenMobile = false,
      openMobile: openMobileProp,
      onOpenMobileChange: setOpenMobileProp,
      className,
      style,
      children,
      ...props
    },
    ref
  ) => {
    const isMobile = useIsMobile()

    const [_mode, _setMode] = React.useState<TopbarMode>(defaultMode)
    const mode = modeProp ?? _mode

    const [_openMobile, _setOpenMobile] = React.useState(defaultOpenMobile)
    const openMobile = openMobileProp ?? _openMobile

    const setMode = React.useCallback(
      (value: TopbarMode | ((value: TopbarMode) => TopbarMode)) => {
        const nextMode = typeof value === "function" ? value(mode) : value

        if (setModeProp) {
          setModeProp(nextMode)
        } else {
          _setMode(nextMode)
        }

        // Persist mode as a cookie for client navigations.
        // (In Next.js you can read this cookie in app/layout.tsx and pass it as defaultMode.)
        if (typeof document !== "undefined") {
          document.cookie = `${TOPBAR_COOKIE_NAME}=${nextMode}; path=/; max-age=${TOPBAR_COOKIE_MAX_AGE}`
        }
      },
      [mode, setModeProp]
    )

    const setOpenMobile = React.useCallback(
      (value: boolean | ((value: boolean) => boolean)) => {
        const nextOpen = typeof value === "function" ? value(openMobile) : value
        if (setOpenMobileProp) {
          setOpenMobileProp(nextOpen)
        } else {
          _setOpenMobile(nextOpen)
        }
      },
      [openMobile, setOpenMobileProp]
    )

    const toggleMode = React.useCallback(() => {
      setMode((prev) => (prev === "expanded" ? "compact" : "expanded"))
    }, [setMode])

    const toggleMobile = React.useCallback(() => {
      setOpenMobile((prev) => !prev)
    }, [setOpenMobile])

    // A convenience toggle: mobile toggles the mobile menu, desktop toggles compact mode.
    const toggleTopbar = React.useCallback(() => {
      return isMobile ? toggleMobile() : toggleMode()
    }, [isMobile, toggleMobile, toggleMode])

    // Keyboard shortcut: cmd/ctrl + shift + m
    React.useEffect(() => {
      const handleKeyDown = (event: KeyboardEvent) => {
        if (
          event.key.toLowerCase() === TOPBAR_KEYBOARD_SHORTCUT &&
          (event.metaKey || event.ctrlKey) &&
          event.shiftKey
        ) {
          event.preventDefault()
          toggleTopbar()
        }
      }

      window.addEventListener("keydown", handleKeyDown)
      return () => window.removeEventListener("keydown", handleKeyDown)
    }, [toggleTopbar])

    const state = mode

    const contextValue = React.useMemo<TopbarContextProps>(
      () => ({
        state,
        mode,
        setMode,
        openMobile,
        setOpenMobile,
        isMobile,
        toggleMode,
        toggleMobile,
        toggleTopbar,
      }),
      [
        state,
        mode,
        setMode,
        openMobile,
        setOpenMobile,
        isMobile,
        toggleMode,
        toggleMobile,
        toggleTopbar,
      ]
    )

    return (
      <TopbarContext.Provider value={contextValue}>
        <TooltipProvider delayDuration={0}>
          <div
            ref={ref}
            style={
              {
                "--topbar-height": TOPBAR_HEIGHT,
                "--topbar-height-compact": TOPBAR_HEIGHT_COMPACT,
                "--topbar-height-mobile": TOPBAR_HEIGHT_MOBILE,
                ...style,
              } as React.CSSProperties
            }
            className={cn(
              "group/topbar-wrapper flex min-h-svh w-full flex-col",
              className
            )}
            {...props}
          >
            {children}
          </div>
        </TooltipProvider>
      </TopbarContext.Provider>
    )
  }
)
TopbarProvider.displayName = "TopbarProvider"

const TOPBAR_SHEET_WIDTH_MOBILE = "18rem"

const Topbar = React.forwardRef<
  HTMLElement,
  React.ComponentProps<"header"> & {
    position?: "sticky" | "fixed" | "static"
    variant?: "topbar" | "floating" | "inset"
    bordered?: boolean
  }
>(
  (
    {
      position = "sticky",
      variant = "topbar",
      bordered = true,
      className,
      style,
      children,
      ...props
    },
    ref
  ) => {
    const { state } = useTopbar()

    const heightVar =
      state === "compact" ? "var(--topbar-height-compact)" : "var(--topbar-height)"

    return (
      <header
        ref={ref}
        data-topbar="topbar"
        data-state={state}
        data-variant={variant}
        data-position={position}
        style={
          {
            "--topbar-height-current": heightVar,
            ...style,
          } as React.CSSProperties
        }
        className={cn(
          "peer/topbar group/topbar z-30 w-full bg-topbar text-topbar-foreground",
          "h-[var(--topbar-height-current)]",
          position === "sticky" && "sticky top-0",
          position === "fixed" && "fixed inset-x-0 top-0",
          bordered && variant === "topbar" && "border-b border-topbar-border",
          variant === "floating" &&
            "m-2 rounded-lg border border-topbar-border shadow",
          variant === "inset" &&
            "md:m-2 md:rounded-xl md:border md:border-topbar-border md:shadow-sm",
          className
        )}
        {...props}
      >
        {children}
      </header>
    )
  }
)
Topbar.displayName = "Topbar"

const TopbarContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    maxWidth?: "full" | "screen" | "xl"
  }
>(({ className, maxWidth = "screen", ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-topbar="content"
      className={cn(
        "flex h-full w-full items-center gap-2 px-2",
        maxWidth === "screen" && "mx-auto max-w-screen-2xl",
        maxWidth === "xl" && "mx-auto max-w-6xl",
        className
      )}
      {...props}
    />
  )
})
TopbarContent.displayName = "TopbarContent"

const TopbarStart = React.forwardRef<HTMLDivElement, React.ComponentProps<"div">>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-topbar="start"
      className={cn(
        "flex min-w-0 items-center gap-2",
        "group-data-[state=compact]/topbar:gap-1",
        className
      )}
      {...props}
    />
  )
)
TopbarStart.displayName = "TopbarStart"

const TopbarCenter = React.forwardRef<HTMLDivElement, React.ComponentProps<"div">>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-topbar="center"
      className={cn(
        "flex min-w-0 flex-1 items-center justify-center gap-2",
        "group-data-[state=compact]/topbar:justify-start",
        className
      )}
      {...props}
    />
  )
)
TopbarCenter.displayName = "TopbarCenter"

const TopbarEnd = React.forwardRef<HTMLDivElement, React.ComponentProps<"div">>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-topbar="end"
      className={cn(
        "ml-auto flex min-w-0 items-center justify-end gap-2",
        "group-data-[state=compact]/topbar:gap-1",
        className
      )}
      {...props}
    />
  )
)
TopbarEnd.displayName = "TopbarEnd"

const TopbarBrand = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & { asChild?: boolean }
>(({ className, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "div"

  return (
    <Comp
      ref={ref}
      data-topbar="brand"
      className={cn(
        "flex min-w-0 items-center gap-2 rounded-md px-2 py-1 text-sm font-medium",
        "[&>span:last-child]:truncate",
        "group-data-[state=compact]/topbar:px-1",
        className
      )}
      {...props}
    />
  )
})
TopbarBrand.displayName = "TopbarBrand"

const TopbarTrigger = React.forwardRef<
  React.ElementRef<typeof Button>,
  React.ComponentProps<typeof Button> & {
    showOnDesktop?: boolean
  }
>(({ className, onClick, showOnDesktop = false, ...props }, ref) => {
  const { toggleMobile } = useTopbar()

  return (
    <Button
      ref={ref}
      data-topbar="trigger"
      variant="ghost"
      size="icon"
      aria-label="Open menu"
      className={cn("h-9 w-9", !showOnDesktop && "md:hidden", className)}
      onClick={(event) => {
        onClick?.(event)
        toggleMobile()
      }}
      {...props}
    >
      <Menu />
      <span className="sr-only">Open menu</span>
    </Button>
  )
})
TopbarTrigger.displayName = "TopbarTrigger"

/**
 * A convenience toggle that mirrors `SidebarTrigger`:
 * - mobile: toggles the `TopbarSheet`
 * - desktop: toggles compact mode
 */
const TopbarToggle = React.forwardRef<
  React.ElementRef<typeof Button>,
  React.ComponentProps<typeof Button>
>(({ className, onClick, ...props }, ref) => {
  const { toggleTopbar } = useTopbar()

  return (
    <Button
      ref={ref}
      data-topbar="toggle"
      variant="ghost"
      size="icon"
      aria-label="Toggle topbar"
      className={cn("h-9 w-9", className)}
      onClick={(event) => {
        onClick?.(event)
        toggleTopbar()
      }}
      {...props}
    >
      <Menu />
      <span className="sr-only">Toggle topbar</span>
    </Button>
  )
})
TopbarToggle.displayName = "TopbarToggle"

const TopbarInset = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"main">
>(({ className, ...props }, ref) => {
  return (
    <main
      ref={ref}
      data-topbar="inset"
      className={cn(
        "relative flex w-full flex-1 flex-col bg-background",
        // If the topbar is fixed, create space for it.
        "peer-data-[position=fixed]/topbar:pt-[var(--topbar-height-current)]",
        className
      )}
      {...props}
    />
  )
})
TopbarInset.displayName = "TopbarInset"

const TopbarSearch = React.forwardRef<
  React.ElementRef<typeof Input>,
  React.ComponentProps<typeof Input>
>(({ className, ...props }, ref) => (
  <Input
    ref={ref}
    data-topbar="search"
    className={cn(
      "h-9 w-full bg-background shadow-none focus-visible:ring-2 focus-visible:ring-topbar-ring",
      // By default, hide the search in compact mode (override with className if you want).
      "group-data-[state=compact]/topbar:hidden",
      className
    )}
    {...props}
  />
))
TopbarSearch.displayName = "TopbarSearch"

const TopbarSeparator = React.forwardRef<
  React.ElementRef<typeof Separator>,
  React.ComponentProps<typeof Separator>
>(({ className, orientation = "vertical", ...props }, ref) => (
  <Separator
    ref={ref}
    data-topbar="separator"
    orientation={orientation}
    className={cn(
      orientation === "vertical" ? "mx-1 h-6" : "my-1 w-full",
      "bg-topbar-border",
      className
    )}
    {...props}
  />
))
TopbarSeparator.displayName = "TopbarSeparator"

const TopbarSheet = React.forwardRef<
  React.ElementRef<typeof SheetContent>,
  React.ComponentPropsWithoutRef<typeof SheetContent> & {
    title?: string
    description?: string
    side?: "left" | "right"
  }
>(
  (
    {
      className,
      children,
      title = "Menu",
      description = "Displays the mobile navigation.",
      side = "left",
      style,
      ...props
    },
    ref
  ) => {
    const { isMobile, openMobile, setOpenMobile } = useTopbar()

    // No-op on desktop.
    if (!isMobile) return null

    return (
      <Sheet open={openMobile} onOpenChange={setOpenMobile}>
        <SheetContent
          ref={ref}
          data-topbar="sheet"
          className={cn(
            "w-[--topbar-sheet-width] bg-topbar p-0 text-topbar-foreground [&>button]:hidden",
            className
          )}
          style={
            {
              "--topbar-sheet-width": TOPBAR_SHEET_WIDTH_MOBILE,
              ...style,
            } as React.CSSProperties
          }
          side={side}
          {...props}
        >
          <SheetHeader className="sr-only">
            <SheetTitle>{title}</SheetTitle>
            <SheetDescription>{description}</SheetDescription>
          </SheetHeader>
          <div className="flex h-full w-full flex-col">{children}</div>
        </SheetContent>
      </Sheet>
    )
  }
)
TopbarSheet.displayName = "TopbarSheet"

const TopbarNav = React.forwardRef<
  HTMLUListElement,
  React.ComponentProps<"ul">
>(({ className, ...props }, ref) => (
  <ul
    ref={ref}
    data-topbar="nav"
    className={cn(
      "flex min-w-0 items-center gap-1 overflow-x-auto",
      "[&::-webkit-scrollbar]:hidden",
      className
    )}
    {...props}
  />
))
TopbarNav.displayName = "TopbarNav"

const TopbarNavItem = React.forwardRef<
  HTMLLIElement,
  React.ComponentProps<"li">
>(({ className, ...props }, ref) => (
  <li
    ref={ref}
    data-topbar="nav-item"
    className={cn("group/nav-item relative", className)}
    {...props}
  />
))
TopbarNavItem.displayName = "TopbarNavItem"

const topbarNavButtonVariants = cva(
  "peer/nav-button inline-flex items-center gap-2 overflow-hidden rounded-md px-3 py-2 text-sm font-medium text-topbar-foreground/80 outline-none ring-topbar-ring transition-colors hover:bg-topbar-accent hover:text-topbar-accent-foreground focus-visible:ring-2 active:bg-topbar-accent active:text-topbar-accent-foreground disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 data-[active=true]:bg-topbar-accent data-[active=true]:text-topbar-accent-foreground [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "",
        outline:
          "bg-background shadow-[0_0_0_1px_hsl(var(--topbar-border))] hover:shadow-[0_0_0_1px_hsl(var(--topbar-accent))]",
      },
      size: {
        default: "h-9",
        sm: "h-8 text-xs",
        lg: "h-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const TopbarNavButton = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button"> & {
    asChild?: boolean
    isActive?: boolean
    tooltip?: string | React.ComponentProps<typeof TooltipContent>
  } & VariantProps<typeof topbarNavButtonVariants>
>(
  (
    {
      asChild = false,
      isActive = false,
      variant = "default",
      size = "default",
      tooltip,
      className,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : "button"
    const { isMobile, state } = useTopbar()

    const button = (
      <Comp
        ref={ref}
        data-topbar="nav-button"
        data-size={size}
        data-active={isActive}
        className={cn(
          topbarNavButtonVariants({ variant, size }),
          // In compact mode, make buttons icon-sized and hide labels.
          "group-data-[state=compact]/topbar:!size-9 group-data-[state=compact]/topbar:!p-2",
          "group-data-[state=compact]/topbar:[&>span:last-child]:sr-only",
          className
        )}
        {...props}
      />
    )

    if (!tooltip) return button

    const tooltipProps =
      typeof tooltip === "string" ? { children: tooltip } : tooltip

    return (
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent
          side="bottom"
          align="center"
          hidden={state !== "compact" || isMobile}
          {...tooltipProps}
        />
      </Tooltip>
    )
  }
)
TopbarNavButton.displayName = "TopbarNavButton"

const TopbarNavSkeleton = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    showIcon?: boolean
  }
>(({ className, showIcon = true, ...props }, ref) => {
  // Random width between 40% to 80%.
  const width = React.useMemo(() => {
    return `${Math.floor(Math.random() * 40) + 40}%`
  }, [])

  return (
    <div
      ref={ref}
      data-topbar="nav-skeleton"
      className={cn("flex h-9 items-center gap-2 rounded-md px-3", className)}
      {...props}
    >
      {showIcon && <Skeleton className="size-4 rounded-md" />}
      <Skeleton
        className="h-4 max-w-[--skeleton-width] flex-1"
        style={
          {
            "--skeleton-width": width,
          } as React.CSSProperties
        }
      />
    </div>
  )
})
TopbarNavSkeleton.displayName = "TopbarNavSkeleton"

export {
  Topbar,
  TopbarBrand,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarInset,
  TopbarNav,
  TopbarNavButton,
  TopbarNavItem,
  TopbarNavSkeleton,
  TopbarProvider,
  TopbarSearch,
  TopbarSeparator,
  TopbarSheet,
  TopbarStart,
  TopbarToggle,
  TopbarTrigger,
  useTopbar,
}
