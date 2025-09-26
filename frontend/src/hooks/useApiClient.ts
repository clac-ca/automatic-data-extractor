import { useMemo } from "react";

import { ApiClient } from "@api/client";
import { useSession } from "@hooks/useSession";

export function useApiClient(): ApiClient {
  const { session } = useSession();
  const token = session?.accessToken ?? null;

  return useMemo(() => new ApiClient({ getAccessToken: () => token }), [token]);
}
