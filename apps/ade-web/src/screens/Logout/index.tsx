import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useNavigate } from "@app/nav/history";
import { performLogout, sessionKeys } from "@shared/auth/api";

export default function LogoutRoute() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useEffect(() => {
    let cancelled = false;

    const controller = new AbortController();
    (async () => {
      try {
        await performLogout({ signal: controller.signal });
      } finally {
        if (!cancelled) {
          queryClient.removeQueries({ queryKey: sessionKeys.root, exact: false });
          navigate("/login", { replace: true });
        }
      }
    })().catch(() => {
      if (!cancelled) {
        navigate("/login", { replace: true });
      }
    });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [navigate, queryClient]);

  return null;
}
