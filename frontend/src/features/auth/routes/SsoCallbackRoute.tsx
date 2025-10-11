import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { ApiError, get } from "../../../shared/api/client";
import type { SessionEnvelope } from "../../../shared/api/types";
import { sessionKeys } from "../hooks/sessionKeys";
import { resolveSessionDestination } from "../utils/resolveSessionDestination";

export function SsoCallbackRoute() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<"loading" | "error">("loading");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");
    const errorDescription = searchParams.get("error_description");

    if (error) {
      setStatus("error");
      setMessage(errorDescription || "Single sign-on was cancelled. Try signing in again.");
      return;
    }

    if (!code || !state) {
      setStatus("error");
      setMessage("Missing authorization response. Start the sign-in flow again.");
      return;
    }

    const codeValue = code;
    const stateValue = state;
    let cancelled = false;

    async function completeLogin() {
      try {
        const session = await get<SessionEnvelope>(
          `/auth/sso/callback?code=${encodeURIComponent(codeValue)}&state=${encodeURIComponent(stateValue)}`,
        );
        if (cancelled) {
          return;
        }

        queryClient.setQueryData(sessionKeys.detail(), session);
        navigate(resolveSessionDestination(session), { replace: true });
      } catch (error_) {
        if (cancelled) {
          return;
        }

        if (error_ instanceof ApiError) {
          setMessage(error_.problem?.detail || error_.message);
        } else {
          setMessage("Unable to complete single sign-on. Try again.");
        }
        setStatus("error");
      }
    }

    void completeLogin();

    return () => {
      cancelled = true;
    };
  }, [navigate, queryClient, searchParams]);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-slate-300">
        <p>Completing sign-in…</p>
        <p className="text-xs text-slate-500">You will be redirected shortly.</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-center text-sm text-rose-200">
      <p>{message ?? "Single sign-on failed."}</p>
      <a href="/login" className="font-medium text-sky-300 hover:text-sky-200">
        Return to sign-in
      </a>
    </div>
  );
}
