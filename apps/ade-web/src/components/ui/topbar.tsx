"use client"

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { Menu, X } from "lucide-react"

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

/**
 * Layout vars (mirrors Sidebar's "width vars live on the Provider" approach).
 * Override per app using <TopbarProvider style={{ "--topbar-height": "4rem" }} />
 */
const TOPBAR_HEIGHT = "3.5rem" // 56px
const TOPBAR_HEIGHT_MOBILE = "3.5rem" // 56px
const TOPBAR_SHEET_WIDTH_MOBILE = "18rem"

// Optional keyboard shortcut: cmd/ctrl + shift + m (disabled by default)
const TOPBAR_KEYBOARD_SHORTCUT_DEFAULT: string | null = null

type TopbarContextProps = {
  isMobile: boolean
  openMobile: boolean
  setOpenMobile: (open: boolean | ((open: boolean) => boolean)) => void
  toggleMobile: () => void
  mobileContentId: string
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
  React.ComponentPropsWithoutRef<"div"> & {
    defaultOpenMobile?: boolean
    openMobile?: boolean
    onOpenMobileChange?: (open: boolean) => void

    /**
     * If provided, enables cmd/ctrl + shift + <key> to toggle the mobile menu.
     * Example: keyboardShortcut="m"
     */
    keyboardShortcut?: string | null

    /**
     * Convenience: TopbarNavButton tooltips work out of the box.
     * If your app already has a TooltipProvider, you can set this false.
     */
    withTooltipProvider?: boolean
  }
>(
  (
    {
      defaultOpenMobile = false,
      openMobile: openMobileProp,
      onOpenMobileChange,
      keyboardShortcut = TOPBAR_KEYBOARD_SHORTCUT_DEFAULT,
      withTooltipProvider = true,
      className,
      style,
      children,
      ...props
    },
    ref
  ) => {
    const isMobile = useIsMobile()
    const reactId = React.useId()
    const mobileContentId = `topbar-mobile-${reactId}`

    const [_openMobile, _setOpenMobile] = React.useState(defaultOpenMobile)
    const openMobile = openMobileProp ?? _openMobile

    const setOpenMobile = React.useCallback(
      (value: boolean | ((value: boolean) => boolean)) => {
        const nextOpen = typeof value === "function" ? value(openMobile) : value
        if (onOpenMobileChange) {
          onOpenMobileChange(nextOpen)
        } else {
          _setOpenMobile(nextOpen)
        }
      },
      [openMobile, onOpenMobileChange]
    )

    const toggleMobile = React.useCallback(() => {
      setOpenMobile((prev) => !prev)
    }, [setOpenMobile])

    React.useEffect(() => {
      if (!keyboardShortcut) return

      const handleKeyDown = (event: KeyboardEvent) => {
        // Ignore typing contexts
        const target = event.target as HTMLElement | null
        const isTypingContext =
          !!target &&
          (target.tagName === "INPUT" ||
            target.tagName === "TEXTAREA" ||
            target.tagName === "SELECT" ||
            target.isContentEditable)

        if (isTypingContext) return

        if (
          event.key.toLowerCase() === keyboardShortcut.toLowerCase() &&
          (event.metaKey || event.ctrlKey) &&
          event.shiftKey
        ) {
          event.preventDefault()
          toggleMobile()
        }
      }

      window.addEventListener("keydown", handleKeyDown)
      return () => window.removeEventListener("keydown", handleKeyDown)
    }, [keyboardShortcut, toggleMobile])

    const contextValue = React.useMemo<TopbarContextProps>(
      () => ({
        isMobile,
        openMobile,
        setOpenMobile,
        toggleMobile,
        mobileContentId,
      }),
      [isMobile, openMobile, setOpenMobile, toggleMobile, mobileContentId]
    )

    const wrapper = (
      <div
        ref={ref}
        data-slot="topbar-wrapper"
        style={
          {
            "--topbar-height": TOPBAR_HEIGHT,
            "--topbar-height-mobile": TOPBAR_HEIGHT_MOBILE,
            "--topbar-height-current": isMobile
              ? "var(--topbar-height-mobile)"
              : "var(--topbar-height)",
            "--topbar-sheet-width": TOPBAR_SHEET_WIDTH_MOBILE,
            ...style,
          } as React.CSSProperties
        }
        className={cn("group/topbar-wrapper w-full", className)}
        {...props}
      >
        {children}
      </div>
    )

    return (
      <TopbarContext.Provider value={contextValue}>
        {withTooltipProvider ? (
          <TooltipProvider delayDuration={0}>{wrapper}</TooltipProvider>
        ) : (
          wrapper
        )}
      </TopbarContext.Provider>
    )
  }
)
TopbarProvider.displayName = "TopbarProvider"

const Topbar = React.forwardRef<
  HTMLElement,
  React.ComponentPropsWithoutRef<"header"> & {
    position?: "sticky" | "fixed" | "static"
    variant?: "default" | "floating" | "inset"
    bordered?: boolean
    /**
     * A common header pattern: slightly translucent + blur for sticky headers.
     */
    blur?: boolean
  }
>(
  (
    {
      position = "sticky",
      variant = "default",
      bordered = true,
      blur = false,
      className,
      ...props
    },
    ref
  ) => {
    return (
      <header
        ref={ref}
        data-slot="topbar"
        data-position={position}
        data-variant={variant}
        className={cn(
          "peer/topbar group/topbar z-40 w-full",
          "h-[var(--topbar-height-current)]",
          "bg-background text-foreground",
          position === "sticky" && "sticky top-0",
          position === "fixed" && "fixed inset-x-0 top-0",
          blur &&
            "bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60",
          bordered && variant === "default" && "border-b border-border",
          variant === "floating" && "m-2 rounded-lg border border-border shadow",
          variant === "inset" &&
            "md:m-2 md:rounded-xl md:border md:border-border md:shadow-sm",
          className
        )}
        {...props}
      />
    )
  }
)
Topbar.displayName = "Topbar"

const TopbarContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div"> & {
    maxWidth?: "full" | "screen" | "xl"
  }
>(({ className, maxWidth = "screen", ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-slot="topbar-content"
      className={cn(
        "flex h-full w-full items-center gap-2 px-2 sm:px-4",
        maxWidth === "screen" && "mx-auto max-w-screen-2xl",
        maxWidth === "xl" && "mx-auto max-w-6xl",
        className
      )}
      {...props}
    />
  )
})
TopbarContent.displayName = "TopbarContent"

const TopbarStart = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div">
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-slot="topbar-start"
    className={cn("flex min-w-0 items-center gap-2", className)}
    {...props}
  />
))
TopbarStart.displayName = "TopbarStart"

const TopbarCenter = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div">
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-slot="topbar-center"
    className={cn(
      "flex min-w-0 flex-1 items-center justify-center gap-2",
      className
    )}
    {...props}
  />
))
TopbarCenter.displayName = "TopbarCenter"

const TopbarEnd = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div">
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-slot="topbar-end"
    className={cn("ml-auto flex min-w-0 items-center justify-end gap-2", className)}
    {...props}
  />
))
TopbarEnd.displayName = "TopbarEnd"

const TopbarBrand = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div"> & { asChild?: boolean }
>(({ className, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "div"
  return (
    <Comp
      ref={ref}
      data-slot="topbar-brand"
      className={cn(
        "flex min-w-0 items-center gap-2 rounded-md px-2 py-1 text-sm font-medium",
        "[&>span:last-child]:truncate",
        className
      )}
      {...props}
    />
  )
})
TopbarBrand.displayName = "TopbarBrand"

const TopbarInset = React.forwardRef<
  HTMLElement,
  React.ComponentPropsWithoutRef<"main">
>(({ className, ...props }, ref) => {
  return (
    <main
      ref={ref}
      data-slot="topbar-inset"
      className={cn(
        "relative flex w-full flex-1 flex-col bg-background",
        // If the Topbar is fixed, create space for it.
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
  React.ComponentPropsWithoutRef<typeof Input>
>(({ className, ...props }, ref) => (
  <Input
    ref={ref}
    data-slot="topbar-search"
    className={cn(
      "h-9 w-full bg-background shadow-none",
      "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      className
    )}
    {...props}
  />
))
TopbarSearch.displayName = "TopbarSearch"

const TopbarSeparator = React.forwardRef<
  React.ElementRef<typeof Separator>,
  React.ComponentPropsWithoutRef<typeof Separator>
>(({ className, orientation = "vertical", ...props }, ref) => (
  <Separator
    ref={ref}
    data-slot="topbar-separator"
    orientation={orientation}
    className={cn(
      orientation === "vertical" ? "mx-1 h-6" : "my-1 w-full",
      className
    )}
    {...props}
  />
))
TopbarSeparator.displayName = "TopbarSeparator"

const TopbarTrigger = React.forwardRef<
  React.ElementRef<typeof Button>,
  React.ComponentPropsWithoutRef<typeof Button> & {
    showOnDesktop?: boolean
  }
>(({ className, onClick, showOnDesktop = false, ...props }, ref) => {
  const { openMobile, toggleMobile, mobileContentId } = useTopbar()

  return (
    <Button
      ref={ref}
      data-slot="topbar-trigger"
      type="button"
      variant="ghost"
      size="icon"
      aria-haspopup="dialog"
      aria-controls={mobileContentId}
      aria-expanded={openMobile}
      aria-label={openMobile ? "Close menu" : "Open menu"}
      className={cn("h-9 w-9", !showOnDesktop && "md:hidden", className)}
      onClick={(event) => {
        onClick?.(event)
        toggleMobile()
      }}
      {...props}
    >
      {openMobile ? <X /> : <Menu />}
      <span className="sr-only">{openMobile ? "Close menu" : "Open menu"}</span>
    </Button>
  )
})
TopbarTrigger.displayName = "TopbarTrigger"

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
      description = "Mobile navigation",
      side = "left",
      ...props
    },
    ref
  ) => {
    const { isMobile, openMobile, setOpenMobile, mobileContentId } = useTopbar()

    if (!isMobile) return null

    return (
      <Sheet open={openMobile} onOpenChange={setOpenMobile}>
        <SheetContent
          ref={ref}
          id={mobileContentId}
          data-slot="topbar-sheet"
          side={side}
          className={cn("w-[var(--topbar-sheet-width)] p-0", className)}
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
  React.ComponentPropsWithoutRef<"ul">
>(({ className, ...props }, ref) => (
  <ul
    ref={ref}
    data-slot="topbar-nav"
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
  React.ComponentPropsWithoutRef<"li">
>(({ className, ...props }, ref) => (
  <li
    ref={ref}
    data-slot="topbar-nav-item"
    className={cn("relative", className)}
    {...props}
  />
))
TopbarNavItem.displayName = "TopbarNavItem"

const topbarNavButtonVariants = cva(
  cn(
    "inline-flex items-center gap-2 rounded-md px-3",
    "text-sm font-medium",
    "text-muted-foreground",
    "transition-colors",
    "hover:bg-accent hover:text-accent-foreground",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    "disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50",
    "data-[active=true]:bg-accent data-[active=true]:text-accent-foreground",
    "[&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0"
  ),
  {
    variants: {
      variant: {
        default: "",
        outline: "ring-1 ring-inset ring-border bg-background",
      },
      size: {
        default: "h-9",
        sm: "h-8 px-2 text-xs",
        lg: "h-10 px-4",
      },
      iconOnly: {
        true: "size-9 justify-center px-0 [&>span:last-child]:sr-only",
        false: "",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
      iconOnly: false,
    },
  }
)

const TopbarNavButton = React.forwardRef<
  HTMLButtonElement,
  React.ComponentPropsWithoutRef<"button"> & {
    asChild?: boolean
    isActive?: boolean
    tooltip?: string | React.ComponentPropsWithoutRef<typeof TooltipContent>
  } & VariantProps<typeof topbarNavButtonVariants>
>(
  (
    {
      asChild = false,
      isActive = false,
      variant,
      size,
      iconOnly,
      tooltip,
      className,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : "button"
    const { isMobile } = useTopbar()

    const button = (
      <Comp
        ref={ref}
        data-slot="topbar-nav-button"
        data-active={isActive}
        aria-current={isActive ? "page" : undefined}
        className={cn(topbarNavButtonVariants({ variant, size, iconOnly }), className)}
        {...props}
      />
    )

    if (!tooltip || isMobile) return button

    const tooltipProps = typeof tooltip === "string" ? { children: tooltip } : tooltip

    return (
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="bottom" align="center" {...tooltipProps} />
      </Tooltip>
    )
  }
)
TopbarNavButton.displayName = "TopbarNavButton"

function hashStringToNumber(str: string) {
  // Stable across SSR/CSR because it’s based on useId.
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) >>> 0
  }
  return hash
}

const TopbarNavSkeleton = React.forwardRef<
  HTMLDivElement,
  React.ComponentPropsWithoutRef<"div"> & {
    showIcon?: boolean
  }
>(({ className, showIcon = true, ...props }, ref) => {
  const id = React.useId()
  const width = React.useMemo(() => {
    const n = hashStringToNumber(id)
    return `${40 + (n % 41)}%` // 40% - 80%
  }, [id])

  return (
    <div
      ref={ref}
      data-slot="topbar-nav-skeleton"
      className={cn("flex h-9 items-center gap-2 rounded-md px-3", className)}
      {...props}
    >
      {showIcon && <Skeleton className="size-4 rounded-md" />}
      <Skeleton
        className="h-4 max-w-[var(--skeleton-width)] flex-1"
        style={{ "--skeleton-width": width } as React.CSSProperties}
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
  TopbarTrigger,
  useTopbar,
}
