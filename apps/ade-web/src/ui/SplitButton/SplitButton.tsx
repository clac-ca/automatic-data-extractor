import clsx from "clsx";
import { useRef } from "react";
import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";

import { ChevronDownIcon } from "@ui/Icons";

const BASE_PRIMARY =
  "inline-flex items-center gap-2 rounded-l-md px-3 py-1.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0 disabled:cursor-not-allowed";
const BASE_MENU =
  "inline-flex items-center justify-center rounded-r-md border-l px-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0 disabled:cursor-not-allowed";

export interface SplitButtonProps {
  readonly label: ReactNode;
  readonly icon?: ReactNode;
  readonly disabled?: boolean;
  readonly isLoading?: boolean;
  readonly highlight?: boolean;
  readonly className?: string;
  readonly primaryClassName?: string;
  readonly menuClassName?: string;
  readonly title?: string;
  readonly menuAriaLabel?: string;
  readonly menuIcon?: ReactNode;
  readonly onPrimaryClick?: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  readonly onOpenMenu?: (position: { x: number; y: number }) => void;
  readonly onContextMenu?: (event: ReactMouseEvent<HTMLDivElement>) => void;
}

export function SplitButton({
  label,
  icon,
  disabled,
  isLoading,
  highlight,
  className,
  primaryClassName,
  menuClassName,
  title,
  menuAriaLabel = "Open menu",
  menuIcon = <ChevronDownIcon className="h-4 w-4" />,
  onPrimaryClick,
  onOpenMenu,
  onContextMenu,
}: SplitButtonProps) {
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);
  const isDisabled = Boolean(disabled || isLoading);

  const handleMenuClick = (event: ReactMouseEvent<HTMLButtonElement>) => {
    if (isDisabled) {
      return;
    }
    event.preventDefault();
    const rect = menuButtonRef.current?.getBoundingClientRect();
    if (rect) {
      onOpenMenu?.({ x: rect.left, y: rect.bottom });
      return;
    }
    onOpenMenu?.({ x: event.clientX, y: event.clientY });
  };

  return (
    <div
      role="group"
      className={clsx(
        "inline-flex items-stretch rounded-md shadow-sm",
        highlight && "ring-2 ring-brand-300/70 ring-offset-2 ring-offset-transparent",
        className,
      )}
      onContextMenu={onContextMenu}
    >
      <button
        type="button"
        title={title}
        disabled={isDisabled}
        className={clsx(BASE_PRIMARY, primaryClassName)}
        onClick={(event) => {
          if (isDisabled) {
            return;
          }
          onPrimaryClick?.(event);
        }}
      >
        {icon}
        <span className="whitespace-nowrap">{label}</span>
      </button>
      <button
        ref={menuButtonRef}
        type="button"
        aria-label={menuAriaLabel}
        aria-haspopup="menu"
        aria-expanded="false"
        disabled={isDisabled}
        className={clsx(BASE_MENU, menuClassName)}
        onClick={handleMenuClick}
      >
        {menuIcon}
      </button>
    </div>
  );
}
