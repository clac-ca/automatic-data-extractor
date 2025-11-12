import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useLocation, useNavigate } from "@app/nav/history";

import { normalizeSessionEnvelope, sessionKeys } from "@shared/auth/api";
import { chooseDestination } from "@shared/auth/utils/authNavigation";
import { ApiError, get } from "@shared/api";
import type { components } from "@openapi";
import { Button } from "@ui/button";
import { PageState } from "@ui/PageState";

export default function AuthCallbackRoute() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams(location.search);
    const code = params.get("code");
    const stateParam = params.get("state");

    if (!code || !stateParam) {
      setErrorMessage("Missing authorization details from the identity provider.");
      return;
    }

    async function finishSso() {
      try {
        const query = params.toString();
        const envelope = await get<SessionEnvelope>(`/auth/sso/callback?${query}`);
        if (cancelled) {
          return;
        }

        const normalized = normalizeSessionEnvelope(envelope);
        queryClient.setQueryData(sessionKeys.detail(), normalized);

        const next = chooseDestination(normalized.return_to, params.get("next"));

        navigate(next, { replace: true });
      } catch (error: unknown) {
        if (cancelled) {
          return;
        }
        if (error instanceof ApiError) {
          setErrorMessage(error.problem?.detail ?? error.message);
        } else if (error instanceof Error) {
          setErrorMessage(error.message);
        } else {
          setErrorMessage("Unexpected callback error.");
        }
      }
    }

    void finishSso();

    return () => {
      cancelled = true;
    };
  }, [location.search, navigate, queryClient]);

  if (errorMessage) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState
          title="Unable to finish sign-in"
          description={errorMessage}
          variant="error"
          action={
            <Button variant="secondary" onClick={() => navigate("/login", { replace: true })}>
              Return to sign in
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <PageState title="Finishing sign-in" variant="loading" />
    </div>
  );
}

type SessionEnvelope = components["schemas"]["SessionEnvelope"];
