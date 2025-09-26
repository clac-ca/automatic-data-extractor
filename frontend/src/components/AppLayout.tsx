import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../app/auth/AuthContext";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";

interface AppLayoutProps {
  children: ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { status, email, signOut } = useAuth();
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <Link to="/">Automatic Data Extractor</Link>
        </div>
        <nav className="app-nav">
          <Link to="/workspaces">Workspaces</Link>
          {status === "authenticated" ? <WorkspaceSwitcher /> : null}
        </nav>
        <div className="app-actions">
          {status === "authenticated" ? (
            <>
              <span className="auth-indicator">{email}</span>
              <button type="button" className="button-secondary" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <Link to="/sign-in" className="button-primary">
              Sign in
            </Link>
          )}
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
