import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";

interface UserMenuItem {
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly onSelect: () => void;
}

export interface UserMenuProps {
  readonly displayName: string;
  readonly email: string;
  readonly items?: readonly UserMenuItem[];
  readonly onSignOut: () => void;
  readonly isSigningOut?: boolean;
  readonly className?: string;
}

export function UserMenu({
  displayName,
  email,
  items = [],
  onSignOut,
  isSigningOut = false,
  className,
}: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handleClick = (event: MouseEvent) => {
      if (!menuRef.current) {
        return;
      }
      if (!menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", handleClick);
    return () => window.removeEventListener("mousedown", handleClick);
  }, [open]);

  const initials = useMemo(() => {
    const source = displayName || email;
    return source
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join("")
      .padEnd(2, "•");
  }, [displayName, email]);

  return (
    <div ref={menuRef} className={clsx("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="focus-ring inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2 py-1 text-left text-sm font-semibold text-slate-700 shadow-sm transition hover:border-slate-300"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
          {initials}
        </span>
        <span className="hidden min-w-0 flex-col leading-tight sm:flex">
          <span className="truncate">{displayName || "Signed in"}</span>
          <span className="truncate text-xs font-normal text-slate-400">{email}</span>
        </span>
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-2 text-sm shadow-xl"
        >
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
              className="w-full rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-700 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
            >
              <span>{item.label}</span>
              {item.description ? (
                <span className="mt-0.5 block text-xs font-normal text-slate-400">
                  {item.description}
                </span>
              ) : null}
            </button>
          ))}
          {items.length > 0 ? <div className="my-1 h-px bg-slate-200" aria-hidden="true" /> : null}
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
            className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-semibold text-danger-600 transition hover:bg-danger-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:opacity-60"
            disabled={isSigningOut}
          >
            <span>Sign out</span>
            {isSigningOut ? (
              <span className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : null}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export type { UserMenuItem };
