/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, type ReactNode } from "react";

import type { SessionEnvelope } from "../../../shared/types/auth";
import { refreshSession } from "../api";

type RefetchSession = () => Promise<unknown>;

export interface SessionContextValue {
  readonly session: SessionEnvelope;
  readonly refetch: RefetchSession;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export interface SessionProviderProps {
  readonly session: SessionEnvelope;
  readonly refetch: RefetchSession;
  readonly children: ReactNode;
}

export function SessionProvider({ session, refetch, children }: SessionProviderProps) {
  useSessionAutoRefresh(session, refetch);

  return (
    <SessionContext.Provider value={{ session, refetch }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSessionContext(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSessionContext must be used within a SessionProvider");
  }
  return context;
}

export function useSession() {
  return useSessionContext().session;
}

export function useSessionRefetch() {
  return useSessionContext().refetch;
}

const REFRESH_BUFFER_MS = 60_000;

function useSessionAutoRefresh(session: SessionEnvelope, refetch: RefetchSession) {
  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const expiresAt = Date.parse(session.expires_at);
    const refreshExpiresAt = Date.parse(session.refresh_expires_at);

    if (Number.isNaN(expiresAt) || Number.isNaN(refreshExpiresAt)) {
      return undefined;
    }

    const now = Date.now();
    if (refreshExpiresAt <= now) {
      void refetch().catch((error) => {
        console.warn("Failed to refetch session after refresh expiry", error);
      });
      return undefined;
    }

    const targetTime = Math.min(expiresAt, refreshExpiresAt) - REFRESH_BUFFER_MS;
    const delay = Math.max(targetTime - now, 0);
    let cancelled = false;

    const timeoutId = window.setTimeout(async () => {
      try {
        await refreshSession();
        if (cancelled) {
          return;
        }
        await refetch().catch((refetchError) => {
          console.warn("Failed to refetch session after refresh", refetchError);
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        console.warn("Failed to refresh session", error);
        await refetch().catch((refetchError) => {
          console.warn("Failed to refetch session after refresh failure", refetchError);
        });
      }
    }, delay);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [refetch, session.expires_at, session.refresh_expires_at]);
}
