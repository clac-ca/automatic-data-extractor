import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useId,
} from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import clsx from "clsx";

import { Button } from "../../ui";

export interface AppShellNavItem {
  readonly id: string;
  readonly label: string;
  readonly to: string;
  readonly icon?: ReactNode;
  readonly children?: readonly AppShellNavItem[];
  readonly kind?: "primary" | "secondary" | "footer" | "pinned";
  readonly badge?: string;
  readonly description?: string;
}

export interface AppShellWorkspaceSummary {
  readonly name: string;
  readonly description?: string;
  readonly tag?: { label: string; tone?: "brand" | "success" | "warning" | "neutral" };
  readonly onManage?: () => void;
}

export interface AppShellProfileMenuItem {
  readonly id: string;
  readonly label: string;
  readonly onSelect: () => void;
  readonly icon?: ReactNode;
  readonly description?: string;
}

export interface AppShellInspector {
  readonly title?: string;
  readonly content: ReactNode;
  readonly isOpen: boolean;
  readonly onClose: () => void;
}

interface CommandItem {
  readonly id: string;
  readonly label: string;
  readonly group: string;
  readonly icon?: ReactNode;
  readonly shortcut?: string;
  readonly onSelect: () => void;
}

export interface AppShellProps {
  readonly brand: {
    label: string;
    subtitle?: string;
    onClick?: () => void;
  };
  readonly breadcrumbs?: string[];
  readonly navItems: readonly AppShellNavItem[];
  readonly leftRailContent?: ReactNode;
  readonly collapsedRailContent?: ReactNode;
  readonly isLeftRailCollapsed: boolean;
  readonly onToggleLeftRail: () => void;
  readonly isFocusMode: boolean;
  readonly onToggleFocusMode: () => void;
  readonly topBarActions?: ReactNode;
  readonly workspaceSummary?: AppShellWorkspaceSummary;
  readonly profileMenuItems?: readonly AppShellProfileMenuItem[];
  readonly user: {
    displayName: string;
    email: string;
  };
  readonly onSignOut: () => void;
  readonly isSigningOut?: boolean;
  readonly rightInspector?: AppShellInspector;
  readonly children: ReactNode;
}

export function AppShell({
  brand,
  breadcrumbs,
  navItems,
  leftRailContent,
  collapsedRailContent,
  workspaceSummary,
  profileMenuItems,
  isLeftRailCollapsed,
  onToggleLeftRail,
  isFocusMode,
  onToggleFocusMode,
  topBarActions,
  user,
  onSignOut,
  isSigningOut = false,
  rightInspector,
  children,
}: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [commandMenuOpen, setCommandMenuOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [isScrolled, setIsScrolled] = useState(false);
  const commandListId = useId();
  const commandInputId = useId();
  const commandTitleId = useId();
  const location = useLocation();
  const navigate = useNavigate();

  const leftRailVisible = !isFocusMode;
  const inspectorOpen = !isFocusMode && Boolean(rightInspector?.isOpen);

  const closeInspector = useCallback(() => {
    rightInspector?.onClose();
  }, [rightInspector]);

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 8);
    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (!(mobileNavOpen || commandMenuOpen)) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileNavOpen, commandMenuOpen]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const key = event.key.toLowerCase();
      if ((event.metaKey || event.ctrlKey) && key === "k") {
        event.preventDefault();
        setCommandMenuOpen(true);
        setCommandQuery("");
        return;
      }

      if (event.shiftKey && key === "f") {
        event.preventDefault();
        onToggleFocusMode();
        return;
      }

      if (key === "escape") {
        if (commandMenuOpen) {
          event.preventDefault();
          setCommandMenuOpen(false);
          return;
        }
        if (rightInspector?.isOpen) {
          event.preventDefault();
          rightInspector.onClose();
          return;
        }
        if (mobileNavOpen) {
          event.preventDefault();
          setMobileNavOpen(false);
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [commandMenuOpen, mobileNavOpen, onToggleFocusMode, rightInspector]);

  useEffect(() => {
    setMobileNavOpen(false);
    setCommandMenuOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (isFocusMode && rightInspector?.isOpen) {
      rightInspector.onClose();
    }
  }, [isFocusMode, rightInspector]);

  const currentHref = location.pathname + location.search;

  const commandItems = useMemo<CommandItem[]>(() => {
    const items: CommandItem[] = [];

    navItems.forEach((item) => {
      items.push({
        id: item.id,
        label: item.label,
        group: "Navigate",
        icon: item.icon,
        onSelect: () => navigate(item.to),
      });

      item.children?.forEach((child) => {
        items.push({
          id: child.id ?? `${item.id}:${child.label}`,
          label: `${item.label} • ${child.label}`,
          group: item.label,
          icon: child.icon ?? item.icon,
          onSelect: () => navigate(child.to),
        });
      });
    });

    profileMenuItems?.forEach((item) => {
      items.push({
        id: `profile-${item.id}`,
        label: item.label,
        group: "Profile",
        icon: item.icon,
        onSelect: item.onSelect,
      });
    });

    items.push({
      id: "toggle-focus",
      label: isFocusMode ? "Exit focus mode" : "Enter focus mode",
      group: "Quick actions",
      shortcut: "⇧F",
      onSelect: () => {
        if (!isFocusMode && rightInspector?.isOpen) {
          rightInspector.onClose();
        }
        onToggleFocusMode();
      },
    });

    items.push({
      id: "toggle-rail",
      label: isLeftRailCollapsed ? "Expand navigation" : "Collapse navigation",
      group: "Quick actions",
      onSelect: () => onToggleLeftRail(),
    });

    if (rightInspector?.isOpen) {
      items.push({
        id: "close-inspector",
        label: "Close inspector",
        group: "Quick actions",
        shortcut: "Esc",
        onSelect: () => rightInspector.onClose(),
      });
    }

    return items;
  }, [
    isFocusMode,
    isLeftRailCollapsed,
    navItems,
    navigate,
    onToggleFocusMode,
    onToggleLeftRail,
    profileMenuItems,
    rightInspector,
  ]);

  const primaryNavItems = useMemo(
    () => navItems.filter((item) => (item.kind ?? "primary") === "primary"),
    [navItems],
  );
  const secondaryNavItems = useMemo(
    () => navItems.filter((item) => item.kind === "secondary"),
    [navItems],
  );
  const pinnedNavItems = useMemo(
    () => navItems.filter((item) => item.kind === "pinned"),
    [navItems],
  );
  const footerNavItems = useMemo(
    () => navItems.filter((item) => item.kind === "footer"),
    [navItems],
  );

  const filteredCommands = useMemo(() => {
    if (!commandQuery.trim()) {
      return commandItems;
    }
    const needle = commandQuery.trim().toLowerCase();
    return commandItems.filter((item) =>
      item.label.toLowerCase().includes(needle),
    );
  }, [commandItems, commandQuery]);

  const navContent = useMemo(
    () => (
      <nav aria-label="Workspace navigation" className="mt-4 space-y-5">
        {workspaceSummary ? (
          <NavWorkspaceSummary summary={workspaceSummary} />
        ) : null}
        {pinnedNavItems.length > 0 ? (
          <NavSection
            label="Pinned documents"
            items={pinnedNavItems}
            currentHref={currentHref}
            collapsed={false}
          />
        ) : null}
        {primaryNavItems.length > 0 ? (
          <NavSection
            label="Document views"
            items={primaryNavItems}
            currentHref={currentHref}
            collapsed={false}
          />
        ) : null}
        {secondaryNavItems.length > 0 ? (
          <NavSection
            label="More"
            items={secondaryNavItems}
            currentHref={currentHref}
            collapsed={false}
          />
        ) : null}
      </nav>
    ),
    [currentHref, pinnedNavItems, primaryNavItems, secondaryNavItems, workspaceSummary],
  );
  const expandedRailContent = leftRailContent ?? navContent;

  return (
    <div className="relative flex min-h-screen flex-col bg-gradient-to-br from-slate-50 via-slate-50 to-slate-100 text-slate-900">
      <SkipLink href="#workspace-main">Skip to main content</SkipLink>
      <header
        role="banner"
        className={clsx(
          "sticky top-0 z-30 border-b border-slate-200/70 bg-white/80 backdrop-blur transition-shadow",
          isScrolled ? "shadow-lg shadow-slate-200/80" : "shadow-none",
        )}
      >
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 py-3 lg:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileNavOpen((open) => !open)}
              className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white/90 text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-white lg:hidden"
              aria-label={mobileNavOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={mobileNavOpen}
            >
              <MenuIcon />
            </button>

            <button
              type="button"
              onClick={() => onToggleLeftRail()}
              className="hidden items-center gap-2 rounded-lg border border-transparent px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white lg:inline-flex"
              aria-pressed={!isLeftRailCollapsed}
              aria-label={
                isLeftRailCollapsed
                  ? "Expand navigation rail"
                  : "Collapse navigation rail"
              }
            >
              <CollapseIcon collapsed={isLeftRailCollapsed} />
              <span className="hidden sm:inline">
                {isLeftRailCollapsed ? "Expand" : "Collapse"}
              </span>
            </button>

            <button
              type="button"
              onClick={() => brand.onClick?.()}
              className="flex min-w-0 items-center gap-3 rounded-lg px-2 py-1 text-left transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
            >
              <span className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-600 text-sm font-semibold text-white shadow-sm">
                ADE
              </span>
              <span className="hidden min-w-0 flex-col leading-tight sm:flex">
                <span className="truncate text-sm font-semibold text-slate-900">
                  {brand.label}
                </span>
                {brand.subtitle ? (
                  <span className="truncate text-xs text-slate-500">
                    {brand.subtitle}
                  </span>
                ) : null}
              </span>
            </button>
          </div>

          <div className="flex flex-1 items-center justify-end gap-2">
            <CommandButton
              onClick={() => {
                setCommandMenuOpen(true);
                setCommandQuery("");
              }}
              expanded={commandMenuOpen}
              controlsId={commandListId}
            />
            <IconButton icon={<BellIcon />} label="Notifications" onClick={() => undefined} />
            <IconButton
              icon={<HelpIcon />}
              label="Help center"
              onClick={() => window.open("/docs", "_blank", "noopener,noreferrer")}
            />
            {topBarActions}
            <Button
              variant={isFocusMode ? "primary" : "ghost"}
              size="sm"
              onClick={() => {
                if (!isFocusMode && rightInspector?.isOpen) {
                  rightInspector.onClose();
                }
                onToggleFocusMode();
              }}
              className="hidden items-center gap-2 md:inline-flex"
              aria-pressed={isFocusMode}
            >
              <FocusIcon />
              <span>{isFocusMode ? "Exit focus" : "Focus mode"}</span>
            </Button>
            <ProfileMenu
              displayName={user.displayName}
              email={user.email}
              onSignOut={onSignOut}
              isSigningOut={isSigningOut}
              items={profileMenuItems}
            />
         </div>
       </div>
     </header>

      <div className="flex flex-1 overflow-hidden">
        <aside
          role="navigation"
          aria-label="Workspace navigation"
          className={`${
            leftRailVisible ? "lg:relative lg:translate-x-0" : "lg:-translate-x-full"
          } fixed inset-y-0 left-0 z-30 w-72 transform bg-white shadow-lg transition-transform motion-safe:duration-200 lg:z-auto lg:flex lg:w-auto lg:flex-col lg:border-r lg:border-slate-200 lg:bg-white/90 lg:shadow-none ${
            isLeftRailCollapsed ? "lg:w-20" : "lg:w-72"
          } ${mobileNavOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}
          aria-hidden={!leftRailVisible && !mobileNavOpen}
        >
          <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4 lg:hidden">
            <span className="text-sm font-semibold text-slate-700">Workspace</span>
            <button
              type="button"
              onClick={() => setMobileNavOpen(false)}
              className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
              aria-label="Close navigation"
            >
              <CloseIcon />
            </button>
          </div>
          <div className={`flex-1 overflow-y-auto px-3 pb-4 pt-4 ${isLeftRailCollapsed ? "lg:hidden" : ""}`}>
            {expandedRailContent}
          </div>
          {isLeftRailCollapsed ? (
            <div className="hidden flex-col items-center gap-2 px-2 pb-4 pt-2 lg:flex">
              {collapsedRailContent ?? navItems.map((item) => <CollapsedRailItem key={item.id} item={item} />)}
              <button
                type="button"
                onClick={() => {
                  if (!isFocusMode && rightInspector?.isOpen) {
                    rightInspector.onClose();
                  }
                  onToggleFocusMode();
                }}
                className="focus-ring mt-1 flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:border-brand-200 hover:text-brand-600"
                aria-label={isFocusMode ? "Exit focus mode" : "Enable focus mode"}
                title={isFocusMode ? "Exit focus mode" : "Enable focus mode"}
              >
                <FocusIcon />
              </button>
              <button
                type="button"
                onClick={onToggleLeftRail}
                className="focus-ring flex h-11 w-11 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:text-slate-700"
                aria-label={isLeftRailCollapsed ? "Expand navigation" : "Collapse navigation"}
                title={isLeftRailCollapsed ? "Expand navigation" : "Collapse navigation"}
              >
                <CollapseIcon collapsed={isLeftRailCollapsed} />
              </button>
            </div>
          ) : (
            <div className="hidden border-t border-slate-200/80 px-3 pb-4 pt-3 lg:block">
              <LeftRailFooter
                isFocusMode={isFocusMode}
                onToggleFocusMode={() => {
                  if (!isFocusMode && rightInspector?.isOpen) {
                    rightInspector.onClose();
                  }
                  onToggleFocusMode();
                }}
                onToggleCollapse={onToggleLeftRail}
                footerItems={footerNavItems}
              />
            </div>
          )}
        </aside>

        {mobileNavOpen ? (
          <div
            className="fixed inset-0 z-20 bg-slate-900/40 lg:hidden"
            aria-hidden="true"
            onClick={() => setMobileNavOpen(false)}
          />
        ) : null}

        {inspectorOpen ? (
          <div
            className="fixed inset-0 z-30 bg-slate-900/20 lg:hidden"
            aria-hidden="true"
            onClick={closeInspector}
          />
        ) : null}

        <main
          id="workspace-main"
          className={`flex-1 overflow-y-auto bg-slate-50 px-4 py-6 lg:px-8 ${
            inspectorOpen ? "lg:pr-0" : ""
          }`}
          role="main"
          tabIndex={-1}
        >
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-4">
            {breadcrumbs && breadcrumbs.length > 0 ? (
              <Breadcrumbs segments={breadcrumbs} />
            ) : null}
            {children}
          </div>
        </main>

        {rightInspector ? (
          <aside
            className={`${
              inspectorOpen ? "translate-x-0" : "translate-x-full"
            } fixed inset-y-0 right-0 z-40 w-full max-w-md transform bg-white shadow-xl transition-transform lg:relative lg:w-96 lg:shadow-none ${
              isFocusMode ? "lg:hidden" : ""
            }`}
            role="complementary"
            aria-label="Item details"
          >
            <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4">
              <h2 className="text-sm font-semibold text-slate-700">
                {rightInspector.title ?? "Details"}
              </h2>
              <button
                type="button"
                onClick={rightInspector.onClose}
                className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-100"
                aria-label="Close inspector"
              >
                <CloseIcon />
              </button>
            </div>
            <div className="h-[calc(100%-4rem)] overflow-y-auto px-4 py-6">
              {rightInspector.content}
            </div>
          </aside>
        ) : null}
      </div>

      <CommandMenu
        open={commandMenuOpen}
        query={commandQuery}
        onQueryChange={setCommandQuery}
        items={filteredCommands}
        onClose={() => setCommandMenuOpen(false)}
        listId={commandListId}
        inputId={commandInputId}
        titleId={commandTitleId}
      />
    </div>
  );
}

function SkipLink({ href, children }: { readonly href: string; readonly children: ReactNode }) {
  return (
    <a
      href={href}
      className="focus-ring pointer-events-none absolute left-4 top-4 z-50 -translate-y-14 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white opacity-0 transition focus:pointer-events-auto focus:translate-y-0 focus:opacity-100"
    >
      {children}
    </a>
  );
}

function Breadcrumbs({ segments }: { readonly segments: string[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-slate-500">
      {segments.map((segment, index) => (
        <Fragment key={`${segment}-${index}`}>
          {index > 0 ? <span className="text-slate-400">/</span> : null}
          <span
            className={index === segments.length - 1 ? "font-semibold text-slate-700" : undefined}
          >
            {segment}
          </span>
        </Fragment>
      ))}
    </nav>
  );
}

function NavWorkspaceSummary({ summary }: { readonly summary: AppShellWorkspaceSummary }) {
  const toneClass = (() => {
    switch (summary.tag?.tone) {
      case "success":
        return "bg-success-100 text-success-700";
      case "warning":
        return "bg-warning-100 text-warning-700";
      case "neutral":
        return "bg-slate-200 text-slate-600";
      case "brand":
      default:
        return "bg-brand-100 text-brand-700";
    }
  })();

  return (
    <div className="mx-1 space-y-3 rounded-2xl border border-slate-200 bg-gradient-to-br from-white via-white to-slate-50 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{summary.name}</p>
          {summary.description ? (
            <p className="mt-1 truncate text-xs text-slate-500">{summary.description}</p>
          ) : null}
        </div>
        {summary.tag ? (
          <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", toneClass)}>
            {summary.tag.label}
          </span>
        ) : null}
      </div>
      {summary.onManage ? (
        <button
          type="button"
          onClick={summary.onManage}
          className="focus-ring inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-300 hover:bg-slate-100"
        >
          Manage workspace
        </button>
      ) : null}
    </div>
  );
}

function NavSection({
  label,
  items,
  currentHref,
  collapsed,
}: {
  readonly label: string;
  readonly items: readonly AppShellNavItem[];
  readonly currentHref: string;
  readonly collapsed: boolean;
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="space-y-2">
      <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.id}>
            <LeftRailItem item={item} collapsed={collapsed} currentHref={currentHref} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function LeftRailItem({
  item,
  collapsed,
  currentHref,
}: {
  readonly item: AppShellNavItem;
  readonly collapsed: boolean;
  readonly currentHref: string;
}) {
  const [open, setOpen] = useState(true);
  const hasChildren = Boolean(item.children?.length);

  useEffect(() => {
    if (!hasChildren) {
      return;
    }
    const childMatch = item.children?.some((child) => currentHref.startsWith(child.to));
    if (childMatch) {
      setOpen(true);
    }
  }, [currentHref, hasChildren, item.children]);

  if (collapsed) {
    return null;
  }

  return (
    <div>
      <NavLink
        to={item.to}
        title={item.label}
        aria-current={currentHref.startsWith(item.to) ? "page" : undefined}
        className={({ isActive }) =>
          clsx(
            "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white motion-safe:transition-transform",
            isActive
              ? "bg-gradient-to-r from-brand-600 to-brand-500 text-white shadow-lg ring-1 ring-brand-300/80"
              : "text-slate-500 hover:bg-slate-100 motion-safe:hover:translate-x-1",
          )
        }
      >
        <span
          className={clsx(
            "pointer-events-none absolute left-1.5 top-1/2 h-6 w-1 -translate-y-1/2 rounded-full bg-brand-400 transition-opacity",
            currentHref.startsWith(item.to) ? "opacity-100" : "opacity-0",
          )}
          aria-hidden="true"
        />
        {item.icon ? (
          <span
            className={clsx(
              "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border text-base transition",
              currentHref.startsWith(item.to)
                ? "border-white/30 bg-white/10 text-white"
                : "border-transparent bg-slate-100 text-slate-500 group-hover:bg-slate-200",
            )}
          >
            {item.icon}
          </span>
        ) : null}
        <span className="flex min-w-0 flex-1 flex-col text-left">
          <span className="truncate">{item.label}</span>
          {item.description ? (
            <span className="truncate text-xs font-normal text-slate-400">{item.description}</span>
          ) : null}
        </span>
        {item.badge ? (
          <CommandBadge className="bg-brand-50 text-brand-600">{item.badge}</CommandBadge>
        ) : null}
      </NavLink>
      {hasChildren ? (
        <div className="mt-1">
          <button
            type="button"
            onClick={() => setOpen((current) => !current)}
            className="ml-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400 transition hover:text-slate-500"
            aria-expanded={open}
          >
            Sections
            <span aria-hidden="true" className={`transition-transform ${open ? "rotate-90" : ""}`}>
              ▶
            </span>
          </button>
          {open ? (
            <ul className="mt-2 space-y-1 border-l border-slate-200 pl-4 text-sm">
              {item.children?.map((child) => (
                <li key={child.id}>
                  <NavLink
                    to={child.to}
                    className={({ isActive }) =>
                      clsx(
                        "group flex items-center gap-2 rounded-lg px-2 py-1 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                        isActive ? "bg-brand-50 text-brand-700" : "text-slate-500 hover:bg-slate-100",
                      )
                    }
                  >
                    <span className="sr-only">{item.label}</span>
                    <span>{child.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function CollapsedRailItem({ item }: { readonly item: AppShellNavItem }) {
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        clsx(
          "focus-ring flex h-12 w-12 items-center justify-center rounded-xl border transition",
          isActive
            ? "border-brand-300 bg-brand-50 text-brand-700 shadow-sm"
            : "border-transparent bg-white text-slate-600 hover:border-slate-200 hover:text-slate-800",
        )
      }
      title={item.label}
      aria-label={item.label}
    >
      {item.icon ?? (
        <span className="text-sm font-semibold uppercase">{item.label.charAt(0)}</span>
      )}
    </NavLink>
  );
}

function ProfileMenu({
  displayName,
  email,
  onSignOut,
  isSigningOut,
  items = [],
}: {
  readonly displayName: string;
  readonly email: string;
  readonly onSignOut: () => void;
  readonly isSigningOut: boolean;
  readonly items?: readonly AppShellProfileMenuItem[];
}) {
  const [open, setOpen] = useState(false);
  const initials = getInitials(displayName, email);

  return (
    <details className="relative" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="focus-ring inline-flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-100">
        <span className="sr-only">Open profile menu</span>
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
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
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => {
                    item.onSelect();
                    setOpen(false);
                  }}
                  className="flex w-full items-start gap-3 px-4 py-2 text-left transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                >
                  {item.icon ? (
                    <span className="mt-0.5 text-slate-400">{item.icon}</span>
                  ) : null}
                  <span className="flex-1">
                    <span className="block font-semibold text-slate-700">{item.label}</span>
                    {item.description ? (
                      <span className="mt-0.5 block text-xs text-slate-400">{item.description}</span>
                    ) : null}
                  </span>
                </button>
              </li>
            ))}
            {items.length > 0 ? <li className="my-1 border-t border-slate-200" /> : null}
            <li>
              <button
                type="button"
                onClick={() => {
                  onSignOut();
                  setOpen(false);
                }}
                disabled={isSigningOut}
                className="block w-full px-4 py-2 text-left transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
              >
                {isSigningOut ? "Signing out…" : "Sign out"}
              </button>
            </li>
          </ul>
        </div>
      ) : null}
    </details>
  );
}

function CommandButton({
  onClick,
  expanded,
  controlsId,
}: {
  readonly onClick: () => void;
  readonly expanded: boolean;
  readonly controlsId: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group inline-flex items-center gap-3 rounded-lg border border-slate-200 bg-white/90 px-3 py-2 text-left text-sm text-slate-500 shadow-sm transition hover:border-slate-300 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
      aria-label="Open command palette"
      aria-haspopup="dialog"
      aria-expanded={expanded}
      aria-controls={expanded ? controlsId : undefined}
    >
      <span className="inline-flex items-center gap-2">
        <SearchIcon />
        <span className="hidden min-w-[140px] truncate md:block">Search or jump to…</span>
      </span>
      <span className="hidden md:flex">
        <CommandBadge>⌘K</CommandBadge>
      </span>
      <span className="md:hidden">
        <CommandBadge>⌘K</CommandBadge>
      </span>
    </button>
  );
}

function IconButton({
  icon,
  label,
  onClick,
}: {
  readonly icon: ReactNode;
  readonly label: string;
  readonly onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white/80 text-slate-500 shadow-sm transition hover:border-slate-300 hover:text-slate-700"
      aria-label={label}
    >
      {icon}
    </button>
  );
}

function LeftRailFooter({
  isFocusMode,
  onToggleFocusMode,
  onToggleCollapse,
  footerItems = [],
}: {
  readonly isFocusMode: boolean;
  readonly onToggleFocusMode: () => void;
  readonly onToggleCollapse: () => void;
  readonly footerItems?: readonly AppShellNavItem[];
}) {
  return (
    <div className="space-y-2 text-sm">
      <p className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Quick actions
      </p>
      <button
        type="button"
        onClick={onToggleFocusMode}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-transparent bg-slate-100/70 px-3 py-2 text-left text-slate-600 transition hover:border-brand-100 hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
      >
        <span className="font-medium">{isFocusMode ? "Exit focus mode" : "Focus mode"}</span>
        <CommandBadge>⇧F</CommandBadge>
      </button>
      <button
        type="button"
        onClick={onToggleCollapse}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-transparent px-3 py-2 text-left text-slate-600 transition hover:border-slate-200 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
      >
        <span className="font-medium">Collapse navigation</span>
        <span aria-hidden="true" className="text-xs text-slate-400">
          ↔
        </span>
      </button>
      {footerItems.length > 0 ? (
        <div className="space-y-1 border-t border-slate-200/80 pt-3">
          {footerItems.map((item) => (
            <NavLink
              key={item.id}
              to={item.to}
              className="block rounded-lg px-3 py-2 text-xs font-semibold text-slate-500 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function CommandMenu({
  open,
  onClose,
  query,
  onQueryChange,
  items,
  listId,
  inputId,
  titleId,
}: {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly query: string;
  readonly onQueryChange: (value: string) => void;
  readonly items: readonly CommandItem[];
  readonly listId: string;
  readonly inputId: string;
  readonly titleId: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [highlightIndex, setHighlightIndex] = useState(0);

  useEffect(() => {
    if (open) {
      setHighlightIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open, items, query]);

  if (!open) {
    return null;
  }

  const groupedItems = items.reduce<Record<string, CommandItem[]>>((acc, item) => {
    if (!acc[item.group]) {
      acc[item.group] = [];
    }
    acc[item.group].push(item);
    return acc;
  }, {});

  const flatItems = Object.values(groupedItems).flat();

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightIndex((index) => (index + 1) % Math.max(flatItems.length, 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightIndex((index) =>
        index === 0 ? Math.max(flatItems.length - 1, 0) : index - 1,
      );
    } else if (event.key === "Enter") {
      event.preventDefault();
      flatItems[highlightIndex]?.onSelect();
      onClose();
    }
  }

  const activeItem = flatItems[highlightIndex];
  const activeDescendant = activeItem ? `${listId}-${activeItem.id}` : undefined;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/50 px-4 py-20 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="w-full max-w-xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <h2 id={titleId} className="sr-only">
          Command palette
        </h2>
        <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-3">
          <SearchIcon />
          <input
            id={inputId}
            ref={inputRef}
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search destinations or actions…"
            className="flex-1 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
            aria-labelledby={titleId}
            aria-controls={items.length > 0 ? listId : undefined}
          />
          <button
            type="button"
            onClick={onClose}
            className="focus-ring inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 text-slate-500 hover:bg-slate-100"
            aria-label="Close command menu"
          >
            <CloseIcon />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto px-2 py-3" role="presentation">
          {items.length === 0 ? (
            <p className="px-3 py-6 text-sm text-slate-500">No matches found.</p>
          ) : (
            <div
              id={listId}
              role="listbox"
              aria-activedescendant={activeDescendant}
              className="space-y-4"
            >
              {Object.entries(groupedItems).map(([group, groupItems]) => (
                <div key={group} className="last:mb-0">
                  <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    {group}
                  </p>
                  <div className="mt-2 space-y-1">
                    {groupItems.map((item) => {
                      const index = flatItems.indexOf(item);
                      const highlighted = index === highlightIndex;
                      const optionId = `${listId}-${item.id}`;
                      return (
                        <button
                          key={item.id}
                          id={optionId}
                          type="button"
                          role="option"
                          aria-selected={highlighted}
                          onClick={() => {
                            item.onSelect();
                            onClose();
                          }}
                          className={clsx(
                            "flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white motion-safe:transition-transform",
                            highlighted
                              ? "bg-brand-100 text-brand-800"
                              : "text-slate-600 hover:bg-slate-100 motion-safe:hover:translate-x-0.5",
                          )}
                          onMouseEnter={() => setHighlightIndex(index)}
                          onMouseMove={() => setHighlightIndex(index)}
                        >
                          <span className="flex items-center gap-2">
                            {item.icon ? <span className="text-base">{item.icon}</span> : null}
                            <span>{item.label}</span>
                          </span>
                          {item.shortcut ? <CommandBadge>{item.shortcut}</CommandBadge> : null}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CommandBadge({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold text-slate-400 shadow-sm",
        className,
      )}
    >
      {children}
    </span>
  );
}

function MenuIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path d="M3 5h14a1 1 0 100-2H3a1 1 0 000 2zm14 4H3a1 1 0 000 2h14a1 1 0 100-2zm0 6H3a1 1 0 100 2h14a1 1 0 100-2z" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden="true">
      <path d="M10 3a4 4 0 0 0-4 4v2.586a2 2 0 0 1-.586 1.414L4.29 12.12A1 1 0 0 0 5 13.82h10a1 1 0 0 0 .71-1.7l-1.123-1.12A2 2 0 0 1 14 9.586V7a4 4 0 0 0-4-4Z" />
      <path d="M12 15a2 2 0 1 1-4 0" />
    </svg>
  );
}

function HelpIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden="true">
      <circle cx="10" cy="10" r="8" />
      <path d="M10 14v-1.2c0-1.2 2-1.5 2-3.3a2 2 0 1 0-3.9-.6" />
      <circle cx="10" cy="15.5" r="0.7" fill="currentColor" stroke="none" />
    </svg>
  );
}

function CollapseIcon({ collapsed }: { readonly collapsed: boolean }) {
  return collapsed ? (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M12.47 3.47a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06-1.06L15.69 9H3.75a.75.75 0 010-1.5H15.69l-3.22-3.22a.75.75 0 010-1.06z"
        clipRule="evenodd"
      />
    </svg>
  ) : (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M7.53 3.47a.75.75 0 010 1.06L4.31 7.75H16.25a.75.75 0 010 1.5H4.31l3.22 3.22a.75.75 0 11-1.06 1.06L2.22 9.28a.75.75 0 010-1.06l4.25-4.25a.75.75 0 011.06 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <circle cx="9" cy="9" r="6" />
      <path d="m14 14 4 4" />
    </svg>
  );
}

function FocusIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <path d="M5 5h4M11 5h4M5 5v4M15 5v4M5 11v4M15 11v4M5 15h4M11 15h4" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function getInitials(name: string, email: string) {
  const source = name || email;
  if (!source) {
    return "U";
  }
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length === 1) {
    const [local] = email.split("@");
    return `${parts[0][0]?.toUpperCase() ?? "U"}${local?.[0]?.toUpperCase() ?? ""}`;
  }
  return `${parts[0][0]?.toUpperCase() ?? "U"}${parts[1][0]?.toUpperCase() ?? ""}`;
}
