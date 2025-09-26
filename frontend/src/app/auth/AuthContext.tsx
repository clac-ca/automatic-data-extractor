import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { API_BASE_URL } from "../../api/client";
import { ApiError, normaliseErrorMessage } from "../../api/errors";
import { useToast } from "../../components/ToastProvider";

const TOKEN_STORAGE_KEY = "ade.auth.token";
const EMAIL_STORAGE_KEY = "ade.auth.email";

type AuthStatus = "unauthenticated" | "authenticating" | "authenticated" | "error";

interface AuthContextValue {
  status: AuthStatus;
  token: string | null;
  email: string | null;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

async function requestToken(email: string, password: string): Promise<string> {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);

  const response = await fetch(`${API_BASE_URL}/auth/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
    },
    body,
  });

  const payloadText = await response.text();
  let payload: Record<string, unknown> | null = null;
  if (payloadText) {
    try {
      payload = JSON.parse(payloadText) as Record<string, unknown>;
    } catch (error) {
      throw new ApiError("Unable to parse token response", response.status, payloadText);
    }
  }

  if (!response.ok) {
    const message =
      (payload && typeof payload.detail === "string" && payload.detail) ||
      response.statusText ||
      "Unable to sign in";
    throw new ApiError(message, response.status, payload);
  }

  if (!payload || typeof payload.access_token !== "string") {
    throw new ApiError("Token response was not recognised", response.status, payload);
  }

  return payload.access_token;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const initialToken = useRef<string | null>(
    window.localStorage.getItem(TOKEN_STORAGE_KEY),
  );
  const initialEmail = useRef<string | null>(
    window.localStorage.getItem(EMAIL_STORAGE_KEY),
  );

  const [token, setToken] = useState<string | null>(initialToken.current);
  const [email, setEmail] = useState<string | null>(initialEmail.current);
  const [status, setStatus] = useState<AuthStatus>(
    initialToken.current ? "authenticated" : "unauthenticated",
  );
  const [error, setError] = useState<string | null>(null);
  const { pushToast } = useToast();

  const persistState = useCallback((nextToken: string | null, nextEmail: string | null) => {
    if (nextToken) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, nextToken);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }

    if (nextEmail) {
      window.localStorage.setItem(EMAIL_STORAGE_KEY, nextEmail);
    } else {
      window.localStorage.removeItem(EMAIL_STORAGE_KEY);
    }
  }, []);

  const signIn = useCallback(
    async (nextEmail: string, password: string) => {
      setStatus("authenticating");
      setError(null);

      try {
        const tokenResponse = await requestToken(nextEmail, password);
        setToken(tokenResponse);
        setEmail(nextEmail);
        persistState(tokenResponse, nextEmail);
        setStatus("authenticated");
      } catch (unknownError) {
        const message = normaliseErrorMessage(unknownError);
        setError(message);
        setStatus("error");
        pushToast({ tone: "error", title: "Sign-in failed", description: message });
        throw unknownError;
      }
    },
    [persistState, pushToast],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setEmail(null);
    setStatus("unauthenticated");
    setError(null);
    persistState(null, null);
  }, [persistState]);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo(
    () => ({ status, token, email, error, signIn, signOut, clearError }),
    [status, token, email, error, signIn, signOut, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
