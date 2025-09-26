import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../app/auth/AuthContext";

interface RequireAuthProps {
  children: ReactNode;
}

export function RequireAuth({ children }: RequireAuthProps) {
  const { status, token } = useAuth();
  const location = useLocation();

  if (status === "authenticating") {
    return (
      <div className="page-container">
        <section className="card" style={{ gridColumn: "1 / -1" }}>
          <p className="page-subtitle">Signing you in…</p>
        </section>
      </div>
    );
  }

  if (status !== "authenticated" || !token) {
    return (
      <Navigate
        to="/sign-in"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  }

  return <>{children}</>;
}
