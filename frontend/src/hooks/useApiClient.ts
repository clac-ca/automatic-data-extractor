import { useMemo } from "react";

import { ApiClient } from "@api/client";

export function useApiClient(): ApiClient {
  return useMemo(() => new ApiClient(), []);
}
