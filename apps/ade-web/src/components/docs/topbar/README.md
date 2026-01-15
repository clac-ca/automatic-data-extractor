---
title: Topbar
description: A composable, themeable and customizable top navigation component.
component: true
---

<figure className="flex flex-col gap-4">
  <ComponentPreview
    name="topbar-demo"
    title="Topbar"
    type="block"
    description="A composable, themeable and customizable topbar component built using shadcn/ui"
    className="w-full"
  />
  <figcaption className="text-center text-sm text-gray-500">
    A topbar that supports an optional compact mode and a mobile sheet.
  </figcaption>
</figure>

A topbar (global navigation) looks simple until it isn't: responsive layouts, sticky vs fixed headers, search, actions, overflow menus, and layout offsets.

`topbar.tsx` follows the same philosophy as `sidebar.tsx`: **a small component system** built from composable primitives, powered by a Provider and a tiny state machine.

- Composable (compound components)
- Themeable (dedicated CSS variables)
- Extensible (Slot/asChild, `data-*` contract, variants)
- Simple to use (sane defaults)

## Installation

<CodeTabs>

<TabsList>
  <TabsTrigger value="manual">Manual</TabsTrigger>
</TabsList>

<TabsContent value="manual">

<Steps>

<Step>Copy and paste the following code into your project.</Step>

<ComponentSource name="topbar" title="components/ui/topbar.tsx" />

<Step>Update the import paths to match your project setup.</Step>

<Step>Add the following colors to your CSS file.</Step>

```css showLineNumbers title="app/globals.css"
@layer base {
  :root {
    --topbar: oklch(0.985 0 0);
    --topbar-foreground: oklch(0.145 0 0);
    --topbar-primary: oklch(0.205 0 0);
    --topbar-primary-foreground: oklch(0.985 0 0);
    --topbar-accent: oklch(0.97 0 0);
    --topbar-accent-foreground: oklch(0.205 0 0);
    --topbar-border: oklch(0.922 0 0);
    --topbar-ring: oklch(0.708 0 0);
  }

  .dark {
    --topbar: oklch(0.205 0 0);
    --topbar-foreground: oklch(0.985 0 0);
    --topbar-primary: oklch(0.488 0.243 264.376);
    --topbar-primary-foreground: oklch(0.985 0 0);
    --topbar-accent: oklch(0.269 0 0);
    --topbar-accent-foreground: oklch(0.985 0 0);
    --topbar-border: oklch(1 0 0 / 10%);
    --topbar-ring: oklch(0.439 0 0);
  }
}
```

</Steps>

</TabsContent>

</CodeTabs>

## Structure

A `Topbar` is composed of the following parts:

- `TopbarProvider` - Owns the topbar state (compact/expanded) and mobile sheet state.
- `Topbar` - The header container (sticky/fixed + variants).
- `TopbarContent` - Inner layout wrapper.
- `TopbarStart`, `TopbarCenter`, `TopbarEnd` - Three sections for content.
- `TopbarNav` / `TopbarNavItem` / `TopbarNavButton` - Horizontal navigation primitives.
- `TopbarSheet` - Optional mobile navigation drawer.
- `TopbarTrigger` / `TopbarToggle` - Triggers for mobile and “smart toggle”.
- `TopbarInset` - Wrap your main content when using a fixed topbar.

## Usage

### Basic

```tsx showLineNumbers title="app/layout.tsx"
import {
  Topbar,
  TopbarContent,
  TopbarEnd,
  TopbarProvider,
  TopbarStart,
  TopbarTrigger,
} from "@/components/ui/topbar"

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <TopbarProvider>
      <Topbar position="sticky">
        <TopbarContent>
          <TopbarStart>
            <TopbarTrigger />
            <span className="text-sm font-medium">Acme</span>
          </TopbarStart>
          <TopbarEnd>
            {/* actions */}
          </TopbarEnd>
        </TopbarContent>
      </Topbar>

      {children}
    </TopbarProvider>
  )
}
```

### With a mobile sheet

```tsx showLineNumbers
import {
  Topbar,
  TopbarContent,
  TopbarEnd,
  TopbarProvider,
  TopbarSheet,
  TopbarStart,
  TopbarTrigger,
} from "@/components/ui/topbar"

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <TopbarProvider>
      <Topbar>
        <TopbarContent>
          <TopbarStart>
            <TopbarTrigger />
            <span className="text-sm font-medium">Acme</span>
          </TopbarStart>
          <TopbarEnd>{/* actions */}</TopbarEnd>
        </TopbarContent>
      </Topbar>

      <TopbarSheet>
        <div className="p-2">
          <div className="text-sm font-medium">Navigation</div>
          {/* your mobile nav here */}
        </div>
      </TopbarSheet>

      {children}
    </TopbarProvider>
  )
}
```

### With `sidebar.tsx`

The topbar pairs nicely with the sidebar. Put the `SidebarTrigger` inside `TopbarStart` to keep a consistent global “menu” affordance.

```tsx showLineNumbers
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import {
  Topbar,
  TopbarContent,
  TopbarEnd,
  TopbarProvider,
  TopbarStart,
} from "@/components/ui/topbar"

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <TopbarProvider>
        <Topbar>
          <TopbarContent>
            <TopbarStart>
              <SidebarTrigger />
              <span className="text-sm font-medium">Acme</span>
            </TopbarStart>
            <TopbarEnd>{/* actions */}</TopbarEnd>
          </TopbarContent>
        </Topbar>

        {children}
      </TopbarProvider>
    </SidebarProvider>
  )
}
```

## Components

### TopbarProvider

Wrap your app (or shell) in `TopbarProvider`.

#### Props

| Name                | Type                                  | Description |
| ------------------- | ------------------------------------- | ----------- |
| `defaultMode`       | `"expanded" \| "compact"`           | Uncontrolled initial mode. |
| `mode`              | `"expanded" \| "compact"`           | Controlled mode. |
| `onModeChange`      | `(mode) => void`                      | Controlled mode handler. |
| `defaultOpenMobile` | `boolean`                              | Uncontrolled initial mobile sheet state. |
| `openMobile`        | `boolean`                              | Controlled mobile sheet state. |
| `onOpenMobileChange`| `(open) => void`                      | Controlled mobile handler. |

#### Keyboard Shortcut

`cmd/ctrl + shift + m` toggles:
- mobile: the `TopbarSheet`
- desktop: compact mode

### Topbar

The topbar container.

#### Props

| Name       | Type                                 | Description |
| ---------- | ------------------------------------ | ----------- |
| `position` | `sticky \| fixed \| static`         | Layout mode. Use `fixed` with `TopbarInset`. |
| `variant`  | `topbar \| floating \| inset`       | Visual variant. |
| `bordered` | `boolean`                             | Adds a bottom border (default variant). |

### TopbarSheet

An optional mobile navigation drawer. Renders only on mobile (`useIsMobile()`).

### TopbarInset

Use when `Topbar position="fixed"` to offset content by the current topbar height.

## Theming

Topbar uses dedicated CSS variables (`--topbar-*`) so you can theme it independently from the rest of the app (same idea as the sidebar).

## Styling Tips

Because the topbar exposes state as `data-*` attributes, you can style children without prop drilling.

- Hide something in compact mode:

```tsx
<TopbarEnd className="group-data-[state=compact]/topbar:hidden" />
```

- Show tooltips only in compact mode:

```tsx
<TopbarNavButton tooltip="Settings">...</TopbarNavButton>
```

