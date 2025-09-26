import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

const STORAGE_KEY = "ade-session";

export interface SessionUser {
  readonly id: string;
  readonly email: string;
  readonly role: string;
  readonly isActive: boolean;
  readonly displayName?: string;
}

export interface Session {
  readonly accessToken: string;
  readonly user: SessionUser;
}

interface SessionContextValue {
  readonly session: Session | null;
  readonly isAuthenticated: boolean;
  readonly signIn: (session: Session) => void;
  readonly signOut: () => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

function readStoredSession(): Session | null {
  if (typeof window === "undefined") {
    return null;
  }

  const rawValue = window.localStorage.getItem(STORAGE_KEY);

  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as Session;
  } catch (error) {
    console.warn("Failed to parse stored session", error);
    return null;
  }
}

function persistSession(session: Session | null): void {
  if (typeof window === "undefined") {
    return;
  }

  if (session) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

interface SessionProviderProps {
  readonly children: ReactNode;
}

export function SessionProvider({ children }: SessionProviderProps): JSX.Element {
  const [session, setSession] = useState<Session | null>(() => readStoredSession());

  useEffect(() => {
    persistSession(session);
  }, [session]);

  const signIn = useCallback((nextSession: Session) => {
    setSession(nextSession);
  }, []);

  const signOut = useCallback(() => {
    setSession(null);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      session,
      isAuthenticated: Boolean(session),
      signIn,
      signOut
    }),
    [session, signIn, signOut]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSessionContext(): SessionContextValue {
  const context = useContext(SessionContext);

  if (!context) {
    throw new Error("useSessionContext must be used within a SessionProvider");
  }

  return context;
}
