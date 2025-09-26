import { FormEvent, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../app/auth/AuthContext";

export function SignInPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { status, email, error, signIn, clearError } = useAuth();
  const [formEmail, setFormEmail] = useState(() => email ?? "");
  const [password, setPassword] = useState("");

  const redirectTarget = useMemo(() => {
    const state = location.state as { from?: string } | undefined;
    if (state?.from && typeof state.from === "string") {
      return state.from;
    }
    return "/workspaces";
  }, [location.state]);

  useEffect(() => {
    if (status === "authenticated") {
      navigate(redirectTarget, { replace: true });
    }
  }, [navigate, redirectTarget, status]);

  useEffect(() => {
    setFormEmail(email ?? "");
  }, [email]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await signIn(formEmail.trim(), password);
    } catch (submitError) {
      console.error(submitError);
    }
  };

  const busy = status === "authenticating";

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Sign in</h1>
          <p className="page-intro">
            Use your ADE credentials to access workspace documents and results.
          </p>
        </div>
      </div>
      <form className="card form" style={{ gridColumn: "1 / -1", maxWidth: 420 }} onSubmit={handleSubmit} noValidate>
        <label className="form-field">
          <span>Email address</span>
          <input
            className="input"
            type="email"
            value={formEmail}
            autoComplete="username"
            onChange={(event) => {
              if (error) {
                clearError();
              }
              setFormEmail(event.target.value);
            }}
            required
          />
        </label>
        <label className="form-field">
          <span>Password</span>
          <input
            className="input"
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(event) => {
              if (error) {
                clearError();
              }
              setPassword(event.target.value);
            }}
            required
          />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button className="button-primary" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
