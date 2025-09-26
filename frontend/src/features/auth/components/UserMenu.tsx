import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useSession } from "@hooks/useSession";

import "@styles/user-menu.css";

export function UserMenu(): JSX.Element {
  const { session, signOut } = useSession();
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const displayName = session?.user.displayName ?? session?.user.email ?? "Account";

  const initials = displayName
    .split(" ")
    .map((part) => part[0]?.toUpperCase())
    .join("")
    .slice(0, 2);

  const handleToggle = () => {
    setIsOpen((current) => !current);
  };

  const handleSignOut = () => {
    signOut();
    setIsOpen(false);
    navigate("/sign-in", { replace: true });
  };

  return (
    <div className="user-menu" ref={containerRef}>
      <button
        type="button"
        className="user-menu__trigger"
        onClick={handleToggle}
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        <span className="user-menu__avatar" aria-hidden="true">
          {initials || "?"}
        </span>
        <span className="user-menu__name">{displayName}</span>
      </button>
      {isOpen ? (
        <div className="user-menu__popover" role="menu">
          <div className="user-menu__meta">
            <div className="user-menu__label">Signed in as</div>
            <div className="user-menu__value">{session?.user.email ?? "Unknown"}</div>
          </div>
          <button
            type="button"
            role="menuitem"
            className="user-menu__item"
            onClick={handleSignOut}
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
