import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useLocation, useNavigate } from "@app/nav/history";

import { completeAuthCallback, sessionKeys } from "@shared/auth/api";
import { chooseDestination, resolveRedirectParam } from "@shared/auth/utils/authNavigation";
import { ApiError } from "@shared/api";
import { Button } from "@ui/Button";
import { PageState } from "@ui/PageState";

export default function AuthCallbackScreen() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams(location.search);
    const returnTo = resolveRedirectParam(
      params.get("return_to") ?? params.get("redirectTo") ?? params.get("next"),
    );

    async function finishSso() {
      try {
        const envelope = await completeAuthCallback();
        if (cancelled) {
          return;
        }

        queryClient.setQueryData(sessionKeys.detail(), envelope);

        const next = chooseDestination(null, returnTo);

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
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
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
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <PageState title="Finishing sign-in" variant="loading" />
    </div>
  );
}
