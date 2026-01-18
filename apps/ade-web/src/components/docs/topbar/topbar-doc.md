# Topbar

A composable top navigation bar for application layouts.

The `Topbar` is designed as a set of small primitives (Provider, Header, slots, mobile sheet, nav buttons) so you can build the layout you want without fighting a single “do everything” component.

- **Sticky or fixed** positioning.
- **Mobile menu** via `TopbarSheet` (uses `Sheet`).
- **Structured layout** with `TopbarStart`, `TopbarCenter`, `TopbarEnd`.
- **Link-friendly** via `asChild` (Next.js, React Router, etc).
- **Theme-friendly**: uses standard shadcn tokens (`bg-background`, `border-border`, `ring-ring`, etc).

---

## Example

`components/example-topbar.tsx`

```tsx
"use client"

import * as React from "react"
import Link from "next/link"
import { Settings, User } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Topbar,
  TopbarBrand,
  TopbarCenter,
  TopbarContent,
  TopbarEnd,
  TopbarInset,
  TopbarNav,
  TopbarNavButton,
  TopbarNavItem,
  TopbarProvider,
  TopbarSheet,
  TopbarStart,
  TopbarTrigger,
} from "@/components/ui/topbar"
import { Input } from "@/components/ui/input"

export function TopbarDemo({ children }: { children: React.ReactNode }) {
  return (
    <TopbarProvider>
      <Topbar position="sticky" blur bordered>
        <TopbarContent>
          <TopbarStart>
            <TopbarTrigger />

            <TopbarBrand asChild>
              <Link href="/">
                <span className="font-semibold">Acme</span>
              </Link>
            </TopbarBrand>

            <TopbarNav className="hidden md:flex">
              <TopbarNavItem>
                <TopbarNavButton asChild isActive>
                  <Link href="/dashboard">
                    <span>Dashboard</span>
                  </Link>
                </TopbarNavButton>
              </TopbarNavItem>

              <TopbarNavItem>
                <TopbarNavButton asChild>
                  <Link href="/projects">
                    <span>Projects</span>
                  </Link>
                </TopbarNavButton>
              </TopbarNavItem>
            </TopbarNav>
          </TopbarStart>

          <TopbarCenter className="hidden md:flex">
            <div className="w-full max-w-md">
              <Input placeholder="Search..." />
            </div>
          </TopbarCenter>

          <TopbarEnd>
            <Button variant="ghost" size="icon" aria-label="Settings">
              <Settings />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Account">
              <User />
            </Button>
          </TopbarEnd>
        </TopbarContent>
      </Topbar>

      <TopbarSheet>
        <nav className="flex flex-col gap-1 p-2">
          <TopbarNavButton asChild className="justify-start">
            <Link href="/dashboard">
              <span>Dashboard</span>
            </Link>
          </TopbarNavButton>
          <TopbarNavButton asChild className="justify-start">
            <Link href="/projects">
              <span>Projects</span>
            </Link>
          </TopbarNavButton>
        </nav>
      </TopbarSheet>

      <TopbarInset>{children}</TopbarInset>
    </TopbarProvider>
  )
}
```

---

## Installation

### CLI

If you ship this component via a shadcn registry, you can install it with:

```bash
npx shadcn@latest add topbar
```

### Manual Installation

1) Add the `topbar.tsx` file to your project:

```text
components/ui/topbar.tsx
```

2) Ensure dependencies exist:

```bash
npx @radix-ui/react-slot class-variance-authority lucide-react
```

3) Ensure you have these shadcn/ui components installed (the Topbar composes them):

- `button`
- `input`
- `separator`
- `sheet`
- `skeleton`
- `tooltip`

If you’re using the shadcn CLI:

```bash
npx shadcn@latest add button input separator sheet skeleton tooltip
```

4) Add (or replace) the `useIsMobile` hook used by the Topbar:

```text
hooks/use-mobile.ts
```

If you already have `useIsMobile`, keep yours and update the import path in `topbar.tsx` if needed.

---

## Usage

```tsx
import {
  Topbar,
  TopbarProvider,
  TopbarContent,
  TopbarStart,
  TopbarCenter,
  TopbarEnd,
  TopbarBrand,
  TopbarTrigger,
  TopbarSheet,
  TopbarInset,
} from "@/components/ui/topbar"
```

```tsx
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <TopbarProvider>
      <Topbar>
        <TopbarContent>
          <TopbarStart>
            <TopbarTrigger />
            <TopbarBrand>Acme</TopbarBrand>
          </TopbarStart>

          <TopbarCenter />
          <TopbarEnd />
        </TopbarContent>
      </Topbar>

      <TopbarSheet>{/* mobile navigation */}</TopbarSheet>

      <TopbarInset>{children}</TopbarInset>
    </TopbarProvider>
  )
}
```

> Tip: `TopbarSheet` only renders on mobile. You can include it unconditionally.

---

## Examples

### Link

Use the `asChild` prop to render your router’s link component with Topbar styles.

`components/example-topbar-link.tsx`

```tsx
import Link from "next/link"

import {
  TopbarNav,
  TopbarNavItem,
  TopbarNavButton,
} from "@/components/ui/topbar"

export function TopbarLinkDemo() {
  return (
    <TopbarNav>
      <TopbarNavItem>
        <TopbarNavButton asChild isActive>
          <Link href="/docs">
            <span>Docs</span>
          </Link>
        </TopbarNavButton>
      </TopbarNavItem>
    </TopbarNav>
  )
}
```

### Fixed topbar

When `position="fixed"`, pair it with `TopbarInset` so your page content is automatically offset by the header height.

```tsx
<TopbarProvider>
  <Topbar position="fixed" />
  <TopbarInset>{/* page */}</TopbarInset>
</TopbarProvider>
```

### Icon-only navigation

For dense toolbars, use `iconOnly` and provide a tooltip label.

```tsx
import { Bell } from "lucide-react"
import { TopbarNavButton } from "@/components/ui/topbar"

export function IconOnlyNav() {
  return (
    <TopbarNavButton iconOnly tooltip="Notifications" aria-label="Notifications">
      <Bell />
      <span>Notifications</span>
    </TopbarNavButton>
  )
}
```

### Custom size

Override the layout variables on `TopbarProvider`.

```tsx
<TopbarProvider
  style={
    {
      "--topbar-height": "4rem",
      "--topbar-height-mobile": "3.5rem",
      "--topbar-sheet-width": "20rem",
    } as React.CSSProperties
  }
>
  {/* ... */}
</TopbarProvider>
```

### Controlled mobile menu

Use a controlled state if you want to close the menu on route change, analytics events, etc.

```tsx
import * as React from "react"
import { TopbarProvider } from "@/components/ui/topbar"

export function ControlledTopbar({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false)

  return (
    <TopbarProvider openMobile={open} onOpenMobileChange={setOpen}>
      {children}
    </TopbarProvider>
  )
}
```

### Keyboard shortcut

Enable a keyboard shortcut (disabled by default). This toggles the mobile menu sheet.

```tsx
<TopbarProvider keyboardShortcut="m">
  {/* cmd/ctrl + shift + m */}
</TopbarProvider>
```

---

## Component reference

### `TopbarProvider`

Wrap your layout to enable mobile menu state and layout variables.

Props:
- `defaultOpenMobile?: boolean`
- `openMobile?: boolean`
- `onOpenMobileChange?: (open: boolean) => void`
- `keyboardShortcut?: string | null` (default: `null`)
- `withTooltipProvider?: boolean` (default: `true`)

### `Topbar`

The header element.

Props:
- `position?: "sticky" | "fixed" | "static"` (default: `"sticky"`)
- `variant?: "default" | "floating" | "inset"` (default: `"default"`)
- `bordered?: boolean` (default: `true`)
- `blur?: boolean` (default: `false`)

### `TopbarNavButton`

A styled, accessible nav/action button.

Props:
- `asChild?: boolean`
- `isActive?: boolean` (sets `aria-current="page"`)
- `tooltip?: string | TooltipContentProps` (desktop only)
- `variant?: "default" | "outline"`
- `size?: "default" | "sm" | "lg"`
- `iconOnly?: boolean`

---

## Design notes

- Prefer **composition** over config: `TopbarStart`, `TopbarCenter`, `TopbarEnd` keep layouts predictable.
- Use `TopbarSheet` for mobile navigation instead of trying to squeeze everything into the header.
- Keep the topbar “global”: authentication, search, primary nav, key actions. Push dense secondary navigation into the sidebar or the page.
