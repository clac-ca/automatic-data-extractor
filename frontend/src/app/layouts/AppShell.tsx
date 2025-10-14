import { Fragment, useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

export interface AppShellNavItem {
  readonly label: string;
  readonly to: string;
  readonly end?: boolean;
}

export type AppShellProfileMenuItem =
  | { type: "nav"; label: string; to: string; disabled?: boolean }
  | { type: "action"; label: string; onSelect: () => void; disabled?: boolean };

export interface AppShellSidebarConfig {
  readonly content: ReactNode;
  readonly width?: number;
  readonly collapsedWidth?: number;
  readonly isCollapsed?: boolean;
}

export interface AppShellProps {
  readonly brand: {
    label: string;
    subtitle?: string;
    onClick?: () => void;
  };
  readonly breadcrumbs?: string[];
  readonly navItems?: AppShellNavItem[];
  readonly leading?: ReactNode;
  readonly actions?: ReactNode;
  readonly sidebar?: AppShellSidebarConfig;
  readonly profileMenuItems?: AppShellProfileMenuItem[];
  readonly user: {
    displayName: string;
    email: string;
  };
  readonly onSignOut: () => void;
  readonly isSigningOut?: boolean;
  readonly children: ReactNode;
}

export function AppShell({
  brand,
  breadcrumbs,
  navItems,
  leading,
  actions,
  sidebar,
  profileMenuItems = [],
  user,
  onSignOut,
  isSigningOut = false,
  children,
}: AppShellProps) {
  const navigate = useNavigate();

  const combinedProfileMenuItems: AppShellProfileMenuItem[] = [
    ...profileMenuItems,
    {
      type: "action",
      label: isSigningOut ? "Signing out…" : "Sign out",
      onSelect: onSignOut,
      disabled: isSigningOut,
    },
  ];

  const hasSidebar = Boolean(sidebar);
  const computedSidebarWidth = useMemo(() => {
    if (!sidebar) {
      return 0;
    }
    const { width = 280, collapsedWidth = 72, isCollapsed = false } = sidebar;
    return isCollapsed ? collapsedWidth : width;
  }, [sidebar]);
  const layoutStyle = useMemo<CSSProperties | undefined>(() => {
    if (!hasSidebar) {
      return undefined;
    }
    return {
      gridTemplateColumns: `${computedSidebarWidth}px minmax(0, 1fr)`,
    };
  }, [computedSidebarWidth, hasSidebar]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-6 py-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-6">
              <button
                type="button"
                onClick={brand.onClick ?? (() => navigate("/"))}
                className="flex items-center gap-3 text-left text-slate-900 transition hover:opacity-85"
              >
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white shadow-sm">
                  ADE
                </span>
                <span className="leading-tight">
                  <p className="text-sm font-semibold">{brand.label}</p>
                  {brand.subtitle ? (
                    <p className="text-xs text-slate-500">{brand.subtitle}</p>
                  ) : null}
                </span>
              </button>
              {leading ? <div className="flex items-center gap-3 text-sm text-slate-600">{leading}</div> : null}
            </div>

            <div className="flex items-center gap-3 text-sm text-slate-600">
              {actions}
              <ProfileMenu
                items={combinedProfileMenuItems}
                displayName={user.displayName}
                email={user.email}
                navigate={navigate}
              />
            </div>
          </div>

          {navItems && navItems.length > 0 ? (
            <nav className="flex items-center gap-2 text-sm font-semibold">
              {navItems.map((navItem) => (
                <NavLink
                  key={navItem.to}
                  to={navItem.to}
                  end={navItem.end}
                  className={({ isActive }) =>
                    [
                      "rounded-full px-4 py-2 transition",
                      isActive
                        ? "bg-brand-600 text-white shadow-sm"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-700",
                    ].join(" ")
                  }
                >
                  {navItem.label}
                </NavLink>
              ))}
            </nav>
          ) : null}
        </div>
      </header>

      <div
        className={`mx-auto w-full max-w-7xl px-6 py-8 ${
          hasSidebar ? "flex flex-col gap-8 lg:grid lg:gap-10" : "space-y-6"
        }`}
        style={layoutStyle}
      >
        {hasSidebar ? (
          <aside
            className="space-y-6"
            style={{ width: computedSidebarWidth, maxWidth: "100%", flexShrink: 0 }}
          >
            {sidebar?.content}
          </aside>
        ) : null}
        <main className="flex-1 space-y-6">
          {breadcrumbs && breadcrumbs.length > 0 ? <Breadcrumbs segments={breadcrumbs} /> : null}
          {children}
        </main>
      </div>
    </div>
  );
}

interface ProfileMenuProps {
  readonly items: AppShellProfileMenuItem[];
  readonly displayName: string;
  readonly email: string;
  readonly navigate: ReturnType<typeof useNavigate>;
}

function ProfileMenu({ items, displayName, email, navigate }: ProfileMenuProps) {
  const [open, setOpen] = useState(false);
  const initials = getInitials(displayName, email);

  return (
    <details className="relative" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="focus-ring inline-flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-full border border-slate-300 bg-white text-slate-500 transition hover:bg-slate-50">
        <span className="sr-only">Open profile menu</span>
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
          {initials}
        </span>
      </summary>
      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-56 rounded-lg border border-slate-200 bg-white shadow-lg ring-1 ring-slate-200">
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="text-sm font-semibold text-slate-700">{displayName}</p>
            <p className="text-xs text-slate-500">{email}</p>
          </div>
          <ul className="py-2 text-sm text-slate-600">
            {items.map((item) => (
              <li key={item.label}>
                <button
                  type="button"
                  disabled={item.disabled}
                  onClick={() => {
                    if (item.disabled) {
                      return;
                    }
                    if (item.type === "nav") {
                      navigate(item.to);
                    } else {
                      item.onSelect();
                    }
                    setOpen(false);
                  }}
                  className="block w-full px-4 py-2 text-left transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
                >
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </details>
  );
}

function Breadcrumbs({ segments }: { readonly segments: string[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-slate-500">
      {segments.map((segment, index) => (
        <Fragment key={`${segment}-${index}`}>
          {index > 0 ? <span>/</span> : null}
          <span className={index === segments.length - 1 ? "font-semibold text-slate-700" : undefined}>
            {segment}
          </span>
        </Fragment>
      ))}
    </nav>
  );
}

function getInitials(name: string, email: string) {
  const source = name || email;
  const parts = source.trim().split(/\s+/);
  if (parts.length === 0) {
    return "U";
  }
  const [first, second] = parts;
  if (!second && email) {
    const [local] = email.split("@");
    return (first?.[0] ?? "U").toUpperCase() + (local?.[1]?.toUpperCase() ?? "");
  }
  return `${(first?.[0] ?? "U").toUpperCase()}${(second?.[0] ?? "").toUpperCase()}`;
}
