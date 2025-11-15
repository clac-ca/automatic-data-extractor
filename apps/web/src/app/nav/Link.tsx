import React from "react";
import type { ComponentPropsWithoutRef, MouseEvent, MouseEventHandler } from "react";

import { useNavigate, useLocation } from "./history";

type AnchorProps = ComponentPropsWithoutRef<"a">;

const HTTP_PROTOCOLS = new Set(["http:", "https:"]);

function isModifiedEvent(event: MouseEvent<HTMLAnchorElement>) {
  return (
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  );
}

function shouldHandleClientNavigation(anchor: HTMLAnchorElement) {
  if (anchor.target && anchor.target !== "_self") {
    return false;
  }

  if (anchor.hasAttribute("download")) {
    return false;
  }

  const protocol = anchor.protocol.toLowerCase();
  if (!HTTP_PROTOCOLS.has(protocol)) {
    return false;
  }

  if (anchor.origin !== window.location.origin) {
    return false;
  }

  // TODO: Surface an escape hatch for in-app links that still need native navigation semantics.
  return true;
}

export type LinkProps = React.PropsWithChildren<
  Omit<AnchorProps, "href"> & {
    to: string;
    replace?: boolean;
    onClick?: MouseEventHandler<HTMLAnchorElement>;
  }
>;

export const Link = React.forwardRef<HTMLAnchorElement, LinkProps>(function Link(
  { to, replace, children, onClick, target, rel, ...rest },
  forwardedRef,
) {
  const navigate = useNavigate();

  return (
    <a
      {...rest}
      ref={forwardedRef}
      href={to}
      target={target}
      rel={rel ?? (target === "_blank" ? "noopener noreferrer" : undefined)}
      onClick={(event) => {
        onClick?.(event);

        if (event.defaultPrevented || isModifiedEvent(event)) {
          return;
        }

        const anchor = event.currentTarget;
        if (!shouldHandleClientNavigation(anchor)) {
          return;
        }

        event.preventDefault();
        navigate(to, { replace });
      }}
    >
      {children}
    </a>
  );
});

type NavLinkRenderArgs = { isActive: boolean };
type NavLinkClassName = string | ((args: NavLinkRenderArgs) => string);
type NavLinkChildren =
  | React.ReactNode
  | ((args: NavLinkRenderArgs) => React.ReactNode);

type NavLinkProps = {
  to: string;
  end?: boolean;
  className?: NavLinkClassName;
  children?: NavLinkChildren;
} &
  Omit<LinkProps, "to" | "className" | "children">;

export const NavLink = React.forwardRef<HTMLAnchorElement, NavLinkProps>(function NavLink(
  { to, end, className, children, ...rest },
  forwardedRef,
) {
  const { pathname } = useLocation();
  const isActive = end
    ? pathname === to
    : pathname === to || pathname.startsWith(`${to}/`);
  const computedClassName =
    typeof className === "function" ? className({ isActive }) : className;
  const renderedChildren =
    typeof children === "function" ? children({ isActive }) : children;
  const { ["aria-current"]: ariaCurrentProp, ...linkProps } = rest;

  return (
    <Link
      {...linkProps}
      ref={forwardedRef}
      to={to}
      className={computedClassName}
      aria-current={ariaCurrentProp ?? (isActive ? "page" : undefined)}
    >
      {renderedChildren}
    </Link>
  );
});
