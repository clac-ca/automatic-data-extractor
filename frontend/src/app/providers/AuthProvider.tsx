import type { PropsWithChildren } from "react";
import { createContext, useContext, useMemo } from "react";

type AuthState = {
  token: string;
  userName: string;
};

const MOCK_AUTH_STATE: AuthState = {
  token: "mock-access-token",
  userName: "workspace-admin@example.com",
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const value = useMemo(() => MOCK_AUTH_STATE, []);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);

  if (!auth) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return auth;
}
